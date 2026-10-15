# `split` 分片依赖声明（`needs:`）—— 设计与实施方案

- **日期**: 2026-10-16
- **性质**: **设计与实施方案**（spec workflow：设计 → 实施 → 审计；**先落档、后动手**）
- **授权**: 用户 2026-10-16「按这个方案来」（承当日「社区 agent 编排调研」里 ② 的 `needs:` 小步）
- **目标**: 给 `decompose:` 的分片补上**「谁依赖谁」的声明观测面**（★ **收窄口径**：D7 那条缺口的原话是「改源→标脏→**拓扑传播**」；本批**只记血缘、不做传播** ⇒ **不构成 DAG / 失效机制**）+ 一条**可判红的完整性校验**
  ⇒ ★ **不建调度器、不做抢占**（那两者撞 ADR-0004 唯一管理面 / O-18 单并发 / 证据链文化）
- **真值源**: 卡面 `decompose:`（解析在 `agent-cli.ps1` 的 `Get-FrontMatter`）· 判据落体 = `Expand-DecomposeSubject`（**唯一解析点**）
- ★ **裁决点**: **D1（见 §2）—— ✅ 已裁 (a)（2026-10-16）**。其余三条写死。

---

## 0. 一屏

| 项 | 现状（E1） | 本方案 |
|---|---|---|
| 分片声明形态 | 每片一个**字符串**，可选前缀 `subject=<X> \| <task>` | 追加**可选**前缀 `needs=<s1,s2>`（附加式） |
| 依赖表达 | **无**（全仓无 `needs`/依赖运行时字段） | `needs` = **声明的血缘/读序**（★ **不是执行顺序**，见 D1） |
| 校验 | `Resolve-SplitJoin` **只**判 `subject` 是否声明 | 新增 `Resolve-SplitNeeds`：引用**恰被一片**声明 · 禁自指 · 禁环 |
| 派发 | `Start-Process` 并行起（每片一子进程） | ★ **一字不改**（`needs` 对执行**零影响**） |
| 失败点 | 现有仅 `SPLIT_REQUIRES_2P` / readonly 检查 | 校验在**任何 `Start-Process` 之前**（最便宜的失败点）⇒ 点名消息 + `exit 2` |

**改动面**：`agent-cli.ps1`（**1 处解析扩展 + 1 个纯函数 + 1 处调用**）+ 夹具/测试（含**先验红**）+ 台账/DEV-LOG/手册各一句。

---

## 1. 设计依据（E1，2026-10-16 实读）

| # | 事实 | 位置 |
|---|---|---|
| F1 | `decompose:` 是卡面 front-matter 的**有序字符串列表**（逐条 `.Trim()` 原样收，**不解析**） | `agent-cli.ps1` L1250-1253 / L1326 / L1334-1335 |
| F2 | `Expand-DecomposeSubject` = **唯一解析点**，前缀语法 `subject=<X> \| <task>`（**可缺省**）；无前缀 ⇒ `subject=''` ⇒ join 侧计「未声明」 | `agent-cli.ps1` L3886-3900 |
| F3 | `Resolve-SplitJoin` = **纯函数**：按 `subject` **字符串全等**分组，**禁阈值/相似度**（O-126）；`subject` 缺 ⇒ 报「未声明」且**禁读成"无冲突"** | `agent-cli.ps1` L3902-3928 |
| F4 | ★★ **分片是信息隔离的**：契约 §6.2-2 逐字「片间**不共享锚点**」；每片在**不同站 / 不同工作区**并行跑 ⇒ **分片之间物理上拿不到彼此的产物** | `agent-cli.ps1` L3904-3905（契约 §6.2） |
| F5 | `Invoke-SplitTask`：要求 **≥2 片**（否则 `SPLIT_REQUIRES_2P` + exit 2）· **只对 readonly 卡**有效 · 片→站 `Pool[i % 3]` · 容量 3 = 3 站 × 1 腿（**派发策略上界，非物理上界**） | `agent-cli.ps1` L3952 / L3960 / L3966-4001 |
| F6 | 派发 = `Start-Process` **并发**起全部子进程 → `WaitForExit` → 收集 → merge → `join.json` | `agent-cli.ps1` L4026-4084 / L4087-4114 / L4136-4137 |
| F7 | 退出码：任一片 `rc≠0` ⇒ `SPLIT_PARTIAL_FAIL` + `return 1`；否则 0（**join 的 `undeclared` 只报出、不改退出码**） | `agent-cli.ps1` L4149-4153 |
| F8 | 本仓**头号假防线形态** = 「**声明了却无人读**」（点名：`O-157` 声明了未接线 / W1a「声明 = 假防线」/ `memory-gates`） | `OPEN-ISSUES.md` O-157 |
| F9 | 既有**"派发前当场校验、未过即拒"**的先例 = `require-gate`（O-90，未过即拒 rc=3） | 手册 §2a.5 / `agent-cli.ps1` |

