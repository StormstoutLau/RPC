# 设计文档：集群编排与 RPC 选路可靠性加固

---

id: cluster-orchestration-reliability-DESIGN
type: design
version: 1.0
status: draft
date: 2026-10-26
depends: [ADR-0004, ADR-0014]
upstream: null

---

> **Feature**: 修复 `cluster.py` 统一编排在**失败语义**上的四个缺口——未知态误作忙、worker 普通引擎未卸载、回收失败不传播、预检晚于销毁——使加载/换模在**任何非理想返回**下都表现为**响亮中止**，而不是静默半成品。
> **创建日期**: 2026-10-26
> **状态**: draft（Step 4 已复核；实施展开见 [IMPLEMENTATION.md](./IMPLEMENTATION.md)，验收门见 [CHECKLIST.md](./CHECKLIST.md)）
> **Spec 步骤**: Step 3（设计文档）
> **基于调研**: [集群编排与 RPC 选路可靠性 · 社区外部锚点调研](../../docs/research/2026-10-26_集群编排与RPC选路可靠性_社区外部锚点调研.md)（本设计的**事实与外部锚点来源**）
> **代码基线**: `d11141bb`（`main`，本地 ahead 1）

---

## 1. 设计目标

把"加载一台模型"的失败面收敛成三条可判定规则：

1. **未知不等于可用**：探测失败（`unknown`）的站点不得被选中，更不得被回收。
2. **独占资源不允许两个消费者**：`head + 选中 worker` 必须都完成"容器回收 → 引擎卸载"，任一失败即中止。
3. **部分完成不算成功**：回收失败、端口未释放、卸载 rc 非 0 都必须阻断后续启动。
4. **校验先于破坏**：容器模型的镜像/权重/tokenizer 预检必须在任何回收动作**之前**完成。

**不做**：

- 不引入常驻控制器 / daemon（与 ADR-0004「零自加载·无 daemon」冲突）。
- 不新增并列脚本或第二管理入口。
- 不改变推理引擎路线（qwen=halogen，GLM/DS=llama.cpp RPC）。
- 不新增数字退出码（保持 `0/1/2` 语义，避免破坏既有调用方）。
- 不在日常加载时对 `.hgn` 做全量 sha256。

---

## 2. 设计依据

### 2.1 调研结论 → 设计决策

| 调研结论（外部锚点） | 本仓缺口 | 设计决策 | 证据 |
|---|---|---|---|
| K8s 探针只有 `Success` 才算就绪；`Unknown` 不触发"可用" | `probe-failed` 仍进入"回收它"分支 | **引入三态 `free/busy/unknown`；缺键默认 unknown** | 调研 §3.1；E1 复现 |
| K8s 不向 `not-ready` 节点派发新负载 | 未知站仍可能被选中 | unknown 退出候选池；无候选即中止 | 调研 §3.1 |
| K8s device plugin：设备不可共享、不可超卖 | worker 普通引擎与 rpc-server 可叠加 | 回收范围 = `{head, worker}`，两站都 `infer-unload` | 调研 §3.2；E2 |
| `kubectl drain` 成功返回 = 全部安全驱逐 | 回收失败只打印警告 | `reclaim_and_unload` 返回结构化结果，调用方必须消费 | 调研 §3.3；E2 |
| PDB 返回 429 表示"当前不允许" | 端口未释放仍继续 | `PORT8080_STILL_BUSY` ⇒ 判失败并中止 | 调研 §3.3 |
| Terraform plan/apply：校验先于变更 | 先回收再检查镜像 | 只读 `preflight_container` 前置到回收之前 | 调研 §3.4；E2 |
| Compose `service_healthy`：启动 ≠ 就绪 | 端口/资产未验证 | 预检 + 现有 `/health` 轮询并存 | 调研 §3.4 |
| SLSA / digest pinning | digest 只在运行中核对 | 预检做镜像存在性；digest 判据留在 `check_engine` | 调研 §3.4 |

### 2.2 相关 ADR

| ADR | 决策 | 对本设计的影响 |
|---|---|---|
| [ADR-0004](../../adr/ADR-0004-统一管理入口为唯一管理面.md) | 唯一管理面 = `cluster.py`；不新增并列入口/daemon | 所有改动落在既有函数与既有门禁；不引入 reconciler |
| [ADR-0014](../../adr/ADR-0014-halogen引擎引入与容器写动作扩权.md) | halogen 容器化生产路径；`CONTAINER_MODELS` 为配方单一真值 | 预检资产从配方派生，不新开 host 路径真值 |

