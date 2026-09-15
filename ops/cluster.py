#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cluster.py — 三机推理集群聚合操作 CLI (主控站)

用法:
    python ops/cluster.py status [--html] [--frames]
    python ops/cluster.py load <alias前缀> [--backend unsloth|llama-rpc|llama-single|vllm]
    python ops/cluster.py frames
    python ops/cluster.py unload
    python ops/cluster.py e2e
    python ops/cluster.py secrets {status|scan|push}
    python ops/cluster.py providers
    python ops/cluster.py egress
    python ops/cluster.py web [--host 127.0.0.1] [--port 8095] [--token <可选>]  # 傻瓜式 Web 管理 UI (按需服务)

子命令:
    status   三站 llama /health + 当前加载实例 + 引擎清单一屏聚合
             --html 生成静态快照页 ops/cluster_status.html
             --frames 追加各站框架级运行状态一览 (llama/unsloth/vllm/litellm/opencode)
             --all 追加凭据/Provider/出站三平面一行摘要 (统一入口四平面视图)
    load     自动路由到正确站并执行 infer-load (gpt-oss-120b->A, qwen3.8-27b->C, 其余->B;
             llama-rpc 类默认打印手动步骤, exit 2)
             --backend 显式指定后端四线切换 (unsloth|llama-rpc|llama-single|vllm)。
             换后端只需 load <alias> --backend <new> 一次 (infer-load 已做站内互斥), 无需先 unload;
             但显式 --backend 才会改后端, 缺省沿用 conf 旧值。
             对 llama-rpc 类模型: 显式 --backend 单机后端(非 llama-rpc) 视为强制单机加载, 走正常路径。
    frames   三站框架级运行状态一览 (llama-server/unsloth/vllm/litellm/opencode), 恒 exit 0
    unload   三站并行幂等卸载
    e2e      三站引擎在线冒烟 (直连 :8080, 不经 LiteLLM 网关——网关已退役)
    secrets  站内凭据治理 (平面②): status=落点+权限+明文巡检; scan=明文扫描; push=从主控下发
    providers 三站 agent provider 聚合 (平面②): provider 集合/默认模型/凭据引用形态/漂移检测
    egress   出站平面探针 (平面③): 主控+三站 -> OpenRouter 健康/用量/余额
    web      傻瓜式推理框架管理 Web UI (按需服务, 见 ops/cluster_web.py; 浏览器点按钮加载/切后端/卸载)

退出码:
    0 成功 / 1 失败 / 2 RPC 类需手动

设计: spec/d2-cluster-cli/ (RESEARCH/IMPLEMENTATION/CHECKLIST)
依赖: paramiko (主控站 hermes venv Python 3.11 已装)
      C:\\Users\\Peng\\.hermes\\hermes-agent\\venv\\Scripts\\python.exe
