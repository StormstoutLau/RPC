# 分布式推理路线可行性调研：CIRU / StrixLink / Skulk（含 vLLM 多机 TP 与 AMD 官方路线）

> **日期**: 2026-09-16
> **触发**: 用户提出"当前分布式 llama 对 V4-Flash / GLM-5.3-Flash 支持力度不够"，要求评估 ① **CIRU StrixLink 部署 GLM-5.3-Flash** 与 ② **引入 Skulk 框架** 两条路线的可行性。
> **证据等级**: E1=本轮实测/原页核实；E3=外部文档/官方站点；**E4=未确认**（明确标注，不采信）
> **核查方式**: 定向联网检索 + fetch 官方文档原页；**不做二手转述推断**

---

## 0. 结论先行

| 路线 | 可行性判定 | 一句话理由 |
|---|---|---|
| **① CIRU**（gfx1151 原生 vLLM/ROCm 发行） | 🟡 **单机可行、多机未证实** | 已确认它面向 **gfx1151 + 128GB UMA**、有 Ling-3.0-Flash 的实测战绩（0.269 → **26.23 t/s**，97.5×）；但 **GLM-5.3-Flash 的 CIRU 构建仅在一处第三方索引页出现（0 runs）**，且**未见任何多机/分布式声明** ⇒ 它解决的是"单站吞吐"，**不是**"分布式支持力度" |
| **② StrixLink** | ⚪ **无法评估（未确认）** | 三轮定向检索 + HF API **均未命中任何**名为 StrixLink 的推理/互联项目（命中的全是 ASUS ROG Strix 主板、USB 延长器等同名无关物）⇒ **需用户提供来源**，本文不臆测 |
| **③ Skulk** | 🟠 **可评估，但解决的不是同一问题** | 官方文档确认 **AMD Linux 支持 = `skulk-llama-server-vulkan` wheel**（我们在支持范围内）；但它**的推理后端就是 llama.cpp**（pinned llama-server，可 `SKULK_LLAMA_SERVER_BIN` 注入自有构建），vLLM 路径**仅 NVIDIA** ⇒ 它解决"多机编排/自愈/统一端点"，**不解决"Asus 上游尚未合并 glm5next"** |
| **④ vLLM 多机 TP（Ray + 定制 RCCL + RoCE v2，kyuz0 路线）** | 🔴 **能力最匹配、但需硬件** | 这是唯一"真·多机张量并行（TP=2、~248GB 合并显存）"的成熟社区方案；**前提是 100GbE RDMA 网卡（Intel E810）+ DAC 直连**，而本集群只有 **USB4 ~9.4Gbps** 直连 ⇒ **硬件门槛** |
| **⑤ 现状路线（llama.cpp RPC）+ 等上游** | ✅ 已跑通、且**有 AMD 官方背书** | AMD 官方 playbook《Clustering Two Ryzen AI Halos with RPC》就是这条：**llama.cpp RPC + ROCm 跑 GLM-4.7 358B 两机**；我们已用它跑通 V4-Flash（decode 14.02 t/s）。真正的瓶颈见 §2 |

**一句话**：用户诊断的"支持力度不够"**根因在上游 PR 未合并 + 我们后端/链路的物理上限**，而不是"缺一个更好的框架"；**Skulk 能补编排、CIRU 能补单站吞吐，但都不改上游事实**；vLLM 多机 TP 才真正改能力上限，代价是 100GbE 硬件。

---

## 1. 现状瓶颈（为什么"支持力度不够"）

引用 [upstream-tracker §1.4](../../spec/upstream-tracker/TRACKER.md) 的实测结论：