### 2.3 职责边界

- **职责内**：`cluster.py` 的选路判定、回收/卸载编排、容器加载顺序；`rpc_check.py` 的只读门禁扩展。
- **职责外**：① 推理引擎内部行为；② 权重分发（仍走站间复制 + sha256）；③ systemd 单元定义（若采纳 `Conflicts=`，另立 ADR）；④ `infer-load` / `infer-unload` / `rpc-nodes` 的站上实现。

### 2.4 现状事实（全部已核到行）

| 事实 | 位置 |
|---|---|
| 探测失败返回字符串 `probe-failed` | [cluster.py L1137-1144](../../ops/cluster.py#L1137-L1144) |
| 选路把该字符串当普通 busy | [cluster.py L1106-1128](../../ops/cluster.py#L1106-L1128) |
| `_load_rpc` 只对 head 执行 `infer-unload` | [cluster.py L1218-1224](../../ops/cluster.py#L1218-L1224) |
| `rpc-nodes --start` 不卸载普通引擎 | [rpc-nodes L83-97](../../ops/rpc-nodes#L83-L97) |
| `PORT8080_STILL_BUSY` 只打印 | [cluster.py L883-888](../../ops/cluster.py#L883-L888) |
| 7 个调用点丢弃回收返回值 | `cluster.py` L792/L915/L1052/L1221/L1331/L1355/L1372 |
| 容器加载先回收、后查镜像 | [cluster.py L913-929](../../ops/cluster.py#L913-L929) |
| `check_aliases` 只认"有配方"，不认站 | [rpc_check.py L4941-4946](../../ops/rpc_check.py#L4941-L4946) |
| `check_stations` 权重检查只覆盖 conf 的 `MODEL_PATH` | [rpc_check.py L5408-5431](../../ops/rpc_check.py#L5408-L5431) |
| `check_engine` 只在容器运行时核 digest | [rpc_check.py L6549-L6566](../../ops/rpc_check.py#L6549-L6566) |
| 配方有 `checkpoint`，**无 ngram 路径字段** | [cluster_const.py L136-173](../../ops/cluster_const.py#L136-L173) |
| `ssh_run` 默认 `ok` 不含退出码；`ssh_stream` 连接失败会抛异常 | [cluster_ssh.py L90-128](../../ops/cluster_ssh.py#L90-L128) |

---

## 3. 架构设计

### 3.1 目标控制流

```
cmd_load(alias, backend, engine, worker)
│
├─ 容器模型 (CONTAINER_MODELS 命中)
│    [pre] preflight_container(alias, station)        ← 只读，零破坏
│           ├─ 失败: 镜像缺失 → 下发后台拉取; 其余 → 打印 problems
│           └─ 一律 return 1（不触碰旧服务）
│    [1/4] reclaim_and_unload(station)               ← 失败 → return 1
│    [2/4] docker run -d
│    [3/4] /health 轮询至 status=ok
│    [4/4] 身份打印 + LOWERING THE POOL 检查
│
├─ RPC 双机类 (is_rpc)
│    [0] probe_worker_state(候选)
│         └─ resolve_rpc_worker(probe) → aborted-unknown? return 1
│    [1] reclaim_and_unload(head) + reclaim_and_unload(worker)
│         └─ 任一 ok=False → return 1（早于任何启动）
│    [2] rpc-nodes --start <alias> <worker>
│    [3] rpc-nodes 存活探测（选中 worker 必须在存活清单）
│    [4] infer-load --backend llama-rpc --rpc-target <worker>
│
└─ 单站普通后端 (A/B 或 C)
     [1] reclaim_and_unload(station)                  ← 失败 → return 1
     [2] infer-load（站内 READY 判定）
```

### 3.2 模块划分

| 模块 | 新增/修改 | 职责 |
|---|---|---|
| `ops/cluster.py` | 修改 | 三态探测、选路、回收/卸载契约、容器预检 |
| `ops/cluster_const.py` | 修改 | `CONTAINER_MODELS` 增加 `assets` 声明（主机路径仍由 volume 派生） |
| `ops/rpc_check.py` | 修改 | aliases 站级校验、新增只读 `halogen-assets` |
| `ops/cluster_ssh.py` | 不改 | 传输层；新代码消费其返回值语义 |
| `ops/rpc-nodes` | 不改 | 仍只负责起 worker；卸载责任上移到编排层 |
| `tests/test_cluster_pure.py` | 修改 | 三态/回收/预检的先验红夹具 |

### 3.3 数据流

```
站上事实 ──ssh──> 探针 ──> ProbeResult ──> resolve_rpc_worker ──> Decision
                                                                    │
                      ┌─────────────────────────────────────────────┘
                      ▼
              reclaim_and_unload(head/worker) ──> ReclaimResult ──> 中止 or 继续
                      │
                      ▼
              rpc-nodes --start ──> 存活清单 ──> infer-load
```

关键点：**决策只依赖探针结果，不依赖"默认可用"**；**动作只依赖结构化返回值，不依赖打印文本**。

---

## 4. 接口定义

### 4.1 CLI（不变）

```
python ops/cluster.py load <alias> [--backend B] [--engine E] [--worker A|C]
python ops/cluster.py unload [--station A|B|C]
python ops/rpc_check.py --only halogen-assets      # 新增只读门禁 id
```

退出码保持：`0` 成功；`1` 中止/失败；`2` 别名解析失败。

### 4.2 探针与选路

```python
def classify_worker_probe(ok: bool, out: str) -> dict:
    """纯函数。
    返回 {"state": "free"|"busy"|"unknown", "reason": str}。
    ok=False                      -> unknown("ssh-failed: <detail>")
    ok=True 且 parse 为空         -> free("")
    ok=True 且 parse 非空         -> busy(<joined tokens>)
    """

def probe_worker_state(station: str) -> dict:
    """只读。SSH 执行既有 busy 探针命令，交给 classify_worker_probe。"""

def resolve_rpc_worker(conf_target=None, candidates=None,
                       probe=None, explicit=None) -> dict:
    """纯函数。返回 {target, station, source, reason}。

    probe: {target: {"state": ..., "reason": ...}}
    ★ 缺键 = unknown("未探测") —— 不再默认空闲。
    source: explicit | explicit-invalid | conf | auto | fallback |
            none | aborted-unknown
    """
```

**选路算法（规范序）**

```
known = [c for c in candidates if c in RPC_WORKER_STATIONS]
state(c) = probe.get(c) or unknown("未探测")

1. explicit:
     not in known                  -> explicit-invalid (target=None)
     state == unknown              -> aborted-unknown (target=None)
     否则                           -> explicit

2. 无 known                       -> none (target=None)

3. 分类 free / busy / unknown
   若 free 与 busy 都为空         -> aborted-unknown (target=None)

4. conf_target in free            -> conf
5. conf_target in busy:
     a. 其他候选有 free            -> auto(free[0])，理由写明 conf 忙
     b. 否则其他候选有 busy        -> auto(busy[0])，理由写明"回收它"
     c. 否则其他候选全 unknown     -> aborted-unknown (target=None)
     d. 无其他候选                 -> fallback(conf)，理由写明"回收它"
6. conf 不在候选 / unknown:
     free 非空                     -> auto(free[0])
     busy 非空                     -> auto(busy[0])，理由写明"回收它"
     否则                           -> aborted-unknown
```

> 与旧语义的唯一差异：**"缺键/未知"不再等于空闲**，且 unknown 永不进入可回收分支。
> "两站都忙 ⇒ 改用 C 并回收 C"保持不变——因为它状态**已知**，回收是安全动作。

### 4.3 回收与卸载

```python
def _reclaim_containers(station: str) -> tuple[bool, str]:
    """返回 (ok, detail)。
    ssh 失败                    -> (False, "ssh:<detail>")
    输出含 PORT8080_STILL_BUSY  -> (False, "port8080-still-busy")
    其余                        -> (True, "")
    """

def reclaim_and_unload(station: str) -> dict:
    """结构化结果，不抛异常。
    {
      "station": str,
      "ok": bool,
      "steps": [
        {"name": "containers", "ok": bool, "detail": str},
        {"name": "infer-unload", "ok": bool, "rc": int|None, "detail": str},
      ],
    }
    ssh_stream 抛连接异常 -> steps[-1].ok=False, detail="<ExcType>: <msg>"
    容器步失败            -> 跳过 infer-unload（SSH 已断或容器已删，再发无收益），
                             steps[1] = {"ok": False, "rc": None,
                                         "detail": "skipped: containers failed"}
    """
```

**调用契约**

| 调用点 | 旧行为 | 新行为 |
|---|---|---|
| `_load_rpc` | 回收 `{B, worker}`；仅 head unload；回收返回值被丢弃 | 对 `{head, worker}` 各调 `reclaim_and_unload`；任一失败 `return 1` |
| `_load_container_model` | 回收返回值被丢弃（unload rc 已检查） | 预检通过后 `reclaim_and_unload`；失败 `return 1` |
| `cmd_load` 普通路径 | 回收返回值被丢弃；unload 为条件式且 rc 已检查 | 统一 `reclaim_and_unload`；失败 `return 1` |
| `cmd_load_on` | 回收返回值被丢弃；unload 为条件式且 rc 已检查 | 统一 `reclaim_and_unload`；失败 `return 1` |
| `_cmd_load_c` | 回收返回值被丢弃 | 同上 |
| `cmd_unload_on` | 只返回 unload rc | 容器回收失败也计入 rc |
| `cmd_unload` | 只返回 unload rc | 每站 `reclaim_and_unload`；`ok=False` 该站记失败，最终 rc=1 |

> **单站路径改为无条件 unload 的理由**：旧代码用 `/health` 是否有响应来判定"是否占用"。
> 但容器被 `docker rm -f` 后，HTTP 服务已消失、GTT 仍可能被 docker-proxy/命名空间持有
> （本仓 C 站实测 8080 释放约 4m18s）⇒ 该条件恰好漏掉"容器已删但资源未释放"这一格。
> `infer-unload` 幂等且已含 `wait_gtt`，无条件执行既更简单也更正确。

### 4.4 容器预检

```python
def _host_path_for(spec: dict, inner: str) -> str:
    """纯函数。把容器内路径映射到宿主路径。
    volume 形如 "host:inner[:ro|:rw]"；按 inner 最长前缀匹配。
    无法映射 -> ""（调用方判为配方错误）。
    """

def classify_container_assets(spec: dict, observed: dict) -> list[str]:
    """纯函数。observed 形状：
    {"image": {"present": bool},
     "assets": {inner_path: {"kind": "file"|"dir"|"missing",
                             "size": int, "entries": int}}}
    返回 problems 列表（空 = 通过）。
    """

def preflight_container(alias: str, station: str) -> dict:
    """只读。返回 {"ok": bool, "problems": [str], "image_missing": bool}。
    ★ 不调用 docker rm/run、不调用 infer-unload、不写站上任何文件。
    """
```

**配方扩展（`cluster_const.CONTAINER_MODELS`）**

```python
"assets": [
    {"path": "/hgn/qwen38-flash-next-v2.hgn",    "kind": "file",
     "min_bytes": 60 * 1024**3},
    {"path": "/hgn/qwen38-flash-next-ngram.hgn", "kind": "file",
     "min_bytes": 45 * 1024**3},
    {"path": "/tokenizer",                       "kind": "dir", "min_entries": 1},
],
```

- 路径是**容器内路径**，宿主路径由 `_host_path_for` 从 `volume` 派生 ⇒ **不新增第二份 host 路径真值**。
- `min_bytes` 是**下限**而非精确值：只抓"没到 / 被截断 / 挂错目录"，不抓版本差异。
  实测 v2 62.11 GiB、ngram 47.68 GiB，取 60/45 GiB 留 ~2 GiB 余量。
- `checkpoint` 字段保留（`HALOGEN_CHECKPOINT` 需要它）；预检断言 `assets[0].path == checkpoint`。

**预检检查项**

| 检查 | 手段 | 失败文案 |
|---|---|---|
| 配方自洽 | 纯函数：每个 asset 可映射进 volume；`checkpoint` 与 asset 一致 | `recipe-unmapped:<inner>` / `recipe-checkpoint-mismatch` |
| 镜像存在 | `docker image inspect <image> --format '{{.Id}}'`（strict） | `image-missing` |
| 文件存在/大小 | 一次 SSH 循环：`-f` → `file\|<size>`（`stat` 失败 → `unreadable`）；`-d` → 可读则 `dir\|<entries>`，否则 `unreadable`；否则 `missing` | `asset-missing:<path>` / `asset-too-small:<path>` |
| 目录非空 | 同上（`entries`） | `asset-empty-dir:<path>` |
| 资产可读/类型一致 | 同上：`stat` 失败或目录不可读；观测 kind 与配方 kind 不符（Step 8 回写 D1） | `asset-unreadable:<path>` / `asset-not-file:<path>` / `asset-not-dir:<path>` |

### 4.5 门禁扩展

```python
def check_halogen_assets(ctx):
    """full 档只读断言。返回 (verdict, note, detail)，与 CHECKS 同约定。"""
```

注册：

```python
{"id": "halogen-assets", "title": "容器模型资产预检",
 "fn": check_halogen_assets, "quick": False,
 "fix": "按明细补资产/重分发权重；镜像缺失则 containers pull；不要先杀旧服务"}
```

`check_aliases` 增补判据：

```
旧: (real, st) in declared_conf  或  real in container_backed
新: (real, st) in declared_conf  或  (real in container_backed 且 (real, st) in declared_stations)
```

`declared_stations` 来自 `inventory/models.yaml` 的 `stations` 字段。
新增失败文案区分两种缺口：`无配方` 与 `有配方但 inventory 未声明该站`。

---

## 5. 替代方案

### 5.1 方案 A：只修 `probe-failed` 一个分支（否决）

改动最小，但只覆盖缺口 1；缺口 2/3 仍会让 worker 叠加、失败静默。
且"未知仍回收"的根因是**数据结构把三态压成字符串**，不换数据结构会复发。

### 5.2 方案 B：引入常驻 reconciler 自动收敛（否决）

K8s 式 level-triggered 控制器能自动重试，但需要 daemon 与持续 SSH 轮询，
与 ADR-0004「零自加载·无 daemon」直接冲突，且三站规模下收益不抵复杂度。
本设计只保留其**判定纪律**：失败不标记完成。

### 5.3 方案 C：把预检放在 `docker run` 之前、回收之后（否决）

仍会先杀掉可用服务再发现资产缺失，正是 Terraform 默认 `destroy-before-create`
的形态。本仓单卡单端口无法真正"新旧并存"，所以正确类比是
**validate before destroy**，而不是 `create_before_destroy`。

### 5.4 方案 D：每次加载对 `.hgn` 全量 sha256（否决）

单站 ~110 GiB × 3 站，IO 成本远超收益。存在性 + 大小 + 目录条目数足以覆盖
"未到/截断/挂错"；全量哈希留在分发流程与 full 验收。

### 5.5 方案 E：用 systemd `Conflicts=` 替代上层卸载（否决为主，保留为辅）

`Conflicts=` 能保证 `llama-server@*` 与 `rpc-server@*` 不同时 active，
但它**管不到手工拉起的进程**（studio 直接执行的二进制），且不隐含顺序。
故只能作为第二道防线，不能替代编排层卸载；若采纳需另立 ADR（扩写动作面）。

### 5.6 方案 F：并入 `check_stations` 而不是新开断言（否决）

`check_stations` 已承担 conf/权重/凭据/端口四类判据，再塞入容器资产会让
"失败归因"变模糊，且它复用的是 conf 视角的 `MODEL_PATH`。
新开 `halogen-assets` 保持单一职责；代价是 full 档多 2 次 SSH/站，可接受。

---

## 6. 数据结构

```python
# 探针
ProbeResult = {
    "state": "free" | "busy" | "unknown",
    "reason": str,          # free 时为空串；busy 为 "halogen+port8080"
}

# 选路
Decision = {
    "target": str | None,
    "station": str | None,
    "source": str,
    "reason": str,
}

# 回收
ReclaimResult = {
    "station": str,
    "ok": bool,
    "steps": [{"name": str, "ok": bool, "detail": str, "rc": int | None}],
}

# 预检
PreflightResult = {
    "ok": bool,
    "problems": [str],
    "image_missing": bool,
}
```

**审计日志（保持一行式，便于 grep）**

```
RPC_AUTO_WORKER source=auto target=10.10.11.3:50052 station=C :: conf A 忙(halogen) ⇒ 改用 C；C 空闲
RPC_AUTO_WORKER source=aborted-unknown :: A=unknown(ssh-failed: timeout) C=unknown(ssh-failed: timeout) ⇒ 中止，不做回收
RECLAIM station=A ok=False :: containers=ok, infer-unload=rc=1
PREFLIGHT qwen3.8-flash-next@B ok=False :: asset-missing:/hgn/qwen38-flash-next-ngram.hgn
```

---

## 7. 错误处理

| 条件 | 产生位置 | 结果 | CLI 行为 |
|---|---|---|---|
| 探针 SSH 失败/超时 | `classify_worker_probe` | `unknown` | 退出候选池；无候选 ⇒ rc=1 |
| 显式 worker 不可达 | `resolve_rpc_worker` | `aborted-unknown` | rc=1，**不回收** |
| 容器回收 SSH 失败 | `_reclaim_containers` | `(False, "ssh:...")` | 中止，rc=1 |
| 8080 超时未释放 | `_reclaim_containers` | `(False, "port8080-still-busy")` | 中止，rc=1 |
| `infer-unload` rc≠0 | `reclaim_and_unload` | `steps[-1].ok=False` | 中止，rc=1 |
| `infer-unload` 连接异常 | `reclaim_and_unload` | 捕获 → `ok=False` | 中止，rc=1 |
| 镜像不在站上 | `preflight_container` | `image_missing=True` | 后台拉取 + rc=1，**不回收** |
| checkpoint/ngram 缺失 | `preflight_container` | `asset-missing` | rc=1，**不回收** |
| tokenizer 空目录 | `preflight_container` | `asset-empty-dir` | rc=1，**不回收** |
| 资产不可读/类型不符 | `preflight_container` | `asset-unreadable` / `asset-not-file` / `asset-not-dir` | rc=1，**不回收** |
| 容器启动后未就绪 | 既有轮询 | 既有 | rc=1（不变） |
| 卸载路径某站失败 | `cmd_unload` | 该站记失败 | 最终 rc=1（不变） |

**行为矩阵（实施后回写手册 §3.3）**

| 场景 | 旧行为 | 新行为 |
|---|---|---|
| A/C 都 SSH 不通 | 选 C 并尝试回收 | 中止，`aborted-unknown` |
| A 忙、C 探测失败 | 选 C 并回收 | 中止，`aborted-unknown`（C 不可回收） |
| A 探测失败、C 空闲 | 选 A 并回收 | 选 C，A 不动 |
| worker 被普通引擎占用 | 只回收容器 → 叠加 | 回收容器 + unload 引擎 |
| 8080 480s 未释放 | 打印警告后继续 | 中止 |
| 镜像/权重缺失 | 先杀旧服务再失败 | 预检失败，旧服务不动 |

---

## 8. 不变式（Invariants）

1. **独占**：任一站的 `:8080` 在任一时刻只服务一个引擎或容器。
2. **未知不可破坏**：`unknown` 状态不得触发 `docker rm -f` 或 `infer-unload`。
3. **校验先于破坏**：容器模型的全部只读预检必须在第一次回收调用之前完成。
4. **失败不吞**：加载路径上任一破坏性步骤 `ok=False` ⇒ 立即中止；不得继续启动。
5. **预检只读**：`preflight_container` 不产生任何站上写动作或服务状态变化。
6. **路径单一真值**：宿主资产路径只能由 `volume` 派生，不得在配方里另写一份 host 路径。
7. **缺失即未知**：`probe` 缺键按 `unknown` 处理，不得默认 `free`。
8. **返回码不变**：CLI 仍只用 `0/1/2`。

---

## 9. 幻觉排除审查（Step 4 Review）

### 9.1 设计所依赖的事实逐条核对

| 设计断言 | 核对方式 | 结论 |
|---|---|---|
| `probe-failed` 进入"回收它"分支 | 实际调用 `resolve_rpc_worker`（E1） | ✅ 成立 |
| `_load_rpc` 只 unload head | 读 L1218-1224 | ✅ 成立 |
| `rpc-nodes` 不卸载引擎 | 读 `rpc-nodes` L83-97 | ✅ 成立 |
| 7 个调用点丢弃返回值 | grep `_reclaim_containers(` = 7 处（L792/L915/L1052/L1221/L1331/L1355/L1372） | ✅ 成立（Step 4 复核 6→7） |
| 容器加载先回收后查镜像 | 读 L913-929 | ✅ 成立 |
| 配方无 ngram 路径字段 | 读 `CONTAINER_MODELS` L136-173 | ✅ 成立（仅注释提到） |
| `check_aliases` 不校验站 | 读 L4941-4946 | ✅ 成立 |
| `ssh_stream` 会抛连接异常 | 读 `cluster_ssh.py` L114-128 | ✅ 成立（故需 try/except） |
| 改 `_reclaim_containers` 无外部消费者 | 全仓 grep（仅 `cluster.py` + 测试） | ✅ 成立 |
| 新增 O-176 不与现有编号冲突 | OPEN-ISSUES 最大 O-175 | ✅ 成立 |
| `check_halogen_assets` 可注册 | `CHECKS` 列表项格式（id/title/fn/quick/fix） | ✅ 成立 |

### 9.2 明确**不**声称的内容

- **不声称**已在真站制造过"worker 叠加"或"回收失败"故障；缺口 2/3/4 均为代码路径可证（E2），
  真站故障注入放在实施后的维护窗口。
- **不声称** docker-proxy 端口滞后在所有站都是 4m18s；该数字只是本仓 C 站一次实测。
- **不声称** K8s/Envoy/Terraform 的机制与本仓等价；只迁移判定语义，不迁移控制循环。
- **不声称** `min_bytes` 能发现同尺寸的损坏文件；它只抓截断/未完成/挂错目录。

### 9.3 语义变更的兼容性审查

| 变更 | 兼容性影响 | 处置 |
|---|---|---|
| `resolve_rpc_worker` 的 `busy` → `probe`，缺键=unknown | 现有纯函数测试 `_rw(conf)` 会失败 | 预期：先验红，测试改为显式传 `free` |
| `_reclaim_containers` 返回 `tuple` | 测试 mock `lambda st: ... or True` 失效 | 测试改传 `(True, "")` |
| 单站路径无条件 unload | B 站上会停 RPC worker | 接受：与"同站禁止叠加"一致；写入手册 |
| 新增 `halogen-assets` full 断言 | `--quick` 不受影响；full 增加约 6 次 SSH | 接受；pre-push 全量本来就要 1 次/站 |

---

## 10. 对实施的输入

### 10.1 工程约束

1. **先验红**：§10.4 的 T1–T14 必须先在新接口下失败，再改实现。
2. **双向自证**：每个判据（尤其"未知不回收"）需给出同源对照——只改状态，选择必须翻转。
3. **不新增文件型脚本**：所有逻辑留在 `cluster.py` / `rpc_check.py` / `cluster_const.py`。
4. **纯函数优先**：三态分类、选路、宿主路径映射、资产判定都做成纯函数，SSH 只在薄壳里。
5. **日志可 grep**：`RPC_AUTO_WORKER` / `RECLAIM` / `PREFLIGHT` 三个前缀固定。
6. **不破坏 `parse_worker_busy` 的既有行为**：它仍是解析器，只是被 `classify_worker_probe` 调用。

### 10.2 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 缺键=unknown 让旧调用路径变严 | 正常加载可能因一次 SSH 抖动中止 | 探针已有 20s 超时；中止信息明确；可显式 `--worker` 重试 |
| 无条件 unload 在 B 站停掉 RPC worker | 并行任务被打断 | 本仓纪律是换模串行；手册写明"load 即独占该站" |
| 预检增加加载前延迟 | 秒级 | 只 2 次 SSH（image inspect + 一次 stat 循环） |
| `min_bytes` 阈值过松/过紧 | 漏检或误报 | 取实测值的 ~96%；阈值集中在配方，可单点调整 |
| 新断言拖慢 full 门禁 | 约 6 次 SSH | 只注册 full；不放入 pre-commit quick |

### 10.3 实施顺序（供 IMPLEMENTATION.md 展开）

1. **Phase 0**：补 T1–T14 夹具并确认红。
2. **Phase 1**：`classify_worker_probe` + `probe_worker_state` + 新 `resolve_rpc_worker`；
   接线 `_load_rpc` 的 probe/explicit 分支。
3. **Phase 2**：`_reclaim_containers` 改 `(ok, detail)`；新增 `reclaim_and_unload`；
   更新 7 个调用点（含 `cmd_load_on`）；RPC 路径回收范围改为 `{head, worker}`。
4. **Phase 3**：`CONTAINER_MODELS.assets`；`_host_path_for`、`classify_container_assets`、
   `preflight_container`；`_load_container_model` 前置预检。
5. **Phase 4**：`check_aliases` 站级校验 + 新 `halogen-assets` 断言。
6. **Phase 5**：跑 `tests/test_cluster_pure.py` → `rpc_check --quick` → full；
   维护窗口做真站故障注入（拔 SSH / 占 8080 / 临时改名权重），确认全部响亮中止。
7. **Phase 6**：回写手册 §3.3 行为矩阵；登记 O-176；更新 ADR-0014 若涉及写动作扩权。

### 10.4 先验红测试矩阵

| # | 用例 | 注入 | 期望 |
|---|---|---|---|
| T1 | 两站 unknown | `probe={A:u,C:u}` | `target=None`, `source=aborted-unknown` |
| T2 | conf 忙 + 备选 unknown | `probe={A:busy,C:u}` | 中止，**不选 C** |
| T3 | conf unknown + 备选 free | `probe={A:u,C:free}` | 选 C，A **不被回收** |
| T4 | 显式 worker unknown | `probe={C:u}`, `--worker C` | 中止，回收调用次数 = 0 |
| T5 | worker 忙因为普通引擎 | `probe={A:busy,C:busy(port8080)}` | B、C 都收到 `reclaim_and_unload` |
| T6 | head 卸载失败 | head `infer-unload` rc=1 | 中止，未调 `rpc-nodes --start` |
| T7 | worker 卸载失败 | worker rc=1 | 中止 |
| T8 | 容器回收失败 | `(False, "ssh:...")` | 中止 |
| T9 | 端口未释放 | 输出含 `PORT8080_STILL_BUSY` | `ok=False`，中止 |
| T10 | 缺 checkpoint | observed 缺该路径 | `problems` 含 `asset-missing`，**回收 0 次** |
| T11 | 缺 ngram / tokenizer 空 | 同上 | 同上 |
| T12 | 镜像缺失 | `image.present=False` | `image_missing=True`，回收 0 次 |
| T13 | 宿主路径映射 | 纯函数：`/hgn/x` → volume 派生路径（= models_dir/x） | 映射正确；未挂载路径 → `""` |
| T14 | aliases 站级缺口 | inventory 缺 A 站声明 | 门禁 FAIL，文案指明"有配方但未声明" |

**测试资产改动点**

- `tests/test_cluster_pure.py` L270-297：`_rpc_reclaim_probe` 增加 `probe`、`reclaim`、
  `unload_rc` 参数；替换 `_reclaim_containers` / `_probe_worker_busy` 的 mock 形状。
- 同文件 L449-504：`_rw()` 改为传 `probe`，并新增 T1–T4 用例。
- 新增独立小节：T10–T13（纯函数 + SSH mock）。

---

## 11. 验收标准

1. `py tests/test_cluster_pure.py` **ALL PASS**，且新增用例在改动前**确实红过**。
2. `rpc_check --quick` PASS（pre-commit）；full 档 `halogen-assets` PASS。
3. 真站故障注入四项全部**响亮中止**且旧服务未被误杀：
   - 拔掉 worker SSH（模拟 unknown）；
   - 在 worker 手工起普通引擎占 8080；
   - 临时 `mv` 走 ngram 文件；
   - 临时 `docker rmi` 镜像（只在维护窗口，且随后恢复）。
4. 正常路径不回归：qwen 容器加载 READY；GLM RPC 加载在 A 忙时仍自动选 C。
5. 手册 §3.3 行为矩阵与实现一致；O-176 登记且引用本设计。

---

## 12. 附：待决问题

| # | 问题 | 建议 |
|---|---|---|
| Q1 | 是否采纳 systemd `Conflicts=` 作为第二道防线 | 本轮不做；若做另立 ADR（扩写动作面） |
| Q2 | `halogen-assets` 是否也检查非 `stations` 声明的站 | 不检查；避免对"未部署"的站假红 |
| Q3 | `min_bytes` 是否改为读 `inventory` | 暂不；配方内静态常量更直观，且只有一个模型 |
| Q4 | 是否把 `RECLAIM` 结果写入台账 | 本轮只打印；如需留痕，走既有日志/台账纪律另议 |
