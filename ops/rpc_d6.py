#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D6/D7 检查器：evidence / inbox / ps1-golden / ledger / review-catalog / memory-gates /
multi-round / interruption / rubric / mirror（review-p2-split 8B-2；整段搬出，行为不变）。"""
import argparse
import ast
import concurrent.futures
import fnmatch
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from rpc_common import (
    ADR_CANON, ADR_DIR, ADR_GLOB, ADR_LEGACY, AGENT_CLI, CHECKS, ROOT, SENSITIVITY_INV,
    SENSITIVITY_SECTIONS, SENSITIVITY_TIERS, _decode_out, _ds, _norm_head, _read_text, _s,
    allow_unhit, validate_adr,
)
from rpc_protocol import (
    PROJECTS_REG, d7_cli, projects_index, validate_projects,
)

# ── D6-P1-2 M-1：`事实源 ↔ 镜像` 一致性（当前 1 处合格镜像：判官行）─────────────────────
MANUAL = ROOT / "docs" / "三机推理集群使用手册.md"
AGENT_CLI = ROOT / "ops" / "station-bin" / "agent-cli.ps1"
# ★ 8C（2026-10-28）：`JUDGE_TABLE` 已搬进 `agent-cli-lib/10-tables.ps1` ⇒ 判据要读**定义处**。
#   ⚠ 只读 `agent-cli.ps1` 会报「读不出 JUDGE_TABLE['main']（表结构变了？）」—— 那是**假红**，
#     而更糟的形态是"读成 None 后静默通过"（本判据不静默，故它会喊）。
AGENT_CLI_TABLES = ROOT / "ops" / "station-bin" / "agent-cli-lib" / "10-tables.ps1"
# M-5/M-6: 受理状态机「单一真值」及其文档镜像
INBOX_TRUTH_YAML = ROOT / "inventory" / "inbox.yaml"
INBOX_README = ROOT / "inbox" / "README.md"


def agent_cli_sources_text():
    """入口 + 表库的拼接全文（8C 起表在 lib 里；夹具/判据/测试**同读这一份**）。"""
    out = []
    for p in (AGENT_CLI, AGENT_CLI_TABLES):
        if p.is_file():
            out.append(p.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(out)


def read_inbox_truth(path):
    """读受理状态机「单一真值」(`inventory/inbox.yaml` 的 `states:` 段) -> {state: {group, next}}。

    **纯函数**(只依赖传入路径): 便于单测与注入(正反用例)。
    失败**不静默兜底**(抛出) —— 由调用方报 FAIL / 由 check_inbox 落到空白名单(fail-closed)。
    """
    import yaml
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    states = data.get("states") if isinstance(data, dict) else None
    if not isinstance(states, dict):
        raise ValueError(f"{path} 缺 `states:` 映射段")
    return states


# 受理"必需件"键(requires)的封闭枚举 —— 与 inventory/inbox.yaml 的注释同步
INBOX_REQUIRES_KEYS = {"decide", "plan", "evidence", "manifest"}
# 看板徽章(badge)的封闭枚举 —— 与 inventory/inbox.yaml 同步 (cluster_web 注入前端)
INBOX_BADGE_VALUES = {"ok", "warn", "err", "none"}


def inbox_requires_sets(states, key):
    """**纯函数**: 从真值 `requires` 派生"需要某类件"的状态集。

    D6-P1-2 #7: check_inbox 原有 **4 处硬编码状态子集**, 现全部由真值派生(副本消失)。
    """
    return {s for s, sp in states.items() if key in ((sp or {}).get("requires") or [])}


def read_judge_main(text):
    """从 `agent-cli.ps1` 读 `JUDGE_TABLE['main']` 的三个契约字段（id / egress / compliance）。"""
    m = re.search(r"'main'\s*=\s*@\{([^}]*)\}", text)
    if not m:
        return None
    blob = m.group(1)

    def kv(key):
        mm = re.search(rf"{key}\s*=\s*([^;]+?)(?:\s*;|$)", blob)
        # `$false` ⇒ `false`：PS 的 `$` 前缀在手册里写作裸值，规范化后再比
        return mm.group(1).strip().strip("'\"") if mm else None
    return {k: (kv(k) or "").replace("$", "") for k in ("id", "egress", "compliance")}


def validate_mirror(judge, row):
    """**纯函数**：手册判官行 vs `JUDGE_TABLE['main']` —— 离线可正反夹测。

    P1-2 的定性（取证后大幅收窄）：原以为是"多组镜像"，实测**合格的只有 1 处** ——
    手册 §1.3 的判官行 vs `JUDGE_TABLE['main']`（**指向未来**：改一处而另一处不跟 ⇒ 运行时行为与文档不符）。
    其余（`ROUTE_TABLE`→手册 §2.2 / `ports.yaml`→手册 §1.2）已**显式豁免**（历史记档 / 精选视图）。
    ⚠ M-2（台账"剩余 open"↔手册"= 4 项"）**不在此断言内** —— 已由 **O-50** 裁定为"手册不再维护第二份枚举"
    ⇒ 加断言只会造一条**恒 WARN 的噪音**（对一个已决定不同步的数）。**这是分析结论，不是遗漏。**
    """
    bad = []
    if not judge:
        return ["agent-cli.ps1 里读不出 JUDGE_TABLE['main']（表结构变了？）"], {"n": 0}
    # ⚠ **每键的比对形态不同**（首版统一用 `k=v` ⇒ 对 `id` 造成**假红**：手册写的是
    #   `` `main-opencode-cli` ``（裸 id，无 `id=` 前缀）⇒ 判据必须尊重**各自自然的书写形态**，
    #   否则"判据本身在制造不一致"。egress/compliance 在手册里确实写作 `key=value`，故按该形态查。
    forms = (("id", lambda k, v: v in row),
             ("egress", lambda k, v: f"egress={v}" in row),
             ("compliance", lambda k, v: f"compliance={v}" in row))
    for k, hit in forms:
        v = judge.get(k)
        if not v:
            bad.append(f"JUDGE_TABLE['main'].{k} 读不出（值={v!r}）—— 事实源本身不可读")
        elif not hit(k, v):
            bad.append(f"手册 §1.3 判官行与事实源不一致：事实源 `{k}={v}`，"
                       f"但该串**未出现在**手册判官行里（改一处忘改另一处？）")
    return bad, {"n": 3}


def validate_inbox_mirror(states, readme_text):
    """**纯函数**: 受理状态机真值 ↔ README §3 白名单/状态表 + 真值自洽 (M-5/M-6)。

    收敛后(D6-P1-2)白名单/下一动作/分组都来自 `inventory/inbox.yaml` —— 两处代码**同源**,
    于是"两端白名单相等"退化为**恒真**(这就是假绿); **真正的漂移点是文档**:
    README §3 不能自动消费, 改了真值忘改文档不会报错。故此处补三道:
      · 真值自洽: 每态有 group ∈ {action,active,closed} + 非空 next
        (缺 group ⇒ 分组静默落进 closed = 真静默缺口; 缺 next ⇒ M-6 的键集缺口)
      · README §3「合法取值白名单」 == 真值键集 (= M-5 本体)
      · README §3 状态表首列 == 真值键集
    """
    bad = []
    for name, spec in sorted(states.items()):
        spec = spec or {}
        if spec.get("group") not in ("action", "active", "closed"):
            bad.append(f"inbox.yaml: 状态 {name!r} 的 group={spec.get('group')!r} 不合法 "
                       f"(须 ∈ action/active/closed; 缺省会静默落进 closed)")
        if not spec.get("next"):
            bad.append(f"inbox.yaml: 状态 {name!r} 缺 next (加了状态忘加下一动作 = M-6)")
        rq = spec.get("requires")
        if not isinstance(rq, list):
            bad.append(f"inbox.yaml: 状态 {name!r} 缺 requires 列表 "
                       f"(否则该态的『必需件』规则会**静默不适用**)")
        else:
            unk = sorted(set(rq) - INBOX_REQUIRES_KEYS)
            if unk:
                bad.append(f"inbox.yaml: 状态 {name!r} 的 requires 含未知键 {unk} "
                           f"(合法: {sorted(INBOX_REQUIRES_KEYS)})")
        if spec.get("badge") not in INBOX_BADGE_VALUES:
            bad.append(f"inbox.yaml: 状态 {name!r} 的 badge={spec.get('badge')!r} 不合法 "
                       f"(须 ∈ {sorted(INBOX_BADGE_VALUES)}; 前端徽章由它派生)")
    keys = set(states)
    # 只在 §3 段落内找白名单行/状态表(避免误抓别节里同形的表)
    sec = re.search(r"##\s*3\..*?(?=\n##\s)", readme_text, re.S)
    if not sec:
        bad.append("README 定位不到 §3 段落(标题结构改了?)")
    text = sec.group(0) if sec else readme_text
    m = re.search(r"合法取值白名单\*\*[:：]\s*(.+)", text)
    if not m:
        bad.append("README §3 找不到『合法取值白名单』行(文档结构改了?)")
    else:
        doc = set(re.findall(r"`([^`]+)`", m.group(1)))
        if doc != keys:
            bad.append(f"README §3 白名单与真值不一致: 文档多 {sorted(doc - keys)} / "
                       f"少 {sorted(keys - doc)} (改一处忘改另一处?)")
    tbl = set(re.findall(r"^\|\s*`([^`]+)`\s*\|", text, re.M))
    if tbl and tbl != keys:
        bad.append(f"README §3 状态表与真值不一致: 表多 {sorted(tbl - keys)} / "
                   f"少 {sorted(keys - tbl)}")
    return bad


def validate_manual_states(states, manual_text):
    """**纯函数**: 手册 §1.3 的「受理区位置 … 状态机」段必须**逐个提到**真值的每个状态 (#9)。

    D6-P1-2 #9: 手册是**对外契约母版**(Paper 项目 agent 据此写下游文档); 实测原图**漏了 `rejected`**
    (11/12 态)。此处只做 **⊇ 方向**(真值 ⊆ 手册) —— 手册与 README 图同族, 都是**主路径精选视图**,
    做"12 态全等"会**假红**(同 M-3 `ROUTE_TABLE` / M-4 ports 的豁免理由)。
    """
    m = re.search(r"受理区位置.*?受理流程与状态机见", manual_text, re.S)
    if not m:
        return ["手册 §1.3 定位不到『受理区位置 … 受理流程与状态机见』段(结构改了?)"]
    blk = m.group(0)
    miss = [s for s in sorted(states)
            if not re.search(rf"(?<![a-z\-]){re.escape(s)}(?![a-z\-])", blk)]
    if miss:
        return [f"手册 §1.3 状态机段漏了状态 {miss} (对外契约不全; 改真值后忘改手册?)"]
    return []


def validate_readme_requires(states, readme_text):
    """**纯函数**: README §5.3「交付态强判据」行 == 真值里 `requires` 含 `manifest` 的状态集。

    ⚠ 只钉**这一行**(它本就是精确枚举)。§5.3 其余用 `accepted+`/`release+` 的"+"记法是**有损人读摘要**,
    不做全等对账(会假红) —— 精确集由代码侧 `inbox_requires_sets` 从真值派生, 不靠文档。
    """
    want = inbox_requires_sets(states, "manifest")
    m = re.search(r"交付态强判据[^\n]*", readme_text)
    if not m:
        return ["README §5.3 找不到『交付态强判据』行(结构改了?)"]
    got = set(re.findall(r"`([^`]+)`", m.group(0)))
    if got != want:
        return [f"README §5.3『交付态强判据』行与真值不一致: 文档多 {sorted(got - want)} / "
                f"少 {sorted(want - got)}"]
    return []


# 手册 §2.4 的断言计数声明行（形如 `# 24 项断言 (quick 17 + 全量 7):`）
MANUAL_COUNT_RE = re.compile(r"#\s*(\d+)\s*项断言\s*\(quick\s*(\d+)\s*\+\s*全量\s*(\d+)\)")
# O-50：手册**不得**再长出"第二份枚举 / 写死计数" —— 这两类句式 = 同一事实两处定义
_MANUAL_BANNED = (
    (re.compile(r"真实剩余\s*open[^\n]{0,24}?=\s*[0-9]+\s*项"),
     "手册又出现『真实剩余 open = N 项』的**枚举式声明**（应指向 OPEN-ISSUES §1，别再抄一份）"),
    (re.compile(r"门禁\s*[0-9]+\s*绿"),
     "手册又**写死了门禁计数**（应指向 `rpc.ps1 check` 的当场自报）"),
)


def validate_manual_counts(manual_text, checks):
    """**纯函数**（O-50）：手册声明的断言计数 == 真实 `CHECKS`；并禁止第二份枚举/写死计数。

    为什么这样做（而不是像 M-2 那样对账"台账剩余项数"）：
      · **台账条数**每批都变 ⇒ 对账它只会造一条**恒 WARN 的噪音**（O-50 已判：手册**不再维护第二份枚举**）；
      · **断言项数**只在"加/删断言"时变，且**那时就该改手册** ⇒ 对账它是**精确、非噪音**的。
    ⇒ 把"手册计数会漂移"从空头承诺变成**机判**，同时用反向护栏堵住"再抄一份枚举"。
    """
    bad = []
    m = MANUAL_COUNT_RE.search(manual_text)
    if not m:
        bad.append("手册 §2.4 找不到『# N 项断言 (quick Q + 三站 S)』声明行（结构改了？）")
    else:
        n, q, s = (int(x) for x in m.groups())
        real = len(checks)
        rq = sum(1 for c in checks if c.get("quick"))
        rs = real - rq
        if (n, q, s) != (real, rq, rs):
            bad.append(f"手册声明的断言计数 ({n} = quick {q} + 三站 {s}) 与真实不符 "
                       f"(真实 {real} = quick {rq} + 三站 {rs}) ⇒ **加/删断言后忘了改手册 §2.4**")
        elif n != q + s:
            bad.append(f"手册计数**自相矛盾**: {n} ≠ quick {q} + 三站 {s}")
    for rx, why in _MANUAL_BANNED:
        mm = rx.search(manual_text)
        if mm:
            bad.append(f"{why}（命中 {mm.group(0)[:40]!r}）")
    return bad


def check_mirror(ctx):
    """P1-2: 事实源 ↔ 镜像 一致性 —— 2 处合格镜像(判官行 M-1 / 受理状态机 M-5+M-6+#7#9)。"""
    if not AGENT_CLI.exists() or not MANUAL.exists():
        return "WARN", "缺 agent-cli.ps1 或手册，跳过镜像断言", []
    bad = []
    manual_text = MANUAL.read_text(encoding="utf-8", errors="replace")
    # ── M-1: 手册 §1.3 判官行 ↔ `JUDGE_TABLE['main']`（8C 起表在 agent-cli-lib/10-tables.ps1）──
    judge = read_judge_main(agent_cli_sources_text())
    row = next((l for l in manual_text.splitlines() if "JUDGE_TABLE['main']" in l), "")
    if not row:
        bad.append("手册 §1.3 里找不到判官行（`JUDGE_TABLE['main']` 那行）")
    else:
        bad += validate_mirror(judge, row)[0]
    # ── O-50: 手册的断言计数 == CHECKS（+ 禁"第二份枚举/写死计数"）─────────
    bad += validate_manual_counts(manual_text, CHECKS)
    # ── M-5/M-6 + #7/#9: 受理状态机真值 ↔ README §3 / 手册 §1.3 + 两处代码同源 ──
    n_state = 0
    if not INBOX_TRUTH_YAML.exists() or not INBOX_README.exists():
        bad.append("缺 inventory/inbox.yaml 或 inbox/README.md（状态机真值 / 文档镜像不在）")
    else:
        try:
            states = read_inbox_truth(INBOX_TRUTH_YAML)
        except Exception as e:
            bad.append(f"inventory/inbox.yaml 读不出（真值源坏了）: {e}")
        else:
            n_state = len(states)
            readme_text = INBOX_README.read_text(encoding="utf-8", errors="replace")
            bad += validate_inbox_mirror(states, readme_text)
            bad += validate_readme_requires(states, readme_text)
            bad += validate_manual_states(states, manual_text)
            # 两处代码**消费同一真值**(防"回归硬编码"): 直接核对运行时集合
            sys.path.insert(0, str(ROOT / "ops"))
            try:
                import cluster_web
                for nm, got in (("cluster_web.INBOX_STATES", set(cluster_web.INBOX_STATES)),
                                ("cluster_web._INBOX_NEXT", set(cluster_web._INBOX_NEXT))):
                    if got != set(states):
                        bad.append(f"{nm} 与真值不一致: 多 {sorted(got - set(states))} / "
                                   f"少 {sorted(set(states) - got)}（回归硬编码?）")
            except Exception as e:
                bad.append(f"导入 cluster_web 失败, 无法核对状态机消费面: {e}")
    j = judge or {}
    note = (f"合格镜像 2 处（判官行 3 字段 + 受理状态机 {n_state} 态 ↔ README §3/手册 §1.3/两处代码"
            f"+ 手册断言计数 ↔ CHECKS）· 事实源 id={j.get('id')} "
            f"egress={j.get('egress')} compliance={j.get('compliance')}")
    return ("FAIL" if bad else "PASS"), note, bad


# ── 断言: agent 证据链 (2026-09-17, spec/d6-agent-standard/evidence-chain/) ──
# 为什么门禁要管: 证据链的价值在**被日常撞见** —— 只靠"人工想起跑 agent verify",
#   归档被改动可以长期无人察觉(与本仓"判据必须自证不静默降级"同一纪律)。
# 严重度**刻意分开**(要紧):
#   · verify 报 issues (digest_mismatch / chain_break / cold_mismatch / anchor_mismatch /
#     run_dir_missing / recipe_mismatch) = **证据被改或链被重写** ⇒ FAIL。
#   · "有 run 未入链" = **覆盖缺口, 不是篡改** ⇒ WARN。否则每次派发后提交都被阻断,
#     这类判据会因噪声被整体忽略(doclinks "判不准的不进门禁" 同一条理由)。
def check_evidence(ctx):
    sys.path.insert(0, str(ROOT / "ops"))
    try:
        import cluster
    except Exception as e:
        return "WARN", f"cluster.py 无法导入 ({type(e).__name__}) — 证据链断言跳过", []
    try:
        r = cluster.agent_chain_verify()
    except Exception as e:
        return "FAIL", f"证据链复验异常: {type(e).__name__}: {e}", []
    if r.get("note"):
        return "WARN", f"证据链不可用: {r['note']}", []
    issues = r.get("issues") or []
    un = r.get("unchained") or []
    gaps = r.get("gaps") or []
    notes = r.get("notes") or []
    details = []
    for x in issues:
        k, loc = x.get("kind"), f"{x.get('proj')}/{x.get('run_id')}"
        if k == "digest_mismatch":
            details.append(f"[{x['index']}] {loc} digest 不符, 变了: "
                           f"{', '.join(x.get('files_changed') or []) or '(未知)'}")
        elif k == "chain_break":
            details.append(f"[{x['index']}] {loc} prev 链不闭合 (此条起不可信)")
        elif k == "run_dir_missing":
            details.append(f"[{x['index']}] {loc} 归档目录不在了")
        elif k == "recipe_unknown":
            details.append(f"[{x['index']}] {loc} recipe **不可验** (链={x.get('got')} 本工具知 "
                           f"{x.get('expect')}) —— 工具比链旧, 不得当作通过")
        elif k in ("verdict_mismatch", "golden_identity", "manifest_missing", "manifest_undeclared"):
            details.append(f"[{x.get('index')}] {x.get('detail')}")
        elif k == "anchor_mismatch":
            details.append(f"外部锚与链不符: {', '.join(x.get('diff') or []) or '(未列出)'}")
        elif k == "anchor_unreadable":
            details.append("外部锚不可读 archive/evidence-chain/ANCHOR.txt")
        elif k == "cold_mismatch":
            details.append(f"冷路径与链不符 (冷={x.get('cold_n')} 链={x.get('chain_n')})")
        else:
            details.append(str(x))
    cov = " · ".join(c.split(":")[0] + " " + c.split(":")[1].split("可判")[0].strip()
                     for c in (r.get("coverage") or []) if ":" in c)
    note = (f"证据链: {r.get('entries', 0)} 条 · 未入链 {len(un)} · "
            f"锚{'在' if r.get('anchor_present') else '缺'}" + (f" · {cov}" if cov else ""))
    # ── 增量审计（ADR-0007 路A，2026-09-18）: 只报**新增**可重放性缺口 ─────────────
    # 与上面 verify 的分工（**严格按 D4 三层，不许混**）:
    #   · verify 的 issues = 篡改/损坏 ⇒ **FAIL**
    #   · verify 的 gaps / 未入链 / 缺锚 = **覆盖缺口** ⇒ **WARN**
    #   · 本段 = **可重放性**缺口，同属"**没验到**"⇒ **只 WARN，不进 FAIL 集**
    #     （D4 原文: 属"没验到"不是"验出问题"; 报 FAIL 会让判据**因噪声被整体忽略**）
    # 增量水印（K1/K2）: 用**归一 key** 与基线比对 ⇒ 存量 52 条不刷屏、新增必被抓。
    #   基线由**显式命令** `cluster.py agent audit --accept` 推进 —— **门禁只读、不自己写**
    #   （本文件对仓库全程只读，唯一写动作是 check_syntax 的 tempfile; 门禁挂 pre-commit,
    #    自己写就会把工作区弄脏）。副作用刻意接受: "接受新缺口"是人的显式动作, 不静默抹平。
    try:
        ra = cluster.agent_audit(limit=0)
    except Exception as e:
        # ⚠ 这里**刻意 FAIL 而非 WARN**: `import cluster` 失败是**环境**问题(缺 paramiko),
        #   而 `agent_audit` 抛异常是**本仓自己的 bug** —— 2026-09-18 的 Py3.11 语法事故正是
        #   被上面的 `except Exception` 静默降级成 WARN ⇒ **判据消失而门禁照绿**。两者必须分开。
        return "FAIL", f"可重放性审计异常: {type(e).__name__}: {e}", details
    _base = cluster.agent_audit_baseline_load()
    _bkeys = set(_base.get("keys") or [])
    _cur = set(ra.get("gap_keys") or [])
    _pending = sorted(_cur - _bkeys)
    _gtext = {it["key"]: it["text"] for it in (ra.get("gap_items") or [])}
    note += (f" · 可重放 gap {len(_cur)} 条(存量 {len(_cur & _bkeys)}"
             + (f", **新增 {len(_pending)}**" if _pending else "") + ")")
    # 2026-09-23 (O-29 的 2c): **按框架代分桶** —— 判据演化后历史 gap 与新 gap 混在一起，
    #   "新增"会看起来永远清不完（本轮实测：改完判据仍报 3 条，我一度误判为"没修好"）。
    #   key 形状 `<fwver>|<kind>|<label>|<sub>`（**旧形状 3 段 ⇒ 记 legacy**）。
    #   真值源: `cluster.FRAMEWORK_SUBJECTS_VERSION`（与 `_gap_key` 同源，不另立常量）。
    def _fwv(_k: str) -> str:
        return _k.split("|", 1)[0] if _k.count("|") >= 3 else "legacy"
    _bk = {}
    for _k in _cur:
        _bk[_fwv(_k)] = _bk.get(_fwv(_k), 0) + 1
    if _bk:
        _curv = getattr(cluster, "FRAMEWORK_SUBJECTS_VERSION", None)
        _nc = _bk.get(_curv, 0)
        note += f" · 按框架代分桶: current({_curv})={_nc} · legacy={len(_cur) - _nc}"
    if _pending:
        details.append(
            f"**可重放性审计: 新增 {len(_pending)} 条** gap"
            f"（存量 {len(_cur & _bkeys)} 条已接受、不再重复报；逐条如下）"
            f" ⇒ 确认可接受后跑 `python ops/cluster.py agent audit --accept` 推进水印")
        for _k in _pending[:8]:
            details.append(f"    · {_gtext.get(_k, _k)}")
        if len(_pending) > 8:
            details.append(f"    · …另有 {len(_pending) - 8} 条（`cluster.py agent audit` 看全表）")

    # ── 校准可判（2026-09-18 闭环复核；D4 归类: 覆盖缺口 ⇒ **只 WARN，不阻断**）──────────
    # "改判据必须重跑校准"此前是**空头承诺** —— 校准报告不记判据文本/题集 ⇒ 改了没重跑无人能发现。
    # 本仓自己的纪律原文: "只写规则不绑定执行等于空头承诺, 故做成断言"。指纹机制之后它可判了:
    #   报告指纹 ≠ 当前"判据(A/B) + 稳定题集" ⇒ 报过期。
    # ⚠ 旧报告（生成于指纹机制之前，无 calib 字段）**不当作过期**, 只提示 —— 否则一上线就对历史假告警。
    try:
        _cs = cluster.agent_audit_calib_status()
        note += f" · 校准 {_cs.get('state', '?')}"
    except Exception as e:
        _cs = {"state": "no-report"}
        details.append(f"(info) 校准状态不可判: {type(e).__name__}: {e}")
    _calib_stale = (_cs.get("state") == "stale")
    if _calib_stale:
        details.append(
            f"**judge 校准已过期**（{_cs['file']} 指纹 {_cs['recorded'][:16]}… ≠ 当前 "
            f"{_cs['current'][:16]}…）—— 判据或稳定题集已改、报告没重跑 ⇒ 跑 "
            f"`python ops/cluster.py agent audit-judge --save`（需站上在服务**跨家族**引擎）")

    if issues:
        return "FAIL", note, details
    if gaps or _pending or _calib_stale or not r.get("anchor_present"):
        if not r.get("anchor_present"):
            details.append("外部锚未建立 → `cluster.py agent chain` 生成, 提交并 push 到 origin")
        for g in gaps[:6]:
            details.append(g)
        if len(gaps) > 6:
            details.append(f"…另有 {len(gaps) - 6} 项覆盖缺口/不可判 (见 `cluster.py agent verify`)")
        return "WARN", note, details
    for nt in notes[:3]:
        details.append(f"(info, 不告警) {nt}")
    return "PASS", note, details


# ── 断言: inbox 受理区状态自洽 (P1, quick) ──────────────────────────
# 目的: 阻止受理区目录与状态机漂移 —— 每个 <proj>-<yyyy-mm-dd>/ 必须满足
#   ① 有 00_handoff/ (需求方原件冻结区)
#   ② 40_state/STATE.json 存在、可解析、state ∈ 白名单
#   ③ 状态内容自洽 (accepted+ 须有 受理决定.md; plan-review/plan-revise 须有 20_plan;
#      release+ 须有 30_evidence 记录)
# 依据: ADR-0008 + inbox/README §3 状态机 (2026-09-23 扩展: waiting/协商回环/验收签收)
# D6-P1-2 M-5/M-6: 白名单**已收敛**到 inventory/inbox.yaml —— 由 check_mirror 对账(README §3 + 两处代码)
INBOX_DIR = ROOT / "inbox"
try:
    _INBOX_TRUTH = read_inbox_truth(INBOX_TRUTH_YAML)
except Exception:
    # fail-closed: 真值不可读 => 白名单为空 => 任何 STATE 都 FAIL;
    # 真正的报错点见 check_mirror(它会点名「inbox.yaml 读不出」)
    _INBOX_TRUTH = {}
INBOX_STATES = set(_INBOX_TRUTH)
INBOX_PROJ_RE = re.compile(r"^[^_].+-\d{4}-\d{2}-\d{2}$")   # <proj>-<yyyy-mm-dd>, 排除 _template


def check_inbox(ctx):
    """受理区状态自洽: 目录结构 + STATE.json 合法 + 状态内容自洽。"""
    n_dir = n_state = n_bad = n_mf_skip = 0
    bad = []
    if not INBOX_DIR.is_dir():
        return "PASS", "inbox/ 不存在, 跳过", []
    # 必需件状态集: 由真值 requires 派生 (D6-P1-2 #7: 原为 4 处硬编码子集, 已收敛到一处)
    need = {k: inbox_requires_sets(_INBOX_TRUTH, k) for k in INBOX_REQUIRES_KEYS}
    for d in sorted(p for p in INBOX_DIR.iterdir() if p.is_dir()):
        name = d.name
        if name.startswith("_") or not INBOX_PROJ_RE.match(name):
            continue
        n_dir += 1
        # ① 必须有 00_handoff/ (需求方原件冻结区)
        if not (d / "00_handoff").is_dir():
            n_bad += 1
            bad.append(f"{name}: 缺 00_handoff/ (需求方原件冻结区)")
            continue
        # ② STATE.json 存在且可解析, state ∈ 白名单
        state_file = d / "40_state" / "STATE.json"
        if not state_file.is_file():
            n_bad += 1
            bad.append(f"{name}: 缺 40_state/STATE.json (状态必须可机读)")
            continue
        try:
            state = json.loads(state_file.read_text(encoding="utf-8")).get("state")
        except Exception:
            n_bad += 1
            bad.append(f"{name}: STATE.json 不是合法 JSON")
            continue
        n_state += 1
        if state not in INBOX_STATES:
            n_bad += 1
            bad.append(f"{name}: STATE={state!r} 不在白名单 ({', '.join(sorted(INBOX_STATES))})")
            continue

        def _nonempty(p):
            """目录存在且至少有一个非 .gitkeep 文件。"""
            return p.is_dir() and any(x.is_file() and x.name != ".gitkeep" for x in p.iterdir())

        # ③ 状态内容自洽 (必需件集由真值 requires 派生 —— 见 inventory/inbox.yaml)
        if state in need["decide"]:
            if not (d / "10_admin" / "受理决定.md").is_file():
                n_bad += 1
                bad.append(f"{name}: STATE={state} 须有 10_admin/受理决定.md (受理通过依据)")
        if state in need["plan"]:
            if not _nonempty(d / "20_plan"):
                n_bad += 1
                bad.append(f"{name}: STATE={state} 须有 20_plan/ 派发计划 (非空)")
        if state in need["evidence"]:
            if not _nonempty(d / "30_evidence"):
                n_bad += 1
                bad.append(f"{name}: STATE={state} 须有 30_evidence/ 证据束记录 (非空)")
        # 2026-09-23 收紧: **交付态**必须真的钉死证据束，不能只是"目录非空"。
        #   为什么收紧: 原判据放个无关文件就能过 ⇒ "未附证据束不 done" 形同虚设（空转的软约束）。
        #   判据 = 30_evidence/MANIFEST.sha256 存在。
        #   `rejected-by-requester`(可能交付前就终止) 本态 requires 无 `manifest` ⇒ 不进本集。
        if state in need["manifest"]:
            if not (d / "30_evidence" / "MANIFEST.sha256").is_file():
                n_bad += 1
                bad.append(f"{name}: STATE={state} 须有 30_evidence/MANIFEST.sha256 (交付证据束未钉死); "
                           f"生成: cluster.py inbox seal {name} --go")

        # ④ 交付证据束 **freshness**（D6-P1-1 §11.1-C 纪律 2/3）：只要有 MANIFEST 就**重算 → 比对**
        #   ⇒ 把"生成物**禁手改**"从空头承诺变成**机判**（改源头没重跑 / 手改清单 ⇒ 当场对不上）。
        #   项目根取自 **MANIFEST 头注释**（自包含，换 clone 也能判）；根**不在本机** ⇒ **跳过并报数**
        #   （那是可移植性问题，不是"被手改" ⇒ 不 FAIL，但必须可见）。判据实现与 CLI `--check` **同一个**。
        mf = d / "30_evidence" / "MANIFEST.sha256"
        if mf.is_file():
            try:
                import cluster as _cluster
                mroot, _mok, _mmiss, mbad = _cluster.verify_manifest(mf.read_text(encoding="utf-8"))
            except Exception as e:
                n_bad += 1
                bad.append(f"{name}: MANIFEST 校验无法执行（导入/读取失败）: {type(e).__name__}: {e}")
            else:
                if mroot and not Path(mroot).is_dir():
                    n_mf_skip += 1
                elif mbad:
                    n_bad += 1
                    _shown = "、".join(x.split(":", 1)[0] for x in mbad[:3])
                    bad.append(f"{name}: MANIFEST.sha256 **重算不符 {len(mbad)} 条** ⇒ 证据束被手改或源被改动"
                               f"（如 {_shown}）；核对: cluster.py inbox seal {name} --check")

    note = f"受理目录 {n_dir} · 状态可机读 {n_state} · 违规 {n_bad}"
    if n_mf_skip:
        note += f" · MANIFEST 未校验 {n_mf_skip}（项目根不在本机）"
    return ("FAIL" if n_bad else "PASS"), note, bad


# ── 断言: agent-cli.ps1 离线黄金夹具接线 (D6-P3-2) ────────────────────
# 为什么: `ops/station-bin/_fm_golden_test.ps1` 是一份**离线单测**（用 AST 从 `agent-cli.ps1` 提取**真函数**
#   + **真 `ROUTE_TABLE` / `JUDGE_TABLE`**，185 条断言），覆盖出站硬闸与判定面：
#   `Get-SensitivityBackendReject`（`local-only × 出网 ⇒ REJECT`，**唯一规则**）、`Get-BackendEgress`
#   （fail-closed：只有 `local/<flavor>` 不出网）、`Get-JudgeEgress` / `Get-JudgeComplianceReject`、
#   `Test-EvmStatePull`、`Get-FrameworkSubjects` … 共 20+ 纯函数。
# ⚠ **它此前只靠"人记着跑"**（多份文档称其为铁律）⇒ **不在 `CHECKS` 里** ⇒ 两次重构后**无人发现**
#   夹具期望值已陈旧：① 模块化把 paramiko 下沉到 `cluster_ssh.py`（旧目标恒 `SSHClient=0`）；
#   ② O-29 把 `golden-cmd` 从裸列改成条件列（基线 11→10）⇒ **实测 179 pass / 6 fail**（2026-09-25）。
# ⇒ 本断言把它**接进统一门禁**：退出码 0 = PASS；非 0 ⇒ FAIL 并把尾部 + FAIL 行贴进明细。
#   **判据在夹具里，本断言只负责"让它每次都被跑"**（判据本体不复制，避免第二份实现）。
# ✅ **quick**：实测夹具整体 ≈ **1.9s**（一次 pwsh 启动 + 185 条断言 + 一次 python AST 探测）
#   ⇒ 放进 `--quick`，**由 pre-commit 钩子强制**（否则仍只是"跑全量才判"，等于没接线）。
# ⚠ 定义必须在本行**之前**（`CHECKS` 在模块级求值）。
PS1_GOLDEN = ROOT / "ops" / "station-bin" / "_fm_golden_test.ps1"
# O-63 (2026-09-25): 取号并发夹具 —— 与黄金夹具**分开**成一项，且 `quick:False`：
#   它要起 8 个 **独立进程** + 两次共同释放时刻(各 2.5s) ⇒ 约 6s；塞进 quick 会让 pre-commit 明显变慢。
#   但**必须接进 CHECKS** —— 否则就是本仓反复点名的"有测试 ≠ 有人在跑"。
PS1_RUNSTAMP = ROOT / "ops" / "station-bin" / "_runstamp_hammer.ps1"
# O-64 (2026-09-25): Python 测试的**统一入口**。此前它**不在 CHECKS 里** ⇒ 无任何机械执行者 ⇒
#   实测被两轮提交（59d97c3 / fd96a89）穿透：O-62/O-63 改实现后 `test_cli_concurrency_guards.py`
#   当场红两条，**没有任何钩子出声**。这正是本仓点名的"有测试 ≠ 有人在跑"。
# 为什么 `quick:False`（实测值，与 ps1-runstamp 同一决策依据）：本入口 **12.2s**，而 quick 门禁本体 18.4s
#   ⇒ 塞进 quick 会让 pre-commit 从 ~18s 涨到 ~31s（+66%）。**非 quick 仍能兜住**：pre-push 跑全量
#   ⇒ 红状态**推不出去**。若将来想让它更早暴露，把 CHECKS 里那项改成 quick=True 即可（一行）。
PY_TESTS = ROOT / "tests" / "run_py_tests.py"


def _decode_out(b: bytes) -> str:
    """PS 5.1 重定向时的输出编码随控制台（zh-CN 常见 cp936）⇒ 先 utf-8 再 cp936，最后兜底替换。"""
    for enc in ("utf-8", "cp936"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", "replace")


def check_ps1_runstamp(ctx):
    """O-63: 跑 `_runstamp_hammer.ps1`（ts **取号**的跨进程并发夹具）—— **退出码 0 才算过**。

    它守的是"两个并发派发拿到同一个 ts ⇒ 共用 scratch/runDir ⇒ 证据面混且归属不可复原"这条
    **不可回改**的失败（实测 2026-09-25）。夹具自带**双向**：正向（新实现 8 进程全不同 ts）+
    负向（**同一把锤子**打旧实现 ⇒ 必须检出撞车）⇒ **必须两行都在**才算过，否则"跑空了"也会通过。
    """
    if not PS1_RUNSTAMP.is_file():
        return "WARN", f"{PS1_RUNSTAMP.name} 不存在（本断言的登记依据）", []
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PS1_RUNSTAMP),
             "-N", "8", "-SelfTest"],
            cwd=ROOT, capture_output=True, timeout=180)
    except FileNotFoundError:
        return "WARN", "本机无 powershell ⇒ 跳过（夹具只能在 Windows 侧跑）", []
    except subprocess.TimeoutExpired:
        return "FAIL", "取号夹具超时（>180s）⇒ 可能挂死", []
    out = _decode_out(p.stdout or b"") + _decode_out(p.stderr or b"")
    lines = [ln.rstrip() for ln in out.splitlines() if ln.strip()]
    pos = next((ln for ln in lines if ln.startswith("RUNSTAMP_HAMMER ")), "")
    neg = next((ln for ln in lines if ln.startswith("RUNSTAMP_HAMMER_SELFTEST")), "")
    ok = bool(pos and "PASS" in pos) and bool(neg and "PASS" in neg) and p.returncode == 0
    note = f"取号并发夹具：{pos or '（无正向汇总行）'} · {neg or '（无负向汇总行）'}"
    if p.returncode != 0 and ok:
        note += f" · 退出码 {p.returncode}"
    # ⚠ 缺任一汇总行 ⇒ **直接 FAIL**（"什么都没跑"不得算过 —— 本仓"假绿"头号形态）
    detail = lines[-8:]
    return ("PASS" if ok else "FAIL"), note, detail


