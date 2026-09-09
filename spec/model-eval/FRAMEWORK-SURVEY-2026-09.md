# 推理框架选型调研（Strix Halo 集群，2026-09-08）

> **调研人**: Scott ｜ **触发**: A/B/C 三站 V4-Flash Vulkan 加载 4 次 kernel panic，需换框架
> **范围**: 不局限于 llama.cpp RPC；聚焦能稳定运行 V4-Flash / GLM-5.3-Flash 规模模型（~150-320G）的框架
> **⚠️ 2026-09-08 归因修正**: 4 次崩溃根因 = **单机/本机持有 146G > 124G（算术超限）**，与 Vulkan 无关。本集群 9/1 已用 **llama.cpp RPC 双机层分布**（9859 + Q4 145G）成功跑通——**llama.cpp Vulkan RPC 仍是本集群首选路线**；DwarfStar/vLLM 为替代/增强选项（本调研仍有效，供性能与 GLM 支持参考）
> **结论先行**: **llama.cpp RPC 层分布（复现 9/1 形态）为首选**；DwarfStar (ds4) ROCm 为 GLM-5.3-Flash 备选（vLLM sm_121 有输出 bug 排除）

---

## 1. 背景：为什么换框架

llama.cpp RPC + Vulkan 在 Strix Halo（本集群 A/B/C）加载 V4-Flash-0731（146G MXFP4）**4 次 kernel panic**（详见 [V4-Flash-0731加载崩溃根因分析_20260908.md](../docs/V4-Flash-0731加载崩溃根因分析_20260908.md)）。社区 evidence 显示 Vulkan 后端在 Strix Halo UMA 只能用 ~43G（beowulf #2），**Vulkan 路线不可行**。本调研评估替代框架。

## 2. 框架全景矩阵

| 框架 | 后端 | 分布式能力 | V4-Flash | GLM-5.3-Flash | 部署成本 | 判定 |
|---|---|---|---|---|---|---|
| **DwarfStar (ds4)** | **ROCm/Metal/CUDA** | TP（Metal）+ **PP 层切片（ROCm）** | ✅ 原生 | ✅ 5.2/5.3/5.3-Flash | **低**（make strix-halo） | ⭐ 首选 |
| **vLLM** (kyuz0/AlexKGwyn) | ROCm | **TP=2 RCCL 跨机**（OdinLink RDMA） | ✅ | ✅ | 高（patched 镜像+驱动） | ⭐ 备选 |
| SGLang | ROCm（sglang-rocm） | 多节点 | ✅ 官方 cookbook | 待验证 | 中 | 中 |
| llama.cpp RPC | Vulkan/ROCm | 层分布 | 架构支持 | glm5next 未合入 | 已部署 | ❌（4 崩实证） |

## 3. DwarfStar (ds4) 详情

### 3.1 为什么是它
- **antirez（Redis 作者）专为 V4-Flash 写的专用引擎**，自包含、刻意窄化（非通用 GGUF runner）
- 支持模型：**DeepSeek V4 Flash / PRO、GLM 5.2 / 5.3 / 5.3-Flash**（架构专用内核）
- 后端：Metal（主力）/ CUDA（含 DGX Spark）/ **ROCm（Strix Halo gfx1151 官方目标）**/ CPU
- **绕开 llama.cpp Vulkan UMA 缺陷**——用 ROCm + rocWMMA 原生内核

### 3.2 构建（STRIXHALO.md 官方指南）
```bash
# ROCm 依赖
sudo apt-get install hipcc rocminfo rocm-smi libamdhip64-dev libhipblas-dev \
  libhipblaslt-dev librocblas-dev librocwmma-dev libhipcub-dev
# rocWMMA internal headers 需手动补（Ubuntu 包缺失）
# 内核参数（关键！与 llama.cpp 差异不大）
amd_iommu=off amdgpu.gttsize=126976 ttm.pages_limit=32505856 ttm.page_pool_size=32505856
# 构建
make strix-halo -j$(nproc)   # make rocm 别名
# 运行
./ds4 -m <GGUF>   # 自动用 ROCm 后端
```

