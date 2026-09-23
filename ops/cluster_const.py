#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cluster_const — 统一入口的**常量层**（`cluster.py` 的拆分模块）。

为什么存在：`cluster.py` 是单文件 5000+ 行；本模块是阶段 1a 抽出的第一刀（零耦合、纯声明）。
拆分方案见 docs/2026-09-23_cluster.py模块化重构_调研与方案.md。

约束（**改这里之前先读**）：
  · 本模块**只放声明**（常量表），不放逻辑 —— 逻辑进各自的功能模块。
  · `cluster.py` 以显式 `from cluster_const import (...)` 重导出这些名字，
    使 `cluster.STATIONS` / `cluster.ROUTE` 等**外部调用点保持不变**
    （`cluster_web.py` / `rpc_check.py` 依赖 `cluster.*` 命名空间）。
  · **不要**直接 `import cluster_const` 后到处用 —— 那会把"单一真值"裂成两处引用面。
"""
from pathlib import Path

# ── 常量层 ──────────────────────────────────────────────
STATIONS = {
    # 2026-09-16 (ADR-0006): A/B 由 `*.local` 名改为 **LAN IPv4** —— 与 C 站同一结论(见下行注释)。
    #   理由: Windows 解析 `*.local` 需 ~16-17s 且**只返回公网 IPv6**(2409:8a20:...) => 控制面经
    #   ISP IPv6 绕行而非走局域网; 实测按名 16.2s -> 按 LAN IPv4 0.18s (约 90x)。
    #   真值见 inventory/net.yaml 的 lan 段; 漂移会被门禁 stations 断言报 FAIL(不比"ssh 连不上"更难查)。
    "A": {"host": "192.168.1.33", "user": "scott-lau"},
    "B": {"host": "192.168.1.32", "user": "scott-lau"},
    "C": {"host": "192.168.1.37", "user": "scott-lau"},   # seaviv (2026-09-09 IP 修正: 原 192.168.1.24 过期; seaviv.local 可解析但保持 IPv4 规避 paramiko/IPv6)
}
# 各站引擎 /health 端口 (A/B/C 均 8080; 原 C=18080 为过时值)
STATION_PORT = {"A": 8080, "B": 8080, "C": 8080}
ROUTE = {"gpt-oss-120b": "A", "qwen3.8-27b-mtp": "C", "m27-q4ks": "C"}     # 其余一律 B (DEFAULT_STATION)
# 注: qwen3.8-flash-next 三站齐备 (2026-09-16) 但仍**保持默认 B** —— 不改既有路由行为;
# 要指定站用按站路由名 qwen3.8-flash-next-{a,b,c}。m27-q4ks 为新增, 默认归 C (源站/基线站)。
# ⚠ **别名必须以站上 infer-load 的 alias 空间为准** (`infer-list` 第一列), 不能照模型技术名自造:
#   MiniMax-M2.7 的站上规范别名是 `m27-q4ks` (infer-load 内有归一化 sed: minimax-m2.7.* -> m27-q4ks)。
#   2026-09-16 曾误用 `minimax-m2.7` 建 conf/路由 => `infer-load minimax-m2.7` 直接 "无匹配" (回归, 当日修正)。

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
    # 2026-09-16: minimax-m2.7 (站上别名 m27-q4ks) / qwen3.8-flash-next UD-IQ4_XS 三站齐备 (C 源 -> A/B 已同步)
    "qwen3.8-flash-next-a": ("A", "qwen3.8-flash-next"),
    "qwen3.8-flash-next-c": ("C", "qwen3.8-flash-next"),
    "m27-q4ks-a": ("A", "m27-q4ks"),
    "m27-q4ks-b": ("B", "m27-q4ks"),
    "m27-q4ks-c": ("C", "m27-q4ks"),
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
# LiteLLM 网关服务 :4000 已退役 (2026-09-13): ADR-0002 决策 C 后链路一律直连各站引擎端口。
# 2026-09-16: opencode provider 名统一为 `local`（三站实况仅 local + openrouter）；旧名 "cluster-litellm" 已不存在。
# 网关已无活依赖。故移除 LITELLM_BASE / KEY_FILE / read_key 及 status/e2e 对网关的硬依赖。
HTML_OUT = Path(__file__).parent / "cluster_status.html"
SSH_TIMEOUT = 8


PANELS = [
    ("Beszel 监控", "http://scott-lau-GTR-Pro.local:8090"),
    ("Cockpit B", "https://scott-lau-GTR-Pro.local:9095"),
    ("Cockpit A", "https://scott-lau-NEX.local:9095"),
    ("Cockpit C", "https://192.168.1.37:9095"),
]
