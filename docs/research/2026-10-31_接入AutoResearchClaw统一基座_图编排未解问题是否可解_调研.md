# 接入 AutoResearchClaw 形成统一基座：当期图结构编排未解问题是否可解

---
id: research-arc-unified-base-graph-questions-2026-10-31
type: research
version: 1.0
status: done（结论已出；**无任何代码/配置改动**；外部仓只读取证）
date: 2026-10-31
depends: \[d6-agent-standard-OPEN-ISSUES, d6-agent-standard-D7-PROTOCOL-CONCLUSION-CONTRACT, graph-shard-dependency-DESIGN]
upstream: \[research-graph-shard-dependency-2026-10-31, research-graph-orchestration-2026-10-01, ADR-0004, ADR-0009]
------------------------------------------------------------------

> **触发**：用户令「假设本框架接入 D 盘的 AutoResearchClaw，形成统一「AI 学术推理 + 工程编码 + 形式化验证」基座，当期图结构编排的未解问题是否可解」。
> **射程**：只判**可解性**（可解 / 部分可解 / 不可解 + 前置条件 + 证据）；**不改任何代码、配置、站上状态**；**不擅自新增台账条目**。
> **前提口径**：以 `arb-v2-decisions-research-design.md` 的 D1–D5 裁定为**当前生效**（宿主 = ARC；RPC 集群已单独发布，基座只保留 `RunEnvelope` 互操作 + 可选远端执行适配器；ARC 后续改动强制走 Spec_Workflow）。
> **配套 spec**：[graph-shard-dependency/DESIGN.md](../../spec/graph-shard-dependency/DESIGN.md)（本调研**不改**其 S1/S2 裁定）。

---

## 0. 结论前置（先看这七句）

1. ★★ **接入 ARC 不会让图编排问题「自动」变可解 —— 但它把「什么才算把图编排做好」钉成了四个可判定的轴（详见 §3.4）。** ARC 的编排是**阶段级线性契约 + 共享 `run_dir` 文件系统**（23 阶段一条链，产物靠「同机同目录」找回），它**恰好缺本仓需要的那三样**：stage 内的依赖边、并发闸门语义、跨站片产物搬运。
2. ★★ **9 条问题里：4 条「可解（但只能在本仓解）」、3 条「部分可解（可借 ARC 形态，须新增契约）」、2 条「不可解（两个框架都不具备）」。** 详见 §2 主表。
3. ★★ **可解的 4 条全部落在 RPC 执行面**（Q1 依赖边、Q2 层宽判据、Q3 失败传播、Q6 G1 四路决策）⇒ 实施路径**不变**：`spec/graph-shard-dependency` 的 **乙 → 甲1 → 甲2** 照旧；ARC 只提供「上层脊柱」与「判据形态」，不替本仓改半行 `agent-cli.ps1`。
4. ★★ **决定性的一条是「产物怎么过站」（Q9）**：ARC 的产物传递是 `_read_prior_artifact(run_dir, 文件名)` 在**同一个 run 目录**里找件；本仓三站互不可见、`merged-output.txt` 只是日志拼接 ⇒ **ARC 这条能力在本仓拓扑下不成立**，甲2（主控显式回收 + `--Attach` 注入）仍是**唯一**能让依赖成立的一刀。
5. ★★ **ARC 自身也有「声明了却没人读」的同型坏味道**：Stage 11 写出 `schedule.json` 的 `"depends_on": ["baseline"]`，全仓**无消费点**（只写不读）。⇒ 不能拿「ARC 有依赖声明」当本项目依赖已可执行的论据；相反这是「声明 ≠ 执行」**跨项目复现**的旁证。
6. ★★ **能借的最有价值的两样是「形态」不是「实现」**：① `stages.advance()` 的「状态 + 事件 ⇒ 下一态，非法转移直接 raise」纯函数形态（可机械化为 `O-186` 的 G1 四路决策）；② `stage-13_v1` 式**版本化回滚目录 + MAX_DECISION_PIVOTS 上限**（可借给「图迭代」的收敛闸）。
7. ★★ **ARC 的真实贡献是「问题定义层」，不是「解法层」**：它把九条问题**钉成 4 个可验收的轴 + 3 条有理由的「不做」**（§3.4）。⇒ 本仓不需要「更聪明的图引擎」，需要的是把已有的四条判据写成夹具。

