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


# ── ⑤b ★★ `U1#8`（2026-09-30 裁 / `O-123`）：**历史截断长度的映射路径** ─────────────
# 裁 = 「检测到历史长度时**强制要求"旧代"标注字段存在（缺失即【拒绝】，不是警告）**」+ **独立映射表**
# ⚠ 全部按 `R.U1_TRUNC` / `R.U1_TRUNC_MAP` 取，**不硬编码** `16`/`32`（否则改一次取值就得回来手改）。
def _legacy_decl(**over):
    """造一个**历史长度**（映射表里那条 `from_length`）的声明。"""
    old = R.U1_TRUNC_MAP[0]["from_length"]
    d = {"namespace": NS, "identifier": IDENT, "version": VER,
         "identity": R.u1_identity(NS, IDENT, VER, trunc=old)}
    d.update(over)
    return d


def test_legacy_length_without_mark_is_rejected():
    """★ 无"旧代"标注 ⇒ **拒绝**（不是警告）—— 旧实现只会以格式为由拦下 ⇒ 与"乱串"无从区分。"""
    err = R.u1_verify_declaration(_legacy_decl())
    assert err and R.U1_LEGACY_MARK in err, f"历史长度**未带标注**却没被拒: {err!r}"
    assert R.u1_legacy_marker(_legacy_decl()) is None


def test_legacy_length_with_mark_is_accepted_and_carries_marker():
    """★ 有标注 ⇒ 接受，**且结果携带"旧代"标记**（消费方可自行降级）—— 这是"两阶段"的第二半。"""
    decl = _legacy_decl(**{R.U1_LEGACY_MARK: True})
    assert R.u1_verify_declaration(decl) is None, "带标注的历史长度应被接受（并换把尺子复算通过）"
    mk = R.u1_legacy_marker(decl)
    assert mk and mk.get("legacy") and mk.get("from_length") == R.U1_TRUNC_MAP[0]["from_length"] \
        and mk.get("to_length") == R.U1_TRUNC, f"旧代标记不完整: {mk!r}"


def test_length_never_used_as_u1_is_still_rejected():
    """★ **从未作为 U-1 长度**的取值（如 `12`）⇒ 即便加了标注也**不在映射表里** ⇒ 拒（不许靠标注"洗白"）。"""
    d = {"namespace": NS, "identifier": IDENT, "version": VER,
         "identity": R.u1_identity(NS, IDENT, VER, trunc=12), R.U1_LEGACY_MARK: True}
    err = R.u1_verify_declaration(d)
    assert err and "从未作为 U-1 长度" in err, f"映射表外的长度被放过: {err!r}"


def test_the_legacy_mark_is_not_vacuous():
    """★ **先验红自证**：同一条历史身份 —— **无标注 ⇒ 红；有标注 ⇒ 绿** ⇒ 证明"标注"是真的载荷。"""
    assert R.u1_verify_declaration(_legacy_decl()) is not None
    assert R.u1_verify_declaration(_legacy_decl(**{R.U1_LEGACY_MARK: True})) is None


# ── ⑤c ★★ `U1#5`（2026-10-01 裁）：**命名空间注册表 + 取值域判据** ─────────────
# 缺口（本批实测）：旧判据**只复算** ⇒ `namespace: 任何字符串` 都能过（复算自洽即可）
#   ⇒ D-25 的"前缀必填 + 取值域封闭"**只有前半句落地了**。
_REG = {"namespaces": [
    {"id": "open_data", "label": "Open_Data", "status": "active", "since": "2026-09-26", "aliases": ["Open_Data"]},
    {"id": "old_proj", "label": "旧项目", "status": "retired", "since": "2026-09-26", "aliases": []},
]}


def _real_reg():
    import yaml
    return yaml.safe_load((ROOT / "inventory" / "namespaces.yaml").read_text(encoding="utf-8"))


def test_namespace_registry_is_self_consistent():
    """注册表自身的机判本体：正例无 bad；同一串属于两条 ⇒ 必红（**唯一**会判红的冲突）。"""
    assert R.validate_namespaces(_REG)[0] == []
    clash = {"namespaces": [
        {"id": "a", "status": "active", "since": "2026-09-26", "aliases": ["shared"]},
        {"id": "b", "status": "active", "since": "2026-09-26", "aliases": ["shared"]},
    ]}
    bad = R.validate_namespaces(clash)[0]
    assert any("命名空间冲突" in b for b in bad), f"alias 撞车没被判出: {bad}"
    # status / since 也要判（闭集 + 形态）
    assert any("status" in b for b in R.validate_namespaces(
        {"namespaces": [{"id": "a", "status": "??", "since": "2026-09-26"}]})[0])
    assert any("since" in b for b in R.validate_namespaces(
        {"namespaces": [{"id": "a", "status": "active", "since": "9/26"}]})[0])


