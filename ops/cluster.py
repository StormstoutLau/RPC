#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cluster.py — 三机推理集群聚合操作 CLI (主控站)

用法:
    python ops/cluster.py status [--html] [--frames]
    python ops/cluster.py load <alias前缀> [--backend unsloth|llama-rpc|llama-single|vllm|ds4] [--engine <变体名|绝对路径>] [--worker A|C] [--force] [--keep]
    python ops/cluster.py frames
    python ops/cluster.py unload [--alias <别名>] [--station A|B|C]
    python ops/cluster.py estimate <alias> [--station A|B|C] [--ctx N] [--parallel N] [--ctk q8_0] [--ctv q8_0]  # 事前预估 (内存/耗时)
    python ops/cluster.py models {list|orphan|link|prune|verify|meta|fetch} [--station A|B|C] [--go]  # 模型全生命周期 (fetch=下发下载任务)
    python ops/cluster.py versions                                         # 引擎版本矩阵 (RPC/单机/LM Studio/opencode/内核)
    python ops/cluster.py e2e
    python ops/cluster.py studio status                                     # studio 套件矩阵 (版本/修复/防线 pin/引擎同版/复原路径; 只读)
    python ops/cluster.py secrets {status|scan|push|pull}
    python ops/cluster.py providers
    python ops/cluster.py egress [borrow [--to A|B|C --from A|B|C|--restore A|B|C] [--go]]
    python ops/cluster.py web [--host 127.0.0.1] [--port 8095] [--token <可选>]  # 傻瓜式 Web 管理 UI (按需服务)
    python ops/cluster.py flow [list|<name>] [--plan|--go] [args...]        # 声明式流程 (步骤→判据→台账)
    python ops/cluster.py reqlog {sample|summary|tail|path} [--minutes N]   # 引擎请求/token 统计 (站上采样)
    python ops/cluster.py ttl {status|check|enable|disable} [--ttl N] [--dry-run] [--go]  # 空闲 TTL 自动卸载 (默认关)
    python ops/cluster.py agent {runs|live|tail|chain|verify|audit|audit-judge} [--limit N] [--station X] [--json]  # 进度/吞吐 + 证据链 + 可复现性审计 + judge 校准
    python ops/cluster.py inbox                                             # 受理区跨项目进度 (每笔 <proj>-<date> 的 state/时间, 一行一条)
    python ops/cluster.py inbox seal <proj-dir> [--run <ts>|--all-runs] [--grade Reproduced|Replicated] [--go|--check]  # 交付证据束钉死/重算比对 (默认只出计划)
    python ops/cluster.py containers {status|install|pull|up|down} [--station A|B|C] [--image <ref>] [--name <名>] [--publish host:cont]... [--group-add g]... [--device dev]... [--volume host:cont[:ro]]... [--env K=V]... [--ipc host] [--ulimit k=soft:hard]... [--timeout 秒] [--detach] [--log <path>] [--plan|--go]  # 容器栈纳管 (默认只读 status; 写动作 --go 才动手)

