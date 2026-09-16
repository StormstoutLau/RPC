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
    python ops/cluster.py flow [list|<name>] [--plan|--go] [args...]        # 声明式流程 (步骤→判据→台账)
    python ops/cluster.py reqlog {sample|summary|tail|path} [--minutes N]   # 引擎请求/token 统计 (站上采样)
    python ops/cluster.py ttl {status|check|enable|disable} [--ttl N] [--dry-run] [--go]  # 空闲 TTL 自动卸载 (默认关)
    python ops/cluster.py agent {runs|live|tail} [--limit N] [--station X] [--json]  # agent 任务进度/吞吐 (只读)

子命令:
    status   三站 llama /health + 当前加载实例 + 引擎清单一屏聚合
             --html 生成静态快照页 ops/cluster_status.html
             --frames 追加各站框架级运行状态一览 (llama/unsloth/vllm/litellm/opencode)
             --all 追加凭据/Provider/出站三平面一行摘要 (统一入口四平面视图)
    load     自动路由到正确站并执行 infer-load (gpt-oss-120b->A, qwen3.8-27b-mtp->C, 其余->B;
             支持按站路由名 STATION_ROUTES, 如 gpt-oss-120b-c = C 站的 gpt-oss-120b;
             RPC 双机类 (RPC_MODELS) 走 _load_rpc 编排, 已自动化 —— 2026-09-15 P0-3 前为"打印手动步骤, exit 2")
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
    flow     声明式流程 (P2-1): 每个 flow 声明「步骤 → 判据 → 台账落点」, 一次跑完并落 metrics-log。
             内置 verify(只读, 默认执行) / bench / swap / rotate (三者会改站上状态, 默认只出计划, --go 才动手)。
             `flow list` 打印全部步骤与判据; `flow <name> --plan` 只看计划; 任一步不达标立即中止。
    reqlog   引擎请求/token 统计 (P2-3): 站上读原生 /metrics + /slots, 与上一条样本差分后
             追加 JSONL 到 ~/.local/share/rpc/reqlog.jsonl; 主控聚合 (加权口径)。
             sample=三站各采一次; summary=聚合表; tail=原始样本; path=日志落点。
             口径: **引擎耗时口径**(ΣΔtoken/ΣΔ引擎耗时, 与 API timings 可比)为主, 墙钟口径为辅。
             采样是**按需**的 (不做常驻采样服务); /metrics 无 requests 计数器, 故不给"请求数"。
    ttl      空闲 TTL 自动卸载 (P2-5, **默认关**): 站上 `cluster-ttl` 每 60s 判一次引擎是否已空闲
             ≥ 阈值, 到期执行 `infer-unload` (会一并停掉全部 RPC worker)。空闲判据是 /metrics
             累计计数器的**差分** (llama.cpp 没有"最后请求时间"), 在途请求 >0 视为活跃。
             status=三站状态; check=立刻判一次 (默认只演练, --go 才真卸); enable/disable=写 conf + 开关 timer。
             与"零自加载"方针并存 —— TTL 只释放已加载资源, 从不加载任何模型。
    agent    agent 任务进度/吞吐 (P0, 只读; 见 spec/agent-observability/ 调研):
             runs=派发台账尾 N 条(join <projRoot>/agent-out/<ts>/.agent-run.json 详情);
             live=扫三站 $HOME/agent-workspaces/*/out/.progress (运行中节拍: 末行 t=end ⇒ finished);
             tail=台账原始行。**不新增采集器**, 只读站上既有文件。
             ⚠ 口径: 产出列是 **agent 产出字节口径** (output_bytes / B/s), **不是 token** ——
             与 reqlog 的引擎耗时口径 t/s、API timings 互不可比; 无头 run 不吐 usage ⇒ 不做换算;
             ETA 需目标量而运行中不可得 ⇒ 一律 `NA` (不打荒数字)。
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


def ssh_run(st: str, cmd: str, timeout: int = SSH_TIMEOUT, strict: bool = False) -> tuple:
    """返回 (ok, output)。

    ⚠ ok 的语义 (**容易误用, 2026-09-15 实测踩到**):
      默认 ok=True 只表示"连接与执行没出异常", **不代表远端退出码为 0**。
      这是刻意的 —— 很多探测用 grep/find, 它们"没匹配到"就返回非 0, 若一律判失败会把
      正常结果当错误。需要"退出码为 0 才算 ok"时显式传 `strict=True`。
      (调用方关心退出码却不用 strict 时, 会把失败当成功 —— 我写验证脚本时正是这么错的。)
    """
    try:
        cli = _connect(st, timeout)
        _, out, err = cli.exec_command(cmd, timeout=timeout + 30)
        text = out.read().decode("utf-8", "replace")
        etext = err.read().decode("utf-8", "replace")
        rc = out.channel.recv_exit_status()
        cli.close()
        body = text if text.strip() else etext
        if strict and rc != 0:
            return False, f"(rc={rc}) {body}"
        return True, body
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
    "printf '\\n### hermes\\n'; test -f ~/.hermes/config.yaml && echo present || echo absent; "
    # 记忆协同层 (2026-09-16 增补): opencode 自带 memory (MEMORY.md + SQLite), 非独立 codex-memory 命令
    # 判据: memory.db 存在 + 大小 + MEMORY.md 行数。--wal/--shm 为连接态伴生文件, 一并列示(说明此刻有 opencode 会话在写)。
    "printf '\\n### mem\\n'; "
    "ls -la ~/.local/share/opencode/memory.db* 2>/dev/null | awk '{print $5\"\\t\"$NF}'; "
    "echo -n 'MEMORY.md lines: '; wc -l < ~/.local/share/opencode/memories/MEMORY.md 2>/dev/null || echo '—'; "
    "echo -n 'summary lines: '; wc -l < ~/.local/share/opencode/memories/memory_summary.md 2>/dev/null || echo '—'"
)


def _api_key_form(prov: dict) -> str:
    v = str((prov.get("options") or {}).get("apiKey", ""))
    if not v:
        return "—"
    if v.startswith("{file:") or v.startswith("{env:"):
        return "ref"
    return "PLAIN"


def _ep_form(prov: dict) -> str:
    """opencode provider 端点形态: 网关(:4000) vs 直连引擎端口。2026-09-16。
    判据: 只认 options.baseURL 里的端口; 无 baseURL(如 openrouter 外呼)返回原 URL(缩略)。"""
    url = str((prov.get("options") or {}).get("baseURL", ""))
    if not url:
        return "—"
    if ":4000" in url:
        return "⚠ 网关:4000(已退役, 应直连)"
    if url.startswith("http://"):
        # 缩略: 只留 host:port, 省得 k8s/pod 路径刷屏
        try:
            return url.split("//")[1].split("/")[0]
        except Exception:
            return url
    return url


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
            # 端点形态 (2026-09-16): 判断是否仍过 :4000 网关, 还是已改直连引擎端口
            "eps": {k: _ep_form(v or {}) for k, v in providers.items()},
        }
    except Exception as e:
        res["opencode"] = {"error": f"parse: {type(e).__name__}"}
    try:
        cl = json.loads("\n".join(blocks.get("claude", [])))
        res["claude"] = _claude_forms(cl)
    except Exception as e:
        res["claude"] = {"error": f"parse: {type(e).__name__}"}
    res["hermes"] = (blocks.get("hermes", ["absent"]) or ["absent"])[0].strip()
    res["mem"] = blocks.get("mem") or []   # 记忆协同层 (memory.db + MEMORY.md), 2026-09-16
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
                ep = (oc.get("eps") or {}).get(name, "")
                flag = "  ← 明文!" if form == "PLAIN" else ""
                print(f"               {name:18s} key:{form:5s} ep:{ep}{flag}")
        cl = d.get("claude", {})
        if cl.get("error"):
            print(f"    claude   : {cl['error']}")
        else:
            flag = "  ← 明文!" if cl.get("token_form") == "PLAIN" else ""
            bu = cl.get("base_url") or "—"
            g = "  ⚠ 网关:4000!" if ":4000" in str(bu) else ""
            print(f"    claude   : 模型 {cl.get('model')}; apiKeyHelper {cl.get('helper')}; "
                  f"env token {cl.get('token_form')}{flag}; modelOverrides {cl.get('overrides')}"
                  f"; baseURL {bu}{g}")
        print(f"    hermes   : config.yaml {d.get('hermes')}")
        # 记忆协同层 (2026-09-16)
        mem = d.get("mem") or []
        if mem:
            print("    memory   : opencode 记忆库（见下）")
            for ln in mem:
                print(f"               {ln}")
        else:
            print("    memory   : — (未发现 opencode memory)")
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


# ── meta: 模型元数据 (2026-09-15, 方案 v2 P1-6) ────────────────────
# 目的: 让 `/api/models`(与 CLI) 每个模型都带上"它是什么/怎么跑的", 而不是只有
# 名字 + 体积。学自 llama-swap 的 `metadata` 字段 (方案 §A.2.1)。
#
# 数据源与优先级 (三个源各有权威面, 不做单一来源假设):
#   · ctx_native  ← GGUF `context_length`     模型自身的上下文上限 (改不了)
#   · ctx/params  ← 站上 conf `/etc/llama-instances/<alias>.env`
#                   **实际加载参数**。刻意不解析 spec/infer-load/params-ledger.md:
#                   那份台账是 conf 的**文档镜像**(其维护约定即"改 conf 必须同步台账"),
#                   解析 Markdown 表格既脆又会与站上实况漂移。取 conf 才是取真值。
#   · quant       ← ① inventory/models.yaml 的 `quant`(登记真值, 目前 2/11 覆盖)
#                   ② 文件名推断(实测模型文件名高度规范: -MXFP4 / -UD-IQ4_XS /
#                      -Q4_K_M-00001-of-00003 / -Q6_K-merged ...)
#                   并回传 `quant_src` 标明来源, 不假装它是权威值。
#                   **不用 GGUF `file_type` 枚举反查**: 2026-09-15 实测该枚举值
#                   为 7/8/18/30/38, 其中 18/30/38 已超出经典 llama_ftype 表
#                   (上游插入过新类型), 硬编码映射表必然过期。
#
# 代表文件必须是**第 1 分片**: llama.cpp 只在 `-00001-of-0000N.gguf` 里写完整 KV。
# 2026-09-15 实测踩到 —— 按体积取最大的分片时 nemotron 的 arch/file_type/ctx 全为空。
#
# 耗时特征: gguf-meta 只读头部, 实测 0.01~0.14s/文件 且**与文件大小无关**(156GB 的
# GLM 与 7GB 分片同为 ~0.1s)。故本采集随 `/api/models` 每次全量跑即可, 无需缓存。
_MODEL_META_SCAN = (
    "echo '===G==='; "
    # 深度用 -mindepth 2 且不限上限: 实测存在三种落点 ——
    #   gguf/<repo>/<file>.gguf            (仓库级直放, 见 group_by_model)
    #   gguf/<repo>/<Model>-GGUF/<f>.gguf
    #   gguf/<repo>/<Model>-GGUF/<QUANT>/<f>.gguf
    # 此前按 -mindepth 3 扫描会漏掉第一种 (B 站 davidau-q38-27b-q4k 即此形态)。
    "find -L /data/models/gguf -mindepth 2 -name '*.gguf' ! -name 'mmproj*' 2>/dev/null "
    "| while IFS= read -r f; do "
    "g=$(gguf-meta \"$f\" 2>/dev/null | tr -d ' '); "
    "c=$(printf '%s' \"$g\" | grep -o '\"context_length\":[0-9]*' | head -1 | cut -d: -f2); "
    "t=$(printf '%s' \"$g\" | grep -o '\"file_type\":[0-9]*' | head -1 | cut -d: -f2); "
    "a=$(printf '%s' \"$g\" | grep -o '\"arch\":\"[^\"]*\"' | head -1 | cut -d'\"' -f4); "
    "k=$(printf '%s' \"$g\" | grep -o '\"head_count_kv\":[0-9]*' | head -1 | cut -d: -f2); "
    "printf '%s|%s|%s|%s|%s\\n' \"$f\" \"$c\" \"$t\" \"$a\" \"$k\"; "
    "done; "
    "echo '===P==='; "
    "for f in /etc/llama-instances/*.env; do [ -e \"$f\" ] || continue; "
    "a=${f##*/}; a=${a%.env}; "
    "printf '%s|%s|%s|%s|%s|%s|%s\\n' \"$a\" "
    "\"$(sed -n 's/^CTX=//p' \"$f\" | head -1)\" "
    "\"$(sed -n 's/^PORT=//p' \"$f\" | head -1)\" "
    "\"$(sed -n 's/^BACKEND=//p' \"$f\" | head -1)\" "
    "\"$(sed -n 's/^THREADS=//p' \"$f\" | head -1)\" "
    "\"$(sed -n 's/^N_CPU_MOE=//p' \"$f\" | head -1)\" "
    "\"$(sed -n 's/^RPC_TARGET=//p' \"$f\" | head -1)\"; "
    "done"
)

