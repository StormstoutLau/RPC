#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cluster_catalog — `cluster.py` 的按域拆分模块（review-p2-cluster 阶段）。

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


# ── models: 模型全生命周期 (2026-09-15, 方案 v2 P1-2) ──────────────
# 模型资产在站上有**两条路径**:
#   物理库   ~/.lmstudio/models/<repo>/<model>/    权重真正存放处
#   聚合视图 /data/models/gguf/<repo>/<model>      infer-load / infer-list **只扫这里**
#     ├─ 软链 → 物理库（标准形态）
#     └─ 真目录（本地物理存放, 同样有效）
# 只要新模型进了物理库却漏建软链, 就会"文件在、清单里看不到、也加载不了"
# （2026-09-15 实测: B/C 站 MiniMax-M2.7、A 站 fable-5-distilled / GLM 都是此形态）。
# 本子命令把"检测孤儿 → 自动补链 → 查真断链"串成一条链, 根治这类静默遗漏。
_MODELS_SCAN = (
    "echo '===PHY==='; find -L ~/.lmstudio/models -mindepth 2 -maxdepth 2 -type d 2>/dev/null "
    "| sed 's|.*/models/||' | sort; "
    "echo '===AGG==='; find -L /data/models/gguf -mindepth 2 -maxdepth 2 -type d 2>/dev/null "
    "| sed 's|.*/gguf/||' | sort; "
    "echo '===BROKEN==='; find /data/models/gguf -mindepth 2 -maxdepth 2 -type l "
    "! -exec test -e {} \\; -print 2>/dev/null | sed 's|.*/gguf/||' | sort"
)


def _scan_models(st: str) -> dict:
    """站上模型资产三视图: {phy, agg, orphans, broken}（均为相对路径 repo/model）。

    orphans = 物理库有、聚合视图无（→ 清单看不到、infer-load 也找不到）
    broken  = 聚合视图里的**软链**指向不存在的目标（真断链; 注意：聚合视图里的
              **真目录**是有效的本地物理存放, 不算断链）
    """
    ok, out = ssh_run(st, _MODELS_SCAN, timeout=60)
    if not ok:
        return {}
    phy_part, _, rest = out.partition("===AGG===")
    agg_part, _, brk_part = rest.partition("===BROKEN===")
    phy = [x.strip() for x in phy_part.replace("===PHY===", "").splitlines() if x.strip()]
    agg = [x.strip() for x in agg_part.splitlines() if x.strip()]
    broken = [x.strip() for x in brk_part.splitlines() if x.strip()]
    aset = set(agg)
    return {"phy": phy, "agg": agg,
            "orphans": [x for x in phy if x not in aset],
            "broken": broken}


def _link_model(st: str, rel: str, dry: bool = False) -> str:
    """给孤儿模型补软链: /data/models/gguf/<repo>/<model> -> ~/.lmstudio/models/<repo>/<model>。"""
    repo, _, model = rel.partition("/")
    if not repo or not model:
        return f"跳过(路径异常): {rel}"
    src = f"$HOME/.lmstudio/models/{repo}/{model}"
    dst_dir = f"/data/models/gguf/{repo}"
    dst = f"{dst_dir}/{model}"
    if dry:
        return f"[dry-run] mkdir -p {dst_dir} && ln -s {src} {dst}"
    # 注意: src 必须用**双引号**包裹 —— 单引号会阻止 shell 展开 $HOME, 生成指向字面量
    # "$HOME/..." 的死链（2026-09-15 实测踩坑: 补链后 readlink 为空、断链 +2）。
    ok, out = ssh_run(st, f"mkdir -p '{dst_dir}' && ln -sfn \"{src}\" '{dst}' && "
                          f"readlink -f '{dst}' | head -1")
    return f"已链接 {rel} -> {(out.strip() if ok else '失败: ' + out.strip())}"


def _prune_link(st: str, rel: str, dry: bool = True) -> str:
    """删除死链: 聚合视图里的软链指向已不存在的目标（只删软链本身, 绝不碰真实文件）。

    安全性: 站上再次断言 `[ -L ] && [ ! -e ]` —— 必须是软链**且**目标不存在才删;
    任何真目录/有效软链都会被 skip 掉。
    """
    p = f"/data/models/gguf/{rel}"
    if dry:
        return f"[dry-run] rm -f {p}（仅当它是死链时）"
    ok, out = ssh_run(st, f"if [ -L '{p}' ] && [ ! -e '{p}' ]; then rm -f '{p}' && echo 'removed '"
                          f"$(readlink '{p}' 2>/dev/null || echo '(已删)'); else echo 'skip 非死链'; fi")
    return f"{rel}: {(out or '').strip()}"


