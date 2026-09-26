#!/usr/bin/env python3
"""`ops/id_storage_census.py` 的测试 —— **形态分类 + 角色判据 + 输入语义**（2026-09-26 · U-4）

为什么必须有：
  · U-4 的 `affected` 一直是**手工开库数**出来的 ⇒ 本文件给那个脚本钉住口径；
  · ★ 而且 U-4 的判据库 `decide_invalidation()` 有一个**极易写错**的语义：
    `affected=[]`（**已判定为空**）与 `affected=None`（**判不了**）**不是一回事** ——
    写成 `affected or None` 会把"已知为空"错误升格成 H-3（判不了）⇒ **白白付一次全量**。
    这条已在本文件里**钉住**（`test_empty_affected_is_not_unknown`）。

⚠ **本文件自带 `__main__` 入口**：门禁 `py-tests` 以**脚本**方式调用（只认退出码）。
  没有它 ⇒ 被 import、定义一堆 `test_*`、正常退出 0 ⇒ 门禁报 PASS 而**一条都没跑**
  （`tests/test_rpc_check_u1.py` 就这么**整整一个版本**没跑过，2026-09-26 实测发现）。
"""
import contextlib
import io
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import id_storage_census as C  # noqa: E402
import rpc_check as R          # noqa: E402


# ── ① 形态分类：U-1 那一档必须**与实现同源** ────────────────────────────────
def test_classify_u1_uses_the_real_judge():
    """★ U-1 形态**必须**由 `rpc_check.u1_parse` 判（不另写正则 ⇒ 不做第二个定义点）。"""
    real = R.u1_identity("rpc", "inventory/edges.yaml", "0.0.0")
    assert C.classify(real) == C.SHAPE_U1, "真身份必须被判成 U-1"
    # ★ 反例（**最有信息量的一条**）：格式完整、前缀自描述，但**截断长度不是当前取值**
    #   ⇒ 必须**不**算 U-1。若有人把 classify 改成"看到 `u1:` 前缀就放过"，这条立刻红。
    stale = "u1:sha256:16:" + "0" * 16
    assert C.classify(stale) != C.SHAPE_U1, "前缀对但截断不符 ⇒ **不得**算 U-1（否则退化成只看前缀）"


def test_classify_shapes():
    assert C.classify("0" * 32) == C.SHAPE_SHA256_32
    assert C.classify("0" * 64) == C.SHAPE_OTHER_HEX
    assert C.classify("v_" + "0" * 12) == C.SHAPE_PREFIXED
    assert C.classify("u_" + "0" * 16) == C.SHAPE_PREFIXED
    assert C.classify("") == C.SHAPE_EMPTY
    assert C.classify(None) == C.SHAPE_EMPTY
    assert C.classify("hello") == "非 hex"


def test_classify_distinguishes_u1_from_bare_32hex():
    """本仓当前：Open_Data 的 `event_id` 是**裸 32hex**（无前缀）⇒ 与 U-1 **不同档**。

    这正是迁移要读的东西：形态告诉你"还差什么"（差前缀）。
    """
    assert C.classify("a" * 32) == C.SHAPE_SHA256_32
    assert C.classify("a" * 32) != C.SHAPE_U1


# ── ② ★ 角色判据：**声明的 role 必须回库里核**（声明 ≠ 事实） ─────────────────
def _with_fake_truth(truth, fake_stores):
    """把 `mod.CENSUS` 换成临时真值、`mod.census()` 换成给定实测 —— 调 check()。"""
    import yaml
    old_census, old_fn = C.CENSUS, C.census
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "c.yaml"
        p.write_text(yaml.safe_dump(truth, allow_unicode=True), encoding="utf-8")
        C.CENSUS = p
        C.census = lambda verbose=False: fake_stores
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = C.check()
            return rc, buf.getvalue()
        finally:
            C.CENSUS, C.census = old_census, old_fn


