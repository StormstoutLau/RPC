#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cluster_flow — `cluster.py` 的按域拆分模块（review-p2-cluster 阶段）。

为什么存在：评审 #8「核心文件过大」。本模块由 `tmp/_split_cluster.py` 按 `# ──` 段
整段搬运（行为不变），`cluster.py` 只做重导出与 CLI 分派。
⚠ 跨组调用只允许**向下**（层序见 `inventory/ops.yaml` 的 `cluster_layers`）。
"""
import os
import sys
import re
import time
import json
import base64
import socket
import hashlib
import datetime
import ipaddress
import subprocess
import threading
from pathlib import Path
from contextlib import contextmanager          # O-95/O-96（2026-09-26）：跨进程互斥用

import paramiko

# ── 常量层 (已抽至 cluster_const.py, 阶段 1a 拆分) ──────────────
# 显式重导出 ⇒ `cluster.STATIONS` / `cluster.ROUTE` 等外部调用点不变
# (cluster_web.py / rpc_check.py 依赖 cluster.* 命名空间)。
# 改常量请改 ops/cluster_const.py —— 单一真值在那里。
from cluster_const import (  # noqa: E402
    STATIONS, STATION_PORT, ROUTE, STATION_ROUTES, BACKENDS,
    DEFAULT_STATION, RPC_MODELS, RPC_WORKER_IPS, DS4_PP_MODELS, CONTAINER_MODELS,
    HTML_OUT, SSH_TIMEOUT, PANELS, SERVICE_USER, REPO_ROOT,
)


# ── SSH 层 + 探测层 (已抽至 cluster_ssh.py, 阶段 1b 拆分) ──────────────
# 显式重导出 ⇒ 站内多处调用点 (`cli = _connect(...)` / `ssh_stream(...)`) 与外部
# (cluster_web.py 的 cluster.ssh_run) 均不变。实现改 ops/cluster_ssh.py。
from cluster_ssh import (  # noqa: E402
    _connect, ssh_run, ssh_stream, probe_station, resolve_host,
)

from cluster_catalog import (  # noqa: E402
    probe_studio,
)
from cluster_console import (  # noqa: E402
    disp_width as _dw, pad as _pad,
)
from cluster_runtime import (  # noqa: E402
    AliasError, _station_model_ports, cmd_load, cmd_load_on, cmd_unload, estimate_load,
    probe_metrics, resolve_alias,
)
from cluster_secrets import (  # noqa: E402
    _secrets_verdict, cmd_secrets, probe_secrets,
)

# ── e2e ────────────────────────────────────────────────
def cmd_e2e() -> int:
    """三站引擎在线冒烟（**按站上在跑别名各自的端口**探；无别名才回退 :8080）。

    2026-10-29（O-179 P2-余）：原为写死 `127.0.0.1:8080` —— 单站多模型后，第二个模型绑
    18080，写死 8080 会问候**另一个模型**（或空端口），把「引擎在线」判成引擎离线。
    exit 0 全在线；任一离线 exit 1 并提示 load。
    """
    online, offline = [], []
    for st in ("A", "B", "C"):
        ok_m, models = _station_model_ports(st)
        targets = sorted(set(models.values())) if (ok_m and models) else [STATION_PORT.get(st, 8080)]
        for p in targets:
            ok, out = ssh_run(st, f"curl -s --max-time 5 http://127.0.0.1:{p}/health")
            alive = ok and out.strip().startswith("{")   # HTTP JSON 响应 = 引擎在线
            if alive:
                print(f"[e2e] {st} 站 :{p} ✓ 引擎在线  {out.strip()[:40]}")
                online.append((st, p))
            else:
                print(f"[e2e] {st} 站 :{p} ✗ 引擎离线 — python ops/cluster.py load <该站模型>")
                offline.append((st, p))
    return 0 if not offline else 1


# ── reqlog: 引擎请求/时延/token 统计 (2026-09-15, 方案 v2 P2-3) ────
# 形态: **采样式日志** —— 站上 `reqlog sample` 读 llama.cpp 原生 /metrics + /slots,
#   与上一条样本做差分, 追加一行 JSONL 到 `~/.local/share/rpc/reqlog.jsonl`。
#   主控侧读回原文做聚合 (聚合逻辑只有一处, 不放到站上重复一遍)。
#
# 为什么是采样而不是逐请求日志: llama.cpp 没有逐请求接口, `/metrics` 只有累计计数器;
#   逐请求时延只能解析 server 日志文本 —— 脆且依赖 unsloth 的日志格式。差分采样是
#   唯一能自证的口径。**也不伪造"请求数"**: 实测 /metrics 无 requests 计数器
#   (只有 requests_processing / requests_deferred 两个 gauge), 故汇总里显示 n/a。
#
# 口径 (手册"基准对比铁律": 三种口径互不可比):
#   引擎耗时口径 = ΣΔtoken / ΣΔ引擎耗时   ← 与 API timings 可比, **主口径**, 且必须**加权**平均
#                                            (逐条平均比值会被短样本带偏)
#   墙钟口径     = ΣΔtoken / ΣΔ采样间隔   ← 含引擎空闲, 只作辅助 (配 busy 占比解释)
#
# 采样触发: **按需** (`cluster.py reqlog sample` 或 Web 按钮)。刻意不做常驻采样服务 ——
#   沿用方案 §5.4「不新增常驻服务」的边界。要连续采样, 用主控站的计划任务周期调用它。
# 站上日志落点: `~/.local/share/rpc/reqlog.jsonl` (站上 `reqlog path` 可查)


def _reqlog_station(st: str, act: str, n: int = 200) -> dict:
    cmd = {"sample": "reqlog sample",
           "path": "reqlog path",
           "tail": f"reqlog tail -n {n}"}[act]
    ok, out = ssh_run(st, cmd, timeout=90)
    recs = []
    if act == "tail" and ok:
        for line in out.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                recs.append(json.loads(line))
            except Exception:
                continue
    return {"station": st, "ok": ok, "out": (out or "").strip(), "recs": recs}


def _reqlog_aggregate(recs: list, minutes: int = None) -> dict:
    """按站点记录聚合。吞吐一律**加权** (ΣΔtoken / ΣΔ耗时), 不逐条平均比值。"""
    if minutes:
        cut = time.time() - minutes * 60
        recs = [r for r in recs if float(r.get("t") or 0) >= cut]
    agg = {"n": len(recs), "p_tok": 0.0, "g_tok": 0.0, "p_sec": 0.0, "g_sec": 0.0,
           "wall": 0.0, "restarts": 0, "peak_proc": 0, "peak_slots": 0,
           "cached_tok": 0.0, "decode_n": 0.0,
           "first": None, "last": None, "ports": set()}
    for r in recs:
        agg["p_tok"] += float(r.get("d_prompt_tokens_total") or 0)
        agg["g_tok"] += float(r.get("d_tokens_predicted_total") or 0)
        agg["p_sec"] += float(r.get("d_prompt_seconds_total") or 0)
        agg["g_sec"] += float(r.get("d_tokens_predicted_seconds_total") or 0)
        agg["wall"] += float(r.get("dt_s") or 0)
        agg["cached_tok"] += float(r.get("d_prompt_tokens_cached_total") or 0)
        agg["decode_n"] += float(r.get("d_n_decode_total") or 0)
        agg["restarts"] += 1 if r.get("restart") else 0
        agg["peak_proc"] = max(agg["peak_proc"], float(r.get("requests_processing") or 0))
        agg["peak_slots"] = max(agg["peak_slots"], float(r.get("slots_busy") or 0))
        t = float(r.get("t") or 0)
        agg["first"] = t if agg["first"] is None else min(agg["first"], t)
        agg["last"] = t if agg["last"] is None else max(agg["last"], t)
        if r.get("port"):
            agg["ports"].add(r["port"])
    agg["p_tps"] = round(agg["p_tok"] / agg["p_sec"], 1) if agg["p_sec"] > 0 else None
    agg["g_tps"] = round(agg["g_tok"] / agg["g_sec"], 1) if agg["g_sec"] > 0 else None
    # 墙钟口径 (含引擎空闲): 与主口径并列暴露, 差异由「忙占比」解释。
    # 前端会同时渲染两列, 故这里必须产出 —— 早版漏了这两个字段, 前端只能显示 '-'
    # (2026-09-15 实测: 前后端字段不一致, 页面看不出问题但值永远是空的)。
    agg["p_tps_wall"] = round(agg["p_tok"] / agg["wall"], 1) if agg["wall"] > 0 else None
    agg["g_tps_wall"] = round(agg["g_tok"] / agg["wall"], 1) if agg["wall"] > 0 else None
    agg["g_busy_ratio"] = round(agg["g_sec"] / agg["wall"], 3) if agg["wall"] > 0 else None
    agg["span_s"] = (agg["last"] - agg["first"]) if agg["first"] and agg["last"] else None
    return agg


def cmd_reqlog(argv) -> int:
    """cluster.py reqlog {sample|summary|tail|path} [--minutes N] [--tail N] [--station X]

    采样式引擎统计 (P2-3): 站上 `/metrics`+`/slots` 差分 → JSONL → 主控聚合。
    口径: 引擎耗时口径为主 (与 API timings 可比), 墙钟口径为辅 (含空闲)。
    """
    act = (argv[0] if argv else "summary").lower()
    if act not in ("sample", "summary", "tail", "path"):
        print("用法: cluster.py reqlog {sample|summary|tail|path} "
              "[--minutes N] [--tail N] [--station A|B|C]")
        return 1
    only, minutes, n = None, None, 200
    i = 1
    while i < len(argv):
        if argv[i] == "--station" and i + 1 < len(argv):
            only = argv[i + 1].upper()
            i += 2
            continue
        if argv[i] == "--minutes" and i + 1 < len(argv):
            minutes = int(argv[i + 1])
            i += 2
            continue
        if argv[i] == "--tail" and i + 1 < len(argv):
            n = int(argv[i + 1])
            i += 2
            continue
        i += 1
    stations = [only] if only else ["A", "B", "C"]

    if act == "sample":
        res, threads = {}, []
        for st in stations:
            t = threading.Thread(target=lambda s=st: res.__setitem__(s, _reqlog_station(s, "sample")))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        rc = 0
        for st in stations:
            r = res.get(st, {})
            print(f"[reqlog] {st} 站: {(r.get('out') or '(无输出)')}")
            if not r.get("ok"):
                rc = 1
        return rc

    if act == "path":
        for st in stations:
            r = _reqlog_station(st, "path")
            print(f"[reqlog] {st} 站: {r.get('out')}")
        return 0

    # summary / tail
    res, threads = {}, []
    for st in stations:
        t = threading.Thread(target=lambda s=st: res.__setitem__(s, _reqlog_station(s, "tail", n)))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    if act == "tail":
        for st in stations:
            r = res.get(st, {})
            print(f"\n=== {st} 站 ({len(r.get('recs') or [])} 条) ===")
            for rec in (r.get("recs") or [])[-n:]:
                print(json.dumps(rec, ensure_ascii=False))
        return 0

    print(f"\n=== 引擎请求/token 统计 (P2-3, {('近 %d 分钟' % minutes) if minutes else '全部样本'}) ===")
    print(f"  口径: **引擎耗时口径** = ΣΔtoken/ΣΔ引擎耗时 (与 API timings 可比); "
          f"墙钟口径 = ΣΔtoken/ΣΔ采样间隔 (含空闲, 辅助)\n")
    hdr = (f"  {_pad('站', 3)} {_pad('样本', 4, True)} {_pad('跨度', 7, True)} "
           f"{_pad('prompt tok', 10, True)} {_pad('gen tok', 9, True)} "
           f"{_pad('pp t/s', 8, True)} {_pad('tg t/s', 8, True)} {_pad('忙占比', 7, True)} "
           f"{_pad('峰值并发', 8, True)} {_pad('重启', 4, True)}")
    print(hdr)
    # D6-P3-1: 分隔线长度必须按**显示宽度**算 —— `len(hdr)` 数的是码点, 含 CJK 时会画**短**
    print("  " + "-" * (_dw(hdr) - 2))
    any_rec = False
    for st in stations:
        r = res.get(st, {})
        if not r.get("ok"):
            print(f"  {st:<3} 站不可达/取日志失败")
            continue
        recs = r.get("recs") or []
        if not recs:
            print(f"  {st:<3} 无样本 (引擎未运行过, 或从未采样) "
                  f"—— 用 `cluster.py reqlog sample` 采一次")
            continue
        any_rec = True
        a = _reqlog_aggregate(recs, minutes)
        span = f"{a['span_s']}s" if a["span_s"] else "-"
        print(f"  {st:<3} {a['n']:>4} {span:>7} {a['p_tok']:>10.0f} {a['g_tok']:>9.0f} "
              f"{str(a['p_tps'] or '-'):>8} {str(a['g_tps'] or '-'):>8} "
              f"{str(a['g_busy_ratio'] if a['g_busy_ratio'] is not None else '-'):>7} "
              f"{a['peak_proc']:>8.0f} {a['restarts']:>4}")
        if a["restarts"]:
            print(f"      · 含 {a['restarts']} 次引擎重启 (计数器已归零, 增量从 0 起算)")
        if a["cached_tok"]:
            print(f"      · KV 前缀缓存命中 {a['cached_tok']:.0f} tok "
                  f"(占 prompt 的 {a['cached_tok'] / max(a['p_tok'], 1) * 100:.0f}%)")
        print(f"      · 端口 {sorted(a['ports']) or '-'} · decode 批次 {a['decode_n']:.0f} "
              f"· 采样峰值槽占用 {a['peak_slots']:.0f}")
    if any_rec:
        print(f"\n  注: /metrics 实测**无 requests 计数器** (只有 requests_processing 两个 gauge), "
              f"故不给「请求数」—— 不拿 decode 批次数冒名顶替")
    return 0


# ── flow: 声明式流程 (2026-09-15, 方案 v2 P2-1) ────────────────────
# 目的: 把"一次操作要走的一串步骤"从散落的一次性脚本收敛成**声明式表** ——
#   每个 flow 声明「步骤 → 判据 → 台账落点」, 一次跑完并留下记录。
# 学 LM Studio 的"一次点击完成一件事"; 范式来自 archive/scripts-history/b5_bench_cluster.sh
#   的五段式(读声明 → 起依赖 → 执行 → **无条件收尾** → 落账), 判据用退出码分层。
#
# 设计约定 (与既有纪律对齐):
#   · **只读 flow 默认执行; 会改站上状态的 flow 默认只出计划, 加 --go 才动手**
#     (沿用 `cluster.py models link|prune` 的 dry-run 约定)
#   · 判据既写进 step 的 run() 也用 criteria 字符串**声明出来** —— `flow <name> --plan`
#     会把"步骤→判据"整表打印, 跑之前就知道要满足什么
#   · 任一步 ok=False **立即中止**(fail-fast), 并执行已登记的 teardown
#   · 台账**只增不改**, 每条必带 日期 / 判据(口径) / 证据 三要素
#     (metrics-log 既有教训: 缺任一要素的记录无法复核)
#
# 为什么台账写入器是净新增件: 查过三份台账, **在此之前没有任何脚本写它们** ——
#   b5_bench_cluster.sh 只 echo 到 stdout(其 DESIGN 声称"自动追加 metrics-log"从未落地);
#   手册也写了"结果自动追加到 metrics-log", 同样是空头承诺。P2-1 补上这一环。
#
# 台账落点为何只挂 metrics-log: params-ledger 的表是「参数变更」(§4 修改历史),
#   results-ledger 是「模型评测」(按模型分节 + 5 列题号表), 各有专属 schema;
#   由脚本往别人的表里塞异构行会写坏它。故 flow 统一落 metrics-log 的"运行记录"节,
#   另两份台账保持人工维护 (不假装支持)。
# ⚠ `REPO_ROOT` 已下沉到 `cluster_const`（2026-10-28，拆模块前置：多组共用，留在门面会逼出反向依赖）
LEDGERS = {"metrics-log": REPO_ROOT / "spec" / "rpc-optimization" / "metrics-log.md"}
FLOW_SECTION = "## Phase 7: flow 运行记录 (2026-09-15 起, 由 `cluster.py flow` 自动追加)"
FLOW_TABLE_HEAD = ("| 日期 | flow | 目标 | 判据(口径) | 结果 | 证据 |\n"
                   "|---|---|---|---|---|---|")


def _ledger_append(ledger: str, row: str, dry: bool = True) -> str:
    """把一行记录追加到台账 (只增不改; 缺节则先补节与表头)。"""
    p = LEDGERS.get(ledger)
    if not p:
        return f"未知台账 {ledger!r} (可选: {', '.join(LEDGERS)})"
    if not p.is_file():
        return f"台账文件不存在: {p}"
    if dry:
        return f"[dry-run] 将追加到 {p.name}: {row}"
    text = p.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    if FLOW_SECTION not in text:
        text += f"\n{FLOW_SECTION}\n\n{FLOW_TABLE_HEAD}\n"
    text += row + "\n"
    p.write_text(text, encoding="utf-8")
    return f"已追加到 {p.name}"


def _flow_find_engine() -> tuple:
    """找"哪个站在服务"。返回 (station, port) 或 (None, None)。"""
    for st in ("A", "B", "C"):
        try:
            mt = probe_metrics(st)
        except Exception:
            continue
        if mt.get("port"):
            return st, mt["port"]
    return None, None


def _flow_bench_payload() -> str:
    """标准请求体。刻意**记录** prompt 的实际 token 数(取响应 timings), 而非假装它是 pp512。"""
    filler = "The quick brown fox jumps over the lazy dog. "
    return json.dumps({
        "model": "main",          # 引擎忽略该字段(ports.yaml 已登记), 仅占位
        "messages": [{"role": "user", "content": filler * 40}],
        "max_tokens": 128, "temperature": 0, "stream": False,
    })


def resolve_host_alias(alias: str) -> str:
    """别名 → 目标站代号 (借 resolve_alias, 只取站; 解析失败退默认站)。"""
    try:
        st, _real, _rpc, _how = resolve_alias(alias)
    except AliasError:
        return DEFAULT_STATION
    return st or DEFAULT_STATION


def _flow_step_probe_engine(ctx) -> tuple:
    st, port = _flow_find_engine()
    if st:
        ctx["station"], ctx["port"] = st, port
        return True, f"{st} 站引擎在服务 (127.0.0.1:{port})", []
    if ctx.get("alias"):
        ctx["station"] = resolve_host_alias(ctx["alias"])
        return (True if ctx["go"] else False,
                f"无引擎在服务; 目标是 {ctx['station']} 站的 {ctx['alias']}"
                + ("" if ctx["go"] else " —— 需要 --go 才会加载"),
                ["零自加载方针: 本 flow 不会擅自加载, 故默认只出计划"])
    return False, "三站都没有引擎在服务, 且未指定 alias", \
        ["用法: cluster.py flow bench [<alias前缀>] --go"]


def _flow_step_ensure_loaded(ctx) -> tuple:
    if ctx.get("port"):
        return True, "已在服务, 跳过加载", []
    if not ctx["go"]:
        return False, "需要加载 (--go 才执行)", []
    est = estimate_load(ctx["station"], ctx["alias"])
    ctx["estimate"] = est
    verdict = est.get("verdict", "UNKNOWN")
    if verdict == "NO_FIT":
        return False, f"事前预估 NO_FIT, 拒绝加载: {est.get('reasons')}", []
    rc = cmd_load(ctx["alias"])
    if rc != 0:
        return False, f"加载失败 (rc={rc})", []
    ctx["loaded_here"] = True
    st, port = _flow_find_engine()
    ctx["station"], ctx["port"] = st, port
    return (port is not None), f"加载完成, 引擎在 {st}:{port}", \
        ([f"预估: {verdict} need={est.get('need_gib')}G"] if est else [])


def _flow_step_bench(ctx) -> tuple:
    if not ctx.get("port"):
        return False, "无引擎可测", []
    st = ctx["station"]
    body = _flow_bench_payload().replace("'", "")
    cmd = (f"curl -s -m 300 -H 'Content-Type: application/json' -d '{body}' "
           f"http://127.0.0.1:{ctx['port']}/v1/chat/completions")
    ok, out = ssh_run(st, cmd, timeout=330)
    if not ok or not out.strip().startswith("{"):
        return False, f"请求失败: {(out or '')[:120]}", []
    try:
        r = json.loads(out)
        t = r.get("timings") or {}
    except Exception as e:
        return False, f"响应解析失败: {type(e).__name__}", [out[:160]]
    if not t:
        return False, "响应无 timings 字段 (非 llama.cpp 原生引擎?)", [out[:160]]
    ctx["timings"] = t
    return True, (f"pp {t.get('prompt_n')} tok @ {t.get('prompt_per_second', 0):.1f} t/s · "
                  f"tg {t.get('predicted_n')} tok @ {t.get('predicted_per_second', 0):.1f} t/s"), []


def _flow_teardown_bench(ctx) -> tuple:
    if not ctx.get("loaded_here"):
        return True, "本 flow 未加载, 无需收尾", []
    rc = cmd_unload()
    st, port = _flow_find_engine()
    return (rc == 0 and port is None), \
        f"已卸载 (rc={rc}); 复核: {'引擎已停' if port is None else f'仍在 {st}:{port}'}", []


def _flow_verify_checks(ctx) -> tuple:
    """复用健康引擎的断言表 (只读)。"""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import rpc_check
    except Exception as e:
        return False, f"无法导入 rpc_check ({type(e).__name__})", []
    want = ["inventory", "ports", "plugins", "aliases", "usb4", "gates", "engine",
            "models", "stations"]
    detail, fails = [], []
    for c in rpc_check.CHECKS:
        if c["id"] not in want:
            continue
        try:
            status, note, _d = c["fn"]({})
        except Exception as e:
            status, note = "FAIL", f"{type(e).__name__}: {e}"
        detail.append(f"[{status}] {c['id']:10s} {note}")
        if status == "FAIL":
            fails.append(c["id"])
    ctx["verify_failed"] = fails
    return (not fails), f"断言 {len(detail)} 项, 失败 {len(fails)} 项" + (
        f": {', '.join(fails)}" if fails else ""), detail


def _flow_rotate_status(ctx) -> tuple:
    # 2026-09-16 顺带修 (既有缺陷, 非本次引入): 原实现把 ssh_run 回来的**原始文本**喂给
    # `_secrets_verdict`(它期望 probe_secrets 的 dict) ⇒ `p["reachable"]` 直接 TypeError;
    # 且即便不崩, 下一行 `v != "OK"` 比的是 tuple ≠ str ⇒ 该步恒判"需关注"。
    # 改为直接调 probe_secrets 取状态字符串 (顺带去掉了那次多余的 ssh_run("A","true"))。
    verdicts = {}
    for st in ("A", "B", "C"):
        p = probe_secrets(st)
        verdicts[st] = _secrets_verdict(p)[0] if p.get("reachable") else "UNREACHABLE"
    ctx["rotate_verdicts"] = verdicts
    bad = [s for s, v in verdicts.items() if v != "OK"]
    return (not bad), "凭据落点/引用/权限: " + ", ".join(f"{s}={v}" for s, v in verdicts.items()), \
        ([f"{s} 站需关注 —— 见 `cluster.py secrets status`" for s in bad] if bad else [])


def _flow_rotate_scan(ctx) -> tuple:
    """明文门禁: 直接复用既有 `secrets scan`（它已覆盖"三站生效配置 + 归档"）。"""
    print("        (调用 cluster.py secrets scan ...)")
    rc = cmd_secrets("scan")
    return rc == 0, f"secrets scan rc={rc} (0=无明文命中)", \
        ([] if rc == 0 else ["有明文残留 —— 先按 scan 输出定位再轮换"])


def _flow_rotate_push(ctx) -> tuple:
    if not ctx["go"]:
        return False, "需要下发正本 (--go 才执行)", ["改完 secrets/stations/<站>/ 后执行"]
    rc = cmd_secrets("push")
    return rc == 0, f"正本下发 rc={rc}", []


def _flow_swap_precheck(ctx) -> tuple:
    est = estimate_load(ctx["station"], ctx["alias"])
    ctx["estimate"] = est
    v = est.get("verdict", "UNKNOWN")
    ok = v in ("FITS", "TIGHT")
    return ok, f"事前预估 {v} · need {est.get('need_gib')}G / 可用 {est.get('avail_effective')}G", \
        ([] if ok else (est.get("advice") or ["预估不通过在, 拒绝切换"]))


def _flow_swap_apply(ctx) -> tuple:
    """卸载与加载都在 cmd_load_on 里 (它先探 :8080 占用 → infer-unload → 加载)。

    刻意不再自己拆成一卸一装 —— 那会把"先卸后装、等 GTT 释放"的既有语义复制一份,
    两处实现迟早漂移 (与 P1-6 "取 conf 而非抄台账"同一条理由)。
    """
    if not ctx["go"]:
        return False, "需要按站加载 (--go)", []
    st, backend = ctx["station"], ctx.get("backend")
    rc = cmd_load_on(st, ctx["alias"], backend) if backend else cmd_load_on(st, ctx["alias"])
    return rc == 0, f"{st} 站加载 {ctx['alias']} rc={rc}", []


def _flow_swap_ready(ctx) -> tuple:
    st = ctx["station"]
    ps = probe_station(st, with_list=False)
    mt = probe_metrics(st)
    ok = ps.get("llama") == "READY" and bool(mt.get("port"))
    return ok, f"{st} 站 llama={ps.get('llama')} 引擎端口={mt.get('port') or '无'}", \
        ([] if ok else ["就绪判据未满足 —— 见 inference 日志 / infer-load 输出"])


def _flow_ledger_step(ctx) -> tuple:
    """统一的落账步骤: 只增不改 + 三要素。默认 dry-run。"""
    row = ctx.get("ledger_row")
    if not row:
        return True, "无记录可落 (跳过)", []
    msg = _ledger_append(ctx.get("ledger") or "metrics-log", row, dry=not ctx["go"])
    ctx["ledger_msg"] = msg
    return True, msg, []


# ── P2-4 路径对比 (单机 vs 双机) ───────────────────────────────────
# 供"决策门"用: 同一模型在两条路径上各跑一次实测基准, 输出对照表 + 推荐。
# **刻意不 fail-fast**: 对比类 flow 的判据是"每条路径都给出结论(可用/不可用 + 数据)",
# 而不是"任一条失败即中止" —— 某条路径跑不通本身就是决策所需的信息。
# (bench/swap/rotate 仍走 fail-fast; 这是 flow 声明的 continue_on_fail 开关。)
#
# 为什么双机侧不给"事前预估": `estimate_load` 的口径是**整个模型落在一站**,
# 而 RPC 会把层拆到两站, 权重与 KV 都分摊 —— 拿单站口径去套会得出错误结论。
# 与其编一个看似精确的粗判数字, 不如只给单机的精确预估 + 双机的**实测**。
# (双机是否可行的第一手判据 = 它能不能加载起来, 这也是实测能给的。)
def _station_gtt_gib(st: str):
    """站上 GTT 占用合计 (GiB); 取不到返回 None。

    **为什么内存代价必须用 GTT 而不是进程 RSS**: 本集群是 UMA (AMD 8060S), 模型权重驻留
    在 GTT/显存, **不进进程 RSS** —— 2026-09-15 实测: 加载 77G 的
    gpt-oss-120b-fable-5-distilled 后 `ps` 里 llama-server 的 RSS 只有 **217MB**,
    而同刻 GTT 是 **54.6 GB**, MemAvailable 掉了 57G。
    GTT 也正是站上前提门禁 (load-gate / infer-load 的 `mem_info_gtt_used`) 用的口径,
    故与"能不能装下"的判定同源。
    (另: `_station_mem` 的 `avail` 本身就是 **GiB**, 早版我又除了一次 1024 → 得 0.1G 假象。)
    """
    ok, out = ssh_run(st, "for f in /sys/class/drm/card*/device/mem_info_gtt_used; do "
                          "[ -f \"$f\" ] && cat \"$f\"; done")
    if not ok:
        return None
    tot = sum(int(x) for x in out.split() if x.isdigit())
    return round(tot / 1024 ** 3, 1)


def _flow_path_measure(ctx, backend: str, label: str) -> tuple:
    """跑一条路径: 预估(仅单机) → 加载 → 标准请求 → 卸载, 记录实测。"""
    st = ctx["station"]
    alias = ctx["alias"]
    rec = {"backend": backend, "label": label}
    gtt0 = _station_gtt_gib(st)
    t0 = time.time()
    rc = cmd_load_on(st, alias, backend)
    rec["load_s"] = round(time.time() - t0, 1)
    gtt1 = _station_gtt_gib(st)
    rec["gtt_gib"] = gtt1
    try:
        rec["gtt_used_gib"] = round(max(0.0, (gtt1 or 0) - (gtt0 or 0)), 1)
    except Exception:
        rec["gtt_used_gib"] = None
    if rc != 0:
        rec["ok"] = False
        rec["note"] = f"加载失败 rc={rc}"
        ctx.setdefault("paths", []).append(rec)
        cmd_unload()
        return False, f"{label}: 加载失败 (rc={rc}) —— 该路径不可用", \
            [f"加载耗时 {rec['load_s']}s"]
    port = probe_metrics(st).get("port")
    if not port:
        rec["ok"] = False
        rec["note"] = "加载后取不到内层引擎端口"
        ctx.setdefault("paths", []).append(rec)
        cmd_unload()
        return False, f"{label}: 加载后无引擎端口 —— 该路径不可用", []
    # **后端生效性判据 (本 flow 的核心防线)**: 判据不能只看"以为选了什么", 要看**进程
    # 命令行里到底有没有 --rpc**。2026-09-15 实测: `--backend llama-single` 因 conf 的
    # RPC_TARGET 未被清空 → 实际仍是双机, 于是"单机 vs 双机"两边都是双机;
    # 没有这一项, 这种错误数据会一路写进台账被当成结论。
    #
    # ⚠ 取命令行必须避开两个坑 (都实测踩到过):
    #   1) `pgrep -f llama-server` 会**匹配到执行它的 bash -c 包装进程本身** →
    #      `head -1` 拿到的是 bash 的 cmdline, 判据直接失效。改用 `pgrep -x` (按进程名
    #      **精确**匹配, 不做全命令行匹配) 就不会自匹配。
    #   2) 不截断: --rpc 往往出现在很长的命令行**靠后**位置, 截前 120 字符会漏判。
    # 故: 按 comm 精确取 pid → 读 /proc/<pid>/cmdline (NUL 转空格) 全文。
    cmdline = ssh_run(st, "p=$(pgrep -x llama-server | head -1); "
                          "[ -n \"$p\" ] && tr '\\0' ' ' < /proc/$p/cmdline || echo NOENGINE")[1]
    rpc_active = " --rpc" in f" {cmdline}"
    rec["rpc_active"] = rpc_active
    # 记下实际用了**哪些** worker —— RPC 路径可能是 1 个或 2 个 worker, 不记就说不清
    # 对照里的"双机"到底是几机 (nodes.env 声明 A+C, 都可能被用上)。
    m = re.search(r"--rpc\s+(\S+)", cmdline)
    rec["rpc_nodes"] = m.group(1) if m else None
    if rpc_active != (backend == "llama-rpc"):
        rec["ok"] = False
        rec["note"] = (f"请求 {backend}, 但进程{'含' if rpc_active else '不含'} --rpc "
                       f"—— 该路径未按请求生效, **数据不可用于对照**")
        ctx.setdefault("paths", []).append(rec)
        cmd_unload()
        return False, f"{label}: 后端未生效 —— {rec['note']}", [cmdline.strip()[:150]]
    body = _flow_bench_payload().replace("'", "")
    ok, out = ssh_run(st, f"curl -s -m 300 -H 'Content-Type: application/json' -d '{body}' "
                          f"http://127.0.0.1:{port}/v1/chat/completions", timeout=330)
    try:
        t = json.loads(out).get("timings") or {}
    except Exception:
        t = {}
    rec["port"] = port
    rec["pp_tps"] = round(t.get("prompt_per_second", 0), 1) or None
    rec["tg_tps"] = round(t.get("predicted_per_second", 0), 1) or None
    rec["prompt_n"] = t.get("prompt_n")
    rec["gen_n"] = t.get("predicted_n")
    rec["ok"] = bool(t)
    rec["note"] = "实测通过" if t else f"请求无 timings: {(out or '')[:80]}"
    ctx.setdefault("paths", []).append(rec)
    cmd_unload()                      # 每条路径跑完立刻收尾, 避免两条路径的残留互相污染内存读数
    if not t:
        return False, f"{label}: 请求无 timings —— 数据不可用", [rec["note"]]
    return True, (f"{label}: pp {rec['pp_tps']} t/s · tg {rec['tg_tps']} t/s "
                  f"(加载 {rec['load_s']}s, GTT +{rec['gtt_used_gib']}G)"), []


def _flow_paths_single(ctx) -> tuple:
    est = estimate_load(ctx["station"], ctx["alias"])
    ctx["est_single"] = est
    v = est.get("verdict", "UNKNOWN")
    ok = v in ("FITS", "TIGHT")
    return ok, f"单机事前预估 {v} · need {est.get('need_gib')}G / 可用 {est.get('avail_effective')}G", \
        ([] if ok else (est.get("advice") or ["预估不通过 —— 单机路径不可行"]))


def _flow_paths_run_single(ctx) -> tuple:
    return _flow_path_measure(ctx, "llama-single", "单机")


def _flow_paths_run_rpc(ctx) -> tuple:
    return _flow_path_measure(ctx, "llama-rpc", "双机 RPC")


def _flow_paths_report(ctx) -> tuple:
    """对照表 + 推荐。判据: 两条路径都有结论 (可用/不可用)。"""
    rows = ctx.get("paths") or []
    if not rows:
        return False, "没有任何路径的实测数据", []
    detail = []
    good = [r for r in rows if r.get("ok") and r.get("tg_tps")]
    for r in rows:
        detail.append(f"{r['label']:8s} {r['backend']:13s} "
                      f"{'✓' if r.get('ok') else '✕'} "
                      f"rpc={'是' if r.get('rpc_active') else '否'}"
                      + (f"({r.get('rpc_nodes')})" if r.get("rpc_nodes") else "")
                      + f" pp={r.get('pp_tps')} tg={r.get('tg_tps')} "
                      f"加载={r.get('load_s')}s GTT +{r.get('gtt_used_gib')}G "
                      f"({r.get('note', '')})")
    if len(rows) < 2:
        detail.append("只有一条路径有数据 —— 对照不完整 (另一条路径可能在加载阶段就失败了)")
    if good:
        best = max(good, key=lambda r: r["tg_tps"])
        # 推荐 = decode 更快者; 同档时选内存代价小的 (单机通常更省)
        detail.append(f"→ 推荐: **{best['label']}** ({best['tg_tps']} t/s) —— "
                      f"另一条路径 "
                      + (f"{min((r['tg_tps'] for r in good if r is not best), default=0)} t/s"
                         if len(good) > 1 else "无可用数据"))
    est = ctx.get("est_single") or {}
    if est.get("verdict"):
        detail.append(f"单机事前预估 {est['verdict']} (need {est.get('need_gib')}G) "
                      f"vs 实测 tg {next((r['tg_tps'] for r in rows if r['backend'] == 'llama-single'), '-')} t/s "
                      f"—— 预估判可行性与实测性能是两件事")
    ctx["paths_ok"] = bool(len(rows) >= 2 and any(r.get("ok") for r in rows))
    return bool(rows), f"{len(rows)} 条路径有结论, 其中 {len(good)} 条可用", detail


# ── flow: studio-upgrade 的步骤实现 (2026-09-23 增) ─────────────────────
# 为什么有这个 flow: 2026-09-22/23 的整轮升级是**内联 ssh + heredoc** 做的 —— 顺序与判据
#   只活在那一轮对话里，与 ADR-0004 D3① (管理操作应走统一入口) 相悖。本 flow 把当天**实测
#   通过**的顺序固定下来：预检(防线/下源) → 阶段应用 → 验证(版本/修复/引擎未动/防线) → 门禁 → 落账。
# 边界(刻意，不是"待补"): 只纳入 **python 阶段**。`--stage engine|node` **明确不支持并给出指引**，
#   而不是静默跳过 —— 因为引擎阶段需从 github.com 取 337.4 MiB 的 rocm bundle，node 阶段需
#   nodejs.org 取 ~200 MiB (api-only 形态用不到)；预检会把下源可达性打出来供你判断。
_SU_HOME = "$HOME/.unsloth/studio/unsloth_studio"
_SU_PY = _SU_HOME + "/bin/python"
_SU_SP = _SU_HOME + "/lib/python3.13/site-packages"
_SU_SHIM = "/tmp/.rpc-su-nogit"        # 前置 PATH 的假 git (exit 127) ⇒ 走脚本自带的 no-git 跳过分支
_SU_INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple"


def _flow_step_su_precheck(ctx) -> tuple:
    """防线(pin) + 三站套件现状 + 下源可达性。判据 = 每站 pin 生效且可达。"""
    sts = ([s for s in (ctx.get("station") or "").upper().replace(" ", "").split(",") if s]
           or ["A", "B", "C"])
    ctx["stations"] = sts
    rows, detail = {}, []
    for st in sts:
        d = probe_studio(st)
        rows[st] = d
        if not d.get("reachable"):
            return False, f"{st} 站不可达", detail
        detail.append(f"{st}: studio {d.get('studio_ver') or '?'} · pin {d.get('pin') or '(空)'} "
                      f"· 修复 {d.get('events') or '0'} · 引擎 {(d.get('engine_md5') or '?')[:12]}")
    ctx["pre"] = rows
    bad = [s for s in sts if rows[s].get("pin") != "rocm"]
    if bad:
        return False, ("pin 未生效: " + " / ".join(bad) + " —— 先落 /etc/environment 的 "
                       "UNSLOTH_LLAMA_CPP_BACKEND=rocm (见决策简报 §8.2)"), detail
    ok, out = ssh_run(sts[0],
                      "for u in " + _SU_INDEX + "/ https://github.com; do printf '%s ' \"$u\"; "
                      "curl -sS -o /dev/null -w '%{http_code}\\n' --max-time 6 \"$u\" 2>/dev/null || echo FAIL; done",
                      timeout=40)
    ctx["net"] = (out or "").strip()
    detail.append("下源可达性(" + sts[0] + " 站): " + " | ".join((out or "").split()))
    return True, f"防线在位 · {len(sts)} 站预检通过", detail


def _flow_step_su_apply(ctx) -> tuple:
    """按阶段应用。本 flow 只实现 python 阶段 (engine/node 明确不支持并给指引)。"""
    stage = (ctx.get("stage") or "python").lower()
    sts = ctx["stations"]
    if stage in ("engine", "node"):
        why = ("引擎阶段需从 github.com 取 **337.4 MiB** 的 rocm bundle (实测 A/C 直连不通、"
               "B 仅 ~35 KB/s ⇒ 1.3–2.7 h)，见决策简报 §8.3" if stage == "engine"
               else "node 阶段需从 nodejs.org 取 ~200 MiB (站上 Node 只有前端需要，api-only 用不到)")
        return False, f"--stage {stage} **本 flow 明确不纳入** —— {why}；请按简报 §8.3 的预置/中转手法做", []
    to = (ctx.get("to") or "").strip()
    detail, failed = [], None
    for st in sts:
        cmd = ("set -u; mkdir -p " + _SU_SHIM
               + "; printf '#!/bin/sh\\nexit 127\\n' > " + _SU_SHIM + "/git; chmod 755 " + _SU_SHIM + "/git; "
               + "PATH=\"" + _SU_SHIM + ":$PATH\" "
               + "UV_INDEX_URL=" + _SU_INDEX + " UV_DEFAULT_INDEX=" + _SU_INDEX
               + " PIP_INDEX_URL=" + _SU_INDEX + " STUDIO_PACKAGE_NAME=unsloth "
               + _SU_PY + " " + _SU_SP + "/studio/install_python_stack.py > /tmp/rpc-su.log 2>&1; rc=$?; "
               + ("PIP_INDEX_URL=" + _SU_INDEX + " " + _SU_PY + " -m pip install -q \"unsloth==" + to
                  + "\" >> /tmp/rpc-su.log 2>&1; rc=$?; " if to else "")
               + "rm -rf " + _SU_SHIM + "; tail -4 /tmp/rpc-su.log; exit $rc")
        ok, out = ssh_run(st, cmd, timeout=1800)
        tail = " / ".join((out or "").strip().splitlines()[-2:])[:180]
        detail.append(f"{st}: rc={'0' if ok else '非 0'} · {tail}")
        if not ok:
            failed = st
            break
    if failed:
        return False, f"{failed} 站 {stage} 阶段失败 (命令 rc 非 0；站上日志 /tmp/rpc-su.log)", detail
    return True, f"{len(sts)} 站 {stage} 阶段完成" + (f" · 目标版本 {to}" if to else ""), detail


def _flow_step_su_verify(ctx) -> tuple:
    """升级后验证: 版本==目标 · 修复在位 · pin 仍在 · (只跑 python 阶段时) 引擎 md5 未变。"""
    stage = (ctx.get("stage") or "python").lower()
    to = (ctx.get("to") or "").strip()
    sts, pre = ctx["stations"], (ctx.get("pre") or {})
    detail, bad = [], []
    for st in sts:
        d = probe_studio(st)
        v = d.get("studio_ver")
        if to and v != to:
            bad.append(f"{st} 版本 {v or '?'} ≠ 目标 {to}")
        if not d.get("events") or d["events"] == "0":
            bad.append(f"{st} 缺 `X-Unsloth-Events` 修复")
        if d.get("pin") != "rocm":
            bad.append(f"{st} pin 丢失 ({d.get('pin') or '(空)'})")
        was = (pre.get(st) or {}).get("engine_md5")
        if stage == "python" and was and d.get("engine_md5") != was:
            bad.append(f"{st} 引擎 md5 **变了** ({(was or '?')[:12]} → {(d.get('engine_md5') or '?')[:12]})"
                       f" —— 只跑 python 阶段不该动引擎")
        detail.append(f"{st}: studio {v or '?'} · 修复 {d.get('events') or '0'} · pin {d.get('pin') or '(空)'} "
                      f"· 引擎 {(d.get('engine_md5') or '?')[:12]}")
    if bad:
        return False, "验证不通过", bad + detail
    return True, "版本/修复/防线 通过" + (" · 引擎未被动" if stage == "python" else ""), detail


def _flow_step_su_gate(ctx) -> tuple:
    """门禁复核: 复用 rpc_check 的 backend + engine 两项断言 (子进程, 同一个解释器)。"""
    r = subprocess.run([sys.executable, str(REPO_ROOT / "ops" / "rpc_check.py"), "--only", "backend,engine"],
                       capture_output=True, text=True, timeout=300)
    lines = [ln.strip() for ln in (r.stdout or "").splitlines()
             if "结论:" in ln or "[FAIL]" in ln or "[WARN]" in ln]
    ok = (r.returncode == 0)
    return ok, ("门禁通过" if ok else f"门禁未通过 (rc={r.returncode})"), lines[:6]


# 每个 flow: 步骤 → 判据 → 台账落点。dry_default=True 者默认只出计划。
FLOWS = {
    "verify": {
        "title": "健康引擎全项校验",
        "desc": "复用 rpc_check 的 9 项三站断言, 一次给结论 (只读)",
        "dry_default": False,      # 只读 → 默认执行
        "ledger": "metrics-log",
        "steps": [
            ("checks", "健康引擎断言", "全部 PASS (无 FAIL)", _flow_verify_checks),
        ],
    },
    "bench": {
        "title": "引擎基准 (API timings 口径)",
        "desc": "对已就绪引擎发标准请求, 从响应的 timings 取 pp/tg, 并落 metrics-log",
        "dry_default": True,       # 可能加载模型 → 默认只出计划
        "ledger": "metrics-log",
        "steps": [
            ("engine", "定位在服务的引擎", "三站之一有引擎端口", _flow_step_probe_engine),
            ("load", "确保目标就绪", "已有引擎, 或预估非 NO_FIT 且加载成功", _flow_step_ensure_loaded),
            ("bench", "标准请求取 timings", "HTTP 200 且响应含 timings", _flow_step_bench),
        ],
        "teardown": _flow_teardown_bench,
    },
    "studio-upgrade": {
        "title": "studio 套件升级 (Python 阶段；默认三站同升)",
        "desc": "预检(防线 pin / 下源可达) → 阶段应用 → 验证(版本·修复·引擎未动·防线) → 门禁 → 落账。"
                "只纳入 python 阶段；`--stage engine|node` 明确不支持(见决策简报 §8.3)。"
                "用法: flow studio-upgrade [--to 2026.9.7] [--stage python] [--station C] --go",
        "dry_default": True,       # 改站上状态 → 默认只出计划
        "ledger": "metrics-log",
        "steps": [
            ("precheck", "防线与下源预检", "三站可达 且 pin=rocm", _flow_step_su_precheck),
            ("apply", "按阶段应用", "命令 rc=0 (python 阶段: install_python_stack; --to 则压回版本)", _flow_step_su_apply),
            ("verify", "升级后验证", "版本==目标 且 修复在位 且 pin 仍在 且 引擎未被动", _flow_step_su_verify),
            ("gate", "门禁复核", "rpc_check --only backend,engine 无 FAIL", _flow_step_su_gate),
        ],
    },
    "swap": {
        "title": "换模型/后端 (按站)",
        "desc": "事前预估 → 卸载该站 → 加载新目标 → 就绪复核",
        "dry_default": True,
        "ledger": "metrics-log",
        "steps": [
            ("precheck", "事前预估", "verdict ∈ {FITS, TIGHT}", _flow_swap_precheck),
            ("apply", "按站加载 (含自动卸载/GTT 等待)", "cmd_load_on rc=0", _flow_swap_apply),
            ("ready", "就绪复核", "llama=READY 且有引擎端口", _flow_swap_ready),
        ],
    },
    "rotate": {
        "title": "凭据轮换 (下发 + 复核)",
        "desc": "巡检落点/引用/权限 → 明文门禁 → 下发正本 → 复核。只做运维侧, 不生成新密钥",
        "dry_default": True,
        "ledger": "metrics-log",
        "steps": [
            ("status", "凭据现状巡检", "三站 verdict=OK", _flow_rotate_status),
            ("scan", "明文门禁", "命中 0 处", _flow_rotate_scan),
            ("push", "下发正本", "cmd_secrets push rc=0", _flow_rotate_push),
        ],
    },
    "paths": {
        "title": "路径对比: 单机 vs 双机 (决策门)",
        "desc": "同一模型在两条路径上各做一次实测基准, 输出对照表与推荐 —— 供'该走哪条路径'决策",
        "dry_default": True,
        "continue_on_fail": True,   # 对比类: 某条路径不通本身就是结论, 不能 fail-fast
        "ledger": "metrics-log",
        "steps": [
            ("est", "单机事前预估", "verdict ∈ {FITS, TIGHT} 才值得实测", _flow_paths_single),
            ("single", "单机实测 (加载→基准→留存)",
             "HTTP 200 且含 timings", _flow_paths_run_single),
            ("rpc", "双机 RPC 实测 (RPC 编排→加载→基准)",
             "加载成功且含 timings (双机无单站口径的事前预估, 只认实测)", _flow_paths_run_rpc),
            ("report", "对照与推荐", "两条路径都给出结论 (可用/不可用 + 数据)", _flow_paths_report),
        ],
    },
}


def _flow_usage() -> str:
    lines = ["用法: cluster.py flow {list|<name>} [--plan|--go] [--no-ledger] [args...]", "",
             "  --plan       只打印步骤与判据, 不执行任何一步 (只读信息用各自的专用命令)",
             "  --go         执行会改站上状态的 flow; 也决定是否**真落账**",
             "  --no-ledger  跑了但不落账 (负向测试/试跑用, 避免污染台账)", "",
             "flow 内置表 (步骤 → 判据 → 台账落点):"]
    for name, f in FLOWS.items():
        d = "默认出计划(--go 执行)" if f["dry_default"] else "默认执行"
        lines.append(f"\n  {name:8s} {f['title']}  [{d}] → {f['ledger']}")
        lines.append(f"           {f['desc']}")
        for i, (sid, title, crit, _fn) in enumerate(f["steps"], 1):
            lines.append(f"           {i}. {title:16s} 判据: {crit}")
        if f.get("teardown"):
            lines.append("           ↳ 收尾: 本次若加载过则自动卸载")
    return "\n".join(lines)


def cmd_flow(argv) -> int:
    """cluster.py flow —— 声明式流程 (P2-1)。"""
    if not argv or argv[0] in ("-h", "--help", "list"):
        print(_flow_usage())
        return 0
    name = argv[0]
    f = FLOWS.get(name)
    if not f:
        print(f"未知 flow: {name}\n\n{_flow_usage()}")
        return 2
    rest = argv[1:]
    # 先剔掉带值的开关, 免得 `flow swap --backend vllm gpt-oss` 把 vllm 当成 alias
    positional, ctx = [], {"flow": name, "ledger": f["ledger"],
                           "go": ("--go" in rest), "plan_only": ("--plan" in rest),
                           "no_ledger": ("--no-ledger" in rest)}
    i = 0
    while i < len(rest):
        a = rest[i]
        # 带值开关统一表: 形态 `--x <v>` ⇒ ctx["x"]。加新开关只改这张表, 不再加分支。
        key = {"--backend": "backend", "--station": "station",
               "--to": "to", "--stage": "stage"}.get(a)
        if key and i + 1 < len(rest):
            ctx[key] = rest[i + 1]
            i += 2
            continue
        if not a.startswith("--"):
            positional.append(a)
        i += 1
    if positional:
        ctx["alias"] = positional[0]
    if name == "bench":
        ctx.setdefault("alias", None)
    if name in ("swap", "paths"):
        if not ctx.get("alias"):
            print(f"{name} 需要目标: cluster.py flow {name} <alias前缀>"
                  + (" [--backend X]" if name == "swap" else "") + " [--go]")
            return 2
        ctx["station"] = resolve_host_alias(ctx["alias"])

    mode = "计划" if (ctx["plan_only"] or (f["dry_default"] and not ctx["go"])) else "执行"
    print(f"\n=== flow {name}: {f['title']} [{mode}] ===")
    print(f"  {f['desc']}")
    if ctx.get("alias"):
        print(f"  目标: {ctx['alias']}" + (f" @ {ctx['station']} 站" if ctx.get("station") else ""))
    print()

    n = len(f["steps"])
    failed_at, step_fails, guard_fail = None, [], False
    for i, (sid, title, crit, fn) in enumerate(f["steps"], 1):
        print(f"  [{i}/{n}] {title}")
        print(f"        判据: {crit}")
        if mode == "计划":
            print("        - 计划模式: 未执行")
            continue
        try:
            ok, note, detail = fn(ctx)
        except Exception as e:
            ok, note, detail = False, f"异常 {type(e).__name__}: {e}", []
        print(f"        {'✓' if ok else '✕'} {note}")
        for d in (detail or [])[:6]:
            print(f"          · {d}")
        if not ok:
            step_fails.append(title)
            if not f.get("continue_on_fail"):
                failed_at = title
                break
            # continue_on_fail: 中间步骤失败只算"部分完成"; **最后一步失败 = 整体失败**
            # (最后一步是"对照/报告", 它给不出结论就说明这个 flow 白跑了)
            guard_fail = (i == n)
    if not failed_at and step_fails and not f.get("continue_on_fail"):
        failed_at = step_fails[0]
    teardown = f.get("teardown")
    if teardown and mode == "执行":
        print("  收尾")
        try:
            ok, note, _d = teardown(ctx)
        except Exception as e:
            ok, note = False, f"异常 {type(e).__name__}: {e}"
        print(f"        {'✓' if ok else '✕'} {note}")

    # 落账行 (日期 / flow / 目标 / 判据(口径) / 结果 / 证据 三要素齐)
    t = ctx.get("timings") or {}
    # 默认取**该 flow 末步的判据**(= 验收判据)：这样新增 flow 不用再回来改这条链,
    # 也不会串台 (2026-09-23 实测: studio-upgrade 的行曾误用 bench 的"API timings"文案)。
    crit = f["steps"][-1][2] if f.get("steps") else "—"
    if name == "bench":
        crit = (f"API timings 口径 · max_tokens=128 · prompt 实测 {t.get('prompt_n', '?')} tok")
    elif name == "verify":
        crit = "健康引擎 9 项断言全 PASS"
    elif name == "rotate":
        crit = "凭据落点/引用/权限 OK + 明文 0 命中"
    elif name == "swap":
        crit = "预估 FITS/TIGHT + 就绪 READY"
    elif name == "paths":
        crit = "API timings 口径 · 单机 vs 双机各一次实测 (同请求体, max_tokens=128)"
    result = "PLAN" if mode == "计划" else ("FAIL" if (failed_at or guard_fail)
                                            else ("PARTIAL" if step_fails else "PASS"))
    target = ctx.get("alias") or ctx.get("station") or "-"
    if ctx.get("alias") and ctx.get("station"):
        target += f"@{ctx['station']}"
    if name == "bench" and t:
        ev = (f"pp {t.get('prompt_n')} tok {t.get('prompt_per_second', 0):.1f} t/s · "
              f"tg {t.get('predicted_n')} tok {t.get('predicted_per_second', 0):.1f} t/s")
    elif name == "verify":
        ev = f"断言失败 {len(ctx.get('verify_failed') or [])} 项"
    elif name == "rotate":
        ev = "verdicts " + ",".join(f"{k}={v}" for k, v in (ctx.get("rotate_verdicts") or {}).items())
    elif name == "paths":
        ev = " / ".join(f"{r['label']} tg={r.get('tg_tps') or '不可用'}" for r in (ctx.get("paths") or []))
    else:
        ev = ctx.get("estimate", {}).get("verdict", "-") if ctx.get("estimate") else "-"
    ctx["ledger_row"] = (f"| {time.strftime('%Y-%m-%d %H:%M')} | {name} | {target} | {crit} "
                         f"| {result} | {ev} |")
    # 只有真正跑过才落账 (计划模式只预览); --no-ledger 给"只跑不落账"留出口 ——
    # 负向测试/试跑不该污染台账 (2026-09-15 实测: 测试跑的 FAIL 行落进了 metrics-log)。
    if mode == "执行" and not ctx.get("no_ledger"):
        _ok, lmsg, _d = _flow_ledger_step(ctx)
        print(f"  落账\n        {lmsg}")
    elif ctx.get("no_ledger"):
        print(f"  落账\n        [--no-ledger] 已跳过 (仅本次不落)")
    else:
        print(f"  落账 (计划)\n        [dry-run] {ctx['ledger_row']}")

    print(f"\n  结论: flow {name} {result}"
          + (f" (中止于「{failed_at}」)" if failed_at else "")
          + (f" (部分完成: {len(step_fails)} 步未达标 —— 见上)" if (step_fails and not failed_at) else "")
          + "\n")
    # PARTIAL 仍是"跑完了、有结论", 不算失败; 只有 FAIL(含最后一步失败) 才返回 1
    return 1 if (failed_at or guard_fail) else 0


