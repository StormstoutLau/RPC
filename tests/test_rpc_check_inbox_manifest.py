"""`MANIFEST.sha256` 的 `parse_manifest` / `verify_manifest` 正反夹测 —— 永久护栏（D6-P1-1 §11.1-C）

事实源 = 项目根 `agent-out/<ts>/`；生成物 = `inbox/<proj>/30_evidence/MANIFEST.sha256`。
⭐ **纯函数**（注入 `read_bytes`）⇒ 离线可正反夹测，**不碰真文件、不碰站**。
⭐ 这两函数是**唯一实现**：CLI `cluster.py inbox seal --check` 与门禁 `inbox` 断言共用。
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import cluster as C  # noqa: E402

ROOTDIR = r"D:\proj-x"
GOOD = b"GLOB_PROBE_OK\n"
H = hashlib.sha256(GOOD).hexdigest()

MANIFEST = (
    "# MANIFEST.sha256 — 30_evidence 交付证据束 (ADR-0008 §5.1)\n"
    f"# 受理目录: inbox/proj-x-2026-01-01    项目根: {ROOTDIR}    交付分级: Reproduced\n"
    "# 生成时间: 2026-01-01T00:00:00+08:00    件数: 1    run: 111\n"
    f"{H}  agent-out/111/a.txt\n"
)


def main() -> int:
    fails = []

    # ① 解析：头注释带出项目根；数据行 = (sha, rel)
    root, entries = C.parse_manifest(MANIFEST)
    if root != ROOTDIR or entries != [(H, "agent-out/111/a.txt")]:
        fails.append(f"parse_manifest 不对: root={root!r} entries={entries}")
    else:
        print("  ok   parse_manifest：项目根 + 1 条数据行")

    # ② 头里**没有**「项目根:」⇒ root=None（**不猜** ⇒ verify 会把每条判成"读不到"）
    r2, _ = C.parse_manifest("# 无项目根行\n" + f"{H}  agent-out/111/a.txt\n")
    if r2 is not None:
        fails.append(f"缺项目根时应为 None: {r2!r}")
    else:
        print("  ok   缺『项目根:』⇒ root=None（不猜）")

    # ③ 真实基线（注入真内容）⇒ 逐条一致
    _r3, ok3, miss3, bad3 = C.verify_manifest(MANIFEST, lambda p: GOOD)
    if bad3 or ok3 != 1 or miss3 != 0:
        fails.append(f"基线不干净: ok={ok3} miss={miss3} bad={bad3}")
    else:
        print("  ok   基线：1 件逐条一致")

    # ④ ★ 内容被手改 ⇒ 必须点名「哈希不符」（+ 带相对路径）
    _r4, _o4, _m4, bad4 = C.verify_manifest(MANIFEST, lambda p: b"TAMPERED\n")
    ok4 = len(bad4) == 1 and "哈希不符" in bad4[0] and "agent-out/111/a.txt" in bad4[0]
    print(f"  {'ok  ' if ok4 else 'FAIL'} [负例1] 内容被手改 ⇒ 点名哈希不符：{'在' if ok4 else '缺'}")
    if not ok4:
        fails.append(f"负例1 未点名: {bad4}")

    # ⑤ ★ 件缺失（或项目根不在本机）⇒ 必须点名「读不到」，不得静默通过
    def _boom(p):
        raise FileNotFoundError(str(p))
    _r5, _o5, miss5, bad5 = C.verify_manifest(MANIFEST, _boom)
    ok5 = miss5 == 1 and any("读不到" in b for b in bad5)
    print(f"  {'ok  ' if ok5 else 'FAIL'} [负例2] 件缺失 ⇒ 点名读不到：{'在' if ok5 else '缺'}")
    if not ok5:
        fails.append(f"负例2 未点名: {bad5}")

    # ⑥ 结构护栏：门禁有 id='inbox'（否则 artifacts.yaml 的 `check: inbox` 会成"挂名假判"）
    import rpc_check as R  # noqa: E402
    if "inbox" not in {c["id"] for c in R.CHECKS}:
        fails.append("CHECKS 里没有 id='inbox'（artifacts.yaml 的 check: inbox 会成挂名假判）")
    else:
        print("  ok   结构护栏：'inbox' 已在 CHECKS 注册")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
