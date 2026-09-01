# 调研文档：D1 防挂死与容错补全

***

id: d1-watchdog-fault-RESEARCH
type: design
version: 1.0
status: draft
date: 2026-09-02
depends: \[ADR-0001, infer-load-DESIGN]
upstream: null
--------------

> **Feature**: D1 防挂死与容错补全（health 看门狗 + LiteLLM fallbacks + 参数台账）
> **创建日期**: 2026-09-02
> **状态**: draft
> **Spec 步骤**: Step 1-2
> **决策来源**: [ADR-0001](../../adr/ADR-0001-集群运维框架审计与四项改进决策.md) §决策 4（D1.1-D1.4）

***

## 1. 调研目标

**核心问题**:

1. ADR-0001 D1 三件套（health 看门狗 / 跨模型 fallbacks / 参数台账）的**现状基线**是什么？——现有防护栈哪些模态已覆盖、哪些是真空？
2. 看门狗的**部署位置与处置边界**如何设计？——挂死模态是"系统冻结、进程存活"（E2 根因报告），本机看门狗在冻结时同死，探测者必须在冻结域之外（ADR 替代方案 B 否决理由）
3. LiteLLM 1.98.0 的 **fallbacks / 限流语法与行为**是什么？——特别是：后端完全宕（connection refused）时 fallback 是否触发？请求体跨模型是否透传？上下文长度不匹配时行为？
4. 参数台账的**素材与缺口**：现有 6 实例 conf 的每个参数，哪些有实测依据（可引用 results-ledger），哪些从未调优（须诚实标注）？

## 2. 调研方法

### 2.1 使用的工具

| 工具                          | 用途                   | 查询                                                         |
| --------------------------- | -------------------- | ---------------------------------------------------------- |
| RunCommand (SSH)            | 两站现状取证               | systemd unit 全文、实例 conf 全量、GTT 路径、Beszel DB、LiteLLM 版本与端点  |
| subagent (general\_purpose) | LiteLLM 1.98.0 源码级验证 | PyPI 源码下载直读 router.py/constants.py（fallbacks 触发路径、rpm 支持性） |
| Read                        | 本地文档核对               | ADR-0001、根因报告、results-ledger、cluster.py、station-bin 快照     |

### 2.2 证据等级

- **E1** = 2026-09-02 00:20-00:55 本会话 SSH/本地实测（命令输出节选见 §3）

- **E1'** = LiteLLM 1.98.0 PyPI 源码直接阅读（subagent，非文档转述）

- **E2** = 前会话留档（根因报告 / results-ledger / 手册）

- **E3** = 外部 web 调研，未亲手复现

## 3. 调研发现

### 3.1 现有防护栈全景（E1 + E2）

| 层      | 机制                                                                                                                                       | 覆盖模态                   | 盲区                                              |
| ------ | ---------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- | ----------------------------------------------- |
| 进程级    | `llama-server@.service`: Restart=on-failure, RestartSec=10, StartLimitIntervalSec=0；`rpc-server@.service`: Restart=always                | 进程死亡（crash/被 kill）     | **进程活但服务冻结**（/health 挂）；**系统冻结**（本机 systemd 全停） |
| 内存级    | `load-mem-gate`（MemAvailable≥模型+12G 垫，60s 拒绝）+ `wait-gtt-release`（MemAvailable≥100G 代理）                                                  | 加载前 OOM 预防             | 加载后的运行期泄漏/叠加（无常态监测）                             |
| OOM 加固 | litellm `OOMScoreAdjust=-500` + MemoryHigh=2G/MemoryMax=4G；netconsole-listen `-800`                                                      | global OOM 时关键服务不先死    | ——                                              |
| 主机级    | Beszel 0.18.8：两站 agent + B 站 hub，**8 条告警**（CPU 95%/Temp 85/Disk 90/Status ×两站），**email 通知已配**（user\_settings: <peng.liu.john@gmail.com>） | 主机失联（Status 告警）、CPU 满载 | 服务冻结但主机活（Beszel 无 /health 探测）                   |
| 取证级    | netconsole A→B + softlockup 全核栈（常驻，E2）                                                                                                   | 挂死后遗言捕获                | 只取证不处置                                          |
| 请求级    | LiteLLM 1.98.0: num\_retries=1, cooldown\_time=30, background\_health\_checks=true, health\_check\_interval=300, timeout=600             | 单 deployment 内重试与冷却    | **跨模型 fallbacks 无、rpm/rps 限流无**——后端宕时错误直抛调用方    |

**关键空档确认**（与 ADR-0001 根因 1/2 一致）：服务冻结模态（进程活、/health 挂）零覆盖；主机冻结模态仅有 Beszel Status 邮件兜底（无处置）。

