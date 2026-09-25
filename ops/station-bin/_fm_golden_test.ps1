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
# O-15/AUDIT (2026-09-21): 追加提取 claude 按路基线(Get-ClaudeFrameworkSubjects) 与 fallback 判定 (Test-FallbackEligible)。
foreach ($nm in @('Get-FrameworkSubjects', 'Get-ClaudeFrameworkSubjects', 'Merge-EvidenceSubjects', 'Test-EvmStatePull', 'Test-FallbackEligible', 'Test-CtxOverflowError', 'Resolve-CtxOverflowCode', 'Resolve-ClaudeStationCandidates', 'Get-SensitivityBackendReject', 'Get-BackendEgress', 'Get-JudgeEgress', 'Get-JudgeComplianceReject', 'Get-AttachEgressReject', 'Get-ScrubRules', 'Invoke-Scrubber', 'Get-ScrubBlockReason', 'Resolve-ReviewPrompt', 'Resolve-ClaudeBudget', 'Resolve-LocalBash', 'Invoke-LocalBashCmd', 'Resolve-ExitCode')) {
    $f = @($fns) | Where-Object { $_.Name -eq $nm } | Select-Object -First 1
    if (-not $f) { throw "$nm not found in agent-cli.ps1" }
    Invoke-Expression $f.Extent.Text
}

# --- 2026-09-21: 提取**真实 ROUTE_TABLE**(它是赋值语句, 不是函数) ---
# 为什么必须测真表: `_probe_fallback.ps1` 的 `Resolve-Model` 是 **stub** ⇒ 守护不到真表;
#   而 claude 备路型号一旦回退成 **Claude 原生 id**, 经 OpenRouter 会 **403 地区墙**(2026-09-21 实测)
#   —— 这条回归**没有别的守卫**。
$rtAst = @($ast.FindAll({ param($n)
    $n -is [System.Management.Automation.Language.AssignmentStatementAst] -and
    $n.Left.Extent.Text -eq '$Script:ROUTE_TABLE' }, $true)) | Select-Object -First 1
if (-not $rtAst) { throw '$Script:ROUTE_TABLE assignment not found in agent-cli.ps1' }
Invoke-Expression $rtAst.Extent.Text
Write-Host "DEBUG ROUTE_TABLE keys=$(@($Script:ROUTE_TABLE.Keys).Count)"

# --- W1a (2026-09-21): 一并提取**真实 JUDGE_TABLE**（同为赋值语句） ---
# 为什么必须测真表: W1a 把 `egress` / `compliance` 从"声明了但没人读"变成真判据 ⇒ 表里的数据
#   本身就是判据的真值源 ⇒ 必须断言"**每个 judge 都分类了**"（否则新增 judge 会静默走 fail-closed 或漏判）。
$jtAst = @($ast.FindAll({ param($n)
    $n -is [System.Management.Automation.Language.AssignmentStatementAst] -and
    $n.Left.Extent.Text -eq '$Script:JUDGE_TABLE' }, $true)) | Select-Object -First 1
if (-not $jtAst) { throw '$Script:JUDGE_TABLE assignment not found in agent-cli.ps1' }
Invoke-Expression $jtAst.Extent.Text
Write-Host "DEBUG JUDGE_TABLE keys=$(@($Script:JUDGE_TABLE.Keys).Count)"

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
    - name: station-reality
      path: station-reality.json
      state: out/station-reality.json
      digest: sha256
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
Assert-True "evm: five subjects" (@($ev['subjects']).Count -eq 5)
Assert-True "evm: subject[0] name/path/digest" ($ev['subjects'][0]['name'] -eq 'agent-output' -and $ev['subjects'][0]['path'] -eq 'agent-output.txt' -and $ev['subjects'][0]['digest'] -eq 'sha256')
Assert-True "evm: subject[1] collect parsed, path empty" ($ev['subjects'][1]['name'] -eq 'workspace-diff' -and $ev['subjects'][1]['collect'] -match 'find \. -newer' -and $ev['subjects'][1]['path'] -eq '')
Assert-True "evm: top-level keys NOT clobbered" ($h5['task'] -eq 'evm parse test' -and $h5['model'] -eq 'gpt-oss')
Assert-True "evm: body intact" ($h5['body'] -match 'evm body')
# ADR-0007 3-b-2: subject 级 ephemeral(设计性临时产物) —— 布尔归一 + 未声明者缺省 false
Assert-True "evm: ephemeral true on subject[2]" ($ev['subjects'][2]['ephemeral'] -eq $true)
Assert-True "evm: ephemeral default false on subject[0]/[1]" ($ev['subjects'][0]['ephemeral'] -eq $false -and $ev['subjects'][1]['ephemeral'] -eq $false)
# 3-b-2: manifest 块内注释行被忽略(不影响其后的 subject 解析)
Assert-True "evm: subject after in-block comment parsed" ($ev['subjects'][4]['name'] -eq 'after-comment' -and $ev['subjects'][4]['path'] -eq 'after-comment.txt')
# O-40/A-1 (2026-09-24): subject 级 `state`(站上源路径) —— 解析出值; 未声明者缺省空串
Assert-True "evm: state 解析(有声明者取到站上路径)" ($ev['subjects'][3]['state'] -eq 'out/station-reality.json')
Assert-True "evm: state 缺省为空串(未声明者不泄漏/不为 null)" ($ev['subjects'][0]['state'] -eq '' -and $ev['subjects'][2]['state'] -eq '')
# O-40/A-1 (2026-09-24): 产物拉回的白名单判定 —— 正反用例(防恒真/恒假)
Assert-True "evm-state: 正例 out/* 扁平 → ok" ((Test-EvmStatePull -state 'out/station-reality.json' -path 'station-reality.json').ok -eq $true)
Assert-True "evm-state: 反例 非 out/ 前缀 → 拒" ((Test-EvmStatePull -state 'tmp/station-reality.json' -path 'station-reality.json').ok -eq $false)
Assert-True "evm-state: 反例 绝对路径 / 根(Linux) → 拒" ((Test-EvmStatePull -state '/etc/passwd' -path 'passwd.json').ok -eq $false)
Assert-True "evm-state: 反例 绝对路径(C:) → 拒" ((Test-EvmStatePull -state 'C:\x\y.json' -path 'y.json').ok -eq $false)
Assert-True "evm-state: 反例 state 含 .. → 拒" ((Test-EvmStatePull -state 'out/../secrets/x' -path 'x.txt').ok -eq $false)
Assert-True "evm-state: 反例 path(落盘名)含 .. → 拒" ((Test-EvmStatePull -state 'out/x.json' -path '../x.json').ok -eq $false)
Assert-True "evm-state: 反例 path 非扁平(含 /) → 拒(防目录穿越)" ((Test-EvmStatePull -state 'out/x.json' -path 'sub/x.json').ok -eq $false)
Assert-True "evm-state: 反例 state 为空 → 拒" ((Test-EvmStatePull -state '' -path 'x.json').ok -eq $false)
Assert-True "evm-state: 反例 path 为空 → 拒" ((Test-EvmStatePull -state 'out/x.json' -path '').ok -eq $false)

# --- ADR-0007 路B: 框架固定件基线 + 合并 (纯函数, 无需真派发即可验证) ---
# 2026-09-25 (D6-P3-2 接线): 期望 11 → **10** —— **不是回归**: O-29(2026-09-23) 把 `golden-cmd`
#   从"裸列"改成"`$goldenActive` 条件列"（见 agent-cli.ps1 该件注释：裸列会让每个无 golden 的 run
#   记一条 missing-artifact gap）⇒ **基线少 1 件**。该期望值当时没跟着改，而本夹具此前不在门禁里
#   ⇒ **静静积累了多轮**。⚠ 判据：这是**合法演进**（有代码注释为证），不是回归 —— 故改期望值而非改代码。
$b0 = @(Get-FrameworkSubjects @() $false)
$n0 = @($b0 | ForEach-Object { $_.name })
Assert-True "baseline: 无 accept 无 golden => 9 件" ($b0.Count -eq 9)
Assert-True "baseline: 含 judgment-record/prompt/workspace-diff/card" (
    ($n0 -contains 'judgment-record') -and ($n0 -contains 'prompt') -and
    ($n0 -contains 'workspace-diff') -and ($n0 -contains 'card'))
# 这条是**负向自证**: 实测无 accept 的 run 上该两件不存在 ⇒ 基线若无条件列入, 每个这类 run
#   都会假报 missing-artifact(把缺口判据变成噪声) ⇒ 必须**不**列入。
Assert-True "baseline: 无 accept => 不含 accept-output(否则每 run 假报缺件)" (-not ($n0 -contains 'accept-output'))

# W1b/W4 收口 (2026-09-22): `review` 件 —— 为什么既要**在**基线里、又要**带 ephemeral**:
#   ① 不在基线里 ⇒ `review` 一旦写过 `review.json`, 门禁的 undeclared 判据(**动态枚举 runDir**)
#      就把该件报成"已归档但未被任何 subject 覆盖"的可重放缺口(实测 run `202609221131192690`)。
#   ② 在基线里但**不带** ephemeral ⇒ 每个没 review 过的 run 都假报 `missing-artifact`(噪声判据)。
#   ⇒ 两条必须**同时**成立, 故本块的两个断言缺一不可(只断言"存在"会放过 ②, 只断言 ephemeral 会放过 ①)。
$rb = @($b0 | Where-Object { $_.name -eq 'review' })
Assert-True "baseline: 含 review 件(path=review.json)" (
    $rb.Count -eq 1 -and $rb[0].path -eq 'review.json')
Assert-True "baseline: review 件带 ephemeral=true(否则未 review 的 run 假报 missing-artifact)" (
    $rb.Count -eq 1 -and $rb[0]['ephemeral'] -eq $true)

$b1 = @(Get-FrameworkSubjects @('echo ok') $true)
$n1 = @($b1 | ForEach-Object { $_.name })
Assert-True "baseline: 有 accept+golden => 13 件" ($b1.Count -eq 13)
Assert-True "baseline: 有 accept+golden => 含 accept-output/accept-golden-output" (
    ($n1 -contains 'accept-output') -and ($n1 -contains 'accept-golden-output'))

# 合并: 卡里历史遗留的框架件声明必须与基线**去重**(否则同一件在链上出现两次)
$cardSubs = @(
    @{ name = 'prompt'; path = 'prompt.txt'; digest = 'sha256'; collect = ''; ephemeral = $false }
    @{ name = 'station-tmp-log'; path = ''; collect = 'tail -5 /tmp/x.log'; digest = 'sha256'; ephemeral = $true }
)
$mg = @(Merge-EvidenceSubjects $cardSubs @() $false)
# 9(基线) + 2(卡声明) - 1(其中 prompt 与基线同 path, 去重) = 10
# O-56 (2026-09-25): 10 -> 9 —— `accept-cmds` 已改**条件列**（无 accept 的卡站上**永不产出**该件）。
#   与 §218 那条同性质: **合法演进**（判据缺陷修复），故改期望值而非改代码。
Assert-True "merge: 基线9 + 卡声明2 - 重复1 = 10" ($mg.Count -eq 10)
Assert-True "merge: 卡声明与基线同 path 只出现一次" ((@($mg | Where-Object { $_.path -eq 'prompt.txt' })).Count -eq 1)
$tmp = @($mg | Where-Object { $_.name -eq 'station-tmp-log' })
Assert-True "merge: 卡特有 subject 保留(collect/ephemeral 未丢)" (
    $tmp.Count -eq 1 -and $tmp[0].collect -eq 'tail -5 /tmp/x.log' -and $tmp[0].ephemeral -eq $true)
Assert-True "merge: 五键齐备(免得下游取键得 null 静默传播)" (
    (@($mg | Where-Object { -not ($_.Contains('name') -and $_.Contains('path') -and
                                $_.Contains('collect') -and $_.Contains('digest') -and
                                $_.Contains('ephemeral')) })).Count -eq 0)
# 合并必须**透传** ephemeral: 若 Merge 这一环把 ephemeral 吃成缺省 false, 基线里那两条 review 断言
#   就只是"函数返回值好看", 发射到 run.json 的形状仍是 false ⇒ 缺口照旧。断言合并**结果**而非仅基线。
Assert-True "merge: review 件经合并后仍 ephemeral=true(透传, 非仅基线好看)" (
    (@($mg | Where-Object { $_.name -eq 'review' -and $_.ephemeral -eq $true })).Count -eq 1)

# O-37 补足 (2026-09-24): run.json 的 subjects 也要带 `state` 足迹 —— merge 结果**透传**卡声明
#   与基线的 state, 使"collect 用 state 拉了文件"这件事**在元数据里有痕**(而非 collect 侧二次取卡对账)。
#   两个方向都证: ①有声明者透传到合并结果; ②无声明者缺省空串(保六键纯净, 不插 null)。
$cardSubsSt = @(@{ name = 'station-reality'; path = 'station-reality.json'; collect = ''; digest = 'sha256'; ephemeral = $false; state = 'out/station-reality.json' })
$mgSt = @(Merge-EvidenceSubjects $cardSubsSt @() $false)
$srSt = @($mgSt | Where-Object { $_.name -eq 'station-reality' })
Assert-True "merge: 卡声明 state 透传到合并结果(run.json 留痕)" ($srSt.Count -eq 1 -and $srSt[0]['state'] -eq 'out/station-reality.json')
Assert-True "merge: 未声明 state 的件缺省空串(保六键纯净, 不插 null)" ((@($mgSt | Where-Object { $_.state -eq '' })).Count -ge 9)

# 路B 的核心目的: **无 manifest 的卡**(= 71 个真实 run 的来源)也能拿到非空声明 ⇒ 不再是 recipe v1
$m0 = @(Merge-EvidenceSubjects @() @() $false)
Assert-True "merge: 空卡仍得 9 件(=> 不再退化为 recipe v1)" ($m0.Count -eq 9)

# --- O-15/AUDIT (2026-09-21): claude 备路按路基线(证据面到齐 => recipe v2) ---
# 该路归档件集 = opencode 子集 + stderr, 无 judgment-record 等远端合成批件
$cb = @(Get-ClaudeFrameworkSubjects @() $false)
$cbn = @($cb | ForEach-Object { $_.name })
Assert-True "claude: 无 accept/golden => 5 件" ($cb.Count -eq 5)
Assert-True "claude: 含 agent-output/prompt/stderr/card" (
    ($cbn -contains 'agent-output') -and ($cbn -contains 'prompt') -and
    ($cbn -contains 'stderr') -and ($cbn -contains 'card'))
# W1b/W4 收口: 与主路同理(该路 run 一样可被 review ⇒ 一样落 review.json) ⇒ 两条件同时断言
$crb = @($cb | Where-Object { $_.name -eq 'review' })
Assert-True "claude baseline: 含 review 件且 ephemeral=true(否则重演同一条 undeclared 缺口)" (
    $crb.Count -eq 1 -and $crb[0].path -eq 'review.json' -and $crb[0]['ephemeral'] -eq $true)
