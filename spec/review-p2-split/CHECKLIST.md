# 验收 Checklist：#8B 拆 `rpc_check.py` / #8C 拆 `agent-cli.ps1`

---

id: review-p2-split-CHECKLIST
type: design
version: 1.0
status: accepted
date: 2026-10-28
depends: [review-p2-split-IMPLEMENTATION, review-p2-split-DESIGN]
upstream: review-p2-big-CHECKLIST

---

> **Feature**: 按 [DESIGN](./DESIGN.md) 与 [IMPLEMENTATION](./IMPLEMENTATION.md) 验收 #8B（`rpc_check.py` 拆为 common + 5 域模块 + 注册表 + 门面，412 个基线顶层名与 52 个 CHECKS 零变化）与 #8C（`agent-cli.ps1` 抽出 3 个 dot-source lib，116 个函数与三个 AST 夹具不回退）。
> **创建日期**: 2026-10-28
> **状态**: accepted（2026-10-28：本地全量 + 夹具 + CI 全绿）
> **Spec 步骤**: Step 5（验收）
> **基于实施**: [IMPLEMENTATION.md](./IMPLEMENTATION.md)
> **基于设计**: [DESIGN.md](./DESIGN.md)（v1.1，含 §10 Step 4 设计评审）
> **基于调研**: [2026-10-28 #8B/#8C 调研](../../docs/research/2026-10-28_原始评审P2拆分_8B8C_调研.md)
> **代码基线**: `54ecba42`（`main`）→ 8B-1 `e04d996c` · 8B-2 `44d1fddb` · 8B-3 `392b8484` · 8C `345e589a`（均已推送）
> **审查轮次**: 第 1 轮拆 `rpc_check.py`（三刀）· 第 2 轮拆 `agent-cli.ps1` · 第 3 轮设计评审（DESIGN §10）· 第 4 轮全量门禁 + CI（run `40676593130` 两 job 绿）

---

## 0. 验收门总览

| 门 | 内容 | 章节 | 项数 | 级别 | 结论 |
|---|---|---|---|---|---|
| M1 | 交付物 | §1 | 16 | **P0** | 全 ☑ |
| M2 | 先验红 → 后验绿 | §2 | 8 | **P0** | 全 ☑ |
| M3 | 契约与边界 | §3 | 12 | **P0** | 全 ☑ |
| M4 | 门禁与回归 | §4 | 9 | **P0** | 全 ☑ |
| M5 | 不变式 | §5 | 7 | **P1** | 全 ☑ |
| M6 | 行号引用政策 | §6 | 4 | P1 | 全 ☑ |
| M7 | 残留、回滚与边界 | §7 | 6 | P1/P3 | 6 条记录 |
| 附 | 既有测试改动审计 | §8 | 15 | **P0** | 全 ☑ |

**明确不在本轮验收范围**：116 个 PowerShell 函数的全量搬迁、`cluster.py` 再抽取、站上件部署与实弹派发、门禁语义变更（详见 DESIGN §1.2）。

---

## 1. M1 交付物

| # | 交付物 | 落位 | 判据 | 状态 | 证据 |
|---|---|---|---|---|---|
| T1 | `rpc_common.py` | [ops/rpc_common.py](../../ops/rpc_common.py) | 路径/常量/IO 小工具；**无**域逻辑；`CHECKS = []` 占位 | ☑ | 163 行 |
| T2 | `rpc_protocol.py` | [ops/rpc_protocol.py](../../ops/rpc_protocol.py) | U-1/U-2/U-3/U-4/U-5 + D7 判据库 | ☑ | 2317 行 |
| T3 | `rpc_docs.py` | [ops/rpc_docs.py](../../ops/rpc_docs.py) | doclinks / spec-untested / doc-status / md-tables / determinism / derived-view / executor-trace | ☑ | 1258 行 |
| T4 | `rpc_d6.py` | [ops/rpc_d6.py](../../ops/rpc_d6.py) | evidence / inbox / ps1-golden / ledger / review-catalog / memory-gates / multi-round / interruption / rubric / mirror | ☑ | 2305 行 |
| T5 | `rpc_governance.py` | [ops/rpc_governance.py](../../ops/rpc_governance.py) | secrets / syntax / scripts / artifacts / sensitivity / facade / deps / adr / inventory / shell-strict / station-layout | ☑ | 1414 行 |
| T6 | `rpc_stations.py` | [ops/rpc_stations.py](../../ops/rpc_stations.py) | ports / plugins / impact / aliases / halogen / stations+LAN / engine / gates / usb4 / backend / models | ☑ | 2294 行 |
| T7 | `rpc_registry.py` | [ops/rpc_registry.py](../../ops/rpc_registry.py) | `CHECKS` **唯一填充点**；**幂等** `if not CHECKS:` | ☑ | 488 行；`CHECKS 52 · uniq 52` |
| T8 | 门面收薄 | [ops/rpc_check.py](../../ops/rpc_check.py) | 只留重导出 + `MARKS`/`MODE_SKIP` + `_validate_graph`/`run_checks`/`main` | ☑ | **321** 行（≤500） |
| T9 | `10-tables.ps1` | [agent-cli-lib/10-tables.ps1](../../ops/station-bin/agent-cli-lib/10-tables.ps1) | `ROUTE_TABLE`(34) / `JUDGE_TABLE`(6)；带 BOM | ☑ | 141 行；实测 `ROUTE=34 JUDGE=6` |
| T10 | `20-scrub.ps1` | [agent-cli-lib/20-scrub.ps1](../../ops/station-bin/agent-cli-lib/20-scrub.ps1) | 三函数；规则仍 9 条且单一真值源 | ☑ | 83 行；`SCRUB_RULES=9` |
| T11 | `30-d7.ps1` | [agent-cli-lib/30-d7.ps1](../../ops/station-bin/agent-cli-lib/30-d7.ps1) | 6 个 D7/出网判据函数 | ☑ | 169 行 |
| T12 | 入口 dot-source | [agent-cli.ps1](../../ops/station-bin/agent-cli.ps1) | `$Script:AGENT_CLI_LIBS` 唯一顺序真值；排在 `$Script:REPO_ROOT` 之后 | ☑ | 7406 → **7045** 行 |
| T13 | lib README | [agent-cli-lib/README.md](../../ops/station-bin/agent-cli-lib/README.md) | 三条纪律 + 行号政策（2026-10-28 起） | ☑ | 43 行 |
| T14 | 3 个新测试 | `tests/test_rpc_check_split_facade.py` / `test_rpc_check_modules.py` / `test_agent_cli_libs.py` | 独立可跑、带 `RESULT:` | ☑ | `py-tests 68/68` |
| T15 | 符号基线 | [tests/fixtures/rpc_check_symbols.txt](../../tests/fixtures/rpc_check_symbols.txt) | 412 个基线顶层名（从基线 AST 生成） | ☑ | 412 行 |
| T16 | 登记 | [inventory/ops.yaml](../../inventory/ops.yaml) | `entry_modules` 含 7 个 py 模块 + 3 个 ps1 lib | ☑ | `scripts`：`拆分模块 17 · 未登记 0` |

---

## 2. M2 先验红 → 后验绿

| # | 验收项 | 先验红（实测） | 后验绿 | 状态 |
|---|---|---|---|---|
| F1 | `test_rpc_check_modules.py`「模块已存在」 | 基线 `54ecba42` 无 `rpc_common.py`/`rpc_protocol.py`（`git cat-file -e` ⇒ `path exists on disk, but not in '54ecba42'`） | 7 模块齐全、均 ≤3000 行、不反向 import | ☑ |
| F2 | `test_rpc_check_modules.py`「二次加载幂等」 | 修复前实测 `once 52 → after 2nd load 104`（`CHECKS` 重复注册，`mirror` 的 O-50 计数当场对不上） | `52 → 52 · uniq 52` | ☑ |
| F3 | 反向 import 负向夹具 | 注入 `import rpc_check` ⇒ 被抓到 | `['import rpc_check']` | ☑ |
| F4 | `test_agent_cli_libs.py` | 基线无 `agent-cli-lib/`；入口无 `$Script:AGENT_CLI_LIBS`（解析得 `None`） | 四处清单逐项同序 · 116 函数 · 无重名 · 3 个 BOM · 无 `$PSScriptRoot` | ☑ |
| F5 | `ps1-golden` 夹具（搬 lib 后、改拼接前） | 实跑报 `Get-BackendEgress not found in agent-cli.ps1`（夹具按单文件解析） | `FM_GOLDEN_TEST pass=663 fail=0` | ☑ |
| F6 | `check_mirror`（搬表后） | 实测报 `agent-cli.ps1 里读不出 JUDGE_TABLE['main']（表结构变了？）` ⇒ 3 条用例连带红 | 引入 `agent_cli_sources_text()` 后 `合格镜像 2 处` | ☑ |
| F7 | `scripts` 门禁（新增 lib、未登记时） | `扫描 77 个脚本 · 未登记 3` | `拆分模块 17 · 未登记 0` | ☑ |
| F8 | 既有测试的"打桩点失效" | `test_rpc_check_artifacts` 5 条全红（patch 门面常量，判据已读自己模块的全局） | `ALL PASS`（见 §8） | ☑ |

> `test_rpc_check_split_facade.py` **不承担先验红**（基线符号本就在同一文件里）——它是拆分**之后**的护栏，DESIGN §6 已如实标注。

---

## 3. M3 契约与边界

| # | 接口/边界 | 判据 | 状态 |
|---|---|---|---|
| C1 | 412 个基线顶层名 | 逐个 `hasattr(R, n)`；`RESULT: ALL PASS` | ☑ |
| C2 | 52 个 CHECKS | id 集合/顺序不变；`fn` 可调用；`quick 43` | ☑ |
| C3 | CLI `--list` | 输出 52 行、可解析 | ☑ |
| C4 | CLI `--list-projects` | 打 JSON（4 项目）且不自洽即 2 | ☑ |
| C5 | CLI `--quick` / `--only` | 模式语义不变（MODE_SKIP 不进失败集） | ☑ |
| C6 | 门面 ≤500 行 | 321 | ☑ |
| C7 | 模块 ≤3000 行 | 最大 2317（protocol） | ☑ |
| C8 | 域模块不反向 import | 7 个模块全过 + 负向夹具 | ☑ |
| C9 | 116 个 PS 函数 | 拼接后 116（入口 107 + lib 9），无重名 | ☑ |
| C10 | 三处夹具拼接清单 | 入口 + 3 夹具逐项同序（4 处） | ☑ |
| C11 | lib 编码 | 3 个 lib 全带 UTF-8 BOM；`syntax` 的 `ps1-bom 20/20` | ☑ |
| C12 | TEMP 副本 | 带 `AGENT_CLI_REPO_ROOT` ⇒ 正常打 usage（rc=2）；无 env ⇒ **响亮失败**（rc=1，点名缺失 lib），不静默 | ☑ |

负向项均由测试内置夹具执行（临时数据，不改真文件）：反向 import、重复注册、清单不一致、lib 缺 BOM、lib 用 `$PSScriptRoot`、dot-source 早于 `REPO_ROOT`。

---

## 4. M4 门禁与回归

| # | 门禁 | 判据 | 读数 | 状态 |
|---|---|---|---|---|
| G1 | `py-tests` | 68/68（65 既有 + 3 新增） | `结果: 68/68 通过 · 用时 62.1s` | ☑ |
| G2 | `rpc_check --quick` | 0 红 | `绿灯 41 · 黄灯 2 · 红灯 0` | ☑ |
| G3 | 全量 `rpc_check`（pre-push） | 0 红 | `绿灯 49 · 黄灯 3 · 红灯 0`（黄灯为 evidence / memory-gates / stations 存量） | ☑ |
| G4 | `ps1-golden` | 663/0 | `FM_GOLDEN_TEST pass=663 fail=0` | ☑ |
| G5 | `_probe_fallback -SmokeOnly` | 仍提取全部函数 | `已提取 116 个函数 · 脚本级赋值 44 个 · 排除 2 个[$Script:REPO_ROOT,$Script:REVIEW_DIR]` | ☑ |
| G6 | `_scrubber_coverage_test` | 全 PASS | `SCRUBBER_COVERAGE_TEST pass=43 fail=0` | ☑ |
| G7 | `gates` / `usb4` / `ps1-runstamp` / `halogen-assets` | 全 PASS | `gates 可达 3/3 · 站上件一致 36/36`；另 3 项 PASS | ☑ |
| G8 | `id-census` / `doclinks` / `md-tables` | 不漂 | `真值一致 10 个 · 不符 0`；`失效 0`；`新增 0` | ☑ |
| G9 | CI（push 后） | 两 job 绿 | run [`40676593130`](https://github.com/StormstoutLau/RPC/actions/runs/40676593130)：`py-tests` ✓ · `shellcheck` ✓（1m34s） | ☑ |

---

## 5. M5 不变式

| # | 不变式 | 落点 | 状态 |
|---|---|---|---|
| N1 | 412 名 / 52 CHECKS / CLI 输出不变 | `test_rpc_check_split_facade` ALL PASS；`mirror` 的 O-50 计数 == 52 | ☑ |
| N2 | 域模块依赖单向 | 7 模块静态扫描 + 负向夹具 | ☑ |
| N3 | 每个 `CHECKS.fn` 行为不变 | 65 个既有测试的断言全绿（改动仅注入点，见 §8） | ☑ |
| N4 | 116 个 PS 函数全在；夹具断言数不减 | `test_agent_cli_libs` 116；`ps1-golden 663`（拆前 663）· scrubber 43 | ☑ |
| N5 | 站上件 md5 不变 | `STATION_BINS` 12 件；`agent-cli.ps1` **不在**站上件清单（控制台侧）⇒ `gates 36/36` | ☑ |
| N6 | 不新增 daemon / 子命令 / 配置面 | diff 无新 `.service`、无新 CLI 参数、无新 yaml 真值表 | ☑ |
| N7 | 扫文本门禁计数同步复核 | `scripts`(未登记 0) / `syntax`(ps1 20·BOM 20) / `doclinks`(0 失效) / `mirror` / `ps1-golden` 全部复跑 | ☑ |

---

## 6. M6 行号引用政策

| # | 项 | 判据 | 状态 |
|---|---|---|---|
| P1 | 政策落纸 | [agent-cli-lib/README.md](../../ops/station-bin/agent-cli-lib/README.md) 写明"2026-10-28 起以文件 + 函数名为准" | ☑ |
| P2 | 活文档无行号引用 | `docs/三机推理集群使用手册.md` / `ops/station-bin/README.md` / `docs/FRAMEWORK-INDEX.md` 实测 **0 处** `agent-cli.ps1:NNNN` | ☑ |
| P3 | 历史文档不改 | `docs/2026-09-23_*` 等带日期的调研仍保留当时行号（证据快照），不做批量改写 | ☑ |
| P4 | 新增引用受约束 | 由 review 纪律约束（DESIGN §3.3：不加门禁，无法在不改历史的前提下基线化） | ☑ |

---

## 7. M7 残留、回滚与边界

| # | 项 | 状态 | 说明 |
|---|---|---|---|
| R-1 | 回滚（8B） | 备用 | 三刀各自单提交，`git revert 392b8484` / `44d1fddb` / `e04d996c` 可逐刀回退 |
| R-2 | 回滚（8C） | 备用 | 单提交 `345e589a`；revert 后入口恢复单文件、夹具恢复单文件解析 |
| R-3 | `split` 真派发 | **未跑** | 本轮只验证加载期两态（带/不带 env）；跨站派发不在离线验收范围 |
| R-4 | lib 与入口版本错配 | 已覆盖 | 四处清单一致性测试；TEMP 副本无 env 时**响亮失败** |
| R-5 | `CHECKS` 幂等依赖"空列表" | 已记录 | 若将来有人在 `rpc_common` 里预填 `CHECKS`，幂等判据会失效 ⇒ 由 T7 的"唯一填充点"注释 + 幂等测试共同守 |
| R-6 | 116 函数仍有 107 在入口 | 边界 | DESIGN §1.2 非目标①：本轮只搬"纯数据/纯函数"三块 |

---

## 8. 既有测试改动审计（对应 DESIGN D-3 / N3）

> 口径：**断言与期望值一行未改**；只改"打桩打在哪个模块的全局"与"扫哪些文件"——因为判据本体搬了家。
> 未列出的 50 个既有测试**零改动**。

| # | 文件 | 改动性质 | 原因 |
|---|---|---|---|
| A1 | `test_rpc_check_artifacts.py` | patch `R.ARTIFACTS_INV` → `rpc_governance.ARTIFACTS_INV` | 判据读定义模块的全局 |
| A2 | `test_rpc_check_engine_bands.py` | patch `R._health_probe` → `rpc_stations.*`（2 处） | 同上 |
| A3 | `test_rpc_check_ports_range.py` | patch 4 个常量 → `rpc_stations.*`（2 处调用点） | 同上 |
| A4 | `test_rpc_check_usb4_key.py` | patch `_net_doc`/`_health_probe` → `rpc_stations.*` | 同上 |
| A5 | `test_rpc_check_lan_drift.py` | patch `_ssh_g_hostname` → `rpc_stations.*`（2 处） | 同上 |
| A6 | `test_rpc_check_derived_view.py` | patch `DERIVED_VIEW` → `rpc_docs.*` | 同上 |
| A7 | `test_rpc_check_executor_trace.py` | patch `AGENT_CLI` → `rpc_docs.*`（3 处） | 同上 |
| A8 | `test_rpc_check_conclusion_ledger.py` | patch `LEDGERS_INV` → `rpc_d6.*` + `import rpc_d6` | 同上 |
| A9 | `test_rpc_check_mirror.py` | `AGENT_CLI.read_text()` → `agent_cli_sources_text()` | 表搬到 lib，读**定义处**（单一读路） |
| A10 | `test_rpc_check_ps1_golden.py` | `CLI.read_text()` → 入口 + 3 lib 拼接 | 8C：`Get-BackendEgress` 在 lib |
| A11 | `test_cli_concurrency_guards.py` | 源扫描 `rpc_check.py` → `ops/rpc_*.py` | 源码断言不再限于门面 |
| A12 | `test_rpc_check_allow_unhit.py` | 同上 | 同上 |
| A13 | `test_rpc_check_spec_untested.py` | 同上 | 同上 |
| A14 | `test_rpc_check_cross_family.py` | 同上 | 同上 |
| A15 | `test_cluster_pure.py`（T14） | 动态导入门面 + patch → `import rpc_stations` 后 patch | 判据本体搬走后，门面 patch 不再生效 |

---

## 9. 验收结论

**通过**（2026-10-28）。

- **M1-M6** 全部 ☑；**M4 G9** 由 CI run [`40676593130`](https://github.com/StormstoutLau/RPC/actions/runs/40676593130) 闭环（`py-tests` + `shellcheck` 两 job 绿）。
- 关键读数：`rpc_check.py 10378 → 321` · `agent-cli.ps1 7406 → 7045` · `py-tests 68/68` · `quick 41/2/0` · `full 49/3/0` · `ps1-golden 663/0` · `probe 116 函数` · `scrubber 43/0` · `gates 36/36` · `scripts 未登记 0`。
- **两个真实收获（都是"静默失败"家族，已变成测试）**：
  1. **`CHECKS` 二次注册**：共享可变列表 + 脚本方式运行 ⇒ 52→104、id 全重复，症状只出现在 `mirror` 的一条计数上。⇒ 幂等填充 + 「二次加载」断言。
  2. **事实源搬家 ⇒ 判据假红**：`JUDGE_TABLE` 进 lib 后，`check_mirror` 只读入口就报"表结构变了"。⇒ 收敛成 `agent_cli_sources_text()` 单一读路（判据与测试同读）。
- **过程偏差已在 DESIGN §10 逐条回写**（registry 层 / 15 个测试改动 / 三夹具 / 8C 合刀 / 412 vs 178 口径）。
- **提交**：`e04d996c` · `44d1fddb` · `392b8484` · `345e589a`（4 个，均已推送）。
