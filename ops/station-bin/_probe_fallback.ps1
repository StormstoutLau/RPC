# _probe_fallback.ps1 - Injection live-probe for claude auto-fallback (O-15/AUDIT 2026-09-21)
# Drives the REAL Invoke-Task dispatch logic; stubs only the remote/site deps so the
# opencode main path returns rc=6 (engine-deadlock/timeout sentinel) WITHOUT a live site,
# then asserts the AUTO_FALLBACK branch fires and calls the REAL Invoke-Task-Claude.
# claude CLI is installed but UNAUTHENTICATED in this env => the backup run FAILS, but
# the v2 evidence (evidence_manifest + attach array + stderr/card/prompt archive) must
# still be emitted => proves "evidence is judgeable on a real failure", not faked.
# P0 (2026-09-21): also drives the **sensitivity x backend** hard gate in BOTH directions -
# local-only x (direct -cli claude | AUTO_FALLBACK) must be REJECTED (rc=4, no claude run produced =
# the outbound-side evidence), while sanitized x (same two entries) must PASS THROUGH (claude run
# produced). The sanitized direction is a reverse guard: a "sanitized x trains" rule was added and
# then withdrawn the same day (see Get-SensitivityBackendReject for why) - re-adding it turns C/D red.
# Exit: 0 = pass, 1 = fail. Comments kept ASCII to avoid PS5.1 BOM/GBK parse traps.
# SilentlyContinue: bare collect scp to an OFFLINE site returns nonzero; under EAP=Stop that
# would throw before the fallback gate is reached. This is the known BatchMode OPEN-ISSUE
# (ssh/scp), not part of this change. We want the stubbed rc=6 path to COMPLETE and hit
# the fallback gate, so swallow the offline-scp native errors in the probe.
param(
    [switch]$SmokeOnly   # 2026-09-22: 只跑"提取清单齐备性"自检, 不派发/不触站/不起 claude ⇒ 供夹具冒烟
)
$ErrorActionPreference = 'SilentlyContinue'
$cliPath = 'd:\RPC\ops\station-bin\agent-cli.ps1'

# --- parse source (UTF8, BOM-safe) ---
$src = [System.IO.File]::ReadAllText($cliPath)
$tok = $null; $errs = $null
$ast = [System.Management.Automation.Language.Parser]::ParseInput($src, [ref]$tok, [ref]$errs)
if ($errs -and $errs.Count -gt 0) { throw "agent-cli.ps1 parse errors: $($errs | Out-String)" }
$fns = @($ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true))

# ── 提取**全部**函数定义 (2026-09-22, 取代原"硬编码函数名清单") ──────────────────────────
# 为什么改: 原实现用**硬编码清单**抽取, 而 agent-cli.ps1 每加一个被 `Invoke-Task` 调用的纯函数,
#   清单就漂移一次 ⇒ 探针**静默变死**（实测坏过 8 天: `Get-BackendEgress is not recognized`）。
#   先加"清单齐备性"自检能抓到漂移, 但**免维护**的解法是**根本不提清单**: 全部抽进来。
# ⚠ 为什么可行 —— **顺序即语义**: 本探针的 stub 与自身辅助函数**都定义在下面(晚于此处)**,
#   而 PS 里同名函数**后定义者胜** ⇒ stub 依旧生效。**这条顺序就是正确性的全部依据。**
# ⚠ 已核对: agent-cli.ps1 的 58 个函数**无一与内置 cmdlet 同名**(全是自定义名) ⇒ 不会遮蔽
#   本探针自身机制要用的 cmdlet。
foreach ($f in $fns) { Invoke-Expression $f.Extent.Text }

