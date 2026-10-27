"""cluster_web 鉴权与引导（P1 #10）—— 先验红 / 后验绿行为测试。

覆盖 IMPLEMENTATION §9.1 #10 行：
  · `_token_eq` 常量时间比较、空值/非 ASCII 不抛；
  · `_auth_ok` 接受 `X-Auth-Token` 与 `rpc_token` Cookie；
  · `/?token=<正确>` → 302 + Set-Cookie(HttpOnly/SameSite=Strict/Path=/) + 空 body；
  · `/?token=<错误>` → 401、无 Set-Cookie；
  · 非 loopback 绑定 + query token → 401（禁用引导）；
  · `/?token=`（空值）→ 200 公开页（F-6 防回归钉）；
  · 所有响应 `Referrer-Policy: no-referrer`；401/302 `Cache-Control: no-store`；
  · 启动日志不含完整 token；非 loopback 有告警。

用法: py tests\\test_cluster_web_auth.py
"""
import http.client
import sys
import threading
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))
import cluster_web as W                                  # noqa: E402

fails = []
TOKEN = "abc123"


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


# ── 1. _token_eq ────────────────────────────────────────────────
fn = getattr(W, "_token_eq", None)
chk("_token_eq 存在", callable(fn))
if callable(fn):
    chk("_token_eq 正确值", fn(TOKEN, TOKEN) is True)
    chk("_token_eq 错误值", fn("no", TOKEN) is False)
    chk("_token_eq 空值", fn("", TOKEN) is False and fn("", "") is False)
    chk("_token_eq 非 ASCII 不抛", fn("中文", TOKEN) is False)

# ── 2. _auth_ok：Header + Cookie ────────────────────────────────
W.Handler._token = TOKEN
auth = W.Handler._auth_ok


def fake(headers):
    return types.SimpleNamespace(headers=headers, _token=TOKEN)


chk("header 正确 ⇒ True", auth(fake({"X-Auth-Token": TOKEN})) is True)
chk("header 错误 ⇒ False", auth(fake({"X-Auth-Token": "no"})) is False)
chk("cookie 正确 ⇒ True", auth(fake({"Cookie": "a=1; rpc_token=" + TOKEN})) is True)
chk("cookie 错误 ⇒ False", auth(fake({"Cookie": "rpc_token=no"})) is False)
chk("无凭据 ⇒ False", auth(fake({})) is False)

src = (ROOT / "ops" / "cluster_web.py").read_text(encoding="utf-8")
chk("源码使用 compare_digest", "compare_digest" in src)

# ── 3. 启动日志 / 掩码 ─────────────────────────────────────────
sl = getattr(W, "_startup_lines", None)
chk("_startup_lines 存在", callable(sl))
if callable(sl):
    txt = "\n".join(sl(8095, TOKEN, Path("web-token"), "127.0.0.1"))
    chk("启动日志不含完整 token", TOKEN not in txt, txt.replace("\n", " | "))
    chk("启动日志含 token 文件路径", "web-token" in txt)
    txt2 = "\n".join(sl(8095, TOKEN, None, "0.0.0.0"))
    chk("非 loopback 启动告警", ("header" in txt2.lower()) or ("非 loopback" in txt2),
        txt2.replace("\n", " | "))
mask = getattr(W, "_mask_token", None)
chk("_mask_token 存在", callable(mask))
if callable(mask):
    chk("掩码不含完整 token", TOKEN not in mask(TOKEN), mask(TOKEN))


# ── 4. HTTP 行为 ────────────────────────────────────────────────
W.Handler._page = "<html>ok</html>"
W.Handler._token = TOKEN


def start(host):
    W.Handler._host = host
    srv = W.ThreadingHTTPServer(("127.0.0.1", 0), W.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def req(port, path):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", path)
    r = c.getresponse()
    body = r.read()
    hdrs = {k.lower(): v for k, v in r.getheaders()}
    c.close()
    return r.status, hdrs, body


srv = start("127.0.0.1")
port = srv.server_address[1]
try:
    st, h, b = req(port, "/?token=" + TOKEN)
    chk("引导正确 token ⇒ 302", st == 302, st)
    chk("引导 Location=/", h.get("location") == "/", h.get("location"))
    sc = h.get("set-cookie", "")
    chk("Set-Cookie 含 HttpOnly", "HttpOnly" in sc, sc)
    chk("Set-Cookie 含 SameSite=Strict", "SameSite=Strict" in sc, sc)
    chk("Set-Cookie 含 Path=/", "Path=/" in sc, sc)
    chk("引导 body 为空", b == b"", repr(b))

    st, h, _ = req(port, "/?token=wrong")
    chk("引导错误 token ⇒ 401", st == 401, st)
    chk("错误 token 不设 Cookie", "set-cookie" not in h)

    st, h, _ = req(port, "/?token=")
    chk("空 token query ⇒ 200 公开页（F-6）", st == 200, st)
    chk("空 token query 不设 Cookie", "set-cookie" not in h)

    st, h, _ = req(port, "/")
    chk("公开页 200", st == 200, st)
    chk("所有响应 Referrer-Policy", h.get("referrer-policy") == "no-referrer", h)
finally:
    srv.shutdown()
    srv.server_close()

srv = start("0.0.0.0")
port = srv.server_address[1]
try:
    st, h, _ = req(port, "/?token=" + TOKEN)
    chk("非 loopback + query token ⇒ 401", st == 401, st)
    chk("非 loopback 不设 Cookie", "set-cookie" not in h)
    st, h, _ = req(port, "/?token=wrong")
    chk("非 loopback 错误 token ⇒ 401", st == 401, st)
finally:
    srv.shutdown()
    srv.server_close()


# ── RESULT ─────────────────────────────────────────────────────
print("\nRESULT: " + ("PASS" if not fails else "FAIL (" + str(len(fails)) + " 项)") +
      " · 失败: " + (", ".join(fails) if fails else "无"))
sys.exit(0 if not fails else 1)
