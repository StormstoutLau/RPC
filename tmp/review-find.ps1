$ErrorActionPreference = 'Stop'
$cli = 'd:\RPC\ops\station-bin\agent-cli.ps1'

function Invoke-Cli($argsList) {
    & $cli @argsList
    return $LASTEXITCODE
}

Write-Host '=== T2: route unknown alias (expect 2/4) ==='
& $cli 'route' '--model' 'nonexistent-xyz' 2>&1 | Out-Host
Write-Host "T2 exit=$LASTEXITCODE"

# find a real task card + matching completed runDir
$runDirs = Get-ChildItem 'D:\Paper\agent-out' -Directory | Sort-Object Name -Descending
Write-Host "=== candidate runDirs with agent-output.txt ==="
foreach ($d in $runDirs) {
    $prod = Join-Path $d.FullName 'agent-output.txt'
    $runjson = Join-Path $d.FullName '.agent-run.json'
    if ((Test-Path $prod) -and (Test-Path $runjson)) {
        $sz = (Get-Item $prod).Length
        if ($sz -gt 0) {
            Write-Host $d.Name
        }
    }
}