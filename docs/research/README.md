# docs/research — 研究/调研文档索引

> **用途**: 本目录全部调研文档的**导航入口**（避免主题混杂与"同一事实多处维护"）。
> **纪律**: 每个主题**只有一个承载文档**；跨主题内容**建链接、不复制**。上游活数据（PR/引擎基线）的**单一真值**永远是 [spec/upstream-tracker/TRACKER.md](../../spec/upstream-tracker/TRACKER.md)，本目录只引用、不重复维护。
> **建立**: 2026-09-28 · 新增文档时**请同时在本索引登记一行**。

---

## 0. 分布式推理框架调研 · 统一入口（vLLM / SGLang / RCCL / CIRU / Skulk / ds4）

> **先看这里**：回答「本集群跑 GLM-5.3-Flash / DS V4.1-Flash 该用什么多机框架」时，按本节路由；**本节只做索引，不复制结论**。
> **三类真值分工**：上游 PR/引擎基线 → [TRACKER](../../spec/upstream-tracker/TRACKER.md)；**决策** → [ADR-0011](../../adr/ADR-0011-A4-vLLM-TP2-暂缓裁定.md) / [ADR-0010](../../adr/ADR-0010-DwarfStar第二引擎引入立项.md)；**事实与实测** → 下表承载文档。

**阅读顺序（按问题）**

1. **先选型** → [FRAMEWORK-SURVEY-2026-09](../../spec/model-eval/FRAMEWORK-SURVEY-2026-09.md)：llama.cpp RPC / ds4 / vLLM / SGLang 全景与首次判定。
2. **要在 USB4 上做多机 TP** → [CIRU-Skulk 多机 TP](./2026-09-16_分布式推理路线可行性调研_CIRU-Skulk-多机TP.md)：CIRU 双机 GLM **23.69 / 402**、Skulk 只是编排、通用 vLLM TP 需 100GbE。
3. **要问 RCCL 能不能上** → [RCCL 必要性](./2026-09-30_RCCL部署方案与集群必要性评估.md)：RCCL 不是引擎；无消费方；socket 跨机 **182 µs**。
4. **要问 vLLM TP=2 做不做** → [ADR-0011](../../adr/ADR-0011-A4-vLLM-TP2-暂缓裁定.md)：**暂缓**；tg 17.60 < 24；GGUF 不可用，需 AWQ/FP8。
5. **要问 ds4 能不能当第二引擎** → [ADR-0010](../../adr/ADR-0010-DwarfStar第二引擎引入立项.md) + [ds4 执行记录](./2026-09-28_DwarfStar前置核验与ROCm工具链安装决策.md) + [ds4 方案](./2026-09-28_DwarfStar部署专项方案.md)：**观察保留**；旧读数 0.41–0.44 t/s。
6. **GLM-5.3-Flash 怎么跑** → [GLM 系列](./2026-09-28_GLM系列本地推理部署.md)：`glm5next` + 双机 RPC **11.2–11.9 t/s**；MTP 后 **19.40 t/s**（手册 §3.3）。
7. **DS V4.1-Flash 怎么跑** → [DeepSeek V4 系列](./2026-09-28_DeepSeek-V4系列调研与部署.md)：V4.1 与 V4 不同 arch；llama.cpp 无、ds4 官方 V4.1 无 ROCm、vLLM 仅数据中心。
8. **服务化/编排（LiteLLM / llama-swap / exo）** → [双机推理服务化与编排框架调研](../../spec/operator-optimization/research/双机推理服务化与编排框架调研.md)。
9. **互连层（USB4 / RDMA / 100GbE）** → [AMD395 互连调研](../../spec/rpc-optimization/research/AMD395分布式推理高性能互连方案调研.md)。

**框架 → 承载文档 → 当前判定（2026-10-26）**

