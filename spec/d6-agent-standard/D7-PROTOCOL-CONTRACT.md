# D7 协议契约（六相 · 三信封 · 三红线）

> **定案稿**（`D7-P0-2` 的产出）：把 D7 的六相状态机、三种信封、三条设计红线**固定为契约**，
> 并**显式登记"未实测"**。
>
> **来源与可追溯性（如实标注）**：内容来自 [D7 调研（合并稿）§3.1](../../docs/2026-09-23_D7调研_立项·机制·统一基座.md)
> 的**出站版摘要**（登记为 `public`：`spec/d6-agent-standard/dogfood-cards/inputs/d7-p0-2-protocol-excerpt.md`），
> 经吃狗粮卡 `d7-p0-2-protocol-freeze` 定案（run `202609260832348857`，`exit=0`，ACCEPT 9/9）。
> ⚠ 摘要**不承载原文完整性**：摘要未给出的字段级定义，**一律登记为未实测**（见末节），**不补齐**。
>
> **硬要求**：**未经实测的东西不得写成"已具备"** —— 本契约的任何部分在落盘时**都还没有真实运行验证过**
> ⇒ 末节 `## 未实测登记` **必然非空**，且**不得**把该节内容搬进任何"已具备"清单。

---

## 1. 六相协议契约（定案稿）

| 相 | 谁 | 何时 | 产出信封 | 关键动作 |
|---|---|---|---|---|
| **P0 立契** | 主控站 | 任务创建时 | **TaskContract** | 写入 `task_id`、任务描述、**`accept[]`（判据 + `criteria_hash`）**、`golden{ref, checksum}`、`inputs{ref, digest}`、`evidence_budget{anchors, tool_calls}`、`constraints`（禁止项）、`timeout_s`、`sensitivity`、`readonly`；状态 `drafted → dispatched` |
| **P1 领取** | 工作站 | 收到 TaskContract 后 | —（仅状态迁移） | 读取契约，状态 `dispatched → claimed` |
| **P2 执行** | 工作站 | 领取后 | —（产出物就绪后进 P3） | 执行任务本体，**不自评、不写 verdict、不重派、不合并**；状态 `claimed → executing` |
| **P3 回收** | 工作站 → 主控站 | 执行结束 | **RunReport** | 工作站写出 `run_id`、`attempt`、`artifact{digest, size}`、`inputs_digest`、`exit_code`、`decisions[]`（八字段）、`evidence[]`（锚点）、`usage`，**无 verdict 字段**；状态 `executing → collected` |
| **P4a 机械验证** | 主控站（自动化） | 收到 RunReport 后 | —（写 Verdict 的 `l1_results[]`） | 运行 L1 机械门；状态 `collected → mech_verified` |
| **P4b 语义复核**（**可选**） | 主控站（人工/模型复核） | P4a 通过后 | —（写 Verdict 的 `l2_marks[]`，可选） | 运行 L2 语义门，**L2 无权改写 L1 结果**；状态 `mech_verified → sem_verified` |
| **P5 裁决登记** | 主控站 | 验证链结束 | **Verdict**（**仅登记**） | 写入 `verdict`（exit code）、`phase`、`l1_results[]`、`l2_marks[]`（可选）、`redispatch?`、`recorded_at + seq`；状态 `sem_verified → accepted \| rejected` |

**状态名序列**：`drafted → dispatched → claimed → executing → collected → mech_verified →（可选）sem_verified → accepted | rejected`

### 1.1 三种信封（字段级）

- **TaskContract**（主控站 → 工作站，P0）：`task_id` / 任务描述 / **`accept[]`（判据 + `criteria_hash`）** /
  `golden{ref, checksum}` / `inputs{ref, digest}` / `evidence_budget{anchors, tool_calls}` /
  `constraints`（禁止项） / `timeout_s` / `sensitivity` / `readonly`
- **RunReport**（工作站 → 主控站，P3）：`run_id` / `attempt` / `artifact{digest, size}` / `inputs_digest` /
  `exit_code` / `decisions[]`（八字段） / `evidence[]`（锚点） / `usage` / **无 verdict 字段**
