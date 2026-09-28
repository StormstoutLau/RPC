# DwarfStar (ds4) 前置核验与 ROCm 工具链安装决策（2026-09-28）

> **性质**: 执行记录 + 决策分析（承 [DwarfStar 部署专项方案](./2026-09-28_DwarfStar部署专项方案.md)、收口于 [ADR-0010](../../adr/ADR-0010-DwarfStar第二引擎引入立项.md)）。覆盖：前置核验 → ROCm 工具链**安装决策与故障回退** → 工具链**补全与首次构建** → ds4 **官方目标版本发现** → ROCm 依赖**核验与 10.0 风险评估** → 容器**性能评估与运行时现状** → **原生 ROCm 10.0 落地与 P-0 冒烟** → **GLM 档位与双机 PP 前置核验** → **格式兼容性与性能/质量核验** → **下载入口与 C 站双机准备**。
> **证据约定**: E1 = 本站实测；E2 = 前会话留档；E3 = 外部文档（官方/社区）；E4 = 推断。
> **状态**: ★ **B 站 P-0「引擎活着」已达成，并已交 ADR-0010 立项（2026-09-28）** —— 原生 ROCm 10.0 装好（与 7.2.4 双隔离、现役零影响）+ ds4 构建成功（1 行上游补丁）+ `ds4`/`ds4-server` 可执行；**双机能力经源码核验修正为 PP（非 TP）**；**格式核验：ds4 用专用 GGUF，A 站 Unsloth 档不可用**；**吞吐/质量官方不覆盖本硬件 ⇒ 待自测**。★★ **新增（§14）：GLM Q4 下载中（走 `lm-download@`，ETA ~47min）+ C 站已配好（ROCm 10.0 + ds4 构建）+ B↔C USB4 直连确认**。[教训与回退见 §6；工具链补全与构建见 §7；官方目标版本见 §8；ROCm 依赖核验与 10.0 风险见 §9；容器评估见 §10；原生 10.0 落地与 P-0 见 §11；GLM 档位与双机 PP 前置见 §12；格式兼容性与性能/质量见 §13；**下载入口与 C 站准备见 §14**]。

---

> ★ **文档边界（2026-09-28 整理；同日二次剥离）**: 本文主题 = **DwarfStar (ds4) 的核验、部署与裁决** —— 即 **§1–§16**（前置核验 / ROCm 工具链安装决策与回退 / 工具链补全与构建 / 官方目标版本 / 依赖核验 / 容器评估 / 原生 10.0 落地 / **双机 PP 起跑与崩溃根因** · `antirez/ds4#1141`）+ **§18.1**（ds4 ROCm TP 源码门禁）+ **§20.3 存废结论** + **§21 存量盘点与裁决**。
> ★★ **GLM 与 DeepSeek 的内容已于 2026-09-28 分别剥离归档**：
> 　· **GLM 家族** → [GLM 系列本地推理部署](./2026-09-28_GLM系列本地推理部署.md) —— 原 §17 / §18.2 / §18.3 / §19 / §20.1 / §20.2 已迁出，落在其**正文（§4–§9）+ 附录 A**；
> 　· **DeepSeek V4 家族 / V4.1 / Zrald** → [DeepSeek V4 系列调研与部署](./2026-09-28_DeepSeek-V4系列调研与部署.md) —— 原 §20.4 / §20.5 / §22 已迁出，落在其 **第三部 §6 / §7**。
> 　⇒ **这两主题的新变更一律更新那两份文档，勿在此处追加**；本文对应小节**只留指针 + 一行结论**。
> ⚠ **§12 / §13 / §14 / §16 留在本文**：它们的**主题是 ds4 的双机 PP 前置与实施**（GLM-5.3-Flash 在其中只作为**被测对象**出现）⇒ 归 ds4 一侧。
> 全部研究文档索引见 [docs/research/README.md](./README.md)。

## 1. 前置核验（P-0 I，E1 三站实测）

### 1.1 核验项汇总（全部只读）

| 项 | A (192.168.1.33) | B (192.168.1.32) | C (192.168.1.37) | 结论 |
|---|---|---|---|---|
| OS / 内核 | 6.17.0-40 | 6.17.0-23 | 6.17.0-23 | 三站有内核漂移（既有记录，非本次引入）|
| 磁盘可用 | 676G (62%) | 958G (45%) | 1.2T (34%) | ✅ GLM-5.3-Flash Q4(178G) 任意机可放 |
| gttsize | 120000 | 120000 | 120000(+iommu=off) | ✅ AMD 官方值，**不改内核** |
| ttm.pages_limit | 30720000 | 30720000 | 32000000 | ✅ 范围内 |
| ROCm runtime | ✅ /opt/rocm-7.2.4 | ✅ | ✅ | llama.cpp 现役在用 |
| KFD | ✅ gfx1151 | ✅ | ✅ | ds4 硬件就绪 |
| kfd read/write | ✅ | ✅ | ✅ | 三站实测可读写 |
| user ∈ render | ✅ 992 | ✅ 992 | ✅ 992 | ✅ |
| user ∈ video | ✅ 44 | ❌ **缺 44** | ✅ 44 | ⚠ B 缺 video；但 kfd R/W 已 ok ⇒ 非阻塞 |
| 端口 9911 | 空闲 | 空闲 | 空闲 | ✅ 无冲撞（ds4 分布式官方端口）|
| ds4/glm 残留 | 无 | 无 | 无 | ✅ 零污染起点 |
| **hipcc 编译链** | ❌ 缺 | ❌ 缺 | ❌ 缺 | ⚠ **唯一阻塞** |

### 1.2 前置核验结论