| 框架/主题 | 权威文档 | 回答什么 | 当前判定 |
|---|---|---|---|
| **llama.cpp RPC** | [FRAMEWORK-SURVEY](../../spec/model-eval/FRAMEWORK-SURVEY-2026-09.md) + 手册 §3.3 | 官方多机/层切分 | **生产基线**；GLM 需变体档 `glm5next`；V4.1 无 `deepseek41` |
| **vLLM** | [ADR-0011](../../adr/ADR-0011-A4-vLLM-TP2-暂缓裁定.md) + [双机服务化调研](../../spec/operator-optimization/research/双机推理服务化与编排框架调研.md) + [kyuz0 评估](./2026-09-30_kyuz0容器方案评估与现役venv对比.md) | TP=2 / RCCL / 容器 | **暂缓**；gfx1151 小模型可用；GLM/V4.1 recipe 仅 **gfx950/MI300X** |
| **SGLang** | [AMD395 互连 §2.5](../../spec/rpc-optimization/research/AMD395分布式推理高性能互连方案调研.md) + [FRAMEWORK-SURVEY](../../spec/model-eval/FRAMEWORK-SURVEY-2026-09.md) | 多节点/PD 分离 | **排除/不建议**：gfx1151 未验证；社区 patch 后仍慢于 vLLM |
| **RCCL** | [RCCL 必要性](./2026-09-30_RCCL部署方案与集群必要性评估.md) | 集合通信库 | **不部署**：无消费方；socket 182 µs |
| **CIRU StrixLink** | [CIRU-Skulk](./2026-09-16_分布式推理路线可行性调研_CIRU-Skulk-多机TP.md) | GLM 双机 TP=2 现成包 | **已取证 23.69 / 402**；需 ROCm10 + Py3.14 + **NHI（内核 7.2.2）**；本集群 6.17 拿不到 |
| **Skulk** | [CIRU-Skulk](./2026-09-16_分布式推理路线可行性调研_CIRU-Skulk-多机TP.md) | 编排/引擎注入 | **不引入**：后端仍是 llama.cpp；常驻 supervisor 与零自加载冲突 |
| **ds4 / DwarfStar** | [ADR-0010](../../adr/ADR-0010-DwarfStar第二引擎引入立项.md) + [执行记录](./2026-09-28_DwarfStar前置核验与ROCm工具链安装决策.md) | 第二引擎/分布式 | **观察保留**；官方 V4.1 ROCm 未实现；**PR #1036** 双机 16.6 / 395（未合）、**PR #1011** GLM 单机 11.9 / 203 |
| **其它（Project Maya / hipEngine / exo / distributed-llama / prima.cpp）** | [FRAMEWORK-SURVEY](../../spec/model-eval/FRAMEWORK-SURVEY-2026-09.md) + [AMD395 §2.5](../../spec/rpc-optimization/research/AMD395分布式推理高性能互连方案调研.md) | 替代运行时 | **不适用/排除**：Maya 是 CUDA 侧 fork；hipEngine 单 GPU；exo 等已排除 |

> **一句话现状（2026-10-26）**：**官方多机只有 llama.cpp RPC**；**GLM 单流极限 = CIRU 23.7**（代价大）；**GLM 实用 = ds4 PR 单机 11.9 或现役 llama RPC 11.2–11.9**；**V4.1 唯一 = ds4 PR #1036 双机 16.6**（100GbE 口径；USB4 40G 未测）；**vLLM/SGLang 在 gfx1151 上对这两个大模型没有可用多机路径**。

> **边界**：本节只做**索引与路由**；上游 PR 状态变化**先改 TRACKER**，再回写本表；任何「换框架」动作**另立 ADR**（ADR-0004 唯一管理面）。

---

## A. 推理引擎与模型部署

