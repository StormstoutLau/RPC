#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cluster.py — 双机推理集群聚合操作 CLI (主控站)

用法:
    python ops/cluster.py status [--html]
    python ops/cluster.py load <alias前缀>
    python ops/cluster.py unload
    python ops/cluster.py e2e

子命令:
    status   两站 llama /health + 当前加载实例 + LiteLLM 状态一屏聚合
             --html 生成静态快照页 ops/cluster_status.html
    load     自动路由到正确站并执行 infer-load (gpt-oss-120b->A, 其余->B;
             llama-rpc 类打印手动步骤, exit 2)
    unload   两站并行幂等卸载
    e2e      经 LiteLLM 双路由 (nemotron + gpt-oss) 冒烟, max_tokens=64

退出码:
    0 成功 / 1 失败 / 2 RPC 类需手动 / 3 e2e 前置未加载

设计: spec/d2-cluster-cli/ (RESEARCH/IMPLEMENTATION/CHECKLIST)
依赖: paramiko (主控站 hermes venv Python 3.11 已装)
      C:\\Users\\Peng\\.hermes\\hermes-agent\\venv\\Scripts\\python.exe
"""
import sys
import time
import json
import threading
import urllib.request
import urllib.error
from pathlib import Path

import paramiko

# ── 常量层 ──────────────────────────────────────────────
STATIONS = {
    "A": {"host": "scott-lau-NEX.local", "user": "scott-lau"},
    "B": {"host": "scott-lau-GTR-Pro.local", "user": "scott-lau"},
}
ROUTE = {"gpt-oss-120b": "A"}          # 其余一律 B (DEFAULT_STATION)
DEFAULT_STATION = "B"
RPC_MODELS = {"deepseek-v4-flash-0731", "gpt-oss-120b-fable-5-distilled", "qwen3.8-flash-next"}
LITELLM_BASE = "http://scott-lau-GTR-Pro.local:4000"
KEY_FILE = Path(r"d:\RPC\secrets\litellm_master.key")
HTML_OUT = Path(__file__).parent / "cluster_status.html"
SSH_TIMEOUT = 8
HTTP_TIMEOUT = 8

PANELS = [
    ("LiteLLM 网关", "http://scott-lau-GTR-Pro.local:4000"),
    ("Beszel 监控", "http://scott-lau-GTR-Pro.local:8090"),
    ("Cockpit B", "https://scott-lau-GTR-Pro.local:9095"),
    ("Cockpit A", "https://scott-lau-NEX.local:9095"),
]


# ── SSH 层 ─────────────────────────────────────────────
def ssh_run(st: str, cmd: str, timeout: int = SSH_TIMEOUT) -> tuple:
    """返回 (ok, output)。ok=False 时 output 为错误信息。"""
    try:
        cli = paramiko.SSHClient()
        cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        cli.connect(STATIONS[st]["host"], username=STATIONS[st]["user"],
                    timeout=timeout, banner_timeout=timeout)
        _, out, err = cli.exec_command(cmd, timeout=timeout + 30)
        text = out.read().decode("utf-8", "replace")
        etext = err.read().decode("utf-8", "replace")
        rc = out.channel.recv_exit_status()
        cli.close()
        return True, (text if text.strip() else etext)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def ssh_stream(st: str, cmd: str) -> int:
    """实时流式回传长命令 (infer-load 需 40s~3min)。返回远端 exit code。"""
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(STATIONS[st]["host"], username=STATIONS[st]["user"],
                timeout=SSH_TIMEOUT, banner_timeout=SSH_TIMEOUT)
    _, out, err = cli.exec_command(cmd, timeout=600)
    chan = out.channel
    while True:
        while chan.recv_ready():
            sys.stdout.write(chan.recv(4096).decode("utf-8", "replace"))
            sys.stdout.flush()
        if chan.exit_status_ready() and not chan.recv_ready():
            break
        time.sleep(0.2)
    rc = chan.recv_exit_status()
    cli.close()
    return rc


# ── 探测层 ─────────────────────────────────────────────
def http_get(url: str, key: str = "", timeout: int = HTTP_TIMEOUT) -> tuple:
    """返回 (ok, body 前 200 字符或错误)。"""
    req = urllib.request.Request(url)
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, r.read().decode("utf-8", "replace")[:200]
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def probe_station(st: str) -> dict:
    """单站探测: llama health + 当前加载实例 + infer-list。"""
    result = {"station": st, "reachable": False, "llama": "?", "loaded": "?", "list": ""}
    ok, out = ssh_run(st, "curl -s --max-time 5 http://127.0.0.1:8080/health; echo; "
                          "systemctl is-active llama-server@* 2>/dev/null | head -1; "
                          "systemctl list-units 'llama-server@*' --no-legend 2>/dev/null | awk '{print $1}'")
    if not ok:
        result["llama"] = "UNREACHABLE"
        return result
    result["reachable"] = True
    lines = [l for l in out.splitlines() if l.strip()]
    result["llama"] = "READY" if (lines and lines[0].strip().startswith('{"status"')) else (lines[0] if lines else "?")
    loaded = [l for l in lines[1:] if l.startswith("llama-server@")]
    result["loaded"] = loaded[0].replace("llama-server@", "").replace(".service", "") if loaded else "(未加载)"
    ok2, out2 = ssh_run(st, "infer-list 2>/dev/null | head -30")
    result["list"] = out2 if ok2 else "(infer-list 不可用)"
    return result


def read_key() -> str:
    try:
        return KEY_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


# ── status ─────────────────────────────────────────────
def collect_status() -> dict:
    data = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "stations": {}, "litellm": ("?", "")}
    threads = []

    def run_a():
        data["stations"]["A"] = probe_station("A")

    def run_b():
        data["stations"]["B"] = probe_station("B")

    for t in (threading.Thread(target=run_a), threading.Thread(target=run_b)):
        t.start(); threads.append(t)
    key = read_key()
    ok, body = http_get(f"{LITELLM_BASE}/health/liveliness", key)
    data["litellm"] = ("UP" if ok else "DOWN", body if not ok else "")
    for t in threads:
        t.join()
    return data


def cmd_status(html: bool) -> int:
    d = collect_status()
    for st in ("A", "B"):
        s = d["stations"].get(st, {})
        print(f"── {st} 站 ({STATIONS[st]['host']}) ──")
        print(f"  llama :8080 : {s.get('llama', '?')}")
        print(f"  加载实例      : {s.get('loaded', '?')}")
        print()
    print(f"── LiteLLM :4000 : {d['litellm'][0]}")
    print()
    for st in ("A", "B"):
        print(f"── infer-list @ {st} 站 (原样透传) ──")
        print(d["stations"].get(st, {}).get("list", "(无)"))
        print()
    if html:
        render_html(d)
    return 0


def render_html(d: dict) -> None:
    rows = ""
    for st in ("A", "B"):
        s = d["stations"].get(st, {})
        color = "#2e7d32" if s.get("llama") == "READY" else "#c62828"
        rows += (f"<tr><td>{st} 站</td><td>{STATIONS[st]['host']}</td>"
                f"<td style='color:{color};font-weight:600'>{s.get('llama', '?')}</td>"
                f"<td>{s.get('loaded', '?')}</td></tr>")
    lit_color = "#2e7d32" if d["litellm"][0] == "UP" else "#c62828"
    panels = "".join(f'<li><a href="{u}">{n}</a></li>' for n, u in PANELS)
    lists = ""
    for st in ("A", "B"):
        txt = d["stations"].get(st, {}).get("list", "(无)")
        lists += f"<h3>{st} 站 infer-list</h3><pre>{txt}</pre>"
    html_doc = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>双机推理集群状态快照</title>
<style>
body{{font-family:Consolas,'Microsoft YaHei',monospace;margin:2em;background:#fafafa}}
h1{{font-size:1.3em}} table{{border-collapse:collapse;margin:1em 0}}
td,th{{border:1px solid #bbb;padding:6px 14px;font-size:0.95em}}
pre{{background:#fff;border:1px solid #ddd;padding:8px;overflow-x:auto;font-size:0.85em}}
.meta{{color:#666;font-size:0.85em}} li{{margin:4px 0}}
</style></head><body>
<h1>双机推理集群状态快照</h1>
<p class="meta">生成时刻 {d['time']} — 静态快照, 重新运行 <code>cluster.py status --html</code> 刷新</p>
<table><tr><th>站点</th><th>主机</th><th>llama :8080</th><th>加载实例</th></tr>
{rows}
<tr><td>LiteLLM</td><td>:4000</td><td style="color:{lit_color};font-weight:600">{d['litellm'][0]}</td><td>统一网关</td></tr>
</table>
<h3>面板入口</h3><ul>{panels}</ul>
{lists}
</body></html>"""
    HTML_OUT.write_text(html_doc, encoding="utf-8")
    print(f"HTML 快照已生成: {HTML_OUT}")
    print(f"浏览器打开: file:///{HTML_OUT.as_posix()}")


