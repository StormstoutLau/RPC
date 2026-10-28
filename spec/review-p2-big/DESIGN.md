# 设计：原始评审 P2 大项（#5 站上 shell 严格模式 / #8A station-bin 分层）

---

id: review-p2-big-DESIGN
type: design
version: 1.0
status: draft
date: 2026-10-28
depends: []
upstream: null

---

> **Feature**: 收掉原始评审 #5（站上 shell 统一严格模式）与 #8 的第一刀（`station-bin` 正式件与一次性探针分层）。`#8B`（拆 `rpc_check.py`）与 `#8C`（拆 `agent-cli.ps1`）**不在本批**，见 §1 非目标。
> **创建日期**: 2026-10-28
> **状态**: draft（Step 2；待 Step 4 设计评审）
> **Spec 步骤**: Step 2（DESIGN）
> **基于调研**: [2026-10-28 原始评审 P2 大项调研](../../docs/research/2026-10-28_原始评审P2大项_社区外部锚点调研.md)
> **代码基线**: `8dd2f3db`（`main`，已推送）
> **范围裁定**: 用户选定「#5 + 8A」

---

## 1. 目标与非目标

### 1.1 目标

| # | 目标 | 判据 |
|---|---|---|
| G1 | 站上 13 个 shell 执行件统一 `set -euo pipefail` | 每个文件 prologue 可机判；`load-gate` 为唯一显式豁免 |
| G2 | 2 个被 `source` 的库**不设** shell 选项 | `model-locate.sh` / `conf-lib.sh` 全文无 `set -[eux]` |
| G3 | 新增门禁 `shell-strict`（quick），把 G1/G2 与豁免表变成可机判 | 负向夹具能判红；豁免未命中会自报 |
| G4 | `ops/station-bin/` 根目录只剩**部署件 + 入口运行时件 + 在跑夹具** | 根目录 `_*` 仅允许 9 个在册文件 |
| G5 | 一次性 `_*` 探针移入 `archive/station-bin-probes/` | 新门禁 `station-layout` + 登记表无残留路径 |
| G6 | 去掉 `agent-cli.ps1` 内 5 处 `D:\RPC\...` 硬编码兄弟路径 | 全部改 `$Script:REPO_ROOT` 派生；fresh-checkout 可跑 |

### 1.2 非目标（明确不做）

1. **#8B 拆 `rpc_check.py`**（10168 行 / 217 defs / 50 CHECKS / 43 个测试文件 / 180 个 `R.*` 符号）——另立 spec。
2. **#8C 拆 `agent-cli.ps1`**（7406 行；两个 AST 夹具 663 条黄金断言 + 55 处文档行号）——另立 spec。
3. **`cluster.py`**：2026-09-23 已模块化（5 模块 + 门面 + 层序门禁），当时明确「`flow`/证据链/审计域按需再抽」；本批不动。
4. **164 个冻结件之外的 `.sh`**（`archive/`、根级、`tests/`）：不在运行路径，不做严格模式扫荡。
5. **非 `_` 前缀的一次性件**（`repro-*.sh`、`b6_smoke_*.py`、`a5-nextday-verify.sh` 等）：`REPRO-RUNBOOK.md` 仍引用，本轮不动。
6. **`load-gate` 的 `set +e`**：保留为显式豁免（§4.1）。
7. 站上**实弹加载/卸载**：不触发（会打断在服务模型）。

---

## 2. 依据（E1 事实摘要）

详见[调研文档](../../docs/research/2026-10-28_原始评审P2大项_社区外部锚点调研.md) §1；本设计只依赖以下事实：