- **Verdict**（主控站，P5，**仅登记**）：`verdict`（exit code） / `phase` / `l1_results[]` /
  `l2_marks[]`（可选） / `redispatch?` / `recorded_at + seq`

> ★ **`RunReport` 刻意不含 verdict 字段** —— **产出方不得自评**。

> ★ **A 段（2026-10-01）落定的三处"摘要未给、但机判必需"的键名**（**只钉键名，不钉语义**）：
> ① `任务描述` ⇒ 键名 **`task_desc`**；② `accept[]` 每项 ⇒ **`criteria` + `criteria_hash`**
> （`criteria_hash` 是摘要逐字给出的；`criteria` 只是"判据"的键名）；
> ③ `recorded_at + seq` ⇒ **两个键** `recorded_at` / `seq`。
> ⚠ 钉它们是为了让"**判据与 golden 哈希在 P0 固化**"（红线 3）**可机判**；
> 摘要**未给内部结构**的键（`constraints` / `decisions[]` 八字段 / `sensitivity` / `redispatch?`）
> **一律不钉、不补**（见 §1.5）。
>
> ★★ **`verdict` 词义冲突的裁定（A 段，2026-10-01）** —— 本契约定：**同一个词、两个含义，靠信封与值类型分离**：
> · **本信封（`Verdict`）的 `verdict` = exit code（整数）**（照摘要逐字，**不改名**）；
> · **`review.json` 的 `verdict` = 判官四值**（`accept` / `revise` / `reject` / `uncertain`，见
>   `ops/station-bin/review/judge-prompt.tmpl`）—— **不属本信封**。
> · ⇒ **机判切分**：`Verdict.verdict` **不是整数**（如写成判官四值 / 布尔）⇒ **拒**（`validate_envelope`）。
> ⚠ 为什么**不改名**（如改叫 `exit_verdict`）：本契约把 `Verdict 字段集`列为**逐字采纳**（见 §2）
> ⇒ 改名 = **改摘要逐字**，会让那条采纳记录失效；而"同名不同物"靠**值类型**已能机械分开。

### 1.2 三条设计红线（逐字）

1. **完成信号权只在主控站**；
2. **L1 机械门先于 L2 语义门，且 L2 无权改写**；
3. **判据与 golden 哈希在 P0 固化**（即"判据不能事后改"）。

### 1.3 不变量（摘要含 3 条）

- **I-1 单写者**（事件流只有主控站可写，工作站只产出不落账）
- **I-3 完成信号权在主控站**
- **I-6 fail-closed**

### 1.4 角色禁项

- **主控站**："**不执行任务本体**"；
- **工作站**："**不自评通过、不写 verdict、不重派、不合并**"。

### 1.5 A 段落的射程截断（§2 五行"依据不足"的处置）

**A 段（2026-10-01 · 离线契约化）** 把本契约落成 `ops/rpc_check.py` 的**纯函数判据库**
（`validate_envelope` / `d7_transition` / `d7_block` 的 8 条规则）。★ **射程到此为止，逐条如下**：

- **信封校验只到"键在不在"这一层** —— 顶层必需键 + 摘要**逐字给出**的子键
  （`golden{ref,checksum}` / `inputs{ref,digest}` / `evidence_budget{anchors,tool_calls}` /
  `artifact{digest,size}`）；**不判取值、不判内部结构**。
- ★ **§2 五行"依据不足"的处置 = 【登记为射程边界】，既不是待办、也不是缺口**：
  `evidence_budget` 结构 / `constraints` 清单 / `decisions[]` 八字段 / `redispatch?` 触发条件 /
  `sensitivity` 取值域 —— **一律不判、不补**。理由照 §2 原话：它们记的是"**摘要里没有**"，
  补它们**需要回原文**，**不属于本契约的范围**；由本仓**自行发明**一份结构与"新建第二份真值"同罪。
