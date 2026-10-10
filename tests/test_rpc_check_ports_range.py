"""`O-158 甲`：`unmanaged` 的 **owner/段位形态**（"端口号不是真值, owner + 段位才是"）—— 离线守五组契约（2026-10-10）。

为什么要有它：`stations` 的端口对账原**只认整数 `port`**（`_reg_covers`），而 `rpc.statd` 的
loopback 套接字**每次启动自选端口**（实测 `724` → `729` → `657`，都落在特权段 512–1023）
⇒ 写死端口号的登记**每次重启都可能假红**，且 `unmanaged` 的过期条目**无出口（静默腐烂）**。
本测试守：

  T1 **同源对照（先验红）**：同一份站上实况（轮换后的口 `701` + 占用者 `rpc.statd` + loopback）——
     旧形态（`port: 657`）**必红**（逐字复现"换号即假红"）；新形态（owner+range）**必绿**；
  T2 **不恒真（防洗信号）**：owner 不命中 / 非 loopback / 端口出段位 / 占用者取数缺失 ⇒ **一律 FAIL**
     （护栏 = 「只覆盖 loopback + 已知 owner」，见 `O-158`；"判不了 ≠ 通过"）；
  T3 **边界与回归**：range 两端含、两侧外不含；≥32768 豁免与整数条目两条**旧路径**一字未改；
  T4 **协议侧**：`proto: udp` 的段位条目**接不住** TCP 侧的同口（侧匹配与整数条目同口径）；
  T5 **真值形态（只读真文件）**：真 `ports.yaml` 的 statd 条已是段位形态且无整数残留；
     `check_ports`（表内自洽）对段位形态的**校验会红**（坏 range / 缺 owner / 非 loopback bind）。

★ **零写入 / 零 ssh**：把 `cluster.ssh_run` 与 `_net_doc` / `_plugins_doc` / `load_inventory` /
  `_port_entries` 整体**打桩**（合成数据）⇒ 跑**真判据**；唯一读真文件处是 T5（只读）。
  合成输出逐字照抄 B 站 2026-10-10 的 `sudo -n ss -lunp` 实测行（含表头），避免"格式漂了判据不知道"。

用法（退出码 0 = 全过）：
    py tests\\test_rpc_check_ports_range.py
"""
import sys
import types
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


# ── 合成站上输出（照抄线上形态）────────────────────────────────────────────────
_SS_HEAD = "State  Recv-Q Send-Q  Local Address:Port  Peer Address:PortProcess"


def _ss(addr, port, *names, state="UNCONN"):
    """一行 `ss -lXnp`（实况格式: 第 4 列 = Local, 行尾 users:(("名",pid=..,fd=..))）。"""
    users = ("   users:((" + "),(".join(f'"{n}", pid=1234, fd=5' for n in names) + "))") if names else ""
    return f"{state}  0      0            {addr}:{port}        0.0.0.0:*{users}"


def _own(*lines):
    return "\n".join([_SS_HEAD] + list(lines))


def _st_out(bind="", ubind="", towner="", uowner=""):
    """合成一次合并 ssh 的输出：**cfg 三站同**（否则 (a) 会因三站不一致先红），其余段按需。"""
    cfg = "\n".join(f"{'a' * 16}  {p}" for p in R.WATCHED)
    return ("\n[cfg]\n" + cfg + "\n[conf]\n\n[bind]\n" + bind + "\n\n[ubind]\n" + ubind
            + "\n\n[towner]\n" + towner + "\n\n[uowner]\n" + uowner + "\n")


# 真值条目两形态（同一覆盖意图, 只差"键"）
RANGE = {"owner": "rpc.statd", "proto": "udp", "range": [512, 1023],
         "purpose": "rpc.statd 的本地特权套接字", "scope": ["B"], "bind": "127.0.0.1"}
OLD = {"port": 657, "proto": "udp", "purpose": "rpc.statd 的本地特权套接字", "scope": ["B"]}


