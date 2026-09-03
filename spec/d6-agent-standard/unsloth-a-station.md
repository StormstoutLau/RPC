# Unsloth Studio 调研落档：A站单机模型管理后端

> 日期：2026-09-03
> 目标：A站（scott-lau-NEX）现状 + 桥接Claude Code可行性 + 推理/训练评估

## 1. 已探明安装状态

| 项              | 值                                                                       |
| -------------- | ----------------------------------------------------------------------- |
| 安装根            | `~/.unsloth/studio/`                                                    |
| CLI 版本         | unsloth 2026.9.2                                                        |
| Python venv    | Python 3.13.5 (`~/.unsloth/studio/unsloth_studio/bin/python`)           |
| CLI 入口         | `~/.local/bin/unsloth` → `~/.unsloth/studio/unsloth_studio/bin/unsloth` |
| Studio 数据库     | `~/.unsloth/studio/studio.db`                                           |
| 当前未运行          | 8080 被 `llama-server gpt-oss-120b` 占用，8888 关闭                           |
| 模型目录           | `/data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF`（同现有裸跑）         |
| A站 opencode 配置 | 现有 `cluster-local` → `baseURL http://127.0.0.1:8080/v1` → 复用 8080 最小迁移  |

## 2. Unsloth ↔ 现有集群架构

### 2.1 端口协议（双方言兼容）

Unsloth Studio 同一端口同时支持两种 OpenAI/Anthropic 兼容端点：

| Client                | Protocol           | Path                   | 现状兼容性                  |
| --------------------- | ------------------ | ---------------------- | ---------------------- |
| opencode (D6 wrapper) | OpenAI-compatible  | `/v1/chat/completions` | ✅ 直接兼容，baseURL 不变走最小迁移 |
| Claude Code CLI       | Anthropic Messages | `/v1/messages`         | ✅ 原生兼容，无需翻译代理 → 同端口并存  |

> 要点：`unsloth studio run --api-only` → 只启服务不启前端，走纯后端路径；`--host 0.0.0.0` → 可跨机访问（D6 不跨机，现状保留`127.0.0.1`）。

### 2.2 Claude Code 桥接（`unsloth start claude`）

- 原生支持直接接入：`unsloth start claude --model ...` 自动导出所需 `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN`，直接拉起 claude 会话。

- `--no-launch` → 只打印 env 不拉起，脚本化友好。

- `--as-subagent` → 保持当前模型、加接 Unsloth 本地推理子代理。

- **已知坑**：

  1. Claude Code  attribution header **KV cache 作废 → 推理慢 90%** → 修复：`export CLAUDE_CODE_ATTRIBUTION_HEADER=0` + `~/.claude/settings.json` env 落档。
  2. 不能同时设 `ANTHROPIC_API_KEY` + `ANTHROPIC_AUTH_TOKEN` → auth 冲突。
  3. 必须映射 `ANTHROPIC_DEFAULT_{SONNET,HAIKU,OPUS}_MODEL` → 否则 Claude 自动请求不存在的 Anthropic 模型名。

## 3. 调研结论：桥接可行性

✅ **可行，双客户端同端口并存**：opencode（D6 wrapper 头less）与 Claude Code（交互式）共享同一个 Unsloth 后端 + 模型，不需要两个端口/两次加载。

***

## 4. 推理性能调优参数、潜力

### 4.1 并行解码槽位

默认：`--parallel 4` → 4 路并行解码。现有裸跑 `llama-server` `--np 1`（单槽），换 Unsloth 原生调度可提升并发吞吐。

CLI 可调：`--parallel 1~64` → 依 GPU 显存/模型大小调：

| 模型大小 | 推荐槽数  |
| ---- | ----- |
| 120B | 2\~4  |
| 70B  | 4\~8  |
| <30B | 8\~16 |

### 4.2 推理上下文与量化

Unsloth Studio 自动参数调优：

- `max-seq-length` → 默认模型推荐值（GGUF 元读出来），覆盖可`--max-seq-length N`。

- 已有 GGUF（MXFP4/Q4/Q8）Unsloth 直接加载，不需要二次转换；对 GPT-OSS 官方 GGUF 开箱即用。

- 内存策略：`--gpu-memory-mode auto/manual` → auto 自动放置分层，manual 留给专家微调。

- MoE 适配：Unsloth 底层用 llama.cpp，原生支持 `--n-cpu-moe 0`（CPU offload 专家），与现有裸跑配置一致，不需要改。

**Unsloth Dynamic 2.0 量化（推理性能关键变量，第三方实测）：**

- 机制：非均匀逐层量化——敏感层（embedding/首尾 attention）保 Q6/Q8，MoE 专家 FFN 压到 Q2/Q3；平均位宽≈Q4，但困惑度接近均匀 Q5。

- 实测（独立 benchmark）：UD-Q3\_K\_XL 对比均匀 Q4\_K\_M，**体积小 \~30%** 且生成提速 1.6\~7.8%（长输入/长上文时更明显，因内存带宽瓶颈随体积下降）；短输入 prefill 偶有 Q4 略快（引擎差异）。

- **注意**：Unsloth 的 UD GGUF **与 Ollama 不兼容**（仅 llama.cpp/Unsloth server 可跑），这一点正符合我们用 unsloth 自带 server，不冲突。

- 对 A站 120B：现在跑 MXFP4，可试切 Unsloth 官方 gpt-oss-120b-GGUF（含 chat template 修复）或其 UD 变体，通常比等位宽 k-quant 更小更快；**同机需自测**，第三方数字为 M3 Max/消费级，非 A站硬件。

### 4.3 自修复工具调用

Unsloth Studio 内置 `StreamToolCallHealer` → 对于小模型写出的文本化工具调用（"`json ...`"）自动修复为结构化 `delta.tool_calls`，**减少约 50% 坏调用**，对 coding agent 吞吐提升。支持：

- 自动开启（默认），可 `--disable-tool-call-healing` 关闭。

- 对 OpenAI/Anthropic 协议都生效。

### 4.4 推理延迟 & 吞吐潜力

对比裸跑 `llama-server`：

- **相同模型/量化**：Unsloth 底层还是 llama.cpp，核心推理延迟一致，没有 overhead。

- **潜力 1（吞吐）**：`--parallel N` → 单 GPU 多槽并发解码，多任务排队 latency 低于裸跑单槽。

- **潜力 2（体积→速度）**：UD 动态量化（§4.2）更小更快（内存带宽瓶颈）。

- **潜力 3（speculative decoding）**：llama.cpp 支持草稿模型+大模型投机采样，**第三方实测 3.2× 提速**（64→206 t/s，代价 +\~9GB 显存）——对 120B 是最大吞吐杠杆，值得在 A站实测。

