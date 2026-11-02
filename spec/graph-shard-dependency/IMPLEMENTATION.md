# 实施文档：片间依赖边从「只记录」到「可执行」

---

id: graph-shard-dependency-IMPLEMENTATION
type: design
version: 1.0
status: draft
date: 2026-10-31
depends: [graph-shard-dependency-DESIGN]
upstream: null

---

> **Feature**: 按 DESIGN 的三期（乙 → 甲1 → 甲2）落地片间依赖边，每期**一提交且门禁全绿**。
> **创建日期**: 2026-10-31
> **状态**: draft（尚未开工；§1 的 P0 前置为用户确认 DESIGN §1.3 两条语义裁定）
> **Spec 步骤**: Step 5-6
> **基于设计**: [DESIGN.md](./DESIGN.md)
> **基于调研**: [片间依赖边从观测到执行 · 调研](../../docs/research/2026-10-31_片间依赖边从观测到执行_调研.md)
> **验收门**: [CHECKLIST.md](./CHECKLIST.md)

---

## 0. 前置条件（硬门）

1. **用户批复** DESIGN §1.3 的 S1（`needs` = 数据依赖）与 S2（固定 `all_success`）。未批复 ⇒ **不动生产代码**。
2. 每期开工前记录**先验红**（旧实现上的反例输出原文），修复后复跑同一夹具转绿。
3. `agent-cli.ps1` 编辑后保持 **UTF-8 BOM**（`ps1-bom` 门禁）。

---

## 1. 实施范围（交付物）

| # | 交付物 | 落位 | 期 | 类型 |
|---|---|---|---|---|
| T1 | `SPLIT_NEEDS_UNSUPPORTED` 闸（有 `needs` ⇒ exit 2，零子进程） | [agent-cli.ps1](../../ops/station-bin/agent-cli.ps1) `Invoke-SplitTask` | 乙 | 修改 |
| T2 | 纯函数 `Get-SplitWaves`（Kahn 分层 + `width_max` + `ok/reasons`） | 同上 | 甲1 | 新增 |
| T3 | `Get-SplitDispatchPlan` 参数改义（`-ShardCount` → `-Width`） | 同上 | 甲1 | 修改 |
| T4 | `Invoke-SplitTask` 波次派发 + `SPLIT_SKIPPED` 失败传播 | 同上 | 甲1 | 修改 |
| T5 | 子卡 front-matter **派生** `evidence-manifest`（仅当主卡声明且该卡带 `needs`） | 同上（子卡生成段） | 甲2 | 修改 |
| T6 | 波末回收（`Invoke-EvmStatePull`）+ 依赖片 `--Attach` 注入 + 摘要比对 | 同上 | 甲2 | 修改 + 复用 |
| T7 | `join.json` 增 `waves` / `width_max` / `skipped[]` / `skipped_count` | 同上（合并段） | 甲1/甲2 | 修改 |
| T8 | 夹具：`O141-split⑩–⑫`、`NEEDS-乙①–④`、`WAVES①–⑩`、`XPORT①–⑥` | [_fm_golden_test.ps1](../../ops/station-bin/_fm_golden_test.ps1) | 三期 | 新增 |
| T9 | 台账与索引回写（`O-184` 状态、`docs/research/README.md` C 节） | [OPEN-ISSUES.md](../d6-agent-standard/OPEN-ISSUES.md) / [README.md](../../docs/research/README.md) | 收尾 | 修改 |

### 边界（不做）

- 不做跨 run / 跨卡依赖；不做可写 split；不引 daemon/中心库；不做按输入哈希复用（M5）。
- 不改 `Resolve-SplitJoin` 判定核；不改站位选路（round-robin 保留）。
- 不新增数字退出码（失败沿用 `1`）。
- 不动 `_fm_golden_test.ps1` 的既有用例语义（只**追加**用例；`NEEDS⑦` 属被撤销的正例，需按 T1 改期望并记录）。

---

## 2. 分期实施

### 2.1 乙（G1 · fail-closed）

1. `Invoke-SplitTask`：在 `Resolve-SplitNeeds` **之后、模型解析之前**加闸 —— `n_with_needs > 0` ⇒ 打 `SPLIT_NEEDS_UNSUPPORTED` 并 `return 2`。
2. 同步撤销 2026-10-16 注释口径（改写成「本版拒绝执行，见 DESIGN §1.3-S1」），`Expand-DecomposeSubject` 的解析逻辑**不动**。
3. 探针卡 `needs-decl-probe` 的期望改为「被拒」；`NEEDS⑦`（正例）先验红（旧实现 rc=0 ⇒ 新实现 rc=2）。

### 2.2 甲1（G2/G3 · 波次）

1. 新增 `Get-SplitWaves`（只读 `Resolve-SplitNeeds` 的 `edges`，**不重算**引用完整性）。
2. `Get-SplitDispatchPlan` 参数改 `-Width`；`Invoke-SplitTask` 传 `$waves[$k].Count`。
3. 派发循环改为逐波：每波内仍 round-robin + 一次性 `Start-Process`；波末 `WaitForExit`。
4. 失败传播：记录每片 `rc`；下一波开始前剔除「上游 rc≠0」的片并入 `skipped[]`；每次剔除打一行 `SPLIT_SKIPPED`。
5. 无 `needs` 时：`waves` 恒为单波 `[[1..n]]`，`width = n` ⇒ 与现状**同判**（不变式 2）。