---

## 2. 设计（四条决策；D1 已裁 (a)）

### ★★ D1 · `needs` 的语义 = **声明的血缘/读序，不是执行序**（**✅ 已裁 (a) · 2026-10-16**）

**证据（F4）**：split 的每片在**不同站 / 不同工作区**并行跑、**互不可见**（契约 §6.2-2「片间不共享锚点」）。
⇒ **分片之间在结构上不可能有"运行时数据依赖"**（片 B 拿不到片 A 的产物）。
⇒ 若把 `needs` 实现成「依赖未满足就不派」，等于**声明一个机制交付不了的语义** —— 正是 F8 那类**假防线**。

**两条诚实出路**（请裁其一）：

- **(a)【本方案推荐 · 其余章节按此写】**：`needs` 定义为**声明的血缘/读序** —— 只在 `join.json` **记录** + 校验**引用完好性**（引用可达 / 恰一片 / 无自指 / 无环）；**对执行零影响**；卡面提示与手册**加粗写「不是执行顺序」**。
  - ★ 它**有真消费点**（"引用完好性"是一条**可判红**的判据）⇒ **不落** F8 的"无人读"形态。
- **(b)**：**不做**。台账登记「**分片间依赖 = split 模型之外**；**顺序 `task` 派发才是依赖机制**」+ 写明**再触发条件**（出现"必须先有片 A 结果才好派片 B"的**真实实例**时再立）。

> ⇒ **已裁（2026-10-16）= (a) 落地**：它比 (b) 多一张**可判红的完整性判据**，并给"依赖表达"补一个**声明观测面**（★ **不构成 DAG/传播** —— 见顶部"目标"的收窄口径）；成本 = 1 个纯函数 + 1 处调用。

### D2 · 引用模型 = `subject` 名（写死）
- 引用**必须恰被一片**声明（重复 `subject` ⇒ **歧义** ⇒ **拒**，与 `Resolve-SplitJoin` 的 `same_subject_groups` 立场一致：重复只报出、引用则判红）。
- **禁自指**（`needs` 不许含自己的 `subject`）· **禁环**（A→B→A ⇒ 拒）。
- **不做归一/推断**（"这俩是不是同主体"属**语义**判断 ⇒ 归声明面；承 O-126 禁阈值/相似度）。

### D3 · 校验点 = `Invoke-SplitTask` 解析完 `$shards` 后、**任何 `Start-Process` 之前**（写死）
最便宜的失败点（**不碰引擎、不碰站、不写站上盘**）。失败 ⇒ 出**点名**消息（哪个引用、缺哪片）+ `exit 2`（与 `SPLIT_REQUIRES_2P` 同族）。

### D4 · 解析走 `Expand-DecomposeSubject` 前缀语法的**附加式**改动（写死）
- 旧 `subject=X | task` 与**裸字符串**行为**逐字不变**（测试钉住）。
- `Get-FrontMatter` **零改动**（`needs` 骑在 `decompose` 列表字符串里，F1 的 raw `.Trim()` 天然容纳）。
- **不建波次 / 拓扑调度**（波次 = 调度器种子 ⇒ 越界；登记再触发条件即可）。

