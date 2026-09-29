# 分布式推理路线可行性调研：CIRU StrixLink / Skulk（含 vLLM 多机 TP 与 AMD 官方路线）

> **日期**: 2026-09-16（**v3 增补 2026-09-17**：新增 **§9「ROCm 6.x vs 7.x on gfx1151 专项调研」** —— 回答"B/C 是否该与 A 站同步装 ROCm 6.4.1 / ROCm 7.x 是否在本显卡退化"；同时补齐 §8 的 ROCm 一手来源。v2，同日修订：用户给出 `jcbtc/GLM5.3-Flash-CIRU-STRIX-IU4` 出处后**重新取证并推翻 v1 的"未证实"结论**；**v4 增补 2026-09-29**：新增 **§10「USB4 模拟 RDMA 专项核验（`thunderbolt-ibverbs` / Soft-RoCE）」** —— 回答"社区那条把 USB4 当 RDMA 用的路子本机群能不能做"，并**收窄 §5.1 的"必须 100GbE"前提**为"真正卡的是**每对 rail 数 + 内核 NHI 直通**"；**v5 增补 2026-09-29**：新增 **§11「CIRU 是否比现役 llama.cpp RPC 更快」** —— 结论 = **GLM 那约 2× 的差距主因是「投机解码」而非互联**（`23.69` 与 `11.94` **不同口径，不可相减**）；**DeepSeek 无现成 CIRU 包**，但 vLLM 官方 recipe 同样开投机解码；**同日二次更正（v5 内）**：§11 的归因由"几乎全是投机解码"更正为「**①串行跨链 + ②TP 语义 + ③投机解码**」**三条轴叠乘**（见 **§11.7**），并更正 §10.5 的"换 40G 线"为**可靠性项（非性能项）**；**同日三轮追加**：新增 **§11.8「①轴当前能不能解」** —— 税 = **次数 × RTT** ⇒ **RTT 那半今天可解（A3a，零成本）**、**次数那半只能绕**（`#26610` **对 GLM 无效** / vLLM TP=2 **现在就能试**），触发条件见 TRACKER §W-6）
> **触发**: 用户提出"当前分布式 llama 对 V4-Flash / GLM-5.3-Flash 支持力度不够"，要求评估 ① **CIRU StrixLink 部署 GLM-5.3-Flash** 与 ② **引入 Skulk 框架** 的可行性。
> **证据等级**: **E1**=本轮实测/`fetch` 原页核实；**E3**=外部文档；**E4**=未确认（明确标注，不采信）
> **核查纪律**: 先确认**通道可达**再判定"有无"（v1 的教训见 §3）

---

## 0. 结论先行（v2）

| 路线 | 可行性判定 | 一句话理由 |
|---|---|---|
| **① CIRU StrixLink + GLM-5.3-Flash（`jcbtc/GLM5.3-Flash-CIRU-STRIX-IU4`）** | 🟢 **E1 已取证：这是"现成的双机 320B 部署包"，与本集群硬件同构度极高** | README 首句即"**320 billion parameters. Two Strix Halo PCs. Entirely local inference.**"——权重**已按 `rank-0`/`rank-1` 两机切好**（每机 ~**83.25 GiB**）、**vLLM/ROCm 10 定制运行时**、**gfx1151 专用内核**、`INSTALL-RUNTIME.sh` 自包含、**实测 decode 23.69 t/s / 402.5 prompt t/s**；**但它是 TP=2 双机方案 ⇒ 不能单机跑**，且要引入 **ROCm 10 + Python 3.14** 新栈 |
| **② "StrixLink"** | ✅ **E1 已定位：它不是独立框架**，而是该部署包的组成部分 —— 官方 tag `ciru-strixlink` + `tools/ciru-strixlink-0.3.x-linux-amd64.tar.gz`，作用是"**配置/检查/准备两机连接**" | 关键：**前端（generation frontend, :8083）不依赖 CiruStrixLink 应用** ⇒ 我们可以**只用"两 rank + 前端"**，把 StrixLink 当诊断/连接工具，不必引入其常驻服务 |
| **③ Skulk** | 🟠 可评估，但**不解决同一问题** | 官方原页确认 **AMD Linux = `skulk-llama-server-vulkan`**（我们在支持范围内）、引擎可注入；但**后端就是 llama.cpp** ⇒ 不改"上游未合 glm5next"的事实；且其**常驻 supervised service** 与"零自加载/看门狗禁用/唯一管理面"冲突 |
| **④ vLLM 多机 TP（Ray + 定制 RCCL + RoCE v2）** | 🔴 能力最通用，但**需 100GbE RDMA 硬件** | 合并显存 ~248GB、RDMA 5µs 级延迟；**我们只有 USB4**。**注**：CIRU 路线在某种意义上已用 USB4 + 自有 all-reduce 实现了 TP=2（见 §2），故本条的"必须 100GbE"前提**对 CIRU 不适用** |
| **⑤ 现状路线（llama.cpp RPC）+ 等上游** | ✅ 已跑通，**有 AMD 官方背书** | 官方 playbook《Clustering Two Ryzen AI Halos with RPC》= llama.cpp RPC + ROCm 跑 GLM-4.7 358B；但我们**只有 9/8 前构建的引擎**，glm5next 未合 |
| **⑥ USB4 模拟 RDMA（`thunderbolt-ibverbs` / Soft-RoCE）** —— **v4 新增** | 🔴 **不建议做**（项目**真实**、同款硬件跑通过；但对本机群**收益≈0**且与硬约束冲突） | 需 **mainline ≥7.1 + 内核补丁**（本集群 **pin 6.17**）· 作者自述 **"Soft DMA"**、**内核频繁锁死**、**非生产可用**；本栈（llama.cpp RPC）**不消费 IB verbs**，瓶颈已实测是**内存带宽**；本环**每对仅 1 根线** ⇒ **拿不到其头条数字**（那是双线聚合）。详见 **§10** |

**一句话（v2）**：用户诊断的"支持力度不够"**有一条现成解** —— **CIRU StrixLink 双机方案**（GLM-5.3-Flash 320B、UMA 分片权重、USB4 上自有 all-reduce、实测可用吞吐）；代价是**引入 ROCm 10/vLLM 新栈 + 需两机同时在场 + 治理接入**。Skulk 补的是编排，**不改上游事实**。

> ★ **v5 增补（2026-09-29）**：用户追问"CIRU 能否比现役 llama RPC 更快跑 GLM / DeepSeek"⇒ **见 §11**。
> 一句话：**CIRU 对 GLM 确实约 2× 快，但那 2× 的来源是「投机解码」而不是互联或引擎**；
> 且 **DeepSeek 没有现成的 CIRU 包**（vLLM 侧同样开投机解码，但要自建栈）。**建议先做零新栈的同口径对照再决定。**

---

## 1. 现状瓶颈（为什么"支持力度不够"）

引用 [upstream-tracker §1.4](../../spec/upstream-tracker/TRACKER.md) 的实测结论：

1. **GLM-5.3-Flash 尚未进 llama.cpp 主线**（glm5next 三线 Open；#27754 虽转 `mergeable_state=unstable` 仍未合）⇒ 只要引擎是 llama.cpp，就装不了它。
2. **GLM-5.3 的 RPC 有已知未确认问题**（#28360，报告者第二台为 **GFX1151 同架构**）。
3. **V4-Flash 的 `-sm tensor` 主体已合并（#26490，8/24）**，但 **RPC 形态待 #26610** ⇒ 现在只能用 `-sm layer`。
4. 物理链路：三机 **USB4 直连 ~9.4 Gbps** —— 对层分布够用；**但 CIRU 的实测证明 USB4 上做 TP=2 是可行的**（用 USB4 硬件环 + DMA-BUF 自有 all-reduce，见 §2），**前提是内核支持 NHI/USB4STREAM**。

> **推论**：提升"支持力度"的路只有三条：**(a) 等上游**；**(b) 换引擎**（CIRU=vLLM/ROCm 属此类）；**(c) 换通用多机 TP 栈**（vLLM+Ray+RCCL+RoCE，需 100GbE）。**CIRU 同时占了 (b) 且顺带给出 (c) 的 USB4 变体。**

---

## 2. CIRU StrixLink —— `jcbtc/GLM5.3-Flash-CIRU-STRIX-IU4`（E1 已取证）

### 2.1 仓库事实（`hf-mirror.com` 原页，2026-09-16 实取）

| 项 | 值 |
|---|---|
| 仓库 | `jcbtc/GLM5.3-Flash-CIRU-STRIX-IU4`（**HF**；likes **6**、downloads 0、`lastModified` **2026-09-08**、sha `93782912…`） |
| 体量 | **103 文件 / 166.72 GiB** |
| tags | `vllm` · `glm5_next` · `mixture-of-experts` · `rocm` · `amd` · `strix-halo` · `speculative-decoding` · `dflash2` · `custom-code` · **`ciru-strixlink`** |
| base_model | **`zai-org/GLM-5.3-Flash`** + **`wtdcode/GLM-5.3-Flash-AWQ-W4A16`** |
| license | `mixed-mit-apache-2.0`（有 `THIRD_PARTY_NOTICES.md` / `LICENSE_SCOPE.md` / `PUBLIC_RELEASE_CHECKLIST.md`） |
| 权重布局 | **`rank-0/` 与 `rank-1/` 各 11 片 safetensors**（各 ~7.65 GiB×10 + 7.312 + 7.044 ≈ **83.4 GiB/机**）⇒ **已按两机切好** |
| 运行时 | `runtime/packages/`：`vllm-0.1.0rc2.dev9+g9255fd9fb9.rocm100-cp314-cp314-linux_x86_64.whl`、`amd_aiter-0.1.0rc1` wheel、两个源码 tarball（vllm / aiter-gfx1151） |
| 内核 | `runtime/gfx1151/*.so`（`iu4-m1` / `dense-kda` / `m4-residual` / `resident-g128` / `top8-epilogue` / `m8-align`）+ `packages/aiter-jit-gfx1151/module_aiter_core.so` ⇒ **编译好的 gfx1151 专用内核** |
| 工具 | **`tools/ciru-strixlink-0.2.0 / 0.3.0 / 0.3.1 / 0.3.2 / 0.3.3 -linux-amd64.tar.gz`** |
| 其它 | `config/tokenizer.json`、`assets/*.png`、`benchmarks/`、`docs/`、`runtime/generation-frontend/` |

### 2.2 架构（README / `runtime/packages/README.md` 原文要点）