"""
import os
import sys
import re
import time
import json
import socket
import subprocess
import threading
from pathlib import Path

import paramiko

# ── 常量层 ──────────────────────────────────────────────
STATIONS = {
    "A": {"host": "scott-lau-NEX.local", "user": "scott-lau"},
    "B": {"host": "scott-lau-GTR-Pro.local", "user": "scott-lau"},
    "C": {"host": "192.168.1.37", "user": "scott-lau"},   # seaviv (2026-09-09 IP 修正: 原 192.168.1.24 过期; seaviv.local 可解析但保持 IPv4 规避 paramiko/IPv6)
}
# 各站引擎 /health 端口 (A/B/C 均 8080; 原 C=18080 为过时值)
STATION_PORT = {"A": 8080, "B": 8080, "C": 8080}
ROUTE = {"gpt-oss-120b": "A", "qwen3.8-27b-mtp": "C"}     # 其余一律 B (DEFAULT_STATION)

# ── 按站路由名: 显式指明"从哪个工作站加载本地模型" ──────────────────
# 键 = 站上真实别名 + "-" + 站小写;  值 = (station, 站上真实别名)。
#
# 为什么需要: 同一别名可能在多个站都有 conf (如 gpt-oss-120b 在 A/B/C 都有), 而 ROUTE
# 只能给一个默认站。按站路由名让用户直接说"我要 C 站那个"。
# 它同时是手册 §2.2 里 `gpt-oss-c` / `nemotron-c` 的**现行替代品** —— 那两个名字是
# LiteLLM 时代的网关别名, 网关依 ADR-0002 退役后已失效 (nemotron 甚至不是站上别名)。
#
# 命名刻意用「完整别名 + 站后缀」而非「短名 + 站后缀」: 短名无法从真值表派生, 会再引入
# 一套要人工同步的命名。且因为是**精确查表** (不做后缀解析), 不存在歧义 ——
# "qwen3.8-27b-mtp-b" 到底是别名还是"别名+站后缀", 查表即知。
# 门禁 aliases 断言会校验此表与 inventory/models.yaml 的 conf 声明一致。
STATION_ROUTES = {
    "gpt-oss-120b-a": ("A", "gpt-oss-120b"),
    "gpt-oss-120b-b": ("B", "gpt-oss-120b"),
    "gpt-oss-120b-c": ("C", "gpt-oss-120b"),
    "gpt-oss-20b-b": ("B", "gpt-oss-20b"),
    "gpt-oss-120b-fable-5-distilled-b": ("B", "gpt-oss-120b-fable-5-distilled"),
    "nvidia-nemotron-3-super-120b-a12b-b": ("B", "nvidia-nemotron-3-super-120b-a12b"),
    "nvidia-nemotron-3-super-120b-a12b-c": ("C", "nvidia-nemotron-3-super-120b-a12b"),
    "deepseek-v4-flash-0731-b": ("B", "deepseek-v4-flash-0731"),
    "qwen3.8-27b-mtp-b": ("B", "qwen3.8-27b-mtp"),
    "qwen3.8-27b-mtp-c": ("C", "qwen3.8-27b-mtp"),
    "qwen3.8-flash-next-b": ("B", "qwen3.8-flash-next"),
    "davidau-q38-27b-q4k-b": ("B", "davidau-q38-27b-q4k"),
}
# 与路由表解耦: 后端是站内概念, 换后端不改 alias->station 映射。C 专属键应置于本字典尾部以保前缀匹配序
BACKENDS = {"unsloth", "llama-rpc", "llama-single", "vllm"}   # infer-load --backend 白名单
DEFAULT_STATION = "B"
# C 站 (2026-09-09): 常驻引擎为手动 /opt/llama.cpp llama-server (Vulkan, 如 nemotron Q4_K_M :8080),
# 非 systemd llama-server@*.service 单元。infer-* 工具链已补装 (load 用 infer-load, 含 pkill 兜底),
# 故 C 站 load/unload 与 A/B 同路径。C_ENGINE_UNIT(systemd 特判) 已废弃。
# 走 RPC 双机通道的模型 (resolve_alias 据此判 is_rpc)。
# qwen3.8-flash-next 已移出 (2026-09-15): 它是单机量化加载模型, 用 STATION_ROUTES 的
# qwen3.8-flash-next-b 走 B 站本地加载, 不再经 RPC 双机通道。
RPC_MODELS = {"deepseek-v4-flash-0731", "gpt-oss-120b-fable-5-distilled"}
# LiteLLM 网关服务 :4000 已退役 (2026-09-13): ADR-0002 决策 C 后常用链路经 "cluster-litellm" provider
# 直连各站引擎端口, 不经网关; 网关已无活依赖。故移除 LITELLM_BASE / KEY_FILE / read_key 及 status/e2e 对网关的硬依赖。
HTML_OUT = Path(__file__).parent / "cluster_status.html"
SSH_TIMEOUT = 8


PANELS = [
    ("Beszel 监控", "http://scott-lau-GTR-Pro.local:8090"),
    ("Cockpit B", "https://scott-lau-GTR-Pro.local:9095"),
    ("Cockpit A", "https://scott-lau-NEX.local:9095"),
    ("Cockpit C", "https://192.168.1.37:9095"),
]


# ── SSH 层 ─────────────────────────────────────────────
# 主机名解析缓存 —— 性能关键 (2026-09-14 实测):
#   mDNS 解析 *.local 单次约 14s (A 14.07s / B 14.10s), 而 IP 直连 ssh 仅 0.2s。
#   原先每次 ssh_run 都用主机名重连 ⇒ 每次连接白付 ~14s。9 次串行即 130s
#   (这正是 /api/status 129.6s 的根因, 见 CHECKLIST F19)。
#   C 站一直用 IP 故从未受影响。
#   此处缓存解析结果, 使"解析一次、全程复用"; 长驻的 web 服务受益最大 (热后近 0 成本)。
_HOST_CACHE = {}


def resolve_host(st: str) -> str:
    """解析站点主机名 -> IP (结果进程内缓存)。解析失败时回退原名, 不阻断。"""
    name = STATIONS[st]["host"]
    if name not in _HOST_CACHE:
        try:
            _HOST_CACHE[name] = socket.gethostbyname(name)
        except OSError:
            _HOST_CACHE[name] = name
    return _HOST_CACHE[name]


def _connect(st: str, timeout: int = SSH_TIMEOUT) -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(resolve_host(st), username=STATIONS[st]["user"],
                timeout=timeout, banner_timeout=timeout)
    return cli


def ssh_run(st: str, cmd: str, timeout: int = SSH_TIMEOUT) -> tuple:
    """返回 (ok, output)。ok=False 时 output 为错误信息。"""
    try:
        cli = _connect(st, timeout)
        _, out, err = cli.exec_command(cmd, timeout=timeout + 30)
        text = out.read().decode("utf-8", "replace")
        etext = err.read().decode("utf-8", "replace")
        rc = out.channel.recv_exit_status()
        cli.close()
        return True, (text if text.strip() else etext)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def ssh_stream(st: str, cmd: str) -> int:
    """实时流式回传长命令 (infer-load 需 40s~3min)。返回远端 exit code。"""
    cli = _connect(st)
    _, out, err = cli.exec_command(cmd, timeout=600)
    chan = out.channel
    while True:
        while chan.recv_ready():
            sys.stdout.write(chan.recv(4096).decode("utf-8", "replace"))
            sys.stdout.flush()
        if chan.exit_status_ready() and not chan.recv_ready():
            break
        time.sleep(0.2)
    rc = chan.recv_exit_status()
    cli.close()
    return rc


# ── 探测层 ─────────────────────────────────────────────
def probe_station(st: str, with_list: bool = True) -> dict:
    """单站探测: llama health + 当前加载实例。端口按 st 取 STATION_PORT。

    with_list=False 跳过 infer-list —— 该脚本自身耗时约 10.3s (三站一致, 与 ssh/mDNS 无关,
    2026-09-14 实测), 而 web 面板并不渲染该字段, 故 web 路径应传 False。
    """
    result = {"station": st, "reachable": False, "llama": "?", "loaded": "?", "list": ""}
    port = STATION_PORT.get(st, 8080)
    # 引擎探测 (2026-09-15 修复): 旧实现只 curl /health + systemd llama-server@*, 而
    # A 站等是 unsloth studio / LM Studio 进程 —— 它们**不响应 /health**(404) 且**非 systemd
    # 单元**, 于是"引擎已加载成功"被误判成"加载失败/未加载"。改为: 监听端口 + 从进程
    # 命令行提取真实模型名 (兼容 `--model path` / `-m path`), 对三套引擎统一。
    ok, out = ssh_run(st, (
        f"ss -ltn 2>/dev/null | grep -c ':{port}'; "
        "printf '|MODEL|'; "
        "ps -eo args 2>/dev/null | grep -E 'studio run|llama-server|lmstudio|lms ' "
        "| grep -v grep | grep -oE '(--model[ =][^ ]+| -m [^ ]+)' | head -1"))

    if not ok:
        result["llama"] = "UNREACHABLE"
        return result
    result["reachable"] = True
    listen_part, _, mod_part = out.partition("|MODEL|")
    listening = (listen_part.strip().splitlines()[-1] if listen_part.strip() else "0").strip()
    mod = (mod_part or "").strip()
    # READY 判定 (2026-09-15 修): 不能只看 STATION_PORT(8080) —— 部分模型的 conf 用
    # 别的端口 (如 qwen3.8-27b-mtp 用 18080), 只看 8080 会把"已加载"误报成 STOPPED。
    # 判据放宽为: 目标端口有监听 **或** 进程命令行能抓到加载的模型名。
    listening_ok = listening.isdigit() and int(listening) > 0
    result["llama"] = "READY" if (listening_ok or mod) else "STOPPED"
    if mod:
        p = mod.replace("--model", "").strip()
        if p.startswith(("=", " ")):
            p = p[1:]
        p = p.replace("-m", "").strip()
        name = os.path.basename(p.rstrip("/"))
        name = re.sub(r"\.gguf$", "", name, flags=re.I)
        name = re.sub(r"-\d{5}-of-\d{5}$", "", name)  # 分片号剥离
        result["loaded"] = name or "(未加载)"
    else:
        result["loaded"] = "(未加载)"
    if not with_list:
        result["list"] = "(skipped)"
        return result
    ok2, out2 = ssh_run(st, "infer-list 2>/dev/null | head -30 || systemctl list-units 'llama-server@*' --no-legend 2>/dev/null")
    result["list"] = out2 if ok2 else "(infer-list 不可用)"
    return result


# ── 引擎指标采集 (2026-09-15 新增, 方案 v2 附录 A.1.1) ──────────────
# 为什么必须"直连内层端口": unsloth studio 是**代理层**(8080 = 它的 FastAPI),
# 它不透传 /metrics /slots /health —— 2026-09-15 实测 8080 上三者全返回
# `{"detail":"API endpoint not found"}`, 而真实 llama-server 在 studio 背后的
# 随机端口(A 站实测 :53873)。systemd 路径引擎自己监听 conf 的 PORT, 可直接访问。
# 指标来源 = llama.cpp 原生端点, **无需 exporter**, 也无需引入任何时序库。
_METRICS_CMD = (
    "P=$(ps -eo args 2>/dev/null | grep -E 'llama.cpp/llama-server|llama-server -m' | grep -v grep "
    "| grep -oE '\\-\\-port [0-9]+' | head -1 | awk '{print $2}'); "
    "echo \"PORT=${P:-0}\"; "
    "if [ -n \"$P\" ]; then "
    "echo '===M==='; curl -s --max-time 4 http://127.0.0.1:${P}/metrics 2>/dev/null | grep -E '^llamacpp:' | head -24; "
    "echo '===S==='; curl -s --max-time 4 http://127.0.0.1:${P}/slots 2>/dev/null | head -c 1200; "
    "fi"
)


def probe_metrics(st: str) -> dict:
    """单站引擎指标: 内层端口 + Prometheus /metrics + /slots。

    返回 {reachable, port, metrics:{name:value}, n_slots, slots_busy, ctx}。
    引擎未运行时 port=0, 其余为空 —— 调用方据此显示"未加载"。
    """
    d = {"station": st, "reachable": False, "port": 0,
         "metrics": {}, "n_slots": 0, "slots_busy": 0, "ctx": 0}
    ok, out = ssh_run(st, _METRICS_CMD, timeout=30)
    if not ok:
        return d
    d["reachable"] = True
    head, _, rest = out.partition("===M===")
    for line in head.splitlines():
        if line.startswith("PORT="):
            try:
                d["port"] = int(line.split("=", 1)[1].strip())
            except ValueError:
                d["port"] = 0
    if not d["port"]:
        return d
    m_part, _, s_part = rest.partition("===S===")
    for line in m_part.splitlines():
        line = line.strip()
        if not line.startswith("llamacpp:"):
            continue
        key, _, val = line.partition(" ")
        try:
            d["metrics"][key.replace("llamacpp:", "").strip()] = float(val.strip())
        except ValueError:
            pass
    try:
        slots = json.loads(s_part.strip()) if s_part.strip() else []
    except Exception:
        slots = []
    if isinstance(slots, list):
        d["n_slots"] = len(slots)
        d["slots_busy"] = sum(1 for x in slots if isinstance(x, dict) and x.get("is_processing"))
        ctxs = [x.get("n_ctx") for x in slots if isinstance(x, dict) and x.get("n_ctx")]
        d["ctx"] = max(ctxs) if ctxs else 0
    return d


# ── 事前预估 (2026-09-15, 方案 v2 P1-1) ────────────────────────
# 为什么需要: load-gate 在**站内事后**拒绝 (命令已发出才发现不够), 用户拿不到
# "这次能不能加载 / 该改哪个参数"的前置答案。本函数把预估前移到主控: 读 GGUF 架构
# 元数据 (站上 gguf-meta) + conf + 站上内存, 算出权重/KV/SSM/开销, 与 load-gate 规则联算。
# 算法依据: 社区 gguf_vram_calc 的逐项拆分 (v2 方案附录 A.3), 核心 KV 公式
#   kv = n_parallel × ctx × n_attn_layer × kv_heads × head_dim × (bytes_k + bytes_v)
# 关键差异: hybrid SSM/attention 模型 (Qwen3.x-Next / Nemotron-H) **只有全注意力层算 KV**,
# 且 SSM state 与 ctx 无关 —— 按纯 transformer 线性外推会严重高估 (A.3 已论证)。

# 各 KV dtype 的每元素字节数 (含 block scale 开销)
_KV_BPE = {"f16": 2.0, "bf16": 2.0, "f32": 4.0, "q8_0": 1.0625,
           "q4_0": 0.5625, "q4_1": 0.625, "iq4_nl": 0.5625}


def _parse_conf(text: str) -> dict:
    """解析站上 conf (/etc/llama-instances/<alias>.env) 为 dict。"""
    d = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        d[k.strip()] = v.strip().strip('"').strip("'")
    return d


def _station_mem(st: str) -> dict:
    """站上内存与**既有引擎占用** (GiB)。

    口径严格对齐站上 `load-gate`（项目硬规则的真实实现, ops/station-bin/load-gate）:
        total = MemTotal
        avail = MemAvailable
        used  = total - avail            ← **不是 free 的 used 口径**!
        rssm  = 已有 llama-server / ggml-rpc-server / llama-cli 进程 RSS 总和

    ⚠️ 两个踩过的坑 (2026-09-15):
      1) 首版用 `free` 口径 used=total-free-buffers-cached, 与 load-gate 不一致;
         且 `free` 输出随 locale 变化(中文表头是「内存：」) —— 故统一读 /proc/meminfo。
      2) 首版**漏了 rssm(已有引擎 RSS)**, 而 UMA 架构下模型权重会表现为 Cached,
         只看 used/avail 会说不清"为什么装不下"。rssm 是 load-gate 规则③的依据。
    """
    ok, out = ssh_run(st,
        "awk '/^MemTotal:/{t=$2} /^MemAvailable:/{a=$2} END{printf \"%d %d\", t/1024, a/1024}' /proc/meminfo; "
        "ps -eo rss,comm 2>/dev/null | grep -E 'llama-server|ggml-rpc-server|llama-cli' "
        "| awk '{s+=$1} END{printf \" %d\", s/1024}'")
    if not ok or not out.strip():
        return {}
    p = out.strip().split()
    if len(p) < 2:
        return {}
    try:
        total_mb, avail_mb = int(p[0]), int(p[1])
        rssm_mb = int(p[2]) if len(p) > 2 else 0
    except ValueError:
        return {}
    return {"total": total_mb / 1024, "avail": avail_mb / 1024,
            "used": (total_mb - avail_mb) / 1024, "existing_rss": rssm_mb / 1024}


def _fallback_conf(st: str, alias: str) -> tuple:
    """conf 缺失时的回退：按 alias 反查站上模型库, 返回 (conf_dict, err)。

    为什么必须回退: `infer-load` 在 conf 不存在时会**自动生成**
    (默认 CTX=32768 / THREADS=16 / N_CPU_MOE=8 / backend 按需判定),
    所以"模型库里有权重 ⇒ 可加载"; 而预估器若强行要求 conf 存在, 就会把
    "权重已就位但尚未首次加载"的模型全部误报失败 (2026-09-15 实测: m27-q4ks /
    qwen3-coder-next / all-minilm / qwen3.8-flash-next / deepseek / nemotron 都被误报)。

    本函数复刻 infer-load 的 alias 匹配规则（目录名去 -GGUF、转小写、minimax 重映射、
    精确优先再前缀）做反查; 参数按 infer-load 的默认值填。
    """
    ok, out = ssh_run(st, "find -L /data/models/gguf -mindepth 2 -maxdepth 2 -type d 2>/dev/null")
    if not ok or not out.strip():
        return None, "无法扫描模型库"
    low = alias.strip().lower()
    exact, pref = [], []
    for d in out.splitlines():
        d = d.strip()
        if not d:
            continue
        a = re.sub(r"-GGUF$", "", os.path.basename(d), flags=re.I).lower()
        if a.startswith("minimax-m2.7"):
            a = "m27-q4ks"
        if a == low:
            exact.append(d)
        elif a.startswith(low):
            pref.append(d)
    hits = exact or pref
    if not hits:
        return None, f"模型库中未找到 alias '{alias}'"
    repo = hits[0]
    # 主 gguf 选取规则与 infer-load 一致: 合并单文件(排除分片/mmproj) → 分片首片 → 任意
    ok, f = ssh_run(st, f"find -L '{repo}' -name '*.gguf' ! -name '*-of-0000*.gguf' "
                       "! -name 'mmproj*' -size +1G -printf '%s %p\\n' 2>/dev/null "
                       "| sort -rn | head -1 | cut -d' ' -f2-")
    if not ok or not f.strip():
        ok, f = ssh_run(st, f"find -L '{repo}' -name '*-00001-of-*.gguf' 2>/dev/null | head -1")
    if not ok or not f.strip():
        ok, f = ssh_run(st, f"find -L '{repo}' -name '*.gguf' 2>/dev/null | head -1")
    mpath = (f or "").strip()
    if not mpath:
        return None, f"{repo} 下无 gguf"
    return {"MODEL_PATH": mpath, "CTX": "32768", "THREADS": "16",
            "N_CPU_MOE": "8", "EXTRA_FLAGS": "-fa on"}, ""


def estimate_load(st: str, alias: str, ctx: int = None, n_parallel: int = None,
                  ctk: str = "q8_0", ctv: str = "q8_0", pad_gib: int = 12) -> dict:
    """指定站加载 <alias> 的**事前预估** + 与 load-gate 规则联算。

    返回 {ok, alias, station, model{...}, ctx, n_parallel, weights_gib, kv_gib,
          ssm_gib, overhead_gib, need_gib, mem{...}, verdict, reasons[], advice[]}
    verdict ∈ {FITS, TIGHT, NO_FIT, UNKNOWN}
    """
    out = {"ok": False, "alias": alias, "station": st, "ctk": ctk, "ctv": ctv,
           "pad_gib": pad_gib, "reasons": [], "advice": []}
    ok, conf_txt = ssh_run(st, f"cat /etc/llama-instances/{alias}.env 2>/dev/null")
    if not ok or not conf_txt.strip():
        # conf 缺失 → 回退到模型库反查（infer-load 首次加载会自动生成 conf, 预估必须同源）
        fb, err = _fallback_conf(st, alias)
        if not fb:
            out["reasons"].append(f"站上无 conf 且回退失败: {err}")
            return out
        out.setdefault("notes", []).append(
            "站上暂无 conf —— infer-load 首次加载会自动生成; 预估按默认参数 "
            f"CTX={fb['CTX']} / THREADS={fb['THREADS']} / N_CPU_MOE={fb['N_CPU_MOE']}")
        conf_txt = "\n".join(f"{k}={v}" for k, v in fb.items())
    conf = _parse_conf(conf_txt)
    mpath = conf.get("MODEL_PATH", "")
    if not mpath:
        out["reasons"].append("conf 缺 MODEL_PATH")
        return out
    extra = conf.get("EXTRA_FLAGS", "")
    try:
        ctx = int(ctx or conf.get("CTX") or 32768)
    except ValueError:
        ctx = 32768
    out["ctx"] = ctx
    if n_parallel is None:
        m = re.search(r"--parallel\s+(\d+)", extra)
        n_parallel = int(m.group(1)) if m else 1
    out["n_parallel"] = n_parallel

    # 权重 = 主模型所在目录全部 *.gguf (含分片与 mmproj/draft)
    d = os.path.dirname(mpath)
    ok, sz = ssh_run(st, f"du -smcL '{d}'/*.gguf 2>/dev/null | tail -1 | cut -f1")
    weights = 0.0
    if ok and sz.strip().isdigit():
        weights = int(sz.strip()) / 1024
    out["weights_gib"] = round(weights, 1)

    # 架构元数据
    meta = {}
    ok, meta_txt = ssh_run(st, f"gguf-meta '{mpath}' 2>/dev/null")
    if ok and meta_txt.strip():
        try:
            meta = json.loads(meta_txt)
        except Exception:
            meta = {}
    out["model"] = {k: meta.get(k) for k in (
        "arch", "name", "block_count", "head_count", "head_count_kv", "key_length",
        "embedding_length", "context_length", "file_type", "ssm_state_size")}

    # ctx 超出模型原生上限时明确提示 (引擎会静默钳制, 用户看不到)
    native_ctx = meta.get("context_length")
    if native_ctx and ctx > native_ctx:
        out.setdefault("notes", []).append(
            f"ctx {ctx} 超出该模型原生上限 {native_ctx} —— 引擎会钳制到原生值")

    bc = meta.get("block_count") or 0
    hc = meta.get("head_count") or 0
    kl = meta.get("key_length")
    emb = meta.get("embedding_length") or 0
    head_dim = kl or (int(emb / hc) if hc else 0)
    interval = meta.get("full_attention_interval")

    # 全注意力层数 & KV heads —— 按精度递减处理三种形态:
    #  ① kv_heads 是**逐层数组**（hybrid SSM/attention 常见; 如 nemotron_h_moe 的
    #     88 层里只有 8 层 kv_heads=2, 其余全 0 = SSM 层不产生 KV）→ **数组本身就是
    #     "哪些层是全注意力层"的权威答案**, 直接数 >0 的个数, 不必再用 interval 推
    #     (2026-09-15 实测: 此前按 block_count=88 计 KV = 5.84G, 按数组应为 8 层 ≈ 0.53G)
    #  ② 标量 kv_heads + full_attention_interval → ceil(block_count / interval)
    #  ③ 纯 transformer → 全部层
    kvh_raw = meta.get("head_count_kv")
    if isinstance(kvh_raw, list):
        attn = [x for x in kvh_raw if isinstance(x, int) and x > 0]
        n_attn = len(attn) or bc
        kvh = max(attn) if attn else hc
    else:
        kvh = kvh_raw or hc
        n_attn = bc
        if interval:
            try:
                n_attn = -(-bc // int(interval))     # ceil
            except (TypeError, ValueError, ZeroDivisionError):
                n_attn = bc
    bk = _KV_BPE.get(ctk, 1.0625)
    bv = _KV_BPE.get(ctv, 1.0625)
    kv_gib = (n_parallel * ctx * n_attn * kvh * head_dim * (bk + bv)) / (1024 ** 3)
    out["kv_gib"] = round(kv_gib, 2)
    out["n_attn_layer"] = n_attn
    out["head_dim"] = head_dim

    # SSM recurrent state (hybrid 架构; 固定大小, 与 ctx 无关) —— 近似口径
    ssm = meta.get("ssm_state_size")
    if ssm and bc:
        ssm_gib = (bc * ssm * max(head_dim or 128, 128) * 2) / (1024 ** 3)
        out["ssm_gib"] = round(ssm_gib, 2)
        out["ssm_approx"] = True
    else:
        out["ssm_gib"] = 0.0

    fa = ("-fa on" in extra) or ("--flash-attn on" in extra)
    overhead = 0.5 if fa else 1.0
    out["overhead_gib"] = overhead

    need = weights + out["kv_gib"] + out["ssm_gib"] + overhead
    out["need_gib"] = round(need, 1)

    mem = _station_mem(st)
    out["mem"] = {k: round(v, 1) for k, v in mem.items()}
    out.setdefault("notes", [])
    if mem:
        rss = mem.get("existing_rss", 0.0)
        # 加载流程 (cmd_load / cmd_load_on) 会**先卸载本站旧实例**再加载, 故预估按
        # "卸载后"口径算: avail_eff = avail + 现有引擎 RSS。这点必须显式 —— 否则
        # "本站已有实例"会被误报成装不下 (2026-09-15 用户指出的判定偏差)。
        avail_eff = mem["avail"] + rss
        used_eff = max(mem["used"] - rss, 0.0)
        out["avail_effective"] = round(avail_eff, 1)
        if rss > 0:
            out["notes"].append(
                f"本站已有引擎 RSS {rss:.1f}G —— 加载会先自动卸载它; 预估已按卸载后口径计算")
        # 判据严格对齐站上 load-gate: used/avail + 12G 安全垫
        if used_eff + need + pad_gib > mem["total"]:
            out["verdict"] = "NO_FIT"
            out["reasons"].append(
                f"used_eff {used_eff:.1f} + need {need:.1f} + pad {pad_gib} > total {mem['total']:.1f}")
        elif avail_eff < need + pad_gib:
            out["verdict"] = "NO_FIT"
            out["reasons"].append(
                f"avail_eff {avail_eff:.1f} < need {need:.1f} + pad {pad_gib}")
        elif avail_eff < need + pad_gib + 20:
            out["verdict"] = "TIGHT"
        else:
            out["verdict"] = "FITS"
    else:
        out["verdict"] = "UNKNOWN"

    if out["verdict"] in ("NO_FIT", "TIGHT"):
        if out["kv_gib"] > 0:
            out["advice"].append(f"ctx {ctx} → {ctx // 2}: 省 ≈{out['kv_gib'] * 0.5:.1f}G KV")
        if n_parallel > 1:
            out["advice"].append(f"--parallel {n_parallel} → 1: 省 ≈{out['kv_gib'] * (1 - 1 / n_parallel):.1f}G")
        out["advice"].append("KV 量化 q8_0 → q4_0: 再省约一半 KV (质量损失小)")
        if out["ssm_gib"] > 0:
            out["advice"].append("该模型为 hybrid SSM 架构, SSM state 与 ctx 无关, 降 ctx 收益有限")
        out["advice"].append("或改走单机路径 / 换更小量化档")
    out["ok"] = True
    return out


# 框架级探测: 单次 ssh 多命令, 检测各站 llama/unsloth/vllm/litellm/opencode。
# [u]/[v] 前缀规避 pgrep 自匹配; llama 的 RUNNING 由 systemctl(A/B) 或 pgrep llama-server(C 手动) 取其一。
FRAME_CMD = (
    "echo '[llama]'; systemctl is-active 'llama-server@*' 2>/dev/null|head -1; "
    "pgrep -x llama-server >/dev/null && echo running; "
    "echo '[unsloth]'; pgrep -f '[u]nsloth studio run' >/dev/null && echo running; "
    "echo '[vllm]'; pgrep -f '[v]llm.entrypoint' >/dev/null && echo running; "
    "echo '[litellm]'; systemctl is-active litellm 2>/dev/null; "
    "echo '[opencode]'; pgrep -f '[o]pencode' >/dev/null && echo running; "
    "echo '[claude]'; pgrep -f '[c]laude-code' >/dev/null && echo running")


def probe_frames(st: str) -> dict:
    """单站框架级运行状态一览。返回 {station, reachable, frames:{name:("RUNNING"/"STOPPED"/"Unknown", detail)}}。"""
    result = {"station": st, "reachable": False, "frames": {}}
    ok, out = ssh_run(st, FRAME_CMD)
    if not ok:
        result["frames"]["llama"] = ("Unknown", "UNREACHABLE")
        return result
    result["reachable"] = True
    active_frame = None
    detail = ""
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            if active_frame:
                result["frames"][active_frame] = _frame_status(detail)
            active_frame = line[1:-1]
            detail = ""
        elif active_frame:
            detail = f"{detail} {line}".strip()
    if active_frame:
        result["frames"][active_frame] = _frame_status(detail)
    return result


def _frame_status(detail: str) -> tuple:
    """由探测文本判 RUNNING / STOPPED。非 llama 框架无进程迹象时 detail 为空 -> STOPPED; 不可达由调用方填 UNKNOWN。
    判定序: running(进程实据) > inactive > active。注意 'inactive' 含子串 'active', 必须先判 inactive。"""
    if "UNREACHABLE" in detail:
        return ("Unknown", detail)
    if not detail:
        return ("STOPPED", detail)
    if "running" in detail:          # pgrep 命中 = 进程实据, 最高优先
        return ("RUNNING", detail)
    if "inactive" in detail:
        return ("STOPPED", detail)
    if "active" in detail:
        return ("RUNNING", detail)
    # 其它框架: 仅 pgrep 命中才出现 detail; 无 detail 即未运行
    return ("STOPPED", detail)


# ── 凭据平面 (secrets / providers) ─────────────────────
# 收敛约定 (2026-09-14 明文治理): 站内唯一落点 ~/.config/rpc/*.key (700/600),
# 配置侧用引用而非明文 —— opencode 走 {file:...}, claude code 走 apiKeyHelper。
RPC_DIR = "~/.config/rpc"
SECRETS_ROOT = Path(__file__).parent.parent / "secrets" / "stations"   # 主控正本
# 明文 key 指纹: 用于巡检。占位符 ***REMOVED*** 与 {file:...} 不命中。
KEY_PAT = r"sk-(or-v1|unsloth|RPC|local|lm)-[A-Za-z0-9_-]{6,}"
MASK_SED = r"sed -E 's/(sk-[A-Za-z0-9_-]{4})[A-Za-z0-9_-]+/\1***/g'"
OPC_CONF = "~/.config/opencode/opencode.jsonc"
CLD_CONF = "~/.claude/settings.json"

SECRETS_PROBE = (
    "printf '\\n[dir]\\n'; ls -1 " + RPC_DIR + "/ 2>/dev/null || echo '(未建立)'; "
    "printf '\\n[perm]\\n'; stat -c '%a %n' " + RPC_DIR + " " + RPC_DIR + "/* 2>/dev/null; "
    "printf '\\n[live]\\n'; grep -lE '" + KEY_PAT + "' " + OPC_CONF + " " + CLD_CONF + " 2>/dev/null; "
    "printf '\\n[archive]\\n'; grep -rlE '" + KEY_PAT + "' ~/.config/opencode/backups-keys-* "
    "~/.claude/backups-keys-* 2>/dev/null | wc -l; "
    "printf '\\n[refs]\\n'; grep -hoE '\\{file:[^}]*\\}' " + OPC_CONF + " 2>/dev/null | sort -u; "
    "printf '\\n[helper]\\n'; grep -oE '\"apiKeyHelper\": *\"[^\"]*\"' " + CLD_CONF + " 2>/dev/null"
)


def probe_secrets(st: str) -> dict:
    """单站凭据落点探测。返回 {station, reachable, dir, perm, live, archive, refs, helper}。"""
    res = {"station": st, "reachable": False, "dir": [], "perm": [],
           "live": [], "archive": 0, "refs": [], "helper": ""}
    ok, out = ssh_run(st, SECRETS_PROBE, timeout=20)
    if not ok:
        return res
    res["reachable"] = True
    section = None
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            section = s[1:-1]
            continue
        if not s or section is None:
            continue
        if section == "dir":
            res["dir"].append(s.split()[-1])
        elif section == "perm":
            parts = s.split()
            if len(parts) >= 2:
                res["perm"].append((parts[0], parts[-1]))
        elif section == "live":
            res["live"].append(s)
        elif section == "archive":
            res["archive"] = int(s) if s.isdigit() else -1
        elif section == "refs":
            res["refs"].append(s)
        elif section == "helper":
            res["helper"] = s
    return res


def _secrets_verdict(p: dict) -> tuple:
    """返回 (状态, 说明)。关键判据: 生效配置无明文 + 归档无明文 + 权限收紧。"""
    if not p["reachable"]:
        return "UNREACHABLE", "站不可达"
    problems = []
    if p["live"]:
        problems.append(f"生效配置明文 x{len(p['live'])}")
    if p["archive"]:
        problems.append(f"归档明文 x{p['archive']}")
    loose = [n for m, n in p["perm"] if m not in ("600", "700") and not n.endswith(RPC_DIR.split("/")[-1])]
    if loose:
        problems.append(f"权限过宽 {len(loose)}")
    keys = [f for f in p["dir"] if f.endswith(".key")]
    if not p["dir"]:
        problems.append("无站内落点")
    if problems:
        return "ATTENTION", "; ".join(problems)
    return "OK", f"落点 {len(keys)} key; 引用 {len(p['refs'])} 处"


def cmd_secrets(action: str = "status") -> int:
    if action not in ("status", "scan", "push"):
        print(f"用法: cluster.py secrets {{status|scan|push}}  (未知动作: {action})")
        return 1
    if action == "push":
        return _secrets_push()

    probes = {}
    threads = []
    for st in ("A", "B", "C"):
        t = threading.Thread(target=lambda s=st: probes.__setitem__(s, probe_secrets(s)))
        t.start(); threads.append(t)
    for t in threads:
        t.join()

    hits = 0
    for st in ("A", "B", "C"):
        p = probes.get(st, {})
        state, note = _secrets_verdict(p)
        if action == "scan":
            plain = len(p.get("live", [])) + p.get("archive", 0)
            hits += plain
            print(f"{st} 站 明文命中 {plain:2d} 处  ({note})")
        else:
            print(f"── {st} 站 {STATIONS[st]['host']} ──")
            print(f"    状态     : {state:10s}{note}")
            print(f"    站内落点 : {', '.join(p.get('dir') or ['(未建立)'])}")
            print(f"    引用点   : {', '.join(p.get('refs') or ['(无)'])}")
            print(f"    claude   : {p.get('helper') or '(无 apiKeyHelper)'}")
            loose = [f"{m} {n}" for m, n in p.get("perm", []) if m not in ("600", "700")]
            if loose:
                print(f"    权限告警 : {'; '.join(loose)}")
            print()
    if action == "scan":
        print(f"[secrets] 明文命中合计 {hits} 处 -> {'FAIL' if hits else 'PASS'}")
        return 1 if hits else 0
    return 0


def _secrets_push() -> int:
    """从主控 secrets/stations/<st>/ 下发到各站 ~/.config/rpc/ (SFTP, 600 / 脚本 700)。"""
    if not SECRETS_ROOT.is_dir():
        print(f"[secrets] 主控正本目录不存在: {SECRETS_ROOT}")
        return 1
    total = 0
    for st in ("A", "B", "C"):
        src = SECRETS_ROOT / st
        if not src.is_dir():
            print(f"[secrets] {st} 站: 跳过 (无正本 {src})")
            continue
        try:
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(resolve_host(st), username=STATIONS[st]["user"],
                        timeout=SSH_TIMEOUT, banner_timeout=SSH_TIMEOUT)
            ssh_run(st, f"mkdir -p {RPC_DIR} && chmod 700 {RPC_DIR}")   # 复用 ssh_run 建目录
            sftp = cli.open_sftp()
            names = []
            for f in sorted(src.iterdir()):
                if not f.is_file():
                    continue
                remote = f"/home/{STATIONS[st]['user']}/.config/rpc/{f.name}"
                with sftp.open(remote, "w") as fh:
                    fh.write(f.read_bytes())
                sftp.chmod(remote, 0o700 if f.name.endswith(".sh") else 0o600)
                names.append(f.name)
                total += 1
            sftp.close(); cli.close()
            print(f"[secrets] {st} 站 下发 {len(names)} 个: {', '.join(names)}")
        except Exception as e:
            print(f"[secrets] {st} 站 下发失败: {type(e).__name__}: {e}")
            return 1
    print(f"[secrets] 完成, 共 {total} 个文件 (站内 agent 需重启生效)")
    return 0


PROVIDERS_PROBE = (
    # 用 printf 前置换行: 部分配置文件无尾换行, 直接 echo marker 会被粘到上一行末尾
    "printf '\\n### opencode\\n'; " + MASK_SED + " " + OPC_CONF + " 2>/dev/null; "
    "printf '\\n### claude\\n'; " + MASK_SED + " " + CLD_CONF + " 2>/dev/null; "
    "printf '\\n### hermes\\n'; test -f ~/.hermes/config.yaml && echo present || echo absent"
)


def _api_key_form(prov: dict) -> str:
    v = str((prov.get("options") or {}).get("apiKey", ""))
    if not v:
        return "—"
    if v.startswith("{file:") or v.startswith("{env:"):
        return "ref"
    return "PLAIN"


def _claude_forms(cl: dict) -> dict:
    """判定 claude settings.json 的凭据形态。env token 需区分 ref/真密钥/占位符,
    否则本地占位值(如 'lmstudio')会被误报为明文。"""
    env = cl.get("env") or {}
    tok = str(env.get("ANTHROPIC_AUTH_TOKEN", ""))
    if not tok:
        form = "—"
    elif tok.startswith("{file:") or tok.startswith("{env:"):
        form = "ref"
    elif len(tok) >= 20:
        form = "PLAIN"
    else:
        form = f"占位符({len(tok)}B)"
    return {
        "model": cl.get("model", "(未设)"),
        "helper": bool(cl.get("apiKeyHelper")),
        "token_form": form,
        "base_url": str(env.get("ANTHROPIC_BASE_URL", "")),
        "overrides": len(cl.get("modelOverrides") or {}),
    }


def probe_providers(st: str) -> dict:
    """单站 agent provider 聚合 (key 值已脱敏, 只判形态)。"""
    res = {"station": st, "reachable": False, "opencode": {}, "claude": {}, "hermes": "absent"}
    ok, out = ssh_run(st, PROVIDERS_PROBE, timeout=20)
    if not ok:
        return res
    res["reachable"] = True
    blocks, name = {}, None
    for line in out.splitlines():
        if line.startswith("### "):
            name = line[4:].strip(); blocks[name] = []
        elif name:
            blocks[name].append(line)
    try:
        oc = json.loads("\n".join(blocks.get("opencode", [])))
        providers = oc.get("provider", {}) or {}
        res["opencode"] = {
            "model": oc.get("model", "(未设)"),
            "providers": {k: _api_key_form(v or {}) for k, v in providers.items()},
        }
    except Exception as e:
        res["opencode"] = {"error": f"parse: {type(e).__name__}"}
    try:
        cl = json.loads("\n".join(blocks.get("claude", [])))
        res["claude"] = _claude_forms(cl)
    except Exception as e:
        res["claude"] = {"error": f"parse: {type(e).__name__}"}
    res["hermes"] = (blocks.get("hermes", ["absent"]) or ["absent"])[0].strip()
    return res


def cmd_providers() -> int:
    """三站 agent provider 聚合 + 漂移检测 (恒 exit 0, 仅供观测)。"""
    data = {}
    threads = []
    for st in ("A", "B", "C"):
        t = threading.Thread(target=lambda s=st: data.__setitem__(s, probe_providers(s)))
        t.start(); threads.append(t)
    for t in threads:
        t.join()

    for st in ("A", "B", "C"):
        d = data.get(st, {})
        oc = d.get("opencode", {})
        print(f"── {st} 站 {STATIONS[st]['host']} ──")
        if oc.get("error"):
            print(f"    opencode : {oc['error']}")
        else:
            print(f"    opencode : 默认模型 {oc.get('model')}")
            for name, form in (oc.get("providers") or {}).items():
                flag = "  ← 明文!" if form == "PLAIN" else ""
                print(f"               {name:18s} key:{form}{flag}")
        cl = d.get("claude", {})
        if cl.get("error"):
            print(f"    claude   : {cl['error']}")
        else:
            flag = "  ← 明文!" if cl.get("token_form") == "PLAIN" else ""
            print(f"    claude   : 模型 {cl.get('model')}; apiKeyHelper {cl.get('helper')}; "
                  f"env token {cl.get('token_form')}{flag}; modelOverrides {cl.get('overrides')}")
        print(f"    hermes   : config.yaml {d.get('hermes')}")
        print()

    # 漂移检测: 默认模型 / provider 集合
    live = {st: data.get(st, {}).get("opencode", {}) for st in ("A", "B", "C")}
    models = {st: v.get("model") for st, v in live.items() if not v.get("error")}
    if len(set(models.values())) > 1:
        print("[providers] opencode 默认模型漂移:")
        for st, m in models.items():
            print(f"    {st}: {m}")
    prov_sets = {st: frozenset((v.get("providers") or {}).keys()) for st, v in live.items() if not v.get("error")}
    if prov_sets:
        common = set.intersection(*[set(s) for s in prov_sets.values()]) if prov_sets else set()
        for st, s in prov_sets.items():
            only = set(s) - common
            if only:
                print(f"[providers] {st} 站独有 provider: {', '.join(sorted(only))}")
    return 0


# ── 出站平面 (egress) ──────────────────────────────────
# 探针目标: OpenRouter /api/v1/key (幂等只读, 返回用量/余额)。
# 铁律: 强制 IPv4 —— 主控到 openrouter.ai 的 IPv6 路径黑洞 (ADR-0003 实测), 故一律 curl -4。
EGRESS_URL = "https://openrouter.ai/api/v1/key"
EGRESS_SEP = "__META__"


def _mask_key(s: str) -> str:
    """OpenRouter /key 的 label 会回显 key 前段, 输出前必须脱敏。"""
    return re.sub(r"(sk-[A-Za-z0-9_-]{4})[A-Za-z0-9_-]+", r"\1***", s)


def _parse_egress(body: str) -> dict:
    try:
        d = (json.loads(body) or {}).get("data") or {}
    except Exception:
        return {}
    return {"usage": d.get("usage"), "remaining": d.get("limit_remaining"),
            "limit": d.get("limit"), "label": _mask_key(str(d.get("label", "")))}


def _egress_cmd(keyexpr: str) -> str:
    return (f"K=$({keyexpr} 2>/dev/null); "
            "if [ -z \"$K\" ]; then echo 'NO_KEY'; else "
            f"curl -4 -s -m 12 -w '{EGRESS_SEP}http=%{{http_code}} t=%{{time_total}}' "
            f"-H \"Authorization: Bearer $K\" {EGRESS_URL}; fi")


def probe_egress_station(st: str) -> dict:
    """单站出站探测 (走站内 ~/.config/rpc/openrouter.key)。"""
    res = {"station": st, "reachable": False, "http": "?", "time": "", "info": {}, "note": ""}
    ok, out = ssh_run(st, _egress_cmd("cat ~/.config/rpc/openrouter.key"), timeout=25)
    if not ok:
        res["note"] = "站不可达"
        return res
    res["reachable"] = True
    res["note"] = out.strip()
    if "NO_KEY" in out:
        res["http"] = "NO_KEY"
        return res
    body, _, meta = out.rpartition(EGRESS_SEP)
    for kv in meta.split():
        if kv.startswith("http="):
            res["http"] = kv[5:]
        elif kv.startswith("t="):
            res["time"] = kv[2:][:5]
    res["info"] = _parse_egress(body)
    return res


def probe_egress_master() -> dict:
    """主控出站探测 (走主控正本 secrets/openrouter.key; curl.exe -4 规避 IPv6 黑洞)。"""
    res = {"station": "主控", "reachable": True, "http": "?", "time": "", "info": {}, "note": ""}
    keyfile = Path(__file__).parent.parent / "secrets" / "openrouter.key"
    if not keyfile.exists():
        res["http"] = "NO_KEY"
        res["note"] = f"{keyfile.name} 不存在"
        return res
    lines = [l.strip() for l in keyfile.read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.strip().startswith("#")]
    if not lines:
        res["http"] = "NO_KEY"
        res["note"] = "key 文件无有效行"
        return res
    try:
        cp = subprocess.run(
            ["curl.exe", "-4", "-s", "-m", "12", "-o", "-",
             "-w", EGRESS_SEP + "http=%{http_code} t=%{time_total}",
             "-H", f"Authorization: Bearer {lines[0]}", EGRESS_URL],
            capture_output=True, text=True, timeout=40)
    except Exception as e:
        res["http"] = "ERR"
        res["note"] = f"{type(e).__name__}: {e}"
        return res
    body, _, meta = cp.stdout.rpartition(EGRESS_SEP)
    for kv in meta.split():
        if kv.startswith("http="):
            res["http"] = kv[5:]
        elif kv.startswith("t="):
            res["time"] = kv[2:][:5]
    res["info"] = _parse_egress(body)
    return res


def cmd_egress() -> int:
    """出站平面探针: 主控 + 三站 -> OpenRouter (健康/用量/余额)。恒 exit 0, 仅供观测。"""
    res = {"主控": probe_egress_master()}
    threads = []
    for st in ("A", "B", "C"):
        t = threading.Thread(target=lambda s=st: res.__setitem__(s, probe_egress_station(s)))
        t.start(); threads.append(t)
    for t in threads:
        t.join()

    for name in ("主控", "A", "B", "C"):
        r = res.get(name, {})
        info = r.get("info") or {}
        if r.get("http") == "200":
            bal = info.get("remaining")
            bal = "无限额" if bal is None else f"余 {bal}"
            print(f"{name:4s} : OK    http=200  {r.get('time','')}s  "
                  f"用量 {info.get('usage')} / {bal}")
        else:
            print(f"{name:4s} : FAIL  http={r.get('http')}  {(r.get('note') or '')[:70]}")
    print()
    print("[egress] 注: `:free` 档模型受 agentic-harness 门禁, 裸 API 调用返回 403;")
    print("         须经 claude code / opencode 等 harness 调用 (见 ADR-0003)。")
    return 0


# ── status ─────────────────────────────────────────────
def collect_status(with_list: bool = True) -> dict:
    data = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "stations": {}}
    threads = []

    def run_a():
        data["stations"]["A"] = probe_station("A", with_list)

    def run_b():
        data["stations"]["B"] = probe_station("B", with_list)

    def run_c():
        data["stations"]["C"] = probe_station("C", with_list)

    for t in (threading.Thread(target=run_a), threading.Thread(target=run_b),
              threading.Thread(target=run_c)):
        t.start(); threads.append(t)
    for t in threads:
        t.join()
    return data


def _planes_compact() -> None:
    """四平面一屏汇总 (供 status --all)。并行探测, 只打印一行摘要。"""
    sec, pv, eg = {}, {}, {}
    threads = []
    for st in ("A", "B", "C"):
        threads.append(threading.Thread(target=lambda s=st: sec.__setitem__(s, probe_secrets(s))))
        threads.append(threading.Thread(target=lambda s=st: pv.__setitem__(s, probe_providers(s))))
        threads.append(threading.Thread(target=lambda s=st: eg.__setitem__(s, probe_egress_station(s))))
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print("── 平面② 凭据 (站内 ~/.config/rpc, 引用化) ──")
    for st in ("A", "B", "C"):
        state, note = _secrets_verdict(sec.get(st, {}))
        print(f"    {st} : {state:10s}{note}")
    print("── 平面②b Provider (agent 配置) ──")
    for st in ("A", "B", "C"):
        d = pv.get(st, {}) or {}
        oc, cl = d.get("opencode", {}), d.get("claude", {})
        oc_s = oc.get("model") or oc.get("error", "?")
        cl_s = cl.get("token_form") or cl.get("error", "?")
        print(f"    {st} : opencode={oc_s}  claude={cl_s}"
              f"{' +apiKeyHelper' if cl.get('helper') else ''}")
    print("── 平面③ 出站 (OpenRouter /key) ──")
    for st in ("A", "B", "C"):
        r = eg.get(st, {})
        ok_s = f"OK {r.get('time', '')}s" if r.get("http") == "200" else f"FAIL http={r.get('http')}"
        print(f"    {st} : {ok_s}")
    print()


def cmd_status(html: bool, frames: bool = False, all_planes: bool = False) -> int:
    d = collect_status()
    for st in ("A", "B", "C"):
        s = d["stations"].get(st, {})
        print(f"── {st} 站 ({STATIONS[st]['host']}) ──")
        print(f"  llama :{STATION_PORT.get(st, 8080)} : {s.get('llama', '?')}")
        print(f"  加载实例      : {s.get('loaded', '?')}")
        print()
    for st in ("A", "B", "C"):
        print(f"── infer-list @ {st} 站 (原样透传) ──")
        print(d["stations"].get(st, {}).get("list", "(无)"))
        print()
    if frames:
        fd = collect_frames()
        for st in ("A", "B", "C"):
            f = fd.get(st, {})
            print(f"── 框架 @ {st} 站 ──")
            for name, (status, detail) in f.get("frames", {}).items():
                print(f"    {name:10s} : {status:8s}{('  ' + detail) if detail else ''}")
            if f.get("reachable") is False and not f.get("frames"):
                print("    (站不可达)")
            print()
    if all_planes:
        _planes_compact()
    if html:
        render_html(d)
    return 0


def collect_frames() -> dict:
    """三站并行框架级状态。返回 {station: probe_frames 结果}。"""
    data = {}
    threads = []
    for st in ("A", "B", "C"):
        t = threading.Thread(target=lambda s=st: data.__setitem__(s, probe_frames(s)))
        t.start(); threads.append(t)
    for t in threads:
        t.join()
    return data


def cmd_frames() -> int:
    """三站框架级运行状态一览, 恒 exit 0。"""
    fd = collect_frames()
    for st in ("A", "B", "C"):
        f = fd.get(st, {})
        print(f"── {st} 站 ({STATIONS[st]['host']}) ──")
        for name in ("llama", "unsloth", "vllm", "litellm", "opencode", "claude"):
            status, detail = f.get("frames", {}).get(name, ("Unknown", ""))
            print(f"    {name:10s} : {status:8s}{('  ' + detail) if detail else ''}")
        print()
    return 0


def render_html(d: dict) -> None:
    rows = ""
    for st in ("A", "B", "C"):
        s = d["stations"].get(st, {})
        color = "#2e7d32" if s.get("llama") == "READY" else "#c62828"
        rows += (f"<tr><td>{st} 站</td><td>{STATIONS[st]['host']}</td>"
                f"<td style='color:{color};font-weight:600'>{s.get('llama', '?')}</td>"
                f"<td>{s.get('loaded', '?')}</td></tr>")
    panels = "".join(f'<li><a href="{u}">{n}</a></li>' for n, u in PANELS)
    if "C" in STATIONS:
        panels += "<li>C 站: 引擎 :8080 (独立端点, 走 CLI)</li>"
    lists = ""
    for st in ("A", "B", "C"):
        txt = d["stations"].get(st, {}).get("list", "(无)")
        lists += f"<h3>{st} 站 infer-list</h3><pre>{txt}</pre>"
    html_doc = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>三机推理集群状态快照</title>
<style>
body{{font-family:Consolas,'Microsoft YaHei',monospace;margin:2em;background:#fafafa}}
h1{{font-size:1.3em}} table{{border-collapse:collapse;margin:1em 0}}
td,th{{border:1px solid #bbb;padding:6px 14px;font-size:0.95em}}
pre{{background:#fff;border:1px solid #ddd;padding:8px;overflow-x:auto;font-size:0.85em}}
.meta{{color:#666;font-size:0.85em}} li{{margin:4px 0}}
</style></head><body>
<h1>三机推理集群状态快照</h1>
<p class="meta">生成时刻 {d['time']} — 静态快照, 重新运行 <code>cluster.py status --html</code> 刷新</p>
<table><tr><th>站点</th><th>主机</th><th>llama /health</th><th>加载实例</th></tr>
{rows}
</table>
<h3>面板入口</h3><ul>{panels}</ul>
{lists}
</body></html>"""
    HTML_OUT.write_text(html_doc, encoding="utf-8")
    print(f"HTML 快照已生成: {HTML_OUT}")
    print(f"浏览器打开: file:///{HTML_OUT.as_posix()}")