# 量化串的形态: Q4_K_M / Q8_0 / IQ4_XS / UD-IQ4_XS / MXFP4 / F16 / BF16 / F32。
# 取 basename 里**最后一次**匹配 (模型名里可能含 Qwen3 之类, 但 Q 后必须紧跟数字,
# 故不会误命中; 量化串总在文件名末尾)。
_QUANT_RE = re.compile(
    r"(?:UD-)?(?:IQ\d[A-Za-z0-9_]*|Q\d[A-Za-z0-9_]*|MXFP\d[A-Za-z0-9_]*|BF16|F16|F32)")

INVENTORY_MODELS = Path(__file__).resolve().parent.parent / "inventory" / "models.yaml"


def infer_quant(filename: str) -> str:
    """从 gguf 文件名推断量化档 (如 `...-Q4_K_M-00001-of-00003.gguf` → `Q4_K_M`)。"""
    base = os.path.basename(filename)
    if base.lower().endswith(".gguf"):
        base = base[:-5]
    hits = _QUANT_RE.findall(base)
    return hits[-1].upper() if hits else ""


def ledger_quant(alias: str) -> str:
    """inventory/models.yaml 里登记的量化档 (登记真值; 未登记返回 "")。"""
    try:
        import yaml
        doc = yaml.safe_load(INVENTORY_MODELS.read_text(encoding="utf-8")) or {}
    except Exception:
        return ""
    for it in doc.get("models") or []:
        if isinstance(it, dict) and str(it.get("alias")) == alias:
            return str(it.get("quant") or "")
    return ""


def resolve_quant(alias: str, filename: str) -> tuple:
    """(量化串, 来源)。登记值优先; 否则文件名推断; 都没有则空串。"""
    q = ledger_quant(alias)
    if q:
        return q, "ledger"
    q = infer_quant(filename)
    return (q, "filename") if q else ("", "none")


def parse_model_meta(text: str) -> dict:
    """解析 `_MODEL_META_SCAN` 输出 → {gguf: {path: {...}}, params: {alias: {...}}}。

    gguf 段一行一文件 (含**所有**分片), 由调用方按模型分组后取代表分片 ——
    这样分组规则只有一处 (见 cluster_web._station_models 的 (repo, model_dir))。
    """
    gguf, params = {}, {}
    sec, cur = {}, None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("===") and s.endswith("==="):
            cur = s.strip("=")
            sec[cur] = []
        elif cur:
            sec[cur].append(line)
    for line in sec.get("G", []):
        parts = line.strip().split("|")
        if len(parts) < 5 or not parts[0].startswith("/"):
            continue

        def _num(x):
            try:
                return int(x)
            except (TypeError, ValueError):
                return None

        gguf[parts[0]] = {"ctx": _num(parts[1]), "file_type": _num(parts[2]),
                          "arch": parts[3], "head_count_kv": _num(parts[4])}
    for line in sec.get("P", []):
        p = line.strip().split("|")
        if len(p) < 7 or not p[0]:
            continue
        params[p[0]] = {"ctx": p[1], "port": p[2], "backend": p[3],
                        "threads": p[4], "n_cpu_moe": p[5], "rpc_target": p[6]}
    return {"gguf": gguf, "params": params}


def probe_model_meta(st: str) -> dict:
    """单站采集模型元数据 (CLI 用; Web 侧把它并进自己那次扫描, 省一轮 ssh)。"""
    ok, out = ssh_run(st, _MODEL_META_SCAN, timeout=120)
    return parse_model_meta(out) if ok else {"gguf": {}, "params": {}}


def pick_representative(paths: list) -> str:
    """从同一模型的多个 gguf 里挑代表文件。

    必须优先 `-00001-of-0000N`: llama.cpp 只在第 1 分片写完整 KV metadata,
    其余分片的 arch/file_type/ctx 均为空 (2026-09-15 实测)。
    """
    if not paths:
        return ""
    for p in paths:
        if "-00001-of-" in os.path.basename(p):
            return p
    return sorted(paths)[0]


MODELS_ROOT = "/data/models/gguf/"


def alias_of(model_dir: str) -> str:
    """模型目录名 → infer-load 别名。规则与站上 infer-load 保持一致（含 minimax 重映射）。

    单一定义点: CLI 与 Web 都从这里取, 否则同一模型在两处会被算成不同别名,
    进而查不到 conf 参数 (P1-6 的 conf 摘要按别名匹配)。
    """
    a = re.sub(r"-GGUF$", "", model_dir, flags=re.I).lower()
    return "m27-q4ks" if a.startswith("minimax-m2.7") else a


def group_by_model(paths) -> dict:
    """把 gguf 路径按 (repo, model_dir) 分组 —— 与 infer-load 的模型粒度一致。

    取 marker 之后**前两段**: 模型目录下可能还有子目录 (如
    `MiniMax-M2.7-GGUF/UD-IQ4_XS/*.gguf`), 用倒数两段会把 MiniMax 误显示为
    UD-IQ4_XS (2026-09-15 实测踩到)。此处是该规则的单一定义点, Web 侧复用之。

    第二段若是**文件**（`<repo>/<file>.gguf`, 即仓库级直放），则 model_dir 记空串。
    这种形态 2026-09-15 在 B 站实测到（`davidau-q38-27b-q4k/` 下直接放 gguf）:
    它既不在物理库、也不是软链, 是允许的"本地物理存放"; 而此前按 `-mindepth 3`
    扫描的口径看不到它 —— 有 conf、能加载, 却在模型清单与 infer-list 里都不存在。
    """
    out = {}
    for p in paths:
        if MODELS_ROOT not in p:
            continue
        seg = p.split(MODELS_ROOT, 1)[1].split("/")
        if len(seg) < 2:
            continue
        sub = "" if seg[1].lower().endswith(".gguf") else seg[1]
        out.setdefault((seg[0], sub), []).append(p)
    return out


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
              f"{r.get('version','?')} · built {r.get('built','?')}"
              + (f" · rpc_protocol {r['rpc_protocol']}" if r.get("rpc_protocol") else ""))
        print(f"    完整性  md5sum -c (MANIFEST) {d.get('md5','?')}")
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
        print(f"  {'模型目录':<46} {'原生ctx':>9}  {'量化':<15} {'加载ctx':>9} "
              f"{'后端':<13} {'port':>6}  conf 参数")
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
            print(f"  {label:<46} {str(m.get('ctx') or '-'):>9}  "
                  f"{(q + '(' + qsrc + ')') if q else '-':<15} "
                  f"{str(p.get('ctx') or '-'):>9} {str(p.get('backend') or '-'):<13} "
                  f"{str(p.get('port') or '-'):>6}  {pstr}")
            confs.discard(alias)
        # conf 有、模型库无: 指向的权重可能已被删 (与 stations 断言的 (e) 子项呼应)
        for a in sorted(confs):
            if params[a].get("ctx") or params[a].get("port"):
                print(f"  [仅 conf 无模型目录] {a}")
    print()
    return 0


