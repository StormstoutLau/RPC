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
> · **判官输出（= 结论契约 `D7-PROTOCOL-CONCLUSION-CONTRACT`）的 `verdict` = 四值**
>   （`accept` / `revise` / `reject` / `uncertain`；承载 = `ops/station-bin/review/judge-prompt.tmpl` +
>   `Test-ConclusionContract`；★ 本仓落点 = **`review.json.contract.verdict`（嵌套）** ——
>   **`review.json` 顶层没有 `verdict` 键**）—— **不属本信封**。
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

### 1.6 六相 × 本仓现状（**B 段落点表** · 2026-10-01）

> ★ **本表不是新造的** —— 字段级"本仓有没有"仍以既有对照表为准
> （[Spec_Workflow 调研 §3.3](../../docs/2026-09-23_Spec_Workflow能否作为D6-D7工作流基准_调研.md)，2026-09-23）；
> 本表只补"**接线落在哪个既有载体、缺什么**"这一层（**不重复**那份的字段清单）。
> ★★ **B 段的口径**（用户 2026-10-01 裁）：**对齐既有载体 · 不新增信封件** —— 三信封**映射到**卡 /
> `.agent-run.json` / `review.json`，判据一律走 `ops/rpc_check.py`（**外壳不重写判据**）。

| 相 | 落点（既有载体，**不新增件**） | 现状 / B 段动作 |
|---|---|---|
| **P0 立契** | 卡 front-matter + `Get-CardIdentity` → `New-TaskContract` | ★ **已接（B 段）**：`Invoke-Task` 的 `require-gate` 之后产 `TaskContract` 信封（**新增** `criteria_hash` = 红线 3 的**固化动作**）⇒ `Write-D7Report` 调判据本体；`gaps` 3 项**如实报出**、**灰度期不阻断**。★ **复核更正**：claude 备路**也被覆盖**（`Invoke-Task` 的两处 `Invoke-Task-Claude` 调用在 L2133 / L3410，**都在 P0 块 L2067 之后**）—— B1 曾登记"claude 备路未接"，**该说法有误，已就地更正** |
| **P1 领取** | 站上 `.agent-state.json` + `.agent-lock`（`Invoke-LockState`） | ★ **已接（B3）**：acquire 写 `claimed`（B3 之前写 `running`） |
| **P2 执行** | `Invoke-Task` 本体 | ★ **已接（B3）**：任务体写 `executing`；claude 备路也落同一词（★ 该行**同时是 PRM 冲突点**，见下） |
| **P3 回收** | runDir + `.agent-run.json` → `New-RunReport` | ★ **已接（B2）**：**两处** `.agent-run.json` 写出点（主路 + claude 备路）各产 `RunReport` ⇒ 判据校验；★ **刻意不含 `verdict`**（产出方不得自评）；`gaps` 3 项如实报出 |
| **P4a 机械门** | ★ **`Resolve-L1Gate`（已存在）** | ★ **已接（B2）**：`Write-D7Adjudication` 逐跳调 `d7_transition`（`collected→mech_verified`） |
| **P4b 语义复核** | ★ **`Invoke-Review` + 结论契约校验（已存在）** | ★ **已接（B2）**：L2 跑过 ⇒ 走 `sem_verified`；**没跑（判官调用失败）⇒ 如实跳过**；`l2_marks[]` = 结论契约段**原文照收** |
| **P5 裁决登记** | `review.json`（**advisory**；**顶层无 `verdict` 键**）→ `New-Verdict` | ★ **已接（B2）**：**两处** review 写出点各产 `Verdict` 信封（`verdict` = review 的 **exit code**）⇒ 判据校验 + 红线 1/2；★ 仍 **advisory**（**不改退出码**） |
| **I-1 单写者** | `Add-LedgerLine`（带锁共享 ledger） | 无**流级**单写者身份层（**未接** · B3） |

★ **B 段落的本地映射（摘要没给"谁对谁" ⇒ 写死在这里，免得下次另发明一套）**：

- P3：`run_id` ← `task_id`（本仓 run 的既有标识）· `artifact.digest` ← `content_digest` ·
  `artifact.size` ← `output_bytes` · `inputs_digest` ← `card.sha256`（卡 = 最大的注入物）。
- P5：`l1_results[]` ← `review.json` 的 `l1` 段 · `l2_marks[]` ← 结论契约段（**原文照收，不新造结构**）·
  `verdict` ← review 的 exit code · `phase` ← `P5` · `seq` **固定 1**（⚠ 摘要未给语义 ⇒ **占位不是真值**，进 `gaps`）。
- 相序列：起点 `collected`；终态 = `accepted` **iff L1 = green**（机械门通过 = 本仓"完成信号"的来源）；
  **L2 是 advisory ⇒ 不翻转终态**。
- ⚠ **诚实**：红线 1 的 `actor` 在本架构里**恒为 `master`**（外壳只在主控跑）⇒ 它的实用价值是
  **防将来有人把 P5 搬到站上**，**不是**"已拦过真实动作"。

