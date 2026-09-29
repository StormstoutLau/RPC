# ADR-0011: A4（vLLM TP=2）暂缓裁定 —— vLLM 路径的定位、门槛与重启条件

---

id: ADR-0011
type: adr
version: 2.2
status: accepted
date: 2026-09-29
depends: [ADR-0004]
upstream: null
---

> **Feature**: 把「A4（vLLM TP=2 over USB4）」从混合研究文档中**剥离、单独立为决策记录** —— 回答"要不要推进 / 以何形态存在 / 何时重启"，并与既有的服务化与编排调研（[双机推理服务化与编排框架调研.md](../spec/operator-optimization/research/双机推理服务化与编排框架调研.md)）**对齐边界**：**该文档保留服务化与编排调研正文，vLLM 的决策面归本 ADR**。
> **创建日期**: 2026-09-29
> **状态**: accepted（2026-09-29 裁定：**暂缓**；v1.1 MTP / v1.2 支持度 / v1.3 版本边界 / v1.4 上游 0.27.0 / v1.5 更正 0.29.0 / v1.6 落地取证 / v1.7 FlashInfer-ROCm / v1.8 收敛版 / v1.9 M3 专项 / v2.0 M3 可行性 / v2.1 权重门 / **v2.2 AWQ 候选 ⇒ 有条件可行**）
> **适用**: A4 / vLLM 路径的**存废与定位**（是否推进、以何形态存在、何时重启）。**不改变** llama.cpp 作为主路线的地位、**不改变**三站现有服务形态、**不涉及** DwarfStar（另有 [ADR-0010](./ADR-0010-DwarfStar第二引擎引入立项.md)）。

---

## 元数据

