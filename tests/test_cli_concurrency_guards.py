"""已落地修复的**静态护栏**（回归哨兵）—— 2026-09-23

为什么用"静态文本断言"而不是跑真并发
--------------------------------------
这些修复的**失效方式**都是"被回退"或"被顺手删掉"（例如有人清理"没用的行"时删掉
远端的 `mkdir -p "$W/out"`，或把 `$ts` 的去重当作冗余去掉）。用一次真并发去守它们，
成本高、且只在特定环境可跑；而**静态断言能在每次测试里零成本拦住回退**。

覆盖的修复（每条都给"反向即红"的判据）
--------------------------------------
- **F-2**（BLINDSCAN-v3）：共享固定名 `agent-out\\.agent-run.json` **不得**再出现
  （它无写入方 ⇒ 死清理；留着会误导审查，且一旦有人恢复写该名就会变成并发真破坏）。
- **F-3 / RC④**：远端脚本**必须**保留 `mkdir -p "$W" "$W/out"` ——
  **站侧自建 out/ 是既定事实**（不依赖 tar 携带空目录）；删掉它才会让 RC④ 复现。
- **O-28 RC② / O-63**：`$ts` 取号**必须**走**原子抢占**（`Get-UniqueRunStamp` 的 create-or-fail），
  不得退回"存在性检查"（`while (Test-Path …) { 递增 }` = **TOCTOU**：两个并发进程会**同时**判"不存在"）。
  ⚠ **2026-09-25 判据改写**：原判据盯的是 check-then-act 的**行文**（`$ts = …ToString(…)` 紧跟 `while (Test-Path …)`）——
  O-63 换成原子抢占后那段行文**已不存在** ⇒ 旧判据变成"指向已删除实现细节"的**过期断言**（恒红）。
  ⇒ 改为盯**原子语义**（原语 + 两处调用 + 旧模式已消失 + 抢占物有 GC）。**方向是改写，不是回退代码。**
- **裁定 A**：`station-ready` 必须**按后端属性分流**（`Get-BackendEgress`），
  不得退回无条件探测（那会把出网档重新锁死在引擎门上）。
- **O-27**：`.meta` 必须写 `RC_DOMAIN=v2`（TASK_RC 与 run.json 同域的标记）。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "ops" / "station-bin" / "agent-cli.ps1"


def code_hits(src: str, needle: str):
    """只在**注释之外**的代码文本里找 needle。

    2026-09-23 实测教训（本文件第一版就被自己抓到）：F-2 的注释**必须**写出被删的那条路径以留档，
    而粗糙的子串检查会把**注释里的留档**当成违规 ⇒ 假红。
    ⇒ 与本仓既有纪律一致：**扫代码文本的断言要区分"代码"与"注释"**（否则文档与判据互相打架）。
    """
    hits = []
    for i, ln in enumerate(src.splitlines(), 1):
        code = ln.split('#', 1)[0]
        if needle in code:
            hits.append((i, ln.strip()[:80]))
    return hits


def code_only(src: str) -> str:
    """剥掉**注释**后的代码文本（逐行取 `#` 之前的部分）。与 `code_hits` 同一口径。

    ⚠⚠ 2026-09-25 **实测踩到**：`O-28 RC②/O-63` 那条判据的第一版用的是**全文子串**（`in src`）⇒
    只要**注释里**出现 `[IO.FileMode]::CreateNew`，断言就会**过**，哪怕代码侧已经退化成
    `OpenOrCreate`（非原子）。**实测复现**：代码改 `OpenOrCreate` + 注释写上该串 ⇒ 断言仍
    `ALL PASS`（= **假绿**）。⇒ 这正是本文件 `code_hits` 注释里写的那条纪律，我改写时违反了自己文件里的规矩。
    """
    return "\n".join(ln.split('#', 1)[0] for ln in src.splitlines())


def main() -> int:
    if not CLI.exists():
        print(f"FAIL: 找不到 {CLI}")
        return 1
    src = CLI.read_text(encoding="utf-8", errors="replace")
    fails = []

    def need(desc, cond, hint):
        print(("  ok  " if cond else "  FAIL ") + desc)
        if not cond:
            fails.append(f"{desc} ⇒ {hint}")

    # F-2：共享固定名不得出现在**代码**里（注释里的留档允许）
    hits = code_hits(src, "agent-out\\.agent-run.json")
    need("F-2 共享固定名（代码中）不再出现",
         not hits,
         f"有人恢复了共享固定路径的引用 ⇒ 并发时会删掉他人 run 记录；命中={hits}")

    # F-3：远端自建 out/ 必须保留
    need('F-3 远端脚本保留 mkdir -p "$W" "$W/out"',
         bool(re.search(r'mkdir -p "`\$W" "`\$W/out"', src)),
         "删掉它会让 RC④（全新工作区无 out/）复现；这是站侧自建、不依赖 tar 的行为")

    # O-28 RC② / O-63：`$ts` 取号必须走**原子抢占**（见文件头"2026-09-25 判据改写"）
    # ⚠ 一律用 **`code_only`**（剥注释）—— 第一版用全文子串，实测被注释蒙过（假绿，见 code_only 的 docstring）。
    co = code_only(src)
    ts_atomic = "[IO.FileMode]::CreateNew" in co and "[IO.FileShare]::None" in co
    ts_def = "function Get-UniqueRunStamp" in co
    ts_sites = len(re.findall(r"Get-UniqueRunStamp -ProjOutRoot", co))
    # 旧 check-then-act 必须**消失**。⚠ 只在**代码**里判（注释里留档该模式是刻意的，不算违规）
    ts_cta = code_hits(src, "while (Test-Path (Join-Path $tsOutRoot")
    # 抢占物必须有**出口**（对应 runDir 已存在 / 超 7 天 ⇒ 删）—— 防"登记无出口 ⇒ 腐化"
    ts_gc = "$d.CreationTime -lt $cut" in co
    need("O-28 RC②/O-63 $ts 走原子抢占（原语 + 两处调用 + 旧 check-then-act 已消失 + 抢占物有 GC）",
         ts_atomic and ts_def and ts_sites >= 2 and not ts_cta and ts_gc,
         f"原子原语={ts_atomic} 定义={ts_def} 调用点={ts_sites}/2 旧check-then-act残留={ts_cta} GC={ts_gc} ⇒ "
         "退回 check-then-act ⇒ 两个并发进程同时判『不存在』⇒ 取到同一 ts ⇒ runDir/scratch 互踩（实测 rc=7）")

    # 裁定 A：station-ready 按后端属性分流
    need("裁定 A station-ready 按 Get-BackendEgress 分流",
         bool(re.search(r"if \(Get-BackendEgress \$id\)[\s\S]{0,400}?STATION_READY_SKIPPED", src)),
         "退回无条件探测 ⇒ 出网档（lightning/ultra/free-1m）又被锁在本地引擎门上")

    # O-27：.meta 必须带域标记
    need("O-27 .meta 写入 RC_DOMAIN=v2",
         "RC_DOMAIN=v2" in src,
         "去掉域标记 ⇒ cluster.py 会按 v1 解释 ⇒ 验收失败的 run 又被误判 FAIL")

    # F-1 / O-28 RC③：探针名必须带 per-invocation 身份
    need("F-1 探针名带 RUN_TOKEN（不得退回秒级精度）",
         bool(re.search(r"_preflight_\$\(\$Script:RUN_TOKEN\)\.probe", src)),
         "退回 _preflight_HHmmss.probe ⇒ 同一秒启动的两进程撞同一探针 ⇒ Stream was not readable，"
         "且会把『并发』伪装成『环境不可写』（错误归因）")

    # F-14：sync tar 名必须带 per-invocation 身份（本地与站上同名）
    need("F-14 sync tar 名带 RUN_TOKEN",
         not re.search(r"agent-cli-sync-\$proj\.tar", src),
         "退回共享固定名 agent-cli-sync-<proj>.tar ⇒ **sync 在远端 flock 之前** ⇒ 同 proj 并发互删"
         "（实测 sync failed: Cannot find path '…Temp\\agent-cli-sync-dogfood.tar'）")

    # ── ★ 纪律断言化（2026-09-23）─────────────────────────────────────────────
    # BLINDSCAN-v3 §3 的跨条目纪律: **凡"共享路径", 要么带 per-invocation 身份
    #   (`$Script:RUN_TOKEN` / `$ts`), 要么走真锁(`flock`)。**
    # 为什么要把逐个 F 编号换成一条通用规则: F-1(探针) / F-2(死路径) / F-14(sync tar)
    #   三条**同一病因** —— "漏照抄本仓已有的两个样板"(TMP_ROOT 的 token / 远端 flock)。
    #   换个编号继续撞没有意义; **把它写成判据后, 它自己抓出了 F-14(扫描没列的那条)**。
    # 实现: 扫所有"临时/暂存路径构造点"(Join-Path $env:TEMP "…" 与 /tmp/…), 逐个要求含身份。
    # 身份 token: 直接身份(`$Script:RUN_TOKEN`/`$ts`/随机/pid) **或**派生自 TMP_ROOT 的局部变量
    #   (`$Script:TMP_ROOT` 本身已带 RUN_TOKEN ⇒ 从中派生的路径**传递地带身份**, `:169` 即此形)。
    IDENTITY = ("RUN_TOKEN", "$ts", "$tsN", "$tsOutRoot", "Get-Random", "$$",
                "$localPath", "$LocalName", "$tmpSm", "$tmp", "$localSh")
    # 豁免: 内容恒定、幂等覆盖、且**不承载 per-run 数据**的只读脚本投递点(并发 scp 同内容无害)。
    #   ⚠ 新增豁免必须在此显式登记并写理由 —— 防"豁免清单腐化"。
    EXEMPT = {
        "_station_ready.sh": "内容恒定只读脚本, scp 幂等覆盖, 不承载 per-run 数据",
        "_slot_gate.sh": "同上",
        "_oc_session_meta.sh": "同上(经 $Script:TMP_ROOT 投递, 此处仅列远端名)",
        "_p3_run.sh": "同上(内容恒定 here-string 常量 + 参数传入; O-31 已核实)",
        # ── 第二类（2026-09-25 新增）：**必须跨进程共享**——共享正是它的功能（与第一类**理由不同**）──
        #   第一类是"内容恒定 ⇒ 同内容互覆无害"；本类是"**共享是设计目的** ⇒ 加 per-run 身份会**破坏语义**"。
        #   ⚠ key 用**带引号的字面量**（如 `'agent-cli-claims'`）钉住具体那行 —— 防宽 key 顺带豁免掉将来
        #     新出现的同类命名（豁免面必须**恰好**等于已知项）。
        "'agent-cli-claims'": "O-63 的 ts **抢占目录**（`%TEMP%\\agent-cli-claims`）—— 跨进程必须共用"
                              "**同一个** claim 空间才叫原子抢占；加 `RUN_TOKEN` ⇒ 每 run 各占各的目录 ⇒ "
                              "抢占**失效**（等于把 O-63 修好的 TOCTOU 洞挖回来）",
        '"agent-cli-lease-': "O-62/C3+C1 的**工作区租约文件**（`%TEMP%\\agent-cli-lease-<key>.lock`）—— "
                             "互斥/共享的前提就是**同一个**文件名（key 已含站与 proj）；加 `RUN_TOKEN` ⇒ "
                             "各锁各的 ⇒ 锁形同虚设（危险序① 复活）",
    }
    temp_names = re.findall(r'Join-Path \$env:TEMP "([^"]+)"', src)
    # ⚠ 字符类必须含 `:` —— 否则 `$Script:RUN_TOKEN` 会在 `:` 处被截断 ⇒ 把"已带身份"误判成"无身份"(假红)。
    tmp_names = re.findall(r"/tmp/([A-Za-z0-9_.$(){}%:\-]+)", src)
    # 已登记项: 允许存在, 但**必须在此显式列出** —— 防"新增未分类路径混进来"。
    #   · EXEMPT    = **已核实**确实恒定无害(可长期留)
    #   · KNOWN_DEFECTS = **已核实是缺陷, 但本轮未修**(必须带修法; 修掉后应删除本行)
    #   ★ 2026-09-24 同步(见台账 O-31): 2026-09-23 核实的四项**已全部结清** ——
    #     · `_p3_claude_{in,out,err}.txt`: **已修** —— 站上临时名改用 GUID 唯一前缀 `$p3id`
    #       (经参数 `$4` 传入站上脚本, [agent-cli.ps1:3058](../../ops/station-bin/agent-cli.ps1))
    #       ⇒ 固定名已从脚本消失 ⇒ 按本表自身纪律"修掉后应删除本行"**删除**。
    #     · `_p3_run.sh`: 核实为"内容恒定 + scp 幂等覆盖" ⇒ **转入 EXEMPT**。
    KNOWN_DEFECTS = {}   # 当前为空(机制保留: 后续"已核实待修"项仍须在此显式登记)
    KNOWN_PENDING = KNOWN_DEFECTS   # 兼容旧名(断言只关心"是否已显式登记")
    bad_lines = []
    # ⚠ 采用**行级**检查而非"解析路径名" —— 2026-09-23 实测: 按名解析会被 `:`、`/`、`$(` 等
    #   反复截断, 产出 `agent-cli-ev-` 这类**残缺名**, 把"已带身份"误判成"无身份"(连续两次假红)。
    #   行级检查更粗但**不会被截断骗**。
    #   ⚠⚠ 判定必须用**完整行** —— 我把 `[:70]` 的显示截断误用到了判定上, 又一次自伤(第三次假红)。
    #
    # **射程（有意收窄）**：只盯**我们自己构造、且承载 per-run 数据**的路径 —— 即前缀 `agent-cli-`。
    #   依据：本纪律的三个真实实例 F-1(`_preflight_*.probe`) / F-2(`agent-out\*.json`) / F-14(`agent-cli-sync-*.tar`)
    #   **全部**是这种。而 `/tmp/` 下**投递的只读脚本**（`_station_ready.sh` / `_slot_gate.sh`：
    #   内容恒定 + scp 幂等覆盖 + 不承载 per-run 数据）**不在射程** —— 它们的名字常经变量拼接,
    #   从行内无法判定, 强行纳入只会把判据变成噪声源。
    def _in_scope(code: str) -> bool:
        return "agent-cli-" in code
    temp_lines = [(i, ln) for i, ln in enumerate(src.splitlines(), 1)
                  if "Join-Path $env:TEMP" in ln.split('#', 1)[0] and _in_scope(ln)]
    tmp_lines = [(i, ln) for i, ln in enumerate(src.splitlines(), 1)
                 if "/tmp/" in ln.split('#', 1)[0] and _in_scope(ln)]
    bad_lines = []
    for i, ln in tmp_lines + temp_lines:
        code = ln.split('#', 1)[0]
        # 样板本身: `$Script:TMP_ROOT` 的定义行(它就是被照抄的那个样板, 不必自证)
        if code.strip().startswith("$Script:TMP_ROOT"):
            continue
        if any(tok in code for tok in IDENTITY):
            continue
        if any(k in code for k in EXEMPT) or any(k in code for k in KNOWN_PENDING):
            continue
        bad_lines.append((i, code.strip()[:70]))
    print(f"  · 纪律扫描(行级): temp 构造行 {len(temp_lines)} · /tmp 引用行 {len(tmp_lines)}")
    need("★ 纪律: 无【新增】的共享临时/暂存路径行（已登记项除外）",
         not bad_lines,
         f"以下行既无 RUN_TOKEN/ts 也未登记 ⇒ 并发会互踩: {sorted(set(bad_lines))}；"
         "修法 = 照抄样板加 $($Script:RUN_TOKEN)，或在 EXEMPT/KNOWN_PENDING 显式登记理由")
    pend = sorted({k for k in (EXEMPT | KNOWN_PENDING) if any(k in ln for _, ln in tmp_lines + temp_lines)})
    if pend:
        print(f"  · 已登记(EXEMPT/已知缺陷, 台账 O-31): {pend}")

    # F-4：ledger 追加必须走 Add-LedgerLine（互斥 + 退避），不得退回裸 Add-Content
    #   （ledger 是**必须共享**的全局台账 ⇒ 按 BLINDSCAN-v3 §3 纪律只能"走真锁"）
    naked = [(i, ln.strip()[:70]) for i, ln in enumerate(src.splitlines(), 1)
             if "Add-Content" in ln.split('#', 1)[0] and "$ledger" in ln.split('#', 1)[0]]
    ledger_calls = [ln for ln in src.splitlines() if "Add-LedgerLine" in ln.split('#', 1)[0]]
    need("F-4 ledger 走 Add-LedgerLine（ledger 上无裸 Add-Content）",
         (not naked) and len(ledger_calls) >= 3,
         f"ledger 上的裸 Add-Content 命中={naked}；Add-LedgerLine 出现数={len(ledger_calls)}（应为 定义1 + 两路各1 = 3）")

    # O-29：`golden-cmd` 必须**条件列**（与 accept-* 同纪律），不得裸列进 subjects 基线。
    #   裸列 ⇒ 无 golden 的卡每 run 记一条 missing-artifact 可重放 gap（实测连续 3 个 run 命中）。
    #   检查法：`golden-cmd` 不得出现在**裸 `$list = @(` 块内** ⇒ 近似判据 = 同一行组里
    #   `golden-cmd` 必须与 `if ($goldenActive)` 同现（见 Get-FrameworkSubjects）。
    g_cond = re.search(r"if \(\$goldenActive\) \{[\s\S]{0,600}?golden-cmd", src)
    g_naked = re.search(r"@\{ name = 'golden-cmd'[\s\S]{0,80}?@\{ name = 'progress-trace'", src)
    need("O-29 golden-cmd 条件列（无 golden 卡不再记 gap）",
         bool(g_cond) and not g_naked,
         f"条件列命中={bool(g_cond)} · 裸列命中={bool(g_naked)} ⇒ 裸列会让无 golden 的卡每 run 记一条 gap")

    # O-29 / D6-P1-1：`framework_version` 必须**成对**（写入侧 + 消费者），且 key 分桶必须**默认不改旧形状**。
    #   两半缺一即禁止（本会话已把它写成 P1-1 检查项："新字段必须核对消费者"）。
    cl = (ROOT / "ops" / "cluster.py").read_text(encoding="utf-8", errors="replace")
    rc = (ROOT / "ops" / "rpc_check.py").read_text(encoding="utf-8", errors="replace")
    w_side = "framework_version = '2'" in src
    c_const = "FRAMEWORK_SUBJECTS_VERSION" in cl
    c_use = "_fwver_set(" in cl and "_FWVER_SCOPE" in cl
    c_safe = '_FWVER_SCOPE = ""' in cl          # 默认空 ⇒ 历史 key 不变（防 18 条假"新增"）
    c_disp = "按框架代分桶" in rc and "FRAMEWORK_SUBJECTS_VERSION" in rc   # 2c 的显示消费者
    need("O-29 framework_version 成对（写入侧 + 消费者 + 默认不改旧形状 + 分桶显示）",
         w_side and c_const and c_use and c_safe and c_disp,
         f"写入侧={w_side} 常量={c_const} 消费={c_use} 默认空={c_safe} 分桶显示={c_disp} ⇒ "
         "缺消费者 = 违反 P1-1 检查项；默认非空 = 存量 key 全变 ⇒ 一次报 18 条假新增")

    # D7-P1-1（水印入仓化）：审计水印必须**在仓内**（inventory/），且不得被 .gitignore 忽略。
    #   依据: docs/research/2026-09-18_证据流审计常跑…md §D-b 的升级条件（"若将来多人/多机，
    #   再升级为入仓"）—— D7 即该条件所指的"多机"。代价是提交摩擦（**这正是留痕来源**）。
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8", errors="replace")
    # ⚠ 按本仓纪律「扫代码文本的断言要区分"代码"与"注释"」：只看**非注释行** ——
    #   否则"已移除此项"的留档注释（含该字串）会让断言**假红**（本会话已犯过一次同型错）。
    gi_code = "\n".join(l for l in gi.splitlines() if not l.lstrip().startswith("#"))
    gi_removed = "ops/.audit-baseline.json" not in gi_code
    path_moved = '"inventory" / "audit-baseline"' in cl and "AGENT_AUDIT_BASELINE_DIR" in cl
    per_host = "_audit_host()" in cl and "load()" in cl   # 按机分片 + 读时并集
    gi_code = "\n".join(l for l in gi.splitlines() if not l.lstrip().startswith("#"))
    gi_removed = "ops/.audit-baseline.json" not in gi_code
    need("D7-P1-1 水印入仓化（inventory/ 分片 + 未被 gitignore + 按机分文件）",
         path_moved and per_host and gi_removed,
         f"路径已改={path_moved} 按机分片={per_host} gitignore 已移除={gi_removed}（只判非注释行）")

    # O-31：claude 备路的**站上临时名**必须带"本次唯一 id"（固定名 ⇒ 同站并发互相覆盖/混写）。
    #   依据 BLINDSCAN-v3 §3 的跨条目纪律：**共享路径要么带 per-invocation 身份、要么走真锁**。
    o31_old = "_p3_claude_in.txt" not in src
    o31_id = "$p3id" in src
    o31_pfx = "${PFX}_in.txt" in src and 'PFX="$4"' in src
    need("O-31 claude 备路站上临时名带唯一 id（且前缀经 $4 传入站上脚本）",
         o31_old and o31_id and o31_pfx,
         f"旧固定名已清除={o31_old} p3id={o31_id} PFX 传递={o31_pfx} ⇒ "
         "固定名会让同站两个备路 run 互踩（O-31）")

    # O-39：**出网档「不适用」与本地档「缺基准」必须分开报**（否则后者**隐身**）。
    #   依据 = 本仓头号失败形态「把两件事说成一件」：混成同一句 MISS ⇒
    #   "出网档本该 MISS"会成为遮住"某本地档一直没测"的**挡箭牌**（真缺口从此无人补）。
    o39_egress = "$modelId -like 'openrouter/*'" in src and "na = $true" in src
    o39_branch = "elseif ($est.na)" in src and "N/A by design" in src
    o39_local = "missing bench row" in src
    need("O-39 出网档『不适用』与本地档『缺基准』分报（不得混成同一句）",
         o39_egress and o39_branch and o39_local,
         f"egress 判定={o39_egress} na 分支={o39_branch} 本地缺基准另有措辞={o39_local}")

    # O-52：glob 采集面的**四条不变量** —— 核心是"glob **不引入**执行用户命令"。
    #   ① 字符集白名单（挡 `'`/`;`/`$` 等元字符，因为 pattern 要送到站上）② 解析出的名字**必须复校验**
    #   ③ 恰好 1 匹配才收（0/>1 拒，**不猜**）④ 枚举命令**固定**（`ls`）+ pattern 单引号包裹 ⇒ 只作参数、不拼接。
    o52_charset = "state-charset" in src and "'^out/[A-Za-z0-9._*?-]+$'" in src
    o52_reglob = "$evmT.glob" in src and "$evmT2.glob" in src
    # ③ O-52② **运行窗口隔离**（2026-09-24 补）：枚举须同时给出"候选"与"本轮窗口(`-nt .run-marker`)"两段。
    #    缺窗口 ⇒ 真实工作区（实测 dogfood `out/` 有 4 个 `.txt`）**必然拒** ⇒ 该能力形同虚设。
    o52_window = "-nt .run-marker" in src and "==CAND==" in src and "==WIN==" in src
    # 决策三态**不猜**：窗口恰 1 → 取；窗口 0 且候选恰 1 → 取（产物由 mv/cp -p 而来、mtime 在窗口外
    #   —— 实测确认过 ⇒ 不能只认窗口，否则**制造回归**）；其余 → 拒。
    o52_rule = ("$gWin.Count -eq 1" in src) and ("$gWin.Count -eq 0 -and $gCand.Count -eq 1" in src)
    # ★ pattern 必须**不加引号**地交给 shell 通配（引号会把 `*` 变字面量 ⇒ 永远 0 匹配，O-52 端到端实测）；
    #   安全由**字符集白名单**承担。此处钉住"以 {1} 注入且未被引号包裹"。
    o52_unquoted = ("for f in {1};" in src) and ("for f in '{1}'" not in src) and ('for f in "{1}"' not in src)
    need("O-52 glob 采集面（字符集白名单 + 解析名复校验 + 运行窗口唯一确定 + 不得加引号）",
         o52_charset and o52_reglob and o52_window and o52_rule and o52_unquoted,
         f"字符集={o52_charset} 复校验={o52_reglob} 窗口={o52_window} 三态规则={o52_rule} "
         f"未加引号={o52_unquoted} ⇒ 缺窗口=脏工作区必拒; 加引号=通配静默失效")

    # O-48（2026-09-24）：**命令位**的 `timeout` 一律带 `-k`。
    #   根因（受控复现）：裸 `timeout` 对**忽略 SIGTERM** 的子进程会**一直等**，不是"到点即杀" ——
    #   `timeout 2 bash -c 'trap "" TERM; sleep 6'` ⇒ rc=124 但**耗时 6s**；加 `-k 1` ⇒ rc=137 **3s**。
    #   ⇒ opencode 挂死（DEBUG 日志卡在流上）时裸 timeout **永不返回**、留孤儿占槽（B 站实测活 17.2h）。
    #   锚点须是**命令位**（行首 / `;`/`&`/`|` / `$(` 之后），否则 `$timeout`、`"…timeout after…"` 会误报。
    bare = []
    for i, ln in enumerate(src.splitlines(), 1):
        code = ln.split('#', 1)[0]
        for m in re.finditer(r"(?:^|[;&|]|\$\()\s*timeout\s+", code):
            tail = code[m.end():]
            if not (tail.startswith("-k") or tail.startswith("--kill-after")):
                bare.append((i, ln.strip()[:80]))
    need("O-48 命令位 `timeout` 一律带 `-k`（无裸 timeout）",
         not bare,
         f"裸 timeout 对忽略 SIGTERM 的子进程**一直等** ⇒ 挂死时永不返回、留孤儿占槽；命中={bare}")

    o48_sites = sum(src.count(x) for x in (
        "timeout -k 10 $timeout opencode run -m",
        "timeout -k 10 $continueTimeout opencode run --continue",
        'timeout -k 10 "$BUDGET" claude',
        "timeout -k 10 $timeoutS opencode run -m"))
    need("O-48 4 处生产派发命令位都已加 `-k`（主路/续跑/claude 备路/judge）",
         o48_sites == 4,
         f"只命中 {o48_sites}/4 ⇒ 有命令位漏改（漏的那个悬挂时永不返回）")

    o48_rc = ("$code -eq 124 -or $code -eq 137" in src) and ("$rc -eq 124 -or $rc -eq 137" in src)
    need("O-48 rc 映射把 `-k` 的 KILL 码 137 与 124 一并归 6",
         o48_rc,
         "加 `-k` 后 KILL 生效时 timeout 返回 137（非 124）⇒ 不归并会让「超时」落成**未映射失败**，"
         "丢掉续跑/备路（且 137 与 OOM 同码，已在注释里留痕说明）")

    print(f"\n静态护栏 {18} 条")
    if fails:
        print("FAIL:")
        for x in fails:
            print("  ✗ " + x)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
