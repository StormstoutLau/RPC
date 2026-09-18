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
    [string]$TaskType = '',      # task cmd: code|reason|concept|numeric|doc -> 6.4 thinking/template
    [int]$EngineCtxHint = 0,     # route cmd (test): simulate engine n_ctx to exercise clamp (radical fix B); 0=off
    [string]$RunId = '',         # review cmd (O-16): target runDir ts; empty -> newest completed run
    [switch]$Overwrite,          # review cmd (O-16): allow re-review overwriting existing review.json
    [switch]$SlotAllowBusy,      # O-25 P1: allow task dispatch even if target engine /slots busy
    [string]$Cli = ''            # task cmd (O-15): executor selector: ''(auto by route/card) | opencode | claude (控制台本地备路)
)

# ---------------- constants / env ----------------
$ErrorActionPreference = 'Stop'
$Script:GNU_TAR = 'C:\Program Files\Git\usr\bin\tar.exe'   # S1: not Win10 bsdtar
$Script:REMOTE_USER = 'scott-lau'
$Script:WORKSPACE_ROOT = '/home/scott-lau/agent-workspaces'
$Script:WORKSPACE_ARCHIVE_ROOT = '/home/scott-lau/agent-workspaces-archive'   # O-02 (2026-09-14): archive snapshot root
$Script:PROJECTS = @{ paper = 'D:\Paper'; Cpp_Hub = 'F:\Cpp_Hub'; Auto_Prover = 'F:\Auto_Prover' }    # console project root mapping (2026-09-14 Cpp_Hub 修正指真实主项目 F:)
$Script:TMP_ROOT = Join-Path $env:TEMP 'agent-cli'
# O-12 REPO_ROOT: repo root for golden source resolution (this file is d:\RPC\ops\station-bin\ ->
# two parents up = d:\RPC). NEW script var (IMPLEMENTATION §3.2 P1-1: not inherited/现役).
$Script:REPO_ROOT = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
# V2 concurrency (O-11 L2/O-26): 单控制台并发调用时, TMP_ROOT 用 per-invocation token 子目录,
#   避免固定名临时脚本 (agent-cli-attach-mkdir.sh 等) 被并发进程互撞 (shared-temp race)。
$Script:RUN_TOKEN = [Guid]::NewGuid().ToString('N')
$Script:TMP_ROOT = Join-Path $env:TEMP ("agent-cli-" + $Script:RUN_TOKEN)

# ---------------- ROUTE_TABLE (BP-2 alias->full-id, T3 task uses; fixed here) ----------------
# NOTE (2026-09-16): provider 名已统一为 `local`（三站 opencode.jsonc 实况: 仅 local + openrouter）。
# 旧名 'cluster-litellm/*' 已不存在 —— 沿用会让 _station_ready.sh 注入 ERR_INJECT exit 11、整条派发门挂掉。
# 模型 id 现为 `local/<flavor>`，flavor 与 local.models 声明键一一对应（保留风味/站点语义）。
$Script:ROUTE_TABLE = @{
    # alias -> @{ id=full-id; station=target }
    'nemotron'   = @{ id = 'local/nemotron';                          station = 'B' }
    'qwen'       = @{ id = 'local/qwen';                              station = 'B' }
    'gpt-oss'    = @{ id = 'local/gpt-oss';                           station = 'A' }
    'gpt-oss-20b'= @{ id = 'local/gpt-oss-20b';                       station = 'B' }   # O-13 sympy 收口卡 (B 站 20b, 2026-09-14)
    'lightning'  = @{ id = 'opencode/nemotron-3.5-lightning-free';              station = 'B' }
    'ultra'      = @{ id = 'opencode/nemotron-3-ultra-free';                    station = 'B' }
    'free-1m'    = @{ id = 'opencode/nemotron-3-ultra-free';                    station = 'B' }  # alias of ultra
    # C 站 (seaviv) 2026-09-09: gpt-oss 本地引擎已注入 8080; nemotron 模型已传待启
    'gpt-oss-c'  = @{ id = 'local/gpt-oss';                           station = 'C' }
    'nemotron-c' = @{ id = 'local/nemotron';                          station = 'C' }
    # 2026-09-16: m27-q4ks (MiniMax-M2.7) / qwen3.8-flash-next UD-IQ4_XS 三站齐备 (C 源 -> A/B 已同步)
    # ⚠ 别名必须用站上 infer-load alias 空间真值 (m27-q4ks), 不是模型技术名 (minimax-m2.7) —— 见 cluster.py ROUTE 注
    'm27-q4ks'       = @{ id = 'local/m27-q4ks';                      station = 'C' }
    'm27-q4ks-a'     = @{ id = 'local/m27-q4ks';                      station = 'A' }
    'm27-q4ks-b'     = @{ id = 'local/m27-q4ks';                      station = 'B' }
    'flash-next'     = @{ id = 'local/qwen3.8-flash-next';            station = 'C' }
    'flash-next-a'   = @{ id = 'local/qwen3.8-flash-next';            station = 'A' }
    'flash-next-b'   = @{ id = 'local/qwen3.8-flash-next';            station = 'B' }
    # full id directly (M3 dual representation)
    'local/nemotron'              = @{ id = 'local/nemotron';              station = 'B' }
    'local/qwen'                  = @{ id = 'local/qwen';                  station = 'B' }
    'local/gpt-oss'               = @{ id = 'local/gpt-oss';               station = 'A' }
    'local/m27-q4ks'              = @{ id = 'local/m27-q4ks';              station = 'C' }
    'local/qwen3.8-flash-next'    = @{ id = 'local/qwen3.8-flash-next';    station = 'C' }
    'opencode/nemotron-3.5-lightning-free'  = @{ id = 'opencode/nemotron-3.5-lightning-free';  station = 'B' }
    'opencode/nemotron-3-ultra-free'        = @{ id = 'opencode/nemotron-3-ultra-free';        station = 'B' }
    # O-15 claude 备通道 (2026-09-12): 控制台本地执行, station 空 = 不走 ssh. cli=claude 选中本地执行器.
    #   id = 传给 `claude -p --model` 的 Claude 型号; 作者/登录走 claude CLI 自身 (claude auth/login)。
    'claude'       = @{ id = 'claude-sonnet-4-5'; station = ''; cli = 'claude' }   # 默认备份型号
    'claude-opus'  = @{ id = 'claude-opus-4-1';    station = ''; cli = 'claude' }   # 高保真备路
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
    if ($station -eq 'C') { return '192.168.1.37' }   # C (seaviv): 无 avahi .local, 用管理网 IP
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
    # C2 (2026-09-16): 引擎面固定 unsloth studio :8080 (OpenAI + Anthropic + Responses 三协议),
    # _station_ready.sh 只做**就绪校验**, 不再改写任何配置 (旧实现就地改写 local.baseURL
    # => 任务后留下死端口 + 三站 config 漂移 + 门禁 stations 转红)。
    # 密钥新鲜度由 infer-load 落盘 ~/.config/rpc/unsloth.key 保证。
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
    if ($joined -notmatch 'STATION_READY port=' -or $joined -notmatch 'CHAT_OK') { throw "STATION_NOT_READY: readiness not confirmed ($HostName)" }
    # radical fix B: surface real engine n_ctx (if present) so caller clamps profile.context
    $ctx = 0
    if ($joined -match 'ENGINE_CTX=(\d+)') { $ctx = [int]$Matches[1] }
    return @{ ok=$true; engine_ctx=$ctx; raw=$joined }
}

function Invoke-SlotGate {
    # O-25 P1 (2026-09-12): probe llama-server /slots on target station BEFORE dispatch.
    # Criteria O-08/F1: dispatch must NOT silently queue behind an occupied engine -> busy/reject.
    # Only meaningful for in-cluster llama engines; callers decide enforcement (egress have no /slots).
    # Never blocks on probe failure: ssh/scp/pass failures degrade to na=allow (observability, not a
    # hard gate on infra flake). Uses ssh-capture (returns objects), unlike Invoke-RemoteScript which
    # only streams stdout.
    [CmdletBinding()]
    param(
        [string]$HostName,
        [int]$Port
    )
    $na = @{ na = $true; ok = $false; slot_total = 0; slot_busy = 0; slot_queue = 0 }
    if (-not (Test-RemoteReach $HostName)) { return $na }
    $tmp = Join-Path $Script:TMP_ROOT '_slot_gate.sh'
    New-Item -ItemType Directory -Path $Script:TMP_ROOT -Force | Out-Null
    Copy-Item 'D:\RPC\ops\station-bin\_slot_gate.sh' $tmp -Force
    scp -q -o ConnectTimeout=10 $tmp "${HostName}:/tmp/_slot_gate.sh"
    if ($LASTEXITCODE -ne 0) { return $na }
    try {
        $out = ssh -o ConnectTimeout=10 $HostName "bash /tmp/_slot_gate.sh $Port" 2>&1
        $code = $LASTEXITCODE
    }
    catch {
        $out = @("$($_.Exception.Message)")
        $code = 255
    }
    foreach ($ln in $out) { Write-Host $ln }
    $joined = $out -join "`n"
    if ($code -eq 20) { return $na }
    if ($joined -match 'SLOT_NA') { return @{ na = $true; ok = $true; slot_total = 0; slot_busy = 0; slot_queue = 0 } }
    $t = 0; $b = 0; $q = 0
    if ($joined -match 'SLOT_TOTAL=(\d+)') { $t = [int]$Matches[1] }
    if ($joined -match 'SLOT_BUSY=(\d+)')  { $b = [int]$Matches[1] }
    if ($joined -match 'SLOT_QUEUE=(\d+)') { $q = [int]$Matches[1] }
    return @{ na = $false; ok = $true; slot_total = $t; slot_busy = $b; slot_queue = $q }
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
    $station = if ($Station) { $Station } elseif ($HostName -in @('A','B','C')) { $HostName } else { 'B' }
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
        # O-02 (2026-09-14): formal archive - timestamp snapshot tar of remote workdir,
        #   kept in ~/agent-workspaces-archive/<proj>/. Preserves live workdir + station memory (R7).
        # Single-quoted here-string: all $ literal (PS keeps $.Replace injects paths reliably vs $Script: interpolation ambiguity).
        $body = @'
set -eu
W=__PLACEHOLDER_W__
AR=__PLACEHOLDER_AR__
STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p "$AR"
if [ ! -d "$W" ]; then echo "ARCHIVE_SKIP nodir $W"; exit 0; fi
tar -C "$(dirname "$W")" -cf "$AR/__PLACEHOLDER_P__-$STAMP.tar" "$(basename "$W")"
SIZE=$(du -h "$AR/__PLACEHOLDER_P__-$STAMP.tar" | cut -f1)
echo "ARCHIVED $AR/__PLACEHOLDER_P__-$STAMP.tar ($SIZE) live workdir preserved (R7)"
ls -1 "$AR" | sort
'@
        $body = $body.Replace('__PLACEHOLDER_W__', "$Script:WORKSPACE_ROOT/$proj").Replace('__PLACEHOLDER_AR__', "$Script:WORKSPACE_ARCHIVE_ROOT/$proj").Replace('__PLACEHOLDER_P__', $proj)
        Invoke-RemoteScript -HostName $hostName -ScriptBody $body -LocalName "agent-cli-ws-archive.sh"
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
    param([string]$model, [string]$complexity, [string]$taskType, [int]$EngineCtx = 0)
    # EngineCtx > 0 = real n_ctx detected from target engine (radical fix B). When present,
    # it becomes the ONLY source of truth: profile.context is clamped to min(intent, EngineCtx),
    # eliminating the engine-ctx < request 400 deadlock (refdedupe 12536 vs nothink -c 8192).
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
    $ctxMax = @{ 'nemotron'=131072; 'qwen'=131072; 'gpt-oss'=131072; 'lightning'=262144; 'ultra'=1000000; 'free-1m'=1000000 }
    $modelCtx = 262144
    if ($model -and $ctxMax.ContainsKey($model)) { $modelCtx = $ctxMax[$model] }
    # radical fix B: engine real n_ctx overrides the static ctxMax table entirely when known.
    # (engine ctx = ONLY truth; static table is fallback for engines lacking /props)
    if ($EngineCtx -gt 0) { $modelCtx = $EngineCtx }
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
    # radical fix B: engine ctx clamp. Engine ctx = ONLY truth; intent>engine -> clamp +
    # WARN so the 400-deadlock is impossible and the mismatch is visible in meta.
    if ($EngineCtx -gt 0 -and $pro['context'] -gt $EngineCtx) {
        $pro['context'] = [int]$EngineCtx
        $src = "$src;ctx-clamped-to-engine=$EngineCtx"
    }
    return [pscustomobject]@{ profile=$pro['name']; context=$pro['context']; max_output=$pro['max_output'];
                             thinking=$pro['thinking']; template=$pro['template']; reasoning_format=$pro['reasoning_format'];
                             flavor=$pro['flavor']; source=$src }
}

# ---------------- O-25 P0-①: model-flavor throughput bench (dispatch-time estimate) ----------------

