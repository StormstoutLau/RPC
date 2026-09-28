# ADR-0010: DwarfStar (ds4) 第二引擎引入立项（B 站单站试点）

---------------------------------------------------------------------

id: ADR-0010
type: adr
version: 1.0
status: proposed
date: 2026-09-28
depends: [ADR-0004]
upstream: null
---------------------------------------------------------------------

> **Feature**: 在 llama.cpp 主路线之外，**立项引入 DwarfStar（ds4）作为第二推理引擎**，以 **B 站单站试点** 起步，目标 = 跑 **llama.cpp 当前跑不了的前沿架构**（首推 GLM-5.3-Flash `glm5next`）。
> **创建日期**: 2026-09-28
> **状态**: proposed（提议）/ accepted（接受）/ superseded（已被取代）/ deferred（推迟）
> **适用**: ds4 的引入范围、形态与能力边界；**不改变** llama.cpp 作为主路线的地位

---

## 元数据

| 字段 | 值 |
|------|-----|
| 编号 | ADR-0010 |
| 日期 | 2026-09-28 |
| 状态 | proposed |
| 决策者 | Scott (鹏) |
| 相关文档 | [DwarfStar 部署专项方案](../docs/research/2026-09-28_DwarfStar部署专项方案.md)（规划）· [DwarfStar 前置核验与 ROCm 工具链安装决策](../docs/research/2026-09-28_DwarfStar前置核验与ROCm工具链安装决策.md)（**执行与实测落档，本文证据主源**）· [FRAMEWORK-SURVEY §H.7](../spec/model-eval/FRAMEWORK-SURVEY-2026-09.md)（非 llama 引擎全景）· `O-112`/`O-113`（OPEN-ISSUES）· `EV-3`/`EV-4` |
| 取代 | 无 |

**证据等级约定**: E1=本会话实测；E2=前会话实测留档；E3=外部文档（官方/社区）；E4=推断。

---

## 范围声明（先于一切）

**本决策仅约束「ds4 是否/以何形态引入本集群」，不改变 llama.cpp 主路线的任何现有做法，也不改变 A/C 两站的现状。**

- 试点范围 = **仅 B 站**；A/C 站**不动**（E1：本轮全部系统改动都在 B 站）。
- 本 ADR **不裁**「第二栈的长期生命周期归属」（那属 `EV-4`）；本 ADR 只裁「**以 B 站单站试点的形态立项**」这一步。

---

## 背景（Context）

### 触发实例

1. **llama.cpp 对前沿架构合入滞后（E3）**：GLM-5.3-Flash 的 `glm5next` 架构在 llama.cpp **至今未合入 main**（PR #27754/#27752/#27773 三线竞争，`ms=blocked`）⇒ 现役引擎**跑不了**该模型。
2. **用户指令（2026-09-28）**：要求先给出部署方案，后按方案执行；本轮已完成 **B 站 P-0「引擎活着」**（E1）。
3. **ds4 是唯一落在本集群硬件上的别家栈（E1+E3）**：ds4 官方 ROCm 一等后端以 Strix Halo 为目标；本轮已实测在本集群 gfx1151 上**装起 ROCm 10.0 并构建成功**。

### 根因

「前沿开源模型发布 → 通用引擎（llama.cpp）架构合入」之间**存在数月量级的时滞**，而该时滞内**没有第二条本地路线**。ds4 是**窄引擎**（只认自家 GGUF），但它对少数模型家族的跟进速度远快于通用引擎 ⇒ **补的是"架构覆盖时滞"这个能力缺口**，不是吞吐。

---

## 决策（Decision）

**在有本集群实证支撑的前提下，选择「以 B 站单站试点形态引入 ds4」，而非「容器化引入」「系统级替换 ROCm」或「不引入继续等 llama.cpp」。**

### 1. 范围与形态：B 站单站试点 + 用户域隔离 + 零自加载

- **仅 B 站**；不装 supervisor / 开机自启 / systemd 单元（沿用「开机 = 零自加载」）。
- 落点：**`/opt/rocm/core-10.0`**（ROCm 10.0 core，与 `/opt/rocm-7.2.4` **包名+路径双隔离**）+ **`~/ds4`**（源码与二进制）+ `~/ds4/gguf`（项目专属 GGUF）。
- 运行需 `LD_LIBRARY_PATH=/opt/rocm/core-10.0/lib/rocm_sysdeps/lib:/opt/rocm/core-10.0/lib` —— **per-invocation，不写系统 profile**（E1）。

