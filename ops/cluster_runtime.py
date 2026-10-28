#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cluster_runtime — `cluster.py` 的按域拆分模块（review-p2-cluster 阶段）。

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
    HTML_OUT, SSH_TIMEOUT, PANELS, SERVICE_USER, REPO_ROOT, STATION_RESERVED_GIB,
)


# ── SSH 层 + 探测层 (已抽至 cluster_ssh.py, 阶段 1b 拆分) ──────────────
# 显式重导出 ⇒ 站内多处调用点 (`cli = _connect(...)` / `ssh_stream(...)`) 与外部
# (cluster_web.py 的 cluster.ssh_run) 均不变。实现改 ops/cluster_ssh.py。
from cluster_ssh import (  # noqa: E402
    _connect, ssh_run, ssh_stream, probe_station, resolve_host,
)


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
    """解析站上 conf (/etc/llama-instances/<alias>.env) 为 dict。

    P1 #4: 委托 ops/conf_parse（与站上 conf-lib.sh 同一转义规则）。
    函数内导入 ⇒ 不成为 cluster_*.py 依赖图的模块级边。
    """
    from conf_parse import parse_conf
    return parse_conf(text)


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


def _cmd_load_c(alias: str, backend: str = None, engine: str = None, keep: bool = False) -> int:
    """C 站 load：与 A/B 同路径 (infer-load 已补装, 含 pkill 兜底管理手动引擎)。

    ⚠ 2026-10-12 修 Bug A：原签名只收 (alias, backend) ⇒ **`--engine` 在 C 站被静默丢弃**
    (C 站分支在 cmd_load 里**先于**通用路径 return)。表现：`load <C别名> --engine <变体>`
    仍用 conf 旧引擎，日志**无**「引擎变体已落 conf」行 —— 对 GLM（C 站 + `--engine glm5next-*`）
    是潜在同族风险面。改走 `_build_infer_load_cmd` 统一拼装（与 A/B 同一构造器，避免再分叉）。"""
    print(f"[cluster] C 站 (seaviv) 加载 {alias} ...")
    # ★ 2026-10-22 实测：C 站分支在 cmd_load 里**先于**通用路径 return ⇒ 必须在此单独回收容器。
    #   漏掉它的表现（C 站连续复现）：halogen 容器继续占 8080/GTT ⇒ 新 studio 落到 **8081**，
    #   两个引擎同抢 ~90 GB ⇒ 容器随后 OOM `Exited (1)`。
    _rc_c = reclaim_and_unload("C", alias if keep else None)
    if not _rc_c["ok"]:
        print(f"[cluster] C 站回收/卸载失败 ⇒ 中止: {_rc_c['steps']}")
        return 1
    cmd = _build_infer_load_cmd(alias, backend, engine)
    rc = ssh_stream("C", cmd)
    if rc != 0:
        print(f"[cluster] C 站加载失败 (rc={rc})。")
        return 1
    ok, out = ssh_run("C", "curl -s --max-time 8 http://127.0.0.1:8080/health")
    if ok and out.strip():
        print(f"[cluster] C 站引擎 :8080 响应: {out.strip()[:60]}")
    print(f"[cluster] C 站引擎 READY ✓ (站内 infer-load 判定, rc=0)")
    return 0


_ENGINE_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._/-")


def _engine_ok(engine: str) -> bool:
    """引擎变体白名单校验 (仅 字母/数字/./_/-)。
    为什么必须校验: engine 来自命令行, 会被拼进**远端** ssh 命令 ⇒ 不做校验等于开放注入面。
    (--backend 无此问题, 因为它先过 BACKENDS 枚举白名单。)"""
    return bool(engine) and all(c in _ENGINE_CHARS for c in engine)


def _pp_listen_ip(coord: str, worker: str) -> str:
    """coordinator 在 coord-worker 直连段上的 IP；找不到 / 多义 / 非法 ⇒ ""（不猜）。

    只解析 inventory/net.yaml 的 `segments:` 段（ends 为 inline map）。
    找不到返回空，由 _load_ds4_pp 在起 worker **之前**中止 —— 绝不退回 0.0.0.0。
    """
    path = Path(__file__).resolve().parent.parent / "inventory" / "net.yaml"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    in_seg, seg, hits = False, {}, []

    def close_seg():
        if coord in seg and worker in seg and coord != worker:
            hits.append(seg[coord])

    for line in lines:
        s = line.strip()
        if s.startswith("segments:"):
            in_seg = True
            continue
        if in_seg and s.startswith("routes:"):
            break
        if not in_seg:
            continue
        if s.startswith("- name:"):
            close_seg()
            seg = {}
            continue
        m = re.search(r"station:\s*([ABC])\b.*?\bip:\s*([0-9.]+)", s)
        if m:
            try:
                ipaddress.ip_address(m.group(2))
            except ValueError:
                continue
            seg[m.group(1)] = m.group(2)
    close_seg()
    return hits[0] if len(hits) == 1 else ""


def _build_infer_load_cmd(matched: str, backend: str, engine: str = None,
                          rpc_target: str = None, pp_listen: str = None) -> str:
    """拼装远端 infer-load 命令。backend 来自白名单校验(枚举), engine 来自 _engine_ok(), 均无注入风险。
    engine(引擎变体) 见 infer-load 的 --engine 说明: 名 -> /opt/llama.cpp-<名>/, 或绝对路径。
    rpc_target: 仅 RPC 类使用；worker 站 letter 经 RPC_WORKER_IPS 映射后传入（已在调用方校验）。
    pp_listen: 仅 ds4 coordinator 使用；由 _pp_listen_ip 从直连段取值并在此二次校验。"""
    cmd = f"infer-load '{matched}'" + (f" --backend {backend}" if backend else "")
    if engine:
        cmd += f" --engine '{engine}'"
    if rpc_target:
        cmd += f" --rpc-target '{rpc_target}'"
    if pp_listen:
        try:
            ipaddress.ip_address(pp_listen)
        except ValueError as e:
            raise ValueError(f"非法 pp_listen: {pp_listen!r}") from e
        cmd += f" --pp-listen '{pp_listen}'"
    return cmd


def _conf_rpc_target(station: str, alias: str) -> str:
    """读 head 站实例 conf 的 RPC_TARGET，**仅供预启动选择 worker**（2026-10-22）。

    为什么需要: `_load_rpc` 在 infer-load 之前先 `rpc-nodes --start` 做前置探活。原先不带
    过滤 ⇒ **未使用的节点也会被起**（实测默认单 worker A 时 C 仍 active），与"1 head + 1 worker"
    的固化语义不符。无 `--worker` 时应以 conf 的 RPC_TARGET 为准。

    只认**单个 ip:port**；`auto` / 空 / 多节点列表（含空格或逗号）⇒ 返回空 = 起全部声明节点
    （保留旧的多 worker 语义，不在这里重新解释 auto）。读失败同样返回空，不阻断加载 ——
    真正的目标校验仍由 infer-load 与存活探针完成。
    """
    ok, out = ssh_run(station, f"sed -n 's/^RPC_TARGET=//p' /etc/llama-instances/{alias}.env | tail -1")
    t = (out or "").strip().strip('"')
    if not ok or not t or t == "auto" or " " in t or "," in t:
        return ""
    return t


# ── 容器化模型 (halogen) 编排 ─────────────────────────────
def _container_cleanup_cmd() -> str:
    """站内**全部**已登记容器的一次性回收命令 (幂等)。供 unload 与启动前互斥共用。

    ★ 2026-10-22 C 站实测：`docker rm -f` 返回 0 后，容器会**立刻**从 `docker ps -a` 消失，
    但 docker-proxy/网络命名空间仍占着 8080 数分钟（C 站一次 ~4m18s）。只发 rm 不等 ⇒
    随后 studio 端口检测看到 8080 仍被占 ⇒ 自动落到 **8081**（客户端零迁移前提被破坏）。
    ⇒ 等待信号 = **8080 真的没人监听**（`ss -ltn`）；且只在**确实有容器**时才等
    （★ C 站实测 `docker rm -f` 对**不存在的名字**也返回 0 ⇒ 必须先用 `docker container inspect`
    探存在；没有容器就直接跳过 —— 避免与 studio 自己占用的 8080 互锁，也避免假 `PORT8080_STILL_BUSY`）。
    """
    names = sorted({s["name"] for s in CONTAINER_MODELS.values()})
    if not names:
        return "true"
    parts = []
    for n in names:
        # `docker rm -f` 返回 0 ≠ 端口已释放：容器会立刻从 `docker ps -a` 消失，但
        # docker-proxy/网络命名空间的清理可能还要数分钟（C 站实测 ~4m18s）。唯一可靠信号
        # 是 8080 真的没人监听。★ 但 `docker rm -f` 对**不存在的名字**也返回 0（C 站实测）
        # ⇒ 先 `docker container inspect` 探存在；仅当容器确实存在时才等，避免假阳性。
        parts.append(
            f"if docker container inspect {n} >/dev/null 2>&1; then "
            f"docker rm -f {n} >/dev/null 2>&1; "
            f"for _ in $(seq 1 240); do ss -ltn 2>/dev/null | grep -q ':8080 ' || break; sleep 2; done; "
            f"ss -ltn 2>/dev/null | grep -q ':8080 ' && echo 'PORT8080_STILL_BUSY'; fi")
    return "; ".join(parts)