# $TpBench: route model id -> { prefill_tps; decode_tps; src }. Source: THROUGHPUT-BASELINE.md anchors.
# Only HIT rows produce an estimate; MISS rows never fabricate (no-bench discipline: source must be non-empty).
# prefill omitted (null) = unmeasured -> prefill_sec treated as 0 (agent budget is decode-dominated).
# ASCII only on purpose: Edit strips UTF-8 BOM, PS5.1 re-decode of non-ASCII comments can crash parse.
$TpBench = @{
    'local/gpt-oss' = @{ prefill = 125; decode = 50; src = 'THROUGHPUT-BASELINE#L13-14 (HIP A124/C152)' }    # gpt-oss-120b MXFP4, decode 49-53
    'local/nemotron' = @{ prefill = $null; decode = 22; src = 'THROUGHPUT-BASELINE#L15 (nemotron-120B HIP20.5)' } # decode-level only; prefill unmeasured
    # 2026-09-16 转正为派发别名后补入 (src 见 THROUGHPUT-BASELINE.md, 均为 decode-level)
    'local/m27-q4ks'           = @{ prefill = $null; decode = 21.5; src = 'THROUGHPUT-BASELINE#L16 (MiniMax-M2.7 UD-IQ4_XS, C 单机)' }
    'local/qwen3.8-flash-next' = @{ prefill = $null; decode = 19;   src = 'THROUGHPUT-BASELINE#L18 (flash-next 短ctx 19-20; 长ctx 塌缩 5.5-6.1)' }
    # deepseek-v4-flash-0731(7.9) 仍非派发别名 -> MISS here until routed via this table.
}

function Get-ThroughputEstimate {
    # Dispatch-time budget estimate (O-25 criteria-3): prefill + decode phases x agent-loop fudge.
    # NON-linear: pure tok/throughput is a lower bound; tool-call/thought/retry adds real wall-clock.
    param([string]$modelId, [int]$maxOutput, [int]$context, [double]$fudge = 1.6)
    if (-not $TpBench.ContainsKey($modelId)) { return @{ hit = $false } }
    $b = $TpBench[$modelId]
    $prefillSec = if ($b.prefill -and $context -gt 0) { ([double]$context / [double]$b.prefill) } else { 0.0 }
    $decodeSec  = if ($b.decode -gt 0) { ([double]$maxOutput / [double]$b.decode) } else { 0.0 }
    $total = (([double]$prefillSec + $decodeSec)) * $fudge
    return @{ hit = $true; prefill = $prefillSec; decode = $decodeSec; total = $total; src = $b.src }
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
    $h = @{ model=''; sensitivity=''; readonly=$false; timeout_s=900; task=''; cli='opencode'; accept=@(); body=''; complexity=''; 'task-type'=''; 'isolate-xdg'=$false }
    # O-24 P0-①: continue-timeout-s - independent resume budget (default = timeout_s)
    $h['continue-timeout-s'] = 0
    # O-12: accept-golden single-object {source, cmd} (IMPLEMENTATION §3.1 M1)
    $h['accept-golden'] = @{ source=''; cmd='' }
    # O-16 review ring: advisory judge routing + reserved gate toggle + judge timeout budget
    $h['review-model'] = ''
    $h['review-gate']  = 'false'
    $h['review-timeout-s'] = 0
    # O-26 Split-Dispatcher (2026-09-12): decompose ordered shard list. Each item = one shard's
    # task description. Dispatcher splits master card into N sub-cards (one per shard) and fans
    # them across stations (cross-station each 1). Only valid for readable (readonly) big tasks.
    $h['decompose'] = @()
    $inFreq = $false; $bodyRead = $false; $curKey = ''
    $bodyLines = @()
    $lines = [System.IO.File]::ReadAllLines($Path, [System.Text.UTF8Encoding]::new($false))
    foreach ($l in $lines) {
        # 缺口10 修复 (2026-09-18): 围栏判据加 `-not $bodyRead` 守卫。
        #   原判据"遇 `---` 即翻转"⇒ 正文里的 markdown 分隔线把 inFreq 翻回 true, 其后**正文行**
        #   若形如 `key: value` 且命中已知键, 会被 `$h[$k] = $v` **静默覆盖**已解析的 front-matter
        #   (实测能被覆盖的含 `readonly`/`task`/`model` —— 卡正文可静默改写卡契约)。
        #   `$bodyRead` 一旦置真即表示 front-matter 已闭合, 此后任何 `---` 都只是正文。
        #   回归用例: _fm_golden_test.ps1 的 fence 四例。
        if (-not $bodyRead -and $l.Trim() -eq '---') { if (-not $inFreq) { $inFreq = $true; continue } else { $inFreq = $false; $bodyRead = $true; continue } }
        # O-12 M1: nested source/cmd under accept-golden MUST be matched BEFORE the top-level regex
        # (`\s*` allows leading whitespace, so indented `  source:` would hit the generic key branch
        # and be dropped by the whitelist gate - P2-1/IMPLEMENTATION §3.1).
        elseif ($inFreq -and $curKey -eq 'accept-golden' -and $l -match '^\s{2,}(source|cmd)\s*:\s*(.+)$') {
            $h['accept-golden'][$matches[1].ToLower()] = $matches[2].Trim()
        }
        elseif ($inFreq -and $l -match '^\s*([A-Za-z_\-]+)\s*:\s*(.*)$') {
            $k = $matches[1].ToLower(); $v = $matches[2].Trim()
            $curKey = ''
            if ($h.ContainsKey($k)) {
                if ($k -eq 'accept') { $curKey = 'accept' }
                elseif ($k -eq 'accept-golden') { $curKey = 'accept-golden' }   # O-12: enter nested object mode
                elseif ($k -eq 'decompose') { $curKey = 'decompose' }          # O-26: ordered shard list mode
                else { $h[$k] = $v }
            }
        }
        elseif ($inFreq -and $curKey -eq 'accept' -and $l -match '^\s*-\s+(.+)$') {
            $h['accept'] += $matches[1].Trim()
        }
        elseif ($inFreq -and $curKey -eq 'decompose' -and $l -match '^\s*-\s+(.+)$') {
            $h['decompose'] += $matches[1].Trim()
        }
        elseif ($bodyRead) {
            $bodyLines += $l
            $t = $l -replace '^#{1,6}\s*任务描述\s*', '' -replace '^#{1,6}\s*', ''
            if (-not $h['task'] -and $t.Trim()) { $h['task'] = $t.Trim() }
        }
    }
    $h['body'] = (($bodyLines -join "`n").Trim())
    if ($h['readonly'] -eq 'true') { $h['readonly'] = $true } else { $h['readonly'] = $false }
    # O-09 isolate-xdg: 并行写任务各自 XDG_DATA_HOME 隔离 opencode.db, 消除同站并发写锁串行化.
    if ($h['isolate-xdg'] -eq 'true') { $h['isolate-xdg'] = $true } else { $h['isolate-xdg'] = $false }
    $ts = 0
    if (-not [int]::TryParse([string]$h['timeout_s'], [ref]$ts) -or $ts -le 0) { $ts = 900 }
    $h['timeout_s'] = $ts
    # O-24 P0-①: continue-timeout-s - independent resume budget; 0 sentinel = fall back to timeout_s
    $cts = 0
    if (-not [int]::TryParse([string]$h['continue-timeout-s'], [ref]$cts) -or $cts -le 0) { $cts = 0 }
    $h['continue-timeout-s'] = $cts
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
        [string]$taskType,   # 6.4: code|reason|concept|numeric|doc
        [string]$cli,        # O-15 executor: ''(auto by route/card) | opencode | claude (控制台本地备路)
        [switch]$SlotAllowBusy   # O-25 P1: allow dispatch even if target engine /slots busy
    )
    if (-not $card) { Write-Host 'task requires --card <task.md>'; return 2 }
    if (-not (Test-Path $card)) { throw "card not found: $card" }
    $projRoot = $Script:PROJECTS[$proj]
    if (-not $projRoot -or -not (Test-Path $projRoot)) { throw "unknown/missing project: $proj (registered: $($Script:PROJECTS.Keys -join ','))" }
    if (-not $attach) { $attach = @() }
    # O-25 P1: slot-gate decision fields for ledger (default not-gated)
    $slotGate = [ordered]@{ gated=$false; total=0; busy=0; queue=0; action='na' }

    # 1) card front-matter
    $fm = Get-FrontMatter $card
    $m = if ($model) { $model } else { if ($fm['model']) { $fm['model'] } else { '' } }
    $sens = if ($sensitive) { $sensitive } else { if ($fm['sensitivity']) { $fm['sensitivity'] } else { 'public' } }
    if (-not $m) { Write-Host 'REJECT missing-model (exit 2) - card has no model and no --model (inv 3)'; return 2 }
    $readonly = [bool]$fm['readonly']
    # O-09 isolate-xdg: 1 => 远程 $body 里 per-task XDG_DATA_HOME 隔离 opencode.db (同站并行写任务用)
    $isolateXdgOn = if ([bool]$fm['isolate-xdg']) { 1 } else { 0 }
    $timeout = [int]$fm['timeout_s']
    # O-24 P0-①: resume gets its OWN budget (continue-timeout-s); 0/absent => same as timeout_s.
    # Real recovery scenario (2026-09-09): first run killed at the timeout, resume must NOT inherit
    # the already-consumed first budget - it gets a fresh full budget and can use it up to the cap.
    $continueTimeout = [int]$fm['continue-timeout-s']
    if ($continueTimeout -le 0) { $continueTimeout = $timeout }
    Write-Host "BUDGET: first=$timeout resume=$continueTimeout"

    # 2) M3 route (reuse Resolve-Model + local-only gate)
    $r = Resolve-Model $m
    if (-not $r) { Write-Host "REJECT unknown-model ($m) exit 2 - not in route table"; return 2 }
    $id = $r['id']; $station = $r['station']
    if ($sens -eq 'local-only' -and $id -match '^opencode/') { Write-Host "REJECT local-only+remote ($id) exit 4 - no override channel"; return 4 }
    # O-15 claude 备通道: 有效执行器 = --cli > route.cli > card.cli > opencode. claude => 控制台本地执行分支.
    $effectiveCli = if ($cli) { $cli.ToLower() } elseif ($r['cli']) { [string]$r['cli'] } elseif ($fm['cli']) { [string]$fm['cli'].ToLower() } else { 'opencode' }
    Write-Host "CLI=$effectiveCli route_station=$station"
    if ($effectiveCli -eq 'claude') {
        return Invoke-Task-Claude -proj $proj -card $card -model $m -sensitive $sens -attach $attach -complexity $complexity -taskType $taskType
    }
    elseif ($effectiveCli -ne 'opencode') {
        Write-Host "REJECT unknown-cli ($effectiveCli) - only opencode|claude supported"
        return 2
    }
    if (-not $hostName) { $hostName = Get-TargetHost $station }

    # 6.4 complexity routing: CLI --complexity/--task-type > card front-matter > default(reason)
    $cx = if ($complexity) { $complexity } else { if ($fm['complexity']) { $fm['complexity'] } else { 'auto' } }
    $tt = if ($taskType) { $taskType } else { if ($fm['task-type']) { $fm['task-type'] } else { '' } }

    # radical fix B (order): station-ready MUST run before profile resolve so the real
    # engine n_ctx is known -> profile.context clamped to min(intent, engine ctx).
    # This kills the engine-ctx < request 400 deadlock at its source.
    $baseAliasE = ($m -split '/')[-1]
    $readyInfo = $null
    try { $readyInfo = Invoke-StationReady -HostName $hostName -Alias $baseAliasE }
    catch { Write-Host "STATION_NOT_READY: $($_.Exception.Message)"; return 10 }
    $engineCtx = if ($readyInfo -and $readyInfo['engine_ctx']) { [int]$readyInfo['engine_ctx'] } else { 0 }

    # O-25 P1: slot gate AFTER station-ready (engine port known), BEFORE sync/run dispatch.
    # Criteria O-08/F1: dispatch must NOT silently queue behind an occupied engine. Default reject-if-busy
    # (exit 24, clear semantics for orchestrator to redirect); --slot-allow-busy overrides.
    # Only gates in-cluster llama engines (local/*); egress (opencode/*) has no /slots -> skip.
    # na (SLOT_NA or probe failure) always allow - probe is observability, never a hard gate on infra flake.
    if ($id -like 'local/*') {
        $port = 0
        if ($readyInfo -and $readyInfo['raw'] -match 'STATION_READY port=(\d+)') { $port = [int]$Matches[1] }
        if ($port -gt 0) {
            $sg = Invoke-SlotGate -HostName $hostName -Port $port
            $slotGate.gated = $true
            $slotGate.total = $sg['slot_total']
            $slotGate.busy  = $sg['slot_busy']
            $slotGate.queue = $sg['slot_queue']
            if ($sg['na']) {
                $slotGate.action = 'na'
                Write-Host "SLOT-GATE: na (no /slots or probe fail), allow"
            }
            elseif ($sg['slot_busy'] -ge $sg['slot_total'] -or $sg['slot_queue'] -gt 0) {
                if ($SlotAllowBusy) {
                    $slotGate.action = 'allow-busy'
                    Write-Host "SLOT-GATE: total=$($sg['slot_total']) busy=$($sg['slot_busy']) queue=$($sg['slot_queue']) - busy, but --slot-allow-busy, allow"
                }
                else {
                    $slotGate.action = 'reject'
                    Write-Host "SLOT-GATE: total=$($sg['slot_total']) busy=$($sg['slot_busy']) queue=$($sg['slot_queue']) - busy, reject dispatch (use --slot-allow-busy to override) [exit 24]"
                    return 24
                }
            }
            else {
                $slotGate.action = 'allow'
                Write-Host "SLOT-GATE: total=$($sg['slot_total']) busy=$($sg['slot_busy']) queue=$($sg['slot_queue']) - idle, allow"
            }
        }
        else {
            $slotGate.action = 'na'
            Write-Host "SLOT-GATE: na (engine port unknown)"
        }
    }
    else {
        $slotGate.action = 'egress'
        Write-Host "SLOT-GATE: skip (egress $id)"
    }

    $prof = Resolve-Profile -model $m -complexity $cx -taskType $tt -EngineCtx $engineCtx
    $profTxt = "profile=$($prof.profile) ctx=$($prof.context) max_out=$($prof.max_output) thinking=$($prof.thinking) template=$($prof.template) reasoning=$($prof.reasoning_format) flavor=$($prof.flavor) ($($prof.source))"
    Write-Host "PROFILE: $profTxt"
    if ($engineCtx -gt 0) { Write-Host "ENGINE_CTX=$engineCtx (ctx clamped to engine truth)" }
    # L1 hint (only log, NEVER auto-unload/reload - GTT mutually exclusive, avoid disrupting loaded instance):
    if ($prof.flavor -eq 'nothink' -or $prof.flavor -eq 'long') { Write-Host "PROFILE-L1-HINT: flavor=$($prof.flavor) - requires instance with matching CTX/template; verify loaded instance or reload manually" }

    # O-25 P0-① (criteria-3): dispatch-time budget estimate - prefill+decode phases x fudge, vs hard timeout_s.
    # HIT only from bench table; MISS prints no fabricated number (no-bench discipline).
    $est = Get-ThroughputEstimate -modelId $id -maxOutput $prof.max_output -context $prof.context
    if ($est.hit) {
        Write-Host ("ESTIMATE: model=$id prefill_sec={0:N0} decode_sec={1:N0} est_total_s={2:N0} (bench={3})" -f $est.prefill, $est.decode, $est.total, $est.src)
        if ($est.total -gt $timeout) {
            Write-Host ("TIMEOUT-WARN: est_total_s={0:N0} > timeout_s={1} (x{2:N1}) - first run likely killed; raise timeout_s/continue-timeout-s or lower complexity/max_output" -f $est.total, $timeout, ($est.total / $timeout))
        }
    }
    else {
        Write-Host "ESTIMATE: model=$id no-bench (MISS) - skip dispatch estimate"
    }

    # TODO-2 pre-flight (2026-09-07): fail fast on unwritable agent-out BEFORE station-ready/sync/run.
    # Route+profile dry-run above already printed; now verify the local collect destination.
    if (-not (Assert-AgentOutWritable -projRoot $projRoot)) {
        Write-Host "ABORT: agent-out not writable (exit 12) - fix Settings > Permission & Approval > Custom Configuration"
        return 12
    }

    # O-19: station env-ready gate (discover engine port + inject local provider baseURL BEFORE dispatch)
    # (already run above as part of radical fix B - engine ctx discovery)

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

    # 4c) golden (O-12, IMPLEMENTATION §3.2 M2): authoritative golden test injected BEFORE dispatch
    #     (inv 3: after sync, before $body; clean-inject = .golden equals current injection).
    #     source resolved against REPO_ROOT; checksum computed console-side ONCE and embedded as
    #     literal in fused script (inv 5, P1-1: no .golden.sha256 manifest file in workspace).
    $g = $fm['accept-golden']
    $goldenActive = [bool]($g.source -and $g.cmd)
    $goldenSha = ''; $goldenCmdB64 = ''; $goldenBase = ''
    $goldenBlock = ''
    if ($goldenActive) {
        try {
            $gSrc = Resolve-Path (Join-Path $Script:REPO_ROOT $g.source) -ErrorAction Stop
        }
        catch {
            Write-Host "GOLDEN_SOURCE_MISSING: $($g.source) (resolved under $Script:REPO_ROOT)"
            return 2   # abort BEFORE dispatch - no session started
        }
        $goldenBase   = [IO.Path]::GetFileName($gSrc)
        $goldenSha    = (Get-FileHash -Algorithm SHA256 $gSrc).Hash.ToLower()
        $goldenCmdB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($g.cmd))
        $goldenTgz = Join-Path $env:TEMP "agent-cli-golden-$ts.tgz"
        & $Script:GNU_TAR --force-local -C (Split-Path $gSrc) -cf $goldenTgz $goldenBase
        if ($LASTEXITCODE -ne 0) { Write-Host "GOLDEN_TAR_FAIL: $($g.source)"; Remove-Item $goldenTgz -ErrorAction SilentlyContinue; return 2 }
        scp -q -o ConnectTimeout=10 $goldenTgz "${hostName}:$W/.golden.tgz"
        if ($LASTEXITCODE -ne 0) { Write-Host "NETFAIL: golden scp failed"; Remove-Item $goldenTgz -ErrorAction SilentlyContinue; return 5 }
        Remove-Item $goldenTgz -ErrorAction SilentlyContinue
        # clean-inject (inv 3, P2-3): rm -rf .golden THEN extract -> golden path equals current injection
        # compress convention: plain tar (`-cf`/`-xf`) matches live sync chain (L246/L260) - NOT gzip;
        # mismatched `-xzf` would fail "not in gzip format" (V0 real-run finding, 2026-09-09)
        $goldenInject = @"