### 3.2 挂死模态 × 检测路径矩阵（设计输入）

根因报告（E2）实证的模态：A 站两次挂死均为 **系统级冻结**（journal 静默、USB4 断链、进程存活）。由此推出看门狗设计公理：

> **探测者不能与被探测者同死。** 系统冻结模态下，本机一切用户态机制（systemd/timer/看门狗脚本）同冻结——唯一有效检测路径是**对端站探测**。

| 故障模态                           | 检测者        | 检测手段                    | 可处置性                                     |
| ------------------------------ | ---------- | ----------------------- | ---------------------------------------- |
| M1 进程死                         | 本机 systemd | Restart 自动拉起            | ✅ 已覆盖（D1 无增量）                            |
| M2 服务冻结（进程活 /health 挂）         | 本机 timer   | curl /health            | ✅ 可 restart / unload                     |
| M3 主机活但 SSH 断（网络故障）            | 对端 timer   | SSH 探测                  | ⚠️ 只能通知                                  |
| M4 系统冻结（A 站两次实锤）               | 对端 timer   | SSH + /health 三态判定      | ❌ 无法远程处置（冻结站收不到任何指令）→ 通知 + netconsole 取证 |
| M5 GTT 异常残留（LM Studio GUI 抢占等） | 本机 timer   | mem\_info\_gtt\_used 水位 | ✅ 可 unload 清场                            |

**既有 ping 型看门狗定位**：`archive/root-scripts/e1_hang_repro.sh` 中的 20s ping×3 是**一次性测试脚本**（判别实验用），非常驻机制。D1.1 是把它升级为常驻 systemd timer + 从"ping 止损"扩展为"health 分级处置"。

### 3.3 GTT 水位查询实证（E1）

- `/sys/kernel/debug/amdgpu/gtt_mem_usage`：**不存在**（实测 NO\_GTT\_FILE）

- `/sys/class/drm/card*/device/mem_info_gtt_used`：**存在**，infer-unload 生产在用（<2,000,000,000 B 判释放，90 次×2s 轮询）——看门狗 GTT 水位探测复用此路径

- wait-gtt-release 用 `MemAvailable≥100G` 做代理（两者不可混用：MemAvailable 含系统缓存，GTT used 是精确值）

### 3.4 LiteLLM 1.98.0 fallbacks / 限流源码级验证（E1'）

subagent 从 PyPI 下载 1.98.0 源码直读（router.py / constants.py / fallback\_event\_handlers.py / exception\_mapping\_utils.py）：

| 问题                                         | 结论                                                                                                                                                       | 依据                                                                        |
| ------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| fallbacks 语法                               | `router_settings.fallbacks: [{nemotron: [gpt-oss]}, {gpt-oss: [nemotron]}]`                                                                              | docs/routing + router.py `async_function_with_fallbacks`                  |
| **后端完全宕（connection refused）是否触发 fallback** | **✅ 触发**——TCP 层失败 → APIConnectionError → 重试耗尽 → 进 fallback 链                                                                                             | router.py `async_function_with_retries` → `async_function_with_fallbacks` |
| 触发 fallback 的错误类型                          | 429/408/401/403/APIConnectionError ✅；400 一般不触发；ContextWindowExceededError 须单独配 `context_window_fallbacks`                                                | `should_retry_this_error()` + `_should_retry()`                           |
| 限流语法                                       | `litellm_params.rpm` / `tpm`；**`rps`** **不存在**（全源码零匹配）                                                                                                   | types\_router.py `LiteLLMParamsTypedDict`                                 |
| 请求体跨模型透传                                   | **原样透传**（messages/max\_tokens/temperature 全部 kwargs 直传 fallback）                                                                                         | fallback\_event\_handlers.py `run_async_fallback`                         |
| ctx 不匹配行为                                  | **无自动截断**——fallback 模型 ctx 装不下时抛 ContextWindowExceededError（llama.cpp 错误串 "exceeds the available context size" 已被识别映射）；配 `context_window_fallbacks` 可再回切 | exception\_mapping\_utils.py `is_error_str_context_window_exceeded`       |
| 环与深度保护                                     | AttemptedFallbackTargets 环检测（内建）；max\_fallbacks 默认 5                                                                                                     | constants.py `ROUTER_MAX_FALLBACKS=5`                                     |
| 重试-fallback 顺序                             | 同 deployment 先耗尽 num\_retries（当前配置=1）→ 才进 fallback 链                                                                                                     | constants.py `DEFAULT_MAX_RETRIES=2`（当前显式设 1）                             |
| 1.98.x 兼容性                                 | 无 fallbacks 相关 breaking change（源码直读确认）                                                                                                                   | 源码                                                                        |

