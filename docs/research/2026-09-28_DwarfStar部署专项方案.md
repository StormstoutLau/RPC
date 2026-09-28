# DwarfStar (ds4) 集群部署专项方案

> **日期**: 2026-09-28
> **触发**: 用户要求「给出本框架部署 DwarfStar 的具体方案，结合当前集群现状、管理方式、社区信息，综合分析，避免环境污染」。
> **性质**: 规划文档（**未执行**）；所有"现状"来自既有文档（E1/E2），外部技术用 E3 标注；任何"该不该上"的结论都留给 ADR-0004 立项裁决。
> **关联**: 承 `O-112`/`O-113`（REAP/V4.1 部署）、`EV-3`（vLLM 换栈）、`EV-4`（第二栈生命周期）、`ADR-0004`（唯一管理面）、`FRAMEWORK-SURVEY §3`（ds4 详情，本方案的动作落地）。
> **执行记录**: ★ 本方案的执行与实测落档在 [DwarfStar 前置核验与 ROCm 工具链安装决策](./2026-09-28_DwarfStar前置核验与ROCm工具链安装决策.md)（前置核验 / 工具链安装与回退 / 构建 / 官方 ROCm 10.0 目标版本发现 / ROCm 依赖核验与风险 / 容器评估 / **原生 ROCm 10.0 落地与 P-0 冒烟** / **GLM 档位与双机 PP 前置**）。
> **立项**: ★ 已交 [ADR-0010](../../adr/ADR-0010-DwarfStar第二引擎引入立项.md) —— **v1.2 裁决 accepted（2026-09-28 深夜）：由「试点立项」降为「观察保留」**。v1.1 的「单机为唯一可交付形态」仅作**冷藏能力**保留；**不再投入**（依据：llama.cpp 经共存变体 + 双机 RPC 已跑 GLM-5.3-Flash **11.2–11.9 t/s**，ds4 单机仅 0.41–0.44 t/s，慢 27×；★ **双机 PP 被实测推翻并冻结**，已报上游 `antirez/ds4#1141`）。

---

## 0. 方案最高约束（"避免环境污染"的三条铁律）

| # | 铁律 | 依据 | 本方案落实 |
|---|---|---|---|
| ① | **零自加载**：引擎不自启，每次断掉须运维拉起；看门狗 timer 除外 | 手册 §1.1「开机状态 = 零自加载」 | ds4 走**手动进程**形态，不装任何 supervisor / 开机自启 / systemd 单元 |
| ② | **唯一管理面**：所有管理操作从 `ops/cluster.py` 走，禁止并列入口 | ADR-0004 D1/D3/D4 | ★★ **本次最关键**：ds4 的起停/探活**并入 `cluster.py` 子命令**（如 `cluster.py infer-load --backend ds4`），**不在 `ops/` 新增一次性脚本** |
| ③ | **临时验证件放 `tmp/`**，不入库 | ADR-0004 D3 情形④ | 一切探针/一次性验证写 `tmp/`（gitignore 覆盖），**不占用 `ops/`** |

---

## 1. 复用既有前例，而不是发明新形态

★ **集群已跑过"第二引擎"且有成熟范式** —— **vLLM 便携构建 `~/vllm-rocm`**（手册 §1.1 L31）：

- **位置**：`/home/scott-lau/vllm-rocm`（**用户目录、非 /opt**）= 独立 venv（`bin/python3.14`）
- **分发**：`vllm-rocm-gfx1151.part0X.tar.gz` 分卷 + md5 校验 + USB4 转发（存档 `a4_*.sh`）
- **生命周期**：**手动进程 + 零自加载**（无 systemd）；C 站尤其明确「端点半托管 = 手动进程，非 systemd 单元」
- **治理**：已被 `infer-load` 的 pkill 兜底覆盖（`infer-load` 管理手动引擎）

⇒ **ds4 完全照这套范式落地**，只是引擎二进制的来源不同（`make strix-halo` 本地构建 vs 分卷 tar 分发）。

**为什么这能避免污染**：ds4 只落 `~/`（用户域）不动 `/opt`（llama.cpp 域）、不动端口表（§6）、不动加载绕组（§5），与现役 llama.cpp 完全隔离。

---

## 1.5 ★★ 能力边界清查（2026-09-28 只读核验，E3 官方文档）

> **为什么先做这项**：它决定"方案在该模型/该硬件上是否成立"。
> **来源**：ds4 官方 `README.md` / `docs/MODELS.md` / `docs/DISTRIBUTED.md` / `docs/STRIX_HALO.md`（gh 原页直取，E3）。

### 核心结论（★ 直接修正本方案此前一个错误假设）