set -eu
W="$Script:WORKSPACE_ROOT/$proj"
rm -rf "`$W/.golden" && mkdir -p "`$W/.golden" \
  && tar -xf "`$W/.golden.tgz" -C "`$W/.golden" && rm -f "`$W/.golden.tgz"
"@
        Invoke-RemoteScript -HostName $hostName -ScriptBody $goldenInject -LocalName "agent-cli-golden-$ts.sh"
        # M3 golden block (fused into $body below; literal interpolation ONLY for the three
        # console-side values goldenSha/goldenBase/goldenCmdB64 - all remote vars backtick-escaped)
        $goldenBlock = @"
GOLDEN_ACTIVE=1
GOLDEN_SHA="$goldenSha"
GOLDEN_BASE="$goldenBase"
GOLDEN_CMD_B64="$goldenCmdB64"
echo "`$GOLDEN_SHA  `$W/.golden/`$GOLDEN_BASE" | sha256sum -c >/dev/null 2>&1
TAMPER_RC=`$?
if [ `$TAMPER_RC -ne 0 ]; then
  echo "GOLDEN_TAMPERED"
  ACCEPT_GOLDEN_OK=0
else
  echo "`$GOLDEN_CMD_B64" | base64 -d > "`$W/out/.golden-cmd.txt"
  ( cd "`$W" && eval "`$(cat "`$W/out/.golden-cmd.txt")" ) > "`$W/out/.accept-golden-output.txt" 2>&1
  GOLDEN_RC=`$?
  [ `$GOLDEN_RC -ne 0 ] && { echo "GOLDEN_FAIL rc=`$GOLDEN_RC"; ACCEPT_GOLDEN_OK=0; }
fi
echo "ACCEPT_GOLDEN_OK=`$ACCEPT_GOLDEN_OK"
"@
    }
    # O-17 layer-2 rwlock (2026-09-12, DESIGN §4.1): readonly task -> shared flock, writable -> exclusive.
    # Codex RwLock semantics: shared readers may be concurrent; any writer is exclusive.
    # Concurrency PLANNING stays with slot-gate (O-25) + O-18 cross-station discipline - the lock only
    # guarantees write-safety, it is decoupled from how many readers actually get dispatched.
    $flockShared = if ($readonly) { '1' } else { '0' }
    $body = @"
set -u
W="$W"
S="`$W/.agent-state.json"
mkdir -p "`$W" "`$W/out"
# O-09 isolate-xdg: 同站并行写任务时把 opencode 数据目录隔离到 per-task 工作区,
#   消除共享 opencode.db 上的写锁串行化 (SQLite 写锁序列化事实见 _bs1.py)。
#   仅隔离 data 目录: config(~/.config/opencode, 含 provider baseURL) 仍共享;
#   memory.db 独立 symlink 保留跨任务共享记忆; auth 不在 db 中(本地直连, 无外挂凭据)。
if [ "${isolateXdgOn}" = 1 ]; then
  mkdir -p "`$W/.xdg/opencode" "`$W/.xdg/cache"
  [ -e "`$HOME/.local/share/opencode/memory.db" ] && ln -sfn "`$HOME/.local/share/opencode/memory.db" "`$W/.xdg/opencode/memory.db"
  export XDG_DATA_HOME="`$W/.xdg"
  export XDG_CACHE_HOME="`$W/.xdg/cache"
  echo "XDG_ISOLATED data=`$W/.xdg"
fi
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
# O-17 layer-2 rwlock: shared iff readonly ($flockShared=1), exclusive otherwise (default).
LOCK_SHARED=$flockShared
LOCK_FLAGS=""
[ "`$LOCK_SHARED" = 1 ] && LOCK_FLAGS="-s"
if ! flock `$LOCK_FLAGS -n 9; then
  owner=`$(grep -o '"pid": *[0-9]*' "`$S" 2>/dev/null | grep -o '[0-9]*' | head -1)
  [ -z "`$owner" ] && owner=unknown
  echo "LOCK_HELD owner_pid=`$owner mode=`$( [ -n "`$LOCK_FLAGS" ] && echo shared || echo exclusive )"
  exit 3
fi
echo "LOCK_ACQUIRED pid=`$$ mode=`$( [ -n "`$LOCK_FLAGS" ] && echo shared || echo exclusive )"
Q0=`$(date +%s%N)
printf '{"state":"running","pid":%d,"ts_start":"%s","task_id":"%s","host":"agent-cli"}' "`$$" "`$(date -Is)" "$ts" > "`$S"
sleep 2   # artificial intake gap (BP-4: makes queue_s measurable on contention holder)
printf '%s' "$promptB64" | base64 -d > "`$W/out/.prompt.txt"
echo "PIPE_STDIN_OK"
cd "`$W" || exit 8    # cwd=workspace so agent reads AGENTS.md + project files (inv 4: stdin pipe, not cwd hijack)
R0=`$(date +%s%N)     # P2-1: run clock starts here (queue = lock+intake up to this point)
# O-24 P0-① (CLOSED-LOOP-ANALYSIS-2026-09-09): first run + resume-on-failure loop.
# Use opencode native --session/--continue to resume partial session (NOT restart/re-read),
# capped at 2 retries to bound wall time / avoid infinite loops. Resume prompt is base64
# literal (ASCII 纪律, same as acceptB64): "Continue the unfinished task from where it stopped.
# Re-read needed files, complete what was left, then verify per original criteria."
CONT_B64="Q29udGludWUgdGhlIHVuZmluaXNoZWQgdGFzayBmcm9tIHdoZXJlIGl0IHN0b3BwZWQuIFJlLXJlYWQgbmVlZGVkIGZpbGVzLCBjb21wbGV0ZSB3aGF0IHdhcyBsZWZ0LCB0aGVuIHZlcmlmeSBwZXIgb3JpZ2luYWwgY3JpdGVyaWEu"
# O-25 P0-② (2026-09-12): lightweight live-progress sampler. opencode run stdout is an
# appending file (`$W/out/.agent-output.txt); no token signal exists in headless run
# (CLOSED-LOOP 3.1), so we sample BYTE GROWTH + wall clock every 5s into `.progress`.
# Pure stdio-driven, zero external dependency. Sampler records its own clock base SP0
# (R1 is defined only AFTER the run completes, so it must not be referenced here).
SAMPLE=t
SB0=`$(( `$(date +%s%N) / 1000000 ))   # sampler clock base (ms), captured before first run
: > "`$W/out/.progress"
sample_progress() {
  while [ "`$SAMPLE" = t ]; do
    ob=`$(wc -c < "`$W/out/.agent-output.txt" 2>/dev/null)
    sw=`$(( `$(date +%s%N) / 1000000 - SB0 ))   # ms since sampler start
    st=`$(( sw / 1000 ))                        # s since sampler start
    bps=`$(( ob*1000/(sw+1) ))
    printf 't=%s bytes=%s bytes_s=%s\n' "`$st" "`$ob" "`$bps" >> "`$W/out/.progress"
    sleep 5
  done
}
sample_progress &
SPID=`$!
timeout $timeout opencode run -m "$id" < "`$W/out/.prompt.txt" > "`$W/out/.agent-output.txt" 2>&1
RC=`$?
# O-24 P0-① resume loop: on failure retry <=2 via `--continue` (opencode isolates sessions
# per workspace path -> in $W it resumes THIS run's session, verified 2026-09-09 on A station;
# no session-id parsing needed; base64 prompt keeps ASCII discipline)
CONT_ATTEMPT=0
while [ `$RC -ne 0 ] && [ `$CONT_ATTEMPT -lt 2 ]; do
  CONT_ATTEMPT=`$((CONT_ATTEMPT+1))
  echo "=== RESUME[`$CONT_ATTEMPT] prev_rc=`$RC ===" >> "`$W/out/.agent-output.txt"
  # O-24 P0-①: resume runs under its OWN timeout budget (continue-timeout-s), not the first budget
  echo "`$CONT_B64" | base64 -d \
    | timeout $continueTimeout opencode run --continue -m "$id" \
       >> "`$W/out/.agent-output.txt" 2>&1
  RC=`$?
  echo "=== RESUME[`$CONT_ATTEMPT] rc=`$RC ===" >> "`$W/out/.agent-output.txt"
