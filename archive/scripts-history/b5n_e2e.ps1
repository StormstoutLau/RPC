# B5n: 主控站端到端验证 — 带 key 调用 litellm 网关
$ErrorActionPreference = 'Stop'
$key = (Get-Content d:\RPC\secrets\litellm_master.key -Raw).Trim()
try {
  $r = Invoke-RestMethod -Uri 'http://192.168.1.15:4000/v1/models' -Headers @{ Authorization = "Bearer $key" } -TimeoutSec 10
  Write-Output "主控站带 key: OK — models: $(($r.data | ForEach-Object { $_.id }) -join ', ')"
} catch {
  Write-Output "主控站带 key: FAIL $($_.Exception.Message)"
}
try {
  Invoke-RestMethod -Uri 'http://192.168.1.15:4000/v1/models' -TimeoutSec 10 | Out-Null
  Write-Output "主控站无 key: 被放行 (异常!)"
} catch {
  Write-Output "主控站无 key: 被拒绝 ✓ ($($_.Exception.Response.StatusCode.value__)) "
}
