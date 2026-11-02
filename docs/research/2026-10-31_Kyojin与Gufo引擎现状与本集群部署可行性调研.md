# Kyojin 与 Gufo 引擎现状 · 本集群部署可行性 · 与现有配置的优势劣势

---------------------------------------------------------------------

id: research-kyojin-gufo-20261031
type: research
version: 1.0
status: active
date: 2026-10-31
depends: [ADR-0004, ADR-0014, ADR-0015]
related: [O-180, O-181, O-182, O-183]

---------------------------------------------------------------------

> **一句话**：用户所问的「Kyojin Gufo 引擎」实为**两个独立引擎** —— **Kyojin**（`Yamz-Labs/kyojin`，基于 ExLlamaV3，EXL3 权重）与 **Gufo**（`gufo-org/gufo`，C++/HIP，GGUF）。两者都是 **MIT · 单机单硅片 · 专为 Strix Halo / gfx1151 / 128 GiB UMA 优化**，与我们三站硬件**完全同构**，可与现役 halogen 同定位替换；**但两者都只有 OpenAI 面、都没有多机 RPC** ⇒ **不能替代 llama.cpp Vulkan RPC 分布式轴**。
>
> **取证级别**：**E3 外网**（GitHub API 直读 + 第三方实测页 + 上游 README 自报），**本仓未做任何实测**。⚠ 本报告所有性能数字**分两档标注**：`[自报]` = 上游 README 自述，`[三方]` = llmkube 实验室同机对照实测。

---

## 0. 名称澄清（先纠正前提）

用户原话是「Kyojin Gufo引擎」。核查结论：**没有名为 "Kyojin Gufo" 的单一项目**，这是两个**不同团队、不同底座、不同权重格式**的引擎：

| | Kyojin | Gufo |
|---|---|---|
| 仓库 | `Yamz-Labs/kyojin` | `gufo-org/gufo` |
| 底座 | **ExLlamaV3**（turboderp），ROCm 工作来自 sdougbrown / vcruz305 | **自研 C++/HIP** |
| 权重格式 | **EXL3**（`yamz-labs/*-EXL3-Yamz`） | **GGUF**（unsloth 等社区档） |
| 许可 | **MIT** | **MIT** |
| Stars | 219 | **1,000** |
| 最新版本 | **v1.8.3**（tags 连续到 10-30） | **v0.28.0**（Release 2026-10-30T13:08:51Z） |
| 自述定位 | 「在一台迷你机或一张显卡上跑最大的开放模型，约为 llama.cpp 的 2 倍」 | 「The Open Source Strix Halo AI engine」 |

⚠ **两个引擎都在 10-30 当天有新版本**，迭代节奏分别接近「每天一版」（Gufo v0.23 10-24 → v0.28 10-30）。

---

## 1. 现状：上游能力面

### 1.1 Gufo

| 维度 | 事实 | 级别 |
|---|---|---|
| 硬件目标 | **只针对 Strix Halo 128 GiB**（原话：*"Build and optimize specifically for the Strix Halo 128 GiB hardware"*） | E3 |
| 模型策略 | 只支持「该尺寸下最好的可用模型」，**不跨模型复用 kernel**（*"Don't reuse kernels across different models to limit blast radius"*） | E3 |
| 服务面 | **OpenAI 兼容** `/v1/chat/completions` + **Responses API**（text / images / function tools / structured output / streaming） | E3 |
| **Anthropic `/v1/messages`** | **README 全文未提及** ⇒ **未证实**（**这是对我们最关键的未知项**） | E3（缺口） |
| 多机 / RPC | **README 未提及** ⇒ **未证实**（判断为单机） | E3（缺口） |
| 并发 | `--sessions 2`（llmkube 实测两路并发）；README 自报 8 并发聚合 | E3 |
| 投机解码 | `--speculative mtp`（shared MTP head `mtp-*-shared-Q8_0.gguf`）· Qwen3.8-27B 另有 **DFlash2** | E3 |
| 模型覆盖 | Qwen3.8-Flash-Next · Qwen3.8-27B · **DeepSeek V4 Flash**（DSpark） | E3 |
| 分发形态 | 源码构建（Nix / cmake）· **容器镜像** `ghcr.io/defilantech/llmkube-gufo-rocm-gfx1151`（ROCm 7.2.3，**按 digest 钉死**） | E3 |