# ── load / unload ──────────────────────────────────────
class AliasError(Exception):
    """别名解析失败 (歧义)。"""


def resolve_alias(alias: str) -> tuple:
    """把用户输入解析为 (station, matched_alias, is_rpc, how)。

    how ∈ {exact, prefix, rpc, default} —— 供调用方把"落到默认站"**显式**打印出来。

    为什么需要 how (2026-09-14 修复):
      旧实现未匹配时静默返回 (DEFAULT_STATION, alias, ...), 调用方照常打印
      "[cluster] 路由: X -> B 站", 与正常路由外观一致。于是当 ROUTE 的键写成缩写
      (旧值 `qwen3.8-27b`, 站上真实别名是 `qwen3.8-27b-mtp`) 时, 用户输入真实别名
      匹配失败 → 被静默加载到 B 站 (B 站恰有同名 conf 故不报错)。数据已修正, 但
      **同类缺陷会随新键再次发生**, 故让"未匹配"在输出上可辨识。

    匹配策略:
      0) 精确匹配 (忽略大小写) 优先
      1) 单向前缀: 路由键以输入开头
         **刻意不做双向** —— 否则 `ROUTE["gpt-oss-120b"]` 会吞掉更具体的
         `gpt-oss-120b-fable-5-distilled` (后者属 RPC 双机类, 必须走 RPC 分支)。
         单向恰好让"更具体的别名"不撞"更短的别名"。
      2) 多个候选 => 抛 AliasError (旧实现静默取 dict 第一个, ROUTE 增长后会误路由)
    """
    low = alias.strip().lower()

    # 0) 按站路由名 (精确查表, 必须最先查) —— 否则会被下面的 ROUTE 前缀匹配或
    #    "更长变体"安全网误判 (如 gpt-oss-120b-c 会被当成 gpt-oss-120b 的更长变体而报错)。
    for name, (st, real) in STATION_ROUTES.items():
        if name.lower() == low:
            return st, real, real in RPC_MODELS, "station"

    def pick(cands):
        exact = [c for c in cands if c.lower() == low]
        return exact, [c for c in cands if c.lower().startswith(low)]

    for cands, kind in ((list(ROUTE.keys()), "route"), (sorted(RPC_MODELS), "rpc")):
        exact, pref = pick(cands)
        hits = exact or pref
        if len(hits) > 1:
            raise AliasError(
                f"'{alias}' 前缀匹配到多个候选: {', '.join(hits)} —— 请写更完整的别名")
        if len(hits) == 1:
            m = hits[0]
            if kind == "route":
                return ROUTE[m], m, m in RPC_MODELS, ("exact" if exact else "prefix")
            return None, m, True, "rpc"

    # 兜底前的安全网 (2026-09-14): 若输入只是某个路由键的**更长版本**, 绝不能静默落默认站。
    # 场景: 输入 `qwen3.8-27b-mtp` (站上真实别名), 而 ROUTE 键写成了缩写 `qwen3.8-27b` ——
    # 单向匹配不会命中, 旧实现便静默送到 DEFAULT_STATION (B 站恰有同名 conf 故不报错),
    # 即"加载到错误的站"。这里宁可报错逼人确认。
    longer = [k for k in ROUTE if low != k.lower() and low.startswith(k.lower())]
    if longer:
        raise AliasError(
            f"'{alias}' 比路由键 {', '.join(sorted(longer))} 更具体, 但不在路由表中 —— "
            f"若它确是站上别名, 说明该路由键已过期 (应改成完整别名); "
            f"否则请改用确切的别名 (其余别名按默认站 {DEFAULT_STATION} 处理)")

    return DEFAULT_STATION, alias, alias in RPC_MODELS, "default"


