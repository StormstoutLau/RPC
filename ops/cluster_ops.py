#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cluster_ops — `cluster.py` 的按域拆分模块（review-p2-cluster 阶段）。

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

from cluster_agent import (  # noqa: E402
    _agent_proj_roots,
)
from cluster_console import (  # noqa: E402
    disp_width as _dw, pad as _pad,
)
from cluster_runtime import (  # noqa: E402
    containers_plan,
)

# ── P2-5: TTL 空闲自动卸载 ───────────────────────────────
# 站上件: /usr/local/bin/cluster-ttl (检查器) + cluster-ttl.{service,timer} (60s oneshot)
# 与"零自加载"方针并存: TTL 只**释放**已加载的资源, 从不加载任何模型。
# **默认关**: conf `TTL_ENABLED=0` ⇒ 检查器降级为"演练"(照常判定并打印结论, 绝不卸载)。
TTL_BIN = "/usr/local/bin/cluster-ttl"
TTL_CONF = "/etc/llama-instances/ttl.env"
TTL_TIMER = "cluster-ttl.timer"
TTL_DEFAULT_S = 1800


def _ttl_probe(st: str) -> dict:
    """一次 ssh 取全 (部署态 + 状态 JSON + 单元态) —— 不做三次往返。

    ⚠ `systemctl is-enabled` 对"存在但未启用"的单元会**既打印 disabled 又返回 1**,
    直接写 `|| echo not-found` 会同时输出两行、把"未启用"误读成"不存在" (实测踩到)。
    故一律用 `| head -1` 只取一行, 而"单元是否存在"单独用文件判据 (unit=yes/no)。
    """
    cmd = (f"if [ -x {TTL_BIN} ]; then echo DEPLOYED; else echo MISSING; fi; "
           f"{TTL_BIN} --status --json 2>/dev/null || echo '{{}}'; "
           f"[ -f /etc/systemd/system/{TTL_TIMER} ] && echo 'unit=yes' || echo 'unit=no'; "
           f"printf 'enabled=%s\\n' \"$(systemctl is-enabled {TTL_TIMER} 2>/dev/null | head -1)\"; "
           f"printf 'active=%s\\n' \"$(systemctl is-active {TTL_TIMER} 2>/dev/null | head -1)\"")
    ok, out = ssh_run(st, cmd, timeout=45)
    res = {"ok": ok, "deployed": False, "unit": False, "state": {},
           "timer_enabled": "?", "timer_active": "?"}
    for ln in out.splitlines():
        ln = ln.strip()
        if ln == "DEPLOYED":
            res["deployed"] = True
        elif ln == "MISSING":
            res["deployed"] = False
        elif ln.startswith("{"):
            try:
                res["state"] = json.loads(ln)
            except Exception:
                pass
        elif ln == "unit=yes":
            res["unit"] = True
        elif ln == "unit=no":
            res["unit"] = False
        elif ln.startswith("enabled="):
            res["timer_enabled"] = ln.split("=", 1)[1] or "?"
        elif ln.startswith("active="):
            res["timer_active"] = ln.split("=", 1)[1] or "?"
    return res


def _ttl_parallel(stations) -> dict:
    res, threads = {}, []
    for st in stations:
        t = threading.Thread(target=lambda s=st: res.__setitem__(s, _ttl_probe(s)))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    return res


def _ttl_row(st: str, r: dict) -> str:
    s = r.get("state") or {}
    if not r.get("deployed"):
        return (f"  {st:<3} {_pad('未部署', 6)} {'-':<8} {'-':<11} {'-':<16} {'-':<14} "
                f"装: ops/station-bin/cluster-ttl + systemd 单元")
    on = "开" if s.get("enabled") else "关"
    timer = f"{r.get('timer_enabled')}/{r.get('timer_active')}"
    if s.get("engine_pid"):
        eng = f"pid={s['engine_pid']}:{s.get('engine_port')}"
        idle = (f"{s['idle_s']}s/{s.get('ttl_s')}s" if s.get("idle_s") is not None else "未比对")
    else:
        eng, idle = "无 (零自加载)", "-"
    la = s.get("last_action") or {}
    if la:
        act = (f"{str(la.get('iso'))[11:19]} {('已卸载' if la.get('result') == 'unloaded' else la.get('result'))}"
               f" (idle {la.get('idle_s')}s)")
    else:
        act = "无"
    # D6-P3-1: `on`(开/关) · `eng`(无 (零自加载)) · `idle`(未比对) 都可能是中文 ⇒ 按显示宽度填充
    return (f"  {st:<3} {_pad(on, 6)} {str(s.get('ttl_s', TTL_DEFAULT_S)) + 's':<8} {timer:<11} "
            f"{_pad(eng, 16)} {_pad(idle, 14)} {act}")


