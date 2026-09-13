$t=$null;$e=$null
$a=[System.Management.Automation.Language.Parser]::ParseInput([IO.File]::ReadAllText('d:\RPC\ops\station-bin\agent-cli.ps1',[Text.UTF8Encoding]::new($false)),[ref]$t,[ref]$e)
Write-Host ("parse errors: " + $e.Count)
if ($e.Count -gt 0) { $e | Select-Object -First 5 | ForEach-Object { Write-Host ("L" + $_.Extent.StartLineNumber + ": " + $_.Message) } }