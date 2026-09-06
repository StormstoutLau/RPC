# ============================================================================
# agent-cli.ps1 - D6 agent-cli wrapper (Microsoft PowerShell 5.1)
# Main console -> two-node agent CLI cross-project invocation.
# T1 scope (D6 IMPL v1.2): skeleton + ROUTE_TABLE + Invoke-RemoteScript + workspace cmd
#   workspace <proj> --create | --sync | --archive
#   (task cmd in T3; review/collect phase 2)
# Rules (D6): R14 remote cmd always script-on-disk; tar = Git Bash GNU tar (S1);
#             .agentsync patterns -> --exclude; NOTE: source kept ASCII-only for PS5.1
# ============================================================================

[CmdletBinding()]
param(
    [Parameter(Position=0)][string]$Command = '',
    [Parameter(Position=1)][string]$Proj = '',
    [switch]$Create,
    [switch]$Sync,
    [switch]$Archive,
    [string]$Type = '',          # .agentsync template: python|cpp|doc|lean4
    [string]$HostName = '',      # target station override: B|A (default B)
    [string]$KeyFile = '',       # ssh key (optional)
    [string]$Model = '',         # route cmd: model alias or full id
    [string]$Sensitivity = '',   # route cmd: public|sanitized|local-only
    [string]$Act = '',           # lock cmd: acquire|release|status
    [int]$Hold = 0,              # lock cmd: seconds to hold after acquire (A9 test)
    [string]$RemoteHost = '',    # lock cmd: actual remote host; default B
    [string]$Card = '',          # task cmd: path to task card md
    [string[]]$Attach = @(),     # task cmd: attachment files/dirs -> workspace .attach/ (O-01)
    [string]$Complexity = '',    # task cmd: auto|short|standard|long -> 6.4 complexity profile
    [string]$TaskType = ''       # task cmd: code|reason|concept|numeric|doc -> 6.4 thinking/template
)

# ---------------- constants / env ----------------
$ErrorActionPreference = 'Stop'
$Script:GNU_TAR = 'C:\Program Files\Git\usr\bin\tar.exe'   # S1: not Win10 bsdtar
$Script:REMOTE_USER = 'scott-lau'
$Script:WORKSPACE_ROOT = '/home/scott-lau/agent-workspaces'
$Script:PROJECTS = @{ paper = 'D:\Paper' }    # console project root mapping
$Script:TMP_ROOT = Join-Path $env:TEMP 'agent-cli'

# ---------------- ROUTE_TABLE (BP-2 alias->full-id, T3 task uses; fixed here) ----------------
# NOTE (ADR-0002, 2026-09-04): 'cluster-litellm/*' provider 已在 B 站 opencode.jsonc 中 baseURL
# 直连 127.0.0.1:8080（绕开 LiteLLM 网关 :4000，key=sk-unsloth-...），语义不再经网关。id 字符串
# 保持不变以匹配 opencode 模型 id（provider/model），仅其底层 baseURL 更改为直连。
$Script:ROUTE_TABLE = @{
    # alias -> @{ id=full-id; station=target }
    'nemotron'   = @{ id = 'cluster-litellm/nemotron';                          station = 'B' }
    'gpt-oss'    = @{ id = 'cluster-litellm/gpt-oss';                           station = 'A' }
    'lightning'  = @{ id = 'opencode/nemotron-3.5-lightning-free';              station = 'B' }
    'ultra'      = @{ id = 'opencode/nemotron-3-ultra-free';                    station = 'B' }
    'free-1m'    = @{ id = 'opencode/nemotron-3-ultra-free';                    station = 'B' }  # alias of ultra
    # full id directly (M3 dual representation)
    'cluster-litellm/nemotron'              = @{ id = 'cluster-litellm/nemotron';              station = 'B' }
    'cluster-litellm/gpt-oss'               = @{ id = 'cluster-litellm/gpt-oss';               station = 'A' }
    'opencode/nemotron-3.5-lightning-free'  = @{ id = 'opencode/nemotron-3.5-lightning-free';  station = 'B' }
    'opencode/nemotron-3-ultra-free'        = @{ id = 'opencode/nemotron-3-ultra-free';        station = 'B' }
}

# ---------------- .agentsync four-type templates (T1, F3) ----------------
$Script:AGENTSYNC_TEMPLATES = @{
    python = @('__pycache__/', '.venv/', '*.egg-info/', 'raw_md/', 'new_papers/', '*.duckdb', '.git/', 'out/', '.agent-lock', '.agent-state.json', '.attach/')
    cpp    = @('build/', 'third_party/', '*.o', '.git/', 'out/', '.agent-lock', '.agent-state.json', '.attach/')
    doc    = @('.git/', 'out/', '.agent-lock', '.agent-state.json', '.attach/')
    lean4  = @('.lake/', '.git/', 'out/', '.agent-lock', '.agent-state.json', '.attach/')
}

# ---------------- helpers ----------------

function Get-TargetHost([string]$station) {
    if ($station -eq 'A') { return 'scott-lau-NEX.local' }
    return 'scott-lau-GTR-Pro.local'   # B default (memory master)
}

function Test-RemoteReach([string]$hostName) {
    # PS5.1 landmine (confirmed 2026-09-03): native stderr redirect (2>$null) under EAP=Stop
    # throws NativeCommandError (e.g. DNS failure text) instead of returning - treat any throw as unreachable.
    try {
        $r = ssh -o ConnectTimeout=8 -o BatchMode=yes $hostName 'echo alive' 2>$null
        return ($LASTEXITCODE -eq 0 -and "$r" -match 'alive')
    }
    catch { return $false }
}

