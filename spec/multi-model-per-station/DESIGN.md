# 设计：单站多模型共存（P0 容量门 + P1 alias 级卸载）

---

id: multi-model-per-station-DESIGN
type: design
version: 1.0
status: draft
date: 2026-10-28
depends: []
upstream: null

---

> **Feature**: 把「同站禁止叠加加载」这条准则从**硬禁止**改为**按容量准入**：站上已有一个引擎时，只要内存余量算得下，就允许再加载一个**不同别名**的模型（例：`gpt-oss-20b` 11.5G + `qwen3.8-27b-mtp` 29.5G 共存）。本轮只做 **P0 容量门**与 **P1 alias 级卸载**两刀，P2 之后（端口真值 / 网关寻址 / 声明式共存组）只登记不做。
> **创建日期**: 2026-10-28
> **状态**: draft（Step 3 实施中；Step 4 设计评审后改 verified）
> **Spec 步骤**: Step 2（DESIGN）→ Step 3（IMPLEMENTATION）→ Step 4（设计评审）→ Step 5（验收，见 [CHECKLIST](./CHECKLIST.md)）
> **基于调研**: 本文 §2（仓库现状盘点 + 社区案例 + 容量算账）
> **代码基线**: `8031a406`（`main`）

---

## 1. 目标与非目标

### 1.1 目标

| # | 目标 | 判据 |
|---|---|---|
| G1 | 站上已有引擎时，`load <另一别名> --keep` 在**内存算得下**时成功叠加 | 真站：B 站空载先 `load gpt-oss-20b`，再 `load qwen3.8-27b-mtp-b --keep` ⇒ 两个 `llama-server@` 同时 active，8080 与 18080 各自 `/health` 200 |
| G2 | 算不下时**响亮拒绝**，不先破坏再失败 | 容量门返回非 0，且**未发**任何 `systemctl stop` / `docker rm` / `rpc-nodes --start` |
| G3 | 卸载可按别名 | `infer-unload <alias>` 只停该别名的 `llama-server@` 与各站 `rpc-server@`；无参数 = 现行为（全停） |
| G4 | 默认行为**零变化** | 不带 `--keep` 时，回收范围、顺序、日志与非 RPC/容器路径全部与 `8031a406` 一致；69 个既有测试全绿 |
| G5 | 判不了 ≠ 通过 | 预估返回 `UNKNOWN`（缺 conf / 缺 gguf-meta / 缺内存读数）⇒ 拒绝加载并说明缺什么 |

### 1.2 非目标（本轮刻意不做）

1. **P2 端口真值**：`18080` 未登记 `inventory/ports.yaml`，`ports` 门禁的站上对账仍会黄；本轮不补表。
2. **P3 网关寻址**：客户端（opencode / claude）仍只认 `127.0.0.1:8080`；第二个模型只能 `ssh <站> curl 127.0.0.1:<port>` 访问。
3. **P4 声明式共存组**（`COEXIST_GROUPS`）、**P5 router 模式**（上游 `--models-dir/--models-max`）。
4. **worker 站兼作第二 head**：`rpc-server@<alias>` 的 GTT 与 head 权重同池竞争，本轮维持「worker 站独占」。
5. 不改 `cluster.py unload`（无参数）的三站全停语义。

---

## 2. 调研

### 2.1 仓库现状（哪些已具备、哪些挡路）

**已具备 —— 不需要新建机制**