def cmd_models(argv) -> int:
    """cluster.py models {list|orphan|link|prune|verify|meta} [--station A|B|C] [--go]

    list   三站模型资产概览（物理库 / 聚合视图 / 孤儿 / 断链 计数）
    orphan 只列孤儿与断链详情（诊断用）
    link   给孤儿补软链（默认 dry-run, 加 --go 才写入; 可 --station 限定单站）
    prune  清理死链（默认 dry-run, 加 --go 才写入）
    verify 断链检查 + 主 gguf 可读性抽验（gguf-meta）
    meta   模型元数据表: 原生 ctx / 量化(含来源) / 站上 conf 加载参数 (P1-6)
    """
    act = (argv[0] if argv else "list").lower()
    if act not in ("list", "orphan", "link", "prune", "verify", "meta"):
        print("用法: cluster.py models {list|orphan|link|prune|verify|meta} "
              "[--station A|B|C] [--go]")
        return 1
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


# ── reqlog: 引擎请求/时延/token 统计 (2026-09-15, 方案 v2 P2-3) ────
# 形态: **采样式日志** —— 站上 `reqlog sample` 读 llama.cpp 原生 /metrics + /slots,
#   与上一条样本做差分, 追加一行 JSONL 到 `~/.local/share/rpc/reqlog.jsonl`。
#   主控侧读回原文做聚合 (聚合逻辑只有一处, 不放到站上重复一遍)。
#
# 为什么是采样而不是逐请求日志: llama.cpp 没有逐请求接口, `/metrics` 只有累计计数器;
#   逐请求时延只能解析 server 日志文本 —— 脆且依赖 unsloth 的日志格式。差分采样是
#   唯一能自证的口径。**也不伪造"请求数"**: 实测 /metrics 无 requests 计数器
#   (只有 requests_processing / requests_deferred 两个 gauge), 故汇总里显示 n/a。
#
# 口径 (手册"基准对比铁律": 三种口径互不可比):
#   引擎耗时口径 = ΣΔtoken / ΣΔ引擎耗时   ← 与 API timings 可比, **主口径**, 且必须**加权**平均
#                                            (逐条平均比值会被短样本带偏)
#   墙钟口径     = ΣΔtoken / ΣΔ采样间隔   ← 含引擎空闲, 只作辅助 (配 busy 占比解释)
#
# 采样触发: **按需** (`cluster.py reqlog sample` 或 Web 按钮)。刻意不做常驻采样服务 ——
#   沿用方案 §5.4「不新增常驻服务」的边界。要连续采样, 用主控站的计划任务周期调用它。
# 站上日志落点: `~/.local/share/rpc/reqlog.jsonl` (站上 `reqlog path` 可查)


def _reqlog_station(st: str, act: str, n: int = 200) -> dict:
    cmd = {"sample": "reqlog sample",
           "path": "reqlog path",
           "tail": f"reqlog tail -n {n}"}[act]
    ok, out = ssh_run(st, cmd, timeout=90)
    recs = []
    if act == "tail" and ok:
        for line in out.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                recs.append(json.loads(line))
            except Exception:
                continue
    return {"station": st, "ok": ok, "out": (out or "").strip(), "recs": recs}


def _reqlog_aggregate(recs: list, minutes: int = None) -> dict:
    """按站点记录聚合。吞吐一律**加权** (ΣΔtoken / ΣΔ耗时), 不逐条平均比值。"""
    if minutes:
        cut = time.time() - minutes * 60
        recs = [r for r in recs if float(r.get("t") or 0) >= cut]
    agg = {"n": len(recs), "p_tok": 0.0, "g_tok": 0.0, "p_sec": 0.0, "g_sec": 0.0,
           "wall": 0.0, "restarts": 0, "peak_proc": 0, "peak_slots": 0,
           "cached_tok": 0.0, "decode_n": 0.0,
           "first": None, "last": None, "ports": set()}
    for r in recs:
        agg["p_tok"] += float(r.get("d_prompt_tokens_total") or 0)
        agg["g_tok"] += float(r.get("d_tokens_predicted_total") or 0)
        agg["p_sec"] += float(r.get("d_prompt_seconds_total") or 0)
        agg["g_sec"] += float(r.get("d_tokens_predicted_seconds_total") or 0)
        agg["wall"] += float(r.get("dt_s") or 0)
        agg["cached_tok"] += float(r.get("d_prompt_tokens_cached_total") or 0)
        agg["decode_n"] += float(r.get("d_n_decode_total") or 0)
        agg["restarts"] += 1 if r.get("restart") else 0
        agg["peak_proc"] = max(agg["peak_proc"], float(r.get("requests_processing") or 0))
        agg["peak_slots"] = max(agg["peak_slots"], float(r.get("slots_busy") or 0))
        t = float(r.get("t") or 0)
        agg["first"] = t if agg["first"] is None else min(agg["first"], t)
        agg["last"] = t if agg["last"] is None else max(agg["last"], t)
        if r.get("port"):
            agg["ports"].add(r["port"])
    agg["p_tps"] = round(agg["p_tok"] / agg["p_sec"], 1) if agg["p_sec"] > 0 else None
    agg["g_tps"] = round(agg["g_tok"] / agg["g_sec"], 1) if agg["g_sec"] > 0 else None
    # 墙钟口径 (含引擎空闲): 与主口径并列暴露, 差异由「忙占比」解释。
    # 前端会同时渲染两列, 故这里必须产出 —— 早版漏了这两个字段, 前端只能显示 '-'
    # (2026-09-15 实测: 前后端字段不一致, 页面看不出问题但值永远是空的)。
    agg["p_tps_wall"] = round(agg["p_tok"] / agg["wall"], 1) if agg["wall"] > 0 else None
    agg["g_tps_wall"] = round(agg["g_tok"] / agg["wall"], 1) if agg["wall"] > 0 else None
    agg["g_busy_ratio"] = round(agg["g_sec"] / agg["wall"], 3) if agg["wall"] > 0 else None
    agg["span_s"] = (agg["last"] - agg["first"]) if agg["first"] and agg["last"] else None
    return agg


