# DSpark 与专用加速框架调研 — DeepSeek V4 Flash / GLM 5.3 Flash 在 A/B 集群的适配性

> **日期**: 2026-08-28
> **作者**: Scott (鹏)
> **适用系统**: A 站 + B 站 (AMD Ryzen AI Max 395 / Strix Halo, Radeon 8060S iGPU, 各 128GB 统一内存, Ubuntu, Vulkan/RADV, USB4 RPC 直连), 主控站 Win10 + RTX 4060 8G (不参与大模型推理)
> **当前状态**: llama.cpp v0.2.0, RPC 协议 v4.0.1, MiniMax-M2.7 Q4_K_S 双机 RPC ~18.2 t/s (tg128 20.15)
> **调研问题**: 开源社区的 DSpark 等专用模型加速框架, 对当前软硬件加载 DeepSeek V4 Flash / GLM 5.3 Flash 两类模型的可行性
> **关联文档**: 《RPC协议瓶颈调研.md》(协议层), 《提速调研报告.md》(整体), DEV-LOG-009 (v0.2.0 升级)
> **v1.1 (2026-08-28)**: 引用审计修正 — ① **DSpark 在 Vulkan 主线实测无加速**(sypherin 同硬件: 接受率 61.8% 但 tg 持平), 1.5~1.9x 为 CUDA 数据, 原预期 25~35 t/s 不成立; ② 草稿体积 6.5GB→**10.1GiB**, IQ2 档 80GB→84.6GiB; ③ 原 "GTT 108GiB 墙" 无来源支持, 按 Unsloth 官方推荐 IQ3_XXS+Q8_0 草稿为 128GB 机器标配; ④ GLM 量化体积修正(IQ1_S 93GB / Q2_K_XL 109GB / IQ3_XXS 120GB); 详见《三调研报告审计.md》

---

## 一、执行摘要

