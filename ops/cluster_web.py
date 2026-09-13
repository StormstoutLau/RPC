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
import sys
import json
import time
import secrets
import contextlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cluster  # 复用 ssh_run / probe_frames / cmd_load / cmd_unload / BACKENDS / ROUTE 等

WEB_HOST = "127.0.0.1"
WEB_PORT = 8095

# 前端下拉可选模型 (ROUTE 键优先, 再补 RPC_MODELS, 去重保序; 也允许自由输入)
def _model_suggestions():
    seen, out = set(), []
    for name in list(cluster.ROUTE) + sorted(cluster.RPC_MODELS):
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def _collect_status():
    """聚合三站: 框架探测 + 引擎 :8080 health + 加载实例。返回可 JSON 化 dict。"""
    frames = {st: cluster.probe_frames(st) for st in ("A", "B", "C")}
    base = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "stations": {}}
    for st in ("A", "B", "C"):
        f = frames[st]
        fr = {}
        for name in ("llama", "unsloth", "vllm", "litellm", "opencode", "claude"):
            status, detail = f["frames"].get(name, ("Unknown", ""))
            fr[name] = {"status": status, "detail": detail}
        # 引擎 :8080 health
        engine, loaded = "?", "?"
        if f["reachable"]:
            # 复用 cluster.probe_station 的 loaded 判定 (含 /health + systemd + infer-list)
            ps = cluster.probe_station(st)
            engine = ps.get("llama", "?")
            loaded = ps.get("loaded", "?")
        base["stations"][st] = {
            "reachable": f["reachable"],
            "frames": fr,
            "engine": engine,
            "loaded": loaded,
        }
    return base


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
        if self.path in ("/", "/index.html"):
            return self._text(200, self._page)
        if self.path == "/api/status":
            if not self._auth_ok():
                return self._json(401, {"error": "unauthorized"})
            return self._json(200, _collect_status())
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self._auth_ok():
            return self._json(401, {"error": "unauthorized"})
        body = self._body_json()
        if self.path == "/api/load":
            alias = (body.get("alias") or "").strip()
            if not alias:
                return self._json(400, {"error": "alias required"})
            res = _run_capture(lambda: _load_action(alias, body.get("backend")))
            return self._json(200 if res["rc"] == 0 else 400, res)
        if self.path == "/api/backend":
            alias = (body.get("alias") or "").strip()
            backend = (body.get("backend") or "").strip()
            if not alias or not backend:
                return self._json(400, {"error": "alias and backend required"})
            res = _run_capture(lambda: cluster.cmd_load(alias, backend))
            return self._json(200 if res["rc"] == 0 else 400, res)
        if self.path == "/api/unload":
            res = _run_capture(cluster.cmd_unload)
            return self._json(200 if res["rc"] == 0 else 400, res)
        return self._json(404, {"error": "not found"})

    def log_message(self, fmt, *args):  # 静默访问日志, 保持控制台干净
        pass