**Gufo 自报性能**（`[自报]`，README 表；口径见 §1.1a —— `116.93` 是 **repetitive 峰值**，同条件 **mixed 仅 35.79**）：

| 模型 | prefill | decode 单用户 | 8 并发聚合 |
|---|---|---|---|
| **Qwen3.8-Flash-Next Q4_K_XL（AR）** | **1,801.01 tok/s** | **116.93 tok/s**（MTP） | **245.81 tok/s** |
| Qwen3.8-27B Q4_K_XL（DFlash2） | 648.89 tok/s | 71.55 tok/s | 128.42 tok/s |
| DeepSeek V4 Flash（DSpark） | 484.62 tok/s | 26.62 tok/s | 54.74 tok/s |

**Gufo 第三方同机实测**（`[三方]`，llmkube，2026-10-02，**Gufo v0.5.0**，与 llama.cpp 同机同卷同限额对照）：

| Prompt | Gufo Q4 | llama.cpp 四档最优 | 倍率 |
|---|---|---|---|
| 8K | 1,343 tok/s | 361 tok/s | 3.7× |
| 32K | 1,286 tok/s | 307 tok/s | 4.2× |
| 131K | 1,213 tok/s | 137 tok/s | 8.8× |
| **250K** | **1,184 tok/s** | 101 tok/s | **11.7×** |

| 首 token（冷） | Gufo | llama.cpp |
|---|---|---|
| 131K | **108 s** | 953 s |
| **250K** | **211 s** | 2,464 s（41 分钟） |

**形状差异比倍率更重要**：Gufo 从 8K 到 250K 只掉 **12%** prefill 速率；llama.cpp Vulkan 掉 **72%**。llmkube 给出的原因：**llama.cpp Vulkan 的 chunked DeltaNet prefill shader 尚未启用，36 层 DeltaNet 逐 token prefill**。

decode 对照（`[三方]`，agent 形态 4K prompt + 512 输出，thinking 默认开）：

| | Gufo Q4（sessions 2） | llama.cpp Q3（单槽） |
|---|---|---|
| 单流 | **33.5 tok/s** | 36.2 tok/s（Gufo 慢 **7%**） |
| 双流 | **26.5 + 28.1 同时**（合 54.6） | 37.2 / 35.2 **串行** |
| 双流 TTFT | 6.0 s / 6.0 s | 13.6 s / 41.8 s |

#### 1.1a 社区是否复现官方 decode 数字（2026-10-31 补充核查）

**先看官方自己的口径**：README 头条的 `116.93 tok/s` **不是"任意文本"的 decode**，而是官方 BENCHMARKS 表里 `tg128` 的 **repetitive（重复文本）档**；同一行并列的 **mixed（混合真实文本）档只有 35.79 tok/s**。README 表下脚注原文 *"Peaks include repetitive output"*。

| Flash-Next Q4 MTP（单用户，context 4096） | Gufo tg mixed | Gufo tg repetitive | llama.cpp tg mixed |
|---|---:|---:|---:|
| depth 0 | **35.79** | **116.93 ± 0.10** | 31.73 |
| 4,096 | 37.64 | 116.41 ± 0.07 | 34.48 |
| 8,192 | 36.91 | 114.08 ± 0.01 | 32.20 |

**社区四个独立测量（全部只在官方镜像/上游代码上跑，未做引擎改造，除 #474 自编译 kernel）**：

