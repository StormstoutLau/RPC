# Qwen3.8-Flash-Next 工作站（Strix Halo）单机部署调研

---
date: 2026-09-02
status: draft（调研落档，未部署）
scope: agentionai/Qwen3.8-Flash-Next-ROCmFP4-FAST-imatrix-GGUF 评估 + 社区 Strix Halo 优化版本盘点 + 本集群（395 AI Max 128G / Radeon 8060S）单机部署可行性
---

> **问题**: ① agentionai 的 Qwen3.8-Flash-Next-ROCmFP4-FAST-imatrix-GGUF 能否在工作站（AMD 395 AI Max Strix Halo + Radeon 8060S, 128G 统一内存）上单机高效部署？② 社区还有哪些 AMD Strix Halo 优化版本？
> **方法**: 官方模型卡/llama.cpp issue 直抓（E1）+ 社区实测报告（E2，标注）+ 本集群硬件基线对照。agentionai HF 仓库两次直抓失败（细节标 E4，格式机制经 ROCmFPX 项目 E1 间接实证）。

## 0. 速览

| 问题 | 结论 |
| --- | --- |
| 模型是什么 | Qwen3.8-Flash-Next（2026-08-26 发布，**Qwen4 架构预览**，arch 名 qwen4exp）：125B 总参 MoE / **6B 激活** / 51B n-gram embedding / 4B MTP 头；48 层 = 36 Gated DeltaNet + 12 稀疏注意力；原生 262k ctx（YaRN 1M）；多模态；Qwen Community License 1.0 |
| 128G 单机装得下吗 | **装得下**：unsloth UD-IQ4_XS 93.7GB（含 headroom ~112GB）或 UD-Q3_K_XL 90GB；262k 全窗 KV 仅 ~6.5GB（QSA 每 token 只 2 KV 头，超省） |
| 跑得快吗 | **分两档**：stock 主线 llama.cpp 在 gfx1151 有 **1K ctx decode 崩塌**（19-21 → 5.5 t/s，3.5-4x，#27856，QSA top_k 在 HIP 上 CPU fallback）；带修复堆栈后 **17 → 47 t/s**（drluoto #27950：GPU TOP_K + 原生 MTP + ngram-mod，实测 coding 8k ctx 47.1 t/s / 24k 25-28 t/s） |
| agentionai ROCmFP4 值得用吗 | **激进选项**：ROCmFP4 = charlie12345 ROCmFPX 家族的 speed-first 4-bit AMD 专用格式（比 Q4_K_M 小 ~12%，agent-aware preset 保护 code/JSON/tool-call 张量，内建 MTP target-verified 自投机）；**实验性 + 需 ROCmFPX fork 构建**（主线 llama.cpp 不认其 tensor type）——agentionai 仓细节未核验（E4） |
| 本集群上不上 | 可行且社区已充分踩坑；条件 = ①llama.cpp 构建含 qwen4exp（PR #27742，8-27 已合入主线）**且含 TOP_K HIP 修复**（#26592/#27466，或直接用 drluoto 预组装分支）②UD-IQ4_XS 起步 ③新 conf 实例进 infer-load 框架过 load-mem-gate。RPC 双机路径有崩溃报告（#27865）不推荐 |

## 1. 模型事实（E1 官方模型卡 / Zenn 技术拆解直抓）

| 项 | 值 |
| --- | --- |
| 发布 | 2026-08-26（HF/ModelScope）；定位 = Qwen4 架构预览（同 Qwen3-Next→Qwen3.5-3.8 的先例） |
| 参数 | **总 125B / 激活 ~6B**；512 experts（10 routed + 1 shared）；hidden 2560 / 48 层 |
| 特殊部件 | **51B n-gram PLE embedding**（2 千万 bigram/trigram 表，layer 2，查表不计算——设计为驻留系统内存）；**4B MTP**（多 token 预测投机头）；视觉+视频塔 |
| 注意力 | 混合：**36 Gated DeltaNet（线性）+ 12 full-attn（Qwen Sparse Attention）**；4 分支门控残差（hyper-connections） |
| 上下文 | 原生 **262,144**；YaRN 扩 1M；262k 全窗 KV cache 仅 ~6.5GB（E2 unsloth 测算） |
| 能力定位 | 6B 激活 ≈ 逼近 Qwen3.7-Plus（397B/17B 激活）大部分自测基准；训练成本 1/9；编码/agentic 强项；reasoning effort 可选 xhigh/medium/low/none |
| License | **Qwen Community License 1.0**（非 Apache——商用注意，与 Qwen3.8-27B 的 Apache-2.0 不同） |
| FP8 体积 | 172.78 GiB（稀疏激活省算力**不省存储**——量化才是上消费硬件的正道） |