| 文档 | 主题（一句话） |
|---|---|
| [2026-09-28_GLM系列本地推理部署.md](./2026-09-28_GLM系列本地推理部署.md) | ★ **GLM 家族（**系列**）在本集群的部署与运维实况**：§0 系列总览（**Flash 与旗舰是两个架构、引擎结论相反**）· **Flash**：`glm5next` 分支引擎引入 / `--engine` 入口 / 起停 / **实测吞吐（双机 11.9、三机 11.2 t/s）** / **1M（KV 24 KiB/token）** · **旗舰 `glm-dsa`：三机 RPC 可行性**（现役主干引擎直接可用） |
| [2026-09-28_DwarfStar前置核验与ROCm工具链安装决策.md](./2026-09-28_DwarfStar前置核验与ROCm工具链安装决策.md) | ★ **DwarfStar (ds4) 主线执行记录**：前置核验 → ROCm 工具链安装与回退 → 构建 → **双机 PP 崩溃根因（上游 #1141）** → PP 自闭环判定 → ds4 存废与存量裁决 → V4.1/Zrald 核查 |
| [2026-09-28_DwarfStar部署专项方案.md](./2026-09-28_DwarfStar部署专项方案.md) | ds4 引入的**规划方案**（立项与能力边界，收口于 ADR-0010） |
| [2026-09-28_DeepSeek-V4系列调研与部署.md](./2026-09-28_DeepSeek-V4系列调研与部署.md) | ★ **DeepSeek V4 家族（**系列**，三份文档合并）**：§0 系列总览 · **第一部** V4-Flash 加载崩溃根因 · **第二部** 复现（无 rpccache / 环网） · **第三部** V4.1-Flash 部署路径（含 V4 系后端更新与 Zrald 社区档核查） |
| [2026-09-28_O-110同站并发实测与O-112单机容量核验.md](./2026-09-28_O-110同站并发实测与O-112单机容量核验.md) | ★ **同站并发的真实代价（H-1a/b/c 判定：2 并发聚合 +32–48%、不成立"~2.8×"）** + **DS V4-Flash 各量化档真实体积与单机容量上界（≈119 GiB）**（承载 `O-110`/`O-112` 的 D-1 实测） |
| [2026-09-30_RCCL部署方案与集群必要性评估.md](./2026-09-30_RCCL部署方案与集群必要性评估.md) | ★ **AMD RCCL 三问**（部署方案 / 模型支持度 / 必要性）⇒ 裁 **当前不部署（无消费方）**。★ 含**两条就地更正**：「RCCL 对 gfx1151 需补丁」**已过期**（ROCm 10 有官方分架构包）；**v1.0 的"跨机挂死"实为本测缺陷**（用了不存在的 `RCCL_SOCKET_IFNAME`）⇒ 改用 `NCCL_SOCKET_IFNAME` 后**跨机实测跑通**（182 µs / `NET/Socket`）。★ §6 = **外部诊断清单逐条对账**。承载 `O-120` |
| [2026-09-30_kyuz0容器方案评估与现役venv对比.md](./2026-09-30_kyuz0容器方案评估与现役venv对比.md) | ★ **`kyuz0/vllm-therock-gfx1151` 容器方案评估**（对比现役 vLLM 栈）⇒ 裁 **当前不引入**。★ 核心洞察：**它与现役 `~/vllm-rocm` 是同一条 TheRock 路线的两种封装**（补丁 RCCL / device 补丁在本集群**已被 AMD 官方渠道覆盖**）。含 E1 前置盘点（Ubuntu 需 Distrobox · daemon 仅 A 站 active）。承载 `O-121` |
| [2026-10-22_上游引擎与GLM-FlashX评估.md](./2026-10-22_上游引擎与GLM-FlashX评估.md) | ★ **上游引擎与 GLM-5.3-Flash-X 评估**（2026-10-22）：① **待办盘点**（台账仍开 5 项，均不阻塞）· ② **llama.cpp** 现役 `23b0202a` → HEAD `e197cef4` = **261 提交**，无 revert、无"必须升"的头部项 ⇒ **先影子 A/B**（EV-14）· ③ **halogen 0.18.11→0.18.13**：Flash checkpoint 不变、temp=0 逐字节一致，★ **A/B：0.18.12 冷 8k/32k prefill 未复现（噪声内）；0.18.13 短请求 TTFT 15.77→0.80 s、流式中断 15.96→0.85 s（代价 +8.9%）** ⇒ **已升级 0.18.13**（重 pin `sha256:2e98dc53…`；三站重建 + `engine` PASS）· ④ **GLM-5.3-Flash-X 无开放权重**（HF `search=flashx` 0 条；仅 OpenRouter `z-ai/glm-5.3-flashx`）⇒ **不可本地部署 · 无替换对象** |
| [2026-10-22_ADR-0014开放项闭环调研.md](./2026-10-22_ADR-0014开放项闭环调研.md) | ★ **ADR-0014 未实测登记 #2/#6/#7/#9 闭环**：**#2** digest pin（建议 `tag@sha256` + drift 检查）· **#6** searxng 共驻实测（144 MiB / 0% CPU；8k/32k 无可测干扰）· **#7** 登记项过期（D4 已于 2026-10-11 回写数字 GID）· **#9** 权重目录落物 1.5 G/站（磁盘余量充足，建议保留） |
| [2026-10-01_Qwen3.8系列本地推理加速调研.md](./2026-10-01_Qwen3.8系列本地推理加速调研.md) | ★★ **Qwen3.8 系列（Flash-Next / 27B）本地推理加速**（**系列级承载文档**；2026-10-01 由 halogen 单题升级）。**已落 = 路线①`halogen-flash-server`**（闭源 OCI 容器 + 私有 `.hgn`）⇒ **裁【暂缓 / 冻结投入】**，承载 `O-137` ｜ ★ **2026-10-11 回写**：已由 [ADR-0014](../../adr/ADR-0014-halogen引擎引入与容器写动作扩权.md) 立项并 **A/B/C 三站真部署**（BYO GGUF 档；P1/P2 落地，**P3 111 GiB `.hgn` 仍冻结**）。★ 路线①的三条要害：**引擎为单硅片写死 ⇒ 是【单站部署】不是机群部署**（RPC 无用）· **62–63 GiB 单文件 >50 GB ⇒ 只能走 `lm-download@` 的 aria2c 分段** · **现役基线自身口径脏**（BASELINE#L18 后端列 Vulkan 而方法列 HIP）。★ 含吞吐对账 + 三条口径警告（后端不同 / 投机 vs 裸 AR / **prompt set 依赖 ~2×**）。★★ **§11 系列级加速路线扫描（2026-10-01 增补，承载 `O-138`）**：**11 条同类路线**（量化档 / 投机解码·MTP / llama.cpp·运行时 fork / 内核后端 / n-gram offload / vLLM·SGLang·ds4·封装类·TensorSharp / MoE 专家感知量化 / 参数面）+ **用户两条线索查证** + 收口（按改动面 P1–P5）+ 未查到清单。★ 两条关键查证：**pwilkin 确在做 llama.cpp/Strix Halo 优化但面向 Qwen3.8-27B（非 Flash-Next）**· **`llama.cpp#27742`(qwen4exp 架构) 已 merged 2026-08-27**，MTP 本体 `#27836`/`#28243` 仍 open（rollback `#28123` 已 merged） ★ **2026-10-22 P1 已执行**：C 站 Vulkan 单机 decode **27.55 / 26.85 t/s**（0.56k / 4.1k tok）；`ncmoe=8` −13%；KV `q8_0` 无差；`-fa off` 长 ctx −5.7%；详见 §11.2a + [o138-p1-20261022](../../spec/rpc-optimization/o138-p1-20261022/) |
| [2026-09-16_分布式推理路线可行性调研_CIRU-Skulk-多机TP.md](./2026-09-16_分布式推理路线可行性调研_CIRU-Skulk-多机TP.md) | 非 llama.cpp 的**多机分布式路线**（CIRU/StrixLink、Skulk）可行性 |
| [2026-09-17_ROCm三站统一7.2.4_总结报告.md](./2026-09-17_ROCm三站统一7.2.4_总结报告.md) | 三站 **ROCm 7.2.4 统一**的起因、执行与验收 |
| [2026-09-21_claude备路免登录与后端选型调研.md](./2026-09-21_claude备路免登录与后端选型调研.md) | agent **备路（claude）免登录**与后端选型 |
| [2026-09-21_D6备路站上化与sensitivity设闸调研与方案.md](./2026-09-21_D6备路站上化与sensitivity设闸调研与方案.md) | D6 **备路站上化** + sensitivity 设闸方案 |
| [2026-10-23_O-165_O-166_备路判定根与golden注入_调研.md](./2026-10-23_O-165_O-166_备路判定根与golden注入_调研.md) | ★★ **备路「执行点 / 判据点 / 注入点」三处 cwd 不一致**（承载 `O-165` + `O-166`）：站上 accept 用**主控陈旧件**判 ⇒ 假绿/假红；golden 注入 scratch 而判据 cwd=`projRoot` ⇒ **必假红**（E1 离线 A/B：rc=**127** vs rc=**0**）。★ 外部锚点（Bazel/GitHub/GitLab/Jenkins/Ansible + 社区 postmortem）五生态收敛：**判据在产出环境跑 · 输入显式入沙箱 · 跨边界显式搬运 · 陈旧工作区是已知假绿源**。方案甲（未裁）= 单一 `$judgeRoot`=执行点 |
| [2026-10-01_Hy4-preview-STQ1_0本集群部署方案调研.md](./2026-10-01_Hy4-preview-STQ1_0本集群部署方案调研.md) | ★ **Hy4-preview（Tencent Hy 770B/49B-active，1M ctx）的 STQ1_0 档能否在本集群部署**（承载 `O-142`）：★★★ **P0 判定 = 【不建议投入 / 转托管】** —— 决定性事实 = **STQ1_0 的上游支持（`llama.cpp#22836`，仍 **Open**）【只有 CPU 后端】**（`ggml-quants.c` dequant + `ggml-cpu` generic vec_dot + ARM NEON，**无 CUDA/Vulkan/Metal/SYCL 内核**），而本集群 **RPC/分布式路径 = Vulkan**（`/opt/llama.cpp`）⇒ ★ **STQ1_0 张量无法 GPU offload**；且 **213.66 GiB > 单机 119.4 GiB（`O-112`）⇒ 必走 RPC ⇒ 正撞这条**。唯一理论险路 = **HIP/ROCm**（llama.cpp HIP 与 CUDA **共用 `ggml-cuda/` 源** ⇒ HF 的 `0002-…-and-cuda.patch` 理论可继承）**但未确证**（HF 补丁抓取失败 + **零公开案例**）。★ 另两条硬事实：**架构串 `hyv4` ≠ 上游 `hy_v4`**（`#28127` 已合并进 v0.4.1，但主线**认不了** AngelSlim 的 GGUF ⇒ 须整套用补丁基线 `0cea36222`）· **RPC worker 端口 50052 写死** ⇒ 载 Hy4 **须先卸** `glm-5.3-flash`/`V4-Flash`。⇒ **建议转托管兜底**（OpenRouter 已上架 hy4-preview，`ADR-0003` egress 已就绪）。⚠ 别把 Vulkan 侧的 **`TQ1_0`**（`#27765`）读成 STQ1_0（**不同格式**）。含 §5 **八条未确证** |

