# ============================================================================
# _switch_qwen_flavor.ps1 - L1 instance-layer flavor switch (console -> B station)
# Pushes ops/station-bin/qwen-flavor-<flavor>.env to the B station active conf
# (/etc/llama-instances/qwen3.8-27b-mtp.env) and reloads llama-server@qwen3.8-27b-mtp
# with memory-guard + /props verification. MANUAL tool - only run in an idle window
# because it interrupts the running qwen instance for the reload duration.
#
# usage: powershell -File _switch_qwen_flavor.ps1 -Flavor nothink|think|long
#   nothink -> code/doc, thinking OFF,   ctx 8192   (proven-best 5/5 default)
#   think   -> reason/short,     thinking ON,  ctx 32768
#   long    -> big docs,         thinking ON,  ctx 262144
# source kept ASCII-only for PS5.1 BOM safety.
# ============================================================================
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet('nothink','think','long')][string]$Flavor,
    [string]$Station = 'B'
)
$ErrorActionPreference = 'Stop'
if ($Station -eq 'A') { $hostName = 'scott-lau-NEX.local' } else { $hostName = 'scott-lau-GTR-Pro.local' }

$preset = Join-Path $PSScriptRoot "qwen-flavor-$Flavor.env"
$sh = Join-Path $PSScriptRoot '_switch_qwen_flavor.sh'
if (-not (Test-Path $preset)) { Write-Host "ERR: no preset $preset"; exit 1 }
if (-not (Test-Path $sh))     { Write-Host "ERR: no script $sh"; exit 1 }

$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes([IO.File]::ReadAllText($preset)))
Write-Host "SWITCH flavor=$Flavor -> $hostName (preset=$preset)"

# --- ensure guard scripts exist on the station before switch (idempotent, self-healing) ---
# The remote _switch_qwen_flavor.sh prefers $(dirname)/wait-gtt-release then /home/scott-lau/.
# /tmp copies are ephemeral, so deploy the guards to /home/scott-lau/ every switch.
$guards = @('wait-gtt-release', 'load-mem-gate')
foreach ($g in $guards) {
    $localGuard = Join-Path $PSScriptRoot $g
    if (-not (Test-Path $localGuard)) { Write-Host "WARN: local guard missing $localGuard (skip)"; continue }
    # cheap existence check on the station; scp only if missing (also forces +x)
    $chk = ssh -o ConnectTimeout=10 -o BatchMode=yes $hostName "[ -x /home/scott-lau/$g ] && echo present || echo missing" 2>$null
    if ($LASTEXITCODE -eq 0 -and "$chk" -match 'present') { continue }
    Write-Host "GUARD deploy: $g -> /home/scott-lau/"
    scp -q -o ConnectTimeout=10 $localGuard "${hostName}:/home/scott-lau/$g" 2>$null
    if ($LASTEXITCODE -ne 0) { Write-Host "WARN: scp guard $g failed"; continue }
    ssh -o ConnectTimeout=10 -o BatchMode=yes $hostName "chmod +x /home/scott-lau/$g" 2>$null
}

scp -q -o ConnectTimeout=10 $sh "${hostName}:/tmp/_switch_qwen_flavor.sh"
if ($LASTEXITCODE -ne 0) { Write-Host "ERR: scp _switch_qwen_flavor.sh failed"; exit 5 }

$sshCmd = "bash /tmp/_switch_qwen_flavor.sh $Flavor $b64"
try {
    $out = ssh -o ConnectTimeout=10 -o BatchMode=yes $hostName $sshCmd 2>&1
    $code = $LASTEXITCODE
} catch { $out = @("$($_.Exception.Message)"); $code = 255 }
$out | ForEach-Object { Write-Host $_ }
Write-Host "SWITCH remote exit=$code"
exit $code