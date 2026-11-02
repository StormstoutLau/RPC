# 设计：片间依赖边从「只记录」到「可执行」

---

id: graph-shard-dependency-DESIGN
type: design
version: 1.0
status: draft
date: 2026-10-31
depends: [research-graph-shard-dependency-2026-10-31]
upstream: [ADR-0004, ADR-0009]

---

> **Feature**: 把 `split` 的片间依赖声明（`needs=`）从**观测面**推进为**执行面**：先以 fail-closed 拒绝「声明了却忽略」，再按 Kahn 波次派发并把容量判据改为「单层最大宽度」，最后补上「片产物 → 依赖片输入」的搬运链。
> **创建日期**: 2026-10-31
> **状态**: draft（Step 3 设计稿；§1.3 两条语义裁定**待用户确认**，未确认前不实施乙）
> **Spec 步骤**: Step 3（设计文档）→ Step 4（设计评审）
> **基于调研**: [片间依赖边从观测到执行 · 调研](../../docs/research/2026-10-31_片间依赖边从观测到执行_调研.md)（本设计的**全部事实与外部锚点来源**）
> **台账**: [O-184](../d6-agent-standard/OPEN-ISSUES.md)
> **实施展开**: [IMPLEMENTATION.md](./IMPLEMENTATION.md) · 验收门: [CHECKLIST.md](./CHECKLIST.md)

---

## 1. 目标与非目标

### 1.1 目标

| # | 目标 | 判据（可机判） |
|---|---|---|
| G1 | **乙·响亮拒绝**：带 `needs=` 的 `split` 在派发前被拒 | 退出码 2，日志含 `SPLIT_NEEDS_UNSUPPORTED`，**零 `Start-Process`** |
| G2 | **甲1·波次派发**：边决定先后，容量判据改为**单层最大宽度** | 三层串行链（宽度 1）不再 `SPLIT_INFEASIBLE`；宽度超容量才 exit 18 |
| G3 | **甲1·失败传播**：上游非 0 ⇒ 依赖它的片**不派发**且响亮报告 | 日志含 `SPLIT_SKIPPED`；整体退出码非 0（沿用既有 1，不新增码） |
| G4 | **甲2·产物搬运**：依赖片**真拿到**上游产物 | 依赖片 runDir / `.attach/` 出现上游件；缺失或摘要不符 ⇒ 响亮失败 |
| G5 | **零声明零变化**：不带 `needs` 的 `split` 行为逐字不变 | 既有 `O141-split①–⑨`、`NEEDS①–⑮` 夹具全绿，派发序与日志不变 |

### 1.2 非目标

1. **不做** 跨 `run` / 跨卡 / 跨项目的依赖（射程只到**同一次 `split` 内的片间边**）。
2. **不做** 可写任务扇出：`Invoke-SplitTask` 的 `SPLIT_ABORT`（`writable merge not supported`）**保留不动**（结论契约 §6.2-5）。
3. **不引入** 常驻调度器 / 中心元数据库（与 [ADR-0004](../../adr/ADR-0004-统一管理入口为唯一管理面.md)「零自加载 · 无 daemon」冲突）。
4. **不做** 共享产物仓库 / 全局中枢：三站互不可见，搬运**只由主控显式发起**（同 ADR-0004）。
5. **不做** 按输入哈希跳过已完成片（M5 幂等）—— 本设计只做**摘要校验**，复用登记为后续。
6. **不改** `Resolve-SplitJoin` 的判定核：**禁阈值/相似度**（`O-126`），「同主体相反结论」仍然**只报出**（领域语义，[ADR-0013](../../adr/ADR-0013-跨仓库使用本框架的准入与派发分界.md) 的 D5 边界）。
7. **不新增** 数字退出码：整体失败沿用 `1`（既有 `SPLIT_PARTIAL_FAIL`）。
8. **不新增** `after=`（仅排序边）：外部是一等公民（Make `|` / Ninja `||` / Prefect `wait_for` / Argo `dependencies`），但本仓**无真实用例**；`needs=` 只承载数据依赖，纯排序需求**当前不表达**（调研 §8.3 / §6-7）。

### 1.3 需要用户确认的两条语义裁定