| 来源 | 条件 | decode 读数 | 同时测的 halogen |
|---|---|---|---|
| llmkube（2026-10-02，v0.5.0） | agent 形态 4K prompt + 512 输出，thinking 开，`--sessions 2` | **33.5 单流** · soak 3 小时中位 **35–39** · 双流 26.5 + 28.1 | llama.cpp 36.2（Gufo 慢 7%） |
| Michael Kofler（2026-10-09，Fedora / Framework Desktop 128 GB） | 官方 podman 镜像 + `--speculative mtp` + `--sessions 2` + `--context 262144`；HumanEval+ 前 40 题，greedy，`reasoning_effort: low` | **52.2**（407 s 跑完 40 题；终端观感 35–50，多为 ~40） | **61.6**（356 s）；「Halogen 快约 12% 时间 / 18% 吞吐」 |
| gufo issue **#474**（2026-10-07，gufo 0.8.0 + 自编译 dense Q4_1 kernel） | 24 条 pi agent 任务；另 replay 198 条真实会话（中位 16.6k prompt） | 上游基线 **46.5** → 调优后 **54.5**；replay 0–8k **48.2** / 8–32k **46.5** / 32k+ **47.8** | ht43 **~60**（固定 depth 2）；gufo = **0.85×** halogen |
| Habr 评论（MrDetrox） | 日常使用 | **~40** | **~60** |

**结论（分三层，勿混为一谈）**：

1. ★ **能复现的是官方 mixed 档，不能复现 README 头条。** 33.5 / 35–39 / 46.5 / 48–52 全部落在 **mixed 35.8–37.6** 的 ±30% 内（高的两档是代码输出或自编译 kernel），而 **116.93 无人复现** —— 因为它是 **repetitive 合成负载的峰值**，不是真实输出。
2. ★ **prefill 自报可复现。** #474 实测冷 prefill **1,540 tok/s**（gufo）vs 1,800（halogen），与自报 `1,801.01 pp` 同量级；llmkube 的 1,343–1,184 是 8K–250K 档，同样成立。
3. ★ **社区一致认为 Gufo decode 慢于 halogen**：0.85×（#474 replay）· 52.2 vs 61.6（Kofler）· ~40 vs ~60（Habr）。差异来源经 #474 定位：**不是 draft 接受率**（gufo 每步 3.15 token，反而高于 halogen 的 ~2.5），而是**每步成本 57.5 ms vs 42 ms**（约 15 ms/步，推测 halogen 的 fused q4 MoE grouped GEMM + 更小权重字节 3.6 bpw）。

**旁证：版本间 decode 本身在 ±6–18% 波动**（上游 issue #475 `0.5.0` 比 `23cacbb` 慢 12–18%、#598 −6.2%、#632 −5.72%、#684 210k 处 −6%、#863 换 ROCm 版本 −12.6%）⇒ README 的单点峰值**不能当作稳定产能**。社区也**没有统一提交渠道**（#809 OPEN：不同机器/功耗档/OS 的数字目前不可互比）。

**对本报告的修正**：原 §4.1 劣势 4/5 的「3.5 倍量级不一致」应改为「**官方 mixed 与社区一致；头条数字是 repetitive 峰值**」。换 Gufo 的收益仍主要在 **262K 原生 + prefill 形状**，**不在 decode**。

### 1.2 Kyojin

| 维度 | 事实 | 级别 |
|---|---|---|
| 硬件 | **AMD (ROCm) + NVIDIA (CUDA)** —— 比 Gufo 宽 | E3 |
| 权重 | **EXL3 only**（如 `yamz-labs/Qwen3.8-Flash-Next-EXL3-Yamz`，约 **95 GB**）—— **不支持 GGUF** | E3 |
| 服务面 | **OpenAI API，端口 8000** | E3 |
| Anthropic `/v1/messages` | **未提及** ⇒ 未证实 | E3（缺口） |
| 多机 / RPC | **未提及** ⇒ 未证实 | E3（缺口） |
| **SSD 分层** | ★ **DeepSeek-V4.1-Flash-1017（763B / 16B active）** 的 **172 GiB EXL3** 能在 **128 GB 内存 + NVMe** 上跑：专家池驻 RAM，其余按需读 SSD，用模型自带 DSpark draft + Engram 表 | E3 |
| **Uncensored mode** | ★ 每模型可选，**加载时应用、权重不动**；GLM-5.3-Flash 与 MiMo-V2.6-Flash 有现成 pack，Qwen3.8-Flash-Next pack 内置但默认关 | E3 |
| 相对 llama.cpp | 「约 2× 快」；Qwen3.8-27B EXL3 4.0bpw + MTP + n-gram：**decode 各深度均领先**；**llama.cpp 在 32K 内 prefill 快 10–19%** | E3 |
| ⚠ 质量不可比 | 上游明示：*"Weights differ between engines (EXL3 against GGUF), so quality is not compared"* | E3 |

