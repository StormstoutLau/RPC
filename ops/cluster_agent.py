#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cluster_agent — `cluster.py` 的按域拆分模块（review-p2-cluster 阶段）。

为什么存在：评审 #8「核心文件过大」。本模块由 `tmp/_split_cluster.py` 按 `# ──` 段
整段搬运（行为不变），`cluster.py` 只做重导出与 CLI 分派。
⚠ 跨组调用只允许**向下**（层序见 `inventory/ops.yaml` 的 `cluster_layers`）。
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

from cluster_console import (  # noqa: E402
    pad as _pad,
)
from cluster_flow import (  # noqa: E402
    _flow_find_engine,
)

# ── P0: agent 任务进度/吞吐只读视图 (2026-09-15, 调研 spec/agent-observability/) ──
# **一个采集器都不新增**: 三个数据源全是 O-25 已建的 ——
#   ① 主控派发台账 ops/station-bin/agent-runs.log (ts,proj,model,sens,code,queue_s,run_s)
#      ⚠ **model 列的语义 = "实际执行身份"**(2026-09-22 订正, 只改语义不改 schema):
#          · 站上 claude 分支 ⇒ `station:<站>/<别名>`(如 `station:B/main` —— 实际跑的是**站上本地引擎**)
#          · 其余 ⇒ 路由/别名指向的型号 id(那时它**就是**真值)
#        为什么钉一句: 原先站上分支写的是路由 id ⇒ 对一个 `local-only`("物理不出网")的 run
#        会**报一个云端型号**(实测 `thinkingmachines/inkling:free`) ⇒ 而"按 model 列判该 run 是否
#        出网"是个**看起来能用**的判据 ⇒ 会读出假警报(同族的反向错误会**掩盖真出网**)。
#        ⇒ **判"是否出网"请看 `local-only` + `station:` 前缀, 别把 model 当云端型号去匹配。**
#   ② 主控 run 详情 <projRoot>/agent-out/<ts>/.agent-run.json (status/run_s/output_bps/slot/profile/accept)
#   ③ 站上运行中节拍 $HOME/agent-workspaces/<proj>/out/.progress[.<ts>] (5s 一行 t=.. bytes=.. bytes_s=.., 终值 t=end)
#
# ⚠ 口径 (调研 §3 的关键结论, 别混):
#   · 本视图的"产出"列是 **agent 产出字节口径** (output_bytes / output_bps) —— **不是 token**,
#     与 reqlog 的"引擎耗时口径 t/s"、API timings 三者互不可比, 故分列显示、列头写明口径。
#   · 上游无头 run 不吐 usage (run.json 里 usage.total_tokens 实测恒 0) ⇒ **不做字节→token 换算**。
#   · ETA 需要"目标产出量", 而 max_output 只在 run 结束的 run.json 里 ⇒ 运行中**没有目标**,
#     一律打 `NA` —— 不打荒数字 (O-25 no-bench 纪律)。
# 字段命名对齐社区标准 (只为将来接 trace 后端不返工, 不引入依赖):
#   run ≈ OTel GenAI `invoke_agent` span · 状态 ≈ A2A TaskState (我们原本缺 `working`, 由 live 补上)
AGENT_LEDGER = Path(__file__).resolve().parent / "station-bin" / "agent-runs.log"
AGENT_WS = "$HOME/agent-workspaces"
AGENT_BEAT_STALE_S = 60          # 节拍 5s 一次; 超 60s 未更新 ⇒ 疑似卡死 (O-25 的"黑盒"信号)
AGENT_STATUS_BY_CODE = {0: "completed", 6: "timeout", 24: "slot-rejected"}

# ── 证据链 (2026-09-17, spec/d6-agent-standard/evidence-chain/DESIGN.md) ──
# 目的: 把"归档证据事后被无痕改动"变成"断链在首个 diff 处可定位"。
# **不是防篡改**: 不防 T3 (执行站+主控全泄露), 不防"提前不记录", 不证 judgement 级真伪。
# 语义: `prev` 链接的是**入链顺序** (append-only 日志序), 不是 ts 序 —— 扫描补录时
#   按 ts 排候选, 但插入次序即链接次序; 故 ts 交错的并发派发不会破坏链。
AGENT_CHAIN = Path(__file__).resolve().parent / "station-bin" / "agent-chain.json"
# 冷路径 (外置链头): 与链文件异目录, 两者不一致即"链被全量回改"。注意**非跨机**,
#   真正的跨信任域锚需人工/外部介质固化 —— 见 DESIGN §3 诚实边界。
AGENT_CHAIN_COLD = Path(__file__).resolve().parent.parent / "archive" / "evidence-chain" / "agent-chain.json"
# 外部锚 (2026-09-17 遗留#3): 一页纯文本, 钉住**链文件字节** ⇒ 与链形成两级:
#   ANCHOR 钉链文件 → 链钉归档证据。理由: 链文件本身若被整体重写, 单看链自洽;
#   锚把它压成一个可提交/可推送的短指纹, 由 **git origin (GitHub)** 充当跨信任域见证。
#   ⚠ 强度诚实: 需 `git push` 到 origin 才成立; 持推送凭据者可改写 ⇒ 仅"公开仓库/多副本见证"级,
#   不是密码学不可否认 (见 evidence-chain/DESIGN.md §3)。
AGENT_CHAIN_ANCHOR = AGENT_CHAIN_COLD.parent / "ANCHOR.txt"
# recipe 版本 —— **按条目分派**，不是全局单值 (2026-09-18, ADR-0007 阶段 1 架构半):
#   每条链目自带 `recipe`; 复验器**按该条目的 recipe** 重算 digest ⇒ 新增 recipe(如把
#   `workspace-diff` 等新证据纳入) **不会**让历史条目误判断链 ⇒ **无需重建链(重新基线化)**。
#   这是缺口 4 的前置: 原设计"加件即 bump 全局 recipe"会强制作废全部历史并重新基线化
#   (等于把当时字节洗白, 丢掉此前篡改的可检测性) —— 故先做按条目分派。
#   新增 recipe 的纪律: ① 入 `AGENT_DIGEST_RECIPES` 才可被复验; ② 未知 recipe = **不可验**
#   ⇒ 报 recipe_unknown 且 FAIL (不得静默跳过 —— 那会让"工具比链旧"变成静默通过)。
AGENT_DIGEST_RECIPE = "v1"
AGENT_DIGEST_RECIPES = ("v1", "v2")   # v2 = 件集由 run.json 的 evidence_manifest.subjects 声明 (ADR-0007 阶段 1)
# 入 digest 的回收件 (与 agent-cli.ps1 collect 段 Move 后的名字一致):
#   · .agent-run.json    = 主控写的终态契约 (含 accept_golden.sha256 ⇒ "当次注入的是哪份 golden")
#   · judgment-record.txt= 远端 .meta (builder 自述) —— **入链不等于可信**, 只保证"回收后未被改"
#   说明: DESIGN §2.2 曾把"goldenSha 只在内存、无法异地重算"列为关键实现坑; ADR-0005 已把它
#   落进 .agent-run.json, 故此处**只哈希该文件字节**即覆盖之 —— 不另抽 golden_sha 字段,
#   避免同一事实两个定义点 (抽出来也永远与文件哈希同涨同落, 是冗余)。
AGENT_EVIDENCE_FILES = (".agent-run.json", "judgment-record.txt", "agent-output.txt",
                        "accept-output.txt", "accept-golden-output.txt", "prompt.txt")
# v2 的"必须声明"集 = 已知证据件去掉 `.agent-run.json`(它是声明载体本身, 卡不该声明它)。
#   判据见 agent_chain_verify 的 manifest_undeclared (ADR-0007 阶段1「未声明产物出现即失败」)。
AGENT_MANIFEST_REQUIRED = tuple(f for f in AGENT_EVIDENCE_FILES if f != ".agent-run.json")


# D6-P3-1: 显示宽度 / 填充**下沉到 L0 共用件** `cluster_console`（见其模块注释 —— 为什么不能留在这里：
#   `cluster_secrets`(L2) / `cluster_egress`(L3) 也要用，从 L4 取是**反向 import** ⇒ 门禁 `deps` 会 FAIL）。
# **保留同名 alias** ⇒ 本文件内既有调用点**零改动**。
from cluster_console import disp_width as _dw       # noqa: E402
from cluster_console import pad as _pad             # noqa: E402


def _human_age(sec) -> str:
    """秒 → 人读时长。freshness 列必须一眼看出"这是多久以前"。"""
    try:
        sec = float(sec)
    except (TypeError, ValueError):
        return "-"
    if sec < 90:
        return f"{sec:.0f}s"
    if sec < 5400:
        return f"{sec / 60:.1f}m"
    if sec < 172800:
        return f"{sec / 3600:.1f}h"
    return f"{sec / 86400:.1f}d"