def _cmd_load_c(alias: str, backend: str = None) -> int:
    """C 站 load：与 A/B 同路径 (infer-load 已补装, 含 pkill 兜底管理手动引擎)。"""
    print(f"[cluster] C 站 (seaviv) 加载 {alias} ...")
    cmd = f"infer-load '{alias}'" + (f" --backend {backend}" if backend else "")
    rc = ssh_stream("C", cmd)
    if rc != 0:
        print(f"[cluster] C 站加载失败 (rc={rc})。")
        return 1
    ok, out = ssh_run("C", "curl -s --max-time 8 http://127.0.0.1:8080/health")
    if ok and out.strip():
        print(f"[cluster] C 站引擎 :8080 响应: {out.strip()[:60]}")
    print(f"[cluster] C 站引擎 READY ✓ (站内 infer-load 判定, rc=0)")
    return 0


def _build_infer_load_cmd(matched: str, backend: str) -> str:
    """拼装远端 infer-load 命令。backend 来自白名单校验(枚举), 无注入风险。"""
    return f"infer-load '{matched}'" + (f" --backend {backend}" if backend else "")


def cmd_load(alias: str, backend: str = None) -> int:
    if backend is not None and backend not in BACKENDS:
        print(f"[cluster] 非法 --backend '{backend}'. 可选: {', '.join(sorted(BACKENDS))} (exit 1)")
        return 1
    try:
        station, matched, is_rpc, how = resolve_alias(alias)
    except AliasError as e:
        print(f"[cluster] 别名解析失败: {e} (exit 2)")
        print(f"  路由别名   : {', '.join(sorted(ROUTE))}")
        print(f"  RPC 类模型 : {', '.join(sorted(RPC_MODELS))}")
        print(f"  按站路由名 : {', '.join(sorted(STATION_ROUTES))}")
        print(f"  其余别名按默认站 {DEFAULT_STATION} 处理")
        return 2
    if station == "C":
        # C 站分支在通用路由行之前 return, 故这里单独标一下"按站路由" —— 让用户知道
        # 自己是靠按站路由名进来的 (A/B 路径的标注在下面 tag 处)。
        if how == "station":
            print(f"[cluster] 按站路由: {alias} -> C 站, 站上别名 {matched}")
        return _cmd_load_c(matched, backend)
    # llama-rpc 双机类: 显式 --backend 单机后端(非 llama-rpc) 视为强制单机加载, 走正常路径;
    # 否则走 RPC 编排 (见 _load_rpc) —— 2026-09-15 落地方案 v2 P0-3, 原为"打印手动步骤 exit 2"。
    if is_rpc:
        if backend and backend != "llama-rpc":
            station = station or DEFAULT_STATION
            print(f"[cluster] '{matched}' 为 RPC 双机类, --backend {backend} 视为强制单机加载 (退化为 {station} 站单机)。")
        else:
            return _load_rpc(matched, station or DEFAULT_STATION)
    st_host = STATIONS[station]["host"]
    # 把"匹配方式"显式打印: default 分支意味着别名未在路由表中, 只是落到了默认站 ——
    # 若站上并无该别名, infer-load 才会失败; 不这样标出来会让它与正常路由外观一致 (见 resolve_alias 注释)。
    tag = {"prefix": "  [前缀匹配]",
           "station": "  [按站路由 —— 由路由名显式指定来源站]",
           "default": f"  [★未在路由表中 → 落默认站; 若站上无此别名, infer-load 会失败]"}.get(how, "")
    print(f"[cluster] 路由: {matched} -> {station} 站 ({st_host}){tag}")
    # P1 换模型串行化: 先探 :8080, 有响应即视为已有引擎占用, 先 unload 等 GTT 释放再加载。
    # 判定放宽为"任意 HTTP 响应" (非 {"status" 前缀)——unsloth OpenAI 后端 /health 返回 {"detail":...} 也是占用实据。
    # infer-unload 幂等, 误判(如杂散 8080 服务)时快速成功退出, 无害; infer-load 内部亦会再兜底互斥+释放。
    ok, out = ssh_run(station, "curl -s --max-time 5 http://127.0.0.1:8080/health")
    if ok and out.strip():
        print(f"[cluster] {station} 站 :8080 有引擎占用, 先卸载并等待 GTT 释放 ...")
        rc = ssh_stream(station, "infer-unload")
        if rc != 0:
            print(f"[cluster] 卸载失败 (rc={rc}), 中止。")
            return 1
    print(f"[cluster] 加载中 (站内 load-mem-gate 自动护航) ...")
    rc = ssh_stream(station, _build_infer_load_cmd(matched, backend))
    if rc != 0:
        print(f"[cluster] 加载失败 (rc={rc})。")
        return 1
    # 站内 infer-load 已针对不同后端 (llama/unsloth/vllm) 做真实 READY 判定 (实测 rc=0 即就绪)。
    # 不再用 {"status" 前缀复核——unsloth OpenAI 后端 /health 返回 {"detail":...} 会误判为未就绪。
    ok, out = ssh_run(station, "curl -s --max-time 5 http://127.0.0.1:8080/health")
    if ok and out.strip():
        print(f"[cluster] {station} 站引擎 :8080 响应: {out.strip()[:60]}")
    print(f"[cluster] READY ✓ (站内 infer-load 判定, rc=0)")
    return 0