---

## 2. 与本集群现有配置的对照

### 2.1 现有三条引擎轴（本仓实测，E1）

| 轴 | 引擎 | 拓扑 | 上下文 | 实测 prefill | 实测 decode | Anthropic 面 |
|---|---|---|---|---|---|---|
| ① 分布式 | llama.cpp `master-23b0202a` + `-sm layer` | **B head + A worker（Vulkan RPC）** | 65K–262K | 随长度崩：`llmkube` 对照里 250K 仅 **101 tok/s** | 13.8–36.2 tok/s | 无（OpenAI） |
| ② 单站生产 | **halogen 0.18.18**（闭源 `.hgn` + GGUF 直读） | 三站各自 `127.0.0.1:8731` | **1M（`ROPE_YARN=4`）** | **1,227–1,285 tok/s**（`O-183` 实测：737,280 tok @ 600.5 s） | C 47.7 / A 41.6 / B 40.3 tok/s | **有 `/v1/messages`** |
| ③ 单站回退 | unsloth studio（HIP，`--backend unsloth`） | 单站 | 视 conf | 未系统测 | 未系统测 | 无 |

### 2.2 关键交点：**halogen 的 prefill 与 Gufo 几乎同速**

| | halogen 实测（E1，75.5 万 token 长会话） | Gufo `[三方]`（250K） |
|---|---|---|
| prefill | **1,227 / 1,285 tok/s** | 1,184 tok/s |
| 上下文上限 | 1,048,576（YaRN 4×） | **262,144（原生，无 YaRN）** |
| 每轮固定成本 | ★ **每请求都跑 scaled RoPE**（`#225`：+0.4–0.6% ppl、draft 少 5–15 点、decode 慢 ~10%） | **无此成本** |

⇒ ★★ **换 Gufo 不会让"每 token 的 prefill"更快多少；它改变的是"要 prefill 多少 token"** —— 262K 原生上限把 `O-183` 的 75.5 万 token 死循环直接消掉（250K 冷启 TTFT 211 s < 600 s 超时）。

⇒ 反之，**继续留在 halogen 1M 档就必须每轮付 `#225` 的 YaRN 税**，且 75.5 万 token 的压缩请求**在数学上永远超 600 s**。

### 2.3 模型档位对照（能否复用现有权重）

| | 现役 halogen | Gufo | Kyojin |
|---|---|---|---|
| Qwen3.8-Flash-Next | 站上 `UD-IQ4_XS` 三片 ≈ **93.7 GB**（GGUF）+ 需 draft head | 官方验证档 **`UD-Q4_K_XL` = 103.69 GiB**（GGUF）+ shared MTP Q8_0 | **EXL3 95 GB**（需重下） |
| 能否直接用现有 GGUF | — | **IQ4_XS 未在官方验证列表**（技术上标准 GGUF，**未证实**） | **不能**（EXL3 ≠ GGUF） |
| Qwen3.8-27B | 站上有 | ✓ Q4/Q8 + DFlash2 | ✓ EXL3 4.0bpw |
| DeepSeek V4 Flash | ✓（llama.cpp RPC 轴） | ✓（DSpark，484 pp / 26.62 tg）[自报] | ✓（**含 V4.1-Flash 763B 的 SSD 分层**） |
| GLM-5.3-Flash | ✓（`glm5next` 变体档） | **未列** | ✓（含 Uncensored pack） |

---

## 3. 集群部署可行性

### 3.1 硬件与运行时（结论：**硬件完全匹配，运行时需核对**）