done
R1=`$(date +%s%N)
# O-25 P0-② teardown: stop sampler, flush final write, capture aggregate throughput baseline.
# bytes_total = final output size; RUNS computed below also from R1. bytes_s_total is bytes/RUNS.
SAMPLE=f
kill `$SPID 2>/dev/null   # sampler subshell keeps a COPY of SAMPLE (fork); f won't reach it -> kill directly, else wait blocks forever
wait `$SPID 2>/dev/null
TOTAL_BYTES=`$(wc -c < "`$W/out/.agent-output.txt" 2>/dev/null)
TBPS=`$(( TOTAL_BYTES / ( (R1-R0)/1000000000 +1 ) ))
printf 't=end bytes=%s bytes_s=%s\n' "`$TOTAL_BYTES" "`$TBPS" >> "`$W/out/.progress"
# accept gate (A14): run executable criteria in workspace after agent completes
# golden gate (O-12, IMPLEMENTATION §3.3 M3): authoritative criteria run BEFORE self accept (inv 2/5)
# default line: ACCEPT_GOLDEN_OK always present in .meta (derived-requirement, IMPLEMENTATION §9.2)
GOLDEN_ACTIVE=0; ACCEPT_GOLDEN_OK=1
ACCEPT_B64="$acceptB64"
ACCEPT_OK=1
$goldenBlock
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
# G1 C4 guard (2026-09-12, G1-continue-spawn-decision.md): final state must NOT be a silent
# "done" when the task failed after resume exhausted. Pure RC-driven, no context signal needed.
ST=done; RN=0
[ "`$RC" -ne 0 ] && { ST=failed; RN=1; }
printf '{"state":"%s","pid":%d,"ts_start":"%s","task_id":"%s","host":"agent-cli"}' "`$ST" "`$$" "`$(date -Is)" "$ts" > "`$S"
QUEUE=`$(( (R0-Q0)/1000000000 ))    # P2-1: queue = lock wait + intake (sleep 2 => ~2s)
RUNS=`$(( (R1-R0)/1000000000 ))      # P2-1: run = agent generation wall time
echo "QUEUE_S=`$QUEUE"
echo "RUN_S=`$RUNS"
echo "TASK_RC=`$RC"
echo "ACCEPT_OK=`$ACCEPT_OK"
echo "OUT_BYTES=`$(wc -c < "`$W/out/.agent-output.txt" 2>/dev/null)"
printf 'TASK_ID=%s\nQUEUE_S=%s\nRUN_S=%s\nTASK_RC=%s\nACCEPT_OK=%s\nACCEPT_GOLDEN_OK=%s\nREVIEW_NEEDED=%s\n' "$ts" "`$QUEUE" "`$RUNS" "`$RC" "`$ACCEPT_OK" "`$ACCEPT_GOLDEN_OK" "`$RN" > "`$W/out/.meta"
# task succeeds only if agent ok AND (golden active -> golden ok) AND (no accept criteria OR accept all pass)
# O-12 P3-1: exit 9 reused for BOTH golden-fail and self-accept-fail (deliberate; run.json
# accept_golden.passed / accept.passed disambiguate at contract layer - IMPLEMENTATION §6.2)
if { [ "`$GOLDEN_ACTIVE" -eq 1 ] && [ "`$ACCEPT_GOLDEN_OK" -ne 1 ]; } \
 || { [ -n "`$ACCEPT_B64" ] && [ "`$ACCEPT_OK" -ne 1 ]; }; then exit 9; fi
