#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rpc 统一校验入口 (P0) —— 一条命令给结论。

被 `ops/rpc.ps1 check` 与 git hooks 调用。

设计铁律 (来自 docs/research/2026-09-14_暴露问题调研.md 的 CI/CD 分析):
  1. 断言清单化: 新增一条校验 = 往 CHECKS 加一条声明 + 写一个函数。
     目的: 避免"又一个脚本"式增长 —— 仓库现有 40+ 个手工校验脚本却没有总入口,
     而其中大部分从没被自动触发过。
  2. 退出码即门禁: 任一 FAIL -> exit 1, 供 pre-commit / pre-push 阻断。
  3. 结论先行: 先总表后明细; 跳过项、白名单项、不可达项都必须显式列出, 不做静默放行。

用法:
  python ops/rpc_check.py                  # 全量 (含三站配置比对)
  python ops/rpc_check.py --quick          # 仅本地快检 (pre-commit 用)
  python ops/rpc_check.py --only secrets,syntax
  python ops/rpc_check.py --list           # 只列断言清单
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── 断言 A1: 明文扫描 ─────────────────────────────────────────────
# 边界 (?<![A-Za-z0-9]) 用于排除 `task-2026...` 这类含 "sk-" 子串的误报。
SECRET_RE = re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}")

# 白名单: 需要"故意保留样串"的文件。每条必须写明原因, 且每次运行都会计数打印,
# 不允许变成静默放行。
SECRET_ALLOW = {
    "spec/d6-agent-standard/test-cards/sanitized.md":
        "脱敏器验收样串 (d6 CHECKLIST P1/A8b 判据要求此文件含样串)",
    "spec/d6-agent-standard/CHECKLIST.md":
        "文档正文引用 scrubber 正则与验收样串",
}


def _iter_source_files():
    """返回 (相对路径, 绝对路径) —— 以 git 跟踪文件为范围。

    范围选 git 跟踪文件而非"整个工作区": pre-commit 阶段新文件已 `git add`,
    故会出现在 ls-files 中; 而 tmp/ 等未跟踪目录不应参与提交门禁。
    """
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                             capture_output=True, check=True).stdout
        rels = [p for p in out.decode("utf-8", "replace").split("\0") if p]
    except Exception:
        rels = [str(p.relative_to(ROOT)).replace("\\", "/")
                for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]
    for r in rels:
        yield r, ROOT / r


def _is_binary(path):
    try:
        with open(path, "rb") as fh:
            return b"\x00" in fh.read(8192)
    except OSError:
        return True


def _read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _mask(s):
    return s[:8] + "…" if len(s) > 9 else s


def check_secrets(ctx):
    """扫描跟踪文件中的明文密钥形态。"""
    hits, allowed, scanned, skipped_bin = [], [], 0, 0
    for rel, path in _iter_source_files():
        if _is_binary(path):
            skipped_bin += 1
            continue
        text = _read_text(path)
        if "sk-" not in text:
            scanned += 1
            continue
        scanned += 1
        for i, line in enumerate(text.splitlines(), 1):
            for m in SECRET_RE.finditer(line):
                rec = (rel, i, _mask(m.group(0)))
                (allowed if rel in SECRET_ALLOW else hits).append(rec)
    detail = [f"{r}:{n}  {s}" for r, n, s in hits]
    for r, n, s in allowed:
        detail.append(f"(白名单) {r}:{n}  {s} —— {SECRET_ALLOW[r]}")
    note = f"扫描 {scanned} 个文本文件 (跳过 {skipped_bin} 个二进制), 命中 {len(hits)} 处"
    if allowed:
        note += f", 白名单 {len(allowed)} 处"
    return ("FAIL" if hits else "PASS"), note, detail


# ── 断言 A2: 语法检查 ─────────────────────────────────────────────
PS_SNIPPET = r"""
$files = @($input | Where-Object { $_ -and $_.Trim() -ne '' })
foreach ($f in $files) {
  $tok = $null; $errs = $null
  [System.Management.Automation.Language.Parser]::ParseFile($f, [ref]$tok, [ref]$errs) | Out-Null
  if ($errs -and $errs.Count -gt 0) {
    foreach ($e in $errs) { "FAIL`t$($e.Extent.StartLineNumber)`t$($e.Message)" }
  }
}
"""

SH_SNIPPET = ("while IFS= read -r f; do [ -z \"$f\" ] && continue; "
              "if ! out=$(bash -n \"$f\" 2>&1); then printf 'FAIL\\t1\\t%s\\n' \"$out\"; fi; "
              "done")


