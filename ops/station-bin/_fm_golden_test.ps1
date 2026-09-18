# ============================================================================
# _fm_golden_test.ps1 — 离线单测: Get-FrontMatter 解析 accept-golden (IMPLEMENTATION §8.1)
# 用法: powershell -NoProfile -ExecutionPolicy Bypass -File ops/station-bin/_fm_golden_test.ps1
# 退出码: 0 = all pass; 1 = fail
# 隔离方式: 从 agent-cli.ps1 用 AST 提取 Get-FrontMatter 函数体单独定义(不执行主入口)
# ============================================================================
$ErrorActionPreference = 'Stop'
$cli = 'd:\RPC\ops\station-bin\agent-cli.ps1'
$tmpCards = Join-Path $env:TEMP 'agent-cli-fm-test'
if (-not (Test-Path $tmpCards)) { New-Item -ItemType Directory -Path $tmpCards -Force | Out-Null }

# --- 提取 Get-FrontMatter 定义 ---
# .NET ReadAllText 默认按 UTF-8 解码（无 BOM 也按 UTF8），ParseFile 则按系统 ANSI (GBK) 解码
# 中文注释会乱码导致假解析错误 —— 故用 ReadAllText + ParseInput（IMPL §2.3 PS5.1 UTF-8 纪律）。
$content = [System.IO.File]::ReadAllText($cli, [System.Text.UTF8Encoding]::new($false))
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseInput($content, [ref]$tokens, [ref]$errors)
if ($errors -and $errors.Count -gt 0) { throw "agent-cli.ps1 parse errors: $($errors | Out-String)" }
$fns = $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true)
Write-Host "DEBUG fns count=$(@($fns).Count)"
$fn = @($fns) | Where-Object { $_.Name -eq 'Get-FrontMatter' } | Select-Object -First 1
Write-Host "DEBUG fn found=$([bool]$fn)"
if (-not $fn) { throw 'Get-FrontMatter not found in agent-cli.ps1' }
Invoke-Expression $fn.Extent.Text   # 定义函数到当前会话

# --- ADR-0007 路B: 一并提取框架基线两函数 ---
# 它们是**纯函数**(只吃 $accept/$goldenActive/卡 subjects, 不碰站、不碰文件系统)
# ⇒ 可离线单测; 这正是"派发路径改动"能被验证而不用每次都真派发的关键。
foreach ($nm in @('Get-FrameworkSubjects', 'Merge-EvidenceSubjects')) {
    $f = @($fns) | Where-Object { $_.Name -eq $nm } | Select-Object -First 1
    if (-not $f) { throw "$nm not found in agent-cli.ps1" }
    Invoke-Expression $f.Extent.Text
}

$pass = 0; $fail = 0
function Assert-True($name, $cond) {
    if ($cond) { $script:pass++; Write-Host "PASS  $name" }
    else { $script:fail++; Write-Host "FAIL  $name" }
}

# --- 用例卡 ---
$goldenCard = Join-Path $tmpCards 'golden.md'
@"
---
proj: paper
task: golden parse test
model: gpt-oss
accept-golden:
  source: spec/d6-agent-standard/strong-accept/golden/path_guard_golden.py
  cmd: ./.venv/bin/python .golden/path_guard_golden.py
---
## 任务描述
body here
"@ | Set-Content $goldenCard -Encoding utf8

$plainCard = Join-Path $tmpCards 'plain.md'
@"
---
proj: paper
task: plain parse test
model: nemotron
accept:
  - echo ok
---
## 任务描述
plain body
"@ | Set-Content $plainCard -Encoding utf8

$partialCard = Join-Path $tmpCards 'partial.md'
@"
---
proj: paper
task: partial golden
model: gpt-oss
accept-golden:
  source: spec/x/y.py
---
## 任务描述
partial body
"@ | Set-Content $partialCard -Encoding utf8

# 缺口10 回归 (2026-09-18): 正文里的 markdown 分隔线 `---` 之后的 **`key: value` 形正文行**,
#   不得被当成 front-matter 吸收(会**覆盖已解析的键**)。
#   机制: 原判据"遇 `---` 即翻转 inFreq"且无 `bodyRead` 守卫 ⇒ 正文分隔线把 inFreq 翻回 true,
#     之后的正文行走 front-matter 分支; 因 `$h.ContainsKey($k)` 命中已知键即 `$h[$k] = $v`,
#     **标量键被静默覆盖**(如 readonly/task/model), 而 `accept`/`decompose` 会被追加。
#   ⚠ 注意失效形态**不是**"正文整体丢失" —— `$bodyRead` 不重置, 普通正文行仍走 body 分支
#     (我最初如此断言, 被本用例证伪 ⇒ 判据必须实测, 不能凭推理)。
$fenceCard = Join-Path $tmpCards 'fence.md'
@"
---
proj: paper
task: fence trap test
readonly: true
model: gpt-oss
---
## 任务描述
下面这段是**引用另一个卡片的 front-matter 示例**, 必须原样保留在正文里:

---

task: EVIL-OVERWRITE
readonly: false
model: EVIL-MODEL
"@ | Set-Content $fenceCard -Encoding utf8

# ADR-0007 阶段 1 (2026-09-18): evidence-manifest 三级嵌套。
#   关键坑: 键名含 `-`, 而通用键正则 `^\s*([A-Za-z_\-]+)\s*:` 的字符类**也含 `-`** 且允许前导
#   空白 ⇒ 若新分支顺序错位, `evidence-manifest:` 会落到通用分支, 因 ContainsKey 命中而
#   `$h[$k] = $v`(**空串覆盖整个哈希表**) ⇒ 顶层键同时被清。本用例同时守这两件事。
$evmCard = Join-Path $tmpCards 'evm.md'
@"
---
proj: paper
task: evm parse test
model: gpt-oss
evidence-manifest:
  version: 1
  subjects:
    - name: agent-output
      path: agent-output.txt
      digest: sha256
    - name: workspace-diff
      collect: "find . -newer .marker"
      digest: sha256
    - name: station-tmp-log
      collect: "tail -5 /tmp/x.log"
      ephemeral: true
# 3-b-2: manifest 块内的注释行(以 # 开头)必须被**忽略** —— 卡作者要能就地写说明,
#   而不会被当成键(已实测: `#` 不在通用键正则的字符类内 ⇒ 落到无匹配分支 ⇒ 忽略)。
    - name: after-comment
      path: after-comment.txt
      digest: sha256
---
## 任务描述
evm body
"@ | Set-Content $evmCard -Encoding utf8

# --- 用例 ---
$h = Get-FrontMatter $goldenCard
Assert-True "golden: source parsed" ($h['accept-golden'].source -eq 'spec/d6-agent-standard/strong-accept/golden/path_guard_golden.py')
Assert-True "golden: cmd parsed" ($h['accept-golden'].cmd -eq './.venv/bin/python .golden/path_guard_golden.py')
Assert-True "golden: other keys unaffected (task)" ($h['task'] -eq 'golden parse test')
Assert-True "golden: body intact" ($h['body'] -match 'body here')
Assert-True "golden: accept empty" ($h['accept'].Count -eq 0)

$h2 = Get-FrontMatter $plainCard
Assert-True "plain: accept-golden source empty (back-compat)" ($h2['accept-golden'].source -eq '')
Assert-True "plain: accept-golden cmd empty" ($h2['accept-golden'].cmd -eq '')
Assert-True "plain: accept list preserved" ($h2['accept'].Count -eq 1 -and $h2['accept'][0] -eq 'echo ok')

$h3 = Get-FrontMatter $partialCard
Assert-True "partial: source parsed, cmd empty" ($h3['accept-golden'].source -eq 'spec/x/y.py' -and $h3['accept-golden'].cmd -eq '')

$h4 = Get-FrontMatter $fenceCard
Assert-True "fence: header task NOT overwritten by body line (缺口10)" ($h4['task'] -eq 'fence trap test')
Assert-True "fence: header readonly NOT overwritten by body line (缺口10)" ($h4['readonly'] -eq $true)
Assert-True "fence: header model NOT overwritten by body line (缺口10)" ($h4['model'] -eq 'gpt-oss')
Assert-True "fence: body keeps the quoted lines verbatim" ($h4['body'] -match 'EVIL-OVERWRITE')