def cmd_reqlog(argv) -> int:
    """cluster.py reqlog {sample|summary|tail|path} [--minutes N] [--tail N] [--station X]

    采样式引擎统计 (P2-3): 站上 `/metrics`+`/slots` 差分 → JSONL → 主控聚合。
    口径: 引擎耗时口径为主 (与 API timings 可比), 墙钟口径为辅 (含空闲)。
    """
    act = (argv[0] if argv else "summary").lower()
    if act not in ("sample", "summary", "tail", "path"):
        print("用法: cluster.py reqlog {sample|summary|tail|path} "
              "[--minutes N] [--tail N] [--station A|B|C]")
        return 1
    only, minutes, n = None, None, 200
    i = 1
    while i < len(argv):
        if argv[i] == "--station" and i + 1 < len(argv):
            only = argv[i + 1].upper()
            i += 2
            continue
        if argv[i] == "--minutes" and i + 1 < len(argv):
            minutes = int(argv[i + 1])
            i += 2
            continue
        if argv[i] == "--tail" and i + 1 < len(argv):
            n = int(argv[i + 1])
            i += 2
            continue
        i += 1
    stations = [only] if only else ["A", "B", "C"]

    if act == "sample":
        res, threads = {}, []
        for st in stations:
            t = threading.Thread(target=lambda s=st: res.__setitem__(s, _reqlog_station(s, "sample")))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        rc = 0
        for st in stations:
            r = res.get(st, {})
            print(f"[reqlog] {st} 站: {(r.get('out') or '(无输出)')}")
            if not r.get("ok"):
                rc = 1
        return rc

    if act == "path":
        for st in stations:
            r = _reqlog_station(st, "path")
            print(f"[reqlog] {st} 站: {r.get('out')}")
        return 0

    # summary / tail
    res, threads = {}, []
    for st in stations:
        t = threading.Thread(target=lambda s=st: res.__setitem__(s, _reqlog_station(s, "tail", n)))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    if act == "tail":
        for st in stations:
            r = res.get(st, {})
            print(f"\n=== {st} 站 ({len(r.get('recs') or [])} 条) ===")
            for rec in (r.get("recs") or [])[-n:]:
                print(json.dumps(rec, ensure_ascii=False))
        return 0

    print(f"\n=== 引擎请求/token 统计 (P2-3, {('近 %d 分钟' % minutes) if minutes else '全部样本'}) ===")
    print(f"  口径: **引擎耗时口径** = ΣΔtoken/ΣΔ引擎耗时 (与 API timings 可比); "
          f"墙钟口径 = ΣΔtoken/ΣΔ采样间隔 (含空闲, 辅助)\n")
    hdr = (f"  {'站':<3} {'样本':>4} {'跨度':>7} {'prompt tok':>10} {'gen tok':>9} "
           f"{'pp t/s':>8} {'tg t/s':>8} {'忙占比':>7} {'峰值并发':>8} {'重启':>4}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    any_rec = False
    for st in stations:
        r = res.get(st, {})
        if not r.get("ok"):
            print(f"  {st:<3} 站不可达/取日志失败")
            continue
        recs = r.get("recs") or []
        if not recs:
            print(f"  {st:<3} 无样本 (引擎未运行过, 或从未采样) "
                  f"—— 用 `cluster.py reqlog sample` 采一次")
            continue
        any_rec = True
        a = _reqlog_aggregate(recs, minutes)
        span = f"{a['span_s']}s" if a["span_s"] else "-"
        print(f"  {st:<3} {a['n']:>4} {span:>7} {a['p_tok']:>10.0f} {a['g_tok']:>9.0f} "
              f"{str(a['p_tps'] or '-'):>8} {str(a['g_tps'] or '-'):>8} "
              f"{str(a['g_busy_ratio'] if a['g_busy_ratio'] is not None else '-'):>7} "
              f"{a['peak_proc']:>8.0f} {a['restarts']:>4}")
        if a["restarts"]:
            print(f"      · 含 {a['restarts']} 次引擎重启 (计数器已归零, 增量从 0 起算)")
        if a["cached_tok"]:
            print(f"      · KV 前缀缓存命中 {a['cached_tok']:.0f} tok "
                  f"(占 prompt 的 {a['cached_tok'] / max(a['p_tok'], 1) * 100:.0f}%)")
        print(f"      · 端口 {sorted(a['ports']) or '-'} · decode 批次 {a['decode_n']:.0f} "
              f"· 采样峰值槽占用 {a['peak_slots']:.0f}")
    if any_rec:
        print(f"\n  注: /metrics 实测**无 requests 计数器** (只有 requests_processing 两个 gauge), "
              f"故不给「请求数」—— 不拿 decode 批次数冒名顶替")
    return 0


# ── flow: 声明式流程 (2026-09-15, 方案 v2 P2-1) ────────────────────
# 目的: 把"一次操作要走的一串步骤"从散落的一次性脚本收敛成**声明式表** ——
#   每个 flow 声明「步骤 → 判据 → 台账落点」, 一次跑完并留下记录。
# 学 LM Studio 的"一次点击完成一件事"; 范式来自 archive/scripts-history/b5_bench_cluster.sh
#   的五段式(读声明 → 起依赖 → 执行 → **无条件收尾** → 落账), 判据用退出码分层。
#
# 设计约定 (与既有纪律对齐):
#   · **只读 flow 默认执行; 会改站上状态的 flow 默认只出计划, 加 --go 才动手**
#     (沿用 `cluster.py models link|prune` 的 dry-run 约定)
#   · 判据既写进 step 的 run() 也用 criteria 字符串**声明出来** —— `flow <name> --plan`
#     会把"步骤→判据"整表打印, 跑之前就知道要满足什么
#   · 任一步 ok=False **立即中止**(fail-fast), 并执行已登记的 teardown
#   · 台账**只增不改**, 每条必带 日期 / 判据(口径) / 证据 三要素
#     (metrics-log 既有教训: 缺任一要素的记录无法复核)
#
# 为什么台账写入器是净新增件: 查过三份台账, **在此之前没有任何脚本写它们** ——
#   b5_bench_cluster.sh 只 echo 到 stdout(其 DESIGN 声称"自动追加 metrics-log"从未落地);
#   手册也写了"结果自动追加到 metrics-log", 同样是空头承诺。P2-1 补上这一环。
#
# 台账落点为何只挂 metrics-log: params-ledger 的表是「参数变更」(§4 修改历史),
#   results-ledger 是「模型评测」(按模型分节 + 5 列题号表), 各有专属 schema;
#   由脚本往别人的表里塞异构行会写坏它。故 flow 统一落 metrics-log 的"运行记录"节,
#   另两份台账保持人工维护 (不假装支持)。
REPO_ROOT = Path(__file__).resolve().parent.parent
LEDGERS = {"metrics-log": REPO_ROOT / "spec" / "rpc-optimization" / "metrics-log.md"}
FLOW_SECTION = "## Phase 7: flow 运行记录 (2026-09-15 起, 由 `cluster.py flow` 自动追加)"
FLOW_TABLE_HEAD = ("| 日期 | flow | 目标 | 判据(口径) | 结果 | 证据 |\n"
                   "|---|---|---|---|---|---|")


def _ledger_append(ledger: str, row: str, dry: bool = True) -> str:
    """把一行记录追加到台账 (只增不改; 缺节则先补节与表头)。"""
    p = LEDGERS.get(ledger)
    if not p:
        return f"未知台账 {ledger!r} (可选: {', '.join(LEDGERS)})"
    if not p.is_file():
        return f"台账文件不存在: {p}"
    if dry:
        return f"[dry-run] 将追加到 {p.name}: {row}"
    text = p.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    if FLOW_SECTION not in text:
        text += f"\n{FLOW_SECTION}\n\n{FLOW_TABLE_HEAD}\n"
    text += row + "\n"
    p.write_text(text, encoding="utf-8")
    return f"已追加到 {p.name}"


def _flow_find_engine() -> tuple:
    """找"哪个站在服务"。返回 (station, port) 或 (None, None)。"""
    for st in ("A", "B", "C"):
        try:
            mt = probe_metrics(st)
        except Exception:
            continue
        if mt.get("port"):
            return st, mt["port"]
    return None, None


def _flow_bench_payload() -> str:
    """标准请求体。刻意**记录** prompt 的实际 token 数(取响应 timings), 而非假装它是 pp512。"""
    filler = "The quick brown fox jumps over the lazy dog. "
    return json.dumps({
        "model": "main",          # 引擎忽略该字段(ports.yaml 已登记), 仅占位
        "messages": [{"role": "user", "content": filler * 40}],
        "max_tokens": 128, "temperature": 0, "stream": False,
    })


def resolve_host_alias(alias: str) -> str:
    """别名 → 目标站代号 (借 resolve_alias, 只取站; 解析失败退默认站)。"""
    try:
        st, _real, _rpc, _how = resolve_alias(alias)
    except AliasError:
        return DEFAULT_STATION
    return st or DEFAULT_STATION


def _flow_step_probe_engine(ctx) -> tuple:
    st, port = _flow_find_engine()
    if st:
        ctx["station"], ctx["port"] = st, port
        return True, f"{st} 站引擎在服务 (127.0.0.1:{port})", []
    if ctx.get("alias"):
        ctx["station"] = resolve_host_alias(ctx["alias"])
        return (True if ctx["go"] else False,
                f"无引擎在服务; 目标是 {ctx['station']} 站的 {ctx['alias']}"
                + ("" if ctx["go"] else " —— 需要 --go 才会加载"),
                ["零自加载方针: 本 flow 不会擅自加载, 故默认只出计划"])
    return False, "三站都没有引擎在服务, 且未指定 alias", \
        ["用法: cluster.py flow bench [<alias前缀>] --go"]


def _flow_step_ensure_loaded(ctx) -> tuple:
    if ctx.get("port"):
        return True, "已在服务, 跳过加载", []
    if not ctx["go"]:
        return False, "需要加载 (--go 才执行)", []
    est = estimate_load(ctx["station"], ctx["alias"])
    ctx["estimate"] = est
    verdict = est.get("verdict", "UNKNOWN")
    if verdict == "NO_FIT":
        return False, f"事前预估 NO_FIT, 拒绝加载: {est.get('reasons')}", []
    rc = cmd_load(ctx["alias"])
    if rc != 0:
        return False, f"加载失败 (rc={rc})", []
    ctx["loaded_here"] = True
    st, port = _flow_find_engine()
    ctx["station"], ctx["port"] = st, port
    return (port is not None), f"加载完成, 引擎在 {st}:{port}", \
        ([f"预估: {verdict} need={est.get('need_gib')}G"] if est else [])


def _flow_step_bench(ctx) -> tuple:
    if not ctx.get("port"):
        return False, "无引擎可测", []
    st = ctx["station"]
    body = _flow_bench_payload().replace("'", "")
    cmd = (f"curl -s -m 300 -H 'Content-Type: application/json' -d '{body}' "
           f"http://127.0.0.1:{ctx['port']}/v1/chat/completions")
    ok, out = ssh_run(st, cmd, timeout=330)
    if not ok or not out.strip().startswith("{"):
        return False, f"请求失败: {(out or '')[:120]}", []
    try:
        r = json.loads(out)
        t = r.get("timings") or {}
    except Exception as e:
        return False, f"响应解析失败: {type(e).__name__}", [out[:160]]
    if not t:
        return False, "响应无 timings 字段 (非 llama.cpp 原生引擎?)", [out[:160]]
    ctx["timings"] = t
    return True, (f"pp {t.get('prompt_n')} tok @ {t.get('prompt_per_second', 0):.1f} t/s · "
                  f"tg {t.get('predicted_n')} tok @ {t.get('predicted_per_second', 0):.1f} t/s"), []


def _flow_teardown_bench(ctx) -> tuple:
    if not ctx.get("loaded_here"):
        return True, "本 flow 未加载, 无需收尾", []
    rc = cmd_unload()
    st, port = _flow_find_engine()
    return (rc == 0 and port is None), \
        f"已卸载 (rc={rc}); 复核: {'引擎已停' if port is None else f'仍在 {st}:{port}'}", []


def _flow_verify_checks(ctx) -> tuple:
    """复用健康引擎的断言表 (只读)。"""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import rpc_check
    except Exception as e:
        return False, f"无法导入 rpc_check ({type(e).__name__})", []
    want = ["inventory", "ports", "plugins", "aliases", "usb4", "gates", "engine",
            "models", "stations"]
    detail, fails = [], []
    for c in rpc_check.CHECKS:
        if c["id"] not in want:
            continue
        try:
            status, note, _d = c["fn"]({})
        except Exception as e:
            status, note = "FAIL", f"{type(e).__name__}: {e}"
        detail.append(f"[{status}] {c['id']:10s} {note}")
        if status == "FAIL":
            fails.append(c["id"])
    ctx["verify_failed"] = fails
    return (not fails), f"断言 {len(detail)} 项, 失败 {len(fails)} 项" + (
        f": {', '.join(fails)}" if fails else ""), detail


def _flow_rotate_status(ctx) -> tuple:
    ok, out = ssh_run("A", "true", timeout=20)   # 借一次 ssh 判可达性
    verdicts = {}
    for st in ("A", "B", "C"):
        ok, out = ssh_run(st, SECRETS_PROBE, timeout=90)
        verdicts[st] = _secrets_verdict(out) if ok else "UNREACHABLE"
    ctx["rotate_verdicts"] = verdicts
    bad = [s for s, v in verdicts.items() if v != "OK"]
    return (not bad), "凭据落点/引用/权限: " + ", ".join(f"{s}={v}" for s, v in verdicts.items()), \
        ([f"{s} 站需关注 —— 见 `cluster.py secrets status`" for s in bad] if bad else [])


def _flow_rotate_scan(ctx) -> tuple:
    """明文门禁: 直接复用既有 `secrets scan`（它已覆盖"三站生效配置 + 归档"）。"""
    print("        (调用 cluster.py secrets scan ...)")
    rc = cmd_secrets("scan")
    return rc == 0, f"secrets scan rc={rc} (0=无明文命中)", \
        ([] if rc == 0 else ["有明文残留 —— 先按 scan 输出定位再轮换"])


def _flow_rotate_push(ctx) -> tuple:
    if not ctx["go"]:
        return False, "需要下发正本 (--go 才执行)", ["改完 secrets/stations/<站>/ 后执行"]
    rc = cmd_secrets("push")
    return rc == 0, f"正本下发 rc={rc}", []


def _flow_swap_precheck(ctx) -> tuple:
    est = estimate_load(ctx["station"], ctx["alias"])
    ctx["estimate"] = est
    v = est.get("verdict", "UNKNOWN")
    ok = v in ("FITS", "TIGHT")
    return ok, f"事前预估 {v} · need {est.get('need_gib')}G / 可用 {est.get('avail_effective')}G", \
        ([] if ok else (est.get("advice") or ["预估不通过在, 拒绝切换"]))


def _flow_swap_apply(ctx) -> tuple:
    """卸载与加载都在 cmd_load_on 里 (它先探 :8080 占用 → infer-unload → 加载)。

    刻意不再自己拆成一卸一装 —— 那会把"先卸后装、等 GTT 释放"的既有语义复制一份,
    两处实现迟早漂移 (与 P1-6 "取 conf 而非抄台账"同一条理由)。
    """
    if not ctx["go"]:
        return False, "需要按站加载 (--go)", []
    st, backend = ctx["station"], ctx.get("backend")
    rc = cmd_load_on(st, ctx["alias"], backend) if backend else cmd_load_on(st, ctx["alias"])
    return rc == 0, f"{st} 站加载 {ctx['alias']} rc={rc}", []


def _flow_swap_ready(ctx) -> tuple:
    st = ctx["station"]
    ps = probe_station(st, with_list=False)
    mt = probe_metrics(st)
    ok = ps.get("llama") == "READY" and bool(mt.get("port"))
    return ok, f"{st} 站 llama={ps.get('llama')} 引擎端口={mt.get('port') or '无'}", \
        ([] if ok else ["就绪判据未满足 —— 见 inference 日志 / infer-load 输出"])


def _flow_ledger_step(ctx) -> tuple:
    """统一的落账步骤: 只增不改 + 三要素。默认 dry-run。"""
    row = ctx.get("ledger_row")
    if not row:
        return True, "无记录可落 (跳过)", []
    msg = _ledger_append(ctx.get("ledger") or "metrics-log", row, dry=not ctx["go"])
    ctx["ledger_msg"] = msg
    return True, msg, []


# ── P2-4 路径对比 (单机 vs 双机) ───────────────────────────────────
# 供"决策门"用: 同一模型在两条路径上各跑一次实测基准, 输出对照表 + 推荐。
# **刻意不 fail-fast**: 对比类 flow 的判据是"每条路径都给出结论(可用/不可用 + 数据)",
# 而不是"任一条失败即中止" —— 某条路径跑不通本身就是决策所需的信息。
# (bench/swap/rotate 仍走 fail-fast; 这是 flow 声明的 continue_on_fail 开关。)
#
# 为什么双机侧不给"事前预估": `estimate_load` 的口径是**整个模型落在一站**,
# 而 RPC 会把层拆到两站, 权重与 KV 都分摊 —— 拿单站口径去套会得出错误结论。
# 与其编一个看似精确的粗判数字, 不如只给单机的精确预估 + 双机的**实测**。
# (双机是否可行的第一手判据 = 它能不能加载起来, 这也是实测能给的。)
def _station_gtt_gib(st: str):
    """站上 GTT 占用合计 (GiB); 取不到返回 None。

    **为什么内存代价必须用 GTT 而不是进程 RSS**: 本集群是 UMA (AMD 8060S), 模型权重驻留
    在 GTT/显存, **不进进程 RSS** —— 2026-09-15 实测: 加载 77G 的
    gpt-oss-120b-fable-5-distilled 后 `ps` 里 llama-server 的 RSS 只有 **217MB**,
    而同刻 GTT 是 **54.6 GB**, MemAvailable 掉了 57G。
    GTT 也正是站上前提门禁 (load-gate / infer-load 的 `mem_info_gtt_used`) 用的口径,
    故与"能不能装下"的判定同源。
    (另: `_station_mem` 的 `avail` 本身就是 **GiB**, 早版我又除了一次 1024 → 得 0.1G 假象。)
    """
    ok, out = ssh_run(st, "for f in /sys/class/drm/card*/device/mem_info_gtt_used; do "
                          "[ -f \"$f\" ] && cat \"$f\"; done")
    if not ok:
        return None
    tot = sum(int(x) for x in out.split() if x.isdigit())
    return round(tot / 1024 ** 3, 1)


def _flow_path_measure(ctx, backend: str, label: str) -> tuple:
    """跑一条路径: 预估(仅单机) → 加载 → 标准请求 → 卸载, 记录实测。"""
    st = ctx["station"]
    alias = ctx["alias"]
    rec = {"backend": backend, "label": label}
    gtt0 = _station_gtt_gib(st)
    t0 = time.time()
    rc = cmd_load_on(st, alias, backend)
    rec["load_s"] = round(time.time() - t0, 1)
    gtt1 = _station_gtt_gib(st)
    rec["gtt_gib"] = gtt1
    try:
        rec["gtt_used_gib"] = round(max(0.0, (gtt1 or 0) - (gtt0 or 0)), 1)
    except Exception:
        rec["gtt_used_gib"] = None
    if rc != 0:
        rec["ok"] = False
        rec["note"] = f"加载失败 rc={rc}"
        ctx.setdefault("paths", []).append(rec)
        cmd_unload()
        return False, f"{label}: 加载失败 (rc={rc}) —— 该路径不可用", \
            [f"加载耗时 {rec['load_s']}s"]
    port = probe_metrics(st).get("port")
    if not port:
        rec["ok"] = False
        rec["note"] = "加载后取不到内层引擎端口"
        ctx.setdefault("paths", []).append(rec)
        cmd_unload()
        return False, f"{label}: 加载后无引擎端口 —— 该路径不可用", []
    # **后端生效性判据 (本 flow 的核心防线)**: 判据不能只看"以为选了什么", 要看**进程
    # 命令行里到底有没有 --rpc**。2026-09-15 实测: `--backend llama-single` 因 conf 的
    # RPC_TARGET 未被清空 → 实际仍是双机, 于是"单机 vs 双机"两边都是双机;
    # 没有这一项, 这种错误数据会一路写进台账被当成结论。
    #
    # ⚠ 取命令行必须避开两个坑 (都实测踩到过):
    #   1) `pgrep -f llama-server` 会**匹配到执行它的 bash -c 包装进程本身** →
    #      `head -1` 拿到的是 bash 的 cmdline, 判据直接失效。改用 `pgrep -x` (按进程名
    #      **精确**匹配, 不做全命令行匹配) 就不会自匹配。
    #   2) 不截断: --rpc 往往出现在很长的命令行**靠后**位置, 截前 120 字符会漏判。
    # 故: 按 comm 精确取 pid → 读 /proc/<pid>/cmdline (NUL 转空格) 全文。
    cmdline = ssh_run(st, "p=$(pgrep -x llama-server | head -1); "
                          "[ -n \"$p\" ] && tr '\\0' ' ' < /proc/$p/cmdline || echo NOENGINE")[1]
    rpc_active = " --rpc" in f" {cmdline}"
    rec["rpc_active"] = rpc_active
    # 记下实际用了**哪些** worker —— RPC 路径可能是 1 个或 2 个 worker, 不记就说不清
    # 对照里的"双机"到底是几机 (nodes.env 声明 A+C, 都可能被用上)。
    m = re.search(r"--rpc\s+(\S+)", cmdline)
    rec["rpc_nodes"] = m.group(1) if m else None
    if rpc_active != (backend == "llama-rpc"):
        rec["ok"] = False
        rec["note"] = (f"请求 {backend}, 但进程{'含' if rpc_active else '不含'} --rpc "
                       f"—— 该路径未按请求生效, **数据不可用于对照**")
        ctx.setdefault("paths", []).append(rec)
        cmd_unload()
        return False, f"{label}: 后端未生效 —— {rec['note']}", [cmdline.strip()[:150]]
    body = _flow_bench_payload().replace("'", "")
    ok, out = ssh_run(st, f"curl -s -m 300 -H 'Content-Type: application/json' -d '{body}' "
                          f"http://127.0.0.1:{port}/v1/chat/completions", timeout=330)
    try:
        t = json.loads(out).get("timings") or {}
    except Exception:
        t = {}
    rec["port"] = port
    rec["pp_tps"] = round(t.get("prompt_per_second", 0), 1) or None
    rec["tg_tps"] = round(t.get("predicted_per_second", 0), 1) or None
    rec["prompt_n"] = t.get("prompt_n")
    rec["gen_n"] = t.get("predicted_n")
    rec["ok"] = bool(t)
    rec["note"] = "实测通过" if t else f"请求无 timings: {(out or '')[:80]}"
    ctx.setdefault("paths", []).append(rec)
    cmd_unload()                      # 每条路径跑完立刻收尾, 避免两条路径的残留互相污染内存读数
    if not t:
        return False, f"{label}: 请求无 timings —— 数据不可用", [rec["note"]]
    return True, (f"{label}: pp {rec['pp_tps']} t/s · tg {rec['tg_tps']} t/s "
                  f"(加载 {rec['load_s']}s, GTT +{rec['gtt_used_gib']}G)"), []


def _flow_paths_single(ctx) -> tuple:
    est = estimate_load(ctx["station"], ctx["alias"])
    ctx["est_single"] = est
    v = est.get("verdict", "UNKNOWN")
    ok = v in ("FITS", "TIGHT")
    return ok, f"单机事前预估 {v} · need {est.get('need_gib')}G / 可用 {est.get('avail_effective')}G", \
        ([] if ok else (est.get("advice") or ["预估不通过 —— 单机路径不可行"]))


def _flow_paths_run_single(ctx) -> tuple:
    return _flow_path_measure(ctx, "llama-single", "单机")


def _flow_paths_run_rpc(ctx) -> tuple:
    return _flow_path_measure(ctx, "llama-rpc", "双机 RPC")


def _flow_paths_report(ctx) -> tuple:
    """对照表 + 推荐。判据: 两条路径都有结论 (可用/不可用)。"""
    rows = ctx.get("paths") or []
    if not rows:
        return False, "没有任何路径的实测数据", []
    detail = []
    good = [r for r in rows if r.get("ok") and r.get("tg_tps")]
    for r in rows:
        detail.append(f"{r['label']:8s} {r['backend']:13s} "
                      f"{'✓' if r.get('ok') else '✕'} "
                      f"rpc={'是' if r.get('rpc_active') else '否'}"
                      + (f"({r.get('rpc_nodes')})" if r.get("rpc_nodes") else "")
                      + f" pp={r.get('pp_tps')} tg={r.get('tg_tps')} "
                      f"加载={r.get('load_s')}s GTT +{r.get('gtt_used_gib')}G "
                      f"({r.get('note', '')})")
    if len(rows) < 2:
        detail.append("只有一条路径有数据 —— 对照不完整 (另一条路径可能在加载阶段就失败了)")
    if good:
        best = max(good, key=lambda r: r["tg_tps"])
        # 推荐 = decode 更快者; 同档时选内存代价小的 (单机通常更省)
        detail.append(f"→ 推荐: **{best['label']}** ({best['tg_tps']} t/s) —— "
                      f"另一条路径 "
                      + (f"{min((r['tg_tps'] for r in good if r is not best), default=0)} t/s"
                         if len(good) > 1 else "无可用数据"))
    est = ctx.get("est_single") or {}
    if est.get("verdict"):
        detail.append(f"单机事前预估 {est['verdict']} (need {est.get('need_gib')}G) "
                      f"vs 实测 tg {next((r['tg_tps'] for r in rows if r['backend'] == 'llama-single'), '-')} t/s "
                      f"—— 预估判可行性与实测性能是两件事")
    ctx["paths_ok"] = bool(len(rows) >= 2 and any(r.get("ok") for r in rows))
    return bool(rows), f"{len(rows)} 条路径有结论, 其中 {len(good)} 条可用", detail


# 每个 flow: 步骤 → 判据 → 台账落点。dry_default=True 者默认只出计划。
FLOWS = {
    "verify": {
        "title": "健康引擎全项校验",
        "desc": "复用 rpc_check 的 9 项三站断言, 一次给结论 (只读)",
        "dry_default": False,      # 只读 → 默认执行
        "ledger": "metrics-log",
        "steps": [
            ("checks", "健康引擎断言", "全部 PASS (无 FAIL)", _flow_verify_checks),
        ],
    },
    "bench": {
        "title": "引擎基准 (API timings 口径)",
        "desc": "对已就绪引擎发标准请求, 从响应的 timings 取 pp/tg, 并落 metrics-log",
        "dry_default": True,       # 可能加载模型 → 默认只出计划
        "ledger": "metrics-log",
        "steps": [
            ("engine", "定位在服务的引擎", "三站之一有引擎端口", _flow_step_probe_engine),
            ("load", "确保目标就绪", "已有引擎, 或预估非 NO_FIT 且加载成功", _flow_step_ensure_loaded),
            ("bench", "标准请求取 timings", "HTTP 200 且响应含 timings", _flow_step_bench),
        ],
        "teardown": _flow_teardown_bench,
    },
    "swap": {
        "title": "换模型/后端 (按站)",
        "desc": "事前预估 → 卸载该站 → 加载新目标 → 就绪复核",
        "dry_default": True,
        "ledger": "metrics-log",
        "steps": [
            ("precheck", "事前预估", "verdict ∈ {FITS, TIGHT}", _flow_swap_precheck),
            ("apply", "按站加载 (含自动卸载/GTT 等待)", "cmd_load_on rc=0", _flow_swap_apply),
            ("ready", "就绪复核", "llama=READY 且有引擎端口", _flow_swap_ready),
        ],
    },
    "rotate": {
        "title": "凭据轮换 (下发 + 复核)",
        "desc": "巡检落点/引用/权限 → 明文门禁 → 下发正本 → 复核。只做运维侧, 不生成新密钥",
        "dry_default": True,
        "ledger": "metrics-log",
        "steps": [
            ("status", "凭据现状巡检", "三站 verdict=OK", _flow_rotate_status),
            ("scan", "明文门禁", "命中 0 处", _flow_rotate_scan),
            ("push", "下发正本", "cmd_secrets push rc=0", _flow_rotate_push),
        ],
    },
    "paths": {
        "title": "路径对比: 单机 vs 双机 (决策门)",
        "desc": "同一模型在两条路径上各做一次实测基准, 输出对照表与推荐 —— 供'该走哪条路径'决策",
        "dry_default": True,
        "continue_on_fail": True,   # 对比类: 某条路径不通本身就是结论, 不能 fail-fast
        "ledger": "metrics-log",
        "steps": [
            ("est", "单机事前预估", "verdict ∈ {FITS, TIGHT} 才值得实测", _flow_paths_single),
            ("single", "单机实测 (加载→基准→留存)",
             "HTTP 200 且含 timings", _flow_paths_run_single),
            ("rpc", "双机 RPC 实测 (RPC 编排→加载→基准)",
             "加载成功且含 timings (双机无单站口径的事前预估, 只认实测)", _flow_paths_run_rpc),
            ("report", "对照与推荐", "两条路径都给出结论 (可用/不可用 + 数据)", _flow_paths_report),
        ],
    },
}


def _flow_usage() -> str:
    lines = ["用法: cluster.py flow {list|<name>} [--plan|--go] [--no-ledger] [args...]", "",
             "  --plan       只打印步骤与判据, 不执行任何一步 (只读信息用各自的专用命令)",
             "  --go         执行会改站上状态的 flow; 也决定是否**真落账**",
             "  --no-ledger  跑了但不落账 (负向测试/试跑用, 避免污染台账)", "",
             "flow 内置表 (步骤 → 判据 → 台账落点):"]
    for name, f in FLOWS.items():
        d = "默认出计划(--go 执行)" if f["dry_default"] else "默认执行"
        lines.append(f"\n  {name:8s} {f['title']}  [{d}] → {f['ledger']}")
        lines.append(f"           {f['desc']}")
        for i, (sid, title, crit, _fn) in enumerate(f["steps"], 1):
            lines.append(f"           {i}. {title:16s} 判据: {crit}")
        if f.get("teardown"):
            lines.append("           ↳ 收尾: 本次若加载过则自动卸载")
    return "\n".join(lines)


def cmd_flow(argv) -> int:
    """cluster.py flow —— 声明式流程 (P2-1)。"""
    if not argv or argv[0] in ("-h", "--help", "list"):
        print(_flow_usage())
        return 0
    name = argv[0]
    f = FLOWS.get(name)
    if not f:
        print(f"未知 flow: {name}\n\n{_flow_usage()}")
        return 2
    rest = argv[1:]
    # 先剔掉带值的开关, 免得 `flow swap --backend vllm gpt-oss` 把 vllm 当成 alias
    positional, ctx = [], {"flow": name, "ledger": f["ledger"],
                           "go": ("--go" in rest), "plan_only": ("--plan" in rest),
                           "no_ledger": ("--no-ledger" in rest)}
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--backend" and i + 1 < len(rest):
            ctx["backend"] = rest[i + 1]
            i += 2
            continue
        if not a.startswith("--"):
            positional.append(a)
        i += 1
    if positional:
        ctx["alias"] = positional[0]
    if name == "bench":
        ctx.setdefault("alias", None)
    if name in ("swap", "paths"):
        if not ctx.get("alias"):
            print(f"{name} 需要目标: cluster.py flow {name} <alias前缀>"
                  + (" [--backend X]" if name == "swap" else "") + " [--go]")
            return 2
        ctx["station"] = resolve_host_alias(ctx["alias"])

    mode = "计划" if (ctx["plan_only"] or (f["dry_default"] and not ctx["go"])) else "执行"
    print(f"\n=== flow {name}: {f['title']} [{mode}] ===")
    print(f"  {f['desc']}")
    if ctx.get("alias"):
        print(f"  目标: {ctx['alias']}" + (f" @ {ctx['station']} 站" if ctx.get("station") else ""))
    print()

    n = len(f["steps"])
    failed_at, step_fails, guard_fail = None, [], False
    for i, (sid, title, crit, fn) in enumerate(f["steps"], 1):
        print(f"  [{i}/{n}] {title}")
        print(f"        判据: {crit}")
        if mode == "计划":
            print("        - 计划模式: 未执行")
            continue
        try:
            ok, note, detail = fn(ctx)
        except Exception as e:
            ok, note, detail = False, f"异常 {type(e).__name__}: {e}", []
        print(f"        {'✓' if ok else '✕'} {note}")
        for d in (detail or [])[:6]:
            print(f"          · {d}")
        if not ok:
            step_fails.append(title)
            if not f.get("continue_on_fail"):
                failed_at = title
                break
            # continue_on_fail: 中间步骤失败只算"部分完成"; **最后一步失败 = 整体失败**
            # (最后一步是"对照/报告", 它给不出结论就说明这个 flow 白跑了)
            guard_fail = (i == n)
    if not failed_at and step_fails and not f.get("continue_on_fail"):
        failed_at = step_fails[0]
    teardown = f.get("teardown")
    if teardown and mode == "执行":
        print("  收尾")
        try:
            ok, note, _d = teardown(ctx)
        except Exception as e:
            ok, note = False, f"异常 {type(e).__name__}: {e}"
        print(f"        {'✓' if ok else '✕'} {note}")

    # 落账行 (日期 / flow / 目标 / 判据(口径) / 结果 / 证据 三要素齐)
    t = ctx.get("timings") or {}
    crit = "API timings @ 内层端口 (pp/tg 由响应 timings 实测)"
    if name == "bench":
        crit = (f"API timings 口径 · max_tokens=128 · prompt 实测 {t.get('prompt_n', '?')} tok")
    elif name == "verify":
        crit = "健康引擎 9 项断言全 PASS"
    elif name == "rotate":
        crit = "凭据落点/引用/权限 OK + 明文 0 命中"
    elif name == "swap":
        crit = "预估 FITS/TIGHT + 就绪 READY"
    elif name == "paths":
        crit = "API timings 口径 · 单机 vs 双机各一次实测 (同请求体, max_tokens=128)"
    result = "PLAN" if mode == "计划" else ("FAIL" if (failed_at or guard_fail)
                                            else ("PARTIAL" if step_fails else "PASS"))
    target = ctx.get("alias") or ctx.get("station") or "-"
    if ctx.get("alias") and ctx.get("station"):
        target += f"@{ctx['station']}"
    if name == "bench" and t:
        ev = (f"pp {t.get('prompt_n')} tok {t.get('prompt_per_second', 0):.1f} t/s · "
              f"tg {t.get('predicted_n')} tok {t.get('predicted_per_second', 0):.1f} t/s")
    elif name == "verify":
        ev = f"断言失败 {len(ctx.get('verify_failed') or [])} 项"
    elif name == "rotate":
        ev = "verdicts " + ",".join(f"{k}={v}" for k, v in (ctx.get("rotate_verdicts") or {}).items())
    elif name == "paths":
        ev = " / ".join(f"{r['label']} tg={r.get('tg_tps') or '不可用'}" for r in (ctx.get("paths") or []))
    else:
        ev = ctx.get("estimate", {}).get("verdict", "-") if ctx.get("estimate") else "-"
    ctx["ledger_row"] = (f"| {time.strftime('%Y-%m-%d %H:%M')} | {name} | {target} | {crit} "
                         f"| {result} | {ev} |")
    # 只有真正跑过才落账 (计划模式只预览); --no-ledger 给"只跑不落账"留出口 ——
    # 负向测试/试跑不该污染台账 (2026-09-15 实测: 测试跑的 FAIL 行落进了 metrics-log)。
    if mode == "执行" and not ctx.get("no_ledger"):
        _ok, lmsg, _d = _flow_ledger_step(ctx)
        print(f"  落账\n        {lmsg}")
    elif ctx.get("no_ledger"):
        print(f"  落账\n        [--no-ledger] 已跳过 (仅本次不落)")
    else:
        print(f"  落账 (计划)\n        [dry-run] {ctx['ledger_row']}")

    print(f"\n  结论: flow {name} {result}"
          + (f" (中止于「{failed_at}」)" if failed_at else "")
          + (f" (部分完成: {len(step_fails)} 步未达标 —— 见上)" if (step_fails and not failed_at) else "")
          + "\n")
    # PARTIAL 仍是"跑完了、有结论", 不算失败; 只有 FAIL(含最后一步失败) 才返回 1
    return 1 if (failed_at or guard_fail) else 0


# ── P0: agent 任务进度/吞吐只读视图 (2026-09-15, 调研 spec/agent-observability/) ──
# **一个采集器都不新增**: 三个数据源全是 O-25 已建的 ——
#   ① 主控派发台账 ops/station-bin/agent-runs.log (ts,proj,model,sens,code,queue_s,run_s)
#   ② 主控 run 详情 <projRoot>/agent-out/<ts>/.agent-run.json (status/run_s/output_bps/slot/profile/accept)
#   ③ 站上运行中节拍 $HOME/agent-workspaces/<proj>/out/.progress (5s 一行 t=.. bytes=.. bytes_s=.., 终值 t=end)
#
# ⚠ 口径 (调研 §3 的关键结论, 别混):
#   · 本视图的"产出"列是 **agent 产出字节口径** (output_bytes / output_bps) —— **不是 token**,
#     与 reqlog 的"引擎耗时口径 t/s"、API timings 三者互不可比, 故分列显示、列头写明口径。
#   · 上游无头 run 不吐 usage (run.json 里 usage.total_tokens 实测恒 0) ⇒ **不做字节→token 换算**。
#   · ETA 需要"目标产出量", 而 max_output 只在 run 结束的 run.json 里 ⇒ 运行中**没有目标**,
#     一律打 `NA` —— 不打荒数字 (O-25 no-bench 纪律)。
# 字段命名对齐社区标准 (只为将来接 trace 后端不返工, 不引入依赖):
#   run ≈ OTel GenAI `invoke_agent` span · 状态 ≈ A2A TaskState (我们原本缺 `working`, 由 live 补上)
AGENT_LEDGER = Path(__file__).resolve().parent / "station-bin" / "agent-runs.log"
AGENT_CLI_PS1 = Path(__file__).resolve().parent / "station-bin" / "agent-cli.ps1"
AGENT_WS = "$HOME/agent-workspaces"
AGENT_BEAT_STALE_S = 60          # 节拍 5s 一次; 超 60s 未更新 ⇒ 疑似卡死 (O-25 的"黑盒"信号)
AGENT_STATUS_BY_CODE = {0: "completed", 6: "timeout", 24: "slot-rejected"}


def _dw(s) -> int:
    """终端显示宽度 —— CJK 占 2 格。不这样算, 中英混排的表头永远对不上 (实测)。"""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))