> 这两条与 **2026-10-16「方案 a」**的原语义**互斥**，乙落地即撤销旧口径。**未确认前**只落丙（维持观测）+ 本文档。

| # | 旧口径（2026-10-16 方案 a） | 本设计采用 | 理由 |
|---|---|---|---|
| S1 | `needs=` = 「声明的血缘/读序」，**对执行零影响** | `needs=` = **数据依赖**：上游必须成功、产物必须可传，下游才可跑；**回收 0 件 ⇒ 响亮失败**（不把「无数据」静默放行） | 调研 §8：外部把「仅排序」与「数据」当两种边，**先例是新增边类型而非改判**；但本仓旧语义是**什么都不做**（不是「已排序」），且全仓唯一真卡（`needs-decl-probe`）**本意即数据依赖** ⇒ 改判面可控。**「仅排序」(`after=`) 本批不做**（§1.2-8 / 调研 §6-7） |
| S2 | 失败传播未定（外部有 `all_success`/`one_failed`/`all_done`） | **固定 `all_success`**：上游非 0 ⇒ 下游不派发；**`SPLIT_SKIPPED` 与失败分开报**，`join.status` 不因 skip 变 `ok`，整体退出码非 0 | 调研 §9：十系统默认压倒性 `all_success`/failFast；「跳过」与「失败」在外部一律独立状态（Airflow `upstream_failed` / Argo `Skipped`·`Omitted` / GHA `conclusion=skipped`）；`all_done`/`afterany` 只服务清理/汇总节点，本仓无此节点 ⇒ 可配置不做 |

★ **补充调研已并入（2026-10-31）**：S1 → 调研 §8（两类边的一等公民清单 + **本仓存量用法核查**：全仓仅 1 张真卡使用 `needs=`，其本意即数据依赖）；S2 → 调研 §9（十系统默认值与「skipped ≠ failed」证据；Argo 的 Skipped 放行属分支语义，**不照搬**）。

★ 确认方式：用户在台账 `O-184` 上批复；未批复则本设计停在 Step 4，**不进入实施**。

---

## 2. 现状事实（读码，2026-10-31）

### 2.1 已有三件

| 件 | 落点（**函数名**，不用行号） | 做到 | 没做到 |
|---|---|---|---|
| 卡面解析 | `Expand-DecomposeSubject` | 剥 `subject=` / `needs=` 前缀；旧语法逐字不变 | 不推断语义、不归一 |
| 完整性校验 | `Resolve-SplitNeeds` | 悬空 / 歧义 / 自指 / 环（Kahn）⇒ `SPLIT_NEEDS_FAIL` exit 2，早于模型解析与 `Start-Process` | **不排波次、不阻断、不传产物** |
| 声明式汇聚 | `Resolve-SplitJoin` | `subject` 分组 + `undeclared` fail-closed；`join.json` | 只到**声明层** |

### 2.2 派发链缺口

`Invoke-SplitTask` 的实际顺序：解析 `decompose:` ⇒ `Resolve-SplitNeeds`（只校验）⇒ `Get-SplitDispatchPlan` ⇒ **一次性** `Start-Process` 全部子卡 ⇒ `WaitForExit` ⇒ 合并。
⇒ `plan.assignments` 与派发循环**都不读 `needs`**；`needs_graph` 只写进 `join.json` 且标注「派生非真值」。

### 2.3 容量判据错配

`Get-SplitDispatchPlan` 的 `ok = (ShardCount <= StationPool.Count * LegsPerStation)`。
⇒ 串行链（层宽 1、共 3 片）与无依赖 3 片得到同一结论；外部九系统**没有任何一个**因图节点数 > worker 数拒绝整张图（调研 §2.1）。

### 2.4 产物通道缺失（本设计的**关键前提**）

| 事实 | 证据 | 后果 |
|---|---|---|
| `merged-output.txt` = 各 `shard$i.log` 拼接 | `Invoke-SplitTask` 合并段 | 「汇聚」是**日志拼接**，不是片产物归并 |
| 子卡 front-matter 不复制 `evidence-manifest` | 子卡生成段只复制 `model/sensitivity/readonly/timeout-s/accept/accept-golden/cli/complexity/task-type/isolate-xdg` | 片的 `out/` 声明件**没有回收触发点** |
| `Invoke-EvmStatePull` 只在单任务 collect 被调 | 收集段 | 波次之间**没有**「回收上游产物」的动作 |

