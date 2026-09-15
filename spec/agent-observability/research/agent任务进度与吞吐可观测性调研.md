# agent 任务进度与吞吐可观测性 —— 集成进「统一管理入口」调研

> **日期**: 2026-09-15
> **触发**: 用户回溯问「之前写的模型吞吐状态 + agent 工作进程进度监测，是否已集成到统一管理入口」→ 查证结论是**没有**，于是先做选型调研
> **证据等级**: E1=本轮实测 / E2=前轮实测留档 / E3=外部文档与社区项目 / E4=推断
> **关联**: `spec/d6-agent-standard/OPEN-ISSUES.md` O-25（进度可观测性，2026-09-12 已收口）· `spec/rpc-optimization/` P2-3 reqlog · `docs/2026-09-15_统一管理入口_深入分析与优化方案_v2.md`（本文是其后续输入）
> **结论**: 现有资产**完好但没进统一入口**，且它的形态（file:// 快照）在入口里**必然过期**（实测已陈旧 3 天）。社区同构需求的标准答案是 **trace/span + DB 栈**，与本集群「零外部依赖 / 按需服务 / 无常驻 / 无 DB」直接冲突 → **引语义、不引栈**。集成应做成 CLI + web 两小件，判据核心是**口径分列**与**陈旧度自显**。

---

## 0. 结论摘要

| # | 问题 | 调查结论 | 严重度 |
|---|---|---|---|
| Q1 | 吞吐 + agent 进度的监测**是否已在统一入口**？ | **否**（E1）。全部消费方只有 `agent-cli.ps1` / `make-dashboard.ps1` / 其产物 `dashboard.html`；`cluster.py` 与 `cluster_web.py` 对这些关键词**零命中** | 中 |
| Q2 | 现有资产还能用吗？ | **能，但形态有结构性缺陷**（E1+E2）：`dashboard.html` 是**生成时刻的内联快照**，刷新 = 手动重跑生成器 → 实测已停在 2026-09-12 12:18，而 ledger 最后一条是 09-14 13:12，**看板落后 3 天且不自我暴露** | 高（会主动误导） |
| Q3 | 社区标准做法能否直接复用？ | **不能整栈引，但语义全部可借**（E3）：OTel GenAI 语义约定（`invoke_agent` / `execute_tool` / `gen_ai.client.token.usage`）、A2A 任务状态机（submitted→working→…→completed/failed）、AG-UI 事件模型（`RUN_STARTED` / `TEXT_MESSAGE_CONTENT` / `TOOL_CALL_*`） | — |
| Q4 | 采集侧选 textfile 还是 Pushgateway？ | **两者都不引，但记住结论**（E3）：Prometheus 官方明确「Pushgateway 只推荐 service-level batch job」，**与机器/站绑定的批作业用 node_exporter textfile**。我们的 run 正是"绑定到某站某引擎"的批作业 → 落账进本地 JSONL 才是同构做法 | — |
| Q5 | 最大的技术陷阱是什么？ | **三种 t/s 口径不可比**（E2 实测）：API timings 67.6 / 引擎耗时口径 68.1 / agent 产出字节墙钟 32.0 —— 同屏并列而不标口径，等于把"基准对比铁律"踩一遍；且字节→token 换算有**信号天花板**（O-25 已判定不打荒数字） | 高 |
| Q6 | 最小可行集成是什么？ | **CLI 一行 + web 一卡**（P0/P1），把三口径**分列并标注**、ETA 无动态值就打 `NA`、并把**陈旧度做成一等字段**。SSE/DB/trace 栈列入"触发条件式不做" | — |

---

## 1. 现状回溯（E1：本轮实测，逐条可复现）

### 1.1 既有资产清单（都很完整，这点先说清楚）

| 资产 | 位置 | 提供什么 |
|---|---|---|
| 派发前预估 | `agent-cli.ps1` `$TpBench` + `Get-ThroughputEstimate` | route id → prefill/decode t/s 基准，分相估算秒数，**HIT 才打印**（MISS 不打荒数字） |
| 派发中节拍 | 远端 `$W/out/.progress`（每 5s 追加 `t=<st> bytes=<ob> bytes_s=<bps>`，teardown 写 `t=end`） | 已产出字节 / 瞬时 bytes_s / 墙钟 → 实时 t/s + ETA |
| 运行台账 | 主控 `ops/station-bin/agent-runs.log` + `D:\Paper\agent-out\<ts>\.agent-run.json` | `ts,proj,id,sens,code,queue_s,run_s` + profile/slot/accept/output_bps/model/status |
| 吞吐基准表 | `spec/d6-agent-standard/THROUGHPUT-BASELINE.md` | 现役各档 decode 锚（gpt-oss 49-53 / nemotron 20.5-23.2 / M2.7 21.5-22.1 / V4-flash 7.9 / Qwen3.8 19-20） |
| 看板 | `make-dashboard.ps1` → `dashboard.html` | tab1 已完成总览（三态着色 + run.json 展开）· tab2 正在跑（`-Live` 时 scp 拉 `.progress`） |

