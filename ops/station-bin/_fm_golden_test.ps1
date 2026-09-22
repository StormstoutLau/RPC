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
foreach ($nm in @('Get-FrameworkSubjects', 'Get-ClaudeFrameworkSubjects', 'Merge-EvidenceSubjects', 'Test-FallbackEligible', 'Test-CtxOverflowError', 'Resolve-CtxOverflowCode', 'Resolve-ClaudeStationCandidates', 'Get-SensitivityBackendReject', 'Get-BackendEgress', 'Get-JudgeEgress', 'Get-JudgeComplianceReject', 'Get-AttachEgressReject', 'Get-ScrubRules', 'Invoke-Scrubber', 'Get-ScrubBlockReason', 'Resolve-ReviewPrompt', 'Resolve-ClaudeBudget', 'Resolve-LocalBash', 'Invoke-LocalBashCmd', 'Resolve-ExitCode')) {
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
Assert-True "baseline: 无 accept 无 golden => 11 件" ($b0.Count -eq 11)
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
# 11(基线) + 2(卡声明) - 1(其中 prompt 与基线同 path, 去重) = 12
Assert-True "merge: 基线11 + 卡声明2 - 重复1 = 12" ($mg.Count -eq 12)
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

# 路B 的核心目的: **无 manifest 的卡**(= 71 个真实 run 的来源)也能拿到非空声明 ⇒ 不再是 recipe v1
$m0 = @(Merge-EvidenceSubjects @() @() $false)
Assert-True "merge: 空卡仍得 11 件(=> 不再退化为 recipe v1)" ($m0.Count -eq 11)

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
# baselineFn 缺省(主路调用点)不传时行为不变 => 既有的 11 件合并仍成立(防退化)
$defmg = @(Merge-EvidenceSubjects @() @() $false)
Assert-True "claude merge: 缺省 baselineFn 仍得主路 11 件(未破坏主路调用)" ($defmg.Count -eq 11)

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
Assert-True "station: 判据已参数化 -backendEgress (-not \$useStation)(P2 的核心)" (
    $content.Contains('-backendEgress (-not $useStation)'))
Assert-True "station: 分流判据 = sensitivity eq 'local-only'" (
    $content.Contains('$useStation = ($sens -eq ''local-only'')'))
Assert-True "station: 站上不可用 ⇒ fail-closed(有 REJECT 行 + return 4, 且该分支内无 Invoke-ClaudeFly 回退)" (
    $content.Contains('REJECT local-only-no-station-engine (exit 4)'))
$iNoSt = $content.IndexOf('REJECT local-only-no-station-engine')
$iBlk  = $content.IndexOf('$useStation = ($sens -eq ''local-only'')')
$blkSeg = $content.Substring($iBlk, $iNoSt - $iBlk)
Assert-True "station: fail-closed 分支里**没有**主控本地 spawn(回退=出网)" (
    -not ($blkSeg -match 'Invoke-ClaudeFly\s'))
Assert-True "station: 两处 runner 调用点都已分流(首跑 + resume)" (
    ([regex]::Matches($content, 'Invoke-ClaudeFly-Station -hostName')).Count -ge 2)
# ⚠ 位置断言 —— 2026-09-21 **实弹踩到的顺序 bug**: 初版把 `$stPref` 块放在 `$useStation` 赋值
#   **之前** ⇒ PS 未定义变量为 `$null` ⇒ `if ($useStation)` 为假 ⇒ 走旧的 `REJECT claude-station`
#   分支 ⇒ `local-only` 卡被旧语义误拒。**夹具当时全绿**(它只查"串在不", 查不出顺序) ⇒ 补此条。
$iUse = $content.IndexOf('$useStation = ($sens -eq ''local-only'')')
$iPref = $content.IndexOf("`$stPref = ''")
Assert-True "station: \$useStation 赋值**早于** \$stPref 使用(实弹踩到的顺序 bug)" (
    $iUse -gt 0 -and $iPref -gt 0 -and $iUse -lt $iPref)
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
#   直接入口按**后端属性** ⇒ `(-not $useStation)`(站上本地时不出网)。故断言改为:
#   "两处都调判据" + "两种输入形式都在"(后者正是 P2 的核心, 单列一条以防被改回硬编码)。
Assert-True "reject: 判据在两个入口均被调用(直接入口 + 兜底入口)" (
    ([regex]::Matches($content, [regex]::Escape('Get-SensitivityBackendReject -sensitivity $sens -backendEgress'))).Count -ge 2)
Assert-True "reject: 兜底入口用 \$true(主控本地=出网), 直接入口用 (-not \$useStation) 按后端属性" (
    $content.Contains('Get-SensitivityBackendReject -sensitivity $sens -backendEgress $true') -and
    $content.Contains('Get-SensitivityBackendReject -sensitivity $sens -backendEgress (-not $useStation)'))
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

Write-Host "--------------------------------"
Write-Host "FM_GOLDEN_TEST pass=$pass fail=$fail"
exit $(if ($fail -eq 0) { 0 } else { 1 })