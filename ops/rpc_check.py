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

ROOT = Path(__file__).resolve().parent.parent

# ── review-p2-split 8B-2：rpc_d6.py ─────────────────────────────
from rpc_common import CHECKS
from rpc_d6 import (
    AGENT_CLI, BLINDSPOT_KINDS, CAPABILITY_INV, CAP_BASIS, CAP_CARRIER_KINDS, CAP_DOMAINS,
    CAP_VERDICTS, CAP_WHY_KINDS, CODE_CAP_RE, COMBINED_STATES, DOC_CAP_RE, GUARD_KINDS,
    INBOX_BADGE_VALUES, INBOX_DIR, INBOX_PROJ_RE, INBOX_README, INBOX_REQUIRES_KEYS,
    INBOX_STATES, INBOX_TRUTH_YAML, INTERRUPT_INV, LEDGERS_INV, LEDGER_SCAN_EXCLUDE_DIRS,
    LOOP_CAP_STATES, LOOP_KINDS, MANUAL, MANUAL_COUNT_RE, MEMORY_CODE_EXTS, MEMORY_GATES_INV,
    MEMORY_GATE_IDS, MULTI_ROUND_INV, ON_EXCEED_KINDS, PS1_GOLDEN, PS1_RUNSTAMP, PY_TESTS,
    REVIEW_CATALOG_INV, ROUND_COUNTER_KINDS, RUBRIC_INV, SIDE_ACTIONS, _INBOX_TRUTH,
    _MANUAL_BANNED, _UNBLOCKERS, _decode_out, _ds, _fnmatch_any, _s, _scan_ledger_hits,
    check_capability_inventory, check_conclusion_ledger, check_evidence, check_inbox,
    check_interruption, check_memory_gates, check_mirror, check_multi_round, check_ps1_golden,
    check_ps1_runstamp, check_py_tests, check_review_catalog, check_rubric_blindspot,
    deadlock_risk, extract_loop_cap, extract_memory_symlinks, inbox_requires_sets,
    parse_symlink_paths, read_inbox_truth, read_judge_main, scan_isolation_by_text_prefix,
    scan_memory_egress, scan_memory_touchpoints, scan_prose_caps, validate_capability_inventory,
    validate_conclusion_ledgers, validate_inbox_mirror, validate_interruption,
    validate_manual_counts, validate_manual_states, validate_memory_gates, validate_mirror,
    validate_multi_round, validate_readme_requires, validate_review_catalog,
    validate_rubric_blindspot,
)

# ── review-p2-split 8B-2：rpc_docs.py ─────────────────────────────
from rpc_common import ADR_CANON, ADR_DIR, ADR_GLOB, ADR_LEGACY, AGENT_CLI, CHECKS, _decode_out, _ds, _norm_head, _read_text, _s, allow_unhit, validate_adr
from rpc_docs import (
    DOCLINK_ALLOW, DOCLINK_SKIP_PARTS, DOCLINK_LINK, _doclink_bad, check_doclinks, SPEC_DIR,
    SPEC_UNTESTED_GLOBS, SPEC_UNTESTED_HEAD, SPEC_EMARK_DIRS, SPEC_EMARK_RE, UNTESTED_INDEX,
    validate_spec_untested, LEDGER, LEDGER_ROW_RE, LEDGER_LEAD_RE, LEDGER_CLOSED_MARK,
    parse_ledger_rows, normalize_model_id, model_key_variants, family_of, load_family_index,
    cross_family_verdict, cross_input_verdict, check_model_families, check_ledger_status,
    LEDGER_PENDING_MARK, ledger_pending_ids, _ledger_rows_for_triage, summarize_untested_triage,
    check_spec_untested, check_adr, DOC_STATUS_INV, DOC_STATUS_DIRS, DOC_STATUS_HEAD,
    _DOC_FM_RE, _DOC_BODY_RE, _DOC_NORM, _doc_token, _doc_raw_token, _parse_template_vocab,
    _vocab_tokens, load_kind_vocab, _doc_kind, scan_doc_status, validate_doc_status,
    check_doc_status, MD_TABLES_INV, _md_cols, _md_is_sep, _md_is_fence, md_table_scan,
    _md_line_hash, check_md_tables, DET_NOISE_INV, _DET_SAMPLES, det_manifest_diff,
    det_scan_noise, _det_walk_na, check_determinism, DERIVED_VIEW, check_derived_view,
    EXEC_TRACE_SECTIONS, check_executor_trace,
)

# ── review-p2-split 8B-1：共享层 + 协议层（门面重导出，调用方零改动）────────
from rpc_common import SENSITIVITY_INV, SENSITIVITY_SECTIONS, SENSITIVITY_TIERS
from rpc_protocol import (
    CARD_GLOB, D7_BLOCK_FNS, D7_BLOCK_RULES, D7_CLI_EXIT_UNDECIDABLE, D7_ENVELOPES,
    D7_ENV_VERDICTS, D7_HOST_SEP_RULE, D7_MASTER, D7_PHASES, D7_TERMINAL, D7_TRANSITIONS,
    D7_TRANSITION_ACTOR, D7_VERDICT_WORDS, D7_WORKER, D7_WORKER_FORBIDDEN, DIALECT_AXES,
    DIALECT_INV, DIALECT_RELATIONS, DIALECT_UNKNOWN, EDGES_INV, EDGE_DEAD_PROV, EDGE_REQUIRED,
    NAMESPACE_REG, NS_ID_RULES, NS_RULE_UNSET, NS_STATUS, NS_VER_RULES, PROJECTS_REG,
    PROJ_STATUS, PROMOTION_INV, PROMO_OPS, PROMO_POLICIES, PROMO_REQUIRED_CRITERIA,
    PROVENANCE_NONE, PROVENANCE_OUTPUT_PREFIXES, PROV_PATH_TOKEN_RE, TIER_RANK, U1_ALGO,
    U1_DECL_SCAN_DIR, U1_DEFAULT_VERSION, U1_HEADER_RE, U1_LEGACY_MARK, U1_PREFIX, U1_TRUNC,
    U1_TRUNC_MAP, U4_ACTIONS, U4_ALGEBRAIC_PROPS, U4_CLASSES, U4_CLOSURE_VERDICTS,
    U4_DERIVED_VERDICTS, U4_EXEC_STATUS, U4_FALSIFY_VERDICTS, U4_ITEM_STATUS, U4_ORIGINS,
    U4_SELFCHECK_VERDICTS, _FM_KEY_RE, _card_frontmatter, _d7_blk_completion,
    _d7_blk_fail_closed, _d7_blk_frozen, _d7_blk_l1_l2, _d7_blk_master_scope,
    _d7_blk_single_writer, _d7_blk_worker_scope, _d7_cli_read, _dialect_norm, _dialect_slice,
    _edge_pair, _promo_cmp, _sens_registry, _u1_identity_of_path, _u1_prefix,
    check_derived_boundary, check_dialect, check_edges, check_falsification_suite,
    check_id_census, check_id_storage, check_input_provenance, check_projects, check_promotion,
    check_u1_identity, d7_block, d7_cli, d7_host_separation, d7_transition, decide_invalidation,
    edge_direction_error, edge_provenance_invalid, execute_invalidation, namespace_domain_error,
    namespace_for_project, namespace_index, projects_index, promotion_entry_verdict,
    recompute_closure, runtime_selfcheck, u1_canonical_bytes, u1_classify, u1_decl_conflicts,
    u1_header_line, u1_identity, u1_legacy_marker, u1_parse, u1_verify_declaration,
    v1_definition_correspondence, v2_bridge_completeness, v3_axiom_whitelist,
    v4_build_reproducible, validate_dialect, validate_edges, validate_envelope,
    validate_input_provenance, validate_namespace_coords, validate_namespaces,
    validate_projects, validate_promotion, verify_affected_closure,
)

# ── 断言 A1: 明文扫描 ─────────────────────────────────────────────
# 边界 (?<![A-Za-z0-9]) 用于排除 `task-2026...` 这类含 "sk-" 子串的误报。
# ⚠ 本清单与 `agent-cli.ps1` 的 `Get-ScrubRules`（出网前消毒，2026-09-21 扩到 9 条）**刻意不同**，
#   且**不要**为"对齐"去改：两者**作用域不同** —— 本处扫**仓库跟踪文件**（问"仓库里有没有真钥匙"），
#   那边扫**待出网 prompt**（问"出网字节里有没有敏感形态"）。裁定与理由见
#   docs/security/2026-09-21_scrubber规则扩充裁定与影响面.md §4 行 3。
#
# ★ 2026-10-21 扩形态（安全评审触发）：原正则**只认 `sk-` 前缀**，而仓库里实际躺着
#   Beszel 账号口令与 SSH 口令（非 sk- 形态）⇒ 门禁长期全绿不是因为干净，是因为看不见。
#   现扩到四族：`sk-` / 口令赋值（**仅带引号的字面量**）/ 私钥块头 / 常见云厂商 key 前缀。
#   ⚠ 值分支**刻意只认带引号的字面量**：放开"不带引号"会误伤 `if decision == "pass":`
#     与 `PASS: derived-view` 这类正常文本（2026-10-21 实测）⇒ 该形态登记为盲区，
#     见 tests/test_rpc_check_secret_forms.py 的残留盲区说明。
SECRET_RE = re.compile(
    r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}"
    # ★★ 2026-10-24（O-174）：口令族**允许下划线前缀** —— 原写法 `\b(?:pass|…)` 在
    #   `ADMIN_PASS` / `DB_PWD` 上是**漏报**：`_` 与 `P` 之间没有字边界（两者都是 word char）
    #   ⇒ 整条赋值被跳过（实测：`archive/scripts-history/b5f_hub_deploy.sh` 里一条 59 字符
    #   真凭据因此长期不被门禁看见）。现改为「非字母数字起 + 任意 `xxx_` 前缀 + 关键字」，
    #   并要求关键字**后**不再接字母数字（`(?![A-Za-z0-9])`）。
    #   ⚠ 边界刻意保留：`SSH_ASKPASS_REQUIRE = "force"` 不命中（关键字后接 `_REQUIRE`）、
    #   `bypass="…"` 不命中（`by`/`pass` 之间无下划线），夹具 `test_rpc_check_secret_forms.py` 钉住。
    r"|[\"']?(?<![A-Za-z0-9])(?:[A-Za-z0-9]+_)*(?:pass|passwd|password|pwd)(?![A-Za-z0-9])[\"']?\s*[:=]\s*"
    r"(?:\"(?=[^\"]*[A-Za-z0-9])[^\"\s]{4,}\"|'(?=[^']*[A-Za-z0-9])[^'\s]{4,}')"
    r"|-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
    r"|(?<![A-Za-z0-9])(?:AKIA|ASIA)[0-9A-Z]{16}"
    r"|(?<![A-Za-z0-9])(?:ghp|gho|ghs|ghr)_[A-Za-z0-9]{30,}"
    r"|(?<![A-Za-z0-9])(?:glpat|xox[baprs]|sk_live|AIza)[A-Za-z0-9_\-]{10,}",
    re.IGNORECASE)

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

    ⚠ **2026-09-23（O-34）**：上面这条是**假设**，它**只在 pre-commit 钩子里成立** ——
    手动直跑（本仓推荐做法）若处于"文件已新建/重命名但未暂存"的中间态，范围会与提交时**不同**
    ⇒ **同一命令两种结论**。故配套 `_untracked_count()`，由消费者把它**显式报出来**，
    而不是让"范围已收窄"静默影响结论。
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


def _untracked_count() -> int:
    """**未跟踪**（⇒ 不在门禁范围内）的文件数；`--exclude-standard` ⇒ 尊重 `.gitignore`。

    用途（O-34）：让"范围已收窄"**可见** —— 干净仓库/正常提交路径上恒为 0 ⇒ **零噪声**。
    """
    try:
        out = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "-z"],
                             cwd=ROOT, capture_output=True, check=True).stdout
        return len([p for p in out.decode("utf-8", "replace").split("\0") if p])
    except Exception:
        return 0


def _is_binary(path):
    try:
        with open(path, "rb") as fh:
            return b"\x00" in fh.read(8192)
    except OSError:
        return True




def _mask(s):
    return s[:8] + "…" if len(s) > 9 else s




def check_secrets(ctx):
    """扫描跟踪文件中的明文密钥形态。

    ★ 2026-10-21：删掉 `if "sk-" not in text: continue` 的**整文件短路**。
      原短路让"不含 sk- 的文件"连正则都不跑 —— 扩形态后它会让新增的四族全部失效
      （实测：Beszel 口令所在文件无一含 `sk-`）。范围本来就是 git 跟踪文件（~1000 个），
      全量跑正则的成本可忽略。
    """
    hits, allowed, scanned, skipped_bin = [], [], 0, 0
    for rel, path in _iter_source_files():
        if _is_binary(path):
            skipped_bin += 1
            continue
        text = _read_text(path)
        scanned += 1
        for i, line in enumerate(text.splitlines(), 1):
            for m in SECRET_RE.finditer(line):
                rec = (rel, i, _mask(m.group(0)))
                (allowed if rel in SECRET_ALLOW else hits).append(rec)
    detail = [f"{r}:{n}  {s}" for r, n, s in hits]
    for r, n, s in allowed:
        detail.append(f"(白名单) {r}:{n}  {s} —— {SECRET_ALLOW[r]}")
    # D6-P0-2: 豁免**未命中**（该文件里已无样串）⇒ **自报**，否则清单腐化无人知（可移除但没人删）
    _unhit = allow_unhit(list(SECRET_ALLOW), {r for r, _n, _s in allowed})
    for r in _unhit:
        detail.append(f"(豁免**未命中**) {r} —— {SECRET_ALLOW[r]} ⇒ "
                      f"该文件已无样串命中 ⇒ **该豁免已可移除**")
    note = f"扫描 {scanned} 个文本文件 (跳过 {skipped_bin} 个二进制), 命中 {len(hits)} 处"
    if allowed:
        note += f", 白名单 {len(allowed)} 处"
    if _unhit:
        note += f" · ⚠ 豁免未命中 {len(_unhit)} 条（已可移除，见明细）"
    # O-34: 范围 = git 跟踪文件；若此刻有未跟踪文件 ⇒ 本结论**可能**与 pre-commit 时不同，必须报出来。
    _un = _untracked_count()
    if _un:
        note += (f" · ⚠ 另有 {_un} 个**未跟踪**文件未计入（范围=git 跟踪文件；"
                 f"pre-commit 时新文件已暂存 ⇒ 手动跑与提交跑结论可能不同，见台账 O-34）")
    return ("FAIL" if hits else ("WARN" if _unhit else "PASS")), note, detail


# ── 断言 A2: 语法检查 ─────────────────────────────────────────────
PS_SNIPPET = r"""
$files = @($input | Where-Object { $_ -and $_.Trim() -ne '' })
foreach ($f in $files) {
  $tok = $null; $errs = $null
  [System.Management.Automation.Language.Parser]::ParseFile($f, [ref]$tok, [ref]$errs) | Out-Null
  if ($errs -and $errs.Count -gt 0) {
    foreach ($e in $errs) { "FAIL`t$f`t$($e.Extent.StartLineNumber)`t$($e.Message)" }
  }
}
"""

# ── P2 (ADR-0007 路A, 2026-09-18): 用 **PATH 第一个 `python`** 再编译一遍 .py ──────────
# 为什么单列: 上面那次 py_compile 用**当前解释器**, 而 rpc.ps1 挑的是"候选里**第一个能
#   `import paramiko` 的**" ⇒ 本机落到 **Python312**。后果实测(2026-09-18):
#   `cluster.py` 一行 f-string 表达式段含反斜杠(PEP 701 才允许) ⇒ 在 PATH 第一个
#   `python`(3.11.16) 下**整个模块不可解析**, 而 syntax 报 **0 失败**、evidence 因
#   `import cluster` 被 except 兜住只报 WARN ⇒ **判据静默消失、整仓仍 PASS**。
# 判据: 取 PATH 第一个 `python`(即人工敲 `python ops/cluster.py` 时真正会用的那个);
#   只要它与当前解释器**不同**, 就用它**一个子进程**批量编译(逐文件 spawn 会 43×0.2s)。
#   失败 ⇒ FAIL, 且明细**点名用了哪个解释器** —— 否则读者无从判断"该修语法还是该改声明"。
# 注: 这不是"多解释器矩阵"(不承诺支持任意旧版本), 只盯**人工实际会用的那个**。
PY_SNIPPET = r"""
import sys, os, py_compile, tempfile
td = tempfile.mkdtemp()
n = 0
for raw in sys.stdin.read().splitlines():
    f = raw.strip()
    if not f:
        continue
    n += 1
    try:
        py_compile.compile(f, cfile=os.path.join(td, "c%d" % n), doraise=True)
    except Exception as e:
        msg = str(e).strip().splitlines()
        print("FAIL\t%s\t%s" % (f, (msg[-1] if msg else type(e).__name__)[:160]))
print("SUMMARY\t%d" % n)
"""


def _py_version(exe: str) -> str:
    """取解释器版本 'X.Y.Z'；取不到返回 ''（**不抛** —— 这只是辅助信息，不该炸掉整个断言）。"""
    try:
        p = subprocess.run([exe, "-c", "import sys;print('%d.%d.%d' % sys.version_info[:3])"],
                           capture_output=True, cwd=ROOT, timeout=30)
        return (p.stdout or b"").decode("utf-8", "replace").strip() if p.returncode == 0 else ""
    except Exception:
        return ""


SH_LINT = ("n=0; while IFS= read -r f; do [ -z \"$f\" ] && continue; n=$((n+1)); "
           "if ! out=$(bash -n \"$f\" 2>&1); then printf 'FAIL\\t%s\\t%s\\n' \"$f\" \"$out\"; fi; "
           "done; printf 'COUNT\\t%s\\n' \"$n\"")

# ── shell 语法检查的三条修复 (2026-09-15，方案 v2 §A.6 P2-5 记录的那次事故) ────
# 旧实现把路径直接喂给裸 `bash -n`。本机 PATH 上的 `bash` 是 C:\Windows\system32\bash.EXE (WSL)，
# 它**看不到 D:\ / /d/ 形式的仓库路径** ⇒ `bash -n` 等于"文件不存在"，而旧代码把这种"读不到"
# 当成了"检查通过"：实测 447 个 .sh 报 0 失败，**往已跟踪文件注入语法错也不报**。
# 静默降级落在提交门禁自己身上，是本仓库最不能接受的一类错。故:
#   ① 显式找一个**能读到仓库路径**的 bash (Windows 上通常是 Git Bash)，并**实测它读得到**；
#   ② 统一传 POSIX 形态路径 (/d/RPC/...)；
#   ③ stdin 补尾换行 —— `while IFS= read -r` 会丢掉**没有换行结尾的最后一行**；
#   ④ **自证**: 先拿故意写错的临时文件验证"它真能判错"，做不到就整栏判 FAIL("不可信")，绝不报 PASS。
BASH_BROKEN_SAMPLE = "#!/bin/bash\nif [ 1 == ; then\n"


def _posix(p) -> str:
    """仓库内绝对路径 → POSIX 形态 (D:\\RPC\\x → /d/RPC/x)；任何 MSYS/Git Bash 都能读。"""
    s = str(p)
    if len(s) > 2 and s[1] == ":":
        return "/" + s[0].lower() + s[2:].replace("\\", "/")
    return s.replace("\\", "/")


def _bash_candidates():
    """候选 bash 列表 (去重、存在的)。PATH 上的排第一，其后是 Git for Windows 的常见落点。"""
    cands = [shutil.which("bash")]
    for env in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if not base:
            continue
        cands += [os.path.join(base, "Git", "bin", "bash.exe"),
                  os.path.join(base, "Git", "usr", "bin", "bash.exe"),
                  os.path.join(base, "Programs", "Git", "bin", "bash.exe")]
    seen, out = set(), []
    for c in cands:
        if c and c not in seen and os.path.exists(c):
            seen.add(c)
            out.append(c)
    return out


def _bash_can_read(bash: str) -> bool:
    """用**真实仓库 .sh** 探一下它能不能打开我们的路径 —— "空转"与"真检查"的分界就在这。"""
    probe = next((p for _, p in _iter_source_files()
                  if p.suffix.lower() == ".sh" and p.is_file()), None)
    if probe is None:
        return False
    try:
        r = subprocess.run([bash, "-c", f'test -f "{_posix(probe)}" && echo READABLE'],
                           capture_output=True, text=True, cwd=ROOT, timeout=30)
        return "READABLE" in (r.stdout or "")
    except Exception:
        return False


def _pick_bash():
    """返回 (bash 路径, 说明)。找不到可用的就返回 (None, 原因)。"""
    tried = []
    for b in _bash_candidates():
        if _bash_can_read(b):
            return b, ""
        tried.append(b)
    return None, (f"找不到能读到仓库路径的 bash (试过 {len(tried)} 个: {', '.join(tried) or '无'}) —— "
                  f"本栏**不可信**, 请装 Git for Windows 或把它的 bash.exe 放进 PATH")


def _bash_lint(files, bash: str) -> tuple:
    """用指定 bash 跑一遍 `bash -n`。返回 (bad, details, count_seen)。

    count_seen = 远端循环实际处理的文件数 —— 用它断言"真的读到了全部文件"，
    而不是只看"没有 FAIL 行"(那是空转也会有的结果)。
    """
    out = _run_with_stdin([bash, "-c", SH_LINT], [_posix(p) for p in files])
    bad, details, seen = 0, [], None
    for ln in out.splitlines():
        if ln.startswith("FAIL\t"):
            parts = ln.split("\t", 2)
            msg = (parts[2] if len(parts) > 2 else "").strip()
            name = parts[1] if len(parts) > 1 else "?"
            bad += 1
            details.append(f"(sh) {name if name not in ('1', '') else ''} {msg[:150]}".strip())
        elif ln.startswith("COUNT\t"):
            try:
                seen = int(ln.split("\t", 1)[1])
            except ValueError:
                seen = None
    return bad, details, seen


# ── shell 语法检查并行化 (2026-09-23, 第③项) ────────────────────────
# 为什么是**并行分块**而不是"合并外层循环"(第一条捷径):
#   `bash -n <file>` 只把第一个入口当脚本解析(source 进来的不算), 所以每个文件**必须**独立
#   fork 一次 `bash -n` —— 那把多个文件拼进同一次 bash 调用的"合并"做法, 只会检查第一个文件,
#   是静默降为 0 覆盖(本仓最忌讳)。cProfile 实测 syntax 19.6s 里 ~17s 卡在逐文件 fork 的
#   `_stdin_write`, 语法解析本身仅 ~0.3s ⇒ 并行分块是不**删除**任何判据、也不改 seen 口径的提速。
def _bash_lint_parallel(files, bash: str, workers: int = 8) -> tuple:
    """并行分块跑 `_bash_lint`。返回 (bad, details, seen_sum)。

    seen 口径保持"远端循环实际处理的文件总数" ⇒ 覆盖校验仍看它 == len(files)，
    不会因为并行而丢掉"读到数 != 喂入数 ⇒ 结果不可信"这条。
    """
    if not files:
        return 0, [], 0
    n = min(workers, len(files))
    chunks = [files[i::n] for i in range(n)]
    bad_total, seen_total, all_det = 0, 0, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as ex:
        futs = [ex.submit(_bash_lint, chunk, bash) for chunk in chunks]
        for f in futs:
            b, d, seen = f.result()
            bad_total += b
            all_det += d
            seen_total += (seen if seen is not None else 0)
    return bad_total, all_det, seen_total


def _iter_shebang_scripts():
    """git 跟踪文件里**无扩展名但带 shebang** 的脚本 → (rel, path, kind)。

    为什么必须有这一段: 站上件大多是**无扩展名**的 —— infer-load / infer-unload /
    llama-serve-instance / cluster-ttl / reqlog / load-gate …，.py/.ps1/.sh/.json 一个都不覆盖
    ⇒ 这批"真正跑在站上的东西"此前**完全不过语法门禁**，而它们恰恰最不能带语法错上站
    (改坏 infer-load 会让整条加载链断掉)。
    """
    known = (".py", ".ps1", ".sh", ".json")
    for rel, path in _iter_source_files():
        if path.suffix.lower() in known or not path.is_file() or _is_binary(path):
            continue
        head = _read_text(path).splitlines()[:1]
        if not head or not head[0].startswith("#!"):
            continue
        if "python" in head[0]:
            yield rel, path, "py"
        elif "/bash" in head[0] or head[0].rstrip().endswith("/sh"):
            yield rel, path, "sh"


def _run_with_stdin(argv, files):
    """把文件列表喂给 argv 的 stdin。

    两个都是**实测踩过**的坑, 少一个就会静默出错:
    ⚠ ① **必须走字节模式** (不是 `text=True`): Windows 上文本模式会把写给孩子进程的 stdin 里的
       `\\n` 翻成 `\\r\\n`; 子壳的 `while IFS= read -r` 只吃掉 `\\n`, 路径尾巴上留下 `\\r`
       ⇒ 每个路径都变成"不存在的文件"。表现为**全部文件报失败** (实测 447/447), 极易误判成
       "仓库全坏了"。`subprocess` **没有** `newline=` 参数 (传了会 TypeError), 故只能喂 bytes。
    ⚠ ② **必须补尾换行**: `while IFS= read -r` 遇到没有换行结尾的最后一行时 read 返回非 0,
       循环体**不执行** —— 少喂一个文件却毫无提示 (同一个 while-read 家族的两个不同坑)。
    """
    try:
        p = subprocess.run(argv, input=("\n".join(files) + "\n").encode("utf-8"),
                           capture_output=True, cwd=ROOT)
        return (p.stdout or b"").decode("utf-8", "replace")
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

    # ── P2: 再用 **PATH 第一个 `python`** 编译一遍（见 PY_SNIPPET 处说明）─────────────
    # 目的只有一个: 让"人工敲 `python ops/cluster.py` 会不会炸"成为**门禁判据** ——
    #   上面那次编译用的是门禁自己的解释器(rpc.ps1 挑的第一个带 paramiko 的), 两者可能不同版本。
    _alt = shutil.which("python")
    _cur_ver = "%d.%d.%d" % sys.version_info[:3]
    if not _alt:
        detail.append("(py-alt) PATH 上无 `python` ⇒ 【人工敲的那个解释器能否解析】该维度未验证")
    elif os.path.abspath(_alt) == os.path.abspath(sys.executable):
        detail.append(f"(py-alt) PATH 第一个 python 就是当前解释器({_cur_ver}) ⇒ 无需重复编译")
    else:
        _alt_ver = _py_version(_alt)
        if not _alt_ver:
            detail.append(f"(py-alt) PATH 第一个 python({_alt}) 取不到版本 ⇒ 该维度未验证")
        else:
            _abs2rel = {str(p): rel for rel, p in py_files}
            _out = _run_with_stdin([_alt, "-c", PY_SNIPPET], [str(p) for _, p in py_files])
            _fails, _seen = [], 0
            for _ln in _out.splitlines():
                if _ln.startswith("SUMMARY\t"):
                    _, _n = _ln.split("\t", 1)
                    _seen = int(_n.strip() or 0)
                elif _ln.startswith("FAIL\t"):
                    _, _f, _msg = _ln.split("\t", 2)
                    _fails.append(f"(py{_alt_ver}) {_abs2rel.get(_f, _f)}  {_msg}")
            bad_alt = len(_fails)
            detail += _fails
            if _seen != len(py_files):
                # 与 .sh 分支同一条纪律: 读到数 != 喂入数 ⇒ 结果不可信, 拒绝给 PASS
                bad_alt = len(py_files)
                detail.append(f"(py{_alt_ver}) 覆盖不全: 实际编译 {_seen} / 应有 {len(py_files)} 个"
                              f" (读到数 != 喂入数 ⇒ 结果不可信)")
            counts[f".py@{_alt_ver}"] = (len(py_files), bad_alt)
            detail.append(f"(py-alt) PATH 第一个 python = {_alt_ver}"
                          f"（≠ 门禁解释器 {_cur_ver}）⇒ 已按它复检 {_seen} 个 .py, 失败 {bad_alt}")

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
        # ⚠ 失败数按**文件**计(不是按错误行计): 一个文件多行报错只算 1 —— 否则摘要会写
        #   "13文件/11失败", 读起来像"11 个文件坏了"(2026-09-21 实地误导过一次: 实际只有 1 个文件)。
        #   明细里**必须带文件名**: 13 个文件里只报 "Unexpected token ')' [line 37]" 是查不到人的。
        #   且统一回**仓库相对路径**(snippet 收到的是绝对路径), 与其它断言的明细格式一致。
        rel_of = {str(p): rel for rel, p in ps_files}
        bad_files = set()
        for ln in out.splitlines():
            if ln.startswith("FAIL\t"):
                parts = ln.split("\t", 3)
                if len(parts) < 4:
                    bad_files.add(f"<unparsed:{ln[:40]}>")
                    detail.append(f"(ps1) {ln[:160]}")
                    continue
                _, fabs, lineno, msg = parts
                frel = rel_of.get(fabs.strip(), fabs.strip())
                bad_files.add(frel)
                detail.append(f"(ps1) {frel}  {msg[:160]}  [line {lineno}]")
        bad = len(bad_files)
    counts[".ps1"] = (len(ps_files), bad)

    # ── .ps1 子判据 (2026-09-21, ADR-0004 D3 路径①): 含非 ASCII 的 .ps1 **必须**带 UTF-8 BOM ──
    # 触发: 09-18(守门夹具静默失效) 与 09-21(编辑工具剥掉三个脚本的 BOM 后夹具当场解析崩溃)。
    # ⚠ **根因(2026-09-21 实测更正, 勿沿用早先的错误说法)**: `Parser::ParseFile` **不是**按 UTF-8 读
    #   BOM-less 文件, 它与 `powershell -File x.ps1` **走同一条解码路径(BOM-less ⇒ ANSI/GBK)**。
    #   实测证据: 把一个 BOM-less 的中文 .ps1 喂给上游那次 ParseFile ⇒ 报 11 条错, 行号**全部落在
    #   中文注释行**(30/37/209/214/231/237/257/299) —— 若真是按 UTF-8 读, 一条错都不会有。
    # ⇒ 所以上游那条判据**能抓到**, 但**只在乱码恰好破坏语法时**才抓到:
    #     3 字节 UTF-8 被当 2 字节 GBK 解码, 是否"吞掉相邻换行"**取决于内容** ⇒ 同样的缺陷在
    #     **不同内容下**可能报 11 条错, 也可能报 **0 条错却照样跑坏**(09-18 目击的正是后者: 门禁
    #     `.ps1:12文件/0失败`, 而夹具 `fns count=0`)。**间歇、内容相关、且报错指向注释行而不指根因**
    #     —— 这三条加在一起才构成"必须另加字节判据"的理由。
    # 本判据是**确定性**的(读字节, 与内容无关), 且**报的是根因**(含非 ASCII 却无 BOM)而非症状。
    # 判据: 有非 ASCII 字节 且 无 `EF BB BF` ⇒ FAIL。纯 ASCII 的 .ps1 **不受约束**(无 BOM 也安全, 不误报)。
    # 为什么**不**覆盖 .sh: `.sh` **不得**加 BOM —— BOM 会让内核把 `#!` 认成 `\xEF\xBB\xBF#!`
    #   ⇒ `bad interpreter` 直接不可执行。站上是 UTF-8 locale, 风险形态不同, 故不在此判。
    bad_bom = 0
    for rel, path in ps_files:
        try:
            raw = path.read_bytes()
        except OSError as e:
            bad_bom += 1
            detail.append(f"(ps1-bom) {rel}  读字节失败: {type(e).__name__}")
            continue
        if raw[:3] == b"\xef\xbb\xbf":
            continue
        if any(byte > 0x7F for byte in raw):
            bad_bom += 1
            detail.append(f"(ps1-bom) {rel}  含非 ASCII 却**无 UTF-8 BOM** ⇒ PS5.1 按 ANSI(GBK) "
                          f"解码可能吞掉换行致脚本静默损坏 ⇒ 修: 以 UTF-8 **带 BOM** 重写")
    counts[".ps1-bom"] = (len(ps_files), bad_bom)

    # ── shell 语法: .sh + **无扩展名的 shebang 脚本** (站上件), 共用一次 bash 调用 ──
    sh_files = [(rel, p) for rel, p in by_ext.get(".sh", [])]
    sb = list(_iter_shebang_scripts())
    sb_sh = [(rel, p) for rel, p, k in sb if k == "sh"]
    sb_py = [(rel, p) for rel, p, k in sb if k == "py"]

    bash, why = _pick_bash()
    bad_sh, bad_sb_sh = 0, 0
    if not bash:
        # 判"不可信"而不是 PASS —— 见 SH_LINT 上方的说明 (本仓库最忌讳的静默降级正在这里)
        bad_sh = len(sh_files)
        bad_sb_sh = len(sb_sh)
        detail.append(f"shell 语法检查不可信: {why}")
    else:
        # 自证 (双向对照): 好样本必须不报错、坏样本必须报**语法错**。
        # ⚠ 只断言"出现了 FAIL"是不够的 —— 我第一版就是这么写的, 结果在"所有路径都因为 CRLF
        # 变成不存在的文件"时, 自证依然"通过"(它测的其实是个不存在的文件)。必须校验**报错内容**。
        with tempfile.TemporaryDirectory() as td:
            good = Path(td) / "good.sh"
            broke = Path(td) / "broken.sh"
            good.write_text("#!/bin/bash\nset -u\nfor i in 1 2 3; do echo \"$i\"; done\n",
                            encoding="utf-8", newline="\n")
            broke.write_text(BASH_BROKEN_SAMPLE, encoding="utf-8", newline="\n")
            n_good, det_good, seen_good = _bash_lint([good], bash)
            n_broke, det_broke, seen_broke = _bash_lint([broke], bash)
        ok_self = (n_good == 0 and seen_good == 1
                   and n_broke == 1 and seen_broke == 1
                   and any("syntax error" in d for d in det_broke))
        if not ok_self:
            bad_sh, bad_sb_sh = len(sh_files), len(sb_sh)
            detail.append(
                f"shell 语法检查自证失败: {os.path.basename(bash)} 好样本报错/坏样本未被判为语法错"
                f" (good={n_good}/{seen_good} bad={n_broke}/{seen_broke}"
                f" detail={' | '.join(det_broke)[:80]}) → 本栏不可信, 拒绝给 PASS")
        else:
            # ③(2026-09-23): 业务 `.sh` 与无扩展名脚本**并行**检查。
            #   cProfile 实测: `bash -n` 必须逐文件 fork(见 _bash_lint_parallel 注释), syntax 的
            #   ~17s 全卡在 fork, 解析本身仅 0.3s ⇒ 并行分块(默认 8 worker)让 19.6s → ~3s 量级。
            #   自证(good/broke)保持串行独立 —— 那是"好样本必 0 错/坏样本必 1 错"的单文件判定。
            if sh_files:
                bad_sh, det, seen = _bash_lint_parallel([p for _, p in sh_files], bash)
                detail += det
                if seen != len(sh_files):
                    bad_sh = len(sh_files)
                    detail.append(f".sh 覆盖不全: 实际检查 {seen} / 应有 {len(sh_files)} 个"
                                  f" (读到数 != 喂入数 ⇒ 结果不可信)")
            if sb_sh:
                bad_sb_sh, det, seen = _bash_lint_parallel([p for _, p in sb_sh], bash)
                detail += det
                if seen != len(sb_sh):
                    bad_sb_sh = len(sb_sh)
                    detail.append(f"无扩展名脚本覆盖不全: 实际检查 {seen} / 应有 {len(sb_sh)} 个")
    counts[".sh"] = (len(sh_files), bad_sh)

    # ── A. `.sh` 行尾: **CRLF 字节判据** (2026-10-17, 与上面的 `.ps1-bom` 同机理) ──────────
    # 为什么必须**另判一次"字节"**: 本栏的 `bash -n` 跑在 **Git Bash(MSYS)** 上, 而脚本的**靶子是 Linux bash**。
    #   实测(同一份 CRLF 的 .sh, 样本 `archive/scripts-history/gen_manifest.sh`):
    #     · 门禁侧 MSYS `bash -n` ⇒ **rc=0 通过**   (⇒ 本栏报 `.sh:414文件/0失败`, **漏判**)
    #     · 站上 Linux `bash -n` ⇒ **报语法错** `未预期的记号 "}"`
    #   ⇒ 解析式判据对"行尾"这类**字节级**属性**结构性不可见**, 那个绿是**假的**。
    #   与 `.ps1-bom` 的教训**完全同源**: 解析判据抓不到字节级属性 ⇒ 必须另加一个"读字节"的维度。
    # 判据(确定性, 与内容无关): `.sh` 与无扩展名 shebang 脚本**含任何 `0x0D`** ⇒ FAIL。
    #   为什么不能靠 `.gitattributes`: 那里的 `text eol=lf` 只覆盖**已登记前缀**, 覆盖不到全仓与站上产物。
    crlf_targets = sh_files + sb_sh
    bad_crlf = 0
    with tempfile.TemporaryDirectory() as td:
        # 自证(双向): LF 样本必**不**含 CR、CRLF 样本必含 —— 判据本身要能被证伪, 才配写进 FAIL 集
        lf_s, crlf_s = Path(td) / "lf.sh", Path(td) / "crlf.sh"
        lf_s.write_bytes(b"#!/bin/bash\necho hi\n")
        crlf_s.write_bytes(b"#!/bin/bash\r\necho hi\r\n")
        ok_crlf_self = (b"\x0d" not in lf_s.read_bytes()) and (b"\x0d" in crlf_s.read_bytes())
    if not ok_crlf_self:
        bad_crlf = len(crlf_targets)
        detail.append("(sh-crlf) 字节判据自证失败: LF 样本被误判 / CRLF 样本未被识别 ⇒ 本栏不可信, 拒绝给 PASS")
    else:
        for rel, path in crlf_targets:
            try:
                raw = path.read_bytes()
            except OSError as e:
                bad_crlf += 1
                detail.append(f"(sh-crlf) {rel}  读字节失败: {type(e).__name__}")
                continue
            if b"\x0d" in raw:
                bad_crlf += 1
                detail.append(f"(sh-crlf) {rel}  含 CR(0x0D) ⇒ 行尾为 CRLF; 靶子是 **Linux bash**, "
                              f"CRLF 会破坏解析(实测同文件 MSYS `bash -n` 通过而 Linux `bash -n` 报错) "
                              f"⇒ 修: 转 LF (`dos2unix` / 编辑器设 LF / `.gitattributes` 加 `text eol=lf`)")
    counts[".sh-crlf"] = (len(crlf_targets), bad_crlf)

    # 无扩展名脚本的 python 半边 (与 bash 无关, 总能查)
    bad_sb_py = 0
    if sb_py:
        with tempfile.TemporaryDirectory() as td:
            for rel, path in sb_py:
                cfile = os.path.join(td, rel.replace("/", "_") + "c")
                try:
                    import py_compile
                    py_compile.compile(str(path), cfile=cfile, doraise=True)
                except py_compile.PyCompileError as e:
                    bad_sb_py += 1
                    detail.append(f"(无扩展名/py) {rel}  {str(e).strip().splitlines()[-1][:140]}")
                except Exception as e:
                    bad_sb_py += 1
                    detail.append(f"(无扩展名/py) {rel}  {type(e).__name__}: {e}")
    counts["无扩展名"] = (len(sb), bad_sb_sh + bad_sb_py)

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


