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
    ok, out = ssh_run(st, f"curl -s --max-time 5 http://127.0.0.1:{port}/health; echo; "
                          "systemctl is-active llama-server@* 2>/dev/null | head -1; "
                          "systemctl list-units 'llama-server@*' --no-legend 2>/dev/null | awk '{print $1}'")

    if not ok:
        result["llama"] = "UNREACHABLE"
        return result
    result["reachable"] = True
    lines = [l for l in out.splitlines() if l.strip()]
    result["llama"] = "READY" if (lines and lines[0].strip().startswith('{"status"')) else (lines[0] if lines else "?")
    loaded = [l for l in lines[1:] if l.startswith("llama-server@")]
    result["loaded"] = loaded[0].replace("llama-server@", "").replace(".service", "") if loaded else "(未加载)"
    if not with_list:
        result["list"] = "(skipped)"
        return result
    ok2, out2 = ssh_run(st, "infer-list 2>/dev/null | head -30 || systemctl list-units 'llama-server@*' --no-legend 2>/dev/null")
    result["list"] = out2 if ok2 else "(infer-list 不可用)"
    return result


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
    # llama-rpc 双机类: 显式 --backend 单机后端(非 llama-rpc) 视为强制单机加载, 走正常路径
    if is_rpc:
        if backend and backend != "llama-rpc":
            station = station or DEFAULT_STATION
            print(f"[cluster] '{matched}' 为 RPC 双机类, --backend {backend} 视为强制单机加载 (退化为 {station} 站单机)。")
        else:
            print(f"[cluster] '{matched}' 为 llama-rpc 双机类模型, 超出单命令边界 (exit 2)。")
            print("  手动步骤:")
            print("  1) A 站: sudo systemctl start rpc-server        # 10.10.10.1:50052")
            print("  2) B 站: ssh scott-lau@scott-lau-GTR-Pro.local 'infer-load <完整别名>'")
            print("  3) 用毕: B 站 infer-unload (会顺带停 A 站 rpc-server)")
            return 2
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
