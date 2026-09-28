# 设计文档：ds4 (DwarfStar) 后端并入统一管理面

---

id: ds4-backend-DESIGN
type: design
version: 1.0
status: draft
date: 2026-09-28
depends: [ADR-0010]
upstream: null
---

> **Feature**: 把 DwarfStar（ds4）作为**第 4 个后端**并入 `ops/cluster.py` 的 `infer-load` 体系，使**单机 resident** 与**双机 PP** 的起停/探活/卸载全部从**唯一管理面**执行，不新增并列入口与一次性脚本。
> **创建日期**: 2026-09-28
> **状态**: draft（草稿）
> **Spec 步骤**: Step 3-4
> **基于调研**: [DwarfStar 前置核验与 ROCm 工具链安装决策](../../docs/research/2026-09-28_DwarfStar前置核验与ROCm工具链安装决策.md)（**本设计的全部事实来源**）

---

## 1. 设计目标

为 ds4 提供与 `unsloth / llama-rpc / llama-single / vllm` 同级的**后端入口**，使三件事从 `cluster.py` 一次做完：① 单机 resident 加载／卸载；② **双机 PP**（coordinator+worker）跨站编排；③ 只读探活并入 `cluster.py status`。
**不做**：不把 ds4 变成常驻服务、不动 `/opt`、不改 llama.cpp 主路线。

---

## 2. 设计依据

### 2.1 调研结论

| 调研发现 | 设计决策 | 引用 |
|---|---|---|
| ds4 二进制在**用户域** `~/ds4/`；运行需 `LD_LIBRARY_PATH=/opt/rocm/core-10.0/lib/rocm_sysdeps/lib:/opt/rocm/core-10.0/lib` | 启动命令由**入口统一注入**该环境变量，**不写系统 profile** | 执行记录 §11.3 / §11.5 |
| ds4 **不是通用 GGUF 加载器**（只认自家 5 类量化）；GLM 档在 `~/ds4/gguf/` | conf 里 `MODEL_PATH` 指向 **ds4 专属目录**，**不并入** `/data/models/gguf` 的 llama.cpp 模型库 | §13.1 |
| **TP 在 ROCm 被拒**（`tensor parallelism requires the Metal backend`）；**PP（`--layers`）可用** | 双机模式**只实现 PP**；不提供 `--tensor-parallel` 路径 | §12.2 |
| PP 语义：`--role coordinator|worker` + `--layers A:B` + `--listen/--coordinator <ip> 9911`（TCP） | 双机编排按「**先 worker、后 coordinator**」；端口固定 **9911** | 官方 DISTRIBUTED.md（§12.2 旁证）|
| B↔C 有 **USB4 直连**（10.10.11.1 ↔ 10.10.11.3，ssh 免密双向） | PP 的 `--coordinator` 取**直连段地址**，非管理网 | §14.3 |
| ROCm 10.0 的安装**未写 ld.so.conf / LD_LIBRARY_PATH**；现役 llama `not-found=0` | 入口**不做任何全局库路径改动**（改动面为零，只需进程级 env） | §11.3 / §14.2 |

### 2.2 相关 ADR

| ADR | 决策 | 对本设计的影响 |
|-----|------|--------------|
| [ADR-0004](../../adr/ADR-0004-统一管理入口为唯一管理面.md) | 唯一管理面 = `cluster.py`；新增管理能力**加子命令**，不新增并列入口；临时件放 `tmp/` | 本设计**唯一合法形态**：扩展 `BACKENDS` + `infer-load`，不写新脚本 |
| [ADR-0010](../../adr/ADR-0010-DwarfStar第二引擎引入立项.md) | **v1.1 裁决 accepted（2026-09-28，范围收窄）**：批准 B 站试点；**D4 = 起停/探活并入 `cluster.py`**；能力边界 = **单机（PP 冻结）**、专用 GGUF | 本设计的直接授权与边界。★ 本文 §4.2 的 **PP 编排已实施且编排正确**（`2054370`：worker-first / route 建立 / 就绪语义），但**引擎前向崩溃**（上游 `antirez/ds4#1141`）⇒ **PP 冻结，单机为交付形态** |