- **缺陷**：一次只能加载一个模型，切换即卸载重载 → 多模型冷启动延迟，不做多模型并发（留给 litellm 网关）。

***

## 5. 模型微调/训练：Unsloth 是否更合适？

### 5.1 核心优势（针对 gpt-oss 官方数据）

现跑的就是 gpt-oss-120b，而 Unsloth **对 gpt-oss 有专用微调路径**：

1. **gpt-oss 微调**：**1.5× 更快、VRAM 省 70%**、上下文长 10×；`gpt-oss-20b QLoRA 仅需 ~14GB VRAM`，`gpt-oss-120b 约 65GB VRAM`（QLoRA）。
2. **MoE 专用内核**：`torch._grouped_mm` + Triton 分组 GEMM → **MoE 训练 12× 更快、VRAM 省 35%、上下文长 6×**（无精度损失）；A100 上 Triton kernel 还再快 \~2.5×。gpt-oss/Qwen3/DeepSeek/GLM 均支持，含 **gpt-oss-120b A100 官方 notebook**。
3. **长上下文 + RL**：Unsloth Flex Attention → >8× 更长上下文、>50% 省显存、>1.5× 更快；GRPO 强化学习 → 2× 更快、显存省 80%。
4. **端到端导出闭环**：微调完（LoRA/QLoRA/全量）可直接导出 **GGUF / vLLM / HF** → 回到 Studio 推理后端，训练→部署一条链，不用换中间层。
5. **无代码 UI**（Studio）：Data Recipes 可视化数据流程 + 训练监控 + 导出，降低工程门槛。

### 5.2 关键 caveat（技术伦理，避免踩坑）

- **MoE 不推荐 4-bit QLoRA**：BitsandBytes 不支持 MoE 4bit（非 Unsloth 特有）→ 用 **bf16 LoRA 或全量**。

- 加速数据多在 colab/A100/消费级测得，A站具体显卡需**自跑 benchmark**。

- Studio UI 为 **AGPL-3.0**（核心库 Apache-2.0）——商用/再分发需注意许可证边界。

### 5.3 对比 D6 场景结论

| 场景                | 裸 llama.cpp   | Unsloth Studio                           |
| ----------------- | ------------- | ---------------------------------------- |
| 纯推理单模型（现 A站）      | 工作良好          | 原生多槽并发 + 工具自愈 + UD 量化 + 投机解码可选 → 更好      |
| 多模型并发             | 需要 litellm 网关 | 仍需要（单加载）→ 与裸跑一致                          |
| LoRA/QLoRA 微调     | 无原生支持         | 原生支持 → **好很多**                           |
| 全参数 / MoE / RL 训练 | 需自搭 pipeline  | 原生 gpt-oss 专用 + 12× MoE + GRPO → **好很多** |
| 微调后导出推理           | 需手动转 GGUF     | 一键导出直接加载回 Studio → **好很多**               |

**结论**：

- **现在（纯推理 gpt-oss-120b）**：换 Unsloth 有收益（多槽并发/工具自愈/UD 量化），无成本（复用现有 GGUF 或换官方 gpt-oss-120b-GGUF 即更快），可落地。

- **未来（扩展微调/训练）**：Unsloth **明显更合适**——现跑 gpt-oss 恰是其头号支持对象，微调→导出→推理一条链闭环；裸 llama.cpp 需要另搭训练栈。**若 D6 计划对现网模型做领域适配，Unsloth 是下一版的自然演进目标。**

***

（本文件第 4/5 节数据来源：unsloth.ai 官方文档 + 独立第三方 llama.cpp/GGUF benchmark；`unsloth start claude --help`/版本为 A站本机实测）

***

## 6. 推理后端：版本管理与 Vulkan/ROCm 切换（补充调研 2026.9）

### 6.1 llama.cpp 推理后端版本管理

Unsloth 的 GGUF 推理底层为 **launched llama.cpp（`llama-server`）**，其版本管理机制：

| 能力                     | 支持情况                                              | 说明                                                                                                                            |
| ---------------------- | ------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| 后端更新                   | ✅ 应用内 **Update llama.cpp 按钮**                     | 不必重装 Studio，单独更新本地 llama.cpp 后端                                                                                               |
| 预编译分发作                 | ✅ CUDA/ROCm/Windows/Linux/macOS 均为 fresh prebuilt | ROCm 版**每日**更新                                                                                                                |
| Studio 本体更新            | ⚠️ 用官方安装脚本                                        | `curl -fsSL https://unsloth.ai/install.sh \| sh` / `irm ...uns.ps1 \| iex`；**官方警告：不要用** **`unsloth studio update`**（打包不会拿到最新） |
| 版本号                    | 双轨                                                | `v0.1.xxx-beta` 与日期 `2026.x.x` 并存；A站现装 **2026.9.2**                                                                           |
| **指定/固定 llama.cpp 版本** | ❌ **不支持**                                         | 只有"latest 每日 prebuilt"，**无法 pin 到某 commit**                                                                                   |

> **对 D6 的意义（治理风险）**：作为 7×24 推理节点，后端每次启动拉最新 llama.cpp，**可复现性差**——D6 验收依赖稳定的契约/吞吐口径，版本漂移可能改变 token/s、错误码、工具解析行为。若严肃当后端，需评估：①能否靠 `UNSLOTH_LLAMA_CPP_BACKEND` + 本地缓存固定 prebuilt；②或在升级窗口做回归。当前裸跑 `/opt/llama.cpp` 是系统级固定版本，反而可控。

### 6.2 后端切换：Vulkan / ROCm（✅ 完整支持）

GGUF 推理后端**可在安装时与运行时可切换**：

- **运行时 UI**：Settings > System > **GGUF inference engine** = `CPU / CUDA / ROCm / Vulkan`（只列出当前机器有 build 的项）。

- **安装时强制**：`UNSLOTH_LLAMA_CPP_BACKEND=auto|cpu|cuda|rocm|vulkan`。

- **ROCm（AMD）**：官方支持 Radeon RX 9000/7000、Instinct MI300/350、Strix Halo；setup.sh 经 `hipcc/hipconfig/rocminfo` 自动探测，CUDA 存在时**CUDA 优先**（不静默翻转）；ROCm prebuilt 每日更新。

- **Vulkan**：**仅 GGUF 推理**，**不用于训练**；对无 ROCm PyTorch wheel 的 Polaris/RDNA1 等老卡是 GPU 推理兜底。

- **macOS**：走 Metal（无 Vulkan bundle），Apple Silicon 与 Intel-Mac-AMD 均覆盖。