def _reclaim_containers(station: str, alias: str = None) -> tuple:
    """回收站上已登记的容器，返回 `(ok, detail)`。**必须先于 `infer-unload`** —— 反之
    infer-unload 的 wait_gtt 会因容器仍持 ~90 GB GTT 每站白等满 180 s (90×2s) 才 WARN 退出。

    ★ timeout=540（2026-10-22 C 站实测）：`docker rm -f` 后 8080 的真实释放可能达 ~4m18s；
    命令内部轮询上限 480 s，这里再留余量。

    ★ 2026-10-26 缺口 3：旧版返回裸 bool 且只 `print` 端口未释放 ⇒ 调用方**无法区分**
    "删干净了" / "端口还占着" / "SSH 都连不上"，于是静默继续加载。现在三者都用
    `(ok, detail)` 显式表达，detail 供上层原样打印（不吞）。

    ★★ O-179（2026-10-28）：`alias` 非 None 且**不是**容器模型 ⇒ **跳过**（`skipped: keep`）。
    这是 `--keep`（同站叠加）的核心语义：为了装 B 模型去 `docker rm -f` A 模型的容器，
    等于换了名字继续全站清空。
    """
    if alias is not None and alias not in CONTAINER_MODELS:
        return True, "skipped: keep (非容器别名，不动站上容器)"
    ok, out = ssh_run(station, _container_cleanup_cmd(), timeout=540)
    if not ok:
        return False, f"ssh:{(out or '').strip()[:160]}"
    if "PORT8080_STILL_BUSY" in (out or ""):
        print(f"[cluster] {station} 站容器已删, 但 8080 在 480s 内未释放 —— 先排查占用者再加载"
              f" (studio 可能落到 8081)")
        return False, "port8080-still-busy"
    return True, ""


def reclaim_and_unload(station: str, alias: str = None) -> dict:
    """回收容器 + 卸载引擎，返回结构化结果（**不抛异常**）。

    steps 恒为两项，名称固定 `containers` / `infer-unload`：
      {"name": "containers", "ok": bool, "detail": str}
      {"name": "infer-unload", "ok": bool, "rc": int|None, "detail": str}

    ★ 容器步失败 ⇒ **跳过** infer-unload：ok=False 只有两种来源——SSH 已断（再发必然
    同样失败）或端口未释放（容器已删，`infer-unload` 无进程可杀）。两者都无收益，
    跳过并记 `skipped: containers failed`，不做无意义写动作。

    ★★ O-179（2026-10-28）：`alias` 非 None ⇒ **只卸这个别名**（`infer-unload <alias>`，
    只停该别名的 `llama-server@` 与各站 `rpc-server@`，不 pkill）。`alias=None` 逐字保留
    旧语义（全站全停）—— 默认路径的兼容性就靠这条。
    """
    ok_c, detail_c = _reclaim_containers(station, alias)
    steps = [{"name": "containers", "ok": ok_c, "detail": detail_c}]
    if not ok_c:
        steps.append({"name": "infer-unload", "ok": False, "rc": None,
                      "detail": "skipped: containers failed"})
        return {"station": station, "ok": False, "steps": steps}

    rc, ok_u, detail_u = None, False, ""
    cmd = "infer-unload" if alias is None else f"infer-unload {sh_single_quote(alias)}"
    try:
        rc = ssh_stream(station, cmd)
        ok_u = rc == 0
        detail_u = "" if ok_u else f"rc={rc}"
    except Exception as e:          # 连接级异常（超时/认证/端口不可达）
        detail_u = f"{type(e).__name__}: {e}"
    steps.append({"name": "infer-unload", "ok": ok_u, "rc": rc, "detail": detail_u})
    return {"station": station, "ok": ok_c and ok_u, "steps": steps}


def sh_single_quote(p: str) -> str:
    """POSIX 单引号转义：把任意路径变成单个 shell 词（防空格/引号被循环拆词）。"""
    return "'" + str(p).replace("'", "'\\''") + "'"


def _host_path_for(spec: dict, inner: str) -> str:
    """容器内路径 → 宿主路径（按 volume 的 inner 最长前缀匹配）。无法映射 ⇒ ""。

    ★ 路径单一真值：只读 `volume`，配方里不另写 host 路径（DESIGN §8 不变式 6）。
    """
    best_host, best_cont = "", ""
    for v in (spec.get("volume") or []):
        parts = str(v).split(":")
        if len(parts) < 2:
            continue
        host, cont = parts[0], parts[1]
        if not host or not cont:
            continue
        c = cont.rstrip("/") or "/"
        if inner == c or inner.startswith(c + "/") or c == "/":
            if len(c) > len(best_cont):
                best_host, best_cont = host.rstrip("/") or "/", c
    if not best_cont:
        return ""
    if best_cont == "/":                 # 根映射：容器路径即宿主相对路径（不能丢前导 /）
        return (best_host + inner) if best_host != "/" else inner
    rest = "" if inner == best_cont else inner[len(best_cont):]
    return (best_host + rest) if best_host != "/" else rest


def classify_container_assets(spec: dict, observed: dict) -> list:
    """纯函数：配方 + 观测 → problems（空 = 通过）。

    observed 形状: {"image": {"present": bool},
                    "assets": {inner_path: {"kind": "file"|"dir"|"missing"|"unreadable",
                                            "size": int, "entries": int}}}
    """
    problems = []
    assets = spec.get("assets") or []
    for a in assets:
        p = a.get("path")
        if not p or not _host_path_for(spec, p):
            problems.append(f"recipe-unmapped:{p}")
    ckpt = spec.get("checkpoint")
    if ckpt and assets and assets[0].get("path") != ckpt:
        problems.append("recipe-checkpoint-mismatch")

    if not ((observed or {}).get("image") or {}).get("present"):
        problems.append("image-missing")

    obs = (observed or {}).get("assets") or {}
    for a in assets:
        p = a.get("path")
        o = obs.get(p) or {"kind": "missing"}
        kind = o.get("kind")
        if kind == "missing" or kind == "unreadable":
            problems.append(f"asset-{kind}:{p}")
            continue
        if a.get("kind") == "file":
            if kind != "file":
                problems.append(f"asset-not-file:{p}")
            elif int(o.get("size") or 0) < int(a.get("min_bytes") or 0):
                problems.append(f"asset-too-small:{p}")
        elif a.get("kind") == "dir":
            if kind != "dir":
                problems.append(f"asset-not-dir:{p}")
            elif int(o.get("entries") or 0) < int(a.get("min_entries") or 1):
                problems.append(f"asset-empty-dir:{p}")
    return problems


def preflight_container(alias: str, station: str) -> dict:
    """只读预检：镜像存在性 + 资产就位。返回 {"ok", "problems", "image_missing"}。

    ★ 零写动作：不 `docker rm/run`、不 `infer-unload`、不写站上任何文件。
      校验必须先于破坏（Terraform validate-before-destroy，DESIGN §8 不变式 3/5）。
    """
    spec = CONTAINER_MODELS.get(alias) or {}
    image = spec.get("image", "")
    problems = []

    ok_i, out_i = ssh_run(station, f"docker image inspect {image} --format '{{{{.Id}}}}'",
                          strict=True)
    # ssh_run(strict) 非零码 ⇒ "(rc=N) body"（站可达、镜像不在）；
    # 连接失败 ⇒ "TypeName: msg"（站不可达）。两者必须区分，否则误报成"资产缺失"。
    if not ok_i and not str(out_i).startswith("(rc="):
        problems.append(f"ssh-failed:{(out_i or '').strip()[:120]}")
        return {"ok": False, "problems": problems, "image_missing": False}
    image_present = ok_i
    if not image_present:
        problems.append("image-missing")

    observed = {"image": {"present": image_present}, "assets": {}}
    stats = []
    for a in (spec.get("assets") or []):
        hp = _host_path_for(spec, a.get("path", ""))
        if not hp:
            continue
        stats.append(hp)
    if stats:
        q = " ".join(sh_single_quote(p) for p in stats)
        cmd = (f"for p in {q}; do "
               f"if [ -f \"$p\" ]; then "
               f"s=$(stat -c %s \"$p\" 2>/dev/null) && echo \"$p|file|$s\" "
               f"|| echo \"$p|unreadable|0\"; "
               f"elif [ -d \"$p\" ]; then "
               f"if [ -r \"$p\" ] && [ -x \"$p\" ]; then "
               f"echo \"$p|dir|$(ls -A \"$p\" 2>/dev/null | wc -l | tr -d ' ')\"; "
               f"else echo \"$p|unreadable|0\"; fi; "
               f"else echo \"$p|missing|0\"; fi; done")
        ok_s, out_s = ssh_run(station, cmd, timeout=30)
        if not ok_s:
            problems.append(f"ssh-failed:{(out_s or '').strip()[:120]}")
            return {"ok": False, "problems": problems, "image_missing": False}
        for line in (out_s or "").splitlines():
            parts = line.split("|")
            if len(parts) != 3:
                continue
            host_path, kind, num = parts
            # 回填容器内路径（observed 的键必须是配方里的 inner path）
            inner = next((a["path"] for a in (spec.get("assets") or [])
                          if _host_path_for(spec, a["path"]) == host_path), host_path)
            observed["assets"][inner] = {
                "kind": kind,
                "size": int(num) if num.isdigit() else 0,
                "entries": int(num) if num.isdigit() else 0,
            }

    problems.extend(classify_container_assets(spec, observed))
    return {"ok": not problems, "problems": problems, "image_missing": not image_present}