def _truth(role="primary_key", rows=1, distinct=1):
    return {"metric": {"shape_sample_limit": C.MAX_SHAPE_SAMPLE,
                       "role_domain": ["primary_key", "record_key"]},
            "stores": [{"project": "P", "kind": "sqlite", "path": "x", "table": "t",
                        "column": "c", "declared_role": role, "reachable": True,
                        "rows": rows, "distinct": distinct}]}


def _measured(is_pk, rows=1, distinct=1):
    return [{"project": "P", "kind": "sqlite", "path": "x", "table": "t", "column": "c",
             "declared_role": "primary_key", "reachable": True, "ok": True,
             "rows": rows, "distinct": distinct, "is_primary_key": is_pk,
             "shape": {C.SHAPE_SHA256_32: rows}, "shape_sampled": False}]


def test_role_mismatch_is_red():
    """★ **声明 primary_key、库里却不是** ⇒ 判红（这是"声明 ≠ 事实"的唯一机判位）。"""
    rc, out = _with_fake_truth(_truth(), _measured(is_pk=False))
    assert rc == C.EXIT_MISMATCH, f"角色不实应当判红，实际 rc={rc}"
    assert "primary_key" in out and "不是" in out


def test_role_match_is_green():
    rc, _ = _with_fake_truth(_truth(), _measured(is_pk=True))
    assert rc == C.EXIT_OK


def test_row_mismatch_is_red():
    rc, out = _with_fake_truth(_truth(rows=1), _measured(is_pk=True, rows=2))
    assert rc == C.EXIT_MISMATCH and "≠" in out


def test_unreachable_is_degraded_not_pass():
    """★ 存储不可达 ⇒ **degraded（既不 PASS 也不 FAIL）** —— 降级必须可见，不许静默通过。"""
    rc, out = _with_fake_truth(_truth(), [{"project": "P", "kind": "sqlite", "path": "x",
                                           "table": "t", "column": "c",
                                           "declared_role": "primary_key", "reachable": False}])
    assert rc == C.EXIT_DEGRADED and "不可达" in out


def test_metric_drift_is_red():
    """口径漂移（取样上限变了）⇒ 判红，且**优先于**数值不符报。"""
    t = _truth()
    t["metric"]["shape_sample_limit"] = C.MAX_SHAPE_SAMPLE + 1
    rc, out = _with_fake_truth(t, _measured(is_pk=True))
    assert rc == C.EXIT_MISMATCH and "口径已漂移" in out


# ── ③ ★★ 输入语义：`affected=[]` ≠ `affected=None`（本次真实踩过的坑） ─────────
def test_empty_affected_is_not_unknown():
    """★★ **空列表 = 已判定为空；None = 判不了。** 二者不得混。

    ⚠ 一手教训：我在 `--invalidate` 里写过 `affected=[...] or None` ⇒
      把"**已判定为空**"错误升格成"**判不了**"，于是**白白付一次全量**。
      ⇒ 这条测试就是那次错误的回归闸。
    """
    empty = R.decide_invalidation(changed_ids=["u1:x"], affected=[], affected_is_closure=True,
                                 incremental_equivalent=False)
    unknown = R.decide_invalidation(changed_ids=["u1:x"], affected=None, affected_is_closure=True,
                                    incremental_equivalent=False)
    assert "H-3" not in empty[2], "空列表**不得**走 H-3（那是'判不了'才有的）"
    assert "H-3" in unknown[2], "None 才是 H-3 的触发条件"
    assert empty[2] != unknown[2], "两种输入**必须**给出不同的理由（否则就是混成一个）"
    # ⚠ **O-88（2026-09-26）改的是这一行**：原断言 `"H-1" in empty[2]`（"空列表应当继续往下走，
    #   落到 H-1"）—— 那**描述的正是 O-88 那个缺口**（为"没有下游"付一次全量，**期望陈旧**）。
    #   空集 ∧ 已闭包 = **已判定「确实无下游」** ⇒ 正确归宿是 `none`/`MODE_SKIP`，不是 H-1。
    assert "确实无下游" in empty[2], "空列表 ∧ 已闭包 = 已判定无下游（不是 H-1 的'未证'）"
    assert empty[1] == "MODE_SKIP", f"空列表 ∧ 已闭包应当落到 MODE_SKIP，实际 {empty[1]}"