def check_py_tests(ctx):
    """O-64 (2026-09-25): 跑 `tests/run_py_tests.py`（`tests/` 下全部独立测试的统一入口）。

    为什么需要本断言：该入口此前**不在 CHECKS 里** ⇒ **无任何机械执行者** ⇒ 实测被两轮提交穿透
    （O-62/O-63 改实现后 `test_cli_concurrency_guards.py` 当场红两条，无钩子出声）。
    ★ 判据 = **退出码 0 ∧ 解析到汇总行 ∧ 通过数 == 总数 ∧ 总数 > 0**，四者缺一即 FAIL。
      为什么不能只看"跑起来了"：`总数 == 0`（例如入口被改坏、discover 返回空）或"什么都没判"
      都会通过 ⇒ 又落进本仓头号形态（**假绿**）。入口自身也已在"未发现测试"时退 1，这里是双保险。
    ⚠ 解释器用 **`sys.executable`**（= 门禁自身的解释器）—— 依据 O-36：换解释器会**静默少跑 4 个套件**
      （PATH 上的 `python` 与钩子用的 `py.exe` 是不同环境）。用 `sys.executable` 从构造上杜绝该漂移。
    """
    if not PY_TESTS.is_file():
        return "WARN", f"{PY_TESTS} 不存在（本断言的登记依据）", []
    try:
        p = subprocess.run([sys.executable, str(PY_TESTS)], cwd=ROOT,
                           capture_output=True, timeout=420)
    except subprocess.TimeoutExpired:
        return "FAIL", "Python 测试套件超时（>420s）⇒ 可能挂死", []
    out = _decode_out(p.stdout or b"") + _decode_out(p.stderr or b"")
    lines = [ln.rstrip() for ln in out.splitlines() if ln.strip()]
    m = re.search(r"结果:\s*(\d+)/(\d+)\s*通过", out)
    n_pass, n_tot = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    bad = next((ln for ln in lines if ln.startswith("失败:")), "")
    ok = bool(m) and n_tot > 0 and n_pass == n_tot and p.returncode == 0
    note = f"Python 测试套件: {n_pass}/{n_tot} 通过"
    if bad:
        note += f" · {bad}"
    if not m:
        note += " · ⚠ 未解析到汇总行（入口可能被改坏）"
    detail = [ln for ln in lines if "PASS" in ln or "FAIL" in ln][-15:]
    return ("PASS" if ok else "FAIL"), note, detail


