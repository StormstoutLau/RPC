# DwarfStar (ds4) 部署深入调研（2026-09-08）

> **状态**: 官方文档全量核对完成（README / MODELS.md / STRIX_HALO.md / DISTRIBUTED.md / SSD_STREAMING.md / PERFORMANCE.md 原页）
> **关联**: [llama后端盘点与ds4部署方案](llama后端盘点与ds4部署方案_20260908.md) §2/§4 ｜ [FRAMEWORK-SURVEY](../spec/model-eval/FRAMEWORK-SURVEY-2026-09.md) ｜ 上游 [TRACKER](../spec/upstream-tracker/TRACKER.md)
> **落档**: Scott ｜ 2026-09-08

---

## 1. 支持的模型（官方 MODELS.md / README，非全量 GGUF runner ⚠️）

> DwarfStar 只识别其自身的 GGUF 布局/量化混排，任意 GGUF 不保证可加载。**必须用 `download_model.sh` 官方档**。

### 1.1 DeepSeek V4 Flash / PRO

| download 目标 | 大小 | 用途 |
|---|---|---|
| `ds4f-q2` | ~81 GiB | **96/128G 机器首选**；IQ2_XXS gate/up + Q2_K down 路由专家，其余 Q8/F16/F32 |
| `ds4f-q2-q4` | — | Q2 为基础，末尾 6 层路由专家升 Q4（更吃内存） |
| `ds4f-q4` | ≥156G? | 大内存/分布式 |
| `ds4f-mxfp4` | ~156 GiB | **原生 MXFP4 路由专家**（保留 DeepSeek 官方权重不去量化）；大内存/分布式；ROCm 有 resident+PP 路径 |
| `pro-q2-imatrix` | — | PRO 0813，512G 常驻或 SSD streaming |
| `pro-q4-split` / `pro-q4-layers00-30` / `pro-q4-layers31-output` | — | PRO Q4 拆片，双机 PP 各持一半 |

### 1.2 GLM 5.3 Flash / GLM 5.2 / Full GLM 5.3