def judge(port_entries, ubind="", uowner="", bind="", towner=""):
    """打桩 ssh_run / _net_doc / _plugins_doc / load_inventory / _port_entries ⇒ 跑**真判据**。"""
    outs = {st: _st_out() for st in "ABC"}
    outs["B"] = _st_out(bind=bind, ubind=ubind, towner=towner, uowner=uowner)
    fake = types.ModuleType("cluster")
    fake.ROUTE, fake.RPC_MODELS = {}, set()
    fake.ssh_run = lambda st, cmd, timeout=90, strict=False: (True, outs.get(st, ""))
    saved = (sys.modules.get("cluster"), R._net_doc, R._plugins_doc,
             R.load_inventory, R._port_entries)
    sys.modules["cluster"] = fake
    R._net_doc = lambda: {}
    R._plugins_doc = lambda: {}
    R.load_inventory = lambda: ({}, {})
    R._port_entries = lambda: port_entries
    try:
        return R.check_stations({})
    finally:
        old_cluster, R._net_doc, R._plugins_doc, R.load_inventory, R._port_entries = saved
        if old_cluster is None:
            sys.modules.pop("cluster", None)
        else:
            sys.modules["cluster"] = old_cluster


def blob(res):
    st, note, det = res
    return st, " ".join(det)


# 「同一份实况」= 轮换后的口 701（≠ 旧登记 657），占用者/形态都对
LIVE_UBIND = " 127.0.0.1:701 "
LIVE_UOWN = _own(_ss("127.0.0.1", 701, "rpc.statd"))

# ── T1 ★ 同源对照（先验红）：旧键（整数 port）必红 · 新键（owner+range）必绿 ──────────
st_new, b_new = blob(judge({"unmanaged": [RANGE]}, ubind=LIVE_UBIND, uowner=LIVE_UOWN))
chk("T1 新形态 (owner+range)：轮换后的口 701 ⇒ 不红", st_new != "FAIL" and ":701" not in b_new,
    f"<- {st_new} {b_new[:160]}")
st_old, b_old = blob(judge({"unmanaged": [OLD]}, ubind=LIVE_UBIND, uowner=LIVE_UOWN))
chk("T1 ★ 旧形态 (port: 657) 在同一输入上必红（逐字复现'换号即假红'）",
    st_old == "FAIL" and "UDP :701 有监听但分配表未登记" in b_old, f"<- {st_old} {b_old[:200]}")
chk("T1 新形态下 A/C 不被误伤", "A 站 UDP :701" not in b_new and "C 站 UDP :701" not in b_new)

# ── T2 ★ 不恒真（防洗信号）：四道闸任一不合 ⇒ 依旧 FAIL ────────────────────────────
st, b = blob(judge({"unmanaged": [RANGE]}, ubind=LIVE_UBIND,
                   uowner=_own(_ss("127.0.0.1", 701, "avahi-daemon"))))
chk("T2 owner 不命中 ⇒ FAIL 且点名「占用者名未命中」+ 实测名",
    st == "FAIL" and "占用者名未命中" in b and "avahi-daemon" in b, f"<- {st} {b[:200]}")

st, b = blob(judge({"unmanaged": [RANGE]}, ubind=" 0.0.0.0:701 ",
                   uowner=_own(_ss("0.0.0.0", 701, "rpc.statd"))))
chk("T2 非 loopback ⇒ FAIL 且点名「只覆盖 loopback」",
    st == "FAIL" and "只覆盖 loopback" in b and "0.0.0.0" in b, f"<- {st} {b[:200]}")

st, b = blob(judge({"unmanaged": [RANGE]}, ubind=" 127.0.0.1:2099 ",
                   uowner=_own(_ss("127.0.0.1", 2099, "rpc.statd"))))
chk("T2 端口出段位 (2099) ⇒ FAIL（且不算'段位已覆盖但没接住'）",
    st == "FAIL" and ":2099" in b and "段位条目" not in b, f"<- {st} {b[:200]}")

st, b = blob(judge({"unmanaged": [RANGE]}, ubind=LIVE_UBIND, uowner=""))
chk("T2 ★ 占用者取数缺失 ⇒ FAIL 且点名「占用者取数缺失」「判不了」（判不了 ≠ 通过）",
    st == "FAIL" and "占用者取数缺失" in b and "判不了" in b, f"<- {st} {b[:200]}")

# ── T3 边界 + 旧路径回归 ────────────────────────────────────────────────────────
st, b = blob(judge({"unmanaged": [RANGE]}, ubind=" 127.0.0.1:512 127.0.0.1:1023 ",
                   uowner=_own(_ss("127.0.0.1", 512, "rpc.statd"), _ss("127.0.0.1", 1023, "rpc.statd"))))
chk("T3 段位两端 (512/1023) 都含 ⇒ 不红", st != "FAIL" and ":512" not in b and ":1023" not in b,
    f"<- {st} {b[:160]}")