def _load_rpc(alias: str, station: str) -> int:
    """RPC 双机类加载编排 (2026-09-15, 方案 v2 P0-3)。

    把原先"打印手动步骤并 exit 2"升级为**一条命令端到端**。零件全部复用既有资产:
      · `nodes.env`   = RPC 节点声明 (单一事实源, B 站 /etc/llama-instances/nodes.env)
      · `rpc-nodes`   = 站上 helper: 读 nodes.env → 起各节点 rpc-server@<alias> 并等端口 LISTEN
      · `infer-load`  = 站上加载 (conf 的 RPC_TARGET=auto 会自动展开为 rpc-nodes 输出)
      · `infer-unload`= 收尾 (站上已含"顺带停 rpc-server")

    为什么 master 固定 B 站: `nodes.env` 与 `rpc-nodes` 都在 B 站, 且既有设计是
    "B 站发起 + A 站承载张量分片"(见 spec/cluster-bench/DESIGN §2)。指定其他站会被纠正。
    """
    if station != "B":
        print(f"[cluster] RPC 类由 B 站(master)发起 (nodes.env/ rpc-nodes 均在其上), 已忽略指定的 {station} 站。")
        station = "B"
    print(f"[cluster] == RPC 双机类加载编排: {alias} @ {station} 站 (master) ==")

    print("[cluster] [1/4] 卸载本站现存实例 (幂等, 释放 GTT) ...")
    ssh_stream(station, "infer-unload")

    print("[cluster] [2/4] 启动 RPC 工作节点 (rpc-nodes --start, 含等端口 LISTEN) ...")
    ok, out = ssh_run(station, f"rpc-nodes --start '{alias}'", timeout=240)
    if out.strip():
        print(out.strip()[-1200:])
    if not ok:
        print("[cluster] rpc-nodes --start 失败 → 中止 (不进入加载)。")
        return 1

    # 存活探测而非只回显声明 —— 2026-09-15 实测: nodes.env 声明了 C 站(10.10.11.3:50052),
    # 但 C 站未装 rpc-server 单元(--start 会报 Unit not found, 由 rpc-nodes 容错兜住)。
    # 只有**存活**节点才会进 llama-server 的 --rpc, 故这里显式打印两者差异。
    ok, alive = ssh_run(station, "rpc-nodes 2>/dev/null")
    ok2, decl = ssh_run(station, "rpc-nodes --all 2>/dev/null")
    print(f"[cluster] [3/4] RPC 存活节点: {alive.strip() or '(无)'}")
    print(f"[cluster]        声明清单  : {decl.strip() or '(空)'}")
    if not alive.strip():
        print("[cluster] 无存活 RPC 节点 → 中止 (否则 llama-server 会因 --rpc 空而退化为单机)。")
        return 1

    print("[cluster] [4/4] 加载权重 (conf RPC_TARGET=auto 展开为上式清单) ...")
    rc = ssh_stream(station, _build_infer_load_cmd(alias, None))
    if rc != 0:
        print(f"[cluster] 加载失败 (rc={rc}) → 可用 journalctl -u 'llama-server@*' 排查。")
        return 1

    ok, hl = ssh_run(station, "curl -s --max-time 5 http://127.0.0.1:8080/health")
    if ok and hl.strip():
        print(f"[cluster] {station} 站引擎响应: {hl.strip()[:60]}")
    print(f"[cluster] RPC READY ✓  ({alias} 已跨机加载; 收尾用 cluster.py unload)")
    return 0