def check_ps1_golden(ctx):
    """P3-2: 跑 `_fm_golden_test.ps1`（agent-cli.ps1 的离线黄金夹具）—— **退出码 0 才算过**。"""
    if not PS1_GOLDEN.is_file():
        return "WARN", f"{PS1_GOLDEN.name} 不存在（本断言的登记依据）", []
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PS1_GOLDEN)],
            cwd=ROOT, capture_output=True, timeout=300)
    except FileNotFoundError:
        return "WARN", "本机无 powershell ⇒ 跳过（夹具只能在 Windows 侧跑）", []
    except subprocess.TimeoutExpired:
        return "FAIL", "夹具超时（>300s）⇒ 可能挂死", []
    out = _decode_out(p.stdout or b"") + _decode_out(p.stderr or b"")
    lines = [ln.rstrip() for ln in out.splitlines() if ln.strip()]
    summary = next((ln for ln in reversed(lines) if "FM_GOLDEN_TEST" in ln), "").strip()
    fails = [ln for ln in lines if ln.startswith("FAIL")]
    note = f"离线黄金夹具：{summary or '（无汇总行）'}"
    if p.returncode != 0:
        note += f" · 退出码 {p.returncode}"
    detail = lines[-12:]
    if fails:
        detail += ["── FAIL 行 ──"] + fails[:15]
    return ("PASS" if p.returncode == 0 else "FAIL"), note, detail


# ── D7-P3-2 (2026-09-26)「结论收束记账」: 结论进**既有**追加式账本, **不新造账本** ────
#   合并稿 §13.3 原话：「D7 的结论留痕应**复用 `inbox` 的 `40_state/LOG.md` 追加式纪律**，
#   **不新造账本**。」下面的函数把「本仓有哪些账本」变成**封闭集** ⇒
#   「有人新造了第二本账本」从「靠人记得」变成**可机判**。
LEDGERS_INV = ROOT / "inventory" / "conclusion-ledgers.yaml"
LEDGER_SCAN_EXCLUDE_DIRS = (".git", "node_modules", ".venv", "tmp")


def _s(v):
    """取字符串（非字符串一律当空）—— 避免 `42.strip()` 这类调用把判据打崩。"""
    return v.strip() if isinstance(v, str) else ""


def _fnmatch_any(rel, globs):
    """相对仓库根的 posix 路径 是否命中任一 glob。

    ★ 口径 = **fnmatch 语义**（`*` **跨** `/`）—— 这是**显式选择**：本表要的是
      「**形状覆盖**」（防的是「新造一本长得像的」），不是「精确路径」（后者归 `doclinks`）。
      ⚠ 用 `PurePath.match` 会**不同**（它的 `*` 不跨分隔符）⇒ 两处口径会悄悄分叉。
    """
    return any(fnmatch.fnmatchcase(rel, g) for g in (globs or []) if g)


def validate_conclusion_ledgers(doc, scan_hits=None):
    """**纯函数**（D7-P3-2）：账本真值表自洽 + 「扫描命中 ⊆ 登记集」。

    ⚠ `scan_hits` = 相对仓库根的 posix 路径列表（由 `check_conclusion_ledger` 去扫）。
      `None` = **不判扫描**（单测合成样例时用）—— 它**绝不**表示「0 命中 ⇒ 通过」。
      「读不到 ≠ 通过」在本函数里的落法：`None` 时**不产出扫描结论**，
      而不是产出「扫描过了，没问题」。
    """
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["顶层不是映射（yaml 根应是 mapping）"], notes

    disciplines = doc.get("disciplines")
    if not isinstance(disciplines, list) or not disciplines:
        bad.append("`disciplines` 为空 ⇒ 没有封闭枚举就没有纪律（『缺锚点不得登记』同源）")
        disciplines = []
    elif any(not _s(d) for d in disciplines):
        bad.append("`disciplines` 里有非字符串 / 空串项")

    ledgers = doc.get("ledgers")
    if not isinstance(ledgers, list) or not ledgers:
        bad.append("`ledgers` 为空 ⇒ 本表**没有对象**（退化空判 = 本仓头号形态）")
        ledgers = []

    seen_ids, used_disc, ledger_globs = set(), set(), []
    for i, lg in enumerate(ledgers):
        at = f"ledgers[{i}]"
        if not isinstance(lg, dict):
            bad.append(f"{at} 不是映射")
            continue
        lid = _s(lg.get("id"))
        if not lid:
            bad.append(f"{at} 缺 `id`")
        elif lid in seen_ids:
            bad.append(f"{at} `id` 重复: {lid}（账本 id 是标识，不得复用）")
        else:
            seen_ids.add(lid)
            at = f"ledgers[{lid}]"
        # 账本三要素：唯一写入者 / 纪律出处 / 独立校验 —— 缺一即不可判
        for k in ("what", "writer", "truth_doc", "verify"):
            if not _s(lg.get(k)):
                bad.append(f"{at} 缺 `{k}` —— 账本三要素（唯一写入者 / 纪律出处 / 独立校验）缺一即不可判")
        disc = lg.get("discipline")
        if disc not in disciplines:
            bad.append(f"{at} 的 `discipline`={disc!r} 不在声明集 {disciplines} 里")
        else:
            used_disc.add(disc)
        gl = [g for g in (lg.get("globs") or []) if _s(g)]
        pa = [p for p in (lg.get("paths") or []) if _s(p)]
        if not gl and not pa:
            bad.append(f"{at} 既无 `globs` 也无 `paths` ⇒ 无法判它指的是哪个文件")
        ledger_globs += gl + pa

    # 孤儿纪律：声明了却没有任何账本用 ⇒ 装饰（同 promotion 的『孤儿字段』）
    for d in disciplines:
        if d not in used_disc:
            bad.append(f"孤儿纪律: `disciplines` 声明了 {d!r} 但**没有任何账本**用它 ⇒ 形同虚设")

    # ── ★★「不新造账本」的**正面表述**必须写下来（空 = 没写 ⇒ FAIL）─────────
    nal = doc.get("not_a_ledger")
    if not isinstance(nal, list) or not nal:
        bad.append("`not_a_ledger` 为空 ⇒ **没有写下「什么不算账本」** ⇒ 下一个人会按『看着像』再建一本")
        nal = []
    for i, it in enumerate(nal):
        if not isinstance(it, dict) or not _s(it.get("glob")) or not _s(it.get("why")):
            bad.append(f"not_a_ledger[{i}] 缺 `glob` 或 `why`（『什么不算账本』必须给理由）")
            continue
        # ── 交叉：同一形态**不能既登记为账本、又声明不是账本**（自相矛盾）──
        g = _s(it["glob"])
        clashed = [x for x in ledger_globs if fnmatch.fnmatchcase(x, g) or fnmatch.fnmatchcase(g, x)]
        if clashed:
            bad.append(f"`not_a_ledger` 的 {g!r} 与登记的账本形态 {clashed} **相撞**"
                       f"（既说是账本、又声明不是 ⇒ 两处口径矛盾）")

    scan = doc.get("scan") if isinstance(doc.get("scan"), dict) else {}
    if not [g for g in (scan.get("globs") or []) if _s(g)]:
        bad.append("`scan.globs` 为空 ⇒ 没有扫描口径就没有『未登记账本』这条判据")
    if not [d for d in (scan.get("exclude_dirs") or []) if _s(d)]:
        bad.append("`scan.exclude_dirs` 为空 ⇒ 会把 .git / 依赖目录一起扫进来（口径不完整）")

    # ── 扫描侧（`scan_hits is None` ⇒ **不判**，而不是判过）─────────────────
    if scan_hits is not None:
        for rel in scan_hits:
            if not _fnmatch_any(rel, ledger_globs):
                bad.append(f"★**未登记的账本**: {rel} —— 它在扫描口径内却不属于任何已登记账本 ⇒ "
                           f"要么登记进 `inventory/conclusion-ledgers.yaml`，要么把扫描口径说清")
        # 反向防腐化：登记了 globs 的账本**必须**有条目命中（登记了却扫不到 = 登记已腐化）
        for lg in ledgers:
            if not isinstance(lg, dict):
                continue
            gl = [g for g in (lg.get("globs") or []) if _s(g)]
            if gl and not any(_fnmatch_any(h, gl) for h in scan_hits):
                bad.append(f"账本 {_s(lg.get('id'))!r} 登记了 globs {gl} 却**一条也没命中** ⇒ "
                           f"登记腐化（账本被删 / 改名，或 glob 写错）")

    unv = doc.get("unverified")
    if not isinstance(unv, list) or not unv:
        bad.append("`unverified` 为空 ⇒ 本项自己未实测 / 未定的部分没登记")

    if not bad:
        notes.append(f"账本 {len(ledgers)} 本 · 纪律 {sorted(used_disc)} · 非账本点名 {len(nal)} 项")
        if scan_hits is None:
            notes.append("扫描：**未接扫描输入（不判，不算通过）**")
        else:
            notes.append(f"扫描命中 {len(scan_hits)} 处 · 全部已登记")
    return bad, notes


def _scan_ledger_hits():
    """按 `scan` 段扫盘，返回**相对仓库根**的 posix 路径（排序去重）。"""
    import yaml
    doc = yaml.safe_load(_read_text(LEDGERS_INV)) or {}
    scan = doc.get("scan") if isinstance(doc.get("scan"), dict) else {}
    exclude = set(scan.get("exclude_dirs") or []) | set(LEDGER_SCAN_EXCLUDE_DIRS)
    hits = []
    for g in (scan.get("globs") or []):
        if not _s(g):
            continue
        for p in ROOT.glob(g):
            if not p.is_file():
                continue
            rel = p.relative_to(ROOT).as_posix()
            if any(part in exclude for part in rel.split("/")):
                continue
            hits.append(rel)
    return sorted(set(hits))


