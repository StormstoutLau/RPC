# Spec_Workflow 能否成为 D6/D7 工作流的「基准」—— 调研

- **日期**: 2026-09-23（**v2 — 经一轮跨仓复核后修订**，见 §8）
- **状态**: **仅调研（未改动任何被调研方）**
- **Scott 的设想（原话）**：**"Spec_Workflow 是否可以成为 D6 D7 阶段 agent 工作流的基准？"**
- **证据等级（本文件专用刻度，v2 起加命名空间）**: **`RPC-E1`**=本会话实读本仓 ·
  **`RPC-E2`**=子代理实读（全文报告在案，含文件:行号）· **`RPC-E3`**=联网一手检索（URL 可核）·
  **`RPC-E4`**=推断 · **`RPC-E5`**=未找到。
  > **⚠ 命名空间说明（v2 新增）**：v1 用裸标号 `E1–E5`，**与 `Spec_Workflow` 的
  > `ASSERTION_EVIDENCE_FRAMEWORK` 中 `E1–E5`（可重放性分级）同名不同义** —— 已被对方在复核中
  > **按其刻度**判为"标错"。**这是本仓文档自身犯下的第一例「符号冲突」**（正是 `U-2` 要治的病）。
  > 故刻度正式改名 `RPC-E1..E5`；**正文中出现的简称 `E2`/`E3` 一律读作 `RPC-E2`/`RPC-E3`**。
  > **⇒ 教训：跨仓引用必须带命名空间，且不要复用对方的符号。**
- **`D6`/`D7` 的指代（v2 新增，消除同名冲突）**：指 **`D:\RPC`** 的两个开发阶段 ——
  **`D6` = `D:\RPC/spec/d6-agent-standard/`**（三机集群 agent 标准 + 证据链）·
  **`D7` = 其次阶段**（跨主体复核闭环 + 九项目统一基座）。
  > **⚠ 与 `Spec_Workflow` 仓内的 `D6`（决定编号）同名不同义** —— 对方复核时如实报告"**指代不明**"，
  > **根因在我方未给命名空间**（**同一病的第二例**）。此后跨仓引用一律写 `D:\RPC/D6`、`D:\RPC/D7`。
- **伴读**: [D7 调研（合并稿）：立项 · 机制 · 统一基座](2026-09-23_D7调研_立项·机制·统一基座.md)（本文件是它的专题延伸）·
  [D6-D7 分阶段执行方案](2026-09-23_D6-D7分阶段执行方案.md)
- **复核记录**: 本文件 v1 被 `Spec_Workflow` 侧**独立主体**复核；**对方的更正经我方读原文核验后全部成立**。
  双向修正、新增发现与「谁来做修订」的答复见 **§8 跨仓复核实录**。

---

## 0. 结论先行

