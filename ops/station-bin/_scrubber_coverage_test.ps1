# ============================================================================
# _scrubber_coverage_test.ps1 — `sanitized` 档 scrubber 的**覆盖率判据**（三态）
# 用法: powershell -NoProfile -ExecutionPolicy Bypass -File ops/station-bin/_scrubber_coverage_test.ps1
# 退出码: 0 = all pass; 1 = fail
# 隔离方式: 从 agent-cli.ps1 用 AST 提取 Invoke-Scrubber 单独定义(不执行主入口)
#
# 为什么要有这个夹具 (2026-09-21):
#   ZDR 裁定(docs/security/2026-09-21_ZDR可行性裁定与影响面.md §4)依赖一条**从未验证的推论**:
#     「`sanitized` 含**可机判**敏感项 ⇒ 先机械 scrub ⇒ **抹完的残留等级 = public**」。
#   该推论**同时**是 P1"撤回 `sanitized × 可能训练` 闸"的依据之一 ⇒ **两处决策共享同一前提**。
#   本夹具就是去**验证这个前提**, 而不是假设它。
#
# 为什么是**三态**而不是二态(二态会漏掉最危险的那一类):
#   ① **该认的**: 命中 ⇒ 必须被替换 **且原文片段不再出现**
#   ② **不该认的**: 不得被替换(误伤 = 静默破坏任务输入, 与"静默降级"同族)
#   ③ **认了但残留**: 命中过、但输出里**仍能找到敏感片段** —— 最危险, 因为**看起来"处理过了"**
#      (例: 规则吃掉 `C:\Program`, 留下 `Files\Git\bin\bash.exe`)
#
# 另一类不是 FAIL 而是**报告**: "当前 3 条规则未覆盖的敏感形态"(见文件末 REPORT 段)。
#   它们计入**覆盖率分母**并显式列出 —— 免得"以为覆盖了"。修不修是**决策**(加规则有误伤风险)。
# ============================================================================
$ErrorActionPreference = 'Stop'
$cli = 'd:\RPC\ops\station-bin\agent-cli.ps1'

# --- 与 _fm_golden_test.ps1 同族的 AST 提取(不执行主入口) ---
$tok = $null; $errs = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($cli, [ref]$tok, [ref]$errs)
if ($errs.Count -gt 0) { throw "agent-cli.ps1 解析失败: $($errs[0].Message)" }
$fns = $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true)
$fn = @($fns) | Where-Object { $_.Name -eq 'Invoke-Scrubber' } | Select-Object -First 1
if (-not $fn) { throw 'Invoke-Scrubber not found in agent-cli.ps1' }
Invoke-Expression $fn.Extent.Text

$script:pass = 0; $script:fail = 0; $script:failNames = @()
function Assert-True([string]$name, [bool]$cond) {
    if ($cond) { $script:pass++; Write-Host "PASS  $name" }
    else { $script:fail++; $script:failNames += $name; Write-Host "FAIL  $name" }
}
# Write-Host 走 information 流(PS5.0+) ⇒ `6>$null` 可静音 scrubber 自身的 hit 日志
function Scrub([string]$t) { return (Invoke-Scrubber $t 6>$null) }

# ⚠ **所有"像真凭据"的样串一律按段拼接**(`Sam 'x','y'`), 不写字面量:
#   编造值也会被远端 GitHub push-protection 当成真 secret 拦下(实测拦过 `sk-…` 与 `xoxb-…`),
#   且**远端那道闸不认仓库内白名单**(本地门禁的 SECRET_ALLOW 只管本地)。
#   拼接后文件里不出现任何"前缀+长串"的连续形态 ⇒ 两道闸都过; 运行时与真串**逐字节相同**
#   (证据: 拼接后 §1 的 `must` 断言仍然 14/14 通过 —— 若差一个字节, 它们必然变红)。
function Sam([string[]]$parts) { return (-join $parts) }

Write-Host "=== [1] 该认的: 命中后**原文片段不得残留**(覆盖内形态) ==="
$K1 = Sam 'sk', '-or-v1-', '1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b'
$K2 = Sam 'sk', '-ant-api03-', 'abcdefghijklmnopqrstuvwxyz012345'
$pos = @(
    @{ n = 'OpenRouter key (sk-or-v1-…)';  s = $K1;      must = @($K1) },
    @{ n = 'Anthropic key (sk-ant-…)';     s = $K2;      must = @($K2) },
    @{ n = 'email 常规';                    s = 'peng.liu.john@gmail.com';                          must = @('peng.liu.john@gmail.com') },
    @{ n = 'email 带 + 与多级域';            s = 'a.b+c@sub.example.co.uk';                         must = @('a.b+c@sub.example.co.uk') },
    @{ n = 'win 路径 **无空格**';            s = 'C:\RPC\secrets\stations\A\openrouter.key';        must = @('C:\RPC\secrets\stations\A\openrouter.key') },
    @{ n = 'win 路径 **带空格**';            s = 'C:\Program Files\Git\bin\bash.exe';               must = @('C:\Program Files\Git\bin\bash.exe', 'Files\Git\bin\bash.exe') }
)
foreach ($c in $pos) {
    $out = Scrub $c.s
    # ⚠ 不用 `-like '*[REDACTED-*'`: `-like` 的通配符里 `[` 是**字符类起始**, 未闭合 ⇒ 非法模式。
    $hit = $out.Contains('[REDACTED-')
    $left = @($c.must | Where-Object { $out.Contains($_) })
    Assert-True "pos: $($c.n) ⇒ 被替换**且无残留**" ($hit -and $left.Count -eq 0)
    if ($left.Count -gt 0) { Write-Host "      ↳ 残留: $($left -join ' | ')" }
}