function Invoke-RemoteScript {
    # R14: only ssh egress. Generate local bash script -> scp -> ssh bash
    [CmdletBinding()]
    param(
        [string]$HostName,
        [string]$ScriptBody,
        [string]$LocalName
    )
    if (-not (Test-RemoteReach $HostName)) {
        # ssh reach failure -> retry once (inv 7 gate-cache: network-only retry per DESIGN §4.5/F7)
        Write-Output '[retry] remote reach failed, retry once'
        Start-Sleep -Seconds 2
    }
    if (-not (Test-RemoteReach $HostName)) { throw "NETFAIL: remote unreachable: $HostName (ensure station online)" }
    if (-not $LocalName) { $LocalName = "agent-cli-run-$([DateTime]::Now.ToString('HHmmss')).sh" }

    $localPath = Join-Path $Script:TMP_ROOT $LocalName
    if (-not (Test-Path $Script:TMP_ROOT)) { New-Item -ItemType Directory -Path $Script:TMP_ROOT -Force | Out-Null }
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($localPath, $ScriptBody, $utf8NoBom)

    scp -q -o ConnectTimeout=10 $localPath "${HostName}:/tmp/${LocalName}"
    if ($LASTEXITCODE -ne 0) { throw "NETFAIL: scp failed: $LocalName" }

    # PS5.1: 2>&1 under EAP=Stop throws NativeCommandError when ssh writes stderr (network fail
    # confirmed 2026-09-03) - catch and classify by message, then by rc.
    try {
        $sshOut = ssh -o ConnectTimeout=10 $HostName "bash /tmp/${LocalName}" 2>&1
        $code = $LASTEXITCODE
    }
    catch {
        $sshOut = @("$($_.Exception.Message)")   # NativeCommandError text (e.g. DNS failure)
        $code = 255
    }
    # ssh network-level failure -> retry once (inv 7 gate-cache: retry does NOT re-run scrubber; only network retry per DESIGN §4.5/F7)
    if ($code -ne 0 -and ($sshOut -match 'Could not resolve hostname|Connection (refused|timed out|reset)|Network is unreachable|port 22')) {
        Write-Host "[retry] ssh network failure (rc=$code), retry once (gate-cache: scrubber not re-run)"
        Start-Sleep -Seconds 2
        try {
            $sshOut = ssh -o ConnectTimeout=10 $HostName "bash /tmp/${LocalName}" 2>&1
            $code = $LASTEXITCODE
        }
        catch {
            $sshOut = @("$($_.Exception.Message)")
            $code = 255
        }
        # P2-2 (D6 audit): still network-class after retry => terminal network failure -> exit code 5 (DESIGN §8)
        if ($code -ne 0 -and ($sshOut -match 'Could not resolve hostname|Connection (refused|timed out|reset)|Network is unreachable|port 22')) {
            throw "NETFAIL: ssh exec failed after retry (rc=$code, host=$HostName)"
        }
    }
    foreach ($ln in $sshOut) { Write-Host $ln }   # stream remote stdout to console, NOT into return value
    Remove-Item $localPath -ErrorAction SilentlyContinue
    return $code
}

function Invoke-StationReady {
    # O-19 (2026-09-05): station env-ready gate BEFORE dispatch.
    # Root cause was port-topology drift: 8080 = unsloth studio (mgmt, auth) while the
    # llama-server OpenAI engine lands on a RANDOM per-load port. opencode baseURL=8080
    # hit mgmt -> "Cannot connect to API".
    # Fix: run _station_ready.sh on target station -> discover engine port -> verify
    # /v1/models+chat -> idempotently inject cluster-litellm baseURL to that port.
    # (source kept ASCII-only for PS5.1 BOM safety)
    [CmdletBinding()]
    param(
        [string]$HostName,
        [string]$Alias
    )
    if (-not (Test-RemoteReach $HostName)) { throw "NETFAIL: station unreachable: $HostName" }
    $local = 'D:\RPC\ops\station-bin\_station_ready.sh'
    $tmp = Join-Path $Script:TMP_ROOT '_station_ready.sh'
    New-Item -ItemType Directory -Path $Script:TMP_ROOT -Force | Out-Null
    Copy-Item $local $tmp -Force
    scp -q -o ConnectTimeout=10 $tmp "${HostName}:/tmp/_station_ready.sh"
    if ($LASTEXITCODE -ne 0) { throw "NETFAIL: scp _station_ready.sh failed" }
    $arg = if ($Alias) { " '$Alias'" } else { '' }
    try {
        $out = ssh -o ConnectTimeout=10 $HostName "bash /tmp/_station_ready.sh$arg" 2>&1
        $code = $LASTEXITCODE
    }
    catch {
        $out = @("$($_.Exception.Message)")
        $code = 255
    }
    foreach ($ln in $out) { Write-Host $ln }
    $joined = $out -join "`n"
    if ($code -ne 0) {
        if ($joined -match 'ERR_NO_ENGINE') { throw "STATION_NOT_READY: engine not loaded ($HostName) - run load-mem-gate + infer-load first" }
        throw "STATION_NOT_READY: inject failed rc=$code ($HostName)"
    }
    if ($joined -notmatch 'INJECT_OK' -or $joined -notmatch 'STATION_READY port=') { throw "STATION_NOT_READY: injection not confirmed ($HostName)" }
    return $true
}

# ---------------- Invoke-Workspace (M1) ----------------

function Get-AgentsyncExcludes([string]$proj, [string]$type) {
    $projRoot = $Script:PROJECTS[$proj]
    if (-not $type) { $type = 'python' }   # default (Paper pilot)
    $src = $null
    if ($projRoot) { $asPath = Join-Path $projRoot '.agentsync'; if (Test-Path $asPath) { $src = $asPath } }
    if (-not $src) {
        $tmpl = $Script:AGENTSYNC_TEMPLATES[$type]
        if (-not $tmpl) { $tmpl = $Script:AGENTSYNC_TEMPLATES['python'] }
        return $tmpl
    }
    return (Get-Content $src | Where-Object { $_ -and (-not $_.StartsWith('#')) })
}

function Convert-ToExcludeArgs([string[]]$patterns) {
    $args = @()
    foreach ($p in $patterns) {
        $p = $p.Trim().TrimEnd('/')
        if ($p) { $args += "--exclude=$p"; $args += "--exclude=$p/" }
    }
    return $args
}