**当前 config.yaml 基线**（E1 cat 全文）：双路由（nemotron→B:8080 / gpt-oss→A:10.10.10.1:8080），master\_key 明文（内网，已知状态），`/health/models` 路由 404（1.98 无此端点；`/health/liveliness` OK）。

### 3.5 Beszel 告警与通知现状（E1，推翻 ADR 待查项）

ADR-0001"中性/需后续行动"节的 Beszel 疑问已补查：

| 事实          | 值                                                                               | 证据                                     |
| ----------- | ------------------------------------------------------------------------------- | -------------------------------------- |
| 部署形态        | **systemd 二进制**（/opt/beszel/beszel serve），非 Docker                              | `systemctl cat beszel-hub`             |
| 版本          | 0.18.8                                                                          | `beszel --version`                     |
| 告警          | 8 条：CPU 95% ×2 站 / Temp 85°C ×2 站 / Disk 90% ×2 站 / **Status ×2 站**（agent 失联告警） | data.db alerts 表（python3 sqlite3 只读查询） |
| 通知          | **email 已配置**（<peng.liu.john@gmail.com>，user\_settings 表）；.notify 目录空（无积压）      | data.db user\_settings                 |
| sqlite3 CLI | 缺失（查询走 python3 stdlib）                                                          | `which sqlite3`                        |

**设计含义**：M4 主机冻结模态的邮件通知链**已存在**（A 站冻结 → A 站 agent 失联 → B 站 hub Status 告警 → email）。D1.1 看门狗的通知职责只需覆盖 Beszel 盲区（M2 服务冻结 / M5 GTT 异常——主机活、agent 活、Beszel 无感）。看门狗 v1 通知 = journal + 状态文件（cluster.py status 可见），邮件复用 Beszel 既有链——**不新建邮件基础设施**。

### 3.6 参数台账素材盘点（E1 + E2）

B 站 `/etc/llama-instances/` 实测 **7 个文件 = 6 实例 conf + 1 节点清单**（`RPC_NODES.env` 是 cluster-bench 的 RPC 节点声明，非实例——ADR"6 实例"表述精确化）。逐实例参数与依据映射：

| 实例                                | CTX    | THREADS | N\_CPU\_MOE | RPC\_TARGET      | 实测依据（results-ledger）                                                    |
| --------------------------------- | ------ | ------- | ----------- | ---------------- | ----------------------------------------------------------------------- |
| nvidia-nemotron-3-super-120b-a12b | 131072 | 16      | 8           | （空，单机）           | ✅ CTX: KV 仅 1G\@128k 可常开；17.3→20.3 t/s（RPC→单机 +17%）；24k/96.5k needle 全过 |
| gpt-oss-120b                      | 32768  | 16      | **0**       | （空，单机 A 站）       | ⚠️ N\_CPU\_MOE=0 **无台账依据**；CTX 32k 无对比实测                                |
| qwen3.8-flash-next                | 262144 | 16      | 8           | auto             | ✅ tg 15.7 t/s 冒烟（262k 未单独压测，原生 1M 上限内）                                  |
| glm-5.3-flash                     | 32768  | 16      | 8           | 10.10.10.1:50052 | ❌ 模板默认，无实测                                                              |
| deepseek-v4-flash-0731            | 32768  | 16      | 8           | 10.10.10.1:50052 | ⚠️ tg \~6.3 t/s 标称有录；参数未调                                               |
| gpt-oss-120b-fable-5-distilled    | 32768  | 16      | 8           | auto             | ❌ 模板默认，无实测                                                              |

**已知反例**（须进台账"试过的反例"区）：

1. gpt-oss + ngram-simple 投机解码：25.2/22.6/24.8 t/s vs 裸 AR 50.3 t/s——**负收益 \~52%**（思考型输出低 n-gram 重复，命中率低而验证开销照付）
2. nemotron RPC 双机 vs 单机：decode -17.3%（80G 单机可容，RPC 是税不是必需）
3. m27-q4ks thinking 输出失控（3 次采样策略也救不了 A3/C2 题）——模型分型教训

**结构性缺口**（台账价值所在）：THREADS=16 全统一、batch/ubatch 走默认——**从未做过扫描调优**，台账须诚实标注"默认值，无实测依据"而非事后编造理由。

### 3.7 调研副产物与新发现