st, b = blob(judge({"unmanaged": [RANGE]}, ubind=" 127.0.0.1:511 127.0.0.1:1024 ",
                   uowner=_own(_ss("127.0.0.1", 511, "rpc.statd"), _ss("127.0.0.1", 1024, "rpc.statd"))))
chk("T3 段位两侧外 (511/1024) 都不含 ⇒ 2 条 FAIL",
    st == "FAIL" and ":511" in b and ":1024" in b, f"<- {st} {b[:200]}")
st, b = blob(judge({"unmanaged": [{"port": 657, "proto": "udp", "scope": ["B"]}]},
                   ubind=" 127.0.0.1:657 "))
chk("T3 整数条目旧路径一字未改（657 命中 ⇒ 不红）", st != "FAIL" and ":657" not in b, f"<- {st}")
st, b = blob(judge({"unmanaged": [RANGE]}, ubind=" 127.0.0.1:40000 "))
chk("T3 ≥32768 豁免旧路径一字未改（40000 未登记 ⇒ 也不红）", st != "FAIL" and ":40000" not in b, f"<- {st}")

# ── T4 协议侧：udp 段位条接不住 TCP 侧 ──────────────────────────────────────────
st, b = blob(judge({"unmanaged": [RANGE]}, bind=" 127.0.0.1:701 ",
                   towner=_own(_ss("127.0.0.1", 701, "rpc.statd", state="LISTEN"))))
chk("T4 proto: udp 的段位条接不住 TCP 侧同口 ⇒ FAIL", st == "FAIL" and "TCP :701" in b, f"<- {st} {b[:200]}")

# ── T5 真值形态 + 表内自洽（唯一读真文件处，只读）────────────────────────────────
try:
    _ents = R._port_entries()
    _un = [e for e in (_ents.get("unmanaged") or []) if isinstance(e, dict)]
    _st_act = [e for e in _un if e.get("owner") == "rpc.statd"]
    chk("T5 真表 statd 条 = 段位形态 (无 port · range [512,1023] · bind loopback · proto udp · scope [B])",
        len(_st_act) == 1 and not isinstance(_st_act[0].get("port"), int)
        and _st_act[0].get("range") == [512, 1023] and _st_act[0].get("bind") == "127.0.0.1"
        and str(_st_act[0].get("proto")).lower() == "udp" and _st_act[0].get("scope") == ["B"],
        f"<- {_st_act}")
    chk("T5 真表 unmanaged 无整数残留 (657/729/724 不得再以 port 形态出现)",
        not ({657, 729, 724} & {e.get("port") for e in _un}), f"<- {sorted(str(e.get('port')) for e in _un)}")
    _st_p, _note_p, _det_p = R.check_ports({})
    chk("T5 真表 check_ports 仍 PASS（新校验不吃存量）", _st_p == "PASS", f"<- {_st_p} {_det_p[:2]}")
except Exception as e:                                   # noqa: BLE001
    chk("T5 真 ports.yaml 可解析", False, f"<- {type(e).__name__}: {e}")

_M_OK = [{"port": 9999, "purpose": "占位", "scope": ["B"], "bind": "127.0.0.1", "owner": "x"}]


def _check_ports_with(entries):
    orig = R._port_entries
    R._port_entries = lambda: entries
    try:
        return R.check_ports({})
    finally:
        R._port_entries = orig


for _ent, _label, _expect in (
    ({"owner": "rpc.statd", "range": "512-1023", "bind": "127.0.0.1"}, "range 写成字符串", "range"),
    ({"range": [512, 1023], "bind": "127.0.0.1"}, "缺 owner", "owner"),
    ({"owner": "rpc.statd", "range": [512, 1023], "bind": "0.0.0.0"}, "bind 非 loopback", "loopback"),
):
    _st_c, _note_c, _det_c = _check_ports_with({"managed": _M_OK, "unmanaged": [_ent]})
    chk(f"T5 check_ports 对段位形态校验会红（{_label}）",
        _st_c == "FAIL" and any(_expect in x for x in _det_c), f"<- {_st_c} {_det_c}")
_st_c, _note_c, _det_c = _check_ports_with({"managed": _M_OK, "unmanaged": [RANGE]})
chk("T5 check_ports 合法段位形态 ⇒ 不红（不是恒红）", _st_c != "FAIL", f"<- {_st_c} {_det_c}")

print(f"\nRESULT: {'ALL PASS' if not fails else 'FAILED'}  ({total - len(fails)}/{total})")
sys.exit(1 if fails else 0)