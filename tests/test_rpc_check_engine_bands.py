"""`engine` 断言**残留分带**的正反注入（永久护栏，2026-09-24，O-41②）

病根（B2 审计报出 + 读码复核）：旧实现只有两条路 ——
  · `rss >= 2048` 且无引擎端口 ⇒ `detail`(FAIL)
  · 否则                    ⇒ **info「引擎未运行 …… 属正常」**
⇒ **`[1024, 2048)` 这一段完全无声**：一个占 **1.5G** 且不监听任何 `ENGINE_PORTS`
   的 llama 系残留会被判"正常" —— 正是该断言设立时要防的"**内存被占着没干活**"。

修法：新增 `RESIDUAL_WARN_MB = 1024` 预警带 ⇒ 该带报 **WARN**（**不升 FAIL**：
仍可能是"启动中/收尾中"的瞬态，且不阻塞加载）。下沿取 1024 是为了
**不误报 `ggml-rpc-server` 空转(~0.3G)** 这一刻意容忍的情形。

为什么用 monkeypatch 而不真派发：该判据的**注入面**就是三站的「内存读数 + 监听端口」，
而 `_health_probe` 是这两者的**唯一来源** ⇒ 替换它即可**离线**覆盖全部分带
（与 `test_rpc_check_graph.py` 同法：判据纯函数化/可注入，才配得上"正反自证"）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402


def _probe(reachable=True, rss_mb=0, listen=(), error=None, etimes_min_s=None, n_proc=None):
    """构造 `_health_probe` 的返回形状（只含 check_engine 消费的键）。

    ★ O-143（2026-10-03）：`etimes_min_s` / `n_proc` 是**只报数**用的键 —— **不传则不落键**，
    以便用"有/无该键"做**同源对照**（证明报数标记真的由它驱动，不是恒在）。
    """
    d = {"reachable": reachable, "rss_mb": rss_mb, "listen": list(listen), "error": error}
    if etimes_min_s is not None:
        d["etimes_min_s"] = etimes_min_s
    if n_proc is not None:
        d["n_proc"] = n_proc
    return d


def _all(**kw):
    """★ 三站**同参且全可达** —— 否则不可达站会往 detail 里写一条 ⇒ 整项恒 FAIL，
    把"分带判定"这一被测对象整个盖掉（本测试第一版就踩了这个 : 5 条全 FAIL）。"""
    return lambda st: _probe(**kw)


# (说明, A 站探针结果, 期望 verdict, 期望关键词)
CASES = [
    ("★反例 O-41② 修复目标：1536M 无端口（旧实现判 PASS）", _all(rss_mb=1536), "WARN", "疑似残留"),
    ("正例 空转容忍：300M 无端口（ggml-rpc-server 空转量级）", _all(rss_mb=300), "PASS", "属正常"),
    ("正例 真无进程：0M 无端口", _all(rss_mb=0), "PASS", "属正常"),
    ("★反例 FAIL 带：3000M 无端口", _all(rss_mb=3000), "FAIL", "残留"),
    ("正例 在服务：40G 且 8080 在听", _all(rss_mb=40000, listen=["8080"]), "PASS", "在服务"),
    ("★O-143 乙 退回路径：有端口 + RSS 小 + **进程数读不出** ⇒ 退回旧 RSS 口径 ⇒ WARN",
     _all(rss_mb=500, listen=["8080"]), "WARN", "疑似异常进程"),
    # ★★ O-143 **第二步**（2026-10-03「按乙统一口径 + 定档」）：有端口分支改按**进程数**判 ——
    #   判据依据（实测）: A 站 13h / RSS 208M / 推理 56.6 t/s / GTT 68.75G ⇒ "有端口 + RSS 小"**不足以**判异常
    ("★O-143 乙：有端口 + n_proc=1（RSS 208M 但引擎在服务）⇒ **PASS**（不再假报；报数仍在）",
     _all(rss_mb=208, listen=["8080"], etimes_min_s=46698, n_proc=1), "PASS", "最短进程龄 46698s"),
    ("★O-143 乙：有端口 + **无** llama 系进程（n_proc=0）⇒ WARN（真·端口被占）",
     _all(rss_mb=500, listen=["8080"], etimes_min_s=0, n_proc=0), "WARN", "疑似端口被占"),
    ("★反例 三站全不可达（旧 O-41 称'不阻断'，实测应 FAIL）",
     lambda st: _probe(reachable=False, error="unreachable"), "FAIL", "不可达"),
]


def _run(case):
    desc, probe, want, kw = case
    orig = R._health_probe
    R._health_probe = probe
    try:
        got, note, details = R.check_engine(None)
    finally:
        R._health_probe = orig
    blob = note + " " + " ".join(details)
    ok = (got == want) and (kw in blob)
    return desc, ok, f"verdict={got}(期望 {want}) · 关键词'{kw}':{'在' if kw in blob else '缺'}", note


def main() -> int:
    fails = []
    for case in CASES:
        desc, ok, info, note = _run(case)
        if not ok:
            fails.append(f"{desc} ⇒ {info}")
        print(f"  {'ok  ' if ok else 'FAIL'} {desc}\n        {info}")

    # 结构性护栏：两条阈值必须同时存在且有序 —— 少了 WARN 带就退回"无声放过"，
    # 顺序颠倒则 WARN 带永不触发（都会让本护栏的用例失去意义）。
    if not hasattr(R, "RESIDUAL_WARN_MB"):
        fails.append("缺 RESIDUAL_WARN_MB ⇒ 预警带消失，O-41② 会复发（无声判正常）")
    elif not (R.RESIDUAL_WARN_MB < R.RESIDUAL_RSS_MB):
        fails.append(f"阈值顺序错：RESIDUAL_WARN_MB={R.RESIDUAL_WARN_MB} 必须 < "
                     f"RESIDUAL_RSS_MB={R.RESIDUAL_RSS_MB}（否则 WARN 带永不触发）")

    # ★★ 口径护栏（O-143 **第二步**「按乙统一口径 + 定档」，2026-10-03）：
    #   ① 判定必须**集中在一处** ⇒ 断言 `classify_engine_band` 存在（唯一定义点）；
    #   ② 对**三种 n_proc 情形**各钉一条：>=1 ⇒ 在服务 · ==0 ⇒ 疑似端口被占 · 读不出 ⇒ **退回旧口径**。
    #   ★ 判据依据（实测，非凭空）: A 站 **13h** / RSS **208M** / 推理 **56.6 t/s** / GTT **68.75 GiB**
    #     ⇒ "有端口 + RSS 小"**不足以**判异常（RSS 不是"引擎在不在服务"的证据）。
    if not hasattr(R, "classify_engine_band"):
        fails.append("缺 classify_engine_band ⇒ 口径未集中，O-143 的两半会再次分叉")

    def _verdict(probe):
        orig = R._health_probe
        R._health_probe = probe
        try:
            return R.check_engine(None)
        finally:
            R._health_probe = orig

    try:
        v1, n1, _ = _verdict(_all(rss_mb=208, listen=["8080"], etimes_min_s=46698, n_proc=1))
        v2, _, _ = _verdict(_all(rss_mb=208, listen=["8080"], n_proc=2))
        v0, _, _ = _verdict(_all(rss_mb=208, listen=["8080"], n_proc=0))
        vx, _, _ = _verdict(_all(rss_mb=208, listen=["8080"]))          # 进程数读不出
    except Exception as e:  # noqa: BLE001 — 判定集中化不该引入新的崩溃面
        fails.append(f"O-143 乙 引入异常：{type(e).__name__}: {e}")
    else:
        if v1 != "PASS":
            fails.append(f"n_proc=1（在服务）应判 PASS，实得 {v1}")
        if v2 != "PASS" or v1 != v2:
            fails.append(f"n_proc>0 的两种取值应同判 PASS（{v1} / {v2}）—— 判定不该随进程数漂")
        if "最短进程龄 46698s" not in n1:
            fails.append(f"报数应仍在（最短进程龄），实得 note={n1!r}")
        if v0 != "WARN":
            fails.append(f"n_proc=0（无 llama 系进程）应判 WARN「疑似端口被占」，实得 {v0}")
        if vx != "WARN":
            fails.append(f"进程数读不出时应**退回**旧 RSS 口径 WARN（判不了不静默通过），实得 {vx}")

    print(f"RESULT: {len(CASES) - len(fails)}/{len(CASES)} 通过" if not fails
          else f"RESULT: 失败 {len(fails)} 条")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
