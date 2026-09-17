# 三站系统 ROCm 统一装 7.2.4 — DESIGN

> **日期**: 2026-09-17
> **上游依据**: 《分布式推理路线可行性调研》[§9.7](../../docs/research/2026-09-16_分布式推理路线可行性调研_CIRU-Skulk-多机TP.md)（遮蔽判据探测）+ TRACKER 变更日志 v2.0
> **执行站**: A / B / C 三站（192.168.1.33 / .32 / .37，scott-lau）
> **范围**: 三站统一安装系统 ROCm **7.2.4**；不动 bundled 推理运行时（`~/.unsloth/llama.cpp/build/bin/`）；不整体迁移任何框架

## 0. 证据基线（审计后事实，勿臆测）

| 事实 | 实证来源 | 出处 |
|---|---|---|
| A 站有系统 ROCm 6.4.1（`/opt/rocm`→`/opt/rocm-6.4.1`，SONAME `so.6`） | 本轮 `readelf`/`ls` | §9.7-① |
| B/C 站无系统 ROCm（`/opt/rocm` 不存在、dpkg 零 rocm/hip 包） | 本轮勘查 | §9.7-① |
| A 站 6.4.1 进程级引用**零命中**（全 `/proc/*/maps` 扫 `/opt/rocm` = 0、现役推理未跑、infer-load/systemd 仅注释） | 本轮扫描 | §9.7-① |
| 三站 bundled 推理全靠 `RUNPATH=[$ORIGIN]` 自洽，`ldd` 对其 `libamdhip64.so.7`/`libggml-hip.so.0`/`libhipblas.so.3` 全命中 bundled | 本轮 `readelf -d` + `ldd` | §9.7-③ |
| ROCm **7.2.4**（=仓库 latest）兼容矩阵**正式列出 gfx1151**（Ryzen AI Max+ 395 / Radeon 8060S / RDNA 3.5 / Ubuntu 24.04） | 官方 docs-7.2 Linux 矩阵（本轮 fetch） | §9.7-② + 本轮查证 |
| 6.4.4 对 gfx1151 仅「初始/Preview」（PyTorch 2.8 单档） | 官方原页 | §9.7-② |
| **仓库实测：`rocm/apt/` 无 `7.14.0` 目录**；6.x/7.x 现最高 7.2.4，`latest` 即 7.2.4 → 统一目标更正为 7.2.4（官方产品号与 apt 版本段不同，勿再引 7.14） | 本轮 `curl` 目录清单 + `latest` Release | §9.7 判据纠偏 |
| C 站实际 `source` 指向 `rocm/apt/7.2.1`（已偏离 7.2.4，需 pin） | 本轮 grep sources | 本轮实测 |
| `amdgpu-install` 三站漂移：A `6.4.60401` / B `6.3.60303` / C `30.30.1.0.30300100` | 历史勘察 | §9-背景 |
| 内核：A `6.17.0-40`、B/C `6.17.0-23`（7.2 需 HWE 6.17，全站满足） | 历史勘察 | §9-背景 |

**关键判定（已在 §9.7 落档 + 本轮纠偏）**：`$ORIGIN` 解析先于 `ldconfig` 缓存 ⇒ 装 7.2.4 注册 `so.7` 后 bundled 推理仍绝对优先，**遮蔽风险不存在**。A 站 `so.6` 与 bundled/7.2.4 的 `so.7` 不同 SONAME 天然共存。

## 1. 目标

1. 三站装同一系统 ROCm **7.2.4**，补齐 B/C 本地 HIP 构建/诊断能力，消 `amdgpu-install` 三站版本漂移。
2. 采用 TheRock 模块化安装，**只装 `rocm-hip-sdk` 必需集**，控制 footprint，不装不用的 instable/mi300 等。
3. **绝不破坏** bundled 推理路径（`infer-load` 默认 HIP/ROCm 照常）；`so.7` 系统注册后不抢占 bundled。
4. 全程可逆：失败即回滚到装前状态，三站一致。

## 2. 决策记录