| 项 | 事实 | 判定 |
|---|---|---|
| GPU 架构 | 三站均 `gfx1151`（Strix Halo，Radeon 8060S） | ✓ **两引擎的第一目标平台** |
| 内存 | `mem_info_gtt_total` 125,829,120,000 B ⇒ 117.2 GiB；`STATION_RESERVED_GIB=8` | ✓ 与两引擎的 128 GiB 前提一致 |
| ROCm 版本 | A 站系统 ROCm **6.4.1**；B/C 无系统 ROCm，靠 studio bundled（`libamdhip64.so.7.16.26332`） | ⚠ **Gufo 官方镜像内是 ROCm 7.2.3** ⇒ 走**容器**可绕开宿主版本；走**源码/裸二进制**则要重装 ROCm |
| 容器 | 三站 `dockerd` 已装（`containers install` 已落地，A/B/C `docker: active`） | ✓ 可直接跑 `ghcr.io/.../llmkube-gufo-rocm-gfx1151` |
| 端口 | 三站 `8731` 已被 halogen 占（A/B `127.0.0.1:8731`，C 另加 `8080:8731`） | ⚠ **Gufo 默认 8080**（C 站 8080 已占）⇒ 必须另选端口并与 `inventory/ports.yaml` 对齐 |

### 3.2 三条硬门（逐条判）

| 门 | Gufo | Kyojin | 影响 |
|---|---|---|---|
| **① Anthropic `/v1/messages`**（Claude Code 直连的前提） | **未证实**（README 只有 OpenAI + Responses） | **未证实**（只有 OpenAI，端口 8000） | ★★ **最硬的未知**：现役 halogen 有，换任何一方都要加网关（LiteLLM 等）或改客户端 |
| **② 多机 / RPC** | 未提及 ⇒ 判单机 | 未提及 ⇒ 判单机 | 两者**都不能替代 llama.cpp Vulkan RPC 双机轴**；只能与 halogen 同定位（三站各自一份） |
| **③ `model` 字段语义** | ★ **不匹配即 404**（llmkube 原文：*"Gufo answers a request for any other model id with 404 model_not_found"*） | 未记载 | ⚠ 与现役 halogen **相反**（halogen **忽略** `model`，实测 `model=main` 仍 200）⇒ 客户端配置要逐站点名对齐 |

### 3.3 治理面（承 ADR-0004 / ADR-0014 / ADR-0015）

| 约束 | 现状 | 对两引擎的含义 |
|---|---|---|
| **唯一管理面**（ADR-0004 D2） | `ops/cluster.py` · 不新增并列脚本 | 接入须走 `CONTAINER_MODELS` 式配方（halogen 已是这个形态），**不许写一次性 docker 脚本** |
| **零自加载纪律**（ADR-0004:323，「无 daemon；容器与之冲突」） | 已被 **ADR-0014 / ADR-0015** 两次例外化 | 再加一条引擎 = **第三次例外**，须**另立 ADR**（不能读成 ADR-0014 的延伸） |
| **loopback 发布**（ADR-0014 D4） | 三站 halogen 已 `127.0.0.1` | Gufo **同样无鉴权**（未审计）⇒ 必须 **loopback** |
| **端口真值**（ADR-0014 D3） | `inventory/ports.yaml` 单一真值 | 新端口须先登记，否则 `stations` 断言会红 |

---

## 4. 优势 / 劣势（对本集群的实际账）

### 4.1 Gufo

**优势**

1. ★ **原生 262K，不付 YaRN 税** —— 直接消掉 `O-183` 的死循环（250K TTFT 211 s < 600 s），且免掉 `#225` 的每轮成本。
2. ★ **长 prompt 的 prefill 不掉速**（8K→250K 仅 -12%，llama.cpp -72%），根因是 **llama.cpp Vulkan 缺 chunked DeltaNet prefill shader** ⇒ **这是我们现役 llama.cpp 轴的已知短板**。
3. **MIT 开源 + 1000 stars + 每天迭代**，比闭源 halogen 的**可审计性**高（对"闭源引擎"的顾虑正是 `#82` PR 的动机）。
4. **GGUF 生态**：可直接吃 unsloth 档，与我们现有权重管理方式一致。
5. **8 并发聚合 245 tok/s**（`[自报]`）—— 我们现役是**单并发铁律**（O-18），若未来要放开并发，这是唯一有数据的候选。
6. 官方有 **gfx1151 专用容器镜像**（digest 可钉死），与我们 `CONTAINER_MODELS` 的 pin 文化天然契合。