- **A站实际（本机核实，修正 6.2 原假设）**：A站 GPU 为 **AMD Strix Halo（Ryzen AI Max+ 395 / Radeon 8060S, gfx1151）**，**无 NVIDIA**；现系统 gpt-oss 走 **Vulkan** 构建（`/opt/llama.cpp` 链接 `libggml-vulkan.so`）；Unsloth 安装期自动选择 **ROCm/gfx1151** 预编译。故 A站 的 CUDA 无关，**ROCm 与 Vulkan 均直接相关**（见 §7）。

### 6.3 结论

- 版本管理：**有基础的更新机制（in-app 按钮 + 安装脚本）**；官方无"pin 到某 commit"的显式开关，但**可通过删除 marker 实现真正冻结 llama.cpp**（§7 已验证）——治理风险**可解**，非无解。

- 后端切换：**完备**，UI 可切 + 安装期 env 可指定，ROCm/Vulkan 均支持（Vulkan 仅推理）。A站为 **ROCm gfx1151** 卡，ROCm/Vulkan 均直接可用。

- A站落地建议：后端用 `UNSLOTH_LLAMA_CPP_BACKEND=rocm` 显式固化；如需契约稳定，按 §7 冻结 llama.cpp 版本（删 marker → source build 冻结），升级窗再做 D6 回归。

***

## 7. llama.cpp 版本固定方案（验证 2026.9）

> 目标：验证"能否固定 llama.cpp 版本，避免 Unsloth 启动/更新漂移"。

### 7.1 本机实况（A站）

| 项           | 值                                                                                                                                            |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| 预编译位置       | `~/.unsloth/llama.cpp/`（源码树 `build/bin/llama-server`，软链 `llama-server→build/bin/llama-server`，**无 .git**）                                    |
| 已装版本        | `0.3.0-dev (build 10715, commit 92cedc867)` —— *Compiled by the Unsloth team*                                                                |
| 后端          | **rocm / gfx1151**（marker 记录）                                                                                                                |
| 安装身份 marker | `~/.unsloth/llama.cpp/UNSLOTH_PREBUILT_INFO.json`（`tag=b10715`, `release_tag=b10715-mix-86bd2d3`, `source_commit=92cedc8…`, `source_sha256`） |
| 新鲜度缓存       | `~/.unsloth/studio/cache/llama_cpp_freshness/`（24h 磁盘缓存 + 60s 失败缓存）                                                                          |

### 7.2 更新触发机制（代码取证）

- freshness 仅**展示性 banner**：`GET /api/llama/update-status`（经由 `main.py:lifespan()`），**不自动替换**。

- 真正的 swap 只在 **手动** `POST /api/llama/update`（UI "Update llama.cpp"）时经 `llama_cpp_update.py` 触发。

- **离线即无更新压力**：GitHub fetch 失败 → `latest=None` → `is_behind=False`（fails open，不误报 banner）；update checks 可整体禁用，offline boot 静默。

- `is_behind` 有 downgrade guard：`latest` 基础 build 低于 installed 时判定"不落后"。

### 7.3 固定方案（验证结论：**可行，且默认即固定**）

| 方案              | 操作                                                   | 效果                                                                                                                |
| --------------- | ---------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| **A. 默认（不动）**   | 不点 Update llama.cpp                                  | llama.cpp 保持 `b10715/92cedc8` 不变，仅可能出现"有新版本"banner；**不会自动升级**                                                     |
| **B. 强固定（推荐）**  | 删除 `~/.unsloth/llama.cpp/UNSLOTH_PREBUILT_INFO.json` | 被识别为 **source build** → `/api/llama/update` 直接 `skip_reason=not_prebuilt`，**更新机制无法替换** → 二进制锁定当前 commit，banner 消失 |
| **C. 完全禁用更新检查** | 程序级禁用 update checks                                  | 彻底离线式启动，杜绝任何更新响应                                                                                                  |

- **可复现身份已落盘**：即使将来重装，marker 的 `source_commit=92cedc867` + `source_sha256` + release\_tag 即可按原样重建/还原同一份 llama.cpp。

- **正交 axis**：`UNSLOTH_LLAMA_CPP_BACKEND=rocm|cuda|vulkan` 固定的是"后端类型"，与"版本冻结"（§7.3 A/B/C）是两个独立维度，可同时施加。

### 7.4 对 D6 的落地动作

1. 若用 Unsloth 当 A站 后端：先 `export UNSLOTH_LLAMA_CPP_BACKEND=rocm` 固化后端类型。
2. 用 **方案 B（删 marker）** 冻结 `b10715/92cedc8`；或在更新窗内做 D6 回归（吞吐/工具调用/错误码）后再更新。
3. 记录当前版本身份（commit/sha256 已入 §7.1），便于回滚重建。

***

## 8. 实机跑测：unsloth ROCm 跑 gpt-oss-120b（实测 2026.9）

### 8.1 步骤与状态

1. **释放**：停旧系统 `llama-server`(pid 17503, Vulkan) → 统一内存 used 65G→3G（60G 模型释放），无自重启。
2. **启动**：`UNSLOTH_LLAMA_CPP_BACKEND=rocm nohup unsloth studio run --model .../gpt-oss-120b-MXFP4.gguf --port 8081 --api-only`

   - 检测到 **ROCm (HIP 7.13, Radeon 8060S = gfx1151)**；studio app 在 127.0.0.1:8081，底层 llama-server 在本地随机端口。
3. **模型加载**：`phase2` 一次成功（`--fit on / -ngl -1 / --parallel 4 / -c 131072 / --flash-attn on`），"model loaded"，RSS \~67.6G。

   - 首跑 `--load-mode none` 尝试整载 65.4G **OOM**（APU 统一内存 headroom 不足），Unsloth 自动降级 `--fit on`（CPU 可 offload）后成功——**大模型在 Strix Halo 上建议直接留 --fit on / paging**。

### 8.2 性能（OpenAI 兼容流式实测量）

| 指标                               | 值                                            |
| -------------------------------- | -------------------------------------------- |
| 模型                               | gpt-oss-120b **MXFP4**（60G GGUF，全 -ngl，ROCm） |
| TTFT（warm 首 token）               | **\~0.52s**                                  |
| 输出（reasoning\_content + content） | reasoning~~1316 + 内容~~93 ≈ **1409 tokens**   |
| 总耗时                              | 27.04s                                       |
| **整体吞吐（含 prefill）**              | **\~52 tok/s**                               |
| **decode-only**                  | **\~53 tok/s**                               |

