$ErrorActionPreference = 'Stop'
$cli = 'd:\RPC\ops\station-bin\agent-cli.ps1'

function Invoke-Cli($argsList) {
    & $cli @argsList
    return $LASTEXITCODE
}

Write-Host '=== T1: review no args (expect exit 2 + usage) ==='
$c = Invoke-Cli @('review')
Write-Host "T1 exit=$c"

Write-Host '=== T2: unknown alias (expect exit 2 reject) ==='
$c = Invoke-Cli @('route', '--model', 'nonexistent-xyz')
Write-Host "T2 exit=$c"

Write-Host '=== T3: review with card that does not exist (expect exit 3 card not found) ==='
$c = Invoke-Cli @('review', 'paper', '--card', 'D:\Paper\no-such-card.md')
Write-Host "T3 exit=$c"

Write-Host '=== T4: sensitivity gate local-only + egress judge ultra ==='
$c = Invoke-Cli @('review', 'paper', '--card', 'D:\Paper\no-such-card.md', '--sensitivity', 'local-only', '--model', 'ultra')
Write-Host "T4 exit=$c (note: card check runs before judge gate resolves runDir first? verify order)"