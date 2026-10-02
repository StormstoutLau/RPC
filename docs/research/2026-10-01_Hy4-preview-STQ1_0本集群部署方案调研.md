# Hy4-preview（STQ1_0 档）在本集群的部署方案调研

***

id: research-hy4-preview-stq1-0-deploy-2026-10-01
type: research
version: 1.0
status: done（**P0 判定已出**；**无任何代码/配置/站上改动**）
date: 2026-10-01
depends: \[ADR-0003 OpenRouter egress, ADR-0004 统一管理入口, ADR-0010 DwarfStar第二引擎, O-112 单机容量上界, O-138 加速路线扫描, O-142 本条承载, upstream-tracker §1.9]
upstream: \[inventory/models.yaml, inventory/ports.yaml, ops/cluster_const.py, docs/research/2026-09-28_GLM系列本地推理部署.md, docs/research/2026-09-28_O-110同站并发实测与O-112单机容量核验.md]
------------------------------------------------------------------

> **触发**：用户 2026-10-01 令「调研 **hy4 STDQ1** 在本集群部署方案」。
> **正名**：`hy4 STDQ1` = 腾讯混元 **Hy4-preview** 的 **STQ1_0** 量化档（`Hy4-preview-STQ1_0.gguf`）。
> **射程**：本调研**只做 P0 判定与取证**，**不动任何代码/配置/站上状态**；任何引入新引擎分支/新栈的动作都须**另立 ADR**。
> **证据等级**：E1=本会话实测 · E2=前会话实测留档 · **E3=外部文档（官方/社区）** · E4=推断。本文件除引用本仓 E1/E2 外，主体为 **E3 外网**（**未在本仓复现**）。

---

## 0. 结论前置（三句）

1. ★★★ **P0 判定 = 本集群【Vulkan 现役路径】跑不了 STQ1_0 档，本地自建【不建议投入】。**
   决定性事实：STQ1_0 的上游支持（PR #22836）**只有 CPU 后端**（dequant + CPU vec_dot + ARM NEON），
   **无 CUDA/Vulkan/Metal/SYCL 内核**；而本集群的 **RPC / 分布式路径 = Vulkan**（`/opt/llama.cpp`，三站 `ldd` 含 `libggml-vulkan.so.0`，见 `TRACKER §2.6`）
   ⇒ ★ **STQ1_0 张量无法 offload 到 Vulkan GPU**（只能留 CPU）⇒ 对 770B（49B active）**吞吐不可用**。
2. ★ **唯一理论 GPU 险路 = HIP/ROCm**（本集群**单站默认**即 HIP），**但未确证**：HF 分发的 `0002-stq1_0-quant-and-cuda.patch` 名为 "quant-and-cuda"，
   llama.cpp 的 **HIP 后端与 CUDA 共用 `ggml-cuda/` 源码** ⇒ 理论上可继承；**但 HF 侧补丁未能抓取核验，且无任何 AMD/HIP 跑 Hy4 的公开案例**。
   ⇒ 这条路要「在**未合并的格式补丁**上叠 **AMD 移植 + RPC 跨机**两重风险」，**不划算**。
3. ★ **落档建议 = 走托管兜底**（见 §4）：腾讯在 **OpenRouter** 与自家 TokenHub/WorkBuddy/CodeBuddy 均上架了 hy4-preview；
   本仓 **`ADR-0003` egress 通道已就绪**。★ 覆盖场景：**长上下文/agentic 编码批处理**，用托管比在本集群硬啃更省。

**⇒ 一句话**：**这条不是"装个模型"，是"给一个未合并的低比特格式补 AMD/Vulkan 移植"** —— 投入产出比不成立，
**建议转托管（`ADR-0003`）；若仍要本地，须先过 §5 的三条未确证项**。

---

## 1. 目标资产与外部依赖（E3 外网）

### 1.1 模型本体（Tencent Hy）

| 项 | 值 |
|---|---|
| 名称 | **Hy4-preview**（Tencent Hy / 混元，2026-08-28 发布，Apache-2.0） |
| 规模 | **770B 总参 / 49B active** MoE（78 层，256 routed experts，top-8 + 1 shared） |
| 上下文 | **1M** token |
| 架构 | Gated **DeepSeek Sparse Attention** + **IndexCache**（跨层稀疏索引复用）+ **iHC**（identity Hyper-Connections） |
| 附层 | 1 个原生 **MTP** 层（10B 总 / 0.7B active），用于投机解码 |
| 已知缺点（官方） | **复杂任务推理时间过长** · **倾向过度自我验证** |

来源：<https://github.com/Tencent-Hunyuan/Hy4-preview> · <https://huggingface.co/tencent/Hy4-preview>

