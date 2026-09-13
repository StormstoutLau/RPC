$cli = 'd:\RPC\ops\station-bin\agent-cli.ps1'
$card = 'd:\RPC\tmp\gate-card.md'
$runId = '202609031510368423'

# invoke the cli as a fresh child process via -File to avoid in-process param binding issues
$out = & powershell -NoProfile -ExecutionPolicy Bypass -File $cli 'review' 'paper' '--card' $card '--run-id' $runId '--sensitivity' 'local-only' '--model' 'ultra' 2>&1
$code = $LASTEXITCODE
$out | ForEach-Object { Write-Host $_ }
Write-Host "S1 exit=$code (expect 4)"