## B. 证据流与可复现性

| 文档 | 主题 |
|---|---|
| [2026-09-16_任务卡证据流可重放性调研.md](./2026-09-16_任务卡证据流可重放性调研.md) | 任务卡**证据流的可重放性**（缺口表来源；收口于 ADR-0007） |
| [2026-09-17_任务卡证据流_协同篡改威胁_补充调研.md](./2026-09-17_任务卡证据流_协同篡改威胁_补充调研.md) | 证据流面对**协同篡改**的威胁模型与上限 |
| [2026-09-18_证据流审计常跑_触发点与成本严重度调研.md](./2026-09-18_证据流审计常跑_触发点与成本严重度调研.md) | 审计**常跑的触发点与成本/严重度** |

## C. 跨站调用 / D6 agent 框架

| 文档 | 主题 |
|---|---|
| [2026-09-14_D6多项目跨站调用与隔离机制分析.md](./2026-09-14_D6多项目跨站调用与隔离机制分析.md) | D6 **多项目跨站调用与隔离**机制 |
| [2026-09-14_OpenRouter接入与agentic-harness门禁调研.md](./2026-09-14_OpenRouter接入与agentic-harness门禁调研.md) | OpenRouter 接入与 agentic-harness 门禁 |
| [2026-09-14_暴露问题调研.md](./2026-09-14_暴露问题调研.md) | 早期**暴露问题**清单与调研 |
| [2026-10-01_图结构编排升级潜力与机群算力利用调研.md](./2026-10-01_图结构编排升级潜力与机群算力利用调研.md) | ★ **该不该把编排升级为【图结构】（LangGraph/CrewAI 等）+ 算力利用**（承载 `O-141`）：★ 核心结论 = 本仓**不是线性流水线而是【半张图】**（`split`+`decompose` **扇出已有且实测真并行**；**缺的是汇聚/依赖边/迭代**）⇒ 升级的实质是**补这三样**而非换框架；★★ **证明搜索的运行形态本身就是图**（goal/subgoal AND-OR 超图，HTPS 实证；★ 首版「要搜索不要图」的**假二分已撤销** —— 须区分**图的领域语义**与**图的执行外壳**）⇒ 对 `Auto_Prover` 先补**一个真实证明的最小闭环**（P3）；★★ **图框架不创造算力，但「上界 3」的射程要说准**（★ **已更正**：`3` 只约束**本地引擎池**；**并发 LLM 资源 > 3** —— ① 本地引擎池 ② **出网 API 池**（三站**独立 OpenRouter 账户**，各 1000 请求/日（实测按账户隔离）· 20 请求/分（★ 官方文档面 E3；官方未写 per account））③ Lean 验证池）· 多节点 TP / PD 分离**不建议**（官方+实测）· 含分级收口 **P0–P5** + 两道治理闸 |
| [2026-10-16_Hermes-Agent编排对比与本框架可借鉴项调研.md](./2026-10-16_Hermes-Agent编排对比与本框架可借鉴项调研.md) | ★ **Hermes Agent 编排对比 + 本框架可借鉴项**（收口于 [CONSTRAINTS](../../spec/d6-agent-standard/CONSTRAINTS.md)）：本框架 = 确定性 wrapper、Hermes = 常驻个人 agent 平台（**不同层**，正确借鉴 = 把 2 个范式折射进既有合规面）—— ① **约束文件**（**不是**人设文件；`SOUL.md`/论文级证据，身份声明近零增益）② 台账真值的只读视图。★ 「是否引入 Hermes」= **已判否**（存量不弃、不复用，与 ADR-0004「零自加载·无 daemon」冲突）· 任务板 DAG 条件触发本轮不做 |

