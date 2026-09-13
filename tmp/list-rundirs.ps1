$ErrorActionPreference = 'Continue'
$runDirs = Get-ChildItem 'D:\Paper\agent-out' -Directory | Sort-Object Name -Descending
foreach ($d in $runDirs) {
    $prod = Join-Path $d.FullName 'agent-output.txt'
    $runjson = Join-Path $d.FullName '.agent-run.json'
    if ((Test-Path $prod) -and (Test-Path $runjson)) {
        $sz = (Get-Item $prod).Length
        if ($sz -gt 0) {
            Write-Host $d.Name " prod=$sz"
        }
    }
}