# 负向自证: claude 基线**不得**混入 opencode 专用件, 否则每 run 假报缺件(噪声判据)
Assert-True "claude: 无 judgment-record/workdiff/sessmeta/attach/mishap" (-not (
    ($cbn -contains 'judgment-record') -or ($cbn -contains 'workspace-diff') -or
    ($cbn -contains 'session-meta') -or ($cbn -contains 'attach-manifest') -or
    ($cbn -contains 'progress-trace') -or ($cbn -contains 'accept-cmds') -or ($cbn -contains 'golden-cmd')))

$cb1 = @(Get-ClaudeFrameworkSubjects @('echo ok') $true)
$cbn1 = @($cb1 | ForEach-Object { $_.name })
Assert-True "claude: 有 accept+golden => 7 件" ($cb1.Count -eq 7)
Assert-True "claude: 含 accept-output/accept-golden-output" (
    ($cbn1 -contains 'accept-output') -and ($cbn1 -contains 'accept-golden-output'))

# 合并: claude 走 baselineFn 分支 —— 空卡 => 得 claude 基线(5), 不掺主路 11 件
$cmg = @(Merge-EvidenceSubjects @() @() $false { param($ac,$ga) Get-ClaudeFrameworkSubjects $ac $ga })
Assert-True "claude merge: 空卡 => 5 件(claude 基线, 而非主路 11)" ($cmg.Count -eq 5)
# 去重: 卡声明与 claude 基线同 path(prompt.txt)只出现一次
$csubs = @(
    @{ name = 'prompt'; path = 'prompt.txt'; digest = 'sha256'; collect = ''; ephemeral = $false }
    @{ name = 'station-tmp-log'; path = ''; collect = 'tail -5 /tmp/x.log'; digest = 'sha256'; ephemeral = $true }
)
$cmg2 = @(Merge-EvidenceSubjects $csubs @() $false { param($ac,$ga) Get-ClaudeFrameworkSubjects $ac $ga })
Assert-True "claude merge: 基线5 + 卡声明2 - 重复1 = 6" ($cmg2.Count -eq 6)
Assert-True "claude merge: prompt.txt 只出现一次" ((@($cmg2 | Where-Object { $_.path -eq 'prompt.txt' })).Count -eq 1)
Assert-True "claude merge: 卡特有件保留" ((@($cmg2 | Where-Object { $_.name -eq 'station-tmp-log' })).Count -eq 1)
# baselineFn 缺省(主路调用点)不传时行为不变 => 既有的 9 件合并仍成立(防退化; O-56: 10 -> 9)
$defmg = @(Merge-EvidenceSubjects @() @() $false)
Assert-True "claude merge: 缺省 baselineFn 仍得主路 9 件(未破坏主路调用)" ($defmg.Count -eq 9)

# --- O-15/AUDIT (2026-09-21): auto-fallback 触发判定(纯函数, rc 表) ---
# 正向: 只认 rc=6(引擎死锁/超时)才切 claude 备路
Assert-True "fallback: rc=6 => true(引擎死锁/超时才兜底)" (Test-FallbackEligible 6)
# 负向: 任务真实结果/基建门**不得**触发 fallback(否则掩盖真实错误)
$noFallback = ($true)
foreach ($rc in @(0, 1, 5, 9, 10, 12, 24, 13)) {
    if (Test-FallbackEligible $rc) { $noFallback = $false }
}
Assert-True "fallback: rc in {0,1,5,9,10,12,24,13} 均不触发(不掩盖真实错误)" $noFallback

# --- C1 (2026-09-21): 「引擎**明确拒绝**」(ctx 超限 400) 必须从 rc=6 里分出来 → rc=14 ---
# 为什么: rc=6 的语义是"引擎在预算内产不出终态" ⇒ 备路该兜; 而 ctx 超限是**引擎秒回 400、
#   客户端不识别而挂死**(O-21/O-23 + 社区 anomalyco/opencode#11286 已定性) ⇒ **换后端也兜不住**
#   (ctx 不够, 换到哪都不够) ⇒ 让备路兜它 = 白烧一轮 + 把配置问题伪装成引擎问题。
Assert-True "ctxoverflow: llama.cpp 逐字串 ⇒ true" (
    Test-CtxOverflowError 'Error: request (12536 tokens) exceeds the available context size (8192 tokens)')
Assert-True "ctxoverflow: 异常类名 ContextOverflowError ⇒ true" (
    Test-CtxOverflowError 'ContextOverflowError: request (62079 tokens) exceeds ...')
Assert-True "ctxoverflow: 普通 agent 输出 ⇒ false(不误判)" (
    -not (Test-CtxOverflowError "I finished the task. All tests pass. context was sufficient."))
Assert-True "ctxoverflow: 空/null ⇒ false(不抛)" (
    (-not (Test-CtxOverflowError '')) -and (-not (Test-CtxOverflowError $null)))
Assert-True "ctxoverflow: 只提到 context 但非该串 ⇒ false(判据刻意不宽泛)" (
    -not (Test-CtxOverflowError 'the context window is large enough; timeout after 10s'))
# ⚠ 实弹 (2026-09-21) 逐字取自真实站的 opencode 错误体 —— **形态 B**(客户端/SDK 侧长度校验)。
#   它与形态 A(引擎侧 llama.cpp 400)**落点不同**: B 是**快速失败 rc=1**, A 是**挂死 ⇒ rc=6**。
#   两类都要认(否则形态 B 混在"agent 自己失败"里看不出), 但**只有 A 才改 rc**(见下)。
$formBReal = 'Error: {"message":"Message too long: 104003 tokens exceeds the 32768-token context window. Try increasing the Context Length in Model settings, or shorten the conversation.","type":"invalid_request_error","param":"messages","code":"context_length_exceeded"}'
Assert-True "ctxoverflow: 形态B 真实错误体 ⇒ true(实弹逐字)" (Test-CtxOverflowError $formBReal)
Assert-True "ctxoverflow: 形态B 错误码单独出现也认" (Test-CtxOverflowError '{"code":"context_length_exceeded"}')
# 是否改写 rc —— 纯函数, 正负双向 + 不掩盖性
Assert-True "ctxcode: 形态A(rc=6)+命中 ⇒ 14(分出来, 阻止备路兜错)" (
    (Resolve-CtxOverflowCode -code 6 -isOverflow $true) -eq 14)
Assert-True "ctxcode: 形态B(rc=1)+命中 ⇒ **维持 1**(不掩盖 rc=1 的其它含义)" (
    (Resolve-CtxOverflowCode -code 1 -isOverflow $true) -eq 1)
Assert-True "ctxcode: 未命中 ⇒ 原码不变(6/1/0/9 抽查)" (
    ((Resolve-CtxOverflowCode -code 6 -isOverflow $false) -eq 6) -and
    ((Resolve-CtxOverflowCode -code 1 -isOverflow $false) -eq 1) -and
    ((Resolve-CtxOverflowCode -code 0 -isOverflow $false) -eq 0) -and
    ((Resolve-CtxOverflowCode -code 9 -isOverflow $false) -eq 9))

# --- P3 (2026-09-21): claude 备路**站上化**（按 sensitivity 分流） ---
# 目标: `local-only` 卡的 claude 通道必须跑在**站上**并打**站上本地引擎**(物理不出网);
#   站上不可用 ⇒ **fail-closed**(绝不退回主控本地 —— 那会打云端 OpenRouter = 出网)。
# 选站纯函数: **优先排除刚 rc=6 的那一站**(它的引擎可能已被 wedge), 但不丢掉它(放最后)。
Assert-True "station: avoid='B' ⇒ 异站优先且被排除者排最后 (A,C,B)" (
    ((Resolve-ClaudeStationCandidates -Avoid 'B' -Stations @('A', 'B', 'C')) -join ',') -eq 'A,C,B')
Assert-True "station: avoid='' ⇒ 原序 (A,B,C)" (
    ((Resolve-ClaudeStationCandidates -Avoid '' -Stations @('A', 'B', 'C')) -join ',') -eq 'A,B,C')
Assert-True "station: 只有被排除的那一站 ⇒ **仍返回它**(不因排除而丢候选)" (
    ((Resolve-ClaudeStationCandidates -Avoid 'A' -Stations @('A')) -join ',') -eq 'A')
Assert-True "station: 候选为空 ⇒ 空数组(调用方据此 fail-closed)" (
    (@(Resolve-ClaudeStationCandidates -Avoid 'A' -Stations @()).Count) -eq 0)
# ⚠ 2026-09-21 复查发现的**交互缺陷**: pref(卡的 model 指向的站) 会**覆盖率** avoid —— 而兜底场景下
#   pref 常正是刚死锁的那一站 ⇒ 不修就等于"避免死锁站"被架空。规则①(avoid)必须胜过规则②(pref)。
Assert-True "station: pref=B, avoid=B ⇒ **avoid 胜**(B 垫底, 不是第一)(复查修掉的交互缺陷)" (
    ((Resolve-ClaudeStationCandidates -Avoid 'B' -Stations @('A','B','C') -Preferred 'B') -join ',') -eq 'A,C,B')
Assert-True "station: pref=B, avoid='' ⇒ pref 提前 (B,A,C)" (
    ((Resolve-ClaudeStationCandidates -Avoid '' -Stations @('A','B','C') -Preferred 'B') -join ',') -eq 'B,A,C')
Assert-True "station: pref=C, avoid=B ⇒ pref 提到最前 (C,A,B)" (
    ((Resolve-ClaudeStationCandidates -Avoid 'B' -Stations @('A','B','C') -Preferred 'C') -join ',') -eq 'C,A,B')
Assert-True "station: pref 不在候选集 ⇒ 顺序不变(不因未知 pref 而丢站)" (
    ((Resolve-ClaudeStationCandidates -Avoid '' -Stations @('A','B') -Preferred 'Z') -join ',') -eq 'A,B')
# 结构性断言(安全带): ① 判据按**后端属性**参数化(P2 的核心), 不再硬编码 $true;
#   ② 站上不可用时**明确 return 4**(fail-closed)且**不**回退本地 spawn。
Assert-True "station: 判据已参数化 -backendEgress (-not \$backendLocal)(P2 的核心; D7 起与位置解耦)" (
    $content.Contains('-backendEgress (-not $backendLocal)'))
Assert-True "station: 分流判据 = local-only **或** 路由声明了站(D7 拆成两个量)" (
    $content.Contains('$useStation = ($sens -eq ''local-only'') -or [bool]$r[''station'']'))
Assert-True "station: 后端属性独立于位置(\$backendLocal 只由 sensitivity 判)(D7 拆锁)" (
    $content.Contains('$backendLocal = ($sens -eq ''local-only'')'))
Assert-True "station: 站上不可用 ⇒ fail-closed(有 REJECT 行 + return 4, 且该分支内无 Invoke-ClaudeFly 回退)" (
    $content.Contains('REJECT local-only-no-station-engine (exit 4)'))
$iNoSt = $content.IndexOf('REJECT local-only-no-station-engine')
$iBlk  = $content.IndexOf('$useStation = ($sens -eq ''local-only'') -or [bool]$r[''station'']')
$blkSeg = $content.Substring($iBlk, $iNoSt - $iBlk)
Assert-True "station: fail-closed 分支里**没有**主控本地 spawn(回退=出网)" (
    -not ($blkSeg -match 'Invoke-ClaudeFly\s'))
Assert-True "station: 两处 runner 调用点都已分流(首跑 + resume)" (
    ([regex]::Matches($content, 'Invoke-ClaudeFly-Station -hostName')).Count -ge 2)
# ⚠ 位置断言 —— 2026-09-21 **实弹踩到的顺序 bug**: 初版把 `$stPref` 块放在 `$useStation` 赋值
#   **之前** ⇒ PS 未定义变量为 `$null` ⇒ `if ($useStation)` 为假 ⇒ 走旧的 `REJECT claude-station`
#   分支 ⇒ `local-only` 卡被旧语义误拒。**夹具当时全绿**(它只查"串在不", 查不出顺序) ⇒ 补此条。
$iUse = $content.IndexOf('$useStation = ($sens -eq ''local-only'') -or [bool]$r[''station'']')
$iPref = $content.IndexOf("`$stPref = ''")
Assert-True "station: \$useStation 赋值**早于** \$stPref 使用(实弹踩到的顺序 bug)" (
    $iUse -gt 0 -and $iPref -gt 0 -and $iUse -lt $iPref)

# --- D7 (2026-09-25): **站上 claude + OpenRouter**（撤掉"站上 ⇒ 必不出网"那把锁） ---
# 锁的形态: `$useStation = ($sens -eq 'local-only')` 让"跑在站上"与"不出网"互为充要
#   ⇒ 站上 claude **永远配不了 OpenRouter**(真正想跑的形态)。D7 把它拆成两个独立量。
Assert-True "D7: 旧闸已撤除(无 `REJECT claude-station=` 残留)" (
    -not $content.Contains('REJECT claude-station=$'))
Assert-True "D7: 替代闸 = 站上 egress 模式打 local/* id ⇒ 前置拒(fail-closed)" (
    $content.Contains('REJECT claude-station-egress-local-id'))
Assert-True "D7: 站不可用 ⇒ 拒跑并列出替代站(**不静默换站**, 用户裁定 2026-09-25)" (
    $content.Contains('REJECT claude-station-unavailable='))
Assert-True "D7: 站上 egress 就绪判据是**独立函数**(不是引擎就绪)" (
    $content.Contains('function Test-StationClaudeEgressReady'))
Assert-True "D7: 该判据含 claude bin + 站上 openrouter.key 两条" (
    $content.Contains('command -v claude') -and $content.Contains('$HOME/.config/rpc/openrouter.key'))
# egress 分支**不得**复用引擎就绪探针 —— 那会要求先 infer-load, 而该模式物理上不需要引擎(实测)。
$iM2 = $content.IndexOf('模式② (2026-09-25)')
$iEg = $content.IndexOf('CLAUDE_EGRESS_STATION_SELECT')
Assert-True "D7: egress 分支内**不**调 Test-StationEngineReady(该模式不需要引擎)" (
    $iM2 -gt 0 -and $iEg -gt $iM2 -and
    -not ($content.Substring($iM2, $iEg - $iM2) -match 'Test-StationEngineReady'))
Assert-True "D7: 站上脚本有 or 分支(OpenRouter 三件套语义)且 API_KEY 显式置空" (
    $content.Contains('"ANTHROPIC_BASE_URL":"https://openrouter.ai/api"') -and
    $content.Contains('"ANTHROPIC_API_KEY":""'))
Assert-True "D7: or 模式缺站上 openrouter.key ⇒ 站上脚本 fail-closed(不回落本地引擎)" (
    $content.Contains('缺 $ORKEYF ⇒ fail-closed'))
Assert-True "D7: 站上 --model 实参按后端分(local=引擎别名 main / or=真 id)" (
    $content.Contains('$stModelAlias = if ($backendLocal) { ''main'' } else { $id }'))
Assert-True "D7: 两处 runner 调用点都传 -Mode/-ModelId(站上 settings 按后端分叉)" (
    ([regex]::Matches($content, '-WorkDir \$stWorkDir -Mode \$stMode -ModelId \$stModelId')).Count -ge 2)