## D. 其它

| 文档 | 主题 |
|---|---|
| [2026-09-28_Textbook并发与派发机制可借鉴性调研.md](./2026-09-28_Textbook并发与派发机制可借鉴性调研.md) | Textbook 的并发/派发机制对本仓的**可借鉴性** |

## E. 集群编排与失败语义

| 文档 | 主题 |
|---|---|
| [2026-10-26_集群编排与RPC选路可靠性_社区外部锚点调研.md](./2026-10-26_集群编排与RPC选路可靠性_社区外部锚点调研.md) | ★ **`cluster.py` 编排/RPC 选路的四个可靠性缺口**（未知态误作忙 · worker 普通引擎未卸载 · 回收失败不传播 · 预检晚于销毁）⇒ **社区外部锚点**（K8s 探针/驱逐/device plugin · systemd `Conflicts=` · Slurm DRAIN · Terraform plan/`create_before_destroy` · Envoy panic threshold 反例 · SLSA digest）→ 可迁移机制 + 不可照搬清单 + 契约级设计与 14 条先验红夹具 |

## F. 代码评审复核

| 文档 | 主题 |
|---|---|
| [2026-10-26_原始评审报告复核_RPC.md](./2026-10-26_原始评审报告复核_RPC.md) | ★ **2026-10-21 原始评审报告 RPC 段落档 + 当前 HEAD 复核**：10 条发现（1 CRITICAL / 2 HIGH / 5 MEDIUM / 2 LOW）⇒ **1 已闭环 · 1 部分 · 8 未闭环**；7 条建议 1 完成 / 1 部分 / 5 未做；按报告口径仍「阻断」（凭据轮换未做，O-173） |
| [2026-10-26_原始评审P1_社区外部锚点调研.md](./2026-10-26_原始评审P1_社区外部锚点调研.md) | ★ **P1 四条**（#3 模型定位 depth-2 · #4 conf 引号/`sed` 转义 · #7 ds4 监听默认 `0.0.0.0` · #10 Web token `==` + URL query）⇒ **外部锚点**（GNU find 深度语义 · ShellCheck SC2086 · GNU sed 转义 · BashFAQ 105 · CWE-1327 · PostgreSQL/Ollama 安全默认 · Python `compare_digest` · RFC 6750 §2.3 · `Referrer-Policy`）→ 可迁移/不可照搬 + 契约级设计与先验红测试方向 |