## 2. 量化选型（E1 unsloth UD 系列官方数字）

| 量化 | 磁盘 | 内存需求（含 headroom） | 适配 |
| --- | --- | --- | --- |
| UD-IQ1_S（1-bit） | 72.5 GB | ~75 GB | 极限尝鲜；unsloth 称保留 80% top-1（厂方自测口径） |
| UD-Q2_K_XL | 78.9 GB | ~79 GB | Simon Willison DGX Spark 验证可用（xhigh reasoning） |
| UD-Q3_K_XL | 90 GB | ~90 GB | **本集群稳妥档**（GTT 余量健康） |
| **UD-IQ4_XS** | 93.7 GB | ~112 GB | **本集群质量档**（#27856/#27950 实测用档；GTT 紧但可行） |
| UD-Q4_K_XL | 111.3 GB | ~125 GB | 过紧，不建议 |
| BF16 | 355 GB | 355 GB | 不适用 |

对照硬件：128G 统一内存 Mac 跑 4-bit 全 262k ctx ✓（官方映射）；**本站 = 同级（gfx1151, GTT 可用 ~96-110GB）**——IQ4_XS 落在"能装、余量靠 UMA 弹性"区间。

## 3. Strix Halo 实测现状（核心：性能崩塌与修复堆栈）

### 3.1 stock 主线的崩塌（E1 llama.cpp #27856，2026-08-28）

- 现象：gfx1151（Ryzen AI Max+ 395, 128G）上 decode 随**上下文深度**崩塌——<512 tok 时 19-21 t/s；**过 ~1K 后跌到 5.5-6.1 t/s**（4.6 @45K），3.5-4x cliff；prefill 同步退化。`-fa off` A/B 排除 flash-attention；质量无损（45K needle 精确命中）
- 根因定位（issue 作者 + 后续 #27950 确认）：**QSA indexer 每 token 对全上下文跑 12 次 `ggml_top_k`，stock HIP 在 ne>1024 时无 CUB 路径回退 CPU**——拐点恰在 d1024
- 环境：ROCm 7.2.4 / `LLAMA_ATTN_ROT_DISABLE=1`（QSA+q8_0 KV 必需，否则 assert）/ `GGML_HIP_NO_VMM=ON` / PIC=OFF 等 build 细节

### 3.2 修复堆栈（E1 llama.cpp #27950，drluoto，2026-08-29——与本站同硬件的完整答案）

三杠杆（可组合）：

1. **GPU TOP_K**：PR #26592（hipCUB 路径）或 #27466（native radix TOP_K）→ 24k ctx 端到端 +38-53%
2. **原生 MTP 投机解码**（PR #27836，`--spec-type draft-mtp`）+ detached-head loader 修复——**读输出而非只看计数器**（早前社区 MTP 移植在 >1k prompt 时"速度漂亮、输出多语种噪声"）
3. **ngram-mod 叠加**：`--spec-type draft-mtp,ngram-mod`

实测（UD-IQ4_XS，单流 greedy，真实 coding 负载）：

| 场景 | 无投机 | 全堆栈 |
| --- | --- | --- |
| file rewrite @ 8k ctx | 16.8 | **47.1** |
| new code @ 8k | 16.8 | 31.7 |
| file rewrite @ 24k | ~15 | 28.6 |
| new code @ 24k | ~15 | 25.4 |

