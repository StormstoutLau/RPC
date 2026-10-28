# 30-d7.ps1 —— D7 三信封 / 裁决 / 出网判据（review-p2-split 8C；整段抽出，行为不变）
#   Test-D7Envelope / Get-D7Adjudication / Get-BackendEgress / Get-JudgeEgress /
#   Get-JudgeComplianceReject / Get-AttachEgressReject
# ⚠ 判据本体一律在 `ops/rpc_check.py`（`--d7-*` 消费面）；**外壳不重写判据** —— 否则同一事实两处表达。
#   本文件只做「组装 + 调判据 + 报数」，不改任何判定（review 仍是 advisory）。
# ⚠ 由入口按 `$Script:AGENT_CLI_LIBS` 顺序 dot-source；**不得**用 $PSScriptRoot
#   （`$PSScriptRoot` 在 dot-source 里指向调用方，本文件只写**纯函数**）。

function Test-D7Envelope {
    # ★ B 段：三信封校验 ⇒ **唯一的消费点**（判据本体 = `ops/rpc_check.py` 的 `validate_envelope`）。
    param([string]$Kind, $Obj, [string]$Card = '')
    $r = Invoke-D7Cli -Argv @('--d7-envelope', $Kind) -Json $Obj
    $r['card'] = $Card
    return $r
}

