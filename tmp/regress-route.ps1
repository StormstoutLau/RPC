$cli = 'd:\RPC\ops\station-bin\agent-cli.ps1'

Write-Host '=== R1: route nemotron (existing alias regression) ==='
$out = & powershell -NoProfile -ExecutionPolicy Bypass -File $cli 'route' '-Model' 'nemotron' '-Sensitivity' 'public' 2>&1
$code = $LASTEXITCODE
$out | ForEach-Object { Write-Host $_ }
Write-Host "R1 exit=$code"

Write-Host '=== R2: route unknown alias (expect exit 2 reject) ==='
$out = & powershell -NoProfile -ExecutionPolicy Bypass -File $cli 'route' '-Model' 'nonexistent-xyz' '-Sensitivity' 'public' 2>&1
$code = $LASTEXITCODE
$out | ForEach-Object { Write-Host $_ }
Write-Host "R2 exit=$code"