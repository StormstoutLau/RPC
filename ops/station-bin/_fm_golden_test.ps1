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
foreach ($nm in @('Get-FrameworkSubjects', 'Get-ClaudeFrameworkSubjects', 'Merge-EvidenceSubjects', 'Test-EvmStatePull', 'Test-FallbackEligible', 'Test-CtxOverflowError', 'Resolve-CtxOverflowCode', 'Resolve-ClaudeStationCandidates', 'Get-SensitivityBackendReject', 'Get-BackendEgress', 'Get-JudgeEgress', 'Get-JudgeComplianceReject', 'Get-AttachEgressReject', 'Get-ScrubRules', 'Invoke-Scrubber', 'Get-ScrubBlockReason', 'Resolve-ReviewPrompt', 'Resolve-ClaudeBudget', 'Resolve-LocalBash', 'Invoke-LocalBashCmd', 'Resolve-ExitCode', 'Test-GateSummaryOk', 'Resolve-GateCommand',
# O-92 (2026-09-26): 双盲重推导 —— 三个**纯函数** + `Read-ReviewResource`（`Build-BlindPrompt` 依赖它）。
# ⚠ 把 `Read-ReviewResource` 也提取进来 ⇒ 本夹具读的是**真模板文件**
#   ⇒ "盲判模板里不得有 `{{PRODUCT}}`"这条能变成**行为断言**（真跑一遍看输出），而不是扫文本。
'Read-ReviewResource', 'Get-AssertionBlock', 'Build-BlindPrompt', 'Compare-AssertionChains',
# D7-P2-1 (2026-09-26): **机械门先行** 的判定本体（纯函数：只吃已解析的 run 记录 ⇒ 可离线单测）。
# D7-P2-2 (2026-09-26): **结论契约** —— 三个纯函数（校验器 + 综合器）。
'Test-FindingShape', 'Test-ConclusionContract', 'Merge-JudgeFindings', 'Resolve-L1Gate',
# D7-P3-1 (2026-09-26): **不得自审**的判定本体（纯函数）。
'Resolve-SelfReviewGuard',
# D7-P3-2 (2026-09-26): **编排层 —— 谁审谁** 的选择器（纯函数）。
'Select-Reviewer',
# A1 / ADR-0009 §2 (2026-09-29): **D6/D7 层级归属**的求值本体（纯函数：只吃三个布尔 ⇒ 可离线单测）。
'Resolve-D6D7Boundary',
# O-124 (2026-09-30): 批报告取【实际执行站】的判定本体（纯函数：只吃日志行数组 ⇒ 可离线单测）。
# O-124 候选① (2026-09-30): host -> 站字母 的**唯一反查点** + 它的真值源 `Get-TargetHost`
#   （⚠ 必须一并提取 `Get-TargetHost` —— 反查若自己另抄一份 host 表, 就是"同一事实两处表达"）。
# O-125 候选① (2026-09-30): 卡面 `backend:` 的**唯一解析点**（纯函数：吃档位 + 字段值 ⇒ 离线可单测）。
'Get-ActualStation', 'Get-StationLetterFromHost', 'Get-TargetHost', 'Resolve-CardBackendLocal',
# B3 第二半 (2026-10-01): `PRH`（同机可见性）的**两侧事实**推导（纯函数：吃站字母 ⇒ 两个 host 串）。
#   ⚠ 必须一并提取 `Get-TargetHost`（上面已有）—— 它推产出机时用的就是**同一个** host 表，
#     另抄一份 host 表 = "同一事实两处表达"（本仓头号形态）。
'Resolve-D7Hosts',
# 2026-10-01（`O-136` "灰度转硬拒"前置）：`gaps` 的**两分**（纯函数：吃 gaps 名数组）。
#   ⚠ 它依赖 `$Script:D7_GAP_CLASS` 表 ⇒ 必须**一并提取那张表**（同 ROUTE_TABLE/JUDGE_TABLE 的处置）——
#     否则在夹具里表为 `$null` ⇒ 每一项都落 `unknown` ⇒ **断言会假绿**（"看起来分了类"）。
'Split-D7Gaps',
# O-140 (2026-10-01 裁【甲·可机判版】): **该 run 是否已入证据链**（纯函数：吃链件路径 + proj/run_id）；
#   ⚠ 它只吃**路径**、不碰 `$Script:REPO_ROOT` ⇒ 夹具喂**临时链件**即可**真跑**三态（不是形态断言）。
'Resolve-RunChained',
# D7-CC #8 + #3 (2026-09-30): 判官**取哪件产物**（卡声明 + 强制回退）与**提示词注入产物相对名**
#   （`Resolve-ReviewProduct` 的 `-Exists` 可注入 ⇒ 离线真跑；`Build-JudgePrompt` 依赖已提取的 `Read-ReviewResource`）。
# B 段 (2026-10-01): **P0 立契**的产信封本体（纯函数：只吃已解析的 $fm/$cardId ⇒ 可离线单测）
#   ⚠ 必须一并提取 `Get-Sha256Text` —— 它是 `criteria_hash` 的**唯一**实现点（不许另抄一份哈希）。
'Resolve-ReviewProduct', 'Build-JudgePrompt',
'Get-Sha256Text', 'New-TaskContract',
# B2 (2026-10-01): **P3 回收 / P4a-P4b-P5** 的**纯**那半（产 RunReport / 相序列 / 产 Verdict）
#   ⚠ 有副作用的那半（`Invoke-D7Cli` / `Write-D7Report` / `Write-D7Adjudication`）**刻意不提取** ——
#     它们起子进程；只在本夹具里做**接线形态**断言（判据本体由 py 侧用例覆盖）。
'New-RunReport', 'Resolve-D7PhaseChain', 'New-Verdict')) {
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

# --- O-90 (2026-09-26): 一并提取**真实门禁表 + 汇总行正则 + 复用表**（同为赋值语句） ---
# 为什么必须测真表: `Resolve-GateCommand` 是**纯查表**函数 ⇒ 表空了它就"恒不命中"
#   ⇒ 断言会变成"**判据什么都没判**"（本仓头号形态）。故必须验**真表非空**且值真的是命令。
# `$Script:GATE_SUMMARY_RE` 也必须提取 —— `Test-GateSummaryOk` 依赖它（漏了它会整段抛错）。
foreach ($asn in @('$Script:GATE_TABLE', '$Script:GATE_SUMMARY_RE', '$Script:GATE_CACHE',
                   # O-92: 断言块正则 / 封闭枚举。
                   # ⚠ **刻意不含 `$Script:REVIEW_DIR`** —— 它那条赋值读 `$PSScriptRoot`，
                   #   而 **`Invoke-Expression` 的子作用域里取不到 `$PSScriptRoot`**（下文 O-92⓪ 有实测记录）
                   #   ⇒ 提取它会抛 "Cannot bind argument to parameter 'Path' ... empty string"。
                   '$Script:ASSERT_BLOCK_RE', '$Script:ASSERT_OPS',
                   # 2026-10-01（`O-136` "灰度转硬拒"前置）：`gaps` 两分的**唯一真值表**。
                   #   ⚠ 漏提取 ⇒ `Split-D7Gaps` 见到的表是 `$null` ⇒ **每一项都落 `unknown`** ⇒
                   #     下面的分类断言会**假绿**（"看起来分了类"）—— 故必须提取**真表**。
                   '$Script:D7_GAP_CLASS')) {
    $a = @($ast.FindAll({ param($n)
        $n -is [System.Management.Automation.Language.AssignmentStatementAst] -and
        $n.Left.Extent.Text -eq $asn }, $true)) | Select-Object -First 1
    if (-not $a) { throw "$asn assignment not found in agent-cli.ps1" }
    Invoke-Expression $a.Extent.Text
}
Write-Host "DEBUG GATE_TABLE keys=$(@($Script:GATE_TABLE.Keys).Count)"

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
# ★ A2 (2026-09-29): 期望 9 → **10/14** —— **合法演进**（非回归）: 主路基线新增 `executor-trace` 件
#   （执行侧过程留痕, 见 agent-cli.ps1 该处注释 + A-LIST-LANDING-PLAN §2.4）。⇒ 无 accept/golden = 10、
#   有 accept+golden = 14。**判据**：有代码注释为证 ⇒ 改期望值, 不改代码。
$b0 = @(Get-FrameworkSubjects @() $false)
$n0 = @($b0 | ForEach-Object { $_.name })
Assert-True "baseline: 无 accept 无 golden => 10 件" ($b0.Count -eq 10)
Assert-True "baseline: 含 judgment-record/prompt/workspace-diff/executor-trace/card" (
    ($n0 -contains 'judgment-record') -and ($n0 -contains 'prompt') -and
    ($n0 -contains 'workspace-diff') -and ($n0 -contains 'executor-trace') -and ($n0 -contains 'card'))
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
Assert-True "baseline: 有 accept+golden => 14 件" ($b1.Count -eq 14)
Assert-True "baseline: 有 accept+golden => 含 accept-output/accept-golden-output" (
    ($n1 -contains 'accept-output') -and ($n1 -contains 'accept-golden-output'))

# 合并: 卡里历史遗留的框架件声明必须与基线**去重**(否则同一件在链上出现两次)
$cardSubs = @(
    @{ name = 'prompt'; path = 'prompt.txt'; digest = 'sha256'; collect = ''; ephemeral = $false }
    @{ name = 'station-tmp-log'; path = ''; collect = 'tail -5 /tmp/x.log'; digest = 'sha256'; ephemeral = $true }
)
$mg = @(Merge-EvidenceSubjects $cardSubs @() $false)
# 10(基线) + 2(卡声明) - 1(其中 prompt 与基线同 path, 去重) = 11
# O-56 (2026-09-25): 10 -> 9 —— `accept-cmds` 已改**条件列**（无 accept 的卡站上**永不产出**该件）。
#   与 §218 那条同性质: **合法演进**（判据缺陷修复），故改期望值而非改代码。
# ★ A2 (2026-09-29): 9 -> 10(基线) ⇒ 合并结果 11 —— 基线新增一件（`executor-trace`）。
Assert-True "merge: 基线10 + 卡声明2 - 重复1 = 11" ($mg.Count -eq 11)
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
Assert-True "merge: 空卡仍得 10 件(=> 不再退化为 recipe v1)" ($m0.Count -eq 10)

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
# baselineFn 缺省(主路调用点)不传时行为不变 => 既有的合并仍成立(防退化; O-56: 10 -> 9; A2: 9 -> 10)
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
Assert-True "station: 判据已参数化 -backendEgress (-not \$backendLocal)(P2 的核心; D7 起与位置解耦)" (
    $content.Contains('-backendEgress (-not $backendLocal)'))
Assert-True "station: 分流判据 = local-only **或** 路由声明了站(D7 拆成两个量)" (
    $content.Contains('$useStation = $backendLocal -or [bool]$r[''station''] -or [bool]$PreferredStation'))
# ⚠ O-125 候选① (2026-09-30): 原字面量 `$backendLocal = ($sens -eq 'local-only')` **已不存在**
#   （判定改由纯函数 `Resolve-CardBackendLocal`）⇒ 本守卫的字面量随之更新；
#   ★ **不变式一个字没改**: 后端属性**仍与位置解耦**（判定输入 = 档位 + 卡面 `backend`，**不含站**）。
Assert-True "station: 后端属性独立于位置(判定输入 = 档位 + 卡面 backend; 不含站)(D7 拆锁)" (
    $content.Contains('$br = Resolve-CardBackendLocal -Sensitivity $sens -Backend ([string]$fm[''backend''])'))
Assert-True "station: 站上不可用 ⇒ fail-closed(有 REJECT 行 + return 4, 且该分支内无 Invoke-ClaudeFly 回退)" (
    $content.Contains('REJECT local-only-no-station-engine (exit 4)'))
$iNoSt = $content.IndexOf('REJECT local-only-no-station-engine')
$iBlk  = $content.IndexOf('$useStation = $backendLocal -or [bool]$r[''station''] -or [bool]$PreferredStation')
$blkSeg = $content.Substring($iBlk, $iNoSt - $iBlk)
Assert-True "station: fail-closed 分支里**没有**主控本地 spawn(回退=出网)" (
    -not ($blkSeg -match 'Invoke-ClaudeFly\s'))
Assert-True "station: 两处 runner 调用点都已分流(首跑 + resume)" (
    ([regex]::Matches($content, 'Invoke-ClaudeFly-Station -hostName')).Count -ge 2)
# ⚠ 位置断言 —— 2026-09-21 **实弹踩到的顺序 bug**: 初版把 `$stPref` 块放在 `$useStation` 赋值
#   **之前** ⇒ PS 未定义变量为 `$null` ⇒ `if ($useStation)` 为假 ⇒ 走旧的 `REJECT claude-station`
#   分支 ⇒ `local-only` 卡被旧语义误拒。**夹具当时全绿**(它只查"串在不", 查不出顺序) ⇒ 补此条。
#   ⚠ O-124 候选① (2026-09-30): 两行**字面量都改过**（`$useStation` 增 `-or [bool]$PreferredStation`；
#     `$stPref` 由 `''` 改为 `[string]$r['station']` + 回落行）⇒ 本条断言的字面量随之更新 ——
#     **守卫的语义一个字没改**（仍钉"赋值早于使用"）。
#   ⚠ O-125 候选① (2026-09-30): `$useStation` 的字面量**再改一次**（`($sens -eq 'local-only')` ⇒ `$backendLocal`）
#     ⇒ 同法更新；★ **并补一条同族的次序守卫**（见下）:`$backendLocal` 的解析块也必须早于 `$useStation`
#     —— 这**不是假想**: 本次实现时第一版正是把它放在 `$useStation` 之后（PS 下 `$null` ⇒ 假 ⇒ 静默走错通道）。
$iUse = $content.IndexOf('$useStation = $backendLocal -or [bool]$r[''station''] -or [bool]$PreferredStation')
$iPref = $content.IndexOf('$stPref = [string]$r[''station'']')
Assert-True "station: \$useStation 赋值**早于** \$stPref 使用(实弹踩到的顺序 bug)" (
    $iUse -gt 0 -and $iPref -gt 0 -and $iUse -lt $iPref)
$iBr = $content.IndexOf('$backendLocal = $br[''local'']')
Assert-True "station: \$backendLocal 解析**早于** \$useStation 使用(同族的顺序硬约束)" (
    $iBr -gt 0 -and $iUse -gt 0 -and $iBr -lt $iUse)

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
Assert-True "rc: exit (Resolve-ExitCode `$code) = 6(实测 $exitGuard) ⚠ 增删子命令须同步改本数（2026-09-26 加 batch ⇒ 5→6）" ($exitGuard -eq 6)
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
           '.workspace-diff.txt', '.executor-trace.txt', '.attach-manifest.txt', '.session-meta.txt',
           '.agent-output.txt', '.accept-output.txt', '.accept-golden-output.txt')
$evMiss = @($evAll | Where-Object { -not $content.Contains("name = '$_'") })
Assert-True "o57: 真值表含全部 **12** 个暂存件(逐名核对; 缺: $($evMiss -join ', '))" ($evMiss.Count -eq 0)
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
# ★ 2026-09-26: 夹具此前**只读 agent-cli.ps1**（`$content`/`$codeOnlyFull`），但 O-70 的 `[orph2]` 探针
#   **住在 `ops/rpc_check.py`** ⇒ 断言必须读**那个文件**。
#   ⚠ 我第一版把 o70 断言写在 `$codeOnlyFull` 上（= 读错了被测对象）⇒ **门禁 P3-2 当场判红**
#     —— 那条"先判是回归还是夹具期望值陈旧"的护栏正为此存在，这次它咬的是**我**。
$checkSrc = [System.IO.File]::ReadAllText('d:\RPC\ops\rpc_check.py', [System.Text.UTF8Encoding]::new($false))
$checkCode = (($checkSrc -split "`n") | ForEach-Object { $_ -replace '#.*$', '' }) -join "`n"
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
# ★★ 最强的那条: **11 个 body 内基名的写点全部带后缀**, 且**裸名残留必须为 0**
$evBases = @('.meta', '.prompt.txt', '.progress', '.accept-cmds.txt', '.golden-cmd.txt',
             '.workspace-diff.txt', '.executor-trace.txt', '.attach-manifest.txt',
             '.agent-output.txt', '.accept-output.txt', '.accept-golden-output.txt')
$evBare = @($evBases | Where-Object { $content.Contains('$W/out/' + $_ + '"') })
Assert-True "o68: ★★ 站上写点**无裸名残留**(逐个核对; 残留: $($evBare -join ', '))" ($evBare.Count -eq 0)
$evNoSuf = @($evBases | Where-Object { -not $content.Contains('$W/out/' + $_ + '`$EV_SUF') })
Assert-True "o68: ★★ 11 个基名**逐个**都插了后缀(缺: $($evNoSuf -join ', '))" ($evNoSuf.Count -eq 0)
Assert-True "o68: 主控侧三处用 **PS 变量 `evSuf`**(不是站上那个 bash 变量 ⇒ 语法域不同)" (
    ([regex]::Matches($content, '\$W/out/\.(agent-output|accept-output|accept-golden-output)\.txt\$evSuf')).Count -ge 3)
Assert-True "o68: 会话遥测 helper 的目标路径也带后缀(它**不走** body ⇒ 单独一处)" (
    $content.Contains(".session-meta.txt`$evSuf'"))
Assert-True "o68: 合批的远端路径带后缀, 但 **marker 仍发基名**(归档映射靠基名)" (
    $content.Contains('$W/out/$($_)$evSuf') -and $content.Contains('echo FILE:$_'))

# --- ★★ A2 (2026-09-29): 执行侧**过程留痕** —— 5 项采集点 + `[tool]` 恒 uncore ---
#   为什么: 判据只能看**产物**, 看不到**过程**（幻觉抑制最缺的那类证据 —— 它怎么得出这个结论）。
#   ⚠ **最关键的一条是负向的**: `[tool]`（工具调用链）由**执行体内部**产生 ⇒ 恒标 `uncore`（不可核）——
#     若有人把它改成"可核/verified", 就是把**没判的说成判了且通过**（本仓头号形态）⇒ 断言必须红。
Assert-True "a2: `[cmd]`/`[env]`/`[fs]`/`[tool]`/`[artifact]` 五个采集点**逐个**在 body 里" (
    $content.Contains('[cmd] cmd=') -and $content.Contains('[env] caught_at=') -and
    $content.Contains('[fs] diff_pointer=') -and $content.Contains('[tool] chain=') -and
    $content.Contains('[artifact] hashes='))
Assert-True "a2: `[env]` 采集点在**启动器**(fork 前捕获 ⇒ launch_ns 早于 agent 运行)" (
    ([regex]::Matches($content, '\[env\] caught_at=launcher')).Count -eq 1)