def _agent_proj_roots() -> tuple:
    """读项目注册表 → (proj→root, note)。

    **为什么不在这里再抄一份映射**: proj→root 的真值在 `inventory/projects.yaml`
    （判据侧 `rpc_check.projects_index`, 只收 active）。抄一份就是第二个定义点, 项目增删时必然漂移
    (P1-6"取 conf 而非抄台账"同一条理由)。解析失败**显式降级**, 不猜。
    ⚠ 2026-10-13 `$PROJECTS` 数据化: 旧实现是正则解析 `agent-cli.ps1` 的 `$Script:PROJECTS`
      字面量 —— 该表已改为**注册表载入**（字面量收干净）⇒ 静态解析只会读到空表。
      ⇒ 改走**同一真值源**（复用 `rpc_check` 的纯函数, 不第二次解析 YAML 语义）。
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import rpc_check
    except Exception as e:
        return {}, f"无法导入 rpc_check ({type(e).__name__}) — 详情列将不可用"
    try:
        import yaml
        reg = yaml.safe_load(rpc_check.PROJECTS_REG.read_text(encoding="utf-8")) or {}
    except OSError as e:
        return {}, f"读不到 inventory/projects.yaml ({e.__class__.__name__})"
    except Exception as e:
        return {}, f"projects.yaml 解析失败 ({type(e).__name__}): {e}"
    roots = {}
    for pid, root in rpc_check.projects_index(reg).items():
        roots[pid] = Path(root)
    if not roots:
        return {}, "项目注册表无 active 项 (详情列将不可用)"
    return roots, ""


def _agent_ledger_rows(limit: int) -> list:
    """读派发台账尾部 N 条。跳过标题行 (判据与 make-dashboard 一致: 必须 `^\\d{14,},`)。"""
    try:
        lines = AGENT_LEDGER.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return []
    rows = []
    for ln in lines:
        ln = ln.strip()
        if not re.match(r"^\d{14,},", ln):      # 台账首行是 "RPC_LEDGER_TEST 2026-09-06" 之类的标题
            continue
        f = ln.split(",")
        if len(f) < 7:
            continue
        ts, proj, model, sens, code, qs, rs = (x.strip() for x in f[:7])
        try:
            label = time.strftime("%m-%d %H:%M:%S",
                                  time.strptime(ts[:14], "%Y%m%d%H%M%S"))
        except Exception:
            label = ts[:14]
        try:
            code_i = int(code)
        except ValueError:
            code_i = None
        rows.append({"ts": ts, "label": label, "proj": proj, "model": model, "sens": sens,
                     "code": code_i, "queue_s": int(qs or 0), "run_s": int(rs or 0),
                     "status": AGENT_STATUS_BY_CODE.get(code_i, "failed" if code_i is not None else "?")})
    return rows[-limit:] if limit else rows


def _agent_detail(roots: dict, proj: str, ts: str) -> dict:
    """读该 run 的 .agent-run.json (终态快照)。缺文件返回 {} —— 老 run 无详情属正常。"""
    root = roots.get(proj)
    if not root:
        return {}
    p = root / "agent-out" / ts / ".agent-run.json"
    try:
        j = json.loads(p.read_text(encoding="utf-8-sig", errors="replace"))
    except Exception:
        return {}
    if not isinstance(j, dict):
        return {}
    return {"status": j.get("status"), "exit_code": j.get("exit_code"),
            "cli": j.get("cli"), "model": j.get("model"),
            "run_s": j.get("run_s"), "queue_s": j.get("queue_s"),
            "output_bytes": j.get("output_bytes"), "output_bps": j.get("output_bps"),
            "slot": j.get("slot"), "profile": j.get("profile"),
            "accept": (j.get("accept") or {}).get("passed"),
            "collect": j.get("collect"),
            "usage_total_tokens": (j.get("usage") or {}).get("total_tokens")}


# ── 证据链: 计算 / 追加 / 复验 (全部**主控侧只读站外**, 不碰任何站) ──

def _sha256_file(p: Path) -> str:
    """文件**字节** sha256 (二进制读 —— Windows 下 text 模式会把 \\n 翻成 \\r\\n, 哈希即错)。"""
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha_lf(b: bytes) -> str:
    """sha256 of **LF 规范**字节 (CRLF→LF)。锚的 chain/cold_sha 用它。

    2026-09-21 P2: 实测 `core.autocrlf=true` ⇒ 工作树 JSON 是 **CRLF**, 而 git 仓库存 **LF** blob;
    锚若按盘面原始字节哈希, 就会钉住"本机工作树编码", 与"提交/克隆下来的字节"不符 ⇒
    off-machine 副本与锚对不上(P2 的正向自证正是踩到这条: 同文件 `git show :`=704cd0b7 vs 盘面=b34a3f)。
    全链条统一用 LF 规范哈希, "入仓链 == 锚"才真正生效 —— 且与工作树编码(CRLF or LF)无关。
    """
    return hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()


def _sha_lf_file(p: Path) -> str:
    return _sha_lf(p.read_bytes())


def _run_digest(run_dir: Path, recipe: str = AGENT_DIGEST_RECIPE):
    """按 `recipe` 算 run_digest —— 纯本地重算, 不触站。未知 recipe 返回 None (**不可验**)。

    recipe v1: sha256( "v1\\n" + 逐件 "name:hex|-\\n" )   ← 固定 6 件(AGENT_EVIDENCE_FILES)
    缺件记 `-`: 老 run / collect 部分失败属正常, **不等于篡改** (故不能拿"缺件"当告警)。
    新 recipe 应在此分派, 并登记进 AGENT_DIGEST_RECIPES; **条目各按自己的 recipe 复验**。
    ⚠⚠ **副作用（O-29；2026-09-23 引入，2026-09-26 显式登记）**：v2 分支会 `_fwver_set(...)` 设**全局**
      `_FWVER_SCOPE`（供 `_gap_key` 分桶）⇒ **审计侧依赖「每个 run 都从本函数过一遍」这一【隐性契约】**。
      ⇒ 若将来为性能给本函数加**缓存 / 短路**，`_FWVER_SCOPE` 会**残留上一个 run 的值** ⇒ **静默错桶** ——
      而分桶是**报告层**的：错了**不报错、只是数字不对**（本仓最防的那一类）。
      ⇒ **要短路就必须同时**在调用点显式设框架代（把隐式副作用改成**显式参数**）。
    """
    if recipe not in AGENT_DIGEST_RECIPES:
        return None
    if recipe == "v2":
        # v2 (ADR-0007 阶段 1): 件集 = run.json 的 evidence_manifest.subjects (**按 run 声明**)。
        #   ⇒ 新增证据类型不必动全局 recipe, 历史条目(自带 v1)**不受影响** ⇒ 无需重建链。
        #   `.agent-run.json` **恒入集**(它是声明载体本身, 也要被钉住);
        #   `collect` 型 subject 尚无采集物(缺口 4) ⇒ 记 `-`, 不当篡改。
        try:
            j = json.loads((run_dir / ".agent-run.json").read_text(encoding="utf-8-sig", errors="replace"))
        except Exception:
            return None
        subs = ((j.get("evidence_manifest") or {}).get("subjects")) or []
        # 2026-09-23 (O-29): 设本 run 的**框架代**供 `_gap_key` 分桶 —— 缺字段 ⇒ 空串 ⇒ key 退回旧形状。
        _fwver_set((j.get("evidence_manifest") or {}).get("framework_version"))
        if not subs:
            return None                       # 声明了 v2 却无 subjects ⇒ 不可验(调用方报 manifest_missing)
        lines, files = [], {}
        for nm in (".agent-run.json",):
            hx = _sha256_file(run_dir / nm) if (run_dir / nm).is_file() else "-"
            files[nm] = hx
            lines.append(f"{nm}:{hx}")
        for s in subs:
            name = str(s.get("name") or "").strip() or "?"
            path = str(s.get("path") or "").strip()
            # collect 型 subject 无 path ⇒ 按**约定名** `<name>.txt` 找归档件(缺口 4: 远端采集的
            #   `workspace-diff` 由 console 归档为 `workspace-diff.txt`)。否则该件不被链钉住。
            if not path and str(s.get("collect") or "").strip():
                path = f"{name}.txt"
            tgt = (run_dir / path) if path else None
            hx = _sha256_file(tgt) if (tgt is not None and tgt.is_file()) else "-"
            files[name] = hx
            lines.append(f"{name}:{hx}")
        blob = (recipe + "\n" + "\n".join(lines) + "\n").encode("utf-8")
        return {"digest": hashlib.sha256(blob).hexdigest(), "files": files}
    lines, files = [], {}
    for name in AGENT_EVIDENCE_FILES:
        p = run_dir / name
        hx = _sha256_file(p) if p.is_file() else "-"
        files[name] = hx
        lines.append(f"{name}:{hx}")
    blob = (recipe + "\n" + "\n".join(lines) + "\n").encode("utf-8")
    return {"digest": hashlib.sha256(blob).hexdigest(), "files": files}


def _chain_load(p: Path) -> dict:
    """读链 (缺文件/坏文件一律返回空链骨架 —— 不抛, 让调用方按"空"处理)。"""
    try:
        j = json.loads(p.read_text(encoding="utf-8-sig", errors="replace"))
        if isinstance(j, dict) and isinstance(j.get("entries"), list):
            j.setdefault("version", 1)
            j.setdefault("recipe", AGENT_DIGEST_RECIPE)
            return j
    except Exception:
        pass
    return {"version": 1, "recipe": AGENT_DIGEST_RECIPE, "entries": []}


def _chain_runs(roots: dict) -> list:
    """扫全部 proj 的 agent-out/*/ → [(ts, proj, run_dir)], 按 (ts, proj) 稳定排序。"""
    out = []
    for proj, root in sorted(roots.items()):
        d = root / "agent-out"
        if not d.is_dir():
            continue
        for sub in d.iterdir():
            if sub.is_dir() and (sub / ".agent-run.json").is_file():
                out.append((sub.name, proj, sub))
    out.sort(key=lambda x: (x[0], x[1]))
    return out


def _anchor_write(chain: dict) -> None:
    """把链状态压成**外部锚** (纯文本, 一页, 可提交/推送)。

    锚钉的是**链文件字节** (chain_sha256) ⇒ 链被整体重写也会露馅; 链本身钉归档证据 ⇒ 两级。
    """
    head = chain.get("head") or {}
    lines = [
        "# agent 证据链外部锚 — 由 `cluster.py agent chain` 生成, 请勿手改",
        "# 用途: 提交并 push 到 git origin ⇒ 链被整体重写时此锚不符 (跨信任域见证)",
        "# 校验: python ops/cluster.py agent verify    (判据 kind=anchor_mismatch)",
        "# ⚠ 强度诚实: 仅当已 push 且历史被他人见证时成立; 持推送凭据者可改写 — 非密码学不可否认",
        f"entries={len(chain['entries'])}",
        f"head_run={(head.get('proj') + '/' + head.get('run_id')) if head else '-'}",
        f"head_digest={head.get('digest') or '-'}",
        f"chain_sha256={_sha_lf_file(AGENT_CHAIN)}",
        f"cold_sha256={_sha_lf_file(AGENT_CHAIN_COLD) if AGENT_CHAIN_COLD.is_file() else '-'}",
        f"recipe={AGENT_DIGEST_RECIPE}",
        f"generated_at={time.strftime('%Y-%m-%dT%H:%M:%S')}",
    ]
    AGENT_CHAIN_ANCHOR.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _anchor_check(chain: dict) -> list:
    """比对外部锚。**缺锚返回空** (未建锚≠篡改, 由 verify 另行提示建锚)。"""
    if not AGENT_CHAIN_ANCHOR.is_file():
        return []
    got = {}
    try:
        for ln in AGENT_CHAIN_ANCHOR.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in ln and not ln.lstrip().startswith("#"):
                k, v = ln.split("=", 1)
                got[k.strip()] = v.strip()
    except OSError:
        return [{"kind": "anchor_unreadable"}]
    head = chain.get("head") or {}
    cold_sha = _sha_lf_file(AGENT_CHAIN_COLD) if AGENT_CHAIN_COLD.is_file() else "-"
    diff = []
    if got.get("entries") != str(len(chain["entries"])):
        diff.append(f"条数(锚={got.get('entries')} 链={len(chain['entries'])})")
    if got.get("head_digest") != (head.get("digest") or "-"):
        diff.append("head_digest")
    if got.get("chain_sha256") != _sha_lf_file(AGENT_CHAIN):
        diff.append("chain_sha256(链文件字节已变)")
    if got.get("cold_sha256") != cold_sha:
        diff.append("cold_sha256(冷路径字节已变)")
    if got.get("recipe") not in (None, AGENT_DIGEST_RECIPE):
        diff.append(f"recipe(锚={got.get('recipe')})")
    return [{"kind": "anchor_mismatch", "diff": diff}] if diff else []


# ── 批 A 判据 (2026-09-17, ADR-0007 D4 三层严重度) ──
#   A1 verdict-chain   : judgment-record.txt(.meta) ↔ .agent-run.json 逐项一致
#   A2 golden-identity : run.json.accept_golden.base/sha256 ↔ 仓库 golden 源
# 分层纪律 (ADR-0007 D4): 篡改/损坏 ⇒ issues(FAIL) ; 覆盖缺口 ⇒ gaps(WARN) ; 合法演进 ⇒ notes(info)
#   **判据必须从代码语义推导, 不能凭想象** —— 下面两处映射/容忍均来自实测:
#
# ① TASK_RC → run.json `exit_code` 的**允许集**。依据 [agent-cli.ps1:1200-1201]:
#      `$codeReal = $code; if ($code -eq 9) { $code = 1 }` ⇒ 远端 9(**验收/金标准失败**)
#      在 run.json 里被映射成 1, **原始 9 只留在 .meta** —— 这正是 ADR-0005 归档它的价值
#      (`$codeReal` 赋值后全仓无引用 = 事实上的死变量 ⇒ 原始码从 run.json 侧**不可恢复**)。
#      9 允许 {1,9}: 兼容 claude 备路是否做同一映射的未定情形 —— **宁少报不误报**。
#    ⚠ 2026-09-21 补 `124: {6}`（真实站超时 run 首次暴露的**预存断言缺陷**）:
#      **两条路的映射时机不同** ⇒ `.meta` 里的 TASK_RC 语义不同:
#        · opencode 路: `timeout N opencode run` 的 `$?`=**124**(原始哨兵) 直接写进 `.meta`;
#          124→6 是**控制台侧**在 `Invoke-Task` 里做的(`if ($code -eq 124) { $code = 6 }`)。
#        · claude 路: `Invoke-Task-Claude` **先**做 `if ($rc -eq 124) { $rc = 6 }`, 再写 `.meta`
#          ⇒ 其 `.meta` 里已经是 6(故上面 `6: {6}` 覆盖它)。
#      ⇒ 对 opencode 路, `.meta=124` ↔ `run.json=6` 是**正确且已文档化**的行为(DESIGN §9.5);
#        旧表无 124 条目 ⇒ 回退成 `allowed={124}` ⇒ 把每个**合法超时 run 都误报 FAIL**
#        (实测 2026-09-21: 3 个真实超时 run 202609211645528026/1647356392/1652100034 全部命中)。
#        只允许 {6}(不加 124): 控制台两路都必做该映射 ⇒ 出现 124 反倒说明映射没走。
_VERDICT_RC_MAP = {0: {0}, 6: {6}, 9: {1, 9}, 14: {14}, 24: {24}, 124: {6}}


def _verdict_allowed(rc: int, rc_domain):
    """TASK_RC → run.json `exit_code` 的**允许集**（**判据只在此处定义**，供断言与单测共用）。

    2026-09-23（裁定 b, O-27）：**按 `RC_DOMAIN` 选域** —— 这是一次"治同源"而非"放宽判据"。
      · **v2**（`agent-cli.ps1` 2026-09-23 起写）：`.meta TASK_RC` 已是**整体退出码**（映射前），
        与 run.json `exit_code`（映射后，9→1）**同域** ⇒ 直接用映射表，**不放宽**。
        旧实现写的是 **agent 码**（accept 失败时为 0，而整体码是 9→1）⇒ 两域不一致，
        导致**每个"验收失败"的 run 都被误判 evidence FAIL**（阻断提交）—— 与 2026-09-21 的
        `124` 条目同型（"旧表无该条目 ⇒ 把合法 run 都误报 FAIL"）。
      · **v1**（无标记的历史 run）：**有界宽容** —— 仅把 `0` 放宽到 `{0, 1}`，其余照旧。
        依据：v1 的 `TASK_RC=0` 有两种合法来源（agent 成功且验收成功 ⇄ agent 成功但验收失败）；
        该歧义**自 v2 起不再产生**（源头已修）。
    """
    if (rc_domain or "").strip().lower() == "v2":
        return _VERDICT_RC_MAP.get(rc, {rc})
    if rc == 0:
        return {0, 1}
    return _VERDICT_RC_MAP.get(rc, {rc})


def _meta_parse(p: Path) -> dict:
    """解析 `KEY=VALUE` 行 (原文照收件的读取, **不做规范化**)。"""
    d = {}
    try:
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in ln and not ln.lstrip().startswith("#"):
                k, v = ln.split("=", 1)
                d[k.strip()] = v.strip()
    except OSError:
        return {}
    return d


def _tri(v):
    """'1'→True / '0'→False / 其余→None(=不可判, 跳过该字段而非判失败)。"""
    return True if v == "1" else (False if v == "0" else None)


def _verdict_check(run_dir: Path, ts: str, label: str) -> tuple:
    """A1: `.meta` ↔ run.json 一致性。→ (issues, gaps, judged_bool)

    ⚠ **`ts` 与 `label` 必须分开**: `TASK_ID` 比对的对手是 run 的**裸时间戳**(= 目录名),
      而消息里要显示 `proj/ts`。二者混用会让 `TASK_ID != label` 恒真 ⇒ **判据静默降级为
      "全部上一轮残留"**(2026-09-17 实测踩到, 覆盖率假报 0/67)。

    分层依据 (为什么这样切, 而非一律 FAIL):
      · 两份都是**已归档件** ⇒ 不一致 = 其中之一被改过 ⇒ **FAIL**(verdict_mismatch)
      · `.meta` 属**上一轮残留**(TASK_ID≠ts, O-22 已知情形) ⇒ 不是篡改 ⇒ **gap**
        (此时 run.json 侧已被主动归零, 比对必然假阳性 ⇒ 必须先剔除)
      · 缺 `.meta` = 早于 ADR-0005 ⇒ **gap 且**不计入判据覆盖率, 由调用方聚合为一行
      · `accept.passed is None`(卡无 accept 判据) / 非 0-1 值 ⇒ **跳过该字段**
    """
    mp, jp = run_dir / "judgment-record.txt", run_dir / ".agent-run.json"
    if not mp.is_file():
        return [], [f"{label}:not_applicable"], False
    try:
        j = json.loads(jp.read_text(encoding="utf-8-sig", errors="replace"))
    except Exception:
        return [f"{label}: .agent-run.json 不可解析, 无法比对"], [], False
    meta = _meta_parse(mp)
    if not meta:
        return [], [f"{label}: judgment-record 无可解析键 ⇒ verdict 不可判"], False
    tid = meta.get("TASK_ID")
    if tid and tid != ts:
        return [], [f"{label}: 判据记录属**上一轮残留** (TASK_ID={tid}, O-22) ⇒ 本轮 verdict 不可复核"], False
    bad, gap, judged = [], [], 0

    def cmp(label_, mv, jv):
        nonlocal judged
        if mv is None or jv is None:
            return
        judged += 1
        if mv != jv:
            bad.append(f"{label}: {label_} 不一致 (meta={mv} run.json={jv})")

    rc = meta.get("TASK_RC")
    if rc is not None and rc.lstrip("-").isdigit():
        rci = int(rc)
        allowed = _verdict_allowed(rci, meta.get("RC_DOMAIN"))
        ec = j.get("exit_code")
        judged += 1
        # 形状守卫 (2026-09-18 实测): 环境层污染曾使 `exit_code` 变成**数组** `[null, 0]` ⇒ 原写法
        #   `ec not in allowed`(集合成员判定) 抛 `TypeError: unhashable type: 'list'` ⇒ **复验器崩掉**
        #   ⇒ 整条链的全部判据同时消失(比"单条报错"糟得多)。故先判形状、畸形报 issue, 绝不抛。
        if not isinstance(ec, (int, str, type(None))):
            bad.append(f"{label}: run.json exit_code **形状畸形** ({type(ec).__name__}: {ec!r}) "
                       f"⇒ 该条不可判(不静默跳过)")
        elif ec not in allowed:
            # O-119 (2026-09-30): **传输层失败 / 任务层成功** 的**双真相**。实测来源 = hang 批首跑
            #   4 张卡（O-117：生成件里那条"被推出 `#` 的注释"当命令跑）⇒ **外壳退出码 = 255**
            #   （ssh/bash 的"远端命令失败"约定），而任务自身的 accept **已跑过并通过**
            #   （产物在 runDir、`ACCEPT_OK=1`）。两份归档件**都没被改**（不是篡改）⇒ 属**不可判**
            #   （与 O-22"上一轮残留"同族：判据记录不可信 ⇒ 本轮 verdict 不可复核）。
            #   ★ **刻意不进 FAIL 集**：报 FAIL 会让这 4 条一入链就**阻断一切提交**，而判据会因此
            #   被整体忽略（同 O-29 / D4 的处置）。⚠ 豁免**只覆盖实测过的这一个形状**
            #   （`TASK_RC=0` 且 `exit_code=255`），其余不一致**照旧 FAIL**（见 T15，防"把门拆掉"）。
            if rci == 0 and ec == 255:
                gap.append(f"{label}: TASK_RC={rci} 但 run.json exit_code={ec}"
                           f"（**传输层失败 / 任务层成功** = O-117 形态）⇒ 本轮 verdict 不可复核")
            else:
                bad.append(f"{label}: TASK_RC={rci} 但 run.json exit_code={ec} "
                           f"(依映射允许 {sorted(allowed)})")
    cmp("ACCEPT_OK↔accept.passed", _tri(meta.get("ACCEPT_OK")), (j.get("accept") or {}).get("passed"))
    ag = j.get("accept_golden")
    if isinstance(ag, dict):
        cmp("ACCEPT_GOLDEN_OK↔accept_golden.passed", _tri(meta.get("ACCEPT_GOLDEN_OK")), ag.get("passed"))
    for mk, jk in (("QUEUE_S", "queue_s"), ("RUN_S", "run_s")):
        mv = meta.get(mk)
        if mv is not None and mv.lstrip("-").isdigit():
            cmp(f"{mk}↔{jk}", int(mv), j.get(jk))
    return bad, gap, judged > 0


_GOLDEN_INDEX = None


def _golden_index() -> dict:
    """basename → [路径]，**全仓一次**索引。含被 .gitignore 的 `tmp/`(夹具常驻那里)。

    只按 basename 检索 —— 因 run.json **只记 base、不记路径**(与缺口 5「attach 只存 basename」同族)。
    """
    global _GOLDEN_INDEX
    if _GOLDEN_INDEX is None:
        idx = {}
        root = Path(__file__).resolve().parent.parent
        skip = {".git", "node_modules", "__pycache__", ".venv", ".mypy_cache"}
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in skip]
            for fn in fns:
                idx.setdefault(fn, []).append(Path(dp) / fn)
        _GOLDEN_INDEX = idx
    return _GOLDEN_INDEX


def _golden_identity_check(run_dir: Path, label: str) -> tuple:
    """A2: 当次注入的 golden ↔ 其**仓库源**。→ (issues, gaps, judged_bool)

    ⚠ **本判据永不 FAIL**: golden 会**合法演进**(改判据脚本是正常开发行为),
      "哈希不同" 与 "被篡改" 在此**不可区分** ⇒ 一律 info/gap, 需人判 (ADR-0007 D4)。
    """
    try:
        j = json.loads((run_dir / ".agent-run.json").read_text(encoding="utf-8-sig", errors="replace"))
    except Exception:
        return [], [], False
    g = j.get("accept_golden")
    if not isinstance(g, dict) or not g:
        return [], [], False                     # 非 golden 卡 ⇒ 本判据不适用(不计覆盖率)
    base, sha = (g.get("base") or "").strip(), (g.get("sha256") or "").strip()
    if not base or not sha:
        return [], [f"{label}: accept_golden 无 base/sha256 (ADR-0005 前) ⇒ golden 身份不可判"], False
    cands = _golden_index().get(base, [])
    if not cands:
        return [], [f"{label}: golden 源 '{base}' 已不在仓库 ⇒ 不可判 (**不判为篡改**)"], True
    if len(cands) > 20:                          # 同名过多则不逐个哈希(防拖慢门禁), 报不可判
        return [], [f"{label}: golden 名 '{base}' 全仓有 {len(cands)} 个同名 ⇒ 歧义不可判"], True
    for c in cands:
        try:
            if _sha256_file(c) == sha:
                return [], [], True              # 命中仓库源 ⇒ 身份一致
        except OSError:
            continue
    return [], [f"{label}: golden '{base}' 在仓库存在但哈希**已变** (当次 {sha[:12]}…) "
                f"⇒ 合法演进或篡改, **需人判**"], True


# readonly 卡的 diff-scope 判据 (ADR-0007 缺口 4)。allow = 工作区相对路径前缀。
#   **必须含 `out/`** —— readonly 卡的交付物就写在那里(如 dogfood-research-modulemap 的
#   accept 判的就是 out/.dogfood_module_map.md) ⇒ naive "readonly ⇒ 零改动" 会误杀合法运行。
#   载体 (`workspace-diff.txt`) 自 2026-09-18 起由**远端 `find -newer`** 采集 (缺口 4 已闭环) ⇒
#   仍是 readonly 的**老 run** 无载体, 记 gap 而**不得当作通过**。
AGENT_DIFF_ALLOW_PREFIXES = ("out/",)


def _diff_scope_check(run_dir: Path, label: str) -> tuple:
    """diff-scope: readonly 卡"未越界"判据。→ (issues, gaps, judged_bool)

    载体 = `workspace-diff.txt`, 内容为**工作区相对路径**, 每行一个 (由远端 `find -newer`
    以 `-printf '%P\\n'` 产出 —— 与 git 无关, 因实测工作区非 git 仓库)。
    非 readonly 卡 ⇒ 本判据**不适用**(not-a-judgment, 调研 §7.2 要点 4)。
    """
    try:
        j = json.loads((run_dir / ".agent-run.json").read_text(encoding="utf-8-sig", errors="replace"))
    except Exception:
        return [], [], False
    if not j.get("readonly"):
        return [], [], False                       # 非 readonly ⇒ 不适用
    p = run_dir / "workspace-diff.txt"
    if not p.is_file():
        return [], [f"{label}: readonly 卡但无 workspace-diff 载体 ⇒ **不可判**(缺口 4 未落地)"], False
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], [f"{label}: workspace-diff 不可读"], False
    touched = [ln.strip().lstrip("./") for ln in txt.splitlines() if ln.strip()]
    oos = [t for t in touched if not t.startswith(AGENT_DIFF_ALLOW_PREFIXES)]
    if oos:
        return [f"{label}: readonly 卡**越界** —— 改动 out/ 之外: {', '.join(oos[:5])}"
                + (f" …(共 {len(oos)})" if len(oos) > 5 else "")], [], True
    return [], [], True


def agent_chain_append(reanchor: bool = False) -> dict:
    """把**尚未入链**的 run 补进链 (幂等: 重复跑不产生新条目), 并镜像冷路径。

    prev 链接的是**入链次序**(append-only 日志序) —— 故 ts 交错的并发派发不会破坏链。
    返回 {"added": [...], "total": N, "chain": <path>} ; 只读 run 目录, 不写任何站。
    """
    roots, note = _agent_proj_roots()
    if not roots:
        return {"added": [], "total": 0, "error": note or "PROJECTS 解析为空"}
    # ★ O-96（2026-09-26）：**写后校验 + 重试** —— 治"两个 `cluster.py agent chain` 并发 ⇒
    #   整文件「读 → 追加 → 写」的后写覆盖先写（**链丢 run**）"。
    #   · 为什么在这里重试是安全的：追加**幂等**（按 `(proj, run_id)` 去重）且 prev 串的是
    #     **入链次序** ⇒ 被覆盖后**带着刚读到的新链重来**，只会得到"两边都在"的链。
    #   · digest 与并发无关（只读 run 目录）⇒ **先算一次**，循环里只做「读链 → 追加 → 写 → 校验」。
    #   · 不收敛 ⇒ 如实报 `race: True`（不假装成功）；⚠ 残余窗口（校验通过后、进程退出前又被覆盖）
    #     **不会静默** —— 锚与链不一致会被 `evidence` 判据抓出来（本条的既有缓解手段）。
    prepared = {}
    for ts, proj, run_dir in _chain_runs(roots):
        _rec = AGENT_DIGEST_RECIPE
        try:
            _j = json.loads((run_dir / ".agent-run.json").read_text(encoding="utf-8-sig", errors="replace"))
            if ((_j.get("evidence_manifest") or {}).get("subjects")):
                _rec = "v2"
        except Exception:
            pass
        rd = _run_digest(run_dir, _rec)
        prepared[(proj, ts)] = {"proj": proj, "run_id": ts, "digest": rd["digest"],
                                "files": rd["files"], "recipe": _rec,
                                "chained_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    want = set(prepared)

    def _chain_merge_once():
        """**一次**"读链 → 追加 → 写(冷热) → 写锚 → 校验"。必须在 `_excl_lock` 内调用。"""
        chain = _chain_load(AGENT_CHAIN)
        seen = {(e.get("proj"), e.get("run_id")) for e in chain["entries"]}
        prev = chain["entries"][-1]["digest"] if chain["entries"] else "-"
        added = []
        for key, ent in prepared.items():
            if key in seen:
                continue
            ent = dict(ent)
            ent["prev"] = prev
            chain["entries"].append(ent)
            prev = ent["digest"]
            added.append({"proj": ent["proj"], "run_id": ent["run_id"], "digest": ent["digest"][:16]})
        if added:
            chain["head"] = {"proj": chain["entries"][-1]["proj"],
                             "run_id": chain["entries"][-1]["run_id"],
                             "digest": chain["entries"][-1]["digest"]}
            blob = json.dumps(chain, ensure_ascii=False, indent=1)
            AGENT_CHAIN.write_text(blob, encoding="utf-8")
            try:
                AGENT_CHAIN_COLD.parent.mkdir(parents=True, exist_ok=True)
                AGENT_CHAIN_COLD.write_text(blob, encoding="utf-8")
            except OSError as e:
                added.append({"error": f"冷路径镜像失败: {e.__class__.__name__}"})
        # 锚写不写 —— 语义要紧: 新增条目必然重写; 锚**缺失**时补建(首次); 其余一律不动。
        #   锚与链不符 = 篡改信号, 绝不在 `chain` 里静默"修复"它 (要重锚须显式 --reanchor), 否则
        #   攻击者重写链后跑一次 chain 就把痕迹抹平了。
        anchor_stale = bool(added) or reanchor or not AGENT_CHAIN_ANCHOR.is_file()
        if anchor_stale:
            try:
                AGENT_CHAIN_ANCHOR.parent.mkdir(parents=True, exist_ok=True)
                _anchor_write(chain)
            except OSError as e:
                added.append({"error": f"锚写入失败: {e.__class__.__name__}"})
        on_disk = {(e.get("proj"), e.get("run_id")) for e in _chain_load(AGENT_CHAIN)["entries"]}
        if want <= on_disk:
            return {"added": added, "total": len(chain["entries"]), "chain": str(AGENT_CHAIN),
                    "anchor": str(AGENT_CHAIN_ANCHOR), "anchor_written": anchor_stale}
        return None                      # 校验没通过 ⇒ 交给外层带新链重来

    last = {"added": [], "total": 0, "anchor_written": False}
    for attempt in range(1, 6):
        try:
            with _excl_lock(AGENT_CHAIN):
                got = _chain_merge_once()
        except TimeoutError as e:
            return {"added": [], "total": 0, "chain": str(AGENT_CHAIN),
                    "anchor": str(AGENT_CHAIN_ANCHOR), "anchor_written": False,
                    "attempts": attempt - 1, "race": True, "error": f"{e.__class__.__name__}: {e}"}
        if got:
            got["attempts"] = attempt
            return got
    last.update({"race": True, "attempts": 5})
    return {"chain": str(AGENT_CHAIN), "anchor": str(AGENT_CHAIN_ANCHOR), **last}


def _p2_committed_chain_assert() -> list:
    """P2（2026-09-21）: 断言「**暂存区(将入库)的链** == **暂存区锚钉的 cold_sha256**」。

    为什么需要（这是 P2 断言的必要性，`_anchor_check` 覆盖不了）:
      · `_anchor_check` 的 chain_sha256/cold_sha256 只比**工作区盘面字节** vs 锚 —— 它保证
        "**盘上**的链==锚"，但**不保证"即将/已提交的链==锚"**。
      · 链本体是 append-only、`agent chain` 每次派发都会重写 + 改写锚 ⇒ 若只 `git add` 了锚、
        或只 `git add` 了链，HEAD 里两者就**不成对** ⇒ off-machine 副本与锚对不上，且在
        干净 clone 上无法复验。这正是 P2（链入仓给 off-machine 副本）要抓的**成对提交违规**。
      ⇒ 断言必须盯 **commit 面（git index）**，不是盘上草稿。

    读 index（`git show :<path>`，只读）取两侧字节:
      · 链   = `archive/evidence-chain/agent-chain.json`（冷镜像，已入仓）
      · 锚   = `archive/evidence-chain/ANCHOR.txt` → 取 cold_sha256
    两侧都取 index ⇒ 能同时抓"只 add 锚"与"只 add 链"两种半提交。
    git 不可用 ⇒ 返回空（**不假装 FAIL** —— 沿用"能区分环境缺依赖 vs 本仓 bug"的纪律）。
    """
    import shutil, subprocess
    root = Path(__file__).resolve().parent.parent
    rel_chain = "archive/evidence-chain/agent-chain.json"
    rel_anchor = "archive/evidence-chain/ANCHOR.txt"
    git = shutil.which("git")
    if not git:
        return []

    def _index(path: str):
        try:
            p = subprocess.run([git, "show", f":{path}"], cwd=str(root), capture_output=True)
        except Exception:
            return None
        return p.stdout if p.returncode == 0 else None

    anc_b = _index(rel_anchor)
    if anc_b is None:
        return []   # 锚未暂存 ⇒ 由 _anchor_check / 其它状态兜, 这里不误判
    got = {}
    try:
        for ln in anc_b.decode("utf-8", "replace").splitlines():
            if "=" in ln and not ln.lstrip().startswith("#"):
                k, v = ln.split("=", 1)
                got[k.strip()] = v.strip()
    except Exception:
        got = {}
    pinned = got.get("cold_sha256") or got.get("chain_sha256") or ""
    chain_b = _index(rel_chain)
    if chain_b is None:
        return [{"kind": "p2_pair_mismatch",
                 "detail": f"链与锚未成对提交: 锚已暂存但链未暂存（{rel_chain} 需与锚同批 `git add`）"}]
    if not pinned:
        return []   # 锚里没有 sha 字段 ⇒ 交给 _anchor_check 判
    got_sha = _sha_lf(chain_b)
    if got_sha != pinned:
        return [{"kind": "p2_pair_mismatch",
                 "detail": f"链与锚未成对提交: 暂存链 sha256={got_sha[:16]}… ≠ 锚钉 cold_sha256={pinned[:16]}… "
                           f"⇒ 两件须在同一 commit 一起 add（先跑 `agent chain` 使锚与链一致，再同时 add 两者）"}]
    return []


def agent_chain_verify() -> dict:
    """复验: ①逐条重算 digest 比链 ②prev 链闭合 ③冷路径/外部锚一致 ④A1 verdict-chain ⑤A2 golden-identity。

    输出 **gap 表**(不打分 —— 评分归评审环), 并按 ADR-0007 D4 分三层返回:
      · `issues` = 篡改/损坏 ⇒ 门禁 FAIL
      · `gaps`   = 覆盖缺口/不可判 ⇒ 门禁 WARN
      · `notes`  = 合法演进(如 golden 已变更) ⇒ 仅供参考, **不告警**
    """
    roots, note = _agent_proj_roots()
    chain = _chain_load(AGENT_CHAIN)
    issues, prev = [], "-"
    v_gaps, v_notes = [], []
    v_na, v_judged, g_na, g_judged, d_na, d_judged = 0, 0, 0, 0, 0, 0
    for i, e in enumerate(chain["entries"]):
        proj, ts = e.get("proj"), e.get("run_id")
        tag = {"index": i, "proj": proj, "run_id": ts}
        if e.get("prev") != prev:
            issues.append(dict(tag, kind="chain_break", expect=prev, got=e.get("prev")))
        rec = e.get("recipe")
        root = roots.get(proj)
        run_dir = (root / "agent-out" / ts) if root and ts else None
        # recipe 按条目分派: 未知 recipe = **不可验** ⇒ FAIL (不得静默跳过)
        if rec not in AGENT_DIGEST_RECIPES:
            issues.append(dict(tag, kind="recipe_unknown", got=rec, expect=list(AGENT_DIGEST_RECIPES)))
        elif not run_dir or not run_dir.is_dir():
            issues.append(dict(tag, kind="run_dir_missing"))
        else:
            rd = _run_digest(run_dir, rec)
            if rd is None:
                # 声明了 v2 却无 subjects ⇒ **不可验** ⇒ FAIL (不得当作通过)
                issues.append(dict(tag, kind="manifest_missing",
                                   detail=f"{proj}/{ts}: recipe={rec} 但 run.json 无 evidence_manifest.subjects"))
            elif rd["digest"] != e.get("digest"):
                old = e.get("files") or {}
                issues.append(dict(tag, kind="digest_mismatch",
                                   files_changed=sorted(k for k in rd["files"] if rd["files"][k] != old.get(k)),
                                   expect=(e.get("digest") or "")[:16], got=rd["digest"][:16]))
            if rec == "v2":
                # 阶段1 判据「未声明的产物类型若出现 ⇒ 判失败」(借 SLSA "未识别 externalParameters
                #   ⇒ 校验失败")。判法: 框架**已知**的证据件若**已存在于 runDir 却未在 manifest 声明**
                #   ⇒ manifest_undeclared FAIL。只查"已存在"的 ⇒ 缺件(老 run)不误报。
                try:
                    _jj = json.loads((run_dir / ".agent-run.json").read_text(encoding="utf-8-sig", errors="replace"))
                    _decl = {str(s.get("path") or "").strip() for s in
                             ((_jj.get("evidence_manifest") or {}).get("subjects") or [])}
                except Exception:
                    _decl = set()
                _und = [f for f in AGENT_MANIFEST_REQUIRED if (run_dir / f).is_file() and f not in _decl]
                if _und:
                    issues.append(dict(tag, kind="manifest_undeclared",
                                       detail=f"{proj}/{ts}: 已归档但未在 evidence_manifest 声明的件: {', '.join(_und)}"))
            # ── A1/A2 (批 A) ── 只在 run_dir 可达时判 (ts 是裸时间戳, label 仅用于显示)
            lbl = f"{proj}/{ts}"
            v_bad, v_gap, v_ok = _verdict_check(run_dir, ts, lbl)
            for b in v_bad:
                issues.append(dict(tag, kind="verdict_mismatch", detail=b))
            if not v_ok and v_gap and v_gap[0].endswith(":not_applicable"):
                v_na += 1                      # 早于 ADR-0005 的老 run: 只计覆盖率, 不逐个报(防噪声)
            else:
                v_gaps += v_gap
                v_judged += 1 if v_ok else 0
            g_bad, g_gap, g_ok = _golden_identity_check(run_dir, lbl)
            for b in g_bad:
                issues.append(dict(tag, kind="golden_identity", detail=b))
            if not g_ok and g_gap:
                if "ADR-0005 前" in g_gap[0]:
                    g_na += 1                  # 同上: 老 run 只计覆盖率
                else:
                    v_gaps += g_gap
            elif g_ok:
                g_judged += 1
                v_notes += g_gap               # 可判但"哈希已变/源已不在" ⇒ notes(info), 不告警
            # ── 缺口 4: diff-scope (readonly 卡的"未越界"; 老 run 无载体 ⇒ 不可判, 不当作通过) ──
            d_bad, d_gap, d_ok = _diff_scope_check(run_dir, lbl)
            for b in d_bad:
                issues.append(dict(tag, kind="diff_scope", detail=b))
            if not d_ok and d_gap:
                if "缺口 4 未落地" in d_gap[0]:
                    d_na += 1                  # 载体未落地 ⇒ 只计"不适用", 不逐个报(防噪声)
                else:
                    v_gaps += d_gap
            elif d_ok:
                d_judged += 1
        prev = e.get("digest")
    cold = _chain_load(AGENT_CHAIN_COLD)
    if [x.get("digest") for x in cold["entries"]] != [x.get("digest") for x in chain["entries"]]:
        issues.append({"kind": "cold_mismatch",
                       "cold_n": len(cold["entries"]), "chain_n": len(chain["entries"])})
    issues += _anchor_check(chain)
    issues += _p2_committed_chain_assert()   # P2(入仓链==锚成对): 抓"只 add 锚或只 add 链"
    # 未入链 = **覆盖缺口, 不是篡改** ⇒ gaps(WARN), 见 rpc_check.check_evidence
    seen = {(e.get("proj"), e.get("run_id")) for e in chain["entries"]}
    unchained = sorted(f"{p}/{t}" for t, p, _ in _chain_runs(roots) if (p, t) not in seen)
    n = len(chain["entries"])
    coverage = [
        f"A1 verdict-chain: {v_judged}/{n} 可判" + (f" ({v_na} 个早于 ADR-0005 无 judgment-record)" if v_na else ""),
        f"A2 golden-identity: {g_judged}/{n} 可判" + (f" ({g_na} 个早于 ADR-0005 无 base/sha256)" if g_na else ""),
        f"A3 diff-scope: {d_judged}/{n} 可判" + (f" ({d_na} 个 readonly 卡缺 workspace-diff 载体 ⇒ 不可判)" if d_na else ""),
    ]
    gaps = list(v_gaps) + ([f"未入链 {len(unchained)} 个: {', '.join(unchained[:3])}"
                            + ("…" if len(unchained) > 3 else "")] if unchained else [])
    return {"entries": n, "issues": issues, "gaps": gaps, "notes": v_notes,
            "unchained": unchained, "coverage": coverage,
            "anchor": str(AGENT_CHAIN_ANCHOR), "anchor_present": AGENT_CHAIN_ANCHOR.is_file(),
            "head": chain.get("head"), "note": note}


def _agent_beat(st: str) -> list:
    """扫一站运行中节拍。**只读**: 遍历站上既有 .progress, 不写任何东西, 不装采集器。

    ⚠ O-68/D4 (2026-09-25): 站上节拍文件**已 per-run 化**（`.progress.<ts>`）。只认裸 `.progress`
      会在改名后**恒读旧件/恒空** —— 即"视图静默失效"（本仓头号形态：看起来一切正常）。
      ⇒ 取「裸名 + 全部带后缀名」里 **mtime 最新**的那一份（= 最近一个 run 的节拍）;
        裸名保留是为了兼容改名之前的**历史残留**（D3 的按龄 GC 会在 7 天后清掉它们）。
    """
    cmd = ("for d in " + AGENT_WS + "/*/out; do "
           "f=$(ls -1t \"$d\"/.progress \"$d\"/.progress.* 2>/dev/null | head -1); "
           "[ -n \"$f\" ] || continue; "
           "proj=$(basename \"$(dirname \"$d\")\"); "
           "last=$(grep '^t=' \"$f\" 2>/dev/null | tail -1); "
           "[ -z \"$last\" ] && continue; "
           "printf 'BEAT|%s|%s|%s\\n' \"$proj\" \"$last\" \"$(stat -c %Y \"$f\" 2>/dev/null)\"; "
           "done")
    ok, out = ssh_run(st, cmd, timeout=45)
    if not ok:
        return [{"station": st, "error": (out or "").strip().splitlines()[0][:80] if out else "ssh 失败"}]
    beats, now = [], int(time.time())
    for ln in out.splitlines():
        if not ln.startswith("BEAT|"):
            continue
        parts = ln.split("|", 3)
        if len(parts) < 4:
            continue
        _, proj, last, mtime = parts
        m = re.search(r"^t=(\S+)\s+bytes=(\d+)\s+bytes_s=(\d+)", last.strip())
        if not m:
            continue
        t_val, by, bps = m.group(1), int(m.group(2)), int(m.group(3))
        try:
            age = now - int(mtime)
        except ValueError:
            age = None
        beats.append({"station": st, "proj": proj, "t": t_val, "bytes": by, "bytes_s": bps,
                      "age_s": age, "running": (t_val != "end"),
                      "stale": bool(age is not None and age > AGENT_BEAT_STALE_S),
                      "beat_at": (time.strftime("%m-%d %H:%M:%S", time.localtime(int(mtime)))
                                  if age is not None else "?")})
    return beats