def _run_with_stdin(argv, files):
    try:
        p = subprocess.run(argv, input="\n".join(files), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", cwd=ROOT)
        return p.stdout
    except Exception as e:
        return f"FAIL\t1\t(无法执行 {argv[0]}: {type(e).__name__})"


def check_syntax(ctx):
    """py_compile / PowerShell AST / bash -n / JSON 解析。"""
    by_ext = {}
    for rel, path in _iter_source_files():
        ext = path.suffix.lower()
        if ext in (".py", ".ps1", ".sh", ".json"):
            by_ext.setdefault(ext, []).append((rel, path))

    detail, counts = [], {}

    # .py
    py_files = by_ext.get(".py", [])
    bad = 0
    with tempfile.TemporaryDirectory() as td:
        for rel, path in py_files:
            # 扩展名与内容不符: .py 却是别的解释器 (门禁首个真实收获即此类, 见 _bs1.py 案例)。
            # 直接报"应改扩展名或解包", 而不是抛一句看不懂的 SyntaxError。
            head = _read_text(path).splitlines()[:1]
            if head and head[0].startswith("#!") and "python" not in head[0]:
                bad += 1
                detail.append(f"{rel}  扩展名与内容不符: 首行 '{head[0].strip()}' "
                              f"→ 应解包为真 Python 或改为对应扩展名")
                continue
            cfile = os.path.join(td, rel.replace("/", "_") + "c")
            try:
                import py_compile
                py_compile.compile(str(path), cfile=cfile, doraise=True)
            except py_compile.PyCompileError as e:
                bad += 1
                detail.append(f"{rel}  {str(e).strip().splitlines()[-1][:160]}")
            except Exception as e:
                bad += 1
                detail.append(f"{rel}  {type(e).__name__}: {e}")
    counts[".py"] = (len(py_files), bad)

    # .ps1 —— 单次 PowerShell 调用处理全部文件 (避免逐文件起进程)
    ps_files = by_ext.get(".ps1", [])
    bad = 0
    if ps_files:
        exe = "powershell.exe"
        with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False,
                                         encoding="utf-8-sig") as fh:
            fh.write(PS_SNIPPET)
            tmp_ps = fh.name
        out = _run_with_stdin([exe, "-NoProfile", "-ExecutionPolicy", "Bypass",
                               "-File", tmp_ps], [str(p) for _, p in ps_files])
        try:
            os.unlink(tmp_ps)
        except OSError:
            pass
        for ln in out.splitlines():
            if ln.startswith("FAIL\t"):
                _, lineno, msg = ln.split("\t", 2)
                bad += 1
                detail.append(f"(ps1) {msg[:160]}  [line {lineno}]")
    counts[".ps1"] = (len(ps_files), bad)

    # .sh —— 单次 bash 调用
    sh_files = by_ext.get(".sh", [])
    bad = 0
    if sh_files:
        out = _run_with_stdin(["bash", "-c", SH_SNIPPET], [str(p) for _, p in sh_files])
        for ln in out.splitlines():
            if ln.startswith("FAIL\t"):
                _, _, msg = ln.split("\t", 2)
                bad += 1
                detail.append(f"(sh) {msg.strip()[:160]}")
    counts[".sh"] = (len(sh_files), bad)

    # .json —— 严格 JSON (跳过 .jsonc: 允许注释, 非标准 JSON)
    json_files = by_ext.get(".json", [])
    bad = 0
    for rel, path in json_files:
        try:
            json.loads(_read_text(path))
        except Exception as e:
            bad += 1
            detail.append(f"{rel}  {type(e).__name__}: {str(e)[:140]}")
    counts[".json"] = (len(json_files), bad)

    total_bad = sum(b for _, b in counts.values())
    note = " ".join(f"{ext}:{n}文件/{b}失败" for ext, (n, b) in sorted(counts.items()))
    return ("FAIL" if total_bad else "PASS"), note, detail