def _pad(s, w: int, right: bool = False) -> str:
    s = str(s)
    gap = " " * max(0, w - _dw(s))
    return gap + s if right else s + gap


def _human_age(sec) -> str:
    """秒 → 人读时长。freshness 列必须一眼看出"这是多久以前"。"""
    try:
        sec = float(sec)
    except (TypeError, ValueError):
        return "-"
    if sec < 90:
        return f"{sec:.0f}s"
    if sec < 5400:
        return f"{sec / 60:.1f}m"
    if sec < 172800:
        return f"{sec / 3600:.1f}h"
    return f"{sec / 86400:.1f}d"


def _agent_proj_roots() -> tuple:
    """解析 agent-cli.ps1 的 PROJECTS 表 → (proj→root, note)。

    **为什么不在这里再抄一份映射**: proj→root 的真值在 `agent-cli.ps1` 的 `$Script:PROJECTS`
    (paper=D:\\Paper / Cpp_Hub=F:\\Cpp_Hub / Auto_Prover=F:\\Auto_Prover)。抄一份就是第二个定义点,
    项目增删时必然漂移 (P1-6"取 conf 而非抄台账"同一条理由)。解析失败**显式降级**, 不猜。
    """
    roots, note = {}, ""
    try:
        text = AGENT_CLI_PS1.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as e:
        return {}, f"读不到 {AGENT_CLI_PS1.name} ({e.__class__.__name__})"
    m = re.search(r"\$Script:PROJECTS\s*=\s*@\{(.*?)\}", text, re.S)
    if not m:
        return {}, "未在 agent-cli.ps1 找到 $Script:PROJECTS (详情列将不可用)"
    for name, root in re.findall(r"(\w+)\s*=\s*'([^']+)'", m.group(1)):
        roots[name] = Path(root)
    if not roots:
        note = "$Script:PROJECTS 解析为空 (详情列将不可用)"
    return roots, note