### 2.3 职责边界

- **职责内**：ds4 进程的**生命周期编排**（起/停/探活）、PP 跨站的**先后序**、conf 读写、与门禁的对接。
- **职责外（显式排除）**：① 不实现 ds4 引擎内部（属上游）；② 不接管模型**下载**（走既有 `lm-download@` 组件，见 §5.3）；③ 不改变 `EV-4`（第二栈生命周期）的裁决 —— 本设计只做「**入口化**」，长期归属仍待 EV-4；④ 不把 ds4 并入 llama.cpp 的 `UPGRADE_SOP`。

---

## 3. 架构设计

### 3.1 整体架构

```
ops/cluster.py（唯一入口）
  ├─ load  <alias> --backend ds4 [--station B|C] [--pp] ... ──┐
  ├─ unload --backend ds4                                     │ ssh 到站
  └─ status（只读探活 ds4 进程 + 9911）                        │
                                                              ▼
站上 /usr/local/bin/infer-load（既有 station_runtime 件）
  ├─ 读 conf → /etc/ds4-instances/<alias>.env
  ├─ 注入 LD_LIBRARY_PATH（core-10.0）
  └─ 单机：nohup ~/ds4/ds4-server --rocm -m <gguf> --ctx N --host 127.0.0.1 --port P
     双机：worker → ~/ds4/ds4 --role worker --layers A:B --coordinator <ip> 9911
           coordinator → ~/ds4/ds4-server --role coordinator --layers A:B --listen <ip> 9911
```

### 3.2 模块划分

| 模块 | 职责 | 输入 | 输出 | 依赖 |
|------|------|------|------|------|
| `cluster_const.BACKENDS` | 加入 `"ds4"`（白名单，5 项） | — | — | 既有 |
| `cluster_const.PP_MODELS` | 双机 PP 类模型集合（对标既有 `RPC_MODELS`） | — | — | 既有形态 |
| `cluster.cmd_load` / `cmd_load_on` | 识别 `ds4` 后端 → 走 ds4 编排；`--pp` 触发双机分支 | alias/backend/station/pp | 站上拉起 | 既有函数改造 |
| `cluster._load_ds4`（新内部函数） | 单机/双机 PP 编排（含先后序与两站 env） | alias/conf/目标站 | 两站进程 | 本设计 |
| `station-bin/infer-load` | **站上**解析 `--backend ds4`，读 conf、起进程 | conf | 进程 + 日志 | 既有 station_runtime |
| `cluster.cmd_status` | 增加 **只读** ds4 探测（进程 + `9911` LISTEN）→ `ds4: RUNNING/STOPPED` | — | 一行状态 | 既有函数改造 |

### 3.3 数据流

`conf（/etc/ds4-instances/<alias>.env）` → `infer-load` 读 → 拼 `ds4` 命令行（含 `LD_LIBRARY_PATH`）→ `nohup` 起进程 → 日志落 `/var/log/ds4/<alias>.<role>.log`；**PP 时** coordinator 等待 worker 先注册路由。

### 3.4 控制流（PP 关键序）

1. `cluster.py load glm53-q4 --backend ds4 --pp --station B --peer C --layers 0:|||`
2. 入口**先**在 `--peer`（C）起 **worker**（`--role worker`）；
3. **再**在 `--station`（B）起 **coordinator**（`--role coordinator`）；
4. 探活：`9911` 在 coordinator 侧 LISTEN + 两侧进程存活；
5. `unload` **反序**：先停 coordinator，再停 worker（避免 worker 空等）。

---

## 4. 接口定义

### 4.1 CLI（唯一入口）

```
python ops/cluster.py load <alias> --backend ds4 [--station B|C] [--ctx N] [--port P]
python ops/cluster.py load <alias> --backend ds4 --pp --station B --peer C --layers A:B
python ops/cluster.py unload --backend ds4
python ops/cluster.py status            # 含 ds4: RUNNING / STOPPED（只读）
```

### 4.2 conf（站上，两站同路径）

