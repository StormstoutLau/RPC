# 20-scrub.ps1 —— `sanitized` 档的 scrubber 三函数（review-p2-split 8C；整段抽出，行为不变）
#   Get-ScrubRules（**规则单一真值源**）/ Invoke-Scrubber（抹）/ Get-ScrubBlockReason（拒）
# ⚠ 规则清单只在上面的 `Get-ScrubRules` 里；其余两处**派生**（同族漂移 = 本仓头号失败形态）。
#   覆盖率夹具: ops/station-bin/_scrubber_coverage_test.ps1（同法按名 AST 提取）。
# ⚠ 由入口按 `$Script:AGENT_CLI_LIBS` 顺序 dot-source；**不得**用 $PSScriptRoot。

function Get-ScrubRules {
    # 2026-09-21 · scrubber 规则扩充裁定（docs/security/2026-09-21_scrubber规则扩充裁定与影响面.md）：
    # ★ **规则的单一真值源** —— `Invoke-Scrubber`(抹) 与 `Get-ScrubBlockReason`(拒) 都从这里取，
    #   免得"同一个模式两处各写一遍"然后漂移（本项目反复栽在这个形态上）。
    # 本次按裁定 §3 由 3 条扩到 9 条：加 6 条**凭据类**（固定前缀锚定 ⇒ 可判性高、误伤≈0）。
    # ★ **刻意不加**那 8 条身份与拓扑类（内网 IP / .local 主机名 / Linux 绝对路径 / UNC /
    #   用户名 / 手机号 / 身份证 / 银行卡），理由见裁定 §3，一句话：
    #     · 前三类是**项目自己的日常寻址方式**（`.local` 212 处 / `/home/<user>/` 211 处 /
    #       内网 IP 是 `inventory/net.yaml` 的权威真值）⇒ 抹掉它们 = 抹掉任务可执行性；
    #     · 手机号/身份证/银行卡的**长度判据会命中本仓 run ID**（`yyyyMMddHHmmssffff` 恰好
    #       18 位数字、全仓 204 处）；要加也只能用**校验位**（GB 11643 / Luhn）—— 见裁定 §2.3/§6-P5；
    #     · 裸用户名**不可判**。那 8 项的正确防线是**档位**（含 PII/拓扑的卡走 local-only），不是正则。
    # block=$true ⇒ 命中时**拒发**（不是抹掉继续）—— 见 `Get-ScrubBlockReason` 的注释。
    return @(
        # —— 凭据类：固定前缀锚定 ——
        @{ name = 'private-key'; block = $true;  re = '-----BEGIN [A-Z ]*PRIVATE KEY[A-Z ]*-----';                repl = '[REDACTED-PRIVATE-KEY]' },
        @{ name = 'github-pat';  block = $false; re = '\b(?:github_pat_[A-Za-z0-9_]{22,}|gh[pousr]_[A-Za-z0-9]{36,})'; repl = '[REDACTED-GH-PAT]' },
        @{ name = 'aws-ak';      block = $false; re = '\b(?:AKIA|ASIA|A3T[A-Z0-9]|AGPA|AIDA|AROA|AIPA|ANPA|ANVA)[A-Z0-9]{16}\b'; repl = '[REDACTED-AWS-KEY]' },
        @{ name = 'slack';       block = $false; re = '\bxox[abprs]-[A-Za-z0-9\-]{10,}';                          repl = '[REDACTED-SLACK-TOKEN]' },
        @{ name = 'jwt';         block = $false; re = '\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}'; repl = '[REDACTED-JWT]' },
        @{ name = 'api-key';     block = $false; re = 'sk-[A-Za-z0-9_\-]{16,}';                                   repl = '[REDACTED-KEY]' },
        # bearer **刻意收窄**（裁定 §3-5）：泛模式会吃掉任何长不透明串 ⇒ 只在 `Bearer ` 上下文里认 + 长度 ≥20。
        @{ name = 'bearer';      block = $false; re = '(?i)\bbearer\s+[A-Za-z0-9._~+/=\-]{20,}';                   repl = '[REDACTED-BEARER]' },
        @{ name = 'email';       block = $false; re = '[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}';          repl = '[REDACTED-EMAIL]' },
        # win-path —— 两条**已被夹具实测钉死**的取舍（改动前先读夹具 §2b/§4b）：
        # ⚠ 不能是 `\S+`：空格即断 ⇒ `C:\Program Files\Git\bin\bash.exe` 只吃掉 `C:\Program`，
        #   **残留** `Files\Git\bin\bash.exe` —— 而"看起来已处理过"的残留比不处理更危险。
        # ⚠ 也不能是"段内一律允许空格"（`(?:\\[^\\]+)+`）：贪心会把**路径后面的普通词一起吃**
        #   （`C:\RPC\out.txt done` → 整段变 `[REDACTED-PATH]`）—— 本机 prompt 里句中路径极常见
        #   ⇒ 那是**误伤任务输入**（静默破坏，同族于静默降级）。
        # 取舍：只有当段后**还有 `\`**（即能证明它仍是路径）时才允许段内含空格；末段遇空格即停。
        #   代价 = "末段含空格"形态会**残留**（已知缺口，见夹具 §4b），消除它需再加规则=决策。
        @{ name = 'win-path';    block = $false; re = '(?i)\b[A-Z]:\\(?:[^\\/:*?"<>|\r\n\t]+\\+)*[^\\/:*?"<>|\r\n\t\s]*'; repl = '[REDACTED-PATH]' }
    )
}