Assert-True "D7: 站上脚本调用透传 mode/model-id(第 5/6 个实参)" (
    $content.Contains('$p3id'' ''$Mode'' ''$ModelId'))
# ⚠ 2026-09-25 实测踩到(同族第 2 例): `Invoke-RemoteScript` 早在 2026-09-24 补过 CRLF→LF 归一(R9 根因),
#   但 `Invoke-ClaudeFly-Station` **自写文件**、绕过那道归一 ⇒ Windows checkout 下站上 `set -uo pipefail\r`
#   失败(`rc=7`) ⇒ 站上 claude 路径**整条**不可用(含 P3 原有的 local-only 支)。故就地补归一 + 护栏。
Assert-True "D7: 生成站上脚本时做 CRLF→LF 归一(本函数自写文件, R9 那道保护不到)" (
    $content.Contains('$runSh = $runSh -replace "`r`n", "`n"'))
# ⚠ 2026-09-25 实测踩到(同族第 3 例): O-31 把站上临时名"固定名 → $PFX 前缀"时**丢了 `/tmp/`**,
#   而脚本已 `cd "$WORK"` ⇒ 相对路径解析到工作区 ⇒ `没有那个文件或目录` ⇒ 首跑+续跑均 rc=7。
#   (O-31 注记自认"站上实机并发复跑未做" ⇒ 这正是漏掉的。) 故钉住**绝对路径**形态。
Assert-True "D7: 站上脚本的 stdin/out/err 引用带 /tmp/(O-31 前缀化时丢过 ⇒ 实测 rc=7)" (
    $content.Contains('"/tmp/${PFX}_in.txt"') -and
    $content.Contains('"/tmp/${PFX}_out.txt"') -and
    $content.Contains('"/tmp/${PFX}_err.txt"'))
# ROUTE_TABLE 真值断言(用**提取出来的真表**, 不是文本 grep): 三别名同 id、站分别 A/B/C、cli=claude。
Assert-True "D7: ROUTE_TABLE claude-a/-b/-c = 同一 id + station A/B/C + cli=claude" (
    $Script:ROUTE_TABLE['claude-a']['station'] -eq 'A' -and
    $Script:ROUTE_TABLE['claude-b']['station'] -eq 'B' -and
    $Script:ROUTE_TABLE['claude-c']['station'] -eq 'C' -and
    $Script:ROUTE_TABLE['claude-a']['id'] -eq $Script:ROUTE_TABLE['claude']['id'] -and
    $Script:ROUTE_TABLE['claude-c']['id'] -eq $Script:ROUTE_TABLE['claude']['id'] -and
    $Script:ROUTE_TABLE['claude-a']['cli'] -eq 'claude' -and
    $Script:ROUTE_TABLE['claude']['station'] -eq '')
# ⚠ "优先选与死锁站不同的一站"这条 **2026-09-21 复查时实测未生效**(只读 env, 而无人填 env):
#   ⇒ 兜底调用点必须把主路死锁站传进来; 且 `$avoid` 必须**优先取参数**(env 降级为手工覆盖通道)。
Assert-True "station: AUTO_FALLBACK 调用点把主路死锁站传进来(-AvoidStation \$station)" (
    $content.Contains('-taskType $taskType -AvoidStation $station'))
Assert-True "station: \$avoid **优先取参数**, env 降级为手工覆盖通道" (
    $content.Contains('$avoid = if ($AvoidStation) { $AvoidStation } elseif ($env:AGENT_AVOID_STATION)'))
# 位置断言(结构性, 守"四处一致"的不变式): 检测必须**早于**台账 `$line = …$code…` —— 否则
#   台账说 6、进程返 14(以及 run.json/TASK_DONE 与 fallback 判定各自打架) ⇒ 自己造一次"rc 不可信"。
$iCtx = $content.IndexOf('Test-CtxOverflowError $agentOutText')
$iLed = $content.IndexOf('$line = "$ts,$proj,$id,$sens,$code,$queue_s,$run_s"')
Assert-True "ctxoverflow: 检测点存在且**早于台账行**(四处 $code 一致性)" (
    $iCtx -gt 0 -and $iLed -gt 0 -and $iCtx -lt $iLed)
Assert-True "ctxoverflow: 检测**早于** AUTOFALLBACK 判定点(否则备路仍会被触发)" (
    $iCtx -lt $content.IndexOf('$AutoFallback -and $effectiveCli -eq ''opencode'''))

# --- P0 止血 (2026-09-21): sensitivity × **后端出网性** 硬闸 ---
# 洞: local-only 硬闸三处判据一律只判 `^opencode/`, 而 claude 备路(直接入口 + AUTO_FALLBACK
#   入口)无 sensitivity 判据 ⇒ local-only 卡的 prompt 可**实际出网**(破 DESIGN §358 不变式)。
# ⚠ **同日撤回**了一条 `sanitized × 可能训练` 规则 —— 理由见 Get-SensitivityBackendReject 的留档
#   注释(①与档位定义冲突: sanitized 抹完 = public; ②不对称 ⇒ 虚假安心; ③"免费档可能训练"是使用
#   免费额度的固有代价)。⇒ 本夹具只剩"出网"这一维; **探针的 C/D 例反向守卫"不许再加回那条闸"**。
Assert-True "reject: local-only + 出网后端 => 'local-only+egress'" (
    (Get-SensitivityBackendReject -sensitivity 'local-only' -backendEgress $true) -eq 'local-only+egress')
Assert-True "reject: local-only + 本地引擎(不出网) => 放行" (
    (Get-SensitivityBackendReject -sensitivity 'local-only' -backendEgress $false) -eq '')
Assert-True "reject: sanitized + 出网后端 => 放行(无'训练档'判据 —— 那条规则已撤回)" (
    (Get-SensitivityBackendReject -sensitivity 'sanitized' -backendEgress $true) -eq '')
Assert-True "reject: public + 出网后端 => 放行(public 是唯一无闸档)" (
    (Get-SensitivityBackendReject -sensitivity 'public' -backendEgress $true) -eq '')
Assert-True "reject: 缺省(空 sensitivity) + 出网后端 => 放行(与既有三处闸'缺省=public'一致)" (
    (Get-SensitivityBackendReject -sensitivity '' -backendEgress $true) -eq '')
# 覆盖(结构): 判据必须在**两个入口都真被调用** —— 只判一处会漏(这正是本洞的成因)。
# ⚠ P3 (2026-09-21) 更新: 原断言要求两处**都**是 `-backendEgress $true`(P0 期的实现细节)。
#   分流后**有意**不同: 兜底入口起的 claude 在**主控本地**(=云端=出网) ⇒ `$true`;
#   直接入口按**后端属性** ⇒ `(-not $backendLocal)`(站上本地时不出网)。故断言改为:
#   "两处都调判据" + "两种输入形式都在"(后者正是 P2 的核心, 单列一条以防被改回硬编码)。
#   ⚠ D7 (2026-09-25): 直接入口的入参由 `$useStation` 改为 `$backendLocal` —— **值等价**,
#     但语义**独立于位置**(站上也能出网) ⇒ 断言同步。
Assert-True "reject: 判据在两个入口均被调用(直接入口 + 兜底入口)" (
    ([regex]::Matches($content, [regex]::Escape('Get-SensitivityBackendReject -sensitivity $sens -backendEgress'))).Count -ge 2)
Assert-True "reject: 兜底入口用 \$true(主控本地=出网), 直接入口用 (-not \$backendLocal) 按后端属性" (
    $content.Contains('Get-SensitivityBackendReject -sensitivity $sens -backendEgress $true') -and
    $content.Contains('Get-SensitivityBackendReject -sensitivity $sens -backendEgress (-not $backendLocal)'))
Assert-True "reject: 两条路径的拒绝串可分辨路径(claude-direct / fallback 均在)" (
    $content.Contains('(claude-direct, $id)') -and $content.Contains('(fallback, $fbModel)'))

# --- P4 (2026-09-21): claude 通道的**独立预算** `fallback-timeout-s` ---
# 缺陷: 备路是被主路失败**触发**的, 却继承同一张卡的 `timeout_s`; 而主路往往正是**耗尽**预算才
#   rc=6(实测 fallback-deadlock 卡 `timeout_s:10` 就是被 `timeout 10` 掐断) ⇒ 备路 = "用别人烧剩的"
#   ⇒ 必然立刻超时 ⇒ **白切**。修法: claude 通道用自己的首跑预算。
$bA = Resolve-ClaudeBudget -timeoutS 900 -fallbackTimeoutS 0 -continueTimeoutS 0
Assert-True "budget: 卡未设 fallback => first 回落 timeout_s(不回归)" (
    $bA['first'] -eq 900 -and $bA['first_src'] -eq 'timeout_s')
Assert-True "budget: 卡未设 fallback => resume 跟随 first(=900)" ($bA['resume'] -eq 900)
$bB = Resolve-ClaudeBudget -timeoutS 10 -fallbackTimeoutS 120 -continueTimeoutS 0
Assert-True "budget: 卡设了 fallback => first 用它(120) 且来源可判" (
    $bB['first'] -eq 120 -and $bB['first_src'] -eq 'fallback-timeout-s')
# ⚠ 行为变更点: resume 的**原**缺省是 timeout_s, 现改为跟随 first —— 否则"设了 fallback 但没设
#   continue"的卡会"首跑用备路预算、续接回落主路预算"(错配)。此断言守住该变更。
Assert-True "budget: fallback 生效时 resume 跟随 first(120), **不**回落主路 10" ($bB['resume'] -eq 120)
$bC = Resolve-ClaudeBudget -timeoutS 10 -fallbackTimeoutS 120 -continueTimeoutS 30
Assert-True "budget: continue-timeout-s > 0 时优先(30)" ($bC['resume'] -eq 30)
Assert-True "budget: 畸形/非正值一律回落(fallback=-1 => 取 timeout_s 7)" (
    (Resolve-ClaudeBudget -timeoutS 7 -fallbackTimeoutS -1 -continueTimeoutS -1)['first'] -eq 7)
# ⚠ 卡键必须同时进 `Get-FrontMatter` 的**预置键集** —— 通用键分支有 `ContainsKey` 白名单门,
#   否则卡里写了也会被**静默丢弃**(该门的历史坑见 evidence-manifest/accept-golden 注释)。
$ftsCard = Join-Path $tmpCards 'fallback-budget.md'
@"
---
proj: paper
task: budget parse test
model: claude
sensitivity: public
timeout_s: 10
fallback-timeout-s: 77
---
body
"@ | Set-Content $ftsCard -Encoding utf8
Assert-True "budget: 卡里的 fallback-timeout-s 真能解析进 front-matter(白名单不丢)" (
    ([int]((Get-FrontMatter $ftsCard)['fallback-timeout-s'])) -eq 77)
Assert-True "budget: 未写该键的卡 => 归一为 0 sentinel(不是空串/异常)" (
    ([int]((Get-FrontMatter $plainCard)['fallback-timeout-s'])) -eq 0)

# --- O-15/AUDIT (2026-09-21): claude 本地备路的判据 shell 语义 = bash(本地 Git Bash) ---
# 定案: 卡的 accept/accept-golden **一律 bash 语义**; 两条路只差执行机器与 cwd, 不差 shell。
#   (原用 PowerShell Invoke-Expression ⇒ 实测 `true` 得 rc=1 ⇒ 即使 claude 成功 accept 也必判失败)
$lb = Resolve-LocalBash
Assert-True "bash: 解析到本地 Git Bash 且**不是** WSL 的 system32\bash.exe" ($lb -ne '' -and $lb -notmatch 'system32')
# `true` 是 bash 内建; 在 PS 里 `Invoke-Expression 'true'` 会抛 ⇒ 这正是本次修掉的"判据级假红灯"
$fmLog = Join-Path $env:TEMP 'fm_bash_semantics.log'
Assert-True "bash: 'true' => rc 0 (PS Invoke-Expression 会得 1 = 本次修的 bug)" (
    (Invoke-LocalBashCmd -bashPath $lb -cmd 'true' -cwd $env:TEMP -logFile $fmLog) -eq 0)
Assert-True "bash: 'false' => rc 非 0(判据真能 FAIL, 非恒过)" (
    (Invoke-LocalBashCmd -bashPath $lb -cmd 'false' -cwd $env:TEMP -logFile $fmLog) -ne 0)
Remove-Item $fmLog -ErrorAction SilentlyContinue

# --- 2026-09-21: claude 备路型号必须**经 OpenRouter 可服务**(不能是 Claude 原生 id) ---
# 实测依据: claude-opus-4-7 / claude-sonnet-4-5 / claude-opus-4-1 经 OpenRouter **全部 403**
#   `This model is not available in your region.`(Claude 原生 id 被路由到真实 Anthropic 上游);
#   而 thinkingmachines/*:free 与 nvidia/*:free 可用。故这里守的是**不变量**而非具体型号。
$rtc = $Script:ROUTE_TABLE['claude']; $rto = $Script:ROUTE_TABLE['claude-opus']
Assert-True "route: claude 备路型号非 Claude 原生 id(否则经 OpenRouter 403 地区墙)" ("$($rtc.id)" -notmatch '^claude-')
Assert-True "route: claude-opus 备路型号非 Claude 原生 id" ("$($rto.id)" -notmatch '^claude-')
Assert-True "route: 备路型号形如 OpenRouter id(含 /)" ("$($rtc.id)" -match '/' -and "$($rto.id)" -match '/')
Assert-True "route: claude/claude-opus 仍 station=''(本地执行, 不走 ssh)" ("$($rtc.station)" -eq '' -and "$($rto.station)" -eq '')
Assert-True "route: claude/claude-opus 仍 cli='claude'" ("$($rtc.cli)" -eq 'claude' -and "$($rto.cli)" -eq 'claude')
# env AGENT_FALLBACK_MODEL 覆盖需能解析 ⇒ 必须有 full-id 直传条目
Assert-True "route: 备路型号有 full-id 直传条目(env AGENT_FALLBACK_MODEL 才能解析)" (
    $Script:ROUTE_TABLE.ContainsKey("$($rtc.id)"))
# 备路两型号均为 `:free` —— 这是 OPEN-ISSUES「备路全档依赖'免费模型允许训练'开关 + 免费日额度」
#   那条登记的**事实前提**。若谁把备路换成付费型号, 这条会亮提醒同步那条登记(与闸无关: 那条
#   `sanitized × 可能训练` 规则已于 2026-09-21 撤回, 见上)。
Assert-True "route: 备路两型号均为 :free(⇒ OPEN-ISSUES 的'依赖免费开关/额度'前提成立)" (
    "$($rtc.id)" -match ':free' -and "$($rto.id)" -match ':free')

