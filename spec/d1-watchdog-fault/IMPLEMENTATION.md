# 实施文档：D1 防挂死与容错补全

***

id: d1-watchdog-fault-IMPLEMENTATION
type: design
version: 1.1
status: implemented
date: 2026-09-02
depends: \[d1-watchdog-fault-RESEARCH]
upstream: null
--------------

> **Feature**: D1 防挂死与容错补全（health 看门狗 + LiteLLM fallbacks + 参数台账）
> **创建日期**: 2026-09-02
> **状态**: draft
> **Spec 步骤**: Step 3-6
> **基于调研**: [RESEARCH.md](./RESEARCH.md)
> **决策来源**: [ADR-0001](../../adr/ADR-0001-集群运维框架审计与四项改进决策.md) §决策 4

***

## 1. 实施范围

| 交付物 | 落位 | 站点 |
| ------ | ---- | ---- |
| T1 看门狗脚本 `cluster-watchdog` | 两站 /usr/local/bin + 仓库快照 ops/station-bin/ | A + B |
| T2 systemd unit（service + timer 60s） | 两站 /etc/systemd/system | A + B |
| T3 LiteLLM fallbacks + rpm 限流 | B 站 ~/litellm/config.yaml（改前备份） | B |
| T4 参数台账 | 主控站 spec/infer-load/params-ledger.md | 主控 |
| T5 手册更新（看门狗节 + fallbacks 边界） | docs/双机推理集群使用手册.md | 主控 |
| T6 清理与提交 | .litellm-research/ 删除、git commit | 主控 |

**边界（不做）**: WatchdogSec（ADR 已否决）/ 邮件设施（Beszel 已有）/ rps 限流（不存在）/ context_window_fallbacks（nemotron→gpt-oss ctx 降级 ADR 已接受报错而非回切）/ 看门狗自动拉起模型（违背零自加载——只处置已 active 的服务）。

## 2. 技术栈与约定

- 看门狗: bash（两站 /bin/bash 通用，零 Python 依赖，与 station-bin 既有脚本同栈）
- 探测路径: `/sys/class/drm/card*/device/mem_info_gtt_used`（E1 实证存在，infer-unload 同款）
- 对端探测: `ssh -o BatchMode=yes -o ConnectTimeout=10`（mDNS 名，实测单次可达 ~10s，timer 60s 周期可容忍）
- 状态持久化: `/var/lib/cluster-watchdog/`（计数器文件，跨 timer 触发保持连续失败计数）
- 修改站侧脚本铁律: 先改仓库（ops/station-bin/）review → scp 上站 → 两站 md5 一致性校验（station-bin README 既有约定）

## 3. 任务分解

### T1 看门狗脚本 cluster-watchdog

**探测逻辑**（每 60s 一次，oneshot <10s）:

```
探测 1 [本机服务] systemctl 有 active 的 llama-server@* ?
  ├─ 无 → 跳过（零自加载: 未加载≠故障）
  ├─ 加载窗口 (pgrep infer-load / load-mem-gate) → 跳过（防加载期 503 误报）
  └─ 有 → curl -sf -m 8 http://127.0.0.1:8080/health
        ├─ OK → 计数清零
        └─ 失败 → fail[local]++
             连续 3 → WARN (journal + LOG)
             连续 5 → 处置: sudo systemctl restart llama-server@<instance> + 记录

探测 2 [本机 GTT] cat /sys/class/drm/card*/device/mem_info_gtt_used
  ├─ 有 active 实例 → 跳过水位判定（加载态 GTT 高位正常）
  └─ 无 active 实例 且 used > 20G → WARN (M5: LM Studio GUI 残留/孤儿进程)
       （只告警不处置—— unloaded 态的残留由人工判断是否 LM Studio 在用）

探测 3 [对端] ssh BatchMode 对端 '有 active 实例? + curl health'
  ├─ SSH 失败 → fail[peer]++ 连续 3 → WARN "对端主机失联 (M3/M4)"
  ├─ SSH OK + health OK → 计数清零
  ├─ SSH OK + 对端无 active 实例 → 计数清零（未加载是正常态, 零自加载原则）
  └─ SSH OK + health 挂 (有 active 实例) → WARN "对端服务冻结 (M2, 对端本机看门狗自治)"
```

**要点**:

- 对端模态**只通知不处置**（RESEARCH §4.2-2: M3/M4 无法远程处置；对端 M2 由对端自己的看门狗处置——两站互探闭环里各管各的本机处置）
- 通知 = journal（systemd 自动收 oneshot stdout）+ 追加 `/var/log/cluster-watchdog.log`（logrotate 不配，量级极低——仅 WARN/处置才写）
- 计数器文件: `/var/lib/cluster-watchdog/fail.local` `fail.peer`（纯数字，touch 前置 mkdir -p）
- 探测目标常量置脚本头（PEER=对方 .local 名），两站部署时仅此一行不同（A 站 PEER=scott-lau-GTR-Pro.local，B 站 PEER=scott-lau-NEX.local）——用 sed 生成两份或部署时参数化