★ **各相从"灰度"转"硬拒"的条件（写死，免得靠记忆）**：对应信封的 `gaps` **清空** ⇒ 把 `D7_*_REJECT`
分支改成 `return 3`（拒派发 / 拒收）。

★★ **站上状态件的词汇边界（B3 落，2026-10-01）—— 这一节是"别把生命周期读成相"的护栏**：

- **唯一真值**在 `ops/station-bin/agent-cli.ps1` 的 `$Script:STATE_*` 块（**不许在别处再抄一份词表**）；
  判据 = 夹具 `b3①–⑨`（`_fm_golden_test.ps1`）。
- **契约相（2 个）**：`claimed`（P1 领取）· `executing`（P2 执行）。
- ★★ **非契约词（2 个，必须登记，否则下一个人会把它当相来读）**：
  - `done` —— 锁释放 = **持锁进程退出**，是**进程生命周期**，**不是** D7 终态；
  - `orphaned` —— 孤儿回收（`out/` 已归档到 `out/orphaned/`），同样是**生命周期**。
  ⚠⚠ **为什么它们不许写成 `accepted` / `rejected`**：红线 1「**完成信号权只在主控站**」（§1.2）⇒
  工作站写终态 = **产出方自评**。夹具 `b3⑥` 就钉这一条（站上状态件**从不**出现这两个词）。
- ★★ **读侧必须与写侧同源 —— 本批的主判据**：孤儿判据原先**逐字比** `= running`，而写入侧不再写
  `running` ⇒ **只改写方 = 孤儿检测静默失效**（fail-open，本仓最防的形态）。故活跃态谓词收进同一块、
  被**两个** station body 插值；★ 且**保留 `running` 为 legacy 可读**（B3 之前写出的残留 state 件
  仍是这个词 ⇒ 收掉它会让残留件的孤儿回收静默失效）。夹具 `b3②/④/⑤/⑧` 钉这四条。
- ⚠ **本文件不承载"已加载/运行中"的语义**：站上状态件是**工作站自述**，与 `d7_transition` 的相
  **不是同一个事实源** ⇒ 任何"用 `agent-state.json` 判 D7 到了哪一相"的读法都**无效**。

⚠⚠ **B3 期间就地发现（未裁，如实登记）—— 角色禁项 `PRM` 与 claude 备路冲突**：
契约 §1.4 写「**主控站不执行任务本体**」。★ **冲突面 = 【出网档 且 无站路由/pin】那一路** ——
它 `$useStation=$false` ⇒ **主控本地 spawn**（`agent-cli.ps1` L3708-3710 逐字；`O-124` 实测批
`_batch/20260930145220`：三行 `station=A/B/C` **三次全在主控本地跑**）⇒ **冲突成立**。
⚠⚠ **就地更正（2026-10-01）**：B3 首版把冲突面写成"claude 备路的 `local` 档在主控本地跑"——**错**：
`local-only` 档 `$backendLocal=$true` ⇒ `$useStation=$true` ⇒ 跑在**站上**，**不触** PRM。
本批**只如实落词 + 就地标注**，
**不擅自裁决**（裁法至少三选：① 认定"备路 = 主控代跑"属**已知例外**并登记；② 把 `PRM` 的
`actor` 判据改成"**执行发生在主控 ⇒ 拒**"，从而**禁掉**备路本地档；③ 双轨：备路本地档只允许
`readonly` 卡）。⇒ B3 的 `PRM` / `I-1` / `I-6` / `PRW` **接线待此项先裁**。

⚠ **仍未接**（B3 剩余 + C 段）：`d7_block` 的其余条目（`I-1` / `I-6` / `PRM` / `PRW`）——
★ 其中 `PRM` **须先裁上面那条冲突**；**`RunReport`/`Verdict` 的真跑**（C 段）—— 如实登记，不假装全覆盖。

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

> ★★ **2026-10-01 复核更正（就地 · B 段）** —— 以上 **5 / 7 / 8** 三条里
> "**代码里无对应实现**""**代码层无拦截/校验实现**""**无运行时断言**"的措辞**已过时**。
> **实测（读码，E1）**：**红线 2 与 `I-6` 早有实现** —— `ops/station-bin/agent-cli.ps1` 的 `Resolve-L1Gate`
> （`D7-P2-1`，2026-09-26）：**纯函数** · **fail-closed**（记录读不出 ⇒ `unknown` ⇒ **拒**）·
> `--allow-l1-red` **降级但不隐藏**；**P4b 的 `sem_verified` 侧亦有实现**（`Invoke-Review` +
> 结论契约校验 + `review.json.l1.record_sha256` = "**L2 未改写 L1**"的可判凭据）。
> ⇒ ★ **本节的"未实测"仍然成立**（"从未被**真实运行**验证过"没变），但**"无实现"这半句要改**：
> 真实缺口是"**这些实现没有被收敛到契约的字段与状态名下**"（= B 段在做的），**不是"没有机制"**。
> ⚠ 登记性质 = **就地更正**（"登记比实现旧"这一类），**不是**新裁定。
