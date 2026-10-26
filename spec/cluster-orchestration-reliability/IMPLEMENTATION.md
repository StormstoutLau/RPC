# 实施文档：集群编排与 RPC 选路可靠性加固

---

id: cluster-orchestration-reliability-IMPLEMENTATION
type: design
version: 1.0
status: draft
date: 2026-10-26
depends: [cluster-orchestration-reliability-DESIGN]
upstream: null

---

> **Feature**: 把 `cluster.py` 加载/换模路径的四个失败语义缺口（未知态误作忙、worker 引擎未卸载、回收失败不传播、预检晚于销毁）收敛为**响亮中止**。
> **创建日期**: 2026-10-26
> **状态**: draft（Step 6 已复核；Step 7 验收门见 [CHECKLIST.md](./CHECKLIST.md)；Step 10 第 2 轮验收**有条件通过 102/116**——代码/测试/门禁面全绿，余 14 项待办为 Phase 6 真站注入与 Phase 7 文档回写）
> **Spec 步骤**: Step 5-6
> **基于设计**: [DESIGN.md](./DESIGN.md)
> **基于调研**: [社区外部锚点调研](../../docs/research/2026-10-26_集群编排与RPC选路可靠性_社区外部锚点调研.md)
> **代码基线**: `d11141bb`（`main`，本地 ahead 1）

---

## 1. 实施范围

| # | 交付物 | 落位 | 类型 |
|---|---|---|---|
| T1 | 三态探针与选路（`classify_worker_probe` / `probe_worker_state` / 新 `resolve_rpc_worker`） | [cluster.py](../../ops/cluster.py) | 修改 |
| T2 | 回收契约（`_reclaim_containers` 返回 tuple + 新 `reclaim_and_unload`） | [cluster.py](../../ops/cluster.py) | 修改 |
| T3 | 7 个调用点改为消费结构化结果 | `cluster.py` L792/L1098/L1230/L1465/L1576/L1596/L1613（实施后实测 2026-10-26；设计期快照 L792/L915/L1052/L1221/L1331/L1355/L1372，因预检函数 ~70 行插入而漂移，见 [CHECKLIST §11.3 P3-1](./CHECKLIST.md)） | 修改 |
| T4 | 容器预检（`_host_path_for` / `classify_container_assets` / `preflight_container`） | [cluster.py](../../ops/cluster.py) | 新增函数 |
| T5 | 配方 `assets` 声明 | [cluster_const.py](../../ops/cluster_const.py) L136-173 | 修改 |
| T6 | `check_aliases` 站级校验 + 新 `halogen-assets` 断言 | [rpc_check.py](../../ops/rpc_check.py) | 修改 + 新增 |
| T7 | 先验红夹具 T1-T14 与既有 mock 迁移 | [test_cluster_pure.py](../../tests/test_cluster_pure.py) | 修改 |
| T8 | 手册 §3.3 行为矩阵回写 | [三机推理集群使用手册](../../docs/三机推理集群使用手册.md) | 修改 |
| T9 | O-176 登记（本设计的缺口 2/3/4 与残留风险） | [OPEN-ISSUES.md](../d6-agent-standard/OPEN-ISSUES.md) | 修改 |

**边界（不做）**：

- 不引入 daemon / reconciler（ADR-0004「零自加载·无 daemon」）。
- 不新增并列脚本或第二管理入口；所有逻辑留在既有三个文件。
- 不改 `infer-load` / `infer-unload` / `rpc-nodes` 的站上实现。
- 不新增数字退出码（仍 `0/1/2`）。
- 不对 `.hgn` 做全量哈希（`min_bytes` 只抓截断/未挂）。
- 不采纳 systemd `Conflicts=`（Q1 已裁不采纳，2026-10-26；理由见 DESIGN §5.5 / §12 Q1）。

---

## 2. 工程约定

| 项 | 值 | 依据 |
|---|---|---|
| 解释器 | `py -3.12` | 仓库既有调用（`rpc_check.py` 需 paramiko） |
| 语言 | Python 3.12 | 既有纯函数测试同栈 |
| 新依赖 | **零** | 只用 stdlib + 既有 `ssh_run`/`ssh_stream` |
| 日志前缀 | `RPC_AUTO_WORKER` / `RECLAIM` / `PREFLIGHT` | DESIGN §6，固定可 grep |
| 返回码 | `0` 成功 / `1` 中止 / `2` 别名解析失败 | DESIGN §4.1、不变式 8 |
| 写动作面 | 仅 `cluster.py` 既有入口 | ADR-0004 唯一管理面 |

**解释器约束**：`cluster.py` 顶层 import paramiko；纯函数测试已在导入期处理（`test_cluster_pure.py` 既有做法），新增纯函数不得引入新的顶层 SSH 依赖。

---

## 3. 任务分解

### T1 三态探针与选路

**改造点 1**：提取探测命令常量，新增分类与探测薄壳。

```
_P_WORKER_BUSY_CMD = (
    "docker ps --format '{{.Names}}' 2>/dev/null | grep -qx halogen && echo halogen; "
    "ss -ltn 2>/dev/null | grep -q ':8080 ' && echo port8080"
)
```