1. **GLM-5.3-Flash 根本还没进 llama.cpp 主线**（glm5next 三线 Open；#27754 虽转为 `mergeable_state=unstable` 仍未合）⇒ **无论换哪个前端框架，只要引擎是 llama.cpp，就都装不了它**。
2. **GLM-5.3 的 RPC 有已知未确认问题**（#28360，报告者第二台机器为 **GFX1151 与本集群同架构**）。
3. **V4-Flash 的 `-sm tensor` 主体已合并（#26490，8/24）**，但**RPC 形态的 `-sm tensor` 仍待 #26610** ⇒ 我们现在只能用 `-sm layer`（粗粒度层分布）。
4. 物理链路：三机 **USB4 直连 ~9.4 Gbps**（[strix-halo-llm-perf 实测](http://raw.githubusercontent.com/visorcraft/strix-halo-llm-perf/main/README.md)：两机 USB4 直连 ~9.4 Gbps effective）—— 这对**层分布**够用，对**张量并行**（每层都要 all-reduce）大概率不够（社区 TP 方案一律要求 100GbE RDMA，见 §4）。

> **推论**：要"对 V4/GLM 的支持力度"提升，只有三条路：**(a) 等上游合并**（最便宜）、**(b) 换单站可跑的引擎/量化档**（把"多机"变成"单站"，CIRU 属此类）、**(c) 换真正的多机 TP 栈**（vLLM+Ray+RCCL，需硬件）。

---

## 2. CIRU（gfx1151 原生 vLLM/ROCm 运行时发行）

**已确认的事实**（来源：HuggingFace 模型卡 `jcbtc/Ling-3.0-Flash-CIRU-int4-Strix-native`，经第三方索引页完整引用）：

| 项 | 内容 |
|---|---|
| 它是什么 | "**CIRU's native vLLM/ROCm runtime distribution**" —— 面向 **AMD Strix Halo `gfx1151`** 的运行时发行版：**官方 checkpoint 不改**（不重新量化/不合并/不改名）+ **pinned vLLM fork** + **ROCm 7.15 构建配方** + 在 **Radeon 8060S / 128GB UMA** 上验证过的启动档 |
| 组成 | vLLM commit `d35eb6c` + **15-commit CIRU 分支**（净改动 6 文件 / +365 / −26）；含 `liminfei-amd` 的 **Wave32 LDS fix**（保留原作者署名）；gfx1151 Triton/HSA fault 的 opt-in attention-state merge |
| 实测战绩（Ling-3.0-Flash） | 上游可跑基线 **0.269 t/s** → 本发行 **21.44 t/s**（target-only）/**26.23 t/s**（原生 MTP K1，acceptance 82.35%）＝ **97.55×** |
| 关键优化（按收益排序） | ① **禁用 ROCm skinny-GEMM 在 Wave32 的病态分发**（单这一项 **28.16×**）② vLLM compile mode 3 + graphs off ③ 一致的 ROCm 7.15 / Torch 2.13 / Triton 3.8 栈 ④ W4A16 MoE expert 分配与 reduce ⑤ 多 token verifier 路由 + 原生 MTP K1 ⑥ gfx1151 专用 Triton SiLU-and-multiply kernel |
| **GLM-5.3-Flash 构建** | ⚠️ **仅在一处第三方索引页出现**：`jcbtc/GLM5.3-Flash-CIRU-STRIX-IU4`（**Total runs: 0**）。直接 fetch 该 HF 页面**失败**，二次定向检索**无结果** ⇒ **未证实可用**（IU4 = INT4 档，具体尺寸/显存需求/是否单站可跑**均未知**） |
| **多机/分布式** | **未声明**。模型卡明确"These are **local single-host** measurements" ⇒ **CIRU 不是分布式方案** |

**与本集群契合度（试点成本）**
- ✅ **C 站基本同构**：gfx1151 + 128GB UMA + **ROCm 7.x**（C 站已装 ROCm 7.2.1）⇒ CIRU 的 ROCm 7.15 栈需升级/或用自己的容器，属可控工作。
- ✅ 走 **vLLM**（而非 llama.cpp）⇒ **绕开 glm5next 上游依赖**：**只要 CIRU 的 vLLM fork 支持该架构，就能跑 GLM-5.3-Flash** —— 这正是"支持力度不够"的一条真实出路（**换引擎**而非等上游）。
- ⚠️ **A/B 站是 Vulkan 路线**（无 ROCm/HIP 运行链），CIRU 只在 C 站可试 ⇒ 若走此路，**C 站成唯一 GLM-5.3 承载点**（单站 128GB，是否装得下取决于 IU4 档实际大小——**待验证**）。
- ⚠️ 治理冲突：与"零自加载纪律"和 [ADR-0004](../../adr/ADR-0004-统一管理入口为唯一管理面.md) 的统一管理面需重新对齐（新的启动/落盘形态）。

**结论**：**值得做一次单站试点**（成本可控、绕开上游依赖），但**不要把它当成"分布式方案"**。

---

## 3. StrixLink —— 未确认，不予评估

- 三轮定向检索（`CIRU StrixLink` / `"StrixLink" multi-node Strix Halo` / `"StrixLink" 分布式`）+ HF API 查询**全部未命中**任何相关项目。
- 命中的同名物均为**无关**：ASUS ROG Strix 主板/笔记本、Aniston **StrixLink USB-100**（USB 3.2 延长器）、游戏攻略里的 "Shadowstrix"。
- 因此：**本文不臆测它的形态与能力**。若用户手上有出处（GitHub / HF / Discord / 社区帖），请提供，我可按 [upstream-tracker §1.4](../../spec/upstream-tracker/TRACKER.md) 的做法**fetch 原页**后补一条正式条目。
- 需要留意的**同族命名**：CIRU 的 GLM-5.3 构建名里就含 **STRIX**（`GLM5.3-Flash-CIRU-STRIX-IU4`）⇒ 若 "StrixLink" 是 CIRU 生态的多机组件，它应当是"CIRU 的 vLLM/ROCm + 某种跨机互联"的组合，但**当前无任何公开证据**。

---

## 4. Skulk（多机 AI 计算互联 fabric）

**已确认的事实**（来源：官方文档站点 `foxlight-foundation.github.io/Skulk`，含 `build-and-runtime` 原页）：

| 项 | 内容 |
|---|---|
| 定位 | "**interconnect fabric for multi-node AI compute**" —— 把多台机器组成一个集群，跨机搬工作量"如同单设备"；主打**分布式推理**，对外是**一个 OpenAI 兼容端点**（`/v1/chat/completions`） |
| 三平面 | **compute**（跨机交换模型激活值）/ **control**（集群决策、任务生命周期、节点健康）/ **data**（生成结果回流） |
| 引擎与后端 | **AMD Linux：装 `skulk-llama-server-vulkan` wheel**（NVIDIA Linux 先是 CUDA wheel、失败回退 Vulkan）；macOS 走 in-process MLX；**vLLM 仅 `--with-vllm` 且仅 NVIDIA Linux**；可 `SKULK_LLAMA_SERVER_BIN` **注入自有 llama-server**，`SKULK_NO_ENGINE_AUTOPROVISION=1` 关自动供给 |
| 形态 | macOS 15+/Ubuntu-Debian 包（apt/brew）；dashboard `:52415`；**master 选举 + 自愈 + 崩溃重启 + 节点离开/回归重平衡**；Tailscale 远程；tracing/flight recorder；speech 模型亦可 |
| 分裂方式 | 自行把模型"split across as many machines as it needs"并**按流水路由**（pipeline 式），非 llama.cpp RPC 语义 |

**与本集群的契合/冲突**
- ✅ **AMD Linux + Vulkan 在官方支持路径内**（正是我们的后端）。
- ✅ **引擎可注入** ⇒ 理论上可把"我们自编译含 glm5next 的 llama-server"喂给它 → **这是把 GLM-5.3 拉上多机的唯一非等上游路径**（前提：GLM 分支在 Vulkan/gfx1151 上可用；且 #28360 的 RPC 类问题不在 Skulk 自己的通信层复现）。
- ⚠️ **它不改上游事实**：默认引擎是 pinned llama-server；GLM-5.3 仍需自己编译分支。
- ⚠️ **治理冲突（最需要评估的一条）**：Skulk 是**常驻 supervised service**（开机自启、崩溃自重启）—— 与本集群"**零自加载纪律**"、`load-gate` 内存闸门、[ADR-0004](../../adr/ADR-0004-统一管理入口为唯一管理面.md) 唯一管理面、以及 C 站"看门狗禁用硬规则"**直接冲突**。引入前必须解决"谁管生命周期"。
- ⚠️ 它是**新的一层**（自带 master/placement/存储/端点）⇒ 与现有 `cluster.py` 能力重叠，需按 ADR-0004 的 D3（新增能力三条合法路径）正式裁决，不能并存两套管理面。

**结论**：**可以评估，但要先答"治理归属"**；且它解决的是"多机编排与可用性"，不是"上游模型支持"。**建议作为 §5 的 B 方案试点**（用小模型先验证 Vulkan 引擎注入 + 治理边界）。

---

## 5. 另外两条被检索带出的、更该进评估表的路线

### 5.1 vLLM 多机 TP（Ray + 定制 RCCL + RoCE v2）—— 能力最匹配，硬件是门槛

来源：[kyuz0/amd-strix-halo-vllm-toolboxes](https://github.com/kyuz0/amd-strix-halo-vllm-toolboxes)（含 `rdma_cluster/setup_guide.md`，Fedora 43 实测）

| 项 | 内容 |
|---|---|
| 架构 | **vLLM（TP=2）+ Ray（编排）+ 定制 gfx1151 RCCL（跨机张量同步）+ RoCE v2（RDMA）** |
| 硬件要求 | **2× Strix Halo + 2× 100GbE RDMA NIC（Intel E810-CQDA1）+ DAC 直连**（Framework 主板需 x4→x16 转接）；BIOS iGPU 512MB + 内核参数（`iommu=pt pci=realloc pcie_aspm=off amdgpu.gttsize=... ttm.pages_limit=...`） |
| 收益 | 合并显存 **~248GB**；RDMA 把跨机延迟从 **70-100 µs → ~5 µs** |
| 本项目对照 | 我们**只有 USB4 ~9.4Gbps** 直连、无 100GbE NIC ⇒ **当前不可行**；若采纳，这是一次**硬件决策**（3 台各加 NIC + 转接 + 交换机/DAC） |
| 关键判断 | 这是**唯一真正改变"能力上限"的路线**（TP 而非层流水），也是**唯一能同时吃 GLM-5.3/V4 大档的**（前提：vLLM 侧架构支持，与 CIRU 同源） |

### 5.2 AMD 官方 playbook —— 我们已在走的路线，且有官方背书

来源：[developer.amd.com/playbooks/clustering-rpc-server](https://developer.amd.com/playbooks/clustering-rpc-server/)

- 官方教的就是 **llama.cpp RPC + ROCm 两机跑 GLM-4.7 358B**，含 `amd-ttm --set 120` 调 UMA、BIOS 0.5G 起步、Lemonade SDK 或源码构建。
- ⇒ **我们的现路线与官方一致**；瓶颈不在"路线错"，而在 §1 的上游 PR 与物理链路。

---

## 6. 建议（按性价比排序）

| 序 | 动作 | 成本 | 收益 | 前置 |
|---|---|---|---|---|
| 1 | **等 + 盯 #26610 / #27754**（已在 §1.4 建预警触发） | 0 | 一次性解锁 RPC `-sm tensor` 与 glm5next | 无 |
| 2 | **CIRU 单站试点（C 站）**：验证 gfx1151 上 vLLM/ROCm 能跑 GLM-5.3（若 `GLM5.3-Flash-CIRU-STRIX-IU4` 可获取） | 中（拉权重 + ROCm 7.15 栈） | **绕开上游依赖**，单站即得可用 GLM-5.3（吞吐见 CIRU 战绩） | 需先确认该 IU4 档的实际大小/显存需求（**未证实**） |
| 3 | **Skulk 治理评估**（先答"谁管生命周期"再谈技术） | 小（文档 + 决策）→ 中（试点） | 多机 fabric/自愈/统一端点；引擎可注入 | ADR-0004 裁决；与"零自加载/看门狗禁用"对齐方案 |
| 4 | **100GbE RDMA 硬件评估**（若目标是"真多机 TP 跑大档"） | 大（硬件） | 唯一改变能力上限的路线（~248GB、5µs 级同步） | 硬件预算决策 |
| — | **StrixLink** | — | — | **需用户提供来源**（未确认，不评估） |

**共同前置：任何多机 GLM-5.3 动作，都要先按 [#28360](../../spec/upstream-tracker/TRACKER.md)（同架构报告者的 RPC 问题）做复现自测。**

---

## 7. 待验证清单（进入评估表时随行）

1. `GLM5.3-Flash-CIRU-STRIX-IU4` 是否真实可获取？体积/量化档/显存需求？（**当前 0 runs、页面不可达**）
2. CIRU 是否有多机组件？（若用户所说 StrixLink 即此，需出处）
3. C 站升级到 ROCm 7.15 栈的代价（现 7.2.1；A/B 为 Vulkan 无 ROCm 链）。
4. Skulk 在 AMD Vulkan 下注入**自编译 glm5next llama-server** 是否可行（需小模型先行验证引擎注入）。
5. Skulk 的常驻服务与本集群"零自加载/load-gate/看门狗禁用"的冲突解法。
6. 若上 100GbE：三机 NIC + 转接 + DAC 的采购与 BIOS/内核参数变更（对照 §5.1 的 Fedora 43 配方）。

---

## 8. 来源

- [Skulk 官方文档（Introduction）](https://foxlight-foundation.github.io/Skulk/)｜[Source Builds And Runtime Paths（引擎供给：AMD Linux = `skulk-llama-server-vulkan`）](https://foxlight-foundation.github.io/Skulk/build-and-runtime)
- [CIRU 运行时发行说明（Ling-3.0-Flash-CIRU-int4-Strix-native，经索引页完整引用）](https://www.toolify.ai/ai-model/jcbtc-ling-3-0-flash-ciru-int4-strix-native)（同页列出 `jcbtc/GLM5.3-Flash-CIRU-STRIX-IU4`，Total runs: 0）
- [kyuz0/amd-strix-halo-vllm-toolboxes（vLLM+Ray+RCCL+RoCE v2 集群）](https://github.com/kyuz0/amd-strix-halo-vllm-toolboxes)｜[RDMA 集群设置指南（日文转述）](https://www.hakusoku.com/story/8163)｜[Getting Started（单机 vs RDMA 集群对照）](https://deepwiki.com/kyuz0/amd-strix-halo-vllm-toolboxes/2-getting-started)
- [AMD 官方 playbook: Clustering Two Ryzen AI Halos with RPC](https://developer.amd.com/playbooks/clustering-rpc-server/)
- [strix-halo-llm-perf（USB4 ~9.4 Gbps 实测 + 分布式 RPC 结果）](http://raw.githubusercontent.com/visorcraft/strix-halo-llm-perf/main/README.md)
- 本仓：[upstream-tracker §1.4](../../spec/upstream-tracker/TRACKER.md)｜[ADR-0004](../../adr/ADR-0004-统一管理入口为唯一管理面.md)