1. **`.litellm-research/`** **目录**：subagent 源码验证时下载的 LiteLLM 1.98.0 源码（\~数十 MB，未跟踪）。处置：实施验收后删除（fallbacks 行为已固化进本文档，源码无留存价值）
2. **ops/station-bin/README.md 纯格式 diff**：与 D4 同款（外部工具触碰的表格重排），无内容变更——顺手提交即可
3. **LiteLLM config.yaml 的 master\_key 明文**：生产配置在 B 站 `~/litellm/config.yaml`（主控站 secrets/ 有正本）。key 残留治理是 D4 已关事项，本次 config 改动**只动 router\_settings 块，不复制 key 到任何文档**（本 RESEARCH 已按此原则节选）
4. **A 站 conf 仅 1 个**（gpt-oss-120b.env）——A 站是"薄站"（rpc-server + 单实例），看门狗 A 站部署比 B 站简单

## 4. 综合分析

### 4.1 关键发现总结

1. 防护栈四层（进程/内存/OOM/主机监控）中，**M2 服务冻结与 M5 GTT 常态监测是真空**；M4 系统冻结有 Beszel Status 邮件兜底但无快速检测（周期未知）\[置信度: ★★★★★ E1+E2]
2. 看门狗设计公理成立：**冻结域之外探测是 M4 唯一检测路径**——两站互探（B 探 A 为主，A 探 B 为辅）是必然架构 \[置信度: ★★★★★ E2 根因报告 F6/F7 + ADR 替代方案 B 否决理由]
3. LiteLLM 1.98.0 fallbacks 对 connection-refused 完全可用、请求体原样透传、ctx 不匹配无截断——**ADR 已声明的"长上下文截断局限"精确化为：nemotron(128k conf)→gpt-oss(32k conf) 时超 32k 的请求 fallback 后 400 报错而非截断**（源码级实锤）\[置信度: ★★★★★ E1']
4. `rpm` 可用、`rps` 不存在——限流只能按分钟粒度 \[置信度: ★★★★★ E1']
5. Beszel 0.18.8 已有 8 告警 + email 通道；M4 的通知链已存在，看门狗不重建邮件设施 \[置信度: ★★★★★ E1]
6. 参数台账素材：2/6 实例有实测依据，4/6 为模板默认——台账的核心价值是**把"不知道"显式化** \[置信度: ★★★★★ E1+E2]

### 4.2 设计输入（对实施文档）

1. **看门狗形态**：两站各一 `cluster-watchdog.service` + `.timer`（60s）；脚本探测三态——本机 active 实例 /health、本机 GTT 水位、对端 SSH+/health。**零自加载原则兼容**：无 active 实例时跳过 /health 探测（不误报"未加载"为故障）
2. **分级处置**：连续 3 次失败 = WARN（journal）；连续 5 次 = 处置——本机模态 restart 对应实例（M2）/ 高 GTT 残留提示（M5）；对端模态只通知（M3/M4 无远程处置能力）。通知 = journal + `/var/log/cluster-watchdog.log` + 状态文件（cluster.py status 增强可读）
3. **fallbacks**：`router_settings.fallbacks` 双向互备 + `litellm_params.rpm`（数值实施时定）；不动 master\_key、不动既有 retry/cooldown 语义
4. **台账落位**：`spec/infer-load/params-ledger.md`，三区结构（当前值+依据 / 反例 / 缺口显式化），引用 results-ledger 具体节
5. **边界**：不做 WatchdogSec（ADR 已否决）、不重建邮件（Beszel 已有）、不做 rpm 之外的限流（rps 不存在）

### 4.3 风险与开放问题

| #  | 风险/问题                                                        | 处置                                                                                         |
| -- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------ |
| R1 | 看门狗误报触发不必要的 restart（如加载期 /health 503——手册已录"Loading 期 503"陷阱） | 探测用 `curl -sf` + 只对 `systemctl is-active` 为 active 的实例探测 + N 次确认；加载窗口（load-mem-gate 运行中）跳过 |
| R2 | A 站 SSH 探测 B 站用 mDNS 名（实测单次可达 10.2s 慢）                       | 对端探测超时放宽至 15s；timer 间隔 60s 下可容忍                                                            |
| R3 | fallback 掩盖一端故障（ADR 后果节已声明）                                  | e2e 冒烟 + cluster.py status 人工可见；验收项含"fallback 触发后 status 仍能看出后端 DOWN"                      |
| R4 | 看门狗 timer 自身的可靠性（systemd timer 漂移/堆积）                        | OnUnitActiveSec + 单次 oneshot 执行 <10s，无堆积风险；验收含 timer 连续运行观察                                |
| R5 | Beszel Status 告警周期未知（M4 邮件延迟不可控）                             | 不阻塞 D1（netconsole 取证 + 人工断电是 M4 的既定处置）；看门狗日志是补充                                            |