---

## 1. 事实基线

### 1.1 三份基座文档的生效口径

| 文档 | 效力 | 与本调研相关的要点 |
|---|---|---|
| `academic-reasoning-base-fusion.md` | 架构总报告（部分表述已被 v2 取代） | 四内核 `K1 Ledger/Evidence`·`K2 Gate/Policy`·`K3 Reason/Verify`·`K4 Model/Routing` + 脊柱 `S ← ARC 23 阶段`；7 个跨层契约 C1–C7；冲突 C1–C10 |
| `arb-v2-decisions-research-design.md` | ★ **当前生效裁定（D1–D5）** | 宿主 = ARC（23 阶段为唯一生产脊柱）；**RPC 集群已单独发布**，基座只保留 `RunEnvelope` 互操作 + **可选**远端执行适配器；学术八条 AR-01..AR-08 机械化；ARC 后续改动强制走 Spec_Workflow。★ **`RunEnvelope` 无 verdict 字段**（C1 只承载执行事实） |
| `arc-knowledge-paper-textbook-integration.md` | 知识侧接入（Paper/Textbook） | 形式化不在 ARC 内：Lean 映射来自 `D:\Textbook` 的 `formalized_in`（165 条），Auto_Prover verdict 经 `ap_kg_import_delta/v1` 单向回写；ARC 的 KB 是**只写归档**、KG **零调用**；真正消费知识的是 `hitl/claim_verifier.py` |

### 1.2 ARC 代码事实（E1 读码，2026-10-31）