# ── 自检 (2026-09-22): 把"探针还活着"变成可判（静态、零派发；供夹具冒烟）────────────────
# 两条判据:
#   ① **存在性** —— `Invoke-Task` / `Invoke-Task-Claude` 都已在 agent-cli.ps1 里(没它们探针无从谈起);
#   ② **顺序不变量(要害)** —— 本文件里**每个** `function` 定义都必须**晚于**上面的提取边界;
#      否则它会被提取**覆盖**掉(例如某个 stub 被挪到边界之前 ⇒ 真函数接管 ⇒ 探针可能**真的去 ssh**,
#      而表面上一切正常)。⚠ 这条是"提取全部"**换来的新失效模式**, 所以必须同时给出判据。
$smokeFail = ''; $smokeInfo = ''
try {
    $probeTxt = [System.IO.File]::ReadAllText($MyInvocation.MyCommand.Path)
    $probeAst = [System.Management.Automation.Language.Parser]::ParseInput($probeTxt, [ref]$null, [ref]$null)
    $probeFnAsts = @($probeAst.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true))
    # 边界 = 本文件里**唯一**那处 `Invoke-Expression` 命令(即上面的提取行)
    $ieCmds = @($probeAst.FindAll({ param($n)
                $n -is [System.Management.Automation.Language.CommandAst] -and
                $n.GetCommandName() -eq 'Invoke-Expression' }, $true))
    $haveInCli = @($fns | ForEach-Object { $_.Name })
    $missing = @(@('Invoke-Task', 'Invoke-Task-Claude') | Where-Object { $haveInCli -notcontains $_ })
    if ($missing.Count -gt 0) {
        $smokeFail = ('agent-cli.ps1 里找不到: ' + ($missing -join ', ') + ' ⇒ 探针要驱动的那条链不在')
    } elseif ($ieCmds.Count -ne 1) {
        $smokeFail = ('提取边界不唯一: 本文件里有 ' + $ieCmds.Count + ' 处 Invoke-Expression(期望 1) ⇒ 自检无法定位边界')
    } else {
        $boundary = $ieCmds[0].Extent.StartOffset
        $early = @($probeFnAsts | Where-Object { $_.Extent.StartOffset -lt $boundary } | ForEach-Object { $_.Name })
        if ($early.Count -gt 0) {
            $smokeFail = ('顺序不变量破了: 下列函数定义在**提取边界之前**, 会被提取覆盖 ⇒ ' + ($early -join ', ') +
                          '（stub 被覆盖 = 探针可能真的去 ssh; 把它们挪到提取行之后）')
        } else {
            $smokeInfo = ('提取边界@' + $boundary + '; 本文件 ' + $probeFnAsts.Count + ' 个函数全部晚于边界(stub 有效); ' +
                          'agent-cli.ps1 已提取 ' + $fns.Count + ' 个函数(免维护: 不提清单)')
        }
    }
} catch {
    $smokeFail = '自检本身抛错: ' + $_.Exception.Message
}
if ($smokeFail) { Write-Host ('PROBE_SMOKE_FAIL: ' + $smokeFail); exit 1 }
Write-Host ('PROBE_SMOKE_OK: ' + $smokeInfo)
if ($SmokeOnly) { exit 0 }

# --- stub site/remote deps so opencode main path returns rc=124 -> 6 without a live site ---
function Get-TargetHost([string]$station) { return 'PROBE-A' }
function Resolve-Model([string]$m) {
    # mirror the real ROUTE_TABLE claude entries (2026-09-21: OpenRouter-served ids, NOT Claude-native)
    if ($m -eq 'claude' -or $m -eq 'thinkingmachines/inkling:free') { return @{ id='thinkingmachines/inkling:free'; station=''; cli='claude' } }
    # P0 止血自证用: 站上**本地引擎**型号 —— 非 `opencode/*` ⇒ 三处旧闸**不拦**(这正是洞的前提);
    #   走主路必然 ssh 到站上, 由 Invoke-RemoteScript stub 产出 rc=124→6。
    if ($m -eq 'gpt-oss') { return @{ id='local/gpt-oss-20b'; station='B'; cli='' } }
    return $null
}
function Resolve-Profile { param() return [pscustomobject]@{ profile='reason'; context=8192; max_output=1000; thinking='OFF'; template=''; reasoning_format=''; flavor=''; source='stub' } }
function Get-ThroughputEstimate { param() return @{ hit = $false } }
function Assert-AgentOutWritable { param() return $true }
function Invoke-StationReady { param() return @{ engine_ctx = 4096; raw = 'STATION_READY port=0' } }
function Invoke-SlotGate { param() return @{ na = $true; slot_total = 0; slot_busy = 0; slot_queue = 0 } }
function Invoke-Workspace { param() return $null }
function Invoke-RemoteScript { param() return 124 }   # simulate remote opencode timeout sentinel