### 2. ★ 能力边界（本轮核验后对方案的修正，必须钉死）

| 能力 | 结论 | 证据（E1/E3） |
|---|---|---|
| 可用模型（gfx1151） | **V4-Flash** / **GLM-5.3-Flash**；V4.1 走 fork 专线（见 §替代方案 E） | 本轮源码门禁 + 官方文档 |
| ★ **GGUF 格式** | ⚠ **专用格式**（非通用加载器）：只认自家量化类型 `q8_0/q8_K/q4_K/q2_K/iq2_xxs`；**通用 GGUF（如 A 站冷存的 Unsloth `GLM-5.3-Flash-UD-IQ4_XS`）不可用**，且**不可从 GGUF 转换**（转换器输入是 **safetensors**）⇒ 必须用 `download_model.sh` 官方档 | E1：`ds4.c:2362-2367` tensor type 枚举 + `gguf-tools` 自述 5 类 + A 站文件实测（146.1 GiB / GGUF v3 / IQ4_XS）|
| **TP（`--tensor-parallel`）** | ❌ **antirez 主干拒绝**：`"tensor parallelism requires the Metal backend"`（`ds4.c:72484`，受 `#ifndef DS4_HAS_DEEPSEEK41_GPU` 约束） | E1（本地构建二进制 strings 实证）|
| **PP（`--layers` 层切片）** | ✅ **ROCm 上可用**：源码文案 `"distributed layer slices can run fully resident"`（`ds4.c:70887`） | E1 |
| GLM-5.3 单机 resident | ✅ 豁免 streaming 要求（`!ds4_model_is_glm53()`，`ds4.c:70879`）| E1 |
| GLM-5.2 单机 | ⚠ 需 `--ssd-streaming` | E1（错误文案）|

> ★ **对原方案的修正**：部署方案 §1.5/§3 曾写「GLM-5.3-Flash 双机 **RESIDENT TP**」—— **不成立**。ROCm 双机主线应为 **PP（`--layers` 层切片）**。

**档位实测（E1，hf-mirror `Content-Length`）**：`GLM-5.3-Flash-Q2.gguf` = **89.9 GiB** · `GLM-5.3-Flash-Q4_K.gguf` = **177.8 GiB**。
**链路（E1）**：B 站有两条 USB4 —— `thunderbolt0`=10.10.10.2（连 A）· `thunderbolt1`=10.10.11.1（连 C）⇒ 三站**菊花链**，B 为中间节点。

### 3. 来源与「允许的偏离」（诚实登记）

| 组件 | 来源 | 偏离 |
|---|---|---|
| ROCm 10.0 core | `stable.repo.amd.com/rocm/core/packages/ubuntu2404` | ⚠ **`trusted=yes`** —— 官方签名 key（`FA296B056C5BB456`）**未随 `packages.gpg` 发布**，无法验签 |
| ds4 源码 | `antirez/ds4` main | ⚠ **1 行本地补丁**：`rocm/ds4_rocm_deepseek4_vision.cuh:239` 的 host `rsqrtf` → `1.0f/sqrtf`（**上游固有缺陷**：antirez main 与 `kyuz0/ds4` fork 都有，ROCm 7.2.4/10.0 都报）|

⇒ **升级 ds4 或 ROCm 时须重打该补丁 / 复核 trusted 决策**（写入 §失效条件）。

### 4. 管理面（承 ADR-0004）

- ds4 的**起停/探活必须并入 `ops/cluster.py`**（不新增并列入口、不在 `ops/` 落一次性脚本）；探针/一次性验证件**放 `tmp/`**。
- 本 ADR **仅批准试点**；`cluster.py` 的具体子命令扩展仍未实施（属后续 P-2/P-3）。

### 5. 明确不做（边界）

- **不全量迁移**：llama.cpp 仍是主路线（即便试点通过）。
- **不自动升级**：不并入 llama.cpp 的 UPGRADE_SOP 链。
- **不并行运行时叠加**：试点期间不同时跑 ds4 与现役大模型（同机内存竞争 + `O-18` 带宽铁律）。
- **不碰 `/opt`（llama.cpp 域）**、**不动 A/C 站**。