def cmd_load_on(station: str, alias: str, backend: str = None) -> int:
    """在**指定站**加载模型 (跳过别名路由) —— 供 web 按站操作使用。

    与 cmd_load 的唯一区别: 不做 resolve_alias, 因为调用方已明确目标站
    (用户在下拉里选定了"哪个站加载哪个模型")。其余语义完全一致:
    仍走站内 infer-load (含互斥清理 / load-mem-gate 内存门禁 / 释放等待)。
    """
    if station not in STATIONS:
        print(f"[cluster] 未知站 '{station}' (可选: {', '.join(STATIONS)})")
        return 1
    if backend is not None and backend not in BACKENDS:
        print(f"[cluster] 非法 --backend '{backend}'. 可选: {', '.join(sorted(BACKENDS))} (exit 1)")
        return 1
    print(f"[cluster] 指定站加载: {alias} -> {station} 站 ({STATIONS[station]['host']})")
    ok, out = ssh_run(station, "curl -s --max-time 5 http://127.0.0.1:8080/health")
    if ok and out.strip():
        print(f"[cluster] {station} 站 :8080 有引擎占用, 先卸载并等待 GTT 释放 ...")
        rc = ssh_stream(station, "infer-unload")
        if rc != 0:
            print(f"[cluster] 卸载失败 (rc={rc}), 中止。")
            return 1
    print(f"[cluster] 加载中 (站内 load-mem-gate 自动护航) ...")
    rc = ssh_stream(station, _build_infer_load_cmd(alias, backend))
    if rc != 0:
        print(f"[cluster] 加载失败 (rc={rc})。")
        return 1
    print(f"[cluster] {station} 站 READY ✓ (站内 infer-load 判定, rc=0)")
    return 0