def _load_container_model(alias: str, station: str, keep: bool = False) -> int:
    """容器化模型的加载编排 (2026-10-21, ADR-0014 D7 落地)。

    与 `_load_rpc` / `_load_ds4_pp` 同构的"别名 -> 特殊编排"分支, 但**不经 infer-load**:
    命令由既有 `containers_plan("up", ...)` 生成 (计划与执行同源, ADR-0012 D2),
    配方来自 `CONTAINER_MODELS` (单一真值在 cluster_const.py)。

    四步:
      [1/4] 回收 —— `docker rm -f` **先于** `infer-unload` (理由见 _reclaim_containers)
      [2/4] 镜像存在性 —— 缺失则**后台拉取并中止**: 4.56 GB 拉取远超 ssh exec 上界
            (与 containers pull --detach 同一实测结论), 阻塞拉取必 TimeoutError
      [3/4] `docker run -d` (镜像已在, 秒级返回)
      [4/4] 轮询 `/health` 至 `status: ok` (冷启: GGUF repack 实测 1–2 min), 打印身份 +
            检查启动日志无 `LOWERING THE POOL TO N` (池被自动下调 = 内存余量不足, 须人读)
    """
    spec = CONTAINER_MODELS[alias]
    name, image = spec["name"], spec["image"]
    host = STATIONS[station]["host"]
    timeout = int(spec.get("ready_timeout", 300))

    print(f"[cluster] 容器化模型: {alias} -> {station} 站 ({host}) · 引擎 {spec.get('backend')} · 镜像 {image}")

    # [0/4] 只读预检 —— 必须在任何回收之前（validate before destroy，DESIGN §8 不变式 3）
    pre = preflight_container(alias, station)
    if not pre["ok"]:
        print(f"[cluster] PREFLIGHT {alias}@{station} ok=False :: " + "; ".join(pre["problems"]))
        if pre["image_missing"]:
            pull_cmd = containers_plan("pull", station=station, image=image,
                                       detach=True, log="/tmp/cluster-docker-pull.log")[0]
            ok2, out2 = ssh_run(station, pull_cmd, timeout=30)
            print(f"[cluster] 镜像未落地 ⇒ {'已后台拉取' if ok2 else '拉取下发失败: ' + out2}")
            print(f"[cluster]   进度: ssh {station} 'tail -f /tmp/cluster-docker-pull.log'; "
                  f"完成后重跑本命令。")
        print("[cluster] 未触碰旧服务 ⇒ 修正资产后重跑。")
        return 1
    print(f"[cluster] PREFLIGHT {alias}@{station} ok=True")

    # [1/4] 回收 + 卸载 (O-179: 默认互斥=全站清空; --keep 时只替换同名 alias)
    print(f"[cluster] [1/4] 回收站内既有引擎/容器 ...")
    _r1 = reclaim_and_unload(station, alias if keep else None)
    if not _r1["ok"]:
        print(f"[cluster] [1/4] 回收/卸载失败 ⇒ 中止: {_r1['steps']}")
        return 1

    # [2/4] 镜像已在预检中确认 ⇒ 只回显（预检后到这里的窗口极小，不重复 inspect）
    print(f"[cluster] [2/4] 镜像已在站上 ✓")

    # [3/4] 起容器 —— 与 `containers up --go` 同一生成器
    run_cmd = containers_plan(
        "up", station=station, image=image, name=name,
        publish=spec.get("publish", ()), group_add=spec.get("group_add", ()),
        device=spec.get("device", ()), volume=spec.get("volume", ()),
        env=spec.get("env", ()), ipc=spec.get("ipc"), ulimit=spec.get("ulimit", ()),
    )[0]
    print(f"[cluster] [3/4] docker run -d --name {name} ...")
    ok, out = ssh_run(station, run_cmd, timeout=120, strict=True)
    if not ok:
        print(f"[cluster] 容器启动失败: {out}")
        return 1

    # [4/4] 就绪轮询 + 身份 + 池下调检查
    print(f"[cluster] [4/4] 等待引擎就绪 (≤{timeout}s; 冷启需 GGUF repack) ...")
    deadline = time.time() + timeout
    health = None
    while time.time() < deadline:
        ok, out = ssh_run(station, "curl -s --max-time 5 http://127.0.0.1:8080/health")
        if ok and out.strip():
            try:
                health = json.loads(out)
            except ValueError:
                health = None
            if isinstance(health, dict) and health.get("status") == "ok":
                break
        # 提前失败: 容器已退出就不必空等 (轮询期间 container 可能因取件/内存失败而 exit)
        ok_r, running = ssh_run(station, f"docker inspect -f '{{{{.State.Running}}}}' {name}")
        if ok_r and running.strip() == "false":
            ok_l, logs = ssh_run(station, f"docker logs --tail 30 {name} 2>&1")
            print(f"[cluster] 容器已退出, 最后 30 行日志:\n{logs if ok_l else '(取日志失败)'}")
            return 1
        time.sleep(5)
    if not (isinstance(health, dict) and health.get("status") == "ok"):
        ok_l, logs = ssh_run(station, f"docker logs --tail 30 {name} 2>&1")
        print(f"[cluster] 就绪超时 ({timeout}s)。最后 30 行日志:\n{logs if ok_l else '(取日志失败)'}")
        return 1

    ver = health.get("version") if isinstance(health.get("version"), dict) else {}
    ident = [("model", health.get("model") or health.get("model_id")),
             ("version.api", ver.get("api") or health.get("api")),
             ("context", health.get("context")),
             ("kv_pool_positions", health.get("kv_pool_positions"))]
    print(f"[cluster] {station} 站 halogen 就绪: " +
          " · ".join(f"{k}={v}" for k, v in ident if v is not None))
    if health.get("context") is None:   # 0.18.11 的字段名未在本仓实测过 ⇒ 原文兜底, 不猜
        print(f"[cluster] /health 原文: {json.dumps(health, ensure_ascii=False)[:400]}")
    ok_l, lowered = ssh_run(station, f"docker logs {name} 2>&1 | grep -i 'LOWERING THE POOL' | tail -3")
    if ok_l and lowered.strip():
        print(f"[cluster] ⚠ 池被自动下调 (内存余量不足, 见 ADR-0014 A3):\n{lowered.strip()}")
    print(f"[cluster] READY ✓ ({alias} 由 halogen 容器服务; 回退用 load {alias} --backend unsloth)")
    return 0


# ── O-178 × O-175：反向冲突预检（2026-10-28）──────────────────────────
# 为什么必须在 load **之前**判：`reclaim_and_unload` ⇒ `infer-unload` 会停
# `rpc-server@*`（本站 + 按 nodes.env 停远端），而 ggml-rpc 对「对端消失」的语义是
# **GGML_ABORT**（status=6 / core-dump），不是返回错误 ⇒ 在**正给别的模型当 worker**
# 的站上加载，崩的是**另一台机器**上的生产 head。30 天 12 次 core-dump 里 7 次是这个形状
# （O-178 / O-175 的唯一交点；两处台账都把它写成「不做」，这里补上拒绝面）。
def _worker_conflict(active_units, alias: str) -> str:
    """纯函数：站上活跃 `rpc-server@<x>` 里存在 x != alias ⇒ 返回 x（该站正为它当 worker）。

    同一 alias **不算**冲突：那是「重载自己」，旧实例本来就要换掉。
    """
    for u in active_units or []:
        name = str(u or "").strip()
        if not name.startswith("rpc-server@"):
            continue
        served = name[len("rpc-server@"):]
        if served.endswith(".service"):
            served = served[:-len(".service")]
        if served and served != alias:
            return served
    return ""