```bash
# /etc/ds4-instances/glm53-q4.env
MODEL_PATH=/home/scott-lau/ds4/gguf/GLM-5.3-Flash-Q4_K.gguf
ROCM_PATH=/opt/rocm/core-10.0
CTX=32768
BACKEND=rocm
# 双机 PP 追加：
PP_ROLE=                # coordinator | worker | 空=单机
PP_LAYERS=              # 例 0:19 / 20:output
PP_PEER=                # coordinator 的直连段地址（USB4），如 10.10.11.1
PP_PORT=9911
```

### 4.3 内部函数

```python
def _load_ds4(
    alias: str,
    station: str,
    conf: dict,
    peer: str | None = None,      # 仅 PP
    layers: tuple[str, str] | None = None,
) -> int:
    """
    拉起 ds4。单机：在 station 起 ds4-server。
    双机 PP：先在 peer 起 worker，再在 station 起 coordinator（序不可反）。

    Returns:
        0 成功；非 0 失败（子进程/探活失败）

    Raises:
        不抛异常 —— 失败以退出码 + stderr 报出（与既有 cmd_load 一致）
    """
```

---

## 5. 替代方案

### 5.1 方案 A: 扩展既有 `infer-load` + `BACKENDS`（**选择**）

- 描述: 把 `ds4` 作为第 5 个后端并入既有 `--backend` 白名单与 `infer-load`，PP 对标既有 `RPC_MODELS` 双机编排。
- 优点: ① 零新增入口（合 ADR-0004 D1）；② 复用既有互斥/探活/台账；③ 与 `llama-rpc` 双机先例**同构**，读者一次学会两处。
- 缺点: `station-bin/infer-load` 需增一个 backend 分支；`cmd_load` 需增 PP 分支。
- 选择理由: **唯一同时满足 ADR-0004 与 ADR-0010 D4 的形态**。

### 5.2 方案 B: 独立 `cluster.py ds4 ...` 子命令族（否决）

- 描述: 新开 `cluster.py ds4 load/unload/status`。
- 优点: 语义直白，不触碰既有 `infer-load`。
- 缺点: 与 `--backend` 体系**并列**，形成"第二套加载语义"；`status`/`unload` 会各写一份，**正是 ADR-0004 要防的重复入口**。
- 否决理由: 撞 ADR-0004 D1/D4。

### 5.3 方案 C: 在 `cluster.py` 内直接实现下载 + 起停（否决）

- 描述: 把模型下载也收进 `cluster.py`。
- 优点: 一处到底。
- 缺点: **下载已有既有组件 `lm-download@`（aria2c + 双验 + 断点续传）**；再造一份等于**重复实现 + 两处真值**。
- 否决理由: 违反「不新建体系，只做接线」（方案 v2 §6 已定）。本设计**只接线**：`cluster.py` 增一个"派发 lm-download 任务"的**薄封装**（可选，非必须）。

### 5.4 方案 D: 用 systemd unit 管 ds4（否决）

- 描述: 仿 `llama-server@` 做 `ds4@.service`。
- 优点: Cockpit 服务页免费集成。
- 缺点: 与**零自加载纪律**及 vLLM 先例（**手动进程**）不一致；且 PP 需**两站两进程**，unit 表达力不足。
- 否决理由: 违背手册「开机 = 零自加载」；与已确立的 vLLM 形态不一致。

---

## 6. 数据结构

```python
@dataclass
class Ds4Conf:
    model_path: str          # ds4 专属 GGUF（~/ds4/gguf/*.gguf）
    rocm_path: str = "/opt/rocm/core-10.0"
    ctx: int = 32768
    backend: str = "rocm"
    pp_role: str | None = None       # coordinator | worker | None
    pp_layers: str | None = None     # "0:19" / "20:output"
    pp_peer: str | None = None       # 直连段地址
    pp_port: int = 9911
```

---

## 7. 错误处理