def check_conclusion_ledger(ctx):
    """D7-P3-2: 「结论收束记账」—— 结论进**既有**追加式账本，**不新造账本**。"""
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 conclusion-ledger 断言", []
    if not LEDGERS_INV.exists():
        return "FAIL", "inventory/conclusion-ledgers.yaml 缺失（本断言的登记依据）", []
    try:
        doc = yaml.safe_load(_read_text(LEDGERS_INV)) or {}
    except Exception as e:
        return "FAIL", f"inventory/conclusion-ledgers.yaml 解析失败: {type(e).__name__}: {e}", []
    try:
        hits = _scan_ledger_hits()
    except Exception as e:
        # ⚠ **读不到 ≠ 通过**：扫描失败必须报出来，**不许**回落到「不判扫描」。
        return "FAIL", f"账本扫描失败（不可判 ⇒ 不许当通过）: {type(e).__name__}: {e}", []
    bad, notes = validate_conclusion_ledgers(doc, scan_hits=hits)
    # 盘上存在性：登记了 `paths` 的账本，文件必须真在（「登记腐化」的另一半）
    for lg in (doc.get("ledgers") or []):
        if not isinstance(lg, dict):
            continue
        for p in (lg.get("paths") or []):
            if not _s(p):
                continue
            if not (ROOT / p).exists():
                bad.append(f"账本 {_s(lg.get('id'))!r} 登记的路径不存在: {p} ⇒ "
                           f"登记腐化（换机器 / 被删 / 改名）")
    return ("FAIL" if bad else "PASS"), " · ".join(notes), bad


# ── D7-P3-2 (2026-09-26)「标准复核目录」: 免终裁类目清单（D-43 的退出判据之一）────────
REVIEW_CATALOG_INV = ROOT / "inventory" / "review-catalog.yaml"


def validate_review_catalog(doc):
    """**纯函数**（D7-P3-2）：标准复核目录的自洽（免终裁类目清单）。

    ★ 守的是 **D-43 的准入门槛**「同一类被批准两次」（ITIL 原话）。它最容易被绕开的方式是
      「把 `approvals` 填成 2 但**拿不出那两次的锚点**」⇒ 故
      `len(approval_anchors) == approvals` 是硬条件（只填数字 = 自说自话）。
    """
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["顶层不是映射（yaml 根应是 mapping）"], notes

    adm = doc.get("admission") if isinstance(doc.get("admission"), dict) else {}
    if not adm:
        bad.append("缺 `admission` 段 ⇒ 没有准入门槛，『类目』就退化成『我觉得安全』")
    if not _s(adm.get("rule")):
        bad.append("`admission.rule` 为空 ⇒ 门槛没有出处")
    ma = adm.get("min_approvals")
    if not isinstance(ma, int) or isinstance(ma, bool) or ma < 2:
        bad.append(f"`admission.min_approvals`={ma!r} 必须 ≥ 2 —— 门槛设成 1 或 0 ⇒ "
                   f"**每一类都是标准复核** = 判据恒真（本仓头号形态）")
        ma = 2
    if not isinstance(adm.get("type_axis"), str):
        bad.append("`admission.type_axis` 必须是字符串（未定义 ⇒ 置空串，**不是**省略该键）")
    if not _s(adm.get("type_axis_note")):
        bad.append("`admission.type_axis_note` 为空 ⇒ 类型轴的现状（有 / 无 / 为什么）没写下来")
    rt = adm.get("ratio_target")
    if not isinstance(rt, dict):
        bad.append("缺 `admission.ratio_target`（ITIL 的比例目标 —— 只报数，但必须登记）")
        rt = {}
    else:
        lo, hi, judged = rt.get("low"), rt.get("high"), rt.get("judged")
        if not (isinstance(lo, int) and isinstance(hi, int) and not isinstance(lo, bool)
                and not isinstance(hi, bool) and 0 < lo < hi <= 100):
            bad.append(f"`ratio_target` 的 low/high 非法: {lo}/{hi}（须 0 < low < high ≤ 100）")
        if not isinstance(judged, bool):
            bad.append("`ratio_target.judged` 必须是布尔 —— 它标明这条目标是**判**还是**只报数**")

    sch = doc.get("entry_schema") if isinstance(doc.get("entry_schema"), dict) else {}
    if not sch:
        bad.append("缺 `entry_schema` 段 ⇒ 类目的形状没定义 ⇒ 登进来的东西无法核对")
    stages = sch.get("exempt_stages")
    if not isinstance(stages, list) or not stages or any(not _s(s) for s in stages):
        bad.append("`entry_schema.exempt_stages` 必须是非空字符串列表（免哪一层 = 封闭枚举）")
        stages = []
    fields = sch.get("fields")
    fids = []
    if not isinstance(fields, list) or not fields:
        bad.append("`entry_schema.fields` 为空")
        fields = []
    for i, f in enumerate(fields):
        if not isinstance(f, dict) or not _s(f.get("id")):
            bad.append(f"entry_schema.fields[{i}] 缺 `id`")
            continue
        if not _s(f.get("note")):
            bad.append(f"entry_schema.fields[{i}]({_s(f.get('id'))}) 缺 `note` ⇒ 字段含义靠猜")
        fids.append(_s(f.get("id")))
    if len(fids) != len(set(fids)):
        bad.append("`entry_schema.fields` 的 `id` 有重复")
    req = sch.get("required")
    if not isinstance(req, list) or not req:
        bad.append("`entry_schema.required` 为空 ⇒ 没有必填就没有门")
        req = []
    for r in req:
        if r not in fids:
            bad.append(f"`entry_schema.required` 引用了不存在的字段 {r!r}")
    for fid in fids:
        if fid not in req:
            bad.append(f"孤儿字段: `entry_schema.fields` 有 {fid!r} 但 `required` 没用它 ⇒ 装饰")

    entries = doc.get("entries")
    if not isinstance(entries, list):
        bad.append("缺 `entries` 字段（『不存在』与『为空』必须可区分）")
        entries = []
    seen = set()
    for i, e in enumerate(entries):
        at = f"entries[{i}]"
        if not isinstance(e, dict):
            bad.append(f"{at} 不是映射")
            continue
        eid = _s(e.get("id"))
        if eid and eid in seen:
            bad.append(f"{at} `id` 重复: {eid}")
        seen.add(eid)
        at = f"entries[{eid or i}]"
        for k in req:
            v = e.get(k)
            if v is None or (isinstance(v, (str, list)) and not v):
                bad.append(f"{at} 缺必填 `{k}`")
        if e.get("exempt_from") and e["exempt_from"] not in stages:
            bad.append(f"{at} `exempt_from`={e['exempt_from']!r} 不在封闭枚举 {stages} 里")
        ap = e.get("approvals")
        if not isinstance(ap, int) or isinstance(ap, bool) or ap < ma:
            bad.append(f"{at} `approvals`={ap!r} 未达准入门槛 {ma}（D-43：同一类被批准两次）")
        anchors = e.get("approval_anchors")
        if not isinstance(anchors, list) or not anchors or any(not _s(a) for a in anchors):
            bad.append(f"{at} `approval_anchors` 必须是非空字符串列表")
        elif isinstance(ap, int) and not isinstance(ap, bool) and len(anchors) != ap:
            bad.append(f"{at} `approval_anchors` 有 {len(anchors)} 条但 `approvals`={ap} ⇒ "
                       f"**只填数字拿不出锚点** = 自说自话（D-43 的门槛没被真满足）")
        rv = e.get("review_every")
        if not isinstance(rv, int) or isinstance(rv, bool) or rv <= 0:
            bad.append(f"{at} `review_every` 必须是正整数（天）")

    # ★ 交叉：有类目却**没有类型轴** ⇒ 那些类目凭什么浮出来的？
    if entries and not _s(adm.get("type_axis")):
        bad.append("★ 有类目（`entries` 非空）但 `admission.type_axis` 为空 ⇒ "
                   "**类目没有浮出依据**（门槛是『同一类』，没有轴就没有『类』）")
    if not entries and not _s(doc.get("empty_reason")):
        bad.append("`entries` 为空却没有 `empty_reason` ⇒ **空不许当『没事』**（本仓已登记的假绿形态）")

    unv = doc.get("unverified")
    if not isinstance(unv, list) or not unv:
        bad.append("`unverified` 为空 ⇒ 本项自己未实测 / 未定的部分没登记")

    if not bad:
        notes.append(f"免终裁类目 {len(entries)} 条 · 准入门槛 min_approvals={ma} · "
                     f"类型轴 {'已定义' if _s(adm.get('type_axis')) else '**未定义**'}")
        if rt:
            notes.append(f"比例目标 {rt.get('low')}–{rt.get('high')}%"
                         f"（{'判' if rt.get('judged') else '**只报数、不判**'}）")
        notes.append(f"可豁免层 {stages}")
    return bad, notes


def check_review_catalog(ctx):
    """D7-P3-2: 标准复核目录（D-43 退出判据『免终裁类目有清单』）。"""
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 review-catalog 断言", []
    if not REVIEW_CATALOG_INV.exists():
        return "FAIL", "inventory/review-catalog.yaml 缺失（本断言的登记依据）", []
    try:
        doc = yaml.safe_load(_read_text(REVIEW_CATALOG_INV)) or {}
    except Exception as e:
        return "FAIL", f"inventory/review-catalog.yaml 解析失败: {type(e).__name__}: {e}", []
    bad, notes = validate_review_catalog(doc)
    return ("FAIL" if bad else "PASS"), " · ".join(notes), bad


# ── D7-P3-3 (2026-09-26)「记忆四道门」+ 授权边界写成**结构性约束** ────────────────
#   D-47：共享记忆做，但必须带四道门（write/retrieval/promotion/reuse）；
#         MAPLE-Guard（arXiv 2608.00426）：**私有→共享的"晋升"是攻击面的关键一跳**。
#   D-48：**不要指望"审得更准"，要靠"结构 contain"**（arXiv 2609.17648：JBR 100% 但 Unsafe 0%）。
#   D-40：**单人开发者是常态假设** ⇒ 授权边界只能写成结构性约束。
#   ⇒ 本判据判四件事：① 四门各有一条**真实存在**的判据（防"挂名假判"）；
#     ② 私有→共享的**每条通道**都要写明 `gate`（"无门"必须可区分于"刻意共享"）；
#     ③ 结构性约束**必须有判据**（没判据的仍只是纪律）；
#     ④ 记忆面的**接触点**是封闭集 + 记忆**不得出网**。
MEMORY_GATES_INV = ROOT / "inventory" / "memory-gates.yaml"
MEMORY_GATE_IDS = ("write", "retrieval", "promotion", "reuse")
MEMORY_CODE_EXTS = (".py", ".ps1", ".psm1", ".sh")


def extract_memory_symlinks(text, token):
    """从 `agent-cli.ps1` 提取**把记忆库文件做 symlink** 的行 → `[(行号, 行文本)]`。

    ★ 口径（写死，不许再含糊）：**该行同时含「记忆库文件名」与 `ln -`，且不是注释** ⇒ 算一条通道。
      为什么不是"含该文件名的每一行"：那会把**注释**与**只读探测**一起算进来，
      于是"通道数"这个数就不稳（本仓已因口径含糊连踩三次）。
    ⚠ `token` **由调用方从真值表传入**（不在本文件里硬编码路径）—— 这既是"单一真值"，
      也让本判据自己**不成为**记忆面接触点（否则它得把自己也登记进去）。
    """
    hits = []
    for i, ln in enumerate(text.splitlines(), 1):
        if ln.lstrip().startswith("#"):
            continue
        if token and token in ln and re.search(r"\bln\s+-", ln):
            hits.append((i, ln))
    return hits


def parse_symlink_paths(line):
    """从 symlink 行取出 `(src, tgt)` —— 取该行**最后两个**双引号串（`ln -sfn SRC TGT` 的实参）。"""
    qs = re.findall(r'"([^"]*)"', line)
    if len(qs) < 2:
        return None, None
    return qs[-2], qs[-1]


def scan_memory_touchpoints(path_tokens, bases=("ops", "tests")):
    """扫 `ops/` + `tests/` 下**可执行文件**里提到记忆路径的文件 → 相对仓库根的有序路径表。"""
    hits = []
    for base in bases:
        for p in sorted((ROOT / base).rglob("*")):
            if not p.is_file() or p.suffix.lower() not in MEMORY_CODE_EXTS:
                continue
            if any(x in p.parts for x in (".git", "__pycache__", "node_modules")):
                continue
            if any(t in _read_text(p) for t in path_tokens):
                hits.append(p.relative_to(ROOT).as_posix())
    return hits


def scan_memory_egress(files, path_tokens, carriers):
    """记忆**不得出网**：同一行同时出现【记忆路径】与【跨机搬运令牌】⇒ 命中。

    ⚠ 口径是**同一行**（不跨行）—— 局限（变量拼接/换行可逃）已登记在 yaml 的 `unverified`。
    """
    out = []
    for rel in files:
        for i, ln in enumerate(_read_text(ROOT / rel).splitlines(), 1):
            if ln.lstrip().startswith("#"):
                continue
            if any(t in ln for t in path_tokens) and any(c in ln for c in carriers):
                out.append((rel, i, ln.strip()[:160]))
    return out


def scan_isolation_by_text_prefix(marker, rel_files):
    """项目隔离**不得**以文本前缀为判据 ⇒ 在给定的**判据/测试实现**里找该标记。

    ★ 为什么要裁掉 `CHECKS` 注册表那一段：注册表里的 `fix` 是**给人读的处置说明**，
      不是判据实现 ⇒ 把它算进来会让本判据**自己触发自己**（口径错一次就永远是假红）。
      故：只扫 `CHECKS = [` 之前的**函数体**部分。
    """
    hits = []
    for rel in rel_files:
        p = ROOT / rel
        if p.is_dir():
            for f in sorted(p.glob("test_*.py")):
                t = _read_text(f)
                for i, ln in enumerate(t.splitlines(), 1):
                    if marker in ln:
                        hits.append((f.relative_to(ROOT).as_posix(), i, ln.strip()[:120]))
            continue
        t = _read_text(p)
        head = t.split("\nCHECKS = [")[0]
        for i, ln in enumerate(head.splitlines(), 1):
            if marker in ln:
                hits.append((rel, i, ln.strip()[:120]))
    return hits


