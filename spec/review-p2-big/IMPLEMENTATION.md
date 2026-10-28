# 实施文档：原始评审 P2 大项（#5 站上 shell 严格模式 / #8A station-bin 分层）

---

id: review-p2-big-IMPLEMENTATION
type: design
version: 1.0
status: draft
date: 2026-10-28
depends: [review-p2-big-DESIGN]
upstream: null

---

> **Feature**: 把 [DESIGN](./DESIGN.md) 的 G1-G6 落成可执行的逐文件改造：13 个站上 shell 执行件的 `set -euo pipefail`、2 个库的"禁止 set"、`station-bin` 一次性探针归档、两条新门禁、`agent-cli.ps1` 5 处路径派生。
> **创建日期**: 2026-10-28
> **状态**: draft（Step 3；待 Step 4 设计评审）
> **Spec 步骤**: Step 3（IMPLEMENTATION）
> **基于设计**: [DESIGN.md](./DESIGN.md)
> **代码基线**: `8dd2f3db`（`main`；行号为该基线快照）

---

## 1. 实施范围

| # | 交付物 | 落位 | 类型 |
|---|---|---|---|
| T1 | `shell_strict` / `station_bin_layout` 两段策略 | [inventory/ops.yaml](../../inventory/ops.yaml) | 修改 |
| T2 | 13 个执行件 prologue + 守卫 | `ops/rpc-nodes`、`ops/station-bin/<13>` | 修改 |
| T3 | 2 个库钉住（不改内容，只加测试） | `model-locate.sh` / `conf-lib.sh` | 不动 |
| T4 | 探针归档目录 | `archive/station-bin-probes/` | 新增（`git mv` ≈164 件） |
| T5 | 归档 README | `archive/station-bin-probes/README.md` | 新增 |
| T6 | `ops.yaml` 删 157 条冻结登记 | 同上 | 修改 |
| T7 | `models.yaml` 1 处文案路径 | [inventory/models.yaml](../../inventory/models.yaml) | 修改 |
| T8 | `validate_shell_strict` + `check_shell_strict` | [ops/rpc_check.py](../../ops/rpc_check.py) | 修改 |
| T9 | `validate_station_layout` + `check_station_layout` | 同上 | 修改 |
| T10 | 2 条 CHECKS 注册（quick=True） | 同上 | 修改 |
| T11 | 3 个新测试 | `tests/test_shell_strict.py` / `test_station_bin_layout.py` / `test_agent_cli_paths.py` | 新增 |
| T12 | `agent-cli.ps1` 5 处路径派生 | `ops/station-bin/agent-cli.ps1` | 修改 |
| T13 | CI shellcheck 射程 | `.github/workflows/ci.yml` | 修改 |
| T14 | 站上部署与冒烟 | tdeploy（B 先行） | 部署 |
| T15 | README 部署记录 | [ops/station-bin/README.md](../../ops/station-bin/README.md) | 修改 |

**边界（不做）**：见 DESIGN §1.2；本批不新增 py 模块（两个校验函数直接落在 `rpc_check.py`，避免在 8B 拆分前制造新的 `entry_modules` 登记面）。

---

## 2. 工程约定

| 项 | 值 | 依据 |
|---|---|---|
| Shell | bash；LF；站上件 `#!/bin/bash` | `.gitattributes` |
| 严格模式写法 | 逐字 `set -euo pipefail`（顺序固定） | 便于门禁逐字断言 |
| 库 | 不得出现 `set -[eux]` | DESIGN §4.1 |
| Python | 3.12 / stdlib + pyyaml（测试） | 既有 |
| 归档 | `git mv` 保历史；不改文件内容 | DESIGN N4 |
| 登记 | `frozen_ops_scripts` 只减不增 | ops.yaml 注释 |
| 提交粒度 | 测试先红 1 提交；#5 1 提交；8A 1 提交；门禁/登记 1 提交；文档 1 提交 | cluster 先例纪律 |
| 部署 | B 先行 → 冒烟 → A/C；备份 `*.bak-p2big-YYYYMMDD` | 本批风险等级 |

---

## 3. 任务分解

### I-1 测试先红（不写实现）