Assert-True "a2: ★ `[tool]` **恒 uncore**(执行体内部 ⇒ 不可核; 绝不冒充可核证据)" (
    $content.Contains('[tool] chain=uncore'))
Assert-True "a2: ★ 负向自证 —— body 里**不存在**把它标成可核的形态(`chain=core`/`chain=verified`)" (
    -not ($content.Contains('chain=core') -or $content.Contains('chain=verified')))
Assert-True "a2: env 采集只用**可达命令**(`free -m`, 不读 `/proc` —— README 纪律 8)" (
    $content.Contains('free -m') -and -not $content.Contains('cat /proc/meminfo'))
Assert-True "a2: `[env]` 段用 `>` 建件 + `[cmd/fs/tool/artifact]` 段用 `>>` 追加(同 run 分两处采集)" (
    $content.Contains('} > "`$W/out/.executor-trace.txt`$EV_SUF"') -and
    $content.Contains('} >> "`$W/out/.executor-trace.txt`$EV_SUF"'))
Assert-True "a2: 主控侧把留痕件**归档进 runDir**(executor-trace.txt)" (
    $content.Contains("(Join-Path `$runDir 'executor-trace.txt')"))
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
# --- O-75 残面② 收口 (2026-09-26): 站上 claude 的两条**前置探针**也改走有整体墙钟的执行器 ---
# 为什么当时没做（原文）: 它们的 argv 里含**双引号**（`test -f "$HOME/…"`），改用原始参数字符串会重开纪律 12 的引号地狱。
# ⇒ 本轮的做法是**从根上消掉引号**：路径不含空格 ⇒ 那对双引号本来就不需要。
Assert-True "o75⑤: 两条站上前置探针改走有**整体墙钟**的执行器（残面②收口）" (
    $codeOnlyFull.Contains('Invoke-CappedSsh -Arguments ("-o ConnectTimeout=8 ${remoteUser}@${hostName} bash /tmp/_station_ready.sh $alias")') -and
    $codeOnlyFull.Contains('Invoke-CappedSsh -Arguments ("-o ConnectTimeout=8 ${remoteUser}@${hostName} " + $probe)'))
Assert-True "o75⑥: 探针命令**一个双引号都不含**（`$HOME` 那对引号已去掉 ⇒ 不再有引号地狱可踩）" (
    $content.Contains("test -f `$HOME/.config/rpc/openrouter.key") -and
    -not $content.Contains('test -f "$HOME/.config/rpc/openrouter.key"'))

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
# ⚠ 2026-09-29 期望值更新（**不是回归**）：该句原文里的 `` `bash` `` 落在**双引号 here-string 内** ⇒
#   PS 会把单反引号当转义吃掉 ⇒ 生成件与源码不一致（详见 `o117`）。⇒ 源码按设计改为**双写**
#   ``` ``bash`` ```（渲染出字面反引号）⇒ 本断言同步改期望值。★ 语义一字未变。
Assert-True "o72④: 源码写明【为什么主 body 不自删】(防后来者照抄 T1 的 trap 自删)" (
    $content.Contains('把成功判成失败') -and $content.Contains('再 ``bash`` 一次'))
# ── o117 (2026-09-29): 双引号 here-string 内的「反引号 + 转义字母」会把 markdown 内联码变成**控制字符** ──
#   一手事故: 当日 23:01 批 **4/4 全挂 `exit=255`** —— A2 的采集点注释里写了 `` `nproc` `` / `` `free -m` `` /
#   `` `nvidia-smi` ``，而 `@"..."@` **先做 PS 转义**：`` `n ``→LF · `` `f ``→FF ⇒ 注释**后半截被推出 `#` 之外**
#   ⇒ bash 当命令跑（`proc/ree: 没有那个文件或目录`）⇒ **整条派发链死**（且报错点离病因很远）。
#   ★★ 当时静态断言 `o72④` **全绿** —— 又是本夹具自述的「查'串在不', 查不出'这条链现在跑不跑得起来'」。
#   ⇒ 口径: 双引号 here-string **区段内**，**奇数个**反引号紧邻 [nftbrva0] ⇒ 必红。
#      （**双写** ``` `` ``` 即安全 —— PS 渲染成**字面反引号**，源码与生成件重新一致。）
#   ⚠ 区段判定用**行式**（行尾 `@"` 开、行内仅 `"@` 收）—— 与 `Invoke-RemoteScript` 实际生成的一致，
#     不用跨文件非贪婪正则（那会被注释里偶然出现的 `@"` 骗出假区段）。
$hLines = $content.Split("`n")
$hInDq = $false
$hBad = @()
for ($hk = 0; $hk -lt $hLines.Count; $hk++) {
    $hCur = $hLines[$hk]
    if ($hInDq) {
        if ($hCur.Trim() -eq '"@') { $hInDq = $false; continue }
        foreach ($hmm in [regex]::Matches($hCur, '(`+)([nftbrva0])')) {
            if (($hmm.Groups[1].Value.Length % 2) -eq 1) { $hBad += ("L$($hk+1)=" + $hCur.Trim()) }
        }
    } elseif ($hCur.TrimEnd().EndsWith('@"')) { $hInDq = $true }
}
Assert-True "o117: 双引号 here-string 内**不得**出现【奇数个反引号 + n/f/t/b/r/v/a/0】(PS 当转义 ⇒ 注入控制字符 ⇒ 生成件坏)（危险点 $($hBad.Count) 处）" ($hBad.Count -eq 0)
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

# --- O-67 (2026-09-25): egress 的 `SPLIT_WARN` 措辞必须与**实测**一致（实测 2 片/2 站 = **真并行**） ---
# 旧措辞 "egress has single route, fanout may not parallelize" 是**读码推断**，已被 `split` 实测推翻
#   （`wall_ms=31396` ≈ 单片+开销，远低于串行下界 44s）⇒ 留着它会让读者**放弃一条可用的能力**。
# ⚠ 判据必须**只看代码**：改动说明里必然要**引用旧措辞**（否则读者不知道改了什么），
#   而全文子串会让"引用"与"仍在用"混为一谈。⇒ 复用上面 o68 段已建好的 `$codeOnlyFull`（去 `#` 之后的部分）。
#   ★ 这是同一个坑的**第三次**实例：O-65（假绿：注释能蒙过判据）· O-73（假红：注释里的变量名绊倒判据）· 本条。
#     ⇒ 凡"判某串在/不在"的断言，**先问一句：它会不会被注释影响？**
Assert-True "o67①: SPLIT_WARN **不再**断言『出网档 fan-out 可能不并行』(只看代码)" (
    -not $codeOnlyFull.Contains('fanout may not parallelize'))
# ⚠ 2026-09-26 期望值更新（**是"夹具陈旧"不是回归**）：代码侧按新的取证把括号里的实测数字
#   从「2 片/2 站成立」改成「2 片/2 站、3 片/3 站均成立」（O-67 补测满宽度 3/3，见台账）。
#   ⇒ 顺手把本断言**改成不锚具体数字** —— 否则"证据每增长一次就要改一次夹具"，
#     而这类摩擦的常见下场是**有人干脆把断言删掉**（比不锚更危险）。
Assert-True "o67②: 把条件写成**账户/站粒度**（跨站独立 key ⇒ 可并行）；实测数字随取证更新，断言只锚措辞结构" (
    $content.Contains('并行性取决于**账户/站粒度**') -and
    $content.Contains('跨站（各站独立 key）= 可并行') -and
    $content.Contains('实测') -and $content.Contains('均成立'))

# --- O-70 修法③ (2026-09-26): `orph2` 的**自匹配**不能靠"文本巧合"来挡 ---
# 一手实测（三站对照）: 无残留时 **NAIVE 版（只把排除键换成 `ps -eo`）会多报 1 行 —— 就是 `grep` 进程自己**；
#   而 **NEW 版（按 pgid 排除自己的进程组）0 行**；有真残留时 NEW **只列出真的那条**。
Assert-True "o70①: 探针按 **pgid** 排除自己的进程组（结构性修法，不靠模式串）· **读 rpc_check.py**" (
    $checkCode.Contains('pid=,pgid=,etimes=,args=') -and
    $checkCode.Contains('awk -v pg=$(') -and
    $checkCode.Contains('$2!=pg'))
Assert-True "o70②: **反向断言** —— 不许退回 `grep -v -e grep` 那种'恰好挡住'的文本巧合（它会静默排掉含 `grep` 的真残留）" (
    -not $checkCode.Contains('grep -v -e grep'))

# --- O-76 (2026-09-25): 私有中转目录的**按龄清**（"派发在 body 之前中止"那一格的出口） ---
# 一手泄漏: B 站 2 个残留（含 attach/ 与 golden.tgz，其中一个是 O-71 那次 aborted 派发）。
# ⚠ 这条是**破坏性命令** ⇒ 判据必须双向: ①源码只按龄 ②**行为上**老件被删、**新件保留**。
Assert-True "o76①: 有 `agent-stage-*` 的按龄清(目录形态 + `-mtime +7` + `-exec rm -rf`)" (
    $content.Contains("find /tmp -maxdepth 1 -type d -name 'agent-stage-*' -mtime +7 -exec rm -rf {} +"))
# ⚠ 只看代码: O-46 段的**注释**里为警示写了"绝不能用通配 `/tmp/agent-stage-*`" ⇒ 全文子串会假红
#   （同 o67① 的坑，第三次；见上面 o67 那段的注释）。
Assert-True "o76②: 代码里**没有**『通配删所有 agent-stage』的危险写法(会误删在飞的)" (
    -not $codeOnlyFull.Contains('rm -rf /tmp/agent-stage-*') -and
    -not $codeOnlyFull.Contains("/tmp/agent-stage-*'"))
