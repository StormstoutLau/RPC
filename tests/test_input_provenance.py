"""O-66「卡面 input-provenance 义务」的注入用例 —— 永久护栏

覆盖 `ops/rpc_check.py` 的 `validate_input_provenance`（**纯函数** ⇒ 离线可正反夹测）
与 `_card_frontmatter`（**行式**提取器）。

⚠ 本文件里有**两条"假绿"护栏**，都来自本轮实测踩到的坑（不是预防性设计）：
  ① `_card_frontmatter` **必须能读出值里含 `": "` 的卡** —— 第一版用 `yaml.safe_load`，
     对 `t1-attach-shared-probe` / `cpphub-001` 抛 `ScannerError` 后**静默 return None（跳过该卡）**
     ⇒ 把本该触发的 `t1` 漏过去了 = "什么都没判所以通过"。
  ② **`none` 的可证伪判据只判"tier 严于本卡"的已登记路径** —— 判"任何已登记路径"会**假红**
     （卡天然引用自身所在目录，而它在表里登记为 `public`）。
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402


# 合成真值表（不读真表 ⇒ 本文件的判据不受真表内容漂移影响；真表由 check_sensitivity 管）
INV = {
    "default_tier": "local-only",
    "documents": [
        {"path": "docs/secret-paper.md", "tier": "local-only"},
        {"path": "docs/open-note.md", "tier": "public"},
        {"path": "docs/half-checked.md", "tier": "unverified"},
        # ⚠ 这条是给用例 ⑫ 用的：**卡会引用自身所在目录**（登记为 public）⇒ 不得触发「none 可证伪」告警
        {"path": "spec/d6-agent-standard/dogfood-cards/", "tier": "public"},
    ],
    "contracts": [],
    "code": [{"path": "ops/rpc_check.py", "tier": "public"}],
}


def card(**kw):
    """造一张合成卡：`(label, frontmatter, body)`。`_body` 走正文，不进 front-matter。"""
    body = kw.pop("_body", "")
    fm = {"proj": "x", "task": "t", "model": "m", "cli": "opencode", "readonly": "false", "timeout_s": "60"}
    fm.update(kw)
    return (f"<syn:{kw.get('sensitivity')}/{kw.get('attach-egress')}>", fm, body)


def real_inv():
    """真值表（**基线用例必须用它** —— 合成表里没有真实卡的登记项，用合成表会假红）。"""
    import yaml
    return yaml.safe_load(R.SENSITIVITY_INV.read_text(encoding="utf-8")) or {}


def run(cards):
    return R.validate_input_provenance(cards, INV)


def main() -> int:
    fails = []

    def chk(desc, cond, extra=""):
        print(("  ok   " if cond else "  FAIL ") + desc + (f"  {extra}" if extra and not cond else ""))
        if not cond:
            fails.append(desc)

    # ── 触发条件（两条都是"不触发" ⇒ 不得报）──────────────────────────────
    f, w, _ = run([card(sensitivity="public", **{})])
    chk("① 无 attach-egress ⇒ 不触发（缺 input-provenance 也不报）", f == [] and w == [])

    f, w, _ = run([card(sensitivity="local-only", **{"attach-egress": "ok"})])
    chk("② local-only ⇒ 不触发（它本就不出网）", f == [] and w == [])

    f, w, _ = run([card(sensitivity="unverified", **{"attach-egress": "ok"})])
    chk("③ unverified ⇒ 不触发（按 local-only 处置）", f == [] and w == [])

    # ── 规则 ①：缺字段（含"留空"）────────────────────────────────────────
    f, w, st = run([card(sensitivity="public", **{"attach-egress": "ok"})])
    chk("④ 规则① 触发 + 缺 input-provenance ⇒ FAIL", len(f) == 1 and st["triggered"] == 1)

    f, w, _ = run([card(sensitivity="public", **{"attach-egress": "ok", "input-provenance": ""})])
    chk("⑤ 规则① **留空不算声明** ⇒ 仍 FAIL（防「留空当通过」）", len(f) == 1)

    # ── 规则 ②：项未登记 ────────────────────────────────────────────────
    f, w, _ = run([card(sensitivity="public",
                        **{"attach-egress": "ok", "input-provenance": "docs/nowhere.md"})])
    chk("⑥ 规则② 项未登记于真值表 ⇒ FAIL（未登记 = local-only，fail-closed）",
        len(f) == 1 and "未登记" in f[0])

    # ── 规则 ③：档位不得宽于输入 ────────────────────────────────────────
    f, w, _ = run([card(sensitivity="public",
                        **{"attach-egress": "ok", "input-provenance": "docs/secret-paper.md"})])
    chk("⑦ 规则③ 卡 public 而输入 local-only ⇒ FAIL", len(f) == 1 and "宽于" in f[0])

    f, w, _ = run([card(sensitivity="public",
                        **{"attach-egress": "ok", "input-provenance": "docs/half-checked.md"})])
    chk("⑧ 规则③ `unverified` 按 local-only 排名 ⇒ 卡 public 仍 FAIL", len(f) == 1)

    f, w, _ = run([card(sensitivity="sanitized",
                        **{"attach-egress": "ok", "input-provenance": "docs/open-note.md"})])
    chk("⑨ 正例：sanitized 读 public 输入 ⇒ 通过（rank 1 ≤ 2）", f == [] and w == [])

    f, w, _ = run([card(sensitivity="public",
                        **{"attach-egress": "ok", "input-provenance": ["docs/open-note.md", "ops/rpc_check.py"]})])
    chk("⑩ 正例：**块式列表多项**全部合规 ⇒ 通过", f == [] and w == [])

    # ── 规则 ④：none 必须可证伪（WARN 级，不阻断）─────────────────────────
    f, w, _ = run([card(sensitivity="public",
                        **{"attach-egress": "ok", "input-provenance": "none",
                           "_body": "本卡会读 docs/secret-paper.md 的摘要"})])
    chk("⑪ 规则④ 声明 none 但正文提到 local-only 已登记路径 ⇒ **WARN**（且**不** FAIL）",
        f == [] and len(w) == 1)

    f, w, _ = run([card(sensitivity="public",
                        **{"attach-egress": "ok", "input-provenance": "none",
                           "_body": "参考 docs/open-note.md（public）与 spec/d6-agent-standard/dogfood-cards/"})])
    chk("⑫ ★ 规则④ 只判『严于本卡』 ⇒ 提及 public 已登记路径**不得**报警（本轮收窄的假红）",
        f == [] and w == [])

    # ── ★ 假绿护栏 ①：行式提取必须读得动"值里含 `: `"的卡 ────────────────
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "card.md"
        p.write_text('---\nproj: x\ntask: 输出一行 T1_LIST: <逗号连接>；不改文件\n'
                     'sensitivity: public\nattach-egress: ok\ntimeout_s: 60\n---\n正文\n',
                     encoding="utf-8")
        fm = R._card_frontmatter(p)
        chk("⑬ ★ 值内含 `\": \"` ⇒ 行式提取仍能读出键（YAML 会抛 ScannerError ⇒ 静默跳过 = 假绿）",
            isinstance(fm, dict) and fm.get("attach-egress") == "ok" and fm.get("sensitivity") == "public")

        p2 = Path(td) / "notacard.md"
        p2.write_text("# 标题\n没有 front-matter\n", encoding="utf-8")
        chk("⑭ 首行非 `---` ⇒ 返回 None（不是卡 ⇒ 不参与）", R._card_frontmatter(p2) is None)

        p3 = Path(td) / "blocklist.md"
        p3.write_text('---\nsensitivity: public\nattach-egress: ok\n'
                      'input-provenance:\n  - docs/open-note.md\n  - ops/rpc_check.py\n---\n',
                      encoding="utf-8")
        fm3 = R._card_frontmatter(p3)
        chk("⑮ **块式列表**被读成 list（否则会读成空串 ⇒ 假红）",
            isinstance(fm3, dict) and fm3.get("input-provenance") == ["docs/open-note.md", "ops/rpc_check.py"])

    # ── 结构护栏：判据真的接进了 CHECKS（否则又是"有判据没人在跑"）────────
    entry = next((c for c in R.CHECKS if c.get("id") == "input-provenance"), None)
    chk("⑯ CHECKS 内有 `input-provenance` 且 `quick=True`（提交即拦）",
        bool(entry) and entry.get("quick") is True and entry.get("fn") is R.check_input_provenance)

    # ── 真实基线：全仓卡跑一遍必须无 FAIL（否则本判据一上就红）────────────
    cards = []
    for p in sorted(ROOT.glob(R.CARD_GLOB)):
        if p.name.lower() == "readme.md":
            continue
        fm = R._card_frontmatter(p)
        if fm is None:
            continue
        cards.append((p.relative_to(ROOT).as_posix(), fm,
                      p.read_text(encoding="utf-8", errors="replace")))
    f, w, st = R.validate_input_provenance(cards, real_inv())
    chk(f"⑰ 真实基线：{st['cards']} 张卡 · 触发 {st['triggered']} 张 ⇒ 无 FAIL", f == [], str(f))
    chk("⑱ 覆盖：真实卡数 ≥ 35（防 glob 写坏后『什么都没扫到』却报 PASS）", st["cards"] >= 35,
        f"cards={st['cards']}")

    print(f"\nRESULT: {'ALL PASS' if not fails else str(len(fails)) + ' FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