def test_namespace_domain_rule_is_strict():
    """★ 取值域规则：**只认 active 的 canonical id** —— 别名 / retired / 未登记 **全拒**。"""
    D = R.namespace_domain_error
    assert D("open_data", _REG) is None, "active 的 canonical id 应放行"
    alias = D("Open_Data", _REG)
    assert alias and "canonical id" in alias, f"写别名必须拒并提示 canonical id: {alias!r}"
    retired = D("old_proj", _REG)
    assert retired and "retired" in retired
    unknown = D("nope", _REG)
    assert unknown and "未登记" in unknown


def test_domain_rule_rejects_alias_to_avoid_two_identities():
    """★ **为什么别名必须拒**（不是洁癖）：身份是 `sha256([ns,id,ver])` ⇒ 哈希吃**原字符串**
    ⇒ 若 `open_data` 与 `Open_Data` 都放行，**同一个产物会有两个身份**。"""
    a = R.u1_identity("open_data", IDENT, VER)
    b = R.u1_identity("Open_Data", IDENT, VER)
    assert a != b, "前提失效：两种写法竟然同值（那本条就没有论证对象了）"
    # 而注册表把二者**算作同一个东西**（alias 指向同一 id）⇒ 故只在**身份**这一侧收紧
    by_id, a2i = R.namespace_index(_REG)
    assert a2i["Open_Data"] == "open_data" and "Open_Data" not in by_id


def test_the_domain_rule_is_not_vacuous():
    """★ **先验红自证**：拿本仓**真实声明**的 namespace，只**改一个字符串** ⇒ 判据必须翻红。

    没有这条，"取值域判据"可能只是写了个 `return None`（本仓头号形态：判据什么都没判）。
    """
    d = _decl()                                   # 真声明的形状（namespace = "rpc"）
    bad = dict(d); bad["namespace"] = "nope"
    # ⚠ 只判**取值域**这一层：复算在改名后本来就会不符 ⇒ 故直接调值域判据，不混两层
    assert R.namespace_domain_error(d["namespace"], _real_reg()) is None
    assert R.namespace_domain_error(bad["namespace"], _real_reg()) is not None


def test_u1_decl_conflicts_duplicate_identity_and_fallback_version():
    """`U1#6`（2026-10-18）：**声明集合级**两条 —— ①**身份冲突**（两个声明共用同一 `identity`）必判红；
    ②**兜底版本可见化**：`version == U1_DEFAULT_VERSION` 的声明被**报数**（该维度**实际失效**）。
    ⚠ 刻意**不改默认值** —— 全仓两条真实身份都用 `0.0.0`，改它会破坏复算。

    ★ 先验红：本测试在 `u1_decl_conflicts` **未实现**前必然失败（属性不存在）。
    """
    f = getattr(R, "u1_decl_conflicts", None)
    assert f is not None, "`u1_decl_conflicts` 不存在 ⇒ U1#6 的集合级判据缺失"
    dup = f"{R.U1_PREFIX}:" + "a" * R.U1_TRUNC
    decls = [("b.yaml", {"namespace": "rpc", "identifier": "b", "version": "0.0.0", "identity": dup}),
             ("c.yaml", {"namespace": "rpc", "identifier": "c", "version": "0.0.0", "identity": dup})]
    bad, n_fb = f(decls)
    assert bad and any("重复" in b for b in bad), f"重复身份必须判红: {bad}"
    assert n_fb == 2, f"兜底版本应报数 2，实为 {n_fb}"
    ok = [("b.yaml", {"namespace": "rpc", "identifier": "b", "version": "1.2.3",
                      "identity": f"{R.U1_PREFIX}:" + "a" * R.U1_TRUNC}),
          ("c.yaml", {"namespace": "rpc", "identifier": "c", "version": "0.0.0",
                      "identity": f"{R.U1_PREFIX}:" + "b" * R.U1_TRUNC})]
    bad2, n_fb2 = f(ok)
    assert bad2 == [] and n_fb2 == 1, f"正例应 无冲突 + 兜底 1：bad={bad2} n_fb={n_fb2}"


