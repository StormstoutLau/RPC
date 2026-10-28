# 实施文档：#8B 拆 `rpc_check.py` / #8C 拆 `agent-cli.ps1`

---

id: review-p2-split-IMPLEMENTATION
type: design
version: 1.0
status: draft
date: 2026-10-28
depends: [review-p2-split-DESIGN]
upstream: null

---

> **Feature**: 按 [DESIGN](./DESIGN.md) 把 `rpc_check.py` 拆为「common + 5 域 + 门面」，把 `agent-cli.ps1` 抽出 3 个 dot-source lib；公共面逐项不变。
> **创建日期**: 2026-10-28
> **状态**: draft（Step 3）
> **Spec 步骤**: Step 3（IMPLEMENTATION）
> **基于设计**: [DESIGN.md](./DESIGN.md)
> **基于调研**: [8B/8C 调研](../../docs/research/2026-10-28_原始评审P2拆分_8B8C_调研.md)
> **代码基线**: `54ecba42`（`main`；行号为该基线快照）

---

## 1. 实施范围

| # | 交付物 | 落位 | 类型 |
|---|---|---|---|
| T1 | 共享层 | `ops/rpc_common.py` | 新增 |
| T2 | 协议层 | `ops/rpc_protocol.py` | 新增 |
| T3 | 文档域 | `ops/rpc_docs.py` | 新增 |
| T4 | D6/D7 域 | `ops/rpc_d6.py` | 新增 |
| T5 | 站上/资产域 | `ops/rpc_stations.py` | 新增 |
| T6 | 治理域 | `ops/rpc_governance.py` | 新增 |
| T7 | 门面 | `ops/rpc_check.py` | 缩到 ≤ 500 行 |
| T8 | 登记 | `inventory/ops.yaml` `entry_modules` +6 | 修改 |
| T9 | 3 个新测试 | `tests/test_rpc_check_facade.py` / `test_rpc_check_modules.py` / `test_agent_cli_libs.py` | 新增 |
| T10 | 3 个 lib | `ops/station-bin/agent-cli-lib/{10-tables,20-scrub,30-d7}.ps1` | 新增 |
| T11 | 入口改造 | `agent-cli.ps1`：`$Script:AGENT_CLI_LIBS` + 循环 dot-source | 修改 |
| T12 | 夹具拼接 | `_fm_golden_test.ps1` / `_probe_fallback.ps1`：读"入口 + 3 lib" | 修改 |
| T13 | 行号政策 | `agent-cli-lib/README.md` + 活文档改函数名 | 新增/修改 |

**边界**：见 DESIGN §1.2（不搬主流程、不批量改历史行号、不动站上 shell）。

---

## 2. 工程约定

| 项 | 值 |
|---|---|
| Python | 3.12；模块平铺；`from rpc_common import ...` 显式清单（**不用** `import *`） |
| 门面 | 显式重导出**全部**顶层名（含 `_` 私有）—— 45 个测试按 `R.<name>` 取用 |
| PowerShell | PS 5.1；lib 含非 ASCII ⇒ UTF-8 **BOM**；LF；dot-source 用 `$Script:REPO_ROOT` |
| 提交 | 每阶段一提交（8B-1 / 8B-2 / 8B-3 / 8C-1 / 8C-2 / 8C-3），红了即回滚 |
| 门禁 | 每阶段跑 `py-tests` + `rpc_check --quick` +（8C）`ps1-golden` |

---

## 3. 8B：抽取算法（逐阶段同一套）

**一次性脚本**（`tmp/`，用完删）按 AST 执行：

1. 解析 `ops/rpc_check.py`（`ast`），建立顶层节点表：`name → (start_lineno, end_lineno, source)`。
2. **种子** = 该阶段目标段落的顶层节点（按行号区间，见 §4）。
3. **依赖闭包**：从种子的函数体里收集**自由名**（`ast.Name(Load)` + `global`），对每个自由名若在顶层表里则递归加入。
4. **分流**：
   - 种子 → 目标模块；
   - 闭包中的**非种子**（共享常量/工具）→ `rpc_common.py`；
   - 若闭包里出现 `check_*` 函数 ⇒ **中止并报告**（说明切错了段）。