def _agent_ledger_rows(limit: int) -> list:
    """读派发台账尾部 N 条。跳过标题行 (判据与 make-dashboard 一致: 必须 `^\\d{14,},`)。"""
    try:
        lines = AGENT_LEDGER.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return []
    rows = []
    for ln in lines:
        ln = ln.strip()
        if not re.match(r"^\d{14,},", ln):      # 台账首行是 "RPC_LEDGER_TEST 2026-09-06" 之类的标题
            continue
        f = ln.split(",")
        if len(f) < 7:
            continue
        ts, proj, model, sens, code, qs, rs = (x.strip() for x in f[:7])
        try:
            label = time.strftime("%m-%d %H:%M:%S",
                                  time.strptime(ts[:14], "%Y%m%d%H%M%S"))
        except Exception:
            label = ts[:14]
        try:
            code_i = int(code)
        except ValueError:
            code_i = None
        rows.append({"ts": ts, "label": label, "proj": proj, "model": model, "sens": sens,
                     "code": code_i, "queue_s": int(qs or 0), "run_s": int(rs or 0),
                     "status": AGENT_STATUS_BY_CODE.get(code_i, "failed" if code_i is not None else "?")})
    return rows[-limit:] if limit else rows


def _agent_detail(roots: dict, proj: str, ts: str) -> dict:
    """读该 run 的 .agent-run.json (终态快照)。缺文件返回 {} —— 老 run 无详情属正常。"""
    root = roots.get(proj)
    if not root:
        return {}
    p = root / "agent-out" / ts / ".agent-run.json"
    try:
        j = json.loads(p.read_text(encoding="utf-8-sig", errors="replace"))
    except Exception:
        return {}
    if not isinstance(j, dict):
        return {}
    return {"status": j.get("status"), "exit_code": j.get("exit_code"),
            "cli": j.get("cli"), "model": j.get("model"),
            "run_s": j.get("run_s"), "queue_s": j.get("queue_s"),
            "output_bytes": j.get("output_bytes"), "output_bps": j.get("output_bps"),
            "slot": j.get("slot"), "profile": j.get("profile"),
            "accept": (j.get("accept") or {}).get("passed"),
            "collect": j.get("collect"),
            "usage_total_tokens": (j.get("usage") or {}).get("total_tokens")}