def agent_live(stations=("A", "B", "C")) -> list:
    """三站运行中节拍 (并行)。CLI `agent live` 与 web `/api/agent` **共用这一份**。"""
    res, threads = {}, []
    for st in stations:
        t = threading.Thread(target=lambda s=st: res.__setitem__(s, _agent_beat(s)))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    return [b for st in stations for b in res.get(st, [])]


def agent_runs(limit: int = 20) -> tuple:
    """台账尾 N 条 + join run.json 详情 + 状态归并 → (rows, note)。

    CLI `agent runs` 与 web `/api/agent` **共用这一份** —— join 逻辑只写一遍,
    否则两处迟早漂移 (P2-1 已立过的同一条理由)。
    """
    roots, note = _agent_proj_roots()
    rows = _agent_ledger_rows(limit)
    for r in rows:
        r["detail"] = _agent_detail(roots, r["proj"], r["ts"])
        if r["detail"].get("status"):
            r["status"] = r["detail"]["status"]          # run.json 的 status 优先于 code 映射
    # 台账**不是严格有序的** (实测 09-12 有一对 17:18:20 / 17:18:18 反序, 并发派发所致) ⇒ 按 ts 排一次
    rows.sort(key=lambda r: r["ts"])
    return rows, note


def agent_ledger_freshness(rows) -> dict:
    """台账新鲜度: 事件级 (run 结束才写一行) ⇒ 用**最新一条 ts** 衡量。

    刻意不用"最后一行"(台账实测有并发反序) 也不用文件 mtime (collect 崩了也可能已写过行)。
    """
    if not rows:
        return {}
    newest = max(rows, key=lambda r: r["ts"])
    try:
        t = time.mktime(time.strptime(newest["ts"][:14], "%Y%m%d%H%M%S"))
    except Exception:
        return {"label": newest.get("label"), "age_s": None}
    return {"label": newest.get("label"), "age_s": int(time.time() - t)}