function Get-D7Adjudication {
    # ── ★★ B 段（2026-10-01）：**P4a/P4b/P5 接线** —— 状态机 + 红线 1/2 + Verdict 登记 ────────
    # ★ 只**消费既有事实**（`$L1Section` / `$CcSection` / review 的 exit code），**不改任何判定**：
    #   `review` 仍是 **advisory**（本函数只打印 + 调判据，**不影响退出码**）。
    # ⚠ **有副作用**（子进程）⇒ 不进离线夹具（纯的那半 = `Resolve-D7PhaseChain` / `New-Verdict` 已离线测）。
    # ★★ **甲（2026-10-01，用户裁定）：本函数【返回】段，由调用方在 `review.json` 写盘前调** ──────
    #   为什么改（`O-139`，C 段真跑查出）：旧名 `Write-D7Adjudication` 跑在 `Set-Content` **之后**
    #   ⇒ 判据校验过的那个 `Verdict` **只活在 stdout**，磁盘上找不到 ⇒ 契约把 P5 叫「裁决**登记**」
    #   而**登记面是空的**。现改为「先组装 → 注入 `$review['d7_verdict']` → **一次写盘**」。
    #   ⇒ 改名 `Get-*`（PS 的 `Get-Verb` 它已合规）：**名实相符** —— 它确实是"取一段事实"，不是"写"。
    # ★★ **该段是【派生段】，不是第二份真值**：`l1_results` / `l2_marks` / `verdict` **逐字取**
    #   `review.json` 已有的 `l1` 段 / `contract` 段 / `metadata.call_code` ⇒ 它只是把**同一次裁决**
    #   收成一个**可指对象**（"登记面"），**不引入任何新事实**。
    # ⚠⚠ **生命周期边界（写死，防下一个人把它当账本读）**：`review.json` 已登记 `not_a_ledger`
    #   （`inventory/conclusion-ledgers.yaml`：glob `**/review.json`，why「一次派发一份的产物，**不追加**」）
    #   ⇒ 本段是「**最新裁决**」，**不是「裁决流水」**：重评（`--overwrite`）会**覆盖**它
    #   （`recorded_at` 随之更新）—— 要流水须先升格账本，那是**另一步**（见 `O-139` 的升级路径）。
    # ⚠ 诚实：`actor` 在本架构里**恒为 `master`**（外壳只在主控跑）⇒ 红线 1 的实用价值是
    #   **防将来有人把 P5 搬到站上**（届时 `actor` 变 ⇒ 判据立刻拦）—— **不是**"已拦过真实动作"。
    # ★ B3（2026-10-01）新增 `-ExecHost`：**产出机**（run 记录里的 `exec_host`）—— `PRH` 需要它。
    #   ⚠ 收的是 **host 串**（不是站字母）：本函数的两个调用点在 `Invoke-Review` 里，那里**只有** run
    #     记录可读（`$l1Record.exec_host`），**没有**站字母 ⇒ 传 host 才是**事实直传**（传字母要反查，
    #     反查不到又会回落成"本地"⇒ **假报同机**）。缺 = 空串 ⇒ 判"不可判"（见 ⑤）。
    param($L1Section, $CcSection, [int]$ExitCode, [bool]$L2Ran = $true, [string]$Card = '',
          [string]$ExecHost = '', [System.Collections.IDictionary]$GuardSink = $null)
    $actor = 'master'
    # ★ 报数落点（2026-10-01）：`-GuardSink` = 可选收集器，记**本趟 review** 每台判据的三态码
    #   ⇒ 「每千次 review 拦了多少」才算得出来（此前这些行只走 stdout = 与 `O-139` 同病）。
    #   ⚠ 只记**可计数的三态码**，不记理由文本（理由在 stdout；复制一份 = 第二份真值）。
    # ① 状态机（P4a→P4b 可选→P5）**逐跳调判据** —— 非法跳（如跳过 L1）会当场报 reject
    $chain = Resolve-D7PhaseChain -L1Verdict ([string]$L1Section['verdict']) -L2Ran $L2Ran
    $hopRej = 0
    for ($i = 0; $i -lt $chain.states.Count - 1; $i++) {
        $t = Invoke-D7Cli -Argv @('--d7-transition', $chain.states[$i], $chain.states[$i + 1], $actor)
        if ($t['code'] -ne 0) {
            $hopRej++
            Write-Host ("D7_PHASE_REJECT: " + $t['line'] + " ⇒ **灰度期：不阻断**")
        }
    }
    if ($GuardSink) { $GuardSink['transition.hops'] = [int]($chain.states.Count - 1); $GuardSink['transition.rejected'] = [int]$hopRej }
    Write-Host ("D7_PHASES: " + ($chain.states -join ' -> '))
    # ② 红线 2（L1 先于 L2 且 L2 无权改写）：L1 事实与 L2 结论**分开存** ⇒ 结构上不改写；
    #    可审计凭据 = `$L1Section.record_sha256`（回算 run 记录即可比对）
    $rb2 = Invoke-D7Cli -Argv @('--d7-block', 'RL2') -Json @{
        l1_results = @($L1Section); l2_marks = @($CcSection); l2_rewrites_l1 = $false }
    if ($rb2['code'] -ne 0) { Write-Host ("D7_" + 'RL2_REJECT' + ": " + $rb2['line'] + " ⇒ **灰度期：不阻断**") }
    if ($GuardSink) { $GuardSink['RL2'] = [int]$rb2['code'] }
    # ③ 红线 1（完成信号权只在主控站）
    $rb1 = Invoke-D7Cli -Argv @('--d7-block', 'RL1') -Json @{ actor = $actor }
    if ($rb1['code'] -ne 0) { Write-Host ("D7_RL1_REJECT: " + $rb1['line'] + " ⇒ **灰度期：不阻断**") }
    if ($GuardSink) { $GuardSink['RL1'] = [int]$rb1['code'] }
    # ④ P5 裁决登记：Verdict 信封（`verdict` = review 的 exit code）
    $d7v = New-Verdict -ExitCode $ExitCode -Phase 'P5' -L1Section $L1Section `
                       -L2Marks $(if ($L2Ran) { @($CcSection) } else { $null })
    Write-D7Report -Kind 'Verdict' -Obj $d7v['verdict'] -Gaps $d7v['gaps'] -Tag 'VERDICT' -Card $Card `
                   -GuardSink $GuardSink      # ★ 顺带记 `VERDICT.envelope` / `VERDICT.i6`（缺省 $null ⇒ 无副作用）
    # ── ★★ B3（2026-10-01）：角色禁项 `PRM` / `PRW` —— **角色动作点**（契约 §1.6「不堆在 P5 一处」）──
    # ⚠ 为什么是**这里**：本函数正是"**谁执行 / 谁裁决**"两个角色事实**第一次相遇**的地方（③ 之后）。
    #   · `PRM` 的动作 = `execute_task` ⇒ 执行由 **worker 角色**登记 —— 裁【甲】（契约 §1.4）：§1.4 的
    #     「主控站/工作站」= **角色**（不是机器）⇒ 主控机器上的出网通道也以 `worker` 登记 ⇒ **不触** PRM；
    #     ★ "同一台机器既产出又裁决"这件事由下面的 `PRH` 负责**看见**（报数，不阻断）。
    #     ⇒ ⚠ 这里**不**按机器归属推 actor（裁【甲】第 2 句逐字：**不由机器归属推**）。
    #   · `PRW` 的动作 = `write_verdict` ⇒ 在此**动作点**由 `$actor`（master）驱动 ⇒ 不触 PRW
    #     （PRW 约束的是 worker：不自评/不写 verdict/不重派/不合并）。价值 = **防将来把 P5 搬到站上**。
    $rpm = Invoke-D7Cli -Argv @('--d7-block', 'PRM') -Json @{ actor = 'worker'; action = 'execute_task' }
    if ($rpm['code'] -ne 0) { Write-Host ("D7_PRM_REJECT: " + $rpm['line'] + " ⇒ **灰度期：不阻断**") }
    if ($GuardSink) { $GuardSink['PRM'] = [int]$rpm['code'] }
    $rpw = Invoke-D7Cli -Argv @('--d7-block', 'PRW') -Json @{ actor = $actor; action = 'write_verdict' }
    if ($rpw['code'] -ne 0) { Write-Host ("D7_PRW_REJECT: " + $rpw['line'] + " ⇒ **灰度期：不阻断**") }
    if ($GuardSink) { $GuardSink['PRW'] = [int]$rpw['code'] }
    # ── ★★ B3（2026-10-01）：`PRH` 同机可见性 —— **报数不阻断**（契约 §1.6 ②）──────────────────
    # ★ 判据 = `d7_host_separation`（**不属于**那 8 条拦截 ⇒ 单独调 `--d7-host-sep`，不进 `--d7-block`）。
    # ★ 两侧事实：产出机 = `-ExecHost`（run 记录里的 `exec_host`）· 裁决机 = `$env:COMPUTERNAME`。
    # ⚠⚠ **argv 空值不可表达**（PS 与 argparse 都吃空串 ⇒ `argparse` 直接退 2）⇒ **自家先判空**并报
    #    "不可判"，**不要**把空串交给 CLI（契约 §1.6「已知 argv 限制」逐字）—— 而"判不了"**不许**读成"不同机"。
    $arb = [string]$env:COMPUTERNAME
    if (-not $ExecHost -or -not $arb) {
        Write-Host ("D7_PRH_UNDECIDABLE: 缺 host（exec=" + $ExecHost + " / arbiter=" + $arb +
                    "）⇒ **不可判**（判不了 ≠ 不同机）⇒ 灰度期不阻断")
    } else {
        $hsep = Invoke-D7Cli -Argv @('--d7-host-sep', $ExecHost, $arb)
        if ($hsep['code'] -eq 1) {
            Write-Host ("D7_PRH_SAME: " + $hsep['line'] + " ⇒ **WARN（不阻断；★ 已定档 2026-10-10 = 维持报数 · O-136 裁② 终点）**")
        }
        elseif ($hsep['code'] -eq 0) { Write-Host ("D7_PRH_SEPARATE: " + $hsep['line']) }
        else { Write-Host ("D7_PRH_UNDECIDABLE: " + $hsep['line'] + " ⇒ 灰度期不阻断") }
        # ★ 报数：`PRH` 的**三态**原样入 sink（`0` 分离 / `1` 同机 / `2` 不可判 —— 与 CLI 一致，不另立编码）。
        if ($GuardSink) { $GuardSink['PRH'] = [int]$hsep['code'] }
    }
    # ★ 报数：能走到这里 = 本趟 review 的**三态全跑过** ⇒ 记一个"完成"标记，
    #   使聚合侧能区分「**这段根本没跑**」与「跑了但全 ok」（否则两者都表现为"没有 reject"，是假绿）。
    if ($GuardSink) { $GuardSink['completed'] = 1 }
    # ★ 甲（2026-10-01）：**把段还给调用方**（由它在 `$review | ConvertTo-Json | Set-Content` **之前**注入）。
    #   ⚠ 位置在**函数末尾**（不许提前 return —— 那会跳过上面的 PRM/PRW/PRH 三条角色检查）。
    #   ⚠ 归零纪律：本函数其余输出一律 `Write-Host`（不占管道）⇒ 这里的 return 是**唯一**进管道的对象；
    #     调用方**必须**具名赋值（`$review['d7_verdict'] = Get-D7Adjudication …`），**不许裸跑**。
    return $d7v['verdict']
}