def _active_rpc_workers(station: str):
    """站上活跃 `rpc-server@*` 的单元名。返回 (ok, units)；ok=False = **判不了**。"""
    ok, out = ssh_run(
        station,
        "systemctl list-units 'rpc-server@*' --state=active --no-legend 2>/dev/null "
        "| awk '{print $1}'")
    if not ok:
        return False, []
    return True, [ln.strip() for ln in out.splitlines() if ln.strip()]


def _guard_worker_conflict(station: str, alias: str, force: bool = False) -> int:
    """加载前预检：目标站若正在给**别的**模型当 RPC worker ⇒ 拒绝（exit 3）。

    `--force` 是唯一放行口，且必须让用户看见代价（对面 head 会崩且不再自动重启）。
    判不了（ssh 失败）**不阻断**：load 本身就要 ssh，这里再拦一次只会把网络抖动伪装成
    参数错误；但必须打印留痕 —— 不静默（同 `_probe_worker_busy` 的「不假装知道」）。
    """
    ok, units = _active_rpc_workers(station)
    if not ok:
        print(f"[cluster] ⚠ 无法判定 {station} 站是否有 RPC worker 占用（ssh 失败）—— 继续；"
              f"若该站正在给别的 head 当 worker，本次加载会让那个 head GGML_ABORT（O-178）")
        return 0
    other = _worker_conflict(units, alias)
    if not other:
        return 0
    print(f"[cluster] ⛔ 反向冲突: {station} 站正在给 '{other}' 当 RPC worker"
          f"（活跃 rpc-server@{other}）")
    print(f"[cluster]    在此站加载 '{alias}' 会先跑 infer-unload ⇒ 停掉该 worker ⇒ "
          f"对面的 '{other}' head 会 ggml-rpc ABORT（core-dump，O-178）")
    if force:
        print("[cluster]    --force 已给 ⇒ 继续（对面 head 会被打断，且已不再自动重启）")
        return 0
    print("[cluster]    处置: 先换 worker（重载那个 head 时加 --worker）/ 或 `cluster.py unload`；"
          "确要牺牲它请加 --force (exit 3)")
    return 3


def _uma_fit(total_gib, used_gib, reserved_gib, need_gib) -> tuple:
    """纯函数：UMA **单池**口径 —— 返回 `(放得下?, 可用 GiB)`。

    口径来源（GPUStack `policies/resource_view.py` 的 UMA 分支 +
    `candidate_selectors/gguf_resource_fit_selector.py` 的 fit 判据）：
        allocatable = max(total − used − reserved, 0)
    本集群是 AMD 8060S（UMA）：权重、KV、预分配 buffer 与「显存」落**同一个池**（GTT），
    所以不需要像独显那样分 ram/vram 两本账 —— 只要 `need ≤ allocatable`。

    ⚠ 为什么**必须**扣 reserved（见 `cluster_const.STATION_RESERVED_GIB`）：
      2026-10-26 两次 worker 侧 `vk::DeviceLostError` 都发生在余 15~24G 的区间，
      即「算得下但一跑就崩」—— 判据要表达的是**跑得稳**，不是**塞得进**。
    """
    alloc = max(float(total_gib) - float(used_gib) - float(reserved_gib), 0.0)
    return (float(need_gib) <= alloc), round(alloc, 1)


def _station_gtt(station: str):
    """站上 **GTT** 已用/总量（GiB）。返回 `(ok, used, total)`；读不到 ⇒ `ok=False`。

    为什么不用 `/proc/meminfo`：UMA 下模型权重落 GTT（`ps` RSS 只有几百 MB，
    实测 77G 模型 RSS 仅 217MB / GTT 54.6G）。`estimate_load` 仍用 meminfo 算
    「这个模型要多少」，但「还剩多少」必须读 GTT，否则会把缓存当空闲。
    """
    cmd = ("for f in /sys/class/drm/card*/device/mem_info_gtt_used; do "
           "[ -f \"$f\" ] && { echo \"USED=$(cat $f)\"; break; }; done; "
           "for f in /sys/class/drm/card*/device/mem_info_gtt_total; do "
           "[ -f \"$f\" ] && { echo \"TOTAL=$(cat $f)\"; break; }; done")
    ok, out = ssh_run(station, cmd)
    if not ok:
        return False, 0.0, 0.0
    u = t = None
    for line in (out or "").splitlines():
        line = line.strip()
        if line.startswith("USED="):
            try:
                u = int(line.split("=", 1)[1])
            except ValueError:
                return False, 0.0, 0.0
        elif line.startswith("TOTAL="):
            try:
                t = int(line.split("=", 1)[1])
            except ValueError:
                return False, 0.0, 0.0
    if u is None or not t:
        return False, 0.0, 0.0
    g = 1024.0 ** 3
    return True, round(u / g, 1), round(t / g, 1)


def _capacity_ok(verdict: str) -> bool:
    """纯函数：`estimate_load` 的结论 → 是否放行叠加加载。

    `TIGHT` 与 `cmd_estimate` 同口径（那里也 `return 0`）：余量紧但能装上，
    由调用方打印告警；`UNKNOWN`/`NO_FIT` 一律拒 —— **判不了 ≠ 通过**。
    """
    return str(verdict or "").strip().upper() in ("FITS", "TIGHT")


def _guard_capacity(station: str, alias: str) -> int:
    """`--keep`（允许同站叠加）时的**容量门**：算不下就不动手（exit 4）。

    为什么只在 `--keep` 时判：默认路径会先把该站清空，此时 `estimate_load` 读到的
    used/free 是**卸载前**的读数 ⇒ 拿它判"装不下"是假阴性（会挡住本来合法的替换加载）。

    为什么容器模型直接放行：容器走 `.hgn` 配方、没有 `/etc/llama-instances/<alias>.env`，
    `estimate_load` 取不到 MODEL_PATH/元数据（它自己的兜底也只认 gguf 模型库）。
    容器内存由 halogen 的 `LOWERING THE POOL` 自管 ⇒ 本轮登记为 P2 待办，不在这里猜。
    """
    if alias in CONTAINER_MODELS:
        print(f"[cluster] CAPACITY n/a: '{alias}' 是容器模型（内存由 halogen 自管，O-179 P2 再补）")
        return 0
    est = estimate_load(station, alias)
    if not est.get("ok") or not _capacity_ok(est.get("verdict")):
        free = (est.get("mem") or {}).get("free")
        print(f"[cluster] ⛔ 容量不足: {station} 站装不下 '{alias}' "
              f"(verdict={est.get('verdict')} need={est.get('need_gib')}G"
              + (f" free={free}G" if free is not None else "") + ")")
        for r in (est.get("reasons") or [])[:4]:
            print(f"[cluster]    原因: {r}")
        for a in (est.get("advice") or [])[:4]:
            print(f"[cluster]    建议: {a}")
        print("[cluster]    处置: 先 `cluster.py unload --alias <占着内存的模型>`，或按建议改 conf；"
              "确要硬上请去掉 --keep（会先全站清空）(exit 4)")
        return 4
    # ★ O-179 P0 补强（2026-10-28）：再用**站上 GTT 实账**复核一遍。
    #   estimate 用 /proc/meminfo 算「要多少」，但 UMA 下「还剩多少」只有 GTT 说得准
    #   （MemAvailable 会把可回收缓存算成空闲 ⇒ 偏乐观）。两者都过才放行。
    need = float(est.get("need_gib") or 0.0)
    ok_g, used, total = _station_gtt(station)
    if ok_g:
        fit, alloc = _uma_fit(total, used, STATION_RESERVED_GIB, need)
        print(f"[cluster] CAPACITY(GTT): {station} total={total}GiB used={used}GiB "
              f"reserved={STATION_RESERVED_GIB}GiB alloc={alloc}GiB need={need}GiB")
        if not fit:
            print(f"[cluster] ⛔ 容量不足(GTT): 可用 {alloc}GiB < 需要 {need}GiB ⇒ 拒绝"
                  f"（先 unload 一个、或降 ctx / 换小量化档）(exit 4)")
            return 4
    else:
        print(f"[cluster] ⚠ 读不到 {station} 站 GTT 读数 —— 回退 estimate 的 meminfo 口径；"
              f"该口径偏乐观（把可回收缓存当空闲），故此处留痕")
    print(f"[cluster] CAPACITY ok: {station} 站 verdict={est.get('verdict')} "
          f"need={est.get('need_gib')}G（叠加加载）")
    return 0