PAGE_HTML = r"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>三机推理集群 · 框架管理</title>
<style>
body{font-family:Consolas,'Microsoft YaHei',monospace;margin:2em;background:#fafafa;color:#222}
h1{font-size:1.3em;margin-bottom:0.2em} .meta{color:#666;font-size:0.85em}
table{border-collapse:collapse;margin:0.8em 0;width:100%}
td,th{border:1px solid #ccc;padding:5px 10px;font-size:0.9em;text-align:left}
th{background:#eee} .dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}
.RUNNING{background:#2e7d32}.STOPPED{background:#9e9e9e}.Unknown{background:#c62828}
.ops{background:#fff;border:1px solid #ddd;padding:12px;margin:1em 0;border-radius:6px}
.ops input,.ops select{padding:5px;font-size:0.9em;margin-right:8px}
button{padding:6px 14px;font-size:0.9em;margin-right:8px;cursor:pointer}
button:disabled{opacity:.5;cursor:not-allowed}
#log{background:#111;color:#8dbfff;border-radius:6px;padding:10px;font-size:0.85em;
 white-space:pre-wrap;max-height:260px;overflow:auto;display:none}
input[type=text]{width:120px}
.login{background:#fff8e1;border:1px solid #e6c44a;padding:10px;margin:1em 0;border-radius:6px}
.mt{color:#888;font-size:0.8em}
</style></head><body>
<h1>三机推理集群 · 傻瓜式框架管理</h1>
<p class="meta">主控 `cluster.py web` 按需服务 · 状态自动刷新 · token 存本地</p>

<div class="login" id="loginBox">
  首次访问请输入服务 token: <input type="password" id="tokInput" placeholder="token" />
  <button onclick="saveToken()">保存</button>
  <span class="mt">(存浏览器 localStorage; 刷新需已保存)</span>
</div>

<div class="ops">
  <b>操作</b><br/>
  模型 <input type="text" id="aliasInput" list="aliasList" placeholder="如 gpt-oss" />
  <datalist id="aliasList">{{ALIAS_OPTIONS}}</datalist>
  后端 <select id="backendSel">{{BACKEND_OPTIONS}}</select>
  <button onclick="doOp('load')"    id="bLoad">加载</button>
  <button onclick="doOp('backend')" id="bBackend">切换后端</button>
  <button onclick="doOp('unload')"  id="bUnload">三站卸载</button>
  <span id="spinner"></span>
  <div id="log"></div>
</div>

<div id="panels"></div>
<p class="mt" id="foot">刷新状态中…</p>

<script>
let token = localStorage.getItem('cluster_token') || '';
let busy = false;
const tokBox = document.getElementById('tokInput');
tokBox.value = token;
document.getElementById('loginBox').style.display = token ? 'none' : 'block';

function saveToken(){ token = tokBox.value.trim(); localStorage.setItem('cluster_token', token);
  document.getElementById('loginBox').style.display='none'; loadStatus(); }

async function api(method, path, body){
  const r = await fetch(path, {method, headers:{'Content-Type':'application/json',
    'X-Auth-Token': token}, body: body?JSON.stringify(body):undefined});
  if(r.status===401){ document.getElementById('loginBox').style.display='block'; throw new Error('unauthorized'); }
  if(r.status===404) throw new Error('not found');
  if(r.status>=500) throw new Error('server '+r.status);
  return r.json();
}

function frameRow(name, fr){
  const s = fr.status || 'Unknown';
  const col = s==='RUNNING'?'#2e7d32':(s==='STOPPED'?'#9e9e9e':'#c62828');
  return '<tr><td>'+name+'</td><td><span class="dot" style="background:'+col+'"></span>'+
         s+'</td><td class="mt">'+(fr.detail||'')+'</td></tr>';
}

async function loadStatus(){
  try{
    const d = await api('GET','/api/status');
    const names=['llama','unsloth','vllm','litellm','opencode','claude'];
    let html='';
    for(const st of ['A','B','C']){
      const s=d.stations[st];
      html+='<h3>'+st+' 站 '+ (s.reachable? '' : '(不可达)') +
            ' · 引擎:'+s.engine+' · 加载:'+s.loaded+'</h3>';
      html+='<table><tr><th>框架</th><th>状态</th><th>详情</th></tr>';
      for(const n of names) html+=frameRow(n,s.frames[n]);
      html+='</table>';
    }
    document.getElementById('panels').innerHTML=html;
    document.getElementById('foot').textContent='刷新于 '+d.time;
  }catch(e){ if(e.message!=='unauthorized') document.getElementById('foot').textContent='状态拉取失败: '+e.message; }
}

async function doOp(op){
  if(busy) return; busy=true;
  const d=document.getElementById('log'); d.style.display='block'; d.textContent='操作中…';
  for(const id of ['bLoad','bBackend','bUnload']) document.getElementById(id).disabled=true;
  const sp=document.getElementById('spinner'); sp.textContent='…';
  try{
    let res;
    if(op==='load')      res=await api('POST','/api/load',{alias:document.getElementById('aliasInput').value});
    else if(op==='backend') res=await api('POST','/api/backend',
        {alias:document.getElementById('aliasInput').value,
         backend:document.getElementById('backendSel').value});
    else                res=await api('POST','/api/unload');
    d.textContent=(res.log||'').trim()+'\n[exit '+res.rc+']';
  }catch(e){ d.textContent='失败: '+e.message; }
  finally{
    busy=false; sp.textContent='';
    for(const id of ['bLoad','bBackend','bUnload']) document.getElementById(id).disabled=false;
    setTimeout(loadStatus,600);
  }
}

loadStatus();
setInterval(loadStatus, 5000);
</script></body></html>"""


def _build_page():
    alias_opts = "".join(f'<option value="{m}">' for m in _model_suggestions())
    backend_opts = "".join(f'<option value="{b}">{b}</option>' for b in sorted(cluster.BACKENDS))
    return PAGE_HTML.replace("{{ALIAS_OPTIONS}}", alias_opts).replace("{{BACKEND_OPTIONS}}", backend_opts)


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
    try:
        srv = ThreadingHTTPServer((host, port), Handler)
    except OSError as e:
        print(f"[cluster-web] 绑定失败 {host}:{port}: {e}")
        return 1
    print(f"[cluster-web] 三机推理框架管理 UI 已启动 (按需服务, Ctrl-C 退出)")
    print(f"[cluster-web]   地址: http://{host}:{port}/")
    print(f"[cluster-web]   token: {token}")
    if host in ("0.0.0.0", ""):
        print("[cluster-web]   已监听局域网, 请妥善保管 token")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[cluster-web] 退出, 端口已释放。")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(serve())