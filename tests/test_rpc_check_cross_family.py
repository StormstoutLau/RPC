"""`D7-P3-1`：J-1（跨族）/ J-2（输入独立）判定本体的正反用例（2026-09-26）。

为什么要有：这两条判据**天然会往"默认放行"漂**（族表缺项时若不 fail-closed，
就会把「没判」读成「跨族成立」）。⇒ 必须**证明 `unknown` 分支真的会走**，
而且用的是**实测取到的真实模型串**（不是构造出来的漂亮输入）。

用法（退出码 0 = 全过）：
    py tests\\test_rpc_check_cross_family.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))
import rpc_check as R                                    # noqa: E402

fails = []
total = 0


def chk(name, cond, extra=""):
    global total
    total += 1
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + extra if extra else ""))
    if not cond:
        fails.append(name)


IDX = R.load_family_index()

# ── A. 归一化：四种**实测形态**（2026-09-26 取样真实 runDir）──
chk("A1 `local/gpt-oss-20b` ⇒ gpt-oss-20b", R.normalize_model_id("local/gpt-oss-20b") == "gpt-oss-20b")
chk("A2 `cluster-litellm/gpt-oss-20b` ⇒ gpt-oss-20b",
    R.normalize_model_id("cluster-litellm/gpt-oss-20b") == "gpt-oss-20b")
chk("A3 `station:A/thinkingmachines/inkling:free` ⇒ inkling（剥站点与尾参）",
    R.normalize_model_id("station:A/thinkingmachines/inkling:free") == "inkling")
chk("A4 `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` ⇒ nemotron-3-ultra-550b-a55b",
    R.normalize_model_id("openrouter/nvidia/nemotron-3-ultra-550b-a55b:free") == "nemotron-3-ultra-550b-a55b")
chk("A5 裸别名不变", R.normalize_model_id("m27-q4ks") == "m27-q4ks")
chk("A6 空/None ⇒ 空串", R.normalize_model_id(None) == "" and R.normalize_model_id("  ") == "")

# ── B. J-1 三态 ──
v = R.cross_family_verdict("local/gpt-oss-20b", "local/m27-q4ks", IDX)
chk("B1 跨族（gpt-oss vs minimax）⇒ cross", v["verdict"] == "cross", v["reason"])
v = R.cross_family_verdict("local/gpt-oss-20b", "cluster-litellm/gpt-oss-120b", IDX)
chk("B2 **同族**（20b vs 120b）⇒ same（判据红）", v["verdict"] == "same", v["reason"])
v = R.cross_family_verdict("local/qwen3.8-flash-next", "local/davidau-q38-27b-q4k", IDX)
chk("B3 微调模型**归基座族** ⇒ same（血统口径生效）", v["verdict"] == "same", v["reason"])
v = R.cross_family_verdict(None, "local/m27-q4ks", IDX)
chk("B4 缺 producer ⇒ unknown（不可判）", v["verdict"] == "unknown")

# ── C. ★ 真实数据回归：**出网模型不在族表** ⇒ 必须 unknown 且点名（fail-closed）──
v = R.cross_family_verdict("local/gpt-oss-20b",
                           "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free", IDX)
chk("C1 出网判官（真值串）⇒ **unknown**，绝不默认算跨族", v["verdict"] == "unknown", v["reason"])
chk("C2 且**点名**未入表的那个模型", v.get("unknown") == ["nemotron-3-ultra-550b-a55b"], str(v.get("unknown")))
v = R.cross_family_verdict("local/gpt-oss-20b", "station:A/thinkingmachines/inkling:free", IDX)
chk("C3 站上出网档同样 ⇒ unknown", v["verdict"] == "unknown")
chk("C4 族表当前覆盖 **12** 个 alias（本地库全集）", len(IDX) == 12, f"len={len(IDX)}")

# ── D. J-2 三态（原料：run.json.prompt_sha256 vs review.json.metadata.prompt_hash）──
v = R.cross_input_verdict("sha256:aaa", "sha256:bbb")
chk("D1 摘要不同 ⇒ cross（**下界证据**）", v["verdict"] == "cross")
v = R.cross_input_verdict("sha256:same", "sha256:same")
chk("D2 摘要**相同** ⇒ same（判官看到的就是产出者看到的 ⇒ 判据红）", v["verdict"] == "same", v["reason"])
v = R.cross_input_verdict("sha256:aaa", None)
chk("D3 缺一侧 ⇒ unknown", v["verdict"] == "unknown")

# ── E. 接线的**如实边界**（这两条判据**当前无本仓消费者**：对象在站上 runDir）──
src = (ROOT / "ops" / "rpc_check.py").read_text(encoding="utf-8")
chk("E1 两个判定本体在 rpc_check（纯函数，可离线测）",
    "def cross_family_verdict(" in src and "def cross_input_verdict(" in src)
chk("E2 ⚠ 且**未**登记进 CHECKS（无本仓对象 ⇒ 空判会让它假绿）",
    "cross_family" not in [c["id"] for c in R.CHECKS])

print("--------------------------------")
print(f"CROSS_FAMILY_TEST pass={total - len(fails)}/{total} fail={len(fails)}")
if fails:
    print("FAILED: " + ", ".join(fails))
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED -> {fails}")
sys.exit(1 if fails else 0)