> O-25 判据①-④ 全部闭环、P3（ETA 精度/自动刷新）2026-09-12 **明确收口不实施**（E2）——所以"快照非实时"是当时的**有意边界**，不是漏做。

### 1.2 统一入口现状（`cluster.py` + `cluster_web.py`）

web 现有区块：三站模型清单/加载卸载 · 框架状态(llama/unsloth/vLLM/litellm/opencode/claude) · 三平面(凭据/provider/出站) · 引擎版本矩阵 · 引擎请求/token 统计(reqlog) · 空闲 TTL。
CLI 现有子命令：`status` `load` `frames` `unload` `e2e` `secrets` `providers` `egress` `estimate` `models` `versions` `flow` `reqlog` `ttl` `web`。

**无 agent 区块、无 agent 子命令**。逐条取证（E1）：

- `grep -rn 'dashboard|agent-runs|\.progress|THROUGHPUT-BASELINE|Get-ThroughputEstimate' ops/` → 命中仅 `agent-cli.ps1` / `_agent-cli-bom.ps1` / `make-dashboard.ps1` / `dashboard.html`；**`cluster.py`、`cluster_web.py` 零命中**。
- `dashboard.html` 内联 `"generated":"2026-09-12 12:18:48"`、completed 行 **21** 条；`agent-runs.log` 最后一条 `202609141312071820`（09-14 13:12）→ **看板落后 3 天**。
- 两条通路形态不同：`dashboard.html` 是 **file:// 静态快照**；统一入口是 **http 按需服务 + token 鉴权**。前者无法承载"正在跑"，后者天然可以。

### 1.3 缺口定性

| 缺口 | 性质 | 影响 |
|---|---|---|
| G1 无 agent 区块 | 覆盖缺口 | 想知道"agent 在跑什么/跑到哪"必须离开统一入口、且**先手动跑生成器** |
| G2 快照会过期且不自我暴露 | **判据缺口**（最要命） | 一个显示 3 天前状态的看板，比没有看板更危险 —— 它"自信地撒谎" |
| G3 三条 t/s 口径并存但未分列 | 口径缺口 | 见 §3.1；一旦混用即违反"基准对比铁律"，且错误会静默进台账 |
| G4 运行中数据随 run 消失 | 数据生命周期缺口 | `.progress` 只在跑的时候存在；历史进度未落账（只回填了 `output_bytes/output_bps`） |

---

## 2. 社区层析：三层栈 + 2026 的三个新标准

### 2.1 三层栈（我们历年调研的同一结论，O-25 里已定过性）

| 层 | 代表 | 提供 | 与本集群的关系 |
|---|---|---|---|
| 引擎层 | llama.cpp `/metrics`(Prometheus) + `/slots`；vLLM `/metrics` | prefill/decode t/s、槽位占用、队列、KV | **已在用**（P2-3 reqlog + P1-1 槽位门） |
| 代理/网关层 | llama-swap、LiteLLM | 模型路由、TTL、聚合指标 | 需求已被 `infer-load` + 本入口覆盖；llama-swap 仅作 C 站容量档备选 |
| 任务编排层 | Langfuse / Phoenix / LangSmith / Datadog LLM Obs | trace·span 树、token、延迟、成本、评测 | **我们缺的就是这层**，但社区实现与我们的约束冲突（见 §2.2） |

### 2.2 编排层四家的自托管成本（E3，2026-09 核）