- 该模型为**推理型**（default reasoning\_effort high）：小 max\_tokens 会被 CoT 吃光、无正文（实测 max\_tokens=64/320 时全是 reasoning，输出仅错误提示）。Deal 方式：给足 max\_tokens + 累加 `delta.reasoning_content`+`delta.content`。

- 流式响应**不返回 usage**（`usage=null`）；令牌数为 `len//4` 估算，±\~10%。

### 8.3 对比与结论

- **绝对吞吐**：120B MoE 在 Ryzen AI Max+ 395（Strix Halo，统一内存）上经 ROCm **\~52 tok/s decode**——对这类 APU 是高性价比水平；TTFT 0.52s 也快。

- 旧系统为 **Vulkan** 构建（`--n-cpu-moe 0 -t 16`）；本次 unsloth 为 **ROCm**。二者未做严格同口径 A/B——本表为 unsloth ROCm 绝对值。如需公平对比，可在同 prompt/token 口径下分别测 tok/s。

- **可复用性**：同一 60G GGUF 直接用，无需转换；RL / 工具调用 / 多槽并发（--parallel 4）均由 unsloth 管理。

- **注意（待用户定夺收尾）**：本测试已停掉 A 站 8080 原 gpt-oss 服务；unsloth 现运行于 **8081**（127.0.0.1）。D6 的 A 站 gpt-oss 端点（opencode `cluster-local`→127.0.0.1:8080、B 网关 upstream）当前**不可用**，需恢复或改指。

  - 选项 A：保留 unsloth ROCm，把端点改指 8081（并考虑 `--host 0.0.0.0` 暴露给 B 网关）；

  - 选项 B：停 unsloth，重启原 Vulkan llama-server 于 8080 恢复现状。

### 8.4 Nemotron 3 Super 120B-A12B（rockm 实测 2026.9）

**模型**：`NVIDIA-Nemotron-3-Super-120B-A12B-Q4_K_M`（3 分片共 \~80.1G，从 B 站 rsync/scp 到 A `/data/models/gguf/.../`）。A 站原无此模型。

**冒过坑**：

- `pkill -f "unsloth studio run"` **杀不到底层 llama-server** → 原先 gpt-oss 的 llama-server(47527, RSS 62G) 残留，导致内存不足、nemotron 加载 OOM 告警（available 一度 5G）。**教训：清模型必须先** **`pkill -9 -f llama-server`**。

- 8081 被遗留 gpt-oss studio 占用 → unsloth 自动改用 **8083**。

- 清理后 `available=121G` → nemotron 一次加载成功（`-ngl -1 --fit on -c 663808`, RSS \~92G）。

**性能（OpenAI 兼容流式实测）**：

| 指标                    | Nemotron 3 Super 120B-A12B (Q4\_K\_M) | gpt-oss-120b (MXFP4) 对比 |
| --------------------- | ------------------------------------- | ----------------------- |
| TTFT（warm）            | \~2.84s                               | \~0.52s                 |
| 输出（reasoning+content） | \~762+751 ≈ 1513 tok                  | —                       |
| 总耗时                   | 96.74s                                | 27.04s（1409 tok）        |
| **整体吞吐**              | **\~15.6 tok/s**                      | \~52 tok/s              |
| **decode-only**       | **\~16.1 tok/s**                      | \~53 tok/s              |

**解读**：nemotron 3 Super A12B 为 **12B 活跃 MoE** + Q4\_K\_M(80G)，比 gpt-oss 的 \~5B 活跃 + MXFP4(60G) 每 token 计算/带宽开销大 → **吞吐约降 3 倍**（16 vs 52 tok/s）、TTFT 更高。属合理硬件表现（Strix Halo 统一内存），非故障。两者均为**推理型**（reasoning/thinking），需给足 max\_tokens 并累加 `reasoning_content`+`content`。

***

## 9. 专项调研（2026.9）：Nemotron 3 Super 优化 / 社区 / ROCm 10

### 9.1 Unsloth 对 Nemotron 3 Super 120B 的优化

- **官方 day-zero 支持**（NVIDIA 合作），有专门运行/微调指南；Unsloth 发布 **GGUF(16 量化) / NVFP4 / FP8 / BF16** 全套：`unsloth/NVIDIA-Nemotron-3-Super-120B-A12B-*`。

- 模型：120B 总 / **12B 活跃（512 专家中 22 激活）**，**LatentMoE = Mamba-2 + MoE + Attention 混合**，context 1M，**NoPE**（无位置嵌入 → 只改 `max_position_embeddings`，不需 YaRN）。

- **推荐推理量化**：`UD-Q4_K_XL`（Unsloth dynamic）。4-bit 需 \~64–72GB；8-bit \~128GB。NVIDIA 建议 temp=1.0/top\_p=1.0（通用）、0.6/0.95（工具调用）；chat 用 `<|thinking|>`(12)/`<|response|>`(13)。

- **微调**：Super 120B **bf16 LoRA 需 256GB VRAM**（多 GPU 才现实）；路由层微调默认禁用（稳定性）。NVIDIA 官方工作流是"Super 生成数据 / **Nano 30B 微调**"——120B 本地微调不现实。

### 9.2 社区 / Strix Halo 性能（与 A 站实测对照）

| 来源                                             | 后端/硬件                        | tok/s                        |
| ---------------------------------------------- | ---------------------------- | ---------------------------- |
| **A 站本次实测（unsloth ROCm）**                      | Strix Halo gfx1151, Q4\_K\_M | **\~16（decode）**             |
| 社区 llama.cpp（Strix Halo 128G）                  | HIP / gfx1151, Q4\_K\_M      | 14–17 tok/s                  |
| 社区 llama.cpp（Radeon 8060S, Vulkan/RADV, b9453） | Vulkan, Tesla                | tg128=**17.94**, pp512=292.5 |
| DGX Spark（GB10）                                | CUDA, Q4\_K                  | think 19.6 / nothink 35.4    |

- A 站 \~16 tok/s **与社区 14–17 tok/s 高度一致** → 属该硬件该模型正常水平，非配置故障。

- **社区踩坑与提速点**：BIOS 需开启 Above-4G Decoding + Re-Size BAR + UMA FB 1GB；内核参数 `amdttm.pages_limit / page_pool_size=27648000`；llama.cpp `--no-mmap`（unified memory 防 mmap 错误）；统一内存下 MXFP4 GGUF 在 Strix Halo **初始化失败**，Q4\_K\_M 是可行档 → 可试 UD-Q4\_K\_XL。预填充 pp512 \~292 tok/s。

### 9.3 AMD ROCm 10 / ROCm.AI（2026-08 发布，十周年）

