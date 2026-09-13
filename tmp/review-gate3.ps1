$cli = 'd:\RPC\ops\station-bin\agent-cli.ps1'
$card = 'd:\RPC\tmp\gate-card.md'
$runId = '202609031510368423'

$out = & powershell -NoProfile -ExecutionPolicy Bypass -File $cli 'review' 'paper' '-Card' $card '-RunId' $runId '-Sensitivity' 'local-only' '-Model' 'ultra' 2>&1
$code = $LASTEXITCODE
$out | ForEach-Object { Write-Host $_ }
Write-Host "S1 exit=$code (expect 4)"