# ── 断言 A3: inventory 单点真值 (P1) ──────────────────────────────
# 目的: 阻止"改了这个忘了那个" —— 端口/模型标识变更时, 保证声明源与真值表一致。
#
# **对账模式, 不是文本扫描** (2026-09-14 实测修正, 详见文档 §11):
#   最初的设计是"扫描全仓库出现的端口/模型名, 未登记即 FAIL"。实测该方案不可行:
#     · 端口: 51 个"端口"里 19 个不是端口 (llama.cpp 提交号 9859、参数值 16384/4096/
#       1024、截断匹配 127/808...)。文本里的数字没有唯一语义。
#     · 模型: 以 gguf 结尾的强标识 114 个, 100% 是路径/文件名, 纯噪声。
#   改为只对**结构化声明源**做对账 —— 精确、零噪声、可长期维护:
#     (a) ops/cluster.py 的端口常量 (如 STATION_PORT) 与模型路由常量 (如 ROUTE)
#     (b) docs/三机推理集群使用手册.md 的端点表格行
#   声明源里出现而 inventory 未登记 => FAIL, 并提示"登记真值"或"修正过期引用"。
INVENTORY_DIR = ROOT / "inventory"
DECL_CLUSTER_PY = ROOT / "ops" / "cluster.py"
DECL_MANUAL = ROOT / "docs" / "三机推理集群使用手册.md"

CONST_DICT_RE = r"^(?P<name>%s[A-Z_]*)\s*=\s*\{(?P<body>[^}]*)\}"
PORT_CONST_RE = re.compile(CONST_DICT_RE % r"[A-Z_]*PORT", re.M)
MODEL_CONST_RE = re.compile(CONST_DICT_RE % r"(?:[A-Z_]*ROUTE[A-Z_]*)", re.M)
MANUAL_PORT_RE = re.compile(r"(?:[A-Za-z0-9._\-]+|\*)?:(\d{4,5})\b")


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


def _declared():
    """从声明源解析 (端口, 模型标识)。返回 ({port: [来源]}, {name: [来源]})。"""
    ports, models = {}, {}
    text = _read_text(DECL_CLUSTER_PY) if DECL_CLUSTER_PY.is_file() else ""
    for m in PORT_CONST_RE.finditer(text):
        for v in re.findall(r":\s*(\d{2,5})", m.group("body")):
            ports.setdefault(int(v), []).append(f"cluster.py:{m.group('name')}")
    for m in MODEL_CONST_RE.finditer(text):
        # STATION_ROUTES 是**派生表** (键 = 站上真实别名 + 站后缀, 值 = (站, 真实别名)),
        # 不逐条登记到 inventory —— 那会与基础别名重复, 且引入双份要同步的真值。
        # 它的正确性由 aliases 断言的 (7) 子项校验 (更强: 含站维度, 要求 (别名,站) 已声明 conf)。
        if m.group("name") == "STATION_ROUTES":
            continue
        for k in re.findall(r"[\"']([^\"']+)[\"']\s*:", m.group("body")):
            models.setdefault(k, []).append(f"cluster.py:{m.group('name')}")
    if DECL_MANUAL.is_file():
        for i, line in enumerate(_read_text(DECL_MANUAL).splitlines(), 1):
            if not line.startswith("|"):
                continue
            for m in MANUAL_PORT_RE.finditer(line):
                ports.setdefault(int(m.group(1)), []).append(f"手册:{i}")
    return ports, models


def check_inventory(ctx):
    ports, models = load_inventory()
    if ports is None:
        return "WARN", "未安装 pyyaml, 无法读取 inventory/ (断言跳过)", []
    if not ports and not models:
        return "FAIL", "inventory/ 为空 —— 该断言需要真值表才能工作", []

    decl_ports, decl_models = _declared()
    unk_ports = {v: loc for v, loc in decl_ports.items() if v not in ports}
    unk_models = {t: loc for t, loc in decl_models.items()
                  if t not in models and t.lower() not in {k.lower() for k in models}}

    # 真值表自身的完整性: managed 分组每条必须有 purpose
    incomplete = [f"{f}:{p.get('purpose', '(无 purpose)')}"
                  for p, f in ((v, v["_file"]) for v in ports.values() if v["_group"] == "managed")
                  if not p.get("purpose")]

    detail = []
    for v, loc in sorted(unk_ports.items()):
        detail.append(f"声明源用了未登记端口 {v}  ({', '.join(sorted(set(loc))[:3])}) —— "
                      f"是有效端口就在 inventory/ports.yaml 登记, 否则修正该引用")
    for t, loc in sorted(unk_models.items()):
        detail.append(f"声明源用了未登记模型标识 `{t}`  ({', '.join(sorted(set(loc))[:3])}) —— "
                      f"是有效别名就在 inventory/models.yaml 登记, 否则修正该引用")
    detail += [f"inventory 条目缺 purpose: {x}" for x in incomplete]

    note = (f"对账: 声明源 {len(decl_ports)} 端口 / {len(decl_models)} 模型标识 · "
            f"真值表 {len(ports)} 端口 / {len(models)} 模型键 · "
            f"未登记 {len(unk_ports)} / {len(unk_models)}")
    if unk_ports or unk_models or incomplete:
        return "FAIL", note, detail
    return "PASS", note, []


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
    snap = cluster.ROUTE
    try:
        cluster.ROUTE = {"__amb-a__": "A", "__amb-ab__": "B"}
        n += 1
        try:
            cluster.resolve_alias("__amb-a")
            detail.append("歧义输入未报错 (静默取首个候选 = 会误路由)")
        except cluster.AliasError:
            pass
    finally:
        cluster.ROUTE = snap

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
    declared_conf = set()
    for alias, meta in (models or {}).items():
        if alias != meta.get("alias") or meta.get("_group") == "non_model_conf":
            continue    # non_model_conf (如 rpc-nodes 读的 nodes.env) 不是可加载模型, 不该有按站路由名
        for st in (meta.get("conf") or []):
            declared_conf.add((str(alias), st))
    for name, (st, real) in sorted(cluster.STATION_ROUTES.items()):
        n += 1
        if (real, st) not in declared_conf:
            detail.append(f"按站路由名 {name!r} -> ({st}, {real!r}), 但 inventory/models.yaml "
                          f"未声明 {real} 在 {st} 站有 conf")
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

