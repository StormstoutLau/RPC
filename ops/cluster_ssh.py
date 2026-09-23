#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cluster_ssh — SSH 层 + 探测层（`cluster.py` 的拆分模块，阶段 1b）。

为什么存在：`cluster.py` 是单文件 5000+ 行；本模块收拢"跨站怎么连、连上怎么探"这一层。
拆分方案见 docs/2026-09-23_cluster.py模块化重构_调研与方案.md。

边界（改之前先读）：
  · **本模块是唯一的建连入口** —— 任何地方要发 ssh，走 `ssh_run` / `ssh_stream`，
    不要在别处再 `paramiko.SSHClient()`（超时/策略会与 `_connect` 漂，2026-09-22 已统一三个超时）。
  · 只做**传输 + 单站探测**；集群级聚合（collect_*）与命令实现仍在 `cluster.py`。
  · `cluster.py` 显式重导出 `ssh_run` / `ssh_stream` / `_connect` / `probe_station`，
    使外部调用点（含 `cluster_web.py`）保持不变。
"""
import os
import re
import sys
import time
import socket

import paramiko

from cluster_const import STATIONS, STATION_PORT, SSH_TIMEOUT

# ── SSH 层 ─────────────────────────────────────────────
# 主机名解析缓存 —— 性能关键 (2026-09-14 实测):
#   mDNS 解析 *.local 单次约 14s (A 14.07s / B 14.10s), 而 IP 直连 ssh 仅 0.2s。
#   原先每次 ssh_run 都用主机名重连 ⇒ 每次连接白付 ~14s。9 次串行即 130s
#   (这正是 /api/status 129.6s 的根因, 见 CHECKLIST F19)。
#   C 站一直用 IP 故从未受影响。
#   此处缓存解析结果, 使"解析一次、全程复用"; 长驻的 web 服务受益最大 (热后近 0 成本)。
#   ⚠ 2026-09-16 (ADR-0006) 更新: A/B 的 host 已直接改成 LAN IPv4 ⇒ 本缓存对三站都成了直通
#     (IP 不经解析), "每进程付一次 ~14s" 的成本已彻底消失; 更早的根治理由见 ADR-0006。
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
    """建连的**唯一入口** —— 三个调用点都走它, 别在别处再 `paramiko.SSHClient()`(配置会漂)。

    三个超时都必须显式给 (2026-09-22 统一) —— 这是 OpenSSH 侧
    `-o BatchMode=yes -o ConnectTimeout=N` 的 **paramiko 对应物**:
      · `timeout`        = TCP 建连超时
      · `banner_timeout` = 等 SSH banner
      · `auth_timeout`   = 等认证完成 —— **paramiko 默认 30s** (实测 paramiko 5.0.0 源码:
        `self.banner_timeout = 15` / `self.auth_timeout = 30`), 与 `banner_timeout` **不同源**;
        不显式给 ⇒ "认证阶段卡住"要等 30s 而不是我们的 `SSH_TIMEOUT`, 与 ConnectTimeout 的意图相悖。
    注意差异: paramiko **不会**像 OpenSSH 那样弹口令阻塞等 stdin(它无 BatchMode 选项, 也**没有**
    "挂死"这一形态, 认证失败是抛异常) ⇒ 这一侧要补的只是"把卡住的上界压到 SSH_TIMEOUT"。
    """
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(resolve_host(st), username=STATIONS[st]["user"],
                timeout=timeout, banner_timeout=timeout, auth_timeout=timeout)
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