| # | 决策 | 理由 |
|---|---|---|
| D1 | **版本 = 7.2.4**（=仓库 latest；非此前误引的 7.14） | gfx1151 在 7.2 官方正式支持（本轮矩阵查证）；TheRock 模块化 footprint 可控；bundled 已是 `so.7` 同代；仓库实测 7.2.x 现最高 = 7.2.4 |
| D2 | **`--no-dkms`** | `amdgpu` 内核 in-tree 即可（§9 已证）；装 DKMS 会与 in-tree 冲突并破坏 ROCm GPU 访问（lemonade 社区 + 三站 DKMS 目录空 = 现状匹配）；保持「不装 amdgpu-dkms」必须态 |
| D3 | **装 `rocm-hip-sdk` 模块**（含 hip-dev/rocblas/rocfft/miopen/rccl 等 dev 栈） | 目标是「本地 HIP 构建 + 诊断」能力，非推理运行时；`rocm-hip-sdk` 即此定位（TheRock 用法，见官方 install） |
| D4 | **三站版本 pin**：`amdgpu-install --rocmrelease 7.2.4`（或等价的 `--release` 显式传参） | 防止 C 站默认装到同 7.2.x 漂移（C 现 source 7.2.1 ≠ 7.2.4）；所有站必须显式指定 7.2.4，装后断言版本 |
| D5 | **不卸载 A 站 6.4.1**（本次不删） | A 的 `so.6` 与 7.2.4 的 `so.7` 不同 SONAME 共存无害；删除属独立动作，不在本次范围（§9.7 已标「可安全移除但非冲突」，留待单独裁决） |
| D6 | **MIRROR 一致性**：三站 apt 仓库统一指向同一 ROCm 源（官方 repo.radeon.com 或公司镜像） | 否则三站可能拉到不同构建，破坏「统一」目标 |
| D7 | **执行顺序 = B → C → A** | B 站是合规（架构参考）单点、破坏面最小，先 B 验证脚本 → C → A 收尾（A 已有 6.4.1 共存最复杂，最后） |

## 3. 执行步骤

> 全程经 `ops/cluster.py` 的 `ssh_run/ssh_stream`；每条命令用 `set -euo pipefail` 包裹，`ssh_stream` 校验远端退出码（**不能用 `ssh_run` 的 ok 语义判成功** —— 它 default 不代表 rc=0）。

### 3.0 前置探测（✅ 已实证，2026-09-17）
- **`--rocmrelease=` 选项三站 amdgpu-install 均支持**（`--help` 实查）→ D4 pin 方式成立。
- **7.2.4 rocm/apt 源三站均可解析（`curl` HTTP 200）** → 「7.2.4 仓库可用」实证成立。
- **`amdgpu/7.2.4/ubuntu` = 404**，但 `rocm/apt/7.2.4` = 200 ⇒ 7.x 的 amdgpu(内核)源不在此命名 → **必须 `--no-dkms`**（第二重实证：7.2.4 无 amdgpu-dkms 源，须避开）。
- **`rocm-hip-sdk`/`hip-dev` 包确认存在于 7.2.4 源**（`Packages.gz` 检索）→ D3 装 `rocm-hip-sdk` 成立。
- 三站网络可达 `repo.radeon.com` 200；A 实装 rocm-core 6.4.1 / B、C 无。
- 装前基线记录（备份）：`amdgpu-install --version`、`dpkg -l | grep -E 'rocm|hip'` 全量、`cat /opt/rocm*/.info/version 2>/dev/null`（若有）→ 存 `~/backups/rocm72-precheck-<date>.log`。

### 3.1 备份（三站各一次，破坏性操作前铁律）
- 系统 ROCm 现有面快照：
  - A：`sudo cp -a /opt/rocm-6.4.1 ~/backups/rocm-6.4.1-pre72-<date>/`（**sudo 必须**，root 所有文件无 sudo 的 `cp` 会静默失败 —— 备份铁律补充）。`du -sh` 写入清单并校验与源 size 一致。
  - B/C：无系统 ROCm，无需备份（记录「无」即可）。
- apt 状态：`sudo apt-get --fix-broken install` 干跑确认无残留损坏依赖（失败则中止，先修）——**不建议**（不装东西）除非发现 broken。

