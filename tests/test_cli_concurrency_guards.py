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
- **O-28 RC②**：`$ts` 生成之后**必须**紧跟并发去重（`while (Test-Path …)`）。
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

    # O-28 RC②：ts 之后必须紧跟去重
    need("O-28 RC② $ts 之后紧跟并发去重",
         bool(re.search(r"\$ts = \[DateTime\]::Now\.ToString\('yyyyMMddHHmmssffff'\)[\s\S]{0,900}?while \(Test-Path \(Join-Path \$tsOutRoot", src)),
         "去掉去重 ⇒ 同一时钟滴答内启动的两个进程取到相同 ts ⇒ agent-out/<ts> 与 evidence 临时目录互踩")

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
    }
    temp_names = re.findall(r'Join-Path \$env:TEMP "([^"]+)"', src)
    # ⚠ 字符类必须含 `:` —— 否则 `$Script:RUN_TOKEN` 会在 `:` 处被截断 ⇒ 把"已带身份"误判成"无身份"(假红)。
    tmp_names = re.findall(r"/tmp/([A-Za-z0-9_.$(){}%:\-]+)", src)
    # 已登记待核实项: 允许存在, 但**必须在此显式列出** —— 防"新增未分类路径混进来"。
    #   ⚠ 它们**尚未核实**, 故不进 EXEMPT(豁免要求"确实恒定无害"); 核实后应转 EXEMPT 或修掉。台账见 O-31。
    # 已登记项: 允许存在, 但**必须在此显式列出** —— 防"新增未分类路径混进来"。
    #   · EXEMPT    = **已核实**确实恒定无害(可长期留)
    #   · KNOWN_DEFECTS = **已核实是缺陷, 但本轮未修**(必须带修法; 修掉后应删除本行)
    #   ⚠ 2026-09-23 核实结论(见 O-31): `_p3_claude_{in,out,err}.txt` **是真缺陷** ——
    #     本地 scratch 带 ts([agent-cli.ps1:2527](../../ops/station-bin/agent-cli.ps1)), 但**站上名是固定名**
    #     ([:3016](../../ops/station-bin/agent-cli.ps1) `$rIn='/tmp/_p3_claude_in.txt'`), 且 claude 备路的
    #     站上脚本**不持 flock**([:3019-3050](../../ops/station-bin/agent-cli.ps1)) ⇒ **同站并发两个备路 run 互踩**。
    #     ⇒ 与 F-1/F-2/F-14 **同因**(漏照抄两个样板) ⇒ **第四例**。
    KNOWN_DEFECTS = {
        "_p3_claude_in.txt":  "站上固定名 + 备路无 flock ⇒ 并发互踩。修法: 站上名加 ts/pid, 并让站上脚本从参数取 tmp 前缀",
        "_p3_claude_out.txt": "同上",
        "_p3_claude_err.txt": "同上",
        "_p3_run.sh":         "脚本内容恒定(here-string 常量)+scp 幂等覆盖 ⇒ 可转 EXEMPT; 随上条一并处理",
    }
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
        print(f"  · 已登记(豁免/待核实, 见 O-31): {pend}")

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
    path_moved = '"inventory" / "audit-baseline.json"' in cl
    need("D7-P1-1 水印入仓化（路径在 inventory/ 且未被 gitignore）",
         path_moved and gi_removed,
         f"路径已改={path_moved} gitignore 已移除={gi_removed}（只判非注释行）")

    print(f"\n静态护栏 {12} 条")
    if fails:
        print("FAIL:")
        for x in fails:
            print("  ✗ " + x)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