| 能力 | 证据 |
|---|---|
| 一 alias 一 systemd 实例 | `llama-server@%i` 模板；[llama-serve-instance](../../ops/station-bin/llama-serve-instance#L58-L61) 从 conf 读 `PORT`，绑 `127.0.0.1` |
| 每模型独立端口（conf 级） | `/etc/llama-instances/qwen3.8-27b-mtp.env` 的 `PORT=18080`（B/C 皆有）；`infer-load --port` 已支持 |
| 每 alias 独立 ctx/KV/flags | conf 的 `CTX` / `N_CPU_MOE` / `EXTRA_FLAGS` 本就是 per-alias |
| 容量预估已有 | [`estimate_load`](../../ops/cluster_runtime.py#L210-L360) 产出 `weights_gib / kv_gib / ssm_gib / overhead_gib / need_gib / mem / verdict(FITS·TIGHT·NO_FIT·UNKNOWN) / reasons / advice` |
| 引擎支持上游 router 模式 | B/C 站实测 `--models-dir / --models-max / --models-preset / --no-models-autoload` 全在（`0.6.0-dev`） |

**挡路的三处（这就是本轮要动/登记的）**

| # | 现状 | 后果 | 本轮 |
|---|---|---|---|
| B1 | [infer-unload](../../ops/station-bin/infer-unload#L7-L8) 通配 `systemctl stop 'llama-server@*'` / `'rpc-server@*'` | 无法只卸一个别名 | **P1 修** |
| B2 | [`_load_container_model`](../../ops/cluster_runtime.py#L993-L998) 写死「互斥: 同站禁止叠加加载」；`reclaim_and_unload(station)` 全站回收 | 第二刀必然先杀第一刀 | **P1 修（`--keep` 分支）** |
| B3 | 客户端与探针把 `127.0.0.1:8080` 写死（[cluster_runtime](../../ops/cluster_runtime.py#L1206)、[cluster_flow](../../ops/cluster_flow.py#L63)、[agent-cli.ps1](../../ops/station-bin/agent-cli.ps1#L5840)、[_station_ready.sh](../../ops/station-bin/_station_ready.sh#L11)） | 第二个模型「起来了没人找得到」 | P2/P3 登记 |

**一个容易忽略的事实**：[ports.yaml](../../inventory/ports.yaml#L69-L71) 记着「引擎**忽略**请求里的 `model` 字段，服务的永远是当前加载的那个」⇒ **不能**靠「一个 8080 按模型名路由」。多模型寻址必须靠「per-alias 端口 + 客户端映射」或「外部网关」，这是 P3 的立论基础。

### 2.2 社区案例（决定"默认值"与"上限"从哪来）

| 方案 | 多模型并存机制 | 对本设计的含义 |
|---|---|---|
| LM Studio | 每模型一实例；Server 按 model 名路由；JIT + 空闲 TTL（默认 60 min）+ **Auto-Evict 默认开** ⇒ JIT 只留 1 个，**关掉才允许多个常驻** | 「能加载多个」的前提是**显式关掉驱逐** ⇒ 我们也应**默认互斥、显式开放** |
| Ollama | `OLLAMA_MAX_LOADED_MODELS`（默认 3×GPU 数，**前提是装得下**）+ `OLLAMA_KEEP_ALIVE` | 默认不是禁止而是「**容量准入 + 有上限**」⇒ 容量门是主判据 |
| llama-swap | 一个端口按 model 名路由；`groups` 表达 `swap`（组内留一）/ `exclusive`（载入清空它组）/ `persistent`（免疫驱逐）/ per-model `ttl` | P4 的 `COEXIST_GROUPS` 直接对标 `groups`；本轮先用 `--keep` 表达「这一刀允许叠加」 |
| llama.cpp 上游 router | 不带 `-m` 即 router：`--models-dir` / `--models-max N`（默认 4，0=不限）/ `--models-preset` INI 给每模型独立参数 | 我们的引擎**已支持**，但会把生命周期从 systemd 收进引擎；与 RPC worker、TTL、门禁的组合**未验证** ⇒ 列 P5 |

### 2.3 容量算账（B 站实测，2026-10-28）

| 项 | 值 |
|---|---|
| GTT 上限（三站一致） | **125.8 GB** |
| `gpt-oss-20b`（MXFP4）权重 | **11.5 GB** |
| `qwen3.8-27b-mtp`（Q8_0，ctx 32768，mmproj+MTP）权重 | **29.5 GB** |
| 两者权重合计 | **41 GB** + 两套 KV |
| 空站结论 | ✅ 余量充足，可共存 |
| 当前 B 站（deepseek 1M 占 84.0 GB） | 余 ~41.8 GB ⇒ **放不下这两者** |
| 当前 A 站（deepseek worker 占 110.7 GB） | 余 15.2 GB ⇒ **任何叠加都不行** |

> **单位口径**（P0 补强实测校准）：`mem_info_gtt_total` = 125 829 120 000 B ⇒ **125.8 GB = 117.2 GiB**。
> 容量门内部一律按 **GiB**（`/1024³`），文案也标 `GiB`；上表的 GB 只用于与模型体积（`du` 输出）对齐。

⇒ 「在容量允许的条件下」必须是**机器判据**：这就是 P0 存在的理由。

---

## 3. 决策

| # | 决策 | 理由 |
|---|---|---|
| D-1 | **默认仍互斥**：不带 `--keep` 时 `load` 保持全站回收（现行为） | 与 LM Studio 的 Auto-Evict 默认一致；不改变 69 个既有测试与运维肌肉记忆 |
| D-2 | **共存必须显式**：`load <alias> --keep` 才走「alias 级回收 + 容量门」 | 「允许」不等于「默认」；P4 落地后由 `COEXIST_GROUPS` 接管，`--keep` 保留为一次性开关 |
| D-3 | 容量门**只在 `--keep` 时生效** | 默认路径会先清空该站，预估的 `used` 是卸载前的读数，此时判"装不下"是**假阴性** |
| D-4 | `verdict ∈ {FITS, TIGHT}` 放行；`NO_FIT` **exit 4**；`UNKNOWN` **exit 4** | TIGHT 与 [`cmd_estimate`](../../ops/cluster_runtime.py#L1686) 同口径（它 `return 0`）；`UNKNOWN` 不得当作通过 |
| D-5 | 反向冲突预检（`--force`，exit 3）**先于**容量门 | 「会崩别人」比「放不下」更严重；两条拒绝面互不替代 |
| D-6 | `infer-unload` 用**位置参数**而非 `--alias` | 站上是 bash 脚本、无参数解析器；`infer-unload <alias>` 与 `systemctl stop unit` 的肌肉记忆一致，且旧调用（无参）零改动 |
| D-7 | `infer-unload <alias>` **不**执行 `pkill`（unsloth / ds4 / vllm）与远端全量清扫 | 那些没有 alias 归属；alias 模式下照杀等于**换个名字继续全站清空**，与目标相反 |
| D-8 | 容量门用**两道判据**：`estimate_load` 的 verdict（算「要多少」）+ 站上 **GTT 实账**（算「还剩多少」）+ 站级预留 8 GiB；GTT 读不到 ⇒ 回退 verdict 并留痕 | UMA 下 `MemAvailable` 把可回收缓存算成空闲（偏乐观）；而 10-26 两次 `vk::DeviceLostError` 都发生在 GTT 余 15~24G ⇒ 「塞得进」≠「跑得稳」。同族做法见 GPUStack `system_reserved`（[调研 §5](../../docs/research/2026-10-28_gpustack可复用性分析.md)） |

---

## 4. P0 契约（容量门）

### 4.1 纯函数

```python
def _capacity_ok(verdict: str) -> bool
def _uma_fit(total_gib, used_gib, reserved_gib, need_gib) -> tuple   # (放得下?, 可用 GiB)
def _station_gtt(station: str) -> tuple                              # (ok, used_gib, total_gib)
```
`_capacity_ok`：`FITS` / `TIGHT` ⇒ True；`NO_FIT` / `UNKNOWN` / 其它 ⇒ False。
`_uma_fit`：`alloc = max(total − used − reserved, 0)`，`放得下 = need ≤ alloc`。
`_station_gtt`：读 `/sys/class/drm/card*/device/mem_info_gtt_{used,total}`；解析失败 ⇒ `ok=False`。
三者**都不读全局状态**，可直接单测。

### 4.2 编排函数

```python
def _guard_capacity(station: str, alias: str) -> int
```
- 别名属于 `CONTAINER_MODELS` ⇒ 打一行「容器模型换算不走 estimate」并返回 0（容器内存由 halogen 自行下调，属 P2）
- **第 1 道**：调 `estimate_load(station, alias)`；`ok=False` 或 verdict ∈ {NO_FIT, UNKNOWN} ⇒ 打印 `need_gib / mem / verdict / reasons / advice`，返回 **4**
- **第 2 道（P0 补强，D-8）**：读站上 GTT 实账，`_uma_fit(total, used, STATION_RESERVED_GIB=8, need)`；不 fit ⇒ 打印 `total/used/reserved/alloc/need` 并返回 **4**；GTT 读不到 ⇒ **回退第 1 道**并打印留痕（不因缺读数而拒绝，也不假装精确）
- 放行时打印 `CAPACITY ok verdict=… need=…GiB`（若第 2 道跑过，其读数已在上一行）

### 4.3 调用点（唯一）

[`cmd_load`](../../ops/cluster_runtime.py#L1118) 在**反向冲突预检之后**：

```
if keep and not is_rpc: ...  # 见下
_guard = _guard_capacity(target, matched)   # 仅 keep
```

- RPC 双机（`_load_rpc`）本轮**不开放** `--keep`：head 与 worker 的 GTT 耦合（O-175/O-178）尚未算清 ⇒ `load <rpc模型> --keep` 直接 **exit 1** 并说明。
- 容器模型（halogen）本轮允许 `--keep`，但跳过容量门（见 4.2）。

---

## 5. P1 契约（alias 级卸载）

### 5.1 站上脚本

```
infer-unload              # 现行为：本站 llama-server@* + rpc-server@*（本地+远端）+ 容器 + unsloth/ds4/vllm
infer-unload <alias>      # 只停：本站 llama-server@<alias>
                          #       本站 rpc-server@<alias>（若存在）
                          #       各远端节点的 rpc-server@<alias>
                          #       该别名的容器（若 alias ∈ CONTAINER_MODELS）
                          # 不执行 pkill（D-7），并在日志里写明跳过原因
```

### 5.2 Python 侧

| 函数 | 变化 |
|---|---|
| `reclaim_and_unload(station, alias=None)` | 传 `alias` ⇒ `ssh_stream(station, f"infer-unload {sh_single_quote(alias)}")`；容器步只在「alias 是容器模型」时执行 |
| `_reclaim_containers(station, alias=None)` | `alias` 非容器模型 ⇒ 直接返回 `"skipped: keep"`，不 `docker rm` |
| `_load_container_model(alias, station, keep=False)` | `keep=True` ⇒ `reclaim_and_unload(station, alias)` |
| `_load_rpc(...)` | 保持 `reclaim_and_unload(st)`（全站）不变；`--keep` 在入口拒绝 |
| `cmd_unload_on(station, alias=None)` | web/CLI 单站卸载可带 alias |
| `cmd_unload(alias=None)` | 三站：带 alias 时逐站点卸该别名（B 先、A/C 并行，顺序不变） |

### 5.3 CLI

```
cluster.py load <alias> [--keep] [--force] ...
cluster.py unload [--alias <alias>] [--station A|B|C]
```

`--keep` 与 `--force` 正交：前者=「允许叠加（要过容量门）」，后者=「明知会打断别人的 head 也继续」。

---

## 6. 后续（本轮不做，只登记）

| # | 内容 | 状态 |
|---|---|---|
| P2 | **端口预留记录**：真值 = 各别名站上 conf 的 `PORT`（不造 alias→port 第二张表）+ 加载前**端口门**（`_port_clash` / `_model_port` / `_station_model_ports` / `_guard_port`，撞口 ⇒ exit 5）+ `ports.yaml` 登记 `18080` 暴露面 + 派生视图重渲染 | ✅ **已做（2026-10-29）** |
| P2-余 | 6 处写死 `127.0.0.1:8080` 的探针/客户端改按 alias 取；`load --port N` 暴露（现在只能改站上 conf） | 未做（与 P3 一起做更省：网关定下来后这些点会变） |
| P3 | 网关寻址（llama-swap 优先）：站上 8080 由网关占，按 model 名转 18080/18081 | 未做 |
| P4 | `COEXIST_GROUPS`：对标 llama-swap `groups`，默认互斥、显式允许 | 未做 |
| P5 | 上游 router 模式（`--models-dir/--models-max`） | 未做 |

> **P2 为什么不做 GPUStack 式的「动态分配 + generation 乐观重试」**：那套是给「起容器前不知道端口、需要协商」的场景用的；本仓端口由 conf 静态定义且 `llama-serve-instance` 直接消费 —— 做动态分配器会与 conf 抢真值，并引入持久化依赖。这里取它的**判据精神**（判「谁的端口」而不是「有没有人占」），落地为「读同站已运行别名各自的 conf PORT 再比对」。
> **P2 实测发现**：`gpt-oss-20b.env` 的 `PORT=8080` 与 deepseek 相同 ⇒ 「gpt-oss-20b + qwen3.8-27b-mtp 共存」必须先给前者换端口（改 conf 或用 P2-余 的 `--port`），这正是端口门第一次真跑就报出 `exit 5` 的原因。

---

## 7. 风险、回滚与边界

| 风险 | 处置 |
|---|---|
| 内存紧张时 worker 侧 `vk::DeviceLostError`（O-178 A/B 类，10-26 两次） | 容量门用 `estimate_load` 的 `pad_gib`（默认 12G）；`TIGHT` 放行但打印告警；worker 站本轮禁止 `--keep` |
| 端口撞车（新别名 conf `PORT` 与同站已运行模型相同） | **P2 已转前置判据**：`--keep` 时 `_guard_port` 比对同站已运行别名各自的 conf PORT，撞口 ⇒ exit 5 并点名是谁占着；判不了（ssh 失败）⇒ 留痕放行，仍由健康检查兜底 |
| 别名大小写/连字符注入到站上命令 | `sh_single_quote` 包裹（既有序言） |
| 回滚 | 两刀各自独立：`--keep` 不被使用时行为与基线**完全一致**；`infer-unload` 无参数路径逐字未改 |

---

## 8. 未实测登记

1. `--keep` 真站共存（`gpt-oss-20b` + `qwen3.8-27b-mtp` 同站同时 READY）**未跑**；P0/P1 只有单测与静态断言，真站验证排在 Step 5（CHECKLIST §2）。`state: todo` · `blocker: run`
2. worker 站叠加第二个 head 的 GTT 行为**未测**；本轮用「RPC 禁止 `--keep`」绕过。`state: boundary` · `blocker: decision`
3. 容器模型（halogen）在 `--keep` 下的容量判定**未实现**（`estimate_load` 读 conf，容器无 conf）⇒ 目前直接放行。`state: todo` · `blocker: implementation`
4. 端口撞车未做前置判据（见 §7）。`state: todo` · `blocker: implementation`
5. 客户端对第二个模型的寻址**未做**（P3）。`state: boundary` · `blocker: implementation`
6. 上游 router 模式与 RPC worker 的组合**未验证**（P5）。`state: todo` · `blocker: run`
