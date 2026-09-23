"""`cluster.py inbox seal`（交付证据束生成工具）单元测试。

为什么要这条：
    `inbox seal` 是**交付态门禁的判据来源**（`release`/`done`/`accepted-by-requester`
    必须有 `30_evidence/MANIFEST.sha256`）。它若悄悄写错内容或写错位置，
    门禁会"看着绿"而证据束其实是坏的 —— 与 ADR-0007「通过但什么都没判」同类风险。
    故这里把 入参校验 / run 选择 / 清单格式 / 落盘语义 / 往返复验 逐条钉死。

做法（不碰真实数据）：把 `cluster.INBOX_ROOT` 与 `cluster._agent_proj_roots` 换成
    临时目录里的假 inbox + 假项目根，再调**真实** `_inbox_seal`，捕获其 stdout。

用法（退出码 0 = 全过）：
    py tests\\test_inbox_seal.py
"""
import contextlib
import hashlib
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))
import cluster as C                                   # noqa: E402

fails = []
EMPTY_SHA = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"   # sha256("")

PROJ = "demo"
ENTRY = "demo-2026-01-02"
RUN_OLD = "20260101000000000000"
RUN_NEW = "20260102000000000000"


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


def build(tmp: Path):
    """造：假 inbox（一笔受理）+ 假项目根（两个 run + 一个非数字目录 _audits）。"""
    inbox = tmp / "inbox"
    (inbox / ENTRY / "40_state").mkdir(parents=True)
    (inbox / ENTRY / "40_state" / "STATE.json").write_text(
        json.dumps({"state": "waiting", "updated_at": "x", "by": "admin"}), encoding="utf-8")

    root = tmp / "projroot"
    old = root / "agent-out" / RUN_OLD
    new = root / "agent-out" / RUN_NEW
    old.mkdir(parents=True)
    new.mkdir(parents=True)
    (old / "a.txt").write_text("old", encoding="utf-8")

    (new / ".agent-run.json").write_text('{"status":"completed"}', encoding="utf-8")
    (new / "agent-output.txt").write_text("hello", encoding="utf-8")
    (new / "empty.txt").write_text("", encoding="utf-8")          # 空文件也要被钉(已知答案哈希)
    (new / "sub").mkdir()                                          # 子目录须被跳过
    (new / "sub" / "x.txt").write_text("nested", encoding="utf-8")

    audits = root / "agent-out" / "_audits"                        # 非数字目录: 不得当选
    audits.mkdir()
    (audits / "1.json").write_text("{}", encoding="utf-8")
    return inbox, root