def cmd_ttl(argv) -> int:
    """cluster.py ttl {status|check|enable|disable} [--station X] [--ttl N] [--go] [--dry-run]

    P2-5 空闲 TTL 自动卸载: 站上 cluster-ttl 每 60s 判一次"引擎是否已空闲 ≥ 阈值",
    到期执行 `infer-unload` (会一并停掉全部 RPC worker)。**默认关**。
    check 默认只演练 (不卸载), --go 才真卸; enable/disable 写 conf + 开关 timer。
    """
    act = (argv[0] if argv else "status").lower()
    if act not in ("status", "check", "enable", "disable"):
        print("用法: cluster.py ttl {status|check|enable|disable} "
              "[--station A|B|C] [--ttl N] [--dry-run] [--go]")
        return 1
    only, ttl, go, dry = None, None, ("--go" in argv), ("--dry-run" in argv)
    i = 1
    while i < len(argv):
        if argv[i] == "--station" and i + 1 < len(argv):
            only = argv[i + 1].upper()
            i += 2
            continue
        if argv[i] == "--ttl" and i + 1 < len(argv):
            ttl = int(float(argv[i + 1]))
            i += 2
            continue
        i += 1
    stations = [only] if only else ["A", "B", "C"]

    if act == "status":
        res = _ttl_parallel(stations)
        print(f"\n=== TTL 空闲自动卸载 (P2-5) — 默认关; 开启后 idle ≥ 阈值即执行 infer-unload ===\n")
        hdr = (f"  {_pad('站', 3)} {_pad('开关', 6)} {_pad('阈值', 8)} {_pad('定时器', 11)} "
               f"{_pad('引擎', 16)} {_pad('空闲/阈值', 14)} {'最近动作'}")
        print(hdr)
        print("  " + "-" * (_dw(hdr) - 2))
        for st in stations:
            print(_ttl_row(st, res.get(st, {})))
        print("\n  定时器列 = is-enabled/is-active; 开关列 = conf 的 TTL_ENABLED (关时检查器只演练, 不卸载)")
        print("  空闲 = now − 上次活跃; 判据是 /metrics 累计计数器差分 (Δtok=0 才计空闲), 在途请求>0 视为活跃")
        return 0

    if act == "check":
        mode = "执行" if go else "演练"
        print(f"\n=== TTL 判定一次 [{mode}] ===  (演练=只判定不卸载; 关掉总开关时无论如何都不卸)\n")
        res, threads = {}, []
        for st in stations:
            t = threading.Thread(target=lambda s=st: res.__setitem__(
                s, ssh_run(s, f"{TTL_BIN} {'--dry-run' if not go else ''}", timeout=900)))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        for st in stations:
            ok, out = res.get(st, (False, ""))
            print(f"--- {st} 站 ---")
            print((out or "(无输出)").strip() or "(空)")
        return 0

    # enable / disable
    if act == "enable" and ttl is None:
        ttl = TTL_DEFAULT_S
    pairs = [f"TTL_ENABLED={'1' if act == 'enable' else '0'}"]
    if act == "enable":
        pairs.append(f"TTL_IDLE_SECONDS={ttl}")
        pairs.append(f"TTL_DRY_RUN={'1' if dry else '0'}")
    print(f"\n=== TTL {'开启' if act == 'enable' else '关闭'} ===")
    if act == "enable":
        print(f"  阈值 {ttl}s; 演练={'是' if dry else '否'}"
              f"; 定时器 enable --now (60s 周期)")
    for st in stations:
        if not _ttl_probe(st).get("deployed"):
            print(f"  [{st}] 未部署 cluster-ttl —— 跳过 (先同步 ops/station-bin/cluster-ttl 与单元)")
            continue
        ok, out = ssh_run(st, f"sudo -n {TTL_BIN} --set " + " ".join(pairs), timeout=60)
        if not ok or "已更新" not in out:
            print(f"  [{st}] 写 conf 失败: {(out or '').strip()[:120]}")
            continue
        verb = "enable --now" if act == "enable" else "disable --now"
        ssh_run(st, f"sudo -n systemctl {verb} {TTL_TIMER}", timeout=60)
        r = _ttl_probe(st)
        s = r.get("state") or {}
        if not r.get("unit"):
            print(f"  [{st}] conf 已写, 但 systemd 单元不存在 —— "
                  f"需部署 ops/cluster-ttl.service/.timer (仓库 → /etc/systemd/system/)")
            continue
        print(f"  [{st}] conf TTL_ENABLED={1 if act == 'enable' else 0}"
              f" ttl={s.get('ttl_s')}s → timer {r.get('timer_enabled')}/{r.get('timer_active')}"
              + ("  (演练: 只判定不卸载)" if s.get("conf_dry_run") else ""))
    print("\n  复核: cluster.py ttl status")
    return 0


INBOX_ROOT = Path(__file__).resolve().parent.parent / "inbox"
_INBOX_YAML = Path(__file__).resolve().parent.parent / "inventory" / "inbox.yaml"


def _inbox_truth():
    """读受理状态机真值 (`inventory/inbox.yaml`) —— 与 `rpc_check.py` / `cluster_web.py` **同源**,
    不再各抄一份(ADR-0008 状态机单一真值; D6-P1-2 #8: seal 提示语原为第三份副本)。"""
    import yaml
    data = yaml.safe_load(_INBOX_YAML.read_text(encoding="utf-8"))
    states = data.get("states") if isinstance(data, dict) else None
    if not isinstance(states, dict):
        raise ValueError(f"{_INBOX_YAML} 缺 `states:` 映射段")
    return states


_MANIFEST_LINE_RE = re.compile(r"^([0-9a-f]{64})\s{2}(.+)$")

# ── inbox 交付束的 **U-1 坐标**（2026-10-19 裁定落地 · 用户「按照建议执行」）──────────────
# ★★ **真值只在这一处**（`U1#7-三元组`）：算法 / 截断 / 前缀拼法一律调 `rpc_check`，
#    **不在此重抄**（重抄 = 同一事实两个定义点）。
# 依据：U1 spec §1.3 —— identifier 的**既有映射表已写**「inbox 的文件路径」；「无版本者写 `0.0.0`」
#        + `inventory/namespaces.yaml` 的 `rpc_inbox`（`status: active`）。
# 口径（裁定）：**id = 清单数据行里的相对路径**（相对清单头声明的「项目根」）· **ver = `0.0.0`**。
# ⚠ 不许把 `run` / 交付分级 / 生成时间写进 identity —— 它们**都在头部、或已在 id 里**
#    ⇒ 写进去 = "同一事实两处表达"，**且重封即变 ⇒ 身份抖动**。
# ⚠ **已知残余（登记，不在本次改）**：id 按构造**不含受理目录** ⇒ 两条不同受理目录若出现
#    `agent-out/<同 run>/<同名>` 会**撞身份**；本仓当前零消费者 ⇒ 登记为条件触发（见 U1 spec §未实测 7）。
INBOX_U1_NS = "rpc_inbox"
INBOX_U1_VER = "0.0.0"


