# 三节点（A/B/C）分布式开源模型备选调研 · 2026-09

> **调研人**: Scott ｜ **日期**: 2026-09-08（2026-09-09 追加附录 A-G）
> **范围**: A/B/C 三站（各 128G UMA / 124G 可用），llama.cpp Vulkan + RPC 分布式，环网 Thunderbolt ~9.2Gbps
> **四维度**: 深度学术 / 编程任务 / 强推理 / 长上下文
> **2026-09-09 整合**: 文末附录 A-G 吸收原独立三篇调研（M2.7/Q3.8F 量化档位、社区反馈+契合、单/双站模型池），原文档已归档 `.merged.bak.20260909`；分类索引见 `SOURCING-INDEX.md`
> **方法**: 公开榜单（SWE-bench、AA Intelligence Index、AIME/GPQA）+ llama.cpp issue 实测 + 本站资产盘点
> **⚠️ 上游 PR/Issue 状态与引擎基线 = 活数据，权威以 [upstream-tracker/TRACKER.md](../upstream-tracker/TRACKER.md) 为准**——本文档 §6a 中的状态表仅为调研时点快照，勿据此做版本决策

---

## 1. 结论速览（TL;DR）

| 决策 | 结论 |
|---|---|
| **分布式主力（长上下文/学术/强推理）** | **DeepSeek-V4-Flash-0731**（已在库，146G MXFP4）B+C 或 A+C 两站 50/50 分片；需 llama.cpp ≥ 含 dsv4 Vulkan op 的版本 |
| **编程任务专用（单机轻量）** | **Qwen3-Coder-Next**（已在库 Q6 62G）B 站单机，256K ctx，agentic 训练 |
| **轻量日常/多模态** | Qwen3.5-35B-A3B（Q4 ~24G，单机，262K→1M）——待下载候选 |
| **巡顶不可本地** | Kimi K2.6 / GLM-5.2 / DeepSeek-V4-Pro —— 体积超 384G 预算或 RPC 有已知 crash |

---

## 2. 四维度 TOP 开源模型格局（2026-09 时点）

| 维度 | 榜首（开源） | 关键得分 | 体积约束 |
|---|---|---|---|
| 深度学术 | **Kimi K2.6** | GPQA-D 90.5 / AIME'26 96.4 / Math #1 | 1T MoE → INT4 ~500G+，**本地装不下** |
| 编程任务 | **GLM-5.2**（SWE-Pro 62.1, AA 51）｜**DeepSeek V4**（SWE-V 80.6, CF 3206） | SWE-Pro/Verified 开源纪录 | 744B / 1.6T → **本地装不下**（GLM W4A8 ~422G） |
| 强推理 | **Kimi K2.6**（AIME 96.4）｜**DSV4-Pro**（数学/STEM 开源第一） | 同上学分值 | 同上 |
| 长上下文 | **DeepSeek V4 全系**（1M ctx, DSA 稀疏注意力）｜GLM-5.2（1M）｜Qwen3.5（262K→1M） | 1M 原生 + KV 压缩 | **V4-Flash 284B 是唯一 1M 且可分片** |

关键洞察：**四维榜首全是"装不下"的旗舰**；本地集群的实际选择在第二梯队里按体积-质量-许可重新排序。

---

## 3. 候选模型清单与关键参数

| 模型 | 参数量（MoE active） | ctx | 体积（量化） | 许可 | 强项 |
|---|---|---|---|---|---|
| **DeepSeek-V4-Flash** | 284B / 13B | **1M** | MXFP4 146G*；Q4_K_M-XL ~163G；IQ2_XS ~81G | MIT | 长上下文 + 世界知识 + Agent/Coding 平衡 |
| **Qwen3-Coder-Next** | 80B / 3B | 256K | Q6 62G* | Apache-2.0 | agentic 代码（SWE-Pro 44.3, Terminal 40.5），很轻 |
| **Qwen3.5-35B-A3B** | 35B / 3B | **262K→1M** | Q4 ~24G | Apache-2.0 | 多模态 + 线性注意力低成本长ctx |
| gpt-oss-120b | 120B / 12B | 128K | 已在 A 站 | Apache-2.0 | 通用底座（非编程专精） |
| Nemotron-3-Super-120B-A12B | 120B / 12B | 128K | 已在 A/B 站 | NVIDIA | 通用底座 |
| Qwen3.8-Flash-Next | — | 262K | 103G* | — | 现役双机主力，冒烟已过 |
| Qwen3.8-27B-MTP（mmproj 配） | 27B | 8K/32K | 29G | — | C 站现役轻量 |
| GLM-5.2 / 5.3 | 744B/762B MoE ~40B | 1M | W4A8 ~422G；UQ-Q5 ~562G | MIT | 综合开源最强，**本地超预算** |
| Kimi K2.6 / K3 | 1T~2.8T / 32B | 262K / 1M | INT4 500G+ | Modified-MIT | 推理/数学最强，**本地装不下** |
| DeepSeek-V4-Pro | 1.6T / 49B | 1M | W4A8 ~900G | MIT | 世界知识/数学开源第一，**本地装不下** |

`*` = 已在本集群 B 站库存核实（见 §5 资产盘点）。

---

## 4. 分布式加载可行性评估（128G × 3 + RPC）

### 4.1 内存账本（每站 124G 可用）

| 方案 | 权重分布 | 每站权重占用 | 剩余给 KV/engine | 结论 |
|---|---|---|---|---|
| V4-Flash MXFP4 两站分片 | 50/50 | ~68G | ~56G | ✅ 长 ctx 可行（128K+） |
| V4-Flash Q4_K_M-XL 两站分片 | 50/50 | ~82G | ~42G | ✅ | 
| V4-Flash IQ2_XS-XL 单机 | C=A/B 单站 | ~76-81G | ~43G | ✅ 单机 1M 轻级路线（IQ2 质量） |
| Qwen3-Coder-Next 单机 | B 站 | 62G | ~62G | ✅ 富余 |
| Qwen3.5-35B-A3B 单机 | 任一站 | 24G | ~100G | ✅ 最轻 |
| GLM-5.2 / K2.6 / V4-Pro | — | >422G | — | ❌ 超 384G 总预算 |

### 4.2 llama.cpp RPC 已知风险（2026-09 实测/issue）

