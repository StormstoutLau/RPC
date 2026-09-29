# A 清单（A1–A6）：设计底稿勘误与落地排期（2026-09-29）

> **本文什么不做**：不重复 [OPEN-ISSUES.md](OPEN-ISSUES.md) 的证据链、不重述 [ADR-0009](../../adr/ADR-0009-D6与D7分界判据.md) 的判据原文
> ⇒ 只做三件事：**① 把两批吃狗粮出的 6 份设计提案勘误为可用底稿**（§1）；**② 给每项落地排期**（§2）；
> **③ 点名仍缺的裁定**（§3）。
> **会不会过期**：会 —— **每落地一项就回来改一次**。
> **单一真值边界（不复制）**：8 项灰色地带的归属 = `ADR-0009` §3；台账 = `OPEN-ISSUES.md`；能力判定 = [capability-inventory.yaml](../../inventory/capability-inventory.yaml)
> ⇒ 本文只**引用**，**不抄第二份**（"同一事实两处表达"是本仓头号失败形态）。
> **射程声明（如实）**：本文件名**不匹配** `U[0-9]-*.md` / `D7-PROTOCOL-*.md` ⇒ **不进** `spec-untested` 射程；文件名头 20 行**无** `status:` 声明 ⇒ **不成** `doc-status` 位点；**进** `doclinks` 射程。

---

## 0. 一览（A1–A6 ↔ 卡 ↔ run ↔ 判读）

| 项 | 缺口（能力 id / 出处） | 卡 | 站·模型 | run | 产物（行数） | 主控判读 |
|---|---|---|---|---|---|---|
| **A1** | `ADR-0009` §待验证项「判据在派发引擎中的实际求值 = 无代码」 | `imp1-boundary-judge-wiring.md` | A · `ultra-a` | `202609291929091622` | `boundary-judge-design.md`（31） | ⚠ **8 项灰色地带表 4/8 与 `ADR-0009` §3 不符**（§1.3） |
| **A2** | `executor-trace`（**absent**） | `imp4-executor-trace-design.md` | A · `ultra-a` | `202609291939005729` | `executor-trace-design.md`（32） | ◐ 可用，但采集点**自标"不在本机群"** ⇒ 须就地核实 |
| **A3** | `derived-readonly-view`（**absent**） | `imp5-derived-view-design.md` | B · `ultra` | `202609291939006123` | `derived-view-design.md`（38） | ⚠ **自相矛盾**（`generated-at` vs 逐字节一致）（§1.2） |
| **A4** | `cell-safety`（**absent**） | `imp2-cell-safety-judge.md` | B · `ultra` | `202609291929092530` | `cell-safety-design.md`（94） | ⚠ **参考实现 2 处缺陷 + 1 处自报不实**（§1.1） |
| **A5** | `determinism-idempotence`（**absent**） | `imp3-determinism-idempotence-judge.md` | C · `ultra-c` | `202609291929092399` | `determinism-design.md`（28） | ✅ 可用（噪声 7 类 + `determinism: n/a` 纪律） |
| **A6** | `u4-invalidation` **未实测第 10 条**（`ops/id_storage_census.py` 自注「只产出决策，不执行重算」） | `imp6-invalidation-executor-design.md` | C · `ultra-c` | `202609291939006697` | `invalidation-executor-design.md`（41） | ✅ 质量最好（6 步形态 + 三态 + 防假绿硬约束） |

> 6 卡均 `sensitivity: public` · **无附件** · `readonly: false`；批次日志 `tmp/dogfood-ws/agent-out/_batch/`。
> ⚠ **覆盖面如实标注**：6 卡全走 `ultra`（**同一 id** `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`）的**不同站**
> ⇒ **只跨站、未跨族** ⇒ 按 `D7-P0-3` 的 **J-1** 口径只是"同族多实例"，**不构成认知多样性**（见 §3.1）。

---

## 1. 底稿勘误（本轮已修，3 处）

> 口径：**勘误只改"模型产物里与真值/自洽性冲突的部分"，不改模型的实质设计**。
> 判读**不采信模型自报**（卡里未给真值）⇒ 以下每条都是主控**按原文独立复核**得出。

### 1.1 A4 · `cell-safety`（imp2）—— 2 处机械缺陷 + 1 处自报不实

产物 `## 参考实现` 的 `check_table_columns` 有两处会让判据**自己失真**：

**缺陷 ①（假红）—— `_count_cols` 只数"非空"单元格**：