| 模型 | ROCm（gfx1151 可用）？ | 分布式模式 | 结论 |
|---|---|---|---|
| **DS V4-Flash** | ✅（`make strix-halo` + `--rocm`） | ⚠ TP 需 Metal/CUDA（**ROCm 被拒**）· **PP**（层切片）可用 | ✅ 集群可行（PP）|
| **GLM-5.3-Flash** | ✅（ROCm 支持）| ★★ **双机 PP 层切片**（`glm53-q4` **177.8 GiB**）—— **TP 在 ROCm 被拒**（见下注）| ✅ 集群可行（PP）|
| **DS V4.1-Flash** | ❌❌ **ROCm 未实现**（官方 MODELS.md 原话："DSpark, **pipeline execution and ROCm** are not implemented for V4.1"）| ❌ **无 PP** | ★● **gfx1151 上不可用**（仅 Metal + CUDA text）；★ 例外：社区 fork 为 V4.1 开了 ROCm **TP**（见 §7.3 旁证）|

> ★★ **2026-09-28 源码核验修正（E1，见 [执行记录 §12.2](./2026-09-28_DwarfStar前置核验与ROCm工具链安装决策.md)）**：ds4 源码 `ds4.c:72484` 明写 **`"tensor parallelism requires the Metal backend"`**（受 `#ifndef DS4_HAS_DEEPSEEK41_GPU` 约束）⇒ **ROCm 上 TP 不可用**；而 **PP（`--layers`）可用**（源码文案 `"distributed layer slices can run fully resident"`，`ds4.c:70887`）。⇒ 原写「双机 RESIDENT TP」**不成立**，**双机主线改为 PP**。

★★★ **最大发现：V4.1 在我们集群（gfx1151 ROCm）上不可用** —— ds4 官方对 V4.1 只实现 Metal / CUDA(text) 两条后端，**ROCm 与 pipeline 都未实现**。⇒ ★ **本方案此前的"V4.1 Q4 三机 PP"假设不成立**；V4.1 只能靠 Metal（本集群无）或 CUDA（非 gfx1151）⇒ **V4.1 走 ds4 在本集群 = 不成立，应从 ds4 目标清单移除**（V4.1 若要在本集群跑，得回到 llama.cpp `#28696` / vLLM 路线，见 `O-113`）。

### 逐项实证（E3 原话摘录）

**README（顶层）**：「*Supported hardware*：Metal（primary）· **NVIDIA CUDA**（DGX Spark 主目标）· **ROCm** on Strix Halo / Framework Desktop」；并称「用两个 128GB Mac 连 RDMA，可 TP 跑 4-bit Flash 或 GLM 5.3 Flash」。

**MODELS.md（量化 + 支持边界）**：
- `glm53-q4`（178G）· `glm53-q2`（90G）· `glm53-fp8`（305G，**inference 未实现**）⇒ GLM-5.3-Flash **Q4/Q2 都有现成档**。
- `ds4f-q2`（81G）· `ds4f-q2-q4` · `ds4f-q4` · `ds4f-mxfp4` ⇒ V4-Flash 档位齐全。
- ★ 「**DSpark, pipeline execution and ROCm are not implemented for V4.1**」—— V4.1 后端边界，白纸黑字。
- ★ V4.1 文件：`ds41f-q2`（**341G** gguf / 152G main weights）+ `ds41f-q4`（**483G** / 294G）⇒ 即使能跑也是大文件。

**DISTRIBUTED.md（分布式）**：
- **两种模式**：TP（拆 experts/层，双机 decode 分摊）/ **PP**（`--layers` 层区间，多机 sum RAM 跑大模型）。
- ★ PP = **TCP transport**（非 RDMA 必需）· `--layers 0:19` / `20:output` 手工分区 · 激活 32-bit（可降 16/8）。
- **glm53-q4 明确支持双机 TP**（2×128GB **Mac** 例子）—— ⚠ **该例是 Mac(Metal)**；★★ **ROCm 上 TP 被源码拒绝**（`ds4.c:72484`），**ROCm 双机只能用 PP**（见 §1.5 注）。
- ★ `download_model.sh pro-q4-split`（PRO Q4 拆片）只有 Mac Studio 512GB 沿 —— 与本集群无关。

**STRIX_HALO.md（ROCm 构建）**：
- `make strix-halo` + `./download_model.sh ds4f-q2` + `./ds4 --rocm` = **V4-Flash ROCm 官方路径**。
- GLM 5.3 Flash ROCm = SSD streaming 路径（`--ssd-streaming` + small ctx）。
- 内核参数 = `amdgpu.gttsize=126976 ...`（照抄 STRIX_HALO，但 §4.1 已证本集群 120000 够用、非强制）。