def _u1_identity(rel):
    """一条 inbox 条目的 **U-1 身份**（坐标在这里拼，算法/截断来自 `rpc_check`）。"""
    import rpc_check                      # 惰性 import —— 同 `_proj_roots` 的做法（避免顶层循环依赖）
    return rpc_check.u1_identity(INBOX_U1_NS, rel, INBOX_U1_VER)


def _u1_decl_line():
    """文件级**声明行** `# u1:<algo>:<trunc>` —— 拼法取自 `rpc_check.u1_header_line`（唯一真值源）。"""
    import rpc_check
    return rpc_check.u1_header_line()


def parse_u1_track(text, decl_line=None):
    """**纯函数** → `(declared, pairs, errors)`：解析 MANIFEST 的 **u1 轨**（`U1#7` 的第二轨）。

    `declared` = 首部有没有**声明行** `# u1:<algo>:<trunc>` —— ★★ **这就是本轨的开关**：
      没有声明 ⇒ `verify_manifest` **不判** u1（**旧清单零影响** ⇒ 不追溯改历史）。
    `pairs`    = `[(identity, relpath)]`，**按邻近配对**：一条 `# u1:…` 行 + **紧随其后**的数据行
      （identifier 就是数据行里那条路径 ⇒ **路径只写一处**，身份对得上一一）。
    `errors`   = 轨道缺陷（数据行缺身份行 / 身份行后面没有数据行 / 有 u1 行却没声明行 …）。

    ⚠ 为什么是"**声明制**"而不是"有条目就必须双轨"：后者会让**既有清单当场判红**
      —— 那正是 D-23 要防的"**追溯改历史**"。⇒ 老清单照旧、新清单强制双轨。
    """
    if decl_line is None:
        decl_line = _u1_decl_line()
    # ★★ **先判"本文件是否声称带 u1 轨"** —— 这决定要不要严判：
    #    · 有声明行（正常新清单） ⇒ 严判（每条数据行都要有身份行）
    #    · 既无声明、也**一条 u1 行都没有**（旧清单） ⇒ **不严判** ⇒ 一个字都不报（零影响）
    #    · 无声明却**出现了** u1 行（半拉子） ⇒ 严判 + 点名"轨不自描述"
    #   ⚠ 首稿把"每条数据行都要有身份行"**无条件**执行 ⇒ 旧清单**当场判红**
    #     —— 那正是 D-23 要防的"追溯改历史"；夹具第 ① 条当面抓住（先验红的收益）。
    stripped = [ln.strip() for ln in text.splitlines()]
    declared = decl_line in stripped
    has_u1 = any(ln.startswith("# u1:") for ln in stripped)
    strict = declared or has_u1
    pairs, errors = [], []
    pending = None
    for s in stripped:
        if not s:
            continue
        if s == decl_line:
            continue
        if s.startswith("# u1:"):
            if pending is not None:
                errors.append(f"上一条 u1 行（{pending[:28]}…）后面**没有数据行** ⇒ 身份悬空")
            pending = s[2:].strip()
            continue
        if s.startswith("#"):
            continue
        m = _MANIFEST_LINE_RE.match(s)
        if not m:
            continue
        rel = m.group(2).strip()
        if pending is None:
            if strict:
                errors.append(f"{rel}: **缺 u1 轨**（该数据行前面没有紧邻的 `# u1:…` 身份行）")
        else:
            pairs.append((pending, rel))
            pending = None
    if pending is not None:
        errors.append(f"末一条 u1 行（{pending[:28]}…）后面**没有数据行** ⇒ 身份悬空")
    if not declared and has_u1:
        errors.append(f"出现 u1 行却**没有**文件级声明行 `{decl_line}` ⇒ 轨不自描述")
    return declared, pairs, errors


def parse_manifest(text):
    """**纯函数**: 解析 `MANIFEST.sha256` -> `(项目根, [(sha256, 相对路径)])`。

    格式（`_inbox_seal` 生成，同 `sha256sum -c` 形）：
      · `#` 行 = 头注释 —— 其中 `项目根: <path>` 带出项目根（用于定位 `agent-out/<run>/<file>`）；
      · 数据行 = `<64hex>␠␠agent-out/<run>/<file>`（**两个空格**分隔）。
    """
    root, entries = None, []
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        if s.startswith("#"):
            m = re.search(r"项目根:\s*(\S+)", s)
            if m:
                root = m.group(1)
            continue
        m = _MANIFEST_LINE_RE.match(s)
        if m:
            entries.append((m.group(1), m.group(2).strip()))
    return root, entries