运维要点（对 agent 会话直接相关）：
- **36 层 GDN 是 recurrent 的，不能回滚 → 必须 `--ctx-checkpoints`**；多会话共一个 llama-server 用 `-np 3 --ctx-checkpoints 8`（LCP 匹配保各会话热缓存，真实 trace 上 TTFT 21-251s → 0.3-0.5s）
- ROCm <7.13 需 `GGML_CUDA_DISABLE_GRAPHS=1`；`-ub 2048` bench 陷阱等打包在指南仓
- 交付物：[drluoto/flash-next-strix-halo](https://github.com/drluoto/flash-next-strix-halo)（指南）+ [drluoto/llama.cpp `strix-halo-flash-next`](https://github.com/drluoto/llama.cpp/tree/strix-halo-flash-next)（预组装分支）+ [drluoto/Qwen3.8-Flash-Next-MTP-GGUF](https://huggingface.co/drluoto/Qwen3.8-Flash-Next-MTP-GGUF)（ROCm 验证 MTP sidecar，HTTP range 只拉 5.2GB 头部）

### 3.3 反面数据点

- **RPC 双机崩溃**（#27865）：gfx1151×2 经 RPC 跑 Q8_0，TOP_K "invalid configuration argument" ~350-370 token 后崩——**双机 RPC 路径勿碰**（本集群本就回退双端点单机架构，一致）
- CSDN/Reddit 朴素跑法（无修复）报告 Strix Halo 10-15 t/s 量级——即 3.1 崩塌态的水位

## 4. agentionai / ROCmFP4-FAST-imatrix-GGUF 分析

**仓库直核失败**（HF 页面两次 fetch 失败——细节 E4）；但命名指向的格式家族有充分 E1：

- **ROCmFPX 家族**（[charlie12345/ROCmFPX](https://github.com/charlie12345/ROCmFPX)，**AMD 送测硬件开发**，MIT）：AMD 专用 GGUF 权重格式族 ROCmFP2/3/4/6/8——真权重格式（非 KV 压缩），HIP/ROCm + Vulkan 加速内核 + CPU 参考实现；**实验性**（API/调优/性能可变，官方自荐用 BF16 源对质量）
- **ROCmFP4 = speed-first 4-bit 家族**：现有 Qwen 对照文件**比 Q4_K_M 小 ~12%**；**agent-aware preset**（coherent/agent recipe 保护 code/JSON/tool-call/结构化输出关键张量）；**内建 MTP target-verified 自投机**（含 M-RoPE Qwen，无需独立 draft 模型）；ROCmFP2（2.50-bpw S40 codebook + 双 UE4M3 scale）已在主线落地为 `Q2_0_ROCMFPX`，Qwen3.6-35B-A3B 实测 Vulkan 90.3 t/s / ROCm 75.9 t/s（对照 ROCmFP4 76.2/67.5）
- **Strix Halo 专项开发**：作者开发机即 Framework Desktop（Strix Halo 395+128G）；另有 [charlie12345/rocmfp4-llama](https://github.com/charlie12345/rocmfp4-llama) `mtp-rocmfp4-strix` 分支（含 MTP 的 ROCmFP4 llama.cpp fork）
- **推断**（E5，仓库名证据）：agentionai 该仓 = 用 ROCmFP4 格式 + imatrix（重要性矩阵）量化 + FAST（家族内速度预设）的 Qwen3.8-Flash-Next GGUF 打包；**加载它需要 ROCmFPX fork 构建，主线 llama.cpp 不识别其 tensor type**

**裁定**：技术上有吸引力（更小更快 + agent 张量保护 + 免 draft 自投机），但①实验性格式 ②质量需对 BF16 自验 ③绑定 fork 构建不走主线 infer-load 升级窗——**建议作为二期评估项，首部署不用**；首部署走 unsloth UD-IQ4_XS + drluoto 修复分支（社区同硬件实测最厚）。

## 5. 社区 Strix Halo 优化版本盘点

| 版本 | 形态 | Strix Halo 适配度 | 备注 |
| --- | --- | --- | --- |
| **unsloth/Qwen3.8-Flash-Next-GGUF**（UD 系列） | 通用 GGUF 基线 | ★★★（两份 Strix Halo 实测均用它） | UD-IQ4_XS 93.7GB 为 #27856/#27950 实测档 |
| **drluoto/flash-next-strix-halo** + llama.cpp 分支 + MTP sidecar | **Strix Halo 专项全栈** | ★★★★★（同硬件 47 t/s 实测） | 指南+预组装分支+ROCm 验证 MTP 头；GDN checkpoints 运维要点 |
| **charlie12345/ROCmFPX / rocmfp4-llama（mtp-rocmfp4-strix）** | AMD 专用格式族 fork | ★★★★（Strix Halo 上开发） | FP2-8 全家族+agent preset+内建 MTP；实验性 |
| agentionai/...ROCmFP4-FAST-imatrix-GGUF | ROCmFPX 格式打包 | ★★★（未核验 E4） | 用户点名项；需 fork 构建加载 |
| ARC4NUM/Qwen3.8-Flash-Next-Uncensored-MLX-Serve-4bit | MLX（Mac 专用） | ✗（不适用；参考价值） | ~68GB resident（**51B n-gram 表 mmap 磁盘**思路）+56-60 t/s on M5 Max——Mac 侧最快方案，证明 n-gram 表可外置 |
| orcarouter 系 abliterated | 去审查 BF16/GGUF | 通用 | 需求特定 |
| 27B 对照 | — | — | 若只要"本地 Opus 4.6 级"，Qwen3.8-27B（Dense, Apache-2.0, Q4 18GB）是零风险替代——非本调研主题 |

## 6. 本集群单机部署评估（B 站为优）

| 维度 | 评估 |
| --- | --- |
| 显存 | IQ4_XS 93.7GB 权重 + KV（131k ctx q8_0 远小于 6.5GB）→ 装得下但 GTT 紧；**Q3_K_XL 90GB 留余量更稳**；过 load-mem-gate（MemAvailable ≥ 模型+12G 缓冲）时 UMA 弹性需实测 |
| 构建前置 | ① llama.cpp 含 qwen4exp（#27742 已入主线，**但须核对站上 llama.cpp 现版本**——为 nemotron/gpt-oss 构建的版本大概率更旧）② **含 TOP_K HIP 修复**（#26592/#27466 是否已入主线需核；否则用 drluoto 分支）③ `LLAMA_ATTN_ROT_DISABLE=1`、ROCm≥7.1、graphs 开关按 ROCm 版本 |
| 性能预期 | 修复+MTP：**8k coding 30-47 t/s、24k 25-28 t/s**（同硬件实测锚点）；无修复：>1k ctx 即 5.5 t/s 不可用 |
| 与现役关系 | GTT 互斥——装 Flash-Next 必卸 nemotron/gpt-oss（infer-load 框架新 conf 实例轮换）；或 A 站试点（gpt-oss 让位） |
| 集成路径 | 走既有框架：新 conf（EXTRA_FLAGS 含 QSA 相关 env）→ infer-load → LiteLLM 路由第三条目 → agent CLI 即插即用（D5 生态零改动——provider 加模型条目+limit.context 即可） |
| 风险 | ①fork 构建脱离主线升级窗（内核锁定的先例逻辑）②Qwen Community License 1.0 商用条款③实验性 PR 仍在快速变动（#27836 MTP 8-29 才合）④51B n-gram 表驻留 UMA 的带宽竞争待实测 |

**结论：可以单机高效部署，且社区已把本硬件的坑基本排平**——但"高效"的前置条件不是模型而是**构建**（TOP_K 修复 + MTP）。推荐路径（若决定上）：

```
P0 前置核验（30min）: 站上 llama.cpp 版本是否含 qwen4exp + TOP_K 修复；ROCm 版本 ≥7.1
→ 首部署: unsloth UD-Q3_K_XL 或 IQ4_XS + drluoto strix-halo-flash-next 分支构建
→ 入框架: /etc/llama-instances/ 新 conf + load-mem-gate + PONG 冒烟
→ 基准: llama-bench 对照社区锚点（16.8/47 t/s）；needle 抽查（45K 全命中为质量线）
→ 二期评估: ROCmFP4（agentionai/charlie12345 fork）——质量对 BF16 自验后再议
```

## 参考源

- [llama.cpp #27856: qwen4exp decode slowdown on HIP/gfx1151](https://github.com/ggml-org/llama.cpp/issues/27856)（E1 直抓：崩塌数据/根因/环境）
- [llama.cpp #27950: Strix Halo 17→47 tok/s MTP stack](https://github.com/ggml-org/llama.cpp/discussions/27950)（E1 直抓：drluoto 修复堆栈/GDN checkpoints/交付物清单）
- [llama.cpp #27865: ROCm RPC TOP_K crash](https://github.com/ggml-org/llama.cpp/issues/27865)（E1 直抓：双机 RPC 反例）
- [charlie12345/ROCmFPX](https://github.com/charlie12345/ROCmFPX)（E1 直抓：ROCmFP 家族规格/ROCmFP2 主线落地/AMD 送测披露）
- [Zenn: Qwen3.8-Flash-Next 技术拆解](https://zenn.dev/neotechpark/articles/23e1374df4d0eb)（E1 直抓：模型卡/架构四变体/规格表）
- [howaiworks: 本地 GGUF 内存映射表](https://howaiworks.ai/blog/alibaba-qwen-3-8-flash-next-local-gguf)（E1 直抓：unsloth UD 体积/262k KV 6.5GB/机器映射）
- [ARC4NUM MLX-Serve 4bit](https://huggingface.co/ARC4NUM/Qwen3.8-Flash-Next-Uncensored-MLX-Serve-4bit)（E1 直抓：Mac 侧 mmap n-gram 表方案）
- [drluoto/flash-next-strix-halo](https://github.com/drluoto/flash-next-strix-halo)（E2 指南仓，#27950 交付物）
- agentionai/Qwen3.8-Flash-Next-ROCmFP4-FAST-imatrix-GGUF（**E4：两次直抓失败，仓库存在性由用户给定，细节未核验**）
- 本集群硬件/框架基线：D5 CHECKLIST §6、手册 §1-§3（E1）
