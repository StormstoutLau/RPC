$ErrorActionPreference = 'Continue'
$cli = 'd:\RPC\ops\station-bin\agent-cli.ps1'
$card = 'd:\RPC\tmp\gate-card.md'
$runId = '202609031510368423'

Write-Host '=== S1: local-only + ultra (egress) -> expect exit 4 sensitive reject ==='
& $cli 'review' 'paper' '--card' $card '--run-id' $runId '--sensitivity' 'local-only' '--model' 'ultra' 2>&1 | Out-Host
Write-Host "S1 exit=$LASTEXITCODE"