- **Core SDK 10.0** 基于 **TheRock** 构建；统一 repo.amd.com 发行源；Windows/Linux/Instinct+Radeon+Ryzen。

- **ROCm.AI 平台（GA）三件套**：

  1. **ROCm CLI**：`install/validate/serve/examine`，`rocm serve` 推理、`rocm examine` 诊断、支持离线(air-gapped)打包。
  2. **AMD Skills**：Agent Skills 格式的验证知识模块，可装进 **Claude Code / Cursor / Codex**——直接相关（D6 用 opencode，opencode 亦近同生态）。
  3. **Hyperloom**：开源 agentic 自动推断优化闭环（baseline→profile→改 kernel/serving→校验→重复），面向 HIP/Triton/FlyDSL，配 vLLM/SGLang。

- 框架：ROCm 10 支持 vLLM、SGLang（turnkey serving）+ **Unsloth on Ryzen AI Max（LoRA/QLoRA 本地微调）**——与 A 站直接相关；roofline 扩展到 GFX11xx、ROCm Optiq 1.0、ASAN 包。

- 声称：ROCm.AI 较 ROCm 7 **inference \~3.3× / training \~2.4×**（条件：8×MI355X + preview 配置，非通用；对 A 站 Strix Halo 需自测）。

- **A 站现状与风险**：现检测 HIP **7.13**（ROCm 7.x）。升 ROCm 10 可能带来推断提升与 Unsloth-Ryzen 官方支持，但**上轮已见 unsloth bundled ROCm lib 与系统 ROCm 的 symbol 不匹配**（`hsa_amd_queue_create`）——升级属**高风险操作**，须先在 A 站做 ROCm 10 + unsloth 兼容性验证与基准，避免破坏当前可用状态。

### 9.4 ROCm 10 对 Strix Halo(gfx1151) 支持度 + 社区反馈（补充调研 2026.9）

**官方支持度**：

- **ROCm 10.0.0 兼容矩阵明确列入 gfx1151**（Ryzen AI Max+ PRO 495 / Radeon 8065S）；ROCm 7.14 已支持 Pred 495/490/485(gfx1151)。A 站的 **395 / Radeon 8060S** 为消费级同 gfx1151 架构（官方矩阵主要列 PRO 版，架构一致）。

- 历史：ROCm 7.x 曾有 issue #6348 "gfx1151 missing HIP kernel"，AMD 官方回复"gfx1151 已支持"，并在 7.14/10 正式落实——**支持早自 7.x 便具备，10 是延续**。

**社区反馈 / 痛点（LLM 后端，重要）**：

1. **llama.cpp HIP 在 gfx1151 有严重问题**（open issues）：

   - **#27579**：HIP backend 在 gfx1151 **产出损坏输出**——dense 模型(llama/qwen35)全失败、**512-expert MoE 正常**（怀疑 mul\_mat vs mul\_mat\_id 路径）；Vulkan 同 flags 正确。

   - **#27856**：HIP/gfx1151 **decode 随 context 深度悬崖**（\~1K tokens 后 19→5.5 tok/s，QSA/top-k HIP 未优化）——长上下文惩罚巨大。

   - **#27865**：ROCm RPC/TOP\_K crash。
2. **vLLM on gfx1151**（#32180）：V1 engine HIP graph capture 超时，被迫 `--enforce-eager`（慢）；社区："vLLM 只在超慢 fallback 模式可用"。
3. **Ollama on Strix Halo**：社区实测 **ollama-vulkan 最快**，rocm 各种 HSA\_OVERRIDE 都更慢——"ROCm on Strix Halo 仍很原始(green)"。
4. **Strix Halo 平台带宽上限**：\~256GB/s LPDDR5X → 70B Q4 \~6 tok/s、EMB=memory-bound。

**对 A 站的综合含义（关键）**：

- A 站两模型（gpt-oss/nemotron）**都是 MoE**——llama.cpp HIP 的 MoE(mul\_mat\_id) 路径按 #27579 实测正常，与我们实测（gpt-oss \~52、nemotron \~16 tok/s、输出正确）一致。

- **风险点**：①长上下文 >\~1K tokens 的 HIP 深度降速（#27856）——D6 若用到长上下文需留意；②dense 模型在 HIP 有损坏输出（#27579，若未来上 dense 模型慎用 HIP）；③vLLM 在 gfx1151 不稳定（#32180）——**不依赖 vLLM**。

- **Vulkan vs ROCm**：社区普遍认为 gfx1151 上 **Vulkan 更稳**——这与 A 站原系统(Vulkan)一致。unsloth 走 ROCm；若追求稳可考虑 unsloth 配 Vulkan 后端对比。

- **ROCm 10 升级**：有推算收益（官方 3.3×，但基于 8×MI355X preview，非 gfx1151），且上述 HIP 问题（#27579/#27856/#32180）在 ROCm 10 下**仍未关闭**；叠加 bundled-lib symbol 风险 → **现阶段维持 ROCm 7.x 跑 unolorh 更稳，ROCm 10 评估留作低优先级/需隔离验证**。

### 8.5 A/B：unsloth 复用自编 /opt Vulkan llama（实测 2026.9，nemotron）

**机制验证**：unsolth 通过 **`LLAMA_SERVER_PATH=/opt/llama.cpp/llama-server`**（优先级最高，llama\_cpp.py:7558）直接复用我们自编的 **Vulkan** llama-server；实测派生的正是 `/opt/llama.cpp/llama-server ... --device Vulkan0 --fit off --load-mode none`。用 env/custom 路径时 unsloth 视为**非托管**→不自动更新（顺带落版冻结）。

**Nemotron 3 Super 120B-A12B 同 prompt A/B**：

| 指标          | **Vulkan**（复用 /opt，ggml 0.22） | ROCm（unsloth b10715） |
| ----------- | ----------------------------- | -------------------- |
| TTFT        | **8.99s**（劣）                  | 2.84s                |
| 输出 tokens   | \~1400（716 reasoning+684）     | \~1513               |
| 总耗时         | 87.35s                        | 96.74s               |
| 整体吞吐        | **16.03 tok/s**               | 15.6 tok/s           |
| decode-only | **17.87 tok/s**               | 16.1 tok/s           |

**结论**：

- **可复用性成立**：unsloth 能用 `LLAMA_SERVER_PATH` 跑我们编的 Vulkan llama，零额外安装。

- **性能基本打平**：整体 \~16 tok/s 一致；Vulkan decode-only 略高（17.9 vs 16.1），但 **TTFT 明显更差**（8.99 vs 2.84s，Vulkan 预填充/旧 ggml 0.22 更慢）。

