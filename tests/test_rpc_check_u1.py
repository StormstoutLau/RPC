"""U-1 产物身份（`ops/rpc_check.py` 的 `u1_*`）—— **已知向量 + 先验红**（2026-09-26）

为什么必须有这个文件：`spec/d6-agent-standard/U1-ARTIFACT-IDENTITY.md` 末节记着两条**未实测**：
  ① "**规范化 JSON 数组**作为哈希输入：**从未在任何出处实现过**，只存在于文档里"；
  ② "**头部注释前缀 `# u1:sha256:<截断>`**：**从未在任何清单 / 索引文件里写过**"。
⇒ 本文件把 ① 变成**可复算**；② 由 `inventory/dialect.yaml` / `inventory/edges.yaml` 的**真实声明**消掉
  （判据 = 门禁 `u1-identity`，它**复算**而不只看格式）。

⚠ 本文件的立场：只判"有个 `u1:` 前缀"是**假绿**（随手编一个合规长度的 hex 就能过）⇒
  下面既有正例，也有**反例族**，还有一条**先验红自证**（证明"复算"这条判据不是恒真）。
⚠⚠ **不硬编码截断长度**：算法 / 截断一律从 `R.U1_ALGO` / `R.U1_TRUNC` 取 ——
  否则改一次取值（如 2026-09-26 的 `16`→`32`，见 O-84）就得回来手改一堆字面量，
  而**漏改的那条会变成"因为格式不对而通过的假测试"**（本文件 2026-09-26 就这么差点踩中）。
"""
import hashlib
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402

NS, IDENT, VER = "rpc", "inventory/edges.yaml", "0.0.0"


# ── ① 已知向量：钉住**字节级**行为（不是"算出来两个一样就过"）────────────────
def test_canonical_bytes_is_exactly_the_array():
    """规范说哈希输入 = `["<ns>","<id>","<ver>"]` 的规范化 JSON 字节序列 ⇒ 逐字节钉住它。"""
    assert R.u1_canonical_bytes(NS, IDENT, VER) == b'["rpc","inventory/edges.yaml","0.0.0"]'
    # 无空白：一旦有人改成 json.dumps 默认（带空格），这条立刻红
    assert b", " not in R.u1_canonical_bytes(NS, IDENT, VER)


def test_identity_equals_sha256_first_trunc_of_that_vector():
    want = f"{R.U1_PREFIX}:" + hashlib.sha256(
        b'["rpc","inventory/edges.yaml","0.0.0"]').hexdigest()[:R.U1_TRUNC]
    assert R.u1_identity(NS, IDENT, VER) == want


def test_default_version_is_000():
    """无版本者写 `0.0.0`（spec §1.3）—— 省略与显式写必须**同值**（否则"无版本"会造出两个身份）。"""
    assert R.u1_identity("rpc", "x") == R.u1_identity("rpc", "x", "0.0.0")


def test_prefix_is_self_describing_and_matches_implementation():
    """★ D-25 的"前缀必须自描述"若无人对照就只是装饰 ⇒ 这里把前缀与实现**对上账**。"""
    ident = R.u1_identity(NS, IDENT, VER)
    got = R.u1_parse(ident)
    assert got == (R.U1_ALGO, R.U1_TRUNC)
    assert ident.startswith(R.U1_PREFIX + ":")


# ── ② ★ 这条是"为什么选 JSON 数组"的**唯一可观测优势** ────────────────────────
def test_separator_injection_is_resolved_by_json_array():
    """用自定义分隔符拼接时 `("a|b","c")` 与 `("a","b|c")` 会撞同一串；JSON 数组不会。

    ★ 有这条，"选 JSON 数组"才是在解决一个**真问题**；没有它，那只是一个口味偏好。
    """
    assert R.u1_identity("a|b", "c") != R.u1_identity("a", "b|c")
    assert R.u1_identity("a__b", "c") != R.u1_identity("a", "b__c")
    # 反向自证：拼接法**确实**会撞（否则本用例什么都没证）
    assert "|".join(["a|b", "c"]) == "|".join(["a", "b|c"]) == "a|b|c"


def test_field_boundaries_do_not_blur():
    """字段边界必须由 JSON 语法给出：`("ab","c")` 与 `("a","bc")` 不得同值。"""
    assert R.u1_identity("ab", "c") != R.u1_identity("a", "bc")