**劣势**

1. ★★ **Anthropic `/v1/messages` 未证实** —— 这是 Claude Code 接入的**唯一硬门**；halogen 有，Gufo 没有（README 只有 OpenAI/Responses）。加网关会引入**新的常驻进程/新管理面**（撞 ADR-0004）。
2. ★ **`model` 名不匹配直接 404** —— 与 halogen「忽略 model」相反，三站客户端配置要逐站对齐 `--served-model-name`，否则**静默 404**（比卤素更难排查）。
3. **单机**（未证实多机）⇒ 接不了分布式轴。
4. **decode 单流慢约 7%**（llmkube v0.5.0 实测 33.5 vs 36.2）；且 `--sessions 2` 会**分摊**带宽（26.5+28.1）。
5. ★ **decode 慢于 halogen，且 README 头条不可引用** —— 官方 `116.93` 是 **repetitive 峰值**，同条件 **mixed 35.79**（§1.1a）；社区三方一致给 **0.85× halogen**（#474 replay 46.5–48.2 vs ~60，Kofler 52.2 vs 61.6，Habr ~40 vs ~60），**不是量级失真，是负载口径**。换 Gufo 的收益在 262K/ prefill，**不在 decode**。
6. 模型覆盖窄（只 3 个家族），**GLM-5.3-Flash 未列**。

### 4.2 Kyojin

**优势**

1. ★ **decode 领先**（Qwen27 各深度超 llama.cpp；EXL3 + MTP + n-gram）。
2. ★★ **SSD 分层跑超大模型**：**DeepSeek V4.1-Flash 763B（172 GiB EXL3）** 在 128 GB + NVMe 上跑 —— 这是我们 `O-179`/DS 家族从未有过的路线（llama.cpp 需要 246–414 GiB 档，只能三站 RPC）。
3. ★★ **Uncensored mode 内建**（加载时应用、权重不动）—— 直接呼应 `O-182`「无审查版本」的需求，且**比换权重更省盘**。
4. **MIT**，AMD + NVIDIA 双支持。

**劣势**

1. ★★ **EXL3 only** —— 我们现役 `UD-IQ4_XS`（93.7 GB GGUF）**完全不能用**，必须重下 ~95 GB pack；`CONTAINER_MODELS` 的权重映射要重做。
2. ★ **OpenAI only（端口 8000）**，Anthropic 面未证实。
3. **prefill 比 llama.cpp 慢 10–19%（32K 内）** —— 与我们 `O-183` 最痛的点**反方向**。
4. **质量不可比**：上游明示 EXL3 与 GGUF 权重不同、不做质量对照 ⇒ 换引擎 = **换权重**，`COMMUNITY` 的 golden 集要重跑。
5. 生态小（219 stars），单机。
6. **Uncensored mode 的合规/审计含义未评估**（本报告不作判断，仅登记）。

### 4.3 两者共同的劣势

- **都不能替代 llama.cpp 分布式轴**（无 RPC）⇒ 即便接入，也只是「halogen 的替代」，**三站拓扑不变**。
- **都要第三次给 ADR-0004 开口子**（常驻容器例外）。
- **都要重做权重映射**（Gufo 换 Q4_K_XL / Kyojin 换 EXL3），`halogen-assets` 与 `models` 断言要重配。
- **都缺 Anthropic 面证据** ⇒ 在拿到 `/v1/messages` 实测之前，**Claude Code 接入这条路不成立**。

---

## 5. 判定与建议

### 5.1 三条可选动作（按性价比）