---

## 3. 接口定义

| 名字 | 签名 | 职责 |
|---|---|---|
| `Expand-DecomposeSubject` | `(string) → @{subject; needs[]; task}` | **扩展**：多解析一个可选 `needs=<s1,s2>` 前缀；无 ⇒ `needs=@()`（向后兼容） |
| `Resolve-SplitNeeds` | `(decls) → @{ok; dangling[]; ambiguous[]; selfref[]; cycle[]; status}` | **新纯函数**（离线可测）：校验引用完好性（D2 四规则） |
| `Invoke-SplitTask` | — | 在首个 `Start-Process` **之前**调用校验；打 `SPLIT_NEEDS:` 行；`join.json` 增记 `needs_graph`（观测用） |
| 失败码 | `2` | 声明/引用错误（沿用既有"参数/声明错误"码） |

**卡面形态**（附加式，存量卡零影响）：
```
decompose:
  - subject=风控口径 | needs= | 讲清本片的风控口径
  - subject=回测假设 | needs=风控口径 | 讲清回测假设（与风控口径有关）
```

---

## 4. 实施清单

| # | 文件 | 改动 |
|---|---|---|
| I1 | `ops/station-bin/agent-cli.ps1` | ① `Expand-DecomposeSubject` 加解析 `needs=`；② 新增纯函数 `Resolve-SplitNeeds`；③ `Invoke-SplitTask` 在**首个 `Start-Process` 前**调用 + 打 `SPLIT_NEEDS:` + `join.json` 增记 |
| I2 | `ops/station-bin/_fm_golden_test.ps1` | 加断言：解析器在 · 校验调用在 · **顺序断言**（`校验 IndexOf < 首个 Start-Process`，同 PROJ③ 式）+ **先验红**（摘掉校验调用 ⇒ 必红）+ **向后兼容钉住**（旧语法逐字不变） |
| I2′ | **dogfood 探针卡**（★ **真跑要求**的载体） | 新增 `spec/d6-agent-standard/dogfood-cards/needs-decl-probe.md`（**正向** · 2 片 · 引用可达）+ `…/needs-decl-dangling.md`（**负向** · 悬空引用）—— 供 §5.0「真跑层」使用 |
| I3 | `tests/`（纯函数离线单测） | `Resolve-SplitNeeds` 正/反例族（dangling / ambiguous / selfref / cycle）+ **先验红** |
| I4 | 台账 `OPEN-ISSUES.md` | `O-160`（本项）登记；**O-153 纪律**（条目含独有锚串、表内用**全角** `｜`） |
| I5 | `docs/DEV-LOG-014-*.md` | §107 执行记录（证据级引用） |
| I6 | 手册 `split` 节 | 一句：`needs` = **声明的血缘/读序，不是执行顺序** |

**不动**：`Resolve-SplitJoin`（只**新增**校验器，**不改**其语义）· 派发/收集/merge 全链 · `Get-FrontMatter` · 站上任何东西。

---

## 5. 验证收口

### 5.0 两层验收（★ **离线层不得替代真跑层**）

**离线层（本批内可完成）**
1. **先验红**：摘掉 `Resolve-SplitNeeds` 的调用 ⇒ 夹具/测试**必红**（证判据不恒真）。
2. **向后兼容**：旧语法（`subject=X | task` / 裸字符串）解析结果**逐字不变**（夹具钉住）。
3. **顺序不变量**：**校验调用在首个 `Start-Process` 之前**（机器可判的 IndexOf 顺序断言，同 PROJ③ 式）。
4. **前缀不落片正文**：夹具钉住「`needs` 前缀**不进** `$shardSpec.task`」（承吃狗粮复审 `a-prefix`；摘掉剥前缀逻辑 ⇒ 必红）。
5. 全量门禁 **PASS**（预期 46 绿 / 3 黄 / 0 红）+ `py-tests` 全绿。