子命令:
    status   三站 llama /health + 当前加载实例 + 引擎清单一屏聚合
             --html 生成静态快照页 ops/cluster_status.html
             --frames 追加各站框架级运行状态一览 (llama/unsloth/vllm/litellm/opencode)
             --all 追加凭据/Provider/出站三平面一行摘要 (统一入口四平面视图)
    load     自动路由到正确站并执行 infer-load (gpt-oss-120b->A, qwen3.8-27b-mtp->C, 其余->B;
             支持按站路由名 STATION_ROUTES, 如 gpt-oss-120b-c = C 站的 gpt-oss-120b;
             RPC 双机类 (RPC_MODELS) 走 _load_rpc 编排, 已自动化 —— 2026-09-15 P0-3 前为"打印手动步骤, exit 2")
             --backend 显式指定后端六线切换 (unsloth|llama-rpc|llama-single|vllm|ds4|halogen)。
             ★ 容器化模型 (CONTAINER_MODELS, 当前 = qwen3.8-flash-next): 缺省或 --backend halogen
               时**不分派 infer-load**, 改走 `_load_container_model` (docker run + /health 轮询);
               `--backend unsloth` 即回退到既有站内路径。
             换后端只需 load <alias> --backend <new> 一次 (infer-load 已做站内互斥), 无需先 unload;
             但显式 --backend 才会改后端, 缺省沿用 conf 旧值。
             对 llama-rpc 类模型: 显式 --backend 单机后端(非 llama-rpc) 视为强制单机加载, 走正常路径。
            --engine 指定**引擎变体** (与 --backend 的拓扑轴正交): 名 -> /opt/llama.cpp-<名>/, 或绝对路径。
              例: load glm-5.3-flash --engine glm5next-20260928   (RPC 双机必需, 见下)
              用途: 跑未并入主线的特性分支(如 GLM-5.3-Flash 的 glm5next), 而**不动** /opt/llama.cpp symlink。
              变体路径须已存在(见 vulkan-version-control/UPGRADE_SOP 的并存目录约定); 非法字符会被拒。
              ★ RPC 类模型 (RPC_MODELS) 也透传本参数: 变体引擎要求 **head 与 worker 同版**
                (infer-load 落 conf 的 LLAMA_SERVER_BIN + LLAMA_RPC_SERVER_BIN, 后者由
                 rpc-nodes --start 透传到各 worker 的 rpc-server@<alias> 单元)。
             对 ds4 (DwarfStar): 单机按普通 `infer-load --backend ds4` 路径;
               **双机走 PP (DS4_PP_MODELS, 值 = (coordinator 站, worker 站))** —— ds4 在 ROCm 不支持 TP,
               且**必须先起 worker、后起 coordinator** (见 _load_ds4_pp)。
            --worker 单 worker 指派 (仅 RPC 双机类, 2026-10-22): head 固定**权重所在站 B**,
              worker 由用户选 A|C (映射 = cluster_const.RPC_WORKER_IPS)。落实为
              `infer-load --rpc-target <ip:port>` **仅本次加载**覆盖 conf, 不改 conf。
              未给 --worker ⇒ 沿用 conf 的 RPC_TARGET (GLM/DS 已固化单 worker)。
              worker 必须同时在 `rpc-nodes --all` 声明与存活清单中, 否则响亮中止。
              例: load glm-5.3-flash --worker C
            --force 越过"反向冲突"预检 (O-178, 2026-10-28): 目标站若有活跃
              `rpc-server@<别的模型>` (= 正在给某个 head 当 worker), 默认**拒绝**
              (exit 3) —— 因为 load 的第一步 `infer-unload` 会停掉它, 对面 head 会
              `GGML_ABORT`(core-dump)。确要牺牲那个 head 才加 --force。
            --keep 允许**同站叠加** (O-179, 2026-10-28): 只替换同名 alias（不做全站清空），
              并且**先过容量门** —— 站上剩余内存装不下就 exit 4 并给出卸谁/改哪个参数的建议。
              不给 --keep ⇒ 仍按"同站互斥"全站清空（旧行为，默认）。RPC 双机本轮不支持。
    frames   三站框架级运行状态一览 (llama-server/unsloth/vllm/litellm/opencode), 恒 exit 0
    unload   三站并行幂等卸载；--alias 只卸该别名（保留同站其它模型），--station 只卸一站
    estimate 事前预估 (P1-1): 给定 alias 预估加载后的内存/耗时, 不实际加载 (只读)。
             支持 --station/--ctx/--parallel/--ctk/--ctv 覆盖 conf 推测值。
    models   模型全生命周期 (P1-2): list=按 (repo,模型目录) 聚合的清单(体积/量化/conf/是否已加载);
             orphan=物理库有但聚合视图看不到; link=给孤儿建软链; prune=清断链;
             verify 校验, meta=单站元数据。
             ★ fetch=**下发站上 `lm-download@<任务>` 下载任务**（把"下载"纳入唯一入口；ADR-0004 D3 路径①）:
               `models fetch <repo> <文件> [<文件>...] --station A|B|C [--name 任务名] [--dir DL_DIR]
                [--mirror hf-mirror|hf] [--go]`。单元 `ExecStart` 只吃**一个** `${DL_URL}`
               ⇒ 多文件（GGUF 分片 + mmproj）自动拆成 N 个任务；必须走本通道（`hf-mirror` 无 Xet
               ⇒ `hf download` 撞 HF >50 GB 常规上限，ADR-0010 实测踩过）。
             改站上状态的子命令**默认只出计划, --go 才动手**。
    versions 引擎版本矩阵 (P1-3): RPC 引擎 / 单机引擎 / LM Studio / opencode / 内核 三站并列,
             暴露版本漂移与受控路径完整性缺口 (MANIFEST md5 计数)。
    studio   studio 套件矩阵 (只读): 三站版本/修复项/防线 pin/引擎是否同版/复原路径。
    e2e      三站引擎在线冒烟 (直连 :8080, 不经 LiteLLM 网关——网关已退役)
    secrets  站内凭据治理 (平面②): status=落点+权限+明文巡检+"站内产物"型凭据与正本是否一致;
             scan=明文扫描; push=从主控下发 (对"站内产物"型凭据默认**跳过**覆盖, --force 强制);
             pull [站]=把"站内产物"型凭据 (如 unsloth.key, 由 studio 每次加载重铸) **从站上收回正本**
             —— push 前先 pull 才是幂等的, 否则会用陈旧正本覆盖站上真 key、打断该站 agent
    providers 三站 agent provider 聚合 (平面②): provider 集合/默认模型/凭据引用形态/漂移检测
    egress   出站平面探针 (平面③): 主控+三站 -> OpenRouter 健康/用量/余额
             [borrow] 额度借用/归还 (**默认只出计划; --go 才写凭据**): 单站日额度到顶时,
             把同侪 key 临时推给该站(每站仍 1 个 key 文件 ⇒ 明文面不扩大); 台账 ops/.or-borrow.json
    flow     声明式流程 (P2-1): 每个 flow 声明「步骤 → 判据 → 台账落点」, 一次跑完并落 metrics-log。
             内置 verify(只读, 默认执行) / bench / swap / rotate (三者会改站上状态, 默认只出计划, --go 才动手)。
             `flow list` 打印全部步骤与判据; `flow <name> --plan` 只看计划; 任一步不达标立即中止。
    reqlog   引擎请求/token 统计 (P2-3): 站上读原生 /metrics + /slots, 与上一条样本差分后
             追加 JSONL 到 ~/.local/share/rpc/reqlog.jsonl; 主控聚合 (加权口径)。
             sample=三站各采一次; summary=聚合表; tail=原始样本; path=日志落点。
             口径: **引擎耗时口径**(ΣΔtoken/ΣΔ引擎耗时, 与 API timings 可比)为主, 墙钟口径为辅。
             采样是**按需**的 (不做常驻采样服务); /metrics 无 requests 计数器, 故不给"请求数"。
    ttl      空闲 TTL 自动卸载 (P2-5, **默认关**): 站上 `cluster-ttl` 每 60s 判一次引擎是否已空闲
             ≥ 阈值, 到期执行 `infer-unload` (会一并停掉全部 RPC worker)。空闲判据是 /metrics
             累计计数器的**差分** (llama.cpp 没有"最后请求时间"), 在途请求 >0 视为活跃。
             status=三站状态; check=立刻判一次 (默认只演练, --go 才真卸); enable/disable=写 conf + 开关 timer。
             与"零自加载"方针并存 —— TTL 只释放已加载资源, 从不加载任何模型。
    agent    agent 任务进度/吞吐 (P0, 只读; 见 spec/agent-observability/ 调研):
             runs=派发台账尾 N 条(join <projRoot>/agent-out/<ts>/.agent-run.json 详情);
             live=扫三站 $HOME/agent-workspaces/*/out/.progress[.<ts>] (运行中节拍: 末行 t=end ⇒ finished);
             tail=台账原始行。**不新增采集器**, 只读站上既有文件。
             ⚠ 口径: 产出列是 **agent 产出字节口径** (output_bytes / B/s), **不是 token** ——
             与 reqlog 的引擎耗时口径 t/s、API timings 互不可比; 无头 run 不吐 usage ⇒ 不做换算;
             ETA 需目标量而运行中不可得 ⇒ 一律 `NA` (不打荒数字)。
    web      傻瓜式推理框架管理 Web UI (按需服务, 见 ops/cluster_web.py; 浏览器点按钮加载/切后端/卸载;
             管理页含「受理区」卡片: 跨项目进度 + 待办聚合, 15s 自动刷新)
    inbox    受理区跨项目进度 (只读, ADR-0008): 读 inbox/<proj>-<date>/40_state/STATE.json,
             列出每笔的 state + updated_at。合法状态白名单/自洽性由门禁 `rpc_check.py --only inbox` 判定。
    containers 容器栈纳管 (ADR-0012 D2 / ADR-0014 D2): status=三站 docker ps -a / images / compose ls
             + 端口对账(容器声明面 vs inventory/ports.yaml), **只读, 恒 exit 0**, 空集**显式报「无容器」**;
             install=容器栈供应 (**默认只出计划, --go 才动手**; ADR-0014 D8(a)) —— 给站上补 **dockerd**
             (B/C 实测**有 CLI、无 daemon**): 启用 docker apt 源(修 dist-upgrade 改名) + 装
             docker-ce/containerd + `systemctl enable --now docker` + 把 ssh 用户加进 docker 组;
             **幂等**(已有 dockerd ⇒ 跳过), 与 A 站配置对齐。默认跑三站(A 站自跳过);
             pull/up/down=写动作 (**默认只出计划, --go 才动手**), 走唯一建连层 ssh_run(strict=True)
             —— 不新增并列脚本 (ADR-0004 D2)。`up` 的 flag 集照抄上游部署配方:
             `--device /dev/kfd /dev/dri` · `--group-add video render` · `--ipc=host`(★ load-bearing,
             上游明文"no `shm_size` substitutes" ⇒ 本仓**不提供** `--shm-size`) · `--ulimit memlock=-1:-1`
             · `-v <models>:/models:ro` · `-e HALOGEN_CHECKPOINT=...`。⚠ 站上监听占用对账权威仍是 `rpc_check --only ports`。

退出码:
    0 成功 / 1 失败 / 2 RPC 类需手动

设计: spec/d2-cluster-cli/ (RESEARCH/IMPLEMENTATION/CHECKLIST)
依赖: paramiko (主控站 hermes venv Python 3.11 已装)
      C:\\Users\\Peng\\.hermes\\hermes-agent\\venv\\Scripts\\python.exe
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
    HTML_OUT, SSH_TIMEOUT, PANELS, SERVICE_USER, REPO_ROOT,
)


# ── SSH 层 + 探测层 (已抽至 cluster_ssh.py, 阶段 1b 拆分) ──────────────
# 显式重导出 ⇒ 站内多处调用点 (`cli = _connect(...)` / `ssh_stream(...)`) 与外部
# (cluster_web.py 的 cluster.ssh_run) 均不变。实现改 ops/cluster_ssh.py。
from cluster_ssh import (  # noqa: E402
    _connect, ssh_run, ssh_stream, probe_station, resolve_host,
)

# ── ops 域（2026-10-28 拆分；重导出 ⇒ 外部 `cluster.*` 调用点不变）──────
from cluster_ops import (  # noqa: E402
    INBOX_ROOT, INBOX_U1_NS, INBOX_U1_VER, PORTS_YAML, TTL_BIN, TTL_CONF, TTL_DEFAULT_S, TTL_TIMER, _DOCKER_DAEMON_JSON, _INBOX_YAML, _MANIFEST_LINE_RE, _PROBE_CMD, _containers_status, _inbox_seal, _inbox_truth, _ports_yaml, _ttl_parallel, _ttl_probe, _ttl_row, _u1_decl_line, _u1_identity, cmd_containers, cmd_inbox, cmd_ttl, containers_install_cmd, containers_port_audit, docker_published_ports, format_containers_station, parse_containers_probe, parse_docker_images, parse_docker_ps, parse_manifest, parse_u1_track, registered_host_ports, verify_manifest,
)

# ── agent 域（2026-10-28 拆分；重导出 ⇒ 外部 `cluster.*` 调用点不变）──────
from cluster_agent import (  # noqa: E402
    AGENT_AUDIT_BASELINE, AGENT_AUDIT_BASELINE_DIR, AGENT_AUDIT_JUDGE_RULE, AGENT_AUDIT_JUDGE_RULE_B, AGENT_BEAT_STALE_S, AGENT_CHAIN, AGENT_CHAIN_ANCHOR, AGENT_CHAIN_COLD, AGENT_DIFF_ALLOW_PREFIXES, AGENT_DIGEST_RECIPE, AGENT_DIGEST_RECIPES, AGENT_EVIDENCE_FILES, AGENT_LEDGER, AGENT_MANIFEST_REQUIRED, AGENT_STATUS_BY_CODE, AGENT_WS, FRAMEWORK_SUBJECTS_VERSION, _FWVER_SCOPE, _GOLDEN_INDEX, _VERDICT_RC_MAP, _agent_beat, _agent_detail, _agent_ledger_rows, _agent_proj_roots, _anchor_check, _anchor_write, _audit_host, _audit_judge_items, _audit_judge_stable_items, _card_accept_list, _chain_load, _chain_runs, _dashboard_html, _diff_scope_check, _excl_lock, _fwver_set, _gap_key, _golden_identity_check, _golden_index, _human_age, _judge_calib_digest, _judge_call, _judge_identity, _meta_parse, _p2_committed_chain_assert, _p3_pin_notes, _p4_mirror, _p4_mkdir, _p4_run_mirror, _p4_writable, _parse_verdicts, _run_digest, _sha256_file, _sha_lf, _sha_lf_file, _tri, _verdict_allowed, _verdict_check, agent_audit, agent_audit_baseline_accept, agent_audit_baseline_load, agent_audit_calib_status, agent_audit_judge, agent_chain_append, agent_chain_verify, agent_ledger_freshness, agent_live, agent_runs, calib_status_line, cmd_agent, cmd_agent_dashboard, compare_accept_cmds,
)

# ── flow 域（2026-10-28 拆分；重导出 ⇒ 外部 `cluster.*` 调用点不变）──────
from cluster_flow import (  # noqa: E402
    FLOWS, FLOW_SECTION, FLOW_TABLE_HEAD, LEDGERS, _SU_HOME, _SU_INDEX, _SU_PY, _SU_SHIM, _SU_SP, _flow_bench_payload, _flow_find_engine, _flow_ledger_step, _flow_path_measure, _flow_paths_report, _flow_paths_run_rpc, _flow_paths_run_single, _flow_paths_single, _flow_rotate_push, _flow_rotate_scan, _flow_rotate_status, _flow_step_bench, _flow_step_ensure_loaded, _flow_step_probe_engine, _flow_step_su_apply, _flow_step_su_gate, _flow_step_su_precheck, _flow_step_su_verify, _flow_swap_apply, _flow_swap_precheck, _flow_swap_ready, _flow_teardown_bench, _flow_usage, _flow_verify_checks, _ledger_append, _reqlog_aggregate, _reqlog_station, _station_gtt_gib, cmd_e2e, cmd_flow, cmd_reqlog, resolve_host_alias,
)

# ── runtime 域（2026-10-28 拆分；重导出 ⇒ 外部 `cluster.*` 调用点不变）──────
from cluster_runtime import (  # noqa: E402
    AliasError, FRAME_CMD, RPC_WORKER_STATIONS, _ENGINE_CHARS, _KV_BPE, _METRICS_CMD, _active_rpc_workers, _build_infer_load_cmd, _capacity_ok, _cmd_load_c, _conf_rpc_target, _container_cleanup_cmd, _engine_ok, _fallback_conf, _frame_status, _guard_capacity, _guard_worker_conflict, _host_path_for, _load_container_model, _load_ds4_pp, _load_rpc, _parse_conf, _planes_compact, _pp_listen_ip, _probe_map, _reclaim_containers, _station_mem, _worker_conflict, classify_container_assets, classify_worker_probe, cmd_estimate, cmd_frames, cmd_load, cmd_load_on, cmd_status, cmd_unload, cmd_unload_on, collect_frames, collect_status, containers_plan, estimate_load, parse_worker_busy, preflight_container, probe_frames, probe_metrics, probe_worker_state, reclaim_and_unload, render_html, resolve_alias, resolve_rpc_worker, sh_single_quote,
)

# ── catalog 域（2026-10-28 拆分；重导出 ⇒ 外部 `cluster.*` 调用点不变）──────
from cluster_catalog import (  # noqa: E402
    LM_DL_TASKS, LM_DL_UNIT, LM_DL_UNIT_FILE, _MODELS_SCAN, _STUDIO_SCAN, _VER_SCAN, _cmd_models_fetch, _cmd_models_meta, _fetch_plan, _link_model, _prune_link, _scan_models, cmd_models, cmd_studio, cmd_versions, probe_studio, probe_versions,
)

# ── model 层重导出（★ 这张表原先住在 catalog 段内，随段搬走 ⇒ 门禁 `facade` 当场报
#    `alias_of / group_by_model / infer_quant / parse_model_meta` 不可达（tests/test_cluster_pure.py 取用）。
#    ⇒ 门面**保留同一份** import（下层模块，允许）。改这里的清单前先看 `facade` 的消费者清单。）
from cluster_model import (  # noqa: E402
    _MODEL_META_SCAN, _QUANT_RE, INVENTORY_MODELS, MODELS_ROOT,
    alias_of, group_by_model, infer_quant, ledger_quant, parse_model_meta,
    pick_representative, probe_model_meta, resolve_quant,
)

# ── 控制台宽度工具（`_dw` / `_pad` 原先在 agent 段内 import，随段搬走 ⇒ 门面补回）
from cluster_console import disp_width as _dw  # noqa: E402
from cluster_console import pad as _pad        # noqa: E402


# ── 凭据平面 (secrets / providers) 已抽至 cluster_secrets.py (阶段 2a 拆分) ──────────
# 显式重导出 ⇒ cluster.py 内部调用点与 cluster_web.py 用到的
# probe_secrets / _secrets_verdict / probe_providers 均不变。实现改 ops/cluster_secrets.py。
from cluster_secrets import (  # noqa: E402
    CLD_CONF, KEY_PAT, MASK_SED, OPC_CONF, PROVIDERS_PROBE, RPC_DIR, SECRETS_PROBE,
    SECRETS_ROOT, STATION_MINTED, _api_key_form, _claude_forms, _ep_form,
    _master_minted_fp, _remote_secret, _secrets_pull, _secrets_push,
    _secrets_verdict, cmd_providers, cmd_secrets, probe_providers, probe_secrets,
)


# ── 出站域 (出站平面 + OR 免费档计数 + 额度借用) 已抽至 cluster_egress.py (阶段 2b) ──
# 显式重导出 ⇒ cluster.py 内 cmd_egress/cmd_egress_borrow 分发与 cluster_web.py 用到的
# probe_egress_station 均不变。实现改 ops/cluster_egress.py。
from cluster_egress import (  # noqa: E402
    EGRESS_SEP, EGRESS_STATION_FILE, EGRESS_URL, FREE_ALERT_RATIO, FREE_QUOTA_FREE,
    OR_BORROW_AT, OR_BORROW_FILE, OR_POOL_DIR,
    # ★ 2026-10-20 R1 裁【丙】（用户令「继续执行 R1 实施面，清理旧件四件」）：
    #   旧的主控侧单计数器四件 —— `EGRESS_DAILY_FILE` / `_egress_daily` / `_egress_bump` / `_egress_save`
    #   —— **已随该件一并删除** ⇒ **不再重导出**（本地计数面单件承载 = 派发侧 `ops/.egress_station.json`）。
    #   ⚠ 门禁 `facade` 会让"消费者引用了不存在的门面名"当场变红 ⇒ 这里删与实现删必须同步。
    _egress_cmd, _egress_probe_all, _egress_station_today, _free_quota,
    # R4 裁【甲】(2026-10-20): 免费档日限额的**主口径**（直读服务端 `free_limit` + 兜底如实）
    #   —— ★ 必须一并重导出：门禁 `facade` 判「消费者引用的符号必须在门面可达名里」
    #     （`tests/test_cluster_pure.py` 的新用例直接引用它）⇒ 漏了会当场 FAIL。
    _free_quota_effective,
    _mask_key, _or_info, _or_line, _or_master_key_file, _or_own_key_file, _or_pct,
    _or_read_key, _or_state, _or_state_save, _parse_egress, cmd_egress,
    cmd_egress_borrow, probe_egress_master, probe_egress_station,
)


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
        rest, backend, engine, worker, force, keep, i = [], None, None, None, False, False, 0
        while i < len(tail):
            if tail[i] == "--backend" and i + 1 < len(tail):
                backend = tail[i + 1]   # 提取值并跳过, 避免污染 alias 前缀
                i += 2
                continue
            if tail[i] == "--engine" and i + 1 < len(tail):
                engine = tail[i + 1]    # 引擎变体: 名 -> /opt/llama.cpp-<名>/; 或绝对路径
                i += 2
                continue
            if tail[i] == "--worker" and i + 1 < len(tail):
                worker = tail[i + 1]    # 单 worker 指派 (A|C); head 固定权重站 B
                i += 2
                continue
            if tail[i] == "--force":     # O-178: 越过"反向冲突"预检（目标站在给别人当 worker）
                force = True
                i += 1
                continue
            if tail[i] == "--keep":      # O-179: 允许同站叠加（alias 级回收 + 容量门）
                keep = True
                i += 1
                continue
            rest.append(tail[i])
            i += 1
        if not rest:
            print("用法: cluster.py load <alias前缀> [--backend unsloth|llama-rpc|llama-single|vllm|ds4] "
                  "[--engine <变体名|绝对路径>] [--worker A|C] [--force] [--keep]")
            return 1
        return cmd_load(" ".join(rest), backend, engine, worker, force, keep)
    if sub == "frames":
        return cmd_frames()
    if sub == "unload":
        tail, alias, only = args[1:], None, None
        i = 0
        while i < len(tail):
            if tail[i] == "--alias" and i + 1 < len(tail):
                alias = tail[i + 1]
                i += 2
                continue
            if tail[i] == "--station" and i + 1 < len(tail):
                only = tail[i + 1]
                i += 2
                continue
            print(f"[cluster] unload 不认识的参数 '{tail[i]}' "
                  f"(用法: unload [--alias <别名>] [--station A|B|C]) (exit 1)")
            return 1
        if only:
            return cmd_unload_on(only, alias)
        return cmd_unload(alias)
    if sub == "estimate":
        return cmd_estimate(args[1:])
    if sub == "models":
        return cmd_models(args[1:])
    if sub == "versions":
        return cmd_versions(args[1:])
    if sub == "studio":
        return cmd_studio(args[1:])
    if sub == "flow":
        return cmd_flow(args[1:])
    if sub == "reqlog":
        return cmd_reqlog(args[1:])
    if sub == "ttl":
        return cmd_ttl(args[1:])
    if sub == "agent":
        return cmd_agent(args[1:])
    if sub == "inbox":
        return cmd_inbox(args[1:])
    if sub == "containers":
        return cmd_containers(args[1:])
    if sub == "e2e":
        return cmd_e2e()
    if sub == "secrets":
        return cmd_secrets(args[1] if len(args) > 1 else "status", args[2:])
    if sub == "providers":
        return cmd_providers()
    if sub == "egress":
        # 2026-09-21: `egress borrow ...` = 额度借用/归还(**默认只出计划, --go 才动手**)
        if len(args) > 1 and args[1] == "borrow":
            return cmd_egress_borrow(args[2:])
        return cmd_egress()
    if sub == "web":
        import cluster_web
        return cluster_web.serve(args[1:])
    print(f"未知子命令: {sub}\n{__doc__}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