- **两机两路张量并行（TP=2）**，两机都参与推理；**应用只看到单一端点**。
- **通信两条路**：
  - **Direct USB4 → NHI（Native Host Interface）**：把专用非缓存 HIP 分配导出为 **DMA-BUF 池**，经 **USB4 硬件环**交换，校验序号/epoch footer，在 GPU 上累加 BF16 分片。**实测 `[8,4096]`/64-KiB all-reduce 组件门中位 109.897–110.807 µs，对照 RCCL socket 340.904–342.745 µs（低 67.5–67.9%，bit-exact）**，每 rank 80 次交换无超时。
  - 其它通信走**配置好的网络集合（RCCL/socket）**。
- **生成必须经前端**：`runtime/generation-frontend/`（**FastAPI/Uvicorn，默认 `:8083`**，Apache-2.0）把**同一请求提交给两个 rank-local 的 `:8100` API**，返回 rank 0、drain rank 1。**前端可跑在任一节点，且不依赖 CiruStrixLink 应用。**
- **CiruStrixLink 的职责**：帮助**配置/检查/准备**那条连接；可选 Launch 页可选 context profile、加载两个 rank、显示 host 级统一内存用量、报告 **Fast mode 是否真的就绪/在用**、卸载成对 rank。

### 2.3 量化与质量（原文实测，WikiText 767 个匹配位置、全 154,880 词表打分）

| 指标 | 官方 BF16 | CIRU STRIX IU4 |
|---|---:|---:|
| Perplexity | 2.1486 | **2.2612**（+**5.24%**） |
| Top-token 一致率 | — | **91.92%** |
| BF16 top 落在量化 top-5 / top-10 | — | **99.35%** / **99.48%** |
| 正向 KL（均值 / 中位 / P95） | — | 0.0943 / 0.0122 / 0.5059 nats |

- 权重：路由专家 **对称 4-bit + 每 128 组共享 scale**，敏感组件保高精度 ⇒ **平均 ~4.46 bits/param**（非严格 4-bit）。
- 作者自己限定："这是**量化检查**，不是完整 WikiText 评测、不是能力评分、不是与其他量化的排名"。

### 2.4 性能（原文实测，64K profile + NHI + DFlash2 k7 + prefix caching + 2,304 batch）

- **402.455 prompt tokens/s**、**TTFT 5.089 s**、**decode 23.686 t/s**（不含 prefill）、**draft acceptance 56.593%**（2,048 prompt × 128 output）
- DFlash2 = 一次提 5 个 draft token 交目标模型一起验；batch budget 2,304 为默认（8,192 / 20,480 均未改善或未能启动）
- context profile：**1 = 64K/6 GiB KV**（低内存回退）、**2 = 128K/12 GiB KV（默认，131,200 tokens）**、**3 = 256K/8 GiB**（实验）；三者 host staging 均 8 GiB
- `VLLM_NHI_TIMEOUT_MS` 默认 30 s（避免 rank 首次 JIT 触发 1 s 对端超时）

### 2.5 硬件与软件要求（**决定可行性的核心**）

| 项 | 要求 | 与本集群对照 |
|---|---|---|
| 机器 | **两台 Strix Halo，各 128 GiB 统一内存**，经 **USB4** 连接；GPU `gfx1151` | ✅ **完全同构**（A/B/C 均 gfx1151 + 128GB + USB4 三角直连） |
| 软件栈 | **ROCm 10.0.0** + 自带 vLLM 运行时；PyTorch **2.13.0+rocm10.0.0**；**Python 3.14.3**；AITER `ec6b1a5d…`；**TileLang 0.1.10 + Apache TVM FFI 0.1.10（必需）** | ⚠️ **2026-09-17 订正**（原文"A/B 现为纯 Vulkan 路线（无 ROCm）、C 站为 ROCm 7.2.1"**有误**）：本集群**已是双后端并存** —— **默认单站加载（`infer-load` 缺省 `unsloth`）就是 HIP/ROCm，三站同构**（studio 自带引擎 b10715，`ROCm0`）；**只有分布式/RPC 路径是 Vulkan**（`/opt/llama.cpp`）。**系统 ROCm 仅 A 站有 6.4.1**（B/C 无系统 ROCm，HIP 面靠 studio 自带 bundled 运行时）⇒ 与 CIRU 要求的 **ROCm 10.0.0** 属**版本代差**，不是"从零引入"；但 **Python 3.14.3 + TileLang 0.1.10 是净新增**（详见 [TRACKER §2.6](../../spec/upstream-tracker/TRACKER.md)） |
| 内核 | **Direct-NHI 需 USB4STREAM/NHI 支持的内核**（实测用 **NixOS + Linux 7.2.2**）；**"通用 USB4 内核不足以提供 direct-NHI 路径"** | ⚠️ 我们 Ubuntu 内核为 6.x ⇒ **大概率拿不到 110 µs 直连**，退回 **RCCL/socket 网络集合（≈341 µs）**；性能红利需打折 |
| wheel 平台 | 构建于 **Ubuntu 24.04（glibc 2.39 / GCC 13）**，tag `cp314-cp314-linux_x86_64`，**非 manylinux**、无 host 特定 RPATH ⇒ "**Ubuntu 24.04+ 或等价兼容**" | ✅ 若站上为 Ubuntu 24.04+ 则**在目标范围内**（这半解了"非 NixOS 未测试"的顾虑）；NixOS 另提供 module |
| 磁盘 | 每机 **~83.25 GiB 权重** + draft + runtime + 缓存（"substantial additional storage for disk caching"）；建议本地 NVMe | ⚠️ **需核三站 NVMe 余量**（今天刚做过 C→A 202 GB 传输） |
| 内存 | 128K 默认档：**12 GiB GPU KV + 8 GiB host staging /机**；与其它应用共享同一物理内存 | ⚠️ 与现有模型驻留互斥，需走 `load-gate` |

### 2.6 与既有约束的冲突与化解

| 约束 | 冲突 | 化解（初步） |
|---|---|---|
| **ADR-0004 唯一管理面** | 新增两 rank 的 `:8100` API + `:8083` 前端（+可选 CiruStrixLink Launch 页面） | 把"两 rank + 前端"当作**一个新的引擎面**纳入统一入口（类比 `infer-load` 的既有一致性范式）；**前端不依赖 CiruStrixLink** 这点使耦合可控 |
| **零自加载纪律** | 它自带服务安装程序（`INSTALL-RUNTIME.sh` 落 `/srv/llm/...`） | **不走它的开机自启**：由我们的入口按需拉起/停止（**比 Skulk 的常驻 supervisor 好处理**） |
| **C 站看门狗禁用 / load-gate** | 12 GiB KV + 8 GiB staging 需并入内存预算 | 纳入 `load-gate` 的占用登记 |
| **现役后端口径**（见 [TRACKER §2.6](../../spec/upstream-tracker/TRACKER.md)） | CIRU 需 ROCm 10 + Python 3.14；本集群分布式面是 Vulkan、单站面**已是 HIP/ROCm** | **仅在参与该模式的机器上引入**（建议先 A+B 或 B+C 两台，第三台不动）；★ **HIP 面三站已存在**（studio 自带 bundled 运行时）⇒ 属"**版本代差升级 / 与之并存**"而非"首次引入" |

---

## 3. "StrixLink" 的确切身份 + **v1 误判的复盘**

### 3.1 身份（E1）

**StrixLink 不是独立框架**，而是 CIRU 部署包的组成部分：

- HF tags 明列 **`ciru-strixlink`**；
- 包内 `tools/ciru-strixlink-0.2.0 … 0.3.3-linux-amd64.tar.gz`（5 个版本，最新 **0.3.3**）；
- 职责（README 原文）："**CiruStrixLink helps configure, inspect, and prepare that connection**"——即**两机 USB4/NHI 连接的配置与诊断工具**（含 Launch 页：选 context profile、加载两 rank、显示 host 统一内存、报告 **Fast mode** 是否真就绪、卸载成对 rank）；
- 外部还有 GitHub 组织 **`github.com/ciru-ai/CiruStrixLink`**（README 引用其 `docs/performance.md`），包内另有 `docs/STRIXLINK-TRANSPORT.md`。

**⇒ 结论修正**：用户所说"CIRU StrixLink"= **CIRU 的 Strix Halo 双机互联/部署方案**，与"GLM-5.3-Flash 双机部署包"是同一件事的两面。

### 3.2 v1 为什么判成"未确认"（方法论复盘，必须记下）

- v1 依据"，三轮定向检索 + HF API **全未命中**"得出"未确认"，并写明"不臆测"。
- **真实原因**：**主控与 B 站直连 `huggingface.co` 均超时（`WinError 10060` / `http=000`）** —— 即 **HF 在本地网络不可达**；而我的检索通道与 `WebFetch` 同样取不到该页 ⇒ **"取不到"被误读为"不存在"**。
- **修正后的可用通道（重要运维事实）**：**站上 `hf-mirror.com` 可达（HTTP 200）**；本次全部取证均经此通道完成（`curl hf-mirror.com/api/models/...` + `/resolve/main/...`）。
- **教训（已回写记忆）**：**判"不存在"之前，必须先证明"通道可达"**（对 HF 这类分区可达站点尤其如此）；等价于本仓既有的"判据必须能自证"纪律在**取证通道**上的推广。

---

## 4. Skulk（多机 AI 计算互联 fabric）—— E1 已确认

| 项 | 内容 |
|---|---|
| 定位 | "interconnect fabric for multi-node AI compute"：多机组成集群、跨机搬工作量；对外**一个 OpenAI 兼容端点**（`/v1/chat/completions`） |
| 三平面 | compute（跨机交换激活值）/ control（集群决策、任务生命周期、节点健康）/ data（结果回流） |
| 引擎与后端 | **AMD Linux：`skulk-llama-server-vulkan` wheel**（NVIDIA 先 CUDA、失败回退 Vulkan）；macOS 走 in-process MLX；**vLLM 仅 `--with-vllm` 且仅 NVIDIA Linux**；可 `SKULK_LLAMA_SERVER_BIN` 注入自有 llama-server、`SKULK_NO_ENGINE_AUTOPROVISION=1` 关自动供给 |
| 形态 | macOS 15+/Ubuntu-Debian 包；dashboard `:52415`；**master 选举 + 自愈 + 崩溃重启 + 重平衡**；Tailscale 远程；tracing/flight recorder |

**判断**：✅ AMD+Vulkan 在官方支持路径内；✅ 引擎可注入（理论上可喂自编译 glm5next llama-server）；❌ **不改上游事实**；⚠️ **常驻 supervised service** 与零自加载/load-gate/看门狗禁用/唯一管理面冲突 ⇒ **引入前先裁决"谁管生命周期"**。

**与 CIRU 路线的对比（这是 v2 新增的关键判断）**：

