"""项目注册表（`ops/rpc_check.py` 的 `validate_projects` / `projects_index`）—— 正反用例 + **先验红**（2026-10-13）

背景：`$PROJECTS` 从 `agent-cli.ps1` 的**硬编码常量表**改为 **`inventory/projects.yaml` 注册表**
（⇒ 接入一个仓库不再改内核关键路径；`ADR-0013` §「两个前置」①）。
设计见 `docs/2026-10-13_项目注册表_PROJECTS数据化_设计与实施方案.md`。

本文件钉住两件事：
  ① **真值文件自洽**（`validate_projects` 对**真文件**必过）—— 否则门禁 `projects` 与外壳载入会一起炸；
  ② **判据本身不是恒真**：反例族（每条治理规则一条）+ **先验红自证**。

⚠★ 本文件**不判 `root` 存在性**（设计 D3：`F:`/`E:` 外盘可能离线 ⇒ 判存在性=**假红**）；
  故反例里**故意**用不存在的 root，仍应 PASS（下面 `test_nonexistent_root_still_passes`）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402


def _reg(items):
    return {"projects": items}


def _p(pid, root="X:\\x", status="active", since="2026-09-14"):
    return {"id": pid, "root": root, "status": status, "since": since}


# ── ① 正例：真值文件必须自洽 ─────────────────────────────────────────────
def test_real_registry_is_self_consistent():
    import yaml
    reg = yaml.safe_load(R.PROJECTS_REG.read_text(encoding="utf-8")) or {}
    bad, notes = R.validate_projects(reg)
    assert bad == [], f"真实注册表不自洽: {bad}"
    assert R.projects_index(reg), "projects_index 为空 ⇒ 外壳载入会得到空表（命令全部不可用）"


def test_real_registry_keys_are_exactly_the_legacy_four():
    """★ 行为中性（本批的核心验收）：active 的 `id` 集合**逐字等于** 2026-09-23 硬编码的 4 键，根值逐字相同。"""
    import yaml
    reg = yaml.safe_load(R.PROJECTS_REG.read_text(encoding="utf-8")) or {}
    idx = R.projects_index(reg)
    assert set(idx) == {"paper", "Cpp_Hub", "Auto_Prover", "dogfood"}, f"键集变了: {set(idx)}"
    assert idx["paper"] == "D:\\Paper"
    assert idx["Cpp_Hub"] == "F:\\Cpp_Hub"
    assert idx["Auto_Prover"] == "F:\\Auto_Prover"
    assert idx["dogfood"] == "d:\\RPC\\tmp\\dogfood-ws"


def test_cluster_proj_roots_reads_registry_not_the_empty_literal():
    """★ 第二个消费面（`cluster._agent_proj_roots`，证据链详情列用）**必须是同一真值源**。

    2026-10-13 数据化后 `agent-cli.ps1` 的 `$Script:PROJECTS` 已是**空表 + 载入** ⇒ 旧的正则
    静态解析只会读到空表。**实测过**：门禁 `evidence` 曾退化为「$Script:PROJECTS 解析为空」
    = 详情列不可用（一次真实回归）。本用例钉住：它**改走注册表**且键集/根值仍与真值一致。
    """
    import cluster as C
    roots, note = C._agent_proj_roots()
    assert note == "", f"不该降级（详情列不可用）: {note!r}"
    assert set(roots) == {"paper", "Cpp_Hub", "Auto_Prover", "dogfood"}, f"键集变了: {set(roots)}"
    assert roots["paper"] == Path("D:\\Paper")


# ── ② 反例族：每条治理规则各一条会红的用例 ───────────────────────────────
def test_empty_projects_fails():
    bad, _ = R.validate_projects(_reg([]))
    assert any("为空" in b for b in bad), "空表必须红（否则判据退化 = 无对象）"


def test_missing_id_fails():
    bad, _ = R.validate_projects(_reg([{"root": "X:\\x", "status": "active", "since": "2026-09-14"}]))
    assert any("缺 `id`" in b for b in bad)


def test_bad_status_fails():
    bad, _ = R.validate_projects(_reg([_p("a", status="zombie")]))
    assert any("不在闭集" in b for b in bad)


def test_bad_since_fails():
    bad, _ = R.validate_projects(_reg([_p("a", since="2026/09/14")]))
    assert any("since" in b for b in bad)


def test_empty_root_fails():
    bad, _ = R.validate_projects(_reg([_p("a", root="   ")]))
    assert any("root" in b for b in bad)


def test_conflicting_id_fails():
    """★ 治理规则②：同一个串不许属两条（id 冲突）。"""
    bad, _ = R.validate_projects(_reg([_p("a"), _p("a", root="Y:\\y")]))
    assert any("冲突" in b for b in bad)


def test_conflict_via_alias_fails():
    bad, _ = R.validate_projects(_reg([
        _p("a"), {"id": "b", "root": "X:\\x", "status": "active", "since": "2026-09-14",
                  "aliases": ["a"]}]))
    assert any("冲突" in b for b in bad)


# ── ③ ★ 不判 root 存在性（D3）─────────────────────────────────────────────
def test_nonexistent_root_still_passes():
    bad, _ = R.validate_projects(_reg([_p("a", root="Z:\\definitely-not-here")]))
    assert bad == [], "判了 root 存在性 ⇒ 外盘离线时门禁会**假红**（D3 明确禁止）"


# ── ④ projects_index 只收 active（退役不许再派发）──────────────────────────
def test_index_excludes_retired():
    idx = R.projects_index(_reg([_p("a", status="active"), _p("b", root="Y:\\y", status="retired")]))
    assert set(idx) == {"a"}, f"retired 混进了消费面: {set(idx)}"


# ── ⑤ ★ **先验红自证**：判据有分辨力（恒真桩会被抓）──────────────────────
def test_prered_always_pass_stub_is_distinguishable():
    """★ 先验红：一个**恒说自洽**的假桩可通过空表，而**真判据必须红** ⇒ 上面的反例族不是装饰。

    ⚠ 若有人把 `validate_projects` 换成"恒返回 `([], [...])`"的桩，本行立刻红。
    """
    def stub(_):
        return [], ["stub 永远说自洽"]
    assert stub(_reg([]))[0] == []                    # 假桩：空表也"自洽"
    assert R.validate_projects(_reg([]))[0] != []     # 真判据：空表**必须**红 ⇒ 分辨力成立


# ── ⑥ ★ 无 pytest 的自跑入口（门禁 `py-tests` 以**脚本**方式调用本文件）────
#   ⚠ 没有它 ⇒ 被 import 后定义一堆 test_* 再正常退出 0 ⇒ 门禁报 PASS 而**一条没跑**
#     （本仓实测过一次，见 tests/test_rpc_check_u1.py 的 `_run_all` docstring）。
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
        except Exception as e:                      # 非断言异常同样是失败（不许静默）
            fails.append(name)
            print(f"  FAIL {name}: {type(e).__name__}: {e}")
        else:
            print(f"  ok   {name}")
    ok = len(tests) - len(fails)
    print()
    if not tests:
        print("RESULT: FAIL 未发现任何 test_* 函数（入口本身坏了）")
        return 1
    print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED -> {fails}")
    print(f"  （{ok}/{len(tests)} 通过）")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(_run_all())