| 选项 | 内容 | 前置 | 代价 |
|---|---|---|---|
| **A（推荐先做）** | **只验 Anthropic 面**：在三站之一起 Gufo 容器，**只发一条 `/v1/messages`**，确认 200 或 404 | 无（容器已在） | 半小时内可判死；**不改任何生产配置** |
| B | 若 A 通过 ⇒ **单站影子 A/B**（同 alias、conf 快照、不切 symlink），比 `O-183` 的两个硬指标：**250K 冷 TTFT** 与 **单流 decode** | A 通过 + 新 ADR | 重下 Q4_K_XL（103.69 GiB） |
| C | Kyojin 作为 **`O-182` 的解法**（Uncensored）+ **DS V4.1 SSD 分层**的候选 | 独立立项 | 重下 EXL3 95 GB / 172 GiB；合规评估 |

### 5.2 明确的「不做」

- **不换 llama.cpp 分布式轴**（两引擎无 RPC）。
- **不在拿到 `/v1/messages` 证据前**动三站客户端配置。
- **不引用 `[自报]` 数字当结论**：头条 `116.93` 是 **repetitive 峰值**，真实文本用 **mixed 35.79**（§1.1a）。

### 5.3 与现有台账的关系

- `O-183`（compaction 超时）⇒ **Gufo 的 262K 原生是"根治候选"**，但需 `A` 步先过 Anthropic 门。
- `O-182`（无审查模型）⇒ **Kyojin 的 Uncensored mode 是"不用换权重"的第二条路**（原调研只找了 abliterated GGUF）。
- `O-180`（长 prefill 慢）⇒ **Gufo 的 DeltaNet prefill 优势命中 llama.cpp 轴**，与 halogen 无关。
- `EV-15/EV-16`（halogen 版本跟进）⇒ 与本报告**正交**，不冲突。

---

## 6. 未实测登记（如实）

| # | 未证实项 | 阻塞程度 |
|---|---|---|
| 1 | **Gufo 是否实现 `/v1/messages`** | ★★ **决定 Claude Code 能否直连** |
| 2 | **Kyojin 是否实现 Anthropic 面** | ★★ 同上 |
| 3 | 两引擎是否支持**多机 / RPC** | ★ 决定能否触及分布式轴 |
| 4 | Gufo 能否加载我们现有 **`UD-IQ4_XS`**（非官方验证档） | ★ 决定是否要重下 103.69 GiB |
| 5 | ~~`[自报]` 1,801 pp / 116.93 tg 的测试条件~~ **已闭环（2026-10-31）**：官方 BENCHMARKS 给双档 —— **mixed 35.79 / repetitive 116.93**；README 脚注 *"Peaks include repetitive output"* | ✅ 结论 = **头条只用 repetitive，真实文本用 mixed**（§1.1a） |
| 6 | Gufo/Kyojin 在**三站实测**的 prefill/decode（本仓零实测） | ★ |
| 7 | Gufo 容器在**我们宿主 ROCm 6.4.1** 下能否正常起（镜像内是 7.2.3） | ⚠ 运行时门 |
| 8 | Kyojin **Uncensored mode** 的合规与审计含义 | ⚠ 需裁 |
| 9 | Kyojin SSD 分层在**我们 NVMe 容量/带宽**下的实际 tok/s | ⚠ |

---

## 7. 来源

