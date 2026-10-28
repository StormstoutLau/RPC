"""ds4 PP 监听默认与编排传参（P1 #7）。

覆盖 IMPLEMENTATION §9.1 #7 行：
  · `_pp_listen_ip` 从真实 inventory/net.yaml 取 coord 在直连段的 IP；
    找不到段 / 同站 / 未知站 ⇒ ""；
  · `_build_infer_load_cmd` 含/不含 `--pp-listen`；非法 IP ⇒ ValueError；
  · `_load_ds4_pp`：取不到 IP ⇒ 在起 worker **之前**中止；取到 ⇒ worker 先起、
    coordinator 命令带 `--pp-listen '<ip>'`；
  · infer-load 源码不再有 `PP_LISTEN:-0.0.0.0`，coordinator 无显式值即 exit 1。

用法: py tests\\test_cluster_pp_listen.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))
sys.path.insert(0, str(ROOT / "tests"))
from _cluster_proxy import cluster_proxy  # noqa: E402  ★ 拆分后打桩须落到定义模块
C = cluster_proxy()

fails = []


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


# ── 1. _pp_listen_ip ────────────────────────────────────────────
fn = getattr(C, "_pp_listen_ip", None)
chk("_pp_listen_ip 存在", callable(fn))
if callable(fn):
    chk("B-C ⇒ B 的直连段 IP", fn("B", "C") == "10.10.11.1", fn("B", "C"))
    chk("C-B ⇒ C 的直连段 IP", fn("C", "B") == "10.10.11.3", fn("C", "B"))
    chk("A-C ⇒ A 的直连段 IP", fn("A", "C") == "10.10.12.1", fn("A", "C"))
    chk("A-B ⇒ A 的直连段 IP", fn("A", "B") == "10.10.10.1", fn("A", "B"))
    chk("同站 ⇒ 空", fn("A", "A") == "")
    chk("未知站 ⇒ 空", fn("A", "Z") == "")

# ── 2. _build_infer_load_cmd ─────────────────────────────────────
build = getattr(C, "_build_infer_load_cmd", None)
chk("_build_infer_load_cmd 存在", callable(build))
if callable(build):
    chk("不含 pp_listen 时不追加",
        build("ds4", "ds4") == "infer-load 'ds4' --backend ds4", build("ds4", "ds4"))
    cmd = build("ds4", "ds4", pp_listen="10.10.11.1")
    chk("含 pp_listen 时追加", "--pp-listen '10.10.11.1'" in cmd, cmd)
    try:
        build("ds4", "ds4", pp_listen="1.2.3.999")
        chk("非法 pp_listen ⇒ ValueError", False, "未抛")
    except ValueError:
        chk("非法 pp_listen ⇒ ValueError", True)

# ── 3. _load_ds4_pp 编排 ────────────────────────────────────────
load_pp = getattr(C, "_load_ds4_pp", None)
chk("_load_ds4_pp 存在", callable(load_pp))
if callable(load_pp):
    calls = []
    orig_stream = C.ssh_stream
    orig_run = C.ssh_run
    orig_ip = getattr(C, "_pp_listen_ip", None)
    try:
        C.ssh_stream = lambda st, cmd: (calls.append((st, cmd)) or 0)
        C.ssh_run = lambda st, cmd, timeout=None: (True, '{"data":[]}')
        C._pp_listen_ip = lambda coord, worker: "10.10.11.1"
        rc = C._load_ds4_pp("ds4", "B", "C")
        chk("PP 成功 rc=0", rc == 0, rc)
        chk("先起 worker 后起 coordinator",
            len(calls) == 2 and calls[0][0] == "C" and calls[1][0] == "B", calls)
        chk("worker 不带 --pp-listen", "--pp-listen" not in calls[0][1], calls[0][1])
        chk("coordinator 带 --pp-listen",
            "--pp-listen '10.10.11.1'" in calls[1][1], calls[1][1])

        calls.clear()
        C._pp_listen_ip = lambda coord, worker: ""
        rc = C._load_ds4_pp("ds4", "B", "C")
        chk("无直连段 IP ⇒ rc=1", rc == 1, rc)
        chk("无 IP 时不启动任何进程", calls == [], calls)
    finally:
        C.ssh_stream = orig_stream
        C.ssh_run = orig_run
        if orig_ip is not None:
            C._pp_listen_ip = orig_ip

# ── 4. infer-load 源码口径 ──────────────────────────────────────
src = (ROOT / "ops" / "station-bin" / "infer-load").read_text(encoding="utf-8")
chk("infer-load 不再默认 0.0.0.0", "PP_LISTEN:-0.0.0.0" not in src)
chk("infer-load 含 --pp-listen", "--pp-listen" in src)
chk("coordinator 无显式值即退出", "不能默认 0.0.0.0" in src)

print("\nRESULT: " + ("PASS" if not fails else f"FAIL ({len(fails)} 项)") +
      " · 失败: " + (", ".join(fails) if fails else "无"))
sys.exit(0 if not fails else 1)