> **① 设想的答案不是"能/不能"，而是"『基准』这个词必须先拆开"。**
> 把"基准"拆成 **5 种不同用途**后，结论是：**2 项可以 · 2 项有条件 · 1 项"可以委托但不得继承"**（§2）。
>
> **② 权威源那一种：v1 判"必须拒绝"，v2 改判"可以委托，但不得继承"。**
> **⚠ v2 更正（Scott 转来对方复核意见，经我方读原文核验成立）**：v1 原写"**它自己的先例就失败了**"，
> **该措辞不成立，已撤回**。核 [ADR-0006 修订历史](file:///f:/Spec_Workflow/adr/ADR-0006-assertion-framework-dual-copy-authority.md#L133-L134)：
> **指针封堵 2026-08-17 已执行**（P-001，提交 `96edc5c`）·
> **回流通道 2026-08-17 已首次批量使用成功**（P-002 → 框架 v1.3/v1.4，已推送）。
> ⇒ **机制跑通且成功回流过一次** —— 方案 B 的目标（"哪个是真的"有答案）**达成了**。
> ⇒ **修正后的拒绝理由**：不是"先例失败"，而是**对象不同** —— `D6/D7` 与 `Spec_Workflow` 是
> **"消费方 ↔ 规范来源"**关系，而方案 C 讨论的是**"同一份规范的两个副本"**关系（对方判"这是方案 C 的
> 近亲"，属**类比越界**）；且 SLSA 的 **not transitive** 精确支持**"符合性不可继承"**。
> ⇒ **可以委托权威（有成功先例），但下游副本的符合性必须逐方重新确立。**
>
> **③ ★ 社区给出的关键补充 —— SLSA 的两句。**
> SLSA 明确写：**"SLSA is in the eye of the beholder: software consumers ultimately make their own
> SLSA determinations, though in practice they may delegate to some authority."**（`RPC-E3`）
> 且 **"each link in the software supply chain has its own, independent SLSA level — it is not
> transitive"**（**分级不传递**）。
> > **⚠ v2 更正**：v1 引了"可委托"这半句却推出"**不设权威源**"—— **引文内部就含它的反例**
> > （对方指出，我确认）。**正确读法**：SLSA 要的是「**判定权归消费方**」+「**不得继承**」，
> > **不要求**各自持表；**委托是消费方行使判定权的一种合法方式**。
> ⇒ **可委托；但"继承"不行。**
>
> **④ 它与本仓"双向零依赖"的设计，恰好使这种用法成立。**
> `tools/spec_runner/README.md`：**"与 Spec_Workflow 双向零依赖：本 runner 不内置其路径；
> 其校验器不调用本 runner"**（E2）—— **它自己就为"可被借用而不耦合"留了口子**。
>
> **⑤ 一条最强的外部印证（两处独立来源同结论）**：
> SLSA 2026-05 事件分析：**"A signed artifact is not necessarily a trustworthy one."**
> ⇒ 与 NS 事件的 **"Lean 通过 ≠ 问题被解决"**（T-4）**完全同构**。
> ⇒ **"有证据"与"证据可信"是两件事** —— 这正是 D7 必须把证据强度做成字典的理由。

---

## 1. 先把问题问准：这里"基准"可能指五种东西

| # | "基准"的含义 | 若成立，意味着什么 |
|---|---|---|
| **K-1** | **流程基准** | D6/D7 阶段的 agent 工作流**按它的 10 步 × 5 阶段走** |
| **K-2** | **协议基准** | D6/D7 的**信封/状态机/红线**以它的六相协议为准 |
| **K-3** | **词表基准** | 证据强度、缺陷严重度、状态词**以它的词表为准**（U-2） |
| **K-4** | **门禁实现基准** | D6/D7 的**机械门禁形态**（声明 vs 真值 / P1-P3 / selftest）照它写 |
| **K-5** | **权威源基准** | **它说了算**，其他仓库/项目以它为准并跟随（ADR-0006 的范式） |

> **⚠ 这五种必须分开答**：混在一起会得出"要么全接受、要么全拒绝"的结论，而实测是**分裂的**。

---

## 2. 判定矩阵（逐项给证据）

| 候选 | 判定 | 理由（摘要） | 依据 |
|---|---|---|---|
| **K-1 流程基准** | **◐ 有条件** | 它的流程是**"单人开发者 + LLM Agent"的文档流程**（README 首行自陈），**不是跨站派发流程**；且它自己把"每 agent 嵌套微工作流"**判负**。可作**项目侧工作流**的基准，**不可作 D6/D7 派发层的基准** | §3.2 · §4.2 |
| **K-2 协议基准** | **◐ 有条件** | 六相 + 三信封**字段级对照：约 1/3 本机群已有实现（可对齐）、约 2/3 是它单方面提出**；且其 `status: in-review`、**"§10 协议未实测"**、**"四端点全部不可达"** ⇒ **只能作"设计输入"，不能作"规范源"** | §3.3 |
| **K-3 词表基准** | **✅ 可以，且应当** | 九项目中**只有它同时提供"证据强度分级 + 可重放性分级 + 覆盖度 + 状态词表"四件**，且**六条规则逐条登记"来源事故/失效条件/拦截记录"** ⇒ 这是 `U-2` 唯一现成的输入 | §3.4 |
| **K-4 门禁实现基准** | **✅ 可以（作形态参照）** | 三校验器的 **"声明 vs 机械重数" + P1/P2/P3 + `--selftest` 内置反例 fixture** 形态，正是本仓 `D6-P1` 该学的；**但不可搬运代码**（作用域/路径全绑本仓） | §3.5 |
| **K-5 权威源基准** | **◐ 可以委托，但不得继承**（**v2 改判**，原判"❌ 必须拒绝"） | ① **有成功先例**：ADR-0006 的指针封堵已执行、回流通道已成功用过一次（v2 核验）；② SLSA **明确允许委托**（**"may delegate to some authority"**），故"委托"本身不违范式；③ 但 SLSA **not transitive** ⇒ **下游副本的符合性不可继承，须逐方重新确立** | §3.1 · §5.1 · §8 |

**⇒ 一句话**：**`Spec_Workflow` 可以作 D6/D7 的"词典"、"形态参照"，乃至"（显式委托的）权威来源"；
但不能作"宪法"** —— 因为**符合性不可继承**，且**无论选哪条路径，机械 drift check 都不可省**。

---

## 3. 它是什么（事实基线，E2）

### 3.1 自我定位与"权威性"的论证方式

| 项 | 事实 | 出处（E2） |
|---|---|---|
| 自我定位 | **"纯文档型方法论：无源代码、无构建系统、无运行时"**；服务对象是**"单人开发者 + LLM Agent"** | `README.md:9` |
| 目标 | **"最大限度抑制 LLM 生成内容中的幻觉与形式化审查表演"** | `README.md:9` |
| 仓库性质 | **"方法论文档仓库为体、最小工具层为用"**（3 校验器 + 5 hook + 控制台生成器 + spec_runner 薄壳） | `CODE_WIKI.md:6` |
| **权威性怎么论证** | **三条**：① **实测样本数 + 复发次数**（M7 账本：样本 ①-㉞、**形态 II 复发 76 处**）；② **每条规则登记"来源事故 + 失效条件 + 拦截记录"**（RULE-1~6 逐条）；③ **工具化**（"把事后审计发现**前移为提交瞬间拦截**"） | `README.md:11,43`；`M7_EVIDENCE_LOG.md:85,87`；`SPEC_PROCESS.md:337-348` |
| **未找到** | **任何"本仓是某种标准/基准"的对外声明**；也没有**"另一个仓库可自行声明为准"的判定规则** | — |

**⇒ 含义**：它的权威性是**内部治理级**（本仓内谁是唯一真值源），**不是对外承认级**。
`ADR-0006` 只定义了**三条失效条件（何时重审该 ADR）**，没有定义"别仓如何取得权威地位"。

### 3.2 流程定义（10 步 × 5 阶段）

| 阶段 | 步 | 产出 |
|---|---|---|
| 调研 | 1 → **2 Review** | `spec/<feature>/RESEARCH.md` |
| 设计 | 3 → **4 Review** | `DESIGN.md` |
| 实施 | 5 → **6 Review** | `IMPLEMENTATION.md` |
| 验收 | 7 → **8 Review** | `CHECKLIST.md` |
| 实现 | 9 TDD → **10 ADD 审计** | P1 清零才算完成 |

- **"每个偶数步是 Review 门禁"** 的原文在 `README.md:29` / `AGENTS.md:12`；
  **但 `SPEC_PROCESS.md` 正文没有这句**（用分节表达）。
- **★ 真正带"阻断语义"的门禁只有 Step 2 一个**（v1.4 新增，ADR-0008 D4，四条 (a)-(d)：
  FALSIFIED 已改写 / CONFLICT·STEP_GAP_OPEN 已仲裁 / 阻断性断言双源 / 假设区已转 A/B）。
  其余 Step 4/6/8 **仍是无阻断力的 checklist**。
- **ADR-0008 的核心判断（极有价值的一句）**：
  > **"checklist 是建议性（跳过无流程后果），门禁是阻断性（不满足不能进 Step 3）。
  > M6 实证的失效不是『缺少检查项』——五项 checklist 全部打勾照样漏——而是『检查项无阻断力』。"**

**⇒ 对 D6/D7 的直接含义**：**"打勾"与"阻断"必须分开设计**。
本仓 `inbox` 的 `40_state` 与门禁体系**天然是阻断式的**（比它更靠前），但**"清单化验收"的诱惑真实存在**
（`D:\Paper` 的 `checklist.md` 就出现了"绝大多数勾选框为未勾选"的设计态清单）。

### 3.3 六相协议 × 本机群：逐字段对照（**约 1/3 可对齐，2/3 是它单方面提出**）

| 信封 | 字段 | 本机群 | 说明 |
|---|---|---|---|
| **TaskContract** | `task_id` · 任务描述 · `accept[]` · `timeout_s` · `sensitivity` · `readonly` | **✅ 有** | 任务卡 front-matter 已全含 |
| | `golden{ref, checksum}` | **◐ 部分** | 有 `.golden/` + `GOLDEN_TAMPERED`，但**不在信封里**，是主控侧目录 + run.json 落值 |
| | `inputs{ref, digest}` | **◐ 部分** | 有 `card{path,sha256,bytes,front_matter}` + `attach[].sha256` + `prompt_sha256`（**注入物哈希**，非"输入快照"） |
| | `accept[].criteria_hash`（**P0 固化**） | **❌ 无** | 判据"天然先于派发"但**无哈希承诺** |
| | `evidence_budget{anchors, tool_calls}` | **❌ 无** | 它自己也承认**"无既有经验值可依"** |
| | 统一 `constraints`（禁止项） | **❌ 无** | 由 `sensitivity`/`readonly`/`audit` 三字段分散承载 |
| **RunReport** | `exit_code` · `usage` · `content_digest` | **✅ 有** | `.agent-run.json` |
| | **无 verdict 字段** | **✅ 同构** | 本机群"模型不自我盖章"；`review.json` **不写 verdict** |
| | `decisions[]`（八字段）· `evidence[]`（E1–E4 锚点） | **❌ 无** | **本仓有**（`DECISION_RECORD_CONTRACT`），本机群没有 |
| | `attempt` · `artifact.size` · `inputs_digest` | **❌ 无** | — |
| **Verdict** | `verdict` / `phase` / `l1_results[]` / `l2_marks[]` / `redispatch` | **❌ 无** | **对应本仓 `O-24 断点①`**："产出→ledger 后**无机器复核门**" |
| **不变量** | I-3 完成信号权在主控站 · I-6 fail-closed | **✅ 同构** | accept 门控独立于 agent 退出码；`GOLDEN_TAMPERED → exit 9` |
| | I-1 单写者（**事件流只有主控站可写**）· I-4 证据锚点化 | **❌ 无** | 本机群是 flock 锁，**无流级单写者、无签名身份层** |

**⇒ 三条结论**：
1. **它提出的"信封"里，本机群已经天然满足的恰好是最关键的两条**（不写 verdict / fail-closed）；
2. **它新增的部分（criteria_hash / inputs 快照 / evidence_budget / decisions[] / evidence[] / Verdict 结构）
   是本机群"缺什么"的清单** —— 与 `O-24`、`O-16` 高度重合，**不是新需求，是把旧缺口写成了 schema**；
3. **协议未实测**（自陈 `status: in-review`、**"§10 协议未实测"**、
   **"四端点当前全部不可达（2026-09-10 实测）"**）⇒ **零联调实证**。

### 3.4 词表（K-3 的支撑）—— 九项目里唯一的"四件套"

| 分级 | 取值 | 用途 |
|---|---|---|
| **断言证据分类** | `A 事实类` / `B 推断类` / `C 判断类`（+ `[单源-待二核]`） | 调研/审计 agent |
| **可重放性** | `E1 可重放命令` / `E2 运行时脚本` / `E3 静态读码行号（须绑 commit hash）` / `E4 盲区扫描` / `E5 推测（**禁止出现在审计结论中**）` | 审计报告 |
| **审计状态词表**（**固定，不得自造**） | `FALSIFIED` / `SURVIVED` / `CONFLICT` / `STEP_GAP_CLOSED` / `STEP_GAP_OPEN` / `UNCERTAIN` / `PENDING` / `NO_PROBE` | 流程记录 |
| **问题严重度** | `P1 阻断验收` / `P2 应修` / `P3 提示`；另有 **P0 审计项**（=不变式/隔离边界类，**须全量执行**，与严重度不同轴） | 验收 |
| **错误形态学 + 危害等级** | `I 无据断言 → 极高` / `II 弱记忆填充 → 中` / `III 把正确事实标成幻觉 → 最高` | 缺陷归因 |
| **纪律** | **"无标注句子不得含可验证事实"** · **"E5 禁止出现在审计结论中"** | 强制 |

**⇒ 这是 `U-2` 冲突清单（`L1/L2/L3` 有 5 种义、`A/B/C` 有 3 种义）里，唯一"自带失效条件"的一套词。**

### 3.5 门禁实现形态（K-4 的支撑）

| 形态 | 具体做法 | 出处（E2） |
|---|---|---|
| **声明 vs 真值** | `declared` 七键（**P1 阻断**）· `pattern 命中值 vs 真值`（**P2**）· `facade prose vs baseline`（**P3 非阻断**）· `快照滞后`（**P3**） | `repo_stats.py:635-643,518-586` |
| **三级严重度 + gap 三元组** | 报错带 **"意图(声明) X → 证据(重数) Y → 缺口"** | `repo_stats.py:641` |
| **零写通道** | "**对账器非重生成器——无 `--write`、无任何写通道（I-1）**，prose 位点永不代改，只报偏差" | `repo_stats.py:7-8` |
| **写守卫** | `m7_stats --write`：不可修复形态**拒绝写入** + 写后自检失败 **exit 2 且不落盘** | `m7_stats.py:522-560` |
| **内置反例 fixture** | `--selftest`：`dc_validator` **13** 项 / `repo_stats` **27** 项 + **I-1 只读断言（前后字节不变）** / `m7_stats` **16** 项 | `dc_validator.py:322-419` 等 |
| **计数不得手填** | **"计数由 expect 调用自增，不手填"**（R7 同构） | `dc_validator.py:322-419` |
| **诚实边界** | **"`--no-verify` 旁路不可根除 = git 官方文档明示 + 实测 12 种绕过向量全放行 → 本地 hook 是『诚实护栏』非绝对强制"** | `CODE_WIKI.md:734` |

**⇒ 这套形态**是本仓 `D6-P1`（"生成物清单 + `--check`"）与 `P3`（出站断言）**最直接可抄的参照**，
尤其三条：**gap 三元组**、**零写通道（对账器不代改）**、**fixture 内建 + 计数不手填**。

---

## 4. 边界与限制（**v2：4.1 由"证伪"改写为"可成但有条件"**）

> **⚠ v2 结构性更正**：v1 把本节标题写作"为什么不能当『宪法』（四类不利证据）"，
> 其中 **4.1 的"先例失败"已被撤回**（§3.1 改写）。**保留的实际限制是三条**：
> 4.2 体裁不匹配 · 4.3 自身缺口 · 4.4 P-b 判负。

### 4.1 权威源范式：**跑通了，但执行不完整**（K-5，v2 改写）

`ADR-0006` 决策原文（`RPC-E2`）：

> **方案 B：Spec_Workflow 仓库为权威源。**
> ① 吸收增量（版本起跳 v1.2）② DIS-007 对齐 ③ **指针封堵**：Cpp_Hub 侧两文件头部各加一行
> "权威源已迁移至 Spec_Workflow 仓库" ④ **回流通道**：…（**人工纪律，无自动同步**）

**实际后果（v2：逐条核 ADR-0006 修订历史 + 我方亲读被引文件）**：

| 项 | 结果 | 核验 |
|---|---|---|
| **指针封堵** | **已执行**（2026-08-17，P-001）：Cpp_Hub 侧 AEF 头部落指针，提交 `96edc5c`，`grep` 双命中 | [ADR-0006 L134](file:///f:/Spec_Workflow/adr/ADR-0006-assertion-framework-dual-copy-authority.md#L134) |
| **回流通道** | **已首次批量使用成功**（2026-08-17，P-002）→ 框架 v1.3/v1.4 + SPEC_PROCESS v1.4（commits `8ea38bf..8a4bfda`，**已推送**） | [L133](file:///f:/Spec_Workflow/adr/ADR-0006-assertion-framework-dual-copy-authority.md#L133) |
| **失效条件** | 三条，含「回流频度 **<1 次/季度** → 通道名存实亡，重审是否退回方案 A」；且 L133 明记「**观测起点自此计**」 | [L121-125](file:///f:/Spec_Workflow/adr/ADR-0006-assertion-framework-dual-copy-authority.md#L121-L125) |
| 方案 A / C 否决理由 | A："与本仓库自包含化、跨项目方法论权威的定位冲突"；C："**放弃治理等于接受未来更大的合并成本**" | [L70-80](file:///f:/Spec_Workflow/adr/ADR-0006-assertion-framework-dual-copy-authority.md#L70-L80) |
| **⚠ 执行缺陷**（**对方主动指出，我方独立核验成立**） | ① **封堵只做了一半**：`DIS-007` 按 Cpp_Hub `.gitignore` L82 本就不入库 ⇒ **指针仅本地生效**（我方**亲读** `F:\Cpp_Hub\.gitignore` 确认 L82 = `docs/discoveries/`）② **提交未推送**（Cpp_Hub `main ahead 11`）⇒ **对外不可见** ③ **无自动同步、无机械 drift check** | [L134](file:///f:/Spec_Workflow/adr/ADR-0006-assertion-framework-dual-copy-authority.md#L134) · [.gitignore L82](file:///f:/Cpp_Hub/.gitignore#L82) |

**⇒ v2 判断（撤回 v1 的"用治理的名义实现了方案 C 的实质"）**：
**方案 B 达成了它的目标** —— 权威明确、一份被标为历史快照、回流把新发现带了回来，
"哪个是真的"**有答案**。**真正的缺口不是"权威拓扑错"，而是"执行不完整 + 缺机械判据"**：
① 封堵半侧本地化 ⇒ **不持久**；② 未推送 ⇒ **对外不可见**；③ **"人工纪律"无机械检查** ⇒ 必然漂移。
**⇒ 三条都可修，且都不要求更换权威拓扑**（**对方诊断更准，我方接受**）。

> **⚠ 连带撤回**：v1 写"方案 C 被以『未来合并成本』否决，**但方案 B 的实际运行结果就是方案 C 的实质**"。
> **该判断错误**：**存在双份 ≠ 双份失控**；两种方案的实质差别在于「**"哪个是真的"有没有答案**」——
> 而这里**有答案**（权威份 + 指针 + 历史快照）。**撤回。**

### 4.2 体裁不匹配：它是"单人文档流程"，D6/D7 是"跨站派发 + 复核"

| 维度 | `Spec_Workflow` | D6/D7 |
|---|---|---|
| 主体 | **单人开发者 + LLM** | **≥2 主体**（产出方 + 复核方），可跨站 |
| 运行 | **无运行时**（自陈） | 有运行时（agent-cli / SSH / 锁 / 槽位） |
| 并发 | **单写者/单进程**（`SPEC_RUNNER_DESIGN` **明列"多 worker / 水平扩展"为非目标**） | **跨站各 1 并发**（`O-18` 铁律） |
| 写权 | **I-1 单写者：事件流只有主控站可写** | 已实现 flock 双层锁，**无流级单写者** |
| 触发 | **pre-commit 本地钩子** | **派发 → 站上 headless 执行 → 回收** |

**⇒ 结论**：**把它的 10 步流程当作 D6/D7 派发层的规范，等于拿"单人写作规范"当"分布式编排规范"。**

### 4.3 它自己承认的缺口，正是 D7-G 要补的

| 缺口（它自陈，E2） | 对应本文件的 |
|---|---|
| **"依赖 DAG、健康监控、崩溃恢复『普遍空缺』"** | **U-3（依赖边）· U-4（失效传播）** |
| **"`review--peer` 未实现"** | **D7 主体** |
| **"coordinator 模式未投产"** | D7-E 编排层 |
| **"§10 协议未实测"·"四端点全部不可达"** | **零联调实证** |
| **无 `schema_version` / 无 `MANIFEST` / 无内容寻址**（三者**均未找到**，唯一 `sha256` 用于**外部二进制**） | **U-1** |

**⇒ 它的缺口清单与 D7-G 的接口面清单几乎一一对应** ⇒ **它是"同路人"，不是"上位标准"。**

### 4.4 "每 agent 嵌套微工作流"已被它自己判负（对 K-1 的强约束）

`RESEARCH.md` 的 P-b 裁定（E2）**判负**，四项代价全数命中：

| 代价 | 数据 |
|---|---|
| **复利误差** | **`p^N`：0.95^10 = 59.9%；5 agent × 80% = 32.8%**；"Agentic Telephone Game" 每跳 ~92% 保真 ⇒ **4 轮降至 ~72%，且输出仍"读起来很流畅"** |
| **MAST 失败分类学** | 1,600+ 轨迹 / 7 框架 ⇒ **FC1 规范问题 41.77%** / FC2 智能体间错配 36.94% / **FC3 任务验证 21.30%**；整体失败率 **41%–86.7%** |
| **四重硬约束** | Interaction Tax（**多样性被擦除**）· Belief Entrenchment（**辩论强化偏误**）· Spiral of Silence（**少数派被淹没**）· Co-Failure Ceiling（**增益上限由共同错误率 β 决定**） |
| **递归退化** | opencode #18100 实证：**depth 2–18 全是 `explore→explore` 空转**，直到 depth 19 才真正 `grep` 一次 |

**⇒ 对 D6/D7 的直接约束**：**不要设计"agent 内嵌套工作流"**；且 **"多了 agent 就更好"已被实证否定**，
**最大失败类别是"规范"（41.77%），先于任何 agent 发言就注定失败** —— 这**反向支持**本文件的
"先把判据/契约做对（D7-G），再谈编排（D7-E）"的顺序。

---

## 5. 社区案例：三种"基准"范式，我们该选哪种

### 5.1 ★ SLSA —— 与 ADR-0006 相反的范式（**最重要的外部依据**）

| SLSA 的机制 | 原文（E3） | 对我们的含义 |
|---|---|---|
| **消费方判定** | **"SLSA is in the eye of the beholder: software consumers ultimately make their own SLSA determinations, though in practice they may delegate to some authority."** | **基准不由生产方宣布** ⇒ **拒绝 K-5** |
| **分级不传递** | **"each link in the software supply chain has its own, independent SLSA level — in other words, it is not transitive"** | **每个项目各自评级 + 一张映射表** ⇒ 正是 `U-2` 的形态 |
| **可扩展而不失效** | 用 **tracks + levels**：**"Tracks also allow the SLSA spec to evolve: we can add more tracks without invalidating previous levels."** | `U-2` 加新方言**不得使旧档位失效** |
| **自我限界** | **"SLSA alone is not sufficient to determine if an artifact is 'safe'"**；只覆盖"**those that can be fully automated**" | 基准只管**可自动化的那一部分** ⇒ 本仓 `quick`/`full` 分层同源 |
| **★ signed ≠ trustworthy** | 2026-05 事件：恶意包**"carried cryptographically valid attestations… indistinguishable from the real thing"**，因为**构建平台不满足 L3 隔离**；结论：**"A signed artifact is not necessarily a trustworthy one."** | **与 NS 事件的 T-4 同构** ⇒ **D7 必须把"证据强度"与"证据存在"分开**（`U-5`） |
| **L3 三条隔离 MUST** | ① 不可能跨构建污染 cache（cache poisoning）② 不可能访问构建平台密钥 ③ 不可能持久化影响后续构建 | 可作为**本机群"跨站派发"的隔离判据参照**（尤其"前一次派发不得影响后一次"） |

**⇒ 结论（v2 修正）**：**D6/D7 应采用"消费方判定"范式**：
`Spec_Workflow` 提供**词表与形态**（**可**作单一来源），**D6/D7 持有符合性判定与偏差记录**。
> **⚠ v2 更正**：v1 写"…**不设"权威源"**"，**表述过强，已撤回** —— SLSA 明文允许委托。
> **修正后的正确形式是三段式**：**共享词表（集中：单一来源）+ 本地判定（分布：逐方显式 + 偏差记录）+ 机械 drift check（可检出）**。

### 5.2 GitHub Spec Kit —— SDD 已是事实标准（**证明"过程序"可作基准**）

| 事实（E3） | 对我们的含义 |
|---|---|
| 核心流程 **Specify → Plan → Tasks → Implement → Converge**；**"Each phase produces a Markdown artifact that feeds the next"** | 与 `Spec_Workflow` 的**四文档管道同构** ⇒ **我们这条路不是孤例，社区主流同形** |
| 生态规模：**130K+ stars / 270+ contributors / 38 integrations / 157 extensions / 33 presets** | **"过程"确实可以被当作可复用基准**（K-1/K-4 成立的外部证据） |
| **Canon**：**"baseline-driven workflows (spec-first, code-first, spec-drift)"** | ★ **"baseline-driven" 与 "spec-drift" 是社区已有词** ⇒ 我们的 `U-2` 应直接采用 **drift（漂移）** 这个术语 |
| **AIDE**（7-step AI-driven engineering lifecycle）· **MAQA**（multi-agent orchestration **with quality assurance gates**） | 社区已有"**多 agent 编排 + 质量门**"的成体流程 ⇒ `D7-E` 可对标 |
| **38 integrations**（含 Kiro、Claude、Codex、Copilot）**"Switch freely between agents… No lock-in"** | **不锁定执行器**是本机群既有立场（对应 §4.4 的"外壳与模型无关"） |

### 5.3 AWS Kiro —— 产品化的 SDD，两条可直接借的纪律

| 纪律（E3） | 对我们的含义 |
|---|---|
| **两种工作流二选一，且"不能中途切换"**：**"No, you must choose a workflow when creating the spec. If you need to change approaches, create a new Feature Spec"** | **与三条红线之"判据与 golden 哈希在 P0 固化"同义** ⇒ 本机群已同构 |
| **Bugfix Spec 显式捕获"不变行为"**：**"WHEN [condition] THEN the system SHALL CONTINUE TO [existing behavior]"** | 可直接用于本机群 `D6-P3 出站断言`的**反向用例模板**（"不该变的没变"） |
| 与 `Spec_Workflow` 的差异 | Kiro/Spec Kit 都**内置了运行时**；`Spec_Workflow` **没有**（自陈）⇒ 进一步支持 §4.2 的体裁判断 |

---

## 6. 建议的落地形态：把 Spec_Workflow **拆成三份可移植制品 + 一份"可选但须显式"**（v2 改）

| # | 制品 | 内容 | 落到哪 | 形态 |
|---|---|---|---|---|
| **S-1** | **词表**（✅ 移植） | `A/B/C` + `E1–E5` + 固定状态词表 + `P1/P2/P3` + `P0 审计项` | **`U-2` 字典的"方言之一"** | 作为**映射表的一列**；**词表可单一来源，符合性判定不可继承**（§4.1 · §8） |
| **S-2** | **门禁形态**（✅ 移植） | gap 三元组 · 零写通道 · `--selftest` fixture · 计数不手填 · 三级严重度 | **`D6-P1` / `P3` 的实现参照** | **照形态重写**（不搬代码，作用域不同） |
| **S-3** | **权限与红线**（✅ 移植） | 三条红线 + 单向权限（只标记不改写）+ 不得自审 + `RunReport 无 verdict` | **`D7-D` 权限模型** | 与 `Auto_Prover` 的 mission 三角色、`Cpp_Hub` 的双盲**三源互证** |
| **S-4** | **权威源身份**（**◐ v2 由"❌ 拒绝"改判为"可选，但须显式 + 必配机械判据"**） | ADR-0006 式"指定一处为准 + 指针封堵 + 回流通道" | 若采用：写成**显式委托声明**，并**补齐它缺的第三段** | ① SLSA **允许委托**（**"may delegate to some authority"**）② **ADR-0006 有成功先例**（§4.1）③ **符合性不得继承**（`not transitive`）④ **无论委托与否，机械 drift check 是共同前提** |

**⇒ 三条实施纪律（v2 第 1 条改写）**：

1. **用"映射 + 本地判定 + 机械漂移检查"代替"跟随"**：
   - **共享词表（集中）** —— 单一来源，避免"两实现同错"（即 `Spec_Workflow` 自己的 **A-33 / I-10 语义同源**教训，与 §8 的对方论证一致）；
   - **本地判定（分布）** —— D6/D7 侧产出**方言对照表**并**逐项声明符合/偏离**；
   - **机械 drift check（可检出）** —— **映射表与版本行的一致性本身要被门禁校验**（源词表变了下游要红）。
   > 这正是 v1 缺的那一段，也**正是 ADR-0006 缺的第三段**：它只有"指针 + 回流 + 人工纪律"，**没有机械判据**。
2. **借形态不借代码**：它的校验器写入端全绑本仓路径（且它与本仓"**双向零依赖**"），
   ⇒ **只借"形状"**（gap 三元组 / 零写通道 / selftest fixture），**不引入依赖**。
3. **凡"未实测"的，一律标为候选而非依据**：六相协议 `status: in-review` + **四端点实测不可达** +
   **"§10 协议未实测"** ⇒ 它只能进 **`D7` 的设计输入**，**不能进任何"已具备"清单**。

---

## 7. 待 Scott 裁定

| # | 事项 | 建议 | 依据 |
|---|---|---|---|
| 1 | **采用哪条路径**（**v2 改问法** —— v1 问"是否采用消费方判定范式"**预设了答案**） | **两条都可，但必须显式**：① **委托**（以 `Spec_Workflow` 为准 + 指针对齐 + 回流 + **补机械 drift check**）—— **有成功先例，非空谈**；② **自判**（D6/D7 自持符合性判定 + 偏差记录）—— SLSA 允许。**共同前提：机械 drift check 不可省** | §4.1 · §5.1 · §8 |
| 2 | **`Spec_Workflow` 的定位表述** | 建议写作 **"词表与形态的来源（source of vocabulary & form）；符合性判定权在消费方"**（**v2 改**：v1 写"非规范源"**过强** —— 词表本身**可以**是单一来源） | §2 · §6 |
| 3 | **是否移植 S-1 词表为 `U-2` 的方言之一** | **建议移植**，但**只作映射表的一列**，不强推各项目改名 | §3.4 · §6 |
| 4 | **是否移植 S-2 门禁形态到 `D6-P1`/`P3`** | **建议移植三条**：gap 三元组 · 零写通道 · selftest fixture + 计数不手填 | §3.5 |
| 5 | **是否移植 S-3 权限红线到 `D7-D`** | **建议移植**（与 `Auto_Prover` 三角色、`Cpp_Hub` 双盲三源互证） | §3.3 · §6 |
| 6 | **六相协议如何处置**（`in-review` + 未实测 + 端点不可达） | 建议**保留为 `D7-A` 的设计输入**，**同时登记"未实测"状态**，不得进"已具备"清单 | §3.3 · §4.3 |
| 7 | **是否把"每 agent 嵌套微工作流"写进非范围**（它自己判负） | **建议写进非范围** —— 四项代价（`p^N` / MAST FC1 41.77% / 四重硬约束 / 递归退化）全数命中 | §4.4 |
| 8 | **是否新增术语 `drift`（漂移）**（社区已有：`spec-drift`） | 建议采用 —— `U-2` 需要它描述"源词表变了而下游没跟" | §5.2 |
| 9 | **是否把"检查项无阻断力"立为一条独立教训**（ADR-0008 的核心判断） | **建议立** —— "五项 checklist 全部打勾照样漏" | §3.2 |
| 10 | **是否对 `F:\Spec_Workflow` 做一次"端点实测"以取得联调证据** | 建议**在 D7-A 之前做**（它自陈四端点 2026-09-10 全不可达，此后无更新） | §4.3 |

---

## 8. ★ 跨仓复核实录（v2 新增）—— 本文件自身就是 D7 的第一个真实案例

> **背景**：本文件 v1 完成后被 `Spec_Workflow` 侧**独立主体**（另一会话）复核。
> 对方按其自身纪律（**"先按本仓纪律核事实（声明=重数），再评推理"**）做了四件事：
> ① 读 `ADR-0006` 原文；② 读 `ASSERTION_EVIDENCE_FRAMEWORK`；③ **联网核验本文件引用的 SLSA 两句**；
> ④ 逐条指出我方问题。

### 8.1 对方提出的更正（**我方读原文核验后，逐条结论**）

| # | 对方的更正 | 我方核验 | 结论 |
|---|---|---|---|
| 1 | "**它自己的先例就失败了**"不成立：指针封堵**已执行**、回流通道**已成功用过一次** | 与 [ADR-0006 L133-134](file:///f:/Spec_Workflow/adr/ADR-0006-assertion-framework-dual-copy-authority.md#L133-L134) 逐字核对 | **成立 ⇒ 我方撤回该措辞** |
| 2 | v1 引了 SLSA "**may delegate to some authority**" 却推出"**不设权威源**" —— **引文内部就含反例** | 复核自引文 | **成立 ⇒ 我方撤回"不设权威源"** |
| 3 | "**指针封堵只做了一半**"：`DIS-007` 按 Cpp_Hub `.gitignore` L82 本就不入库 ⇒ 指针**仅本地生效**；且 `main ahead 11` **未推送** | **我方亲读 [F:\Cpp_Hub\.gitignore](file:///f:/Cpp_Hub/.gitignore#L82) 独立确认 L82 = `docs/discoveries/`** | **成立，且比我方原证据更硬** ⇒ 已采纳为 §4.1 的"执行缺陷" |
| 4 | **归因跳跃**：漂移根因是"**跨仓库无同步机制**"（ADR-0006 §4 明写），**不是权威拓扑的错** | [L55-57](file:///f:/Spec_Workflow/adr/ADR-0006-assertion-framework-dual-copy-authority.md#L55-L57) | **成立** |
| 5 | 失效条件**自带重审触发器**（"回流频度 <1 次/季度"），v1 未先检验它 | [L121-125](file:///f:/Spec_Workflow/adr/ADR-0006-assertion-framework-dual-copy-authority.md#L121-L125) | **成立**；精确化见 §8.2 |
| 6 | "**这是方案 C 的近亲**" | — | **不成立（类比越界）**：方案 C 的对象是"**同一份规范的两个副本**"，本文件讨论的是"**消费方 ↔ 规范来源**"，**对象不同** |
| 7 | 本文件 `E1–E5` 与其 `E1–E5` 同名不同义，"E2 标错" | v1 自带刻度定义（`E2`=子代理实读） | **对方是范畴错误**（用其刻度度量我方文档）；**但根因在我方未给命名空间** ⇒ **已改 `RPC-E1..E5`**，记为 `U-2` 的**第一例真实符号冲突** |
| 8 | "`D6/D7` **指代不明**" | — | **成立**：我方未给命名空间 ⇒ **已在文件头显式定义**，记为同一病的**第二例** |

### 8.2 我方对第 5 条的精确化（比对方的说法更准）

对方的失效条件是「回流频度 **<1 次/季度**」，而 [L133](file:///f:/Spec_Workflow/adr/ADR-0006-assertion-framework-dual-copy-authority.md#L133) 明记
「**观测起点自此计**」（2026-08-17）⇒ **该触发器最早 2026-11-17 才可判定**，在 2026-09-23 **做不了**。
更关键：**它测的是「通道存亡」，测不到「下游只能继承符合性声明、不能自判并记偏差」** —— **两个不同命题**。
⇒ **即使回流频度达标、通道健在，本文件 K-5 要治的那个缺口依然存在。**

### 8.3 ★ 本次交互实测到的 D7 设计要素（**本文件最有价值的副产品**）

| D7 设计要素 | 本次实测表现 |
|---|---|
| **独立执行主体** | 对等主体**找到了我方引文的自相矛盾**（第 2 条）—— 同源自审做不到 |
| **锚点化** | 双方全部用 `file:line`；对方给 ADR 行号，我方核到行 |
| **外部引文核验** | **对方核了 SLSA（逐字属实）· 我方核了 ADR-0006 与 `.gitignore`（属实）—— 互补而非重复** |
| **双向修正** | 对方接受"冻结 v1.1"成立；我方撤回 **2 处措辞 + 2 处判断** |
| **符号冲突** | **真实发生 2 例**（`E1–E5`、`D6`）—— `U-2` 从"我预言的"变成"**我亲历的**" |
| **双方一致的结论** | **真缺口 = 执行不完整 + 缺机械判据**（**不是"不该有权威源"**） |

**★ 一条修正上一轮结论的新发现**：`D7` 调研（合并稿）§4.4 曾论证"**异构是派发选择的结果**"。
本次案例补充**第二个正交维度**：**信息独立性** ——
**两个同族 agent（都是 LLM），因各自只读自己的仓库，仍产生了对等反证**。
⇒ **D7 的判据应同时写两条**：`judge.family ≠ producer.family`（**家族异构**）
**与** `judge.input ≠ producer.input`（**信息独立**，即"**盲写**"的机器化表述）。

### 8.4 对"要我把 S-4 写成 ADR-0006 修订草案吗"的答复

**答复：修订应由 `Spec_Workflow` 侧做；我方只出「偏差记录表」。**
理由：① **单写者原则**（其六相 `I-1`）—— 权威份的修订权在它那边；
② 这本身就是 **SLSA 范式的一次应用演示**：**规范来源做修订，消费方记录自己的符合性/偏差**，
而不是反过来让消费方去改权威源。
**我方可交付的**：`D:\RPC` 侧的**方言对照表 + 符合性声明 + 偏离清单**（随 `U-2` 落地产出）。

---

## 附 A：本次未覆盖 / 需补（诚实标注）

| # | 项 | 状态 |
|---|---|---|
| 1 | **`Spec_Workflow` 的 32 个 spec feature 目录逐个内容** | **未逐个读** —— 只读了 `distributed-agent` / `academic-writing-workflow` / `precommit-dc-validator` 等与本问题直接相关的 |
| 2 | **它 130K+ stars 类生态数据的时效性**（Spec Kit 侧） | E3 单源（官网），**未交叉验证** |
| 3 | **SLSA v1.2 的 `build-requirements` 正文** | 只读到 L3 隔离三条 MUST 的**引用版**，**未读规范原文** |
| 4 | **`in-toto` 的 attestation 格式细节** | **未查**（SLSA 引用它，本轮未展开） |
| 5 | **`Spec_Workflow` 六条 RULE 在各 feature 的**实际拦截记录**是否为空 | 只确认**机制存在**（"规则真实拦截一次违规时追加一条"），**未统计** |
| 6 | **三段式落地后，`D:\RPC` 侧的"符合性判定表/偏差清单"谁持有** | **未设计** —— 候选：`inventory/` 真值表扩展 / `rpc_check.py` 常量层；随 `U-2` 落地时专项设计 |
| 7 | **对方的复核意见未以"仓内制品"形式固化** | **待补** —— 我方拿到的是**转述文本**，非其仓的 Discovery/ADR 产物。若要把本次记为 `D7` 的"第一个真实案例"，**应由对方按其 `discoveries` 机制登记**（其仓有登记门槛：**"单发事件不登记，仅跨 feature/跨仓库复发的系统性模式入册"**）—— 这次**恰好符合**"跨仓库复发的系统性模式" |
| 8 | **ADR-0006 失效条件「回流频度 <1 次/季度」的实际判定** | **最早 2026-11-17 可判**（观测起点 2026-08-17，见 §8.2）——**在此之前任何"通道存亡"的结论都是提前判定** |

## 附 B：引用的一手来源（E3）

**Spec-Driven Development（社区主流）**
- [GitHub Spec Kit（SDD 核心流程 Specify→Plan→Tasks→Implement→Converge；Canon baseline-driven；157 extensions/38 integrations）](https://github.github.io/spec-kit/)
- [AWS Kiro 官网（spec-driven development / property-based tests / parallel agents）](https://kiro.dev/)
- [Kiro Docs · Specs 最佳实践（Requirements-First vs Design-First；工作流不可中途切换）](https://kiro.dev/docs/specs/best-practices/)
- [AWS 文档总览 · Kiro（spec-driven coding / agent hooks / steering files）](https://aws.amazon.com/es/documentation-overview/kiro/)
- [AWS for Industries：From spec to production（requirements.md / design.md / tasks.md 三件套）](https://aws.amazon.com/blogs/industries/from-spec-to-production-a-three-week-drug-discovery-agent-using-kiro/)

**SLSA（分级基准的范本）**
- [SLSA 官网（levels as a common language；four compliance levels）](https://slsa.dev/)
- [SLSA · Security levels（Build L0–L3；tracks 可扩展不使旧 level 失效；**not transitive**；**in the eye of the beholder**）](https://slsa.dev/spec/v1.0/levels)
- [SLSA · About（"common vocabulary"；"a set of incrementally adoptable guidelines, established by industry consensus"）](https://slsa.dev/spec/v1.0/about)
- [SLSA Blog：Mini Shai-Hulud — Where SLSA's Boundaries Fall（**"A signed artifact is not necessarily a trustworthy one."** + L3 隔离三条 MUST）](https://slsa.dev/blog/2026/05/mini-shai-hulud-what-slsa-can-and-cannot-do)

**被对方复核后我方亲读核验的仓内一手文件（v2 新增，`RPC-E1`）**
- [`F:\Spec_Workflow\adr\ADR-0006-assertion-framework-dual-copy-authority.md`](file:///f:/Spec_Workflow/adr/ADR-0006-assertion-framework-dual-copy-authority.md) ——
  元数据 [L13-22] · 差异对照 [L32-53] · **漂移根因 [L55-57]** · **决策（方案 B 四语义）[L59-66]** ·
  方案 A/C 否决理由 [L70-80] · 验证与**失效条件 [L102-125]** · **修订历史 [L127-134]**
- [`F:\Cpp_Hub\.gitignore` L82](file:///f:/Cpp_Hub/.gitignore#L82) —— 独立确认 `docs/discoveries/` 不入库
  ⇒ **`DIS-007` 的指针仅本地生效**（§8.1 第 3 条）

**本机群与被调研方（E1/E2）**
- `F:\Spec_Workflow`：`README.md` · `SPEC_PROCESS.md` · `CODE_WIKI.md` · `AGENTS.md` · `adr/ADR-0006`、`ADR-0007`、`ADR-0008` ·
  `docs/ASSERTION_EVIDENCE_FRAMEWORK.md` · `docs/FACT_CHECK_FRAMEWORK.md` · `docs/DECISION_RECORD_CONTRACT.md` ·
  `docs/M7_EVIDENCE_LOG.md` · `scripts/{dc_validator,repo_stats,m7_stats,step_enforce,console_gen}.py` ·
  `tools/spec_runner/` · `tools/arc/` · `spec/distributed-agent/DISTRIBUTED_AGENT_RESEARCH.md` · `spec/templates/`
- 本仓：[D7 调研（合并稿）](2026-09-23_D7调研_立项·机制·统一基座.md) · [ADR-0007](../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md) ·
  [inbox 受理区标准](../inbox/README.md) · [二次裁定取证](2026-09-23_二次裁定取证_证据与断言.md)