function Invoke-Scrubber {
    # D6 audit P1 (2026-09-03): regex-only sanitizer for sensitivity=sanitized (IMPL T2 scope).
    # Runs on console BEFORE the prompt leaves (invariant 2: scrub on console, remote only
    # receives sanitized text). R4: prints masked previews of hit lines for human confirmation;
    # no whitelist in MVP. **规则清单已抽到 `Get-ScrubRules`（单一真值源，2026-09-21）。**
    param([string]$text)
    $hits = 0
    foreach ($r in (Get-ScrubRules)) {
        $ms = [regex]::Matches($text, $r['re'])
        if ($ms.Count -gt 0) {
            $hits += $ms.Count
            foreach ($m in $ms) {
                $preview = if ($m.Value.Length -gt 8) { $m.Value.Substring(0, 8) + '...' } else { $m.Value }
                Write-Host "SCRUB[$($r['name'])] hit: $preview (len=$($m.Value.Length)) -> $($r['repl'])"
            }
            $text = [regex]::Replace($text, $r['re'], $r['repl'])
        }
    }
    if ($hits -gt 0) { Write-Host "SCRUB total hits: $hits (sanitized gate active)" }
    return $text
}

function Get-ScrubBlockReason {
    # 2026-09-21 · scrubber 规则扩充裁定 §5-1：把"**命中即拦截**"与"**脱敏后继续**"的二分钉死
    #   （此前 DESIGN §193 写"命中即拦截"、而 §2.1 三档定义写"sanitized→**脱敏后**远端"，
    #     两句张力一直没被处置）。二分依据 = **能不能安全抹除**：
    #   · 凭据类（key/email/路径/PAT/…）⇒ **抹掉继续**：抹掉后卡仍自洽，且下游（证据流/归档/
    #     验收/基线）看到的就是"已消毒"的 prompt，语义与 `public` 档一致。
    #   · **私钥块** ⇒ **拒发（fail-closed）**：卡里贴了整把私钥说明**这张卡本身就不该出网**；
    #     抹掉它会让一张本该被作者修掉的卡**看起来正常** —— 与"看起来处理过了"同族。
    # 返回 '' = 放行 / 否则原因 token（与 `Get-SensitivityBackendReject` 同约定）。
    # ⚠ 模式**不在此处重复写**：从 `Get-ScrubRules` 里取 `block=$true` 的那几条（单一真值源）。
    # 纯函数 ⇒ 夹具可按名提取离线单测（与 `Test-FallbackEligible` 同族）。
    param([string]$text)
    if (-not $text) { return '' }
    foreach ($r in (Get-ScrubRules)) {
        if ($r['block'] -and [regex]::IsMatch($text, $r['re'])) { return "scrub-unsafe:$($r['name'])" }
    }
    return ''
}