| 事实 | 数值 |
|---|---|
| 站上 shell 执行件（`station_runtime` 里的 bash 件 + `ops/rpc-nodes`） | **13** |
| 被 `source` 的共享库 | **2**（`model-locate.sh` / `conf-lib.sh`） |
| 其中现 prologue 已达 `-uo pipefail` | 4（infer-load / infer-unload / conf-get / 另 1 为 `set -u` 系） |
| 显式 `set +e`（有意） | 1（`load-gate`） |
| `station-bin` tracked 文件 | 227（根目录 `_*` 175，含 `attach-test/` 2） |
| 可移动的一次性 `_*`（根目录，除 9 个在册） | ≈164（Step 3 精确枚举） |
| 可移动件的 md/代码引用 | md 链接 **1** 条（`_zen_pty_pilot.sh`）；yaml 158 条（157 在 `ops.yaml` + 1 在 `models.yaml`） |
| `agent-cli.ps1` 内 `D:\RPC` 硬编码 | **5** 处（L473 / L517 / L3538 / L3778 / L5115） |

---

## 3. 架构

### 3.1 #5：三层分域

```
执行件（13）── 默认 set -euo pipefail
   └─ 豁免（当前 1）：load-gate —— "报告型门禁"必须跑完四条规则再给结论
共享库（2）── 禁止任何 set 行（不得改调用方选项）
其余 .sh ── 不在本批（冻结/归档/测试夹具）
```

**为什么按"执行件 vs 库"分，而不是按目录**：`set -e` 的作用域是**当前 shell**，库被 `source` 后会把选项泄漏给调用方；这条边界比"文件在哪个目录"更本质。

### 3.2 8A：`station-bin` 根目录契约

```
ops/station-bin/
├── infer-load / infer-unload / infer-list
├── llama-serve-instance / rpc-serve-instance
├── cluster-ttl / cluster-watchdog
├── load-gate / load-mem-gate / wait-gtt-release
├── model-locate.sh / conf-lib.sh / conf-get
├── _station_ready.sh / _slot_gate.sh / _oc_session_meta.sh     # agent-cli 上传的运行时件
├── _fm_golden_test.ps1 / _probe_fallback.ps1                    # 在跑夹具（CHECKS 直接执行）
├── _runstamp_hammer.ps1 / _scrubber_coverage_test.ps1
├── _switch_qwen_flavor.ps1 / _switch_qwen_flavor.sh             # 被黄金夹具 AST 读取
├── README.md / REPRO-RUNBOOK.md / agent-cli.ps1 / golden/ ...
├── （非 `_` 前缀的一次性件：本轮不动）
└── attach-test/（夹具，本轮不动）

archive/station-bin-probes/   # 新增：≈164 个一次性 `_*` 件 + README
```

**为什么进 `archive/` 而不是 `ops/station-bin/probes/`**：

- `archive/**` **已在** `check_scripts` 的射程**之外**（`_in_script_scope` = `ops/**` ∪ 根级文件），且仓内已有 `archive/root-scripts/`（≈130 件）、`archive/scripts-history/`（≈180 件）两处先例；
- `ops.yaml` 的 `frozen_ops_scripts` 注释写明「**只减不增**；迁进统一入口后请从本表删除」——归档后删 163 条登记正是这条纪律的方向；
- 若放 `ops/station-bin/probes/`，则要把 163 条登记改路径（不是删除），`scripts` 仍会持续把死代码算进治理面，收益为零。

**代价与边界（实施期实测订正）**：归档后这些文件**仍会被 `syntax` 的 `bash -n` 扫描** —— `check_syntax` 的范围是**全部 git 跟踪文件**（按扩展名），不按 `scripts` 的 `ops/**` 谓词；**只有 `scripts` 治理**（登记/入口计数）不再覆盖它们。实际结果是：静态语法网**不变**，登记表**变干净**（192 → 29）。需要复用时按归档 README 的"取回流程"（`git mv` 回 `ops/` 并登记）。

---

## 4. 契约

### 4.1 `shell_strict` 策略表（唯一真值：`inventory/ops.yaml`）