# ── load / unload ──────────────────────────────────────
def resolve_alias(alias: str) -> tuple:
    """返回 (station, matched_alias, is_rpc)。"""
    low = alias.lower()
    for full in ROUTE:
        if full.startswith(low):
            return ROUTE[full], full, full in RPC_MODELS
    for m in RPC_MODELS:
        if m.startswith(low):
            return None, m, True
    return DEFAULT_STATION, alias, alias in RPC_MODELS


def cmd_load(alias: str) -> int:
    station, matched, is_rpc = resolve_alias(alias)
    if is_rpc or station is None:
        print(f"[cluster] '{matched}' 为 llama-rpc 双机类模型, 超出单命令边界 (exit 2)。")
        print("  手动步骤:")
        print("  1) A 站: sudo systemctl start rpc-server        # 10.10.10.1:50052")
        print("  2) B 站: ssh scott-lau@scott-lau-GTR-Pro.local 'infer-load <完整别名>'")
        print("  3) 用毕: B 站 infer-unload (会顺带停 A 站 rpc-server)")
        return 2
    st_host = STATIONS[station]["host"]
    print(f"[cluster] 路由: {matched} -> {station} 站 ({st_host})")
    # P1 换模型串行化: 先查 health, READY 则先 unload 等 GTT 释放
    ok, out = ssh_run(station, "curl -s --max-time 5 http://127.0.0.1:8080/health")
    if ok and out.strip().startswith('{"status"'):
        print(f"[cluster] {station} 站当前已加载模型, 先卸载并等待 GTT 释放 ...")
        rc = ssh_stream(station, "infer-unload")
        if rc != 0:
            print(f"[cluster] 卸载失败 (rc={rc}), 中止。")
            return 1
    print(f"[cluster] 加载中 (站内 load-mem-gate 自动护航) ...")
    rc = ssh_stream(station, f"infer-load '{matched}'")
    if rc != 0:
        print(f"[cluster] 加载失败 (rc={rc})。")
        return 1
    ok, out = ssh_run(station, "curl -s --max-time 5 http://127.0.0.1:8080/health")
    ready = ok and out.strip().startswith('{"status"')
    print(f"[cluster] {'READY ✓' if ready else 'health 探测未通过, 请查 status'}")
    return 0 if ready else 1


