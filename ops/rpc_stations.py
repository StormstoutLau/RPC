#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三站/基础设施类检查器（review-p2-split 8B-3；从 `rpc_check.py` 整段抽出，行为不变）：ports / plugins / impact / aliases / halogen / stations+LAN / engine / gates / usb4 / backend / models。"""
import argparse
import ast
import concurrent.futures
import fnmatch
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from rpc_common import (
    INVENTORY_DIR, ROOT, load_inventory,
)

# ── 断言 A6: 端口分配表自洽 (P1-4) ────────────────────────────────
# 目的: 让 inventory/ports.yaml 从"一份文档"变成"一份可断言的分配表"。
# 只做**表内自洽** (不碰站上, 故可进 quick 门禁); 站上占用对账在 stations 断言的 (g)。
#
# 为什么需要: 2026-09-15 首次做站上对账时暴露三类表本身的问题 ——
#   · 8090 登记为 "Beszel agent, scope [A, B]", 实际监听方是 B 站 beszel-hub
#     (A 站的 agent 是**出站**客户端, 不监听) → 分配表的 scope 与 owner 都会写错
#   · mountd/statd 的端口号被写死 (52591/53517/55723), 一天后全变 → 端口号不是真值
#   · 137/138/546/5353/3702/6665/724 等长期监听的系统端口从未登记 → 对账必红
INVENTORY_PORTS = INVENTORY_DIR / "ports.yaml"
VALID_SCOPE = {"master", "A", "B", "C"}
VALID_PROTO = {"tcp", "udp", "http", "https", "tcp+udp"}
VALID_MODE = {"always", "on_demand"}
# 内核临时端口段下界。三站实测 net.ipv4.ip_local_port_range = "32768 60999"。
# 该段端口随服务启动重分配 (NFS mountd/statd 即典型), 不能当作真值登记, 故对账豁免。
EPHEMERAL_MIN = 32768
ALL_STATIONS = ("A", "B", "C")


def _port_entries():
    """读 inventory/ports.yaml → {group: [entry, ...]}。

    文件不存在返回 {}; **解析失败抛异常** —— 刻意不吞:
    2026-09-15 实测教训 —— 初版把异常吞成 {} 后, 一个 `note:` 值的 YAML 语法错误
    让整张表变空, stations 断言随即报了 40+ 条"端口未登记"的**假象**,
    真正的错因 (第 142 行) 完全看不到。真值表解析失败必须立刻炸出来。
    """
    if not INVENTORY_PORTS.is_file():
        return {}
    import yaml
    doc = yaml.safe_load(INVENTORY_PORTS.read_text(encoding="utf-8")) or {}
    return {g: v for g, v in doc.items() if isinstance(v, list)}


def _scopes(e):
    """条目适用的站列表。**无 scope = 三站通用** (unmanaged 里的系统端口多如此)。"""
    s = e.get("scope")
    return [str(x) for x in s] if s else list(ALL_STATIONS)


def check_ports(ctx):
    """纯表内自洽: 结构 / 唯一 / 跨组重叠 / 枚举 / expect_bind 具体性。"""
    if not INVENTORY_PORTS.is_file():
        return "WARN", "inventory/ports.yaml 缺失 (端口分配表未建)", []
    try:
        entries = _port_entries()
    except Exception as e:
        return "FAIL", f"ports.yaml 解析失败: {type(e).__name__}: {str(e)[:180]}", []
    if not entries.get("managed"):
        return "FAIL", "ports.yaml 无可解析的 managed 分组", []

    detail = []
    groups = ("managed", "third_party", "unmanaged", "deprecated")

    # (1) 结构完整性: managed 要求 purpose/scope/bind/owner 四件套
    #     (scope 是"按站对账"的前提, bind 是"暴露面"的前提; 缺任一项该行就不可断言)
    for g, req in (("managed", ("purpose", "scope", "bind", "owner")),
                   ("third_party", ("purpose", "owner", "scope"))):
        for e in entries.get(g) or []:
            if not isinstance(e, dict):
                continue
            miss = [k for k in req if not e.get(k)]
            if miss:
                detail.append(f"{g} :{e.get('port', '?')} 缺字段 {', '.join(miss)}")

    # (2) 同一端口不得在同一分组内出现两次 (后者覆盖前者 = 静默丢条目)
    for g in groups:
        seen = {}
        for e in entries.get(g) or []:
            if not isinstance(e, dict) or not isinstance(e.get("port"), int):
                continue
            seen.setdefault(e["port"], []).append(e)
        for p, lst in sorted(seen.items()):
            if len(lst) > 1:
                detail.append(f"{g} 内端口 {p} 重复 {len(lst)} 次 —— 后者会覆盖前者")

    # (3) 跨分组不得重叠 —— 这是"分配表"的核心约束: 一个端口同一时刻只属于一类。
    #     deprecated 也纳入: 已退役端口若又出现在在用分组, 说明退役不彻底/登记过期。
    owner_of = {}
    for g in groups:
        for e in entries.get(g) or []:
            if isinstance(e, dict) and isinstance(e.get("port"), int):
                owner_of.setdefault(e["port"], []).append(g)
    for p, gs in sorted(owner_of.items()):
        if len(set(gs)) > 1:
            detail.append(f"端口 {p} 同时登记在 {', '.join(sorted(set(gs)))} 两个分组 —— "
                          f"应只在其中一处 (在用的进 managed/third_party/unmanaged, "
                          f"退役的只留 deprecated)")

    # (3b) ★ 段位形态 (O-158 甲, 2026-10-10): `unmanaged` 里**无 `port` 有 `range`** 的条目 ——
    #     形态必须合法, 否则站上对账时它**静默变成"不覆盖"**(坏 range 匹配不上任何口),
    #     真因要到 stations 那一步才表现成"某口未登记"。故三件套在**门口**先判:
    #       range = [lo, hi] 两个整数且 lo ≤ hi · owner 非空 · bind 是 loopback
    #       (护栏「只覆盖 loopback + 已知 owner」的字面落点)。
    #     ⚠ 这类条目**不**参与 (2)(3) 的重复/重叠检查 —— 覆盖由"占用者是谁"决定, 与数字区间无关。
    for e in entries.get("unmanaged") or []:
        if not isinstance(e, dict) or isinstance(e.get("port"), int):
            continue
        rng = e.get("range")
        if rng is None:
            continue                    # 既无 port 又无 range 的注释性散条不判 (旧式, 无关覆盖)
        if not (isinstance(rng, (list, tuple)) and len(rng) == 2
                and all(isinstance(x, int) for x in rng) and rng[0] <= rng[1]):
            detail.append(f"unmanaged 段位条目 range={rng!r} 非法 —— "
                          f"须为 [lo, hi] 两个整数且 lo ≤ hi (见 O-158)")
            continue
        if not e.get("owner"):
            detail.append(f"unmanaged 段位条目 {rng!r} 缺 owner —— 段位形态的覆盖**必须有** "
                          f"owner 闸 (只覆盖 loopback + 已知 owner, 见 O-158)")
        if str(e.get("bind") or "") not in ("127.0.0.1", "::1"):
            detail.append(f"unmanaged 段位条目 {rng!r} 的 bind={e.get('bind')!r} 不是 loopback "
                          f"—— 护栏只允许覆盖 loopback (见 O-158)")

    # (4) 枚举合法性 —— 拼错 scope/proto/mode 会让对账**静默失效**
    #     (如 scope 写成 "a" 则不匹配任何站; mode 写成 "ondemand" 则豁免规则不生效)
    for g in ("managed", "third_party", "unmanaged"):
        for e in entries.get(g) or []:
            if not isinstance(e, dict):
                continue
            p = e.get("port", "?")
            for s in (e.get("scope") or []):
                if str(s) not in VALID_SCOPE:
                    detail.append(f"{g} :{p} 的 scope 含非法值 {s!r} (合法: "
                                  f"{'/'.join(sorted(VALID_SCOPE))})")
            if e.get("proto") and str(e["proto"]).lower() not in VALID_PROTO:
                detail.append(f"{g} :{p} 的 proto 非法 {e['proto']!r} "
                              f"(合法: {'/'.join(sorted(VALID_PROTO))})")
            if e.get("mode") and str(e["mode"]) not in VALID_MODE:
                detail.append(f"{g} :{p} 的 mode 非法 {e['mode']!r} "
                              f"(合法: {'/'.join(sorted(VALID_MODE))})")

    # (5) expect_bind 必须是**具体地址** —— 它的用途是断言"暴露面没超预期",
    #     写成 * 或 0.0.0.0 则断言恒真, 等于没写。
    for e in entries.get("managed") or []:
        exp = (e or {}).get("expect_bind")
        if exp and ("*" in str(exp) or str(exp).startswith("0.0.0.0")):
            detail.append(f"managed :{e.get('port')} 的 expect_bind={exp!r} 不是具体地址, "
                          f"该断言会恒真")

    n_ports = len([1 for e in entries.get("managed") or []
                   if isinstance(e, dict) and isinstance(e.get("port"), int)])
    note = (f"分配表: managed {n_ports} · third_party {len(entries.get('third_party') or [])} · "
            f"unmanaged {len(entries.get('unmanaged') or [])} · "
            f"deprecated {len(entries.get('deprecated') or [])} · "
            f"dynamic {len(entries.get('dynamic') or [])}")
    if detail:
        return "FAIL", note, detail
    return "PASS", note, []


# ── 断言 A7: 插件/技能三站同构基线 (P1-5) ─────────────────────────
# 目的: 把 PLUGIN-LEDGER 的"三站完全同构"从**人工文字断言**改成可断言的真值。
# 为什么必须改: 2026-09-15 首次实测即推翻该结论 —— C 站 ARS 链的 25 个软链
# **全部是死链**(源目录 ~/tools/opencode-academic-research 在 C 站不存在), 而
# "只数软链个数"三站恰好都是 25, 手工核对显示"一致"。判据必须定在**可达性**上。
#
# 本断言(index)只做**纯本地**部分(可进 quick 门禁):
#   · items 结构自洽: id 唯一非空 / kind 合法 / expect 类型与 kind 匹配
#   · local_sources 对账: 仓库侧源(ops/agent-skills/*/SKILL.md)的名字集合必须
#     等于它所镜像的 item 的 expect —— 抓"仓库加了技能但没登记", 无需 ssh
#   · known_drift 必须指向存在的 item 与合法站, 且 extra 不得落在 expect 内
# 站上部分在 stations 断言的 (h) 子项 (复用同一次 ssh 往返)。
INVENTORY_PLUGINS = INVENTORY_DIR / "plugins.yaml"
PLUGIN_KINDS = {"scalar", "set", "count", "flag"}
PLUGIN_STATIONS = ("A", "B", "C")


def _plugins_doc():
    """读 inventory/plugins.yaml。文件缺失返回 {}; **解析失败抛异常**(同 ports)。"""
    if not INVENTORY_PLUGINS.is_file():
        return {}
    import yaml
    return yaml.safe_load(INVENTORY_PLUGINS.read_text(encoding="utf-8")) or {}


def _plugin_items(doc):
    """{id: item}。"""
    out = {}
    for it in doc.get("items") or []:
        if isinstance(it, dict) and it.get("id"):
            out[str(it["id"])] = it
    return out


def _plugin_scope(it):
    """item 适用的站; 无 scope = 三站通用。"""
    s = it.get("scope")
    return [str(x) for x in s] if s else list(PLUGIN_STATIONS)


def _plugin_diff(it, got):
    """把站上实得值与基线比对。返回 None=一致, 否则 (差异类, 明细)。

    set 类区分两种差异: ("extra", 只多出的元素) 与 ("diff", 明细) ——
    前者才有可能匹配 known_drift（已登记的多余项降 WARN），
    后者(少了元素/多出未登记元素)一律 FAIL。
    """
    kind, exp = it.get("kind"), it.get("expect")
    if kind == "count":
        try:
            return None if int(got) == exp else ("diff", [got, exp])
        except (TypeError, ValueError):
            return ("diff", [got, exp])
    if kind in ("scalar", "flag"):
        return None if got == exp else ("diff", [got, exp])
    if kind == "set":
        g = {x for x in str(got).split(",") if x}
        e = {str(x) for x in (exp or [])}
        if g == e:
            return None
        if not (e - g):
            return ("extra", sorted(g - e))
        return ("diff", [f"缺{sorted(e - g)}", f"多{sorted(g - e)}"])
    return ("diff", [f"未知 kind={kind!r}"])


def _plugin_src_names(path, glob):
    """仓库侧源的条目名。glob 形如 '*/SKILL.md' → 取条目所在目录名。"""
    files = sorted(path.glob(glob))
    names = set()
    for p in files:
        names.add(p.parent.name if len(p.parts) > len(path.parts) + 1 else p.name)
    return sorted(names)


def check_plugins(ctx):
    """纯本地: 基线结构自洽 + 仓库内源与登记值对账。"""
    if not INVENTORY_PLUGINS.is_file():
        return "WARN", "inventory/plugins.yaml 缺失 (插件同构基线未建)", []
    try:
        doc = _plugins_doc()
    except Exception as e:
        return "FAIL", f"plugins.yaml 解析失败: {type(e).__name__}: {str(e)[:180]}", []

    detail = []
    raw = [it for it in (doc.get("items") or []) if isinstance(it, dict)]
    items = _plugin_items(doc)

    # (1) 结构自洽
    dup = {}
    for i, it in enumerate(raw, 1):
        iid = it.get("id")
        if not iid:
            detail.append(f"items[{i}] 缺 id")
            continue
        dup[iid] = dup.get(iid, 0) + 1
        if it.get("kind") not in PLUGIN_KINDS:
            detail.append(f"{iid} 的 kind 非法 {it.get('kind')!r} "
                          f"(合法: {'/'.join(sorted(PLUGIN_KINDS))})")
        else:
            exp = it.get("expect")
            ok = (isinstance(exp, int) and not isinstance(exp, bool) if it["kind"] == "count"
                  else isinstance(exp, list) and bool(exp) and all(isinstance(x, str) for x in exp)
                  if it["kind"] == "set"
                  else isinstance(exp, str) and bool(exp) if it["kind"] == "scalar"
                  else exp in ("yes", "no"))
            if not ok:
                detail.append(f"{iid} 的 expect 与 kind={it['kind']} 不匹配: {exp!r}")
        if not it.get("purpose"):
            detail.append(f"{iid} 缺 purpose")
        for s in (it.get("scope") or []):
            if str(s) not in PLUGIN_STATIONS:
                detail.append(f"{iid} 的 scope 含非法站 {s!r}")
    for iid, n in sorted(dup.items()):
        if n > 1:
            detail.append(f"item id {iid!r} 重复 {n} 次 —— 后者会覆盖前者")
    if not items:
        detail.append("items 为空 —— 该断言需要基线才能工作")

    # (2) 仓库内源 → 登记值对账 (本地就能抓"加了技能没登记")
    for src in doc.get("local_sources") or []:
        if not isinstance(src, dict):
            continue
        name = src.get("name") or "?"
        mirrors = src.get("mirrors")
        path = ROOT / str(src.get("path") or "")
        glob = str(src.get("glob") or "*/SKILL.md")
        if mirrors not in items:
            detail.append(f"local_sources/{name} 的 mirrors={mirrors!r} 在 items 中不存在")
            continue
        if not path.is_dir():
            detail.append(f"local_sources/{name} 的路径不存在: {src.get('path')}")
            continue
        exp = items[mirrors].get("expect")
        if not isinstance(exp, list):
            detail.append(f"local_sources/{name} 镜像的 {mirrors} 不是 set 类, 无法对账")
            continue
        got = _plugin_src_names(path, glob)
        if got != sorted(exp):
            detail.append(
                f"仓库源 {src.get('path')} 与基线 {mirrors} 不一致: "
                f"源 {len(got)} 项 / 基线 {len(exp)} 项; "
                f"仅在源 {sorted(set(got) - set(exp)) or '无'}; "
                f"仅在基线 {sorted(set(exp) - set(got)) or '无'}")

    # (3) known_drift 自洽
    for kd in doc.get("known_drift") or []:
        if not isinstance(kd, dict):
            continue
        tag = f"known_drift({kd.get('station')}/{kd.get('id')})"
        if kd.get("id") not in items:
            detail.append(f"{tag} 指向不存在的 item")
        if str(kd.get("station")) not in PLUGIN_STATIONS:
            detail.append(f"{tag} 的 station 非法")
        if not kd.get("note"):
            detail.append(f"{tag} 缺 note (登记必须写明原因)")
        extra, exp = kd.get("extra"), (items.get(kd.get("id")) or {}).get("expect")
        if isinstance(extra, list) and isinstance(exp, list):
            inside = [x for x in extra if x in exp]
            if inside:
                detail.append(f"{tag} 的 extra 里有本就属于 expect 的元素 {inside} —— "
                              f"extra 只应列**多余项**")

    n_drift = len([k for k in (doc.get("known_drift") or []) if isinstance(k, dict)])
    note = (f"基线 {len(items)} 项 · 本地源 {len(doc.get('local_sources') or [])} 个 · "
            f"已登记漂移 {n_drift} 项")
    if detail:
        return "FAIL", note, detail
    return "PASS", note, []


# ── 断言 A?: 影响面反查表 (CI/CD Layer 3) ─────────────────────────
# inventory/impact.yaml 登记"每个模型/端口/配置被谁消费"。此断言保证:
#   (a) impact.yaml 存在且 YAML 合法
#   (b) 登记的每个 consumer 路径真实存在 (防"登记即漂移" —— 登记了却指向不存在的地方)
def check_impact(ctx):
    p = INVENTORY_DIR / "impact.yaml"
    if not p.is_file():
        return "WARN", "inventory/impact.yaml 缺失 (影响面反查表未建)", []
    try:
        import yaml
        doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return "FAIL", f"impact.yaml 解析失败: {type(e).__name__}: {e}", []
    missing = []
    checked = 0
    for section in ("models", "ports", "configs"):
        if section not in doc or not isinstance(doc[section], dict):
            continue
        for key, meta in doc[section].items():
            for c in (meta or {}).get("consumers", []):
                if not isinstance(c, str) or not c.strip():
                    continue
                checked += 1
                target = c.split(":", 1)[1] if c.startswith(("file:", "doc:")) else c
                if not (ROOT / target).exists():
                    missing.append(f"{section}/{key} → {c}  不存在")
    note = f"impact.yaml: {len(doc.get('models', {}))} 模型 / {len(doc.get('ports', {}))} 端口 / " \
           f"{len(doc.get('configs', {}))} 配置 · 校验 {checked} 条 consumer"
    if missing:
        return "FAIL", note, missing
    return "PASS", note, []