**改造点 2**：`_probe_worker_busy`（[L1137-1144](../../ops/cluster.py#L1137-L1144)）删除。全仓消费者已核：仅 `_load_rpc` 1 处调用 + 测试 1 处 mock，均在本轮改动面内。`parse_worker_busy`（L1131-1134）**保持原样**。

**改造点 3**：`resolve_rpc_worker`（[L1089-1128](../../ops/cluster.py#L1089-L1128)）整体替换为三态版；`busy` 参数更名为 `probe`。

**改造点 4**：`_load_rpc`（[L1187-1224](../../ops/cluster.py#L1187-L1224)）接线：

- 候选探测改为 `probe_worker_state`，结果装 `{target: probe}`。
- **显式 `--worker` 也探测**（旧代码显式时跳过探测；新契约要求显式目标为 unknown 时中止，故必须探）。
- 诊断行 `选路输入: conf=… busy=…` 改为打印三态。

### T2 回收契约

`_reclaim_containers`（[L874-888](../../ops/cluster.py#L874-L888)）返回 `(ok, detail)`；`PORT8080_STILL_BUSY` 从"只打印"改为"判失败"，打印保留（可见性不变）。

新增 `reclaim_and_unload`（紧跟其后）：先容器、后 `infer-unload`；`ssh_stream` 的**连接异常就地捕获**（[cluster_ssh.py L114-128](../../ops/cluster_ssh.py#L114-L128) 的 `_connect` 会抛），不逃出函数。

### T3 调用点改造

| # | 调用点 | 现状 | 改法 |
|---|---|---|---|
| 1 | `_cmd_load_c` [L792](../../ops/cluster.py#L792) | 只回收容器 | `reclaim_and_unload("C")`，失败 return 1 |
| 2 | `_load_container_model` [L915](../../ops/cluster.py#L915) | 回收 + 单独 unload（rc 已检查） | 预检通过后 `reclaim_and_unload`，失败 return 1 |
| 3 | `cmd_load` 普通路径 [L1052](../../ops/cluster.py#L1052) | 回收 + `/health` 条件式 unload | 无条件 `reclaim_and_unload`，失败 return 1 |
| 4 | `_load_rpc` [L1221](../../ops/cluster.py#L1221) | 循环回收，仅 head unload | 对 `{head, worker}` 各调 `reclaim_and_unload`，任一失败 return 1 |
| 5 | `cmd_load_on` [L1331](../../ops/cluster.py#L1331) | 回收 + 条件式 unload | 同 #3 |
| 6 | `cmd_unload_on` [L1355](../../ops/cluster.py#L1355) | 只返回 unload rc | `ok` 决定 rc |
| 7 | `cmd_unload` [L1372](../../ops/cluster.py#L1372) | 线程内回收 + unload | `reclaim_and_unload`；保留线程内 try/except（防 `results[st]` 缺键） |

**#3/#5 为什么删掉 `/health` 判定**：容器被 `rm -f` 后 HTTP 已消失、GTT 仍可能被 docker-proxy 持有（C 站实测 8080 释放 ~4m18s）⇒ 旧条件恰好漏掉"容器已删但资源未释放"。`infer-unload` 幂等且含 `wait_gtt`，无条件执行更简单也更正确（DESIGN §4.3 注）。

### T4 容器预检

三个函数均放在 `cluster.py` 容器编排区（`_container_cleanup_cmd` 之后），**只读**：不调 `docker rm/run`、不调 `infer-unload`、不写站上文件。

### T5 配方扩展

`CONTAINER_MODELS["qwen3.8-flash-next"]` 增加 `assets`（见 §5.4）。`checkpoint` 保留，`HALOGEN_CHECKPOINT` 不动。

### T6 门禁扩展

- `check_aliases`（[L4847](../../ops/rpc_check.py#L4847)）第 (7) 段增补站级判据。
- 新增 `check_halogen_assets`，注册进 `CHECKS`（[L9489](../../ops/rpc_check.py#L9489)），`quick: False`。

### T7 测试

先验红：先改测试（新接口 + T1-T14），跑出 FAIL，再改实现至全绿。

### T8 手册回写

§3.3 行为矩阵六行（DESIGN §7）逐行替换；补一句「`load` 即独占该站」。

### T9 O-176 登记

`OPEN-ISSUES.md` 最大编号 O-175（已闭环）⇒ 新登记 O-176，引用本设计与调研报告，记录缺口 2/3/4 的 E2 状态与真站故障注入待办。

---

## 4. 逐文件改造点

### 4.1 `cluster.py` 纯函数层（新增/替换）

```python
# ── RPC worker 三态探针 ────────────────────────────────
def classify_worker_probe(ok: bool, out: str) -> dict:
    """纯函数：SSH 结果 → {state, reason}。ok=False 即 unknown（不当作忙，也不当作空闲）。"""
    if not ok:
        detail = (out or "").strip().splitlines()
        return {"state": "unknown",
                "reason": f"ssh-failed: {(detail[0] if detail else 'no-output')[:120]}"}
    reason = parse_worker_busy(out)
    return {"state": "busy", "reason": reason} if reason else {"state": "free", "reason": ""}


def probe_worker_state(station: str) -> dict:
    """只读薄壳：SSH 执行 busy 探针，交给 classify_worker_probe。"""
    ok, out = ssh_run(station, _P_WORKER_BUSY_CMD, timeout=20)
    return classify_worker_probe(ok, out)
```

```python
def _probe_map(targets) -> dict:
    """把候选清单逐个探一遍（只探能映射到站的）。缺站映射的目标不进表 ⇒ 选路判 unknown。"""
    return {t: probe_worker_state(RPC_WORKER_STATIONS[t])
            for t in targets if t in RPC_WORKER_STATIONS}
```

### 4.2 `cluster.py` 动作层（替换/新增）

```python
def _reclaim_containers(station: str) -> tuple[bool, str]:
    ok, out = ssh_run(station, _container_cleanup_cmd(), timeout=540)
    if not ok:
        first = (out or "").strip().splitlines()
        return False, f"ssh:{(first[0] if first else 'no-output')[:160]}"
    if "PORT8080_STILL_BUSY" in (out or ""):
        print(f"[cluster] {station} 站容器已删, 但 8080 在 480s 内未释放 —— "
              f"先排查占用者再加载 (studio 可能落到 8081)")
        return False, "port8080-still-busy"
    return True, ""


def reclaim_and_unload(station: str) -> dict:
    """容器回收 → 引擎卸载。任一步失败即 ok=False；连接异常就地捕获，不抛出。"""
    steps = []
    ok_c, detail_c = _reclaim_containers(station)
    steps.append({"name": "containers", "ok": ok_c, "detail": detail_c, "rc": None})

    rc, ok_u, detail_u = None, False, ""
    if not ok_c:
        # SSH 已不可用 / 端口未释放 ⇒ 不再发第二个写动作
        detail_u = "skipped: containers failed"
    else:
        try:
            rc = ssh_stream(station, "infer-unload")
            ok_u = rc == 0
            detail_u = "" if ok_u else f"rc={rc}"
        except Exception as e:
            detail_u = f"{type(e).__name__}: {e}"
    steps.append({"name": "infer-unload", "ok": ok_u, "detail": detail_u, "rc": rc})

    ok = all(s["ok"] for s in steps)
    print(f"[cluster] RECLAIM station={station} ok={ok} :: " +
          ", ".join(f"{s['name']}={'ok' if s['ok'] else (s['detail'] or 'fail')}"
                    for s in steps))
    return {"station": station, "ok": ok, "steps": steps}
```

**跳过 `infer-unload` 的条件说明**：`ok_c=False` 只有两种来源——SSH 失败（再发命令必然同样失败）或端口未释放（容器已删，`infer-unload` 无进程可杀）。两者都无收益，故跳过并记 `skipped: containers failed`，不做无意义写动作。

### 4.3 `cluster.py` 编排层

**`_load_rpc`（替换 L1187-1224）**

```python
    # ── worker 选路（三态）────────────────────────────────────────────
    ok_d, decl = ssh_run(station, "rpc-nodes --all 2>/dev/null")
    decl_list = decl.replace(",", " ").split() if ok_d else []
    if not decl_list:
        print(f"[cluster] nodes.env 声明清单为空/不可读 ({decl.strip() or '空'}) → 中止。")
        return 1
    conf_target = _conf_rpc_target(station, alias) or None
    # ★ 显式 --worker 也探测：显式目标 unknown 必须中止（旧代码显式时跳过探测）
    probe = _probe_map(decl_list)
    print("[cluster] 选路输入: " + " ".join(
        f"{t}={p['state']}({p['reason']})" if p["reason"] else f"{t}={p['state']}"
        for t, p in probe.items()))
    decision = resolve_rpc_worker(conf_target, decl_list, probe, explicit_target)
    if decision["target"] is None:
        print(f"[cluster] RPC worker 选路失败: {decision['reason']} → 中止 (不静默退化)。")
        return 1
    rpc_target, worker_station = decision["target"], decision["station"]
    print(f"[cluster] RPC_AUTO_WORKER source={decision['source']} target={rpc_target} "
          f"station={worker_station} :: {decision['reason']}")
    if decision["source"] == "fallback":
        print("[cluster] ⚠ conf 忙且无其他候选 ⇒ 回退 conf 目标（该站的 qwen/halogen 会被回收）。")

    # ── 回收 + 卸载：head 与选中 worker 都做，任一失败即中止 ──────────
    reclaim = sorted({station, worker_station})
    print(f"[cluster] 回收范围: {'/'.join(reclaim)}（非 worker 站的 qwen 保留）")
    for st in reclaim:
        r = reclaim_and_unload(st)
        if not r["ok"]:
            print(f"[cluster] {st} 站回收/卸载未完成 → 中止 (不启动 rpc-nodes, 不加载)。")
            return 1
```

> `aborted-unknown` 时 `target` 恒为 `None`，上文 `if decision["target"] is None` 已 return 并打印 `reason`（含"判不了 ≠ 选默认"语义），故此处**不再另设分支**。

**`_load_container_model`（替换 L913-919 + 插入预检）**

```python
    # [0/4] 只读预检 —— 必须在任何回收之前（validate before destroy）
    pre = preflight_container(alias, station)
    if not pre["ok"]:
        print(f"[cluster] PREFLIGHT {alias}@{station} ok=False :: " + "; ".join(pre["problems"]))
        if pre["image_missing"]:
            pull_cmd = containers_plan("pull", station=station, image=image,
                                       detach=True, log="/tmp/cluster-docker-pull.log")[0]
            ok2, out2 = ssh_run(station, pull_cmd, timeout=30)
            print(f"[cluster] 镜像未落地 ⇒ {'已后台拉取' if ok2 else '拉取下发失败: ' + out2}")
            print(f"[cluster]   进度: ssh {station} 'tail -f /tmp/cluster-docker-pull.log'; "
                  f"完成后重跑本命令。")
        print("[cluster] 未触碰旧服务 ⇒ 修正资产后重跑。")
        return 1
    print(f"[cluster] PREFLIGHT {alias}@{station} ok=True")

    # [1/4] 回收 + 卸载
    print("[cluster] [1/4] 回收站内既有引擎/容器 ...")
    r = reclaim_and_unload(station)
    if not r["ok"]:
        print("[cluster] 回收/卸载未完成 → 中止 (不启动容器)。")
        return 1

    # [2/4] 镜像已在预检中确认 ⇒ 只回显
    print("[cluster] [2/4] 镜像已在站上 ✓")
```

**`cmd_load` 普通路径 / `cmd_load_on` / `_cmd_load_c`**

三处统一为：

```python
    r = reclaim_and_unload(station)          # _cmd_load_c 用 "C"
    if not r["ok"]:
        print(f"[cluster] {station} 站回收/卸载未完成 → 中止。")
        return 1
```

删除原 `/health` 探测 + 条件式 `ssh_stream(station, "infer-unload")` 两段（L1053-1062 / L1332-1338）。

**`cmd_unload_on`**

```python
    r = reclaim_and_unload(station)
    print(f"[cluster] {station} 站回收/卸载: {'OK' if r['ok'] else 'FAIL'}")
    return 0 if r["ok"] else 1
```

**`cmd_unload`** 线程体内：

```python
        try:
            r = reclaim_and_unload(st)
            results[st] = 0 if r["ok"] else 1
        except Exception as e:
            results[st] = f"{type(e).__name__}: {e}"
```

### 4.4 `cluster_const.py`（T5）

在 `CONTAINER_MODELS["qwen3.8-flash-next"]` 的 `"checkpoint"` 之后插入：

```python
        "assets": [
            {"path": "/hgn/qwen38-flash-next-v2.hgn",    "kind": "file",
             "min_bytes": 60 * 1024 ** 3},
            {"path": "/hgn/qwen38-flash-next-ngram.hgn", "kind": "file",
             "min_bytes": 45 * 1024 ** 3},
            {"path": "/tokenizer",                       "kind": "dir", "min_entries": 1},
        ],
```

`/tokenizer` 的宿主路径由第二条 volume `...qwen38-flash-next-tokenizer:/tokenizer:ro` 派生出（[cluster_const.py L158-161](../../ops/cluster_const.py#L158-L161)），**不在配方里另写 host 路径**（不变式 6）。

### 4.5 `rpc_check.py`（T6）

**(a) `check_aliases` 第 (7) 段**（[L4929-4946](../../ops/rpc_check.py#L4929-L4946)）：

```python
    declared_conf, declared_stations = set(), set()
    for alias, meta in (models or {}).items():
        if alias != meta.get("alias") or meta.get("_group") == "non_model_conf":
            continue
        for st in (meta.get("conf") or []):
            declared_conf.add((str(alias), st))
        for st in (meta.get("stations") or []):
            declared_stations.add((str(alias), st))
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
```

**(b) 新断言**：

```python
def check_halogen_assets(ctx):
    """只读：容器配方声明的资产是否在站上就位（镜像 + 权重 + tokenizer）。"""
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
```

**注册**（`CHECKS` 内，`engine` 之前）：

```python
    {"id": "halogen-assets", "title": "容器模型资产预检", "fn": check_halogen_assets,
     "quick": False,
     "fix": "按明细补资产/重分发权重；镜像缺失则 containers pull；不要先杀旧服务"},
```

### 4.6 `tests/test_cluster_pure.py`（T7）

**(a) 既有夹具迁移**（[L270-297](../../tests/test_cluster_pure.py#L270-L297)）：

```python
def _rpc_reclaim_probe(worker=None, conf_target="", probe=None, reclaim=None,
                       alive="10.10.10.1:50052 10.10.11.3:50052",
                       decl="10.10.10.1:50052 10.10.11.3:50052"):
    calls, built, runs = [], [], []
    probe = probe or {_AW: {"state": "free", "reason": ""},
                      _CW: {"state": "free", "reason": ""}}
    reclaim = reclaim or {}
    saved = (C._reclaim_containers, C.reclaim_and_unload, C.ssh_stream, C.ssh_run,
             C._build_infer_load_cmd, C._conf_rpc_target, C.probe_worker_state)
    try:
        def _reclaim_and_unload(st):
            calls.append(st)                      # 记录"哪些站被要求回收"
            return reclaim.get(st) or {"station": st, "ok": True, "steps": []}

        C._reclaim_containers = lambda st: (True, "")
        C.reclaim_and_unload = _reclaim_and_unload
        ...
        C.probe_worker_state = lambda st: probe.get(st) or {"state": "unknown",
                                                            "reason": "未探测"}
```

`reclaim_and_unload` 的 mock 必须在内部记录被调用的站，否则 T5（两站都收到回收）无法断言。

**(b) `_rw()` 迁移**（[L457-458](../../tests/test_cluster_pure.py#L457-L458)）：

```python
def _rw(conf, probe=None, explicit=None, cands=None):
    probe = probe or {t: {"state": "free", "reason": ""}
                      for t in (_CANDS if cands is None else cands)}
    return C.resolve_rpc_worker(conf, _CANDS if cands is None else cands, probe, explicit)
```

**同源对照保持**（L495-498）：只把 `{}` 换成 `{_AW: busy}` ⇒ 选择必须翻转。

---

## 5. 接口实现

### 5.1 `resolve_rpc_worker`

```python
def resolve_rpc_worker(conf_target=None, candidates=None, probe=None, explicit=None):
    """RPC worker 选路（纯函数）。返回 {target, station, source, reason}。

    probe: {target: {"state": "free"|"busy"|"unknown", "reason": str}}
    ★ 缺键 = unknown（未探测）—— 不再默认空闲。
    source: explicit | explicit-invalid | conf | auto | fallback | none | aborted-unknown
    """
    probe = probe or {}
    known = [c for c in (candidates or []) if c in RPC_WORKER_STATIONS]

    def info(c):
        return probe.get(c) or {"state": "unknown", "reason": "未探测"}

    def state(c):
        return info(c)["state"]

    def why(c):
        p = info(c)
        return p["reason"] or p["state"]

    if explicit:
        if explicit not in known:
            return {"target": None, "station": None, "source": "explicit-invalid",
                    "reason": f"显式目标 {explicit} 不在已声明/存活候选 {known or '空'}"}
        if state(explicit) == "unknown":
            return {"target": None, "station": None, "source": "aborted-unknown",
                    "reason": f"显式目标 {explicit} 探测失败({why(explicit)}) ⇒ 中止，不做回收"}
        return {"target": explicit, "station": RPC_WORKER_STATIONS[explicit],
                "source": "explicit", "reason": "用户显式指派"}

    if not known:
        return {"target": None, "station": None, "source": "none",
                "reason": "候选为空或无节点可映射到站"}

    free = [c for c in known if state(c) == "free"]
    busy = [c for c in known if state(c) == "busy"]
    unknown = [c for c in known if state(c) == "unknown"]

    if not free and not busy:      # 全部 unknown
        return {"target": None, "station": None, "source": "aborted-unknown",
                "reason": "全部候选状态未知(" +
                          " ".join(f"{c}=unknown({why(c)})" for c in unknown) +
                          ") ⇒ 中止，不做回收"}

    if conf_target in free:
        return {"target": conf_target, "station": RPC_WORKER_STATIONS[conf_target],
                "source": "conf", "reason": "conf 目标空闲"}

    if conf_target in busy:
        alts = [c for c in known if c != conf_target]
        alt_free = [c for c in alts if state(c) == "free"]
        if alt_free:
            t = alt_free[0]
            return {"target": t, "station": RPC_WORKER_STATIONS[t], "source": "auto",
                    "reason": f"conf {conf_target} 忙({why(conf_target)}) ⇒ 改用 {t}；{t} 空闲"}
        alt_busy = [c for c in alts if state(c) == "busy"]
        if alt_busy:
            t = alt_busy[0]
            return {"target": t, "station": RPC_WORKER_STATIONS[t], "source": "auto",
                    "reason": f"conf {conf_target} 忙({why(conf_target)}) ⇒ 改用 {t}；"
                              f"{t} 也忙({why(t)}) ⇒ 回收它"}
        if alts:      # alts 非空但全 unknown（free/busy 已被上面接住）
            return {"target": None, "station": None, "source": "aborted-unknown",
                    "reason": f"conf {conf_target} 忙({why(conf_target)}) 且其他候选均未知 ⇒ 中止"}
        return {"target": conf_target, "station": RPC_WORKER_STATIONS[conf_target],
                "source": "fallback",
                "reason": f"conf {conf_target} 忙({why(conf_target)}) 且无其他候选 ⇒ 回退并回收它"}

    # conf 不在候选 / unknown：只从已知状态里选
    if free:
        t = free[0]
        return {"target": t, "station": RPC_WORKER_STATIONS[t], "source": "auto",
                "reason": "conf 不在候选 ⇒ 用空闲节点"}
    t = busy[0]
    return {"target": t, "station": RPC_WORKER_STATIONS[t], "source": "auto",
            "reason": f"conf 不在候选/未知且无空闲 ⇒ 用 {t}（回收它）"}
```

**签名一致性**：与 DESIGN §4.2 一致；差异仅 `unknown` 列表参与全未知分支的 reason 拼接（不改变判定）。规则 5d（conf 忙且无其他候选 ⇒ `fallback(conf)`）对应 `alts` 为空的兜底分支，与既有测试 `cands=[_AW]` 期望一致。

### 5.2 `_reclaim_containers` / `reclaim_and_unload`

签名与 DESIGN §4.3 一致（见 §4.2 代码）。`steps` 恒为两项，名称固定 `containers` / `infer-unload`。

### 5.3 `preflight_container`

```python
def _host_path_for(spec: dict, inner: str) -> str:
    """容器内路径 → 宿主路径（按 volume 的 inner 最长前缀匹配）。无法映射 ⇒ ""。"""
    best_host, best_cont = "", ""
    for v in (spec.get("volume") or []):
        parts = str(v).split(":")
        if len(parts) < 2:
            continue
        host, cont = parts[0], parts[1]
        if not host or not cont:
            continue
        c = cont.rstrip("/") or "/"
        if inner == c or inner.startswith(c + "/") or c == "/":
            if len(c) > len(best_cont):
                best_host, best_cont = host.rstrip("/") or "/", c
    if not best_cont:
        return ""
    if best_cont == "/":                 # 根映射：容器路径即宿主相对路径（不能丢前导 /）
        return (best_host + inner) if best_host != "/" else inner
    rest = "" if inner == best_cont else inner[len(best_cont):]
    return (best_host + rest) if best_host != "/" else rest


def classify_container_assets(spec: dict, observed: dict) -> list[str]:
    """纯函数：配方 + 观测 → problems（空 = 通过）。"""
    problems = []
    assets = spec.get("assets") or []
    for a in assets:
        p = a.get("path")
        if not p or not _host_path_for(spec, p):
            problems.append(f"recipe-unmapped:{p}")
    ckpt = spec.get("checkpoint")
    if ckpt and assets and assets[0].get("path") != ckpt:
        problems.append("recipe-checkpoint-mismatch")

    if not ((observed or {}).get("image") or {}).get("present"):
        problems.append("image-missing")

    obs = (observed or {}).get("assets") or {}
    for a in assets:
        p = a.get("path")
        o = obs.get(p) or {"kind": "missing"}
        kind = o.get("kind")
        if kind == "missing" or kind == "unreadable":
            problems.append(f"asset-{kind}:{p}")
            continue
        if a.get("kind") == "file":
            if kind != "file":
                problems.append(f"asset-not-file:{p}")
            elif int(o.get("size") or 0) < int(a.get("min_bytes") or 0):
                problems.append(f"asset-too-small:{p}")
        elif a.get("kind") == "dir":
            if kind != "dir":
                problems.append(f"asset-not-dir:{p}")
            elif int(o.get("entries") or 0) < int(a.get("min_entries") or 1):
                problems.append(f"asset-empty-dir:{p}")
    return problems


def preflight_container(alias: str, station: str) -> dict:
    """只读：镜像存在性 + 资产就位。零写动作。"""
    spec = CONTAINER_MODELS.get(alias) or {}
    image = spec.get("image", "")
    problems = []

    ok_i, out_i = ssh_run(station, f"docker image inspect {image} --format '{{{{.Id}}}}'",
                          strict=True)
    # ssh_run(strict) 非零码 ⇒ "(rc=N) body"（站可达、镜像不在）；
    # 连接失败 ⇒ "TypeName: msg"（站不可达）。两者必须区分，否则误报 asset-missing。
    if not ok_i and not str(out_i).startswith("(rc="):
        problems.append(f"ssh-failed:{(out_i or '').strip()[:120]}")
        return {"ok": False, "problems": problems, "image_missing": False}
    image_present = ok_i
    if not image_present:
        problems.append("image-missing")

    observed = {"image": {"present": image_present}, "assets": {}}
    stats = []
    for a in (spec.get("assets") or []):
        hp = _host_path_for(spec, a.get("path", ""))
        if not hp:
            continue
        stats.append(hp)
    if stats:
        q = " ".join(sh_single_quote(p) for p in stats)
        cmd = (f"for p in {q}; do "
               f"if [ -f \"$p\" ]; then "
               f"s=$(stat -c %s \"$p\" 2>/dev/null) && echo \"$p|file|$s\" "
               f"|| echo \"$p|unreadable|0\"; "
               f"elif [ -d \"$p\" ]; then "
               f"if [ -r \"$p\" ] && [ -x \"$p\" ]; then "
               f"echo \"$p|dir|$(ls -A \"$p\" 2>/dev/null | wc -l | tr -d ' ')\"; "
               f"else echo \"$p|unreadable|0\"; fi; "
               f"else echo \"$p|missing|0\"; fi; done")
        ok_s, out_s = ssh_run(station, cmd, timeout=30)
        if not ok_s:
            problems.append(f"ssh-failed:{(out_s or '').strip()[:120]}")
            return {"ok": False, "problems": problems, "image_missing": False}
        for line in (out_s or "").splitlines():
            parts = line.split("|")
            if len(parts) != 3:
                continue
            host_path, kind, num = parts
            # 回填容器内路径（observed 的键必须是配方里的 inner path）
            inner = next((a["path"] for a in (spec.get("assets") or [])
                          if _host_path_for(spec, a["path"]) == host_path), host_path)
            observed["assets"][inner] = {
                "kind": kind,
                "size": int(num) if num.isdigit() else 0,
                "entries": int(num) if num.isdigit() else 0,
            }

    problems.extend(classify_container_assets(spec, observed))
    return {"ok": not problems, "problems": problems, "image_missing": not image_present}
```

**`sh_single_quote`**：新增 3 行纯函数（`return "'" + p.replace("'", "'\\''") + "'"`）。路径来自配方常量，但仍做单引号转义，避免空格/特殊字符破坏循环。

### 5.4 配方 `assets`

见 §4.4。`min_bytes` 取实测值 ~96%（v2 62.11 GiB → 60 GiB；ngram 47.68 GiB → 45 GiB）。

---

## 6. 兼容性与迁移

### 6.1 测试迁移（必须先红）

| 既有用例 | 失败原因（先验红形态） | 迁移 |
|---|---|---|
| `_rw(conf)` 12 条（[L461-494](../../tests/test_cluster_pure.py#L461-L494)） | 第 3 位置实参从 `busy` 变 `probe`，`{"10.10.10.1:50052": "halogen"}` 被当 probe ⇒ `KeyError`/状态未知 | 改传 `{t: {"state": "busy", "reason": "halogen"}}` |
| `_rw(_AW, {})` | 空 probe ⇒ 缺键 unknown ⇒ 全未知中止（旧期望"选 conf"） | 改为显式 free |
| `_rpc_reclaim_probe` mock（[L278](../../tests/test_cluster_pure.py#L278)） | `lambda st: ... or True` 返回 bool，新代码解包 tuple ⇒ TypeError | 改 `lambda st: (True, "")`；新增 `reclaim_and_unload` mock |
| L292 `_probe_worker_busy` mock | 函数已删 ⇒ AttributeError（**这就是预期的先验红**） | 改 mock `probe_worker_state` |

### 6.2 行为变更（用户可见）

| 变更 | 影响面 | 缓解 |
|---|---|---|
| 单站路径无条件 `infer-unload` | B 站加载普通模型会停掉该站 RPC worker | 与"同站禁止叠加"一致；手册写明「`load` 即独占该站」。O-175 射程已登记"反向冲突不自动迁移" |
| 缺键 = unknown | 一次 SSH 抖动即中止 | 探针 20s 超时；中止信息含站与原因；可 `--worker` 显式重试 |
| `PORT8080_STILL_BUSY` 判失败 | 原本"警告后继续"的加载会变成 rc=1 | 正是本设计目标；修复手段=排查 8080 占用 |
| 新增 `halogen-assets` full 断言 | pre-push 多 2 次 SSH/站（约 6 次） | 只注册 full；不进 `--quick` |

### 6.3 文档回写

- 手册 §3.3 行为矩阵（DESIGN §7）六行替换。
- `OPEN-ISSUES.md` 新登记 O-176，引用 DESIGN §1 与调研 §3。
- Q1（systemd `Conflicts=`）已裁**不采纳**（2026-10-26，理由见 DESIGN §5.5 / §12）；若后续重启议题，另立 ADR。

---

## 7. 错误处理实施

| 条件 | 代码位置 | 结果 | CLI |
|---|---|---|---|
| 探针 SSH 失败/超时 | `classify_worker_probe` | `unknown` | 退出候选池；无候选 rc=1 |
| 显式 worker unknown | `resolve_rpc_worker` | `aborted-unknown` | rc=1，回收 0 次 |
| 容器回收 SSH 失败 | `_reclaim_containers` | `(False, "ssh:…")` | 中止 rc=1 |
| 8080 超时未释放 | `_reclaim_containers` | `(False, "port8080-still-busy")` | 中止 rc=1 |
| `infer-unload` rc≠0 | `reclaim_and_unload` | `steps[-1].ok=False` | 中止 rc=1 |
| `infer-unload` 连接异常 | `reclaim_and_unload` | 就地捕获 | 中止 rc=1 |
| 镜像不在站上 | `preflight_container` | `image_missing=True` | 后台拉取 + rc=1，**不回收** |
| 权重缺失/过小 | `preflight_container` | `asset-missing` / `asset-too-small` | rc=1，**不回收** |
| 资产类型不符 | `preflight_container` | `asset-not-file` / `asset-not-dir` | rc=1，**不回收** |
| tokenizer 空目录 | `preflight_container` | `asset-empty-dir` | rc=1，**不回收** |
| 资产不可读 | `preflight_container` | `asset-unreadable` | rc=1，**不回收** |
| 容器启动后未就绪 | 既有轮询（[L946-968](../../ops/cluster.py#L946-L968)） | 既有 | rc=1（不变） |

---

## 8. 不变式实施

| # | 不变式（DESIGN §8） | 实施位置 | 验证 |
|---|---|---|---|
| 1 | 独占：` :8080` 同时只一个引擎/容器 | `reclaim_and_unload` 串行于启动之前 | T5/T6/T7 |
| 2 | 未知不可破坏 | `resolve_rpc_worker` unknown 不入 free/busy；`aborted-unknown` 前 return | T1/T2/T3/T4 |
| 3 | 校验先于破坏 | `_load_container_model` 第 [0/4] 段 | T10/T11/T12（回收 0 次） |
| 4 | 失败不吞 | 7 个调用点消费 `ok` | T6-T9 |
| 5 | 预检只读 | `preflight_container` 无 `docker rm/run`、无 `infer-unload` | 代码审查 + T10-T12 |
| 6 | 路径单一真值 | `_host_path_for` 只读 `volume` | T13 |
| 7 | 缺失即未知 | `probe.get(c) or unknown` | T1 |
| 8 | 返回码不变 | 各入口 `return 0/1`；别名失败仍 2 | 全量测试 |

---

## 9. 测试策略

### 9.1 矩阵（对应 DESIGN §10.4）

| # | 用例 | 注入 | 期望 | 断言点 |
|---|---|---|---|---|
| T1 | 两站 unknown | `probe={A:u,C:u}` | `target=None`, `aborted-unknown` | `d["source"]` |
| T2 | conf 忙 + 备选 unknown | `probe={A:busy,C:u}` | 中止，不选 C | `d["target"] is None` |
| T3 | conf unknown + 备选 free | `probe={A:u,C:free}` | 选 C | `d["target"]==_CW` |
| T4 | 显式 worker unknown | `probe={C:u}, explicit=_CW` | 中止 | 回收调用次数 = 0 |
| T5 | worker 忙因为普通引擎 | `probe={A:busy,C:busy(port8080)}` | B、C 都 `reclaim_and_unload` | `calls == ["B", "C"]` |
| T6 | head 卸载失败 | `reclaim={"B": ok=False}` | 中止，未 `rpc-nodes --start` | `runs` 无 start |
| T7 | worker 卸载失败 | `reclaim={"C": ok=False}` | 中止 | rc=1 |
| T8 | 容器回收 SSH 失败 | `(False, "ssh:…")` | `reclaim_and_unload.ok=False` | steps[0] |
| T9 | 端口未释放 | 输出含 `PORT8080_STILL_BUSY` | `(False, "port8080-still-busy")` | steps[0] |
| T10 | 缺 checkpoint | observed 缺该路径 | `asset-missing` | problems |
| T11 | 缺 ngram / tokenizer 空 | `kind=missing` / `entries=0` | 同上 / `asset-empty-dir` | problems |
| T12 | 镜像缺失 | `image.present=False` | `image_missing=True` | 返回键 |
| T13 | 宿主路径映射 | `/hgn/x`、`/tokenizer`、未挂载 `/nope` | 映射正确 / `""` | `_host_path_for` |
| T14 | aliases 站级缺口 | inventory 缺 A 站 `stations` | 门禁 FAIL，文案含"未声明" | `check_aliases` |

**双向自证**：T3 与 T2 只改 C 的状态（free ↔ unknown）⇒ 选择必须翻转（中止 ↔ 选 C）。沿用既有同源对照写法（[L495-498](../../tests/test_cluster_pure.py#L495-L498)）。

### 9.2 测试分层

| 层 | 手段 | 覆盖 |
|---|---|---|
| 纯函数 | 直接调用，无 mock | T1-T4、T10-T13 |
| 薄壳 | monkeypatch `ssh_run`/`ssh_stream` | T8、T9 |
| 编排 | `_rpc_reclaim_probe` 夹具 | T5-T7 |
| 门禁 | `check_aliases` 直接调用 + inventory 造数 | T14 |

### 9.3 命令

```powershell
py -3.12 tests\test_cluster_pure.py
py -3.12 ops\rpc_check.py --only halogen-assets,aliases
py -3.12 ops\rpc_check.py --quick
py -3.12 ops\rpc_check.py
```

---

## 10. 实施顺序

| Phase | 动作 | 产出 | 门 |
|---|---|---|---|
| 0 | 改测试夹具 + 新增 T1-T14 | 先验红输出（逐字留存） | 必须 FAIL |
| 1 | `classify_worker_probe` / `probe_worker_state` / `_probe_map` / 新 `resolve_rpc_worker` | T1-T4 转绿 | `test_cluster_pure` |
| 2 | `_reclaim_containers` tuple / `reclaim_and_unload` / 7 调用点 / `_load_rpc` 回收范围 | T5-T9 转绿 | 同上 |
| 3 | `assets` / `_host_path_for` / `classify_container_assets` / `preflight_container` / `_load_container_model` 前置 | T10-T13 转绿 | 同上 |
| 4 | `check_aliases` 站级 + `check_halogen_assets` + `CHECKS` | T14 转绿 | `--only halogen-assets,aliases` |
| 5 | 全量门禁 | 无回归 | `--quick` + full |
| 6 | 真站故障注入（维护窗口） | 四项均响亮中止 | 人工验收 |
| 7 | 手册 §3.3 回写 + O-176 登记 | 文档闭环 | `doc-status`/`doclinks`/`md-tables` |

**Phase 6 故障注入清单**（需用户授权，不在本轮执行）：

| 注入 | 手段 | 期望 |
|---|---|---|
| worker SSH 不可达 | 先占住 conf 目标站（加载一模型使其 busy），再断开另一候选 SSH | `aborted-unknown`，conf 站服务存活 |
| worker 被普通引擎占 8080 | 站上手工起 `llama-server` | 回收后 unload 成功，无叠加 |
| ngram 文件缺失 | `mv` 移走 ngram | 预检 FAIL，旧服务未停 |
| 镜像缺失 | `docker rmi`（随后恢复） | `image-missing` + 后台拉取，旧服务未停 |

---

## 11. 与设计的一致性对齐

### 11.1 逐项对齐

| DESIGN 章节 | 本文落点 | 状态 |
|---|---|---|
| §3.1 目标控制流 | §4.3（四个入口的顺序） | ✅ |
| §3.2 模块划分 | §4 逐文件 | ✅ |
| §4.2 探针与选路 | §4.1 + §5.1 | ✅ |
| §4.3 回收与卸载 | §4.2 + §5.2 | ✅ |
| §4.4 容器预检 | §4.4 + §5.3 | ✅ |
| §4.5 门禁扩展 | §4.5 | ✅ |
| §7 错误矩阵 | §7 | ✅ |
| §8 不变式 8 条 | §8 | ✅ |
| §10.3 Phase 0-6 | §10（细化为 Phase 0-7） | ✅ |
| §10.4 T1-T14 | §9.1 | ✅ |
| §11 验收标准 | §10 Phase 5-7 | ✅ |

### 11.2 实施期偏差登记（Step 6/7 已复核：D1 补登两码+目录不可读，D3 补 WARN 返回）

| # | 偏差 | 理由 | 影响 |
|---|---|---|---|
| D1 | `preflight_container` 新增 `asset-unreadable` / `asset-not-file` / `asset-not-dir` 三个问题码（Step 6 复核：原登记漏了后两码；Step 7 补：文件 `stat` 失败与**目录不可读**两条路径都判 `unreadable`） | `stat` 失败≠`missing`（误报"没到"）；目录不可读会被 `ls` 空输出误判成 `asset-empty-dir`；探测 kind 与配方不符也需显式码 | 问题码 **6 → 9**（DESIGN §4.4 表 4 行内共 6 码：`recipe-unmapped` / `recipe-checkpoint-mismatch` / `image-missing` / `asset-missing` / `asset-too-small` / `asset-empty-dir`）；DESIGN 词表同步留待 Step 8 一致性对齐回写，届时以本偏差为准 |
| D2 | 新增 `sh_single_quote` 小工具 | 宿主路径含空格时循环会拆词 | 纯函数，无副作用 |
| D3 | `check_halogen_assets` 先 `ssh true` 探可达；不可达站记 **WARN**（`note` 含跳过站例数） | 站不可达应与"资产缺失"区分（否则未部署的站假红）；跳过信息不能只装进局部变量（Step 7 复核发现原骨架 `warn` 未被返回） | 与 Q2 一致；多 1 次轻量 SSH；WARN 不阻塞 |
| D4 | `_probe_map` 抽为独立函数 | `_load_rpc` 内联会让函数再长 8 行 | 纯函数，可单测 |
| D5 | 测试夹具用 `_swap(name, value)` 替代 `saved` 元组（Step 9 实施期发现） | 先验红阶段 `probe_worker_state` / `reclaim_and_unload` **尚不存在**，直接读属性会 AttributeError 中断整条脚本式测试；`saved` 元组方案只在"先绿后红"下成立 | `_swap` 用 `getattr(..., _MISSING)` 兼容属性未定义，还原时 `delattr`；语义等价，仅测试辅助，不触生产代码 |

---

## 12. 幻觉排除审查（Step 6）

### 12.1 依赖与 API

| 断言 | 核对 | 结论 |
|---|---|---|
| 零新依赖 | 仅 stdlib + 既有 `ssh_run`/`ssh_stream` | ✅ |
| `ssh_run(strict=True)` 非零码返回 `(rc=N) body` | [cluster_ssh.py L107-108](../../ops/cluster_ssh.py#L107-L108) | ✅（故用 `startswith("(rc=")` 区分可达性） |
| `ssh_stream` 连接失败抛异常 | [cluster_ssh.py L116](../../ops/cluster_ssh.py#L116) → `_connect` | ✅ 故 `reclaim_and_unload` 必须 try/except |
| `containers_plan` 签名 | `(action, station=, image=, name=, publish=, group_add=, device=, volume=, env=, ipc=, ulimit=)` | ✅ 既有调用 L924-938 |
| `load_inventory()` 返回 `(ports, models)` | [rpc_check.py L4912](../../ops/rpc_check.py#L4912)、L5336 | ✅ |
| `models[alias]["stations"]` 存在 | [models.yaml L111](../../inventory/models.yaml#L111) `stations: [A, B, C]` | ✅ |
| `CONTAINER_MODELS` 只有 1 个别名 | [cluster_const.py L136-173](../../ops/cluster_const.py#L136-L173) | ✅ |

### 12.2 签名一致性

- [ ] `classify_worker_probe(ok, out) -> dict` = DESIGN §4.2
- [ ] `probe_worker_state(station) -> dict` = DESIGN §4.2
- [ ] `resolve_rpc_worker(conf_target, candidates, probe, explicit) -> dict` = DESIGN §4.2
- [ ] `_reclaim_containers(station) -> tuple[bool, str]` = DESIGN §4.3
- [ ] `reclaim_and_unload(station) -> dict`（`steps` 两项）= DESIGN §4.3
- [ ] `preflight_container(alias, station) -> dict`（三键）= DESIGN §4.4
- [ ] `_host_path_for(spec, inner) -> str` = DESIGN §4.4

### 12.3 覆盖检查

- [ ] DESIGN §3.2 的 6 个模块均有落点（`cluster_ssh` / `rpc-nodes` 明确不改）
- [ ] 无设计未覆盖的实施（D1-D4 已登记）
- [ ] 7 个调用点全部改造（grep 复核）
- [ ] 无新增脚本文件（`check_scripts` 门禁）

### 12.4 不声称

- 不声称 T8/T9 覆盖真实 SSH 语义——它们是 monkeypatch，真站行为靠 Phase 6。
- 不声称 `min_bytes` 能发现同尺寸损坏；它只抓截断/未完成/挂错。
- 不声称 `asset-unreadable` / `asset-not-file` / `asset-not-dir` 已在真站复现；它们是防御性分支。

---

## 13. 风险与回滚

| 风险 | 触发条件 | 回滚 |
|---|---|---|
| 缺键=unknown 过严 | 一次 SSH 抖动导致加载中止 | 显式 `--worker` 重试；必要时临时把该站探针超时提到 30s（单点常量） |
| 无条件 unload 打断并行任务 | B 站有 RPC worker 时加载普通模型 | 接受（纪律）；手册写明独占 |
| 预检误红 | 资产未分发/路径变更 | 预检只读 ⇒ 修正资产后重跑，旧服务仍在 |
| `check_halogen_assets` 拖慢 full | pre-push 频繁 | 只 full；可用 `--only` 跳过 |

**代码回滚**：本轮改动集中在 3 个源文件 + 1 个测试文件，`git checkout -- ops/cluster.py ops/cluster_const.py ops/rpc_check.py tests/test_cluster_pure.py` 即可完全回退（未提交前）。

---

**Review 签字**: _________ 日期: _________