# W3 步 1 (2026-09-22): 站上候选探查的**可观测桩** —— 它给出一条**行为性**判据: "被拒的卡是否零触站"。
#   为什么必须可观测: 探针环境里没有真实站 ⇒ 站上候选探查**本来就必然失败** ⇒ 若只用 "rc=4 + claude run
#   计数不增" 判, **新闸不存在时该用例照样 PASS**(因为探查循环随后也会走到 `local-only-no-station-engine`
#   并 rc=4) —— 那是"判据在跑, 但判的不是你以为的东西"(本项目已踩三次)。⇒ 用计数器把两者分开。
#   ⚠ 同时它把此前**未定义**的 `Test-StationEngineReady`(PS 里未定义命令在 if 条件中为假 ⇒ 旧行为是
#   "静默当假")变成显式 $false —— 行为等价, 但从此**可观测**。
$script:probeStationProbes = 0
function Test-StationEngineReady {
    param([string]$hostName, [string]$remoteUser, [string]$alias)
    $script:probeStationProbes++
    return $false
}

# 2026-09-21 加固(真实站实弹教训): 也让"远端证据回收"产出一个 `.meta`。
#   为什么必须加: 主路 collect 段有 `$m = Get-Content $metaTxt | Out-String`, 会把 `$m` **改写成
#   .meta 全文**。若不产 `.meta`, 该行不执行 ⇒ `$m` 保持为模型别名 ⇒ **本夹具对"fallback 把
#   .meta 文本当模型名"这一类回归完全不敏感**(首版正是如此, 是真实站实弹当场踩到 `REJECT unknown-model
#   (TASK_ID=…)` 才暴露)。加了它之后, 回归一旦发生 ⇒ `Resolve-Model <meta 文本>` 返回 $null ⇒
#   REJECT ⇒ 下面对"是否产出 claude run"的断言必 FAIL。
#   本函数覆盖真实 `ssh`(PS 里函数优先于外部命令), 只在证据批通道(命令行含 'FILE:')回 marker+base64。
function ssh {
    $all = ($args -join ' ')
    if ($all -match 'FILE:') {
        $meta = "TASK_ID=PROBE-SYNTHETIC`nQUEUE_S=2`nRUN_S=7`nTASK_RC=124`nACCEPT_OK=1`nACCEPT_GOLDEN_OK=1`nREVIEW_NEEDED=1`n"
        Write-Output 'FILE:.meta'
        Write-Output ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($meta)))
        Write-Output ''
    }
}