def cmd_unload_on(station: str) -> int:
    """只卸载**指定站** (web 按站操作; 三站并行卸载仍用 cmd_unload)。"""
    if station not in STATIONS:
        print(f"[cluster] 未知站 '{station}'")
        return 1
    rc = ssh_stream(station, "infer-unload")
    print(f"[cluster] {station} 站 infer-unload: {'OK' if rc == 0 else f'rc={rc}'}")
    return 0 if rc == 0 else 1


def cmd_unload() -> int:
    results = {}
    threads = []

    def run(st):
        results[st] = ssh_stream(st, "infer-unload")

    for st in ("A", "B", "C"):
        t = threading.Thread(target=run, args=(st,))
        t.start(); threads.append(t)
    for t in threads:
        t.join()
    rc = 0
    for st in ("A", "B", "C"):
        r = results[st]
        print(f"[cluster] {st} 站 infer-unload: {'OK' if r == 0 else f'rc={r}'}")
        rc |= (r if r != 0 else 0)
    return 0 if rc == 0 else 1


# ── estimate (事前预估) ─────────────────────────────────
def cmd_estimate(argv) -> int:
    """cluster.py estimate <alias> [--station A|B|C] [--ctx N] [--parallel N] [--ctk X --ctv Y]"""
    if not argv:
        print("用法: cluster.py estimate <alias> [--station A|B|C] [--ctx N] [--parallel N] "
              "[--ctk q8_0] [--ctv q8_0]")
        return 1
    alias = argv[0]
    station = None
    ctx = npar = None
    ctk = ctv = "q8_0"
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--station" and i + 1 < len(argv):
            station = argv[i + 1].upper(); i += 2; continue
        if a == "--ctx" and i + 1 < len(argv):
            ctx = int(argv[i + 1]); i += 2; continue
        if a == "--parallel" and i + 1 < len(argv):
            npar = int(argv[i + 1]); i += 2; continue
        if a == "--ctk" and i + 1 < len(argv):
            ctk = argv[i + 1]; i += 2; continue
        if a == "--ctv" and i + 1 < len(argv):
            ctv = argv[i + 1]; i += 2; continue
        i += 1
    if not station:
        try:
            station, matched, is_rpc, how = resolve_alias(alias)
        except AliasError as e:
            print(f"[cluster] 别名解析失败: {e}")
            return 2
        station = station or DEFAULT_STATION
        print(f"[cluster] 路由: {matched} -> {station} 站 ({how})")
        if is_rpc:
            print("[cluster] 注: 该模型为 RPC 双机类 —— 此处只预估发起站, 承载站需另行预估。")
    r = estimate_load(station, alias, ctx, npar, ctk, ctv)
    if not r.get("ok"):
        print("[cluster] 预估失败: " + "; ".join(r.get("reasons") or ["未知原因"]))
        return 1
    m, mem = r["model"], r["mem"]
    kvh_show = m.get("head_count_kv")
    if isinstance(kvh_show, list):
        kvh_show = f"逐层(全注意力 {r['n_attn_layer']}/{m.get('block_count')} 层)"
    print(f"\n=== 事前预估: {alias} @ {r['station']} 站 ===")
    print(f"  模型      : {m.get('name')} [{m.get('arch')}] 层={m.get('block_count')} "
          f"kv_heads={kvh_show} head_dim={r['head_dim']} 原生ctx={m.get('context_length')}")
    print(f"  加载参数  : ctx={r['ctx']} parallel={r['n_parallel']} KV=({r['ctk']},{r['ctv']})")
    print(f"  权重      : {r['weights_gib']} GiB")
    print(f"  KV cache  : {r['kv_gib']} GiB   (全注意力层 {r['n_attn_layer']} 层)")
    if r.get("ssm_gib"):
        print(f"  SSM state : {r['ssm_gib']} GiB  (hybrid 架构, 近似口径, 与 ctx 无关)")
    print(f"  运行开销  : {r['overhead_gib']} GiB")
    print("  ────────────────────────")
    print(f"  合计需求  : {r['need_gib']} GiB")
    if mem:
        print(f"  站上内存  : total {mem.get('total')} / used {mem.get('used')} / avail {mem.get('avail')}"
              + (f" / 已有引擎RSS {mem.get('existing_rss')}" if mem.get("existing_rss") else "") + " GiB")
        print(f"  门禁判据  : (对齐站上 load-gate) used_eff+need+{r['pad_gib']} ≤ total  且  "
              f"avail_eff ≥ need+{r['pad_gib']}"
              + (f"   · avail_eff={r.get('avail_effective')}" if r.get("avail_effective") else ""))
    print(f"  结论      : 【{r['verdict']}】")
    for x in r.get("notes", []):
        print(f"    · {x}")
    for x in r["reasons"]:
        print(f"    ✗ {x}")
    for x in r["advice"]:
        print(f"    → {x}")
    return 0 if r["verdict"] in ("FITS", "TIGHT") else 3


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