```yaml
shell_strict:
  exec:                 # 必须恰好 `set -euo pipefail`（前 20 行内、非注释行）
    - ops/rpc-nodes
    - ops/station-bin/infer-load
    - ops/station-bin/infer-unload
    - ops/station-bin/infer-list
    - ops/station-bin/llama-serve-instance
    - ops/station-bin/rpc-serve-instance
    - ops/station-bin/load-mem-gate
    - ops/station-bin/wait-gtt-release
    - ops/station-bin/conf-get
    - ops/station-bin/cluster-watchdog
    - ops/station-bin/ocrun
    - ops/station-bin/backup-memories.sh
  libs:                 # 全文禁止 `set -[eux]`（被 source，不得改调用方选项）
    - ops/station-bin/model-locate.sh
    - ops/station-bin/conf-lib.sh
  allow:                # 执行件豁免：仅允许"报告型门禁"，每条必须带 why
    - file: ops/station-bin/load-gate
      why: "四条规则必须全部跑完再给 [ABORT]/[WARN]/[OK]；abort 会丢结论。取数函数在**逻辑或**列表中被调用 ⇒ -e 本就不生效（SC2310），保留 set +e 是显式化，不是疏漏"
```

**判据语义**（`validate_shell_strict` 纯函数 + `check_shell_strict` 门禁）：

| 断言 | 失败语义 |
|---|---|
| `exec` 中每件首个非注释 `set` 行 == `set -euo pipefail` | FAIL 点名 |
| `libs` 中每件全文无 `set -[eux]` | FAIL 点名 |
| `allow` 的 file ∈ `exec`，且 `why` 非空 | FAIL |
| `allow` 未命中（文件有 `set -euo pipefail` 却仍在豁免表） | **FAIL（防腐化）**——提示删掉该条 |
| `exec` ∪ `libs` 的路径都存在且被 git 跟踪 | FAIL |
| 两个 `exec` 列表重叠 / 同一文件同时出现在 exec 与 libs | FAIL |

### 4.2 根目录契约（`station_bin_layout.root_keep`）

根目录下**以 `_` 开头的文件**只允许这 9 个（白名单，理由逐条）：

| 文件 | 角色 |
|---|---|
| `_station_ready.sh` / `_slot_gate.sh` / `_oc_session_meta.sh` | `station_runtime`：agent-cli 上传到站上执行 |
| `_fm_golden_test.ps1` / `_probe_fallback.ps1` | `CHECKS` 直接执行的离线夹具 |
| `_runstamp_hammer.ps1` / `_scrubber_coverage_test.ps1` | `CHECKS` 直接执行的并发/覆盖率夹具 |
| `_switch_qwen_flavor.ps1` / `.sh` | 被黄金夹具 AST 读取的对象 |

**不变量**：根目录任何 `^_` 文件 ∉ 上述 9 个 ⇒ FAIL（防"又扔一个探针回来"）。
非 `_` 前缀文件**不设白名单**（本轮不动，避免把 `repro-*.sh` 等卷进来）。

### 4.3 归档目录契约

```yaml
station_bin_layout:
  probes_dir: archive/station-bin-probes
  root_keep: [ ... §4.2 的 9 项 ... ]
```

| 断言 | 语义 |
|---|---|
| `probes_dir` 存在且非空 | FAIL 若缺失/空（否则"分层"是空话） |
| `probes_dir` 内每个文件名都被 `git` 跟踪 | FAIL 列出未跟踪项 |
| `ops.yaml` 的 `frozen_ops_scripts` 里**不含**任何 `ops/station-bin/_*` 根级路径 | FAIL（登记残留） |
| 根目录与 `probes_dir` 无同名 `_*` 件（防"复制一份"；README 等文档各有一份是正常的） | FAIL |

### 4.4 门禁与登记