def verify_manifest(text, read_bytes=None, identity_of=None):
    """**纯函数**（注入 `read_bytes` ⇒ 离线可测）: 重算每条 sha256 与记录比对。

    D6-P1-1 §11.1-C 纪律 2「**`--check` 等价物（重算 → 比对）**」的唯一落点 ——
    供 `inbox seal --check`（生产者侧）与门禁 `inbox` 断言（**禁手改**机判）**共用**（避免两份实现）。
    返回 `(root, ok, missing, bad)`：`bad` = 逐条不符 / 读不到的明细（**含相对路径**）。

    ★ 2026-10-19 起**还判 u1 轨**（`U1#7` 裁定落地）—— 口径是「**声明制**」：
      仅当清单首部有**声明行**（`# u1:<algo>:<trunc>`）**才**判第二轨；**没有声明 ⇒ 不判**
      （旧清单**零影响** ⇒ 不重跑、不追溯改历史）。判据两条：
        ① **轨完整性**：每条数据行都要有**紧邻**的 `# u1:…` 身份行（缺一轨 ⇒ bad）；
        ② **身份复算**：身份必须与 `identity_of(rel)` 相符 ⇒ 格式合规但内容编造**也拦得住**。
      `identity_of` **注入**（同 `edge_direction_error` 的做法）⇒ 夹具离线可跑；默认
      走 `rpc_check.u1_identity`（**唯一真值源** ⇒ 此处不造第二份实现）。
    """
    read_bytes = read_bytes or (lambda p: Path(p).read_bytes())
    root, entries = parse_manifest(text)
    base = Path(root) if root else None
    ok, missing, bad = 0, 0, []
    for want, rel in entries:
        got = None
        if base is not None:
            try:
                got = hashlib.sha256(read_bytes(base / rel)).hexdigest()
            except Exception:
                got = None
        if got is None:
            missing += 1
            bad.append(f"{rel}: 读不到（项目根 {root} 下该件缺失）")
        elif got != want:
            bad.append(f"{rel}: **哈希不符**（记录 {want[:12]}… 实算 {got[:12]}…）⇒ 被手改或源被改动")
        else:
            ok += 1

    # ── u1 轨（**声明制**：无声明 ⇒ 一律不判 ⇒ 旧清单/旧束零影响，不追溯改历史）──────────
    declared, pairs, terrs = parse_u1_track(text)
    bad.extend(terrs)
    if declared:
        identity_of = identity_of or _u1_identity
        if not entries:
            bad.append("声明了 u1 轨却**零数据行** ⇒ 判据没有对象（本轨要求至少 1 条）")
        for ident, rel in pairs:
            want_id = identity_of(rel)
            if want_id != ident:
                bad.append(f"{rel}: u1 身份**复算不符**（记录 {ident[:28]}… 复算 {want_id[:28]}…）"
                           f"⇒ 格式合规但内容编造，或身份被手改")
    return root, ok, missing, bad


