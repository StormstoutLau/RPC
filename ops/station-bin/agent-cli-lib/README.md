# agent-cli-lib —— `agent-cli.ps1` 的判据库（review-p2-split 8C）

## 是什么

`agent-cli.ps1`（7406 行 / 116 函数）里三类**可独立成册**的内容搬到这里，入口只留
param / 常量 / REPO_ROOT / 命令分派：

| 文件 | 内容 |
|---|---|
| `10-tables.ps1` | `$Script:ROUTE_TABLE`（route 别名 → 模型 id + 站）· `$Script:JUDGE_TABLE`（judge 别名 → type/id/station/ctx/egress/compliance/maxtokens） |
| `20-scrub.ps1` | `Get-ScrubRules`（**规则的单一真值源**）/ `Invoke-Scrubber`（抹）/ `Get-ScrubBlockReason`（拒） |
| `30-d7.ps1` | `Test-D7Envelope` / `Get-D7Adjudication` / `Get-BackendEgress` / `Get-JudgeEgress` / `Get-JudgeComplianceReject` / `Get-AttachEgressReject` |

## 加载方式（顺序的唯一真值）

入口在 `$Script:REPO_ROOT` **之后**声明并循环 dot-source：

```powershell
$Script:AGENT_CLI_LIBS = @('10-tables.ps1', '20-scrub.ps1', '30-d7.ps1')
foreach ($libName in $Script:AGENT_CLI_LIBS) {
    . (Join-Path $Script:REPO_ROOT "ops\station-bin\agent-cli-lib\$libName")
}
```

**三条纪律**

1. **lib 里不得用 `$PSScriptRoot` 互相找** —— dot-source 时 `$PSScriptRoot` 指向**调用方**；
   而 `split` 的 BOM 副本落在 `%TEMP%`（O-161 同源），靠它会算错根。
2. **lib 必须带 UTF-8 BOM** —— 无 BOM 的中文 `.ps1` 在 PS 5.1 按 ANSI 解码 ⇒ 注释乱码导致
   **假解析错误**（门禁 `ps1-bom` 与 `tests/test_agent_cli_libs.py` 各守一次）。
3. **清单三处必须逐项同序** —— 入口的 `$Script:AGENT_CLI_LIBS`，以及三个夹具
   （`_fm_golden_test.ps1` / `_probe_fallback.ps1` / `_scrubber_coverage_test.ps1`）的拼接清单。
   夹具按"拼接后的全文"做 AST 提取（函数 + `$Script:*` 赋值）；清单不一致 ⇒ 夹具全绿而线上少一个函数。

## 行号政策（2026-10-28 起）

- **对外引用一律用「文件 + 函数名」**，不要写 `agent-cli.ps1:NNNN` —— 行号随任何一次编辑漂移，
  而拆库后 `agent-cli.ps1` 的行号**已整体改变**。
- 历史文档里的 `agent-cli.ps1:NNNN`（ADR / `docs/research/` / `OPEN-ISSUES.md` / `DEV-LOG`）
  是**当时的快照**，刻意不回改；需要精确定位时按函数名 grep 现文件。
- 新增判据库时：先在入口 `$Script:AGENT_CLI_LIBS` 里加名（顺序即语义），再同步三个夹具的清单
  （`tests/test_agent_cli_libs.py` 会当场拦下漏改），最后在 `inventory/ops.yaml` 的
  `entry_modules` 登记（否则门禁 `scripts` 报"未登记脚本"）。