⇒ **只做甲1 等于「顺序剧场」**：顺序对了，数据仍拿不到。甲2 是让依赖成立的**唯一一刀**。

---

## 3. 架构设计

### 3.1 三阶段总览

```
阶段乙（G1）：needs 存在 ──▶ SPLIT_NEEDS_UNSUPPORTED [exit 2]  （零子进程）
阶段甲1（G2/G3）：decompose → Resolve-SplitNeeds → Get-SplitWaves（Kahn 分层）
                  → 逐波：宽度 ≤ capacity ? 派发 : SPLIT_INFEASIBLE[exit 18]
                  → 上游 rc≠0 ⇒ 下游标记 SPLIT_SKIPPED（不派发）
阶段甲2（G4）：波次边界 → 主控回收产片 runDir 产物 → 依赖片以 --Attach 注入
                  → 摘要不符 / 上游零产物 ⇒ 响亮失败
```

### 3.2 模块与落点

| 模块 | 职责 | 落点 | 类型 |
|---|---|---|---|
| `Resolve-SplitNeeds` | 唯一解析完整性校验点；**新增输出波次所需的 `waves` 不再在此算**（单一定义点：由 `Get-SplitWaves` 算） | [agent-cli.ps1](../../ops/station-bin/agent-cli.ps1) | 不改判定核（仅消费其 `edges`） |
| `Get-SplitWaves` | **纯函数**：已解析边 ⇒ Kahn 分层 `waves[]` + `width_max`；坏输入 ⇒ `ok=false` | 同上 | **新增** |
| `Get-SplitDispatchPlan` | 容量判据：参数由「总片数」改为「**单波最大宽度**」 | 同上 | 修改（参数名 `-ShardCount` → `-Width`） |
| `Invoke-SplitTask` | 派发主体：乙闸 / 波次循环 / 跳过传播 / 波次边界回收 | 同上 | 修改 |
| 子卡 front-matter 生成 | 主卡有 `evidence-manifest` 时**派生复制**到子卡 | 同上（子卡生成段） | 修改 |
| `Invoke-EvmStatePull` | 片产物回收 | 同上 | **复用**（不改） |
| `--Attach` 注入 | 依赖片派发时把上游件挂进 `.attach/` | 同上（`Invoke-Task` 既有通道） | **复用**（不改） |

### 3.3 数据流

1. 主卡 `decompose:` 条目 ⇒ `Expand-DecomposeSubject` ⇒ `{subject, needs[], task}`。
2. `Resolve-SplitNeeds -Decls` ⇒ `{ok, edges[], …}`（既有）。
3. `Get-SplitWaves -Edges <edges> -ShardCount <n>` ⇒ `{ok, waves=[[i…],…], width_max, reasons}`。
4. 每波：`Get-SplitDispatchPlan -Width <本波片数>`；超容量 ⇒ `SPLIT_INFEASIBLE` exit 18。
5. 波内派发：沿用既有 `Start-Process` 循环，**站位仍 round-robin**（不改选路）。
6. 波末：`Invoke-EvmStatePull -Subjects <子卡 manifest> -RunDir <片 runDir> -HostName <站>` 回收。
7. 依赖片派发时 `--Attach <上游片产物目录>`；子卡任务结束后比对 `digest`（manifest 声明了才比）。

### 3.4 控制流（失败传播）

- 片 `rc ≠ 0` ⇒ 该片「失败」；所有 `needs` 指向它的片**不进入任何后续波次**，记 `SPLIT_SKIPPED shard=j needs=<subject> upstream=shard=i rc=<n>`。
- 被跳过的片**不计入 `merged-output.txt` 的成功段**（写占位行 `rc=SKIPPED`），`join.json` 记 `skipped[]`。
- 整体退出码：存在失败或被跳过 ⇒ `1`（沿用 `SPLIT_PARTIAL_FAIL`）。
- **不**把「跳过」读成「通过」；`join.status` 不因跳过而变 `ok`（新增 `skipped_count` 只报数）。

---

## 4. 接口定义

### 4.1 `Get-SplitWaves`（新增纯函数）