def cmd_load(alias: str, backend: str = None, engine: str = None, worker: str = None,
             force: bool = False, keep: bool = False) -> int:
    if backend is not None and backend not in BACKENDS:
        print(f"[cluster] 非法 --backend '{backend}'. 可选: {', '.join(sorted(BACKENDS))} (exit 1)")
        return 1
    if engine is not None and not _engine_ok(engine):
        print(f"[cluster] 非法 --engine '{engine}' (仅允许 字母/数字/./_/-; 例: glm5next-20260928) (exit 1)")
        return 1
    if worker is not None and worker not in RPC_WORKER_IPS:
        print(f"[cluster] 非法 --worker '{worker}'. 可选: {', '.join(sorted(RPC_WORKER_IPS))} (exit 1)")
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
    # --worker 只对 RPC 双机类有意义 (head 固定权重站 B, worker 由用户指派 A|C)。
    if worker and not is_rpc:
        print(f"[cluster] --worker 仅适用于 RPC 双机类模型 ({', '.join(sorted(RPC_MODELS))}) (exit 1)")
        return 1
    # ★ O-179（2026-10-28）：`--keep` = 允许同站叠加（只替换同名 alias + 过容量门）。
    #   RPC 双机本轮不开放：head 与 worker 的 GTT 同池竞争（O-175/O-178）还没算清，
    #   放行等于用一个未验证的内存模型去赌生产 head。
    if keep and is_rpc:
        print(f"[cluster] --keep 暂不支持 RPC 双机类 ({', '.join(sorted(RPC_MODELS))})："
              f"head/worker 的 GTT 同池竞争未算清 (O-179 D-2) (exit 1)")
        return 1
    # ★ O-178/O-175：反向冲突预检 —— 目标站若正给**别的**模型当 RPC worker，加载会
    #   （经 reclaim_and_unload ⇒ infer-unload）停掉那个 worker，对面 head 直接 ABORT。
    #   放在所有分派之前：容器化/按站路由/RPC 三条路都会先回收该站。
    _guard = _guard_worker_conflict(station or DEFAULT_STATION, matched, force)
    if _guard:
        return _guard
    # ★ O-179 P0：容量门只在 --keep 时判（默认路径会先清空该站，读数会是卸载前的假阴性）。
    if keep:
        _cap = _guard_capacity(station or DEFAULT_STATION, matched)
        if _cap:
            return _cap
    # 容器化模型 (halogen, CONTAINER_MODELS): 不走 infer-load ⇒ 必须在 **C 站分支之前**分派。
    # 显式 `--backend unsloth` 等其它后端时**不**分派 —— 保留既有回退路径 (load ... --backend unsloth)。
    if matched in CONTAINER_MODELS and backend in (None, CONTAINER_MODELS[matched]["backend"]):
        if how == "station":
            print(f"[cluster] 按站路由: {alias} -> {station} 站, 容器编排 {matched}")
        if engine:
            print(f"[cluster] ⚠ --engine '{engine}' 对容器化模型无意义, 已忽略。")
        return _load_container_model(matched, station, keep)
    if backend == "halogen":     # 非容器模型没有 halogen 配方 ⇒ 响亮拒绝, 不让 infer-load 报"未知后端"
        print(f"[cluster] '{matched}' 不在 CONTAINER_MODELS 中, 无 halogen 容器配方 "
              f"(已登记: {', '.join(sorted(CONTAINER_MODELS))}) (exit 1)")
        return 1
    if station == "C":
        # C 站分支在通用路由行之前 return, 故这里单独标一下"按站路由" —— 让用户知道
        # 自己是靠按站路由名进来的 (A/B 路径的标注在下面 tag 处)。
        if how == "station":
            print(f"[cluster] 按站路由: {alias} -> C 站, 站上别名 {matched}")
        return _cmd_load_c(matched, backend, engine, keep)
    # llama-rpc 双机类: 显式 --backend 单机后端(非 llama-rpc) 视为强制单机加载, 走正常路径;
    # 否则走 RPC 编排 (见 _load_rpc) —— 2026-09-15 落地方案 v2 P0-3, 原为"打印手动步骤 exit 2"。
    if is_rpc:
        if backend and backend != "llama-rpc":
            if worker:
                print(f"[cluster] --worker '{worker}' 与 --backend {backend} (强制单机) 矛盾 (exit 1)")
                return 1
            station = station or DEFAULT_STATION
            print(f"[cluster] '{matched}' 为 RPC 双机类, --backend {backend} 视为强制单机加载 (退化为 {station} 站单机)。")
        else:
            return _load_rpc(matched, station or DEFAULT_STATION, engine, worker)
    # ds4 双机 PP: 别名在 DS4_PP_MODELS 且显式 --backend ds4 ⇒ 走双机编排 (值 = (coordinator 站, worker 站))。
    # 单机 ds4 (别名不在表里, 或未显式指定 backend) 落到下面的普通路径 (`infer-load --backend ds4`)。
    if backend == "ds4" and matched in DS4_PP_MODELS:
        return _load_ds4_pp(matched, *DS4_PP_MODELS[matched])
    st_host = STATIONS[station]["host"]
    # 把"匹配方式"显式打印: default 分支意味着别名未在路由表中, 只是落到了默认站 ——
    # 若站上并无该别名, infer-load 才会失败; 不这样标出来会让它与正常路由外观一致 (见 resolve_alias 注释)。
    tag = {"prefix": "  [前缀匹配]",
           "station": "  [按站路由 —— 由路由名显式指定来源站]",
           "default": f"  [★未在路由表中 → 落默认站; 若站上无此别名, infer-load 会失败]"}.get(how, "")
    print(f"[cluster] 路由: {matched} -> {station} 站 ({st_host}){tag}")
    # ★ 2026-10-21: 老后端路径也必须先回收**容器** —— infer-unload 只杀进程, 看不见 docker 容器
    #   (容器仍占 8080 发布面 + ~90 GB GTT)。缺这一步时 `load ... --backend unsloth` 会与
    #   halogen 容器抢 8080/GTT。回收幂等, 无容器时零副作用。
    # ★ 2026-10-26 缺口 2/3：回收 + 卸载统一走 reclaim_and_unload —— 旧代码先 `_reclaim_containers`
    #   再用 `/health` 有无响应决定是否 unload。但容器被 `docker rm -f` 后 HTTP 服务已消失、
    #   GTT 仍可能被 docker-proxy/命名空间持有（本仓 C 站实测 8080 释放约 4m18s）⇒ 那个条件
    #   恰好漏掉"容器已删但资源未释放"这一格。`infer-unload` 幂等且含 wait_gtt，无条件执行更正确。
    _r1 = reclaim_and_unload(station, matched if keep else None)
    if not _r1["ok"]:
        print(f"[cluster] {station} 站回收/卸载失败 ⇒ 中止: {_r1['steps']}")
        return 1
    print(f"[cluster] 加载中 (站内 load-mem-gate 自动护航) ...")
    rc = ssh_stream(station, _build_infer_load_cmd(matched, backend, engine))
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


# ── RPC worker 选路（纯函数，2026-10-25）────────────────────────────────
# 现场：三站都跑 qwen halogen；GLM/DS 的 conf RPC_TARGET 固定 A。`_load_rpc`
# 原先未给 --worker 时无条件用 conf 的 A，且回收三站容器 ⇒ A 的 qwen 被杀。
# 本函数只做"选哪个节点"的决策（不碰站、不发 ssh）：
#   · 显式 --worker 优先；
#   · 否则 conf 目标空闲就用它；
#   · conf 忙（如 A 有 halogen 容器）⇒ 按候选顺序取第一个空闲节点（自动换 C）；
#   · 全部忙 ⇒ 回退 conf 目标并标 fallback（调用方负责大声报出）；
#   · 候选为空 / 无法映射到站 ⇒ target=None（判不了 ≠ 选默认）。
RPC_WORKER_STATIONS = {ip: st for st, ip in RPC_WORKER_IPS.items()}


def parse_worker_busy(out: str) -> str:
    """把站上 busy 探针输出解析成忙因（排序去重；'' = 空闲）。"""
    toks = sorted({t.strip() for t in (out or "").splitlines() if t.strip()})
    return "+".join(toks)


def classify_worker_probe(ok: bool, out: str) -> dict:
    """把一次探针结果归一成三态（纯函数）。

    ★ 2026-10-26 缺口 1：旧的失败形态是字符串 "probe-failed"，随后被选路当成
    "普通忙因" ⇒ 探测失败的节点仍进"可回收"分支（E1 复现）。这里把失败显式归
    `unknown`，让它只能导致中止——对齐 K8s 探针语义：只有 Success 才算就绪。
    """
    if not ok:
        return {"state": "unknown", "reason": f"ssh-failed: {(out or '').strip()[:120]}"}
    why = parse_worker_busy(out)
    if why:
        return {"state": "busy", "reason": why}
    return {"state": "free", "reason": ""}