exit `$RC
"@
    $code = Invoke-RemoteScript -HostName $hostName -ScriptBody $body -LocalName "agent-cli-task-$ts.sh"
    # DESIGN §9.5 exit-code dispatch: 124(timeout by `timeout`) -> 6; other remote run rc preserved as failure
    if ($code -eq 124) { $code = 6 }
    Write-Host "TASK remote excode=$code"

    # 6) collect: pull out/.meta + out/.agent-output.txt + out/.accept-output.txt, compute content_digest (M1)
    $outTxt = Join-Path $env:TEMP "agent-cli-out-$ts.txt"
    $accTxt = Join-Path $env:TEMP "agent-cli-accept-$ts.txt"
    $accGoldTxt = Join-Path $env:TEMP "agent-cli-accept-golden-$ts.txt"   # O-12 M4 P2-2: golden output pulled (contract observable)
    # ADR-0005 阶段0 (2026-09-16) 证据回收闭环 —— **5 个小文本件合批单连接回收**。
    #   为什么合批: 实测 Win32-OpenSSH 9.5p1 每次连接 14-17s, 且 ControlMaster 不可用
    #   (getsockname failed: Not a socket) ⇒ 逐个 scp 会把 collect 从 5 次连接抬到 8 次(+50s/run)。
    #   通道: 一条 ssh 跑 `tar|base64`, 文本通道沿用本文件既有手法($promptB64/$ACCEPT_B64),
    #   避免"二进制过 PowerShell 重定向被改写"。
    #   回收物: .meta(判据原始记录) / .prompt.txt(输入全文) / .progress(节拍原文)
    #           / .accept-cmds.txt / .golden-cmd.txt —— 这 5 件此前**从不回收**。
    $evDir = Join-Path $env:TEMP "agent-cli-ev-$ts"
    $metaTxt = Join-Path $evDir '.meta'
    $promptTxt = Join-Path $evDir '.prompt.txt'
    $progressTxt = Join-Path $evDir '.progress'
    $accCmdTxt = Join-Path $evDir '.accept-cmds.txt'
    $goldCmdTxt = Join-Path $evDir '.golden-cmd.txt'
    scp -q -o ConnectTimeout=10 "${hostName}:$W/out/.agent-output.txt" "$outTxt" 2>$null
    if ($accept.Count -gt 0) { scp -q -o ConnectTimeout=10 "${hostName}:$W/out/.accept-output.txt" "$accTxt" 2>$null }
    try {
        # 逐件 `marker + base64`（**刻意不用 tar**）: Windows 侧 GNU tar 对 `C:\...` 会按 host:path 去连
        #   "C" 主机(需 --force-local), 而 --force-local 又不认反斜杠路径 —— 两坑皆实测踩到。base64
        #   文本通道是本文件既有手法, 且全程不经过本机原生工具的参数解析。
        $evNames = @('.meta', '.prompt.txt', '.progress', '.accept-cmds.txt', '.golden-cmd.txt')
        $evCmd = (($evNames | ForEach-Object { "if [ -f $W/out/$_ ]; then echo FILE:$_ ; base64 -w0 $W/out/$_ ; echo ; fi" }) -join ' ; ')
        $evRaw = @(& ssh -o ConnectTimeout=10 $hostName $evCmd 2>$null)
        $evBuf = @{}; $evCur = ''
        foreach ($ln in $evRaw) {
            $t = "$ln".Trim()
            if ($t -like 'FILE:*') { $evCur = $t.Substring(5); $evBuf[$evCur] = '' }
            elseif ($evCur -and $t) { $evBuf[$evCur] += $t }
        }
        foreach ($n in $evNames) {
            if ($evBuf[$n]) {
                if (-not (Test-Path $evDir)) { New-Item -ItemType Directory -Path $evDir -Force | Out-Null }
                [IO.File]::WriteAllBytes((Join-Path $evDir $n), [Convert]::FromBase64String($evBuf[$n]))
            }
        }
    } catch { Write-Host "EVIDENCE_PULL_WARN: $($_.Exception.Message)" }
    # O-12 M4 P2-2: golden output pulled; TAMPERED path does NOT create the file -> scp NativeCommandError under
    # EAP=Stop would pollute exit (V0 real-run finding 2026-09-09) -> silent catch (missing file is expected there)
    if ($goldenActive) {
        try { scp -q -o ConnectTimeout=10 "${hostName}:$W/out/.accept-golden-output.txt" "$accGoldTxt" 2>$null }
        catch { $accGoldTxt = $null; Write-Host "(golden output absent - expected when TAMPERED/FAIL pre-write)" }
    }
    $queue_s = 0; $run_s = 0; $accept_ok = $null; $accept_golden_ok = $null
    $metaTaskId = ''
    if (Test-Path $metaTxt) {
        $m = Get-Content $metaTxt | Out-String
        if ($m -match 'TASK_ID=(\S+)') { $metaTaskId = $matches[1] }
        if ($m -match 'QUEUE_S=(\d+)') { $queue_s = [int]$matches[1] }
        if ($m -match 'RUN_S=(\d+)')   { $run_s = [int]$matches[1] }      # P2-1: run_s now measured (R1-R0)
        if ($m -match 'ACCEPT_OK=(\d+)') { $accept_ok = [int]$matches[1] }
        if ($m -match 'ACCEPT_GOLDEN_OK=(\d+)') { $accept_golden_ok = [int]$matches[1] }   # O-12 M4
    }
    # meta stale guard (O-22): .meta is run-end snapshot; if meta TASK_ID != this run's ts
    # it is a previous run leftover -> annotate (queue/run numbers untrusted), never claimed as live.
    # O-12 P2-1: stale ALSO nulls accept/golden verdicts (fail-safe: stale meta = verdict unknown =
    #            treated as fail, never trusts previous round's old values)
    if ($metaTaskId -and $metaTaskId -ne "$ts") {
        Write-Host "META_STALE: meta TASK_ID=$metaTaskId != this run ts=$ts (previous-run residual; queue/run omitted)"
        $queue_s = 0; $run_s = 0
        $accept_ok = $null; $accept_golden_ok = $null
    }
    $contentSha = ''
    if (Test-Path $outTxt) { $contentSha = Get-Sha256Text ([IO.File]::ReadAllText($outTxt)) }
    # O-25 P0-②: parse .progress tail ("t=end bytes=.. bytes_s=..") into per-run throughput baseline.
    $outputBytes = 0; $outputBps = 0
    if (Test-Path $progressTxt) {
        $lastLine = (Get-Content $progressTxt | Where-Object { $_ -match '^t=' } | Select-Object -Last 1)
        if ($lastLine -and $lastLine -match 'bytes=(\d+).*bytes_s=(\d+)') {
            $outputBytes = [int]$matches[1]; $outputBps = [int]$matches[2]
        }
    }
    # accept gate: remote exit 9 => agent ok but accept criteria failed (DESIGN §8 not exposed; local marker)
    $acceptPassed = $true
    if ($accept.Count -gt 0) { $acceptPassed = ($accept_ok -eq 1) }
    # O-12 P2-3: golden verdict EXPLICIT in status (no longer implicit via exit 9->1 only)
    $acceptGoldenPassed = $true
    if ($goldenActive) { $acceptGoldenPassed = ($accept_golden_ok -eq 1) }
    $codeReal = $code
    if ($code -eq 9) { $code = 1 }  # map accept-gate failure to generic failed for shell return

    # 8) ledger line FIRST (G13) -- fixed to sandbox-writable d:\RPC zone (O-04: projRoot not
    #     sandbox-safe). Run ledger before any agent-out write so a collect crash (startup-
    #     injected sandbox whitelist w/o D:\Paper\agent-out) never loses the run record.
    $ledger = 'd:\RPC\ops\station-bin\agent-runs.log'
    # 批B / 缺口6 (2026-09-18): 原为硬编码 `0,0` ⇒ 台账 queue_s/run_s **恒 0**, 与 run.json
    #   和 .meta 直接矛盾(已被 ADR-0007 阶段 0.5 夹具当场复现: 台账 `0,0` 而 .meta=QUEUE_S=2/RUN_S=19)。
    #   `$queue_s/$run_s` 在上方 meta 解析段(L1165-1183)已就绪; META_STALE 时二者已被主动归零,
    #   故与 run.json 的取值保持一致。**注**: claude 本地备路**不在本修范围** —— 其 .meta 本就写
    #   QUEUE_S=0(本地执行无远端队列), 台账/run.json 同为 0, 自洽。
    $line = "$ts,$proj,$id,$sens,$code,$queue_s,$run_s"
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
        status = if ($code -eq 0 -and $acceptPassed -and $acceptGoldenPassed) { 'completed' } elseif ($code -eq 6) { 'timeout' } else { 'failed' }
        content_digest = "sha256:$contentSha"
        usage = [ordered]@{ total_tokens = 0; tool_uses = 0 }
        queue_s = $queue_s
        run_s = $run_s
        slot = $slotGate
        output_bytes = $outputBytes
        output_bps = $outputBps
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
    # O-12 M4: accept_golden contract field (only when golden active; optional key, backward compatible)
    if ($goldenActive) {
        $run['accept_golden'] = [ordered]@{
            cmd = @($g.cmd)
            passed = ($accept_golden_ok -eq 1)
            source = 'golden'
            hidden_from_model = $true        # inv 1 extension: golden content never entered prompt
            # ADR-0005 D3 (2026-09-16): 当次注入的权威 checksum **只记于此** —— 此前只在主控变量+远端
            #   脚本字面量里, 事后无法回答"这次跑的是不是我期望的那份 golden"。不另立 .sha256 文件
            #   (避免第二定义点); 复验时用 `echo "<sha>  <base>" | sha256sum -c` 动态生成即可。
            sha256 = $goldenSha
            base = $goldenBase
        }
    }
    if ($collectOk) {
        try {
            $run | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $runDir '.agent-run.json') -Encoding utf8
            # move pulled output into runDir
            if (Test-Path $outTxt) { Move-Item $outTxt (Join-Path $runDir 'agent-output.txt') -Force }
            if (Test-Path $accTxt) { Move-Item $accTxt (Join-Path $runDir 'accept-output.txt') -Force }
            if (Test-Path $accGoldTxt) { Move-Item $accGoldTxt (Join-Path $runDir 'accept-golden-output.txt') -Force }   # O-12 M4 P2-2
            # ADR-0005 D1/D2/D4a (2026-09-16) 证据回收闭环: 判据记录 / 节拍原文 / 输入全文 / 命令清单
            #   一并归 runDir(**原文照收**, 不改写不规范); Move 即同时完成 TEMP 清理(D4a)。
            if (Test-Path $metaTxt) { Move-Item $metaTxt (Join-Path $runDir 'judgment-record.txt') -Force }
            if (Test-Path $progressTxt) { Move-Item $progressTxt (Join-Path $runDir 'progress-trace.txt') -Force }
            if (Test-Path $promptTxt) { Move-Item $promptTxt (Join-Path $runDir 'prompt.txt') -Force }
            if ($accCmdTxt -and (Test-Path $accCmdTxt)) { Move-Item $accCmdTxt (Join-Path $runDir 'accept-cmds.txt') -Force }
            if ($goldCmdTxt -and (Test-Path $goldCmdTxt)) { Move-Item $goldCmdTxt (Join-Path $runDir 'golden-cmd.txt') -Force }
            # D4a: 合批暂存目录(5 个小件已 Move 走)一并清掉, 不留 TEMP 残留
            if (Test-Path $evDir) { Remove-Item $evDir -Recurse -Force -ErrorAction SilentlyContinue }
            Remove-Item (Join-Path $projRoot 'agent-out\.agent-run.json') -ErrorAction SilentlyContinue
        }
        catch {
            $collectOk = $false
            Write-Host "COLLECT_FAIL: agent-out write failed: $($_.Exception.Message)"
        }
    }
    # ADR-0005 D4c (2026-09-16): collect 失败时**不得清理** —— 归档路径已失效, 此时清掉就是
    #   "既没归档又被删"。保留原地的证据并打印可寻路径(可 grep)。注: 本分支无法低成本端到端
    #   验证(派发前的 Assert-AgentOutWritable 探针会先拦住多数情形), 属代码走查, 见 ADR 后果段。
    if (-not $collectOk) {
        $left = @(@($outTxt, $metaTxt, $promptTxt, $accTxt, $accCmdTxt, $accGoldTxt, $goldCmdTxt, $progressTxt) |
                  Where-Object { $_ -and (Test-Path $_) })
        if ($left.Count -gt 0) { Write-Host "EVIDENCE_LEFT_IN_TEMP=$($left -join ';')" }
    }

    # (ledger already written above, before collect - G13/O-04)
    Write-Host "TASK_DONE dir=$runDir exit=$code prompt_sha256=sha256:$promptSha content_digest=sha256:$contentSha"
    Write-Host "ledger+=$line"
    return $code
}

# ---------------- O-26 Split-Dispatcher (2026-09-12) ----------------
# 单任务分解派发并行: 主卡 front-matter `decompose:` 有序列表 => N 子卡, 跨站各 1 派发并行.
# 复用(非新建)现有 task cmd 全链: 每个子卡 = 独立 `agent-cli task --RemoteHost <站>` 子进程.
# round-robin 把 N 分片轮询分配到 A/B/C(物理上界 3, O-18 铁律: cross-station each 1).
# readonly 轻量 Merge: 收集各子卡 terminal product(agent-output.txt/accept-output.txt) 按分片序拼装.
# 写型/强依赖任务不拆(O-26 判定: 只拆"可切分 readonly 大任务")。
function Invoke-SplitTask {
    param(
        [string]$proj,
        [string]$card,       # master card with decompose:
        [string]$model,      # model alias/full-id override
        [string]$sensitive,
        [string]$type,
        [string]$complexity,
        [string]$taskType,
        [switch]$SlotAllowBusy,
        [string]$cli,
        [string[]]$attach
    )
    if (-not $card) { Write-Host 'split requires --card <task.md>'; return 2 }
    if (-not (Test-Path $card)) { throw "card not found: $card" }
    $projRoot = $Script:PROJECTS[$proj]
    if (-not $projRoot -or -not (Test-Path $projRoot)) { throw "unknown/missing project: $proj (registered: $($Script:PROJECTS.Keys -join ','))" }
    if (-not (Assert-AgentOutWritable -projRoot $projRoot)) { Write-Host "ABORT: agent-out not writable (exit 12)"; return 12 }

    $fm = Get-FrontMatter $card
    $shards = @($fm['decompose'])
    if ($shards.Count -lt 2) {
        Write-Host "SPLIT_REQUIRES_2P: decompose must declare >=2 shards (use 'task' for single dispatch) [exit 2]"
        return 2
    }
    $m = if ($model) { $model } else { if ($fm['model']) { $fm['model'] } else { '' } }
    if (-not $m) { Write-Host 'REJECT missing-model (exit 2) - card has no model and no --model (inv 3)'; return 2 }
    $sens = if ($sensitive) { $sensitive } else { if ($fm['sensitivity']) { $fm['sensitivity'] } else { 'public' } }
    $readonly = [bool]$fm['readonly']
    if (-not $readonly) {
        Write-Host "SPLIT_ABORT: decompose only valid for readonly tasks (master card readonly=false) - writable merge not supported [exit 2]"
        return 2
    }
    $timeout = [int]$fm['timeout_s']
    $cid = (Split-Path $card -Leaf)
    $r = Resolve-Model $m
    if (-not $r) { Write-Host "REJECT unknown-model ($m) exit 2 - not in route table"; return 2 }
    $id = $r['id']
    if ($sens -eq 'local-only' -and $id -match '^opencode/') { Write-Host "REJECT local-only+remote ($id) exit 4 - no override channel"; return 4 }
    if ($id -notlike 'local/*') {
        Write-Host "SPLIT_WARN: model=$id is egress (opencode/*) - cross-station each-1 assumes per-station engines; egress has single route, fanout may not parallelize"
    }

    # round-robin target stations A/B/C (cross-station each 1, O-18 physical upper bound 3)
    $stationPool = @('A','B','C')
    if ($shards.Count -gt $stationPool.Count) {
        Write-Host "SPLIT_INFEASIBLE: $($shards.Count) shards > $($stationPool.Count) station pool (O-18 cross-station each-1, physical upper bound 3) [exit 18]"
        return 18
    }
    $t0 = [DateTime]::UtcNow
    $subDir = Join-Path $Script:TMP_ROOT ('split-' + $cid.Replace('.md',''))
    if (-not (Test-Path $subDir)) { New-Item -ItemType Directory -Path $subDir -Force | Out-Null }
    $pshell = if ($PSVersionTable.PSVersion.Major -ge 6) { (Get-Process -Id $PID).Path } else { 'powershell' }
    $selfPath = $MyInvocation.MyCommand.Path
    if (-not $selfPath) { $selfPath = $PSScriptRoot + '\agent-cli.ps1' }
    if (-not (Test-Path $selfPath)) { $selfPath = Join-Path $PSScriptRoot 'agent-cli.ps1' }
    # V2 子进程启动脚本必须是 PS5.1 可解析的 BOM 版: 仓库源 committed BOM-less, PS5.1 CP936 直接 -File
    #   会误解析其中 UTF-8 反引号/$( 序列. $MyInvocation 在函数体内无 Path(恒回退原始文件), 故此处
    #   显式生成 per-run BOM 副本供 children 使用 (与 O-11 L2 生产 launcher 的 temp-BOM 一致)。
    $ChildScript = Join-Path $subDir 'agent-cli-bom.ps1'
    $scriptSrc = if (Test-Path $selfPath) { [System.IO.File]::ReadAllText($selfPath, [System.Text.Encoding]::UTF8) } else { '' }
    [System.IO.File]::WriteAllText($ChildScript, $scriptSrc, (New-Object System.Text.UTF8Encoding $true))

    # serialize master common fields for prop to child card
    $common = @{
        model = $m; sensitivity = $sens; readonly = 'true'; timeout_s = $timeout;
        'continue-timeout-s' = $fm['continue-timeout-s']; cli = $fm['cli'];
        complexity = $fm['complexity']; 'task-type' = $fm['task-type']; 'isolate-xdg' = $fm['isolate-xdg']
    }
    $accept = @($fm['accept'])
    $golden = $fm['accept-golden']

    $procs = @(); $shardFiles = @()
    for ($i = 0; $i -lt $shards.Count; $i++) {
        $station = $stationPool[$i % $stationPool.Count]
        $shardBody = [string]$shards[$i]
        $subCard = Join-Path $subDir ("shard$($i+1).md")
        $lines = @()
        $lines += '---'
        $lines += "model: $m"
        if ($sens) { $lines += "sensitivity: $sens" }
        $lines += 'readonly: true'
        $lines += "timeout-s: $timeout"
        if ([int]$common['continue-timeout-s'] -gt 0) { $lines += "continue-timeout-s: $($common['continue-timeout-s'])" }
        if ($common['cli']) { $lines += "cli: $($common['cli'])" }
        if ($common['complexity']) { $lines += "complexity: $($common['complexity'])" }
        if ($common['task-type']) { $lines += "task-type: $($common['task-type'])" }
        if ([bool]$common['isolate-xdg']) { $lines += 'isolate-xdg: true' }
        if ($accept.Count -gt 0) {
            $lines += 'accept:'
            foreach ($a in $accept) { $lines += "  - $a" }
        }
        if ($golden -and $golden['source'] -and $golden['cmd']) {
            $lines += 'accept-golden:'
            $lines += "  source: $($golden['source'])"
            $lines += "  cmd: $($golden['cmd'])"
        }
        $lines += '---'
        $lines += ''
        $lines += "任务描述: (shard $($i+1)/$($shards.Count) of $cid) $shardBody"
        if ($fm['body']) {
            $lines += ''
            $lines += $fm['body']
        }
        $lines += ''
        $lines += "【分片约束】你是本大任务的第 $($i+1) 个分片（共 $($shards.Count) 个，并行在其他站执行）。只处理本分片描述的部分，不要越界处理其它分片内容；输出写到 out/ 下以你的分片标识命名的文件，避免与并行分片产物冲突。"
        [System.IO.File]::WriteAllLines($subCard, $lines, (New-Object System.Text.UTF8Encoding $true))
        $shardFiles += $subCard

        $hostArg = Get-TargetHost $station
        $logFile = Join-Path $subDir ("shard$($i+1).log")
        $childArgs = @('-NoProfile','-File',$ChildScript,'task',$proj,
            '--card',("`"$subCard`""),
            '--RemoteHost',("`"$hostArg`""),
            '--model',("`"$m`""),
            '--sensitivity',("`"$sens`""))
        foreach ($a in @($attach)) {
            if (Test-Path $a) { $childArgs += '--Attach', ("`"$a`"") }
        }
        $p = Start-Process -FilePath $pshell -ArgumentList $childArgs -RedirectStandardOutput $logFile -RedirectStandardError ($logFile + '.err') -WindowStyle Hidden -PassThru
        Write-Host "SPLIT_SHARD[$($i+1)] dispatched station=$station host=$hostArg pid=$($p.Id) card=$subCard"
        $procs += $p
    }

    # wait all sub-processes concurrently
    $wallT0 = [DateTime]::UtcNow
    foreach ($p in $procs) { $p.WaitForExit() | Out-Null }
    $wallMS = ([DateTime]::UtcNow - $wallT0).TotalMilliseconds

    # collect + merge results
    $mergedRoot = Join-Path $projRoot 'agent-out'
    $mergedDir = Join-Path $mergedRoot ('split-' + [DateTime]::UtcNow.ToString('yyyyMMddHHmmss'))
    New-Item -ItemType Directory -Path $mergedDir -Force | Out-Null
    $results = @()
    $allOk = $true
    for ($i = 0; $i -lt $procs.Count; $i++) {
        $p = $procs[$i]
        $out = if (Test-Path ($logFile = Join-Path $subDir ("shard$($i+1).log"))) { Get-Content $logFile -Raw } else { '' }
        # 权威退出码: 优先子进程 .ExitCode; Start-Process -PassThru 读 .ExitCode 偶发 $null (O-26,
        #   观察到两分片功能成功但 rc 空), 故 Refresh 后回退解析子任务日志序列化的远程退出码。
        $rc = $null
        try { $p.Refresh(); $rc = $p.ExitCode } catch { $rc = $null }
        if ($null -eq $rc) {
            if ($out -match 'TASK remote excode=(\d+)') { $rc = [int]$Matches[1] }
            elseif ($out -match 'TASK_DONE\s+.*exit=(\d+)') { $rc = [int]$Matches[1] }
            elseif ($out -match 'ACCEPT_OK=1') { $rc = 0 }
            else { $rc = 1 }
        }
        $ok = ($rc -eq 0)
        if (-not $ok) { $allOk = $false }
        $results += [pscustomobject]@{ idx = $i+1; station = $stationPool[$i % 3]; rc = $rc; ok = $ok; log = $out }
        Write-Host "SPLIT_SHARD_DONE[$($i+1)] rc=$rc ok=$ok"
    }

    # readonly merge: concatenate each shard terminal product into merged out.txt (by shard order)
    $mergedTxt = Join-Path $mergedDir 'merged-output.txt'
    $mergedBuf = [System.Collections.Generic.List[string]]::new()
    for ($i = 0; $i -lt $shards.Count; $i++) {
        $mergedBuf.Add("===== shard $($i+1) ($($stationPool[$i % 3])) rc=$($results[$i].rc) =====")
        $rb = $results[$i]
        $mergedBuf.Add($rb.log)
        $mergedBuf.Add('')
    }
    [System.IO.File]::WriteAllLines($mergedTxt, $mergedBuf, (New-Object System.Text.UTF8Encoding $true))

    Write-Host "SPLIT_DONE shards=$($shards.Count) all_ok=$allOk wall_ms=$([int]$wallMS) merged=$mergedTxt"
    if (-not $allOk) {
        Write-Host 'SPLIT_PARTIAL_FAIL - at least one shard exited non-zero; review per-shard logs'
        return 1
    }
    return 0
}

