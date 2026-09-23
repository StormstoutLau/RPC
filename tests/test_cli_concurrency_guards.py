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

    print(f"\n静态护栏 {7} 条")
    if fails:
        print("FAIL:")
        for x in fails:
            print("  ✗ " + x)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
