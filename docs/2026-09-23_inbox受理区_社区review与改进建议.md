# 决策简报 — inbox 受理区 community review 与改进建议（ADR-0008）

- **日期**: 2026-09-23
- **状态**: **仅落档（不改动）** —— 本次只记录社区对照结论与改进建议，**不实施任何改动**；
  待 Scott 逐条裁定后再改。
- **依据**: [ADR-0008](../adr/ADR-0008-跨项目受理区与目录治理.md)（已落地）+ 社区案例调研（见 §1 来源）
- **关联**: `inbox/`（受理区现状）、[三机推理集群使用手册 §1.3](三机推理集群使用手册.md)

---

## 1. 社区案例来源

| 来源 | 主题 | 对 inbox 最相关的点 |
|---|---|---|
| [assign.cloud 任务工作流模板](https://assign.cloud/task-management-workflow-templates-small-teams) | 五问：work/owner/status/blocker/complete；"priority ≠ workload" | 受理判据、单 owner、明确状态 |
| [Asana 项目受理流程](https://asana.com/resources/project-intake-process) | 单受理通道 + 排期 + 先测试流程 | 单一入口、dashboard、试点先行 |
| [ClickUp 12 受理软件](https://clickup.com/blog/project-intake-software/) | 单通道 + 命名打分框架 + 单一 owner 批准 + 连接交付 | 最终审批人 = 管理员 |
| [numan 多仓库目录治理](http://raw.githubusercontent.com/tonythethompson/numan/master/docs/plans/consolidated-multi-repo-roadmap.md) | intake→evidence→staging→production，跨仓库产物不可跨阶段信任 | 证据强制、阶段推进 |
| [Modonome repo-local 自治环](http://raw.githubusercontent.com/nateshpp/modonome/HEAD/prompts/modonome.bundle.md) | 状态目录 `.modonome/` + 可机读状态 + 严格 safety gate | 状态可机读、变更审计 |

---

## 2. 对照结论（对齐/差距）

| 社区实践 | inbox 现状 | 对齐/差距 |
|---|---|---|
| 单一受理通道 + 单一最终审批人 | inbox 唯一入口；管理员唯一受理人 | ✅ 对齐 |
| 明确 owner / status / blocker / complete | README 有 owner/状态机/待裁项/受理判据 | ✅ 对齐 |
| 先测试流程再推广 | paper-2026-08-23 即试点 | ✅ 对齐 |
| 产物不可跨阶段信任（numan 证据链） | inbox 00→10→20→30→40 | ⚠️ 部分（缺 hash 钉住，见劝5） |
| 状态目录可机读 + 变更审计（Modonome） | `40_state/STATE` 手写文本、无门禁 | ❌ 差距最大（劝1） |
| dashboard 让所有人看得到状态（Asana） | 需人翻目录 | ⚠️ 差距（劝2） |
| 显式"等待/转人工"状态（assign.cloud blocker） | `triage` 混"在处理"与"等回复" | ⚠️ 差距（劝3） |
| 不用 priority 替代排期 | 无优先级字段 | ✅ 对齐（好） |

---

## 3. 改进建议（按优先级，待裁定）

### ① [P0] `40_state/STATE` 结构化 + 变更 LOG
- 现状：一行手写文本，靠人改，无机器可判结构、无审计。
- 建议：读 `STATE.json`（`{"state":"open","updated_at":"…","by":"admin"}`），或 STATE 文本
  相邻加 `40_state/LOG.md` 记录每次变更，可审计/可回滚。
- 依据：Modonome 教训——状态必须可机读且变更可追溯。

### ② [P0] 状态机加 `waiting`
- 现状：`triage` 混了"管理员主动处理中"与"卡在等需求方回复/外部条件"。
- 建议：加 `waiting`（等需求方补充 / 等外部条件），与 `triage` 区分。
- 例子：paper 本笔正卡在等 CR-1/CR-5 裁定 → 标 `waiting` 更诚实。

### ③ [P1] 加 `inbox` 门禁断言（ADR-0008 已列为可选）
- 校验每个 `<proj>-<date>/`：① 有 `00_handoff/` ② `STATE` 合法取值 ③ 状态与内容自洽
  （`accepted` 必须有 `10_admin/受理决定.md`）。
- 依据：本仓纪律——先验红再启用；Modonome safety gate + ADR-0004 管理面纪律。

### ④ [P1] 聚合清单或入口命令（dashboard 替代）
- 建议：`inbox/STATUS.md` 聚合清单，或 `cluster.py inbox` 子命令：列出所有目录 + state + 更新时间，一行一条。
- 依据：Asana dashboard 教训；符合本仓"单一真值源 + 管理走入口"纪律（ADR-0004）。

### ⑤ [P1] `00_handoff` 与项目侧双副本漂移
- 现状：`00_handoff` 是复制；`D:\Paper\handoff_to_rpc_admin` 原目录仅被 `.agentsync` 排除。
  若需求方更新原目录，00_handoff 不自动同步 → 漂移。
- 建议二选一：
  - **A（推荐）**：项目侧原目录标记"权威见 inbox"，收拢为唯一副本；或
  - **B**：`00_handoff/` 存原目录 `MANIFEST.sha256` 清单，漂移可检（复用既有校验思想）。
- ✅ **已实施（2026-09-23，方案 B）**：`paper-2026-08-23/00_handoff/MANIFEST.sha256` 已生成
  （标准 `sha256sum` 格式：`<hex>  <relpath>`，顶部注释头含生成时间 + 校验方法）。
  **双向自证通过**：基线源 vs 清单 8/8 一致 → 临时改源 README 引入漂移 ⇒ 校验报 **False**（可检）→
  还原 ⇒ **True**。漂移检测**可检出、可还原、非恒真**。校验命令：cd 到源目录后
  `sha256sum -c <MANIFEST绝对路径>`（Windows 侧等价用 Python 递归比对）。

### ⑥ [P2] `30_evidence` 证据 hash 链接
- 现状：`30_evidence` 设计为"指针"，产物在项目根 `agent-out/`，未链死。
- 建议：每笔落回收产物清单 hash（指向 `D:\Paper\agent-out/<ts>/` 的 run.json），与既有证据链
  （ADR-0007）对齐——证明"这一批产出就是这些"。

### ⑦ [P2] 受理时容量预估进 `20_plan/`
- 建议：批量任务受理时预估墙钟/站占用窗口（如 2468 篇×20 天），进 `20_plan/`。
- 依据：assign.cloud "priority ≠ workload"；这是业务判断，不强制。

---

## 4. 验证为"不必改"的设计（保留）

- **日期命名 `<proj>-<date>`**：与社区 per-date/可排序一致。
- **无 priority 字段**：符合"priority ≠ workload"教训。
- **机群侧 inbox（非项目根）**：与 mono/polyrepo 集中管理面一致。
- **转运包 ≠ 任务**：职责分离正确。

---

## 5. 待 Scott 裁定（改动由你定）

| # | 建议 | 优先 | 采纳? | 说明 |
|---|---|---|---|---|
| 1 | STATE 结构化 + LOG | P0 | — | |
| 2 | 状态机加 `waiting` | P0 | — | |
| 3 | inbox 门禁断言 | P1 | — | |
| 4 | STATUS.md / cluster.py inbox | P1 | — | |
| 5 | 00_handoff hash 钉住 | P1 | ✅ 已实施 | 方案 B：MANIFEST.sha256（见 §3 ⑤） |
| 6 | 30_evidence 回收 hash | P2 | — | |
| 7 | 20_plan 容量预估 | P2 | — | |

> 本简报只记录；任何一项是否采纳、如何改，由 Scott 逐条裁决。