**处置动作安全约束**: restart 前二次确认 `systemctl is-active`（防探测-处置间隙服务已被人工 stop）；restart 仅一次/计数周期（处置后计数清零，若再挂 5 次会再 restart——StartLimitIntervalSec=0 保证 systemd 不拦）。

### T2 systemd unit（两站）

```ini
# /etc/systemd/system/cluster-watchdog.service
[Unit]
Description=cluster health watchdog (one-shot probe, see timer)
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/cluster-watchdog

# /etc/systemd/system/cluster-watchdog.timer
[Unit]
Description=run cluster-watchdog every 60s

[Timer]
OnBootSec=2min
OnUnitActiveSec=60s

[Install]
WantedBy=timers.target
```

- `systemctl daemon-reload && systemctl enable --now cluster-watchdog.timer`
- 首跑观察: `journalctl -u cluster-watchdog -f`（3 个周期无异常 WARN 即稳）
- **不与"零自加载"冲突**: timer 是探测机制非推理服务自启（ADR-0001 机制原理节已背书）

### T3 LiteLLM fallbacks + rpm

改 B 站 `~/litellm/config.yaml`（先 `cp config.yaml config.yaml.bak-d1`）:

```yaml
model_list:
  - model_name: nemotron
    litellm_params:
      model: openai/nemotron
      api_base: http://127.0.0.1:8080/v1
      api_key: sk-local-noauth
      rpm: 30
  - model_name: gpt-oss
    litellm_params:
      model: openai/gpt-oss
      api_base: http://10.10.10.1:8080/v1
      api_key: sk-local-noauth
      rpm: 30

router_settings:
  routing_strategy: usage-based-routing-v2   # v1.1 新增, 见下
  num_retries: 1
  cooldown_time: 30
  background_health_checks: true
  fallbacks:
    - nemotron: ["gpt-oss"]
    - gpt-oss: ["nemotron"]
```

**v1.1 实施修正（A6 首轮实测发现）**: 仅加 `rpm` 不生效——默认 `simple-shuffle` 路由策略下 LiteLLM 不注册 rpm pre-call 检查 handler（`async_routing_strategy_pre_call_checks` 只遍历 `litellm.callbacks` 中注册的策略 handler），实测 40 并发全 200 直通。补 `routing_strategy: usage-based-routing-v2`（注册 `LowestTPMLoggingHandler_v2` → `async_pre_call_check` 执行部署级 rpm 拦截，源码 lowest_tpm_rpm_v2.py L135-190 已在 B 站实文件核验）后 rpm enforcement 生效。每组仅 1 个 deployment，路由选择行为不受影响。

- **只动 router_settings 块与新增 rpm 行**，master_key/timeout/health_check_interval 原样不动（RESEARCH §3.7-3 备案原则）
- rpm=30 依据: llama-server 默认单 slot 串行队列，4-agent 集群并发场景下 30 req/min（平均 0.5 req/s）已高于实际峰值；超限请求由网关背压消化——防的是并发风暴不是常态限速
- **超限实际行为（A6 实测, v1.1 修正预期）**: 非 429 也非 fallback——rpm pre-call 检查抛出的 RateLimitError 带 `retry-after: 60` 头，LiteLLM 内部按该头延迟 60s 重试，落进新分钟窗口（计数归零）后成功返回 200。实测两轮 40 并发：首轮 ~24 个快速通过 + 16 个压 ~62-65s 后成功；第二轮 29 快 + 11 压 60s。无 429 / 无降级 / 无 5xx，llama-server 实际接收速率被压在 rpm 内（风暴隔离目标达成）。该隐性背压行为已写入手册 fallbacks 边界节。
- 重启: `sudo systemctl restart litellm` → `curl /health/liveliness` 冒烟
- **验证见 §4-A4**（停 nemotron 后请求降级实测）

### T4 参数台账 spec/infer-load/params-ledger.md

三区结构（依据 RESEARCH §3.6 素材）:

1. **当前值 + 依据区**: 6 实例 × (CTX/THREADS/N_CPU_MOE/RPC_TARGET/EXTRA_FLAGS)，每字段标 `依据: results-ledger <节名>` 或 `无实测依据（模板默认）`
2. **反例区**: ngram-simple 投机（gpt-oss -52%）/ nemotron RPC -17.3% / m27 thinking 失控三案例
3. **缺口区**: THREADS=16 未扫描 / N_CPU_MOE 0-vs-8 无对比 / batch/ubatch 默认——显式声明"未调优"

维护约定: 每次改 conf 调参必须同步台账（写入手册 §"改 conf 即调参"处一句引用）。

### T5 手册更新

