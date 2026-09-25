"""O-57 配套：`accept-cmds` **归属**判据的离线护栏（2026-09-25）。

为什么要有这条测试：站上 `out/` 是**累计**的，而 collect 的固定名拉回**无 run 窗口**
⇒ 上一次 run 的残留会被当本次证据归档（实测 4 个 proj 根 83 个 run 里 **12 条**）。
该形态的症状是"**在**" ⇒ `missing-artifact` 判据**永远看不见它** ⇒ 只有本判据能判。
而本判据**自己也必须被守** —— 本仓既有教训「写了判据但没接进链路 = 假防线」。

用法（退出码 0 = 全过）：
    py tests\\test_agent_audit_accept_owner.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))
import cluster as C                                    # noqa: E402

fails = []
total = 0


def chk(name, cond, extra=""):
    global total
    total += 1
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + extra if extra else ""))
    if not cond:
        fails.append(name)


# ── A. `_card_accept_list` 口径（必须与产出侧 `$accept -join "\n"` 一致）──
CARD_STD = (
    "---\n"
    "proj: paper\n"
    "model: claude\n"
    "accept:\n"
    "  - test -f out/a.txt\n"
    "  - grep -q OK out/a.txt\n"
    "readonly: true\n"
    "---\n"
    "## 任务描述\n\n正文里的 `accept:` 字样不算\n"
)
got = C._card_accept_list(CARD_STD)
chk("A1 标准块 + 保序 + 去空白", got == ["test -f out/a.txt", "grep -q OK out/a.txt"], f"got={got}")

chk("A2 无 front-matter => []", C._card_accept_list("no front matter\n- x\n") == [])
chk("A3 无 accept 键 => []", C._card_accept_list("---\nmodel: x\n---\n") == [])

CARD_GOLD = ("---\n"
             "accept-golden:\n"
             "  source: ops/x.sh\n"
             "  cmd: bash x.sh\n"
             "---\n")
chk("A4 `accept-golden` 不得混入 accept", C._card_accept_list(CARD_GOLD) == [])

# 块结束边界: 下一个顶层键之后的 `- item` **不得**被采（否则会造出不存在的声明）
CARD_BOUND = ("---\n"
              "accept:\n"
              "  - one\n"
              "model: y\n"
              "  - NOT_AN_ACCEPT\n"
              "---\n")
chk("A5 块在下一顶层键处结束（其后的 - item 不采）",
    C._card_accept_list(CARD_BOUND) == ["one"], f"got={C._card_accept_list(CARD_BOUND)}")

chk("A6 行内写法不采（与产出侧 PS 解析器一致）",
    C._card_accept_list("---\naccept: inline_cmd\n---\n") == [])
chk("A7 CRLF 容忍", C._card_accept_list("---\r\naccept:\r\n  - a\r\n---\r\n") == ["a"])
chk("A8 块内空行不结束(继续采后续 item)",
    C._card_accept_list("---\naccept:\n\n  - a\n---\n") == ["a"])

# ── B. `compare_accept_cmds` 三态 ──
same, wn, gn = C.compare_accept_cmds(CARD_STD, "test -f out/a.txt\ngrep -q OK out/a.txt\n")
chk("B1 相符 => (True, 2, 2)", same is True and wn == 2 and gn == 2, f"{(same, wn, gn)}")

# ★ O-57 的**核心形态**: 卡没有 accept，归档却有内容（= 别人的残留）
same, wn, gn = C.compare_accept_cmds("---\nmodel: x\n---\n", "test -f out/glob-probe.txt\n")
chk("B2 卡无 accept 但归档有 => 不符（残留核心形态）", same is False and wn == 0 and gn == 1)

same, _, _ = C.compare_accept_cmds(CARD_STD, "echo PRE_FIX_SENTINEL\n")
chk("B3 归档是别的卡 => 不符", same is False)

same, _, _ = C.compare_accept_cmds(CARD_STD, "grep -q OK out/a.txt\ntest -f out/a.txt\n")
chk("B4 **顺序**不同 => 不符（产出侧保序 ⇒ 序变即非同一声明）", same is False)

same, wn, gn = C.compare_accept_cmds("---\nmodel: x\n---\n", "\n\n")
chk("B5 双方皆空 => 相符（空件不算残留）", same is True and wn == 0 and gn == 0)

# ── C. 结构护栏: 判据必须**真的接进** agent_audit（"写了但没跑" = 假防线）──
src = (ROOT / "ops" / "cluster.py").read_text(encoding="utf-8")
chk("C1 agent_audit 内**确实调用** compare_accept_cmds",
    src.count("compare_accept_cmds(") >= 2, f"count={src.count('compare_accept_cmds(')}")
chk("C2 gap kind `accept-cmds-mismatch` 存在且用 _gap_key 归一（可进水位）",
    "accept-cmds-mismatch" in src and '_gap_key("accept-cmds-mismatch"' in src)
chk("C3 三态计数进 totals（不符可被机器消费）",
    all(k in src for k in ('"accept_ok"', '"accept_bad"', '"accept_skip"')))

print("--------------------------------")
print(f"ACCEPT_OWNER_TEST pass={total - len(fails)}/{total} fail={len(fails)}")
if fails:
    print("FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)