| Issue | 现象 | 对本集群影响 |
|---|---|---|
| [#28047](https://github.com/ggml-org/llama.cpp/issues/28047)（**09-10 更新：已 Closed 9/5，由 #26500 修复**，见 §6a 表） | **DSV4-Pro 3-worker / GLM-5.3 多 worker 确定性 crash**（分片调度器把 FLAG_COMPUTE view 发错 worker）；DSV4-Flash 多 worker **正常**、gpt-oss 正常 | ✅ 我们选 V4-Flash 恰好避开；⚠️ 旧引擎下勿上 GLM-5.x / V4-Pro 分布式 — **升级引擎(含 #26500)后前置解除，按实测确认** |
| [#26152](https://github.com/ggml-org/llama.cpp/issues/26152) | MoE 部分 offload 时 `GGML_SCHED_MAX_SPLIT_INPUTS` 崩溃 | 大 MoE 全量 offload 到两站时用 `-ot`/层分片规避 |
| Azure 实测（2026-04） | **单机装得下的模型 RPC 反而更慢**（网络开销） | RPC 仅用于超单机模型（V4-Flash）；62G 以下单机直跑 |
| **V4 Vulkan op 关键前置** | dsv4 系列算子（DSA/lightning indexer/超连接）是近期才合入的 | llama.cpp 须升级到含 [#26565 cont-permute](https://github.com/ggml-org/llama.cpp/pull/26585)+[#26578 HC fused](https://github.com/ggml-org/llama.cpp/pull/26578) 的版本；已验证 gfx1151 双机 50/50 分片跑 Flash UD-Q4_K_XL |

---

## 5. 站内资产盘点（已核实 2026-09-08）

- **B 站** `/data/models/gguf/lmstudio-community/`
  - `DeepSeek-V4-Flash-0731-MXFP4.gguf` **146G** ← 分布式主力已就位
  - `Qwen3-Coder-Next-Q6_K-merged.gguf` **62G** ← 编程专用已就位
  - `Qwen3.8-Flash-Next-UD-Q4_K_XL.gguf` **104G**（现役 org/262K）
  - `gpt-oss-120b / gpt-oss-20b / Nemotron-3-Super-120B / Qwen2.5-7B`
- **A 站**：`gpt-oss-120b / Nemotron-3-Super-120B`
- **C 站**：`Qwen3.8-27B-MTP`（29G，现役 18080）
- 磁盘余量：B 905G / A 1.2T 可用（充裕）

---

## 6. 推荐路线

### 主推（零新增下载）
1. **分布式长ctx/学术/推理**：`DeepSeek-V4-Flash-0731`（146G MXFP4）→ B+C 或 A+C 各半层分片，llama.cpp 升级至含 dsv4 Vulkan op 版本，`-ot` 层分片规避 #26152
2. **编程 agent**：`Qwen3-Coder-Next`（62G）→ B 站单机直跑（RPC 反而慢），256K ctx，agentic 代码归它

### 增量下载候选（按需）
3. `Qwen3.5-35B-A3B`（~24G）→ 任意站单机：多模态 + 262K→1M 线性注意力，性价比最高的长 ctx 补充
4. `DeepSeek-V4-Flash` IQ2_XS-XL（~81G）→ 若想单机跑 1M（不进分布式），IQ2 质量自评后决定

### 明确不上
- GLM-5.2/5.3 旗舰、Kimi K2.6、DSV4-Pro：本地装不下（**#28047 RPC crash 已 9/5 修复，升级引擎后可重评估分布式**，见 §4.2/§6a）——巡顶需求走外部 API
- 单机能装的模型不上 RPC（实测变慢）

---

## 6a. 补充调研：GLM-5.3-Flash / Nemotron 3 Ultra（2026-09-08 二轮）

### GLM-5.3-Flash（`zai-org/GLM-5.3-Flash`，320B-A18B）

| 项 | 值 |
|---|---|
| 发布 | 2026-08-27 权重开源（代号 Ox-Alpha「牛来」，OpenRouter 灰度周调用第一） |
| 架构 | 320B total / 18B active，45 层（34 KDA 线性 + 11 MLA），mHC 超连接，IndexPool 索引器 4→1 池化；**首个开源稀疏+线性混合注意力**，KV 缓存较 GLM-5.3 降 4.44× |
| 上下文 / 许可 | **1M** / **MIT**（旗舰 GLM-5.3 非 MIT，勿混） |
| 能力 | AA Index 57（平 Claude Opus 4.8）；原生**多模态**（视觉编码器 24 层，30T token 语料）；价格 Opus ~1/40 |
| GGUF 体积 | UD-IQ1_S 93.1G / IQ1_M 97.6G / **Q2_K_XL 108.7G** / Q3_K_XL 147.5G / Q4_K_XL 199.7G；**mmproj 必须另载 ~1.13G（不载则静默无视觉）** |
| **llama.cpp 支持** | ⚠️ **`glm5next` 架构未合入 master**（2026-09-08 交叉核实）：**3 个独立实现并存且均 Open**——[#27754](https://github.com/ggml-org/llama.cpp/pull/27754)（**danielhanchen/unsloth 官方**，40 commits，文本+视觉，含 MTP 投机解码实测表：16K ctx 55→77.2 t/s）+ [#27752](https://github.com/ggml-org/llama.cpp/pull/27752)（eauchs，10 commits，文本）/ [#27773](https://github.com/ggml-org/llama.cpp/pull/27773)（timkhronos，41 commits，文本+视觉，logits 对齐 HF）；MTP 另在 #27917。**本集群引擎 0d18aaa 无法加载**（unknown architecture） |
| HF/社区反馈 | #27752 作者实测 `UD-IQ1_M + -ngl 99 --cpu-moe` 文本连贯、thinking 正常；#27754 作者（unsloth CEO）自测含 `NVIDIA_TF32_OVERRIDE=0` + `-fa off` 两前置 flag（CUDA 路径）；HN 162 分；社区 DeepSWE 首轮 ~80%；⚠️ `reasoning_effort` 默认 **max**（typo 也 max），成本陷阱 |

**结论**：GLM-5.3-Flash **能力/许可均优（MIT+1M+多模态+AA 57）**，且 Q2_K_XL 108.7G **单站放得下**；但**引擎支持未合入**，现阶段仅两条路径：① API 验证质量（`glm-5.3-flash`）；② 等 #27754/#27752/#27773 任一合入后整树同步（沿用 B 源站 rsync，unsloth 分支已在 git remote 可用）。**暂不落地本地镜像**。

### NVIDIA Nemotron 3 Ultra（`nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B`）

| 项 | 值 |
|---|---|
| 发布 | 2026-06-04，OpenMDW-1.1（开放权重+训练数据+配方，比 MIT 更彻底） |
| 架构 | 550B total / 55B active，LatentMoE：Mamba-2 层 ∥ MoE ∥ attention 混合（108 层），MTP 投机解码，NVFP4 预训练 |
| 上下文 / 吞吐 | **1M**，官方称同类开源吞吐高 ~6×（Mamba 剪 KV） |
| 能力 | GPQA 87 / MMLU-Pro 86.8 / SWE-V 71.9 / LCB v6 89.0 / RULER-1M 94.7 / AA 47.7 |
| 体积 | NVFP4 ~275G（需 TRT-LLM/vLLM 系，**llama.cpp 不吃原生 NVFP4**）；BF16 ~1.1-1.7T；GGUF 社区 Q4_K ~472G / UD-IQ 1-bit ~189G |
| 本集群可行性 | ❌ **不现实**：Q4 472G 超 372G 预算；UD-IQ1 189G 三站可分但质量损失大且 Mamba/LatentMoE 走 GGUF 支持同 V4 一样依赖新 master。**留 API**（build.nvidia.com 有免费层） |

**对照**：站内已有 **Nemotron-3-Super-120B-A12B**（3-11 发布，120B/12B active，同为 **1M ctx** LatentMoE）——这才是本集群能装下的 Nemotron 家族成员（Q4 67G 单站，DGX Spark 128G 实测 19.5 t/s），**建议将其从"库存杂物"提级为 1M ctx 候选**（A/B 站已有）。

### DS V4 Flash 算子 PR 动态（更新 v0 版 §4.2）

| PR / Release | 内容 | 状态（2026-09-08 fetch 核实） |
|---|---|---|
| **v0.3.0**（8/25） | DS4 tensor-split（`-sm tensor`）、多序列 rollback 修复；⚠️ **注意未含 Vulkan Lightning Indexer**（8/27 才合入，晚于 v0.3.0） | ✅ release |
| [#26585](https://github.com/ggml-org/llama.cpp/pull/26585) | vulkan tiled transpose 0↔2（V4 lightning indexer 瓶颈，~43% prefill → 修复） | ✅ **Merged 8/19** |
| [#26578](https://github.com/ggml-org/llama.cpp/pull/26578) | vulkan DSV4_HC_COMB/PRE/POST 融合算子（原 #26548 closed 后重开） | ✅ **Merged 9/7**（2026-09-10 复核）→ decode 1.50×/prefill 1.12×；现役 /opt(8/31) 缺，升级即得。**状态见 TRACKER §1.2** |
| [#27453](https://github.com/ggml-org/llama.cpp/pull/27453) | **vulkan LIGHTNING_INDEXER**（f32/f16/bf16/q8/q5/q4/iq4_nl；16931/16931 全量通过；live Flash avg_err 3e-10） | ✅ **Merged 8/27** |
| [#28133](https://github.com/ggml-org/llama.cpp/pull/28133) | mtmd 支持 DeepSeek-V4-Flash-Vision-Exp（视觉） | ✅ **Merged 9/2**（文本模型需先 reconvert #28154） |
| [#28047](https://github.com/ggml-org/llama.cpp/issues/28047) | V4-Pro/GLM-5.3 多 worker RPC crash | ✅ **Closed 9/5 — 由 [#26500](https://github.com/ggml-org/llama.cpp/pull/26500)（8/30 merged）修复**（2026-09-10 复核）；Pro/GLM-5.3 分布式禁用前置已解除，升级引擎(含 #26500)后实测确认。**状态见 TRACKER §1.2** |

**关键结论（引擎升级解锁）**：✅ **2026-09-10 已升级完成**（master-91f6a6cf v0.4.0-dev，含 #26578 DSV4_HC + sparse-fa），V4-Flash A/B 两机层分布 decode **9.56→14.02 t/s（+46.7%）实测闭环**（metrics-log Phase 6）。升级走 UPGRADE_SOP 三站原子切换，`check_llama_version.py --deep` 全绿。旧 0d18aaa 引擎缺全部算子；现役 /opt 已是 ≥9/7 master → **V4-Flash 可正常加载高速运行**。

---

## 7. 待办（建议后续，按优先级）

- [ ] **P0 llama.cpp 升级**：B 源站 pull 到 ≥ v0.3.0（含 #26585/#26548/#27453/#28133），A/B/C 同 commit 重编（Vulkan + GGML_RPC 参数不动）；升级前 B 站记录当前 0d18aaa 基准（现役 qwen3.8 Q8 + RPC 配置）
- [ ] **P0 V4-Flash-0731 实测**：升级后先用 `-sm tensor` 单站验证 146G 加载 → B+C 两站分片 1M ctx 冒烟（参考 model-eval 冒烟口径）
- [ ] P1 Nemotron-3-Super-120B 提级为 1M ctx 候选并准入评测（A/B 已有，零下载）
- [ ] P2 GLM-5.3-Flash：API 层先验证质量；`glm5next` 合入 master 后评估落地（Q2_K_XL 108.7G 单站候选）
- [ ] P3 与 opencode limit.context 一致性：V4-Flash 1M ctx 时 catalog 上限同步（对齐 D-18）

---

## 8. 佐证来源

- [AIWiki Best Open-Source LLMs](https://aiwiki.ai/wiki/best_open_source_llms)（AA Index 51 / SWE-V 80.6 / 各维度冠军，2026-07 核）
- [DeepSeek 官方发布页](https://api-docs.deepseek.com/zh-cn/news/news260424/)（V4 1M ctx / DSA / Flash 284B-13B MIT）
- [DevelopersDigest GLM-5.2 vs V4 vs Qwen3](https://www.developersdigest.tech/blog/glm-5-2-vs-deepseek-v4-vs-qwen3-open-weights-coding-showdown)（SWE-Pro 62.1 / 81.0 / 88.3）
- [llama.cpp #28047](https://github.com/ggml-org/llama.cpp/issues/28047)（DSV4-Pro/GLM-5.3 RPC crash 实测表；Flash 多 worker OK）
- [llama.cpp #26585](https://github.com/ggml-org/llama.cpp/pull/26585)（gfx1151 双机跑 V4-Flash UD-Q4_K_XL 数据点）
- [llama.cpp #27453](https://github.com/ggml-org/llama.cpp/pull/27453)（vulkan LIGHTNING_INDEXER merged 8/27）
- [llama.cpp #27752/#27773](https://github.com/ggml-org/llama.cpp/pull/27752)（GLM-5.3-Flash glm5next，未合入）
- [dev.to: Run GLM-5.3 Locally](https://dev.to/purpledoubled/run-glm-53-locally-real-quant-sizes-the-llamacpp-surprise-and-the-reasoningeffort-trap-2nmg)（Flash 93.1G 起、旗舰 stock 可跑、reasoning_effort 陷阱、许可差异）
- [runaihome Nemotron 3 Ultra 硬件指南](https://runaihome.com/blog/nvidia-nemotron-3-ultra-local-ai-hardware-guide-2026/)（NVFP4 275G / UD-IQ 189G / LM 许可）
- [nabe2030: Nemotron-3-Super on DGX Spark](https://github.com/nabe2030/nemotron-3-super-dgx-spark)（Super Q4 67G 128G UMA 实测 19.5 t/s，与本站同构）
- [GitHub gist: V4-Flash on 64G Strix Halo](https://gist.github.com/AlexsJones/9b43e7b8f3682679d17f255a3ca0d9d3)（单机 mmap/专家流式参数铁律）

---

# 附录（2026-09-09 三篇调研合并）

> **整合说明（2026-09-09）**: 本节吸收原独立三篇——`QUANTS-SINGLE-STATION-2026-09-09.md`（M2.7/Q3.8F 量化档位）、`COMMUNITY-FEEDBACK-FIT-2026-09-09.md`（社区反馈+契合）、`SINGLE-DUAL-STATION-POOL-2026-09-09.md`（单/双站模型池）——统一收敛到此主文档；原三篇已归档（`.merged.bak.20260909`）。分类索引见 `SOURCING-INDEX.md`。

## A. MiniMax-M2.7 社区量化盘点（原 QUANTS §2）

### A.1 模型基线
- 229B sparse MoE，**10B active**，256 experts（8 routed），62 层，200K ctx，FP8 原生权重
- 官方开源（HF `MiniMaxAI/MiniMax-M2.7`）；**Modified-MIT 非商用许可**（商用须授权，与 M2/M2.5 的 MIT 不同）
- 社区热点: SWE-Pro 56.22%（对齐 GPT-5.3-Codex）、GDPval-AA ELO 1495、Terminal-Bench 2 57%

### A.2 社区量化档位（HuggingFace）

**Unsloth 系**（`unsloth/MiniMax-M2.7-GGUF`，Dynamic 2.0，22 档，质量与体积最优，M2.5 同架构 750-prompt 基准）：

| 档位 | 体积 | 单站(124G)? | 备注 |
|------|------|-----------|------|
| Q8_0 | ~243G | ❌ | 需 256G 机 |
| UD-Q4_K_XL | ~130G | ❌ 紧超 | 质量最接近原版（-6.0 分）|
| **UD-IQ4_XS** | **~108G** | ✅ **推荐** | 128G 机官方档，15-25 t/s |
| UD-Q3_K_M | ~90-101G | ✅ | 3-bit 保守档 |
| UD-Q2_K_XL / UD-IQ3_S | ~80-90G | ✅ | 96G 设备档，压缩较狠 |
| UD-IQ2_XXS | ~66G | ✅ | 低比特，质量折损大 |

**非 Unsloth 系**（`Youssofal/MiniMax-M2.7-GGUF` 等，imatrix）：

| 档位 | 体积 | 单站(124G)? | 备注 |
|------|------|-----------|------|
| Q8_0 / Q6_K / Q5_K_M | 243G / 188G / 162G | ❌ | — |
| Q4_K_M / Q4_K_S | ~138G / ~130G | ❌ | 超 124G |
| IQ4_XS | ~122G | ⚠️ 边界 | 余量极小 |
| Q3_K_L / Q3_K_M | ~118G / ~109G | ⚠️ / ✅ | Q3_K_M 可但质量一般 |
| Q2_K | ~83G | ✅ | 极低质量 "surprisingly usable" |

### A.3 单站可行性评估
- **推荐 `UD-IQ4_XS` ~108G**：128G 机设计档，留 ~14G 给 KV+引擎，与 gpt-oss/nemotron 先例同量级
- **次选 `UD-Q3_K_M` ~90-101G**：更保守内存，无 NVIDIA 限制（CUDA 13.2 NaN bug 不涉本集群 Vulkan）
- ⚠️ **避免**非 Unsloth Q4/Q5（超 124G）+ **blk.61 ffn_down_exps NaN bug**（须 unsloth fixed 档）

## B. Qwen3.8-Flash-Next 社区量化盘点（原 QUANTS §3）

### B.1 模型基线
- **125B MoE，6B active**，512 experts（10 routed +1 shared），48 层，**262K ctx 原生（可 1M）**
- 复合: 125B 主干 + **51B N-gram 嵌入表**（可 offload system RAM）+ 4B MTP 预测头
- 多模态（mmproj 视觉）；FP8 原生 172.78 GiB；llama.cpp 已合入支持（PR #27742，8-27 merged，架构 qwen4exp）

### B.2 社区量化档位

**Unsloth 系**（官方首推）：

| 档位 | 体积 | 运行 RAM | 单站(124G)? |
|------|------|---------|-----------|
| UD-IQ4_XS | ~93.7G | ~112G | ✅ 推荐（留 ~12G）|
| UD-Q3_K_XL | ~90G | ~90G+ | ✅ |
| **UD-Q2_K_XL** | **~78.9G** | **~79G** | ✅ 最稳（社区默认）|
| UD-IQ1_S | ~72.5G | ~75G | ✅（1-bit，大幅折损）|

**非 Unsloth 系**（`bartowski` imatrix）：Q8_0/Q6_K/Q5_K_M ❌；Q4_K_M ~119.6G ⚠️边界；Q4_K_S ~113G ✅；Q2_K_L ~107G ✅；IQ4_XS ~97.7G ✅；Q3_K_L/IQ3_M ~93G ✅；Q2_K ~81G ✅；IQ2_XS/IQ1_M ❌低质量

**本地现况**：B 站已有 `qwen3.8-flash-next`（UD-Q4_K_XL ~111G 已下载，RPC 分布式走）；111G 超单站预算 → 单站需换 UD-IQ4_XS/UD-Q2_K_XL 档。

## C. 性能与质量损失对比（原 QUANTS §4，社区实测）

### C.1 MiniMax-M2.7
| 档位 | 质量信号 | 吞吐实测 |
|------|---------|---------|
| UD-Q4_K_XL (~130G) | **-6.0 分 / 错误 +22.8%**（性价比最高）| — |
| **UD-IQ4_XS (~108G)** | Q4 系 ≈64.5-64.9% acc / 错误 +33-35% | Apple 128G **15+ t/s**；Thor T5000 17 t/s |
| IQ3_XXS (82G, Ollama) | — | M4 Max **22.1/36.7 t/s**（短/长），VRAM 104G |
| UD-IQ1_M (~61G) | ❌ 质量崩塌（1-bit 断崖）| 最快但不可用 |

**规律**：1-bit 断崖（IQ1_M）→ 2-bit 下限 → 3-bit 拐点 → 4-bit 甜点；Unsloth 动态全面优于同体积传统量化（小 ~8G 更准）。

### C.2 Qwen3.8-Flash-Next
| 档位 | 质量信号 | 吞吐实测 |
|------|---------|---------|
| UD-Q4_K_XL (~111G) | **MTP on 138.8 vs off 83.2 t/s（+67%）零损失** | B200 单卡 |
| **UD-IQ4_XS (~93.7G)** | 高质量（≈Q4 级）| llama.cpp mmap **12 t/s** decode（128G DDR5）|
| UD-Q2_K_XL (~78.9G) | MMLU ~70.8%（2-bit 可用下限）| 10-12 t/s |
| UD-IQ1_S (~72.5G) | ❌ 1-bit（GPQA/MMLU 断崖）| MTP+34%（但质量崩）|

**MTP 关键**：q4exp 内置 MTP 头 → **零质量损失 +34~67%**；⚠️ 主控线 llama.cpp 0eadefebd **尚无 MTP graph**（须 unsloth 分支 b10715+ 或自编）

**选档铁律**：4-bit 与 BF16 几乎无可见差异（TB2.1/GPQA）；2-bit 开始明显；1-bit 断崖；**按任务基准（TB2/GPQA）而非 PPL 选档**。

### C.3 与本集群锚点对照
- gpt-oss-120b 50 t/s（HIP 实测）、nemotron-120B 19.5 t/s（DGX 报告）
- q3.8f 6B-active 预期单站 encode 10-15 t/s；M2.7 10B-active 略低
- Strix Halo `--load-mode mmap` 模型页可回收（社区: 93.7G 文件仅占 21-32G RAM）→ 124G 预算实际更宽裕（需实测确认）

## D. M2.7 与 Q3.8F：社区反馈 + 用户场景契合（原 COMMUNITY-FEEDBACK）

### D.1 社区反馈
**M2.7**：✅ agent 编排最强（Hermes 最佳组合）、重构/狩猎强（KiloCode 全找到且一处优于 Opus）、性价比（90% Opus 质量 / 7% 成本）、2-node 41.5 t/s；❌ **长文写作惰性**、架构思维 < Opus、SWE-bench Verified 78% < M2.5 80.2%、**Modified-MIT 商用雷区**、eval 3.3× 推理放大、NaN/非 unsloth 坑。

**Q3.8F**：✅ 写作/办公强（JobBench 55.7 vs Opus 36.6）、agent-coded 全（SWE-Pro 62.5/CoWorkBench 73.9）、**DGX Spark 同类硬件 43 t/s**、原生多模态、Vulkan 8-27 已合；❌ **默认 xhigh 过度思考**（单题 21min/20k token）、4-bit 以下代码易 bug、MTP 提速不及预期、前端过度设计、许可 qwen-community-1.0（较 Apache2 收紧）。

### D.2 任务-模型契合矩阵
| 用户任务 | M2.7 | Q3.8F | 选型 |
|---------|------|-------|------|
| agent wrapper/工具编码 | ✅ 强 | ✅ 强 | 平手 |
| 论文/文档/调研写作 | ⚠️ 惰性 | ✅ 强 | **Q3.8F** |
| 敏感 local-only | ✅ | ✅ | 平手 |
| 长任务（DCP+记忆 ≥128K）| ⚠️ 推理放大 | ✅ 262K+降思考 | **Q3.8F** |
| spec/审计文档 | ⚠️ | ✅ | **Q3.8F** |
| research 综述 | ⚠️ | ✅ | **Q3.8F** |

### D.3 综合建议
> **Qwen3.8-Flash-Next = 单站首选**（写作/研究/上下文/单站预算/许可五维全面占优）
> **MiniMax-M2.7 = 编码补位备选**（不首发；重编码需求强烈且接受许可/惰性代价时启用）
> 均满足 local-only 铁律；均建议 ≥4-bit 档；加载守 load-gate 单模型纪律。

### D.4 落地对策
| 社区坑 | 本集群对策 |
|--------|-----------|
| Q3.8F xhigh 烧 ctx | `reasoning_effort=low/medium`（对齐 6.4 profile）|
| Q3.8F <4-bit 代码 bug | UD-IQ4_XS/Q2_K_XL ≥4-bit + golden 兜底 |
| M2.7 非 unsloth NaN | 只用 unsloth 档 + wtf token 冒烟 |
| M2.7 推理过长 | 200K 内 + DCP |
| 双模型并存 | load-gate 禁同站叠加，错峰 A/C |

### D.5 C 站双后端实测 + 社区证据（2026-09-10）

> 用户 C 站 LM Studio 加载 Qwen3.8-Flash-Next **UD-IQ4_XS**（已下载 93.7G 三片）实测两后端，一可用一异常，社区均有对应 issue。**结论先行：LM Studio 内置引擎下 Vulkan 为 C 站 Q3.8F 主力后端，其 ROCm 后端不可用（gfx1151 MoE 数值损坏）；思考冗长 = 默认 `reasoning_effort=xhigh` 所致，须显式调 medium/low。⚠️ 本结论限 LM Studio 内置引擎——切换到 unsloth b10715 HIP 后 Q3.8F 实测正常，见 D.6（引擎级对照）。**

**现象 1：Vulkan 可用，tg 18.85 t/s，但思考冗长**
- 实测：加载成功（`n_ctx_slot=217856`），decode 18.85 t/s 可用；但"解释 frechet 可微"思考接近 **6 分钟**（远慢于生成速度）
- 根因（社区实证）：Qwen3.8 全系**默认 `reasoning_effort=xhigh`**（GGUF chat_template 内建），xhigh 疯狂过度思考：
  - [QwenLM/Qwen3.8#216](https://github.com/QwenLM/Qwen3.8/issues/216)：xhigh 默认下 **~19.4% 空回答**（烧几千-2.6万 reasoning token 后 `finish_reason=stop` 无 content）；`reasoning_effort=medium/low` 零失败
  - [insiderllm 实测](https://insiderllm.com/pdfs/qwen-3-8-27b-reasoning-token-cost.pdf)：HumanEval#108 烧 **3.2 万 token / 14.2 分钟** 未作答（decode 正常 37.2 t/s，是"生成过多"非慢）
  - Simon Willison 实测：画 SVG 用 21 分钟 / 2.2 万推理 token；**建议 initial 用 low 或关推理**
  - **⚠️ LM Studio 坑（#216 明确）**：LM Studio **静默丢弃 `reasoning_effort` 参数** → 界面设了也无效，仍发 xhigh
- **对策**：C 站 LM Studio 需在模型配置/引擎参数层固定 `reasoning_effort=medium` + `--reasoning-budget`（如 4000）+ `--reasoning-preserve`（ryan4yin gist 实测：medium+budget 4000 是 Q3.8-Flash-Next 最优，xhigh 质量还退化自疑循环）；llama.cpp 命令行加 `--chat-template-kwargs '{"reasoning_effort":"medium"}'`

**现象 2：切换 ROCm 后端输出全"？？？？？"但 tg 略快**
- 实测：ROCm/HIP 后端 tg 显示略快但输出全问号（乱码/数值损坏）
- 根因（社区实证，gfx1151 HIP MoE 数值 bug 家族）：
  - [llama.cpp#28113](https://github.com/ggml-org/llama.cpp/issues/28113)（8/31）：**MoE 模型在 gfx1151 HIP 输出重复标点垃圾**（`///////…`），tg 正常 41 t/s 但采样全垃圾 —— 与"tg 略快但输出乱码"完全同型；由 #27621（`ggml_cuda_should_fuse_mul_mat_vec_q` 条件改）引入，`mul_mat_vec_q_moe` 多 token 融合路径数值错误
  - [llama.cpp#27579](https://github.com/ggml-org/llama.cpp/issues/27579)（8/22）：gfx1151 HIP 稠密架构退化 word salad（Vulkan 同参全对）
  - [llama.cpp#28211](https://github.com/ggml-org/llama.cpp/issues/28211)（9/1）：HIP gfx1151 长 prompt > n_ubatch 错误 logits（无报错）
  - [llama.cpp#17797](https://github.com/ggml-org/llama.cpp/issues/17797)：ROCm gfx1151 输出 gibberish，Vulkan 正常（历史）
  - **关键**：Qwen3.8-Flash-Next 是 512-expert MoE（qwen4exp）→ 命中 #28113 的 MoE HIP 数值路径；**C 站 LM Studio 自带 ROCm 引擎可能含 #27621 回归或独立 HIP bug**
- **对策**：C 站 Q3.8F **用 Vulkan 后端**（18.85 t/s 可用且输出正确）；HIP 仅作对照，等 #28113 修复（gfx1151 MoE HIP 数值）再评估；本集群 /opt 引擎为 Vulkan（C 站 9/8 实测 HIP 仅 gpt-oss 正常，MoE 系有风险）
- **注意**：C 站 gpt-oss-120b HIP 正常（48.8 t/s, 9/8）说明 HIP 非全坏——**问题限定在 MoE 大模型数值路径（qwen4exp/新架构）**，与 #28113 结论（MoE 家族）一致

**对 E.1 表格的校准**：Q3.8F UD-IQ4_XS 单站首测实际 **18.85 t/s（Vulkan, 4 slot/217K ctx）**——在 E.1 预估 12-43 t/s 区间；思考冗长治理后才是可用主力（否则 xhigh 烧 ctx）。

### D.6 C 站 unsloth（HIP）双模型实测（2026-09-10，与 D.5 形成引擎级对照）

> 引擎：C 站 `~/.unsloth/llama.cpp` **b10715**（commit 92cedc867，Clang 23，**HIP/ROCm 后端，无 Vulkan**），设备 `ROCm0: 125000 MiB`；libllama 架构探测 `dsv4/glm5next/minimax/qwen4exp` 全支持。模型均为 `~/.lmstudio/models/lmstudio-community/` 下的 unsloth UD-IQ4_XS 档。
> **内存账本（load-gate 硬规则）**：M2.7 文件 108.4G → need=107 通过（2+107+12=121 ≤ 121 恰好）；Q3.8F 93.7G → need=94 通过。实测加载后 avail 均有富余（M2.7 后 15G / Q3.8F 后 57G）。**结论：两模型 unsloth HIP 单站加载无 OOM 风险，属 load-gate 允许边界内。**

**测试 1：MiniMax-M2.7 UD-IQ4_XS（108.4G，4 分片）— ✅ 完全可用，24.4 t/s**
- 启动参数：`-c 16384 --flash-attn on --no-context-shift --device ROCm0 -ngl 999 -sm none --kv-unified -np 1 --cache-type-k q8_0 --cache-type-v q8_0 -b 1024 -ub 1024 --cache-ram 0 --temp 1.0 --top-k 40 --top-p 0.95`
- 结果：40s 加载，health OK；中文/英文输出**质量正常无乱码**；tg **24.4-24.8 t/s**（优于 LM Studio 的 ~20 t/s）
- **⚠️ M2.7 是 CoT 模型**：回复先在 `reasoning_content` 思考、再输出 `content`。默认 `max_tokens` 预算若小于思考长度，会 `finish_reason=length` 且 content 为空（非 bug）。实测 `max_tokens=800` 中文长文完整输出（reasoning 2275 tok + content 800 tok）
- 采样参数用 MiniMax 官方推荐：`temp 1.0 / top_p 0.95 / top_k 40`

**测试 2：Qwen3.8-Flash-Next UD-IQ4_XS（93.7G，3 分片）— ✅ 可用，稳态 22.8 t/s，无乱码（与 D.5 修正关键）**
- 启动参数：同 M2.7 + `--reasoning-effort medium --reasoning-budget 2000 --reasoning-preserve`
- 结果：25s 加载；**英文/中文/多轮（3 segment）输出全部正常**（Paris ✓ / Frechet 中文 ✓ / "Your name is Bob" ✓）；稳态 tg **22.6-23.2 t/s**，中文 22.2 t/s，多轮 16.2 t/s；长 prompt（1610 tok）prefill 快（6s 含首 token）
- **⚡ D.5 修正**：D.5 现象 2 判定"HIP/ROCm 暂不可用"基于 **LM Studio 内置 ROCm 引擎**（疑似含 #27621 回归）；**unsloth b10715 HIP 实测无此问题（gfx1151 MoE 数值路径正常）** → C 站 Q3.8F 的 HIP 路径**并非全坏，unsloth b10715 引擎即回避方案**。两证据同机同参不同引擎，归因差异 = 引擎版本（b10715 未踩 #28113 回归）
- **思考冗长治理生效**：`--reasoning-effort medium --reasoning-budget 2000` 下 reasoning 仅 20-245 token（对比 LM Studio 默认 xhigh 的 6 分钟/2 万 token）；b10715 原生支持这两参数（D.5 提到 LM Studio 会静默丢弃，unsloth CLI 不丢）
- 长 ctx（262K）验证待后续：本次 -c 16384 仅为 OOM 冒烟，未覆盖长上下文内存曲线

**结论（D.6）**：C 站单站可用形态 = **unsloth b10715 HIP 双载 M2.7 / Q3.8F 均验证通过**，无需依赖 Vulkan（C 站 unsloth 无 Vulkan 后端，LM Studio 才有多后端）。参数配方以此节为准；M2.7 跑长任务需给足 max_tokens，Q3.8F 必须显式降 reasoning_effort。

## E. 单站/双站模型池（原 SINGLE-DUAL-STATION-POOL）

### E.1 单站（≤124G）候选
| 模型 | 激活 | 档位/体积 | 速度 | 契合 |
|------|------|----------|------|------|
| **Qwen3.8-Flash-Next** | 6B | UD-IQ4_XS 93.7G | 12-43 t/s | **首选**：写作+agent+262K+多模态 |
| gpt-oss-120b（现役）| — | MXFP4 59G | 41 t/s(120b)/58(20b) | 已用 agent 快档 |
| Qwen3-Coder-Next | 3B | MXFP4 ~32G | ~35 t/s | 编码特化（70.6% SWE）|
| Qwen3.6-27B | 27B dense | NVFP4 14G | 15-20 | 小模型编码最强（77.2% SWE）|
| Gemma4-26B-A4B | 3.8B | MXFP4 13G | 快 | 泛用性价比 |
| Nepx N2-mini | 3B | NVFP4 | **57 t/s** | 最快多模态 |
| Nemotron-3-Super-120B（现役）| 12B | NVFP4 67G | 19.5 | 1M LatentMoE |
| **MiniMax-M2.7** | 10B | UD-IQ4_XS 108G | 15-42 | agent 强/写作弱/许可禁商 |
| Qwen3.5-122B-A10B | 10B | NVFP4 102G | ~13 | 偏重 |
| Mistral 4 Small | 6.5B | 4-bit 66G | — | 2M ctx 潜力 |

### E.2 双站（RPC/TP2）候选
| 模型 | 体积 | 双站速度 | 契合 |
|------|------|---------|------|
| **MiniMax-M2.7** AWQ-4bit | ~130G/2站 | **41.5 t/s** | agentic 吞吐王（2-node 首选）|
| **Qwen3.5-397B-A17B** | FP8 ~400G | **28-32 t/s**（TP2）| 最强推理/长文（prefill 瓶颈）|
| DeepSeek-V4-Flash-0731（现役）| 145G | 已双站跑通 | keep |
| GLM-5.3-Flash | Q2_K_XL 108.7G | 引擎未合 | 能力优但暂不可落 |

### E.3 关键洞察（社区共识）
1. **激活参数决定解码速度**（低激活 MoE >> 同总参 dense）——日常任务选低激活 MoE
2. **量化必选**（内存带宽瓶颈）：NVFP4（Blackwell）/ MXFP4 / Unsloth-UD（GGUF）；**llama.cpp Q4_K 不上 FP4 核 = 浪费**；本集群 AMD Vulkan 走 GGUF（NVFP4 不适用）
3. **MTP 免费加速 +40%**（q3.8f 已验证；nemotron 自家 vLLM 有坑）
4. **TP 扩展性**：高激活参比 TP 收益递减（397B-A17B prefill 瓶颈）→ 双站适合低激活大总参
5. 300B+ 只该上双站；单站 124G 下 <=110G 权重可跑

### E.4 回避清单
| 模型/形态 | 原因 |
|----------|------|
| 400B+ dense | 单站必崩、TP 差 |
| GLM-5.3/Kimi K2.6 | 引擎未合入（llama.cpp 不支持）|
| 1-bit 档任何模型 | 质量断崖 |
| Nemotron-MTP（自家 vLLM）| Mamba+MTP 崩溃 |
| llama.cpp Q4_K 跑 NVFP4 专属 | 浪费带宽（本集群无涉）|

### E.5 落地建议（用户场景）
1. **单站主力 = Q3.8F**（下 UD-IQ4_XS 93.7G → B 站三卡冒烟：写作/长ctx/agent → A/C 同构）
2. **双站保留 = V4-Flash 现役** + 评估 M2.7 AWQ/UD（agentic 吞吐诉求强时）；**Q3.5-397B-A17B** 列超长/超难推理升级盘
3. **小模型同站共存**：A/C 跑 Q3.8F，B 站留 coder/小模型做快速工具
4. **引擎验证先行**：`/opt/llama.cpp` 支持 qwen4exp（应已合 8-27）+ minimax（M2.7 待确认）；若缺升级重编
5. **量化纪律**：≥4-bit、UD/MXFP4 档、避 1-bit；load-gate 单模型

## F. 待实测验证（落地门，合并后统一）
- [ ] `/opt/llama.cpp`（8-31 构建）含 qwen4exp 与 minimax arch 支持
- [ ] Q3.8F UD-IQ4_XS 单站加载+冒烟（写作/长ctx/agent 三卡）
- [ ] M2.7 UD-IQ4_XS 单站内存账本实测（108G 是否贴线）
- [ ] 双站 RPC 下 M2.7 / Q3.5-397B 吞吐基准（对齐 V4-Flash 先例）

## G. 佐证来源（合并增补）
- unsloth 官方文档（M2.7 / Q3.8F）、HF `unsloth/*`、`Youssofal/MiniMax-M2.7-GGUF`、`bartowski/Qwen3.8-Flash-Next-GGUF`
- llama.cpp PR #27742（qwen4exp）、#28123（MTP）、unsloth b10715 分支
- 质量基准：Benjamin Marie 750-prompt（M2.5 同架构）、quesma（Qwen3.8 27B）、Qwen3.8-27B-Unleashed（IQ1_M=MMLU 25.8%）
- 吞吐实测：M4 Max / Jetson Thor T5000 / 2×RTX3060（llama.cpp mmap 12 t/s）/ 4×Arc B70（INT4 110 t/s）/ SGLang #22603（397B FP8）
- DGX Spark 生态：firsh.me、miramar-labs nemoclaw、qiita、ai-girls、dredyson 2-node 1200 测试、NVIDIA forum
- 社区口碑：r/LocalLLaMA / r/clawdbot / KiloCode / bswen / datacamp / eet-china / 36kr
- [Azure 三机 RPC 实测（2026-04）](https://level69.net/archives/34269)（单机装得下则 RPC 变慢）

## H. docs 模型专项调研并入（2026-09-09）

> **整合说明**: 本附录吸收 `docs/` 下 3 篇模型专项调研的关键结论（已并入来源 G 增补）；原文档归档 `.merged.bak.20260909` 供回溯。

### H.1 Qwen3.8-Flash-Next 工作站（Strix Halo）单机部署（原《Qwen3.8-Flash-Next_StrixHalo部署调研.md》2026-09-02）
- 核心对象：`agentionai/Qwen3.8-Flash-Next-ROCmFP4-FAST-imatrix-GGUF`（AMD 优化版）+ 社区 Strix Halo 优化版本盘点
- 评估（draft 落档时未部署）：ROCmFP4-FAST 为 AMD 专用调优；本集群 Vulkan 路径需回归 UD-GGUF 档（附录 B）
- 结论衔接：单机 124G 可行性以附录 B/C 为准；此篇补充"AMD 优化版本生态"视角，落地门并入附录 F

### H.2 Qwen3.8-Flash-Next 社区实测核实（原《Qwen3.8-Flash-Next社区实测调研_20260909.md》）
- **2026-09-09 修正：Flash-Next 与 Qwen3.8-27B 是不同模型**，早版误并 27B 数据已剔除——本表仅供 Flash-Next
- 架构/量化/部署可行性核实完毕；对应附录 B 档位表与 C.2 性能表（无新增数值，佐证一致性）

### H.3 gpt-oss-120b 后训练生态 + GPT-6 Astra 蒸馏（原《gpt-oss-120b后训练生态与Astra蒸馏调研_20260908.md》）
- gpt-oss 后训练家族盘点 + GPT-6 Astra 蒸馏发布状态核实（社区调研，2026-09-08）
- 关联现役资产（gpt-oss-120b 已在 A 站）；本文档正文 §3/§5 已涵盖 gpt-oss 选型结论

### H.4 溯源映射（docs → 本附录）
| docs 原档（归档 .merged.bak.20260909）| 本附录 | 说明 |
|---|---|---|
| Qwen3.8-Flash-Next_StrixHalo部署调研.md | H.1 | AMD 优化版单机评估 |
| Qwen3.8-Flash-Next社区实测调研_20260909.md | H.2 | Flash-Next 核实（27B 误并剔除）|
| gpt-oss-120b后训练生态与Astra蒸馏调研_20260908.md | H.3 | gpt-oss 后训练/Astra |

### H.5 待办承接
- [ ] Qwen3.8-Flash-Next 单站落地时评估 ROCmFP4-FAST 档（若 A 站 ROCm 路径启用）（H.1）
- [ ] gpt-oss 后训练家族（如有蒸馏变体）纳入实测台账（H.3，P3 级）

## I. domain_matrix 五模型实测判分对照（2026-09-11，Nemotron-120B 并入）

> 测试集: `spec/model-eval/questions/domain_matrix.md`（20 题，概念/证明/计算/诊断/代码，rubric 判分：锚点+疑似幻觉标志）。结果目录 `tmp/res_*`。Q3.8F/M2.7 首轮空答由 `--reasoning-preserve` 使思考计入预算导致，均关闭 preserve + 收紧 `max_tokens`(Q3.8F=12000, M2.7=20000) 后补跑，全部产出完整答案。

### I.1 判分总览

| 模型 | 站/量化 | 优秀 | 良好 | 不合格 | 幻觉标志触发 | 备注 |
|---|---|---|---|---|---|---|
| **MiniMax-M2.7** | C / UD-IQ4_XS (229B MoE, CoT) | 15 | 1 | 0 | **0** | B1 答案截断 |
| **Qwen3.8-Flash-Next** | B / UD-IQ4_XS (CoT) | **19** | 1 | 0 | **0** | B1 草稿化截断；优秀率最高 |
| **gpt-oss-120b** | A / MXFP4 (60G) | 19 | 1 | 0 | 0 | A3 λ_U 数值错 |
| **gpt-oss-120b-Fable-5-Distilled** | A / Q5_0 (76G) | 18 | 2 | 0 | 0 | A3 数值错 + E1 时序列缺陷 |
| **Nemotron-3-Super-120B-A12B** | B / Q4_K_M (81G, 12B激活) | 18 | 2 | 0 | **0** | A3 λ_U≈0.44(+11%) + A2 L2 控制收敛表述不足 |

### I.2 A3 λ_U 数值跨模型核验（关键分歧点）

正确值 λ_U=2·t₅(−√(5·(1−ρ)/(1+ρ)))，ρ=sin(π/4)≈0.7071 → **0.397**。

| 模型 | λ_U 答案 | 判定 |
|---|---|---|
| M2.7 | 0.402 | ✅ 容差内正确 |
| **Q3.8F** | **0.40** | ✅ 正确 |
| gpt-oss (MXFP4) | 0.165 | ❌ 错（df 用 ν 而非 ν+1，−58%） |
| fable (Q5_0) | 0.1854 | ❌ 错（t₅ CDF 估错约一半，−53%） |
| **Nemotron-120B** | ~0.44 | ❌ 错（t₅ CDF 用 Φ_t 琐错，+11%，超±5%） |

> 结论：**长链 CoT 模型（M2.7/Q3.8F）在纯计算代入类题上精确（0.40），非 CoT 高吞吐模型（gpt-oss/fable/Nemotron）系统性在 λ_U 数值坑失手**；但 Nemotron(+11%, 12B激活) 误差远小于 gpt-oss 家族(−53~58%, 5B激活)，**紧凑 MoE 架构数值精度明显优于 5B 激活超大宽模型**。

### I.3 逐题对照（优秀/良好）

| 题 | M2.7 | Q3.8F | gpt-oss | fable | Nemotron-120B |
|---|---|---|---|---|---|
| A1 | 优 | 优 | 优 | 优 | 优 |
| **A2** | 优 | 优 | 优 | 优 | ⚠️良好（L2 控制收敛表述不足）|
| **A3** | 优 | 优 | ⚠️良好 | ⚠️良好 | ⚠️良好（λ_U +11% 超±5%）|
| B1 | ⚠️良好 | ⚠️良好 | 优 | 优 | 优 |
| B2,C1,C2,D1,D2,E2,F1,G1,G2,H1,H2,I1,I2,J1,J2 | 优 | 优 | 优 | 优 | 优 |
| E1 | 优 | 优 | 优 | ⚠️良好 | 优 |

### I.4 落地研判

- **Q3.8F 为当前机群数理主力最优候选**：19/20 优秀（五者最高），且每题 300-635s 快于 M2.7(250-1100s)；与 M2.7 在 A3 双双重数值正确。
- **Nemotron-120B（12B 激活紧凑 MoE）为第二梯队最优通用底座**：18/20 优秀，A3 λ_U +11% 误差远小于 gpt-oss 家族(−53~58%, 5B激活)，印证**紧凑 MoE 数值精度 > 超大宽 MoE**；A2 L2 控制收敛表述不足为唯一额外良好。
- **gpt-oss / fable 定位**：概念/证明/诊断全对，唯纯计算代入类题（A3）翻车，适合作快速工具/执行层，不作深度数理主判。fable(Q5_0) 未优于原版 MXFP4。
- 五模型均 0 幻觉标志触发（A3 椭圆 τ 不变性、E2 最优权重、J2 敏感度等反直觉陷阱全部正确绕开）。

### I.5 附带任务收尾

- **Hermes Agent 升级**：A 站 v0.14.0(5月) → **v0.21.1(2026.9.7)**，`uv run` 路径 + shim 指向 `.venv`；备份 `hermes-agent.bak_pre_upgrade_20260910_200935`。经验：A 站直连 GitHub git 协议不稳，主控站(魔法)下载 tarball + scp 内网传输最稳。
- **V4.1 Flash 量化评估**：原生 511GB（含 196B Engram 表 189GiB），显存底线 614GB(8×H200/GB200)；llama.cpp 未支持 + Engram 跨机通信爆炸 + Q2 崩 → **三站不可行**；走外部 API 巡顶（便宜77%、快427-507t/s）。机群归属仍为 V4-Flash-0731（现役 MXFP4 146G）。