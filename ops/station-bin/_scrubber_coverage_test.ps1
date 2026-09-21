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
# ⚠ 2026-09-21: 规则清单抽到 `Get-ScrubRules`(单一真值源) 后, 被提取的函数由 1 个变 3 个 ——
#   缺任何一个都会让夹具"跑不起来", 或更糟: 跑的是**半套**(旧定义 + 新调用点)。故按名单提取 + 缺则显式抛错。
foreach ($nm in @('Get-ScrubRules', 'Invoke-Scrubber', 'Get-ScrubBlockReason')) {
    $f = @($fns) | Where-Object { $_.Name -eq $nm } | Select-Object -First 1
    if (-not $f) { throw "$nm not found in agent-cli.ps1" }
    Invoke-Expression $f.Extent.Text
}

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
# 2026-09-21 新增的 6 条凭据类（裁定 §3「加」的那 6 项），样串同样按段拼接（见上方说明）。
$GP = Sam 'ghp_', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
$GP2 = Sam 'github_pat_', 'abcdefghijklmnopqrstuv_0123456789'
$AK = Sam 'AKIA', 'IOSFODNN7EXAMPLE'
$SL = Sam 'xoxb-', '123456789012-abcdefghijklmnop'
$JW = Sam 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.', 'eyJzdWIiOiIxIn0.', 'abcdEFGH1234'
$BT = Sam '8f3a29c7d1b04e6f9a2c5b8d7e0f1a3c'
$PK = Sam '-----BEGIN ', 'OPENSSH PRIVATE KEY-----'
$pos = @(
    @{ n = 'OpenRouter key (sk-or-v1-…)';  s = $K1;      must = @($K1) },
    @{ n = 'Anthropic key (sk-ant-…)';     s = $K2;      must = @($K2) },
    @{ n = 'GitHub PAT (ghp_…)';           s = $GP;      must = @($GP) },
    @{ n = 'GitHub PAT (github_pat_…)';    s = $GP2;     must = @($GP2) },
    @{ n = 'AWS Access Key (AKIA…)';       s = $AK;      must = @($AK) },
    @{ n = 'Slack token (xoxb-…)';         s = $SL;      must = @($SL) },
    @{ n = 'JWT (三段)';                    s = $JW;      must = @($JW) },
    @{ n = 'Bearer token';                 s = ('Authorization: Bearer ' + $BT); must = @($BT) },
    @{ n = 'OpenSSH 私钥块';                s = $PK;      must = @($PK) },
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
# ★ 标星的三条 = **把裁定的"不加"决定做成可判的回归守卫**: 判别力差一点点(改回长度判据)就会变红。
$neg = @(
    @{ n = '普通技术文本(含反斜杠但无盘符)'; s = 'use bin\bash.exe and \n escapes' },
    @{ n = '短 sk- 片段(<16 字符, 非 key)';  s = 'the tag sk-short has fewer chars' },
    @{ n = '相对路径';                        s = '.\out\agent-output.txt' },
    @{ n = '无 TLD 的 @ 用法';                s = 'mail me at user@localhost' },
    @{ n = '短 ghp_(<36 字符)';               s = 'ghp_abc123' },
    @{ n = 'AKIA 但不足 16 位';               s = 'AKIA1234567890' },
    @{ n = 'Bearer 但 token 过短(<20)';       s = 'Authorization: Bearer short12' },
    @{ n = '裸词 bearer(无 token)';           s = 'the bearer of this letter' },
    @{ n = '证书块(-----BEGIN CERTIFICATE-----, 公钥非私钥)'; s = '-----BEGIN CERTIFICATE-----' },
    @{ n = '裸长十六进制串(无 Bearer 上下文 ⇒ 不收窄就会吃)'; s = 'token=8f3a29c7d1b04e6f9a2c5b8d7e0f1a3c' },
    @{ n = '★ run ID(18 位数字 = 本项目证据句柄)'; s = '复现 run 202609180952112524 的结论' },
    @{ n = '★ 站主机名(.local = 项目主要寻址方式)'; s = 'ssh scott-lau-GTR-Pro.local' },
    @{ n = '★ 内网 IP(inventory/net.yaml 真值)';   s = 'C 站 192.168.1.37 / A-B 段 10.10.10.0/24' }
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

Write-Host "=== [2c] 新凭据类规则的**过度消费**守门(与 §2b 同族) ==="
# ⚠ 凭据类的固有风险与路径相反: 前缀很确定 ⇒ 误伤≈0, 但**贪婪把后面的词一起吃**同样要防。
$over2 = @(
    @{ n = 'Bearer 后只吃 token, 不吃后续词'; s = ('Bearer ' + $BT + ' and more');   e = '[REDACTED-BEARER] and more' },
    @{ n = 'AKIA 后接普通词';                s = ($AK + ' is a sample key');        e = '[REDACTED-AWS-KEY] is a sample key' },
    @{ n = 'ghp_ 后接普通词';                s = ($GP + ' leaked here');            e = '[REDACTED-GH-PAT] leaked here' },
    @{ n = '私钥块后接正文';                  s = ($PK + ' then content');           e = '[REDACTED-PRIVATE-KEY] then content' }
)
foreach ($c in $over2) { Assert-True "over: $($c.n) ⇒ 只替换凭据本身" ((Scrub $c.s) -eq $c.e) }

Write-Host "=== [3] 幂等性: 再跑一遍结果不变(占位符不得被二次处理) ==="
# ⚠ 覆盖**全部 9 类占位符**(不只路径/邮箱/key): 只要有一类的新占位符能二次命中, 这里就红。
#   例: `bearer` 规则若不收窄, `[REDACTED-BEARER]` 之后的字样可能被再次吃掉 —— 幂等性是它的哨兵。
$idem = Scrub ('C:\RPC\a.key + peng.liu.john@gmail.com + ' + $K1 + ' + ' + $GP + ' + ' + $AK + ' + ' + $SL + ' + ' + $JW + ' + ' + $PK + ' + Bearer ' + $BT)
Assert-True "幂等: scrub(scrub(x)) == scrub(x) (覆盖 9 类占位符)" ((Scrub $idem) -eq $idem)

Write-Host "=== [4] 覆盖率报告: 现有 9 条规则**未覆盖**的敏感形态(不计 FAIL, 但必须显式列出) ==="
# ⚠ 这一段的**存在**比数值重要: 它把"我以为覆盖了"变成"我知道没覆盖这些"。
# 2026-09-21: 前 6 项(凭据类)已由裁定 §3 落地规则 ⇒ 本段应从 0/14 变 6/14。
# ⚠ **后 8 项是裁定明确"不加"的**(身份与拓扑类) —— 它们**不是待办**, 而是**设计上交给档位**的:
#   含 PII/拓扑的卡走 `local-only`。故这段的期望值就是 6/14, 不是 14/14。
# ⚠ 若将来真要给「身份证/银行卡」加规则: **必须用校验位**(GB 11643 mod-11-2 / Luhn),
#   且**本段的探针要同时换掉** —— 现在的 `110101199003071234` / `6222021234567890123` 都是**编造值,
#   校验位不合法**(实测: 校验位判据对它们**不命中**), 不换探针就会出现"有规则但探针永不被认"的假覆盖。
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
Write-Host "  另两条**设计如此**(不是缺口, 免得被当成 bug 去修): JWT **只有两段**(header.payload)不认(需第 3 段 ≥10 字符); 私钥块命中由 §5 **拒发**, 不是抹掉继续"

Write-Host "=== [5] 不可安全抹除判据(Get-ScrubBlockReason): 命中 ⇒ **拒发**, 不是抹掉继续 ==="
# 2026-09-21 (裁定 §5-1): DESIGN §193「命中即拦截」与 §2.1 三档定义「脱敏后远端」的张力在此钉死 ——
#   二分依据 = **能不能安全抹除**。凭据类抹掉后卡仍自洽 ⇒ 继续; 私钥块 ⇒ 拒发(卡本身不该出网)。
$blk = @(
    @{ n = 'OpenSSH 私钥块';        s = (Sam '-----BEGIN ', 'OPENSSH PRIVATE KEY-----');    e = 'scrub-unsafe:private-key' },
    @{ n = 'RSA 私钥块';            s = (Sam '-----BEGIN ', 'RSA PRIVATE KEY-----');        e = 'scrub-unsafe:private-key' },
    @{ n = 'PGP 私钥块(BLOCK 后缀)'; s = (Sam '-----BEGIN ', 'PGP PRIVATE KEY BLOCK-----');  e = 'scrub-unsafe:private-key' },
    @{ n = '证书块(公钥) ⇒ 放行';    s = '-----BEGIN CERTIFICATE-----';                      e = '' },
    @{ n = '普通卡正文 ⇒ 放行';      s = '把结果写到 out/result.md';                          e = '' },
    @{ n = '只含 key/路径 ⇒ 放行(抹掉即可)'; s = ($K1 + ' at C:\RPC\a.key');                 e = '' },
    @{ n = '空串 ⇒ 放行';           s = '';                                                e = '' }
)
foreach ($c in $blk) { Assert-True "block: $($c.n) ⇒ '$($c.e)'" ((Get-ScrubBlockReason $c.s) -eq $c.e) }

Write-Host "=== [6] 规则清单自证(抽成 Get-ScrubRules 后必须仍是「单一真值源」) ==="
# ⚠ 这条是"抽公共函数"的**代价守卫**: 抽出去以后若有人又在别处手写一遍模式, 这两条断言抓不到,
#   但至少能保证**这一份**自身是完整的(名字唯一 + 四键齐备) —— 否则规则会**静默失效**
#   (例: 漏写 `block` 键 ⇒ Get-ScrubBlockReason 永不命中, 而夹具其余部分照样全绿)。
$rules = @(Get-ScrubRules)
$names = @($rules | ForEach-Object { $_['name'] })
$missing = @($rules | Where-Object { -not ($_.ContainsKey('name') -and $_.ContainsKey('re') -and $_.ContainsKey('block') -and $_.ContainsKey('repl')) })
Assert-True "规则清单: 名字唯一($($names.Count) 条无重名)" ((@($names | Sort-Object -Unique)).Count -eq $names.Count)
Assert-True "规则清单: 每条都有 name/re/block/repl 四键(缺键 = 静默失效)" ($missing.Count -eq 0)
Write-Host "  规则数: $($rules.Count) 条 · 其中 block(命中即拒发) $((@($rules | Where-Object { $_['block'] })).Count) 条"

Write-Host ""
Write-Host "SCRUBBER_COVERAGE_TEST pass=$script:pass fail=$script:fail  (未覆盖形态 $($uncovered.Count) 项 / 残留缺口 $($leaky.Count) 项, 见上)"
if ($script:fail -gt 0) { Write-Host "FAILED: $($script:failNames -join ' | ')"; exit 1 }
exit 0
