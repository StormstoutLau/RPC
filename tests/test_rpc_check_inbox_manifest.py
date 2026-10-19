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

    # ── ⑦ ★★ `U1#7` 裁定落地（2026-10-19）：**双轨**（字节清单 + u1 身份轨）────────────
    # 裁 = 用户「按照建议执行」：`ns=rpc_inbox` · `id` = 清单数据行的相对路径 · `ver=0.0.0`。
    # ★ 本段的核心不是"能写"，而是两条**边界**：① **旧清单零影响**（声明制 ⇒ 不追溯改历史）；
    #   ② **身份复算**（格式合规的假身份也要拦 ⇒ 判据不是格式判）。
    DECL = C._u1_decl_line()          # `# u1:<algo>:<trunc>` —— **不硬编码 32**（拼法来自 rpc_check）
    REL = "agent-out/111/a.txt"
    ID1 = C._u1_identity(REL)
    HEAD = (f"# 受理目录: inbox/proj-x-2026-01-01    项目根: {ROOTDIR}    交付分级: Reproduced\n"
            f"# 生成时间: 2026-01-01T00:00:00+08:00    件数: 1    run: 111\n")
    _GOOD = lambda p: GOOD                                            # noqa: E731（注入"读得到"）

    # ⑦-0 ★ 旧清单（无声明、无身份行）⇒ 解析器**一个字都不报**（本会话先验红真抓到过这条：
    #   首稿"每条数据行都要有身份行"是**无条件**执行的 ⇒ 旧束当场判红 = 追溯改历史）
    d0, p0, e0 = C.parse_u1_track(MANIFEST)
    ok = (d0 is False and p0 == [] and e0 == [])
    print(f"  {'ok  ' if ok else 'FAIL'} [轨·回归] 旧清单：不声称的轨 ⇒ 不严判、零报错")
    if not ok:
        fails.append(f"旧清单被严判了（追溯改历史的入口）: declared={d0} pairs={p0} errors={e0}")

    # ⑦-1 声明 + 双轨齐 + 身份**正确** ⇒ 绿（默认 identity_of = rpc_check 的唯一真值）
    M_OK = HEAD + DECL + "\n" + f"# {ID1}\n{H}  {REL}\n"
    d1, p1, e1 = C.parse_u1_track(M_OK)
    _r, _o, _m, bad1 = C.verify_manifest(M_OK, read_bytes=_GOOD)
    ok = (d1 is True and p1 == [(ID1, REL)] and e1 == [] and bad1 == [])
    print(f"  {'ok  ' if ok else 'FAIL'} [轨·正例] 声明 + 双轨齐 + 身份复算相符 ⇒ 绿")
    if not ok:
        fails.append(f"双轨正例不过: declared={d1} pairs={p1} errors={e1} bad={bad1}")

    # ⑦-2 ★ 声明 + **缺身份行** ⇒ 点名缺轨（"双写缺任一轨 ⇒ 红"）
    M_MISS = HEAD + DECL + "\n" + f"{H}  {REL}\n"
    _d, _p, e2 = C.parse_u1_track(M_MISS)
    _r, _o, _m, bad2 = C.verify_manifest(M_MISS, read_bytes=_GOOD)
    ok = any("缺 u1 轨" in x for x in e2) and any("缺 u1 轨" in x for x in bad2)
    print(f"  {'ok  ' if ok else 'FAIL'} [轨·负例1] 声明了却缺身份行 ⇒ 点名缺轨")
    if not ok:
        fails.append(f"缺轨未点名: errors={e2} bad={bad2}")

    # ⑦-3 ★★ **身份复算**：格式合规的**假身份**必须被判红 —— 且"同源对照两向"：
    #   同一份清单，**把身份改成正确值 ⇒ 绿**（⑦-1）⇒ 证明咬住它的**是复算**，不是别的
    FAKE = f"{C._u1_identity('x').rsplit(':', 1)[0]}:" + "deadbeef" * (len(ID1.rsplit(':', 1)[1]) // 8)
    M_FAKE = HEAD + DECL + "\n" + f"# {FAKE}\n{H}  {REL}\n"
    _r, _o, _m, bad3 = C.verify_manifest(M_FAKE, read_bytes=_GOOD)
    ok = any("复算不符" in x and REL in x for x in bad3)
    print(f"  {'ok  ' if ok else 'FAIL'} [轨·负例2] 格式合规的假身份 ⇒ 复算判红（非格式判）")
    if not ok:
        fails.append(f"假身份未被复算拦下: bad={bad3}（fake={FAKE}）")

    # ⑦-4 身份行**后面没有数据行** ⇒ 点名身份悬空（不许静默）
    _d, _p, e4 = C.parse_u1_track(HEAD + DECL + "\n" + f"# {ID1}\n")
    ok = any("身份悬空" in x for x in e4)
    print(f"  {'ok  ' if ok else 'FAIL'} [轨·负例3] 身份行后无数据行 ⇒ 点名悬空")
    if not ok:
        fails.append(f"悬空身份未点名: {e4}")

    # ⑦-5 有 u1 行却**没有声明行** ⇒ 轨不自描述（半拉子清单不许混过去）
    _d, _p, e5 = C.parse_u1_track(HEAD + f"# {ID1}\n{H}  {REL}\n")
    ok = any("不自描述" in x for x in e5)
    print(f"  {'ok  ' if ok else 'FAIL'} [轨·负例4] 有身份行却没有声明行 ⇒ 轨不自描述")
    if not ok:
        fails.append(f"半拉子清单未点名: {e5}")

    # ⑦-6 声明了却**零数据行** ⇒ 判据没有对象（防退化空判）
    _r, _o, _m, bad6 = C.verify_manifest(HEAD + DECL + "\n", read_bytes=_GOOD)
    ok = any("零数据行" in x for x in bad6)
    print(f"  {'ok  ' if ok else 'FAIL'} [轨·负例5] 声明了 u1 轨但零条目 ⇒ 点名空判")
    if not ok:
        fails.append(f"空轨未点名: {bad6}")

    # ⑦-7 ★ 结构护栏：生产者侧**真的**产双轨（否则上面全是"能读不能写"的空判）
    src = __import__("inspect").getsource(C._inbox_seal)
    ok = ("_u1_identity" in src and "_u1_decl_line" in src)
    print(f"  {'ok  ' if ok else 'FAIL'} 结构护栏：`_inbox_seal` 真的调用 u1 两件（身份行 + 声明行）")
    if not ok:
        fails.append("`_inbox_seal` 没产 u1 轨 ⇒ 判据只读不写（挂名假判）")
    # 拼法**唯一**：声明行由 rpc_check 给（这里若自拼 32，改截断就会两处漂移）
    if C._u1_decl_line() != R.u1_header_line():
        fails.append(f"声明行拼法不是同一处: {C._u1_decl_line()!r} vs {R.u1_header_line()!r}")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
