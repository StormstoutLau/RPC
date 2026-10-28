# archive/station-bin-probes/ — `station-bin` 一次性探针归档

> **归档日期**: 2026-10-28（review-p2-big #8A）
> **来源**: `ops/station-bin/` 根目录下 164 个以 `_` 开头的**一次性探针/历史调试件**
> **迁移方式**: 全部 `git mv`，**内容零改动**（`git log --follow` 可追）

## 为什么在这里

`ops/station-bin/` 是**站上部署快照**：根目录只该放 部署件 / 入口运行时件 / 在跑夹具。
这 164 个文件是历次排查留下的一次性脚本（`_qwen27_*` / `_davidau_*` / `_probe_glm*` /
`_a*` / `_b*` 等），**不参与任何运行路径，也不上站**。

它们**没有删除**：里面记录了当时的判定依据与现场形态，是一手证据。

## 边界（重要）

1. **不部署**：任何 `/usr/local/bin` 里都不该出现这里的文件。
2. **不进门禁「登记」**：`archive/**` 在 `rpc_check` 的 `scripts` 治理（`ops/**` 谓词）之外
   （与 `archive/root-scripts/`、`archive/scripts-history/` 同待遇）。
   ⚠ 但**语法检查仍覆盖**：`syntax` 按扩展名扫**全部 git 跟踪文件**，这里的 `.sh` 仍会被 `bash -n`。
3. **不是"第二份实现"**：这些件若仍需要，应当**迁进统一入口**（`ops/cluster.py` /
   `ops/station-bin/` 的正式件），而不是在这里继续长。

## 取回流程（需要复用某个探针时）

1. `git mv archive/station-bin-probes/<file> ops/station-bin/<file>`；
2. 在 `inventory/ops.yaml` 对应段落登记（脚本治理 `scripts` 门禁要求）；
3. 跑 `py ops/rpc_check.py --only scripts,syntax,station-layout`；
4. 若它要在站上跑，按 `ops/station-bin/README.md` 的部署纪律（备份 → `install` → `bash -n` → md5）。

## 根目录白名单（对照）

仍在 `ops/station-bin/` 根目录的 9 个 `_*` 件（`station_bin_layout.root_keep`）：

- 运行时件：`_station_ready.sh` / `_slot_gate.sh` / `_oc_session_meta.sh`
- 在跑夹具：`_fm_golden_test.ps1` / `_probe_fallback.ps1` / `_runstamp_hammer.ps1` / `_scrubber_coverage_test.ps1`
- 被黄金夹具 AST 读取：`_switch_qwen_flavor.ps1` / `_switch_qwen_flavor.sh`

新增任何根目录 `_*` 件都会被 `station-layout` 门禁判红。