$h5 = Get-FrontMatter $evmCard
$ev = $h5['evidence-manifest']
Assert-True "evm: version parsed" ($ev['version'] -eq '1')
Assert-True "evm: two subjects" (@($ev['subjects']).Count -eq 4)
Assert-True "evm: subject[0] name/path/digest" ($ev['subjects'][0]['name'] -eq 'agent-output' -and $ev['subjects'][0]['path'] -eq 'agent-output.txt' -and $ev['subjects'][0]['digest'] -eq 'sha256')
Assert-True "evm: subject[1] collect parsed, path empty" ($ev['subjects'][1]['name'] -eq 'workspace-diff' -and $ev['subjects'][1]['collect'] -match 'find \. -newer' -and $ev['subjects'][1]['path'] -eq '')
Assert-True "evm: top-level keys NOT clobbered" ($h5['task'] -eq 'evm parse test' -and $h5['model'] -eq 'gpt-oss')
Assert-True "evm: body intact" ($h5['body'] -match 'evm body')
# ADR-0007 3-b-2: subject 级 ephemeral(设计性临时产物) —— 布尔归一 + 未声明者缺省 false
Assert-True "evm: ephemeral true on subject[2]" ($ev['subjects'][2]['ephemeral'] -eq $true)
Assert-True "evm: ephemeral default false on subject[0]/[1]" ($ev['subjects'][0]['ephemeral'] -eq $false -and $ev['subjects'][1]['ephemeral'] -eq $false)
# 3-b-2: manifest 块内注释行被忽略(不影响其后的 subject 解析)
Assert-True "evm: subject after in-block comment parsed" ($ev['subjects'][3]['name'] -eq 'after-comment' -and $ev['subjects'][3]['path'] -eq 'after-comment.txt')

# --- ADR-0007 路B: 框架固定件基线 + 合并 (纯函数, 无需真派发即可验证) ---
$b0 = @(Get-FrameworkSubjects @() $false)
$n0 = @($b0 | ForEach-Object { $_.name })
Assert-True "baseline: 无 accept 无 golden => 10 件" ($b0.Count -eq 10)
Assert-True "baseline: 含 judgment-record/prompt/workspace-diff/card" (
    ($n0 -contains 'judgment-record') -and ($n0 -contains 'prompt') -and
    ($n0 -contains 'workspace-diff') -and ($n0 -contains 'card'))
# 这条是**负向自证**: 实测无 accept 的 run 上该两件不存在 ⇒ 基线若无条件列入, 每个这类 run
#   都会假报 missing-artifact(把缺口判据变成噪声) ⇒ 必须**不**列入。
Assert-True "baseline: 无 accept => 不含 accept-output(否则每 run 假报缺件)" (-not ($n0 -contains 'accept-output'))

$b1 = @(Get-FrameworkSubjects @('echo ok') $true)
$n1 = @($b1 | ForEach-Object { $_.name })
Assert-True "baseline: 有 accept+golden => 12 件" ($b1.Count -eq 12)
Assert-True "baseline: 有 accept+golden => 含 accept-output/accept-golden-output" (
    ($n1 -contains 'accept-output') -and ($n1 -contains 'accept-golden-output'))

# 合并: 卡里历史遗留的框架件声明必须与基线**去重**(否则同一件在链上出现两次)
$cardSubs = @(
    @{ name = 'prompt'; path = 'prompt.txt'; digest = 'sha256'; collect = ''; ephemeral = $false }
    @{ name = 'station-tmp-log'; path = ''; collect = 'tail -5 /tmp/x.log'; digest = 'sha256'; ephemeral = $true }
)
$mg = @(Merge-EvidenceSubjects $cardSubs @() $false)
# 10(基线) + 2(卡声明) - 1(其中 prompt 与基线同 path, 去重) = 11
Assert-True "merge: 基线10 + 卡声明2 - 重复1 = 11" ($mg.Count -eq 11)
Assert-True "merge: 卡声明与基线同 path 只出现一次" ((@($mg | Where-Object { $_.path -eq 'prompt.txt' })).Count -eq 1)
$tmp = @($mg | Where-Object { $_.name -eq 'station-tmp-log' })
Assert-True "merge: 卡特有 subject 保留(collect/ephemeral 未丢)" (
    $tmp.Count -eq 1 -and $tmp[0].collect -eq 'tail -5 /tmp/x.log' -and $tmp[0].ephemeral -eq $true)
Assert-True "merge: 五键齐备(免得下游取键得 null 静默传播)" (
    (@($mg | Where-Object { -not ($_.Contains('name') -and $_.Contains('path') -and
                                $_.Contains('collect') -and $_.Contains('digest') -and
                                $_.Contains('ephemeral')) })).Count -eq 0)

# 路B 的核心目的: **无 manifest 的卡**(= 71 个真实 run 的来源)也能拿到非空声明 ⇒ 不再是 recipe v1
$m0 = @(Merge-EvidenceSubjects @() @() $false)
Assert-True "merge: 空卡仍得 10 件(=> 不再退化为 recipe v1)" ($m0.Count -eq 10)

Write-Host "--------------------------------"
Write-Host "FM_GOLDEN_TEST pass=$pass fail=$fail"
exit $(if ($fail -eq 0) { 0 } else { 1 })