# ── meta: 模型元数据 (已抽至 cluster_model.py, 阶段 1c 拆分) ──────────────
# 显式重导出 ⇒ cluster.py 内的 cmd_models 调用点与 cluster_web.py 用到的
# _MODEL_META_SCAN / alias_of / group_by_model / parse_model_meta /
# pick_representative / resolve_quant 均不变。实现改 ops/cluster_model.py。
from cluster_model import (  # noqa: E402
    _MODEL_META_SCAN, _QUANT_RE, INVENTORY_MODELS, MODELS_ROOT,
    alias_of, group_by_model, infer_quant, ledger_quant, parse_model_meta,
    pick_representative, probe_model_meta, resolve_quant,
)


# ── versions: 引擎版本矩阵 (2026-09-15, 方案 v2 P1-3) ──────────────
# 目的: 把"三站各引擎的实际版本/构建"摆到一屏, 暴露:
#   ① 版本漂移 (如 LM Studio C 站旧于 A/B)
#   ② 受控路径的完整性缺口 (如 MANIFEST.md5 缺失 → 硬规则要求的 md5sum -c 校验无法执行)
# 对齐 spec/vulkan-version-control 的 UPGRADE_SOP 溯源要求。
#
# 术语: 站上有**两个 llama.cpp 构建**, 用途不同, 不可混为一谈 ——
#   RPC 引擎   /opt/llama.cpp           受控路径, 只放 ggml-rpc-server + 库 (MANIFEST 管版本)
#   单机引擎   ~/llama.cpp/build/bin    单机 llama-server (--version 直读 commit)
#   ⚠ 2026-10-12: 单机引擎轴**已退役** (唯一消费方 conf 已归位 /opt; 三站目录已删) —— 见 _VER_SCAN 注。
_VER_SCAN = (
    "echo '===RPC==='; grep -E '^(commit|version|build_date|toolchain|rpc_protocol)[[:space:]]*=' "
    "/opt/llama.cpp/MANIFEST* 2>/dev/null | head -8; "
    # 完整性: 优先 MANIFEST.md5; 否则用 MANIFEST **自带**的校验段 —— 实测 MANIFEST 前 9 行是键值元数据,
    # md5 列表从第 10 行起 (check_llama_version.sh 也是 tail -n +10)。旧实现只找 MANIFEST.md5 ⇒ 三站
    # 全部显示"缺失", 明明校验数据就在 MANIFEST 里 —— 属"能力看着坏了其实数据在"的假阴性。
    # ⚠ `LC_ALL=C` 是必须的: 站上 LANG=zh_CN.UTF-8, md5sum 会打印"成功"而不是 "OK" ——
    #   按英文文本解析会把**全部通过**读成"全 FAILED"(实测踩到)。凡是解析命令输出的地方都要锁 locale
    #   (同 memory 里 "free 输出随 locale 变化 ⇒ 改读 /proc/meminfo" 那条教训)。
    "echo '===MD5==='; R=$(readlink -f /opt/llama.cpp 2>/dev/null || echo /opt/llama.cpp); "
    "if [ -f \"$R/MANIFEST.md5\" ]; then F=\"$R/MANIFEST.md5\"; SKIP=0; "
    "elif [ -f \"$R/MANIFEST\" ]; then F=\"$R/MANIFEST\"; SKIP=9; else F=; fi; "
    "if [ -n \"$F\" ]; then "
    "(cd \"$R\" && tail -n +$((SKIP+1)) \"$F\" | LC_ALL=C md5sum -c 2>&1 | grep -c ': OK$'); "
    "(cd \"$R\" && tail -n +$((SKIP+1)) \"$F\" | LC_ALL=C md5sum -c 2>&1 | grep 'FAILED' | head -3); "
    "else echo 'MISSING'; fi; "
    # ★ 2026-10-12: 单站引擎轴 (~/llama.cpp, Vulkan) **已退役** —— 该轴逐站本地构建、
    #   无 MANIFEST/门禁/回滚, 三站实测不可复现 (llama-server 同但 libggml-base/vulkan 各异);
    #   唯一消费方 2 个别名的 conf 已归位 /opt/llama.cpp, 三站目录已删 (tar 备份见
    #   /data/backup/single-engine-retire-20261012/) ⇒ 见 docs/2026-10-12_单站引擎轴不一致调研与统一方案.md。
    #   探针保留"存在则读"分支: 万一目录被重新建出 (旧脚本回光), 仍能显示其指纹而非静默空白。
    "echo '===SINGLE==='; "
    "if [ -x ~/llama.cpp/build/bin/llama-server ]; then "
    "  ~/llama.cpp/build/bin/llama-server --version 2>&1 | head -2; "
    "  git -C ~/llama.cpp rev-parse --short HEAD 2>/dev/null; "
    "else echo 'RETIRED'; fi; echo; "
    "echo '===LMS==='; grep -m1 -oE '\"version\": \"[^\"]+\"' "
    "/opt/LM-Studio/resources/app/package.json 2>/dev/null; "
    "echo '===OC==='; opencode --version 2>/dev/null | head -1; "
    "echo '===KERN==='; uname -r"
)


