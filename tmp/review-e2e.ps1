$cli = 'd:\RPC\ops\station-bin\agent-cli.ps1'
$card = 'd:\RPC\tmp\public-card.md'
$runId = '202609031510368423'

Write-Host '=== E1: public + default judge (ultra, egress via B) ==='
$out = & powershell -NoProfile -ExecutionPolicy Bypass -File $cli 'review' 'paper' '-Card' $card '-RunId' $runId 2>&1
$code = $LASTEXITCODE
$out | ForEach-Object { Write-Host $_ }
Write-Host "E1 exit=$code"
Write-Host '=== review.json status ==='
if (Test-Path "D:\Paper\agent-out\$runId\review.json") {
    Get-Content "D:\Paper\agent-out\$runId\review.json" -Raw -ErrorAction SilentlyContinue
} else {
    Write-Host 'no review.json'
}