1. 新建 `tests/test_shell_strict.py`：读 `inventory/ops.yaml` 的 `shell_strict`，**当前 yaml 尚无该段** ⇒ 先以"缺段"红；再补 yaml 后断言 13 件 prologue（实测只有 4 件达标）⇒ 红。
2. 新建 `tests/test_station_bin_layout.py`：根目录 175 个 `_*` ⇒ 白名单 9 ⇒ 红。
3. 新建 `tests/test_agent_cli_paths.py`：5 处 `D:\RPC` 命中 ⇒ 红。
4. 分别留存 FAIL 输出（写入 CHECKLIST 的证据列）。

### I-2 #5 逐文件改造

按 §4.1 的 prologue 表 + §4.2 的守卫规则逐件改；每件改完 `bash -n`，全部改完跑 `shellcheck`（本机无则留 CI）。

### I-3 8A 归档

按 §5 的生成规则 `git mv`；同步 §5.3 登记清理；写归档 README 与根 README 指针。

### I-4 门禁与登记

§6 的两个校验函数 + 两条 CHECKS + §5.3 的 `ops.yaml` 两段。

### I-5 `agent-cli.ps1` 路径派生

§4.6 的 5 处；`test_agent_cli_paths.py` 转绿。

### I-6 CI

§8；`test_ci_workflow.py` 的断言同步（14 件 + SC2310/SC2311 定向）。

### I-7 部署与冒烟

§9；B 先行，成功后 A/C；`gates` 36/36。

---

## 4. 逐文件改造点（#5）

### 4.1 prologue 表

| 文件 | 现状 | 目标 | 备注 |
|---|---|---|---|
| `ops/rpc-nodes` | `set -u` | `set -euo pipefail` | 6 处 and-or 列表需审 |
| `infer-load` | `set -uo pipefail` | `set -euo pipefail` | 16 and-or · 13 管道；写 conf 主路径 |
| `infer-unload` | `set -uo pipefail` | `set -euo pipefail` | 5 and-or · 4 管道 |
| `infer-list` | 无 | `set -euo pipefail` | 10 and-or · 3 管道；`hostname -s` 在 case 中（安全） |
| `llama-serve-instance` | `set -u` | `set -euo pipefail` | **3 处高危**（§4.3） |
| `rpc-serve-instance` | `set -u` | `set -euo pipefail` | 1 处 `$MODEL_PATH` 未设风险 |
| `load-mem-gate` | 无 | `set -euo pipefail` | 无 and-or；算术需默认值 |
| `wait-gtt-release` | 无 | `set -euo pipefail` | 循环外 `$AVAIL` 可能未定义（§4.3） |
| `conf-get` | `set -uo pipefail` | `set -euo pipefail` | 1 处管道 |
| `cluster-watchdog` | 无 | `set -euo pipefail` | 4 and-or · 6 管道；`sudo` 写路径 |
| `ocrun` | 无 | `set -euo pipefail` | 1 and-or |
| `backup-memories.sh` | `set -u` | `set -euo pipefail` | 无 and-or；含 sqlite/python 调用 |
| `load-gate` | `set +e` | **不变（豁免）** | `shell_strict.allow` 登记，`why` 见 DESIGN §4.1 |

### 4.2 errexit 守卫改写规则（四类）

| 形态 | 为什么在新模式下会炸 | 改法 |
|---|---|---|
| `[ -n "$X" ] && CMD`（顶层，非 if 条件） | and-or 列表的**最后一条**失败 ⇒ `-e` 触发 | 改成 `if [ -n "$X" ]; then CMD; fi` |
| `CMD1 && { ...; break; }`（循环内） | 同上：第一条失败即整表返回非 0 | 改成 `if CMD1; then ...; break; fi` |
| `VAR=$(cmd1 \| cmd2)`（顶层赋值） | 赋值语句的退出码 = 命令替换的退出码；`pipefail` 下 `grep` 无命中即 1 | 末尾 `\|\| true`；或 `\|\| echo 0`；或 `if ! VAR=$(...); then VAR=0; fi` |
| `VAR=$(( expr ))` 里含未定义/非数字 | 算术错误返回 1 | 先 `${VAR:-0}` 归一；或 `VAR=$(( ${A:-0} + ${B:-0} ))` |

