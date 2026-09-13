# 临时验证: REPO_ROOT 公式 + goldenBlock heredoc 转义（M2/M3 关键易错点）
$cli = 'd:\RPC\ops\station-bin\agent-cli.ps1'
# 1) REPO_ROOT
$PSScriptRoot = 'd:\RPC\ops\station-bin'
$repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Write-Host "REPO_ROOT=$repo  expect=d:\RPC  match=$($repo -eq 'd:\RPC')"

# 2) goldenBlock 字面量模拟（与 agent-cli.ps1 内逐字一致）
$goldenSha = 'abc123'
$goldenBase = 'path_guard_golden.py'
$goldenCmdB64 = 'eHl6'
$goldenBlock = @"
GOLDEN_ACTIVE=1
GOLDEN_SHA="$goldenSha"
GOLDEN_BASE="$goldenBase"
GOLDEN_CMD_B64="$goldenCmdB64"
echo "`$GOLDEN_SHA  `$W/.golden/`$GOLDEN_BASE" | sha256sum -c >/dev/null 2>&1
TAMPER_RC=`$?
if [ `$TAMPER_RC -ne 0 ]; then
  echo "GOLDEN_TAMPERED"
  ACCEPT_GOLDEN_OK=0
else
  echo "`$GOLDEN_CMD_B64" | base64 -d > "`$W/out/.golden-cmd.txt"
  ( cd "`$W" && eval "`$(cat "`$W/out/.golden-cmd.txt")" ) > "`$W/out/.accept-golden-output.txt" 2>&1
  GOLDEN_RC=`$?
  [ `$GOLDEN_RC -ne 0 ] && { echo "GOLDEN_FAIL rc=`$GOLDEN_RC"; ACCEPT_GOLDEN_OK=0; }
fi
echo "ACCEPT_GOLDEN_OK=`$ACCEPT_GOLDEN_OK"
"@
$goldenBlock | Set-Content "$env:TEMP\golden-block-check.sh" -Encoding ascii -NoNewline:$false
Write-Host "--- goldenBlock rendered ---"
$goldenBlock
# 3) 校验渲染后无 PS 插值泄漏: 不应含 $goldenSha 字样（应字面量 abc123 已入）
$generated = Get-Content "$env:TEMP\golden-block-check.sh" -Raw
Write-Host "shows literal sha: $($generated -match 'GOLDEN_SHA="abc123"')"