### 1.2 GGUF 资产（org = **`AngelSlim`**，非腾讯官方）

| 文件 | 体积 | bpw |
|---|---|---|
| **`Hy4-preview-STQ1_0.gguf`**（本调研目标） | **213.66 GiB** | **2.38** |
| `Hy4-preview-UD-IQ1_M.gguf` | 219.83 GiB | 2.44 |
| `Hy4-preview-Q4_K_M.gguf` | 435.20 GiB | 4.86 |
| （BF16 原始） | ≈1.5 TB | — |

来源：<https://huggingface.co/AngelSlim/Hy4-preview-GGUF>

### 1.3 STQ1_0 是什么（格式细节）

- **3:4 稀疏三值**：每 4 个 lane 保留 3 个三值（`{-d,0,+d}`）、**强制 1 个置零**；每 4 权重 = 4-bit code + 1-bit table-select（查 32 项 codebook）；**每 256 权重一个 fp16 scale** ⇒ **(2+32+8)/256 = 1.3125 bpw**。
- ★ **强制需要 imatrix**（重要性矩阵）；编码器 = 加权最小二乘 scale + imatrix-aware zero placement。
- **混合分配**：`ffn_gate_exps`/`ffn_up_exps` = **STQ1_0（29 层）/ IQ2_XXS（48 层）**；`ffn_down_exps` = IQ3_XXS（末 3 层 IQ4_XS）；attn out/gate/q_a = Q5_K；MLA q_b/k_b/v_b/kv_a_mqa = Q8_0；indexer = Q8_0/F32；iHC/router/norms/output = F32。

### 1.4 必需的 llama.cpp 补丁（★ 本任务核心）

| 补丁 | 覆盖 | 说明 |
|---|---|---|
| `0001-hyv4-architecture.patch` | **两个 GGUF 都要** | 架构 `hyv4`（18 files,+1632/−3） |
| `0002-stq1_0-quant-and-cuda.patch` | **仅 STQ1_0** | 格式 + **CUDA kernel**（25 files,+683/−4） |

- 分发位置：HF 仓库 `hy4-preview-patch/`，基线 **commit `0cea36222`**。
- 模型卡原文：**"Neither file runs on stock llama.cpp"**，`hyv4` 不在上游。

★ **PR 状态的单一真值在 [`spec/upstream-tracker/TRACKER.md` §1.9](../../spec/upstream-tracker/TRACKER.md)**（本表不重复维护）：
摘要 —— **架构 PR #28127（`hy_v4`）已合并（2026-09-04 → v0.4.1）**；**STQ1_0 格式 PR #22836 仍 open**。

---

## 2. P0 判定（本调研的实质产出）

### 2.1 ★★★ 判定①：STQ1_0 的后端支持面 —— **只有 CPU**

**结论（E3，官方 PR 文件表）**：PR **#22836** 的改动**只有 CPU 路径**，**无 CUDA / Vulkan / Metal / SYCL**：

- `ggml/include/ggml.h`（新增 `GGML_TYPE_STQ1_0 = 43`）、`ggml/src/ggml-common.h`（`block_stq1_0` + codebook）
- `ggml/src/ggml-quants.c/.h`（**dequant 参考实现**）
- `ggml/src/ggml-cpu/quants.c/.h`（`ggml_vec_dot_stq1_0_q8_K` **generic C**）+ `arch-fallback.h` + `arch/arm/quants.c`（**ARM NEON**）
- 工具链：`ggml-py` / `llama-model-loader.cpp` / `llama-quant.cpp` / `quantize.cpp` / `tests/`

⇒ 逐文件核对：**无 `ggml-cuda/`、无 `ggml-vulkan/`、无 `ggml-metal/`、无 `ggml-sycl/` 任何条目**。
⇒ **有 CPU dequant + vec_dot** ⇒ 纯 CPU **能加载运行**；但**不能 GPU offload**。

**对本集群的后果**：
- 本仓 **RPC / 分布式路径 = Vulkan**（TRACKER §2.6：三站 `/opt/llama.cpp` 的 `ldd` 含 `libggml-vulkan.so.0`；`nodes.env` 仅 B 站） ⇒ **Vulkan GPU 无 STQ1_0 内核 ⇒ 相关张量回退 CPU**。
- 213.66 GiB **> 单站 119.4 GiB**（`O-112`）⇒ **必须跨站** ⇒ 必走 **RPC** ⇒ **撞上 Vulkan 这一条**。
- ⚠ **修正一个易错读**：Vulkan 侧确实存在一个叫 **TQ1_0** 的三值格式支持（PR #27765），**但 TQ1_0 ≠ STQ1_0，不能混用**。