- **注意混淆变量**：Vulkan 是较旧的 /opt build(ggml 0.22)，ROCm 是 unsloth b10715——差异含引擎版本因素，非纯粹后端对比。

- 两者均可用于 A 站；选择取决于：要更稳的预填充/短 TTFT 用 ROCm，或接受慢启动换略高稳定/兼容（Vulkan 社区偏好）。当前实测未发现 ROCm 在 MoE 上的正确性问题（与我们模型均为 MoE 吻合，规避了 dense 的 HIP bug）。

### 8.6 原系统 Vulkan llama 版本明细（取证 2026.9）

| 项            | 值                                                                     |
| ------------ | --------------------------------------------------------------------- |
| 路径           | `/opt/llama.cpp/llama-server`                                         |
| llama.cpp 版本 | `0.3.0-dev (build 0, commit unknown)` —— 自编源码快照，**无 git/commit 元数据**  |
| 编译器          | GNU 13.3.0 for Linux x86\_64                                          |
| 构建时间         | \~2026-08-31 14:57                                                    |
| ggml 核心      | **0.22.0**（`libggml.so.0.22.0` + base/cpu/rpc 0.22.0）                 |
| 后端           | **仅 Vulkan**（`libggml-vulkan.so.0.22.0`，无 CUDA/ROCm .so）              |
| 链接           | RUNPATH=`$ORIGIN`，自包含                                                 |
| 对应原服务        | A 站 gpt-oss-120b @ 8080 的 `llama-server -ngl 999 --n-cpu-moe 0 -t 16` |

> 比 unsloth 自带 ROCm b10715 旧一代 → 解释 A/B 中 Vulkan TTFT 偏慢。

### 9.5 补充调研（2026.9）：Vulkan 更新 / DeepSeek-V4 算子 / GLM-5.3 支持

**① llama.cpp Vulkan 后端更新（快进中，gfx1151 重点优化）**

- **#26585**（已合）：tiled transpose 优化 DeepSeek-V4 lightning-indexer 的 0↔2 permute → gfx1151 上该算子 7~~20→86~~580 GB/s，V4-Flash IQ3 prefill +84%（56→104 t/s）。

- **#27952**（open）：RDNA3/4 **int8 coopmat1 matmul** → Strix Halo prompt 处理显著提升，量化 q3\~q6/mxfp4/nvfp4 支持，\~1.2–1.4×。

- **#26829**（draft，Intel ARC）：新 FA shaders + GEMM/MoE 优化。

- **b10517**（released）：Vulkan **KV-cache dequant 优化 → \~2×**（coopmat1 q8\_0 单趟 dequant），OOB VRAM 兜底。

- 结论：我们自编 /opt Vulkan(ggml 0.22) 已明显过时——升级能换来大幅 prefill 增益（尤其 DeepSeek-V4 indexer 类）。

**② DeepSeek-V4-Flash 算子问题（HIP + Vulkan 都有坑，均 open）**

- **#25382**（已修）：q8\_0 K-cache **全后端乱码**——根因 KV Hadamard rotation 把模型逼离稀疏路径 → 禁 DEEPSEEK4 rotation 修复。

- **#26399**（open）：HIP **GGML\_OP\_TOP\_K >\~3–4K context 回落 CPU → 6.4× tg 损失**（gfx906 6×MI50 实测）。

- **#26746**（open）：**ROCm gfx1151 RPC worker 在 V4 prefill 4096 tokens 后 TOP\_K 崩溃**（7.13/7.14 均复现）；**换 Vulkan worker 同机不稳但稳定不崩**（慢）。

- **#27856**：HIP decode 随 context 悬崖（前已述）。

- Vulkan 侧（CSDN 实测）：**Lightning Indexer / fused DSV4 HC pre/comb/post 在 Vulkan 不支持、被 disabled** → 加载能过、推理崩。

- 结论：V4-Flash 这类新 hybrid（lightning indexer + HC fusion）在 Strix Halo 的 HIP/Vulkan **算子支持未成熟**，现阶段上 A 站有风险。

**③ GLM-5.3-Flash 支持问题（主线未合并）**

- GLM-5.3-Flash = arch **glm5next**（Z AI，320\~321B hybrid：34 KDA + 11 DSA、mHC、DeepSeek 式 MoE、MLA/NoPE、视觉）。unsloth 已出 UD-Q1/Q2/Q3 GGUF。

- **#27922**（open）：主线**无法加载**——`unknown model architecture: 'glm5next'`（+ flash mmproj CLIP 失败）。

- **#27773**（open PR，timkhronos）：gem5next 支持（复用 Kimi-K3/KDA、DSV4/mHC、DSA indexer 4-token 池）；MTP 另 PR；多序列需 `--kv-unified`。

- **#27754**（open PR，unsloth/danielhanchen）：官方未合并支持；**正确性需** **`NVIDIA_TF32_OVERRIDE=0`** **+** **`-fa off`**（MLA F32→F16 cast）；MTP 支持；B200 有深度吞吐优化。

- 结论：**GLM-5.3-Flash 尚未进主线 llama.cpp**，仅 open PR / unsloth 分支可用；"flash"视觉 mmproj 亦未接。A 站暂不可用/不稳。

**对 A 站综合结论**：

- 现在的 gpt-oss / nemotron（成熟 arch）稳定可用（§8 实测）；**新 hybrid 模型（DeepSeek-V4、GLM-5.3）算子支持未熟，暂不建议上 A 站**（HIP TOP\_K 回落/崩溃、Vulkan indexer/HC 缺失）。

- **若要用 Vulkan 提速，应升级 llama.cpp**（新版 coopmat1/KV-dequant 对 gfx1151 prefill 增益大），而不是守着 /opt ggml 0.22。

### 8.7 llama.cpp Vulkan 升级 + 双模型 A/B（实测 2026.9）

**升级动作**：主控站在线下载 unsloth **b10715-mix-86bd2d3 Linux x64 Vulkan 预编译**（32MB，sha256 `BAD11C3C…`），scp 到 A 解压于 **`/home/scott-lau/llama.cpp-vulkan-b10715/`**（`/opt` 为 root-only 未覆盖）。版本 `0.3.0-dev (build 10715, commit 92cedc867)`，GNU 11.4，自包含 RUNPATH=$ORIGIN，`--device Vulkan0`。烟测：加载 gpt-oss-120b **model loaded**、生成正确。注意：**不含 coopmat1 PR#27952**（未合入 b10715），只含已合入的 #26585/KV-dequant 等。

**双模型实测（unsloth** **`LLAMA_SERVER_PATH=<新 Vulkan>`）**：

