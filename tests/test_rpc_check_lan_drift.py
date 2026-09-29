"""`ADR-0006 v1.1 · D6`：LAN 地址对账判据（「站上实况 vs 真值」+ USB4 降级通道）正反用例（2026-09-29）。

为什么要有它：本判据要消灭的**具体缺陷**是 —— 旧版靠 `ssh -G <别名>`，于是 `host: null` 的
C 站**整站不在射程内**；2026-09-29 C 的 LAN 由 `192.168.1.37` 漂到 `192.168.1.8` 时，
6 项断言**一律只报「可达 2/3 站」、不给根因**。⇒ 本测试守三条契约：
  ① **会红**（漂移 ⇒ FAIL 且**点名** + 带修法）；
  ② ★ **射程可见**（`host: null` 的站必须有**显式**射程声明，绝不静默跳过 —— 这正是原缺陷）；
  ③ **不静默降级**（探不到 ⇒ 报「无法判定」而**不是**通过）。

★ **零写入**：本测试只调**纯函数**（`validate_lan_addr` / `pick_lan_addr` / `_parse_lanip`）并注入
  合成数据；唯一读真文件的地方是 `_net_doc()`（只读）。⇒ 不存在"探针回写同一文件改了 CRLF"那类风险
  （本仓踩过），故末尾无需字节级自证。

用法（退出码 0 = 全过）：
    py tests\\test_rpc_check_lan_drift.py
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


# 合成真值：A/B 有别名，C 无别名（= 线上实况的形态，但不依赖真文件）；主控 IP 也登记在真值里
MASTER_WANT = "192.168.1.36"
LAN = {"master": {"ip": MASTER_WANT, "iface": "WLAN"},
       "stations": [
           {"station": "A", "host": "scott-lau-NEX.local", "ip": "192.168.1.33", "iface": "enp195s0"},
           {"station": "B", "host": "scott-lau-GTR-Pro.local", "ip": "192.168.1.32", "iface": "enp193s0"},
           {"station": "C", "host": None, "ip": "192.168.1.37", "iface": "eno1"},
       ]}
NAMED = [e["station"] for e in LAN["stations"] if e.get("host")]


_DEF = object()          # 哨兵：区分"未传"（= 给个与真值一致的 master）与"显式传 None"


def judge(seen, lan=None, master=_DEF):
    """打桩 `_ssh_g_hostname`（master 侧绑定：默认"正确"），只让**站上实况**决定结果。

    master 默认给"与真值一致"的值 ⇒ 旧的用例不受新增的主控判据影响；
    要测"master 探不到"必须**显式**传 `master=None`（故这里用哨兵而不是默认参数 None）。
    """
    orig = R._ssh_g_hostname
    R._ssh_g_hostname = lambda alias: {"scott-lau-NEX.local": "192.168.1.33",
                                       "scott-lau-GTR-Pro.local": "192.168.1.32"}.get(alias)
    try:
        return R.validate_lan_addr(lan or LAN, seen,
                                   {"ip": MASTER_WANT} if master is _DEF else master)
    finally:
        R._ssh_g_hostname = orig


# ── A. 正例：三站地址都与真值一致 ⇒ 无 FAIL 无 WARN ──────────────────────────
d, w, i = judge({
    "A": {"ip": "192.168.1.33", "iface": "enp195s0", "dynamic": True},
    "B": {"ip": "192.168.1.32", "iface": "enp193s0", "dynamic": True},
    "C": {"ip": "192.168.1.37", "iface": "eno1", "dynamic": True},
})
chk("A1 全一致 ⇒ 无 FAIL", not d, f"<- {d}")
chk("A2 全一致 ⇒ 无 WARN", not w, f"<- {w}")
chk("A3 三站都报『<站> LAN 地址与真值一致』（不含 master 那行, 单列在 J6）",
    sum(1 for x in i if "站 LAN 地址与真值一致" in x) == 3, f"<- {i}")

# ── B. ★ 先验红：站上实况漂移（= 2026-09-29 C 站的真实现象）────────────────────
d, w, i = judge({
    "A": {"ip": "192.168.1.33", "iface": "enp195s0", "dynamic": True},
    "B": {"ip": "192.168.1.32", "iface": "enp193s0", "dynamic": True},
    "C": {"ip": "192.168.1.8", "iface": "eno1", "dynamic": True},
})
blob = " ".join(d)
chk("B1 C 站 .37→.8 ⇒ FAIL", bool(d), f"<- {d}")
chk("B2 且**点名已漂移**并给出新旧值", "已漂移" in blob and "192.168.1.37" in blob and "192.168.1.8" in blob,
    f"<- {blob[:160]}")
chk("B3 且标注 scope=dynamic/DHCP", "dynamic/DHCP" in blob, f"<- {blob[:160]}")
chk("B4 ★ 且带**修法**（三处真值 + 根治指向 D5）",
    "net.yaml" in blob and "cluster_const" in blob and "D5" in blob, f"<- {blob[:200]}")
chk("B5 A/B 不因此被误报", not any("A 站" in x or "B 站" in x for x in d), f"<- {d}")

# ── C. 先验红：master 侧**名字绑定**漂移（D1 的那一面，必须仍然会红）──────────
def _judge_bad_alias():
    orig = R._ssh_g_hostname
    R._ssh_g_hostname = lambda alias: "192.168.1.99"
    try:
        return R.validate_lan_addr(LAN, {"A": {"ip": "192.168.1.33", "iface": "enp195s0"},
                                         "B": {"ip": "192.168.1.32", "iface": "enp193s0"},
                                         "C": {"ip": "192.168.1.37", "iface": "eno1"}})
    finally:
        R._ssh_g_hostname = orig


d, _, _ = _judge_bad_alias()
chk("C1 master 侧绑定错 ⇒ FAIL 且点名『master 侧绑定漂移』",
    bool(d) and any("master 侧绑定漂移" in x for x in d), f"<- {d}")

# ── D. ★ 不静默降级：探不到 ⇒ 报「无法判定」，而不是通过 ──────────────────────
for seen, label, expect in (
    ({"A": None, "B": {"ip": "192.168.1.32", "iface": "enp193s0"},
      "C": {"ip": "192.168.1.37", "iface": "eno1"}}, "seen 为 None", "无法判定"),
    ({"A": {"error": "直连: iface=eno1 在站上不存在"},
      "B": {"ip": "192.168.1.32", "iface": "enp193s0"},
      "C": {"ip": "192.168.1.37", "iface": "eno1"}}, "seen 带 error", "无法判定"),
):
    d, w, _ = judge(seen)
    chk(f"D 探不到({label}) ⇒ WARN 且点名『{expect}』（不得静默通过）",
        not d and any(expect in x for x in w), f"<- detail={d} warn={w}")

# ── E. 先验红：接口漂移（地址对但 iface 变了）⇒ WARN ────────────────────────
d, w, _ = judge({"A": {"ip": "192.168.1.33", "iface": "enp195s0_renamed"},
                 "B": {"ip": "192.168.1.32", "iface": "enp193s0"},
                 "C": {"ip": "192.168.1.37", "iface": "eno1"}})
chk("E1 LAN 地址所在接口变了 ⇒ WARN 且点名 iface", not d and any("接口已变" in x for x in w), f"<- {w}")

# ── F. ★★ 射程契约：host:null 的站必须有**显式**射程声明（本缺陷的直接监管）────
d, w, i = judge({
    "A": {"ip": "192.168.1.33", "iface": "enp195s0"},
    "B": {"ip": "192.168.1.32", "iface": "enp193s0"},
    "C": {"ip": "192.168.1.37", "iface": "eno1"},
})
chk("F1 host:null 的站 ⇒ 有**射程声明**（不是静默跳过）",
    any("无别名" in x and "射程声明" in x for x in i), f"<- {i}")
chk("F2 且该站照常参与『站上实况』判定（有『与真值一致』）",
    any("C 站 LAN 地址与真值一致" in x for x in i), f"<- {i}")

# ── G. pick_lan_addr：挑选规则（先精后宽，歧义不猜）────────────────────────
_SEGS = [R.ipaddress.ip_network("10.10.10.0/24"), R.ipaddress.ip_network("10.10.11.0/24"),
         R.ipaddress.ip_network("10.10.12.0/24")]
_ROWS = [
    {"iface": "eno1", "ip": "192.168.1.8", "cidr": "192.168.1.8/24", "dynamic": True},
    {"iface": "thunderbolt0", "ip": "10.10.11.3", "cidr": "10.10.11.3/24", "dynamic": False},
    {"iface": "thunderbolt1", "ip": "10.10.12.3", "cidr": "10.10.12.3/24", "dynamic": False},
]
got, err = R.pick_lan_addr(_ROWS, "eno1", _SEGS)
chk("G1 认 iface ⇒ 挑中 LAN 地址", got and got["ip"] == "192.168.1.8" and not err, f"<- {got} {err}")
got, err = R.pick_lan_addr(_ROWS, None, _SEGS)
chk("G2 无 iface 提示 ⇒ 排除 USB4 段后唯一剩下的就是 LAN", got and got["ip"] == "192.168.1.8" and not err,
    f"<- {got} {err}")
got, err = R.pick_lan_addr(_ROWS, "eth_does_not_exist", _SEGS)
chk("G3 登记的 iface 不存在 ⇒ 不猜, 报原因", got is None and "不存在" in (err or ""), f"<- {got} {err}")
got, err = R.pick_lan_addr(_ROWS + [{"iface": "enp9s0", "ip": "192.168.1.77",
                                     "cidr": "192.168.1.77/24", "dynamic": True}], None, _SEGS)
chk("G4 多候选(>1 个非 USB4) ⇒ 不猜, 报原因", got is None and "不猜" in (err or ""), f"<- {got} {err}")
got, err = R.pick_lan_addr(_ROWS, "thunderbolt0", _SEGS)
chk("G5 登记的 iface 落在 USB4 段内(= net.yaml 自相矛盾) ⇒ 不猜, 报原因",
    got is None and "自相矛盾" in (err or ""), f"<- {got} {err}")
got, err = R.pick_lan_addr([r for r in _ROWS if r["iface"] != "eno1"], None, _SEGS)
chk("G6 站上没有任何非 USB4 地址(LAN 已断) ⇒ 不猜, 报原因",
    got is None and "LAN 可能已断" in (err or ""), f"<- {got} {err}")

# ── H. _parse_lanip：真实样例（站上原样输出）──────────────────────────────
_RAW = ("2: eno1    inet 192.168.1.8/24 brd 192.168.1.255 scope global dynamic noprefixroute eno1\\"
        "       valid_lft 47003sec preferred_lft 47003sec\n"
        "4: thunderbolt0    inet 10.10.11.3/24 brd 10.10.11.255 scope global noprefixroute "
        "thunderbolt0\\       valid_lft forever preferred_lft forever\n"
        "1: lo    inet 127.0.0.1/8 scope host lo\\       valid_lft forever preferred_lft forever\n"
        "(这行是垃圾, 应被忽略)")
rows = R._parse_lanip(_RAW)
chk("H1 解析出 2 条, 且 **lo 被解析层自己丢掉**（defense in depth：不依赖调用方的 `scope global`）",
    len(rows) == 2 and all(r["iface"] != "lo" for r in rows), f"<- {rows}")
chk("H2 eno1 那条 dynamic=True 且 cidr 正确",
    rows and rows[0]["iface"] == "eno1" and rows[0]["dynamic"] is True
    and rows[0]["cidr"] == "192.168.1.8/24", f"<- {rows[:1]}")
chk("H3 thunderbolt0 那条 dynamic=False(静态)", rows and rows[1]["dynamic"] is False, f"<- {rows[1:]}")
chk("H4 垃圾行被忽略(不猜)", all("垃圾" not in r["iface"] for r in rows), f"<- {rows}")

# ── J. ★★ 主控自身漂移（2026-09-29 实况：master .36 → .102，整段换网 ⇒ 三站全不可达）──
_SAME = {"A": {"ip": "192.168.1.33", "iface": "enp195s0"},
         "B": {"ip": "192.168.1.32", "iface": "enp193s0"},
         "C": {"ip": "192.168.1.37", "iface": "eno1"}}
d, w, i = judge(dict(_SAME), master={"ip": "192.168.10.102"})
blob = " ".join(d)
chk("J1 master 自身 LAN 漂移 ⇒ FAIL", bool(d), f"<- {d}")
chk("J2 且**点名 master 自身**并给出新旧值", "master" in blob and "192.168.1.36" in blob
    and "192.168.10.102" in blob, f"<- {blob[:180]}")
chk("J3 且说明它是『三站全部不可达』的根因", "三站全部不可达" in blob, f"<- {blob[:200]}")
d, w, _ = judge(dict(_SAME), master={"error": "socket 失败"})
chk("J4 master 探不到 ⇒ WARN 点名『无法判定』（不得静默通过）",
    not d and any("master 自身 LAN 地址**无法判定**" in x for x in w), f"<- {w}")
d, w, _ = judge(dict(_SAME), master=None)
chk("J5 master 结果缺失(None) ⇒ WARN 点名『无法判定』", not d and any("master" in x for x in w), f"<- {w}")
d, w, i = judge(dict(_SAME))
chk("J6 master 一致 ⇒ 有『与真值一致』且无 FAIL/WARN",
    not d and not w and any("master 自身 LAN 地址与真值一致" in x for x in i), f"<- {i}")
# 先验红（本地原语）：`_local_lan_ip` 的两种边界 —— 有路则给出源地址、非法目标则 None（不猜）
_r = R._local_lan_ip("203.0.113.1")            # TEST-NET-3: 走默认路由, 不需要它可达
chk("J7 `_local_lan_ip` 对有默认路由的目标返回本机源地址（原语可用且**不发包**）",
    isinstance(_r, str) and _r.count(".") == 3, f"<- {_r!r}")
chk("J8 `_local_lan_ip` 对非法目标返回 None（不猜）", R._local_lan_ip("not-an-ip") is None)

# ── I. 真真值源仍可读（且三站都在）—— 只读，不改 ───────────────────────────
try:
    real = (R._net_doc() or {}).get("lan") or {}
    sts = [e.get("station") for e in (real.get("stations") or []) if isinstance(e, dict)]
    chk("I1 真 net.yaml §lan 可解析且含 A/B/C", set(sts) >= {"A", "B", "C"}, f"<- {sts}")
    chk("I2 真表的每站都登记了 ip 与 iface（登记完整才有资格当判据输入）",
        all(e.get("ip") and e.get("iface") for e in real.get("stations") or []),
        f"<- {real.get('stations')}")
except Exception as e:
    chk("I1 真 net.yaml §lan 可解析", False, f"<- {type(e).__name__}: {e}")

# ── 汇总 ────────────────────────────────────────────────────────────────
print("\n" + "-" * 40)
print(f"LAN_DRIFT_TEST pass={total - len(fails)}/{total} fail={len(fails)}")
print("RESULT: " + ("ALL PASS" if not fails else f"{len(fails)} FAILED -> {fails}"))
sys.exit(1 if fails else 0)