| 项目 | 许可 | 自托管形态 | 对本集群的判定 |
|---|---|---|---|
| Langfuse | MIT | **ClickHouse + Postgres + Redis + blob storage**（生产形态；Docker Compose 单机可起） | 为"看几条 agent 进度"引入四件套 + 常驻服务 → **不引** |
| Arize Phoenix | ELv2（source-available，非 OSI 开源） | 单容器 SQLite（Postgres 可换） | 成本最低的 trace 栈，但仍是常驻容器 + 非开源许可 → **不引**（保留为将来"要做 eval"时的候选） |
| LangSmith | 专有 | 自托管**仅企业版** | 直接排除 |
| Datadog LLM Obs | 专有 SaaS | 无 | 与数据主权冲突，排除 |

**要点**：社区这层的计价单位是 **trace / span**，架构前提是**常驻接收端 + 数据库**。本集群的既定边界是「按需服务、用完即停、不引时序库/DB」（方案 v2 §5.4），两者不可调和 —— 所以正确动作是**借语义不借栈**。

### 2.3 借什么语义（三套标准，映射成本≈0）

**(a) OpenTelemetry GenAI 语义约定**（仍在 Development 阶段，需锁版本；E3）

| 社区约定 | 形状 | 我们已有的对应物 |
|---|---|---|
| `invoke_agent` span / `gen_ai.invoke_agent.duration` | 一次完整 agent 调用 | 一条 `.agent-run.json`（run 起止） |
| `execute_tool {tool_name}` span | 单次工具调用耗时/成败 | 目前**无**（opencode 无头 run 不吐 usage/工具事件）→ 记为空缺 |
| `gen_ai.client.token.usage`（histogram）/ `gen_ai.usage.input_tokens`·`output_tokens` | 计费 token | **拿不到**（见 §3.2 天花板）→ 我们只能给字节 |
| `gen_ai.conversation.id` | 会话/线程关联 | `proj` + ledger `ts` |
| `gen_ai.agent.name/id/version` | agent 标识 | `proj` + 模型路由 id |
| gen_ai.client.operation.duration | 模型调用延迟 | `.progress` 的墙钟 + `.agent-run.json` 的 `run_s` |

**(b) A2A 任务状态机**（2026 已入 Linux Foundation，v0.3；E3）：`submitted → working → input-required → completed / canceled / failed / unknown`。
我们的 ledger 是 `code`(exit) + `status`(completed/timeout/failed) **两态** —— 与 A2A 对齐后**多出一个 `working`**，正好就是我们缺的"正在跑"这一档；`input-required` 我们无此语义（无头 run），**明确留空**而不硬套。

**(c) AG-UI 事件模型**（SSE，事件名固定；E3）：`RUN_STARTED` / `TEXT_MESSAGE_START|CONTENT|END` / `TOOL_CALL_START|ARGS|RESULT|END` / `STATE_SNAPSHOT|DELTA` / `RUN_FINISHED|ERROR`。
它是"agent→UI"的事件契约 —— 我们**现在用不上**（`opencode` 无头不吐事件），但**P2 若做流式**，事件名照抄即可，不必自创协议。

### 2.4 采集侧：textfile vs Pushgateway（E3，Prometheus 官方立场）

- **Pushgateway**：官方原话「只推荐在**有限**场景使用」「通常唯一有效用例是捕获 **service-level batch job** 的结果」，并明确两条坑：① **永不遗忘**（陈旧指标会一直以"看似健康"的样子被采集，除非手工删）；② 失去 `up` 健康语义。社区文章的直接结论是「**按 freshness 告警，而不是按原始值** —— 因为原始值可能是幽灵」。
- **node_exporter textfile collector**：官方对"与机器相关的批作业"（如 cron 安全更新）**指定**用 textfile：脚本把指标写进目录里的 `*.prom`，exporter 扫目录合并进 `/metrics`。两条硬约束：**不支持时间戳**（要表达"何时采集"必须自己写一个 metric）、需**原子写**（tmp + mv）。

**对我们的意义（这是本次调研最实用的一条）**：我们的 agent run 是**绑定到某站某引擎**的批作业 → 官方指引指向 textfile ≠ Pushgateway。而我们已经有一个**同构且更简单**的载体：站上 `reqlog.jsonl`（采样 + 差分 + 落账）。所以**采集侧不动**，只补"消费侧"。

> ⚠ 而 Pushgateway 那条"陈旧指标会自信地撒谎"的教训，**我们已经在自己身上复现了**：`dashboard.html` 停在 3 天前、界面上没有任何"这是旧的"标记（§1.2 E1）。社区结论反过来印证了 G2 必须修。

### 2.5 社区可直接借的 5 条 / 明确不引的 4 条