function Invoke-Workspace {
    param([string]$proj, [string]$act, [string]$type, [string]$Station = '')
    $projRoot = $Script:PROJECTS[$proj]
    if (-not $projRoot -or -not (Test-Path $projRoot)) { throw "unknown/missing project: $proj (registered: $($Script:PROJECTS.Keys -join ','))" }
    # station resolution: explicit Station parameter wins; else bind caller's script-level $HostName ('A'/'B');
    # else default B. Never trust a bare $HostName here: through PowerShell dynamic scope it may be an
    # Invoke-Task $hostName SSH string (e.g. scott-lau-NEX.local) that is not 'A'/'B' -> silent B-target bug.
    $station = if ($Station) { $Station } elseif ($HostName -in @('A','B')) { $HostName } else { 'B' }
    $hostName = Get-TargetHost $station

    if ($act -eq 'create') {
        # 1. build skeleton (AGENTS.md/CLAUDE.md/.agentsync/out) in local staging
        $stag = Join-Path $env:TEMP "agent-cli-stag-$proj"
        if (Test-Path $stag) { Remove-Item $stag -Recurse -Force }
        New-Item -ItemType Directory -Path "$stag\out" -Force | Out-Null

        $agentsSrc = Join-Path $projRoot 'AGENTS.md'
        $agentsDst = Join-Path $stag 'AGENTS.md'
        if (Test-Path $agentsSrc) { Copy-Item $agentsSrc $agentsDst } else {
            $marker = "# $proj project instructions`n`n## marker`n$([DateTime]::Now.ToString('yyyMMdd'))-$proj single source of project instructions.`n"
            [System.IO.File]::WriteAllText($agentsDst, $marker, (New-Object System.Text.UTF8Encoding $false))
        }
        $claude = "@AGENTS.md`n`n($proj D6 workspace thin-shell)`n"
        [System.IO.File]::WriteAllText((Join-Path $stag 'CLAUDE.md'), $claude, (New-Object System.Text.UTF8Encoding $false))
        $excl = Get-AgentsyncExcludes $proj $type
        [System.IO.File]::WriteAllLines((Join-Path $stag '.agentsync'), $excl, (New-Object System.Text.UTF8Encoding $false))

        # 2. tar skeleton (full: AGENTS.md/CLAUDE.md/.agentsync/out)
        $tarFile = Join-Path $env:TEMP "agent-cli-create-$proj.tar"
        if (Test-Path $tarFile) { Remove-Item $tarFile -Force }
        Push-Location $stag
        try {
            & $Script:GNU_TAR --force-local -cf $tarFile AGENTS.md CLAUDE.md .agentsync out
            if ($LASTEXITCODE -ne 0) { throw 'tar skeleton pack failed' }
        } finally { Pop-Location }

        # 3. scp
        scp -q -o ConnectTimeout=10 $tarFile "${hostName}:/tmp/agent-cli-create-$proj.tar"
        if ($LASTEXITCODE -ne 0) { throw "NETFAIL: scp skeleton failed" }

        # 4. remote mkdir + extract
        $body = @"
set -eu
W="$Script:WORKSPACE_ROOT/$proj"
mkdir -p "`$W"
cd "`$W"
tar -xf /tmp/agent-cli-create-$proj.tar -C "`$W"
mkdir -p out
echo '--- workspace files:'
find "`$W" -maxdepth 2 -type f | sort
echo '--- md5 (AGENTS.md/CLAUDE.md/.agentsync):'
md5sum AGENTS.md CLAUDE.md .agentsync
"@
        Invoke-RemoteScript -HostName $hostName -ScriptBody $body -LocalName "agent-cli-ws-create.sh"
        # 5. local md5 for comparison
        $mdLocal = (Get-FileHash (Join-Path $stag 'AGENTS.md') -Algorithm MD5).Hash.ToLower()
        Write-Host "Local AGENTS.md md5: $mdLocal"
    }
    elseif ($act -eq 'sync') {
        # incremental push source subset per .agentsync; never overwrite out/ (unidirectional, inv 6)
        $excl = Get-AgentsyncExcludes $proj $type
        $exArgs = Convert-ToExcludeArgs $excl
        $tarFile = Join-Path $env:TEMP "agent-cli-sync-$proj.tar"
        if (Test-Path $tarFile) { Remove-Item $tarFile -Force }
        Push-Location $projRoot
        try {
            $tarArgs = @('-cf', $tarFile, '--force-local') + $exArgs + @('.')
            & $Script:GNU_TAR @tarArgs
            if ($LASTEXITCODE -ne 0) { throw "tar sync failed (rc=$LASTEXITCODE; trim .agentsync if exceed)" }
        } finally { Pop-Location }
        $size = (Get-Item $tarFile).Length
        if ($size -gt 200MB) { throw "sync pkg $([math]::Round($size/1MB,1))MB > 200MB cap, add excludes (G4)" }
        scp -q -o ConnectTimeout=10 $tarFile "${hostName}:/tmp/agent-cli-sync-$proj.tar"
        if ($LASTEXITCODE -ne 0) { throw "NETFAIL: scp sync failed (rc=$LASTEXITCODE) - station likely down" }
        $body = @"
set -eu
W="$Script:WORKSPACE_ROOT/$proj"
mkdir -p "`$W"
cd "`$W"
tar -xf /tmp/agent-cli-sync-$proj.tar -C "`$W"
echo "sync OK: `$(du -sh "`$W" | cut -f1)"
"@
        Invoke-RemoteScript -HostName $hostName -ScriptBody $body -LocalName "agent-cli-ws-sync.sh"
    }
    elseif ($act -eq 'archive') {
        Write-Host "archive (T1 placeholder): archive $Script:WORKSPACE_ROOT/$proj to timestamp snapshot; memory stays on node"
    }
    else { throw "unknown workspace action: $act (create|sync|archive)" }
}

# ---------------- M3 router ----------------

function Resolve-Model {
    # returns hashtable @{ id; station } or $null if resolution fails (unknown alias/id)
    param([string]$model)
    if (-not $model) { return $null }
    $name = $model.Trim()
    if ($Script:ROUTE_TABLE.ContainsKey($name)) { return $Script:ROUTE_TABLE[$name] }
    return $null
}

function Invoke-Router {
    # D6 M3: three hard reject rules -> caller exit code (2/4/0).
    #   rule A: model missing          -> reject exit 2
    #   rule C: model not in route     -> reject exit 2
    #   rule B: local-only + opencode/*(Zen egress) -> reject exit 4  (owner-policy: no override)
    param(
        [string]$model,
        [string]$sensitivity
    )
    if (-not $sensitivity) { $sensitivity = 'public' }

    # rule A: missing model (explicit-model invariant #3)
    if (-not $model) { Write-Host 'REJECT missing-model (exit 2) - explicit model required (inv 3)'; return 2 }

    # resolve alias/full-id -> @{id;station}
    $r = Resolve-Model $model
    if (-not $r) { Write-Host "REJECT unknown-model ($model) exit 2 - not in route table"; return 2 }

    $id = $r['id']
    $station = $r['station']

    # rule B: local-only never goes to Zen egress (opencode/* => outbound)
    if ($sensitivity -eq 'local-only' -and $id -match '^opencode/') {
        Write-Host "REJECT local-only+remote ($id) exit 4 - no override channel (owner-policy)"; return 4
    }

    Write-Host "ROUTE ok: $model -> $id (station $station, sensitivity=$sensitivity)"
    return 0
}

# ---------------- 6.4 complexity routing ----------------

function Resolve-Profile {
    # 6.4: {model-alias, complexity, taskType} -> resolved inference-param profile.
    # profile = {profile, context, max_output, thinking(ON/OFF), template, reasoning_format, flavor, source}
    # priority: taskType > complexity > default(reason). code/doc force thinking OFF (实测: 满ctx+最高思考横测
    # 代码题思考开启对质量负收益 - cost 94.9x; 见 model-eval/results-ledger 配置变体对照 2026-09-06).
    # reasoning_format fixed = qwen: `--reasoning-format deepseek` 剥不动 qwen 的 thinking/response 标签
    # (llama.cpp #24671, 本集群实证 reasoning_content=0).
    param([string]$model, [string]$complexity, [string]$taskType)
    $typeProfiles = @{
        code    = @{ name='code';    context=8192;  max_output=8192;  thinking='OFF'; template='froggeric'; reasoning_format='qwen'; flavor='nothink' }
        reason  = @{ name='reason';  context=32768; max_output=8192;  thinking='ON';  template='froggeric'; reasoning_format='qwen'; flavor='think' }
        concept = @{ name='reason';  context=32768; max_output=8192;  thinking='ON';  template='froggeric'; reasoning_format='qwen'; flavor='think' }
        numeric = @{ name='short';   context=8192;  max_output=2048;  thinking='ON';  template='froggeric'; reasoning_format='qwen'; flavor='think' }
        doc     = @{ name='doc';     context=0;     max_output=8192;  thinking='OFF'; template='froggeric'; reasoning_format='qwen'; flavor='nothink' }
    }
    $compProfiles = @{
        short    = @{ name='short';  context=8192;  max_output=2048;  thinking='ON';  template='froggeric'; reasoning_format='qwen'; flavor='think' }
        standard = @{ name='reason'; context=32768; max_output=8192;  thinking='ON';  template='froggeric'; reasoning_format='qwen'; flavor='think' }
        long     = @{ name='long';   context=0;     max_output=16384; thinking='ON';  template='froggeric'; reasoning_format='qwen'; flavor='long' }
        auto     = @{ name='reason'; context=32768; max_output=8192;  thinking='ON';  template='froggeric'; reasoning_format='qwen'; flavor='think' }
    }
    $ctxMax = @{ 'nemotron'=131072; 'gpt-oss'=131072; 'lightning'=262144; 'ultra'=1000000; 'free-1m'=1000000 }
    $modelCtx = 262144
    if ($model -and $ctxMax.ContainsKey($model)) { $modelCtx = $ctxMax[$model] }
    $pro = $null; $src = ''
    if ($taskType -and $typeProfiles.ContainsKey($taskType)) { $pro = $typeProfiles[$taskType].Clone(); $src = "type=$taskType" }
    elseif ($complexity) {
        $cl = if ($compProfiles.ContainsKey($complexity)) { $complexity } else { 'auto' }
        $pro = $compProfiles[$cl].Clone(); $src = "complexity=$complexity"
    }
    else { $pro = $compProfiles['auto'].Clone(); $src = 'default' }
    # context=0 sentinel -> model context max (long/doc)
    if ($pro['context'] -le 0) { $pro['context'] = $modelCtx }
    # conflict: type=code/doc + complexity=long -> keep thinking OFF, bump context to large
    if ($taskType -and $complexity -eq 'long' -and $pro['name'] -in @('code','doc')) { $pro['context'] = $modelCtx }
    if ($pro['name'] -in @('code','doc')) { $pro['thinking'] = 'OFF' }
    return [pscustomobject]@{ profile=$pro['name']; context=$pro['context']; max_output=$pro['max_output'];
                             thinking=$pro['thinking']; template=$pro['template']; reasoning_format=$pro['reasoning_format'];
                             flavor=$pro['flavor']; source=$src }
}

# ---------------- M4 lock/state ----------------

function Invoke-LockState {
    # D6 M4: acquire/release/status on remote .agent-lock + .agent-state.json (orphan detection)
    # Lock held on station via flock fd 9 (R14: remote script on disk). Exit codes:
    #   0 ok (or orphan recovered) / 3 lock held (owner pid reported) / 2 bad act.
    # hold>0 (acquire only): keep script running that many secs so A9 can observe contention.
    param(
        [string]$act,       # acquire|release|status
        [string]$proj,
        [string]$hold,      # seconds to hold lock after acquire (A9 concurrency test)
        [string]$hostName
    )
    if (-not $hostName) { $hostName = 'scott-lau-GTR-Pro.local' }
    $W = "$Script:WORKSPACE_ROOT/$proj"
    if (-not $hold) { $hold = '0' }

    $sleepLine = ''
    if ($act -eq 'acquire' -and [int]$hold -gt 0) { $sleepLine = "sleep $hold  # hold fd open for A9 contention test" }

    # PS5.1 gotcha: inside here-string the REMOTE vars must be backtick-escaped.
    # Only PS-side vars ($act, $sleepLine) are interpolated here directly.
    $body = @"
set -u
W="$W"
S="`$W/.agent-state.json"
mkdir -p "`$W" "`$W/out"
case "$act" in
  acquire)
    # orphan check first: running + dead pid => archive out/ -> orphaned -> recoverable
    if [ -f "`$S" ]; then
      st=`$(grep -o '"state": *"[^"]*"' "`$S" | head -1 | cut -d'"' -f4 2>/dev/null)
      pid=`$(grep -o '"pid": *[0-9]*' "`$S" | grep -o '[0-9]*' | head -1)
      if [ "`$st" = running ] && [ -n "`$pid" ] && ! kill -0 "`$pid" 2>/dev/null; then
        mkdir -p "`$W/out/orphaned"
        cp -r "`$W/out/"* "`$W/out/orphaned/" 2>/dev/null || true
        printf '{"state":"orphaned","pid":%s,"ts_start":"%s","task_id":"","host":"agent-cli"}' "`$pid" "`$(date -Is)" > "`$S"
        echo "ORPHAN_RECOVERED pid=`$pid archived out/ -> orphaned, then re-acquire"
      fi
    fi
    exec 9> "`$W/.agent-lock"
    if ! flock -n 9; then
      owner=`$(grep -o '"pid": *[0-9]*' "`$S" 2>/dev/null | grep -o '[0-9]*' | head -1)
      [ -z "`$owner" ] && owner=unknown
      echo "LOCK_HELD owner_pid=`$owner"
      exit 3
    fi
    printf '{"state":"running","pid":%d,"ts_start":"%s","task_id":"locktest","host":"agent-cli"}' "`$$" "`$(date -Is)" > "`$S"
    echo "LOCK_ACQUIRED pid=`$$"
    $sleepLine
    ;;
  release)
    printf '{"state":"done","pid":%d,"ts_start":"%s","task_id":"locktest","host":"agent-cli"}' "`$$" "`$(date -Is)" > "`$S"
    echo "LOCK_RELEASED pid=`$$"
    ;;
  status)
    if [ -f "`$S" ]; then cat "`$S"; echo; else echo "NO_STATE"; fi
    ;;
  *) echo "bad lock action: $act"; exit 2 ;;