def validate_memory_gates(doc, known_checks, touchpoint_hits=None):
    """**纯函数**（D7-P3-3）：四道门 + 通道 + 结构性约束的结构自洽。

    `known_checks` = 已注册的 `CHECKS` id 集合（由调用方传入；与 `validate_manual_counts` 同形）。
    ★ 传它是为了堵本仓最典型的一类假绿：**判据指向一个不存在的判据**（挂名）。
    `touchpoint_hits=None` ⇒ **不判接触点封闭集**（合成样例用）；**绝不**读成"没有接触点"。
    """
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["顶层不是映射（yaml 根应是 mapping）"], notes

    # ── ① 四道门：**缺一即红**（这就是退出判据「四门各一条判据」的机判）─────────
    gates = doc.get("gates")
    if not isinstance(gates, list) or not gates:
        bad.append("`gates` 为空 ⇒ 四道门没有对象（退化空判 = 本仓头号形态）")
        gates = []
    seen = {}
    for i, g in enumerate(gates):
        at = f"gates[{i}]"
        if not isinstance(g, dict):
            bad.append(f"{at} 不是映射")
            continue
        gid = _s(g.get("id"))
        if not gid:
            bad.append(f"{at} 缺 `id`")
        elif gid in seen:
            bad.append(f"{at} `id` 重复: {gid}")
        else:
            seen[gid] = g
            at = f"gates[{gid}]"
        if not _s(g.get("what")):
            bad.append(f"{at} 缺 `what`（这道门管什么）")
        if not _s(g.get("object")):
            bad.append(f"{at} 缺 `object`（本仓的判据对象）")
        # ★ `not_covers` **必填** —— 本仓已登记的假绿形态 = 把"部分覆盖"当"全覆盖"
        if not _s(g.get("not_covers")):
            bad.append(f"{at} 缺 `not_covers` ⇒ **没写清它不覆盖什么**（部分覆盖会被读成全覆盖）")
        j = g.get("judgment")
        if not isinstance(j, dict):
            bad.append(f"{at} 缺 `judgment` 段 ⇒ **这道门没有判据**（「没判」与「判了且通过」必须可区分）")
            continue
        kind = j.get("kind")
        if kind == "check":
            ref = _s(j.get("ref"))
            if not ref:
                bad.append(f"{at}.judgment 缺 `ref`")
            elif ref not in known_checks:
                bad.append(f"{at}.judgment.ref={ref!r} **不是已注册的 CHECKS id** ⇒ "
                           f"挂名假判（判据写了但没人跑）")
        elif kind == "na":
            if not _s(j.get("object_absent_why")):
                bad.append(f"{at}.judgment 是 `na` 但缺 `object_absent_why` ⇒ "
                           f"**「不做」也要写下来**（不适用必须给理由）")
        else:
            bad.append(f"{at}.judgment.kind={kind!r} 不在封闭集 {{check, na}} 里")
    for gid in MEMORY_GATE_IDS:
        if gid not in seen:
            bad.append(f"★ 缺一道门: {gid!r} —— D-47 要求 write/retrieval/promotion/reuse **四门齐**")
    for gid in seen:
        if gid not in MEMORY_GATE_IDS:
            bad.append(f"多出一道门 {gid!r} ⇒ 四门是**封闭集**（多出来的那门有没有判据？）")

    # ── ② 私有 → 共享的通道（"关键一跳"必须逐条写明门）──────────────────────
    bridges = doc.get("bridges")
    if not isinstance(bridges, list) or not bridges:
        bad.append("`bridges` 为空 ⇒ **关键一跳（私有→共享）没有对象**，四门里的 promotion/reuse 判不了")
        bridges = []
    ungated_engine, ungated_ours = [], []
    seen_b = set()
    for i, b in enumerate(bridges):
        at = f"bridges[{i}]"
        if not isinstance(b, dict):
            bad.append(f"{at} 不是映射")
            continue
        bid = _s(b.get("id"))
        if not bid or bid in seen_b:
            bad.append(f"{at} 缺 `id` 或 `id` 重复: {bid!r}")
        seen_b.add(bid)
        at = f"bridges[{bid or i}]"
        for k in ("channel", "why", "evidence"):
            if not _s(b.get(k)):
                bad.append(f"{at} 缺 `{k}`")
        if not isinstance(b.get("isolated"), bool):
            bad.append(f"{at} `isolated` 必须是布尔（「是否按项目/任务隔离」是**实测口径**，不是形容词）")
        if not isinstance(b.get("controllable_by_us"), bool):
            bad.append(f"{at} `controllable_by_us` 必须是布尔（决定这条通道该红还是该点名）")
        gate = b.get("gate")
        if gate == "none":
            if b.get("controllable_by_us") is True:
                ungated_ours.append(bid)
                bad.append(f"{at} ★ `gate: none` 且**本仓可控** ⇒ **红**：本仓能关却不关，"
                           f"正是 MAPLE-Guard 说的「关键一跳」敞着")
            else:
                ungated_engine.append(bid)
        elif gate == "by-design-shared":
            # "刻意共享"与"忘了关门"必须可区分 ⇒ 刻意共享要**给出理由**
            if not _s(b.get("why")):
                bad.append(f"{at} `gate: by-design-shared` 但 `why` 为空 ⇒ 与 `none` 无法区分")
        elif gate == "cwd-keyed":
            if not _s(b.get("key")):
                bad.append(f"{at} `gate: cwd-keyed` 但没写 `key`（按什么键控隔离？没键就不叫键控）")
        else:
            bad.append(f"{at} `gate`={gate!r} 不在封闭集 {{cwd-keyed, by-design-shared, none}} 里")

    # ── ③ 结构性约束：**每条必须有判据**（没判据的还只是纪律）────────────────
    scs = doc.get("structural_constraints")
    if not isinstance(scs, list) or not scs:
        bad.append("`structural_constraints` 为空 ⇒ **授权边界没有写成结构性约束**（D-48 的核心要求）")
        scs = []
    seen_sc = set()
    for i, s in enumerate(scs):
        at = f"structural_constraints[{i}]"
        if not isinstance(s, dict):
            bad.append(f"{at} 不是映射")
            continue
        sid = _s(s.get("id"))
        if not sid or sid in seen_sc:
            bad.append(f"{at} 缺 `id` 或 `id` 重复: {sid!r}")
        seen_sc.add(sid)
        at = f"structural_constraints[{sid or i}]"
        if not _s(s.get("rule")):
            bad.append(f"{at} 缺 `rule`")
        if not _s(s.get("why_structural")):
            bad.append(f"{at} 缺 `why_structural` ⇒ 没说明**为什么它是结构而不是「指望写清楚」**")
        jb = _s(s.get("judged_by"))
        if jb == "NA_UNIT":
            bad.append(f"{at} `judged_by: NA_UNIT` ⇒ **它就不是结构性约束** ⇒ "
                       f"请移到 `known_non_structural` 段并说明为什么"
                       f"（两段混用 = 把两件事说成一件，本仓头号形态）")
        elif jb not in known_checks:
            bad.append(f"{at} `judged_by`={jb!r} 不是已注册的 CHECKS id ⇒ "
                       f"**没判据的约束仍只是纪律**（「写成结构性约束」的含义就是有判据）")

    # ── ③b 如实登记：**今天还不是**结构性约束的授权边界（两段**不得混用**）────────
    kns = doc.get("known_non_structural")
    if not isinstance(kns, list) or not kns:
        bad.append("`known_non_structural` 为空 ⇒ 「今天还不是结构性约束」的边界没有登记"
                   "（「不是结构」这件事也必须写下来）")
        kns = []
    for i, k in enumerate(kns):
        at = f"known_non_structural[{i}]"
        if not isinstance(k, dict):
            bad.append(f"{at} 不是映射")
            continue
        kid = _s(k.get("id"))
        at = f"known_non_structural[{kid or i}]"
        for fld in ("rule", "today", "why_not_structural", "object_absent_why"):
            if not _s(k.get(fld)):
                bad.append(f"{at} 缺 `{fld}`")
        if kid and kid in seen_sc:
            bad.append(f"{at} 与 `structural_constraints` **出现同一个 id** {kid!r} ⇒ "
                       f"同一条边界被同时说成「是结构」和「不是结构」")

    # ── ④ 接触点封闭集（`None` ⇒ **不判**，而不是判过）──────────────────────
    tps = doc.get("touchpoints")
    if not isinstance(tps, list) or not tps:
        bad.append("`touchpoints` 为空 ⇒ 「记忆面接触点」没有封闭集 ⇒ 新开一条通道不会被发现")
        tps = []
    reg = []
    for i, t in enumerate(tps):
        if not isinstance(t, dict) or not _s(t.get("file")):
            bad.append(f"touchpoints[{i}] 缺 `file`")
            continue
        if not _s(t.get("why")):
            bad.append(f"touchpoints[{i}]({_s(t.get('file'))}) 缺 `why`")
        if not isinstance(t.get("egress"), bool):
            bad.append(f"touchpoints[{i}]({_s(t.get('file'))}) 的 `egress` 必须是布尔")
        reg.append(_s(t.get("file")))
    if touchpoint_hits is not None:
        for h in touchpoint_hits:
            if h not in reg:
                bad.append(f"★**未登记的记忆面接触点**: {h} ⇒ 要么登记进 `touchpoints`（含理由），"
                           f"要么把记忆路径从该文件里去掉")
        # ⚠「登记的接触点不存在」**不在这里判** —— 那是**盘上存在性**，属 `check_memory_gates`
        #   （本函数是纯函数：纯函数不碰盘）。放这儿会让合成样例悄悄跳过它。

    # ── ⑤ 出网口径 / 前缀口径 必填 ─────────────────────────────────────────
    eg = doc.get("egress")
    if not isinstance(eg, dict):
        bad.append("缺 `egress` 段 ⇒ 记忆「不得出网」没有口径")
    else:
        ptk = eg.get("path_tokens")
        if not isinstance(ptk, dict) or not ptk or not all(_s(v) for v in ptk.values()):
            bad.append("`egress.path_tokens` 必须是非空映射、且值非空 —— 角色名就是用途，"
                       "**不靠顺序**（顺序口径本仓已吃过亏）")
        if not [x for x in (eg.get("carrier_tokens") or []) if _s(x)]:
            bad.append("`egress.carrier_tokens` 为空 ⇒ 不知道什么算「跨机搬运」")
    tp = doc.get("text_prefix")
    if not isinstance(tp, dict) or not _s(tp.get("marker")) \
            or not [x for x in (tp.get("forbidden_in") or []) if _s(x)]:
        bad.append("`text_prefix` 段缺 `marker` / `forbidden_in`（缺席判据要点名它扫哪里）")

    unv = doc.get("unverified")
    if not isinstance(unv, list) or not unv:
        bad.append("`unverified` 为空 ⇒ 本项自己未实测 / 未定的部分没登记")

    if not bad:
        n_na = sum(1 for g in seen.values()
                   if isinstance(g.get("judgment"), dict) and g["judgment"].get("kind") == "na")
        notes.append(f"四门齐（{len(seen)}/4，其中判据 NA {n_na} 道）· 通道 {len(bridges)} 条 · "
                     f"结构性约束 {len(scs)} 条 · 非结构性（如实登记）{len(kns)} 条 · 接触点 {len(reg)} 个")
        notes.append(f"无门通道：本仓可控 {len(ungated_ours)} 条 / 引擎侧 {len(ungated_engine)} 条"
                     f"{'（点名: ' + ', '.join(ungated_engine) + '）' if ungated_engine else ''}")
        if touchpoint_hits is None:
            notes.append("接触点扫描：**未接扫描输入（不判，不算通过）**")
        else:
            notes.append(f"接触点扫描命中 {len(touchpoint_hits)} 个文件 · 全部已登记")
    return bad, notes


def check_memory_gates(ctx, doc=None):
    """D7-P3-3: 记忆四道门 + 授权边界（结构性约束）+ 接触点封闭集 + 不得出网。

    ★ `doc` 是可注入缝（测试用）：`None` ⇒ 从 `inventory/memory-gates.yaml` 读。
      为什么需要它：「**登记的接触点不存在**」与「备份落点」这类判断要吃**盘上实况**，
      而 `validate_memory_gates` 是纯函数 —— 没有这个缝，那两条只能靠合成样例"假装验过"。
    """
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 memory-gates 断言", []
    if doc is None:
        if not MEMORY_GATES_INV.exists():
            return "FAIL", "inventory/memory-gates.yaml 缺失（本断言的登记依据）", []
        try:
            doc = yaml.safe_load(_read_text(MEMORY_GATES_INV)) or {}
        except Exception as e:
            return "FAIL", f"inventory/memory-gates.yaml 解析失败: {type(e).__name__}: {e}", []

    # 0) 记忆路径的**唯一字面定义点**在真值表里 ⇒ 本文件**不硬编码**它们
    eg = doc.get("egress") if isinstance(doc.get("egress"), dict) else {}
    ptk = eg.get("path_tokens") if isinstance(eg.get("path_tokens"), dict) else {}
    ptokens = [v for v in ptk.values() if _s(v)]
    db_token = _s(ptk.get("db"))
    if not db_token:
        return "FAIL", "`egress.path_tokens.db` 缺失 ⇒ SC-1（记忆库 symlink）不可判；**不可判 ≠ 通过**", []

    # 1) 记忆面：接触点扫盘（扫不到 ≠ 通过 ⇒ 异常要报出来）
    try:
        tp_hits = scan_memory_touchpoints(ptokens)
    except Exception as e:
        return "FAIL", f"接触点扫描失败（不可判 ⇒ 不许当通过）: {type(e).__name__}: {e}", []

    bad, notes = validate_memory_gates(doc, known_checks={c["id"] for c in CHECKS},
                                      touchpoint_hits=tp_hits)
    # 1b) **盘上存在性**：登记的接触点必须真在（纯函数判不了这条 —— 它要碰盘）
    for t in (doc.get("touchpoints") or []):
        if isinstance(t, dict) and _s(t.get("file")) and not (ROOT / _s(t["file"])).exists():
            bad.append(f"登记的接触点不存在: {_s(t['file'])} ⇒ "
                       f"登记腐化（文件被删 / 改名 / 换机器）")

    # 2) SC-1：`agent-cli.ps1` 里**恰好一条**记忆库 symlink，且源必须在站级 $HOME 下
    if AGENT_CLI.exists():
        syms = extract_memory_symlinks(_read_text(AGENT_CLI), db_token)
        if len(syms) != 1:
            bad.append(f"★ 记忆面 symlink 实测 **{len(syms)} 处**（要求恰 1 处）⇒ "
                       f"共享面被扩容或判据没对象；行号 {[n for n, _ in syms]}")
        else:
            ln_no, ln_txt = syms[0]
            src, tgt = parse_symlink_paths(ln_txt)
            plane = doc.get("memory_plane") or {}
            guard = doc.get("plane_guard") or {}
            ok_pre = [p for p in (guard.get("allowed_source_prefixes") or []) if src and src.startswith(p)]
            forbid = [m for m in (guard.get("forbidden_source_markers") or []) if src and m in src]
            ok_suf = tgt and _s(guard.get("allowed_target_suffix")) and tgt.endswith(_s(guard["allowed_target_suffix"]))
            if not ok_pre:
                bad.append(f"{AGENT_CLI.name}:{ln_no} symlink 源 {src!r} 不在允许前缀 "
                           f"{guard.get('allowed_source_prefixes')} 里 ⇒ 共享面可能被指到工作区/项目目录")
            if forbid:
                bad.append(f"{AGENT_CLI.name}:{ln_no} symlink 源含禁止标记 {forbid} ⇒ "
                           f"记忆被搬进项目目录（= 把项目记忆写进共享层）")
            if not ok_suf:
                bad.append(f"{AGENT_CLI.name}:{ln_no} symlink 目标 {tgt!r} 不以 "
                           f"{guard.get('allowed_target_suffix')!r} 结尾")
            if not isinstance(plane.get("scope"), str) or not _s(plane.get("scope")):
                bad.append("`memory_plane.scope` 为空 ⇒ 记忆面的**共享面**没写下来")
            if not _s(plane.get("scope_evidence")):
                bad.append("`memory_plane.scope_evidence` 为空 ⇒ 共享面的**出处**没写（实测还是推断？）")
    else:
        bad.append("缺 agent-cli.ps1 ⇒ SC-1（记忆面路径常量）不可判；**不可判 ≠ 通过**")

    # 3) SC-2：记忆不得出网（同一行同现）+ 备份只落**站内** $HOME
    carriers = [t for t in (eg.get("carrier_tokens") or []) if _s(t)]
    eg_hits = scan_memory_egress(tp_hits, ptokens, carriers)
    for rel, ln_no, txt in eg_hits:
        bad.append(f"★ 记忆**出网**嫌疑: {rel}:{ln_no} ⇒ `{txt}`（同一行同现记忆路径与跨机搬运）")
    bscript = _s(eg.get("backup_script"))
    if bscript:
        if not (ROOT / bscript).exists():
            bad.append(f"`egress.backup_script` 指向的 {bscript} 不存在 ⇒ 登记腐化")
        else:
            var = _s(eg.get("backup_dir_var"))
            prefs = tuple(_s(x) for x in (eg.get("backup_dir_prefixes") or []) if _s(x))
            vals = [ln.split(var, 1)[1].strip() for ln in _read_text(ROOT / bscript).splitlines()
                    if ln.startswith(var) and not ln.lstrip().startswith("#")]
            if not vals:
                bad.append(f"{bscript} 找不到 `{var}` 赋值 ⇒ 备份落点不可判（不可判 ≠ 通过）")
            elif not any(v.startswith(prefs) for v in vals):
                bad.append(f"{bscript} 的 `{var}`={vals[0]!r} 不在站内前缀 {prefs} 里 ⇒ "
                           f"备份可能落到站外（记忆出网）")

    # 4) SC-3：项目隔离**不得**以文本前缀为判据（缺席判据）
    tp = doc.get("text_prefix") or {}
    marker = _s(tp.get("marker"))
    if marker:
        pref_hits = scan_isolation_by_text_prefix(marker, [x for x in (tp.get("forbidden_in") or []) if _s(x)])
        for rel, ln_no, txt in pref_hits:
            bad.append(f"★ 隔离**靠文本前缀**: {rel}:{ln_no} ⇒ `{txt}` —— "
                       f"把命名当边界（D-48：要靠结构 contain，不是「指望写清楚」）")

    if bad:
        return "FAIL", " · ".join(notes) if notes else "见明细", bad
    eng = [_s(b.get("id")) for b in (doc.get("bridges") or [])
           if isinstance(b, dict) and b.get("gate") == "none"]
    if eng:
        # 引擎侧无门通道：**点名 + WARN**（本仓关不了；但绝不静默 —— 明细里必须**逐个报名字**，
        #   ★ 只说"见 yaml"不算点名：那等于让读者自己去猜是哪一条）
        return "WARN", " · ".join(notes), [
            f"引擎侧无门通道 {len(eng)} 条（本仓关不了 ⇒ 只登记 + 点名）: " + ", ".join(eng)]
    return "PASS", " · ".join(notes), []