> 判定口径：**只改"业务上容忍失败"的位点**；业务上不该容忍的，保持失败即中止（这正是本项的目的）。
> 每处改动在 §4.5 登记一行（文件 / 行 / 形态 / 改法 / 理由），供 Step 4 复核。

### 4.3 已知高危点（基线实测）

| 文件:行 | 现状 | 修法 |
|---|---|---|
| `llama-serve-instance:37` | `(exec 3<>...) 2>/dev/null && { exec 3>&- 3<&-; break; }` | 改 `if (exec 3<>...) 2>/dev/null; then ...; break; fi` |
| `llama-serve-instance:49` | `[ -n "${N_GPU_LAYERS:-}" ] && NGL_ARGS="-ngl ..."` | 改 `if` |
| `llama-serve-instance:24/28` | `[ -f "$MODEL_PATH" ]` 与 `RPC_TARGET="$(rpc-nodes ... \|\| true)"` | `$MODEL_PATH` 用 `${MODEL_PATH:-}`；后者已守卫 |
| `rpc-serve-instance:27` | `$(ls -d /opt/llama.cpp* ...)` 在 echo 里 | 安全（命令替换不改变 echo 退出码）；**保留** |
| `wait-gtt-release:16` | 循环后引用 `$AVAIL` | 循环前 `AVAIL=0` |
| `load-mem-gate:8` | `AVAIL=$(awk ...)` | awk 读 `/proc/meminfo` 恒成功；**保留** |
| `cluster-watchdog:19` | `sudo mkdir -p ... && sudo chown ...`（if 块内） | if 条件内的 and-or 安全；**保留** |
| `infer-load` / `infer-unload` | 现有 `\|\| true` 19 / 10 处 | **保留**（它们本来就是"容忍"标注）；新增 `-e` 后逐条复核覆盖面 |
| `infer-list` | `ssh ... 2>/dev/null` 单次探测 | 失败必须容忍（对端不可达是正常态）⇒ 加 `\|\| true` 或 `if` |

### 4.4 库（不改）

| 文件 | 断言 |
|---|---|
| `model-locate.sh` | 首 20 行无 `set -`；函数只做路径解析 |
| `conf-lib.sh` | 首 20 行无 `set -`；`conf_set_kv` 的 rc 由 caller 判 |

### 4.5 审计记录表（实施时逐条填）

| # | 文件:行 | 形态 | 改法 | 理由 |
|---|---|---|---|---|
| 1 | （示例）`llama-serve-instance:37` | `&& {}` | `if` | 连接失败是正常态（RPC 尚未就绪），不能中止服务启动 |
| … | — | — | — | — |

> Step 4 设计评审将逐条核对：**每处改写都必须能用"业务上容忍失败"解释**，否则退回（说明该失败本来就该中止）。

### 4.6 `agent-cli.ps1`（5 处）

| 行 | 现状 | 目标 |
|---|---|---|
| 473 | `$local = 'D:\RPC\ops\station-bin\_station_ready.sh'` | `$local = Join-Path $Script:REPO_ROOT 'ops\station-bin\_station_ready.sh'` |
| 517 | `Copy-Item 'D:\RPC\ops\station-bin\_slot_gate.sh' ...` | `Join-Path $Script:REPO_ROOT 'ops\station-bin\_slot_gate.sh'` |
| 3538 | `$localSm = 'D:\RPC\ops\station-bin\_oc_session_meta.sh'` | 同上 |
| 3778 | `$ledger = 'd:\RPC\ops\station-bin\agent-runs.log'` | `Join-Path $Script:REPO_ROOT 'ops\station-bin\agent-runs.log'` |
| 5115 | 同 3778 | 同上 |

> 注释里的 `d:\RPC`（L54/55/3775/5401）是**说明性文字**，不改；测试只扫**代码行**（剥 `#` 之后的部分）。

---

## 5. 8A：归档执行

### 5.1 根目录保留的 `_*`（9 项，`station_bin_layout.root_keep`）

```
_station_ready.sh  _slot_gate.sh  _oc_session_meta.sh
_fm_golden_test.ps1  _probe_fallback.ps1  _runstamp_hammer.ps1  _scrubber_coverage_test.ps1
_switch_qwen_flavor.ps1  _switch_qwen_flavor.sh
```

### 5.2 生成规则

```
movable = { ops/station-bin/<f> : f 以 "_" 开头
                                且 f ∉ root_keep
                                且 f 不在 attach-test/ 子目录 }
```

