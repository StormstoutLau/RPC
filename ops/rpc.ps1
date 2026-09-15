# ============================================================================
# rpc 统一入口 (P0)
# 目标: 人只需要记一条命令 —— `ops\rpc.ps1 check`
# 设计背景见 docs/research/2026-09-14_暴露问题调研.md (CI/CD 与流水线分析)
#
#   ops\rpc.ps1 check              # 全量校验 (明文 + 语法 + 真值登记 + 端口分配 + 插件同构 + 三站实况)
#   ops\rpc.ps1 check -Quick       # 本地快检 (pre-commit 用)
#   ops\rpc.ps1 check -List        # 只列断言清单
#   ops\rpc.ps1 install-hooks      # 安装/更新 pre-commit + pre-push 门禁 (幂等)
# ============================================================================
[CmdletBinding()]
param(
    [Parameter(Position = 0)][string]$Command = 'check',
    [switch]$Quick,
    [string]$Only = '',
    [switch]$List
)
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path $PSScriptRoot -Parent

function Get-PythonCandidates {
    $list = @()
    foreach ($c in @('python', 'py')) {
        $cmd = Get-Command $c -ErrorAction SilentlyContinue
        if ($cmd) { $list += $cmd.Source }
    }
    foreach ($p in @(
            (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
            (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'),
            'C:\Python312\python.exe')) {
        if (Test-Path $p) { $list += $p }
    }
    return ($list | Select-Object -Unique)
}

# 三站比对断言依赖 paramiko, 而机器上可能存在多个 Python。故在候选里挑第一个
# 能 import paramiko 的; 都没有则退化为第一个, 并把 stations 断言降级为 WARN。
$script:Candidates = Get-PythonCandidates
$script:Py = $script:Candidates | Select-Object -First 1
$script:PyHasParamiko = $false
# 注意: 原生命令的 stderr 在 $ErrorActionPreference='Stop' 下会被当成终止错误,
# 故探测期间临时降级, 否则"缺 paramiko"会直接把脚本打断而不是继续换解释器。
$prevEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
foreach ($c in $script:Candidates) {
    & $c -c "import paramiko" 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $script:Py = $c; $script:PyHasParamiko = $true; break }
}
$ErrorActionPreference = $prevEap

function Show-Usage {
    Write-Host @'
rpc 统一入口 (P0)

  ops\rpc.ps1 check             全量校验 (明文扫描 + 语法 + 真值登记 + 端口分配 + 插件同构 + 三站实况)
  ops\rpc.ps1 check -Quick      本地快检 (pre-commit 门禁用, 不含三站比对)
  ops\rpc.ps1 check -Only <ids> 只跑指定断言, 逗号分隔 (见 -List)
  ops\rpc.ps1 check -List       列出全部断言
  ops\rpc.ps1 install-hooks     安装/更新 pre-commit + pre-push 门禁 (幂等, 旧文件存 .bak)

退出码: 0=PASS/WARN  1=有 FAIL (阻断)  2=用法或环境错误
'@
}

function Install-HookEntry {
    # 生成单个 git hook。pre-commit 跑 quick; pre-push 跑全量(含三站比对)。
    param([string]$Name, [string]$RunArgs, [string]$Label)
    $hook = Join-Path $RepoRoot (".git\hooks\$Name")
    if (Test-Path $hook) {
        $existing = Get-Content $hook -Raw -ErrorAction SilentlyContinue
        if ($existing -notmatch 'rpc 统一校验门禁') {
            Copy-Item $hook "$hook.bak" -Force
            Write-Host "  已备份原 hook -> $Name.bak"
        }
    }
    $pyUnix = $script:Py -replace '\\', '/'
    $lines = @(
        '#!/bin/sh',
        "# rpc 统一校验门禁 ($Name) — 由 ops/rpc.ps1 install-hooks 生成, 请勿手改",
        '# pre-commit = 本地快检; pre-push = 全量 (明文+语法+三站配置比对+站上实况对账)',
        'ROOT=$(git rev-parse --show-toplevel) || exit 0',
        'cd "$ROOT" || exit 0',
        "PY='$pyUnix'",
        'if [ ! -f "$PY" ]; then',
        '  echo "[rpc-check] 未找到 Python ($PY), 门禁放行 — 见 ops/rpc.ps1 install-hooks"',
        '  exit 0',
        'fi',
        "exec `"`$PY`" ops/rpc_check.py $RunArgs"
    )
    $text = ($lines -join "`n") + "`n"
    [System.IO.File]::WriteAllText($hook, $text, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "  已安装 $Name 门禁" -ForegroundColor Green
    Write-Host "    hook     : $hook"
    Write-Host "    生效范围 : $Label"
}

function Remove-HookEntry {
    param([string]$Name)
    $hook = Join-Path $RepoRoot ".git\hooks\$Name"
    if (Test-Path $hook) {
        $existing = Get-Content $hook -Raw -ErrorAction SilentlyContinue
        if ($existing -match 'rpc 统一校验门禁') {
            Remove-Item $hook -Force
            Write-Host "  已移除 rpc $Name 门禁" -ForegroundColor Green
        }
        else {
            Write-Host "  $Name 非 rpc 生成, 未动" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "  无 $Name, 无需处理"
    }
}

switch ($Command.ToLower()) {
    'check' {
        if (-not $script:Py) { Write-Host 'rpc: 未找到 Python (需 3.8+)' -ForegroundColor Red; exit 2 }
        if (-not $script:PyHasParamiko) {
            Write-Host "  [提示] 选中解释器无 paramiko: $script:Py" -ForegroundColor Yellow
            Write-Host "         stations(三站配置比对)断言将降级为 WARN" -ForegroundColor Yellow
        }
        $argv = @((Join-Path $PSScriptRoot 'rpc_check.py'))
        if ($Quick) { $argv += '--quick' }
        if ($Only) { $argv += @('--only', $Only) }
        if ($List) { $argv += '--list' }
        & $script:Py @argv
        exit $LASTEXITCODE
    }

    'install-hooks' {
        $hookDir = Join-Path $RepoRoot '.git\hooks'
        if (-not (Test-Path $hookDir)) { Write-Host "rpc: 未找到 $hookDir" -ForegroundColor Red; exit 2 }
        if (-not $script:Py) { Write-Host 'rpc: 未找到 Python, 无法生成门禁' -ForegroundColor Red; exit 2 }
        Install-HookEntry -Name 'pre-commit' -RunArgs '--quick' -Label 'git commit (本地快检: 明文+语法)'
        Install-HookEntry -Name 'pre-push'   -RunArgs ''       -Label 'git push (全量: 明文+语法+真值登记+端口分配+插件同构+三站实况对账)'
        Write-Host '已完成; 全量手动校验: ops\rpc.ps1 check' -ForegroundColor Green
        exit 0
    }

    'uninstall-hooks' {
        Remove-HookEntry -Name 'pre-commit'
        Remove-HookEntry -Name 'pre-push'
        exit 0
    }

    default {
        Show-Usage
        exit 2
    }
}
