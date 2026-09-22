# thin loader (O-11 L2 workaround): PS5.1 CP936 mis-parses BOM-less UTF-8 with non-ASCII strings;
# copy source to BOM'd temp file then -File it (agent-cli source is committed BOM-less by design).
#
# 2026-09-22 迁移（原在**仓库根** `d:\RPC\_o26_reverify_loader.ps1`）: 根级脚本不在 `scripts` 门禁
#   治理圈内（ADR-0004 D2/D3 只声明覆盖 `ops/`）⇒ 属"删除时才发现漏网"的空白。本轮按决策简报
#   （docs/2026-09-22_门禁口径决策简报…）**分类处置**：本工装与其卡片/附件是**互为引用的活体**
#   （原第 10 行硬编码绝对路径调用根级 `test-cards/`），故**不归档、而是整组迁入受治理位置**。
#
# ⚠ 路径**不再硬编码绝对路径** —— 改为**由脚本自身位置推算仓库根**：
#   硬编码 `d:\RPC\...` 正是"移动即断、且**不报警**"的形态（卡片已随之迁移，靠硬编码会静默指向
#   不存在的旧路径）。下方 `缺件即 throw` 是配套的 fail-closed 守卫（宁可不跑，也不拿空路径去跑）。
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent     # ops/station-bin -> ops -> <repo root>
$src  = Join-Path $repoRoot 'ops\station-bin\agent-cli.ps1'
$card = Join-Path $repoRoot 'spec\d6-agent-standard\test-cards\o26-split-fanout.md'
$att  = Join-Path $repoRoot 'ops\station-bin\attach-test\_o26_src.txt'
foreach ($p in @($src, $card, $att)) {
    if (-not (Test-Path -LiteralPath $p)) { throw "O26_LOADER: 缺件 $p (卡片/附件迁移后未同步?)" }
}
$tmp = Join-Path $env:TEMP ('o26-cli-' + [Guid]::NewGuid().ToString('N') + '.ps1')
$text = [System.IO.File]::ReadAllText($src, [System.Text.Encoding]::UTF8)
[System.IO.File]::WriteAllText($tmp, $text, (New-Object System.Text.UTF8Encoding $true))

$sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    & $tmp 'split' 'paper' -card $card -attach $att
} finally {
    $sw.Stop()
    Write-Host "LOADER_WALL_MS=$($sw.ElapsedMilliseconds)"
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
}