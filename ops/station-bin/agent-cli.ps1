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
    [string]$Card = ''           # task cmd: path to task card md
)

# ---------------- constants / env ----------------
$ErrorActionPreference = 'Stop'
$Script:GNU_TAR = 'C:\Program Files\Git\usr\bin\tar.exe'   # S1: not Win10 bsdtar
$Script:REMOTE_USER = 'scott-lau'
$Script:WORKSPACE_ROOT = '/home/scott-lau/agent-workspaces'
$Script:PROJECTS = @{ paper = 'D:\Paper' }    # console project root mapping
$Script:TMP_ROOT = Join-Path $env:TEMP 'agent-cli'

# ---------------- ROUTE_TABLE (BP-2 alias->full-id, T3 task uses; fixed here) ----------------
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
    $r = ssh -o ConnectTimeout=8 -o BatchMode=yes $hostName 'echo alive' 2>$null
    return ($LASTEXITCODE -eq 0 -and $r -match 'alive')
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
    if (-not (Test-RemoteReach $HostName)) { throw "remote unreachable: $HostName (ensure station online)" }
    if (-not $LocalName) { $LocalName = "agent-cli-run-$([DateTime]::Now.ToString('HHmmss')).sh" }

    $localPath = Join-Path $Script:TMP_ROOT $LocalName
    if (-not (Test-Path $Script:TMP_ROOT)) { New-Item -ItemType Directory -Path $Script:TMP_ROOT -Force | Out-Null }
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($localPath, $ScriptBody, $utf8NoBom)

    scp -q -o ConnectTimeout=10 $localPath "${HostName}:/tmp/${LocalName}"
    if ($LASTEXITCODE -ne 0) { throw "scp failed: $LocalName" }

    $sshOut = ssh -o ConnectTimeout=10 $HostName "bash /tmp/${LocalName}" 2>&1
    $code = $LASTEXITCODE
    # ssh network-level failure -> retry once (inv 7 gate-cache: retry does NOT re-run scrubber; only network retry per DESIGN §4.5/F7)
    if ($code -ne 0 -and ($sshOut -match 'Could not resolve hostname|Connection (refused|timed out|reset)|Network is unreachable|port 22')) {
        Write-Host "[retry] ssh network failure (rc=$code), retry once (gate-cache: scrubber not re-run)"
        Start-Sleep -Seconds 2
        $sshOut = ssh -o ConnectTimeout=10 $HostName "bash /tmp/${LocalName}" 2>&1
        $code = $LASTEXITCODE
    }
    foreach ($ln in $sshOut) { Write-Host $ln }   # stream remote stdout to console, NOT into return value
    Remove-Item $localPath -ErrorAction SilentlyContinue
    return $code
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
    param([string]$proj, [string]$act, [string]$type)
    $projRoot = $Script:PROJECTS[$proj]
    if (-not $projRoot -or -not (Test-Path $projRoot)) { throw "unknown/missing project: $proj (registered: $($Script:PROJECTS.Keys -join ','))" }
    $station = if ($HostName -in @('A','B')) { $HostName } else { 'B' }
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
        if ($LASTEXITCODE -ne 0) { throw 'scp skeleton failed' }

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