**关于 HIP（唯一险路，E4 推断）**：
- llama.cpp 的 **HIP 后端与 CUDA 共用 `ggml-cuda/` 源码**（HIP 是 CUDA 源的 `__HIP_PLATFORM_AMD__` 编译路径）。
- HF 的 `0002-…-and-cuda.patch` 名为 "quant-and-cuda" ⇒ **推断**其 STQ1_0 内核落在 `ggml-cuda/` ⇒ **HIP 理论上可继承**。
- ⚠ **但两处未确证**：① HF 补丁**抓取失败**，文件表未核；② **无任何在 AMD/HIP 或 Vulkan 上跑 `hyv4`/STQ1_0 的公开案例**。
- ⇒ 即便如此，本集群的**分布式路径是 Vulkan，不是 HIP** ⇒ 走 HIP 还得**自建 HIP 版 RPC 引擎分支**（head+worker 成对同版）。

### 2.2 ★★ 判定②：架构补丁口径 —— **不能偷懒用主线**

**结论（E4 高置信推断）**：PR **#28127** 用 arch 名 **`hy_v4`** + 新路径 `src/models/hy-v4.cpp`（16 files）；
而 AngelSlim 的 `0001-hyv4-architecture.patch` 用 **`hyv4`**（18 files） ⇒ **非同一实现**。

- 模型卡原文 "**the `hyv4` architecture is not upstream**" ⇒ 该 GGUF 的 arch 串**很可能写作 `hyv4`**，而主线注册的是 `hy_v4` ⇒ **主线（v0.4.1）+ #22836 很可能加载不了该 GGUF**。
- ⇒ **必须整套用补丁基线 `0cea36222` + 两个补丁**，自建分支。
- ⚠ **未做二进制验证**（`hyv4`↔`hy_v4` 是否二进制兼容未确证）。

### 2.3 判定③：磁盘与下载闸 —— **磁盘不是瓶颈，下载是既有闸**

- 磁盘余量（E2，据 `ADR-0010:32` 与手册）：**A 894 G / B 792 G / C 1.1 T free** ⇒ **213.66 GiB 任一站放得下**，**不构成阻塞**。
  ⚠ A 站历史登记有 605/773/894 三个值（回收 rpccache 前后），**若要真做须以实时实测为准**。
- ★ **下载闸（既有，非新问题）**：`ADR-0010:33` 记载 —— `hf-mirror` **不提供 Xet 端点** ⇒ `huggingface_hub` 回落常规 HTTP ⇒ **撞 HF 的 >50 GB 常规下载上限** ⇒ **须走 `lm-download@` 的分段并行 Range 路径**（213.66 GiB 远超 50 GB）。

### 2.4 判定④：治理闸（逐条）

| 闸 | 约束 |
|---|---|
| `ADR-0001` | **零自加载**：推理服务不自启、仅显式加载（本次符合） |
| `ADR-0004` | D1 唯一管理面 = `cluster.py`；D3① 新能力**加子命令**、禁并列脚本 |
| `ADR-0010` | B 站试点、"**不装常驻单元**"；**>50 GB 下载闸**（见 §2.3） |
| `ADR-0011:40` | **A4 / vLLM TP2 暂缓仍有效** ⇒ **不走 vLLM**（且官方 recipe 只覆盖 FP8，见 §4.2） |
| `ADR-0012` | D5 **不为推理栈背书 / 不新增镜像** |
| `O-112` | 单机权重上界 **119.4 GiB** ⇒ 213.66 GiB 单机必失败 |
| ★ 新引擎变体 | **须过 ADR**（`glm5next` / `O-121` 先例）——本仓**无引擎变体自动构建/分发**（`spec/vulkan-version-control/IMPLEMENTATION.md`） |
| ★ 机制互斥 | **worker 端口 50052 在单元里写死、无端口变量** ⇒ **同一时刻只能有一个 RPC 模型** ⇒ 载 Hy4 须先卸 `glm-5.3-flash` / `deepseek-v4-flash` |

---

## 3. 若仍要本地：条件性部署路径（**仅在 §5 前置通过后**）

> ⚠ 本节为**路径描述**，**不是建议**。P0 判定为「不建议投入」；下列仅供前置澄清后复用。