### 对本方案的净结论

1. ★ **ds4 在本集群（gfx1151 ROCm）真正能承担的 = V4-Flash 与 GLM-5.3-Flash**，不是 V4.1。
2. ★ **V4.1 从本方案的目标清单剔除**（ROCm 不可用）；它回归 llama.cpp `#28696` / vLLM 路线（`O-113`）。
3. **GLM-5.3-Flash 才是 ds4 在本集群的相对 llama.cpp 增益点**（llama 跑不了 `glm5next`；ds4 ROCm + Q4/Q2 现成 + 双机 **PP** 可用（★ TP 在 ROCm 被拒，见上注））⇒ **分布式主线应聚焦 GLM-5.3-Flash**。
4. V4-Flash 本集群 llama.cpp 已在跑（tg 6.3）⇒ ds4 对它是"换引擎实测对照"（P-4 背靠背），非必要。

---

## 2. 目录/二进制布局（用户域隔离，零污染）

```
/home/scott-lau/
├── ds4/                        # 源码 + 构建（git clone antirez/ds4）
│   ├── Makefile
│   └── ./ds4 ./ds4-server ./ds4-agent   # make strix-halo 产物
├── ds4-models/                 # 项目专属 GGUF（与 llama.cpp 模型库完全分开）
│   ├── v4.1-q2.gguf           # 或 download_model.sh ds4f-q2 现成档
│   └── glm53-q4.gguf
├── ds4-gguf-tools/             # gguf-tools（含 deepseek41_quantize.py，仅本地转换用）
└── vllm-rocm/                  # ★ 既有（本方案不碰）
```

**三条隔离原则**：
1. **不落 `/opt`**（那是 llama.cpp MANIFEST 域）—— 避免与现有引擎版本/MANIFEST/升级 SOP 纠缠。
2. **GGUF 分目录** `ds4-models/` 独立 —— 不污染 `models.yaml` 的 llama.cpp 模型库，避免 `infer-list`/`models` 误扫。
3. **构建在用户侧**，用官方 `make strix-halo`（含 ICU 内嵌 KFD 检查），不覆盖 li系统 ROCm，不动 `/opt/llama.cpp`。

---

## 3. 构建步骤（社区标准 + 集群对齐）

> 来自 FRAMEWORK-SURVEY §3.2（E3，社区/p0）合并本集群事实。

```bash
# 1. 前置依赖（ROCm 用户态）
sudo apt-get install hipcc rocminfo rocm-smi libamdhip64-dev libhipblas-dev \
  libhipblaslt-dev librocblas-dev librocwmma-dev libhipcub-dev
#   ⚠ 可能需手动补 rocWMMA internal headers（Ubuntu 包缺失，FRAMEWORK-SURVEY §3.2 注明）

# 2. 内核参数（关键，与 llama.cpp 差异不大）：
#    典型参考： amd_iommu=off amdgpu.gttsize=126976 ttm.pages_limit=32505856 ttm.page_pool_size=32505856
#    ⚠ 但本集群 gttsize=120000 已是 AMD 官方值（§4.1），ds4 官方不强制 126976；
#     是否改见 §4.1 —— 大概率不改，且要改须脚本化+可回退。

# 3. 构建
cd ~/ds4 && make strix-halo -j$(nproc)

# 4. 下载/转换 V4.1 GGUF（项目专属）
./download_model.sh ds4f-q2          # 官方现成档（推荐，避免自转换坑）
# 或：python3 gguf-tools/deepseek41_quantize.py --hf models/DeepSeek-V4.1-Flash ...  # 本地转换（自建，成本高）
```

★ **优先级的排序（2026-09-28 用户纠正后修订）**：
- ★★ **第一优先级 = 分布式（双机/三机 PP），跑 llama.cpp 双/三机【跑不了 / 跑不快】的模型**（GLM-5.3-Flash 320B、V4.1 552B 等）—— 这是 ds4 相对 llama.cpp RPC 的**本质增益**。
- **第二优先级 = 单机、合适量化**（Q4 而非 Q2），用于**目标模型的快速落点验证**。
- **Q2（~80G）单机压缩换装下 = 退路 / 兜底档**，不是起点，**不该提前**。

> ★ 依据：用户指出「当前尝试使用 DwarfStar 是为了获取**前沿模型推理能力**，特别是**双机/三机能跑大参数模型的分布式推理**，尤其是 **llama 分布式架构当前跑不了、跑不快的模型**；Q2 这种压缩过高换取单机可跑的方式**优先级不应该提前**」。
>
> 结合 ds4 实际：它的分布式 = **ROCm PP 层切片**（coordinator + workers，`kyuz0 ds4-toolbox`），顶的能力正是 llama.cpp RPC 当前**没有的**（GLM-5.3-Flash `glm5next` 未合入 → RPC 跑不了；V4.1 CED 未合入 → 跑不了）。PP 解决的是"**178G+ 放不进单机**"的容量问题（FRAMEWORK-SURVEY H.2 原话），**不是 decode 加速**。

