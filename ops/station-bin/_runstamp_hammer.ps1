# O-63 并发自证：N 个**独立进程**同时调 `Get-UniqueRunStamp`，断言 ts **全不相同**。
# 为什么必须"多进程": check-then-act 的失效只在**跨进程同时**发生（同进程内是串行的 ⇒ 测不出来）。
# 为什么写进仓: 原缺陷（两 run 同 ts ⇒ 同 runDir）是**静默**的 —— 没有判据时只能靠事后发现"少一个 runDir"。
# 双向: `-SelfTest` 用**同一把锤子**打"旧实现(Test-Path 递增)"，**必须**检出撞车 ⇒ 证明本夹具真能看见撞车
#       （否则它只是装饰 —— 本仓"有测试 ≠ 有人在跑"的同族自律）。
# 用法: powershell -File ops\station-bin\_runstamp_hammer.ps1 [-N 12] [-SelfTest]
param([int]$N = 12, [switch]$Child, [switch]$Naive, [switch]$SelfTest, [string]$At = '')
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$outRoot = Join-Path $repo 'tmp\dogfood-ws\agent-out'
# ⚠ 脚本路径必须在**脚本作用域**取: `$MyInvocation.MyCommand.Path` 在**函数内**是 null（实测 ⇒ Start-Process
#   ArgumentList 校验失败）。`$PSCommandPath` 也一样只在脚本作用域可靠 ⇒ 固化进 $Script:SelfPath。
$Script:SelfPath = $PSCommandPath

function Get-Stamp {
    $src = Get-Content (Join-Path $repo 'ops\station-bin\agent-cli.ps1') -Raw
    $tokens = $null; $errors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseInput($src, [ref]$tokens, [ref]$errors)
    $fn = $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Get-UniqueRunStamp' }, $true)
    if (-not $fn) { return '' }
    Invoke-Expression $fn[0].Extent.Text
    return (Get-UniqueRunStamp -ProjOutRoot $outRoot)
}

function Get-NaiveStamp {
    # 负向对照: **故意**复刻被替换掉的旧实现（check-then-act）。不改产品代码, 只在夹具里当"靶子"。
    $t = [DateTime]::Now.ToString('yyyyMMddHHmmssffff')
    $n = [Int64]$t
    while (Test-Path (Join-Path $outRoot ([string]$n))) { $n++ }
    return [string]$n
}

# ⚠ PS 5.1: `if` **不是表达式** ⇒ 要包在 `$()` 里（`Write-Output (if …)` 会解析错，实测）。
# ⚠ **共同释放时刻（自旋屏障）**: 子进程的 PS 启动耗时本身有几百 ms 抖动 ⇒ 直接并发发起时 `[DateTime]::Now`
#   会自然散开,**撞不上时钟滴答**（实测: 负向对照拿到 12/12 唯一 ⇒ 判据"看起来"没用）。
#   必须先 spin 到同一时刻再取 ts —— 这才是产品里真实发生的形态（两个 run 走过**相同的**前置工作 ⇒ 同步）。
if ($Child) {
    if ($At) { $t = [DateTime]::Parse($At); while ([DateTime]::Now -lt $t) { } }
    Write-Output $(if ($Naive) { Get-NaiveStamp } else { Get-Stamp }); exit 0
}

function Invoke-Hammer {
    param([int]$Count, [string[]]$Extra)
    $self = $Script:SelfPath
    $tag = if ($Extra -contains '-Naive') { 'naive' } else { 'real' }
    # 共同释放时刻: 给子进程留 2.5s 启动余量 —— 启动再慢也在同一时刻被放出来。
    $at = (Get-Date).AddSeconds(2.5).ToString('yyyy-MM-ddTHH:mm:ss.fff')
    $procs = @()
    foreach ($i in 1..$Count) {
        $procs += Start-Process powershell -NoNewWindow -PassThru -RedirectStandardOutput (Join-Path $env:TEMP "stamp_$tag`_$i.out") `
            -ArgumentList (@('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $self, '-Child', '-At', $at) + $Extra)
    }
    $procs | ForEach-Object { $_.WaitForExit() }
    $got = @()
    foreach ($i in 1..$Count) {
        $p = Join-Path $env:TEMP "stamp_$tag`_$i.out"
        if (Test-Path $p) {
            $v = (Get-Content $p | Where-Object { $_ -match '^\d{18}$' } | Select-Object -First 1)
            if ($v) { $got += $v }
        }
        Remove-Item $p -Force -ErrorAction SilentlyContinue
    }
    return , $got
}

$real = Invoke-Hammer -Count $N -Extra @()
$uniq = @($real | Sort-Object -Unique).Count
$ok = ($real.Count -eq $N) -and ($uniq -eq $N)
Write-Output "RUNSTAMP_HAMMER n=$N got=$($real.Count) uniq=$uniq => $(if ($ok) { 'PASS' } else { 'FAIL(撞车!)' })"
if (-not $ok) { Write-Output ("dup: " + (($real | Group-Object | Where-Object { $_.Count -gt 1 } | ForEach-Object { $_.Name }) -join ',')) }

if ($SelfTest) {
    $nv = Invoke-Hammer -Count $N -Extra @('-Naive')
    $nuniq = @($nv | Sort-Object -Unique).Count
    # ⚠ 负向判据必须**同时**要求"跑满了" —— 否则 `got=0` 时 `0 < N` 会**假绿**（"什么都没跑"也算检出撞车）。
    #   实测踩过这一脚（第一版就是这么写的）⇒ 与产品代码里那些"因为什么都没判所以通过"的判据同族。
    $negOk = ($nv.Count -eq $N) -and ($nuniq -lt $N)
    Write-Output "RUNSTAMP_HAMMER_SELFTEST(旧实现) n=$N got=$($nv.Count) uniq=$nuniq => $(if ($negOk) { 'PASS(夹具能看见撞车)' } else { 'FAIL(夹具是装饰: 旧实现也没撞 / 或没跑满)' })"
    if (-not $negOk) { $ok = $false }
}

exit $(if ($ok) { 0 } else { 1 })