**借**（成本≈0）：
1. **freshness 是一等字段**：任何快照/看板必须带采集时刻 + 距今时长，过期即变色（源自 Pushgateway 教训）。
2. **口径写进列名**：同一屏出现多个 t/s 时，列头必须写明"引擎耗时口径 / 墙钟口径 / API timings"。
3. **span 命名照 OTel GenAI**：`invoke_agent` / `execute_tool` / `gen_ai.client.token.usage`，将来接任何 trace 后端不用改数据模型。
4. **状态机照 A2A**：把我们缺失的 `working` 补上，与"正在跑"一一对应。
5. **批作业指标落本地文本、不推远端缓存**（官方 textfile 路线），与现有 JSONL 同构。

**不引**（并记录触发条件，避免反复讨论）：
1. Langfuse/Phoenix/LangSmith/Datadog —— 触发条件 = "需要 trace 树 + 评测闭环 + 多用户"，当前无。
2. OTLP/Collector 常驻接收端 —— 触发条件 = 出现第二个消费方且需要跨机聚合。
3. Pushgateway —— 语义上就不该用于"与机器绑定的批作业"。
4. Prometheus + Grafana 时序栈 —— 方案 v2 §5.4 已排除；Beszel 已在承担节点监控。

---

## 3. 关键口径与判据问题（本文重点，也是集成时的雷区）

### 3.1 三种 t/s 互不可比（E2：P2-3 实测三口径同刻对照）

| 口径 | 定义 | 同刻实测（同一请求） | 用途 |
|---|---|---|---|
| API timings | 响应体 `timings.predicted_per_second` | **67.6 t/s** | 单次请求的"引擎侧真实"值 |
| 引擎耗时口径 | `ΣΔtoken / ΣΔ引擎耗时`（reqlog 主口径） | **68.1 t/s**（差 <1%） | 区间聚合，与 API timings 可比 |
| 墙钟口径 | `ΣΔtoken / ΣΔ采样间隔` | **32.0 t/s**（忙占比 0.47） | 只反映"这段时间引擎多忙"，**含空闲会被稀释** |
| agent 产出字节/墙钟 | `.progress` 的 `bytes_s` | — | **第四种**：分子是产出文件字节，不是 token |

⇒ 集成时**绝不能**把它们放进同一列或算同一个"平均吞吐"。四者中前两个可比、后两个各自独立。

### 3.2 字节 → token 的换算天花板（E2：O-25 已定论，不重复踩）

`opencode` 无头 run **不打印 usage**，wrapper 只能测**产出文件字节**。中文 ≈1.5-2 B/token、英文 ≈4 B/token → 换算系数不可信。O-25 的处置是「MISS 不打荒数字」。
⇒ 集成里 agent 侧的 t/s **只能标注为"字节口径（非 token）"**，或直接显示 `bytes/s` 而不假装是 token 速率。**ETA 同理**：无动态 `bytes_s` 且无基准档 → 打 `ETA NA`。

### 3.3 "运行中"信号的存在性（E2：代码事实）

`.progress` **只在任务运行期存在**（远端 `$W/out/.progress`），teardown 写 `t=end` 终值。含义：
- "正在跑"的判据 = 能读到 `.progress` 且**最后一行不是 `t=end`**；读到 `t=end` 而 ledger 尚无该 ts = **刚结束/收尾中**（这是个中间态，别当成 running）。
- 要**历史进度**必须在 run 结束时把终值落账（现在只回填 `output_bytes/output_bps`）——若要曲线，得新增一行/一列。

### 3.4 陈旧度（freshness）判据

数据源有三种时效性，**必须分别标注**：

| 源 | 时效 | 判据 |
|---|---|---|
| 站上 `.progress` | 秒级（5s 采样），仅运行期 | 距今 > 60s 未更新 ⇒ 疑似卡死（O-25 的"卡死黑盒"正是它） |
| ledger `agent-runs.log` | 事件级（run 结束才写） | 最后一条的 ts 与"最近一次派发"对照 |
| 看板/快照 | 人工重跑才更新 | **必须带 `generated` + 距今**，超阈值显式标"本页已陈旧 N 天"（当前 3 天，无标记） |

---

## 4. 建议方案（不作实现，只给形态与判据）

### 4.1 形态：CLI 一行 + web 一卡（P0/P1）