function Get-BackendEgress {
    # route id 用它自己跑时会不会出网。规则刻意**反转为 fail-closed 默认**：
    #   **只有站内本地引擎（`local/<flavor>`）不出网，其余一律视为出网**（含未知/空 id）。
    param([string]$id)
    if ([string]::IsNullOrWhiteSpace($id)) { return $true }
    return -not ($id -match '^local/')
}

function Get-JudgeEgress {
    # judge 会不会出网 —— **优先读 `JUDGE_TABLE` 声明的 `egress` 字段**（真值源就在表里）；
    #   未声明时**回退按 `type` 推**，仍无法判定 ⇒ **视为出网**（fail-closed）。
    #   为什么以声明字段为主: `type='http'` 是 **ENV 注入**的外部 /v1 —— 若调用方把它指向**本地**端点,
    #   那它就不出网, 而 type 推不出来（故 `commercial` 那一行注释要求"改一处就同时改另一处"）。
    #   type 语义: 'local'(控制台 CLI) / 'http-local'(站上引擎) ⇒ 不出网; 'egress'(云) / 'http'(外部) ⇒ 出网。
    param($judge)
    if (-not $judge) { return $true }
    if ($judge.ContainsKey('egress')) { return [bool]$judge['egress'] }
    $t = [string]$judge['type']
    if ($t -eq 'local' -or $t -eq 'http-local') { return $false }
    return $true
}

