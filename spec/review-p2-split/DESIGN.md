# 设计：#8B 拆 `rpc_check.py` / #8C 拆 `agent-cli.ps1`

---

id: review-p2-split-DESIGN
type: design
version: 1.0
status: draft
date: 2026-10-28
depends: []
upstream: null

---

> **Feature**: 把两个"单体大文件"按职责拆开，同时**保住全部公共面**：#8B 用"common + 域模块 + 门面"保 178 个符号与 52 个 CHECKS；#8C 用"入口 + dot-source lib"保 116 个函数与两个单文件 AST 夹具。
> **创建日期**: 2026-10-28
> **状态**: draft（Step 2；待 Step 4 设计评审）
> **Spec 步骤**: Step 2（DESIGN）
> **基于调研**: [2026-10-28 #8B/#8C 调研](../../docs/research/2026-10-28_原始评审P2拆分_8B8C_调研.md)
> **代码基线**: `54ecba42`（`main`，已推送）
> **分期**: 8B 先 → 8C 后；两个阶段各自有独立验收门

---

## 1. 目标与非目标

### 1.1 目标

| # | 目标 | 判据 |
|---|---|---|
| G1 | `rpc_check.py` 拆为 **7 个模块 + 1 个门面** | 每模块 ≤ 3000 行；`rpc_check.py` 门面 ≤ 500 行（8B-3 实测 320） |
| G2 | **公共面零变化**：178 个 `R.*` 符号、52 个 `CHECKS` id、CLI 参数与输出 | 新测试 `test_rpc_check_facade.py` 全覆盖；既有 65 测试不改一行 |
| G3 | 域模块**不得反向 import 门面** | 新测试 `test_rpc_check_modules.py` 静态扫描 import |
| G4 | `agent-cli.ps1` 抽出 **3 个 lib**（表 / scrub / D7 判据） | 入口 7406 → **7045** 行（lib 合计 393 行；只搬 9 函数 + 2 表，分派主体不动）；lib 均带 UTF-8 BOM |
| G5 | 单文件 AST 夹具改为**有序拼接**解析 | `ps1-golden` 仍 663/0；`_probe_fallback.ps1` 仍 PASS（仍提取 116 函数）；`_scrubber_coverage_test.ps1` 43/0 |
| G6 | 行号引用政策可执行 | 历史文档不改（加注记）；活文档（手册/README/INDEX）改为"函数名 + 文件"引用 |

### 1.2 非目标

1. **不做** 116 个函数的全量搬迁；主流程（task/review/workspace/accept/judge）留在入口。
2. **不改** 任何一门禁的判据语义（`CHECKS` 只换 `__module__`，不换行为）。
3. **不改** `cluster.py` / `cluster_web.py` / 站上 shell（P2 大项已收口）。
4. **不新增** daemon / 子命令 / 配置文件。
5. **不批量重写** ADR / OPEN-ISSUES / 调研里的 261 处历史行号（见 §4.4）。

---

## 2. 架构

### 2.1 #8B：三层（common → 域 → 门面）

```
rpc_common.py        # 路径/常量/IO 小工具（ROOT、OPS_INV、_read_text、_norm、yaml 读取、_iter_source_files…）
rpc_protocol.py      # U-1 身份 / U-2 方言 / U-3 边 / U-4 失效 / U-5 晋升 / D7 三信封+状态机+PRH（≈2285 行）
rpc_docs.py          # doclinks / spec-untested / doc-status / md-tables / determinism / derived-view / executor-trace
rpc_d6.py            # evidence / inbox / ps1-golden / ledger / review-catalog / memory-gates / multi-round / interruption / rubric / mirror
rpc_stations.py      # ports / plugins / impact / aliases / halogen / stations / LAN / engine / gates / usb4 / backend / models
rpc_governance.py    # secrets / syntax / scripts / deps / adr / inventory / facade / projects / shell-strict / station-layout
rpc_registry.py      # CHECKS 字面量（唯一填充点；import 各域模块的 check_* 函数，幂等 extend）
rpc_check.py         # 门面：import 七个模块 → 重导出全部公共名 → CLI（main/--only/--list-projects）
```

**依赖方向**：`common ← protocol/docs/d6/stations/governance ← registry ← rpc_check`。域模块只 import `common`（允许协议模块被 d6 依赖，但**不允许**任何域模块 import `rpc_check`）。

> **为什么多一层 registry**（8B-3 实测）：`CHECKS` 字面量 455 行（`fix` 文案很长），留在门面会让「门面 ≤500 行」**必然落空**；而放进 `rpc_common` 会让 common 反向 import 域模块（成环）。⇒ 单独一层「注册表」：只 import 域模块、只填 `rpc_common.CHECKS`，门面从它取。填充点仍保持**幂等**（`if not CHECKS:`，见 §8B 的二次加载坑）。

**为什么不用包（`rpc_check/`）**：入口路径 `ops/rpc_check.py` 被 hook、CI、`agent-cli.ps1 --list-projects`、文档同时引用；改成包会改调用面（`python ops/rpc_check.py` 仍可跑，但 `sys.path` 与相对导入会引入新失败面）。**平铺模块 + 门面**与 2026-09-23 `cluster.py` 完全同构。

### 2.2 #8C：入口 + lib（dot-source）

```
ops/station-bin/agent-cli.ps1        # param / 常量 / REPO_ROOT / PROJECTS 载入 / dot-source / 命令分派
ops/station-bin/agent-cli-lib/
  10-tables.ps1                      # ROUTE_TABLE / JUDGE_TABLE（纯数据）
  20-scrub.ps1                       # Get-ScrubRules / Invoke-Scrubber / Get-ScrubBlockReason
  30-d7.ps1                          # D7 三信封/状态机/合规与出网判据（纯函数）
```

- 入口在 `$Script:REPO_ROOT` 计算之后 dot-source（`Join-Path $Script:REPO_ROOT 'ops\station-bin\agent-cli-lib\...'`）；**lib 内不得用 `$PSScriptRoot` 互相找**（TEMP 副本场景）。
- 入口保留 `$Script:AGENT_CLI_LIBS = @('10-tables.ps1','20-scrub.ps1','30-d7.ps1')` 作为**唯一顺序真值**，循环 dot-source。
- **不引 `.psm1`**：模块作用域会改变 `$Script:` 语义与夹具提取；dot-source 保持"同一作用域"。

---

## 3. 契约

### 3.1 #8B 公共面（硬契约）

| 项 | 断言 |
|---|---|
| 178 个 `R.*` 符号 | 门面全部可达（新测试逐个 `getattr`） |
| 52 个 `CHECKS` | id 集合与顺序不变；每项 `fn` 可调用、`quick`/`fix` 不变 |
| CLI | `py ops/rpc_check.py [--only X] [--list] [--quick] [--list-projects]` 行为不变 |
| 模块行数 | 每模块 ≤ 3000；门面 ≤ 500 |
| 依赖 | 域模块不 import `rpc_check`；不出现跨域反向依赖 |
| 登记 | 6 个模块进 `entry_modules`；`scripts` 未登记 0 |

### 3.2 #8C 公共面（硬契约）

| 项 | 断言 |
|---|---|
| 116 个函数 | 拼接后全部存在（新测试按 `FunctionDefinitionAst` 计数） |
| 夹具 | `_fm_golden_test.ps1` / `_probe_fallback.ps1` 解析"入口 + 3 lib 有序拼接"；`ps1-golden` 663/0 |
| 顺序 | 入口的 `$Script:AGENT_CLI_LIBS` 与两个夹具的拼接清单**逐项相同**（测试断言三处一致） |
| 编码 | 新 lib 含非 ASCII ⇒ UTF-8 BOM；入口与 lib 均 LF |
| TEMP 副本 | `split` 子命令在 `AGENT_CLI_REPO_ROOT` 下仍能 dot-source 到 lib（行为测试） |

### 3.3 行号引用政策（#8C）

| 类别 | 处置 |
|---|---|
| `adr/`、`docs/research/`、`OPEN-ISSUES.md`、`DEVELOPMENT-LOG.md` 等**带日期的历史记录** | **不改**（它们是当时的证据快照）；在 `agent-cli-lib/README.md` 声明"2026-10-28 后的行号以文件+函数名为准" |
| 活文档（`docs/三机推理集群使用手册.md`、`ops/station-bin/README.md`、`docs/FRAMEWORK-INDEX.md`） | 指向 `agent-cli.ps1` 的引用改为**函数名**（如 `Invoke-Task`），不写行号 |
| 新增引用 | **禁止** `agent-cli.ps1:NNNN`；由 review 纪律约束（不加门禁：无法在不改历史的前提下基线化） |

### 3.4 实施顺序（两个阶段）

| 阶段 | 内容 | 前置 |
|---|---|---|
| **8B-1** | 抽 `rpc_common.py` + `rpc_protocol.py`；门面重导出 | 先写 `test_rpc_check_facade.py` |
| **8B-2** | 抽 `rpc_docs.py` + `rpc_d6.py` | 8B-1 绿 |
| **8B-3** | 抽 `rpc_stations.py` + `rpc_governance.py`；门面收薄 | 8B-2 绿 |
| **8C-1** | 抽 `10-tables.ps1`（纯表）+ 夹具拼接改造 | 8B 全绿 |
| **8C-2** | 抽 `20-scrub.ps1`（规则+抹除+拒发判据） | 8C-1 绿 |
| **8C-3** | 抽 `30-d7.ps1`（D7 纯判据） | 8C-2 绿 |

---

## 4. 替代方案

| 方案 | 否决理由 |
|---|---|
| **把 `rpc_check.py` 改成包** | 调用面广（hook/CI/agent-cli/文档）；相对导入改变失败面；门面方案零调用面改动 |
| **只拆协议层，检查器不动** | `rpc_check.py` 仍 8000 行；评审 #8 的核心诉求是"大文件"，不是"分层"本身 |
| **按行数机械切分** | 会切断 `# ──` 段边界与函数依赖；按域切才可读 |
| **`agent-cli.ps1` 用 `.psm1` 模块** | 模块作用域 + 路径依赖 + 夹具按文件解析；dot-source 才是"同作用域" |
| **一次搬 116 个函数** | 261 处行号引用全部失效 + 两个夹具重写面过大；先搬"纯数据/纯函数"三块 |
| **把 261 处历史行号全改** | 历史文档是当时的证据快照；改写它们等于篡改证据，且成本高于收益 |
| **给行号引用加门禁** | 无法基线化（历史文件必须保留）；改为 review 纪律 + 活文档改写 |

---

## 5. 不变式

| # | 不变式 |
|---|---|
| N1 | 178 个符号 / 52 个 CHECKS / CLI 输出**逐项不变**（门面测试钉住） |
| N2 | 域模块依赖方向单向（不 import 门面） |
| N3 | 每个 `CHECKS.fn` 的行为不变（65 个既有测试即证据） |
| N4 | 116 个 PowerShell 函数在拼接后**全部存在**；两个夹具的断言数不减 |
| N5 | 站上件 md5 不变（#8B/#8C 都不改站上执行件） |
| N6 | 不新增 daemon / 子命令 / 配置面 |
| N7 | 搬完后所有"扫文本"门禁的计数同步复核（`scripts` / `syntax` / `doclinks` / `mirror` / `ps1-golden`） |

---

## 6. 测试策略（先验红）

| 测试 | 先验红如何成立 |
|---|---|
| `test_rpc_check_facade.py` | 实现前：门面即文件本体，符号可达但**无 `rpc_common` 等模块** ⇒ 模块清单断言 FAIL |
| `test_rpc_check_modules.py` | 实现前：模块不存在 ⇒ FAIL；实现后：行数/依赖方向/登记 |
| `test_agent_cli_libs.py` | 实现前：`agent-cli-lib/` 不存在、三处清单不一致 ⇒ FAIL |
| 既有 65 测试 | 全程跑；每刀一提交，红了即回滚 |
| `ps1-golden` | 搬表/搬 scrub 后仍 663/0 |
| `py-tests` | 65 → **68**（+3 新测试） |

---

## 7. 验收口径

| 门 | 内容 |
|---|---|
| M1 | 交付物：6 模块 + 门面、3 lib + 入口、3 新测试、登记、README |
| M2 | 先验红 → 后验绿（3 个新测试） |
| M3 | 公共面：178 符号 / 52 CHECKS / CLI / 116 函数 / 夹具 663 |
| M4 | 门禁：`py-tests` 68/68、`rpc_check` 0 红、`gates` 36/36、`scripts` 未登记 0、`ps1-golden` 663/0、CI 两 job 绿 |
| M5 | 不变式 N1-N7 |
| M6 | 行号引用政策落地（活文档改写 + 历史注记） |

---

## 8. 风险与回滚

| 风险 | 等级 | 缓解 | 回滚 |
|---|---|---|---|
| 门面漏导出某符号 | 高 | 178 符号逐个 `getattr` + 45 个测试 | 单模块提交 revert |
| 循环 import | 中 | `common` 只放路径/IO；域模块只依赖 common/protocol | 同上 |
| 夹具拼接顺序漂移 | 高 | 三处清单一致性测试 | 单文件 revert |
| PowerShell 编码/换行 | 中 | lib 带 BOM + LF；`syntax` 门禁 | 同上 |
| TEMP 副本找不到 lib | 中 | `$REPO_ROOT` + 行为测试 | 同上 |
| `ps1-golden` 行号类断言失效 | 中 | 夹具改为 AST/拼接后重跑 663 | 同上 |

---

## 9. 与其它 spec 的关系

- [P2 大项](../review-p2-big/DESIGN.md)：本 spec 是它 §1.2 明确"另立"的 8B/8C。
- [cluster.py 模块化先例](../../docs/2026-09-23_cluster.py模块化重构_调研与方案.md)：同形态（门面 + 分层 + 登记 + 一刀一提交）。
- **ADR-0004**：不新增管理入口；拆分只减少单文件复杂度。