def probe_worker_state(st: str) -> dict:
    """只读探针：站上有 halogen 容器或 :8080 在听 ⇒ busy；SSH 探不了 ⇒ unknown。

    与旧 `_probe_worker_busy` 的唯一差别是**返回值形状**（三态 dict 而非字符串），
    探针命令本身不变（仍是只读的 docker ps + ss）。
    """
    ok, out = ssh_run(
        st,
        "docker ps --format '{{.Names}}' 2>/dev/null | grep -qx halogen && echo halogen; "
        "ss -ltn 2>/dev/null | grep -q ':8080 ' && echo port8080",
        timeout=20)
    return classify_worker_probe(ok, out)


def _probe_map(targets) -> dict:
    """对候选目标逐个探测 → {target: ProbeResult}。

    无法映射到站的目标**不入表**（选路按缺键 = unknown 处理，不会默认空闲）；
    单个目标探测异常也只归它自己 unknown，不拖死整条加载。
    """
    out = {}
    for t in targets:
        st = RPC_WORKER_STATIONS.get(t)
        if not st:
            continue
        try:
            out[t] = probe_worker_state(st)
        except Exception as e:          # 连接级异常（超时/认证/端口不可达）
            out[t] = {"state": "unknown", "reason": f"{type(e).__name__}: {e}"}
    return out


def resolve_rpc_worker(conf_target=None, candidates=None, probe=None,
                       explicit=None) -> dict:
    """RPC worker 选路（纯函数）。返回 {target, station, source, reason}。

    source: explicit | explicit-invalid | conf | auto | fallback | none | aborted-unknown
    probe:  {target: {"state": "free"|"busy"|"unknown", "reason": str}}
            ★ 缺键 = unknown("未探测") —— 不再默认空闲。

    规范序见 spec/cluster-orchestration-reliability/DESIGN.md §4.2。
    核心纪律：**unknown 永不进入可回收分支**；它只可能让选路中止。
    （"两站都忙 ⇒ 改用 C 并回收 C"仍成立——因为忙是**已知**状态，回收是安全动作。）
    """
    probe = probe or {}
    known = [c for c in (candidates or []) if c in RPC_WORKER_STATIONS]

    def state(c):
        return (probe.get(c) or {"state": "unknown", "reason": "未探测"})["state"]

    def why(c):
        return (probe.get(c) or {}).get("reason") or state(c)

    # 1. explicit（★ 显式也必须探测：旧代码在显式路径下跳过探针）
    if explicit:
        if explicit not in known:
            return {"target": None, "station": None, "source": "explicit-invalid",
                    "reason": f"显式目标 {explicit} 不在已声明/存活候选 {known or '空'}"}
        if state(explicit) == "unknown":
            return {"target": None, "station": None, "source": "aborted-unknown",
                    "reason": f"显式目标 {explicit} 探测失败({why(explicit)}) ⇒ 中止，不回收"}
        return {"target": explicit, "station": RPC_WORKER_STATIONS[explicit],
                "source": "explicit", "reason": "用户显式指派"}

    # 2. 无已知候选
    if not known:
        return {"target": None, "station": None, "source": "none",
                "reason": "候选为空或无节点可映射到站"}

    # 3. 分类；free/busy 全空 = 全未知
    free = [c for c in known if state(c) == "free"]
    busy = [c for c in known if state(c) == "busy"]
    if not free and not busy:
        detail = " ".join(f"{c}=unknown({why(c)})" for c in known)
        return {"target": None, "station": None, "source": "aborted-unknown",
                "reason": f"{detail} ⇒ 中止，不做回收"}

    # 4. conf 空闲
    if conf_target in free:
        return {"target": conf_target, "station": RPC_WORKER_STATIONS[conf_target],
                "source": "conf", "reason": "conf 目标空闲"}

    # 5. conf 忙 ⇒ 优先保护它（如 A 的 qwen），按 a/b/c/d 互斥完备
    if conf_target in busy:
        alts = [c for c in known if c != conf_target]
        alt_free = [c for c in alts if state(c) == "free"]
        if alt_free:
            t = alt_free[0]
            return {"target": t, "station": RPC_WORKER_STATIONS[t], "source": "auto",
                    "reason": f"conf {conf_target} 忙({why(conf_target)}) ⇒ 改用 {t}；{t} 空闲"}
        alt_busy = [c for c in alts if state(c) == "busy"]
        if alt_busy:
            t = alt_busy[0]
            return {"target": t, "station": RPC_WORKER_STATIONS[t], "source": "auto",
                    "reason": f"conf {conf_target} 忙({why(conf_target)}) ⇒ 改用 {t}；"
                              f"{t} 也忙({why(t)}) ⇒ 回收它"}
        if alts:      # 有其他候选但全 unknown（free/busy 已被上面接住）
            return {"target": None, "station": None, "source": "aborted-unknown",
                    "reason": f"conf {conf_target} 忙({why(conf_target)}) 且其他候选均未知 ⇒ 中止"}
        return {"target": conf_target, "station": RPC_WORKER_STATIONS[conf_target],
                "source": "fallback",
                "reason": f"conf {conf_target} 忙({why(conf_target)}) 且无其他候选 ⇒ 回退并回收它"}

    # 6. conf 不在候选 / unknown：只从已知状态里选
    if free:
        t = free[0]
        return {"target": t, "station": RPC_WORKER_STATIONS[t], "source": "auto",
                "reason": "conf 不在候选/未知 ⇒ 用空闲节点"}
    t = busy[0]
    return {"target": t, "station": RPC_WORKER_STATIONS[t], "source": "auto",
            "reason": f"conf 不在候选/未知且无空闲 ⇒ 用 {t}（回收它）"}


