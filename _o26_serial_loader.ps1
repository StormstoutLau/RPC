# O-26 serial baseline: run the two shard cards back-to-back (A then B), sum wall.
# Production-style invocation via BOM copy so $MyInvocation/children path correctly.
param(
  [string]$BomPs1 = 'd:\RPC\ops\station-bin\_agent-cli-bom.ps1',
  [string]$Card1 = 'C:\Users\Peng\AppData\Local\Temp\agent-cli-6957fd278fd14eeab35b780e35f95eef\split-o26-split-fanout\shard1.md',
  [string]$Card2 = 'C:\Users\Peng\AppData\Local\Temp\agent-cli-6957fd278fd14eeab35b780e35f95eef\split-o26-split-fanout\shard2.md',
  [string]$Host1 = 'scott-lau-NEX.local',
  [string]$Host2 = 'scott-lau-GTR-Pro.local'
)
function Run-One([string]$card,[string]$HostArg,[int]$n){
  $w=[System.Diagnostics.Stopwatch]::StartNew()
  & powershell -NoProfile -ExecutionPolicy Bypass -File $BomPs1 'task' 'paper' -card $card -RemoteHost $HostArg
  $rc=$LASTEXITCODE
  $w.Stop()
  Write-Host ("SERIAL[$n] rc=$rc wall_ms=$($w.ElapsedMilliseconds) card=$card host=$HostArg")
  return $w.ElapsedMilliseconds
}
$t0=[DateTime]::UtcNow
$r1=Run-One $Card1 $Host1 1
$r2=Run-One $Card2 $Host2 2
$tot=([DateTime]::UtcNow-$t0).TotalMilliseconds
Write-Host "SERIAL_TOTAL_MS=$([int]$tot) (part1=$r1 part2=$r2)"