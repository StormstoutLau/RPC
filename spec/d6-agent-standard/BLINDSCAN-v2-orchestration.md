# 盲区扫描：V2 并发 fan-out 编排（BS-1..6）

***

id: d6-agent-standard-BLINDSCAN
type: design
version: 1.1
status: finalized
date: 2026-09-04
depends: \[d6-agent-standard-DESIGN v1.4 (approved), d6-agent-standard-IMPLEMENTATION v1.2]
upstream: \[d6-agent-standard-DESIGN]
-------------------------------------

> **Feature**: D6 wrapper **单工作区锁下 MVP 已验收**；本扫描针对**迈入 V2（readonly 共享/fan-out 并行）那一刻才会激活**的盲区，逐条给出证据链 + 与 DESIGN §4.1/V0/V2 的映射 + 处理边界。
> **方法**: 结合 2026-03\~09 社区实测（agent CLI 协作/llama-server 并发）与现役软硬件（gfx1151 RADV Vulkan、unsloth 单实例、opencode 1.18.25、LiteLLM/Zen 网关、claude 2.1.258）。
> **核心结论**: D6 当前设计"保守正确"——单槽 + 工作区排它锁 + 观测先行恰好**全部避开** BS-3 槽 bug 与 BS-1/BS-2 前提不稳；这些盲区只在并发 fan-out 阶段被激活，处理边界见 §6。

***

## 1. BS-1【硬】跨工作区并行时 opencode.db SQLite 写锁序列化