# --- script globals referenced by extracted functions / Invoke-Task ---
$probeProj = Join-Path $env:TEMP 'probe-proj'
# ⚠ **每次必须清空**: 否则"找最新的 claude run"会命中**上一次运行遗留**的 run ⇒ 断言**假 PASS**
#   (2026-09-21 负向自证当场踩到: 把 fallback 退回用 `$m` 的回归版**仍报 pass**, 因为上一轮
#   成功产出的 claude run 还在磁盘上被找到)。夹具的隔离性本身也是判据的一部分。
if (Test-Path $probeProj) { Remove-Item $probeProj -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Path $probeProj -Force | Out-Null
$Script:PROJECTS = @{ paper = $probeProj }
$Script:REPO_ROOT = 'd:\RPC'
$Script:WORKSPACE_ROOT = 'C:\Windows\Temp\probe-ws'
$Script:WORKSPACE_ARCHIVE_ROOT = 'C:\Windows\Temp\probe-arch'
$Script:TMP_ROOT = 'C:\Windows\Temp\probe-tmp'
$Script:ROUTE_TABLE = @{ 'claude' = @{ id='claude-sonnet-4-5'; station=''; cli='claude' } }

# helper: newest numeric run dirs only (exclude split-*, *_audits)
function Get-NumericRuns([string]$root) {
    return @(Get-ChildItem -Path $root -Directory | Where-Object { $_.Name -match '^\d{14,}$' } | Sort-Object Name -Descending)
}
# helper: scalarize a possibly polluted return value (stub leak only; take last), but the
#     authoritative signal is the on-disk run.json, not this int.
function Scalar([object]$v) { if ($v -is [array]) { return $v[@($v).Count - 1] }; return $v }

# --- env bridge check (exact line from agent-cli.ps1 task entry) ---
$env:AGENT_AUTO_FALLBACK = '1'
$autoFb = ($env:AGENT_AUTO_FALLBACK -eq '1')
if (-not $autoFb) { Write-Host 'FAIL env-bridge AGENT_AUTO_FALLBACK==1 did not map to true'; exit 1 }
Write-Host 'PASS  env-bridge AGENT_AUTO_FALLBACK=1 -> $autoFb=true'

# --- temp card with front-matter (model routes to local claude; positive safety gate) ---
$card = Join-Path $env:TEMP 'probe-fallback-card.md'
@"
---
proj: paper
task: probe claude auto-fallback (unauth claude => expected run failure, evidence v2)
model: claude
sensitivity: public
timeout_s: 5
continue-timeout-s: 3
accept:
  - true
---
## probe
reply with 'PASS'
"@ | Set-Content -Path $card -Encoding utf8

# --- run the REAL dispatch with AutoFallback forced ON, cli forced opencode ---
$capture = @()
try {
    $code = Invoke-Task -proj 'paper' -card $card -model 'claude' -sensitive 'public' -cli 'opencode' -AutoFallback:$true
} catch {
    Write-Host ("FAIL dispatch threw: " + $_.Exception.Message); exit 1
}
$code = Scalar $code
Write-Host ('dispatch exit=' + $code)

# --- assertions ---
$ok = $true
# (1) fallback actually ran: verified by a fresh claude run dir (Invoke-Task-Claude side effect).
#     claude channel runs locally (no site), so rc here = claude's finalCode (non-zero: unauth).
$outRoot = Join-Path $probeProj 'agent-out'
$newest = Get-NumericRuns $outRoot
$producedClaude = $false; $claudeRun = $null; $claudeTs = ''
foreach ($d in $newest) {
    $rj = Join-Path $d.FullName '.agent-run.json'
    if (Test-Path $rj) {
        $j = Get-Content $rj -Raw | ConvertFrom-Json
        if ($j.cli -eq 'claude') { $producedClaude = $true; $claudeRun = $j; $claudeTs = $d.Name; break }
    }
}
if (-not $producedClaude) { Write-Host 'FAIL no claude run produced (fallback did not invoke Invoke-Task-Claude)'; $ok = $false }
else {
    Write-Host ("PASS  claude run produced ts=" + $claudeTs)
    # (2) status failed (because claude unauth) - honest, not faked
    if ($claudeRun.status -ne 'failed' -and $claudeRun.status -ne 'timeout') {
        Write-Host ('WARN  claude run status=' + $claudeRun.status + ' (expected failed/timeout under unauth claude)')
    } else { Write-Host ('PASS  claude run status=' + $claudeRun.status + ' (honest failure, unauth claude)') }
    # (2b) 备路型号映射: 必须落到 claude 路由解析出的 id, **不能**是主路模型别名、更不能是 .meta 文本;
    #      且必须是 **OpenRouter 可服务的 id**(2026-09-21 实测: Claude 原生 id 经 OpenRouter 必 403 地区墙)。
    if ($claudeRun.model -eq 'thinkingmachines/inkling:free') {
        Write-Host 'PASS  claude run model=thinkingmachines/inkling:free (备路型号映射正确, 非 .meta 文本/非 Claude 原生 id)'
    } else {
        Write-Host ('FAIL  claude run model=' + $claudeRun.model + ' (期望 thinkingmachines/inkling:free)'); $ok = $false
    }
    # (3) evidence_manifest present => recipe v2 (the headline of this change)
    $evm = $claudeRun.evidence_manifest
    if (-not $evm -or -not @($evm.subjects).Count) {
        Write-Host 'FAIL claude run missing evidence_manifest (still recipe v1!)'; $ok = $false
    } else {
        Write-Host ('PASS  evidence_manifest v' + $evm.version + ' subjects=' + @($evm.subjects).Count)
        $names = @($evm.subjects | ForEach-Object { $_.name })
        if ($names -contains 'stderr' -and $names -contains 'card') { Write-Host 'PASS  claude baseline: stderr+card present' }
        else { Write-Host 'FAIL claude baseline missing stderr/card'; $ok = $false }
        if ($names -contains 'judgment-record' -or $names -contains 'attach-manifest') {
            Write-Host 'FAIL claude baseline leaked opencode-only items'; $ok = $false
        } else { Write-Host 'PASS  claude baseline: no opencode-only leak (stderr present, judgment-record/attach-manifest absent)' }
        # (§5.5.4 2026-09-22) review 件必须**在基线里且带 ephemeral** —— 这是本仓唯一能**离线**跑真实
        #   归档路径并读到 .agent-run.json 的地方 ⇒ 它给的是**行为证据**(夹具只证明纯函数返回值)。
        #   两个条件缺一不可: 不在 ⇒ `review` 写过 review.json 后变成 undeclared 缺口; 不带 ephemeral
        #   ⇒ 每个没 review 过的 claude run 都假报 missing-artifact(与本探针上面那条"泄漏"断言同为噪声判据)。
        $rv = @($evm.subjects | Where-Object { $_.name -eq 'review' })
        if ($rv.Count -eq 1 -and $rv[0].path -eq 'review.json' -and $rv[0].ephemeral -eq $true) {
            Write-Host 'PASS  claude baseline: review(review.json) present + ephemeral=true'
        } else {
            Write-Host ('FAIL  claude baseline: review 件缺或 ephemeral 非 true (count=' + $rv.Count + ')'); $ok = $false
        }
    }
    # (4) archived artifacts exist (stderr.txt, card.md, prompt.txt)
    $rd = Join-Path $outRoot $claudeTs
    foreach ($art in @('stderr.txt','card.md','prompt.txt','.agent-run.json')) {
        if (Test-Path (Join-Path $rd $art)) { Write-Host ("PASS  archived " + $art) } else { Write-Host ("FAIL  missing " + $art); $ok = $false }
    }
    # (4b) accept 的 shell 语义(O-15/AUDIT 2026-09-21): 备路用**本地 Git Bash**判 —— 卡的 accept 是
    #      bash 语义(`true`), 必须 rc=0。**回归检测**: 若退回 PowerShell `Invoke-Expression`,
    #      `true` 不是 PS 命令 ⇒ rc=1 ⇒ accept.passed=false ⇒ 本断言 FAIL(这就是本次修的 bug)。
    if ($claudeRun.accept.passed -eq $true) {
        Write-Host 'PASS  claude accept.passed=true (bash 语义判据在本地 Git Bash 下通过)'
    } else {
        Write-Host ('FAIL  claude accept.passed=' + $claudeRun.accept.passed + ' (期望 true; 退回 PS 会得 false)'); $ok = $false
    }
    $aot = Join-Path $rd 'accept-output.txt'
    if ((Test-Path $aot) -and ((Get-Content $aot -Raw) -match 'ACCEPT_RC\[1\]=0')) {
        Write-Host 'PASS  accept-output.txt 记 ACCEPT_RC[1]=0'
    } else {
        Write-Host 'FAIL  accept-output.txt 缺失 或 ACCEPT_RC[1] != 0'; $ok = $false
    }
    # (5) attach shape: array (may be empty for no-attach); must be present as array
    $att = $claudeRun.attach
    if ($null -eq $att) { Write-Host 'WARN  attach absent (null)'; } else { Write-Host ('PASS  attach is array type (' + $att.Count + ')') }
}

# (6) fallback gate semantics negative: with AutoFallback OFF, same rc=6 must NOT fallback.
#     Invoke a second dispatch without -AutoFallback and confirm the opencode run is produced
#     as the newest (i.e., Invoke-Task returned 6 and did NOT call claude).
Write-Host ''
Write-Host '=== negative gate: AutoFallback OFF, rc=6 should NOT call claude ==='
$env:AGENT_AUTO_FALLBACK = '0'
$code2 = Scalar (Invoke-Task -proj 'paper' -card $card -model 'claude' -sensitive 'public' -cli 'opencode' -AutoFallback:$false)
$newest2 = @(Get-NumericRuns $outRoot)[0]
$rj2 = Join-Path $newest2.FullName '.agent-run.json'
$cli2 = ''
if (Test-Path $rj2) { $cli2 = (Get-Content $rj2 -Raw | ConvertFrom-Json).cli }
if ($code2 -eq 6 -and $cli2 -eq 'opencode') { Write-Host 'PASS  gate-off: returned 6, newest run cli=opencode (no fallback)' }
else { Write-Host ("FAIL  gate-off: code=" + $code2 + " newest cli=" + $cli2); $ok = $false }

# === 硬闸自证 (2026-09-21): sensitivity × **后端出网性**, 两条出网路径各自判 ===
# 洞: 既有三处闸只判 `^opencode/`(把"出网"等同于"opencode/*"), 而 claude 备路(主控本地
#   spawn → ANTHROPIC_BASE_URL=云端 OpenRouter)**没有** sensitivity 判据 ⇒ local-only 卡的
#   prompt 可**实际出网**(破 DESIGN §358 路由不变式)。
# ⚠ 同日**撤回**了一条 `sanitized × 可能训练` 规则(理由见 Get-SensitivityBackendReject 留档) ⇒
#   本探针**双向守**: A/B 必须**被拒**(负例), C/D 必须**被放行且真在免费档产出 claude run**
#   (反向守卫 —— 谁再把那条无依据的闸加回来, C/D 立刻变红)。**C/D 会真发 2 个免费档请求**
#   (合成 prompt "reply with PASS") —— 这正是"放行"的实弹证据。
# 出网侧证据: claude 通道在发请求**前**必先落 `.agent-run.json`(cli=claude) ⇒
#   "claude run 计数"就是本地可判的出网计数器(拒 ⇒ 不增; 放行 ⇒ 必增)。
Write-Host ''
Write-Host '=== sensitivity x backend gate: local-only must be REJECTED; sanitized must PASS THROUGH ==='
function New-ProbeCard([string]$name, [string]$sens) {
    $p = Join-Path $env:TEMP "probe-$name-card.md"
    @"
---
proj: paper
task: probe $name backend gate
model: claude
sensitivity: $sens
timeout_s: 5
continue-timeout-s: 3
accept:
  - true
---
## probe
reply with 'PASS'
"@ | Set-Content -Path $p -Encoding utf8
    return $p
}
$cardLocal = New-ProbeCard 'localonly' 'local-only'
$cardSanit = New-ProbeCard 'sanitized' 'sanitized'

function Count-ClaudeRuns {
    $n = 0
    foreach ($d in @(Get-NumericRuns $outRoot)) {
        $rj = Join-Path $d.FullName '.agent-run.json'
        if (Test-Path $rj) { if ((Get-Content $rj -Raw | ConvertFrom-Json).cli -eq 'claude') { $n++ } }
    }
    return $n
}

# 直接入口用 claude 型号; 兜底入口的主路用**站上本地引擎**型号(gpt-oss) —— 那正是本洞的真实场景
#   (非 `opencode/*` ⇒ 旧三处闸不拦)。
# ⚠ 每个用例都**显式**给 `attach`: 因为 `@($null).Count` 在 PS 里是 **1**(不是 0) —— 若让缺省值漏进来,
#   `local-only` 的用例会被误判成"有附件"(进而走进站上附件同步分支, 在探针里必然失败)。
$cases = @(
    @{ tag = 'A local-only + -cli claude (直接入口) '; card = $cardLocal; sens = 'local-only'; cli = 'claude';   model = 'claude';  fb = $false; expect = 'reject'; attach = @(); probes = 'gt0' },
    @{ tag = 'B local-only + AUTO_FALLBACK (兜底入口)'; card = $cardLocal; sens = 'local-only'; cli = 'opencode'; model = 'gpt-oss'; fb = $true;  expect = 'reject'; attach = @() },
    @{ tag = 'C sanitized  + -cli claude (直接入口) '; card = $cardSanit; sens = 'sanitized'; cli = 'claude';   model = 'claude';  fb = $false; expect = 'allow';  attach = @() },
    @{ tag = 'D sanitized  + AUTO_FALLBACK (兜底入口)'; card = $cardSanit; sens = 'sanitized'; cli = 'opencode'; model = 'gpt-oss'; fb = $true;  expect = 'allow';  attach = @() }
    # ⚠ 原用例 E（`local-only` + claude + 附件）已**删除**：它当时验的是 W3 步 1 那道"一律拒绝"闸的
    #   **零触站**性质。步 2 把能力做了出来（站上建工作区 + 附件真的 scp 上去 + cwd 指过去）⇒ 该闸已撤,
    #   而**站上同步这条路径在探针环境里根本无法验**（没有真实站; scp 必然失败 ⇒ 会走 fail-closed 的
    #   rc=5 分支, 那验的是"网络失败"而不是"附件到位"）。⇒ 它的**行为证据由真实站实弹提供**
    #   （`local-only` + `-Cli claude` + `-Attach` ⇒ agent 真读到附件; 见 REMEDIATION-PLAN §W3 步 2）。
    #   ⚠ 这里刻意**不**留一个"看着像在验"的替身：那正是本项目反复吃过的"判据在跑, 判的不是你以为的"。
)
foreach ($c in $cases) {
    $before = Count-ClaudeRuns
    $script:probeStationProbes = 0
    $rc = Scalar (Invoke-Task -proj 'paper' -card $c.card -model $c.model -sensitive $c.sens -cli $c.cli -AutoFallback:$c.fb -attach $c.attach)
    $after = Count-ClaudeRuns
    if ($c.expect -eq 'reject') {
        if ($rc -eq 4 -and $after -eq $before) {
            Write-Host ('     PASS  ' + $c.tag + ' [拒]: rc=4 且 claude run 数 ' + $before + '->' + $after + ' 未增(未出网)')
        } else {
            Write-Host ('     FAIL  ' + $c.tag + ' [拒]: rc=' + $rc + ' claude run 数 ' + $before + '->' + $after + ' (期望 rc=4 且不增)')
            $ok = $false
        }
    } else {
        if ($after -gt $before -and $rc -ne 4) {
            Write-Host ('     PASS  ' + $c.tag + ' [放行]: claude run 数 ' + $before + '->' + $after + ' 已增(真到免费档); rc=' + $rc)
        } else {
            Write-Host ('     FAIL  ' + $c.tag + ' [放行]: rc=' + $rc + ' claude run 数 ' + $before + '->' + $after + ' (期望计数增加且 rc<>4 ⇒ 不许把撤回的闸加回来)')
            $ok = $false
        }
    }
    # ⚠⚠ **正对照(没有它,"0 次"可能是恒真的)**: 若计数器/探查循环根本没在跑, 这类 `= 0` 会**永远 PASS**
    #   ⇒ 那是"判据在跑, 但判的不是你以为的东西"(本项目已踩三次)。⇒ 必须有**一个已知会触碰站**的用例
    #   (A: local-only + claude, 无附件 ⇒ 走到候选探查)把计数证明成 **> 0**。
    if ($c.probes -eq 'gt0') {
        if ($script:probeStationProbes -gt 0) {
            Write-Host ('     PASS  ' + $c.tag + ' [正对照]: 站上候选探查 ' + $script:probeStationProbes + ' 次(>0) ⇒ 计数器是活的, 故 E 的"0 次"有意义')
        } else {
            Write-Host ('     FAIL  ' + $c.tag + ' [正对照]: 站上候选探查 0 次(期望 >0) ⇒ 计数器或探查循环没在跑 ⇒ E 的"零触站"断言恒真、不可信'); $ok = $false
        }
    }
}

# (7e) 覆盖: 4 例对"是否出网"这一结果在**同一类**内是同构的(任一处闸生效都成立) ⇒ 只有覆盖断言能把
#      "哪一处闸在守"分辨开(与夹具的结构断言互补: 判据必须报覆盖率, 而不是"有个闸在跑")。
# ⚠ (2026-09-22) **本判据第一版已过时，且过时方向很危险** —— 它数的是**字面量**
#    `Get-SensitivityBackendReject -sensitivity $sens -backendEgress $true` 出现 >=2 次。
#    而 W1a 的**全部用意**就是把硬编码 `$true` 换成**后端属性判据** `(Get-BackendEgress $id)`
#    （故意只留兜底入口那 1 处 `$true`，因它在主控本地=云端=出网）⇒ 实测该字面量只剩 **1** 处。
#    ⇒ 继续用它，等于要求"把属性判据改回硬编码"（**判据与设计反向**）。这与夹具那条"位置断言被注释骗"
#    同族：**文本判据会随实现改进而静默变成错误的要求**。改为按**当前设计**判：判据在 `Invoke-Task`
#    体内被调用 **>=2 次**（直接入口 + 兜底入口），且两处拒绝串可分辨是哪条路径。
# ⚠ (2026-09-22) 本判据原先读的是 `$it`(提取 Invoke-Task 时留下的 AST 变量) —— 改成"提取全部"后
#   那个变量被删掉了 ⇒ 计数变**空** ⇒ 本断言当场红(rc=1)。**这次是判据自己抓到了重构漏改的引用**
#   (而它红得"对": 空值 -ge 2 为假)。⇒ 改为**就地**取 AST, 不再依赖别处的中间变量。
$itAst = @($fns | Where-Object { $_.Name -eq 'Invoke-Task' }) | Select-Object -First 1
$nCalls = if ($itAst) { @($itAst.FindAll({ param($n)
        $n -is [System.Management.Automation.Language.CommandAst] -and
        $n.GetCommandName() -eq 'Get-SensitivityBackendReject' }, $true)).Count } else { -1 }
if ($nCalls -ge 2 -and $src.Contains('(claude-direct, $id)') -and $src.Contains('(fallback, $fbModel)')) {
    Write-Host ('     PASS  coverage: 判据在 Invoke-Task 体内调用 ' + $nCalls + ' 处(直接入口+兜底入口) + 拒绝串可分辨路径')
} else {
    Write-Host ('     FAIL  coverage: Invoke-Task 体内调用点 ' + $nCalls + ' 处(期望 >=2) 或拒绝串缺失'); $ok = $false
}

Write-Host '--------------------------------'
if ($ok) { Write-Host 'PROBE_FALLBACK pass'; exit 0 } else { Write-Host 'PROBE_FALLBACK FAIL'; exit 1 }