```python
# 原（第 76 行）
return sum(1 for p in parts if p.strip() != "")
# 修
return len(parts)
```

理由：`| a |  | c |` 是 **3 格**（中间是**空单元格**，不是"没有格"）。原实现把它数成 2 ⇒ 与表头 3 列不符 ⇒
**把合法表判成违规**（假红）。⚠ 且 `## 判据定义` 明写"有效列数 = …**非空**单元格数" ⇒ **定义与正确语义同错**，
须一并改为"**按未转义竖线分割后的单元格数**（空单元格计入）"。

**缺陷 ②（假绿）—— 分隔行查找跨空行**：

```python
# 原（第 33-38 行）：向后扫到"第一个以 | 开头的行"再判它是不是分隔行
j = i + 1
while j < len(lines) and not lines[j].strip().startswith("|"):
    j += 1
if j >= len(lines) or not _is_sep(lines[j].strip()):
    i += 1
    continue
# 修：GFM 的分隔行必须【紧邻】表头行的下一行 ⇒ 不跨行去找
if i + 1 >= len(lines) or not _is_sep(lines[i + 1].strip()):
    i += 1
    continue
```

理由：原实现允许"表头行 → 空行/散文 → 某个 `|---|`"也被当成一张表 ⇒
**判了一个 GFM 里并不存在的表格**（既可能假绿、也可能把别的块的错误算到这张表上）。GFM 要求分隔行**紧邻**。

**缺陷 ③（自报不实，非代码缺陷）—— `## 假绿` 第 2 条与实现矛盾**：
原文称"表格仅有表头+分隔行、无数据行 ⇒ 返回空列表 ⇒ **漏掉「表头列数≠分隔列数」**"。
但代码在数据行循环**之前**（第 40-41 行）**已经**比对 `sep_cols != header_cols` ⇒ 该情况**会**被报出 ⇒ 该条**不成立**。
⇒ 须替换为真实假绿，建议二选一：
- 「**表头行被缩进 ≥4 空格**（GFM 视作代码块）⇒ 本实现 `strip()` 后仍当表格 ⇒ 判了一张并不存在的表」；
- 「**`~~~` 围栏**（本实现只识别 ```` ``` ````）内的伪表格会被当真表判」。

**修后须满足**（原卡的验收面不变）：`## 判据定义` / `## 参考实现` / `## 边界用例` / `## 假绿` **四节名照抄**；
边界用例 ≥4（① 内容含合法竖线 ② 数据行少一格 ③ 代码围栏内 ④ 表头被改坏）；**代码 ≤40 行**。

### 1.2 A3 · `derived-readonly-view`（imp5）—— 自相矛盾（生成时间 vs 逐字节一致）

**矛盾**：`## 视图形态` 把 `generated-at: <RFC3339-UTC>` 列进"**含确定性字段**"，
而 `## --check 判据` 要求"渲染结果与落档**逐字节一致**" ⇒ **每次渲染时间不同 ⇒ `--check` 恒红**。

**处置（选 A）**：
- **A（推荐，本轮采用）**：**从档内移除 `generated-at`** —— 落档视图**只含确定性字段**（`source-hash` / `generator`）；
  生成时间只写**构建日志 / CI 输出**（**不入档、不参与比对**）。
  理由：「逐字节一致」需要"**档内无非确定字段**"这一**充分条件**；而"比对时忽略某一行"的写法会造出
  "哪一行可以忽略"的**第二个定义点**（本仓头号形态）。
- B（不推荐）：保留 `generated-at`，比对前**归一化**该行 ⇒ 弱化了"逐字节一致"，且引入同一第二定义点。

**同步改**：`## 视图形态` 的"含确定性字段" ⇒ "**只含**确定性字段（清单：`source-hash` / `generator`）"。
**其余各节不动**（`--check` 三态退出码 0/1/2 · 防恒真规则 · 假绿 3 条 · 缺料 5 条均可用；
★ 假绿第 3 条"把非确定字段写进视图"在修后**恰好**成为本矛盾的守门条，保留）。

### 1.3 A1 · 分界判据（imp1）—— 8 项灰色地带表 4/8 与 `ADR-0009` §3 不符

产物 `## 灰色地带对照表` 逐行比对 [ADR-0009](../../adr/ADR-0009-D6与D7分界判据.md) §3 ⇒ **4 行不符**：