- **三个可机判入口（本次新落）**：① `RunReport` 含 `verdict` ⇒ **拒**（产出方不得自评）；
  ② `Verdict.verdict` **非整数** ⇒ 拒（`verdict` 词义冲突的机械切分，见 §1.1）；
  ③ `TaskContract.accept[]` 缺 `criteria_hash` ⇒ 拒（红线 3 的机判入口）。
- **状态机判"迁移合法性 + 驱动角色"**：含**不得跳过 L1**（`collected` 不直落 `accepted|rejected`）
  与**终态无出边**、以及"P1/P2/P3 由工作站驱动、P0/P4a/P4b/P5 由主控站驱动"；
  ⚠ 它**不判**轮询/推送等**实现形态**（那是 B 段接线的事）。
- ⚠⚠ **仍未实测（与 §未实测 1–6 同口径）**：本段落的判据**从未被真实信封 / 真实迁移驱动过** ——
  本仓**零个真实 `TaskContract` / `RunReport` / `Verdict`** ⇒ 判据的输入全是**离线夹具**。
  ⇒ §未实测 **7 / 8 / 9** 的 `state` 按口径记 **`partial`**（判据已落、真跑未做），**不**记为已消。

---

## 2. 采纳 / 裁剪的逐项决定

| 项 | 决定 | 理由（引用摘要第几处） |
|---|---|---|
| 六相状态机（P0–P5） | 采纳 | 摘要首行完整给出六相序列 |
| 状态名序列 | 采纳 | 摘要第二行完整给出序列 |
| TaskContract 字段集 | 采纳 | 摘要"三种信封（字段级）"第一项逐字列出 |
| RunReport 字段集 | 采纳 | 摘要"三种信封（字段级）"第二项逐字列出 |
| RunReport 无 verdict 字段 | 采纳 | 摘要显式标注"★ RunReport 刻意不含 verdict 字段 —— 产出方不得自评" |
| Verdict 字段集 | 采纳 | 摘要"三种信封（字段级）"第三项逐字列出 |
| 红线 1：完成信号权只在主控站 | 采纳 | 摘要"三条设计红线（逐字）"第 1 条 |
| 红线 2：L1 先于 L2，且 L2 无权改写 | 采纳 | 摘要"三条设计红线（逐字）"第 2 条 |
| 红线 3：判据与 golden 哈希在 P0 固化 | 采纳 | 摘要"三条设计红线（逐字）"第 3 条 |
| 不变量 I-1 单写者 | 采纳 | 摘要"不变量（摘要含 3 条）"第 1 项 |
| 不变量 I-3 完成信号权在主控站 | 采纳 | 摘要"不变量"第 2 项 |
| 不变量 I-6 fail-closed | 采纳 | 摘要"不变量"第 3 项 |
| 角色禁项：主控站不执行任务本体 | 采纳 | 摘要"角色禁项"第 1 句 |
| 角色禁项：工作站不自评/不写 verdict/不重派/不合并 | 采纳 | 摘要"角色禁项"第 2 句 |
| P4b 语义复核的可选性 | 采纳 | 状态名序列中标注"（可选）sem_verified" |
| `evidence_budget` 的结构细节 | **依据不足** | 摘要仅给出键名 `anchors` / `tool_calls`，无内部结构定义 |
| `constraints` 禁止项的具体清单 | **依据不足** | 摘要仅给出键名，无枚举 |
| `decisions[]` 八字段的具体定义 | **依据不足** | 摘要仅提"八字段"，未展开 |
| Verdict 中 `redispatch?` 的触发条件 | **依据不足** | 摘要字段列表含 `redispatch?`，无规则说明 |
| `sensitivity` 的取值域与分级规则 | **依据不足** | 摘要仅出现键名，无取值定义 |

> ⚠ **五行"依据不足"不是待办、是登记**：它们记的是"**摘要里没有**"，
> 补它们需要回原文，**不属于本契约的范围**（见末节）。
> ★ **A 段（2026-10-01）补一条处置（落回本节）**：这五行在**机判**上的形态 = **射程边界** ——
> 信封校验器**只判这些键在不在**，其内部结构**不判、不补**（见 §1.5）。
> ⇒ 它们是"**已知的信息边界**"，**不是**积压的待办；把它们当待办去"补齐"，
> 等于**由本仓发明一份真值**（本仓头号形态）。