1. 新增 §"集群看门狗（D1）"小节: 探测矩阵（M1-M5 五模态×处置）+ `journalctl -u cluster-watchdog` / `cat /var/log/cluster-watchdog.log` 排查入口 + 误报阈值调整说明（fail 阈值在脚本头常量）
2. LiteLLM 节补 fallbacks: 双向互备 + **已知边界: nemotron 128k → gpt-oss 32k conf 降级时超 32k 请求报错（非截断），长上下文任务勿依赖 fallback**（RESEARCH §3.4 源码级结论）
3. "零自加载"表述加注: `（网关 litellm 与看门狗 timer 除外）`（ADR-0001 后续行动项落账）
4. 参数台账引用: conf 调参小节指向 params-ledger.md

### T6 清理与提交

1. 删 `.litellm-research/`（subagent 源码，结论已固化 RESEARCH §3.4）
2. 删主控站 `tmp_d1probe.sh`（调研临时脚本）
3. 站侧脚本同步快照: cluster-watchdog → ops/station-bin/（README 文件清单 +1 行，注明两站仅 PEER 行不同）
4. git: 顺手提交 station-bin/README.md 纯格式 diff（D4 同款先例）+ 本 spec 全部 + 台账 + 手册 + station-bin 快照

## 4. 验证方案（验收门）

| # | 验收项 | 方法 | 通过判据 |
| - | ----- | ---- | ------- |
| A1 | 看门狗常驻探测无谎报 | enable timer 后观察 5 周期（~5min，当前 A=gpt-oss B=nemotron 均健康态） | journal 无 WARN；两站 timer NEXT 持续刷新 |
| A2 | M2 处置实测 | B 站 kill -STOP llama-server 主进程（模拟冻结: 进程活 /health 挂）→ 观察看门狗处置 → 恢复后 kill -9 验证 M1（systemd Restart 自动拉起，看门狗不干预）| 连续 5 失败后 journal 见 WARN×2 + RESTART 记录（注: STOP 态进程收不到 SIGTERM，restart 需等 systemd TimeoutStopSec 默认 90s 后 SIGKILL，观察窗口留 3min）；恢复后计数清零 |
| A3 | 对端探测三态 | A 站 kill -STOP gpt-oss 主进程（SSH OK + 实例 active + health 挂）→ 观察 B 站看门狗；恢复后再验清零 | B 站 journal 出现 "对端服务冻结" WARN；恢复后无持续新增 |
| A4 | fallback 降级实测 | B 站 stop nemotron → 经 :4000 请求 `model=nemotron`（max_tokens=32）| 返回 200 且 content 非空（实际由 gpt-oss 服务）；`model` 字段/响应头可见 fallback 痕迹；恢复 nemotron 后正向请求正常 |
| A5 | e2e 回归 | `python ops/cluster.py e2e` | 双路由 ✓（退出码 0） |
| A6 | rpm 限流生效 | 连发 40 个并发小请求（model=nemotron）| **实测通过（行为与预期不同, 已记录）**: 超限请求不 429 不降级，而是被网关按 `retry-after: 60` 延迟重试（新分钟窗口计数归零后 200），无 5xx；llama-server 实际接收速率被压在 rpm=30 内（风暴隔离目标达成）。两轮复现一致（24+16 / 29+11 分布） |
| A7 | 台账一致性 | 台账参数 vs `sudo cat /etc/llama-instances/*.env` 实测逐字段比对 | 6 实例零偏差；反例区与 results-ledger 引用可追溯 |
| A8 | 误报防护 | 加载窗口内（infer-load 运行中）观察看门狗 | 无 restart 误触发（加载窗口跳过逻辑生效） |

**注**: A2 的 kill -STOP 模拟冻结态在恢复（kill -CONT）前服务不可用 ~5min，安排在无任务窗口执行；A4 期间 nemotron 用户请求会真实降级到 gpt-oss——与生产行为一致，属预期。

## 5. 回滚方案

| 组件 | 回滚 |
| ---- | ---- |
| 看门狗 | `sudo systemctl disable --now cluster-watchdog.timer`（脚本/单元留在盘上无副作用；计数器目录可删） |
| fallbacks/rpm | `cp config.yaml.bak-d1 config.yaml && sudo systemctl restart litellm`（单文件单服务，秒级） |
| 台账/手册 | git revert（纯文档，无运行时影响） |

## 6. 任务顺序与依赖

```
T4 台账（纯文档，零风险，先行）
 → T1 看门狗脚本（仓库内编写）
 → T2 两站部署 + A1/A2/A3 验收
 → T3 fallbacks（B 站）+ A4/A6 验收
 → A5 e2e 回归（全链路）
 → T5 手册 + T6 清理提交
```

T4 先行的理由: 台账是纯文档零风险，且 T3 改 conf 前台账先立，rpm/ctx 的参数决策直接进台账形成首条记录（fallbacks 的 rpm=30 成为台账第一个"新增依据"条目）。