def probe_versions(st: str) -> dict:
    """单站引擎版本矩阵。返回 {rpc:{...}, single:{...}, lmstudio, opencode, kernel, md5}。"""
    d = {"station": st, "reachable": False, "rpc": {}, "single": {},
         "lmstudio": "?", "opencode": "?", "kernel": "?", "md5": "?"}
    ok, out = ssh_run(st, _VER_SCAN, timeout=60)
    if not ok:
        return d
    d["reachable"] = True

    def _seg(name, nxt):
        part = out.partition(f"==={name}===")[2]
        return part.partition(f"==={nxt}===")[0].strip() if nxt else part.strip()

    # MANIFEST 形如 `commit        = 91f6a6cf`（键与 = 之间多个空格）→ 用通用键值正则解析
    for line in _seg("RPC", "MD5").splitlines():
        m = re.match(r"^\s*(\w+)\s*=\s*(.+?)\s*$", line)
        if not m:
            continue
        k, v = m.group(1), m.group(2)
        if k == "commit":
            d["rpc"]["commit"] = v
        elif k == "version":
            d["rpc"]["version"] = v
        elif k == "rpc_protocol":
            d["rpc"]["rpc_protocol"] = v
        elif k == "build_date":
            d["rpc"]["built"] = v.split("(")[0].strip()

    md5raw = _seg("MD5", "SINGLE").splitlines()
    if md5raw:
        first = md5raw[0].strip()
        if first == "MISSING":
            d["md5"] = "缺失"
        else:
            try:
                n_ok = int(first)
            except ValueError:
                n_ok = 0
            bad = [x.strip() for x in md5raw[1:] if x.strip()]
            d["md5"] = f"{n_ok} OK" + (f" / {len(bad)} FAILED" if bad else "") if n_ok else "全 FAILED"

    sl = [x.strip() for x in _seg("SINGLE", "LMS").splitlines() if x.strip()]
    for x in sl:
        if x == "RETIRED":            # 2026-10-12 单站引擎轴已退役 (见 _VER_SCAN 注)
            d["single"]["retired"] = True
            d["single"]["version"] = "已退役"
            d["single"]["commit"] = "已退役"
        elif x.startswith("version:"):
            d["single"]["version"] = x.split(":", 1)[1].strip()
        elif x.startswith("built with"):
            d["single"]["toolchain"] = x
        elif re.fullmatch(r"[0-9a-f]{7,40}", x):
            d["single"]["commit"] = x

    lms = _seg("LMS", "OC")
    if lms:
        m = re.search(r'"version":\s*"([^"]+)"', lms)
        d["lmstudio"] = m.group(1) if m else "?"
    d["opencode"] = (_seg("OC", "KERN").splitlines() or ["?"])[0].strip()
    d["kernel"] = (_seg("KERN", None).splitlines() or ["?"])[0].strip()
    return d


