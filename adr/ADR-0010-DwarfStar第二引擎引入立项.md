# ADR-0010: DwarfStar (ds4) 第二引擎引入立项（B 站单站试点）

---------------------------------------------------------------------

id: ADR-0010
type: adr
version: 1.2
status: accepted
date: 2026-09-28
depends: [ADR-0004]
upstream: null
---------------------------------------------------------------------

> **Feature**: 在 llama.cpp 主路线之外，**立项引入 DwarfStar（ds4）作为第二推理引擎**，以 **B 站单站试点** 起步，目标 = 跑 **llama.cpp 当前跑不了的前沿架构**（首推 GLM-5.3-Flash `glm5next`）。
> **创建日期**: 2026-09-28
> **状态**: accepted（2026-09-28 裁决；**v1.2 降为「观察保留」** —— 原 v1.1 的"单机交付形态"仅作为**冷藏能力**保留，不再投入）
> **适用**: ds4 的引入范围、形态与能力边界；**不改变** llama.cpp 作为主路线的地位
> ★ **v1.2 裁决（2026-09-28 深夜）**: 决策等级由「**试点立项**」降为「**观察保留**」。
> **依据（E1，执行记录 §20.3）**：
> ① v1.0/v1.1 的**核心动因「跑 llama.cpp 跑不了的前沿架构」已被吞并** —— llama.cpp **主线已含 `deepseek4`**；且经「**并存变体（glm5next 分支）+ 双机 RPC**」已能跑 GLM-5.3-Flash **11.2–11.9 t/s**（§19），而 ds4 单机 `--ssd-streaming` 仅 **0.41–0.44 t/s**（**慢 27×**）。
> ② ds4 的分布式能力**双重不可用**：PP 两端夹死（§16.9）· TP 源码门禁（§18.1）。
> ③ ds4 量化白名单**仅 5 类**（`IQ2_XXS/Q2_K/Q4_K/Q8_0/Q8_K`，源码级）⇒ **连 `Q3_K_M` 都读不了**，覆盖面窄于直觉。
> **处置**：**不删除、不投入** —— 引擎（0.4 GB 代码 + `/opt` 并存目录）与 **ds4 专属 Q4_K 档（190 GB）**均**保留冷藏**；**不再排 P-x 计划、不再做自维护补丁**。
> **复活条件**：① 出现 llama.cpp **确实不支持而 ds4 支持**的目标架构（届时按需取用，模型可重下）；② 需要「**第二实现交叉验证**」（用 ds4 验 llama.cpp 数值）；③ llama.cpp 主线回归需备援。
> **退役条件**：磁盘告急，或出现第二个同类候选引擎。
> ★ **v1.1 裁决（2026-09-28）**: 立项**通过**（原为「提议」），但**决策范围收窄** —— **可交付形态 = 单机（resident / `--ssd-streaming`）**；原「双机 PP 为 ROCm 主线」**被本轮实测推翻**，改为 **冻结（upstream-tracked）**。裁决依据与边界见下方「裁决（v1.1）」。原 v1.0 正文**保留不改**，仅对与实测冲突处就地标注。

---

## 元数据