### 2.3 甲2（G4 · 搬运）

1. 子卡生成：若主卡有 `evidence-manifest` 且该片 `needs` 非空 ⇒ 把 `evidence-manifest` 段**逐字派生**进子卡 front-matter（否则不写，保证无 `needs` 卡零变化）。
2. 波末：对**已完成波次**的每片，用 `Invoke-EvmStatePull`（`-HostName <片所在站>`）回收声明件到片 runDir。
3. 依赖片派发前：把上游片 runDir 产物拷到主控暂存目录（`split-<cid>/attach/shard<i>/`），以既有 `--Attach` 注入。
4. 摘要：仅当 manifest 显式声明 `digest` 时比对；不符 ⇒ `SPLIT_DIGEST_MISMATCH` 并中止后续波次。
5. 上游零产物 ⇒ `SPLIT_PRODUCT_MISSING` 并中止。

---

## 3. 测试设计（先验红优先）

| 组 | 用例 | 红/绿判据 |
|---|---|---|
| `NEEDS-乙①–④` | 带 1/2 条 `needs`、带 `needs` 但全空、带 `needs` 且坏声明 | 旧实现 rc=0（红）⇒ 新实现 rc=2 且**零子进程**（绿） |
| `O141-split⑩` | 三层串行链（宽度 1，共 3 片） | 旧 `SPLIT_INFEASIBLE`（红）⇒ 新判据 ok（绿） |
| `O141-split⑪` | 单波宽度 4 > 容量 3 | 新实现 exit 18（绿），错误行含 `wave #k width 4` |
| `WAVES①–⑩` | 无环/菱形/多入边/无边/越界边/`ShardCount<=0`/自造环（**先验红**：恒 `[{1..n}]` 桩当场红） | 纯函数返回波次与 `width_max` 正确 |
| `NEEDS-甲1` | 上游 rc≠0 ⇒ 下游不派发 | 日志含 `SPLIT_SKIPPED`；`join.json.skipped[]` 有值；整体 rc=1 |
| `XPORT①–⑥` | 上游零产物 / 摘要不符 / 正常注入 / 无 manifest / 无 needs 零变化 / 跨站路径 | 前两例响亮失败；正常例依赖片 runDir 可见件 |

★ 每组必须至少 1 条**能打红**的反例；恒真断言按本仓规矩视为无效（`O-172` 同族）。

---

## 4. 门禁与真跑验证

| 项 | 命令/动作 | 通过条件 |
|---|---|---|
| 单测 | `powershell -NoProfile -ExecutionPolicy Bypass -File ops/station-bin/_fm_golden_test.ps1` | 全绿，新增组全过 |
| 门禁 | `py -3 ops/rpc_check.py --quick` | 无红（黄项须逐条说明） |
| ID 站点普查 | `py -3 ops/id_site_census.py --emit` | 新增 `O-184` 引用行后无漂移告警 |
| 文档链接 | `doclinks`（随 `rpc_check` 跑） | 新增相对链接全部可达 |
| 真站（甲1） | 三层串行链真跑 `split` | `SPLIT_JOIN` / `SPLIT_DONE` 正常；墙钟与跳过行为符合 G2/G3 |
| 真站（甲2） | 两片依赖链真跑 | 依赖片**真读到**上游产物（站上 scp/日志为证） |

⚠ 离线夹具只证明判据与接线顺序；**跨站搬运**只有真跑能证明（调研 §5 尾注）。

---

## 5. 风险与回滚

| 期 | 回滚方式 | 副作用 |
|---|---|---|
| 乙 | 撤 T1 的闸与日志行 | 恢复「声明但忽略」旧口径；须同步回写文档与探针期望 |
| 甲1 | 撤 `Get-SplitWaves` 接线，`plan` 回到总片数 | 串行链重新被判 `SPLIT_INFEASIBLE`（回到现状） |
| 甲2 | 撤子卡 manifest 派生与搬运段 | 波次仍正确，但依赖片拿不到产物 ⇒ **必须同时回到乙或甲1 的「半件」声明**，不得报「依赖可执行」 |

★ 回滚后 `join.json` 的 `waves`/`skipped` 字段可能残留：按「不追溯改历史」保留，文档标注口径。

---

## 6. 文档回写清单

1. [DESIGN.md](./DESIGN.md)：实施偏差回写（§3.2 落点若漂移）。
2. [CHECKLIST.md](./CHECKLIST.md)：逐项留证据（命令输出/run id）。
3. [OPEN-ISSUES.md](../d6-agent-standard/OPEN-ISSUES.md) 的 `O-184` 行：按期更新状态（乙落 / 甲1 落 / 甲2 落）。
4. [docs/research/README.md](../../docs/research/README.md) C 节：调研文档索引行。
5. 如涉及跨批次经验：`spec/d6-agent-standard/DEVELOPMENT-LOG.md` 追加一条（**不**另建日志）。