def cmd_unload() -> int:
    results = {}
    threads = []

    def run(st):
        results[st] = ssh_stream(st, "infer-unload")

    for st in ("A", "B"):
        t = threading.Thread(target=run, args=(st,))
        t.start(); threads.append(t)
    for t in threads:
        t.join()
    rc = 0
    for st in ("A", "B"):
        r = results[st]
        print(f"[cluster] {st} 站 infer-unload: {'OK' if r == 0 else f'rc={r}'}")
        rc |= (r if r != 0 else 0)
    return 0 if rc == 0 else 1


# ── e2e ────────────────────────────────────────────────
def cmd_e2e() -> int:
    key = read_key()
    if not key:
        print("[cluster] 读不到 LiteLLM key (secrets/litellm_master.key), exit 1")
        return 1
    # P3 前置检查: 双路由后端是否 READY
    backends = {"nemotron": ("B", "nvidia-nemotron-3-super"), "gpt-oss": ("A", "gpt-oss-120b")}
    not_ready = []
    for route, (st, m) in backends.items():
        ok, out = ssh_run(st, "curl -s --max-time 5 http://127.0.0.1:8080/health")
        if not (ok and out.strip().startswith('{"status"')):
            not_ready.append((route, st, m))
    if not_ready:
        print("[cluster] e2e 前置未就绪 (exit 3):")
        for route, st, m in not_ready:
            print(f"  路由 {route}: {st} 站 llama 未 READY — 先执行 python ops/cluster.py load {m}")
        return 3
    for route in backends:
        body = {"model": route, "messages": [{"role": "user", "content": "回复一个词: OK"}], "max_tokens": 64}
        req = urllib.request.Request(f"{LITELLM_BASE}/v1/chat/completions",
                                     data=json.dumps(body).encode(),
                                     headers={"Authorization": f"Bearer {key}",
                                              "Content-Type": "application/json"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                resp = json.loads(r.read().decode("utf-8"))
            dt = time.time() - t0
            u = resp.get("usage", {})
            ct = (u.get("completion_tokens") or 0)
            tps = ct / dt if dt > 0 and ct else 0
            content = (resp.get("choices") or [{}])[0].get("message", {}).get("content", "")[:60]
            print(f"[e2e] {route:10s} ✓ {dt:5.1f}s  {tps:5.1f} t/s  content: {content!r}")
        except Exception as e:
            print(f"[e2e] {route:10s} ✗ {type(e).__name__}: {e}")
            print(f"      排查: python ops/cluster.py status  — 看哪站没起")
            return 1
    return 0


# ── main ───────────────────────────────────────────────
def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    sub = args[0]
    if sub == "status":
        return cmd_status("--html" in args[1:])
    if sub == "load":
        if len(args) < 2:
            print("用法: cluster.py load <alias前缀>")
            return 1
        return cmd_load(" ".join(args[1:]))
    if sub == "unload":
        return cmd_unload()
    if sub == "e2e":
        return cmd_e2e()
    print(f"未知子命令: {sub}\n{__doc__}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
