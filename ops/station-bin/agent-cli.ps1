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
    [string]$KeyFile = ''        # ssh key (optional)
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
    if (-not (Test-RemoteReach $HostName)) { throw "remote unreachable: $HostName (ensure station online)" }
    if (-not $LocalName) { $LocalName = "agent-cli-run-$([DateTime]::Now.ToString('HHmmss')).sh" }

    $localPath = Join-Path $Script:TMP_ROOT $LocalName
    if (-not (Test-Path $Script:TMP_ROOT)) { New-Item -ItemType Directory -Path $Script:TMP_ROOT -Force | Out-Null }
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($localPath, $ScriptBody, $utf8NoBom)

    scp -q -o ConnectTimeout=10 $localPath "${HostName}:/tmp/${LocalName}"
    if ($LASTEXITCODE -ne 0) { throw "scp failed: $LocalName" }

    ssh -o ConnectTimeout=10 $HostName "bash /tmp/${LocalName}"
    $code = $LASTEXITCODE
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
            $cmd = @($Script:GNU_TAR) + @('--force-local','-cf', $tarFile, '.') + $exArgs
            & $cmd
            if ($LASTEXITCODE -ne 0) { throw 'tar sync failed (trim .agentsync if exceed)' }
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

# ---------------- entry ----------------
try {
    if ($Command -eq 'workspace') {
        $act = if ($Create) { 'create' } elseif ($Sync) { 'sync' } elseif ($Archive) { 'archive' } else { 'create' }
        if (-not $Proj) { $Proj = $env:AGENT_CLI_PROJ }
        Invoke-Workspace -proj $Proj -act $act -type $Type
        exit 0
    }
    elseif ($Command -eq 'task') {
        Write-Host '[T1 placeholder] task cmd implemented in T3. usage: agent-cli task <proj> ...'
        exit 0
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