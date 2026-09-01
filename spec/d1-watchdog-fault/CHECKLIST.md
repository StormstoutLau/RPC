# 审查验收 Checklist：D1 防挂死与容错补全

***

id: d1-watchdog-fault-CHECKLIST
type: design
version: 1.1
status: accepted
date: 2026-09-02
depends: \[d1-watchdog-fault-IMPLEMENTATION, d1-watchdog-fault-RESEARCH]
upstream: null
--------------

> **Feature**: D1 防挂死与容错补全（health 看门狗 + LiteLLM fallbacks + 参数台账）
> **创建日期**: 2026-09-02
> **状态**: 已验收通过（2026-09-02，A1-A8/R1-R3/C1-C7 全过，见 §3/§4）
> **Spec 步骤**: Step 7-8, 10
> **基于实施**: [IMPLEMENTATION.md](./IMPLEMENTATION.md)
> **基于调研**: [RESEARCH.md](./RESEARCH.md)
> **审查轮次**: 第 1 轮（文档审查，实施前门）

***

## 0. 审查结论速览

**结论：有条件通过（3 项已修正进 IMPLEMENTATION，1 项事实核验待补）。** 文档层抓出 4 处问题：P1/P2/P3（设计缺陷，已修正）、P4（验收设计依赖的实测事实，已补验通过）。

| # | 审查发现 | 性质 | 处置 |
| - | ------- | ---- | ---- |
| P1 | A2/A3 原设计用 `systemctl stop` 模拟故障，但 stop 是干净停止——既不触发 Restart=on-failure，也被看门狗当作"未加载=正常态"跳过，**两个验收都无法产生预期 WARN/RESTART** | 逻辑缺陷（文档层） | 已修正：A2/A3 均改用 kill -STOP 模拟冻结态（进程活 /health 挂，正是看门狗目标模态 M2）；A2 补 kill -9 验证 M1 与看门狗不冲突；补注 STOP 态 restart 需等 TimeoutStopSec~90s |
| P2 | A6 判据"部分返回 429"不成立——配置 fallbacks 后 429 会触发降级链（RESEARCH §3.4 实锤），超限请求可能被 fallback 到对端成功返回 | 判据缺陷 | 已修正：判据改为"429 或降级服务（两行为皆合规），无 5xx，验收时记录实际行为" |
| P3 | T1 探测 3 伪码缺"SSH OK + 对端无 active 实例"分支——该态是零自加载原则下的正常态，不定义会落进默认分支误报 | 行为缺口 | 已修正：显式补"计数清零（未加载是正常态）"分支 |
| P4 | RESEARCH §3.3 的 `mem_info_gtt_used` 存在性原为推断（infer-unload 生产在用的间接证据） | 证据等级不足 | **已补验（E1, 2026-09-02）**：两站实测 B=90.5G（nemotron 加载中）/ A=64.8G（gpt-oss 加载中），与实际加载态吻合——路径实证成立 |

## 1. 事实核验（Anti-Hallucination Review, 2026-09-02）

**方法**: 对 RESEARCH/IMPLEMENTATION 全部事实性声明逐条与实测输出比对；对 subagent 源码级结论做本地抽查（排除子代理幻觉）。

### 1.1 RESEARCH 声明核验

| 正文声明 | 核验方式 | 结果 |
| ------- | ------- | ---- |
| llama-server@.service: Restart=on-failure/RestartSec=10/StartLimitIntervalSec=0 | E1 cat 两站 unit 全文 | ✅ |
| rpc-server@.service: Restart=always | E1 cat A 站 unit | ✅ |
| 6 实例 conf 逐字段（CTX/THREADS/N_CPU_MOE/RPC_TARGET） | E1 `sudo cat /etc/llama-instances/*.env` 全文比对 | ✅ 含 RPC_NODES.env 非实例的辨析 |
| A 站 conf 仅 1 个 | E1 `ls /etc/llama-instances/` | ✅ |
| debugfs gtt_mem_usage 不存在 | E1 cat 返回 NO_GTT_FILE | ✅ |
| mem_info_gtt_used 两站存在 | **本轮补验**：B=90.5G / A=64.8G | ✅ 且数值与加载态吻合 |
| Beszel 0.18.8 / systemd 部署（非 Docker） | E1 `--version` + `systemctl cat` | ✅ |
| 8 条告警（CPU 95×2 / Temp 85×2 / Disk 90×2 / Status×2） | E1 data.db alerts 表 sqlite 只读查询 | ✅ |
| email 通知已配（peng.liu.john@gmail.com） | E1 user_settings 表 | ✅ |
| sqlite3 CLI 缺失 | E1 which | ✅ |
| LiteLLM 1.98.0 / liveliness OK / health/models 404 | E1 `--version` + curl | ✅ |
| config.yaml 基线（双路由/retry/cooldown） | E1 cat 全文 | ✅ |
| e1_hang_repro.sh 看门狗为一次性测试脚本 | E1 read 脚本 | ✅ 20s ping×3，非常驻 |
| results-ledger 引用（17.3→20.3 / 96.5k needle / ngram -52% / m27 失控） | E2 grep ledger 原文 | ✅ |