1. **DSpark 已进入 llama.cpp 主线**, 无需专用框架 — PR [#25173](https://github.com/ggml-org/llama.cpp/pull/25173) 2026-07-28 由 ggerganov 合入, 作者是 wjinxu (DFlash 前身 #22105, 作者 ruixiang63, 2026-06-28 合入)。用法即 `--spec-type draft-dspark` + 对应草稿 GGUF。v0.2.0 (2026-08-21 标签, 审计确认) 在合并之后, **已包含**; 上线前一条命令验证。**注意: PR 明示置信头已转换加载但推理未启用 (phase 1) — "置信度调度剪枝"是论文能力, 非 llama.cpp 现状**。
2. **DeepSeek V4 Flash (284B/13B 激活) 在同硬件已被跑通**: 同款 Strix Halo 128GB 实测 — Lucebox (ROCm 自定义路线) **32.0 t/s decode (DSpark q=4)**; **Vulkan 主线裸自回归仅 ~9.5~12 t/s**(sypherin IQ2_XXS tg32=12.24; #26578 基线 IQ3_XXS tg=11.16 — 榜单 18.99 为 MQ2+MTP 含投机解码, 15.6 为 Q2_K 特定配置, 均非裸基线)。**v1.1 关键修正: DSpark 在 Vulkan 主线实测无加速** — sypherin 2026-08-08: 接受率 61.8% 但 tg 9.5→9.5 t/s, 草稿自身 ~10GiB 前向成本在带宽受限 iGPU 上吃掉全部收益; Unsloth 的 1.5~1.9x 是 CUDA(B200/DGX) 数据。Vulkan 路线的真实 decode 加速杠杆是 [#26578](https://github.com/ggml-org/llama.cpp/pull/26578) 融合算子 (1.50x, 数据已逐字核验)。
3. **GLM 5.3 Flash (320B/18B 激活) 尚未合入 llama.cpp**: 三个 Draft PR (2026-08-26, [#27754](https://github.com/ggml-org/llama.cpp/pull/27754)/[#27752](https://github.com/ggml-org/llama.cpp/pull/27752)/[#27773](https://github.com/ggml-org/llama.cpp/pull/27773)) 竞争中, 无 MTP/投机解码, Vulkan 路径未验证 (仅 CPU/CUDA 验证)。
4. **单机内存预算 (v1.1 修正 — 原 "108GiB GTT 墙" 断言未获任何来源支持, 系合成误差)**: 实测证据分散 — #21948 构建行 GTT=120 GiB (RADV); tinycomputers (HIP+VMM 路径) 96GB; sypherin 实跑 IQ2_XXS(84.6GiB)+131k 上下文+草稿共 97G used / 26G free (需 `GGML_VK_PREFER_HOST_MEMORY=ON`); **Unsloth 官方明示: "3 位版本为 103GB, 可在 110GB RAM 设备上运行", 并推荐 128GB 机器用 IQ3_XXS+Q8_0 草稿组合 (DSpark 需约 10GB 额外内存)**; sypherin 评 IQ3_XXS "right at the edge"。结论: Q3+草稿单机=**边缘但官方推荐配置**(以实测为准), Q4/Q8 档需双机 RPC 拆分。
5. **两大风险**: ① RPC + 投机解码的历史崩溃已修 ([#23273](https://github.com/ggml-org/llama.cpp/pull/23273), 5 月合入), 但 MTP 多 ubatch 竞态 ([#26827](https://github.com/ggml-org/llama.cpp/pull/26827), Open) 未修, 长 prompt prefill 有整机锁死前科; ② RADV 上 KDA 线性注意力 prefill 呈非线性扩展 ([#27638](https://github.com/ggml-org/llama.cpp/issues/27638)) — GLM 5.3 Flash 有 34/45 层是 KDA。

**结论 (v1.1 改写)**: 短期 — B 站单机 Vulkan 试点 DeepSeek V4 Flash IQ2/IQ3 档, **定位为质量/容量评估而非提速** (Vulkan 裸 AR ~10-12 t/s, DSpark 无增益, 低于现 MiniMax 双机 18.2 t/s); 中期 — 双机 RPC 拆分跑 Q3/Q8 档 (容量价值), 监控 #26827; 提速的正道是等 #26578 融合算子合并 (decode +50%)。长期 — 订阅 GLM 5.3 三个 PR, 合并后按 UD-IQ1_S 双机拆分试点。CUDA 专用框架 (Home-Seek、GB10 fork、vLLM) 全部不可用; ROCm 专用路线 (Lucebox ROCmFPX) 32 t/s 是唯一实测大幅提速路径, 但属定制 fork, 与本集群版本化 SOP 冲突, 仅作性能上限参考。

---

## 二、DSpark / DFlash: 模型层加速(投机解码)

### 2.1 机制与论文

[DSpark 论文](https://arxiv.org/pdf/2607.05147.pdf) (DeepSeek-AI + 北大, 2026-07-06, arXiv 2607.05147):

| 组件 | 机制 | 解决的问题 |
|:---|:---|:---|
| **半自回归 (SAR) 草稿架构** | 并行骨干 (DFlash 块扩散, 一次前向出整块) + 轻量顺序模块 (Markov head) 引入块内 token 依赖 | 并行草稿的"后缀衰减": 块尾 token 因缺乏块内条件而接受率骤降 |
| **置信度调度验证** | 联合(累积)存活概率截断草稿 + 按引擎负载动态调整验证长度 | 无差别验证长块浪费目标模型 batch 容量, 高并发下吞吐反降 |

关键实测数据:
- DeepSeek-V4 生产流量: 对比 MTP-1 基线, **每用户生成提速 60%~85%** (等吞吐约束下)
- 离线基准: 接受长度对 Eagle3 提升 +26.7%~+30.9% (Qwen3-4B/8B/14B)
- DSpark checkpoints 与 DeepSpec 训练库已开源 (草稿模型按目标模型训练, **非通用**)

### 2.2 llama.cpp 支持时间线

| 时间 | 事件 | 状态 |
|:---|:---|:---|
| 2026-06-28 | DFlash 合入 (#22105, 作者 ruixiang63, v1.1 修正日期), `--spec-type draft-dflash` | 已在主线 |
| 2026-07-28 | DSpark 合入 (#25173, 作者 wjinxu, ggerganov 合并; `DFlash + Markov head` 折叠进 DFlash arch 按 spec type 选择)。**置信头已加载但推理未启用 (phase 1) — 置信度剪枝是论文能力, 非 llama.cpp 现状 (v1.1)** | 已在主线 |
| 2026-08-06 | Unsloth 为 DeepSeek-V4-Flash GGUF 启用 DSpark (1.5~1.9x, **CUDA 硬件数据**) | 模型侧就绪 |

v0.2.0 (2026-08-21 标签, 审计确认) 在 #25173 之后, **已包含 DSpark**; **验证方法**: `llama-server --help 2>&1 | grep -i dspark` (或 `--spec-type` 列表中出现 `draft-dspark`)。若缺失则需 master 重建。

### 2.3 llama.cpp 全部投机解码类型(当前可用工具箱)

| 类型 | 机制 | 额外模型 | 适用 |
|:---|:---|:---|:---|
| draft-simple / ngram | 自身/上下文 n-gram 复用 | **无** | 任意模型 (代码/agent 输出收益高), GLM 5.3 唯一可用的加速项 |
| draft-mtp | 目标模型自带 MTP 头 | MTP GGUF | DeepSeek V4 (原生 MTP 块)、Gemma 4 QAT |
| draft-eagle3 | 自回归 EAGLE 草稿 | EAGLE GGUF | 有对应训练草稿的模型 |
| draft-dflash | 块扩散并行草稿 | dflash GGUF | 通用并行草稿 |
| **draft-dspark** | DFlash + Markov head + 置信度剪枝 | dspark GGUF | **DeepSeek-V4 系列 (官方训练)** |

### 2.4 DeepSeek V4 Flash 的 DSpark 官方用法 (Unsloth)

```bash
llama-server \
  -m DeepSeek-V4-Flash-0731-UD-IQ2_KS.gguf \
  -md unsloth/DeepSeek-V4-Flash-0731-GGUF/dspark-DeepSeek-V4-Flash-0731-Q8_0.gguf \
  --temp 1.0 --top-p 1.0 --min-p 0.01 \
  --spec-type draft-dspark --spec-draft-n-max 3 \
  -ngl 99 -ngld 99
```

来源: [Unsloth DeepSeek-V4 指南](https://unsloth.ai/docs/zh/mo-xing/deepseek-v4) (草稿为独立 GGUF; **Q8_0 档实为 ~10.1 GiB** — sypherin 实测加载值, Unsloth 官方 "DSpark 需约 10GB 额外内存"; v1.0 写 6.5GB 系低估)。

⚠️ **sypherin 实测的三个配对陷阱 (v1.1 新增, 同硬件 Vulkan)**:
1. **草稿必须与目标同 quant 家族同源** — Unsloth 目标 + antirez 重量化草稿 = 接受率仅 **0.15%** (分布不匹配); Unsloth target + Unsloth dspark-Q8_0 才有 61.8%
2. **`--spec-type` 写错静默失效** — 误写 `draft-dflash` (无 Markov head) 时 `/slots` 仍显示 `speculative: false`, 不报错
3. **大模型 Vulkan 分配** — 需 `GGML_VK_PREFER_HOST_MEMORY=ON` (sypherin 131k 上下文实跑前提)

---

## 三、目标模型一: DeepSeek V4 Flash (0731) — 可立即部署

### 3.1 规格

| 项 | 值 |
|:---|:---|
| 总参数 / 激活 | **284B / 13B** (256 路由专家 + 1 共享, 每 token 激活 6 专家) |
| 上下文 | 1M (混合压缩注意力: SWA 128 + CSA 4x/top-512 + HCA 128x → KV 极小) |
| 原生精度 | QAT: 路由专家 (96% 权重) 原生 MXFP4, 其余 FP8/BF16 |
| 基准 | Terminal Bench 2.1: 82.7%; DeepSWE: 54.4% (同档最佳, 超 V4-Pro 预览版) |
| 原生加速 | MTP 块 (可用 draft-mtp) + DSpark 草稿 (官方训练) |

### 3.2 量化矩阵 (Unsloth UD 系列 + 社区)

| 量化 | 体积 | 质量 | 单机 128GB 可行性 |
|:---|:---|:---|:---|
| UD-Q8_K_XL | 162GB | 逐位无损 (1328 张量对官方权重 bit-exact) | ✗ 单机; ✓ 双机 (81GB/站) |
| UD-Q4_K_XL | ~155GB | 近无损 (专家仍 bit-exact, 非专家 Q8) | ✗ 单机; ✓ 双机 |
| UD-IQ3_XXS | **103GB** | 高 (QAT 训练使 3-bit 表现好) | **边缘但官方推荐**: Unsloth 明示 "可在 110GB RAM 设备运行", 推荐 128GB 机器 IQ3_XXS+Q8_0 草稿; sypherin 评 "right at the edge" (v1.1) |
| IQ2_XXS / IQ2_M | **84.6~91GB** | 中 | ✓ 单机 (sypherin 实证: +131k ctx + 草稿共 97G used) |
| Q2_K_XL | 97GB | 中 | ✓ 单机 (边缘) |
| IQ1_S (teamblobfish) | **58GB** | 低-中 | ✓✓ 单机, 巨量余量 (tinycomputers 实证加载成功) |

⚠️ **内存约束 (v1.1 重写 — 原 "108GiB GTT 墙" 断言未获来源支持, 系合成误差)**: 各来源实测值不一 — [#21948](https://github.com/ggml-org/llama.cpp/issues/21948) 构建行 **GTT 120 GiB** (RADV); [tinycomputers](https://tinycomputers.io/posts/running-deepseek-v4-flash-on-amd-strix-halo.html) (HIP+VMM 路径) **96GB**; [sypherin](https://github.com/sypherin/strix-halo-setup) 实跑 IQ2_XXS+131k ctx+草稿 **97G used / 26G free** (`GGML_VK_PREFER_HOST_MEMORY=ON` 为前提); Unsloth 官方: IQ3_XXS (103GB) 可在 110GB RAM 设备运行。综合: 单机上限按 "Q3 档+草稿≈边缘可行" 处理, 以实测为准; Q4/Q8 档必须双机。

### 3.3 同硬件实测 (LocalMaxxing 社区榜单, 2026-07-18)

| 提交 | 路线 | 量化 | decode t/s |
|:---|:---|:---|:---|
| **Lucebox** | **ROCm 7.2.4 + 自研 ROCmFPX HIP kernel + DSpark (q=4)** | ROCmFP2 混合 102.3GB + 草稿 11.3GB | **32.0** (裸 AR 25.31) |
| HipFire | Vulkan 主线 + **MTP** (含投机解码, 非裸基线) | MQ2 | 18.99 |
| DwarfStar | Vulkan 主线 | Q2_K | 15.60 |
| **sypherin (v1.1 新增)** | **Vulkan 主线 (build fb30ba9)** | UD-IQ2_XXS (84.6GiB) | **tg32 = 12.24** (pp512 130.17); +DSpark: tg 9.5→9.5 **无加速** |
| (参照) #26578 PR 基线 | Vulkan 主线 | IQ3_XXS | tg = 11.16 (融合前) → 16.77 (融合后, PR 数据) |

来源: [Lucebox 博客](https://www.lucebox.com/blog/deepseek-v4-strix-halo) (同一颗 Ryzen AI MAX+ 395 + 8060S + 128GB; 另有 ~250 t/s 索引稀疏 prefill)。

**对照本集群现状 (v1.1 改写)**: MiniMax-M2.7 双机 RPC 18.2 t/s vs DS4-Flash 单机 Vulkan 主线 ~10~12 t/s → **换模型不升反降**; DSpark 在 Vulkan 实测无增益。提速路径排序: ① #26578 融合算子 (IQ3 decode 11.16→16.77, +50%, Open) ② MTP 轻量草稿 (同机 Qwen3.6-35B-A3B + draft-mtp 实测 ~78 t/s 有效 — DS4 的 MTP 头在 llama.cpp 的支持待验证) ③ Lucebox ROCm 定制路线 (32 t/s, 脱离主线)。

---

## 四、目标模型二: GLM 5.3 Flash (ox-alpha) — 等待合并, 暂不可部署

### 4.1 规格 (Z.ai, 2026-08-26 发布)

| 项 | 值 |
|:---|:---|
| 总参数 / 激活 | **320B (321.3B) / 18B**, 多模态 (文本+视觉) |
| 结构 | 45 层 trunk + MTP 块 (index 45): **34 层 KDA 线性注意力** (Kimi Delta Attention, 复用 kimi-linear/Kimi-K3 路径) + 11 层 DSA 稀疏 MLA (NoPE, kv_lora 512, q_lora 1536) |
| MoE | 288 路由专家 + 1 共享, top-8, sigmoid 门控 |
| 超连接 | mHC (流形约束超连接, DeepSeek-V4 同款 Sinkhorn), 3 thinking 档位 (low/high/max) |
| 上下文 | 1,048,576; 训练 30T token |
| 定位 | 超 GLM-5.2 (1/10 价格), 编码/agent 接近 Claude Opus 4.8 |

### 4.2 llama.cpp 支持状态: 三个 Draft PR 竞争 (2026-08-26 同日提交)

| PR | 作者 | 范围 | 验证状态 | 备注 |
|:---|:---|:---|:---|:---|
| [#27754](https://github.com/ggml-org/llama.cpp/pull/27754) | danielhanchen (Unsloth) | 文本+视觉, 20 commits | CPU 全绿 (0.00e+00); CUDA 上对 641GB BF16 做过 PPL/对话验证; **本分支 CUDA-only 验证** | 需 `NVIDIA_TF32_OVERRIDE=0` + `-fa off` (CUDA 特定); k-pool 池级选择 vs 单元格级选择的隐蔽 bug 已排查 |
| [#27752](https://github.com/ggml-org/llama.cpp/pull/27752) | eauchs | 仅文本 | 未对 HF 数值验证; RTX 5090 上 UD-IQ1_M 可加载并连贯生成 | 大量复用 kimi-linear/dsv4/glm-dsa; 无 MTP 图; `-kvu` 多序列退化 |
| [#27773](https://github.com/ggml-org/llama.cpp/pull/27773) | timkhronos | 文本+视觉 | logits 对齐 transformers; 视觉 ~1e-5; BF16 GGUF 已放 [avar6/GLM-5.3-Flash-BF16-gguf](https://huggingface.co/avar6/GLM-5.3-Flash-BF16-gguf) | 无 MTP; 多序列需 `--kv-unified`; 长上下文 indexer 池键每步重算 (未优化) |

三者均 **Draft, 未合并** (截至 2026-08-28)。Unsloth 官方指南 ([unsloth.ai/docs/models/glm-5.3-flash](https://unsloth.ai/docs/models/glm-5.3-flash)) 指向自家 #27754 分支构建, GGUF 在 [unsloth/GLM-5.3-Flash-GGUF](https://huggingface.co/unsloth/GLM-5.3-Flash-GGUF) ("more quants uploading")。

### 4.3 量化与内存 (v1.1 按 Unsloth 官方量化表重写; v1.0 的 "IQ1_M ~102GB / ~150-200GB" 数字有误)

| 量化 | 体积 | 内存需求 (Unsloth 官方表) | 双机拆分 (A+B 各承担一半) |
|:---|:---|:---|:---|
| BF16 | 641.64GB | 650GB | ✗ |
| **UD-IQ1_S** | **93GB** (保 71% top-1% 精度) | 100GB | ✓ 双机 47GB/站 舒适; 单机边缘 |
| UD-Q2_K_XL | 109GB (保 78%) | 115GB | ✓ 双机 55GB/站; 单机不可 |
| UD-IQ3_XXS | 120GB (保 82%) | **128-150GB** | ✓ 双机 60GB/站; 128GB 单机边缘 |
| UD-Q4_K_XL | 200GB (保 93%) | 162-210GB | ✓ 双机 100GB/站 |

### 4.4 Vulkan/RADV 兼容性风险 (与 DeepSeek V4 Flash 的关键差异)

GLM 5.3 Flash 的 34/45 层是 KDA (`GGML_OP_GATED_DELTA_NET`), 该算子在 Vulkan 上的现状:
- [issue #27638](https://github.com/ggml-org/llama.cpp/issues/27638) (2026-08-27, 未确认): 5 个 Vulkan 驱动横评中 **Intel ANV 最差 (prefill ~O(N²), -ub≥2048 崩溃)**; **RADV 表现中等偏好** (RX 6800 XT: Ling-3.0-tiny 7.9B Q8 上 PP16384 = 406 t/s), 但仍不及 CUDA 的线性扩展。
- [issue #24483](https://github.com/ggml-org/llama.cpp/issues/24483): **RDNA4** (Strix Halo 8060S 即 gfx1151 RDNA4) 大上下文 TG 退化: 50k 上下文 -36% (KV 带宽占 21%, 其余为 L2 thrash + split_k barrier 开销) → GLM 5.3 的 1M 长上下文能力在本机实际会显著折损, 建议按 32k~64k 使用预期。
- 无任何 PR 在 Vulkan 上验证过 GLM 5.3 (三 PR 均 CPU/CUDA 验证) → **首个 Vulkan 部署者即社区首批测试者**, 需自担排查成本。
- 无 MTP/投机解码 (NextN 张量已保留但未接线) → decode 加速只有 **ngram** (零成本, agent/代码负载有效)。

---

## 五、A/B 集群匹配分析与部署方案

### 5.1 内存预算 (Strix Halo 128GB × 2; v1.1 修正草稿体积与判定)

| 方案 | 目标 | 草稿 | KV/buffer | 单站峰值 | 判定 |
|:---|:---|:---|:---|:---|:---|
| B 单机 Vulkan | DS4-Flash IQ2_XXS (84.6GiB) | dspark Q8_0 (~10.1GiB) | @131k 可跑 | ~97GB (实测) | ✓ sypherin 实证 (需 GGML_VK_PREFER_HOST_MEMORY=ON) |
| B 单机 Vulkan | DS4-Flash UD-IQ3_XXS (103GB) | dspark (~10.1GiB) | 小 | ~115GB | ⚠ 边缘 — Unsloth 官方推荐组合, 以实测为准 (v1.1: 原 "溢出" 判定依据不成立) |
| **双机 RPC 拆层** | **DS4-Flash UD-Q3 (103GB)** | dspark B 站本地 | 分摊 | ~58GB/站 | ✓✓ 舒适, 可上大上下文 |
| 双机 RPC 拆层 | DS4-Flash UD-Q8 (162GB, 无损) | dspark | 分摊 | ~87GB/站 | ✓ (prefill 受 RPC 协议拖累) |
| B 单机 Vulkan | GLM-5.3 UD-IQ1_S (93GB) | 无 | +indexer cache | ~100GB | ⚠ 边缘 (IQ1_S 在 Vulkan 上慢) |
| **双机 RPC 拆层** | **GLM-5.3 UD-IQ1_S (93GB)** | 无 | 分摊 | ~47GB/站 | ✓ (等 PR 合并) |

### 5.2 RPC + 投机解码兼容性 (双机方案的前置条件)

| 问题 | 状态 | 影响 |
|:---|:---|:---|
| [issue #23242](https://github.com/ggml-org/llama.cpp/issues/23242): RPC 后端 + draft-mtp/simple 崩溃 (Vulkan 主机 + CUDA RPC 从机, 与本集群同构) | **已修** [#23273](https://github.com/ggml-org/llama.cpp/pull/23273) (2026-05 合入, v0.2.0 已含) | 基本路径可用 |
| [PR #26827](https://github.com/ggml-org/llama.cpp/pull/26827) (Open): MTP catch-up 多 ubatch 竞态, 长 prefill (100k+) 整机锁死, 双后端/tensor-split 必现 | **未修** | 双机 RPC + DSpark 跑长 prompt 时有宿主机锁死风险; 缓解: 限制 prompt 长度 / 监控 / systemd 兜底 (B 站已有) |
| RPC 协议本身 decode 损耗 (每 token 串行跨层传导) | 见《RPC协议瓶颈调研.md》 | v1.1 注: "DSpark 对 RPC 杠杆大于单机"原为假设 — sypherin 实测显示草稿前向成本在带宽受限 iGPU 上即可吃掉全部收益, 且 RPC 场景草稿仍在 B 站本地跑, 收益不必然为正, 待实测 |

### 5.3 性能预期折算 (v1.1 全面改写 — 原表建立在 CUDA 加速倍数外推与含 MTP 榜单成绩之上, 被同硬件实测反驳)

| 配置 | 依据 | decode 预期 |
|:---|:---|:---|
| B 单机 Vulkan, IQ2/IQ3, 裸 AR | sypherin 实测 tg32=12.24 (IQ2_XXS); #26578 基线 11.16 (IQ3) | **~10~12 t/s** (原 "15~19" 系含 MTP/特定 quant 榜单) |
| B 单机 Vulkan, IQ2/IQ3 + DSpark | sypherin 实测 9.5→9.5 | **≈0 增益** (1.5~1.9x 仅 CUDA) |
| B 单机 Vulkan, IQ3 + #26578 融合算子 | PR 实测 11.16→16.77 (1.50x) | **~17 t/s** (PR 合并后) |
| 双机 RPC, Q3 + DSpark | DS4 激活 13B vs M2.7 10B (算力更重); RPC 协议税; DSpark 增益存疑 | **~12~18 t/s** (待实测; 原预期 20~30 下调) |
| GLM 5.3 双机 RPC, IQ1_S + ngram | 无同硬件数据; IQ1_S Vulkan kernel 慢; 34 层 KDA | **未知, 预计 5~12 t/s** (首次测试需自建基线) |

### 5.4 与现有 SOP 的衔接

- 版本: 走 UPGRADE_SOP / DEV-LOG-009 流程; 若 v0.2.0 缺 dspark 则升级 master (RUNPATH patch 流程复用 [fix_runpath_v2.sh](file:///d:/RPC/scripts/fix_runpath_v2.sh))。
- 服务化: 沿用 B 站 llama-server.service systemd 兜底 (Restart=on-failure + A 站 rpc-server 探活 ExecStartPre)。
- 缓存: A 站 rpc-server `-c` + `LLAMA_CACHE` 按模型分目录 (103GB 级模型预填充收益极大, 见瓶颈调研 6.4 节); 磁盘按 v1.1 核实: 模型文件 B 站 103GB + A 站 rpc 缓存 ~52GB (layer split 五五切分, 见瓶颈调研 6.1 修正 3), 非 v1.0 所写 "~110GB×2"。

---

## 六、其他专用加速框架盘点 (对本集群可用性)

| 框架/路线 | 面向硬件 | 对 A/B 集群 | 结论 |
|:---|:---|:---|:---|
| **llama.cpp 内置投机解码** (dspark/dflash/mtp/ngram) | 全后端 | Vulkan/RPC 均支持 (#23273 后) | **✓ 唯一正道, 零额外依赖** |
| **Lucebox** (ROCmFPX 混合量化 + DSV4 专用 HIP kernel + DSpark) | Strix Halo (ROCm 7.2.4, gfx1151) | 同硬件 32 t/s 上限证明; 但为定制 fork, 量化格式自研, 偏离版本化 SOP | ○ 仅作上限基准; 若 Vulkan 路线不达标可评估 |
| **Home-Seek** (RTX 4090 24GB 四级缓存 + Triton MTP) | CUDA | N/A (且仅 1.6 t/s, 无参考价值) | ✗ |
| **GB10 CUDA forks** (Entrpi/ds4, marco.palaferri: 1000 t/s prefill) | NVIDIA DGX Spark CUDA | N/A | ✗ |
| **vLLM / SGLang** | 数据中心 CUDA/ROCm | [nerds-run/strix_halo_vllm](https://github.com/nerds-run/strix_halo_vllm) 实测 DeepSeek-V4-Flash **"EXPERIMENTAL, GATED, DOES NOT CURRENTLY RUN"** | ✗ |
| **Unsloth Desktop / `unsloth run`** | llama.cpp + 自动 offload | 可作为运行时备选, 但核心仍是 llama.cpp + 其 PR 分支 | ○ 备选 |
| **thunderbolt-ibverbs / RDMA RPC** | 传输层 | 见《RPC协议瓶颈调研.md》第三节 (与本文正交, 可叠加) | ○ 中期 |

---

## 七、行动建议

**阶段 0 — 验证 (零下载, 10 分钟)**
1. B 站: `llama-server --help | grep -A2 spec-type` 确认 v0.2.0 含 `draft-dspark`; 缺则按 SOP 升 master。
2. 磁盘盘点: B 站模型 103GB + A 站 rpc 缓存 ~52GB (v1.1 修正, 见 5.4)。

**阶段 1 — 单机试点 (B 站, 优先; v1.1: 定位为质量/容量评估而非提速)**
3. 下载 `unsloth/DeepSeek-V4-Flash-0731-GGUF` 的 **IQ2_XXS 档 (84.6GiB)** + 同源 `dspark-DeepSeek-V4-Flash-0731-Q8_0.gguf` 草稿 (~10.1GiB)。
4. 单机 Vulkan 启动 (不接 RPC, 排除协议变量; **含 sypherin 实测坑位清单 — 草稿必须同源配对 / `--spec-type` 必须精确 `draft-dspark` / 大模型需 host memory 偏好**):

```bash
GGML_VK_PREFER_HOST_MEMORY=ON llama-server \
  -m DeepSeek-V4-Flash-0731-UD-IQ2_XXS-00001-of-00003.gguf \
  -md dspark-DeepSeek-V4-Flash-0731-Q8_0.gguf \
  --spec-type draft-dspark --spec-draft-n-max 3 \
  -ngl 99 -fa 1 -c 32768 --load-mode mmap --jinja
# 误写 draft-dflash 会静默失效 — 用 /slots 确认 speculative: true
```

5. `llama-bench` 对照: 裸 AR vs DSpark vs 现 MiniMax-M2.7 双机 18.2 t/s。**预期 (v1.1): 裸 AR ~10-12 t/s, DSpark 增益≈0** — 本试点的价值是复现/推翻 sypherin 结论 + 评估 284B 质量, 而非提速 (同硬件已有实测, 若结果一致可跳过)。

**阶段 2 — 双机 RPC (通过阶段 1 后)**
6. A 站 rpc-server `-c` 预填充 + B 站 RPC 拆层跑同一模型; **先用 ≤8k prompt 验证 DSpark+RPC 稳定性** (#26827 竞态风险, 长 prefill 需 systemd 兜底并逐步加压)。
7. 若 Q3 档需求质量: 双机拆 UD-Q3 (103GB) 甚至 UD-Q8 无损 (162GB)。

**阶段 3 — GLM 5.3 Flash (被动等待)**
8. GitHub watch [#27754](https://github.com/ggml-org/llama.cpp/pull/27754)/[#27773](https://github.com/ggml-org/llama.cpp/pull/27773); 合并后按 SOP 升级, UD-IQ1_S (93GB) 双机拆分试点 + ngram 投机; 关注 RADV KDA prefill 扩展性 (#27638) 与 RDNA4 长上下文退化 (#24483), 上下文按 32k~64k 规划。

**决策点 (v1.1 更新)**: Vulkan 路线提速的现实预期是 ~17 t/s (#26578 合并后), 仍低于现 MiniMax 双机 18.2 t/s — 若对速度有硬需求, Lucebox ROCm 路线 (32 t/s 上限) 从 "备选" 升为 "唯一实测大幅提速路径", 代价是脱离主线版本管理; 否则维持 MiniMax 日常 + DS4-Flash 按质量/长上下文场景选用。

---

## 八、参考来源

1. [DSpark: Confidence-Scheduled Speculative Decoding with Semi-Autoregressive Generation (arXiv 2607.05147)](https://arxiv.org/pdf/2607.05147.pdf)
2. [llama.cpp PR #25173 — spec: add DSpark speculative decoding](https://github.com/ggml-org/llama.cpp/pull/25173)
3. [llama.cpp PR #22105 — DFlash (NVIDIA)](https://github.com/ggml-org/llama.cpp/pull/22105) / [The Agent Times 报道](https://www.theagenttimes.com/articles/llama-cpp-adds-dflash-speculative-decoding-in-nvidia-backed--0e1f0008)
4. [Unsloth — DeepSeek-V4 本地运行指南 (含 DSpark GGUF 用法与量化分析)](https://unsloth.ai/docs/zh/mo-xing/deepseek-v4)
5. [Lucebox — DeepSeek V4 Flash 32 tok/s on Ryzen AI MAX+ 395 (LocalMaxxing)](https://www.lucebox.com/blog/deepseek-v4-strix-halo)
6. [tinycomputers.io — Running DeepSeek V4 Flash on AMD Strix Halo](https://tinycomputers.io/posts/running-deepseek-v4-flash-on-amd-strix-halo.html)
7. [llama.cpp PR #27754 — model: add GLM-5-Next (GLM-5.3-Flash), Unsloth](https://github.com/ggml-org/llama.cpp/pull/27754)
8. [llama.cpp PR #27752 — model: add GLM-5.3-Flash (glm5next)](https://github.com/ggml-org/llama.cpp/pull/27752)
9. [llama.cpp PR #27773 — add GLM-5.3-Flash (GLM5-Next) support](https://github.com/ggml-org/llama.cpp/pull/27773)
10. [Unsloth — GLM-5.3-Flash 指南](https://unsloth.ai/docs/models/glm-5.3-flash)
11. [llama.cpp issue #27638 — Vulkan KDA (GATED_DELTA_NET) prefill 扩展性与驱动横评](https://github.com/ggml-org/llama.cpp/issues/27638)
12. [llama.cpp issue #24483 — RDNA4 大上下文 TG 退化](https://github.com/ggml-org/llama.cpp/issues/24483)
13. [llama.cpp issue #23242 / PR #23273 — RPC + 投机解码崩溃与修复](https://github.com/ggml-org/llama.cpp/issues/23242)
14. [llama.cpp PR #26827 — MTP 多 ubatch 竞态 (Open)](https://github.com/ggml-org/llama.cpp/pull/26827)
15. sypherin/strix-halo-setup — [docs/deepseek-v4-flash-284b.md](https://github.com/sypherin/strix-halo-setup/blob/master/docs/deepseek-v4-flash-284b.md) (v1.1: 原引注 "124GiB 可见 / GTT 108GiB cap 实测" 未在该仓库文档中找到, 已作废; 该仓库的实际价值是上条 18 的实测文档)
16. [nerds-run/strix_halo_vllm — vLLM 路线状态](https://github.com/nerds-run/strix_halo_vllm) / [QingGo/home-seek — RTX 4090 路线](https://github.com/QingGo/home-seek)
17. [NVIDIA GB10 论坛 — DSpark on DeepSeek-V4-Flash (CUDA 生态参考)](https://forums.developer.nvidia.com/t/optimizing-deepseek-v4-flash-on-a-single-nvidia-gb10-gx10-with-dspark-speculative-decoding/376830)
18. [sypherin/strix-halo-setup docs/deepseek-v4-flash-284b.md — **Vulkan 主线同硬件实测 (tg32=12.24) + DSpark 无加速结论 + 三个配对陷阱 (v1.1 审计新增的关键反证来源)**](https://github.com/sypherin/strix-halo-setup/blob/master/docs/deepseek-v4-flash-284b.md)