# ---------------- O-15 claude 备通道 (本地 headless 执行) ----------------
# 2026-09-12, G1 单机闭环备路: 当站内引擎/opencode 死锁时, 用控制台本地 claude CLI 兜底.
# 语义镜像远程 opencode 分支(fm->route->prompt->golden->accept->run/continue->状态->collect),
# 但取消 ssh/站内工作区/station-ready/slot-gate 依赖:  cwd=projRoot 直读项目源,
# 全部 scratch 写 $env:TEMP, 日志/run.json 契约与远程分支一致(DESIGN §6.2)。
# 调用形式: 首跑 `claude -p "" --model <id>`(stdin 喂 prompt), 失败续接 `claude --continue -p "" --model <id>`.
function Invoke-Task-Claude {
    param(
        [string]$proj,
        [string]$card,
        [string]$model,
        [string]$sensitive,
        [string[]]$attach,
        [string]$complexity,
        [string]$taskType
    )
    if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
        Write-Host "REJECT claude-not-installed (exit 13) - run: npm i -g @anthropic-ai/claude-code, then: claude auth login"
        return 13
    }
    if (-not $card) { Write-Host 'task requires --card <task.md>'; return 2 }
    if (-not (Test-Path $card)) { throw "card not found: $card" }
    $projRoot = $Script:PROJECTS[$proj]
    if (-not $projRoot -or -not (Test-Path $projRoot)) { throw "unknown/missing project: $proj (registered: $($Script:PROJECTS.Keys -join ','))" }
    if (-not $attach) { $attach = @() }

    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    $fm = Get-FrontMatter $card
    $m = if ($model) { $model } else { if ($fm['model']) { $fm['model'] } else { '' } }
    $sens = if ($sensitive) { $sensitive } else { if ($fm['sensitivity']) { $fm['sensitivity'] } else { 'public' } }
    if (-not $m) { Write-Host 'REJECT missing-model (exit 2) - card has no model and no --model (inv 3)'; return 2 }
    $readonly = [bool]$fm['readonly']
    $timeout = [int]$fm['timeout_s']
    $continueTimeout = [int]$fm['continue-timeout-s']
    if ($continueTimeout -le 0) { $continueTimeout = $timeout }
    Write-Host "BUDGET: first=$timeout resume=$continueTimeout (claude local backup)"


    $r = Resolve-Model $m
    if (-not $r) { Write-Host "REJECT unknown-model ($m) exit 2 - not in route table"; return 2 }
    $id = $r['id']
    if ($r['station']) { Write-Host "REJECT claude-station=$($r['station']) (exit 4) - claude channel must run local (station='')"; return 4 }

    $prof = Resolve-Profile -model $m -complexity $complexity -taskType $taskType
    Write-Host "PROFILE: profile=$($prof.profile) ctx=$($prof.context) max_out=$($prof.max_output) flavor=$($prof.flavor) (claude local)"

    $ts = [DateTime]::Now.ToString('yyyyMMddHHmmssffff')
    $scratch = Join-Path $env:TEMP "agent-cli-claude-$ts"
    New-Item -ItemType Directory -Path $scratch -Force | Out-Null
    $promptIn  = Join-Path $scratch '.claude-prompt.txt'
    $contIn    = Join-Path $scratch '.claude-continue.txt'
    $outTxt    = Join-Path $scratch 'agent-output.txt'
    $errTxt    = Join-Path $scratch 'claude-err.txt'
    $metaTxt   = Join-Path $scratch '.meta'
    $accTxt    = Join-Path $scratch 'accept-output.txt'
    $accGoldTxt= Join-Path $scratch 'accept-golden-output.txt'
    $goldenCmdTxt = Join-Path $scratch '.golden-cmd.txt'

    # ---- prompt assembly (镜像远程分支; claude 本地不需要 base64, 直写 UTF-8 文件喂 stdin) ----
    $promptFull = "[proj:$proj]`n$($fm['task'])"
    if ($fm['body']) { $promptFull += "`n`n" + $fm['body'] }
    if ($attach.Count -gt 0) {
        # claude cwd=projRoot -> attach 复制到 projRoot\.attach (与远程 workspace 语义一致)
        $attachLocal = Join-Path $projRoot '.attach'
        New-Item -ItemType Directory -Path $attachLocal -Force -EA SilentlyContinue | Out-Null
        $names = @()
        foreach ($a in $attach) {
            if (-not (Test-Path $a)) { Write-Host "attach missing (skip): $a"; continue }
            $name = Split-Path $a -Leaf
            try { Copy-Item $a (Join-Path $attachLocal $name) -Recurse -Force -EA Stop; $names += $name } catch { Write-Host "ATTACH_WARN: local copy failed: $a ($($_.Exception.Message))" }
        }
        if ($names.Count -gt 0) {
            $promptFull += "`n`n[attachments in workspace .attach/]: " + ($names -join ', ')
            $promptFull += "`n(attachments staged under .attach/ - read as needed)"
        }
    }
    if ($prof.thinking -eq 'ON' -and $prof.profile -in @('short','reason')) {
        $promptFull += "`n`n(concise reply expected: minimize thinking, give key steps + final result)"
    }
    if ($sens -eq 'sanitized') { Write-Host 'SANITIZED gate: scrubbing prompt (P1a)'; $promptFull = Invoke-Scrubber $promptFull }
    [IO.File]::WriteAllText($promptIn, $promptFull, $utf8NoBom)
    $promptSha = Get-Sha256Text $promptFull
    Write-Host "PROMPT_SHA=sha256:$promptSha scratch=$scratch"

    # ---- accept criteria ----
    $accept = @($fm['accept'] | Where-Object { $_.Trim() })
    # ---- golden (O-12 M2, 本地注入) ----
    $g = $fm['accept-golden']
    $goldenActive = [bool]($g.source -and $g.cmd)
    $goldenSha = ''; $goldenBase = ''
    if ($goldenActive) {
        try { $gSrc = Resolve-Path (Join-Path $Script:REPO_ROOT $g.source) -ErrorAction Stop } catch {
            Write-Host "GOLDEN_SOURCE_MISSING: $($g.source)"; return 2 }
        $goldenBase = [IO.Path]::GetFileName($gSrc)
        $goldenSha = (Get-FileHash -Algorithm SHA256 $gSrc).Hash.ToLower()
        $goldenLocal = Join-Path $scratch '.golden'
        New-Item -ItemType Directory -Path $goldenLocal -Force | Out-Null
        Copy-Item $gSrc (Join-Path $goldenLocal $goldenBase) -Force
        Write-Host "GOLDEN_ACTIVE base=$goldenBase sha=$goldenSha"
    }

    # ---- run + continue loop (stopwatch) ----
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $stateFile = Join-Path $scratch '.agent-state.json'
    [IO.File]::WriteAllText($stateFile, '{"state":"running","task_id":"' + $ts + '","host":"agent-cli-claude"}', $utf8NoBom)

    $rcov = Invoke-ClaudeFly -argStr ('-p "" --model "' + $id + '"') -stdin $promptIn -stdout $outTxt -stderr $errTxt -scratch $scratch -budgetS $timeout
    $rc = $rcov['code']; $rcMsg = $rcov['msg']; if ($rcMsg) { Write-Host "CLAUDE_RUN_WARN: $rcMsg" }
    Write-Host "claude first rc=$rc"

    # O-24 P0-① resume loop (本地等价): 失败 <=2 次续接, 每次独立预算 continueTimeout
    $contAttempt = 0
    $contB64 = "Q29udGludWUgdGhlIHVuZmluaXNoZWQgdGFzayBmcm9tIHdoZXJlIGl0IHN0b3BwZWQuIFJlLXJlYWQgbmVlZGVkIGZpbGVzLCBjb21wbGV0ZSB3aGF0IHdhcyBsZWZ0LCB0aGVuIHZlcmlmeSBwZXIgb3JpZ2luYWwgY3JpdGVyaWEu"
    while ($rc -ne 0 -and $contAttempt -lt 2) {
        $contAttempt++
        Add-Content $outTxt "`n=== RESUME[$contAttempt] prev_rc=$rc ==="
        [IO.File]::WriteAllText($contIn, ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($contB64))), $utf8NoBom)
        $rcov = Invoke-ClaudeFly -argStr ('--continue -p "" --model "' + $id + '"') -stdin $contIn -stdout $outTxt -stderr $errTxt -scratch $scratch -budgetS $continueTimeout
        $rc = $rcov['code']; $rcMsg = $rcov['msg']; if ($rcMsg) { Write-Host "CLAUDE_RESUME_WARN: $rcMsg" }
        Add-Content $outTxt "`n=== RESUME[$contAttempt] rc=$rc ==="
        Write-Host "claude resume[$contAttempt] rc=$rc"
    }
    $sw.Stop()
    $runS = [int]$sw.Elapsed.TotalSeconds
    if ($rc -eq 124) { $rc = 6 }   # timeout sentinel -> 6 (镜像远程 DESIGN §9.5)

    # ---- golden gate (先于 accept, inv 2/5) ----
    $acceptGoldenOk = 1
    if ($goldenActive) {
        $gCopy = Join-Path $scratch '.golden'
        $gFile = Join-Path $gCopy $goldenBase
        $h = (Get-FileHash -Algorithm SHA256 $gFile).Hash.ToLower()
        if ($h -ne $goldenSha) {
            Write-Host "GOLDEN_TAMPERED"; $acceptGoldenOk = 0
        } else {
            try { Push-Location $projRoot; try { Invoke-Expression $g.cmd } finally { Pop-Location } } catch { $acceptGoldenOk = 0 }
        }
        if ($acceptGoldenOk -eq 1) { Write-Host "ACCEPT_GOLDEN_OK=1" } else { Write-Host "ACCEPT_GOLDEN_OK=0" }
    }
    # ---- accept gate (A14) ----
    $acceptOk = 1
    if ($accept.Count -gt 0) {
        $i = 0
        foreach ($c in $accept) {
            $i++
            Add-Content $accTxt "=== ACCEPT_CMD[$i] >>> $c"
            $arc = 0
            try { Push-Location $projRoot; try { Invoke-Expression $c *> $null } finally { Pop-Location } } catch { $arc = 1 }
            if ($arc -ne 0) { $acceptOk = 0 }
            Add-Content $accTxt "--- ACCEPT_RC[$i]=$arc"
        }
        Write-Host "ACCEPT_OK=$acceptOk"
    }

    $state = if ($rc -eq 0 -and $acceptOk -eq 1 -and $acceptGoldenOk -eq 1) { 'done' } elseif ($rc -eq 6) { 'timeout' } else { 'failed' }
    [IO.File]::WriteAllText($stateFile, ('{"state":"' + $state + '","task_id":"' + $ts + '","host":"agent-cli-claude"}'), $utf8NoBom)
    $outputBytes = if (Test-Path $outTxt) { (Get-Item $outTxt).Length } else { 0 }
    $outputBps = if ($runS -gt 0) { [int]($outputBytes / $runS) } else { 0 }
    $meta = "TASK_ID=$ts`nQUEUE_S=0`nRUN_S=$runS`nTASK_RC=$rc`nACCEPT_OK=$acceptOk`nACCEPT_GOLDEN_OK=$acceptGoldenOk`nREVIEW_NEEDED=0"
    [IO.File]::WriteAllText($metaTxt, $meta, $utf8NoBom)

    # ---- collect (契约与远程一致: ledger 先写(沙箱可写区), 再 .agent-run.json + 产物) ----
    $code = $rc
    if ($code -eq 9) { $code = 1 }   # 兼容: 9 仅本地语义保留, 原生 rc 走下面映射
    $finalCode = if ($rc -eq 0 -and $acceptOk -eq 1 -and $acceptGoldenOk -eq 1) { 0 } elseif ($rc -eq 6) { 6 } else { 1 }
    $ledger = 'd:\RPC\ops\station-bin\agent-runs.log'
    $line = "$ts,$proj,$id,$sens,$finalCode,0,$runS"
    try { Add-Content -Path $ledger -Value $line -Encoding utf8 } catch { Write-Host "LEDGER_WARN: $($_.Exception.Message)" }

    $collectOk = $true; $runDir = ''
    try {
        $projOutRoot = Join-Path $projRoot 'agent-out'
        if (-not (Test-Path $projOutRoot)) { New-Item -ItemType Directory -Path $projOutRoot -Force | Out-Null }
        $runDir = Join-Path $projOutRoot $ts
        New-Item -ItemType Directory -Path $runDir -Force | Out-Null
    } catch { $collectOk = $false; $runDir = "$projRoot\agent-out\<$ts>"; Write-Host "COLLECT_FAIL: $($_.Exception.Message)" }

    $contentSha = if (Test-Path $outTxt) { Get-Sha256Text ([IO.File]::ReadAllText($outTxt)) } else { '' }
    $run = [ordered]@{
        proj = $proj; task_id = "task-$ts"; cli = 'claude'; model = $id; sensitivity = $sens
        readonly = $readonly; session_id = ''; exit_code = $finalCode
        status = if ($finalCode -eq 0) { 'completed' } elseif ($finalCode -eq 6) { 'timeout' } else { 'failed' }
        content_digest = "sha256:$contentSha"; usage = [ordered]@{ total_tokens = 0; tool_uses = 0 }
        queue_s = 0; run_s = $runS; slot = $null
        output_bytes = $outputBytes; output_bps = $outputBps
        timestamp_start = ''; timestamp_end = ''
        prompt_sha256 = "sha256:$promptSha"; attach = @($attach)
        profile = [ordered]@{ name=$prof.profile; context=$prof.context; max_output=$prof.max_output;
                              thinking=$prof.thinking; template=$prof.template; reasoning_format=$prof.reasoning_format; flavor=$prof.flavor }
        accept = [ordered]@{ cmd = @($accept); passed = ($acceptOk -eq 1) }
        collect = if ($collectOk) { 'ok' } else { 'failed' }
    }
    if ($goldenActive) {
        $run['accept_golden'] = [ordered]@{ cmd = @($g.cmd); passed = ($acceptGoldenOk -eq 1); source = 'golden'; hidden_from_model = $true
                                            sha256 = $goldenSha; base = $goldenBase }   # ADR-0005 D3: 当次权威 checksum 只记于此
    }
    if ($collectOk) {
        try {
            $run | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $runDir '.agent-run.json') -Encoding utf8
            if (Test-Path $outTxt) { Copy-Item $outTxt (Join-Path $runDir 'agent-output.txt') -Force }
            if (Test-Path $accTxt) { Copy-Item $accTxt (Join-Path $runDir 'accept-output.txt') -Force }
            if ($goldenActive -and (Test-Path $accGoldTxt)) { Copy-Item $accGoldTxt (Join-Path $runDir 'accept-golden-output.txt') -Force }
            # ADR-0005 D1 (2026-09-16) 证据回收闭环(本地备路): prompt 全文 + stderr 归 runDir ——
            #   本路的 prompt/stderr 是主控本地 scratch 里的件, 此前同样不归档(出 bug 时无从复核)。
            if (Test-Path $promptIn) { Copy-Item $promptIn (Join-Path $runDir 'prompt.txt') -Force }
            if (Test-Path $errTxt) { Copy-Item $errTxt (Join-Path $runDir 'stderr.txt') -Force }
        } catch { $collectOk = $false; Write-Host "COLLECT_FAIL: $($_.Exception.Message)" }
    }
    # ADR-0005 D4a/D4c (2026-09-16): **归档成功才清理** scratch(本路原为 Copy-Item, scratch 此前永不
    #   清理); 失败则保留并打印可寻路径 —— 不得"既没归档又被删"。
    if ($collectOk) { try { Remove-Item $scratch -Recurse -Force -ErrorAction SilentlyContinue } catch {} }
    else { Write-Host "EVIDENCE_LEFT_IN_SCRATCH=$scratch" }

    Write-Host "TASK_DONE dir=$runDir exit=$finalCode cli=claude prompt_sha256=sha256:$promptSha"
    Write-Host "ledger+=$line"
    return $finalCode
}