def _agent_beat(st: str) -> list:
    """扫一站运行中节拍。**只读**: 遍历站上既有 .progress, 不写任何东西, 不装采集器。"""
    cmd = ("for d in " + AGENT_WS + "/*/out; do "
           "[ -f \"$d/.progress\" ] || continue; "
           "proj=$(basename \"$(dirname \"$d\")\"); "
           "last=$(grep '^t=' \"$d/.progress\" 2>/dev/null | tail -1); "
           "[ -z \"$last\" ] && continue; "
           "printf 'BEAT|%s|%s|%s\\n' \"$proj\" \"$last\" \"$(stat -c %Y \"$d/.progress\" 2>/dev/null)\"; "
           "done")
    ok, out = ssh_run(st, cmd, timeout=45)
    if not ok:
        return [{"station": st, "error": (out or "").strip().splitlines()[0][:80] if out else "ssh 失败"}]
    beats, now = [], int(time.time())
    for ln in out.splitlines():
        if not ln.startswith("BEAT|"):
            continue
        parts = ln.split("|", 3)
        if len(parts) < 4:
            continue
        _, proj, last, mtime = parts
        m = re.search(r"^t=(\S+)\s+bytes=(\d+)\s+bytes_s=(\d+)", last.strip())
        if not m:
            continue
        t_val, by, bps = m.group(1), int(m.group(2)), int(m.group(3))
        try:
            age = now - int(mtime)
        except ValueError:
            age = None
        beats.append({"station": st, "proj": proj, "t": t_val, "bytes": by, "bytes_s": bps,
                      "age_s": age, "running": (t_val != "end"),
                      "stale": bool(age is not None and age > AGENT_BEAT_STALE_S),
                      "beat_at": (time.strftime("%m-%d %H:%M:%S", time.localtime(int(mtime)))
                                  if age is not None else "?")})
    return beats