**档位建议**（★ 依 §1.5 能力边界修正：ds4 在本集群能跑 V4-Flash / GLM-5.3-Flash，**不包含 V4.1**）：
- **D-目标（分布式主线）**：**GLM-5.3-Flash Q4（177.8 GiB，★ 双机 **PP 层切片** —— TP 在 ROCm 被拒，见 §1.5 注）** —— 这是验证"llama.cpp 跑不了（`glm5next` 未合入）的模型，ds4 分布式能否在本集群跑起来"的**唯一真正目标**。
- **P-落地（单机支线）**：GLM-5.3-Flash Q2（~90G）单机，用于**快速验证架构/算子无缺陷**（V4-Flash **不再作单机候选**——§7.1 已证无速度优势，仅保留在 P-4 作为引擎对照项）。
- ⚠ `ds4f-q2`（~80G）**仅作 P-0 冒烟**（确认 `make strix-halo` + ds4-server 能起来），不把 Q2 当部署目标。
- ★ **V4.1 不在 ds4 目标内**（ROCm 未实现，§1.5）—— 若要在本集群跑 V4.1，走 llama.cpp `#28696` / vLLM 路线（`O-113`），**不是 ds4**。
- ★★ **Step 5 Preview / Mimo / Inkling 等其它前沿模型不在 ds4 支持面**（§7.2 已核）—— 若要跑，走 llama.cpp 通用路线，**不是 ds4**。

**★★ 特殊量化格式依赖（用户 2026-09-28 指出，必须注明）**：
- ds4 是**项目专属 GGUF、非通用加载器** ⇒ 它的"Q2/Q4"**不是** llama.cpp 的通用 `Q2_K`/`Q4_K_M`，而是 **ds4 特制的混合量化布局**（如 asymmetric / 路由专家压缩 + 共享/关键路径保精度；社区实测档位如 `IQ2_XXS ~80.8G`、`Hybrid Q2/Q4 ~97G` 等）。
- ⇒ **任何"单机 Q4" 的前提 = 该模型的 ds4 专属 Q4 档（或能本地用 `gguf-tools` 转换）已经存在**。llama.cpp 能单机跑 MiniMax-M2.7 / Qwen3.8-Flash-Next / V4-Flash，恰好因为那些是 llama.cpp 的 GGUF；**ds4 路线要跑 GLM / DeepSeek，必须落到 ds4 的 own 格式**。
- ★ **这是 P-1（单机 Q4）的前置依赖**：部署前须核 ds4 官方/社区是否已提供 目标模型 × 目标档位 的专属 GGUF；本地用 `deepseek41_quantize.py` 自转的成本高（§3 已标），且 `V4 template 不兼容`、`V4.1 须专属转换`。
- ⚠ 更贴近一个判断：既然"单机 Q4 专用档"本身是非平凡依赖，**分布式 PP 反而是绕开它的更稳路径**（双/三机可负担更大、更接近原始精度的档位）—— 这**再次支撑了【分布式为主线】的排序**。

---

## 4. 前置核验（★ 全未做，部署前必须逐项确认）

| 项 | 现状| 需确认 | 风险 |
|---|---|---|---|
| **ROCm 版本** | C 站 7.2.x（FRAMEWORK-SURVEY 提过） | ds4 `make strix-halo` 需要的最低 ROCm；`rocminfo` gfx1151 + KFD 可用 | 版本过低则构建/运行失败 |
| ★★ **内核参数 gttsize** | **本集群 = `120000`（AMD 官方 trillion-cluster 同值）** | ★ **ds4 官方并不强制 126976**（见 §4.1 专项） | ⚠ **大概率不需要改**；若改须按 §4.1 脚本化 + 可回退 |
| **磁盘空间** | ★ **已核（2026-09-28 只读 df）**：A 可用 **676G** / B **958G** / C **1.2T** | ✓ 足够：GLM-5.3 Q4 `glm53-q4`（178G）· V4-Flash Q4（~100G）任意单机都放得下；V4.1（341G Q2/483G Q4）也能落盘（虽 ROCm 不可用，§1.5）| 低 |
| ★★ **专属量化格式可用性** | ★ **已核（§1.5，E3）：目标模型现成档已有** —— GLM-5.3-Flash `glm53-q4`(178G)/`glm53-q2`(90G) · V4-Flash `ds4f-q4`/`ds4f-q2`(81G)；V4.1 `ds41f-q2`(341G)/`ds41f-q4`(483G) 存在但 ROCm 不可用 | ✓ 目标（V4/GLM-5.3）**有现成 ds4 专属 GGUF**，无需本地自转；★ 自转（`gguf-tools`）仅当要自定义档位时 | 低（现成档已够）|
| **端口** | 见 §6 | ds4-server 用哪个端口、不冲撞现役 | 端口表 |
| **KFD / 内存账本** | load-gate / load-mem-gate 已就位 | ds4 加载是否与 `wait-gtt-release` / `backup-memories` 兼容 | 双引擎并存的内存竞争（O-18 铁律） |