| 维度 | CIRU StrixLink | Skulk |
|---|---|---|
| 后端 | **vLLM / ROCm 10**（**绕开 glm5next 上游依赖**） | **llama.cpp / Vulkan**（仍受上游约束） |
| 模型支持现状 | **已给出可跑的 GLM-5.3-Flash 320B 双机包**（E1） | 取决于 llama.cpp 是否合 glm5next（今日仍未合） |
| 多机机制 | TP=2 + USB4 NHI/DMA-BUF 自有 all-reduce（实测 110 µs） | 自有 fabric + 流水式放置 |
| 生命周期 | **前端不需常驻**（可不装其服务） | **常驻 supervisor**（与我们的纪律冲突更大） |
| 适配工作量 | 需 ROCm 10 栈（两机，**版本代差升级**）+ 磁盘/内核条件；Python 3.14/TileLang 净新增 | 需解决治理归属 + 仍需自编译引擎 |

> ⚠️ **口径注（2026-09-17）**：上表 Skulk 列的"llama.cpp / Vulkan"指的是**我们现役的分布式/RPC 路径**（`/opt/llama.cpp`，master + worker 均 Vulkan）；**默认单站加载走的是 HIP/ROCm**（三站同构）—— 完整后端矩阵见 [TRACKER §2.6](../../spec/upstream-tracker/TRACKER.md)。

⇒ **对"GLM-5.3-Flash 分布式"这一具体目标，CIRU 路线的性价比高于 Skulk。**

---

## 5. 另外两条（v1 保留，结论微调）

### 5.1 vLLM 多机 TP（Ray + 定制 RCCL + RoCE v2）

