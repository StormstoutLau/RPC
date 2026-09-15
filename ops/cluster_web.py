#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cluster_web.py — cluster.py web 子命令: 傻瓜式推理框架管理 Web UI (按需服务, 主控站)
零外部框架依赖 (纯 stdlib http.server + paramiko)。用 Ctrl-C 退出即停, 不常驻。

用法:
    python ops/cluster.py web [--host 127.0.0.1] [--port 8095] [--token <可选>]

端点:
    GET  /            单页 HTML (公开)
    GET  /api/status  三站框架状态 + 引擎 :8080 + 加载实例  (需 token)
    POST /api/load    {alias, backend?} 加载模型            (需 token)
    POST /api/unload  三站并行卸载                          (需 token)
    POST /api/backend {alias, backend} 切换后端一次命令      (需 token)

鉴权: X-Auth-Token header; 首次 401 前端弹 token 存 localStorage。
设计: spec/d2-cluster-cli/  .trae/documents/cluster-web-ui-实现计划.md
"""
import io
import re
import sys
import json
import time
import socket
import secrets
import contextlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import cluster  # 复用 ssh_run / probe_frames / cmd_load / cmd_unload / BACKENDS / ROUTE 等

WEB_HOST = "127.0.0.1"
WEB_PORT = 8095

# 前端模型清单改为 /api/models 动态渲染 (2026-09-15):
# 旧实现 _model_suggestions() 只返回 ROUTE(2)+RPC_MODELS(2) 共 4 个静态名字, 与实际
# 可加载模型 (站上 /data/models/gguf/*/*/, 10+) 严重不符 —— 见 _station_models 注释。


def _collect_status():
    """聚合三站: 框架探测 + 引擎 :8080 health + 加载实例。返回可 JSON 化 dict。

    并行说明 (2026-09-14, 修 CHECKLIST F19): 复用 cluster 里**已并行**的
    collect_frames() / collect_status(), 而不是逐站串行调用 (原实现为
    3×probe_frames + 3×probe_station 串行 = 9 次 ssh, 实测 129.6s)。
    """
    fd = cluster.collect_frames()      # 三站并行
    st_status = cluster.collect_status(with_list=False)   # 三站并行; 跳过慢的 infer-list
    base = {"time": st_status["time"], "stations": {}}
    for st in ("A", "B", "C"):
        f = fd.get(st, {})
        ps = st_status["stations"].get(st, {})
        fr = {}
        for name in ("llama", "unsloth", "vllm", "litellm", "opencode", "claude"):
            status, detail = f.get("frames", {}).get(name, ("Unknown", ""))
            fr[name] = {"status": status, "detail": detail}
        base["stations"][st] = {
            "reachable": f.get("reachable", False),
            "frames": fr,
            "engine": ps.get("llama", "?"),
            "loaded": ps.get("loaded", "?"),
        }
    return base


# ── 模型清单 (2026-09-15 新增) ────────────────────────────────
# 为什么: 旧实现 _model_suggestions() 只把 ROUTE(2) + RPC_MODELS(2) 共 4 个名字
# 塞进下拉框。而站上实际可加载模型有 10+ 个 —— infer-load 扫的是
# /data/models/gguf/*/*/ 并按需**自动生成 conf**, 所以"有权重 = 可加载"。
# 结果: B/C 站的 MiniMax-M2.7 等根本不在下拉里, 用户既看不到也点不了。
# 新实现直扫站上模型库 (与 infer-load 同一数据源), 保证"页面所见 = 站上可加载"。
_MODEL_SCAN = (
    "echo '===M==='; "
    # 深度用 -mindepth 2 不限上限: 实测三种落点 (仓库级直放 / 模型目录 / 模型目录下的量化子目录),
    # 早期写 -mindepth 3 会漏掉"仓库级直放"那一类 (B 站 davidau-q38-27b-q4k, 有 conf、能加载,
    # 却在清单里看不到)。分组规则见 cluster.group_by_model。
    "find -L /data/models/gguf -mindepth 2 -name '*.gguf' ! -name 'mmproj*' -printf '%s|%p\\n' 2>/dev/null; "
    "echo '===C==='; ls /etc/llama-instances/ 2>/dev/null; "
    # 物理库与聚合视图的差集 = 孤儿 (物理库有、聚合视图无 → 清单看不到、也加载不了)。
    # 见 cluster._scan_models 的说明; 这里并进同一次 ssh, 避免多一轮往返。
    "echo '===PHY==='; find -L ~/.lmstudio/models -mindepth 2 -maxdepth 2 -type d 2>/dev/null "
    "| sed 's|.*/models/||' | sort; "
    "echo '===AGG==='; find -L /data/models/gguf -mindepth 2 -maxdepth 2 -type d 2>/dev/null "
    "| sed 's|.*/gguf/||' | sort; "
    "echo '===BRK==='; find /data/models/gguf -mindepth 2 -maxdepth 2 -type l "
    "! -exec test -e {} \\; -print 2>/dev/null | sed 's|.*/gguf/||' | sort; "
    # P1-6 模型元数据 (原生 ctx / 量化 / conf 加载参数): 并进同一次 ssh。
    # 采集器与解析器都在 cluster.py —— 单一定义点, CLI `models meta` 复用同一份。
    + cluster._MODEL_META_SCAN
)


def _alias_of(model_dir: str) -> str:
    """目录名 → infer-load 别名 (单一定义点在 cluster.alias_of)。"""
    return cluster.alias_of(model_dir)



def _station_models(st: str) -> dict:
    """单站: 模型库清单 (含大小/conf 状态/是否已加载/元数据) + 引擎态。"""
    d = {"station": st, "reachable": False, "engine": "?", "loaded": "?", "models": []}
    # timeout 120: 这次 ssh 里含 find + 每个 gguf 一次 gguf-meta (实测单站 0.5~15s, 视模型数)
    ok, out = cluster.ssh_run(st, _MODEL_SCAN, timeout=120)
    if not ok:
        return d
    d["reachable"] = True
    m_part, _, tail = out.partition("===C===")
    c_part, _, phy_agg = tail.partition("===PHY===")
    phy_raw, _, rest_agg = phy_agg.partition("===AGG===")
    agg_raw, _, rest_brk = rest_agg.partition("===BRK===")
    # BRK 段**必须**在 ===G=== 处截断: 后面还有 P1-6 的元数据段, 不截断会把
    # 每条元数据行都当成一个"断链"(2026-09-15 实测踩到: 断链数被虚报为 10/29/17)。
    brk_raw, _, _meta = rest_brk.partition("===G===")
    # 孤儿 = 物理库有、聚合视图无 (→ 清单看不到、infer-load 也找不到, 需补软链)
    # 断链 = 聚合视图里的软链指向不存在的目标 (真目录不算, 见 cluster._scan_models)
    phy_set = {x.strip() for x in phy_raw.splitlines() if x.strip()}
    agg_set = {x.strip() for x in agg_raw.splitlines() if x.strip()}
    d["unmanaged"] = sorted(phy_set - agg_set)
    d["broken"] = sorted(x.strip() for x in brk_raw.splitlines() if x.strip())
    size_of = {}
    for line in m_part.replace("===M===", "").splitlines():
        line = line.strip()
        if "|" not in line:
            continue
        sz, _, path = line.partition("|")
        try:
            size_of[path] = size_of.get(path, 0) + int(sz)
        except ValueError:
            pass
    # 模型粒度 (repo, model_dir) 的单一定义点在 cluster.group_by_model —— 它也处理
    # "仓库级直放"(<repo>/<file>.gguf) 这一形态, 见其 docstring。
    groups = cluster.group_by_model(size_of)
    sizes = {k: sum(size_of[p] for p in ps) for k, ps in groups.items()}
    # P1-6 元数据: 原生 ctx / 量化 / conf 加载参数 (解析器与 CLI 共用)
    meta = cluster.parse_model_meta(out)
    gguf_meta, conf_params = meta["gguf"], meta["params"]
    confs = {c for c in c_part.split() if c.endswith(".env")}
    ps = cluster.probe_station(st, with_list=False)
    d["engine"] = ps.get("llama", "?")
    d["loaded"] = ps.get("loaded", "?")
    loaded_low = (ps.get("loaded") or "").lower()
    for (repo, model), sz in sorted(sizes.items()):
        alias = _alias_of(model or repo)
        disp = re.sub(r"-GGUF$", "", model or repo, flags=re.I)
        # 已加载判定: A 站 unsloth 报的是 "gpt-oss-120b-MXFP4", 目录名是 "gpt-oss-120b-GGUF",
        # 故用"显示名的首个词段"做包含匹配 (gpt-oss-120b / m27 / qwen3.8 等前缀足够区分)。
        stem = disp.lower().split("-")[0]
        rep = cluster.pick_representative(groups[(repo, model)])
        gm = gguf_meta.get(rep, {})
        quant, quant_src = cluster.resolve_quant(alias, rep)
        d["models"].append({
            "alias": alias,
            "display": disp,
            "repo": repo,
            "size_gb": round(sz / 1073741824, 1),
            "has_conf": (alias + ".env") in confs,
            "loaded": bool(loaded_low) and bool(stem) and stem in loaded_low,
            # ── P1-6 元数据 ──
            # ctx_native: 模型自带上下文上限 (GGUF); ctx: 站上 conf 的实际加载值。
            # 两者常不同 (如 qwen3.8-27b-mtp 原生 262144 / B 站按 32768 加载) ——
            # 它们回答的是不同问题, 故并列暴露, 不合并。
            "ctx_native": gm.get("ctx"),
            "arch": gm.get("arch") or "",
            "quant": quant,
            "quant_src": quant_src,
            "params": conf_params.get(alias) or {},
        })
    return d


def _collect_models():
    """三站模型清单聚合 (并行)。耗时主要在站上 find, 三站并行 ~数秒。"""
    res = {}
    threads = [threading.Thread(target=lambda s=st: res.__setitem__(s, _station_models(s)))
               for st in ("A", "B", "C")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return {"time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "stations": {st: res.get(st, {}) for st in ("A", "B", "C")}}


def _collect_metrics():
    """三站引擎指标聚合 (并行): 内层端口 + Prometheus /metrics + /slots。

    数据源是 llama.cpp 原生端点 (见 cluster.probe_metrics), 不引入 exporter/时序库。
    """
    res = {}
    threads = [threading.Thread(target=lambda s=st: res.__setitem__(s, cluster.probe_metrics(s)))
               for st in ("A", "B", "C")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return {"time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "stations": {st: res.get(st, {}) for st in ("A", "B", "C")}}


def _collect_versions():
    """三站引擎版本矩阵 (并行)。P1-3: 暴露版本漂移与受控路径完整性缺口。"""
    res = {}
    threads = [threading.Thread(target=lambda s=st: res.__setitem__(s, cluster.probe_versions(s)))
               for st in ("A", "B", "C")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return {"time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "stations": {st: res.get(st, {}) for st in ("A", "B", "C")}}


def _collect_planes():
    """凭据 / Provider / 出站 三平面聚合 (统一入口的 ②③ 平面)。"""
    sec, pv, eg = {}, {}, {}
    threads = []
    for st in ("A", "B", "C"):
        threads.append(threading.Thread(target=lambda s=st: sec.__setitem__(s, cluster.probe_secrets(s))))
        threads.append(threading.Thread(target=lambda s=st: pv.__setitem__(s, cluster.probe_providers(s))))
        threads.append(threading.Thread(target=lambda s=st: eg.__setitem__(s, cluster.probe_egress_station(s))))
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    out = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "secrets": {}, "providers": {}, "egress": {}}
    for st in ("A", "B", "C"):
        state, note = cluster._secrets_verdict(sec.get(st, {}))
        out["secrets"][st] = {"state": state, "note": note}
        d = pv.get(st, {}) or {}
        out["providers"][st] = {"opencode": d.get("opencode", {}), "claude": d.get("claude", {})}
        r = eg.get(st, {}) or {}
        out["egress"][st] = {"http": r.get("http"), "time": r.get("time"), "info": r.get("info", {})}
    return out


def _run_capture(fn):
    """在后台线程执行 fn (write 到 stdout 会被捕获), 返回 {rc, log}。"""
    buf = io.StringIO()
    result = {}

    def _target():
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            result["rc"] = fn()

    t = threading.Thread(target=_target)
    t.start()
    t.join()
    return {"rc": result.get("rc", 1), "log": buf.getvalue()}


def _load_action(alias, backend):
    if backend is None:
        rc = cluster.cmd_load(alias)
    else:
        # 换后端与加载同为 cmd_load(alias, backend); 白名单校验已在 cmd_load 内
        rc = cluster.cmd_load(alias, backend)
    return rc


class Handler(BaseHTTPRequestHandler):

    server_version = "ClusterWeb/0.1"
    _token = ""
    _page = ""

    def _auth_ok(self):
        return self.headers.get("X-Auth-Token", "") == self._token

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text(self, code, text, ctype="text/html; charset=utf-8"):
        body = text.encode("utf-8") if isinstance(text, str) else text
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body_json(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length:
                return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            pass
        return {}

    def do_GET(self):
        # ⚠️ 必须先剥离 query string! `self.path` 形如 "/?token=xxx",
        # 直接与 "/" 比较会失配 → 免输链接 /?token=… 会返回 {"error":"not found"}。
        # 2026-09-15 实测踩到: 只测了不带 query 的 "/", 漏测了带 token 的真实入口。
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            return self._text(200, self._page)
        if path == "/api/status":
            if not self._auth_ok():
                return self._json(401, {"error": "unauthorized"})
            return self._json(200, _collect_status())
        if path == "/api/models":
            if not self._auth_ok():
                return self._json(401, {"error": "unauthorized"})
            return self._json(200, _collect_models())
        if path == "/api/versions":
            if not self._auth_ok():
                return self._json(401, {"error": "unauthorized"})
            return self._json(200, _collect_versions())
        if path == "/api/metrics":
            if not self._auth_ok():
                return self._json(401, {"error": "unauthorized"})
            return self._json(200, _collect_metrics())
        if path == "/api/planes":
            if not self._auth_ok():
                return self._json(401, {"error": "unauthorized"})
            return self._json(200, _collect_planes())
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self._auth_ok():
            return self._json(401, {"error": "unauthorized"})
        body = self._body_json()
        path = urlparse(self.path).path      # 同上: 剥离 query string
        if path == "/api/load":
            alias = (body.get("alias") or "").strip()
            station = (body.get("station") or "").strip().upper()
            if not alias:
                return self._json(400, {"error": "alias required"})
            if station:
                # 按站加载 (2026-09-15): 用户在某一站的模型列表里点了"加载",
                # 目标站已明确 → 走 cmd_load_on (跳过别名路由, 不再"猜站")。
                if station not in ("A", "B", "C"):
                    return self._json(400, {"error": f"bad station '{station}'"})
                res = _run_capture(lambda: cluster.cmd_load_on(station, alias, body.get("backend")))
            else:
                res = _run_capture(lambda: _load_action(alias, body.get("backend")))
            return self._json(200 if res["rc"] == 0 else 400, res)
        if path == "/api/backend":
            alias = (body.get("alias") or "").strip()
            backend = (body.get("backend") or "").strip()
            station = (body.get("station") or "").strip().upper()
            if not alias or not backend:
                return self._json(400, {"error": "alias and backend required"})
            if station:
                if station not in ("A", "B", "C"):
                    return self._json(400, {"error": f"bad station '{station}'"})
                res = _run_capture(lambda: cluster.cmd_load_on(station, alias, backend))
            else:
                res = _run_capture(lambda: cluster.cmd_load(alias, backend))
            return self._json(200 if res["rc"] == 0 else 400, res)
        if path == "/api/unload":
            station = (body.get("station") or "").strip().upper()
            if station:
                if station not in ("A", "B", "C"):
                    return self._json(400, {"error": f"bad station '{station}'"})
                res = _run_capture(lambda: cluster.cmd_unload_on(station))
            else:
                res = _run_capture(cluster.cmd_unload)
            return self._json(200 if res["rc"] == 0 else 400, res)
        if path == "/api/estimate":
            # 事前预估 (2026-09-15, P1-1): 提交加载前先算"能不能装下 / 该改哪个参数"。
            alias = (body.get("alias") or "").strip()
            station = (body.get("station") or "").strip().upper()
            if not alias:
                return self._json(400, {"error": "alias required"})
            if station and station not in ("A", "B", "C"):
                return self._json(400, {"error": f"bad station '{station}'"})
            if not station:
                try:
                    station = cluster.resolve_alias(alias)[0]
                except Exception:
                    station = None
                station = station or cluster.DEFAULT_STATION
            def _int(v):
                try:
                    return int(v) if v not in (None, "") else None
                except (TypeError, ValueError):
                    return None
            res = cluster.estimate_load(
                station, alias, _int(body.get("ctx")), _int(body.get("parallel")),
                (body.get("ctk") or "q8_0"), (body.get("ctv") or "q8_0"))
            return self._json(200 if res.get("ok") else 400, res)
        if path == "/api/models-link":
            # P1-2 模型全生命周期: 给"未纳管"模型补软链 (物理库有、聚合视图无 → 清单与加载都看不到)。
            # 只建软链, 不复制权重 —— 权重留在 ~/.lmstudio/models, /data/models/gguf 只是聚合视图。
            st = (body or {}).get("station")
            if st not in ("A", "B", "C"):
                return self._json(400, {"error": "station 必须是 A/B/C"})
            m = cluster._scan_models(st) or {}
            orph = m.get("orphans", [])
            logs = [cluster._link_model(st, x, dry=False) for x in orph]
            return self._json(200, {"ok": True, "station": st, "count": len(orph),
                                    "log": "\n".join(logs) if logs else "无孤儿, 无需补链"})
        if path == "/api/secrets-push":
            # 凭据管理: 从主控 secrets/stations/<st>/ 重下发三站 ~/.config/rpc/
            # (密钥轮换落地: 覆盖正本后在这里一键 push, 对齐审计 §16.3 ① 的闭环)。
            # 已在 do_POST 入口过了 token, 前端另有 confirm 二次确认。
            res = _run_capture(cluster._secrets_push)
            return self._json(200 if res["rc"] == 0 else 500, res)
        return self._json(404, {"error": "not found"})

    def log_message(self, fmt, *args):  # 静默访问日志, 保持控制台干净
        pass


PAGE_HTML = r"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>三机推理集群 · 框架管理</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--line:#e3e6ea;--fg:#1f2328;--mut:#6b7280;
      --ok:#16a34a;--warn:#d97706;--err:#dc2626;--accent:#2563eb;--radius:10px}
*{box-sizing:border-box}
.warnbar{margin:10px;padding:10px 12px;border:1px solid #f0c36d;background:#fffaf0;
         border-radius:8px;color:#8a5a00;font-size:13px;line-height:1.5}
body{font-family:'Segoe UI','Microsoft YaHei',system-ui,sans-serif;margin:0;background:var(--bg);color:var(--fg);font-size:14px}
header{background:var(--card);border-bottom:1px solid var(--line);padding:13px 22px;display:flex;
       align-items:center;gap:14px;flex-wrap:wrap;position:sticky;top:0;z-index:10}
header h1{font-size:16px;margin:0;font-weight:600}
.spacer{flex:1}
button{font-family:inherit;font-size:13px;padding:7px 14px;border:1px solid var(--line);background:#fff;
       border-radius:8px;cursor:pointer;transition:.15s}
button:hover:not(:disabled){background:#f0f2f5;border-color:#c9cfd6}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff}
button.primary:hover:not(:disabled){background:#1d4ed8}
button.danger{color:var(--err);border-color:#f3c7c7}
button:disabled{opacity:.45;cursor:not-allowed}
button.mini{padding:3px 10px;font-size:12px;border-radius:6px}
select{font-family:inherit;font-size:13px;padding:6px 8px;border:1px solid var(--line);border-radius:8px;background:#fff}
.wrap{padding:18px 22px 80px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden}
.card-head{padding:12px 16px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.card-head b{font-size:15px}
.card-body{padding:0;max-height:460px;overflow:auto}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block;flex:0 0 auto}
.ok{background:var(--ok)}.off{background:#c3c8ce}.err{background:var(--err)}.warn{background:var(--warn)}
.badge{font-size:11px;padding:2px 8px;border-radius:20px;background:#eef1f4;color:var(--mut);white-space:nowrap}
.badge.conf{background:#e7f5ec;color:#15803d}
.badge.noconf{background:#fdf1e3;color:#b45309}
.badge.ok{background:#e7f5ec;color:#15803d}
.badge.err{background:#fdecec;color:#b91c1c}
table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:8px 12px;font-size:13px;border-bottom:1px solid var(--line)}
th{background:#fafbfc;color:var(--mut);font-weight:600;font-size:12px;position:sticky;top:0}
tr.loaded{background:#f0f8f2}
td.acts{white-space:nowrap;text-align:right}
.mut{color:var(--mut);font-size:12px}
.mmeta{font-size:11px;color:#8a949e;margin-top:2px}
details{margin-top:16px;background:var(--card);border:1px solid var(--line);border-radius:var(--radius)}
summary{padding:12px 16px;cursor:pointer;font-weight:600;font-size:13px}
details>div{padding:0 16px 16px}
#log{position:fixed;left:0;right:0;bottom:0;max-height:40vh;overflow:auto;background:#0f172a;color:#c9e2ff;
     font-family:Consolas,monospace;font-size:12px;padding:14px 18px 18px;white-space:pre-wrap;display:none;
     border-top:1px solid #1e293b;z-index:20}
#log.show{display:block}
#logBar{position:fixed;right:14px;bottom:calc(40vh + 8px);z-index:21;display:none}
#logBar.show{display:block}
.login{background:#fffbeb;border:1px solid #fde68a;padding:12px 16px;margin:16px 22px 0;border-radius:var(--radius)}
.stmeta{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.metrics{display:flex;gap:6px;flex-wrap:wrap;padding:8px 16px;border-bottom:1px solid var(--line);background:#fbfcfe}
.badge.warnb{background:#fef2f2;color:#b91c1c}
</style></head><body>
<header>
  <h1>三机推理集群 · 模型与框架管理</h1>
  <span class="spacer"></span>
  <span class="mut">后端</span>
  <select id="backendSel">{{BACKEND_OPTIONS}}</select>
  <button class="danger" onclick="doUnloadAll()" id="bUnloadAll">三站全部卸载</button>
  <button onclick="doPush()" id="bPush">凭据重下发</button>
  <span class="badge" id="foot">连接中…</span>
</header>

<div class="login" id="loginBox">
  首次访问请输入服务 token: <input type="password" id="tokInput" placeholder="token" />
  <button class="primary" onclick="saveToken()">保存</button>
  <span class="mut">(存浏览器 localStorage)</span>
</div>

<div class="wrap">
  <div class="grid" id="stations"></div>
  <details>
    <summary>框架运行状态 (llama / unsloth / vLLM / litellm / opencode / claude)</summary>
    <div id="panels"></div>
  </details>
  <details>
    <summary>统一入口平面 ② ③ (凭据 / Provider / 出站)</summary>
    <div id="planes"></div>
  </details>
  <details>
    <summary>引擎版本矩阵 (RPC 引擎 / 单机引擎 / LM Studio / opencode / 内核)</summary>
    <div id="versions"></div>
  </details>
</div>

<button id="logBar" onclick="closeLog()">收起输出 ✕</button>
<div id="log"></div>

<script>
let token = localStorage.getItem('cluster_token') || '';
// 支持从 URL ?token= 自动登录: 启动日志会打印"免输链接", 点击即用, 无需手输。
// (手输入口仍保留, 作为换机/清缓存后的兜底)
const urlTok = new URLSearchParams(location.search).get('token');
if(urlTok){ token = urlTok; localStorage.setItem('cluster_token', token);
  history.replaceState(null, '', location.pathname); }
let busy = false;
const tokBox = document.getElementById('tokInput');
tokBox.value = token;
document.getElementById('loginBox').style.display = token ? 'none' : 'block';

function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

function saveToken(){ token = tokBox.value.trim(); localStorage.setItem('cluster_token', token);
  document.getElementById('loginBox').style.display='none'; refreshAll(); }

async function api(method, path, body){
  const r = await fetch(path, {method, headers:{'Content-Type':'application/json',
    'X-Auth-Token': token}, body: body?JSON.stringify(body):undefined});
  if(r.status===401){ document.getElementById('loginBox').style.display='block'; throw new Error('unauthorized'); }
  if(r.status===404) throw new Error('not found');
  if(r.status>=500) throw new Error('server '+r.status);
  return r.json();
}

function showLog(txt){ const d=document.getElementById('log'); d.textContent=txt;
  d.classList.add('show'); document.getElementById('logBar').classList.add('show'); }
function closeLog(){ document.getElementById('log').classList.remove('show');
  document.getElementById('logBar').classList.remove('show'); }

function engineDot(e){
  if(e==='READY') return '<span class="dot ok"></span>已就绪';
  if(e==='STOPPED') return '<span class="dot off"></span>空闲';
  return '<span class="dot err"></span>'+esc(e);
}

// 引擎实时指标行 (数据源: llama.cpp 原生 /metrics + /slots, 经内层端口)
function metricsLine(mt){
  if(!mt || !mt.port) return '<div class="metrics"><span class="mut">指标: 引擎未运行</span></div>';
  const m = mt.metrics || {};
  const f = k => (m[k]!==undefined ? Number(m[k]).toFixed(1) : '—');
  let s = '<div class="metrics">'
        + '<span class="badge">端口 '+mt.port+'</span>'
        + '<span class="badge">prefill '+f('prompt_tokens_seconds')+' t/s</span>'
        + '<span class="badge">decode '+f('predicted_tokens_seconds')+' t/s</span>'
        + '<span class="badge">槽位 '+(mt.slots_busy||0)+'/'+(mt.n_slots||0)+'</span>'
        + '<span class="badge">ctx '+(mt.ctx||0)+'</span>';
  if(m.requests_deferred > 0) s += '<span class="badge warnb">排队 '+m.requests_deferred+'</span>';
  if(Object.keys(m).length === 0) s += '<span class="badge noconf">/metrics 未启用</span>';
  return s + '</div>';
}

// 单站一张卡片: 站头(状态+已加载+卸载本站) + 指标行 + 该站模型清单(每行可加载)
// P1-6 模型元数据行: 原生 ctx / 架构 / 量化(含来源) / 站上 conf 的加载参数。
// 刻意把"原生 ctx"与"加载 ctx"并列显示 —— 它们回答不同问题 (模型能吃到多少 vs 本站
// 实际给了多少), 合并成一个数字会掩盖 conf 把 ctx 调小这类事实。
function metaLine(m){
  const bits = ['原生 ctx ' + (m.ctx_native==null ? '?' : m.ctx_native)];
  if(m.arch) bits.push(m.arch);
  if(m.quant) bits.push(m.quant + (m.quant_src==='ledger' ? '(台账)' : '(文件名)'));
  const p = m.params || {};
  if(p.ctx) bits.push('加载 ctx ' + p.ctx);
  if(p.backend) bits.push(p.backend);
  if(p.port) bits.push(':' + p.port);
  if(p.n_cpu_moe) bits.push('n_cpu_moe ' + p.n_cpu_moe);
  if(p.rpc_target) bits.push('rpc ' + p.rpc_target);
  return '<div class="mut mmeta">'+esc(bits.join(' · '))+'</div>';
}
function stationCard(st, s, mt){
  const loc = {A:'NEX', B:'GTR-Pro', C:'seaviv'}[st] || '';
  let h = '<div class="card"><div class="card-head">'
        + '<b>'+st+' 站</b><span class="mut">'+loc+'</span>'
        + '<span class="stmeta">'+engineDot(s.engine)+'</span>'
        + '<span class="spacer"></span>'
        + '<span class="mut">已加载: '+esc(s.loaded||'(无)')+'</span>'
        + '<button class="mini danger" onclick="doUnload(\''+st+'\')">卸载本站</button>'
        + '</div>' + metricsLine(mt) + '<div class="card-body">';
  if(!s.reachable){ h += '<div style="padding:16px" class="mut">站不可达</div>'; }
  else if(!s.models || !s.models.length){ h += '<div style="padding:16px" class="mut">模型库为空</div>'; }
  else {
    h += '<table><tr><th>模型</th><th>大小</th><th>状态</th><th style="text-align:right">操作</th></tr>';
    for(const m of s.models){
      const badge = m.has_conf ? '<span class="badge conf">conf ✓</span>'
                               : '<span class="badge noconf">加载时自动生成 conf</span>';
      const stt = m.loaded ? ' <span class="badge">已加载</span>' : '';
      h += '<tr class="'+(m.loaded?'loaded':'')+'">'
         + '<td><div>'+esc(m.display)+'</div>'
         + '<div class="mut">'+esc(m.alias)+' · '+esc(m.repo)+'</div>'
         + metaLine(m) + '</td>'
         + '<td class="mut">'+m.size_gb+'G</td>'
         + '<td>'+badge+stt+'</td>'
         + '<td class="acts">'
         + '<button class="mini" onclick="doEstimate(\''+st+'\',\''+esc(m.alias)+'\')">预估</button> '
         + '<button class="mini" onclick="doLoad(\''+st+'\',\''+esc(m.alias)+'\')">加载</button>'
         + (m.loaded ? ' <button class="mini danger" onclick="doUnload(\''+st+'\')">卸载</button>' : '')
         + '</td></tr>';
    }
    h += '</table>';
    // 未纳管 / 断链 (2026-09-15 P1-2): 物理库里有权重、但聚合视图(/data/models/gguf)里
    // 没有软链的模型 —— "文件在, 清单看不到, infer-load 也找不到"。这正是 MiniMax-M2.7
    // 当初"存在却加载不了"的形态。这里显式暴露, 并给一键补链。
    const un = s.unmanaged||[], br = s.broken||[];
    if(un.length || br.length){
      h += '<div class="warnbar">';
      if(un.length)
        h += '⚠ <b>'+un.length+'</b> 个模型未纳管（有权重、无软链 → 清单与加载都看不到）'
           + '<div class="mut" style="margin:3px 0">'+un.map(esc).join(' · ')+'</div>'
           + '<button class="mini" onclick="doModelsLink(\''+st+'\')">一键补链</button>';
      if(br.length)
        h += (un.length?'<div style="margin-top:6px"></div>':'')
           + '⚠ <b>'+br.length+'</b> 个软链已断（目标不存在，建议清理）'
           + '<div class="mut" style="margin:3px 0">'+br.map(esc).join(' · ')+'</div>';
      h += '</div>';
    }
  }
  return h + '</div></div>';
}

// 轮询一律「完成后自调度」+ in-flight 去重 (沿用 CHECKLIST F20 修复, 防并发堆积)
let modelsBusy=false, statusBusy=false, planesBusy=false;

async function loadModels(){
  if(modelsBusy) return; modelsBusy=true;
  try{
    // 模型清单 + 引擎指标并行拉取 (指标来自 llama.cpp 原生 /metrics 与 /slots)
    const [d, mt] = await Promise.all([api('GET','/api/models'), api('GET','/api/metrics')]);
    let h='';
    for(const st of ['A','B','C'])
      h += stationCard(st, d.stations[st]||{}, ((mt.stations||{})[st])||{});
    document.getElementById('stations').innerHTML = h;
  }catch(e){
    if(e.message!=='unauthorized')
      document.getElementById('stations').innerHTML='<div class="mut">模型清单拉取失败: '+esc(e.message)+'</div>';
  }
  finally{ modelsBusy=false; setTimeout(loadModels, 20000); }
}

async function loadStatus(){
  if(statusBusy) return; statusBusy=true;
  try{
    const d = await api('GET','/api/status');
    const names=['llama','unsloth','vllm','litellm','opencode','claude'];
    let h='<table><tr><th>站</th>'+names.map(n=>'<th>'+n+'</th>').join('')+'</tr>';
    for(const st of ['A','B','C']){
      const s=d.stations[st]||{};
      h += '<tr><td><b>'+st+'</b>'+(s.reachable?'':' <span class="mut">不可达</span>')+'</td>';
      for(const n of names){
        const fr=(s.frames||{})[n]||{};
        const t=fr.status||'Unknown';
        h += '<td><span class="dot '+(t==='RUNNING'?'ok':(t==='STOPPED'?'off':'err'))+'"></span> '+t+'</td>';
      }
      h += '</tr>';
    }
    document.getElementById('panels').innerHTML = h+'</table>';
    document.getElementById('foot').textContent = '更新于 '+d.time;
  }catch(e){ if(e.message!=='unauthorized') document.getElementById('foot').textContent='状态拉取失败'; }
  finally{ statusBusy=false; setTimeout(loadStatus, 8000); }
}

async function loadPlanes(){
  if(planesBusy) return; planesBusy=true;
  try{
    const d = await api('GET','/api/planes');
    let h='<table><tr><th>站</th><th>凭据 (~/.config/rpc)</th><th>opencode 默认模型</th>'
         +'<th>claude 凭据</th><th>出站 OpenRouter</th></tr>';
    for(const st of ['A','B','C']){
      const s=d.secrets[st]||{}, p=d.providers[st]||{}, e=d.egress[st]||{};
      const oc=(p.opencode&&(p.opencode.model||p.opencode.error))||'?';
      const cl=(p.claude&&(p.claude.token_form||p.claude.error))||'?';
      const eg=(e.http==='200')?('OK '+(e.time||'')+'s'):('FAIL '+e.http);
      h+='<tr><td><b>'+st+'</b></td>'
       + '<td><span class="dot '+(s.state==='OK'?'ok':'err')+'"></span> '+esc(s.state)
       + ' <span class="mut">'+esc(s.note||'')+'</span></td>'
       + '<td class="mut">'+esc(oc)+'</td>'
       + '<td class="mut">'+esc(cl)+((p.claude&&p.claude.helper)?' +apiKeyHelper':'')+'</td>'
       + '<td class="mut">'+esc(eg)+'</td></tr>';
    }
    document.getElementById('planes').innerHTML=h+'</table>';
  }catch(e){}
  finally{ planesBusy=false; setTimeout(loadPlanes, 20000); }
}

function setBtns(dis){
  for(const id of ['bUnloadAll','bPush']){ const el=document.getElementById(id); if(el) el.disabled=dis; }
}

// 事前预估 (P1-1): 提交前算"能不能装下 / 该改哪个参数"
async function doEstimate(st, alias){
  if(busy) return;
  busy=true; setBtns(true); showLog('['+st+'] 预估 '+alias+' 中… (读 GGUF 元数据 + 站上内存)');
  try{
    const r = await api('POST','/api/estimate',{station:st, alias:alias});
    if(!r.ok){ showLog('预估失败: '+((r.reasons||[]).join('; ')||'未知原因')); return; }
    const m = r.model||{}, mem = r.mem||{};
    let t = '=== 事前预估: '+alias+' @ '+r.station+' 站 ===\n';
    t += '  模型      : '+(m.name||'?')+' ['+(m.arch||'?')+'] 层='+m.block_count
       + ' kv_heads='+m.head_count_kv+' head_dim='+r.head_dim+' 原生ctx='+m.context_length+'\n';
    t += '  加载参数  : ctx='+r.ctx+' parallel='+r.n_parallel+' KV=('+r.ctk+','+r.ctv+')\n';
    t += '  权重      : '+r.weights_gib+' GiB\n';
    t += '  KV cache  : '+r.kv_gib+' GiB   (全注意力层 '+r.n_attn_layer+' 层)\n';
    if(r.ssm_gib) t += '  SSM state : '+r.ssm_gib+' GiB  (hybrid 架构, 近似, 与 ctx 无关)\n';
    t += '  运行开销  : '+r.overhead_gib+' GiB\n';
    t += '  ────────────────────────\n';
    t += '  合计需求  : '+r.need_gib+' GiB\n';
    if(mem.total) t += '  站上内存  : total '+mem.total+' / used '+mem.used+' / avail '+mem.avail+' GiB\n';
    t += '  结论      : 【'+r.verdict+'】\n';
    for(const x of (r.reasons||[])) t += '    ✗ '+x+'\n';
    for(const x of (r.advice||[]))  t += '    → '+x+'\n';
    showLog(t);
  }catch(e){ showLog('预估失败: '+e.message); }
  finally{ busy=false; setBtns(false); }
}

// 预估结果 → 可读文本 (与 CLI `cluster.py estimate` 同口径)
function fmtEstimate(r){
  const m=r.model||{}, mem=r.mem||{};
  let t = '=== 事前预估: '+(r.alias||'')+' @ '+r.station+' 站 ===\n';
  let kvh = m.head_count_kv;
  if(Array.isArray(kvh)) kvh = '逐层(全注意力 '+r.n_attn_layer+'/'+m.block_count+' 层)';
  t += '  模型      : '+m.name+' ['+m.arch+'] 层='+m.block_count+' kv_heads='+kvh
     + ' head_dim='+r.head_dim+' 原生ctx='+m.context_length+'\n';
  t += '  加载参数  : ctx='+r.ctx+' parallel='+r.n_parallel+' KV=('+r.ctk+','+r.ctv+')\n';
  t += '  权重      : '+r.weights_gib+' GiB\n';
  t += '  KV cache  : '+r.kv_gib+' GiB  (全注意力层 '+r.n_attn_layer+' 层)\n';
  if(r.ssm_gib) t += '  SSM state : '+r.ssm_gib+' GiB  (hybrid 架构, 近似, 与 ctx 无关)\n';
  t += '  运行开销  : '+r.overhead_gib+' GiB\n';
  t += '  ─────────────────────\n';
  t += '  合计需求  : '+r.need_gib+' GiB\n';
  if(mem.total) t += '  站上内存  : total '+mem.total+' / used '+mem.used+' / avail '+mem.avail
                   + (mem.existing_rss ? ' / 已有引擎RSS '+mem.existing_rss : '') + ' GiB\n';
  t += '  门禁判据  : (对齐 load-gate) avail_eff '
     + (r.avail_effective !== undefined ? r.avail_effective : '?') + ' ≥ need+'+r.pad_gib+'\n';
  t += '  结论      : 【'+r.verdict+'】\n';
  (r.notes||[]).forEach(function(x){ t += '    · '+x+'\n'; });
  (r.reasons||[]).forEach(function(x){ t += '    ✗ '+x+'\n'; });
  (r.advice||[]).forEach(function(x){ t += '    → '+x+'\n'; });
  return t;
}

async function doEstimate(st, alias){
  if(busy) return;
  busy=true; setBtns(true); showLog('['+st+'] 预估 '+alias+' 中…');
  try{
    const r = await api('POST','/api/estimate',{station:st, alias:alias});
    showLog(r.ok ? fmtEstimate(r) : ('预估失败: '+((r.reasons||[]).join('; ')||'未知')));
  }catch(e){ showLog('预估失败: '+e.message); }
  finally{ busy=false; setBtns(false); }
}

async function doLoad(st, alias){
  if(busy) return;
  busy=true; setBtns(true);
  const bd = document.getElementById('backendSel').value;
  // 加载前自动预估: NO_FIT 时把原因与建议放进确认框 (预估失败不阻断加载)
  let warn = '';
  try{
    const est = await api('POST','/api/estimate',{station:st, alias:alias});
    if(est && est.ok){
      const avail = (est.avail_effective !== undefined ? est.avail_effective
                    : (est.mem && est.mem.avail));
      warn = '预估: 需求 '+est.need_gib+'G / 可用 '+(avail!==undefined?avail:'?')+'G → 【'+est.verdict+'】\n';
      if((est.notes||[]).length) warn += est.notes.join('\n')+'\n';
      if(est.verdict === 'NO_FIT'){
        warn += '原因: '+((est.reasons||[]).join('; ')||'—')+'\n';
        warn += '建议: '+((est.advice||[]).join('; ')||'—')+'\n';
      }
    }
  }catch(e){ /* 预估不可用则跳过 */ }
  if(!confirm('在 '+st+' 站加载 '+alias+' ?\n\n'+warn+'\n会先卸载该站当前引擎; 大模型可能需 1-3 分钟。')){
    busy=false; setBtns(false); showLog('已取消'); return;
  }
  showLog('['+st+'] 加载 '+alias+' 中… (大模型请耐心等待, 完成后此处显示日志)');
  try{
    const res = await api('POST','/api/load',{station:st, alias:alias, backend:bd||undefined});
    showLog((res.log||'').trim()+'\n[exit '+res.rc+']');
  }catch(e){ showLog('失败: '+e.message); }
  finally{ busy=false; setBtns(false); setTimeout(loadModels,600); setTimeout(loadStatus,600); }
}

async function doUnload(st){
  if(busy) return;
  if(!confirm('卸载 '+st+' 站引擎?')) return;
  busy=true; setBtns(true); showLog('['+st+'] 卸载中…');
  try{
    const res = await api('POST','/api/unload',{station:st});
    showLog((res.log||'').trim()+'\n[exit '+res.rc+']');
  }catch(e){ showLog('失败: '+e.message); }
  finally{ busy=false; setBtns(false); setTimeout(loadModels,600); setTimeout(loadStatus,600); }
}

async function doUnloadAll(){
  if(busy) return;
  if(!confirm('三站全部卸载?')) return;
  busy=true; setBtns(true); showLog('三站卸载中…');
  try{
    const res = await api('POST','/api/unload',{});
    showLog((res.log||'').trim()+'\n[exit '+res.rc+']');
  }catch(e){ showLog('失败: '+e.message); }
  finally{ busy=false; setBtns(false); setTimeout(loadModels,600); setTimeout(loadStatus,600); }
}

async function doPush(){
  if(busy) return;
  if(!confirm('用主控 secrets/stations/ 正本覆盖三站离线凭据?')) return;
  busy=true; setBtns(true); showLog('凭据重下发中…');
  try{
    const res = await api('POST','/api/secrets-push',{});
    showLog((res.log||'').trim()+'\n[exit '+res.rc+']\n凭据已重下发, 站内 agent 需重启生效');
  }catch(e){ showLog('失败: '+e.message); }
  finally{ busy=false; setBtns(false); }
}

async function doModelsLink(st){
  if(busy) return;
  if(!confirm(st+' 站: 给所有未纳管模型补软链?\n（在 /data/models/gguf 下建指向 ~/.lmstudio/models 的软链，不复制权重）')) return;
  busy=true; setBtns(true); showLog(st+' 站补链中…');
  try{
    const res = await api('POST','/api/models-link',{station:st});
    showLog((res.log||'').trim()+'\n[exit '+(res.ok?0:1)+']');
  }catch(e){ showLog('失败: '+e.message); }
  finally{ busy=false; setBtns(false); setTimeout(loadModels,800); }
}

// P1-3 引擎版本矩阵: 逐维度比对三站, 不一致打红并标"漂移"
let verBusy=false;
async function loadVersions(){
  if(verBusy) return; verBusy=true;
  try{
    const d = await api('GET','/api/versions');
    const S = d.stations||{};
    const dims = [
      ['RPC 引擎 (/opt/llama.cpp)', s=>(s.rpc||{}).commit,
        s=>((s.rpc||{}).version||'')+(s.rpc&&s.rpc.built?' · '+s.rpc.built:'')],
      ['RPC 完整性 (md5sum -c)', s=>s.md5, null],
      ['单机引擎 (~/llama.cpp)', s=>((s.single||{}).commit||'').slice(0,7),
        s=>(s.single||{}).version||''],
      ['LM Studio', s=>s.lmstudio, null],
      ['opencode', s=>s.opencode, null],
      ['内核', s=>s.kernel, null],
    ];
    let h='<table style="margin:8px 12px"><tr><th>维度</th><th>A</th><th>B</th><th>C</th><th>一致</th></tr>';
    for(const [name,keyf,extf] of dims){
      const vals = ['A','B','C'].map(st=>keyf(S[st]||{}));
      const same = vals.every(v=>v===vals[0]);
      h += '<tr><td>'+esc(name)+'</td>';
      for(const st of ['A','B','C']){
        const s=S[st]||{};
        const main = esc(String(keyf(s)===undefined?'?':keyf(s)));
        h += '<td'+(same?'':' style="color:#dc2626;font-weight:600"')+'>'+main
           + (extf && extf(s) ? '<div class="mut">'+esc(String(extf(s)))+'</div>' : '')
           + '</td>';
      }
      h += '<td>'+(same?'<span class="badge ok">一致</span>'
                        :'<span class="badge err">漂移</span>')+'</td></tr>';
    }
    h += '</table>';
    document.getElementById('versions').innerHTML = h;
  }catch(e){
    if(e.message!=='unauthorized')
      document.getElementById('versions').innerHTML =
        '<div class="mut" style="padding:12px">加载失败: '+esc(e.message)+'</div>';
  }finally{ verBusy=false; }
}

function refreshAll(){ loadModels(); loadStatus(); loadPlanes(); loadVersions(); }
refreshAll();
</script></body></html>"""