| 阶段 | 动作 | 本仓落点 |
|---|---|---|
| **S1 补丁核验** | 确认 `0002` 的 STQ1_0 内核是否在 `ggml-cuda/`（⇒HIP 可否继承）；确认是否**必须** CUDA 13 构建 | 外部取证 |
| **S2 引擎供给** | 复用 `glm5next` 的「**并存版本目录**」法：**B 单点构建** `/opt/llama.cpp-hy4-<sha>/`（`patchelf $ORIGIN`，**不切 symlink**）→ 三站分发；**head/worker 两端同版** | [GLM 部署文档 §6](../../docs/research/2026-09-28_GLM系列本地推理部署.md) |
| **S3 加载** | `python ops/cluster.py load hy4-preview-stq1_0 --engine hy4-<sha>`（落实例 conf 的 `LLAMA_SERVER_BIN` + `LLAMA_RPC_SERVER_BIN`）；★ 运行须 **`--jinja`**、权重放**本地盘**（NFS mmap 慢） | `--engine` 机制见 GLM 文档 §5 |
| **S4 切分** | 213.66 GiB ⇒ **B(head) + A + C**（`RPC_MODELS` head 恒 B、worker 仅 A/C、**上限 3 站**）；⚠ 三机 bench 已实测 **decode −6%** | `ops/cluster_const.py:85`、`cluster.py` `_load_rpc` |
| **S5 登记+治理** | `RPC_MODELS` 加别名 + `inventory/models.yaml` 三写法 + conf 自动生成 + **ADR** | `inventory/models.yaml` |

**性能预期（E3，仅供感受量级）**：官方 **8×H20** decode ≈**20 t/s**；**Prima.cpp** 异构（4090 笔记本 + 4×A4000）≈**1.5 TPS**。
⇒ 本集群（Vulkan/HIP + 3 机 RPC，本身 −6%）现实预期 **低个位数 t/s** —— **适合批处理，不适合交互**。

---

## 4. 落档建议：转托管兜底（★★ 首选）

### 4.1 走 OpenRouter（本仓通道已就绪）

- 腾讯在 **OpenRouter** 与自家 **TokenHub / WorkBuddy / CodeBuddy** 均上架 **hy4-preview**。
- 本仓 **`ADR-0003`** 已建成 egress（三站独立 OpenRouter 账户、`cluster.py egress` 用量监控、`local-only` 技术闸）⇒ **零新增基建**。
- 官方 API 价（launch-time）：**$0.834/M input · $2.501/M output · $0.042/M cached**。
- ⚠ 合规：走 egress ⇒ **仅 `public`/`sanitized` 内容可用**（`ADR-0003` D4 铁律）。

### 4.2 为什么不选 vLLM/SGLang 本地

官方 vLLM / SGLang recipe **只覆盖 FP8 checkpoint**（vLLM 用 `FLASHMLA_SPARSE`+`mtp`；SGLang 用 `NEXTN`），**不含 GGUF/STQ1_0**；
且 `ADR-0011` 明示 **A4 / vLLM TP2 暂缓**、`ADR-0012` 不新增镜像 ⇒ **此路不通**。

---

## 5. 未确证 / 待实测（★ 未做，不得当已知）

1. **`0002` 补丁是否含 Vulkan/HIP 可编译路径**（HF 抓取失败）—— **决定性未确证**。
2. **`hyv4` 与上游 `hy_v4` 的二进制/权重兼容性**（未做二进制验证）。
3. **llama.cpp RPC 跑 Hy4** —— **无任何公开案例**。
4. **1M ctx 的 KV cache 开销** —— **无公开数字**（GLM 1M 为 24 KiB/token，Hy4 未定标）。
5. **GGUF 侧 MTP 投机解码支持** —— 未确证。
6. **STQ1_0 档是否分片**（模型卡未说明）。
7. **A 站实时磁盘余量**（登记值有 605/773/894 三版）。
8. 二手 **「1.02 tok/s」** —— 未在官方源找到（官方 Prima 博客为 **1.5 TPS**），视为存疑。

---

## 6. 参考

| 项 | 位置 |
|---|---|
| **PR 状态单一真值** | [spec/upstream-tracker/TRACKER.md §1.9](../../spec/upstream-tracker/TRACKER.md) |
| egress 通道与免费/付费额度 | [ADR-0003](../../adr/ADR-0003-OpenRouter密钥与egress路由管理.md) |
| 跨站切分（`--engine` / 并存目录 / RPC 上限 3） | [2026-09-28_GLM系列本地推理部署.md](../../docs/research/2026-09-28_GLM系列本地推理部署.md) |
| 单机容量上界 119.4 GiB | [2026-09-28_O-110同站并发实测与O-112单机容量核验.md](../../docs/research/2026-09-28_O-110同站并发实测与O-112单机容量核验.md) |
| 现役后端矩阵（Vulkan vs HIP 双后端） | TRACKER §2.6 |
| 模型/引擎 ID 三写法 | [inventory/models.yaml](../../inventory/models.yaml) |
| Hy4 官方 | <https://github.com/Tencent-Hunyuan/Hy4-preview> |
| Hy4 GGUF（AngelSlim） | <https://huggingface.co/AngelSlim/Hy4-preview-GGUF> |
| 补丁基线 commit `0cea36222`（HF `hy4-preview-patch/`） | 见上 GGUF 仓库 |