function Invoke-ClaudeFly {
    # 用 Start-Process 把 stdin 文件喂给 claude headless, stdout/stderr 落盘; 超时 kill 返回 124.
    param([string]$argStr, [string]$stdin, [string]$stdout, [string]$stderr, [string]$scratch, [int]$budgetS)
    if (-not (Test-Path $stdin)) { [IO.File]::WriteAllText($stdin, '', (New-Object System.Text.UTF8Encoding $false)) }
    try {
        $p = Start-Process -FilePath 'claude' -ArgumentList $argStr -NoNewWindow -PassThru `
            -RedirectStandardInput $stdin -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        if (-not $p.WaitForExit($budgetS * 1000)) { $p.Kill(); $p.WaitForExit(); return @{ code = 124; msg = "timeout after ${budgetS}s (killed)" } }
        return @{ code = $p.ExitCode; msg = '' }
    }
    catch { return @{ code = 7; msg = $_.Exception.Message } }
}

# ---------------- O-16 review ring (review --peer) ----------------
# Community-grounded LLM-as-judge (ref: .trae/documents/review-subcommand-impl-O16.md):
#  - five-source hetero judge (judge != producing model) to avoid self-certification
#  - deterministic layer (accept/golden, O-12) runs first; review = semantic/advisory layer (L2)
#  - judge call: G-Eval (CoT anchors then level), temperature=0 + seed recorded, pass/fail + 4-level
#  - candidate output treated as untrusted evidence; no verbosity/position reward
# Non-ASCII rubric text is OUTSIDE this file (PS5.1 parse-safety): review/*.txt / *.tmpl (UTF-8).

$Script:REVIEW_DIR = Join-Path $PSScriptRoot 'review'

# JUDGE_TABLE: review-model alias -> @{type; id; station; ctx; compliance}
#   type 'egress'      = opencode gateway on B (outbound, NOT for local-only)      [src ② ultra]
#   type 'local'       = console opencode CLI (npm i -g opencode-ai)               [src ⑤ main]
#   type 'http'        = OpenAI-compatible /v1 (commercial hook, ENV-injected)     [src ① commercial]
#   type 'http-local'  = OpenAI-compatible /v1 to station engine (load-gate)       [src ③ rpc / ④ m27]
$Script:JUDGE_TABLE = @{
    'ultra'       = @{ type='egress';      id='opencode/nemotron-3-ultra-free'; station='B'; ctx=1000000; compliance='public,sanitized'; maxtokens=2500 }
    'free-1m'     = @{ type='egress';      id='opencode/nemotron-3-ultra-free'; station='B'; ctx=1000000; compliance='public,sanitized'; maxtokens=2500 }
    'main'        = @{ type='local';       id='main-opencode-cli';               station='';  ctx=1000000; compliance='all'; maxtokens=4000 }
    'commercial'  = @{ type='http';        id='commercial';                      station='';  ctx=131072;  compliance='all'; maxtokens=2500 }
    'm27'         = @{ type='http-local';  id='local/m27-q4ks';                  station='C'; ctx=131072;  compliance='all'; maxtokens=8000 }
    'rpc-v4flash' = @{ type='http-local';  id='cluster-v4flash';                 station='C'; ctx=1000000; compliance='all'; maxtokens=8000 }
}

$Script:REVIEW_PARTIAL_OUT = ''   # (internal) carries error/marker across helpers on failure path

function Resolve-Judge {
    param([string]$alias)
    if (-not $alias) { return $null }
    return $Script:JUDGE_TABLE[$alias.Trim()]
}

function Read-ReviewResource([string]$name) {
    $p = Join-Path $Script:REVIEW_DIR $name
    if (-not (Test-Path $p)) { return 'RUBRIC_UNAVAILABLE: ' + $p }
    return [System.IO.File]::ReadAllText($p, [System.Text.UTF8Encoding]::new($false))
}

function Get-MainOpenCode {
    $c = Get-Command opencode -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    return $null
}

function Get-ReviewRunDir {
    param([string]$projRoot, [string]$runId)
    $root = Join-Path $projRoot 'agent-out'
    if (-not (Test-Path $root)) { return $null }
    if ($runId) {
        $d = Join-Path $root $runId
        if (-not (Test-Path $d)) { return $null }
        return $d
    }
    $newest = Get-ChildItem -Path $root -Directory | Where-Object {
        Test-Path (Join-Path $_.FullName '.agent-run.json') } |
        Sort-Object Name -Descending | Select-Object -First 1
    if (-not $newest) { return $null }
    return $newest.FullName
}

function Build-JudgePrompt {
    param($fm, [string]$product, [string]$runId, [string]$cardPath)
    $tmpl = Read-ReviewResource 'judge-prompt.tmpl'
    $rubric = Read-ReviewResource 'rubric-4level.txt'
    $taskLine = if ($fm['task']) { $fm['task'] } else { '' }
    $body = if ($fm['body']) { $fm['body'] } else { '' }
    $goldenMeta = 'none'
    $g = $fm['accept-golden']
    if ($g.source -and $g.cmd) { $goldenMeta = "source=" + (Split-Path $g.source -Leaf) + "; cmd=" + $g.cmd }
    $accept = @($fm['accept'])
    $acceptMeta = if ($accept.Count -gt 0 -and $accept[0]) { ($accept -join ' | ') } else { 'none' }
    $p = $tmpl
    $p = $p.Replace('{{RUBRIC}}', $rubric)
    $p = $p.Replace('{{TASK}}', $taskLine)
    $p = $p.Replace('{{CARD_BODY}}', $body)
    $p = $p.Replace('{{ACCEPT}}', $acceptMeta)
    $p = $p.Replace('{{GOLDEN}}', $goldenMeta)
    $p = $p.Replace('{{RUN_ID}}', $runId)
    $p = $p.Replace('{{PRODUCT}}', $product)
    return $p
}

function Invoke-RemoteCapture {
    # review-only ssh helper: like Invoke-RemoteScript but RETURNS remote stdout (string),
    # for capturing the judge's JSON reply (opencode-gateway source ②).
    param([string]$HostName, [string]$ScriptBody, [string]$LocalName)
    if (-not (Test-RemoteReach $HostName)) { throw "NETFAIL: remote unreachable: $HostName (ensure station online)" }
    if (-not $LocalName) { $LocalName = "agent-cli-cap-$([DateTime]::Now.ToString('HHmmss')).sh" }
    $localPath = Join-Path $Script:TMP_ROOT $LocalName
    if (-not (Test-Path $Script:TMP_ROOT)) { New-Item -ItemType Directory -Path $Script:TMP_ROOT -Force | Out-Null }
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($localPath, $ScriptBody, $utf8NoBom)
    scp -q -o ConnectTimeout=10 $localPath "${HostName}:/tmp/${LocalName}"
    if ($LASTEXITCODE -ne 0) { throw "NETFAIL: scp failed: $LocalName" }
    try { $sshOut = ssh -o ConnectTimeout=10 $HostName "bash /tmp/${LocalName}" 2>&1 }
    catch { $sshOut = @("$($_.Exception.Message)"); $LASTEXITCODE = 255 }
    Remove-Item $localPath -ErrorAction SilentlyContinue
    return (($sshOut | Out-String).Trim())
}

function Get-MarkerValue {
    param([string]$text, [string]$start, [string]$end)
    if (-not $text) { return $null }
    $i = $text.IndexOf($start); if ($i -lt 0) { return $null }
    $i += $start.Length
    $j = $text.IndexOf($end, $i); if ($j -lt 0) { return $null }
    return $text.Substring($i, $j - $i).Trim()
}

function ConvertFrom-JudgeOutput {
    # strict-ish JSON extraction: grab first '{' .. last '}', ConvertFrom-Json; else $null
    param([string]$raw)
    if (-not $raw) { return $null }
    $s = $raw.IndexOf('{'); if ($s -lt 0) { return $null }
    $e = $raw.LastIndexOf('}'); if ($e -le $s) { return $null }
    try { return ($raw.Substring($s, $e - $s + 1) | ConvertFrom-Json) }
    catch { return $null }
}

function Invoke-JudgeHttp {
    # OpenAI-compatible /v1 chat completion; temperature=0; returns visible message.content
    # 硬限速 (2026-09-16, ADR-0003): OpenRouter free 档 20 请求/分 (RPM) 且 429/失败仍计入配额。
    #  - RPM gate: 令牌桶=最小 3s 间隔 (20/分), 同进程多次调用限速 (仅本函数=review commercial 单一出口)
    #  - 429 退避: 指数 1s/2s 后重试, 第三次仍 429 才 throw
    param([string]$base, [string]$key, [string]$model, [string]$prompt, [int]$timeoutS, [int]$maxTokens = 2500)
    # RPM 20 gate (min 3s between judge http posts)
    if ($null -eq $Script:JudgeHttpLast) { $Script:JudgeHttpLast = [DateTime]::MinValue }
    if ($Script:JudgeHttpLast -ne [DateTime]::MinValue) {
        $elapsed = (Get-Date) - $Script:JudgeHttpLast
        $wait = 3.0 - $elapsed.TotalSeconds
        if ($wait -gt 0) { Start-Sleep -Milliseconds ([int]($wait * 1000)) }
    }
    $Script:JudgeHttpLast = Get-Date

    $headers = @{ 'Content-Type' = 'application/json' }
    if ($key) { $headers['Authorization'] = "Bearer $key" }
    $payload = @{
        model = $model
        messages = @(@{ role = 'user'; content = $prompt })
        temperature = 0.0
        max_tokens = $maxTokens
    } | ConvertTo-Json -Depth 6
    $attempt = 0
    while ($true) {
        $attempt++
        try {
            $r = Invoke-WebRequest -Uri "$base/chat/completions" -Method Post `
                -Headers $headers -Body $payload -TimeoutSec $timeoutS -UseBasicParsing
            $obj = $r.Content | ConvertFrom-Json
            return [string]$obj.choices[0].message.content
        }
        catch {
            $code = 0
            if ($_.Exception.Response) { try { $code = [int]$_.Exception.Response.StatusCode } catch { $code = 0 } }
            if ($code -eq 429 -and $attempt -lt 3) {
                Start-Sleep -Seconds ([math]::Pow(2, $attempt - 1))   # 1s, 2s exponential backoff
                Write-Host "RPM_429_BACKOFF: attempt $attempt (429 rate-limit, backing off)"
                continue
            }
            if ($_.Exception.Message -match 'timed out|could not be resolved|connect|inet') {
                throw "NETFAIL: judge http: $($_.Exception.Message)"
            }
            throw "JUDGE_HTTP_FAIL: $($_.Exception.Message)"
        }
    }
}