### 3.2 安装（每站一步到位，失败即止并跳 5 回滚）
```bash
set -euo pipefail
# 显式 pin 版本（D4）（安装器版本号串以实际 release 名为准，装前 3.0 先行核定）
sudo amdgpu-install \
  --rocmrelease 7.2.4 \
  --no-dkms \
  --no-32bit-lib \
  -y --usecase=rocm,hipdev   # rocm=核心运行时；hipdev 含 hip 开发栈
```
> ⚠ `--usecase` 的具体名（`rocm`/`hipdev`/`rocmdevelop`）须在 3.0 预检时用 `amdgpu-install --help` 在当前版本核定，写死可能因版本差异失败。**判据先行**：先看本机 `amdgpu-install --help` 支持哪些 usecase 字符串，再定最终命令行。

### 3.3 装后断言（每站，成败判据）
```bash
# ① 版本 = 7.2.4
dpkg -l | grep -E '^ii\s+rocm-core' | awk '{print $3}'

# ② 目录存在且为 7.2
ls -d /opt/rocm /opt/rocm-7.2.4
cat /opt/rocm-7.2.4/.info/version

# ③ SONAME 为 so.7
ls -l /opt/rocm-7.2.4/lib/libamdhip64.so*

# ④ ldconfig 已注册（不要求是唯一的，只要在）
ldconfig -p | grep -m3 libamdhip64.so.7
```
全部通过 = 本站装成功；任一失败 = 进 5 回滚。

### 3.3 ✅ B 站试点（2026-09-17，超出设计的方法发现）

**结论**：B 站已装系统 ROCm 7.2.4，遮蔽自证 + 冒烟双证通过。

**方法发现（比设计更简）**：**无需升级 amdgpu-install 到 30.x**。直接在**已修好的 7.2.4 源**上用 apt 装 `rocm-hip-runtime` 即可。关键前置 = **修复 apt 源体制**：
1. B 站 apt 源曾混杂：`rocm/7.2.4` + `amdgpu/6.3.3` 并存 + **`.distUpgrade` 后缀**（apt 偶发忽略 rocm 源）→ `apt-cache` 空但 curl 直拉 Packages 有。
2. **修法**：备份全部含 rocm/amdgpu 源 → 禁用 amdgpu(6.3.3, 仅 dkms, 与 in-tree/--no-dkms 冲突) 移 `.disabled` → rocm `.distUpgrade` 改名 `.list` → 单源 update 稳定收录。
3. 装 `rocm-hip-runtime`（dry-run 验证依赖纯用户态，无 dkms/内核包）→ 结果：rocm-core 7.2.4.70204、hip-runtime-amd 7.2.53211、hsa-rocr 1.18.0、**gfx1151 枚举命中**、`--device ROCm0` 冒烟通过。
4. **hipcc 未装**（属 `rocm-hip-sdk`，待评估；runtime 已可跑 HIP 应用，编译需 SDK）。

**回滚**：从备份 `.bak-rocmfix` 恢复原 rocm/amdgpu 源 + `apt-get` 卸载 rocm-hip-runtime。B 站源修复已保留（统一到 7.2.4 即目标）。

### 3.3 ✅ A 站清理 + 统一 7.2.4（2026-09-17，承 B 站方法）

**结论**：A 站系统 ROCm 6.4.1 已清除，统一到 7.2.4，遮蔽 + 冒烟双证通过（A 与 B 状态一致）。

### 3.3 ✅ C 站统一 7.2.4（2026-09-17，三站闭环）

**结论**：C 站系统 ROCm 7.2.4 已装，遮蔽 + 双路径冒烟通过 —— **三站（B/C/A）全部统一 7.2.4 完成**。

**执行**（略异于 A/B，因 C 无系统 ROCm 也无活动 rocm 源）：C 站 rocm/amdgpu 源全在 `backup-radeon-20260908/` 备份子目录（**未激活**）→ **直接新建** `/etc/apt/sources.list.d/rocm.list` 指向 `rocm/apt/7.2.4`（keyring 在、仓库 200 可达）→ `apt-get install rocm-hip-runtime` → rocm-core 7.2.4.70204，gfx1151 枚举命中。**不动** backup 历史目录（不视为活动源）。