| 项 | 落点 | 变化 |
|---|---|---|
| 新 CHECKS 项 `shell-strict`（quick=True） | `ops/rpc_check.py` | 50 → 51 项 |
| 新 CHECKS 项 `station-layout`（quick=True） | `ops/rpc_check.py` | 51 → 52 项 |
| `inventory/ops.yaml` | 新增 `shell_strict` / `station_bin_layout` 两段；`frozen_ops_scripts` 删 163 条 | 登记表**只减不增** |
| `inventory/models.yaml` | 1 处 `_davidau_download.sh` 文案路径同步 | 不改变语义 |
| `.github/workflows/ci.yml` | shellcheck 目标 12 → 15（+`cluster-watchdog`/`ocrun`/`backup-memories.sh`）；**不加** SC2310/SC2311 全局门禁 | CI 只加静态网，不 ssh |
| `ops/station-bin/README.md` | 根目录范围 + 归档目录指针 | 与布局契约一致 |

> **为什么不加 SC2310/SC2311 门禁（实施期裁定）**：本批的执行件里，"函数在 `if` 条件/命令替换里被调用"是**刻意语义**（`probe_one` / `node_selected` / `wait_port` 就是靠返回码分支，而不是靠 abort）。把它们当门禁会逼出一串 `# shellcheck disable=`，反而把"哪里是故意的"抹平。替代：`shell-strict` 只钉 prologue 与库边界；"是否该容忍失败"由 IMPLEMENTATION §4.5 的逐条审计 + 真实冒烟兜住。

### 4.5 代码契约（`agent-cli.ps1` 去硬编码）

| 位置 | 现状 | 目标 |
|---|---|---|
| L473 | `'D:\RPC\ops\station-bin\_station_ready.sh'` | `Join-Path $Script:REPO_ROOT 'ops\station-bin\_station_ready.sh'` |
| L517 | `'D:\RPC\ops\station-bin\_slot_gate.sh'` | 同上 |
| L3538 | `'D:\RPC\ops\station-bin\_oc_session_meta.sh'` | 同上 |
| L3778 / L5115 | `'d:\RPC\ops\station-bin\agent-runs.log'` | `Join-Path $Script:REPO_ROOT 'ops\station-bin\agent-runs.log'` |

**为什么用 `$Script:REPO_ROOT` 而不是 `$PSScriptRoot`**：`agent-cli.ps1` 的 `split` 子命令会把自身 BOM 副本落到 `%TEMP%`，此时 `$PSScriptRoot` 已不是仓库目录；`REPO_ROOT` 走 `AGENT_CLI_REPO_ROOT` 环境变量兜底（既有 O-161 设计），是唯一正确的锚。

---

## 5. 替代方案（考虑过 / 否决了什么）

| 方案 | 否决理由 |
|---|---|
| **全仓 195 个 `.sh` 全开 `set -euo pipefail`** | 冻结件不在运行路径；`archive/` 已出治理范围；逐文件改会制造大量无收益 diff 与回归风险 |
| **只加 `set -u` + `pipefail`，不碰 `-e`** | 原文点名的实质风险是"关键写操作失败后继续"（写 conf / `sudo chown`），`-e` 才是那一层的判据 |
| **给 `load-gate` 强行开 `-e`** | 它是**报告型门禁**：必须在同一轮里读完四条规则再给结论；其取数函数已在**逻辑或**列表中被调用 ⇒ `-e` 本就不生效（SC2310）。改成 `-e` 只会制造"看起来严格、实际无效"的假象 |
| **探针放 `ops/station-bin/probes/`** | 仍在 `ops/**` 治理范围：要改 157 条登记路径、`syntax` 继续扫死代码、`scripts` 计数不降；收益为 0 |
| **探针删除** | 不可逆；这些是一手证据（`_qwen27_*`/`_davidau_*` 记录了当时的判定依据）。归档保留 `git log` 与内容 |
| **本批顺带拆 `rpc_check.py`** | 180 个测试符号 + 50 个 `fn` 对象 + 43 个测试文件；与 #5/8A 无依赖关系，混批会让回滚粒度变粗 |
| **用 `.psm1` 模块拆 `agent-cli.ps1`** | PS 5.1 + 无模块路径依赖 + 两个夹具按**单文件** AST 解析；本批不做（另立 spec 时再评估 dot-source） |
| **给 `rpc_check` 加"行数上限"门禁** | 本仓没有这个契约；800 行是外部借用规范。若设阈值，应另立 spec 与全仓基线，不在本批夹带 |

