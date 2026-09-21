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
    #   id = 传给 `claude -p --model` 的型号。
    #   ⚠ **2026-09-21 修正（实测，阻断级）**: 原为 **Claude 原生 id**(claude-sonnet-4-5 / claude-opus-4-1) ——
    #     控制台 claude 已切 **OpenRouter** 后，这些 id 会被 OpenRouter **路由到真实 Anthropic 上游** ⇒
    #     **必 403 `This model is not available in your region.`**（实测三个 Claude 原生 id 全 403；
    #     `thinkingmachines/*:free` 与 `nvidia/*:free` 均 `OK`）。⇒ 免登录只解决认证、**不解决可用性**。
    #   现 id 取 `secrets/openrouter.conf` 的 **`harness_priority`** 前两档（该键是权威真值，三处消费方从此镜像；
    #     本表只镜像其前两项，**不新立模型清单**）。
    #   别名 `claude` / `claude-opus` **保留原名** —— 它们命名的是**备通道档位**(默认/高保真)，不是厂商。
    'claude'       = @{ id = 'thinkingmachines/inkling:free';          station = ''; cli = 'claude' }   # 默认备份型号
    'claude-opus'  = @{ id = 'nvidia/nemotron-3-ultra-550b-a55b:free'; station = ''; cli = 'claude' }   # 高保真备路
    # full id 直传 (与上面 local/* 同例): 使 `--model <openrouter-id>` 与 env `AGENT_FALLBACK_MODEL` 可解析
    'thinkingmachines/inkling:free'          = @{ id = 'thinkingmachines/inkling:free';          station = ''; cli = 'claude' }
    'nvidia/nemotron-3-ultra-550b-a55b:free' = @{ id = 'nvidia/nemotron-3-ultra-550b-a55b:free'; station = ''; cli = 'claude' }
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
        # ⚠ 归零纪律 (2026-09-18 实测事故): 本函数**只有 `$code` 能进管道** —— 任何 Write-Output /
        #   未被 `Out-Null` 吸收的 cmdlet 输出都会**混进返回值**, 使调用方拿到数组。实测: 环境层的
        #   `Remove-Item` 包装器在"回收站失败"时向管道吐 `$null` ⇒ 远端 rc 变成 `[null,0]` ⇒
        #   run.json `exit_code` 变数组 + `status` 误判 failed + 复验器 TypeError 崩掉(整条链判据消失)。
        #   故本函数内**一律 Write-Host**(通知) + 对可产出输出的 cmdlet 加 `| Out-Null`。
        Write-Host '[retry] remote reach failed, retry once'
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
    # `| Out-Null` 是**承重**的(2026-09-18 实测): 本函数**只有 `$code` 能进管道** —— 环境层的
    #   `Remove-Item` 包装器在"回收站失败"时会向管道吐 `$null`, 使返回值变数组、污染契约字段。
    Remove-Item $localPath -ErrorAction SilentlyContinue | Out-Null
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
    Copy-Item $local $tmp -Force | Out-Null   # ⚠ 归零纪律: 本函数返回哈希表, 非返回值输出必须吸收(见 Invoke-RemoteScript 注)
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
    Copy-Item 'D:\RPC\ops\station-bin\_slot_gate.sh' $tmp -Force | Out-Null   # ⚠ 归零纪律(见 Invoke-RemoteScript 注)
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
    # ADR-0007 阶段 1 (2026-09-18): evidence-manifest —— 卡声明"该产出哪些证据 + 怎么验"。
    #   形状借 in-toto Statement (subjects: name + path|collect + digest), **不自创语义**。
    #   本阶段只做"声明 + 落 run.json"(原文照收, 不规范化 —— ADR-0005 D2 纪律); 复验侧
    #   由复验器按 run.json 声明的 subjects 走 recipe v2 (recipe 已按条目分派, 无需重建链)。
    $h['evidence-manifest'] = @{ version = ''; subjects = @() }
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
        # ADR-0007 阶段 1: evidence-manifest 三级嵌套。**必须整体排在通用键正则之前** ——
        #   通用分支 `^\s*([A-Za-z_\-]+)\s*:` 允许前导空白, 且 `evidence-manifest` 含 `-` 亦在其
        #   字符类内 ⇒ 若落到通用分支, 会因 ContainsKey 命中而 `$h[$k] = $v`(**空串覆盖**整个
        #   哈希表)。与 accept-golden 嵌套键当年踩的是同一个坑(P2-1/IMPLEMENTATION §3.1)。
        elseif ($inFreq -and $l -match '^\s*evidence-manifest\s*:\s*$') { $curKey = 'evm' }
        elseif ($inFreq -and $curKey -eq 'evm' -and $l -match '^\s{2,}version\s*:\s*(.+)$') {
            $h['evidence-manifest']['version'] = $matches[1].Trim()
        }
        elseif ($inFreq -and $curKey -eq 'evm' -and $l -match '^\s{2,}subjects\s*:\s*$') { $curKey = 'evm-subjects' }
        elseif ($inFreq -and $curKey -eq 'evm-subjects' -and $l -match '^\s*-\s*name\s*:\s*(.+)$') {
            # ADR-0007 3-b-2 (2026-09-18): subject 增 `ephemeral`(设计性临时产物) —— 见代码内注释
            #   与 ADR-0007「3-b-2 本体」: 它把"产物在站上 /tmp、设计上就不进 runDir"与"件丢了"分开。
            $h['evidence-manifest']['subjects'] += @{ name = $matches[1].Trim(); path = ''; collect = ''; digest = ''; ephemeral = $false }
        }
        elseif ($inFreq -and $curKey -eq 'evm-subjects' -and $l -match '^\s{2,}(path|collect|digest|ephemeral)\s*:\s*(.+)$') {
            $subs = $h['evidence-manifest']['subjects']
            if ($subs.Count -gt 0) { $subs[$subs.Count - 1][$matches[1].ToLower()] = $matches[2].Trim() }
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
    # ADR-0007 3-b-2: subject 级 `ephemeral` 归一为布尔(与 readonly/isolate-xdg 同法, 不用字符串真值)
    foreach ($s in @($h['evidence-manifest']['subjects'])) { $s['ephemeral'] = ("$($s['ephemeral'])" -eq 'true') }
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

function Get-CardIdentity([string]$card) {
    # ADR-0007 前置(2026-09-18): **卡片身份** —— 卡是最大的注入物(决定 prompt / 验收 / golden / manifest 本身),
    #   而此前 run.json 与站上 .meta **都不记卡** ⇒ "那次跑的是**哪张卡的哪个版本**"不可判、复跑无法定版
    #   (实测: Cpp_Hub 的复现关键 `commit=b278151` **只存在于 prompt 文本**里)。
    #   摘要用**原始字节**(Get-FileHash), 便于任何工具独立复核(`Get-FileHash`/`sha256sum`/python 均可)。
    #   **单一实现点**: 主路与 claude 备路共用本函数(避免两处各算一份而漂移)。
    #   注: 只记 path+hash **不够** —— 卡**会改**(同日实测改了 4 张夹具卡) ⇒ 调用方另把卡字节归档为 runDir `card.md`。
    $o = [ordered]@{ path = [string]$card; sha256 = ''; bytes = 0; front_matter = $false }
    try {
        if (Test-Path -LiteralPath $card) {
            $full = (Resolve-Path -LiteralPath $card).Path
            $o.path = $full
            $o.bytes = [int](Get-Item -LiteralPath $full).Length
            $o.sha256 = "sha256:" + (Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLower()
            # "有没有 front-matter" **必须看原文围栏**, 不能用 `$fm.Keys.Count` ——
            #   ⚠ 本轮实测(2026-09-18): `Get-FrontMatter` 返回的是**预置 18 键的固定集**(缺的键=空值)
            #   ⇒ `Keys.Count` **恒为 18**、判据恒真, 护栏曾因此**放行**无 front-matter 卡(与"恒真判据"
            #   同族: 批A 的 `TASK_ID != label`、缺口4 的空件被丢)。按 §4 契约, front-matter 以 `---` 围栏给出。
            $txt = [IO.File]::ReadAllText($full)     # ReadAllText 自动去 BOM
            $o.front_matter = [bool]($txt -match '^\s*---\r?\n')
        }
    }
    catch { Write-Host "CARD_ID_WARN: $($_.Exception.Message)" }
    return $o
}

function Test-CardSafetyDeclared([string]$card, $cardId, [string]$sensitive) {
    # ADR-0007 前置(2026-09-18): **无 front-matter 卡的处置** —— 实测这类卡在 D6 路径下会**静默退化**:
    #   `readonly` 永远 false、`sensitivity` 默认 `public`、且无 accept-golden / 无 manifest。
    #   对 local-only 项目(Paper/Cpp_Hub/Auto_Prover 实测均以 local-only 为主)**这就是安全回退**。
    #   实测依据: Cpp_Hub 真正走 D6 的 4 次派发**全部** `sensitivity=local-only` 且带
    #   `accept_golden.cmd`, 即用的是**有 front-matter 的卡**; `F:\Cpp_Hub\dispatch\TASK_*.md` 那批
    #   无 front-matter 的手工任务书走的是 bespoke `dispatch/*.ps1`, 不是本路径。
    #   ⇒ 处置: **要求显式声明安全属性**(`-Sensitive`) 才放行; 否则拒绝(与 §4 统一卡契约一致)。
    if ($cardId -and $cardId.front_matter) { return $true }
    if ($sensitive) {
        Write-Host ("CARD_WARN: 卡无 front-matter ⇒ readonly=false / 无 accept-golden / 无 manifest" +
                    "(已按显式 -Sensitivity=$sensitive 放行)")
        return $true
    }
    Write-Host ("REJECT no-front-matter-card (exit 2) - 卡 $card 无 front-matter ⇒ 会静默退化为 " +
                "sensitivity=public + readonly=false(对 local-only 项目是安全回退)。" +
                "请补 front-matter, 或显式传 -Sensitivity <local-only|public>。")
    return $false
}

function Get-Sha256Lines([string[]]$lines) {
    # ADR-0007 缺口 5: 附件摘要 —— 对已(按相对路径)排序的 `relpath:sha256` 行做整体哈希。
    #   目录附件用**树摘要**; 单文件附件只有一行 ⇒ 摘要即该文件哈希的再哈希(仍可判断"是否被换")。
    #   **单一实现点在本文件**(console)。复验侧刻意**不重算** —— 重算会引入第二实现点, 而原始件
    #   (`attach-manifest.txt`)本身未被链钉住 ⇒ 重算也判不出篡改, 故不做(见 Invoke-Task 内注释)。
    $blob = ''
    if ($lines -and @($lines).Count -gt 0) { $blob = (@($lines) -join "`n") + "`n" }
    return (Get-Sha256Text $blob)
}

function Get-FrameworkSubjects($accept, [bool]$goldenActive) {
    # ADR-0007 路B (2026-09-18): **框架固定件基线** —— 每次派发都由本文件归档、与卡无关的件。
    # 为什么需要它(实测): 84 个 run 里只有 13 个带 evidence_manifest, 且**全部来自夹具卡**
    #   ⇒ 71 个(84%)真实工作 run 是 recipe v1 = **零声明** ⇒ 可重放性判据对真实语料整段不可判。
    #   而"每张卡都声明全部证据件"确实能修, 但会让 12 件框架件在每张卡里重复 —— 实测夹具卡
    #   `smoke-dispatch.md` 13 条声明里有 12 条是框架件, 只有 `station-tmp-log` 是卡特有。
    # ⇒ 把框架件提到**产出方**声明一次; 卡只声明**卡特有件**(站上临时采集物等)。
    # 单一真值(要紧, 别误读): 清单在**产出方**(此处), 复验侧 `cluster.py agent_audit` 的 undeclared
    #   判据仍**动态枚举 runDir**、只与 run.json 记录的声明比对 ⇒ **审计侧不新增硬编码清单** ——
    #   cluster.py 那条"不维护第二份框架件清单"的纪律**不破**: 清单全局只此一份, 且由产出方持有。
    # 反例警戒(实测, 否则基线自己变成噪声源): 基线只能列**该次派发必产出**的件 ——
    #   `accept-output/accept-golden-output` 在无 accept/golden 的 run 上实测**不存在**
    #   (run `202609181751581972` = 无 front-matter 卡, 该两件 0/1 存在) ⇒ 若无条件列入,
    #   每个这类 run 都会假报 `missing-artifact`, 把缺口判据变成天天红的东西。
    $list = @(
        @{ name = 'agent-output';    path = 'agent-output.txt' }
        @{ name = 'judgment-record'; path = 'judgment-record.txt' }
        @{ name = 'prompt';          path = 'prompt.txt' }
        @{ name = 'accept-cmds';     path = 'accept-cmds.txt' }
        @{ name = 'golden-cmd';      path = 'golden-cmd.txt' }
        @{ name = 'progress-trace';  path = 'progress-trace.txt' }
        @{ name = 'session-meta';    path = 'session-meta.txt' }
        @{ name = 'attach-manifest'; path = 'attach-manifest.txt' }
        @{ name = 'workspace-diff';  path = 'workspace-diff.txt' }
        @{ name = 'card';            path = 'card.md' }
    )
    $hasAccept = $false
    foreach ($a in @($accept)) { if ("$a".Trim()) { $hasAccept = $true } }
    if ($hasAccept) { $list += @{ name = 'accept-output'; path = 'accept-output.txt' } }
    if ($goldenActive) { $list += @{ name = 'accept-golden-output'; path = 'accept-golden-output.txt' } }
    return $list
}

function Get-ClaudeFrameworkSubjects($accept, [bool]$goldenActive) {
    # O-15/AUDIT (2026-09-21): **claude 备路按路的框架基线**。该路归档件集**与主路不同**:
    #   有 `stderr.txt`(本地 Start-Process 捕获), 而无主路的 `judgment-record`(本地无站上 .meta 回收)、
    #   无 `accept-cmds`/`prompt…`之外的 `progress-trace`/`session-meta`/`attach-manifest`/`workspace-diff`
    #   (那些是远端合成批产物, claude 本地路径不产)。
    #   ⇒ 复用主路基线会让每个 claude run 都假报 `missing-artifact`, 把判据变噪声 —— 审查总账早已提醒
    #   该路 run 恒 v1、"需按路各一份基线、单独立项"; 本次即把该条落地(recipe v2 的关键)。
    # 与主路 Get-FrameworkSubjects 同纪律: **只列该次派发必产出的件**(accept/golden 件按激活与否条件列)。
    $list = @(
        @{ name = 'agent-output';       path = 'agent-output.txt' }
        @{ name = 'prompt';             path = 'prompt.txt' }
        @{ name = 'stderr';             path = 'stderr.txt' }
        @{ name = 'card';               path = 'card.md' }
    )
    $hasAccept = $false
    foreach ($a in @($accept)) { if ("$a".Trim()) { $hasAccept = $true } }
    if ($hasAccept) { $list += @{ name = 'accept-output'; path = 'accept-output.txt' } }
    if ($goldenActive) { $list += @{ name = 'accept-golden-output'; path = 'accept-golden-output.txt' } }
    return $list
}

function Merge-EvidenceSubjects($cardSubjects, $accept, [bool]$goldenActive, $baselineFn = $null) {
    # baselineFn(2026-09-21): 可选**按路基线函数**(脚本块, 签名 (accept, goldenActive))。
    #   缺省 = 主路 Get-FrameworkSubjects; claude 备路传入 Get-ClaudeFrameworkSubjects(归档件集不同)。
    # 合并: **基线在前、卡声明在后**, 同 path(collect 型按同 name)**以先到者为准**。
    #   去重的理由: 夹具卡里还留着历史遗留的框架件声明(逐卡手写时代的产物), 不去重就会双份
    #   ⇒ 链上同一件出现两次、audit 的 covered 集合语义含糊。去重后**改卡与否都不影响结论**。
    #   归一: 每项补齐 name/path/collect/digest/ephemeral 五键(与 run.json 发射形状一致),
    #   免得下游按 subject 取键时遇到缺键(PS 哈希表缺键取值为 $null, 会静默传播)。
    $seen = New-Object 'System.Collections.Generic.HashSet[string]'
    $out = New-Object System.Collections.ArrayList
    $baselineItems = if ($baselineFn) { @(& $baselineFn $accept $goldenActive) } else { @(Get-FrameworkSubjects $accept $goldenActive) }
    foreach ($s in @($baselineItems) + @($cardSubjects)) {
        if ($null -eq $s) { continue }
        $p = ([string]$s['path']).Trim()
        $n = ([string]$s['name']).Trim()
        if (-not $n) { continue }
        $key = if ($p) { "path:$p" } else { "name:$n" }
        if (-not $seen.Add($key)) { continue }
        $d = ([string]$s['digest']).Trim()
        if (-not $d) { $d = 'sha256' }
        $out.Add([ordered]@{ name = $n; path = $p; collect = ([string]$s['collect']).Trim()
                             digest = $d; ephemeral = [bool]$s['ephemeral'] }) | Out-Null
    }
    # 返回**扁平**数组。⚠ 别在这里用 `Write-Output -NoEnumerate`(首版就这么写的, 实测踩到):
    #   函数输出集合**本身**就会把结果包成数组 ⇒ 再加 `-NoEnumerate` 得到的是
    #   "1 元素数组、其唯一元素才是真数组" ⇒ 调用方 `.Count` **恒为 1**; 更阴的是
    #   `$_.path` 在数组上走**成员枚举**, 于是 `Where-Object { $_.path -eq 'x' }` 会对整个
    #   内层数组判真 ⇒ 断言**假 PASS**(与"恒真判据"同族: 判了, 但判的不是你以为的东西)。
    #   单元素退化问题由调用方 `@(...)` 兜底, 不在被调方解决。
    return $out.ToArray()
}

function Get-NumOr([string]$s, [double]$def) {
    # ADR-0007 缺口 8: 站上遥测文件的**容错取数** —— 只在形如数字时才转, 否则取默认值。
    #   为什么不用 `[int]$x`: 字段缺失/被截断时会**抛异常**, 而遥测不该影响任务结论(只该显式降级)。
    if ("$s" -match '^-?\d+(\.\d+)?$') { return [double]$s }
    return $def
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

function Test-FallbackEligible([int]$code) {
    # O-15/AUDIT (2026-09-21): 主路(opencode)失败中**哪一类才值得自动切 claude 备路**。
    # 只认 rc=6(= 远程 `timeout` sentinel→124→6, 及本地 resume 耗尽后的超时) —— 这正是 claude
    # 备路注释里"站内引擎/opencode 死锁时本地兜底"的场景(如 #17307 超时死锁: 引擎在预算内产不出
    # 终态输出 ⇒ 死锁, 重温和继续都无效 ⇒ 换本地 claude 重跑是合理的)。
    # **刻意不认** 1/5/10/12/24/9(任务真实结果: accept 失败/net 挂/station 未就绪/sandbox 不可写/
    # slot/engine 拒绝) —— 换 claude 重跑会**掩盖真实错误**(用户纪律: 自动 fallback 默认关、显式
    # 开启; 即便开启也只对"引擎死锁"这一类兜底, 不对"任务失败"兜底)。
    return ($code -eq 6)
}

function Get-SensitivityBackendReject {
    # 硬闸**判据唯一实现点** (P0 止血 + P1 免费档闸, 2026-09-21)。返回 '' = 放行;
    # 否则返回**拒绝原因 token**(供调用点打印, 使证据行能指名"哪条规则拦的")。
    # 为什么判据是"**后端属性**"而不是"型号前缀": 同一个型号在不同通道下属性不同 ——
    #   `gpt-oss-20b` 走站上本地引擎(不出网/不训练), 而 `claude` 走**主控本地** spawn =
    #   云端 OpenRouter 的 **`:free`** 档(**出网 + 可能训练/公开输入**)。旧判据把"出网"等同于
    #   `^opencode/` ⇒ 整个 claude 备路失守(见 OPEN-ISSUES 的安全策略洞)。
    # 两条规则:
    #   local-only × 会出网        ⇒ `local-only+egress`
    #     (DESIGN §358 路由不变式: prompt 字节永不离开"主控站→站内本地模型"路径)
    #   sanitized  × 可能训练/发布 ⇒ `sanitized+trains`
    #     (P1 实测: 免费档端点**全部**训练/不可 ZDR ⇒ **脱敏 ≠ 同意进公开数据集**)
    #   public 恒放行。
    # ⚠ `$backendTrains` 现由调用点以 `$id -match ':free'` 派生 —— 这是**代理判据**:
    #   公开 API 实测**不暴露**端点级 `data_policy`(见 P1 调研), 故暂不能直读。
    #   P2 应把它换成"按后端属性登记/实测"的查表, 与本函数的另外两个参数同源。
    # 刻意做成**纯函数**(不碰站、不碰文件系统) ⇒ 夹具可按名提取离线单测(与 Test-FallbackEligible 同族)。
    param(
        [string]$sensitivity,
        [bool]$backendEgress,
        [bool]$backendTrains = $false
    )
    if ($sensitivity -eq 'local-only' -and $backendEgress) { return 'local-only+egress' }
    if ($sensitivity -eq 'sanitized' -and $backendTrains) { return 'sanitized+trains' }
    return ''
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
        [switch]$SlotAllowBusy,  # O-25 P1: allow dispatch even if target engine /slots busy
        [switch]$AutoFallback    # O-15/AUDIT: opencode 引擎死锁/超时(rc=6)时自动转本地 claude 备路 (默认关, 显式开启)
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
    # ADR-0007 前置: 卡身份(路径/原始字节摘要/字节数/是否含 front-matter) —— 复跑定版的唯一依据。
    #   形状守卫: 环境层会往管道吐 $null 使返回值变数组(缺口 5 实测教训) ⇒ 退化时取首元素。
    $cardId = Get-CardIdentity $card
    if ($cardId -is [array]) { $cardId = $cardId[0] }
    $m = if ($model) { $model } else { if ($fm['model']) { $fm['model'] } else { '' } }
    $sens = if ($sensitive) { $sensitive } else { if ($fm['sensitivity']) { $fm['sensitivity'] } else { 'public' } }
    # O-15/AUDIT (2026-09-21 实弹实测修正): 自动 fallback 的**入参必须在此处快照** ——
    #   主路 collect 段有 `$m = Get-Content $metaTxt | Out-String`(见本函数内"遥测解析"上方)
    #   会把 `$m` **改写成 .meta 全文**。真实站点实弹(2026-09-21, B 站 rc=6)正是因此把 meta 文本
    #   当模型名传给 claude 备路 ⇒ `REJECT unknown-model (TASK_ID=202609211645528026 QUEUE_S=2 …)`。
    #   与缺口 5「返回值被非返回值输出污染」同族: **变量被复用即等于被污染**。
    #   ⚠ 注入式夹具(_probe_fallback.ps1)抓不到它 —— stub 不产 .meta 文件 ⇒ `Test-Path $metaTxt`
    #   为假 ⇒ `$m` 未被改写; **只有真实站才暴露**(这是真实实弹不可被注入式替代的实例)。
    $taskModel = $m
    if (-not $m) { Write-Host 'REJECT missing-model (exit 2) - card has no model and no --model (inv 3)'; return 2 }
    # ADR-0007 前置: 无 front-matter 卡**必须显式声明安全属性**才放行(否则静默退化为 public+可写)。
    #   形状守卫同 $cardId(环境层可能吐 $null 使返回值变数组)。
    $cardOk = Test-CardSafetyDeclared $card $cardId $sensitive
    if ($cardOk -is [array]) { $cardOk = @($cardOk | Where-Object { $null -ne $_ })[0] }
    if (-not $cardOk) { return 2 }
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
    # ADR-0007 缺口 5: 附件身份 —— 除名字外还记**源路径**与**种类**(file/dir), 供 run.json 落
    #   每件摘要(kind 在该 .ps1 内是已知的; 从远端清单反推种类会多一个推断点)。
    $attachSrc = @{}; $attachKind = @{}
    # remote .attach/ reset —— **无条件**(含"本次无附件"的情形)! 2026-09-18 实测发现: 原实现只在
    #   `$attach.Count -gt 0` 时才重建 ⇒ **无附件的派发会留着上一次的附件**(agent 可 `ls`/读到, 且
    #   `attach-manifest` 会把外来文件算进本次 run —— 实测两次无附件 run 都报 `ATTACH_MANIFEST_LINES=3`)。
    #   代价: 无附件派发多一次 ssh(reset) —— 正确性优先, 且该 reset 必须在 scp 之前。
    $body = @"
set -eu
W="$Script:WORKSPACE_ROOT/$proj"
# ADR-0007 缺口 5 实测发现(2026-09-18): `.attach/` **从不回收** —— 站上实测残留着 09-05/09-12 五次派发的
#   附件(fileA.md/fileB.txt/inbox.txt/_o11_src.txt/_o26_src.txt + docs/emptydir/), 与 IMPLEMENTATION
#   "`.attach/` 生命周期=单次 task(结束即回收)" 的声明**正相反**。后果有二: ①**污染本次附件摘要**
#   (上一轮的旧文件混进本次 digest ⇒ 摘要看着正常但内容不是本次注入的); ②agent 可能读到残留件。
#   ⇒ 改为**派发前清空**(等价于所声明的语义, 且不必依赖"collect 回收"那一步)。
rm -rf "`$W/.attach" && mkdir -p "`$W/.attach"
"@
    Invoke-RemoteScript -HostName $hostName -ScriptBody $body -LocalName "agent-cli-attach-reset.sh"
    if ($attach.Count -gt 0) {
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
            $attachKind[$name] = if ($isDir) { 'dir' } else { 'file' }
            $srcAbs = $a
            try { $srcAbs = (Resolve-Path -LiteralPath $a -EA Stop).Path } catch { }
            $attachSrc[$name] = $srcAbs
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
# ADR-0007 缺口 5: 附件"注入字节"的**原始证据** —— 站上逐文件 `sha256sum`(`<hex>  <relpath>`)。
#   必须在 agent 运行**之前**采样(故在 marker 之前): 记的是"注入的字节", 而非 agent 可能改写后的。
#   与主控侧对**源文件**的独立哈希互为**跨信任域交叉验证**(e2e 据此自证"记录属实")。
: > "`$W/out/.attach-manifest.txt"
if [ -d "`$W/.attach" ]; then
  ( cd "`$W/.attach" && find . -type f -printf '%P\n' 2>/dev/null | LC_ALL=C sort | xargs -r sha256sum ) > "`$W/out/.attach-manifest.txt" 2>/dev/null || true
fi
echo "ATTACH_MANIFEST_LINES=`$(wc -l < "`$W/out/.attach-manifest.txt" 2>/dev/null || echo 0)"
# ADR-0007 缺口 4: agent 运行**窗口起点**标记 —— 必须在 agent 运行前创建, 否则窗口错位、
#   diff 恒空。后续用 `find -newer` 列出本窗口内被改动的文件(与 git 无关: 实测工作区非
#   git 仓库, git diff 会静默返回空 = 假的"未越界")。
: > "`$W/.run-marker"
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
# ADR-0007 缺口 4: readonly 卡的"未越界"载体 —— **与 git 无关**(实测工作区非 git 仓库,
#   `git diff` 在非仓库上静默返回空 = 假的"未越界") ⇒ marker + `find -newer`, 只列 agent
#   运行窗口内被改动的**工作区相对路径**(`-printf '%P'`)。
#   **放在 golden/accept 门之前** —— 否则会被 golden 自身产出的构建物(如 cpphub beta 编译)污染。
#   排除框架自身产物(漏项 ⇒ diff 恒非空 ⇒ 判据退化为噪声)。
( cd "`$W" && find . -newer .run-marker -type f -printf '%P\n' 2>/dev/null \
    | grep -v -E '^(out|\.golden|\.attach|agent-out|\.agentsync|\.git)/' \
    | grep -v -E '^\.(agent-lock|agent-state\.json|run-marker)$' \
    | grep -v -E '^agent-runs\.log$' ) > "`$W/out/.workspace-diff.txt" 2>/dev/null || true
echo "WORKSPACE_DIFF_LINES=`$(wc -l < "`$W/out/.workspace-diff.txt" 2>/dev/null || echo 0)"
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

    # ADR-0007 缺口 8 (2026-09-18): 站在 **opencode 会话库**取本 run 遥测(session_id / tokens / tool_uses /
    #   时间戳)。**不猜数**: headless run 的 stdout 不吐 usage(见 cluster.py reqlog 注) ⇒ 唯一可自证的
    #   口径是**会话库自己对这次会话的聚合**。只有"取到/取不到"两态: 取不到时下方落
    #   `usage.source=unavailable` 并告警 —— **绝不把 0 当作"用了 0 token"**。
    #   纪律: 遥测**不参与成败判定**(失败只告警, 不改 rc), 与 .meta/.progress 同属"站上原件"。
    try {
        $localSm = 'D:\RPC\ops\station-bin\_oc_session_meta.sh'
        $tmpSm = Join-Path $Script:TMP_ROOT '_oc_session_meta.sh'
        New-Item -ItemType Directory -Path $Script:TMP_ROOT -Force | Out-Null
        Copy-Item $localSm $tmpSm -Force | Out-Null
        scp -q -o ConnectTimeout=10 $tmpSm "${hostName}:/tmp/_oc_session_meta.sh" 2>$null
        if ($LASTEXITCODE -ne 0) { Write-Host "SESSION_META_WARN: scp helper failed" }
        else {
            # 窗口起点 = 本 run 的 ts − 5min 裕度 ⇒ 只取"本次新建"的会话(同工作区的旧会话被 since 排除)
            #   ⚠ **PS5.1 地雷(实测 2026-09-18)**: `[DateTime]::UnixEpoch` 在 .NET Framework 4.8 **不存在**
            #   (静默为 `''` ⇒ 相减时抛 `找不到 op_Subtraction 的重载`)。改用 `[DateTimeOffset]`(4.6+ 有
            #   `ToUnixTimeMilliseconds`) —— 该路径虽有 try/catch 兜底(首次实测正是它把 NA 路径跑通了),
            #   但**不能靠兜底当正常路径**。
            $runStart = [DateTimeOffset]::ParseExact($ts.Substring(0, 14), 'yyyyMMddHHmmss', [Globalization.CultureInfo]::InvariantCulture)
            $sinceMs = $runStart.ToUnixTimeMilliseconds() - 300000
            & ssh -o ConnectTimeout=10 $hostName "bash /tmp/_oc_session_meta.sh '$W' $sinceMs '$W/out/.session-meta.txt'" 2>$null | Out-Null
        }
    }
    catch { Write-Host "SESSION_META_WARN: $($_.Exception.Message)" }

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
        # ADR-0007 缺口 4: 增 `.workspace-diff.txt`(readonly 卡的"未越界"载体) 入合批通道。
        #   远端已由 `find -newer .run-marker` 产出(见 body 内的采集段); 缺件时下面 else 分支跳过。
        # ADR-0007 缺口 5: 增 `.attach-manifest.txt`(附件**注入字节**的逐文件哈希; 无附件时为**空件**,
        #   仍会发 marker ⇒ 靠下面的**存在性**判定归档, 不靠真值判定)。
        # ADR-0007 缺口 8: 增 `.session-meta.txt`(站上会话库遥测; helper **一定**产出该件, 含"取不到"情形)。
        $evNames = @('.meta', '.prompt.txt', '.progress', '.accept-cmds.txt', '.golden-cmd.txt', '.workspace-diff.txt', '.attach-manifest.txt', '.session-meta.txt')
        $evCmd = (($evNames | ForEach-Object { "if [ -f $W/out/$_ ]; then echo FILE:$_ ; base64 -w0 $W/out/$_ ; echo ; fi" }) -join ' ; ')
        $evRaw = @(& ssh -o ConnectTimeout=10 $hostName $evCmd 2>$null)
        $evBuf = @{}; $evCur = ''
        foreach ($ln in $evRaw) {
            $t = "$ln".Trim()
            if ($t -like 'FILE:*') { $evCur = $t.Substring(5); $evBuf[$evCur] = '' }
            elseif ($evCur -and $t) { $evBuf[$evCur] += $t }
        }
        foreach ($n in $evNames) {
            # ⚠ 缺口 4 实测踩到: 原为 `if ($evBuf[$n])` = **真值**判定 ⇒ **空文件被静默丢弃**
            #   (base64 -w0 对空文件输出空串 ⇒ 值为 '' ⇒ falsy)。而 `workspace-diff` 的"零改动"
            #   恰恰是**空文件** = readonly 卡最正常的结果 ⇒ 该例必被丢。改为**存在性**判定:
            #   marker 行 `FILE:<name>` 只要文件存在就发, 故 ContainsKey 即"远端确有该件"。
            if ($evBuf.ContainsKey($n)) {
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

    # ADR-0007 缺口 5 (2026-09-18): **附件身份** —— 把"当次注入的字节"钉进 run.json。
    #   真值来源 = 站上产的 `out/.attach-manifest.txt`(逐文件 `<sha>  <relpath>`; 在 agent 运行**前**采样,
    #   故记的是"注入的字节"而非 agent 可能改写后的)。摘要由**本侧**计算(单一实现点 Get-Sha256Lines);
    #   复验侧刻意**不重算** —— 重算会引入第二实现点, 而原始件 `attach-manifest.txt` 本身**未被链钉住**
    #   ⇒ 重算也判不出篡改。落进 run.json 后**自动被链钉住**(`.agent-run.json` 在件集内) ⇒
    #   事后想换附件摘要必撞 `digest_mismatch`; 这正是"补哈希"的收益所在。
    #   ⚠ **形状变更**: **有附件的新 run** ⇒ `attach` = 对象数组; 老 run 与 claude 备路仍为**名字数组**。
    $attachEntries = @()
    if ($attachNames.Count -gt 0) {
        $amPath = Join-Path $evDir '.attach-manifest.txt'
        $amMissing = -not (Test-Path $amPath)
        if ($amMissing) {
            Write-Host "ATTACH_MANIFEST_ABSENT: 站上无附件清单(回收缺口) ⇒ 本次附件摘要**不可判**, 记空串(不静默当作通过)"
        }
        $amLines = @()
        if (-not $amMissing) { $amLines = @(Get-Content $amPath -Encoding UTF8 | Where-Object { "$_".Trim() }) }
        $grp = @{}
        foreach ($ln in $amLines) {
            # GNU sha256sum 输出 `<hex>  <relpath>`(文件名含换行/反斜杠时行首带 `\`, 见其 --help)
            if ("$ln" -match '^\\?([0-9a-fA-F]{64})\s+\*?(.+)$') {
                $h = $matches[1].ToLower(); $rel = "$($matches[2])".Trim()
                $top = ($rel -split '/')[0]                 # 首段路径 = 附件名(`docs/inner.txt` -> `docs`)
                if (-not $grp.ContainsKey($top)) { $grp[$top] = New-Object System.Collections.ArrayList }
                [void]$grp[$top].Add("$rel`:$h")
            }
        }
        $orphan = @($grp.Keys | Where-Object { $attachNames -notcontains $_ })
        if ($orphan.Count -gt 0) { Write-Host "ATTACH_MANIFEST_UNEXPECTED: 站上 .attach/ 含未发送条目: $($orphan -join ', ')" }
        foreach ($n in $attachNames) {
            # 组缺失**不报错**: 空目录附件本就没有行 ⇒ files=0 且摘要 = 空行集摘要(确定性)。
            $ls = @(); if ($grp.ContainsKey($n)) { $ls = @($grp[$n]) }
            $sha = ''
            if (-not $amMissing) { $sha = Get-Sha256Lines $ls }
            $attachEntries += [ordered]@{
                name   = $n
                src    = "$($attachSrc[$n])"
                kind   = if ($attachKind[$n]) { $attachKind[$n] } else { 'file' }
                files  = $ls.Count
                sha256 = $sha
            }
        }
    }

    # ── ADR-0007 缺口 8 (2026-09-18): **遥测解析**(站上会话库原件 ⇒ run.json) ──
    #   三态而非二态: `SESSION_FOUND=1` ⇒ 落真实值(source=opencode-session-db);
    #   否则 ⇒ `usage.source='unavailable'` + 告警(**不把 0 当成"用了 0 token"**, 与缺口 4/5 的
    #   "不适用/不可判/可判分开报"同一纪律)。文件缺失同样落入 unavailable 分支(件存在性由合批通道保证)。
    $sessKv = @{}
    $smPath = Join-Path $evDir '.session-meta.txt'
    if (Test-Path $smPath) {
        foreach ($ln in @(Get-Content $smPath -Encoding UTF8)) {
            if ("$ln" -match '^([A-Z_]+)=(.*)$') { $sessKv[$matches[1]] = $matches[2] }
        }
    }
    $sessionId = ''; $tsStart = ''; $tsEnd = ''
    $usageObj = [ordered]@{ source = 'unavailable'; total_tokens = 0; tool_uses = 0 }
    if ($sessKv['SESSION_FOUND'] -eq '1') {
        $sessionId = "$($sessKv['SESSION_ID'])"
        $srcTag = 'opencode-session-db'
        if ("$($sessKv['SESSION_AMBIGUOUS'])" -eq '1') {
            # 站上判据: 仅当**另一会话与本会话时间重叠**才算歧义(与钟无关) ⇒ 背靠背派发不会误报;
            #   真并发(同工作区 readonly 共享锁)才会命中 ⇒ 标注而非假装确定。
            $srcTag = "opencode-session-db(时间重叠 $($sessKv['SESSION_CANDIDATES']) 个会话: 归属不确定)"
            Write-Host "SESSION_META_AMBIGUOUS: 该工作区有与本 run **时间重叠**的会话 ⇒ 遥测归属不确定(已标注)"
        }
        $usageObj = [ordered]@{
            source = $srcTag
            total_tokens = [int](Get-NumOr $sessKv['TOKENS_TOTAL'] 0)
            tool_uses = [int](Get-NumOr $sessKv['TOOL_USES'] 0)
            input = [int](Get-NumOr $sessKv['TOKENS_INPUT'] 0)
            output = [int](Get-NumOr $sessKv['TOKENS_OUTPUT'] 0)
            reasoning = [int](Get-NumOr $sessKv['TOKENS_REASONING'] 0)
            cache_read = [int](Get-NumOr $sessKv['TOKENS_CACHE_READ'] 0)
            cache_write = [int](Get-NumOr $sessKv['TOKENS_CACHE_WRITE'] 0)
            cost = Get-NumOr $sessKv['SESSION_COST'] 0
        }
        foreach ($pair in @(@('TS_CREATED_MS', 'start'), @('TS_UPDATED_MS', 'end'))) {
            if ("$($sessKv[$pair[0]])" -match '^\d+$') {
                # ⚠ 同上: 用 [DateTimeOffset](PS5.1 无 [DateTime]::UnixEpoch)
                $iso = [DateTimeOffset]::FromUnixTimeMilliseconds([int64]$sessKv[$pair[0]]).ToLocalTime().ToString('o')
                if ($pair[1] -eq 'start') { $tsStart = $iso } else { $tsEnd = $iso }
            }
        }
    }
    else {
        Write-Host "SESSION_META_UNAVAILABLE: 站上未取到本 run 会话遥测(helper/会话库/窗口不匹配) ⇒ usage.source=unavailable(**不猜数**)"
    }

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
    try { Add-Content -Path $ledger -Value $line -Encoding utf8 | Out-Null; $ledgerOk = $true }
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
        # ADR-0007 前置: 归档**卡字节**(卡会改 ⇒ 只记 hash 无法复跑; 与 prompt.txt 同族但含 front-matter)
        if ($cardId.path -and (Test-Path -LiteralPath $cardId.path)) {
            Copy-Item -LiteralPath $cardId.path -Destination (Join-Path $runDir 'card.md') -Force | Out-Null
        }
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
        # ADR-0007 缺口 8: 会话 id / 用量 / 时间戳 —— 源为**站上 opencode 会话库**(见上方遥测解析段);
        #   取不到时 session_id='' 且 usage.source='unavailable'(**不猜数**)。
        session_id = $sessionId
        exit_code = $code
        status = if ($code -eq 0 -and $acceptPassed -and $acceptGoldenPassed) { 'completed' } elseif ($code -eq 6) { 'timeout' } else { 'failed' }
        content_digest = "sha256:$contentSha"
        # 缺口 8: 形状升级 —— 除 total_tokens/tool_uses 外含 breakdown + `source`(血缘: 会话库 vs 取不到)
        usage = $usageObj
        queue_s = $queue_s
        run_s = $run_s
        slot = $slotGate
        output_bytes = $outputBytes
        output_bps = $outputBps
        timestamp_start = $tsStart
        timestamp_end = $tsEnd
        prompt_sha256 = "sha256:$promptSha"
        # ADR-0007 前置(2026-09-18): 卡身份 —— 与 prompt_sha256 同族, 但**卡决定 prompt 自己**
        #   (最大的注入物); 落进 run.json ⇒ 自动被证据链钉住。原始件另存 runDir `card.md`。
        card = $cardId
        # ADR-0007 缺口 5: 有附件时为**对象数组** {name,src,kind,files,sha256}(摘要源于站上清单);
        #   无附件时 `[]`(与老形状一致)。消费方需按"对象数组 / 名字数组"两种形状处理(见 ARCHITECTURE §6)。
        attach = $attachEntries
        profile = [ordered]@{ name=$prof.profile; context=$prof.context; max_output=$prof.max_output;
                              thinking=$prof.thinking; template=$prof.template; reasoning_format=$prof.reasoning_format;
                              flavor=$prof.flavor; source=$prof.source }
        accept = [ordered]@{ cmd = $accept; passed = $acceptPassed }
        collect = if ($collectOk) { 'ok' } else { 'failed' }
    }
    # ADR-0007 阶段 1 + 路B(2026-09-18): evidence-manifest 落 run.json。
    #   阶段1 时是"卡声明什么就照收什么"; 路B 改为**框架基线合并** ——
    #   框架固定件由 `Get-FrameworkSubjects`(产出方)声明一次, 卡只声明卡特有件。
    #   ⇒ **卡不写 manifest 也能得到 v2**(逐件被链钉住), 这正是把 71 个 v1 真实 run 拉进
    #     可重放性判定面的手段; 写了 manifest 的卡与基线**去重合并**(见 Merge-EvidenceSubjects)。
    #   ⚠ 后果(刻意接受): 新 run **一律带此键** ⇒ 一律走 recipe v2。老 run.json 形状不受影响
    #     (历史条目自带 recipe, 按条目分派 ⇒ 无需重建链, 见 cluster.py 的 recipe 分派注释)。
    #   仍保留"非空才落"的守卫: 若某天基线被清空, 宁可退回 v1 也不要落一个空 subjects
    #     (空 subjects + recipe v2 = `_run_digest` 返回 None ⇒ verify 报 manifest_missing FAIL)。
    $evm = $fm['evidence-manifest']
    $mergedSubjects = @(Merge-EvidenceSubjects @($evm['subjects']) $accept $goldenActive)
    if ($mergedSubjects.Count -gt 0) {
        $mergedVer = "$($evm['version'])".Trim()
        if (-not $mergedVer) { $mergedVer = '1' }   # 卡未写 version ⇒ 取 1(基线 = 框架件, 与阶段1 同代)
        $run['evidence_manifest'] = [ordered]@{ version = $mergedVer; subjects = $mergedSubjects }
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
            # ⚠ **归零纪律**(2026-09-18 实测事故, 见 ADR-0007 缺口 5): 本函数**只有 `$code` 该进管道**,
            #   任何未被 `Out-Null` 吸收的 cmdlet 输出都会**混进返回值**(调用方 `$code = Invoke-Task …`)。
            #   实测: 环境层 `Remove-Item` 包装器在"回收站失败"时往管道吐了 `$null` ⇒ 契约字段畸形。
            #   ⇒ 本段所有 `Move-Item`/`Copy-Item`/`Remove-Item` 一律 `| Out-Null`(它们本就无返回值语义)。
            $run | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $runDir '.agent-run.json') -Encoding utf8
            # move pulled output into runDir
            if (Test-Path $outTxt) { Move-Item $outTxt (Join-Path $runDir 'agent-output.txt') -Force | Out-Null }
            if (Test-Path $accTxt) { Move-Item $accTxt (Join-Path $runDir 'accept-output.txt') -Force | Out-Null }
            if (Test-Path $accGoldTxt) { Move-Item $accGoldTxt (Join-Path $runDir 'accept-golden-output.txt') -Force | Out-Null }   # O-12 M4 P2-2
            # ADR-0005 D1/D2/D4a (2026-09-16) 证据回收闭环: 判据记录 / 节拍原文 / 输入全文 / 命令清单
            #   一并归 runDir(**原文照收**, 不改写不规范); Move 即同时完成 TEMP 清理(D4a)。
            if (Test-Path $metaTxt) { Move-Item $metaTxt (Join-Path $runDir 'judgment-record.txt') -Force | Out-Null }
            if (Test-Path $progressTxt) { Move-Item $progressTxt (Join-Path $runDir 'progress-trace.txt') -Force | Out-Null }
            if (Test-Path $promptTxt) { Move-Item $promptTxt (Join-Path $runDir 'prompt.txt') -Force | Out-Null }
            if ($accCmdTxt -and (Test-Path $accCmdTxt)) { Move-Item $accCmdTxt (Join-Path $runDir 'accept-cmds.txt') -Force | Out-Null }
            if ($goldCmdTxt -and (Test-Path $goldCmdTxt)) { Move-Item $goldCmdTxt (Join-Path $runDir 'golden-cmd.txt') -Force | Out-Null }
            # ADR-0007 缺口 4: readonly 卡的"未越界"载体 —— console 侧**有则收**(缺件时不动)。
            # ⚠ 原注释写"非 readonly 卡本就没有", **与实测不符**(2026-09-18 复核): 以缺口 4 落地界
            #   `202609181119254134` 划开, 界之后 **13/13** 个 run 全带该件(含 10 个非 readonly,
            #   零例外) ⇒ 站上是**无条件产出**的。不要用它反推 readonly(判 readonly 看 run.json)。
            $wdSrc = Join-Path $evDir '.workspace-diff.txt'
            if (Test-Path $wdSrc) { Move-Item $wdSrc (Join-Path $runDir 'workspace-diff.txt') -Force | Out-Null }
            # ADR-0007 缺口 5: 附件清单原件(逐文件 `<sha>  <relpath>`) —— **下钻**用(是"哪份附件里的哪个
            #   文件"的原始证据)。⚠ 本件**未被链钉住**(被钉住的是 run.json 里的摘要), 故"本件 ↔ 摘要"
            #   是否自洽**只能在人/工具侧核对**, 该上限已记入 ADR-0007/ARCHITECTURE。
            $amSrc = Join-Path $evDir '.attach-manifest.txt'
            if (Test-Path $amSrc) { Move-Item $amSrc (Join-Path $runDir 'attach-manifest.txt') -Force | Out-Null }
            # ADR-0007 缺口 8: 遥测原件(会话库取数结果) —— 与 run.json 的解析值**同源**, 便于人/工具复核
            #   (解析若被误改, 可直接比对原件; 摘要未被链钉住 ⇒ 该上限同 attach-manifest, 见 ADR-0007)
            $smSrc = Join-Path $evDir '.session-meta.txt'
            if (Test-Path $smSrc) { Move-Item $smSrc (Join-Path $runDir 'session-meta.txt') -Force | Out-Null }
            # D4a: 合批暂存目录(5 个小件已 Move 走)一并清掉, 不留 TEMP 残留
            if (Test-Path $evDir) { Remove-Item $evDir -Recurse -Force -ErrorAction SilentlyContinue | Out-Null }
            Remove-Item (Join-Path $projRoot 'agent-out\.agent-run.json') -ErrorAction SilentlyContinue | Out-Null
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
    # O-15/AUDIT (2026-09-21): **自动 fallback** —— 仅当显式 -AutoFallback 且主路确走 opencode
    #   ($effectiveCli='opencode')且 rc 命中"引擎死锁/超时"(rc=6)时才转本地 claude 备路。
    #   ⚠ 归零纪律: 本函数只有返回值进管道(见 L1634 注); Invoke-Task-Claude 自身已 Out-Null 收敛,
    #   `return (…)` 只会吐其 int 返回值, 不会污染调用方 `$code = Invoke-Task …`。
    #   ⚠ 刻意只对 `effectiveCli -eq 'opencode'`: 若卡/路由本就选 claude(或其自身超时)则**不二次转发**。
    if ($AutoFallback -and $effectiveCli -eq 'opencode' -and (Test-FallbackEligible $code)) {
        # ⚠ P0 止血 + P1 免费档闸 (2026-09-21, 安全策略洞 · 出网路径②): 主路 model 是**站上本地引擎**
        #   时(如 gpt-oss-20b 走 B 站), 上方的闸**不会**拦(它只拦 local-only + `^opencode/`)
        #   ⇒ 死锁 rc=6 一路走到这里 ⇒ `Invoke-Task-Claude` ⇒ **云端 `:free` 档**
        #   ⇒ `local-only` 的 prompt **实际出网**; `sanitized` 的 prompt **进可能训练/公开的 provider**。
        #   必须**在调用点也判**(Invoke-Task-Claude 内那道守"直接入口", 这道守"自动兜底入口" ——
        #   只判一处会漏)。语义: **拒绝兜底**(fail-closed, 不是"兜底到别处")。返回 4 而**不是**原 rc
        #   —— 刻意让"策略拒绝"盖过"超时": 否则调用方只看到 timeout 会**换站重试**(每次重试都要再跑
        #   一遍本地引擎), 策略事件被埋掉。原 rc 已在上一行 `TASK_DONE … exit=$code` 打印, 未丢失。
        # ⚠ **必须用 `$taskModel`(顶部快照), 不能用 `$m`** —— 后者已被 collect 段改写为 .meta 全文
        #   (2026-09-21 真实站实弹实测踩到, 见上方快照处注释)。
        # 备路模型: claude 备路只接受 `station=''` 的**本地** claude 路由(Invoke-Task-Claude 内护栏),
        #   而主路模型(如 gpt-oss-20b)解析出 station='B' ⇒ **不能透传**, 否则被
        #   `REJECT claude-station=B (exit 4)` 拦掉 ⇒ 备路等于白切。故按语义切到 claude 备路型号:
        #   默认 ROUTE_TABLE 的 `claude`(=**thinkingmachines/inkling:free**, OpenRouter 可服务;
        #   2026-09-21 实测修正: 原值 `claude-sonnet-4-5` 是 Claude 原生 id ⇒ 经 OpenRouter 被路由到
        #   真实 Anthropic 上游 ⇒ **403 地区墙**, 见 ROUTE_TABLE 处注释), 可用 env `AGENT_FALLBACK_MODEL` 覆盖。
        $fbModel = if ($env:AGENT_FALLBACK_MODEL) { $env:AGENT_FALLBACK_MODEL } else { 'claude' }
        # 判据要的是**后端属性**(是否 `:free` = 是否可能训练/公开), 而别名本身看不出这属性 ⇒
        #   必须**先 Resolve-Model 拿到 id 再判**(这也是本函数收"属性"而非"型号前缀"的原因)。
        $fbR = Resolve-Model $fbModel
        $fbId = if ($fbR) { $fbR['id'] } else { $fbModel }
        $rej = Get-SensitivityBackendReject -sensitivity $sens -backendEgress $true -backendTrains ("$fbId" -match ':free')
        if ($rej) {
            Write-Host "AUTO_FALLBACK: opencode rc=$code -> REFUSED (sensitivity=$sens, backend=$fbId)"
            Write-Host "REJECT $rej (fallback, $fbId) exit 4 - no override channel (owner-policy)"
            return 4
        }
        Write-Host "AUTO_FALLBACK: opencode rc=$code -> local claude backup (explicit -AutoFallback)"
        Write-Host "AUTO_FALLBACK_MODEL: $taskModel -> $fbModel"
        return (Invoke-Task-Claude -proj $proj -card $card -model $fbModel -sensitive $sens -attach $attach -complexity $complexity -taskType $taskType)
    }
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
    # O-15/AUDIT (2026-09-21): 判据需要本地 **Git Bash**(bash 语义, 见 Resolve-LocalBash 的定案)。
    #   **提前**拒绝(= 在跑 agent 之前, 与 claude-not-installed 同处): 否则会白跑完整轮次才发现
    #   无法判 accept。刻意**不**退回 PowerShell `Invoke-Expression` —— 那正是本次修掉的 bug
    #   (bash 语义的命令在 PS 里必失败 ⇒ 判据假红灯)。缺 Git Bash 是**环境不全**, 该明确拒绝。
    $bashPath = Resolve-LocalBash
    if (-not $bashPath) {
        Write-Host "REJECT local-bash-missing (exit 13) - 未找到 Git Bash(C:\Program Files\Git\bin\bash.exe)。"
        Write-Host "  卡的 accept/accept-golden 是 **bash 语义**, 备路必须用 Git Bash 判(不退回 PowerShell/WSL)。"
        return 13
    }
    if (-not $card) { Write-Host 'task requires --card <task.md>'; return 2 }
    if (-not (Test-Path $card)) { throw "card not found: $card" }
    $projRoot = $Script:PROJECTS[$proj]
    if (-not $projRoot -or -not (Test-Path $projRoot)) { throw "unknown/missing project: $proj (registered: $($Script:PROJECTS.Keys -join ','))" }
    if (-not $attach) { $attach = @() }

    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    $fm = Get-FrontMatter $card
    # ADR-0007 前置(2026-09-18): 卡身份 —— 与主路**共用单一实现点** Get-CardIdentity(避免两处各算一份漂移);
    #   含形状守卫(环境层可能往管道吐 $null 使返回值变数组, 缺口 5 实测教训)。
    $cardId = Get-CardIdentity $card
    if ($cardId -is [array]) { $cardId = $cardId[0] }
    $m = if ($model) { $model } else { if ($fm['model']) { $fm['model'] } else { '' } }
    $sens = if ($sensitive) { $sensitive } else { if ($fm['sensitivity']) { $fm['sensitivity'] } else { 'public' } }
    if (-not $m) { Write-Host 'REJECT missing-model (exit 2) - card has no model and no --model (inv 3)'; return 2 }
    # ADR-0007 前置: 无 front-matter 卡须显式声明安全属性(claude 备路独立入口也要护栏)
    $cardOk = Test-CardSafetyDeclared $card $cardId $sensitive
    if ($cardOk -is [array]) { $cardOk = @($cardOk | Where-Object { $null -ne $_ })[0] }
    if (-not $cardOk) { return 2 }
    $readonly = [bool]$fm['readonly']
    $timeout = [int]$fm['timeout_s']
    $continueTimeout = [int]$fm['continue-timeout-s']
    if ($continueTimeout -le 0) { $continueTimeout = $timeout }
    Write-Host "BUDGET: first=$timeout resume=$continueTimeout (claude local backup)"


    $r = Resolve-Model $m
    if (-not $r) { Write-Host "REJECT unknown-model ($m) exit 2 - not in route table"; return 2 }
    $id = $r['id']
    if ($r['station']) { Write-Host "REJECT claude-station=$($r['station']) (exit 4) - claude channel must run local (station='')"; return 4 }
    # ⚠ P0 止血 + P1 免费档闸 (2026-09-21, 安全策略洞 · 出网路径①): **local-only / sanitized 不走本通道**
    #   —— 本函数是**主控本地** spawn claude, 其 ANTHROPIC_BASE_URL(主控 settings.json)= 云端
    #   OpenRouter, 且 ROUTE_TABLE 的 `claude`/`claude-opus` 型号**都是 `:free`** ⇒ 该档
    #   **出网 且 可能训练/公开输入**(P1 实测: 免费端点对 `data_collection=deny` 与 `zdr` **均 404**)。
    #   此前本函数**没有任何** sensitivity 判据, 而既有三处闸(Resolve-Model L435 / Invoke-Task L987 /
    #   route cmd L1837)一律只判 `^opencode/` ⇒ 卡写 `sensitivity: local-only` + `cli: claude`
    #   会从 L987 **放行**并在本函数出网。该洞此前**惰性**(备路不可用 `Not logged in`),
    #   2026-09-21 备路修通后**变活** ⇒ 破 DESIGN §358。→ 与既有三处同族: REJECT + exit 4, 无覆写通道。
    $rej = Get-SensitivityBackendReject -sensitivity $sens -backendEgress $true -backendTrains ($id -match ':free')
    if ($rej) {
        Write-Host "REJECT $rej (claude-direct, $id) exit 4 - no override channel (owner-policy)"
        return 4
    }

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
    $attachEntries = @()
    if ($attach.Count -gt 0) {
        # claude cwd=projRoot -> attach 复制到 projRoot\.attach (与远程 workspace 语义一致)
        $attachLocal = Join-Path $projRoot '.attach'
        New-Item -ItemType Directory -Path $attachLocal -Force -EA SilentlyContinue | Out-Null
        $names = @()
        foreach ($a in $attach) {
            if (-not (Test-Path $a)) { Write-Host "attach missing (skip): $a"; continue }
            $name = Split-Path $a -Leaf
            $isDir = Test-Path $a -PathType Container
            $srcAbs = $a
            try { $srcAbs = (Resolve-Path -LiteralPath $a -EA Stop).Path } catch { }
            try { Copy-Item $a (Join-Path $attachLocal $name) -Recurse -Force -EA Stop; $names += $name } catch { Write-Host "ATTACH_WARN: local copy failed: $a ($($_.Exception.Message))"; continue }
            # O-15/AUDIT (2026-09-21): 附件身份 —— 与主路缺口 5 同目标, 但**无远端 attach-manifest**
            #   (claude 本地执行不产该件) ⇒ 摘要取自**本地源文件**哈希(复制到 .attach/ 的注入字节)。
            #   单文件 = 其字节哈希; 目录 = 对 `relpath:sha256` 行整体哈希的**树摘要**(Get-Sha256Lines)。
            $lines = New-Object System.Collections.ArrayList
            if (-not $isDir) {
                [void]$lines.Add("$name`:" + (Get-FileHash -Algorithm SHA256 $srcAbs).Hash.ToLower())
                $files = 1
            } else {
                $files = 0
                foreach ($f in @(Get-ChildItem -LiteralPath $srcAbs -Recurse -File -EA SilentlyContinue)) {
                    $files++
                    $rel = Join-Path $name ($f.FullName.Substring($srcAbs.Length).TrimStart('\','/'))
                    [void]$lines.Add("$rel`:" + (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLower())
                }
            }
            $attachEntries += [ordered]@{ name=$name; src=$srcAbs; kind=$(if($isDir){'dir'}else{'file'}); files=$files; sha256=Get-Sha256Lines $lines }
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
            # O-15/AUDIT (2026-09-21): 与 accept **同语义** —— 本地 Git Bash, cwd=projRoot。
            #   原为 PowerShell `Invoke-Expression`(与 accept 同一个 bug, 故一并修:
            #   "只修一半的修复看起来是完整的")。输出落 `accept-golden-output.txt` ⇒ 备路首次
            #   也有黄金门**输出证据**(此前该件在备路恒不存在)。
            $garc = Invoke-LocalBashCmd -bashPath $bashPath -cmd $g.cmd -cwd $projRoot -logFile $accGoldTxt
            if ($garc -ne 0) { $acceptGoldenOk = 0 }
        }
        if ($acceptGoldenOk -eq 1) { Write-Host "ACCEPT_GOLDEN_OK=1" } else { Write-Host "ACCEPT_GOLDEN_OK=0" }
    }
    # ---- accept gate (A14) ----
    # O-15/AUDIT (2026-09-21): 用**本地 Git Bash**跑(**bash 语义**, 与主路一致; 见 Resolve-LocalBash)。
    #   输出逐行落 `accept-output.txt`(与主路契约一致) —— 备路此前用 `*> $null` **丢弃输出**,
    #   只留 rc, 出 bug 无从复核。
    $acceptOk = 1
    if ($accept.Count -gt 0) {
        Write-Host "ACCEPT_MODE=bash-local ($bashPath, cwd=$projRoot)"
        $i = 0
        foreach ($c in $accept) {
            $i++
            Add-Content $accTxt "=== ACCEPT_CMD[$i] >>> $c"
            $arc = Invoke-LocalBashCmd -bashPath $bashPath -cmd $c -cwd $projRoot -logFile $accTxt
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
    try { Add-Content -Path $ledger -Value $line -Encoding utf8 | Out-Null } catch { Write-Host "LEDGER_WARN: $($_.Exception.Message)" }

    $collectOk = $true; $runDir = ''
    try {
        $projOutRoot = Join-Path $projRoot 'agent-out'
        if (-not (Test-Path $projOutRoot)) { New-Item -ItemType Directory -Path $projOutRoot -Force | Out-Null }
        $runDir = Join-Path $projOutRoot $ts
        New-Item -ItemType Directory -Path $runDir -Force | Out-Null
        # ADR-0007 前置: 归档卡字节(与主路同一处置; 卡会改 ⇒ 只记 hash 无法复跑)
        if ($cardId.path -and (Test-Path -LiteralPath $cardId.path)) {
            Copy-Item -LiteralPath $cardId.path -Destination (Join-Path $runDir 'card.md') -Force | Out-Null
        }
    } catch { $collectOk = $false; $runDir = "$projRoot\agent-out\<$ts>"; Write-Host "COLLECT_FAIL: $($_.Exception.Message)" }

    $contentSha = if (Test-Path $outTxt) { Get-Sha256Text ([IO.File]::ReadAllText($outTxt)) } else { '' }
    $run = [ordered]@{
        proj = $proj; task_id = "task-$ts"; cli = 'claude'; model = $id; sensitivity = $sens
        readonly = $readonly; session_id = ''; exit_code = $finalCode
        status = if ($finalCode -eq 0) { 'completed' } elseif ($finalCode -eq 6) { 'timeout' } else { 'failed' }
        # 缺口 8 **刻意不做 claude 备路**(与缺口 5/6 同例): 该路的会话不落在 opencode 会话库 ⇒
        #   不猜数, 用 source 显式标注"未采集", 使"0"与"没采集"可区分。
        content_digest = "sha256:$contentSha"
        usage = [ordered]@{ source = 'not-collected-claude-path'; total_tokens = 0; tool_uses = 0 }
        queue_s = 0; run_s = $runS; slot = $null
        output_bytes = $outputBytes; output_bps = $outputBps
        timestamp_start = ''; timestamp_end = ''
        prompt_sha256 = "sha256:$promptSha"; attach = $attachEntries
        # ADR-0007 前置(2026-09-18): 卡身份(与主路同一处置)
        card = $cardId
        profile = [ordered]@{ name=$prof.profile; context=$prof.context; max_output=$prof.max_output;
                              thinking=$prof.thinking; template=$prof.template; reasoning_format=$prof.reasoning_format; flavor=$prof.flavor }
        accept = [ordered]@{ cmd = @($accept); passed = ($acceptOk -eq 1) }
        collect = if ($collectOk) { 'ok' } else { 'failed' }
    }
    if ($goldenActive) {
        $run['accept_golden'] = [ordered]@{ cmd = @($g.cmd); passed = ($acceptGoldenOk -eq 1); source = 'golden'; hidden_from_model = $true
                                            sha256 = $goldenSha; base = $goldenBase }   # ADR-0005 D3: 当次权威 checksum 只记于此
    }
    # O-15/AUDIT (2026-09-21): **claude 备路证据面到齐 → recipe v2**(此前该路 run 恒 v1 = 零声明,
    #   audit 不可判 —— 审查总账"该路 run 恒 v1, 需按路各一份基线, 单独立项"; 本次落地)。
    #   复用主路 Merge-EvidenceSubjects(基线在前、卡声明在前者去重), 但**按本路归档件集**给基线
    #   (Get-ClaudeFrameworkSubjects): 有 stderr.txt、无 judgment-record/accept-cmds/progress-trace/
    #   session-meta/attach-manifest/workspace-diff ⇒ 不能复用 opencode 基线(否则每个 claude run
    #   都假报缺件)。遥测 usage 维持明标 `not-collected-claude-path`(claude 无 opencode 会话库, 不猜数)。
    $evmC = $fm['evidence-manifest']
    $mergedSubjects = @(Merge-EvidenceSubjects @($evmC['subjects']) $accept $goldenActive { param($ac,$ga) Get-ClaudeFrameworkSubjects $ac $ga })
    if ($mergedSubjects.Count -gt 0) {
        $mergedVer = "$($evmC['version'])".Trim()
        if (-not $mergedVer) { $mergedVer = '1' }
        $run['evidence_manifest'] = [ordered]@{ version = $mergedVer; subjects = $mergedSubjects }
    }
    if ($collectOk) {
        try {
            $run | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $runDir '.agent-run.json') -Encoding utf8
            # ⚠ 归零纪律(见 Invoke-Task 内注): 本函数返回 `$finalCode`, 故以下副作用一律 `| Out-Null`。
            if (Test-Path $outTxt) { Copy-Item $outTxt (Join-Path $runDir 'agent-output.txt') -Force | Out-Null }
            if (Test-Path $accTxt) { Copy-Item $accTxt (Join-Path $runDir 'accept-output.txt') -Force | Out-Null }
            if ($goldenActive -and (Test-Path $accGoldTxt)) { Copy-Item $accGoldTxt (Join-Path $runDir 'accept-golden-output.txt') -Force | Out-Null }
            # ADR-0005 D1 (2026-09-16) 证据回收闭环(本地备路): prompt 全文 + stderr 归 runDir ——
            #   本路的 prompt/stderr 是主控本地 scratch 里的件, 此前同样不归档(出 bug 时无从复核)。
            if (Test-Path $promptIn) { Copy-Item $promptIn (Join-Path $runDir 'prompt.txt') -Force | Out-Null }
            if (Test-Path $errTxt) { Copy-Item $errTxt (Join-Path $runDir 'stderr.txt') -Force | Out-Null }
        } catch { $collectOk = $false; Write-Host "COLLECT_FAIL: $($_.Exception.Message)" }
    }
    # ADR-0005 D4a/D4c (2026-09-16): **归档成功才清理** scratch(本路原为 Copy-Item, scratch 此前永不
    #   清理); 失败则保留并打印可寻路径 —— 不得"既没归档又被删"。
    if ($collectOk) { try { Remove-Item $scratch -Recurse -Force -ErrorAction SilentlyContinue | Out-Null } catch {} }
    else { Write-Host "EVIDENCE_LEFT_IN_SCRATCH=$scratch" }

    Write-Host "TASK_DONE dir=$runDir exit=$finalCode cli=claude prompt_sha256=sha256:$promptSha"
    Write-Host "ledger+=$line"
    return $finalCode
}

function Resolve-ClaudeSpawn {
    # O-15/AUDIT (2026-09-21): 把 `claude` 解析为"可直接 Start-Process 的原生可执行", 绕开 Windows npm shim。
    # 现象: Get-Command claude 命中 ExternalScript=`...\npm\claude.ps1`; 因 Invoke-ClaudeFly 用了
    #   `-RedirectStandardInput` ⇒ PS 强制 `UseShellExecute=$false` ⇒ Start-Process 走 CreateProcess 直接
    #   把该 .cmd/.ps1 shim 当 Win32 程序加载 ⇒ 报 "%1 不是有效的 Win32 应用程序"(2026-09-21 实测,
    #   rc=7, 备路即便登录也在 exec 级失败)。
    # 处置: 定位 npm 同时生成的**原生二进制** `node_modules\@anthropic-ai\claude-code\bin\claude.exe`
    #   (本环境实测存在; --version headless 正常)。直调该 exe ⇒ 与 shim 等效但可被 CreateProcess 加载,
    #   stdin/stdout/stderr 重定向无碍。纯 JS 部署(无 .exe)则保留原样走 PATH(可能复现旧失败, 少见)。
    $cmd = Get-Command claude -ErrorAction SilentlyContinue
    if (-not $cmd) { return 'claude' }
    $src = "$($cmd.Source)"
    try { $src = (Get-Item -LiteralPath $src -ErrorAction Stop).FullName } catch { }
    $ext = [IO.Path]::GetExtension($src).ToLower()
    if ($ext -eq '.exe') { return $src }                       # 真 exe(PATH 层级已是原生)
    if ($ext -eq '') { return 'claude' }                       # bash shebang / Unix 直 exec
    # Windows npm shim(.ps1/.cmd): 与 shim 同 npmRoot 下的原生 bin
    $base = Split-Path $src -Parent
    $native = Join-Path $base 'node_modules\@anthropic-ai\claude-code\bin\claude.exe'
    if (Test-Path $native) { return $native }
    return $src                                                # 兜底(可能复现旧 exec 失败)
}

function Resolve-LocalBash {
    # O-15/AUDIT (2026-09-21): 本地 **Git Bash** —— 供 claude 本地备路执行卡的判据命令。
    #   语义决定(定案): 卡里的 `accept` / `accept-golden` **一律是 bash 语义** —— 主路在**远端 bash**
    #   跑, 备路在**本地 Git Bash** 跑; 两条路只差**执行机器与 cwd**(远端 Linux 工作区 vs 本地 projRoot),
    #   **不差 shell**。为什么必须统一: 备路原先用 PowerShell `Invoke-Expression` 跑 ⇒ 实测
    #   `ACCEPT_CMD[1] >>> true` 得 `ACCEPT_RC=1`(`true` 不是 PS 命令) ⇒ **即使 claude 成功,
    #   accept 也必判失败** ⇒ 备路等于白修(与"exec 级失败"同族的**判据级失败**)。
    #   ⚠ 刻意**不走 PATH 的 `bash`** —— 本机实测 PATH 命中 `C:\Windows\system32\bash.exe`(**WSL**)。
    #   WSL 在**另一个文件系统 + 另一套 cwd 映射**里执行, 与 Git Bash **不是同一环境**: 拿它跑卡里的
    #   accept 会在错误的目录语义下判 —— "看起来跑了", 判的却不是这里的东西(同"恒真/恒假判据"族)。
    #   Git Bash 本就是**项目硬前提**(S1: `$Script:GNU_TAR` 直接指向 Git 的 tar; 远端脚本全 `.sh`)。
    foreach ($c in @('C:\Program Files\Git\bin\bash.exe',
                     'C:\Program Files\Git\usr\bin\bash.exe',
                     'C:\Program Files (x86)\Git\bin\bash.exe')) {
        if (Test-Path $c) { return $c }
    }
    return ''      # 缺失 ⇒ 调用方必须**显式拒绝**(绝不静默换 WSL/PowerShell)
}

function Invoke-LocalBashCmd {
    # 在本地 Git Bash 里跑**一条**判据命令, cwd = $cwd; 返回其 exit code(= 判据 rc)。
    #   输出(含 stderr)逐行追加到 $logFile ⇒ 与主路 `accept-output.txt` 的契约对齐
    #   (主路是 `>> out/.accept-output.txt 2>&1`; 备路此前**只记 rc 不记输出**, 出 bug 无从复核)。
    param([string]$bashPath, [string]$cmd, [string]$cwd, [string]$logFile)
    $rc = 0
    Push-Location $cwd
    try {
        & $bashPath -c $cmd 2>&1 | Add-Content -Path $logFile -ErrorAction SilentlyContinue
        if ($LASTEXITCODE -ne 0) { $rc = $LASTEXITCODE }
    }
    catch { $rc = 1 }
    finally { Pop-Location }
    return $rc
}

function Invoke-ClaudeFly {
    # 直起 claude headless: stdin 从文件喂, stdout/stderr 落盘; 预算超时则 kill 并返回 124。
    # ⚠ **2026-09-21 实弹实测修正**: 原写法 `Start-Process -NoNewWindow -PassThru -RedirectStandard*`
    #   在本 PS5.1 上 **`$p.ExitCode` 恒为 `$null`**(实测: 加 `-Wait` 才非空, 仅调无参 `WaitForExit()`
    #   或 `Refresh()` 都补不回来) ⇒ `$rc` 变 **空串** ⇒ 两处后果: ①`'' -ne 0` 为真 ⇒ resume 循环空转;
    #   ②`$null -eq 0` 为假 ⇒ **成功的 claude run 也会被判 `failed`**(最终码恒 1) —— 备路等于白修。
    #   改用 .NET `Process`+`ProcessStartInfo`: `WaitForExit(ms)` 语义不变(**保留预算内 kill**),
    #   且 `ExitCode` 真实可读(**实测 `--version` 得 0**)。
    param([string]$argStr, [string]$stdin, [string]$stdout, [string]$stderr, [string]$scratch, [int]$budgetS)
    if (-not (Test-Path $stdin)) { [IO.File]::WriteAllText($stdin, '', (New-Object System.Text.UTF8Encoding $false)) }
    $fsIn = $null; $fsOut = $null; $fsErr = $null
    try {
        $spawn = Resolve-ClaudeSpawn
        Write-Host "CLAUDE_SPAWN=$spawn"
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $spawn
        $psi.Arguments = $argStr
        $psi.UseShellExecute = $false
        $psi.RedirectStandardInput = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true
        $proc = [System.Diagnostics.Process]::Start($psi)
        # 三路**并发**搬运, 防任一管道写满互锁: stdin 从文件灌入, stdout/stderr 落文件。
        #   必须先起 stdout/stderr 的搬运再去等 stdin —— 否则"子进程猛写 stdout 而我们卡在喂 stdin"会死锁。
        $fsIn  = [IO.File]::OpenRead($stdin)
        $fsOut = [IO.File]::Create($stdout)
        $fsErr = [IO.File]::Create($stderr)
        $tIn  = $fsIn.CopyToAsync($proc.StandardInput.BaseStream)
        $tOut = $proc.StandardOutput.BaseStream.CopyToAsync($fsOut)
        $tErr = $proc.StandardError.BaseStream.CopyToAsync($fsErr)
        $tIn.Wait()                              # 喂完即关 stdin(等价 `< file` 的 EOF 语义)
        try { $proc.StandardInput.Close() } catch { }
        $done = $proc.WaitForExit($budgetS * 1000)
        if (-not $done) { try { $proc.Kill() } catch { }; try { $proc.WaitForExit() } catch { } }
        # 收尾: 等三路搬运收敛(进程已退出 ⇒ 管道关闭 ⇒ 任务立即完成), 再取 rc
        foreach ($t in @($tIn, $tOut, $tErr)) { try { [void]$t.Wait(5000) } catch { } }
        if (-not $done) { return @{ code = 124; msg = "timeout after ${budgetS}s (killed)" } }
        return @{ code = $proc.ExitCode; msg = '' }
    }
    catch { return @{ code = 7; msg = $_.Exception.Message } }
    finally {
        foreach ($fs in @($fsIn, $fsOut, $fsErr)) { if ($fs) { try { $fs.Dispose() } catch { } } }
    }
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
    # 同上(归零纪律): 本函数返回**文本**, 故收尾的 Remove-Item 必须 `| Out-Null`。
    Remove-Item $localPath -ErrorAction SilentlyContinue | Out-Null
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
        # O-15/AUDIT: 自动 fallback 的**显式开关走 env `AGENT_AUTO_FALLBACK=1`**(默认关、显式开启)。
        #   ⚠ 不放顶/函数单项 switch 到脚本 param(): 实测 top-level param 块在此 PS5.1 环境**无法再新增一个
        #   param**(pristine HEAD 单加一行也报 Missing-')') ⇒ 走 Invoke-Task 的**函数级** switch, 由 env 桥接。
        $autoFb = ($env:AGENT_AUTO_FALLBACK -eq '1')
        $code = Invoke-Task -proj $Proj -card $Card -model $Model -sensitive $Sensitivity -type $Type -hostName $RemoteHost -attach $Attach -complexity $Complexity -taskType $TaskType -SlotAllowBusy:$SlotAllowBusy -cli $Cli -AutoFallback:$autoFb
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