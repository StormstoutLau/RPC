# a4/parallel_download.ps1 — Range 分段并行下载 (绕过单连接限速)
# 用法: powershell -File parallel_download.ps1 <url> <out> <chunks>
param(
    [Parameter(Mandatory=$true)][string]$Url,
    [Parameter(Mandatory=$true)][string]$OutFile,
    [Parameter(Mandatory=$true)][int]$Chunks = 12
)
$ErrorActionPreference = 'Stop'
# 1. 取总大小 (带重试)
$size = 0
for ($try = 1; $try -le 5; $try++) {
    $resp = curl.exe -sIL $Url | Select-String -Pattern 'content-length'
    $m = "$resp" | Select-String -Pattern '(\d{5,})' -AllMatches
    if ($m) {
        $size = [int64]($m.Matches[-1].Value)
        if ($size -gt 0) { break }
    }
    Write-Host "HEAD attempt $try failed, retrying..."
    Start-Sleep -Seconds 3
}
if ($size -le 0) { throw "BAD_SIZE after 5 tries (last resp: $resp)" }
Write-Host "TOTAL_SIZE=$size ($([math]::Round($size/1MB)) MB), chunks=$Chunks"
# 2. 分段并行
$chunkSize = [math]::Ceiling($size / $Chunks)
$jobs = @()
for ($i = 0; $i -lt $Chunks; $i++) {
    $start = $i * $chunkSize
    $end = [math]::Min(($i + 1) * $chunkSize - 1, $size - 1)
    if ($start -gt $end) { break }
    $segFile = "$OutFile.seg$i"
    if ((Test-Path $segFile) -and ((Get-Item $segFile).Length -eq ($end - $start + 1))) {
        Write-Host "seg$i already complete, skip"
        continue
    }
    $jobs += Start-Job -Name "seg$i" -ScriptBlock {
        curl.exe -sL --retry 8 --retry-delay 3 --retry-all-errors -r "$($args[0])-$($args[1])" -o "$($args[2])" "$($args[3])"
        exit $LASTEXITCODE
    } -ArgumentList $start, $end, $segFile, $Url
    Write-Host "seg$i : $start-$end ($([math]::Round(($end-$start+1)/1MB)) MB) launched"
}
if ($jobs.Count -gt 0) {
    $jobs | Wait-Job | Out-Null
    $failed = @($jobs | Where-Object { $_.State -eq 'Failed' })
    $jobs | Remove-Job -Force
    if ($failed.Count -gt 0) { throw "SEGMENTS_FAILED: $($failed.Count)" }
}
# 3. 校验每段大小
$nSegs = 0
for ($i = 0; $i -lt $Chunks; $i++) {
    $segFile = "$OutFile.seg$i"
    if (-not (Test-Path $segFile)) { continue }
    $nSegs++
    $expected = [math]::Min(($i + 1) * $chunkSize, $size) - ($i * $chunkSize)
    $actual = (Get-Item $segFile).Length
    if ($actual -ne $expected) {
        throw "SEG$i SIZE MISMATCH: expect=$expected actual=$actual"
    }
}
Write-Host "All $nSegs segments verified, concatenating..."
# 4. 流式拼接
$outStream = [System.IO.File]::Create($OutFile)
try {
    for ($i = 0; $i -lt $nSegs; $i++) {
        $inStream = [System.IO.File]::OpenRead("$OutFile.seg$i")
        try { $inStream.CopyTo($outStream) } finally { $inStream.Close() }
    }
} finally { $outStream.Close() }
$finalSize = (Get-Item $OutFile).Length
if ($finalSize -ne $size) { throw "FINAL SIZE MISMATCH: expect=$size actual=$finalSize" }
# 5. 清理段文件
for ($i = 0; $i -lt $nSegs; $i++) { Remove-Item "$OutFile.seg$i" -Force }
Write-Host "OK: $OutFile ($([math]::Round($finalSize/1MB)) MB) DOWNLOAD_COMPLETE"