- 实施时先跑一次只读枚举，把结果写进提交信息（件数 + 首末各 3 个文件名），供复核。
- **全部 `git mv ops/station-bin/<f> archive/station-bin-probes/<f>`**；不修改内容。
- 移动后**不得**出现同名文件（根目录与归档目录）。

### 5.3 登记清理

| 文件 | 动作 |
|---|---|
| `inventory/ops.yaml` | 从 `frozen_ops_scripts` 删除全部 `ops/station-bin/_*` 根级项（≈157）；**不删除** `station_runtime` 的 3 个 `_*`（运行时件） |
| `inventory/models.yaml` | `_davidau_download.sh` 的文案路径 → `archive/station-bin-probes/_davidau_download.sh` |
| `spec/d6-agent-standard/OPEN-ISSUES.md` | `_zen_pty_pilot.sh` 的相对链接指向归档目录 |
| `archive/station-bin-probes/README.md` | 新增：来源、日期、内容边界、取回流程（`git mv` 回 `ops/` + 登记 + 过门禁） |

### 5.4 根 README

`ops/station-bin/README.md` 顶部加 3 行：

- 本目录只放**部署件 / 入口运行时件 / 在跑夹具**；
- 一次性探针已归档到 `archive/station-bin-probes/`（只读证据，不部署）；
- 新增 `_*` 根级文件必须先过 `station-layout`（白名单只有 9 项）。

---

## 6. 门禁实现

### 6.1 `validate_shell_strict(doc, read_text)`

纯函数，返回 `(bad, notes)`：

```
输入: doc = ops.yaml 的 shell_strict 段; read_text(path) -> str
断言:
  ① exec / libs / allow 三者存在且均为 list
  ② exec 每件: 前 20 行首个非注释非空行 == "set -euo pipefail"
  ③ libs 每件: 全文（剥注释后）无 r"^\s*set\s+-[eux]"
  ④ allow 每条的 file ∈ exec 且 why.strip() 非空
  ⑤ allow 未命中（该文件已严格） ⇒ bad（防腐化）
  ⑥ exec ∩ libs = ∅；路径均存在
输出: (bad: list[str], notes: list[str])  # notes 报 "执行件 N / 库 M / 豁免 K"
```

### 6.2 `validate_station_layout(doc, root_files, archive_files, frozen_paths)`

纯函数：

```
输入: doc = station_bin_layout 段; root_files = 根目录文件名集合;
      archive_files = 归档目录文件名集合; frozen_paths = ops.yaml 的 frozen 列表
断言:
  ① probes_dir 存在且 archive_files 非空
  ② root_files 中以 "_" 开头者 ⊆ root_keep
  ③ root_files ∩ archive_files 中的 `_*` 件 = ∅（README 等文档不判）
  ④ frozen_paths 中不含 "ops/station-bin/<_*>"（根级探针残留）
  ⑤ root_keep 每项都真实存在于 root_files（防白名单腐化）
输出: (bad, notes)
```

### 6.3 `inventory/ops.yaml` 两段（唯一真值）

```yaml
# #5 站上 shell 严格模式（DESIGN review-p2-big §4.1）
shell_strict:
  exec: [...13...]
  libs: [...2...]
  allow:
    - file: ops/station-bin/load-gate
      why: "报告型门禁：四条规则必须全部跑完再给结论；取数函数在逻辑或列表中被调用 ⇒ -e 本就不生效（SC2310）"

# #8A station-bin 布局（DESIGN review-p2-big §4.2/§4.3）
station_bin_layout:
  probes_dir: archive/station-bin-probes
  root_keep: [...9...]
```

### 6.4 CHECKS

| id | 标题 | fn | quick |
|---|---|---|---|
| `shell-strict` | 站上 shell 严格模式 | `check_shell_strict` | True |
| `station-layout` | station-bin 布局 | `check_station_layout` | True |

`fix` 文案必须写"下一步"（既有纪律）：如「把 prologue 改成 `set -euo pipefail` 并补显式守卫；确需豁免 ⇒ 在 `shell_strict.allow` 登记 why」。

---

## 7. 测试实现