esac
"@
    $code = Invoke-RemoteScript -HostName $hostName -ScriptBody $body -LocalName "agent-cli-lock-$act.sh"
    return $code
}

# ---------------- M2 task full-chain ----------------

function Assert-AgentOutWritable {
    # TODO-2 pre-flight (2026-09-07): BEFORE any remote sync/run, verify the console agent-out
    # root is writable from the injected sandbox whitelist. A fresh host session may NOT include
    # D:\Paper\agent-out (Settings UI only; global.json does not apply) -> collect would crash
    # AFTER a long run. Probe early and fail fast instead of wasting a run.
    param([string]$projRoot)
    $outRoot = Join-Path $projRoot 'agent-out'
    $probe = Join-Path $outRoot "_preflight_$([DateTime]::Now.ToString('HHmmss')).probe"
    try {
        if (-not (Test-Path $outRoot)) { New-Item -ItemType Directory -Path $outRoot -Force | Out-Null }
        Set-Content -Path $probe -Value 'ok' -ErrorAction Stop
        Remove-Item $probe -Force -ErrorAction SilentlyContinue
        Write-Host "PREFLIGHT agent-out=WRITABLE ($outRoot)"
        return $true
    }
    catch {
        Write-Host "PREFLIGHT-FAIL: agent-out NOT writable ($outRoot): $($_.Exception.Message)"
        Write-Host "  -> Settings > Permission & Approval > Custom Configuration: ensure this dir is writable (global.json does NOT apply)."
        return $false
    }
}