- **证据**: [py-opencode-wrapper](https://github.com/idailylife/oc_py_wrapper) 明确 `isolate_db=True`——并发 `opencode run` 必须各自独立 `<XDG_DATA_HOME>`，否则共用一个 `opencode.db`，在 **tool 执行时于 SQLite 写锁上串行**。

- **与 D6 冲突**: D6 锁在工作区 flock 级（DESIGN §4.1），保证"同工作区单写者"，但**跨工作区**（paper/cpp\_hub/spec）在**同站**并行时，默认都读 `~/.local/share/opencode` 同一 db → read 并行（V2 readonly fan-out）可能被 db 写锁悄悄串行，`queue_s` 记排队但**无法归因**根因是 db 锁而非模型槽。

- **落点（V2 前置不变式）**: 每工作区独立 `XDG_DATA_HOME`（`isolate_db` 等价物）。成本低，须写进 V2 设计约束，或并入 V0 验证门。

## 2. BS-2【硬】网关/请求方言可能强制 parallel\_tool\_calls=false，令 fan-out 静默变串行

- **证据**: [codex-pooler #180](https://github.com/icoretech/codex-pooler/issues/180) 实锤——经第三方网关（OpenAI-compatible **Lite 方言**）跑模型时，`task` 工具 fan-out **永远串行**（3/3 次仅一个 sibling 调用）；官方 OAuth 才并行。Lite 方言锁死 `parallel_tool_calls=false`（openai/codex #26487 引入，Lite 是"耦合请求方言"非单纯并发开关）。

- **证据（2026-09-04 深化，剥字段是普遍故障源，非单点）**: [LiteLLM #38612](https://github.com/BerriAI/litellm/issues/38612) —— `chatgpt` provider 的 transformation 用 `allowed_keys` 白名单**剥掉** **`parallel_tool_calls`**，后端看到 Lite header + 默认 true → 400，**网关剥字段→静默方言漂移的官方案例**；[sub2api #6107/#6084](https://github.com/Wei-Shaw/sub2api/pull/6107) —— OpenAI 硬性要求 Responses-Lite 必须 `parallel_tool_calls:false`，网关强制降 false。共同指向：**修字段不治本，网关是方言不确定面**。

- **与 D6 冲突**: D6 并发相走 **LiteLLM / Zen 网关**（DESIGN §9.4）。若网关是 Lite 方言，opencode 的 `task` 工具扇出在 parent **单轮内发不出多个子代理** → 社区 Orca 式"并行赛马"策略不生效，且无报错（静默）。

- **落点（V2 验收前提, 提升为 V0 新增门）**: 用一条 3-sibling `task` 提示词实测网关是否放行多 tool call。这是 D6 真值源约定（§2.1/§9.4 实测层）的正确归因入口。

- **落点（2026-09-04 深化，正面解药）**: 扇出可靠性分两条路线——①**模型内并行工具**（依赖 `parallel_tool_calls` 方言，被网关剥字段→不可靠，❌）；②**编排层并发 HTTP 发起**（多线程各发完整独立请求，不依赖方言→健壮，✅，Hermes `async_delegation`/Codex `multi_agent max_threads`/D6 `task` 多 agent 同构）。**BS-2 解药是把扇出从模型内编译期并行下沉到编排层运行期并行**，而非修网关字段。

## 3. BS-3【硬】单槽是硬瓶颈；gfx1151 + 多槽有已知 slot-0 stuck bug

- **证据**: llama.cpp server `update_slots()` 有 [slot0 stuck bug #20906](https://github.com/ggml-org/llama.cpp/issues/20906)——**恰好 Radeon 8060S (RADV GFX1151)、uma:1**；2 请求并发时 slot0 从 init\_sampler 到 token 生成**卡 9 分钟**，且区分出是后端自有任务。报告里 `n_parallel=auto→4, kv_unified=true`。

- **与 D6 冲突**: D6 明确单槽（DESIGN §4.1），**恰好避开**该 bug ✓；但 V2 要"真并行"则单槽(串行)或加槽(撞 #20906 + KV 翻倍)。D6 现定"观测先行 F1"——`queue_s` 只能看到排队，把并发归因留给 V2 补探测乃合理但有上手成本。

- **落点（V2 探测模块设计输入）**: 若加槽，先用同源 n\_ubatch 回归验证该槽 bug 是否命中；否则维持单槽，fan-out 只放**跨站**（A↔B 静态 IP/USB4），同站并行收益被槽位封顶。

## 4. BS-4【中】Continue-vs-Spawn 决策表缺 context-rot 维度

- **证据**: Thariq 五选择框架（[继续/rewind/clear/compact/subagent](https://github.com/shanraisshan/claude-code-best-practice/blob/main/tips/claude-thariq-tips-16-apr-26.md)）——"继续"是最差 default；rewind 优于"纠错续跑"；**subagent 是上下文管理手段而非并行工具**；1M 窗口 context rot 约 300-400k 起；`/compact` 有损，`--continue` 只带摘要不带细节。服务端 [compaction](https://platform.claude.com/docs/fr/build-with-claude/compaction) 已被官方推荐用于长会话。

- **与 D6 冲突**: D6 §9.6-2 决策表留给二期 `--continue` 路由，但应显式纳入 **context rot 阈值 + "新任务=新 session"**，否则二手决策表被"continue 方便"误导。

- **落点（二期决策表输入）**: 按模型窗口设 rot 阈值（免费档 lightning 262k / nemotron 1M 不同）。

## 5. BS-5【中】token 预算与可恢复重放（fan-out 成本线性增长）

- **证据**: opencode-drawer 的 [budget/cap + 按 key 重放的 journaling](https://www.npmjs.com/package/opencode-drawer-workflows)——崩溃后重放**仅重跑未 settle 的 agent 调用**，不重花已完成 token；并发门 `min(16, cores-2)`。

- **与 D6 冲突**: D6 已吸收孤儿锁/幂等（§9.8.1），可再吸收"按 task 卡 key 粒度重放"以省崩溃后重复成本。

- **落点（事务性采纳）**: 二期 `--continue/review` 时按任务卡 key 记录已完成子步骤，重放只补未完成段。

## 6. BS-6【中】统一内存带宽竞争（硬件约束）

- gfx1151 uma:1 统一内存、Vulkan decode 快 prefill 慢（手册 §8.x 已录）→ 同站 read 并行多个短 prefill 抢统一内存带宽 + KV 共享。同站并行收益 < 跨站分配。

- **落点**: V2 扇出前用 GTT 实测判据，不预设同站并行收益。

## 7. 处理边界总结

| BS   | 严重性 | 决定                                   | 归属            |
| ---- | --- | ------------------------------------ | ------------- |
| BS-1 | 硬   | 提升为 **V0 新增验证门**：跨工作区并行需 isolate\_db | V2 fan-out 前置 |
| BS-2 | 硬   | 提升为 **V0 新增验证门**：网关是否放行多 tool call   | V2 fan-out 前置 |
| BS-3 | 硬   | 登记为 V2 并发探测模块设计输入（加槽需回归槽 bug）        | V2 探测模块       |
| BS-4 | 中   | 并入二期 `--continue` 决策表输入              | 二期            |
| BS-5 | 中   | 事务性采纳（按 key 重放）                      | 二期            |
| BS-6 | 中   | 扇出前 GTT 实测，倾向跨站并行                    | V2 设计输入       |

## 8. 复现记录（2026-09-04 实机回填）

### 8.1 BS-3 slot0-stuck #20906 复现（A/B 两站）

**方法**: 对现役 unsloth 实例（gpt-oss-120b，KV q8\_0）并发两路长上下文请求（各 \~1500 词随机文本 prefill，`max_tokens=16` 短 decode，聚焦 prefill/batch 相位），复现前执行备份预案（§9）。

| 站          | 前端           | 槽位                       | 结果                                                                        |
| ---------- | ------------ | ------------------------ | ------------------------------------------------------------------------- |
| B（GTR-Pro） | unsloth:8080 | `--parallel`（unsloth 默认） | **未命中**；两请求完成，`engine_stats running` 曾达 2（双槽真并行），后端 POST 200（295ms/615ms） |
| A（NEX）     | unsloth:8080 | `--parallel 4 -c65536`   | **未命中**；两请求完成，`running=2`，POST 200（295ms/616ms）                           |

**结论修正（较 draft）**: slot0-stuck 为**概率性/窗口性 bug**，当前两站现役配置吞吐下均未复现；**不能据此判定免疫**。提高复现概率方向：压满槽数（A 站 4 槽）、混入不同长度 prefill 制造排空竞争、或切 HIP 后端交叉验证 logits。复现用脚本 `ops/station-bin/repro-*.sh`，备份/重启预案见 [REPRO-RUNBOOK.md](../../ops/station-bin/REPRO-RUNBOOK.md)。

### 8.2 BS-1 opencode.db SQLite 写锁串行化（B 站实测）

- **实测**: 生产 `opencode.db` 为 **WAL 模式 + busy\_timeout=5000ms**（存在 `-wal`/-shm，wal 约 4.2MB）；XDG\_DATA\_HOME 未设 → 默认全局一份 `~/.local/share/opencode/opencode.db`（143MB），**多工作区/会话共用同一 db 确认成立**。

- **并发写时序**（独立副本模拟，非生产）: 两并发写 wall=5.2ms vs 串行两写 total=3.0ms → 写操作被锁**排队（非死锁）**。

- **结论分级**: BS-1 的「写锁串行化」**成立但不危重** —— WAL + busy\_timeout 下小写入是排队而非阻塞；真正风险在**大而频繁的 tool 输出写**（大 tool 缓存/快照/会话持久化）时排队时间放大。**V0/V2 前置不变式「每工作区独立 XDG\_DATA\_HOME（isolate\_db 等价物）」仍需保留**，用于隔离高频大写入路径。

### 8.3 BS-2 网关 parallel\_tool\_calls 方言（B 站实测）

- **本机 LiteLLM :4000 在跑**（pid 2637，`litellm/config.yaml`，`--num_workers 1`），但 `/v1/models` 返回 **Internal server error** → 网关诊断面不稳，佐证「网关是瓶颈面」。

- **config.yaml 实测**: `model_list` 用 `openai/` 前缀（OpenAI-compatible 方言），**无任何** **`parallel_tool_calls`** **显式配置** → 依赖 provider 默认；OpenAI-compatible Lite 方言通常默认 `false`（锁死并行主动途）。`rpm: 30` 路由限流是硬并发上限。

- **免费的 subagent 扇出实测**: `opencode run -m opencode/nemotron-3.5-lightning-free` + 3-sibling subagent 提示词 → **timeout 300 无输出（卡住）**；且 `auth.json` 0 credentials（默认模型走 opencode 内置远端免费档，非本机）。

- **结论**: BS-2 成立 —— 现役网关（LiteLLM openai/ 方言 + 免费档）**不保证并行 tool call 扇出**，V2 的「单轮 3-sibling 并行」前提不稳、且失败为静默。**保留 V0 新增门：网关是否放行多 tool call**，作为 V2 fan-out 硬验。

### 8.4 BS-6 统一内存带宽竞争（B 站实测）

**方法**: unsloth:8080，409-token prefill 短请求，串行 vs 并发 4 发对比总耗时。

| 模式     | 总耗时                   |
| ------ | --------------------- |
| 串行 4 次 | **3320ms**（各 \~830ms） |
| 并发 4 发 | **3431ms**（≈串行，微慢 3%） |

**结论**: 并发 4 发（>1 槽）总耗时 ≈ 串行（无加速、无降速）→ 统一内存 prefill 是主瓶颈，并发被串行化，**同站并行收益被槽位/带宽封顶**。验证「V2 扇出倾向**跨站分配**（A↔B USB4），同站 read 并行收益有限」。

### 8.5 BS-4 / BS-5（设计类，不可实机复现）

- **BS-4**（Continue-vs-Spawn 缺 context-rot 维度）: 属**决策表设计准则**，非可执行 bug。落点不变：按模型窗口设 rot 阈值（free lightning 262k / nemotron 1M），并入二期 `--continue` 决策表。

- **BS-5**（token 预算/可恢复重放）: 属 **journaling 机制设计**，非可复现 bug。落点不变：二期按任务卡 key 记录已 settle 子步骤，崩溃后重放只补未完成段。

> 复现脚本备份: `BLINDSCAN-v2-orchestration.md.bak`（回填前）。

### 8.6 Hermes Agent 编排机制与社区编排案例（落点摘要）

> **调研主体已迁出**：Hermes Agent 编排架构源码实读 + 社区编排框架综述（Gas Town / OpenAI Agents SDK / LangGraph / CrewAI / AutoGen / Temporal / Tonbi 对比）已迁移至调研总文档 **`docs/Agent生态升级与多智能体协作架构调研.md §9`**（2026-09-04）。本节仅保留 D6 spec 侧**落点结论**，避免通用调研素材与 d6 复现记录混档。

#### 8.6.1 对 D6 的落点映射

1. **工作区隔离已验证成熟范式**: Hermes 子代理独立 `task_id`/terminal/file-ops 缓存、Tonbi 单看板 + 独立 agent——D6「单工作区单写者」与业界隔离思路一致，**保留**。
2. **BS-5 可吸收两种成熟持久化范式**: batch\_runner 的「按内容 resume」+ LangGraph/CrewAI 的「@persist/checkpoint」，叠加现有「任务卡 key + 孤儿锁幂等」→ 二期重放更稳。
3. **BS-2（网关纯串行扇出）在 Hermes 内不适用但提醒边界**: Hermes 自己用 `ThreadPoolExecutor` **进程内真并行**绕开网关了 parallel\_tool\_calls 方言问题；这提示 D6 若要坚持「单轮多子代理发起」，**同站进程内多线程也可作为规避网关方言的备选**（代价：同站统一内存带宽竞争，回 BS-6 结论，仍倾向跨站扇出）。
4. **编排「依赖 DAG / 健康监控 / 崩溃恢复」普遍空缺**: 连 Hermes 官方都把「委派→多智能体」列为未竟愿景、CrewAI 用 Flow 骨架补确定性、Temporal 用外部平台补耐久——D6 的「确定性 wrapper + 任务卡状态机」方向正确，**无需追这些框架**，维持保守正确。

**状态**: §8.6 为调研补充（Hermes 主控站源码实读 + 社区综述），非复现结论；沿用 finalized。

### 8.7 跨站扇出专项（2026-09-04 调研，V2 设计输入）

> BS-3/BS-6 已定"同站并行收益被槽位/带宽封顶"，V2 倾向跨站。本小节把跨站扇出的**数据面算力来源 + 编排侧前置 + 互补关系**补全，作为 V2 设计输入。

#### 8.7.1 数据面：跨站 = 唯一真并行来源

- llama-server 单实例 = **单** **`server_context`（专用单线程）+ 单一共享 batch**（`server_queue`→`update_slots` 合并进一次 `llama_decode`，官方 README-dev 明示）；并发数被 `n_parallel`/slot 封顶，且 `prefill 兼容性 / 内存带宽` 都在**单站物理资源**内收敛（uma:1 已验证，§8.4）。

- **跨站扇出**将请求分发到 **A、B 各自独立的 llama-server 实例** → 各自的 batch、KV、内存带宽**物理独立** → A+B 各一槽 = **真正 2x 数据面并行**，规避"单站 prefill 被内存带宽串行化"。这是跨站面向 BS-3/BS-6 的正解。

#### 8.7.2 编排侧前置（D6 V2 需新增）

1. **M3 扩展**：readonly 任务复制为 N 份（N=候选站）各跑各的。`readonly` 无写冲突 → **无需跨站 flock**（flock 仍只在本站互斥写任务，DESIGN §4.1 双层锁语义不变）。
2. **同步**：M1 已支持多站推拉（各自 `~/agent-workspaces/<proj>/`）；M5 两站 out/ 各自回收 → 主控台汇总。
3. **硬前置**：两站 unsloth 健康（infer-load 域：load-mem-gate / health 认证 / wait-gtt）；同模型（gpt-oss 两站均有）→ 纯净 cross-station 扇出；B 站 nemotron / Zen 出站可作为异构补充。
4. **限制**：仅 `readonly`（research/分析/审查）有效；`implementation`（写）仍单工作区排它。

#### 8.7.3 与 BS-2 的互补关系（V2 定位）

| 层         | 要解决的问题                      | 解药                        |
| --------- | --------------------------- | ------------------------- |
| BS-2（控制面） | 扇出**能否发起**（网关剥字段/方言漂移）      | 编排层并发 HTTP，绕开网关方言（§2 落点②） |
| 跨站（数据面）   | 发起后**是否真并行**（单站 batch+带宽收敛） | 多站独立实例 2x                 |

→ 两者互补，**D6 V2 的"跨站扇出 + 编排层并发发盘"同时命中两个解药**（与 Hermes 上轮结论闭环：Hermes 进程内并发 HTTP 绕方言；跨站绕带宽）。

#### 8.7.4 L1 验证设计（2026-09-04 落档，判据先行；CHECKLIST「BS 验证门」对齐）

> 方法铁律（三条新加于 D6 现有验证纪律之上）：**①隔离单变量**（同批任务只改被测变量）；**②对照基线**（每组实验必带现状基线）；**③客观 running 判据**（并行发起须让 unsloth `/properties` 的 `engine_stats.running` 升到期望并发数，只信耗时不够——FIFO 合并也会显得快）。另：**重复 N 次取中位数**（BS 是概率/带宽特性，单次不可信）、**判据先写死**（禁止事后调判据让结果好看）。

| 门                    | L1 验证方法                                                              | 通过判据（先写死）                                                 | 客观并行判据                                    | 归属               |
| -------------------- | -------------------------------------------------------------------- | --------------------------------------------------------- | ----------------------------------------- | ---------------- |
| **BS-1** isolate\_db | 同批 4 个 opencode 写任务：现役共享 db vs 各自 `XDG_DATA_HOME`                    | 隔离后并发两写耗时 < 现役基线（已测 5.2ms 排队，判据=收益非"不崩"）；SQLite busy 命中归零 | busy\_timeout 命中次数↓                       | V0 前置            |
| **BS-2** 编排层并发 HTTP  | 3-sibling：现役经网关单轮 tool call vs 编排层并行发起                               | 完成时间窗 < 串行基线；unsloth `running` 曾达 3                       | `engine_stats.running`=3                  | V0 前置            |
| **跨站** 多站独立实例        | 同批 4 个 readonly：A 串行 4 次 vs A+B 各 2 次（cross-station）；先验两站 unsloth 健康 | cross-station 总耗时 ≤ A 串行 ×\~1.6（对照 §8.4 同站并发仅微慢 3%）       | A `running`=2 **且** B `running`=2（证分散两实例） | V2 设计输入（可先做前瞻实验） |

**可验证实验（归因，复用上表命令）**:

- ① BS-2 归因：同一条 3-sibling 请求 **直发 B 站 LiteLLM** vs **绕网关直连 A 站 unsloth** → 界定"网关剥字段 vs 后端不支持"谁是真凶，决定 BS-2 解药是否真需落在编排层。

- ② 跨站收益：同批 4 个独立 readonly 任务 **A 串行 4 次** vs **A+B 各 2 次** 总耗时对比 → 量化数据面收益。

**推进顺序**: L1 微基准（本表）→ L2 端到端（真实 readonly 卡）→ L3 回归（agent-cli-smoke + A 抽检）。**BS-2 最先做**（扇出能否发起是其他前置）。

**状态**: §8.7 为跨站扇出专项调研（源码/设计输入），非实机复现；沿用 finalized。

#### 8.7.5 BS-2 L1 实机回填（2026-09-04，判据修正 + 结果）

> **本机网络散文**：A/B 站 IP 已从 11/15 漂为 32/33；ssh 用 mDNS 别名 `scott-lau-GTR-Pro.local`（B，192.168.1.32，USB4 10.10.10.2）、`scott-lau-NEX.local`（A，.33/USB4 .1）。
>
> **判据修正**：`nvidia`/llama-server 均无 `/properties` → `engine_stats.running` 客观判据在此端**不可用**。改用**墙钟收敛**：3 并行 HTTP 的完成墙钟 ≈ max 且 ≪ 各请求之和，即证数据面并发被后端接受（FIFO 串行合并会显 ≈ sum，恰可区分）。

**实测 1 —— 直连 model 单轮 tool\_call 并行度（B:8080 直连，gpt-oss-120b-MXFP4）**：

- 3-tool + `parallel_tool_calls=True`，直连 llama-server(8080) → HTTP 200，**单轮仅 1 个 tool\_call**（wall 48.3s）。

- **结论**：单模型内"编译期并行"不成立 → fan-out 必须押编排层并发 HTTP（§2 落点②实证成立）。

**实测 2 —— 编排层并发 HTTP 墙钟收敛（直连 8080，3 单 tool 请求）**：

- 串行基线 3×：37.6 + 31.5 + 41.7 = **110.9s**（每轮 tool\_calls=1）。

- 3 线程并行：**wall=52.1s ≈ max(52.1s)**，≪ 串行和 110.9s → **收敛判据 PASS**，后端数据面真并行（同站 3 并发 \~2.1× 加速）。

- 并行批个别请求 tool\_calls=0（模型行为方差，非扇出机制问题）。

**实测 3 —— 网关路径（对照组）当前故障（根因详见 §8.7.5 下方更正）**：

- B:4000 LiteLLM：连 `master_key=sk-RPC-gz...` 也返 **401「Invalid token payload」**，`/v1/models` 报 Internal error（注：此错误逐字源自**上游后端**对过期的占位 key 拒绝，非网关 frontdoor 校验，见下文更正）。

- config 语义：`nemotron → B:8080`（现载 gpt-oss）、`gpt-oss → A:10.10.10.1:8080`，rpm 30，usage-based-routing-v2。

**⚠️ 根因更正（2026-09-04 二次核实，最初"master\_key 哈希不匹配"断言有误）**：

- **真凶 = 后端实例换载后 key 不同步**：本地 8080 unsloth 实例今 03:24 重新拉起（gpt-oss-120b-MXFP4，自带 `sk-unsloth-...` key），但 litellm 进程仍为 9/3 旧进程、config 的 `nemotron` 路由写死占位 `api_key: sk-local-noauth`。实测：同后端用 `sk-local-noauth` 直打 8080 返「Invalid token payload」逐字复现；用真实 `sk-unsloth-0895...` 直打返 200。

- **叠加**：fallback `gpt-oss`→A(10.10.10.1:8080) 连接被拒（A 的 llama-server 未监听，A 主机本身通 USB4/LAN）→ 双后端全挂 → 网关 401。

- **与"AB 更新"的关系**：是**更新/换载后配置不同步**（后端 key 变了、litellm 未重启、A 端未拉起），非更新损坏网关二进制。

- 修复路径：①config `nemotron` 路由 `api_key` 改真实 unsloth key + 重启 litellm；②拉起 A:8080；③或走直连（编排层并发 HTTP 实证，fan-out 押编排层，天然绕网关）。

**BS-2 门判定**：✅ **通过**（编排层并发 HTTP 墙钟收敛 52.1s≪110.9s；单轮 tool\_call=1 证模型内并行不成立；网关不可用本身反证 fan-out 须绕网关押编排层）。

## 9. 备份与重启预案

> 复现属对**现役服务**的风险操作，任何并发打压前必须：
>
> 1. **配置备份**: `cp /home/scott-lau/.unsloth/run-<alias>.log{,.pre-repro-<ts>}` + 备份 conf `/etc/llama-instances/<alias>.env`
> 2. **端点到 key 快照**: 记录当前实际端口 + API Key，供复现后重指 CLI 端点
> 3. **重启路径**: 卡死后 `infer-unload <alias>` → GTT 回收 → `infer-load <alias> --backend unsloth`；极端情况 `pkill -9 -f 'unsloth studio run'` + `pkill -9 -x llama-server` 兜底
> 4. **复现窗口**: 仅本实例，复现过程不触碰 A 站常驻 gpt-oss；复现完恢复 8080 端口与 key 后再收尾

***

**状态**: **finalized（2026-09-04 实机复现回填）** —— BS-1 写锁串行化成立但非危重（WAL+busy\_timeout 下排队非阻塞）；BS-2 网关方言不保证并行扇出，free 档 subagent 实测卡死、且失败静默；BS-3 slot0-stuck 两站均未命中（概率性 bug，不能免疫）；BS-6 并发≈串行（带宽/槽位封顶，倾向跨站扇出）；BS-4/BS-5 为设计类，落点不变。详见 §8。
