#!/usr/bin/env pwsh
<#
check_llama_version.ps1 — 三站 A/B/C llama.cpp 引擎版本一致性巡检（主控站 PowerShell 版）
依据: spec/vulkan-version-control/IMPLEMENTATION.md §4.3 + bash 版 ops/check_llama_version.sh
用法: powershell -File check_llama_version.ps1 [-Deep]
退出: 0 一致 / 1 不一致 / 2 SSH 不可达
指纹: <symlink 目标>|<version>|<commit>|<rpc_protocol>|<md5ok>
#>
param([switch]$Deep)

$Hosts = @(
  'scott-lau@scott-lau-GTR-Pro.local',  # B (master)
  'scott-lau@scott-lau-NEX.local',      # A
  'scott-lau@192.168.1.24'              # C (WiFi 动态 IP)
)

function Get-Fingerprint([string]$h) {
  $cmd = @'
D=/opt/llama.cpp
L=$(readlink "$D" 2>/dev/null || echo NO_SYMLINK)
M=$(readlink -f "$D")/MANIFEST
V=$(grep "^version" "$M" 2>/dev/null | cut -d= -f2 | tr -d " " || echo NO_MANIFEST)
C=$(grep "^commit" "$M" 2>/dev/null | cut -d= -f2 | tr -d " " || echo "?")
R=$(grep "^rpc_protocol" "$M" 2>/dev/null | cut -d= -f2 | tr -d " " || echo "?")
MD=$(cd "$(readlink -f "$D")" 2>/dev/null && tail -n +10 MANIFEST 2>/dev/null | md5sum -c 2>&1 | grep -c "成功" || echo 0)
echo "$L|$V|$C|$R|md5ok=$MD"
'@
  try {
    $out = ssh -o ConnectTimeout=8 -o BatchMode=yes $h $cmd 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $out) { return $null }
    return ($out -join ' ').Trim()
  } catch { return $null }
}

$fp = @{}
$okAll = $true
foreach ($h in $Hosts) {
  $f = Get-Fingerprint $h
  if (-not $f) { Write-Host "❌ $h SSH 不可达"; $okAll = $false; continue }
  $fp[$h] = $f
  Write-Host "$h → $f"
}
if (-not ($Hosts | Where-Object { $fp.ContainsKey($_) }).Count -gt 0) { exit 2 }
if (-not $okAll) { exit 2 }

# 指纹比对（前 4 段）
$base = ($fp[$Hosts[0]] -split '\|')[0..3] -join '|'
$mismatch = $false
foreach ($h in $Hosts) {
  if (-not $fp.ContainsKey($h)) { continue }
  $k = ($fp[$h] -split '\|')[0..3] -join '|'
  if ($k -ne $base) { Write-Host "❌ 不一致: $h = $k vs base = $base"; $mismatch = $true }
}
if ($mismatch) { exit 1 }
Write-Host "✅ 三站指纹一致: $base"

if ($Deep) {
  Write-Host "== 深度模式: 三站文件集 md5 比对 =="
  $hash = @{}
  foreach ($h in $Hosts) {
    $hostk = [System.BitConverter]::ToString([System.Security.Cryptography.MD5]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($h))).Replace('-','').Substring(0,8).ToLower()
    $fs = ssh -o ConnectTimeout=8 -o BatchMode=yes $h 'cd /opt/llama.cpp && md5sum llama-* ggml-rpc-server libggml*.so* libllama*.so* libmtmd*.so* 2>/dev/null | sort' 2>$null
    $tmp = Join-Path $env:TEMP "md5_${hostk}.txt"
    $fs | Set-Content -Encoding utf8 $tmp
    $hash[$h] = $tmp
    Write-Host "$h → $(Get-Item $tmp | Select-Object -ExpandProperty Length) bytes, $(($fs | Measure-Object).Count) 文件"
  }
  $ref = $hash[$Hosts[0]]
  foreach ($h in $Hosts[1..($Hosts.Count-1)]) {
    $d = Compare-Object (Get-Content $ref) (Get-Content $hash[$h])
    if ($d) {
      Write-Host "❌ $h 与 ${Hosts[0]} 文件集不一致"
      $d | Select-Object -First 10 | ForEach-Object { Write-Host "   $($_.SideIndicator) $($_.InputObject)" }
      $mismatch = $true
    }
  }
  if (-not $mismatch) { Write-Host "✅ 三站文件集 md5 完全一致" }
}
if ($mismatch) { exit 1 }
exit 0