```powershell
function Get-SplitWaves {
    param([object[]]$Edges, [int]$ShardCount)
    # 输入：$Edges = Resolve-SplitNeeds 的 edges（@{ from=int; to_subject=str; to_idx=int }）
    # 输出：@{
    #   ok       = $true|$false      # 边引用越界 / ShardCount<=0 ⇒ $false（fail-closed）
    #   waves    = @( @(idx…), … )   # 按 Kahn 分层；无边的片落在第 1 波
    #   width_max= [int]             # 各波片数最大值
    #   reasons  = @(…)
    # }
}
```

约束：**唯一**波次计算点；`Invoke-SplitTask` **不得**就地再算一遍（同一事实两处表达 = 本仓头号失败形态）。

### 4.2 `Get-SplitDispatchPlan`（改参数语义）

```powershell
function Get-SplitDispatchPlan {
    param([int]$Width, [string[]]$StationPool, [int]$LegsPerStation)
    # ok = (Width <= StationPool.Count * LegsPerStation)
    # 旧参数 -ShardCount 删除（夹具同步改）；容量数值不变（3 站 × 1 腿）
}
```

### 4.3 `Invoke-SplitTask`（行为契约）

| 输入 | 行为 |
|---|---|
| 无 `needs` | **逐字沿用**现状：一次派发、round-robin、`merged-output.txt` 拼接 |
| 有 `needs`（阶段乙） | `SPLIT_NEEDS_UNSUPPORTED` exit 2，零子进程 |
| 有 `needs`（阶段甲1+） | 按 `waves` 逐波派发；宽度判据；失败传播 |
| 有 `needs`（阶段甲2+） | 同上 + 波末回收 + `--Attach` 注入 + digest 比对 |

---

## 5. 替代方案

### 5.1 方案甲（一次到位：排序 + 搬运 + 判据，选择其**分期形态**）

- 描述：乙/甲1/甲2 一轮全做。
- 优点：语义一次收口。
- 缺点：跨站搬运**未实测**，与排序改动混在一次提交 ⇒ 失败时无法定位是哪一刀。
- 选择理由：**拆三期、每期一提交且绿**（调研 §4 建议）。

### 5.2 方案乙（仅 fail-closed 拒执行，选择为首期）

- 描述：有 `needs` 即拒，零执行风险。
- 优点：把「声明了却忽略」变响亮；夹具成本最低。
- 缺点：依赖**暂不可用**（如实拒绝）。
- 选择理由：先止血，再谈能力；避免「假图」继续存在。

### 5.3 方案丙（维持观测，否决）

- 否决理由：`O-184` 保持开启；「有边不排序 = 假图」照旧；且 `needs` 声明会持续给人以「依赖已生效」的错觉。

### 5.4 方案丁（引入外部 DAG 框架，否决）

- 否决理由：违反 [ADR-0004](../../adr/ADR-0004-统一管理入口为唯一管理面.md)（常驻调度器/中心库）；三站无共享存储（调研 N1/N2）。

---

## 6. 数据结构

### 6.1 `join.json`（扩展，不新造账本）

```json
{
  "n": 3, "declared": 3, "undeclared": 0, "status": "ok",
  "same_subject_groups": [],
  "needs_graph": { "note": "派生非真值（机械由卡面 decompose: 重算）", "edges": [ ... ] },
  "waves": [[1], [2], [3]],
  "width_max": 1,
  "skipped": [],
  "skipped_count": 0
}
```

★ `needs_graph` 的「派生非真值」标注**保留**：`waves` 同样由卡面重算，不是第二个定义点。

---

## 7. 错误处理

| 错误场景 | 处理方式 | 用户可见信息 |
|---|---|---|
| 悬空 / 歧义 / 自指 / 环 | 维持现状：`exit 2`，**早于**模型解析与派发 | `SPLIT_NEEDS_FAIL: … [exit 2] · 未派发任何子进程` |
| 阶段乙：带 `needs` | `exit 2`，零子进程 | `SPLIT_NEEDS_UNSUPPORTED: 本版不支持依赖执行（乙）… [exit 2]` |
| 单波宽度 > 容量 | `exit 18` | `SPLIT_INFEASIBLE: wave #k width W > capacity C …` |
| 上游 rc≠0 | 下游不派发，记跳过 | `SPLIT_SKIPPED shard=j needs=<subject> upstream=shard=i rc=n` |
| 上游**零产物**（甲2） | 下游不派发，响亮失败 | `SPLIT_PRODUCT_MISSING: shard=i 声明 <subject> 但回收 0 件` |
| 摘要不符（甲2） | 下游不派发，响亮失败 | `SPLIT_DIGEST_MISMATCH: shard=i <path> expected=… actual=…` |
| 回收/注入通道失败 | 中止后续波次（fail-closed） | `SPLIT_TRANSFER_FAIL: …` |