STATION_CMD = (
    "printf '\\n[cfg]\\n'; sha256sum " + " ".join(WATCHED) + " 2>/dev/null | cut -c1-16; "
    "printf '\\n[conf]\\n'; ls -1 /etc/llama-instances/*.env 2>/dev/null "
    "| xargs -r -n1 basename | sed 's/\\.env$//' | tr '\\n' ' '; echo; "
    "printf '\\n[bind]\\n'; ss -ltn 2>/dev/null | awk 'NR>1{print $4}' | tr '\\n' ' '; echo; "
    # UDP 侧单独一段 (P1-4): 系统里长期监听的 UDP 端口并不少 (nmbd/avahi/NetworkManager/
    # wsdd/netconsole/rpc.statd), 只查 TCP 会让它们对账时"看不见"。
    "printf '\\n[ubind]\\n'; ss -lun 2>/dev/null | awk 'NR>1{print $4}' | tr '\\n' ' '; echo; "
    "printf '\\n[mpath]\\n'; for f in /etc/llama-instances/*.env; do [ -e \"$f\" ] || continue; "
    "a=${f##*/}; a=${a%.env}; p=$(sed -n 's/^MODEL_PATH=//p' \"$f\" | head -1 | tr -d '\"'); "
    "if [ -z \"$p\" ]; then echo \"$a NO_MODEL_PATH\"; "
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
    "CK=$(cat ~/.config/rpc/claude.key 2>/dev/null | tr -d '\\n'); "
    "UK=$(cat ~/.config/rpc/unsloth.key 2>/dev/null | tr -d '\\n'); "
    "if [ -n \"$CK\" ] && [ \"$CK\" = \"$UK\" ]; then echo 'claudekey=SAME_AS_UNSLOTH'; "
    "else echo 'claudekey=DIFFERS'; fi"
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
    #     必须"引用得到、非空、可执行"; 以及 claude.key 是否与同站引擎 key 一致。
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
            elif line.startswith("claudekey=") and line.split("=", 1)[1] != "SAME_AS_UNSLOTH":
                warn.append(f"{st} 站 claude.key 与同站 unsloth.key 不一致 —— "
                            f"A/B 站二者相同 (claude 走本地 :8080, 用引擎 key); "
                            f"C 站是 15B 占位串 'sk-local-noauth…', 是否有意待确认")

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
        by_port = {}
        for g in ("managed", "third_party", "unmanaged"):
            for e in port_entries.get(g) or []:
                if isinstance(e, dict) and isinstance(e.get("port"), int):
                    by_port.setdefault(e["port"], []).append((g, e))

        def _reg_covers(port, side, st):
            """分配表是否已登记该 (端口, 协议侧, 站)。

            proto 语义: tcp/http/https → TCP 侧; udp → UDP 侧;
                        tcp+udp → 两侧 (mihomo 的 mixed / DNS 端口即双栈);
                        缺省 → 两侧都算 (unmanaged 里的系统端口多不关心协议侧)。
            """
            for g, e in by_port.get(port, []):
                if st not in _scopes(e):
                    continue
                p = str(e.get("proto") or "").lower()
                if p == "udp" and side != "udp":
                    continue
                if p in ("tcp", "http", "https") and side != "tcp":
                    continue
                return True                  # tcp+udp 与缺省都覆盖两侧
            return False

        def _listening(st, sec):
            out = set()
            for tok in (live[st].get(sec) or "").split():
                if ":" in tok:
                    p = tok.rpartition(":")[2]
                    if p.isdigit():
                        out.add(int(p))
            return out

        for st in reach:
            for side, sec in (("tcp", "bind"), ("udp", "ubind")):
                for port in sorted(_listening(st, sec)):
                    checked_ports += 1
                    if _reg_covers(port, side, st):
                        continue
                    if port >= EPHEMERAL_MIN:
                        ignored_eph += 1
                        continue
                    detail.append(f"{st} 站 {side.upper()} :{port} 有监听但分配表未登记 —— "
                                  f"是常驻服务就登记到 inventory/ports.yaml "
                                  f"(我方 = managed, 他方 = third_party/unmanaged)")
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

    if unreachable:
        info.insert(0, f"站点不可达 (未计入判定): {', '.join(unreachable)}")
    note = (f"可达 {len(reach)}/3 站 · 对账 cfg{len(WATCHED)}/ROUTE{len(cluster.ROUTE)}"
            f"/RPC{len(cluster.RPC_MODELS)}/conf{sum(len(v) for v in declared_conf.values())}"
            f"/bind{sum(1 for m in (ports_inv or {}).values() if m.get('expect_bind'))}"
            f"/port{checked_ports}(豁免临时段 {ignored_eph})"
            f"/weight{sum(1 for st in reach for _ in (live[st].get('mpath') or '').splitlines())}")
    if detail:
        return "FAIL", note, info + detail + [f"(WARN) {w}" for w in warn]
    if warn:
        return "WARN", note, info + warn
    return "PASS", note, []


# ── 断言清单 (加校验 = 在此加一条 + 写一个函数) ─────────────────────
CHECKS = [
    {"id": "secrets", "title": "明文扫描", "fn": check_secrets, "quick": True},
    {"id": "syntax", "title": "语法检查", "fn": check_syntax, "quick": True},
    {"id": "inventory", "title": "真值登记", "fn": check_inventory, "quick": True},
    {"id": "ports", "title": "端口分配表自洽", "fn": check_ports, "quick": True},
    {"id": "impact", "title": "影响面反查", "fn": check_impact, "quick": True},
    {"id": "aliases", "title": "别名解析契约", "fn": check_aliases, "quick": True},
    {"id": "stations", "title": "三站配置+占用一致", "fn": check_stations, "quick": False},
]


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--quick", action="store_true", help="仅本地快检 (pre-commit)")
    ap.add_argument("--only", default="", help="逗号分隔的断言 id")
    ap.add_argument("--list", action="store_true", help="只列断言清单")
    args = ap.parse_args()

    if args.list:
        for c in CHECKS:
            print(f"  {c['id']:10s} {c['title']:14s} quick={c['quick']}")
        return 0

    selected = CHECKS
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        selected = [c for c in CHECKS if c["id"] in want]
    elif args.quick:
        selected = [c for c in CHECKS if c["quick"]]

    mode = "quick" if args.quick else "全量"
    print(f"\nrpc check · 模式={mode} · {ROOT}\n")

    results, failures = [], 0
    for c in selected:
        try:
            status, note, detail = c["fn"]({})
        except Exception as e:
            status, note, detail = "FAIL", f"{type(e).__name__}: {e}", []
        results.append((c["id"], c["title"], status, note, detail))
        if status == "FAIL":
            failures += 1

    for cid, title, status, note, _ in results:
        print(f"  [{status:4s}] {cid:10s} {title:14s} {note}")

    skipped = [c["id"] for c in CHECKS if c not in selected]
    if skipped:
        print(f"\n  已跳过 (模式={mode}): {', '.join(skipped)}")

    for cid, title, status, note, detail in results:
        if status in ("FAIL", "WARN") and detail:
            print(f"\n  ── {cid} 明细 ──")
            for d in detail[:40]:
                print(f"    {d}")
            if len(detail) > 40:
                print(f"    … 另有 {len(detail) - 40} 条")

    if failures:
        print(f"\n  结论: FAIL ({failures} 项失败) → 阻断; 修复后重跑\n")
        return 1
    warn = sum(1 for r in results if r[2] == "WARN")
    print(f"\n  结论: PASS{'' if not warn else f' (含 {warn} 项 WARN)'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