def run_seal(args):
    """调真实 _inbox_seal, 返回 (rc, stdout)。"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = C._inbox_seal(args)
    return rc, buf.getvalue()


def manifest(entry_dir: Path) -> Path:
    return entry_dir / "30_evidence" / "MANIFEST.sha256"


def data_lines(txt: str):
    return [l for l in txt.splitlines() if l and not l.startswith("#")]


tmp = Path(tempfile.mkdtemp(prefix="seal_test_"))
real_inbox, real_roots = C.INBOX_ROOT, C._agent_proj_roots
try:
    inbox, root = build(tmp)
    entry_dir = inbox / ENTRY

    # ── 入参校验 ───────────────────────────────────────────────────────
    C.INBOX_ROOT = inbox
    C._agent_proj_roots = lambda: ({PROJ: root}, "")

    rc, out = run_seal([])
    chk("无参数 → rc=1 且打印用法", rc == 1 and "用法" in out, f"rc={rc}")

    rc, out = run_seal([ENTRY, "--bogus"])
    chk("未知参数 → rc=1 且点名该参数", rc == 1 and "--bogus" in out, f"rc={rc}")

    rc, out = run_seal([ENTRY, "--grade", "Bogus"])
    chk("非法 --grade → rc=1（只接受 Reproduced/Replicated）",
        rc == 1 and "只接受" in out, f"rc={rc}")

    rc, out = run_seal(["nosuch-2026-01-01"])
    chk("非受理目录(缺 STATE.json) → rc=1", rc == 1 and "不是受理目录" in out, f"rc={rc}")

    # 项目根未知: 目录名合法但 proj 不在 PROJECTS
    (inbox / "ghost-2026-01-02" / "40_state").mkdir(parents=True)
    (inbox / "ghost-2026-01-02" / "40_state" / "STATE.json").write_text("{}", encoding="utf-8")
    rc, out = run_seal(["ghost-2026-01-02"])
    chk("proj 不在 $PROJECTS → rc=1 并列出已知 proj",
        rc == 1 and "项目根未知" in out and PROJ in out, f"rc={rc}")

    # 有 proj 但无 agent-out
    noroot = tmp / "noroot"
    noroot.mkdir()
    C._agent_proj_roots = lambda: ({PROJ: noroot}, "")
    rc, out = run_seal([ENTRY])
    chk("项目根下无 agent-out → rc=1", rc == 1 and "无 agent-out" in out, f"rc={rc}")
    C._agent_proj_roots = lambda: ({PROJ: root}, "")

    rc, out = run_seal([ENTRY, "--run", "19990101000000000000"])
    chk("--run 指向不存在的 run → rc=1", rc == 1 and "没有可钉的 run" in out, f"rc={rc}")

    # ── run 选择 ──────────────────────────────────────────────────────
    rc, out = run_seal([ENTRY])
    chk("默认取**最新数字 run**，且忽略 `_audits` 这类非数字目录",
        rc == 0 and f"钉住 run : {RUN_NEW}" in out and "_audits" not in out, out.splitlines()[2] if len(out.splitlines()) > 2 else out)

    rc, out = run_seal([ENTRY, "--run", RUN_OLD])
    chk("--run <ts> 精确命中旧 run", rc == 0 and f"钉住 run : {RUN_OLD}" in out, f"rc={rc}")

    rc, out = run_seal([ENTRY, "--all-runs"])
    chk("--all-runs 覆盖两个 run（且不含 _audits）",
        rc == 0 and RUN_NEW in out and RUN_OLD in out and "_audits" not in out, f"rc={rc}")

    # ── dry-run 不落盘 ────────────────────────────────────────────────
    chk("dry-run 明确标注只出计划", "以上为**计划**" in out)
    chk("dry-run **不落盘**", not manifest(entry_dir).exists())

    # ── --go 落盘 + 清单格式 ─────────────────────────────────────────
    rc, out = run_seal([ENTRY, "--go"])
    mf = manifest(entry_dir)
    chk("--go 后清单存在于 30_evidence/MANIFEST.sha256",
        rc == 0 and mf.is_file(), f"rc={rc} exists={mf.is_file()}")

    txt = mf.read_text(encoding="utf-8")
    lines = data_lines(txt)
    chk("清单行数 = 新 run 的 3 个文件（.agent-run.json/agent-output.txt/empty.txt）",
        len(lines) == 3, f"n={len(lines)} -> {[l.split('  ')[-1] for l in lines]}")
    chk("子目录 sub/ 被跳过（未出现在清单）", not any("sub/" in l for l in lines))
    chk("行格式 = <64位hex><两空格><相对项目根路径>",
        all(len(l.split("  ")[0]) == 64 and l.split("  ")[1].startswith(f"agent-out/{RUN_NEW}/")
            for l in lines), lines[:1])
    chk("按文件名排序", [l.split("  ")[1] for l in lines]
        == sorted(l.split("  ")[1] for l in lines))
    chk("空文件按已知答案哈希钉住 (sha256(''))",
        any(l.startswith(EMPTY_SHA) and l.endswith("empty.txt") for l in lines))
    chk("头部含 受理目录/项目根/run/件数/分级",
        all(k in txt for k in (f"inbox/{ENTRY}", str(root), RUN_NEW, "件数: 3", "交付分级: Reproduced")),
        "")
    chk("头部声明重放语义（只支持重放验证, 不承诺重放生成）",
        "重放**验证**" in txt and "不承诺" in txt and "重放**生成**" in txt)
    chk("默认分级 Reproduced 写入头部", "交付分级: Reproduced" in txt)

    rc, out = run_seal([ENTRY, "--grade", "Replicated", "--go"])
    chk("--grade Replicated 反映到头部",
        rc == 0 and "交付分级: Replicated" in manifest(entry_dir).read_text(encoding="utf-8"))

    # ── 往返复验（等价 sha256sum -c）：真实内容 / 改坏内容 ──────────────
    def verify(ptxt):
        ok, bad = 0, []
        for l in data_lines(ptxt):
            sha, _, rel = l.partition("  ")
            p = root / rel
            if not p.is_file():
                bad.append(f"缺失:{rel}")
            elif hashlib.sha256(p.read_bytes()).hexdigest() == sha:
                ok += 1
            else:
                bad.append(f"不符:{rel}")
        return ok, bad

    ok, bad = verify(manifest(entry_dir).read_text(encoding="utf-8"))
    chk("往返复验: 真实内容 3/3 匹配", ok == 3 and not bad, f"ok={ok} bad={bad}")

    first = data_lines(manifest(entry_dir).read_text(encoding="utf-8"))[0]
    tampered = "0" * 64 + first[64:]
    ok2, bad2 = verify(tampered + "\n")
    chk("往返复验非恒真: 改坏 1 行 ⇒ 恰好 1 条不匹配", ok2 == 0 and len(bad2) == 1, f"ok={ok2} bad={bad2}")

    # ── 真实仓的 INBOX_ROOT 未被污染 ─────────────────────────────────
    C.INBOX_ROOT = real_inbox
    rc, out = run_seal([ENTRY])
    chk("恢复真实 INBOX_ROOT 后, 假目录不再可见（注入仅限测试内）",
        rc == 1 and "不是受理目录" in out, f"rc={rc}")

finally:
    C.INBOX_ROOT, C._agent_proj_roots = real_inbox, real_roots
    shutil.rmtree(tmp, ignore_errors=True)

print()
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED -> {fails}")
sys.exit(1 if fails else 0)
