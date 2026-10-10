"""`usb4` 判据的**键**：从「接口名」改成「物理端口(`tb_pci`)」—— 离线守四条契约（2026-10-10）。

为什么要有它：TB/USB4 的 netdev 名由**内核枚举顺序**决定 ⇒ **跨重启会翻**。实测 B 站 2026-10-10 11:13
重启后 `thunderbolt0/1` 互换（domain↔对端映射不变 · 地址仍在正确链路 · 8 向连通全绿），而按名字比对的
旧判据报出 **2 条"地址不符"** ⇒ **标签层假红**（抓不到真故障，每次重启却被点亮）。

★ **零写入 / 零 ssh**：本测试只调**纯函数**（`tb_pci_of` / `usb4_pick_iface`），端到端那两条把
  `_net_doc()` 与 `_health_probe()` **整体打桩**（合成数据）；唯一读真文件的地方是 T1（`_net_doc()`，只读）。

契约：
  ① **会红**：地址挂到**错的物理端口** ⇒ FAIL（新键不是恒真）；
  ② ★ **不再假红**：名字翻转、地址仍对 ⇒ PASS —— 且用**旧键（名字）**去取，同一份输入**必错 2 条**
     （= 逐字复现线上那次 FAIL，构成**先验红 · 同源对照**）；
  ③ **判不了 ≠ 通过**：登记缺 `tb_pci` / 站上无该端口 / 命中多个 ⇒ FAIL 且点名原因；
  ④ **真值完备**：真 `net.yaml` 的每个端点都有 `tb_pci` 且**互不重复**（防将来新增段漏字段）。

用法（退出码 0 = 全过）：
    py tests\\test_rpc_check_usb4_key.py
"""
import sys
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


# ── 合成实况：**名字翻转**（B 的 A-B 段落在 thunderbolt1），但地址/端口/MTU/连通全对 ──────────
def _dev(pci):
    """按线上的真实形态生成设备路径（domain 号按 PCI 函数推：.6 ⇒ domain1，.5 ⇒ domain0）。"""
    dom = 1 if str(pci).endswith(".6") else 0
    return f"/sys/devices/pci0000:00/0000:00:08.3/{pci}/domain{dom}/{dom}-0/{dom}-2/{dom}-2.0"


def _live(addr_by_st):
    out = {}
    for st, (t0, t1, a0, a1) in addr_by_st.items():
        out[st] = {"reachable": True,
                   "addr": {"thunderbolt0": a0, "thunderbolt1": a1},
                   "link": {"thunderbolt0": {"mtu": "9000", "state": "up", "dev": _dev(t0)},
                            "thunderbolt1": {"mtu": "9000", "state": "up", "dev": _dev(t1)}},
                   "ping": {x: "OK" for x in ("10.10.10.1", "10.10.10.2", "10.10.11.1",
                                              "10.10.11.3", "10.10.12.1", "10.10.12.3")},
                   "route": {}, "raw": ""}
    return out


# 名字 = **今天（翻转后）**；B 的 t0 是 B-C 段、t1 是 A-B 段
LIVE_OK = _live({"A": ("0000:c7:00.6", "0000:c7:00.5", "10.10.10.1", "10.10.12.1"),
                 "B": ("0000:c8:00.6", "0000:c8:00.5", "10.10.11.1", "10.10.10.2"),
                 "C": ("0000:c8:00.6", "0000:c8:00.5", "10.10.11.3", "10.10.12.3")})

# 合成真值：`iface` 写**旧名字**（B 的 A-B 段记 thunderbolt0）⇒ 与今天的名字不符，pci 相符
DOC = {"segments": [
    {"name": "A-B", "mtu": 9000, "ends": [
        {"station": "A", "tb_pci": "0000:c7:00.6", "iface": "thunderbolt0", "ip": "10.10.10.1", "peer": "B"},
        {"station": "B", "tb_pci": "0000:c8:00.5", "iface": "thunderbolt0", "ip": "10.10.10.2", "peer": "A"}]},
    {"name": "B-C", "mtu": 9000, "ends": [
        {"station": "B", "tb_pci": "0000:c8:00.6", "iface": "thunderbolt1", "ip": "10.10.11.1", "peer": "C"},
        {"station": "C", "tb_pci": "0000:c8:00.6", "iface": "thunderbolt0", "ip": "10.10.11.3", "peer": "B"}]},
    {"name": "A-C", "mtu": 9000, "ends": [
        {"station": "A", "tb_pci": "0000:c7:00.5", "iface": "thunderbolt1", "ip": "10.10.12.1", "peer": "C"},
        {"station": "C", "tb_pci": "0000:c8:00.5", "iface": "thunderbolt1", "ip": "10.10.12.3", "peer": "A"}]}],
    "routes": [], "cross_checks": []}


def judge(doc, live):
    """打桩 `_net_doc`（合成真值）+ `_health_probe`（合成实况）⇒ 跑**真判据**。"""
    orig_doc, orig_hp = R._net_doc, R._health_probe
    R._net_doc = lambda: doc
    R._health_probe = lambda st: live.get(st, {"reachable": False, "error": "未打桩", "raw": ""})
    try:
        return R.check_usb4({})
    finally:
        R._net_doc, R._health_probe = orig_doc, orig_hp