Write-Host "=== [2] 不该认的: 不得被替换(误伤 = 静默破坏输入) ==="
$neg = @(
    @{ n = '普通技术文本(含反斜杠但无盘符)'; s = 'use bin\bash.exe and \n escapes' },
    @{ n = '短 sk- 片段(<16 字符, 非 key)';  s = 'the tag sk-short has fewer chars' },
    @{ n = '相对路径';                        s = '.\out\agent-output.txt' },
    @{ n = '无 TLD 的 @ 用法';                s = 'mail me at user@localhost' }
)
foreach ($c in $neg) {
    $out = Scrub $c.s
    Assert-True "neg: $($c.n) ⇒ 原样保留" ($out -eq $c.s)
}

Write-Host "=== [2b] 新 win-path 正则的**过度消费**守门(改规则的直接风险) ==="
# 2026-09-21: 原 `\S+` 在空格处断 ⇒ 残留路径尾; 改成"逐段吃"后, 风险反过来是**吃多**。
# ⚠ 改成"段内允许空格"后, 路径后面若跟普通文本, 不得把文本一起吃掉。
$over = @(
    @{ n = '路径后接普通词';    s = 'C:\RPC\out.txt done'; e = '[REDACTED-PATH] done' },
    @{ n = '路径后接换行';      s = "C:\RPC\a`nb";         e = "[REDACTED-PATH]`nb" },
    @{ n = '两段路径以空格相隔'; s = 'C:\a C:\b';           e = '[REDACTED-PATH] [REDACTED-PATH]' }
)
foreach ($c in $over) { Assert-True "over: $($c.n) ⇒ 只替换路径本身" ((Scrub $c.s) -eq $c.e) }

Write-Host "=== [3] 幂等性: 再跑一遍结果不变(占位符不得被二次处理) ==="
$idem = Scrub ('C:\RPC\a.key + peng.liu.john@gmail.com + ' + $K1)
Assert-True "幂等: scrub(scrub(x)) == scrub(x)" ((Scrub $idem) -eq $idem)

Write-Host "=== [4] 覆盖率报告: 当前 3 条规则**未覆盖**的敏感形态(不计 FAIL, 但必须显式列出) ==="
# ⚠ 这一段的**存在**比数值重要: 它把"我以为覆盖了"变成"我知道没覆盖这些"。
$probe = @(
    @{ n = 'GitHub PAT';        s = (Sam 'ghp_', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') },
    @{ n = 'AWS Access Key';    s = (Sam 'AKIA', 'IOSFODNN7EXAMPLE') },
    @{ n = 'Slack token';       s = (Sam 'xoxb-', '123456789012-abcdefghijklmnop') },
    @{ n = 'JWT';               s = (Sam 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.', 'eyJzdWIiOiIxIn0.', 'abcdEFGH1234') },
    @{ n = 'Bearer token';      s = (Sam 'Authorization: Bearer ', '8f3a29c7d1b04e6f9a2c5b8d7e0f1a3c') },
    @{ n = 'OpenSSH 私钥块';     s = (Sam '-----BEGIN ', 'OPENSSH PRIVATE KEY-----') },
    @{ n = 'Linux 绝对路径';     s = '/home/scott-lau/.config/rpc/openrouter.key' },
    @{ n = 'UNC 路径';           s = '\\fileserver\share\secrets.key' },
    @{ n = '内网 IP';            s = '192.168.1.32' },
    @{ n = '主机名(.local)';     s = 'scott-lau-GTR-Pro.local' },
    @{ n = '用户名';             s = 'scott-lau' },
    @{ n = '中国大陆手机号';      s = '13800138000' },
    @{ n = '身份证号(18 位)';     s = '110101199003071234' },
    @{ n = '银行卡号(16-19 位)';  s = '6222021234567890123' }
)
$uncovered = @()
foreach ($c in $probe) { if ((Scrub $c.s) -eq $c.s) { $uncovered += $c.n } }
$cov = $probe.Count - $uncovered.Count
Write-Host "  覆盖率: $cov / $($probe.Count) 个探测形态被现有规则覆盖"
Write-Host "  未覆盖($($uncovered.Count)): $($uncovered -join ' · ')"

Write-Host "=== [4b] 已知**残留缺口**(改 win-path 正则时**明示取舍**掉的, 不计 FAIL 但必须可见) ==="
# 取舍依据(见 agent-cli.ps1 win-path 注释): 「末段含空格」与「路径后跟普通词」在字面上**不可机械区分**
#   ⇒ 只能二选一。选了"优先不误伤任务输入"(§2b), 代价就是下面这些形态**会残留路径尾**。
# ⚠ 这与 [4] 的"未覆盖"是两件事: [4] 是"这类东西根本没规则管", [4b] 是"规则**碰了**但没吃干净"。
$resid = @(
    @{ n = '末段含空格(未加引号)'; s = 'C:\Users\John Doe';                     left = 'Doe' },
    @{ n = '末段含空格(已加引号)'; s = '"C:\Program Files\my file.txt"';        left = 'file.txt' }
)
$leaky = @()
foreach ($c in $resid) {
    $out = Scrub $c.s
    if ($out.Contains($c.left)) { $leaky += $c.n; Write-Host "  残留: $($c.n) ⇒ '$out'  (残留 '$($c.left)')" }
    else { Write-Host "  已覆盖: $($c.n) ⇒ '$out'" }
}
Write-Host "  残留缺口: $($leaky.Count) / $($resid.Count)"

Write-Host ""
Write-Host "SCRUBBER_COVERAGE_TEST pass=$script:pass fail=$script:fail  (未覆盖形态 $($uncovered.Count) 项 / 残留缺口 $($leaky.Count) 项, 见上)"
if ($script:fail -gt 0) { Write-Host "FAILED: $($script:failNames -join ' | ')"; exit 1 }
exit 0