| 错误场景 | 处理方式 | 用户可见信息 |
|---|---|---|
| `--pp` 未给 `--peer`/`--layers` | 入口即拒，不起任何进程 | `ds4 PP 需要 --peer 与 --layers` |
| PP 中 worker 未起即起 coordinator | **强制先后序**，入口内保证；若 worker 起失败则**中止且不起 coordinator** | `worker 启动失败，已中止（未起 coordinator）` |
| `9911` 被占 | 起前检查，占用则拒 | `端口 9911 被 <pid> 占用` |
| `MODEL_PATH` 不存在/非法 GGUF | 起前 `stat` 校验；ds4 自身会报量化类型不支持 | `模型文件不存在: <path>` |
| `LD_LIBRARY_PATH` 缺失致 `libhipblas.so.3 not found` | 入口**始终注入**；启动后 3s 内探活，失败则回显 | `ds4 启动失败（见 /var/log/ds4/...）` |

---

## 8. 不变式（Invariants）

1. **唯一入口**：ds4 的任何管理动作**只能**经 `cluster.py`（无第二路径、无 `ops/` 新脚本）。
2. **零自加载**：进程为**手动进程**；不开机自启、不装 systemd unit。
3. **不改全局库路径**：只注入**进程级** `LD_LIBRARY_PATH`；不得写 `/etc/ld.so.conf.d/` 或系统 profile。
4. **不碰 `/opt`（llama.cpp 域）**；ds4 只写 `~/ds4` 与 `/etc/ds4-instances/`。
5. **PP 先后序不可反**：worker 先、coordinator 后；`unload` 反序。
6. **只读探活**：`status` 不得启动/停止任何进程。
7. **模型格式边界**：只接受 ds4 专属 GGUF；**不尝试**加载通用 GGUF（避免"看似加载成功实则错"）。

---

## 9. 幻觉排除审查（Step 4 Review）

### 9.1 设计基于已验证的调研结论

- [x] 所有设计决策可追溯到执行记录 §11–§14（E1 实测）或官方文档（E3）
- [x] 无未经验证的假设（**TP→PP 的改正是源码门禁实证**，非推断）
- [x] 无论证驱动的归因扭曲

### 9.2 替代方案审查

- [x] 列出 4 个替代方案（A/B/C/D）
- [x] 每个均有明确否决理由

### 9.3 职责边界审查

- [x] 职责边界清晰（§2.3，4 条显式排除）
- [x] 不越界吞并其它范式（不接管下载、不接管引擎内部、不动 EV-4）

---

## 10. 对实施的输入

### 10.1 关键工程约束

1. `BACKENDS` 加 `"ds4"` 是**纯增量**（`cluster_web.py:1383` 的后端下拉会自动多一项）。
2. PP 的 `--coordinator` 地址**必须取直连段**（B 10.10.11.1 / C 10.10.11.3），**不得**用管理网 —— 官方明确"地址须在直连成员接口上"。
3. `--layers` 的**层号取决于 GLM-5.3-Flash 的实际层数**（`glm5-next.block_count`）⇒ **实施第一步须先从 GGUF 元数据读出层数**，再定切分点（本设计不预设数字）。
4. 日志落 `/var/log/ds4/`（新目录，属站上运行时产物，**不入库**）。
5. 与门禁对接：`ports` 断言需把 **9911** 登记进 `inventory/ports.yaml`（`managed` 段，`mode: on_demand`）。

### 10.2 风险与缓解

| 风险 | 缓解措施 |
|---|---|
| PP 两站层切分写错 → 起不来或输出错乱 | 先用 `--help distributed` + `ds4 --role` 干跑校验；`--dist-replay-check` 诊断开关 |
| 9911 与既有服务冲突 | 起前查 `ss -ltn`；并登记 `ports.yaml` 由门禁持续看住 |
| 双机 PP 实测不达预期（社区显示 ds4 ROCm 反低于 llama.cpp） | 本设计**只做入口**；收益判定属 P-4 对照，**不预设结论** |
| ds4 beta 质量、模型可能被上游移除 | 版本锁定 + `.orig` 备份；升维时重打 1 行补丁（记于 ADR-0010 §失效条件）|

---

**Review 签字**: _________ 日期: _________