| 步 | 交付 | 内容 | 默认 |
|---|---|---|---|
| P0 | `cluster.py agent {runs\|live\|tail}` | `runs`=读 ledger 尾 N 条（含 status/queue_s/run_s/output_bps）；`live`=扫三站 `~/agent-workspaces/*/out/.progress`（ssh，复用 `-Live` 的 scp/正则）→ 站/模型/已跑/bytes_s/**ETA**；`tail`=原始行 | 只读，默认执行 |
| P1 | web `GET /api/agent` + 卡片「Agent 任务（进行中 / 已完成）」 | 两栏：进行中（含"距上次节拍 Ns"）+ 已完成（ledger 尾 N 条，三态着色） | 只读，随页轮询 |
| P2（可选） | SSE 事件流 | 借 AG-UI 事件名（`RUN_STARTED`/`STATE_DELTA`/`RUN_FINISHED`）推送进行中状态 | **默认不做**，见触发条件 |

**统一入口的既有约定照抄**：只读默认执行、改状态才要 `--go`（本项目 P2-1 已立的规矩）；`/api/agent` 必须带 token 鉴权（P2-5 刚验过的新端点鉴权纪律）。

### 4.2 展示纪律（判据级要求，不是"最好有"）

1. **口径分列**：`引擎耗时口径 t/s`（来自 reqlog，可比 API timings）与 `agent 字节口径 B/s`（`.progress`）**分列**，列头写明口径。
2. **ETA 只在有动态值时给**；否则 `ETA NA`（no-bench 纪律）。
3. **freshness 自显**：`进行中` 行显示"距上次节拍 Ns"；`已完成` 行显示 ledger 最后写入时刻距今天数。
4. **不引入新采集器**：复用 `.progress` + ledger + reqlog（P2-1 的教训：同类逻辑两份实现必然漂移）。
5. **字段命名对齐 OTel/A2A**（§2.3 映射表），避免将来迁移时改一遍。

### 4.3 明确不做（附触发条件）

| 不做 | 触发条件（满足再做） |
|---|---|
| trace/span 栈（Langfuse/Phoenix/…） | 需要"看单次 run 内部工具调用树"或"跑评测闭环"时 |
| OTLP Collector / 时序库 | 出现第二个独立消费方 + 需要跨机长期留存 |
| 常驻采样服务 | 需要"分钟级连续曲线"，且证明按需采样不够时（方案 v2 §5.4 边界） |
| 自动刷新 `dashboard.html` | 若 P1 落地则**该快照可退休**（或降级为导出用） |
| 字节→token 换算 | 上游开始吐 usage（`opencode` 无头支持）之前，**不做** |

---

## 5. 落地判据（可自证，供 P0/P1 验收）

| # | 判据 | 证据形态 | 负向用例（必须能抓到） |
|---|---|---|---|
| V1 | `agent live` 能识别"正在跑"与"已结束" | 造一个 `t=..` 的 `.progress` → 判 running；改成 `t=end` → 判 finished | `t=end` 误判为 running ⇒ FAIL |
| V2 | freshness 自显 | 卡片显示"距上次节拍 Ns"；ledger 过期显示"N 天前" | 快照超阈值不标 ⇒ FAIL |
| V3 | 口径分列 | 同屏两列，列头含"引擎耗时口径"/"字节口径" | 混成一列或算平均 ⇒ FAIL |
| V4 | ETA 不编 | 无 `bytes_s` 且无基准 → `ETA NA` | 出现无出处数字 ⇒ FAIL |
| V5 | 新端点鉴权 | 无 token → 401（P2-5 已验证同款） | 漏鉴权 ⇒ FAIL |
| V6 | 空态不假绿 | 三站无 `.progress` + ledger 为空 → 明确"无任务在跑" | 空白页/报错 ⇒ FAIL |
| V7 | 不新增采集器 | `git diff` 无站上新脚本；web 只读站上既有文件 | 引入第二个采样实现 ⇒ FAIL |

---

## 6. 风险

| 风险 | 说明 | 缓解 |
|---|---|---|
| 又造一个"会过期的看板" | 若 P1 只做静态快照，复现 G2 | web 端点**每次请求现算**（按需服务天然如此），不做内联快照 |
| 口径漂移 | 有人把 agent 的 B/s 当 t/s 用 | 列头写口径 + 文档 §3.1 入手册 |
| `.progress` 被覆盖 | 同名目录复用/并发派发 → live 行互相污染 | 显示 proj + 远端 mtime；无法区分就标"来源不唯一" |
| 站不可达时的静默 | ssh 失败会让"进行中"栏空着，看着像"没在跑" | 站不可达必须显式标（照 reqlog/ttl 的"未部署/不可达"处理） |
| OTel 约定仍在 Development | 名称可能变（semconv-genai 独立仓） | 只在**我们自己的字段注释**里写映射，不硬编码到外部依赖 |

---

## 7. 调研来源

- OpenTelemetry GenAI 语义约定（注册表，已迁往独立仓）: [Gen AI attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/) · [semantic-conventions-genai](https://github.com/open-telemetry/semantic-conventions-genai)
- OTel 在 agent 上的落地写法与信号表（spans/metrics/token/latency）: [OpenTelemetry for AI Agents](https://digitalthoughtdisruption.com/2026/07/20/opentelemetry-ai-agent-observability/) · [Azure App Service 多 agent 监控教程](https://learn.microsoft.com/en-us/azure/app-service/tutorial-ai-agent-monitoring-dotnet) · [AWS AgentCore Observability（本地/多云 agent）](https://aws.amazon.com/blogs/machine-learning/monitor-on-premises-and-multi-cloud-ai-agents-with-agentcore-observability/)
- Agent 观测平台横评与自托管成本: [Top 5 Agent Observability Tools 2026](https://www.mlflow.org/top-5-agent-observability-tools) · [Langfuse vs Arize Phoenix/AX](https://langfuse.com/resources/engineering/best-phoenix-arize-alternatives) · [Datadog vs Langfuse vs LangSmith vs Phoenix](https://dreaming.press/posts/langfuse-vs-langsmith-vs-phoenix-observability.html) · [AI 应用可观测性平台工程 2026](https://blog.lonae.com/posts/ai-2026-NIlCoI)
- AG-UI（agent→UI 事件协议，SSE）: [AG-UI 协议介绍](https://docs.ag-ui.com/introduction) · [AG2 的 AG-UI 接入与事件清单](https://docs.ag2.ai/latest/docs/user-guide/ag-ui/) · [AWS AgentCore 的 AG-UI 协议契约](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-agui-protocol-contract.html)
- A2A 任务状态机与流式订阅: [A2A 规范（TaskState/SubscribeToTask）](https://a2a-protocol.org/latest/definitions/) · [Task 概念与生命周期](https://agent2agent.info/docs/concepts/task/) · [A2A 综述（LF 治理、v0.3）](https://stacka2a.dev/learn/what-is-a2a)
- 批作业指标采集的两条社区路线: [When to use the Pushgateway（官方）](https://prometheus.io/docs/practices/pushing/) · [node_exporter textfile collector（官方包文档，含"不支持时间戳"）](https://pkg.go.dev/github.com/prometheus/node_exporter) · [Pushgateway 的陈旧指标陷阱](https://devopsaitoolkit.com/blog/prometheus-pushgateway-when-to-use-it-and-when-not-to/) · [textfile 原子写与新鲜度实践](https://fastfox.pro/blog/tutorials/node-exporter-textfile-bash-python/)
- 引擎侧（既有结论复用）: llama.cpp `/metrics` 与 `/slots` —— 见 `docs/2026-09-15_统一管理入口_深入分析与优化方案_v2.md` §A.1.1 与本仓 P2-3 实测

---

## 8. 落地记录与下一步

### P0 已落地（2026-09-15，本次）

`ops/cluster.py agent {runs|live|tail} [--limit N] [--station X] [--json]`（只读，无副作用）。

| 判据 | 结果 |
|---|---|
| V1 `.progress` 三态 | ✓ 真数据 4 条全是 `t=end` → 判 `finished`；造 `t=12 …` → 判 `working`；**终值残留不会被当在跑** |
| V2 新鲜度自显 | ✓ `live` 给"距上次节拍"（造 mtime -5min → 行内标 `⚠陈旧`）；`runs` 给"最新一条距今 32.2 小时" |
| V4 ETA 不编 | ✓ 运行中无目标量 → 一律 `NA (无 max_output 目标)` |
| V6 空态不假绿 | ✓ 无 `.progress` → "三站均无 … 没有任务在跑"；站不可达显式打印不可达 |
| V7 不新增采集器 | ✓ 只读三处既有文件（台账 / run.json / .progress）；projRoot 从 `agent-cli.ps1` 现取，未另抄 |

负向验证 **10/10**（`tmp/_verify_agent_p0.py`：T1 working / T2 陈旧标记 / T3 `t=end`⇒finished / T4 无文件⇒无行 / T5 空文件⇒跳过且 rc=0；用一次性假工作区 `_aoprobe`，测完即删）。门禁全量 12 项 11 绿 / 1 黄 / 0 红。

**过程中修正的三个真实细节**（都是实测才发现）：
1. 台账 `queue_s/run_s` 列**实测恒 0** → 真实耗时必须 join `run.json`（本命令的 `run_s` 列即来自详情）。
2. 台账**不是严格有序的**（09-12 有一对 `17:18:20 / 17:18:18` 反序，并发派发所致）→ 显示前按 ts 排序；新鲜度取 `max(ts)` 而非"最后一行"。
3. 顺带确认：`run.json` 的 `usage.total_tokens` **恒 0** —— §3.2 的"字节→token 天花板"再获一次实证。

### P1 已落地（2026-09-15，本次）

web 卡片「Agent 任务（进行中 / 已完成）」+ `GET /api/agent`（token 鉴权，随页 15s 轮询）。取数与 CLI **共用 `cluster.agent_runs()/agent_live()/agent_ledger_freshness()`** —— 单一定义点，页面不做第二次 join。

| 判据 | 结果 |
|---|---|
| V3 口径分列 | ✓ 两端表头均标「字节口径」共 4 处，并声明"**不是 token**"、与 reqlog 引擎耗时口径"**互不可比**"（渲染结果里实测存在，不只是代码里有） |
| V2 新鲜度自显 | ✓ 运行中行给"距上次节拍"（陈旧标红 + 上行汇总"⚠陈旧(疑似卡死)"）；台账行给"最新一条 09-14 13:12（距今 1.3d）" |
| V4 ETA 不编 | ✓ 后端**不提供** eta 字段，前端固定渲染 `NA` + 原因（实测断言：4 行 live 均无 eta key） |
| V5 新端点鉴权 | ✓ 无 token → 401 |
| V6 空态不假绿 | ✓ 无 `.progress` 时渲染"没有任务在跑"；站不可达单独一行显示原因 |
| V1 两态 | ✓ `working` 徽章**只**在后端 `running=true` 时出现（真数据 0 条在跑 → 不出现；合成载荷 1 条在跑 → 出现） |

验证三层（**光有 "页面含 loadAgent 字样" 不算验证**）：
1. API/静态 **17/17**（`tmp/_verify_agent_web.py`：鉴权、页面含卡片、结构与判据字段、排序、空态）
2. **渲染路径** —— 把页面 JS 抽出来在 node 里用**真实载荷**跑一遍 `loadAgent()`，断言产出的 HTML 里**确实**有口径声明/新鲜度/两态：真数据 **13/13**、合成"在跑" **17/17**、合成"陈旧" **17/17**（`tmp/_verify_agent_render.js`）
3. `node --check` 内联 JS 语法 ✓（588 行）

**过程中踩的三个坑（都是验证工具自身，记录以免复发）**：
1. `eval(src)` 拿不到函数声明的作用域 → 改 `new Function(src + '; return {...}')`；
2. 包裹体里脚本末尾的 `refreshAll()` 会先占住 `agentBusy`，再调用被 `if(agentBusy) return` 弹回，而真渲染的 promise 还没 settle 就被 `process.exit` 掐掉 → **先剥掉末尾 `refreshAll();`**（这是"渲染 0 字符"的真因）；
3. 断言里"两态文案必存在"对**合成载荷**不成立（只造了在跑行）→ 断言改为按载荷分支判断。

**`dashboard.html` 的处置**：**保留为离线导出，不再手动刷新**（手册已注明）。P1 落地后它的 G1/G2 缺口由本页承担；要不要删文件由用户裁决 —— 本次不删（它在 O-25 是已收口的交付物）。

### 仍未做（按顺序）

| 序 | 项 | 说明 |
|---|---|---|
| P2 | SSE 事件流（借 AG-UI 事件名） | **默认不做**：与"按需服务、非实时"边界冲突，仅当"要盯着长卡跑"成为常态时再议 |
| — | `dashboard.html` 删除 | 可选项；当前以"手册标注已被取代"替代 |

> 两条纪律不变：**口径分列** + **freshness 自显**。P0/P1 都做到了 —— 这是这两步真正区别于"又一个看板"的地方。