| 测试 | 关键断言 |
|---|---|
| `test_shell_strict.py` | 真实 yaml → PASS；负向夹具：exec 缺项 / 库含 `set -e` / allow 未命中 / 同一文件双列 |
| `test_station_bin_layout.py` | 真实树 → PASS；负向夹具：根目录加 `_x.sh` / 归档空 / frozen 残留 / root_keep 失效 |
| `test_agent_cli_paths.py` | 剥注释后无 `[dD]:\\RPC`；5 处均含 `$Script:REPO_ROOT`；正例反例各 1 |

3 个测试都走「独立可跑 + `RESULT:` 行」的既有形状（`run_py_tests.py` 认 `RESULT:`）。

---

## 8. CI 更新

1. `shellcheck --severity=error` 目标增加：`ops/station-bin/ocrun`、`backup-memories.sh`、`cluster-watchdog`（12 → 15 件）。
2. **不**新增 SC2310/SC2311 门禁（实施期裁定，理由见 DESIGN §4.4）：本批 helper 谓词在 `if` 里返回码分支是刻意语义，全局门禁只会逼出 disable。
3. `test_ci_workflow.py` 的 shebang 断言自动覆盖新增 3 件；`test_ci_workflow` 无其它改动。

---

## 9. 部署与冒烟

| 步 | 动作 | 判据 |
|---|---|---|
| 1 | B 站备份 `*.bak-p2big-YYYYMMDD`（逐件 `cp -a`；核备份 md5 == 原 md5） | 备份存在 |
| 2 | `install -m 755` 到 B 站 `/usr/local/bin`（仅站上实际存在的件） | `bash -n` 逐件 0 |
| 3 | B 站只读冒烟：`load-gate 1` rc=0；`load-mem-gate 1` rc=0；`infer-list B` 出三站清单；`conf-get <conf> MODEL_PATH` 输出真实路径 | 4/4 |
| 4 | `cluster-watchdog` 由 timer 跑一轮（60s 内）后查 journal 无 `ERROR`/`Traceback` | 1 轮 |
| 5 | A/C 同法部署 | `gates` 36/36 |
| 6 | `rpc-nodes` / `ocrun` / `backup-memories.sh`：以站上 `ls -l` 为准，存在的站部署；`rpc-nodes` 额外跑 `--start` 只读？**不跑**（会起进程） | `bash -n` + md5 |

**明确不跑**：`infer-load` 实弹加载、`infer-unload` 实弹卸载、`ocrun` 真派发、`backup-memories.sh` 真备份（写真实目录）。

---

## 10. 实施顺序（TDD）

1. I-1 写 3 个测试 → 跑红（留证）。
2. I-2 #5：先改 9 个低风险件（load-mem-gate / wait-gtt-release / rpc-serve-instance / llama-serve-instance / conf-get / ocrun / backup-memories.sh / rpc-nodes / cluster-watchdog），再改 2 个大件（infer-list / infer-unload），最后改 `infer-load`。
3. I-3 8A 归档 + 登记清理。
4. I-4 门禁 + yaml 两段 → `test_shell_strict` / `test_station_bin_layout` 转绿。
5. I-5 agent-cli 路径 → `test_agent_cli_paths` 转绿。
6. I-6 CI → `test_ci_workflow` 绿。
7. 全量 `py-tests` + `rpc_check --quick`。
8. I-7 B 站部署 + 冒烟 → A/C → `gates`。
9. 全量 `rpc_check` + CI 推送。

---

## 11. 验证矩阵

| 层 | 命令 | 期望 |
|---|---|---|
| 单测 | `py tests\run_py_tests.py` | 65/65 |
| 门禁 | `py ops\rpc_check.py --only shell-strict,station-layout,scripts,doclinks,deps,syntax` | 0 红 |
| 全量 | `py ops\rpc_check.py` | 0 红（黄灯存量） |
| 站上 | `gates` | 36/36 |
| CI | push 后两 job | 绿 |

---

## 12. 回滚

| 层 | 动作 |
|---|---|
| 仓库 | 按提交 revert（测试 / #5 / 8A / 门禁各一个提交） |
| 站上 | `cp -a <file>.bak-p2big-YYYYMMDD <file>` → `bash -n` → md5 对账 |
| 归档 | `git mv archive/station-bin-probes/<f> ops/station-bin/<f>` + 恢复登记 |