**★★ 真跑层（★ 本批的「真跑要求」—— 死特性闸门）**
6. **一张带 `needs` 的卡真跑 `split` 全链**（探针卡见 §5.1）—— 必须**真派发**，**不得**只靠单测/夹具：
   - **正向**读数（逐字）：`SPLIT_NEEDS: … ok` · `SPLIT_DONE` · `join.json` 含 `needs_graph`（**须标"派生非真值"**）；
   - **负向**读数：一张含**悬空引用**的卡 ⇒ **在任何派发之前** `exit 2`（站上零动作、零引擎占用）。
7. ★ **未跑则不得声称已闭环**：同 `executor-trace` 的自家口径「**未经真派发 ⇒ 覆盖率未验**」；
   **不得**用 `cluster.py agent audit --accept` 把它抹成"存量"。
   ⚠ **前置**：真跑**需先加载引擎**（`cluster.py load`）—— 当前三站已 `unload`。
8. 若本批**不跑**：在台账 `O-160` 的状态格**登记为未实测**，并写明**解锁条件** = "一次引擎加载窗口内跑 §5.1 两卡"。

### 5.1 真跑探针卡（形态；由 §4 的 I2′ 创建）
- **正向** `dogfood-cards/needs-decl-probe.md`：`readonly: true` · ≥2 片 · 至少一片带 `needs=<另一片 subject>`（**引用可达**）。
- **负向** `dogfood-cards/needs-decl-dangling.md`：同上，但引用一个**不存在**的 `subject` ⇒ 期望 `exit 2`。
- 运行：`ops\station-bin\agent-cli.ps1 split <proj> --card <card>`（**真派发**）。

### 5.2 ★ 真跑读数（2026-10-16 · **已执行** · 逐字）

**负向卡**（`needs=不存在的主体`）：
```
SPLIT_NEEDS_FAIL: shard2 needs '不存在的主体'（**未声明** ⇒ 无此片） [exit 2] - 分片依赖声明的引用坏了；**未派发任何子进程**
EXITCODE=2
```
★ 该卡 model 刻意是**无效值**（`needs-probe-invalid`）⇒ **早于 model 解析**即拒 ⇒ 证明"**因 needs 而拒、非因未知模型**"（无假绿）。

**正向卡**（片2 `needs=路由层`）：
```
SPLIT_NEEDS: n=2 with_needs=1 status=ok
SPLIT_SHARD_DONE[1] rc=0 ok=True
SPLIT_SHARD_DONE[2] rc=0 ok=True
SPLIT_JOIN: n=2 declared=2 undeclared=0 status=ok
SPLIT_DONE shards=2 all_ok=True wall_ms=63048
EXITCODE=0
```
`join.json.needs_graph` = `{edges:[{from:2,to_subject:"路由层",to_idx:1}], note:"派生非真值（机械由卡面 decompose: 重算）"}`

⚠ **前置（如实）**：本卡 `model: ultra`（**出网**）⇒ **无需加载本地引擎**；`accept:` **非空**（否则 `TaskContract` 硬拒 exit 3，见 2026-10-13「转硬拒」）。

---

## 6. 明确**不在**本批（防越界）

- ★ **不做波次 / 拓扑调度**：依赖声明**不改变**并行执行（D1(a) 的"零影响"是刻意的）。
- ★ **不做抢占**：与「证据链不可篡改 + 跨站各 1 并发（O-18）」冲突（前期评估已判）。
- ★ **不新建管理面**：ADR-0004 唯一管理面 = `ops/cluster.py`。
- **不改** `Resolve-SplitJoin` 既有语义（只新增）。
- **不动**存量卡（`needs` 可缺省）。

---

## 7. 审计（Step 4）

