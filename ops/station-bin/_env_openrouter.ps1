# ============================================================================
# _env_openrouter.ps1 - OpenRouter egress key injection (ADR-0003)
# 用法: . d:\RPC\ops\station-bin\_env_openrouter.ps1
# 作用: 从 secrets/openrouter.key(+可选 secrets/openrouter.conf) 读配置, 注入会话 env:
#   - REVIEW_COMMERCIAL_BASE/KEY/MODEL  -> agent-cli judge 'commercial' 槽 (JUDGE_TABLE type=http)
#   - OPENROUTER_API_KEY / OPENROUTER_BASE_URL -> research-lookup skill (parallel-cli)
# 设计铁律: key 单一真值在 secrets/, 本脚本只读不写不硬编码; 绝不回显完整 key。
# ============================================================================
$ErrorActionPreference = 'Stop'

if ($MyInvocation.InvocationName -ne '.') {
    Write-Warning '_env_openrouter.ps1 建议以 dot-source 加载: . <path>'
}

# repo root: 本文件在 ops/station-bin/ -> 上两级 = d:\RPC
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$keyPath  = Join-Path $repoRoot 'secrets\openrouter.key'
$cfgPath  = Join-Path $repoRoot 'secrets\openrouter.conf'

if (-not (Test-Path $keyPath)) {
    throw "OPENROUTER_KEY_MISSING: 未找到 $keyPath (请写入 API key, 见 ADR-0003)"
}
$key = (Get-Content $keyPath -Raw).Trim()
if (-not $key -or $key -match 'PASTE_YOUR') {
    throw "OPENROUTER_KEY_PLACEHOLDER: $keyPath 仍是占位符/空, 请填入真实 key"
}

# 默认值 (可被 secrets/openrouter.conf 覆盖)
$base  = 'https://openrouter.ai/api/v1'
$model = ''
if (Test-Path $cfgPath) {
    foreach ($line in (Get-Content $cfgPath)) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith('#')) { continue }
        if ($t -match '^\s*([A-Za-z_]+)\s*=\s*(.*)$') {
            $k = $matches[1].ToLower(); $v = $matches[2].Trim()
            if ($k -eq 'base'  -and $v) { $base  = $v }
            if ($k -eq 'model' -and $v) { $model = $v }
        }
    }
}

# --- 注入 (进程级 env, 仅当前会话) ---
$env:REVIEW_COMMERCIAL_BASE = $base
$env:REVIEW_COMMERCIAL_KEY  = $key
if ($model) { $env:REVIEW_COMMERCIAL_MODEL = $model }
elseif (-not $env:REVIEW_COMMERCIAL_MODEL) {
    Write-Warning 'REVIEW_COMMERCIAL_MODEL 未设 (conf 为空且 env 为空) - judge commercial 调用前需显式指定模型'
}

$env:OPENROUTER_API_KEY  = $key
$env:OPENROUTER_BASE_URL = $base

$tail = if ($key.Length -ge 4) { $key.Substring($key.Length - 4) } else { '****' }
Write-Host "OPENROUTER_ENV_OK base=$base model=$($env:REVIEW_COMMERCIAL_MODEL) key=****$tail"