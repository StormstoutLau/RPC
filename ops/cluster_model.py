#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cluster_model — 模型元数据 / 量化 / 分组 / 别名（`cluster.py` 的拆分模块，阶段 1c）。

为什么存在：`cluster.py` 是单文件 5000+ 行；本模块是"模型域"的纯函数工具层。
拆分方案见 docs/2026-09-23_cluster.py模块化重构_调研与方案.md。

边界（改之前先读）：
  · 本模块**只放模型域的纯函数与常量**（不碰 ssh 之外的副作用）；集群级聚合
    （collect_*）与 `cmd_models` 等命令仍在 `cluster.py`。
  · `alias_of` / `group_by_model` / `resolve_quant` 是**单一定义点** —— CLI 与 Web 都从这里取，
    否则同一模型在两处会被算成不同别名/不同分组，进而查不到 conf 参数。
  · `cluster.py` 显式重导出全部符号，外部调用点（含 `cluster_web.py` 用到的
    `_MODEL_META_SCAN` / `alias_of` / `group_by_model` / `parse_model_meta` /
    `pick_representative` / `resolve_quant`）保持不变。
"""
import os
import re
from pathlib import Path

from cluster_ssh import ssh_run

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
# ⚠ 实测注意: BF16/F16/F32 与 Q\d 等分支**大小写敏感** ⇒ 小写 `bf16`/`f16` 不会被识别
#   （已由 tests/test_cluster_pure.py 的 BUG-PIN 钉住；本次拆分不改行为）。
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