# ── 断言 A13: 脚本治理 (ADR-0004「统一管理入口为唯一管理面」) ──────────
# 背景: ops/ 下积累了两百多个一次性脚本 (`_xxx.sh` 一片), 各自管一小块、与统一入口能力重复、
# 还要各自维护。规则: **所有管理操作从统一入口 (cluster.py / cluster_web.py) 执行**;
# 存量冻结(只减不增), 新增脚本必须登记 —— 登记这个动作本身就是 review 时能看见的留痕。
# 只写规则不绑定执行等于空头承诺, 故做成断言 (与 plugins 的 known_drift 同一套纪律)。
OPS_INV = ROOT / "inventory" / "ops.yaml"
SCRIPT_EXT = (".py", ".ps1", ".sh")


def _in_script_scope(rel):
    """脚本治理的**范围谓词** (两层): `ops/**` ∪ **仓库根顶层文件**。

    为什么不写成"全仓递归 + 排除表" (2026-09-22 裁定, 决策简报《门禁口径…root 级脚本范围》):
      · 全仓递归会把 `spec/**` (文档/卡片)、`tests/**` (夹具)、`archive/**` (已归档) 一并圈进来,
        而这些目录**天然**不是管理面; 要正确排除就得维护一张不断变长的例外清单 ——
        每加一个目录就多一个定义点, 漏一项就是假红/假绿 (本仓纪律: 判据只在一处定义)。
      · 两层谓词**不需要任何例外清单**: 顶层文件 = 有人把一次性的东西直接丢在仓库根,
        正是 2026-09-16 真正出事的形态 (根级 3 个零引用脚本); `ops/**` 是 ADR-0004 定义的管理面。
        目录内的散件由目录自身归位 (archive/ 归档、tests/ 夹具)。
      · 实测 (2026-09-22): 顶层被跟踪文件只有 `.gitignore` 与 `LICENSE`,
        二者在 Python 里 `suffix=''` ⇒ 走 shebang 分支、首行非 `#!` ⇒ 不被当脚本
        ⇒ 扩范围后**今日 0 项未登记**, 登记表零改动。
    注意: PowerShell 的 `[IO.Path]::GetExtension('.gitignore')` 得 `.gitignore`,
    与 Python 的 `os.path.splitext` 语义不同 —— 判据以 Python 侧为准。
    """
    return rel.startswith("ops/") or "/" not in rel


def _iter_governed_scripts():
    """受脚本治理约束的 git 跟踪**脚本** → [(rel, path)]。范围见 `_in_script_scope`。
    含无扩展名但带 shebang 的 (站上件常见)。"""
    for rel, path in _iter_source_files():
        if not _in_script_scope(rel) or not path.is_file():
            continue
        if path.suffix.lower() in SCRIPT_EXT:
            yield rel, path
        elif not path.suffix and not _is_binary(path):
            head = _read_text(path).splitlines()[:1]
            if head and head[0].startswith("#!"):
                yield rel, path