---

## 单一真值在哪（本目录之外）

| 需要什么 | 去哪（**不要去别处找**） |
|---|---|
| **上游 PR/Issue 状态 + 引擎基线** | [spec/upstream-tracker/TRACKER.md](../../spec/upstream-tracker/TRACKER.md)（§1.1 GLM / §1.2c V4.1 / §2.x 引擎基线） |
| **管理面纪律（唯一管理入口）** | [adr/ADR-0004](../../adr/ADR-0004-统一管理入口为唯一管理面.md) |
| **引擎升级 SOP / 版本目录 / MANIFEST** | [spec/vulkan-version-control/UPGRADE_SOP.md](../../spec/vulkan-version-control/UPGRADE_SOP.md) |
| **ds4 引入裁决** | [adr/ADR-0010](../../adr/ADR-0010-DwarfStar第二引擎引入立项.md)（v1.2：观察保留） |
| **ds4 管理面设计** | [spec/ds4-backend/DESIGN.md](../../spec/ds4-backend/DESIGN.md) |
| **证据流路线与阶段** | [adr/ADR-0007](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md) |
| **模型选型/来源** | [spec/model-eval/MODEL-SOURCING-2026-09.md](../../spec/model-eval/MODEL-SOURCING-2026-09.md) · [SOURCING-INDEX](../../spec/model-eval/SOURCING-INDEX.md) |
| **端口/服务登记** | [inventory/ports.yaml](../../inventory/ports.yaml) |
| **未决事项** | [spec/d6-agent-standard/OPEN-ISSUES.md](../../spec/d6-agent-standard/OPEN-ISSUES.md) |