| 灰项 | 产物写 | `ADR-0009` §3 真值 | 判 |
|---|---|---|---|
| 判官抽检 | D6 · 否/否/是 | D6 · 否/否/是 | ✅ |
| 受理阶段的协商回环 | **D7 · 否/是/否** | D6 · **否/否/否** | ❌ |
| 需求方验收签收 | **D7 · 是/否/否** | D6 · **否/否/否** | ❌ |
| 跨站派发 | **D7 · 是/否/否** | D6 · **否/否/否** | ❌ |
| 站间互审 | D7 · 是/是/否 | D7 · 是/是/否 | ✅ |
| 异构复审编排 | D7 · 是/是/否 | D7 · 是/是/否 | ✅ |
| 多轮续聊 | D7 · 否/是/否 | D7 · 否/是/否 | ✅ |
| agent 派生边表 / 多 agent 树 | **D6 · 否/否/是** | **D7 · 是/是/否** | ❌ |

**修法（不是逐行改正，而是删表改指针）**：**删除该表**，替换为一句：
> 灰色地带归属的**单一真值** = `ADR-0009` §3（8 项逐项裁定 + 判据取值）；本卡**不复制**该表。

理由：① 逐行改正会留下**第二份真值**（日后 `ADR-0009` 改判须两处同步）；② 该表**本来就是模型自填**，
把它抄成本仓文档等于把模型幻觉升格为真值。
**保留**产物的**实质产出**：`## 判定输入` 三字段（`needs_non_producer_verdict` / `needs_multi_round_review` /
`is_intra_dispatch_quality_gate`）+ `## 缺料与歧义` 5 条（"同一产物"无机读键 · "非产出方主体"无判定字段等）——
并**补一条**：求值规则已是**三分支**（`ADR-0009` §2，2026-09-29 由 `O-115` 补入），
第三分支 `B-3=否 ∧ ¬B-1 ∧ ¬B-2 ⇒ 按约定归 D6` **正是覆盖上表 3 行 `否/否/否` 的规则** ⇒ 引擎实现**必须**处理它。

---

## 2. 落地排期

### 2.1 通用落法（6 项**共用**，不要每项重造）

本仓既有的判据落地形态（`O-105` / `O-108` / `O-109` 三次落地已定型）：

1. **判据本体 = 纯函数**（放 `ops/rpc_check.py`，可单测、无副作用）；
2. **注册进 `CHECKS`**（新增一项 ⇒ **须同步** `mirror` 的 `manual-counts` 与手册里的计数断言字数）；
3. **夹具**：**先验红**（改坏真对象 ⇒ 断言必须红 ⇒ 字节级恢复 + 自证）+ **变异自证**（把判据改成恒真 ⇒ 必须红）；
4. **真值表**（若判据读表）⇒ 表头写**读数日期**（本仓已裁：增长型载体必须带 `updated`）；
5. **"没判 ≠ 判了且通过"**：跳过 / 无对象 / 无词表可判 ⇒ **单列报数，不入分母**。

### 2.2 逐项

| 项 | 判据（一句话） | **先验红点**（改坏什么 ⇒ 断言必须红） | 验收判据 | 建议载体（未接线） |
|---|---|---|---|---|
| **A1** | 派发前对三字段求值 ⇒ 按 §2 **三分支**得唯一归属 | 删掉 §2 **第三分支** ⇒ "3 行全否"用例**必须红** | 8 种取值组合**全命中且仅命中一条**；3 行灰项**由规则算出**（非人工） | `ops/station-bin/agent-cli.ps1`（派发前求值）+ `_fm_golden_test.ps1` 夹具 |
| **A2** | 每次派发产出过程留痕（5 项）· **工具调用链标记"不可核"** | 删掉任一采集点 ⇒ 清单断言红 | 1 次真派发后留痕件齐 + 与产物哈希**交叉锚定**；**先核采集点在本机群可达** | `agent-cli.ps1`（采集）+ 新 gate |
| **A3** | 落档视图（**只含确定性字段**）+ `--check` 重渲染**逐字节**比对 | **改了真值不重渲染** ⇒ `--check` **必须红** | 退出码 **0/1/2 三态各实跑一次** + "改真值 ⇒ 红"实测 | 新脚本（渲染 + `--check`）+ 新 gate |
| **A4** | 同一表格内 **数据行/表头/分隔行列数守恒**（空单元格计入） | 台账某行注一个**未转义竖线** ⇒ 断言**必须红** | §1.1 修后参考实现 + 4 条边界用例全过 + 假绿清单（含"整篇无表 ⇒ 空集恒真"）显式登记 | `ops/rpc_check.py`（新 gate，扫仓内 md 表） |
| **A5** | **同源双跑逐字节一致**（SHA-256）；`n/a` 须显式标记 + 理由 | 把**时间戳**写进产物 ⇒ **必须红** | 一个真管线双跑实测 + 清单里 `determinism: n/a` **逐条有理由** | 新 gate（**须先冻结噪声清单口径**，见 §3.2） |
| **A6** | 决策 → 重算执行（6 步）+ 三态（跳过/失败/不适用）；汇总**仅当全部成功且版本号严格单调递增**才整体成功 | 让 **1 项失败** ⇒ 汇总**必须**报"部分失败"（**禁报成功**） | `ops/id_storage_census.py` 由"只产出决策"变为"可执行重算" + 执行侧实测 + 与 [U4-INVALIDATION-RULES.md](U4-INVALIDATION-RULES.md) 对账 | `ops/id_storage_census.py` + `U4-INVALIDATION-RULES.md` |