5. 生成代码：
   - `rpc_common.py`：原文件头部 `import` 段 + 闭包里的共享节点（保持原顺序）。
   - 目标模块：`from rpc_common import a, b, ...`（显式）+ 种子节点。
   - `rpc_check.py`：移除已搬节点；顶部加 `from rpc_common import ...` 与本阶段模块的显式重导出。
6. 跑 `py-tests` + `rpc_check --quick`；绿了提交。

> **⚠ 共享 `CHECKS` 必须幂等填充**（8B-2 实测）：`CHECKS` 搬进 `rpc_common` 后是**共享可变列表**，
> 而门面在**脚本方式**跑时模块名是 `__main__`；若过程中又有模块 `import rpc_check`（`cluster.py`
> 有惰性 import），模块体执行第二遍 ⇒ `CHECKS` 52 → **104 条、id 全重复**，表现为 `mirror` 的
> O-50 断言计数对不上。故门面尾部固定写成 `if not CHECKS: CHECKS.extend([...])`，
> 并由 `test_rpc_check_modules.py` 用"二次加载"断言守住。

> 为什么不用 `import *`：`_read_text` 等私有名不会被星号导出，而 45 个测试按 `R._read_text` 取用；显式清单还能让"漏导出"在 import 时**立刻**报错。

---

## 4. 8B 分阶段（段区间 = 基线行号）

| 阶段 | 种子区间 | 目标模块 | 预期结果 |
|---|---|---|---|
| **8B-1** | L885-L3178（U-2/U-1/U-3/U-4/D7/U-5/O-66 判据库） | `rpc_protocol.py` | `rpc_check.py` ≈ 8100 行；协议测试全绿 |
| **8B-2** | L3532-L3620 doclinks · L3836-L3897 spec-untested · L8933-L8971 doc-status · L9255-L9433 md-tables · L9433-L9602 determinism · L9602-L9636 derived-view · L9636-L10378 executor-trace · L6193-L6638 evidence · L6850-L6959 inbox · L7162-L7289 ps1-golden · L7289-L7471 ledger · L7471-L7615 review-catalog · L7615-L8031 memory-gates · L8031-L8380 multi-round · L8380-L8602 interruption · L8602-L8933 rubric · L3279-L3532 mirror | `rpc_docs.py` / `rpc_d6.py` | 两模块各 ≈ 1500-2900 行 |
| **8B-3** | L4479-L4972 ports/plugins/impact/aliases · L4972-L5177 halogen · L5012-L5860 stations · L5177-L6016 LAN · L5860-L6193 engine · L6016-L6324 gates · L6324-L6638 usb4 · L6638-L6850 backend · L38-L885 secrets/syntax/scripts · L3621-L3774 deps · L3774-L3836 adr · L4355-L4479 inventory · L3179-L3279 facade · L6959-L7159 shell-strict/station-layout · L7159-L7180 CHECKS 前的常量 | `rpc_stations.py` / `rpc_governance.py` / `rpc_registry.py` | 门面 ≤500 行（实测 **320**）；stations 2294 · governance 1414 · registry 488 |

> 行号会随上一阶段漂移 ⇒ 每个阶段开始前**重新用段标记定位**（`# ──` 标题），不硬编码行号。

---

## 5. 8B 新测试

| 测试 | 内容 |
|---|---|
| `test_rpc_check_facade.py` | 从基线快照读取 178 个符号名单（硬编码）；逐个 `getattr(R, name)`；52 个 CHECKS 的 id 与顺序；`--list` 输出可解析 |
| `test_rpc_check_modules.py` | 7 个模块存在；每模块 ≤ 3000 行；域模块源码不含 `import rpc_check` / `from rpc_check`；`entry_modules` 含 7 个新路径；**二次加载不重复注册 CHECKS**；七模块齐后门面 ≤ 500 行 |
| `test_agent_cli_libs.py` | 3 个 lib 存在且带 BOM；入口 `$Script:AGENT_CLI_LIBS` 与两个夹具的拼接清单**逐项相同**；拼接后函数数 ≥ 116 |

---

## 6. 8C：三个 lib 的边界（基线行号）

