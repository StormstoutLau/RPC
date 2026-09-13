$cli = 'd:\RPC\ops\station-bin\agent-cli.ps1'
$card = 'd:\RPC\tmp\public-card.md'
$runId = '202609031510368423'

Write-Host '=== E2: idempotent re-run, no overwrite (expect exit 0 + reuse prompt) ==='
$out = & powershell -NoProfile -ExecutionPolicy Bypass -File $cli 'review' 'paper' '-Card' $card '-RunId' $runId 2>&1
$code = $LASTEXITCODE
$out | ForEach-Object { Write-Host $_ }
Write-Host "E2 exit=$code"

Write-Host '=== E3: overwrite forces re-review (expect real judge call again, exit 0) ==='
$out = & powershell -NoProfile -ExecutionPolicy Bypass -File $cli 'review' 'paper' '-Card' $card '-RunId' $runId '-Overwrite' 2>&1
$code = $LASTEXITCODE
$out | ForEach-Object { Write-Host $_ }
Write-Host "E3 exit=$code"