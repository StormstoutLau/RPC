# RPC 跨项目受理区（Inbox）

> **单点入口**：本目录是"需求方 → 机群管理员"跨项目请求的唯一受理面。
> 依据 [ADR-0008](../adr/ADR-0008-跨项目受理区与目录治理.md)；受理前先读
> [手册 §1.3](../docs/三机推理集群使用手册.md)（框架完成度/受理标准）。
> 本目录**默认不进站**（`.agentsync` 排除语义；未发表语料绝不随 sync 上站）。

---

## 1. 这是什么

当**其他项目**（如 `D:\Paper`）需要把批量任务交给本机群（A/B/C 三站）执行时，
需求方提交一份**转运包**（含缺陷报告 DR / 变更需求 CR / 编排与接口约定 / 证据附录），
管理员据此**受理、裁决、派发、观测、关闭**。本目录就是这个流程的**统一载体**。

> ⚠ 转运包 ≠ 任务本身。转运包是"受理请求"，任务被执行时走 `agent-cli task paper --card <卡>`
> 等既有派发链，产物回收仍在项目根的 `agent-out/`。本目录只承载**受理与裁决的痕迹**。

---

## 2. 目录结构（每笔受理一个目录）

```
d:\RPC\inbox\
   README.md                     # 本文件（受理流程单一真值源）
   _template\                    # 标准模板（复制它到新项目）
      00_handoff\                # 需求方原始转运包（只读冻结，不覆写）
      10_admin\                # 管理员裁决 + 复核意见（受理决定 / 裁决报告 / 复核意见-N）
      20_plan\                 # 派发计划 / 任务卡模板（修订留版本 vN）
      30_evidence\             # 执行台账 / 交付证据束（MANIFEST.sha256 钉死）
      40_state\                # 生命周期标记（STATE.json + LOG.md）
   <project>-<yyyy-mm-dd>\       # 每笔受理（项目名-提交日期）
```

---

## 3. 生命周期状态机

由 `40_state/STATE.json`（`state`/`updated_at`/`by`）标记；每次变更在 `40_state/LOG.md` 追加一条。

```
open → triage ⇄ waiting → accepted → plan-review ⇄ plan-revise → running → release → done
   → accepted-by-requester | rejected-by-requester
rejected（可从 triage / accepted / plan-review / plan-revise 任一进入）
```

> `⇄` 表示可循环（协商回环 / 等回复）。直线为主路径；`rejected` 与 `rejected-by-requester` 为终止态
> （后续新需求**开新 `open`**，不重写旧目录状态）。

| 状态 | 含义 | 何时进入 |
|---|---|---|
| `open` | 已提交，等待管理员初筛 | 需求方提交转运包后 |
| `triage` | 正在核对 DR/CR/接口，出裁决报告（**主动处理中**） | 管理员开始处理 |
| `waiting` | 卡在**等需求方补充 / 等外部条件**（区别于 triage 的主动处理） | 需需求方补料 / 依赖未就绪 |
| `accepted` | 裁决通过，准备派发（入 `$PROJECTS`） | 裁决报告落 `10_admin/` |
| `plan-review` | 派发计划已交需求方**复核**，等回复 | `20_plan/` 成型后交对方 |
| `plan-revise` | 收到需求方意见，管理员**修订** `20_plan` | 复核退回，修订中 |
| `running` | 正在机群执行 | 方案定稿开始派发 |
| `release` | 执行完毕，交付证据束，**等需求方验收** | 产出回收入 `30_evidence/` 后 |
| `done` | 运维确认完成（**结案**） | 证据束已回收、哈希钉住 |
| `accepted-by-requester` | **验收签收**（需求方认账） | 需求方确认交付 |
| `rejected-by-requester` | 验收不通过 / 终止 | 需求方拒收，终止 |
| `rejected` | 裁决驳回 / 暂缓（`10_admin/受理决定.md` 写明理由） | 裁决否 |

**合法取值白名单**：`open` `triage` `waiting` `accepted` `plan-review` `plan-revise` `running` `release` `done` `accepted-by-requester` `rejected-by-requester` `rejected`

