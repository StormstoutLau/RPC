"""`D7-P3-1` 前置：`model-families` 判据的正反用例 + **先验红**（2026-09-26）。

为什么要有：该判据管的是"**有没有 alias 没被归类**"—— 它**天然容易腐化**（新模型加进
`models.yaml` 后没人管族表）⇒ 必须证明它**真的会红**（否则就是"通过是因为什么都没判"）。
★ **先验红**是本仓通用纪律（§3.0 四条之一）：把真文件改成"坏"的形态，断言判据**红且点名**，
再**字节级恢复**并在末尾**自证恢复**（本仓踩过"只读探针用 write 回写同一文件 ⇒ 改了 CRLF"的坑）。

用法（退出码 0 = 全过）：
    py tests\\test_rpc_check_model_families.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))
import rpc_check as R                                    # noqa: E402

FAM = ROOT / "inventory" / "model-families.yaml"
ORIG = FAM.read_bytes()                                  # ★ 字节级原件（含 CRLF）

fails = []
total = 0


def chk(name, cond, extra=""):
    global total
    total += 1
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + extra if extra else ""))
    if not cond:
        fails.append(name)


def judge_on(text: str):
    """把**坏**内容写进真文件、跑判据、恢复 ⇒ 返回 `(status, note, detail)`。"""
    try:
        FAM.write_bytes(text.encode("utf-8"))
        return R.check_model_families({})
    finally:
        FAM.write_bytes(ORIG)                            # ★ 立刻恢复（finally 保证）


GOOD = ORIG.decode("utf-8")

# ── A. 真文件 ⇒ PASS + 报数（并防"空判"：必须真的数出 12 个 alias）──
st, note, det = R.check_model_families({})
chk("A1 真文件 ⇒ PASS", st == "PASS", f"{st} · {note}")
chk("A2 报数含「成员覆盖 12/12」（防 0/0 被读成没问题）", "覆盖 12/12" in note, note)
chk("A3 判据列出族名（可读）", any("gpt-oss" in d for d in det))

# ── B. **先验红**（每条都要求"红 + 点名"）──
st, note, det = judge_on(GOOD.replace("gpt-oss-20b, ", ""))
chk("B1 从族里删掉一个 alias ⇒ FAIL 且点名「未归类」",
    st == "FAIL" and any("未归类" in d for d in det), f"{st} · {[d[:40] for d in det]}")

st, note, det = judge_on(GOOD.replace("members: [gpt-oss-120b,", "members: [no-such-model,"))
chk("B2 族里塞一个不存在的 alias ⇒ FAIL 且点名「孤儿引用」",
    st == "FAIL" and any("孤儿引用" in d for d in det), f"{st} · {[d[:40] for d in det]}")

st, note, det = judge_on(GOOD.replace("basis: OpenAI 开源权重（gpt-oss 系列）", "basis: x"))
chk("B3 一族 basis 过短 ⇒ FAIL 且点名 basis", st == "FAIL" and any("basis" in d for d in det))

st, note, det = judge_on(GOOD.replace("members: [m27-q4ks]", "members: [m27-q4ks, gpt-oss-120b]"))
chk("B4 同一 alias 归两族 ⇒ FAIL 且点名「重复归类」",
    st == "FAIL" and any("重复归类" in d for d in det))

st, note, det = judge_on("version: 1\nfamilies: []\n")
# ⚠ 这里**不能**写 `any("空判" in d for d in note + " ".join(det))` —— 那是**逐字符**迭代，
#   恒假（本批实测踩到：先用它把一条正确的判据判成 FAIL）。⇒ 先拼成整串再判。
_msg = note + " ".join(det)
chk("B5 `families` 为空 ⇒ FAIL（防『什么都没判』）", st == "FAIL" and "空判" in _msg, f"{st} · {note}")

st, note, det = judge_on(GOOD.replace(
    "{keys: [poolside/laguna-s-2.1], family: poolside, basis_from: vendor-prefix,",
    "{keys: [poolside/laguna-s-2.1], family: poolside, basis_from: ,"))
chk("B6 出网条目缺 `basis_from` ⇒ FAIL（口径来源必须写）",
    st == "FAIL" and any("basis_from" in d for d in det), f"{st} · {[d[:46] for d in det]}")

# ── C. 接线与语义边界（防"写了但没接" / 防后人读过头）──
ids = [c["id"] for c in R.CHECKS]
chk("C1 判据已登记进 CHECKS", "model-families" in ids)
chk("C2 且 **quick = True**（真在门禁里跑）",
    next(c.get("quick", False) for c in R.CHECKS if c["id"] == "model-families") is True)
_ls = GOOD[GOOD.index("linked_state:"):] if "linked_state:" in GOOD else ""
_st = ""
for _ln in _ls.splitlines()[1:6]:
    if _ln.strip().startswith("status:"):
        _st = _ln.split(":", 1)[1].split("#")[0].strip()   # ★ 去掉行尾注释（否则 `in` 判定会因注释而假红）
        break
# ★ 2026-09-26 实测后 `status` 由 `unverified` 改为更精确的 `runtime-not-truth-table`
#   ⇒ **改断言（不是回退代码）**：本条的**意图**是"**不许假装拿到了『已加载』**" ⇒
#   断言写成"**必须在允许集内** + **不得是任何『已定案/已验证』语义**"，比钉死一个字更耐用。
chk("C3 `linked_state.status` 明示【未当作已加载真值】",
    _st in ("unverified", "runtime-not-truth-table") and "verif" not in _st.replace("unverified", ""),
    f"status={_st}")
chk("C4 且说清「≠ stations / conf」（防把两件事说成一件）",
    "stations" in GOOD and "conf" in GOOD and "linked_state" in GOOD)

# ── D. 恢复自证（先验红写回同一文件 ⇒ 必须字节级回到原状）──
chk("D1 **字节级恢复自证**（先验红没污染真文件）", FAM.read_bytes() == ORIG)
st2, note2, _ = R.check_model_families({})
chk("D2 恢复后判据仍 PASS（与 A1 一致）", st2 == "PASS", note2)

print("--------------------------------")
print(f"MODEL_FAMILIES_TEST pass={total - len(fails)}/{total} fail={len(fails)}")
if fails:
    print("FAILED: " + ", ".join(fails))
# ★ O-89 纪律：门禁只认退出码 ⇒ 必须有 `RESULT:` 汇总行
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED -> {fails}")
sys.exit(1 if fails else 0)