# ── 断言 A4: 别名解析契约 (回归护栏) ──────────────────────────────
# 为什么门禁要管这个 (2026-09-14):
#   刚修的 bug 是 cluster.py 的 ROUTE 键写成了缩写 (旧值 `qwen3.8-27b`, 站上真实别名
#   是 `qwen3.8-27b-mtp`)。因 resolve_alias 只做单向前缀匹配, 用户输入站上真实别名时
#   匹配失败 → 静默落到 DEFAULT_STATION → **加载到错误的站**, 且 B 站恰有同名 conf
#   故全程不报错。改数据只能修这一次; 故把 resolve_alias 的**契约**钉进门禁:
#     · 每个 ROUTE 键精确命中自己 (how=exact)
#     · 每个 RPC_MODELS 条目走 rpc 分支
#     · **任何 ROUTE 键的前缀都不得静默落默认站** (这正是缺陷类)
#     · 不存在的别名必须显式标 how=default
#     · 多个候选必须抛 AliasError, 不得静默取首个
#   断言**自更新**: 从 cluster 的常量派生用例, 不硬编码 ROUTE 内容。


def check_aliases(ctx):
    sys.path.insert(0, str(ROOT / "ops"))
    try:
        import cluster
    except Exception as e:
        return ("WARN",
                f"无法导入 cluster.py ({type(e).__name__}: {e}) — 该项需 paramiko; "
                f"请用装有 paramiko 的 Python 运行", [])

    detail, warn, n = [], [], 0

    # (1) ROUTE 键精确命中自己
    for key, st in cluster.ROUTE.items():
        n += 1
        got = cluster.resolve_alias(key)
        if got != (st, key, key in cluster.RPC_MODELS, "exact"):
            detail.append(f"ROUTE 键 {key!r} 未精确命中: 实得 {got}")

    # (2) RPC_MODELS 走 rpc 分支
    for m in sorted(cluster.RPC_MODELS):
        n += 1
        got = cluster.resolve_alias(m)
        if got != (None, m, True, "rpc"):
            detail.append(f"RPC_MODELS {m!r} 未走 rpc 分支: 实得 {got}")

    # (3) 核心不变式 (**双向**): 无论输入是 ROUTE 键的前缀, 还是它的**更长变体**,
    #     都不得静默落默认站。
    #     ⚠ 第一版护栏只测了"前缀"方向, 因而对本次真实 bug 无感 —— 真实方向恰恰相反:
    #       输入是站上真实别名 `qwen3.8-27b-mtp`, 而 ROUTE 键是缩写 `qwen3.8-27b`。
    #       注入旧值复验时护栏 PASS, 才发现测错了方向, 遂补上更长变体方向。
    for key in cluster.ROUTE:
        frags = [key[:cut] for cut in (len(key) - 1, max(2, len(key) // 2))
                 if 2 <= cut < len(key)]
        frags.append(key + "-mtp")            # 更长变体 (贴近真实别名形态)
        for frag in frags:
            n += 1
            try:
                _, _, _, how = cluster.resolve_alias(frag)
            except cluster.AliasError:
                continue                      # 明确报错 = 可接受 (不静默)
            if how == "default":
                detail.append(f"{frag!r} (来自 ROUTE 键 {key!r}) 静默落默认站 "
                              f"—— 要防的缺陷类: 用户输入更完整的别名会被送到错误的站")

    # (4) 不存在的别名必须显式标 default
    n += 1
    bogus = "__no_such_alias_xyz__"
    if cluster.resolve_alias(bogus) != (cluster.DEFAULT_STATION, bogus, False, "default"):
        detail.append(f"未知别名 {bogus!r} 未显式落到 default")

    # (5) 歧义必须报错 (打桩 ROUTE 制造共享前缀, 事后还原)
    # ★ 2026-10-28（评审 #8 拆 cluster.py）：`resolve_alias` 已搬进 `cluster_runtime`，
    #   它读的是**该模块**的 `ROUTE` ⇒ 只改 `cluster.ROUTE` 打不中（实测：判据假红"歧义未报错"）。
    #   ⇒ 直接改函数**定义处**的全局（`__globals__`），同时同步门面别名以保持外部视图一致。
    g = getattr(cluster.resolve_alias, "__globals__", {})
    snap = g.get("ROUTE", cluster.ROUTE)
    facade_snap = cluster.ROUTE
    try:
        g["ROUTE"] = {"__amb-a__": "A", "__amb-ab__": "B"}
        cluster.ROUTE = g["ROUTE"]
        n += 1
        try:
            cluster.resolve_alias("__amb-a")
            detail.append("歧义输入未报错 (静默取首个候选 = 会误路由)")
        except cluster.AliasError:
            pass
    finally:
        g["ROUTE"] = snap
        cluster.ROUTE = facade_snap

    # (6) inventory 里声明了 route 的别名, 必须真的路由到该站
    #     —— 这条才直接抓得住"路由键过期"的原始 bug: 旧值 qwen3.8-27b 时,
    #        解析站上真实别名 qwen3.8-27b-mtp 会报错/落错站, 与 inventory 的声明矛盾。
    _, models = load_inventory()
    for alias, meta in sorted((models or {}).items()):
        if alias != meta.get("alias") or not meta.get("route"):
            continue
        n += 1
        rt = meta["route"]
        try:
            st, _, _, how = cluster.resolve_alias(alias)
        except cluster.AliasError as e:
            detail.append(f"inventory 声明 {alias!r} -> {rt} 站, 但解析报错: {e}")
            continue
        if st != rt:
            detail.append(f"inventory 声明 {alias!r} -> {rt} 站, 实际解析为 {st} 站 (how={how})")

    # (7) 按站路由名 <-> inventory 的 conf 声明 双向一致
    #     · 路由名指向的 (station, 别名) 必须已声明有 conf (FAIL) —— 防止路由名指向一个站上不存在的东西
    #     · inventory 有 conf 的组合应配一个按站路由名 (WARN) —— 保证"能加载的都点得出来"
    declared_conf, declared_stations = set(), set()
    for alias, meta in (models or {}).items():
        if alias != meta.get("alias") or meta.get("_group") == "non_model_conf":
            continue    # non_model_conf (如 rpc-nodes 读的 nodes.env) 不是可加载模型, 不该有按站路由名
        for st in (meta.get("conf") or []):
            declared_conf.add((str(alias), st))
        for st in (meta.get("stations") or []):
            declared_stations.add((str(alias), st))
    # ★ 2026-10-25 (O-138 方案乙): "可加载"有两种后端 ——
    #   ① 站上有 llama.cpp conf（原判据）；② 该别名有 **halogen 容器配方**（CONTAINER_MODELS，
    #   三站通用）。生产全切 halogen 后 A/B 不再保留 conf ⇒ 只认 conf 会把 -a/-b 判成假红
    #   （实测：`conf: [C]` 时先红在本行，随后放宽到"容器配方也算可加载"）。
    #   ⚠ 只放宽"后端存在性"这一半：路由名仍须指向真实别名（real 有配方 = 站上可加载）。
    # ★ 2026-10-26 (T14): 容器配方只证明"站上能加载"，不证明"该站有模型库条目"。
    #   再补一层 stations 声明校验：有配方但 inventory 未声明该站 ⇒ 站上大概率没权重，
    #   加载会走到预检才失败。提前在门禁里点名（区分"无配方"与"未声明"两种缺口）。
    container_backed = set(getattr(cluster, "CONTAINER_MODELS", None) or {})
    for name, (st, real) in sorted(cluster.STATION_ROUTES.items()):
        n += 1
        if (real, st) in declared_conf:
            continue
        if real not in container_backed:
            detail.append(f"按站路由名 {name!r} -> ({st}, {real!r}), 但 inventory/models.yaml "
                          f"未声明 {real} 在 {st} 站有 conf（且该别名无 halogen 容器配方）")
        elif (real, st) not in declared_stations:
            detail.append(f"按站路由名 {name!r} -> ({st}, {real!r}) 有容器配方，"
                          f"但 inventory/models.yaml 未声明 {real} 在 {st} 站有模型库条目 "
                          f"(stations 字段)")
    named = {(real, st) for _, (st, real) in cluster.STATION_ROUTES.items()}
    gap = declared_conf - named
    if gap:
        warn.append("inventory 声明有 conf 但缺按站路由名: " +
                    ", ".join(f"{a}@{s}" for a, s in sorted(gap)))

    note = f"别名解析契约 {n} 例"
    if detail:
        return "FAIL", note, detail + [f"(WARN) {w}" for w in warn]
    if warn:
        return "WARN", note, warn
    return "PASS", note, []


# ── 断言 A4b: 容器模型资产预检 (P2, 慢, 非 quick, 2026-10-26) ─────────────
# 为什么新开而不是塞进 check_stations: 后者已承担 conf/权重/凭据/端口四类判据（DESIGN §5.6），
# 再塞容器资产会让"失败归因"变模糊；且它复用的是 conf 视角的 MODEL_PATH，看不见容器内路径。
def check_halogen_assets(ctx):
    """只读：容器配方声明的资产是否在站上就位（镜像 + 权重 + tokenizer）。

    ★ 站不可达 ⇒ **跳过并记 WARN**，不判 FAIL —— 未部署/掉线的站不该把门禁染红
      （与 Q2「不对未部署的站假红」一致）。跳过信息必须出现在 note/output 里，不得静默。
    """
    sys.path.insert(0, str(ROOT / "ops"))
    try:
        import cluster
    except Exception as e:
        return ("WARN", f"无法导入 cluster.py ({type(e).__name__}: {e})", [])

    _, models = load_inventory()
    declared = {}
    for alias, meta in (models or {}).items():
        if alias == meta.get("alias"):
            declared[str(alias)] = [str(s) for s in (meta.get("stations") or [])]

    detail, warn, n = [], [], 0
    for alias in sorted(cluster.CONTAINER_MODELS):
        for st in declared.get(alias, []):
            ok_h, out_h = cluster.ssh_run(st, "true", strict=True)
            if not ok_h:                      # 未部署/不可达 ⇒ 不判（避免假红）
                warn.append(f"{st} 站不可达，跳过 {alias} 资产预检: {str(out_h)[:80]}")
                continue
            n += 1
            pre = cluster.preflight_container(alias, st)
            if not pre["ok"]:
                detail.append(f"{st} 站 {alias}: " + "; ".join(pre["problems"]))
    note = f"容器资产预检 {n} 站例" + (f"（{len(warn)} 站例跳过）" if warn else "")
    if detail:
        return ("FAIL", note, detail)
    if warn:                                  # 跳过信息必须可见，不得静默丢在局部变量里
        return ("WARN", note, warn)
    return ("PASS", note, [])


# ── 断言 A5: 站上实况对账 (P2, 慢, 非 quick) ───────────────────────
# 把"站上实测"接进对账 —— 在此之前 inventory 只对账仓库内的声明源, 站上是否真的
# 与真值一致无从得知。三站各一次 ssh(合并命令), 做四件事:
#   (a) agent 配置 sha256 三站一致
#   (b) **路由键在目标站真实存在** —— 这条直接防住 §12 那个 bug 复发:
#       路由键过期(站上没这个别名) 会在这里立刻 FAIL, 而不是等用户 load 到错误的站
#   (c) conf 集合: inventory 声明的 conf 必须在站上存在 (缺 = FAIL);
#       站上有而 inventory 未声明 = WARN (可能是新模型/非模型条目, 不该阻断)
#   (d) bind 合规: inventory 里带 expect_bind 的端口, 若站上在监听则地址必须匹配
#   (e) **conf -> 权重存在性**: 每个 /etc/llama-instances/<alias>.env 里的 MODEL_PATH
#       必须真的存在 —— conf 在而权重没了 = load 必失败, 而这种事此前完全不可见。
#       已登记的缺失 (inventory/models.yaml 的 known_broken_conf) 记 WARN 不阻断, 但**新出现的
#       缺失会 FAIL** —— 避免"登记即遗忘"。2026-09-14 首跑即查出 2 处: glm-5.3-flash 与
#       qwen3.8-flash-next (后者还在 cluster.py 的 RPC_MODELS 里, 即被标为"可用"却加载不了)。
#
# 为什么模型侧只查 conf 与"点名几个路由键", 不做全量比对:
#   /etc/llama-instances/*.env 是**人工维护的命名集合**, 稳定可双向比对;
#   而 infer-list 反映模型库(下载即变), 全量比对必然天天误报 —— 故只做定点查询。
WATCHED = ["~/.config/opencode/opencode.jsonc", "~/.claude/settings.json"]

# 站上 LAN 地址采集命令 —— ★ **单一实现**：直连探针（本 STATION_CMD 的 [lanip] 段）与
#   USB4 降级通道（`_lanip_via_usb4` 经邻站中转）**共用同一条**，避免"同一事实两个定义点"。
#   · `scope global` 天然排除 `lo` 的 `scope host`（**不要**用 `grep -v lo` —— "global" 里就含 `lo`）；
#   · 整串**不含任何引号** ⇒ 可安全嵌进 `ssh <ip> "<cmd>"` 的双引号里（引号嵌套是本仓反复踩的坑）。
_LANIP_CMD = "ip -4 -o addr show scope global 2>/dev/null | cut -c1-160"

STATION_CMD = (
    "printf '\\n[cfg]\\n'; sha256sum " + " ".join(WATCHED) + " 2>/dev/null | cut -c1-16; "
    "printf '\\n[conf]\\n'; ls -1 /etc/llama-instances/*.env 2>/dev/null "
    "| xargs -r -n1 basename | sed 's/\\.env$//' | tr '\\n' ' '; echo; "
    "printf '\\n[bind]\\n'; ss -ltn 2>/dev/null | awk 'NR>1{print $4}' | tr '\\n' ' '; echo; "
    # (i) LAN 地址实况 (ADR-0006 v1.1 · D6, 2026-09-29): 站上**实际**的 global-scope IPv4。
    #   为什么必须从站上取（而不是像旧版那样只看 master 侧 `ssh -G` 的绑定）:
    #     旧判据的射程靠"别名"，C 站 `host: null` ⇒ **整站被跳过**，于是 2026-09-29 C 的
    #     LAN 由 .37 漂到 .8 时，门禁只报"可达 2/3 站"、**给不出根因**。
    #   ⚠ 本段**不新增连接** —— 搭在同一次合并 ssh 上（与 [bind]/[conf] 同源）。
    "printf '\\n[lanip]\\n'; " + _LANIP_CMD + "; "
    # UDP 侧单独一段 (P1-4): 系统里长期监听的 UDP 端口并不少 (nmbd/avahi/NetworkManager/
    # wsdd/netconsole/rpc.statd), 只查 TCP 会让它们对账时"看不见"。
    "printf '\\n[ubind]\\n'; ss -lun 2>/dev/null | awk 'NR>1{print $4}' | tr '\\n' ' '; echo; "
    # ★ 占用者身份面 (O-158 甲, 2026-10-10): 段位形态条目 (`unmanaged` 里无 `port`、有 `owner`+`range`)
    #   的第三道闸要判"这个口是不是登记的 owner 占的" ⇒ 必须取"监听口 → 占用者名"。
    #   为什么必须 sudo: 非 root 的 `ss -p` 只显示**本用户**的进程, 而 rpc.statd 这类系统服务
    #   跑在 root 下 (实测三站 `sudo -n` 均可非交互用, 2026-10-10)。⚠ 取不到 (sudo 失败等) ⇒
    #   门禁侧 **fail-closed**: 段位条不覆盖 ⇒ 该口照常报"未登记"并点名"占用者取数缺失"
    #   (判不了 ≠ 通过)。⚠ 原始行**不裁剪** (门禁侧只解析一次; 第 4 列 = addr:port, 行尾含
    #   users:(("名",pid=..,fd=..)))。
    "printf '\\n[towner]\\n'; sudo -n ss -ltnp 2>/dev/null; "
    "printf '\\n[uowner]\\n'; sudo -n ss -lunp 2>/dev/null; "
    # 插件面事实 (P1-5): 由站上工具一次性汇报 `id=value` 行, 判定留在门禁侧。
    # 不把采集逻辑内联在这里 —— JSONC 解析 + 目录遍历 + 软链可达性判断用 shell
    # 单行串写会变成转义地狱, 且三站口径无法保证一致。
    "printf '\\n[plug]\\n'; plugin-probe 2>/dev/null || true; "
    "printf '\\n[mpath]\\n'; for f in /etc/llama-instances/*.env; do [ -e \"$f\" ] || continue; "
    "a=${f##*/}; a=${a%.env}; "
    "CG=$(command -v conf-get 2>/dev/null || echo /usr/local/bin/conf-get); "
    "p=$(\"$CG\" \"$f\" MODEL_PATH 2>/dev/null); rc=$?; "
    "if [ \"$rc\" -ne 0 ] || [ -z \"$p\" ]; then echo \"$a NO_MODEL_PATH\"; "
    "elif [ -f \"$p\" ]; then echo \"$a OK\"; else echo \"$a MISSING $p\"; fi; done; "
    # (f) 凭据引用完整性 —— 2026-09-14 补: 起因是把 B/C 的 apiKeyHelper 抄进 A 站 settings.json
    # 时**没有把被引用的 claude-key.sh 一起部署**, 而所有断言都只看"配置文件是否一致",
    # 没有任何一条检查"被引用的文件是否存在"。此段专门堵这个盲区。
    "printf '\\n[cred]\\n'; "
    "HB=$(grep -o '\"apiKeyHelper\"[^,}]*' ~/.claude/settings.json 2>/dev/null | head -1 "
    "| sed 's/.*\"\\([^\"]*\\)\"$/\\1/'); "
    "if [ -z \"$HB\" ]; then echo 'helper=UNCONFIGURED'; "
    "elif [ ! -e \"$HB\" ]; then echo \"helper=MISSING:$HB\"; "
    "elif [ ! -x \"$HB\" ]; then echo \"helper=NOEXEC:$HB\"; "
    "else OUT=$(\"$HB\" 2>/dev/null | tr -d '\\n'); "
    "if [ -n \"$OUT\" ]; then echo \"helper=OK:${#OUT}\"; else echo \"helper=EMPTY:$HB\"; fi; fi; "
    "for P in $(grep -o '{file:[^}]*}' ~/.config/opencode/opencode.jsonc 2>/dev/null | sed 's/{file://;s/}//'); do "
    "Q=$(echo \"$P\" | sed \"s|~|$HOME|\"); "
    "if [ -s \"$Q\" ]; then echo \"ocfile=OK:$(basename \"$Q\")\"; else echo \"ocfile=BAD:$P\"; fi; done; "
    # 2026-09-16 (A) 判据升级: 原为「claude.key vs unsloth.key 两个文件互相比较」。实测该判据
    # 背后藏着结构缺陷 —— claude.key 是引擎 key 的第二份拷贝而**没有任何写入方** (infer-load
    # 每次加载只重铸落盘 unsloth.key), 于是它必然陈旧: C 站遗留脱敏占位串, A/B 只是靠人工
    # 同步过一次才对上, 且**下次加载即变黄**。改为比较「apiKeyHelper 的实际输出 vs 同站引擎
    # key」—— 这才是功能判据 (claude 真正拿到的 key), 且单一真值就是 unsloth.key。
    # helper 不可用时输出 SKIP (该情形已由上面 helper=EMPTY/MISSING/NOEXEC 报出, 不重复告警)。
    "UK=$(cat ~/.config/rpc/unsloth.key 2>/dev/null | tr -d '\\n'); "
    "if [ -z \"$OUT\" ]; then echo 'claudekey=SKIP_NO_HELPER'; "
    "elif [ \"$OUT\" = \"$UK\" ]; then echo 'claudekey=HELPER_EQ_UNSLOTH'; "
    "else echo 'claudekey=DIFFERS'; fi; "
    # (f2) unsloth studio 日志的明文面 (2026-09-16 增补): studio 每次加载都会把引擎 key 写进
    # ~/.unsloth/run-<alias>.log (实测每次 4 处), 而 infer-load 正是**从该日志 grep 取 key** ⇒
    # "日志含 key" 是设计使然、无法消除, 所以判据只能落在**权限**上:
    #   ~/.unsloth 须 700, run-*.log 须 600 (默认 umask 022 下是 775/664 ⇒ 组与其他用户可读)。
    # 顺带报"含 key 的日志份数 + 总份数", 供评估存量(实测三站曾累积 16 个历史 key / 64 处明文)。
    "DP=$(stat -c %a $HOME/.unsloth 2>/dev/null || echo NA); "
    "LF=$(ls -1 $HOME/.unsloth/run-*.log 2>/dev/null | wc -l); "
    "LK=$(grep -lE 'sk-(or-v1|unsloth|RPC|local|lm)-[A-Za-z0-9_-]{6,}' $HOME/.unsloth/run-*.log 2>/dev/null | wc -l); "
    "LL=$(find $HOME/.unsloth -maxdepth 1 -name 'run-*.log' ! -perm 0600 2>/dev/null | wc -l); "
    "echo \"unslothlog=dirperm:${DP} files:${LF} withkeys:${LK} loose:${LL}\"; "
    # (h) 长龄 orphan 探针 (O-58, 2026-09-25): 站上 ad-hoc ssh 探针/派发留下的僵尸/长龄进程。
    #   起因(一手实测): B 站留了 2 条 —— `bash` 1-12:19 与 `bash`+**活着的裸 `opencode`**
    #   1-04:59(47 fd、持**共享** `opencode.db` 180MB)；根因是**未加引号的 `|`** 被远端 shell
    #   当管道(纪律 12)。该信号此前**只能靠人肉 `ps` 偶然撞见** ⇒ 本段把它变机判。
    #   ⚠ 模式**不带空格**且用**多枚 `-e`**：带空格的引号经 PS/ssh 会被剥掉，远端 shell 会把
    #     模式后半当**文件名**(纪律 12, 实测 `grep: run: 没有那个文件或目录`)。
    #   只输出 `pid ppid etimes comm` 四列，**阈值与豁免全留在门禁侧**(与 [conf]/[mpath] 同分工)。
    "printf '\\n[orph]\\n'; ps -eo pid=,ppid=,etimes=,comm= 2>/dev/null "
    "| grep -e opencode -e claude -e timeout -e defunct | head -20; "
    # (i) O-70 第二类: 白名单**之外、但是我们自己的**残留（2026-09-25）—— **只报数, 不判定**。
    #   为什么需要: (h) 的白名单只认 4 个 comm ⇒ 实测那条**真孤儿**(`bash /tmp/agent-cli-task-*.sh`
    #     + 它的 `sleep` 子壳, 存活 **28.6h**, 见台账 O-72)**完全不在白名单里** ⇒ 只因人肉 `ps` 才发现
    #     = b3 说的"**在路灯下找钥匙**"。
    #   ⚠⚠ 第一版按 `ps -u $USER --ppid 1` 取 —— **实测两处都不成立**:
    #     ① 在一台桌面机上它抓到 **122 条系统守护**(`systemd-journald`/`udevd`/`avahi-daemon`…, 全是 **root**)
    #        ⇒ 说明 `$USER` 在**非登录 ssh 会话**里可能为空 ⇒ `-u` 过滤**静默失效**（纪律 12 同族: 别赌远端变量在）;
    #     ② 即便过滤对了, 桌面用户的 `ppid=1` 也天然包含 `systemd --user` 等**合法**长龄进程 ⇒ 恒有噪声。
    #   ⇒ 改成按**产物名**匹配(args 里出现我们自己的脚本名): 这是"事实"判据、噪声面小得多,
    #     且**正好**覆盖 O-72 那一类。阈值仍留在门禁侧(下面按 `ORPHAN_SEC` 判)。
    # ★★ 2026-09-26 结构性修法：**按 pgid 排除探针自己的整个进程组**（不再靠文本巧合）。
    #   起因（本轮实测）：直查时用 `pgrep -af agent-cli-task …` ⇒ **它自匹配了自己所在的命令行**
    #     ⇒ 说明"自匹配"是这条探针的**真实**风险，不是理论风险。
    #   旧版靠 `grep -v -e grep` 恰好挡住（自匹配行里也含 `grep` 一词）—— **侥幸成立**，
    #     代价是：**任何 args 里含子串 `grep` 的真残留会被静默排掉**（"路灯下找钥匙"的第二个面）。
    #   ⚠ 我曾以为"把排除键换成 `ps -eo`"是正解 —— **三站实测证伪**：那样会漏掉
    #     `grep -e agent-cli-task …` **进程自己**（其 args 含 `agent-cli-task` 却不含 `ps -eo`）⇒ 假阳性 1 行。
    #   ⇒ 现改为：`ps` 多输出一列 pgid + `awk` 剔除 `$2 == 自身 pgid`。
    #     shell / ps / grep / awk **同属一个进程组** ⇒ 一次全剔，**不依赖任何模式串**。
    #   ★ 实测对照（三站，注入假残留前后）：
    #       无残留 ⇒ **NEW 0 行**（旧版 0 行 / NAIVE 1 行假阳性）；有真残留 ⇒ **NEW 1 行，且只有真的那条**。
    #   ⚠ awk 把 pgid 列清空 ⇒ 输出行多一个空格；门禁侧用 `line.split()` 解析 ⇒ 不受影响（已实测）。
    "printf '\\n[orph2]\\n'; ps -eo pid=,pgid=,etimes=,args= 2>/dev/null "
    "| awk -v pg=$(ps -o pgid= -p $$ | tr -d ' ') '$2!=pg { $2=\"\"; print }' "
    "| grep -e agent-cli-task -e agent-stage- -e _oc_session_meta -e _p3_run -e _station_ready -e _slot_gate "
    "| head -20; "
)
# 刻意不取 infer-list: (1) 它自身约 10s+, 三站并行也要 30s+ (实测全量从 31s 涨到 60s);
# (2) 判定"别名在该站是否可用"本来就该看 conf —— infer-load 读的正是
#     /etc/llama-instances/<alias>.env, 模型库里有而 conf 没有的别名是 load 不了的。

SEC_RE = re.compile(r"^\[(\w+)\]$")


def _parse_sections(out):
    """按 [name] 分段解析远端合并命令的输出。"""
    sec, cur = {}, None
    for line in out.splitlines():
        m = SEC_RE.match(line.strip())
        if m:
            cur = m.group(1)
            sec[cur] = []
        elif cur is not None:
            sec[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in sec.items()}


def _ssh_g_hostname(alias):
    """`ssh -G <别名>` 的 hostname 字段 (**纯本地展开, 不建连**)。ssh 不可用返回 None。

    用于 ADR-0006 的 LAN 绑定对账: 名字是否仍被绑定到 net.yaml 登记的 LAN IPv4。
    """
    try:
        r = subprocess.run(["ssh", "-G", alias], capture_output=True, text=True,
                           timeout=20, encoding="utf-8", errors="replace")
    except Exception:
        return None
    for line in (r.stdout or "").splitlines():
        if line.lower().startswith("hostname "):
            return line.split(None, 1)[1].strip()
    return None


# ── LAN 地址对账（ADR-0006 v1.1 · D6，2026-09-29）──────────────────────────────
# 背景（一句话）：D4 的判据靠 `ssh -G <别名>`，于是 `host: null` 的 C 站**整站不在射程内**；
#   2026-09-29 C 的 LAN 由 .37 漂到 .8 时，6 项断言只报"可达 2/3 站"、**不给根因**
#   —— 正是 ADR-0006 D4 自己要消灭的那个"ssh 连不上的谜题"。
# 本节把判据换成"**站上实况** vs net.yaml 真值"，并在 LAN 不可达时**经 USB4 段向邻站中转**去问。
#
# 为什么判据与 IO **分开**：① 门禁侧只判不做 IO ⇒ **可先验红**（本仓纪律，见
#   tests/test_rpc_check_lan_drift.py）；② 直连与降级通道产出**同一种** `seen` ⇒ 判据只有一份。
def _local_lan_ip(probe_ip):
    """取**本机通往 probe_ip 那条路**上使用的源地址（= 本机的 LAN 管理面地址）。

    为什么用 UDP-connect 这个怪招：① **不发任何包**（UDP connect 只做路由选择），零流量、不打扰；
    ② 只用 stdlib（`ipconfig` 解析在中文 Windows 上字段名会变、且不可移植）；
    ③ 它回答的正是我们要问的问题 —— "**我用哪个地址去够那些站**"（而不是"本机一共配了哪些地址"）。
    失败返回 None（调用方按"无法判定"处理，**不猜**）。

    ★ 为什么主控也要判（2026-09-29 实测新增）：本轮排查中**主控自己的 LAN 先漂了**
      （`192.168.1.36` → `192.168.10.102`，整段换网），表现就是"三站全不可达" —— 又一个
      "可达 0/3 却不给根因"的谜题，且它比单站漂移**更彻底**（控制面全断）。
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((str(probe_ip), 9))
        return s.getsockname()[0]
    except Exception:
        return None
    finally:
        s.close()


def _parse_lanip(text):
    """解析 `ip -4 -o addr show scope global` 的原始输出 ⇒ [{iface, ip, cidr, dynamic}]。

    样例: `2: eno1    inet 192.168.1.8/24 brd 192.168.1.255 scope global dynamic noprefixroute eno1\\ ...`
    ⇒ 取行首的 `序号: 接口`、`inet <地址>/<前缀>`，并看整行里有没有 `dynamic`（DHCP）。
    ★ **这里也丢回环**（defense in depth）：真值源命令已用 `scope global` 过滤掉 `lo`，
      但**判据不该依赖调用方那半条 shell** —— 若将来有人动 `_LANIP_CMD`，`lo` 会变成
      "非 USB4 网段的唯一地址"而被误当成 LAN 地址。故解析层再过一遍。
    解析不出的行**忽略**（不猜）；全空 ⇒ 调用方走降级通道/报"无法判定"。
    """
    rows = []
    for ln in (text or "").splitlines():
        m = re.match(r"^\s*\d+:\s+(\S+)\s+inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)\s+(.*)$", ln)
        if not m or m.group(1) == "lo" or m.group(2).startswith("127."):
            continue
        rows.append({"iface": m.group(1), "ip": m.group(2),
                     "cidr": f"{m.group(2)}/{m.group(3)}",
                     "dynamic": "dynamic" in m.group(4)})
    return rows


def pick_lan_addr(rows, iface_hint, seg_nets):
    """从站上所有 global 地址里挑出**LAN 管理面**那一个。返回 ({...} | None, 原因串)。

    为什么需要挑：站上同时有 USB4 三段地址，都算 `scope global`。挑法（**先精后宽**）：
      ① 登记了 `iface` ⇒ **认接口**（最精确，且与 net.yaml 的声明同源）；
      ② 否则排除 USB4 各段的网段，剩下的**唯一**一个才算 LAN 地址；
      ③ 剩 0 个或多个 ⇒ **不猜**，返回原因（同本仓"解析失败不能表现成业务全错"纪律）。
      ④ ①命中但与②的候选集不一致（登记接口 ≠ 非 USB4 地址）⇒ 也返回原因 —— 那说明
         net.yaml 的 `iface` 与 `segments` 至少有一个是错的。
    """
    rows = rows or []
    lan_rows = [r for r in rows if not any(ipaddress.ip_address(r["ip"]) in n for n in (seg_nets or []))]
    if iface_hint:
        hit = [r for r in rows if r["iface"] == iface_hint]
        if len(hit) == 1:
            if lan_rows and hit[0]["ip"] not in {r["ip"] for r in lan_rows}:
                return None, (f"net.yaml 登记的 iface={iface_hint} 上的地址 {hit[0]['ip']} "
                              f"落在 USB4 网段内（与 segments 冲突）⇒ net.yaml 自相矛盾, 不猜")
            return hit[0], None
        if len(hit) > 1:
            return None, f"iface={iface_hint} 上有多个 global 地址 ({[r['ip'] for r in hit]}) ⇒ 不猜"
        return None, (f"net.yaml 登记的 iface={iface_hint} 在站上不存在（实测接口: "
                      f"{sorted({r['iface'] for r in rows})}）")
    if len(lan_rows) == 1:
        return lan_rows[0], None
    if not lan_rows:
        return None, "站上没有任何非 USB4 网段的 global 地址 ⇒ 该站 LAN 可能已断"
    return None, f"非 USB4 网段的 global 地址有 {len(lan_rows)} 个 ({[r['ip'] for r in lan_rows]}) ⇒ 不猜"


def validate_lan_addr(lan_doc, seen, seen_master=None):
    """★ 纯判据（D6）：`net.yaml §lan` 真值 vs **实测** LAN 地址。返回 (detail, warn, info)。

    detail(FAIL) = 实测 ≠ 真值 —— ★ 这里必须**带根因与修法**（本次改判据的全部意义所在）
    warn         = 判定**不成立**（探不到 / 解析不出 / 登记自相矛盾）或接口漂移
    info         = 射程声明：哪些站"没有可判的东西"必须**显式说出来**（不得像旧版那样静默跳过）

    seen        : {station: {"ip","iface","dynamic"} | {"error": "<原因>"} | None}
                  （None = 该站根本没采集到 ⇒ 也算"判定不成立"，**不是**通过）
    seen_master : {"ip": ...} | {"error": ...} | None —— **主控自身**的 LAN 地址。
      ★ 射程含主控的理由（2026-09-29 实测）：主控的 LAN 一漂，**三站全不可达** ——
        那是"可达 0/3 却不给根因"的最坏形态。主控地址就登记在 net.yaml §lan 的 `master.ip`。
    """
    detail, warn, info = [], [], []

    # ⓪ **主控自身**（先判它：它错了，下面三站的"不可达"是**同一个根因**，不是三个问题）
    m_want = ((lan_doc.get("master") or {}) or {}).get("ip")
    if m_want:
        if not seen_master:
            warn.append(f"master 自身 LAN 地址**无法判定**（net.yaml §lan.master 登记 {m_want}）")
        elif seen_master.get("error"):
            warn.append(f"master 自身 LAN 地址**无法判定**：{seen_master['error']}")
        elif seen_master.get("ip") and seen_master["ip"] != m_want:
            detail.append(
                f"★★ **master（本机）自身的 LAN 地址已漂移**: {m_want} → {seen_master['ip']} "
                f"—— ★ 这是**三站全部不可达**的根因（控制面源地址变了）；"
                f"先修 master（接到正确的网 / 或更新 net.yaml §lan.master 的登记），再谈各站")
        elif seen_master.get("ip"):
            info.append(f"master 自身 LAN 地址与真值一致: {seen_master['ip']}")
    for ent in (lan_doc.get("stations") or []):
        if not isinstance(ent, dict):
            continue
        st, want, iface_hint = ent.get("station"), ent.get("ip"), ent.get("iface")
        if not st or not want:
            warn.append(f"net.yaml §lan 有条目缺 station/ip, 本项无法判: {ent!r}")
            continue

        # ① master 侧**名字绑定**（ADR-0006 D1 的资产）—— 与站上实况是**两个不同的面**，都留着。
        alias = ent.get("host")
        if not alias:
            # ★ 射程**显式化**：旧版这里是一句 `continue`，于是"C 不在射程内"**无人知道**。
            info.append(f"{st} 站在 net.yaml 里无别名(host: null) ⇒ 无 master 侧绑定可判；"
                        f"该站由下面的『站上实况』覆盖（射程声明, 非跳过）")
        else:
            got = _ssh_g_hostname(alias)
            if got is None:
                warn.append(f"`ssh -G {alias}` 不可用 —— 无法核对 master 侧绑定 (该名应绑定到 {want})")
            elif got != want:
                detail.append(f"master 侧绑定漂移: `ssh -G {alias}` 的 hostname={got}, "
                              f"而 net.yaml §lan 登记 {want} ⇒ 同步 master ~/.ssh/config 与 net.yaml")

        # ② ★ 站上实况（D6 新增；不依赖别名 ⇒ 三站全覆盖）
        s = seen.get(st)
        if not s:
            warn.append(f"{st} 站 LAN 地址**无法判定**：直连采集不到，USB4 降级通道也没取回 ⇒ "
                        f"本项对该站**不成立**（不是通过）")
            continue
        if s.get("error"):
            warn.append(f"{st} 站 LAN 地址**无法判定**：{s['error']}")
            continue
        got, got_iface, dyn = s.get("ip"), s.get("iface"), s.get("dynamic")
        if not got:
            warn.append(f"{st} 站 LAN 地址**无法判定**：采集到但解析不出 (原始: {str(s)[:80]})")
            continue
        if got != want:
            detail.append(
                f"★ {st} 站 LAN 地址**已漂移**: {want} → {got} "
                f"(iface={got_iface}, scope={'dynamic/DHCP' if dyn else 'static'}) —— "
                f"这与「{st} 站不可达 / 依赖它的断言红灯」是**同一件事**, 根因在此。"
                f"修法: 同步三处真值 (inventory/net.yaml §lan · ops/cluster_const.py 的 STATIONS · "
                f"master ~/.ssh/config); 要**根治**见 ADR-0006 v1.1 的 D5")
        else:
            info.append(f"{st} 站 LAN 地址与真值一致: {got} (iface={got_iface})")
        if iface_hint and got_iface and iface_hint != got_iface:
            warn.append(f"{st} 站 LAN 地址所在接口已变: 实测 {got_iface}, net.yaml 登记 {iface_hint} "
                        f"⇒ 更新 net.yaml §lan 的 iface")
    return detail, warn, info


def _lanip_via_usb4(target, segs, live, ssh_run):
    """LAN 直连采集失败时，经**与该站有 USB4 直连的邻站**中转，去问它自己的 LAN 地址。

    ★ 这是 D6 的关键一步：它让「站不可达」与「地址漂移」**可区分**。
      2026-09-29 实测：C 的 LAN 已断（.37 消失），但经 `B → 10.10.11.3` 完全可达
      ⇒ 能问出它当时的真实地址（.8）—— 旧判据在这里只会吐一句"可达 2/3 站"。
    邻站与目标站的 USB4 地址**全部从 net.yaml §segments 派生**（不硬编码拓扑）。
    返回 (rows, err)：err=None 表示取回；否则是**响亮**的原因串（不静默、不降级成"通过"）。
    """
    cands = []
    for sg in (segs or []):
        if not isinstance(sg, dict):
            continue
        for e in (sg.get("ends") or []):
            if isinstance(e, dict) and e.get("station") == target and e.get("peer") and e.get("ip"):
                cands.append((e["peer"], e["ip"]))
    if not cands:
        return [], f"net.yaml §segments 里没有 {target} 站的 USB4 端点 ⇒ 无降级通道可走"
    errs = []
    for peer, ip in cands:
        if not live.get(peer):
            errs.append(f"邻站 {peer} 自身不可达")
            continue
        try:
            ok, out = ssh_run(peer, f'ssh -o BatchMode=yes -o ConnectTimeout=6 {ip} "{_LANIP_CMD}"',
                              timeout=40)
        except Exception as e:
            errs.append(f"经 {peer}→{ip}: {type(e).__name__}: {str(e)[:60]}")
            continue
        rows = _parse_lanip(out)
        if ok and rows:
            return rows, None
        errs.append(f"经 {peer}→{ip}: {'取回但解析不出' if ok else 'ssh 未成功'}")
    return [], f"降级通道全失败 ({'; '.join(errs)})"


def _is_loopback_addr(a):
    """`ss` 输出里的 Local 地址是不是 loopback —— **段位形态的护栏** (O-158 甲, 2026-10-10:
    "只覆盖 loopback + 已知 owner")。纯函数 ⇒ 可离线单测。"""
    s = str(a or "").strip()
    return s.startswith("127.") or s in ("::1", "[::1]", "localhost")


def check_stations(ctx):
    sys.path.insert(0, str(ROOT / "ops"))
    try:
        import cluster
    except Exception as e:
        return ("WARN",
                f"无法导入 cluster.py ({type(e).__name__}: {e}) — 该项需 paramiko; "
                f"请用装有 paramiko 的 Python 运行 (见 ops/rpc.ps1 的解释器选择)", [])

    ports_inv, models_inv = load_inventory()
    # detail = 判定失败的项; info = 上下文 (仅在失败/告警时附带打印, 不参与判定)
    detail, warn, info = [], [], []

    live = {}
    for st in ("A", "B", "C"):
        ok, out = cluster.ssh_run(st, STATION_CMD, timeout=90)
        live[st] = _parse_sections(out) if ok else None

    unreachable = [st for st, v in live.items() if not v]
    reach = [st for st in ("A", "B", "C") if live.get(st)]

    # (a) agent 配置 sha256 三站一致
    for i, path in enumerate(WATCHED):
        vals = {st: (live[st].get("cfg", "").splitlines()[i:i + 1] or ["(缺失)"])[0]
                for st in reach}
        row = f"{path}  " + " ".join(f"{st}={v}" for st, v in sorted(vals.items()))
        if len(set(vals.values())) > 1:
            detail.append(f"三站不一致: {row}")
        else:
            info.append(f"三站一致: {row}")

    # (b) 路由键 / RPC 模型 必须在目标站真实存在 (判据用 conf —— infer-load 读的就是它)
    def has(st, key):
        return key in (live.get(st) or {}).get("conf", "").split()

    for key, st in cluster.ROUTE.items():
        if st in reach and not has(st, key):
            detail.append(f"ROUTE 键 {key!r} 在目标站 {st} 站无 conf —— 该键已过期, "
                          f"load 会失败或落错站 (站上 conf: "
                          f"{', '.join(sorted((live[st].get('conf') or '').split()))})")
    for m in sorted(cluster.RPC_MODELS):
        if not any(has(st, m) for st in reach):
            detail.append(f"RPC 模型 {m!r} 在所有可达站都无 conf")

    # (c) conf 集合: 声明的必须存在 (缺=FAIL); 多出来的 = WARN
    #     load_inventory 会扫 models.yaml 的每个顶层列表, 故 non_model_conf 里的
    #     nodes 也一并进入 models_inv (带 alias+conf 字段), 这里无需另开分支。
    declared_conf = {}
    for alias, meta in (models_inv or {}).items():
        if alias != meta.get("alias"):
            continue
        for st in (meta.get("conf") or []):
            declared_conf.setdefault(st, set()).add(alias)
    for st in reach:
        live_conf = set((live[st].get("conf") or "").split())
        miss = declared_conf.get(st, set()) - live_conf
        if miss:
            detail.append(f"{st} 站缺少 inventory 已声明的 conf: {', '.join(sorted(miss))} "
                          f"—— 站上被删或 inventory 过期")
        extra = live_conf - declared_conf.get(st, set())
        if extra:
            warn.append(f"{st} 站 conf 有未登记条目: {', '.join(sorted(extra))} "
                        f"(新模型请登记到 inventory/models.yaml; 非模型条目应清理)")

    # (d) bind 合规 (仅查声明了 expect_bind 的端口)
    for st in reach:
        binds = {}
        for tok in (live[st].get("bind") or "").split():
            if ":" in tok:
                addr, _, p = tok.rpartition(":")
                if p.isdigit():
                    binds[int(p)] = addr
        for port, meta in (ports_inv or {}).items():
            exp = meta.get("expect_bind")
            if not exp or port not in binds:
                continue
            got = binds[port]
            if got not in (exp, exp.replace("127.0.0.1", "localhost")):
                detail.append(f"{st} 站 :{port} ({meta.get('purpose', '?')}) 实际监听 {got}, "
                              f"inventory 要求 {exp} —— 暴露面超预期")

    # (e) conf -> 权重存在性
    broken = set()
    try:
        import yaml
        _doc = yaml.safe_load((INVENTORY_DIR / "models.yaml").read_text(encoding="utf-8")) or {}
        broken = {(it.get("station"), it.get("alias"))
                  for it in (_doc.get("known_broken_conf") or [])}
    except Exception:
        pass
    non_model = {a for a, m in (models_inv or {}).items() if m.get("_group") == "non_model_conf"}
    for st in reach:
        for line in (live[st].get("mpath") or "").splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            alias, status = parts[0], parts[1]
            where = parts[2] if len(parts) > 2 else "?"
            if status == "MISSING":
                if (st, alias) in broken:
                    warn.append(f"{st} 站 {alias} 权重缺失 (已登记 known_broken_conf): {where}")
                else:
                    detail.append(f"{st} 站 {alias} 的 conf 指向的权重不存在 → load 必失败 ({where})")
            elif status == "NO_MODEL_PATH" and alias not in non_model:
                warn.append(f"{st} 站 {alias}.env 无 MODEL_PATH, 且未登记为 non_model_conf")

    # (f) 凭据引用完整性 —— settings.json 的 apiKeyHelper / opencode 的 {file:...}
    #     必须"引用得到、非空、可执行"; 以及 claude helper 的输出是否等于同站引擎 key。
    for st in reach:
        for line in (live[st].get("cred") or "").splitlines():
            line = line.strip()
            if line.startswith("helper="):
                v = line.split("=", 1)[1]
                if not v.startswith("OK:"):
                    detail.append(f"{st} 站 claude apiKeyHelper 不可用 ({v}) —— "
                                  f"settings.json 引用的脚本不存在/不可执行/输出为空")
            elif line.startswith("ocfile="):
                v = line.split("=", 1)[1]
                if not v.startswith("OK:"):
                    detail.append(f"{st} 站 opencode provider 引用的凭据文件不可用 ({v}) "
                                  f"—— 不存在或为空")
            elif line.startswith("claudekey="):
                # 2026-09-16 (A): 判据改为「helper 输出 == 同站 unsloth.key」。SKIP_NO_HELPER
                # 不在此告警 (helper 自身的问题已由上面 helper= 行报出)。
                if line.split("=", 1)[1] == "DIFFERS":
                    warn.append(f"{st} 站 claude apiKeyHelper 的输出与同站引擎 key "
                                f"(~/.config/rpc/unsloth.key) 不一致 —— claude 走本地 :8080, "
                                f"必须与 opencode 用同一份引擎 key; 站上跑一次 infer-load 会重铸该 key")
            elif line.startswith("unslothlog="):
                # 2026-09-16 (f2): unsloth studio 日志的明文面 —— 判据是**权限**而非"含不含 key"
                # (studio 每次加载必写 key 进日志, 且 infer-load 依赖从日志取 key, 消除不掉)。
                kv = dict(p.split(":", 1) for p in line.split("=", 1)[1].split() if ":" in p)
                dp = kv.get("dirperm", "NA")
                loose = kv.get("loose", "0")
                wk = kv.get("withkeys", "0")
                if dp not in ("700", "NA"):
                    warn.append(f"{st} 站 ~/.unsloth 权限 {dp} (应 700) —— 该目录含 studio 每次"
                                f"加载写入的引擎 key 明文日志; 修: chmod 700 ~/.unsloth")
                if loose != "0":
                    warn.append(f"{st} 站 {loose} 份 run-*.log 权限非 600 (含 key 的共 {wk} 份) "
                                f"—— 修: chmod 600 ~/.unsloth/run-*.log")

    # (g) 站上监听端口 vs 分配表 (P1-4 占用对账)
    #     方向一 (FAIL): 站上在听、端口 < EPHEMERAL_MIN、且分配表里没有它 →
    #        真值表漏登记 (第一次跑就查出 137/138/546/5353/3702/6665/724 七类)。
    #        ≥ EPHEMERAL_MIN 的一律豁免: 该段是内核临时端口, 服务每次启动换号
    #        (NFS mountd/statd 即典型), 登记端口号必然过期。
    #     方向二 (WARN): 分配表声明在用、站上却没听 → 可能只是服务挂了。
    #        带 status 或 mode: on_demand 的条目豁免 (如 studio 的 8080 本就是按需启停)。
    try:
        port_entries = _port_entries()
    except Exception as e:
        # 解析失败必须报真因, 不能让下面的循环把"整张表读不出"表现成
        # 几十条"端口未登记"的假象 (2026-09-15 实测踩到), 故直接跳过整段对账。
        port_entries = None
        detail.append(f"ports.yaml 解析失败, 端口占用对账无法进行 —— "
                      f"{type(e).__name__}: {str(e)[:160]}")
    ignored_eph, checked_ports = 0, 0
    if port_entries is not None:
        by_port, by_range = {}, []
        for g in ("managed", "third_party", "unmanaged"):
            for e in port_entries.get(g) or []:
                if not isinstance(e, dict):
                    continue
                if isinstance(e.get("port"), int):
                    by_port.setdefault(e["port"], []).append((g, e))
                elif e.get("range"):
                    by_range.append((g, e))       # ★ 段位形态 (O-158 甲, 2026-10-10)

        def _proto_ok(e, side):
            """proto 语义: tcp/http/https → TCP 侧; udp → UDP 侧;
                        tcp+udp → 两侧 (mihomo 的 mixed / DNS 端口即双栈);
                        缺省 → 两侧都算 (unmanaged 里的系统端口多不关心协议侧)。"""
            p = str(e.get("proto") or "").lower()
            if p == "udp" and side != "udp":
                return False
            if p in ("tcp", "http", "https") and side != "tcp":
                return False
            return True

        def _range_hits(st, side, port):
            """段位形态里「站 + 协议侧 + 端口落在 range 内」三项都命中的条目。"""
            out = []
            for g, e in by_range:
                rng = e.get("range")
                if not (isinstance(rng, (list, tuple)) and len(rng) == 2
                        and all(isinstance(x, int) for x in rng)
                        and rng[0] <= port <= rng[1]):
                    continue
                if st not in _scopes(e) or not _proto_ok(e, side):
                    continue
                out.append((g, e))
            return out

        def _reg_covers(port, side, st, addr=None, names=None):
            """分配表是否已登记该 (端口, 协议侧, 站) —— 两种形态:

            ① **整数 `port` 条目** (旧口径, 一字未改): 命中 (端口, 侧, 站) 即覆盖。
            ② ★ **段位形态** (O-158 甲, 2026-10-10): 无 `port`、有 `owner` + `range` ⇒
               **三闸齐**才覆盖 —— 端口落在 range 内 · 站上实况**绑在 loopback** ·
               占用者名**命中登记 owner**。⚠ 占用者名取不到 (sudo -n 失败等) ⇒ **不覆盖**
               (**判不了 ≠ 通过**)。护栏 = 「只覆盖 loopback + 已知 owner」: 段位写得再宽
               也**吞不掉**别的形态的口 (非 loopback / 别的 owner / 无名可取 ⇒ 照常报未登记)。
            """
            for _g, e in by_port.get(port, []):
                if st not in _scopes(e) or not _proto_ok(e, side):
                    continue
                return True                  # tcp+udp 与缺省都覆盖两侧
            for _g, e in _range_hits(st, side, port):
                if not _is_loopback_addr(addr):
                    continue
                if names and e.get("owner") in names:
                    return True
            return False

        def _range_miss(port, side, st, addr, names):
            """段位命中了「站+侧+段位」却没接住 ⇒ 点名是**哪一道闸**没过 (只作 FAIL 文案后缀;
            防"段位写得含糊 ⇒ 真因不可见")。"""
            for _g, e in _range_hits(st, side, port):
                own = e.get("owner", "?")
                if not _is_loopback_addr(addr):
                    return (f"；⚠ 段位条目 (owner={own}) 只覆盖 loopback, 站上实况绑的是 {addr} "
                            f"—— 见 O-158")
                if not names:
                    return (f"；⚠ 段位条目 (owner={own}) 覆盖此段位但**占用者取数缺失** "
                            f"(站上 sudo -n ss 无该口?) —— 判不了 ≠ 通过 (O-158)")
                if own not in names:
                    return (f"；⚠ 段位条目 (owner={own}) 覆盖此段位但**占用者名未命中** —— "
                            f"站上取到 {'/'.join(sorted(names))} —— 见 O-158")
            return ""

        def _listening(st, sec):
            out = set()
            for tok in (live[st].get(sec) or "").split():
                if ":" in tok:
                    p = tok.rpartition(":")[2]
                    if p.isdigit():
                        out.add(int(p))
            return out

        def _listen_rows(st, sec):
            """`(addr, port)` 明细 (同口不同绑址各一条) —— 段位形态判 loopback 用;
            `_listening` 只留端口 (旧口径, 方向二仍在用)。"""
            out = set()
            for tok in (live[st].get(sec) or "").split():
                if ":" not in tok:
                    continue
                a, _, p = tok.rpartition(":")
                if p.isdigit():
                    out.add((a, int(p)))
            return out

        def _owners_by_socket(st, sec):
            """{(addr, port): {占用者名}} —— 由 `[towner]/[uowner]` (sudo `ss -lXnp`) 解析。

            行格式: 第 4 列 = Local `addr:port`, 行尾 `users:(("名",pid=..,fd=..))`。
            ⚠ 无该 socket / 无 users 字段 ⇒ 查不到 ⇒ 段位条**不覆盖** (fail-closed)。
            """
            out = {}
            for line in (live[st].get(sec) or "").splitlines():
                f = line.split()
                if len(f) < 4 or ":" not in f[3]:
                    continue
                a, _, p = f[3].rpartition(":")
                if not p.isdigit():
                    continue
                m = re.search(r"users:\((.*)\)", line)
                out[(a, int(p))] = set(re.findall(r'"([^"]+)"', m.group(1))) if m else set()
            return out

        for st in reach:
            owners = {"tcp": _owners_by_socket(st, "towner"),
                      "udp": _owners_by_socket(st, "uowner")}
            for side, sec in (("tcp", "bind"), ("udp", "ubind")):
                rows_by_port = {}
                for addr, port in _listen_rows(st, sec):
                    rows_by_port.setdefault(port, []).append(addr)
                for port, addrs in sorted(rows_by_port.items()):
                    checked_ports += 1
                    miss = [a for a in sorted(addrs)
                            if not _reg_covers(port, side, st, a, owners[side].get((a, port)))]
                    if not miss:
                        continue
                    if port >= EPHEMERAL_MIN:
                        ignored_eph += 1
                        continue
                    for a in miss:
                        detail.append(
                            f"{st} 站 {side.upper()} :{port} 有监听但分配表未登记 —— "
                            f"是常驻服务就登记到 inventory/ports.yaml "
                            f"(我方 = managed, 他方 = third_party/unmanaged)"
                            f"{_range_miss(port, side, st, a, owners[side].get((a, port)))}")
            # 方向二
            for g in ("managed", "third_party"):
                for e in port_entries.get(g) or []:
                    if not isinstance(e, dict) or not isinstance(e.get("port"), int):
                        continue
                    if st not in [str(x) for x in (e.get("scope") or [])]:
                        continue      # 反向只查明确声明了该站的条目
                    if e.get("status") or str(e.get("mode") or "") == "on_demand":
                        continue
                    if (e["port"] in _listening(st, "bind")
                            or e["port"] in _listening(st, "ubind")):
                        continue
                    warn.append(f"{st} 站 :{e['port']} ({e.get('purpose', '?')}, "
                            f"owner={e.get('owner', '?')}) 声明在用但未监听 —— "
                            f"服务挂了? 若本就按需启停, 加 mode: on_demand")

    # (h) 插件/技能三站同构 (P1-5)
    #     站上 plugin-probe 汇报 `id=value` → 与 inventory/plugins.yaml 的 expect 逐项比对。
    #     known_drift 命中降 WARN, 但**只有"恰好多出已登记的那些"**才降级 —— 少了元素、
    #     或多了未登记的东西, 一律 FAIL (与 models.yaml 的 known_broken_conf 同一精神:
    #     已登记的可见不阻断, 但新差异不许被登记这件事糊过去)。
    try:
        pdoc = _plugins_doc()
    except Exception as e:
        pdoc = None
        detail.append(f"inventory/plugins.yaml 解析失败, 插件同构对账无法进行 —— "
                      f"{type(e).__name__}: {str(e)[:160]}")
    plugin_checked = 0
    if pdoc is not None:
        pitems = _plugin_items(pdoc)
        drift = {}
        for kd in pdoc.get("known_drift") or []:
            if isinstance(kd, dict) and kd.get("id") in pitems:
                drift[(str(kd.get("station")), str(kd.get("id")))] = \
                    sorted(str(x) for x in (kd.get("extra") or []))

        for st in reach:
            facts = {}
            for line in (live[st].get("plug") or "").splitlines():
                if "=" in line:
                    k, _, v = line.partition("=")
                    facts[k.strip()] = v.strip()
            if not facts:
                warn.append(f"{st} 站 plugin-probe 无输出 —— 站上未部署 "
                            f"ops/station-bin/plugin-probe (部署后重跑); 本子项对该站跳过")
                continue
            for iid, it in sorted(pitems.items()):
                if st not in _plugin_scope(it):
                    continue
                plugin_checked += 1
                got = facts.get(iid)
                if got is None:
                    detail.append(f"{st} 站 plugin-probe 未汇报 {iid} —— 站上脚本比基线旧, "
                                  f"需重新部署 ops/station-bin/plugin-probe")
                    continue
                diff = _plugin_diff(it, got)
                if diff is None:
                    continue
                reg = drift.get((st, iid))
                if diff[0] == "extra" and reg is not None and sorted(diff[1]) == reg:
                    warn.append(f"{st} 站 {iid} 多出已登记项 {diff[1]} "
                                f"(inventory/plugins.yaml 的 known_drift, 不阻断)")
                else:
                    detail.append(f"{st} 站 {iid} ({it.get('purpose', '?')}) "
                                  f"实得 {got!r} · 基线 {it.get('expect')!r} · 差异 {diff[1]}")

    # (h) LAN 地址对账 (ADR-0006 v1.1 · D6, 2026-09-29) —— 两个面：
    #     ① master 侧**名字绑定**（`ssh -G <别名>` == net.yaml 的 ip；D1 的资产，纯本地展开）；
    #     ② ★ **站上实况**（站上 `ip -4 -o addr` 的 LAN 地址 == net.yaml 的 ip；D6 新增）。
    #   为什么加②: ①的射程靠"别名"，`host: null` 的 C 站**整站被跳过** —— 2026-09-29 C 由
    #     .37 漂到 .8 时，6 项断言只报"可达 2/3 站"、**不给根因**（正是 D4 要消灭的谜题）。
    #   代价: ②搭在同一次合并 ssh 上（零新增连接）；**只有某站直连采集失败**时才多一次
    #     `邻站 → USB4` 的中转 ssh —— 而那种情况本来就已经在报红灯。
    try:
        net_doc = _net_doc() or {}
        lan_doc, segs = net_doc.get("lan") or {}, net_doc.get("segments") or []
    except Exception as e:
        lan_doc, segs = {}, []
        warn.append(f"net.yaml 解析失败, LAN 地址对账跳过 —— {type(e).__name__}: {str(e)[:120]}")
    seg_nets = []
    for sg in segs:
        try:
            seg_nets.append(ipaddress.ip_network(str(sg.get("cidr")), strict=False))
        except Exception:
            warn.append(f"net.yaml §segments 的 cidr 不可解析, 已忽略: {sg.get('cidr')!r}")
    seen_lan = {}
    for ent in (lan_doc.get("stations") or []):
        if not isinstance(ent, dict) or not ent.get("station"):
            continue
        st = ent["station"]
        rows, src = _parse_lanip((live.get(st) or {}).get("lanip")), "直连"
        if not rows:                                    # 直连采集不到 ⇒ 走 USB4 降级通道
            rows, err = _lanip_via_usb4(st, segs, live, cluster.ssh_run)
            src = "USB4 降级通道"
            if err:
                seen_lan[st] = {"error": err}
                continue
            info.append(f"{st} 站直连采集不到（LAN 不通?）, 已**经 USB4 降级通道**取回其真实地址")
        got, perr = pick_lan_addr(rows, ent.get("iface"), seg_nets)
        seen_lan[st] = got if got else {"error": f"{src}: {perr}"}
    # 主控自身：探针 = 真值里**第一个站的 ip**（UDP-connect 只做路由选择, 不发包）
    probe = next((e.get("ip") for e in (lan_doc.get("stations") or [])
                  if isinstance(e, dict) and e.get("ip")), None)
    seen_master = {"ip": _local_lan_ip(probe)} if probe else \
        {"error": "net.yaml §lan.stations 里没有可用的 ip ⇒ 无法判断本机走哪条路"}
    if probe and not seen_master.get("ip"):
        seen_master = {"error": f"无法确定本机通往 {probe} 的源地址（socket 失败）"}
    d_lan, w_lan, i_lan = validate_lan_addr(lan_doc, seen_lan, seen_master)
    detail += d_lan
    warn += w_lan
    info += i_lan

    # (h) 长龄 orphan (O-58, 2026-09-25) —— 站上 ad-hoc 探针/派发留下的僵尸 / 长龄进程。
    #   判据: comm ∈ {opencode, claude, timeout, defunct} 且 etimes ≥ 阈值。
    #   ⚠ **刻意只 WARN、不 FAIL**: 该阈值**判不出"合法的长 run"**(我们自己的长卡可以跑 >6h)
    #     ⇒ 需要人判。本条的价值是**把信号从"偶然人肉 ps"变成"每次全量门禁都报"**，
    #     不是自动清理(清孤儿是不可逆动作, 见 O-58 的裁定记录)。
    #   ⚠ 阈值可由 `RPC_ORPHAN_SEC` 覆盖 —— **为了能先验红**: 6h 的长龄进程无法现场造出来,
    #     而新判据必须双向自证(否则无从区分"判据对"与"判据恒假")。默认仍是 6h。
    # ★ O-70 (2026-09-25) **射程写准**: 本条**只守本站 runtime 白名单那几类**, 不是"站上有无异常进程"。
    #   依据(实测): O-72 那条真孤儿是 `bash` + `sleep`(存活 28.6h), **完全不在白名单** ⇒ 漏报。
    #   ⇒ ① 报数/告警文案里**列出白名单**; ② 另设 (i) `[orph2]` = 白名单外的 ppid=1 长龄进程,
    #     **只报数不判定**(见下), 补上"可见化"这一半。
    ORPHAN_WHITELIST = "opencode|claude|timeout|defunct"
    ORPHAN_SEC = int(os.environ.get("RPC_ORPHAN_SEC") or 6 * 3600)
    orphan_checked = 0
    for st in reach:
        stale = []
        for line in (live[st].get("orph") or "").splitlines():
            f = line.split()
            if len(f) < 4:
                continue
            pid, ppid, et, comm = f[0], f[1], f[2], " ".join(f[3:])
            if not et.isdigit():
                continue
            orphan_checked += 1
            et = int(et)
            if et >= ORPHAN_SEC:
                stale.append(f"{comm} (pid {pid}, ppid {ppid}, 已 {et // 3600}h{(et % 3600) // 60}m)")
        if stale:
            warn.append(f"{st} 站发现**长龄 orphan** (⚠ 射程 = 本白名单 `{ORPHAN_WHITELIST}` · ≥{ORPHAN_SEC // 3600}h；"
                        f"见台账 O-58/O-70): {'; '.join(stale)} —— ⚠ 正在跑的**合法**长 run 也会命中，先确认再清")
        else:
            info.append(f"{st} 站无长龄 orphan (白名单 `{ORPHAN_WHITELIST}` · ≥{ORPHAN_SEC // 3600}h)")
    # (i) O-70 第二类: **我们自己的**产物名命中的进程(不限于白名单 comm) —— **只报数, 永不进 warn/FAIL**。
    #   为什么分开: 白名单内那四类是我们的 runtime, 长龄基本=卡死; 而这一类的匹配键是"**我们的脚本名**",
    #     覆盖 `bash`/`sleep`/`find` 这些白名单看不到的形态(O-72 的真孤儿正是 `bash`+`sleep`) ——
    #     按已裁定的口径**只做可见化**(判成 WARN 会淹信号; 判成 FAIL 更糟, 清孤儿**不可逆**)。
    #   第三列是 `args`(完整命令行) ⇒ 直接打印出来, 人一眼能看出是哪条链漏的。
    orph2_checked = 0
    orph2_stale = []
    for st in reach:
        for line in (live[st].get("orph2") or "").splitlines():
            f = line.split()
            if len(f) < 3:
                continue
            pid, et, what = f[0], f[1], " ".join(f[2:])
            if not et.isdigit():
                continue
            orph2_checked += 1
            if int(et) >= ORPHAN_SEC:
                orph2_stale.append(f"{st}:{what[:70]} (pid {pid}, {int(et) // 3600}h)")
    if orph2_stale:
        info.append(f"白名单外但**属于我们**的长龄残留 {len(orph2_stale)} 条 (**只报数不判定**; 见台账 O-70): "
                    f"{'; '.join(orph2_stale[:5])}")

    if unreachable:
        info.insert(0, f"站点不可达 (未计入判定): {', '.join(unreachable)}")
    note = (f"可达 {len(reach)}/3 站 · 对账 cfg{len(WATCHED)}/ROUTE{len(cluster.ROUTE)}"
            f"/RPC{len(cluster.RPC_MODELS)}/conf{sum(len(v) for v in declared_conf.values())}"
            f"/bind{sum(1 for m in (ports_inv or {}).values() if m.get('expect_bind'))}"
            f"/port{checked_ports}(豁免临时段 {ignored_eph})/plugin{plugin_checked}"
            f"/weight{sum(1 for st in reach for _ in (live[st].get('mpath') or '').splitlines())}"
            f"/orph{orphan_checked}"
            f"/orphx{orph2_checked}"
            # ★ O-70 (2026-09-26): 把**第二类的 stale 条数**也放进 note —— 此前 note 只有 `orphx`
            #   （= 探针**见到几行**，与年龄无关），而"有几条超阈值"只在 >0 时才出现在 info 里
            #   ⇒ 采样时无法**直接读**这个数（只能靠"info 里有没有那行"，脆弱）。
            #   ⚠ 加这个数**不改灯的语义**（第二类仍只报告、不进 WARN/FAIL）；它只是让 O-70 的
            #     "先看几轮噪声水平再裁"这一步**有数据可读**。
            f"/orphxstale{len(orph2_stale)}")
    if detail:
        return "FAIL", note, info + detail + [f"(WARN) {w}" for w in warn]
    if warn:
        return "WARN", note, info + warn
    return "PASS", note, []


# ── 断言 A8..A11: 健康引擎 (P2-2) ─────────────────────────────────
# 目的: 把 rpc_check.py 从"提交门禁"扩成"集群健康引擎"—— 学 Ollama Herd 的
# "成体系的自检项 + 红黄绿 + 修复建议"形态 (方案 §A.2.2), 补齐方案 §5.3 P2-2 列的
# 维度里**尚未覆盖**的四块:
#   usb4   链路层: 三段地址/MTU/接口状态/六向直连/主备回程路由   (此前完全没覆盖)
#   gates  内存门禁: load-gate 可用性 + 当前余量 + loadavg       (此前完全没覆盖)
#   engine 引擎态: 就绪 + **残留检测**(内存被占着但没有服务)      (此前只看 conf/ROUTE)
#   models 模型库完整性: 孤儿/断链                                (此前只在 CLI, 未进门禁)
# (端口/凭据/配置一致性/插件同构已由 ports + stations 的 (a)(d)(f)(g)(h) 覆盖)
#
# ssh 往返控制: usb4/gates/engine 三项共用**一次**合并采集(每站), 并按站缓存 ——
# 否则 3 项 × 3 站 = 9 次往返, 门禁会慢到没人愿意跑。缓存只活在本进程内,
# 故 `--only` 单跑某项时同样只需 1 次/站。
INVENTORY_NET = INVENTORY_DIR / "net.yaml"
# 三段全部端点地址: 采集侧盲发 ping, 由门禁侧判定"哪些必须通"
NET_ENDS = ("10.10.10.1", "10.10.10.2", "10.10.11.1",
            "10.10.11.3", "10.10.12.1", "10.10.12.3")
ENGINE_PORTS = ("8080", "8081", "18080", "18081", "50052")


# ★ O-146（2026-10-05）：**8080 的占用者是哪条路径的引擎** —— 取数分类（**只报数、不进判定**）。
# 为什么需要（根因，读码取证）：`backend` 判**装机面**（两条路径的二进制在不在 + 后端类型），
#   `engine` 判**运行面**却只问"在不在服务 / 是不是残留" ⇒ **"运行中的引擎来自哪条路径"
#   落在两个门禁的缝里，两边都不判**（实测：A 站跑 `/opt/llama.cpp/llama-server` 占着 8080，
#   而 `backend` 照样 PASS ⇒ "未迁移"在门禁层不可见）。更深一层：`BACKEND` 只被 `infer-load`
#   消费，systemd 单元走 `llama-serve-instance`、只读 `LLAMA_SERVER_BIN`（缺省 `/opt/...`）。
# ★★ **O-146 乙′（2026-10-05 裁定）：占用者【进判定】** —— 作用域 = `ports.yaml` 里 `purpose` 含
#   "推理引擎" 的端口（**由真值表驱动、不硬编码**；现 = 8080）；`other`（认不出的东西占着）·
#   `unknown`（取不到 ⇒ 判不了）⇒ **WARN**；`{studio,opt-vulkan,opt-variant}` / `none` ⇒ 通过。
#   ★ 为什么**不**做"按站期望"（甲案）：A 站形态随**外部消费者**时变（实测 `gpt-oss-120b`↔
#   `MiniMax-M2.7`、`llama-single`↔`unsloth` 都出现过）⇒ 写死期望必生误报（SRE 共识：**静态阈值
#   是误报头号成因**；`O-143` 的 A 站 RSS 假阳性即先例）。外部依据：NIST SP 800-167 白名单 =
#   **有限已知集**（不声明"谁该在"）；path 类识别「单独用弱」⇒ 故本判据**只判"认不出/取不到"**，
#   **不判"身份是否正确"**。三者对照见 `O-146` 的多维表。
# ⚠ fail-closed：取不到 ⇒ `unknown`（**绝不**把"读不出"当 `none`）；`listening=True` 却说
#   `none`（LISTEN 段与占用者取数矛盾）⇒ 也记 `unknown`。
_OCCUPANT_KINDS = (("opt-vulkan", "/opt/llama.cpp/"),  # /opt/llama.cpp/（Vulkan 分布式路径 · ★ 当前基线）
                   ("opt-variant", "llama.cpp-"),      # /opt/llama.cpp-<变体>/（GLM 等特性分支）
                   ("studio", "unsloth"),              # studio 启动器（cmdline 含 `unsloth studio run`）
                   # ★ 2026-10-21 (ADR-0014 D7): halogen 容器把 8080 发布到宿主 ⇒ 宿主监听者
                   #   是 docker 的 **userland proxy**，不是引擎进程本身（实测 B 站:
                   #   `127.0.0.1:8080 users:(("docker-proxy",pid=…))`，容器内引擎叫 flash_serve）。
                   ("docker-publish", "docker-proxy"))
# ⚠⚠ **顺序承重（2026-10-05 活体检查抓到）**：`/opt/llama.cpp` 是 **symlink → `/opt/llama.cpp-master-<hash>`**
#   ⇒ 若按 `readlink -f` 的 **exe** 分类，**当前基线**会撞上 `llama.cpp-` 而被误标 `opt-variant`。
#   故：① **opt-vulkan 必须排在 opt-variant 之前**；② 分类用的 blob **含 cmdline**（cmdline 保留
#   **未解析**的 `/opt/llama.cpp/llama-server`）⇒ 当前基线稳定落 `opt-vulkan`，真变体（cmdline 里是
#   `/opt/llama.cpp-<名>/…`，**不含** `/opt/llama.cpp/`）才落 `opt-variant`。同理 studio 的监听进程
#   exe 是 **python 启动器**，其身份只在 cmdline ⇒ 必须看 cmdline。


def classify_engine_occupant(path, listening=False, cmdline=""):
    """把"占用 8080 的进程"归成一类（**唯一定义点**，纯函数 ⇒ 可离线单测）。

    ⚠⚠ **必须同时看 `cmdline`**（2026-10-05 活体检查抓到）：studio 的监听进程是**python 启动器**
    （实测 exe = `…/anaconda3/bin/python3.13`），**只看 exe 会把 studio 误报成 `other`** ⇒
    分类基于 `exe + cmdline` 的合并串（cmdline 里才有 `unsloth studio run --model …`）。
    """
    p = str(path or "").strip()
    c = str(cmdline or "").strip()
    if p in ("", "unknown") and not c:
        return "unknown"                 # 取不到 ⇒ 不可判（fail-closed，**绝不**当 none）
    if p == "none" and not c:
        # LISTEN 段说在听、占用者却说 none ⇒ 取数自相矛盾 ⇒ **不可判**（不是"没占用"）
        return "unknown" if listening else "none"
    blob = p + " " + c
    for kind, marker in _OCCUPANT_KINDS:
        if marker in blob:
            return kind
    return "other"


# ★★ O-146 乙′（2026-10-05）：**允许出现的占用者形态**（有限已知集，NIST SP 800-167 白名单同构）。
#   ⚠ 刻意**不**含"哪一站该跑哪个" —— 那正是被否的甲案（期望随外部消费者时变）。
_OCCUPANT_OK = ("studio", "opt-vulkan", "opt-variant", "docker-publish")


def _engine_api_ports():
    """从 `inventory/ports.yaml` 取"**推理引擎 API**"端口（★ 真值表驱动，不硬编码）。

    判据 = 该端口条目的 `purpose` 含「推理引擎」（现 = 8080 与 8731：前者是客户端面，后者是
    halogen 的原生 API 面）。
    读不到/解析失败 ⇒ 退回 `("8080",)`（**fail-safe 到已知端口**，不是"跳过判定"）。
    ★ 2026-10-21（`O-164` 修复）：原实现**未 import yaml** ⇒ `NameError` 被下面
    `except Exception` 吞掉 ⇒ 实际恒返回 `("8080",)`，"真值表驱动"**从未生效**。
    现与文件内其它断言同口径：**函数内** `import yaml`（缺 pyyaml 时降级为 fail-safe）。
    """
    try:
        import yaml                          # 函数内导入 ⇒ 缺 pyyaml 时走 fail-safe, 不整仓崩
        doc = yaml.safe_load(INVENTORY_PORTS.read_text(encoding="utf-8")) or {}
    except Exception:
        return ("8080",)
    out = []

    def _walk(o):
        if isinstance(o, dict):
            if "port" in o and "推理引擎" in str(o.get("purpose", "")):
                out.append(str(o["port"]))
            for _v in o.values():
                _walk(_v)
        elif isinstance(o, list):
            for _v in o:
                _walk(_v)

    _walk(doc)
    return tuple(out) or ("8080",)


# 残留阈值: 进程 RSS 超过它却没有引擎在服务 → 视为残留(占着内存不干活)。
# 取 2G: 正常单机 llama-server 的 RSS 是几十 G 量级, 而 ggml-rpc-server 空转也有 ~0.3G,
# 故 2G 能把"真占住了"和"进程刚起/空跑"分开 (本会话真的踩到过 62.6G 残留污染判定)。
RESIDUAL_RSS_MB = 2048
# O-41② (2026-09-24): **预警带下沿** —— `[1024, RESIDUAL_RSS_MB)` 且无引擎端口 ⇒ 报 WARN（不 FAIL）。
#   为什么需要: 旧实现只有"≥2G = 残留 FAIL"与"否则 = 正常"，**1024~2048M 这一段完全无声**
#   （O-41② 实测: 1.5G 无端口残留被判"正常"）。下沿取 1024 是为了**不误报 ggml-rpc-server 空转(~0.3G)**
#   与"进程刚起"这两种刻意容忍的情形 ⇒ 只覆盖"明显占住了但没在服务"的带。
RESIDUAL_WARN_MB = 1024


def classify_engine_band(has_ports, rss_mb, n_proc=None):
    """`engine` 断言的**唯一定义点**（O-143 乙，2026-10-03）—— 两分支共用同一份口径。

    返回 `(verdict, reason)`；`verdict ∈ {"FAIL","WARN",None}`（`None` = 无告警）；`reason` 是**不带站名**的短句。

    ★ 为什么必须集中: 修 O-143 之前，"进程刚起"这一情形在**无端口**分支被**刻意容忍**
    （见 `RESIDUAL_WARN_MB` 的注释），在**有端口**分支却按**裸 RSS** 判异常
    ⇒ **同一断言的两半对同一情形给出相反判定**。

    ★★ 判据依据的**更正**（2026-10-03 实测，E1）: **RSS 不是"引擎在不在服务"的证据** ——
    A 站在 **13h**、RSS **208M** 下实测推理 **56.6 t/s**、**GTT 68.75 GiB** 驻留
    （Vulkan/UMA 引擎的权重驻留**设备侧**）⇒ **"有端口 + RSS 小"不足以判异常**。
    故**有端口**分支改用**进程数**作判据:
      · `n_proc >= 1` ⇒ **在服务**（RSS / 进程龄 只作**报数**）
      · `n_proc == 0` ⇒ **端口在听但不是我们的引擎** ⇒ 疑似端口被占（WARN）
      · `n_proc` 读不出     ⇒ **退回旧的 RSS 口径**（「判不了 ≠ 通过」，不静默放过）

    ⚠ **射程（诚实登记，见台账 `O-143`）**: `n_proc >= 1` 只证明**站上有 llama 系进程**，
    **不证明 8080 的持有者就是它**（证到那一层须按端口取 pid —— 需 root，本门禁不具）。
    """
    if has_ports:
        if isinstance(n_proc, int):
            if n_proc <= 0:
                return "WARN", "端口在听但站上**无** llama 系进程 ⇒ 疑似端口被占"
            return None, None
        # 进程数读不出 ⇒ 退回旧口径（保守: 仍可能报，但不静默通过）
        if rss_mb < 1024:
            return "WARN", f"有引擎端口在听但 RSS 仅 {rss_mb}M（进程数读不出）⇒ 疑似异常进程/端口被占"
        return None, None
    if rss_mb >= RESIDUAL_RSS_MB:
        return "FAIL", (f"无任何引擎端口在听, 但 llama/rpc 进程仍占 {rss_mb // 1024}G RSS"
                        f" —— 内存被占着没干活, 会污染加载预估 (先 infer-unload / 清残留再加载)")
    if rss_mb >= RESIDUAL_WARN_MB:
        return "WARN", (f"有 llama 系进程占 {rss_mb}M 但无引擎端口在听 —— 疑似残留/启动中 "
                        f"(预警带 ≥{RESIDUAL_WARN_MB}M, FAIL 阈值 {RESIDUAL_RSS_MB}M)")
    return None, None

# ── 站上件"部署一致性"跟踪清单 (2026-09-22 裁定接入 gates) ──────────────────────
# 背景: 这些件是**站上件** —— 部署在 `/usr/local/bin/`, 仓库副本只是"快照"。
#   ⇒ **改仓库副本不生效**, 必须重新部署; 而"站上跑的那份是不是仓库这份"此前**没有任何机器判据**
#     (只靠 `ops/station-bin/README.md` 的**手工 md5 约定**) ⇒ 本清单把那条约定变成可判。
# ⚠ **期望值不在此处写死**: 真值源 = 仓库副本 `ops/station-bin/<name>` 自身(运行期算 md5)
#   ⇒ 不立第二定义点, 也免掉"改了仓库忘改表"这种漂移(与本仓"判据只在一处定义"同一条纪律)。
# 为什么只列这些: 它们是 `ops/station-bin/README.md` 文件清单里声明的站上件。
# ⚠ 为什么敢判 FAIL(而非 WARN): 接入前实测过**误报面** —— 8 个件 × 三站里 7 个本来就逐字节一致,
#   唯一不一致的 `wait-gtt-release` 是**真漂移**(A/B 落后一版且带 BOM), 已单独立项。
# 2026-09-29 补第 9 件 `rpc-serve-instance`(RPC worker 包装器, GLM-5.3-Flash 引擎变体需要)。
# 2026-10-27 补第 10-12 件（P1 review-p1-remediation）:
#   `model-locate.sh` / `conf-lib.sh` / `conf-get` —— #3 模型定位与 #4 conf 读写的共享实现。
# ⚠⚠ 同日本项**顺带抓到一类系统性假红**: `core.autocrlf=true` 使仓库工作树里
#   `infer-load` / `infer-unload` 是 CRLF, 而站上是 LF ⇒ 逐字节比对必然 FAIL(内容其实一致)。
#   判据是对的(CRLF 的 shell 脚本在 Linux 上**真的**语法错误, 2026-09-29 部署时实测 203/EXEC 同类),
#   错的是**仓库工作树**: 已把这 2 件归一为 LF。改这几个件时务必确认行尾是 LF。
STATION_BINS = ("infer-load", "infer-unload", "infer-list", "llama-serve-instance",
                "rpc-serve-instance", "cluster-ttl", "load-mem-gate", "wait-gtt-release",
                "load-gate", "model-locate.sh", "conf-lib.sh", "conf-get")

_HEALTH_CMD = (
    "echo '===ADDR==='; ip -o -4 addr show 2>/dev/null "
    "| awk '$4 ~ /^10\\.10\\./ {print $2, $4}'; "
    "echo '===LINK==='; for i in $(ls /sys/class/net 2>/dev/null | grep '^thunderbolt'); do "
    "echo \"$i $(cat /sys/class/net/$i/mtu 2>/dev/null) $(cat /sys/class/net/$i/operstate 2>/dev/null) $(readlink -f /sys/class/net/$i/device 2>/dev/null)\"; done; "
    "echo '===ROUTE==='; ip route show 2>/dev/null | while read -r dst rest; do "
    "case \"$dst\" in 10.10.*) via=$(echo \"$rest\" | sed -n 's/.*via \\([0-9.]*\\).*/\\1/p'); "
    "met=$(echo \"$rest\" | sed -n 's/.*metric \\([0-9]*\\).*/\\1/p'); "
    "echo \"$dst ${via:-direct} ${met:-0}\";; esac; done; "
    "echo '===PING==='; for t in " + " ".join(NET_ENDS) + "; do "
    "printf '%s ' \"$t\"; ping -c1 -W1 -q \"$t\" >/dev/null 2>&1 && echo OK || echo FAIL; done; "
    # ⚠ 列序: `ps -eo rss,etimes,comm` ⇒ $1=rss(KB) · $2=etimes(秒) · $3+=comm
    #   `etimes_min_s` = **最年轻**那个 llama 系进程的年龄 —— O-143 的"刚起"读数。
    #   ★ 本项**只报数**（判据阈值待读数足够后再定，见 O-126「不许凭空取数」）。
    "echo '===PROC==='; ps -eo rss,etimes,comm 2>/dev/null "
    # ★ flash_serve = halogen 容器的推理进程 (2026-10-21 实测 B 站: host 侧可见, RSS ~77G);
    #   不纳入则"有端口 + 无 llama 系进程"会把它误判成"端口被占" (classify_engine_band)。
    "| grep -E 'llama-server|ggml-rpc-server|llama-cli|flash_serve' | grep -v grep "
    "| awk '{s+=$1; n++; if (n==1 || $2+0<m) m=$2+0} "
    "END {printf \"rss_mb=%d\\n\", s/1024; printf \"etimes_min_s=%d\\n\", m; "
    "printf \"n_proc=%d\\n\", n}'; "
    "echo '===LISTEN==='; ss -ltn 2>/dev/null | awk 'NR>1{print $4}' | sed 's/.*://' "
    "| grep -E '^(" + "|".join(ENGINE_PORTS) + ")$' | sort -u | tr '\\n' ','; echo; "
    # ★ O-146（2026-10-05）：**占用者是谁** —— 见 `classify_engine_occupant` 的注释（只报数）。
    "echo '===OCCUPANT==='; for P in " + " ".join(ENGINE_PORTS) + "; do "
    # ★ 2026-10-21: root 进程 (docker-proxy / systemd 起的引擎) 的 `users:(...)` 对普通用户
    #   **不可见** ⇒ 旧实现恒得 `unknown` (实测 B 站 halogen: sudo 前 unknown / sudo 后 docker-proxy)。
    #   故先 `sudo -n ss`，无免密 sudo 时回退普通 ss (仍可能 unknown —— 判不了 ≠ 通过)。
    "L=$(sudo -n ss -ltnp 2>/dev/null | awk -v s=\":$P\" '$4 ~ s\"$\"{print $NF}' | head -1); "
    "[ -z \"$L\" ] && L=$(ss -ltnp 2>/dev/null | awk -v s=\":$P\" '$4 ~ s\"$\"{print $NF}' | head -1); "
    "if [ -z \"$L\" ]; then printf 'occupant_%s=none\\n' \"$P\"; continue; fi; "
    "PID=$(printf '%s' \"$L\" | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2); "
    "E=$(readlink -f \"/proc/${PID:-0}/exe\" 2>/dev/null); "
    "C=$(tr '\\0' ' ' < \"/proc/${PID:-0}/cmdline\" 2>/dev/null | cut -c1-200); "
    "printf 'occupant_%s=%s\\n' \"$P\" \"${E:-unknown}\"; "
    "printf 'occupantcmd_%s=%s\\n' \"$P\" \"$C\"; done; "
    "echo '===MEM==='; awk '/MemTotal/{printf \"total_mb=%d \", $2/1024} "
    "/MemAvailable/{printf \"avail_mb=%d\", $2/1024}' /proc/meminfo; "
    "printf ' load1=%s' \"$(cut -d' ' -f1 /proc/loadavg)\"; "
    "printf ' loadgate=%s\\n' \"$(command -v load-gate >/dev/null 2>&1 && echo yes || echo no)\"; "
    "echo '===BINMD5==='; for f in " + " ".join(STATION_BINS) + "; do "
    "printf '%s=%s\\n' \"$f\" \"$(md5sum /usr/local/bin/$f 2>/dev/null | cut -d' ' -f1)\"; done; "
    # ★ 2026-10-22 (ADR-0014 #2 甲): 容器镜像 digest 漂移检查取数 —— 仅列**在跑**容器。
    #   输出 `name|Config.Image|RepoDigests`；无 docker/无容器 ⇒ 节为空（不判）。
    "echo '===IMG==='; for c in $(docker ps --format '{{.Names}}' 2>/dev/null); do "
    "i=$(docker inspect --format '{{.Config.Image}}' \"$c\" 2>/dev/null); "
    "d=$(docker inspect --format '{{.RepoDigests}}' \"$i\" 2>/dev/null); "
    "printf '%s|%s|%s\\n' \"$c\" \"$i\" \"$d\"; done"
)

_HEALTH_CACHE = {}


def _health_probe(st: str) -> dict:
    """单站合并采集 (链路/路由/连通/引擎/内存)。返回 {reachable, addr, link, route, ping, ...}。

    解析失败**显式标 reachable=False**, 绝不返回半份数据让下游误判
    (与 P1-4 的"解析失败不能表现成业务全错"同一原则)。
    """
    if st in _HEALTH_CACHE:
        return _HEALTH_CACHE[st]
    d = {"station": st, "reachable": False, "addr": {}, "link": {}, "route": {},
         "ping": {}, "rss_mb": None, "listen": [], "occupant": {}, "occupant_cmd": {},
         "mem": {}, "binmd5": {}, "containers": [], "raw": ""}
    sys.path.insert(0, str(ROOT / "ops"))
    try:
        import cluster
    except Exception as e:
        d["error"] = f"无法导入 cluster.py ({type(e).__name__}) — 该组需 paramiko"
        _HEALTH_CACHE[st] = d
        return d
    ok, out = cluster.ssh_run(st, _HEALTH_CMD, timeout=120)
    d["raw"] = out or ""
    if not ok:
        d["error"] = out
        _HEALTH_CACHE[st] = d
        return d
    d["reachable"] = True
    sec = _parse_health_sections(out)
    for line in sec.get("ADDR", []):
        p = line.split()
        if len(p) >= 2 and "/" in p[1]:
            d["addr"][p[0]] = p[1].split("/")[0]
    for line in sec.get("LINK", []):
        p = line.split()
        if len(p) >= 3:
            d["link"][p[0]] = {"mtu": p[1], "state": p[2], "dev": p[3] if len(p) >= 4 else ""}
    for line in sec.get("ROUTE", []):
        p = line.split()
        if len(p) >= 3:
            # ⚠ 同一目的地的**主备两条**路由必须并存 —— 早版按 dst 存单个 dict,
            # 后一条把前一条覆盖掉了, 于是"主备齐备"这件事根本查不出来
            # (2026-09-15 实测: A 站 10.10.11.0/24 的两条被压成一条, 误报主路由缺失)。
            d["route"].setdefault(p[0], []).append({"via": p[1], "metric": p[2]})
    for line in sec.get("PING", []):
        p = line.split()
        if len(p) >= 2:
            d["ping"][p[0]] = p[1]
    for line in sec.get("PROC", []):
        # rss_mb (合计) + etimes_min_s / n_proc (O-143 的"刚起"读数, 只报数不判 —— 见 _HEALTH_CMD 注)
        for _k in ("rss_mb", "etimes_min_s", "n_proc"):
            if line.startswith(_k + "="):
                try:
                    d[_k] = int(line.split("=", 1)[1])
                except ValueError:
                    pass
                break
    d["listen"] = [x for x in ",".join(sec.get("LISTEN", [])).split(",") if x]
    # ★ O-146：8080 占用者（**只报数**）—— `occupant_<port>=<exe 路径|none|unknown>`
    #   + `occupantcmd_<port>=<cmdline>`（⚠ 必须看 cmdline：studio 的监听进程是 python 启动器）
    for line in sec.get("OCCUPANT", []):
        if "=" in line:
            k, _, v = line.strip().partition("=")
            if k.startswith("occupantcmd_"):
                d["occupant_cmd"][k[len("occupantcmd_"):]] = v.strip()
            elif k.startswith("occupant_"):
                d["occupant"][k[len("occupant_"):]] = v.strip()
    mem_line = " ".join(sec.get("MEM", []))
    for tok in mem_line.split():
        if "=" in tok:
            k, _, v = tok.partition("=")
            d["mem"][k] = v
    # 站上件副本 md5 (name=hash) —— 与本次探测**同一条命令**取回, 零额外连接。
    # 值为空串 = 文件读不到(md5sum 失败) ⇒ 与"缺失"同义, 由判据那边报出来。
    for line in sec.get("BINMD5", []):
        if "=" in line:
            k, _, v = line.strip().partition("=")
            d["binmd5"][k] = v.strip()
    # 在跑容器: name|image|RepoDigests (2026-10-22, ADR-0014 #2 甲)
    for line in sec.get("IMG", []):
        p = line.strip().split("|", 2)
        if len(p) == 3 and p[0]:
            d["containers"].append({"name": p[0], "image": p[1], "digests": p[2]})
    _HEALTH_CACHE[st] = d
    return d


def _parse_health_sections(out):
    sec, cur = {}, None
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("===") and s.endswith("==="):
            cur = s.strip("=")
            sec[cur] = []
        elif cur:
            sec[cur].append(line)
    return {k: [x for x in v if x.strip()] for k, v in sec.items()}


def _net_doc():
    """读 inventory/net.yaml。缺失返回 {}; **解析失败抛异常**。"""
    if not INVENTORY_NET.is_file():
        return {}
    import yaml
    return yaml.safe_load(INVENTORY_NET.read_text(encoding="utf-8")) or {}


# ── 2026-10-10 · `usb4` 判据的**键**：物理端口（`tb_pci`），**不是**接口名 ─────────────
# 为什么：TB/USB4 的 netdev 名由**内核枚举顺序**决定 ⇒ 跨重启会翻。实测 B 站 2026-10-10 11:13 重启后
#   `thunderbolt0/1` **互换**（domain↔对端映射不变 · 地址仍在正确链路 · 8 向连通全绿），而旧判据按名字比对
#   ⇒ 报出 2 条"地址不符" = **标签层假红**（抓不到真故障，每次重启却被点亮；同型先例 2026-09-29 C 站）。
# ⇒ 键取 `tb_pci` = `/sys/class/net/<if>/device` realpath 里的 **PCI 函数**（`0000:XX:00.5|.6`）= **物理端口**：
#   跨重启不变；**换线/换口**才变 —— 那正是**该报红**的情形。真值侧见 `inventory/net.yaml` 头部同名段。
TB_PCI_RE = re.compile(r"/(\d{4}:[0-9a-f]{2}:\d{2}\.[0-7])/domain\d+/")


def tb_pci_of(dev_path):
    """**纯函数**：从 `/sys/class/net/<if>/device` 的 realpath 里取 **PCI 函数**（= 物理端口标识）。

    实测样例（B 站 2026-10-10）：`/sys/devices/pci0000:00/0000:00:08.3/0000:c8:00.5/domain0/0-0/0-2/0-2.0`
    ⇒ `0000:c8:00.5`。**取不到 ⇒ `None`**（判不了 —— 绝不回落成"按接口名比"）。
    """
    m = TB_PCI_RE.search(str(dev_path or ""))
    return m.group(1) if m else None


def usb4_pick_iface(link_map, end):
    """**纯函数**：把 `net.yaml` 的一个端点接到**站上实测**的 thunderbolt 接口上。返回 `(iface|None, reason)`。

    键 = `tb_pci`（物理端口）。**fail-closed 三态，都不是通过**：
      · 登记缺 `tb_pci` ⇒ 键不完整，判不了；· 站上无该 pci ⇒ 端口没枚举 / 换了口；· 命中多个 ⇒ 真值有歧义。
    """
    want = str((end or {}).get("tb_pci") or "").strip()
    if not want:
        return None, "登记缺 `tb_pci`（键不完整 ⇒ **判不了**；见 net.yaml 头部 2026-10-10 段）"
    seen, hits = [], []
    for nm, lk in (link_map or {}).items():
        pci = tb_pci_of((lk or {}).get("dev"))
        seen.append(f"{nm}={pci or '非TB/取不到'}")
        if pci == want:
            hits.append(nm)
    if not hits:
        return None, (f"站上没有 pci={want} 的接口（实测: {', '.join(sorted(seen)) or '无 thunderbolt 接口'}）"
                      f" —— 端口未枚举 / 该段的接线或端口变了")
    if len(hits) > 1:
        return None, f"pci={want} 命中多个接口: {', '.join(sorted(hits))} ⇒ 真值有歧义"
    return hits[0], ""


def check_usb4(ctx):
    """USB4 三角环链路: 地址/MTU/接口状态 + 六向直连 + 主备回程路由 + 跨段生效性。"""
    if not INVENTORY_NET.is_file():
        return "WARN", "inventory/net.yaml 缺失 (链路真值未建)", []
    try:
        doc = _net_doc()
    except Exception as e:
        return "FAIL", f"net.yaml 解析失败: {type(e).__name__}: {str(e)[:180]}", []

    detail, warn, info = [], [], []
    live = {st: _health_probe(st) for st in ("A", "B", "C")}
    reach = [st for st in ("A", "B", "C") if live[st]["reachable"]]
    for st in ("A", "B", "C"):
        if not live[st]["reachable"]:
            detail.append(f"{st} 站不可达/采集失败: {live[st].get('error') or live[st].get('raw', '')[:120]}")

    n_addr = n_ping = n_route = n_keyed = 0
    for seg in doc.get("segments") or []:
        if not isinstance(seg, dict):
            continue
        name, want_mtu = seg.get("name", "?"), str(seg.get("mtu") or "")
        for end in seg.get("ends") or []:
            st = str((end or {}).get("station"))
            ip = str((end or {}).get("ip") or "")
            if not st or not ip:
                detail.append(f"net.yaml 段 {name} 的端点字段不全: {end}")
                continue
            if st not in reach:
                continue
            n_addr += 1
            # ★ 2026-10-10：键从 `iface`(名字，跨重启会翻) 换成 `tb_pci`(物理端口) —— 见本文件同名注释段。
            got_if, why = usb4_pick_iface(live[st]["link"], end)
            if not got_if:
                detail.append(f"{st} 站 {name} 段端点接不上（真值 ip={ip} · "
                              f"键 tb_pci={end.get('tb_pci') or '(缺)'}）—— {why}")
                continue
            n_keyed += 1
            tag = f"pci={end.get('tb_pci')}（今名 {got_if}）"
            got = live[st]["addr"].get(got_if)
            if got != ip:
                detail.append(f"{st} 站 {tag} 地址 = {got or '(无)'}, 真值 {ip} —— **地址挂在物理端口上不符**："
                              f"地址跟错链路(真故障) / 或该段接线换过(旧判据在此按名字比 ⇒ 名字一变就假报)")
            lk = live[st]["link"].get(got_if) or {}
            if want_mtu and lk.get("mtu") != want_mtu:
                detail.append(f"{st} 站 {tag} MTU = {lk.get('mtu')}, 真值 {want_mtu}")
            if lk.get("state") != "up":
                detail.append(f"{st} 站 {tag} 状态 = {lk.get('state')} (应为 up)")

    # 六向直连: 每站 ping 它两个直连对端 (对端地址从线段两端推导)
    for seg in doc.get("segments") or []:
        if not isinstance(seg, dict):
            continue
        ends = [e for e in (seg.get("ends") or []) if isinstance(e, dict)]
        if len(ends) != 2:
            continue
        for i in (0, 1):
            me, peer = ends[i], ends[1 - i]
            st, tip = str(me.get("station")), str(peer.get("ip") or "")
            if st not in reach or not tip:
                continue
            n_ping += 1
            if live[st]["ping"].get(tip) != "OK":
                detail.append(f"{st} → {tip} ({seg.get('name')} 段直连对端) ping 不通 —— "
                              f"链路级问题, 先查 thunderbolt 枚举(见归档 §6.5)")

    # 主备回程路由: 主备**两条都要**(缺主路由实测降级 268×, 缺回程路由 100% 丢包)
    for r in doc.get("routes") or []:
        if not isinstance(r, dict):
            continue
        st, dst = str(r.get("station")), str(r.get("dst") or "")
        if st not in reach or not dst:
            continue
        got = live[st]["route"].get(dst) or []
        have = ", ".join(f"via {g['via']} m{g['metric']}" for g in got) or "无"
        for kind in ("primary", "backup"):
            spec = r.get(kind) or {}
            n_route += 1
            via, met = str(spec.get("via") or ""), str(spec.get("metric") or "")
            match = [g for g in got if g.get("via") == via]
            if not match:
                detail.append(f"{st} 站缺到 {dst} 的**{kind}**路由 (应 via {via} metric {met}); "
                              f"实有: {have} —— 见 inventory/net.yaml 的 routes 段 / 归档 §6.6")
            elif met and all(g.get("metric") != met for g in match):
                # metric 不符按 **FAIL** 判: 主备的 metric 决定优先级, 颠倒后跨段流量会走
                # 备路由(经第三方中转) —— 实测 9.46Gb/s → 35Mb/s (268×), 属功能回退而非风味问题。
                detail.append(f"{st} 站到 {dst} 的 {kind} 路由 (via {via}) metric="
                              f"{match[0].get('metric')}, 真值 {met} —— metric 决定主备优先级, "
                              f"不符会让跨段流量走错路径(实测降级 268×)")
    for st in reach:
        if st in {str(r.get("station")) for r in (doc.get("routes") or [])
                  if isinstance(r, dict)}:
            info.append(f"{st} 站到非直连段的路由: " +
                        "; ".join(f"{k} → " + ", ".join(f"via {g['via']} m{g['metric']}"
                                                        for g in v)
                                  for k, v in sorted(live[st]["route"].items())))

    # 跨段主路由生效性
    for cx in doc.get("cross_checks") or []:
        if not isinstance(cx, dict):
            continue
        st, tip = str(cx.get("from")), str(cx.get("to") or "")
        if st not in reach or not tip:
            continue
        n_ping += 1
        if live[st]["ping"].get(tip) != "OK":
            detail.append(f"{st} → {tip} 不通 ({cx.get('why')}) —— 跨段主路由未生效")

    note = (f"链路: 可达 {len(reach)}/3 站 · 地址 {n_addr} 端 · 连通 {n_ping} 向 · "
            f"路由 {n_route} 条(主备) · 段 {len(doc.get('segments') or [])} · "
            f"按物理端口对上 {n_keyed}/{n_addr}")
    if detail:
        return "FAIL", note, info + detail + [f"(WARN) {w}" for w in warn]
    if warn:
        return "WARN", note, info + warn
    return "PASS", note, info


def check_gates(ctx):
    """内存门禁: load-gate 可用性 + 当前余量 + loadavg。"""
    detail, warn, info = [], [], []
    live = {st: _health_probe(st) for st in ("A", "B", "C")}
    reach = [st for st in ("A", "B", "C") if live[st]["reachable"]]
    for st in ("A", "B", "C"):
        if not live[st]["reachable"]:
            detail.append(f"{st} 站不可达/采集失败: {live[st].get('error')}")

    bin_ok = bin_bad = 0
    for st in reach:
        mem = live[st]["mem"]
        try:
            total, avail = int(mem["total_mb"]), int(mem["avail_mb"])
        except (KeyError, ValueError):
            detail.append(f"{st} 站内存读数异常: {mem}")
            continue
        used = total - avail                      # 与站上 load-gate 同口径(used = total - avail)
        headroom = avail // 1024 - 12             # 12G 安全垫(load-gate 的 saf_mb)
        info.append(f"{st} 站 total {total // 1024}G / used {used // 1024}G / "
                    f"avail {avail // 1024}G → 单模型可加载上限约 {headroom}G")
        try:
            if float(mem.get("load1", 0)) > 8:
                warn.append(f"{st} 站 loadavg1={mem.get('load1')} > 8 —— 与 load-gate 同阈值, "
                            f"此时加载会明显变慢")
        except ValueError:
            pass
        if mem.get("loadgate") != "yes":
            detail.append(f"{st} 站 load-gate 不可用 (command -v 取不到) —— 站上加载门禁失效")
        if headroom <= 0:
            detail.append(f"{st} 站余量 {headroom}G ≤ 0 —— 当前**任何**模型都过不了门禁, "
                          f"需先卸载或清理残留")

        # ── 站上件部署一致性 (2026-09-22 裁定接入) ──────────────────────
        # 判据: `STATION_BINS` 里每个站上件, 三站副本必须**逐字节等于**仓库副本。
        # 为什么判 FAIL 而不是 WARN: 这是"**站上跑的不是我们 review 过的那份**" ——
        #   与本站 `stations` 断言(conf/凭据/端口不符即以站上实况改仓库侧)同一性质, 不是"判不准的噪声"。
        # 快照语义: 期望值取**仓库副本当前内容**(运行期算 md5) ⇒ "改了仓库还没部署"也会被判出来 ——
        #   这正是要的: 该件改仓库**不生效**, 必须走「改仓库 → 核对 → 部署」。
        got = live[st].get("binmd5") or {}
        for name in STATION_BINS:
            src = ROOT / "ops" / "station-bin" / name
            if not src.is_file():
                bin_bad += 1
                detail.append(f"STATION_BINS 里的 {name} 在仓库副本不存在 —— 清单该改(不是站上的问题)")
                continue
            exp = hashlib.md5(src.read_bytes()).hexdigest()
            have = got.get(name, "")
            if not have:
                bin_bad += 1
                detail.append(f"{st} 站 /usr/local/bin/{name} 取不到 md5 —— 站上缺件或读不到(权限)")
            elif have != exp:
                bin_bad += 1
                detail.append(f"{st} 站 /usr/local/bin/{name} 与仓库副本**不一致** "
                              f"(站上 {have[:8]}… / 仓库 {exp[:8]}…) —— 这是**站上件**, "
                              f"改仓库副本不生效: 核对后二选一(部署仓库版 / 回滚站上版)")
            else:
                bin_ok += 1

    note = (f"内存门禁: 可达 {len(reach)}/3 站 · "
            f"最小余量 {min([int(live[s]['mem'].get('avail_mb', 0)) // 1024 - 12 for s in reach] or [0])}G · "
            f"站上件一致 {bin_ok}/{bin_ok + bin_bad}")
    if detail:
        return "FAIL", note, info + detail + [f"(WARN) {w}" for w in warn]
    if warn:
        return "WARN", note, info + warn
    return "PASS", note, info


def check_engine(ctx):
    """引擎态: 就绪 + **残留检测**(内存被占着但没有服务)。

    全站停机**不是失败** —— 本项目是"零自加载"方针, 引擎按需启停。
    真正要抓的是"占着内存却没有服务": 本会话实测踩到过一次 A 站 62.6G 的测试残留,
    它污染了后续所有内存判定 (预估被误报 NO_FIT)。
    """
    detail, warn, info = [], [], []
    live = {st: _health_probe(st) for st in ("A", "B", "C")}
    reach = [st for st in ("A", "B", "C") if live[st]["reachable"]]
    running = 0
    for st in ("A", "B", "C"):
        if not live[st]["reachable"]:
            detail.append(f"{st} 站不可达/采集失败: {live[st].get('error')}")
    for st in reach:
        rss = live[st]["rss_mb"] or 0
        ports = live[st]["listen"]
        n_proc = live[st].get("n_proc")
        age = live[st].get("etimes_min_s")
        # ★★ O-143 乙（2026-10-03）：**判定集中到 `classify_engine_band`（唯一定义点）** ——
        #   本循环只负责**取数 + 呈现**：`info`/`note` 是报数，`detail`/`warn` 才来自判定。
        band, why = classify_engine_band(bool(ports), rss, n_proc)
        if ports:
            running += 1
            # ★ O-146（2026-10-05）：**占用者是哪条路径的引擎** —— 只报数（`classify_engine_occupant`
            #   是唯一定义点；**不参与 `classify_engine_band` 的判定**）。取不到 ⇒ `unknown`。
            _occ = live[st].get("occupant") or {}
            _ocmd = live[st].get("occupant_cmd") or {}
            _occ_txt = " ".join(
                f"{_p}:{classify_engine_occupant(_occ.get(_p, 'unknown'), listening=True, cmdline=_ocmd.get(_p, ''))}"
                for _p in ports)
            info.append(f"{st} 站引擎在服务: 端口 {','.join(ports)} · 进程 RSS {rss // 1024}G"
                        + (f" · 进程数 {n_proc}" if isinstance(n_proc, int) else "")
                        + (f" · 最短进程龄 {age}s"
                           if isinstance(age, int) and isinstance(n_proc, int) and n_proc > 0 else "")
                        + (f" · 占用者 {_occ_txt}" if _occ_txt else ""))
            # ★★ O-146 乙′（2026-10-05 裁定）：**占用者进判定** —— 作用域 = `ports.yaml` 驱动的引擎 API 端口。
            for _p in ports:
                if _p not in _engine_api_ports():
                    continue
                _k = classify_engine_occupant(_occ.get(_p, "unknown"), listening=True,
                                              cmdline=_ocmd.get(_p, ""))
                if _k in ("other", "unknown"):
                    _why = "认不出的形态" if _k == "other" else "取不到（判不了 ≠ 通过）"
                    warn.append(f"{st} 站引擎端口 {_p} 占用者**未登记/不可判**（{_k} = {_why}）"
                                f" —— 允许形态 {','.join(_OCCUPANT_OK)}；见 O-146")
        else:
            info.append(f"{st} 站引擎未运行 (RSS {rss}M) —— 零自加载方针下属正常")
        if band == "FAIL":
            detail.append(f"{st} 站**残留**: {why}")
        elif band == "WARN":
            warn.append(f"{st} 站{why}")

    # ★ 2026-10-22 (ADR-0014 #2 甲): 容器镜像 **digest 漂移** —— 只判**在跑**的已登记容器。
    #   pin 的真值 = `CONTAINER_MODELS[alias].image` 里的 `@sha256:…`；tag 可重推，digest 才是制品身份。
    #   未运行 ⇒ 不判（零自加载方针：容器按需启停）。取不到 digest ⇒ 报"取不到"，不静默通过。
    try:
        sys.path.insert(0, str(ROOT / "ops"))
        from cluster_const import CONTAINER_MODELS as _CM
    except Exception:
        _CM = {}
    _pins = {s["name"]: s["image"].split("@", 1)[1]
             for s in _CM.values() if "@sha256:" in s.get("image", "")}
    for st in reach:
        for c in live[st].get("containers") or []:
            pin = _pins.get(c["name"])
            if not pin:
                continue
            if pin not in (c.get("digests") or ""):
                detail.append(f"{st} 站容器 {c['name']} 镜像 digest 与 pin 不符: "
                              f"期望 {pin} / 实际 {c.get('digests') or '取不到'}")

    _ages = [live[s].get("etimes_min_s") for s in reach
             if isinstance(live[s].get("etimes_min_s"), int)
             and (live[s].get("n_proc") or 0) > 0]   # ⚠ n_proc=0 的站不参与（否则 0 会污染 min）
    note = (f"引擎: 可达 {len(reach)}/3 站 · 在服务 {running} 站 · "
            f"总占用 {sum((live[s]['rss_mb'] or 0) for s in reach) // 1024}G"
            # ★ O-143 第一步：**只报数** —— 三站里最年轻的 llama 系进程年龄（判据判不了"刚起"时至少看得见）
            + (f" · 最短进程龄 {min(_ages)}s" if _ages else ""))
    if detail:
        return "FAIL", note, info + detail + [f"(WARN) {w}" for w in warn]
    if warn:
        return "WARN", note, info + warn
    return "PASS", note, info


# ── 引擎后端 + 回滚基线 (2026-09-17 新增) ───────────────────────────
# 为什么必须有这条: 原 14 项里**没有任何一项判定"HIP 还是 Vulkan"** —— `engine` 只查进程
#   残留/内存, `stations` 只对账 conf/端口/凭据/插件。后果**已经发生过**: 台账 §1 的
#   "对本集群影响"曾整片按"本集群 = Vulkan / 无 ROCm"写错, 而门禁 13 绿照过
#   (2026-09-17 订正, 见 TRACKER §2.6)。
# 判据(全部可机械判定, 不需要人读; 且都落到**二进制**而非配置文本):
#   (a) 三站 studio 自带引擎在位, 且 ldd 含 libggml-hip         <- 默认单站加载路径的后端
#   (b) 三站 /opt 的 llama-server 与 ggml-rpc-server 均含 libggml-vulkan <- 分布式路径后端
#   (c) 三站 studio 自带 ROCm 运行时版本串一致                  <- 防 studio 静默换 SDK 致三站分叉
#   (d) 三站回滚基线 /opt/llama.cpp-9859 在位                   <- UPGRADE_SOP §6 要求(实测 C 站曾缺失)
_BACKEND_CMD = (
    "echo '===STUDIO==='; "
    "B=\"$HOME/.unsloth/llama.cpp/build/bin/llama-server\"; "
    "if [ -x \"$B\" ]; then "
    "echo 'studio_exe=yes'; "
    "printf 'studio_ggml=%s\\n' \"$(ldd \"$B\" 2>/dev/null | grep -oE 'libggml-(hip|vulkan|cpu)[.]so' | sort -u | tr '\\n' ',')\"; "
    "printf 'studio_rocm=%s\\n' \"$(ls -1 \"$HOME/.unsloth/llama.cpp/build/bin\" 2>/dev/null | grep -oE 'libamdhip64[.]so[.][0-9][0-9.]*' | sort -uV | tail -1)\"; "
    "else echo 'studio_exe=no'; fi; "
    "echo '===OPT==='; "
    "printf 'opt_link=%s\\n' \"$(basename \"$(readlink -f /opt/llama.cpp 2>/dev/null)\")\"; "
    "for n in llama-server ggml-rpc-server; do "
    "P=\"/opt/llama.cpp/$n\"; "
    "if [ -x \"$P\" ]; then "
    "printf 'opt_%s=%s\\n' \"$n\" \"$(ldd \"$P\" 2>/dev/null | grep -oE 'libggml-(hip|vulkan)[.]so' | sort -u | tr '\\n' ',')\"; "
    "else printf 'opt_%s=missing\\n' \"$n\"; fi; "
    "done; "
    "echo '===ROLLBACK==='; "
    "printf 'rollback=%s\\n' \"$(ls -d /opt/llama.cpp-9859 2>/dev/null || echo missing)\"; "
    # ── (e)-(h) 2026-09-23 增: studio 套件的"防线/修复/同版/复原路径" ──────────
    # 为什么加: 2026-09-22 的 A 站翻转事故里, **引擎后端被 update 静默翻转**这件事
    #   是靠人工发现的, 而门禁当时只判"后端类型"(即 (a)) —— 它连"我们事先下的
    #   pin 是否真的生效"都不判。本轮把这四类事实变成取数, 判据见 check_backend。
    "echo '===SUITE==='; "
    "printf 'pin_file=%s\\n' \"$(grep -E '^UNSLOTH_LLAMA_CPP_BACKEND=' /etc/environment 2>/dev/null | tail -1 | cut -d= -f2-)\"; "
    "printf 'pin_seen=%s\\n' \"$(printenv UNSLOTH_LLAMA_CPP_BACKEND 2>/dev/null)\"; "
    "S=\"$HOME/.unsloth/studio/unsloth_studio/lib/python3.13/site-packages\"; "
    "printf 'studio_ver=%s\\n' \"$(ls -d \"$S\"/unsloth-[0-9]*.dist-info 2>/dev/null | sed -E 's|.*/unsloth-(.+)[.]dist-info|\\1|' | sort -V | tail -1)\"; "
    "printf 'events_files=%s\\n' \"$(grep -rl 'X-Unsloth-Events' \"$S/studio\" 2>/dev/null | wc -l)\"; "
    "printf 'engine_md5=%s\\n' \"$(md5sum \"$HOME/.unsloth/llama.cpp/build/bin/llama-server\" 2>/dev/null | cut -d' ' -f1)\"; "
    "printf 'engine_bak=%s\\n' \"$(ls -d \"$HOME/.unsloth/llama.cpp.\"* 2>/dev/null | xargs -r -n1 basename 2>/dev/null | tr '\\n' ',')\""
)
_EXPECT_STUDIO_BACKEND = "libggml-hip.so"      # 默认单站加载 = HIP/ROCm
_EXPECT_LLAMA_BACKEND = "rocm"                 # /etc/environment 里 pin 的期望值 (2026-09-23 增)
_EXPECT_DIST_BACKEND = "libggml-vulkan.so"     # 分布式 / RPC = Vulkan


def check_backend(ctx):
    """引擎后端(默认单站=HIP / 分布式=Vulkan) + 三站同构 + 回滚基线在位。"""
    sys.path.insert(0, str(ROOT / "ops"))
    try:
        import cluster
    except Exception as e:
        return ("WARN", f"无法导入 cluster.py ({type(e).__name__}) — 该项需 paramiko; "
                        f"请用装有 paramiko 的 Python 运行", [])

    detail, warn, info = [], [], []
    per = {}
    for st in ("A", "B", "C"):
        ok, out = cluster.ssh_run(st, _BACKEND_CMD, timeout=60)
        if not ok:
            detail.append(f"{st} 站不可达/采集失败: {out}")
            continue
        d = {}
        for line in (out or "").splitlines():
            if "=" in line and not line.startswith("==="):
                k, _, v = line.partition("=")
                d[k.strip()] = v.strip()
        # 采集成功但关键字段全缺 = 解析失败, 不能当"没问题"
        if not d.get("studio_exe") and not d.get("opt_link"):
            detail.append(f"{st} 站采集输出无法解析 (不做判定): {(out or '')[:120]!r}")
            continue
        per[st] = d

    rocm = {}
    for st, d in per.items():
        s_ggml = d.get("studio_ggml", "")
        if d.get("studio_exe") != "yes":
            detail.append(f"{st} 站 **默认单站引擎缺失**: ~/.unsloth/llama.cpp/build/bin/llama-server "
                          f"不可执行 —— `infer-load`(缺省 backend=unsloth) 会直接加载失败")
        elif _EXPECT_STUDIO_BACKEND not in s_ggml:
            detail.append(f"{st} 站 默认单站引擎**后端不是 HIP**: ldd=[{s_ggml}] "
                          f"(期望含 {_EXPECT_STUDIO_BACKEND}) —— 单站路径实际后端已变, "
                          f"台账 §2.6 的后端矩阵必须同步")
        else:
            info.append(f"{st} 站 默认单站 = HIP ✓ ({s_ggml.strip(',')})")
        rocm[st] = d.get("studio_rocm", "")
        for n in ("llama-server", "ggml-rpc-server"):
            v = d.get(f"opt_{n}", "")
            if v in ("", "missing"):
                detail.append(f"{st} 站 /opt/llama.cpp/{n} 不可执行 —— 分布式路径缺件")
            elif _EXPECT_DIST_BACKEND not in v:
                detail.append(f"{st} 站 /opt/llama.cpp/{n} **后端不是 Vulkan**: ldd=[{v}] "
                              f"(期望含 {_EXPECT_DIST_BACKEND})")
        rb = d.get("rollback", "")
        if not rb or rb == "missing":
            detail.append(f"{st} 站 **回滚基线缺失** /opt/llama.cpp-9859 —— UPGRADE_SOP §6 要求"
                          f"保留 `<现役>` + `9859` 两个版本目录以支持分钟级回滚")
        else:
            info.append(f"{st} 站 回滚基线在位 ({rb})")

    # (c) 三站 studio ROCm 运行时一致 —— 取不到时**不判**(取不到 ≠ 不存在), 显式告警
    vals = sorted({v for v in rocm.values() if v})
    if len(vals) > 1:
        detail.append("三站 studio 自带 ROCm 运行时**不一致**: "
                      + " / ".join(f"{s}={rocm[s]}" for s in sorted(rocm))
                      + " —— 三站可能跑在**不同 HIP 版本**上 (studio 静默换 SDK)")
    elif len(vals) == 1:
        info.append(f"三站 studio ROCm 运行时一致 ({vals[0]})")
    else:
        warn.append("三站均未取到 studio 自带 ROCm 版本串 —— 不做一致性判定 (取不到 ≠ 不存在)")

    # ── (e) pin 在位且**本会话可见** (2026-09-23 增) ────────────────────
    # 判据取「printenv 读得到」而不是「文件里有行」：门禁自身的采集与 `studio update` 是
    # **同一类会话**(非交互 ssh)，故读得到 = 安装器也能读到；只写文件 ≠ 生效
    # (`~/.bashrc` 有 interactive 守卫、`~/.profile` 只被登录 shell 读 —— 见决策简报 §8.2)。
    pins = {s: d.get("pin_seen", "") for s, d in per.items()}
    pinf = {s: d.get("pin_file", "") for s, d in per.items()}
    bad_pin = sorted(s for s, v in pins.items() if v != _EXPECT_LLAMA_BACKEND)
    if bad_pin:
        shown = " / ".join(s + "=会话「" + (pins.get(s) or "(空)") + "」文件「" + (pinf.get(s) or "(无)") + "」"
                           for s in bad_pin)
        detail.append("**" + " / ".join(bad_pin) + " 站 pin 未生效** (非交互 ssh 会话读不到 "
                      "`UNSLOTH_LLAMA_CPP_BACKEND`)： " + shown
                      + " —— 期望「" + _EXPECT_LLAMA_BACKEND + "」。这是「引擎后端被 update 静默翻转」的"
                        "**唯一防线** (显式请求 = mandatory；marker 里的历史选择只是 advisory，探测不认即丢)；"
                        "落点应为 /etc/environment (经 pam_env 对非交互命令亦生效)，见决策简报 §8.2")
    else:
        info.append("pin 在位且会话可见 ✓ (" + _EXPECT_LLAMA_BACKEND + ")")

    # ── (f) X-Unsloth-Events 修复在位 (2026-09-23 增) ──────────────────
    # 缺 = 网关注入无 `choices` 的控制帧 ⇒ 本地 provider 的 compaction 必然失败 (上游 #10362；本仓 O-23)
    noev = sorted(s for s, d in per.items() if (d.get("events_files") or "0") == "0")
    if noev:
        detail.append("**" + " / ".join(noev) + " 站不含 `X-Unsloth-Events` 修复** —— 网关会注入无 `choices` "
                      "的控制帧 ⇒ 本地 provider 的 compaction 必然失败 (上游 unsloth#10362；本仓 O-23)。"
                      "修法 = 升级 studio，见决策简报 §三")
    else:
        info.append("`X-Unsloth-Events` 修复三站在位 ✓")

    # ── (g) studio 版本三站一致性 (不一致 = WARN：滚动升级中间态可接受，但必须可见) ──
    vers = sorted({d.get("studio_ver") for d in per.values() if d.get("studio_ver")})
    if len(vers) > 1:
        warn.append("三站 studio 版本**不一致**：" + " / ".join(
            s + "=" + (per[s].get("studio_ver") or "?") for s in sorted(per))
            + " —— 本仓既定形态是「三站同升」；滚动升级中间态可接受，但口径不一致必须可见")
    elif len(vers) == 1:
        info.append("三站 studio 版本一致 ✓ (" + vers[0] + ")")

    # ── (h) 引擎逐字节同版 ⇒ 站间 tar 复原路径可用 (不同版 = WARN，非 FAIL：各站仍可各自下载) ──
    md5s = sorted({d.get("engine_md5") for d in per.values() if d.get("engine_md5")})
    if len(md5s) > 1:
        warn.append("三站引擎**构建不同版** (md5 不一致)：" + " / ".join(
            s + "=" + (per[s].get("engine_md5") or "?")[:12] for s in sorted(per))
            + " —— 「从同版站 tar 复原」这条分钟级回滚路径不可用 (实测 1.9 G / 18 s)，预案须按逐站写")
    elif len(md5s) == 1:
        info.append("三站引擎逐字节同版 ✓ ⇒ 站间 tar 可复原 (md5 " + md5s[0][:12] + "…)")
    baks = {s: (d.get("engine_bak") or "").strip(",") for s, d in per.items()}
    info.append("引擎面备份目录 (" + "~/.unsloth/llama.cpp.*" + ")： " + " / ".join(
        s + "=" + (baks.get(s) or "(无 — 引擎若被替换，只能靠站间 tar 或重下)") for s in sorted(baks)))

    if not per:
        return "FAIL", "后端: 三站均采集失败", detail
    tip = vals[0] if len(vals) == 1 else " / ".join(f"{s}:{rocm.get(s) or '?'}" for s in sorted(rocm))
    note = f"后端: 可达 {len(per)}/3 站 · 单站=HIP / 分布式=Vulkan · ROCm {tip}"
    # 摘要行必须带上「防线 / 修复 / 同版」三件事 —— info 明细只在 FAIL/WARN 时渲染 (见 main),
    # PASS 时不可见；而这三件事恰是"没红也想知道"的 (如"pin 还在不在位")。
    note += (" · pin " + ("✓" if not bad_pin else "✗")
             + " · studio " + (vers[0] if len(vers) == 1 else ("/".join(vers) or "?"))
             + " · 引擎 " + ("同版" if len(md5s) == 1 else (str(len(md5s)) + " 版不同"))
             + " · 修复 " + ("✗" if noev else "✓"))
    if detail:
        return "FAIL", note, info + detail + [f"(WARN) {w}" for w in warn]
    if warn:
        return "WARN", note, info + warn
    return "PASS", note, info


def check_models(ctx):
    """模型库完整性: 孤儿(物理库有/聚合视图无) + 断链(软链目标不存在)。"""
    sys.path.insert(0, str(ROOT / "ops"))
    try:
        import cluster
    except Exception as e:
        return ("WARN", f"无法导入 cluster.py ({type(e).__name__}) — 该项需 paramiko", [])

    detail, info = [], []
    reach = 0
    tot_o = tot_b = 0
    for st in ("A", "B", "C"):
        m = cluster._scan_models(st)
        if not m:
            detail.append(f"{st} 站模型库扫描失败 (站不可达?)")
            continue
        reach += 1
        orp, brk = m["orphans"], m["broken"]
        tot_o += len(orp)
        tot_b += len(brk)
        info.append(f"{st} 站: 物理库 {len(m['phy'])} / 聚合视图 {len(m['agg'])} / "
                    f"孤儿 {len(orp)} / 断链 {len(brk)}")
        for x in orp:
            detail.append(f"{st} 站孤儿 {x} —— 物理库有、聚合视图无: **权重在但清单看不到、"
                          f"也加载不了**; 修: `cluster.py models link --go`")
        for x in brk:
            detail.append(f"{st} 站断链 {x} —— 聚合视图软链目标不存在; "
                          f"修: `cluster.py models prune --go`")

    note = f"模型库: 可达 {reach}/3 站 · 孤儿 {tot_o} · 断链 {tot_b}"
    if detail:
        return "FAIL", note, info + detail
    return "PASS", note, info



INVENTORY_DIR = ROOT / "inventory"
def load_inventory():
    """读 inventory/*.yaml。返回 (ports: {int: 条目}, models: {str: 条目})。"""
    try:
        import yaml
    except Exception:
        return None, None
    ports, models = {}, {}
    if not INVENTORY_DIR.is_dir():
        return ports, models
    for f in sorted(INVENTORY_DIR.glob("*.yaml")):
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        for group, items in doc.items():
            # 纯登记用的段不参与"已声明真值"计算 (否则 known_broken_conf 里的 alias
            # 会被当成正常模型键, 掩盖它其实是坏的)
            if group in ("known_issues", "known_drift", "known_broken_conf"):
                continue
            if not isinstance(items, list):
                continue
            for it in items:
                if not isinstance(it, dict):
                    continue
                if isinstance(it.get("port"), int):
                    ports[it["port"]] = {**it, "_group": group, "_file": f.name}
                for key in ("alias", "engine_id"):
                    if it.get(key):
                        models[str(it[key])] = {**it, "_group": group, "_file": f.name}
    return ports, models