**建议顺序**（按"共享改动面 + 是否挡别项"）：**A4 → A5 → A3 → A6 → A2 → A1**。
理由：A4/A5/A3 是**新 gate**（互不共享代码面 ⇒ 可并行立项）；**A6 = 本轮已落地**（见 §2.3）；
**A2/A1 都动 `agent-cli.ps1`**（关键路径 ⇒ **串行**，每步过全套夹具 `_fm_golden_test` + `rpc check`）。

### 2.3 A6 本轮状态

**A6 已在本轮落地**（用户裁定"落地 imp6 失效传播执行侧"）——
`ops/rpc_check.py` 新增纯函数 `execute_invalidation()` + `ops/id_storage_census.py` 的 `--invalidate` 由
**三段扩为四段**（④ = 执行报告）· `tests/test_rpc_check_u4.py` 新增 **9 条执行侧用例 + 1 条先验红自证**（全绿）·
`U4-INVALIDATION-RULES.md` 新增 **§8 执行侧**并同步未实测第 1/5/10 条。**runtime 实测三条路径**（真实 CLI `not-executed`
· 注入假执行器 `executed` · 1 项失败 `partial-failed`）见 §8 与 `DEVELOPMENT-LOG.md` 同日条目。
⚠ **射程**：执行侧**只有框架、注册表为空** ⇒ 九项目 **0/9 未变**（`executed` ≠ "失效传播跑通"）。
**其余 5 项（A1–A5）**（★ 2026-09-29 更新：A4/A5/A3/A2 已落地见 §2.4，**A1 已落地见 §2.5** ⇒ **A1–A6 六项全部落地**，§2.2/§2.4 的"设计底稿已勘误、代码未动"表述**已全部作废**）。

### 2.4 本批落地记录（A4 → A5 → A3 → A2，2026-09-29）

按 §2.2 建议顺序执行（前四项三项**新 gate** 互不共享代码面；A2 动 `agent-cli.ps1` 关键路径）。
四项**均已完整闭环**（判据 + 注册 + 手册计数 + 夹具 + 先验红 + 字节级恢复自证）。

| 项 | 落地件 | gate | 夹具 | 实测读数 |
|---|---|---|---|---|
| **A4** | `ops/rpc_check.py`（`md_table_scan` / `check_md_tables`）+ [inventory/md-tables.yaml](../../inventory/md-tables.yaml)（28 条冻结） | `md-tables` | [tests/test_rpc_check_md_tables.py](../../tests/test_rpc_check_md_tables.py) 14/14 绿 | 扫描 270 篇 · 表 1881 张 · 违规 28（冻结 28 · 新增 0） |
| **A5** | `ops/rpc_check.py`（`det_manifest_diff` / `check_determinism`）+ [inventory/determinism-noise.yaml](../../inventory/determinism-noise.yaml)（噪声 7 类） | `determinism` | [tests/test_rpc_check_determinism.py](../../tests/test_rpc_check_determinism.py) 14/14 绿 | 噪声 7 类（可机检 5 · 无字面模式 2）· 正则样本自证 12/12 |
| **A3** | [ops/derived_view.py](../../ops/derived_view.py)（渲染 + `--check`）+ [docs/派生视图_端口分配.md](../../docs/派生视图_端口分配.md) | `derived-view` | [tests/test_rpc_check_derived_view.py](../../tests/test_rpc_check_derived_view.py) 12/12 绿 | source-hash `ac133408fbac…` · 逐字节一致（三态 0/1/2 各实跑） |
| **A2** | [ops/station-bin/agent-cli.ps1](../../ops/station-bin/agent-cli.ps1) 五采集点（`$Script:EV_FILES` + body 启动器 `[env]` + body 尾 `[cmd][fs][tool][artifact]` + 主控 collect + `Get-FrameworkSubjects`） | `executor-trace` | [tests/test_rpc_check_executor_trace.py](../../tests/test_rpc_check_executor_trace.py) 9/9 绿 + [_fm_golden_test.ps1](../../ops/station-bin/_fm_golden_test.ps1) 409/0（+7 条） | 机制：采集点 5/5 · 覆盖：runDir 含该件 **0 个**（尚无真派发） |