### 机制原理（为何有效）

ds4 的窄化（只认自家 GGUF + 专用内核）使其对少数模型家族的跟进**不受通用引擎的架构合入排队约束** ⇒ 直接补「架构覆盖时滞」。本轮 **1 行补丁即解开构建**（E1）也佐证：其工程面窄、定位清晰，落点成本低。

### 与既有 ADR/规则的关系

- **ADR-0004**：ds4 属"第二管理面"风险 ⇒ 本 ADR 以「起停并入唯一入口」为前提批准试点（不新增入口）。
- **`EV-4`（第二栈生命周期）**：**本 ADR 不替代** —— 长期"谁管生命周期"仍需 EV-4 裁。
- **`EV-3`（vLLM 换栈）**：**并行不同路** —— EV-3 走 vLLM，本 ADR 走 ds4；**两者都撞 ADR-0004**，须**逐个**（而非一并）立项。

---

## 考虑的替代方案（Alternatives Considered）

### 替代方案 A: 容器 / toolbox 引入（否决）

- 优点: 官方推荐路径；ROCm 10.0 与 gfx1151 补丁开箱；隔离性最好。
- 缺点: **B 站实测三重阻塞** —— ① docker 仅 Desktop CLI 且 daemon 未运行，`podman`/`distrobox`/`toolbox`/`apptainer` 均未装；② `docker.io` 直连超时，国内 mirror 需登录；③ docker 常驻 daemon **撞「零自加载」纪律**。
- 否决理由: 三条都是**当前环境下的硬阻塞**，且治理面须先过 ADR-0004/EV-4；而原生路径已用**零系统风险**（§验证）达成同等目标。

### 替代方案 B: 系统装 ROCm 10.0 覆盖/替换 7.2.4（否决）

- 优点: 一步到位，工具链版本统一。
- 缺点: **动集群 2026-09-17 刚统一的 7.2.4 基线**；且 AMD 安装器常写 `ld.so.conf.d` / `LD_LIBRARY_PATH` ⇒ 按 **§9 风险通道**，一旦写入且指向含 `so.7` 的路径，**会遮蔽 bundled 库 ⇒ 破坏现役 llama**（`LD_LIBRARY_PATH` 优先于 `RUNPATH`）。
- 否决理由: 现役 llama 对系统 ROCm **零依赖**（E1 三站实测）本可"不碰最好"；**双隔离共存**（`/opt/rocm/core-10.0` vs `-7.2.4`）以更低风险达到同样目的。

### 替代方案 C: 自维护 fork + 大量补丁（否决）

- 优点: 可强行让 antirez main 在 gfx1151 上跑起来。
- 缺点: 上游本身还需 gfx1151 补丁（`kyuz0/ds4` fork 存在本身就是证据）；仓库 `rsqrtf` 类 host/device 问题**全仓 78 处**，逐个打补丁 = 自维护一条长期分叉。
- 否决理由: 维护面远超收益；**本轮 1 行补丁已够**（构建全通），无需 fork。

### 替代方案 D: 不引入，继续等 llama.cpp 合入 `glm5next`（否决）

- 优点: 零新增栈、零治理成本。
- 缺点: 三 PR（#27754/#27752/#27773）竞争 + `ms=blocked`，**已等数月仍未合**；期间该模型在本集群**完全不可用**。
- 否决理由: 把"能力可得性"押在不可控的上游排队上，与 `O-113` 的结论矛盾。

### 替代方案 E: 直接用 `kyuz0/ds4` fork（`main-gfx1151`）（推迟）

- 优点: 官方容器所用分支；其 `docs/CLUSTERING_ROCM.md` 给出 **ROCm 双机实测 ~16.6 t/s(TCP) / 17.3 t/s(RoCE)**。
- 缺点: 该文档的 ROCm 双机方案是 **`--tensor-parallel` 且明确「splitting by `--layers` are not supported」**，**面向 V4.1 Flash Q2**，与本期 **GLM-5.3-Flash** 目标**不同**；且 fork 额外打 PR #2/#1012。
- 推迟理由: 与本期目标不重叠 ⇒ 留作 **V4.1 专线**候选，不在本 ADR 范围内启用。