function Invoke-Judge {
    # dispatch judge call by JUDGE_TABLE type -> raw judge reply text.
    param([hashtable]$judge, [string]$prompt, [int]$timeoutS)
    switch ($judge['type']) {
        'egress' {
            $hostName = if ($judge['station']) { (Get-TargetHost $judge['station']) } else { (Get-TargetHost 'B') }
            $b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($prompt))
            $body = @"
set -eu
D=`$(mktemp -d)
printf '%s' "$b64" | base64 -d > "`$D/judge-in.txt"
cd "`$D"
timeout $timeoutS opencode run -m "$($judge['id'])" < "`$D/judge-in.txt" > "`$D/judge-out.txt" 2>&1
echo "REVIEW_B64_START"
base64 -w0 "`$D/judge-out.txt" 2>/dev/null || base64 "`$D/judge-out.txt"
echo ""
echo "REVIEW_B64_END"
"@
            $cap = Invoke-RemoteCapture -HostName $hostName -ScriptBody $body -LocalName "agent-cli-review.sh"
            $b = Get-MarkerValue -text $cap -start 'REVIEW_B64_START' -end 'REVIEW_B64_END'
            if ($b) {
                try { return ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b))) }
                catch { return $cap }
            }
            return $cap
        }
        'local' {
            $exe = Get-MainOpenCode
            if (-not $exe) {
                throw "JUDGE_UNREADY: source 5 (main opencode CLI) not installed - run: npm i -g opencode-ai, then: opencode auth login"
            }
            $m = $env:REVIEW_MAIN_MODEL
            if (-not $m) { $m = 'local/nemotron' }   # in-cluster model, NOT outbound gateway (local-only safe)
            $tf = Join-Path $env:TEMP "agent-cli-review-in-$(Get-Random).txt"
            [System.IO.File]::WriteAllText($tf, $prompt, (New-Object System.Text.UTF8Encoding $false))
            $errPath = $tf + '.err'
            try {
                $raw = (Get-Content -Raw -Path $tf | & $exe run -m $m 2>$errPath) | Out-String
            }
            catch { $raw = "JUDGE_LOCAL_FAIL: $($_.Exception.Message)" }
            Remove-Item $tf -ErrorAction SilentlyContinue; Remove-Item $errPath -ErrorAction SilentlyContinue
            return ($raw.Trim())
        }
        'http-local' {
            # source ③ rpc / ④ m27: OpenAI-compatible local engine. Guard sync via env.
            if (-not $env:REVIEW_HTTP_BASE) { throw "JUDGE_UNREADY: local judge '$($judge['id'])' requires REVIEW_HTTP_BASE (engine /v1) - load an engine + set env" }
            $mt = if ($judge['maxtokens']) { $judge['maxtokens'] } else { 8000 }
            return (Invoke-JudgeHttp -base $env:REVIEW_HTTP_BASE -key $env:REVIEW_HTTP_KEY `
                -model $($judge['id']) -prompt $prompt -timeoutS $timeoutS -maxTokens $mt)
        }
        'http' {
            if (-not $env:REVIEW_COMMERCIAL_BASE -or -not $env:REVIEW_COMMERCIAL_MODEL) {
                throw "JUDGE_UNREADY: commercial judge (source 1) not injected - set REVIEW_COMMERCIAL_BASE/KEY/MODEL (O-16 open item)"
            }
            $m = $env:REVIEW_COMMERCIAL_MODEL
            $mt = if ($judge['maxtokens']) { $judge['maxtokens'] } else { 2500 }
            return (Invoke-JudgeHttp -base $env:REVIEW_COMMERCIAL_BASE -key $env:REVIEW_COMMERCIAL_KEY `
                -model $m -prompt $prompt -timeoutS $timeoutS -maxTokens $mt)
        }
        default { throw "JUDGE_UNKNOWN_TYPE: $($judge['type'])" }
    }
}

function Invoke-Review {
    param(
        [string]$proj,
        [string]$card,
        [string]$runId,
        [string]$model,
        [switch]$overwrite,
        [string]$sensitive
    )
    if (-not $proj) { $proj = $env:AGENT_CLI_PROJ }
    if (-not $card) { Write-Host 'usage: agent-cli review <proj> --card <task.md> [--run-id <ts>] [--model <judge-alias>] [--overwrite]'; return 2 }
    if (-not (Test-Path $card)) { Write-Host "card not found: $card"; return 3 }
    $projRoot = $Script:PROJECTS[$proj]
    if (-not $projRoot -or -not (Test-Path $projRoot)) { Write-Host "unknown/missing project: $proj (registered: $($Script:PROJECTS.Keys -join ','))"; return 2 }

    $fm = Get-FrontMatter $card
    $sens = if ($sensitive) { $sensitive } else { if ($fm['sensitivity']) { $fm['sensitivity'] } else { 'public' } }

    # judge resolution: --model > front-matter review-model > default
    $judgeAlias = $null
    if ($model) { $judgeAlias = $model }
    elseif ($fm['review-model']) { $judgeAlias = [string]$fm['review-model'] }
    elseif ($sens -eq 'local-only') { $judgeAlias = 'main' }      # src ⑤ self-contained on console
    else { $judgeAlias = 'ultra' }                                 # src ② default machine baseline (proven)
    $judge = Resolve-Judge $judgeAlias
    if (-not $judge) { Write-Host "REJECT unknown-judge ($judgeAlias) exit 2 - judge aliases: ultra|free-1m|main|commercial|m27|rpc-v4flash"; return 2 }

    # sensitivity gate: local-only never to egress (opencode/* outbound)
    if ($sens -eq 'local-only' -and $judge['type'] -eq 'egress') {
        Write-Host "REJECT local-only+egress-judge ($($judge['id'])) exit 4 - no override channel"; return 4
    }

    $runDir = Get-ReviewRunDir -projRoot $projRoot -runId $runId
    if (-not $runDir) { Write-Host "REVIEW_RUNDIR_NOT_FOUND (proj=$proj run-id=$runId) exit 3"; return 3 }
    $runName = Split-Path $runDir -Leaf
    $product = Join-Path $runDir 'agent-output.txt'
    if (-not (Test-Path $product)) {
        $product = Join-Path $runDir 'accept-output.txt'
        if (-not (Test-Path $product)) { Write-Host "REVIEW_PRODUCT_MISSING: no agent-output.txt in $runDir (exit 3)"; return 3 }
    }

    # advisory (O-16): review.json is a parallel key; NEVER alters run.json/task accept semantics
    $reviewPath = Join-Path $runDir 'review.json'
    if ((Test-Path $reviewPath) -and -not $overwrite) {
        Write-Host "REVIEW_IDEMPOTENT: $reviewPath exists (use --overwrite to re-review)"
        Get-Content $reviewPath
        return 0
    }

    $productText = [System.IO.File]::ReadAllText($product, [System.Text.UTF8Encoding]::new($false))
    if ($productText.Length -gt 40000) {
        # G4: head+tail truncation - judge needs the conclusion/tail most (agent-tool-use-eval)
        $head = $productText.Substring(0, 20000)
        $tail = $productText.Substring($productText.Length - 20000)
        $productText = $head + '...[TRUNCATED mid (head+tail 40K total)]...' + $tail
    }
    $prompt = Build-JudgePrompt -fm $fm -product $productText -runId $runName -cardPath $card
    $rt = 600
    $rtFm = 0
    if ([int]::TryParse([string]$fm['review-timeout-s'], [ref]$rtFm) -and $rtFm -gt 0) { $rt = $rtFm }

    $t0 = [DateTime]::UtcNow
    $raw = $null; $callCode = 0; $callError = ''; $retries = 0
    # G3: retry<=2 (theneuralbase: timeout+health+fast-degrade on a retry budget)
    for ($try = 1; $try -le 3; $try++) {
        try { $raw = Invoke-Judge -judge $judge -prompt $prompt -timeoutS $rt; break }
        catch {
            $callError = $_.Exception.Message
            Write-Host "JUDGE_CALL_FAIL(attempt $try/3): $callError"
            if ($callError -like 'NETFAIL*') { $callCode = 5 }
            elseif ($callError -match 'timed out|timeout') { $callCode = 6 }
            else { $callCode = 7 }
            if ($try -lt 3) { Start-Sleep -Seconds 3; $retries++ }   # brief backoff then retry (or JSON retry below)
        }
    }
    # JSON retry: if reply came back but unparseable, one more attempt
    if ($callCode -eq 0 -and -not (ConvertFrom-JudgeOutput -raw $raw)) {
        Write-Host "JUDGE_JSON_RETRY: unparseable reply, retrying once"
        Start-Sleep -Seconds 3
        try { $raw = Invoke-Judge -judge $judge -prompt $prompt -timeoutS $rt; $retries++ }
        catch {
            $callError = $_.Exception.Message
            if ($callError -like 'NETFAIL*') { $callCode = 5 }
            elseif ($callError -match 'timed out|timeout') { $callCode = 6 }
            else { $callCode = 7 }
        }
    }
    $elapsed = [int]([DateTime]::UtcNow - $t0).TotalSeconds

    $judgeObj = ConvertFrom-JudgeOutput -raw $raw
    $seed = (Get-Random -Maximum 2147483647).ToString()   # recorded for reproducibility audit (arXiv 2606.26185)
    $promptHash = Get-Sha256Text $prompt

    if (-not $judgeObj) {
        # advisory: unparseable judge output still records a review_error, never blocks the task
        $review = [ordered]@{
            task = $fm['task']; run_id = $runName; card = $card
            output = [ordered]@{
                score = '不合格'; pass = $false
                evidence = @()
                flags_hit = @('JUDGE_OUTPUT_UNPARSEABLE')
                conclusion = ('judge reply unparseable / call failed' + $(if ($callError) { ': ' + $callError } else { '' }))
            }
            metadata = [ordered]@{
                judge_alias = $judgeAlias; judge_model = $judge['id']; temperature = 0; seed = $seed
                prompt_hash = "sha256:$promptHash"; elapsed_s = $elapsed; review_gate = 'false'
                call_code = $callCode; retries = $retries
            }
            review_error = $callError
        }
        $review | ConvertTo-Json -Depth 8 | Set-Content $reviewPath -Encoding utf8
        Write-Host "REVIEW_WRITTEN(advisory,error) $reviewPath"
        if ($callCode -ge 5) { return $callCode }   # NETFAIL(5)/timeout(6)/unparseable(7) surfaced, non-blocking
        return 0
    }

    $evidence = @()
    foreach ($ev in @($judgeObj.evidence)) {
        $evidence += [ordered]@{ anchor = [string]$ev.anchor; hit = [bool]$ev.hit; reasoning = [string]$ev.reasoning }
    }
    $flags = @()
    foreach ($f in @($judgeObj.flags_hit)) { $flags += [string]$f }

    $review = [ordered]@{
        task = $fm['task']; run_id = $runName; card = $card
        output = [ordered]@{
            score = [string]$judgeObj.score
            pass = [bool]$judgeObj.pass
            evidence = $evidence
            flags_hit = $flags
            conclusion = [string]$judgeObj.conclusion
        }
        metadata = [ordered]@{
            judge_alias = $judgeAlias; judge_model = $judge['id']; temperature = 0; seed = $seed
            prompt_hash = "sha256:$promptHash"; elapsed_s = $elapsed; review_gate = 'false'
            call_code = $callCode; retries = $retries
        }
    }
    $review | ConvertTo-Json -Depth 8 | Set-Content $reviewPath -Encoding utf8
    Write-Host "REVIEW_WRITTEN(advisory) $reviewPath"
    Write-Host ("REVIEW score=" + $review.output.score + " pass=" + $review.output.pass + " judge=" + $judge['id'] + " elapsed_s=" + $elapsed)
    return 0   # advisory: score=不合格 does NOT block; exit 0 signals commit (O-16 closed)
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
            $prof = Resolve-Profile -model $Model -complexity $Complexity -taskType $TaskType -EngineCtx $EngineCtxHint
        if ($EngineCtxHint -gt 0) { Write-Host "ENGINE_CTX_HINT=$EngineCtxHint (test clamp)" }
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
        $code = Invoke-Task -proj $Proj -card $Card -model $Model -sensitive $Sensitivity -type $Type -hostName $RemoteHost -attach $Attach -complexity $Complexity -taskType $TaskType -SlotAllowBusy:$SlotAllowBusy -cli $Cli
        exit $code
    }
    elseif ($Command -eq 'split') {
        # O-26 Split-Dispatcher. usage: agent-cli split <proj> --card <master.md> [--model <m>] (master card must declare decompose: ordered list)
        $code = Invoke-SplitTask -proj $Proj -card $Card -model $Model -sensitive $Sensitivity -type $Type -complexity $Complexity -taskType $TaskType -SlotAllowBusy:$SlotAllowBusy -cli $Cli -attach $Attach
        exit $code
    }
    elseif ($Command -eq 'review') {
        # O-16 review ring (advisory). usage: agent-cli review <proj> --card <task.md> [--run-id <ts>] [--model <judge-alias>] [--overwrite]
        $code = Invoke-Review -proj $Proj -card $Card -runId $RunId -model $Model -overwrite:$Overwrite -sensitive $Sensitivity
        exit $code
    }
    else {
        Write-Host "usage:"; Write-Host "  agent-cli workspace <proj> [--create|--sync|--archive] [--type python|cpp|doc|lean4]"
        Write-Host "  agent-cli task <proj> ...  (T3)"
        Write-Host "  agent-cli split <proj> --card <master.md> ...  (O-26 split dispatcher)"
        exit 2
    }
}
catch {
    Write-Host "ERROR: $($_.Exception.Message)"
    $ii = $_.InvocationInfo
    if ($ii) { Write-Host ("ERROR_AT: {0}:{1} - {2}" -f $ii.ScriptName, $ii.ScriptLineNumber, $ii.Line.Trim()) }
    # P2-2 (D6 audit): terminal network failure (reach/exec after retry) -> DESIGN §8 exit code 5
    if ($_.Exception.Message -like 'NETFAIL*') { exit 5 }
    exit 1
}