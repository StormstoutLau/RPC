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
foreach ($nm in @('Get-FrameworkSubjects', 'Get-ClaudeFrameworkSubjects', 'Merge-EvidenceSubjects', 'Test-FallbackEligible', 'Test-CtxOverflowError', 'Resolve-CtxOverflowCode', 'Resolve-ClaudeStationCandidates', 'Get-SensitivityBackendReject', 'Resolve-ClaudeBudget', 'Resolve-LocalBash', 'Invoke-LocalBashCmd')) {
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

# --- O-15/AUDIT (2026-09-21): claude 备路按路基线(证据面到齐 => recipe v2) ---
# 该路归档件集 = opencode 子集 + stderr, 无 judgment-record 等远端合成批件
$cb = @(Get-ClaudeFrameworkSubjects @() $false)
$cbn = @($cb | ForEach-Object { $_.name })
Assert-True "claude: 无 accept/golden => 4 件" ($cb.Count -eq 4)
Assert-True "claude: 含 agent-output/prompt/stderr/card" (
    ($cbn -contains 'agent-output') -and ($cbn -contains 'prompt') -and
    ($cbn -contains 'stderr') -and ($cbn -contains 'card'))
# 负向自证: claude 基线**不得**混入 opencode 专用件, 否则每 run 假报缺件(噪声判据)
Assert-True "claude: 无 judgment-record/workdiff/sessmeta/attach/mishap" (-not (
    ($cbn -contains 'judgment-record') -or ($cbn -contains 'workspace-diff') -or
    ($cbn -contains 'session-meta') -or ($cbn -contains 'attach-manifest') -or
    ($cbn -contains 'progress-trace') -or ($cbn -contains 'accept-cmds') -or ($cbn -contains 'golden-cmd')))

$cb1 = @(Get-ClaudeFrameworkSubjects @('echo ok') $true)
$cbn1 = @($cb1 | ForEach-Object { $_.name })
Assert-True "claude: 有 accept+golden => 6 件" ($cb1.Count -eq 6)
Assert-True "claude: 含 accept-output/accept-golden-output" (
    ($cbn1 -contains 'accept-output') -and ($cbn1 -contains 'accept-golden-output'))

# 合并: claude 走 baselineFn 分支 —— 空卡 => 得 claude 基线(4), 不掺主路 10 件
$cmg = @(Merge-EvidenceSubjects @() @() $false { param($ac,$ga) Get-ClaudeFrameworkSubjects $ac $ga })
Assert-True "claude merge: 空卡 => 4 件(claude 基线, 而非主路 10)" ($cmg.Count -eq 4)
# 去重: 卡声明与 claude 基线同 path(prompt.txt)只出现一次
$csubs = @(
    @{ name = 'prompt'; path = 'prompt.txt'; digest = 'sha256'; collect = ''; ephemeral = $false }
    @{ name = 'station-tmp-log'; path = ''; collect = 'tail -5 /tmp/x.log'; digest = 'sha256'; ephemeral = $true }
)
$cmg2 = @(Merge-EvidenceSubjects $csubs @() $false { param($ac,$ga) Get-ClaudeFrameworkSubjects $ac $ga })
Assert-True "claude merge: 基线4 + 卡声明2 - 重复1 = 5" ($cmg2.Count -eq 5)
Assert-True "claude merge: prompt.txt 只出现一次" ((@($cmg2 | Where-Object { $_.path -eq 'prompt.txt' })).Count -eq 1)
Assert-True "claude merge: 卡特有件保留" ((@($cmg2 | Where-Object { $_.name -eq 'station-tmp-log' })).Count -eq 1)
# baselineFn 缺省(主路调用点)不传时行为不变 => 既有的 10 件合并仍成立(防退化)
$defmg = @(Merge-EvidenceSubjects @() @() $false)
Assert-True "claude merge: 缺省 baselineFn 仍得主路 10 件(未破坏主路调用)" ($defmg.Count -eq 10)

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

Write-Host "--------------------------------"
Write-Host "FM_GOLDEN_TEST pass=$pass fail=$fail"
exit $(if ($fail -eq 0) { 0 } else { 1 })