def _load_rpc(alias: str, station: str, engine: str = None, worker: str = None) -> int:
    """RPC 双机类加载编排 (2026-09-15, 方案 v2 P0-3)。

    把原先"打印手动步骤并 exit 2"升级为**一条命令端到端**。零件全部复用既有资产:
      · `nodes.env`   = RPC 节点声明 (单一事实源, B 站 /etc/llama-instances/nodes.env)
      · `rpc-nodes`   = 站上 helper: 读 nodes.env → 起各节点 rpc-server@<alias> 并等端口 LISTEN
      · `infer-load`  = 站上加载 (conf 的 RPC_TARGET=auto 会自动展开为 rpc-nodes 输出)
      · `infer-unload`= 收尾 (站上已含"顺带停 rpc-server")

    为什么 master 固定 B 站: `nodes.env` 与 `rpc-nodes` 都在 B 站, 且既有设计是
    "B 站发起 + A 站承载张量分片"(见 spec/cluster-bench/DESIGN §2)。指定其他站会被纠正。

    engine = 引擎变体 (见 infer-load --engine), 2026-09-29 起**必须透传到此**:
      未透传时 `--engine` 只对 `_cmd_load_c`(C 站) 与最终 infer-load 生效 —— 而 RPC 类的加载
      入口正是本函数, 于是 `load glm-5.3-flash --engine glm5next-20260928` 会在 head 侧
      `unknown model architecture: 'glm5next'` 失败。worker 侧同版引擎由 conf 键
      LLAMA_RPC_SERVER_BIN + `rpc-nodes --start` 透传 (见 ops/rpc-nodes)。

    worker = 2026-10-22 单 worker 形态: **head 固定权重所在站 B**, worker 由用户按
      `--worker A|C` 指派 (映射见 cluster_const.RPC_WORKER_IPS), 最终以
      `infer-load --rpc-target <ip:port>` 覆盖 conf 的 RPC_TARGET —— **不改 conf**。
      未给 --worker ⇒ 沿用 conf 的 RPC_TARGET (GLM/DS 已固化单 worker, 见 params-ledger)。
      目标必须同时出现在 `rpc-nodes --all` 声明与存活探测中: 显式 RPC_TARGET 不像 `auto`
      那样可静默退化, 死 worker 会让 llama-server 加载中途失败且难读。
    ★ 2026-10-25 自动选路: 未给 --worker 时探 A/C 的 busy（halogen 容器 / :8080 在听），
      conf 目标忙则改用另一空闲节点（`resolve_rpc_worker`, 纯函数）；两站都忙则回退 conf
      目标并打 `RPC_AUTO_WORKER source=fallback`。容器回收范围同时收窄到 **head + 选中
      worker**（非 worker 站的 qwen 保留）。
    """
    if station != "B":
        print(f"[cluster] RPC 类由 B 站(master)发起 (nodes.env/ rpc-nodes 均在其上), 已忽略指定的 {station} 站。")
        station = "B"
    explicit_target = RPC_WORKER_IPS.get(worker) if worker else None
    if worker and not explicit_target:
        print(f"[cluster] 非法 --worker '{worker}'. 可选: {', '.join(sorted(RPC_WORKER_IPS))} (exit 1)")
        return 1
    print(f"[cluster] == RPC 双机类加载编排: {alias} @ {station} 站 (master) ==")
    if engine:
        print(f"[cluster] 引擎变体: {engine} (head 与 worker 必须同版, 由 conf + rpc-nodes 透传)")

    # ── worker 选路（2026-10-25）────────────────────────────────────────
    # 候选 = B 站 nodes.env 的**声明**清单（启动前的 “存活” 必然为空，不能拿它当候选）。
    ok_d, decl = ssh_run(station, "rpc-nodes --all 2>/dev/null")
    decl_list = decl.replace(",", " ").split() if ok_d else []
    if not decl_list:
        print(f"[cluster] nodes.env 声明清单为空/不可读 ({decl.strip() or '空'}) → 中止。")
        return 1
    conf_target = _conf_rpc_target(station, alias) or None
    # ★ 2026-10-26 缺口 1：显式 --worker 也必须探测 —— 旧代码在显式路径下跳过探针，
    #   于是死节点被当作"可用"直接进回收+启动。现在 probe 恒有值，unknown 只能中止。
    probe = _probe_map(decl_list)
    print("[cluster] 选路输入: " + " ".join(
        f"{t}={p['state']}({p['reason']})" if p["reason"] else f"{t}={p['state']}"
        for t, p in probe.items()))
    decision = resolve_rpc_worker(conf_target, decl_list, probe, explicit_target)
    if decision["target"] is None:
        print(f"[cluster] RPC worker 选路失败: {decision['reason']} → 中止 (不静默退化)。")
        return 1
    rpc_target = decision["target"]
    worker_station = decision["station"]
    print(f"[cluster] RPC_AUTO_WORKER source={decision['source']} target={rpc_target} "
          f"station={worker_station} :: {decision['reason']}")
    if decision["source"] == "fallback":
        print("[cluster] ⚠ conf 忙且无其他候选 ⇒ 回退 conf 目标（该站的 qwen/halogen 会被回收）。")

    # ★ 2026-10-22 修「8080 假绿」：RPC 加载原先只做 `infer-unload`，不回收 docker 容器。
    #   2026-10-25 收窄：只回收 **head(B) + 选中 worker**；非 worker 站的 qwen 不动。
    #   （B 的 8080 仍被先回收 ⇒ READY 不会命中旧容器。）
    # ★★ 2026-10-28（O-178）：**顺序承重** —— 必须先停 head、再停 worker。
    #   旧写法 `sorted({station, worker})` 恰好先回收 worker（A < B）⇒ head 在退出清理
    #   （`common_memory_breakdown_print` → `ggml_backend_rpc_get_device_memory`）时发现对端没了，
    #   ggml-rpc 把"对端崩溃/畸形响应"当**致命** ⇒ `GGML_ABORT` ⇒ SIGABRT（status=6，core-dump）。
    #   实测：B 站 deepseek 30 天内 7 次 core-dump，7 次都带 `Remote RPC server crashed`。
    #   ⇒ head 必须**先**停并等其进程真正退出（`systemctl stop` 同步），之后才动 worker。
    head_first = [station] + [w for w in sorted({worker_station or ""}) if w and w != station]
    print(f"[cluster] 回收范围: {'/'.join(head_first)}（head 先停；非 worker 站的 qwen 保留）")
    for st in head_first:
        _r = reclaim_and_unload(st)
        if not _r["ok"]:
            print(f"[cluster] {st} 站回收/卸载未完成 → 中止: {_r['steps']}")
            return 1

    print("[cluster] [2/4] 启动 RPC 工作节点 (rpc-nodes --start, 含等端口 LISTEN) ...")
    # 2026-10-22: 有 --worker 时把目标作为 rpc-nodes 的第三参数（节点过滤）——
    #   预启动也只起被选节点，避免"未选节点缺单元/离线"拖垮整条加载。
    start_cmd = f"rpc-nodes --start '{alias}'" + (f" '{rpc_target}'" if rpc_target else "")
    ok, out = ssh_run(station, start_cmd, timeout=240)
    if out.strip():
        print(out.strip()[-1200:])
    if not ok:
        print("[cluster] rpc-nodes --start 失败 → 中止 (不进入加载)。")
        return 1

    # 存活探测而非只回显声明 —— 2026-09-15 实测: nodes.env 声明了 C 站(10.10.11.3:50052),
    # 但 C 站未装 rpc-server 单元(--start 会报 Unit not found, 由 rpc-nodes 容错兜住)。
    # 只有**存活**节点才会进 llama-server 的 --rpc, 故这里显式打印两者差异。
    ok, alive = ssh_run(station, "rpc-nodes 2>/dev/null")
    print(f"[cluster] [3/4] RPC 存活节点: {alive.strip() or '(无)'}")
    print(f"[cluster]        声明清单  : {decl.strip() or '(空)'}")
    if not alive.strip():
        print("[cluster] 无存活 RPC 节点 → 中止 (否则 llama-server 会因 --rpc 空而退化为单机)。")
        return 1
    alive_set = alive.replace(",", " ").split()
    if rpc_target not in alive_set:
        print(f"[cluster] 选中 worker {rpc_target} 未在存活清单 "
              f"({alive.strip() or '空'}) → 中止 (不会静默退化到 conf/auto)。")
        return 1

    print(f"[cluster] [4/4] 加载权重 (RPC_TARGET={rpc_target or 'conf 值'}) ...")
    # ★★ 2026-09-28 修: 这里原为 `_build_infer_load_cmd(alias, None)` —— **backend 漏传**。
    #   后果(实测复现): 远端收到 `infer-load '<alias>'`(不带 --backend) ⇒ infer-load 落到
    #   默认 BACKEND=unsloth ⇒ **studio 单机加载**, 把"双机 RPC"变成"单机全量持有" ⇒
    #   V4-Flash 这种 146 GiB 模型必然 OOM(SIGKILL, signal 9)。
    #   ⚠ 且**显式 `--backend llama-rpc` 也救不了**: cmd_load 的 is_rpc 分支里
    #   `backend == "llama-rpc"` 仍走 _load_rpc, 而本行恒传 None ⇒ 无论用户怎么传都落到 unsloth。
    #   ⇒ 这便是"RPC 类模型只能手工起"的真因, 不是能力缺失。
    #   兄弟函数 _load_ds4_pp 传的是 "ds4"(见下方), 本处漏传属**不一致**, 非设计。
    rc = ssh_stream(station, _build_infer_load_cmd(alias, "llama-rpc", engine, rpc_target))
    if rc != 0:
        print(f"[cluster] 加载失败 (rc={rc}) → 可用 journalctl -u 'llama-server@*' 排查。")
        return 1

    ok, hl = ssh_run(station, "curl -s --max-time 5 http://127.0.0.1:8080/health")
    if ok and hl.strip():
        print(f"[cluster] {station} 站引擎响应: {hl.strip()[:60]}")
    print(f"[cluster] RPC READY ✓  ({alias} 已跨机加载; 收尾用 cluster.py unload)")
    return 0