def _build_page():
    # ALIAS_OPTIONS 已废弃 (2026-09-15): 模型列表由前端 /api/models 动态渲染。
    backend_opts = "".join(f'<option value="{b}">{b}</option>' for b in sorted(cluster.BACKENDS))
    return PAGE_HTML.replace("{{BACKEND_OPTIONS}}", backend_opts)


def serve(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    host, port, token = WEB_HOST, WEB_PORT, None
    i = 0
    while i < len(argv):
        if argv[i] == "--host" and i + 1 < len(argv):
            host = argv[i + 1]; i += 2; continue
        if argv[i] == "--port" and i + 1 < len(argv):
            port = int(argv[i + 1]); i += 2; continue
        if argv[i] == "--token" and i + 1 < len(argv):
            token = argv[i + 1]; i += 2; continue
        i += 1
    token = token or secrets.token_urlsafe(9)
    Handler._token = token
    Handler._page = _build_page()

    # 双栈监听 (2026-09-15 修): Windows 下 `localhost` 会同时解析出 `::1`(IPv6) 与
    # `127.0.0.1`, 且 **::1 排在前面**; 而默认 ThreadingHTTPServer 只绑 IPv4 →
    # 浏览器访问 http://localhost:port 先试 ::1 被拒, 部分浏览器不做 fallback 直接报错
    # (curl 有 happy-eyeballs fallback, 所以命令行测不出来)。故 IPv4 / IPv6 各起一个。
    if host in ("127.0.0.1", "localhost"):
        bindings = [(socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")]
    elif host in ("0.0.0.0", ""):
        bindings = [(socket.AF_INET, "0.0.0.0"), (socket.AF_INET6, "::")]
    else:
        bindings = [(socket.AF_INET, host)]

    servers, bound = [], []
    for fam, addr in bindings:
        try:
            cls = type("_Srv", (ThreadingHTTPServer,), {"address_family": fam})
            servers.append(cls((addr, port), Handler))
            bound.append(addr)
        except OSError as e:
            if fam == socket.AF_INET:
                print(f"[cluster-web] 绑定失败 {addr}:{port}: {e}")
                return 1
            print(f"[cluster-web] (提示) IPv6 未绑定 {addr}:{port}: {e}")

    print("[cluster-web] 三机推理框架管理 UI 已启动 (按需服务, Ctrl-C 退出)")
    print(f"[cluster-web]   免输链接(推荐): http://127.0.0.1:{port}/?token={token}")
    print(f"[cluster-web]   或手输 token : {token}")
    print(f"[cluster-web]   监听: {', '.join(bound)}  (port {port}; localhost 与 127.0.0.1 均可用)")
    if host in ("0.0.0.0", ""):
        print("[cluster-web]   已监听局域网, 请妥善保管 token")
    try:
        for s in servers[1:]:
            threading.Thread(target=s.serve_forever, daemon=True).start()
        servers[0].serve_forever()
    except KeyboardInterrupt:
        print("\n[cluster-web] 退出, 端口已释放。")
    finally:
        for s in servers:
            s.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(serve())