def agent_live(stations=("A", "B", "C")) -> list:
    """三站运行中节拍 (并行)。CLI `agent live` 与 web `/api/agent` **共用这一份**。"""
    res, threads = {}, []
    for st in stations:
        t = threading.Thread(target=lambda s=st: res.__setitem__(s, _agent_beat(s)))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    return [b for st in stations for b in res.get(st, [])]


def agent_runs(limit: int = 20) -> tuple:
    """台账尾 N 条 + join run.json 详情 + 状态归并 → (rows, note)。

    CLI `agent runs` 与 web `/api/agent` **共用这一份** —— join 逻辑只写一遍,
    否则两处迟早漂移 (P2-1 已立过的同一条理由)。
    """
    roots, note = _agent_proj_roots()
    rows = _agent_ledger_rows(limit)
    for r in rows:
        r["detail"] = _agent_detail(roots, r["proj"], r["ts"])
        if r["detail"].get("status"):
            r["status"] = r["detail"]["status"]          # run.json 的 status 优先于 code 映射
    # 台账**不是严格有序的** (实测 09-12 有一对 17:18:20 / 17:18:18 反序, 并发派发所致) ⇒ 按 ts 排一次
    rows.sort(key=lambda r: r["ts"])
    return rows, note


def agent_ledger_freshness(rows) -> dict:
    """台账新鲜度: 事件级 (run 结束才写一行) ⇒ 用**最新一条 ts** 衡量。

    刻意不用"最后一行"(台账实测有并发反序) 也不用文件 mtime (collect 崩了也可能已写过行)。
    """
    if not rows:
        return {}
    newest = max(rows, key=lambda r: r["ts"])
    try:
        t = time.mktime(time.strptime(newest["ts"][:14], "%Y%m%d%H%M%S"))
    except Exception:
        return {"label": newest.get("label"), "age_s": None}
    return {"label": newest.get("label"), "age_s": int(time.time() - t)}


def cmd_agent(argv) -> int:
    """cluster.py agent {runs|live|tail} [--limit N] [--station A|B|C] [--json]

    P0 只读视图: `runs`=派发台账尾 N 条(join run.json 详情) / `live`=三站运行中节拍 /
    `tail`=台账原始行。**只读, 无副作用**; 口径与判据见 spec/agent-observability/。
    """
    act = (argv[0] if argv else "runs").lower()
    if act not in ("runs", "live", "tail"):
        print("用法: cluster.py agent {runs|live|tail} [--limit N] [--station A|B|C] [--json]")
        return 1
    limit, only, as_json = 20, None, ("--json" in argv)
    i = 1
    while i < len(argv):
        if argv[i] == "--limit" and i + 1 < len(argv):
            try:
                limit = max(1, int(argv[i + 1]))
            except ValueError:
                print("--limit 需要整数")
                return 1
            i += 2
            continue
        if argv[i] == "--station" and i + 1 < len(argv):
            only = argv[i + 1].upper()
            i += 2
            continue
        i += 1
    if only and only not in STATIONS:
        print(f"未知站 '{only}' (可选: {', '.join(STATIONS)})")
        return 1
    stations = [only] if only else ["A", "B", "C"]

    if act == "live":
        beats = agent_live(stations)
        if as_json:
            print(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "beats": beats},
                             ensure_ascii=False))
            return 0
        print("\n=== agent 运行中 (站上 $HOME/agent-workspaces/*/out/.progress) — 只读 ===")
        print("  口径: 产出为 **字节口径** (bytes / bytes_s), 不是 token; ETA 需目标量, 运行中不可得 ⇒ NA\n")
        running = [b for b in beats if b.get("running")]
        cols = [(3, "站", 0), (10, "proj", 0), (11, "状态", 0), (6, "已跑s", 1), (10, "已产出", 1),
                (7, "B/s", 1), (11, "距上次节拍", 1), (24, "ETA", 0), (14, "节拍时刻", 0)]
        print("  " + " ".join(_pad(t, w, bool(r)) for w, t, r in cols))
        print("  " + "-" * (sum(w for w, _, _ in cols) + len(cols) - 1))
        for b in beats:
            if b.get("error"):
                print("  " + _pad(b["station"], 3) + " " + _pad("不可达", 10) + " " + b["error"])
                continue
            st_txt = "working" if b["running"] else "finished"
            if b.get("stale") and b["running"]:
                st_txt += " ⚠陈旧"
            age = "-" if b["age_s"] is None else _human_age(b["age_s"])
            cells = [_pad(b["station"], 3), _pad(b["proj"], 10), _pad(st_txt, 11),
                     _pad(b["t"] if b["running"] else "-", 6, True), _pad(b["bytes"], 10, True),
                     _pad(b["bytes_s"], 7, True), _pad(age, 11, True),
                     _pad("NA (无 max_output 目标)", 24), _pad(b["beat_at"], 14)]
            print("  " + " ".join(cells))
        if not beats:
            print("  (三站均无 .progress —— 没有任务在跑; 注意 finished 行是**上一次** run 的终值残留)")
        print(f"\n  working={len(running)} · 判据: 末行 t=end ⇒ finished (不是 running); "
              f"节拍 >{AGENT_BEAT_STALE_S}s 未更新 ⇒ 疑似卡死")
        return 0

    rows, note = agent_runs(limit)
    if act == "tail":
        for r in rows:
            print(",".join(str(r[k]) for k in ("ts", "proj", "model", "sens", "code",
                                               "queue_s", "run_s")))
        return 0

    if as_json:
        print(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "note": note,
                          "ledger": str(AGENT_LEDGER), "rows": rows,
                          "ledger_freshness": agent_ledger_freshness(rows)}, ensure_ascii=False))
        return 0

    print("\n=== agent 任务台账 (终态) — 只读 ===")
    print(f"  台账: {AGENT_LEDGER}")
    roots, _ = _agent_proj_roots()
    print("  详情: <projRoot>/agent-out/<ts>/.agent-run.json"
          + (f"   ⚠ {note}" if note else f"   (projRoot 取自 agent-cli.ps1: "
                                        f"{', '.join(f'{k}={v}' for k, v in roots.items())})"))
    print("  ⚠ 口径: 产出列是 **字节口径** (output_bytes / B/s), 不是 token —— "
          "与 reqlog 的引擎耗时口径 t/s 互不可比\n")
    cols = [(15, "时间", 0), (10, "proj", 0), (26, "模型", 0), (10, "sens", 0), (4, "exit", 1),
            (13, "状态", 0), (6, "run_s", 1), (7, "queue_s", 1), (9, "产出字节", 1),
            (6, "B/s", 1), (12, "slot", 0), (34, "profile", 0)]
    print("  " + " ".join(_pad(t, w, bool(r)) for w, t, r in cols))
    print("  " + "-" * (sum(w for w, _, _ in cols) + len(cols) - 1))
    for r in rows:
        d = r["detail"]

        def g(k, dflt="-"):
            v = d.get(k)
            return dflt if v is None else v
        slot = "-"
        if d.get("slot"):
            s = d["slot"]
            slot = f"{s.get('action', '?')}({s.get('busy', '?')}/{s.get('total', '?')})"
        prof = "-"
        if d.get("profile"):
            p = d["profile"]
            prof = f"{p.get('name', '?')} ctx={p.get('context', '?')} max={p.get('max_output', '?')}"
            if d.get("accept") is False:
                prof += "  accept=Fail"
        cells = [_pad(r["label"], 15), _pad(r["proj"], 10), _pad(r["model"], 26),
                 _pad(r["sens"], 10), _pad(r["code"], 4, True), _pad(r["status"], 13),
                 _pad(g("run_s", r["run_s"]), 6, True), _pad(g("queue_s", r["queue_s"]), 7, True),
                 _pad(g("output_bytes"), 9, True), _pad(g("output_bps"), 6, True),
                 _pad(slot, 12), _pad(prof, 34)]
        print("  " + " ".join(cells))
    if not rows:
        print("  (台账为空或文件不可读)")
    fr = agent_ledger_freshness(rows)
    if fr:
        hint = "  ← 该台账已久未更新" if (fr.get("age_s") or 0) > 172800 else ""
        print(f"\n  共 {len(rows)} 条 (取尾部) · 最新一条 {fr.get('label')} "
              f"(距今 {_human_age(fr.get('age_s'))}){hint}")
    print("  详情缺失(-)属正常: 早于 O-25 的 run 未落 .agent-run.json; "
          "usage.total_tokens 实测恒 0 (无头 run 不吐 usage) ⇒ 本视图不给 token 速率")
    return 0


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
        return (f"  {st:<3} {'未部署':<6} {'-':<8} {'-':<11} {'-':<16} {'-':<14} "
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
    return (f"  {st:<3} {on:<6} {str(s.get('ttl_s', TTL_DEFAULT_S)) + 's':<8} {timer:<11} "
            f"{eng:<16} {idle:<14} {act}")


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
        hdr = (f"  {'站':<3} {'开关':<6} {'阈值':<8} {'定时器':<11} {'引擎':<16} "
               f"{'空闲/阈值':<14} {'最近动作'}")
        print(hdr)
        print("  " + "-" * (len(hdr) - 2))
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
    if sub == "flow":
        return cmd_flow(args[1:])
    if sub == "reqlog":
        return cmd_reqlog(args[1:])
    if sub == "ttl":
        return cmd_ttl(args[1:])
    if sub == "agent":
        return cmd_agent(args[1:])
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