| lib | 内容 | 基线行 |
|---|---|---|
| `10-tables.ps1` | `$Script:ROUTE_TABLE` / `$Script:JUDGE_TABLE` 赋值 | 由 `Select-String '$Script:ROUTE_TABLE ='` 定位 |
| `20-scrub.ps1` | `Get-ScrubRules`(L2206) / `Invoke-Scrubber`(L2242) / `Get-ScrubBlockReason`(L2264) | 至下一个 `function` 前 |
| `30-d7.ps1` | `Test-D7Envelope`(L1524) / `Get-D7Adjudication`(L1747) / `Get-BackendEgress`(L2439) / `Get-JudgeEgress`(L2447) / `Get-JudgeComplianceReject`(L2461) / `Get-AttachEgressReject`(L2476) | 同上 |

**入口改造**（在 `$Script:REPO_ROOT` 之后）：

```powershell
$Script:AGENT_CLI_LIBS = @('10-tables.ps1', '20-scrub.ps1', '30-d7.ps1')
foreach ($libName in $Script:AGENT_CLI_LIBS) {
    . (Join-Path $Script:REPO_ROOT "ops\station-bin\agent-cli-lib\$libName")
}
```

**夹具拼接**（两处同形）：

```powershell
$libNames = @('10-tables.ps1', '20-scrub.ps1', '30-d7.ps1')
$content = [IO.File]::ReadAllText($cli)
foreach ($n in $libNames) {
    $content += "`n" + [IO.File]::ReadAllText((Join-Path $PSScriptRoot "agent-cli-lib\$n"))
}
```

> 拼接顺序 = 入口 dot-source 顺序；三处清单由 `test_agent_cli_libs.py` 钉死。

**实测结果（2026-10-28）**

| 文件 | 行数 | 内容 |
|---|---|---|
| `agent-cli.ps1` | 7406 → **7045** | 只减不增（9 个函数 + 2 张表搬走）；分派主体（`Invoke-Task` / `Invoke-Review` / `split` 等）不动 |
| `agent-cli-lib/10-tables.ps1` | 141 | `ROUTE_TABLE`(34 键) / `JUDGE_TABLE`(6 键) |
| `agent-cli-lib/20-scrub.ps1` | 83 | 三个 scrub 函数（9 条规则） |
| `agent-cli-lib/30-d7.ps1` | 169 | 6 个 D7 / 出网判据函数 |

函数总数守恒：入口 107 + lib 9 = **116**（拆分前基线），无重名。
第三个夹具 `_scrubber_coverage_test.ps1` 也按同一份清单拼接（原文写死 `d:\RPC` 绝对路径，一并改为 `$PSScriptRoot` 派生）。

---

## 7. 行号政策落地

| 文件 | 动作 |
|---|---|
| 新增 `ops/station-bin/agent-cli-lib/README.md` | 写明"2026-10-28 起，行号以文件+函数名为准；ADR/调研/OPEN-ISSUES 的历史 `#L` 是当时快照" |
| `docs/三机推理集群使用手册.md` / `ops/station-bin/README.md` | 把 `agent-cli.ps1:NNNN` 改为函数名（实施时逐条 grep） |
| 历史文档（ADR / research / OPEN-ISSUES / DEV-LOG） | **不改**，只在上述 README 里声明政策 |

---

## 8. 验证矩阵

| 层 | 命令 | 期望 |
|---|---|---|
| 单测 | `py tests\run_py_tests.py` | 68/68（65 + 3） |
| 门禁 | `py ops\rpc_check.py --quick` | 0 红 |
| 夹具 | `rpc_check --only ps1-golden` | 663/0 |
| 全量 | `py ops\rpc_check.py` | 0 红（黄灯存量） |
| CI | push 后两 job | 绿 |
| 站上 | 不涉及部署（`gates` 36/36 仍应绿） | 36/36 |

---

## 9. 回滚

| 层 | 动作 |
|---|---|
| 每阶段 | 单提交 revert（模块新增 + 门面改动在同一提交） |
| 8C | 入口 + 夹具 + lib 在同一提交 ⇒ 一次 revert 完整还原 |
| 登记 | `entry_modules` 增删与模块同一提交 |