**验证**：遮蔽自证 PASS（`$ORIGIN` + 三 HIP lib 全 bundled）；**双路径冒烟**——qwen3.8-27b-mtp（Vulkan，C 站既有 conf 指定）→ READY ✓ :18080；**gpt-oss-120b（unsloth/HIP）→ READY ✓ :8080 + `--device ROCm0` + 端口 401** ⇒ 证明 C 站 **HIP/ROCm 与 Vulkan 双路径均未受影响**。ldconfig `so.7` 未全局注册 = 三站共性（runtime 安装）。

**遗留**：C 站 backup 目录里旧的 amdgpu/30.30.1 + graphics/7.2.1 源为历史备份，未清理（非活动，无害）。

**① 6.4.1 清理 = `apt-get purge`（实证 `amdgpu-uninstall` 是"假卸载"）**：
- **`amdgpu-uninstall --rocmrelease=6.4.1` 软链到 amdgpu-install（图形驱动卸载器）**，只 purge 驱动 `BASE_PACKAGES` + `amdgpu-firmware-*` + 源清理，**不卸 ROCm 软件栈**。两次运行 END rc=0 但 55+ rocm/hip/hsa 包全在、`/opt/rocm-6.4.1` 仍在。**判据坑：END rc=0 ≠ 卸载成功**。
- 正确做法：**直接 `apt-get purge` 63 包**（rocm-core/hip-runtime-amd/hsa-rocr/rocblas/comgr/miopen/rccl/hipcc 等；dry-run 先验干净无系统关键包）。收尾 `sudo rm -rf /opt/rocm-6.4.1`（purge 不删该目录）。
- 判据落实：`/opt/rocm*` 全消失、ldconfig `so.6` 无。残留的 `amdgpu-install`/`amdgpu-core`/`libdrm-amdgpu*` 为图形驱动栈（非 ROCm 软件），保留。

**② 统一 7.2.4**（B 站方法复刻）：修源 amdgpu/6.4.1 + rocm/6.4.1 → amdgpu `.disabled` + rocm `.list` 改指 7.2.4（备份 `.bak-rocm72-*`）→ `apt-get install rocm-hip-runtime`。结果 **rocm-core 7.2.4.70204 / hip-runtime-amd 7.2.53211 / hsa-rocr 1.18.0 / rocm-llvm 22.0.0**，`gfx1151` 枚举命中（rocminfo Agent2 = gfx1151, Radeon 8060S）。

**③ 遮蔽自证 PASS**：`$ORIGIN` RUNPATH 完好，ldd 三 HIP lib（libamdhip64.so.7/libggml-hip.so.0/libhipblas.so.3）全命中 bundled `$ORIGIN`。

**④ 端到端冒烟 PASS**：`infer-load gpt-oss-120b`（A 本地；gpt-oss-20b 在 B 站）→ READY ✓ :8080，进程 `--device ROCm0`，端口 200，卸载后内存回落。

**⑤ ldconfig 注记（非异常）**：A/B 两站 `libamdhip64.so.7` 均**未全局注册**（A 仅系统级 libhsa 引用）—— 属 runtime 安装共性，ROCm 工具走自身 RUNPATH，遮蔽自证已证 bundled 不受影响 ⇒ 断言④"ldconfig 注册"对 runtime-only 安装**不适用**，改为核对 A/B 一致即可。

## 4. 装后遮蔽自证判据（核心，三站必须全绿）

> 目的：证明「系统 7.2.4 装完，bundled 推理仍走自身」—— 这是本次改动**不能破坏现役推理**的铁证。
>
> **B 站已实测通过（2026-09-17）**：装系统 7.2.4 后 ldd 对 `libamdhip64.so.7`/`libggml-hip.so.0`/`libhipblas.so.3` 全命中 bundled `$ORIGIN` 目录，系统库未抢占；`infer-load gpt-oss-20b` → READY ✓ + `--device ROCm0`，端到端无影响。