function Get-FrontMatter {
    # minimal front-matter parser from a task card md.
    # P1b (D6 audit 2026-09-03): the card BODY is the clean-room task spec (DESIGN §6.1
    # "正文为干净室任务描述") and MUST be transmitted - previously only the one-line
    # front-matter task: was sent and the whole body was silently dropped (A14 finding:
    # model self-designed the deliverable + self-authored its tests => self-certifying accept).
    param([string]$Path)
    $h = @{ model=''; sensitivity=''; readonly=$false; timeout_s=900; task=''; cli='opencode'; accept=@(); body=''; complexity=''; 'task-type'='' }
    $inFreq = $false; $bodyRead = $false; $curKey = ''
    $bodyLines = @()
    $lines = [System.IO.File]::ReadAllLines($Path, [System.Text.UTF8Encoding]::new($false))
    foreach ($l in $lines) {
        if ($l.Trim() -eq '---') { if (-not $inFreq) { $inFreq = $true; continue } else { $inFreq = $false; $bodyRead = $true; continue } }
        if ($inFreq -and $l -match '^\s*([A-Za-z_\-]+)\s*:\s*(.*)$') {
            $k = $matches[1].ToLower(); $v = $matches[2].Trim()
            $curKey = ''
            if ($h.ContainsKey($k)) {
                if ($k -eq 'accept') { $curKey = 'accept' }
                else { $h[$k] = $v }
            }
        }
        elseif ($inFreq -and $curKey -eq 'accept' -and $l -match '^\s*-\s+(.+)$') {
            $h['accept'] += $matches[1].Trim()
        }
        elseif ($bodyRead) {
            $bodyLines += $l
            $t = $l -replace '^#{1,6}\s*任务描述\s*', '' -replace '^#{1,6}\s*', ''
            if (-not $h['task'] -and $t.Trim()) { $h['task'] = $t.Trim() }
        }
    }
    $h['body'] = (($bodyLines -join "`n").Trim())
    if ($h['readonly'] -eq 'true') { $h['readonly'] = $true } else { $h['readonly'] = $false }
    $ts = 0
    if (-not [int]::TryParse([string]$h['timeout_s'], [ref]$ts) -or $ts -le 0) { $ts = 900 }
    $h['timeout_s'] = $ts
    return $h
}

function Get-Sha256Text([string]$text) {
    $sha = [Security.Cryptography.SHA256]::Create()
    $bytes = $sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($text))
    return (($bytes | ForEach-Object { $_.ToString('x2') }) -join '')
}

function Invoke-Scrubber {
    # D6 audit P1 (2026-09-03): regex-only sanitizer for sensitivity=sanitized (IMPL T2 scope).
    # Patterns: api keys (sk-...), emails, windows absolute paths. Runs on console BEFORE
    # the prompt leaves (invariant 2: scrub on console, remote only receives sanitized text).
    # R4: prints masked previews of hit lines for human confirmation; no whitelist in MVP.
    param([string]$text)
    $rules = @(
        @{ name = 'api-key';  re = 'sk-[A-Za-z0-9_\-]{16,}';                             repl = '[REDACTED-KEY]' },
        @{ name = 'email';    re = '[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}';   repl = '[REDACTED-EMAIL]' },
        @{ name = 'win-path'; re = '(?i)\b[A-Z]:\\\S+';                                    repl = '[REDACTED-PATH]' }
    )
    $hits = 0
    foreach ($r in $rules) {
        $ms = [regex]::Matches($text, $r['re'])
        if ($ms.Count -gt 0) {
            $hits += $ms.Count
            foreach ($m in $ms) {
                $preview = if ($m.Value.Length -gt 8) { $m.Value.Substring(0, 8) + '...' } else { $m.Value }
                Write-Host "SCRUB[$($r['name'])] hit: $preview (len=$($m.Value.Length)) -> $($r['repl'])"
            }
            $text = [regex]::Replace($text, $r['re'], $r['repl'])
        }
    }
    if ($hits -gt 0) { Write-Host "SCRUB total hits: $hits (sanitized gate active)" }
    return $text
}