function Get-JudgeComplianceReject {
    # **接线 `JUDGE_TABLE.compliance`** —— 该字段此前全仓只有声明、**无任何读取点**（= 假防线，
    #   见 OPEN-ISSUES「消毒面 ≠ 出网面」缺口③）。语义：该 judge **允许承载的 sensitivity 列表**；
    #   `all` = 全部允许；**未声明 ⇒ 拒**（fail-closed，别让"忘写字段"变成"默认放行"）。
    # 返回 '' = 放行 / 否则 = 拒绝原因 token（纯函数，与 Get-SensitivityBackendReject 同族）。
    param($judge, [string]$sensitivity)
    if (-not $judge) { return 'judge-unknown' }
    $c = [string]$judge['compliance']
    if ([string]::IsNullOrWhiteSpace($c)) { return 'judge-compliance-undeclared' }
    if ($c.Trim().ToLower() -eq 'all') { return '' }
    $allow = @($c.Split(',') | ForEach-Object { $_.Trim().ToLower() })
    if ($allow -contains ([string]$sensitivity).ToLower()) { return '' }
    return 'judge-compliance'
}

function Get-AttachEgressReject {
    # W4 裁定 B（2026-09-22）: **附件默认不出网 + 显式放行**。返回 '' = 放行 / 否则原因 token。
    # 为什么附件与卡正文**不同规矩**（§5.5.2 的决定性判据 = **可判性**）:
    #   · 卡正文是文本 ⇒ 能建**可测的覆盖率**（14 项探测形态 + 9 条规则）⇒ **抹后可出网**（= `sanitized` 档定义）；
    #   · **附件形态不可判**（二进制/压缩/base64/UTF-16/未知编码）⇒ **抹不出可测覆盖率** ⇒ 「抹」只产出
    #     **假防线**（"抹了一半"比"明确不抹"**更难发现**）⇒ 只能靠**不出网**兜底。
    # 三条全中才拒: ① 有附件 ② 目标后端**会出网** ③ 卡**未**显式声明放行。
    # 放行通道 = 卡写 `attach-egress: ok|yes|true`（与 `review-model` 同属"**显式接受出网**"家族）。
    # ⚠ 后端是否出网由调用方按通道给（opencode 通道 = Get-BackendEgress $id；claude 通道 = -not $backendLocal）。
    # 纯函数 ⇒ 夹具可按名提取离线单测（与 Get-SensitivityBackendReject / Resolve-ReviewPrompt 同族）。
    param([int]$attachCount, [bool]$backendEgress, [string]$declared)
    if ($attachCount -le 0) { return '' }
    if (-not $backendEgress) { return '' }
    $d = ([string]$declared).Trim().ToLower()
    if ($d -eq 'ok' -or $d -eq 'yes' -or $d -eq 'true') { return '' }
    return 'attach-egress-unconfirmed'
}
