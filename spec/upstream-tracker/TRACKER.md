# 上游跟踪台账：llama.cpp PR/Issue 状态 + 集群引擎基线（单一真源）

***

id: upstream-tracker
type: tracker
version: 1.4
status: active（维护中）
date: 2026-09-08（**1.4 更新 2026-09-16：新建 §1.5「待评估事项」动作队列（EV-1…EV-6）+ 分布式路线可行性调研落档**（[调研文档](../../docs/research/2026-09-16_分布式推理路线可行性调研_CIRU-Skulk-多机TP.md)）—— 用户要求把两个待定动作入队，并评估 CIRU/StrixLink 与 Skulk；结论：Skulk 已确认但后端即 llama.cpp（不改上游事实）且与"零自加载/看门狗禁用/唯一管理面"冲突、CIRU 部分确认（GLM-5.3 构建未证实、无多机声明）、**StrixLink 三轮检索未命中 ⇒ 不予评估（需来源）**，另带出 vLLM 多机 TP（需 100GbE）与 AMD 官方 playbook 两条。**1.3 更新 2026-09-16：新增 §1.4「分布式推理相关 PR 集中索引」** —— 核查发现 V4 侧已有层级标注、GLM 侧散落未标注，且两模型均缺 4 条关键条目；集中补录 #26490（V4 `-sm tensor` 主体，Merged 8/24，现役已含）/ #27825（HIP AllReduce，Merged 9/15，现役不含）/ #28360（GLM-5.3 的 RPC issue，报告者第二机为 **GFX1151 同架构**）/ #27311（调度器 UMA ring buffer，活跃）。1.2 更新 2026-09-16: GLM 首选线 #27754 → 45c 且 `mergeable_state=unstable` + 当日有活动 = 9/13 以来首个「接近可合并」信号，仍未合入。1.1 更新 2026-09-10: #26578 实测落地）
depends: [vulkan-version-control-UPGRADE_SOP v1.0, operator-optimization-DESIGN v1.1, model-eval-MODEL-SOURCING v1.0]

> **用途**: 本集群所有「上游活数据」的**单一真值台账**——llama.cpp 相关 PR/Issue 合并状态、引擎基线（各构建目录/现役实例/版本）、以及上游变动对集群的触发动作。**状态变更必须回写本表，禁止散落各处**。
> **背景**: 2026-09-08 交叉核实时发现同一 PR 状态在 4+ 文档重复维护且新旧不一（GLM-5.3-Flash 曾从 3 PR 扩到 4 PR 而 docs 未同步）；现役引擎存在 3 套构建目录且文档记载（b10715/v0.3.0）与实际运行进程（0d18aaa 系）不一致。
> **关闭标准**: 条目失效（PR merged 且集群已升级并验证）→ 移入「已关闭」区；引擎基线随每次 UPGRADE_SOP 升级原子更新本表。
> **核查仪式**: 每次会话触碰本表主题 → 先看 `last-checked`；> 2 天则 fetch 上游核对（fetch 原页，不依赖二手转述）；状态变化只改本表 + 在相关调研文档留一行『状态见 tracker』链接。

***

## 1. llama.cpp 上游 PR/Issue 跟踪

### 1.1 GLM-5.3-Flash（glm5next 架构）——通用

