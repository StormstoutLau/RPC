# AMD 平台算子层优化与 USB4 直连分布式推理调研

> **日期**: 2026-08-28
> **作者**: Scott (鹏)
> **适用系统**: A 站 + B 站 (AMD Ryzen AI Max+ 395 / Strix Halo, Radeon 8060S iGPU gfx1151, 各 128GB 统一内存, Ubuntu, Vulkan/RADV, USB4 RPC 直连)
> **当前状态**: llama.cpp v0.2.0, MiniMax-M2.7 Q4_K_S 双机 RPC ~18.2 t/s (tg128 20.15)
> **调研问题**: ① 当前 AMD 平台是否有算子层面的优化, 开源社区有哪些相关工作; ② 尤其是USB4 直连 + 分布式推理场景
> **关联文档**: 《RPC协议瓶颈调研.md》(协议层)、《DSpark与Flash模型加速框架调研.md》(模型层)、《提速调研报告.md》(总览)
> **v1.1 (2026-08-28)**: 引用审计修正 — **#27554 与 #21344 实为 Closed 未合并(非 Open)**, 跟踪点改为 issue #27553; "差 27 倍" 带宽比系单位错误(实为 ~218 倍); #25356 作者名 ftoleedo; 详见《三调研报告审计.md》

---

## 一、执行摘要