def test_repo_registry_covers_real_declarations_and_the_census_gap():
    """★ 端到端：真读 `inventory/namespaces.yaml` —— ① 注册表自洽；② 两个真声明都在域内；
    ③ **`U1#5` 普查出的缺口已补**：`auto_prover` 在域里、且 `Open_Data` 是 **alias 而非 id**。"""
    reg = _real_reg()
    assert R.validate_namespaces(reg)[0] == []
    by_id, a2i = R.namespace_index(reg)
    assert "auto_prover" in by_id, "普查缺口未补：Auto_Prover 仍没有合法 namespace"
    assert "open_data" in by_id and a2i.get("Open_Data") == "open_data"
    # 两个真声明（edges.yaml / dialect.yaml）的 namespace 必须在 active 域里
    import yaml
    for name in ("edges.yaml", "dialect.yaml"):
        doc = yaml.safe_load((ROOT / "inventory" / name).read_text(encoding="utf-8"))
        ns = doc["u1"]["namespace"]
        assert R.namespace_domain_error(ns, reg) is None, f"{name} 的 namespace={ns!r} 不在取值域里"
    # 消费侧换算（`--invalidate` 的 affected 归集）：census 的驼峰写法应换算回 canonical id
    assert R.namespace_for_project("Open_Data", reg) == "open_data"
    assert R.namespace_for_project("Auto_Prover", reg) == "auto_prover"
    # ⚠ 未登记 ⇒ **原样返回**（不猜、不造白名单）—— 这是与旧行为一致的那一半
    assert R.namespace_for_project("Unknown_Proj", reg) == "Unknown_Proj"


# ── ⑤d ★★ `U3#5`（2026-10-18）：**RFC 8785 的转义 ≡ 第二个工具链的 JSON 序列化** ──────
# 未实测原话（U3 spec 末节 5 · U1 spec §1.3 同一条）："**RFC 8785 跨语言 / 跨工具链的字节级一致性未验证**"。
# 本段两半（刻意分开，因为它们的**证据强度不同**）：
#   ① **字面量**钉住 JCS 的转义形态 —— **不依赖任何外部工具** ⇒ 门禁永远跑得到，且改动会被抓住；
#   ② **若本机有 node**，拿它的 `JSON.stringify`（ECMAScript 的 JSON 序列化）与我们的字节**逐字节对**。
#      ⚠ **无 node ⇒ 打印【可见的】SKIP**（环境降级，**不是**静默消失 —— 本仓纪律：降级必须可见）。
# ⚠ 射程如实：只对 `[str, str, str]` 这一形状声称（见 `u1_canonical_bytes` 的 docstring）——
#    JCS 的数字序列化 / 键排序本实现**既不实现也不声称**，故**不在此测**（测了就是假装覆盖面更大）。
_ESCAPE_CASES = [
    ("分隔符注入面（本规范最关心的那类）", ("a|b", "c__d", "0.0.0"), b'["a|b","c__d","0.0.0"]'),
    ("引号 / 反斜杠", ('ns"q', "id" + "\\" + "back", "1.2.3"), b'["ns\\"q","id\\\\back","1.2.3"]'),
    ("控制字符（tab ⇒ `\\t` · U+0001 ⇒ `\\uXXXX` **小写** hex）",
     ("ns\tx", "id\u0001y", "0.0.0"), b'["ns\\tx","id\\u0001y","0.0.0"]'),
    ("非 ASCII（**不转义**，原样 UTF-8 字节）", ("中文空间", "标识-ñ-ü", "0.0.0"),
     '["中文空间","标识-ñ-ü","0.0.0"]'.encode("utf-8")),
]


def test_jcs_escaping_is_pinned_by_literals():
    """★ 逐字节钉住 JCS 的转义：注入面 / 引号 / 反斜杠 / 控制字符 / 非 ASCII。"""
    for why, (ns, i, v), want in _ESCAPE_CASES:
        got = R.u1_canonical_bytes(ns, i, v)
        assert got == want, f"JCS 转义不符（{why}）: got={got!r} want={want!r}"