# ★★ 行为测试（本地 Git Bash）: 造"8 天前"与"刚刚"各一个 agent-stage-*，跑**同一条 find** ⇒
#   老件必须被删、**新件必须留下**（后者才是"不误删在飞的"那半个判据；只验"删掉老的"是不够的）。
$o76Root = (Join-Path $env:TEMP 'fm_o76_stage_probe').Replace('\', '/')
$log76 = Join-Path $env:TEMP 'fm_o76_find.log'
Remove-Item $log76 -ErrorAction SilentlyContinue
$oldStamp = (Get-Date).AddDays(-8).ToString('yyyyMMddHHmm')
$cmd76 = "rm -rf '$o76Root'; mkdir -p '$o76Root/agent-stage-OLD/a' '$o76Root/agent-stage-NEW/b'; touch -t $oldStamp '$o76Root/agent-stage-OLD'; find '$o76Root' -maxdepth 1 -type d -name 'agent-stage-*' -mtime +7 -exec rm -rf {} + ; ls -1 '$o76Root'"
$rc76 = Invoke-LocalBashCmd -bashPath $lb -cwd $env:TEMP -logFile $log76 -cmd $cmd76
$out76 = "$(Get-Content $log76 -Raw -ErrorAction SilentlyContinue)"
Assert-True "o76③(行为): 8 天前的被删、**刚刚的保留**（= 不误删在飞的；双向）" (
    $rc76 -eq 0 -and $out76 -match 'agent-stage-NEW' -and -not $out76.Contains('agent-stage-OLD'))
Remove-Item $log76 -ErrorAction SilentlyContinue
if (Test-Path ($o76Root -replace '/', '\')) { Remove-Item ($o76Root -replace '/', '\') -Recurse -Force -ErrorAction SilentlyContinue }

# --- O-77 (2026-09-26): 框架保留目录必须永远从 sync 排除（同站并发 tar race 的根因） ---
# 一手实测: 同站 3 张 readonly 卡并发 ⇒ 3/3 死在 sync（`tar: ./agent-out: file changed as we read it`）。
# ⚠ O-78② 把"补一个字面量"改成"取唯一真值常量" ⇒ 本组断言**随之改形**（旧断言查 `@('agent-out')`，已不存在）。
Assert-True "o77①: 唯一真值常量含 agent-out（框架保留目录不再散落各写一份）" (
    $codeOnlyFull.Contains("`$Script:FRAMEWORK_RESERVED_DIRS = @('out', '.golden', '.attach', 'agent-out', '.agentsync', '.git')"))
# ⚠ 顺序判据: 并入必须**发生在** Convert-ToExcludeArgs **之前** —— 否则清单算出来也不会进 tar 的 --exclude
#   （同族先例: D4 的"后缀定义必须早于第一个写点"）。
Assert-True "o77②: sync 并入的是**该常量**，且发生在 Convert-ToExcludeArgs 之前（否则不生效）" (
    $codeOnlyFull.Contains('$excl = @($excl) + $Script:FRAMEWORK_RESERVED_DIRS') -and
    $codeOnlyFull.IndexOf('$excl = @($excl) + $Script:FRAMEWORK_RESERVED_DIRS') -lt
    $codeOnlyFull.IndexOf('$exArgs = Convert-ToExcludeArgs $excl'))
# ⚠ 只看代码会漏掉这条: 本条要的正是**源码注释里必须存留的理由**（为什么写在代码而非各 proj 的 .agentsync）。
Assert-True "o77③: 源码里写明了『为什么写在代码而非载体 .agentsync』(版本控制内才是真值源)" (
    $content.Contains('修复必须落在版本控制内的真值源上') -and $content.Contains('file changed as we read it'))

# --- O-78 (2026-09-26): 并行面两处"说了等于没说" ---
# ① 排他拒绝的**文案**：实测（DEV-LOG-014 §40.6）3 个 **shared** run 在跑时，一张想取 exclusive 的卡被拒，
#    文案却写「已有**排他**派发在跑」⇒ 把持有者说错、把排障方向指反。修法 = 按事实说话 + 明说不可得。
Assert-True "o78①: 源码**不再**断言『已有排他派发在跑』（实测会说错持有者）" (
    -not $codeOnlyFull.Contains('已有**排他**派发在跑'))
Assert-True "o78①b: 拒绝分支改报**实际持有者**，且读不到时明确说不可得（不退回去猜）" (
    $codeOnlyFull.Contains('Format-WorkspaceLeaseHolder') -and
    $content.Contains('持有者**不可得**') -and
    $content.Contains('绝不退回去猜'))
Assert-True "o78①c: 租约获取时写 who 旁路（Windows 文件锁**没有元数据** ⇒ 只能靠旁路文件）" (
    $codeOnlyFull.Contains('Get-LeaseWhoPath') -and $codeOnlyFull.Contains('agent-cli-lease-') -and
    $codeOnlyFull.Contains('mode=$(if ($Exclusive) { ''exclusive'' } else { ''shared'' })'))
# ② 框架保留清单**合流为单一真值**：此前 sync 排除与站上 diff 过滤各写一份 ⇒ 各自漂移（O-77 就是这么踩的）。
Assert-True "o78②: 站上 diff 过滤的正则**从常量派生**，源码里不再留第二份字面量" (
    $codeOnlyFull.Contains('Get-FrameworkReservedDirRegex') -and
    $codeOnlyFull.Contains('Get-FrameworkReservedFileRegex') -and
    -not $codeOnlyFull.Contains("grep -v -E '^(out|"))
Assert-True "o78②b: 两条派生正则**确被站上 body 调用**（常量存在 ≠ 真用上了）" (
    $codeOnlyFull.Contains("grep -v -E '`$(Get-FrameworkReservedDirRegex)'") -and
    $codeOnlyFull.Contains("grep -v -E '`$(Get-FrameworkReservedFileRegex)'"))

# --- O-79 真根因 (2026-09-26): `Invoke-CappedSsh` 必须给子进程"空且立即关闭的 stdin" ---
# 一手 A/B/C（后台 job 上下文）: ① stdin 继承 ⇒ TIMEOUT 20s ② redirect+Close ⇒ 179ms ③ 裸 `ssh -n` ⇒ 179ms。
# ⚠ 这条缺陷能装一天没被发现, 是因为它**只在后台/批处理上下文**触发（交互上下文里 stdin 会 EOF）。
Assert-True "o79①: helper 重定向 stdin（否则 ssh 等 stdin EOF ⇒ 后台/批处理上下文每次必挂）" (
    $codeOnlyFull.Contains('$psi.RedirectStandardInput = $true'))
Assert-True "o79②: 启动后**立即** Close() 子进程 stdin（只设 redirect 不关 = 仍永不 EOF ⇒ 白设）" (
    $codeOnlyFull.Contains('$p.StandardInput.Close()'))
Assert-True "o79③: 三条对照证据留在源码里（继承=TIMEOUT / redirect+Close=179ms / 裸 ssh -n=179ms）" (
    $content.Contains('stdin 继承** ⇒ **TIMEOUT 20s') -and $content.Contains('裸 `ssh -n`'))
Assert-True "o79④: 写明『为什么单发测不出来』（交互上下文 stdin 会 EOF；后台/批处理才触发）" (
    $content.Contains('为什么单发时测不出来') -and $content.Contains('每次必挂'))

# --- O-80 (2026-09-26): 批次派发入口（"多张不同卡并发"）—— 落档见 DEV-LOG-014 §42 ---
Assert-True "o80①: 有 batch verb 且落在既有 `$Command` 派发链里 + 进 usage 文本" (
    $codeOnlyFull.Contains("`$Command -eq 'batch'") -and
    $codeOnlyFull.Contains('agent-cli batch <proj> --card <清单文件>'))
# ⚠ 措辞就地更正（§42.7 ② 原写"子进程必须 redirect stdin+Close"）: 实际选型 = **Start-Job + 原生调用**,
#   **不自起 ProcessStartInfo** ⇒ 子进程 stdin 由 shell 正常处理、ssh 的 stdin 由 `Invoke-CappedSsh`（O-79 修好）承担。
#   ⇒ 判据改成: 用 Start-Job 机制 + 源码写明"不在本层重复造一遍"（重复造 = 两处真值）。
Assert-True "o80②: batch 用 Start-Job 机制, 且源码写明『不在本层重复造 stdin 处理』" (
    $codeOnlyFull.Contains('Start-Job -ScriptBlock') -and $content.Contains('不在本层重复造一遍'))
Assert-True "o80③: 输出落日志文件（源码写明不用 OS 管道收集, 防缓冲死锁）" (
    $codeOnlyFull.Contains('_batch\') -and $content.Contains('不用 OS 管道收集'))
Assert-True "o80④: 每站默认并发 1（v1 只跨站并行）" (
    $codeOnlyFull.Contains('$Script:BATCH_PER_STATION = 1'))
Assert-True "o80⑤: 单卡墙钟默认 2400s, 且超时**显式记为未完成**（绝不静默）" (
    $codeOnlyFull.Contains('$Script:BATCH_TIMEOUT_S = 2400') -and $content.Contains('显式记为未完成'))
Assert-True "o80⑥: 三条硬约束写在源码里（ADR-0004 不加脚本 / param 块加不了参数 / env 桥是权宜）" (
    $content.Contains('ADR-0004') -and $content.Contains('加不了新参数') -and $content.Contains('权宜, 不是设计偏好'))
Assert-True "o80⑦: >1 每站并发**显式拒绝**（不许静默按 1 跑）+ 说明『计划==现实』的钉站理由" (
    $codeOnlyFull.Contains('BATCH_ABORT: AGENT_BATCH_PER_STATION=') -and $content.Contains('plan == reality'))
# v1.1（2026-09-26）：清单新增逐卡附件 `attach=`（D7-P0 三卡都要输入摘要 ⇒ 无它就只能单张跑）
Assert-True "o80⑧: 清单支持逐卡附件 `attach=`（解析 + 缺失 fail-fast + 传绝对路径进 -Attach）" (
    $codeOnlyFull.Contains("'^(?i)attach=(.+)$'") -and $codeOnlyFull.Contains("'ATTACH_NOT_FOUND'") -and
    $codeOnlyFull.Contains('$h.Attach = @($c.attachAbs)'))
# ★ 2026-09-26 检查时发现的自伤: 汇总声称"以 runDir 为真值", 但文件名写成 `run.json`（**该文件永不存在**）
#   ⇒ Test-Path 恒假 ⇒ **静默回落到日志**。真值源是 **`.agent-run.json`**（有点前缀，含 exit_code/status/accept）。
Assert-True "o80⑨: 汇总从 **`.agent-run.json`** 读真值（不是 `run.json`）+ 回落时显式标来源" (
    $codeOnlyFull.Contains("'.agent-run.json'") -and -not $codeOnlyFull.Contains("Join-Path `$runDir 'run.json'") -and
    $codeOnlyFull.Contains("`$exitSrc = 'log'") -and $codeOnlyFull.Contains('src={5}'))
# ★ 2026-09-26 补：**标签也必须是真名**。上一版只判了"读哪"（路径），没判"说读了哪"（标签）
#   ⇒ 实测汇总里打出 `src=run.json`（而实际读的是 `.agent-run.json`）= **标签在说谎**，
#     与 O-81 是同一件事的下一层（上次错在读的文件名、这次错在对外声明的文件名）。
Assert-True "o80⑨b: `src=` 打出的**标签**也必须是真名（读对了但说错，仍是'没读到'的同族）" (
    -not $codeOnlyFull.Contains("`$exitSrc = 'run.json'") -and
    $codeOnlyFull.Contains("`$exitSrc = '.agent-run.json'"))
# ★ O-116（2026-09-29）: 汇总**逐卡取值必须限定在"本卡的块"内** —— 站级日志是"多卡**顺序追加**"
#   （同站串行 ⇒ 一个 log 文件里 N 张卡首尾相接）。在**整站**日志里取 `TASK_DONE`/`RUNSTAMP` 的末行
#   ⇒ **每张卡都拿到末卡的值** ⇒ 用**末卡**的 runDir 读 `.agent-run.json` ⇒ 覆盖逐卡 rc。
#   一手实证（本批 3 卡同钉 B）：`xrev2` 真 `rc=1` / 站级日志 `TASK_RC=9` / 产物缺失，
#   而官方汇总三行**同一个 runDir**（末卡 `xrev3` 的）+ `exit=0` + `BATCH_DONE: 失败或未完成=0`
#   ⇒ 这不是"读数偏差"，是**判决级假绿**（失败被报成成功）。同族 = O-57（跨 run 证据错配）。
Assert-True "o80⑩: 汇总**先按卡切块**（块首 = 子进程写的 marker `=== CARD <卡> rc=<rc> ===`）" (
    $codeOnlyFull.Contains("^=== CARD (.+) rc=.* ===") -and $codeOnlyFull.Contains('$blocks'))
# ⚠ 两条合起来才非空转：⑩b 单独被"删掉整个取值段"满足（那是不算）⇒ ⑩c 必须证明"改成从块里取"
Assert-True "o80⑩b: `TASK_DONE`/`RUNSTAMP` **不再取自整站 `$txt`**（整站取末行 = 每卡拿到末卡的值）" (
    -not $codeOnlyFull.Contains('$txt | Where-Object { "$_" -like ''*TASK_DONE dir=*'' }') -and
    -not $codeOnlyFull.Contains('$txt | Where-Object { "$_" -like ''*RUNSTAMP:*'' }'))
Assert-True "o80⑩c: 两者**取自本卡的块**（`$clines`），且按卡取块是「取最后一个」（同卡重复行时以末次为准）" (
    $codeOnlyFull.Contains('$clines | Where-Object { "$_" -like ''*TASK_DONE dir=*'' }') -and
    $codeOnlyFull.Contains('$clines | Where-Object { "$_" -like ''*RUNSTAMP:*'' }') -and
    $codeOnlyFull.Contains('$blocks | Where-Object { $_.card -eq $c.card } | Select-Object -Last 1'))

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

# --- O-90（2026-09-26）: **流程前置** —— 门禁未过 ⇒ 拒绝派发 ---
# 为什么必须在这里测: 派发路径改动的**唯一离线验证面**是本夹具（真派发要站）。
# 判据本体刻意拆成纯函数（Test-GateSummaryOk / Resolve-GateCommand）正是为了能在这里跑。

# ① 真表非空 + 值真的是命令（防"表空了 ⇒ 判据恒不命中"= 判据什么都没判）
Assert-True "o90①: GATE_TABLE 非空且 rpc-check 映射到真命令（实测 $(@($Script:GATE_TABLE.Keys) -join '|')）" (
    @($Script:GATE_TABLE.Keys).Count -ge 2 -and (Resolve-GateCommand 'rpc-check') -match 'rpc_check\.py')

# ② 未登记 / 空名 ⇒ **fail-closed 返回 $null**（不猜、不放过）
Assert-True "o90②: 未登记门禁名 ⇒ `$null（fail-closed，不猜）" (
    $null -eq (Resolve-GateCommand 'no-such-gate') -and $null -eq (Resolve-GateCommand ''))

# ③ 汇总行判据（正例）
$gOk = Test-GateSummaryOk "扫描 239 个 md`n结论: PASS · 绿灯 31 · 黄灯 2 · 红灯 0"
Assert-True "o90③: 有汇总行 ⇒ ok（line=$($gOk.line)）" ($gOk.ok -and $gOk.line -match '结论: PASS')

# ④ ★★ **exit 0 但无汇总行 ⇒ 必须不 ok** —— 这就是 O-89 的判据化，
#    也正是本机制与参考实现（Spec_Runner 只看 exit code）的**分野**。
$gNo = Test-GateSummaryOk "  ok   test_a`n  ok   test_b"
Assert-True "o90④: **无汇总行 ⇒ 不 ok**（exit 0 也可能一条断言都没跑）" (
    (-not $gNo.ok) -and $gNo.reason -match '无汇总行')

# ⑤ 空 / 纯空白输出 ⇒ 不 ok（防"空输出被当成通过"）
Assert-True "o90⑤: 空输出与纯空白 ⇒ 不 ok" (
    (-not (Test-GateSummaryOk '').ok) -and (-not (Test-GateSummaryOk "  `n `t ").ok))

# ⑥ ★ **先验红**：一个"只看 exit code"的桩会放过 ④ 那条 ⇒ 证明真判据不是恒真
$naiveGate = { param($text, $code) ($code -eq 0) }
Assert-True "o90⑥(先验红): 只看 exit code 的桩放过 ④ ⇒ 真判据不是恒真" (
    (& $naiveGate "  ok   test_a" 0) -and (-not (Test-GateSummaryOk "  ok   test_a").ok))

# ⑦ ★★ **白名单护栏（行为级）**：卡写 `require-gate:` 必须**真被解析出来**。
#    ⚠ `Get-FrontMatter` 是**白名单解析**（未知键静默丢弃）⇒ 漏登记会让这条纪律
#      "**看起来写了、其实没人读**"（= 假防线，O-81 同族）⇒ 故这里**真跑解析**，不是扫文本。
$rgCard = Join-Path $tmpCards 'o90-require-gate.md'
[System.IO.File]::WriteAllText($rgCard, "---`nproj: dogfood`ntask: t`nrequire-gate: rpc-check`n---`n`nbody`n", [System.Text.UTF8Encoding]::new($false))
$rgFm = Get-FrontMatter $rgCard
Assert-True "o90⑦: 卡的 require-gate **真被解析**（白名单已登记）" ([string]$rgFm['require-gate'] -eq 'rpc-check')
$rgCard2 = Join-Path $tmpCards 'o90-no-gate.md'
[System.IO.File]::WriteAllText($rgCard2, "---`nproj: dogfood`ntask: t`n---`n`nbody`n", [System.Text.UTF8Encoding]::new($false))
$rgFm2 = Get-FrontMatter $rgCard2
Assert-True "o90⑦b(反向): 未声明 ⇒ 空串 = **不要求**（存量卡行为不变，向后兼容）" ([string]$rgFm2['require-gate'] -eq '')

# ⑧ 接线：派发入口必须**真的调用**它，且失败**真的拒发**
Assert-True "o90⑧: Invoke-Task 接线（调 Invoke-GateCheck 且失败 return 3）" (
    $content -match 'Invoke-GateCheck -Name \$reqGate' -and $content -match 'return 3 \}\s+# 3 = GATE_BLOCK')
Assert-True "o90⑨: 批量侧逐项接线（fail-fast ⇒ 该行标 GATE_BLOCK，不整批崩）" (
    $content -match '\$rgB -and -not \(Invoke-GateCheck' -and $content -match "\`$err = 'GATE_BLOCK'")

# ═══════════════════════════════════════════════════════════════════════════════
# O-92（2026-09-26）：**双盲重推导** —— 判据在三个纯函数里，这里**真跑**它们（不是扫文本）。
# 为什么：主评审模板带 `{{PRODUCT}}` ⇒ "原推理里的跳步会被它再走一遍"（锚定效应）
#   ⇒ 形态 III（**把两件事说成一件**）**结构性拦不住**。盲判 = 只给「源 + 命题」，让 judge 独立重推。
# ⚠ 本组最值钱的是 ③④（**不得泄漏原链 / 原产物**）：盲判若把 claimed chain 递过去，等于**没盲**。
# ═══════════════════════════════════════════════════════════════════════════════
function O92-Doc([string]$json) { "产物正文 SENTINEL_PRODUCT_PROSE`n`n" + '```assertions' + "`n" + $json + "`n" + '```' + "`n" }

# ⓪ `Read-ReviewResource` 依赖 `$Script:REVIEW_DIR`（`agent-cli.ps1` 里它 = `Join-Path $PSScriptRoot 'review'`）。
# ★★ 实测机制（本批踩到，记下来防下次再撞）：**`$PSScriptRoot` 在 `Invoke-Expression` 的子作用域里取不到**
#   ⇒ 直接提取那条赋值会抛 `Cannot bind argument to parameter 'Path' because it is an empty string`，
#   **且报错指向 `Invoke-Expression` 那一行**（不指向赋值本身）⇒ 极易误判成"AST 没找到"。
#   实测对照：同一句 `Join-Path $PSScriptRoot 'review'` **直接求值正常**、包进 `Invoke-Expression` 即抛错。
# ⇒ 这里用**夹具自己的位置**（与 agent-cli.ps1 同目录 ⇒ 指向同一个真资源目录），并**断言该目录真的可用**。
$Script:REVIEW_DIR = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'review'
Assert-True "o92⓪: 评审资源目录可得（盲判模板真存在）——否则后面的断言会以误导形式失败" (
    (Test-Path (Join-Path $Script:REVIEW_DIR 'judge-prompt-blind.tmpl')))
$o92Good = O92-Doc '[ {"id":"B1","conclusion":"站点数为 3","op":"counting","chain":["列出三站","数一遍得 3"],"sources":["inventory/cluster.yaml"]}, {"id":"B2","conclusion":"门禁与实现同一份代码","op":"equivalence","chain":["读门禁","读实现","比对通过"],"sources":["ops/rpc_check.py"]} ]'
$o92Ab = Get-AssertionBlock $o92Good

# ① 正例：真解析（2 条命题）—— ⚠ 名字里带 `reason`，失败时**当场看到原因**（不必再复现）
Assert-True "o92①: Get-AssertionBlock 正例（真解析出 2 条命题）[ok=$($o92Ab.ok) reason=$($o92Ab.reason)]" (
    $o92Ab['ok'] -and @($o92Ab['assertions']).Count -eq 2)

# ①b ★★ 回归护栏：**单条**也必须 ok。
#    ⚠ 本批真踩过：PS 5.1 的 `ConvertFrom-Json` 把顶层数组当**一个对象**发出 ⇒ 写成 `@($j | ConvertFrom-Json)`
#      会得到 **1 个元素（=整个数组）**，`$a.id` 走成员枚举返回 "B1 B2"、`$a.op` 返回 "counting equivalence"
#      ⇒ **1 条能过、2 条必红**（一个"看起来在工作"的解析器）。这条与 ① 成对，专门钉住那个不对称。
$o92One = Get-AssertionBlock (O92-Doc '[ {"id":"B1","conclusion":"只有一条","op":"counting","chain":["a"]} ]')
Assert-True "o92①b: **单条**断言也必须 ok（防「1 条过、2 条红」的不对称）[ok=$($o92One.ok) reason=$($o92One.reason)]" (
    $o92One['ok'] -and @($o92One['assertions']).Count -eq 1)

# ② 反例族：**每一类都必须不可用**（fail-closed —— 块不在 / 空 / op 越界 / 缺 chain）
Assert-True 'o92②: 无 ```assertions 块 ⇒ 不可用' (-not (Get-AssertionBlock "正文里没有那个块").ok)
Assert-True "o92②b: 空数组 ⇒ 不可用（防'块在但没内容'被当通过）" (-not (Get-AssertionBlock (O92-Doc '[]')).ok)
$o92OpBad = Get-AssertionBlock (O92-Doc '[ {"id":"B1","conclusion":"x","op":"我觉得","chain":["a"]} ]')
Assert-True "o92②c: op 不在**封闭枚举** ⇒ 不可用（否则枚举形同虚设）" (
    (-not $o92OpBad.ok) -and $o92OpBad.reason -match '封闭枚举')
$o92ChBad = Get-AssertionBlock (O92-Doc '[ {"id":"B1","conclusion":"x","op":"counting"} ]')
Assert-True "o92②d: 缺 chain ⇒ 不可用（没有链就没法做步数对照）" (
    (-not $o92ChBad.ok) -and $o92ChBad.reason -match 'chain')

# ③ ★★ 泄漏护栏：盲判提示词含**命题**，但**不含原链任一步**
$o92Fm = @{ task = 't'; body = '源材料正文' }
$o92Prompt = Build-BlindPrompt -fm $o92Fm -assertions $o92Ab['assertions'] -runId 'r-o92'
Assert-True "o92③: 盲判提示词含**命题**但**不含**原链任一步（否则=没盲）" (
    $o92Prompt.Contains('站点数为 3') -and
    -not $o92Prompt.Contains('列出三站') -and -not $o92Prompt.Contains('数一遍得 3') -and
    -not $o92Prompt.Contains('比对通过'))

# ④ ★ 盲判提示词**不含产物正文**（哨兵）且**不含 `{{PRODUCT}}` 占位符**
Assert-True "o92④: 不含产物正文（哨兵）且不含 `{{PRODUCT}}`（真读真模板，非扫文本）" (
    -not $o92Prompt.Contains('SENTINEL_PRODUCT_PROSE') -and -not $o92Prompt.Contains('{{PRODUCT}}'))
Assert-True "o92④b: 其余占位符**都已被替换**（防'新模板少填一个变量'静默漏）" (
    -not ($o92Prompt -match '\{\{[A-Z_]+\}\}'))

# ⑤ Compare-AssertionChains 五态（★ 结论一致∧步数相同 = MATCH）
#   ⚠ 观测值打进退化名 ⇒ 失败时**当场看到实际状态**（与 ① 同一手法）。
$o92C0 = @($o92Ab['assertions'])[0]
$o92Same = @(Compare-AssertionChains -claimed @($o92C0) -blind @(@{ id = 'B1'; verdict = 'TRUE'; chain = @('a', 'b'); key_reason = 'k' }))
Assert-True "o92⑤: 结论一致 ∧ 步数相同 ⇒ **MATCH** [n=$($o92Same.Count) state0=$($o92Same[0].state)]" (
    $o92Same.Count -eq 1 -and $o92Same[0].state -eq 'MATCH')
$o92Gap = @(Compare-AssertionChains -claimed @($o92C0) -blind @(@{ id = 'B1'; verdict = 'TRUE'; chain = @('a'); key_reason = 'k' }))
Assert-True "o92⑤b: 结论一致 ∧ 步数不同 ⇒ **STEP_GAP_OPEN**（机器**不**闭合）[state0=$($o92Gap[0].state)]" (
    $o92Gap[0].state -eq 'STEP_GAP_OPEN')
$o92Fal = @(Compare-AssertionChains -claimed @($o92C0) -blind @(@{ id = 'B1'; verdict = 'FALSE'; chain = @('a'); key_reason = '反证' }))
Assert-True "o92⑤c: 盲判 FALSE ⇒ **CONFLICT**（必须仲裁）[state0=$($o92Fal[0].state)]" (
    $o92Fal[0].state -eq 'CONFLICT')
$o92NoP = @(Compare-AssertionChains -claimed @($o92C0) -blind @(@{ id = 'B9'; verdict = 'TRUE'; chain = @('a') }))
Assert-True "o92⑤d: 盲判没返回该条 ⇒ **NO_PROBE**（**不算通过**）[state0=$($o92NoP[0].state)]" (
    $o92NoP[0].state -eq 'NO_PROBE')
$o92Unc = @(Compare-AssertionChains -claimed @($o92C0) -blind @(@{ id = 'B1'; verdict = 'UNCERTAIN'; chain = @(); key_reason = '依据不足' }))
Assert-True "o92⑤e: 盲判 UNCERTAIN ⇒ **UNCERTAIN**（诚实优先，不算通过）[state0=$($o92Unc[0].state)]" (
    $o92Unc[0].state -eq 'UNCERTAIN')

# ⑥ ★★ **机器不产出 CLOSED**（写成正向断言，防日后有人"顺手补上"）
$o92All = @()
foreach ($bl in @(@{ id = 'B1'; verdict = 'TRUE'; chain = @('a', 'b') }, @{ id = 'B1'; verdict = 'TRUE'; chain = @('a') },
                   @{ id = 'B1'; verdict = 'FALSE'; chain = @('a') }, @{ id = 'B9'; verdict = 'TRUE'; chain = @('a') },
                   @{ id = 'B1'; verdict = 'UNCERTAIN'; chain = @() })) {
    $o92All += @(Compare-AssertionChains -claimed @($o92C0) -blind @($bl))
}
Assert-True "o92⑥: 状态集内**永不出现** STEP_GAP_CLOSED（差额步无法机器闭合）" (
    -not (@($o92All | ForEach-Object { $_.state }) -contains 'STEP_GAP_CLOSED'))
Assert-True "o92⑥b: **源码里也**没把它写成产物（防注释与实现不符）" (
    -not $codeOnlyFull.Contains('STEP_GAP_CLOSED'))

# ⑦ **不静默**：三条"没跑成"的路径都必须**显式落状态**（O-89 同族：静默 = 假绿）
Assert-True "o92⑦: SKIPPED / REJECT / UNPARSEABLE 三条路径都**显式落状态**" (
    $content -match "status = 'SKIPPED'" -and $content -match "status = 'REJECT'" -and
    $content -match "status = 'UNPARSEABLE'")

# ⑧ 白名单（行为级）：卡写 `review-blind: true` **真被解析**；未声明 ⇒ false（向后兼容）
$rbCard = Join-Path $tmpCards 'o92-review-blind.md'
[System.IO.File]::WriteAllText($rbCard, "---`nproj: dogfood`ntask: t`nreview-blind: true`n---`n`nbody`n", [System.Text.UTF8Encoding]::new($false))
Assert-True "o92⑧: 卡的 review-blind **真被解析**（白名单已登记）" (
    (Get-FrontMatter $rbCard)['review-blind'] -eq 'true')
$rbCard2 = Join-Path $tmpCards 'o92-no-blind.md'
[System.IO.File]::WriteAllText($rbCard2, "---`nproj: dogfood`ntask: t`n---`n`nbody`n", [System.Text.UTF8Encoding]::new($false))
Assert-True "o92⑧b(反向): 未声明 ⇒ 'false' = **不跑盲判**（存量卡行为不变）" (
    (Get-FrontMatter $rbCard2)['review-blind'] -eq 'false')

# ⑨ 接线：`Invoke-Review` 真的调用纯函数、真的由卡面门控、真的把结果写进 review
Assert-True "o92⑨: 接线（取命题 + 对照 + 写 `blind` 段）" (
    $content -match 'Get-AssertionBlock \$productText' -and
    $content -match 'Compare-AssertionChains -claimed \$ab\[' -and
    $content -match "\`$review\['blind'\] = \`$blindSection")
Assert-True "o92⑨b: **默认关**（门控用卡面值，不是「一上来就跑两次」）" (
    $content -match "\[string\]\`$fm\['review-blind'\] -eq 'true'")
Assert-True "o92⑨c: 盲判提示词**与主判同规矩**出网（过 Resolve-ReviewPrompt，不绕门面）" (
    $content -match 'Resolve-ReviewPrompt -prompt \$blindPrompt')
Assert-True "o92⑨d: `blind` 段**仅在跑过时**才加（关掉开关时 review.json schema 不变）" (
    $content -match "if \(\`$blindSection\) \{ \`$review\['blind'\] = \`$blindSection \}")

# ⑩ D7-P2-1（2026-09-26）：**机械门先行 —— L1 全绿才允许进 L2**
# 为什么要有这组：此前 `Invoke-Review` 只看产物、不读 run 记录 ⇒ "accept 红/没跑"的 run 也能被打出
#   语义结论并**与机械面并列呈现**。判定是本组上方提取的**纯函数** `Resolve-L1Gate`。
$l1g = Resolve-L1Gate -Record (@{ status = 'completed'; exit_code = 0; accept = @{ passed = $true } })
Assert-True "l1-1 全绿（卡无金标）⇒ ok + green" ($l1g['ok'] -and $l1g['verdict'] -eq 'green')
$l1g2 = Resolve-L1Gate -Record (@{ status = 'completed'; exit_code = 0; accept = @{ passed = $true };
                                   accept_golden = @{ passed = $true } })
Assert-True "l1-2 金标启用且过 ⇒ green" ($l1g2['ok'] -and $l1g2['verdict'] -eq 'green')
$l1gf = Resolve-L1Gate -Record (@{ status = 'completed'; exit_code = 0; accept = @{ passed = $true };
                                   accept_golden = @{ passed = $false } })
Assert-True "l1-3 金标红 ⇒ 拒（red，reason 点名 golden）" (
    (-not $l1gf['ok']) -and $l1gf['verdict'] -eq 'red' -and $l1gf['reason'] -match 'golden=FAIL')
$l1af = Resolve-L1Gate -Record (@{ status = 'completed'; exit_code = 0; accept = @{ passed = $false } })
Assert-True "l1-4 accept 红 ⇒ 拒（reason 点名 accept）" (
    (-not $l1af['ok']) -and $l1af['reason'] -match 'accept=FAIL')
$l1st = Resolve-L1Gate -Record (@{ status = 'failed'; exit_code = 1; accept = @{ passed = $true } })
Assert-True "l1-5 status != completed ⇒ 拒（reason 带 status 值）" (
    (-not $l1st['ok']) -and $l1st['reason'] -match 'status=failed')
Assert-True "l1-6 ★**金标未启用（键缺）不是红**（防假红：把'没这道门'读成'这道门红了'）" (
    (Resolve-L1Gate -Record (@{ status = 'completed'; exit_code = 0; accept = @{ passed = $true } }))['verdict'] -eq 'green')
$l1nr = Resolve-L1Gate -Record $null
Assert-True "l1-7 记录缺 ⇒ unknown + 拒（读不到 != 已通过）" (
    (-not $l1nr['ok']) -and $l1nr['verdict'] -eq 'unknown' -and $l1nr['reason'] -eq 'NO_RECORD')
Assert-True "l1-8 status 空 ⇒ unknown" (
    (Resolve-L1Gate -Record (@{ accept = @{ passed = $true } }))['verdict'] -eq 'unknown')
Assert-True "l1-9 accept 键缺 ⇒ unknown（不可当'不适用=通过'）" (
    (Resolve-L1Gate -Record (@{ status = 'completed' }))['verdict'] -eq 'unknown')
$l1al = Resolve-L1Gate -Record (@{ status = 'failed'; exit_code = 1; accept = @{ passed = $false } }) -AllowRed
Assert-True "l1-10 显式 AllowRed ⇒ 放行但 **verdict 仍 red**（降级 != 隐藏）" (
    $l1al['ok'] -and $l1al['verdict'] -eq 'red')
Assert-True "l1-11 放行时 facts 仍如实带 status/exit_code（结论永远带标签）" (
    $l1al['facts']['status'] -eq 'failed' -and $l1al['facts']['exit_code'] -eq 1)
# ── 接线（防"写了但没跑"）──
Assert-True "l1-12 接线：L2 里真过了 L1 门（拒 ⇒ return 5）" (
    $content -match 'Resolve-L1Gate -Record \$l1Record -AllowRed:\$allowL1Red' -and
    $content -match 'return 5')
Assert-True "l1-13 接线：L1 门在**读产物之前**（红就不把产物送出去判）" (
    $content.IndexOf('Resolve-L1Gate -Record $l1Record') -lt
    $content.IndexOf('$productText = [System.IO.File]::ReadAllText($product'))
Assert-True "l1-14 L1 事实写进 review.json（**两处**写点都带 ⇒ 判官失败也留档）" (
    ([regex]::Matches($content, "\`$review\['l1'\] = \`$l1Section")).Count -ge 2)
Assert-True "l1-15 **L2 无权改写可机判**：review 自带 run 记录摘要（事后可验）" (
    $content -match 'record_sha256 = "sha256:\$l1RecSha"')
$fnRev = @($fns) | Where-Object { $_.Name -eq 'Invoke-Review' } | Select-Object -First 1
Assert-True "l1-16 ★**结构护栏**：`Invoke-Review` 函数体内**没有**对 `.agent-run.json` 的写" (
    $null -ne $fnRev -and -not ($fnRev.Extent.Text -match 'Set-Content[^\r\n]*\.agent-run\.json'))
Assert-True "l1-17 卡面/命令行有**显式放行通道**（不是偷偷放行）" (
    $content -match '\[switch\]\$allowL1Red' -and $content -match '--allow-l1-red')

# ⑪ D7-P2-2（2026-09-26）：**结论契约** —— `Test-FindingShape` / `Test-ConclusionContract` / `Merge-JudgeFindings`
# ★ 每条判据都配一个**能把它打红的反例**（防"恒真判据"= D7-P2-3 的最小可用形态）。
$fOK = @{ id = 'F1'; statement = 'x'; hit = $true; priority = 3; confidence = 0.8;
          path = 'ops/a.py'; line_range = 'L10-L20' }
Assert-True "cc-1 合法 finding ⇒ ok" ((Test-FindingShape -Finding $fOK)['ok'])
Assert-True "cc-2 单行 `L7` 合法" (
    (Test-FindingShape -Finding (@{ statement = 's'; hit = $false; priority = 0; confidence = 0.0;
                                    path = 'a'; line_range = 'L7' }))['ok'])
Assert-True "cc-3 `L7-`（开放区间）合法" (
    (Test-FindingShape -Finding (@{ statement = 's'; hit = $false; priority = 1; confidence = 1.0;
                                    path = 'a'; line_range = 'L7-' }))['ok'])
Assert-True "cc-4 缺 path ⇒ NO_PATH" (
    (Test-FindingShape -Finding (@{ statement = 's'; hit = $true; priority = 1; confidence = 0.5;
                                    path = ''; line_range = 'L1' }))['reasons'] -contains 'NO_PATH')
Assert-True "cc-5 `line_range` 形态错（120-134）⇒ BAD_LINE_RANGE" (
    (Test-FindingShape -Finding (@{ statement = 's'; hit = $true; priority = 1; confidence = 0.5;
                                    path = 'a'; line_range = '120-134' }))['reasons'] -match 'BAD_LINE_RANGE')
Assert-True "cc-6 priority 小数 ⇒ PRIORITY_NOT_INT（浮点 priority 会让排序'看起来有区别'）" (
    (Test-FindingShape -Finding (@{ statement = 's'; hit = $true; priority = 3.5; confidence = 0.5;
                                    path = 'a'; line_range = 'L1' }))['reasons'] -contains 'PRIORITY_NOT_INT')
Assert-True "cc-7 priority 负 ⇒ PRIORITY_NEGATIVE" (
    (Test-FindingShape -Finding (@{ statement = 's'; hit = $true; priority = -1; confidence = 0.5;
                                    path = 'a'; line_range = 'L1' }))['reasons'] -match 'PRIORITY_NEGATIVE')
Assert-True "cc-8 confidence 越界 1.5 ⇒ OUT_OF_RANGE" (
    (Test-FindingShape -Finding (@{ statement = 's'; hit = $true; priority = 1; confidence = 1.5;
                                    path = 'a'; line_range = 'L1' }))['reasons'] -match 'CONFIDENCE_OUT_OF_RANGE')
Assert-True "cc-9 confidence 不是数（'high'）⇒ NOT_NUMBER" (
    (Test-FindingShape -Finding (@{ statement = 's'; hit = $true; priority = 1; confidence = 'high';
                                    path = 'a'; line_range = 'L1' }))['reasons'] -contains 'CONFIDENCE_NOT_NUMBER')
Assert-True "cc-10 hit 不是布尔（'yes'）⇒ HIT_NOT_BOOL" (
    (Test-FindingShape -Finding (@{ statement = 's'; hit = 'yes'; priority = 1; confidence = 0.5;
                                    path = 'a'; line_range = 'L1' }))['reasons'] -contains 'HIT_NOT_BOOL')
Assert-True "cc-11 ★**判官自报 agreement ⇒ 拒**（自证；分类只能由综合器算）" (
    (Test-FindingShape -Finding (@{ statement = 's'; hit = $true; priority = 1; confidence = 0.5;
                                    path = 'a'; line_range = 'L1'; agreement = 'consensus' }))['reasons'] -contains 'AGREEMENT_SELF_REPORTED')
Assert-True "cc-12 statement 空 ⇒ NO_STATEMENT" (
    (Test-FindingShape -Finding (@{ statement = ' '; hit = $true; priority = 1; confidence = 0.5;
                                    path = 'a'; line_range = 'L1' }))['reasons'] -contains 'NO_STATEMENT')
$ccGood = Test-ConclusionContract -Verdict 'revise' -Findings @($fOK)
Assert-True "cc-13 整体：合法 verdict + 合法 findings ⇒ ok" ($ccGood['ok'] -and $ccGood['count'] -eq 1)
Assert-True "cc-14 自造 verdict（looks-good）⇒ BAD_VERDICT" (
    (Test-ConclusionContract -Verdict 'looks-good' -Findings @())['reasons'] -match 'BAD_VERDICT')
Assert-True "cc-15 findings 空 ⇒ **合法**（但 count=0 被显式报出，不是'没问题'）" (
    (Test-ConclusionContract -Verdict 'accept' -Findings @())['ok'] -and
    (Test-ConclusionContract -Verdict 'accept' -Findings @())['count'] -eq 0)
Assert-True "cc-16 一条坏 ⇒ 整体 reason **点名序位**" (
    (Test-ConclusionContract -Verdict 'accept' -Findings @($fOK, @{ statement = ''; hit = $true;
        priority = 1; confidence = 0.5; path = 'a'; line_range = 'L1' }))['reasons'] -match '#1:')
# ── 综合（N 判官 ⇒ 三分类）──
$jA = @{ findings = @(@{ statement = 'a'; hit = $true; priority = 1; confidence = 0.5; path = 'p'; line_range = 'L1' }) }
$jB = @{ findings = @(@{ statement = 'b'; hit = $true; priority = 2; confidence = 0.6; path = 'p'; line_range = 'L1' }) }
$jC = @{ findings = @(@{ statement = 'c'; hit = $false; priority = 3; confidence = 0.7; path = 'p'; line_range = 'L1' }) }
$m1 = Merge-JudgeFindings -Verdicts @($jA)
Assert-True "cc-17 ★单判官 ⇒ **只可能 unique** 且显式报 judges=1" (
    $m1['judges'] -eq 1 -and $m1['findings'].Count -eq 1 -and $m1['findings'][0]['agreement'] -eq 'unique')
$m2 = Merge-JudgeFindings -Verdicts @($jA, $jB)
Assert-True "cc-18 两判官 · 同锚点 · 同 hit ⇒ consensus（措辞不同不影响对齐）" (
    $m2['findings'][0]['agreement'] -eq 'consensus' -and $m2['findings'][0]['judges'] -eq 2)
$m3 = Merge-JudgeFindings -Verdicts @($jA, $jC)
Assert-True "cc-19 两判官 · 同锚点 · hit 相反 ⇒ disagreement" (
    $m3['findings'][0]['agreement'] -eq 'disagreement')
$jD = @{ findings = @(@{ statement = 'd'; hit = $true; priority = 1; confidence = 0.5; path = 'q'; line_range = 'L9' }) }
$m4 = Merge-JudgeFindings -Verdicts @($jA, $jD)
Assert-True "cc-20 两判官 · 不同锚点 ⇒ 两条各自 unique" (
    @($m4['findings'] | Where-Object { $_['agreement'] -eq 'unique' }).Count -eq 2)
$m5 = Merge-JudgeFindings -Verdicts @(@{ findings = @() }, @{ findings = @() })
Assert-True "cc-21 ★**空集不产共识**：opinions=0 且 findings 空（0/0 不许读成'没问题'）" (
    $m5['opinions'] -eq 0 -and @($m5['findings']).Count -eq 0)
Assert-True "cc-22 判官数为 0（null 输入）⇒ judges=0（规模显式）" (
    (Merge-JudgeFindings -Verdicts @($null))['judges'] -eq 0)
Assert-True "cc-23 综合结果**带规模**（judges 与 opinions 都在）" (
    ($m2.Contains('judges')) -and ($m2.Contains('opinions')))
# ── 接线（防"写了但没跑"）──
Assert-True "cc-24 接线：review.json 写契约段（**两处**写点都带）" (
    ([regex]::Matches($content, "\`$review\['contract'\] = \`$ccSection")).Count -ge 2)
Assert-True "cc-25 接线：契约段由**校验器 + 综合器**共同产出" (
    $content -match 'Test-ConclusionContract -Verdict \(\[string\]\$judgeObj\.verdict\)' -and
    $content -match 'merged = \(Merge-JudgeFindings -Verdicts @\(\$judgeObj\)\)')
# ⚠ 必须用 UTF-8 **显式**读模板：PS 5.1 的 `Get-Content` 默认按系统 ANSI(GBK) 解码 ⇒ 中文会乱码
#   ⇒ 对中文关键字做正则会**假红**（本夹具顶部记过同族坑）。
$ccTmpl = [System.IO.File]::ReadAllText((Join-Path (Split-Path $cli) 'review\judge-prompt.tmpl'),
                                        [System.Text.UTF8Encoding]::new($false))
Assert-True "cc-26 提示词模板**明确禁止**判官自报分类" ($ccTmpl -match '禁止输出 `agreement`')
Assert-True "cc-27 提示词模板要求 `path`/`line_range` 必填" (
    $ccTmpl -match 'line_range' -and $ccTmpl -match '必填')
# ⑪b D7-CC **#8 + #3**（2026-09-30 裁 / O-123）：判官**取哪件产物** + **注入产物相对名**（`path` 相对根 = runDir）
# ★ `Resolve-ReviewProduct` 的 `-Exists` **可注入** ⇒ 下列断言**离线真跑**（不碰文件系统、不发请求）。
# ⚠ 注入的存在性判据按**叶名**判（`Join-Path` 在 Windows 上产出 `\run\x` 而不是 `/run/x` —— 第一版按全路径比，实测 5 红）。
$present = @('dec-cc.md')
$ex = { param($p) $present -contains (Split-Path $p -Leaf) }
$exAgent = { param($p) (Split-Path $p -Leaf) -eq 'agent-output.txt' }
$exAcc = { param($p) (Split-Path $p -Leaf) -eq 'accept-output.txt' }
$exNone = { param($p) $false }
$fmSub = @{ 'evidence-manifest' = @{ subjects = @(@{ name = 'dec-cc'; path = 'dec-cc.md'; state = 'out/dec-cc.md' }) } }
$r1 = Resolve-ReviewProduct -runDir '/run' -fm $fmSub -Exists $ex
Assert-True "cc-28 ★#8 卡声明产物**在 runDir** ⇒ 取它（source=evidence-manifest.subjects）" (
    $r1['ok'] -and $r1['name'] -eq 'dec-cc.md' -and $r1['source'] -eq 'evidence-manifest.subjects')
$r2 = Resolve-ReviewProduct -runDir '/run' -fm $fmSub -Exists $exAgent
Assert-True "cc-29 ★#8 声明产物**不在 runDir** ⇒ 回退 agent-output.txt（source=fallback）" (
    $r2['ok'] -and $r2['name'] -eq 'agent-output.txt' -and $r2['source'] -eq 'fallback')
$r3 = Resolve-ReviewProduct -runDir '/run' -fm $fmSub -Exists $exAcc
Assert-True "cc-30 #8 两级回退：agent-output 也没有 ⇒ accept-output.txt" (
    $r3['ok'] -and $r3['name'] -eq 'accept-output.txt')
$r4 = Resolve-ReviewProduct -runDir '/run' -fm $fmSub -Exists $exNone
Assert-True "cc-31 ★#8 三者都无 ⇒ ok=false 且 tried 逐项列出（不静默）" (
    (-not $r4['ok']) -and (@($r4['tried']) -contains 'dec-cc.md') -and
    (@($r4['tried']) -contains 'agent-output.txt') -and (@($r4['tried']) -contains 'accept-output.txt'))
$fmEvil = @{ 'evidence-manifest' = @{ subjects = @(@{ path = '../../etc/passwd' }, @{ path = 'C:\win\evil.md' }) } }
$r5 = Resolve-ReviewProduct -runDir '/run' -fm $fmEvil -Exists $exAgent
Assert-True "cc-32 ★#8 安全边界：绝对路径 / 含 .. 的声明**驳回并登记**，不 Join 出仓" (
    $r5['ok'] -and $r5['source'] -eq 'fallback' -and
    @($r5['tried'] | Where-Object { $_ -match '驳回' }).Count -eq 2)
$r6 = Resolve-ReviewProduct -runDir '/run' -fm @{} -Exists $exAgent
Assert-True "cc-33 #8 无 evidence-manifest ⇒ 直接走回退（不报错）" (
    $r6['ok'] -and $r6['source'] -eq 'fallback' -and $r6['name'] -eq 'agent-output.txt')
Assert-True "cc-34 接线：Invoke-Review 用 Resolve-ReviewProduct（不再硬编码产物名）" (
    $content.Contains('Resolve-ReviewProduct -runDir $runDir -fm $fm') -and
    (-not $content.Contains("`$product = Join-Path `$runDir 'agent-output.txt'")))
# ── #3 注入面：真跑 `Build-JudgePrompt`（读**真模板**）──
$p1 = Build-JudgePrompt -fm @{ task = 'T'; body = 'B'; accept = @('test -f out/dec-cc.md') } `
                        -product 'PRODUCT_TEXT' -runId 'RUNX' -cardPath 'x.md' -productName 'dec-cc.md'
Assert-True "cc-35 ★#3 注入：提示词带**产物相对名**，且**无未替换占位**（{{…}} 一个不剩）" (
    $p1 -match 'dec-cc\.md' -and (-not ($p1 -match '\{\{')))
Assert-True "cc-36 ★#3 注入面写明相对根 = runDir（判官无从自推 ⇒ 只能由外壳喂）" (
    $p1 -match '相对根 = `runDir`')
Assert-True "cc-37 #3 既有占位仍全部替换（PRODUCT / RUN_ID 逐字在）" (
    $p1 -match 'PRODUCT_TEXT' -and $p1 -match 'RUNX')
Assert-True "cc-38 模板已写明 `path` 相对根 = runDir（#3 的注入面）" (
    $ccTmpl -match '相对根 = `runDir`' -and $ccTmpl -match 'PRODUCT_NAME')

# ⑫ D7-P3-1（2026-09-26）：**不得自审**（权限模型四要素之一）
# 为什么要有：站上**只做粗判（归一后同名 ⇒ 自审）**；族级细判在本仓（`agent_pair_audit.py`）
#   —— 因为**族表不在站上** ⇒ 站上**不假装能判族**。本组守的就是"粗判"这一层。
$g1 = Resolve-SelfReviewGuard -ProducerModel 'local/m27-q4ks' -JudgeId 'local/m27-q4ks' -JudgeAlias 'm27'
Assert-True "sr-1 同名 ⇒ self 且**拒**" ((-not $g1['ok']) -and $g1['verdict'] -eq 'self')
$g2 = Resolve-SelfReviewGuard -ProducerModel 'local/m27-q4ks' -JudgeId 'cluster-litellm/m27-q4ks' -JudgeAlias 'x'
Assert-True "sr-2 ★**跨传输前缀同名** ⇒ self（归一穿透前缀）" ($g2['verdict'] -eq 'self')
$g3 = Resolve-SelfReviewGuard -ProducerModel 'local/gpt-oss-20b' -JudgeId 'openrouter/nvidia/gpt-oss-20b:free' -JudgeAlias 'x'
Assert-True "sr-3 ★**尾参差异**（`:free`）仍判 self" ($g3['verdict'] -eq 'self')
$g4 = Resolve-SelfReviewGuard -ProducerModel 'Station:A/ThinkingMachines/Inkling:Free' -JudgeId 'thinkingmachines/inkling' -JudgeAlias 'x'
Assert-True "sr-4 大小写与前缀差异 ⇒ self" ($g4['verdict'] -eq 'self')
$g5 = Resolve-SelfReviewGuard -ProducerModel 'local/gpt-oss-20b' -JudgeId 'openrouter/nvidia/nemotron-3-ultra-550b-a55b:free' -JudgeAlias 'ultra'
Assert-True "sr-5 不同名 ⇒ ok（放行进 L2）" ($g5['ok'] -and $g5['verdict'] -eq 'ok')
$g6 = Resolve-SelfReviewGuard -ProducerModel '' -JudgeId 'local/m27-q4ks' -JudgeAlias 'm27'
Assert-True "sr-6 ★producer 的 model **读不出 ⇒ 拒**（fail-closed：读不到 ≠ 不同）" (
    (-not $g6['ok']) -and $g6['verdict'] -eq 'unknown')
$g7 = Resolve-SelfReviewGuard -ProducerModel '' -JudgeId 'local/m27-q4ks' -JudgeAlias 'm27' -Allow
Assert-True "sr-7 显式 Allow ⇒ 放行但 **verdict 仍 unknown**（降级 != 隐藏）" ($g7['ok'] -and $g7['verdict'] -eq 'unknown')
$g8 = Resolve-SelfReviewGuard -ProducerModel 'local/m27-q4ks' -JudgeId 'local/m27-q4ks' -JudgeAlias 'm27' -Allow
Assert-True "sr-8 显式 Allow ⇒ 放行但 **verdict 仍 self**" ($g8['ok'] -and $g8['verdict'] -eq 'self')
$g9 = Resolve-SelfReviewGuard -ProducerModel 'local/gpt-oss-20b' -JudgeId '' -JudgeAlias ''
Assert-True "sr-9 judge id 读不出 ⇒ **Allow 也不放行**（配置错误，不是'不可判'）" (-not $g9['ok'])
Assert-True "sr-10 facts 带两侧原始值（可追溯）" (
    $g1['facts']['producer_model'] -eq 'local/m27-q4ks' -and $g1['facts']['judge_id'] -eq 'local/m27-q4ks')
# 接线（防"写了但没跑"）
Assert-True "sr-11 接线：门在**读产物之前**且**拒码独立**（exit 8）" (
    $content.IndexOf('Resolve-SelfReviewGuard -ProducerModel') -lt
    $content.IndexOf('$productText = [System.IO.File]::ReadAllText($product') -and
    $content -match 'return 8')
Assert-True "sr-12 两处写点都留 self_review_guard" (
    ([regex]::Matches($content, "\`$review\['self_review_guard'\] = \`$sgSection")).Count -ge 2)
Assert-True "sr-13 有显式放行通道（不是偷偷放行）" (
    $content -match '\[switch\]\$allowSelfReview' -and $content -match '--allow-self-review')

# ⑬ D7-P3-2（2026-09-26）：**编排层 —— 谁审谁**（自动避让，而非只拒）
# 为什么要有：`D7-P3-1` 的门只"拒"，**没解决"该谁审"**（实测 review 覆盖 2/246）⇒ 本组守"换得对"。
$jT = [ordered]@{
    'ultra'       = @{ egress = $true;  id = 'openrouter/nvidia/nemotron-3-ultra-550b-a55b:free' }
    'main'        = @{ egress = $false; id = 'main-opencode-cli' }
    'm27'         = @{ egress = $false; id = 'local/m27-q4ks' }
    'rpc-v4flash' = @{ egress = $false; id = 'cluster-v4flash' }
}
$s1 = Select-Reviewer -ProducerModel 'local/m27-q4ks' -Table $jT -PreferAlias 'm27' -Sensitivity 'public'
Assert-True "sel-1 ★原选中与产出者同名 ⇒ **被排除**，自动改选" ($s1['ok'] -and $s1['alias'] -ne 'm27', $s1['alias'])
Assert-True "sel-2 ★改选**跨传输档优先**（产出者本机 ⇒ 优选出网判官）" ($s1['alias'] -eq 'ultra' -and $s1['cross_tier'])
Assert-True "sel-3 被排除者**点名**（可追溯，不静默）" (@($s1['rejected']) -join ' ') -match 'm27\(与产出者同名\)'
$s2 = Select-Reviewer -ProducerModel 'openrouter/nvidia/nemotron-3-ultra-550b-a55b:free' -Table $jT -PreferAlias 'ultra' -Sensitivity 'public'
Assert-True "sel-4 产出者是出网档 ⇒ 优选**本机判官**（即 cross_tier 为真，且原选中被排除）" (
    $s2['ok'] -and $s2['cross_tier'] -and $s2['alias'] -ne 'ultra')
# ⚠ **期望不钉死具体 alias**：并列时的次序键是 `alias` 升序，而 `m27` < `main`
#   （**数字 '2'(50) 先于字母 'a'(97)**）—— 我先按"字典直觉"写成 `main` ⇒ 假红。
#   ⇒ 断言**性质**（跨档 + 非同名）比钉死一个名字更耐用；名字本身由 `sel-8` 的可复现性守。
$s3 = Select-Reviewer -ProducerModel 'local/gpt-oss-20b' -Table $jT -PreferAlias 'm27' -Sensitivity 'public'
Assert-True "sel-5 ★原选中**可用时保持不变**（尊重卡/命令行的显式选择）" ($s3['alias'] -eq 'm27')
$s4 = Select-Reviewer -ProducerModel 'local/gpt-oss-20b' -Table $jT -PreferAlias 'nope' -Sensitivity 'public'
Assert-True "sel-6 prefer 是无效 alias ⇒ 仍能选出（不因 prefer 错而失败）" ($s4['ok'] -and $s4['alias'])
$onlySelf = [ordered]@{ 'a' = @{ egress = $false; id = 'local/x' }; 'b' = @{ egress = $true; id = 'openrouter/y/x' } }
$s5 = Select-Reviewer -ProducerModel 'local/x' -Table $onlySelf -PreferAlias 'a' -Sensitivity 'public'
Assert-True "sel-7 ★全部候选都被排除 ⇒ **ok=false**（fail-closed，不偷偷放行）" (-not $s5['ok'], $s5['reason'])
$s6 = Select-Reviewer -ProducerModel 'local/m27-q4ks' -Table $jT -PreferAlias 'm27' -Sensitivity 'public'
Assert-True "sel-8 **可复现**（同输入两次同结果）" ($s6['alias'] -eq $s1['alias'])
# 接线（防"写了但没跑"）
Assert-True "sel-9 接线：**先换后拒**（换在前面，拒在后面）" (
    $content.IndexOf('Select-Reviewer -ProducerModel') -lt $content.IndexOf('REJECT SELF_REVIEW_BLOCK'))
Assert-True "sel-10 接线：换过之后**重新过一遍**门（不是换完就算）" (
    $content -match '\$sg2 = Resolve-SelfReviewGuard' -and $content -match "if \(\`$sg2\['ok'\]\)")
Assert-True "sel-11 留痕：review.json 记 `switched_from`（未换 = 空串）" (
    $content -match "switched_from = \`$switchedFrom")

# --- ★★ A1 (2026-09-29): D6/D7 分界判据求值（ADR-0009 §2 三分支）---
#   为什么: A1 的实质 = "**派发前**对三判据求值 ⇒ 唯一归属"；而"**互斥且穷尽**"是它的**全部价值**
#     —— 8 种取值组合必须**全命中且仅命中一条**（既不落空、也不双命中）。
#   ⚠ 第三分支（¬B-3 ∧ ¬B-1 ∧ ¬B-2 ⇒ D6）是**约定归属**（修 O-115）⇒ 删掉它，下面
#     "3 行灰项"形态的用例**必须红**（这正是 A-LIST-LANDING-PLAN §2.2 点名的**先验红点**）。
$c = Resolve-D6D7Boundary 'true' 'true' 'true'
Assert-True "a1: 是/是/是 ⇒ D7（第一分支 B-1∨B-2 优先，压过 B-3）" ($c.resolved -and $c.layer -eq 'D7' -and $c.branch -eq 'B-1orB-2')
$c = Resolve-D6D7Boundary 'false' 'false' 'true'
Assert-True "a1: 否/否/是 ⇒ D6（第二分支：仅本次派发内部质量门，如判官抽检）" (
    $c.resolved -and $c.layer -eq 'D6' -and $c.branch -eq 'B-3')
$c = Resolve-D6D7Boundary 'false' 'false' 'false'
Assert-True "a1: ★否/否/否 ⇒ D6（**第三分支=约定归属**；ADR §3 三行灰项正是此形）" (
    $c.resolved -and $c.layer -eq 'D6' -and $c.branch -eq 'convention')
$c = Resolve-D6D7Boundary 'true' 'false' 'false'
Assert-True "a1: 是/否/否 ⇒ D7（B-1：需非产出方给结论，如需求方验收/跨站派发）" ($c.resolved -and $c.layer -eq 'D7')
$c = Resolve-D6D7Boundary 'false' 'true' 'false'
Assert-True "a1: 否/是/否 ⇒ D7（B-2：同产物多轮往返，如多轮续聊 审→改→再审）" ($c.resolved -and $c.layer -eq 'D7')
# 穷尽性：8 种组合**逐个**求值 ⇒ resolved 必有、layer 必 ∈ {D6,D7}（**无一落空**）。
$miss = @(); $nD6 = 0; $nD7 = 0
foreach ($a in @('true', 'false')) { foreach ($bb in @('true', 'false')) { foreach ($d in @('true', 'false')) {
    $r = Resolve-D6D7Boundary $a $bb $d
    if (-not $r.resolved -or -not $r.layer) { $miss += "$a/$bb/$d" } elseif ($r.layer -eq 'D6') { $nD6++ } else { $nD7++ }
}}}
Assert-True "a1: ★8 种取值组合**全命中**（无一落空；落空者: $($miss -join ',')）" ($miss.Count -eq 0)
Assert-True "a1: 互斥穷尽 ⇒ D6/D7 计数 = 2/6（D7 = B-1∨B-2 为真的 3×2；D6 = 其余 1×2）" (
    $nD6 -eq 2 -and $nD7 -eq 6)
# 诚实性：任一键未声明（空/非 true|false）⇒ **不假装已求值**。
$c = Resolve-D6D7Boundary '' 'false' 'true'
Assert-True "a1: 任一键未声明 ⇒ resolved=false 且 layer 空（「没判」≠「判了且归 D6」）" (
    (-not $c.resolved) -and $c.layer -eq '')
$c = Resolve-D6D7Boundary 'yes' 'false' 'true'
Assert-True "a1: 非枚举值（yes）不被当成 true ⇒ 未求值（fail-soft，不扩大取值域）" (
    (-not $c.resolved) -and $c.layer -eq '')
# 行为断言（**非文本扫描**，避免 O-65 那种"用全文子串判"的假绿）: 三键经真 Get-FrontMatter 解析。
$bCard = Join-Path $tmpCards 'boundary.md'
@"
---
proj: paper
task: boundary parse test
model: gpt-oss
needs_non_producer_verdict: true
needs_multi_round_review: false
is_intra_dispatch_quality_gate: false
---
## 任务描述
boundary body
"@ | Set-Content $bCard -Encoding utf8
$bm = Get-FrontMatter $bCard
Assert-True "a1: 三键经 Get-FrontMatter **解析出来**（登记进白名单生效，非「写了没人读」）" (
    $bm['needs_non_producer_verdict'] -eq 'true' -and $bm['needs_multi_round_review'] -eq 'false' -and
    $bm['is_intra_dispatch_quality_gate'] -eq 'false')
Assert-True "a1: 三键与求值闭合（解析出的三键喂给求值 ⇒ 是/否/否 ⇒ D7，与 §3 B-1 行一致）" (
    (Resolve-D6D7Boundary $bm['needs_non_producer_verdict'] $bm['needs_multi_round_review'] $bm['is_intra_dispatch_quality_gate']).layer -eq 'D7')
$plainB = Get-FrontMatter (Join-Path $tmpCards 'plain.md')
Assert-True "a1: ★存量卡（无这三键）⇒ 三键缺省空串 ⇒ 求值 resolved=false（**向后兼容**，不误判归属）" (
    $plainB['needs_non_producer_verdict'] -eq '' -and $plainB['needs_multi_round_review'] -eq '' -and
    $plainB['is_intra_dispatch_quality_gate'] -eq '' -and
    (-not (Resolve-D6D7Boundary $plainB['needs_non_producer_verdict'] $plainB['needs_multi_round_review'] $plainB['is_intra_dispatch_quality_gate']).resolved))
# 接线（防"写了但没跑"）: 派发前求值 + run.json 落键。
Assert-True "a1: 接线：`$run 落 boundary 键（派发前求值随 run.json 留痕）" (
    $content -match 'boundary = \$boundary')
Assert-True "a1: 接线：求值点在**派发前**（早于主路 body 的 `out/.progress` 写入）" (
    ($content.IndexOf('Resolve-D6D7Boundary $fm')) -gt 0 -and
    ($content.IndexOf('Resolve-D6D7Boundary $fm')) -lt $content.IndexOf('out/.progress'))

# ══════════════════════════════════════════════════════════════════════════════
# --- o118 (2026-09-30, `O-118` 甲): 循环检测 —— 「同一步重复 N 次 ⇒ 判循环并终止续跑」---
#   动机: opencode **无内置循环检测 / 打断** ⇒ 死循环只能人工监控
#     （实测本地 qwen3-coder-next 良率 0% / 死循环 273 次 grep）。
#   设计: 只读本站**已留痕**的 `out/.agent-output.txt`（不新增采集面 / 不改协议 / 不出网）;
#     检测到即**终止续跑**（把同一循环重跑一遍 = 白烧 token）; 不杀首跑（那是 `timeout -k 10` 的职责）。
#   阈值 `LOOP_N=20` = **设计选择、未实测**（无真实死循环样本可校准; 已知样本 273 ⇒ 20 远离它）。
#   ★ 本条**必须**有行为测试: 静态断言只能证"那段文本在"——
#     正是 o117 的教训（查'串在不', 查不出'这条链现在跑不跑得起来'）。
Assert-True "o118①: body 在循环检测段（LOOP_DETECTED + **排除空行** + LOOP_N 阈值）" (
    $content.Contains('LOOP_DETECTED=1') -and
    $content.Contains("grep -v '^[[:space:]]*$'") -and
    $content.Contains('LOOP_N=20'))
Assert-True "o118②: 续跑 while **必须**带 `LOOP_DETECTED -eq 0` 闸（检测到循环 ⇒ 不续跑; 缺闸 = 白烧 token）" (
    $content.Contains('[ "`$LOOP_DETECTED" -eq 0 ]'))
Assert-True "o118③: 两处**显式报** LOOP_DETECTED（`.meta` + executor-trace）⇒ 可审计, 不静默" (
    $content.Contains('LOOP_DETECTED=%s') -and $content.Contains('loop_detected=%s'))
# 行为: 用**本地 Git Bash** 跑同一段 bash 结构（含阈值判定 + 续跑闸）。
# ⚠ 传参纪律（本仓老坑）: `& $bashPath -c $cmd` 走 **PowerShell 原生参数** ⇒ `-cmd` 串里
#   **不得含双引号**（PS 会剥引号 + 按空白重切 ⇒ 命令被截断；实测 `echo "AA BB CC"` 只吐 `AA`）。
#   ⇒ 本段用**单引号 / 裸词**改写（等价结构，非等价引号）。body 侧不受此限（那是**写进文件**的 bash）。
$q = [char]39
$fLoopP = Join-Path $env:TEMP 'fm_o118_pos.txt'
$fLoopN = Join-Path $env:TEMP 'fm_o118_neg.txt'
$logLoopP = Join-Path $env:TEMP 'fm_o118_pos.log'
$logLoopN = Join-Path $env:TEMP 'fm_o118_neg.log'
foreach ($f in @($logLoopP, $logLoopN)) { Remove-Item $f -ErrorAction SilentlyContinue }
# 正例: 同一行重复 **25** 次 **且** 混入 **30 个空行**（空行必须被排除, 否则空行会把计数堆到假阳）
Set-Content -Path $fLoopP -Encoding ASCII -Value (@(1..25 | ForEach-Object { 'grep -rn FOO .' }) + @(1..30 | ForEach-Object { '' }))
# 负例: 40 行**互不相同**（一条正常失败日志的样子 —— 不该被判成循环）
Set-Content -Path $fLoopN -Encoding ASCII -Value (1..40 | ForEach-Object { "step line $_" })
$snipBody = 'LOOP_N=20; LOOP_MAX=$(grep -v ' + $q + '^[[:space:]]*$' + $q + ' $F 2>/dev/null | sort | uniq -c | sort -rn | head -1 | awk ' + $q + '{print $1}' + $q + '); LOOP_DETECTED=0; if [ x$LOOP_MAX != x ] && [ $LOOP_MAX -ge $LOOP_N ]; then LOOP_DETECTED=1; fi; RC=1; CONT_ATTEMPT=0; N=0; while [ $RC -ne 0 ] && [ $CONT_ATTEMPT -lt 3 ] && [ $LOOP_DETECTED -eq 0 ]; do N=$((N+1)); CONT_ATTEMPT=$((CONT_ATTEMPT+1)); break; done; echo LD=$LOOP_DETECTED MAX=$LOOP_MAX RESUME_RAN=$N'
$cmdLoopP = 'F=' + $q + ($fLoopP -replace '\\', '/') + $q + '; ' + $snipBody
$cmdLoopN = 'F=' + $q + ($fLoopN -replace '\\', '/') + $q + '; ' + $snipBody
$rcLoopP = Invoke-LocalBashCmd -bashPath $lb -cwd $env:TEMP -logFile $logLoopP -cmd $cmdLoopP
$rcLoopN = Invoke-LocalBashCmd -bashPath $lb -cwd $env:TEMP -logFile $logLoopN -cmd $cmdLoopN
$outLoopP = "$(Get-Content $logLoopP -Raw -ErrorAction SilentlyContinue)"
$outLoopN = "$(Get-Content $logLoopN -Raw -ErrorAction SilentlyContinue)"
Assert-True "o118④(行为): 同行重复 25 次（且 30 空行被排除）⇒ LD=1 · 续跑**未跑**（RESUME_RAN=0）" (
    $rcLoopP -eq 0 -and $outLoopP -match 'LD=1' -and $outLoopP -match 'MAX=25' -and $outLoopP -match 'RESUME_RAN=0')
Assert-True "o118⑤(行为·先验红): **无**重复行 ⇒ LD=0 · 续跑**照常跑**（RESUME_RAN=1）（否则判据会把正常失败也当循环）" (
    $rcLoopN -eq 0 -and $outLoopN -match 'LD=0' -and $outLoopN -match 'RESUME_RAN=1')
foreach ($f in @($fLoopP, $fLoopN)) { Remove-Item $f -ErrorAction SilentlyContinue }

# ══════════════════════════════════════════════════════════════════════════════
# --- o124 (2026-09-30, `O-124` 候选②): 批报告的 `st=` 必须取【实际站】（不可判时如实回落）---
#   一手事故: `local-only` 档下 claude **自己按"引擎就绪顺序"选站** ⇒ 三次实测**全落 A 站**
#     （三份 `.agent-run.json` 均 `station:A/main`），而批报告打的是 `st=A / st=B / st=C`。
#   ★ 本函数**只报事实**: 日志里没有那两行 ⇒ 返回 ''（= **不可判**）⇒ 调用方**如实回落**请求值。
$stLogLocal = @(
    'P3_CANDIDATES: A,B,C (pref= avoid=)',
    'P3_STATION_SELECT: station=A host=scott-lau-NEX.local (local engine ready) avoid=',
    'RUNSTAMP: 202609301456389799 (atomic claim; O-63)'
)
$stLogEgress = @('CLAUDE_EGRESS_STATION_SELECT: station=C host=192.168.10.37 (backend=OpenRouter)')
$stLogNone = @('BATCH_PLAN: 行=3', 'RUNSTAMP: 123 (atomic claim; O-63)')
$stLogResel = @(
    'P3_STATION_SELECT: station=A host=h1 (local engine ready) avoid=',
    'P3_STATION_SELECT: station=B host=h2 (local engine ready) avoid='
)
Assert-True "o124①: local 档日志 ⇒ 实际站 = A（报告将打 A 而不是请求值）" (
    (Get-ActualStation -Lines $stLogLocal) -eq 'A')
Assert-True "o124②: 出网档日志 ⇒ 实际站 = C（**另一种行名也认**）" (
    (Get-ActualStation -Lines $stLogEgress) -eq 'C')
Assert-True "o124③(先验红·边界): 日志里**没有**那两行 ⇒ 返回 ''（**不可判**）—— 必须回落, 不许猜" (
    (Get-ActualStation -Lines $stLogNone) -eq '')
Assert-True "o124④: 同名多行（resume 重选）⇒ 取**最后一条**（= 最终实际用的站）" (
    (Get-ActualStation -Lines $stLogResel) -eq 'B')
Assert-True "o124⑤: 接线 —— 批报告用 `Get-ActualStation` 取实际站, 且**取不到时回落请求值**" (
    $content.Contains('$stActual = Get-ActualStation -Lines $clines') -and
    $content.Contains('$stLabel = if ($stActual -and $stActual -ne $j.station)'))

# --- o124b (2026-09-30, `O-124` 候选①): 卡/批行的 `station=` 必须**真的被采纳**（local 档的 pref）---
#   根因（读码）: 卡用 `model: claude`（自然写法）⇒ `Resolve-Model` 给出 `station=''`
#     ⇒ `$stPref` 恒空 ⇒ `P3_CANDIDATES: A,B,C (pref= avoid=)` ⇒ 三行 `station=A/B/C` **全落第一站**。
#   ⇒ 修法 = 路由无站时**回落** `-PreferredStation`（来源 = 批行 `station=` 经 `--remotehost` 转成的 host 串）。
#   ⚠ 边界: `Get-TargetHost` 对**未知**输入**默认返回 B 的 host** ⇒ 反查**不能**直接拿它比
#     （否则任意串都会"反查成 B"）。本用例 o124b② 就是钉这条。
#   ⚠ 写卡/写断言须知（本次踩到）: `Assert-True "…"` 的描述串**不得以反引号结尾**
#     —— `` `" `` 会被 PS 读成**转义引号** ⇒ 字符串不终止 ⇒ 报 "string is missing the terminator"
#     （错报位置在**文件末尾**，不在出错行 ⇒ 别按报的位置找）。
Assert-True "o124b①: host -> 站字母（A/B/C 三条**全部**可反查）" (
    (Get-StationLetterFromHost 'scott-lau-NEX.local') -eq 'A' -and
    (Get-StationLetterFromHost 'scott-lau-GTR-Pro.local') -eq 'B' -and
    (Get-StationLetterFromHost '192.168.10.37') -eq 'C')
Assert-True "o124b②(先验红·边界): **未知 host** ⇒ ''（不许因 `Get-TargetHost` 的 B 默认而误判成 B）" (
    (Get-StationLetterFromHost 'scott-lau-WHATEVER.local') -eq '' -and
    (Get-StationLetterFromHost '') -eq '')
Assert-True "o124b③: 端到端（纯函数链）—— 批行 host 经反查后**真的**成为 pref 首选" (
    ((Resolve-ClaudeStationCandidates -Avoid '' -Stations @('A', 'B', 'C') -Preferred (Get-StationLetterFromHost 'scott-lau-GTR-Pro.local')) -join ',') -eq 'B,A,C')
Assert-True "o124b④: 接线 —— `Invoke-Task-Claude` 在**路由无站**时回落到 `-PreferredStation`（pref 回填）" (
    $content.Contains('if (-not $stPref) { $stPref = [string]$PreferredStation }'))
Assert-True "o124b⑤: 接线 —— pin 使通道**成为站上通道**（否则出网档的 pin 仍被静默丢弃）" (
    $content.Contains('-or [bool]$PreferredStation'))
Assert-True "o124b⑥: 接线 —— claude 分支把 `-hostName` 反查成站并**传下去**" (
    $content.Contains('$pinSt = Get-StationLetterFromHost $hostName') -and
    $content.Contains('-PreferredStation $pinSt'))

# --- o125 (2026-09-30, `O-125` 候选①): `backend` 从 `sensitivity` 拆出（**可选字段** + 缺省推导）---
#   为什么: `sensitivity` 一个字段扛两个语义（内容档位 / 执行后端），而**后端是档位的副作用**
#     ⇒ 想"按内容判档、却测另一条执行链"的作者没有正当写法（实测: 为测本地引擎被迫把 public 卡写成
#     local-only = **过分类**）。⇒ 加可选 `backend: local|egress`，**缺省仍由档位推导**（向后兼容：
#     实测全仓 **0 张卡**在用该键 ⇒ 迁移面为空）。
#   ★ 判据（`O-125` 明写）: 卡面**同时**声明 `sensitivity` 与 `backend` 且**互相矛盾** ⇒ FAIL。
#     `local-only` + `backend: egress` = 内容标了"不出网"却显式要出网 ⇒ **拒**（不猜、不静默取一边）。
#   ⚠ 未知取值同样 fail-closed（`backend: egresss` 这种拼错**不许静默退回推导值**）。
function BE([string]$s, [string]$b) { return (Resolve-CardBackendLocal -Sensitivity $s -Backend $b) }
Assert-True "o125①(先验红·缺省推导): 不带 `backend` ⇒ 与旧式**逐字等价**（local-only ⇒ local；其余 ⇒ egress）" (
    (BE 'local-only' '').ok -and (BE 'local-only' '').local -eq $true -and
    (BE 'public' '').ok -and (BE 'public' '').local -eq $false -and
    (BE 'sanitized' '').ok -and (BE 'sanitized' '').local -eq $false -and
    (BE 'unverified' '').ok -and (BE 'unverified' '').local -eq $false)
Assert-True "o125②: 显式 `backend: local` 在**非** local-only 档上生效（= 过分类/选链，允许）" (
    (BE 'public' 'local').ok -and (BE 'public' 'local').local -eq $true -and
    (BE 'sanitized' 'LOCAL').ok -and (BE 'sanitized' 'LOCAL').local -eq $true)
Assert-True "o125③: 显式 `backend: egress` 在 local-only 档上 ⇒ **矛盾**（ok=false，不许猜）" (
    -not (BE 'local-only' 'egress').ok)
Assert-True "o125④: 显式 `backend: egress` + 非 local-only 档 ⇒ 与缺省同值（egress）" (
    (BE 'public' 'egress').ok -and (BE 'public' 'egress').local -eq $false -and
    (BE 'local-only' 'local').ok -and (BE 'local-only' 'local').local -eq $true)
Assert-True "o125⑤(先验红·边界): 未知取值（拼错）⇒ fail-closed（不许静默退回推导值）" (
    -not (BE 'public' 'egresss').ok -and -not (BE 'local-only' 'l').ok -and -not (BE 'public' '1').ok)
Assert-True "o125⑥: 接线 —— 唯一赋值点改用该纯函数, 且 `$useStation` 把 `$backendLocal` 也算进去" (
    $content.Contains('$br = Resolve-CardBackendLocal -Sensitivity $sens -Backend ([string]$fm[''backend''])') -and
    $content.Contains('$backendLocal = $br[''local'']') -and
    $content.Contains('$useStation = $backendLocal -or [bool]$r[''station''] -or [bool]$PreferredStation'))

# --- o127 (2026-09-30, `O-127`): 批清单**必须显式按 UTF-8 读**（裸 `Get-Content` ⇒ ANSI ⇒ 吞换行）---
#   一手实测: 同一份 BOM-less UTF-8 清单，裸读 = **21 行/kept=0**（卡行被并进注释 ⇒ 整批 ABORT）；
#     加 `-Encoding UTF8` = **33 行/kept=1**（卡行完好）。⇒ 这是**读侧**的病，不是"清单要带 BOM"的约定。
Assert-True "o127: 批清单解析**显式 -Encoding UTF8**（裸 `Get-Content` 会按 ANSI 解码 ⇒ 吞掉换行 ⇒ 0 行）" (
    $content.Contains('Get-Content -LiteralPath $listFile -Encoding UTF8'))

# --- b1 (2026-10-01, `O-135` **B 段**): **P0 立契** —— 卡 → `TaskContract` 信封（纯函数）--------
#   契约 = `D7-PROTOCOL-CONTRACT.md` §1.1；判据 = `ops/rpc_check.py` 的 `validate_envelope`
#     （★ 判据**不在本夹具里重写** —— 这里只测"**产信封**"这一半；判据那一半由
#      `tests/test_rpc_check_d7_protocol.py` 的 CLI 用例覆盖）。
#   ★ 本批**唯一新增的计算** = `criteria_hash`（= 红线 3「判据与 golden 哈希在 **P0 固化**」的固化动作）。
#   ⚠ `gaps` = 本仓**当前不提供真值**的字段（如实报出）—— 断言它**非空**，防"占位被读成有值"。
$fmT = @{ accept = @('test -f out/x.md', 'echo ok'); 'accept-golden' = @{ source = 'golden/g.py'; cmd = './g.py' }
          task = 'TC 夹具'; timeout_s = 900; sensitivity = 'local-only'; readonly = $true }
$cidT = @{ path = 'card.md'; sha256 = 'sha256:deadbeef'; bytes = 1; front_matter = $true }
$TCT = New-TaskContract -Fm $fmT -CardId $cidT
Assert-True "b1①: task_id 取卡身份哈希（本仓唯一的任务标识）" (
    $TCT.contract.task_id -eq 'sha256:deadbeef')
Assert-True "b1②: accept 每项含 criteria + criteria_hash，且哈希 = 判据文本的哈希（**可复算**）" (
    $TCT.contract.accept.Count -eq 2 -and
    $TCT.contract.accept[0].criteria -eq 'test -f out/x.md' -and
    $TCT.contract.accept[0].criteria_hash -eq ("sha256:" + (Get-Sha256Text 'test -f out/x.md')))
Assert-True "b1③: 两条不同判据 ⇒ 两个不同哈希（否则「固化」是恒真判据）" (
    $TCT.contract.accept[0].criteria_hash -ne $TCT.contract.accept[1].criteria_hash)
Assert-True "b1④: golden/inputs/evidence_budget 的**子键键在**（摘要逐字给出的键，值可为空）" (
    $TCT.contract.golden.Contains('ref') -and $TCT.contract.golden.Contains('checksum') -and
    $TCT.contract.inputs.Contains('ref') -and $TCT.contract.inputs.Contains('digest') -and
    $TCT.contract.evidence_budget.Contains('anchors') -and
    $TCT.contract.evidence_budget.Contains('tool_calls') -and
    $TCT.contract.golden.ref -eq 'golden/g.py')
Assert-True "b1⑤: gaps 如实报出本仓**不提供真值**的三项" (
    (@($TCT.gaps) -join ',') -eq 'evidence_budget,constraints,golden.checksum')
Assert-True "b1⑥(先验红·空 accept): 无判据的卡 ⇒ accept 为空表（判据会因此拒 ⇒ 非恒真）" (
    (New-TaskContract -Fm @{ accept = @(); 'accept-golden' = @{ source = '' }; task = 't'
                             timeout_s = 900; sensitivity = ''; readonly = $false } -CardId $cidT).contract.accept.Count -eq 0)
Assert-True "b1⑦: 空白判据串被跳过（不产生 criteria_hash 空哈希的假条目）" (
    (New-TaskContract -Fm @{ accept = @('  ', 'a'); 'accept-golden' = @{ source = '' }; task = 't'
                             timeout_s = 900; sensitivity = ''; readonly = $false } -CardId $cidT).contract.accept.Count -eq 1)
Assert-True "b1⑧: 接线 —— P0 立契在 `Invoke-Task` 内，且**调判据本体**（外壳不重写判据）" (
    $content.Contains('$d7tc = New-TaskContract -Fm $fm -CardId $cardId') -and
    $content.Contains("Write-D7Report -Kind 'TaskContract'") -and
    $content.Contains('Invoke-D7Cli -Argv') -and
    ([regex]::Matches($content, [regex]::Escape('--d7-envelope'))).Count -ge 1)
$d7blk = ''
$bi0 = $content.IndexOf('$d7tc = New-TaskContract')
$bi1 = $content.IndexOf('# A1 / ADR-0009', $bi0)
if ($bi0 -ge 0 -and $bi1 -gt $bi0) { $d7blk = $content.Substring($bi0, $bi1 - $bi0) }
Assert-True "b1⑨: 接线 —— **灰度期不阻断**（P0 块内**无** return/die；收紧时机 = gaps 清空）" (
    $d7blk.Length -gt 0 -and -not ($d7blk -match '\breturn\b') -and
    $content.Contains('-Gaps $d7tc'))

# --- b2 (2026-10-01, `O-136` **B2**): **P3 回收 + P4a/P4b/P5**（产信封 / 相序列 / 判据接线）-------
#   ★ 纯的那半（`New-RunReport` / `Resolve-D7PhaseChain` / `New-Verdict`）**离线真跑**；
#     有副作用的那半（`Invoke-D7Cli` / `Write-D7Report` / `Write-D7Adjudication`）只做**接线形态**断言
#     （判据本体由 `tests/test_rpc_check_d7_protocol.py` 覆盖 ⇒ **不在此处抄第二份**）。
$runT = [ordered]@{
    task_id = 'task-20260101000000000000'; exit_code = 0
    content_digest = 'sha256:aaaa'; output_bytes = 123
    usage = [ordered]@{ total_tokens = 7 }
    card = [ordered]@{ sha256 = 'sha256:card' }
}
$RRT = New-RunReport -Run $runT -RunDir 'C:\runs\1'
Assert-True "b2①: RunReport 取到**真值**的五项（run_id/artifact{digest,size}/inputs_digest/exit_code/usage）" (
    $RRT.report.run_id -eq 'task-20260101000000000000' -and
    $RRT.report.artifact.digest -eq 'sha256:aaaa' -and $RRT.report.artifact.size -eq 123 -and
    $RRT.report.inputs_digest -eq 'sha256:card' -and $RRT.report.exit_code -eq 0 -and
    $RRT.report.usage.total_tokens -eq 7)
Assert-True "b2②(★红线): RunReport **不含 verdict**（产出方不得自评 —— 契约 §1.1 的 ★）" (
    -not $RRT.report.Contains('verdict'))
Assert-True "b2③: gaps 如实报出本仓无读数的三项（attempt/decisions/evidence）" (
    (@($RRT.gaps) -join ',') -eq 'attempt,decisions,evidence')
Assert-True "b2④: RunReport 顶层**恰**八键（摘要逐字；多一个少一个都算漂）" (
    (@($RRT.report.Keys) -join ',') -eq 'run_id,attempt,artifact,inputs_digest,exit_code,decisions,evidence,usage')

$pcA = Resolve-D7PhaseChain -L1Verdict 'green' -L2Ran $true
$pcB = Resolve-D7PhaseChain -L1Verdict 'green' -L2Ran $false
$pcC = Resolve-D7PhaseChain -L1Verdict 'red'   -L2Ran $true
Assert-True "b2⑤: 相序列 —— L2 跑过 ⇒ 走 `sem_verified`；**没跑 ⇒ 跳过**（P4b 可选）" (
    ($pcA.states -join '>') -eq 'collected>mech_verified>sem_verified>accepted' -and
    ($pcB.states -join '>') -eq 'collected>mech_verified>accepted')
Assert-True "b2⑥: 终态 = `accepted` **iff L1=green**（L2 是 advisory ⇒ **不翻转**终态）" (
    $pcA.terminal -eq 'accepted' -and $pcC.terminal -eq 'rejected' -and $pcC.states[2] -eq 'sem_verified')
Assert-True "b2⑦(★非法跳自证): 相序列**从不**跳过 `mech_verified`（跳过 L1 = 红线 2 违规）" (
    $pcA.states[1] -eq 'mech_verified' -and $pcB.states[1] -eq 'mech_verified' -and
    $pcC.states[1] -eq 'mech_verified')

$l1T = [ordered]@{ verdict = 'green'; status = 'completed'; exit_code = 0; accept_passed = $true
                   golden_active = $false; golden_passed = $null; allowed_red = $false
                   record_sha256 = 'sha256:rec' }
$ccT = [ordered]@{ ok = $true; reasons = @(); verdict = 'accept'; findings_count = 2 }
$V1 = New-Verdict -ExitCode 0 -L1Section $l1T -L2Marks @($ccT)
Assert-True "b2⑧: Verdict.verdict = **整数**（exit code；★ 不是判官四值 —— 值类型即切分）" (
    ($V1.verdict.verdict -is [int]) -and $V1.verdict.verdict -eq 0)
Assert-True "b2⑨: phase/recorded_at/seq 在；`l1_results` = **原文照收**（复算凭据未丢）" (
    $V1.verdict.phase -eq 'P5' -and $V1.verdict.recorded_at -match '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$' -and
    $V1.verdict.seq -eq 1 -and $V1.verdict.l1_results.Count -eq 1 -and
    $V1.verdict.l1_results[0].verdict -eq 'green' -and
    $V1.verdict.l1_results[0].record_sha256 -eq 'sha256:rec')
Assert-True "b2⑩: `l2_marks` **可选** —— 传则有键、不传则**键不存在**（不是 null 占位）" (
    $V1.verdict.Contains('l2_marks') -and $V1.verdict.l2_marks[0].verdict -eq 'accept' -and
    -not (New-Verdict -ExitCode 0 -L1Section $l1T).verdict.Contains('l2_marks'))
Assert-True "b2⑪(如实): gaps 含 `seq`（摘要未给其语义 ⇒ 固定 1 是**占位不是真值**）" (
    (@($V1.gaps) -join ',') -eq 'seq')
Assert-True "b2⑫: 接线 —— P3 在**两处** `.agent-run.json` 写出点（主路 + claude 备路）" (
    ([regex]::Matches($content, [regex]::Escape("Write-D7Report -Kind 'RunReport'"))).Count -eq 2)
Assert-True "b2⑬: 接线 —— P5 在**两处** review 写出点，且 L2 没跑时**如实**传 -L2Ran false" (
    ([regex]::Matches($content, [regex]::Escape('Get-D7Adjudication -L1Section'))).Count -eq 2 -and
    $content.Contains('-L2Ran $false'))
Assert-True "b2⑭: 接线 —— 三个判据入口都被调（envelope / block / transition **各至少一处**）" (
    ([regex]::Matches($content, [regex]::Escape('--d7-envelope'))).Count -ge 1 -and
    ([regex]::Matches($content, [regex]::Escape('--d7-block'))).Count -ge 2 -and
    ([regex]::Matches($content, [regex]::Escape('--d7-transition'))).Count -ge 1)
# ★ 先验红自证（同源对照）：**同一份信封**，只多一个 `verdict` 键 ⇒ 两者必须不同
#   （= 证明 b2② 那条断言**真的在看**这个键，而不是恒真）。
$rrCopy = [ordered]@{}
foreach ($k in $RRT.report.Keys) { $rrCopy[$k] = $RRT.report[$k] }
$rrCopy['verdict'] = 0
Assert-True "b2⑮(先验红·同源对照): 加 `verdict` 的副本 与 真产物 **不同**（b2② 非恒真）" (
    $rrCopy.Contains('verdict') -and (-not $RRT.report.Contains('verdict')) -and
    (@($rrCopy.Keys).Count -eq @($RRT.report.Keys).Count + 1))

# --- b3 (2026-10-01, `O-136` **B3**): **P1/P2 状态名落站**（站上 `.agent-state.json` 词汇对齐契约）---
#   ★★ 本批的真实风险（也是主判据的由来）：旧孤儿判据**逐字比** `= running`，而写入侧现在不再
#     写 `running` ⇒ **只改写方 = 孤儿检测静默失效**（fail-open，本仓最防的形态）。
#     ⇒ 判据不只是"词对不对"，而是"**读侧是否与写侧同源**"。
#   ★ 口径：本块只测**接线形态 + 词汇守恒**（站上 bash 无法离线真跑）；相序列 / 判据本体那一半
#     由 `tests/test_rpc_check_d7_protocol.py` 覆盖 ⇒ **不在此抄第二份**（同 b1/b2 的切分口径）。
Assert-True "b3①: 唯一真值 —— 活跃态谓词**只定义一次**，两处 body 插值**同一变量**（不各写一份词表）" (
    ([regex]::Matches($content, [regex]::Escape("STATE_ACTIVE_ERE = '^(claimed|executing|running)$'"))).Count -eq 1 -and
    ([regex]::Matches($content, '\$activeEre\s*=\s*\$Script:STATE_ACTIVE_ERE')).Count -eq 2)
Assert-True "b3②(★主判据): 孤儿判据**不再逐字比** legacy 词，改用活跃态谓词，且**两处都改**" (
    -not $content.Contains('`$st" = running') -and
    ([regex]::Matches($content, [regex]::Escape('if echo "`$st" | grep -qE "$activeEre"'))).Count -eq 2)
Assert-True "b3③: 两个写入相各有**唯一真值来源**（P1 在 lock 函数 / P2 在任务体，各捕获一次局部名）" (
    $content.Contains('$stClaimed = $Script:STATE_CLAIMED') -and
    $content.Contains('$stExecuting = $Script:STATE_EXECUTING'))
Assert-True "b3④(★词汇守恒): 写入侧**不再产出** legacy 词 `running`；两个契约相各**恰一个**写入点" (
    ([regex]::Matches($content, [regex]::Escape('"state":"running"'))).Count -eq 0 -and
    ([regex]::Matches($content, [regex]::Escape('"state":"$stClaimed"'))).Count -eq 1 -and
    ([regex]::Matches($content, [regex]::Escape('"state":"$stExecuting"'))).Count -eq 1)
Assert-True "b3⑤(★legacy 可读): 活跃态集合**含** `running` ⇒ 残留 state 件的孤儿回收不会静默失效" (
    $content.Contains("STATE_ACTIVE_ERE = '^(claimed|executing|running)$'"))
Assert-True "b3⑥(★红线 1): 站上状态件**从不**写 D7 终态 —— 完成信号权只在主控站（产出方不得自评）" (
    -not $content.Contains('"state":"accepted"') -and -not $content.Contains('"state":"rejected"'))
Assert-True "b3⑦: 两个**非契约词**仍在（锁释放 / 孤儿回收 = 生命周期，**不是**相）" (
    $content.Contains('"state":"done"') -and $content.Contains('"state":"orphaned"'))
Assert-True "b3⑧(先验红·同源对照): b3④ 那条**真的在看** —— 同串放进样本里计数为 1，而真源件为 0" (
    ([regex]::Matches('x "state":"running" x', [regex]::Escape('"state":"running"'))).Count -eq 1 -and
    ([regex]::Matches($content, [regex]::Escape('"state":"running"'))).Count -eq 0)
Assert-True "b3⑨: 接线 —— 备路（claude 本地路）也落 P2 词，并**就地标注 PRM 冲突**（不静默放过）" (
    $content.Contains('+ $Script:STATE_EXECUTING +') -and $content.Contains('角色禁项 PRM'))

# --- b3 第二半 (2026-10-01, `O-136` **B3**): `PRH` 接线 + 四条按调用点接入（I-1/I-6/PRM/PRW）---
#   ★★ 本块的主判据 = "**四条不在 P5 一处堆**"（契约 §1.6 逐字：全堆在 P5 = **挂名接线**）
#      ⇒ 断言形态是"**每条恰一处调用点**"，不是"都调过"。
#   ★ 口径同 b1/b2/b3 前半：只测**接线形态 + 纯函数三态**（判据本体由 py 侧用例覆盖，不在此抄第二份）。
$hEmpty = Resolve-D7Hosts -Station ''
$hA = Resolve-D7Hosts -Station 'A'
$hB = Resolve-D7Hosts -Station 'B'
$hZ = Resolve-D7Hosts -Station 'Z'
Assert-True "b3⑩: `Resolve-D7Hosts` 三态 —— 站空 ⇒ 产出==裁决（本地跑=同机）· 站 A/B ⇒ 产出=站 host · 站 Z ⇒ 产出=''（不可判）" (
    $hEmpty.exec_host -eq $hEmpty.arbiter_host -and [bool]$hEmpty.exec_host -and
    $hA.exec_host -eq (Get-TargetHost 'A') -and $hB.exec_host -eq (Get-TargetHost 'B') -and
    $hZ.exec_host -eq '' -and [bool]$hZ.arbiter_host)
Assert-True "b3⑪(★不堆在 P5 · 主判据): 四条 `--d7-block` **各恰一处**调用点（I1 事件流写点 / I6 决策点 / PRM·PRW 角色动作点）" (
    ([regex]::Matches($content, [regex]::Escape("@('--d7-block', 'I1')"))).Count -eq 1 -and
    ([regex]::Matches($content, [regex]::Escape("@('--d7-block', 'I6')"))).Count -eq 1 -and
    ([regex]::Matches($content, [regex]::Escape("@('--d7-block', 'PRM')"))).Count -eq 1 -and
    ([regex]::Matches($content, [regex]::Escape("@('--d7-block', 'PRW')"))).Count -eq 1)
Assert-True "b3⑫: `I-1` 判据在**重试循环之前** ⇒ 只跑一次（放进循环会让重试次数变成判据调用次数）" (
    $content.IndexOf("@('--d7-block', 'I1')") -gt 0 -and
    $content.IndexOf("@('--d7-block', 'I1')") -lt $content.IndexOf('for ($i = 0; $i -lt 10; $i++) {'))
Assert-True "b3⑬: `PRH` 两侧事实落在**两处** `.agent-run.json` 写出点（主路 + claude 备路，同一实现）" (
    ([regex]::Matches($content, [regex]::Escape('Resolve-D7Hosts -Station'))).Count -eq 2 -and
    ([regex]::Matches($content, [regex]::Escape("Set-Content (Join-Path `$runDir '.agent-run.json')"))).Count -eq 2 -and
    ([regex]::Matches($content, [regex]::Escape('$run[''exec_host''] ='))).Count -eq 2 -and
    ([regex]::Matches($content, [regex]::Escape('$run[''arbiter_host''] ='))).Count -eq 2)
Assert-True "b3⑭: `--d7-host-sep` 已接 + **自家先判空**（argv 空值不可表达 ⇒ 不许把空串交给 CLI）+ 三态分支齐" (
    $content.IndexOf('if (-not $ExecHost -or -not $arb)') -gt 0 -and
    $content.IndexOf('if (-not $ExecHost -or -not $arb)') -lt $content.IndexOf("@('--d7-host-sep'") -and
    $content.Contains('D7_PRH_UNDECIDABLE') -and $content.Contains('D7_PRH_SAME') -and
    $content.Contains('D7_PRH_SEPARATE'))
Assert-True "b3⑮(先验红·同源对照): 四条分支产出**互不相同**（含 'Z' ⇒ ''）⇒ b3⑩ 非恒真（恒真桩会三态同值）" (
    $hEmpty.exec_host -ne $hA.exec_host -and $hA.exec_host -ne $hB.exec_host -and
    $hZ.exec_host -ne $hB.exec_host -and $hZ.exec_host -eq '' -and $hZ.station -eq 'Z')

# --- b3 第三刀 (2026-10-01, `O-136` **C 段首次真跑**): 两个**真缺陷**的回归护栏 -----------
#   ★★ 本块记的是"C 段第一次真跑就崩了"这件事本身 —— 两个缺陷**都不是**"判据错了"，
#      而是**外壳与判据的交界**错了（判据本体一直是对的）。四条 b3⑯/⑰ 就是那两处交界。
#   ⚠ 口径同前：本夹具只做**形态断言**（真跑需要站 + py 子进程 ⇒ 不在离线夹具里）。
Assert-True "b3⑯(★真缺陷①): JSON 入参**按入口分形态** —— `--d7-envelope` 收位置参数 / `--d7-block` 收 `--d7-ctx`，且未知入口 throw" (
    $content.Contains("'--d7-envelope' { , `$tmp }") -and
    $content.Contains("'--d7-block'    { '--d7-ctx'; `$tmp }") -and
    $content.Contains('D7_CLI_UNKNOWN_MODE') -and
    ([regex]::Matches($content, [regex]::Escape("@('--d7-ctx', `$tmp)")).Count -eq 0) -and
    -not $content.Contains('$a += $tmp'))
Assert-True "b3⑰(★真缺陷②): 末行提取**空管道安全** —— `.Trim()` 不许与 `[string](...)` 同表达式（PS 把方法落在内部管道上）" (
    $content.Contains('$line = ([string]$hit).Trim()') -and
    -not $content.Contains('[string]($out -split'))
# ★ 先验红自证（本机真跑 PS 解析规则）：旧写法在**空管道**上**确实会抛** ⇒ b3⑰ 非恒真。
$oldThrew = $false
try { $null = ([string]('' -split "`r?`n" | Where-Object { $_ -match '^D7_' } | Select-Object -Last 1)).Trim() }
catch { $oldThrew = $true }
Assert-True "b3⑱(先验红·同源对照): 旧写法在空管道上**当场抛**（b3⑰ 非恒真；恒真的断言在这里会红）" (
    $oldThrew -and $content.Contains('$line = ([string]$hit).Trim()'))
Assert-True "b3⑲(★真缺陷③): 无读数的两个**列表**字段填空 = **空数组**（`null` 会被判据当场拒 ⇒ P3 信封每次真跑都红）" (
    ($RRT.report.decisions -is [array]) -and @($RRT.report.decisions).Count -eq 0 -and
    ($RRT.report.evidence -is [array]) -and @($RRT.report.evidence).Count -eq 0 -and
    # ★ 同源对照：**仍是** gaps 里的三项（"类型合规" 不冒充 "有真值"）
    (@($RRT.gaps) -join ',') -eq 'attempt,decisions,evidence')

# --- b3 第四刀 (2026-10-01, `O-139` **甲**): P5 登记面落地 —— Verdict 段随 review.json 落盘 ----
#   ★★ 判据的由来：C 段真跑查出旧实现把 P5 跑在 `Set-Content` **之后** ⇒ 判据校验过的 `Verdict`
#      **只活在 stdout**（契约叫「裁决登记」而登记面是空的）⇒ 本刀的**唯一技术含量 = 顺序**。
#   ★ 口径同前：夹具只做**形态/顺序**断言（真跑要站 + py 子进程）。
# ⚠ 钉到**调用形态**（带 `-L1Section`）：只钉前半段会**把注释里的引用也算进去** ⇒ 计数失真（第一次就踩了）。
$inj = @([regex]::Matches($content, [regex]::Escape("`$review['d7_verdict'] = Get-D7Adjudication -L1Section")))
$wrt = @([regex]::Matches($content, [regex]::Escape('Set-Content $reviewPath')))
Assert-True "b3⑳(★O-139 甲·主判据): Verdict 段在**两处**写盘点**之前**注入（一次写盘；旧实现是写盘后才跑）" (
    $inj.Count -eq 2 -and $wrt.Count -eq 2 -and
    $inj[0].Index -lt $wrt[0].Index -and $inj[1].Index -lt $wrt[1].Index)
Assert-True "b3㉑(★O-139 甲): 组装点**只有一个**（`New-Verdict` 仅在 `Get-D7Adjudication` 内被调），且段**逐字取既有事实**" (
    ([regex]::Matches($content, [regex]::Escape('$d7v = New-Verdict -ExitCode'))).Count -eq 1 -and
    ([regex]::Matches($content, [regex]::Escape('Get-D7Adjudication -L1Section $l1Section -CcSection $ccSection'))).Count -eq 2 -and
    $content.Contains("return `$d7v['verdict']") -and
    # ★ 改名要**收干净**：旧名不许再作为**调用**出现（注释里提到旧名不算 —— 故钉 ` -L1Section`）
    ([regex]::Matches($content, [regex]::Escape('Write-D7Adjudication -L1Section'))).Count -eq 0)
# ★ 先验红·同源对照：把**旧顺序**（先写盘、后裁决）放进样本 ⇒ 同一条顺序判据必须**当场为假**
#   ⇒ 证明 b3⑳ 真的在看顺序，而不是恒真。
$oldOrder = "`$review | ConvertTo-Json -Depth 8 | Set-Content `$reviewPath`n`$review['d7_verdict'] = Get-D7Adjudication -L1Section `$l1Section"
$oldInj = [regex]::Matches($oldOrder, [regex]::Escape("`$review['d7_verdict'] = Get-D7Adjudication -L1Section"))
$oldWrt = [regex]::Matches($oldOrder, [regex]::Escape('Set-Content $reviewPath'))
# --- b3 第五刀 (2026-10-01, `O-140` **裁【甲·可机判版】**): 入链后再 review ⇒ 默认拦（可机判）------
#   ★★ 判据的由来（`O-140` 实测）：`review.json` 是链钉住的 subject，而 `review` 可重跑 ⇒ 对已入链的
#      run 写 review.json 会让门禁 `evidence` 报 `digest 不符` **FAIL**，且 `chain`（幂等去重）与
#      `--reanchor`（只重写锚）**都改不了已有条目** ⇒ 只能事后恢复。**本刀把它提前成"动手前判"**。
#   ★ 口径：判据本体 = **纯函数** `Resolve-RunChained` ⇒ 本块**真跑三态**（喂临时链件），
#      外加接线/顺序的**形态**断言（外壳那半起子进程，不进离线夹具）。
$chTmp = Join-Path $tmpCards 'chain-probe.json'
# ⚠ 链件是**对象**（`{entries:[…]}`），不是裸数组 —— 第一次就写错成裸数组，
#   而判据**当场报"判不了"**（不是静默放行）⇒ 这一条本身就是"形状不对 ⇒ fail-closed"的现场证据。
[IO.File]::WriteAllText($chTmp, '{"entries":[{"proj":"dogfood","run_id":"202601010000000001"},{"proj":"paper","run_id":"ts-b"}],"head":{"proj":"paper"}}', [Text.UTF8Encoding]::new($false))
$chHit = Resolve-RunChained -ChainPath $chTmp -Proj 'dogfood' -RunId '202601010000000001'
$chMiss = Resolve-RunChained -ChainPath $chTmp -Proj 'dogfood' -RunId '202601010000000099'
$chGone = Resolve-RunChained -ChainPath (Join-Path $tmpCards 'no-such-chain.json') -Proj 'dogfood' -RunId 'x'
[IO.File]::WriteAllText($chTmp, '{"head":{}}', [Text.UTF8Encoding]::new($false))
$chEmpty = Resolve-RunChained -ChainPath $chTmp -Proj 'dogfood' -RunId 'x'
Assert-True "b3㉓(★O-140 主判据): 三态不可混 —— 已在链内 ⇒ true · 不在 ⇒ false · 链件缺/无 entries ⇒ **不可判(null)**" (
    ($chHit.chained -eq $true) -and ($chMiss.chained -eq $false) -and
    ($null -eq $chGone.chained) -and ($null -eq $chEmpty.chained))
Assert-True "b3㉔(★fail-closed): 外壳对**不可判**按「已入链」处理 —— 条件必须是 -ne `$false（含 `$null`）" (
    $content.Contains("if (`$acChk['chained'] -ne `$false) {") -and
    $content.Contains('REJECT REVIEW_AFTER_CHAIN') -and $content.Contains('return 9'))
Assert-True "b3㉕(★顺序承重): 入链拦在**幂等守卫之后**（那个守卫不写盘 ⇒ 不该被拦）" (
    $content.IndexOf('REVIEW_IDEMPOTENT') -lt $content.IndexOf('REJECT REVIEW_AFTER_CHAIN'))
Assert-True "b3㉖: 显式通道**降级但留痕** —— `--allow-after-chain` 写进 review.json（**两处**写点各一）" (
    ([regex]::Matches($content, [regex]::Escape('if ($acSection) { $review[''after_chain_guard''] = $acSection }')).Count -eq 2) -and
    $content.Contains('REVIEW_AFTER_CHAIN_ALLOWED') -and
    $content.Contains('$AllowAfterChain') -and $content.Contains('[switch]$allowAfterChain'))
# ★ 先验红·同源对照：**恒 false 桩**（= "什么都不在链内"）在同一批样本上必须**当场红**
#   ⇒ 证明 b3㉓ 真的在看链内容，而不是恒真。
$stubSaysNotChained = { param($p, $j) @{ chained = $false; reason = 'stub' } }
$redHit = & $stubSaysNotChained $chTmp '202601010000000001'
Assert-True "b3㉗(先验红·同源对照): 恒 false 桩在「已在链内」样本上给出 false ⇒ b3㉓ 非恒真" (
    ($redHit.chained -eq $false) -and ($chHit.chained -eq $true))

# --- b3 第六刀 (2026-10-01, `O-136` 的「灰度转硬拒」前置): `gaps` 两分 ---------------------------
#   ★★ 由来（读码 + 契约核对）：契约 §1.6 的收紧条件写的是「对应信封的 `gaps` **清空** ⇒ 转硬拒」，
#      但 TaskContract 的 `constraints` 与 RunReport 的 `decisions` 属 §1.5 **射程边界（明令不判不补）**
#      ⇒ **永不消失** ⇒ 「清空」**按构造不可达**。「规则对、门槛错」—— 本刀只把两类**分开报**，
#      **不动门槛**（改门槛 = 待用户裁）。
$gTC = Split-D7Gaps -Gaps @('evidence_budget', 'constraints', 'golden.checksum')
$gRR = Split-D7Gaps -Gaps @('attempt', 'decisions', 'evidence')
$gVD = Split-D7Gaps -Gaps @('seq')
Assert-True "b3㉘(★主判据): 两分正确 —— TC 的 `constraints` 与 RR 的 `decisions` 归 **boundary**（永久不补）" (
    (@($gTC.boundary) -join ',') -eq 'constraints' -and
    (@($gRR.boundary) -join ',') -eq 'decisions' -and
    (@($gTC.open) -join ',') -eq 'evidence_budget,golden.checksum' -and
    (@($gRR.open) -join ',') -eq 'attempt,evidence' -and
    # ★ Verdict 无 boundary ⇒ 「唯一便宜的那条路」=（定义 seq 语义即可清）
    (@($gVD.boundary).Count -eq 0) -and (@($gVD.open) -join ',') -eq 'seq')
Assert-True "b3㉙(★fail-closed): **未登记的 gap 名 ⇒ unknown**，不许静默当成 open（那会高估「可清」）" (
    (@((Split-D7Gaps -Gaps @('brand.new.gap')).unknown) -join ',') -eq 'brand.new.gap' -and
    (@((Split-D7Gaps -Gaps @('brand.new.gap')).open).Count -eq 0))
Assert-True "b3㉚: 表**非空且只有两个值**（防空表 ⇒ 全落 unknown 的假绿；也防将来有人加第三个类而不说清）" (
    (@($Script:D7_GAP_CLASS.Keys).Count -ge 8) -and
    (@($Script:D7_GAP_CLASS.Values | Sort-Object -Unique) -join ',') -eq 'boundary,open')
Assert-True "b3㉛(★接线): 分类**只在一处**（唯一汇报壳），且分类行明示「不计入转硬拒门槛」" (
    ([regex]::Matches($content, [regex]::Escape('$gc = Split-D7Gaps -Gaps $Gaps')).Count -eq 1) -and
    $content.Contains('_GAPS_CLASS: ') -and $content.Contains('不计入「转硬拒」门槛'))
# ★ 先验红·同源对照：**恒 open 桩**（= "什么都能清"）在同一批样本上必须**当场红**
#   ⇒ 证明 b3㉘ 真的在看那张表，而不是恒真。
$stubAllOpen = { param($g) @{ open = @($g); boundary = @(); unknown = @() } }
$redOpen = & $stubAllOpen @('constraints')
# --- b3 第七刀 (2026-10-01, `O-136` **测收益的 ②**): D7 判据报数落点 ----------------------------
#   ★ 由来：`D7_*` 那些行此前**只走 stdout** ⇒「每千次 review 拦了多少」**算不出来**
#     （与 `O-139` 的 `Verdict` 只走 stdout **同病**，只是病在**报数面**）。
#   ★ 机制：`-GuardSink`（`IDictionary`）—— 靠 **PS 引用语义**把三态码写回调用方；
#     ⚠ **不用返回值**：那两个函数是**裸调用**的 ⇒ 加返回值会往管道吐对象，破**归零纪律**。
$sinkProbe = [ordered]@{}
function _sinkProbeFn { param([System.Collections.IDictionary]$Sink) $Sink['k'] = 7 }
_sinkProbeFn -Sink $sinkProbe
Assert-True "b3㉝(★口径自证): PS 引用语义成立 —— 被调方写 sink，**调用方看得见**（否则全部落点是空的假绿）" (
    ($sinkProbe['k'] -eq 7) -and ($sinkProbe -is [System.Collections.IDictionary]))
Assert-True "b3㉞(★类型坑): sink 形参必须是 `IDictionary` —— `[ordered]@{}` **不是** `[hashtable]`（写错会绑定失败）" (
    $content.Contains('[System.Collections.IDictionary]$GuardSink') -and
    -not $content.Contains('[hashtable]$GuardSink'))
Assert-True "b3㉟(★记录点齐): 九台判据各有一处入 sink（transition 记两键 + RL2/RL1/PRM/PRW/PRH + 信封·I6 由汇报壳记）" (
    ([regex]::Matches($content, '\$GuardSink\[')).Count -ge 8 -and
    $content.Contains("`$GuardSink['transition.rejected']") -and
    $content.Contains("`$GuardSink['completed'] = 1") -and
    # ★ 汇报壳两处入 sink（envelope / i6）—— 靠 `$Tag` 前缀区分用具名 tag
    ([regex]::Matches($content, [regex]::Escape('$GuardSink["$Tag.envelope"]')).Count -eq 1) -and
    ([regex]::Matches($content, [regex]::Escape('$GuardSink["$Tag.i6"]')).Count -eq 1))
Assert-True "b3㊱(★假绿防护): 报「跑完了」的 `completed` 标记**只在函数末尾** ⇒ 聚合能分开「没跑」与「跑了且全 ok」" (
    $content.IndexOf("`$GuardSink['completed'] = 1") -gt $content.IndexOf("`$GuardSink['PRH'] =") -and
    $content.IndexOf("`$GuardSink['completed'] = 1") -lt $content.IndexOf('return $d7v[''verdict'']'))
# ⚠⚠ **必须判【顺序】，不能只判【存在】**（2026-10-01 真跑当场抓到）：首版把注入行写在
#   `Get-D7Adjudication` **之前** ⇒ 那时 sink 还空 ⇒ `Count -gt 0` 为假 ⇒ **什么都没落盘**；
#   而**只计数**的断言照样全绿 —— 这就是"**假绿**"的教科书形态（同 `O-139` 的"顺序承重"家族）。
$sinkIdx = @(); foreach ($m in [regex]::Matches($content, [regex]::Escape('-GuardSink $d7g'))) { $sinkIdx += $m.Index }
$injIdx  = @(); foreach ($m in [regex]::Matches($content, [regex]::Escape('if ($d7g.Count -gt 0) { $review[''d7_guard''] = $d7g }'))) { $injIdx += $m.Index }
$wrtIdx  = @(); foreach ($m in [regex]::Matches($content, [regex]::Escape('Set-Content $reviewPath'))) { $wrtIdx += $m.Index }
Assert-True "b3㊲(★接线两处 + 顺序承重): 每处都是 sink → 注入 → 写盘（先注入后填充 = 空落盘，只计数会假绿）" (
    ($sinkIdx.Count -eq 2) -and ($injIdx.Count -eq 2) -and ($wrtIdx.Count -eq 2) -and
    ($sinkIdx[0] -lt $injIdx[0]) -and ($injIdx[0] -lt $wrtIdx[0]) -and
    ($sinkIdx[1] -lt $injIdx[1]) -and ($injIdx[1] -lt $wrtIdx[1]) -and
    # ⚠ 必须 `Escape`：`[ordered]` 在**正则**里是**字符类**（匹配单个 o/r/d/e）⇒ 不转义则计数为 0（本批踩到）
    ([regex]::Matches($content, [regex]::Escape('$d7g = [ordered]@{}')).Count -eq 1))
# ★ 先验红·同源对照：把**错顺序**（先注入、后填充）放进样本 ⇒ 同一条判据必须当场为假
$badOrder = "if (`$d7g.Count -gt 0) { `$review['d7_guard'] = `$d7g }`n-A' -GuardSink `$d7g  |  Set-Content `$reviewPath"
$bSink = [regex]::Matches($badOrder, [regex]::Escape('-GuardSink $d7g'))[0].Index
$bInj  = [regex]::Matches($badOrder, [regex]::Escape("if (`$d7g.Count -gt 0) { `$review['d7_guard'] = `$d7g }"))[0].Index
Assert-True "b3㊳(先验红·同源对照): **错顺序**样本上 `sink < 注入` 为假 ⇒ b3㊲ 非恒真" (
    -not ($bSink -lt $bInj))

# --- b3 第八刀 (2026-10-01, `O-136` 测收益的 ②·task 侧): 报数落进 `.agent-run.json` -----------------
#   ★ 为什么 task 侧必须另找落点：P0/P3/`I-1` 发生在**创建 `review.json` 之前**，且该 run
#     **可能永不 review** ⇒ 不落在 run 记录里就**永远算不出来**。
#   ★ 落 `.agent-run.json` **不破** `l1.record_sha256`：键在 run **写盘时一并落** ⇒ 它本来就是
#     run 的**原始字节**（⚠ 与 `O-139` 排除的"**事后**再写"**不是一回事**）。
$tSink = @(); foreach ($m in [regex]::Matches($content, [regex]::Escape("`$run['d7_guard'] = `$d7t"))) { $tSink += $m.Index }
$tSinkWrt = @(); foreach ($m in [regex]::Matches($content, [regex]::Escape("`$run | ConvertTo-Json -Depth 6 | Set-Content"))) { $tSinkWrt += $m.Index }
$tRep = @(); foreach ($m in [regex]::Matches($content, [regex]::Escape("-Tag 'RUNREPORT' -Card `$card ``"))) { $tRep += $m.Index }
Assert-True "b3㊴(★两处写点 + 顺序): 主路与 claude 备路**都**落 `d7_guard`，且**都在写盘之前**（先落键后写盘）" (
    ($tSink.Count -eq 2) -and ($tSinkWrt.Count -eq 2) -and
    ($tSink[0] -lt $tSinkWrt[0]) -and ($tSink[1] -lt $tSinkWrt[1]))
Assert-True "b3㊵(★顺序承重·主判据): P3 报数**挪到了写盘之前**（旧位置在写盘之后 ⇒ `RUNREPORT.*` 赶不上）" (
    ($tRep.Count -eq 2) -and
    ($tRep[0] -lt $tSinkWrt[0]) -and ($tRep[1] -lt $tSinkWrt[1]))
Assert-True "b3㊶(★P0 与 I1 入 sink): P0 的 `CONTRACT.*`（经汇报壳 `-GuardSink $d7t`）与 `I1`（经 Add-LedgerLine）都记" (
    # P0 一处 + 主路 P3 一处 + 备路 P3 一处 ≥3；`I1` 两处（主路 + 备路 ledger 追加）
    ([regex]::Matches($content, [regex]::Escape('-GuardSink $d7t')).Count -ge 3) -and
    ([regex]::Matches($content, [regex]::Escape("-Line `$line -GuardSink `$d7t")).Count -eq 2))
Assert-True "b3㊷(★备路带上 P0): `Add-LedgerLine` 与 `Invoke-Task-Claude` **都**收 sink ⇒ 备路 run 记录含 CONTRACT.*" (
    # 三个函数各有形参（汇报壳 / ledger / 备路）
    ([regex]::Matches($content, [regex]::Escape('[System.Collections.IDictionary]$GuardSink = $null')).Count -ge 3) -and
    # `Invoke-Task-Claude` 的**两处调用**都传（站路由路 + AUTO_FALLBACK 路）
    ([regex]::Matches($content, 'Invoke-Task-Claude[^\r\n]*-GuardSink \$d7t').Count -eq 2) -and
    # 备路内的 `$d7t = $GuardSink` 别名（缺省自建）—— 缺它则备路写的是一个**空的新 sink**
    ([regex]::Matches($content, [regex]::Escape('$d7t = $GuardSink')).Count -eq 1))
# ★ 先验红·同源对照：**写盘后**才落键的样本上，"键在写盘之前"必须为假
$badT = "`$run | ConvertTo-Json -Depth 6 | Set-Content x`nif (`$d7t.Count -gt 0) { `$run['d7_guard'] = `$d7t }"
$bW = [regex]::Matches($badT, [regex]::Escape("`$run | ConvertTo-Json -Depth 6 | Set-Content"))[0].Index
$bK = [regex]::Matches($badT, [regex]::Escape("`$run['d7_guard'] = `$d7t"))[0].Index
Assert-True "b3㊸(先验红·同源对照): **写盘后才落键**样本上 `键 < 写盘` 为假 ⇒ b3㊴ 非恒真" (
    -not ($bK -lt $bW) -and ($tSink[0] -lt $tSinkWrt[0]))
Assert-True "b3㉜(先验红·同源对照): 恒 open 桩把 constraints 也说成 open ⇒ b3㉘ 非恒真" (
    (@($redOpen.boundary).Count -eq 0) -and (@($gTC.boundary) -join ',') -eq 'constraints')
Assert-True "b3㉒(先验红·同源对照): **旧顺序**样本上同一条判据为假（b3⑳ 非恒真）" (
    ($oldInj.Count -eq 1) -and ($oldWrt.Count -eq 1) -and
    -not ($oldInj[0].Index -lt $oldWrt[0].Index))

Write-Host "--------------------------------"
Write-Host "FM_GOLDEN_TEST pass=$pass fail=$fail"
exit $(if ($fail -eq 0) { 0 } else { 1 })