def _inbox_seal(argv) -> int:
    """cluster.py inbox seal <proj-dir> [--run <ts>|--all-runs] [--grade Reproduced|Replicated] [--go|--check]

    交付证据束钉死 (ADR-0008 §5.1): 把项目根 `agent-out/<ts>/` 的**实际存在的**证据件逐个 sha256,
    写入 `inbox/<proj-dir>/30_evidence/MANIFEST.sha256`（与 00_handoff 同格式，`sha256sum -c` 可校验）。

    为什么钉"实际存在的全部文件"而不是 `AGENT_EVIDENCE_FILES` 那 6 件:
      实测真实 run 目录并**不齐**那 6 件（judgment-record/accept-* 只在配了 accept/golden 的任务里才有）
      ⇒ 那 6 件是**链校验的"声明件"**，不等于"本次交付束"。硬套会导致常态失败。
    ⚠ 默认**只出计划**; `--go` 才落盘（与 flow / models link / egress borrow 同纪律）。
    """
    if not argv:
        print("用法: cluster.py inbox seal <proj-dir> [--run <ts>|--all-runs] "
              "[--grade Reproduced|Replicated] [--go|--check]")
        return 1
    name = argv[0]
    only_ts, all_runs, grade, go, check = None, False, "Reproduced", False, False
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--run" and i + 1 < len(argv):
            only_ts = argv[i + 1]; i += 2; continue
        if a == "--all-runs":
            all_runs = True; i += 1; continue
        if a == "--grade" and i + 1 < len(argv):
            grade = argv[i + 1]; i += 2; continue
        if a == "--go":
            go = True; i += 1; continue
        if a == "--check":
            check = True; i += 1; continue
        print(f"[seal] 未知参数: {a}")
        return 1
    if grade not in ("Reproduced", "Replicated"):
        print("[seal] --grade 只接受 Reproduced(内部同基座复验) 或 Replicated(异基座独立审计)")
        return 1

    entry = INBOX_ROOT / name
    if not (entry / "40_state" / "STATE.json").is_file():
        print(f"[seal] 不是受理目录 (缺 40_state/STATE.json): {entry}")
        return 1

    # 目录名 = <proj>-<yyyy-mm-dd> ⇒ 去日期得 proj; proj→root 真值在 agent-cli.ps1 (不在此再抄一份)
    proj = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", name)
    roots, note = _agent_proj_roots()
    root = roots.get(proj)
    if not root:
        print(f"[seal] 项目根未知: proj={proj!r}; 已知 {sorted(roots) or note}")
        return 1
    if check:
        # D6-P1-1 §11.1-C 纪律 2: **`--check` 等价物（重算 → 比对）** —— 只读, 不写。
        #   与门禁 `inbox` 断言共用 `verify_manifest`（**唯一实现**）; 项目根取自 **MANIFEST 头注释**
        #   （自包含: 换机器/换 clone 也能判，只要那个根在本机）。
        dst = entry / "30_evidence" / "MANIFEST.sha256"
        if not dst.is_file():
            print(f"[seal-check] 无 MANIFEST（尚未 `--go` 落盘）: {dst}")
            return 1
        mroot, mok, mmiss, mbad = verify_manifest(dst.read_text(encoding="utf-8"))
        print(f"[seal-check] {dst}")
        print(f"[seal-check] 项目根(取自清单头)={mroot}  ok={mok}  读不到={mmiss}  不符={len(mbad)}")
        for b in mbad[:10]:
            print(f"  ✗ {b}")
        if len(mbad) > 10:
            print(f"  …另 {len(mbad) - 10} 条")
        if not mbad:
            print("[seal-check] ✅ 逐条一致 ⇒ 证据束未被改动（可结案）。")
        return 1 if mbad else 0
    ao = root / "agent-out"
    if not ao.is_dir():
        print(f"[seal] 项目根下无 agent-out: {ao}")
        return 1

    all_cand = sorted((p for p in ao.iterdir() if p.is_dir() and p.name.isdigit()),
                      key=lambda p: p.name, reverse=True)
    if only_ts:
        runs = [p for p in all_cand if p.name == only_ts]
    elif all_runs:
        runs = all_cand
    else:
        runs = all_cand[:1]
    runs = [r for r in runs if any(f.is_file() for f in r.iterdir())]
    if not runs:
        print(f"[seal] 没有可钉的 run 目录 (在 {ao}; 候选 {len(all_cand)} 个)")
        return 1

    lines, total = [], 0
    for r in runs:
        for f in sorted(r.iterdir()):
            if not f.is_file():
                continue
            rel = f"agent-out/{r.name}/{f.name}"
            lines.append(f"# {_u1_identity(rel)}")        # ★ u1 轨：**紧邻**在数据行之前（§1.4「每条之前一行」）
            lines.append(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {rel}")
            total += 1

    dst = entry / "30_evidence" / "MANIFEST.sha256"
    when = datetime.datetime.now().astimezone().isoformat()
    head = [
        _u1_decl_line(),                              # ★ 文件级**声明行**（§1.4「每文件首行」）：本清单带 u1 轨
        "# MANIFEST.sha256 — 30_evidence 交付证据束 (ADR-0008 §5.1)",
        "# 作用：钉住本次交付的证据件字节态 —— 证明「这一批产出就是这些」，且回收之后未被改动。",
        f"# 受理目录: inbox/{name}    项目根: {root}    交付分级: {grade}",
        f"# 生成时间: {when}    件数: {total}    run: {', '.join(r.name for r in runs)}",
        f"# 校验: 在项目根 ({root}) 下 `sha256sum -c {dst}`（忽略 # 行）; Windows 侧用 python 递归比对。",
        "# 重放语义: 本清单只支持「重放**验证**」(哈希/退出码/diff 白名单), "
        "不承诺「重放**生成**」逐位一致 (见 inbox/README §5.3)。",
    ]
    payload = "\n".join(head + lines) + "\n"

    print(f"[seal] 受理目录 : inbox/{name}")
    print(f"[seal] 项目     : {proj}  ->  {root}")
    print(f"[seal] 钉住 run : {', '.join(r.name for r in runs)}")
    print(f"[seal] 件数     : {total}    分级: {grade}")
    print(f"[seal] 目标     : {dst}")
    for ln in lines[:5]:
        print(f"         {ln}")
    if total > 5:
        print(f"         …另 {total - 5} 件")
    if not go:
        print("[seal] 以上为**计划**（未写文件）。确认无误后加 --go 落盘。")
        return 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    # ★ 2026-10-19 改 `write_text` → `write_bytes`：**行尾必须是 LF**（本次真跑实测抓出的缺陷）
    #   `Path.write_text(..., encoding=…)` 在 Windows 上会把 `\n` 翻成 `\r\n`，而 `sha256sum -c`
    #   把那个 `\r` 当成**文件名的一部分** ⇒ 逐条 `'agent-out/…/a.txt'$'\r': No such file or directory`
    #   → `FAILED open or read` → **exit 1** ⇒ 清单头自称的"`sha256sum -c` 应全 OK"**在 Windows 上不成立**
    #   （本仓既有 `00_handoff/MANIFEST.sha256` 同样是 CRLF ⇒ **预先存在**，不是本次引入；该件属**另案 `O-163`** —— 2026-10-20 以**甲**收口：**只就地更正其声明行、不动哈希行，见 `inbox/README.md` §5 的 Windows 口径**）。
    #   ⚠ python 侧消费者对两种行尾都容忍（`parse_manifest` 用 `splitlines()`）⇒ 影响**只在** CLI 那条路。
    dst.write_bytes(payload.encode("utf-8"))
    print(f"[seal] 已写入 {dst}（{len(payload)} 字节）。")
    _delivery = "/".join(s for s, sp in _inbox_truth().items()
                         if "manifest" in ((sp or {}).get("requires") or []))
    print(f"[seal] 提示: 交付态 ({_delivery}) 门禁要求本文件存在; 结案后本目录冻结。")
    return 0


def cmd_inbox(argv) -> int:
    """cluster.py inbox [seal ...]  — 受理区 dashboard / 交付证据束钉死。

    无参数 = 列出每笔目录 + 状态 + 更新时间（纯本地无站上依赖, ADR-0008）。
    `seal` 子命令见 `_inbox_seal`（ADR-0008 §5.1 交付证据束）。
    合法状态白名单与自洽判定在 rpc_check.py 的 inbox 断言 (quick)。
    """
    if argv and argv[0] == "seal":
        return _inbox_seal(argv[1:])
    if argv:
        print("用法: cluster.py inbox | inbox seal <proj-dir> [--run <ts>|--all-runs] "
              "[--grade Reproduced|Replicated] [--go]")
        return 1
    root = INBOX_ROOT
    if not root.is_dir():
        print("inbox/ 不存在")
        return 0
    rows = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        if d.name.startswith("_"):
            continue
        st, ts = "no-state", ""
        f = d / "40_state" / "STATE.json"
        if f.is_file():
            try:
                j = json.loads(f.read_text(encoding="utf-8"))
                st = j.get("state", "no-state")
                ts = j.get("updated_at", "")
            except Exception:
                st = "BAD-JSON"
        rows.append((d.name, st, ts))
    print(f"  {_pad('目录', 30)} {_pad('state', 26)} {'updated_at'}")
    for name, st, ts in rows:
        # D6-P3-1: 受理目录名可能是中文 ⇒ 按**显示宽度**填充（`state` 取值在白名单内 ⇒ 恒 ASCII）
        print(f"  {_pad(name, 30)} {_pad(st, 26)} {ts}")
    return 0


# ── containers: A 站容器栈纳管 (ADR-0012 D2 / ADR-0014 D2) ──────────────
# 唯一经统一管理面执行 docker 的入口 (ADR-0004 D2: 新能力加子命令, **不**新增并列脚本)。
# 纪律:
#   · status = 只读, **恒 exit 0**, 且空集必须**显式报「无容器」**(ADR-0012 D2 —— 本仓头号形态:
#     空集被读成"没问题" ⇒ 不许打印空);
#   · pull/up/down = 写动作, **默认 --plan**(只打印将下发的命令, **不连站**), --go 才动手;
#     计划与执行**同源**(都走 containers_plan) ⇒ 不出现"计划一套、执行另一套";
#   · 写动作 ssh_run(..., strict=True) —— 要**远端 rc==0** 才算成功(默认 ok 只表示"没抛异常")。
PORTS_YAML = REPO_ROOT / "inventory" / "ports.yaml"

# 站上探测块: 一次连接取三段。docker 缺席也要**可判**(DOCKER=absent), 不靠"空输出"反推。
_PROBE_CMD = (
    "if command -v docker >/dev/null 2>&1; then echo DOCKER=active; "
    "echo '===PS==='; docker ps -a --format '{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null; "
    "echo '===IMG==='; docker images --format '{{.Repository}}:{{.Tag}}\t{{.Size}}' 2>/dev/null; "
    "echo '===CMP==='; docker compose ls --format table 2>/dev/null; "
    "else echo DOCKER=absent; fi"
)


def docker_published_ports(ports_field: str) -> list:
    """`docker ps` 的 PORTS 列 → 已发布**宿主**端口列表(保序, 可重复)。

    docker 形态: `127.0.0.1:8731->8731/tcp, 0.0.0.0:8888->8080/tcp, :::8888->8080/tcp`。
    未发布(只有容器内口, 无 `->`)不计 —— 那些端口只在容器网络内, 不在宿主监听面。
    """
    out = []
    for tok in (ports_field or "").split(","):
        tok = tok.strip()
        if "->" not in tok:
            continue
        hp = tok.split("->", 1)[0].rsplit(":", 1)[-1].strip()
        if hp.isdigit():
            out.append(int(hp))
    return out


def parse_docker_ps(text: str) -> list:
    """`docker ps -a` 四列文本(names\\timage\\tstatus\\tports) → 行字典。空行/短行跳过。"""
    rows = []
    for ln in (text or "").splitlines():
        if not ln.strip():
            continue
        parts = ln.split("\t")
        if len(parts) < 4 or not parts[0].strip():
            continue
        rows.append({"name": parts[0].strip(), "image": parts[1].strip(),
                     "status": parts[2].strip(), "ports_raw": parts[3].strip(),
                     "host_ports": docker_published_ports(parts[3])})
    return rows


def parse_docker_images(text: str) -> list:
    """`docker images` 两列文本(ref\\tsize) → [{ref, size}]。空行/短行跳过。"""
    rows = []
    for ln in (text or "").splitlines():
        if not ln.strip():
            continue
        parts = ln.split("\t")
        if len(parts) < 2 or not parts[0].strip():
            continue
        rows.append({"ref": parts[0].strip(), "size": parts[1].strip()})
    return rows


def parse_containers_probe(text: str) -> dict:
    """站上探测块 → `{docker, ps, images, compose}`。`docker` ∈ active/absent/unknown。

    ★ unknown 与 absent **不同**: 前者 = 探测没给出结论(不假装"没装"), 后者 = 明确无 dockerd。
    """
    out = {"docker": "unknown", "ps": [], "images": [], "compose": []}
    section, buf = None, {"ps": [], "img": [], "cmp": []}
    for ln in (text or "").splitlines():
        s = ln.strip()
        if s == "DOCKER=active":
            out["docker"] = "active"; continue
        if s == "DOCKER=absent":
            out["docker"] = "absent"; continue
        if s == "===PS===":
            section = "ps"; continue
        if s == "===IMG===":
            section = "img"; continue
        if s == "===CMP===":
            section = "cmp"; continue
        if not s:
            continue
        if section:
            buf[section].append(ln)
    out["ps"] = parse_docker_ps("\n".join(buf["ps"]))
    out["images"] = parse_docker_images("\n".join(buf["img"]))
    # `docker compose ls --format table` **恒**先打一行表头（`NAME STATUS CONFIG FILES`）——
    #   项目集为空时**只**有表头 ⇒ 不过滤会把 0 个栈误报成 1 个（"看不见空集"的反向假阳；
    #   与 ADR-0012 D2"空集不许打印空"同一条纪律：既不许静默空，也不许**凭空有**）。
    #   过滤判据 = 该行空白分词恰为表头四列（比扫列宽稳，且真项目名不会恰叫 NAME+STATUS+CONFIG+FILES）。
    _CMP_HEADER = ["NAME", "STATUS", "CONFIG", "FILES"]
    out["compose"] = [x.strip() for x in buf["cmp"]
                      if x.strip() and x.split() != _CMP_HEADER]
    return out


def registered_host_ports(table: dict) -> dict:
    """`ports.yaml` 解析结果 `{group:[entry]}` → `{port_int: "group/port"}`。

    只收**具体端口**条目(`port:` 为 int); **段位形态**(`owner`+`range`, 见 `O-158` 甲)
    **不**进集合 —— 它的覆盖靠 `rpc_check._reg_covers`, 不是"某个具体端口"。"""
    out = {}
    for group, entries in (table or {}).items():
        if not isinstance(entries, list):
            continue
        for e in entries:
            if isinstance(e, dict) and isinstance(e.get("port"), int):
                out.setdefault(e["port"], f"{group}/{e['port']}")
    return out


def _ports_yaml() -> dict:
    """读 `inventory/ports.yaml` → `{group:[entry]}`(缺文件回 `{}`; 与 `rpc_check` 同源, 不抄一份)。"""
    import yaml
    if not PORTS_YAML.is_file():
        return {}
    doc = yaml.safe_load(PORTS_YAML.read_text(encoding="utf-8")) or {}
    return {g: v for g, v in doc.items() if isinstance(v, list)}


def containers_port_audit(published_by_station: dict, registered: dict) -> list:
    """容器**已发布宿主端口** vs 真值表 → 未登记的问题行(ADR-0012 D3 的口径)。

    ⚠ 只做"**容器声明面 ↔ 真值表**"; 站上**监听占用**对账的权威仍是 `rpc_check` 的 `ports` 断言
    ⇒ 本条**不复刻**其站上扫描(不造第二份真值)。"""
    issues = []
    for st in sorted(published_by_station):
        for p in sorted(set(published_by_station[st])):
            if p not in registered:
                issues.append(f"{st} 站容器已发布宿主端口 {p} **未**在 inventory/ports.yaml 登记")
    return issues


def format_containers_station(st: str, info: dict) -> list:
    """单站容器信息 → 文本行。**空集必须显式报「无容器」**(ADR-0012 D2)。"""
    lines = [f"=== {st} 站 ==="]
    docker = info.get("docker", "unknown")
    if docker == "absent":
        lines.append("  docker: 未安装（无 dockerd）—— 容器路径不适用")
        return lines
    lines.append(f"  docker: {docker}")
    ps = info.get("ps", [])
    if not ps:
        lines.append("  容器: 0 个 —— **无容器**（`docker ps -a` 空集, 非\"打印空\"）")
    else:
        lines.append(f"  容器: {len(ps)} 个")
        for r in ps:
            tail = f"  [{r['ports_raw']}]" if r.get("ports_raw") else ""
            lines.append(f"    - {r['name']}  {r['image']}  {r['status']}{tail}")
    imgs = info.get("images", [])
    lines.append("  镜像: 0 个" if not imgs else f"  镜像: {len(imgs)} 个")
    for r in imgs:
        lines.append(f"    - {r['ref']}  {r['size']}")
    cmp_ = info.get("compose", [])
    lines.append("  compose 栈: 无" if not cmp_ else f"  compose 栈: {len(cmp_)} 个")
    for c in cmp_:
        lines.append(f"    - {c}")
    return lines




# ── dockerd 供应 (ADR-0014 D8(a))：B/C 复用 A 站容器栈 ──────────────
# B/C 站上 docker **CLI** 已在（随 docker-desktop / docker-ce-cli 而来），缺的是
# **daemon + systemd unit**。供应 = 启用 docker apt 源（修 dist-upgrade 改名）+ 装
# docker-ce/containerd + 起 unit + 把 ssh 用户加进 docker 组（A 站 scott-lau 即在 docker 组）。
# ⚠ 幂等：已有 dockerd 且 docker active ⇒ 跳过。**默认 --plan**，--go 才动手（同 pull/up/down）。
_DOCKER_DAEMON_JSON = (
    "{\n"
    '  "registry-mirrors": [\n'
    '    "https://docker.1ms.run",\n'
    '    "https://docker.m.daocloud.io",\n'
    '    "https://mirror.ccs.tencentyun.com",\n'
    '    "https://docker.xuanyuan.me"\n'
    "  ]\n"
    "}"
)


def containers_install_cmd() -> str:
    """单站容器栈供应脚本（与 A 站配置对齐）。幂等；用 `docker info`（含 context 解析）自判。"""
    return (
        "set -e; U=$(id -un); "
        # ★ 对齐 A 站: context=default。B 站实测 CLI 的 currentContext=desktop-linux
        #   指向未启的 ~/.docker/desktop/docker.sock ⇒ docker 全废（A/C 均是 default）。
        "docker context use default >/dev/null 2>&1 || true; "
        "if command -v dockerd >/dev/null 2>&1 && systemctl is-active docker >/dev/null 2>&1 "
        "&& docker info >/dev/null 2>&1; "
        "then echo 'ALREADY: dockerd + docker active(ctx=default) — 跳过'; exit 0; fi; "
        # ★ 站上实测形态：docker apt 源被 dist-upgrade 改名成 .distUpgrade ⇒ 恢复
        "if [ ! -e /etc/apt/sources.list.d/docker.sources ] && "
        "[ ! -e /etc/apt/sources.list.d/docker.list ] && "
        "[ -e /etc/apt/sources.list.d/docker.list.distUpgrade ]; then "
        "sudo mv /etc/apt/sources.list.d/docker.list.distUpgrade "
        "/etc/apt/sources.list.d/docker.list; echo 'REPO: restored docker.list (from .distUpgrade)'; fi; "
        "sudo apt-get update -qq || echo 'WARN: apt-get update 有报错(容忍, 继续)'; "
        "sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y "
        "docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin; "
        "sudo systemctl enable --now docker; "
        'sudo usermod -aG docker "$U"; '
        f"printf '%s\\n' '{_DOCKER_DAEMON_JSON}' | sudo tee /etc/docker/daemon.json >/dev/null; "
        "sudo systemctl restart docker; "
        "docker context use default >/dev/null 2>&1 || true; "
        "echo \"OK: $(command -v dockerd) | $(docker --version) | $(docker info 2>&1 "
        "| grep -m1 -i 'Server Version' || echo 'info: FAIL')\""
    )


def _containers_status(stations) -> int:
    """只读一屏: 三站 docker ps -a / images / compose ls + 端口对账。**恒 exit 0**(只读观测)。"""
    pub = {}
    for st in stations:
        ok, out = ssh_run(st, _PROBE_CMD)
        if not ok:
            print(f"=== {st} 站 ===")
            print(f"  [不可达] {out}")
            continue
        info = parse_containers_probe(out)
        for ln in format_containers_station(st, info):
            print(ln)
        pts = [p for r in info["ps"] for p in r["host_ports"]]
        if pts:
            pub[st] = pts
    try:
        reg = registered_host_ports(_ports_yaml())
    except Exception as e:
        print(f"\n[containers] ⚠ inventory/ports.yaml 解析失败({type(e).__name__}): {str(e)[:120]} —— 对账跳过")
        return 0
    issues = containers_port_audit(pub, reg)
    print()
    if not pub:
        print("[containers] 三站均无已发布端口 ⇒ 无须对账")
    elif issues:
        print("[containers] 端口对账（容器声明面 vs 真值表）:")
        for x in issues:
            print(f"  ⚠ {x}")
    else:
        print("[containers] 端口对账（容器声明面 vs 真值表）: 已发布宿主端口**全部**已登记 ✓")
    print("[containers] 注: 站上**监听占用**对账的权威 = `ops/rpc_check.py --only ports`（本条不替代）")
    return 0


def cmd_containers(argv) -> int:
    """cluster.py containers {status|pull|up|down} ...  —— 容器栈纳管 (ADR-0012 D2 / ADR-0014 D2)

    status          只读一屏 (三站 docker ps -a / images / compose ls + 端口对账), 恒 exit 0
    pull/up/down    写动作 —— **默认只出计划, --go 才动手**; 走 ssh_run(strict=True)
    """
    act = (argv[0].lower() if argv and not argv[0].startswith("-") else "status")
    if act not in ("status", "install", "pull", "up", "down"):
        print("用法: cluster.py containers {status|install|pull|up|down} [--station A|B|C] [--image <ref>] "
              "[--name <名>] [--publish host:cont]... [--group-add g]... [--device dev]... "
              "[--volume host:cont[:ro]]... [--env K=V]... [--ipc host] [--ulimit k=soft:hard]... "
              "[--timeout 秒] [--detach] [--log <path>] [--plan|--go]")
        return 1
    tail = argv[1:] if argv and not argv[0].startswith("-") else argv
    station = image = name = ipc = None
    timeout = log = None
    detach = False
    publish, group_add, device, volume, env, ulimit, go, i = [], [], [], [], [], [], False, 0
    # 多值 flag（各自可重复）与单值 flag 的**唯一**归属表 —— 与 containers_plan 的形参同名，
    #   避免"解析漏一个、计划少一段"（计划=执行的同源前提）。
    _multi = {"--publish": publish, "--group-add": group_add, "--device": device,
              "--volume": volume, "--env": env, "--ulimit": ulimit}
    while i < len(tail):
        a = tail[i]
        if (a in _multi or a in ("--station", "--image", "--name", "--ipc",
                                 "--timeout", "--log")) and i + 1 < len(tail):
            v = tail[i + 1]
            if a == "--station":
                station = v.upper()
            elif a == "--image":
                image = v
            elif a == "--name":
                name = v
            elif a == "--ipc":
                ipc = v
            elif a == "--log":
                log = v
            elif a == "--timeout":
                if not v.isdigit():
                    print(f"[containers] --timeout 需为整数秒: {v}")
                    return 1
                timeout = int(v)
            else:
                _multi[a].append(v)
            i += 2
            continue
        if a in ("--go", "--plan", "--detach"):
            if a == "--go":
                go = True
            elif a == "--detach":
                detach = True
            i += 1; continue
        print(f"[containers] 未知参数: {a}")
        return 1
    stations = [station] if station else ["A", "B", "C"]
    if act == "status":
        return _containers_status(stations)
    if act == "install":                       # ADR-0014 D8(a): B/C 复用 A 站容器栈(装 dockerd)
        cmd = containers_install_cmd()
        for st in stations:
            print(f"[containers] install @ {st} 站" + ("" if go else "   （计划 · --go 才下发）"))
            print(f"  $ {cmd}")
        if not go:
            print("  提示: 加 --go 执行（写动作默认只出计划）")
            return 0
        ok_all = True
        for st in stations:                    # 默认 600s: apt 拉 docker-ce/containerd 远超 SSH_TIMEOUT
            ok, out = ssh_run(st, cmd, timeout=(timeout or 600), strict=True)
            print(f"  {'✓' if ok else '✗'} install @ {st}")
            for ln in (out or "").strip().splitlines():
                print(f"      {ln}")
            ok_all = ok_all and ok
        return 0 if ok_all else 1
    try:
        plan = containers_plan(act, station=(station or "A"), image=image, name=name,
                               publish=publish, group_add=group_add, device=device,
                               volume=volume, env=env, ipc=ipc, ulimit=ulimit,
                               detach=detach, log=log)
    except ValueError as e:
        print(f"[containers] {e}")
        return 1
    where = station or "A"
    for p in publish:                      # ADR-0014 D4: 引擎协议无鉴权 ⇒ 只准 loopback
        if p.split(":", 1)[0] not in ("127.0.0.1", "localhost"):
            print(f"[containers] ⚠ publish `{p}` 宿主绑定非 loopback —— 引擎协议**无鉴权**"
                  f"（ADR-0014 D4），建议 127.0.0.1")
    print(f"[containers] {act} @ {where} 站" + ("" if go else "   （计划 · --go 才下发）"))
    for c in plan:
        print(f"  $ {c}")
    if not go:
        print("  提示: 加 --go 执行（写动作默认只出计划）")
        return 0
    ok_all = True
    for c in plan:
        # pull 可能是多 GB 镜像(耗时远超 SSH_TIMEOUT=8s 的 exec 上界) ⇒ 允许 --timeout 放宽;
        #   缺省仍走 SSH_TIMEOUT, 不改变既有短动作的行为。
        ok, out = ssh_run(where, c, timeout=(timeout or SSH_TIMEOUT), strict=True)
        print(f"  {'✓' if ok else '✗'} {c}")
        for ln in (out or "").strip().splitlines():
            print(f"      {ln}")
        ok_all = ok_all and ok
    return 0 if ok_all else 1