function Invoke-Task {
    # D6 M2: full chain sync->lock->run->collect->unlock for a single task card.
    # prompt is transferred via base64 (immune to quote hell); remote reads it and
    # pipes to opencode via stdin (inv 4: no position-arg form).
    param(
        [string]$proj,
        [string]$card,       # local path to task card md
        [string]$model,      # alias/full-id override
        [string]$sensitive,  # sensitivity override
        [string]$type,       # .agentsync type for sync step
        [string]$hostName,
        [string[]]$attach,   # O-01: attachments -> workspace .attach/
        [string]$complexity, # 6.4: auto|short|standard|long
        [string]$taskType    # 6.4: code|reason|concept|numeric|doc
    )
    if (-not $card) { Write-Host 'task requires --card <task.md>'; return 2 }
    if (-not (Test-Path $card)) { throw "card not found: $card" }
    $projRoot = $Script:PROJECTS[$proj]
    if (-not $projRoot -or -not (Test-Path $projRoot)) { throw "unknown/missing project: $proj (registered: $($Script:PROJECTS.Keys -join ','))" }
    if (-not $attach) { $attach = @() }

    # 1) card front-matter
    $fm = Get-FrontMatter $card
    $m = if ($model) { $model } else { if ($fm['model']) { $fm['model'] } else { '' } }
    $sens = if ($sensitive) { $sensitive } else { if ($fm['sensitivity']) { $fm['sensitivity'] } else { 'public' } }
    if (-not $m) { Write-Host 'REJECT missing-model (exit 2) - card has no model and no --model (inv 3)'; return 2 }
    $readonly = [bool]$fm['readonly']
    $timeout = [int]$fm['timeout_s']

    # 2) M3 route (reuse Resolve-Model + local-only gate)
    $r = Resolve-Model $m
    if (-not $r) { Write-Host "REJECT unknown-model ($m) exit 2 - not in route table"; return 2 }
    $id = $r['id']; $station = $r['station']
    if ($sens -eq 'local-only' -and $id -match '^opencode/') { Write-Host "REJECT local-only+remote ($id) exit 4 - no override channel"; return 4 }
    if (-not $hostName) { $hostName = Get-TargetHost $station }

    # 6.4 complexity routing: CLI --complexity/--task-type > card front-matter > default(reason)
    $cx = if ($complexity) { $complexity } else { if ($fm['complexity']) { $fm['complexity'] } else { 'auto' } }
    $tt = if ($taskType) { $taskType } else { if ($fm['task-type']) { $fm['task-type'] } else { '' } }
    $prof = Resolve-Profile -model $m -complexity $cx -taskType $tt
    $profTxt = "profile=$($prof.profile) ctx=$($prof.context) max_out=$($prof.max_output) thinking=$($prof.thinking) template=$($prof.template) reasoning=$($prof.reasoning_format) flavor=$($prof.flavor) ($($prof.source))"
    Write-Host "PROFILE: $profTxt"
    # L1 hint (only log, NEVER auto-unload/reload - GTT mutually exclusive, avoid disrupting loaded instance):
    if ($prof.flavor -eq 'nothink' -or $prof.flavor -eq 'long') { Write-Host "PROFILE-L1-HINT: flavor=$($prof.flavor) - requires instance with matching CTX/template; verify loaded instance or reload manually" }

    # TODO-2 pre-flight (2026-09-07): fail fast on unwritable agent-out BEFORE station-ready/sync/run.
    # Route+profile dry-run above already printed; now verify the local collect destination.
    if (-not (Assert-AgentOutWritable -projRoot $projRoot)) {
        Write-Host "ABORT: agent-out not writable (exit 12) - fix Settings > Permission & Approval > Custom Configuration"
        return 12
    }

    # O-19: station env-ready gate (discover engine port + inject cluster-litellm baseURL BEFORE dispatch)
    $baseAlias = ($m -split '/')[-1]
    try { Invoke-StationReady -HostName $hostName -Alias $baseAlias | Out-Null }
    catch { Write-Host "STATION_NOT_READY: $($_.Exception.Message)"; return 10 }

    # 3) sync source subset (never overwrite out/); target station is B (memory master) ws root
    Write-Host "TASK sync source -> $proj (model=$id station=$station sens=$sens readonly=$readonly)"
    try { Invoke-Workspace -proj $proj -act 'sync' -type $type -Station $station | Out-Null }
    catch {
        $msg = $_.Exception.Message
        if ($msg -like 'NETFAIL*') { Write-Host "sync network failure: $msg"; return 5 }   # P2-2: DESIGN §8
        Write-Host "sync failed: $msg"; return 6
    }

    # 3b) attachments (O-01): scp each attachment -> workspace .attach/ (only-if-local isolates console reads;
    #      .attach/ excluded from sync so it stays one-way in; agent reads by relative path in prompt refs)
    $attachNames = @()
    if ($attach.Count -gt 0) {
        # remote .attach/ once; files/dirs scp per attachment below
        $body = @"
set -eu
W="$Script:WORKSPACE_ROOT/$proj"
mkdir -p "`$W/.attach"
"@
        Invoke-RemoteScript -HostName $hostName -ScriptBody $body -LocalName "agent-cli-attach-mkdir.sh"
        foreach ($a in $attach) {
            if (-not (Test-Path $a)) { Write-Host "attach missing (skip): $a"; continue }
            $isDir = Test-Path $a -PathType Container   # dir -> scp -r recursion (O-01 dfile)
            $name = Split-Path $a -Leaf
            if ($isDir) {
                # scp -r 不复制空目录 -> 预建远端同名目录兜底 (O-01 edge)
                $bodyDir = @"
set -eu
W="$Script:WORKSPACE_ROOT/$proj"
mkdir -p "`$W/.attach/$name"
"@
                Invoke-RemoteScript -HostName $hostName -ScriptBody $bodyDir -LocalName "agent-cli-attach-mkdir-dir.sh"
                scp -q -r -o ConnectTimeout=10 $a "${hostName}:$Script:WORKSPACE_ROOT/$proj/.attach/" 2>$null
            }
            else {
                scp -q -o ConnectTimeout=10 $a "${hostName}:$Script:WORKSPACE_ROOT/$proj/.attach/" 2>$null
            }
            if ($LASTEXITCODE -ne 0) { Write-Host "NETFAIL: attach scp failed: $a"; return 5 }
            $attachNames += $name
            Write-Host "ATTACH_OK: $a -> workspace $proj/.attach/$name"
        }
    }

    # 4) prompt + M1 hash (inv 5: Model-visible means logged)
    #    P1b: card BODY (clean-room spec) is transmitted with the task line.
    #    P1a: sanitized gate scrubs on console BEFORE hashing/encoding (inv 2).
    $promptFull = "[proj:$proj]`n$($fm['task'])"
    if ($fm['body']) { $promptFull += "`n`n" + $fm['body'] }
    if ($attachNames.Count -gt 0) {
        $promptFull += "`n`n[attachments in workspace .attach/]: " + ($attachNames -join ', ')
        $promptFull += "`n(" + ((Split-Path $attachNames[0] -Leaf)) + " 等附件已在工作区 .attach/ 目录，按需读取)"
    }
    # L3 prompt deformation (6.4): reasoning/short profiles add "think terse" tail so agent
    # does not blow the thinking budget (实测: 思考无限在短题负收益 / 空响应 - see ledger 2026-09-06).
    if ($prof.thinking -eq 'ON' -and $prof.profile -in @('short','reason')) {
        $promptFull += "`n`n(高效应答: 请尽量精简思考, 直接给出关键步骤与最终结论)"
    }
    if ($sens -eq 'sanitized') {
        Write-Host 'SANITIZED gate: scrubbing prompt before it leaves console (P1a)'
        $promptFull = Invoke-Scrubber $promptFull
    }
    $promptSha = Get-Sha256Text $promptFull
    $promptB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($promptFull))

    # 4b) accept criteria (A14): executable verification gate run remotely after agent completes
    $accept = @($fm['accept'])
    if ($accept.Count -gt 0 -and $accept[0]) { $accept = @($accept | Where-Object { $_.Trim() }) } else { $accept = @() }
    $acceptB64 = ''
    if ($accept.Count -gt 0) { $acceptB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes(($accept -join "`n"))) }

    # 5) fused remote script: orphan->flock->state->opencode(stdin)->state->output (R14)
    $W = "$Script:WORKSPACE_ROOT/$proj"
    $ts = [DateTime]::Now.ToString('yyyyMMddHHmmssffff')
    $body = @"