| # | 来源 | 用途 |
|---|---|---|
| 1 | [gufo-org/gufo](https://github.com/gufo-org/gufo)（GitHub API 实读 README，2026-10-31） | 版本 v0.28.0 · MIT · 1,000 stars · 模型表与自报数字 · 硬件定位 · OpenAI/Responses 面 |
| 2 | [Qwen3.8-Flash-Next on Gufo on one Strix Halo](https://llmkube.com/docs/labs/qwen38-flash-next-gufo-on-strix-halo)（LLMKube，2026-10-02，Gufo v0.5.0） | **第三方同机对照实测**：prefill 4 档、TTFT、decode 单/双流、llama.cpp 对比、`--served-model-name` 404 行为、容器 digest |
| 3 | [Trying a new engine on the Strix Halo: 41 minutes to first token became 3.5](https://llmkube.com/blog/qwen38-flash-next-gufo-strix-halo)（LLMKube Blog） | 同上背景与"替换 llama.cpp Vulkan 构建"的动机 |
| 4 | [Yamz-Labs/kyojin](https://github.com/Yamz-Labs/kyojin)（GitHub API 实读 README，2026-10-31） | 版本 v1.8.3 · MIT · 219 stars · EXL3 · SSD 分层（DS V4.1 763B）· Uncensored mode · prefill 落后 10–19% |
| 5 | [Two ~300B MoE models, each on ONE 128 GB mini PC](https://prismix.dev/news/8c69dc3c670a) | Kyojin 100 GB 级 MoE 单机能力 · 基于 ExLlamaV3 · ROCm 贡献者 |
| 6 | [Qwen3.8-Flash-Next (125B) on a single Strix Halo: 44-59 tok/s](https://prismix.dev/news/1ee5fd82e0c1) | Kyojin 侧 Qwen3.8-Flash-Next 的 EXL3 pack 与投机解码数字 |
| 7 | [evermx.com/open-source](https://evermx.com/open-source) | 两仓库许可与 star 数的旁证（MIT / 850→1,000 区间） |
| 8 | 本仓既有实测（E1） | halogen 0.18.18 的 1,227–1,285 tok/s（`O-183`）· 三站 decode 47.7/41.6/40.3 · llama.cpp 轴 `/opt` 拓扑 · `UD-IQ4_XS` 93.7 GB · GTT 117.2 GiB |
| 9 | [gufo BENCHMARKS.md（qwen3.8-flash-next）](https://github.com/gufo-org/gufo/blob/main/docs/models/qwen3.8-flash-next/BENCHMARKS.md)（GitHub API 实读，2026-10-31） | ★ **官方双档拆分**：`tg mixed 35.79` / `tg repetitive 116.93`（depth 0/4k/8k）· llama.cpp mixed 31.73 · 8 并发表 |
| 10 | [Qwen 3.8 Flash Next auf Strix-Halo-Rechnern ausführen](https://kofler.info/qwen-38-flash-next-strix-halo/)（Michael Kofler，2026-10-09） | ★ **独立同机 halogen 对照**：HumanEval+ 40 题 · Gufo **52.2** vs Halogen **61.6** tok/s · 安装/参数/终端观感 |
| 11 | [gufo #474「where the decode gap is」](https://github.com/gufo-org/gufo/issues/474)（2026-10-07） | ★ **社区调优与根因**：46.5→54.5 · replay 46.5–48.2 vs halogen ~60 · **每步 57.5 ms vs 42 ms**（非 draft 接受率）· 冷 prefill 1,540 vs 1,800 |
| 12 | [gufo #809「comparable community results」](https://github.com/gufo-org/gufo/issues/809)（OPEN，2026-10-26） | ★ **社区数字不可互比**（机器/功耗档/OS 未记录）· Windows 64 GB 对照表 |

---

## 8. 变更日志

| 日期 | 版本 | 内容 |
|---|---|---|
| 2026-10-31 | v1.0 | 首次落档：名称澄清（Kyojin ≠ Gufo）· 两引擎现状 · 与本集群三轴对照 · 三条硬门 · 优势劣势 · 三条动作建议 · 9 项未实测 |
| 2026-10-31 | **v1.1** | **补 §1.1a 社区复现核查**：官方 BENCHMARKS 双档（mixed **35.79** / repetitive **116.93**，README 脚注 *"Peaks include repetitive output"*）· 四个独立测量（llmkube 33.5 / Kofler 52.2 vs halogen 61.6 / #474 46.5→54.5 / Habr ~40）· 判定 = 能复现 mixed、不能复现头条 · Gufo decode 一致 **0.85× halogen**，根因是每步成本 · 版本间 ±6–18% 波动（#475/#598/#632/#684/#863）· #809 社区不可比 · §4.1 劣势 5 / §5.2 / §6 #5 同步修正 |