---

## 未实测登记

> **本节的读法**：逐条列"本契约里**尚未被任何真实运行验证过**的部分"，并指出**在什么意义上**没被验证。
> ⚠⚠ **本节必然非空、且至少 5 条** —— 理由：本契约是**新定案的**，其任何部分都还没有真实运行验证过
> ⇒ **不成立**"这一节可以写无"。若认为某部分**已被**验证，必须指出**是哪一个 run / 哪一次机判**；
> 指不出来，就属于未实测。

1. **P0 立契阶段从未真实跑通过**：TaskContract 的生成、固化判据与 golden 哈希、分发到工作站的全链路，
   无任何一次真实运行记录可供核验。
2. **P1 领取状态迁移从未被真正触发**：工作站轮询/推送获取 TaskContract 并置 `claimed` 状态，
   文档层有描述、**代码中无对应实现**，从未有真实 run 产生过 `claimed` 事件。
3. **P2 执行阶段 RunReport 从未被真正写过**：RunReport 全字段集（含 `decisions[]` 八字段、
   `evidence[]` 锚点、`usage`）从未在真实执行中由工作站产出、序列化、传回主控站。
4. **P3 回收与 P4a 机械验证从未被机判过**：主控站接收 RunReport、自动跑 L1 门、写入 `l1_results[]`
   的完整流程，无任何一次机判记录。
5. **P4b 语义复核（可选分支）从未被真实触发**：`sem_verified` 状态、`l2_marks[]` 产出、
   "L2 无权改写 L1"的红线约束，**均只存在于文档，代码里无对应实现**。
6. **P5 裁决登记 Verdict 从未被真实落盘**：Verdict 信封（含 `verdict`、`phase`、`l1_results[]`、
   `l2_marks[]`、`redispatch?`、`recorded_at + seq`）的生成与持久化，无真实 run 对应。
7. **三条红线从未被机制强制过**：完成信号权仅在主控站 · L1 先于 L2 且 L2 不改写 ·
   判据与 golden 哈希 P0 固化 —— 均为**文档约束**，代码层**无拦截/校验实现**。
   ★ **A 段已落（2026-10-01）**：三条已落成**纯函数拦截**（`ops/rpc_check.py` 的 `d7_block`
   规则 `RL1` / `RL2` / `RL3`）+ 离线夹具（`tests/test_rpc_check_d7_protocol.py`，含先验红自证）。
   ⚠ **仍未实测**：这些拦截**从未拦过真实动作**（本仓零个真实信封），且**尚未接线**
   （须等 B 段）⇒ `state` 记 **`partial`**（判据已落、真跑未做）。
8. **不变量 I-1 / I-3 / I-6 从未被运行时守护过**：单写者、完成信号权在主控站、fail-closed
   三条不变量，无运行时断言、审计日志或熔断机制对应。
   ★ **A 段已落（2026-10-01）**：已落成纯函数规则（`d7_block` 的 `I1` / `I3` / `I6`；
   ★ `I3` 与红线 1 **同内容** ⇒ **共用同一份实现**，不造第二份真值）。
   ⚠ **仍未实测**：无运行时断言 / 无审计日志 / 无熔断**接入**（本段只落判据）⇒ `state` 记 **`partial`**。
9. **角色禁项从未被代码层阻断过**：主控站"不执行任务本体"、工作站"不自评通过/不写 verdict/不重派/不合并"，
   **全靠约定**，无编译期或运行期约束。
   ★ **A 段已落（2026-10-01）**：两角色禁项已落成纯函数规则（`d7_block` 的 `PRM` / `PRW`）
   + **状态机的驱动角色约束**（`d7_transition` 的角色检查：P1/P2/P3 由工作站、其余由主控站）。
   ⚠ **仍未实测**：**未接编译期或运行期约束**（仍靠调用方传 `actor`）⇒ `state` 记 **`partial`**。