set -u
W="$W"
S="`$W/.agent-state.json"
mkdir -p "`$W" "`$W/out"
# orphan check
if [ -f "`$S" ]; then
  st=`$(grep -o '"state": *"[^"]*"' "`$S" | head -1 | cut -d'"' -f4 2>/dev/null)
  pid=`$(grep -o '"pid": *[0-9]*' "`$S" | grep -o '[0-9]*' | head -1)
  if [ "`$st" = running ] && [ -n "`$pid" ] && ! kill -0 "`$pid" 2>/dev/null; then
    mkdir -p "`$W/out/orphaned"
    cp -r "`$W/out/"* "`$W/out/orphaned/" 2>/dev/null || true
    echo "ORPHAN_RECOVERED pid=`$pid"
  fi
fi
exec 9> "`$W/.agent-lock"
if ! flock -n 9; then
  owner=`$(grep -o '"pid": *[0-9]*' "`$S" 2>/dev/null | grep -o '[0-9]*' | head -1)
  [ -z "`$owner" ] && owner=unknown
  echo "LOCK_HELD owner_pid=`$owner"
  exit 3
fi
Q0=`$(date +%s%N)
printf '{"state":"running","pid":%d,"ts_start":"%s","task_id":"%s","host":"agent-cli"}' "`$$" "`$(date -Is)" "$ts" > "`$S"
sleep 2   # artificial intake gap (BP-4: makes queue_s measurable on contention holder)
printf '%s' "$promptB64" | base64 -d > "`$W/out/.prompt.txt"
echo "PIPE_STDIN_OK"
cd "`$W" || exit 8    # cwd=workspace so agent reads AGENTS.md + project files (inv 4: stdin pipe, not cwd hijack)
R0=`$(date +%s%N)     # P2-1: run clock starts here (queue = lock+intake up to this point)
timeout $timeout opencode run -m "$id" < "`$W/out/.prompt.txt" > "`$W/out/.agent-output.txt" 2>&1
RC=`$?
R1=`$(date +%s%N)
# accept gate (A14): run executable criteria in workspace after agent completes
ACCEPT_B64="$acceptB64"
ACCEPT_OK=1
if [ -n "`$ACCEPT_B64" ]; then
  echo "`$ACCEPT_B64" | base64 -d > "`$W/out/.accept-cmds.txt"
  : > "`$W/out/.accept-output.txt"
  i=0
  while IFS= read -r c || [ -n "`$c" ]; do
    [ -z "`$c" ] && continue
    ((i++))
    echo "=== ACCEPT_CMD[`$i] >>> `$c" >> "`$W/out/.accept-output.txt"
    ( cd "`$W" && eval "`$c" ) >> "`$W/out/.accept-output.txt" 2>&1
    arc=`$?
    echo "--- ACCEPT_RC[`$i]=`$arc" >> "`$W/out/.accept-output.txt"
    [ "`$arc" -ne 0 ] && ACCEPT_OK=0
  done < "`$W/out/.accept-cmds.txt"
  echo "ACCEPT_OK=`$ACCEPT_OK"