**A4 先验红**：向 `docs/分布式推理.md` 注入 2 列表头 + 3 格数据行 ⇒ `FAIL · 新增 1`（精确点到 `docs/分布式推理.md:612 row 行 3 格 ≠ 表头 2 格`）⇒ 字节级恢复自证（sha256 前后一致）。
**A5 先验红**：把 `determinism-noise.yaml` 的 timestamp 正则改为不匹配 ⇒ `FAIL`（点名声到该条）⇒ 恢复后 sha256 一致。
**A3 先验红**：改真值不重渲染 ⇒ `rc=1` 且报「过期」；手改视图 ⇒ `rc=1` 报「逐字节不一致」；档缺 ⇒ `rc=2`。
**A3 落地的两处设计决定**：① 档内**移除 `generated-at`**（§1.2 勘误）；② `source-hash` 在**生产端**归一化行尾/BOM
（否则 `core.autocrlf=true/false` 两台机器算出不同哈希 ⇒ 视图"互相过期"—— 正是 §3.2 旁证那条活问题的机器版）。
**A2 落地的两处设计决定**：① **工具调用链如实标 `uncore`**（执行体内部产生 ⇒ 可篡改/漏报/伪造），门禁**负向自证**
（出现 `chain=core`/`chain=verified` ⇒ FAIL）；② **覆盖 0 个不作为 FAIL**（尚无真派发 ⇒ "没验到" ≠ "验出问题"，
报数不入分母）—— 逐条字面细节（两段写入 / `EV_FILES` 登记 / 主控归档 / `free -m` 而非 `/proc`）留在**离线夹具**，
门禁**不抄第二份**。★ **A2 runtime 验收未实测**（§2.2 要求"1 次真派发后留痕件齐 + 与产物哈希交叉锚定"）
⇒ **如实登记为未实测**。
★ **连带改动**：手册计数 **46 → 47**（quick 38 → 39；A4/A5/A3）→ **47 → 48**（quick 39 → 40；A2）；
`py ops/id_site_census.py --emit` 重出真值（本仓 RPC **23 → 25** 行 / **5 → 6** 文件，因 `ops/derived_view.py` 贡献
`hashlib.sha256()` + `h.hexdigest()` 两行）+ [U4-INVALIDATION-RULES.md](U4-INVALIDATION-RULES.md) §1 表同步。

### 2.5 A1 落地记录（2026-09-29，本批第 6 项 / 收尾）

A1 动 [ops/station-bin/agent-cli.ps1](../../ops/station-bin/agent-cli.ps1)（**关键路径**）⇒ 按 §2.2 与 A2 后**串行**落地
（每步过全套 `_fm_golden_test` + `rpc check`）。**已完整闭环**（判据本体 + 白名单登记 + 派发前求值 + 夹具 + 先验红 + 字节级恢复自证）。

| 项 | 落地件 | gate | 夹具 | 实测读数 |
|---|---|---|---|---|
| **A1** | `agent-cli.ps1` 纯函数 `Resolve-D6D7Boundary`（§2 **三分支**互斥穷尽）+ `Get-FrontMatter` **白名单登记三键** + `Invoke-Task` **派发前求值**⇒ 落 `run.json` 的 `boundary` | **无**（A1 只求值+留痕，无消费判据） | [_fm_golden_test.ps1](../../ops/station-bin/_fm_golden_test.ps1) **423/0**（+14 条 `a1-*`） | 8 种取值组合**全命中且仅命中一条**（D7=6 / D6=2）· 三键未声明 ⇒ `resolved=false`（**不假装已判**） |