---

## 6. 不变式

| # | 不变式 | 守住什么 |
|---|---|---|
| N1 | `STATION_BINS` 12 件的仓库路径与 md5 **不变** | `gates` 36/36 不因本批抖动；本批不改部署件内容（§4.5 只改 agent-cli，非站上件） |
| N2 | 站上件**内容**变更仅限 §4.1 的 prologue 与必要守卫 | 部署 md5 会变，但语义变化可审计（逐文件 diff） |
| N3 | 库不设选项 | 调用方 shell 语义不被库偷改 |
| N4 | 一次性件只 `git mv`，**不改内容** | 归档件保持一手证据；避免"搬运顺手改 bug" |
| N5 | 登记表只减不增 | `frozen_ops_scripts` 从 192 → ≈35 |
| N6 | 所有"扫文本"的门禁清单同步搬家 | 防 P2 阶段点名的"静默降级成假绿"（搬完必须复核基线条数） |
| N7 | 不新增 daemon / systemd 单元 / 管理子命令 | ADR-0004：管理面只有 `cluster.py` + web |

---

## 7. 错误与边界

| 场景 | 处置 |
|---|---|
| `set -e` 让某条**设计性容忍**的失败变成中止 | 就地加显式守卫（**逻辑或**短路、`if !`、取值兜底），**并在 IMPLEMENTATION 逐条登记**；不允许"为了过就把 `-e` 去掉" |
| 站上部署后某命令行为变化 | 单站（B）先部署 + 只读冒烟 → 再 A/C；失败按 `.bak-p2big-*` 回滚 |
| 归档后有人仍按旧路径引用 | `doclinks` 抓 md 链接；`scripts` 抓未登记；`station-layout` 抓根目录残留 |
| `models.yaml` 的 `_davidau_download.sh` 文案 | 同步为新路径；不改变判据语义 |
| 黄金夹具的路径派生 | `_fm_golden_test.ps1` 已按 `$PSScriptRoot` 派生（P2 小批次修复）；`_switch_qwen_flavor.*` 保持在根目录 |
| `agent-cli.ps1` 的 BOM 副本（split） | 用 `REPO_ROOT` 而非 `PSScriptRoot`（§4.5） |

---

## 8. 测试策略（先验红 → 后验绿）

| 测试 | 内容 | 先验红如何成立 |
|---|---|---|
| `tests/test_shell_strict.py` | 读 `ops.yaml` 的 `shell_strict`；断言 13 执行件 prologue、2 库无 `set`、豁免表非空且命中；负向夹具（prologue 缺失 / 库含 `set -e` / 豁免未用） | 实现前运行：13 件中 9 件不满足 ⇒ FAIL |
| `tests/test_station_bin_layout.py` | 断言根目录 `_*` ⊆ 9 项白名单；`archive/station-bin-probes/` 非空；`ops.yaml` 无 `ops/station-bin/_*` 残留；无同名复制；负向夹具（临时根目录加 `_foo.sh` ⇒ FAIL） | 实现前：根目录 175 个 `_*` ⇒ FAIL |
| `tests/test_agent_cli_paths.py`（小） | 断言 `agent-cli.ps1` 全文无 `D:\RPC` / `d:\RPC` 字面（注释除外），且 5 处引用都走 `$Script:REPO_ROOT` | 实现前：5 处命中 ⇒ FAIL |
| 既有 `py-tests` | 62 → 65 个测试全绿 | — |
| `rpc_check --quick` | 新增 2 项 CHECKS 全绿；其余不退化 | — |
| CI | `shellcheck --severity=error` 覆盖 14 件；`--include=SC2310,SC2311` 定向无命中 | — |