function Get-FrontMatter {
    # minimal front-matter parser from a task card md
    param([string]$Path)
    $h = @{ model=''; sensitivity=''; readonly=$false; timeout_s=900; task=''; cli='opencode' }
    $inFreq = $false; $bodyRead = $false
    foreach ($l in (Get-Content $Path)) {
        if ($l.Trim() -eq '---') { if (-not $inFreq) { $inFreq = $true; continue } else { $inFreq = $false; $bodyRead = $true; continue } }
        if ($inFreq -and $l -match '^\s*([A-Za-z_]+)\s*:\s*(.*)$') {
            $k = $matches[1].ToLower(); $v = $matches[2].Trim()
            if ($h.ContainsKey($k)) { $h[$k] = $v }
        }
        elseif ($bodyRead) {
            $t = $l -replace '^#{1,6}\s*任务描述\s*', '' -replace '^#{1,6}\s*', ''
            if (-not $h['task'] -and $t.Trim()) { $h['task'] = $t.Trim() }
        }
    }
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
        [string]$hostName
    )
    if (-not $card) { Write-Host 'task requires --card <task.md>'; return 2 }
    if (-not (Test-Path $card)) { throw "card not found: $card" }
    $projRoot = $Script:PROJECTS[$proj]
    if (-not $projRoot -or -not (Test-Path $projRoot)) { throw "unknown/missing project: $proj (registered: $($Script:PROJECTS.Keys -join ','))" }

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

    # 3) sync source subset (never overwrite out/); target station is B (memory master) ws root
    Write-Host "TASK sync source -> $proj (model=$id station=$station sens=$sens readonly=$readonly)"
    try { Invoke-Workspace -proj $proj -act 'sync' -type $type | Out-Null }
    catch { Write-Host "sync failed: $($_.Exception.Message)"; return 6 }

    # 4) prompt + M1 hash (inv 5: Model-visible means logged)
    $promptFull = "[proj:$proj]`n$($fm['task'])"
    $promptSha = Get-Sha256Text $promptFull
    $promptB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($promptFull))

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
timeout $timeout opencode run -m "$id" < "`$W/out/.prompt.txt" > "`$W/out/.agent-output.txt" 2>&1
RC=`$?
Q1=`$(date +%s%N)
printf '{"state":"done","pid":%d,"ts_start":"%s","task_id":"%s","host":"agent-cli"}' "`$$" "`$(date -Is)" "$ts" > "`$S"
QUEUE=`$(( (Q1-Q0)/1000000 ))
echo "QUEUE_S=`$QUEUE"
echo "TASK_RC=`$RC"
echo "OUT_BYTES=`$(wc -c < "`$W/out/.agent-output.txt" 2>/dev/null)"
printf 'QUEUE_S=%s\nTASK_RC=%s\n' "`$QUEUE" "`$RC" > "`$W/out/.meta"
exit `$RC
"@
    $code = Invoke-RemoteScript -HostName $hostName -ScriptBody $body -LocalName "agent-cli-task-$ts.sh"
    # DESIGN §9.5 exit-code dispatch: 124(timeout by `timeout`) -> 6; other remote run rc preserved as failure
    if ($code -eq 124) { $code = 6 }
    Write-Host "TASK remote excode=$code"

    # 6) collect: pull out/.meta + out/.agent-output.txt, compute content_digest (M1)
    $outTxt = Join-Path $env:TEMP "agent-cli-out-$ts.txt"
    $metaTxt = Join-Path $env:TEMP "agent-cli-meta-$ts.txt"
    scp -q -o ConnectTimeout=10 "${hostName}:$W/out/.agent-output.txt" "$outTxt" 2>$null
    scp -q -o ConnectTimeout=10 "${hostName}:$W/out/.meta" "$metaTxt" 2>$null
    $queue_s = 0
    if (Test-Path $metaTxt) {
        $m = Get-Content $metaTxt | Out-String
        if ($m -match 'QUEUE_S=(\d+)') { $queue_s = [int]$matches[1] }
    }
    $contentSha = ''
    if (Test-Path $outTxt) { $contentSha = Get-Sha256Text ([IO.File]::ReadAllText($outTxt)) }

    # 7) .agent-run.json under <proj>/agent-out/<ts>/ (DESIGN §6.2)
    $projOutRoot = Join-Path $projRoot 'agent-out'
    if (-not (Test-Path $projOutRoot)) { New-Item -ItemType Directory -Path $projOutRoot -Force | Out-Null }
    $runDir = Join-Path $projOutRoot $ts
    New-Item -ItemType Directory -Path $runDir -Force | Out-Null
    $run = [ordered]@{
        proj = $proj
        task_id = "task-$ts"
        cli = 'opencode'
        model = $id
        sensitivity = $sens
        readonly = $readonly
        session_id = ''
        exit_code = $code
        status = if ($code -eq 0) { 'completed' } elseif ($code -eq 6) { 'timeout' } else { 'failed' }
        content_digest = "sha256:$contentSha"
        usage = [ordered]@{ total_tokens = 0; tool_uses = 0 }
        queue_s = $queue_s
        run_s = 0
        timestamp_start = ''
        timestamp_end = ''
        prompt_sha256 = "sha256:$promptSha"
        attach = @()
    }
    $run | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $runDir '.agent-run.json') -Encoding utf8
    # move pulled output into runDir
    if (Test-Path $outTxt) { Move-Item $outTxt (Join-Path $runDir 'agent-output.txt') -Force }
    Remove-Item (Join-Path $projRoot 'agent-out\.agent-run.json') -ErrorAction SilentlyContinue

    # 8) ledger line (G13)
    $ledger = Join-Path $projRoot 'agent-runs.log'
    $line = "$ts,$proj,$id,$sens,$code,0,0"
    Add-Content -Path $ledger -Value $line -Encoding utf8

    Write-Host "TASK_DONE dir=$runDir exit=$code prompt_sha256=sha256:$promptSha content_digest=sha256:$contentSha"
    Write-Host "ledger+=$line"
    return $code
}

# ---------------- entry ----------------
try {
    if ($Command -eq 'workspace') {
        $act = if ($Create) { 'create' } elseif ($Sync) { 'sync' } elseif ($Archive) { 'archive' } else { 'create' }
        if (-not $Proj) { $Proj = $env:AGENT_CLI_PROJ }
        Invoke-Workspace -proj $Proj -act $act -type $Type
        exit 0
    }
    elseif ($Command -eq 'route') {
        # M3 router diagnostic (A8). usage: agent-cli route --model <name> [--sensitivity <x>]
        if (-not $Model) { Write-Host 'usage: agent-cli route --model <alias|full-id> [--sensitivity public|sanitized|local-only]'; exit 2 }
        $code = Invoke-Router -model $Model -sensitivity $Sensitivity
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
        # M2 full chain. usage: agent-cli task <proj> --card <task.md> [--model <m>] [--sensitivity <x>]
        $code = Invoke-Task -proj $Proj -card $Card -model $Model -sensitive $Sensitivity -type $Type -hostName $RemoteHost
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
    exit 1
}