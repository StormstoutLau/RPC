# _probe_fallback.ps1 - Injection live-probe for claude auto-fallback (O-15/AUDIT 2026-09-21)
# Drives the REAL Invoke-Task dispatch logic; stubs only the remote/site deps so the
# opencode main path returns rc=6 (engine-deadlock/timeout sentinel) WITHOUT a live site,
# then asserts the AUTO_FALLBACK branch fires and calls the REAL Invoke-Task-Claude.
# claude CLI is installed but UNAUTHENTICATED in this env => the backup run FAILS, but
# the v2 evidence (evidence_manifest + attach array + stderr/card/prompt archive) must
# still be emitted => proves "evidence is judgeable on a real failure", not faked.
# P0+P1 (2026-09-21): also drives the **sensitivity x backend** hard gate - 4 cases over
# (local-only | sanitized) x (direct -cli claude | AUTO_FALLBACK). All 4 must be REJECTED (rc=4)
# with NO claude run produced (that count is the outbound-side evidence). Mutation-tested: dropping
# either rule turns exactly its own 2 cases red while the other 2 stay green.
# Exit: 0 = pass, 1 = fail. Comments kept ASCII to avoid PS5.1 BOM/GBK parse traps.
# SilentlyContinue: bare collect scp to an OFFLINE site returns nonzero; under EAP=Stop that
# would throw before the fallback gate is reached. This is the known BatchMode OPEN-ISSUE
# (ssh/scp), not part of this change. We want the stubbed rc=6 path to COMPLETE and hit
# the fallback gate, so swallow the offline-scp native errors in the probe.
$ErrorActionPreference = 'SilentlyContinue'
$cliPath = 'd:\RPC\ops\station-bin\agent-cli.ps1'

# --- parse source (UTF8, BOM-safe) ---
$src = [System.IO.File]::ReadAllText($cliPath)
$tok = $null; $errs = $null
$ast = [System.Management.Automation.Language.Parser]::ParseInput($src, [ref]$tok, [ref]$errs)
if ($errs -and $errs.Count -gt 0) { throw "agent-cli.ps1 parse errors: $($errs | Out-String)" }
$fns = @($ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true))

# extract REAL pure functions we need (no site/file deps)
foreach ($nm in @('Get-FrontMatter','Get-CardIdentity','Test-CardSafetyDeclared','Get-Sha256Text',
                  'Get-Sha256Lines','Get-NumOr','Invoke-Scrubber','Merge-EvidenceSubjects',
                  'Get-FrameworkSubjects','Get-ClaudeFrameworkSubjects','Test-FallbackEligible',
                  'Get-SensitivityBackendReject',
                  'Resolve-ClaudeSpawn','Invoke-ClaudeFly','Resolve-LocalBash','Invoke-LocalBashCmd','Invoke-Task-Claude')) {
    $f = @($fns) | Where-Object { $_.Name -eq $nm } | Select-Object -First 1
    if (-not $f) { throw "$nm not found" }
    Invoke-Expression $f.Extent.Text
}
# extract Invoke-Task (the dispatch under test)
$it = @($fns) | Where-Object { $_.Name -eq 'Invoke-Task' } | Select-Object -First 1
if (-not $it) { throw 'Invoke-Task not found' }
Invoke-Expression $it.Extent.Text

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

# === 硬闸自证 (2026-09-21): sensitivity × **后端属性**, 两条出网路径各自判 ===
# 洞①(P0): 既有三处闸只判 `^opencode/`(把"出网"等同于"opencode/*"), 而 claude 备路(主控本地
#   spawn → ANTHROPIC_BASE_URL=云端 OpenRouter)**没有** sensitivity 判据 ⇒ local-only 卡的
#   prompt 可**实际出网**(破 DESIGN §358 路由不变式)。
# 洞②(P1): claude 备路两型号都是 **`:free`**, 而免费档端点**全部训练/不可 ZDR**(P1 实测:
#   `data_collection=deny` 与 `zdr` 均 404 `No endpoints found matching your data policy`)
#   ⇒ sanitized 卡的 prompt 会进"可能训练/公开发布"的 provider。**脱敏 ≠ 同意进公开数据集**。
# 两条路径(直接入口 / 自动兜底入口)是**独立入口** ⇒ 2 类 sensitivity × 2 条路径 = 4 例, 逐个自证。
# 判据用**出网侧证据**: claude 通道在发请求**前**必先落 `.agent-run.json`(cli=claude) ⇒
#   "claude run 计数不增"就是"未出网"的本地可判证据(计数若增 = 真发了请求; claude 现已带
#   OpenRouter key 授权, 会真出网)。
Write-Host ''
Write-Host '=== sensitivity x backend gate: local-only/sanitized must NOT reach the :free claude channel ==='
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

# 直接入口用 claude 型号; 兜底入口的主路用**站上本地引擎**型号(gpt-oss) —— 那正是洞②的真实场景
#   (非 `opencode/*` ⇒ 旧三处闸不拦)。
$cases = @(
    @{ tag = 'A local-only + -cli claude (直接入口) '; card = $cardLocal; sens = 'local-only'; cli = 'claude';   model = 'claude';  fb = $false },
    @{ tag = 'B local-only + AUTO_FALLBACK (兜底入口)'; card = $cardLocal; sens = 'local-only'; cli = 'opencode'; model = 'gpt-oss'; fb = $true  },
    @{ tag = 'C sanitized  + -cli claude (直接入口) '; card = $cardSanit; sens = 'sanitized'; cli = 'claude';   model = 'claude';  fb = $false },
    @{ tag = 'D sanitized  + AUTO_FALLBACK (兜底入口)'; card = $cardSanit; sens = 'sanitized'; cli = 'opencode'; model = 'gpt-oss'; fb = $true  }
)
foreach ($c in $cases) {
    $before = Count-ClaudeRuns
    $rc = Scalar (Invoke-Task -proj 'paper' -card $c.card -model $c.model -sensitive $c.sens -cli $c.cli -AutoFallback:$c.fb)
    $after = Count-ClaudeRuns
    if ($rc -eq 4 -and $after -eq $before) {
        Write-Host ('     PASS  ' + $c.tag + ': rc=4 且 claude run 数 ' + $before + '->' + $after + ' 未增(未出网)')
    } else {
        Write-Host ('     FAIL  ' + $c.tag + ': rc=' + $rc + ' claude run 数 ' + $before + '->' + $after + ' (期望 rc=4 且不增)')
        $ok = $false
    }
}

# (7e) 覆盖: 4 例对"零出网"这一结果是**同构**的(任一处闸生效都成立) ⇒ 只有覆盖断言能把
#      "哪一处闸在守"分辨开(与夹具的结构断言互补: 判据必须报覆盖率, 而不是"有个闸在跑")。
$callSig = 'Get-SensitivityBackendReject -sensitivity $sens -backendEgress $true'
$nCalls = ([regex]::Matches($src, [regex]::Escape($callSig))).Count
if ($nCalls -ge 2 -and $src.Contains('(claude-direct, $id)') -and $src.Contains('(fallback, $fbId)')) {
    Write-Host ('     PASS  coverage: 判据在两条路径均被调用(实测调用点 ' + $nCalls + ' 处) + 拒绝串可分辨路径')
} else {
    Write-Host ('     FAIL  coverage: 调用点 ' + $nCalls + ' 处(期望 >=2) 或拒绝串缺失'); $ok = $false
}

Write-Host '--------------------------------'
if ($ok) { Write-Host 'PROBE_FALLBACK pass'; exit 0 } else { Write-Host 'PROBE_FALLBACK FAIL'; exit 1 }