> 取证对象：`D:\AutoResearchClaw-main\AutoResearchClaw-main\researchclaw\`。下表只记**能直接支撑判决**的事实，不做评价。

| # | 事实 | 证据（文件 · 符号） | 对本仓的含义 |
|---|---|---|---|
| F1 | **23 阶段是一条线性链**，无分支汇聚节点 | `pipeline/stages.py` 的 `STAGE_SEQUENCE = tuple(Stage)` 与 `NEXT_STAGE` 逐级映射 | ARC **没有「stage 内子图」概念** ⇒ 片间依赖无处安放 |
| F2 | **契约是文件级 I/O，不是节点级依赖** | `pipeline/contracts.py` 的 `StageContract{input_files, output_files, dod, error_code, max_retries}` | 声明的是「读哪些件」，**不是「依赖哪个节点」** |
| F3 | **产物传递 = 共享 `run_dir`** | `executor.execute_stage` 调 `_read_prior_artifact(run_dir, input_file)`；后者在 `run_dir/stage-*` 里按文件名找最新的非版本化副本 | 依赖「同一台机器、同一个目录」。本仓三站互不可见 ⇒ **不成立** |
| F4 | **失败传播 = all_success** | `runner.execute_pipeline`：`status == FAILED ⇒ break`；唯一例外 `NONCRITICAL_STAGES`（仅 Stage 21）且需 `skip_noncritical=True` | 与本仓固定 `all_success` **同向**；但 ARC 留了「非关键阶段跳过」的开关，分片**不得**照搬 |
| F5 | **无 stage 内并发** | `pipeline/` 内 `parallel` / `ThreadPool` / `asyncio` / `DAG` **零命中**；`config.py` 的 `max_parallel_tasks=1` **无消费点**；唯一并发控制是 `project/scheduler.py` 的**项目级** `max_concurrent=2` 优先级队列 | ARC 帮不上「层宽判据」；但项目级调度是「**满则排队、不拒绝**」的外部同向样本 |
| F6 | ★ **ARC 也有「声明不消费」** | `stage_impls/_execution.py` 生成的 `schedule.json` 写 `"depends_on": ["baseline"]`；全仓 grep 该字段**只有写入、没有读取** | 「依赖声明 ≠ 依赖执行」**跨项目复现**；不能作为本仓问题的解法论据 |
| F7 | **迭代 = 阶段级回滚** | `stages.py` 的 `DECISION_ROLLBACK`（pivot→Stage 8 / refine→Stage 13）+ `MAX_DECISION_PIVOTS=2`；`runner` 递归 `execute_pipeline(from_stage=…)` + `_version_rollback_stages`（`stage-13_v1` 版本目录） | 这是 ARC 有、本仓缺的「迭代/搜索」；但粒度是**阶段**，不是**片** |
| F8 | **断点 = 单标量** | `runner._write_checkpoint` 只写「下一阶段」；`read_checkpoint`/`resume_from_checkpoint` 据此恢复 | **无节点级状态、无跨 run 图** ⇒ 跨 run 依赖无处挂载 |
| F9 | **执行面接缝在手** | `experiment/factory.py` 有 `docker` / `ssh_remote` / `colab_drive` / 三类 agent 沙箱；`StageResult.evidence_refs` 已由 `_write_stage_meta` 落进 `decision.json` | 与 ARB 的 C1 `RunEnvelope` / C5 `EvidenceRef` 的接线点**已存在**（字段级，不是新造） |
| F10 | **ARC 内无形式化验证** | `researchclaw/` 全仓无 Lean / Auto_Prover 调用点（grep 仅命中 "clean" 误匹配） | 「形式化」只能来自 Textbook 的 `formalized_in` + AP `ap_kg_import_delta`，或按 ARB 定为 **Tier-3 可选** |

### 1.3 本仓待判的九条（来源）

| 编号 | 问题 | 出处 |
|---|---|---|
| Q1 | `needs=` 是数据依赖还是仅排序；乙期是否拒执行 | `O-184` / DESIGN §1.3 S1 |
| Q2 | 「总片数 ≤ 站数」判据错配，改为「单层最大宽度」 | `O-184` / 调研 §3.1 M2 |
| Q3 | 失败传播固定 `all_success`；`SPLIT_SKIPPED` 不得读成通过 | DESIGN §1.3 S2 / 调研 §9 |
| Q4 | `join` 的「同主体相反结论」裁决（禁阈值，只报出） | D7-PROTOCOL-CONCLUSION-CONTRACT §6.2 |
| Q5 | 图迭代/搜索缺失 | 图编排调研 §1.2 |
| Q6 | G1 四路决策（继续/分叉/新开片/转人工）仍是文档而非判据 | `O-186` |
| Q7 | 跨 run / 跨卡依赖 | `O-184` 射程外 |
| Q8 | 形式化验证与工程编码如何分层 | 本次前提 / ARB |
| Q9 | 片产物如何跨站搬运（依赖成立的真实前提） | 调研 §1.4 / 甲2 |

---

## 2. 逐条判决（主表）

| 编号 | ARC/基座能否承接 | 判决 | 前置条件（缺一不可） | 证据 |
|---|---|---|---|---|
| **Q1** `needs=` 语义与乙期拒执行 | 不能。ARC 无 stage 内边（F1/F2），且自身有「声明不消费」同型（F6） | ★ **可解 · 只能在本仓解** | ① 用户批复 S1（数据依赖）与「`after=` 本批不做」；② 乙期先验红（现有正例探针改期望）；③ 零子进程早退 | F1/F2/F6 + 调研 §8 |
| **Q2** 层宽容量判据 | 不能。ARC 无 stage 内并发（F5）；项目级调度只做「满则排队」 | ★ **可解 · 本仓局部改** | ① 新纯函数 `Get-SplitWaves`；② `Get-SplitDispatchPlan` 收 `-Width` 并让既有夹具先红；③ 容量数值不变（3 站 × 1 腿） | F5 + 调研 §2.1 九系统 |
| **Q3** 失败传播 / skipped 语义 | 方向一致，可作外部锚点（F4） | ★ **可解 · 且已对齐** | ① 固定 `all_success`；② `SPLIT_SKIPPED` 与失败分开报，`join.status` 不因 skip 变 `ok`；③ **不**照搬 `skip_noncritical`（分片跳过会变静默通过） | F4 + 调研 §9 |
| **Q4** join / 冲突裁决 | 部分。ARC `review_service` 只做 LLM 评审 + `VerifiedRegistry` 数值白名单，**无冲突裁决器** | **部分可解** | ① 借 ARB 的 verdict 三分层（`RunVerdict` / `ClaimStatus` / `EvidenceTier`）与「白名单」形态；② 「同主体相反结论」仍按 D7 §6.2 **只报出、禁阈值** | F1/F9 + `pipeline/review_service.py` / `pipeline/verified_registry.py` |
| **Q5** 图迭代 / 搜索 | 部分。ARC 有**阶段级** PIVOT/REFINE + 回滚版本目录（F7），**无片级迭代** | **部分可解** | ① 跨 run 的迭代可借 ARC 脊线（rollback + `MAX_DECISION_PIVOTS`）；② split 内「片 i 失败后重跑片 i」仍须本仓自建（且依赖甲2 的产物通道） | F7 + `runner` 递归调用点 |
| **Q6** `O-186` G1 四路决策 | 部分。ARC 无显式「四路」，但 `advance()` 是「状态+事件⇒下一态」纯函数（非法转移 `raise ValueError`） | ★ **可解 · 形态可借** | ① 卡增 `decision` 字段（`continue/fork/spawn/human`）；② 纯函数按「上下文余量 / 证据冲突 / 工具失败次数」求值；③ 门禁只判「声明与求值一致」，不判决策对错 | `pipeline/stages.py` 的 `advance` / `TransitionOutcome` |
| **Q7** 跨 run / 跨卡依赖 | 不能。ARC 断点是单标量「下一阶段」（F8），无跨 run 图 | ★ **不可解（两框架都不具备）** | 若要做，须新设计（且中心调度会撞 ADR-0004「零自加载 · 无 daemon」） ⇒ **建议继续射程外** | F8 + ADR-0004 |
| **Q8** 形式化验证与工程编码分层 | 不能由 ARC 单独承接（F10）；但 ARB 已给分层口径 | ★ **可解 · 分层可定** | ① ARC = 推理/写作/门禁（默认 Stage 2 数值证伪）；② RPC = 执行面证据（`RunEnvelope` 互操作）；③ Auto_Prover = 断言级；④ **Lean = 可选 Tier-3**，Stage 20 不要求 `FORMALLY_VERIFIED` | F9/F10 + `arb-v2` D2/D3 + `arc-knowledge-…` §2 |
| **Q9** 片产物跨站搬运 | 不能。ARC 靠共享 `run_dir`（F3），无跨机搬运原语 | ★ **不可解（在 ARC 内）· 须本仓主控显式搬运** | ① 子卡派生 `evidence-manifest`；② 波末 `Invoke-EvmStatePull` 回收；③ `--Attach` 注入 + digest 比对；④ 真站实测（跨站两跳） | F3 + 调研 §1.4 |

### 2.1 判决口径说明

- **「可解」= 有明确的落点与判据，且不依赖未定前提之外的新架构**；不等于「已实现」。
- **「部分可解」= 能借到形态或分层，但关键判据仍须本仓自建**。
- **「不可解」= 现有两个框架都没有该能力，需新设计或明确排除射程**。Q7 建议排除；Q9 的「不可解」限定在 **ARC 内**（本仓甲2 可解）。

---

## 3. 四条硬结论

### 3.1 接 ARC ≠ 图编排问题可解

ARC 的价值在**上层**：23 阶段脊柱、阶段级契约与门禁、HITL、PIVOT/REFINE、证据引用字段（`evidence_refs`）。本仓九条问题里，**凡涉及「片」的**（Q1/Q2/Q3/Q9）都属于**执行面**，ARC 既无 stage 内图，也无跨机搬运 ⇒ 这些问题的落点仍在 `agent-cli.ps1` 的 `split` 段，**spec 的乙 → 甲1 → 甲2 顺序不变**。

### 3.2 「可解」不等于「现在能做」

4 条「可解」都有**未批复或未实测**的前置：Q1 等用户裁 S1；Q2/Q3 等夹具先验红；Q6 等 `O-186` 立项。本次调研**不动代码**，也不把「可解」报成「已解决」。

### 3.3 ARC 的同型坏味道要当警示，不能当依据

F6（`schedule.json` 的 `depends_on` 只写不读）说明「声明了却没消费」是**跨项目**的常见失败形态。本仓 `needs_graph` 标注「仅观测用」与之同型 ⇒ 乙期「响亮拒绝」比「补一个更漂亮的声明」更符合纪律（`O-184` 的「有边不排序 = 假图」）。

### 3.4 ARC 的真实贡献是「问题定义层」，不是「解法层」

ARC 不替本仓跑图，但它把「什么才算把图编排做好」钉成了四个**可判定**的轴。本仓九条问题放进这个坐标系后，**每条要么落进一个格子（目标因此可验收），要么明确落在坐标系外（「不做」因此有理由而非遗漏）**。

| 轴 | ARC 的锚点（事实） | 本仓问题被明确成什么 | 验收判据（可直接写夹具） |
|---|---|---|---|
| **A 依赖 = 文件级 I/O** | `StageContract` 的 `input_files` / `output_files`（F2） | Q1 不再是「依赖还是排序」的措辞之争，而是「下游片是否指名了要读的件、上游片是否声明了产出的件」 | 依赖片必须能指名读件；无可读件 ⇒ 拒执行并报 `SPLIT_NEEDS_UNSUPPORTED` |
| **B 失败 = 三态而非两态** | `FAILED ⇒ break` / `BLOCKED_APPROVAL` / `NONCRITICAL_STAGES`（F4） | Q3 从「all_success 还是可配置」变为「跳过必须与失败分开报，跳过不得被读成通过」 | `SPLIT_SKIPPED` 独立计数；存在 skip 时 `join.status` 不得为 `ok` |
| **C 迭代 = 回滚目标 + 轮数上限 + 版本目录** | `DECISION_ROLLBACK` / `MAX_DECISION_PIVOTS=2` / `stage-13_v1`（F7） | Q5 从「图迭代缺失」变为三个可答问题：回到哪一片、最多几轮、旧产物怎么命名 | 片级重跑须有显式回滚目标 + 上限 + 版本化目录，缺一不可 |
| **D 决策 = 纯函数（状态 + 事件 ⇒ 下一态）** | `stages.advance()` 非法转移即 `raise`（§2 Q6） | Q6 的 G1 四路从「文档描述」变为「可注入正反夹具的状态机」 | 非法转移必须抛错；四路各有正例与反例夹具 |

**坐标系外三条（明确「不做」，不是「漏做」）**：Q7 跨 run / 跨卡 —— ARC 断点只有单标量（F8），两个框架都没有节点级持久状态；Q9 跨站搬运 —— ARC 靠共享 `run_dir`（F3），本仓三站互不可见，**是拓扑不允许**而不是实现难；Q4「同主体相反结论」裁决 —— ARC 的 `review_service` 只产评审文本、`VerifiedRegistry` 只是数值白名单，两者都**没有冲突裁决**，故本仓维持「只报出、不裁决」。

★ **反向定义验收（来自 F6）**：ARC 的同型坏味道给出一条通用判据 —— **「有声明」不构成验收，「有消费点」才构成**。这条比任何 DAG 库的文档都更直接地约束了本仓 `needs=` 的验收方式。

---

## 4. 与现有 spec 的增量关系

| 项 | 关系 | 说明 |
|---|---|---|
| DESIGN §1.3 S1/S2 | **不变** | 本调研不新增裁定，只确认其前置条件与外部依据 |
| 甲2 的产物字段 | **建议（非本批）** | 片产物回收建议采用与 C5 `EvidenceRef` 同形的 `{tier, locator, digest, producer}`，便于日后汇入 ARC 证据面；**不改变甲2 的搬运机制** |
| `join.json` 字段 | **建议（非本批）** | `waves[]` / `skipped[]` 仅做**命名对齐**（对齐 ARC `decision.json` 的 `status/next_stage`），**不改语义** |
| `O-186` G1 | **形态先例** | 以 `advance()` 为范例：纯函数 + 正反注入夹具 + 非法转移即抛 |
| `O-185`（D7 灰度开关） | **不在本调研射程** | 属判据/契约问题，不涉及图编排；本次不判 |

★ 结论：**接入 ARC 不产生新的 spec 需求**；它只改变「证据字段叫什么」，不改变「图怎么跑」。

---

## 5. 未实测登记

1. **ARC 从未在本机实跑**：全部结论来自读码 + 三份文档；23 阶段端到端行为、`max_parallel_tasks` 是否在未检索到的分支被消费，均未实测。
2. **`ssh_remote` 沙箱能否把 RPC 站作为执行目标**：只读了 `factory.py` 的分支，未读 `ssh_sandbox.py` 的接口契约 ⇒ 未验；且 v2 裁定已把 RPC 降为「可选远端适配器」，优先级低。
3. **ARC `evidence_refs` 的实际内容**：未逐字段核对是否含 digest / tier；ARB 的 C5 仍为设计稿。
4. **PIVOT/REFINE 的递归成本与墙钟**：未测；`MAX_DECISION_PIVOTS=2` 的实际收敛率未知。
5. **文档与代码的漂移面**：只核了 `stages/contracts/executor/runner/cli/factory/scheduler` 与 `review_service/verified_registry`；其余模块未逐一比对。
6. **本仓九条的「可解」均未实现**：本次无代码改动，全部为判断。

---

## 6. 候选新问题（**不擅自入台账**）

| 候选 | 标题 | 为什么值得单列 | 建议 |
|---|---|---|---|
| `O-187`（候选） | 图编排层 ↔ ARC 基座的**互操作契约**（`RunEnvelope` / `EvidenceRef` 字段对齐；片产物回收是否采用同形字段） | 它会决定甲2 的产物格式；晚定则要改两次 | 等用户确认是否接 ARC；未确认前不建条目 |
| —（不建议新增） | Q7 跨 run / 跨卡依赖 | 两个框架都不具备；本仓 ADR-0004 禁中心调度 | 维持射程外，出现真实用例再立项 |

---

## 7. 来源

**外部（只读，2026-10-31）**

- `D:\AutoResearchClaw-main\academic-reasoning-base-fusion.md`
- `D:\AutoResearchClaw-main\arb-v2-decisions-research-design.md`（★ 生效裁定 D1–D5）
- `D:\AutoResearchClaw-main\arc-knowledge-paper-textbook-integration.md`
- `D:\AutoResearchClaw-main\AutoResearchClaw-main\researchclaw\pipeline\stages.py`（`STAGE_SEQUENCE` / `NEXT_STAGE` / `GATE_STAGES` / `DECISION_ROLLBACK` / `advance`）
- `…\researchclaw\pipeline\contracts.py`（`StageContract` / `CONTRACTS`）
- `…\researchclaw\pipeline\executor.py`（`execute_stage` / `_read_prior_artifact` 调用点 / 缺件即 FAILED）
- `…\researchclaw\pipeline\runner.py`（`execute_pipeline` / `_write_checkpoint` / `read_checkpoint` / PIVOT 递归）
- `…\researchclaw\pipeline\_helpers.py`（`_read_prior_artifact` / `_write_stage_meta` 写 `evidence_refs`）
- `…\researchclaw\pipeline\stage_impls\_execution.py`（`schedule.json` 的 `depends_on`）
- `…\researchclaw\pipeline\review_service.py` / `…\verified_registry.py`
- `…\researchclaw\config.py`（`max_parallel_tasks=1` / `max_concurrent=2`）
- `…\researchclaw\project\scheduler.py`（项目级优先级队列）
- `…\researchclaw\experiment\factory.py`（`docker` / `ssh_remote` / `colab_drive` 分支）

**本仓**

- [片间依赖边从观测到执行 · 调研](./2026-10-31_片间依赖边从观测到执行_调研.md)（§1.4 产物通道 / §8 两类边 / §9 触发规则）
- [graph-shard-dependency/DESIGN.md](../../spec/graph-shard-dependency/DESIGN.md) / [IMPLEMENTATION.md](../../spec/graph-shard-dependency/IMPLEMENTATION.md) / [CHECKLIST.md](../../spec/graph-shard-dependency/CHECKLIST.md)
- [D7-PROTOCOL-CONCLUSION-CONTRACT.md §6.2](../../spec/d6-agent-standard/D7-PROTOCOL-CONCLUSION-CONTRACT.md)
- [OPEN-ISSUES.md](../../spec/d6-agent-standard/OPEN-ISSUES.md)（`O-184` / `O-185` / `O-186`）
- [ADR-0004](../../adr/ADR-0004-统一管理入口为唯一管理面.md)（零自加载 · 无 daemon）