```bash
set -euo pipefail
LD_ALL_OK=1
# ① bundled llama-server 的 RUNPATH 仍为 $ORIGIN（未被改写）
echo "RUNPATH: $(readelf -d ~/.unsloth/llama.cpp/build/bin/llama-server | grep -i runpath)"

# ② ldd 下 libamdhip64.so.7 / libggml-hip.so.0 必须命中 bundled 目录
for lib in libamdhip64.so.7 libggml-hip.so.0 libhipblas.so.3; do
  hit=$(ldd ~/.unsloth/llama.cpp/build/bin/llama-server | grep -oP "\$ORIGIN.*$lib|/home/scott-lau/.unsloth/.*$lib.*" | head -1)
  case "$hit" in
    /home/scott-lau/.unsloth/llama.cpp/build/bin/*$lib*) echo "OK  $lib -> bundled" ;;
    *) echo "FAIL $lib 命中: $hit"; LD_ALL_OK=0 ;;
  esac
done
[ "$LD_ALL_OK" = 1 ] && echo "遮蔽自证: PASS (三 lib 全 bundled)" || echo "遮蔽自证: FAIL —— 立即回滚"
exit $LD_ALL_OK
```
**负向对照**（可选强化）：临时把 bundled 目录改名 → `ldd` 应 fallback 到系统 `so.7`（证明系统库可用），再改回（必须恢复大小写与权限）。**不默认做**，只在遮蔽 FAIL 排查时用。

## 5. 端到端冒烟（装后，任一站）

- `infer-load gpt-oss-20b`（非 Qwen，HIP 单机线）→ 加载日志出现 `--device ROCm0`、`READY ✓ :8080` → `/v1/models` 200 → unload 后占用回落。
- **判据**：端到端必须 PASS；否则 = 系统 7.2.4 意外影响推理 → 立即回滚。

## 6. 回滚（三站一致，失败或遮蔽 FAIL 时执行）

- **A/B/C**：进入装前基线（3.1 备份）：
  - 若仅新增 rocm-7.2.4 且与 6.4.1 并存不被干扰：`sudo amdgpu-install --uninstall`（卸 7.2.4）→ `sudo rm -rf /opt/rocm-7.2.4`（A 保留 6.4.1）。
  - A 站 6.4.1 若被改：从 `~/backups/rocm-6.4.1-pre70-*/` 恢复（`sudo cp -a`）。
- **回滚后验证**：`ldconfig -p | grep libamdhip64` 回到装前集合；`infer-load gpt-oss-20b` 再次冒烟 PASS。
- **回滚不可靠依赖**：不引入新卸载器，只用 `amdgpu-install --uninstall` + 手工清目录；卸载前 `dpkg -l | grep rocm-7.2.4` 记录待删清单。

## 7. 验收清单（全部绿才算完成）

| # | 项 | 通过标准 |
|---|---|---|
| 1 | 三站版本 | `rocm-core` 均 7.2.4（**✅ 2026-09-17 B/A/C 三站完成**） |
| 2 | 目录 | 三站 `/opt/rocm-7.2.4` 存在；~~A 站 6.4.1 仍在（共存）~~（**✅ A 站 6.4.1 已 purge 清除**，此项更新为「A 站 `/opt/rocm*` 仅 7.2.4」） |
| 3 | ~~amdgpu-install 漂移消除~~ | **不适用（实际路线 = 直连 apt 装 `rocm-hip-runtime`，不升级/统一 amdgpu-install 安装器）**——安装器版本 A `6.4.60401` / B `6.3.60303` / C `30.30.1.0.30300100` 仍漂移，但 **ROCm 软件栈已统一 7.2.4（这才是目标）** |
| 4 | 遮蔽自证 | §4 脚本三站全 PASS（三 lib 全 bundled）（**✅ B/A/C 全 PASS**） |
| 5 | 端到端 | 至少 B 站 `infer-load gpt-oss-20b` 冒烟 PASS（**✅ B gpt-oss-20b / A gpt-oss-120b / C gpt-oss-120b(HIP)+qwen(Vulkan) 双路径全 PASS**） |
| 6 | 门禁 | `ops\rpc.ps1 check`（全量，含 backend/stations）无新增 FAIL（**✅ 2026-09-17 实测：PASS 绿灯 14 / 黄灯 1 / 红灯 0**；backend 断言确认单站=HIP/分布式=Vulkan，bundled `so.7.16.26332` 不受影响；唯一黄灯 stations = A 站 claude-plugins-official 已登记漂移，不阻断） |
| 7 | DKMS | 三站 `ls /var/lib/dkms` 仍空/无 amdgpu-dkms（`--no-dkms` 生效）（**✅ 全程未装 dkms**） |
| 8 | 回滚演练 | 挑 B 站走一遍 §6 回滚再重装，验证可逆（可选，成本高） |

