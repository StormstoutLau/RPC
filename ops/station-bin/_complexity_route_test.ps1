# ============================================================================
# _complexity_route_test.ps1 - 6.4 complexity-route unit/integration test
# Exercises agent-cli.ps1 `route` dry-run via subprocess and asserts the PROFILE
# line against expected {profile,ctx,max_output,thinking,flavor,source}.
#   priority: taskType > complexity > default(reason)
#   context=0 sentinel -> model ctx cap; type=code/doc force thinking OFF.
#   NOTE: source kept ASCII-only for PS5.1 BOM safety (non-ASCII disallowed).
#   ASCII-only casts color-blind over prompt-language; messages left English.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File _complexity_route_test.ps1
# Exit: 0 all pass / 1 any fail
# ============================================================================
$ErrorActionPreference = 'Stop'
$cli = Join-Path $PSScriptRoot 'agent-cli.ps1'

# model ctx caps mirrored from agent-cli.ps1 Resolve-Profile $ctxMax (for sentinel resolution)
$ctxCaps = @{ 'nemotron'=131072; 'gpt-oss'=131072; 'lightning'=262144; 'ultra'=1000000; 'free-1m'=1000000 }

# test table: alias | cx | type | expected @{profile;ctx;max_output;thinking;flavor;source}
$cases = @(
    # taskType priority over complexity (code wins, thinking forced OFF)
    @{ alias='nemotron'; cx='standard'; type='code'; exp=@{profile='code'; ctx=8192; mo=8192; th='OFF'; fl='nothink'; src='type=code'} },
    # complexity=short alone
    @{ alias='nemotron'; cx='short';    type='';      exp=@{profile='short'; ctx=8192;  mo=2048; th='ON'; fl='think';  src='complexity=short'} },
    # complexity=standard alone -> reason
    @{ alias='nemotron'; cx='standard'; type='';      exp=@{profile='reason'; ctx=32768; mo=8192; th='ON'; fl='think'; src='complexity=standard'} },
    # type=doc with model having 131072 cap -> sentinel -> model ctx cap
    @{ alias='gpt-oss';  cx='';        type='doc';    exp=@{profile='doc'; ctx=131072; mo=8192; th='OFF'; fl='nothink'; src='type=doc'} },
    # type=doc on lightning (262144 cap) -> sentinel resolution checks cap not hardcoded
    @{ alias='lightning';cx='';        type='doc';    exp=@{profile='doc'; ctx=262144; mo=8192; th='OFF'; fl='nothink'; src='type=doc'} },
    # code + complexity=long conflict -> keep thinking OFF, ctx bumped to model cap
    @{ alias='nemotron'; cx='long';    type='code';   exp=@{profile='code'; ctx=131072; mo=8192; th='OFF'; fl='nothink'; src='type=code'} },
    # numeric -> short profile (2048 out)
    @{ alias='gpt-oss';  cx='';        type='numeric';exp=@{profile='short'; ctx=8192; mo=2048; th='ON'; fl='think'; src='type=numeric'} },
    # concept/reason -> reason profile
    @{ alias='nemotron'; cx='';        type='concept';exp=@{profile='reason'; ctx=32768; mo=8192; th='ON'; fl='think'; src='type=concept'} },
    # complexity=auto -> reason
    @{ alias='nemotron'; cx='auto';    type='';      exp=@{profile='reason'; ctx=32768; mo=8192; th='ON'; fl='think'; src='complexity=auto'} },
    # long complexity alone -> long profile, ctx=model cap, thinking ON, 16384 out
    @{ alias='nemotron'; cx='long';    type='';      exp=@{profile='long'; ctx=131072; mo=16384; th='ON'; fl='long'; src='complexity=long'} }
)

$fail = 0
$pass = 0
$wild = 0   # cases expecting NO PROFILE line (default: not printed unless explicit)

foreach ($c in $cases) {
    $args = @('route', '-Model', $c.alias)
    if ($c.cx)   { $args += '-Complexity', $c.cx }
    if ($c.type) { $args += '-TaskType', $c.type }
    $r = & powershell -NoProfile -ExecutionPolicy Bypass -File $cli @args 2>&1
    $pl = ($r | Where-Object { $_ -match '^PROFILE:' })
    if (-not $pl) {
        Write-Host "FAIL [$($c.alias) cx=$($c.cx) type=$($c.type)] no PROFILE line (route rc present?)"
        $fail++; continue
    }
    # parse PROFILE line fields (fixed format from agent-cli.ps1 Resolve-Profile):
    # PROFILE: profile=P ctx=C max_out=M thinking=T template=... reasoning=R flavor=F (source)
    $t = $pl -join ' '
    $m = [regex]::Match($t, 'profile=(\w+) ctx=(\d+) max_out=(\d+) thinking=(\w+) template=\S+ reasoning=\S+ flavor=(\w+) \(([^)]+)\)')
    if (-not $m.Success) { Write-Host "FAIL [$($c.alias) cx=$($c.cx) type=$($c.type)] unparsable: $t"; $fail++; continue }
    $got = @{ profile=$m.Groups[1].Value; ctx=[int]$m.Groups[2].Value; mo=[int]$m.Groups[3].Value;
              th=$m.Groups[4].Value; fl=$m.Groups[5].Value; src=$m.Groups[6].Value }
    $e = $c.exp
    $errs = @()
    if ($got.profile -ne $e.profile) { $errs += "profile got=$($got.profile) exp=$($e.profile)" }
    if ($got.ctx -ne $e.ctx)         { $errs += "ctx got=$($got.ctx) exp=$($e.ctx)" }
    if ($got.mo -ne $e.mo)           { $errs += "max_output got=$($got.mo) exp=$($e.mo)" }
    if ($got.th -ne $e.th)           { $errs += "thinking got=$($got.th) exp=$($e.th)" }
    if ($got.fl -ne $e.fl)           { $errs += "flavor got=$($got.fl) exp=$($e.fl)" }
    if ($got.src -ne $e.src)         { $errs += "source got=$($got.src) exp=$($e.src)" }
    if ($errs.Count -gt 0) { Write-Host "FAIL [$($c.alias) cx=$($c.cx) type=$($c.type)] :: $($errs -join '; ')"; $fail++ }
    else { $pass++; Write-Host "PASS [$($c.alias) cx=$($c.cx) type=$($c.type)] -> profile=$($got.profile) ctx=$($got.ctx) max_out=$($got.mo) thinking=$($got.th) flavor=$($got.fl) ($($got.src))" }
}

# case requiring NO PROFILE: default (no cx/type) should skip profile print by design
$r = & powershell -NoProfile -ExecutionPolicy Bypass -File $cli route -Model nemotron 2>&1
$pl = ($r | Where-Object { $_ -match '^PROFILE:' })
if ($pl) { Write-Host "FAIL [default] expected no PROFILE but got: $pl"; $fail++ }
else { $pass++; Write-Host "PASS [default] no PROFILE (route rc=0, dry-run requires explicit cx/type)" }

Write-Host ''
Write-Host "RESULT: $pass pass, $fail fail (of $($cases.Count + 1) assertions)"
if ($fail -gt 0) { exit 1 }
exit 0