# ── D7-P4-1 (2026-09-26)「多轮闭环 + **轮数上限有判据**」────────────────────────
#   退出判据原文 = 「多轮闭环可跑；**轮数上限有判据**」。
#   ★ 先去找对象（本会话第四次）：受理侧**早就有**一个协商回环（`plan-review ⇄ plan-revise`，
#     路线总表 §11.2(a) 已实测标注「**已有原型 ⇒ 复用状态语义，而非另建**」）
#     ⇒ 本项不是"造多轮引擎"，而是**把本仓真实存在的闭环逐条钉住上限与终止条件**。
#   ★★ 本批实测抓到的真缺陷：**注释里的上限落后于代码** —— `agent-cli.ps1` 里**两处**
#     写 `retry <=2`，而代码分别是 `-lt 3` 与 `-le 3`（O-46 改 cap 时注释没跟）。
#     ⇒ 故本判据专门有 **`prose_caps` 封闭集**：散文里的上限必须逐处登记且与代码一致。
MULTI_ROUND_INV = ROOT / "inventory" / "multi-round.yaml"
LOOP_KINDS = ("advance", "retry")
LOOP_CAP_STATES = ("capped", "unbounded-by-design", "undecided")
ROUND_COUNTER_KINDS = ("file-glob", "shell-var", "state-log")
# 超限处置：**封闭枚举**（★ 刻意不是"扫散文里有没有『继续』" —— 那是文本口径，
#   实测会假红：`"超限 ⇒ 升级（不是继续）"` 里含「继续」就被判红）。
ON_EXCEED_KINDS = ("escalate", "terminate", "fail-record", "undecided")
CODE_CAP_RE = re.compile(r"-(?:lt|le)\s+(\d+)")
# 文档上限写法：`≤N` **或** `<= N` —— ★ `spec/**/*.md` 用 `≤`（且词与运算符间常隔字），
#   上面 `prose_caps` 的口径只认 `<词> <= N` 紧邻 ⇒ **扫不到**（已登记的逃逸）⇒ 必须单独认。
DOC_CAP_RE = re.compile(r"(?:≤|<=)\s*(\d+)")


def extract_loop_cap(text, marker, op):
    """从目标文件里**实提取**循环上限：形如 `<marker> … <op> N` → `[(行号, N)]`。

    ★ 口径（**双锚**，写死）：**同一行**里既含 `marker` 又含 `<op> N`，且不是注释。
      为什么要双锚：只按 marker 找会把 `CONT_ATTEMPT=0` 这种**赋值行**也算进来
      —— 那正是"口径没定就量"的老毛病（本仓已连踩三次）。
    """
    rx = re.compile(re.escape(op) + r"\s+(\d+)")
    hits = []
    for i, ln in enumerate(text.splitlines(), 1):
        if ln.lstrip().startswith("#"):
            continue
        if marker in ln:
            m = rx.search(ln)
            if m:
                hits.append((i, int(m.group(1))))
    return hits


def scan_prose_caps(text, words):
    """扫**散文里的上限**：`<词> <= N`（口径写死：词集封闭 + 允许空格）→ `[(行号, N, 行)]`。"""
    out = []
    for i, ln in enumerate(text.splitlines(), 1):
        for w in words:
            m = re.search(re.escape(w) + r"\s*<=\s*(\d+)", ln)
            if m:
                out.append((i, int(m.group(1)), ln.strip()))
                break
    return out


def validate_multi_round(doc):
    """**纯函数**（D7-P4-1）：多轮闭环的结构自洽（轮次可数 · 上限或理由 · 正向终止 · 超限处置）。"""
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["顶层不是映射（yaml 根应是 mapping）"], notes

    loops = doc.get("loops")
    if not isinstance(loops, list) or not loops:
        bad.append("`loops` 为空 ⇒ 多轮闭环没有对象（退化空判 = 本仓头号形态）")
        loops = []
    seen, undecided = {}, []
    for i, lp in enumerate(loops):
        at = f"loops[{i}]"
        if not isinstance(lp, dict):
            bad.append(f"{at} 不是映射")
            continue
        lid = _s(lp.get("id"))
        if not lid or lid in seen:
            bad.append(f"{at} 缺 `id` 或 `id` 重复: {lid!r}")
        seen[lid or i] = lp
        at = f"loops[{lid or i}]"
        for k in ("what", "carrier", "evidence", "delta", "delta_note", "on_exceed"):
            if not _s(lp.get(k)):
                bad.append(f"{at} 缺 `{k}`")
        if lp.get("kind") not in LOOP_KINDS:
            bad.append(f"{at} `kind`={lp.get('kind')!r} 不在封闭集 {LOOP_KINDS} —— "
                       f"**状态推进型**与**同一步重试型**必须分开标（否则就是把两件事说成一件）")
        # ── 轮次**可数** ────────────────────────────────────────────────
        rc = lp.get("round_counter")
        if not isinstance(rc, dict):
            bad.append(f"{at} 缺 `round_counter` ⇒ **轮次从哪来**没写 ⇒ 上限无法核")
        else:
            if rc.get("kind") not in ROUND_COUNTER_KINDS:
                bad.append(f"{at}.round_counter.kind={rc.get('kind')!r} 不在封闭集 {ROUND_COUNTER_KINDS}")
            if not _s(rc.get("how")):
                bad.append(f"{at}.round_counter 缺 `how`（怎么数）")
            if rc.get("kind") == "file-glob" and not _s(rc.get("glob")):
                bad.append(f"{at}.round_counter 是 `file-glob` 但没给 `glob`")
            if rc.get("kind") == "shell-var" and not _s(rc.get("var")):
                bad.append(f"{at}.round_counter 是 `shell-var` 但没给 `var`")
        # ── 上限：**要么给数、要么给理由、要么点名待裁**（三条都不许空）────
        cs = lp.get("cap_state")
        if cs == "capped":
            mr = lp.get("max_rounds")
            if not isinstance(mr, int) or isinstance(mr, bool) or mr < 1:
                bad.append(f"{at} `cap_state: capped` 但 `max_rounds`={mr!r} 不是正整数")
        elif cs == "unbounded-by-design":
            if not _s(lp.get("unbounded_reason")):
                bad.append(f"{at} `cap_state: unbounded-by-design` 但缺 `unbounded_reason` ⇒ "
                           f"**「没有上限」必须给理由**（否则与「忘了写」无法区分）")
        elif cs == "undecided":
            if not _s(lp.get("needs_decision_by")):
                bad.append(f"{at} `cap_state: undecided` 但缺 `needs_decision_by` ⇒ "
                           f"**未定也要写清等谁裁**（点名，不许静默）")
            else:
                undecided.append(lid)
        else:
            bad.append(f"{at} `cap_state`={cs!r} 不在封闭集 {LOOP_CAP_STATES} ⇒ "
                       f"**漏写上限**是本项最要防的形态（上限/理由/待裁三者必须显式其一）")
        # ── EASE 式**正向终止**（"一致即停"）────────────────────────────
        if not _s(lp.get("stop_on_agreement")):
            bad.append(f"{at} 缺 `stop_on_agreement` ⇒ **正向终止条件**没写明 —— "
                       f"上限只管「最多几轮」，「什么时候**可以停**」是另一半（EASE 早停）")
        if not isinstance(lp.get("stop_on_agreement_machine_readable"), bool):
            bad.append(f"{at} `stop_on_agreement_machine_readable` 必须是布尔 "
                       f"（它是人判还是可机判，是 EASE 能不能自动早停的前提）")
        # ── 超限处置：**结构化**地声明"超限时发生什么" ───────────────────
        # ★★ 第一版这里是**文本禁令**（"不得出现『继续』"）⇒ 实测**当场假红**：
        #    `on_exceed: "超限 ⇒ 升级（不是继续）"` 里含「继续」就被判红。
        #    —— 又是"文本口径造假阳性"（本仓已因口径吃过多次亏）。
        #    ⇒ 改为**封闭枚举**：作者必须声明**处置的种类**，机器不猜措辞。
        oek = lp.get("on_exceed_kind")
        if oek not in ON_EXCEED_KINDS:
            bad.append(f"{at} `on_exceed_kind`={oek!r} 不在封闭集 {ON_EXCEED_KINDS} ⇒ "
                       f"**超限时发生什么**必须是一个可枚举的动作（不是一段散文）")
        elif cs == "capped" and oek == "undecided":
            bad.append(f"{at} 已有上限（`cap_state: capped`）却把 `on_exceed_kind` 留成 `undecided` ⇒ "
                       f"**上限没说清超限怎么办 = 上限只有一半**")

    # ── 散文上限：**封闭集**（本批实测抓到的真实缺陷形态）──────────────────
    pw = [_s(w) for w in (doc.get("prose_words") or []) if _s(w)]
    if not pw:
        bad.append("`prose_words` 为空 ⇒ 散文上限没有扫描口径（口径不先定就量 = 本仓吃过三次亏）")
    pcs = doc.get("prose_caps")
    if not isinstance(pcs, list) or not pcs:
        bad.append("`prose_caps` 为空 ⇒ **注释里的上限没人管** —— "
                   "实测它就会落后于代码（本批两处都写 2 而代码是 3）")
        pcs = []
    for i, p in enumerate(pcs):
        at = f"prose_caps[{i}]"
        if not isinstance(p, dict):
            bad.append(f"{at} 不是映射")
            continue
        f_, tok = _s(p.get("file")), _s(p.get("line_token"))
        at = f"prose_caps[{f_}:{tok or i}]"
        for k in ("file", "line_token", "why"):
            if not _s(p.get(k)):
                bad.append(f"{at} 缺 `{k}`")
        if not isinstance(p.get("expect"), int) or isinstance(p.get("expect"), bool):
            bad.append(f"{at} 的 `expect` 必须是整数（散文里应当写的那个数）")

    # ── 文档里的上限：**显式登记 + 唯一锚**（★ 覆盖 `≤` 写法 —— 散文口径只认 `<=`）────
    # 为什么单列一段：`spec/**/*.md` 里的上限句用 `≤`（且**词与运算符之间隔字**）写，
    #   上面 `prose_caps` 要求 `<词> <= N` **紧邻** ⇒ **扫不到**（已登记的逃逸）。
    # 口径（写死）：**每一处**都必须显式登记；锚 `line_token` 在该文件里必须**恰一处**命中，
    #   且该行实测的 `≤N` / `<= N` 必须 == `expect`（核在 `check_multi_round` 里做）。
    # ⚠ 刻意**不做**"扫所有像上限的句子"：那个口径**不可判**（本仓已因口径含糊连踩三次）。
    dcs = doc.get("doc_caps")
    if not isinstance(dcs, list) or not dcs:
        bad.append("`doc_caps` 为空 ⇒ **文档里的上限句没人管** —— "
                   "实测 `spec/**` 就用 `≤` 写上限（`prose_caps` 口径**扫不到**）")
        dcs = []
    for i, d in enumerate(dcs):
        at = f"doc_caps[{i}]"
        if not isinstance(d, dict):
            bad.append(f"{at} 不是映射")
            continue
        f_, tok = _s(d.get("file")), _s(d.get("line_token"))
        at = f"doc_caps[{f_}:{tok or i}]"
        for k in ("file", "line_token", "why"):
            if not _s(d.get(k)):
                bad.append(f"{at} 缺 `{k}`")
        if not isinstance(d.get("expect"), int) or isinstance(d.get("expect"), bool):
            bad.append(f"{at} 的 `expect` 必须是整数（文档里应当写的那个数）")

    unv = doc.get("unverified")
    if not isinstance(unv, list) or not unv:
        bad.append("`unverified` 为空 ⇒ 本项自己未实测 / 未定的部分没登记")

    if not bad:
        n_cap = sum(1 for v in seen.values() if v.get("cap_state") == "capped")
        n_unb = sum(1 for v in seen.values() if v.get("cap_state") == "unbounded-by-design")
        kinds = sorted({_s(v.get("kind")) for v in seen.values()})
        notes.append(f"闭环 {len(seen)} 条 · kind {kinds} · 有上限 {n_cap} · 无上限(有理由) {n_unb} · "
                     f"**未定 {len(undecided)}**"
                     f"{'（点名: ' + ', '.join(undecided) + '）' if undecided else ''} · "
                     f"散文上限登记 {len(pcs)} 处（词集 {pw}） · 文档上限登记 {len(dcs)} 处")
    return bad, notes


def check_multi_round(ctx, doc=None):
    """D7-P4-1: 多轮闭环 —— **轮数上限有判据**（含与代码**实提取**对账 + 散文上限封闭集）。

    ★ `doc` 是可注入缝（测试用）：`None` ⇒ 从 `inventory/multi-round.yaml` 读。
    """
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 multi-round 断言", []
    if doc is None:
        if not MULTI_ROUND_INV.exists():
            return "FAIL", "inventory/multi-round.yaml 缺失（本断言的登记依据）", []
        try:
            doc = yaml.safe_load(_read_text(MULTI_ROUND_INV)) or {}
        except Exception as e:
            return "FAIL", f"inventory/multi-round.yaml 解析失败: {type(e).__name__}: {e}", []

    bad, notes = validate_multi_round(doc)
    cache = {}

    def _text(rel):
        if rel not in cache:
            cache[rel] = _read_text(ROOT / rel)
        return cache[rel]

    # 1) ★★ 与**代码实提取**对账：每个 `cap_sites` 都要实测到**恰一处**上限；
    #    **各 site 必须同值**；且 `max_rounds == 该值 + plus_extra 之和`。
    #    ★ 为什么是**复数** site：本条闭环有**两份实现**（站上 bash body + 本地 PS）——
    #      那正是"同一事实两个定义点"最容易漂的地方（本批实测的注释漂移就发生在旁边）。
    for lp in (doc.get("loops") or []):
        if not isinstance(lp, dict):
            continue
        lid = _s(lp.get("id")) or "?"
        sites = [x for x in (lp.get("cap_sites") or []) if isinstance(x, dict)]
        if not sites:
            continue                      # 无代码侧实现（如受理侧回环）⇒ 不对账；**不是"通过"**
        caps = []
        for s in sites:
            rel = _s(s.get("file"))
            where = _s(s.get("where"))
            if not where:
                bad.append(f"loops[{lid}].cap_sites 有一条缺 `where` ⇒ 两个定义点必须可区分")
                where = "?"
            if not rel or not (ROOT / rel).exists():
                bad.append(f"loops[{lid}].cap_sites 的 file={rel!r} 不存在 ⇒ "
                           f"对账不可判（**不可判 ≠ 通过**）")
                continue
            hits = extract_loop_cap(_text(rel), _s(s.get("marker")), _s(s.get("op")))
            if len(hits) != 1:
                bad.append(f"loops[{lid}] 的 site({where})：在 {rel} 按锚点 "
                           f"({s.get('marker')!r}, {s.get('op')!r}) 实测到 **{len(hits)} 处**上限"
                           f"（要求恰 1 处）⇒ 要么上限多了个定义点、要么口径过期；"
                           f"行号 {[n for n, _ in hits]}")
                continue
            caps.append((where, hits[0][0], hits[0][1]))
        if not caps:
            continue
        if len({v for _, _, v in caps}) > 1:
            bad.append(f"loops[{lid}] **多处实现的上限不一致**: "
                       + " / ".join(f"{w}@{ln}={v}" for w, ln, v in caps)
                       + " ⇒ 同一事实两个定义点，必须同步（或合并为一处）")
            continue
        rel0 = _s(sites[0].get("file"))
        n_extra = 0
        for x in [y for y in (lp.get("plus_extra") or []) if isinstance(y, dict)]:
            anc, cnt = _s(x.get("anchor")), x.get("count")
            if not anc or not isinstance(cnt, int) or isinstance(cnt, bool):
                bad.append(f"loops[{lid}].plus_extra 缺 `anchor` 或 `count` 非整数")
                continue
            if anc not in _text(rel0):
                bad.append(f"loops[{lid}].plus_extra 的锚点 {anc!r} 在 {rel0} 里**找不到** ⇒ "
                           f"登记腐化（那段代码改了 / 删了）")
                continue
            n_extra += cnt
        code_cap = caps[0][2]
        want = code_cap + n_extra
        if isinstance(lp.get("max_rounds"), int) and lp.get("max_rounds") != want:
            bad.append(f"loops[{lid}] 的 `max_rounds`={lp.get('max_rounds')} 与代码**不符**："
                       f"实测循环上限 {code_cap}"
                       f"{f' + plus_extra {n_extra}' if n_extra else ''} = {want} ⇒ "
                       f"改真值表**或**改代码（两处必须同时说同一个数）")

    # 2) ★★ 散文上限：逐处核 + **完整性**（文件里每一处都要被登记）
    pw = [_s(w) for w in (doc.get("prose_words") or []) if _s(w)]
    pcs = [p for p in (doc.get("prose_caps") or []) if isinstance(p, dict)]
    for rel in sorted({_s(p.get("file")) for p in pcs if _s(p.get("file"))}):
        if not (ROOT / rel).exists():
            bad.append(f"prose_caps 指向的 {rel} 不存在 ⇒ 登记腐化")
            continue
        t = _text(rel)
        caps_all = {int(x) for x in CODE_CAP_RE.findall(t)}
        found = scan_prose_caps(t, pw)
        for ln_no, val, txt in found:
            covered = [p for p in pcs if _s(p.get("line_token")) and _s(p.get("line_token")) in txt]
            if not covered:
                bad.append(f"★**未登记的散文上限**: {rel}:{ln_no} ⇒ `{txt[:100]}` —— "
                           f"散文里的上限**逐处登记**，否则它会悄悄落后于代码")
        for p in pcs:
            if _s(p.get("file")) != rel:
                continue
            tok = _s(p.get("line_token"))
            lines = [(i, l) for i, l in enumerate(t.splitlines(), 1) if tok in l]
            if not lines:
                bad.append(f"prose_caps 登记的锚 {tok!r} 在 {rel} 里**找不到** ⇒ 口径过期（代码改了？）")
                continue
            if len(lines) > 1:
                bad.append(f"prose_caps 的锚 {tok!r} 在 {rel} 里命中 {len(lines)} 行 ⇒ 锚不唯一")
                continue
            ln_no, txt = lines[0]
            vals = [re.search(re.escape(w) + r"\s*<=\s*(\d+)", txt) for w in pw]
            got = next((int(m.group(1)) for m in vals if m), None)
            if got is None:
                bad.append(f"{rel}:{ln_no} 锚在但**不再含上限写法** ⇒ 口径过期"
                           f"（散文改成别的说法了？那该重定口径，而不是留着这条）")
            elif got != p.get("expect"):
                bad.append(f"★★ 散文上限与登记**不符**: {rel}:{ln_no} 实测 {got} ≠ "
                           f"`expect` {p.get('expect')} ⇒ `{txt[:100]}`")
            elif caps_all and got not in caps_all:
                bad.append(f"{rel}:{ln_no} 的 `expect`={got} **不落在该文件的循环上限集合** "
                           f"{sorted(caps_all)} 里 ⇒ 像随手编的数")

    # 3) ★★ 文档上限：显式登记 + **唯一锚** + 行内实测 == `expect`
    #    ★ 与 `prose_caps` 分开：那份口径只认 `<词> <= N`（紧邻），文档用 `≤` 且隔字 ⇒ 扫不到。
    #    锚**必须唯一**（本仓已因锚不唯一吃过亏）；找不到锚 ⇒ 口径过期；命中多处 ⇒ 锚不唯一。
    for i, d in enumerate([x for x in (doc.get("doc_caps") or []) if isinstance(x, dict)]):
        rel, tok = _s(d.get("file")), _s(d.get("line_token"))
        at = f"doc_caps[{rel}:{tok or i}]"
        if not rel or not (ROOT / rel).exists():
            bad.append(f"{at} 的 file={rel!r} 不存在 ⇒ 对账不可判（**不可判 ≠ 通过**）")
            continue
        lines = [(j, l) for j, l in enumerate(_text(rel).splitlines(), 1) if tok and tok in l]
        if not lines:
            bad.append(f"{at} 的锚 {tok!r} 在 {rel} 里**找不到** ⇒ 口径过期（文档改了？）")
            continue
        if len(lines) > 1:
            bad.append(f"{at} 的锚 {tok!r} 在 {rel} 里命中 {len(lines)} 行 ⇒ **锚不唯一**")
            continue
        ln_no, txt = lines[0]
        m = DOC_CAP_RE.search(txt)
        if not m:
            bad.append(f"{rel}:{ln_no} 锚在但**不再含上限写法**（`≤N` / `<= N`）⇒ 口径过期"
                       f"（文档改成别的说法了？那该重定口径，而不是留着这条）")
        elif int(m.group(1)) != d.get("expect"):
            bad.append(f"★★ 文档上限与登记**不符**: {rel}:{ln_no} 实测 {m.group(1)} ≠ "
                       f"`expect` {d.get('expect')} ⇒ `{txt[:100]}`")

    if bad:
        return "FAIL", " · ".join(notes) if notes else "见明细", bad
    und = [_s(v.get("id")) for v in (doc.get("loops") or [])
           if isinstance(v, dict) and v.get("cap_state") == "undecided"]
    if und:
        # 上限**未定**：**点名 + WARN**（不是漏写 —— 漏写在 `validate_` 里已经是红了）
        return "WARN", " · ".join(notes), [
            f"上限未定的闭环 {len(und)} 条（待裁，点名）: " + ", ".join(und)]
    return "PASS", " · ".join(notes), []


