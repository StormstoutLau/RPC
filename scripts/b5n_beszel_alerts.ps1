# B5n: Beszel 告警配置 (POST /api/beszel/user-alerts)
# 官方 API: name/value/min/systems; Temperature 取全传感器 max (无传感器级区分)
# 告警集: Temperature 85C (5min 窗口防瞬时峰值) / Status 掉线 / Disk 90%
$ErrorActionPreference = 'Stop'
$HUB = 'http://192.168.1.15:8090'

$auth = Invoke-RestMethod -Method Post -Uri "$HUB/api/collections/users/auth-with-password" `
  -ContentType 'application/json' `
  -Body '{"identity":"peng.liu.john@gmail.com","password":"Beszel-49dc2e75"}'
$H = @{ Authorization = "Bearer $($auth.token)" }
$A = '6qhew01z4lk7y0k'   # NEX
$B = 'gqyb73pjkjd1lla'   # GTR-Pro

$alerts = @(
  @{ name = 'Temperature'; value = 85; min = 5;  systems = @($A, $B) },
  @{ name = 'Status';                          systems = @($A, $B) },
  @{ name = 'Disk';        value = 90; min = 10; systems = @($A, $B) }
)

foreach ($al in $alerts) {
  $body = $al | ConvertTo-Json -Compress
  try {
    $r = Invoke-RestMethod -Method Post -Uri "$HUB/api/beszel/user-alerts" -Headers $H -ContentType 'application/json' -Body $body
    Write-Output "OK   [$($al.name)] $($r | ConvertTo-Json -Compress -Depth 5)"
  } catch {
    Write-Output "FAIL [$($al.name)] $($_.ErrorDetails.Message)"
  }
}

# 验证: 读回 alert 记录
$recs = Invoke-RestMethod -Uri "$HUB/api/collections/alerts/records?perPage=50" -Headers $H
Write-Output "--- alerts on hub: $($recs.items.Count) 条 ---"
$recs.items | ForEach-Object {
  $sysNames = ($_.system | ForEach-Object { if ($_ -is [string]) { $_.Substring(0,8) } else { '(expand)' } }) -join ','
  Write-Output "  $($_.name) value=$($_.value) min=$($_.min) system=$sysNames"
}