### 4.1 ★★ 内核参数专项：可脚本化、可回退、且大概率不用改

**回答用户问题「内核参数问题是否可以脚本控制且可回退」= 是，且分三层：**

| 层 | 机制 | 能否脚本化 | 能否回退 |
|---|---|---|---|
| gttsize / pages_limit / iommu | `/etc/default/grub` 的 `GRUB_CMDLINE_LINUX_DEFAULT`（**纯文本**）→ `sudo update-grub` → `reboot` | ✅（sed/编辑文本 + update-grub） | ✅（**备份原 grub 文件 → 还原 → update-grub → reboot**）|
| 内核版本锁定 | GRUB 子菜单索引法（`GRUB_DEFAULT="1>4"`）| ✅ 已固化（手册 L1161-1163）| ✅ 已固化（有回退）|
| BIOS carveout | UMA Frame Buffer | ❌ 仅 BIOS 手动 | ❌（需进 BIOS）|

**★ 关键澄清（本方案此前抄了过时结论，现修正）**：

1. **本集群 gttsize=`120000` 是正确的、与后端无关**（`.trae/documents/三机群文档升级` L12 取样证：GTT 是内核 amdgpu 驱动"系统内存→GPU 地址空间映射池"上限，**Vulkan/ROCm 后端共用同一池**；A/B/C 三站实测一致 120000 + ttm.pages_limit 30720000/32000000）。
2. ★ **仓库记忆中 `gttsize=126976` 那条已被标记为"过时错误条目"**（源于 GMKtec EVO-X2 / lemonade #2631，非本集群）。
3. ★ **ds4 官方 `docs/STRIX_HALO.md` 原文（E3，2026-09-28 取）**：126976 是 "a system-specific starting point, **not an allocation budget** for DwarfStar"，且要求 **"Preserve existing boot options ... Keep RAM available for the OS"**，并警告 **"Do not disable the IOMMU merely to copy another host's configuration"**。

⇒ **结论**：
- **不一定需要改 gttsize**。本集群 120000 已在 AMD 官方值域；是否调成 126976（多 ~6.8G GPU 可见）只取决于 **ds4 V4.1 Q2 + 上下文**是否真缺这 6.8G。
- **若 decide 要调**，按 §4.1 的"备份 grub → 改 → update-grub → reboot → 验证 → 需回退则还原 grub → update-grub → reboot"，**完全脚本化且可回退**，不碰 BIOS。
- **更优先的做法**：先**不改任何内核参数**跑 ds4 V4.1 Q2 单机冒烟（起点用官方现成档）。只有确认"GPU 可见内存不足"才动 grub —— 把"改内核"从**前置**降级为**按需触发**，进一步缩小对现役 llama.cpp 的干扰面。

---

## 5. 与统一管理面的集成（★ 避免污染的难点）

ds4 是**独立引擎** = 撞 ADR-0004「第二管理面」。**不是"加个载荷进 `infer-load`"就完事，而是要先走 EV-4 的"谁管生命周期"裁决**。本方案给出**最小、不污染**的集成路径：

### 5.1 只读探活先于任何写入
- `cluster.py status` 增加对 `~/ds4/ds4-server` 进程/端口的**只读探测**（不启动、不停止）—— 属于 D1 的观测能力，天然合规。
- 判据：`ds4-server` 进程存在 + 端口 LISTEN ⇒ 报 `ds4: RUNNING`；否则 `ds4: STOPPED`（只读，不 FAIL）。

### 5.2 起停走 infer-load 扩展（须立项）
- 沿用 vLLM 已被 `infer-load` 管理的先例（手册 L214"`infer-load` 的 pkill 兜底可管理手动引擎"）。
- **提案**：`infer-load` / `infer-unload` 扩展 `--backend ds4`，用它 start/stop `~/ds4/ds4-server -m ... --ctx N`。
- ⚠ **这本身是 ADR-0004 D1 的一项新增子命令能力 → 必须立项**（EV-4 裁决），**不是**靠临时脚本。