def test_mode_skip_has_exactly_two_decided_classes():
    """允许落到 `MODE_SKIP` 的**两类**（都是"**已判定**"，都不是"判不了"）：

      ① `changed_ids` 为空 —— 真的没事；
      ② ★ O-88（2026-09-26）：**有变更**但 `affected=[] ∧ affected_is_closure=True` —— 确实无下游。
    ⚠ 原先本测试叫 `..._is_the_only_mode_skip`（"**唯一**"）—— 那个"唯一"随 O-88 作废。
    """
    action, class_, reason = R.decide_invalidation(changed_ids=[], affected=None)
    assert (action, class_) == ("none", "MODE_SKIP")
    assert "确实无需动作" in reason
    action2, class2, reason2 = R.decide_invalidation(
        changed_ids=["u1:x"], affected=[], affected_is_closure=True, incremental_equivalent=False)
    assert (action2, class2) == ("none", "MODE_SKIP")
    assert "确实无下游" in reason2
    # ★ 三类**保守**输入仍一律不许 skip（否则第二类就成了"给判不了开口子"）
    for kw in ({"affected": [], "affected_is_closure": False},
               {"affected": None}):
        _, c, _ = R.decide_invalidation(changed_ids=["u1:x"], **kw)
        assert c != "MODE_SKIP", f"保守路径被放宽了: {kw}"


def test_no_judgment_falls_into_mode_skip():
    """★ 硬不变量：**任何"判不了"都不得落到 MODE_SKIP**（那正是"静默 skip"的形态）。

    ⚠ **O-88（2026-09-26）后射程精确化**：原先把 `affected=[]`（默认 `closure=False`）与
      `{"affected": [], "incremental_equivalent": False}` 都当作"判不了"列在这里 ——
      现在 `[] ∧ 已闭包` 是**已判定**（合法 MODE_SKIP），故**移出本测试**，
      并**补两条反例**证明本断言**没有变成恒真**（H-1 的射程 = **有下游时**才看等价性）。
    """
    for kw in ({"affected": None},                                    # H-3 判不了
               {"affected": [], "affected_is_closure": False},        # 空但**未闭包化** ⇒ 保守
               {"affected": ["a"], "incremental_equivalent": False},  # ★ 反例：有下游且未证 ⇒ H-1
               {"affected": ["a"], "affected_is_closure": False}):    # ★ 反例：有下游未闭包 ⇒ H-2
        _, class_, _ = R.decide_invalidation(changed_ids=["u1:x"], **kw)
        assert class_ != "MODE_SKIP", f"判不了却报 MODE_SKIP: {kw}"


# ── ④ 入口自检（把刚才的教训变成断言） ──────────────────────────────────────
def test_runner_entry_exists():
    """★ 门禁以**脚本**方式跑本文件 ⇒ 必须有 `_run_all` 且 `__main__` 调它。

    没有它 ⇒ 门禁报 PASS 而**一条都没跑**（`test_rpc_check_u1.py` 的前车之鉴）。
    """
    src = (ROOT / "tests" / "test_rpc_check_u1.py").read_text(encoding="utf-8")
    assert "def _run_all" in src and '__name__ == "__main__"' in src, \
        "test_rpc_check_u1.py 必须**自带自跑入口**（否则它在门禁里是静的）"


# ── 无 pytest 的自跑入口（本文件自己也要有！） ──────────────────────────────
def _run_all() -> int:
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    fails = []
    for name, fn in tests:
        try:
            fn()
        except AssertionError as e:
            fails.append(name)
            print(f"  FAIL {name}: assert 失败 {e or ''}".rstrip())
        except Exception as e:
            fails.append(name)
            print(f"  FAIL {name}: {type(e).__name__}: {e}")
        else:
            print(f"  ok   {name}")
    print()
    if not tests:
        print("RESULT: FAIL 未发现任何 test_* 函数（入口本身坏了）")
        return 1
    print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED -> {fails}")
    print(f"  （{len(tests) - len(fails)}/{len(tests)} 通过）")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(_run_all())
