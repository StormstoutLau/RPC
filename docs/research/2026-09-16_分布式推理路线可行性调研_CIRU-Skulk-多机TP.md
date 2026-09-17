# 分布式推理路线可行性调研：CIRU StrixLink / Skulk（含 vLLM 多机 TP 与 AMD 官方路线）

> **日期**: 2026-09-16（**v3 增补 2026-09-17**：新增 **§9「ROCm 6.x vs 7.x on gfx1151 专项调研」** —— 回答"B/C 是否该与 A 站同步装 ROCm 6.4.1 / ROCm 7.x 是否在本显卡退化"；同时补齐 §8 的 ROCm 一手来源。v2，同日修订：用户给出 `jcbtc/GLM5.3-Flash-CIRU-STRIX-IU4` 出处后**重新取证并推翻 v1 的"未证实"结论**）
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

**一句话（v2）**：用户诊断的"支持力度不够"**有一条现成解** —— **CIRU StrixLink 双机方案**（GLM-5.3-Flash 320B、UMA 分片权重、USB4 上自有 all-reduce、实测可用吞吐）；代价是**引入 ROCm 10/vLLM 新栈 + 需两机同时在场 + 治理接入**。Skulk 补的是编排，**不改上游事实**。

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

**二手（仅作旁证）**
- [CIRU 运行时发行说明索引页（Ling-3.0-Flash-CIRU-int4-Strix-native）](https://www.toolify.ai/ai-model/jcbtc-ling-3-0-flash-ciru-int4-strix-native)
- [kyuz0/amd-strix-halo-toolboxes](https://github.com/kyuz0/amd-strix-halo-toolboxes)（把 `rocm-6.4.4` 标 Stable、`rocm-7-nightlies` 标 Experimental）｜[其 toolbox 说明](https://deepwiki.com/kyuz0/amd-strix-halo-toolboxes/3.1-rocm-toolboxes)
- [lemonade-server：gfx1151 Linux 踩坑（`amdgpu-dkms` 破坏 ROCm）](https://lemonade-server.ai/gfx1151_linux.html)
- [NGA 帖（同机 6.4.4 vs 7.0.2 的 pp 数字）](https://bbs.nga.cn/read.php?tid=45354933)（**二手，未经复验**）

**本仓**
- [upstream-tracker §1.4/§1.5](../../spec/upstream-tracker/TRACKER.md)｜[ADR-0004](../../adr/ADR-0004-统一管理入口为唯一管理面.md)

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