**A1 先验红**：删掉 §2 **第三分支**（`¬B-3 ∧ ¬B-1 ∧ ¬B-2 ⇒ D6`，约定归属）⇒ 夹具 **3 条红**（`FAIL a1: ★否/否/否 ⇒ D6` /
`★8 种取值组合全命中（落空者: false/false/false）` / `互斥穷尽 ⇒ D6/D7 计数 = 2/6`，`pass=420 fail=3`）
⇒ **字节级恢复**后复跑 **423/0**（删第三分支 = 3 行灰项 `否/否/否` 求值落空，正是 §1.3 点的 O-115 补丁要覆盖的形态）。

**A1 落地的三处设计决定**：① **纯函数 + 派发前求值** —— 三键全部来自卡、与运行结果无关 ⇒ 可在产出开始前算（ADR-0009 §机制原理：判据问**流程形态**、不问产物主题）；
② **fail-soft 诚实性** —— 三键任一未声明（空串 / 非 `true|false`）⇒ `resolved=false`、`layer` 空，**不假装已判**
（"没判" ≠ "判了且归 D6"；与 `Resolve-SelfReviewGuard` 的"读不出 ⇒ 不默认放行"同族）⇒ **存量卡不带三键 ⇒ 归属不变**，只多一条 `unresolved` 留痕；
③ **命名口径 = 下划线**（`needs_non_producer_verdict` / `needs_multi_round_review` / `is_intra_dispatch_quality_gate`），与 §2 行 L117-118 一致。
⚠ **射程（如实）**：**claude 本地备路**在 `Invoke-Task-Claude` 分支早返回，其 run 记录**不带**本键（另一条写入路径，未纳入 A1）。
★ **A1 无新 gate** ⇒ 手册计数**不变（仍 48 = quick 40 + 全量 8）**；`_fm_golden_test.ps1` 受 `ps1-golden` 判据自动读（409 → **423**）。
★ **A1 runtime 验收未实测**（§2.2 要求"1 次真派发后 `run.json` 含 `boundary` 键"）⇒ **如实登记为未实测**（与 A2 同）。

---

## 3. 仍缺的裁定（需你定）

### 3.1 跨族复核批的形态（`inkling` 复核 6 份产物）

**已定**：`inkling` 只用 **`lightning`**（钉 **B 站**、走 `opencode`、**零代码改动**）。
**未定（本约束尚未明示）**：**若把 3 张复核卡同排一批且都钉 B 站**，是否会撞**同站互斥锁**（`LOCK_HELD exit 3`）。
**候选**（**须先干跑核实，不许凭断言**）：
- **① 单批 3 卡全钉 B**（若 `batch` 的"每站串行"确实串行执行 ⇒ 锁在两次运行之间已释放 ⇒ **可行**）；
- **② 拆 3 次单卡派发**（严格串行，**必然**不撞锁，代价 = 失去站间并行）；
- **③ 1 张 inkling（B）+ 2 张 ultra（A/C）**（有跨族，但另两张与产出者**同族** ⇒ 只算部分跨族）。
⇒ **动作**：先 `AGENT_BATCH_DRYRUN=1` 干跑批次文件看分组与串并行，再定形态。

★ **2026-09-29 已裁 = ①**（干跑已核实，**非断言**）。落到 3 张卡（**2 份底稿/卡**）+ 一个批次文件：

| 卡（本目录） | 复核的 2 份底稿 | 产物 |
|---|---|---|
| [xrev1-cellsafety-boundary.md](dogfood-cards/xrev1-cellsafety-boundary.md) | A4 `cell-safety` + A1 `boundary-judge` | `out/xrev1.md` |
| [xrev2-derivedview-executortrace.md](dogfood-cards/xrev2-derivedview-executortrace.md) | A3 `derived-view` + A2 `executor-trace` | `out/xrev2.md` |
| [xrev3-invalidation-determinism.md](dogfood-cards/xrev3-invalidation-determinism.md) | A6 `invalidation-executor` + A5 `determinism` | `out/xrev3.md` |

批次文件 = [batches/xrev.txt](dogfood-cards/batches/xrev.txt)（三行全 `station=B model=lightning`）。

**干跑逐字回显**（`$env:AGENT_BATCH_DRYRUN=1`，2026-09-29）：

```
BATCH_PLAN: 行=3 · 可用=3 · 站分配 A=0 B=3 C=0
  L21  …/xrev1-cellsafety-boundary.md  -> B (…) model=lightning
  L22  …/xrev2-derivedview-executortrace.md  -> B (…) model=lightning
  L23  …/xrev3-invalidation-determinism.md  -> B (…) model=lightning
BATCH_DRYRUN: 已打印分配表，未派发任何任务
```