**运行时证据（单测替代不了的部分）**：

1. 三站 `bash -n`（部署时逐件）。
2. B 站先行只读冒烟：`load-gate 1`（rc 0）、`load-mem-gate 1`、`infer-list B`、`conf-get <conf> MODEL_PATH`、`cluster-watchdog` 由 systemd timer 跑一轮后看 journal 无 ERROR。
3. `infer-load` **不做**实弹加载；以 `bash -n` + 逐命令审计 + `conf-lib` 单测覆盖写路径。
4. `ocrun` / `backup-memories.sh`：`bash -n` + 人工读一遍守卫（不实跑，避免写真实备份目录）。

---

## 9. 验收口径

| 门 | 内容 |
|---|---|
| M1 | 交付物：`ops.yaml` 两段、2 个新 CHECKS、3 个新测试、归档目录、README、CI 更新、agent-cli 5 处 |
| M2 | 先验红 → 后验绿：3 个测试各自留存 FAIL 输出 |
| M3 | 契约：§4.1/§4.2/§4.3 每条断言有对应测试或门禁 |
| M4 | 站上：`STATION_BINS` 里 9 个 shell 件三站部署（备份 + `bash -n` + md5 对账 ⇒ `gates` 36/36）；`cluster-watchdog`/`rpc-nodes`/`ocrun`/`backup-memories.sh` 按站上实际存在情况部署；B 站只读冒烟 |
| M5 | 门禁：`py-tests` 全绿、`rpc_check` 0 红、`gates` 36/36、`doclinks` 0 失效、`md-tables` 新增 0、CI 两 job 绿 |
| M6 | 不变式 N1-N7 逐条核对 |

---

## 10. 实施输入（详见 IMPLEMENTATION）

1. 先写 3 个测试并跑红（§8）。
2. #5 逐文件改造：prologue + 守卫（逐条登记在 IMPLEMENTATION §4）。
3. 8A：`git mv` → 删登记 → 加两段 yaml → 加两门禁 → 修 1 条 md 链接 + 1 条 models.yaml 文案。
4. agent-cli 5 处硬编码 → `REPO_ROOT`。
5. 部署 13 件（B 先行）→ 冒烟 → A/C。
6. 全量门禁 + CI。

---

## 11. 风险与回滚

| 风险 | 等级 | 缓解 | 回滚 |
|---|---|---|---|
| `set -e` 改变站上加载路径行为 | **高** | 逐命令审计 + 只加显式守卫；B 先行冒烟 | 单文件 `cp -a *.bak-p2big-*` 回站上 |
| 归档 164 件后有人按旧路径找文件 | 低 | README + 归档 README 写明取回流程；`station-layout` 防回迁 | `git mv` 原路返回 |
| 门禁清单搬家后静默降级 | 中 | 搬完复核每个"扫文本"门禁的报数（§6 N6） | 单提交 revert |
| `ops.yaml` 删 157 条误删在用项 | 中 | 只删 `ops/station-bin/_*` 且在归档目录存在的项；测试断言残留 0 | 单提交 revert |
| `agent-cli` 路径改动的 split 场景 | 低 | 用 `REPO_ROOT`（已有 env 兜底）；`test_cli_concurrency_guards.py` 覆盖 split | 单文件 revert |

---

## 12. 与其它 spec / ADR 的关系

- **ADR-0004**（统一管理入口）：本批不新增入口；归档是"减少管理面"，方向一致。
- **[cluster.py 模块化先例](../../docs/2026-09-23_cluster.py模块化重构_调研与方案.md)**：本批沿用其"一刀一提交 / 门面 / 扫文本清单同步 / 漏导入检查"纪律；但**不**在 `rpc_check` 上开工（另立 8B）。
- **[review-p2-small](../review-p2-small/CHECKLIST.md)**：`ops/station-bin` 身份收敛与 CI 的既有状态作为基线；本批的 prologue 会**再改** 13 件的 md5，README 需追加部署记录。