> **真值源**：[`inventory/inbox.yaml`](../inventory/inbox.yaml) 的 `states:` 段 —— 白名单 / 下一动作 / 待办分组都出自那里，
> `rpc_check.py` 与 `cluster_web.py` 消费同一份。**本行的白名单与上表由门禁 `mirror` 断言对账**：
> 改状态**只改 yaml 一处**，本行与状态表跟着改（改一处忘改另一处会被门禁点名）。

**变更纪律**：状态只由管理员改 —— 覆盖写 `40_state/STATE.json`（`state`/`updated_at`/`by`），
并在 `40_state/LOG.md` **追加**一条变更记录；需求方不改。
每笔目录的 `10_admin/受理决定.md`（及其后的 `10_admin/复核意见-N.md`）是**状态变更的理由真值源**。

---

## 4. 管理员受理流程（每笔）

1. **初筛**：读 `00_handoff/`，对照 [手册 §1.3](../docs/三机推理集群使用手册.md) 的
   "受理前置均已就绪"清单，标 `triage`。
2. **裁决**：`10_admin/裁决报告.md` 逐条回复 DR（确认/不成立/已修）+ CR（采纳/拒绝/替代）
   + 接口确认（A1-A13 语义核对）。`10_admin/受理决定.md` 写最终边界（合规轨 L/P、并发约束）。
3. **阻塞转 waiting**：若需需求方补料 / 等外部条件（如 CR-5 宿主、CR-7 引擎常驻裁定）→ 标 `waiting`，
   LOG 记理由；补毕回 `triage`。
4. **入台**：通过 → `$PROJECTS` 注册（`agent-cli.ps1`）+ `20_plan/` 派发计划（含**容量预估**：墙钟/
   站占用窗口，见 `_template/20_plan/`）；驳回 → 写理由 + 标 `rejected`。
5. **方案复核回环**：`20_plan/` 成型 → 标 `plan-review` 交需求方复核；收到意见 → 标 `plan-revise`，
   意见落 `10_admin/复核意见-N.md`，修订 `20_plan/`（版本 vN）→ 再交 `plan-review`，循环至定稿。
6. **执行**：按定稿 `20_plan/` 派发；观测记录落 `30_evidence/`（产物本身在项目根 `agent-out/`）。
7. **交付 + 验收**：产出回收 → 30_evidence 证据束链死 → 标 `release` 交需求方验收；
   需求方签收 → `accepted-by-requester`；拒收/终止 → `rejected-by-requester`（后续新需求开新 `open`）。
8. **关闭**：`done`（运维结案）/ 各终止态；更新手册 §1.3 若框架完成度有变。

---

## 5. 交付证据束标准（结案必查）

> 把框架已有的 run/卡级证据束（[ADR-0005](../adr/ADR-0005-任务卡证据回收闭环.md) /
> [ADR-0007](../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md)）在结案点钉成**交付物标准**。
> 模板见 `_template/30_evidence/README.md`。

1. **链死**：结案时把项目根 `agent-out/<ts>/` 的**实际存在的全部证据件**逐个 sha256，
   写入 `30_evidence/MANIFEST.sha256`（与 `00_handoff` 同格式，`sha256sum -c` 可校验）。
   **未附证据束 → 不 `done`**。
   - **一条命令**：`python ops/cluster.py inbox seal <proj-dir> [--run <ts>|--all-runs] [--grade Reproduced|Replicated] [--go]`
     （默认只出计划，`--go` 落盘；proj→项目根的真值取自 `agent-cli.ps1` 的 `$Script:PROJECTS`，不另抄一份）。
   - ⚠ 钉的是**目录里实际有的文件**，不是固定的 6 件清单：实测真实 run 目录并**不齐**
     `AGENT_EVIDENCE_FILES`（`judgment-record.txt`/`accept-*` 只在配了 accept/golden 的任务里才有）
     —— 那 6 件是**链校验的"声明件"**，不等于"本次交付束"，硬套会导致常态失败。
   - 站上原始名（`.meta`/`.progress`/`.accept-cmds.txt`/`.golden-cmd.txt`/`.workspace-diff.txt`/
     `.attach-manifest.txt`/`.session-meta.txt`）在 **collect 阶段**已被归并/改名进 run 目录，
     故本清单按回收后的文件名钉（`.agent-run.json`/`agent-output.txt`/`prompt.txt`/`card.md`/`stderr.txt` …）。