- 除 **hipcc 编译工具链缺失** 外，三站全部就绪。KFD/gfx1151/ROCm runtime/磁盘/端口/无残留 全部 PASS。
- **hipcc 缺失根因**：三站此前按 [ROCm 三站统一 7.2.4 报告](./2026-09-17_ROCm三站统一7.2.4_总结报告.md) 的 **D3 决策**只装 `rocm-hip-runtime`（有意不装 SDK，`hipcc` 属 `rocm-hip-sdk` 待评估未装）。
- ds4 `make strix-halo` **硬依赖 hipcc**（[官方 Makefile](https://raw.githubusercontent.com/antirez/ds4/main/Makefile) L54：`HIPCC ?= command -v hipcc || echo /opt/rocm/bin/hipcc`，两路径三站均不存在）。

---

## 2. 官方构建依赖核对（E3）

ds4 官方 `docs/STRIX_HALO.md`（native Ubuntu 构建）preres 原文：

```sh
sudo apt-get install -y hipcc rocminfo rocm-smi \
  libamdhip64-dev libhipblas-dev libhipblaslt-dev librocblas-dev \
  librocwmma-dev libhipcub-dev
sudo usermod -aG render,video "$USER"
```

关键点：
1. 官方列的正是 **hipcc + 6 个 HIP/dev 库**（hipblas/hipblaslt/rocblas/rocwmma/hipcub/amdhip64），**无 SDK meta** —— 「精确 6+1」思路与官方一致。
2. 官方注明 **Ubuntu 26.04**。**包名是否为 26.04 专属是本次落档的核心差异点（见 §4）**。
3. 官方要求 `usermod -aG render,video`。三站已具 render（kfd 可写），B 站缺 video 但 kfd 实测可写 ⇒ 非阻塞，可选补。

---

## 3. 官方 26.04 vs 本地 noble(24.04) 包可用性差异（E1 + E3 交叉）

> ⚠ **核心风险**：官方 26.04 的裸包名（`libhipblas-dev` 等）在 noble 下**不会全部解析到 rocm 7.2.4 源**。B 站实测：

### 3.1 官方裸名 在 noble 的解析结果（B 站 `LANG=C apt-cache policy`）

| 官方 26.04 包名 | noble 解析候选版本 | 归属源 | 判定 |
|---|---|---|---|
| `hipcc` | **`1.1.1.70204`** | ✅ rocm 7.2.4 | 正确 |
| `libamdhip64-dev` | `5.7.1-3` | ⚠ **Ubuntu 官方源**（旧 5.7）| 版本错 |
| `libhipblas-dev` | `5.5.1-4` | ⚠ **Ubuntu 官方源**（旧 5.5）| 版本错 |
| `librocblas-dev` | `5.5.1+dfsg-5` | ⚠ **Ubuntu 官方源**（旧）| 版本错 |
| `libhipcub-dev` | `5.7.1-3build1` | ⚠ **Ubuntu 官方源**（旧）| 版本错 |
| **`libhipblaslt-dev`** | **不可得（Ubuntu 源无）** | ❌ | 需 variant |
| **`librocwmma-dev`** | **不可得（Ubuntu 源无）** | ❌ | 需 variant |
| `rocm-smi` | `5.7.0-1` | ⚠ Ubuntu 源（旧）| 版本漂移 |

### 3.2 差异结论

- 官方 26.04 写法**只有 `hipcc` 真正拿到 7.2.4**；其余 `lib*` 名被 **Ubuntu noble 官方源抢先解析到 5.5/5.7 旧版**（不需要的旧 ROCm 库）⇒ **照抄官方裸名 = 在 noble 装错版本，污染且浪费**。
- `libhipblaslt-dev` / `librocwmma-dev` 在 Ubuntu noble 源**根本不存在** ⇒ 必须用 rocm 7.2.4 源里的**带版本 variant**：`hipblaslt-dev7.2.4` / `rocwmma-dev7.2.4`。
- ⚠ **locale 陷阱复发**：首版脚本用 `awk '/Candidate/'`，但 zh locale 下 apt-cache 输出「候选」⇒ 全判「不可得」（**假阴性**）。修正：`LANG=C apt-cache policy`。此即记忆/TRACKER 反复记的「解析命令输出必须锁 locale」（`md5sum -c` `free` 同源教训）。

---

## 4. 安装方式分析：SDK meta vs 精确 7.2.4 variant

### 4.1 两案 dry-run 实测（B 站）

| 维度 | `rocm-hip-sdk` meta | 精确 `*7.2.4` variant |
|---|---|---|
| 新装包数 | **57** | **30** |
| hipcc | ✅ 7.2.4 | ✅ 7.2.4 |
| hipblaslt / rocwmma | ✅ 7.2.4 | ✅ 7.2.4 |
| **无关库拖带** | hipfft/hipfft-dev、hipsolver(+dev)、hipsparse(+dev)、hipsparselt(+dev)、hiptensor(+dev)、hiprand、rocalution(+dev)、rocfft(+dev)、rccl(+dev)、hipfort-dev 等 **20+ 无关 ROCm 库** | **无**（仅 ds4 需要的 HIP/GEMM 库 + 必要依赖）|
| 版本正确性 | ✅（meta 锁 7.2.4 族）| ✅（显式 pin 7.2.4）|
| 缺点 | 污染面大、卸载回收面大 | 需逐包知道 variant 名（已核清）|

### 4.2 卸载回退干净度（用户问「meta 是否更干净」—— 结论：否）

- 两种方式装的都是 **apt 自动安装依赖**，卸载都走 `apt purge <pkg> && apt autoremove --purge` 回收 ⇒ **机制相同**。
- 干净度差异由「**装了几个包 + 是否被现有软件反向依赖**」决定，不因「meta vs 明细」而异。
- **meta(57 包) 卸载面更大**：多 20+ 个与 ds4 无关的 ROCm 库需逐一判定回收，合规失败时**更多无关残留**。
- **精确 variant(30 包) 卸载面更小**：只装 ds4 需要的 + 依赖，卸载 `purge` + `autoremove` 更聚焦。
- **反向依赖核验（E1）**：30 包中的 hipcc 会被 `rocm-dev/rocm-hip/hip-dev` 反向依赖——但这些是 meta 才装的，精确方式不装，故精确方式的 hipcc 无残余反依赖；rocblas/hipblaslt7.2.4 的反向依赖全在 7.2.4 族内（自洽，autoremove 可清）。
- **回退基线（E1）**：`rocm-hip-sdk`/`hipcc`/`hipblaslt7.2.4`/`rocwmma-dev7.2.4` 当前**全部未装** ⇒ 卸载回退 = 净零污染起点。

### 4.3 裁定

> **选用「精确 7.2.4 variant（30 包）」**，理由：① 与官方 STRIX_HALO 依赖面一致（无 SDK meta 无关库）；② noble 版本正确；③ **卸载回退更干净**（30 vs 57 面）；④ 最小污染（D 核验零污染起点）。在 **B 站试点**。

---

## 5. B 站试点：安装清单

> ⚠ **§5.1 的「精确 7.2.4 variant」方案已在 B 站实地尝试但失败并回退**（见 §6 故障记录）。本节命令保留作为「失败方法」记录，**不再按此执行**。

### 5.1 拟定安装命令（精确 7.2.4 variant，30 包）【已证不可行 §6】

```bash
sudo apt-get update
sudo apt-get install -y \
  hipcc \
  libamdhip64-dev \
  hipblas-dev7.2.4 hipblaslt-dev7.2.4 rocblas-dev7.2.4 \
  rocwmma-dev7.2.4 hipcub-dev7.2.4
# 依赖自动拉入: comgr7.2.4 hip-runtime-amd7.2.4 hsa-rocr7.2.4 rocm-core7.2.4
#   rocminfo7.2.4 rocprim-dev7.2.4 rocsolver/rocsparse/roctracer(7.2.4) 等
# 可选: 官方还列 rocm-smi (诊断, 非构建必需, noble 解析到 5.7 旧版 ⇒ 暂不装, 规避旧库)
# 可选: sudo usermod -aG video scott-lau  (B 站缺 video 组, 但 kfd 已可写 ⇒ 非阻塞, 暂缓)
```

### 5.2 安装前基线记录（回退锚点）

- `/opt/rocm` → `/opt/rocm-7.2.4` 现状（未动）。
- 现役推理 bundled 库 `RUNPATH=$ORIGIN`（TRACKER 记录）—— 装 hipcc/dev 到系统 `/opt/rocm` 后**必须跑 `ldd` 遮蔽自证**确认不遮蔽现役 llama.cpp。
- `inventory/ports.yaml` / 门禁 `scripts` 基线。

### 5.3 安装后验收（P-0 II）

1. `which hipcc` 命中 + `hipcc --version` 正常。
2. 现役 llama.cpp 未遮蔽：`ldd` 对系统新增 `libhipblaslt.so`/`librocblas.so` 的遮蔽自证 PASS。
3. 三站隔离：系统 `/opt/rocm` 变化不影响 `~/.unsloth` bundled。
4. → 进入方案 **P-0 冒烟**：`git clone antirez/ds4` → `make strix-halo` → `./download_model.sh ds4f-q2` → `./ds4-server` 起停。

---

## 6. B 站执行故障记录与回退（2026-09-28 实地，E1）

> **结论先行**：安装「精确 7.2.4 variant」在 B 站**失败**，已**完整回退**到安装前状态，现役 llama/Runtime 零受损。根因 = **variant 包(带 `7.2.4` 后缀)与既有 non-variant runtime 包混装冲突**。

### 6.1 故障现象（time-ordered）

| 步骤 | 动作 | 结果 |
|---|---|---|
| 1 | `apt install -y hipcc libamdhip64-dev hipblas-dev7.2.4 hipblaslt-dev7.2.4 rocblas-dev7.2.4 rocwmma-dev7.2.4 hipcub-dev7.2.4` | **失败**：dpkg error code 1；`rocm-core7.2.4`/`comgr7.2.4`/`hsa-rocr7.2.4`/`rocminfo7.2.4`/`hip-runtime-amd7.2.4` 等 core variant **半配置(in)** |
| 2 | 状态盘点 | `hipcc`=ii（装了但不在 PATH；因依赖 variant 未配置）；**variant 库全 iU**(unpacked未configure)；core variant 全 in |
| 3 | 影响评估 | **现役 llama 零受损**：ldd 全命中 bundled `~/.unsloth/.../build/bin/`；既有 runtime(rocm-core/hsa-rocr/rocm-hip-runtime/rocminfo/comgr) 全 ii 7.2.4 |
| 4 | 用户裁定 | **回退到安装前** |
| 5 | `apt remove --purge` variant+dev | 被依赖阻塞：`libamdhip64-5` Depends `libamd-comgr2`(被移除) ⇒ 拒绝 |
| 6 | `dpkg --remove --force-remove-reinstreq <半配置包>` + `dpkg --configure -a` | ✅ 半配置包归 0，variant 归 0，运行时完整性 ✓，ldd 遮蔽 ✓ |

### 6.2 根因（E1 推断 + 已实证）

- **variant 包（`*7.2.4`）是 ROCm「多版本并存」专用的路径隔离变体**（装 `/opt/rocm-7.2.4`），**与已装的 non-variant `rocm-core`/`hsa-rocr` 等概念冲突**：两者都要注册同一批 core 文件/路径 ⇒ dpkg 配置阶段互相覆盖 → 半配置。
- **`hipcc` 之所以「装了却不在 PATH」**：hipcc 正确落在 `/opt/rocm-7.2.4/bin/hipcc`，但因依赖的 core variant 未配置完，链接到 PATH 的 alternatives/符号缺失。
- **§4 的「精确 variant 卸载更干净」判断失误**：只比较了包数量(30 vs 57)，**没考虑到「variant 与既有 runtime 混装」这一前提本身不成立**。

### 6.3 关键替代线索（下一步方向，未执行）

- **`/opt/rocm-7.2.4/bin/hipcc` 实际一直在系统里**（`dpkg -S` 属 `hipcc` 包，物理存在 249KB，ldd 全通），只是**普通用户 PATH 不含 `/opt/rocm-7.2.4/bin`**。
- **更干净的路径（未验证）**：① 不装 variant，改为 **PATH/alternatives 直接指向已存在的 `/opt/rocm-7.2.4/bin/hipcc`**；② 或装 **non-variant 裸名**（让 apt 从 rocm.list 7.2.4 拿，而非 Ubuntu 旧源——但需处理 §3 的 Ubuntu 旧包遮蔽）；③ 或用官方推荐的 **container/toolbox**（`kyuz0/strix-halo-ds4-toolbox`，彻底隔离，零污染最稳妥）。

### 6.4 用户裁定（2026-09-28）：走路径① PATH/alternatives

> ✅ **用户裁定**：先落档，再尝试 **路径① PATH/alternatives 直接指向既有 hipcc**（零包安装、最干净，不触 variant/runtime 冲突）。
> **尝试计划**：① 确认 `/opt/rocm-7.2.4/bin/hipcc` 可独立运行（`hipcc --version`）→ ② 用它测试 ds4 的 `.mk`/`Makefile` 是否认（`HIPCC=/opt/rocm-7.2.4/bin/hipcc make strix-halo` 或 exports PATH）→ ③ 若可行，则**无需任何 apt 安装**，避免了一切 variant/runtime 冲突。
> **验证点**：① `hipcc --version` 正常且报 7.2.4；② 用 hipcc 能实际编译/驱动 ds4 Makefile 的 rocm 目标（这是真判据，非"装上了"）；③ 现役 llama 仍零受损。
> **威胁/回退**：若 hipcc 依赖的某些 dev 库（hipblaslt/rocwmma headers）其实缺失，会编译报错 → 此时才回到路径②或③，且无环境污染（纯读/测试，零写）。

### 6.5 路径①实测细化 + 修正（2026-09-28）

> **路径① 实测**：`/opt/rocm-7.2.4/bin/hipcc` 二进制可跑（`--version` 出 clang 编译器信息、`hipconfig` 报 `HIP_PATH=/opt/rocm-7.2.4`），**但缺 HIP 头文件**：
> - ⚠ `hipcc --version` 报 Warning：`HIP version file: /opt/rocm-7.2.4/share/hip/version 未找到`（HIP version 为空）；
> - ⚠ **`/opt/rocm-7.2.4/include/hip/hip_runtime.h` 不存在**；`include/` 下只有 `amd_comgr`/`rocm-core`/`rocprofiler-register` 三个目录。
> - 说明：09-17 的 `rocm-hip-runtime` **只含可跑运行库，不含 HIP dev 头文件**（无法编译 HIP 代码）。`hipcc 在但不完整`。
> - ✅ 全盘另有 `/usr/include/hip/hip_runtime.h`（**Ubuntu 官方 5.x 世代**，与 7.2.4 不一致）。

> **修正解法（已被用户接受）**：装 **non-variant `hip-dev`（7.2.4 族，7.2.53211.70204，从 rocm.list 拿）**，只需 4 包：
> ```
> hip-dev  hsa-rocr-dev  libfile-copy-recursive-perl  libfile-which-perl
> ```
> - **无 variant 冲突**（无 `*7.2.4` 后缀包，不重演 §6 故障）；dry-run 实测 0 冲突。
> - `hip-dev` 提供 HIP 头文件（`/opt/rocm-7.2.4/include/hip/*`）+ `share/hip/version` → **补齐 hipcc 编译能力**。
> - `hsa-rocr-dev` 是已装 `hsa-rocr`（non-variant，已 ii）的 dev 扩展，同族兼容。
> - **并非重装 variant**；此是 non-variant 语义，正是 §7 教训的避坑路径。
>
> **▸ 已执行（用户裁定）**：B 站 `apt install -y hip-dev`（联动 hsa-rocr-dev + 2 perl）→ 验证 `hipcc --version` 不再警告 + `hip_runtime.h` 落地 → 进入 P-0 冒烟。

---

## 7. 工具链补全与首次构建（2026-09-28 实地，E1）

> 承 §6.5。hip-dev 补齐了 HIP 头文件，但构建暴露下一层缺口。

### 7.1 hip-dev 后仍缺 GEMM dev 头/库

- **HIP 编译冒烟通过**（`hipcc --version` 报 HIP `7.2.53211`，`--offload-arch=gfx1151` 生效），但**首次真实构建** `make strix-halo` 在**第一处 HIP 源**即失败：
  - `ds4_rocm.cu:2 → ds4_rocm.h:4: fatal error: 'hipblas/hipblas.h' file not found`
  - → ds4 还需 **hipblas / hipblaslt / rocblas / rocwmma** 的 dev 头与库（链接 `-lhipblas -lhipblaslt -lrocblas`）。
- 纯 C 部分（ds4.c / ds4_distributed / ds4_tp / ds4_ssd / ds4_image 等）**全部编译通过**，说明 C 侧无碍，问题集中在 ROCm dev 依赖。

### 7.2 遮蔽源定位（★ 关键诊断）

- 构建报 `rsqrtf` / 头文件错时，实际被包含的是 **`/usr/include/hip/...`**（`-H` 实证），而**非** `/opt/rocm-7.2.4/include/hip/...`。
- `dpkg -S` 定位：`/usr/include/hip/hip_runtime.h` 属 **Ubuntu 包 `libamdhip64-dev` 5.7.1-3** ⇒ **Ubuntu 5.7 旧 HIP 头遮蔽了 7.2.4 头**（§3 记录的「Ubuntu 源遮蔽」在**头文件层**复现）。
- ⚠ 加 `-I/opt/rocm-7.2.4/include` **无效**：hipcc 的 clang 命令行中 `-internal-isystem`（内置目录）排在 `-I` **之前**，按命令行序搜索 ⇒ 内置路径先命中。

### 7.3 修复（★ 本轮真正走通的路径）

| 步骤 | 动作 | 结果 |
|---|---|---|
| ① | `apt purge libamdhip64-dev`（Ubuntu 5.7 遮蔽源，仅影响自身 1 包）| `/usr/include/hip` 消失，遮蔽解除 |
| ② | `apt install hipblas-dev hipblaslt-dev rocblas-dev rocwmma-dev hipcub-dev`（**不带 `7.2.4` 后缀**，全从 rocm 7.2.4 源解析）| 装 5 dev 包 + 依赖（hipblas/rocblas/rocsolver/rocsparse/roctracer/rocprim-dev 等，**全 7.2.4**，无 Ubuntu 旧包、无 variant 冲突）|
| ③ | 验证头/库 | `hip_runtime.h`/`hipblas.h`/`hipblaslt.h`/`rocblas.h`/`rocwmma.hpp` **全在**；`libhipblas.so`/`libhipblaslt.so`/`librocblas.so` **全在** `/opt/rocm-7.2.4/lib` |
| ④ | HIP 编译冒烟（**无需宏补丁**）| **PASS**（`t.o` 生成）|
| ⑤ | 现役 llama | `not-found=0`，**零受损** |

> ★★ **关键区分（本轮最值钱的一条）**：§5.1 失败的包名是 **`hipblas-dev7.2.4`（带后缀 = variant）**；本轮成功的是 **`hipblas-dev`（不带后缀 = ROCm 仓库常规包）**。**两者是完全不同的包** —— 之前把「带后缀 variant」误当作唯一精确解法，才是 §6 故障的根。

### 7.4 首次完整构建结果

- 用 `make strix-halo HIPCC=/opt/rocm-7.2.4/bin/hipcc` **再次构建**：C 侧全过、HIP 侧推进到编译 `ds4_rocm.cu`，
- **新阻塞**：`rocm/ds4_rocm_deepseek4_vision.cuh:239` → `no matching function for call to 'rsqrtf'`（**host 函数调用 device-only 的 `rsqrtf`**）。全仓 `rsqrtf` 共 **78 处**。
- ⇒ 这是 **ds4 源码与 clang 22 / ROCm 7.2.4 的版本兼容问题**（CUDA 下 `rsqrtf` 为 host+device 双可用，HIP clang 22 下为 device-only）⇒ 见 §8 的版本代差结论。

---

## 8. ds4 官方目标版本发现（2026-09-28，E3）

> 为判断 §7.4 的 `rsqrtf` 阻塞是「配置错」还是「版本代差」，核 ds4 官方容器的构建面。

**官方 `kyuz0/strix-halo-ds4-toolbox/Dockerfile.rocm-10.0` 原文关键行**：

```
ROCm 10.0.0   (baseurl = stable.repo.amd.com/rocm/core/packages/rhel10/x86_64)
install amdrocm-core-devel10.0-gfx1151          ← gfx1151 专用开发元包
ARG REPO=https://github.com/kyuz0/ds4.git
ARG BRANCH=main-gfx1151                          ← 用 fork 分支，非 antirez main
+ git am PR #2 (deepseek41 SWA) / PR #1012 (server raw prompts)
```

**三点硬结论**：

1. ★ **ds4 的 ROCm 构建目标 = ROCm 10.0**（AMD 新 "core" 打包），**本集群系统为 7.2.4** ⇒ **存在大版本代差**，正是 §7.4 `rsqrtf` 报错的根（clang 版本行为差异）。
2. ★★ **gfx1151 需要社区补丁分支**：官方/社区用 **`kyuz0/ds4` 的 `main-gfx1151` 分支 + PR 补丁**，**不是 antirez main** ⇒ **antirez 主干在 gfx1151 上并不能干净构建**。
3. 容器是 ds4 官方**明确推荐**路径（STRIX_HALO.md 首选 container/toolbox）。

⇒ **净含义**：要让 ds4 在我们硬件上跑起来，「原生 7.2.4 构建」已证不通（版本代差 + 缺 gfx1151 补丁）；可行路径只剩 **容器（官方 ROCm 10.0 + gfx1151 fork）** 或「系统装 10.0」（见 §9 风险评估）。

---

## 9. ROCm 7.2.4 依赖核验 + ROCm 10.0 安装风险评估（2026-09-28 实地，E1）

> **缘起**：用户提出「ROCm 7.2.4 我记得当前似乎没有引擎依赖这个，请核实是否可能破坏现役 llama」。
> **方法**：三站只读实证（`ldd` / `ldconfig -p` / `ld.so.conf.d` / `profile` / 反依赖）。

### 9.1 三站核验结果（A/B/C 一致）

| 检查项 | A | B | C | 结论 |
|---|---|---|---|---|
| 现役 llama-server `ldd` 引用 `/opt/rocm` | **0** | **0** | **0** | ✅ 全走 bundled |
| RUNPATH | `$ORIGIN` | `$ORIGIN` | `$ORIGIN` | ✅ 优先自家目录 |
| studio python `libtorch_hip.so` 引用 `/opt/rocm` | **0** | **0** | **0** | ✅ 用 site-packages 内 `_rocm_sdk_core` |
| `/etc/profile.d` rocm/LD 注入 | 无 | 无 | 无 | ✅ |
| `~/.bashrc`/`.profile`/`/etc/environment` 的 LD | 无 | 无 | 无 | ✅（仅 `UNSLOTH_LLAMA_CPP_BACKEND=rocm`，是后端标记非路径）|
| `/etc/ld.so.conf.d/*rocm*` | 无 | 无 | 无 | ✅ |
| 系统 ldconfig 注册的 HIP 库 | 仅 `libamdhip64.so.5`(Ubuntu 旧) | 同 | 无 | ✅ 与 bundled `so.7` **soname 不同** |

> A 站唯一的 `/etc/ld.so.conf.d/20-amdgpu.conf` 指向 `/opt/amdgpu/lib/...`（**图形驱动栈，非 rocm**）。

### 9.2 结论：现役引擎「零依赖」系统 ROCm 7.2.4（用户记忆正确）

- 现役 `llama-server` 与 studio `torch` 的 ROCm 库**全部 bundled 在自家目录**，靠 `RUNPATH=$ORIGIN` 解析；
- **系统 `/opt/rocm-7.2.4` 只作构建工具链（hipcc）+ 诊断（rocminfo）**，与 TRACKER 2026-09-17 记录一致；
- ⇒ **装 ROCm 10.0 不会「直接」破坏现役 llama**（现役压根不看系统 ROCm）。

### 9.3 但仍需防的 3 个「间接通道」

| # | 风险通道 | 机制 | 当前基线 |
|---|---|---|---|
| ★★ | **LD_LIBRARY_PATH / `rocm.conf`** | AMD 安装器**常写这两个**；一旦指向含 `so.7` 的 `/opt/rocm/lib` ⇒ **LD_LIBRARY_PATH 优先于 RUNPATH** ⇒ **会遮蔽 bundled ⇒ 真破坏** | 三站干净（**回退锚点**）|
| ★ | **amdgpu-dkms** | 与 in-tree amdgpu 驱动冲突（Ryzen 要求 `--no-dkms`）| 三站 DKMS 目录为空 |
| ○ | ldconfig 注册同名 `so.7` | 理论遮蔽，但 RUNPATH 兜底（装后 `ldd` 自证）| 现仅注册 Ubuntu `so.5` |

另有代价：会**升级/冲突**本轮刚装的 7.2.4 dev 包（`hip-dev`/`hipblas-dev` 等，仅服务 ds4 构建、不服务推理，冲突可控但须处理）。

### 9.4 净判断（判断，非实测）

- 装 ROCm 10.0 对现役 llama 是**风险可控但不为零**（取决于安装器是否写 LD_LIBRARY_PATH/`rocm.conf`）；代价是**把集群刚统一的 7.2.4 基线下掉**，换成未在本集群验证的大版本。
- **容器路径能用 ROCm 10.0 且完全不碰系统** ⇒ 规避上述全部风险，且天然带 gfx1151 补丁（§8）。

---

## 10. 容器 toolbox 性能评估 + 运行时现状（2026-09-28，E1 + E3）

> **缘起**：用户问「容器 toolbox 是否会明显降低推理性能」（针对 §8/§9 提出的容器路径）。
> **结论先行**：**不会明显降低**。性能不是选容器路径的阻碍；阻碍在**治理（daemon）**与**宿主驱动兼容**。

### 10.1 机制层：容器不是虚拟机

- **共享宿主内核**（无 hypervisor、无 CPU/内存虚拟化）；
- GPU 走**设备直通**（`/dev/kfd` + `/dev/dri/renderD128`）+ **宿主 amdgpu 驱动原生**执行 ⇒ **无虚拟化开销**；
- 本集群实测：B 站 `/dev/kfd`、`/dev/dri/renderD128` 均在（属 `render` 组，带 ACL）。

### 10.2 社区实证（同硬件 gfx1151，E3）

| 来源 | 事实 |
|---|---|
| visorcraft/strix-halo-llm-perf | 主后端即 **kyuz0 distrobox 容器**（ROCm 7.0 nightlies）；榜单 MiniMax M2.5 **32.8 tg**、Qwen3-30B **86.1 tg** 等**均为容器内结果** |
| sleepingrobots（ROCm 7 toolbox 对拍）| **整个生产栈跑在 toolbox 容器**；跨版本差异 ±9%，明确归因于 **ROCm 版本**、非容器 |
| sleepingrobots（PR #21344）| 容器内 `llama-bench` 对拍，prefill +24% 等增益正常复现 |

⇒ **三条独立来源均无「容器税」**。

### 10.3 ★ 真正的性能变量 = 容器内的 ROCm 版本（非容器本身）

- 官方 ds4 toolbox 自带 **ROCm 10.0**（§8），宿主为 7.2.4；
- 社区横评显示不同 ROCm 版本在 gfx1151 上**互有胜负、无一致赢家**（±10% 量级）⇒ 属**版本效应**，与容器无关。

### 10.4 需留意的 3 点（非「性能税」）

| # | 事项 | 说明 |
|---|---|---|
| ① | **宿主驱动兼容** | 容器共享宿主内核（6.17 + in-tree amdgpu）；ROCm 10.0 用户态与宿主 KFD 的匹配性**需实测**。风险在**能不能跑**，不在**跑多快** |
| ② | **GTT/内核参数仍由宿主决定** | 容器改不了内核参数 ⇒ 本集群 `gttsize=120000` 继续生效 ✓（反而是好事）|
| ③ | ★ **治理** | B 站**只装了 docker**（always-on daemon）⇒ 与「零自加载」纪律冲突；`podman`/`distrobox` 未装。ADR-0004 立场 = 容器仅极端兜底、优先无 daemon 的 **Apptainer** |

### 10.5 本集群容器运行时现状（E1，B 站实测）

| 运行时 | B 站 |
|---|---|
| `docker` | ✅ 有（`/usr/local/bin/docker`）—— **always-on daemon，撞零自加载** |
| `podman` / `distrobox` / `toolbox` | ❌ 均未装（podman 无 daemon，如需容器路径**建议装 podman+distrobox**）|
| `apptainer` | ❌ 未装（ADR-0004 的首选无 daemon 方案）|
| `podman.socket` | inactive（未激活）|

---

## 11. 原生 ROCm 10.0 路线与 P-0 冒烟（2026-09-28 实地，E1 + E3）

> **缘起**：按容器路径推进时遇三重阻塞（见 §11.1），用户裁定转**原生 ROCm 10.0（ubuntu2404 源）**。

### 11.1 容器路径的三重阻塞（E1，B 站实测）

| # | 阻塞 | 实证 |
|---|---|---|
| ① | **无可用容器运行时** | docker 仅 **Desktop CLI**（`context=desktop-linux`），daemon 未运行（socket 不存在）；`podman`/`distrobox`/`toolbox`/`apptainer` **均未装** |
| ② | **镜像源不可用** | `docker.io` 直连**超时**；`docker.xuanyuan.run` **需登录**；`dockerproxy.com` 不可达 |
| ③ | **治理** | ADR-0004：容器运行时须先过 ADR/EV-4；docker 常驻 daemon 撞零自加载 |

### 11.2 ★ 发现：ROCm 10.0 有官方 Ubuntu 24.04 源（E3）

- 旧 `repo.radeon.com/rocm/apt` **止于 7.2.4**；ROCm 10.0 在 **新仓库**：
  `https://stable.repo.amd.com/rocm/core/packages/ubuntu2404`（`dists/stable` + `pool/main`，464 包）
- gfx1151 dev 元包：**`amdrocm-core-dev10.0-gfx1151`**（含 `amdrocm-core10.0-gfx1151` + runtime/blas/fft/sparse/solver/dnn/rccl… 各 `-dev`）
- ⚠ **签名 key 缺口**：InRelease 由 `C367239A86C9B62AF49C921EFA296B056C5BB456` 签，但官方发布的 `packages.gpg` 是另一把（`D0F0…D5E02107`，"AMD MLSE DevOps"）⇒ **无匹配 key** ⇒ 临时用 **`trusted=yes`**（须记录为偏离）。

### 11.3 安装与「共存/零影响」核验（E1）

**dry-run 预判**：46 包 / **~793 MiB** / **0 移除** / 不触碰任何现有 7.2.4 包 / 安装到 **`/opt/rocm/core-10.0/`**（与 `/opt/rocm-7.2.4/` **分路径**）。

**实际安装**（`apt-get install -y --no-install-recommends amdrocm-core-dev10.0-gfx1151`）：rc=0，46 包，version **10.0.0**。

**装后核验（★ 对照 §9 的 3 个风险通道）**：

| 检查 | 结果 |
|---|---|
| §9 通道① `ld.so.conf.d` 新增 | **无** ✓ |
| §9 通道① `LD_LIBRARY_PATH` | **空** ✓ |
| §9 通道③ ldconfig 同名 so | **未注册 core-10.0 的 so**（仍是 Ubuntu 旧 `so.5`）✓ |
| **现役 llama** | `not-found=0`，仍全走 bundled ✓ **零受损** |
| `/opt/rocm` symlink | 未改（仍 → `/etc/alternatives/rocm`）|
| `rocminfo`(10.0) | **gfx1151 可见** ✓ |
| 副作用 | 注册了若干 `update-alternatives`（`/usr/bin/amdclang*` 等 → core-10.0）|

### 11.4 ds4 构建：`rsqrtf` 上游缺陷 + 1 行补丁（E1 + E3）

- 用 `/opt/rocm/core-10.0/bin/hipcc` 构建 `make strix-halo ROCM_ARCH=gfx1151`：
  **C 侧全过**，卡在 `rocm/ds4_rocm_deepseek4_vision.cuh:239` → `rsqrtf`（**host 函数调 device-only 函数**）。
- ★★ **关键取证：该缺陷与版本无关** —— **ROCm 7.2.4(clang22) 与 10.0(clang23) 都报**；**antirez main 与 `kyuz0/ds4` 的 `main-gfx1151` fork 都有同一行**；容器额外的 **PR #2 / #1012 也不涉及 `rsqrtf`**。
- **机制**：clang 的 `__clang_hip_math.h` 把 `rsqrtf` 无条件声明为 `__DEVICE__`，而 ROCm 的 host 数学头未补 host 版 ⇒ **host 上下文无可用 `rsqrtf`**。
- **修法（最小补丁，1 处，已备份 `.orig`）**：
  `const float alpha = rsqrtf((float)head_dim);` → `const float alpha = 1.0f / sqrtf((float)head_dim);`
- **结果**：5 个二进制**全部链接成功**（`ds4` / `ds4-server` / `ds4-bench` / `ds4-eval` / `ds4-agent`，各 ~33MB）。

### 11.5 P-0 冒烟结果（E1）

| 验证 | 结果 |
|---|---|
| `./ds4 --help` | ✅ 正常（含 `--rocm` / `--ssd-streaming` 等 ROCm 选项）|
| `./ds4-server --help` | ✅ 正常（自述兼容 OpenAI / Responses / Anthropic / completion API）|
| 运行前置 | 需 `LD_LIBRARY_PATH=/opt/rocm/core-10.0/lib/rocm_sysdeps/lib:/opt/rocm/core-10.0/lib`（**仅 per-invocation，不写系统**）|
| 现役 llama | ✅ `not-found=0` 零受损 |

⇒ **P-0「引擎活着」达成**（CLI/server 可执行、ROCm 后端可选）。**完整 P-0 尚需加载模型**（见 §12）。

### 11.6 遗留与偏离（必须记录）

| # | 项 | 状态 |
|---|---|---|
| ① | **源码补丁** | `~/ds4/rocm/ds4_rocm_deepseek4_vision.cuh:239` 一行 —— **本地偏离上游**，升级须重打 |
| ② | **`trusted=yes`** | ROCm 10.0 源无匹配官方 key ⇒ 签名校验被跳过（偏离）|
| ③ | **模型下载** | B 站外网实测 ~270 KB/s ⇒ 81GB 约 85h ⇒ **待核可行路径**（见 §12 待补）|
| ④ | 系统改动面 | **仅 B 站**：加 1 个 apt 源文件 + 46 个 `amdrocm-*` 包；A/C 未动 |

---

## 12. GLM-5.3-Flash 档位与双机 PP 前置核验（2026-09-28，E1 + E3）

> **缘起**：P-0 达成后，核「GLM-5.3-Flash 档位」与「双机 PP 的前置」，为 [ADR-0010](../../adr/ADR-0010-DwarfStar第二引擎引入立项.md) 的能力边界提供实证。

### 12.1 档位（E1，hf-mirror `Content-Length` 实测）

| 档位 | 文件 | 大小 |
|---|---|---|
| Q2 | `GLM-5.3-Flash-Q2.gguf` | **89.9 GiB** |
| Q4_K | `GLM-5.3-Flash-Q4_K.gguf` | **177.8 GiB** |

B 站 `/home` 可用 **937G** ⇒ 两档均可落盘（Q4 需双机分片跑，见 12.2）。

### 12.2 ★★ 双机能力核验（源码门禁实证，对原方案的关键修正）

| 能力 | ROCm(gfx1151) 结论 | 证据 |
|---|---|---|
| **TP**（`--tensor-parallel`） | ❌ **被拒**：`"tensor parallelism requires the Metal backend"` | `ds4.c:72484`（受 `#ifndef DS4_HAS_DEEPSEEK41_GPU` 约束）；本地构建二进制 `strings` 亦含该串 |
| **PP**（`--layers` 层切片） | ✅ **可用**：`"distributed layer slices can run fully resident"` | `ds4.c:70887` 源码文案 |
| GLM-5.3 单机 resident | ✅ **豁免** streaming 要求（`!ds4_model_is_glm53()`）| `ds4.c:70879` |
| GLM-5.2 单机 | ⚠ 需 `--ssd-streaming` | 错误文案 `ds4.c:70885` |

⇒ ★★ **对部署方案 §1.5/§3 的修正**：原写「GLM-5.3-Flash 双机 **RESIDENT TP**」**不成立**；**ROCm 双机主线 = PP（`--layers` 层切片）**。

> 旁证（E3）：`kyuz0/ds4` fork 的 `docs/CLUSTERING_ROCM.md` 给出 ROCm 双机实测 **~16.6 t/s(TCP) / 17.3 t/s(RoCE)**，但其方案是 **`--tensor-parallel` 且明确 `--layers` 不支持**、**面向 V4.1 Flash Q2** —— 与本期 GLM 目标不同，故该 fork 留作 **V4.1 专线**候选（见 ADR-0010 替代方案 E）。

### 12.3 链路（E1，B 站实探）

- `thunderbolt0` = **10.10.10.2/24**（连 A 站 10.10.10.1，**可达**）
- `thunderbolt1` = **10.10.11.1/24**（**第二条 USB4**，连 C 站）
- ⇒ 三站**菊花链拓扑，B 为中间节点**；「10.10.10.3 不可达」的原因 = C 不在该段。

### 12.4 模型下载可行路径（E1 已冒烟）

| 项 | 结果 |
|---|---|
| HF 直连 | ❌ `huggingface.co` http=000（不可达）|
| **`hf-mirror.com`** | ✅ 可达；**实测 10.79 MB/s** |
| `hf` CLI | ✅ 已在 `~/.local/bin/hf`，脚本 `find_hf_command()` 会自动命中 |
| 链路冒烟 | ✅ `hf download`（经镜像、`HF_HUB_DISABLE_XET=1`）小仓库 **rc=0** |

**执行式**：
```bash
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_DISABLE_XET=1
cd ~/ds4 && ./download_model.sh ds4f-q2     # 86.7GB ≈ 2.2h
```

---

## 13. 格式兼容性与性能/质量核验（2026-09-28，E1 + E3）

> **缘起**：用户两问 —— ① ds4 双机 PP 跑 GLM-5.3-Flash 用的是**专用格式还是通用 GGUF**（A 站已冷存 Unsloth GLM-5.3-Flash IQ4_XS）；② ds4 单机跑 V4-Flash / GLM-5.3-Flash 的**吞吐**与**压缩性能损失**。

### 13.1 ★ Q1：ds4 用**专用格式**，A 站的 Unsloth GGUF **不可用**（E1 + E3）

**官方声明（E3）**：README L13「**deliberately narrow, not a general GGUF runner**: you need to use the [project's GGUFs]」；MODELS.md L5-6「other GGUFs may have unsupported **tensor layouts, metadata, or quantization mixes**」。

**机制层实证（E1，源码）**：

| 事实 | 证据 |
|---|---|
| ds4 量化器以 **HF safetensors** 为输入 | `gguf-tools/deepseek4-quantize.c`（"HF-safetensors to GGUF quantizer"）|
| **只实现 5 种量化类型** | `gguf-tools` 自述：`q8_0 / q8_K / q4_K / q2_K / iq2_xxs` |
| GLM 只认这三种路由专家量化 | `ds4.c:2362-2367` 枚举 `DS4_TENSOR_Q2_K=10 / Q4_K=12 / IQ2_XXS=16`；`ds4.c:1043-1046` 注释即 GLM 配方（Q2_K down / Q4_K 高内存档 / IQ2_XXS gate-up）|

**A 站文件实测（E1）**：`~/.lmstudio/models/unsloth/GLM-5.3-Flash-GGUF/GLM-5.3-Flash-UD-IQ4_XS.gguf` = **146.1 GiB**，标准 **GGUF v3**，1412 tensors —— 用的是 **IQ4_XS 等 llama.cpp 量化类型**，**不在 ds4 的 5 类实现集内**。

⇒ **结论**：① **ds4 读不了**该文件（量化类型 + tensor layout + metadata 均不匹配）；② **不能从它转**（ds4 转换器输入是 **safetensors**，非 GGUF）；③ ⇒ **A 站冷存储对 ds4 不可用**；要跑 ds4 的 GLM 必须走 `./download_model.sh glm53-q2`（90 GiB）/ `glm53-q4`（178 GiB）。

### 13.2 ★ Q2：吞吐与压缩损失 —— 官方**不覆盖本集群硬件**，必须自测（E1 + E3）

**① 官方 benchmarks（E3，`docs/PERFORMANCE.md`）** —— **只有 V4-Flash，且只有 Metal/CUDA 两行，无 ROCm**：

| 机器 | 后端 | ctx 2k | ctx 64k | prefill（2k → 64k）|
|---|---|---|---|---|
| M5 Max 128G | Metal | **39.35** t/s | 27.64 | 790 → 399 |
| DGX Spark 128G | CUDA | **18.05** t/s | 13.84 | 826 → 823 |

⇒ **官方既无 Strix Halo/ROCm 行，也无 GLM-5.3-Flash 行**。

**② 同款硬件（gfx1151 ROCm，社区 E3）**：V4-Flash **ds4 ≈ 12.5 t/s / prefill 122**（prismix）vs llama.cpp Vulkan **18.33 / 254** ⇒ **ds4 在 ROCm 上不占优**（与 §7.1 一致；该文注明 gfx1151 ROCm 尚早期）。
**GLM-5.3-Flash 的 ds4 吞吐：公开数据缺失**（搜到的 Spark GLM 数据均为 **vLLM**，非 ds4）。

**③ 分布式（官方 E3）**：2×M5 Max Flash Q4 —— prefill **加速 1.38–1.85×**，但 **generation ≈ −19% 惩罚**（与 §7.1「PP 非 decode 加速」一致）。

**④ 压缩损失**：
- ds4 官方 Q2 配方 = 路由专家 **IQ2_XXS(gate/up) + Q2_K(down)**，其余关键路径保高精度（Q8/F16/F32），imatrix 引导；
- 官方仅给 **continuation top-token 一致** 类对比（`QA_BEFORE_RELEASES`），**非本仓任务面的质量结论**；
- 社区独立数据点：Lucebox ROCmFP3（**2.766 bpw，定制格式、非 ds4 官方档**）在 `ds4-eval-92` 得 **82/92**，与参考（2.88 bpw）**持平** ⇒ 佐证 ~2.8bpw 可保质量，但**不可外推到 ds4 官方 GLM 档**。

⇒ **结论**：**Q2 的答案是「必须自测」**—— 官方不覆盖我们的硬件与 GLM，社区在 ROCm 上反而显示 ds4 不如 llama.cpp。这正是 ADR-0010 中 **P-3/P-4** 存在的理由；本仓立场（**未自复现不采信**）要求用我们的 gold 夹具实收。

---

## 14. 执行：GLM Q4 下载（走既有入口）+ C 站双机准备（2026-09-28 实地，E1）

> **触发**：用户指令「先启动 GLM Q4 专用格式后台下载任务，复用之前的下载框架；然后配置 C 站为 B/C 两站 ds4 双机跑 GLM 5.3 Flash 做准备」。
> ★ 用户同时纠正：**必须走统一管理框架既有的模型下载组件，不得新增零散脚本**。

### 14.1 ★ 下载入口修正（本轮教训）

| 尝试 | 结果 |
|---|---|
| ① `./download_model.sh glm53-q4`（脚本内置 hf CLI 路径）| ❌ **失败**：`ValueError: The file is too large to be downloaded using the regular download method. Install hf_xet...`。取证：`hf_xet` **其实已装**（`/usr/bin/python3` 可 import）；真因 = **hf-mirror 不提供 Xet 端点** ⇒ huggingface_hub 回落**常规 HTTP**（traceback 实证走 `http_get`）⇒ 触发 HF 的 **>50GB 常规下载上限**。 |
| ② 经用户纠正后：**既有组件 `lm-download@<name>`**（`/etc/systemd/system/lm-download@.service`）| ✅ **成功** |

**② 的形态（与既有示例同形，未新增脚本）**：
- 任务定义：`/etc/lm-download/tasks/ds4-glm53-q4.env`（三变量 `DL_URL` / `DL_DIR` / `DL_OUT`）
- 启动：`sudo systemctl start lm-download@ds4-glm53-q4`
- 引擎：unit 内 `aria2c --max-connection-per-server=16 --split=16 --min-split-size=64M --continue=true`
- 落点：`/home/scott-lau/ds4/gguf/GLM-5.3-Flash-Q4_K.gguf`（**190,875,526,464 B** = 177.8 GiB）
- 实测：**DL ≈ 43–51 MiB/s**，**ETA ≈ 47 min**（比 hf CLI 路线实测的 10.8 MB/s 更快）

⇒ **教训**：**"复用下载框架" 的正解是 `lm-download@`（aria2c 直链）**，不是脚本内置的 hf CLI 路径 —— 后者在**镜像场景**（无 Xet）对 >50GB 文件结构性不可用。

### 14.2 C 站配置（为 B/C 双机 PP 准备）

| 项 | 结果（E1） |
|---|---|
| 前置 | Ubuntu 24.04.5 / 内核 6.17.0-23 / **磁盘 1.2T 可用** / KFD+`renderD128` ok |
| 现役依赖 | `ldd` 现役 llama 引用 `/opt/rocm` = **0**（与 B 同构）|
| ROCm 10.0 core | ✅ 装好（46 包 / `10.0.0` / `/opt/rocm/core-10.0`）；**与 B 同法**（ubuntu2404 源 + `trusted=yes`）|
| ★ §9 风险通道 | ✅ **全清**：无 `ld.so.conf.d` 新增 · `LD_LIBRARY_PATH` 空 · `ldconfig` 命中 core-10.0 = 0 · **现役 llama `not-found=0`** |
| ds4 源码 | ✅ 由 B `rsync`（`--exclude gguf`）；**1 行补丁随行**（`vision.cuh` rsqrtf = 0 实证）|
| ds4 构建 | ✅ 5 个二进制全建出；`./ds4 --help` 可执行 |
| ⚡ 加速手法 | C 直连 AMD 源仅 **843 KB/s**（832MB 需 ~14min）⇒ 改为 **B→C 传已缓存 deb**（46 个 / 794M，USB4 秒级）再本地安装 |

### 14.3 ★ B↔C 链路（PP 的物理前提，E1）

| 站 | 网口 | 地址 |
|---|---|---|
| B | `thunderbolt1` | **10.10.11.1/24** |
| C | `thunderbolt1` | **10.10.11.3/24** |

⇒ **同段直连成立**（互 ping 通、**ssh 免密双向可用**）—— 这是双机 PP 的传输通道（`--coordinator <addr> 9911`）。

### 14.4 剩余步骤（未做）

1. **GGUF 同步到 C**：B 下载完成后经 USB4 `10.10.11.x` rsync B→C（177.8 GiB）。
2. ★ **PP 拉起须先补管理面**：按 ADR-0010 决策 4，ds4 起停**必须并入 `ops/cluster.py`**（不得新增并列入口）⇒ 见 **P-2 设计**（另档）。

---

## 15. 关联与合规

- **关联方案**: [DwarfStar 部署专项方案](./2026-09-28_DwarfStar部署专项方案.md) §3（构建）/§4（前置核验）/§10（执行序，第②步前置核验 → 第③步构建+P-0）。
- **关联台账**: `spec/upstream-tracker/TRACKER.md`（三站 ROCm 7.2.4 统一记录 / 系统 ROCm「不在推理路径上」的既有结论，本轮 §9 为其 E1 复证）· `spec/model-eval/FRAMEWORK-SURVEY-2026-09.md §H.7`（非 llama 引擎路线全景）。
- **ADR-0004**: 安装属系统包管理（`/opt/rocm` 域），探针脚本放 `tmp/`（已 gitignore）合规；起停/ds4 管理面后续并入 `cluster.py`（方案 §5，仍待立项 EV-4）。★ **系统改动（累计，如实登记）**：**B 站** —— ① `purge libamdhip64-dev`；② `install hip-dev` + 5 个 ROCm 7.2.4 dev 包；③ 新增 `/etc/apt/sources.list.d/rocm-core10.list`（`trusted=yes`）+ 46 个 `amdrocm-*` 10.0 包（→ `/opt/rocm/core-10.0`）；④ **新增下载任务定义 `/etc/lm-download/tasks/ds4-glm53-q4.env`（走既有 `lm-download@` 组件，非新脚本）**。**C 站（§14.2）** —— ③④ 同 B（同源同法、同 `trusted=yes`）。**A 站未改动**。⚠ **回退锚点**：删源文件 + `apt purge amdrocm-*` + `systemctl stop`/删任务 env，即回到 7.2.4-only。★ **容器路径治理含义（承 §10.4/§10.5）**：B 站现仅 `docker`（always-on daemon，**撞零自加载纪律**），`podman`/`distrobox`/`apptainer` 均未装 ⇒ 若日后再走容器，仍须先过 ADR-0004/EV-4。
- **证据等级**: 前置核验 / dry-run / 安装实测 / 回退 / 构建 / ROCm 依赖核验 / 容器运行时现状 / ROCm 10.0 安装与共存核验 / ds4 构建与 P-0 冒烟 / **C 站配置与 B↔C 链路 / `lm-download@` 下载实测** = **E1**；官方构建依赖、26.04 差异、官方容器 Dockerfile（ROCm 10.0 + gfx1151 fork）、容器性能社区实证、ROCm 10.0 ubuntu2404 源与包索引、ds4 官方 MODELS/PERFORMANCE/DISTRIBUTED/gguf-tools 文档 = **E3**；`rsqrtf` 根因与 10.0 风险 = **E1+E3 合成判断**。

---

## 16. P-2 落地 · 首次双机 PP 起跑 · 崩溃根因定位（2026-09-28 晚）

### 16.1 编排链路：通过（E1）

`py ops/cluster.py load glm53-q4 --backend ds4` 三阶段全通：`[1/3]` C 站 worker（官方序：先 worker）→ `[2/3]` B 站 coordinator → `[3/3]` `/v1/models` 返回 `glm-5.3-flash`。
实测路由建立：`distributed route ready: local 0:22 -> 10.10.11.3:35969 Q4 23:output`（`layers=45`，与 `glm5-next.block_count` 推导一致）。

### 16.2 首跑暴露并修复的三个真实缺陷（已随 commit `2054370`）

| # | 缺陷 | 根因 | 修复 |
|---|---|---|---|
| 1 | worker 就绪**假阴性**（报「worker 未存活」）| `pgrep -f '[d]s4 --role'` 是**连续子串**匹配，真实命令行 `ds4 --rocm --role worker` 中间夹 `--rocm` ⇒ 永不命中 | 改 `'[d]s4 .*--role'`；就绪判据从「进程还活着」升级为**日志真就绪标记** `distributed worker:`（= 模型加载完 + 后端初始化完 + 层片切好） |
| 2 | 互斥/卸载 **pkill 失效**（残留进程杀不掉）| 同一坏模式用于 `[3]互斥` 与 `infer-unload` | 两处同改 |
| 3 | 部署后 bash 报 `$'in\r'` 语法错 | 工作树 CRLF（`core.autocrlf=true`）而 git 真值 LF | 部署前 LF 归一化（部署脚本侧处理，仓库内容不变） |

### 16.3 阻断：双机 PP 前向 SIGSEGV —— 根因已定位（E1）

**现象**：路由就绪后处理 prompt 即 `exit 139`（SIGSEGV + core dump）；worker 侧随后报 `coordinator disconnected; reconnecting`。

**回溯（gdb，带符号）**：

```
dist_coordinator_prefill_prompt (ds4_distributed.c:3815)
 → ds4_session_eval_layer_slice    (ds4.c:74518)
 → glm_graph_forward_indexed_tokens (ds4.c:55032)
 → ds4_gpu_tensor_read (rocm/ds4_rocm_runtime.cuh:6048)
 → hipMemcpy → libhsa-runtime64:
     hsa_amd_memory_unlock → AMD::MemoryRegion::Unlock → KfdDriver::MakeMemoryUnresident
     → hsaKmtUnmapMemoryToGPU → hsakmt_fmm_unmap_from_gpu → vm_find_object  ✗
```

**关键实验**（在断点处手工调 `hipMemcpy`，源统一用已知良好的 `batch_hc_cur->ptr`）：

| 单次拷贝 | 源 | 结果 |
|---|---|---|
| 4,096 B | `batch_hc_cur` | ✅ 返回 0 |
| 4,096 B | `hc_cur->ptr` | ✅ 返回 0 |
| 65,536 / 262,144 / 524,288 / **1,048,576 B** | `batch_hc_cur` | ✅ 全返回 0 |
| **1,245,184 B**（`-p "Hi"` 实测回读量）| `hc_cur->ptr` | ❌ SIGSEGV |
| **1,638,400 B**（25-token prompt 回读量）| `hc_cur->ptr` | ❌ SIGSEGV |
| **1,638,400 B** | `batch_hc_cur`（**同样崩**）| ❌ SIGSEGV |

⇒ **在 ds4 进程内**，触发因素是单次 D2H 拷贝 > 1 MiB（2^20），与源缓冲区无关；≤1 MiB 的单次拷贝稳定成功。
⚠ **但这不是 HIP/ROCm 的通用尺寸上限** —— 见 §16.8 的**自我否证**（裸 HIP 程序 16 MiB 完全正常）。此表的正确射程是「ds4 coordinator 进程内部」，不是「hipMemcpy 本身」。

**为何单机能跑、双机必崩**：★ 根本差别是**单机路径根本不做这次回读** —— `output_hc` 只在层切片/分布式路径由 `ds4_session_eval_layer_slice` 传入；单机生成走 `output_hc = NULL`，只回读 logits（≈593 KiB）。
而 coordinator 必须回读**整段 prompt** 的 hidden：量 = `n_tokens × N_EMBD × N_HC × 4 = n_tokens × 65,536 B`；经聊天模板 **19 token 的 `-p "Hi"`** 即 **1,245,184 B**。

**反证据（已排除的解释）**：

- 非 ds4 账目错 ⇒ 源指针 `hc_cur->ptr == g->batch_hc_next->ptr`（delta = 0x0），读长 `hc_cur->bytes = 1,638,400` ≪ base 的 128 MiB；
- 非 ctx ⇒ 4096 与 8192 均崩；非 server 层 ⇒ CLI coordinator 同样崩；
- 非竞态 ⇒ `AMD_SERIALIZE_KERNEL=3 HIP_LAUNCH_BLOCKING=1 HSA_ENABLE_SDMA=0` 全部无效；
- 非 pin/pageable 差异 ⇒ `ds4.c` 内 `cudaMallocHost` **零命中**（单机回读同样走 pageable）。

### 16.4 上游支持矩阵（该组合本就不应期待可用）

- `STRIX_HALO.md`（我们确切硬件）GLM 5.3 Flash 参考配置 = **`glm53-q2` + `--ssd-streaming` + 小 ctx，单机**；原话 **"Flash's ROCm resident and pipeline paths should not be confused with the GLM SSD-streaming path"**。
- `MODELS.md`：`glm53-q2 → ROCm also supported`；`glm53-q4 → Larger Mac, two 128 GB Macs, or SSD streaming`，而双机 GLM 走 **ownership-aware TP（Metal）** —— ROCm 的 TP 被源码门禁拒绝（`tensor parallelism requires the Metal backend`）。
- `--power` 默认即 100（"requires `--power 100`" 自动满足，与崩溃无关）。

### 16.5 已实测可用替代（E1）

现成 Q4 + **单机** `--ssd-streaming --ctx 4096` **跑通**（输出 `Hello there!`）。
实测 **prefill 0.41 t/s / generation 0.44 t/s**（冷缓存；约 65% 专家走 SSD；缓存预算 60.13 GiB / 4561 experts）。
官方参考档为 Q2（90 GiB，专家体积减半 ⇒ 命中率显著更高）。

### 16.6 上游 issue：已投递 `antirez/ds4#1141`（E1）

- **投递结果**：**https://github.com/antirez/ds4/issues/1141**（英文 · 含完整回溯 + 阈值实验表 + 反证据 + workaround 建议）。
- **落点说明**：原拟投 `kyuz0/ds4`（我们实际构建的 `main-gfx1151`），但该仓 **`has_issues: false` 且 `has_discussions: false`** ⇒ 无对外报告通道；改用正典上游 `antirez/ds4`（issues 开放），正文明确注明「构建自 kyuz0 fork `main-gfx1151`」。
- **正文已如实披露**：该组合（`glm53-q4` + ROCm 双机 PP）上游**未承诺支持**；报它的理由是「失败形态剧烈（健康启动 + 完整路由后 SIGSEGV/coredump）且根因与模型无关（纯 D2H `hipMemcpy` > 1 MiB 即可复现）」。
- **拟反喂上游的实验清单**（正文尾部已声明可随时执行）：缩微复现 · `--dist-activation-bits` · 不同 `--layers` 切分 · 换小模型双机。
- ★ **更正记录（2026-09-28）**：初稿环境表把 coordinator 写成 **"Ubuntu 26.04"**，**实为两站均 Ubuntu 24.04.5 LTS (noble)** / kernel 6.17.0-23-generic。
  根因是**把上游的参考环境当成了自己的机器** —— `STRIX_HALO.md` 写 "The Ubuntu 26.04 setup used these packages"，而 §3 讨论的正是「官方 26.04 包名 vs 本地 noble 解析差异」，改写时误合成一句。
  已用 `gh issue edit` 更正线上正文，并顺带补齐 ROCm 运行时库版本（`libhsa-runtime64.so.1.21.0` / `libamdhip64.so.7.15.26333`）、ROCm apt 轨道（`ubuntu2404` + `trusted=yes`）、模型获取口径（aria2c 直链镜像，非 `download_model.sh` 的 hf CLI 路径）、以及 log 摘录里 `ctx=8192` 行的来源标注。

<details>
<summary>正文全文（存档，便于后续回复上游时引用）</summary>

```
Title: [ROCm] D2H hipMemcpy > 1 MiB segfaults in libhsa-runtime64 on gfx1151
       (ROCm 10.0) — pipeline-parallel coordinator unusable

Environment
  HW      : 2x AMD Strix Halo (Radeon 8060S, gfx1151), 128 GB unified memory
  OS      : Ubuntu 24.04.5 LTS (noble) — BOTH ranks; kernel 6.17.0-23-generic, x86_64
  ROCm    : 10.0.0 — amdrocm-core-dev10.0-gfx1151 10.0.0-4 (ubuntu2404 track)
            runtime libs: libhsa-runtime64.so.1.21.0 · libamdhip64.so.7.15.26333
  Build   : make strix-halo, source = kyuz0/ds4 branch main-gfx1151 (tarball)
  Model   : GLM-5.3-Flash-Q4_K.gguf (178 GiB, same sha256 on both ranks)

Repro (pipeline parallelism, 2 ranks)
  # worker (C)
  ./ds4 --rocm --role worker --layers 23:output --coordinator 10.10.11.1 9911 \
        -m gguf/GLM-5.3-Flash-Q4_K.gguf -c 4096
  # coordinator (B)
  ./ds4 --rocm --role coordinator --layers 0:22 --listen 10.10.11.1 9911 \
        -m gguf/GLM-5.3-Flash-Q4_K.gguf -c 4096 -p "Hi"

Observed
  Route establishes fine ("distributed route ready: local 0:22 -> ..."), then the
  coordinator dies with SIGSEGV (exit 139) while prefilling.

Backtrace (trimmed, symbolized)
  dist_coordinator_prefill_prompt        ds4_distributed.c:3815
   ds4_session_eval_layer_slice          ds4.c:74518
    glm_graph_forward_indexed_tokens     ds4.c:55032
     ds4_gpu_tensor_read                 rocm/ds4_rocm_runtime.cuh:6048
      hipMemcpy
       hsa_amd_memory_unlock
        rocr::AMD::MemoryRegion::Unlock
         rocr::AMD::KfdDriver::MakeMemoryUnresident
          hsaKmtUnmapMemoryToGPU
           hsakmt_fmm_unmap_from_gpu
            vm_find_object   <-- SIGSEGV (table pointer is a garbage value)

Localized trigger (manual hipMemcpy at the breakpoint, D2H=2)
  4096 B      from batch_hc_cur->ptr   -> OK (0)
  4096 B      from hc_cur->ptr         -> OK (0)
  65536 B     from batch_hc_cur->ptr   -> OK (0)
  262144 B    from batch_hc_cur->ptr   -> OK (0)
  524288 B    from batch_hc_cur->ptr   -> OK (0)
  1048576 B   from batch_hc_cur->ptr   -> OK (0)
  1245184 B   from hc_cur->ptr         -> SIGSEGV   (19-token prompt readback)
  1638400 B   from hc_cur->ptr         -> SIGSEGV   (25-token prompt readback)
  1638400 B   from batch_hc_cur->ptr   -> SIGSEGV

  => the fault depends on the COPY SIZE (>1 MiB), not on the source buffer:
     every single D2H hipMemcpy <= 1 MiB succeeds; >1 MiB dies inside the HSA
     runtime. The copy is in-bounds: hc_cur->ptr == batch_hc_next->ptr (delta 0)
     into a 128 MiB allocation, reading hc_cur->bytes == n_tokens*N_EMBD*N_HC*4.

Why single-rank GLM works but PP does not
  The coordinator reads back the whole prompt's hidden state:
      n_tokens * DS4_N_EMBD * DS4_N_HC * 4 == n_tokens * 65536 bytes
  A chat-templated "Hi" is already 19 tokens -> 1,245,184 B > 1 MiB -> crash.
  Single-rank reads only the LAST token's hidden (65,536 B) or logits (~593 KiB),
  both below the threshold.

Ruled out
  - ctx: crashes at both -c 4096 and -c 8192
  - server layer: ds4 (CLI coordinator) crashes the same way
  - race: AMD_SERIALIZE_KERNEL=3 HIP_LAUNCH_BLOCKING=1 HSA_ENABLE_SDMA=0 -> no change
  - pinned vs pageable host: ds4.c has no cudaMallocHost for this path

Suggested directions
  1. ROCm side: hsa_amd_memory_unlock/MakeMemoryUnresident should not fault when
     the region was never GPU-mapped; the fmm lookup should return NULL safely.
  2. ds4 side (workaround): chunk the coordinator hidden-state readback into
     <= 1 MiB pieces, or stage it through pinned memory.
```

</details>

### 16.7 本轮证据与关联

- **证据等级**：P-2 三阶段编排通过 / 三个缺陷修复 / gdb 回溯 / 手工 `hipMemcpy` 阈值实验 / 单机 `--ssd-streaming` 跑通 = **E1**；上游支持矩阵（`STRIX_HALO.md` / `MODELS.md` / `DISTRIBUTED.md` 原话）= **E3**；「阈值 = hipMemcpy 大拷贝路径」的推断**已被 §16.8 对照实验否证**（降级为「ds4 进程内的观测边界」）。
- **合规**：探针脚本全部落 `tmp/`（已 gitignore）；站上 ds4 进程已清，GTT 归零；未改 `/opt/rocm`、未改系统配置。
- ★ **门禁副产物（供后续避坑）**：`id-census` 门禁扫描 `*.py` 的 `hexdigest()|md5(|sha256(|sha1(`，**不读 gitignore** ⇒ **新写的 `tmp/*.py` 若含哈希调用会直接红灯**（本轮实测 +3 行/+1 文件）。临时脚本要么去掉哈希调用，要么用非 `.py` 扩展名。

---

## 16.8 ★ 自我否证：那 1 MiB 不是 HIP 的尺寸上限（E1）

§16.3 把「单次 D2H > 1 MiB 必崩」写成了通用规律，**本轮后续两个对照实验把它否证了**，故单列归档 —— 这是本仓反复强调的「报数必须带射程」的又一次实例。

**对照 A：裸 HIP 程序不复现**（同机 / 同 ROCm 10.0 / 同 `gfx1151`，`hipcc` 直编）

| 场景 | 结果 |
|---|---|
| 256 MiB 设备分配 → D2H pageable 4 KiB…**16 MiB** | **全部 hipSuccess(0)** |
| 同上 → D2H pinned（`hipHostMalloc`）4 KiB…16 MiB | **全部 hipSuccess(0)** |
| 先 `hipMalloc + hipMemset` **32 / 64 / 85 GiB** 占住 GTT，再做 D2H 至 4 MiB | **全部 hipSuccess(0)** |

⇒ **不是 HIP 的尺寸边界，也不是 GTT 压力**。

**对照 B：ds4 的零拷贝 host 登记路径未参与**

`ds4_rocm_runtime.cuh:4651` 有一条对未落设备缓存的模型区间做 `cudaHostRegister(MapPointer|ReadOnly)` 的零拷贝回退（`g_model_ranges[].host_registered`），因崩溃点正是 host 登记区的 `Unlock → MakeMemoryUnresident`，本是头号嫌疑。用 gdb 在复现过程中对该行**计数**：

```
readback hits         = 1
hostRegister attempts = 0
```

⇒ 复现全程**没有**任何 `cudaHostRegister` 调用。该假设出局。

**结论（射程收窄后的事实）**：(a) 崩溃点/回溯稳定；(b) 只在 **ds4 coordinator 进程**内复现，裸 HIP 进程不复现；(c) 在该进程内确定性且随拷贝尺寸变化（≤1 MiB 过、>1 MiB 崩，同地址）。
⇒ **「1 MiB」是该进程内的观测边界，不是根因**；真正致命的 **ds4 进程态差异尚未定位**（可疑面：多线程 HIP 上下文 · `hipStreamCreateWithPriority` 的非默认 stream · 逐线程 device 设置 · 超大驻留集下的 ROCr 内部记账）。

**已同步上游**：`antirez/ds4#1141` 标题与正文均已更正 —— 加了 "Update — what the '1 MiB' threshold is *not*" 小节（含裸 HIP 对照输出与 `hostRegister attempts = 0`），并把 "Likely mechanism" 从「HIP 侧机制推断」下调为「mechanism is open」。

**下一步候选（未做，留给裁决）**：① 在断点处用**新 `hipMalloc` 的缓冲**做 >1 MiB D2H（区分「ds4 分配方案」与「进程态」）；② `LD_PRELOAD` 包裹 `hipMemcpy`/`hsa_amd_memory_*` 记录序列；③ 把 ds4 源码里零拷贝回退**编译期关掉**重建（`g_model_range_mapping_supported = 0`）—— 本条已被对照 B 降级为低优先；④ 换一个体积小得多的 ds4 系模型做双机 PP，看是否与「超大驻留集」相关。

---

## 16.9 双机 PP「能否自行闭环」的实测判定（E1）：**不能靠配置；硬阻塞在 ds4 自身**

承「双机 PP 当前条件下我们是否能够自行闭环」之问。**方法**：以「每次跨站 span 的回读量」为唯一变量，用**既有** `--dist-prefill-chunk` 扫描（B=coordinator / C=worker，`-c 4096`，其余不变）。

| `--dist-prefill-chunk` | 每 span 回读 | 结果 | 失败模式 |
|---|---|---|---|
| 默认（≥ prompt）| 整段 19 token = 1.22 MiB | ❌ exit **139** | ROCm HSA `vm_find_object` SIGSEGV（原始缺陷）|
| 16 | 1.00 MiB | ❌ **139** | 同上 |
| 12 | 768 KiB | ❌ **139** | 同上 |
| 10 | 640 KiB | ❌ **134** | **ds4 堆损坏**（`malloc(): unsorted double linked list corrupted`）|
| 8 | 512 KiB | ❌ **134** | **ds4 堆损坏**（pipelined 与 `DS4_DIST_DISABLE_PREFILL_PIPELINE=1` fallback **两条路径都复现**）|

**两条结论**：

1. ★ **ROCm 那一面不是硬阻塞 —— 它可从 ds4 侧绕开**：把回读压到 ~768 KiB 以下，HSA SIGSEGV **不再出现** ⇒ 触发面是「该进程内的**大单次 D2H 回读**」，不是「ROCm 做不到」。
2. ★ **但绕过之后暴露第二、独立缺陷：ds4 在分块 span 路径上写坏自己的堆**。glibc 报三种消息（`unsorted double linked list corrupted` / `malloc_consolidate(): invalid chunk size` / `unaligned fastbin chunk detected`）；**触发线程是 ROCr 的 `AsyncEventsLoop`** ⇒ 它是**受害者**而非元凶。

⇒ **不存在可用的 flag 组合**（两端夹死）。因此问题的性质不是「ROCm 不支持 PP」，而是：

> **ds4 的 PP 实现有两处缺陷：① ROCm 侧触发那处**可绕过**；② ds4 自身的堆破坏**不行**。**

### 附：默认路径为何必然吞整段（源码级原因）

```c
static bool dist_coordinator_can_pipeline_prefill(..., uint32_t n_tokens, uint32_t chunk_cap) {
    if (getenv("DS4_DIST_DISABLE_PREFILL_PIPELINE")) return false;
    ...
    if (chunk_cap == 0 || n_tokens <= chunk_cap) return false;   /* chunk_cap 默认 = session prefill cap */
```
默认 `chunk_cap` = session prefill cap（数千）⇒ 普通 prompt 永远满足 `n_tokens <= chunk_cap` ⇒ **永不走 pipelined**，落回 fallback 循环并**整段一次吞** = 恰好一次 `n_tokens × 65,536` 的 D2H —— 就是死掉的那一次。

### ASan 定位（时间盒一轮，**未取得报告**）

- 尝试：源码副本构建 / 重链接 / 就地构建（构建后立即恢复 release，`md5` 校验一致）。
- 卡点（已定位到工具链）：**`ld.lld` 拒绝 clang 的 ASan 目标文件** ——
  `ld.lld: error: ds4_cli.o: SHT_STRTAB string table section [index 37] is non-null terminated`，并伴随 `undefined symbol: __asan_report_store8` 等一串 `__asan_*`。
- 下一轮的第一步已明确（**非本轮**）：`-fuse-ld=bfd` 换链接器 + 链 `libasan`（或 `LD_PRELOAD` 法）。
- 最小复现（供后续接手）：`--dist-prefill-chunk 10 -p "Hi"` 于 coordinator。
- ⇒ 按**时间盒约定收手**：维持 PP 冻结，不做未经裁决的自维护补丁投入。

**已同步上游**：`antirez/ds4#1141` 追加 "Update 2"（含扫描表、两条失败模式、`can_pipeline_prefill` 源码原因、ASan 链接卡点与最小复现）。

---

## 17. 替代路径调研：GLM-5.3-Flash 还能用什么跑 —— ★ **已迁出**

> 本节（AMD 官方进展 · 六条可选路径 ①–⑥ · 处置倾向）**主题是 GLM 怎么跑**，已按「一主题一承载文档」迁至
> **[GLM-5.3-Flash 本地推理部署 §附录 A.1](2026-09-28_GLM系列本地推理部署.md)**。
> 结论要点（供索引）：① llama.cpp `glm5next` 分支 + RPC 层切分 = **最贴近现状且已执行**；② vLLM 卡在量化格式与权重可得性；③ ds4 ROCm TP **已被源码否证**；④ GLM-5.3 旗舰（`glm-dsa`）**主线本就支持**，卡在体积。
---

## 18. 三条任务的调研结论（E1，2026-09-28）—— ⚠ 任务①/③ 已迁出

> 本节原含三条：**① glm5next 分支引入方案 · ② ds4 的 ROCm TP · ③ GLM-5.3 旗舰（753B）**。
> **① 与 ③ 的主题是 GLM，已迁出**至 [GLM 文档附录 A.3 / A.2](2026-09-28_GLM系列本地推理部署.md)；**本文只保留 ②**（它本身就是 ds4 的能力结论）。

### 18.1 任务②：ds4 的 ROCm TP —— **不可用（源码级双门禁）**，上轮"可能可用"被否证

上轮（§17.2 ③）我据「门禁处于 `#ifndef DS4_HAS_DEEPSEEK41_GPU` 之下」推测"带宏构建可能开放 ROCm TP"。**读源码后否证**：

```c
/* ds4.c:49-52 —— ROCm 构建下该宏被显式排除 */
#if !defined(DS4_NO_GPU) && !defined(DS4_ROCM_BUILD)
#define DS4_HAS_DEEPSEEK41_GPU 1
#endif

/* ds4.c:72479-72493 —— 第一道门（编译期） */
int ds4_engine_tp_bind(...) {
#ifndef DS4_HAS_DEEPSEEK41_GPU
    snprintf(err, errlen, "tensor parallelism requires the Metal backend");   /* ← ROCm 走这里 */
    return 0;
#else
    /* 第二道门（运行期） */
    if (!e || !tp || (e->backend != DS4_BACKEND_METAL &&
        (e->backend != DS4_BACKEND_CUDA || DS4_MODEL_FAMILY != DS4_MODEL_FAMILY_DEEPSEEK41))) {
        snprintf(err, errlen, "tensor parallelism requires Metal or V4.1 CUDA");
        return 0;
    }
```

⇒ **两道门叠加**：① `-DDS4_ROCM_BUILD` 使 `DS4_HAS_DEEPSEEK41_GPU` 不成立 ⇒ 直接报 Metal-only；② 即便强行打开，运行期仍要求 **Metal** 或 **(CUDA 且 family = DEEPSEEK41)** —— **GLM 系不在其中**。
⇒ **结论**：ds4 的 TP 对 GLM-5.3-Flash **在 ROCm 上不可用**，且**不是"开个构建宏就行"**；要动它等于**改上游 TP 语义**（把 family 白名单扩到 GLM），属自维护补丁范畴 ⇒ **候选 ③ 关闭**。
（附注：`kyuz0/ds4` 的 `docs/CLUSTERING_ROCM.md` 在**我们的源码树里不存在**（不是 tarball 的一部分）——ADR-0010 替代方案 E 里那条引用来自外部浏览，非本地实证。）

### 18.2 / 18.3 GLM-5.3 旗舰支持 · `glm5next` 分支引入方案 —— ★ **已迁出**

> 两节**主题是 GLM**，已迁至 **[GLM 文档 §附录 A.2（旗舰 753B 支持）/ §附录 A.3（分支引入方案）](2026-09-28_GLM系列本地推理部署.md)**。
> 一句话：旗舰（arch `glm-dsa`）**现役引擎架构层已支持**，障碍在体积（最小档 ≈216.7 GB ⇒ 必须多机层切分）；
> `glm5next`（Flash）**未进主线** ⇒ 只能从 PR 分支构建，且**不得切 symlink**（并存版本目录 + 入口化）。

---

## 19. ★★ GLM-5.3-Flash 在 llama.cpp 双机 RPC 上跑通 —— ★ **已迁出**

> 本节（执行链路 · 首跑结果 · 双机 RPC 实录）**主题是 GLM 怎么跑**，其**结论与实测数据已在**
> **[GLM 文档](2026-09-28_GLM系列本地推理部署.md)** 正文（§4 引擎引入 / §5 入口 / §6 起停 / §7 吞吐 / §8 容量 / §9 限制）；
> **正文未覆盖的两块**（ds4 那份 Q2 档的"只有 ds4 能读"张量命名判据 · 本轮运维事实）已迁至 **GLM 文档 §附录 A.4 / A.5**。
> 对本 ds4 文档的意义只有一句：**它证否了"ds4 是跑 GLM 的必要路径"** ⇒ 与 §20.3 的存废结论同源。

---

## 20. ds4 存废（其余内容已迁出）

> 本节原为「调优、三节点、ds4 存废与 V4.1 支持」的合集，**其中 GLM 与 V4.1 的部分已分别迁出**：
> **§20.1 配置扫描 / §20.2 三节点 → [GLM 文档 §7.3 / §7.2](2026-09-28_GLM系列本地推理部署.md)**；
> **§20.4 V4 系支持与后端更新 → [V4.1 文档 §6](2026-09-28_DeepSeek-V4系列调研与部署.md)**。
> **§20.5 待办的三条归宿**：① zrald 体积/片数/架构 → 已核，见 **V4.1 文档 §7**；② ADR-0010 降级裁决 → 已执行，见本文件 **§21.4**；③ 长 ctx decode 衰减曲线 → 仍是空白，见 **GLM 文档 §8.4**。
> 下面**只保留属于 ds4 的那一节**。

### 20.3 ★ ds4（DwarfStar）在本集群的存在必要性 —— **作为生产引擎，必要性已消失**

| 事实（E1）| 对 ds4 价值的影响 |
|---|---|
| llama.cpp **主线已含 `deepseek4`**，变体分支的 dsv4 实现**更完整**（`llama_kv_cache_dsv4`、`llm_graph_input_dsv4`、compress_ratios 0/4/128 校验）| ADR-0010 v1.0 的**核心动因"架构覆盖面"已被吞并** |
| llama.cpp 双机 RPC 跑 GLM-5.3-Flash **11.2–11.9 t/s** vs ds4 单机 streaming **0.41–0.44 t/s** | ds4 **慢 27×** |
| ds4 PP 两端夹死（§16.9）· TP 源码门禁（§18.1）| ds4 **分布式能力双重不可用** |
| ds4 量化白名单仅 **5 类**（源码级：`IQ2_XXS/Q2_K/Q4_K/Q8_0/Q8_K`）| **连 `Q3_K_M` 都读不了** |

**剩余价值（三条，均不值投入）**：① 超内存模型的 **SSD streaming**（190 GB/124 GB 机器；llama.cpp 有 `--n-cpu-moe`/`-ot exps=CPU` 近似替代）；② **第二实现 = 交叉验证价值**（用 ds4 验 llama.cpp 数值，方法学有意义但非生产力）；③ 备援引擎。

⇒ **建议：ADR-0010 从「试点立项」降为「观察保留」** —— 不删（代码 0.4 GB + Q4 模型 190 GB），**不再投入工程时间**，仅在需要"第二意见"时启用。

### 20.4 / 20.5 V4 系支持与后端更新 · 待办 —— ★ **已迁出**

> 已迁至 **[V4.1-Flash 部署路径调研 §6](2026-09-28_DeepSeek-V4系列调研与部署.md)**（V4 `Q3_K_M` 量化白名单 · 后端更新的两条路 A/B）。
> ⚠ 该节原文标题写「V4.1（Q3_K_M）」，但内容实为 **V4-Flash（arch `deepseek4`）**；**V4.1（arch `deepseek41`）两引擎均不支持** —— 这一区分已在新文档 §6/§7 钉死。

---

## 21. 存量盘点与裁决：ds4 侧保留什么（2026-09-28 收口，E1）

### 21.1 现存资产

| 资产 | 体量 | 性质 | 现状 |
|---|---|---|---|
| ds4 源码 + ROCm 构建产物（`~/ds4`） | ~0.4 GB（代码）+ 179 G（含模型，见下） | 上游 tarball + 1 行补丁 | 冷藏 |
| `/opt/llama.cpp-glm5next-20260928`（并存变体） | 73 MB | **现役在用** | ✅ **GLM-5.3-Flash 的唯一通路** |
| ROCm 10.0 工具链（`/opt/rocm/core-10.0`） | — | ds4 构建依赖（与 7.2.4 双隔离） | 冷藏 |
| `GLM-5.3-Flash-UD-IQ4_XS.gguf`（A 原 + B 副本） | 146.1 GiB ×2 | llama.cpp 用 | ✅ 现役 |
| **`GLM-5.3-Flash-Q4_K.gguf`** | **190,875,526,464 B（177.8 GiB）** | ★ **ds4 专属** | **见 §21.3 裁决** |

### 21.2 那份 190 GB 是什么（实测）

- **出处**：ds4 官方档 `glm53-q4`（`download_model.sh`），下载后字节一致 + sha256 双端一致（§14）
- **内容**：`architecture = glm5-next` · 46 层 · 1412 张量 · 量化类 `F32×614 / BF16×459 / Q8_0×210 / Q4_K×129`（**全部标准 llama.cpp 类型**）
- ★ **可用性边界（决定性）**：**张量命名是 ds4 转换器体系** —— `kda_like = 510` 处、**`ssm_like = 0`** ⇒ 与那份 Q2 同一来源，**llama.cpp 结构性不可读**（该判据的完整版见 [GLM 文档附录 A.4](2026-09-28_GLM系列本地推理部署.md)）；且 177.8 GiB **> 单站 124 GB** ⇒ 只能靠 ds4 `--ssd-streaming`（**0.41–0.44 t/s**）
- **与替代品对比**：同一模型在 llama.cpp 侧有 Unsloth `UD-IQ4_XS`（146.1 GiB，A/B 站**已有**）⇒ 速度 **27×**、**零额外下载**、质量同位或更好

### 21.3 裁决：**保留冷藏（不删）**

| 理由 | 事实 |
|---|---|
| 磁盘不紧 | B 站余 **612 G** |
| 唯一性 | 它是**唯一 ds4 可读的 GLM-5.3-Flash 档** ⇒ ADR-0010 v1.2 的「**复活条件②：第二实现交叉验证**」**没有它就无法落地** |
| 重下成本 | ~190 GB ≈ 1 h（hf-mirror 56 MB/s）+ 校验 |
| 代价 | 190 GB 磁盘；**无速度/内存代价**（ds4 非常驻、零自加载） |

⇒ **退役条件**：磁盘告急，或 ADR-0010 再降为「退役」。

### 21.4 ADR-0010 v1.2（降级）与镜像同步

| 处 | 改动 |
|---|---|
| `adr/ADR-0010-…md` | fm `version 1.1→1.2`；状态行与元数据表改「**由试点立项降为观察保留**」；新增 **v1.2 裁决**段（依据/处置/复活条件/退役条件）|
| `docs/research/…部署专项方案.md` | 立项行 → v1.2 |
| `spec/ds4-backend/DESIGN.md §2.2` | ADR-0010 行 → v1.2（**授权与 D4 不变，但不再有后续 P-x 投入**）|

**v1.2 依据（复述要点）**：① 核心动因「跑 llama.cpp 跑不了的架构」**已被吞并**（主线含 `deepseek4`；glm5next 经变体+双机 RPC 跑通 **11.2–11.9 t/s** vs ds4 **0.41–0.44 t/s**）；② 分布式**双重不可用**（PP 两端夹死 · TP 源码门禁）；③ 量化白名单仅 5 类 ⇒ **连 `Q3_K_M` 都读不了**。

---

## 22. 外部依赖核查：`Zrald/zralddeepseekv4.1` —— ★ **已迁出**

> 全节（仓库真相 · 玩具档铁证 · `deepseek41` 架构 · 内存边界 · HTTP Range 方法论）**主题是 DeepSeek V4.1**，
> 已迁至 **[V4.1-Flash 部署路径调研 §7](2026-09-28_DeepSeek-V4系列调研与部署.md)**（含 §7.5 的"零下载判支持性"方法论）。
> 一句话结论：**不结案 —— 阻塞在引擎（`deepseek41` 两引擎均不支持），不在权重**（`compressed` 真档 246.3 GiB 可下载、三站可装）。