---

## 后果（Consequences）

### 正面

- 首次在本集群获得「**跑 llama.cpp 跑不了的前沿架构**」能力（GLM-5.3-Flash）。
- ROCm 10.0 与 7.2.4 **双隔离共存**，现役 llama **零受损**（E1）。
- 构建链路已实证**极低修复成本**（1 行补丁）。

### 负面

- **两条偏离**（`trusted=yes`、1 行源码补丁）须长期维护。
- ds4 自述 **beta 质量、快速变化**（模型可能被移除）⇒ 不适合承载生产。
- B 站额外 ~793 MiB（ROCm 10.0）+ 后续 GGUF（GLM Q2 89.9 / Q4 177.8 GiB）磁盘占用。

### 中性 / 需要后续行动

- **模型下载**：HF 直连不可用，须走 `HF_ENDPOINT=https://hf-mirror.com` + `HF_HUB_DISABLE_XET=1`（链路已冒烟，实测 ~10.8 MB/s ⇒ 86.7GB ≈ 2.2h）。
- 「第二栈生命周期归属」移交 **EV-4**。

---

## 验证（Validation）

### 已有实证

| 依据 | 来源 | 状态 |
|---|---|---|
| 前置核验（ROCm/KFD/磁盘/端口/内核参数）三站通过 | 本轮 E1 | ✅ |
| ROCm 10.0 core 装成、与 7.2.4 双隔离、**未写 ld.so.conf / LD_LIBRARY_PATH** | 本轮 E1（§11.3） | ✅ |
| 现役 llama `ldd not-found=0`（装 ROCm 10.0 前后一致） | 本轮 E1 | ✅ |
| ds4 构建全通（5 个二进制），`--help`/`--rocm` 可用 | 本轮 E1（§11.4/11.5） | ✅ 单实例 |
| **TP 被 ROCm 拒绝 / PP 被 ROCm 支持** | 本轮 E1（源码门禁 + 二进制 strings） | ✅ |
| GLM 档位尺寸（Q2 89.9 / Q4 177.8 GiB） | 本轮 E1（hf-mirror HEAD） | ✅ |
| HF 镜像下载链路（`hf download` rc=0） | 本轮 E1（小仓库冒烟） | ✅ 单实例 |

### 待验证项

- **真模型加载与推理**（完整 P-0）：尚**未**下载任何 ds4 GGUF，未做真实 token 生成。
- **双机 PP 实跑**（`--layers` 在 BD 两站、USB4 链路）：**未做**。
- **与 llama.cpp 的同题对照**（gold 夹具 / V4-Flash 背靠背）：**未做**。
- **GLM-5.3-Flash 在本集群的实际质量与吞吐**：**未测**。★ 且**官方数据不覆盖**——`ds4` benchmarks/perf 只给 **V4-Flash 的 Metal(M5 Max)/CUDA(DGX Spark) 两行，无 ROCm、无 GLM**；社区在 gfx1151 上给 V4-Flash 的 ds4 ROCm ≈ **12.5 t/s / prefill 122**（**低于** llama.cpp Vulkan 的 18.33 / 254）⇒ **本集群的 ds4 收益必须自测，不可引用官方数字**。

### 失效条件（何时重审本 ADR）

- **llama.cpp 合入 `glm5next`** ⇒ 「架构覆盖」这一核心动因消失，须重审是否仍需要 ds4。
- **ds4 上游修复 `rsqrtf` 缺陷** ⇒ 可去掉 1 行补丁（减少偏离）。
- **AMD 发布可验签的 ROCm 10 源 key** ⇒ 可去掉 `trusted=yes`。
- **上游移除 GLM-5.3-Flash 支持**（ds4 自述"模型可能被移除"）⇒ 本期目标失效。
- **现役 llama 出现任何因系统 ROCm 变更导致的加载/性能异常** ⇒ 立即回退（回退锚点：删 `rocm-core10.list` + `apt purge amdrocm-*`）。

---

## 修订历史

| 日期 | 变更 |
|------|------|
| 2026-09-28 | 初始版本（B 站 P-0 已达成；能力边界经源码核验修正：① 双机主线 = **PP 非 TP**；② **GGUF 为专用格式**，通用 GGUF/Unsloth 档不可用亦不可转） |