def _node_canonical_hex(cases):
    """把 cases 交给 `node` 的 `JSON.stringify` ⇒ 每例的**字节 hex**；**无 node / 失败 ⇒ None**。"""
    import json as _json        # 仅在**喂给 node** 这一步用（是把字符串序列化成 JSON **文本**，不是我们的判据）
    import shutil
    import subprocess
    exe = shutil.which("node")
    if not exe:
        return None
    script = ("const a=JSON.parse(require('fs').readFileSync(0,'utf8'));"
              "for(const c of a) console.log(Buffer.from(JSON.stringify(c),'utf8').toString('hex'));")
    payload = _json.dumps([[ns, i, v] for _why, (ns, i, v), _w in cases]).encode("utf-8")
    try:
        p = subprocess.run([exe, "-e", script], input=payload, capture_output=True, timeout=30)
    except Exception:
        return None
    if p.returncode != 0:
        return None
    return [l.strip() for l in p.stdout.decode("utf-8", "replace").splitlines() if l.strip()]


def test_cross_toolchain_json_serialization_is_byte_identical():
    """★★ `U3#5` 的本体：本实现 vs **第二个工具链**（node / ECMAScript 的 `JSON.stringify`）**逐字节**对。"""
    py_hex = [R.u1_canonical_bytes(ns, i, v).hex() for _why, (ns, i, v), _w in _ESCAPE_CASES]
    node_hex = _node_canonical_hex(_ESCAPE_CASES)
    if node_hex is None:
        print("  SKIP 环境降级：本机无 node（或调用失败）⇒ 跨工具链这**一半没跑**"
              "（可见，非静默；字面量那一半仍在上一条里跑着）")
        return
    assert node_hex == py_hex, f"跨工具链**字节不一致**：\n  py  ={py_hex}\n  node={node_hex}"


def test_the_literal_vectors_are_not_vacuous():
    """★ **先验红自证**：`json.dumps` 的**默认**（`ensure_ascii=True` + 默认分隔符）在**每一例**上
    都必须与上面的 JCS 字面量**不同** —— 否则这些字面量没在判 JCS（本仓头号形态：判据什么都没判）。"""
    import json as _json
    same = [why for why, (ns, i, v), want in _ESCAPE_CASES
            if _json.dumps([ns, i, v]).encode("utf-8") == want]
    assert not same, f"默认 `json.dumps` 竟与 JCS 字面量同值 ⇒ 这些字面量是恒真的（假绿）: {same}"


# ── ⑤e ★★ `O-162`（2026-10-20 裁「坐标语义进注册表字段」）：`identifier` / `version` 的语义 ──
# 缺口：§1.3 的 identifier / version 语义**只有 prose 一张表**（"既有各处可无损映射"）⇒ **不是判据**
#   ⇒ 每处各自拼三元组；`U1#5` 把"**取值域**"搬进了注册表、**没搬"语义"** ⇒ 缺的正是这一格。
# 裁 = 注册表条目加 `identifier_rule` / `version_rule`（**闭集**）+ 判据「active 必须登记」
#   + 「★ **已在用**（`inventory/*.yaml` 里有它的 `u1:` 声明）却登记成 `unset`」⇒ 判红（用了却没定语义）。
# ⚠ 如实标注：本判据判的是**登记完整性**，**不是**语义正确性（后者无法机判 ⇒ 不许读成"语义已验证"）。
_COORD_OK = {"namespaces": [
    {"id": "a", "status": "active", "since": "2026-09-26", "aliases": [],
     "identifier_rule": "relpath", "version_rule": "semver-0.0.0-fallback"},
]}


def test_namespace_coords_must_be_declared_and_in_closed_set():
    """① active 缺字段 ⇒ 红；② 闭集外的取值 ⇒ 红；③ retired **不强制**（历史条目只解释历史身份）。"""
    f = getattr(R, "validate_namespace_coords", None)
    assert f is not None, "`validate_namespace_coords` 不存在 ⇒ O-162 ② 的坐标语义判据缺失"
    assert f(_COORD_OK)[0] == [], f"正例误判: {f(_COORD_OK)[0]}"
    miss = {"namespaces": [{"id": "a", "status": "active", "since": "2026-09-26", "aliases": []}]}
    bad = f(miss)[0]
    assert any("identifier_rule" in b for b in bad) and any("version_rule" in b for b in bad), bad
    out = {"namespaces": [dict(_COORD_OK["namespaces"][0], identifier_rule="whatever")]}
    assert any("identifier_rule" in b for b in f(out)[0]), f"闭集外的取值未判出: {f(out)[0]}"
    old = {"namespaces": [{"id": "o", "status": "retired", "since": "2026-09-26", "aliases": []}]}
    assert f(old)[0] == [], f"retired 不该被强制登记坐标: {f(old)[0]}"