| download 目标 | 大小 | 用途 |
|---|---|---|
| `glm53-q2` | ~90 GiB | **单 128G 机器**（Mac/DGX Spark/**ROCm Strix Halo 均支持**） |
| `glm53-q4` | ~178 GiB | 大内存 / **双机** / SSD streaming |
| `glm53-fp8` | ~305 GiB | 仅打包原生权重，**推理未实现** ⚠️ |
| `glm53-full-q2` | ~197 GiB | Full GLM 5.3 Q2（需大机器或 `--ssd-streaming`） |
| `glm-antirez-*` / `glm-unsloth-q4` | — | GLM 5.2 全档 |

**GLM 特性**：KDA 线性注意力 + DSA 稀疏 attention + 超连接 + 内置 MTP 块；`--mtp`（无第二模型文件）启用投机解码；**Directional steering 仅 GLM 5.3 支持（5.2 不支持）**；**需 `--power 100`**；不支持 `--prefill-chunk`/外部 `--mtp-model`。

### 1.3 视觉（Vision）

- DeepSeek Flash Vision Exp：`ds4f-vision-q2`（主模型+encoder），`--vision gguf/...-Encoder.gguf`
- GLM 5.3-Flash：`glm53-vision` encoder + `--vision`（文本 GGUF 不变）
- ROCm 支持 PNG/JPEG（CLI / agent / HTTP server）

### 1.4 明确不支持 / 注意

- **MiniMax M3、Qwen 系、Nemotron** 等均不在 ds4 支持表（"deliberately narrow"）→ 集群其他模型仍走 llama.cpp
- GLM 5.2 只支持官方测试过的 4 个 GGUF 档（Q2_K/Q4_K/Q5_K gate·up、Q2-Q6_K down）

---

## 2. 吞吐速度（官方实测）

### 2.1 官方基线（README / PERFORMANCE.md，ds4-bench：Promessi sposi 2048-token 步长 + 128 token 贪心生成）

| 机器 | 后端 | ctx | prefill | generation |
|---|---|---|---|---|
| M5 Max 128G | Metal | 2048/16384/32768/65536 | 790/573/557/399 | 39.4/36.1/34.4/27.6 t/s |
| DGX Spark GB10 128G | CUDA | 2048/16384/32768/65536 | 826/872/856/823 | 18.1/15.1/14.4/13.8 t/s |
| **Strix Halo（ROCm）** | ROCm | — | **官方曲线未在 speed-bench 固化** | 社区同构 19-32 t/s（survey） |

### 2.2 SSD streaming 官方实测（SSD_STREAMING.md，M5 Max 128G，2026-09-06）

| 模型 | 初 prefill | 续 prefill | gen（三回中位数） |
|---|---|---|---|
| GLM 5.3 Flash Q4_K（177.77 GiB） | 121 t/s | 104 t/s | **11.9 / 14.9 t/s** |
| DS Flash Vision Exp MXFP4（145.26 GiB） | 300 t/s | 263 t/s | 11.9 / 19.3 t/s |

> 完全超内存的 Full GLM 5.3（196.58 GiB，8K ctx，61.35 GiB expert cache）：16-token 追加 30.8s→2.9s（cache 命中），生成 4.09→5.11 t/s。

### 2.3 集群相关预期（对照）

- **单站 128G ROCm**：Flash Q2 常驻 —— 社区 Strix Halo ds4 6.7-32 t/s（survey 记录）
- **三站 PP**：每站层切片 —— generation 不因 PP 叠加加速（**PP 为容量+长 prefill 设计，非 decode 加速**，"A single generation stream cannot use that overlap"官方法原文）→ 预期 decode 仍是单站速度（流泪点：**PP 不给 decode 提速**，仅扩容量）
- Flash Q4 ≈151-156G 单站放不下 → 双机/三机 PP（`ds4f-q4`/`ds4f-mxfp4`）

---

## 3. 部署具体步骤（ROCm / Strix Halo 三站）

### 3.0 前提（STRIX_HALO.md 原文）

```
工具链（每站，或走 kyuz0 toolbox 容器 rocm-10.0）:
  apt install hipcc rocminfo rocm-smi libamdhip64-dev libhipblas-dev \
            libhipblaslt-dev librocblas-dev librocwmma-dev libhipcub-dev
  usermod -aG render,video $USER   # 重登生效
  注意: 部分打包 rocWMMA 缺 rocwmma/internal/ → 需自补匹配版本头文件
内核参数（参考）:
  amdgpu.gttsize=126976 ttm.pages_limit=32505856 ttm.page_pool_size=32505856
  ⚠️ 官方不建议仅为复刻他人配置关 IOMMU
构建:
  git clone https://github.com/antirez/ds4
  make strix-halo     # 别名 make rocm
模型:
  ./download_model.sh ds4f-q2        # V4-Flash Q2 (~81G)
  ./download_model.sh glm53-q2       # GLM-5.3-Flash Q2 (~90G)
```

### 3.1 单站验证（先做，C 站 ROCm 就绪）

```sh
./ds4 -m ds4flash.gguf --rocm          # 默认 ROCm
./ds4 -m gguf/GLM-5.3-Flash-Q2.gguf --ctx 32768   # GLM spec
./ds4-agent -m gguf/GLM-5.3-Flash-Q2.gguf --mtp --ctx 50000   # MTP 投机
make test-mxfp4-rocm                   # ROCm MXFP4 路由内核自检
```

### 3.2 三站 PP 切片（官方 DISTRIBUTED.md，Flash Q4 作为大模型例）

```
每站:  ./download_model.sh ds4f-q4        # 或按内存用 glm53-q2 (90G 单站即可)

# 层范围 inclusive；N:output 含末层+输出头
# 例 3 站 Flash Q4（假设 45 层 → A=0:14, B=15:29, C=30:output）

A 站: ./ds4 --role coordinator --layers 0:14 --listen <A环网IP> 9911
B 站: ./ds4 --role worker --layers 15:29 --coordinator <A> 9911
C 站: ./ds4 --role worker --layers 30:output --coordinator <A> 9911
```

**PP 必须注意**：
- 所有 peer **同一 commit**；模型路径/artifact 一致
- worker 注册层范围；中间 worker 直接转发 activation 给下一 stage
- **无需 `--transport rdma`**（PP 用 TCP；RDMA 是双 Mac TP 专用）
- 激活传输默认 32-bit：`--dist-activation-bits 16/8` 减半/更激进（改线上精度，须验证输出）
- `--dist-prefill-window N` 控制 in-flight chunk 数；`--dist-prefill-chunk N` 覆盖 chunk 尺寸
- 断线 worker 使 route 失效 → 协调者可回放保存的 token prefix 重建
- `--debug` 查看 route/per-hop 计时

### 3.3 TP（双机，ROCm 不适用）

> ⚠️ **官方 TP 仅针对两台 Mac（Metal）**；`--transport rdma` 需 active verbs 设备（iogpu.wired_limit_mb=120000）。**集群 Strix Halo + ROCm 无 TP 路径**（TP fork 属 wkljohn 分支，非官方主线能力）。

### 3.4 SSD streaming（模型超内存时，ROCm 支持 GLM 5.2/5.3）

```sh
./ds4 -m gguf/GLM-5.3-Flash-Q2.gguf --ssd-streaming --ctx 4096
# 缓存预算: --ssd-streaming-cache-experts 32GB  (字节预算) 或 4000(动态槽位)
# GLM 默认缓存跨层分给选中专家; --ssd-streaming-full-layers N 保留整层
# 非路由权重与 KV 不计入该预算
```

---

## 4. 环境与参数速查

| 项 | 值/说明 |
|---|---|
| 后端选择 | `--rocm`（Linux AMD 默认）；`make rocm` = `make strix-halo` |
| ctx | Flash 默认；GLM 5.3-Flash Q2 spec 用 `--ctx 32768`；MTB `--ctx 50000` |
| 投机解码 | V4: `--mtp gguf/...DSpark-support-0731.gguf --dspark`（默认置信阈值 CUDA/ROCm=0.7）；GLM: `--mtp`（内置 MTP 块） |
| 质量/复现 | `--quality` / `--dspark-strict` 保持 target-only 解码 |
| GLM 限制 | `--power 100` 必带；无 `--prefill-chunk`；steering 仅 5.3 |
| 内存护栏 | SSD streaming 有自动 budget；**不要**仅因内存不足关内存护栏（非良药） |
| 协议安全 | 分布式网络无认证/加密 → 只在可信网络；peer 同 commit |
| 模型下载 | `--token TOKEN` / `HF_TOKEN` / 本地 HF cache；断点续传 `curl -C -` |
| stop 覆盖 | `ds4_server --stop ...` （SERVER.md） |

---

## 5. 对本集群可行性（更新 §4 结论）

1. **模型定位**：ds4 = **DeepSeek V4 Flash/PRO + GLM 5.3 Flash（+GLM 5.2）专用引擎**；MiniMax/Qwen/Nemotron 等一律不支持 → 与 llama.cpp 互补而非取代。
2. **单站 ROCm**（C 站已具备 HIP）：`ds4f-q2`（81G）常驻可跑，或 `glm53-q2`（90G）常驻 —— 均有官方 ROCm 支持声明；预期 decode 与单站 HIP 实测（gpt-oss 48.8）量级类似，Flash Q2 官方 Metal 39/36 t/s 可作上界参考。
3. **三站 PP**：Flash Q4/MXFP4（151-156G）正合 A+B+C 384G —— **PP 目的=容量与长 prefill 吞吐，非 decode 提速**（官方明示）→ 若追求 decode 高吞吐，三站仍走 llama.cpp RPC（ROCM 容器路线）；ds4 PP 用于"塞进 320B+ 大模型"。
4. **工具链**：三站需 hipcc 等 dev 包（仅 A 现成）→ **kyuz0 toolbox（rocm-10.0 容器）为最低成本路径**（与 llama.cpp RPC 容器路线同源）。
5. **GLM-5.3-Flash 唯一本集群工具**：llama.cpp 主线未合（仍 Open，#27754/27773），**ds4 glm53-q2 是当下唯一本机部署路径**。

## 6. 风险提示

- beta 质量（官方自述 "very fast changing... beta"）；发布前有 QA 但不保证稳定
- PP/TD 网络无加密 → 仅环网可信段
- GLM FP8（305G）**推理未实现**，勿投入
- 混合量化 GGUF 在 ROCm 有 OOM 史（MEMO 单一档规则）→ 只用官方档
- tp fork（wkljohn）GLM 未稳：**主用官方 PP**

## 7. 参考（官方原文件）

- README.md / docs/MODELS.md / docs/STRIX_HALO.md / docs/DISTRIBUTED.md / docs/SSD_STREAMING.md / docs/PERFORMANCE.md / docs/SERVER.md / speed-bench/（antirez/ds4 main, 712 commits）