| 字段 | 值 |
|------|-----|
| 编号 | ADR-0011 |
| 日期 | 2026-09-29 |
| 状态 | **accepted（v2.2 · 2026-09-29：暂缓；… v2.0 M3 可行性 / v2.1 权重门 / v2.2 AWQ 候选 ⇒ 有条件可行）** |
| 决策者 | Scott (鹏) |
| 相关文档 | [双机推理服务化与编排框架调研.md](../spec/operator-optimization/research/双机推理服务化与编排框架调研.md)（**服务化与编排调研正文；vLLM 决策面已归本 ADR**）· [metrics-log §A4/§A4b](../spec/rpc-optimization/metrics-log.md)（**成绩与实测主源**）· [AMD395分布式推理高性能互连方案调研](../spec/rpc-optimization/research/AMD395分布式推理高性能互连方案调研.md)（A4 行动项出处 §2.2/§4）· [双机剩余优化空间评估](../docs/双机剩余优化空间评估.md)（§2 排序）· [CIRU-Skulk-多机TP 调研](../docs/research/2026-09-16_分布式推理路线可行性调研_CIRU-Skulk-多机TP.md)（§11.1 decode 内存带宽 bound）· [GLM 系列本地推理部署](../docs/research/2026-09-28_GLM系列本地推理部署.md)（vLLM 跑 GLM 的量化可塞性）· [DwarfStar 专属量化清退方案](../docs/research/2026-09-29_DwarfStar专属量化清退方案.md)（同期清退，边界相邻）· 上游 [ayysasha/Strix-halo-dual-optimized](https://github.com/ayysasha/Strix-halo-dual-optimized)（配方出处）· 上游 [vLLM Speculative Decoding 文档](https://docs.vllm.ai/en/latest/features/speculative_decoding/)（MTP 方法选型表 + "memory-bound" 定位；见「MTP / 投机解码专项调研」节） |
| 取代 | 无（本 ADR **不取代**任何既有 ADR；它把 [ADR-0010](./ADR-0010-DwarfStar第二引擎引入立项.md) 语境里偶被并列讨论的"vLLM 替代路线"**单列成独立决策面**） |

## 最终结论汇总（TL;DR · 2026-09-29 · **v2.2**）

> 本节是全 ADR 的**收敛版**，**已并入 §11（M3 专项）与 §12（M3 可行性）**。下方各节保留**逐次取证的原始过程（含 4 次自我更正）**；只读结论看本节即可。

### A. A4 本体

| 项 | 结论 |
|---|---|
| 状态 | **暂缓**（非否决、非待办） |
| 已实测（E1，2026-08-29） | pp512 **298 t/s（2.1×）** · tg128 **17.60（−14.7%）** · 16k **稳定通过**；决策门「单流 tg ≥ 24」**未达** |
| 定位 | **长上下文 prefill 路径**（16k PP 193 t/s）+ **decode 侧投机解码候选**（未试） |
| 已定稿配置 | `--enforce-eager` + 无 `TORCHDYNAMO_DISABLE` + BIOS carve-out 0.5 G + 双路径（8080 llama.cpp / 8081 vLLM） |
| ★ 判据射程 | CUDA graph 已证伪（16k TG −71%）；**投机解码尚未试** ⇒ "无已知路径拉高 tg"**只覆盖 kernel/config 与 launch 开销两条轴** |

### B. 五族模型在 vLLM 上的支持度（终版，逐条更正后）

| 模型 | 架构实现 | AMD 原生 | MTP | 本仓权重格式 |
|---|---|---|---|---|
| **GLM-5.3-Flash** | ✅ **`GlmMoeDsaForCausalLM`（本 build 即有，`deepseek_v2.py:1914`）** | ⚠ 0.29.0 上提至 `vllm.models.deepseek_v32`（本 build 该子包仅 `nvidia/`） | ❌ 仅 glm4 系 | ❌ GGUF |
| **DeepSeek-V4-Flash** | ✅ `DeepseekV4ForCausalLM` | ✅ **有 `deepseek_v4/amd/`** | ✅ `deepseek_mtp` | ❌ GGUF |
| **MiniMax-M2.7** | ✅ `MiniMaxM2ForCausalLM`（**A4 已实测跑通**） | ⚠ 无（`minimax_m3` 才有） | ❌ 仅 M3 | ❌ GGUF |
| **Qwen3.8-Flash-Next** | ✅ `vllm/models/qwen4_exp`（**0.29.0 起**） | ❌ | 模型自带 MTP 参数 | ❌ GGUF |
| ★ **MiniMax-M3** | ✅ `MiniMaxM3SparseForConditionalGeneration/G`（**官方 config.json 实取，逐字一致**） | ✅★ **一等路径**（`models/minimax_m3/amd/` + `amd/ops/index_topk.py`·`sparse_attn.py`·`gemma_rmsnorm.py`·`swiglu_oai.py`，与 `use_gemma_norm`/`swigluoai` 属性一一对应） | ✅ `MiniMaxM3MTP` + `amd/mtp.py` | ❌ GGUF / ✅ **AWQ 有候选**（`cyankiwi/…-AWQ-INT4` **258.0 GB**，E1 实测） |
| **共同第一道门** | **本 build 零 GGUF 支持** ⇒ 五族现役 GGUF 权重**一份都不能直接用**（与架构支持无关） | | | |

### C. 版本与渠道

| 项 | 结论 |
|---|---|
| 三站实装 | `vllm 0.25.2.dev0+rocm7.15.0a20260724.g752a3a504.d20260724`（**2026-07-24**），**三站逐字一致** |
| lemonade 渠道（gfx1151） | **已到顶** —— 该档仍是其最新发布（GitHub API 实查，E1） |
| 上游 | **v0.30.0**（`v0.31.0rc1` 在途）；**0.29.0 起 GLM-5.3-Flash 入支持面**（Experimental；官方配方 = `vllm/vllm-openai:glm53-flash` 镜像 + FlashInfer ≥0.6.17） |
| ⇒ 升级意义 | 要吃到 0.29.0 需**换渠道或自建**（ROCm 10.0.0 支持矩阵含 gfx1151 + vLLM 0.27.0，py3.14 + torch2.13） |

### D. GLM-5.3 在本集群走 vLLM 的**净结论**

> **架构有实现 · 依赖有 ROCm 替代 · 但无已验证路径。**

- ✅ **`flashinfer` 非前置** —— 本 build 有平行 ROCm 后端（`rocm_aiter_mla_sparse` / AITER ops / Triton indexer），且 `has_flashinfer()` **每个调用点都带 NVIDIA 能力门（90 / 120）**
- ⚠ **但官方 FlashInfer-ROCm 只覆盖 Instinct（MI3xx）**，且版本 **0.5.3 < 所需 0.6.17** ⇒ **gfx1151 无已验证路径**
- ⚠ **权重格式仍是第一道门**（本仓五族全 GGUF）
- ⇒ 要判可行性**只能实起一次**；**本 ADR 从未加载过任何 GLM-5.3 权重**

### D2. ★ MiniMax-M3 在本集群走 vLLM（§11–§12）

> **有条件可行** —— 五族里**唯一"引擎版本 + ROCm 一等路径 + MTP + 现成权重候选"四者都在手**的。

| 条件 | 状态 |
|---|---|
| 架构 / 算子 | ✅ `MiniMaxM3SparseForConditionalGeneration/G` + **AMD 专用算子**（对照 GLM-5.3 走通用实现，**无 AMD 专用算子**） |
| 引擎版本 | ✅ 现装 `0.25.2.dev0` 即有，**不需升版**（GLM-5.3 需换渠道） |
| MTP | ✅ 可用（`amd/mtp.py`） |
| 权重 | ✅ 候选 = `cyankiwi/MiniMax-M3-AWQ-INT4` **258.0 GB**；且 **AWQ+MoE+ROCm+gfx1151 已由 A4 实证**（M2.7-AWQ 17.60 t/s） |
| MoE tuned config | ⚠ **需为 M3 调 `E=128`**（现档 `E=256,N=768`） |
| 三站 TP=3 实起 | ⚠ **未测** |
| 体积 | ⚠ **69% 占用**（258 / 三站 ≈372 GB）；外部参考盘更大（TP4 384 GB）⇒ **真实风险** |
| 对照：llama.cpp RPC | ❌ **现装不支持**（commit `91f6a6cf` 早于支持 MSA 的 #24908）⇒ 且 MSA 强制 FA、**M3 自带 MTP 在 llama.cpp 未被利用** |

### E. ★ 方法教训（本 ADR **四次**自我更正的根因 —— 写给下一个人）

| 已写下的错误结论 | 被推翻的原因 |
|---|---|
| "GLM-5.3 / Qwen4exp **无匹配键**" | ① 把 **GGUF 侧**架构名 `glm5next` 当 **HF 侧 `architectures` 键名**比对；② 只 grep **含 "glm" 字样**的键名，**漏掉 `GlmMoeDsa`**；③ **版本只查到 0.27.0** |
| "升级**不解锁** GLM-5.3" | 版本上界写死，未查 0.29.0 |
| "**唯一**硬缺口 = FlashInfer" | 把**上游 CUDA 配方**的要求当成**跨平台前置**，未读本 build 的 ROCm 分支 |
| ★ **共同根因** | **证据只覆盖一段时，把结论写满了。** ⇒ **规矩：每写一条否定性结论，必须同时写明它的射程**（版本 / 平台 / 渠道 / 权重格式）；否则下一位读者会把它当**全称判断**用。 |
| ★★ **第 4 次更正补的规矩** | **枚举类结论还要写明"用什么手段枚举的"。** "M3 无可用量化档"被用户三个仓推翻，根因是**手段太弱**（HF 搜索 API 不可达，只能按已知路径 HEAD 试）—— 射程声明有了，**手段声明没有**。⇒ 凡"未找到 X"的结论，须同时写**检索手段与其已知盲区**。 |

## 范围声明（先于一切）

**本决策仅约束「本集群是否/以何形态保留 vLLM 路径」，不改变 llama.cpp 主路线的任何现有做法。**

- 显式排除：vLLM **引擎内部**实现（属上游）；三站**服务化与编排架构**（属[框架调研](../spec/operator-optimization/research/双机推理服务化与编排框架调研.md)）；DwarfStar 的存废（属 ADR-0010）。
- 本 ADR **裁的是"暂缓"这一状态**及其**重启条件** —— 不是"否决 vLLM"。

## 背景（Context）

### 触发实例

1. **A4 已执行过，且已定稿**（E1，2026-08-28/29）：在 **B head + A worker** 的 TP=2 形态上跑通 —— pp512 **298 t/s（2.1×）**、tg128 **17.60（−14.7%）**、16k **完整跑完无崩溃**。
2. **决策门一过一不过**：门①「单流 tg ≥ 24 t/s」**未达**（17.60）；门②「16k 上下文无崩溃」**通过**。
3. **已试过的拉高 tg 手段被证伪**（E1，A4b）：去掉 `--enforce-eager` 上 CUDA graph ⇒ 短上下文 decode −15%、**16k decode −71%（病理性）**，已回退。定性：**瓶颈是 LPDDR5X 带宽，不是 kernel launch 开销** ⇒ graph 无从改善。⚠ 该证伪只覆盖"**削 launch 开销**"这条轴；**投机解码是另一条轴，且尚未试过** —— 见「MTP / 投机解码专项调研」节。
4. **资产缺口**（E1，2026-09-29 三站实测）：vLLM 便携栈 `~/vllm-rocm` **三站齐备**（C 站于 2026-09-29 补齐并与 B **逐位一致**），但 **A4 所用 AWQ 模型（MiniMax-M2.7-AWQ-G32-STRIX-2H，155.28 GB）已删净**（HF cache 仅剩 12 KB 元数据）⇒ 任何"再跑一次"都是**净新增十几小时下载**。
5. **同期出现的替代解释**（E1/E2）：[CIRU 调研 §11.1](../docs/research/2026-09-16_分布式推理路线可行性调研_CIRU-Skulk-多机TP.md) 实测 **decode 是内存带宽 bound**（加节点 decode 反降：双机 11.94 → 三机 11.22）；本仓 A3a 端到端复测亦给出**零 tg 增益**（RTT 压 6.8× 而 decode 纹丝不动）⇒ 印证"跨机链路的算力/延迟项不是 decode 的约束"。

### 根因

**A4 的价值与"决策门"错配**：决策门（tg ≥ 24）度量的是 **decode**，而 A4 实测真值在 **prefill（2–3×）**。既有的"是/否推进"框架**用一个它并不擅长的指标来裁一个它擅长的事** ⇒ 才出现"门未达，但也不该简单否决"的悬空态。本 ADR 的作用就是把判据从"**能不能替代 llama.cpp**"改成"**要不要保留一条 prefill 专用路径（外加一个 decode 侧的投机解码候选）**"。

## 决策（Decision）

**在「无长上下文 prefill 瓶颈」的当前负载下，选择"暂缓"（保留能力面、不投入体积与时间）而非"推进产品化"或"彻底否决"。**

### 1. 状态 = 暂缓（非否决、非待办）

- **不排 P-x 计划**，不再重跑 A4，不再追逐 ayysasha 报告上限（剩余变量仅 Triton MoE tuned-config / AWQ kernel 差异，边际 ≤10%，已判"不再追逐"）。★ **该判断只覆盖 kernel / 配置层**；**投机解码属另一条轴，不在"不再追逐"射程内** —— 见「MTP / 投机解码专项调研」节。
- **保留能力面**：三站 `~/vllm-rocm`（各 8.0 G）+ `~/moe-shim` + `~/moe-configs` **不删**；`cluster.py` 的 `BACKENDS` 白名单仍含 `vllm`。
- **保留已定稿配置**（重启用它，不重新实验）：`--enforce-eager` + **无** `TORCHDYNAMO_DISABLE` + BIOS carve-out 0.5 G + 双路径并存（**8080 llama.cpp / 8081 vLLM**）。

### 2. 定位 = prefill 路径 + **decode 的投机解码候选**（不是现成 decode 替代）

vLLM 在本集群的角色写死为 **长上下文 prefill 加速器**（16k PP 实测 **193 t/s**，是本仓**唯一量过**的高上下文 prefill 数据点）+ **投机解码候选**（「MTP / 投机解码专项调研」节：站上 vLLM 内置 MTP/投机方法，且投机解码攻击的就是本仓实证的带宽瓶颈）。

**现成状态下 decode 仍回归 llama.cpp**（20.64 vs 17.60，+14.7%）。⇒ 任何"vLLM 现成形态已是更快的主引擎"的说法**与本 ADR 冲突**；但 **「MTP / 投机解码专项调研」节给出的路径，是打开 decode 决策门（≥24 t/s）的已知候选**。

### 3. 重启条件（写死，避免"暂缓"滑成"遗忘"）

满足**任一条**即重启 A4（届时按「状态 = 暂缓」节列出的已定稿配置直接走，不重做实验）：

1. **出现长上下文 prefill 密集的常态负载**（RAG / 代码库分析 / 长文档批处理），且实测 llama.cpp 8080 的 **prefill 成为端到端瓶颈**；
2. llama.cpp 侧 prefill 出现**回归**（既有观测：BIOS 512 MB 配置下 pp512 已记 **−9.1%**；若进一步劣化）；
3. 有别的工作负载明确要求 **>16k 上下文**；
4. **上游已有 GLM-5.3 / Qwen3.8-Flash-Next 的架构支持**（v0.29.0 起）—— ⚠ 但**本集群仍无已验证路径**（见 §10：官方 FlashInfer-ROCm 只覆盖 Instinct 且 0.5.3 < 0.6.17；lemonade 的 gfx1151 档仍停在 0.25.2）⇒ **本条不构成"现在就该动"的理由**；真正的前置是**换渠道 / 自建 0.29.0+，并自行打通 AITER 稀疏 MLA**。

> ★ **启动成本必须先标价再决定**：重下 AWQ **155.28 GB**（量级十几小时）+ 复现 pp/tg —— 属**净新增投入**，不是"接着上次跑"。

### 机制原理（为何有效）

**把"能力保留"与"体积/时间投入"分开**：栈（8.0 G/站）保留成本≈0，模型（155.28 G）是可重下的外部资产 ⇒ "暂缓"只冻结**投入**，不销毁**能力**。论证强度：**单实例实证**（A4/A4b 各一轮实测）+ 机制设计常规论证。

### 与既有 ADR/规则的关系

- **与 [ADR-0010](./ADR-0010-DwarfStar第二引擎引入立项.md)**：互补且**同构** —— 两者都是"保留引擎、清退/冻结重型权重"的处置；但**决策对象不同**（ADR-0010 管 ds4 引擎的存废，本 ADR 管 vLLM 路径的推进与否），**不可互相替代**。
- **与 [ADR-0004](./ADR-0004-统一管理入口为唯一管理面.md)**：A4 的**加载入口**（`cluster.py load --backend vllm`）是统一管理面的一部分，本 ADR 只裁"要不要用"，不改入口实现。
- **与框架调研文档**：该文档的 vLLM 段落是**服务化视角**（网关/路由/监控如何对待 8081），**决策面已上移到本 ADR**。

## 考虑的替代方案（Alternatives Considered）

### 替代方案 0: 带 MTP / 投机解码的 vLLM 路径（**另见「MTP / 投机解码专项调研」节**）

- 摘要: 站上 vLLM 0.25.2.dev0 **内置 MTP 投机解码**（`MTPModelTypes` 20 族）+ 多种无头方法（ngram/suffix/draft/eagle 等）；官方将投机解码定位为"**面向 memory-bound 负载、降低 token 间延迟**"，与 A4 实测的**带宽瓶颈**直接对口。
- 否决/推迟理由: 硬前提是**目标权重自带 MTP 头**（如 `deepseek_mtp` / `qwen3_next_mtp` / `minimax_m3_mtp`），而 A4 现役的 **MiniMax-M2.7 本 build 无 MTP 实现** ⇒ 仍卡在**重下权重**这道门。详见该节。

### 替代方案 A: 立即重下 AWQ 并产品化到 8081（**推迟**）

- 优点: 兑现 prefill 2–3×；把双路径从"脚本手工切换"变成常驻服务。
- 缺点: **净投入十几小时下载**（08-29 分段并行实测仅 2.6 MB/s）+ 复现与回归成本；而**当前没有触发它的负载**。
- 否决理由: **收益无对应场景** —— 为一个尚未出现的负载先付十几小时与 155 GB 磁盘。**不是不可行，是顺序错**（故记"推迟"而非"否决"，重启条件见「重启条件」节）。

### 替代方案 B: 用现役 GGUF 模型试 vLLM（**否决**）

- 优点: 不下载，立刻能跑。
- 缺点: vLLM 在 GGUF 上的 MoE 支持不是 A4 的实测路径；**A4 的 2.1× prefill 依赖 MoE AWQ tuned-kernel + shim**，换格式就把这条优势丢掉。
- 否决理由: 结论**不可用于判定 vLLM 路径本身**（口径不对），等于花钱做一个不能采信的实验。

### 替代方案 C: 彻底否决并清掉 vLLM 栈（**否决**）

- 优点: 三站各回收 8.0 G，仓库少一条并行路径。
- 缺点: 栈的保留成本≈0；且**重启条件是活的**（「重启条件」节三条随时可能触发）⇒ 清掉等于把"命中条件后再花十几小时下载 + 重新解压 + 修 shebang"这些工作**重做一遍**。
- 否决理由: 与"保留能力面"的成本收益相反；栈是**廉价期权**，不该提前行权。

## 后果（Consequences）

### 正面

- 决策面**单点化**：vLLM 的存废/定位/重启条件不再散落在研究文档与滚动日志里。
- 判据**换对**：从"能否替代 llama.cpp"改为"要不要保留 prefill 专用路径"，消除了"门未达但不该否决"的悬空态。

### 负面

- **双路径的服务化收尾被无限期挂起**（8081 仍是脚本态，非 systemd 常驻）⇒ 框架调研文档中与之相关的编排条目保持"未落地"。
- 一旦命中 §3 条件，**首次启动要付十几小时下载**（无缓存可复用）。

### 中性 / 需要后续行动

- C 站虽在 2026-09-29 补齐了 vLLM 栈，但**TP=3 的可行性未验证**（栈前提已具备，缺权重与实测）。
- `~/vllm-rocm` 与 `~/moe-*` 属**能力面资产**，其清理条件写在本 ADR「状态 = 暂缓」节与 [DwarfStar 清退方案](../docs/research/2026-09-29_DwarfStar专属量化清退方案.md) §5。

## 验证（Validation）

### 已有实证

| 依据 | 来源 | 状态 |
|------|------|------|
| pp512 298 t/s（2.1×）/ tg128 17.60（−14.7%） | [metrics-log §A4](../spec/rpc-optimization/metrics-log.md)（2026-08-29 实测） | ✅ E1（历史实测，**本轮未复跑**） |
| 16k 稳定性门通过（无崩溃/hang/OOM） | 同上 | ✅ E1 |
| CUDA graph 全面负迁移（16k TG −71%） | 同上 §A4b | ✅ E1（已回退） |
| 三站 `~/vllm-rocm` 齐备 · C 与 B 逐位一致 · GPU 可见 | 2026-09-29 实测（`cuda_avail True` · `AMD Radeon 8060S Graphics`） | ✅ E1 |
| AWQ 模型三站皆无 | 2026-09-29 三站实测 | ✅ E1 |

### 待验证项

- **长期不用的栈是否会腐化**（`~/vllm-rocm` 依赖 `LD_LIBRARY_PATH` 指向自带 ROCm 用户态；系统 `/opt/rocm` 若升级，栈是否仍可用）—— 未测。
- **TP=3 over USB4 的 Gloo/RCCL 行为** —— 未测（栈前提已具备，缺权重）。
- **MTP / 投机解码的实测收益**（见「MTP / 投机解码专项调研」节）—— 支持面已取证，但**从未跑过任何投机配置**；需带 MTP 头的权重才可测。
- **权重体积可塞性**（见「模型支持度专项调研」节 §4）—— 该节只裁"引擎侧支持面"；**DeepSeek-V4-Flash 的 HF 档体积与其在 TP=2 下的显存预算均未核**，故"首选"仅指支持面，不等于可跑。

### 失效条件（何时重审本 ADR）

- 「重启条件」节**任一命中** ⇒ 本 ADR 的"暂缓"前提不再成立，须重审。
- 「模型支持度专项调研」节里标"**无匹配键**"的两项（GLM-5.3-Flash / Qwen3.8-Flash-Next），若出现**任一**新 build（lemonade gfx1151 出新档，或按 ROCm 10.0.0 支持矩阵自建 vLLM 0.27.x）且其 registry 含对应键 ⇒ **须重审该节**（该节结论是版本绑定的）。
- 出现**同类替代路线**（如 SGLang / 其他 prefill 引擎）在本集群被实测优于 vLLM ⇒ 须重审「定位」节。
- llama.cpp 侧 prefill 大幅改善（如 `-ub` / 新算子合入）至 193 t/s 量级 ⇒ vLLM 的 prefill 优势消失，须重审。
- **「MTP / 投机解码专项调研」节的路径若被实测证明能把 vLLM decode 推到决策门（≥24 t/s）** ⇒ **决策门从"未达"翻转为"可达"** ⇒ 「定位」节里"decode 回归 llama.cpp"的结论失效，须重审。

## MTP / 投机解码专项调研（2026-09-29）

**缘起**：本 ADR 初版写"**没有已知路径把 tg 推到 24**"。该判断只覆盖了两类**已试过**的手段 —— **压链路延迟**（A3a）与**削 kernel launch 开销**（A4b）。本节核查**第三类：投机解码**，它恰好攻击本仓实证的**带宽瓶颈**。

### 1. 站上 build 的支持面（E1，直接读 `~/vllm-rocm` 源码）

| 项 | 证据 |
|---|---|
| 版本 | `vllm 0.25.2.dev0+rocm7.15.0a20260724.g752a3a504.d20260724` |
| MTP 是否内置 | ✅ `vllm/config/speculative.py` 的 `MTPModelTypes` 为 **20 项**字面量清单 |
| MTP 族清单 | `deepseek_mtp`（V3/V4）· `mimo_mtp` / `mimo_v2_mtp` · `glm4_moe_mtp` / `glm4_moe_lite_mtp` / `glm_ocr_mtp` · `ernie_mtp` · `nemotron_h_mtp` · `exaone_moe_mtp` / `exaone4_5_mtp` · **`qwen3_next_mtp`** / **`qwen3_5_mtp`** · `longcat_flash_mtp` · **`minimax_m3_mtp`** · `bailing_hybrid_mtp` · `mtp`（通用）· `pangu_ultra_moe_mtp` · `step3p5_mtp` · `hy_v3_mtp` · `gemma4_mtp` |
| **无需 MTP 头**的方法 | `ngram` · `ngram_gpu` · `suffix` · `draft_model` · `eagle` · `eagle3` · `medusa` · `mlp_speculator` · `dflash` · `dspark` · `custom_class` |
| 调用面 | `--speculative-config '{"method": "<族>_mtp", "num_speculative_tokens": N}'` |

### 2. 硬约束：MTP 需要**权重自带 MTP 头**

- vLLM 官方选型表原话：MTP **"Best when the target model has native MTP support"**。
- 本 build 的 `models/` 下 MiniMax **只有 `minimax_m3/`**（含 `mtp.py`）；`model_executor/models/minimax_m2.py` **存在但不含 MTP**。
- ⇒ **A4 现役的 MiniMax-M2.7 吃不到 MTP** —— **不是引擎能力问题，是权重缺头**。
- ⇒ 想走 MTP 仍需**重下带 MTP 头的权重**，与「替代方案 A」**是同一道门**。

### 3. 为什么这条路"方向对"（本次调研最值钱的判断）

| 手段 | 攻击对象 | 本仓实测 |
|---|---|---|
| **A3a**（TCP 低延迟 sysctl） | 链路 RTT | RTT 压 **6.8×** ⇒ decode **零增益** |
| **A4b**（CUDA graph） | kernel launch 开销 | 16k TG **−71%**（病理性）⇒ 证伪 |
| **投机解码 / MTP** | ★ **每 token 的权重搬运量** | **未测** |

投机解码在**一次前向**里验证 k+1 个候选 ⇒ **被接受的 token 近乎"免费"**（验证开销与候选数无关）。这与本仓已钉死的 **decode = 内存带宽 bound**（[CIRU §11.1](../docs/research/2026-09-16_分布式推理路线可行性调研_CIRU-Skulk-多机TP.md)）**正面对口**：官方把投机解码定位为 "reduce inter-token latency under … **memory-bound** workloads"；Red Hat 讲 MTP 的文章开篇即 "autoregressive decoding … **is memory-bandwidth bound** … the hardware spends most of its time moving weights"。

### 4. TP 路径特有的加成（与 llama.cpp RPC 的既往结论**方向相反**）

本仓 [双机剩余优化空间评估](../docs/双机剩余优化空间评估.md) 曾判："投机解码在**双机 RPC 上**是未验证的赌博 —— 每步验证引入额外跨链同步，**方向上与已确认的瓶颈（命令数）相反**"。该判断对 `-sm layer` + 串行跨链**成立**。

但在 **vLLM TP** 上该反向税**不存在**：TP 本就每层 all-reduce，投机解码让**每输出 token 的 all-reduce 轮数降到约 1/(k+1)** ⇒ 对 TP 是**双重收益**（带宽 + 通信）。⚠ 此为**机制推演，未实测**。⇒ 结论应记为：**投机解码更适配 vLLM TP，而不是 llama.cpp RPC**。

### 5. 门槛与风险（全部未验证）

| 门槛 | 现状 |
|---|---|
| 带 MTP 头的权重 | 三站皆无 ⇒ **需下载**（同「替代方案 A」） |
| AWQ + 投机在 gfx1151/ROCm | **未验**（本 build 的 MTP 实现含 `amd/` 目录，但从未跑过） |
| 16k 长上下文收益衰减 | 预期衰减（A4 已测 16k TG 12.87，自身已 −27%） |
| 收益档位 | 官方选型表：**低 QPS 高收益 / 高并发中等收益** |

### 6. 结论

**能，但不是 A4 现役那份权重。** ⇒ 记为本 ADR 的**已知候选路径**（未推进；同受「重启条件」与「重下权重」两道门约束），并在「失效条件」登记其**翻转判据**。

另注：本仓 `metrics-log` **零 MTP 命中** ⇒ vLLM 路线的投机解码**从未试过**；GLM 的 `--mtp` 亦仅为 [ADR-0010](./ADR-0010-DwarfStar第二引擎引入立项.md) 侧的未测项。⚠ 勿与 llama.cpp 侧的 "DSpark draft 无法加载"（#26490/#26610）混淆 —— vLLM 的 `dspark` 是同源概念的不同实现。

## 模型支持度专项调研（2026-09-29）

**缘起**：上一节只回答了"vLLM 能不能做投机解码"。真正决定 vLLM 路径可用面的是**四个现役模型各自的架构支持度**。本节按 **①架构键 ②AMD 原生实现 ③MTP ④本仓权重格式** 四轴逐个核。

### 1. 四轴对照（除标注外均为 E1：直接读站上 build 与权重头）

| 本仓现役模型 | GGUF `arch`（读权重头） | vLLM registry 对应键 | AMD/gfx1151 原生 | 投机 / MTP | 本仓权重可直接用？ |
|---|---|---|---|---|---|
| **GLM-5.3-Flash** | `glm5next` | ⚠️ **无匹配键** —— GLM 侧只有 `Glm` / `Glm4` / `Glm4Moe` / `Glm4MoeLite` / `GlmMoeDsa` | ❌ 无 `glm*` 的 `amd/` | 有 `glm4_moe_mtp` / `glm4_moe_lite_mtp` / `glm_ocr_mtp`，**均非 5.3** | ❌ GGUF |
| **DeepSeek-V4-Flash-0731** | `deepseek4` | ✅ **`DeepseekV4ForCausalLM`** → `vllm.models.deepseek_v4` | ✅ **有 `models/deepseek_v4/amd/`** | ✅ `deepseek_mtp` + registry `DeepSeekV4MTPModel` | ❌ GGUF |
| **MiniMax-M2.7** | `minimax-m2` | ✅ `MiniMaxM2ForCausalLM` → `minimax_m2`（**A4 已实测可跑**） | ⚠️ M2 **无** `amd/`（`minimax_m3` 才有） | ❌ 仅 `minimax_m3_mtp` | ❌ GGUF |
| **Qwen3.8-Flash-Next** | **`qwen4exp`** | ❌ **无匹配键** —— Qwen 侧只有 `Qwen3` / `Qwen3Moe` / `Qwen3Next` / `Qwen3_5` / `Qwen3_5Moe` | ❌ | ✅ 模型**自带 MTP 参数**（E3）；但 registry 的 `qwen3_5_mtp` **不匹配 `qwen4exp`** | ❌ GGUF |
| _参考：`qwen3.8-27b-mtp`_ | `qwen35` | ✅ `Qwen3_5ForCausalLM` | ❌ | ✅ `qwen3_5_mtp` | ❌ GGUF |

> ★★ **本节下方 §8 已推翻本表的两行结论（GLM-5.3 / Qwen3.8-Flash-Next 的"无匹配键"）** —— 那两行只对 `0.25.2.dev0`（及 0.27.0）成立，**上游 v0.29.0 起已变**。读本表前请先读 §8。

### 2. 三条关键结论

**① 格式是共同的第一道门（且比架构更硬）。** 本 build **零 GGUF 支持** —— `find *gguf*` 在 `vllm/` 下**零命中**，quantization 目录亦无 `gguf.py`；它支持的是 `auto_awq` / `auto_gptq` / `fp8` / `fbgemm_fp8` / `compressed_tensors` / `modelopt` / `mxfp4` / `moe_wna16` / `torchao` / `quark` 等**safetensors 系**。而本仓四份现役权重**全是 GGUF** ⇒ **一份都不能直接用**，与架构支持与否无关。

**② 架构支持分三档。**
- **最完整 = DeepSeek-V4-Flash**：架构键 ✓、**AMD 原生实现 ✓**、MTP ✓ —— **四轴里唯一三齐的**。
- **键齐但缺 AMD 原生 = MiniMax-M2.7**：`MiniMaxM2ForCausalLM` 在，且 A4 已实测跑通（17.60 t/s）；但 M2 没有 `amd/` 专用实现。
- **本 build 无匹配键 = GLM-5.3-Flash 与 Qwen3.8-Flash-Next**：前者是 `glm5next`（E3：vLLM stable 的 GLM 支持表止于 **GLM-4.5/4.6/4.7 + 4.7-Flash**，**无 5.3**）；后者是 **Qwen4 预览架构**（E3：官方 blog 自述 "an early preview of the architecture used in **Qwen4**"，NVIDIA blog 亦称 Qwen3.8-Flash-Next 的 vLLM 支持只是 **"best-effort Day 0 functional support"**）。

**③ MTP 可用面被这一步显著收窄。**
- 四轴里"架构 + MTP 双命中"的**只有 DeepSeek-V4-Flash**。
- MiniMax-M2.7 与 GLM-5.3 都**吃不到 MTP**（前者只有 M3 版实现；后者只有 glm4 系）。
- Qwen3.8-Flash-Next **自带 MTP 参数**，但其架构不在本 build ⇒ **白白错过**。

### 3. 逃生口（E3，未验证）

vLLM 提供 **"Transformers modeling backend"**（`--model-impl transformers` + `--trust-remote-code`）可加载**未原生支持**的架构。⚠ 但它是**非调优路径** —— MoE 专用 kernel 与投机解码**未必生效**；且需 transformers 侧先支持该架构。**本仓未验证**。

### 4. 对本 ADR 的修正（重要）

「MTP / 投机解码专项调研」节曾把门槛写成"需要带 MTP 头的权重"。**本节把它收紧为一个有首选的判断**：

> 若要重启 A4 试投机解码，**最省的门不是重下 MiniMax-M2.7 AWQ**（架构命中但 **MTP 不命中**、且无 AMD 原生），**而是 DeepSeek-V4-Flash 的 HF 权重** —— 它是四轴里唯一"架构 + AMD 原生 + MTP"全命中者，且上游有现成重量化档（`mxfp4` 在本 build 的 quantization 白名单内）。

⇒ 这条把"重下哪份权重"从一个开放问题变成一个**有明确首选**的问题。**但注意**：本结论**只覆盖引擎侧支持面**，**未含**权重体积可塞性（V4-Flash 的 HF 档体积、TP=2 下的显存预算**均未核**）。

### 5. ★ 版本边界（本节的适用射程 —— 防外推）

| 项 | 值 |
|---|---|
| 本节**全部结论的基准** | 三站**一致**的 build：`vllm 0.25.2.dev0+rocm7.15.0a20260724.g752a3a504.d20260724` · `amd_torch_device_gfx1151 2.12.0+rocm7.15.0a20260724` · `ray 2.58.0`（构建日期戳 **2026-07-24**） |
| 来源与**渠道新鲜度** | [lemonade-sdk/vllm-rocm](https://github.com/lemonade-sdk/vllm-rocm) 的 **gfx1151** release bundle。**E1（2026-09-29 经 GitHub API 实查）**：对 gfx1151，`…d20260724` **仍是该渠道最新发布档**（同批覆盖 gfx1151 / 1150 / 110X / 120X；列表里更晚发布的是 `vllm0.19.1-rocm7.13.0-gfx950`，属**另一条架构线**）⇒ **就 lemonade 渠道而言无更新可拉** |
| ★ **但上游 vLLM 已到 0.27.x**（E3） | NVIDIA vLLM **26.08** 容器 = **0.27.1**；**ROCm 10.0.0 官方支持矩阵（2026-08-26）= vLLM 0.27.0，且明确含 `gfx1151`**（Linux / Python 3.14 / PyTorch 2.13.0）⇒ 本 build **落后约 2 个小版本**（0.25.2 → 0.26 → 0.27） |

> ⚠ **推论边界（写死）**：§1 的"**无匹配键**"（`glm5next` / `qwen4exp`）**只对 `0.25.2.dev0+…d20260724` 成立**，**不得**外推为"vLLM 不支持"。0.26 / 0.27 的 registry 是否已补入对应键——**未核**——而这恰是这两项的**唯一解锁条件**。
> ★ **两条升级路径（均未做）**：① 等 lemonade 渠道出 gfx1151 新档（今日无）；② 按 ROCm 10.0.0 支持矩阵**自建** vLLM 0.27.0 + gfx1151（系统 ROCm 10.0.0 + Python 3.14 + PyTorch 2.13.0）—— 后者是**一条全新构建路径**，成本/风险都不等同于现在的"便携 bundle 开箱"。

### 6. 上游 **v0.27.0** 对照（E1：直接读该 tag 源码，非读文档）

> **为什么补**：§1 的基准是站上 `0.25.2.dev0`。本节按用户要求**拉上游 v0.27.0 的 tag 源码**复核（`raw.githubusercontent.com/vllm-project/vllm/v0.27.0/...` + GitHub contents API，经站上 curl）。

| 判据 @**v0.27.0** | 结果 | 相对 `0.25.2.dev0` |
|---|---|---|
| **GLM 键** | `Glm` / `Glm4` / **`Glm4Moe`** / `Glm4MoeLite` / `GlmMoeDsa`（另有 VLM/ASR/OCR 变体）—— **无 `Glm5` / `Glm5Next`** | **无变化** |
| **DeepSeek 键** | `Deepseek` / `V2` / `V3` / `V32` / **`V4`**（`vllm.models.deepseek_v4`） | **无变化** |
| MiniMax 键 | `MiniMaxM2` / `MiniMaxM3Sparse` | 无变化 |
| `vllm/models/` 原生子包 | `deepseek_v32` · `deepseek_v4` · `minimax_m3` · **`inkling`** · **`kimi_k3`** | **+2 家**（与 GLM/DeepSeek 无关） |
| `MTPModelTypes` | **22 项**（+`kimi_k3_mtp` / `inkling_mtp`）；GLM 侧仍仅 `glm4_moe_mtp` / `glm4_moe_lite_mtp` / `glm_ocr_mtp`；DeepSeek 仍 `deepseek_mtp` | +2 项 |

> ★★ **核心结论（推翻本 ADR 自设的一条前提）**：**从 `0.25.2.dev0` 升到 `0.27.0`，GLM / DeepSeek 的支持度没有任何变化** —— GLM-5.3 **依旧没有以 `glm5*` 命名的实现**；DeepSeek-V4 依旧**三齐**（架构键 + AMD 原生 + MTP）。
> ⇒ 「重启条件」节第 4 条设想的"升级后出现 `glm5next` 键"，**在 0.27.0 上已核：未出现** ⇒ **升级不是解锁 GLM-5.3 的手段**（至少到 0.27.0 为止）。

> ⚠ **本节与 §1 共同的未取证项（勿过度断言）**：**两份模型在 HF 侧的 `architectures` 字段仍未取到**（本轮试取 `zai-org/GLM-5.3-Flash`、`deepseek-ai/DeepSeek-V4-Flash`、`deepseek-ai/DeepSeek-V4-Flash-0731`、`Qwen/Qwen3.8-Flash-Next` 的 `config.json`，**均返回空** —— 仓库名不符或被门禁）。
> ⇒ 故"GLM-5.3 **无匹配键**"的严格表述是：**registry 里没有以 `glm5` / `glm5next` 命名的实现**；而它**是否复用既有的 `Glm4MoeForCausalLM` 标识**——**未取证**。`glm5next` 是 **GGUF 侧**的架构名（llama.cpp 移植引入），**未必等于** HF 的 `architectures`。
> ⇒ **不得据此断言"vLLM 装不了 GLM-5.3"。**

### 7. 对"是否升级 vLLM"的结论

> ★ **本节只对 0.25.2 → 0.27.0 的跨度成立**；**§8 已证明该跨度之后的 0.29.0 有实质增量（GLM-5.3 / Qwen4exp）** ⇒ 本表**不作为"不必升级"的依据**。

| 结论 | 依据 |
|---|---|
| **就支持度而言，升到 0.27.0 对 GLM/DeepSeek 零收益** | §6：两类键**逐项未变** |
| **就 DeepSeek 而言也无需升** | 现装 `0.25.2.dev0` 已有 `DeepseekV4ForCausalLM` + `models/deepseek_v4/amd/` + `deepseek_mtp`，与 0.27.0 等同 |
| **升级的真实增量只在别家** | §6：新增 `inkling` / `kimi_k3` 原生子包与对应 MTP —— **本仓无这两族的权重** |
| ⇒ **不因 GLM/DeepSeek 升级** | 触发条件收敛为：出现**本仓实际持有**且**现装不支持**的架构，或前两条 §6 判据出现变化 |

### 8. ★★ 上游 **v0.29.0** 复核（**推翻本 ADR §1 / §6 的支持度结论**）

> **缘起**：用户指出"vLLM 已将 **GLM-5.3-Flash** 纳入支持（**Experimental**；需 **vLLM 0.29.0+**；官方建议走镜像 `vllm/vllm-openai:glm53-flash`；依赖 **FlashInfer ≥ 0.6.17** 以支其 **NoPE 稀疏 MLA**）"。⇒ 本 ADR 此前**只查到 0.27.0**，复核 0.29.0（**E1：读该 tag 源码**）。

| 判据 @**v0.29.0** | 结果 | 相对 0.25.2 / 0.27.0 |
|---|---|---|
| ★ **`GlmMoeDsaForCausalLM`** | 实现位置**由 `("deepseek_v2", …)` 上提为 `("vllm.models.deepseek_v32", …)`** | **实质性变化** |
| GLM 其余键 | `Glm` / `Glm4` / `Glm4Moe` / `Glm4MoeLite`（+ VLM/ASR/OCR） | 未变 |
| ★ **`vllm/models/` 子包** | 新增 **`qwen4_exp`** · `hy_v4` · `dots3_note` | **`qwen4_exp` 正对应 Qwen3.8-Flash-Next 的 GGUF arch `qwen4exp`** |
| MiniMax | `MiniMaxM2ForCausalLM` → `minimax_m2`（另有 `MiniMaxM3MTP` 等） | **未变 —— M2.7 一直在支持面内，与 A4 实测一致（用户所述正确）** |
| 上游最新 tag | **v0.30.0**（另有 `v0.31.0rc1`） | 我此前只查到 0.27.0 |

**⇒ 三条自我更正：**
1. ✗ **"GLM-5.3-Flash 无匹配键"不成立。** 其架构很可能就是 **`GlmMoeDsaForCausalLM`**（GLM-MoE + **DSA 稀疏注意力**），而该键**在 0.25.2/0.27.0 就已存在**（只是实现挂在 `deepseek_v2`）。**§1 的方法论错误**：我把 **GGUF 侧的架构名** `glm5next` 当成 **HF 侧 `architectures` 键名**去比对 —— 而 §6 自己的"未取证项警告"恰恰指出了这一点，**我却仍把结论写满了**。
2. ✗ **"升级不解锁 GLM-5.3"的版本上界写错。** 该判断只覆盖到 0.27.0；**0.29.0 起 GLM-5.3-Flash 已进入支持面（Experimental）**。
3. ✗ **"Qwen3.8-Flash-Next 无匹配键"同样被推翻** —— `vllm/models/qwen4_exp` 自 0.29.0 起存在。

**⚠ 但"vLLM 支持 GLM-5.3" ≠ "本集群能跑 GLM-5.3" —— 新增两道未核门（E3，本轮未验证）：**
- **FlashInfer ≥ 0.6.17 是 CUDA 侧的依赖**（NoPE 稀疏 MLA 路径）—— **gfx1151 / ROCm 上是否存在该 kernel，未核**；本仓 `~/vllm-rocm` 亦**未确认**含 FlashInfer。
- 官方推荐的 `vllm/vllm-openai:glm53-flash` 是 **CUDA 镜像**，其对 ROCm 的意义**未核**。
- 且**渠道仍卡**：lemonade 的 gfx1151 档仍停在 `0.25.2.dev0`（§5），要吃到 0.29.0 需**换渠道或自建**。

### 9. ★ 本 build 的 **GLM-5.3 落地可行性**取证（E1：实读站上 `~/vllm-rocm`）

| 判据 | 结果 | 判读 |
|---|---|---|
| 本 build 是否已有 GLM-5.3 实现 | ✅ **有** —— `model_executor/models/deepseek_v2.py:1914` 即 `class GlmMoeDsaForCausalLM(DeepseekV2ForCausalLM)`；registry `:116` 同键 | ★★ **§1 的"无匹配键"在本 build 层面也不成立** —— 我此前只 grep 了**含 "glm" 字样**的键名，**漏掉了 `GlmMoeDsa`** 这个不含 `glm5` 的键 |
| 稀疏 MLA 依赖链 | `layers/sparse_attn_indexer.py`（`SparseAttnIndexer` / `fused_indexer_q_rope_quant`）· `v1/attention/backends/mla/indexer.py`（`DeepseekV32IndexerBackend`）· `layers/mla.py`（`MultiHeadLatentAttentionWrapper`） | GLM-5.3 的 **NoPE 稀疏 MLA** 组件在本 build **齐全** |
| **FlashInfer**（题目所述硬依赖 ≥0.6.17） | ❌ **site-packages 内无 `flashinfer`** —— 只有 `vllm/utils/flashinfer.py` 这个**兼容封装**（其 `has_flashinfer()` 会返回 False） | ★ **本 build 缺该依赖**；若 NoPE 稀疏 MLA 的 fast path 硬绑它，则**现装跑不了那条路径** |
| MLA 的 ROCm 路径 | ✅ `v1/attention/backends/mla/aiter_triton_mla.py` · `mla/sparse_swa.py`；另有 `rocm_aiter_fa.py` / `rocm_attn.py` | **MLA 在 ROCm 上有 AITER / Triton 路径**，并非纯 CUDA |
| `models/deepseek_v32/` 子包 | ⚠ 仅 `__init__.py` + **`nvidia/`** —— **无 `amd/`** | 0.29.0 把 `GlmMoeDsa` 上提到该子包后，**其 AMD 实现是否补齐未核**（本 build 的 `GlmMoeDsa` 走 `deepseek_v2`，不受此限） |
| 本 build 的加速栈 | `flash_attn 2.8.3` · `triton 3.8.0+…rocm7.15.0a20260724` · `conch_triton_kernels 1.2.1` | 确认是 **ROCm 版** |

**⇒ 修正后的判定（第三版，逐次收紧）**：
1. ✗ **"GLM-5.3 在本 build 无实现"仍是错的** —— 实现类就在 `deepseek_v2.py`，**与 §8 的方向一致**。
2. ~~✅ **唯一已确证的硬缺口 = FlashInfer 缺失**（题目依赖 ≥0.6.17，本 build 无此包）。~~ ← **⚠ 此项已被 §10 收回**（FlashInfer 是 CUDA 配方要求，对 ROCm 路径非前置）。
3. ⚠ **权重格式仍是第一道门**（本仓四份全 GGUF；vLLM 侧需 HF/AWQ 系）。
4. ⚠ **"能不能起"必跑才算** —— 本节只做到**依赖面取证**，**未加载过任何 GLM-5.3 权重**。

### 10. **FlashInfer 在 ROCm 的可得性**（方案 B 结论：E1 源码 + E3 文档）

**内 —— 本 build 源码：`flashinfer` 对 GLM-5.3 **不是**硬依赖**

| 证据 | 内容 |
|---|---|
| **平行的 ROCm 后端就在** | `v1/attention/backends/mla/` 下**同时**有 `flashinfer_mla_sparse.py` / `flashinfer_mla_sparse_sm120.py` **与** `rocm_aiter_mla.py` / **`rocm_aiter_mla_sparse.py`** / `aiter_triton_mla.py` / `triton_mla.py` |
| indexer 显式带 ROCm 分支 | `mla/indexer.py:127` `return [1, 64] if current_platform.is_rocm() else [64]`；`sparse_attn_indexer.py:743` `elif current_platform.is_rocm():` |
| ROCm 专属 metadata builder 已在包内 | `mla/sparse_swa.py:124-129` → `from vllm.models.deepseek_v4.amd.rocm import DeepseekV4ROCMAiterSparseSWAMetadataBuilder` |
| ★ **`has_flashinfer()` 每个调用点都带 NVIDIA capability 门** | `kernel_warmup.py:94`（cap **90** = Hopper）· `flashinfer_sparse_mla_warmup.py:97`（**family 120** = Blackwell）· `trtllm_mxfp4_moe.py:87`（`is_cuda()`）· `kernels/linear/{scaled_mm,nvfp4}/flashinfer.py` ⇒ **无一处是 ROCm 必需** |
| ROCm 侧的算子来源 = **AITER + Triton** | `sparse_attn_indexer.py:9` `from vllm._aiter_ops import rocm_aiter_ops`；全程 Triton kernel（`triton 3.8.0+…rocm7.15.0a20260724`） |

**外 —— E3：想把 CUDA 配方照搬到 gfx1151，没有现成路**

| 项 | 事实 |
|---|---|
| ROCm 侧确有 FlashInfer | ✅ ROCm 文档有专门安装页（`rocm/flashinfer` 镜像 · `pip install amd-flashinfer --index-url https://pypi.amd.com/simple`） |
| ★ **但官方支持平台只列 Instinct** | **MI300X / MI325X / MI355X** —— **不含 gfx1151 / Strix Halo / Radeon** |
| ★ **ROCm 侧版本落后** | 官方页当前 **FlashInfer 0.5.3**；题目要求 **≥ 0.6.17** |
| 依赖源不同 | ROCm 版 FlashInfer 需 **AMD AITER** + 特定组合（ROCm 7.0.2/7.2.0 + py3.12 + torch2.9.1），与本仓便携栈（ROCm 用户态 7.15 + py3.14 + torch2.12）**不同源** |

**⇒ 方案 B 结论（三条）**
1. ⚠ **收回 §9 的判定**："**唯一已确证的硬缺口 = FlashInfer 缺失**"**不成立** —— 该依赖是**上游 CUDA 配方**的要求；在本 build 的 **ROCm 路径上不构成前置**（有 AITER/Triton 平行实现，`has_flashinfer()` 全带 NVIDIA 门）。
2. ★ **障碍换了位置**：不是"缺一个包"，而是 —— **不存在任何已验证的 gfx1151 路径**（官方 FlashInfer-ROCm 只覆盖 Instinct，且版本 0.5.3 < 所需的 0.6.17）。
3. ⇒ **方案 A（补 FlashInfer 后实跑）性价比低**：它**不会**因为装上 `flashinfer` 就通；需要**自行打通并调试 AITER 稀疏 MLA 路径**，已超出"补依赖"的范围；**且须先过权重格式那道门**（本仓四份全 GGUF）。

> **对 A4 的含义**：GLM-5.3 走 vLLM 的现状 = 「**架构有实现 · 依赖有 ROCm 替代 · 但无已验证路径**」。要判可行性**只能实起一次**，成本显著高于此前估计。

### 11. **MiniMax-M3 专项**：vLLM vs llama.cpp RPC（2026-09-29）

> **本节的两半性质不同**：vLLM 半 = **本 ADR 射程内**；llama.cpp RPC 半 = **对照**（回答"另一条路能不能跑 M3"），**不改变本 ADR 的范围声明**。

#### 11.1 模型本身（E3）
~**428B** total / ~**23B** active MoE · 128 专家（4 激活）· 60 层 · **1M 上下文** · **MSA（MiniMax Sparse Attention）** · 多模态（text/image/video）。GGUF（unsloth）现成档：**UD-IQ3_XXS ≈ 159 GB** · **UD-IQ4_XS ≈ 194 GiB** · 最小 4-bit ≈ 208 GB。

#### 11.2 vLLM 侧（E1：本 build 实读）—— ★ **四轴全齐**

| 轴 | 结果 |
|---|---|
| 架构键 | ✅ `MiniMaxM3SparseForCausalLM` · `MiniMaxM3SparseForConditionalGeneration`（多模态） |
| **AMD 原生** | ✅ **`models/minimax_m3/amd/`** —— `model.py` · **`mtp.py`** · `ops/` |
| NVIDIA | ✅ `.../nvidia/` —— `model.py` · `indexer_msa.py` · `sparse_attention_msa.py` · `mtp.py` |
| **MTP** | ✅ **`MiniMaxM3MTP` → `vllm.models.minimax_m3`**；**nvidia/ 与 amd/ 各一份 `mtp.py`** |
| 共同结构 | `common/` —— `indexer.py` · `sparse_attention.py` · `vision_tower.py` · `ops/` |

> ⇒ **M3 是本 ADR 调研过的四族里支持面最完整的一个**（比 DeepSeek-V4 还多"**AMD 侧 MTP 实现**"这一项）。⚠ 但**同样受"本 build 零 GGUF 支持"约束** ⇒ 用 vLLM 跑 M3 需 **HF 系权重**，unsloth 的 M3 **GGUF 不可用**。

#### 11.3 llama.cpp RPC 侧（E1 站上实测 + E3 上游）

| 项 | 结果 |
|---|---|
| **本仓现装支持吗** | ❌ **不支持** —— `/opt/llama.cpp/llama-server` 内 **grep 不到任何 `minimax` 架构串**；版本 `0.4.0-dev (build 1533, commit 91f6a6cf)` |
| 上游时间线（E3） | **#24523** = preliminary M3（未进发行版，须自建）→ **#24908（2026-07-26 合并）= 正式 MSA 支持** → **#25113（同日）= vision tower**，且 **tensor 改名 `merge`→`merger` ⇒ 旧 M3 GGUF 必须重新生成** |
| ⇒ 本仓缺口 | commit `91f6a6cf` **早于 7-26** ⇒ **不含 #24908** ⇒ 要支持须**升到含该 PR 的版本**（并保留 `-DGGML_RPC=ON`） |
| **MSA 的硬要求** | ★ **必须开 Flash Attention**（直接调 `ggml_flash_attn_ext`）；FA 关 ⇒ 回退 dense，而 PR 明言 **dense = out-of-distribution、降质**；`--kv-unified + -np>1` 亦回退 dense；**不支持** context shifting 与 partial `seq_rm`；**量化 KV 类型未验证**（仅 F16/BF16） |
| MSA 的收益 | decode 注意力**不再随上下文增长**（上游实测 7.7 tok/s @5k → **7.67 @62k**，基本持平） |
| **社区实测速度**（E3，**非本集群实测**） | 2× DGX Spark（**CUDA**）：**decode ≈ 10.7 tok/s** · prefill ≈ 590 tok/s @`--ubatch-size 2048`（8k prompt）· 首载 13–25 min |

#### 11.4 ★ **MTP 在两条路径上的处境**（回答"是否支持 MTP 等加速"）

| 引擎 | M3 自带 MTP 头是否可用 |
|---|---|
| **vLLM** | ✅ **可用** —— `MiniMaxM3MTP` 已注册，**且 AMD 侧有 `amd/mtp.py`**（四族里唯一） |
| **llama.cpp** | ❌ **未见利用路径** —— 上游 M3 的 PR/文档**未提及 M3 的 MTP**；本仓二进制内 `mtp` 串**零命中**；llama.cpp 的投机解码是**通用机制**（draft model / ngram），**不与模型自带 MTP 头对接** |

⇒ **加速面结论：M3 的 MTP 只在 vLLM 侧吃得到；llama.cpp 侧只能用通用投机解码，对 MoE 大盘收益有限。**

#### 11.5 本集群可行性（三条新门，**均未核**）

1. **体积门**：最小可用档 **UD-IQ3_XXS ≈ 159 GB** > 单站 124 GiB ⇒ **必须多机 RPC**（2 站 248 GiB 可容 194 GiB 档）⇒ 回到"串行跨链税"老问题。
2. **后端门（★ 最不确定）**：MSA 走 `ggml_flash_attn_ext` + 自有 indexer；社区实测**全在 CUDA**，本集群是 **Vulkan/ROCm** ⇒ **Vulkan 后端是否有 MSA 的 flash-attn 路径与其 indexer 算子，未核**。
3. **FA 门**：MSA 要求 FA 开 —— 与在役 `-fa on` 不冲突，但需与 RPC 层切分组合验证。

#### 11.6 结论

| 路径 | 支持度 | 拦路 |
|---|---|---|
| **vLLM** | ★ **四轴最完整**（架构 + **AMD 原生** + **MTP** + 多模态） | 权重格式（本 build 零 GGUF）+ 渠道停在 0.25.2 |
| **llama.cpp RPC** | ❌ **现装不支持**；上游 7-26 起支持 | 需升版 + **MSA 的 FA/Vulkan 未核** + 体积需多机 + **MTP 不可用** |
| **实测速度** | **本集群无实测**（无权重、现装不支持）；社区 CUDA 双机 ≈ **10.7 tok/s** | — |

### 12. ★★ **本集群 vLLM 跑 M3 的可行性判定**（2026-09-29，E1 实读 + 算术）

> 本节回答"本机群是否具备 vLLM 跑 M3 的可行性"，把 §11 的"四条门"逐条落到**已确证 / 未核**。

#### 12.1 ★ 正面新证据：M3 的 ROCm 是**一等路径**（这是与 GLM-5.3 的根本差别）

| 证据（E1，实读 `vllm/models/minimax_m3/`） | 内容 |
|---|---|
| **`__init__.py` 有真正的平台分派** | `if TYPE_CHECKING or not current_platform.is_rocm():` → `nvidia/…` **`else:` → `amd/model.py` + `amd/mtp.py`** ⇒ ROCm 上**走 `amd/` 分支**，非"顺带支持" |
| **AMD 侧有专用 MSA 算子**（补掉了上一轮的疑点） | `amd/ops/` 内：**`index_topk.py`（35 KB）** · **`sparse_attn.py`（10.9 KB）** · `gemma_rmsnorm.py` · `swiglu_oai.py` —— 即 MSA 的 **top-k 块选择 + 稀疏注意力**在 AMD 侧是**独立实现**（并非缺失；它们不在 `nvidia/` 的同名文件里，而在 `ops/` 下） |
| **MLA/indexer 在 ROCm 上走 Triton** | `common/indexer.py:32` `if current_platform.is_rocm():` → `:86 return MiniMaxM3IndexerTritonMetadataBuilder` |
| **MSA 公共实现有 ROCm 分支** | `common/sparse_attention.py:32` `if current_platform.is_rocm():` |
| **AMD 侧接 AITER** | `amd/model.py:28` `from vllm._aiter_ops import rocm_aiter_ops` |
| **AMD 侧 MTP 存在** | `amd/mtp.py`（12.9 KB） |

> ⇒ **M3 是本 ADR 调研过的四族里唯一"ROCm 一等公民"**（对比 [GLM-5.3](#)：`GlmMoeDsa` 挂在通用 `deepseek_v2` 里，**无 AMD 专用算子**；`deepseek_v32` 子包在本 build **只有 `nvidia/`**）。

#### 12.2 逐门判定

| 门 | 判定 | 依据 |
|---|---|---|
| **引擎版本** | ✅ **具备，且不需升版** | 现装 `0.25.2.dev0` **已含 M3 全套**（含 `amd/` 与 `MiniMaxM3MTP`）⇒ 与 GLM-5.3 需换渠道的情形**不同** |
| **架构 / 算子** | ✅ **具备**（E1） | §12.1 六条；平台分派 + AMD 专用 MSA 算子 + Triton indexer + AITER |
| **权重格式** | ❓ **未取证，且是当前唯一可能的硬门** | 本 build **零 GGUF** ⇒ 必须 HF 系（AWQ/GPTQ/FP8/compressed-tensors）；而社区现成档**几乎都是 GGUF**（unsloth 159–194 GB）⇒ **M3 是否存在足够小的 HF 量化档，本轮未取到证据** |
| **体积（算术）** | ⚠ **紧，但非不可能** | M3 428B：BF16 ≈ 856 GB（✗）· **4-bit ≈ 214 GB** · 2-bit ≈ 107 GB。三站 vLLM/ROCm 走 **GTT = 系统内存**，BIOS 0.5 G 后每站 ≈ **124 GB** ⇒ 三站合计 ≈ **372 GB** ⇒ **4-bit 档可容纳（≈71 GB/rank）**，但 KV + 激活另算，余量薄 |
| **TP 通信** | ⚠ **未测** | 60 层 MoE（128 专家）⇒ 每层 all-reduce + 专家通信；**TP=3 over USB4（20G 链路）是否够**，未测 |
| **MTP** | ✅ **可用**（若跑起来） | `MiniMaxM3MTP` + `amd/mtp.py` |

#### 12.3 结论

> **可行性显著高于 GLM-5.3 —— 架构与引擎两门都已在手，卡点从"无已验证路径"换成"缺可用权重"。**

| | M3 | GLM-5.3（对照） |
|---|---|---|
| 引擎版本 | ✅ 现装即有 | ⚠ 需换渠道 / 自建 |
| ROCm 路径 | ✅ **一等路径**（专用算子） | ⚠ 走通用实现，**无 AMD 专用算子** |
| MTP | ✅ AMD 侧有实现 | ❌ |
| **唯一硬门** | **HF 系量化权重是否存在（未取证）** | **无已验证的 gfx1151 路径** |

**⇒ 下一步（若要做）：只需查一件事 —— M3 有没有 4-bit 级的 HF/AWQ/compressed-tensors 档。** 有 ⇒ 三站 TP 实起一次（体积算术已过关）；没有 ⇒ 本集群 vLLM 路线**止步于权重**，与 M3 无关。

#### 12.4 ★ 权重门取证结果（2026-09-29，E1 实取；**方法受限，如实标注**）

**方法**：HF API 在本环境**不可达**（站上直连 `Connection refused`；hf-mirror 的 `/api/` 返 **403**；主控 WebFetch 失败）⇒ 改用 **hf-mirror 的文件路径 HEAD 探测** + **实取官方 `config.json`**。

**① ✅ 官方仓存在，且 HF 架构名与 registry 逐字对上**（本轮最有用的一条）

`MiniMaxAI/MiniMax-M3` → **200**；实取 `config.json`：

```
architectures: ["MiniMaxM3SparseForConditionalGeneration"]   ← 与 registry 键逐字一致
model_type:   minimax_m3_vl          ← 官方是「多模态(VL)」版
text_config:  60 层 · 128 experts(4 激活) · 64 heads / 4 kv · head_dim 128 · vocab 200064
              max_position_embeddings 1048576
              ★ use_gemma_norm: true      ★ hidden_act: "swigluoai"
              rope_theta 5e6 · partial_rotary_factor 0.5
```

> ★★ **这一条同时坐实了 §12.1 的"AMD 一等路径"**：`amd/ops/` 里的 **`gemma_rmsnorm.py`** 正对应 `use_gemma_norm: true`，**`swiglu_oai.py`** 正对应 `hidden_act: "swigluoai"` ⇒ **AMD 算子是按该模型的特有属性写的，不是通用兜底**。

**② ❌ 但没找到 gfx1151 可用的量化档**

| 候选仓 | HTTP | 判读 |
|---|---|---|
| `MiniMaxAI/MiniMax-M3` | **200** | **官方 = safetensors / BF16**（tags 无量化项）⇒ 约 **856 GB** ⇒ 不可行 |
| `nvidia/MiniMax-M3-NVFP4` | **200** | ⚠ NVFP4 = **Blackwell(NVIDIA) 专用**；本 build 的 quantization 白名单内**无 `nvfp4`** ⇒ 对 ROCm 无用 |
| `…-AWQ` / `…-GPTQ` / `…-Int4` / `…-W4A16` / `…-FP8` / `RedHatAI/…-FP8-dynamic` | **404** | 未证实存在 |

> ⚠ **方法盲点（如实记）**：**GGUF 仓没有 `config.json`** ⇒ 该探测法对 `unsloth/MiniMax-M3-GGUF` 也返 404，**而它确实存在**（§11.1 已引）⇒ **"404 = 不存在"对 GGUF 类仓不成立**，对 AWQ/FP8 类仓较可信。**且 HF 搜索 API 不可达 ⇒ 本轮枚举不完整。**

#### 12.5 ★ 最终判定（修正 §12.3）

> **当前不具备可行性 —— 且不是 M3 或 vLLM 的问题，而是"没有 ROCm 可用的 M3 量化权重"。**

| 门 | 终判 |
|---|---|
| 架构 | ✅ **已对上**（`MiniMaxM3SparseForConditionalGeneration` 逐字一致） |
| 引擎版本 | ✅ 现装即有，**不需升版** |
| ROCm 算子 | ✅ **一等路径**（AMD 算子与 `use_gemma_norm` / `swigluoai` 一一对应） |
| MTP | ✅ 可用 |
| **权重** | ❌ **本轮未找到出路** —— 官方 BF16 ≈856 GB；唯一探到的量化档是 NVFP4（NVIDIA 专用）；AWQ/GPTQ/Int8/FP8 类**未证实存在** |
| 体积算术 | ⚠ 4-bit ≈214 GB 可容纳（三站 ≈372 GB）⇒ **只要有权重就成立** |

**⇒ 闸门只剩「权重」这一道，但它是硬闸** —— 与 GLM-5.3 的"无已验证路径"性质不同（那条要改代码/打通算子，这条只等一个档）。⇒ 记为**等外部条件的开放项**：**一旦出现 ROCm 可用的 M3 4-bit HF 档（AWQ / GPTQ / compressed-tensors / W4A16），三站 TP 实起即可**（体积算术与算子面都已过关）。

> ⚠ **本判定的射程**：**受"HF 搜索 API 不可达"限制，本轮枚举不完整** ⇒ **不得外推为"M3 不存在任何量化档"**。

#### 12.6 ★★ 修正 §12.5（用户补入三个候选仓 ⇒ **判定从"不具备"改为"有条件可行"**）

**用户指出的三个仓**（我上一轮枚举漏掉 —— 正是 §12.4 已声明的"**HF 搜索 API 不可达 ⇒ 枚举不完整**"这一射程限制的实例）：

| 候选 | 格式 | 体积 | 本集群适用性（E1 取证） |
|---|---|---|---|
| ★ **`cyankiwi/MiniMax-M3-AWQ-INT4`** | AWQ 4-bit | ★ **258.0 GB**（实取 `model.safetensors.index.json` 的 `total_size` = **258,004,204,864 B**） | **最有希望**（见下） |
| `olka-fi/MiniMax-M3-MXFP4` | MXFP4 4-bit | ~256 GB（**未证实**：镜像 403） | ⚠ 本 build `mxfp4.py` **有 `Mxfp4MoeBackend.AITER_MXFP4_BF16`**（AMD 后端）✓，但该仓与 AMD 路径**均未跑过** |
| `Inferact/MiniMax-M3-EAGLE3-GQA-NVFP4` | NVFP4 | 未明确 | ❌ 本 build 白名单**无 `nvfp4`** + Blackwell 专用 |

**为什么 AWQ-INT4 本集群最有希望：**

1. ★ **AWQ + MoE + ROCm + gfx1151 已由本集群实证** —— A4 的 `MiniMax-M2.7-AWQ-G32-STRIX-2H`（**AWQ 4bit**、MoE）在本集群跑通 **17.60 t/s**；`~/moe-configs/` 现成一份 **`dtype=int4_w4a16` + `device_name=Radeon_8060S_Graphics`** 的 tuned config ⇒ **这条格式链不是猜测，是已走通的**。
2. **本 build 侧 AWQ 无需平台分派** —— `awq_triton.py` 是 Triton 实现（跨平台），MoE 走 `fused_moe` 的 Triton 路径，与 A4 实测一致。
3. ⚠ **附加工作（真实但小）**：A4 的 tuned config 键是 **`E=256,N=768`**；而 M3 的 `config.json`（§12.4 实取）是 **`num_local_experts: 128`** ⇒ 需**为 M3 调一档 `E=128`** 的 config（机制与流程已被 A4 打通）。

**体积再核**：258 GB ÷ 三站（BIOS 0.5 G 后每站 ≈124 GB ⇒ 合计 ≈**372 GB**）= **69%**，余量 ≈114 GB 给 KV + 激活 + 框架开销。
> ⚠ 外部参考盘**更大**：AWQ-INT4 参考用 **8×A100 80GB（640 GB，TP8）**、MXFP4 参考用 **4×RTX PRO 6000（384 GB，TP4）** ⇒ **我们 372 GB 略低于后者的 384 GB** ⇒ **体积是真实风险点，非纸面过关**。

#### 12.7 修正后的终判（取代 §12.5）

> **从"不具备可行性"改为「AWQ 路线有条件可行」** —— 并且**闸门不再只有权重，而是三条可执行条件**：

| 条件 | 状态 |
|---|---|
| ① 权重 | ✅ **有精确候选**：`cyankiwi/MiniMax-M3-AWQ-INT4`，**258.0 GB（E1 实测索引）** |
| ② MoE tuned config | ⚠ **需为 M3 调 `E=128` 一档**（A4 的 `E=256,N=768` 不匹配；流程已通） |
| ③ 三站 TP=3 实起 | ⚠ **未测**（60 层 MoE / 128 专家的 all-reduce 与 all-to-all over USB4） |
| 体积 | ⚠ **69% 占用、余量 ≈114 GB**；外部参考盘更大 ⇒ **真实风险** |

**⇒ 与 A4「暂缓」的关系**：这**不改变** A4（vLLM TP=2 跑 M2.7）的暂缓；但它把 **M3 从"等外部条件"变成"可排期"** —— 触发条件仍是「**有实际需要跑 M3 的场景**」（见「重启条件」节），届时按 ①②③ 走。

> ⚠ **射程**：①②③ **均未实测**；MXFP4 与 NVFP4 两仓**未证实**（镜像 403 / 404）⇒ 本节只裁"**AWQ 候选的可用性与体积算术**"，不外推其它格式。

## 附：C 站 vLLM 栈对齐执行记录（2026-09-29）

**缘起**：本 ADR §背景 实例 4 判定"栈齐备、模型缺失"。当时 C 站**尚无** vLLM 便携栈（A/B 有）⇒ 先把栈补齐，使"重启 A4"的前置只剩**权重**一项。

**方法选择（先取证再动手）**：`~/vllm-rocm` 不是本地构建，而是 **lemonade-sdk 的 GitHub release 两分卷 tar** 解出的便携树（源见 `archive/scripts-history/a4_speedtest_gh.sh`；解压法见站上 `a4_extract.sh`）。比对两站既有树：**A 与 B 只差 1087 个 `.pyc`**（`bin/` `include/` `share/` 逐字节同尺寸；`bin/python3.14` sha256 **同**；`bin/ray` shebang **均已修**；`moe-shim/sitecustomize.py` 与 `moe-configs/*.json` hash **同**）⇒ 两树功能等价 ⇒ **选 B（A4 head）为源整体同步，不重下**（站上 dist 分卷已不在，重下要过 GitHub/mirror）。

| 步骤 | 命令（在 B 上执行） | 结果 |
|---|---|---|
| 建目标目录 | `ssh scott-lau@10.10.11.3 "mkdir -p ~/vllm-rocm ~/moe-shim ~/moe-configs"` | OK |
| 同步栈 | `rsync -aH --numeric-ids -e 'ssh -o BatchMode=yes …' ~/vllm-rocm/ scott-lau@10.10.11.3:~/vllm-rocm/` | **62,699 文件 / 8,350,018,277 B / 20.1 s（407 MB/s）** |
| 同步 moe | 同法 rsync `moe-shim/` + `moe-configs/` | OK |
| 同步 launcher | `rsync -a ~/a4_vllm_launch.sh scott-lau@10.10.11.3:~/` | sha256 `6be7ab4d…` 两侧一致 |

> **为什么走 USB4 而不是 LAN**：B→C 的 **LAN 通道 `Host key verification failed`**（C 的 LAN 主机键未收录在 B），而 **USB4 段 `10.10.11.3` 直接可用**（`BatchMode` rc=0）⇒ 反而更快（407 MB/s）。脚本已持久化在 B：`~/a4_vllm_sync_c.sh`。

**验证（C vs B）**：清单指纹 `22b4706f…` **逐位一致**；文件数 62,699 / 字节 8,350,018,277 同；`bin/python3.14` sha256 `df97dea4…` 同；`bin/ray` shebang 同；`moe-shim` · `moe-configs` hash 同；可执行位保留。

**栈自检（C，带 ROCm 用户态 `LD_LIBRARY_PATH`）**：`Python 3.14.6` · `ray 2.58.0` · **`vllm 0.25.2.dev0+rocm7.15.0a20260724.g752a3a504.d20260724`** · `torch 2.12.0+rocm7.15.0a20260724` · **`cuda_avail True · device_count 1 · dev0 = AMD Radeon 8060S Graphics`**。

> ⚠ **边界（不夸大）**：**栈级**验证（导入 + 设备可见 + 与 B 逐位一致）；**端到端推理未做**（三站皆无 AWQ 权重）⇒ C 站状态 = **「栈就绪，待模型」**。此即下方"长期不用的栈是否腐化"的观察起点。

## 未实测登记（不静默）

1. **A4 数字未复跑** —— 本 ADR 的成绩**全部引自 metrics-log 的历史实测**（2026-08-29），本轮**未复现**（因 AWQ 模型已删）。
2. **C 站参与 TP 的可行性未测** —— 栈前提已具备且 GPU 可见，但 **TP=3 over USB4 的 Gloo/RCCL 行为**与**端到端推理**（需 AWQ 模型）**均未验证**。
3. **8081 常驻形态未做** —— 双路径仍是手工脚本切换，systemd 化**未实施**（属框架调研文档的编排条目）。
4. **MTP / 投机解码从未实测**（v1.1 新增）—— 仅完成**支持面取证**（读站上源码 + 官方文档）；**未跑过任何投机配置** ⇒ `num_speculative_tokens` 取值、实际接受率、AWQ + 投机在 gfx1151/ROCm 上的兼容性**全部未知**。
5. **GLM-5.3-Flash 与 Qwen3.8-Flash-Next 的 HF 侧架构名未取证**（v1.2 新增）—— 「模型支持度专项调研」节是从**本 build registry 的键名**反推"无匹配"，**没有**拿到这两份模型的 `config.json`（本仓只有 GGUF，无 HF 配置）⇒ 结论按 **E1（registry 实读）+ E4（推断）** 记，**非**直接验证。另：`--model-impl transformers` 逃生口**未验证**。

## 修订历史

| 日期 | 变更 |
|------|------|
| 2026-09-29 | 初始版本：从 [DwarfStar 专属量化清退 与 A4 暂缓方案](../docs/research/2026-09-29_DwarfStar专属量化清退方案.md) 剥离 A4 决策面，单独立为 ADR-0011；与 [双机推理服务化与编排框架调研.md](../spec/operator-optimization/research/双机推理服务化与编排框架调研.md) 对齐边界（决策面归本 ADR，正文留原文档）。 |
| 2026-09-29 | **v1.1**：补「MTP / 投机解码专项调研」节（站上 build 内置 MTP **20 族** + 11 种无头方法；**A4 现役 MiniMax-M2.7 无 MTP 头** ⇒ 仍卡重下权重）；「定位」节增列 **decode 侧投机候选**；「背景·触发实例 3」与「状态 = 暂缓」各补一句**射程澄清**（A4b 的证伪只覆盖"削 launch 开销"轴）；「失效条件」增列 **MTP 翻转判据**。 |
| 2026-09-29 | **v1.2**：补「模型支持度专项调研」节（四轴对照：架构键 / AMD 原生 / MTP / 权重格式）—— 站上 build **零 GGUF 支持**、四份现役权重**全部不可直接用**；四轴里**唯一三齐的是 DeepSeek-V4-Flash**，GLM-5.3 与 Qwen3.8-Flash-Next **本 build 无匹配键**；据此把"重下哪份权重"收紧为**有首选**的判断。 |
| 2026-09-29 | **v1.3**：补同节 §5「**版本边界**」—— 三站 build 实查一致（`0.25.2.dev0+…d20260724`）；**经 GitHub API 实查：对 gfx1151，它仍是 lemonade 渠道最新档**，但**上游 vLLM 已到 0.27.x**（ROCm 10.0.0 支持矩阵含 gfx1151）⇒ 补**防外推声明**（"无匹配键"只对 0.25.2 成立）；「重启条件」增列第 4 条、"失效条件"增列对应重审项。 |
| 2026-09-29 | **v2.2**：★ **再次修正**（用户补入三个候选仓）—— 补 §12.6「**修正 §12.5**」+ §12.7「**修正后终判**」：**`cyankiwi/MiniMax-M3-AWQ-INT4` 体积实取 = 258,004,204,864 B（258.0 GB）**；**AWQ+MoE+ROCm+gfx1151 已由 A4 实证**（M2.7-AWQ 跑通 17.60 t/s，且 `~/moe-configs` 有 `int4_w4a16` + `Radeon_8060S` 档）⇒ **终判由"不具备可行性"改为「AWQ 路线有条件可行」**；条件 = ① 258 GB 权重 ② 为 M3 调 `E=128` tuned config（现档是 `E=256,N=768`）③ 三站 TP=3 实起；体积 69% 占用、**低于外部参考档（384 GB TP4）** ⇒ 记为真实风险。 |