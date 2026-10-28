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


# ── review-p2-split 8B-3：注册表 + 治理层 + 三站层（门面重导出）─────────
from rpc_registry import CHECKS
from rpc_common import (
    INVENTORY_DIR, ROOT, load_inventory,
)
from rpc_governance import (
    ARTIFACTS_INV, BASH_BROKEN_SAMPLE, CLUSTER_GLOB, CLUSTER_LAYER_KEY, CLUSTER_LAZY_ALLOW_KEY,
    CONST_DICT_RE, DECL_CLUSTER_FILES, DECL_CLUSTER_PY, DECL_MANUAL, FACADE, MANUAL_PORT_RE,
    MODEL_CONST_RE, OPS_INV, PORT_CONST_RE, PS_SNIPPET, PY_SNIPPET, SCRIPT_EXT, SECRET_ALLOW,
    SECRET_RE, SHELL_STRICT_KEY, SHELL_STRICT_PROLOGUE, SHELL_STRICT_SCAN_LINES, SH_LINT,
    STATION_LAYOUT_KEY, STATION_PROBE_GLOB, _FACADE_CONSUMER_RE, _FACADE_DIRS, _bash_can_read,
    _bash_candidates, _bash_lint, _bash_lint_parallel, _collect_imports, _declared,
    _in_script_scope, _is_binary, _iter_governed_scripts, _iter_shebang_scripts,
    _iter_source_files, _lib_set_line, _load_ops_inv, _mask, _mods_of, _pick_bash, _posix,
    _py_version, _run_with_stdin, _shell_prologue, _strip_py_prose, _untracked_count,
    check_artifacts, check_cluster_deps, check_facade, check_inventory, check_scripts,
    check_secrets, check_sensitivity, check_shell_strict, check_station_layout, check_syntax,
    cluster_dep_edges, cluster_dep_graph, facade_names, find_cycles, validate_cluster_deps,
    validate_facade, validate_sensitivity_inv, validate_shell_strict, validate_station_layout,
)
from rpc_stations import (
    ALL_STATIONS, ENGINE_PORTS, EPHEMERAL_MIN, INVENTORY_NET, INVENTORY_PLUGINS,
    INVENTORY_PORTS, NET_ENDS, PLUGIN_KINDS, PLUGIN_STATIONS, RESIDUAL_RSS_MB, RESIDUAL_WARN_MB,
    SEC_RE, STATION_BINS, STATION_CMD, TB_PCI_RE, VALID_MODE, VALID_PROTO, VALID_SCOPE, WATCHED,
    _BACKEND_CMD, _EXPECT_DIST_BACKEND, _EXPECT_LLAMA_BACKEND, _EXPECT_STUDIO_BACKEND,
    _HEALTH_CACHE, _HEALTH_CMD, _LANIP_CMD, _OCCUPANT_KINDS, _OCCUPANT_OK, _engine_api_ports,
    _health_probe, _is_loopback_addr, _lanip_via_usb4, _local_lan_ip, _net_doc,
    _parse_health_sections, _parse_lanip, _parse_sections, _plugin_diff, _plugin_items,
    _plugin_scope, _plugin_src_names, _plugins_doc, _port_entries, _scopes, _ssh_g_hostname,
    check_aliases, check_backend, check_engine, check_gates, check_halogen_assets, check_impact,
    check_models, check_plugins, check_ports, check_stations, check_usb4, classify_engine_band,
    classify_engine_occupant, pick_lan_addr, tb_pci_of, usb4_pick_iface, validate_lan_addr,
)

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