def _load_ds4_pp(alias: str, coord: str, worker: str) -> int:
    """ds4 (DwarfStar) 双机 PP 加载编排 (2026-09-28, 见 spec/ds4-backend/DESIGN.md)。

    与 _load_rpc 同构 (零件复用: 站上 infer-load / infer-unload), 但序**不可反**:
      [1/3] 先在 worker 站起 ds4 (持层片 + KV 分片)
      [2/3] 再在 coordinator 站起 ds4 (持 prompt/采样/客户端 API)
      [3/3] 探活 coordinator 的 /v1/models (★ ds4 无 /health 端点, 只能用 /v1/models)

    为什么序不可反: ds4 PP 官方原话 "Start workers first, then start the coordinator."
    —— coordinator 要等 worker 注册层片路由; 若 worker 起失败仍去起 coordinator, coordinator
    只会空等 → 挂死。故 worker 非 0 即**中止且不起下游**。

    为什么只有 PP 没有 TP: ds4 在 ROCm 上 TP 被源码门禁拒绝 ("tensor parallelism requires
    the Metal backend"), 故 DS4_PP_MODELS 只给层切片切分 (--layers, 闭区间, 末段写 :output)。
    """
    print(f"[cluster] == ds4 双机 PP 加载编排: {alias} @ worker={worker} 站 → coordinator={coord} 站 ==")

    # P1 #7: 先取 coordinator 的直连段 IP —— 取不到就在**起 worker 之前**中止，
    # 绝不退回 0.0.0.0（CWE-1327：默认即全接口暴露）。
    pp_ip = _pp_listen_ip(coord, worker)
    if not pp_ip:
        print(f"[cluster] 无法从 inventory/net.yaml 读出 {coord}-{worker} 直连段 IP "
              f"⇒ ds4 PP 中止 (不默认 0.0.0.0)。")
        return 1
    print(f"[cluster] PP listen: coordinator={coord} ip={pp_ip}")

    print(f"[cluster] [1/3] 先在 worker={worker} 站起 ds4 (官方序: 先 worker 后 coordinator) ...")
    rc = ssh_stream(worker, _build_infer_load_cmd(alias, "ds4"))
    if rc != 0:
        print(f"[cluster] worker 启动失败 (rc={rc}) → 中止, 未起 coordinator。")
        return 1

    print(f"[cluster] [2/3] 再在 coordinator={coord} 站起 ds4 (--pp-listen {pp_ip}) ...")
    rc = ssh_stream(coord, _build_infer_load_cmd(alias, "ds4", pp_listen=pp_ip))
    if rc != 0:
        print(f"[cluster] coordinator 启动失败 (rc={rc}) → 中止。")
        return 1

    print("[cluster] [3/3] 探活 coordinator /v1/models (ds4 无 /health 端点) ...")
    ok, out = ssh_run(coord, "curl -s --max-time 5 http://127.0.0.1:8080/v1/models")
    if ok and out.strip():
        print(f"[cluster] {coord} 站引擎响应: {out.strip()[:60]}")
    print(f"[cluster] ds4 PP READY ✓  ({alias} 已跨机 PP 加载; worker={worker} + coordinator={coord}; 收尾用 cluster.py unload)")
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
    # 容器化模型 (CONTAINER_MODELS): 与 cmd_load 同一分派判据 (显式别的后端 ⇒ 保留回退路径)。
    if alias in CONTAINER_MODELS and backend in (None, CONTAINER_MODELS[alias]["backend"]):
        return _load_container_model(alias, station)
    if backend == "halogen":
        print(f"[cluster] '{alias}' 不在 CONTAINER_MODELS 中, 无 halogen 容器配方 (exit 1)")
        return 1
    print(f"[cluster] 指定站加载: {alias} -> {station} 站 ({STATIONS[station]['host']})")
    # ★ 2026-10-21: 同 cmd_load —— 老后端路径必须先回收容器 (infer-unload 看不见 docker)。
    #   2026-10-26: 回收 + 卸载合并为无条件一步，失败即中止。
    _r1 = reclaim_and_unload(station)
    if not _r1["ok"]:
        print(f"[cluster] {station} 站回收/卸载失败 ⇒ 中止: {_r1['steps']}")
        return 1
    print(f"[cluster] 加载中 (站内 load-mem-gate 自动护航) ...")
    rc = ssh_stream(station, _build_infer_load_cmd(alias, backend))
    if rc != 0:
        print(f"[cluster] 加载失败 (rc={rc})。")
        return 1
    print(f"[cluster] {station} 站 READY ✓ (站内 infer-load 判定, rc=0)")
    return 0


def cmd_unload_on(station: str, alias: str = None) -> int:
    """只卸载**指定站** (web 按站操作; 三站并行卸载仍用 cmd_unload)。

    `alias` 非 None ⇒ 只卸该别名（O-179 P1）；None ⇒ 整站清空（旧语义）。
    """
    if station not in STATIONS:
        print(f"[cluster] 未知站 '{station}'")
        return 1
    # ★ 容器**必须先回收** —— 否则 infer-unload 的 wait_gtt 会因容器仍持 ~90 GB GTT
    #   在站上白等满 180 s (90×2s) 才 WARN。
    _r = reclaim_and_unload(station, alias)
    _what = f" {alias}" if alias else ""
    print(f"[cluster] {station} 站{_what} " + "; ".join(
        f"{s['name']}={'OK' if s['ok'] else (s['detail'] or 'FAIL')}" for s in _r["steps"]))
    return 0 if _r["ok"] else 1


def cmd_unload(alias: str = None) -> int:
    """三站并行卸载。★ 单站连不上**只记该站失败** —— 不吞掉其余站的结论, 也不让整条命令崩。

    `alias` 非 None ⇒ 三站都只卸这个别名（`cluster.py unload --alias <alias>`，O-179 P1）。
    """
    results = {}
    threads = []

    def run(st):
        # 异常**必须在现场转成"该站失败"**: 一旦逃出线程, results 就缺键 ⇒ 主循环
        # `results[st]` 抛 KeyError ⇒ 整条 unload 崩掉, 连 A/B 已成功的结论都拿不到。
        # (2026-09-29 实测形态: C 站 LAN 192.168.1.37 不通 —— 命令直接 traceback, 只回显了 A/B。
        #  与 P1-4「解析失败不能表现成业务全错」同一原则。)
        try:
            _r = reclaim_and_unload(st, alias)   # 同为 wait_gtt 前置; 且是"卸载"该有的语义
            results[st] = 0 if _r["ok"] else _r
        except Exception as e:          # 连接级异常: 超时 / 认证 / 端口不可达
            results[st] = f"{type(e).__name__}: {e}"

    # ★★ 2026-10-28（O-178）：**B 先停、再并行 A/C**。RPC 模型的 head 固定落在 B（权重所在站），
    #   若三站并发，A 的 worker 可能在 B 的 head 走完退出清理之前就没了 ⇒ head 的
    #   `common_memory_breakdown_print` 去取 worker 显存 ⇒ ggml-rpc 判"对端崩溃"⇒ ABORT/core-dump。
    #   非 RPC 场景下"先停 B"只是顺序变化，语义不变。
    run("B")
    for st in ("A", "C"):
        t = threading.Thread(target=run, args=(st,))
        t.start(); threads.append(t)
    for t in threads:
        t.join()
    rc = 0
    for st in ("A", "B", "C"):
        r = results.get(st, "线程未回填")
        if r == 0:
            print(f"[cluster] {st} 站 回收+卸载: OK")
        else:
            print(f"[cluster] {st} 站 回收+卸载: FAIL ({r})")
            rc = 1
    return rc


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


def containers_plan(act: str, *, station: str, image=None, name=None,
                    publish=(), group_add=(), device=(), volume=(), env=(),
                    ipc=None, ulimit=(), detach=False, log=None) -> list:
    """动作 → **将下发到站上的命令列表**(纯函数, 不连站)。★ 计划与执行**同源**。

    act ∈ {pull, up, down}; 缺参抛 ValueError。`up` 的 `-p` 绑定由调用方给出的 `publish` 决定
    (loopback 约束见 `cmd_containers` / ADR-0014 D4)。

    ★ `up` 的 flag 集**照抄上游部署配方**(`docker-compose.yml` / `AGENTS.md`), 不自由发挥:
      · `device`   `--device /dev/kfd --device /dev/dri` —— GPU(KFD/DRI) 准入;
      · `group_add` `--group-add video --group-add render` —— Docker 路径(Podman 的 `keep-groups` 是扩展);
      · `ipc`      `--ipc=host` —— ★ **load-bearing**: 上游逐字"no `shm_size` substitutes"
                   ⇒ 本仓**不提供** `--shm-size`, 需要共享命名空间就用 `--ipc=host`;
      · `ulimit`   `--ulimit memlock=-1:-1` —— 大页锁定;
      · `env`/`volume` —— BYO GGUF 的 `HALOGEN_CHECKPOINT` + `-v <models>:/models:ro`。
    保序: name → device → group-add → ipc → ulimit → env → volume → publish → image。"""
    act = (act or "").lower()
    if act == "pull":
        if not image:
            raise ValueError("pull 需要 --image <ref>")
        if detach:
            # ★ 实测(2026-10-10): 多 GB 镜像 `docker pull` 远超 ssh exec 上界(timeout+30s)
            #   ⇒ 两次实拉(900s/1800s)均 TimeoutError、镜像未落地。解耦 ssh 会话:
            #   setsid 脱离控制终端, fd 全部重定向, `&` 后立即返回; docker 端缓存可续传。
            lf = log or "/tmp/cluster-docker-pull.log"
            return [f"setsid sh -c 'docker pull {image} >>{lf} 2>&1' "
                    f"</dev/null >/dev/null 2>&1 & echo DETACHED"]
        return [f"docker pull {image}"]
    if act == "down":
        if not name:
            raise ValueError("down 需要 --name <容器名>")
        return [f"docker rm -f {name}"]
    if act == "up":
        if not image:
            raise ValueError("up 需要 --image <ref>")
        if not name:
            raise ValueError("up 需要 --name <容器名>")
        cmd = f"docker run -d --name {name}"
        for d in device:
            cmd += f" --device {d}"
        for g in group_add:
            cmd += f" --group-add {g}"
        if ipc:
            cmd += f" --ipc={ipc}"
        for u in ulimit:
            cmd += f" --ulimit {u}"
        for e in env:
            cmd += f" -e {e}"
        for v in volume:
            cmd += f" -v {v}"
        for p in publish:
            cmd += f" -p {p}"
        return [cmd + f" {image}"]
    raise ValueError(f"未知容器动作: {act}（可选 pull|up|down）")