2. **artifact freeze**：`done` 后 `30_evidence/` 与 `00_handoff/` 同样冻结，不再改动；
   后续新需求开新 `open`。
3. **重放语义**：验收判据 = **重放验证、非重放生成**（沿 ADR-0007）——可证伪的是哈希/diff/退出码/
   输入快照，不承诺逐位一致再生成。
4. **分级标注**：交付物标注 `Reproduced`（内部同基座复验，Phase 2）
   或 `Replicated`（异基座独立审计/cold mirror，Phase 3）。
5. **环境快照**：`cluster.py versions` 三站引擎/uv/模型哈希/`--kv-cache` 参数随证据束落档
   （社区"机器可读环境描述"）。

---

## 6. 三条硬约束（向需求方传达）

1. **零自加载**：引擎不自启，每次断掉须运维 `infer-load`。
2. **跨站各 1 并发**（同站叠开被统一内存带宽顶起 ~2.8×）。
3. **`local-only` 硬门**：未发表语料走轨 L，`egress → REJECT exit 4` 无覆盖通道。

---

## 7. 门禁

- 本目录**不参与** `scripts` 断言（是文档/交接物，非脚本）。
- **`inbox` 断言（`rpc_check.py`，quick 已启用）**：校验每个 `<proj>-<date>/`
  ① 有 `00_handoff/` ② `40_state/STATE.json` 存在、可解析、state ∈ 白名单
  ③ 状态内容自洽 —— **各态的"必需件"由** [`inventory/inbox.yaml`](../inventory/inbox.yaml) **的 `requires` 字段定义**
  （门禁 `inbox` 派生执行，改需求只改 yaml 一处；下面是人读概览，非真值）：
  `accepted` 及之后须有受理决定 · `plan-review`/`plan-revise` 须有派发计划 · 交付态须有证据束。
- **交付态强判据（2026-09-23 收紧）**：`release` / `done` / `accepted-by-requester` 三态
  **必须存在 `30_evidence/MANIFEST.sha256`**（不再只是"目录非空"）。
  加严理由：原判据放个无关文件即可通过 ⇒「未附证据束不 `done`」形同虚设（空转的软约束）。
  生成：`cluster.py inbox seal <proj-dir> --go`。
  `rejected-by-requester`（可能交付前就终止）不进本集，只保留"目录非空"。
- **dashboard**：
  - `cluster.py inbox` —— 列出所有受理目录 + state + updated_at，一行一条（CLI）。
  - **web 看板**（推荐，零手动）—— `cluster.py web` 管理页的**「受理区 · 跨项目进度 + 待办聚合」卡片**：
    15s 自动刷新，按"需要动作"分组（`waiting`/`plan-review`/`release` 黄底高亮 · 进行中 · 已关闭折叠），
    顶部健康快照（共 N 笔 · 需动作 M · 进行中 K），并**从状态机派生每笔的"下一动作"**（待办聚合，
    无需人工维护）。数据源 = 各笔 `40_state/STATE.json`（派生视图，与门禁同一套状态语义）。

---

## 8. 第一笔实例

`paper-2026-08-23/` ← `D:\Paper\handoff_to_rpc_admin`（2468 篇论文蒸馏，已裁决推进中）。
需求方原件已复制到 `00_handoff/`（复核用），项目侧原目录继续被 `.agentsync` 排除。

**当前待办**（解除 `waiting` 的前置）：产出正式 `10_admin/裁决报告.md`
（逐条 DR/CR/接口确认；CR-1/CR-5/CR-7 需需求方裁定）→ `10_admin/受理决定.md` → `20_plan/`（含容量预估）
→ 交需求方复核。待办明细见 `paper-2026-08-23/40_state/评估摘要.md`。