# 2026-09-23 (O-29 / D6-P1-1)：**框架期望件集的版本** —— 判据演化时用它分桶。
#   当前代 = "2"：accept-* 与 golden-cmd 改为**条件列**这一代（此前为裸列，见 O-29）。
#   ⚠ `_FWVER_SCOPE` 默认 **空串** ⇒ `_gap_key` **保持旧形状** ⇒ 历史 gap 的 key **不变**。
#     （若默认非空，存量 18 条的 key 会**全部改变** ⇒ 水印比对时一次性报 18 条假"新增"——**比不做更糟**。）
FRAMEWORK_SUBJECTS_VERSION = "2"
_FWVER_SCOPE = ""


def _fwver_set(v) -> None:
    """审计循环在**每个 run 处理前**调用（设置点见 readiness 的 run 循环）。"""
    global _FWVER_SCOPE
    _FWVER_SCOPE = str(v or "")


def _gap_key(kind: str, label: str, sub: str) -> str:
    """把 gap 归一为**可比较标识**（ADR-0007 路A 的硬前置 K1）。

    为什么**不能**用 gap 的文本做增量基线（实测，见
    docs/research/2026-09-18_证据流审计常跑_触发点与成本严重度调研.md §4.3）:
      同类 gap 的文本会随"约定名归档件在/不在"而变化 —— 例如 collect 型会多一句
      "（归档件 `x.txt` 按约定名存在 ⇒ 只有产物、无执行记录）"，件一被补上/删掉文本就变
      ⇒ 拿文本比对会把"同一 gap 换了种表现"读成**新增 gap** ⇒ **假告警**。
    形状: `<kind>|<label>|<sub>`；`sub` = subject 名，undeclared 型 = **排序后件名**逗号连接
      （排序保证集合可比；新增/减少件确实改变 key —— 那是**真信息**，应当告警）。

    **2026-09-23 追加（O-29）**：key 前**再加一维框架代** ⇒ `<fwver>|<kind>|<label>|<sub>`。
      目的：**判据演化之后，历史 gap 与新 gap 的 key 天然不同** ⇒ 水印机制**自动分桶**，
      无需另写"按版本判"的分支；报告层的 `current=N · legacy=M` 计数可后补（见 P1-1）。
      `_FWVER_SCOPE` 为空时**退化为旧形状**（保证历史 key 不变，见上）。
    """
    if _FWVER_SCOPE:
        return f"{_FWVER_SCOPE}|{kind}|{label}|{sub}"
    return f"{kind}|{label}|{sub}"


# ── 审计水印（ADR-0007 路A / K2）───────────────────────────────────────
# 用途: 让"常跑审计"只报**新增**可重放性缺口 —— 否则存量 52 条会天天刷屏，正好落进
#   ADR-0007 D4 警告的"判据因噪声被整体忽略"。
# **为什么写点必须在这里、而不在门禁里**（复验实测）: `ops/rpc_check.py` 对仓库**全程只读**
#   （唯一写动作是 check_syntax 的 tempfile），而门禁挂在 pre-commit 上 —— 门禁自己去写水印
#   会把工作区弄脏。⇒ 水印只能由**显式命令** `cluster.py agent audit --accept` 推进。
#   副作用（刻意接受，与"不静默降级"同向）: **"接受这批新 gap"成为人类的显式动作**，
#   而不是被自动抹平。门禁的 fix 字段会直接给出该命令。
# 存储位置（**2026-09-23 变更：已入仓**）——
#   原为 `ops/.audit-baseline.json`（本地、已 gitignore）。该选择的**两处代价**在
#   `docs/research/2026-09-18_证据流审计常跑_触发点与成本严重度调研.md` §D-b 已登记：
#     ① 换机器/新克隆首跑会把存量当"新增"报一次（**自愈**）；
#     ② **"基线何时建立"不可审计**。
#   同处写明的**升级条件**是"**若将来多人/多机，再升级为入仓**"（那时 `git log` 就是
#   "谁在何时接受了什么"的留痕）。⇒ **D7（三站 + 跨项目）正是该条件所指的"多机"**
#   ⇒ 本轮执行入仓化（**执行已登记的决策，不是新决策**）。
#   代价（刻意接受）：每次 `--accept` 会改动仓内文件 ⇒ **提交摩擦** —— 而**这正是留痕的来源**。
#   已知未决：多机并发 `--accept` 会产生合并冲突（后续可改"按机分文件"，见 D7-P1-1 待办）。
# 2026-09-23（D7-P1-1 后续）：**按机分文件 + 读时并集** —— 治"多机并发 `--accept` 合并冲突"。
#   为什么这样治: 水印语义本就是**单调并集**（非快照）⇒ **并集天然可合并** ⇒
#   把"一台机一个分片"分开写、读时取并集 ⇒ **零冲突、零锁**（不需要 flock，也不需要重放）。
#   代价: 文件数 = 机器数（很小）；好处是"哪台机接受了什么"直接体现在**文件名**上。
#   兼容: 目录不存在但旧的单文件 `audit-baseline.json` 还在 ⇒ 仍读它（迁移期无需停机）。
AGENT_AUDIT_BASELINE_DIR = Path(__file__).resolve().parent.parent / "inventory" / "audit-baseline"
AGENT_AUDIT_BASELINE = AGENT_AUDIT_BASELINE_DIR / "audit-baseline.json"   # 兼容名（旧单文件/文档引用）


def _audit_host() -> str:
    """本机标识（用作分片文件名）。取 COMPUTERNAME/HOSTNAME，缺 ⇒ `local`。"""
    h = os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "local"
    return re.sub(r"[^A-Za-z0-9._-]", "_", h).lower()


@contextmanager
def _excl_lock(target: Path, timeout: float = 30.0):
    """跨进程**互斥**（**只**给"读 → 改 → 写**整文件**"的生产者用）。

    ★ O-95/O-96（2026-09-26）：为什么必须是**锁**而不是"写后校验 + 重试" ——
      重试的收敛性只在"两方竞争"下成立；**真并发 8 方**时重试会**耗尽**（实测：8 线程 × 20 key
      ⇒ 160 个 key **丢了 80 个**）⇒ 它是**概率性**修法，而丢更新是**确定性**要治的病。
    · 锁的**释放**交给内核（POSIX `flock` / Windows `msvcrt`）⇒ **进程崩溃也会释放** ⇒
      没有"陈旧锁文件"这一类新故障（这正是不用"独占创建锁文件"做法的理由）。
    · 锁文件放**系统临时目录**（按目标路径哈希命名）⇒ **不污染仓库**（否则会被生成物/扫描类判据看到）。
    · 拿不到锁 ⇒ 抛 `TimeoutError`（调用方**如实报**，绝不"等不到就直接写"——那正是丢更新的来源）。
    """
    import hashlib, tempfile
    d = Path(tempfile.gettempdir()) / "rpc-locks"
    d.mkdir(parents=True, exist_ok=True)
    lk = d / (hashlib.sha256(str(Path(target).resolve()).encode("utf-8")).hexdigest()[:16] + ".lock")
    f = open(lk, "a+b")
    deadline = time.time() + timeout
    try:
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.time() > deadline:
                    raise TimeoutError(f"取锁超时({timeout}s): {lk.name}")
                time.sleep(0.05)
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        f.close()


def agent_audit_baseline_load() -> dict:
    """读水印 —— **并集所有机的分片**；缺失/损坏 ⇒ 空基线（**不抛**：缺基线=首跑把存量当新增报一次，自愈）。

    真值源 = **目录下所有 `*.json` 的并集**（单调并集语义 ⇒ 并集即正确值）。
    单分片损坏**不拖垮整体**（跳过它，其余仍有效）。
    """
    files = []
    if AGENT_AUDIT_BASELINE_DIR.is_dir():
        files = sorted(AGENT_AUDIT_BASELINE_DIR.glob("*.json"))
    elif AGENT_AUDIT_BASELINE.is_file():
        files = [AGENT_AUDIT_BASELINE]          # 迁移期兼容：旧的单文件
    keys, created, updated, srcs = set(), "", "", []
    for p in files:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not (isinstance(d, dict) and isinstance(d.get("keys"), list)):
            continue
        keys |= {str(k) for k in d["keys"]}
        created = created or (d.get("created") or "")
        updated = max(updated, d.get("updated") or "")
        srcs.append(p.name)
    return {"version": 1, "keys": sorted(keys), "created": created,
            "updated": updated, "sources": srcs}


def agent_audit_baseline_accept(keys) -> dict:
    """把当前 gap key 集合**并入水印**（**单调**：并集，绝不移除）—— **只写本机分片**。

    单调的理由: 非单调（快照式）会在"runDir 被删后又恢复"时把老 gap 读成新增 ⇒ 假告警。
    代价（已在调研 §10.3 记账）: 同一处 gap 被修复后再次出现**不会二次告警**。

    2026-09-23: 写目标由"单一共享文件"改为 **本机分片** `audit-baseline/<host>.json`
      ⇒ 多机并发 `--accept` **不再产生 git 合并冲突**（各写各的文件；读时并集）。

    ★ O-95（2026-09-26）：**写后校验 + 重试** —— 治"**同机**两个 `--accept` 并发 ⇒ 后写覆盖先写"。
      · 为什么用重试**而不是锁**：水印语义本就是**单调并集**（见上方 2026-09-23 注："并集天然可合并
        ⇒ 零冲突、零锁"）—— 用**同一语义**收口即可，不必为此引入 flock（少一个可失败的原语）。
      · 收敛性：写后**重读全部分片的并集**，若本次要写的 key 不在其中 ⇒ 说明被并发覆盖 ⇒
        带着"刚看到的新并集"重写一次；每次写的内容都是"**并集 ⊇ 自己那部分**" ⇒ **≤2 轮收敛**。
      · 不收敛时**如实报 `race: True`**（不假装成功）—— 与"宁可显式失败也不静默丢"同纪律。
    """
    wanted = {str(k) for k in keys}
    new, merged, tgt = [], [], AGENT_AUDIT_BASELINE_DIR / f"{_audit_host()}.json"
    try:
        with _excl_lock(tgt):
            for attempt in range(1, 11):
                cur = agent_audit_baseline_load()
                old = set(cur.get("keys") or [])
                new = sorted(wanted - old)
                merged = sorted(old | wanted)
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                host = _audit_host()
                AGENT_AUDIT_BASELINE_DIR.mkdir(parents=True, exist_ok=True)
                out = {"version": 1, "host": host, "keys": merged,
                       "created": (cur.get("created") or ts), "updated": ts}
                tgt = AGENT_AUDIT_BASELINE_DIR / f"{host}.json"
                tgt.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                on_disk = set(agent_audit_baseline_load().get("keys") or [])
                if wanted <= on_disk:
                    return {"added": new, "total": len(on_disk), "path": str(tgt), "attempts": attempt}
    except TimeoutError as e:
        return {"added": [], "total": 0, "path": str(tgt), "attempts": 0, "race": True,
                "error": f"{e.__class__.__name__}: {e}"}
    return {"added": new, "total": len(merged), "path": str(tgt), "attempts": 10, "race": True}


def _card_accept_list(card_text: str) -> list:
    """取卡的 front-matter 里 `accept:` 的**有序列表** —— 与产出侧逐字对齐。

    为什么口径必须与产出侧一致：站上写 `out/.accept-cmds.txt` 的内容是
    `($accept -join "\\n")`（`agent-cli.ps1` 的 `$acceptB64`），**行序 = 卡里的声明序**
    ⇒ 这里也必须**保序**取列表，才能做等值判定。

    只认 `---` 围栏内的顶层 `accept:` 块（与 `Get-FrontMatter` 同规则）：
      · `accept-golden:` 是**另一个键**，不得混入；
      · 行内写法（`accept: foo`）产出侧**不采**（PS 解析器只认 `- item` 列表式）⇒ 这里同样不采。
    纯函数（不碰站 / 不碰文件系统）⇒ 离线可测（与 `Test-EvmStatePull` 同纪律）。
    """
    lines = card_text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return []
    out, in_acc = [], False
    for ln in lines[1:]:
        if ln.strip() == "---":
            break
        if re.match(r"^accept\s*:", ln):
            in_acc = True
            continue
        if in_acc:
            m = re.match(r"^\s*-\s+(.+)$", ln)
            if m:
                out.append(m.group(1).strip())
                continue
            if ln.strip() and not ln[:1].isspace():
                in_acc = False          # 顶层下一个键 ⇒ 块结束
    return out


def compare_accept_cmds(card_text: str, archived_text: str) -> tuple:
    """比较**归档的** `accept-cmds.txt` 与**该 run 卡的** `accept:` 声明（O-57 配套判据）。

    返回 `(same, want_n, got_n)`。纯函数（只吃两个文本）⇒ 离线可测。
    为什么**保序等值**而不是"集合包含"：产出侧写的是 `($accept -join "\\n")` ⇒ 归档字节就是
    卡里那段声明的**逐字有序**副本；序不同 = 不是同一份声明 ⇒ 同样属残留（不放过）。
    """
    want = _card_accept_list(card_text)
    got = [x.strip() for x in archived_text.splitlines() if x.strip()]
    return (want == got), len(want), len(got)