| 字段 | 值 |
|------|-----|
| 编号 | ADR-0010 |
| 日期 | 2026-09-28 |
| 状态 | **accepted（v1.2 · 2026-09-28 裁决：由「试点立项」降为「观察保留」）** |
| 决策者 | Scott (鹏) |
| 相关文档 | [DwarfStar 部署专项方案](../docs/research/2026-09-28_DwarfStar部署专项方案.md)（规划）· [DwarfStar 前置核验与 ROCm 工具链安装决策](../docs/research/2026-09-28_DwarfStar前置核验与ROCm工具链安装决策.md)（**执行与实测落档，本文证据主源；§16 为本裁决的直接依据**）· [ds4-backend P-2 设计](../spec/ds4-backend/DESIGN.md)（管理面）· [FRAMEWORK-SURVEY §H.7](../spec/model-eval/FRAMEWORK-SURVEY-2026-09.md)（非 llama 引擎全景）· 上游 [antirez/ds4#1141](https://github.com/antirez/ds4/issues/1141)（双机 PP 崩溃已报）· `O-112`/`O-113`（OPEN-ISSUES）· `EV-3`/`EV-4` |
| 取代 | 无 |

**证据等级约定**: E1=本会话实测；E2=前会话实测留档；E3=外部文档（官方/社区）；E4=推断。

---

## 范围声明（先于一切）

**本决策仅约束「ds4 是否/以何形态引入本集群」，不改变 llama.cpp 主路线的任何现有做法，也不改变 A/C 两站的现状。**

- 试点范围 = **仅 B 站**；A/C 站**不动**（E1：本轮全部系统改动都在 B 站）。
- 本 ADR **不裁**「第二栈的长期生命周期归属」（那属 `EV-4`）；本 ADR 只裁「**以 B 站单站试点的形态立项**」这一步。

---

## 裁决（v1.1 · 2026-09-28）

### 裁决结论

**接受立项（proposed → accepted），同时把可交付形态从「双机 PP 主线」收窄为「单机」；双机 PP 冻结并转上游跟踪。**

| 决策点 | v1.0 原定 | v1.1 裁决 | 依据 |
|---|---|---|---|
| 是否引入 ds4 | 立项试点 | ✅ **成立**（升为 accepted）| E1：P-0/P-2 全通，且 **GLM-5.3-Flash 真实生成成功** |
| 主交付形态 | 双机 PP（`--layers`）| ❌ → **单机**（resident / `--ssd-streaming`）| E1：PP 前向稳定 SIGSEGV |
| 双机 PP | ROCm 主线 | **冻结**（upstream-tracked，`#1141`）| E1 + E3 |
| 双机 TP | 已否决（源码门禁）| **维持否决** | E1 |

### 依据（E1，可复算）

1. **单机路径已实证可用**：`GLM-5.3-Flash-Q4_K.gguf` + `--rocm --ssd-streaming --ctx 4096` 在本集群**真实生成**（输出 `Hello there!`）⇒ 「跑 llama.cpp 跑不了的架构」这一**核心动因已兑现**（v1.0 的「待验证：真模型加载与推理」至此闭环）。
2. **双机 PP 在 ROCm 上不可用**：编排三阶段全通、`distributed route ready` 正常建立，但 coordinator 处理 prompt 即 **SIGSEGV（exit 139 + core）**。崩溃点固定在 ROCm 10.0 `libhsa-runtime64` 的 `hsa_amd_memory_unlock → MemoryRegion::Unlock → MakeMemoryUnresident → hsaKmtUnmapMemoryToGPU → vm_find_object`；已在 `antirez/ds4#1141` 报告（含可复算实验）。
3. **该组合上游未承诺支持**（E3）：`STRIX_HALO.md` 明示 GLM 在 ROCm 上走**单机 SSD streaming**（原话 "Flash's ROCm resident and pipeline paths should not be confused with the GLM SSD-streaming path"）；`MODELS.md` 中 `glm53-q2` 标 "ROCm also supported"，而双机 GLM 走 **ownership-aware TP（Metal）**（ROCm TP 被源码门禁拒绝）⇒ 「GLM53 + ROCm 双机」属**未支持组合**。
4. **口径纪律**：崩溃虽以「单次 D2H > 1 MiB」为**进程内观测边界**，但**裸 HIP 对照已否证**其为 HIP/ROCm 尺寸上限（§16.8）⇒ 记为**未定位的进程态缺陷**，**不作机制定论**（避免把一个进程内现象写成库级规律）。

### 本次收窄明确不做

- **不做**：双机 PP（冻结）· 双机 TP（源码门禁）· 把 ds4 当吞吐路径（实测 V4-Flash 单机 ds4 **12.5 t/s** < llama Vulkan **18.33**；双机 16.8 ≈ llama RPC 17）。

### 待测（不阻断立项，属运行面调优）

- ★ **「双机 PP 能否自行闭环」= 已判定：不能靠配置**（§16.9）。ROCm 侧那处**可从 ds4 侧绕过**（压小回读即不崩），但绕过之后暴露 **ds4 自身在分块 span 路径的堆损坏** ⇒ 硬阻塞在 **ds4 上游代码**。要闭环必须**改 ds4 源码**（即自维护补丁），与**替代方案 C 的否决理由**正面冲突 ⇒ **维持冻结，不投入**；ASan 定位已按**时间盒一轮**执行、未取得报告（卡在 `ld.lld` 拒绝 ASan 目标文件），下一轮首步已写明（`-fuse-ld=bfd` + 链 `libasan`）。
- **单机 Q2**（官方 Strix Halo 参考档，**已下载完成** 96,505,816,384 B）吞吐是否到可交互。
- **`--mtp`**（GLM 内置 draft block 投机解码）增益。
- ★ **质量自测**：用上游 `gguf-tools/quality-testing/score_official` + `data/glm53-flash-openrouter-zai-fp8-100` 夹具，对 Q2 / Q4（子集）自测，对标上游参考带（Q2 `0.458030/89/7.37`；Q4 `0.299918/90/9.66`）。

### 角色定位（写死，防止被当吞吐栈用）

ds4 在本集群的角色 = **架构覆盖面 + 容量**（跑 llama 跑不了的架构；`--ssd-streaming` 的超内存容量），**不是吞吐引擎**。

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
| **PP（`--layers` 层切片）** | ❌ **ROCm 上不可用（v1.1 实测推翻 v1.0 的"源码文案推断"）⇒ 冻结**。详见 §16.9 扫描：**两端夹死** —— 回读 ≥768 KiB ⇒ ROCm HSA SIGSEGV；≤640 KiB ⇒ **ds4 自身堆损坏**（两条路径都复现）⇒ **不存在可用 flag 组合** | E1（§16.3/§16.8/§16.9）+ E3 |
| GLM-5.3 单机 resident | ✅ 豁免 streaming 要求（`!ds4_model_is_glm53()`，`ds4.c:70879`）| E1 |
| ★ GLM-5.3 单机 `--ssd-streaming` | ✅ **已实测跑通**（Q4_K 178 GiB → 真实生成；0.41/0.44 t/s 冷缓存）| E1（§16.5）|
| GLM-5.2 单机 | ⚠ 需 `--ssd-streaming` | E1（错误文案）|

> ★ **对原方案的修正（v1.0）**：部署方案 §1.5/§3 曾写「GLM-5.3-Flash 双机 **RESIDENT TP**」—— **不成立**。ROCm 双机主线**名义上**应为 **PP（`--layers` 层切片）**。
> ★★ **v1.1 二次修正（实测推翻）**：该「PP 主线」**同样不可用**（见上表 PP 行）。且上游文档明示 ROCm 的 resident/pipeline 路径**面向 Flash 系**，GLM 走**单机 SSD streaming** ⇒ **ROCm 上的双机形态整体冻结**（PP 与 TP 皆否）。

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
| ★ **P-2 管理面并入 `cluster.py`**（ds4 后端 · 端口 9911 · 互斥 · 就绪语义）| E1（commit `2054370`）| ✅ |
| ★ **GLM-5.3-Flash Q4 单机真实生成**（`--rocm --ssd-streaming --ctx 4096`）| E1（§16.5）| ✅ |
| ★ **双机 PP 首跑**：编排三阶段全通 + `route ready`，但前向 **SIGSEGV** | E1（§16.3/§16.8）| ❌ **冻结** |
| ★ **上游已报**：`antirez/ds4#1141`（英文详尽，含裸 HIP 对照与自我否证）| E1 | ✅ |
| Q2 档尺寸（`Content-Length` **96,505,816,384 B**）| E1（hf-mirror HEAD）| ✅ |

### 待验证项

- ★ **单机 Q2 的吞吐与可交互性**：下载中（`lm-download@ds4-glm53-q2`）；Q2 是上游 **ROCm 参考档**（"ROCm also supported"），预期缓存命中率显著高于 Q4。
- **`--mtp`（GLM 内置 draft block 投机解码）增益**：**未测**。
- ★ **质量自测（不靠外推）**：上游 `gguf-tools/quality-testing/score_official` + `data/glm53-flash-openrouter-zai-fp8-100` 夹具已在站上，可对 Q2 / Q4（子集）自测，对标上游参考带（Q2 `0.458030 / 89 / 7.37`；Q4 `0.299918 / 90 / 9.66`，指标 = average NLL / first-token match / average greedy prefix）。**未跑**。
- **与 llama.cpp 的同题对照**（gold 夹具 / V4-Flash 背靠背）：**未做**。
- **双机 PP 根因**：崩溃已定位到 ROCm host-unlock 路径，但**ds4 进程态差异未定位**（裸 HIP 对照见 §16.8）；解冻前须先解根因或等上游修。
- **V4-Pro / V4.1 的 PP**：同属 ROCm PP 路径 ⇒ **一并冻结**。
- **GLM-5.3-Flash 的实际质量与吞吐**：★ **官方数据不覆盖** —— `ds4` benchmarks/perf 只给 **V4-Flash 的 Metal(M5 Max)/CUDA(DGX Spark) 两行，无 ROCm、无 GLM**；社区在 gfx1151 上给 V4-Flash 的 ds4 ROCm ≈ **12.5 t/s / prefill 122**（**低于** llama.cpp Vulkan 的 18.33 / 254）⇒ **本集群的 ds4 收益必须自测，不可引用官方数字**。

### 失效条件（何时重审本 ADR）

- **llama.cpp 合入 `glm5next`** ⇒ 「架构覆盖」这一核心动因消失，须重审是否仍需要 ds4。
- **ds4 上游修复 `rsqrtf` 缺陷** ⇒ 可去掉 1 行补丁（减少偏离）。
- **AMD 发布可验签的 ROCm 10 源 key** ⇒ 可去掉 `trusted=yes`。
- **上游移除 GLM-5.3-Flash 支持**（ds4 自述"模型可能被移除"）⇒ 本期目标失效。
- **现役 llama 出现任何因系统 ROCm 变更导致的加载/性能异常** ⇒ 立即回退（回退锚点：删 `rocm-core10.list` + `apt purge amdrocm-*`）。
- ★ **双机 PP 解冻条件（v1.1 新增）**：上游为 PP 的激活回读做分块/换路径，**或** ROCm 修复 host-unlock 路径，且我们复现通过 ⇒ 重审「双机形态」是否恢复为主线。
- ★ **本期目标成立性复核（v1.1 新增）**：若 **Q2 自测质量不可接受**（显著偏离上游参考带）**且** **Q4 单机吞吐不可交互** ⇒ 「一个可用的 GLM-5.3-Flash」不成立 ⇒ 须重审是否维持 ds4（可能退回「继续等 llama.cpp 合入」）。

---

## 修订历史

| 日期 | 变更 |
|------|------|
| 2026-09-28 | 初始版本 v1.0（B 站 P-0 已达成；能力边界经源码核验修正：① 双机主线 = **PP 非 TP**；② **GGUF 为专用格式**，通用 GGUF/Unsloth 档不可用亦不可转）|
| 2026-09-28 | **v1.1 裁决：proposed → accepted（范围收窄）**。① 核心动因兑现：**GLM-5.3-Flash Q4 单机 `--ssd-streaming` 真实生成成功**（E1）；② ★ **双机 PP 被实测推翻**（前向稳定 SIGSEGV，崩溃点在 ROCm `libhsa-runtime64` host-unlock 路径）⇒ **双机形态整体冻结**（PP+TP 皆否），新增解冻条件；③ 已上游报警 `antirez/ds4#1141`；④ 新增「角色定位 = 架构覆盖面 + 容量，非吞吐引擎」；⑤ 待测项改为运行面：单机 Q2 · `--mtp` · 上游夹具质量自测 |