# ── versions: 引擎版本矩阵 (2026-09-15, 方案 v2 P1-3) ──────────────
# 目的: 把"三站各引擎的实际版本/构建"摆到一屏, 暴露:
#   ① 版本漂移 (如 LM Studio C 站旧于 A/B)
#   ② 受控路径的完整性缺口 (如 MANIFEST.md5 缺失 → 硬规则要求的 md5sum -c 校验无法执行)
# 对齐 spec/vulkan-version-control 的 UPGRADE_SOP 溯源要求。
#
# 术语: 站上有**两个 llama.cpp 构建**, 用途不同, 不可混为一谈 ——
#   RPC 引擎   /opt/llama.cpp           受控路径, 只放 ggml-rpc-server + 库 (MANIFEST 管版本)
#   单机引擎   ~/llama.cpp/build/bin    单机 llama-server (--version 直读 commit)
_VER_SCAN = (
    "echo '===RPC==='; grep -E '^(commit|version|build_date|toolchain)[[:space:]]*=' "
    "/opt/llama.cpp/MANIFEST* 2>/dev/null | head -6; "
    "echo '===MD5==='; if [ -f /opt/llama.cpp/MANIFEST.md5 ]; then "
    "(cd /opt/llama.cpp && md5sum -c MANIFEST.md5 2>&1 | grep -c ': OK$'); "
    "(cd /opt/llama.cpp && md5sum -c MANIFEST.md5 2>&1 | grep 'FAILED' | head -3); "
    "else echo 'MISSING'; fi; "
    "echo '===SINGLE==='; ~/llama.cpp/build/bin/llama-server --version 2>&1 | head -2; "
    "git -C ~/llama.cpp rev-parse --short HEAD 2>/dev/null; echo; "
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
        if x.startswith("version:"):
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
              f"{r.get('version','?')} · built {r.get('built','?')}")
        print(f"    完整性  md5sum -c            {d.get('md5','?')}")
        print(f"  单机引擎  (~/llama.cpp)       commit {s.get('commit','?')} · "
              f"{s.get('version','?')}")
        print(f"  LM Studio                     {d.get('lmstudio','?')}")
        print(f"  opencode                      {d.get('opencode','?')}")
        print(f"  内核                          {d.get('kernel','?')}")
    # 漂移比对
    print("\n=== 一致性检查 ===")
    for field, getter in (("RPC commit", lambda d: d.get("rpc", {}).get("commit")),
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
            print(f"  ⚠ {st} 站 MANIFEST.md5 缺失 → 无法执行 md5sum -c 完整性校验"
                  f"（硬规则要求, 应重建）")
    return 0


def cmd_models(argv) -> int:
    """cluster.py models {list|orphan|link|verify} [--station A|B|C] [--all] [--dry-run]

    list   三站模型资产概览（物理库 / 聚合视图 / 孤儿 / 断链 计数）
    orphan 只列孤儿与断链详情（诊断用）
    link   给孤儿补软链（默认 dry-run, 加 --go 才写入; 可 --station 限定单站）
    verify 断链检查 + 主 gguf 可读性抽验（gguf-meta）
    """
    act = (argv[0] if argv else "list").lower()
    if act not in ("list", "orphan", "link", "prune", "verify"):
        print("用法: cluster.py models {list|orphan|link|prune|verify} [--station A|B|C] [--go]")
        return 1
    only, do_go = None, False
    for a in argv[1:]:
        if a in ("A", "B", "C") or (len(a) == 1 and a.upper() in ("A", "B", "C")):
            only = a.upper()
        if a == "--go":
            do_go = True
    stations = [only] if only else ["A", "B", "C"]

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


# ── e2e ────────────────────────────────────────────────
def cmd_e2e() -> int:
    """三站引擎在线冒烟 (直连 :8080, 不经 LiteLLM 网关——2026-09-13 网关已退役)。
    ssh 站内 curl :8080/health 返回 HTTP JSON 即引擎在线。exit 0 全在线; 任一离线 exit 1 并提示 load。"""
    rc = 0
    for st in ("A", "B", "C"):
        ok, out = ssh_run(st, "curl -s --max-time 5 http://127.0.0.1:8080/health")
        alive = ok and out.strip().startswith("{")   # HTTP JSON 响应 = 引擎在线 (connection refused 不命中)
        if alive:
            print(f"[e2e] {st} 站 :8080 ✓ 引擎在线  {out.strip()[:40]}")
        else:
            print(f"[e2e] {st} 站 :8080 ✗ 引擎离线 — python ops/cluster.py load <该站模型>")
            rc = 1
    return rc


# ── main ───────────────────────────────────────────────
def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    sub = args[0]
    if sub == "status":
        return cmd_status("--html" in args[1:], "--frames" in args[1:], "--all" in args[1:])
    if sub == "load":
        tail = args[1:]
        rest, backend, i = [], None, 0
        while i < len(tail):
            if tail[i] == "--backend" and i + 1 < len(tail):
                backend = tail[i + 1]   # 提取值并跳过, 避免污染 alias 前缀
                i += 2
                continue
            rest.append(tail[i])
            i += 1
        if not rest:
            print("用法: cluster.py load <alias前缀> [--backend unsloth|llama-rpc|llama-single|vllm]")
            return 1
        return cmd_load(" ".join(rest), backend)
    if sub == "frames":
        return cmd_frames()
    if sub == "unload":
        return cmd_unload()
    if sub == "estimate":
        return cmd_estimate(args[1:])
    if sub == "models":
        return cmd_models(args[1:])
    if sub == "versions":
        return cmd_versions(args[1:])
    if sub == "e2e":
        return cmd_e2e()
    if sub == "secrets":
        return cmd_secrets(args[1] if len(args) > 1 else "status")
    if sub == "providers":
        return cmd_providers()
    if sub == "egress":
        return cmd_egress()
    if sub == "web":
        import cluster_web
        return cluster_web.serve(args[1:])
    print(f"未知子命令: {sub}\n{__doc__}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