# ── T1 真值完备（唯一读真文件处，只读）─────────────────────────────────────────
try:
    _real = R._net_doc() or {}
    _ends = [e for s in (_real.get("segments") or []) for e in (s.get("ends") or [])]
    _pcis = [str(e.get("tb_pci") or "") for e in _ends]
    chk("T1 真 net.yaml 每个端点都有 tb_pci", bool(_ends) and all(_pcis), f"<- {len(_ends)} 端")
    chk("T1 真 net.yaml 的 tb_pci 互不重复（同站内）",
        all(len({p}) == 1 for p in _pcis) and
        len({(str(e.get("station")), str(e.get("tb_pci"))) for e in _ends}) == len(_ends),
        f"<- {_pcis}")
except Exception as e:                                   # noqa: BLE001
    chk("T1 真 net.yaml 可解析", False, f"<- {type(e).__name__}: {e}")

# ── T2 `tb_pci_of` 形态 ───────────────────────────────────────────────────────
chk("T2 真样例取到 PCI 函数", R.tb_pci_of(_dev("0000:c8:00.5")) == "0000:c8:00.5",
    f"<- {R.tb_pci_of(_dev('0000:c8:00.5'))}")
chk("T2 空/非 TB 路径 ⇒ None（判不了，不回落成按名字）",
    R.tb_pci_of("") is None and R.tb_pci_of("/sys/devices/pci0000:00/0000:00:1f.6") is None)

# ── T3 `usb4_pick_iface` 三态 ─────────────────────────────────────────────────
_lm = LIVE_OK["B"]["link"]
got, why = R.usb4_pick_iface(_lm, {"tb_pci": "0000:c8:00.5"})
chk("T3 pci 命中（且与名字无关）", got == "thunderbolt1", f"<- {got!r} {why}")
got, why = R.usb4_pick_iface(_lm, {})
chk("T3 登记缺 tb_pci ⇒ fail-closed", got is None and "tb_pci" in why, f"<- {why}")
got, why = R.usb4_pick_iface(_lm, {"tb_pci": "0000:aa:00.9"})
chk("T3 站上无该 pci ⇒ fail-closed 且报实测", got is None and "站上没有" in why, f"<- {why}")

# ── T4 ★ 名字翻转 + 地址仍对 ⇒ PASS；同一输入用旧键必错 2 条（先验红 · 同源对照）─────
st4, note4, det4 = judge(DOC, LIVE_OK)
chk("T4 名字翻转、地址正确 ⇒ **PASS**（本次修复的回归）", st4 == "PASS", f"<- {st4} {det4}")
chk("T4 报数含「按物理端口对上 6/6」", "6/6" in note4, f"<- {note4}")
# 同源对照：旧键 = 真值里的 `iface` 名字 → 直接取地址
_old_bad = []
for s in DOC["segments"]:
    for e in s["ends"]:
        if LIVE_OK[e["station"]]["addr"].get(e["iface"]) != e["ip"]:
            _old_bad.append(f"{e['station']}/{e['iface']}")
chk("T4 ★ 旧键（名字）在同一输入上必错 **2 条**（逐字复现线上那次 FAIL）",
    sorted(_old_bad) == ["B/thunderbolt0", "B/thunderbolt1"], f"<- {sorted(_old_bad)}")

# ── T5 ★ 真故障仍会被抓：把 B-C 的地址配到 A-B 的端口上 ─────────────────────────
BAD = _live({"A": ("0000:c7:00.6", "0000:c7:00.5", "10.10.10.1", "10.10.12.1"),
             "B": ("0000:c8:00.6", "0000:c8:00.5", "10.10.10.2", "10.10.11.1"),   # ← 地址挂错端口
             "C": ("0000:c8:00.6", "0000:c8:00.5", "10.10.11.3", "10.10.12.3")})
st5, _n5, det5 = judge(DOC, BAD)
chk("T5 地址挂在**错的物理端口** ⇒ FAIL（新键不是恒真）", st5 == "FAIL", f"<- {st5}")
chk("T5 明细点名「地址挂在物理端口上不符」",
    any("地址挂在物理端口上不符" in x for x in det5), f"<- {det5[:2]}")

# ── T6 缺 tb_pci ⇒ FAIL（判不了 ≠ 通过）──────────────────────────────────────
DOC_NOKEY = {"segments": [{"name": "A-B", "mtu": 9000, "ends": [
    {"station": "A", "iface": "thunderbolt0", "ip": "10.10.10.1", "peer": "B"},
    {"station": "B", "iface": "thunderbolt1", "ip": "10.10.10.2", "peer": "A"}]}],
    "routes": [], "cross_checks": []}
st6, _n6, det6 = judge(DOC_NOKEY, LIVE_OK)
chk("T6 登记缺 tb_pci ⇒ FAIL 且点名（判不了 ≠ 通过）",
    st6 == "FAIL" and any("登记缺 `tb_pci`" in x for x in det6), f"<- {st6}")

print(f"\nRESULT: {'ALL PASS' if not fails else 'FAILED'}  ({total - len(fails)}/{total})")
sys.exit(1 if fails else 0)