# ── ③ `u1_parse` 的**反例族**（判据必须会咬）────────────────────────────────
def test_parse_accepts_only_the_declared_shape():
    good = R.u1_identity(NS, IDENT, VER)
    assert R.u1_parse(good) is not None
    T = R.U1_TRUNC
    bad = [
        ("大写 hex（规范要求小写）", good.upper()),
        ("长度不足", f"{R.U1_PREFIX}:" + "0" * (T - 1)),
        ("长度超出", f"{R.U1_PREFIX}:" + "0" * (T + 1)),
        ("前缀写的长度与实际位数不符", "u1:sha256:16:" + "0" * 16),
        ("算法不是我们用的那个", f"u1:md5:{T}:" + "0" * T),
        ("截断长度不是我们定的那个", "u1:sha256:12:" + "0" * 12),
        ("缺段", "u1:sha256:" + "0" * T),
        ("不是字符串", 12345),
        ("空串", ""),
        ("路径混进来（不是身份）", "inventory/edges.yaml"),
        ("全 64 位未截断", "u1:sha256:64:" + "0" * 64),
    ]
    for why, s in bad:
        assert R.u1_parse(s) is None, f"`u1_parse` 放过了不合规输入（{why}）: {s!r}"


# ── ④ `u1_verify_declaration`：把"可复算"变成判据 ───────────────────────────
def _decl(**over):
    d = {"namespace": NS, "identifier": IDENT, "version": VER,
         "identity": R.u1_identity(NS, IDENT, VER)}
    d.update(over)
    return d


def test_declaration_roundtrips():
    assert R.u1_verify_declaration(_decl()) is None


def test_declaration_rejects_missing_fields():
    """只写 identity 就**无法复算** —— 那正是本条要防的（身份不能是一句自述）。"""
    for miss in ("namespace", "identifier", "version", "identity"):
        err = R.u1_verify_declaration(_decl(**{miss: ""}))
        assert err and miss in err, f"缺 `{miss}` 未被判出"


def test_declaration_rejects_recompute_mismatch():
    """★ 核心反例：编一个**格式完全合规**的 hex ⇒ 必须被复算判红。

    这条就是"格式判 != 身份判"的分界；没有它，`u1-identity` 门禁等于什么都没判。
    ⚠⚠ 假身份**必须按当前 `U1_TRUNC` 造**：若写成别的长度，它会被 `u1_parse` 以**格式**为由拦下，
      于是本用例**因为错的原因通过** —— 报的还是"复算不符"就会被读成"复算在起作用"（假绿）。
    """
    fake = f"{R.U1_PREFIX}:" + "deadbeef" * (R.U1_TRUNC // 8)
    assert R.u1_parse(fake) is not None, "假身份必须先过**格式**判（否则本用例证不到复算）"
    err = R.u1_verify_declaration(_decl(identity=fake))
    assert err and "复算不符" in err


def test_declaration_rejects_swapped_fields():
    """取值自相矛盾也要抓：把 identifier 换成另一个路径 ⇒ 复算必然不符。"""
    assert R.u1_verify_declaration(_decl(identifier="inventory/dialect.yaml")) is not None


def test_declaration_rejects_non_mapping():
    assert R.u1_verify_declaration(f"{R.U1_PREFIX}:" + "0" * R.U1_TRUNC) is not None
    assert R.u1_verify_declaration(None) is not None


# ── ⑤ ★ **先验红自证**：上面那条判据不是恒真 ─────────────────────────────────
def _naive_verify(decl):
    """一个**只判格式**的桩：任何合规长度的 hex 都放过（= 假绿版判据）。"""
    return None if R.u1_parse((decl or {}).get("identity")) else "格式不合规"


def test_the_recompute_check_is_not_vacuous():
    """★ 先验红：同一份**编造的**声明 —— 假绿桩放过它，真判据必须判红。

    没这条，"复算"可能只是写了个 `return None`（本仓头号形态：判据什么都没判）。
    """
    fake = _decl(identity=f"{R.U1_PREFIX}:" + "deadbeef" * (R.U1_TRUNC // 8))
    assert _naive_verify(fake) is None, "桩应当放过（证明假绿确实存在）"
    assert R.u1_verify_declaration(fake) is not None, "真判据必须判红"


# ── ⑥ 端到端真读：本仓真的写了这两个声明（消掉 U1 spec 未实测 #2）──────────
def test_repo_inventory_declarations_exist_and_recompute():
    import yaml

    seen = []
    for p in sorted((ROOT / "inventory").glob("*.yaml")):
        doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if not (isinstance(doc, dict) and doc.get("u1")):
            continue
        seen.append(p.name)
        assert R.u1_verify_declaration(doc["u1"]) is None, f"{p.name} 的身份复算不符"
        head = p.read_text(encoding="utf-8").splitlines()[:5]
        assert any(R.U1_HEADER_RE.match(l) for l in head), \
            f"{p.name} 缺 `# {R.U1_PREFIX}` 头部注释行（D-25：前缀进头部注释）"
    # ★ 一个都没有 ⇒ 本条判据失去对象（会在门禁里静默退化成空判）
    assert seen, "inventory/*.yaml 里没有任何 U-1 身份声明 ⇒ 未实测 #2 并未被消掉"