| PR/Issue | 作者 | 内容 | 状态 | 对本集群影响 | 触发动作 |
|---|---|---|---|---|---|
| [#27754](https://github.com/ggml-org/llama.cpp/pull/27754) | danielhanchen（unsloth） | 文本+视觉 **45 commits / 42 files**（9/13→9/16 **+2**）；含 MTP 投机解码（16K ctx 55→77.2 t/s）；两前置 flag：`NVIDIA_TF32_OVERRIDE=0` + `-fa off`；分支 `unslothai:glm5next/upstream` | 🟠 **Open，`mergeable_state=unstable`，9/16 有活动**（9/13 起首个「接近可合并」信号，**仍未合入**） | 首选候选（unsloth 官方，vision+MTP） | **状态转 `clean` 且获 reviewer 批准 → 立即评估选向** |
| [#27752](https://github.com/ggml-org/llama.cpp/pull/27752) | eauchs | 文本 only **11 commits**（未变）；KDA 线性注意力映射 kimi-linear，mHC 沿用 DSV4；`mergeable_state=dirty` | 🔴 Open（9/16 复核，11c / 更新 9/11 / **dirty=有冲突**） | 最简文本线 | 合并 → 评估 |
| [#27773](https://github.com/ggml-org/llama.cpp/pull/27773) | timkhronos | 文本+视觉 **46 commits**；logits 对齐 HF；quantized GGUF 已发布（avar6/GLM-5.3-Flash-BF16-gguf）；`mergeable_state=dirty` | 🔴 Open（9/16 复核，46c / 更新 9/12 / **dirty**） | 视觉备选 | 合并 → 评估 |
| [#27917](https://github.com/ggml-org/llama.cpp/pull/27917) | timkhronos | MTP draft head（NextN），31 commits，依赖 #27773，含 index_share_forward，`--spec-type draft-mtp` 启用；`dirty` | 🔴 Draft（9/16 复核，31c / 更新 9/11） | 仅随 #27773 | — |
| [#27922](https://github.com/ggml-org/llama.cpp/issues/27922) | mirek-vl | **"Feature Request: Support GLM5.3 (flash)"** —— 主线 `unknown architecture 'glm5next'` 佐证（mmproj 加载失败 + UD-Q2_K_XL 文本加载失败双证） | 🔴 Open（9/16 复核，更新 9/11） | 确认主线未合 | 关闭即该来信号 |
| [#28282](https://github.com/ggml-org/llama.cpp/issues/28282) ⭐新 | —— | **CUDA illegal memory access on GLM-5.3-Flash 长 prefill（`-ub 2048`, Blackwell/sm_120）**；作者自述"built from PR #27754 HEAD，只能在 PR 分支上测"；label `bug-unconfirmed`，2 评论 | 🟡 Open（9/16 复核，创建 9/2 / **更新 9/15**） | **对我们无关键**（本集群 Vulkan/gfx1151，非 CUDA sm_120），但提示 **#27754 线的长 prefill 侧仍有未确认 bug** | 合并后评估时**必须压测长 prefill**，勿只看 decode |
| [#28727](https://github.com/ggml-org/llama.cpp/pull/28727) / [#28729](https://github.com/ggml-org/llama.cpp/pull/28729) ⭐新 | AIalliAI | `glm5next: avoid soft_max gridDim.y overflow in the indexer`（同分支两次提交，45c/42 files，`mergeable=clean`） | ⚫ **Closed 未合并**（9/11）—— 该修复**未进任何线** | GLM indexer 的 soft_max 溢出问题被提出但无人承接 | 观察：若 GLM 线合并后长 prefill 有异常，先查此项 |
| [#28106](https://github.com/ggml-org/llama.cpp/issues/28106) ⭐新 | —— | `glm5next: resolve_fused_ops validates device placement but not tensor …`（op 校验器只查设备位置、不查 tensor —— 正对应我们实测过的 HC `resolve_fused_ops` 警告路径） | 🟡 Open（创建 8/31，本次核查补录） | 解释"HC 融合警告"一类现象的上游视角 | 与 #28144（SOFT_MAX failed）同批观察 |

**结论（2026-09-16 核查）**: glm5next **仍未合入 master**，但出现 **9/13 以来第一个「接近可合并」信号** —— **#27754（unsloth 首选线）45c + `mergeable_state=unstable` + 9/16 当日有活动**（此前三线全 Open 且无活动）；另两线为 46c（#27773，9/12 后未动，`dirty`）与 11c（#27752，`dirty`），#27917 仍 Draft。**新增风险面两条**：① **#28282** 报告在 **#27754 HEAD 上长 prefill（`-ub 2048`）出现 CUDA 非法访存**（`bug-unconfirmed`，非本集群后端，但说明该线**长 prefill 侧未验证**）；② 针对 GLM indexer `soft_max gridDim.y` 溢出的修复 **#28727/#28729 双双 closed 未合并**（无人承接）⇒ 若合并后长 prefill 异常，**先查此项**。**判定**：GLM-5.3-Flash 本地部署**维持等待**，事件驱动前置维持**三变二**不变（① 任一 PR 合并；② RPC crash 已由 #26500 修复，前置满足；③ 可选与 #26610 同窗原子升级），并**新增一条预警触发**：`#27754 转 clean + reviewer 批准` → 即启动评估环境准备（不必等合并）。 [行为快照追溯](file:///d:/RPC/spec/model-eval/FRAMEWORK-SURVEY-2026-09.md)（附录 H.4，原 docs/GLM-5.3-Flash-分布式部署调研并入）｜[模型选型](file:///d:/RPC/spec/model-eval/MODEL-SOURCING-2026-09.md) §6a

> **分布式相关性标注（2026-09-16 补）**：GLM-5.3-Flash 的分布式相关条目**此前散落在 §1.2 的 #28047 与上面结论文字里、表格内无显式标注**（本次核查发现）。现已集中到 **§1.4「分布式推理相关 PR 集中索引」**；其中最直接的一条是 **#28360**（GLM-5.3-Flash 的 RPC issue，**报告者第二台机器为 Strix Halo / GFX1151 —— 与本集群 A/B/C 同架构**）。⇒ 合并任一线后、上分布式前，先按该 issue 条件做前置自测。

### 1.2 DeepSeek V4（deepseek4）算子链——Vulkan 后端

| PR/Release | 内容 | 状态 | 集群影响 |
|---|---|---|---|
| **v0.3.0**（8/25） | DS4 tensor-split（`-sm tensor`）、多序列 rollback 修复 | ✅ release | 基线；⚠️ 不含 Vulkan Lightning Indexer（8/27 才合入） |
| [#26585](https://github.com/ggml-org/llama.cpp/pull/26585) | vulkan tiled transpose 0↔2（V4 indexer 瓶颈 ~43% prefill → 修复） | ✅ **Merged 8/19** | 已在 ≥8/19 master |
| [#26548](https://github.com/ggml-org/llama.cpp/pull/26548) | vulkan DSV4_HC 融合（原案） | ❌ Closed 2026-09-07? | 由 #26578 承接并最终合并 |
| [#26578](https://github.com/ggml-org/llama.cpp/pull/26578) | vulkan DSV4_HC_COMB/PRE/POST 融合（decode 1.50× / prefill 1.12×） | ✅ **Merged 9/7**（0cc4m, 2 commits） | **V4-Flash decode 提速最大单点已入主线**；现役 /opt(d2e206c4 8/31) 缺 → 升级窗口即得 |
| [#27453](https://github.com/ggml-org/llama.cpp/pull/27453) | **vulkan LIGHTNING_INDEXER**（16931/16931 通过） | ✅ **Merged 8/27** | 现役引擎缺；master 已有 |
| [#27970](https://github.com/ggml-org/llama.cpp/pull/27970) | **CUDA+ggml sparse-fa for DSV4/GLM** | ✅ **Merged 9/2** | 新发现；Vulkan 侧影响待评估 |
| [#28133](https://github.com/ggml-org/llama.cpp/pull/28133) | mtmd 支持 DeepSeek-V4-Flash-Vision-Exp | ✅ **Merged 9/2** | 文本模型需先 reconvert #28154 |
| [#28047](https://github.com/ggml-org/llama.cpp/issues/28047) | loganbruns | RPC ≥2 worker 下 V4-Pro/GLM-5.3 确定性 crash（split scheduler 发错 worker） | ✅ **Closed 9/5 — 由 [#26500](https://github.com/ggml-org/llama.cpp/pull/26500) 修复**（"rpc: avoid serializing buffers from other servers"，8/30 merged） | **Pro/GLM-5.3 分布式禁用前置已解除** — 升级引擎（含 #26500）后按闪存纪律实测确认 |
| [#26500](https://github.com/ggml-org/llama.cpp/pull/26500) | rpc: avoid serializing buffers from other servers | ✅ **Merged 8/30** | #28047 修复源；在 ≥8/30 master |
| [#27332](https://github.com/ggml-org/llama.cpp/pull/27332) | theycallmeloki | vulkan density gate（#25356 启发，MMV 路径；+36%@B9, +27%@B16, +21%@B64, B≤8 中性；gfx1151/RDNA3/gfx1013 验证） | ⚠️ Open（9/13 核查，1→2 commits，更新 9/9） | 合并即评估（MoE decode 密度门） | 合并 → 评估 |

**结论（2026-09-10 更新）**: master（≥9/7）已**全齐** V4-Flash Vulkan 算子链（indexer 8/27 + transpose 8/19 + HC 融合 9/7 + sparse-fa 9/2 + vision 9/2 + RPC 修复 8/30）。**✅ #26578 已实测落地（2026-09-10）**：三站引擎升级 master-91f6a6cf（v0.4.0-dev build 1533），A/B 两机 V4-Flash 层分布 decode **9.56→14.02 t/s（+46.7%）**，日志 `resolve_fused_ops` HC 警告清零 → **升级闭环**。详见 metrics-log Phase 6。⚠️ 归位/base 记录：0d18aaa 系（B 站会话级 llama-server）缺全部，禁止在升级前承载 V4-Flash。 [算子调研](file:///d:/RPC/spec/rpc-optimization/research/AMD平台算子层优化与USB4分布式调研.md)｜[选型](file:///d:/RPC/spec/model-eval/MODEL-SOURCING-2026-09.md) §6a

### 1.2b DeepSeek V4-Flash 框架级 PR（open，2026-09-13 补充调研）

> **层级界定**: 本节为「框架级」——架构/转换/分布式形态，区别于 §1.2 的 Vulkan 算子优化。直接关系到三机分布的 `-sm layer` → `-sm tensor` 演进与 V4.1 迁移。**分布式相关条目已集中索引于 §1.4**（含每条"现役引擎是否已含"的判定）。

| PR | 层级 | 内容 | 状态（9/16 核查） | 对集群影响 | 触发动作 |
|---|---|---|---|---|---|
| [#26610](https://github.com/ggml-org/llama.cpp/pull/26610) | RPC/分布式 | RPC 层 add `-sm tensor`（全后端拉通） | 🔴 Open，**非 draft，3 commits / 2 files，更新 2026-09-16（当日有活动）** — `mergeable_state` 本次读数为 `unknown`（GitHub 惰性计算，非状态回退）；**最可合并候选** | **三机 tensor-split 中枢**：若合，配合 #25860/#26490 可把现役 `-sm layer` 演进到 `-sm tensor`（层均衡更细）| 合并 → 与该 PR 同窗评估是否升级（与 GLM 侧引用同一 PR）|
| [#25860](https://github.com/ggml-org/llama.cpp/pull/25860) | 架构/前端 | Deepseek V4: split-mode tensor | ⚪ Draft，2 commits，更新 7/30，停滞 | 设计草案，配套 #26610 | 待其/上游转绿 |
| [#28696](https://github.com/ggml-org/llama.cpp/pull/28696) | 转换 | convert: add DeepSeek V4.1 (DeepseekV41ForCausalLM) | ⚪ **Draft**，2 commits，**更新 9/13**（9/13 台账记 9/12，有触碰） | V4.1 新架构转换入口（9/10 发布 V4.1-Flash）| 观察（V4-Flash 上游重心已移向 V4.1）|
| [#23122](https://github.com/ggml-org/llama.cpp/pull/23122) | 底层算子 | ggml: add DSV4 hyperconnection + KV ops (CPU) | 🔴 Open，非 draft，2 commits，更新 8/1 | CPU 底层 dsv4 算子入主线 → 基线 | 合并即入基线 |
| [#28569](https://github.com/ggml-org/llama.cpp/pull/28569) | 架构 | model: re-enable `-sm tensor` for qwen4exp | 🔴 Open，1 commit，更新 9/8 | 姊妹架构 tensor-split 验证 | 观察 |
| [#25452](https://github.com/ggml-org/llama.cpp/issues/25452) ⭐新 | 运行时/KV | **Eval bug: DSV4-Flash churned-reuse SWA KV-cache exhaustion（crash + stall）** —— SWA（滑窗注意力）cache 在"轮换复用"路径下被耗尽，表现为崩溃与停顿；label `bug-unconfirmed,stale`，**12 评论**（社区在跟） | 🟡 Open（创建 **7/8**，**更新 9/15**） | **与本集群直接相关**：我们跑 V4-Flash 层分布长上下文，SWA cache 行为受 `-c`/ctx 与 slot 复用影响 —— 但**报告者环境为 CUDA 5 卡（非 Vulkan）**，后端相关性未定 | **待自测甄别**：复现条件（长 ctx + 多次轮换复用 + churn）落成一条对照实验；若 Vulkan 侧也复现 → 直接影响分布式长上下文可用性 |

**架构核心历史（已 merged，v0.3.0/v0.4.0 基线，非待跟踪）**: DeepSeek V4 arch 支持（框架主线）、tensor-split、多序列 rollback、sparse-fa、Vision (#28154/#28133)、MTP/NextN、RPC event/async 基建。均已并入现役引擎升级链，状态见 §2.4。

**⚠️ Vulkan 专有缺口（观测，2026-09-13 社区调研口述待核实，不入台账真值）**: 社区反映 V4 关键 dsv4 自定义 op（compressor decode / hyper-connection sinkhorn / lightning indexer / FP8-KV quantize / NextN heads）在主线 **Vulkan 无 kernel**（`feat/v4-port-cuda` 分支注明 "ROCm/Vulkan/Metal-on-AMD fail at first dsv4 op"）——仅 CUDA/Metal 保证。**但本集群实测与台账冲突**: V4-Flash 已在 `/opt` Vulkan 三站层分布跑通（§2.4，decode 14.02 t/s）→ 需实测甄别「哪些 op 缺失/回退 CPU」后再定论，勿采信单一社区说法。分发框架支持（vLLM/SGLang/KTransformers/LM Studio）为参考，未原页核实，不在此列。

### 1.3 其他 gfx1151 算子波（跟踪中，合并即评估）

| PR/Issue | 内容 | 状态 |
|---|---|---|
| ~~[#27332](https://github.com/ggml-org/llama.cpp/pull/27332)~~ | ~~MoE decode 密度门~~（已并入 §1.2 详列） | ⚠️ Open（9/13 核查，1→2 commits，见上） |
| [#27554](https://github.com/ggml-org/llama.cpp/pull/27554) | mmq 大 tile（dense prefill 1.76×） | ❌ Closed；方向由 [#27553](https://github.com/ggml-org/llama.cpp/issues/27553) 承接 |

### 1.4 分布式推理相关 PR（集中索引，2026-09-16 新增）

> **为什么单列**: 用户 2026-09-16 指出「V4-Flash 与 GLM-5.3-Flash 需要关注**分布式推理相关 PR**」。核查结论：**V4 侧此前已有标注**（§1.2b 的「层级」列 + §1.2 的 v0.3.0 / #28047 行），**GLM 侧则散落在 §1.2 的 #28047 与 §1.1 结论文字里、表格内无标注**；且两模型**均缺 4 条关键条目**（本次补录，行首标 ⭐）。本节作为**跨模型的单一入口**：既收模型专属项，也收**两模型共用的分布式基建**。

| PR/Issue | 归属 | 主题 | 内容/证据 | 状态（9/16 核查） | 对本集群影响与触发动作 |
|---|---|---|---|---|---|
| [#26490](https://github.com/ggml-org/llama.cpp/pull/26490) ⭐ | DS V4-Flash | 架构/分布式 | **Deepseek 4: `-sm tensor`**（am17an；8 commits / 7 files；分支 `am17an:dsv4-sm-tensor`） | ✅ **Merged 2026-08-24** | **重要澄清**：V4 的 `-sm tensor` **主体早已入主线，且现役引擎（master-91f6a6cf，9/10 构建）已含** ⇒ "单机/多进程 `-sm tensor`" 已具备；**缺的只是 RPC 多机形态（#26610）**。此前台账仅在 §1.2b"配合 #25860/#26490"里提及、未标 merged |
| [#27825](https://github.com/ggml-org/llama.cpp/pull/27825) ⭐ | 共用基建（**C 站直接相关**） | ROCm/通信原语 | **HIP: Enable AllReduce for ROCm**（1 commit / 3 files） | ✅ **Merged 2026-09-15** —— **现役引擎不含**（9/10 构建） | **AllReduce 是张量并行的通信原语**；C 站为 HIP/ROCm ⇒ 若将来走 `-sm tensor` + ROCm，这是**前置**。触发：**下次引擎升级纳入**（与 #26610 评估同窗） |
| [#26610](https://github.com/ggml-org/llama.cpp/pull/26610) | 两模型共用 | RPC/分布式 | RPC 层 add `-sm tensor`（全后端拉通） | 🔴 Open，非 draft，3 commits / 2 files，**9/16 有活动** | **三机 tensor-split 中枢**：只有它合并，`-sm tensor` 才在 **RPC** 上可用（#26490 只解决非 RPC 路径） | 合并 → 与 GLM/V4 同窗评估升级（详见 §1.2b） |
| [#28047](https://github.com/ggml-org/llama.cpp/issues/28047) / [#26500](https://github.com/ggml-org/llama.cpp/pull/26500) | GLM-5.3（+ V4-Pro）分布式前置 | RPC/修复 | RPC ≥2 worker 下 V4-Pro/**GLM-5.3** 确定性 crash（split scheduler 发错 worker）→ 由 #26500 修复 | ✅ Closed 9/5 / **#26500 Merged 8/30（现役已含）** | **GLM-5.3 分布式禁用的前置已解除** = §1.1 结论「三变二」的第②条。触发：**已满足** |
| [#28360](https://github.com/ggml-org/llama.cpp/issues/28360) ⭐ | **GLM-5.3** | RPC/运行时 | **Eval bug: RPC Issue in add GLM-5.3-Flash (GLM5-Next) support - #27773**；报告者两机 = **4×9060XT(GFX1200) + Strix-Halo(GFX1151)**，走 RPC | 🟡 **Open**（创建/更新 9/4，1 评论，`bug-unconfirmed`） | **最直接的一条**：报告者第二台就是 **gfx1151（与本集群同架构）**，且明确挂在 #27773 线上 ⇒ GLM-5.3 走 RPC 存在**已知未确认问题**。触发：**合并任一线后、上分布式前，先按该 issue 条件做前置自测** |
| [#27311](https://github.com/ggml-org/llama.cpp/pull/27311) ⭐ | 共用基建（**UMA**） | 调度器 | **Scheduler UMA ring buffer**（+ sanitizer 加固与调度修复；**49 评论、9/16 仍活跃**） | 🟡 Open（8/18 创建，**更新 9/16**） | 本集群是 **UMA（Strix Halo 统一内存）** 且跑 RPC ⇒ 调度器输入张量 ring buffer 与我们的形态**直接相关**（可能关联"长跑稳定 / 内存行为"）。触发：合并 → 评估 |
| [#26384](https://github.com/ggml-org/llama.cpp/issues/26384) | DS V4-Flash（分布式健壮性） | RPC/健壮性 | deepseek_v4 over RPC（2 节点，Thunderbolt）：输出退化为 `====` → worker 侧图失败**直接杀掉整个 server**，原文注明 **"RPC has no error recovery"** | ⚫ Closed（`stale`；7/31 创建、9/14 更新） | **通用风险认知**：RPC 无错误恢复 ⇒ 三机形态下 **worker 故障会连带 head 全挂**（与本集群 2026-09-08 两次 kernel panic 经验同族）。触发：已记入风险认知，非动作项 |
| [#27964](https://github.com/ggml-org/llama.cpp/issues/27964) | `-sm tensor` 风险观察 | 运行时 | Qwen3.8-Flash-Next：`--split-mode tensor` 在 CUDA 双卡上 **abort（`SPLIT_AXIS_UNKNOWN`）** | 🟡 Open（8/29 创建，更新 9/16） | `-sm tensor` 在**其他架构上仍有失败案例**（姊妹架构 qwen4exp / qwen3.8）⇒ 我们启用前**必须先做形态验证**。触发：纳入 `-sm tensor` 验证清单 |

**低相关存档**：[#26906](https://github.com/ggml-org/llama.cpp/issues/26906)（"model stop answering after some hours of work"，`stale`）—— 报告环境为 **CPU 双机、无 GPU**，与本集群形态不符，仅存档不动作。

**§1.4 判定（2026-09-16）**：分布式路径上**真正的两个闸门**是 ① **#26610**（RPC `-sm tensor`，仍 Open，但 9/16 有活动）与 ② **GLM 侧的 #28360**（同架构报告者的 RPC 问题，未确认）。V4 侧的 `-sm tensor` 主体（#26490）与 RPC crash 修复（#26500）**均已在现役引擎内**；C 站 HIP 侧的 AllReduce（#27825，9/15 合并）**尚未入现役**，若走 ROCm 张量并行需随下次升级纳入。

### 1.5 待评估事项（上游驱动的动作队列，2026-09-16 建）

> **用途**: 把"上游状态变化 ⇒ 我们要做什么"从 §1.1–§1.4 的散落语句收成**一张队列表**；每条含触发条件 / 成本 / 依赖 / 出处。**评估结论回写到本表**，不在此处下结论。

| # | 事项 | 类型 | 触发条件 / 现状 | 成本 | 依赖 | 出处 |
|---|---|---|---|---|---|---|
| **EV-1** | **#28360 前置自测** —— GLM-5.3 上分布式**之前**，按该 issue 条件（同架构报告者：**GFX1151 + RPC**）做复现对照 | 上游风险 | **待做**（GLM 任一线合并后即成为前置）；#28360 仍 Open | 中（需可跑的 glm5next 引擎） | 需先有可跑的 glm5next 引擎 | §1.4 |
| **EV-2** | **#27825（HIP AllReduce）纳入下次引擎升级清单** | 升级项 | **待列入**；已 Merged 9/15，**现役不含** | 小（随 UPGRADE_SOP 一次走） | 下次引擎升级窗口 | §1.4 |
| **EV-3** | **CIRU（gfx1151 原生 vLLM/ROCm 发行）单站试点** —— 走 vLLM **绕开 glm5next 上游依赖** | 引擎换路线 | **待证前提**：`GLM5.3-Flash-CIRU-STRIX-IU4` 是否真实可获取 / 体积 / 显存需求（**当前 0 runs、HF 页面不可达**） | 中（拉权重 + ROCm 7.15 栈，C 站） | C 站 ROCm 栈升级；**权重可获取性未证实** | [调研 §2](../../docs/research/2026-09-16_分布式推理路线可行性调研_CIRU-Skulk-多机TP.md) |
| **EV-4** | **Skulk 引入可行性** —— 多机 fabric（AMD Linux = `skulk-llama-server-vulkan`；引擎可注入 `SKULK_LLAMA_SERVER_BIN`） | 框架引入 | **待决策**：先答"**谁管生命周期**"（与**零自加载 / load-gate 内存闸门 / C 站看门狗禁用 / ADR-0004 唯一管理面**的冲突） | 小（决策）→ 中（试点） | ADR-0004 D3 裁决 | [调研 §4](../../docs/research/2026-09-16_分布式推理路线可行性调研_CIRU-Skulk-多机TP.md) |
| **EV-5** | **100GbE RDMA 硬件评估**（若目标是"真·多机 TP 跑大档"） | 硬件决策 | **待决策**；vLLM+Ray+RCCL+RoCE v2 需 Intel E810 级 NIC（本集群只有 **USB4 ~9.4Gbps**） | 大 | 预算决策 | [调研 §5.1](../../docs/research/2026-09-16_分布式推理路线可行性调研_CIRU-Skulk-多机TP.md) |
| **EV-6** | **"StrixLink" 取证** | 取证 | **未确认**：三轮定向检索 + HF API **全未命中**（命中物均为同名无关）；**需用户提供出处** | 小 | 用户提供来源 | [调研 §3](../../docs/research/2026-09-16_分布式推理路线可行性调研_CIRU-Skulk-多机TP.md) |

**EV 队列的当前优先级**（按性价比，见[调研 §6](../../docs/research/2026-09-16_分布式推理路线可行性调研_CIRU-Skulk-多机TP.md)）：**EV-1/EV-2 随上游走（零成本）→ EV-3 中等成本、收益明确（绕开上游）→ EV-4 先做治理决策 → EV-5 属硬件预算 → EV-6 等来源**。

***

## 2. 集群引擎基线（2026-09-08 实测）

> ✅ **2026-09-08 归位完成**：三站分布式链路已切回 `/opt/llama.cpp`（v0.3.0, rpc v6.0.0），MANIFEST I3 首次成立，巡检全绿。见下方「2.4 归位后状态（9/8 17:00 收口）」。
> 🧩 **绕 /opt 成因（用户 09-08 补充）**：当初 `/opt` 写入需 sudo 权限，测试新框架时 LLM 建议绕过 /opt 改用用户目录 → 该建议被沿用到运行链路，形成「散置构建 = 现役」格局。回归受控时必须照顾此历史，不能假设 `/opt` 一直是运行入口。

### 2.0 A/B 站运行链路实测对照（2026-09-08）

| 链路 | B 站（GTR-Pro） | A 站（NEX） | 引擎真身 | 版本 |
|---|---|---|---|---|
| 管理/单站推理 | 18081 已停（现 qwen3.8 在 18081 为会话拉起） | **8080 = unsloth studio run gpt-oss-120b-MXFP4**（`~/.unsloth/studio/unsloth_studio/bin/python ... --device Vulkan0 -c 131072`） | `~/.unsloth/llama.cpp`（unsloth 自带框架目录，**用户提示 A/B 站 unsloth 已写死此路径**） | 0.3.0-dev 10715 / ggml 0.22.0 |
| RPC 分布式 | **18081 = `~/llama.cpp/build/bin/llama-server`**（qwen3.8 Q8 + --rpc A/C） | **50052 = `~/llama.cpp/build/bin/rpc-server`** | `~/llama.cpp/build`（绕 /opt） | 0d18aaa / ggml 0.13 系（源码 HEAD 05-26） |

**要点**：① 单站链路由 unsloth 管理（含自有引擎路径），**回归不得破坏 unsloth 引擎**；② 分布式链路（llama-server/rpc-server）的现役是绕 /opt 的 `~/llama.cpp/build`——**这是需要归位回 `/opt` 受控版本的部分**；③ A 站另有 defunct llama-server 僵尸进程（389114），清理时一并处置。

### 2.4 归位后状态（2026-09-08 收口；**2026-09-10 升引擎至 91f6a6cf**）

| 项 | 值 |
|---|---|
| 三站 `/opt/llama.cpp` | symlink → **`llama.cpp-master-91f6a6cf`**（v0.4.0-dev build 1533, commit 91f6a6cf；旧 d2e206c4 保留待清理） |
| MANIFEST | **I3 成立**：三站各 79 条 [md5]，`md5sum -c` 全 `成功`；commit/version/rpc_protocol 三字段统一 |
| rpc_protocol | **v6.0.0**（/opt master rpc-server 启动日志实测；旧 9859 为 v4.0.1） |
| 分布式链路 | B `/opt/llama.cpp/llama-server` + `--rpc 10.10.10.x:50052` → A/C `ggml-rpc-server`（v6.0.0, Vulkan0 GFX1151, `-c` cache） |
| 冒烟 | #26578 实测（9/10）：A/B 两机 V4-Flash decode 9.56→14.02 t/s；HC `resolve_fused_ops` 警告清零 |
| 巡检 | `ops/check_llama_version.py --deep`：三站指纹一致 + 文件集 md5 完全一致 ✅ |
| 已知观察 | ① RUNPATH：新 cmake 产物硬编码 B 站 build 路径 → A/C 必须 patchelf `$ORIGIN`（已修）；② 旧 d2e206c4 目录保留作回滚；③ C 站内核实测 7.0.0-31 观察项（§手册10.1） |

### 2.5 回归后职责边界（更新）

- **分布式链路（llama-server / ggml-rpc-server）** → 一律走 `/opt/llama.cpp`（UPGRADE_SOP 管理）；**禁止**再手动用 `~/llama.cpp/build` 起服务
- **单站管理（unsloth studio）** → 保持 `~/.unsloth/llama.cpp`（写死路径约束，不触碰）
- **散置构建**：`~/llama.cpp/build`（旧现役，待确认无引用后清理）、`~/llama.cpp`（0d18aaa 源码树，保留为对照）、`~/App/llama-gfx1151`（HIP 残留，清理候选）、`~/llama.cpp-vulkan-b10715`（unsloth 构建，保留为升级源之一）

### 2.1 B 站（GTR-Pro）现役实例（PID 612738, port 18081, qwen3.8-27b Q8）

| 项 | 实测值 |
|---|---|
| 进程命令 | `/home/scott-lau/llama.cpp/build/bin/llama-server` |
| 拉起方式 | SSH 会话 scope（cgroup `session-8306.scope`，PPID=1 已脱管）→ **非 systemd 服务，watchdog 可见** |
| maps 加载库 | `llama.cpp/build/bin/libggml-*.so.0.13.0`、`libllama.so.0.0.1`（mtime 9/6 重建） |
| 源码 HEAD | `~/llama.cpp` = `0d18aaa`（2026-05-26，`ci: do not allocate ccache ...`） |
| deepseek4 / glm5next | 均 **0**（现役构建不含）→ V4/GLM5 不可加载 |
| 备注 | build/bin mtime 9/6 16:11-16:12（最近重编过）但版本号仍是 ggml 0.13 系——**疑源码树与构建产物版本号未同步**，纳入升级时核查 |

### 2.2 B 站 /opt 正式版本目录（UPGRADE_SOP 管理）

| 目录 | 版本 | 部署时间 | 含 lightning? | 使用方 |
|---|---|---|---|---|
| `/opt/llama.cpp` → `llama.cpp-master-d2e206c4` | **v0.3.0-dev（libllama.so.0.3.0，ggml 0.22.0，deepseek4 字符串 91 处）** | 8/31 | 待核 | **无进程打开（lsof 空）** |
| `/opt/llama.cpp-9859` | build 9859（ggml 0.15.3） | 7/2 预存/8/27 归档 | 否 | 无 |
| `/opt/llama.cpp-v0.2.0` | v0.2.0 | 8/28 | 否 | 无 |

### 2.3 用户目录散置构建（测试残留，勿混用）

| 目录 | 说明 | 处置 |
|---|---|---|
| `~/llama.cpp-vulkan-b10715` | **unsloth 官方 v0.3.0-dev build 10715，ggml 0.22.0，vulkan lib 含 lightning 字符串 14 处**（8/27 后构建）——文档多年误载为「现役」 | **升级候选可复验**；勿当现役 |
| `~/.unsloth/llama.cpp/build` | unsloth 构建（同 b10715，clang 23） | 复验源之一 |
| `~/App/llama-gfx1151` | **6 月 ROCm/HIP 实验构建**（libggml-hip.so + hipblaslt + libamdhip64 全套，mtime 6/20）——疑用户所说「测试失败未删除的新框架」；6 月时 ROCm gfx1151/kFD 不工作 | ⛔ **过度残留**，Hip llama 后端已死（DEPLOYMENT O4 判定），确认后清理 |
| `~/llama-distributed/` | bench/crash_drill/smoke 脚本 + logs | 保留（RPC 实测产物） |
| `~/src/llama.cpp-0.2.0` `~/build/llama-v0.2.0` | v0.2.0 源码/构建 | 可清 |

**行动（P0）**: 按 [UPGRADE_SOP](file:///d:/RPC/spec/vulkan-version-control/UPGRADE_SOP.md) 以 `~/llama.cpp-vulkan-b10715`（unsloth v0.3.0）或 `/opt/llama.cpp`（v0.3.0）为源，确认 libllama 含 deepseek4 + libggml-vulkan 含 lightning indexer 后做一次两站原子升级 → V4-Flash 解锁。升级前记录现役 0d18aaa 基准（18081 qwen3.8 可跑）。

***

## 3. 已关闭区（merged + 集群已验证）

| 条目 | 关闭日期 | 依据 |
|---|---|---|
| （空，首版） | — | — |

***

## 4. 有状态的反向链接（各文档引用本表）

- [FRAMEWORK-SURVEY 附录 H.4](file:///d:/RPC/spec/model-eval/FRAMEWORK-SURVEY-2026-09.md)（原 docs/GLM-5.3-Flash-分布式部署调研并入）§5.1 —— 架构支持表「快照」→ 状态以本表为准
- [spec/operator-optimization/DESIGN.md](file:///d:/RPC/spec/operator-optimization/DESIGN.md) §6 —— Phase C 跟踪 → 状态以本表为准
- [spec/model-eval/MODEL-SOURCING-2026-09.md](file:///d:/RPC/spec/model-eval/MODEL-SOURCING-2026-09.md) §6a —— PR 表 → 状态以本表为准
- [spec/station-c/DEPLOYMENT.md](file:///d:/RPC/spec/station-c/DEPLOYMENT.md) —— C 站引擎 → 版本描述同步本表 2.x

***

## 5. 变更日志

| 日期 | 操作 | 内容 |
|---|---|---|
| 2026-09-16 | **建 §1.5「待评估事项」动作队列（v1.4）+ 分布式路线可行性调研落档** | 用户要求把上轮两个待定动作"列入待评估事项"，并评估 **CIRU StrixLink 部署 GLM-5.3-Flash** 与 **引入 Skulk 框架** 的可行性（动机：**分布式 llama 对 V4-Flash / GLM-5.3-Flash 支持力度不够**）。**新建 §1.5 队列表 EV-1…EV-6**：EV-1 #28360 前置自测 / EV-2 #27825 纳入下次升级 / EV-3 **CIRU 单站试点** / EV-4 **Skulk 引入（先答"谁管生命周期"）** / EV-5 **100GbE RDMA 硬件** / EV-6 **"StrixLink" 取证（未确认）**。**调研结论**（[文档](../../docs/research/2026-09-16_分布式推理路线可行性调研_CIRU-Skulk-多机TP.md)）：**Skulk 已确认**（官方文档原页：AMD Linux = `skulk-llama-server-vulkan` wheel、引擎可注入 `SKULK_LLAMA_SERVER_BIN`、vLLM 仅 NVIDIA；但**后端就是 llama.cpp** ⇒ 不改上游事实，且其**常驻 supervised service** 与"零自加载 / load-gate / 看门狗禁用 / ADR-0004 唯一管理面"冲突）；**CIRU 部分确认**（gfx1151 原生 vLLM/ROCm 运行时发行；Ling-3.0-Flash 实测 0.269→**26.23 t/s（97.5×）**，关键收益来自"禁用 ROCm skinny-GEMM Wave32 病态分发"28.16×；**但 GLM-5.3 构建 `GLM5.3-Flash-CIRU-STRIX-IU4` 仅一处第三方索引页出现、0 runs ⇒ 未证实**，且**无任何多机声明**）；**"StrixLink" 三轮定向检索 + HF API 全未命中 ⇒ 不予评估（需用户提供出处）**；**检索另带出两条更该进队列的**：**vLLM+Ray+定制 RCCL+RoCE v2 多机 TP**（唯一改能力上限的路线，合并显存 ~248GB、RDMA 5µs 级，但**需 100GbE NIC（Intel E810）**，我们只有 USB4 ~9.4Gbps）与 **AMD 官方 playbook**（llama.cpp RPC 跑 GLM-4.7 358B ＝ 我们现路线，官方背书；瓶颈不在路线而在上游 PR 与物理链路） |
| 2026-09-16 | **新增 §1.4「分布式推理相关 PR 集中索引」（v1.3）** | 用户指出"V4-Flash 与 GLM-5.3-Flash 需要关注**分布式推理相关 PR**" ⇒ 核查发现：**V4 侧此前已有标注**（§1.2b 的「层级」列 + §1.2 行），**GLM 侧未标注**（散落在 §1.2 的 #28047 与 §1.1 结论文字里），且**两模型均缺 4 条关键条目**。集中补录 **#26490**（**V4 `-sm tensor` 主体，Merged 8/24** ⇒ 现役引擎已含；澄清"非 RPC 路径的 `-sm tensor` 早已可用，缺的只是 RPC 形态"）、**#27825**（**HIP AllReduce**，Merged 9/15，**现役不含** —— C 站 ROCm 张量并行的通信原语前置）、**#28360**（**GLM-5.3 的 RPC issue**，报告者第二机为 **GFX1151 同架构**，Open）、**#27311**（调度器 **UMA ring buffer**，49 评论、9/16 活跃）；并把 #28047/#26500（GLM 分布式前置已解除）、#26610（RPC `-sm tensor` 中枢）、#26384（**"RPC has no error recovery"**）、#27964（`-sm tensor` 在 Qwen 侧 `SPLIT_AXIS_UNKNOWN` abort）一并纳入；#26906 标低相关存档。**判定：两个真闸门 = #26610 与 #28360**。同时在 §1.1 结论、§1.2b 层级界定处加"分布式相关性"指针 |
| 2026-09-16 | **GLM-5.3-Flash + DS V4-Flash 上游状态核查（API fetch 原页，v1.2）** | **GLM**：#27754（unsloth 首选线）**43→45 commits（42 files）且 `mergeable_state=unstable` + 9/16 当日有活动** = **9/13 以来首个「接近可合并」信号**（仍未合入）；#27773 46c 未动 / #27752 11c / #27917 Draft 31c（三者均 `dirty`）；#27922 issue 仍 Open（实标题 "Feature Request: Support GLM5.3 (flash)"）。**新补录 3 条**：**#28282**（在 #27754 HEAD 上长 prefill `-ub 2048` 出现 CUDA 非法访存，`bug-unconfirmed`，更新 9/15 ⇒ 提示该线**长 prefill 侧未验证**）、**#28727 + #28729**（GLM indexer `soft_max gridDim.y` 溢出修复，**双双 closed 未合并**、无人承接）、**#28106**（`resolve_fused_ops` 只校验 device placement 不校验 tensor，8/31 创建、本次补录）。**判定**：维持等待 + **新增预警触发「#27754 转 `clean` 且 reviewer 批准 → 启动评估环境准备」**（不必等合并）+ 评估时**必须压测长 prefill**。**DS V4**：**#26610**（RPC `-sm tensor`）**9/16 仍有活动**（3 commits / 2 files；`mergeable_state` 本次惰性读作 `unknown`）⇒ 仍为**最可合并候选**；#25860 Draft 停滞（7/30）/ #28696 Draft（9/13 有触碰）/ #23122（8/1）/ #28569（9/8）均无实质变化；**新补录 #25452**（V4-Flash **SWA KV-cache 轮换复用耗尽 → crash/stall**，12 评论，创建 7/8、更新 9/15；**报告者环境为 CUDA 5 卡 ⇒ 后端相关性待自测甄别**）。**架构级无新 PR**（`deepseek4 in:title updated:>=2026-09-13` = 0） |
| 2026-09-13 | **后端 GLM-5.3-Flash + density gate PR 状态核查（GitHub API fetch 原页）** | **glm5next 仍未合入 master**，但三线推进有实质变化：#27773（timkhronos 文本+视觉）**41→46 commits（9/12，三线最活跃）**；#27754（unsloth 首选线）**41→43 commits（9/11）**；#27332（vulkan density gate）**1→2 commits（9/9）**；#27752 11 commits 未变（仅被触碰 9/11）；#27917 仍 Draft 31 commits（head 5b8593b）；#27922 issue 仍 Open。**DSV4 算子链全 merged 不变**（#26578 9/7 / #27970 / #28133 9/2 / #28047 9/5 由 #26500 修复）。**结论**：无关键合并信号 → GLM-5.3-Flash 维持等待，事件驱动前置「三变二」不变 |
| 2026-09-10 | **B 站 Q3.8F 两档清理：删 UD-Q4_K_XL（111.3G）+ GLM-5.3-Flash PR 状态核查** | **①B 站删除 `Qwen3.8-Flash-Next-UD-Q4_K_XL.gguf`（111,334,654,400 B / 104G 磁盘）**——该档超出单站（121G avail）安全余量（111.3G 权重 + KV 无富余，此前判定「单站无可部署」）；删除后磁盘 817G→923G 可用；保留 UD-IQ4_XS（93.7G，现役档，C→B 经 USB4 1.11GB/s 传输 + md5 三片一致）。**②GLM-5.3-Flash 五 PR fetch 原页核查（9/10）**：#27754 Open 41c 未变（前置 flag 更新：`NVIDIA_TF32_OVERRIDE=0`+`-fa off`）；#27752 Open **10→11c**（唯一变化）；#27773 Open 41c 未变；#27917 Draft 31c 未变（`--spec-type draft-mtp`）；#27922 Open（mmproj+文本双证 `unknown architecture 'glm5next'`）。**无合并信号 → GLM-5.3-Flash 维持等待** |
| 2026-09-10 | **C 站 unsloth(HIP) 双模型实测：M2.7 + Q3.8F 均 ✅** | C 站 `~/.unsloth/llama.cpp` b10715（HIP/ROCm0，无 Vulkan）实测：**M2.7 UD-IQ4_XS（108.4G）** 加载 40s，quality 正常，**tg 24.4-24.8**（load-gate need=107 恰好过）；**Q3.8F-Next UD-IQ4_XS（93.7G）** 加载 25s，中/英/多轮无乱码，稳态 **22.6-23.2 t/s**（need=94）。**D.5 结论修正**：Q3.8F 的 HIP 乱码限 **LM Studio 内置 ROCm 引擎**（疑含 #27621 回归），**unsloth b10715 HIP 实测无 #28113 MoE 数值 bug** → C 站 Q3.8F HIP 非全坏，unsloth b10715 即回避方案。思考治理：`--reasoning-effort medium --reasoning-budget 2000` 生效（reasoning 仅 20-245 tok）。⚠️ M2.7 是 CoT 模型，max_tokens 须 > 思考长度否则 content 空。详见 [MODEL-SOURCING D.6](../model-eval/MODEL-SOURCING-2026-09.md) |
| 2026-09-10 | **三站引擎升级 master-91f6a6cf + #26578 实测落地 ✅** | UPGRADE_SOP 六步：B worktree 构建 v0.4.0-dev build 1533（含 #26578 DSV4_HC + #27970 sparse-fa）→ MANIFEST 79 条 → tar 分发 A/C → **patchelf `$ORIGIN` 修正 RUNPATH**（cmake 产物硬编码 B 站 build 路径，不改 A/C 无法加载）→ 原子切换 symlink → `check_llama_version.py --deep` 三站指纹+79 文件全等 ✅。A/B 两机 V4-Flash（-sm layer 无 -ngl 99, 单文件 156G）decode **9.56→14.02 t/s（+46.7%）**，`resolve_fused_ops` HC 警告清零 → **#26578 升级闭环**。详见 metrics-log Phase 6。另修 `check_llama_version.py` C 站 IP（192.168.1.24→.37）。**load-gate 三站对齐 ✅**（A/B 补装 station-bin 同源，md5 6acec519 三站一致，60G 冒烟 OK）|
| 2026-09-10 | **算子 PR 动态复核（fetch 原页）** | **#26578 DSV4_HC 融合 → Merged 9/7**（decode 1.50×/prefill 1.12×，V4-Flash decode 提速最大单点入主线）；**#28047 RPC crash → Closed 9/5（#26500 修复）**，V4-Pro/GLM-5.3 分布式禁用前置解除；新增 #27970（sparse-fa 9/2 merged）；现役 /opt（d2e206c4 8/31）缺 sparse-fa+HC → **引擎升级 P0 强化**（升级即得 decode 1.50×）；GLM-5.3-Flash 三 PR 仍 Open（#27754 9/9 更新）未合入 |
| 2026-09-08 | 创建 | 首版：收拢 GLM5next 4PR + DSV4 算子 6 项 + gfx1151 波 2 项；引擎基线三套目录实测（现役=0d18aaa 系，/opt=v0.3.0 未用，b10715=文档误载）；发现 `~/App/llama-gfx1151` HIP 残留 |
| 2026-09-08 | 归位完成 | 三站分布式链路切回 `/opt/llama.cpp`（v0.3.0, rpc **v6.0.0**）；重建三站 MANIFEST（I3 首次成立，79 条全过）；C 站补装 /opt master；巡检脚本重建（`ops/check_llama_version.py`，paramiko 三站版）首跑全绿；回归后职责边界 §2.5 落地；绕 /opt 成因入档 |
| 2026-09-08 | V4-Flash 崩溃定案 | 两次 kernel panic（三站分片 + `-c 512` 最小验证均崩）；根因=**单文件 146G MXFP4 > 120G UMA 池 + `-ngl 99` 全 offload**，与 mmap/ctx/RPC 无关；完整分析见 [V4-Flash-0731加载崩溃根因分析](../../docs/V4-Flash-0731加载崩溃根因分析_20260908.md)；P0 修正=验证 MXFP4 Vulkan 支持→分片→加载监控 |
| 2026-09-08 | V4-Flash 四次崩溃定案 | 第 3/4 次（`-fit on` / `-dio`+分片）仍崩；社区调研证实 **Vulkan 后端在 Strix Halo UMA 不可行**（beowulf「只能用 ~43G」；成功案例全走 ROCm/HIP 或 CPU-only）→ **弃 Vulkan 路线，转 ROCm/HIP**（Lucebox 32t/s 同构）；文档 §3.3/3.4/4.1b/6/7 更新；恢复 B 18081 为 P0 |
| 2026-09-08 | 环网恢复（MAC 绑定根治） | B 站 thunderbolt-net 接口枚举漂移（thunderbolt0/1 名与物理口互换）致 10.10.x 全盲、RPC 退走 WiFi、无 rpccache；根因=netplan 按接口名绑定 + 重启枚举漂移。修法=netplan 改 `match: macaddress`（段 id 须改非接口名防 netplan5 反导出 interface-name）；A/C worker 补 `--cache` 启用 rpccache。重启验证：接口名又互换但 IP 正确跟随 MAC。详见 [V4复现-无rpccache与环网异常落档](../../docs/V4复现-无rpccache与环网异常落档_20260908.md) |
| 2026-09-08 | **V4-Flash 三站分布式成功复现** | 分片 4×45G + `-sm layer` 层分布 + master(v0.3.0, rpc v6.0.0) + 环网 RPC（10.10.10.1/10.10.11.3），**不用 `-ngl 99`** → 加载成功（5m21s），三站内存 B=55/A=60/C=72G 均 < 110G 阈值，无 OOM。生成冒烟：中文问候输出 ✅，**decode 7.93 t/s**（9/1 基线 ~6.3 t/s，+26%）。日志含 HC 融合警告（#26578 未合入，已知瓶颈）。**推翻「弃 Vulkan 转 ROCm」** — Vulkan 路线在正确形态（层分布、非全量持有、分片）下可行 |
| 2026-09-08 | llama 后端盘点 + ds4 部署方案 | 盘点 A/B/C 残留 llama 后端；/opt 已 MANIFEST 控制 ✅；ds4 方案落档。**（subagent 审计修正：C 站非完全同构仅 3 目录；补遗 llama-distributed/~/App/llama-gfx1151(1.7G ROCm)/zip/tar.gz 等；C 有活跃 Qwen3 多模态 llama-server 勿动）** 见 [FRAMEWORK-SURVEY 附录 H.2](../model-eval/FRAMEWORK-SURVEY-2026-09.md)（原 llama后端盘点并入） |
| 2026-09-08 | **llama 残留后端清除完成** | 已清除（先备份+md5 验证后删）：A/B 站 `/opt/llama.cpp-v0.2.0`、`~/llama.cpp-vulkan-b10715`；B 站 `~/App/llama-gfx1151`（1.7G，2024 老 ROCm CI 残留，已 tar 备份 445M）、`llama-b1292-*.zip`、`llama.cpp-v0.2.0.tar.gz`。备份：B 站 `/data/backup/llama-cleanup-20260908/`（5 项 1.2G）、A 站同路径（2 项，vulkan 由 B 同 commit 补齐，删除前 md5 与备份一致）。现役链路（/opt master 软链 + A/C rpc-server）无受损 |
| 2026-09-08 | gpt-oss-120b 后训练生态 + Astra 调研 | 盘点 AutoTrust/cloudyu 蒸馏家族（Fable-5 本地已有，HumanEval +15pp；Sonnet-Reasoning/Hertetic 等）；**GPT-6 Astra（9/3 发布）闭源 + 不支持微调 + latent thinking 阻碍蒸馏 → 不存在基于 Astra 的开源模型**；gpt-oss-120b 仍是集群单机可后训练唯一现实基座。见 [MODEL-SOURCING 附录 H.3](../model-eval/MODEL-SOURCING-2026-09.md)（原 gpt-oss 调研并入） |
| 2026-09-08 | **Fable-5/Sonnet-Reasoning 幻觉核查** | ①**Fable-5-Distilled**：AutoTrust 模型卡官方警告 **severe hallucination**（捏造 API 签名/路径/URL/版本号），黄金法则=配 anysearch 锚定；根因=40-step+无RLHF+352 turns。②**Sonnet-Reasoning-Distilled**：无专项警告，但 gpt-oss 基线 SimpleQA 高幻觉率 → 事实内容仍须验证；1000-step checkpoint 数值精度弱。**结论：两模型仅可用于代码/推理链，事实性内容一律检索验证门**。见调研文档 §4.3/§4.4 |
| 2026-09-08 | **C 站 unsloth 引擎补齐（与 A/B 同构）** | C 站原无 `~/.unsloth/llama.cpp`（studio UI-only）→ 经 B 站 tar-over-ssh 全量同步（2,011,722,283 B 字节级一致），**三站 key 文件 md5 完全一致**（llama-server=31d8787b、libggml-hip=87ea1504）。C 站 KFD + ROCm 7.2.1 环境验证可用（HIP 引擎枚举 ROCm0 120G）。C 站活跃 qwen3.8 服务未受影响。⚠️ 遗留：C 站内核为 **7.0.0-31**（A/B 为 6.17.x），与项目内核锁定规则不符，待确认 |
| 2026-09-08 | **C 站内核切换 6.17.0-23 + 环网 MAC 绑定根治** | C 站已装 6.17.0-23（与 B 同版本）但 GRUB_DEFAULT=0 跑 7.0.0-31 → 改 `GRUB_DEFAULT="1>4"`（id 方式失效，子菜单索引生效）→ 重启后运行 **6.17.0-23** ✅。**继发发现并修复两处环网问题**：①C 站 thunderbolt 接口名重启漂移（与 B 同款）→ netplan 改 MAC 绑定（02:c0:c6:93:d4:eb→10.10.11.3、02:8e:c8:89:54:ef→10.10.12.3）②A 站 `thunderbolt1` 连接 **autoconnect=false** 致 10.10.12.1 重启不恢复（这是用户此前需手动开 A thb1 开关的底层原因）→ 手动 `nmcli con up` 激活。**环网三站两两 0% 丢包全通**；C 站 qwen3.8 服务 18080 自恢复 |
| 2026-09-08 | **A 站 autoconnect 固化（根治 10.10.12 重启丢失）** | A 站 `thunderbolt1` 连接（3bdf2925，10.10.12.1）原 `autoconnect=false` → netplan yaml passthrough 改为 `"true"`（先备份 .bak-autoconnect-20260908）→ NM 运行时确认 true + netplan generate 后 yaml 仍 true（重启持久化验证）。**三站环网全通稳定** |
| 2026-09-08 | **C 站管理网迁移（WiFi→eno1, IP .24→.37）** | C 站网络接入改为网线 eno1，DHCP 获 `192.168.1.37`（原 WiFi `192.168.1.24` 弃用）；用户手动关闭 WiFi → **单网卡单默认路由**（与 A/B 同构，治理 IP 漂移）。文档同步：DEPLOYMENT.md（SSH/Cockpit URL）、tmp 工具脚本（v4f_start_monitor.sh/rpccache_deep.sh/deploy_key.py）改 .37；V4 落档加历史注记 |
| 2026-09-08 | **C 站 HIP 定案翻转：UMA=4G 档全链路打通 🎉** | 事件链：①B 站同参对照成功→定位 C 站差异=UMA carveout；②用户 BIOS 确认最小档仅 1G、Auto=64G；③社区调研（EVO-X2 同 2014:801d 公板转 Vulkan；jstormes/StrixHalo UMA 建议 512M-4G；ROCm #6146/#6582）佐证 carveout 档位是真实变量；④软件层穷尽（ROCm 屏蔽/aqlprofile/hipBLASLt/XNACK/CPU-only/amd_iommu=off+pages_limit=32M）均不解决 → **BIOS 设 4G 档**；⑤实测 gpt-oss-120b HIP：**加载 23s、零 fault、prefill 152 t/s、decode 48.8 t/s**（A/B 站 49.8-52.7 同级）→ **三站 unsloth HIP 单站同构达成**。根因=carveout 档位：1G→SVM page fault；Auto(64G)→HIP 池仅 61G 装不下 60G；**4G 两全**。**教训：C 站"HIP 不可用"早期定案错误，被用户"统一内存为何跑不了"质疑纠偏** |
| 2026-09-08 | **C 站 llama-systemd 看门狗关闭 + 显存占用根治** | `llama-server@.service` 模板 `Restart=on-failure`→`Restart=no`（备份 `.bak-watchdog-20260908`）；qwen 实例 `systemctl disable`（移除 multi-user.target.wants symlink）→ 不再开机自启/失败复活。显存占用溯源：qwen `-ngl 999` 全 offload → 权重进 GPU（carveout 4.2G + GTT 30G）；服务停止后 vram/gtt 回归基线。**C 站当前无 llama 进程、端口全释放；需手动起 qwen: `systemctl start llama-server@qwen3.8-27b-mtp`** |
| 2026-09-08 | **C 站 HIP vs Vulkan 后端对照（gpt-oss-120b, UMA=4G）** | 同模型同参数双后端实测：**HIP**（unsloth b10715, ROCm0）= prefill **152 t/s** / decode **48.8 t/s**；**Vulkan**（/opt v0.3.0, Vulkan0）= prefill **88.6 t/s** / decode **53.3-53.7 t/s**。两者均 23s 加载、零 fault。结论与 A/B 站 nemotron 规律一致：**Vulkan decode 略优（+9%）、HIP prefill 明显更快（+72%）**。C 站三后端（HIP/Vulkan/CPU）全部可用，HIP 定为主引擎（三站同构），Vulkan 互补。注意：`~/llama.cpp/build` 旧引擎不支持 `--load-mode`，Vulkan 测试须用 `/opt`。详见 [spec/infer-load/research/C站unsloth推理验证](../infer-load/research/C站unsloth推理验证_20260908.md) §8.5 |
| 2026-09-08 | **上游状态核对（fetch 原页）** | 全部 Open 无 merged：**#27754** 40→**41 commits**（8/26 更新，含 mHC 宽残差/KDA；MTP 性能 16K ctx 77.2 t/s 实证）；**#27917** 31 commits Draft（8/28）；**#27752/#27773** 未变（#27773 附 avar6 quantized GGUF 发布）；**#27922** enrichment 未合（mmproj 失败佐证）；**#26578** Open 1 commit（force-push ccbc178，性能 1.12×/1.50× 与台账一致）；**#28047** Open 未修（新增：deepseek4 命中 `dsv4_csa_state_kv_l16`、glm-dsa 命中 `top_k-40`，无 assignee/PR，master f1793c1 仍复现 → 维持 Flash 不受影响、Pro/GLM-5.3 分布式禁用的判据）；**#27332** Open（并入 §1.2 详列）。**结论保持：GLM-5.3 未合入、V4-Flash 引擎升级 P0 不变** |
| 2026-09-09 | **三站模型目录统一（方案 A）+ 迁移后冒烟 ✅** | 散落实体全部搬入 `~/.lmstudio/models/<publisher>/<repo>`，`/data/models/gguf` 反向软链（架构与 §5.7 一致，加载脚本零改动）。B 4 repo / A 2 / C 2（C 由空库变实体库）；misc 归位 lmstudio-community 后删除。C 站真实加载冒烟 gpt-oss-120b（走软链路径）**decode 56.5 t/s** 与基准一致。详见 [spec/operator-optimization/research/模型路径统一方案A](../operator-optimization/research/模型路径统一方案A_20260909.md) |
| 2026-09-09 | **V4-Flash 三站 Vulkan RPC 加载复跑成功 ✅** | 按 9/8 成功形态：B head `/opt/llama.cpp`（v0.3.0, rpc v6.0.0）+ A/C worker（`ggml-rpc-server --device Vulkan0 -c` 50052，**环网 10.10.10.1 / 10.10.11.3**，非 WiFi），模型 split3 分片，`-sm layer` 无 `-ngl 99`。加载 ~4.5min（含 A/C rpccache 命中），三站内存均衡（B52/A54/C53G，无单机全量持有 146G）。冒烟推理 `12*13=156` ✅ decode **7.79 t/s**（=历史 7.9 t/s 基线）。worker 参数修正：`ggml-rpc-server` 缓存为 `-c` 布尔开关（无路径参数） |
| 2026-09-09 | **V4-Flash 整片单文件两机 RPC 验证（A-C / B-C）✅ + split3 删除** | 删 split3 分片（146G）仅留单文件 156G 主资产。单文件经环网 B→A 同步（3m56s @632MB/s，md5 一致）。**两两组合均成功**：A-C（head=A worker=C）decode **9.20 t/s**；B-C（head=B worker=C）**9.11 t/s**，均 `-sm layer` 无 `-ngl 99`，`layer 23→RPC0` 层分布生效，两机内存均衡（head~76G / worker~76G）。**结论：整片单文件两机分布可行且比三站分片更快（-1.4 t/s，少一站 RPC）**；历史"单文件崩溃"根因实为「单机全量持有 + `-ngl 99`」非单文件本身。注：B→C ssh 复杂命令易超时，用脚本内 `setsid nohup ... </dev/null &` 规避；C 管理网 ssh 偶发失败可经 B 跳板 |