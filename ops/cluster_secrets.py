#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cluster_secrets — 凭据平面 (secrets / providers)（`cluster.py` 的拆分模块，阶段 2a）。

为什么存在：`cluster.py` 是单文件 5000+ 行；本模块收拢"凭据落点与一致性 / Provider 集合与漂移"
这一平面。拆分方案见 docs/2026-09-23_cluster.py模块化重构_调研与方案.md。

边界（改之前先读）：
  · 只做**凭据 / Provider 平面**；出站平面与 OpenRouter 额度借用不在本模块（见 cluster_egress.py）。
  · `_secrets_push` 是**跨模块依赖点**（cluster_egress 的额度借用会用到）⇒ 保持在本模块可导入。
  · ⚠ 本模块含明文凭据路径与脱敏规则（KEY_PAT / MASK_SED）—— 改动须同步 `secrets` 门禁断言的判据。
  · `cluster.py` 显式重导出全部符号，外部调用点（cluster_web.py 的 cluster.probe_secrets /
    cluster._secrets_verdict / cluster.probe_providers）与 cluster.py 内部调用点均不变。
"""
import hashlib
import json
import os
import re
import threading
from pathlib import Path

from cluster_const import STATIONS
from cluster_ssh import _connect, ssh_run

# ── 凭据平面 (secrets / providers) ─────────────────────
# 收敛约定 (2026-09-14 明文治理): 站内唯一落点 ~/.config/rpc/*.key (700/600),
# 配置侧用引用而非明文 —— opencode 走 {file:...}, claude code 走 apiKeyHelper。
RPC_DIR = "~/.config/rpc"
SECRETS_ROOT = Path(__file__).parent.parent / "secrets" / "stations"   # 主控正本
# "站内产物"型凭据 (2026-09-16): 真值在**站上**, 主控正本只是兜底。
#   unsloth.key = unsloth studio 每次加载重铸, 唯一写入方是站上 infer-load ⇒ 正本必然陈旧,
#   而 push 会用陈旧值**覆盖站上真 key**, 直接打断该站的 opencode/claude。
#   ⇒ push 对这类文件**默认拒绝覆盖**(除非 --force); 要收回站上真值用 `secrets pull`。
STATION_MINTED = {"unsloth.key"}
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
    "printf '\\n[helper]\\n'; grep -oE '\"apiKeyHelper\": *\"[^\"]*\"' " + CLD_CONF + " 2>/dev/null; "
    # [kv] "站内产物"型凭据的**归一化指纹** (去尾换行后 sha256 前 12 位) —— 供 status 判定
    # "站上 vs 主控正本"是否一致 (不一致 ⇒ push 会跳过, 需先 secrets pull)。
    # 只打指纹不打值: 巡检输出不应携带密钥材料。
    "printf '\\n[kv]\\n'; for n in " + " ".join(sorted(STATION_MINTED)) + "; do "
    "v=$(tr -d '\\n' < " + RPC_DIR + "/$n 2>/dev/null); "
    "[ -n \"$v\" ] && printf '%s %s\\n' \"$n\" \"$(printf '%s' \"$v\" | sha256sum | cut -c1-12)\"; done"
)


def probe_secrets(st: str) -> dict:
    """单站凭据落点探测。返回 {station, reachable, dir, perm, live, archive, refs, helper}。"""
    res = {"station": st, "reachable": False, "dir": [], "perm": [],
           "live": [], "archive": 0, "refs": [], "helper": "", "kv": {}}
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
        elif section == "kv":
            parts = s.split()
            if len(parts) == 2:
                res["kv"][parts[0]] = parts[1]
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


def _master_minted_fp(st: str, name: str):
    """主控正本里"站内产物"型凭据的**归一化指纹** (去换行后 sha256 前 12 位)。

    口径必须与站上探针 `[kv]` 完全一致, 否则比较会假阳/假阴。只算指纹不返回值。
    """
    p = SECRETS_ROOT / st / name
    if not p.is_file():
        return None
    v = p.read_bytes().replace(b"\n", b"").replace(b"\r", b"")
    if not v:
        return None
    return hashlib.sha256(v).hexdigest()[:12]


def cmd_secrets(action: str = "status", extra: list = None) -> int:
    extra = extra or []
    if action not in ("status", "scan", "push", "pull"):
        print(f"用法: cluster.py secrets {{status|scan|push [A|B|C] [--force]|pull [A|B|C]}}  (未知动作: {action})")
        return 1
    if action == "push":
        # 2026-09-21: 支持 `secrets push <A|B|C>` 单站下发(额度借用只需改一站); 位置参数可选。
        only = next((x for x in extra if x.upper() in STATIONS), None)
        return _secrets_push(force=("--force" in extra), only=only)
    if action == "pull":
        return _secrets_pull(extra[0] if extra else None)

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
            # 站内产物 vs 正本 (2026-09-16): 不一致时 push 会跳过该文件 (防覆盖真 key),
            # 这里把它显式报出来并给出下一步 —— 否则"push 看着成功却少下发一个"很难察觉。
            for name in sorted(STATION_MINTED):
                fp_r = (p.get("kv") or {}).get(name)
                fp_m = _master_minted_fp(st, name)
                if fp_r is None and fp_m is None:
                    continue
                if fp_r is None:
                    verdict = "站上缺失 (下一次 infer-load 会重建)"
                elif fp_m is None:
                    verdict = "正本缺失 (可 secrets pull 回写)"
                elif fp_r == fp_m:
                    verdict = "一致 ✓"
                else:
                    verdict = f"**不一致** —— push 会跳过该文件; 先回写: cluster.py secrets pull {st}"
                print(f"    站内产物 : {name} 站上={fp_r or '—'} 正本={fp_m or '—'}  {verdict}")
            loose = [f"{m} {n}" for m, n in p.get("perm", []) if m not in ("600", "700")]
            if loose:
                print(f"    权限告警 : {'; '.join(loose)}")
            print()
    if action == "scan":
        print(f"[secrets] 明文命中合计 {hits} 处 -> {'FAIL' if hits else 'PASS'}")
        return 1 if hits else 0
    return 0


def _remote_secret(st: str, name: str):
    """读站上 ~/.config/rpc/<name> 的**原始字节**; 不存在返回 None。仅用于"站内产物"型凭据。"""
    try:
        cli = _connect(st)          # 统一入口(勿在此处再 new SSHClient: 超时/策略会与 _connect 漂)
        sftp = cli.open_sftp()
        try:
            with sftp.open(f"/home/{STATIONS[st]['user']}/.config/rpc/{name}", "rb") as fh:
                data = fh.read()
        except Exception:
            data = None
        sftp.close(); cli.close()
        return data
    except Exception as e:
        print(f"[secrets] {st} 站读取 {name} 失败: {type(e).__name__}: {e}")
        return None


def _secrets_pull(only: str = None) -> int:
    """把"站内产物"型凭据从**站上取回**主控正本 (2026-09-16)。

    存在理由: `unsloth.key` 由 unsloth studio 每次加载重铸 ⇒ **站上才是真值**, 正本必然陈旧,
    而 `push` 若直接下发会用陈旧值**覆盖站上真 key**、打断该站 opencode/claude。正确顺序 =
    「先 pull 回写正本 → 再 push (此时幂等)」。把这一步做成入口动作, 而不是手工 scp。
    """
    sts = [only] if only in ("A", "B", "C") else ["A", "B", "C"]
    total = 0
    for st in sts:
        dst = SECRETS_ROOT / st
        if not dst.is_dir():
            print(f"[secrets] {st} 站: 跳过 (无正本目录 {dst})")
            continue
        written = []
        for name in sorted(STATION_MINTED):
            data = _remote_secret(st, name)
            if data is None:
                print(f"[secrets] {st} 站 {name}: 站上不存在 -> 跳过")
                continue
            cur = dst / name
            if cur.is_file() and cur.read_bytes().strip() == data.strip():
                print(f"[secrets] {st} 站 {name}: 已一致 -> 跳过")
                continue
            cur.write_bytes(data)
            written.append(name)
            total += 1
        if written:
            print(f"[secrets] {st} 站 回写正本 {len(written)} 个: {', '.join(written)}")
    print(f"[secrets] pull 完成, 共回写 {total} 个 (之后 push 才是幂等的)")
    return 0


def _secrets_push(force: bool = False, only: str = None) -> int:
    """从主控 secrets/stations/<st>/ 下发到各站 ~/.config/rpc/ (SFTP, 600 / 脚本 700)。

    `--force` 之外, "站内产物"型凭据 (STATION_MINTED) **站上已有且与正本不同则跳过** ——
    那种情况下站上才是真值, 覆盖会打断该站; 要收回真值用 `secrets pull`。
    `only`(2026-09-21 加, 与 `_secrets_pull(only)` 对称): 只下发单站 —— 额度借用只需改一站,
    全量下发会顺带触碰另两站(无谓的风险面)。
    """
    if not SECRETS_ROOT.is_dir():
        print(f"[secrets] 主控正本目录不存在: {SECRETS_ROOT}")
        return 1
    stations = (only.upper(),) if only else ("A", "B", "C")
    if only and only.upper() not in STATIONS:
        print(f"[secrets] 未知站: {only} (可选 A|B|C)")
        return 1
    total = 0
    for st in stations:
        src = SECRETS_ROOT / st
        if not src.is_dir():
            print(f"[secrets] {st} 站: 跳过 (无正本 {src})")
            continue
        try:
            cli = _connect(st)          # 统一入口(勿在此处再 new SSHClient: 超时/策略会与 _connect 漂)
            ssh_run(st, f"mkdir -p {RPC_DIR} && chmod 700 {RPC_DIR}")   # 复用 ssh_run 建目录
            sftp = cli.open_sftp()
            names = []
            skipped = []
            for f in sorted(src.iterdir()):
                if not f.is_file():
                    continue
                remote = f"/home/{STATIONS[st]['user']}/.config/rpc/{f.name}"
                # "站内产物"型凭据保护 (2026-09-16): 站上已有且与正本不同 ⇒ 站上才是真值, 跳过。
                if f.name in STATION_MINTED and not force:
                    try:
                        with sftp.open(remote, "rb") as fh:
                            cur = fh.read()
                    except Exception:
                        cur = None
                    if cur is not None and cur.strip() != f.read_bytes().strip():
                        skipped.append(f.name)
                        continue
                with sftp.open(remote, "w") as fh:
                    fh.write(f.read_bytes())
                sftp.chmod(remote, 0o700 if f.name.endswith(".sh") else 0o600)
                names.append(f.name)
                total += 1
            sftp.close(); cli.close()
            print(f"[secrets] {st} 站 下发 {len(names)} 个: {', '.join(names) if names else '(无)'}")
            if skipped:
                print(f"[secrets] {st} 站 **跳过** {len(skipped)} 个'站内产物'型凭据: {', '.join(skipped)}")
                print(f"[secrets]   ↑ 站上值 ≠ 正本(站上才是真值, 覆盖会打断该站 opencode/claude)。"
                      f"回写正本: cluster.py secrets pull {st} ; 强制覆盖: secrets push --force")
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