## 8. 不做清单（边界）

- ~~**不卸载 A 站 6.4.1**（独立动作，待单独裁决）~~ → **✅ 已执行（2026-09-17）**：A 站 6.4.1 已 `apt-get purge` 清除（见 §3.3）。
- **不改 bundled 推理路径**（`~/.unsloth/llama.cpp/build/bin/` 只读不改）。
- **不做 6.4.4 vs 7.2.4 对照实验**（属 §9.5 独立设计，非本次）。
- **不装 `amdgpu-dkms`**（D2）。
- **不升级 vLLM/ray/LM Studio**（不相关，纯系统 ROCm 铺设）。

## 9. 落档

- 完成后回写调研文档 §9.7 遗留项 → 「已执行」；TRACKER 变更日志新增 v2.1 行。
- **总结报告**: [2026-09-17_ROCm三站统一7.2.4_总结报告.md](../../docs/research/2026-09-17_ROCm三站统一7.2.4_总结报告.md)
- `project_memory` 记录三站系统 ROCm 7.2.4 状态 + 遮蔽判据自证 SOP。
- 执行脚本存 `tmp/`（gitignored）；备份留在各站 `~/backups/rocm714-precheck-<date>.log` 与 `rocm-6.4.1-pre714-<date>/`。

## 10. 审计注记（2026-09-17，设计完成时就地取证）

| # | 初稿断言 | 取证/风险 | 处置 |
|---|---|---|---|
| 1 | `--usecase=rocm,hipdev` 名词 | 各版本 usecase 字符串可能不同，写死会失败 | 前置 3.0 先用 `amdgpu-install --help` 核定再定命令行（已写入 §3.2 注） |
| 2 | 装 7.2.4 后 A 的 `so.6`/`so.7` 共存 | SONAME 不同天然不冲突；但 `ldconfig` 会同时注册两条，`libamdhip64.so`（无名后缀）会指向上一次装的 | 断言只查具体 SONAME `so.7`/`so.6`，不依赖 `so` 无版本符（已写入 §3.3/§4） |
| 3 | 回滚用 `amdgpu-install --uninstall` 可逆性 | 卸载依赖项可能连带删 A 的 6.4.1 依赖 | 回滚前记录待删验收清单；若 6.4.1 共享依赖被连带，从备份恢复；预案见 §6 |
| 4 | 统一目标「**7.14.0**」 | **初稿基于官方产品/release 号，apt 仓库实测无 `7.14.0` 目录**（`repo.radeon.com/rocm/apt/` 7.x 最高 = 7.2.4，`latest` 即 7.2.4）；官方 7.2 矩阵正式列 gfx1151（docs-7.2 native_linux） | **pin 更正为 7.2.4**。教训：**版本号必须以 apt 仓库真实存在为准，官方产品号 ≠ apt 版本段，pin 前必须 `curl` 仓库根目录清单确认该版本目录存在**（本轮 `curl https://repo.radeon.com/rocm/apt/` + `latest/dists/noble/Release` 实测） |

> **方法论沉淀**：本设计与 §9.7 完全一致的遮蔽判据链条，且把「判据本身先自证」落到每一步（版本先核定再 pin、soname 查具体版本符、回滚先定清单）。所有「必须保持」的状态（DKMS 目录空、amdgpu in-tree）在验收清单 7 有专项断言，杜绝静默降级。