- [x] 决策可溯源 §1 F1–F9（全部 E1 实读 / 台账原文）
- [x] 四条决策：**D1 已裁 (a)** + D2/D3/D4 **写死**
- [x] **不发明结构**（镜像既有前缀语法 `subject=` 与既有 fail-closed 纪律，非新铸）
- [x] 改动面最小（**1 解析 + 1 纯函数 + 1 调用**；全链零改）
- [x] 越界项**显式排除**（§6：波次/调度/抢占/新管理面/改 join 语义）
- ⚠ **风险（如实）**：`needs` 对执行**零影响** —— 其价值集中在"**声明表达 + 完整性判据**"；若你判这仍属"无害但无用"，则走 **D1(b) 不做**。
- ★ **D1 已裁（2026-10-16）= (a) 落地**（用户「按方案 (a) 落地并执行真跑验收」）⇒ 见 §5.2 真跑读数 + §8 执行记录。
- [x] **承「吃狗粮复审」（2026-10-16）**：用本仓失败形态清单过筛 (a)/(b) 断言。★ **已补**：`a1`「真消费点」缺口 ⇒ §5.0 **真跑层**（真派发 + 越前 `exit 2` + `needs_graph` 标派生非真值）+ §4 的 `I2′` 探针卡。
- [x] **复审后的三处已全部收口**：`a2` **已收窄**为"分片**血缘观测面**"（见顶部"目标"与 §2-D1）；`a-ref` **已写明立场差**（`Resolve-SplitJoin` 对重复**只报出** vs 本校验对**引用歧义**判**拒** —— 见 `Resolve-SplitNeeds` 注释 + 夹具 `NEEDS⑪`）；`a-prefix` **已钉**（§5.0 离线层第 4 条 + 夹具 `NEEDS⑮`）。
- ⚠ **复审的决定性读数**：仓内 `decompose:` **零卡声明依赖**（真实用例 4 张），且 `ADR-0013` **早已登记"片间依赖边"缺口**并警告"有序列表 vs 并行派发 ⇒ 依赖理解分叉" ⇒ 按 `O-45`「需求 0」先例，**(b) 更合本仓先例**（除非你确认"近期确有一张会声明 `needs` 的卡"）。

---

## 8. 执行记录（2026-10-16 · 落地 + 真跑验收）

**已实现**（§4 的 I1 / I2 / I2′ / I3）：`Expand-DecomposeSubject` 加 `needs=`（**附加式**，旧语法逐字不变）·
`Resolve-SplitNeeds`（新纯函数）· `Invoke-SplitTask` 在**解析 `$shards` 后、model 解析前**校验 ·
`join.json.needs_graph`（标"派生非真值"）· 夹具 **+18 断言**（`FM_GOLDEN_TEST` 587 → **605/0**）· 两张探针卡。

**真跑读数**：见 §5.2（负向 `EXITCODE=2` · 正向 `all_ok=True` / `EXITCODE=0` + `needs_graph` 在 `join.json`）。

★★ **真跑当场抓到一个回归（`O-161`，非本方案引入）**：
`$PROJECTS` 数据化（`O-159`）后，`split` 的**子进程**（BOM 副本落在 TEMP）**算不出 `$Script:REPO_ROOT`**
⇒ 载 `$Script:PROJECTS` 得**空表**（fail-closed）⇒ 子进程 `unknown/missing project: dogfood (registered: )`。
⇒ **本轮修**：父进程经 **env 传根**（`Start-Process` 继承 env）+ 子进程 INIT **优先取它**（无 env ⇒ **逐字回退旧算法**）
⇒ 夹具 `O161①-③` 钉住（含**顺序**断言）。★ 这是 `O-159` 数据化的**第三个消费面**（前两个 = 外壳 / `cluster.py`）。

⚠ **另一处真跑暴露（非回归 · 记录在案）**：`TaskContract.accept` **非空**是 `split` 卡的新硬约束
（2026-10-13「转硬拒」）⇒ 探针卡**必须带 `accept:`**，否则子进程 P0 硬拒 `exit 3`。