**裁① 的依据（机制层，读码得出）**：`batch` 的分派是"**每站一个 job、站内串行**"
（[agent-cli.ps1:5121-5164](file:///d:/RPC/ops/station-bin/agent-cli.ps1#L5121-L5164)）——
站级 job 对每张卡**各起一次 `agent-cli task` 子进程**，锁在**每次子进程内**取、**子进程退出即释放**
⇒ 3 张卡全钉 B 的效果 = **3 次独立串行派发**（与候选 ② 同序），**不是**同一锁内并发 ⇒ **不撞 `LOCK_HELD`**。
⚠ **如实标注两点**：(a) 干跑**只打印分配表、不取锁** ⇒ "不撞锁"是**读码 + 串行语义**得出的，**未被本次干跑实测**；
(b) 本批 3 张全钉 B ⇒ **站间并行恒为 1** ⇒ 候选 ①/② 的**墙钟相同**，选①只为**一条命令**、少一次手工。

### 3.2 A5 的噪声清单口径

A5 的 `## 必须排除的噪声` 列了 **7 类**（时间戳 / 运行 ID / 绝对路径 / 临时目录名 / 并发键序 / 环境变量 / 文件系统元数据）。
⚠ **须裁定**：这 7 类**是本仓统一的噪声口径**（写进真值表、所有双跑判据共用），还是**各管线自定**？

**主控建议 = 统一口径**（待你点头）：把这 7 类收成**单一真值**（机读清单，随 A5 落地一并入 `inventory/`），
所有"双跑 / 逐字节比对"类判据**引用**它、**不各写一份**。
理由 = 本仓头号失败形态（**同一事实两处表达**）：两个管线各写一份噪声清单 ⇒ 同一语义两个定义点，
改一处漏一处 ⇒ 判据之间**静默不一致**。⚠ **反方（如实）**：统一口径会把"某管线真的不需要排某类"变成
"必须显式声明排除它" ⇒ 多一道形式义务；但本仓既有纪律（"空清单必须给 `empty_reason`"）就是这个方向。

★ **2026-09-29 已裁 = 统一（单表）**。落地形态：
`inventory/determinism-noise.yaml`（每类 `id / match / why / applies_to`，另收一类**行尾策略（LF 归一）**）。
`applies_to` = 消费者判据 id 列表 ⇒ **适用面由表声明，不由各判据复述**（正面回应上面的"反方"）。
⚠ **时点 = 随 A5 判据落地同批**（**不**先单独建表）：无消费者的真值表会腐化（本仓纪律）。
⚠ **原写成本（已于 2026-09-29 勘误，见下）**：~~新 `inventory/*.yaml` **必须登记进 [inventory/artifacts.yaml](../../inventory/artifacts.yaml)**，
否则 `artifacts` 判据判**静默缺口 = FAIL**~~。
★★ **勘误（读码核实，非自述）**：上句**是错的**。`check_artifacts` 的真实口径
（[rpc_check.py:693-753](file:///d:/RPC/ops/rpc_check.py#L693)）= **只遍历 `inventory/artifacts.yaml` 的 `items`**
（每条须有 `check`（== 真实 CHECKS id）或 `exempt`）；对 `inventory/*.yaml` **只要求"可解析"**（报 `inventory yaml 可解析 N/N`），
**不要求**每个 yaml 都登记进 `items`。**实证**：A4/A5 新增 `md-tables.yaml` / `determinism-noise.yaml` **均未登记**，
`artifacts` 仍 **PASS**（`生成物 13 条`未变）⇒ 本节原判的"必须登记否则 FAIL"**不成立**。
（登记进 `items` 的意义另说 —— 那是"给生成物配一个判据"，与"新 yaml 是否合法"是两回事。）
**旁证（为什么必须统一）**：本仓已有一次同族发作 —— [rpc_check.py:4429-4432](file:///d:/RPC/ops/rpc_check.py#L4429-L4432) 的站上件逐字节比对被
`core.autocrlf` 的 **CRLF vs LF** 打成假红（内容其实一致）⇒ **"逐字节比对的噪声口径"已经是活问题**，而现况是每个判据各自决定。

### 3.3 本文的常驻载体

本文现为**新建文档**。是否长期常驻 `spec/d6-agent-standard/`，还是**并入** `DEVELOPMENT-LOG.md`
（落地一项回填一次）⇒ **待裁**。⚠ 若常驻，须考虑 §1 的勘误内容与 `ADR-0009` 的**单向依赖**（本文只指路、不复制）。

**主控建议 = 常驻 `spec/d6-agent-standard/`**（待你点头）：
① 本文是**活的计划**（每落地一项回填一次、§3 的裁定会逐条消掉），而 `DEVELOPMENT-LOG.md` 是**只增不改的日志**
⇒ 并入 = 把两种性质混进一份（且日志自有序号体系，插入会打乱）；
② 本文**不进** `spec-untested` / `doc-status` 射程（文件名不匹配 `U[0-9]-*.md` / `D7-PROTOCOL-*.md`、头 20 行无 `status:`）
⇒ 常驻**不增加门禁义务**（已写在本文开头"射程声明"里）；
③ 与 `ADR-0009` 的关系已定为**单向**（§1.3：删表改指针）⇒ 不会造第二份真值。

★ **2026-09-29 已裁 = 常驻 `spec/d6-agent-standard/`**。核查（读码/读数，非自述）：
`spec-untested` 射程 = `U[0-9]-*.md` / `D7-PROTOCOL-*.md`（[rpc_check.py:2695](file:///d:/RPC/ops/rpc_check.py#L2695)）；
`doc-status` 射程 = `spec|adr` **头 20 行**的 `status:`（[rpc_check.py:6952-6953](file:///d:/RPC/ops/rpc_check.py#L6952-L6953)）
⇒ 本文**两条都不匹配**，且 `doc-status` 读数报 **"新增 0"** ⇒ **常驻零门禁义务**（与 §3.3 原判一致）。

### 3.4 A6 执行侧框架是否单列一条能力项

`capability-inventory.yaml` 现有 `u4-invalidation`（verdict `present`，`what` = "**`affected` 可复算**"）
⇒ **它不覆盖**本轮新落的**执行侧框架**（`execute_invalidation()` + 注册表）。
**本轮处置 = 不动该 yaml**（verdict 不变、计数不变）。

**主控建议 = 单列一条 `invalidation-executor`**（待你点头），形态：

```yaml
- id: invalidation-executor
  domain: identity
  what: U-4 失效传播的**执行侧**（决策 → 重算执行报告）
  verdict: partial
  gap: "框架**已落地**（`execute_invalidation()` + 三态 + 版本单调），但**注册执行器为空** ⇒ 本仓与九项目 **0/9**（有活时报 `not-executed`，不假装已执行）"
  carriers:
  - {kind: file, ref: ops/rpc_check.py}
  - {kind: file, ref: ops/id_storage_census.py}
  basis: E2
  evidence: "2026-09-29 落地；`tests/test_rpc_check_u4.py` 9 条执行侧用例 + 1 条先验红；runtime 三条路径（not-executed / executed / partial-failed）"
```

★ **对 §3.4 原判的更正（本轮实测）**：原写"须同步 `capabilities` 的计数断言与 `mirror` 的 `manual-counts`"
⇒ **不成立**。实测：`capabilities` 判据（[rpc_check.py:6926](file:///d:/RPC/ops/rpc_check.py#L6926)）只核**结构 / 载体存在性 / 封闭集**，
**不比对条目数**；`manual-counts` 对的是 **`CHECKS` 断言项数**，与本表条目**无关**
⇒ **新增一条能力项不动任何计数断言、零连锁改动**（成本比原判低）。
理由：`u4-invalidation`（= "`affected` 可复算"，判据/决策侧）与执行侧**不是同一件事**
⇒ 塞进同一条的 `evidence` 会让"已有决策能力"与"执行侧只有框架"混成一句（**同一事实两处表达**的近亲）。

★ **2026-09-29 已裁 = 单列 `invalidation-executor`（`partial`）· 已落地** `inventory/capability-inventory.yaml`
（并同步 `updated` → `2026-09-29`，计数由门禁自动变 `32→33 / partial 7→8`）。
⚠ **一处必须避开的坑**：`execute_invalidation()` 明确是**非 CHECKS 项** ⇒ `carriers` **只能写 `kind: file`**；
写 `kind: gate` 会因该 id 不在 `CHECKS` 里而被判"挂名假判"（[rpc_check.py:739-741](file:///d:/RPC/ops/rpc_check.py#L739-L741)）。