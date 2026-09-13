# thin loader (O-11 L2 workaround): PS5.1 CP936 mis-parses BOM-less UTF-8 with non-ASCII strings;
# copy source to BOM'd temp file then -File it (agent-cli source is committed BOM-less by design).
$src = 'd:\RPC\ops\station-bin\agent-cli.ps1'
$tmp = Join-Path $env:TEMP ('o26-cli-' + [Guid]::NewGuid().ToString('N') + '.ps1')
$text = [System.IO.File]::ReadAllText($src, [System.Text.Encoding]::UTF8)
[System.IO.File]::WriteAllText($tmp, $text, (New-Object System.Text.UTF8Encoding $true))

$sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    & $tmp 'split' 'paper' -card 'd:\RPC\test-cards\o26-split-fanout.md' -attach 'd:\RPC\test-cards\_o26_src.txt'
} finally {
    $sw.Stop()
    Write-Host "LOADER_WALL_MS=$($sw.ElapsedMilliseconds)"
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
}