### 1.2 subagent 源码结论抽查（防子代理幻觉）

| subagent 结论 | 本地抽查（.litellm-research/ 实文件） | 结果 |
| ------------- | --------------------------------- | ---- |
| ROUTER_MAX_FALLBACKS=5 | constants.py L9 逐字命中 | ✅ |
| DEFAULT_MAX_RETRIES=2 | constants.py L21 逐字命中 | ✅ |
| rpm 存在 / fallbacks 在 router_settings | types_router.py L39/122/285 逐字命中 | ✅ |
| llama.cpp ctx 错误串被识别映射 | exception_mapping_utils.py L92 "exceeds the available context size" | ✅ |
| fallback 调用链存在 | router.py 多处 async_function_with_fallbacks | ✅ |

**抽查 5/5 全过——subagent 结论可信，源码目录在 T6 按计划删除。**

### 1.3 残余风险声明

1. "llama-server 默认单 slot"（IMPLEMENTATION T3 rpm 依据的组成部分）为 E4 常识断言，未实测——但 rpm=30 的主要依据是"高于实际峰值"的估计（E4），已在 IMPL 标注为防并发风暴而非精确调优，不阻塞。
2. subagent 的 docs.litellm.ai 引用页未逐字复核（本地源码实证已覆盖相同结论，源码 > 文档）。
3. A2/A3 的 kill -STOP 方案未预演——验收窗口留 3min 观察（IMPL A2 注）。

## 2. 文档一致性验收

### 2.1 RESEARCH ↔ IMPLEMENTATION 对齐

| 检查项 | 状态 |
| ----- | --- |
| RESEARCH §4.2-1 互探架构 → IMPL T1 探测 1/3 | ☑ |
| RESEARCH §4.2-2 分级处置（3 WARN/5 处置） → IMPL T1 计数器逻辑 | ☑ |
| RESEARCH §3.4 fallbacks 语法 → IMPL T3 YAML 块 | ☑ |
| RESEARCH §4.2-4 台账三区结构 → IMPL T4 | ☑ |
| RESEARCH §4.2-5 边界（不做清单） → IMPL §1 边界节 | ☑ |
| P1-P4 修正后交叉核对无矛盾 | ☑ |

### 2.2 与 ADR-0001 / 既有规范的一致性

| 检查项 | 状态 | 说明 |
| ----- | --- | ---- |
| D1.1-D1.4 四子项全覆盖 | ☑ | D1.4（观测网维持不动）= 无操作项，IMPL 边界节已声明 |
| 不越 D2 边界（不改 cluster.py 核心逻辑） | ☑ | 状态文件仅作为人工排查入口提及，不强制改代码 |
| 零自加载原则 | ☑ | timer 是探测非推理服务自启；探测 1/3 均含"未加载≠故障"判定 |
| station-bin 修改流程（先仓库后上站+md5） | ☑ | IMPL §2 约定 |
| 破坏性操作备份铁律 | ☑ | T3 config.yaml.bak-d1；T6 台账/手册 git revert |
| ADR 待办落账：手册"零自加载"加注 | ☑ | IMPL T5-3 |

## 3. 实施验收（验收门）

### 3.1 交付物清单

| # | 交付物 | 落位 | 状态 |
| - | ----- | ---- | ---- |
| C1 | cluster-watchdog 脚本 | 两站 /usr/local/bin + ops/station-bin/ | ✅ md5 归一化一致（仅 PEER 行差异，R2） |
| C2 | systemd service+timer（60s） | 两站 /etc/systemd/system | ✅ 两站 timer NEXT 持续刷新（~66s 周期） |
| C3 | LiteLLM fallbacks+rpm（备份 .bak-d1） | B 站 ~/litellm/config.yaml | ✅ 含 v1.1 修正 routing_strategy（见 A6）；R3 三保留字段原样 |
| C4 | params-ledger.md | spec/infer-load/ | ✅ 含网关参数节（D1 新增依据条目） |
| C5 | 手册 D1 节 + fallbacks 边界 + 零自加载加注 | docs/双机推理集群使用手册.md | ✅ |
| C6 | .litellm-research/ + tmp 脚本清理 | —— | ✅ |
| C7 | git 提交（spec + 台账 + 手册 + station-bin + README 格式 diff） | —— | ✅ |