# ── D7-P4-2 (2026-09-26)「中断态双侧口径 + 不可信证据」──────────────────────────
#   Ds 简报 11（§4.5）：**双向对称性检验（防死锁）** —— 两端都不把 `input-required` 当可完成态；
#     ⇒ D7 必须**双方同时声明**口径，否则**一端等待、一端失败的死锁**。
#   Ds 简报 18（§4.11⑥）：**把对方的文本当不可信证据**，其内部提及**不触发指令解析**。
#   ★★ `deadlock_risk` **由判据算、不由真值表填**（自报 = 同一事实两个定义点 + 空转软约束）。
INTERRUPT_INV = ROOT / "inventory" / "interruption-and-untrusted.yaml"
SIDE_ACTIONS = ("awaiting-peer", "unblocking-peer", "failing", "self-contained")
COMBINED_STATES = ("retry", "terminal-fail", "human", "escalate")
# 能**终结对方等待**的动作：主动解除 或 失败退出（后者让对方"等到一个结果"而不是空等）。
_UNBLOCKERS = ("unblocking-peer", "failing")


def deadlock_risk(main_action, station_action):
    """算两岸组合的**死锁风险** → `(risk, why)`；`risk ∈ {none, silent, mutual}`。

    规则直接来自 Ds 简报 §4.5 的 **方向反转对称**：
      **一端挂起（`awaiting-peer`）⇒ 另一端必须主动终结那个等待**（解除 / 失败）；
      否则等方**永远等** —— 那正是本仓 O-79 实测过的**静默死锁**。

    ⚠ 为什么做成**函数**而不是真值表里的一个字段：自报的话，"填了 none"就没人验；
      而**用真事故校准它**（`history[].as_pair` 必须算出非 none）才能证明规则不是空转的。
    """
    m, s = main_action, station_action
    if m == "awaiting-peer" and s == "awaiting-peer":
        return "mutual", "两侧都在等对方（互等）"
    if m == "awaiting-peer" and s not in _UNBLOCKERS:
        return "silent", f"主控在等对方，而站上侧的动作是 {s!r} ⇒ 那个等待**不会被终结**"
    if s == "awaiting-peer" and m not in _UNBLOCKERS:
        return "silent", f"站上在等对方，而主控侧的动作是 {m!r} ⇒ 那个等待**不会被终结**"
    if m == "awaiting-peer" or s == "awaiting-peer":
        return "none", "一端挂起，另一端**主动终结**（解除 / 失败）⇒ 方向反转对称成立"
    return "none", "两岸都不在等对方"


def validate_interruption(doc):
    """**纯函数**（D7-P4-2）：中断态两岸口径 + 不可信输入的结构自洽。"""
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["顶层不是映射（yaml 根应是 mapping）"], notes

    ips = doc.get("interruptions")
    if not isinstance(ips, list) or not ips:
        bad.append("`interruptions` 为空 ⇒ 中断态没有对象（退化空判 = 本仓头号形态）")
        ips = []
    seen, risky = set(), []
    for i, it in enumerate(ips):
        at = f"interruptions[{i}]"
        if not isinstance(it, dict):
            bad.append(f"{at} 不是映射")
            continue
        iid = _s(it.get("id"))
        if not iid or iid in seen:
            bad.append(f"{at} 缺 `id` 或 `id` 重复: {iid!r}")
        seen.add(iid)
        at = f"interruptions[{iid or i}]"
        # ★★「**两侧**都要声明」—— 缺一侧就是 Ds 说的"一端没写"
        for k in ("what", "main_side", "station_side", "evidence"):
            if not _s(it.get(k)):
                bad.append(f"{at} 缺 `{k}` ⇒ "
                           + ("**只有一端声明了口径**（Ds：一端等待、一端失败的死锁就出在这里）"
                              if k in ("main_side", "station_side") else "字段没写"))
        ma, sa = it.get("main_action"), it.get("station_action")
        for nm, v in (("main_action", ma), ("station_action", sa)):
            if v not in SIDE_ACTIONS:
                bad.append(f"{at} `{nm}`={v!r} 不在封闭集 {SIDE_ACTIONS} ⇒ "
                           f"**谁在等谁**无法判 ⇒ 死锁风险也就判不了")
        if it.get("combined") not in COMBINED_STATES:
            bad.append(f"{at} `combined`={it.get('combined')!r} 不在封闭集 {COMBINED_STATES}")
        if ma in SIDE_ACTIONS and sa in SIDE_ACTIONS:
            risk, why = deadlock_risk(ma, sa)
            if risk != "none":
                if not _s(it.get("mitigation")):
                    bad.append(f"{at} 判出死锁风险 **{risk}**（{why}）却**没有 `mitigation`** ⇒ "
                               f"没人管这个等待怎么被终结")
                else:
                    risky.append((iid, risk))

    # ── ★ 用**真事故**校准规则：历史死锁必须能被算出来 ──────────────────────
    hist = doc.get("history")
    if not isinstance(hist, list) or not hist:
        bad.append("`history` 为空 ⇒ **修掉的静默死锁没登记** ⇒ 它会回来（且没人知道当初为什么改）")
        hist = []
    for i, h in enumerate(hist):
        at = f"history[{i}]"
        if not isinstance(h, dict):
            bad.append(f"{at} 不是映射")
            continue
        hid = _s(h.get("id"))
        at = f"history[{hid or i}]"
        for k in ("symptom", "root_cause", "fix", "evidence"):
            if not _s(h.get(k)):
                bad.append(f"{at} 缺 `{k}`")
        pair = h.get("as_pair")
        if not isinstance(pair, dict) or pair.get("main_action") not in SIDE_ACTIONS \
                or pair.get("station_action") not in SIDE_ACTIONS:
            bad.append(f"{at} `as_pair` 必须给两侧动作（∈ 封闭集）—— "
                       f"它是**校准/先验红**：真事故必须能被 `deadlock_risk()` 算出来")
        else:
            got, why = deadlock_risk(pair["main_action"], pair["station_action"])
            exp = h.get("expected_risk")
            if exp not in ("silent", "mutual"):
                bad.append(f"{at} `expected_risk`={exp!r} 必须是 silent / mutual "
                           f"（历史死锁若算成 none，那它就不是死锁）")
            elif got != exp:
                bad.append(f"{at} ★★ **规则算不出这条真事故**：实测 {got!r} ≠ `expected_risk` {exp!r}"
                           f"（{why}）⇒ **判据是空转的**，先修规则")
        g = h.get("regression_guard")
        if not isinstance(g, dict):
            bad.append(f"{at} 缺 `regression_guard` ⇒ 修过的坑没有护栏")
        else:
            gk, gid = _s(g.get("kind")), _s(g.get("id"))
            if gk not in ("fixture", "test"):
                bad.append(f"{at}.regression_guard.kind={gk!r} 不在封闭集 {{fixture, test}}")
            elif not gid:
                bad.append(f"{at}.regression_guard 缺 `id`")
        # 历史条目的动作组合必须与 `interruptions` 里**当前**的处置不同（否则"修了什么"就没写清）

    # ── 不可信输入（第 18 条）─────────────────────────────────────────────
    uts = doc.get("untrusted_inputs")
    if not isinstance(uts, list) or not uts:
        bad.append("`untrusted_inputs` 为空 ⇒ 不可信证据没有对象")
        uts = []
    un_und = []
    for i, u in enumerate(uts):
        at = f"untrusted_inputs[{i}]"
        if not isinstance(u, dict):
            bad.append(f"{at} 不是映射")
            continue
        uid = _s(u.get("id"))
        at = f"untrusted_inputs[{uid or i}]"
        for k in ("id", "what", "carrier"):
            if not _s(u.get(k)):
                bad.append(f"{at} 缺 `{k}`")
        d = u.get("declared")
        if not isinstance(d, bool):
            bad.append(f"{at} 缺 `declared` 布尔 ⇒ **声明了没有**必须可判")
        elif d:
            if not _s(u.get("declared_in")) or not _s(u.get("marker")):
                bad.append(f"{at} `declared: true` 但缺 `declared_in` / `marker` ⇒ "
                           f"无法去文件里**真找**那句声明（自报不算）")
        else:
            if not _s(u.get("why_not")):
                bad.append(f"{at} `declared: false` 但缺 `why_not` ⇒ "
                           f"**「没声明」也要给理由**（否则与「忘了」无法区分）")
            else:
                un_und.append(uid)

    tis = doc.get("trusted_inputs")
    if not isinstance(tis, list) or not tis:
        bad.append("`trusted_inputs` 为空 ⇒ **什么不算不可信**没写 ⇒ 边界靠猜")

    unv = doc.get("unverified")
    if not isinstance(unv, list) or not unv:
        bad.append("`unverified` 为空 ⇒ 本项自己未实测 / 未定的部分没登记")

    if not bad:
        notes.append(f"中断态 {len(seen)} 条（两岸口径齐）· 有死锁风险的 {len(risky)}"
                     f"{'（' + ', '.join(f'{a}:{b}' for a, b in risky) + '）' if risky else ''} · "
                     f"已修事故 {len(hist)} 条 · 不可信输入 {len(uts)} 条（未声明的 {len(un_und)}"
                     f"{'：' + ', '.join(un_und) if un_und else ''}）· 不算不可信 {len(tis)} 类")
    return bad, notes


def check_interruption(ctx, doc=None):
    """D7-P4-2: 中断态两岸口径（防死锁）+ 不可信证据规则 + 已修死锁的回归护栏。

    ★ `doc` 可注入（测试用）；`None` ⇒ 读 `inventory/interruption-and-untrusted.yaml`。
      签名与 `check_memory_gates` / `check_multi_round` 同形 —— **第一参数必须是 `ctx`**
      （harness 以 `c["fn"]({})` 调用 ⇒ 少写 `ctx` 会把 `{}` 当成 `doc`，判据静默判错对象）。
    """
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 interruption 断言", []
    if doc is None:
        if not INTERRUPT_INV.exists():
            return "FAIL", "inventory/interruption-and-untrusted.yaml 缺失（本断言的登记依据）", []
        try:
            doc = yaml.safe_load(_read_text(INTERRUPT_INV)) or {}
        except Exception as e:
            return "FAIL", f"inventory/interruption-and-untrusted.yaml 解析失败: {type(e).__name__}: {e}", []

    bad, notes = validate_interruption(doc)

    # 1) ★★ `declared: true` ⇒ **去文件里真找**那句声明（自报不算）
    for u in (doc.get("untrusted_inputs") or []):
        if not isinstance(u, dict) or u.get("declared") is not True:
            continue
        rel, mk = _s(u.get("declared_in")), _s(u.get("marker"))
        if not rel or not mk:
            continue
        if not (ROOT / rel).exists():
            bad.append(f"untrusted_inputs[{_s(u.get('id'))}] 的 `declared_in`={rel!r} 不存在 ⇒ "
                       f"声明无处可查（**不可判 ≠ 已声明**）")
            continue
        if mk not in _read_text(ROOT / rel):
            bad.append(f"★ untrusted_inputs[{_s(u.get('id'))}] 声称已在 {rel} 里声明不可信，"
                       f"但**该文件里找不到** {mk!r} ⇒ **自报不算声明**（第 18 条落空）")

    # 2) ★★ 已修事故的**回归护栏必须真实存在**
    for h in (doc.get("history") or []):
        if not isinstance(h, dict):
            continue
        g = h.get("regression_guard")
        if not isinstance(g, dict):
            continue
        gk, gid = _s(g.get("kind")), _s(g.get("id"))
        if not gid:
            continue
        if gk == "fixture":
            if gid not in _read_text(ROOT / "ops" / "station-bin" / "_fm_golden_test.ps1"):
                bad.append(f"history[{_s(h.get('id'))}] 的回归护栏夹具 **{gid}** 在 "
                           f"`_fm_golden_test.ps1` 里找不到 ⇒ 护栏是空头的")
        elif gk == "test":
            if not (ROOT / "tests" / gid).exists():
                bad.append(f"history[{_s(h.get('id'))}] 的回归护栏测试 {gid} 不存在 ⇒ 护栏是空头的")

    if bad:
        return "FAIL", " · ".join(notes) if notes else "见明细", bad
    return "PASS", " · ".join(notes), []


# ── D7-P4-3 (2026-09-26)「rubric + 自环盲区」────────────────────────────────────
#   Ds 简报 15（§4.10④）：rubric **只管本次引入的问题**（防意见被历史债务淹没）。
#   Ds 简报 12（§4.7）：**自环盲区显式登记** —— 「自环永远走我方两端的善意实现；
#     异构第三方 A2A server 的真实差异未测」⇒ ds 的做法就是**登记**，本机群照做。
#   Ds 简报 21（§4.13）：派生边表 ⇒ ⚠ 路线总表 §4.5 已列**非范围** ⇒ 只登记**触发条件**。
RUBRIC_INV = ROOT / "inventory" / "rubric-and-blindspots.yaml"
BLINDSPOT_KINDS = ("implementation", "dispatch", "external")
GUARD_KINDS = ("check", "test", "na")