def agent_audit(limit: int = 0, save: bool = False) -> dict:
    """阶段 3-a (ADR-0007): **证据可复现性审计** → 机器可判 gap 表（advisory）。

    与 `verify` 的**分工**（刻意分清，否则两套判据会互相污染）:
      - `verify` 判 **"证据是否被改"**（篡改/损坏）⇒ 有 FAIL 集，进门槛；
      - `audit`  判 **"每条声明能否被独立复现、卡在哪"**（可重放性）⇒ **只出 gap 表**，不改 FAIL 集。
    这正是不把 audit 直接塞进门禁的原因: 可重放性缺口是**已知的工程债**（如 `collect` 命令从未执行），
    判 FAIL 会把每次派发都拦下 ⇒ 造出"因无人能应对而失败"的判据（调研 §5.6 的反面教训）。

    逐 subject 的 readiness（机器可判字段）:
      path 型   → 归档件在 + 摘要命中 ⇒ `offline-ok`（可离线按件复算）
                  归档件缺            ⇒ `missing-artifact`
      collect 型 → 框架**从不执行**声明的命令（ADR-0007 缺口 4/5 已记）⇒ 一律 `declared-not-executed`，
                  并按**约定名** `<name>.txt` 看归档件: 在 ⇒ `+artifact-by-convention` / 缺 ⇒ `+no-artifact`
      **ephemeral** → 卡声明 `ephemeral: true` 且归档件不在 ⇒ **`artifact-ephemeral-by-design`**：
                  "产物在站上临时目录、设计上就不进 runDir"（Cpp_Hub 型任务：工作目录在站上 `/tmp`）
                  ⇒ **不是缺口**，但**也不计入可离线复算**（单列，否则覆盖率会虚高）
      **失败 run** → `status=failed` ⇒ 该 run **本身未完成**，框架件天然不产出 ⇒
                  **`failed-run-by-design`**（2026-10-23；与 `exit 3` 的 `locked-out-by-design` 同族）
                  ⇒ **不是缺口**，单列且**不计入可离线复算**（否则每次失败 run 会灌 11 条噪声）
      其他       → runDir 里存在但**未被任何 subject 的 path 覆盖**的非隐藏件 ⇒ `undeclared-evidence`
    """
    roots, _note = _agent_proj_roots()
    runs = _chain_runs(roots)
    if limit and limit > 0:
        runs = runs[-limit:]
    out_runs, gaps, gap_keys = [], [], []   # gap_keys 与 gaps **逐条平行**(K1: 供水印比对)
    n_sub = n_offline = n_collect = n_undecl = n_runs_v2 = n_ephemeral = 0
    n_acc_ok = n_acc_bad = n_acc_skip = 0     # O-57: `accept-cmds` 归属核对三态
    n_locked = 0                              # O-61: `exit 3`(锁占用) ⇒ 缺件属"设计性缺席"
    n_failed_absent = 0                       # 2026-10-23: `status=failed` ⇒ 缺件属"失败 run 缺席"
    for ts, proj, run_dir in runs:
        label = f"{proj}/{ts}"
        jp = run_dir / ".agent-run.json"
        if not jp.is_file():
            continue
        try:
            j = json.loads(jp.read_text(encoding="utf-8-sig", errors="replace"))
        except Exception:
            continue
        subs = ((j.get("evidence_manifest") or {}).get("subjects")) or []
        recipe = "v2" if subs else "v1"
        # O-61 (2026-09-25): `exit 3` = **锁占用** ⇒ run body 走 `LOCK_HELD` 早退、**从未运行** ⇒
        #   框架件(progress-trace/workspace-diff/attach-manifest/prompt/judgment-record…)**天然不会产出**。
        #   这是 O-59/T1 之后的**预期形态**(危险面配对从"静默互删"变成"可见 `exit 3`"), **不是缺口**
        #   ⇒ 给**第三态** `locked-out-by-design`(与 `ephemeral` 同族: 缺席有正当理由, 不报 missing-artifact,
        #   单列且**不计入可离线复算**, 否则覆盖率虚高)。
        #   判据源 = `.agent-run.json` 的 `exit_code`(派发时写入, 与 runDir 同级)。
        try:
            _ec = int(j.get("exit_code"))
        except (TypeError, ValueError):
            _ec = None
        locked_out = (_ec == 3)
        # ★ 2026-10-23：**失败 run 缺席**（与 O-61 同族的第三态）——
        #   实证触发：evidence 报 90 条新增 gap，其中 88 条 = 8 次同一失败探针卡（exit 1 / status failed）
        #   × 11 个**框架基线** subject。失败路径上这些件天然不产出；若按 missing-artifact 记，
        #   每次失败 run 都会再灌 11 条 ⇒ 水印只能沉默存量、判据会被噪声整体忽略。
        #   口径（写窄，不扩读）：**只认 `status=failed`**；无 `status` 的旧记录退回 exit_code（非 0/3 ⇒ 失败）。
        #   正向对照（tests/test_agent_audit_failed_run.py A5）：completed run 缺件**仍**记 missing-artifact。
        _status = str(j.get("status") or "")
        run_failed = (_status == "failed") or ((not _status) and (_ec is not None and _ec not in (0, 3)))
        per = _run_digest(run_dir, recipe) or {}
        files = per.get("files") or {}
        subjects, covered = [], set()
        for s in subs:
            name = str(s.get("name") or "?").strip() or "?"
            path = str(s.get("path") or "").strip()
            coll = str(s.get("collect") or "").strip()
            if not path and coll:
                path = f"{name}.txt"                  # 约定名（与 v2 取件规则一致, 不另立规则）
            tgt = run_dir / path if path else None
            exists = bool(tgt is not None and tgt.is_file())
            if path:
                covered.add(path)
            hx = files.get(name)
            eph = bool(s.get("ephemeral"))
            if eph and not exists:
                # 设计性临时产物: 卡已声明 ⇒ **不是缺口**(与 missing-artifact 严格区分), 但单列、不计入可离线复算
                rdy = "artifact-ephemeral-by-design" + ("(collect 未执行)" if coll else "")
                n_ephemeral += 1
            elif coll:
                rdy = "declared-not-executed+" + ("artifact-by-convention" if exists else "no-artifact")
                n_collect += 1
                # ⚠ 这一条的**文本**会随 `exists` 变(见 _gap_key 的说明) ⇒ 故其 key **不含**该细节
                gaps.append(f"{label}: subject '{name}' 声明了 collect 命令但**从未执行**"
                            + (f"（归档件 `{path}` 按约定名存在 ⇒ 只有产物、无执行记录）" if exists
                               else f"（且约定名 `{path}` 无归档件）"))
                gap_keys.append(_gap_key("collect-not-executed", label, name))
            elif not path:
                rdy = "no-path-no-collect"
                gaps.append(f"{label}: subject '{name}' 既无 path 也无 collect ⇒ 不可复现")
                gap_keys.append(_gap_key("no-path-no-collect", label, name))
            elif not exists:
                if locked_out:
                    rdy = "locked-out-by-design"
                    n_locked += 1
                elif run_failed:
                    rdy = "failed-run-by-design"
                    n_failed_absent += 1
                else:
                    rdy = "missing-artifact"
                    gaps.append(f"{label}: subject '{name}' 声明的 `{path}` 不在 runDir")
                    gap_keys.append(_gap_key("missing-artifact", label, name))
            else:
                # ⚠ 此处**刻意不比对链上摘要**（那是 `verify` 的轴）: `_run_digest` 是按**当前字节**重算的,
                #   拿它跟"刚算出的文件哈希"比必然相等 —— 写进判据就是**恒真判据**（自欺, 实测踩到）。
                #   ⇒ audit 只答"能不能离线复算"; "算出来是否与链一致"由 verify 定责（分工, 不重叠）。
                rdy = "offline-ok" if hx not in (None, "-") else "offline-ok(未入 recipe 件集)"
                n_offline += 1
            n_sub += 1
            subjects.append({"name": name, "mode": ("collect" if coll else "path"),
                             "target": path, "readiness": rdy})
        # 已归档但未被任何声明覆盖的非隐藏件（**动态**枚举 —— 不维护第二份"框架件清单"）。
        #   仅对**有 manifest 的 run** 计: v1 run 没有"声明"这回事 ⇒ 全列出来只会淹没 gap 表。
        undecl = []
        if subs and run_dir.is_dir():
            for f in sorted(run_dir.iterdir()):
                if not f.is_file() or f.name.startswith("."):
                    continue
                if f.name in covered:
                    continue
                undecl.append(f.name)
        n_undecl += len(undecl)
        if subs:
            n_runs_v2 += 1
        if undecl:
            gaps.append(f"{label}: 已归档但未被任何 subject 覆盖: {', '.join(undecl)}")
            gap_keys.append(_gap_key("undeclared", label, ",".join(undecl)))
        # O-57 配套机判 (2026-09-25): **归档件的归属** —— `accept-cmds.txt` 的**内容**必须等于
        #   该 run **自己那张卡**声明的 `accept:` 列表。
        #   为什么必须另立这条: 站上 `out/` 是**累计**的，而固定名拉回**无 run 窗口** ⇒ 上一次 run
        #   的残留会被当本次证据归档（O-57 实测: 4 个 proj 根 83 个 run 里 **12 条**）；而那条路径的
        #   症状是"**在**" ⇒ 上面的 `missing-artifact` 判据**永远看不见它** ⇒ 只有本判据能判。
        #   ⚠ 派发前的 reset（批 1 / O-57-A）修掉的是**产出面**；本条守的是**存量**与**回归**。
        #   分工复述: 本条判"**归属**"（谁是产出方）; `verify` 判"**是否被改**"; recipe 判"能否离线复算"。
        accp = run_dir / "accept-cmds.txt"
        cardf = run_dir / "card.md"
        if accp.is_file():
            if not cardf.is_file():
                n_acc_skip += 1          # 缺卡 ⇒ 判不了 ⇒ **不报**（如实计数，不假装已判）
            else:
                same, wn, gn = compare_accept_cmds(
                    cardf.read_text(encoding="utf-8-sig", errors="replace"),
                    accp.read_text(encoding="utf-8-sig", errors="replace"))
                if not same:
                    n_acc_bad += 1
                    gaps.append(f"{label}: `accept-cmds.txt` 与**本 run 卡**的 `accept:` **不符**"
                                f"（卡 {wn} 条 / 归档 {gn} 条）⇒ 该证据件疑为**别的 run 的残留**"
                                f"（O-57: 累计 `out/` + 固定名拉回无 run 窗口）")
                    gap_keys.append(_gap_key("accept-cmds-mismatch", label, f"{wn}v{gn}"))
                else:
                    n_acc_ok += 1
        out_runs.append({"label": label, "recipe": recipe, "declared": len(subs),
                         "offline_ok": sum(1 for x in subjects if x["readiness"] == "offline-ok"),
                         "not_exec": sum(1 for x in subjects if x["readiness"].startswith("declared-not-executed")),
                         "ephemeral": sum(1 for x in subjects if x["readiness"].startswith("artifact-ephemeral")),
                         "subjects": subjects, "undeclared": undecl})
    coverage = [
        f"可离线复算: {n_offline}/{n_sub} 条声明（其余为 collect 型/缺件/设计性临时）",
        f"collect 型（声明了命令但从未执行）: {n_collect} 条",
        f"**设计性临时产物**（卡声明 ephemeral ⇒ 产物不进 runDir）: {n_ephemeral} 条"
        f" —— 不计入缺口, 也**不计入可离线复算**(否则覆盖率虚高)",
        # O-61 (2026-09-25): `exit 3`(锁占用) 的 run body **从未运行** ⇒ 框架件天然不产出。与 ephemeral 同族。
        f"**锁占用缺席**（`exit 3` ⇒ body 未运行, 证据件天然不产出）: {n_locked} 条"
        f" —— 不计入缺口, 也**不计入可离线复算**（O-61；这是 O-59/T1 之后的**预期形态**）",
        # 2026-10-23: 失败 run 与 `exit 3` 同族 —— run 本身未完成, 证据件不产出。单列, 不静默。
        f"**失败 run 缺席**（`status=failed` ⇒ 该 run 本身失败, 证据件不产出）: {n_failed_absent} 条"
        f" —— 不计入缺口, 也**不计入可离线复算**（2026-10-23 口径；与 O-61 同族）",
        f"已归档但未声明: {n_undecl} 件",
        f"有 manifest 的 run: {n_runs_v2}/{len(out_runs)}",
        # P1 (ADR-0007 路A, 2026-09-18): **口径要说实话** —— 上面那行只说"有多少个 run 有 manifest",
        #   不说**另外那些判不了**。report 里 `可离线复算 N/M` 的分母**只覆盖 v2 run**;
        #   若不显式说明, 读表的人会把它当成**语料级**结论（本 ADR 已记过"同一份报告两个口径打架"
        #   的同族问题）。这里把"看不见的那部分"点名, 并说明它是**历史欠账而非缺陷**:
        #   早于阶段 1 的 run 没有声明这回事, 改卡也不会回溯（manifest 是 run.json 的派发时快照）。
        f"**零声明（recipe v1）运行**: {len(out_runs) - n_runs_v2}/{len(out_runs)} 个"
        f" —— 这些 run **不参与可重放性判定**（v1 无「声明」这回事；属**历史欠账非缺陷**，"
        f"改卡不回溯）。故上方 `可离线复算` 的分母**只覆盖 v2 run**，不是语料级结论",
        # O-57 (2026-09-25): 归属核对的三态 —— 显式报"无法判定"的条数，避免把"判不了"读成"全对"。
        f"`accept-cmds` **归属**核对: 相符 {n_acc_ok} / **不符 {n_acc_bad}** / 无法判定 {n_acc_skip}"
        f" —— 「不符」= 归档内容是**别的 run** 的声明（O-57）；该形态**在** ⇒ 上面 "
        f"`missing-artifact` 判据看不见它，故须单列",
    ]
    out = {"runs": out_runs, "coverage": coverage, "gaps": gaps,
           "gap_keys": gap_keys,      # K1: 与水印比对用（**单调集合**，不含文本细节）
           "gap_items": [{"key": k, "text": t} for k, t in zip(gap_keys, gaps)],
           "totals": {"runs": len(out_runs), "subjects": n_sub, "offline_ok": n_offline,
                      "collect": n_collect, "undeclared": n_undecl, "runs_v2": n_runs_v2,
                      "ephemeral": n_ephemeral,
                      # O-61: `exit 3`(锁占用) ⇒ 证据件"设计性缺席"
                      "locked_out": n_locked,
                      # 2026-10-23: `status=failed` ⇒ 证据件"失败 run 缺席"（与 locked_out 同族）
                      "failed_run_absent": n_failed_absent,
                      # O-57: 归属核对三态（不符 = 归档件疑为别的 run 的残留）
                      "accept_ok": n_acc_ok, "accept_bad": n_acc_bad, "accept_skip": n_acc_skip}}
    if save:
        # 落库**第一层**(3-b-2 定案): 机器产物落**项目侧** `<projRoot>/agent-out/_audits/<ts>.json`
        #   —— 与 runDir 同级、名字不以数字开头 ⇒ `_chain_runs` 不会把它当 run, **不碰链**;
        #   **绝不写仓库**(红线: 每个 run 都入仓会污染仓库并逼每次提交; 只有校准报告才入仓)。
        stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        saved = []
        by_proj = {}
        for x in out_runs:
            by_proj.setdefault(x["label"].split("/")[0], []).append(x)
        for proj, rows in by_proj.items():
            root = roots.get(proj)
            if not root:
                continue
            rel = [g for g in gaps if g.startswith(f"{proj}/")]
            d = root / "agent-out" / "_audits"
            try:
                d.mkdir(parents=True, exist_ok=True)
                fp = d / f"{stamp}-audit.json"
                fp.write_text(json.dumps({"ts": stamp, "proj": proj, "coverage": coverage,
                                          "gaps": rel, "runs": rows}, ensure_ascii=False, indent=2),
                              encoding="utf-8")
                saved.append(str(fp))
            except OSError as e:
                print(f"  (落库失败 {proj}: {e.__class__.__name__})")
        out["saved"] = saved
    return out


# ── 阶段 3-b: 异基座 judge 的 **A/A 基线 + 顺序对调** 校准 (ADR-0007) ──────────────
# 为什么先做校准而不是先上"审计结论": 调研 §5.5 已量化"家族级自偏好"与 position bias(63%) ——
#   在**没量出噪声底**之前, 任何"judge 说 X"都无法归因(是发现还是抖动)。故 3-b 第一步只回答一个问题:
#   **"这条判据, 一个跨家族 judge 能不能稳定地判?"** —— 能则继续, 不能则据实停下(不建在沙上)。
AGENT_AUDIT_JUDGE_RULE = """你是**证据可复现性审计员**。给你一次 run 的元数据与若干"声明条目"。
判据（**只按此判据**, 不要引入其它标准）:
  一条 subject 声明**可独立复现**当且仅当：它是 path 型 **且** 该归档件存在 **且** 非空（字节 > 0）。
  其余一律是**缺口（REAL）** —— 含 collect 型（其声明的命令从未执行, 只有约定名产物 ⇒ 不可独立复现）、
  件缺失、件为空、既无 path 也无 collect。
  **唯一的例外**：条目标了 `ephemeral=是`（卡声明"产物在站上临时目录, **设计上不进 runDir**"）且件不在
    ⇒ **不算缺口, 输出 FALSE**（设计使然, 不是丢失）。
  信息不足（如"存在=未知"）⇒ **UNSURE**。
只输出逐行 `ITEM <序号>: <REAL|FALSE|UNSURE>`；不要解释、不要多余文字。

事实：
"""

# 同判据的**改写版**（措辞扰动轴）: 同参同序的 A/A 只证明"确定性"(temp=0 下近乎必一致),
#   措辞一改才看得出判据理解是否**稳健** —— 这是 A/A 之外必须补的一轴(否则噪声底被低估)。
AGENT_AUDIT_JUDGE_RULE_B = """任务：复核"证据可复现性"条目。逐条给结论。
判定原则（仅按此原则）：
  · 只有当**同时**满足"path 型、归档件存在、文件字节数 > 0"时，该声明才算**可复现** ⇒ 输出 FALSE（不是缺口）。
  · 其它情况都算**缺口** ⇒ 输出 REAL。例如：collect 型（声明了命令却没执行过）、文件不存在、文件 0 字节、
    未给出 path 也没给出 collect。
  · 若关键信息没给全（比如"存在=未知"）⇒ 输出 UNSURE（宁弃权不猜）。
  · 例外：若条目写明 `ephemeral=是`（设计性临时产物、产物不进 runDir）且件不在 ⇒ 不是缺口 ⇒ FALSE。
格式：逐行 `ITEM <序号>: <REAL|FALSE|UNSURE>`，无其它内容。

事实：
"""