★ 全部**不静默**：任一失败都不得被读成「通过」。

---

## 8. 不变式（Invariants）

1. **坏声明先于一切副作用**：`SPLIT_NEEDS_FAIL` / `SPLIT_NEEDS_UNSUPPORTED` 必在任何 `Start-Process` 之前返回。
2. **零声明零变化**：无 `needs` 的卡，派发序、日志行、退出码与现状**逐字一致**。
3. **唯一计算点**：卡面解析 = `Expand-DecomposeSubject`；波次 = `Get-SplitWaves`；容量 = `Get-SplitDispatchPlan`。三处均**禁止就地再实现**。
4. **并发是闸门不是准入**：宽度超容量 ⇒ 拒；图总数不构成拒绝理由。
5. **上游失败不被空输入遮掩**：下游不派发，绝不拿空/半成品硬跑。
6. **产物只搬声明件**：搬运白名单 = `evidence-manifest.subjects[].state`（`Invoke-EvmStatePull` 既有收敛），不做任意目录拷贝。
7. **不新增常驻件**：无 daemon、无第二管理入口、无新退出码。
8. **文档不引行号**：新增/修改的 spec 与代码注释一律用**函数名**定位。

---

## 9. 幻觉排除审查（Step 4）

- [x] 设计决策可追溯到调研（§1.5 三条前提更正、§2.1 九系统、§3 可迁移 M1-M5）
- [x] 无未经验证的假设：甲2 的跨站搬运成本与失败形态**已登记为未实测**（调研 §6-1/2），不作「可行」结论
- [x] 不把「拓扑排序」写成「依赖已可执行」（调研 §0-2 / §1.4）
- [x] 至少列 2 个替代方案并各给否决理由（§5.2/5.3/5.4）
- [x] 职责边界：只读扇出；可写 merge 与「谁覆盖谁」仍在射程外（§6.2-5）

---

## 10. 对实施的输入

### 10.1 关键工程约束

1. **先验红**：每期先让既有夹具（或新增反例）**在旧实现上红**，再改代码。
2. `agent-cli.ps1` 必须保持 **UTF-8 BOM**（`ps1-bom` 门禁），编辑后核对。
3. 夹具加在 [_fm_golden_test.ps1](../../ops/station-bin/_fm_golden_test.ps1) 的既有分组（`O141-split` / `NEEDS` 同区），函数提取清单同步。
4. 门禁：`py -3 ops/rpc_check.py --quick` 全绿；新增 `O-184` 引用行后跑 `py -3 ops/id_site_census.py --emit`。
5. 真站验证必须**真跑**：离线夹具只证明判据与接线顺序，不证明跨站搬运（调研 §5 尾注）。

### 10.2 风险与缓解

| 风险 | 缓解 |
|---|---|
| 现有正向探针 `needs-decl-probe` 由「能跑」变「被拒」 | 乙期同步改期望并以先验红证明；探针卡面加注「乙期后应被拒」 |
| 甲1 被误读为「依赖已可执行」 | DESIGN/CHECKLIST/日志文案逐字写明「顺序正确 ≠ 数据可用」；G4 未绿前不得发布该结论 |
| 波次间主控开销吃掉并行收益 | 登记为未实测（调研 §6-2）；甲2 真跑时记墙钟 |
| 摘要校验引入假红（路径/换行差异） | 只比 manifest 显式声明 `digest` 的件；未声明则不校验（但记 `digest=undeclared`） |
| 子卡继承 manifest 后单任务路径变化 | 仅在**有 `needs`** 时才派生；无 `needs` 子卡 front-matter 逐字不变（护不变式 2） |