def validate_rubric_blindspot(doc, known_checks):
    """**纯函数**（D7-P4-3）：rubric 必含条 + 自环盲区 + 派生边条件。"""
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["顶层不是映射（yaml 根应是 mapping）"], notes

    # ── ① rubric：**已落盘**，把它关键的几句变成**可机核的存在性** ──────────────
    #   ★ 为什么核"必须含哪几条"：rubric 是**纯文本资源**，删掉一句没人会知道 ——
    #     而这几句正是它防住的偏差（历史债务 / 自证 / verbosity / 翻案 / 不可信输入）。
    rb = doc.get("rubric")
    if not isinstance(rb, dict) or not _s(rb.get("file")):
        bad.append("缺 `rubric.file` ⇒ rubric 落点没写（退出判据第 1 条就是「rubric 落盘」）")
        rb = {}
    mc = rb.get("must_contain")
    if not isinstance(mc, list) or not mc:
        bad.append("`rubric.must_contain` 为空 ⇒ **关键纪律被删掉也没人知道**")
        mc = []
    seen_mc = set()
    for i, m in enumerate(mc):
        at = f"rubric.must_contain[{i}]"
        if not isinstance(m, dict):
            bad.append(f"{at} 不是映射")
            continue
        mid = _s(m.get("id"))
        if not mid or mid in seen_mc:
            bad.append(f"{at} 缺 `id` 或 `id` 重复: {mid!r}")
        seen_mc.add(mid)
        at = f"rubric.must_contain[{mid or i}]"
        for k in ("marker", "why"):
            if not _s(m.get(k)):
                bad.append(f"{at} 缺 `{k}`")
    # ★ 读取方式必须**显式编码**（否则 PS 5.1 下中文资源会乱码）—— 这条是"防改回去"
    rd = rb.get("reader")
    if isinstance(rd, dict):
        if not _s(rd.get("file")) or not _s(rd.get("marker")):
            bad.append("`rubric.reader` 缺 `file` / `marker`")
        elif not _s(rd.get("why")):
            bad.append("`rubric.reader` 缺 `why` ⇒ 没说清为什么要显式编码")

    # ── ② 自环盲区：**显式登记**（第 12 条）────────────────────────────────
    bs = doc.get("blindspots")
    if not isinstance(bs, list) or not bs:
        bad.append("`blindspots` 为空 ⇒ **自环盲区没有登记**（第 12 条明写要显式登记）")
        bs = []
    seen_bs, na_guards = set(), []
    for i, b in enumerate(bs):
        at = f"blindspots[{i}]"
        if not isinstance(b, dict):
            bad.append(f"{at} 不是映射")
            continue
        bid = _s(b.get("id"))
        if not bid or bid in seen_bs:
            bad.append(f"{at} 缺 `id` 或 `id` 重复: {bid!r}")
        seen_bs.add(bid)
        at = f"blindspots[{bid or i}]"
        for k in ("what", "why_blind", "evidence"):
            if not _s(b.get(k)):
                bad.append(f"{at} 缺 `{k}` ⇒ "
                           + ("**盲区必须写清为什么互审看不见**" if k == "why_blind" else "字段没写"))
        if b.get("kind") not in BLINDSPOT_KINDS:
            bad.append(f"{at} `kind`={b.get('kind')!r} 不在封闭集 {BLINDSPOT_KINDS}")
        g = b.get("other_guard")
        if not isinstance(g, dict):
            bad.append(f"{at} 缺 `other_guard` ⇒ **本仓用什么别的机制覆盖它**必须写（没有就写 `na`）")
        else:
            gk, ref = _s(g.get("kind")), _s(g.get("ref"))
            if gk not in GUARD_KINDS:
                bad.append(f"{at}.other_guard.kind={gk!r} 不在封闭集 {GUARD_KINDS}")
            elif gk == "check":
                if ref not in known_checks:
                    bad.append(f"{at}.other_guard 指的判据 {ref!r} **不是已注册的 CHECKS id** ⇒ 挂名")
            elif gk == "test":
                if not ref or not (ROOT / "tests" / ref).exists():
                    bad.append(f"{at}.other_guard 指的测试 {ref!r} 不存在")
            elif not _s(g.get("why")):
                bad.append(f"{at}.other_guard 是 `na` 但缺 `why` ⇒ **「没有替代机制」也要给理由**")
            if gk == "na":
                na_guards.append(bid)
    # ★★ 本仓**最实质**的盲区：三站互审走**同一份实现** ⇒ 同源代码缺陷两侧同时出现
    if "impl-same-source" not in seen_bs:
        bad.append("★ 缺 `impl-same-source` 盲区 ⇒ **本仓最实质的那条没登记**："
                   "三站互审走**同一份 `agent-cli.ps1`** ⇒ 实现层缺陷会在两侧**同时**出现，"
                   "互审在结构上**不可能**发现它（与「跨站≠跨族」是**正交**的两件事）")

    # ── ③ 派生边表：**条件触发**（第 21 条 + §4.5 非范围）────────────────────
    de = doc.get("derived_edges")
    if not isinstance(de, dict):
        bad.append("缺 `derived_edges` 段 ⇒ 第 21 条**连登记都没有**（非范围不等于不写）")
    else:
        if de.get("status") not in ("deferred", "done"):
            bad.append(f"`derived_edges.status`={de.get('status')!r} 不在封闭集 {{deferred, done}}")
        elif de.get("status") == "deferred" and not _s(de.get("condition")):
            bad.append("`derived_edges` 是 `deferred` 但缺 `condition` ⇒ "
                       "**触发条件没写死 ⇒ 它会永远挂着或悄悄做掉**")
        if not _s(de.get("why")):
            bad.append("`derived_edges` 缺 `why`")

    unv = doc.get("unverified")
    if not isinstance(unv, list) or not unv:
        bad.append("`unverified` 为空 ⇒ 本项自己未实测 / 未定的部分没登记")

    if not bad:
        notes.append(f"rubric 必含 {len(seen_mc)} 条 · 自环盲区 {len(seen_bs)} 条"
                     f"（无替代机制的 {len(na_guards)}"
                     f"{'：' + ', '.join(na_guards) if na_guards else ''}）· "
                     f"派生边 status={de.get('status') if isinstance(de, dict) else '?'}")
    return bad, notes


def check_rubric_blindspot(ctx, doc=None):
    """D7-P4-3: rubric（含"只报本次引入的问题"）+ 自环盲区显式登记 + 派生边条件。"""
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 rubric-blindspot 断言", []
    if doc is None:
        if not RUBRIC_INV.exists():
            return "FAIL", "inventory/rubric-and-blindspots.yaml 缺失（本断言的登记依据）", []
        try:
            doc = yaml.safe_load(_read_text(RUBRIC_INV)) or {}
        except Exception as e:
            return "FAIL", f"inventory/rubric-and-blindspots.yaml 解析失败: {type(e).__name__}: {e}", []

    bad, notes = validate_rubric_blindspot(doc, known_checks={c["id"] for c in CHECKS})

    # 1) ★★ rubric 必含条：**去那个文件里真找**（不是自报"我写了"）
    rb = doc.get("rubric") if isinstance(doc.get("rubric"), dict) else {}
    rel = _s(rb.get("file"))
    if rel:
        if not (ROOT / rel).exists():
            bad.append(f"`rubric.file`={rel!r} 不存在 ⇒ **返回内容是个错误串**（`RUBRIC_UNAVAILABLE`），"
                       f"判官拿不到 rubric（**不可判 ≠ 通过**）")
        else:
            txt = _read_text(ROOT / rel)
            for m in [x for x in (rb.get("must_contain") or []) if isinstance(x, dict)]:
                mk = _s(m.get("marker"))
                if mk and mk not in txt:
                    bad.append(f"★ rubric 里**找不到**必含句 {mk!r}"
                               f"（id={_s(m.get('id'))}）⇒ 那条纪律被删了/改了措辞；"
                               f"改措辞请**同步改真值表**（别让它悄悄失守）")

    # 2) ★ rubric/tmpl 的读取必须**显式编码**（否则 PS 5.1 下中文资源乱码）
    rd = rb.get("reader")
    if isinstance(rd, dict) and _s(rd.get("file")) and _s(rd.get("marker")):
        rf = _s(rd["file"])
        if not (ROOT / rf).exists():
            bad.append(f"`rubric.reader.file`={rf!r} 不存在 ⇒ 读取方式不可判")
        elif _s(rd["marker"]) not in _read_text(ROOT / rf):
            bad.append(f"★ `{rf}` 里找不到 `{_s(rd['marker'])}` ⇒ "
                       f"**读取可能退回裸 `Get-Content`**（PS 5.1 默认 ANSI ⇒ 中文资源乱码）")

    if bad:
        return "FAIL", " · ".join(notes) if notes else "见明细", bad
    return "PASS", " · ".join(notes), []


CAPABILITY_INV = ROOT / "inventory" / "capability-inventory.yaml"
CAP_DOMAINS = ("verify", "identity", "orchestration", "meta")
CAP_VERDICTS = ("present", "partial", "absent")
CAP_BASIS = ("E1", "E2")
CAP_WHY_KINDS = ("na", "not-done", "pending-decision")
CAP_CARRIER_KINDS = ("file", "gate", "table")


def _ds(v):
    """日期字段取串：**接受 yaml 把裸日期解析出的 `date` / `datetime`**。

    ★ 为什么单独一个函数：`updated: 2026-09-27` 会被 yaml 解析成 **`datetime.date`**，
    而 `_s()` 对非字符串一律返回空 ⇒ 判据会报「缺 `updated`」，**而人看表里明明有** ——
    这是**口径陷阱**（同族：O-93 的『同一棵树三种口径三个结果』）。
    ⇒ 判据对**同一事实的不同合法写法**要宽容（裸日期 / 带引号都收），只对**真的没有**严格。
    """
    if isinstance(v, str):
        return v.strip()
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return ""


def validate_capability_inventory(doc, known_checks, exists_fn):
    """**纯函数**（O-105）：能力 → 载体 → 判定。

    ★★ 它要防的是「**能力的存在性靠自报**」—— 所以 present / partial **必须给可核载体**，
    判据去**仓里真找**（file 存在 / gate 是已注册 CHECKS id / table 在 inventory/）；
    absent **必须写理由**（本仓纪律:「不适用也是一种结论，必须写下来」）**与读数** `evidence`
    —— 「本仓没有这个机制」**本身也是断言**，absent **不豁免** evidence（真表首版即此错）。
    """
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["顶层不是映射（yaml 根应是 mapping）"], notes

    # ── ① 表级：口径 + 读数日期（它是**增长型载体**，没日期读者不知道是哪天的树）──
    m = doc.get("metric")
    if not isinstance(m, dict) or not (_s(m.get("name")) and _s(m.get("unit")) and _s(m.get("scope"))):
        bad.append("缺 `metric` 的 `name`/`unit`/`scope` ⇒ **增长型计数没有口径** —— "
                   "口径一变，表里所有数字立刻失去意义（§87.6 的『同日漂移』就是这类）")
    if not _ds(doc.get("updated")):
        bad.append("缺 `updated` ⇒ **没有读数日期** ⇒ 读者无法判断这表是哪一天的树")

    # ── ② 声明的封闭集 == 判据实现（防口径漂移：改了代码没改表 / 反之）──────────
    for k, allowed in (("domains", CAP_DOMAINS), ("verdicts", CAP_VERDICTS),
                       ("basis", CAP_BASIS), ("why_kinds", CAP_WHY_KINDS),
                       ("carrier_kinds", CAP_CARRIER_KINDS)):
        v = doc.get(k)
        if not isinstance(v, list) or tuple(v) != allowed:
            bad.append(f"`{k}`={v!r} 应为封闭集 {list(allowed)} ⇒ "
                       f"**声明的口径必须与判据实现一致**（不一致时，本判据自己就是假绿）")

    items = doc.get("items")
    if not isinstance(items, list) or not items:
        return bad + ["`items` 为空 ⇒ **判据没有对象**（退化空判，本仓头号形态）"], notes

    # ── ③ 逐项 ─────────────────────────────────────────────────────────────
    seen = set()
    for i, it in enumerate(items):
        at = f"items[{i}]"
        if not isinstance(it, dict):
            bad.append(f"{at} 不是映射")
            continue
        cid = _s(it.get("id"))
        if not cid or cid in seen:
            bad.append(f"{at} 缺 `id` 或 `id` 重复: {cid!r}")
        seen.add(cid)
        at = f"items[{cid or i}]"
        for k in ("domain", "what", "evidence"):
            if not _s(it.get(k)):
                bad.append(f"{at} 缺 `{k}`")
        if it.get("domain") not in CAP_DOMAINS:
            bad.append(f"{at} `domain`={it.get('domain')!r} 不在封闭集 {CAP_DOMAINS}")
        if it.get("basis") not in CAP_BASIS:
            bad.append(f"{at} `basis`={it.get('basis')!r} 不在封闭集 {CAP_BASIS} ⇒ "
                       f"**取证方式必须写明**（E1 读文件 / E2 跑命令）")
        vd = it.get("verdict")
        if vd not in CAP_VERDICTS:
            bad.append(f"{at} `verdict`={vd!r} 不在封闭集 {CAP_VERDICTS}")
            continue

        # ★★ 核心：有载体 ⇒ 必须**可达**（去仓里真找，不采信自报）
        if vd in ("present", "partial"):
            cs = it.get("carriers")
            if not isinstance(cs, list) or not cs:
                bad.append(f"{at} verdict={vd} ⇒ **必须给载体**（否则是自报）")
            else:
                for j, c in enumerate(cs):
                    cat = f"{at}.carriers[{j}]"
                    if not isinstance(c, dict):
                        bad.append(f"{cat} 不是映射")
                        continue
                    ck, ref = c.get("kind"), _s(c.get("ref"))
                    if ck not in CAP_CARRIER_KINDS:
                        bad.append(f"{cat}.kind={ck!r} 不在封闭集 {CAP_CARRIER_KINDS}")
                        continue
                    if not ref:
                        bad.append(f"{cat} 缺 `ref`")
                        continue
                    if ck == "gate" and ref not in known_checks:
                        bad.append(f"{cat} 指的判据 {ref!r} **不是已注册的 CHECKS id** ⇒ 挂名"
                                   f"（判据写了但没人跑 —— 本仓最典型的一类假绿）")
                    elif ck == "file" and not exists_fn(ref):
                        bad.append(f"{cat} 指的仓内文件 {ref!r} **不存在**")
                    elif ck == "table" and not exists_fn(
                            ref if "/" in ref else f"inventory/{ref}"):
                        bad.append(f"{cat} 指的真值表 {ref!r} **不存在**")
        if vd == "partial" and not _s(it.get("gap")):
            bad.append(f"{at} verdict=partial 但缺 `gap` ⇒ **缺哪一块必须写清**"
                       f"（否则 partial 是个托词，读者无法判断它离 present 差多少）")
        if vd == "absent":
            wk = it.get("why_kind")
            if wk not in CAP_WHY_KINDS:
                bad.append(f"{at} verdict=absent 但 `why_kind`={wk!r} 不在封闭集 {CAP_WHY_KINDS}"
                           f"（不适用 / 未做 / 待裁 —— 三者含义**不同**，混起来就不可判）")
            if not _s(it.get("why")):
                bad.append(f"{at} verdict=absent 但缺 `why` ⇒ "
                           f"**「不做」也是一种结论，必须写下来**")

    # ── ④ 自指：本表必须盘到自己（否则「能力盘点」这项能力本身没被盘点）────────
    sid = _s(doc.get("self_id"))
    if not sid:
        bad.append("缺 `self_id` ⇒ 表没有声明**哪一项是它自己**")
    elif sid not in seen:
        bad.append(f"`self_id`={sid!r} 不在 items 里 ⇒ "
                   f"**「能力盘点」这项能力本身没被盘点**（自指缺口）")

    unv = doc.get("unverified")
    if not isinstance(unv, list) or not unv:
        bad.append("`unverified` 为空 ⇒ 本项自己未实测 / 未定的部分没登记")

    if not bad:
        cnt = {}
        for x in items:
            if isinstance(x, dict):
                cnt[_s(x.get("verdict"))] = cnt.get(_s(x.get("verdict")), 0) + 1
        notes.append(f"能力 {len(seen)} 项 · present {cnt.get('present', 0)} / "
                     f"partial {cnt.get('partial', 0)} / absent {cnt.get('absent', 0)} · "
                     f"口径 {_s(m.get('name')) if isinstance(m, dict) else '?'} · 读数 {_ds(doc.get('updated'))}")
    return bad, notes


def check_capability_inventory(ctx, doc=None):
    """O-105: 能力 → 载体 → 判定（能力盘点表）。"""
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 capabilities 断言", []
    if doc is None:
        if not CAPABILITY_INV.exists():
            return "FAIL", "inventory/capability-inventory.yaml 缺失（本断言的登记依据）", []
        try:
            doc = yaml.safe_load(_read_text(CAPABILITY_INV)) or {}
        except Exception as e:
            return "FAIL", f"inventory/capability-inventory.yaml 解析失败: {type(e).__name__}: {e}", []

    bad, notes = validate_capability_inventory(
        doc, known_checks={c["id"] for c in CHECKS},
        exists_fn=lambda rel: (ROOT / rel).exists())

    if bad:
        return "FAIL", " · ".join(notes) if notes else "见明细", bad
    return "PASS", " · ".join(notes), []