def cmd_versions(argv) -> int:
    """cluster.py versions —— 三站引擎版本矩阵 (P1-3)。"""
    rows = {}
    threads = [threading.Thread(target=lambda s=st: rows.__setitem__(s, probe_versions(s)))
               for st in ("A", "B", "C")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for st in ("A", "B", "C"):
        d = rows.get(st) or {}
        if not d.get("reachable"):
            print(f"[cluster] {st} 站: 不可达")
            continue
        r, s = d.get("rpc", {}), d.get("single", {})
        print(f"\n=== {st} 站 ===")
        print(f"  RPC 引擎  (/opt/llama.cpp)   commit {r.get('commit','?')} · "
              f"{r.get('version','?')} · built {r.get('built','?')}"
              + (f" · rpc_protocol {r['rpc_protocol']}" if r.get("rpc_protocol") else ""))
        print(f"    完整性  md5sum -c (MANIFEST) {d.get('md5','?')}")
        if s.get("retired"):
            print("  单机引擎  (~/llama.cpp)       ★ 已退役 (2026-10-12 收敛到 /opt/llama.cpp)")
        else:
            print(f"  单机引擎  (~/llama.cpp)       commit {s.get('commit','?')} · "
                  f"{s.get('version','?')}")
        print(f"  LM Studio                     {d.get('lmstudio','?')}")
        print(f"  opencode                      {d.get('opencode','?')}")
        print(f"  内核                          {d.get('kernel','?')}")
    # 漂移比对
    print("\n=== 一致性检查 ===")
    for field, getter in (("RPC commit", lambda d: d.get("rpc", {}).get("commit")),
                          ("RPC rpc_protocol", lambda d: d.get("rpc", {}).get("rpc_protocol")),
                          # commit 短哈希长度随各站 git core.abbrev 而异 (0d18aaa vs 0d18aaa9),
                          # 实际是同一个 commit → 统一取前 7 位再比, 避免把长度差异误报成漂移
                          ("单机 commit", lambda d: (d.get("single", {}).get("commit") or "")[:7]),
                          ("LM Studio", lambda d: d.get("lmstudio")),
                          ("opencode", lambda d: d.get("opencode"))):
        vals = {getter(rows.get(x) or {}) for x in ("A", "B", "C")}
        if len(vals) == 1:
            print(f"  ✓ {field:<12} 三站一致 ({vals.pop()})")
        else:
            detail = " / ".join(f"{x}={getter(rows.get(x) or {})}" for x in ("A", "B", "C"))
            print(f"  ⚠ {field:<12} **漂移** {detail}")
    for st in ("A", "B", "C"):
        if (rows.get(st) or {}).get("md5") == "缺失":
            print(f"  ⚠ {st} 站 MANIFEST/MANIFEST.md5 缺失 → 无法执行 md5sum -c 完整性校验"
                  f"（硬规则要求: 引擎升级前必须重建 MANIFEST 且 md5sum -c 通过）")
        elif "/" in str((rows.get(st) or {}).get("md5", "")):
            print(f"  ⚠ {st} 站 完整性有失败项: {(rows.get(st) or {}).get('md5')}"
                  f" → 引擎文件被改动或升级未同步 (查 cluster.py versions 明细)")
    return 0


# ── studio 套件矩阵 (2026-09-23 增) ─────────────────────────────────────
# 为什么需要: 2026-09-22 的 A 站翻转事故里,「防线还在不在 / 修复在不在 / 三站是否同版」这三件
#   事全靠人工 ssh 拼证据。门禁 `backend` 现已判它们(红会拦), 但**没红时也要能看矩阵** ——
#   尤其回滚预案(引擎备份目录 + 站间 tar 可行性)与 marker 里**记录**的变体。
# 与 `versions` 的分工: `versions` 是**引擎**矩阵(RPC/单机/LM Studio/内核/commit);
#   本条是**studio 套件**(版本/修复/防线/引擎变体/复原路径)。
# 取数刻意**只用免引号模式**(`grep -oE` 抓形状 / `ls`+`sed`), 因为这条命令要经
#   python→paramiko→bash→`$()` 四层, 引号嵌套是本仓历史事故高发区。
_STUDIO_SCAN = (
    "echo '===SUITE==='; "
    "S=\"$HOME/.unsloth/studio/unsloth_studio/lib/python3.13/site-packages\"; "
    "M=\"$HOME/.unsloth/llama.cpp/UNSLOTH_PREBUILT_INFO.json\"; "
    "E=\"$HOME/.unsloth/llama.cpp/build/bin/llama-server\"; "
    "printf 'studio_ver=%s\\n' \"$(ls -d \"$S\"/unsloth-[0-9]*.dist-info 2>/dev/null | sed -E 's|.*/unsloth-(.+)[.]dist-info|\\1|' | sort -V | tail -1)\"; "
    "printf 'zoo_ver=%s\\n' \"$(ls -d \"$S\"/unsloth_zoo-*.dist-info \"$S\"/unsloth-zoo-*.dist-info 2>/dev/null | sed -E 's|.*/unsloth[-_]zoo-(.+)[.]dist-info|\\1|' | sort -V | tail -1)\"; "
    "printf 'pin=%s\\n' \"$(printenv UNSLOTH_LLAMA_CPP_BACKEND 2>/dev/null)\"; "
    "printf 'events=%s\\n' \"$(grep -rl X-Unsloth-Events \"$S/studio\" 2>/dev/null | wc -l)\"; "
    "printf 'engine_md5=%s\\n' \"$(md5sum \"$E\" 2>/dev/null | cut -d' ' -f1)\"; "
    "printf 'engine_bak=%s\\n' \"$(ls -d \"$HOME/.unsloth/llama.cpp.\"* 2>/dev/null | xargs -r -n1 basename 2>/dev/null | tr '\\n' ',')\"; "
    "printf 'marker_tag=%s\\n' \"$(grep -oE 'b[0-9]{5}' \"$M\" 2>/dev/null | head -1)\"; "
    "printf 'marker_asset=%s\\n' \"$(grep -oE 'app-b[0-9]+-[a-z0-9-]+-linux-x64-[a-z0-9-]+[.]tar[.]gz' \"$M\" 2>/dev/null | head -1)\"; "
    "printf 'marker_compiled=%s\\n' \"$(timeout -k 5 20 \"$E\" --version 2>&1 | grep -oE 'Clang [0-9.]+|GNU [0-9.]+' | head -1)\"; "
    # ⚠ 反斜杠一律写 `\\`：`\1` 在 Python 里是**八进制转义**(→ \x01)会把 sed 替换串毁掉,
    #   而 `\(` 只触发 SyntaxWarning(值仍对) —— 两者表现不同, 但都别写单个反斜杠。
    "printf 'devices=%s\\n' \"$(timeout -k 5 20 \"$E\" --list-devices 2>&1 | sed -n 's/^[[:space:]]*\\([A-Za-z][A-Za-z0-9]*[0-9]\\):.*/\\1/p' | tr '\\n' ',')\""
)


def probe_studio(st: str) -> dict:
    """单站 studio 套件矩阵 (只读)。不可达时只带 reachable=False。"""
    d = {"station": st, "reachable": False}
    ok, out = ssh_run(st, _STUDIO_SCAN, timeout=90)
    if not ok:
        return d
    d["reachable"] = True
    for line in (out or "").splitlines():
        if "=" in line and not line.startswith("==="):
            k, _, v = line.partition("=")
            d[k.strip()] = v.strip()
    return d


def cmd_studio(argv) -> int:
    """cluster.py studio status —— studio 套件三站矩阵 (只读)。

    看什么: 版本 / 修复在不在 / **防线(pin)在不在位** / 引擎同不同版 / 复原与备份路径。
    """
    what = (argv[0] if argv else "status")
    if what not in ("status", "-h", "--help"):
        print("用法: cluster.py studio status")
        return 2
    rows = {}
    threads = [threading.Thread(target=lambda s=st: rows.__setitem__(s, probe_studio(s)))
               for st in ("A", "B", "C")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for st in ("A", "B", "C"):
        d = rows.get(st) or {}
        if not d.get("reachable"):
            print(f"\n=== {st} 站 ===\n  不可达")
            continue
        comp = (" · " + d["marker_compiled"]) if d.get("marker_compiled") else ""
        print(f"\n=== {st} 站 ===")
        print(f"  studio        {d.get('studio_ver') or '?'}  · unsloth_zoo {d.get('zoo_ver') or '?'}")
        print(f"  修复          X-Unsloth-Events 命中 {d.get('events') or '0'} 个文件")
        print(f"  防线 pin      {d.get('pin') or '(未生效)'}   (期望 rocm; 见决策简报 §8.2)")
        print(f"  引擎          marker tag {d.get('marker_tag') or '?'} · 设备 {(d.get('devices') or '?').strip(',')}{comp}")
        print(f"  引擎 md5      {(d.get('engine_md5') or '?')[:16]}")
        print(f"  marker asset  {d.get('marker_asset') or '?'}")
        print(f"  备份目录      {(d.get('engine_bak') or '').strip(',') or '(无 — 引擎若被替换只能靠站间 tar 或重下)'}")

    print("\n=== 一致性 / 防线检查 ===")
    for label, key in (("studio 版本", "studio_ver"), ("unsloth_zoo", "zoo_ver"), ("引擎 md5", "engine_md5")):
        vals = {st: (rows.get(st) or {}).get(key) for st in ("A", "B", "C")}
        uniq = {v for v in vals.values() if v}
        if len(uniq) == 1:
            print(f"  ✓ {label:<12}三站一致 ({str(next(iter(uniq)))[:16]})")
        else:
            print(f"  ⚠ {label:<12}**不一致** "
                  + " / ".join(f"{s}={str(vals[s] or '?')[:16]}" for s in ("A", "B", "C")))
    pins = {st: (rows.get(st) or {}).get("pin") for st in ("A", "B", "C")}
    bad_pin = [s for s, v in pins.items() if v != "rocm"]
    print(("  ✓ " if not bad_pin else "  ⚠ ") + "防线 pin    "
          + ("三站均生效 (rocm)" if not bad_pin else "**未生效**: "
             + " / ".join(f"{s}={pins[s] or '(空)'}" for s in bad_pin)))
    evs = {st: (rows.get(st) or {}).get("events") for st in ("A", "B", "C")}
    noev = [s for s, v in evs.items() if not v or v == "0"]
    print(("  ✓ " if not noev else "  ⚠ ") + "修复在位    "
          + ("三站均有 X-Unsloth-Events" if not noev else "**缺失**: " + " / ".join(noev)))
    md5s = {st: (rows.get(st) or {}).get("engine_md5") for st in ("A", "B", "C")}
    if len({v for v in md5s.values() if v}) == 1:
        print("  ✓ 复原路径   三站引擎逐字节同版 ⇒ 可站间 tar (实测 1.9 G / 18 s)")
    else:
        print("  ⚠ 复原路径   三站引擎**不同版** ⇒ 站间 tar 不可用, 只能各自下载或依赖各自备份目录")
    return 0


def _cmd_models_meta(stations) -> int:
    """打印每站模型元数据表 (P1-6): 原生 ctx / 量化(含来源) / conf 加载参数。"""
    for st in stations:
        meta = probe_model_meta(st)
        gguf, params = meta["gguf"], meta["params"]
        if not gguf and not params:
            print(f"[cluster] {st} 站: 元数据采集失败（站上未部署 gguf-meta?）")
            continue
        groups = group_by_model(gguf)
        print(f"\n=== {st} 站 模型元数据 ===")
        print(f"  {_pad('模型目录', 46)} {_pad('原生ctx', 9, True)}  {_pad('量化', 15)} "
              f"{_pad('加载ctx', 9, True)} {_pad('后端', 13)} {_pad('port', 6, True)}  conf 参数")
        confs = set(params)
        for (repo, model), paths in sorted(groups.items()):
            rep = pick_representative(paths)
            m = gguf.get(rep, {})
            alias = alias_of(model or repo)
            q, qsrc = resolve_quant(alias, rep)
            p = params.get(alias, {})
            pstr = " ".join(f"{k}={v}" for k, v in
                            (("threads", p.get("threads")), ("n_cpu_moe", p.get("n_cpu_moe")),
                             ("rpc", p.get("rpc_target"))) if v)
            label = f"{repo}/{model}" if model else f"{repo}/ (仓库级直放)"
            if len(label) > 46:              # 对齐靠列宽, 超长就截断 (否则整表错位)
                label = label[:45] + "…"
            # D6-P3-1: `label` 可能是中文(如 `…/ (仓库级直放)`) ⇒ 必须按**显示宽度**填充
            print(f"  {_pad(label, 46)} {_pad(str(m.get('ctx') or '-'), 9, True)}  "
                  f"{_pad((q + '(' + qsrc + ')') if q else '-', 15)} "
                  f"{_pad(str(p.get('ctx') or '-'), 9, True)} {_pad(str(p.get('backend') or '-'), 13)} "
                  f"{_pad(str(p.get('port') or '-'), 6, True)}  {pstr}")
            confs.discard(alias)
        # conf 有、模型库无: 指向的权重可能已被删 (与 stations 断言的 (e) 子项呼应)
        for a in sorted(confs):
            if params[a].get("ctx") or params[a].get("port"):
                print(f"  [仅 conf 无模型目录] {a}")
    print()
    return 0


def cmd_models(argv) -> int:
    """cluster.py models {list|orphan|link|prune|verify|meta|fetch} [--station A|B|C] [--go]

    list   三站模型资产概览（物理库 / 聚合视图 / 孤儿 / 断链 计数）
    orphan 只列孤儿与断链详情（诊断用）
    link   给孤儿补软链（默认 dry-run, 加 --go 才写入; 可 --station 限定单站）
    prune  清理死链（默认 dry-run, 加 --go 才写入）
    verify 断链检查 + 主 gguf 可读性抽验（gguf-meta）
    meta   模型元数据表: 原生 ctx / 量化(含来源) / 站上 conf 加载参数 (P1-6)
    fetch  下发站上 `lm-download@<任务>` 下载任务（默认只出计划, --go 才下发; 见 _cmd_models_fetch）
    """
    act = (argv[0] if argv else "list").lower()
    if act not in ("list", "orphan", "link", "prune", "verify", "meta", "fetch"):
        print("用法: cluster.py models {list|orphan|link|prune|verify|meta|fetch} "
              "[--station A|B|C] [--go]")
        return 1
    if act == "fetch":          # fetch 自带参数解析（repo + 多个文件 + --mirror/--dir/--name）
        return _cmd_models_fetch(argv[1:])
    only, do_go = None, False
    for a in argv[1:]:
        if a in ("A", "B", "C") or (len(a) == 1 and a.upper() in ("A", "B", "C")):
            only = a.upper()
        if a == "--go":
            do_go = True
    stations = [only] if only else ["A", "B", "C"]

    if act == "meta":
        return _cmd_models_meta(stations)

    total_orphan = total_broken = 0
    for st in stations:
        m = _scan_models(st)
        if not m:
            print(f"[cluster] {st} 站: 扫描失败")
            continue
        orp, brk = m["orphans"], m["broken"]
        total_orphan += len(orp)
        total_broken += len(brk)
        if act == "list":
            print(f"[cluster] {st} 站: 物理库 {len(m['phy'])} / 聚合视图 {len(m['agg'])} / "
                  f"孤儿 {len(orp)} / 断链 {len(brk)}")
        elif act == "orphan":
            print(f"\n=== {st} 站 ===")
            print(f"  孤儿（物理库有、聚合视图无 → 清单看不到）: {len(orp)}")
            for x in orp:
                print(f"    ✗ {x}")
            print(f"  断链（软链目标不存在）: {len(brk)}")
            for x in brk:
                print(f"    ✗ {x}")
        elif act == "link":
            if not orp:
                print(f"[cluster] {st} 站: 无孤儿, 无需补链")
                continue
            print(f"[cluster] {st} 站: 待补 {len(orp)} 个" + ("" if do_go else "（dry-run, 加 --go 执行）"))
            for x in orp:
                print("    " + _link_model(st, x, dry=not do_go))
        elif act == "prune":
            if not brk:
                print(f"[cluster] {st} 站: 无死链, 无需清理")
                continue
            print(f"[cluster] {st} 站: 待清理 {len(brk)} 个死链"
                  + ("" if do_go else "（dry-run, 加 --go 执行）"))
            for x in brk:
                print("    " + _prune_link(st, x, dry=not do_go))
        elif act == "verify":
            print(f"\n=== {st} 站 ===")
            if not brk:
                print("  断链: 无 ✓")
            for x in brk:
                print(f"    ✗ 断链 {x}")
            if not m["agg"]:
                print("  聚合视图为空")
            else:
                probe = m["agg"][0]
                d = f"/data/models/gguf/{probe}"
                ok, out = ssh_run(st, f"F=$(find -L '{d}' -name '*.gguf' -size +1M 2>/dev/null | head -1); "
                                      f"[ -n \"$F\" ] && gguf-meta \"$F\" 2>/dev/null | grep -E '\"(arch|block_count)\"' "
                                      f"|| echo '(无可用 gguf)'")
                print(f"  抽验 {probe}:")
                for line in (out or "").splitlines():
                    print(f"    {line.strip()}")
    if act in ("list", "orphan"):
        print(f"\n[cluster] 合计: 孤儿 {total_orphan} / 断链 {total_broken}"
              + ("   → 用 `cluster.py models link --go` 修复孤儿" if total_orphan else "   ✓ 无遗漏"))
    return 0


# ── models fetch：把「下载」纳入唯一入口（ADR-0004 D3 路径①）─────────────
LM_DL_UNIT = "lm-download@"
LM_DL_TASKS = "/etc/lm-download/tasks"
LM_DL_UNIT_FILE = "/etc/systemd/system/lm-download@.service"
# 下载通道产物的属主归位目标 = 站上服务用户（与推理/管理面同一身份）。
# ★ 为什么必须显式 chown（2026-10-17 实测教训）：`lm-download@` 是 **root** oneshot，且本命令
#   用 `sudo -n mkdir` 建目录 ⇒ 目录归 root:root 755 ⇒ **服务用户对该目录只读** ⇒ 站上用户执行的
#   任何"改写目录内容"的动作（分片合并 / 改名 / 裁撤）都会失败 —— 实测 `llama-gguf-split --merge`
#   以 `std::__ios_failure`(SIGABRT) 中止，排查成本高（看着像工具坏了）。
#   只 chown **目录本身**（不做 -R）即足够：unlink / 建文件只需**父目录**写权限，文件保持
#   root 0644 不影响读取（推理面只读权重）。
# P2 #9: SERVICE_USER 从 cluster_const.STATIONS 派生（单一真值）；此处不再写字面量。


def _fetch_plan(repo, files, base, dl_dir, mirror):
    """离线可测的**纯函数**：repo/文件 → [任务]。

    ★ 为什么**一个任务一个 URL**：站上 `lm-download@.service` 的 `ExecStart` 只吃**一个** `${DL_URL}`
      （2026-10-17 实测该 unit 文件）⇒ GGUF 分片 + mmproj 这类多文件**必须拆成 N 个任务**，塞进同一 env 无解。
    ★ 为什么**必须走本通道**：`hf-mirror` 无 Xet 端点 ⇒ `hf download` 回落常规 HTTP ⇒ 撞 HF 的
      **>50 GB 常规下载上限**（ADR-0010 已实测踩过）；本单元是 aria2c `--max-connection-per-server=16
      --split=16 --min-split-size=64M --continue=true` 分段并行 + 断点续传（净速 ≈ hf-mirror 单流的 11×）。
    ★ `DL_DIR` 缺省落在**聚合视图** `/data/models/gguf/<owner>/<repo>`，与既有落点约定一致（手册 §5.7）。
    """
    owner, _, rname = repo.partition("/")
    rname = rname or owner
    dl = dl_dir or f"/data/models/gguf/{owner}/{rname}"
    host = "https://huggingface.co" if mirror == "hf" else "https://hf-mirror.com"
    out = []
    for i, f in enumerate(files, 1):
        task = base if len(files) == 1 else f"{base}-{i}"
        env = [f"# {task} — 由 `cluster.py models fetch` 下发（统一入口; ADR-0004 D3①）",
               f"# repo: {repo}",
               f"# file: {f}",
               f"DL_URL={host}/{repo}/resolve/main/{f}",
               f"DL_DIR={dl}",
               f"DL_OUT={f.rsplit('/', 1)[-1]}"]
        out.append({"task": task, "url": f"{host}/{repo}/resolve/main/{f}", "dir": dl, "env": env})
    return out


def _cmd_models_fetch(argv) -> int:
    """cluster.py models fetch <repo> <文件> [<文件>...] --station A|B|C
    [--name 任务名] [--dir DL_DIR] [--mirror hf-mirror|hf] [--go]

    ★ 默认只出计划；`--go` 才下发（与 link / prune / containers 同纪律）。
    ★ 用 `systemctl start --no-block`：单元是 `Type=oneshot` ⇒ 不带 `--no-block` 会在**整个下载过程**阻塞。
    """
    pos, station, base, dl_dir, mirror, go = [], None, None, None, "hf-mirror", False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--station", "--name", "--dir", "--mirror") and i + 1 < len(argv):
            v = argv[i + 1]
            if a == "--station":
                station = v.upper()
            elif a == "--name":
                base = v
            elif a == "--dir":
                dl_dir = v
            else:
                mirror = v
            i += 2
            continue
        if a == "--go":
            go = True
            i += 1
            continue
        pos.append(a)
        i += 1
    if len(pos) < 2:
        print("用法: cluster.py models fetch <repo> <文件> [<文件>...] --station A|B|C "
              "[--name 任务名] [--dir DL_DIR] [--mirror hf-mirror|hf] [--go]")
        return 1
    repo, files = pos[0], pos[1:]
    if "/" not in repo:
        print("[models fetch] <repo> 需为 `<owner>/<name>` 形态（如 unsloth/Foo-GGUF）")
        return 1
    if "'" in repo or any("'" in f for f in files):
        print("[models fetch] repo/文件名含单引号 ⇒ 会被远端下发命令截断，拒绝执行")
        return 1
    if station not in ("A", "B", "C"):
        print("[models fetch] 必须显式 --station A|B|C（落盘站）。实测 2026-10-17: B 站已装该单元，C 站无 tasks 目录")
        return 1
    if base is None:
        base = repo.split("/")[-1].replace("-GGUF", "").lower() or "model"
    plan = _fetch_plan(repo, files, base, dl_dir, mirror)
    print(f"[models fetch] {repo} → {station} 站 · {len(plan)} 个任务（mirror={mirror}）"
          + ("" if go else "   （计划 · --go 才下发）"))
    for t in plan:
        print(f"\n  ── 任务 {t['task']} —— {t['url']}")
        print(f"    {LM_DL_TASKS}/{t['task']}.env:")
        for ln in t["env"]:
            print(f"      {ln}")
        print(f"    $ sudo -n mkdir -p '{t['dir']}' && sudo -n chown {SERVICE_USER}:{SERVICE_USER} '{t['dir']}'")
        print(f"    $ sudo -n systemctl start --no-block {LM_DL_UNIT}{t['task']}")
    if not go:
        print(f"\n  提示: 加 --go 下发；进度 `journalctl -u {LM_DL_UNIT}<任务> -f`")
        return 0
    ok, out = ssh_run(station, f"[ -f {LM_DL_UNIT_FILE} ] && echo UNIT_OK || echo UNIT_MISSING", timeout=60)
    if "UNIT_OK" not in (out or ""):
        print(f"[models fetch] ✗ {station} 站无 {LM_DL_UNIT_FILE} ⇒ 该站未接下载通道（先装单元，或换站）")
        return 1
    ok_all = True
    for t in plan:
        env_cmd = ("printf '%s\\n' " + " ".join("'%s'" % ln for ln in t["env"])
                   + f" | sudo -n tee {LM_DL_TASKS}/{t['task']}.env >/dev/null")
        for c in (f"sudo -n mkdir -p '{t['dir']}' && sudo -n chown {SERVICE_USER}:{SERVICE_USER} '{t['dir']}'",
                  f"sudo -n mkdir -p {LM_DL_TASKS}",
                  env_cmd,
                  f"sudo -n systemctl start --no-block {LM_DL_UNIT}{t['task']}"):
            ok, out = ssh_run(station, c, timeout=120, strict=True)
            print(f"  {'✓' if ok else '✗'} {t['task']}: {c[:70]}")
            if not ok:
                print(f"      {(out or '').strip()[:200]}")
                ok_all = False
                break
    if ok_all:
        print(f"\n[models fetch] 已下发 ✓  进度: journalctl -u {LM_DL_UNIT}<任务> -f")
    return 0 if ok_all else 1