# --- 2026-09-21: claude 本地路的 **cwd 接线**(P3 首跑实弹发现的缺陷, 见 Invoke-ClaudeFly 注释) ---
#   缺陷形态: `Invoke-ClaudeFly` 的 `ProcessStartInfo` 不设 `WorkingDirectory` ⇒ 子进程继承**控制台** cwd
#   (常态 `d:\RPC`), 而 prompt 用**相对路径**引用附件(`.attach/<name>`)且附件落在 `<projRoot>\.attach`
#   ⇒ **附件不可达**。实测: 转录 `~/.claude/projects/D--RPC/<s>.jsonl` 里 `cwd="D:\RPC"` + `tool_use blocks=0`。
# ⚠ 这是**结构断言**(查"接线在不"), **不是行为断言** —— 行为证据只有实弹能给。仍然值得守:
#   去掉 `-cwd` 传参或 `WorkingDirectory` 赋值都不会报错、不会让别的断言变红 ⇒ 没有这条就会**静默回退**。
$flyAst = @($fns) | Where-Object { $_.Name -eq 'Invoke-ClaudeFly' } | Select-Object -First 1
Assert-True "cwd: Invoke-ClaudeFly 存在且形参含 `$cwd" (
    $flyAst -and $flyAst.Extent.Text -match '\$cwd\s*=\s*''''')
Assert-True "cwd: Invoke-ClaudeFly 体内**显式**设 WorkingDirectory(不设则继承控制台 cwd)" (
    $flyAst -and $flyAst.Extent.Text -match '\$psi\.WorkingDirectory\s*=\s*\$cwd')
$cliText = [IO.File]::ReadAllText($cli)
$cwdCallSites = ([regex]::Matches($cliText, 'Invoke-ClaudeFly -argStr [^\r\n]*-budgetS \$\w+(?:Timeout)? -cwd \$projRoot')).Count
Assert-True "cwd: 两个本地调用点(首跑 + resume)都传 -cwd `$projRoot(实测 $cwdCallSites 处)" ($cwdCallSites -eq 2)

# --- W1a (2026-09-21): 后端属性判据 —— 把"型号前缀"换成"后端属性"的结构根因验证 ---
# 背景: 旧判据是白名单式 `-match '^opencode/'`, 每加一个云后端就漏一次(已漏两次: claude 备路 / review judge)。
# 三层断言: ① 函数行为(含**假想云端后端**) ② **真表覆盖率**(每个 id / 每个 judge 都被分类)
#           ③ **结构断言**(AST, 免疫注释): 全仓不再有"按型号前缀判敏感度"的残留。
# ⚠ 这些是**结构/单元**断言 —— 它们证明"接线正确"; **行为证据仍只有实弹能给**(见 REMEDIATION-PLAN §2)。
Assert-True "egress: 站内本地引擎(local/*) => 不出网" ((Get-BackendEgress 'local/gpt-oss-20b') -eq $false)
Assert-True "egress: 站上 openrouter(openrouter/*) => 出网" ((Get-BackendEgress 'openrouter/thinkingmachines/inkling:free') -eq $true)
Assert-True "egress: zen(opencode/*) => 出网" ((Get-BackendEgress 'opencode/nemotron-3-ultra-free') -eq $true)
# ★ 这条是**结构根因**的证明: 一个本仓**不存在**的云后端, 无需改判据即被纳管
Assert-True "egress: ★假想云端后端(brand-new-vendor/*) => 出网(新后端无需改判据)" ((Get-BackendEgress 'brand-new-vendor/some-model:free') -eq $true)
Assert-True "egress: 未知/空 id => 出网(fail-closed, 不默认放行)" ((Get-BackendEgress '') -eq $true -and (Get-BackendEgress 'noslash') -eq $true)

$rtIds = @($Script:ROUTE_TABLE.Values | ForEach-Object { [string]$_['id'] } | Sort-Object -Unique)
$rtEgress = @($rtIds | Where-Object { Get-BackendEgress $_ })
$rtLocal = @($rtIds | Where-Object { -not (Get-BackendEgress $_) })
Assert-True "egress: ROUTE_TABLE 扫 $($rtIds.Count) 个 id => 出网 $($rtEgress.Count) / 站内 $($rtLocal.Count)(两类都必须非空, 防判据恒真恒假)" ($rtIds.Count -gt 0 -and $rtEgress.Count -gt 0 -and $rtLocal.Count -gt 0)

$jtMissing = @($Script:JUDGE_TABLE.Keys | Where-Object {
        -not $Script:JUDGE_TABLE[$_].ContainsKey('egress') -or -not $Script:JUDGE_TABLE[$_].ContainsKey('compliance') })
Assert-True "egress: JUDGE_TABLE 全部 $($Script:JUDGE_TABLE.Keys.Count) 个 judge 都声明 egress+compliance(缺: $($jtMissing -join ','))" ($jtMissing.Count -eq 0)

# judge 三态 —— 与 review 闸**同构**（硬不变式 + 表驱动），故这里等于把闸的行为离线复现
function JudgeReject($alias, $sens) {
    $j = $Script:JUDGE_TABLE[$alias]
    $r = Get-SensitivityBackendReject -sensitivity $sens -backendEgress (Get-JudgeEgress $j)
    if (-not $r) { $r = Get-JudgeComplianceReject -judge $j -sensitivity $sens }
    return $r
}
Assert-True "judge: local-only × egress judge(ultra) => 拒" ((JudgeReject 'ultra' 'local-only') -ne '')
Assert-True "judge: sanitized × egress judge(ultra) => 放行(compliance 声明 public,sanitized)" ((JudgeReject 'ultra' 'sanitized') -eq '')
Assert-True "judge: public × egress judge(ultra) => 放行" ((JudgeReject 'ultra' 'public') -eq '')
Assert-True "judge: sanitized × 本地 judge(main) => 放行" ((JudgeReject 'main' 'sanitized') -eq '')
Assert-True "judge: local-only × 本地 judge(main) => 放行(本地不出网 —— 正是敏感卡该走的路)" ((JudgeReject 'main' 'local-only') -eq '')
Assert-True "judge: local-only × commercial(ENV 注入, 按出网) => 拒" ((JudgeReject 'commercial' 'local-only') -ne '')
Assert-True "judge: 未声明 compliance => 拒(fail-closed, 手工构造)" ((Get-JudgeComplianceReject -judge @{ type = 'local' } -sensitivity 'public') -eq 'judge-compliance-undeclared')

$ocMatch = @($ast.FindAll({ param($n)
            $n -is [System.Management.Automation.Language.BinaryExpressionAst] -and
            $n.Operator -eq 'Match' -and
            $n.Right.Extent.Text -match 'opencode/' }, $true))
Assert-True "gate: AST 中不再存在 `-match '<...>opencode/' 形式的判据(注释不算) —— 实测 $($ocMatch.Count) 处" ($ocMatch.Count -eq 0)
$gateCalls = ([regex]::Matches($cliText, 'Get-SensitivityBackendReject -sensitivity')).Count
Assert-True "gate: Get-SensitivityBackendReject 调用点 = 6(实测 $gateCalls) ⚠ 增删闸须同步改本数" ($gateCalls -eq 6)
Assert-True "gate: review 闸已接线 compliance(调用 Get-JudgeComplianceReject)" ($cliText -match 'Get-JudgeComplianceReject -judge')
Assert-True "gate: review 闸已接线 judge 属性(调用 Get-JudgeEgress)" ($cliText -match 'Get-JudgeEgress \$judge')

# --- W1b 裁定 A（2026-09-22）: review 出网前过同一套 scrub + block ---
# 决策被提成**纯函数** `Resolve-ReviewPrompt` ⇒ 这里给的是**行为证据**（不是"接线在不"），
#   因为返回值里带**真正要送出去的文本** —— 正是"行为证据不必依赖实弹"的那条路。
# ⚠ 样串一律**按段拼接**（不写字面量）: ① 本地 `secrets` 门禁会拦未掩码的 `sk-` 样串（它要求掩码或白名单）；
#   ② 远端 GitHub push-protection 另外会拦 `PRIVATE KEY` 字面量。两处都不是"能糊过去的东西"，故与
#   `_scrubber_coverage_test.ps1` 同法处理。
$SAMPLE_LEAKY = 'api key: ' + 'sk-' + 'a8bprobe1234567890abcdef' + ' and path D:\Paper\agent-out\secret.xlsx'
$revSend = Resolve-ReviewPrompt -prompt $SAMPLE_LEAKY -sensitivity 'public'
Assert-True "review: public => 原样发出(不抹, 保住评审保真度)" (
    $revSend['action'] -eq 'send' -and $revSend['reason'] -eq 'as-is' -and $revSend['prompt'] -eq $SAMPLE_LEAKY)
$revScrub = Resolve-ReviewPrompt -prompt $SAMPLE_LEAKY -sensitivity 'sanitized'
Assert-True "review: sanitized => 发出的是**被抹后**的文本(原文消失 + 出现占位符)" (
    $revScrub['action'] -eq 'send' -and $revScrub['reason'] -eq 'scrubbed' -and
    -not ($revScrub['prompt'] -like '*sk-a8bprobe*') -and $revScrub['prompt'] -like '*[[]REDACTED-KEY[]]*')
Assert-True "review: 抹是幂等的(对已抹文本再抹不二次破坏)" (
    (Resolve-ReviewPrompt -prompt $revScrub['prompt'] -sensitivity 'sanitized')['prompt'] -eq $revScrub['prompt'])
# ⚠ 私钥样串**按段拼接**（不写字面量）—— 远端 GitHub push-protection 会拦 PRIVATE KEY 字面量
#   （本地 `secrets` 门禁只认 `sk-`，拦不住它 ⇒ 这一条是**远端**约束）。见 _scrubber_coverage_test.ps1 同族注释。
$PEM = '-----BEGIN ' + 'OPENSSH PRIVATE KEY-----'
Assert-True "review: 私钥块 => 拒发(不是抹) —— 任何 sensitivity 都拒" (
    (Resolve-ReviewPrompt -prompt ("x`n$PEM`nAAA`n" + '-----END ' + 'OPENSSH PRIVATE KEY-----') -sensitivity 'sanitized')['action'] -eq 'reject' -and
    (Resolve-ReviewPrompt -prompt $PEM -sensitivity 'public')['action'] -eq 'reject')
# 位置断言: 消毒/拒必须在**发请求之前**（"算了不用"或"先发后抹"都会静默失效 —— 这类错很隐蔽）
# ⚠ 用 **AST 找实际的命令调用**，不用文本 IndexOf —— 前者免疫注释。
#   （实测教训: 第一版用文本搜 `Resolve-ReviewPrompt` 时命中的是**上方注释里的函数名**，
#     于是"调用被搬走/删掉"它照样 PASS ⇒ 判据在跑但没在判。这类错只在变异测试里才现形。）
$rvFn = @($fns) | Where-Object { $_.Name -eq 'Invoke-Review' } | Select-Object -First 1
Assert-True "review: Invoke-Review 函数体可被 AST 定位" ([bool]$rvFn)
$rvCmds = @($rvFn.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] }, $true))
$guardCmd = @($rvCmds | Where-Object { $_.GetCommandName() -eq 'Resolve-ReviewPrompt' }) | Select-Object -First 1
$sendCmd = @($rvCmds | Where-Object { $_.GetCommandName() -eq 'Invoke-Judge' }) | Select-Object -First 1
$iGuard = if ($guardCmd) { $guardCmd.Extent.StartOffset - $rvFn.Extent.StartOffset } else { -1 }
$iSend = if ($sendCmd) { $sendCmd.Extent.StartOffset - $rvFn.Extent.StartOffset } else { -1 }
Assert-True "review: 位置断言(AST) —— 消毒判定($iGuard) 早于 发请求($iSend)" ($iGuard -gt 0 -and $iSend -gt 0 -and $iGuard -lt $iSend)
$rvBody = $rvFn.Extent.Text
Assert-True "review: 抹后的文本**真的被用于发送**(`$prompt = `$rp['prompt'] 存在)" ($rvBody -match "\`$prompt = \`$rp\['prompt'\]")

# --- W4 裁定 B（2026-09-22）: 附件默认不出网 + 显式放行 ---
Assert-True "attach: 有附件 + 出网后端 + 未声明 => 拒" ((Get-AttachEgressReject -attachCount 1 -backendEgress $true -declared '') -eq 'attach-egress-unconfirmed')
Assert-True "attach: 有附件 + 出网后端 + 声明 ok => 放行" ((Get-AttachEgressReject -attachCount 1 -backendEgress $true -declared 'ok') -eq '')
Assert-True "attach: 声明的容忍(大小写/空白): 'YES'/' true ' 都放行, 'no' 仍拒" (
    (Get-AttachEgressReject -attachCount 1 -backendEgress $true -declared 'YES') -eq '' -and
    (Get-AttachEgressReject -attachCount 1 -backendEgress $true -declared ' true ') -eq '' -and
    (Get-AttachEgressReject -attachCount 1 -backendEgress $true -declared 'no') -ne '')
Assert-True "attach: 后端**不出网** => 放行(无需声明 —— 本条保证不误伤现存本地附件卡)" ((Get-AttachEgressReject -attachCount 1 -backendEgress $false -declared '') -eq '')
Assert-True "attach: **无附件** => 放行(与附件无关的卡不受影响)" ((Get-AttachEgressReject -attachCount 0 -backendEgress $true -declared '') -eq '')
$attCalls = ([regex]::Matches($cliText, 'Get-AttachEgressReject -attachCount')).Count
Assert-True "attach: 两个通道各判一次 = 2(实测 $attCalls)(opencode 通道 + claude 运行时通道)" ($attCalls -eq 2)
Assert-True "attach: 前端 schema 已加预置键 attach-egress" ($cliText -match "\`$h\['attach-egress'\] = ''")

# --- W3（2026-09-22）: claude 路站上变体 —— 步 1 的"一律拒绝"已由步 2"真的同步"取代 ---
# 背景: 站上变体在**站上**跑 claude（原先 `cd` 到 HOME），而附件只落主控本地 ⇒ 读不到 ⇒ "缺件跑完"= 假绿灯。
#   步 1 用 fail-closed 闸挡住；步 2 **把能力做出来**（站上建专用工作区 + 附件 scp 上去 + cwd 指过去），
#   并把"同步失败"做成 fail-closed ⇒ **安全性质不变**（绝不在缺件下跑完），但危险形态变成可用的能力。
# ⚠ 本块守住四条不变量（缺任一条，能力就会静默退化成"假绿灯"）:
#   ① 旧的"一律拒绝"闸**已撤**（不是被悄悄加回来，那会把能力重新关掉）
#   ② 站上 spawn **两处**都传 `-WorkDir`（少传一处 ⇒ 那条路径的 cwd 退回旧语义）
#   ③ 站上脚本**不再** cd 到 HOME，且工作区不可用时**退 8**（fail-closed）
#   ④ 附件上站任何一步失败 ⇒ **非零退出**（绝不静默继续）
$ccFn = @($fns) | Where-Object { $_.Name -eq 'Invoke-Task-Claude' } | Select-Object -First 1
Assert-True "w3: Invoke-Task-Claude 函数体可被 AST 定位" ([bool]$ccFn)
$w3OldGate = ([regex]::Matches($cliText, 'claude-station-attach-unsupported')).Count
Assert-True "w3: 旧的'站上+附件一律拒绝'闸**已撤**(实测 $w3OldGate 处)" ($w3OldGate -eq 0)
$w3WorkDirCalls = ([regex]::Matches($cliText, 'Invoke-ClaudeFly-Station -hostName .*-WorkDir \$stWorkDir')).Count
Assert-True "w3: 站上 spawn 两处都传 -WorkDir = 2(实测 $w3WorkDirCalls)" ($w3WorkDirCalls -eq 2)
# ⚠ **行首锚定**(`(?m)^cd ...`)，不是全文 `-match` —— 因为站上脚本是**here-string**(AST 看不进去),
#   只能文本判; 而全文匹配会被**注释**骗(本仓已踩过 4 次)。锚行首 = "这是一条真命令", 注释行以 `#` 开头。
Assert-True "w3: 站上脚本不再 cd 到 HOME(附件/项目相对路径就地可解析)" (-not ($cliText -match '(?m)^cd "\$HOME"'))
Assert-True "w3: 站上脚本对工作区不可用 **fail-closed**(退 8, 不在错的 cwd 下跑完)" ($cliText -match 'workdir 不可用')
$w3SyncFail = ([regex]::Matches($cliText, 'claude-station-attach-sync-failed')).Count
Assert-True "w3: 附件上站失败 => fail-closed(实测 $w3SyncFail 处; 非零退出, 绝不静默继续)" ($w3SyncFail -eq 1)
# 位置断言（**AST**，不是文本）: 附件上站必须**早于站上 spawn** —— 否则 agent 先跑、附件后到 = 缺件跑完
$ccCmds = @($ccFn.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] }, $true))
$w3Sync = @($ccCmds | Where-Object { $_.Extent.Text -match 'claude-ws-reset\.sh' }) | Select-Object -First 1
$w3Spawn = @($ccCmds | Where-Object { $_.GetCommandName() -eq 'Invoke-ClaudeFly-Station' }) | Select-Object -First 1
$iW3Sync = if ($w3Sync) { $w3Sync.Extent.StartOffset - $ccFn.Extent.StartOffset } else { -1 }
$iW3Spawn = if ($w3Spawn) { $w3Spawn.Extent.StartOffset - $ccFn.Extent.StartOffset } else { -1 }
Assert-True "w3: 位置断言(AST) —— 附件上站($iW3Sync) 早于 站上 spawn($iW3Spawn)" ($iW3Sync -gt 0 -and $iW3Spawn -gt 0 -and $iW3Sync -lt $iW3Spawn)
# 步 2b（2026-09-22）: **站上 claude 的项目工作区** —— 光有附件不够: 卡里"读 `src/x.py`"这类
#   **项目相对路径**若解析不到, **没有任何判据会因此报错** ⇒ 与"缺件却跑完"是同一族(假绿灯)。
#   做法 = **复用主路同一套** `Invoke-Workspace -act sync`，cwd 指向**项目工作区**。
#   ⚠ 刻意**不**自建 scratch: 两套工作区概念会让"附件/项目文件在哪儿"随路径而异 —— 而"同一件事
#   有两个定义点"正是本仓反复踩的坑。
$w3WsSync = ([regex]::Matches($cliText, "-act 'sync'")).Count
Assert-True "w3b: 两条路各同步一次项目工作区 = 2(实测 $w3WsSync) —— 站上支复用主路同一套" ($w3WsSync -eq 2)
Assert-True "w3b: 站上 cwd = **项目工作区**(不是自建 scratch)" ($cliText -match '\$stWorkDir = "\$Script:WORKSPACE_ROOT/\$proj"')
$w3Scratch = ([regex]::Matches($cliText, '_p3_claude_ws')).Count
Assert-True "w3b: 不存在'第二套工作区概念'(实测 $w3Scratch 处自建 scratch)" ($w3Scratch -eq 0)
$w3WsCmd = @($ccCmds | Where-Object { $_.GetCommandName() -eq 'Invoke-Workspace' }) | Select-Object -First 1
$iW3Ws = if ($w3WsCmd) { $w3WsCmd.Extent.StartOffset - $ccFn.Extent.StartOffset } else { -1 }
Assert-True "w3b: 位置断言(AST) —— 工作区同步($iW3Ws) 早于 站上 spawn($iW3Spawn)" ($iW3Ws -gt 0 -and $iW3Spawn -gt 0 -and $iW3Ws -lt $iW3Spawn)
# --- 台账/run.json 的 model 列 = **实际执行身份**（2026-09-22 续）---
# 病: 两处都写 `$id`（路由 id）。站上分支实际跑**站上本地引擎**（别名 main）⇒ 对一个 `local-only`
#   （"物理不出网"）的 run, **台账与 .agent-run.json 会报一个云端型号**（实测 run `202609221331304084`
#   写成 `thinkingmachines/inkling:free`）。而"按 model 列判该 run 是否出网"是个**看起来能用**的判据
#   ⇒ 会读出假警报（同族的反向错误会**掩盖真出网**）。
# 判据四条: ① 两件都写 `$execModel` ② 站上分支才有 `station:` 前缀 ③ `--model` 实参与执行身份串
#   用**同一个** `$stModelAlias`（防两处漂移）④ **反向**: 本地支仍写 `$id`（别把非站上分支也改坏）。
Assert-True "ledger: 台账行写 execModel(不是路由 id)" ($cliText -match '\$line = "\$ts,\$proj,\$execModel,')
Assert-True "run.json: model = execModel(不是路由 id)" ($cliText -match 'cli = ''claude''; model = \$execModel')
Assert-True "execModel: 站上分支带 station:<站>/<别名> 前缀" ($cliText -match '\$execModel = if \(\$useStation\) \{ "station:\$st/\$stModelAlias"')
# ⚠ 拼 needle 时用 `[char]39` 表示单引号 —— 少写一层 `\"`/`''` 转义（本行第一版就是被转义写坏的）。
$needleStAlias = '--model "' + [char]39 + ' + $stModelAlias'
$w3AliasCalls = ([regex]::Matches($cliText, [regex]::Escape($needleStAlias))).Count
Assert-True "execModel: `--model` 实参与执行身份串**同源**(`$stModelAlias`, 实测 $w3AliasCalls 处=站上首跑+resume)" ($w3AliasCalls -eq 2)
$needleLocalId = '--model "' + [char]39 + ' + $id'
$w3LocalModel = ([regex]::Matches($cliText, [regex]::Escape($needleLocalId))).Count
Assert-True "反向: 本地支仍用 \$id(实测 $w3LocalModel 处=本地首跑+resume) —— 别把非站上分支改坏" ($w3LocalModel -eq 2)

# --- W2（2026-09-22）: 进程退出码可信性 —— `exit $数组` 会把 rc 抹成 0 ---
# 实测（临时脚本直测进程 rc）: exit 4 ⇒ 4 / exit @($null,4) ⇒ **0** / exit @(0,4) ⇒ **0**
#   ⇒ 数组一律取不到真值。真例: `Invoke-Task` 内一处**裸调用** `Invoke-RemoteScript`
#   （返回 int rc、成功后=0，且**每次派发都跑**）⇒ `$code = @(0, <真 rc>)` ⇒
#   修前实测: 日志/台账写 `exit=6` 而**进程 rc=0**（**不带** AUTO_FALLBACK 的普通超时 run 同样如此，
#   即"失败被静默读成成功"）。探针 `_probe_fallback.ps1` 里有同名规则的 `Scalar`（取末元素），
#   所以探针一直没被骗到 —— 只有 CLI 的调用方被骗。
Assert-True "rc: 标量化 —— 单值原样透传 (4 => 4)" ((Resolve-ExitCode 4) -eq 4)
Assert-True "rc: 标量化 —— **本 bug 的确切形状** @(0,4) => 4(修前 exit @(0,4) 得 0)" ((Resolve-ExitCode @(0, 4)) -eq 4)
Assert-True "rc: 标量化 —— @(`$null,4) => 4(exit @(`$null,4) 实测得 0)" ((Resolve-ExitCode @($null, 4)) -eq 4)
Assert-True "rc: 标量化 —— 文本杂音 @('stray',4) => 4(exit 同样得 0)" ((Resolve-ExitCode @('stray', 4)) -eq 4)
Assert-True "rc: 标量化 —— 单元素数组 @(6) => 6(不退化为数组)" ((Resolve-ExitCode @(6)) -eq 6)
Assert-True "rc: 标量化 —— 返回类型是 Int32(不是数组/字符串)" ((Resolve-ExitCode @(0, 6)).GetType().Name -eq 'Int32')
# 末元素不可转 int ⇒ **抛错**(故意): 契约是"这些函数返回 int rc", 违契约要响, 不静默给 0
$rcThrew = $false
try { [void](Resolve-ExitCode @(0, 'not-a-code')) } catch { $rcThrew = $true }
Assert-True "rc: 末元素非数字 => 抛错(响, 而非静默 0)" $rcThrew
# 结构性: 出口**全部**走守卫(否则新增子命令又漏) ⇒ 计数断言(故意的摩擦)
$exitRaw = ([regex]::Matches($cliText, 'exit \$code')).Count
Assert-True "rc: 全仓不再有裸 exit `$code 写法(实测 $exitRaw 处 ⇒ 必须过标量化守卫)" ($exitRaw -eq 0)
$exitGuard = ([regex]::Matches($cliText, 'exit \(Resolve-ExitCode \$code\)')).Count
Assert-True "rc: exit (Resolve-ExitCode `$code) = 5(实测 $exitGuard) ⚠ 增删子命令须同步改本数" ($exitGuard -eq 5)
# ⚠ 用 **AST** 判"裸调用"(不是文本 —— 文本会被注释里的函数名骗, 本项目踩过):
#   裸调用 = 该命令是**单元素管道**且父节点是语句容器(既没被赋值、也没 `| Out-Null`)。
# ⚠⚠ **本判据第一版是假判(变异自证当场抓到, 2026-09-22)**: 只判了 `StatementBlockAst`,
#   而**函数体是 `NamedBlockAst`, 与 `StatementBlockAst` 是兄弟类(不是子类)**
#   ⇒ "直接写在函数体顶层的语句"**全被漏掉**。而本 bug 的那处裸调用(attach-reset)恰在
#   `Invoke-Task` 体**顶层** ⇒ 把 `| Out-Null` 删回去,**第一版判据照样 PASS**(假安全)。
#   ⇒ 两个容器类型都要收。**教训(与"位置断言被注释骗"同族): 结构判据必须先在"已知该红"的
#   变异上验红, 否则它只是"在跑", 不是在判。**
$bareRemote = @($ast.FindAll({ param($n)
            $n -is [System.Management.Automation.Language.PipelineAst] -and
            $n.PipelineElements.Count -eq 1 -and
            ($n.Parent -is [System.Management.Automation.Language.StatementBlockAst] -or
             $n.Parent -is [System.Management.Automation.Language.NamedBlockAst]) -and
            $n.PipelineElements[0] -is [System.Management.Automation.Language.CommandAst] -and
            $n.PipelineElements[0].GetCommandName() -eq 'Invoke-RemoteScript' }, $true))
Assert-True "rc: 全仓无**裸调用** Invoke-RemoteScript(返回 int rc ⇒ 裸调用必污染调用方 `$code)(实测 $($bareRemote.Count) 处)" ($bareRemote.Count -eq 0)

# --- 探针冒烟（2026-09-22）: 治"**守门人自己死了，而没有任何判据判它活着**" ---
# `_probe_fallback.ps1` 曾有一处**硬编码提取清单**的腐烂面（静默烂过一次，坏了 8 天没人知道）。
# **2026-09-22 已改为"提取全部 `FunctionDefinitionAst`、再覆盖 stub"** ⇒ 清单不再存在，
#   "漂移"这一失效模式**被构造性消除**；但它**换来一个新的失效模式**：**顺序**。
#   （stub 必须在提取之后定义才生效；若被挪到提取之前就会被真函数覆盖 ⇒ 探针可能**真的去 ssh**。）
# 探针自带 `-SmokeOnly` 静态自检，判两条：① `Invoke-Task`/`Invoke-Task-Claude` 存在；
#   ② **顺序不变量** —— 本文件每个 `function` 都晚于提取边界。
# ⇒ 本夹具**跑它一遍**，把"探针还活着"接到一个**有调用点的判据**上。
# ⚠ 两次变异自证都当场红：① （旧的清单形状）拿掉 `Get-BackendEgress` ⇒ 旧自检红；
#   ② （新的顺序形状）把一个 stub 放到提取边界**之前** ⇒ 自检红 + 本夹具红并点名。
$probePath = Join-Path (Split-Path $cli -Parent) '_probe_fallback.ps1'
$probeSmoke = @(); $probeSmokeRc = -1
try {
    $probeSmoke = @(& powershell -NoProfile -ExecutionPolicy Bypass -File $probePath -SmokeOnly 2>&1)
    $probeSmokeRc = $LASTEXITCODE
} catch { $probeSmoke = @($_.Exception.Message) }
Assert-True "probe: `-SmokeOnly` 通过(rc=0) —— 探针可驱动那条链、且 stub 未被提取覆盖(顺序不变量)" ($probeSmokeRc -eq 0)
if ($probeSmokeRc -ne 0) { Write-Host ('        smoke: ' + ((@($probeSmoke) | Select-Object -Last 3) -join ' / ')) }
else { Write-Host ('        smoke: ' + ((@($probeSmoke) | Where-Object { "$_" -match 'PROBE_SMOKE_OK' }) -join '')) }

# --- ssh/scp 调用纪律（2026-09-22 统一）: 每个调用点必须带 `-o BatchMode=yes` ---
# 为什么: 认证异常时（典型 = `~/.ssh/config` 缺身份块 ⇒ 用户名退化）OpenSSH 会**弹口令并阻塞等
#   stdin** ⇒ 自动化里表现为"卡住"（实测挂起 >90s）而不是"失败"。BatchMode 让它立刻失败。
# ⚠ 用 **AST** 取真实命令节点 —— 文本匹配会被注释骗（本文件顶部刚加的纪律注释里**就写着**
#   `ssh -o ConnectTimeout=10` 这个形状，用文本判必假红/假绿；同族教训本项目已踩 4 次）。
$sshCalls = @($ast.FindAll({ param($n)
            $n -is [System.Management.Automation.Language.CommandAst] -and
            @('ssh', 'scp') -contains $n.GetCommandName() }, $true))
$sshNoBatch = @($sshCalls | Where-Object {
            -not (@($_.CommandElements | ForEach-Object { $_.Extent.Text }) -match 'BatchMode=yes') })
Assert-True "ssh: 全部 ssh/scp 调用点带 `-o BatchMode=yes`（实测 $(@($sshCalls).Count) 处，缺 $(@($sshNoBatch).Count) 处）" (@($sshCalls).Count -gt 0 -and @($sshNoBatch).Count -eq 0)
if (@($sshNoBatch).Count -gt 0) {
    Write-Host ('        缺 BatchMode 的行: ' + ((@($sshNoBatch) | ForEach-Object { $_.Extent.StartLineNumber }) -join ', '))
}
# 同一条不变量**也套到另一个入口** `_switch_qwen_flavor.ps1`（2026-09-22）：该件原为**半修** ——
#   3 处 ssh 带了 BatchMode、2 处 scp 没带（"只修一半的修复看起来是完整的"，本仓已记过同族）。
#   ⚠ 要求 ≥5 是**防恒真**的下界：若哪天解析失败/文件改名导致 0 处命中，必须红，不能静默通过
#   （"0 覆盖与 100% 通过不可区分"是本仓的既有教训）。
$switchPs1 = Join-Path (Split-Path $cli -Parent) '_switch_qwen_flavor.ps1'
$swT = $null; $swErr = $null
$swAst = [System.Management.Automation.Language.Parser]::ParseInput(
    [System.IO.File]::ReadAllText($switchPs1, [System.Text.UTF8Encoding]::new($false)), [ref]$swT, [ref]$swErr)
$swCalls = @($swAst.FindAll({ param($n)
            $n -is [System.Management.Automation.Language.CommandAst] -and
            @('ssh', 'scp') -contains $n.GetCommandName() }, $true))
$swBad = @($swCalls | Where-Object {
            -not (@($_.CommandElements | ForEach-Object { $_.Extent.Text }) -match 'BatchMode=yes') })
Assert-True "ssh: _switch_qwen_flavor.ps1 的全部 ssh/scp 也带 BatchMode（实测 $(@($swCalls).Count) 处，缺 $(@($swBad).Count) 处；解析错 $(@($swErr).Count)）" (@($swCalls).Count -ge 5 -and @($swBad).Count -eq 0 -and @($swErr).Count -eq 0)

# --- .sh 侧（2026-09-22）：**没有可用 AST** ⇒ 只能文本扫描兜底（边界显式声明）---
# 为什么还是要做: `agent-cli-smoke.sh` 有 **12 处**裸调用（其中 7 处 heredoc 形态**连 `-o` 都没有**），
#   而该文件是**升级窗口回归三件套**之一 ⇒ 不能只修不加守卫（"修完就漂"是本仓的常态）。
# ⚠ 边界（诚实声明）: 文本判据会被注释/字符串骗（本项目已踩 5 次）。本扫描靠三条压假阳：
#   ① 只取 `#` 之前的代码段；② 命中点**引号奇偶**判是否在串内；③ 逐文件要求**命中数恰为登记值**。
#   已知残留边界: **跨行字符串**（如 docstring）判不出；`.sh` 里没有 Python AST 可用。
$shScan = @'
import re, sys
CALL = re.compile(r"(?<![\w.\-])(?:&\s*)?(ssh|scp)\s")

def in_quote(s, pos):
    return s[:pos].count('"') % 2 == 1 or s[:pos].count("'") % 2 == 1

for f in sys.argv[1:]:
    bare, total = [], 0
    for i, ln in enumerate(open(f, encoding="utf-8", errors="replace").read().splitlines(), 1):
        code = ln.split("#", 1)[0]
        if not code.strip():
            continue
        for m in CALL.finditer(code):
            if in_quote(code, m.start()):
                continue
            total += 1
            if "BatchMode" not in code:
                bare.append(i)
            break
    print("{} bare={} total={}".format(f.replace("\\", "/").rsplit("/", 1)[-1], len(bare), total))
'@
$shScanFiles = @(
    (Join-Path (Split-Path $cli -Parent) 'agent-cli-smoke.sh'),
    (Join-Path (Split-Path $cli -Parent) 'load-gate'))
$shRes = 'PYERR: not run'
try {
    $shRes = (@(@($shScan | python - @shScanFiles 2>&1) | Where-Object { "$_" -match 'bare=' }) -join ' | ')
} catch { $shRes = "PYERR: $($_.Exception.Message)" }
# ⚠ 逐文件登记值是**防恒真**的下界（0 命中必须红）：⚠ 增删调用须同步改本数（故意的摩擦）
Assert-True "ssh: .sh 侧无裸调用（文本扫描兜底，实测 $shRes）" ($shRes -eq 'agent-cli-smoke.sh bare=0 total=12 | load-gate bare=0 total=4')
# `Test-StationEngineReady` 的 scp 走 `Start-Process -FilePath 'scp' -ArgumentList $scpArgs`
# ⇒ 没有 scp 的 CommandAst 节点，**真实选项在 `$scpArgs` 那个赋值里**。
# ⚠ 第一版我把断言打在 Start-Process 的 `Extent.Text` 上 ⇒ 那串文本里只有 `$scpArgs`（变量名），
#   必红。判据要打**真值所在的那一行**（赋值语句），否则"判了但不是你以为的东西"。
$spScp = @($ast.FindAll({ param($n)
            $n -is [System.Management.Automation.Language.CommandAst] -and
            $n.GetCommandName() -eq 'Start-Process' -and $n.Extent.Text -match "FilePath 'scp'" }, $true))
$spArgs = @($ast.FindAll({ param($n)
            $n -is [System.Management.Automation.Language.AssignmentStatementAst] -and
            $n.Left.Extent.Text -eq '$scpArgs' }, $true))
Assert-True "ssh: Start-Process 形式的 scp 也带 BatchMode（调用 $(@($spScp).Count) 处 / `$scpArgs 赋值 $(@($spArgs).Count) 处）" (@($spScp).Count -gt 0 -and @($spArgs).Count -eq 1 -and $spArgs[0].Extent.Text -match 'BatchMode=yes')

# --- cluster_ssh.py（paramiko 侧）: 建连走**唯一入口** `_connect` 且三个超时全显式 ---
# 2026-09-25 (D6-P3-2 接线): 扫描目标 `cluster.py` → **`cluster_ssh.py`**。
#   为什么: `cluster.py` 模块化重构把 paramiko 建连**下沉**到 `cluster_ssh.py` ⇒ 旧目标上恒得
#   `SSHClient=0 connect=0` ⇒ 两条断言恒失败。⚠ 而本夹具此前**不在门禁里** ⇒ 该失败**静静积累了多轮**
#   （正是"有测试但没人跑"的腐化）。这是本轮把它接进 CHECKS 的**直接收益**。
# paramiko 无 BatchMode（它不弹口令、认证失败是抛异常）⇒ 这一侧的对应物是"把卡住的上界压到 SSH_TIMEOUT"。
# ⚠ 上游事实（paramiko 5.0.0 **实测源码**，非推测）: `self.banner_timeout = 15` / `self.auth_timeout = 30`
#   ⇒ 两者**不同源**，只给 banner_timeout 的话认证阶段仍会等 30s。
# ⚠⚠ 这里**必须用 Python 的 AST**，不能用文本判：第一版我用
#   `[regex]::Matches($text, 'paramiko\.SSHClient\(\)')` 数出 **2 处**，其中一处是 `_connect` 的
#   **docstring 里提到这个名字** —— 正是"文本判据被注释骗"（本项目第 5 次）。改用 `ast` 数**真实调用节点**。
$clusterPy = Join-Path (Split-Path (Split-Path $cli -Parent) -Parent) 'cluster_ssh.py'
$pyProbe = @'
import ast, sys
tree = ast.parse(open(sys.argv[1], encoding="utf-8").read())
calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
newc = [c for c in calls if isinstance(c.func, ast.Attribute) and c.func.attr == "SSHClient"]
conn = [c for c in calls if isinstance(c.func, ast.Attribute) and c.func.attr == "connect"]
kw = sorted({k.arg for c in conn for k in c.keywords})
print("SSHClient={} connect={} kwargs={}".format(len(newc), len(conn), ",".join(kw)))
'@
$pyRes = 'PYERR: not run'
try { $pyRes = (@($pyProbe | python - $clusterPy 2>&1) | Select-Object -Last 1) } catch { $pyRes = "PYERR: $($_.Exception.Message)" }
Assert-True "ssh: cluster_ssh.py 建连只有唯一入口（AST: SSHClient 调用=1, connect 调用=1）—— 实测 $pyRes" ($pyRes -match '^SSHClient=1 connect=1 ')
Assert-True "ssh: cluster_ssh.py 的 connect 三超时全显式（否则 auth 默认 30s）—— 实测 $pyRes" ($pyRes -match 'kwargs=auth_timeout,banner_timeout,timeout')

# O-42 (2026-09-24): claude 通道 `-p` 的权限开关 —— 正反注入(AST/文本级, 不真派发)。
#   反(必拒形态): `readonly: true` 的卡若竟带 acceptEdits ⇒ 破卡面契约(= D-06/D-07 级安全面)。
#   $pmDef 逐字匹配「if(readonly)空串 else acceptEdits」的定义行, 正反两端同时钉死。
$o42J = ([regex]::Matches($content, '\+ \$pmArg\)')).Count
Assert-True 'o42: 四处 claude argStr 拼接均带 $pmArg(站上/本地 × 首跑/resume=4)' ($o42J -eq 4)
$o42Def = "    `$pmArg = if (`$readonly) { '' } else { ' --permission-mode acceptEdits' }"
Assert-True 'o42: $pmArg 定义受 readonly 分支控制(readonly=false 才 acceptEdits, true 空串保只读)' ($content.Contains($o42Def))

# --- O-57-A (2026-09-25): 站上证据暂存件 —— 派发前清理, 且清单**只有一份** ---
# 根因(实测 2026-09-25): `out/` 是累计的 + 固定名拉回**无 run 窗口** ⇒ 上一次 run 的
#   `.accept-cmds.txt` 被当**本次**证据归档(4 个 proj 根 83 个 run 里 **12 条**)。
#   原 reset **只在失败路径**(`O46_CLEAN`) ⇒ 成功路径不清。修法 = 把清提前到**派发前**,
#   与既有的 `.attach/` 无条件 reset **同段**(那也是它的既有纪律)。
# ★ 2026-09-25 (O-68/D1) **就地更正本段**: 真值由"名字数组"升级为"名字 + pull 表"
#   ⇒ 原断言钉的 `$Script:EV_STAGE_NAMES = @(` **字面量已不存在**(清单改为从表**派生**)。
#   **方向是改写断言、不是回退代码** —— 这正是 O-65 的教训(改实现必须同步改断言)。
$evTbl = ([regex]::Matches($content, '\$Script:EV_FILES = @\(')).Count
Assert-True "o57: 暂存件真值**只定义一处**(禁第二份枚举 —— 本仓头号失败形态)" ($evTbl -eq 1)
$evAll = @('.meta', '.prompt.txt', '.progress', '.accept-cmds.txt', '.golden-cmd.txt',
           '.workspace-diff.txt', '.attach-manifest.txt', '.session-meta.txt',
           '.agent-output.txt', '.accept-output.txt', '.accept-golden-output.txt')
$evMiss = @($evAll | Where-Object { -not $content.Contains("name = '$_'") })
Assert-True "o57: 真值表含全部 **11** 个暂存件(逐名核对; 缺: $($evMiss -join ', '))" ($evMiss.Count -eq 0)
Assert-True "o57: 合批清单**从真值表派生**(不手写第二份枚举)" (
    $content.Contains('$Script:EV_FILES | Where-Object { $_.pull -eq ''batch'' }'))
Assert-True "o57: per-run **后缀**的构造规则**只定义一处**(唯一命名规则)" (
    ([regex]::Matches($content, 'function Get-EvSuffix\(')).Count -eq 1)
Assert-True "o57: 后缀分隔符**只有一处定义**(`Script:EV_SUFFIX_SEP" (
    ([regex]::Matches($content, '\$Script:EV_SUFFIX_SEP = ')).Count -eq 1)
Assert-True "o57: 清理命令由该**唯一真值派生**(不是手写 8 条 rm)" (
    $content.Contains('$Script:EV_FILES | ForEach-Object {'))
# ★★ O-68/D2-D3 (2026-09-25) —— 本批**只落 D1 + D3**，**D2 与 D4 同批**（见下）。
#   为什么 D2 必须等 D4: 移除 O-57-A 的 reset 而**尚未** per-run 改名 ⇒ 裸名仍被 collect 读 ⇒
#     **等于把 O-57 放回"修前"状态**（上一次 run 的残留被当本次证据）⇒ 两件**互为前提**。
#   ⇒ 断言按**当前真实状态**钉住三件事（这比"假装已完成"有用）:
#     ① GC **存在**且**只按龄**（`-mtime +7 -delete`）—— 即"不可能误删活件"这个**语义**；
#     ② O-57-A 的 reset **仍在**（过渡态，不是遗漏）；
#     ③ 源码里**写明了"D2 尚未落地"及其理由** —— 防未来有人"顺手"删掉 reset 却没做 D4。
Assert-True "o68: 派发前**有按龄 GC**(只删 >7 天死件 ⇒ 不可能误删活件)" (
    $content.Contains('$evGcCmd') -and $content.Contains('-mtime +7 -delete'))
Assert-True "o68: ★ GC 的**裕度理由**写在源码里(7天 vs 最长 timeout_s=1800s ⇒ 300×)" (
    $content.Contains('1800') -and $content.Contains('300'))
# ⚠ O-73 (2026-09-25) **就地修判据**: 下面这条原用**全文子串**判"已无该变量" ⇒ 而 O-73 的修复注释里
#   为说明"与 D2 移除的那处同类"**提到了这个变量名** ⇒ 判据**假红**。
#   ⇒ 与 O-65 那次"全文子串 ⇒ 可被注释蒙过"是**同一个坑的两个方向**（那次是假绿, 这次是假红）:
#     判据必须**只看代码**。此处就地做代码/注释分离（去 `#` 之后的部分）。
$codeOnlyFull = (($content -split "`n") | ForEach-Object { $_ -replace '#.*$', '' }) -join "`n"
Assert-True "o68: ★★ **已无**'无条件删固定名'(D2 落地 = O-68 修法的**前提条件**; 只看代码)" (
    -not $codeOnlyFull.Contains('$evRmCmd'))
Assert-True "o68: ★ 源码**写明**'不要把它加回来'的理由(防有人手滑复原 reset)" (
    $content.Contains('不要加回来'))
Assert-True "o57: 清理段已接进**派发前**那个 body(与附件中转同段)" (
    $content.Contains('$evGcCmd') -and $content.Contains('rm -rf "`$STAGE" && mkdir -p "`$STAGE/attach"'))

# --- ★★ O-68/D4-D6 (2026-09-25): per-run 命名 —— 站上 10 件 + 主控 3 处 + helper 1 处 ---
Assert-True "o68: 站上后缀变量与主控**同源**(body 内 `EV_SUF=` + PS 变量 `evSuf)" (
    $content.Contains('EV_SUF="$evSuf"'))
$iSufDef = $content.IndexOf('EV_SUF="$evSuf"')
# ⚠ 参考点**不能**取 golden 段: 它的**字符串定义**在 `EV_SUF=` **之前**, 而它的**插值点**在**之后**
#   ⇒ 文本位置只能拿"body 内自己的写点"当参考（这里取 `.prompt.txt`, 在 body 主段内）。
$iFirstEv = $content.IndexOf('$W/out/.prompt.txt`$EV_SUF')
Assert-True "o68: ★ 后缀定义**早于** body 内第一个写点(位置不变量)" (
    $iSufDef -gt 0 -and $iFirstEv -gt $iSufDef)
# golden 段另判**插值点**（它自己也写两件 ⇒ 必须晚于后缀定义, 否则那两件会落成裸名）
$iGoldenUse = $content.IndexOf("`n`$goldenBlock`n")
Assert-True "o68: ★ golden 段的**插值点**晚于后缀定义(故它那两件也带后缀)" (
    $iGoldenUse -gt $iSufDef)
# ★★ 最强的那条: **10 个 body 内基名的写点全部带后缀**, 且**裸名残留必须为 0**
$evBases = @('.meta', '.prompt.txt', '.progress', '.accept-cmds.txt', '.golden-cmd.txt',
             '.workspace-diff.txt', '.attach-manifest.txt',
             '.agent-output.txt', '.accept-output.txt', '.accept-golden-output.txt')
$evBare = @($evBases | Where-Object { $content.Contains('$W/out/' + $_ + '"') })
Assert-True "o68: ★★ 站上写点**无裸名残留**(逐个核对; 残留: $($evBare -join ', '))" ($evBare.Count -eq 0)
$evNoSuf = @($evBases | Where-Object { -not $content.Contains('$W/out/' + $_ + '`$EV_SUF') })
Assert-True "o68: ★★ 10 个基名**逐个**都插了后缀(缺: $($evNoSuf -join ', '))" ($evNoSuf.Count -eq 0)
Assert-True "o68: 主控侧三处用 **PS 变量 `evSuf`**(不是站上那个 bash 变量 ⇒ 语法域不同)" (
    ([regex]::Matches($content, '\$W/out/\.(agent-output|accept-output|accept-golden-output)\.txt\$evSuf')).Count -ge 3)
Assert-True "o68: 会话遥测 helper 的目标路径也带后缀(它**不走** body ⇒ 单独一处)" (
    $content.Contains(".session-meta.txt`$evSuf'"))
Assert-True "o68: 合批的远端路径带后缀, 但 **marker 仍发基名**(归档映射靠基名)" (
    $content.Contains('$W/out/$($_)$evSuf') -and $content.Contains('echo FILE:$_'))
# ⚠ 2026-09-25 (T1) **就地更正本条**: 原断言要求"派发前 body 里也有 `.attach` 的 reset" ——
#   T1 之后那条**已移进锁内落盘段**(理由见 DEV-LOG §27.11-A), 故此处改为只认"中转目录"。
#   若有人把 `.attach` 的重置搬回派发前, 由下面 t1 段的**位置断言**兜住。
Assert-True "o57: collect 的拉回清单**改为引用**同一真值(不再手写字面量)" (
    $content.Contains('$evNames = $Script:EV_STAGE_NAMES'))
# 位置不变量: 清理段必须**早于**主 run body 对 `out/` 的写入(否则会删掉本次自己刚写的件)。
$iGc = $content.IndexOf('$evGcCmd')
$iProg = $content.IndexOf('out/.progress')
Assert-True "o57: 清理段**早于** out/ 任何写入(位置不变量)" (
    $iGc -gt 0 -and $iProg -gt $iGc)

# --- ★★ O-71 (2026-09-25): 环境层 `Remove-Item` 包装器吐 `$null` ⇒ 把**函数返回值**污染成数组 ---
# 一手复现(最小, 已写进 DEV-LOG §38): 本机 profile 把 `Remove-Item` 别名到 `__Safe-Remove-Item-Wrapper`,
#   该包装器**每次调用都往管道吐 1 个 `$null`**（同一命令、同一文件的两个计数: 包装器 = 1,
#   原生 `Microsoft.PowerShell.Management\Remove-Item` = 0）。
# 症状链(实测): `Get-UniqueRunStamp` 的**抢占 GC 一执行** ⇒ 它返回 `@($null, <ts>)` ⇒ 调用方 `$ts` 变**数组**
#   ⇒ `"agent-cli-task-$ts.sh"` 里多一个空格 ⇒ 远端 `bash: /tmp/agent-cli-task-: 没有那个文件或目录`
#   ⇒ **exit 255**（报错点离病因很远 ⇒ 曾被误判为"网络/站上问题"）。
# ⇒ 判据取**全文件级**（不逐函数写），防"下次换个函数再漏一遍"。
$rmBad = @()
$rmNo = 0
foreach ($ln in ($content -split "`n")) {
    $rmNo++
    # ⚠ 归一化两步都**必需**: ① 去注释(`#` 之后非代码) ② 剥单/双引号内文本。
    #   漏掉 ② 会**恒红** —— 本段自己的 ABORT 消息串里就含 `Remove-Item` 这个词（实测）;
    #   而"用全文子串判"正是 O-65 那次假绿的同一个坑（该判据必须只看代码）。
    $cOnly = $ln -replace '#.*$', ''
    $cOnly = $cOnly -replace "'[^']*'", 'Q'
    $cOnly = $cOnly -replace '"[^"]*"', 'Q'
    $nRm = ([regex]::Matches($cOnly, 'Remove-Item')).Count
    if ($nRm -gt 0) {
        $nOut = ([regex]::Matches($cOnly, '\| Out-Null')).Count
        if ($nOut -lt $nRm) { $rmBad += "L$rmNo($nRm/$nOut)" }
    }
}
Assert-True "o71①: 代码行里**每个** Remove-Item 都 `| Out-Null`(违规: $($rmBad -join ', '))" (
    $rmBad.Count -eq 0)
Assert-True "o71②: `Get-UniqueRunStamp` 尾注**写明**根因与包装器名(防有人把它当噪声删掉)" (
    $content.Contains('本函数**返回一个 18 位字符串**') -and
    $content.Contains('__Safe-Remove-Item-Wrapper'))
Assert-True "o71③: `$ts` 消费点有**形状 fail-closed**(数组 ⇒ exit 13; 绝不静默取一个元素接着跑)" (
    $content.Contains('if ($ts -is [array]) { Write-Host "ABORT: ts 形状异常'))

# --- O-73 (2026-09-25): 失败路径清理的**射程收窄**（`rm` 掉 `.agent-lock` = unlink ⇒ 并发持锁者被静默降级） ---
# 为什么这条是 P1: `flock` 的互斥**绑在 inode 上**; `rm` 只 unlink 目录项 ⇒ 并存的持有者仍锁着**旧** inode,
#   后来者却能在**新** inode 上取到 "exclusive" ⇒ 与仍然活着的 shared 持有者并存 = rwlock 语义被破。
# 旁证(一手): O-72 抓到的孤儿 `fd 9 = .agent-lock (deleted)` —— "持锁者存在而锁文件已被 unlink" 真实发生过。
# 另一半: `out/.meta` / `out/.progress` 在 D4(per-run 命名)后**已不是本 run 的件** ⇒ 去删它们 = 删别人的件,
#   与 D2 刚移除的 `$evRmCmd` **完全同类**。⇒ 两项都去掉, **只留 subject-state**（卡的产物不是 per-run 命名的）。
Assert-True "o73①: 失败清理**不再预置**固定名(旧四项 `out/.meta`+`out/.progress`+lock+state 已删)" (
    $content.Contains('$del = @()') -and
    -not $content.Contains("'out/.meta','out/.progress'") -and
    -not $content.Contains("'.agent-lock','.agent-state.json'"))
Assert-True "o73②: 声明产物(subject state)仍被清 —— 收窄没有把它一起关掉" (
    $content.Contains('$del += $st'))
Assert-True "o73③: 射程打成**可观测行**(`O46_CLEAN_SCOPE:`) —— 否则『刻意不清』与『没清』长得一样" (
    $content.Contains('O46_CLEAN_SCOPE: 按 O-73 刻意**不删**'))

# --- O-75 (2026-09-25): 探针 ssh 必须有**整体墙钟**（`ConnectTimeout` 只管 TCP connect, 不管名字解析） ---
# 一手实测: 六并发时 A/B 两站(`.local` ⇒ mDNS)的 `ssh … 'echo alive'` 各**挂约 10 分钟**;
#   杀掉那两条探头 ⇒ 两条 run 立刻继续并 `exit=0` ⇒ 卡点只在探头。正反两侧已在本机验过
#   (远端 `sleep 60` + 3s 上限 ⇒ `code=124 / 耗时 3s`; `echo alive` ⇒ `ok=True`)。
Assert-True "o75①: 有**有墙钟的探针执行器**(常量 + WaitForExit(ms) + 超时 Kill + 124 码)" (
    $content.Contains('$Script:SSH_PROBE_CAP_S = 45') -and
    $content.Contains('if (-not $p.WaitForExit($TimeoutS * 1000))') -and
    $content.Contains('try { $p.Kill() } catch { }') -and
    $content.Contains('return @{ ok = $false; code = 124;'))
# ⚠ 结构性保证: BatchMode 由 helper **强制**加 —— 那条"全部 ssh 调用点必带 BatchMode"的夹具是 **AST 级**
#   的, 扫不到 `$psi.Arguments` 这个字符串 ⇒ 靠调用方自觉就会**静默**跳出护栏。
Assert-True "o75②: `-o BatchMode=yes` 由该 helper **强制**加(不靠调用方自觉, 见 o75 注释)" (
    $content.Contains('-o BatchMode=yes " + $Arguments'))
Assert-True "o75③: `Test-RemoteReach` 改走该 helper(它是四条主路 ssh 入口的共同前置闸)" (
    $content.Contains('$r = Invoke-CappedSsh -Arguments "-o ConnectTimeout=8 $hostName') -and
    -not $content.Contains('ssh -o ConnectTimeout=8 -o BatchMode=yes $hostName'))
# ⚠ **诚实边界**: 派发主体**刻意不加**主控侧墙钟(强杀 ssh 会让远端任务继续跑而证据全丢) ⇒ 源码必须写明,
#   否则后来者会"顺手全加"并把那条纪律变成假全覆盖。
Assert-True "o75④: 源码写明『派发主体刻意不加墙钟』及其理由(防顺手全加 ⇒ 假全覆盖)" (
    $content.Contains('刻意不加') -and $content.Contains('远端任务还在跑 + 本地证据全丢'))

# --- O-72 (2026-09-25): 采样器子壳**必须能自停** + 站上脚本副本**有出口** ---
# 一手取证: B 站抓到一条**活了 28.6h** 的孤儿 `bash /tmp/agent-cli-task-*.sh`(PPID=1, 继承锁 fd),
#   每 5s 往裸名 `.progress` 追写(kill 前持续增长 / kill 后立刻冻结) ⇒ 它就是那个写者。
#   机制: `sample_progress &` 是**子壳**, 父壳末尾 `SAMPLE=f` 到不了它 ⇒ 只能靠 `kill $SPID`。
Assert-True "o72①: 采样器**自带上限**且有 `break` 自停(SIGKILL 下陷阱不触发 ⇒ 这是最后一道防线)" (
    $content.Contains('SAMPLE_MAX_S=`$(( $timeout * 4 + 600 ))') -and
    $content.Contains('[ `$(( SAMPLE_N * 5 )) -ge `$SAMPLE_MAX_S ] && break'))
$iSampler = $content.IndexOf('sample_progress() {')
$iBreak = $content.IndexOf('SAMPLE_N * 5', $iSampler)
$iSleep = $content.IndexOf('sleep 5', $iSampler)
Assert-True "o72①b: `break` 在采样循环的 `sleep 5` **之前**(位置不变量)" (
    $iSampler -gt 0 -and $iBreak -gt $iSampler -and $iSleep -gt $iSampler -and $iBreak -lt $iSleep)
Assert-True "o72②: 有 `HUP/TERM/EXIT` 陷阱兜底杀子壳, 且陷阱体**始终 return 0**(rc 是契约字段)" (
    $content.Contains('trap cleanup_sampler HUP TERM EXIT') -and
    $content.Contains('kill "`$SPID" 2>/dev/null || true') -and
    $content.Contains('return 0'))
Assert-True "o72③: 站上脚本副本 `/tmp/agent-cli-task-*.sh` **按龄清**(无出口 ⇒ 腐化; 实测 B 站 101 个)" (
    $content.Contains("find /tmp -maxdepth 1 -name 'agent-cli-task-*.sh' -mtime +7 -delete"))
# ⚠ 这条是**防倒退**的: T1 那两个中转脚本用 `trap 'rm -f "$0"'` 自删(因为它们**不**走重试链),
#   而主 body **走** `Invoke-RemoteScript` 的网络重试(同一路径再 bash 一次) ⇒ 自删会把"成功"判成 127。
Assert-True "o72④: 源码写明【为什么主 body 不自删】(防后来者照抄 T1 的 trap 自删)" (
    $content.Contains('把成功判成失败') -and $content.Contains('再 `bash` 一次'))
# ★★ o72⑤/⑥ = **行为测试**（离线, 用本地 Git Bash 跑**同一段结构**）——
#   为什么非有不可: 静态断言只验"那行文本在"。而**首跑(2026-09-26)实测**抓到的缺陷恰恰是
#   "文本在、但**跑不起来**": `[ $(( n * 5 )) -ge SAMPLE_MAX_S ]` 少了 `$` ⇒ `[: SAMPLE_MAX_S: 需要整数表达式`
#   ⇒ 整个 run `exit=255`。⇒ 正是 DEV-LOG §26.4「夹具查'串在不', 查不出'这条链现在跑不跑得起来'」。
#   (`$lb` = 上面 O-15 段已解析出的本地 Git Bash; 跑命令用 `Invoke-LocalBashCmd` ——
#    它把 stdout+stderr 落日志并只回 rc ⇒ **不会**因 bash 往 stderr 写字而触发 PS 的 NativeCommandError,
#    这正是本次第一版踩的坑: 直接 `2>&1` 捕获负例 ⇒ 夹具自己中断(exit 1)而不是报 FAIL)。
$logLoop = Join-Path $env:TEMP 'fm_o72_loop.log'
$logPos = Join-Path $env:TEMP 'fm_o72_pos.log'
$logNeg = Join-Path $env:TEMP 'fm_o72_neg.log'
foreach ($f in @($logLoop, $logPos, $logNeg)) { Remove-Item $f -ErrorAction SilentlyContinue }
$rcLoop = Invoke-LocalBashCmd -bashPath $lb -cwd $env:TEMP -logFile $logLoop -cmd 'SAMPLE_MAX_S=12; SAMPLE_N=0; while [ 1 = 1 ]; do SAMPLE_N=$(( SAMPLE_N + 1 )); [ $(( SAMPLE_N * 5 )) -ge $SAMPLE_MAX_S ] && break; sleep 0; done; echo "STOPPED_N=$SAMPLE_N"'
$rcPos = Invoke-LocalBashCmd -bashPath $lb -cwd $env:TEMP -logFile $logPos -cmd 'SAMPLE_N=3; SAMPLE_MAX_S=12; [ $(( SAMPLE_N * 5 )) -ge $SAMPLE_MAX_S ] && echo CMP_OK'
$rcNeg = Invoke-LocalBashCmd -bashPath $lb -cwd $env:TEMP -logFile $logNeg -cmd 'SAMPLE_N=3; SAMPLE_MAX_S=12; [ $(( SAMPLE_N * 5 )) -ge SAMPLE_MAX_S ] && echo CMP_OK'
$outLoop = "$(Get-Content $logLoop -Raw -ErrorAction SilentlyContinue)"
$outPos = "$(Get-Content $logPos -Raw -ErrorAction SilentlyContinue)"
$outNeg = "$(Get-Content $logNeg -Raw -ErrorAction SilentlyContinue)"
Assert-True "o72⑤(行为): 采样循环**真能自停**(上限 12s ⇒ n=3 即 break; 不是'文本在就算过')" (
    $rcLoop -eq 0 -and $outLoop -match 'STOPPED_N=3')
Assert-True "o72⑥(行为·先验红): 带 `$` ⇒ 比较成立; **裸名** ⇒ `[` 报错、打不出 CMP_OK" (
    $rcPos -eq 0 -and $outPos -match 'CMP_OK' -and -not $outNeg.Contains('CMP_OK'))
foreach ($f in @($logLoop, $logPos, $logNeg)) { Remove-Item $f -ErrorAction SilentlyContinue }

# --- O-56 (2026-09-25): 基线"**声明无条件 / 产出有条件**"(两处) ---
# ① 主路: `accept-cmds` 原为**裸列**, 而站上只在 `[ -n "$ACCEPT_B64" ]` 时才写 ⇒ 无 accept 的卡
#    每个 run 假报一条 missing-artifact gap。⇒ 与 `accept-output` **同条件列**(= O-29 对 golden-cmd 的同法)。
$iFn = $content.IndexOf('function Get-FrameworkSubjects')
$iList = $content.IndexOf('$list = @(', $iFn)
$iHasAcc = $content.IndexOf('if ($hasAccept) {', $iList)
$segBase = if ($iList -gt 0 -and $iHasAcc -gt $iList) { $content.Substring($iList, $iHasAcc - $iList) } else { '' }
# ⚠ needle 必须用**键值形态** `name = 'accept-cmds'`，不能用裸词 —— 该段里有说明注释也含这个词
#   (夹具自身踩过: 第一版用裸词 ⇒ 恒红)。
Assert-True "o56①: 主路基线**不再裸列** accept-cmds(无 accept 的卡永不产出该件)" (
    $iFn -gt 0 -and $iList -gt $iFn -and $iHasAcc -gt $iList -and -not ($segBase -match "name = 'accept-cmds'"))
Assert-True "o56①: accept-cmds 已与 accept-output **一起**条件列" (
    $iHasAcc -gt 0 -and ($content.Substring($iHasAcc, 400) -match "name = 'accept-cmds'"))
# ② 备路: `stderr` 在基线里**无条件声明** ⇒ 归档侧**必须**保证产出(缺件则补空件),
#    **不改成条件声明** —— 失败路径的 stderr 恰是最该留的证据。
Assert-True "o56②: 备路基线仍**无条件声明** stderr(未被改成条件声明)" (
    $content.Contains("@{ name = 'stderr';"))
Assert-True "o56②: 备路归档侧补空件(声明无条件 ⇒ 产出也必须无条件)" (
    $content.Contains('if (-not (Test-Path $errTxt))'))

# --- O-59 / T1 (2026-09-25): staging 进锁 + **危险面 ⇒ 排他**（一对，缺一不可） ---
# 先验红(实测, DEV-LOG §27.11-G): 两跑各带 1 件却都 `ATTACH_MANIFEST_LINES=2`、agent 都列出对方的件。
# 本段钉四件事: ① 危险面判据 ② 锁模式公式 ③ `.attach` 的重置**只在锁内** ④ 落盘段早于 manifest 采样。
Assert-True "t1①: 危险面判据 = 有附件 ∨ golden active(**单一来源** `$leaseX`, O-62/C1 上移)" (
    $content.Contains('$leaseX = (($attach.Count -gt 0) -or $goldenActive)') -and
    $content.Contains('$dangerFace = $leaseX'))
Assert-True "t1②: 锁模式 = `readonly ∧ ¬危险面` 才 shared(否则 exclusive)" (
    $content.Contains('$flockShared = if ($readonly -and -not $dangerFace) { ''1'' } else { ''0'' }'))
$iLockAcq = $content.IndexOf('LOCK_ACQUIRED pid=')
$iAttachReset = $content.IndexOf('rm -rf "`$W/.attach" && mkdir -p "`$W/.attach"')
Assert-True "t1③: `.attach` 的重置**出现在 LOCK_ACQUIRED 之后**(⇒ 只在锁内)" (
    $iLockAcq -gt 0 -and $iAttachReset -gt $iLockAcq)
Assert-True "t1④: 落盘段早于 `.attach-manifest` 采样(manifest 记的是注入的字节)" (
    $content.IndexOf('ATTACH_STAGED=') -gt 0 -and
    $content.IndexOf('ATTACH_STAGED=') -lt $content.IndexOf('out/.attach-manifest.txt'))
# console 侧**不得**再碰共享面: 附件 scp 目标与 golden 中转都必须落在 `$stage`
Assert-True "t1⑤: 附件 scp 落点 = 私有中转(不是 `$W`)" (
    -not $content.Contains('${hostName}:$Script:WORKSPACE_ROOT/$proj/.attach/') -and
    $content.Contains('${hostName}:$stage/attach/'))
Assert-True "t1⑥: golden 只传中转(`$stage/golden.tgz`), 旧的 `$goldenInject` 已删" (
    $content.Contains('${hostName}:$stage/golden.tgz') -and
    -not $content.Contains('$goldenInject'))
Assert-True "t1⑦: 中转目录有**失败路径兜底**清理(且用本 run token, 不用通配)" (
    $content.Contains('rm -rf `"/tmp/agent-stage-$($Script:RUN_TOKEN)`"'))
# ⚠ O-59/T1 实测踩到(并发才现形): 这两个 body 的内容现在是 **per-run** 的(含各自 `$STAGE`),
#   而远端落点曾是**固定名** ⇒ 并发时 B 覆盖 A 的脚本 ⇒ A 建出 **B 的** stage ⇒ A 的 scp 必失败。
#   (与 F-1/F-2/F-14/O-31 同族: "固定远端名 + 并发"必互踩。) 故名字必须带 per-run 身份。
Assert-True "t1⑧: 两处附件中转脚本名带 per-run 身份(固定名 + per-run 内容 = 并发互踩)" (
    $content.Contains('LocalName "agent-cli-attach-reset-$($Script:RUN_TOKEN).sh"') -and
    $content.Contains('LocalName "agent-cli-attach-mkdir-dir-$($Script:RUN_TOKEN).sh"'))
# ⚠ per-run 名的**代价**: 不再互相覆盖 ⇒ 会在 /tmp **累积**(实测三站 0/4/0 个) ⇒ 必须自删。
$trapNeedle = 'trap ''rm -f "`$0"'' EXIT'
Assert-True "t1⑨: 两处中转脚本**自删**(trap EXIT, 覆盖早退路径)" (
    ([regex]::Matches($content, [regex]::Escape($trapNeedle))).Count -ge 2)
# ⚠ 2026-09-25 另一条实测缺陷(**非 T1 引入**): 备路 `$ts` 无去重 ⇒ 同滴答内两个 claude run 共用
#   `%TEMP%\agent-cli-claude-<ts>` scratch ⇒ 互相搬走 agent-output.txt(实测 cc-A/cc-B 同 ts, cc-B 失败)。
#   **后续 (O-63)**: 先补的 `Test-Path` 式判据被实测证明只是 check-then-act(两进程同时通过、`TS_DEDUP`
#   一次未打印) ⇒ 见下方 o63 段, 那层判据已被**原子抢占**取代。

# --- O-63 (2026-09-25): ts 必须**原子**取得（create-or-fail），两条通道共用同一判据 ---
# 先验证据(实测): 两 claude run 同 ts、`TS_DEDUP` 一次未打印、**该 ts 下只有一个 runDir**(而两跑各应有一个)、
#   一方 rc=7。⚠ 件数**不作为论据**: 备路 runDir 的**正常件数就是 5**(9 是主路 opencode 的件数) ——
#   我起初把撞车写成"5 件 vs 正常 9 件", 那是**跨通道**拿错了基线; 换成"runDir 个数"才不受件数影响。
# 钉四件事: ① create-or-fail 不带 -Force ② 两处调用点 ③ 旧 check-then-act 已消失 ④ 抢占物有 GC(有出口)
Assert-True "o63①: 用 `[IO.File]::Open(..., CreateNew, ...)` 做 create-or-fail(文档级原子)" (
    $content.Contains('[IO.File]::Open($cf, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)'))
# ⚠ 这条钉的是**实测教训**: 第一版用 `New-Item -ItemType Directory`（它也抛 IOException）,
#   但 12 进程 hammer 下**仍出现一对重复**(uniq=11) ⇒ 换成 CreateNew。别改回去。
#   (注: 不能用"是否含 -Force"当判据 —— `Remove-Item $cf -Force` 里那个 -Force 是**合法**的;
#    第一版断言就那么写, 结果 needle 被 PS 插值成噪声 ⇒ 恒红。)
Assert-True "o63①b: 抢占**不再**用 `New-Item` 建目录(实测它会漏)" (
    -not $content.Contains('New-Item -ItemType Directory -Path (Join-Path $claims $cand)'))
Assert-True "o63②: 主路 + 备路**都**改调 Get-UniqueRunStamp(跨通道同判据 ⇒ 不会互撞)" (
    ([regex]::Matches($content, 'Get-UniqueRunStamp -ProjOutRoot')).Count -ge 2)
Assert-True "o63③: 旧 check-then-act 去重已消失(`TS_DEDUP` 不再出现)" (
    -not $content.Contains('TS_DEDUP:'))
Assert-True "o63④: 抢占目录有**出口**(对应 runDir 已存在 或 超 7 天 ⇒ 删；防'登记无出口')" (
    $content.Contains("agent-cli-claims") -and $content.Contains('$d.CreationTime -lt $cut'))
Assert-True "o63⑤: 抢占物刻意**不在 agent-out 里**(证据根不放判据看不见的杂物)" (
    $content.Contains("Join-Path `$env:TEMP 'agent-cli-claims'"))

# --- O-62 / C3 + C1 (2026-09-25): 控制台侧**工作区租约**(覆盖 staging; 三处调用) ---
# 实测背景: 同站同 proj 并发两 claude run ⇒ 站上 `.attach` 剩两件、agent 见到不属于它的件。
Assert-True "o62①: 租约为 **rwlock**(排他=`FileShare.None` / 共享=`FileShare.Read`)" (
    $content.Contains('[IO.FileShare]::None') -and $content.Contains('[IO.FileShare]::Read') -and
    $content.Contains('$Script:LEASES +='))
Assert-True "o62②: 备路站上取租约在 **staging 之前**(`$useStation` 分支开头)" (
    $content.IndexOf('Enter-WorkspaceLease -Key "st-$st/$proj"') -lt $content.IndexOf('CLAUDE-STATION: sync 项目工作区'))
Assert-True "o62③: 备路站上取不到 ⇒ **显式 REJECT**(exit 3, 与主路 LOCK_HELD 同码)" (
    $content.Contains('REJECT claude-station-busy (exit 3)') -and $content.Contains('return 3'))
# C1: 主路也参与**同一把逻辑锁**(key 格式 `st-<站>/<proj>`) ⇒ **跨通道**闭环
Assert-True "o62④(C1): 主路取租约在 `TASK sync` 之前, 且 key 与备路**同格式**" (
    $content.IndexOf('Enter-WorkspaceLease -Key $leaseKey -Exclusive $leaseX') -lt $content.IndexOf('TASK sync source ->') -and
    $content.Contains('$leaseKey = $(if ($station) { "st-$station" } else { ''local'' }) + "/$proj"'))
Assert-True "o62⑤(C1): 主路模式按危险面(有附件 ∨ golden) 决定排他/共享" (
    $content.Contains('$leaseX = (($attach.Count -gt 0) -or $goldenActive)') -and
    $content.Contains('REJECT main-workspace-busy (exit 3)'))
# 危险面判据**单一来源**(防两份判据漂移 = 本仓头号失败形态)
# ⚠ 计数 = **2**(不是 1): 两个通道各算一次 —— 主路 `Invoke-Task` 一份、备路 claude 一份。
#   "单一来源"指的是**同一函数内不得有两份**(原先备路就有两份: 附件块内 + golden 段) ⇒ 出 3 即回归。
Assert-True "o62⑥: 危险面表达式**每通道仅一处**(全仓 2 处; 主路一份 + 备路一份)" (
    $content.Contains('$dangerFace = $leaseX') -and
    ([regex]::Matches($content, '\$leaseX = \(\(\$attach\.Count')).Count -eq 2)
Assert-True "o62⑦(本地): 本地带附件时取租约(key=`local/$proj`)且**早于** `projRoot\.attach` 复制" (
    $content.Contains('Enter-WorkspaceLease -Key "local/$proj"') -and
    $content.Contains('REJECT claude-local-busy (exit 3)') -and
    $content.IndexOf('Enter-WorkspaceLease -Key "local/$proj"') -lt $content.IndexOf('$attachLocal = Join-Path $projRoot'))
# ⚠ **实测回归**(2026-09-25, 被**我自己的**跨通道对照实验抓到): 第一版把备路两处租约都写死
#   `-Exclusive $true` ⇒ 良性跨通道配对(只读·无附件, 如 6 并发里的 oc+cc 同站对)也被串行化
#   ⇒ 当场 `REJECT claude-station-busy`。修: 两处都改成危险面 `$leaseX`。
#   ⚠ 漏掉它的根因: **只复跑了 claude×claude，没复跑 6 并发**(该对照是唯一能看见"良性配对"的夹具)。
Assert-True "o62⑧(回归): 备路两处租约都按危险面取模式(非硬编码排他)" (
    ([regex]::Matches($content, [regex]::Escape('Enter-WorkspaceLease -Key "st-$st/$proj" -Exclusive $leaseX'))).Count -eq 1 -and
    ([regex]::Matches($content, [regex]::Escape('Enter-WorkspaceLease -Key "local/$proj" -Exclusive $leaseX'))).Count -eq 1)
# ⚠ 回归的**根因**是判据位置: 危险面原在"有附件"块内算 ⇒ **无附件的站上 golden run** 读到 `$null`(=共享)
#   ⇒ 危险序① 漏挡。修: 上移到本函数开头(两处租约之前)**单点**算。这条钉住**位置不变式**。
Assert-True "o62⑨(根因): 危险面判据在 `if ($useStation)` **之前**(否则无附件站上 golden run 会漏挡)" (
    $content.IndexOf('$leaseX = (($attach.Count -gt 0) -or $goldenActive)') -gt 0 -and
    $content.IndexOf('$leaseX = (($attach.Count -gt 0) -or $goldenActive)') -lt $content.IndexOf('if ($useStation)'))

Write-Host "--------------------------------"
Write-Host "FM_GOLDEN_TEST pass=$pass fail=$fail"
exit $(if ($fail -eq 0) { 0 } else { 1 })