def _judge_call(st: str, port: int, prompt: str, max_tokens: int = 512, timeout: int = 240) -> str:
    """站上 curl 调**内层引擎端口**(与 `flow` 的 bench 同路 —— 该端口无鉴权; studio 的 8080 才有 key)。

    body 走 **base64 通道**(与本仓既有手法一致): 避免引号/中文/换行在 shell 层被改写。
    """
    body = json.dumps({"model": "main", "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens, "temperature": 0, "stream": False})
    b64 = base64.b64encode(body.encode("utf-8")).decode("ascii")
    cmd = (f"echo {b64} | base64 -d > /tmp/_judge_body.json && "
           f"curl -s -m {timeout} -H 'Content-Type: application/json' "
           f"--data-binary @/tmp/_judge_body.json http://127.0.0.1:{port}/v1/chat/completions")
    ok, out = ssh_run(st, cmd, timeout=timeout + 30)
    if not ok or not out.strip().startswith("{"):
        return ""
    try:
        r = json.loads(out)
        return (r["choices"][0]["message"]["content"] or "").strip()
    except Exception:
        return ""


def _judge_identity(st: str, port: int) -> str:
    """取引擎实际加载的**模型 id** —— 跨家族的说法必须落到真值上(不写"我以为用的是 Qwen")。"""
    ok, out = ssh_run(st, f"curl -s -m 10 http://127.0.0.1:{port}/v1/models")
    if not ok or not out.strip().startswith("{"):
        return ""
    try:
        d = json.loads(out).get("data") or []
        return ",".join(str(x.get("id") or "") for x in d)[:80]
    except Exception:
        return ""


def _audit_judge_stable_items() -> list:
    """**稳定题集** = 与语料无关的"构造对照"（事实陈述式, 不依赖任何归档件 ⇒ 不动盘上文件）。

    **为什么必须与语料派生条目分开成一个函数**（2026-09-18 闭环复核的两次修正）:
      ① 校准指纹要判"判据/题集改没改、校准过没过期" ⇒ 若把**语料派生**条目也纳入,
         语料一变指纹就变 ⇒ 每次都判"过期"（假告警）。
      ② 更关键: 指纹的**比对方**（`agent_audit_calib_status`，门禁会用）**手上没有 audit 结果**。
         首版让它按空题集算指纹 ⇒ 与报告里"含 16 条"的指纹**恒定不等** ⇒ 保存完立刻自报
         "校准已过期"（实测踩到）。这是"恒真判据"的**镜像: 恒假判据** —— 判据永远不成立,
         后果同样是"判据失效而无人察觉"。
      ⇒ 本题集**无需 audit 即可构造** ⇒ 比对双方从同一来源取, 才谈得上"可比"。
    """
    return [
        ("subject 'prompt' | 类型=path | 归档件 prompt.txt | 存在=是 | 字节=1389 | 机器层判定=offline-ok", "FALSE"),
        ("subject 'workspace-diff' | 类型=collect | 约定名件 workspace-diff.txt | 存在=是 | 字节=0", "REAL"),
        ("subject 'judgment-record' | 类型=path | 归档件 judgment-record.txt | 存在=否 | 机器层判定=missing-artifact", "REAL"),
        ("subject 'attach-manifest' | 类型=collect | 约定名件 attach-manifest.txt | 存在=是 | 字节=232", "REAL"),
        ("subject 'mystery' | 类型=— | 既无 path 也无 collect | 机器层判定=no-path-no-collect", "REAL"),
        ("subject 'session-meta' | 类型=path | 归档件 session-meta.txt | 存在=未知 | 机器层判定=不可判", "UNSURE"),
        ("subject 'agent-output' | 类型=path | 归档件 agent-output.txt | 存在=是 | 字节=51 | 机器层判定=offline-ok", "FALSE"),
        # ⚠ **关键对照: 机器层判定故意与判据相反** —— 用来分辨 judge 是"复核"还是"复读机器判定":
        #   若它照抄机器标签(offline-ok / missing-artifact) ⇒ 异基座复核**零增量**(只是复述);
        #   若它按提示里写明的判据判(0 字节 ⇒ REAL / 件在且非空 ⇒ FALSE) ⇒ 才是真的独立复核。
        ("subject 'ledger-extra' | 类型=path | 归档件 ledger-extra.txt | 存在=是 | 字节=0 | 机器层判定=offline-ok", "REAL"),
        ("subject 'diff-full' | 类型=path | 归档件 diff-full.txt | 存在=是 | 字节=1024 | 机器层判定=missing-artifact", "FALSE"),
        # ── 项目边界样本（3-b-2 定案：题集常数化 ~16 条，按**判据形状**覆盖各项目实际形态）──
        #   ① Cpp_Hub 型: 产物在站上 /tmp, 卡声明 ephemeral ⇒ **新 readiness 类**(不是缺口)
        ("subject 'ctest-log' | 类型=collect | ephemeral=是 | 归档件 ctest-log.txt | 存在=否"
         " | 机器层判定=artifact-ephemeral-by-design", "FALSE"),
        #   ② Cpp_Hub 型: 结果块(大文本, 由模型自报 commit/test_total) —— 仍按 path 判据
        ("subject 'm4-result-block' | 类型=path | 归档件 agent-output.txt | 存在=是 | 字节=21823", "FALSE"),
        #   ③ Paper 型: index.db 大二进制 + **0 字节**(空件不满足"非空")
        ("subject 'index-db' | 类型=path | 归档件 index.db | 存在=是 | 字节=0", "REAL"),
        #   ④ Paper 型: 中文路径件(编码边界) + 缺失
        ("subject '模块图' | 类型=path | 归档件 模块图.md | 存在=否", "REAL"),
        #   ⑤ Auto_Prover 型: 证明日志(长文本) + 存在未知 ⇒ 应弃权
        ("subject 'lake-build-log' | 类型=path | 归档件 lake-build.log | 存在=未知", "UNSURE"),
    ]


def _audit_judge_items(audit: dict) -> list:
    """构造**校准题集**: 每条 = (展示事实, 期望判定)。返回 `(items, n_real)`。

    两类: ① **真实语料条目**(取 audit 的 collect 型 gap) —— 检验"真数据上能否稳定判";
         ② **稳定题集**（= `_audit_judge_stable_items()`）—— 期望值由**提示里写明的判据**唯一决定,
            故可与 judge 的答案比对(这是"校准", 不是"用 LLM 当 oracle")。
    `n_real` = ① 的条数, 交给调用方**只为在报告里写清"哪几条不入指纹"**;
    指纹只覆盖 ② —— 因为 ① 随语料变化, 且**比对方（门禁）手上没有 audit 结果**（见 `_judge_calib_digest`）。
    """
    items = []
    # ① 真实条目: 取 audit 里的 collect 型(declared-not-executed) —— 判据下它们必是 REAL
    real = [g for g in audit.get("gaps", []) if "collect 命令但**从未执行**" in g]
    for g in real[:2]:
        items.append((f"[真实语料] " + g.replace("\n", " "), "REAL"))
    items += _audit_judge_stable_items()
    return items, len(real[:2])


def _judge_calib_digest() -> dict:
    """校准**指纹**: 钉住"判据文本(A/B 两版) + **稳定题集**"。

    取数**不需要 audit 结果**（稳定题集是构造出来的）—— 这点要紧: 门禁就是靠它才能在没有 audit
    上下文的情况下算出"当前指纹"并与报告比对。签名**刻意不带参数**，免得又出现"双方各算一套"。

    为什么需要（2026-09-18 闭环复核）：ADR-0007 写着"改判据必须同步改题集并重跑校准"，
    但校准报告此前**既不记判据文本、也不记题集**（且展示列还截断到 70 字符）⇒
    **"改了没重跑"无人能发现** —— 而本仓自己的纪律原文是：
    "**只写规则不绑定执行等于空头承诺**，故做成断言"（`check_scripts` 注释）。
    本函数把那句空头承诺变成**可判**：报告存指纹，比对不上就是"校准已过期"。

    ⚠ 指纹**排除语料派生条目**（见 `_audit_judge_items`）—— 否则语料一变动就假报过期。
    """
    import hashlib as _h

    def _sha(s: str) -> str:
        return _h.sha256(s.encode("utf-8")).hexdigest()

    # 题集按**完整文本**入指纹 —— 报告正文里那列为了排版截断过, 不能拿它算
    stable = _audit_judge_stable_items()
    blob = "\n".join(f"{a}\t{b}" for a, b in stable) + "\n"
    rule_a, rule_b = _sha(AGENT_AUDIT_JUDGE_RULE), _sha(AGENT_AUDIT_JUDGE_RULE_B)
    items_sha = _sha(blob)
    return {"rule_sha256": rule_a, "rule_b_sha256": rule_b,
            "items_sha256": items_sha, "items_n": len(stable),
            "calib_sha256": _sha(rule_a + "\n" + rule_b + "\n" + items_sha)}


def agent_audit_calib_status() -> dict:
    """把**最近一份校准报告**的指纹与当前判据/题集比对 ⇒ 判"校准是否过期"。

    **纯本地、零网络、不需要引擎** —— 这正是它能被门禁直接调用的原因（才算"可判"）。
    `state`: `fresh`（一致）/ `stale`（**判据或题集改过、报告没重跑**）/ `no-fingerprint`（旧报告，
    产生于指纹机制之前 ⇒ **不得当过期报**，只提示）/ `no-report`。
    """
    d = (Path(__file__).resolve().parent.parent / "spec" / "d6-agent-standard"
         / "evidence-chain" / "audits")
    cur = _judge_calib_digest()
    try:
        fs = sorted(d.glob("AUDIT-JUDGE-*.json"))
    except OSError:
        fs = []
    if not fs:
        return {"state": "no-report", "file": "", "recorded": "", "current": cur["calib_sha256"]}
    f = fs[-1]
    try:
        j = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {"state": "no-report", "file": f.name, "recorded": "", "current": cur["calib_sha256"]}
    rec = str((j.get("calib") or {}).get("calib_sha256") or "")
    if not rec:
        return {"state": "no-fingerprint", "file": f.name, "recorded": "", "current": cur["calib_sha256"]}
    return {"state": "fresh" if rec == cur["calib_sha256"] else "stale",
            "file": f.name, "recorded": rec, "current": cur["calib_sha256"]}


def calib_status_line(cs: dict) -> str:
    """`agent_audit_calib_status()` 的人读一行（**单一文案点** —— 命令与门禁共用，免得两处口径漂移）。"""
    return {"fresh": "✅ 与当前判据/稳定题集一致",
            "stale": "⚠ **校准已过期** —— 判据或稳定题集已改，但报告未重跑",
            "no-fingerprint": "· 最近一份报告生成于指纹机制之前（**无法比对，不当作过期**）",
            "no-report": "· 尚无校准报告"}.get(cs.get("state", ""), "· 状态未知")


def _parse_verdicts(text: str, n_items: int) -> list:
    """从 judge 回复里抽 `ITEM k: V` ⇒ 按**展示序号**返回定长列表(缺失记 'MISSING')。"""
    got = ["MISSING"] * n_items
    for ln in (text or "").splitlines():
        m = re.search(r"ITEM\s*(\d+)\s*[:：]\s*(REAL|FALSE|UNSURE)\b", ln, re.I)
        if m:
            i = int(m.group(1))
            if 1 <= i <= n_items:
                got[i - 1] = m.group(2).upper()
    return got


def agent_audit_judge(audit: dict, max_tokens: int = 400, rounds: int = 3, save: bool = False) -> dict:
    """A/A 基线（同题集连判两次）+ 顺序对调（第三次把题序整体倒过来）⇒ 三个数:

      - **A/A 一致率**: 第 1、2 轮同序 ⇒ 该 judge 的**自一致**(噪声底)
      - **序翻转率**: 第 1 轮 vs 第 3 轮(倒序) **按条目**比对 ⇒ position bias 的直接影响
      - **与判据一致率**: 各轮 vs 期望值 ⇒ 是否真的会按写明的判据判

    仍是 **advisory**: 本命令只**测量** judge 的可靠性, 不改门禁 FAIL 集、不写任何 run 目录。
    """
    st, port = _flow_find_engine()
    if not port:
        return {"error": "无在服务引擎(先 load 一个**跨家族** judge 模型, 如 qwen3.8-27b-mtp)"}
    ident = _judge_identity(st, port)
    items, n_real = _audit_judge_items(audit)
    n = len(items)

    def _one(order, rule=AGENT_AUDIT_JUDGE_RULE):
        facts = "\n".join(f"ITEM {i+1}: {items[j][0]}" for i, j in enumerate(order))
        return _parse_verdicts(_judge_call(st, port, rule + facts, max_tokens), n)

    r1 = _one(list(range(n)))
    r2 = _one(list(range(n)))
    rev = list(range(n))[::-1]
    r3_disp = _one(rev)
    r4 = _one(list(range(n)), AGENT_AUDIT_JUDGE_RULE_B)     # 措辞扰动(同序)
    # 把倒序轮的**展示序**映射回条目 idx
    r3 = ["MISSING"] * n
    for disp, idx in enumerate(rev):
        r3[idx] = r3_disp[disp]

    aa = sum(1 for i in range(n) if r1[i] == r2[i])
    flip = sum(1 for i in range(n) if r1[i] != r3[i])
    para = sum(1 for i in range(n) if r1[i] == r4[i])
    agree = {k: sum(1 for i in range(n) if [r1, r2, r3, r4][k][i] == items[i][1]) for k in (0, 1, 2, 3)}
    used = sum(1 for i in range(n) if r1[i] == "UNSURE") + sum(1 for i in range(n) if r2[i] == "UNSURE")
    rows = [{"idx": i + 1, "fact": items[i][0][:70], "expect": items[i][1],
             "aa_1": r1[i], "aa_2": r2[i], "swap": r3[i], "para": r4[i]} for i in range(n)]
    # 校准指纹（2026-09-18 闭环复核）: 钉住**判据文本 A/B + 稳定题集**
    #   ⇒ 报告由此**自带"当时校的是哪份判据"**；比对不上 = 校准已过期（`agent_audit_calib_status`）。
    #   语料派生条目（② 之前那 n_real 条）**不入指纹** —— 否则语料一变就假报过期。
    calib = _judge_calib_digest()
    res = {"station": st, "port": port, "judge_model": ident, "items": rows,
           "aa_agree": f"{aa}/{n}", "swap_flip": f"{flip}/{n}", "paraphrase_agree": f"{para}/{n}",
           "rule_agree": f"r1 {agree[0]}/{n} · r2 {agree[1]}/{n} · r3(倒序) {agree[2]}/{n} · r4(改写) {agree[3]}/{n}",
           "unsure_total": used, "n_real": n_real, "calib": calib,
           "note": "advisory: 本命令只测量 judge 可靠性, 不改门禁"}
    if save:
        # 落库**第二层**(3-b-2 定案): **校准报告**入仓 `spec/d6-agent-standard/evidence-chain/audits/`。
        #   与第一层的分工: 这是一次"里程碑结论"(人可读、可被 ADR 引用、随代码评审走);
        #   而每次 `audit` 的机器产物**只落项目侧**(红线: 每 run 入仓会污染仓库)。
        stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        d = (Path(__file__).resolve().parent.parent / "spec" / "d6-agent-standard"
             / "evidence-chain" / "audits")
        try:
            d.mkdir(parents=True, exist_ok=True)
            (d / f"AUDIT-JUDGE-{stamp}.json").write_text(
                json.dumps(dict(res, ts=stamp), ensure_ascii=False, indent=2), encoding="utf-8")
            md = [f"# 阶段 3-b 校准报告（{stamp}）", "",
                  "> 由 `python ops/cluster.py agent audit-judge --save` 生成（advisory：只测量 judge 可靠性，不改门禁）。", "",
                  f"- judge 引擎：`{st}:{port}` · 模型：`{ident or '(未报)'}`（**取真值**，跨家族要求见 ADR-0007）",
                  f"- 题集：**{n}** 条（构造校准集 + 项目边界样本）",
                  f"- **A/A 一致 {res['aa_agree']}** · **序翻转 {res['swap_flip']}** · "
                  f"**措辞扰动一致 {res['paraphrase_agree']}**",
                  f"- 与判据一致：{res['rule_agree']} · UNSURE(r1+r2) {used}", "",
                  # 校准指纹（2026-09-18 闭环复核）: 报告必须**自带"当时校的是哪份判据"** —— 否则
                  #   "改了判据没重跑"无人能发现（本仓原文: "只写规则不绑定执行等于空头承诺"）。
                  f"- **校准指纹**：`calib={calib['calib_sha256'][:16]}…`"
                  f" · 规则A `{calib['rule_sha256'][:12]}…` / 规则B `{calib['rule_b_sha256'][:12]}…`"
                  f" · 稳定题集 `{calib['items_sha256'][:12]}…`（{calib['items_n']} 条）",
                  f"  ⤷ 判据或稳定题集一改，指纹即变 ⇒ `cluster.py agent audit-judge` 与门禁会报"
                  f"「校准已过期」；**本报告的 items 里前 {res.get('n_real', 0)} 条取自语料，不入指纹**", "",
                  "| # | 期望 | 第1轮 | 第2轮 | 倒序 | 改写 | 事实 |", "|---|---|---|---|---|---|---|"]
            for x in rows:
                # 注意: 反斜杠不能出现在 f-string 的表达式段 (Py<3.12 SyntaxError) ⇒ 先算再插
                fact = str(x['fact']).replace('|', '\\|')
                md.append(f"| {x['idx']} | {x['expect']} | {x['aa_1']} | {x['aa_2']} | {x['swap']} | "
                          f"{x['para']} | {fact} |")
            md += ["", "## 判读", "",
                   "- **A/A** = 确定性（噪声底）· **序翻转** = position bias · **措辞扰动** = 稳健性（temp=0 下 A/A 测不到的那半）",
                   "- 题集内**故意**放了机器标签与判据相反的条目 ⇒ 可辨 judge 是**复核**还是**复读**",
                   "- **诚实边界**：题面是结构化元数据（非杂乱材料）⇒ 只证明「能稳定执行写明的判据」；单 judge、单轮 ⇒ 下限证据", ""]
            (d / f"AUDIT-JUDGE-{stamp}.md").write_text("\n".join(md), encoding="utf-8")
            res["saved"] = [str(d / f"AUDIT-JUDGE-{stamp}.md"), str(d / f"AUDIT-JUDGE-{stamp}.json")]
        except OSError as e:
            print(f"  (校准报告入仓失败: {e.__class__.__name__})")
    return res


def _p3_pin_notes() -> dict:
    """P3（2026-09-21）: 把冷镜像链存进 git notes ref `refs/notes/evidence-chain` 并 push 到 origin。

    给"链本体"再一份 off-machine 副本（SLSA E2E 的 VSA-in-commit-notes 同款形态）。
    ⚠ **诚实边界（与调研 §14 一致）**:
      · P2 已把同一字节的冷镜像诤在 `main`（且 P1 ruleset 保护）⇒ P3 本质是**冗余副本**；
      · git notes **默认不被 clone/fetch**，离机读者须显式 `git fetch origin refs/notes/evidence-chain`
        再 `git notes --ref=evidence-chain show <commit>` ⇒ **比 P2 隐蔽、更易被忘**。
      只在 `agent chain --pin-notes` 时显式做，不默认每次派发自动跑。
    """
    import shutil, subprocess
    root = Path(__file__).resolve().parent.parent
    src = AGENT_CHAIN_COLD
    git, note_ref = shutil.which("git"), "evidence-chain"
    if not git:
        return {"ok": False, "error": "无 git 可执行"}
    if not src.is_file():
        return {"ok": False, "error": f"{src.name} 不存在（先跑 `agent chain`）"}

    def _g(*a):
        return subprocess.run([git, *a], cwd=str(root), capture_output=True)

    r = _g("notes", "--ref", note_ref, "add", "-f", "-F", str(src), "HEAD")
    if r.returncode != 0:
        return {"ok": False, "error": (r.stderr or r.stdout).decode("utf-8", "replace").strip()[:200]}
    p = _g("push", "origin", f"refs/notes/{note_ref}:refs/notes/{note_ref}")
    if p.returncode != 0:
        return {"ok": False, "partial": True,
                "error": "本地 note 已写，push 失败: "
                         + (p.stderr or p.stdout).decode("utf-8", "replace").strip()[:200]}
    s = _g("notes", "--ref", note_ref, "show", "HEAD")
    return {"ok": True, "ref": f"refs/notes/{note_ref}", "pushed": True,
            "offline_roundtrip": bool(s.returncode == 0 and s.stdout == src.read_bytes())}


def _p4_mirror(st: str) -> dict:
    """P4（2026-09-21）: 把冷镜像链推送到站 `st` 的 `evidence-mirror/`（滚动快照）。

    ⚠ **诚实边界（调研 §14.5，含 2026-09-21 修正）**: 3 台机**同一运营者** ⇒ 这只是**冗余/可用性**，
      **不是不可否认**。最初版本把远端 chmod 成只读(555/444)想模拟 append-only —— **实测自伤**:
      只读后下一次 `--mirror` 自己就写不进去(PermissionError)，同运营者也照样能解除 ⇒ "假只读"
      既非不可否认、又挡更新。故**改成可更新的滚动快照**、写入前置 best-effort 恢复可写。
      "密码学级只读/不可否认"需外部独立托管(方案 P4 已记), 不在同一运营者内假装。
    """
    src = AGENT_CHAIN_COLD
    if not src.is_file():
        return {"ok": False, "error": f"{src.name} 不存在（先跑 `agent chain`）"}
    try:
        cli = _connect(st)
        sftp = cli.open_sftp()
        _p4_mkdir(sftp, "evidence-mirror")
        # 写入前 best-effort 恢复可写(自愈: 曾 chmod 555/444 的老镜像可被本命令再写)
        _p4_writable(sftp, "evidence-mirror")
        remote = "evidence-mirror/agent-chain.json"
        _p4_writable(sftp, remote)
        with sftp.open(remote, "wb") as f, open(src, "rb") as lf:
            f.write(lf.read())
        with sftp.open(remote, "rb") as f:
            got = f.read()
        sftp.close()
        cli.close()
        return {"ok": True, "station": st, "remote": f"{st}:{remote}", "bytes": len(got),
                "match_roundtrip": got == src.read_bytes()}
    except Exception as e:
        try:
            cli.close()
        except Exception:
            pass
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _p4_mkdir(sftp, path: str) -> None:
    """幂等建远端目录（paramiko mkdir 已存在会抛）。"""
    try:
        sftp.mkdir(path)
    except OSError:
        pass


def _p4_writable(sftp, path: str) -> None:
    """写入前 best-effort 恢复远端可写（自愈曾 chmod 555/444 的老镜像）。失败静默忽略。"""
    try:
        sftp.chmod(path, 0o755 if path.endswith("/") or "." not in path.split("/")[-1] else 0o644)
    except (OSError, IOError):
        # 文件可能不存在 — 交给后续 open→write 真正报错
        pass


def _p4_run_mirror(st: str) -> dict:
    """P4（2026-09-21）runDir 对账镜像: 把各项目 `agent-out/` 打进单一 tar.gz, SFTP 推站
    `evidence-mirror/runs/agent-out-current.tar.gz`（滚动覆盖） + `MANIFEST.txt`。

    为什么: 链的**对账对象**（runDir）只主控单份 ⇒ 磁盘故障后链还在、但无法对账
      （`verify` 重算 digest 对链 / `audit` 判可重放性）。体量实测：Paper 90 run=398 件
      **0.7 MB**、Cpp_Hub ≈0 ⇒ 整快照极小，**每次全量即可**（不做增量）。
    ⚠ honest boundary 同 P4（调研 §14.5）: 同一运营者 ⇒ 冗余/可用性, **非不可否认**。
    """
    import tarfile
    import hashlib as _h
    import io
    roots, note = _agent_proj_roots()
    if not roots:
        return {"ok": False, "error": note or "PROJECTS 解析为空"}
    manifest = []
    try:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for proj, root in sorted(roots.items()):
                ao = root / "agent-out"
                if not ao.is_dir():
                    continue
                tar.add(ao, arcname=f"agent-out/{proj}", recursive=True)
                nf = sum(1 for _ in ao.rglob("*") if _.is_file())
                manifest.append(f"{proj}: {nf} files")
        blob = buf.getvalue()
    except OSError as e:
        return {"ok": False, "error": f"tar 失败: {e.__class__.__name__}"}
    sha = _h.sha256(blob).hexdigest()
    manifest_txt = (f"# agent-out 对账镜像 (P4 runDir, {time.strftime('%Y-%m-%dT%H:%M:%S')})\n"
                    + "\n".join(manifest)
                    + f"\ntotal_bytes={len(blob)}\nsha256={sha}\n"
                    + (f"note={note}\n" if note else ""))
    try:
        cli = _connect(st)
        sftp = cli.open_sftp()
        _p4_mkdir(sftp, "evidence-mirror")
        _p4_mkdir(sftp, "evidence-mirror/runs")
        _p4_writable(sftp, "evidence-mirror")          # 自愈曾 555/444 的老镜像
        _p4_writable(sftp, "evidence-mirror/runs")
        tar_path, man_path = "evidence-mirror/runs/agent-out-current.tar.gz", \
                             "evidence-mirror/runs/MANIFEST.txt"
        _p4_writable(sftp, tar_path)
        _p4_writable(sftp, man_path)
        with sftp.open(tar_path, "wb") as f:
            f.write(blob)
        with sftp.open(man_path, "wb") as f:
            f.write(manifest_txt.encode("utf-8"))
        with sftp.open(tar_path, "rb") as f:
            got = f.read()
        sftp.close()
        cli.close()
        return {"ok": True, "station": st, "remote": f"{st}:evidence-mirror/runs",
                "projects": len(manifest), "total_bytes": len(blob), "sha": sha,
                "match_roundtrip": _h.sha256(got).hexdigest() == sha}
    except Exception as e:
        try:
            cli.close()
        except Exception:
            pass
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _dashboard_html(payload: dict) -> str:
    """自包含 HTML：**数据内联成 JSON**，渲染全在本地 JS ⇒ 打开时**零网络请求**（`file://` 直开）。"""
    data = json.dumps(payload, ensure_ascii=False)
    # 数据里若出现 `</` 会提前闭合 <script> ⇒ 转义成 `<\/`（JSON 里合法，解析回 `</`）
    data = data.replace("</", "<\\/")
    return """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>agent 派发看板 (快照)</title>
<style>
 body{font:13px/1.5 ui-monospace,Consolas,monospace;margin:16px;background:#fafafa;color:#222}
 h1{font-size:16px;margin:0 0 4px} h2{font-size:14px} .mut{color:#777}
 table{border-collapse:collapse;width:100%;margin:8px 0 18px;background:#fff}
 th,td{border:1px solid #ddd;padding:3px 6px;text-align:left;white-space:nowrap}
 th{background:#f0f0f0} tr:nth-child(even) td{background:#fbfbfb}
 .ok{color:#1a7f37} .bad{color:#c0392b} .warn{color:#b7791f}
 pre{background:#f5f5f5;padding:6px;overflow:auto;max-height:320px;border:1px solid #e5e5e5}
</style></head><body>
<h1>agent 派发看板 · <span class="mut">快照</span></h1>
<div class="mut" id="head"></div>
<h2>运行中节拍 (站上 .progress, 只读)</h2><div id="live"></div>
<h2>派发台账 (尾 N 条 + run 详情)</h2><div id="runs"></div>
<div class="mut">⚠ 本文件是 <b>快照</b>（数据已内联 ⇒ 打开时零网络）；<b>实时</b>视图见 cluster_web.py「Agent 任务」卡片。</div>
<script>
 const D=__DATA__;
 const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
 const cls=v=>v==="completed"?"ok":(v==="failed"?"bad":"warn");
 document.getElementById("head").textContent =
   "生成于 "+D.generated+" · ledger="+D.ledger+" · 新鲜度: 最新 "
   +(D.freshness&&D.freshness.label?D.freshness.label+" ("+D.freshness.age_s+"s 前)":"—");
 let h='<table><tr><th>ts</th><th>proj</th><th>model</th><th>sens</th><th>status</th>'
   +'<th>code</th><th>queue_s</th><th>run_s</th></tr>';
 for(const r of D.runs){
   h+="<tr><td>"+esc(r.ts)+"</td><td>"+esc(r.proj)+"</td><td>"+esc(r.model)+"</td><td>"+esc(r.sens)
     +'</td><td class="'+cls(r.status)+'">'+esc(r.status)+"</td><td>"+esc(r.code)+"</td><td>"+esc(r.queue_s)
     +"</td><td>"+esc(r.run_s)+"</td></tr>";
 }
 h+="</table>";
 document.getElementById("runs").innerHTML=h;
 document.getElementById("live").innerHTML = D.live.length
   ? "<pre>"+esc(JSON.stringify(D.live,null,1))+"</pre>" : '<div class="mut">(无运行中任务)</div>';
</script>
</body></html>
""".replace("__DATA__", data)


def cmd_agent_dashboard(limit: int, out_path: str) -> int:
    """`cluster.py agent dashboard [--limit N] [--out <file>]`

    产出**自包含单文件 HTML**（内联数据 + 内联样式/脚本 ⇒ **零网络请求**）：`file://` 直开、可离线留存/可作附件。
    ★ **为什么放统一入口而不是独立脚本**（O-38 的处置）：ADR-0004 D5 定了「**统一管理入口为唯一管理面**」，
      原 `make-dashboard.ps1` + `dashboard.html` 正是据此在 `3712f06` 被清减的
      ⇒ **能力在此承接，不复活独立脚本**（否则等于撤销 D5）。
    ⚠ 本命令产出的是**快照**（非实时）；**实时**视图见 `cluster_web.py` 的「Agent 任务」卡片 —— 两者**同源**
      （都走 `agent_runs` / `agent_live`），故不会漂移。
    """
    rows, note = agent_runs(limit)
    beats = agent_live(("A", "B", "C"))
    payload = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "ledger": note, "limit": limit,
               "freshness": agent_ledger_freshness(rows), "runs": rows, "live": beats}
    html = _dashboard_html(payload)
    p = Path(out_path)
    if p.parent and not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html, encoding="utf-8", newline="")
    print(f"DASHBOARD: {p.resolve()}")
    print(f"  {len(html)} 字节 · 自包含零网络 · {len(rows)} run / {len(beats)} 节拍 · 数据内联时间 {payload['generated']}")
    print("  ⚠ 快照非实时；实时视图: cluster_web.py「Agent 任务」卡片（同源数据）。")
    return 0


