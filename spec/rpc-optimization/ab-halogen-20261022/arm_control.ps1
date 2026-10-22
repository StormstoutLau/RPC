param(
    [Parameter(Mandatory = $true)][string]$ImageRef,
    [Parameter(Mandatory = $true)][string]$Label
)
$ErrorActionPreference = "Stop"
$station = "C"
$ip = "192.168.10.37"
Write-Host "=== ARM $Label : $ImageRef (+ splice/nest off) ==="

& py -3 ops\cluster.py containers down --station $station --name halogen --go | Out-Host
if ($LASTEXITCODE -ne 0) { throw "containers down failed" }

for ($i = 0; $i -lt 120; $i++) {
    $state = ssh -o BatchMode=yes scott-lau@$ip "ss -ltn 2>/dev/null | grep -q ':8080 ' && echo BUSY || echo FREE"
    if ($state -match "FREE") { break }
    Start-Sleep -Seconds 2
    if ($i -eq 119) { throw "port 8080 still busy" }
}

& py -3 ops\cluster.py containers up --station $station --name halogen --image $ImageRef `
    --publish "127.0.0.1:8080:8731" --publish "127.0.0.1:8731:8731" `
    --group-add 44 --group-add 992 --device /dev/kfd --device /dev/dri `
    --volume "/data/models/gguf/lmstudio-community/Qwen3.8-Flash-Next-GGUF/UD-IQ4_XS:/models" `
    --env "HALOGEN_CHECKPOINT=/models/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf" `
    --env "HALOGEN_DOWNLOAD=peonist-ai/halogen-qwen3.8-flash-next" `
    --env "HF_ENDPOINT=https://hf-mirror.com" --env "HF_HUB_DISABLE_XET=1" `
    --env "HALOGEN_ADMIT_SPLICE_MS=0" --env "HALOGEN_ADMIT_NEST=0" `
    --ipc host --ulimit memlock=-1:-1 --go | Out-Host
if ($LASTEXITCODE -ne 0) { throw "containers up failed" }

for ($i = 0; $i -lt 120; $i++) {
    $raw = ssh -o BatchMode=yes scott-lau@$ip "curl -s --max-time 5 http://127.0.0.1:8080/health"
    $j = $null
    try { $j = $raw | ConvertFrom-Json } catch { }
    if ($j -and $j.status -eq "ok") {
        "HEALTH_OK version=$($j.version.api) model=$($j.model) ctx=$($j.context) pool=$($j.kv_pool_positions)"
        exit 0
    }
    Start-Sleep -Seconds 3
    if ($i -eq 119) { throw "health timeout" }
}
