# DwarfStar (ds4) 集群部署专项方案

> **日期**: 2026-09-28
> **触发**: 用户要求「给出本框架部署 DwarfStar 的具体方案，结合当前集群现状、管理方式、社区信息，综合分析，避免环境污染」。
> **性质**: 规划文档（**未执行**）；所有"现状"来自既有文档（E1/E2），外部技术用 E3 标注；任何"该不该上"的结论都留给 ADR-0004 立项裁决。
> **关联**: 承 `O-112`/`O-113`（REAP/V4.1 部署）、`EV-3`（vLLM 换栈）、`EV-4`（第二栈生命周期）、`ADR-0004`（唯一管理面）、`FRAMEWORK-SURVEY §3`（ds4 详情，本方案的动作落地）。

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
#    amd_iommu=off amdgpu.gttsize=126976 ttm.pages_limit=32505856 ttm.page_pool_size=32505856
#   ⚠ 本集群现状 amdgpu.gttsize=120000（FRAMEWORK-SURVEY 落地路线步骤 3 已点名要改 126974），
#     须先核：改内核参数 = 重启 + 是否与本集群 ROCm 版本兼容（见 §4 前置核验）

# 3. 构建
cd ~/ds4 && make strix-halo -j$(nproc)

# 4. 下载/转换 V4.1 GGUF（项目专属）
./download_model.sh ds4f-q2          # 官方现成档（推荐，避免自转换坑）
# 或：python3 gguf-tools/deepseek41_quantize.py --hf models/DeepSeek-V4.1-Flash ...  # 本地转换（自建，成本高）
```

★ **档位建议**：起点用 **官方 `ds4f-q2`（~80.8G / 单 128G 机）** —— 单机验证、成本最低；进阶 Q4（~100G）或 GLM V4.1 Q4（需双机）。先单机、再 PP，渐进（同 FRAMEWORK-SURVEY 落地路线步骤 5-7）。

---

## 4. 前置核验（★ 全未做，部署前必须逐项确认）

| 项 | 现状| 需确认 | 风险 |
|---|---|---|---|
| **ROCm 版本** | C 站 7.2.x（FRAMEWORK-SURVEY 提过） | ds4 `make strix-halo` 需要的最低 ROCm；`rocminfo` gfx1151 + KFD 可用 | 版本过低则构建/运行失败 |
| ★★ **内核参数 gttsize** | **本集群 = `120000`（AMD 官方 trillion-cluster 同值）** | ★ **ds4 官方并不强制 126976**（见 §4.1 专项） | ⚠ **大概率不需要改**；若改须按 §4.1 脚本化 + 可回退 |
| **磁盘空间** | — | V4.1 Q2 ≈ 145G、Q4 ≈ 280G 的 `~/` 空间 | 双机 PP 需再考虑 |
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
| ★ **新: `:18081` 或 `:8099`（未占用段）** | ds4-server | 待核 `inventory/ports.yaml` 后定 |

⚠ **部署前必读 [inventory/ports.yaml](file:///d:/RPC/inventory/ports.yaml)** 确认无冲突段；ds4 端口必须登记（`inventory/ports.yaml` 或 infra 台账）。

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

---

## 8. 验收判据（做到才算闭环）

| 阶段 | 判据 |
|---|---|
| **P-1 构建** | `make strix-halo` 无 warning；`./ds4 -p "hi"` 跑通（用官方临时档）|
| **P-2 单机** | `ds4-server --ctx N -m ~/ds4-models/ds4f-q2.gguf` 由 `infer-load --backend ds4` 拉起；`cluster.py status` 报 `ds4: RUNNING`・只读探活正常 |
| **P-3 隔离** | 门禁 `scripts` 断言无新增未登记脚本；`/opt` 未被触碰（`md5sum` 与基线一致）；端口表无冲撞 |
| **P-4 性能** | V4.1 @ Q2 单机 decode 对照现役 V4 双机 tg 6.3；**用现成 gold 夹具跑确定性输出**（不采信厂商声明）|
| **P-5 决策** | 产出「引入 vs 不引入」证据束，交 ADR-0004 立项裁决（含是否值得上 V4.1/是否值得长期维护第二栈）|

---

## 9. 不做的边界（必须写下来）

- **不自动升级**：不并入 UPGRADE_SOP 的 llama.cpp 升级链（ds4 是独立引擎，独立演进）。
- **不并行运行时叠加**：试点期间**不同时跑 ds4 与现役大模型**（同机内存竞争 + O-18 带宽铁律）。
- **不承诺 TT**：不推断"部署要多久"（用户偏好：不给时间估计）。
- **不全量迁移**：即便 P-5 通过，也只是「第二栈可用」，**llama.cpp 仍为主路线**（FRAMEWORK-SURVEY 结论不变）。
- **未做**：本方案**未实际执行任何一步**；前置核验（§4）全未做；本次只落文档。

---

## 10. 一句话执行序

> ① **核 EV-4 / ADR-0004**（"谁管生命周期"立项）→ ② **前置核验**（ROCm 版本 + 内核参数 + gttsize + 磁盘 + 端口）→ ③ 用户域 `~/ds4` 构建（`make strix-halo`）+ 官方 Q2 档 → ④ 只读探活并入 `cluster.py status` → ⑤ 单机 `infer-load --backend ds4` 验证 → ⑥ gold 夹具 bench → ⑦ P-5 证据束，交 ADR 裁决 → ⑧ 通过才扩 PP/TP，不通过即"裁不迁"（O-113/O-112 闭环）。

**核心**：**复用 vLLM 便携构建的"用户域 + 手动进程 + 并入唯一管理面"范式**，ds4 只活在自己的 `~/ds4` 与独占端口里，不碰 `/opt`、不装自启、不进 `ops/` 临时脚本 —— 这就是"避免环境污染"的全部含义。