### 3.3 分布式（社区 fork 实测）
- [wkljohn/ds4-strix-halo-tp-odinlink](https://github.com/wkljohn/ds4-strix-halo-tp-odinlink)：官方 TP 仅 Metal；此 fork **移植到 ROCm + 加 OdinLink RDMA**
- 2× Strix Halo 跑 V4-Flash **Q4_K 153.32GiB**（94.7% 路由专家），**expert 50:50 分片**，每机 shard 80.76GiB，生成只传激活
- **实测（OdinLink TB5）**：prefill 231-233 t/s / **生成 19.1-19.2 t/s**；RoCE v2 18.2-20.4 t/s
- **⚠️ 警告**：混合 IQ2/IQ4 GGUF 会触发系统 OOM（非干净失败）→ 须用官方 imatrix 单一档（如 IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8）
- **⚠️ 内核必须**：无 `amd_iommu=off amdgpu.gttsize=126976` 模型不加载（社区复现）

### 3.4 kyuz0 ds4-toolbox（预编译容器）
- `kyuz0/strix-halo-ds4-toolbox:rocm-10.0`（Toolbx/Distrobox）
- **支持分布式 PP（层切片）**：coordinator + workers，可指定每机层
- 含 ds4-cockpit TUI 管理

## 4. vLLM 路线（备选）

- [kyuz0/amd-strix-halo-vllm-toolboxes](https://github.com/kyuz0/amd-strix-halo-vllm-toolboxes)：ROCm 10.0 + vLLM，**两主机 RCCL TP=2 已测（Ethernet + RDMA/RoCE）**
- [AlexKGwyn/ds4-vllm](https://github.com/AlexKGwyn/ds4-vllm)：**2× Strix Halo + OdinLink RDMA + DSpark MTP**，实测 decode **23 t/s（prose）/ 32 t/s（code）**（ctx 512-100k 全档）
- 工程成本：patched vLLM 镜像 + OdinLink 内核驱动（libibverbs 实现）+ RCCL 配置——**重**，且大量 AI 生成 patch 需验证

## 5. 与本集群（A/B/C 环网）适配评估

| 维度 | DwarfStar (ds4) | vLLM+OdinLink |
|---|---|---|
| 部署成本 | **低**：`make strix-halo`；C 站 ROCm 7.2.1 用户态已备（DEPLOYMENT O4） | 高：patched 镜像 + OdinLink 驱动 + RCCL |
| 三站支持 | PP 层切片（kyuz0 支持 coordinator+workers） | TP=2 验证过（3 站需 TP=3 验证） |
| 环网适配 | TB5 已验证（本站 A/B/C 环网同构） | OdinLink RDMA 已验证 |
| 模型覆盖 | **V4-Flash / GLM-5.3-Flash / PRO 全系** | V4-Flash 主 |
| 稳定性 | 专用引擎 + 社区验证充分 | 大量 AI 生成 patch 需自证 |
| 已有资产 | C 站 ROCm 7.2.1 + 6.17 内嵌 KFD | — |

**判定（归因修正后）**：**llama.cpp RPC 层分布（复现 9/1 成功形态）为本集群首选**——9/1 已用 9859 + 双机层分布跑通 m2.7(121G)/v4-flash(145G Q4)，成本为零（无需换框架）。DwarfStar (ds4) ROCm 为 **GLM-5.3-Flash 备选**（vLLM sm_121 有输出 bug 排除），若 RPC 层分布在 GLM 上验证受阻再启用。两路线均与现有环网（TB5/USB4 9.2Gbps）匹配。

## 5a. 性能对比：DwarfStar TP fork vs vLLM TP=2（2026-09-08 补）

**场景**：2× Strix Halo，V4-Flash Q4_K（153G，expert 50:50 分片）

| 方案 | 后端 | 网络 | decode | prefill | 备注 |
|---|---|---|---|---|---|
| **DwarfStar TP fork**（wkljohn） | ROCm + OdinLink RDMA | TB5 | **19.1-19.2 t/s** | 231-233 t/s | 统一数值；DSpark 加速正在集成（8/10 commit） |
| **vLLM TP=2 + DSpark**（AlexKGwyn） | ROCm | OdinLink RDMA | **23 t/s prose / 32 t/s code** | ~191-300 t/s | 收益主要来自 DSpark 投机解码（代码 draft 命中率高） |

**解读**：vLLM 的 decode 优势（23-32 vs 19）主要来自 **DSpark 投机解码**；纯 AR 下两者约同级。DwarfStar TP fork 正在集成 DSpark（合入后差距收窄）。**两方案均与本站环网（TB5/USB4 9.2Gbps）匹配**。

## 5b. GLM 架构支持矩阵（2026-09-08 补）

| 框架 | GLM-5.2 | GLM-5.3-Flash (glm5_next) | 状态 |
|---|---|---|---|
| **DwarfStar 官方主分支** | ✅ | ✅（下载脚本含 glm53-q2/q4/fp8 档） | **已支持（PP 分布式）** |
| **DwarfStar TP fork**（wkljohn） | 继承官方 | 🔨 **开发中**：`ds4_glm5_next_exec/runtime/state.c` + KDA 内核（8/27-9/3 活跃提交） | 未稳定，可跟进不可依赖 |
| **vLLM** | ✅ | ❌ **main 未支持**：`glm5_next` 需 fork [ZJY0516/vllm glm-release 分支](https://github.com/ZJY0516/vllm)，PR [vllm#53906](https://github.com/vllm-project/vllm/pull/53906) in-flight | 需 fork |
| **vLLM sm_121 (Strix Halo) 陷阱** | — | ❌ **输出错误**（回声 prompt）：`pe_dim==64` kernel 断言与 GLM NoPE（`qk_rope_head_dim=0`）不兼容；SGLang TileLang DSA 有 `tail_dim==0` 专用内核才正常 | ⚠️ 关键坑 |
| **SGLang** | ✅ | ✅ 官方支持 + sm_121 有专用 kernel | 依赖重，需验证 |

**对本集群判定**：
- **V4-Flash**：vLLM TP=2 + DSpark 性能领先（23-32 t/s）；DwarfStar TP 次之（19 t/s 稳定）
- **GLM-5.3-Flash**：**DwarfStar 官方 PP 是当前唯一本集群可行路线**（llama.cpp 不支持 + vLLM sm_121 输出 bug 排除；TP fork GLM 未稳）
- **若两模型都要**：DwarfStar 为主线（V4 用 TP/PP，GLM 用官方 PP），vLLM 仅作 V4-Flash 性能补充

### 5b.1 GLM-5.3-Flash 在 llama.cpp 的支持现状（2026-09-08 三重来源确认）

**直接回答：llama.cpp 当前无法加载 GLM-5.3-Flash**（无论 Vulkan/ROCm 后端，stock 构建均报 `unknown architecture 'glm5next'`）。

| 证据 | 状态 |
|---|---|
| [PR #27754](https://github.com/ggml-org/llama.cpp/pull/27754)（unsloth 官方，40 commits，含 MTP 投机解码实测 16K ctx 55→77.2 t/s） | 🔴 **Open 未合入**（fetch 原页确认） |
| [PR #27752](https://github.com/ggml-org/llama.cpp/pull/27752)（eauchs，文本 only） | 🔴 Open 未合入 |
| [PR #27773](https://github.com/ggml-org/llama.cpp/pull/27773)（timkhronos，文本+视觉） | 🔴 Open 未合入 |
| [dev.to 实测](https://dev.to/purpledoubled/run-glm-53-locally-real-quant-sizes-the-llamacpp-surprise-and-the-reasoningeffort-trap-2nmg)（9/5） | `glm5next` **仍不在 main 分支**（9/2 核）；GLM-5.3 旗舰（glm-dsa）stock 可跑，**Flash 不行** |
| [orcarouter GGUF](https://www.toolify.ai/ai-model/orcarouter-glm-5-3-flash-uncensored-gguf)（9/1） | 「直到 PR 合入需从 PR 分支构建；老运行时报 unknown architecture」 |

**启用路径**：

| 路径 | 说明 | 风险 |
|---|---|---|
| **A. 等 PR 合入 main** | 事件驱动（unsloth #27754 首选）→ 合入后重建 A/B/C 引擎 → Vulkan RPC 层分布 | 无（等合入） |
| **B. 用 PR 分支自建** | `git clone -b glm5next/upstream unslothai/llama.cpp` + `-DGGML_VULKAN=ON -DGGML_RPC=ON` | ⚠️ ①#27754 仅 CUDA 验证（B200），**Vulkan 未验证**（GLM mHC 继承 DSV4 超连接 → Vulkan 可能踩 HC 非融合慢路径）；②RPC 分布式未验证（[#28047](https://github.com/ggml-org/llama.cpp/issues/28047) RPC 大 MoE 有崩溃风险） |

**预期档位**（合入后）：UD-Q4_K_XL 199.7G（三站）/ UD-IQ4_XS 156.8G（双站）/ UD-Q2_K_XL 108.7G（单机）

**结论**：GLM-5.3-Flash 在 llama.cpp 维持「条件未满足、等待」——①#27754 合入 ②Vulkan 验证 ③RPC 验证，三者齐备再评估。当前分布式首选仍是 V4-Flash（deepseek4 已支持）；急用 GLM-5.3-Flash 走 DwarfStar（官方已支持）。

## 5c. llama.cpp Vulkan RPC 社区实测补充（2026-09-08）

### 5c.1 与本站同构的权威实测：双 Strix Halo + USB4 RPC

[visorcraft/strix-halo-llm-perf](https://github.com/visorcraft/strix-halo-llm-perf)（GMKtec EVO-X2 + Beelink GTR9 Pro，双 Ryzen AI Max+ 395 / 128G×2 / USB4 直连 ~9.4Gbps —— **与本站 A/B/C 环网完全同构**）：

**单机 Vulkan 性能**（llama-bench）：

| 模型 | 体积 | pp512 | tg128 |
|---|---|---|---|
| Qwen3-Coder-Next 80B-A3B Q4_K_M | 45G | 531 | **42.7** |
| GPT-OSS 120B Q4_K_M | 58.5G | 120 | **53.4**（llama-server） |
| MiniMax M2.5 Q3_K_M（228.7B） | 101.8G | 156 | **32.8** |
| Qwen3-235B-A22B Q3_K_M | 104.7G | 101 | **17.2** |
| Nemotron-3 Nano 30B MXFP4 | 17.6G | 112 | **61.5** |

**双机 RPC 实测**：

| 模型 | 后端 | 分片 | pp512 | tg128 | 备注 |
|---|---|---|---|---|---|
| MiniMax-M2.5-REAP-139B-A10B Q8_0 | ROCm+RPC | 1.2/0.8 | 332 | **15.35** | 快速分片扫描最优 |
| Qwen3.5-397B-A17B-UD-Q4_K_XL | ROCm+RPC | auto | 147.6 | 11.76 | llama-bench 路径 |
| Qwen3.5-397B-A17B-UD-Q4_K_XL | ROCm+RPC + `-dio` | 1/1 | 25.9 | **12.6** | llama-server 路径 |

**⚠️ 关键结论（与本站崩溃直接相关）**：该 repo 明确标注——
> **「Critical: for `llama-server`/`llama-cli` with `--rpc` on large models, use `-dio` (direct I/O) to avoid load hangs」**

**Qwen3.5-397B（205G）经 `-dio` 在双机 RPC 成功加载并 12.6 t/s 生成**——这是社区对「大模型 + RPC + `-dio`」最直接的实证，**与本站 4 次崩溃的对照**：本站崩溃发生在「单机/本机持有 146G」（未走 RPC 分布），而社区成功案例全是「RPC 分布 + `-dio`」（每机 ~73-102G）。

### 5c.2 Vulkan vs ROCm 后端性能（gfx1151 社区横评）

| 来源 | 结论 |
|---|---|
| [nabe2030 HIP vs Vulkan](https://github.com/nabe2030/hip-vs-vulkan-evo-x2)（ROCm 7.2.2 + Ubuntu 26.04） | **无单一赢家**：长 prompt（RAG/摘要）HIP 快 **+42~48%**；长生成（chat/创作）**Vulkan 快 +13~19%**；质量两后端**一致** |
| [llama.cpp #27154](https://github.com/ggml-org/llama.cpp/discussions/27154)（spec-decode 负载） | 投机解码场景 **ROCm 约为 Vulkan 2 倍**（TG 94.7-98.5 vs 48.8-50.2；prefill -36%）——**Vulkan 在 spec-decode 上弱** |
| [Skulk #144](https://github.com/Foxlight-Foundation/Skulk/issues/144)（2026-05） | **Vulkan (RADV) 是 gfx1151 首选**（pp881/tg52.8，无 HSA workaround）；**ROCm 7.x 在 gfx1151 是回归**（325 vs 1132 t/s，用 6.4.4 才行） |
| [infoedu（ROCm 运维实战）](https://infoedu.co.kr/posts/ai/xgen/llama-cpp-server-ops-story-rocm-gpu-troubleshoot-fix/) | ROCm page fault 崩溃 → `--fit off` + 关 FA → **最终转 Vulkan 解决** |

**对本集群启示**：
- **Vulkan 后端在 gfx1151 完全可用且是社区推荐路径**（Skulk 首选；infoedu 从 ROCm 转 Vulkan 兜底）——再次印证本站崩溃非 Vulkan 问题
- **Vulkan 强在长生成（tg），弱在长 prompt（pp）和 spec-decode**——本站日常单机推理用 Vulkan 是合理选择
- 若追求 pp/spec 性能，ROCm（6.4.4 或 7.2.2）是增强选项，但需接受编译与稳定性成本

### 5c.3 模型支持范围（Vulkan RPC 已实证）

| 模型 | 规模 | 本站验证 |
|---|---|---|
| MiniMax-M2.5/M2.7 | 139-229B | ✅ 本站 9/1 跑通 121G Q4（tg 19.7） |
| DeepSeek-V4-Flash | 284B | ✅ 本站 9/1 跑通 145G Q4（tg 6.3） |
| Qwen3.5-397B | 397B | ✅ 社区双机 205G Q4 跑通（12.6 t/s） |
| GPT-OSS 120B / Nemotron-3 Nano | 120B/30B | ✅ 社区单机 53-61 t/s |
| GLM-4.7 | 358B | ✅ AMD 官方 playbook 双机 RPC 205G 跑通 |

**结论**：llama.cpp Vulkan RPC 对本站目标模型（V4-Flash/GLM-5.3-Flash 规模）的支持**已被社区和本站双重验证**，正确用法 = **RPC 层分布 + `-dio`（大模型加载）+ 每机只持部分层**。

### 5c.4 本站 9/1 成功基线引擎溯源（9859）

**9/1 跑通 m2.7/v4-flash 的引擎 = `/opt/llama.cpp-9859`（/opt 最早构建）**，三方证据一致：

| 来源 | 记录 |
|---|---|
| 文档 [分布式推理.md L562](file:///d:/RPC/docs/分布式推理.md) | version 9859 (commit 4fc4ec554)，RPC v4.0.1，2026-07-02 构建 |
| 实物 `/opt/llama.cpp-9859/` | `libllama.so.0.0.9859` 版本号硬编码，full 工具链 + MANIFEST |
| 用户记忆 | /opt 老版本 = 最早版本 |

**/opt 版本时间线**：9859（7/2 最早）→ v0.2.0（8/28）→ master-d2e206c4 v0.3.0（8/31，**当前 symlink 指向**）。

**复现 9/1 时的引擎选择**：
- **9859**（v4.0.1）= 9/1 实证成功基线，零新变量
- **master**（v0.3.0）= 新增 ds4 算子 + lightning indexer + RPC v6.0.0，但**未在成功分布式运行中验证**——属新变量
- ⚠️ symlink 现指向 master，直接走文档 symlink 路径实跑的是 master 而非 9859（见 [崩溃根因分析 §4.1b](file:///d:/RPC/docs/V4-Flash-0731加载崩溃根因分析_20260908.md)）

## 6. 落地路线图（待三站恢复后执行）

| 步骤 | 动作 | 备注 |
|---|---|---|
| 1 | B/A/C 恢复 18081 常规服务 | P0，恢复日常推理 |
| 2 | 验证 ROCm 状态：`rocminfo` gfx1151 + KFD（对齐 DS4 需要） | C 站已有 7.2.1；A/B 待查 |
| 2b | **验证 Vulkan RPC 层分布 + `-dio`（社区实证优先路线，§5c）** | visorcraft 实证：大模型 RPC 必须 `-dio`；每机只持部分层 |
| 3 | 内核参数对齐：`amdgpu.gttsize=126976`（现 120000） | 与 STRIXHALO.md 官方一致 |
| 4 | B 站构建 ds4（`make strix-halo`）| 或直接拉 kyuz0 ds4-toolbox 容器 |
| 5 | 下载官方 imatrix GGUF（IQ2XXS ~81G 或 Q2K）| 单机档先验证（81G < 124G） |
| 6 | 单机 ds4 验证 → 三站 PP 切片（coordinator+2 workers）| 渐进，防再崩 |
| 7 | 三站实测对比基线（目标 >19 t/s）| 对照 Lucebox 32 t/s / vLLM 23-32 t/s |

## 7. 佐证来源

- [antirez/ds4](https://github.com/antirez/ds4)（README + STRIXHALO.md + QA_BEFORE_RELEASES.md）
- [AMD 官方 playbook: Running DeepSeek V4 Flash with ds4](https://developer.amd.com/playbooks/deepseek-v4-flash-ds4/)
- [jarvis-ai: 双 Strix Halo TB5 实测 19-20 t/s](https://www.jarvis-ai.cz/dva-strix-halo-propojene-kabelem-amd-ukazuje-cestu-k-lokalni-deepseek)
- [wkljohn/ds4-strix-halo-tp-odinlink](https://github.com/wkljohn/ds4-strix-halo-tp-odinlink)（ROCm TP fork）
- [kyuz0/strix-halo-ds4-toolbox](https://github.com/kyuz0/strix-halo-ds4-toolbox)（PP 分布式容器）
- [kyuz0/amd-strix-halo-vllm-toolboxes](https://github.com/kyuz0/amd-strix-halo-vllm-toolboxes)（vLLM TP=2）
- [AlexKGwyn/ds4-vllm](https://github.com/AlexKGwyn/ds4-vllm)（vLLM 2-box 实测 23-32 t/s）
- [SGLang DeepSeek-V4 cookbook](https://docs.sglang.io/cookbook/autoregressive/DeepSeek/DeepSeek-V4)
- [OdinLink (Thunderbolt 5 RDMA)](https://github.com/Geramy/OdinLink-Five)
- [AlexKGwyn/ds4-vllm 2-box 实测](https://github.com/AlexKGwyn/ds4-vllm)（decode 23-32 t/s）
- [jarvis-ai 双 Strix Halo 实测](https://www.jarvis-ai.cz/dva-strix-halo-propojene-kabelem-amd-ukazuje-cestu-k-lokalni-deepseek)（DwarfStar TP 19.1-19.2 t/s）
- [marksunner 双 DGX Spark 基准](https://github.com/marksunner/dgx-spark-ds4-benchmark)（PP 192K ctx 稳定）
- [LibertAIDAI GLM-5.3-Flash-NVFP4](https://huggingface.co/LibertAIDAI/GLM-5.3-Flash-NVFP4)（vLLM sm_121 输出 bug / SGLang 验证）
- [horadecodar GLM-5.3-Flash runtimes](https://horadecodar.com.br/glm-53-flash-local/)（vLLM glm5_next 未入 main）
- [visorcraft/strix-halo-llm-perf](https://github.com/visorcraft/strix-halo-llm-perf)（双 Strix Halo + USB4 RPC，与本站同构；`-dio` 大模型加载铁律）
- [nabe2030 HIP vs Vulkan](https://github.com/nabe2030/hip-vs-vulkan-evo-x2)（gfx1151 两后端工作负载交叉）
- [llama.cpp #27154](https://github.com/ggml-org/llama.cpp/discussions/27154)（spec-decode 两后端对比）
- [Skulk #144](https://github.com/Foxlight-Foundation/Skulk/issues/144)（Vulkan 为 gfx1151 推荐路径）
- [infoedu ROCm 运维实战](https://infoedu.co.kr/posts/ai/xgen/llama-cpp-server-ops-story-rocm-gpu-troubleshoot-fix/)（ROCm→Vulkan 兜底）
- [AMD 官方 RPC 集群 playbook](https://developer.amd.com/playbooks/clustering-rpc-server/)（GLM-4.7 双机 RPC）