### 5.3 明确：不新增并列入口
- **禁止**另写 `ds4-start.sh` / `ds4-health.sh` 放 `ops/`（会被 `scripts` 断言 FAIL）。
- **禁止**装 ds4 自带容器/cockpit 的开机自启（`kyuz0/ds4-toolbox` 若用，仅作一次性构建产物，不做常驻）。

---

## 6. 端口分配（避免与现役冲突）

| 现役端口 | 引擎 | 本方案 |
|---|---|---|
| `:8080` | llama-server（Vulkan/RPC）| **不占用** |
| `:50052` | RPC server | **不占用** |
| `:8000` | vLLM（TP=2）| **不占用** |
| ★ **新: `:9911`**（ds4 官方 PP/TP 默认分布式端口）| ds4 分布式（coordinator/worker）| 待核 `inventory/ports.yaml` 后登记；ds4 单机 server 可用另一未占用段 |

⚠ **部署前必读 [inventory/ports.yaml](file:///d:/RPC/inventory/ports.yaml)** 确认无冲突段；ds4 分布式走官方 `--listen <ip> 9911 --transport tcp`（§1.5 DISTRIBUTED.md），端口 9911 须登记；ds4-server 若单机用，另占一个未占用段。

---

## 7. 社区 / 上游信息（部署决策输入，E3）

| 来源 | 信息 | 对本期的影响 |
|---|---|---|
| dwarfstar.sh 官网 | ds4 已支持 **V4 / V4.1 / GLM 5.x / Qwen3.8**；Metal/CUDA/ROCm 全后端；MIT | ★ 选型可行 |
| HN（9 天前） | antirez 已落地 **V4.1 重度量化** commit（M5 128G SSD 流式）| 确认 V4.1 本地运行有先例 |
| `gguf-tools/deepseek41_quantize.py` | **V4 template 不兼容**，V4.1 须专属转换 | ⚠ 若自转换，成本高 → **优先用官方现成档** |
| wkljohn TP fork | ds4 ROCm TP + OdinLink，双机 V4 Q4 decode 19.1 t/s | 进阶选项（本方案先不做 TP，先单机/PP） |
| jarvis-ai 实测 | 双 Strix Halo TB5 19-20 t/s | 性能上限参照 |
| kyuz0 ds4-toolbox | 预编译 ROCm 10.0 容器 | 备选：**仅用于构建**，不常驻 |

⚠ **所有性能数字均为 E3（别家/社区实测），未在本集群复现**；部署后的 bench 是本方案的验收点（§8）。

### 7.1 ★★ 双机 V4-Flash 速度对照：ds4 vs 现役 llama（2026-09-28 补调研，E3 + E1 现役）

> **缘起**：用户要求补核「DwarfStar 双机跑 V4-Flash 的速度，与现役双机 llama（算子融合后 **~17 t/s**）对比」。

| 方案 | 机型/链路 | decode t/s | 来源 / 证据 |
|---|---|---|---|
| **llama.cpp 双机 RPC（现役，算子融合后）** | Strix Halo ×2 · USB4 | **14.02**（9/10）· **14.06**（9/28 复核） | **E1 本集群实测**（[metrics-log Phase 6](../../spec/rpc-optimization/metrics-log.md)；★ **原表写「~17 / E1 本集群实测」有误，2026-09-28 更正** —— ~17 实为上游 PR #26578 的**单机**数字 11.16→16.77，E3）|
| ds4 双机 TP（RDMA/TB5）| 双 MacBook | **16.8** | PyShine 2026-08 · E3 |
| ds4 双机 TP fork | Strix Halo ×2 · **OdinLink** | **19.1** | wkljohn · E3 |
| ds4 双机（实测） | Strix Halo ×2 · **TB5** | **19-20** | jarvis-ai · E3 |
| ds4 单机 ROCm **gfx1151**（本集群同硬件）| Strix Halo ×1 | **12.5**（ROCm 尚早期）· prefill 122 | prismix 表 · E3 |
| ds4 单机 Metal | M5 Max 128GB · q2 | **39.4**(2k) / 27.6(65k) | dwarfstar.sh · E3 |
| ds4 双机 CUDA（非本集群）| RTX 6000 Blackawell ×2 | **31.7-35.8**（IQ2XXS）| loftllc · E3（异硬件，仅作带宽相关性参照）|

**结论（全部为判断，不给概率）**：

1. ★★ **更正后不再说"持平"**：llama 双机**本集群 E1 = 14.02（9/10）/ 14.06（9/28 复核）t/s**（上表原误写 ~17，已更正）。而 ds4 的 16.8 / 19.1 / 19–20 **全部是 E3（别家硬件与链路）** ⇒ **两者不可直接比较**（量化档、链路、上下文、引擎版本都不同）⇒ **"谁更快"必须靠 P-4 背靠背实测**，本方案**不给结论**。唯一同环境内的可用对照：ds4 **单机** ROCm-gfx1151 = 12.5（E3 · prismix），**低于**本集群 llama 双机 14.06（E1）。
2. ★★ **ds4 在 ROCm-gfx1151（本集群同硬件）是短板而非长板**：官方 ds4 单机仅 **12.5 t/s**（ROCm "still early"），**低于**同表 llama.cpp Vulkan 的 18.33（prismix）⇒ **直接推高 P-4「ds4 vs llama RPC 背靠背」的预期：ds4 未必能超 llama**，只作对照数据。
3. ★ **ds4 双机 19-20 t/s 依赖 TB5 / OdinLink 高速链路**；本集群是 **USB4 40Gbps + 官方/社区 TP** ⇒ **链路带宽是 TP 的关键变量，本集群未必能复现 19**。⚠ 需在 P-3 实测时分出「容量收益 vs 速度收益」。
4. ⇒ **对 V4-Flash，ds4 的价值不是"更快"，而是"能跑 llama 跑不了的架构"（GLM-5.3 `glm5next` /**V4.1 CED**，P-3）**；P-4 的速度对照用于给「换引擎值不值」的判据喂数据，**不背书 ds4 更快**。

### 7.2 ★★ DwarfStar 支持面清查：除 GLM 外，本集群其它前沿模型能否走 ds4（2026-09-28 补调研，E3 → E4 判断）

> **缘起**：确认 DwarfStar 重点落在 GLM-5.3-Flash 分布式后，需核「对**本集群能跑的前沿模型**（如 Step 5 Preview / Mimo / Inkling / MiniMax / Qwen3.8 等）的 ds4 支持度」—— 因为 ds4 是**窄引擎，不是通用 GGUF 加载器**。

**★ 首要事实（E3，ds4 官方 README 直接声明）**：「This implementation only works with the DeepSeek V4 and GLM GGUFs listed below. Young but **not a general GGUF loader** —— arbitrary GGUFs will not have the **tensor layout / quantization mix / metadata / optional MTP state** expected by the engine」⇒ **ds4 只认项目自己产的 `download_model.sh` 现成档**，不接受社区任意 GGUF（§3/§140 的特殊量化依赖即此）。

**ds4 官方支持清单（E3，codekk 镜像 / README）**：
- **DeepSeek**：V4-Flash（primary）· V4.1-Flash（★ **Metal + 仅 CUDA-text**，ROCm/pipeline 未实现，§1.5）· **V4-PRO**（高内存 512GB，本集群 128GB 不适用）。
- **GLM**：GLM 5.2 · **GLM 5.3** · **GLM 5.3-Flash**（★ ROCm 可用 ⇒ 本集群唯一「非 DeepSeek」增益点）。
- **Qwen**：**Qwen3.8-Flash-Next**（★ **Metal + CUDA**，**未见 ROCm** ⇒ gfx1151 大概率不可用，E4）。

**用户点名的模型逐项核（E3/E4）**：

| 模型 | ds4 官方支持？ | 对本集群（gfx1151 ROCm）| 结论 |
|---|---|---|---|
| **GLM-5.3-Flash** | ✅（ROCm） | ✅ 双机 **PP**（★ TP 被拒）| ★ 唯一真正的 ds4 重点 |
| **V4-Flash** | ✅（ROCm） | ✅ 但无速度优势（§7.1）| 仅 P-4 对照 |
| **V4.1-Flash** | ⚠ Metal/CUDA-text only | ❌ ROCm 未实现 | 非 ds4 路线（O-113）|
| **Qwen3.8-Flash-Next** | ✅（Metal/CUDA）| ⚠ 未见 ROCm ⇒ E4 大概率不可用 | 待实测核（次要）|
| **Step 5 Preview** | ❌ 未见支持 | ❌ | 走 llama.cpp 通用路线 |
| **Mimo（V2.5）** | ❌ 未见支持 | ❌ | 走 llama.cpp 通用路线 |
| **Inkling** | ❌ 未见支持 | ❌ | 走 llama.cpp 通用路线 |
| **MiniMax-M2.7** | ❌（antirez 博文仅提及"128GB 2-bit class 里众多模型之一"，并未实现）| ❌ | 走 llama.cpp 通用路线 |

**对本方案的净结论**：
1. **DwarfStar 对本集群的价值 = 唯一集中在 GLM-5.3-Flash 分布式**（ROCm 可用 + llama 跑不了 `glm5next` + 现成 Q4/Q2 档位）。这与 §7.1「V4-Flash 无速度优势」互为印证 ⇒ **GLM-5.3-Flash 分布式是 P-3 且为唯一主线**。
2. **Step 5 Preview / Mimo / Inkling / MiniMax 等前沿模型，ds4 都不支持** —— 它们要么走 llama.cpp（若已有 GGUF / 架构已合入），要么等社区出 ds4 专属转换（成本高、无保证）。**这些不构成 ds4 的加分项**。
3. **Qwen3.8-Flash-Next** 是仅存的不确定项（Metal/CUDA 支持、未见 ROCm）⇒ 标记为**次要、待实测核**，不进入本期主线。
4. ⚠ **证据边界**：Step 5/Mimo/Inkling/MiniMax 的「不支持」多数为 **E4（未见支持证据推断）**，非官方明确排除；若后续要追踪，以 ds4 官方 `download_model.sh` 脚本更新为准。

---

## 8. 验收判据（做到才算闭环）

| 阶段 | 判据 |
|---|---|
| **P-0 冒烟** | `make strix-halo` 无 warning；`./ds4 -p "hi"` + **一条** `ds4-server` 起停跑通（用官方现成档，**非 Q2 部署目标**，仅验证引擎活着）|
| **P-1 架构落点（单机支线）** | Q4 单机跑目标模型，`cluster.py status` 报 `ds4: RUNNING` · 只读探活正常 · Q4 而非 Q2，验证算子/架构在 gfx1151 无缺失 |
| **P-2 隔离** | 门禁 `scripts` 断言无新增未登记脚本；`/opt` 未被触碰（`md5sum` 与基线一致）；端口表无冲撞 |
| ★★ **P-3 分布式主线（本方案核心）** | ★ **GLM-5.3-Flash Q4（177.8 GiB）双机 **PP 层切片**（`--role`/`--layers`；★ TP 在 ROCm 被拒，见 §1.5 注）** 由 `infer-load --backend ds4` 拉起 —— **验证"llama.cpp RPC 跑不了（`glm5next` 未合入）的模型，ds4 分布式能跑起来"**；记录 prefill / decode / 是否稳定 |
| ★★ **P-4 对照** | ★ 用**现成 gold 夹具**跑确定性输出，且**在每档（单机 Q4 / 分布式 TP/PP）各跑一遍**作对照（不采信厂商声明）；对"llama 能跑但慢的模型"（V4-Flash），**ds4 vs llama RPC 同模型同档位背靠背**给加速比 |
| **P-5 决策** | 产出「引入 vs 不引入」证据束，交 ADR-0004 立项裁决（重点 = 分布式能力是否补上了 llama 的短板，而非单机压缩）|

---

## 9. 不做的边界（必须写下来）

- **不自动升级**：不并入 UPGRADE_SOP 的 llama.cpp 升级链（ds4 是独立引擎，独立演进）。
- **不并行运行时叠加**：试点期间**不同时跑 ds4 与现役大模型**（同机内存竞争 + O-18 带宽铁律）。
- **不承诺 TT**：不推断"部署要多久"（用户偏好：不给时间估计）。
- **不全量迁移**：即便 P-5 通过，也只是「第二栈可用」，**llama.cpp 仍为主路线**（FRAMEWORK-SURVEY 结论不变）。
- **未做**：本方案**未实际执行任何一步**；前置核验（§4）全未做；本次只落文档。

---

## 10. 一句话执行序

> ① **核 EV-4 / ADR-0004**（"谁管生命周期"立项）→ ② **前置核验**（ROCm 版本 + gttsize + 磁盘 + 端口）→ ③ 用户域 `~/ds4` 构建（`make strix-halo`）+ **P-0 冒烟**（官方现成档验证引擎活着）→ ④ 只读探活并入 `cluster.py status` → ⑤ **P-1 单机 Q4 落点**（快速验证架构）→ ★★ ⑥ **P-3 分布式主线：GLM-5.3-Flash Q4 双机 PP / V4.1 Q4 三机 PP**（真正目标 = 跑 llama 跑不了/跑不快的模型）→ ⑦ **P-4 gold 夹具每档对照** → ⑧ **P-5 证据束，交 ADR 裁决**（重点 = 分布式是否补上 llama 短板）→ ⑨ 不通过即"裁不迁"（O-113/O-112 闭环）。★ **Q2 仅在容量极限时才作为兜底，不提前**。

**核心**：**复用 vLLM 便携构建的"用户域 + 手动进程 + 并入唯一管理面"范式**，ds4 只活在自己的 `~/ds4` 与独占端口里，不碰 `/opt`、不装自启、不进 `ops/` 临时脚本 —— 这就是"避免环境污染"的全部含义。