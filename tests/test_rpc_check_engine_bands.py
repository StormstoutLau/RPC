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


def _probe(reachable=True, rss_mb=0, listen=(), error=None):
    """构造 `_health_probe` 的返回形状（只含 check_engine 消费的键）。"""
    return {"reachable": reachable, "rss_mb": rss_mb, "listen": list(listen), "error": error}


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
    ("★反例 端口在听但 RSS 过小：500M + 8080", _all(rss_mb=500, listen=["8080"]), "WARN", "疑似异常进程"),
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

    print(f"RESULT: {len(CASES) - len(fails)}/{len(CASES)} 通过" if not fails
          else f"RESULT: 失败 {len(fails)} 条")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