fi
printf '{"state":"done","pid":%d,"ts_start":"%s","task_id":"%s","host":"agent-cli"}' "`$$" "`$(date -Is)" "$ts" > "`$S"
QUEUE=`$(( (R0-Q0)/1000000000 ))    # P2-1: queue = lock wait + intake (sleep 2 => ~2s)
RUNS=`$(( (R1-R0)/1000000000 ))      # P2-1: run = agent generation wall time
echo "QUEUE_S=`$QUEUE"
echo "RUN_S=`$RUNS"
echo "TASK_RC=`$RC"
echo "ACCEPT_OK=`$ACCEPT_OK"
echo "OUT_BYTES=`$(wc -c < "`$W/out/.agent-output.txt" 2>/dev/null)"
printf 'QUEUE_S=%s\nRUN_S=%s\nTASK_RC=%s\nACCEPT_OK=%s\n' "`$QUEUE" "`$RUNS" "`$RC" "`$ACCEPT_OK" > "`$W/out/.meta"
# task succeeds only if agent ok AND (no accept criteria OR accept all pass)
if [ -n "`$ACCEPT_B64" ] && [ "`$ACCEPT_OK" -ne 1 ]; then exit 9; fi
exit `$RC
"@
    $code = Invoke-RemoteScript -HostName $hostName -ScriptBody $body -LocalName "agent-cli-task-$ts.sh"
    # DESIGN §9.5 exit-code dispatch: 124(timeout by `timeout`) -> 6; other remote run rc preserved as failure
    if ($code -eq 124) { $code = 6 }
    Write-Host "TASK remote excode=$code"

    # 6) collect: pull out/.meta + out/.agent-output.txt + out/.accept-output.txt, compute content_digest (M1)
    $outTxt = Join-Path $env:TEMP "agent-cli-out-$ts.txt"
    $metaTxt = Join-Path $env:TEMP "agent-cli-meta-$ts.txt"
    $accTxt = Join-Path $env:TEMP "agent-cli-accept-$ts.txt"
    scp -q -o ConnectTimeout=10 "${hostName}:$W/out/.agent-output.txt" "$outTxt" 2>$null
    scp -q -o ConnectTimeout=10 "${hostName}:$W/out/.meta" "$metaTxt" 2>$null
    if ($accept.Count -gt 0) { scp -q -o ConnectTimeout=10 "${hostName}:$W/out/.accept-output.txt" "$accTxt" 2>$null }
    $queue_s = 0; $run_s = 0; $accept_ok = $null
    if (Test-Path $metaTxt) {
        $m = Get-Content $metaTxt | Out-String
        if ($m -match 'QUEUE_S=(\d+)') { $queue_s = [int]$matches[1] }
        if ($m -match 'RUN_S=(\d+)')   { $run_s = [int]$matches[1] }      # P2-1: run_s now measured (R1-R0)
        if ($m -match 'ACCEPT_OK=(\d+)') { $accept_ok = [int]$matches[1] }
    }
    $contentSha = ''
    if (Test-Path $outTxt) { $contentSha = Get-Sha256Text ([IO.File]::ReadAllText($outTxt)) }
    # accept gate: remote exit 9 => agent ok but accept criteria failed (DESIGN §8 not exposed; local marker)
    $acceptPassed = $true
    if ($accept.Count -gt 0) { $acceptPassed = ($accept_ok -eq 1) }
    $codeReal = $code
    if ($code -eq 9) { $code = 1 }  # map accept-gate failure to generic failed for shell return

    # 8) ledger line FIRST (G13) -- fixed to sandbox-writable d:\RPC zone (O-04: projRoot not
    #     sandbox-safe). Run ledger before any agent-out write so a collect crash (startup-
    #     injected sandbox whitelist w/o D:\Paper\agent-out) never loses the run record.
    $ledger = 'd:\RPC\ops\station-bin\agent-runs.log'
    $line = "$ts,$proj,$id,$sens,$code,0,0"
    try { Add-Content -Path $ledger -Value $line -Encoding utf8; $ledgerOk = $true }
    catch { $ledgerOk = $false; Write-Host "LEDGER_WARN: $($_.Exception.Message)" }

    # 7) .agent-run.json under <proj>/agent-out/<ts>/ (DESIGN §6.2)
    #    Hardened in try/catch: if agent-out is not sandbox-writable (new host session), we
    #    still surface TASK_DONE + a COLLECT_FAIL marker and keep the exit code semantics.
    $collectOk = $true
    try {
        $projOutRoot = Join-Path $projRoot 'agent-out'
        if (-not (Test-Path $projOutRoot)) { New-Item -ItemType Directory -Path $projOutRoot -Force | Out-Null }
        $runDir = Join-Path $projOutRoot $ts
        New-Item -ItemType Directory -Path $runDir -Force | Out-Null
    }
    catch {
        $collectOk = $false
        $runDir = "$projRoot\agent-out\<$ts>"
        Write-Host "COLLECT_FAIL: cannot create agent-out dir: $($_.Exception.Message)"
    }
    $run = [ordered]@{
        proj = $proj
        task_id = "task-$ts"
        cli = 'opencode'
        model = $id
        sensitivity = $sens
        readonly = $readonly
        session_id = ''
        exit_code = $code
        status = if ($code -eq 0 -and $acceptPassed) { 'completed' } elseif ($code -eq 6) { 'timeout' } else { 'failed' }
        content_digest = "sha256:$contentSha"
        usage = [ordered]@{ total_tokens = 0; tool_uses = 0 }
        queue_s = $queue_s
        run_s = $run_s
        timestamp_start = ''
        timestamp_end = ''
        prompt_sha256 = "sha256:$promptSha"
        attach = $attachNames
        profile = [ordered]@{ name=$prof.profile; context=$prof.context; max_output=$prof.max_output;
                              thinking=$prof.thinking; template=$prof.template; reasoning_format=$prof.reasoning_format;
                              flavor=$prof.flavor; source=$prof.source }
        accept = [ordered]@{ cmd = $accept; passed = $acceptPassed }
        collect = if ($collectOk) { 'ok' } else { 'failed' }
    }
    if ($collectOk) {
        try {
            $run | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $runDir '.agent-run.json') -Encoding utf8
            # move pulled output into runDir
            if (Test-Path $outTxt) { Move-Item $outTxt (Join-Path $runDir 'agent-output.txt') -Force }
            if (Test-Path $accTxt) { Move-Item $accTxt (Join-Path $runDir 'accept-output.txt') -Force }
            Remove-Item (Join-Path $projRoot 'agent-out\.agent-run.json') -ErrorAction SilentlyContinue
        }
        catch {
            $collectOk = $false
            Write-Host "COLLECT_FAIL: agent-out write failed: $($_.Exception.Message)"
        }
    }

    # (ledger already written above, before collect - G13/O-04)
    Write-Host "TASK_DONE dir=$runDir exit=$code prompt_sha256=sha256:$promptSha content_digest=sha256:$contentSha"
    Write-Host "ledger+=$line"
    return $code
}

# ---------------- entry ----------------
try {
    if ($Command -eq 'workspace') {
        $act = if ($Create) { 'create' } elseif ($Sync) { 'sync' } elseif ($Archive) { 'archive' } else { 'create' }
        if (-not $Proj) { $Proj = $env:AGENT_CLI_PROJ }
        Invoke-Workspace -proj $Proj -act $act -type $Type -Station $HostName
        exit 0
    }
    elseif ($Command -eq 'route') {
        # M3 router diagnostic (A8). usage: agent-cli route --model <name> [--sensitivity <x>]
        #   [--complexity <auto|short|standard|long> --task-type <code|reason|concept|numeric|doc>]  # 6.4 profile dry-run
        if (-not $Model) { Write-Host 'usage: agent-cli route --model <alias|full-id> [--sensitivity public|sanitized|local-only] [--complexity <auto|short|standard|long>] [--task-type <code|reason|concept|numeric|doc>]'; exit 2 }
        $code = Invoke-Router -model $Model -sensitivity $Sensitivity
        if ($code -eq 0 -and ($Complexity -or $TaskType)) {
            $prof = Resolve-Profile -model $Model -complexity $Complexity -taskType $TaskType
            Write-Host "PROFILE: profile=$($prof.profile) ctx=$($prof.context) max_out=$($prof.max_output) thinking=$($prof.thinking) template=$($prof.template) reasoning=$($prof.reasoning_format) flavor=$($prof.flavor) ($($prof.source))"
        }
        exit $code
    }
    elseif ($Command -eq 'lock') {
        # M4 lock/state diagnostic (A9/A10). usage: agent-cli lock <proj> --acquire|--release|--status [--hold <s>]
        if (-not $Act) { Write-Host 'usage: agent-cli lock <proj> --acquire [--hold <s>] | --release | --status'; exit 2 }
        if (-not $Proj) { $Proj = $env:AGENT_CLI_PROJ }
        $code = Invoke-LockState -act $Act -proj $Proj -hold $Hold -hostName $RemoteHost
        exit $code
    }
    elseif ($Command -eq 'task') {
        # M2 full chain. usage: agent-cli task <proj> --card <task.md> [--model <m>] [--sensitivity <x>] [--complexity <auto|short|standard|long>] [--task-type <code|reason|concept|numeric|doc>]
        $code = Invoke-Task -proj $Proj -card $Card -model $Model -sensitive $Sensitivity -type $Type -hostName $RemoteHost -attach $Attach -complexity $Complexity -taskType $TaskType
        exit $code
    }
    else {
        Write-Host "usage:"; Write-Host "  agent-cli workspace <proj> [--create|--sync|--archive] [--type python|cpp|doc|lean4]"
        Write-Host "  agent-cli task <proj> ...  (T3)"
        exit 2
    }
}
catch {
    Write-Host "ERROR: $($_.Exception.Message)"
    # P2-2 (D6 audit): terminal network failure (reach/exec after retry) -> DESIGN §8 exit code 5
    if ($_.Exception.Message -like 'NETFAIL*') { exit 5 }
    exit 1
}