| 模型            | 后端                  | TTFT  | 整体 tok/s | decode tok/s |
| ------------- | ------------------- | ----- | -------- | ------------ |
| gpt-oss-120b  | ROCm                | 0.52s | 52.0     | \~53         |
| gpt-oss-120b  | **新 Vulkan b10715** | 3.33s | 50.9     | **58.3**     |
| nemotron A12B | ROCm                | 2.84s | 15.6     | 16.1         |
| nemotron A12B | /opt Vulkan 0.22    | 8.99s | 16.0     | 17.9         |
| nemotron A12B | **新 Vulkan b10715** | 8.93s | 13.9     | 15.3         |

**结论**：

- gpt-oss 在新 Vulkan **decode 略优于 ROCm**（58 vs 53）；nemotron 则新 Vulkan 未超 ROCm/旧 Vulkan。整体与 ROCm 基本打平。

- 期望中的"Vulkan 大幅提速"需 **coopmat1 #27952**（RDNA3/4）那一批——**未进 b10715**，要拿它须该 PR 分支构建（或对应预编译）。

- 新 Vulkan 已可供 `LLAMA_SERVER_PATH` 使用；`/opt` 旧构建保留未动（root-only）。

### 8.8 自建 #27952 coopmat1 Vulkan（实测 2026.9）

**构建**：在 A 站本地 git clone `ggml-org/llama.cpp` 的 PR#27952 head（`965e571`，0cc4m/vulkan-coopmat-int8），`cmake -DGGML_VULKAN=ON` + make（gcc13.3 / glslc 已具备），产物 `/home/scott-lau/llama.cpp-coopmat/build/bin/llama-server`（`0.3.0-dev build 1 commit 965e571` + `libggml-vulkan.so.0.22.0`）。未合入主线的 int8 coopmat RDNA3/4 内核。

**实测（unsloth** **`LLAMA_SERVER_PATH=<coopmat>`）**：

| 模型       | coopmat run1                   | coopmat run2               | 对比 b10715 Vulkan | 对比 ROCm     |
| -------- | ------------------------------ | -------------------------- | ---------------- | ----------- |
| gpt-oss  | overall 53.5 / **decode 64.6** | （未复测）                      | decode 58.3      | decode \~53 |
| nemotron | overall 19.7 / **decode 27.1** | overall 6.0 / decode \~6.0 | decode 15.3      | decode 16.1 |

**关键结论（诚实标注）**：

- **coopmat 能构建、能加载两个模型并生成**，但吞吐**跨 run 剧烈波动（nemotron 27 vs 6 tok/s）**，非同次无意义方差；且输出多次为"泛答"而非规格码。

- 原因指向：**unmerged 实验分支 + int8 coopmat 在 Strix Halo 的 MMQ 路径不稳定**（有的 token/quant 组合走快速路径，有的回落慢速/失败路径）。gpt-oss 单次 decode 64.6 优于 b10715(58.3)/ROCm(53)，**但单样本不足以定论**。

- **现阶段不建议**用 coopmat 作 A 站 Vulkan 默认——b10715（稳定）仍是务实选择；若要 coopmat 的潜在大幅 prefill/decode，需等其合入主线并多轮验证后再评估。

### 8.9 工程收尾（2026.9）：A 默认 Vulkan + B 离线修复

**A 站**：

- 已设 `LLAMA_SERVER_PATH=/home/scott-lau/llama.cpp-vulkan-b10715/llama-server`（写入 ~~/.bashrc+~~/.profile）→ unsloth 默认用新 Vulkan b10715，不再走自身 ROCm 后端。

- **已删除** coopmat 实验版（`~/llama.cpp-coopmat`，674MB）。

**B 站（github 被墙）离线修复**（根因：安装器在 github 拉 llama.cpp 后端 + apt 需 root 无 tty + venv 残缺/回滚致软链悬空）：

- 法门同 A：`LLAMA_SERVER_PATH=/opt/llama.cpp/llama-server`(B 本地 llama) → 跳过 github 后端。

- 补齐 B 残缺 venv（曾是 `unsloth_studio.rollback.*`）：恢复为 `unsloth_studio`、修 `~/.local/bin/unsloth` 悬空软链、`pip install unsloth` + `python-multipart` + `diceware` + 完整 `-r studio/backend/requirements/studio.txt`（PyPI 可达）。

- **实测通过**：`unsloth studio run --model Qwen2.5-7B … --api-only` → `Unsloth Studio running …/Model loaded/API Key 签发/生成返回 OK`，派生的正是 `/opt/llama.cpp/llama-server --device Vulkan0`（未触 github）。B 原 nemotron 8080 服务未受影响。

- 遗留：B 上 unsloth 的自身 llama.cpp 后端仍无（靠 LLAMA\_SERVER\_PATH 用 /opt）；若日后需 unsloth 自带后端，可参照 A 用主控站下载其 prebuilt 转 B。

**B 站切新 Vulkan 后端（2026.9 追加）**：

- **发现 sudo 免密可用**：B 的 `scott-lau` 在 `sudo` 组、`/etc/sudoers.d/scott-lau` 免密（`sudo -n true` OK）；此前卸载失败仅因没用 sudo（polkit 拦 `systemctl stop`）。

- **卸载 2 模型（gpt-oss + nemotron）**：`sudo systemctl stop llama-server@gpt-oss-120b` + `...@nvidia-nemotron-3-super-120b-a12b` → active 单元清空、内存 4G/可用 120G（释放 \~85G）、8080 停。

- **复制 A 新 Vulkan → B**：A→B 直连 scp `/home/scott-lau/llama.cpp-vulkan-b10715`（92M，b10715/commit 92cedc867，自包含）。

- **重指 B unsloth**：`LLAMA_SERVER_PATH=/home/scott-lau/llama.cpp-vulkan-b10715/llama-server`（bashrc+profile）；实测派生的正是该二进位 `--device Vulkan0`。

- 结果：A、B 两端 unsloth 统一用新 Vulkan b10715 后端。

**B 补 ROCm llama（2026.9 追加）**：B 原 `~/.unsloth/llama.cpp` 为空（无 ROCm 后端）→ A→B rsync 全量镜像 A 的 ROCm llama（1.9G，b10715/rocm/gfx1151），验证 `LD_LIBRARY_PATH=.../build/bin` 下 `--version` 正常。至此 B 与 A unsloth 目录一致，同时具备①新 Vulkan（LLAMA\_SERVER\_PATH 指向）②ROCm llama（\~/.unsloth/llama.cpp）。

**agent 会话资源纪律 + 默认模型（2026.9 追加）**：