def cmd_agent(argv) -> int:
    """cluster.py agent {runs|live|tail|chain|verify|audit} [--limit N] [--station A|B|C] [--json] [--reanchor]

    P0 只读视图: `runs`=派发台账尾 N 条(join run.json 详情) / `live`=三站运行中节拍 /
    `tail`=台账原始行。**只读, 无副作用**; 口径与判据见 spec/agent-observability/。
    证据链 (spec/d6-agent-standard/evidence-chain/): `chain`=把未入链的 run 补进链(幂等,
    写链 + 冷路径镜像 + 外部锚 ANCHOR.txt; `--reanchor` 才强制重锚) / `verify`=复验
    (重算 digest + 验 prev 链 + 比冷路径与外部锚; 只读)。门禁第 15 项 `evidence` 自动覆盖。
    `audit`=**可复现性审计**(阶段 3-a, ADR-0007): 逐 subject 判"能否被独立复现、卡在哪",
    输出**机器可判 gap 表**(advisory, **不进 FAIL 集**); 与 verify 分工: verify 管"是否被改",
    audit 管"是否可重放"。只读, 不触站。`--save` 落**项目侧** `<proj>/agent-out/_audits/<ts>.json`
    (与 runDir 同级、**不碰链**; 红线: 机器产物**不入仓**)。
    **`--accept`**(路A, 2026-09-18): 把当前 gap 集合**并入水印**(`inventory/audit-baseline/<host>.json`,
    **入仓**；2026-09-23 由 `ops/.audit-baseline.json` **移入**，见台账 O-33) ⇒ 门禁只报此后**新增**的 gap。
    见下"增量水印"一段。需人先看到清单, 故不可与 `--json` 同用。
    `audit-judge`=**阶段 3-b 校准**(advisory): 用**在服务引擎**(宜为**跨家族**模型, 如 qwen3.8-27b-mtp)
    对 3-a 的条目判两次(A/A 噪声底) + 倒序再判一次(position bias) + 判据改写版一次(稳健性) ⇒
    只**测量** judge 可靠性, 不改门禁、不写 run 目录。`--save` 把**校准报告**入仓
    `spec/d6-agent-standard/evidence-chain/audits/`(第二层: 只有里程碑结论入仓)。
    """
    act = (argv[0] if argv else "runs").lower()
    if act not in ("runs", "live", "tail", "chain", "verify", "audit", "audit-judge", "dashboard"):
        print("用法: cluster.py agent {runs|live|tail|chain|verify|audit|audit-judge|dashboard} [--limit N] "
              "[--station A|B|C] [--json] [--save] [chain 可加 --reanchor/--pin-notes/--mirror <站>; "
              "audit 可加 --accept; dashboard 可加 --out <文件>]")
        return 1
    limit, only, as_json, mirror_st, out_path = 20, None, ("--json" in argv), None, "ops/agent-dashboard.html"
    i = 1
    while i < len(argv):
        if argv[i] == "--limit" and i + 1 < len(argv):
            try:
                limit = max(1, int(argv[i + 1]))
            except ValueError:
                print("--limit 需要整数")
                return 1
            i += 2
            continue
        if argv[i] == "--station" and i + 1 < len(argv):
            only = argv[i + 1].upper()
            i += 2
            continue
        if argv[i] == "--mirror" and i + 1 < len(argv):
            mirror_st = argv[i + 1].upper()
            i += 2
            continue
        if argv[i] == "--out" and i + 1 < len(argv):
            out_path = argv[i + 1]
            i += 2
            continue
        i += 1
    if only and only not in STATIONS:
        print(f"未知站 '{only}' (可选: {', '.join(STATIONS)})")
        return 1
    if mirror_st and mirror_st not in STATIONS:
        print(f"未知镜像站 '{mirror_st}' (可选: {', '.join(STATIONS)})")
        return 1
    stations = [only] if only else ["A", "B", "C"]

    if act == "dashboard":
        return cmd_agent_dashboard(limit, out_path)

    if act == "chain":
        r = agent_chain_append(reanchor=("--reanchor" in argv))
        if as_json:
            print(json.dumps(r, ensure_ascii=False))
            return 0
        if r.get("error"):
            print(f"证据链: 不可用 —— {r['error']}")
            return 1
        print("=== 证据链追加 (幂等; 只写主控侧, 不触站) ===")
        if r["added"]:
            for a in r["added"]:
                if a.get("error"):
                    print(f"  ⚠ {a['error']}")
                else:
                    print(f"  + {a['proj']:<10} {a['run_id']}  digest={a['digest']}")
        else:
            print("  (无新增 —— 全部 run 已在链上)")
        print(f"\n  链长={r['total']} · {r['chain']}")
        print(f"  外部锚={'已更新' if r.get('anchor_written') else '未动(已是最新)'} · {r.get('anchor')}")
        print("  判据: 本命令**唯一**写动作为链文件+冷路径镜像+外部锚; run 目录一律只读。")
        if not r.get("anchor_written") and not (r.get("added") or []):
            print("  提示: 锚与链**不符**时本命令刻意不动锚(避免抹掉篡改信号); 确要重锚用 --reanchor。")
        # ── P3 / P4 (2026-09-21): 用户裁定"两者都做"; 显式一次性命令, 非默认自动跑 ──
        if "--pin-notes" in argv:
            rt = _p3_pin_notes()
            if rt.get("ok"):
                print(f"  P3 git-notes 镜像: ✅ 已 push `{rt['ref']}` · 本地回读一致="
                      f"{rt.get('offline_roundtrip')}（诚实: P2 已冗余, notes 更隐蔽）")
            else:
                print(f"  P3 git-notes 镜像: ✗ {rt.get('error')}" + ("（本地已写、未 push）" if rt.get("partial") else ""))
        if mirror_st:
            rm = _p4_mirror(mirror_st)
            if rm.get("ok"):
                print(f"  P4 链镜像: ✅ {rm['remote']} · {rm['bytes']}B · 回读一致="
                      f"{rm.get('match_roundtrip')}（诚实: 同运营者 ⇒ 冗余非不可否认")
            else:
                print(f"  P4 链镜像: ✗ {rm.get('error')}")
            rr = _p4_run_mirror(mirror_st)
            if rr.get("ok"):
                print(f"  P4 runDir 对账镜像: ✅ {rr['remote']} · {rr['projects']} 项目 · "
                      f"{rr['total_bytes']}B · 回读一致={rr.get('match_roundtrip')}（sha={rr['sha'][:12]}…）")
            else:
                print(f"  P4 runDir 对账镜像: ✗ {rr.get('error')}")
        return 0

    if act == "audit":
        r = agent_audit(limit=(limit if "--limit" in argv else 0), save=("--save" in argv))
        # ADR-0007 路A: 水印状态 —— 让"还欠多少"随时可见, 而不只依赖门禁那一次喊话
        base = agent_audit_baseline_load()
        bkeys = set(base.get("keys") or [])
        cur = set(r.get("gap_keys") or [])
        pending = sorted(cur - bkeys)

        def _accept_baseline():
            # K2(**要紧**): 水印的**写点只在这里**。门禁 `rpc_check.py` 对仓库**全程只读**
            #   （唯一写动作是 check_syntax 的 tempfile）⇒ 门禁不能自己写水印（会把 pre-commit
            #   的工作区弄脏）。副作用是**"接受这批新 gap"成为人类的显式动作** —— 与"不静默降级"
            #   同向: 自动推进等于把信号抹平。
            acc = agent_audit_baseline_accept(sorted(cur))
            print(f"  ✓ 水印已推进: 新增接受 **{len(acc['added'])}** 条 key，累计 {acc['total']} 条"
                  f" → {acc['path']}")

        if as_json:
            if "--accept" in argv:
                # 刻意拒绝: 接受动作的前提是"人先看到清单", 且确认行会污染 JSON 流
                print("--accept 不能与 --json 同用（接受前必须先看到 gap 清单）", file=sys.stderr)
                return 2
            print(json.dumps(dict(r, audit_baseline={
                "total": len(bkeys), "pending": len(pending),
                "created": base.get("created") or ""}), ensure_ascii=False))
            return 0
        print("=== 证据可复现性审计 (阶段 3-a; ADR-0007) ===")
        print("  口径: **advisory** —— 只出 gap 表, 不改门禁 FAIL 集。verify 管'是否被改', audit 管'是否可重放'。\n")
        for c in r["coverage"]:
            print(f"  · {c}")
        print()
        cols = [(28, "run", 0), (6, "recipe", 0), (6, "声明", 1), (8, "可离线", 1),
                (8, "未执行", 1), (6, "临时", 1), (8, "未声明", 1)]
        print("  " + " ".join(_pad(t, w, bool(rg)) for w, t, rg in cols))
        print("  " + "-" * (sum(w for w, _, _ in cols) + len(cols) - 1))
        for x in r["runs"][-10:]:
            # 注意: "未执行"按 readiness 计(与覆盖率的 collect 行**同一口径**), 不按 mode 计 ——
            #   否则同一份输出里会同时出现"collect 1"(表) 与 "collect 型 0 条"(覆盖率)两种互相矛盾的数
            #   (本轮实测踩到, 已统一)。
            row = [x["label"], x["recipe"], x["declared"], x["offline_ok"], x["not_exec"],
                   x["ephemeral"], len(x["undeclared"])]
            print("  " + " ".join(_pad(v, w, bool(rg)) for v, (w, _, rg) in zip(row, cols)))
        if len(r["runs"]) > 10:
            print(f"  …另有 {len(r['runs']) - 10} 个 run（--limit 或 --json 查看）")
        if r["gaps"]:
            print(f"\n  ▲ gap 表 ({len(r['gaps'])} 条 —— 均为**可重放性缺口**, 不是篡改):")
            for g in r["gaps"][:10]:
                print(f"      · {g}")
            if len(r["gaps"]) > 10:
                print(f"      · …另有 {len(r['gaps']) - 10} 条")
        else:
            print("\n  ✓ gap 表为空（每条声明都可离线复现, 且无未声明归档件）")
        if r.get("saved"):
            # 落库第一层: 机器产物只落**项目侧**; 仓库侧只收"校准报告"(audit-judge --save)
            print("  已落库(项目侧 _audits/): " + " · ".join(r["saved"]))
        print(f"\n  水印: 存量 key {len(bkeys)} 条 · 待接受(新增) **{len(pending)}** 条"
              + (f" · 建立于 {base.get('created')}" if base.get("created") else " · (尚未建立)"))
        # 校准可判（2026-09-18 闭环复核）: 判据/稳定题集改过而报告没重跑 ⇒ 这里直接说出来
        _cs = agent_audit_calib_status()
        print(f"  校准: {calib_status_line(_cs)}"
              + (f"（{_cs['file']} · 报告指纹 {_cs['recorded'][:16]}…）" if _cs.get("recorded") else ""))
        if pending:
            print("  门禁 `evidence` 会把上面这些**逐条**报为 WARN；确认可接受后跑 "
                  "`python ops/cluster.py agent audit --accept` 推进水印(存量即不再重复报)。")
        if "--accept" in argv:
            _accept_baseline()
        return 0

    if act == "audit-judge":
        a = agent_audit(limit=(limit if "--limit" in argv else 0))
        mt = 400
        if "--max-tokens" in argv:
            try:
                mt = max(64, int(argv[argv.index("--max-tokens") + 1]))
            except (ValueError, IndexError):
                print("--max-tokens 需要整数")
                return 1
        r = agent_audit_judge(a, max_tokens=mt, save=("--save" in argv))
        if as_json:
            print(json.dumps(r, ensure_ascii=False))
            return 0 if not r.get("error") else 1
        if r.get("error"):
            print(f"阶段 3-b 校准: 不可执行 —— {r['error']}")
            return 1
        print("=== 阶段 3-b 校准: A/A 基线 + 序对调 + 措辞扰动 (advisory; 只测 judge 可靠性) ===")
        print(f"  judge 引擎: {r['station']}:{r['port']} · 模型={r['judge_model'] or '(未报)'}")
        print(f"  A/A 一致 **{r['aa_agree']}** · 序翻转 **{r['swap_flip']}** · 措辞扰动一致 **{r['paraphrase_agree']}**")
        print(f"  与判据一致 {r['rule_agree']} · UNSURE(r1+r2) {r['unsure_total']}")
        print(f"  {_pad('#', 3)} {_pad('期望', 7)} {_pad('第1轮', 8)} {_pad('第2轮', 8)} "
              f"{_pad('倒序', 8)} {_pad('改写', 8)} 事实")
        for x in r["items"]:
            # D6-P3-1: 这六列的**值**也可能是中文(期望/两轮答案/倒序/改写) ⇒ 一律按显示宽度填充
            print(f"  {_pad(x['idx'], 3)} {_pad(x['expect'], 7)} {_pad(x['aa_1'], 8)} "
                  f"{_pad(x['aa_2'], 8)} {_pad(x['swap'], 8)} "
                  f"{_pad(x['para'], 8)} {x['fact']}")
        print("\n  判读: A/A=确定性(噪声底) · 序翻转=position bias · 措辞扰动=**稳健性**(A/A 测不到的那半) ·")
        print("        与判据一致=是否真按判据判(对照项故意让机器标签与判据相反 ⇒ 可辨'复核'vs'复读')。")
        _cal = r.get("calib") or {}
        if _cal:
            print(f"  校准指纹: calib={_cal.get('calib_sha256', '')[:16]}…"
                  f" · 规则A/B={_cal.get('rule_sha256', '')[:8]}…/{_cal.get('rule_b_sha256', '')[:8]}…"
                  f" · 稳定题集={_cal.get('items_n', 0)} 条(不入指纹的语料条目 {r.get('n_real', 0)} 条)")
            print(f"  校准状态: {calib_status_line(agent_audit_calib_status())}")
        if r.get("saved"):
            print("  校准报告已入仓(第二层): " + " · ".join(r["saved"]))
        return 0

    if act == "verify":
        r = agent_chain_verify()
        if as_json:
            print(json.dumps(r, ensure_ascii=False))
            return 0 if not r["issues"] else 1
        print("=== 证据链复验 (digest + prev 链 + 冷路径 + 外部锚 + A1 verdict + A2 golden) ===")
        if r.get("note"):
            print(f"  ⚠ {r['note']}")
        if r["entries"] == 0:
            print("  (链为空 —— 先跑 `agent chain` 建立基线)")
            return 0
        for c in (r.get("coverage") or []):
            print(f"  · {c}")
        if not r["issues"]:
            h = r.get("head") or {}
            print(f"  PASS · {r['entries']} 条全绿 (末条 head)")
            print(f"  head={h.get('proj')}/{h.get('run_id')} digest={(h.get('digest') or '')[:16]}")
        else:
            print(f"  FAIL · {len(r['issues'])} 项 (链长 {r['entries']})")
            for x in r["issues"]:
                k = x.get("kind")
                loc = f"{x.get('proj')}/{x.get('run_id')}" if x.get("index") is not None else "-"
                if k == "digest_mismatch":
                    print(f"  ✗ [{x['index']}] {loc} digest_mismatch 变了: {', '.join(x['files_changed']) or '(未知)'}"
                          f"  expect={x['expect']} got={x['got']}")
                elif k == "chain_break":
                    print(f"  ✗ [{x['index']}] {loc} chain_break  expect={str(x['expect'])[:16]} got={str(x['got'])[:16]}")
                elif k == "run_dir_missing":
                    print(f"  ✗ [{x['index']}] {loc} run_dir_missing (归档目录不在了)")
                elif k == "recipe_unknown":
                    print(f"  ✗ [{x['index']}] {loc} recipe 不可验 (链={x['got']} 本工具知 {x['expect']})"
                          f" —— 工具比链旧, **不得当作通过**")
                elif k in ("verdict_mismatch", "golden_identity", "manifest_missing", "manifest_undeclared", "diff_scope"):
                    print(f"  ✗ [{x.get('index')}] {loc} {k}: {x.get('detail')}")
                elif k == "anchor_mismatch":
                    print(f"  ✗ 外部锚 anchor_mismatch 与链不符: {', '.join(x.get('diff') or []) or '(未列出)'}")
                elif k == "anchor_unreadable":
                    print("  ✗ 外部锚不可读 (ANCHOR.txt)")
                else:
                    print(f"  ✗ {k}  cold_n={x.get('cold_n')} chain_n={x.get('chain_n')}")
        if r.get("gaps"):
            print(f"  ▲ 覆盖缺口 / 不可判 {len(r['gaps'])} 项 (**不是篡改**):")
            for g in r["gaps"][:8]:
                print(f"      · {g}")
            if len(r["gaps"]) > 8:
                print(f"      · …另有 {len(r['gaps']) - 8} 项")
        if r.get("notes"):
            print(f"  ℹ 合法演进类 {len(r['notes'])} 项 (**不告警**, 供人判):")
            for nt in r["notes"][:5]:
                print(f"      · {nt}")
        if not r.get("anchor_present"):
            print("  ▲ 外部锚未建立 (ANCHOR.txt 缺失) → 跑 `cluster.py agent chain` 生成后提交并 push 到 origin")
        print("\n  口径: 本命令可判'链内记录与归档字节是否一致'(防篡改) + '两份归档件是否自洽'(防转述失真)。"
              "**不能**判 judgement 级真伪(判据真的跑过且结果真为 0), 也不防 T3 —— 见 evidence-chain/DESIGN.md §6。")
        return 0 if not r["issues"] else 1

    if act == "live":
        beats = agent_live(stations)
        if as_json:
            print(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "beats": beats},
                             ensure_ascii=False))
            return 0
        print("\n=== agent 运行中 (站上 $HOME/agent-workspaces/*/out/.progress[.<ts>]) — 只读 ===")
        print("  口径: 产出为 **字节口径** (bytes / bytes_s), 不是 token; ETA 需目标量, 运行中不可得 ⇒ NA\n")
        running = [b for b in beats if b.get("running")]
        cols = [(3, "站", 0), (10, "proj", 0), (11, "状态", 0), (6, "已跑s", 1), (10, "已产出", 1),
                (7, "B/s", 1), (11, "距上次节拍", 1), (24, "ETA", 0), (14, "节拍时刻", 0)]
        print("  " + " ".join(_pad(t, w, bool(r)) for w, t, r in cols))
        print("  " + "-" * (sum(w for w, _, _ in cols) + len(cols) - 1))
        for b in beats:
            if b.get("error"):
                print("  " + _pad(b["station"], 3) + " " + _pad("不可达", 10) + " " + b["error"])
                continue
            st_txt = "working" if b["running"] else "finished"
            if b.get("stale") and b["running"]:
                st_txt += " ⚠陈旧"
            age = "-" if b["age_s"] is None else _human_age(b["age_s"])
            cells = [_pad(b["station"], 3), _pad(b["proj"], 10), _pad(st_txt, 11),
                     _pad(b["t"] if b["running"] else "-", 6, True), _pad(b["bytes"], 10, True),
                     _pad(b["bytes_s"], 7, True), _pad(age, 11, True),
                     _pad("NA (无 max_output 目标)", 24), _pad(b["beat_at"], 14)]
            print("  " + " ".join(cells))
        if not beats:
            print("  (三站均无 .progress —— 没有任务在跑; 注意 finished 行是**上一次** run 的终值残留)")
        print(f"\n  working={len(running)} · 判据: 末行 t=end ⇒ finished (不是 running); "
              f"节拍 >{AGENT_BEAT_STALE_S}s 未更新 ⇒ 疑似卡死")
        return 0

    rows, note = agent_runs(limit)
    if act == "tail":
        for r in rows:
            print(",".join(str(r[k]) for k in ("ts", "proj", "model", "sens", "code",
                                               "queue_s", "run_s")))
        return 0

    if as_json:
        print(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "note": note,
                          "ledger": str(AGENT_LEDGER), "rows": rows,
                          "ledger_freshness": agent_ledger_freshness(rows)}, ensure_ascii=False))
        return 0

    print("\n=== agent 任务台账 (终态) — 只读 ===")
    print(f"  台账: {AGENT_LEDGER}")
    roots, _ = _agent_proj_roots()
    print("  详情: <projRoot>/agent-out/<ts>/.agent-run.json"
          + (f"   ⚠ {note}" if note else f"   (projRoot 取自 agent-cli.ps1: "
                                        f"{', '.join(f'{k}={v}' for k, v in roots.items())})"))
    print("  ⚠ 口径: 产出列是 **字节口径** (output_bytes / B/s), 不是 token —— "
          "与 reqlog 的引擎耗时口径 t/s 互不可比\n")
    cols = [(15, "时间", 0), (10, "proj", 0), (26, "模型", 0), (10, "sens", 0), (4, "exit", 1),
            (13, "状态", 0), (6, "run_s", 1), (7, "queue_s", 1), (9, "产出字节", 1),
            (6, "B/s", 1), (12, "slot", 0), (34, "profile", 0)]
    print("  " + " ".join(_pad(t, w, bool(r)) for w, t, r in cols))
    print("  " + "-" * (sum(w for w, _, _ in cols) + len(cols) - 1))
    for r in rows:
        d = r["detail"]

        def g(k, dflt="-"):
            v = d.get(k)
            return dflt if v is None else v
        slot = "-"
        if d.get("slot"):
            s = d["slot"]
            slot = f"{s.get('action', '?')}({s.get('busy', '?')}/{s.get('total', '?')})"
        prof = "-"
        if d.get("profile"):
            p = d["profile"]
            prof = f"{p.get('name', '?')} ctx={p.get('context', '?')} max={p.get('max_output', '?')}"
            if d.get("accept") is False:
                prof += "  accept=Fail"
        cells = [_pad(r["label"], 15), _pad(r["proj"], 10), _pad(r["model"], 26),
                 _pad(r["sens"], 10), _pad(r["code"], 4, True), _pad(r["status"], 13),
                 _pad(g("run_s", r["run_s"]), 6, True), _pad(g("queue_s", r["queue_s"]), 7, True),
                 _pad(g("output_bytes"), 9, True), _pad(g("output_bps"), 6, True),
                 _pad(slot, 12), _pad(prof, 34)]
        print("  " + " ".join(cells))
    if not rows:
        print("  (台账为空或文件不可读)")
    fr = agent_ledger_freshness(rows)
    if fr:
        hint = "  ← 该台账已久未更新" if (fr.get("age_s") or 0) > 172800 else ""
        print(f"\n  共 {len(rows)} 条 (取尾部) · 最新一条 {fr.get('label')} "
              f"(距今 {_human_age(fr.get('age_s'))}){hint}")
    print("  详情缺失(-)属正常: 早于 O-25 的 run 未落 .agent-run.json; "
          "usage.total_tokens 实测恒 0 (无头 run 不吐 usage) ⇒ 本视图不给 token 速率")
    return 0