### 3.2 行为验收（IMPL §4 A1-A8）

| # | 验收项 | 状态 | 实施记录 |
| - | ----- | ---- | ------- |
| A1 | 常驻探测 5 周期无谎报 | ✅ | 两站 20+ 周期 journal 零 WARN；A 站曾于 A4 停机窗口正确检出对端过渡态（真阳性非误报） |
| A2 | M2 冻结处置（kill -STOP）+ M1 不冲突（kill -9） | ✅ | 两站同步实测：WARN x3(01:43)/x4/x5 → ACT restart(01:45:03 B / 01:45:21 A) 时间线精确；恢复后 fail.local=0。M1：kill -9 后 systemd 自愈 2min10s（含 80G 重载），看门狗全程静默 |
| A3 | 对端三态（A 站 STOP → B 站 WARN → 恢复清零） | ✅ | 双向检出：B 站 4 次 "对端 NEX 服务冻结" WARN；A 站对 B 同步检出；恢复后 fail.peer=0 |
| A4 | fallback 降级（stop nemotron → gpt-oss 服务） | ✅ | 停 nemotron 后 `model=nemotron` 请求 200，响应 model 字段=`gpt-oss-120b-MXFP4.gguf`（降级痕迹确证）；A 站零直连调用；恢复后正向请求正常（120s 重载） |
| A5 | cluster.py e2e 双路由回归 | ✅ | 验收前 + 全部故障测试后各跑一轮，均退出码 0（nemotron ✓ / gpt-oss ✓） |
| A6 | rpm 限流（429 或降级，无 5xx） | ✅ | **实际行为与预期不同（已记录进 IMPL v1.1 + 手册）**：非 429 非 fallback，超限请求被网关按 retry-after=60s 延迟重试后 200（隐性背压）；两轮复现（24+16 / 29+11）；无 5xx；llama-server 接收速率被压在 rpm 内。**发现并修复配置缺陷**：默认 simple-shuffle 下 rpm 完全不拦截，需 routing_strategy: usage-based-routing-v2 激活 pre-call 检查 handler |
| A7 | 台账 vs conf 逐字段零偏差 | ✅ | B 站 6 实例 + A 站 1 实例 + nodes.env 声明文件全量比对零偏差；台账 RPC_NODES.env 笔误已修正为 nodes.env |
| A8 | 加载窗口误报防护 | ✅ | decoy 进程（cmdline 含 infer-load）+ kill -STOP 冻结态下手动跑看门狗 2 轮：fail.local 保持 0，无 WARN/ACT（guard 生效） |

### 3.3 回归确认

| # | 检查项 | 状态 |
| - | ----- | ---- |
| R1 | F2 修复不回退：换载仍 ~3min 量级（看门狗不干扰 infer-load） | ✅（间接证据）D1 未触碰 infer-load/infer-unload；A8 已证加载窗口 guard；M1 实测重载 2min10s 看门狗静默 |
| R2 | 两站 station-bin md5 一致性（cluster-watchdog 除 PEER 行外一致） | ✅ 归一化 md5 两站一致：cd444c22...（PEER 行外零差异） |
| R3 | litellm 重启后 master_key/timeout/health_check_interval 原样 | ✅ 部署后 config 实测三字段 + drop_params 原样；/health/liveliness 200 |

## 4. 审查签章

| 轮次 | 日期 | 结论 | 审查者 |
| ---- | ---- | ---- | ----- |
| 1（文档门） | 2026-09-02 | 有条件通过（P1-P3 已修正、P4 已补验，放行实施） | Trae (GLM-5.3) |
| 2（实施后） | 2026-09-02 | **通过**。A1-A8/R1-R3 全过；A6 实际行为偏离预期两分支（429/fallback）但达成风暴隔离目标，隐性背压行为已固化进 IMPL v1.1 + 手册 + 台账；实施中发现并修复 rpm enforcement 依赖 routing_strategy 的配置缺陷（P5 级发现，源码级定位） | Trae (GLM-5.3) |