def check_scripts(ctx):
    """脚本治理 (范围: `ops/**` ∪ 仓库根顶层, 见 `_in_script_scope`):
    任何脚本必须在登记表里 (入口 / 站上运行时件 / 冻结存量)。"""
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过脚本治理断言 (不复现于 CI 环境即视为通过)", []
    if not OPS_INV.exists():
        return "FAIL", "inventory/ops.yaml 缺失 (本断言的登记依据)", []
    try:
        inv = yaml.safe_load(OPS_INV.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return "FAIL", f"inventory/ops.yaml 解析失败: {type(e).__name__}: {e}", []

    entry = list(inv.get("entry") or [])
    modules = list(inv.get("entry_modules") or [])      # 2026-09-23: 入口的拆分模块 (见 ops.yaml 注释)
    runtime = list(inv.get("station_runtime") or [])
    frozen = list(inv.get("frozen_ops_scripts") or [])
    known = set(entry) | set(modules) | set(runtime) | set(frozen)

    scripts = dict(_iter_governed_scripts())
    unknown = sorted(s for s in scripts if s not in known)
    missing_entry = [e for e in entry if not (ROOT / e).exists()]
    missing_module = [m for m in modules if not (ROOT / m).exists()]
    gone = sorted(f for f in frozen if not (ROOT / f).exists())          # O-44: 真不存在
    untracked_frozen = sorted(f for f in frozen                          # O-44: 存在但未 git 跟踪
                              if (ROOT / f).exists() and f not in scripts)

    detail = []
    if unknown:
        detail.append(f"新增未登记脚本 {len(unknown)} 个 —— 管理操作请优先给统一入口加子命令 "
                      f"(ops/cluster.py <sub>), 而非再写一个脚本:")
        detail += [f"  {s}" for s in unknown[:20]]
        if len(unknown) > 20:
            detail.append(f"  …另 {len(unknown) - 20} 个")
    if missing_entry:
        detail.append("统一入口件缺失: " + ", ".join(missing_entry))
    if missing_module:
        detail.append("入口拆分模块缺失 (登记了但文件不在): " + ", ".join(missing_module))
    if gone:
        detail.append(f"冻结清单里已不存在的 {len(gone)} 项可从 inventory/ops.yaml 删掉 "
                      f"(只减不增, 删减是欢迎的方向): " + ", ".join(gone[:8])
                      + (" …" if len(gone) > 8 else ""))
    # O-44 (2026-09-24): 与 `gone` 分开报 —— 这些**文件确实在**，只是本次扫描（git 跟踪集）没覆盖到。
    #   旧实现把它们并入 `gone` 并提示"已不存在、可从清单删掉" ⇒ **照做则提交后立刻变"未登记" FAIL**。
    #   措辞必须**明确劝阻删除**（O-34 同源：范围收窄必须让"收窄"本身可见）。
    if untracked_frozen:
        detail.append(f"冻结清单里 {len(untracked_frozen)} 项**文件存在但未被 git 跟踪**(未 `git add`) "
                      f"⇒ 本次扫描未计入, **勿据此删登记**(只需 `git add`): "
                      + ", ".join(untracked_frozen[:8]) + (" …" if len(untracked_frozen) > 8 else ""))
    bad = bool(unknown) or bool(missing_entry) or bool(missing_module)
    note = (f"扫描 {len(scripts)} 个脚本 · 入口 {len(entry)} · 拆分模块 {len(modules)} "
            f"· 站上运行时 {len(runtime)} · 冻结存量 {len(frozen)} · 未登记 {len(unknown)}")
    # 提示必须进 note: PASS 时明细块不打印, 只放 detail 等于没人看得到 (实测踩到)
    if gone:
        note += f" · 清单含 {len(gone)} 项已不存在(应移除)"
    if untracked_frozen:
        note += f" · 清单含 {len(untracked_frozen)} 项未跟踪(勿删, 仅需 git add)"
    return ("FAIL" if bad else "PASS"), note, detail


ARTIFACTS_INV = ROOT / "inventory" / "artifacts.yaml"


def check_artifacts(ctx):
    """生成物清单（D6-P1-1）：**"权威源在别处"的文件，有没有人真的在判它。**

    为什么单独立一项：本仓最贵的失败形态是"**判据通过了，是因为它什么都没判**"——
    而生成物特有的两种病是它的两个变体：
      · **静默缺口**：某文件是推导出来的，**既没人判、也没说明为什么不判** ⇒ 可以长期错着没人知道；
      · **挂名假判**：清单写了 `check: xxx`，但 `xxx` **不是真实断言 id**（改了名/删了项）⇒ 看着有人管。
    本项把这两者都变成 FAIL，并**报覆盖率**（"新增判据必须同时报覆盖率"）。

    第 ① 项（`inventory/*.yaml` 可解析）不是顺手加的：**解析不了 ⇒ 任何"重算 → 比对"都前提失效**，
    而失败会以"下游某个数掉了"的形式远距离显形（本会话已见过 `inventory` 报数掉到 0 仍 PASS 的同族）。
    """
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过生成物清单断言（不复现于 CI 环境即视为通过）", []
    detail = []

    # ① 前提：inventory 真值表必须**全部可解析**（"重算 → 比对"的前置）
    yaml_files = sorted((ROOT / "inventory").glob("*.yaml"))
    bad_parse = []
    for p in yaml_files:
        try:
            yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception as e:
            bad_parse.append(f"{p.name}({type(e).__name__})")
    if bad_parse:
        detail.append("inventory/*.yaml 解析失败 ⇒ 其下游一切'重算比对'前提失效: " + ", ".join(bad_parse))

    # ② 清单本身
    if not ARTIFACTS_INV.exists():
        return "FAIL", "inventory/artifacts.yaml 缺失（本断言的登记依据）", detail
    try:
        inv = yaml.safe_load(ARTIFACTS_INV.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return "FAIL", f"inventory/artifacts.yaml 解析失败: {type(e).__name__}: {e}", detail

    items = list(inv.get("items") or [])
    known_ids = {c["id"] for c in CHECKS}
    covered = exempt = 0
    for it in items:
        p = it.get("path") or "(缺 path)"
        ck, ex = it.get("check"), it.get("exempt")
        if ck and ex:
            detail.append(f"{p}: `check` 与 `exempt` **互斥**（要么判、要么说明豁免，不能既判又豁免）")
        elif ck:
            if ck not in known_ids:
                # 这一条正是"挂名假判"：看着有人管，其实那个 id 不存在（改名/删除后没人发现）
                detail.append(f"{p}: check={ck!r} **不是真实断言 id**（挂在没人跑的判据上 = 挂名假判）")
            else:
                covered += 1
        elif ex:
            exempt += 1
        else:
            # 这一条正是"静默缺口"
            detail.append(f"{p}: **既无 `check` 也无 `exempt`** ⇒ 静默缺口（没人判，也没说明为什么）")

    # ③ 覆盖率必须报（"判据可能什么都没判"的对抗措施）
    note = (f"生成物 {len(items)} 条 · 有断言覆盖 {covered} · 显式豁免 {exempt} "
            f"· inventory yaml 可解析 {len(yaml_files) - len(bad_parse)}/{len(yaml_files)}")
    return ("FAIL" if detail else "PASS"), note, detail




def validate_sensitivity_inv(inv, exists_fn):
    """**纯函数**：`sensitivity.yaml` 的自洽判定（只吃解析后的对象 + 一个 exists 回调 ⇒ 离线可正反夹测）。

    O-51 的定性：该表**权威源在自身**（它就是"内容→档位"的真值），但**建了之后 `ops/` 全域零命中**
    ⇒ 是"**存在但无人读**"的活标本。⇒ 本判据把它的**自洽义务**接上（不新增第二份真值）：

      ① 每条 `path` **必须真实存在**（文件或目录）—— 否则登记指向不存在的东西 = **记录与实效脱节**；
      ② `tier` 必须 ∈ **封闭枚举**（拼错一个档位名不该静默通过）；
      ③ ★ **同一 `path` 不得在两处以"不同 tier"出现** —— "同一事实两个定义点"是本仓头号形态，
         各自看都对、合起来矛盾，且**没有一处会报警**。

    返回 `(bad_list, stats)`；`stats` 供上层**报覆盖率**（"新增判据必须同时报覆盖率"）。
    """
    bad = []
    seen = {}          # path -> (tier, section)
    n = 0
    per_tier = {}
    for sec in SENSITIVITY_SECTIONS:
        for it in (inv.get(sec) or []):
            n += 1
            p = (it or {}).get("path")
            tier = (it or {}).get("tier")
            if not p:
                bad.append(f"[{sec}] 有条目缺 `path`")
                continue
            if tier not in SENSITIVITY_TIERS:
                bad.append(f"[{sec}] {p}: tier={tier!r} 不在封闭枚举 {SENSITIVITY_TIERS}")
            else:
                per_tier[tier] = per_tier.get(tier, 0) + 1
            if not exists_fn(p):
                bad.append(f"[{sec}] {p}: **路径不存在** ⇒ 登记指向空物（记录与实效脱节）")
            if p in seen and seen[p][0] != tier:
                bad.append(f"{p}: **同一路径两处不同 tier**（{seen[p][1]}={seen[p][0]!r} vs {sec}={tier!r}）"
                           f" ⇒ 同一事实两个定义点，各自看都对、合起来矛盾且无人报警")
            else:
                seen[p] = (tier, sec)
    return bad, {"n": n, "tiers": per_tier}


def check_sensitivity(ctx):
    """`inventory/sensitivity.yaml` 的自洽断言（O-51：把"建了没人读"的真值表接上义务）。"""
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 sensitivity 真值表断言", []
    if not SENSITIVITY_INV.exists():
        return "FAIL", "inventory/sensitivity.yaml 缺失", []
    try:
        inv = yaml.safe_load(SENSITIVITY_INV.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return "FAIL", f"inventory/sensitivity.yaml 解析失败: {type(e).__name__}: {e}", []

    default_tier = inv.get("default_tier")
    bad, st = validate_sensitivity_inv(inv, lambda p: (ROOT / p).exists())
    if default_tier != "local-only":
        # fail-closed 的前提：未登记必须是**最严**档。若被改成 public/sanitized ⇒ 静默放宽，必须 FAIL。
        bad.append(f"default_tier={default_tier!r} —— 必须为 'local-only'（fail-closed：未登记不得默认放宽）")

    tiers = " · ".join(f"{k}={v}" for k, v in sorted(st["tiers"].items()))
    note = f"条目 {st['n']} 条 · 档位分布 {tiers} · default={default_tier} · 枚举 {len(SENSITIVITY_TIERS)} 档"
    return ("FAIL" if bad else "PASS"), note, bad


# ── P1-3 `facade`：`cluster.py` 必须**可达**其消费者引用的每一个 `cluster.<符号>` ──────────
FACADE = ROOT / "ops" / "cluster.py"
# 消费形态两种：`import cluster`（用 `cluster.<x>`）与 `import cluster as C`（用 `C.<x>`）
_FACADE_CONSUMER_RE = re.compile(r"^\s*import\s+cluster(?:\s+as\s+([A-Za-z_]\w*))?\s*$", re.M)
_FACADE_DIRS = ("ops", "tests")     # ★ tests 也是契约消费者（实测: test_inbox_seal 用 cluster.INBOX_ROOT 等）


def _strip_py_prose(text):
    """剥掉 `#` 注释与字符串字面量（含 docstring）—— **本仓纪律**：扫代码文本的断言必须区分"代码"与"注释"。

    ⚠ 为什么必须：首版只用正则扫原文 ⇒ 把**文档/注释里出现的 `cluster.py`** 当成引用（抽出符号 `py`）
    ⇒ **假红**。这与 D7-P1-1 那次（"已移除此项"的留档注释让断言假红）是**同一型**的坑。
    strings 用空格占位（避免把两侧代码粘成一个 token）；不做完整词法，够用即可。
    """
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == "#":
            while i < n and text[i] != "\n":
                i += 1
        elif c in "\"'":
            q, triple = c, text[i:i + 3] in ('"""', "'''")
            if triple:
                i += 3
                while i < n and text[i:i + 3] != q * 3:
                    i += 1
                i += 3
            else:
                i += 1
                while i < n and text[i] != q:
                    i += 2 if text[i] == "\\" else 1
                i += 1
            out.append(" ")
        else:
            out.append(c)
            i += 1
    return "".join(out)


def facade_names(text):
    """静态提取 `cluster.py` 对外的**可达名**（三种来源：定义 / 顶层赋值 / 导入重导出）。"""
    names = set(re.findall(r"^def\s+([A-Za-z_]\w*)", text, re.M))
    names |= set(re.findall(r"^class\s+([A-Za-z_]\w*)", text, re.M))
    names |= set(re.findall(r"^([A-Za-z_]\w*)\s*(?::[^=\n]+)?=", text, re.M))
    for braced, plain in re.findall(r"^from\s+[\w.]+\s+import\s+(?:\(([^)]*)\)|([^\n#]+))", text, re.M):
        for seg in (braced or plain or "").split(","):
            n = seg.strip().split(" as ")[-1].strip()
            if re.fullmatch(r"[A-Za-z_]\w*", n or ""):
                names.add(n)
    return names


def validate_facade(consumer_refs, names):
    """**纯函数**：`consumer_refs = {消费者文件名: {符号,...}}`、`names = 门面可达名集` ⇒ 离线可正反夹测。

    P1-3 的定性：本仓已拆出 5 个模块，`cluster_web.py` 用 `import cluster` 复用其符号
    ⇒ **这是一个跨文件的隐式契约**（门面重导出），而**此前门禁 19 项无一检查它**
    ⇒ 谁把符号搬走/改名，`cluster_web.py` 只在**运行到那条路径时**才炸。

    返回 `(bad, stats)`；`stats` 报**覆盖率**（消费者数 / 引用的不同符号数）。
    """
    bad = []
    all_syms = set()
    for consumer, refs in sorted(consumer_refs.items()):
        all_syms |= refs
        for s in sorted(refs):
            if s not in names:
                # 点名：**哪个符号 · 被谁引用**（照 `scripts` 断言"改了没登记就 FAIL 并点名"的成功范式）
                bad.append(f"{consumer} 引用的 cluster.{s} **在门面不可达**（搬走/改名/漏重导出？）")
    # 反向信息（不判死）：门面里"没有任何消费者引用"的名字 —— 只报数，便于日后清理
    orphan = sorted(n for n in names if n not in all_syms and not n.startswith("_"))
    return bad, {"consumers": len(consumer_refs), "syms": len(all_syms), "orphan": len(orphan)}


def check_facade(ctx):
    """P1-3：`cluster.py` 门面符号**可达性**（跨文件隐式契约的唯一机器约束）。"""
    if not FACADE.exists():
        return "FAIL", "ops/cluster.py 缺失（门面本体）", []
    consumer_refs = {}
    for d in _FACADE_DIRS:
        for p in sorted((ROOT / d).glob("*.py")):
            if p.name == FACADE.name or p.name.startswith("cluster_"):
                continue      # 门面自身 / 已拆出的子模块（后者用 `from cluster_xxx import`，不走门面）
            txt = _strip_py_prose(p.read_text(encoding="utf-8", errors="replace"))
            m = _FACADE_CONSUMER_RE.search(txt)
            if not m:
                continue      # 不 import cluster 的文件不构成门面契约（如 rpc_check.py 走子进程）
            alias = m.group(1) or "cluster"
            refs = {x for x in re.findall(rf"\b{re.escape(alias)}\.([A-Za-z_]\w*)", txt)
                    if not x.startswith("__")}
            if refs:
                consumer_refs[f"{d}/{p.name}"] = refs

    names = facade_names(_strip_py_prose(FACADE.read_text(encoding="utf-8", errors="replace")))
    bad, st = validate_facade(consumer_refs, names)
    note = (f"消费者 {st['consumers']} 个 · 引用不同符号 {st['syms']} 个 · 门面可达名 {len(names)} 个 "
            f"· 无消费者引用(仅报数) {st['orphan']} 个")
    return ("FAIL" if bad else "PASS"), note, bad


# ── 断言: cluster 模块依赖方向 (D6-P2-1) ─────────────────────────────
# 目的: `cluster_*.py` 拆出 5 个模块后, "谁能 import 谁"原先**无任何约束** ⇒ 反向依赖会悄悄长回来。
# ★ 必须用 **AST** 而不是正则区分两类 import —— 正则分不清"这行 in 不 in 函数里", 会把两类混成一个桶
#   （本仓头号失败形态），而两者**语义不同**：
#   · **模块级** import = **导入期**依赖 ⇒ 有环 ⇒ `import` 当场就炸 ⇒ **真环, FAIL**；
#   · **函数内懒加载** import = **运行期**耦合 ⇒ 不构成导入环（它是**刻意打破环**的手段），
#     但**反向**（越层）懒加载仍是设计越界 ⇒ **未登记即 FAIL**（登记后 PASS，未命中会自报"已可移除"）。
CLUSTER_GLOB = "cluster*.py"
CLUSTER_LAYER_KEY = "cluster_layers"
CLUSTER_LAZY_ALLOW_KEY = "cluster_lazy_allow"


def _mods_of(node):
    """从单个 Import/ImportFrom 节点取模块名（`from . import x` 的相对形态不取）。"""
    if isinstance(node, ast.Import):
        return {a.name for a in node.names}
    if node.level == 0 and node.module:
        return {node.module}
    return set()


def _collect_imports(node, into):
    """递归收集 import，但**不进入函数体**（函数体里的 import 属"懒加载"，另行收集）。"""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if isinstance(child, (ast.Import, ast.ImportFrom)):
            into |= _mods_of(child)
            continue
        _collect_imports(child, into)


def cluster_dep_edges(text):
    """**纯函数**: 源码 → `(模块级边, 懒加载边)`（模块名 set；**未**过滤"是否本组模块"）。"""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return set(), set()
    top = set()
    _collect_imports(tree, top)
    lazy = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _collect_imports(n, lazy)      # 该函数体(含嵌套块)里的 import；再嵌套的函数由外层 walk 覆盖
    return top, lazy


def cluster_dep_graph(sources):
    """**纯函数**: `{模块名: 源码}` → `{"top": {u:{v}}, "lazy": {u:{v}}}`（只保留**组内**边，去自环）。"""
    g = {"top": {}, "lazy": {}}
    for name, text in sources.items():
        t, l = cluster_dep_edges(text)
        g["top"][name] = {v for v in t if v in sources and v != name}
        g["lazy"][name] = {v for v in l if v in sources and v != name}
    return g


def find_cycles(graph):
    """**纯函数**: 有向图找环 ⇒ `[[n1,n2,…,n1], …]`（DFS 三色；按名排序保证结论**确定**）。"""
    color = {n: 0 for n in graph}
    stack, cycles = [], []

    def dfs(u):
        color[u] = 1
        stack.append(u)
        for v in sorted(graph.get(u, ())):
            if color.get(v) == 1:
                cycles.append(stack[stack.index(v):] + [v])
            elif color.get(v) == 0:
                dfs(v)
        stack.pop()
        color[u] = 2

    for n in sorted(color):
        if color[n] == 0:
            dfs(n)
    return cycles


def validate_cluster_deps(graph, layers, lazy_allow):
    """**纯函数** → `(bad, notes, unhit)`。

    `layers` = 按层从底到顶的 `[[路径,…], …]`；`lazy_allow` = `[[上游, 下游, 原因], …]`。
    规则：① 新模块**必须**在 layers 登记层次；② 模块级图**不得成环**；③ 模块级边**只能向下**（严格下层）；
    ④ **反向**懒加载必须登记（未登记 ⇒ FAIL）；⑤ 已登记但**未命中** ⇒ `unhit`（自报"已可移除"，同 P0-2 纪律）。
    """
    bad, notes, unhit = [], [], []
    lvl = {}
    for i, layer in enumerate(layers):
        for p in layer:
            lvl[Path(p).stem] = i
    # ① 未登记模块 ⇒ 新模块必须声明站在哪一层
    for m in sorted(graph["top"]):
        if m not in lvl:
            bad.append(f"{m}: **未在 inventory/ops.yaml 的 `{CLUSTER_LAYER_KEY}` 登记层次** "
                       f"⇒ 新模块必须显式声明站在哪一层（否则依赖方向无人约束）")
    # ② 成环（模块级 = 导入期依赖 ⇒ 真环）
    for cyc in find_cycles(graph["top"]):
        bad.append(f"**模块级 import 成环**: {' → '.join(cyc)} ⇒ 导入期就会炸"
                   f"（要么拆环，要么把其中一条改成函数内懒加载 + 登记）")
    # ③ 层序：模块级边必须指向**严格下层**
    for u, vs in sorted(graph["top"].items()):
        for v in sorted(vs):
            if u in lvl and v in lvl and lvl[v] >= lvl[u]:
                bad.append(f"**层序越界**: {u}(L{lvl[u]}) → {v}(L{lvl[v]}) —— 只允许依赖**严格下层**")
    # ④ 反向懒加载：不构成环，但仍是越层 ⇒ 须登记
    allow = {(Path(a).stem, Path(c).stem): msg for a, c, msg in lazy_allow}
    hit = set()
    for u, vs in sorted(graph["lazy"].items()):
        for v in sorted(vs):
            if u in lvl and v in lvl and lvl[v] >= lvl[u]:
                if (u, v) in allow:
                    hit.add((u, v))
                    notes.append(f"反向懒加载**已登记**: {u}(L{lvl[u]}) → {v}(L{lvl[v]})")
                else:
                    bad.append(f"**未登记的反向懒加载**: {u}(L{lvl[u]}) → {v}(L{lvl[v]}) "
                               f"⇒ 要么调层，要么在 `{CLUSTER_LAZY_ALLOW_KEY}` 登记原因")
    unhit = allow_unhit(list(allow), hit)
    return bad, notes, unhit


def check_cluster_deps(ctx):
    """P2-1: `cluster_*.py` 依赖方向（未登记模块 / 成环 / 层序越界 / 反向懒加载）。"""
    files = sorted(ROOT.glob(f"ops/{CLUSTER_GLOB}"))
    if not files:
        return "WARN", f"ops/{CLUSTER_GLOB} 无匹配（本断言的登记依据）", []
    src = {p.stem: _read_text(p) for p in files}
    try:
        import yaml          # 与本文件其它断言一致: 函数内导入 ⇒ 缺 pyyaml 时降级而不是整仓报错
    except ImportError:
        return "WARN", "未安装 pyyaml ⇒ 层序无依据（跳过；装上后自动生效）", []
    try:
        inv = yaml.safe_load(OPS_INV.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return "WARN", f"inventory/ops.yaml 不可读 ⇒ 层序无依据: {type(e).__name__}: {e}", []
    layers = inv.get(CLUSTER_LAYER_KEY) or []
    if not layers:
        return "WARN", f"inventory/ops.yaml 缺 `{CLUSTER_LAYER_KEY}` ⇒ 层序无依据（不判）", []
    graph = cluster_dep_graph(src)
    bad, notes, unhit = validate_cluster_deps(graph, layers, inv.get(CLUSTER_LAZY_ALLOW_KEY) or [])
    for k in unhit:
        notes.append(f"⚠ 登记的反向懒加载**未命中**（已可移除）: {k[0]} → {k[1]}")
    n_top = sum(len(v) for v in graph["top"].values())
    n_lazy = sum(len(v) for v in graph["lazy"].values())
    detail = ["层序(底→顶): " + " < ".join("{" + ", ".join(Path(x).stem for x in l) + "}" for l in layers)]
    detail += bad + notes
    note = (f"模块 {len(src)} 个 · 层序 {len(layers)} 层 · 模块级边 {n_top} 条 · "
            f"懒加载边 {n_lazy} 条 · 违规 {len(bad)}")
    if unhit:
        note += f" · ⚠ 未命中登记 {len(unhit)}（已可移除）"
    return ("FAIL" if bad else ("WARN" if unhit else "PASS")), note, detail


# ── 断言: ADR 必留"考虑的替代方案" (D6-P2-2) ──────────────────────────
# 目的: ADR 是"非平凡改动必留决策"的载体; 而"**当时考虑过/否决了哪些方案**"最容易被**静默省略**
#   （写"我决定做什么"容易，写"我否掉了什么"难）⇒ 它是决策记录里**最该被机器盯住**的那一项。
# ★ 锚 = ADR 模板的**现名** `考虑的替代方案（Alternatives Considered）`（见 `spec/vulkan-version-control/ADR_TEMPLATE.md`；
#   ADR-0001/0002 与它同源，其余 6 份于 2026-09-25 由 `否决/比较对象` / `被否的方案` **改名**统一，内容未改）。
#   比较前**规范化**（去括号内容 / 空白 / 全半角）⇒ 防"半角括号 typo"这类**假红**（ADR-0001 历史形态）。
# ⚠ **范围只含 `adr/ADR-*.md`**，**不含** `spec/d6-agent-standard/DECISIONS.md` —— 后者是**表格载体**，
#   "否决/比较对象"是它的**列**（表格在结构上每行都有该槽位，且值可为 `—` 表"确无替代"）⇒
#   门禁的价值在**形状无保证**处；硬要求它也"非空"会假红（实测 D-02 / D-09 该列 = `—`）。






# ── 断言 A3: inventory 单点真值 (P1) ──────────────────────────────
# 目的: 阻止"改了这个忘了那个" —— 端口/模型标识变更时, 保证声明源与真值表一致。
#
# **对账模式, 不是文本扫描** (2026-09-14 实测修正, 详见文档 §11):
#   最初的设计是"扫描全仓库出现的端口/模型名, 未登记即 FAIL"。实测该方案不可行:
#     · 端口: 51 个"端口"里 19 个不是端口 (llama.cpp 提交号 9859、参数值 16384/4096/
#       1024、截断匹配 127/808...)。文本里的数字没有唯一语义。
#     · 模型: 以 gguf 结尾的强标识 114 个, 100% 是路径/文件名, 纯噪声。
#   改为只对**结构化声明源**做对账 —— 精确、零噪声、可长期维护:
#     (a) 入口及其拆分模块的端口常量 (如 STATION_PORT) 与模型路由常量 (如 ROUTE)
#         —— 见 DECL_CLUSTER_FILES (常量层 2026-09-23 抽到 cluster_const.py)
#     (b) docs/三机推理集群使用手册.md 的端点表格行
#   声明源里出现而 inventory 未登记 => FAIL, 并提示"登记真值"或"修正过期引用"。
INVENTORY_DIR = ROOT / "inventory"
DECL_CLUSTER_PY = ROOT / "ops" / "cluster.py"
# 2026-09-23 (阶段 1a 拆分): 声明源可能已搬到"入口的拆分模块"—— 常量层在 cluster_const.py。
# ⚠ **改这里之前先想清楚**: 不覆盖新模块会让本断言**静默降级**（实测: ROUTE/STATION_ROUTES
#   搬走后仍只扫 cluster.py ⇒ "声明源 3 模型标识" 掉成 "0"，而断言照旧 PASS —— 门禁空转的假绿）。
#   凡"常量层再拆分/搬家"，必须同步本清单。
DECL_CLUSTER_FILES = [ROOT / "ops" / "cluster.py", ROOT / "ops" / "cluster_const.py"]
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
    """从声明源解析 (端口, 模型标识)。返回 ({port: [来源]}, {name: [来源]})。

    声明源 = 入口及其拆分模块 (DECL_CLUSTER_FILES) + 手册端点表。"""
    ports, models = {}, {}
    for src in DECL_CLUSTER_FILES:
        if not src.is_file():
            continue
        label = src.name
        text = _read_text(src)
        for m in PORT_CONST_RE.finditer(text):
            for v in re.findall(r":\s*(\d{2,5})", m.group("body")):
                ports.setdefault(int(v), []).append(f"{label}:{m.group('name')}")
        for m in MODEL_CONST_RE.finditer(text):
            # STATION_ROUTES 是**派生表** (键 = 站上真实别名 + 站后缀, 值 = (站, 真实别名)),
            # 不逐条登记到 inventory —— 那会与基础别名重复, 且引入双份要同步的真值。
            # 它的正确性由 aliases 断言的 (7) 子项校验 (更强: 含站维度, 要求 (别名,站) 已声明 conf)。
            if m.group("name") == "STATION_ROUTES":
                continue
            for k in re.findall(r"[\"']([^\"']+)[\"']\s*:", m.group("body")):
                models.setdefault(k, []).append(f"{label}:{m.group('name')}")
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

    # (3b) ★ 段位形态 (O-158 甲, 2026-10-10): `unmanaged` 里**无 `port` 有 `range`** 的条目 ——
    #     形态必须合法, 否则站上对账时它**静默变成"不覆盖"**(坏 range 匹配不上任何口),
    #     真因要到 stations 那一步才表现成"某口未登记"。故三件套在**门口**先判:
    #       range = [lo, hi] 两个整数且 lo ≤ hi · owner 非空 · bind 是 loopback
    #       (护栏「只覆盖 loopback + 已知 owner」的字面落点)。
    #     ⚠ 这类条目**不**参与 (2)(3) 的重复/重叠检查 —— 覆盖由"占用者是谁"决定, 与数字区间无关。
    for e in entries.get("unmanaged") or []:
        if not isinstance(e, dict) or isinstance(e.get("port"), int):
            continue
        rng = e.get("range")
        if rng is None:
            continue                    # 既无 port 又无 range 的注释性散条不判 (旧式, 无关覆盖)
        if not (isinstance(rng, (list, tuple)) and len(rng) == 2
                and all(isinstance(x, int) for x in rng) and rng[0] <= rng[1]):
            detail.append(f"unmanaged 段位条目 range={rng!r} 非法 —— "
                          f"须为 [lo, hi] 两个整数且 lo ≤ hi (见 O-158)")
            continue
        if not e.get("owner"):
            detail.append(f"unmanaged 段位条目 {rng!r} 缺 owner —— 段位形态的覆盖**必须有** "
                          f"owner 闸 (只覆盖 loopback + 已知 owner, 见 O-158)")
        if str(e.get("bind") or "") not in ("127.0.0.1", "::1"):
            detail.append(f"unmanaged 段位条目 {rng!r} 的 bind={e.get('bind')!r} 不是 loopback "
                          f"—— 护栏只允许覆盖 loopback (见 O-158)")

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


# ── 断言 A7: 插件/技能三站同构基线 (P1-5) ─────────────────────────
# 目的: 把 PLUGIN-LEDGER 的"三站完全同构"从**人工文字断言**改成可断言的真值。
# 为什么必须改: 2026-09-15 首次实测即推翻该结论 —— C 站 ARS 链的 25 个软链
# **全部是死链**(源目录 ~/tools/opencode-academic-research 在 C 站不存在), 而
# "只数软链个数"三站恰好都是 25, 手工核对显示"一致"。判据必须定在**可达性**上。
#
# 本断言(index)只做**纯本地**部分(可进 quick 门禁):
#   · items 结构自洽: id 唯一非空 / kind 合法 / expect 类型与 kind 匹配
#   · local_sources 对账: 仓库侧源(ops/agent-skills/*/SKILL.md)的名字集合必须
#     等于它所镜像的 item 的 expect —— 抓"仓库加了技能但没登记", 无需 ssh
#   · known_drift 必须指向存在的 item 与合法站, 且 extra 不得落在 expect 内
# 站上部分在 stations 断言的 (h) 子项 (复用同一次 ssh 往返)。
INVENTORY_PLUGINS = INVENTORY_DIR / "plugins.yaml"
PLUGIN_KINDS = {"scalar", "set", "count", "flag"}
PLUGIN_STATIONS = ("A", "B", "C")


def _plugins_doc():
    """读 inventory/plugins.yaml。文件缺失返回 {}; **解析失败抛异常**(同 ports)。"""
    if not INVENTORY_PLUGINS.is_file():
        return {}
    import yaml
    return yaml.safe_load(INVENTORY_PLUGINS.read_text(encoding="utf-8")) or {}


def _plugin_items(doc):
    """{id: item}。"""
    out = {}
    for it in doc.get("items") or []:
        if isinstance(it, dict) and it.get("id"):
            out[str(it["id"])] = it
    return out


def _plugin_scope(it):
    """item 适用的站; 无 scope = 三站通用。"""
    s = it.get("scope")
    return [str(x) for x in s] if s else list(PLUGIN_STATIONS)


def _plugin_diff(it, got):
    """把站上实得值与基线比对。返回 None=一致, 否则 (差异类, 明细)。

    set 类区分两种差异: ("extra", 只多出的元素) 与 ("diff", 明细) ——
    前者才有可能匹配 known_drift（已登记的多余项降 WARN），
    后者(少了元素/多出未登记元素)一律 FAIL。
    """
    kind, exp = it.get("kind"), it.get("expect")
    if kind == "count":
        try:
            return None if int(got) == exp else ("diff", [got, exp])
        except (TypeError, ValueError):
            return ("diff", [got, exp])
    if kind in ("scalar", "flag"):
        return None if got == exp else ("diff", [got, exp])
    if kind == "set":
        g = {x for x in str(got).split(",") if x}
        e = {str(x) for x in (exp or [])}
        if g == e:
            return None
        if not (e - g):
            return ("extra", sorted(g - e))
        return ("diff", [f"缺{sorted(e - g)}", f"多{sorted(g - e)}"])
    return ("diff", [f"未知 kind={kind!r}"])


def _plugin_src_names(path, glob):
    """仓库侧源的条目名。glob 形如 '*/SKILL.md' → 取条目所在目录名。"""
    files = sorted(path.glob(glob))
    names = set()
    for p in files:
        names.add(p.parent.name if len(p.parts) > len(path.parts) + 1 else p.name)
    return sorted(names)


def check_plugins(ctx):
    """纯本地: 基线结构自洽 + 仓库内源与登记值对账。"""
    if not INVENTORY_PLUGINS.is_file():
        return "WARN", "inventory/plugins.yaml 缺失 (插件同构基线未建)", []
    try:
        doc = _plugins_doc()
    except Exception as e:
        return "FAIL", f"plugins.yaml 解析失败: {type(e).__name__}: {str(e)[:180]}", []

    detail = []
    raw = [it for it in (doc.get("items") or []) if isinstance(it, dict)]
    items = _plugin_items(doc)

    # (1) 结构自洽
    dup = {}
    for i, it in enumerate(raw, 1):
        iid = it.get("id")
        if not iid:
            detail.append(f"items[{i}] 缺 id")
            continue
        dup[iid] = dup.get(iid, 0) + 1
        if it.get("kind") not in PLUGIN_KINDS:
            detail.append(f"{iid} 的 kind 非法 {it.get('kind')!r} "
                          f"(合法: {'/'.join(sorted(PLUGIN_KINDS))})")
        else:
            exp = it.get("expect")
            ok = (isinstance(exp, int) and not isinstance(exp, bool) if it["kind"] == "count"
                  else isinstance(exp, list) and bool(exp) and all(isinstance(x, str) for x in exp)
                  if it["kind"] == "set"
                  else isinstance(exp, str) and bool(exp) if it["kind"] == "scalar"
                  else exp in ("yes", "no"))
            if not ok:
                detail.append(f"{iid} 的 expect 与 kind={it['kind']} 不匹配: {exp!r}")
        if not it.get("purpose"):
            detail.append(f"{iid} 缺 purpose")
        for s in (it.get("scope") or []):
            if str(s) not in PLUGIN_STATIONS:
                detail.append(f"{iid} 的 scope 含非法站 {s!r}")
    for iid, n in sorted(dup.items()):
        if n > 1:
            detail.append(f"item id {iid!r} 重复 {n} 次 —— 后者会覆盖前者")
    if not items:
        detail.append("items 为空 —— 该断言需要基线才能工作")

    # (2) 仓库内源 → 登记值对账 (本地就能抓"加了技能没登记")
    for src in doc.get("local_sources") or []:
        if not isinstance(src, dict):
            continue
        name = src.get("name") or "?"
        mirrors = src.get("mirrors")
        path = ROOT / str(src.get("path") or "")
        glob = str(src.get("glob") or "*/SKILL.md")
        if mirrors not in items:
            detail.append(f"local_sources/{name} 的 mirrors={mirrors!r} 在 items 中不存在")
            continue
        if not path.is_dir():
            detail.append(f"local_sources/{name} 的路径不存在: {src.get('path')}")
            continue
        exp = items[mirrors].get("expect")
        if not isinstance(exp, list):
            detail.append(f"local_sources/{name} 镜像的 {mirrors} 不是 set 类, 无法对账")
            continue
        got = _plugin_src_names(path, glob)
        if got != sorted(exp):
            detail.append(
                f"仓库源 {src.get('path')} 与基线 {mirrors} 不一致: "
                f"源 {len(got)} 项 / 基线 {len(exp)} 项; "
                f"仅在源 {sorted(set(got) - set(exp)) or '无'}; "
                f"仅在基线 {sorted(set(exp) - set(got)) or '无'}")

    # (3) known_drift 自洽
    for kd in doc.get("known_drift") or []:
        if not isinstance(kd, dict):
            continue
        tag = f"known_drift({kd.get('station')}/{kd.get('id')})"
        if kd.get("id") not in items:
            detail.append(f"{tag} 指向不存在的 item")
        if str(kd.get("station")) not in PLUGIN_STATIONS:
            detail.append(f"{tag} 的 station 非法")
        if not kd.get("note"):
            detail.append(f"{tag} 缺 note (登记必须写明原因)")
        extra, exp = kd.get("extra"), (items.get(kd.get("id")) or {}).get("expect")
        if isinstance(extra, list) and isinstance(exp, list):
            inside = [x for x in extra if x in exp]
            if inside:
                detail.append(f"{tag} 的 extra 里有本就属于 expect 的元素 {inside} —— "
                              f"extra 只应列**多余项**")

    n_drift = len([k for k in (doc.get("known_drift") or []) if isinstance(k, dict)])
    note = (f"基线 {len(items)} 项 · 本地源 {len(doc.get('local_sources') or [])} 个 · "
            f"已登记漂移 {n_drift} 项")
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
    declared_conf, declared_stations = set(), set()
    for alias, meta in (models or {}).items():
        if alias != meta.get("alias") or meta.get("_group") == "non_model_conf":
            continue    # non_model_conf (如 rpc-nodes 读的 nodes.env) 不是可加载模型, 不该有按站路由名
        for st in (meta.get("conf") or []):
            declared_conf.add((str(alias), st))
        for st in (meta.get("stations") or []):
            declared_stations.add((str(alias), st))
    # ★ 2026-10-25 (O-138 方案乙): "可加载"有两种后端 ——
    #   ① 站上有 llama.cpp conf（原判据）；② 该别名有 **halogen 容器配方**（CONTAINER_MODELS，
    #   三站通用）。生产全切 halogen 后 A/B 不再保留 conf ⇒ 只认 conf 会把 -a/-b 判成假红
    #   （实测：`conf: [C]` 时先红在本行，随后放宽到"容器配方也算可加载"）。
    #   ⚠ 只放宽"后端存在性"这一半：路由名仍须指向真实别名（real 有配方 = 站上可加载）。
    # ★ 2026-10-26 (T14): 容器配方只证明"站上能加载"，不证明"该站有模型库条目"。
    #   再补一层 stations 声明校验：有配方但 inventory 未声明该站 ⇒ 站上大概率没权重，
    #   加载会走到预检才失败。提前在门禁里点名（区分"无配方"与"未声明"两种缺口）。
    container_backed = set(getattr(cluster, "CONTAINER_MODELS", None) or {})
    for name, (st, real) in sorted(cluster.STATION_ROUTES.items()):
        n += 1
        if (real, st) in declared_conf:
            continue
        if real not in container_backed:
            detail.append(f"按站路由名 {name!r} -> ({st}, {real!r}), 但 inventory/models.yaml "
                          f"未声明 {real} 在 {st} 站有 conf（且该别名无 halogen 容器配方）")
        elif (real, st) not in declared_stations:
            detail.append(f"按站路由名 {name!r} -> ({st}, {real!r}) 有容器配方，"
                          f"但 inventory/models.yaml 未声明 {real} 在 {st} 站有模型库条目 "
                          f"(stations 字段)")
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


# ── 断言 A4b: 容器模型资产预检 (P2, 慢, 非 quick, 2026-10-26) ─────────────
# 为什么新开而不是塞进 check_stations: 后者已承担 conf/权重/凭据/端口四类判据（DESIGN §5.6），
# 再塞容器资产会让"失败归因"变模糊；且它复用的是 conf 视角的 MODEL_PATH，看不见容器内路径。
def check_halogen_assets(ctx):
    """只读：容器配方声明的资产是否在站上就位（镜像 + 权重 + tokenizer）。

    ★ 站不可达 ⇒ **跳过并记 WARN**，不判 FAIL —— 未部署/掉线的站不该把门禁染红
      （与 Q2「不对未部署的站假红」一致）。跳过信息必须出现在 note/output 里，不得静默。
    """
    sys.path.insert(0, str(ROOT / "ops"))
    try:
        import cluster
    except Exception as e:
        return ("WARN", f"无法导入 cluster.py ({type(e).__name__}: {e})", [])

    _, models = load_inventory()
    declared = {}
    for alias, meta in (models or {}).items():
        if alias == meta.get("alias"):
            declared[str(alias)] = [str(s) for s in (meta.get("stations") or [])]

    detail, warn, n = [], [], 0
    for alias in sorted(cluster.CONTAINER_MODELS):
        for st in declared.get(alias, []):
            ok_h, out_h = cluster.ssh_run(st, "true", strict=True)
            if not ok_h:                      # 未部署/不可达 ⇒ 不判（避免假红）
                warn.append(f"{st} 站不可达，跳过 {alias} 资产预检: {str(out_h)[:80]}")
                continue
            n += 1
            pre = cluster.preflight_container(alias, st)
            if not pre["ok"]:
                detail.append(f"{st} 站 {alias}: " + "; ".join(pre["problems"]))
    note = f"容器资产预检 {n} 站例" + (f"（{len(warn)} 站例跳过）" if warn else "")
    if detail:
        return ("FAIL", note, detail)
    if warn:                                  # 跳过信息必须可见，不得静默丢在局部变量里
        return ("WARN", note, warn)
    return ("PASS", note, [])


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

# 站上 LAN 地址采集命令 —— ★ **单一实现**：直连探针（本 STATION_CMD 的 [lanip] 段）与
#   USB4 降级通道（`_lanip_via_usb4` 经邻站中转）**共用同一条**，避免"同一事实两个定义点"。
#   · `scope global` 天然排除 `lo` 的 `scope host`（**不要**用 `grep -v lo` —— "global" 里就含 `lo`）；
#   · 整串**不含任何引号** ⇒ 可安全嵌进 `ssh <ip> "<cmd>"` 的双引号里（引号嵌套是本仓反复踩的坑）。
_LANIP_CMD = "ip -4 -o addr show scope global 2>/dev/null | cut -c1-160"

STATION_CMD = (
    "printf '\\n[cfg]\\n'; sha256sum " + " ".join(WATCHED) + " 2>/dev/null | cut -c1-16; "
    "printf '\\n[conf]\\n'; ls -1 /etc/llama-instances/*.env 2>/dev/null "
    "| xargs -r -n1 basename | sed 's/\\.env$//' | tr '\\n' ' '; echo; "
    "printf '\\n[bind]\\n'; ss -ltn 2>/dev/null | awk 'NR>1{print $4}' | tr '\\n' ' '; echo; "
    # (i) LAN 地址实况 (ADR-0006 v1.1 · D6, 2026-09-29): 站上**实际**的 global-scope IPv4。
    #   为什么必须从站上取（而不是像旧版那样只看 master 侧 `ssh -G` 的绑定）:
    #     旧判据的射程靠"别名"，C 站 `host: null` ⇒ **整站被跳过**，于是 2026-09-29 C 的
    #     LAN 由 .37 漂到 .8 时，门禁只报"可达 2/3 站"、**给不出根因**。
    #   ⚠ 本段**不新增连接** —— 搭在同一次合并 ssh 上（与 [bind]/[conf] 同源）。
    "printf '\\n[lanip]\\n'; " + _LANIP_CMD + "; "
    # UDP 侧单独一段 (P1-4): 系统里长期监听的 UDP 端口并不少 (nmbd/avahi/NetworkManager/
    # wsdd/netconsole/rpc.statd), 只查 TCP 会让它们对账时"看不见"。
    "printf '\\n[ubind]\\n'; ss -lun 2>/dev/null | awk 'NR>1{print $4}' | tr '\\n' ' '; echo; "
    # ★ 占用者身份面 (O-158 甲, 2026-10-10): 段位形态条目 (`unmanaged` 里无 `port`、有 `owner`+`range`)
    #   的第三道闸要判"这个口是不是登记的 owner 占的" ⇒ 必须取"监听口 → 占用者名"。
    #   为什么必须 sudo: 非 root 的 `ss -p` 只显示**本用户**的进程, 而 rpc.statd 这类系统服务
    #   跑在 root 下 (实测三站 `sudo -n` 均可非交互用, 2026-10-10)。⚠ 取不到 (sudo 失败等) ⇒
    #   门禁侧 **fail-closed**: 段位条不覆盖 ⇒ 该口照常报"未登记"并点名"占用者取数缺失"
    #   (判不了 ≠ 通过)。⚠ 原始行**不裁剪** (门禁侧只解析一次; 第 4 列 = addr:port, 行尾含
    #   users:(("名",pid=..,fd=..)))。
    "printf '\\n[towner]\\n'; sudo -n ss -ltnp 2>/dev/null; "
    "printf '\\n[uowner]\\n'; sudo -n ss -lunp 2>/dev/null; "
    # 插件面事实 (P1-5): 由站上工具一次性汇报 `id=value` 行, 判定留在门禁侧。
    # 不把采集逻辑内联在这里 —— JSONC 解析 + 目录遍历 + 软链可达性判断用 shell
    # 单行串写会变成转义地狱, 且三站口径无法保证一致。
    "printf '\\n[plug]\\n'; plugin-probe 2>/dev/null || true; "
    "printf '\\n[mpath]\\n'; for f in /etc/llama-instances/*.env; do [ -e \"$f\" ] || continue; "
    "a=${f##*/}; a=${a%.env}; "
    "CG=$(command -v conf-get 2>/dev/null || echo /usr/local/bin/conf-get); "
    "p=$(\"$CG\" \"$f\" MODEL_PATH 2>/dev/null); rc=$?; "
    "if [ \"$rc\" -ne 0 ] || [ -z \"$p\" ]; then echo \"$a NO_MODEL_PATH\"; "
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
    # 2026-09-16 (A) 判据升级: 原为「claude.key vs unsloth.key 两个文件互相比较」。实测该判据
    # 背后藏着结构缺陷 —— claude.key 是引擎 key 的第二份拷贝而**没有任何写入方** (infer-load
    # 每次加载只重铸落盘 unsloth.key), 于是它必然陈旧: C 站遗留脱敏占位串, A/B 只是靠人工
    # 同步过一次才对上, 且**下次加载即变黄**。改为比较「apiKeyHelper 的实际输出 vs 同站引擎
    # key」—— 这才是功能判据 (claude 真正拿到的 key), 且单一真值就是 unsloth.key。
    # helper 不可用时输出 SKIP (该情形已由上面 helper=EMPTY/MISSING/NOEXEC 报出, 不重复告警)。
    "UK=$(cat ~/.config/rpc/unsloth.key 2>/dev/null | tr -d '\\n'); "
    "if [ -z \"$OUT\" ]; then echo 'claudekey=SKIP_NO_HELPER'; "
    "elif [ \"$OUT\" = \"$UK\" ]; then echo 'claudekey=HELPER_EQ_UNSLOTH'; "
    "else echo 'claudekey=DIFFERS'; fi; "
    # (f2) unsloth studio 日志的明文面 (2026-09-16 增补): studio 每次加载都会把引擎 key 写进
    # ~/.unsloth/run-<alias>.log (实测每次 4 处), 而 infer-load 正是**从该日志 grep 取 key** ⇒
    # "日志含 key" 是设计使然、无法消除, 所以判据只能落在**权限**上:
    #   ~/.unsloth 须 700, run-*.log 须 600 (默认 umask 022 下是 775/664 ⇒ 组与其他用户可读)。
    # 顺带报"含 key 的日志份数 + 总份数", 供评估存量(实测三站曾累积 16 个历史 key / 64 处明文)。
    "DP=$(stat -c %a $HOME/.unsloth 2>/dev/null || echo NA); "
    "LF=$(ls -1 $HOME/.unsloth/run-*.log 2>/dev/null | wc -l); "
    "LK=$(grep -lE 'sk-(or-v1|unsloth|RPC|local|lm)-[A-Za-z0-9_-]{6,}' $HOME/.unsloth/run-*.log 2>/dev/null | wc -l); "
    "LL=$(find $HOME/.unsloth -maxdepth 1 -name 'run-*.log' ! -perm 0600 2>/dev/null | wc -l); "
    "echo \"unslothlog=dirperm:${DP} files:${LF} withkeys:${LK} loose:${LL}\"; "
    # (h) 长龄 orphan 探针 (O-58, 2026-09-25): 站上 ad-hoc ssh 探针/派发留下的僵尸/长龄进程。
    #   起因(一手实测): B 站留了 2 条 —— `bash` 1-12:19 与 `bash`+**活着的裸 `opencode`**
    #   1-04:59(47 fd、持**共享** `opencode.db` 180MB)；根因是**未加引号的 `|`** 被远端 shell
    #   当管道(纪律 12)。该信号此前**只能靠人肉 `ps` 偶然撞见** ⇒ 本段把它变机判。
    #   ⚠ 模式**不带空格**且用**多枚 `-e`**：带空格的引号经 PS/ssh 会被剥掉，远端 shell 会把
    #     模式后半当**文件名**(纪律 12, 实测 `grep: run: 没有那个文件或目录`)。
    #   只输出 `pid ppid etimes comm` 四列，**阈值与豁免全留在门禁侧**(与 [conf]/[mpath] 同分工)。
    "printf '\\n[orph]\\n'; ps -eo pid=,ppid=,etimes=,comm= 2>/dev/null "
    "| grep -e opencode -e claude -e timeout -e defunct | head -20; "
    # (i) O-70 第二类: 白名单**之外、但是我们自己的**残留（2026-09-25）—— **只报数, 不判定**。
    #   为什么需要: (h) 的白名单只认 4 个 comm ⇒ 实测那条**真孤儿**(`bash /tmp/agent-cli-task-*.sh`
    #     + 它的 `sleep` 子壳, 存活 **28.6h**, 见台账 O-72)**完全不在白名单里** ⇒ 只因人肉 `ps` 才发现
    #     = b3 说的"**在路灯下找钥匙**"。
    #   ⚠⚠ 第一版按 `ps -u $USER --ppid 1` 取 —— **实测两处都不成立**:
    #     ① 在一台桌面机上它抓到 **122 条系统守护**(`systemd-journald`/`udevd`/`avahi-daemon`…, 全是 **root**)
    #        ⇒ 说明 `$USER` 在**非登录 ssh 会话**里可能为空 ⇒ `-u` 过滤**静默失效**（纪律 12 同族: 别赌远端变量在）;
    #     ② 即便过滤对了, 桌面用户的 `ppid=1` 也天然包含 `systemd --user` 等**合法**长龄进程 ⇒ 恒有噪声。
    #   ⇒ 改成按**产物名**匹配(args 里出现我们自己的脚本名): 这是"事实"判据、噪声面小得多,
    #     且**正好**覆盖 O-72 那一类。阈值仍留在门禁侧(下面按 `ORPHAN_SEC` 判)。
    # ★★ 2026-09-26 结构性修法：**按 pgid 排除探针自己的整个进程组**（不再靠文本巧合）。
    #   起因（本轮实测）：直查时用 `pgrep -af agent-cli-task …` ⇒ **它自匹配了自己所在的命令行**
    #     ⇒ 说明"自匹配"是这条探针的**真实**风险，不是理论风险。
    #   旧版靠 `grep -v -e grep` 恰好挡住（自匹配行里也含 `grep` 一词）—— **侥幸成立**，
    #     代价是：**任何 args 里含子串 `grep` 的真残留会被静默排掉**（"路灯下找钥匙"的第二个面）。
    #   ⚠ 我曾以为"把排除键换成 `ps -eo`"是正解 —— **三站实测证伪**：那样会漏掉
    #     `grep -e agent-cli-task …` **进程自己**（其 args 含 `agent-cli-task` 却不含 `ps -eo`）⇒ 假阳性 1 行。
    #   ⇒ 现改为：`ps` 多输出一列 pgid + `awk` 剔除 `$2 == 自身 pgid`。
    #     shell / ps / grep / awk **同属一个进程组** ⇒ 一次全剔，**不依赖任何模式串**。
    #   ★ 实测对照（三站，注入假残留前后）：
    #       无残留 ⇒ **NEW 0 行**（旧版 0 行 / NAIVE 1 行假阳性）；有真残留 ⇒ **NEW 1 行，且只有真的那条**。
    #   ⚠ awk 把 pgid 列清空 ⇒ 输出行多一个空格；门禁侧用 `line.split()` 解析 ⇒ 不受影响（已实测）。
    "printf '\\n[orph2]\\n'; ps -eo pid=,pgid=,etimes=,args= 2>/dev/null "
    "| awk -v pg=$(ps -o pgid= -p $$ | tr -d ' ') '$2!=pg { $2=\"\"; print }' "
    "| grep -e agent-cli-task -e agent-stage- -e _oc_session_meta -e _p3_run -e _station_ready -e _slot_gate "
    "| head -20; "
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


def _ssh_g_hostname(alias):
    """`ssh -G <别名>` 的 hostname 字段 (**纯本地展开, 不建连**)。ssh 不可用返回 None。

    用于 ADR-0006 的 LAN 绑定对账: 名字是否仍被绑定到 net.yaml 登记的 LAN IPv4。
    """
    try:
        r = subprocess.run(["ssh", "-G", alias], capture_output=True, text=True,
                           timeout=20, encoding="utf-8", errors="replace")
    except Exception:
        return None
    for line in (r.stdout or "").splitlines():
        if line.lower().startswith("hostname "):
            return line.split(None, 1)[1].strip()
    return None


# ── LAN 地址对账（ADR-0006 v1.1 · D6，2026-09-29）──────────────────────────────
# 背景（一句话）：D4 的判据靠 `ssh -G <别名>`，于是 `host: null` 的 C 站**整站不在射程内**；
#   2026-09-29 C 的 LAN 由 .37 漂到 .8 时，6 项断言只报"可达 2/3 站"、**不给根因**
#   —— 正是 ADR-0006 D4 自己要消灭的那个"ssh 连不上的谜题"。
# 本节把判据换成"**站上实况** vs net.yaml 真值"，并在 LAN 不可达时**经 USB4 段向邻站中转**去问。
#
# 为什么判据与 IO **分开**：① 门禁侧只判不做 IO ⇒ **可先验红**（本仓纪律，见
#   tests/test_rpc_check_lan_drift.py）；② 直连与降级通道产出**同一种** `seen` ⇒ 判据只有一份。
def _local_lan_ip(probe_ip):
    """取**本机通往 probe_ip 那条路**上使用的源地址（= 本机的 LAN 管理面地址）。

    为什么用 UDP-connect 这个怪招：① **不发任何包**（UDP connect 只做路由选择），零流量、不打扰；
    ② 只用 stdlib（`ipconfig` 解析在中文 Windows 上字段名会变、且不可移植）；
    ③ 它回答的正是我们要问的问题 —— "**我用哪个地址去够那些站**"（而不是"本机一共配了哪些地址"）。
    失败返回 None（调用方按"无法判定"处理，**不猜**）。

    ★ 为什么主控也要判（2026-09-29 实测新增）：本轮排查中**主控自己的 LAN 先漂了**
      （`192.168.1.36` → `192.168.10.102`，整段换网），表现就是"三站全不可达" —— 又一个
      "可达 0/3 却不给根因"的谜题，且它比单站漂移**更彻底**（控制面全断）。
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((str(probe_ip), 9))
        return s.getsockname()[0]
    except Exception:
        return None
    finally:
        s.close()


def _parse_lanip(text):
    """解析 `ip -4 -o addr show scope global` 的原始输出 ⇒ [{iface, ip, cidr, dynamic}]。

    样例: `2: eno1    inet 192.168.1.8/24 brd 192.168.1.255 scope global dynamic noprefixroute eno1\\ ...`
    ⇒ 取行首的 `序号: 接口`、`inet <地址>/<前缀>`，并看整行里有没有 `dynamic`（DHCP）。
    ★ **这里也丢回环**（defense in depth）：真值源命令已用 `scope global` 过滤掉 `lo`，
      但**判据不该依赖调用方那半条 shell** —— 若将来有人动 `_LANIP_CMD`，`lo` 会变成
      "非 USB4 网段的唯一地址"而被误当成 LAN 地址。故解析层再过一遍。
    解析不出的行**忽略**（不猜）；全空 ⇒ 调用方走降级通道/报"无法判定"。
    """
    rows = []
    for ln in (text or "").splitlines():
        m = re.match(r"^\s*\d+:\s+(\S+)\s+inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)\s+(.*)$", ln)
        if not m or m.group(1) == "lo" or m.group(2).startswith("127."):
            continue
        rows.append({"iface": m.group(1), "ip": m.group(2),
                     "cidr": f"{m.group(2)}/{m.group(3)}",
                     "dynamic": "dynamic" in m.group(4)})
    return rows


def pick_lan_addr(rows, iface_hint, seg_nets):
    """从站上所有 global 地址里挑出**LAN 管理面**那一个。返回 ({...} | None, 原因串)。

    为什么需要挑：站上同时有 USB4 三段地址，都算 `scope global`。挑法（**先精后宽**）：
      ① 登记了 `iface` ⇒ **认接口**（最精确，且与 net.yaml 的声明同源）；
      ② 否则排除 USB4 各段的网段，剩下的**唯一**一个才算 LAN 地址；
      ③ 剩 0 个或多个 ⇒ **不猜**，返回原因（同本仓"解析失败不能表现成业务全错"纪律）。
      ④ ①命中但与②的候选集不一致（登记接口 ≠ 非 USB4 地址）⇒ 也返回原因 —— 那说明
         net.yaml 的 `iface` 与 `segments` 至少有一个是错的。
    """
    rows = rows or []
    lan_rows = [r for r in rows if not any(ipaddress.ip_address(r["ip"]) in n for n in (seg_nets or []))]
    if iface_hint:
        hit = [r for r in rows if r["iface"] == iface_hint]
        if len(hit) == 1:
            if lan_rows and hit[0]["ip"] not in {r["ip"] for r in lan_rows}:
                return None, (f"net.yaml 登记的 iface={iface_hint} 上的地址 {hit[0]['ip']} "
                              f"落在 USB4 网段内（与 segments 冲突）⇒ net.yaml 自相矛盾, 不猜")
            return hit[0], None
        if len(hit) > 1:
            return None, f"iface={iface_hint} 上有多个 global 地址 ({[r['ip'] for r in hit]}) ⇒ 不猜"
        return None, (f"net.yaml 登记的 iface={iface_hint} 在站上不存在（实测接口: "
                      f"{sorted({r['iface'] for r in rows})}）")
    if len(lan_rows) == 1:
        return lan_rows[0], None
    if not lan_rows:
        return None, "站上没有任何非 USB4 网段的 global 地址 ⇒ 该站 LAN 可能已断"
    return None, f"非 USB4 网段的 global 地址有 {len(lan_rows)} 个 ({[r['ip'] for r in lan_rows]}) ⇒ 不猜"


def validate_lan_addr(lan_doc, seen, seen_master=None):
    """★ 纯判据（D6）：`net.yaml §lan` 真值 vs **实测** LAN 地址。返回 (detail, warn, info)。

    detail(FAIL) = 实测 ≠ 真值 —— ★ 这里必须**带根因与修法**（本次改判据的全部意义所在）
    warn         = 判定**不成立**（探不到 / 解析不出 / 登记自相矛盾）或接口漂移
    info         = 射程声明：哪些站"没有可判的东西"必须**显式说出来**（不得像旧版那样静默跳过）

    seen        : {station: {"ip","iface","dynamic"} | {"error": "<原因>"} | None}
                  （None = 该站根本没采集到 ⇒ 也算"判定不成立"，**不是**通过）
    seen_master : {"ip": ...} | {"error": ...} | None —— **主控自身**的 LAN 地址。
      ★ 射程含主控的理由（2026-09-29 实测）：主控的 LAN 一漂，**三站全不可达** ——
        那是"可达 0/3 却不给根因"的最坏形态。主控地址就登记在 net.yaml §lan 的 `master.ip`。
    """
    detail, warn, info = [], [], []

    # ⓪ **主控自身**（先判它：它错了，下面三站的"不可达"是**同一个根因**，不是三个问题）
    m_want = ((lan_doc.get("master") or {}) or {}).get("ip")
    if m_want:
        if not seen_master:
            warn.append(f"master 自身 LAN 地址**无法判定**（net.yaml §lan.master 登记 {m_want}）")
        elif seen_master.get("error"):
            warn.append(f"master 自身 LAN 地址**无法判定**：{seen_master['error']}")
        elif seen_master.get("ip") and seen_master["ip"] != m_want:
            detail.append(
                f"★★ **master（本机）自身的 LAN 地址已漂移**: {m_want} → {seen_master['ip']} "
                f"—— ★ 这是**三站全部不可达**的根因（控制面源地址变了）；"
                f"先修 master（接到正确的网 / 或更新 net.yaml §lan.master 的登记），再谈各站")
        elif seen_master.get("ip"):
            info.append(f"master 自身 LAN 地址与真值一致: {seen_master['ip']}")
    for ent in (lan_doc.get("stations") or []):
        if not isinstance(ent, dict):
            continue
        st, want, iface_hint = ent.get("station"), ent.get("ip"), ent.get("iface")
        if not st or not want:
            warn.append(f"net.yaml §lan 有条目缺 station/ip, 本项无法判: {ent!r}")
            continue

        # ① master 侧**名字绑定**（ADR-0006 D1 的资产）—— 与站上实况是**两个不同的面**，都留着。
        alias = ent.get("host")
        if not alias:
            # ★ 射程**显式化**：旧版这里是一句 `continue`，于是"C 不在射程内"**无人知道**。
            info.append(f"{st} 站在 net.yaml 里无别名(host: null) ⇒ 无 master 侧绑定可判；"
                        f"该站由下面的『站上实况』覆盖（射程声明, 非跳过）")
        else:
            got = _ssh_g_hostname(alias)
            if got is None:
                warn.append(f"`ssh -G {alias}` 不可用 —— 无法核对 master 侧绑定 (该名应绑定到 {want})")
            elif got != want:
                detail.append(f"master 侧绑定漂移: `ssh -G {alias}` 的 hostname={got}, "
                              f"而 net.yaml §lan 登记 {want} ⇒ 同步 master ~/.ssh/config 与 net.yaml")

        # ② ★ 站上实况（D6 新增；不依赖别名 ⇒ 三站全覆盖）
        s = seen.get(st)
        if not s:
            warn.append(f"{st} 站 LAN 地址**无法判定**：直连采集不到，USB4 降级通道也没取回 ⇒ "
                        f"本项对该站**不成立**（不是通过）")
            continue
        if s.get("error"):
            warn.append(f"{st} 站 LAN 地址**无法判定**：{s['error']}")
            continue
        got, got_iface, dyn = s.get("ip"), s.get("iface"), s.get("dynamic")
        if not got:
            warn.append(f"{st} 站 LAN 地址**无法判定**：采集到但解析不出 (原始: {str(s)[:80]})")
            continue
        if got != want:
            detail.append(
                f"★ {st} 站 LAN 地址**已漂移**: {want} → {got} "
                f"(iface={got_iface}, scope={'dynamic/DHCP' if dyn else 'static'}) —— "
                f"这与「{st} 站不可达 / 依赖它的断言红灯」是**同一件事**, 根因在此。"
                f"修法: 同步三处真值 (inventory/net.yaml §lan · ops/cluster_const.py 的 STATIONS · "
                f"master ~/.ssh/config); 要**根治**见 ADR-0006 v1.1 的 D5")
        else:
            info.append(f"{st} 站 LAN 地址与真值一致: {got} (iface={got_iface})")
        if iface_hint and got_iface and iface_hint != got_iface:
            warn.append(f"{st} 站 LAN 地址所在接口已变: 实测 {got_iface}, net.yaml 登记 {iface_hint} "
                        f"⇒ 更新 net.yaml §lan 的 iface")
    return detail, warn, info


def _lanip_via_usb4(target, segs, live, ssh_run):
    """LAN 直连采集失败时，经**与该站有 USB4 直连的邻站**中转，去问它自己的 LAN 地址。

    ★ 这是 D6 的关键一步：它让「站不可达」与「地址漂移」**可区分**。
      2026-09-29 实测：C 的 LAN 已断（.37 消失），但经 `B → 10.10.11.3` 完全可达
      ⇒ 能问出它当时的真实地址（.8）—— 旧判据在这里只会吐一句"可达 2/3 站"。
    邻站与目标站的 USB4 地址**全部从 net.yaml §segments 派生**（不硬编码拓扑）。
    返回 (rows, err)：err=None 表示取回；否则是**响亮**的原因串（不静默、不降级成"通过"）。
    """
    cands = []
    for sg in (segs or []):
        if not isinstance(sg, dict):
            continue
        for e in (sg.get("ends") or []):
            if isinstance(e, dict) and e.get("station") == target and e.get("peer") and e.get("ip"):
                cands.append((e["peer"], e["ip"]))
    if not cands:
        return [], f"net.yaml §segments 里没有 {target} 站的 USB4 端点 ⇒ 无降级通道可走"
    errs = []
    for peer, ip in cands:
        if not live.get(peer):
            errs.append(f"邻站 {peer} 自身不可达")
            continue
        try:
            ok, out = ssh_run(peer, f'ssh -o BatchMode=yes -o ConnectTimeout=6 {ip} "{_LANIP_CMD}"',
                              timeout=40)
        except Exception as e:
            errs.append(f"经 {peer}→{ip}: {type(e).__name__}: {str(e)[:60]}")
            continue
        rows = _parse_lanip(out)
        if ok and rows:
            return rows, None
        errs.append(f"经 {peer}→{ip}: {'取回但解析不出' if ok else 'ssh 未成功'}")
    return [], f"降级通道全失败 ({'; '.join(errs)})"


def _is_loopback_addr(a):
    """`ss` 输出里的 Local 地址是不是 loopback —— **段位形态的护栏** (O-158 甲, 2026-10-10:
    "只覆盖 loopback + 已知 owner")。纯函数 ⇒ 可离线单测。"""
    s = str(a or "").strip()
    return s.startswith("127.") or s in ("::1", "[::1]", "localhost")


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
    #     必须"引用得到、非空、可执行"; 以及 claude helper 的输出是否等于同站引擎 key。
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
            elif line.startswith("claudekey="):
                # 2026-09-16 (A): 判据改为「helper 输出 == 同站 unsloth.key」。SKIP_NO_HELPER
                # 不在此告警 (helper 自身的问题已由上面 helper= 行报出)。
                if line.split("=", 1)[1] == "DIFFERS":
                    warn.append(f"{st} 站 claude apiKeyHelper 的输出与同站引擎 key "
                                f"(~/.config/rpc/unsloth.key) 不一致 —— claude 走本地 :8080, "
                                f"必须与 opencode 用同一份引擎 key; 站上跑一次 infer-load 会重铸该 key")
            elif line.startswith("unslothlog="):
                # 2026-09-16 (f2): unsloth studio 日志的明文面 —— 判据是**权限**而非"含不含 key"
                # (studio 每次加载必写 key 进日志, 且 infer-load 依赖从日志取 key, 消除不掉)。
                kv = dict(p.split(":", 1) for p in line.split("=", 1)[1].split() if ":" in p)
                dp = kv.get("dirperm", "NA")
                loose = kv.get("loose", "0")
                wk = kv.get("withkeys", "0")
                if dp not in ("700", "NA"):
                    warn.append(f"{st} 站 ~/.unsloth 权限 {dp} (应 700) —— 该目录含 studio 每次"
                                f"加载写入的引擎 key 明文日志; 修: chmod 700 ~/.unsloth")
                if loose != "0":
                    warn.append(f"{st} 站 {loose} 份 run-*.log 权限非 600 (含 key 的共 {wk} 份) "
                                f"—— 修: chmod 600 ~/.unsloth/run-*.log")

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
        by_port, by_range = {}, []
        for g in ("managed", "third_party", "unmanaged"):
            for e in port_entries.get(g) or []:
                if not isinstance(e, dict):
                    continue
                if isinstance(e.get("port"), int):
                    by_port.setdefault(e["port"], []).append((g, e))
                elif e.get("range"):
                    by_range.append((g, e))       # ★ 段位形态 (O-158 甲, 2026-10-10)

        def _proto_ok(e, side):
            """proto 语义: tcp/http/https → TCP 侧; udp → UDP 侧;
                        tcp+udp → 两侧 (mihomo 的 mixed / DNS 端口即双栈);
                        缺省 → 两侧都算 (unmanaged 里的系统端口多不关心协议侧)。"""
            p = str(e.get("proto") or "").lower()
            if p == "udp" and side != "udp":
                return False
            if p in ("tcp", "http", "https") and side != "tcp":
                return False
            return True

        def _range_hits(st, side, port):
            """段位形态里「站 + 协议侧 + 端口落在 range 内」三项都命中的条目。"""
            out = []
            for g, e in by_range:
                rng = e.get("range")
                if not (isinstance(rng, (list, tuple)) and len(rng) == 2
                        and all(isinstance(x, int) for x in rng)
                        and rng[0] <= port <= rng[1]):
                    continue
                if st not in _scopes(e) or not _proto_ok(e, side):
                    continue
                out.append((g, e))
            return out

        def _reg_covers(port, side, st, addr=None, names=None):
            """分配表是否已登记该 (端口, 协议侧, 站) —— 两种形态:

            ① **整数 `port` 条目** (旧口径, 一字未改): 命中 (端口, 侧, 站) 即覆盖。
            ② ★ **段位形态** (O-158 甲, 2026-10-10): 无 `port`、有 `owner` + `range` ⇒
               **三闸齐**才覆盖 —— 端口落在 range 内 · 站上实况**绑在 loopback** ·
               占用者名**命中登记 owner**。⚠ 占用者名取不到 (sudo -n 失败等) ⇒ **不覆盖**
               (**判不了 ≠ 通过**)。护栏 = 「只覆盖 loopback + 已知 owner」: 段位写得再宽
               也**吞不掉**别的形态的口 (非 loopback / 别的 owner / 无名可取 ⇒ 照常报未登记)。
            """
            for _g, e in by_port.get(port, []):
                if st not in _scopes(e) or not _proto_ok(e, side):
                    continue
                return True                  # tcp+udp 与缺省都覆盖两侧
            for _g, e in _range_hits(st, side, port):
                if not _is_loopback_addr(addr):
                    continue
                if names and e.get("owner") in names:
                    return True
            return False

        def _range_miss(port, side, st, addr, names):
            """段位命中了「站+侧+段位」却没接住 ⇒ 点名是**哪一道闸**没过 (只作 FAIL 文案后缀;
            防"段位写得含糊 ⇒ 真因不可见")。"""
            for _g, e in _range_hits(st, side, port):
                own = e.get("owner", "?")
                if not _is_loopback_addr(addr):
                    return (f"；⚠ 段位条目 (owner={own}) 只覆盖 loopback, 站上实况绑的是 {addr} "
                            f"—— 见 O-158")
                if not names:
                    return (f"；⚠ 段位条目 (owner={own}) 覆盖此段位但**占用者取数缺失** "
                            f"(站上 sudo -n ss 无该口?) —— 判不了 ≠ 通过 (O-158)")
                if own not in names:
                    return (f"；⚠ 段位条目 (owner={own}) 覆盖此段位但**占用者名未命中** —— "
                            f"站上取到 {'/'.join(sorted(names))} —— 见 O-158")
            return ""

        def _listening(st, sec):
            out = set()
            for tok in (live[st].get(sec) or "").split():
                if ":" in tok:
                    p = tok.rpartition(":")[2]
                    if p.isdigit():
                        out.add(int(p))
            return out

        def _listen_rows(st, sec):
            """`(addr, port)` 明细 (同口不同绑址各一条) —— 段位形态判 loopback 用;
            `_listening` 只留端口 (旧口径, 方向二仍在用)。"""
            out = set()
            for tok in (live[st].get(sec) or "").split():
                if ":" not in tok:
                    continue
                a, _, p = tok.rpartition(":")
                if p.isdigit():
                    out.add((a, int(p)))
            return out

        def _owners_by_socket(st, sec):
            """{(addr, port): {占用者名}} —— 由 `[towner]/[uowner]` (sudo `ss -lXnp`) 解析。

            行格式: 第 4 列 = Local `addr:port`, 行尾 `users:(("名",pid=..,fd=..))`。
            ⚠ 无该 socket / 无 users 字段 ⇒ 查不到 ⇒ 段位条**不覆盖** (fail-closed)。
            """
            out = {}
            for line in (live[st].get(sec) or "").splitlines():
                f = line.split()
                if len(f) < 4 or ":" not in f[3]:
                    continue
                a, _, p = f[3].rpartition(":")
                if not p.isdigit():
                    continue
                m = re.search(r"users:\((.*)\)", line)
                out[(a, int(p))] = set(re.findall(r'"([^"]+)"', m.group(1))) if m else set()
            return out

        for st in reach:
            owners = {"tcp": _owners_by_socket(st, "towner"),
                      "udp": _owners_by_socket(st, "uowner")}
            for side, sec in (("tcp", "bind"), ("udp", "ubind")):
                rows_by_port = {}
                for addr, port in _listen_rows(st, sec):
                    rows_by_port.setdefault(port, []).append(addr)
                for port, addrs in sorted(rows_by_port.items()):
                    checked_ports += 1
                    miss = [a for a in sorted(addrs)
                            if not _reg_covers(port, side, st, a, owners[side].get((a, port)))]
                    if not miss:
                        continue
                    if port >= EPHEMERAL_MIN:
                        ignored_eph += 1
                        continue
                    for a in miss:
                        detail.append(
                            f"{st} 站 {side.upper()} :{port} 有监听但分配表未登记 —— "
                            f"是常驻服务就登记到 inventory/ports.yaml "
                            f"(我方 = managed, 他方 = third_party/unmanaged)"
                            f"{_range_miss(port, side, st, a, owners[side].get((a, port)))}")
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

    # (h) 插件/技能三站同构 (P1-5)
    #     站上 plugin-probe 汇报 `id=value` → 与 inventory/plugins.yaml 的 expect 逐项比对。
    #     known_drift 命中降 WARN, 但**只有"恰好多出已登记的那些"**才降级 —— 少了元素、
    #     或多了未登记的东西, 一律 FAIL (与 models.yaml 的 known_broken_conf 同一精神:
    #     已登记的可见不阻断, 但新差异不许被登记这件事糊过去)。
    try:
        pdoc = _plugins_doc()
    except Exception as e:
        pdoc = None
        detail.append(f"inventory/plugins.yaml 解析失败, 插件同构对账无法进行 —— "
                      f"{type(e).__name__}: {str(e)[:160]}")
    plugin_checked = 0
    if pdoc is not None:
        pitems = _plugin_items(pdoc)
        drift = {}
        for kd in pdoc.get("known_drift") or []:
            if isinstance(kd, dict) and kd.get("id") in pitems:
                drift[(str(kd.get("station")), str(kd.get("id")))] = \
                    sorted(str(x) for x in (kd.get("extra") or []))

        for st in reach:
            facts = {}
            for line in (live[st].get("plug") or "").splitlines():
                if "=" in line:
                    k, _, v = line.partition("=")
                    facts[k.strip()] = v.strip()
            if not facts:
                warn.append(f"{st} 站 plugin-probe 无输出 —— 站上未部署 "
                            f"ops/station-bin/plugin-probe (部署后重跑); 本子项对该站跳过")
                continue
            for iid, it in sorted(pitems.items()):
                if st not in _plugin_scope(it):
                    continue
                plugin_checked += 1
                got = facts.get(iid)
                if got is None:
                    detail.append(f"{st} 站 plugin-probe 未汇报 {iid} —— 站上脚本比基线旧, "
                                  f"需重新部署 ops/station-bin/plugin-probe")
                    continue
                diff = _plugin_diff(it, got)
                if diff is None:
                    continue
                reg = drift.get((st, iid))
                if diff[0] == "extra" and reg is not None and sorted(diff[1]) == reg:
                    warn.append(f"{st} 站 {iid} 多出已登记项 {diff[1]} "
                                f"(inventory/plugins.yaml 的 known_drift, 不阻断)")
                else:
                    detail.append(f"{st} 站 {iid} ({it.get('purpose', '?')}) "
                                  f"实得 {got!r} · 基线 {it.get('expect')!r} · 差异 {diff[1]}")

    # (h) LAN 地址对账 (ADR-0006 v1.1 · D6, 2026-09-29) —— 两个面：
    #     ① master 侧**名字绑定**（`ssh -G <别名>` == net.yaml 的 ip；D1 的资产，纯本地展开）；
    #     ② ★ **站上实况**（站上 `ip -4 -o addr` 的 LAN 地址 == net.yaml 的 ip；D6 新增）。
    #   为什么加②: ①的射程靠"别名"，`host: null` 的 C 站**整站被跳过** —— 2026-09-29 C 由
    #     .37 漂到 .8 时，6 项断言只报"可达 2/3 站"、**不给根因**（正是 D4 要消灭的谜题）。
    #   代价: ②搭在同一次合并 ssh 上（零新增连接）；**只有某站直连采集失败**时才多一次
    #     `邻站 → USB4` 的中转 ssh —— 而那种情况本来就已经在报红灯。
    try:
        net_doc = _net_doc() or {}
        lan_doc, segs = net_doc.get("lan") or {}, net_doc.get("segments") or []
    except Exception as e:
        lan_doc, segs = {}, []
        warn.append(f"net.yaml 解析失败, LAN 地址对账跳过 —— {type(e).__name__}: {str(e)[:120]}")
    seg_nets = []
    for sg in segs:
        try:
            seg_nets.append(ipaddress.ip_network(str(sg.get("cidr")), strict=False))
        except Exception:
            warn.append(f"net.yaml §segments 的 cidr 不可解析, 已忽略: {sg.get('cidr')!r}")
    seen_lan = {}
    for ent in (lan_doc.get("stations") or []):
        if not isinstance(ent, dict) or not ent.get("station"):
            continue
        st = ent["station"]
        rows, src = _parse_lanip((live.get(st) or {}).get("lanip")), "直连"
        if not rows:                                    # 直连采集不到 ⇒ 走 USB4 降级通道
            rows, err = _lanip_via_usb4(st, segs, live, cluster.ssh_run)
            src = "USB4 降级通道"
            if err:
                seen_lan[st] = {"error": err}
                continue
            info.append(f"{st} 站直连采集不到（LAN 不通?）, 已**经 USB4 降级通道**取回其真实地址")
        got, perr = pick_lan_addr(rows, ent.get("iface"), seg_nets)
        seen_lan[st] = got if got else {"error": f"{src}: {perr}"}
    # 主控自身：探针 = 真值里**第一个站的 ip**（UDP-connect 只做路由选择, 不发包）
    probe = next((e.get("ip") for e in (lan_doc.get("stations") or [])
                  if isinstance(e, dict) and e.get("ip")), None)
    seen_master = {"ip": _local_lan_ip(probe)} if probe else \
        {"error": "net.yaml §lan.stations 里没有可用的 ip ⇒ 无法判断本机走哪条路"}
    if probe and not seen_master.get("ip"):
        seen_master = {"error": f"无法确定本机通往 {probe} 的源地址（socket 失败）"}
    d_lan, w_lan, i_lan = validate_lan_addr(lan_doc, seen_lan, seen_master)
    detail += d_lan
    warn += w_lan
    info += i_lan

    # (h) 长龄 orphan (O-58, 2026-09-25) —— 站上 ad-hoc 探针/派发留下的僵尸 / 长龄进程。
    #   判据: comm ∈ {opencode, claude, timeout, defunct} 且 etimes ≥ 阈值。
    #   ⚠ **刻意只 WARN、不 FAIL**: 该阈值**判不出"合法的长 run"**(我们自己的长卡可以跑 >6h)
    #     ⇒ 需要人判。本条的价值是**把信号从"偶然人肉 ps"变成"每次全量门禁都报"**，
    #     不是自动清理(清孤儿是不可逆动作, 见 O-58 的裁定记录)。
    #   ⚠ 阈值可由 `RPC_ORPHAN_SEC` 覆盖 —— **为了能先验红**: 6h 的长龄进程无法现场造出来,
    #     而新判据必须双向自证(否则无从区分"判据对"与"判据恒假")。默认仍是 6h。
    # ★ O-70 (2026-09-25) **射程写准**: 本条**只守本站 runtime 白名单那几类**, 不是"站上有无异常进程"。
    #   依据(实测): O-72 那条真孤儿是 `bash` + `sleep`(存活 28.6h), **完全不在白名单** ⇒ 漏报。
    #   ⇒ ① 报数/告警文案里**列出白名单**; ② 另设 (i) `[orph2]` = 白名单外的 ppid=1 长龄进程,
    #     **只报数不判定**(见下), 补上"可见化"这一半。
    ORPHAN_WHITELIST = "opencode|claude|timeout|defunct"
    ORPHAN_SEC = int(os.environ.get("RPC_ORPHAN_SEC") or 6 * 3600)
    orphan_checked = 0
    for st in reach:
        stale = []
        for line in (live[st].get("orph") or "").splitlines():
            f = line.split()
            if len(f) < 4:
                continue
            pid, ppid, et, comm = f[0], f[1], f[2], " ".join(f[3:])
            if not et.isdigit():
                continue
            orphan_checked += 1
            et = int(et)
            if et >= ORPHAN_SEC:
                stale.append(f"{comm} (pid {pid}, ppid {ppid}, 已 {et // 3600}h{(et % 3600) // 60}m)")
        if stale:
            warn.append(f"{st} 站发现**长龄 orphan** (⚠ 射程 = 本白名单 `{ORPHAN_WHITELIST}` · ≥{ORPHAN_SEC // 3600}h；"
                        f"见台账 O-58/O-70): {'; '.join(stale)} —— ⚠ 正在跑的**合法**长 run 也会命中，先确认再清")
        else:
            info.append(f"{st} 站无长龄 orphan (白名单 `{ORPHAN_WHITELIST}` · ≥{ORPHAN_SEC // 3600}h)")
    # (i) O-70 第二类: **我们自己的**产物名命中的进程(不限于白名单 comm) —— **只报数, 永不进 warn/FAIL**。
    #   为什么分开: 白名单内那四类是我们的 runtime, 长龄基本=卡死; 而这一类的匹配键是"**我们的脚本名**",
    #     覆盖 `bash`/`sleep`/`find` 这些白名单看不到的形态(O-72 的真孤儿正是 `bash`+`sleep`) ——
    #     按已裁定的口径**只做可见化**(判成 WARN 会淹信号; 判成 FAIL 更糟, 清孤儿**不可逆**)。
    #   第三列是 `args`(完整命令行) ⇒ 直接打印出来, 人一眼能看出是哪条链漏的。
    orph2_checked = 0
    orph2_stale = []
    for st in reach:
        for line in (live[st].get("orph2") or "").splitlines():
            f = line.split()
            if len(f) < 3:
                continue
            pid, et, what = f[0], f[1], " ".join(f[2:])
            if not et.isdigit():
                continue
            orph2_checked += 1
            if int(et) >= ORPHAN_SEC:
                orph2_stale.append(f"{st}:{what[:70]} (pid {pid}, {int(et) // 3600}h)")
    if orph2_stale:
        info.append(f"白名单外但**属于我们**的长龄残留 {len(orph2_stale)} 条 (**只报数不判定**; 见台账 O-70): "
                    f"{'; '.join(orph2_stale[:5])}")

    if unreachable:
        info.insert(0, f"站点不可达 (未计入判定): {', '.join(unreachable)}")
    note = (f"可达 {len(reach)}/3 站 · 对账 cfg{len(WATCHED)}/ROUTE{len(cluster.ROUTE)}"
            f"/RPC{len(cluster.RPC_MODELS)}/conf{sum(len(v) for v in declared_conf.values())}"
            f"/bind{sum(1 for m in (ports_inv or {}).values() if m.get('expect_bind'))}"
            f"/port{checked_ports}(豁免临时段 {ignored_eph})/plugin{plugin_checked}"
            f"/weight{sum(1 for st in reach for _ in (live[st].get('mpath') or '').splitlines())}"
            f"/orph{orphan_checked}"
            f"/orphx{orph2_checked}"
            # ★ O-70 (2026-09-26): 把**第二类的 stale 条数**也放进 note —— 此前 note 只有 `orphx`
            #   （= 探针**见到几行**，与年龄无关），而"有几条超阈值"只在 >0 时才出现在 info 里
            #   ⇒ 采样时无法**直接读**这个数（只能靠"info 里有没有那行"，脆弱）。
            #   ⚠ 加这个数**不改灯的语义**（第二类仍只报告、不进 WARN/FAIL）；它只是让 O-70 的
            #     "先看几轮噪声水平再裁"这一步**有数据可读**。
            f"/orphxstale{len(orph2_stale)}")
    if detail:
        return "FAIL", note, info + detail + [f"(WARN) {w}" for w in warn]
    if warn:
        return "WARN", note, info + warn
    return "PASS", note, []


# ── 断言 A8..A11: 健康引擎 (P2-2) ─────────────────────────────────
# 目的: 把 rpc_check.py 从"提交门禁"扩成"集群健康引擎"—— 学 Ollama Herd 的
# "成体系的自检项 + 红黄绿 + 修复建议"形态 (方案 §A.2.2), 补齐方案 §5.3 P2-2 列的
# 维度里**尚未覆盖**的四块:
#   usb4   链路层: 三段地址/MTU/接口状态/六向直连/主备回程路由   (此前完全没覆盖)
#   gates  内存门禁: load-gate 可用性 + 当前余量 + loadavg       (此前完全没覆盖)
#   engine 引擎态: 就绪 + **残留检测**(内存被占着但没有服务)      (此前只看 conf/ROUTE)
#   models 模型库完整性: 孤儿/断链                                (此前只在 CLI, 未进门禁)
# (端口/凭据/配置一致性/插件同构已由 ports + stations 的 (a)(d)(f)(g)(h) 覆盖)
#
# ssh 往返控制: usb4/gates/engine 三项共用**一次**合并采集(每站), 并按站缓存 ——
# 否则 3 项 × 3 站 = 9 次往返, 门禁会慢到没人愿意跑。缓存只活在本进程内,
# 故 `--only` 单跑某项时同样只需 1 次/站。
INVENTORY_NET = INVENTORY_DIR / "net.yaml"
# 三段全部端点地址: 采集侧盲发 ping, 由门禁侧判定"哪些必须通"
NET_ENDS = ("10.10.10.1", "10.10.10.2", "10.10.11.1",
            "10.10.11.3", "10.10.12.1", "10.10.12.3")
ENGINE_PORTS = ("8080", "8081", "18080", "18081", "50052")


# ★ O-146（2026-10-05）：**8080 的占用者是哪条路径的引擎** —— 取数分类（**只报数、不进判定**）。
# 为什么需要（根因，读码取证）：`backend` 判**装机面**（两条路径的二进制在不在 + 后端类型），
#   `engine` 判**运行面**却只问"在不在服务 / 是不是残留" ⇒ **"运行中的引擎来自哪条路径"
#   落在两个门禁的缝里，两边都不判**（实测：A 站跑 `/opt/llama.cpp/llama-server` 占着 8080，
#   而 `backend` 照样 PASS ⇒ "未迁移"在门禁层不可见）。更深一层：`BACKEND` 只被 `infer-load`
#   消费，systemd 单元走 `llama-serve-instance`、只读 `LLAMA_SERVER_BIN`（缺省 `/opt/...`）。
# ★★ **O-146 乙′（2026-10-05 裁定）：占用者【进判定】** —— 作用域 = `ports.yaml` 里 `purpose` 含
#   "推理引擎" 的端口（**由真值表驱动、不硬编码**；现 = 8080）；`other`（认不出的东西占着）·
#   `unknown`（取不到 ⇒ 判不了）⇒ **WARN**；`{studio,opt-vulkan,opt-variant}` / `none` ⇒ 通过。
#   ★ 为什么**不**做"按站期望"（甲案）：A 站形态随**外部消费者**时变（实测 `gpt-oss-120b`↔
#   `MiniMax-M2.7`、`llama-single`↔`unsloth` 都出现过）⇒ 写死期望必生误报（SRE 共识：**静态阈值
#   是误报头号成因**；`O-143` 的 A 站 RSS 假阳性即先例）。外部依据：NIST SP 800-167 白名单 =
#   **有限已知集**（不声明"谁该在"）；path 类识别「单独用弱」⇒ 故本判据**只判"认不出/取不到"**，
#   **不判"身份是否正确"**。三者对照见 `O-146` 的多维表。
# ⚠ fail-closed：取不到 ⇒ `unknown`（**绝不**把"读不出"当 `none`）；`listening=True` 却说
#   `none`（LISTEN 段与占用者取数矛盾）⇒ 也记 `unknown`。
_OCCUPANT_KINDS = (("opt-vulkan", "/opt/llama.cpp/"),  # /opt/llama.cpp/（Vulkan 分布式路径 · ★ 当前基线）
                   ("opt-variant", "llama.cpp-"),      # /opt/llama.cpp-<变体>/（GLM 等特性分支）
                   ("studio", "unsloth"),              # studio 启动器（cmdline 含 `unsloth studio run`）
                   # ★ 2026-10-21 (ADR-0014 D7): halogen 容器把 8080 发布到宿主 ⇒ 宿主监听者
                   #   是 docker 的 **userland proxy**，不是引擎进程本身（实测 B 站:
                   #   `127.0.0.1:8080 users:(("docker-proxy",pid=…))`，容器内引擎叫 flash_serve）。
                   ("docker-publish", "docker-proxy"))
# ⚠⚠ **顺序承重（2026-10-05 活体检查抓到）**：`/opt/llama.cpp` 是 **symlink → `/opt/llama.cpp-master-<hash>`**
#   ⇒ 若按 `readlink -f` 的 **exe** 分类，**当前基线**会撞上 `llama.cpp-` 而被误标 `opt-variant`。
#   故：① **opt-vulkan 必须排在 opt-variant 之前**；② 分类用的 blob **含 cmdline**（cmdline 保留
#   **未解析**的 `/opt/llama.cpp/llama-server`）⇒ 当前基线稳定落 `opt-vulkan`，真变体（cmdline 里是
#   `/opt/llama.cpp-<名>/…`，**不含** `/opt/llama.cpp/`）才落 `opt-variant`。同理 studio 的监听进程
#   exe 是 **python 启动器**，其身份只在 cmdline ⇒ 必须看 cmdline。


def classify_engine_occupant(path, listening=False, cmdline=""):
    """把"占用 8080 的进程"归成一类（**唯一定义点**，纯函数 ⇒ 可离线单测）。

    ⚠⚠ **必须同时看 `cmdline`**（2026-10-05 活体检查抓到）：studio 的监听进程是**python 启动器**
    （实测 exe = `…/anaconda3/bin/python3.13`），**只看 exe 会把 studio 误报成 `other`** ⇒
    分类基于 `exe + cmdline` 的合并串（cmdline 里才有 `unsloth studio run --model …`）。
    """
    p = str(path or "").strip()
    c = str(cmdline or "").strip()
    if p in ("", "unknown") and not c:
        return "unknown"                 # 取不到 ⇒ 不可判（fail-closed，**绝不**当 none）
    if p == "none" and not c:
        # LISTEN 段说在听、占用者却说 none ⇒ 取数自相矛盾 ⇒ **不可判**（不是"没占用"）
        return "unknown" if listening else "none"
    blob = p + " " + c
    for kind, marker in _OCCUPANT_KINDS:
        if marker in blob:
            return kind
    return "other"


# ★★ O-146 乙′（2026-10-05）：**允许出现的占用者形态**（有限已知集，NIST SP 800-167 白名单同构）。
#   ⚠ 刻意**不**含"哪一站该跑哪个" —— 那正是被否的甲案（期望随外部消费者时变）。
_OCCUPANT_OK = ("studio", "opt-vulkan", "opt-variant", "docker-publish")


def _engine_api_ports():
    """从 `inventory/ports.yaml` 取"**推理引擎 API**"端口（★ 真值表驱动，不硬编码）。

    判据 = 该端口条目的 `purpose` 含「推理引擎」（现 = 8080 与 8731：前者是客户端面，后者是
    halogen 的原生 API 面）。
    读不到/解析失败 ⇒ 退回 `("8080",)`（**fail-safe 到已知端口**，不是"跳过判定"）。
    ★ 2026-10-21（`O-164` 修复）：原实现**未 import yaml** ⇒ `NameError` 被下面
    `except Exception` 吞掉 ⇒ 实际恒返回 `("8080",)`，"真值表驱动"**从未生效**。
    现与文件内其它断言同口径：**函数内** `import yaml`（缺 pyyaml 时降级为 fail-safe）。
    """
    try:
        import yaml                          # 函数内导入 ⇒ 缺 pyyaml 时走 fail-safe, 不整仓崩
        doc = yaml.safe_load(INVENTORY_PORTS.read_text(encoding="utf-8")) or {}
    except Exception:
        return ("8080",)
    out = []

    def _walk(o):
        if isinstance(o, dict):
            if "port" in o and "推理引擎" in str(o.get("purpose", "")):
                out.append(str(o["port"]))
            for _v in o.values():
                _walk(_v)
        elif isinstance(o, list):
            for _v in o:
                _walk(_v)

    _walk(doc)
    return tuple(out) or ("8080",)


# 残留阈值: 进程 RSS 超过它却没有引擎在服务 → 视为残留(占着内存不干活)。
# 取 2G: 正常单机 llama-server 的 RSS 是几十 G 量级, 而 ggml-rpc-server 空转也有 ~0.3G,
# 故 2G 能把"真占住了"和"进程刚起/空跑"分开 (本会话真的踩到过 62.6G 残留污染判定)。
RESIDUAL_RSS_MB = 2048
# O-41② (2026-09-24): **预警带下沿** —— `[1024, RESIDUAL_RSS_MB)` 且无引擎端口 ⇒ 报 WARN（不 FAIL）。
#   为什么需要: 旧实现只有"≥2G = 残留 FAIL"与"否则 = 正常"，**1024~2048M 这一段完全无声**
#   （O-41② 实测: 1.5G 无端口残留被判"正常"）。下沿取 1024 是为了**不误报 ggml-rpc-server 空转(~0.3G)**
#   与"进程刚起"这两种刻意容忍的情形 ⇒ 只覆盖"明显占住了但没在服务"的带。
RESIDUAL_WARN_MB = 1024


def classify_engine_band(has_ports, rss_mb, n_proc=None):
    """`engine` 断言的**唯一定义点**（O-143 乙，2026-10-03）—— 两分支共用同一份口径。

    返回 `(verdict, reason)`；`verdict ∈ {"FAIL","WARN",None}`（`None` = 无告警）；`reason` 是**不带站名**的短句。

    ★ 为什么必须集中: 修 O-143 之前，"进程刚起"这一情形在**无端口**分支被**刻意容忍**
    （见 `RESIDUAL_WARN_MB` 的注释），在**有端口**分支却按**裸 RSS** 判异常
    ⇒ **同一断言的两半对同一情形给出相反判定**。

    ★★ 判据依据的**更正**（2026-10-03 实测，E1）: **RSS 不是"引擎在不在服务"的证据** ——
    A 站在 **13h**、RSS **208M** 下实测推理 **56.6 t/s**、**GTT 68.75 GiB** 驻留
    （Vulkan/UMA 引擎的权重驻留**设备侧**）⇒ **"有端口 + RSS 小"不足以判异常**。
    故**有端口**分支改用**进程数**作判据:
      · `n_proc >= 1` ⇒ **在服务**（RSS / 进程龄 只作**报数**）
      · `n_proc == 0` ⇒ **端口在听但不是我们的引擎** ⇒ 疑似端口被占（WARN）
      · `n_proc` 读不出     ⇒ **退回旧的 RSS 口径**（「判不了 ≠ 通过」，不静默放过）

    ⚠ **射程（诚实登记，见台账 `O-143`）**: `n_proc >= 1` 只证明**站上有 llama 系进程**，
    **不证明 8080 的持有者就是它**（证到那一层须按端口取 pid —— 需 root，本门禁不具）。
    """
    if has_ports:
        if isinstance(n_proc, int):
            if n_proc <= 0:
                return "WARN", "端口在听但站上**无** llama 系进程 ⇒ 疑似端口被占"
            return None, None
        # 进程数读不出 ⇒ 退回旧口径（保守: 仍可能报，但不静默通过）
        if rss_mb < 1024:
            return "WARN", f"有引擎端口在听但 RSS 仅 {rss_mb}M（进程数读不出）⇒ 疑似异常进程/端口被占"
        return None, None
    if rss_mb >= RESIDUAL_RSS_MB:
        return "FAIL", (f"无任何引擎端口在听, 但 llama/rpc 进程仍占 {rss_mb // 1024}G RSS"
                        f" —— 内存被占着没干活, 会污染加载预估 (先 infer-unload / 清残留再加载)")
    if rss_mb >= RESIDUAL_WARN_MB:
        return "WARN", (f"有 llama 系进程占 {rss_mb}M 但无引擎端口在听 —— 疑似残留/启动中 "
                        f"(预警带 ≥{RESIDUAL_WARN_MB}M, FAIL 阈值 {RESIDUAL_RSS_MB}M)")
    return None, None

# ── 站上件"部署一致性"跟踪清单 (2026-09-22 裁定接入 gates) ──────────────────────
# 背景: 这些件是**站上件** —— 部署在 `/usr/local/bin/`, 仓库副本只是"快照"。
#   ⇒ **改仓库副本不生效**, 必须重新部署; 而"站上跑的那份是不是仓库这份"此前**没有任何机器判据**
#     (只靠 `ops/station-bin/README.md` 的**手工 md5 约定**) ⇒ 本清单把那条约定变成可判。
# ⚠ **期望值不在此处写死**: 真值源 = 仓库副本 `ops/station-bin/<name>` 自身(运行期算 md5)
#   ⇒ 不立第二定义点, 也免掉"改了仓库忘改表"这种漂移(与本仓"判据只在一处定义"同一条纪律)。
# 为什么只列这些: 它们是 `ops/station-bin/README.md` 文件清单里声明的站上件。
# ⚠ 为什么敢判 FAIL(而非 WARN): 接入前实测过**误报面** —— 8 个件 × 三站里 7 个本来就逐字节一致,
#   唯一不一致的 `wait-gtt-release` 是**真漂移**(A/B 落后一版且带 BOM), 已单独立项。
# 2026-09-29 补第 9 件 `rpc-serve-instance`(RPC worker 包装器, GLM-5.3-Flash 引擎变体需要)。
# 2026-10-27 补第 10-12 件（P1 review-p1-remediation）:
#   `model-locate.sh` / `conf-lib.sh` / `conf-get` —— #3 模型定位与 #4 conf 读写的共享实现。
# ⚠⚠ 同日本项**顺带抓到一类系统性假红**: `core.autocrlf=true` 使仓库工作树里
#   `infer-load` / `infer-unload` 是 CRLF, 而站上是 LF ⇒ 逐字节比对必然 FAIL(内容其实一致)。
#   判据是对的(CRLF 的 shell 脚本在 Linux 上**真的**语法错误, 2026-09-29 部署时实测 203/EXEC 同类),
#   错的是**仓库工作树**: 已把这 2 件归一为 LF。改这几个件时务必确认行尾是 LF。
STATION_BINS = ("infer-load", "infer-unload", "infer-list", "llama-serve-instance",
                "rpc-serve-instance", "cluster-ttl", "load-mem-gate", "wait-gtt-release",
                "load-gate", "model-locate.sh", "conf-lib.sh", "conf-get")

_HEALTH_CMD = (
    "echo '===ADDR==='; ip -o -4 addr show 2>/dev/null "
    "| awk '$4 ~ /^10\\.10\\./ {print $2, $4}'; "
    "echo '===LINK==='; for i in $(ls /sys/class/net 2>/dev/null | grep '^thunderbolt'); do "
    "echo \"$i $(cat /sys/class/net/$i/mtu 2>/dev/null) $(cat /sys/class/net/$i/operstate 2>/dev/null) $(readlink -f /sys/class/net/$i/device 2>/dev/null)\"; done; "
    "echo '===ROUTE==='; ip route show 2>/dev/null | while read -r dst rest; do "
    "case \"$dst\" in 10.10.*) via=$(echo \"$rest\" | sed -n 's/.*via \\([0-9.]*\\).*/\\1/p'); "
    "met=$(echo \"$rest\" | sed -n 's/.*metric \\([0-9]*\\).*/\\1/p'); "
    "echo \"$dst ${via:-direct} ${met:-0}\";; esac; done; "
    "echo '===PING==='; for t in " + " ".join(NET_ENDS) + "; do "
    "printf '%s ' \"$t\"; ping -c1 -W1 -q \"$t\" >/dev/null 2>&1 && echo OK || echo FAIL; done; "
    # ⚠ 列序: `ps -eo rss,etimes,comm` ⇒ $1=rss(KB) · $2=etimes(秒) · $3+=comm
    #   `etimes_min_s` = **最年轻**那个 llama 系进程的年龄 —— O-143 的"刚起"读数。
    #   ★ 本项**只报数**（判据阈值待读数足够后再定，见 O-126「不许凭空取数」）。
    "echo '===PROC==='; ps -eo rss,etimes,comm 2>/dev/null "
    # ★ flash_serve = halogen 容器的推理进程 (2026-10-21 实测 B 站: host 侧可见, RSS ~77G);
    #   不纳入则"有端口 + 无 llama 系进程"会把它误判成"端口被占" (classify_engine_band)。
    "| grep -E 'llama-server|ggml-rpc-server|llama-cli|flash_serve' | grep -v grep "
    "| awk '{s+=$1; n++; if (n==1 || $2+0<m) m=$2+0} "
    "END {printf \"rss_mb=%d\\n\", s/1024; printf \"etimes_min_s=%d\\n\", m; "
    "printf \"n_proc=%d\\n\", n}'; "
    "echo '===LISTEN==='; ss -ltn 2>/dev/null | awk 'NR>1{print $4}' | sed 's/.*://' "
    "| grep -E '^(" + "|".join(ENGINE_PORTS) + ")$' | sort -u | tr '\\n' ','; echo; "
    # ★ O-146（2026-10-05）：**占用者是谁** —— 见 `classify_engine_occupant` 的注释（只报数）。
    "echo '===OCCUPANT==='; for P in " + " ".join(ENGINE_PORTS) + "; do "
    # ★ 2026-10-21: root 进程 (docker-proxy / systemd 起的引擎) 的 `users:(...)` 对普通用户
    #   **不可见** ⇒ 旧实现恒得 `unknown` (实测 B 站 halogen: sudo 前 unknown / sudo 后 docker-proxy)。
    #   故先 `sudo -n ss`，无免密 sudo 时回退普通 ss (仍可能 unknown —— 判不了 ≠ 通过)。
    "L=$(sudo -n ss -ltnp 2>/dev/null | awk -v s=\":$P\" '$4 ~ s\"$\"{print $NF}' | head -1); "
    "[ -z \"$L\" ] && L=$(ss -ltnp 2>/dev/null | awk -v s=\":$P\" '$4 ~ s\"$\"{print $NF}' | head -1); "
    "if [ -z \"$L\" ]; then printf 'occupant_%s=none\\n' \"$P\"; continue; fi; "
    "PID=$(printf '%s' \"$L\" | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2); "
    "E=$(readlink -f \"/proc/${PID:-0}/exe\" 2>/dev/null); "
    "C=$(tr '\\0' ' ' < \"/proc/${PID:-0}/cmdline\" 2>/dev/null | cut -c1-200); "
    "printf 'occupant_%s=%s\\n' \"$P\" \"${E:-unknown}\"; "
    "printf 'occupantcmd_%s=%s\\n' \"$P\" \"$C\"; done; "
    "echo '===MEM==='; awk '/MemTotal/{printf \"total_mb=%d \", $2/1024} "
    "/MemAvailable/{printf \"avail_mb=%d\", $2/1024}' /proc/meminfo; "
    "printf ' load1=%s' \"$(cut -d' ' -f1 /proc/loadavg)\"; "
    "printf ' loadgate=%s\\n' \"$(command -v load-gate >/dev/null 2>&1 && echo yes || echo no)\"; "
    "echo '===BINMD5==='; for f in " + " ".join(STATION_BINS) + "; do "
    "printf '%s=%s\\n' \"$f\" \"$(md5sum /usr/local/bin/$f 2>/dev/null | cut -d' ' -f1)\"; done; "
    # ★ 2026-10-22 (ADR-0014 #2 甲): 容器镜像 digest 漂移检查取数 —— 仅列**在跑**容器。
    #   输出 `name|Config.Image|RepoDigests`；无 docker/无容器 ⇒ 节为空（不判）。
    "echo '===IMG==='; for c in $(docker ps --format '{{.Names}}' 2>/dev/null); do "
    "i=$(docker inspect --format '{{.Config.Image}}' \"$c\" 2>/dev/null); "
    "d=$(docker inspect --format '{{.RepoDigests}}' \"$i\" 2>/dev/null); "
    "printf '%s|%s|%s\\n' \"$c\" \"$i\" \"$d\"; done"
)

_HEALTH_CACHE = {}


def _health_probe(st: str) -> dict:
    """单站合并采集 (链路/路由/连通/引擎/内存)。返回 {reachable, addr, link, route, ping, ...}。

    解析失败**显式标 reachable=False**, 绝不返回半份数据让下游误判
    (与 P1-4 的"解析失败不能表现成业务全错"同一原则)。
    """
    if st in _HEALTH_CACHE:
        return _HEALTH_CACHE[st]
    d = {"station": st, "reachable": False, "addr": {}, "link": {}, "route": {},
         "ping": {}, "rss_mb": None, "listen": [], "occupant": {}, "occupant_cmd": {},
         "mem": {}, "binmd5": {}, "containers": [], "raw": ""}
    sys.path.insert(0, str(ROOT / "ops"))
    try:
        import cluster
    except Exception as e:
        d["error"] = f"无法导入 cluster.py ({type(e).__name__}) — 该组需 paramiko"
        _HEALTH_CACHE[st] = d
        return d
    ok, out = cluster.ssh_run(st, _HEALTH_CMD, timeout=120)
    d["raw"] = out or ""
    if not ok:
        d["error"] = out
        _HEALTH_CACHE[st] = d
        return d
    d["reachable"] = True
    sec = _parse_health_sections(out)
    for line in sec.get("ADDR", []):
        p = line.split()
        if len(p) >= 2 and "/" in p[1]:
            d["addr"][p[0]] = p[1].split("/")[0]
    for line in sec.get("LINK", []):
        p = line.split()
        if len(p) >= 3:
            d["link"][p[0]] = {"mtu": p[1], "state": p[2], "dev": p[3] if len(p) >= 4 else ""}
    for line in sec.get("ROUTE", []):
        p = line.split()
        if len(p) >= 3:
            # ⚠ 同一目的地的**主备两条**路由必须并存 —— 早版按 dst 存单个 dict,
            # 后一条把前一条覆盖掉了, 于是"主备齐备"这件事根本查不出来
            # (2026-09-15 实测: A 站 10.10.11.0/24 的两条被压成一条, 误报主路由缺失)。
            d["route"].setdefault(p[0], []).append({"via": p[1], "metric": p[2]})
    for line in sec.get("PING", []):
        p = line.split()
        if len(p) >= 2:
            d["ping"][p[0]] = p[1]
    for line in sec.get("PROC", []):
        # rss_mb (合计) + etimes_min_s / n_proc (O-143 的"刚起"读数, 只报数不判 —— 见 _HEALTH_CMD 注)
        for _k in ("rss_mb", "etimes_min_s", "n_proc"):
            if line.startswith(_k + "="):
                try:
                    d[_k] = int(line.split("=", 1)[1])
                except ValueError:
                    pass
                break
    d["listen"] = [x for x in ",".join(sec.get("LISTEN", [])).split(",") if x]
    # ★ O-146：8080 占用者（**只报数**）—— `occupant_<port>=<exe 路径|none|unknown>`
    #   + `occupantcmd_<port>=<cmdline>`（⚠ 必须看 cmdline：studio 的监听进程是 python 启动器）
    for line in sec.get("OCCUPANT", []):
        if "=" in line:
            k, _, v = line.strip().partition("=")
            if k.startswith("occupantcmd_"):
                d["occupant_cmd"][k[len("occupantcmd_"):]] = v.strip()
            elif k.startswith("occupant_"):
                d["occupant"][k[len("occupant_"):]] = v.strip()
    mem_line = " ".join(sec.get("MEM", []))
    for tok in mem_line.split():
        if "=" in tok:
            k, _, v = tok.partition("=")
            d["mem"][k] = v
    # 站上件副本 md5 (name=hash) —— 与本次探测**同一条命令**取回, 零额外连接。
    # 值为空串 = 文件读不到(md5sum 失败) ⇒ 与"缺失"同义, 由判据那边报出来。
    for line in sec.get("BINMD5", []):
        if "=" in line:
            k, _, v = line.strip().partition("=")
            d["binmd5"][k] = v.strip()
    # 在跑容器: name|image|RepoDigests (2026-10-22, ADR-0014 #2 甲)
    for line in sec.get("IMG", []):
        p = line.strip().split("|", 2)
        if len(p) == 3 and p[0]:
            d["containers"].append({"name": p[0], "image": p[1], "digests": p[2]})
    _HEALTH_CACHE[st] = d
    return d


def _parse_health_sections(out):
    sec, cur = {}, None
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("===") and s.endswith("==="):
            cur = s.strip("=")
            sec[cur] = []
        elif cur:
            sec[cur].append(line)
    return {k: [x for x in v if x.strip()] for k, v in sec.items()}


def _net_doc():
    """读 inventory/net.yaml。缺失返回 {}; **解析失败抛异常**。"""
    if not INVENTORY_NET.is_file():
        return {}
    import yaml
    return yaml.safe_load(INVENTORY_NET.read_text(encoding="utf-8")) or {}


# ── 2026-10-10 · `usb4` 判据的**键**：物理端口（`tb_pci`），**不是**接口名 ─────────────
# 为什么：TB/USB4 的 netdev 名由**内核枚举顺序**决定 ⇒ 跨重启会翻。实测 B 站 2026-10-10 11:13 重启后
#   `thunderbolt0/1` **互换**（domain↔对端映射不变 · 地址仍在正确链路 · 8 向连通全绿），而旧判据按名字比对
#   ⇒ 报出 2 条"地址不符" = **标签层假红**（抓不到真故障，每次重启却被点亮；同型先例 2026-09-29 C 站）。
# ⇒ 键取 `tb_pci` = `/sys/class/net/<if>/device` realpath 里的 **PCI 函数**（`0000:XX:00.5|.6`）= **物理端口**：
#   跨重启不变；**换线/换口**才变 —— 那正是**该报红**的情形。真值侧见 `inventory/net.yaml` 头部同名段。
TB_PCI_RE = re.compile(r"/(\d{4}:[0-9a-f]{2}:\d{2}\.[0-7])/domain\d+/")


def tb_pci_of(dev_path):
    """**纯函数**：从 `/sys/class/net/<if>/device` 的 realpath 里取 **PCI 函数**（= 物理端口标识）。

    实测样例（B 站 2026-10-10）：`/sys/devices/pci0000:00/0000:00:08.3/0000:c8:00.5/domain0/0-0/0-2/0-2.0`
    ⇒ `0000:c8:00.5`。**取不到 ⇒ `None`**（判不了 —— 绝不回落成"按接口名比"）。
    """
    m = TB_PCI_RE.search(str(dev_path or ""))
    return m.group(1) if m else None


def usb4_pick_iface(link_map, end):
    """**纯函数**：把 `net.yaml` 的一个端点接到**站上实测**的 thunderbolt 接口上。返回 `(iface|None, reason)`。

    键 = `tb_pci`（物理端口）。**fail-closed 三态，都不是通过**：
      · 登记缺 `tb_pci` ⇒ 键不完整，判不了；· 站上无该 pci ⇒ 端口没枚举 / 换了口；· 命中多个 ⇒ 真值有歧义。
    """
    want = str((end or {}).get("tb_pci") or "").strip()
    if not want:
        return None, "登记缺 `tb_pci`（键不完整 ⇒ **判不了**；见 net.yaml 头部 2026-10-10 段）"
    seen, hits = [], []
    for nm, lk in (link_map or {}).items():
        pci = tb_pci_of((lk or {}).get("dev"))
        seen.append(f"{nm}={pci or '非TB/取不到'}")
        if pci == want:
            hits.append(nm)
    if not hits:
        return None, (f"站上没有 pci={want} 的接口（实测: {', '.join(sorted(seen)) or '无 thunderbolt 接口'}）"
                      f" —— 端口未枚举 / 该段的接线或端口变了")
    if len(hits) > 1:
        return None, f"pci={want} 命中多个接口: {', '.join(sorted(hits))} ⇒ 真值有歧义"
    return hits[0], ""


def check_usb4(ctx):
    """USB4 三角环链路: 地址/MTU/接口状态 + 六向直连 + 主备回程路由 + 跨段生效性。"""
    if not INVENTORY_NET.is_file():
        return "WARN", "inventory/net.yaml 缺失 (链路真值未建)", []
    try:
        doc = _net_doc()
    except Exception as e:
        return "FAIL", f"net.yaml 解析失败: {type(e).__name__}: {str(e)[:180]}", []

    detail, warn, info = [], [], []
    live = {st: _health_probe(st) for st in ("A", "B", "C")}
    reach = [st for st in ("A", "B", "C") if live[st]["reachable"]]
    for st in ("A", "B", "C"):
        if not live[st]["reachable"]:
            detail.append(f"{st} 站不可达/采集失败: {live[st].get('error') or live[st].get('raw', '')[:120]}")

    n_addr = n_ping = n_route = n_keyed = 0
    for seg in doc.get("segments") or []:
        if not isinstance(seg, dict):
            continue
        name, want_mtu = seg.get("name", "?"), str(seg.get("mtu") or "")
        for end in seg.get("ends") or []:
            st = str((end or {}).get("station"))
            ip = str((end or {}).get("ip") or "")
            if not st or not ip:
                detail.append(f"net.yaml 段 {name} 的端点字段不全: {end}")
                continue
            if st not in reach:
                continue
            n_addr += 1
            # ★ 2026-10-10：键从 `iface`(名字，跨重启会翻) 换成 `tb_pci`(物理端口) —— 见本文件同名注释段。
            got_if, why = usb4_pick_iface(live[st]["link"], end)
            if not got_if:
                detail.append(f"{st} 站 {name} 段端点接不上（真值 ip={ip} · "
                              f"键 tb_pci={end.get('tb_pci') or '(缺)'}）—— {why}")
                continue
            n_keyed += 1
            tag = f"pci={end.get('tb_pci')}（今名 {got_if}）"
            got = live[st]["addr"].get(got_if)
            if got != ip:
                detail.append(f"{st} 站 {tag} 地址 = {got or '(无)'}, 真值 {ip} —— **地址挂在物理端口上不符**："
                              f"地址跟错链路(真故障) / 或该段接线换过(旧判据在此按名字比 ⇒ 名字一变就假报)")
            lk = live[st]["link"].get(got_if) or {}
            if want_mtu and lk.get("mtu") != want_mtu:
                detail.append(f"{st} 站 {tag} MTU = {lk.get('mtu')}, 真值 {want_mtu}")
            if lk.get("state") != "up":
                detail.append(f"{st} 站 {tag} 状态 = {lk.get('state')} (应为 up)")

    # 六向直连: 每站 ping 它两个直连对端 (对端地址从线段两端推导)
    for seg in doc.get("segments") or []:
        if not isinstance(seg, dict):
            continue
        ends = [e for e in (seg.get("ends") or []) if isinstance(e, dict)]
        if len(ends) != 2:
            continue
        for i in (0, 1):
            me, peer = ends[i], ends[1 - i]
            st, tip = str(me.get("station")), str(peer.get("ip") or "")
            if st not in reach or not tip:
                continue
            n_ping += 1
            if live[st]["ping"].get(tip) != "OK":
                detail.append(f"{st} → {tip} ({seg.get('name')} 段直连对端) ping 不通 —— "
                              f"链路级问题, 先查 thunderbolt 枚举(见归档 §6.5)")

    # 主备回程路由: 主备**两条都要**(缺主路由实测降级 268×, 缺回程路由 100% 丢包)
    for r in doc.get("routes") or []:
        if not isinstance(r, dict):
            continue
        st, dst = str(r.get("station")), str(r.get("dst") or "")
        if st not in reach or not dst:
            continue
        got = live[st]["route"].get(dst) or []
        have = ", ".join(f"via {g['via']} m{g['metric']}" for g in got) or "无"
        for kind in ("primary", "backup"):
            spec = r.get(kind) or {}
            n_route += 1
            via, met = str(spec.get("via") or ""), str(spec.get("metric") or "")
            match = [g for g in got if g.get("via") == via]
            if not match:
                detail.append(f"{st} 站缺到 {dst} 的**{kind}**路由 (应 via {via} metric {met}); "
                              f"实有: {have} —— 见 inventory/net.yaml 的 routes 段 / 归档 §6.6")
            elif met and all(g.get("metric") != met for g in match):
                # metric 不符按 **FAIL** 判: 主备的 metric 决定优先级, 颠倒后跨段流量会走
                # 备路由(经第三方中转) —— 实测 9.46Gb/s → 35Mb/s (268×), 属功能回退而非风味问题。
                detail.append(f"{st} 站到 {dst} 的 {kind} 路由 (via {via}) metric="
                              f"{match[0].get('metric')}, 真值 {met} —— metric 决定主备优先级, "
                              f"不符会让跨段流量走错路径(实测降级 268×)")
    for st in reach:
        if st in {str(r.get("station")) for r in (doc.get("routes") or [])
                  if isinstance(r, dict)}:
            info.append(f"{st} 站到非直连段的路由: " +
                        "; ".join(f"{k} → " + ", ".join(f"via {g['via']} m{g['metric']}"
                                                        for g in v)
                                  for k, v in sorted(live[st]["route"].items())))

    # 跨段主路由生效性
    for cx in doc.get("cross_checks") or []:
        if not isinstance(cx, dict):
            continue
        st, tip = str(cx.get("from")), str(cx.get("to") or "")
        if st not in reach or not tip:
            continue
        n_ping += 1
        if live[st]["ping"].get(tip) != "OK":
            detail.append(f"{st} → {tip} 不通 ({cx.get('why')}) —— 跨段主路由未生效")

    note = (f"链路: 可达 {len(reach)}/3 站 · 地址 {n_addr} 端 · 连通 {n_ping} 向 · "
            f"路由 {n_route} 条(主备) · 段 {len(doc.get('segments') or [])} · "
            f"按物理端口对上 {n_keyed}/{n_addr}")
    if detail:
        return "FAIL", note, info + detail + [f"(WARN) {w}" for w in warn]
    if warn:
        return "WARN", note, info + warn
    return "PASS", note, info


def check_gates(ctx):
    """内存门禁: load-gate 可用性 + 当前余量 + loadavg。"""
    detail, warn, info = [], [], []
    live = {st: _health_probe(st) for st in ("A", "B", "C")}
    reach = [st for st in ("A", "B", "C") if live[st]["reachable"]]
    for st in ("A", "B", "C"):
        if not live[st]["reachable"]:
            detail.append(f"{st} 站不可达/采集失败: {live[st].get('error')}")

    bin_ok = bin_bad = 0
    for st in reach:
        mem = live[st]["mem"]
        try:
            total, avail = int(mem["total_mb"]), int(mem["avail_mb"])
        except (KeyError, ValueError):
            detail.append(f"{st} 站内存读数异常: {mem}")
            continue
        used = total - avail                      # 与站上 load-gate 同口径(used = total - avail)
        headroom = avail // 1024 - 12             # 12G 安全垫(load-gate 的 saf_mb)
        info.append(f"{st} 站 total {total // 1024}G / used {used // 1024}G / "
                    f"avail {avail // 1024}G → 单模型可加载上限约 {headroom}G")
        try:
            if float(mem.get("load1", 0)) > 8:
                warn.append(f"{st} 站 loadavg1={mem.get('load1')} > 8 —— 与 load-gate 同阈值, "
                            f"此时加载会明显变慢")
        except ValueError:
            pass
        if mem.get("loadgate") != "yes":
            detail.append(f"{st} 站 load-gate 不可用 (command -v 取不到) —— 站上加载门禁失效")
        if headroom <= 0:
            detail.append(f"{st} 站余量 {headroom}G ≤ 0 —— 当前**任何**模型都过不了门禁, "
                          f"需先卸载或清理残留")

        # ── 站上件部署一致性 (2026-09-22 裁定接入) ──────────────────────
        # 判据: `STATION_BINS` 里每个站上件, 三站副本必须**逐字节等于**仓库副本。
        # 为什么判 FAIL 而不是 WARN: 这是"**站上跑的不是我们 review 过的那份**" ——
        #   与本站 `stations` 断言(conf/凭据/端口不符即以站上实况改仓库侧)同一性质, 不是"判不准的噪声"。
        # 快照语义: 期望值取**仓库副本当前内容**(运行期算 md5) ⇒ "改了仓库还没部署"也会被判出来 ——
        #   这正是要的: 该件改仓库**不生效**, 必须走「改仓库 → 核对 → 部署」。
        got = live[st].get("binmd5") or {}
        for name in STATION_BINS:
            src = ROOT / "ops" / "station-bin" / name
            if not src.is_file():
                bin_bad += 1
                detail.append(f"STATION_BINS 里的 {name} 在仓库副本不存在 —— 清单该改(不是站上的问题)")
                continue
            exp = hashlib.md5(src.read_bytes()).hexdigest()
            have = got.get(name, "")
            if not have:
                bin_bad += 1
                detail.append(f"{st} 站 /usr/local/bin/{name} 取不到 md5 —— 站上缺件或读不到(权限)")
            elif have != exp:
                bin_bad += 1
                detail.append(f"{st} 站 /usr/local/bin/{name} 与仓库副本**不一致** "
                              f"(站上 {have[:8]}… / 仓库 {exp[:8]}…) —— 这是**站上件**, "
                              f"改仓库副本不生效: 核对后二选一(部署仓库版 / 回滚站上版)")
            else:
                bin_ok += 1

    note = (f"内存门禁: 可达 {len(reach)}/3 站 · "
            f"最小余量 {min([int(live[s]['mem'].get('avail_mb', 0)) // 1024 - 12 for s in reach] or [0])}G · "
            f"站上件一致 {bin_ok}/{bin_ok + bin_bad}")
    if detail:
        return "FAIL", note, info + detail + [f"(WARN) {w}" for w in warn]
    if warn:
        return "WARN", note, info + warn
    return "PASS", note, info


def check_engine(ctx):
    """引擎态: 就绪 + **残留检测**(内存被占着但没有服务)。

    全站停机**不是失败** —— 本项目是"零自加载"方针, 引擎按需启停。
    真正要抓的是"占着内存却没有服务": 本会话实测踩到过一次 A 站 62.6G 的测试残留,
    它污染了后续所有内存判定 (预估被误报 NO_FIT)。
    """
    detail, warn, info = [], [], []
    live = {st: _health_probe(st) for st in ("A", "B", "C")}
    reach = [st for st in ("A", "B", "C") if live[st]["reachable"]]
    running = 0
    for st in ("A", "B", "C"):
        if not live[st]["reachable"]:
            detail.append(f"{st} 站不可达/采集失败: {live[st].get('error')}")
    for st in reach:
        rss = live[st]["rss_mb"] or 0
        ports = live[st]["listen"]
        n_proc = live[st].get("n_proc")
        age = live[st].get("etimes_min_s")
        # ★★ O-143 乙（2026-10-03）：**判定集中到 `classify_engine_band`（唯一定义点）** ——
        #   本循环只负责**取数 + 呈现**：`info`/`note` 是报数，`detail`/`warn` 才来自判定。
        band, why = classify_engine_band(bool(ports), rss, n_proc)
        if ports:
            running += 1
            # ★ O-146（2026-10-05）：**占用者是哪条路径的引擎** —— 只报数（`classify_engine_occupant`
            #   是唯一定义点；**不参与 `classify_engine_band` 的判定**）。取不到 ⇒ `unknown`。
            _occ = live[st].get("occupant") or {}
            _ocmd = live[st].get("occupant_cmd") or {}
            _occ_txt = " ".join(
                f"{_p}:{classify_engine_occupant(_occ.get(_p, 'unknown'), listening=True, cmdline=_ocmd.get(_p, ''))}"
                for _p in ports)
            info.append(f"{st} 站引擎在服务: 端口 {','.join(ports)} · 进程 RSS {rss // 1024}G"
                        + (f" · 进程数 {n_proc}" if isinstance(n_proc, int) else "")
                        + (f" · 最短进程龄 {age}s"
                           if isinstance(age, int) and isinstance(n_proc, int) and n_proc > 0 else "")
                        + (f" · 占用者 {_occ_txt}" if _occ_txt else ""))
            # ★★ O-146 乙′（2026-10-05 裁定）：**占用者进判定** —— 作用域 = `ports.yaml` 驱动的引擎 API 端口。
            for _p in ports:
                if _p not in _engine_api_ports():
                    continue
                _k = classify_engine_occupant(_occ.get(_p, "unknown"), listening=True,
                                              cmdline=_ocmd.get(_p, ""))
                if _k in ("other", "unknown"):
                    _why = "认不出的形态" if _k == "other" else "取不到（判不了 ≠ 通过）"
                    warn.append(f"{st} 站引擎端口 {_p} 占用者**未登记/不可判**（{_k} = {_why}）"
                                f" —— 允许形态 {','.join(_OCCUPANT_OK)}；见 O-146")
        else:
            info.append(f"{st} 站引擎未运行 (RSS {rss}M) —— 零自加载方针下属正常")
        if band == "FAIL":
            detail.append(f"{st} 站**残留**: {why}")
        elif band == "WARN":
            warn.append(f"{st} 站{why}")

    # ★ 2026-10-22 (ADR-0014 #2 甲): 容器镜像 **digest 漂移** —— 只判**在跑**的已登记容器。
    #   pin 的真值 = `CONTAINER_MODELS[alias].image` 里的 `@sha256:…`；tag 可重推，digest 才是制品身份。
    #   未运行 ⇒ 不判（零自加载方针：容器按需启停）。取不到 digest ⇒ 报"取不到"，不静默通过。
    try:
        sys.path.insert(0, str(ROOT / "ops"))
        from cluster_const import CONTAINER_MODELS as _CM
    except Exception:
        _CM = {}
    _pins = {s["name"]: s["image"].split("@", 1)[1]
             for s in _CM.values() if "@sha256:" in s.get("image", "")}
    for st in reach:
        for c in live[st].get("containers") or []:
            pin = _pins.get(c["name"])
            if not pin:
                continue
            if pin not in (c.get("digests") or ""):
                detail.append(f"{st} 站容器 {c['name']} 镜像 digest 与 pin 不符: "
                              f"期望 {pin} / 实际 {c.get('digests') or '取不到'}")

    _ages = [live[s].get("etimes_min_s") for s in reach
             if isinstance(live[s].get("etimes_min_s"), int)
             and (live[s].get("n_proc") or 0) > 0]   # ⚠ n_proc=0 的站不参与（否则 0 会污染 min）
    note = (f"引擎: 可达 {len(reach)}/3 站 · 在服务 {running} 站 · "
            f"总占用 {sum((live[s]['rss_mb'] or 0) for s in reach) // 1024}G"
            # ★ O-143 第一步：**只报数** —— 三站里最年轻的 llama 系进程年龄（判据判不了"刚起"时至少看得见）
            + (f" · 最短进程龄 {min(_ages)}s" if _ages else ""))
    if detail:
        return "FAIL", note, info + detail + [f"(WARN) {w}" for w in warn]
    if warn:
        return "WARN", note, info + warn
    return "PASS", note, info


# ── 引擎后端 + 回滚基线 (2026-09-17 新增) ───────────────────────────
# 为什么必须有这条: 原 14 项里**没有任何一项判定"HIP 还是 Vulkan"** —— `engine` 只查进程
#   残留/内存, `stations` 只对账 conf/端口/凭据/插件。后果**已经发生过**: 台账 §1 的
#   "对本集群影响"曾整片按"本集群 = Vulkan / 无 ROCm"写错, 而门禁 13 绿照过
#   (2026-09-17 订正, 见 TRACKER §2.6)。
# 判据(全部可机械判定, 不需要人读; 且都落到**二进制**而非配置文本):
#   (a) 三站 studio 自带引擎在位, 且 ldd 含 libggml-hip         <- 默认单站加载路径的后端
#   (b) 三站 /opt 的 llama-server 与 ggml-rpc-server 均含 libggml-vulkan <- 分布式路径后端
#   (c) 三站 studio 自带 ROCm 运行时版本串一致                  <- 防 studio 静默换 SDK 致三站分叉
#   (d) 三站回滚基线 /opt/llama.cpp-9859 在位                   <- UPGRADE_SOP §6 要求(实测 C 站曾缺失)
_BACKEND_CMD = (
    "echo '===STUDIO==='; "
    "B=\"$HOME/.unsloth/llama.cpp/build/bin/llama-server\"; "
    "if [ -x \"$B\" ]; then "
    "echo 'studio_exe=yes'; "
    "printf 'studio_ggml=%s\\n' \"$(ldd \"$B\" 2>/dev/null | grep -oE 'libggml-(hip|vulkan|cpu)[.]so' | sort -u | tr '\\n' ',')\"; "
    "printf 'studio_rocm=%s\\n' \"$(ls -1 \"$HOME/.unsloth/llama.cpp/build/bin\" 2>/dev/null | grep -oE 'libamdhip64[.]so[.][0-9][0-9.]*' | sort -uV | tail -1)\"; "
    "else echo 'studio_exe=no'; fi; "
    "echo '===OPT==='; "
    "printf 'opt_link=%s\\n' \"$(basename \"$(readlink -f /opt/llama.cpp 2>/dev/null)\")\"; "
    "for n in llama-server ggml-rpc-server; do "
    "P=\"/opt/llama.cpp/$n\"; "
    "if [ -x \"$P\" ]; then "
    "printf 'opt_%s=%s\\n' \"$n\" \"$(ldd \"$P\" 2>/dev/null | grep -oE 'libggml-(hip|vulkan)[.]so' | sort -u | tr '\\n' ',')\"; "
    "else printf 'opt_%s=missing\\n' \"$n\"; fi; "
    "done; "
    "echo '===ROLLBACK==='; "
    "printf 'rollback=%s\\n' \"$(ls -d /opt/llama.cpp-9859 2>/dev/null || echo missing)\"; "
    # ── (e)-(h) 2026-09-23 增: studio 套件的"防线/修复/同版/复原路径" ──────────
    # 为什么加: 2026-09-22 的 A 站翻转事故里, **引擎后端被 update 静默翻转**这件事
    #   是靠人工发现的, 而门禁当时只判"后端类型"(即 (a)) —— 它连"我们事先下的
    #   pin 是否真的生效"都不判。本轮把这四类事实变成取数, 判据见 check_backend。
    "echo '===SUITE==='; "
    "printf 'pin_file=%s\\n' \"$(grep -E '^UNSLOTH_LLAMA_CPP_BACKEND=' /etc/environment 2>/dev/null | tail -1 | cut -d= -f2-)\"; "
    "printf 'pin_seen=%s\\n' \"$(printenv UNSLOTH_LLAMA_CPP_BACKEND 2>/dev/null)\"; "
    "S=\"$HOME/.unsloth/studio/unsloth_studio/lib/python3.13/site-packages\"; "
    "printf 'studio_ver=%s\\n' \"$(ls -d \"$S\"/unsloth-[0-9]*.dist-info 2>/dev/null | sed -E 's|.*/unsloth-(.+)[.]dist-info|\\1|' | sort -V | tail -1)\"; "
    "printf 'events_files=%s\\n' \"$(grep -rl 'X-Unsloth-Events' \"$S/studio\" 2>/dev/null | wc -l)\"; "
    "printf 'engine_md5=%s\\n' \"$(md5sum \"$HOME/.unsloth/llama.cpp/build/bin/llama-server\" 2>/dev/null | cut -d' ' -f1)\"; "
    "printf 'engine_bak=%s\\n' \"$(ls -d \"$HOME/.unsloth/llama.cpp.\"* 2>/dev/null | xargs -r -n1 basename 2>/dev/null | tr '\\n' ',')\""
)
_EXPECT_STUDIO_BACKEND = "libggml-hip.so"      # 默认单站加载 = HIP/ROCm
_EXPECT_LLAMA_BACKEND = "rocm"                 # /etc/environment 里 pin 的期望值 (2026-09-23 增)
_EXPECT_DIST_BACKEND = "libggml-vulkan.so"     # 分布式 / RPC = Vulkan


def check_backend(ctx):
    """引擎后端(默认单站=HIP / 分布式=Vulkan) + 三站同构 + 回滚基线在位。"""
    sys.path.insert(0, str(ROOT / "ops"))
    try:
        import cluster
    except Exception as e:
        return ("WARN", f"无法导入 cluster.py ({type(e).__name__}) — 该项需 paramiko; "
                        f"请用装有 paramiko 的 Python 运行", [])

    detail, warn, info = [], [], []
    per = {}
    for st in ("A", "B", "C"):
        ok, out = cluster.ssh_run(st, _BACKEND_CMD, timeout=60)
        if not ok:
            detail.append(f"{st} 站不可达/采集失败: {out}")
            continue
        d = {}
        for line in (out or "").splitlines():
            if "=" in line and not line.startswith("==="):
                k, _, v = line.partition("=")
                d[k.strip()] = v.strip()
        # 采集成功但关键字段全缺 = 解析失败, 不能当"没问题"
        if not d.get("studio_exe") and not d.get("opt_link"):
            detail.append(f"{st} 站采集输出无法解析 (不做判定): {(out or '')[:120]!r}")
            continue
        per[st] = d

    rocm = {}
    for st, d in per.items():
        s_ggml = d.get("studio_ggml", "")
        if d.get("studio_exe") != "yes":
            detail.append(f"{st} 站 **默认单站引擎缺失**: ~/.unsloth/llama.cpp/build/bin/llama-server "
                          f"不可执行 —— `infer-load`(缺省 backend=unsloth) 会直接加载失败")
        elif _EXPECT_STUDIO_BACKEND not in s_ggml:
            detail.append(f"{st} 站 默认单站引擎**后端不是 HIP**: ldd=[{s_ggml}] "
                          f"(期望含 {_EXPECT_STUDIO_BACKEND}) —— 单站路径实际后端已变, "
                          f"台账 §2.6 的后端矩阵必须同步")
        else:
            info.append(f"{st} 站 默认单站 = HIP ✓ ({s_ggml.strip(',')})")
        rocm[st] = d.get("studio_rocm", "")
        for n in ("llama-server", "ggml-rpc-server"):
            v = d.get(f"opt_{n}", "")
            if v in ("", "missing"):
                detail.append(f"{st} 站 /opt/llama.cpp/{n} 不可执行 —— 分布式路径缺件")
            elif _EXPECT_DIST_BACKEND not in v:
                detail.append(f"{st} 站 /opt/llama.cpp/{n} **后端不是 Vulkan**: ldd=[{v}] "
                              f"(期望含 {_EXPECT_DIST_BACKEND})")
        rb = d.get("rollback", "")
        if not rb or rb == "missing":
            detail.append(f"{st} 站 **回滚基线缺失** /opt/llama.cpp-9859 —— UPGRADE_SOP §6 要求"
                          f"保留 `<现役>` + `9859` 两个版本目录以支持分钟级回滚")
        else:
            info.append(f"{st} 站 回滚基线在位 ({rb})")

    # (c) 三站 studio ROCm 运行时一致 —— 取不到时**不判**(取不到 ≠ 不存在), 显式告警
    vals = sorted({v for v in rocm.values() if v})
    if len(vals) > 1:
        detail.append("三站 studio 自带 ROCm 运行时**不一致**: "
                      + " / ".join(f"{s}={rocm[s]}" for s in sorted(rocm))
                      + " —— 三站可能跑在**不同 HIP 版本**上 (studio 静默换 SDK)")
    elif len(vals) == 1:
        info.append(f"三站 studio ROCm 运行时一致 ({vals[0]})")
    else:
        warn.append("三站均未取到 studio 自带 ROCm 版本串 —— 不做一致性判定 (取不到 ≠ 不存在)")

    # ── (e) pin 在位且**本会话可见** (2026-09-23 增) ────────────────────
    # 判据取「printenv 读得到」而不是「文件里有行」：门禁自身的采集与 `studio update` 是
    # **同一类会话**(非交互 ssh)，故读得到 = 安装器也能读到；只写文件 ≠ 生效
    # (`~/.bashrc` 有 interactive 守卫、`~/.profile` 只被登录 shell 读 —— 见决策简报 §8.2)。
    pins = {s: d.get("pin_seen", "") for s, d in per.items()}
    pinf = {s: d.get("pin_file", "") for s, d in per.items()}
    bad_pin = sorted(s for s, v in pins.items() if v != _EXPECT_LLAMA_BACKEND)
    if bad_pin:
        shown = " / ".join(s + "=会话「" + (pins.get(s) or "(空)") + "」文件「" + (pinf.get(s) or "(无)") + "」"
                           for s in bad_pin)
        detail.append("**" + " / ".join(bad_pin) + " 站 pin 未生效** (非交互 ssh 会话读不到 "
                      "`UNSLOTH_LLAMA_CPP_BACKEND`)： " + shown
                      + " —— 期望「" + _EXPECT_LLAMA_BACKEND + "」。这是「引擎后端被 update 静默翻转」的"
                        "**唯一防线** (显式请求 = mandatory；marker 里的历史选择只是 advisory，探测不认即丢)；"
                        "落点应为 /etc/environment (经 pam_env 对非交互命令亦生效)，见决策简报 §8.2")
    else:
        info.append("pin 在位且会话可见 ✓ (" + _EXPECT_LLAMA_BACKEND + ")")

    # ── (f) X-Unsloth-Events 修复在位 (2026-09-23 增) ──────────────────
    # 缺 = 网关注入无 `choices` 的控制帧 ⇒ 本地 provider 的 compaction 必然失败 (上游 #10362；本仓 O-23)
    noev = sorted(s for s, d in per.items() if (d.get("events_files") or "0") == "0")
    if noev:
        detail.append("**" + " / ".join(noev) + " 站不含 `X-Unsloth-Events` 修复** —— 网关会注入无 `choices` "
                      "的控制帧 ⇒ 本地 provider 的 compaction 必然失败 (上游 unsloth#10362；本仓 O-23)。"
                      "修法 = 升级 studio，见决策简报 §三")
    else:
        info.append("`X-Unsloth-Events` 修复三站在位 ✓")

    # ── (g) studio 版本三站一致性 (不一致 = WARN：滚动升级中间态可接受，但必须可见) ──
    vers = sorted({d.get("studio_ver") for d in per.values() if d.get("studio_ver")})
    if len(vers) > 1:
        warn.append("三站 studio 版本**不一致**：" + " / ".join(
            s + "=" + (per[s].get("studio_ver") or "?") for s in sorted(per))
            + " —— 本仓既定形态是「三站同升」；滚动升级中间态可接受，但口径不一致必须可见")
    elif len(vers) == 1:
        info.append("三站 studio 版本一致 ✓ (" + vers[0] + ")")

    # ── (h) 引擎逐字节同版 ⇒ 站间 tar 复原路径可用 (不同版 = WARN，非 FAIL：各站仍可各自下载) ──
    md5s = sorted({d.get("engine_md5") for d in per.values() if d.get("engine_md5")})
    if len(md5s) > 1:
        warn.append("三站引擎**构建不同版** (md5 不一致)：" + " / ".join(
            s + "=" + (per[s].get("engine_md5") or "?")[:12] for s in sorted(per))
            + " —— 「从同版站 tar 复原」这条分钟级回滚路径不可用 (实测 1.9 G / 18 s)，预案须按逐站写")
    elif len(md5s) == 1:
        info.append("三站引擎逐字节同版 ✓ ⇒ 站间 tar 可复原 (md5 " + md5s[0][:12] + "…)")
    baks = {s: (d.get("engine_bak") or "").strip(",") for s, d in per.items()}
    info.append("引擎面备份目录 (" + "~/.unsloth/llama.cpp.*" + ")： " + " / ".join(
        s + "=" + (baks.get(s) or "(无 — 引擎若被替换，只能靠站间 tar 或重下)") for s in sorted(baks)))

    if not per:
        return "FAIL", "后端: 三站均采集失败", detail
    tip = vals[0] if len(vals) == 1 else " / ".join(f"{s}:{rocm.get(s) or '?'}" for s in sorted(rocm))
    note = f"后端: 可达 {len(per)}/3 站 · 单站=HIP / 分布式=Vulkan · ROCm {tip}"
    # 摘要行必须带上「防线 / 修复 / 同版」三件事 —— info 明细只在 FAIL/WARN 时渲染 (见 main),
    # PASS 时不可见；而这三件事恰是"没红也想知道"的 (如"pin 还在不在位")。
    note += (" · pin " + ("✓" if not bad_pin else "✗")
             + " · studio " + (vers[0] if len(vers) == 1 else ("/".join(vers) or "?"))
             + " · 引擎 " + ("同版" if len(md5s) == 1 else (str(len(md5s)) + " 版不同"))
             + " · 修复 " + ("✗" if noev else "✓"))
    if detail:
        return "FAIL", note, info + detail + [f"(WARN) {w}" for w in warn]
    if warn:
        return "WARN", note, info + warn
    return "PASS", note, info


def check_models(ctx):
    """模型库完整性: 孤儿(物理库有/聚合视图无) + 断链(软链目标不存在)。"""
    sys.path.insert(0, str(ROOT / "ops"))
    try:
        import cluster
    except Exception as e:
        return ("WARN", f"无法导入 cluster.py ({type(e).__name__}) — 该项需 paramiko", [])

    detail, info = [], []
    reach = 0
    tot_o = tot_b = 0
    for st in ("A", "B", "C"):
        m = cluster._scan_models(st)
        if not m:
            detail.append(f"{st} 站模型库扫描失败 (站不可达?)")
            continue
        reach += 1
        orp, brk = m["orphans"], m["broken"]
        tot_o += len(orp)
        tot_b += len(brk)
        info.append(f"{st} 站: 物理库 {len(m['phy'])} / 聚合视图 {len(m['agg'])} / "
                    f"孤儿 {len(orp)} / 断链 {len(brk)}")
        for x in orp:
            detail.append(f"{st} 站孤儿 {x} —— 物理库有、聚合视图无: **权重在但清单看不到、"
                          f"也加载不了**; 修: `cluster.py models link --go`")
        for x in brk:
            detail.append(f"{st} 站断链 {x} —— 聚合视图软链目标不存在; "
                          f"修: `cluster.py models prune --go`")

    note = f"模型库: 可达 {reach}/3 站 · 孤儿 {tot_o} · 断链 {tot_b}"
    if detail:
        return "FAIL", note, info + detail
    return "PASS", note, info


# ── review-p2-big（2026-10-28）：站上 shell 严格模式 + station-bin 布局 ──────────
# 两项都是"契约登记在 inventory/ops.yaml、判据在本函数"的形态：门禁与单测读**同一份**真值，
# 避免第二份清单（本仓头号失败形态）。详见 spec/review-p2-big/DESIGN.md §4.1-§4.3。
SHELL_STRICT_KEY = "shell_strict"
STATION_LAYOUT_KEY = "station_bin_layout"
SHELL_STRICT_PROLOGUE = "set -euo pipefail"
SHELL_STRICT_SCAN_LINES = 20
STATION_PROBE_GLOB = re.compile(r"^ops/station-bin/_[^/]+$")


def _load_ops_inv():
    """读 `inventory/ops.yaml`；不可读/缺 pyyaml 返回 None（调用方判 FAIL，不静默放行）。"""
    try:
        import yaml
    except Exception:                                        # noqa: BLE001
        return None
    try:
        return yaml.safe_load(OPS_INV.read_text(encoding="utf-8")) or {}
    except Exception:                                        # noqa: BLE001
        return None


def _shell_prologue(text):
    """前 N 行里**第一条**非注释、非空行（即 prologue 的判据位）。"""
    for ln in (text or "").splitlines()[:SHELL_STRICT_SCAN_LINES]:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        return s
    return ""


def _lib_set_line(text):
    """库里第一条 `set +-...` 行（含函数内）；空 = 合规。"""
    for ln in (text or "").splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if re.match(r"^set\s+[+-]", s):
            return s
    return ""


def validate_shell_strict(doc, read_text):
    """纯函数：`shell_strict` 段自洽 + 13 执行件 prologue + 2 库无 set + 豁免命中。

    `read_text(rel)` 返回文本或 None（文件不存在）。空 problems = PASS。
    """
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["缺 `shell_strict` 段（或不是映射）"], notes

    execs = doc.get("exec")
    libs = doc.get("libs")
    allow = doc.get("allow") or []
    if not isinstance(execs, list) or not execs:
        bad.append("`shell_strict.exec` 为空或不是列表")
        execs = []
    if not isinstance(libs, list):
        bad.append("`shell_strict.libs` 不是列表")
        libs = []
    if not isinstance(allow, list):
        bad.append("`shell_strict.allow` 不是列表")
        allow = []
    execs = [str(x).strip() for x in execs if str(x).strip()]
    libs = [str(x).strip() for x in libs if str(x).strip()]

    dup = sorted({p for p in execs if execs.count(p) > 1})
    if dup:
        bad.append(f"exec 内重复: {dup}")
    overlap = sorted(set(execs) & set(libs))
    if overlap:
        bad.append(f"同一文件同时列入 exec 与 libs（双列）: {overlap}")

    strict_n = 0
    for rel in execs:
        text = read_text(rel)
        if text is None:
            bad.append(f"执行件不存在: {rel}")
            continue
        pro = _shell_prologue(text)
        if pro != SHELL_STRICT_PROLOGUE:
            bad.append(f"prologue 不是 `{SHELL_STRICT_PROLOGUE}`: {rel}（实测 `{pro}`）")
        else:
            strict_n += 1

    for rel in libs:
        text = read_text(rel)
        if text is None:
            bad.append(f"库不存在: {rel}")
            continue
        line = _lib_set_line(text)
        if line:
            bad.append(f"库不得改调用方 shell 选项: {rel}（实测 `{line}`）")

    for i, a in enumerate(allow):
        if not isinstance(a, dict):
            bad.append(f"allow[{i}] 不是映射")
            continue
        f = str(a.get("file") or "").strip()
        why = str(a.get("why") or "").strip()
        if not f:
            bad.append(f"allow[{i}] 缺 `file`")
            continue
        if not why:
            bad.append(f"allow[{i}] 缺 `why`: {f}")
        if f in execs:
            bad.append(f"豁免与 exec 重叠（同一文件既要求严格又豁免）: {f}")
            continue
        text = read_text(f)
        if text is None:
            bad.append(f"豁免文件不存在: {f}")
            continue
        if _shell_prologue(text) == SHELL_STRICT_PROLOGUE:
            bad.append(f"豁免未命中（文件已是严格模式）⇒ 删除该条: {f}")

    notes.append(f"执行件 {len(execs)}（严格 {strict_n}）· 库 {len(libs)} · 豁免 {len(allow)}")
    return bad, notes


def check_shell_strict(ctx):
    """review-p2-big #5：站上 shell 严格模式（真值 = `inventory/ops.yaml` 的 `shell_strict`）。"""
    doc = _load_ops_inv()
    if doc is None:
        return "FAIL", "inventory/ops.yaml 不可读（本断言的登记依据）", []

    def _read(rel):
        p = ROOT / rel
        return _read_text(p) if p.is_file() else None

    bad, notes = validate_shell_strict(doc.get(SHELL_STRICT_KEY), _read)
    return ("FAIL" if bad else "PASS"), " · ".join(notes), bad


def validate_station_layout(doc, root_files, archive_files, frozen_paths):
    """纯函数：根目录 `_*` ⊆ 白名单、归档非空、无同名复制、登记无根级探针残留。"""
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["缺 `station_bin_layout` 段（或不是映射）"], notes

    probes_dir = str(doc.get("probes_dir") or "").strip()
    keep = doc.get("root_keep")
    if not probes_dir:
        bad.append("缺 `probes_dir`")
    if not isinstance(keep, list) or not keep:
        bad.append("`root_keep` 为空或不是列表")
        keep = []
    keep = {str(x).strip() for x in keep if str(x).strip()}

    if probes_dir and not archive_files:
        bad.append(f"归档目录为空或不存在: {probes_dir}")

    stray = sorted(n for n in root_files if n.startswith("_") and n not in keep)
    if stray:
        bad.append(f"根目录有未登记的一次性件 {len(stray)} 个: {stray[:5]}")

    missing = sorted(k for k in keep if k not in root_files)
    if missing:
        bad.append(f"root_keep 指向已不存在的文件（白名单腐化）: {missing}")

    # 只对 `_*` 件判重名：README 等文档在根/归档各有一份是正常的（内容不同）。
    dup = sorted(n for n in (set(root_files) & set(archive_files)) if n.startswith("_"))
    if dup:
        bad.append(f"根目录与归档目录同名（复制而非移动）: {dup[:5]}")

    # 根级探针残留：白名单里的 9 个在跑件**允许**继续登记（它们不是探针，是夹具/运行时件）
    residue = [p for p in frozen_paths
               if STATION_PROBE_GLOB.match(p) and Path(p).name not in keep]
    if residue:
        bad.append(f"登记表残留根级探针 {len(residue)} 条: {residue[:5]}")

    notes.append(f"根目录 `_*` {sum(1 for n in root_files if n.startswith('_'))} · "
                 f"归档 {len(archive_files)} · 白名单 {len(keep)}")
    return bad, notes


def check_station_layout(ctx):
    """review-p2-big #8A：`station-bin` 根目录只放部署件/运行时件/在跑夹具。

    范围 = **git 跟踪文件**（`_iter_source_files`）—— 工作区里未跟踪的运行时残留
    （如 `_dogfood_*.log`）不属于"仓库布局"，不参与判定。
    """
    doc = _load_ops_inv()
    if doc is None:
        return "FAIL", "inventory/ops.yaml 不可读（本断言的登记依据）", []
    sec = doc.get(STATION_LAYOUT_KEY)
    probes_dir = str((sec or {}).get("probes_dir") or "").strip() if isinstance(sec, dict) else ""
    root_files, archive_files = [], []
    for rel, _p in _iter_source_files():
        if rel.startswith("ops/station-bin/") and rel.count("/") == 2:
            root_files.append(Path(rel).name)
        elif probes_dir and rel.startswith(probes_dir + "/"):
            rest = rel[len(probes_dir) + 1:]
            if "/" not in rest:
                archive_files.append(rest)
    frozen = [str(x) for x in (doc.get("frozen_ops_scripts") or [])]
    bad, notes = validate_station_layout(sec, sorted(root_files), sorted(archive_files), frozen)
    return ("FAIL" if bad else "PASS"), " · ".join(notes), bad


# ── 断言清单 (加校验 = 在此加一条 + 写一个函数) ─────────────────────
# fix 字段 = 该项失败/警告时的**处置建议** (健康引擎要求"红灯必须给出下一步", 而不是
# 只报"哪里不对")。main() 在结论区按严重度打印。


# ⚠ 共享列表 + 模块级副作用 ⇒ 必须**幂等**：以脚本跑时 `__main__` 已填过一遍，
#   若再被 `import rpc_check`（`cluster.py` 惰性 import 等）执行第二遍，
#   无保护会变成 104 条、id 全重复（8B-2 实测：mirror 的 O-50 计数对不上正是这个）。
if not CHECKS:
    CHECKS.extend([
    {"id": "secrets", "title": "明文扫描", "fn": check_secrets, "quick": True,
     "fix": "删除明文密钥, 或加入 SECRET_ALLOW 并写明原因(不允许静默放行); "
            "文档里引用样串/占位串时**掩码为 sk-xxx-****** (2026-09-16 增: 未掩码的样串会命中本判据); "
            "⚠ 报『豁免未命中 N』= 那条白名单**已不再需要** ⇒ **把它从 SECRET_ALLOW 删掉**（D6-P0-2 防腐化）"},
    {"id": "syntax", "title": "语法检查", "fn": check_syntax, "quick": True,
     "fix": "按明细里的行号修语法; 扩展名与内容不符的应解包或改名"},
    {"id": "scripts", "title": "脚本治理", "fn": check_scripts, "quick": True,
     "fix": "管理操作请走统一入口 (ops/cluster.py <sub> / web 卡片), 不要新增一次性脚本; "
            "确需独立脚本则在 inventory/ops.yaml 登记并在提交信息里说明理由 (ADR-0004)"},
    {"id": "shell-strict", "title": "站上 shell 严格模式", "fn": check_shell_strict, "quick": True,
     "fix": "review-p2-big #5：把 prologue 改成 `set -euo pipefail`，并给『业务上容忍失败』的命令补显式守卫"
            "（逻辑或短路 / `if !` / 取值兜底）；被 `source` 的库不得改调用方选项；"
            "确需豁免（如报告型门禁 `load-gate`）⇒ 在 `inventory/ops.yaml` 的 `shell_strict.allow` 登记 why。"
            "⚠ 报『豁免未命中』= 该文件已变严格 ⇒ **删掉那条豁免**（防腐化）"},
    {"id": "station-layout", "title": "station-bin 布局", "fn": check_station_layout, "quick": True,
     "fix": "review-p2-big #8A：`ops/station-bin/` 根目录只放部署件 / 入口运行时件 / 在跑夹具；"
            "一次性 `_*` 探针请 `git mv` 到 `archive/station-bin-probes/`（不改内容），并从 "
            "`inventory/ops.yaml` 的 `frozen_ops_scripts` 删登记；确需在根目录新增 `_*` ⇒ 先改 "
            "`station_bin_layout.root_keep` 并说明理由；⚠ 报『白名单腐化』= 该文件已不存在 ⇒ 删掉白名单项"},
    {"id": "deps", "title": "cluster 模块依赖方向", "fn": check_cluster_deps, "quick": True,
     "fix": "P2-1: ① 新 `ops/cluster_*.py` 模块 ⇒ 必须在 `inventory/ops.yaml` 的 `cluster_layers` 登记层次; "
            "② 模块级 import 成环 ⇒ 拆环，或把其中一条改成**函数内懒加载**（并登记 `cluster_lazy_allow`）; "
            "③ 层序越界（反向/同层）⇒ 调整层次或改依赖方向（只允许依赖**严格下层**）; "
            "④ 反向懒加载未登记 ⇒ 登记原因，或调层; ⚠ 报『未命中登记 N』= 那条登记已可移除（删掉）"},
    {"id": "adr", "title": "ADR 替代方案节", "fn": check_adr, "quick": True,
     "fix": "P2-2: ADR 必须有 `## 考虑的替代方案（Alternatives Considered）` 节"
            "（模板: spec/vulkan-version-control/ADR_TEMPLATE.md），节体内**至少 1 个列表项 或 2 个表格行(表头+数据)**"
            " —— 要写「考虑过/否决了什么」，不是只写标题; **恰 1 个**（改名后别留旧节）; "
            "旧名 `否决/比较对象` / `被否的方案` 一律换规范名; "
            "⚠ 范围只含 adr/ADR-*.md —— DECISIONS.md 是表格载体（列在结构上已保证槽位、值可为 `—`），不在范围"},
    {"id": "model-families", "title": "模型家族表（双向对账）", "fn": check_model_families, "quick": True,
     "fix": "D7-P3-1 前置：`inventory/model-families.yaml` 的成员必须与 `inventory/models.yaml` 的 alias "
            "**双向对上** —— ① 成员不在 `models.yaml` ⇒ **孤儿引用**（删掉或改 alias）; "
            "② `models.yaml` 里的 alias **没被任何族收** ⇒ 按**权重血统**归族"
            "（蒸馏/微调**归基座族**，微调者记 `note`，**不改族**）; ③ 一族缺 `basis` ⇒ 补划分依据。"
            "⚠ 本判据**不判族分得对不对**（那要人读血统），只判「**没有一个 alias 没被归类**」与「引用不悬空」。"
            "⚠⚠ 它也**不提供**「站↔**已加载**模型」—— 那**不是** `models.yaml` 的 `stations`（库中有）"
            "或 `conf`（配过实例）; 见 yaml 的 `linked_state`（**未实测**）"},
    {"id": "ledger-status", "title": "台账状态可机读", "fn": check_ledger_status, "quick": True,
     "fix": "O-93: `spec/d6-agent-standard/OPEN-ISSUES.md` 的**每行**状态格必须**以标记开头**"
            "（`✅`=已闭环 · `◐`=已登记未处置 · `⏳`=待触发或待裁 · `🔵`=部分收口）——**允许加粗包裹**"
            "（如 `**✅ …**`，判据会先剥 `**`/`_`/空白）。"
            "\n\n⚠ **只认格首** ⇒ **引文里的 ✅ 不会被误当状态**（这正是「按整行找 ✅」那种口径会错的地方）。"
             "⚠ 状态格子**不在固定第几格**：本表列数不齐（表头声明 8 列、行有 6/8 格、另有行含裸竖线被拆），"
             "同一列在老行是状态、新行是证据 ⇒ 判据取「**第一个**格首带标记的格」。"
             "\n📊 note 里报出「数据行 N · 状态可机读 M · ✅ 闭环 X · **仍开着 Y**」，明细含**仍开着的 ID 清单** "
             "⇒ 排优先级**不再依赖人读**。"
             "\n⚠⚠ **它不判什么**：「应该闭环多少」**不判** —— 「开着」**不是错误**；也**不判**状态写得对不对"
             "（那仍要人读）。别把本判据读成「台账已被审计」。"
             "\n⚠ 若明细指出某行「状态不可机读」⇒ 给那行补一个格首标记即可（**不要**只改文案）。"},
    {"id": "spec-untested", "title": "规范类文档的未实测登记节", "fn": check_spec_untested, "quick": True,
     "fix": "O-91: **规范类文档**（`spec/d6-agent-standard/U[0-9]-*.md` 与 `D7-PROTOCOL-*.md`）必须带"
            "**非空**的 `## 未实测登记` 节 —— 形状与判据 `adr` 同源（锚精确节名 · **恰 1 个** · "
            "节体 **≥1 列表项 或 ≥2 表格行** · 扫描**只到下一个 H2**，故 `### 子节` 属节体）。"
            "① 缺节 ⇒ FAIL；② 多于 1 个 ⇒ FAIL；③ 只写标题没写内容 ⇒ FAIL；"
            "④ **命中集为 0 ⇒ FAIL**（判据**没有对象** = 退化空判，本仓头号形态）。"
            "\n\n⚠⚠ **它不判什么（别读过头）**：**不判**「正文里有没有无证据断言」—— 那**不可机判**，"
            "**仍然是纪律**。本判据只保证「**那一节在、且非空**」。"
            "\n📊 note 里附一条 **报数（不判）**：E 级内联标注的「带具体取证 / 裸」分布 —— "
            "实测 ADR 侧 **57% 是裸标**，而「裸」**不等于「错」**，且**连计数都口径敏感**"
            "（同一棵树两个正则数出 4 vs 8）⇒ 做成 FAIL 会造假红，假红 → 例外名单 → 判据失效。"
            "\n★★ **O-123（2026-09-30）新增第四件事**：本判据**顺带消费** `inventory/untested-index.yaml` 的分诊"
            "（该索引由此**不再是叶子节点**）—— **报数** state / blocker / needs_decision 分布；"
            "**一条判据**：任一条 `needs_decision: true` ⇒ **WARN**（口径 =「**未裁项不许静默**」）。"
            "⚠ 索引缺失/不可解析/`items` 为 0 ⇒ **WARN（非 FAIL）** —— 索引自身的对账与闭集校验由 `py-tests` 判，"
            "**不在此处重复判**（判据只在一处）。"
            "\n⚠ **逃逸（如实记）**：新规范若取名不带 `U\\d-` 前缀，本判据**看不到它** —— "
            "spec 与 adr 实测**全部无 front-matter**（无 `type:` 可锚）⇒ 靠「命中集在输出里可见」缓解。"},
    {"id": "doclinks", "title": "文档链接可达", "fn": check_doclinks, "quick": True,
     "fix": "资源移动/改名后, 文档里的相对链接要跟着改 (注意别写重前缀: spec/<x>/ 里是 "
            "`../y` 不是 `../spec/y`, 引 docs/ 是 `../../docs/z`); 确有不可修的登记 DOCLINK_ALLOW; "
            "⚠ 报『豁免未命中 N』= 那条例外**已不再需要** ⇒ **把它从 DOCLINK_ALLOW 删掉**（D6-P0-2 防腐化）"},
    {"id": "inventory", "title": "真值登记", "fn": check_inventory, "quick": True,
     "fix": "端口/模型标识有变更时同步 inventory/*.yaml 真值表"},
    {"id": "artifacts", "title": "生成物清单", "fn": check_artifacts, "quick": True,
     "fix": "生成物**禁止手工编辑** —— 改源头 → 重跑 → 跑 --check (D6-P1-1); "
            "清单每条须给 `check`(真实断言 id) 或 `exempt`(豁免理由), 两者都缺 = 静默缺口会 FAIL"},
    {"id": "sensitivity", "title": "内容档位真值表", "fn": check_sensitivity, "quick": True,
     "fix": "O-51: sensitivity.yaml 是「内容→档位」的真值(权威源在自身) —— 断言其自洽: "
            "① path 必须真实存在 ② tier 必须 ∈ 封闭枚举 ③ **同一 path 不得两处不同 tier** "
            "④ default_tier 必须为 local-only (fail-closed)"},
    # O-66 (2026-09-25): 卡面 `input-provenance` 义务的**机判** —— 此前只在文档里（`ops/` 全域零命中）。
    {"id": "input-provenance", "title": "卡面输入来源义务", "fn": check_input_provenance, "quick": True,
     "fix": "O-66: 卡声明 `attach-egress: ok` 且 `sensitivity` ∈ {public, sanitized} 时，它**要带附件出网** ⇒ "
            "按 `CROSS-PROJECT-WORK-STANDARD §4` 必填 `input-provenance`：① 逐项本仓相对路径；"
            "② 每项须在 `inventory/sensitivity.yaml` 有 `tier`；③ 卡档位**不得宽于**该项 tier。"
            "确无本仓输入 ⇒ **显式写 `input-provenance: none`**（不要留空；留空 = 缺字段 ⇒ FAIL）。"
            "⚠ 报『none 可证伪性存疑』= **WARN 不阻断**：声明 none 却在正文提到 tier 严于本卡的已登记路径 —— "
            "『提到』不等于『读到』，机械判不出 ⇒ 请人工核一次：若确实读了，把它列进 `input-provenance` 或降档。"},
    # D7-P1-1 (2026-09-26): U-2 证据强度字典 + 方言映射表 —— 映射表自己的两种病
    #   （**漏项** / **源词表改了而映射表没重抽**）。
    {"id": "dialect", "title": "U-2 方言字典与映射表", "fn": check_dialect, "quick": True,
     "fix": "D7-P1-1: `inventory/dialect.yaml` 是「符号 × 出处 → 含义」的投影（**权威源在别处** ⇒ "
            "已登记进 `inventory/artifacts.yaml`，**禁止手工编辑语义**：改源 → 重抽 → 重跑）。"
            "本项判四件事：① `axis` / `namespaces` 是封闭枚举与白名单，映射行的 `namespace` **必填**"
            "（§11.4 教训①：前缀不靠人自觉写）；② `axis=not-assigned` 必须写 `axis_note`（说明属于什么轴），"
            "`axis_value=undefined` 必须写理由（堵「看着像就填」）；"
            "③ `coverage` 逐族行数与实际**双向**相等（`b1b` 实测漏过一行）；"
            "④ `sources` 的**源切片指纹**不符 ⇒ 红（这就是「源词表变了下游红」）。"
            "⚠ 报「读取失败 ⇒ 不可判」= **要修**，不是通过 —— 判不了不许当通过"},
    # D7-P1-3 (2026-09-26): U-3 依赖边格式 —— 最该被机器盯住的是**最容易缺的那个字段**。
    {"id": "u1-identity", "title": "U-1 产物身份（可复算）", "fn": check_u1_identity, "quick": True,
     "fix": "D7-P1 实现侧（U-1 落地）：`inventory/*.yaml` 里声明了 `u1:` 的，**身份必须可复算**。"
            "① 声明四项 `{namespace, identifier, version, identity}` 必须齐（只写 identity **无法复算**）；"
            "② `identity` 必须 **等于** 按 `(namespace, identifier, version)` 复算的结果 —— "
            f"★ 只判格式是**假绿**（随手编一个合规长度的 hex 就能过）；'身份'可判的含义只有『能从 (ns,id,ver) 复算』；"
            f"③ 声明了身份 ⇒ 文件**前 5 行内必须有** `# {U1_PREFIX}` 头部注释行（D-25：前缀进头部注释、"
            "不进哈希行 —— 进了哈希行整份 `sha256sum -c` 会一行都不被验，一手实测见 U1 spec §1.4）；"
            "④ **一个声明都没有 ⇒ FAIL**（本条会静默退化成空判 = 本仓头号失败形态）。"
            "\n\n算法/截断的**唯一真值**在 `ops/rpc_check.py` 的 `u1_identity()`（门禁与产出方同源）；"
            "取值与理由见 `spec/d6-agent-standard/U1-ARTIFACT-IDENTITY.md`。"
            "⚠ 哈希不可逆 ⇒ 本条只能判『声明可复算』，**不能**判『某个文件内容变了 ⇒ 身份该不该变』（那是 U-4 的事）"},
    {"id": "id-census", "title": "ID 站点计数（口径可复算）", "fn": check_id_census, "quick": True,
     "fix": "O-85: `inventory/id-site-census.yaml` 是**唯一真值**，口径的**唯一实现**在 `ops/id_site_census.py`。"
            "① 数值不符 ⇒ 项目变了（正常）⇒ 跑 `py ops/id_site_census.py --emit` 重出真值，"
            "**并回头复核下游结论**（U4 spec §1 表引用了这些数）；"
            "② **口径漂移（正则 / glob / 排除目录 / 是否含测试）⇒ 比数值漂移严重** —— "
            "口径一变，真值里**所有**数字立刻失去意义 ⇒ 必须重出 + 复核；"
            "③ 项目目录不可达 ⇒ **WARN**（它们在 `F:` / `E:` 等**本机才有**的盘上，换机器就没有）"
            "—— ⚠ 但**绝不静默通过**：报告里显式写 `可达 N/M` 与逐项目 `--`（D-26）。"
            "\n\n★ 这条断言的**存在理由**：U4 §1 表原来那一列「计数」**没有口径** —— "
            "Open_Data 换四种口径实测得 12 / 14 / 117 / 139，而表里写的是 34 ⇒ **数字没有定义**。"
            "⚠ 它只回答『有多少处哈希用法』，**不回答**『哪些是产物 ID』（那是 U-4 的 `affected`，仍未解）。"},
    {"id": "id-storage", "title": "ID 存储面（affected 生产者）", "fn": check_id_storage, "quick": True,
     "fix": "U-4: `inventory/id-storage-census.yaml` 是**唯一真值**，口径的**唯一实现**在 `ops/id_storage_census.py`。"
            "① 数值不符 ⇒ 存储变了（正常）⇒ 跑 `py ops/id_storage_census.py --emit` 重出真值，"
            "**并回头复核 U-4 的 `affected`**；"
            "② ★★ **角色不实 ⇒ FAIL**：声明 `primary_key` 就必须**回库里核过**（duckdb 查 "
            "`duckdb_constraints()` · sqlite 查 `PRAGMA table_info`）—— 声明与实测不一致，说明这张表在**自说自话**；"
            "③ **口径漂移**（形态档 / 取样上限 / role 取值域）⇒ 比数值不符**优先**判红；"
            "④ 存储不可达 ⇒ **WARN 不 FAIL**（库在 `F:`/`E:` 等别的盘）—— 但报 `不可达 N/M`，**绝不静默通过**。"
            "\n\n★ **它是什么**：把 2026-09-26 那次『开库手工数 affected』（duckdb + sqlite）变成**可复算的机制**。"
            "`py ops/id_storage_census.py --invalidate --changed <带 u1: 声明的文件>` 会串起三段："
            "**changed_ids（取声明）→ affected（本普查实测）→ `decide_invalidation()` 的处置**。"
            "⚠ 它只产出**决策**，不执行重算（执行侧仍未实现 —— U4 未实测第 10 条）；"
            "⚠ `affected` 的完整性取决于 `STORES` 清单，而**清单是线索不是事实**（已吃过两次亏）。"},
    {"id": "edges", "title": "U-3 依赖边格式", "fn": check_edges, "quick": True,
     "fix": "D7-P1-3: `inventory/edges.yaml` 的**实例**要满足 `U3-EDGE-FORMAT.md`（形状的单一真值）："
            f"① `src`/`dst` 必须是 **U-1 产物身份**形态 `{U1_PREFIX}:<{U1_TRUNC} 位小写 hex>`"
            "（U-1 与 U-3 咬合：写一条边就得先有一个合规身份）——"
            "★ 判据由 `u1_parse()` 给出，与 U-1 实现**同源**（此前这里另写了一份正则 = 同一事实两个定义点）；"
            "③ `provenance` 必填，形式 `<前缀>:<载荷>`，前缀 ∈ `provenance_prefixes`，"
            "**载荷允许含 `:`**（只按第一个 `:` 切分）；"
            "★ 「缺」= 字段不存在 / 空串 / 仅空白 / `null` / `unknown`·`none`·`n/a`·`null` / 前缀不在封闭集 / 载荷为空"
            " ⇒ **该边无效** ⇒ **FAIL**（⚠ 产出方的处置是 FAIL，**不是「丢掉这条边继续」** —— "
            "依据 D-26「禁止静默 skip」；「丢弃 / 降级」是**消费方**那一侧的 H-3 规则）；"
            "④ `(src,dst,kind)` 不得重复；⑤ **`edges` 为空必须给 `empty_reason`** —— "
            "空 ≠ 没事，门禁会把「0 条」显式报出来"},
    # D7-P1-5 (2026-09-26): U-5 晋升门 schema —— 判的是**schema 自身 + 三处实现的映射**（对象真实存在）。
    {"id": "promotion", "title": "U-5 晋升门 schema", "fn": check_promotion, "quick": True,
     "fix": "D7-P1-5: `inventory/promotion.yaml` 是共享记忆**准入形状**的单一真值。"
            "① `gate.required` / `gate.capacity`（field+max+policy）/ `gate.criteria` / `gate.structure` 四件都要有；"
            "② 判据的 `field`/`ref` 只能引用 `fields` 里的字段，`op`/`policy` 是封闭枚举，`$ref` 类型须与 field 一致；"
            "★ ③ **D-38 要求三种判据并存**（`success_rate` / `recurrence` / `verified`）—— 缺一即『发明第四种』；"
            "★ ④ **映射闭包**：`mapping_closure` 里三处实现的 `uses`/`criteria_used` 必须覆盖 schema 的**全部**"
            "字段与判据 —— **出现孤儿字段/孤儿判据 = 有一处没人用，就是变相发明第四种**；"
            "⑤ `entries` 为空必须给 `empty_reason`；⑥ `unverified` 必须登记本 schema 里**新设**的项"},
    {"id": "facade", "title": "门面符号可达性", "fn": check_facade, "quick": True,
     "fix": "P1-3: `cluster.py` 是统一门面, `cluster_web.py` 以 `import cluster` 复用其符号 —— "
            "缺符号即 FAIL 并点名『哪个符号·被谁引用』; 修法: 在 cluster.py 重导出(或改回引用处)"},
    {"id": "mirror", "title": "事实源↔镜像一致", "fn": check_mirror, "quick": True,
     "fix": "P1-2: ① M-1 手册 §1.3 判官行须与 `JUDGE_TABLE['main']` 的 id/egress/compliance 三项一致; "
            "② M-5/M-6 受理状态机真值(`inventory/inbox.yaml`)须与 inbox/README §3 白名单/状态表一致, "
            "且 `cluster_web.py`/`rpc_check.py` 消费同一真值(不得回归硬编码); "
            "③ #7/#9 真值的 `requires`(必需件)须齐全, 手册 §1.3 状态机段须逐个提到真值状态, "
            "README §5.3『交付态强判据』行须 == 真值 `manifest` 集 —— "
            "**改状态/必需件只改 `inventory/inbox.yaml` 一处**, 文档跟着改; "
            "④ O-50 手册声明的断言计数须 == 真实 `CHECKS`（**加/删断言后同步手册 §2.4 的 "
            "`# N 项断言 (quick Q + 全量 R)`**）; 手册**禁**再写『真实剩余 open = N 项』枚举或写死『门禁 N 绿』; "
            "⚠ M-2 已被 O-50 判为『不再维护第二份枚举』故不并入"},
    {"id": "ports", "title": "端口分配表自洽", "fn": check_ports, "quick": True,
     "fix": "按明细修 inventory/ports.yaml (缺字段/同组重复/跨组重叠/枚举拼错)"},
    {"id": "plugins", "title": "插件同构基线", "fn": check_plugins, "quick": True,
     "fix": "改插件/技能后同步 inventory/plugins.yaml; 无法立即修的真实差异登记 known_drift"},
    {"id": "impact", "title": "影响面反查", "fn": check_impact, "quick": True,
     "fix": "impact.yaml 登记的 consumer 路径不存在 —— 修正路径或删掉该条"},
    {"id": "aliases", "title": "别名解析契约", "fn": check_aliases, "quick": True,
     "fix": "以站上 conf 为准改 cluster.py 的 ROUTE/RPC_MODELS/STATION_ROUTES"},
    {"id": "evidence", "title": "agent 证据链", "fn": check_evidence, "quick": True,
     "fix": "digest/链/锚不符 = 归档证据或链被改动 ⇒ FAIL —— 用 `cluster.py agent verify` 定位到条与件, "
            "再追查改动来源(别急着 `--reanchor`, 那是把信号抹平); 有 run 未入链只是**覆盖缺口** ⇒ WARN, "
            "跑 `cluster.py agent chain` 补录(钩子已自动入链, 出现未入链说明钩子没跑或被 --no-verify 绕过); "
            "「可重放性审计: 新增 N 条」= **增量**可重放性缺口(同属覆盖缺口 ⇒ WARN, 刻意不进 FAIL 集) "
            "⇒ 先看逐条明细, **确认可接受**后跑 `cluster.py agent audit --accept` 推进水印(存量即不再重复报); "
            "若明细里是「已归档但未被任何 subject 覆盖」= 新证据件没进产出方基线 ⇒ 应改 "
            "`ops/station-bin/agent-cli.ps1` 的 `Get-FrameworkSubjects`(清单唯一真值在那里), 而不是接受它; "
            "「judge 校准已过期」= 判据(A/B)或稳定题集改过、校准报告没重跑 ⇒ 跑 "
            "`cluster.py agent audit-judge --save`(需站上在服务跨家族引擎)。这条把"
            "「改判据必须重跑校准」从**空头承诺**变成可判——报告自带 calib 指纹, 比对即可"},
    {"id": "inbox", "title": "受理区状态自洽", "fn": check_inbox, "quick": True,
     "fix": "按明细修: 缺 00_handoff/ = 转运包没冻结; STATE.json 缺失/非法/不在白名单 = 状态没走机读格式; "
            "状态内容不自洽(如 accepted 无受理决定) = 先补 10_admin/受理决定.md 再改状态 "
            "(依据 inbox/README §3 状态机, ADR-0008; 状态只由管理员改, 每次变更追加 40_state/LOG.md); "
            "★ **MANIFEST.sha256 重算不符 = 交付证据束被手改或源被改动**（生成物**禁手改**）⇒ "
            "**别去改清单**，走「改源头 → 重跑 → `cluster.py inbox seal <proj-dir> --go`」；"
            "核对用 `cluster.py inbox seal <proj-dir> --check`（与门禁同一实现）；"
            "报『MANIFEST 未校验 N』= 清单头写的项目根**不在本机**（换 clone/换机），不是篡改"},
    {"id": "ps1-golden", "title": "ps1 离线黄金夹具", "fn": check_ps1_golden, "quick": True,
     "fix": "P3-2: 跑 `powershell -NoProfile -ExecutionPolicy Bypass -File ops/station-bin/_fm_golden_test.ps1` "
            "看明细里的 FAIL 行。⚠ **先判「是回归还是夹具期望值陈旧」**："
            "若代码侧确有语义变更（看 agent-cli.ps1 里的注释/新件/O- 台账）⇒ 改**夹具期望值**并写明理由；"
            "若代码侧无变更 ⇒ **是回归**，改代码。⚠ 出站硬闸的判据本体在夹具里，本断言只负责让它**每次都被跑**"},
    # ── D7-P3-2 (2026-09-26): 编排层的两条判据（防 D7 变瓶颈 / 不新造账本）────────
    {"id": "conclusion-ledger", "title": "账本唯一性（不新造账本）", "fn": check_conclusion_ledger, "quick": True,
     "fix": "D7-P3-2『结论收束记账』：合并稿 §13.3 要求 D7 的结论留痕**复用既有追加式纪律、不新造账本**。"
            "`inventory/conclusion-ledgers.yaml` 是**账本的封闭集**（口径 = 只追加 ∧ 唯一写入者 ∧ 有独立校验）。"
            "① 报『**未登记的账本** <路径>』⇒ 有人在扫描口径内新造了一本 ⇒ **要么登记**，"
            "**要么把 `scan.globs` 口径说清**（口径不先定就量 = 本仓已吃过三次亏）；"
            "② 报『登记了 globs 却一条也没命中』= **登记腐化**（账本被删 / 改名 / glob 写错）；"
            "③ 报『登记的路径不存在』同②（`paths` 那一半）；"
            "④ 报『`not_a_ledger` 为空』= **没写下「什么不算账本」** ⇒ 下一个人会按『看着像』再建一本；"
            "⑤ 报『相撞』= 同一形态既登记为账本、又被声明不是账本（两处口径矛盾）；"
            "⑥ 报『扫描失败 ⇒ 不可判』= **要修**，不是通过。"
            "⚠ **它不判什么**：**不判账本内容**对不对，也**不判**『结论该不该进账本』（后者是纪律）。"
            "⚠ 扫描口径**窄**（只 `inbox/*/40_state/LOG.md`）⇒ **别名账本看不到**，"
            "这点已如实写在 yaml 的 `unverified` 里 —— 别把本项读成『账本已全覆盖』"},
    {"id": "review-catalog", "title": "标准复核目录（免终裁类目）", "fn": check_review_catalog, "quick": True,
     "fix": "D7-P3-2 / D-43：`inventory/review-catalog.yaml` 是**免终裁类目的清单**。"
            "① 准入门槛照抄 ITIL（**同一类被批准两次**）—— 报『`approvals` 未达门槛』或"
            "『`approval_anchors` 条数 ≠ `approvals`』= **只填数字拿不出锚点**（门槛没被真满足）；"
            "② 报『有类目但 `type_axis` 为空』= **类目没有浮出依据**（没有轴就没有『类』）；"
            "③ 报『孤儿字段』= `fields` 里有 `required` 没用的字段（装饰）；"
            "④ `entries` 为空**必须**给 `empty_reason` —— **空 ≠ 没事**，门禁会把「0 条」报出来；"
            "⑤ `ratio_target.judged` 标明这条目标是**判**还是**只报数**。"
            "⚠ **它不判什么**：**不判**类目选得对不对（那是人读血统 / 风险），"
            "也**不判**『该不该引入豁免』（D-48 要求先证它与结构 contain 不冲突）。"
            "⚠ 当前 `entries` **实测 0 条**（理由在 `empty_reason`，两条独立实测）——"
            "**别把本项读成『已有免终裁通道』**"},
    {"id": "memory-gates", "title": "记忆四道门 + 授权边界", "fn": check_memory_gates, "quick": True,
     "fix": "D7-P3-3 / D-47 / D-48：`inventory/memory-gates.yaml` 是**四道门**"
            "（write/retrieval/promotion/reuse）与**授权边界（结构性约束）**的单一真值。"
            "① 报『缺一道门』= D-47 要求四门齐；"
            "② 报『挂名假判』= 某门的 `judgment.ref` 指向一个**不存在**的 CHECKS id"
            "（判据写了但没人跑 —— 本仓最典型的一类假绿）；"
            "③ 报『`gate: none` 且本仓可控 ⇒ 红』= **私有→共享那一跳敞着**"
            "（MAPLE-Guard 点名的关键一跳）；**引擎侧**关不掉的无门通道只**点名 + WARN**（绝不静默）；"
            "④ 报『未登记的记忆面接触点』= 有代码新碰了记忆路径 ⇒ **要么登记**（写清为什么）**要么去掉**；"
            "⑤ 报『记忆出网嫌疑』= 同一行同现【记忆路径】与【跨机搬运令牌】（本模型里最贵的错误）；"
            "⑥ 报『隔离靠文本前缀』= 有人把**命名**升格成了**判据**（D-48：要靠结构 contain）；"
            "⑦ 报『登记的接触点不存在』= 登记腐化。"
            "⚠ 记忆路径的**唯一字面定义点**在 yaml 的 `egress.path_tokens`（角色名 → 路径）；"
            "改路径**只改那里**，不要在代码里再抄一份（本仓头号失败形态）。"
            "⚠ **它不判什么**：不判记忆**内容**，也**验不了门的效力** —— "
            "MAPLE-Guard 的 ASR 下降是**它自己的实验**，本仓没有投毒实验台 ⇒ "
            "**别把本项读成「记忆已安全」**"},
    {"id": "multi-round", "title": "多轮闭环 + 轮数上限", "fn": check_multi_round, "quick": True,
     "fix": "D7-P4-1（退出判据原文：多轮闭环可跑；**轮数上限有判据**）："
            "`inventory/multi-round.yaml` 是本仓**真实存在的重复执行闭环**的单一真值"
            "（★ 受理侧的协商回环**早就有**，路线总表 §11.2(a) 已裁「复用状态语义、不另建」）。"
            "① 报『`cap_state` 不在封闭集』= **漏写上限** —— 上限 / 无上限的理由 / 待谁裁，"
            "**三者必须显式其一**（不许靠「没写就是没有」）；"
            "② 报『`max_rounds` 与代码不符』= 真值表与 `agent-cli.ps1` **实提取**的上限不一致 "
            "⇒ 改真值表**或**改代码；"
            "③ ★★ 报『**未登记的散文上限**』或『散文上限与登记不符』= **注释里的上限落后于代码** —— "
            "本批实测**两处**都写 2 而代码是 3（O-46 改 cap 时注释没跟）；"
            "散文里的上限**逐处登记**，否则它会悄悄骗人；"
            "④ 报『缺 `stop_on_agreement`』= **正向终止条件**没写 —— 上限只管最多几轮，"
            "『什么时候可以停』是另一半（EASE 早停）；"
            "⑤ 报『`on_exceed_kind` 不在封闭集』= **超限时发生什么**必须是一个可枚举的动作"
             "（`escalate` / `terminate` / `fail-record`）—— 且已有上限却留 `undecided` ⇒ 上限只有一半；"
            "⑥ 报『`plus_extra` 锚点找不到』= 那段代码改了/删了（登记腐化）；"
            "⑦ 报『上限未定的闭环 …（待裁，点名）』= **WARN 不阻断**："
            "已如实登记、等裁定 ⇒ 但**点名在案，不许静默**。"
            "⚠ **它不判什么**：不判「多轮**跑通**了没有」—— 只验**上限与终止条件被写明**；"
            "`agent-resume` 的续接链与受理侧回环**本轮均未端到端实跑**（见 yaml 的 `unverified`）"},
    {"id": "interruption-untrusted", "title": "中断态两岸口径 + 不可信证据",
     "fn": check_interruption, "quick": True,
     "fix": "D7-P4-2（Ds 简报 11 / 18）：`inventory/interruption-and-untrusted.yaml` 是单一真值。"
            "① 报『缺 `main_side` / `station_side`』= **只有一端声明了口径** —— "
            "Ds 实测的死锁就出在「一端等待、一端失败」；两岸**都要**写；"
            "② 报『判出死锁风险却**没有 `mitigation`**』= 那个等待**没人管怎么终结** —— "
            "★ 注意：**风险由门禁算，不由你填**（自报 = 同一事实两个定义点）；"
            "③ ★★ 报『**规则算不出这条真事故**』= `history` 里那条已修死锁，按当前两岸动作"
            "**算不出非 none** ⇒ **判据是空转的**，先修 `deadlock_risk()` 的规则；"
            "④ 报『护栏是空头的』= 已修事故写的 `regression_guard` 在夹具/测试里**找不到**；"
            "⑤ ★★ 报『**自报不算声明**』= 某条不可信输入声称已在某文件里声明，"
            "但**那个文件里真找不到**该 marker（第 18 条落空）；"
            "⑥ 报『`declared: false` 却缺 `why_not`』= **「没声明」也要给理由**；"
            "⑦ 报『`trusted_inputs` 为空』= **什么不算不可信**没写，边界靠猜。"
            "⚠ **它不判什么**：只能核那句声明**在不在**，**判不了模型是否真遵守**；"
            "也**不做注入实验**（本仓没有实验台）⇒ **别读成「注入已防住」**。"
            "⚠ `interruptions` 只有 3 条 —— **不是穷举**（ssh 不可达 / 站断电等未登记）"},
    {"id": "rubric-blindspot", "title": "rubric 纪律 + 自环盲区登记",
     "fn": check_rubric_blindspot, "quick": True,
     "fix": "D7-P4-3（Ds 简报 15 / 12 / 21）：`inventory/rubric-and-blindspots.yaml` 是单一真值。"
            "① 报『rubric 里**找不到**必含句』= 某条**裁判纪律被人删了/改了措辞**"
            "（rubric 是纯文本资源，删一句没人知道）⇒ 补回来，或**同步改真值表**；"
            "② ★ 报『找不到 `ReadAllText`』= rubric/tmpl 的**读取退回了裸 `Get-Content`** —— "
            "PS 5.1 默认按 ANSI 读 ⇒ **中文资源会乱码**（本仓那条『UTF-8(BOM) 铁律』"
            "实际是靠**显式编码**兜住的）；"
            "③ 报『缺 `impl-same-source`』= **本仓最实质的盲区没登记**：三站互审走**同一份 "
            "`agent-cli.ps1`** ⇒ 实现层缺陷两侧同时出现，互审**结构上发现不了**；"
            "④ 报『缺 `why_blind`』= 没说清**为什么互审看不见**（那就不叫盲区登记，叫感想）；"
            "⑤ 报『`other_guard` 是 `na` 但缺 `why`』= **「没有替代机制」也要给理由**；"
            "⑥ 报『`derived_edges` 是 `deferred` 但缺 `condition`』= 触发条件没写死 ⇒ "
            "它会**永远挂着或悄悄做掉**。"
            "⚠ **它不判什么**：只核那几句**在不在**，**不判 rubric 全文写得好不好**（纯文本，语义不可机判）；"
            "盲区清单**不是穷举**；`derived_edges` 的触发条件是**跨仓事件**，本仓判不了"},
    # O-105 (2026-09-27): 能力盘点表 —— 动机 = "能力的存在性每次都要靠问一遍"
    #   （实测散落在 4 份调研正文里）⇒ 收成一张**可机核**的表；形态借自姊妹仓 P-050 RESEARCH §3.7。
    {"id": "capabilities", "title": "能力盘点（能力 → 载体 → 判定）",
     "fn": check_capability_inventory, "quick": True,
     "fix": "O-105：`inventory/capability-inventory.yaml` 是**能力层**的单一真值"
            "（与 ports/models/plugins 那类**事实**真值表分工不同：本表只**引用**它们，不复制事实）。"
            "① 报『缺 `metric` / `updated`』= **增长型计数没有口径或读数日期** —— "
            "口径一变，表里所有数字立刻失去意义（§87.6 的『同日漂移』就是这类失败）；"
            "② ★ 报『`carriers` 指的判据**不是已注册 CHECKS id**』= **挂名**"
            "（判据写了但没人跑 —— 本仓最典型的一类假绿）；"
            "③ 报『`carriers` 指的文件 / 真值表不存在』= **载体已腐化** ⇒ 改登记或补文件；"
            "④ 报『partial 缺 `gap`』= **缺哪一块没写清**（否则 partial 是个托词，"
            "读者无法判断它离 present 差多少）；"
            "⑤ ★ 报『absent 缺 `why`，或 `why_kind` 不在封闭集』= "
            "**「不做」也是一种结论，必须写下来**（不适用 / 未做 / 待裁 —— 三者含义不同）；"
            "⑥ 报『`self_id` 不在 items 里』= **「能力盘点」这项能力本身没被盘点**（自指缺口）；"
            "⑦ 报『声明的封闭集与判据实现不一致』= 改了代码没改表（或反之）"
            "⇒ **那时本判据自己就是假绿**。"
            "⚠ **它不判什么**：只保证「**有载体且可达**」，**不保证「载体真的管用」**"
            "（效力未被任何实验测过）；`verdict` 与 `gap` / `why` 均为**人工判断**且未经第二方复核；"
            "★ 「**漏了哪项能力**」**不可判** —— 没有权威清单可比对，只能靠新增时补"},
    # O-108 (2026-09-27): 文档状态声明的**两处位点** —— 动机 = `O-106` 落体时发现：
    #   同一文档在 front matter 与正文各写一份状态，**实例 12 处两处不等**（含 `draft` ↔ `verified`）。
    {"id": "doc-status", "title": "文档状态两处声明（判派生过期）",
     "fn": check_doc_status, "quick": True,
     "fix": "O-108：`inventory/doc-status.yaml` 是**两处状态声明**的单一真值"
            "（`semantics` 声明「谁是真值、谁是派生」；`freeze` 只装**存量**）。"
            "① ★ 报『两处不等』= **判为「派生过期」** ⇒ **先确认真值**：若取证显示 **fm 陈旧**，"
            "**先更新 fm**（那是真值更新）再让正文跟上；**稳态下**修法唯一 = **改正文行**"
            "（别改 fm 去迁就正文 —— 一改，那个面就变回「两处都可写」= 被 I-10 禁的形态）；"
            "② 报『冻结项**已自愈** / 已不再是两处都有』= **从 `freeze` 删掉**"
            "（防腐化 —— 同 `secrets` 的「豁免未命中」、`ops.yaml` 的冻结存量）；"
            "③ 报『缺 `semantics.single_write` / `derived`』= 本表**退化成一张豁免清单**了"
            "（没声明谁是真值，就只剩「不许红」这一个作用）；"
            "④ 报『`file` 不在仓里 / 缺 `why`』= 登记腐化 / **冻结没写理由**。"
            "⚠ **它不判什么**：① 它**验不了**「人是否只改 fm」（只能检出两处**不一致**）——"
            "**这正是 I-10 说的「检不出两处一致地错」**；② ★ **本面仍是两个位点** ⇒ "
            "本项是**降格处置**、**非 I-10 的完全实现**（彻底消除 = O-108 案①：只留 front matter）；"
            "③ **词表符合性**见 ⑤（O-109 起并入本项）；"
            "④ 射程**只到文档头 20 行**（口径写死在 `DOC_STATUS_HEAD`，§90.4 的教训）；"
            "⑤ ★ O-109（**第二段判据：词表符合性，按档**）：`inventory/doc-status.yaml` 的 `kind_source`"
            "登记「档 → 词表读取位点」—— 有模板档（design / checklist / adr）真值**在模板链**、"
            "无模板档（ledger / process）**在 yaml**；`kinds` 只登记无模板档的归属，判档按 `kind_rule`。"
            "报『token **不在档内**』= 该位点写了**词表外**的值 ⇒ 改回档内词（词表见报错列的集合）；"
            "报『**词表缺档**』= `kind_source.by_kind` 少了一档 ⇒ 补档（无模板档要同时补 `kinds` 归属）。"
            "⚠ **它只判 token 在不在档内**，**不判**「这个状态对不对」（状态位的**语义**对不对要人读）；"
            "★ **模板文件跳过**（`*_TEMPLATE.md` 的「状态」行是**词表本身**，不是实例值）"},
    {"id": "md-tables", "title": "md 表格列数守恒（防拆错格）",
     "fn": check_md_tables, "quick": True,
     "fix": "A4（2026-09-29）：同一张 markdown 表里 **分隔行 / 数据行** 的**格数**必须 == **表头**格数。"
            "报『**某行 N 格 ≠ 表头 M 格**』= 该行**被拆错格**（字段错位）—— 最常见的原因是"
            "**单元格文本里的竖线没转义**：写成**反斜杠 + 竖线**（`\\|`）即可；"
            "整行少/多一格（比如漏了个 `|`）⇒ 补齐。"
            "★ 口径（**唯一实现** = `md_table_scan`）：① **空单元格计入**格数；"
            "② 分隔行必须**紧邻**表头（不跨行找表）；③ 代码围栏（``` / ~~~）与 GFM 缩进码块**跳过**；"
            "④ 单元格里的转义竖线**不算分隔**。"
            "📊 note 报 `扫描 N 篇 · 表 T 张 · 违规 V（冻结 F · 新增 D）`；"
            "`表 0 张 ⇒ FAIL`（判据**无对象** = 退化空判，故「整篇没表 ⇒ 空集恒真」这种假绿被堵住）。"
            "⚠ 报『冻结条目**失配** / 指向**已不存在**的文件』= **从 `inventory/md-tables.yaml` 删掉对应条目**"
            "（冻结**只减不增** —— 修好了就清账，留着会烂成垃圾桶；同 `secrets` 的「豁免未命中」防腐化）；"
            "存量冻结的**逐条理由**在该 yaml 里（2026-09-29 上线时实测 28 处 / 13 个文件）。"
            "⚠ **它不判什么**：不判表格**内容**对不对，也不判文档该不该有表 —— 只判**格数守恒**。"},
    {"id": "determinism", "title": "确定性噪声口径（单一真值表）",
     "fn": check_determinism, "quick": True,
     "fix": "A5（2026-09-29）：噪声口径 = **单表** `inventory/determinism-noise.yaml`（所有「双跑 / 逐字节比对」"
            "类判据**引用**它，**不各写一份** —— 各写一份 = 同一事实两处表达，改一处漏一处）。"
            "报『缺 `updated`』= 增长型真值表必须带**读数日期**；报『`line-ending.normalize_to` 必须 LF』="
            "逐字节比对要求二进制一致（归一化只在**生产端**固化，比对端妥协 = 把噪声洗成假绿）；"
            "报『`applies_to` 含 X —— 不是真实断言 id』= **孤儿消费者**（无消费者的真值表会腐化）⇒ 改成真实 gate id；"
            "报『正则匹配不上代表样本』= 表里那条正则**检不出该类噪声**（坏正则）⇒ 修正则；"
            "报『有 match 但无自证样本』= 新增了可机检噪声却没给夹具 ⇒ 在 `_DET_SAMPLES` 补样本；"
            "报『`determinism: n/a` 缺 reason』= 天然不可双跑者必须写理由（**禁止静默跳过**）。"
            "⚠ **它不判什么**：不真的跑某条管线双跑（那要具体管线接入）—— 只钉住**口径单一真值 + 表可用性**。"},
    {"id": "derived-view", "title": "派生只读视图（真值→渲染→逐字节比对）",
     "fn": check_derived_view, "quick": True,
     "fix": "A3（2026-09-29）：清单类文档的**第二定义点**正解 —— 抄的那份改成**派生件**，"
            "从真值**渲染**出来（渲染器 = `ops/derived_view.py`；当前真值源 = `inventory/ports.yaml`；"
            "落档视图 = `docs/派生视图_端口分配.md`）。"
            "报『**过期**（声明 source-hash ≠ 当前）』= 真值改了但视图没重渲染 ⇒ 跑 `py ops/derived_view.py --emit`；"
            "报『**逐字节不一致**』= 视图被**手改**过 ⇒ 别手改，同样 `--emit` 覆盖（手改会被下次渲染冲掉）；"
            "报『**渲染链路故障**(rc=2)』= 读真值/解析 yaml/落档写入失败 ⇒ **先修渲染器**（这与「过期」不是一回事）；"
            "报『落档视图**缺 `source-hash` 行**』= 档头被删 ⇒ `--emit` 重出。"
            "★ **为什么判退出码而不在这里重实现比对**：三态（0 一致 / 1 过期·漂移 / 2 故障）由渲染器**单一定义**，"
            "门禁只做消费者 —— 各写一份 = 同一事实两处表达（本仓头号形态）。"
            "⚠ **它不判什么**：不判视图**内容**对不对（那是 `ports` 判据的事），只判「视图 == 真值的确定函数」。"},
    {"id": "executor-trace", "title": "执行侧过程留痕（五采集点）",
     "fn": check_executor_trace, "quick": True,
     "fix": "A2（2026-09-29）：治「判据只能看产物，看不到过程」—— 站上执行体改过哪些文件 / 跑过哪些命令"
            "此前**查不到**（既有两件：输出字节序列只记吞吐曲线、工作区改动摘要实测为空）。"
            "口径 = `dogfood-cards/imp4-executor-trace-design.md`：最小充分集**5 项**"
            "（cmd / env / fs / tool / artifact）。"
            "报『**缺采集点标记 X**』= `ops/station-bin/agent-cli.ps1` 里那一维**没被采集**"
            "（看着有留痕，实际缺维度）⇒ 补回该采集点（**别只补门禁**）；"
            "报『出现 `chain=core` / `chain=verified`』= **伪称执行体内部可核** —— 工具调用链由执行体**内部**产生"
            "（可篡改 / 漏报 / 伪造），**只能如实标 `uncore`**；"
            "报『runDir 的 executor-trace.txt **缺段**』= 落到仓的留痕件不齐（真缺陷）⇒ 查该次派发的采集链路。"
            "**锚定段**（2026-09-30 补）：报『**自报**』= 留痕件里出现执行体自报的产物哈希"
            "（`[artifact] hashes=` 必须是 `main-side` —— 执行体不可信，哈希只能由主控侧回收时算）⇒ 改采集点；"
            "报『**ts 不符**』= 留痕件不属于这一次（`ts=` ≠ runDir 名）⇒ 查归档 / 回收是否张冠李戴（`O-57` 同族）。"
            "⚠『覆盖 0 个』**不作为 FAIL**（本件尚未经真派发 ⇒ 覆盖率**未验**，报数不入分母）；"
            "⚠『无锚记录 N』同理**只报数**（主控侧没有该次 `content_digest` ⇒「没验到 ≠ 验出问题」）。"
            "⚠ **它不判什么**：逐条字面细节（两段写入 / `$Script:EV_FILES` 登记 / 主控归档 / `free -m` 而非 `/proc`）"
            "由**离线夹具** `_fm_golden_test.ps1` 守（见 `ps1-golden`）—— 本判据**不抄第二份**。"},
    # O-63 (2026-09-25): 取号并发夹具。**刻意 quick:False**（要起 8 个独立进程 + 两次 2.5s 共同释放时刻 ⇒ 约 6s）。
    {"id": "ps1-runstamp", "title": "ts 取号并发夹具", "fn": check_ps1_runstamp, "quick": False,
     "fix": "O-63: 跑 `powershell -NoProfile -ExecutionPolicy Bypass -File ops/station-bin/_runstamp_hammer.ps1 -N 8 -SelfTest`。"
            "两行**都要**在：`RUNSTAMP_HAMMER … PASS`（正向：8 进程 ts 全不同）+ "
            "`RUNSTAMP_HAMMER_SELFTEST … PASS`（负向：**同一把锤子**打旧实现必须检出撞车）。"
            "⚠ 只报负向 = **夹具是装饰**（正向根本没产生唯一 ts）；只报正向 = 负向没跑（少一行 ⇒ 本断言直接 FAIL）。"
            "⚠ 若出现 `dup:` ⇒ **真的撞了**：检查 `Get-UniqueRunStamp` 的原子原语是否被改回 "
            "`New-Item -ItemType Directory`（实测它会漏，uniq=11）—— 必须是 `[IO.File]::Open(..., CreateNew, ...)`"},
    # O-64 (2026-09-25): **测试套件接进门禁** —— 此前 21 套测试无任何机械执行者（"有测试 ≠ 有人在跑"）。
    #   实测依据与本项定位见 check_py_tests 的 docstring 与 PY_TESTS 上方注释（含 quick 取舍的实测值）。
    {"id": "py-tests", "title": "Python 测试套件(统一入口)", "fn": check_py_tests, "quick": False,
     "fix": "跑 `py tests/run_py_tests.py`（或 `-v` 看每题完整输出）⇒ 修明细里的 FAIL。"
            "⚠ **先判「是回归还是断言陈旧」**：若实现侧确有语义变更（看 `ops/station-bin/agent-cli.ps1` 的"
            "注释/O- 台账）⇒ 改**断言**并写明理由（**方向是改写断言，不是回退代码** —— 回退等于把修好的洞挖回来）；"
            "若实现侧无变更 ⇒ **是回归**，改代码。"
            "⚠ 报『总数 == 0』或『未解析到汇总行』= 入口本身坏了（如 discover 找不到测试）⇒ 先修入口 —— "
            "那是**比任何单条测试更严重**的失效（整批验证静默消失）"},
    {"id": "usb4", "title": "USB4 三角环链路", "fn": check_usb4, "quick": False,
     "fix": "地址/路由不符 => 对照 inventory/net.yaml 与归档 §6.3/§6.6; "
            "链路不通 => 先查 BIOS USB4 安全等级与是否冷启动(归档 §6.5)"},
    {"id": "gates", "title": "内存门禁", "fn": check_gates, "quick": False,
     "fix": "load-gate 缺失需补部署到 /usr/local/bin; 余量 ≤0 先卸载或清残留; "
            "loadavg>8 等负载回落再加载; 站上件与仓库副本不一致 => 这些件是站上件(改仓库不生效), "
            "按明细走「备份(cp -a, 核备份 md5 == 原 md5) → install -m 755 → 核新 md5 == 仓库副本」, "
            "或回滚站上版并改仓库侧; 清单见 rpc_check.py 的 STATION_BINS"},
    {"id": "halogen-assets", "title": "容器模型资产预检", "fn": check_halogen_assets,
     "quick": False,
     "fix": "按明细补资产/重分发权重；镜像缺失则 containers pull；不要先杀旧服务"},
    {"id": "engine", "title": "引擎态与残留", "fn": check_engine, "quick": False,
     "fix": "残留用 infer-unload 或清 llama/rpc 进程; 端口在听但 RSS 异常需查进程归属"},
    {"id": "backend", "title": "引擎后端与 studio 防线", "fn": check_backend, "quick": False,
     "fix": "默认单站引擎=HIP、分布式(/opt)=Vulkan 是本集群的**既定形态**; 后端变了先查是谁改的 "
            "(studio 自更新 / UPGRADE_SOP 升级 / 有人换构建) 再决定是否改期望值, 并把台账 §2.6 "
            "的后端矩阵同步; 回滚基线缺失 => 从同版本站 tar 分发补回 "
            "(UPGRADE_SOP §6: 保留 `<现役>` + `9859` 两个版本目录以支持分钟级回滚); "
            "**pin 未生效** => 落 `/etc/environment` 的 `UNSLOTH_LLAMA_CPP_BACKEND=rocm`"
            "(`.bashrc`/`.profile` 对非交互 ssh 无效, 见决策简报 §8.2); "
            "**缺 `X-Unsloth-Events`** => 升级 studio(简报 §三); "
            "**studio 版本或引擎构建不同版** => `cluster.py studio status` 看矩阵再决定是否同升; "
            "**引擎备份目录为空** => 引擎若被替换只能靠站间 tar(要求三站逐字节同版)或重下"},
    {"id": "models", "title": "模型库完整性", "fn": check_models, "quick": False,
     "fix": "孤儿 `cluster.py models link --go`; 断链 `cluster.py models prune --go`"},
    {"id": "stations", "title": "三站实况对账", "fn": check_stations, "quick": False,
     "fix": "conf/权重/凭据/端口/插件任一项不符 —— 见明细, 一律以站上实况为准改仓库侧"},
    # ★ 2026-10-13: `$PROJECTS` 数据化 —— 项目注册表**自洽**（`$PROJECTS` 的唯一真值）。
    #   ⚠ 它**不判** root 存在性（外盘可能离线 ⇒ 会假红）；存在性由 `workspace create` 在使用时判。
    {"id": "projects", "title": "项目注册表($PROJECTS 真值)", "fn": check_projects, "quick": True,
     "fix": "改 `inventory/projects.yaml`（`$PROJECTS` 的唯一真值）：① id 非空且**逐字**= 调用方使用的键；"
            "② status ∈ {active, retired}；③ since 形如 YYYY-MM-DD；④ root 非空字符串（**单引号**括起 Windows 路径）；"
            "⑤ **同一串不许属两条**。★ 新增项目 = 追加一条 `active`（**门禁不看人只看登记**）；"
            "退役 = 改 `retired` 而**不删**。⚠ 报『projects 为空』= 判据退化（无对象）"},
])
MARKS = {"PASS": "✓", "WARN": "▲", "FAIL": "✕", "SKIP_FAILED": "⊘"}
# D6-P0-1 (2026-09-23): **"非执行"必须三分, 不许含混** —— 这是本仓"假绿"的头号来源。
#   · **MODE_SKIP**   = `--quick`/`--only` 未选中该断言(**模式性省略**) ⇒ **合法, 不计失败**
#   · **SKIP_FAILED** = `needs` 里有 FAIL/SKIP_FAILED ⇒ **算失败**(不许静默降级)
#   · **WARN**        = **环境降级**(如缺 paramiko ⇒ 断言自报 WARN) ⇒ 不进 FAIL 集, 但必须可见
#     依据: `docs/2026-09-23_D6-D7分阶段执行方案.md` §11.1-A —— 若把环境降级误判成"级联 skip",
#     会让**每个 release 都因环境缺包变红**(假红淹真信号)。
MODE_SKIP = "MODE_SKIP"


def _validate_graph(checks):
    """断言依赖图校验 —— **配置错误必须 FAIL, 不许静默**(D6-P0-1)。

    `needs` = 必须先通过的断言 id 列表。校验两件事：
      · **未知 id**（打错字 / 引用了已删断言）⇒ 报错；
      · **成环** ⇒ 报错（拓扑执行会死锁 / 漏跑）。
    **纯函数** ⇒ 便于单测与注入（正反用例）。
    """
    ids = {c["id"] for c in checks}
    errs = []
    for c in checks:
        for n in c.get("needs", []):
            if n not in ids:
                errs.append(f"{c['id']}: needs 引用了不存在的断言 '{n}'")
    needs_of = {c["id"]: list(c.get("needs", [])) for c in checks}
    color = {}

    def dfs(u, stack):
        color[u] = 1
        for v in needs_of.get(u, []):
            if color.get(v) == 1:
                errs.append("needs 成环: " + " -> ".join(stack + [v]))
                continue
            if color.get(v, 0) == 0:
                dfs(v, stack + [v])
        color[u] = 2

    for c in checks:
        if color.get(c["id"], 0) == 0:
            dfs(c["id"], [c["id"]])
    return errs


def run_checks(selected):
    """**可注入的执行缝**：跑 `selected`，返回 `(results, failures)`。

    D6-P0-1「**非执行三分**」的**唯一落点**（`tests/test_rpc_check_three_classes.py` 三类各一注入）：
      · **MODE_SKIP**   = 调用方**不给**它（`--quick`/`--only` 未选中）⇒ **不进 results ⇒ 不计失败**
        （呈现 = `main()` 里那行"已跳过 (模式=…)"）；
      · **SKIP_FAILED** = `needs` 里有 FAIL/SKIP_FAILED ⇒ **算失败**（不许静默降级成 skip）；
      · **WARN**        = **环境降级**（缺 paramiko/pyyaml 等 ⇒ 断言自报 WARN）⇒ **不进 FAIL 集，但必须可见**。
    ⇒ 三者**互不相同**：**只有 SKIP_FAILED / FAIL 计失败**。

    抽成独立函数是为了能**注入假断言**（不跑真 I/O）做上述三类的注入用例；行为与旧的内联循环逐字等价。
    """
    results, failures, status_of = [], 0, {}
    for c in selected:
        unmet = [n for n in c.get("needs", []) if status_of.get(n) in ("FAIL", "SKIP_FAILED")]
        if unmet:
            status, note, detail = "SKIP_FAILED", f"依赖未满足: {', '.join(unmet)} ⇒ 本项未执行(算失败)", []
        else:
            try:
                status, note, detail = c["fn"]({})
            except Exception as e:
                status, note, detail = "FAIL", f"{type(e).__name__}: {e}", []
        status_of[c["id"]] = status
        results.append((c["id"], c["title"], status, note, detail))
        if status in ("FAIL", "SKIP_FAILED"):
            failures += 1
    return results, failures


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--quick", action="store_true", help="仅本地快检 (pre-commit)")
    ap.add_argument("--only", default="", help="逗号分隔的断言 id")
    ap.add_argument("--list", action="store_true", help="只列断言清单")
    # ★ 2026-10-13（`$PROJECTS` 数据化）：外壳载入用 —— 打 `{id: root}` 的 **JSON**（不自洽 ⇒ 退出码 2）。
    ap.add_argument("--list-projects", action="store_true",
                    help="打项目注册表(inventory/projects.yaml)的 {id: root} JSON（`$PROJECTS` 载入用）；不自洽 ⇒ 2")
    # ★ B 段（2026-10-01）：D7 协议判据的**消费面**（外壳调它 ⇒ 判据只在一处；见 `d7_cli`）。
    ap.add_argument("--d7-envelope", nargs=2, metavar=("KIND", "PATH"),
                    help="D7 信封校验：KIND ∈ TaskContract|RunReport|Verdict；PATH = JSON 文件或 - (stdin)")
    ap.add_argument("--d7-transition", nargs=3, metavar=("FROM", "TO", "ACTOR"),
                    help="D7 六相状态迁移校验（ACTOR ∈ master|worker）")
    ap.add_argument("--d7-block", default="", metavar="RULE",
                    help="D7 8 条拦截之一（RL1/RL2/RL3/I1/I3/I6/PRM/PRW）")
    ap.add_argument("--d7-ctx", default="", metavar="JSON",
                    help="--d7-block 的上下文（JSON 文件或 -）")
    ap.add_argument("--d7-host-sep", nargs=2, default=None, metavar=("EXEC_HOST", "ARBITER_HOST"),
                    help="★ B3 `PRH`：产出机 vs 裁决机的**同机可见性**（0=分离 / 1=同机 / 2=不可判）"
                         "—— 报数用，调用方按 WARN 处理（不阻断）")
    args = ap.parse_args()

    rc = d7_cli(args)                      # 命中 D7 消费面 ⇒ 直接返回（不跑门禁）
    if rc is not None:
        return rc

    # ★ 2026-10-13（`$PROJECTS` 数据化）：**外壳载入的唯一读路** —— 吐 JSON（判据只在一处，
    #   外壳**不自己解析 YAML** —— PS 5.1 无 YAML 解析器，自解析会造第二个解析器 ⇒ 漂移即 fail-open）。
    if args.list_projects:
        if not PROJECTS_REG.is_file():
            print("LIST_PROJECTS_ERR: inventory/projects.yaml 缺失（`$PROJECTS` 的唯一真值）", file=sys.stderr)
            return 2
        try:
            import yaml
            reg = yaml.safe_load(PROJECTS_REG.read_text(encoding="utf-8")) or {}
        except Exception as e:
            print(f"LIST_PROJECTS_ERR: {type(e).__name__}: {e}", file=sys.stderr)
            return 2
        bad, _ = validate_projects(reg)
        if bad:
            print("LIST_PROJECTS_ERR: " + " | ".join(bad), file=sys.stderr)
            return 2
        print(json.dumps(projects_index(reg), ensure_ascii=False))
        return 0

    if args.list:
        for c in CHECKS:
            print(f"  {c['id']:10s} {c['title']:16s} quick={str(c['quick']):5s} {c.get('fix', '')}")
        return 0

    selected = CHECKS
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        selected = [c for c in CHECKS if c["id"] in want]
    elif args.quick:
        selected = [c for c in CHECKS if c["quick"]]

    mode = "quick" if args.quick else "全量"
    print(f"\nrpc check · 模式={mode} · {ROOT}\n")

    # D6-P0-1: **图校验先行** —— 配置错误(未知 id / 成环)不许静默, 直接阻断
    graph_errs = _validate_graph(CHECKS)
    if graph_errs:
        print("  ── 断言依赖图校验 ──")
        for e in graph_errs:
            print(f"    ✕ {e}")
        print("\n  结论: FAIL (断言依赖图配置错误) → 阻断\n")
        return 1

    results, failures = run_checks(selected)

    for cid, title, status, note, _ in results:
        print(f"  [{status:4s}] {MARKS[status]} {cid:10s} {title:16s} {note}")

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

    # 处置建议: 红灯必须给出"下一步", 不能只报"哪里不对" (P2-2 健康引擎形态)
    bad = [r for r in results if r[2] in ("FAIL", "WARN", "SKIP_FAILED")]
    if bad:
        fixes = {c["id"]: c.get("fix", "") for c in CHECKS}
        print("\n  ── 处置建议 (红灯优先) ──")
        for cid, _t, status, _n, _d in sorted(bad, key=lambda r: r[2] != "FAIL"):
            print(f"    {MARKS[status]} {cid:10s} {fixes.get(cid, '')}")

    n_fail = sum(1 for r in results if r[2] in ("FAIL", "SKIP_FAILED"))
    n_warn = sum(1 for r in results if r[2] == "WARN")
    n_ok = len(results) - n_fail - n_warn
    tail = f"绿灯 {n_ok} · 黄灯 {n_warn} · 红灯 {n_fail}"
    if failures:
        print(f"\n  结论: FAIL ({failures} 项失败) → 阻断; 修复后重跑 · {tail}\n")
        return 1
    print(f"\n  结论: PASS · {tail}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