1. **gfx1151 (Strix Halo) 是 llama.cpp Vulkan 算子层优化的当前焦点硬件** — 2026-06 以来至少 5 个针对本芯片的 issue/PR 由社区提交, 全部有实测数据: MUL_MAT_ID prefill 热点 (#21948)、MMV dispatch 断崖 (#25356/#27332)、K-quant mmq tile (#27554)、DSV4 超连接融合算子 (#26578)、ROCm MMQ VGPR (#21344)。
2. **三个 Open PR 值得跟踪, 合并即按 SOP 升级 (v1.1 修正)**: ① #27332 密度门 (MoE batch decode +36%@B9); ② **#27554 大 tile (dense prefill 1.76x) — PR 已 Closed 未合并, 方向由 issue [#27553](https://github.com/ggml-org/llama.cpp/issues/27553) 承接, 等新 PR**; ③ #26578 DSV4_HC 融合 (DeepSeek V4 decode 1.50x, 性能表已逐字核验)。
3. **同硬件双机 USB4 RPC 实测全景已获得** (visorcraft, 与本集群同构: 2×395 + 128GB + USB4 直连 ~9.4 Gbps 有效): 大模型 RPC 的定位是**容量扩展而非速度** — 单机 Vulkan MiniMax-M2.5 Q3 (228.7B) 32.8 t/s vs 双机 RPC Q8 (139B) 15.35 t/s, **两台 395 的 decode 加起来不如一台跑满**, 印证协议层调研"每 token 串行跨层传导"结论。
4. **`-dio` (direct I/O) 是大模型 RPC 的必备参数**: >100GiB 模型 `llama-server` 在 RPC 加载时 hang (llama-bench 正常), issue #19745 + visorcraft + realugbun 三重确认, workaround 就是一个 flag。本集群将来跑 100GB 级模型时必须加上。
5. **传输层天花板仍是 thunderbolt-ibverbs** (~95 Gb/s 双向 / ~7µs, 研究级代码), 但算子层与协议层(前份报告)的收益**不需要动内核, 优先级更高**。
6. **Strix Halo 硬件本身仍有 ~2x 余量** (Luce 自定义 HIP fork: decode 2.23x, prefill 3.05x vs llama.cpp HIP), 但走该路线等于脱离主线版本管理 — 仅作上限参考。

**结论**: 算子层社区工作全部指向 llama.cpp 主线 Vulkan 后端, 无需专用框架; 本集群当前 v0.2.0 已落后于 8 月的 gfx1151 优化 wave (v0.2.0 为 8 月初标签, #27332 8-18 / #27554 8-22 / #26578 更晚), **下一步升级的动机已经从"新特性"变为"同芯片算子修复"**。双机 RPC 继续作为大容量路线 (Q8 无损 / 300B+ 模型), 日常 decode 用单机 Vulkan。

---

## 二、算子层热点图谱 (gfx1151, 社区实测)

token 生成 (decode) 与 prompt 处理 (prefill) 的算子热点完全不同, 且后端 (Vulkan vs ROCm/HIP) 各有强弱:

### 2.1 Prefill 热点: MUL_MAT_ID (MoE 路由专家矩阵乘)

issue [#21948](https://github.com/ggml-org/llama.cpp/issues/21948) (2026-04, 0xSero, **本机同款硬件**):

| 上下文 | MUL_MAT_ID 占 prefill 比例 | 说明 |
|:---|:---|:---|
| KV=512 (batch=512) | **66.2%** | 两形状合计 1124.7ms/step |
| KV=8192 (实用对话) | 57.6% | |
| KV=32768 (长文档) | 41.9% | FLASH_ATTN_EXT 升至 36.4% |
| KV=131072 (128k) | 19.7% | 注意力接管 |

- **关键性质**: MUL_MAT_ID 耗时**与上下文长度无关** (~1050ms 恒定), 纯 batch×expert 数函数 — 上下文越长, 它越被注意力稀释。
- Vulkan vs patched ROCm: pp512 268.89 vs 354.57 t/s (**ROCm +32%**); 但 tg128 23.52 vs 21.00 (**Vulkan 赢 11%**)。
- 已有优化叠加其上: [#15524](https://github.com/ggml-org/llama.cpp/pull/15524) (MUL_MAT_ID subgroup 优化, 已合入, 小 MoE 曾 +100~660%)。

### 2.2 Decode 热点: MMV dispatch 断崖 (多专家 MoE 并发)

issue [#25356](https://github.com/ggml-org/llama.cpp/issues/25356) (2026-07, ftoleedo, **本机同款硬件 + 同款后端 RADV**):

| 并发槽位 B | 1 | 8 | **9** | 16 | 32 |
|:---|:---|:---|:---|:---|:---|
| 聚合 TG (t/s) | 45.4 | 122.5 | **82.9 (断崖)** | 103.8 | 130.9 |

- **根因**: 两个固定阈值在 >8 token 时从 mul_mat_vec (MMV) 切换到 tiled matmul — 为 8 专家 Mixtral 设计的启发式, 对 512 专家/top-10 模型 (Qwen3-Coder-Next) 完全失配: B=12 时 120 draws over 512 experts, 专家重叠≈0, mm-id 无摊销收益纯付 tile 代价。
- **密度门 patch (本地验证)**: B=9 +56%, B=16 +34%, B=32 +20%, B≤8 无回归, temp=0 输出逐字节一致; llama-server 端到端 16 槽位 +41% 聚合。
- **对本集群直接含义**: llama-server 开 `-np` 并发槽位时, **B=9..16 区间是性能陷阱** (当前 master/v0.2.0), 要么 ≤8 要么 ≥24, 直到 #27332 合并。

### 2.3 Decode 热点: 融合算子缺失 (架构新算子)

- **DSV4 超连接** ([#26578](https://github.com/ggml-org/llama.cpp/pull/26578), Open): 未融合的 Sinkhorn comb chain 在 DeepSeek-V4-Flash decode 中占 **32% op 时间 / 每 token ~16k 次 dispatch**; 融合为单 dispatch 后 (寄存器内 20 轮 Sinkhorn, subgroup shuffle), gfx1151 实测 decode 11.16 → **16.77 t/s (+50%)**, prefill +12%。CUDA/Metal 已有对应实现, Vulkan 是最后缺口。
- **KDA/DELTA_NET** (前份报告 #27638): RADV 上 prefill 非线性扩展, 34/45 层 KDA 的 GLM 5.3 Flash 首当其冲。
- **融合 SSM + batched elementwise** (fabiantax fork, 未上游): 264 dispatch/token → 24, +15.5% (Qwen3.5-35B-A3B)。展示同类"dispatch 风暴"问题的通用解法。

### 2.4 后端带宽利用率差距

issue [#24438](https://github.com/ggml-org/llama.cpp/issues/24438) (2026-06, robegan21, 同款硬件):

| 后端 | tg128 (t/s) | 有效带宽 | 占 256GB/s 峰值 |
|:---|:---|:---|:---|
| ROCm/HIP | 33.7 | ~101 GB/s | **~40%** |
| Vulkan | 49.5 | ~149 GB/s | ~58% |

rocprof 显示 HIP 热点在 `mul_mat_vec_q` + `quantize_q8_1` 成对 dispatch (各 45,279 次) — HIP 的 matvec 路径在 gfx1151 上没有吃满 LPDDR5X。这是"Vulkan 赢 decode"的微观解释。

### 2.5 后端选择格局 (同硬件多来源交叉验证)

| 来源 | 结论 |
|:---|:---|
| visorcraft (7 后端横评) | tg: Vulkan AMDVLK 38.65 > RADV 36.80 > ROCm 7.x (+16%); pp: ROCm 7.x nightlies ~502 最高 |
| nabe2030 (HIP vs Vulkan) | 长生成 Vulkan +13~19%; 长 prompt HIP +42~48%; 质量完全一致 |
| realugbun (4 个月迭代后) | 从 ROCm/HIP+自定义 kernel **整体迁回主线 Vulkan/RADV**, "almost everything has changed" |
| ignasivt/strix-halo-guide | "RADV is now faster than ROCm on both pp and tg for MoE models" |

**综合判断**: 本集群坚持 Vulkan/RADV 单栈是对的 (decode 场景赢家 + 维护成本最低); ROCm 仅在"重 prefill 轻生成"的批量场景有 +30~48% 理论空间, 需 kyuz0 toolbox 容器化, 属于按需评估项而非默认项。

*(v1.1 审计注: 上表 visorcraft/realugbun 两行已核验来源; nabe2030 与 ignasivt 引语为二手来源未逐字核验, 且 ignasivt "RADV 在 pp 和 tg 均快于 ROCm" 与 visorcraft 实测 "ROCm 7.x pp 最高(~502)" 相矛盾 — 采信 visorcraft 的实测数据带)*

---

## 三、社区算子 PR 全景 (对本集群的相关性排序)

| PR/Issue | 作者 | 状态 | 算子层内容 | gfx1151 实测收益 | 对本集群 |
|:---|:---|:---|:---|:---|:---|
| [#27332](https://github.com/ggml-org/llama.cpp/pull/27332) | theycallmeloki | **Open** (8-18) | MUL_MAT_VEC_ID 密度门 (替换固定 batch≤8), 9 行改动 | B9 +36%, B16 +27%, B64 +21%; gfx1151/RDNA3/gfx1013 三平台验证 | **高** — llama-server 并发场景直接受益; MiniMax-M2.7 也是多专家 MoE |
| [#27554](https://github.com/ggml-org/llama.cpp/pull/27554) | aic0d3r | **Closed 未合并** (8-22 提交后关闭, v1.1) | K-quant int-mmq 大 tile 128x256@512 threads (RDNA3 iGPU + UMA gate) | pp512 **1.76x**, pp4096 1.75x, tg 不变; dense GEMM 专属, MoE tile 未动 | **中 (v1.1 下调)** — PR 本体已关, 改跟踪承接 issue [#27553](https://github.com/ggml-org/llama.cpp/issues/27553) 等新 PR; 性能数据与无投机回归验证仍有效 |
| [#26578](https://github.com/ggml-org/llama.cpp/pull/26578) | kh0pper | **Open** | DSV4_HC_COMB/PRE/POST 融合 (Vulkan 补齐 CUDA/Metal 缺口) | DeepSeek-V4-Flash decode **1.50x** | **高** — 部署 DS4-Flash 的前置增强; 含 greedy 轨迹敏感性记录 (量化模型固有, 非算子 bug) |
| [#25356](https://github.com/ggml-org/llama.cpp/issues/25356) | ftoleedo | issue (stale) | #27332 的原始报告 + 密度门公式 | 见 2.2 | 已被 #27332 承接 |
| [#21344](https://github.com/ggml-org/llama.cpp/pull/21344) | pedapudi | **Closed 未合并** (v1.1) | ROCm MMQ VGPR tuning (gfx1151) | ROCm prefill +19~35% (数字来自 #21948 作者以此 patch 实测对照) | 低 — 需 ROCm 栈 + 未进主线, 仅作参照 |
| [#27029](https://github.com/ggml-org/llama.cpp/pull/27029) | ubiclouder | Closed (未合并) | RDNA4 (gfx1201) PCI-ID 检测 + mul_mat_id 大 tile + gated_delta pipeline + concat fast-path | R9700 eGPU 验证 | 中 — 思路可借鉴 (subgroup 32/coopmat 检测), 但目标芯片是 RDNA4 不是 gfx1151 |
| [#22105/#25173](https://github.com/ggml-org/llama.cpp/pull/25173) | ruixiang63/wjinxu | **已合入** | DFlash/DSpark 投机解码 (模型层, 见前份报告; v1.1: 1.5~1.9x 为 CUDA 数据, Vulkan 实测无增益) | 1.5~1.9x (CUDA) | 已在 v0.2.0 |
| [#15524](https://github.com/ggml-org/llama.cpp/pull/15524) | — | 已合入 | MUL_MAT_ID subgroup 优化 (non-coopmat) | 小 MoE +100~660% | 已在 v0.2.0 |
| fabiantax fork | fabiantax | 未上游 | 融合 SSM + elementwise mega-kernel | +15.5% | 参考价值 (fork 不引入) |

**观察**: gfx1151 的 Vulkan 算子优化呈"社区众包"格局 — 一人一 PR 一热点, 每个 PR 都带同硬件实测与正确性验证 (test-backend-ops + greedy 输出 diff), 且互相引用形成证据链 (#25356 → #27332; #21948 → #21344/#27554)。**跟踪成本低于自研**: 订阅 3 个 Open PR 即可。

---

## 四、USB4 直连 + 分布式推理: 同硬件实测全景

### 4.1 同构集群基线 (visorcraft/strix-halo-llm-perf, Evo+Beelink 双 395)

与 A/B 集群同构: 2× Ryzen AI MAX+ 395, 128GB/机, USB4/Thunderbolt 直连 (~9.4 Gbps 实测有效带宽), Fedora 43。

**单机 Vulkan (对照)**:

| 模型 | 量化 | 体积 | tg128 |
|:---|:---|:---|:---|
| Qwen3 30B-A3B | Q4_K_M | 17.3GB | **86.1 t/s** |
| GPT-OSS 120B | Q4_K_M | 58.5GB | 53.4 t/s (server) |
| Qwen3-Coder-Next 80B-A3B | Q4_K_M | 45.2GB | 42.7 t/s |
| MiniMax M2.1-REAP 139B | Q4_K_M | 78.4GB | 29.3 t/s |
| **MiniMax M2.5 228.7B** | Q3_K_M | 101.8GB | **32.8 t/s** |
| Qwen3-235B-A22B | Q3_K_M | 104.7GB | 17.2 t/s |

**双机 RPC (关键数据)**:

| 模型 | 分割 | pp512 | tg128 | 备注 |
|:---|:---|---:|---:|:---|
| MiniMax-M2.5-REAP-139B Q8_0 | 1.2/0.8 | 332.36 | **15.35** | 快速 split 扫描最优 |
| Qwen3.5-397B-A17B UD-Q4_K_XL | auto | 147.55 | 11.76 | llama-bench 路径 |
| Qwen3.5-397B-A17B UD-Q4_K_XL | 1/1 + `-dio` | 25.9* | **12.6*** | llama-server 路径 |

**核心对比 — 双机 RPC vs 单机, 同 MiniMax 系模型**:
- 单机 M2.5 Q3 (228.7B): **32.8 t/s**
- 双机 RPC M2.5-REAP Q8 (139B): **15.35 t/s**
- 本集群双机 RPC M2.7 Q4_K_S: **18.2 t/s**

→ **单机 decode 全面碾压双机 RPC** (激活参数相近的模型, 单机快 ~2x)。原因即协议层调研结论: decode 每层串行跨 USB4 (链路 9.4 Gbps ≈ 1.18 GB/s vs 内存 256 GB/s, **差约 218 倍**; v1.1 修正 — 原 "27 倍" 系把 Gbps 数值当 GB/s 相除的单位错误, 修正后结论只会更强), 且每 op 同步往返。**双机 RPC 的正确使用场景是容量**: 397B Q4 (205GB) 这类单机放不下的模型, 11.76~12.6 t/s 但能跑。本集群的 Q8 无损 (162GB) 同理。

### 4.2 大模型 RPC 加载 hang: `-dio` 必备

issue [#19745](https://github.com/ggml-org/llama.cpp/issues/19745) (visorcraft, 同构集群):

- >100GiB 模型 RPC 加载: `llama-bench` 正常 (3-4 min), `llama-server` **无限 hang** at load_tensors (`/health` 503 超 30 min), `llama-cli` HIP/HSA fault 崩溃。
- 46GiB 模型三个工具全部正常 → 大模型 + mmap 路径的 RPC 上传 bug。
- **Workaround: `-dio` (direct I/O) 一个 flag 完全解决**, 138GiB 模型 190-196s 加载完成。
- realugbun (ROCm 路线) 独立确认: "models > ~6 GB hang on load, **required**, not slow, hang"。

**对本集群**: 跑 DS4-Flash Q3 (103GB) 双机方案时**必须**加 `-dio`; 现 MiniMax-M2.7 Q4_K_S (~78GB) 已在临界区之下, 但建议统一加上 (无已知代价)。

### 4.3 算子层与分布式的协同选项

| 选项 | 机制 | 状态 | 评估 |
|:---|:---|:---|:---|
| **`-ot` 张量覆盖** | 正则把指定张量固定到指定后端, 如 `blk\.(0-29)\.=RPC0,exps=CPU` 或反向 | 主线已支持 | **未在本集群 A/B 过** — MoE offload 惯例是"attention/dense/共享专家→快端, 路由专家→大容量端"; 双机场景可试 `attention/dense=Vulkan0, exps=RPC0` (B 站本地算激活部分, A 站容纳米饭部分), 理论上减少每 token 跨链数据量 (激活向量 << 权重) |
| **`-sm row/tensor` 行切分** | 权重按行切到两机 (而非按层), 并行化单算子 | 主线实验性 | row split 每 op 都需跨机 all-reduce — 在 9.4 Gbps USB4 上大概率负收益; layer split (当前默认) 每层只传激活, 已是适配慢链路的最优切法 |
| **RDMA transport** | 握手自动协商 (v0.2.0 已含) | 需 libibverbs | 前份报告已覆盖; 软 RoCE over thunderbolt-net 增益有限 (受 9.4 Gbps 物理限制) |
| **thunderbolt-ibverbs** | 内核模块把 USB4 口模拟成 InfiniBand 设备 | 研究代码 | **~95 Gb/s 双向 / ~7µs 单向延迟** (vs thunderbolt-net 9.4 Gbps); FSDP LoRA step 1359s(Ethernet)→126s; TP 推理 MiniMax-M2.7 已跑通 (前份报告)。工程量大, 与版本化 SOP 冲突, 作为传输层长期选项 |
| **exo 框架** | 拓扑感知自动并行 + TB5 RDMA (Mac/MLX 生态) | 活跃 | Mac 专属后端, 架构参考价值 (拓扑感知分片思路可移植到 llama.cpp 手工 -ts/-ot 配置) |
| **vLLM Ray 集群** | 数据中心路线 | — | 同硬件实测 "EXPERIMENTAL, GATED, DOES NOT CURRENTLY RUN" (前份报告), 排除 |

### 4.4 本集群在全景中的位置

| 维度 | 本集群 (A+B) | visorcraft (Evo+Bee) | 差距/一致 |
|:---|:---|:---|:---|
| 硬件 | 2×395 128GB USB4 直连 | 同 | 完全同构 |
| 有效链路带宽 | ~10 Gb/s 级 (thunderbolt-net) | ~9.4 Gbps 实测 | 一致 |
| 双机 RPC tg (MiniMax 系) | 18.2 t/s (M2.7 Q4_K_S) | 15.35 (M2.5-REAP Q8 139B) / 12.6 (397B Q4) | **本集群更快** (模型更小+quant 更低), 处于合理区间 |
| 单机 Vulkan tg | 未系统基线化 | 86.1 (30B) / 42.7 (80B) / 32.8 (228B) | **盲区: B 站单机基线缺失** — 建议补测, 这是评估"RPC 损失率"的分母 |

### 4.5 单机 Q3 档的三大风险面补充分析 (v1.1 新增, 2026-08-28)

> 触发: 上轮建议 "同级模型 Q3_K_M 单机 ~29-33 t/s" 需核验两个前提 — 量化质量衰减与 KV cache 溢出。以下数字除标注外均已核验。

#### A. KV cache 溢出 — 同硬件实证存在, 但表现为自动降 ctx 而非崩溃

**模型侧规格** (M2.5/M2.7 同家族, 230B.A10B, 62 层, 8 KV heads × 128 dim, 无 MLA):
- issue [#21610](https://github.com/ggml-org/llama.cpp/issues/21610) 日志 — **同硬件 (395+8060S, Windows/Vulkan, M2.5 UD-Q3_K_XL)** 实测:

```
llama_kv_cache: size = 11231.69 MiB (87296 cells, 62 layers), K (q8_0): 5615.84 MiB, V (q8_0): 5615.84 MiB
llama_params_fit_impl: projected to use 121861 MiB vs 108781 MiB of free device memory
llama_params_fit_impl: context size reduced from 196608 to 87296    ← fit 自动裁剪
```

- **每 token KV 开销** (q8_0, 62 层): 11231.69/87296 = **0.129 MiB/token**; f16 翻倍 0.257 MiB/token
- **关键行为**: v0.2.0 时代的 `llama_params_fit` 不再 OOM 崩溃, 而是**自动把 ctx 砍到能塞下的值**(Windows GTT free 106.2GiB → 87k; Linux GTT 120GiB 估 ~90-100k)。溢出的形态从 "crash" 变成 "静默降 ctx" — **必须显式设 -c 才不被动缩水**

**单机 KV 预算表** (Linux, GTT 120GiB, Q3 档 weights ~99GiB, compute buffer ~2GiB, 系统安全垫 ~6GiB):

| KV 类型 | 32k | 64k | 128k | 192k (native) | 判定 |
|:---|:---|:---|:---|:---|:---|
| **q8_0** (`-ctk/-ctv q8_0`) | 4.2 GiB | 8.4 GiB | 16.8 GiB | 25.2 GiB | **64k 安全** / 128k 溢出 |
| f16 (默认) | 8.4 GiB | 16.8 GiB | 33.5 GiB | 50.4 GiB | **64k 即溢出** |

- 结论: **Q3 档单机必须 KV quant q8_0 + ctx ≤64k**; 128k 场景降 IQ2_M (~84GB, 留 20GiB+) 或保持双机 RPC
- 增配: `-np 1`(每槽独立 KV; 开并发则预算除以槽数); RPC 路径另有 RADV 792MB 单张量分配墙(#12, M2.7 特有), 单机 Vulkan 路径无此雷

#### B. 长推理性能衰减 — 三档证据

| 来源 | 数据 | 适用性 |
|:---|:---|:---|
| [#24483](https://github.com/ggml-org/llama.cpp/issues/24483) | **RDNA4 8060S: 50k 上下文 tg -36%** (KV 带宽占 21% + L2 thrash + split_k barrier) | 直接适用 — 本机即 RDNA4 |
| visorcraft | M2.5 Q3_K_M llama-server 长上下文真实使用 **~30 t/s** vs bench 32.8 (仅 -9%) | 同模型同构, 32k 档位衰减温和 |
| snagnever (Mac M4 Max) | >60k 后 swap 压力 → ~0 t/s + 挤死系统服务 | macOS swap 特有, 但提示 Linux 下 KV+weights 贴满 GTT 也会挤压 OS |

综合: **32k 内基本无损 / 50k+ 预期 -10~-36%**; M2.5 家族是 Lightning Attention 混合架构(线性 chunk 内 O(n) + chunk 间 softmax, Vultr 文档), 长上下文衰减理论比纯 softmax 温和, 但 llama.cpp 实现里 62 层全量 KV(#21610 日志), 衰减数据按通用模型预期。

#### C. 量化质量衰减 (Q3 vs Q4) — 修正"Q3_K_M"表述

- [arXiv 2601.14277](https://arxiv.org/abs/2601.14277)(Llama-3.1-8B 统一评测): 3-bit K-quant PPL +1.64 vs F16, downstream 准确率明显损失 — **参考性**(非 MoE 非 MiniMax)
- snagnever 同模型实测: **UD-IQ2_M (dynamic 2-bit) LCB 76% > 标准 Q3_K_S 68%** — importance-matrix 动态量化在同体积下显著优于标准 K-quant
- jmlab (M5 Max): M2.5 Q3_XL rubric 0.98, 与 Q4 的 Nemotron 同档
- 修正: 上轮 "Q3_K_M" 改为 **Unsloth UD-Q3_K_XL (101.8GB, dynamic)** — 质量贴近 Q4, 体积是 Q3 档; 勿用标准 Q3_K_M(更大且质量更差)

#### D. 修正后的单机速度档启动配置

```bash
llama-server -m MiniMax-M2.7-UD-Q3_K_XL.gguf \
  -ngl 99 -fa on -c 65536 \
  -ctk q8_0 -ctv q8_0 \
  -ub 512 -b 2048 --jinja --no-mmap
# 要点: -c 显式 64k(防 fit 静默裁) / KV 必须 q8_0 / --no-mmap 稳驻留
# 128k 需求 → 换 UD-IQ2_M(84GB) 或回双机 RPC
```


---

## 五、行动建议

**阶段 0 — 零成本立即可做 (B 站单机, 1-2 小时)**
1. **补单机 Vulkan 基线**: B 站单机 llama-bench 跑 MiniMax-M2.7 Q4_K_S (同模型同 quant), 与双机 18.2 t/s 对比, 量化 RPC 损失率 (预期单机 ~25-35 t/s)。此后"单机 vs 双机"的选择有数据支撑。**速度档另测 UD-Q3_K_XL (101.8GB): 预期 ~29-33 t/s, 但必须按 4.5 节配置 (q8_0 KV + -c 65536 显式), 否则 fit 静默裁 ctx / f16 KV 直接溢出**。
2. **llama-server 启动参数加 `-dio`**: 防 >100GiB 模型 hang, 一行改动。
3. 并发槽位 (`-np`) 避开 B=9..16 断崖区 (#25356), 用 ≤8 或 ≥24, 直到 #27332 合并。

**阶段 1 — 跟踪三个方向 (被动, 零工作量; v1.1 更新跟踪点)**
4. GitHub watch [#27332](https://github.com/ggml-org/llama.cpp/pull/27332) (密度门) / [#26578](https://github.com/ggml-org/llama.cpp/pull/26578) (DSV4_HC 融合) / **issue [#27553](https://github.com/ggml-org/llama.cpp/issues/27553)** (mmq 大 tile — 原 PR #27554 已关闭, 等新 PR)。任一合并 → 按 UPGRADE_SOP 升级 (RUNPATH patch 流程复用)。三个都落地时, 预期 decode +20~50% (MoE 并发) / prefill +50~76% (dense) — 视负载构成。

**阶段 2 — 双机 RPC 的算子-放置协同实验 (与 DS4-Flash 部署联动)**
5. `-ot` A/B 实验: 对照默认 layer split vs `exps` 定向放置 (路由专家→A 站, attention/dense/共享专家→B 站本地 Vulkan)。MoE offload 社区惯例在 CPU-GPU 混合上已验证, 双 GPU RPC 变体无公开数据 — **本集群可产出社区级空白数据** (strix-halo-guide #12 正在征集 RPC 基准)。
6. DS4-Flash 双机方案 (前份报告阶段 2) 全部带 `-dio`。

**阶段 3 — 中长期选项 (维持前份报告结论)**
7. thunderbolt-ibverbs: 传输层 10 倍改善 (9.4→95 Gb/s), 但内核模块 + 研究级代码, 仅在"双机 decode 需求刚性"时启动。
8. ROCm 双栈 (kyuz0 toolbox): 仅当出现重 prefill 批量场景 (文档摘要/代码库索引) 时按需启用, 预期 +30~48% pp。
9. Luce 路线 (自定义 HIP fork, decode 2.23x 上限证明): 维持"性能天花板参考"定位, 不引入。

---

## 六、参考来源

1. [llama.cpp issue #21948 — Vulkan MUL_MAT_ID dominant prefill bottleneck on gfx1151](https://github.com/ggml-org/llama.cpp/issues/21948)
2. [llama.cpp issue #25356 — Vulkan batched decode cliff at n_tokens=9 (MMV dispatch)](https://github.com/ggml-org/llama.cpp/issues/25356)
3. [llama.cpp PR #27332 — vulkan: use density gate for MUL_MAT_VEC_ID path](https://github.com/ggml-org/llama.cpp/pull/27332)
4. [llama.cpp PR #27554 — vulkan: double the K-quant int-mmq large tile on RDNA3 iGPUs](https://github.com/ggml-org/llama.cpp/pull/27554)
5. [llama.cpp PR #26578 — vulkan: DeepSeek-V4 hyper-connection fused ops](https://github.com/ggml-org/llama.cpp/pull/26578)
6. [llama.cpp PR #21344 — gfx1151 nwarps/tile VGPR tuning (ROCm MMQ)](https://github.com/ggml-org/llama.cpp/pull/21344)
7. [llama.cpp PR #27029 — AMD RDNA4 eGPU fork (closed, 含 RDNA4 检测与 tile 思路)](https://github.com/ggml-org/llama.cpp/pull/27029)
8. [llama.cpp PR #15524 — MUL_MAT_ID subgroup optimization (已合入)](https://github.com/ggml-org/llama.cpp/pull/15524)
9. [llama.cpp issue #24438 — ROCm/HIP 只达 40% 内存带宽 (gfx1151)](https://github.com/ggml-org/llama.cpp/issues/24438)
10. [visorcraft/strix-halo-llm-perf — 同构双机 USB4 RPC 实测库](https://github.com/visorcraft/strix-halo-llm-perf)
11. [llama.cpp issue #19745 — 大模型 RPC 加载 hang 与 -dio workaround](https://github.com/ggml-org/llama.cpp/issues/19745)
12. [nabe2030/hip-vs-vulkan-evo-x2 — HIP vs Vulkan 工作负载交叉研究](https://github.com/nabe2030/hip-vs-vulkan-evo-x2)
13. [llama.cpp discussion #20856 — Known-Good Strix Halo ROCm stack (4 个月迭代, 迁回 Vulkan)](https://github.com/ggml-org/llama.cpp/discussions/20856)
14. [kyuz0/amd-strix-halo-toolboxes — Strix Halo 容器化栈 (含 RDMA 支持)](https://github.com/kyuz0/amd-strix-halo-toolboxes)
15. [strixhalo.wiki — Clustering / Clustering with RDMA](https://strixhalo.wiki/AI/Clustering)
16. [Geek Salad — Thunderbolt-ibverbs: We Have InfiniBand At Home (95 Gb/s / 7µs)](https://geeksalad.org/thunderbolt-ibverbs-we-have-infiniband-at-home/)
17. [fabiantax fork — Vulkan Strix Halo optimizations (fused SSM, +15.5%)](https://github.com/fabiantax/llama.cpp/pull/1)
18. [Doctor-Shotgun — llama.cpp MoE offload 指南 (-ot 惯例)](https://hugging-face.cn/blog/Doctor-Shotgun/llamacpp-moe-offload-guide)
19. [molayo1419 — Luce DFlash/PFlash on Strix Halo (decode 2.23x vs llama.cpp HIP)](https://molayo1419.me/insights/amd-strix-halo%EC%97%90%EC%84%9C%EC%9D%98-luce-dflash-pflash-llama-cpp-hip-%EB%8C%80%EB%B9%84-qwen3-4t1tet)
20. [exo — Mac 生态拓扑感知分布式推理 (架构参考)](https://github.com/exo-explore/exo)