来源：[kyuz0/amd-strix-halo-vllm-toolboxes](https://github.com/kyuz0/amd-strix-halo-vllm-toolboxes)（含 `rdma_cluster/setup_guide.md`，Fedora 43 实测）：**vLLM（TP=2）+ Ray + 定制 gfx1151 RCCL + RoCE v2**，需 **2×100GbE RDMA NIC（Intel E810-CQDA1）+ DAC**、BIOS/内核参数一整套；收益：合并显存 **~248GB**、跨机延迟 **70-100 µs → ~5 µs**。
**v2 微调**：CIRU 证明**在 USB4 上也能做 TP=2**（NHI 硬件环 + DMA-BUF，110 µs 组件门）⇒ "TP 必须 100GbE"**不是普适律**，而是"通用 RCCL/TCP 路径下的现实"；若走 CIRU 那套自有 all-reduce，则 100GbE 非必需（但需 NHI 内核）。

**v4 微调（2026-09-29）**：本条"需 100GbE"的**真正硬约束不是"专用网卡"，而是 ① 每对链路数（rail 数）② 内核是否有 NHI/USB4STREAM 直通** —— 见 §10.3/§10.6。★ 且**"装上 ibverbs" ≠ "提速"**：同款 Strix Halo 上 **Soft-RoCE（同一套 verbs 接口、零内核改动）实测 4.3 Gb/s < TCP 8.85 Gb/s**（E3）⇒ **接口兼容与性能等价是两件事**。

### 5.2 AMD 官方 playbook（我们已在走的路线）

[developer.amd.com/playbooks/clustering-rpc-server](https://developer.amd.com/playbooks/clustering-rpc-server/) = **llama.cpp RPC + ROCm 两机跑 GLM-4.7 358B**（`amd-ttm --set 120` 调 UMA、BIOS 0.5G 起步）⇒ 现路线有官方背书，**瓶颈在上游 PR 与物理链路，不在路线选择**。

---

## 6. 建议（v2，按性价比）

| 序 | 动作 | 成本 | 收益 | 前置 |
|---|---|---|---|---|
| **1** | **等 + 盯 #26610 / #27754**（§1.4 已建预警触发） | 0 | 一次性解锁 RPC `-sm tensor` 与 glm5next | 无 |
| **2** | **CIRU StrixLink 双机部署评估（A+B 或 B+C）** —— 拉取 2×83.25 GiB（**经 hf-mirror**）、铺 ROCm 10 + Python 3.14 栈、跑 `INSTALL-RUNTIME.sh`、以 `:8083` 前端接入统一入口 | 中高（两机新栈 + 磁盘 + 治理接入） | **当场得到可用的 320B GLM-5.3-Flash**（实测 decode 23.69 t/s），**且完全绕开上游 PR 等待** | ① 三站 NVMe 余量核对；② 内核是否有 USB4STREAM/NHI（否则接受 RCCL 路径性能）；③ ADR-0004 立项 |
| **3** | **内核/NHI 前置勘查**（与 2 并行）：确认我们内核能否支持 NHI 直连；不行则评估换 NixOS/新内核的代价 | 小（勘查）→ 大（换内核） | 决定是否能拿到 110 µs 直连（即 67% 的 all-reduce 延迟红利） | 无 |
| **4** | **Skulk 治理评估**（先答"谁管生命周期"） | 小（决策）→ 中（试点） | 多机 fabric/自愈/统一端点；可注入自有引擎 | ADR-0004 裁决 |
| **5** | **100GbE RDMA 硬件评估** | 大（硬件） | 通用 TP 栈（Ray+RCCL+RoCE）的必备条件 | 预算决策 |
| — | **StrixLink** | — | — | ✅ **已取证闭环**（见 §2/§3），不再是待办 |

> **另有一条与本表正交的决策**：「**B/C 是否该与 A 站同步安装系统 ROCm 6.4.1**」（动因：用户观察到 **ROCm 7.x 在本显卡疑似性能退化**）——**证据面见 §9**。一句话：**现役推理已全在 ROCm 7.x（7.13/7.14/7.16），系统 ROCm 是零推理依赖 ⇒ 装它不改变推理版本**；7.2.1 的官方性能条目**不能外推到 7.13+**；**不建议装 7.x**（与 bundled `libamdhip64.so.7` 同名遮蔽面）。

---

## 7. 待验证清单（v2）

1. **三站 NVMe 余量** vs 每机 ~83.25 GiB 权重 + draft + runtime + 缓存（C→A 刚传 202 GB）。
2. **内核 NHI/USB4STREAM 支持**：现内核是否有 `usb4`/NHI 直通路径？（决定 110 µs 直连能否用；不能用则接受 RCCL ≈341 µs）
3. **ROCm 10 与现役 ROCm 面的共存/升级**路径：**A 站系统 ROCm 6.4.1** + **三站 studio 自带 bundled 运行时**（**B/C 无系统 ROCm** —— 2026-09-17 订正，原文"C 站 ROCm 7.2.1"已不存在）⇒ 需先定"装系统 ROCm 10"还是"vLLM 侧自带 ROCm 10、与现役 HIP 面隔离"（见 [TRACKER §2.6](../../spec/upstream-tracker/TRACKER.md)）。**⚠ 该问题的证据面已于 2026-09-17 查清，落档在 §9**：现役推理**全部在 ROCm 7.x**（7.13/7.14/7.16）、**系统 ROCm 是零推理依赖**；故"CIRU 要求 ROCm 10"属**版本代差**而非"从零引入"；且**装 6.x 与 bundled 的 `libamdhip64.so.7` soname 天然错开、装 7.x 则同名**（§9.3）。
4. **Python 3.14 环境**（wheel 是 `cp314`）与现有栈隔离（venv/uv）。
5. **治理接入方案**：`两个 :8100 rank + :8083 前端` 如何并入唯一管理面、如何纳入 `load-gate` 内存预算、如何保持零自加载。
6. **NHI 不可用时的性能实测**：走 RCCL/socket 时 TP=2 在 USB4 9.4 Gbps 上的真实 decode 吞吐（对照作者 NHI 下的 23.69 t/s）。
7. `ciru-ai/CiruStrixLink` GitHub 仓库的版本/变更节奏（判断是否值得跟）。
8. 权重完整性校验：166.72 GiB / 103 文件的逐文件哈希（对照 HF 侧 sha 或 LFS 指针）。

> **v4 追加（2026-09-29，见 §10）**
> 9. **USB4 模拟 RDMA 的收益是否为正**：先在 B/C 两台做**零内核改动**的 Soft-RoCE 对照（`rdma link add rxe0 type rxe netdev thunderbolt0`），量 `ib_send_bw` vs `iperf3`；**预期负收益**（同硬件公开实测 4.3 < 8.85 Gb/s）。
> 10. **`thunderbolt-ibverbs` 的内核前提**：要 **mainline ≥7.1 + LKML 稳定性补丁**；本集群 **pin 6.17**（A `6.17.0-40` / B=C `6.17.0-23`，2026-09-29 实测）且**禁升 7.x**（ROCm 面）⇒ **未评估**"补丁回移 + 模块对 6.17 NHI 内部结构的适配"。
> 11. **IOMMU 面**：**C 站实测 `iommu=off`** ⇒ 任何 DMA-capable 对端都**无 DMA 保护**；该路径属 **DMA 级**能力 ⇒ 若将来要碰，**必须先解决 IOMMU**。

> **v5 追加（2026-09-29，见 §11）**
> 12. **"投机解码值多少"的同口径差值**（§11.5-4，§11.8）：在**现役 llama.cpp 路径**上量 spec-on / spec-off ⇒ 决定 CIRU 那 2× 里多少是"引擎"、多少是"那颗头"。★ 且须验"**RPC 上投机解码是否被串行税倒挂**"（§3.2 的赌博判据）。
> 13. **我方 V4-Flash GGUF 的 MTP 是否可用于投机解码**（§11.4）：头部含 `mtp`/`draft`/`eagle` 字样（E1）**不等于** llama.cpp 能用 ⇒ 须核 `llama.cpp` 对 `deepseek4` 的投机解码支持面（含 `-md` draft 路径）。

> **v6 追加（2026-09-29 第二轮，见 §11.7）**
> 14. **`#26610` 升级对照**（§11.5-3，§11.8-①B）：llama.cpp RPC 协议异步化的 before/after（社区同构预期 **+32% tg**）；本仓 A6 锚点已建。**零新栈、直击第①-B 轴**（但 **GLM 上无收益**）。
> 15. **GLM / 三机的"串行跨链往返数"**（§11.7-未实测）：本仓 **38.7 次往返/token 是 M2.7 双机**的数 ⇒ GLM（glm5next、三机）的往返数**未测**。

> **v7 追加（2026-09-29 第三轮，见 §11.8）**
> 16. **A3a 的实际增益未测** —— 本仓判"收益传导最确定"，但**没有数**；套件是**逐项对照增量应用** ⇒ before/after 可直接落 metrics-log。
> 17. **A4 的决策门未试**：**单流 tg ≥ 24 t/s 且 16k 上下文无崩溃** —— 两条均未跑。

---

## 8. 来源

**一手（本轮实取）**
- **HF 仓库原页（经 hf-mirror）**：`jcbtc/GLM5.3-Flash-CIRU-STRIX-IU4` —— `api/models/...`（元数据/tags/sha）+ `tree/main?recursive=true`（**103 文件 / 166.72 GiB / rank-0|rank-1 分片**）+ `raw/main/README.md`（320B/两机/SW 要求）+ `raw/main/runtime/packages/README.md`（版本矩阵、`INSTALL-RUNTIME.sh`、前端 `:8083`、实测性能、NixOS module）
- [Skulk 官方文档（Introduction）](https://foxlight-foundation.github.io/Skulk/)｜[Source Builds And Runtime Paths](https://foxlight-foundation.github.io/Skulk/build-and-runtime)
- [kyuz0/amd-strix-halo-vllm-toolboxes](https://github.com/kyuz0/amd-strix-halo-vllm-toolboxes)｜[Getting Started（单机 vs RDMA）](https://deepwiki.com/kyuz0/amd-strix-halo-vllm-toolboxes/2-getting-started)
- [AMD 官方 playbook: Clustering Two Ryzen AI Halos with RPC](https://developer.amd.com/playbooks/clustering-rpc-server/)
- [strix-halo-llm-perf（USB4 ~9.4 Gbps 实测）](http://raw.githubusercontent.com/visorcraft/strix-halo-llm-perf/main/README.md)

**一手（§9 ROCm 专项，2026-09-17 抓取）**
- ROCm Ryzen 已知问题页：[7.2.1](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/limitations/limitationsryz.html)（**明列** Ryzen AI MAX+ 395 部分 LLM 负载性能低于预期）｜[6.4.4](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-6.4.4/docs/limitations/limitationsryz.html)（**无此条**）
- [ROCm#6146](https://github.com/ROCm/ROCm/issues/6146)（gfx1151 + 7.2.1 的 `hipMemcpy` GPU page fault）｜[ROCm#6182](https://github.com/ROCm/ROCm/issues/6182)（特定主板全版本不可恢复 HSA fault ⇒ 板级）
- [linux-firmware：revert GC 11.5.0 的 0x83 MES SCH 固件](https://gitlab.com/kernel-firmware/linux-firmware/-/commit/3d5c8135206cef364e7d353711b3e7358a90d152)（"causes problems with ROCm on GC 11.5.0"）
- 兼容矩阵：[通用 6.4.1](https://rocm.docs.amd.com/en/docs-6.4.1/compatibility/compatibility-matrix.html)（**无 gfx1151**）｜[Radeon/Ryzen APU 6.4.4](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-6.4.4/docs/compatibility/compatibilityryz/native_linux/native_linux_compatibility.html)（**gfx1151 首次出现**）｜[7.14 通用矩阵](https://rocm.docs.amd.com/en/docs-7.14.0/compatibility/compatibility-matrix.html)
- 安装：[amdgpu-install 用法（usecase 语义：内核模式驱动包含在所有 usecase）](https://rocm.docs.amd.com/projects/install-on-linux/en/docs-6.1.0/how-to/amdgpu-install.html)｜[ROCm on Ryzen 官方安装（要求 `--no-dkms`）](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.1/docs/install/installryz/native_linux/install-ryzen.html)｜[post-install（写 `rocm.conf` + `ldconfig`）](https://rocm.docs.amd.com/projects/install-on-linux/en/docs-7.0.0/install/post-install.html)｜[多版本共存安装](https://rocmdocs.amd.com/projects/install-on-linux/en/latest/install/install-methods/multi-version-install-index.html)
- [AMD Strix Halo 系统优化文档（7.2.0）](https://rocm.docs.amd.com/en/docs-7.2.0/how-to/system-optimization/strixhalo.html)｜[7.0.2 release notes（hipBLAS/RCCL 的 gfx1151 支持）](https://rocm.docs.amd.com/en/docs-7.0.2/about/release-notes.html)｜[AMD 6.4.4 release notes（Strix Halo = Developer Preview）](https://www.amd.com/en/resources/support-articles/release-notes/RN-AMDGPU-LINUX-ROCM-6-4-4.html)
- Fedora 打包（**soname 证据**）：[rocm-hip @ fedora-43（6.4.2 → `libamdhip64.so.6`）](https://packages.fedoraproject.org/pkgs/rocclr/rocm-hip/fedora-43.html)｜[fedora-rawhide（7.14 → `.so.7`）](https://packages.fedoraproject.org/pkgs/rocclr/rocm-hip/fedora-rawhide.html)

**一手（§10 USB4-RDMA 专项，2026-09-29 抓取）**
- [IV. thunderbolt-ibverbs（hellas.ai 工程博客）](https://blog.hellas.ai/blog/thunderbolt-ibverbs/4-thunderbolt-ibverbs/)（内核补丁 / 带宽逐层拆解 / **`Soft DMA` 自述**）｜[Bonus Round I: AD/FA57（Apple 的 RDMA-over-Thunderbolt 对照）](https://blog.hellas.ai/blog/thunderbolt-ibverbs/6-ad-fa57/)
- [Apple TN3205: Low-latency communication with RDMA over Thunderbolt](https://developer.apple.com/documentation/technotes/tn3205-low-latency-communication-with-rdma-over-thunderbolt)（Apple 官方；TB5 起 + 需 IOMMU 保护）
- [Level1Techs：Ryzen AI Halo — USB4 Clustering with RDMA 实测](https://forum.level1techs.com/t/ryzen-ai-halo-usb4-clustering-with-rdma-testing-notes/253117/1)（**同款 Strix Halo**：TCP 8.85–9.42 Gb/s vs **Soft-RoCE 4.3 Gb/s**）
- [Linux 内核文档：USB4 和 Thunderbolt](https://linuxkernel.org.cn/doc/html/latest/admin-guide/thunderbolt.html)（**security 级别语义**：`user` ⇒ 软件连接管理器**不建 PCIe 隧道**）

**二手（仅作旁证）**
- [CIRU 运行时发行说明索引页（Ling-3.0-Flash-CIRU-int4-Strix-native）](https://www.toolify.ai/ai-model/jcbtc-ling-3-0-flash-ciru-int4-strix-native)
- [kyuz0/amd-strix-halo-toolboxes](https://github.com/kyuz0/amd-strix-halo-toolboxes)（把 `rocm-6.4.4` 标 Stable、`rocm-7-nightlies` 标 Experimental）｜[其 toolbox 说明](https://deepwiki.com/kyuz0/amd-strix-halo-toolboxes/3.1-rocm-toolboxes)
- [lemonade-server：gfx1151 Linux 踩坑（`amdgpu-dkms` 破坏 ROCm）](https://lemonade-server.ai/gfx1151_linux.html)
- [NGA 帖（同机 6.4.4 vs 7.0.2 的 pp 数字）](https://bbs.nga.cn/read.php?tid=45354933)（**二手，未经复验**）

**本仓**
- [upstream-tracker §1.4/§1.5](../../spec/upstream-tracker/TRACKER.md)｜[ADR-0004](../../adr/ADR-0004-统一管理入口为唯一管理面.md)
- ★ **§11 的关键前置（第二轮才发现本仓已有）**：[双机剩余优化空间评估.md](../双机剩余优化空间评估.md)（2026-08-28）—— 已把 RPC 根因量化为**串行跨链税（38.7 次往返/token）**、列出两条攻击路径（**换并行策略 / `#26610`**）、并实测**换线性能 ≈0（利用率 0.02%）**；同文引 Geerling 4×M3 Ultra 的同硬件对照（llama.cpp RPC 负加速 vs TP+RDMA 正加速）｜[ADR-0010](../../adr/ADR-0010-DwarfStar第二引擎引入立项.md)（ds4 = **覆盖面 + 容量**，非吞吐引擎）

---

## 9. 附：ROCm 6.x vs 7.x on gfx1151 专项调研（2026-09-17）

> **为什么单列**：在"B/C 能否与 A 站同步安装 ROCm 6.4.1"的决策中，用户提出「**rocm7.x 在本显卡上似乎有性能退化**」。本节把该直觉的证据面查清，并回答"装系统 ROCm 能否改善推理"。
> **本集群的版本实测矩阵**（精确到 soname）见 [TRACKER §2.6](../../spec/upstream-tracker/TRACKER.md)。

### 9.1 结论先行

1. **装系统 ROCm 不改变推理用的 ROCm 版本。** 三站实测：**没有任何现役推理路径跑在 6.x 上** —— 默认单站加载 = studio 自带 **7.16.26332**、studio python 栈 = **7.13.0**、C 站 HIP 单机线 = **7.14.60850**；而 A 站系统 **6.4.1** 是**零推理依赖**（仅作 `hipcc` 构建工具链 + `rocminfo` 诊断，引用反查 = 0、ldd 依赖 = 0）。⇒ **给 B/C 装 6.4.1 对推理性能没有直接作用。**
2. **"7.x 在本显卡性能退化"的直觉有官方佐证，但只覆盖 7.2.1，不能外推到现役的 7.13–7.16。** 官方 Ryzen 已知问题页明列「在 AMD Ryzen AI MAX+ 395 上运行部分 LLM 负载（如 Llama 3 1B/3B）**出现低于预期的性能**」（**7.2.1 有、6.4.4 无**）——这是目前**唯一**由 AMD 文档化的"7.x 于 Strix Halo 性能不达预期"条目，且**未给量化数字**。
3. **不装，"失去的"只是 HIP 构建/诊断能力**（现状**不需要**：三站 HIP 推理全部走自带运行时且已实测达标）。**若确需**：只在 **B 站**（UPGRADE_SOP 的唯一构建源）装 **6.4.4**（官方 gfx1151 支持起点，**不是 6.4.1**）且**必须 `--no-dkms`**；**不要装 7.x**（理由见 §9.3）。
4. **真正能回答该问题的是受控对照实验**，不是版本号推断（设计见 §9.5）。

### 9.2 证据面（已证实 / 未证实 分开列，不外推）

**已证实（一手为主）**

| # | 事实 | 出处 |
|---|---|---|
| A | ROCm **7.2.1** 的 Ryzen 已知问题列「395 上部分 LLM 负载性能低于预期」；**6.4.4 同页无此条** | [7.2.1](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/limitations/limitationsryz.html) / [6.4.4](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-6.4.4/docs/limitations/limitationsryz.html) |
| B | gfx1151 + **7.2.1** 下 `hipMemcpy` 触发 GPU page fault，**连官方 HIP sample 都失败**；`hipMalloc/hipFree` 正常 | [ROCm#6146](https://github.com/ROCm/ROCm/issues/6146) |
| C | 特定主板（Bosgame M5 / Sixunited AXB35-02）上**所有** ROCm 版本均不可恢复 HSA fault ⇒ **板级而非芯片级** | [ROCm#6182](https://github.com/ROCm/ROCm/issues/6182) |
| D | linux-firmware **revert 了 GC 11.5.0 的 0x83 MES SCH 固件**，理由写明 "causes problems with ROCm on GC 11.5.0" | [commit](https://gitlab.com/kernel-firmware/linux-firmware/-/commit/3d5c8135206cef364e7d353711b3e7358a90d152) |
| E | gfx1151 **首次出现在 Radeon/Ryzen APU 兼容矩阵是 6.4.4**；更早的通用矩阵（含 **6.4.1**）**没有 gfx1151** | [6.4.1 矩阵](https://rocm.docs.amd.com/en/docs-6.4.1/compatibility/compatibility-matrix.html) / [6.4.4 APU 矩阵](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-6.4.4/docs/compatibility/compatibilityryz/native_linux/native_linux_compatibility.html) |
| F | `amdgpu-install` 的**内核模式驱动包含在所有 usecase 中**；Ryzen 官方指引**明确要求 `--no-dkms`** | [amdgpu-install](https://rocm.docs.amd.com/projects/install-on-linux/en/docs-6.1.0/how-to/amdgpu-install.html) / [ROCm on Ryzen](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.1/docs/install/installryz/native_linux/install-ryzen.html) |
| G | `amdgpu-dkms` 会与 in-tree `amdgpu` 冲突并**破坏 Strix Halo 上的 ROCm GPU 访问** | [lemonade-server](https://lemonade-server.ai/gfx1151_linux.html)（社区，但与"三站 DKMS 目录为空"的现状互证） |
| H | 官方 post-install 会写 `/etc/ld.so.conf.d/rocm.conf` + `ldconfig`，并建议导出 `LD_LIBRARY_PATH` | [post-install](https://rocm.docs.amd.com/projects/install-on-linux/en/docs-7.0.0/install/post-install.html) |
| I | **soname**：6.4.x 的 HIP = `libamdhip64.so.6`；7.x = `.so.7` | [fedora-43](https://packages.fedoraproject.org/pkgs/rocclr/rocm-hip/fedora-43.html) / [fedora-rawhide](https://packages.fedoraproject.org/pkgs/rocclr/rocm-hip/fedora-rawhide.html) |
| J | 官方多版本共存做法 = 带版本 meta 包 + apt pin + `update-alternatives`/modules + `LD_LIBRARY_PATH`；**单版本与多版本包不可混装** | [多版本安装](https://rocmdocs.amd.com/projects/install-on-linux/en/latest/install/install-methods/multi-version-install-index.html) |
| K | 官方对 6.4.4 的 Strix Halo 口径是 **Developer Preview**（"稳定性与性能尚未优化"）⇒ **官方从未称 6.4.x 为稳定档** | [AMD 6.4.4 release notes](https://www.amd.com/en/resources/support-articles/release-notes/RN-AMDGPU-LINUX-ROCM-6-4-4.html) |
| L | **7.0.0/7.0.1 对 gfx1151 覆盖不全**：7.0.2 release notes 才记 hipBLAS 3.0.2「新增 gfx1150/1151 支持」、RCCL 2.26.6「启用 gfx1150/1151」 | [7.0.2 release notes](https://rocm.docs.amd.com/en/docs-7.0.2/about/release-notes.html) |

**未证实 / 未找到可靠证据（明确标注）**

| # | 说法 | 状态 |
|---|---|---|
| M | 「7.0/7.1 相对 6.4 有 GEMM/attention 吞吐**量化下降**」 | ❌ **未找到可靠证据**（无权威基准） |
| N | 同机、同 llama.cpp 版本下的 **6.4.x vs 7.x 严格对照** | ❌ **未找到**；现有二手数字显示**两者相当、7.x prefill 略优** |
| O | 「skinny-GEMM Wave32 病态分发导致退化」 | ⚠️ 仅见第三方模型聚合页（非官方、且非版本回归；官方文档反而建议保持该开关开启） |
| P | 「7.2.2 能识别 GPU 但无法编译 shader」 | ⚠️ 仅二手转述 |
| Q | **7.13 / 7.14 / 7.16（我们的现役版本）** 是否命中 7.2.1 那条性能问题 | ❌ **无从判定**（未找到 7.13+ 的对应条目）—— **这正是"不能外推"的原因** |

### 9.3 安装风险评估（若决定装）

| 风险 | 事实 | 对本集群的含义 |
|---|---|---|
| **`amdgpu-dkms`（最高）** | 官方 Ryzen 指引要求 `--no-dkms`；dkms 与 in-tree 冲突会破坏 ROCm（G） | 三站现状**正确**（`amdgpu` in-tree、`/lib/modules/*/updates/dkms/` 空）⇒ **必须保持** |
| **soname 遮蔽（选 6.x 而非 7.x 的最硬理由）** | 6.4.x = `so.6`，7.x = `so.7`（I）；而 **studio bundled 恰是 `so.7`** | 装 6.x ⇒ 与 bundled **天然错开**（A 站即活样本：系统 so.6 + bundled 7.16 共存，HIP 推理实测正常）；装 7.x ⇒ **同名遮蔽面** |
| ld 污染 | 官方 post-install 写 `rocm.conf` + 建议 `LD_LIBRARY_PATH`（H） | A 站现状仅 `10-rocm-opencl.conf`、`LD_LIBRARY_PATH` 空 ⇒ 隔离**干净**；给 B/C 装应**照 A 站口径**（不写全局 rocm.conf、不导 `LD_LIBRARY_PATH`） |
| 内核/固件变量 | 社区普遍认为 Strix Halo 的 KFD 队列创建/CWSR 修复要 6.18.4+；linux-firmware revert 过 GC 11.5.0 MES 固件（D） | **第三个变量**，且**本集群已漂移**：A `6.17.0-40` vs B/C `6.17.0-23`（[TRACKER §2.7](../../spec/upstream-tracker/TRACKER.md)） |
| 工具版本漂移 | `amdgpu-install`：A `6.4.60401` / B `6.3.60303` / **C `30.30.1.0.30300100`** | C 那把是 **ROCm 7.x 时代**遗留 ⇒ 在 C 装必须**显式 pin 版本**，否则默认装到 7.x |

### 9.4 本集群现状对照（决定"装不装"的基线）

| 位置 | ROCm | 在推理路径上？ |
|---|---|---|
| studio 自带引擎运行时（`~/.unsloth/llama.cpp/build/bin/`） | **7.16.26332** | ✅ **默认单站加载（现役主路径）** |
| studio python 栈（`rocm_sdk_core` / torch / triton） | **7.13.0** | studio |
| ~~C 站 `~/Applications/llama-gfx1151`~~ | ~~7.14.60850~~ | **已于 2026-09-17 移除**（唯一活引用 = C 站 flash-next env 的 pin；`libllama qwen4exp=0` 本就不支持 flash-next ⇒ 删除无损）。备份 `tar.gz` 466MB/388 条目保留于 `/home/scott-lau/backups/`。C 站单机线统一回 studio HIP（见 [TRACKER §2.8](../../spec/upstream-tracker/TRACKER.md)） |
| A 站系统 `/opt/rocm-6.4.1` | **6.4.1** | ❌ **零推理依赖** |

⇒ **本集群"已经全是 7.x"**；"装 6.4.1"不会让任何推理路径变回 6.x。

### 9.5 真正该做的：6.x-vs-7.x 受控对照实验（**未执行**，仅设计）

- **锁死变量**：同模型（gpt-oss-120b MXFP4）、同参、同 ctx、同 KV 量化、**同内核**、同 UMA carveout
- **⚠ 关键陷阱**：studio 是 `0.3.0-dev b10715`。若拿"自建 master b1533 + 6.4.4"去比"studio b10715 + 7.16"，**引擎版本与 ROCm 版本混在一起，结论不成立**。干净设计 = **在 B 站用同一 llama.cpp commit 分别编译 ROCm 6.4.4 与 7.x 两个产物**（两组对照，代价 = 多一次构建）
- **观测**：prefill t/s、decode t/s、加载耗时、首次 fault、**≥1000 token 长跑稳定性**
- **判据前置**：先定"差多少算退化"（建议 **≥5%**）
- **前置条件**：B 站装 ROCm 6.4.4（`--no-dkms`，照 A 站隔离口径）；实验前把三站内核锁到同一版本

### 9.6 建议（按性价比）

| 序 | 动作 | 建议 | 理由 |
|---|---|---|---|
| 1 | **B/C 同步装 6.4.1** | ❌ **不建议** | 对推理性能无作用（§9.1-1）；且 6.4.1 **不在官方 gfx1151 支持列表**（E） |
| 2 | **三站都不动** | ✅ **默认建议** | 现状可用且已达标；零风险 |
| 3 | **只在 B 站装 6.4.4（`--no-dkms`）** | ✅ **仅当决定做 §9.5 或需要本地 HIP 构建能力时** | 与 UPGRADE_SOP「B 站单点构建、产物分发」一致；6.4.4 是官方 gfx1151 起点；`so.6` 与 bundled 错开 |
| 4 | **装 ROCm 7.x** | ❌ **不建议** | soname 与 bundled 同名遮蔽面（§9.3）+ 7.2.1 有官方性能条目与 `hipMemcpy` 回归，而**装它并不改变现役推理行为**，纯增污染面 |
| 5 | **用容器隔离而非宿主安装** | 🔵 备选 | 官方/社区事实标准（kyuz0 toolbox 同时提供 6.4.4 与 7-nightlies）；与"唯一管理面 + 零自加载"纪律的兼容性需另行评估 |

> **本文档 9.x 的状态标记**：`✅ 已证实` / `❌ 未找到证据` / `⚠️ 仅二手` / `🔵 备选方案` / **未执行**（§9.5 只是设计）。凡本节未标注为"已证实"的，**引用前必须自查**。

### 9.7 三站统一装系统 ROCm：遮蔽判据探测（2026-09-17，零风险，未装任何东西）

**背景**：用户开放三选一「三站统一安装系统 ROCm / 移除 B 站 ROCm / 维持现状」，倾向**统一安装**，要求先做版本选型与装前零风险遮蔽判据。目的地重新定位为「补齐 B/C 本地 HIP 构建能力 + 消 `amdgpu-install` 三站漂移」（§9 已登记：A `6.4.60401` / B `6.3.60303` / C `30.30.1.0` 7.x 时代）。

**① 系统 ROCm 现状取证（本轮实测，覆盖 §9.4 表）**：
- **A 站**：有系统 ROCm `6.4.1`（`/opt/rocm` → `/opt/rocm-6.4.1`，SONAME `so.6`，完整 dev 栈 rocm-dev/hip-dev/rocblas/miopen/rccl…）；`libamdhip64.so.6`。
- **B/C 站**：无系统 ROCm（`/opt/rocm` 不存在、dpkg 零 rocm/hip 包）。
- **三站 bundled 推理运行时**：`~/.unsloth/llama.cpp/build/bin/` 自带 HIP `7.16.26332`（`libamdhip64.so.7`），**三站同构、均靠 RPATH=`$ORIGIN` 自洽**。
- **A 站系统 ROCm 进程级引用审计（判据先行，非臆测）**：全 `/proc/<pid>/maps` 扫 `/opt/rocm` = **零命中**；现役推理进程（llama-server/vllm/unsloth）当前 A 站未跑；`infer-load`/systemd/`/etc` 反查仅注释文本提及 rocm，**无任何运行时依赖** ⇒ **A 站 6.4.1 是可安全移除的闲置系统 ROCm，但对「统一安装」方向无冲突（装 7.14 后可与 6.4.1 并存）**。

**② 官方版本矩阵（2026-09-17 fetch 原页，覆盖 §9.1）**：
- **ROCm 7.14.0（2026-07-16）**：兼容矩阵**正式列出 gfx1151 = Ryzen AI Max+ 395（Radeon 8060S）、RDNA 3.5、Ubuntu 24.04.4 (HWE kernel 6.17)** ✅；TheRock 模块化架构（`rocm-hip-sdk` 可择装），release 重点 AI inference + vLLM 0.23 + ROCprofiler-SDK。
- **ROCm 6.4.4（Ryzen APU Linux）**：gfx1151 为「**初始支持 / Preview**」，PyTorch 仅 `2.8 + 3.12` 一档，Ubuntu 24.04.3 初步支持 ⇒ **官方定位为试水，非生产级**。
- **选型结论**：统一目标 = **7.14.0**（非 6.4.4）。理由：① gfx1151 正式支持 vs Preview；② TheRock 模块化 footprint 可控；③ bundled 已是 `so.7` 同代，装 7.14 不引入 SONAME 代差。

**③ 遮蔽判据探测（本轮实测，三站一致）**：
- bundled `llama-server` `RUNPATH = [$ORIGIN]`（readelf -d 三站同值）。
- `ldd` 对其运行时依赖 `libamdhip64.so.7` / `libggml-hip.so.0` / `libhipblas.so.3` 全命中 bundled `$ORIGIN` 同目录。
- **结论：`$ORIGIN` 解析先于 `ldconfig` 缓存 ⇒ 即便未来装 7.14 把 `so.7` 注册进 `ldconfig`，bundled 推理仍绝对优先，无遮蔽、无抢占。** A 站现有 `so.6` 与 bundled `so.7` 不同 SONAME，天然不冲突。
- **判定：装 7.14.0 对现役推理路径零风险。**

**遗留（未执行，待裁决后进入设计）**：三站统一装 7.14.0 的完整执行设计（装 `rocm-hip-sdk` 模块 + `--no-dkms` + `amdgpu-install` 三站版本 pin + 备份/回滚 + 装后遮蔽自证判据）。当前仅完成零风险判据探测与取证。

### 9.7-纠偏 版本号更正（2026-09-17，同一会话追加）

> **§9.7 上文「统一目标 7.14.0」需更正为 7.2.4**。理由（判据先行，非臆测）：

- `curl https://repo.radeon.com/rocm/apt/` **实测无 `7.14.0` 目录**；6.x/7.x 现最高 = **7.2.4**，`latest/dists/noble/Release` 亦为 **7.2.4** ⇒ **apt 仓库可安装的最新版本 = 7.2.4**。
- §9.7 上文引的「7.14.0 兼容矩阵列 gfx1151」是**官方产品/release 版本号**，与 **apt 仓库版本段**是两套不同命名（官方 docs-7.14.0 vs repos `rocm/apt/7.2.x`）。**官方 docs-7.2 native_linux 矩阵（本轮单独 fetch）正式列 gfx1151**（Ryzen AI Max+ 395/Radeon 8060S/RDNA 3.5/U24.04）⇒ 7.2 本身即官方正式支持，无需追高到不存在的 7.14。
- **前置探测实测（2026-09-17）**：A 实装 rocm-core `6.4.1`（`so.6`）；B/C 无系统 ROCm；三站 source 段 A `6.4.1`/B `6.3.3`/C `7.2.1`（C 需 pin 到 7.2.4）；网络可达 `repo.radeon.com` 200。
- **统一目标定案 = 7.2.4**（`rocm-hip-sdk` + `--no-dkms` + `--rocmrelease 7.2.4`）。遮蔽判据（§9.7-③，`$ORIGIN` 优先）与版本号无关，**不因本次更正而失效**。
- **方法论沉淀**：安装目标的**版本号必须以 apt 仓库真实存在为准，官方产品号 ≠ apt 版本段**；起设计前应 `curl` 仓库根目录清单确认该版本目录存在，避免 pin 到不存在的版本导致安装失败。
- 完整执行设计已落 `spec/rocm-migration/DESIGN.md`（含 8 项验收清单）；TRACKER 变更日志 v2.1。**下一步**：3.0 前置 `apt-cache policy rocm-core` 确认真实候选，待裁决进入实际安装。

---

## 10. 附：USB4 模拟 RDMA 专项核验（2026-09-29）

> **触发**：用户提供一段二手描述 —— "Strix Halo 上用 `thunderbolt-ibverbs` 把 USB4 端口变成 InfiniBand 设备，vLLM/RCCL/NCCL 无需修改即可识别使用"，要求"分析本机群是否可实现"。
> **证据等级**：**E1** = 本机群实测（本轮）；**E3** = 外部原文（工程博客 / 官方文档 / 第三方实测）；★ **二手转述一律降级并逐条核对**（见 §10.2）。

### 10.1 结论：🔴 不建议做

项目**真实存在**（`hellas-ai/thunderbolt-ibverbs`，作者用的就是**同款 Strix Halo**），但本机群是「**高成本（内核级）+ 收益≈0 + 与硬约束冲突**」。

| 维度 | 判定 | 依据 |
|---|---|---|
| 能否跑通 | ◐ **理论上能试，但在本集群须先补两项未评估前提** | 项目要 **mainline ≥7.1 + LKML 稳定性补丁**；本集群 **pin 6.17**（A `6.17.0-40` / B=C `6.17.0-23`，§10.3）且**禁升 7.x**（ROCm 面）⇒ §7-10 |
| 对本集群收益 | ❌ **≈0** | ① 本栈是 **llama.cpp RPC（Vulkan）**，**不消费 IB verbs**；② 瓶颈**已实测是内存带宽**；③ 本环**每对仅 1 根线** ⇒ 拿不到其头条数字。见 §10.4 |
| 与硬约束 | ❌ **冲突** | 内核 pin（禁升 7.x）· **C 站 `iommu=off`**（无 DMA 保护）· USB4 同时是**数据面兼 ssh 兜底通道**（内核锁死会一起断） |
| 项目成熟度 | ❌ **不可用于生产** | 作者自述 *"research code, **not production-ready**; stability and support are **not guaranteed**"*，博客记录**内核频繁锁死**（锁死后需**物理**输入口令恢复） |

### 10.2 ★ 三处二手转述更正（本节的直接产出）

| 转述说法 | 核对结果（E3 原文） |
|---|---|
| "直接操作 NHI DMA 环，**把 USB4 的 PCIe 隧道能力转化为 RDMA 语义**" | ❌ **机制描述不成立**。作者原话：*"our implementation is **'Soft DMA'** — even if we're woken on interrupts and only **copy DMA descriptors with the CPU**, it's orders of magnitude higher latency than an ASIC could achieve"*。走的是 **NHI 环**（即 USB4NET/tbnet 那条 DMA 路径），**不是 PCIe 隧道**；且 host↔host 之间**没有 PCIe 设备可枚举**，本集群 `security=user`（§10.3）下软件连接管理器**默认就不建 PCIe 隧道** ⇒ "PCIe 隧道"在本场景本来就无关 |
| "**成熟的**社区方案验证了可行性" | ❌ **"成熟"不成立**：项目自陈研究代码、稳定性不保证，博客自述内核锁死频繁 |
| "vLLM/RCCL/NCCL **无需任何修改**即可使用" | ◐ **只有接口面成立**（会注册 `usb4_rdma*`、`ibv_devices` 可见）。它**不解决** RCCL 在 gfx1151 上的支持问题（本仓 [提速调研报告](../提速调研报告.md) 已记 vLLM ❌）；★ 且 **"装上 verbs" ≠ "提速"** —— 同款 Strix Halo 上 **Soft-RoCE**（**同一套 verbs 接口、零内核改动**）实测 **4.3 Gb/s < TCP 8.85 Gb/s** |

### 10.3 本机群实测约束（E1，2026-09-29）

| 项 | 实测值 | 对该路径的意义 |
|---|---|---|
| 内核 | A `6.17.0-40` · B/C `6.17.0-23` | 项目要 **≥7.1 mainline**；本集群**内核锁定**，且 ROCm 7.2.4 就验在这套 6.17 上 |
| USB4 链路 | **Gen2 20Gbps**（`iperf3` `8.8–9.2 Gb/s`，[net.yaml §segments](../../inventory/net.yaml)） | 与第三方同硬件实测（TCP `8.85–9.42`）一致；★ 该项目头条 **`48 Gb/s` 是"同一对机器两根线聚合"** ⇒ 本三角环**每对 1 根线**，**结构上拿不到** |
| `security` 级别 | 三站均 **`user`** | 软件连接管理器 ⇒ **PCIe 隧道默认禁**（故"PCIe 隧道→RDMA"在本场景无关） |
| IOMMU | **C 站 `iommu=off`**（A/B cmdline 无显式项） | 该路径是 **DMA 级**能力 ⇒ 无 IOMMU 时对端可**不受保护**地访问本机内存（作者本人亦点出 *"unfettered access"*） |
| 拓扑 | 三角环、三段各 1 根线（各站 2 个 TB 口已用满） | 无法多 rail 聚合；单 rail 上限即现状 |
| 退路 | 站间 ssh **兜底走 USB4**（见 [ADR-0006](../../adr/ADR-0006-控制面传输绑定LAN_IPv4.md) 的 `known_hosts` 一节） | 该路径若锁死内核 ⇒ **数据面与退路同时断** ⇒ 实验必须**人在机前** |

### 10.4 就算装上，为什么收益≈0（三条量化理由）

1. **本栈不消费 IB verbs**：分布式路径是 **llama.cpp RPC**（自有协议，不看 `ibverbs`）。要用上必须换引擎栈（vLLM/RCCL）—— 那是 **ADR 级**决策，不是网络层改造。
2. **瓶颈已实测是内存带宽**：加节点 **decode 反降**（双机 `11.94` → 三机 `11.22`，§7.2）；`-ub` 调参**只动 prefill、decode 纹丝不动**（§7.3）。跨机链路即使压到 7 µs 延迟，能挤的也只是那点**流水线开销** ⇒ **上限个位数百分比**。
3. **成本侧不对称**：代价 = 往 ROCm-validated 的 6.17 上塞 **out-of-tree 内核模块 + 内核补丁**，换回个位数百分比。

### 10.5 真要做，次序（按性价比）

| 序 | 动作 | 成本/风险 | 说明 |
|---|---|---|---|
| **1** | **别动网络层** | 0 | 先证伪"瓶颈在互联"这一前提 —— **本仓已有答案：是内存带宽** |
| **2** | ~~换 ≤0.8m USB-IF 认证线升 Gen3 40Gbps~~ ⇒ ★ **不是性能项**（2026-09-29 更正） | 低（线材） | ❌ **原写"可升档"易被读成绩效杠杆，已更正**：本仓 A2 实测**利用率 0.02%、20G→40G 无感** ⇒ 它的真实价值是**可靠性**（消除 retimer found/disconnected 振荡），**不是性能** |
| **3** | **先试 Soft-RoCE（零内核改动）** | 低 | `rdma link add rxe0 type rxe netdev thunderbolt0` ⇒ 量 `ib_send_bw` vs `iperf3`；**预期负收益**（同硬件 4.3 < 8.85）—— 用它**证伪/证实**"verbs 值不值" |
| **4** | **若仍要碰 `thunderbolt-ibverbs`** | **高** | 只在 **B+C 两台**做**一次性隔离实验**（`ib_send_bw` 即收）；**绝不上控制面**、不动 `/opt/llama.cpp` 与实例 conf、**先解决 IOMMU**、**人在机前** |

### 10.6 与本文既有结论的关系

- **§5.1「vLLM 多机 TP 需 100GbE」的硬约束被收窄**：真正卡的不是"专用网卡"，而是 ① **每对 rail 数**、② **内核是否有 NHI/USB4STREAM 直通**（后者即 §2.2 的 CIRU 直连路径前提）。
- **§7 待验证清单**新增第 **9–11** 条（1 项可零成本验证 + 2 项未评估前提）。
- **本节不改** §6 建议表的排序 —— 它**仍未进入**"值得投预算"的那一档。
- **未实测登记**：本节全部为"**读原文 + 本机群静态实测**"，**未在本机群跑过** `thunderbolt-ibverbs` / `rxe` / `ib_send_bw`；"收益≈0"的判定依据是**本仓既有实测**（内存带宽墙 + 本栈不消费 verbs）+ 拓扑结构，**不是**本路径的实际基准。

---

## 11. 附：CIRU 是否比现役 llama.cpp RPC 更快（2026-09-29）

> **触发**：用户提问 —— "既然 DwarfStar（ds4）框架实测无太多收益，**CIRU StrixLink 是否比现役 llama RPC 更快跑 GLM / DeepSeek 系列**？"
> **证据等级**：**E1** = 本仓实测；**E3** = 外部原文。★ 本节的核心纪律见 **§11.3：不同口径的数不得直接相减**。

### 11.1 先纠前提：ds4 的失望**不能**外推到 CIRU

| | ds4（DwarfStar） | CIRU StrixLink |
|---|---|---|
| 它是什么 | llama.cpp 之外的**第三实现**（ROCm 为其短板） | **vLLM + ROCm 10 + AITER gfx1151 定制内核** |
| 裁决（[ADR-0010](../../adr/ADR-0010-DwarfStar第二引擎引入立项.md)） | 角色 = **架构覆盖面 + 容量**，**不是吞吐引擎** | 尚未立项 |
| 实测 | V4-Flash 单机 ds4 **12.5** < llama Vulkan **18.33**；双机 16.8 ≈ llama RPC 17 | GLM-5.3-Flash 双机 decode **23.69**（作者实测，E3，§2.4） |

⇒ ds4 的"收益少"是**定位如此**（它从来不是吞吐路径）；而 CIRU 恰是**把"vLLM 在 gfx1151 上不支持"这件事做通**的那套东西（本仓 [提速调研报告](../提速调研报告.md) 记 vLLM ❌）⇒ **两者不同类，不可互推**。

### 11.2 GLM-5.3-Flash：约 2× 的差距，来源是**投机解码**而非互联

| | 现役 llama.cpp RPC（E1 本仓） | CIRU（E3 作者） |
|---|---|---|
| decode · 双机 | **11.94 t/s**（§7.1） | — |
| decode · 三机 | **11.22**（§7.2）· 统一入口 **11.39–11.45**（§7.5） | — |
| decode · CIRU 双机 TP=2 | — | **23.69 t/s**（prompt 402.5 / TTFT 5.089 s，§2.4） |
| **投机解码** | ❌ **结构上不可得** —— GLM 的 **GGUF 转换丢弃 MTP 头**（见 [GLM 文档 §0「主要限制」](./2026-09-28_GLM系列本地推理部署.md)） | ✅ **DFlash2 k7**，draft acceptance **56.6%**（§2.4） |

**倍率估算（★ 估算，非实测）**：α = 0.566、k = 7 ⇒ 每次前向期望接受 token ≈ Σ_{i=0..7} α^i ≈ **2.3**
⇒ `11.94 × 2.3 ≈ 27`，与 CIRU 的 `23.69` **同量级**（差额 ≈ 流水线 + 引擎开销）。
⇒ ~~**那 2× 几乎全部由「有没有投机解码」解释**~~ ★★ **第一轮此句属过度归因，第二轮已更正** —— 正确写法见 **§11.7**：
2× 至少由 **①串行跨链税 + ②TP 语义 + ③投机解码** 三条轴**叠乘**，而上面这条估算**只解释了③那一段**。
（它**仍成立**的部分：③ 确实是其中一段；且这 2× **不是** NHI 互联红利 —— 本集群**拿不到** NHI，见 §2.5。）

### 11.3 ★★ 口径纪律：`23.69` 与 `11.94` **不可直接相减**

一个是**带**投机解码（DFlash2 k7 + prefix caching + 2,304 batch），一个是**不带**。
把它读成"引擎快 2×"，是一句**"听起来完全合理、但前提是假的"** ⇒ 与本仓 **"报数必须带射程"** 同一条纪律。
**要对比，必须把投机解码这两侧拉平**（同开或同关）。

★★ **第二轮追加（同日）**：不止"**不同口径不可相减**"，还有 **"不同轴不可合并归因"** ——
把 ①串行跨链 + ②TP 语义 + ③投机解码 的**和**当成**单项**（读成"引擎更快"）来读，是同一类错误的**第二个变体**。见 **§11.7**。

### 11.4 DeepSeek V4-Flash：**无现成 CIRU 包**，但"投机解码"在 vLLM 侧同样是**官方一等公民**

- **包面（E3 检索）**：找到的 CIRU 包是 **GLM-5.3-Flash**（另有 Ling）；**未发现** Strix Halo 上的 CIRU DeepSeek 包（DeepSeek 的双机 vLLM 案例均为 **NVIDIA DGX Spark / Ascend**）⇒ "用 CIRU 跑 DeepSeek" = **自建 vLLM + AITER 栈**，不是拉包。
- ★ **机制面（关键）**：vLLM 官方 recipe 对 V4-Flash **直接给了投机解码** —— `--speculative-config '{"method":"dspark","num_speculative_tokens":7,…}'`（**0731 自带 DSpark** draft；preview 版为 **MTP**）⇒ **7 个 draft token**，与 CIRU 的 GLM 形态一致。
- 而**我们的 `14.06 t/s`**（[V4 文档](./2026-09-28_DeepSeek-V4系列调研与部署.md) 的 decode 史）**是不带投机解码的** ⇒ **同样是约 2× 量级的缺口，同源**。
- ⚠ **但兑现难度高于 GLM**：① 无现成包，须自建；② 我方 MXFP4 GGUF **头部 120 MB 内含 `mtp`×5 / `draft`×7 / `eagle`×2 字样**（E1 本仓扫描）—— 但 **"GGUF 里有 MTP 权重" ≠ "llama.cpp 能拿它做投机解码"** ⇒ **未证**（见 §7-13）；③ spec decode 的甜区是**小 batch / 短序列**，高并发长上下文会收窄。

### 11.5 建议（按性价比）

| 序 | 动作 | 成本 | 说明 |
|---|---|---|---|
| **1** | ★★ **A3a USB4 低延迟 sysctl 套件**（§11.8-①A） | **零成本** | **三轮更正后的首选**：直击**税基（RTT）**；本仓判"**收益传导最确定**"、原列建议序**第 1 位** ⇒ **今天就能做** |
| **2** | **vLLM TP=2 平行部署**（本仓 A4 已判"现在就能试"） | 中 | **同时拿第①-B + ②轴**；同款 M2.7 AWQ INT4 社区 **18.5–24.8** vs 现 20；**不动 llama.cpp 服务**；**决策门 tg ≥ 24 且 16k 无崩溃** |
| **3** | **等/推 `#26610`**（RPC 协议异步化 + tensor split 的 RPC 形态） | **0（升级窗口）** | 直击**次数**；同构社区 **+32% tg**；★ 但 **GLM 上无收益**（架构正交，§11.8-①B） |
| **4** | 量"投机解码值多少"（同口径 spec-on / spec-off） | **0** | 只解决**第③轴**，且 ★ **依赖②**（§11.8）：RPC 上属"**未验证的赌博**" |
| **5** | **把 CIRU 定位为「GLM-5.3-Flash 的现成解」** | — | 即 §0 的 🟢；**不是**"替换 llama RPC 的通用后端" —— 其**不可替代点收窄为：GLM 的 MTP 投机解码 + 现成打包 + 已测质量报告**（§11.7） |
| **6** | ★★ **在 1–3 之前不投 CIRU** | — | 否则会重现 ds4 的形态（见下） |

★ **两次教训同型（本节最该记住的一句）**：
- **ds4**：以为买的是**吞吐**，实测买到的其实是**容量 / 覆盖面**；
- **CIRU**：以为买的是**引擎 / 互联**，第二轮**拆轴**后实为 **①串行跨链 + ②TP 语义 + ③投机解码** 叠乘（其中 **① 本仓已有 0 成本路径**，见 §11.7）。
⇒ 一句话：**"收益不在你以为的那一层"** —— 与本仓 §10.2 的"二手转述必须逐条核对"是同一族纪律。

### 11.6 未实测登记（不静默）

1. **§11.2 的 2.3× 是估算** —— 由作者公开的 acceptance（56.6%）与 k=7 **反推**，**非本机实测**；估算式假设各 draft 独立同分布，实际可能偏低或偏高。
2. **`mtp` 字样 ≠ 可用于投机解码**：我方 V4-Flash GGUF 头部含 `mtp`/`draft`/`eagle` 字样是 **E1 事实**，但**能否被 llama.cpp 用于投机解码未证**（本次未解析到可下结论的深度）。
3. **CIRU 的 23.69 未复现** —— 其条件（64K profile / NHI / DFlash2 k7 / prefix caching / 2,304 batch）与本集群现役口径不同 ⇒ **本节不把它当作本集群可达值**。
4. **未评估**：自建通用 vLLM + AITER 在 gfx1151 上复刻同等投机解码收益的可行性与代价（§11.5-2）。

### 11.7 ★★ 归因更正（2026-09-29 第二轮）：**7 条轴 + 2×2**

> **为什么补这一节**：§11.2 第一轮把约 2× 的差距**几乎全部归给投机解码** ⇒ **过度归因**。
> 本轮查到本仓**早已**有一份正面打这个问题的分析（[双机剩余优化空间评估.md](../双机剩余优化空间评估.md)，2026-08-28）——
> 它已把 RPC 根因量化为**串行跨链税**，并明确指出**"投机解码与换线恰恰不是预期收益最高的两项"**。
> **原文一字未删**，本节做**更正 + 补全**（本文既有留痕纪律）。

**7 条轴（每条附证据与量级）**

| # | 轴 | llama.cpp RPC（现役） | CIRU / vLLM | 量级与证据 |
|---|---|---|---|---|
| **①** | **串行跨链税（根因）** | `-sm layer` ⇒ **每 token 串行跨机**：本仓实测 **38.7 次往返/token** | TP=2 ⇒ 每层两机**同时**算 | **大**。旁证：**三机 11.22 < 双机 11.94**（加机只增跳数）；Geerling 4×M3 Ultra **同硬件同线**：llama.cpp RPC **负加速** 20.4→15.2 |
| **②** | **并行语义** | layer = 买到"**装得下**" | **tensor** = 买到"**算得快**" | **大**；`-sm tensor` 主体已随 **v0.3.0（8/25）** 发布，但 **RPC 形态待 `#26610`** |
| **③** | **投机解码** | ❌ GLM **结构不可得**（GGUF 丢 MTP 头） | ✅ DFlash2 k7，accept **56.6%** | **大**（估算 ≈2.3×），但在 ①② **之上叠乘** |
| ④ | 互联 | tbnet TCP（9 Gb/s，RTT ~0.15 ms） | NHI 110 µs（**拿不到**：需 7.2 内核） | **小** —— 其价值主要体现在**①的 RTT 税里**，不是独立一项 |
| ⑤ | 引擎内核 | llama.cpp Vulkan（glm5next 分支） | vLLM + **AITER / TileLang gfx1151 定制内核** | **未量化**（唯一"引擎本身"的候选差） |
| ⑥ | 精度/权重体积 | UD-IQ4_XS，**146.1 GiB** | IU4 ≈4.46 bpw，**166.7 GiB** | **反向**：CIRU 权重更大 ⇒ 纯带宽地板更高 ⇒ 2× **不可能**来自"引擎更省带宽" |
| ⑦ | 调度 | 单序列 + `-ub` 调参 | continuous batching + prefix caching | 对**单序列 decode 小**，对**并发吞吐大** |

**★ 2×2：单点对单点归不了因**

| | 投机解码 off | 投机解码 on |
|---|---|---|
| **layer 切分** | ← **本集群在这里**（11.22–11.94） | |
| **TP=2** | | ← **CIRU 在这里**（23.69） |

⇒ 两个单点差的是 **①+②+③ 的和**；**一个数拆不开三项**。

**★ 三条轴各自怎么拿（本节最有用的一节）**

| 轴 | 怎么拿 | 成本 | 依据 |
|---|---|---|---|
| **① 串行跨链（最大的一半）** | ★ **拆两半**（§11.8）：**税基**用 **A3a**（今天可做）· **次数**用 `#26610` 或 vLLM TP | A3a **0** / `#26610` **0（等）** | 同构社区 **+32% tg**；本仓 A6 已建锚点 |
| **①+② 一起** | **vLLM TP=2 平行部署**（本仓 A4 已判"现在就能试"，且**不动 llama.cpp 服务**） | 中 | 同款 M2.7 AWQ INT4 社区 **18.5–24.8** vs 现 20 |
| **② 的 RPC 形态** | 卡 `#26610` | 上游门 | TRACKER §1.4 |
| **③ 投机解码** | ★ GLM 上**只有换运行时**（GGUF 丢 MTP）；llama.cpp 侧可试 **ngram** | 中 | 本仓 A4-4："**不确定，有结构性风险**" |
| ~~换 40G 线~~ | **不是性能项** | — | A2：利用率 **0.02%** |

**★★ 更正后的判词**

CIRU 的 2× ≈ **①串行跨链（本仓已量化，且有 0 成本路径）× ②TP 语义 × ③投机解码**。
⇒ **最大的那半（①）不需要 CIRU**：要么等 `#26610`（+32%），要么 vLLM TP=2。
⇒ **CIRU 的不可替代点收窄为一句**：**GLM-5.3-Flash 的「MTP 投机解码 + 现成打包 + 已测质量报告」**。
⇒ 对 DeepSeek **同构**：**无现成 CIRU 包**，且其差距里**同样含 ①②**（与我方 RPC 完全同型）。

**未实测（不静默，续 §11.6）**

5. **38.7 次往返/token 是 M2.7 双机**的数 ⇒ **GLM（glm5next、三机）的往返数未测**（"三机 < 双机"支持该机制，但不是该数字的复现）。
6. **`#26610` 的 +32% 是社区同构**（非本集群、非 GLM）⇒ 只能当**预期量级**。
7. **第⑤轴（AITER/TileLang vs Vulkan 的引擎效率差）完全未量化** —— 这正是第一轮 §11 想当然排除掉的那一项。

### 11.8 ①轴追问：**串行跨链「当前」能不能解**（2026-09-29 第三轮）

> **触发**：用户追问"① 串行跨链问题**当前**是否可以解决"。
> **答法**：把税**拆成两半** —— **税 = 往返次数 × 单次 RTT**。本仓 §1 已采证到数字级：
> 每 token ≈ **38.7 次 RPC 命令 / 903 KB**，带宽占用 **17.6 MB/s = 链路的 0.02%** ⇒ 瓶颈是**延迟 × 命令数**，**不是带宽**。

| 半边 | **现在能解吗** | 依据 |
|---|---|---|
| **①-A 减 RTT（税基）** | ✅ **能 —— 今天就能做，零成本** | ★ **A3a USB4 低延迟 sysctl 套件**（TCP 低延迟参数 + TB 保活 + **CPU EPP=performance**；源 = `ayysasha 99-usb4net-lowlatency.conf`，**逐项对照增量应用**）＝**零成本、未做**；本仓判"**压 RTT 税基，收益传导最确定**"，列**建议序第 1 位**。**已有基础**：pm_qos=100 + MTU 9000 已把 RTT **0.619 → 0.100 ms（−84%）**。⚠ 只**线性**改善、**不根治**；地板 = tbnet 往返 + 内核栈（24 µs 级 RDMA 拿不到，见 §10） |
| **①-B 减往返次数** | ❌ **修不了，只能绕** | **修**：`#26610` **现在不可用** —— TRACKER §W-6 的 **9/27 状态**：*"当日有活动（commits 3→5、37 评论）**但 checks 失败数 1→3**"* ⇒ ★ 本表纪律：**"有新活动"不得当进展读，要看失败数**；且协议 **6.0.0 无向后兼容**。★ **且对 GLM 无效**：GLM 混合架构（KDA 34/45 层 + NoPE MLA + 池化 indexer + ×4 mHC）**与 `-sm tensor` 正交** ⇒ **GLM 只能走 `-sm layer`**；V4 另需等配套 **`#25860`（Draft，停滞）**。<br>**绕**：**vLLM TP=2** —— 本仓已判 **"现在就能试"**（A4，"B 站平行部署**不动** llama.cpp 服务"）；TRACKER 更判 **"值得试点"**（**ROCm 10.0.0 官方矩阵含 `gfx1151`** ⇒ 不是"能不能跑"的问题）。**决策门：单流 tg ≥ 24 t/s 且 16k 上下文无崩溃** |

**★ 触发条件本仓已写死**（TRACKER §W-6）：**"长期死锁 ⇒ 启动 A/B；转 clean ⇒ 等上游（成本 0）"** —— 即 `#26610`/`#27754` 长期不动就上 vLLM，这是**预授权**的转折信号。

**★★ 机制级收获：③ 依赖 ②，不独立**

本仓 §3.2 明写：**"投机解码在双机 RPC 上是**未验证的赌博**"** —— 分布式场景**每步验证会引入额外跨链同步**，
**方向上与已确认的瓶颈（命令数）相反**（若 ngram 每步多 k 次 `get/set_tensor`，**串行税放大，收益可能被吃掉甚至倒挂**）。
⇒ 这正是 §11.7 用「**叠乘**」而非"叠加"的**机制解释**：**CIRU 的投机解码收益是在 TP（并行语义）上拿的，不是在 RPC 上**；
**拆到 layer-split RPC 上大概率被串行税吃掉** ⇒ ③ **不能脱离 ② 单独搬过来**。

**最小行动（照本仓 08-28 原定序，未改）**

```
A3a sysctl 套件（本周零成本，压 RTT 税基）          ← ①-A，今天可做
  → A4 vLLM TP=2 平行试验（门: tg≥24 且 16k 无崩溃） ← ①-B + ② 一起拿
    → A6 #26610（事件驱动，成本 0；GLM 上无收益）
```
投机解码（③）**排在最后**，且按 §3.2 属"**未验证的赌博**"。

**未实测（不静默，续 §11.7）**

8. ★ **A3a 的端到端增益已实测 = 0（2026-09-29）** —— 本仓原判"收益传导最确定"**被证伪**：C 段 TCP-RTT 已压到 **130.4→~19µs（×6.8）**，但三机 GLM-5.3-Flash `flow bench` decode = **11.4 t/s**（4 次采样 11.4/11.4/11.5/11.4），与**同日 C 未调优**的锚 **11.4** 逐位一致 ⇒ **RTT 税基本身不是 decode 的约束**（与 §11.1「decode = 内存带宽 bound」同向）。详见 metrics-log §A3a 补测。
9. **A4 的决策门未试** —— tg ≥ 24 t/s / 16k 无崩溃**两条均未跑**。
10. **「`#26610` 对 GLM 无效」是 TRACKER 的架构级推断（E3）**，**非本机实测**。