- **opencode 默认走免费 nemotron**：A `~/.config/opencode/opencode.jsonc` 默认模型 = `opencode/nemotron-3-ultra-free`（免费托管）；仅显式 `-m cluster-local/gpt-oss` 才用本地。

- **claude 与 opencode 不要并发用本地模型**：两者都会占 A 站 124G 统一内存（gpt-oss 59G+）。约定一方走本地 gpt-oss 时另一方走免费模型，避免并发争内存。

- unsloth gpt-oss（A:8080）会话：reasoning\_effort=low（思考最低档开启，未关闭）、context=131072（原生 128k 上限）；OpenAI+Anthropic 通道均可用；unsloth 每次重启会重铸 API key，opencode/claude 需同步更新。

### 8.10 A 站并发容量估算 + ROCm Strix Halo 深度优化（调研 2026.9）

**并发内存估算（gpt-oss-120b + qwen3.8-27B）**：

- 实测：gpt-oss-120b 满配（`-c131072 / parallel4 / load-mode none`）**available=0**（124G 几乎吃满）→ 现状**不能**并排加 27B。

- **条件成立**：gpt-oss 降到 `-c32k + parallel1`（≈63-70G）→ 释放 \~50G → qwen3.8-27B Q4\_K\_M（\~16-18G）**可共存**。

- 注：A 站当前无 qwen3.8-27B 本地模型（待取）。

**社区 ROCm Strix Halo（gfx1151）深度优化版本**：

| 方案                                                  | 内容                                            | 收益（27B 类）                                                                 |
| --------------------------------------------------- | --------------------------------------------- | ------------------------------------------------------------------------- |
| **Luce DFlash/PFlash**（lucebox-hub PR#119）          | DFlash(draft多token)+PFlash，gfx1151 专用         | Qwen3.6-27B decode 12→26.85（2.23×）、16K prefill 61.7→20.2s（3.05×）、E2E 2.5× |
| **llama.cpp MTP 分支**（server-rocm-mtp, experimental） | Multi-Token Prediction                        | 27B +111%、35B +94%、122B +78%                                              |
| **justinappler/llama.cpp-strix-halo** fork          | MMQ tile(RDNA3.5)+MoE tile+FA tile(D=256) 三补丁 | prefill +26.6\~28.8%，decode 持平；16k prefill \~986 tok/s                    |
| **upstream #21284**（未合入）                            | gfx1151 MMQ `mmq_x=48/64,y=64,nwarps=4`       | prefill \~+20%（122B）                                                      |

要点：

- **27B 提速最强**：Luce DFlash（2.2× decode + 3× prefill）+ MTP（+111%）；120B 亦有 MTP +78%、Strix Halo fork prefill +27%。

- **优化提速度、不缩模型** → "同时跑"仍靠内存取舍（首节 gpt-oss 降上下文）。

### 8.11 实测：cache-type-k/v q8\_0（KV 量化 A/B，2026.9）

**动机**：gpt-oss-120b 满配 -c131072/parallel4 时 available≈0（§8.10），考察 **KV 缓存量化**能否在几乎不损失速度的前提下腾出内存，支持并排小模型。

**方法**：同一 gpt-oss-120b-MXFP4 GGUF、同一 Vulkan b10715 后端、同一 `-c131072 / parallel4 / flash-attn on / no-context-shift / kv-unified / device Vulkan0 / reasoning_effort=low`，仅切换 `--cache-type-k/v`：

- **f16**（不指定，对照）：KV est **4.5 GB**

- **q8\_0**（`--cache-type-k q8_0 --cache-type-v q8_0`）：KV est **3.5 GB**（-1GB ≈ **-22%**）

**推理速度 A/B（unsloth API 流式，长输出 \~400 tokens 纯生成）**：

| 指标            | f16 KV     | q8\_0 KV         | 差异          |
| ------------- | ---------- | ---------------- | ----------- |
| KV 大小(est)    | 4.5 GB     | 3.5 GB           | -1GB / -22% |
| long decode   | 43.3 tok/s | 44.3 tok/s       | +2.3%（噪声内）  |
| repeat        | 36.7 tok/s | （仅一轮，受 pkill 中断） | 波动 > 差异     |
| 加载后 available | 55-58G     | 58G              | 相当          |
| 正确性 2+2       | 4（通过）      | 4（通过）            | 一致          |

**结论（诚实标注）**：

- **KV 量化收益有限、速度无伤**：q8\_0 将 KV cache 从 4.5G 压到 3.5G（-22%），decode 速度与 f16 持平（43-44 tok/s 同档，跨 run 波动 ±7 tok/s 大于该差异，非显著差异）。正确性不受影响。

- **对并发放行作用小**：gpt-oss 120B 是 **MoE**，KV 缓存仅占比小头（\~3.5-4.5G），真正大头是 59G 权重 + 统一内存 headroom。省 1G KV 不足以让 q8\_0 解禁并排 27B（仍需 -c32k + parallel1 主动降内存卷）。

- **建议**：A 站 gpt-oss 默认开 `--cache-type-k q8_0 --cache-type-v q8_0` **无开销地嫌小收益**（省内存且速度不降），但**不改变** §8.10 的并发结论。

- **注意事项**：unsloth studio run 的 `--port` 参数**未强制生效**（实测多次自动改为 8085/8086/8087/底层 43xxx），重启后 API 端点和 key 会重铸；CLI/网关需按当日实际 `Unsloth Studio running at…` 与 `API Key` 重指（同 §8.9 末备注）。

- **claude code 直连 unsloth 兼容解法（实测 CLAUDE-STABLE-OK rc=0）**：claude 2.1.233+ 对未知模型 ID 抛 `unrecognized_model` 硬预检，且近年 print-mode 对自定义 BASE_URL 强校验——需**两层**配 `~/.claude/settings.json`：①顶层 `"model"="claude-opus-4-6"`（claude 认识的 Anthropic 名）+ `"modelOverrides":{"claude-opus-4-6/sonnet-4-6/haiku-4-5":"gpt-oss-120b-MXFP4"}`（官方映射机制，key 必须是真 Anthropic 名否则被忽略，v2.1.223 起）→ 消 `unrecognized_model`；②`env.ANTHROPIC_AUTH_TOKEN` 填**真实 unsloth key**（非 dummy）→ 消 `401 Invalid token payload`；`env.ANTHROPIC_BASE_URL=http://127.0.0.1:<port>`。```--model <后端名>``` 或 `ANTHROPIC_CUSTOM_MODEL_OPTION` 等方案均无效（仍被预检拦截）；`ANTHROPIC_DEFAULT_*_MODEL` 需移除避免 openai/ 前缀触发 provider 校验。