def test_unset_coords_need_a_reason_and_are_rejected_when_used():
    """★★ 两半：`unset` **必须**带 `coord_note`（否则就是一句无声的"没定"）；而**已在用**的 ns ⇒ `unset` **一律拒**。"""
    f = R.validate_namespace_coords
    un = {"namespaces": [dict(_COORD_OK["namespaces"][0], identifier_rule="unset")]}
    assert any("coord_note" in b for b in f(un)[0]), f"`unset` 没写理由 ⇒ 必须判红: {f(un)[0]}"
    ok = {"namespaces": [dict(_COORD_OK["namespaces"][0], identifier_rule="unset", coord_note="尚无产物")]}
    assert f(ok)[0] == [], f"写了理由应放行: {f(ok)[0]}"
    bad2 = f(ok, used_ns={"a"})[0]
    assert any("已在用" in b for b in bad2), f"已用的 ns 登记成 unset 必须判红（用了却没定语义）: {bad2}"


def test_the_coord_check_is_not_vacuous():
    """★ **先验红自证**：拿**真实注册表**，只把**一条** rule 改成闭集外的串 ⇒ 判据必须翻红。"""
    reg = _real_reg()
    assert R.validate_namespace_coords(reg, used_ns={"rpc"})[0] == [], "真实注册表应先绿（基线）"
    items = [dict(n) for n in reg["namespaces"]]
    for n in items:
        if n["id"] == "rpc":
            n["identifier_rule"] = "made-up"
    assert R.validate_namespace_coords({"namespaces": items}, used_ns={"rpc"})[0], \
        "只改一条却没红 ⇒ 这条判据是恒真的（在本仓，恒真 == 什么都没判）"


def test_repo_registry_registers_coords_for_used_namespaces():
    """★ 端到端真读：① 真实声明用到的 ns 坐标全登记（含 `unset` 的那几个**未被用到**）；
    ② 本仓**两个真实生产者**（`rpc` / `rpc_inbox`）必须**不是** `unset` 且细则在 `coord_note` 里。"""
    import yaml
    reg = _real_reg()
    used = set()
    for p in sorted((ROOT / "inventory").glob("*.yaml")):
        doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        d = doc.get("u1") if isinstance(doc, dict) else None
        if isinstance(d, dict) and d.get("namespace"):
            used.add(d["namespace"])
    assert used, "`inventory/*.yaml` 里没有真实声明 ⇒ 本条没有对象（不许退化成空判）"
    bad = R.validate_namespace_coords(reg, used_ns=used)[0]
    assert bad == [], f"真实注册表未通过坐标判据: {bad}"
    by_id, _a2i = R.namespace_index(reg)
    for nid in ("rpc", "rpc_inbox"):
        assert by_id[nid]["identifier_rule"] != "unset", f"{nid} 有真实生产者 ⇒ 坐标不许登记成 unset"
        assert by_id[nid].get("coord_note"), f"{nid} 的坐标细则应写进 `coord_note`"


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


# ── ⑦ ★ **无 pytest 的自跑入口**（门禁 `py-tests` 以**脚本**方式调用本文件）────────
def _run_all() -> int:
    """★ 为什么必须有这个入口（**一手教训**）：

    门禁 `py-tests` 是 `py tests/run_py_tests.py`，它把每个 `test_*.py` 当**独立脚本**跑，
    **只认退出码**（见 `tests/run_py_tests.py` 的 `run_one`）。

    ⇒ 本文件**原先没有**这个入口：被 import、定义一堆 `test_*`、然后**正常退出 0**
    ⇒ 门禁报 `PASS  test_rpc_check_u1.py  0.1s`（`RESULT` 列是**空的**），
      而**一条断言都没跑** —— 这就是"**整批验证静默消失**"，也是假绿的第 ③ 类
      （"看起来更硬的判据其实没读到"）。

    ⚠⚠ **这不是假设**：2026-09-26 实测确认（`py tests/test_rpc_check_u1.py` ⇒ **exit 0、零输出**），
      而本文件的 14 条断言此前**只在 pytest 下**被跑过（`py -m pytest` 能看到 "14 passed"）
      ⇒ **"我跑过了"与"门禁跑过了"是两件事**，中间差的就是这个入口。
    """
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
    # ⚠ 空集也算失败：没有用例可跑时**绝不能**报 ALL PASS（否则入口坏了没人知道）
    if not tests:
        print("RESULT: FAIL 未发现任何 test_* 函数（入口本身坏了）")
        return 1
    print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED -> {fails}")
    print(f"  （{ok}/{len(tests)} 通过）")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(_run_all())
