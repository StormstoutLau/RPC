# 验收 Checklist：原始评审 P2 大项（#5 站上 shell 严格模式 / #8A station-bin 分层）

---

id: review-p2-big-CHECKLIST
type: design
version: 1.2
status: accepted
date: 2026-10-28
depends: [review-p2-big-IMPLEMENTATION, review-p2-big-DESIGN]
upstream: null

---

> **Feature**: 按 [DESIGN](./DESIGN.md) 与 [IMPLEMENTATION](./IMPLEMENTATION.md) 验收 #5（13 个站上执行件 `set -euo pipefail` + 2 个库钉住 + `shell-strict` 门禁）与 #8A（164 个一次性探针归档 + 9 项根目录白名单 + `station-layout` 门禁），外加 `agent-cli.ps1` 5 处路径派生。
> **创建日期**: 2026-10-28
> **状态**: accepted（2026-10-28：本地 + 站上 + CI 全绿）
> **Spec 步骤**: Step 5（验收）
> **基于实施**: [IMPLEMENTATION.md](./IMPLEMENTATION.md)
> **基于设计**: [DESIGN.md](./DESIGN.md)
> **基于调研**: [P2 大项社区外部锚点调研](../../docs/research/2026-10-28_原始评审P2大项_社区外部锚点调研.md)
> **代码基线**: `8dd2f3db`（`main`）→ 实施 `522ddf90` → 验收修正 `78bbcfd8`（均已推送）
> **审查轮次**: 第 1 轮单测先验红→后验绿（2026-10-28）· 第 2 轮结构/登记 · 第 3 轮三站部署与冒烟 · 第 4 轮全量门禁 + CI（run `40633787470` 两 job 绿）

---

## 0. 验收门总览

| 门 | 内容 | 章节 | 项数 | 级别 | 结论 |
|---|---|---|---|---|---|
| M1 | 交付物 | §1 | 15 | **P0** | 全 ☑ |
| M2 | 先验红 → 后验绿 | §2 | 5 | **P0** | 全 ☑ |
| M3 | 契约与边界 | §3 | 12 | **P0** | 全 ☑ |
| M4 | 站上部署与冒烟 | §4 | 10 | **P0** | 全 ☑ |
| M5 | 门禁与回归 | §5 | 8 | **P0** | 全 ☑ |
| M6 | 不变式 | §6 | 7 | **P1** | 全 ☑ |
| M7 | 残留、回滚与边界 | §7 | — | P1/P3 | 5 条记录 |

**明确不在本轮验收范围**：`#8B` 拆 `rpc_check.py`、`#8C` 拆 `agent-cli.ps1`、`cluster.py` 再抽取、非 `_` 前缀一次性件、站上实弹加载/卸载、行数上限门禁（详见 DESIGN §1.2）。

---

## 1. M1 交付物

| # | 交付物 | 落位 | 判据 | 状态 | 证据 |
|---|---|---|---|---|---|
| T1 | `shell_strict` / `station_bin_layout` | [inventory/ops.yaml](../../inventory/ops.yaml) | `exec` **12** + `allow` **1** = 13 件；`libs` **2**；`root_keep` **9**；`allow.why` 非空 | ☑ | 脚本读数：`exec 12 libs 2 allow 1 keep 9 frozen 29` |
| T2 | 12 个执行件严格模式 | `ops/rpc-nodes` + `ops/station-bin/<12>` | 首个非注释行 == `set -euo pipefail` | ☑ | `shell-strict`：`执行件 12（严格 12）` |
| T3 | 2 个库不设选项 | `model-locate.sh` / `conf-lib.sh` | 全文无 `set +-...` | ☑ | 同上门禁（库 2 项无 FAIL） |
| T4 | 归档目录 | `archive/station-bin-probes/` | 164 件、全部跟踪 | ☑ | `git ls-files` = **164**；根目录 `_*` = **9** |
| T5 | 归档 README | `archive/station-bin-probes/README.md` | 来源/边界/取回流程 | ☑ | 文件存在；根 README 已双向链接 |
| T6 | 登记清理 | `inventory/ops.yaml` | `frozen_ops_scripts` 192 → **29** | ☑ | 删 163 条；`frozen 29`；`scripts` 门禁 `冻结存量 29` |
| T7 | `models.yaml` 文案路径 | [inventory/models.yaml](../../inventory/models.yaml) | 指向归档路径 | ☑ | L165 `archive/station-bin-probes/_davidau_download.sh` |
| T8 | `validate_shell_strict` / `check_shell_strict` | [ops/rpc_check.py](../../ops/rpc_check.py) | 纯函数 + CHECKS；`fix` 含下一步 | ☑ | L7002/L7076；CHECKS 条目带防腐化提示 |
| T9 | `validate_station_layout` / `check_station_layout` | 同上 | 5 条断言 | ☑ | L7090/L7132；范围 = git 跟踪（未跟踪残留不误报） |
| T10 | 两条 CHECKS（quick） | 同上 | `CHECKS` 50 → **52** | ☑ | `checks 52`；`['shell-strict','station-layout']` |
| T11 | 3 个新测试 | `tests/test_shell_strict.py` / `test_station_bin_layout.py` / `test_agent_cli_paths.py` | 独立可跑、带 `RESULT:` | ☑ | `py-tests 65/65`；三者各 `ALL PASS` |
| T12 | `agent-cli.ps1` 5 处路径 | [agent-cli.ps1](../../ops/station-bin/agent-cli.ps1) | L473/517/3538/3778/5115 走 `$Script:REPO_ROOT` | ☑ | `test_agent_cli_paths` ALL PASS |
| T13 | CI 射程 | `.github/workflows/ci.yml` | shellcheck 12 → **15** 件 | ☑ | 脚本读数 `targets 15`；SC2310/2311 门禁**不加**（DESIGN §4.4 裁定） |
| T14 | 站上部署 | 三站 `/usr/local/bin` | 备份 + `bash -n` + md5；`gates` 36/36 | ☑ | B 11 / A 11 / C 10 件；备份 `*.bak-p2big-20261028`；`gates 36/36` |
| T15 | README 更新 | [station-bin README](../../ops/station-bin/README.md) | 根目录范围 + 归档指针 + 当前 md5 | ☑ | 顶部布局块 + “当前（2026-10-28）”段 |

---

## 2. M2 先验红 → 后验绿

| # | 验收项 | 先验红（实测） | 后验绿 | 状态 |
|---|---|---|---|---|
| F1 | `test_shell_strict.py` | 判据未实现 ⇒ `AttributeError`；补 yaml 后 `执行件 12（严格 0）` | `执行件 12（严格 12）` | ☑ |
| F2 | 严格模式真实文件 | 12 件全部不达标（`set -u` / `-uo` / 无 set） | 12/12 达标；`load-gate` 豁免命中 | ☑ |
| F3 | `test_station_bin_layout.py` | 根目录 **164** 个 `_*` 越白名单；归档空；登记残留 169 条 | 根目录 `_*` **9** · 归档 **164** · 白名单 **9** | ☑ |
| F4 | 布局负向夹具 | 临时加 `_stray.sh` / 归档空 / 登记残留 / 白名单腐化 / 同名 ⇒ 各自 FAIL | 5 条夹具全 PASS（判据非恒真） | ☑ |
| F5 | `test_agent_cli_paths.py` | 代码面 **5** 处 `D:\RPC`；4 组引用未走 REPO_ROOT | ALL PASS（含“注释里的路径不判”） | ☑ |

---

## 3. M3 契约与边界

> 负向项由单测夹具执行（临时数据，不改真文件）；每条在 `test_shell_strict` / `test_station_bin_layout` 输出里有对应 `PASS` 行。

| # | 接口/边界 | 判据 | 状态 |
|---|---|---|---|
| C1 | 唯一豁免 | `load-gate` 保留 `set +e`，`why` 非空 | ☑ |
| C2 | 豁免防腐化 | 豁免文件已严格 ⇒ 报「豁免未命中」 | ☑ 夹具 PASS |
| C3 | 库边界 | 库注入 `set -e` ⇒ FAIL | ☑ 夹具 PASS |
| C4 | 执行件边界 | 删 prologue ⇒ FAIL | ☑ 夹具 PASS |
| C5 | 双列 | 同时进 `exec` 与 `libs` ⇒ FAIL | ☑ 夹具 PASS |
| C6 | 路径存在性 | 不存在的 exec 路径 ⇒ FAIL | ☑ 夹具 PASS |
| C7 | 根目录白名单 | 9 项外任何 `_*` ⇒ FAIL | ☑ 夹具 PASS |
| C8 | 白名单腐化 | `root_keep` 指向不存在文件 ⇒ FAIL | ☑ 夹具 PASS |
| C9 | 归档非空 | 空归档 ⇒ FAIL | ☑ 夹具 PASS |
| C10 | 登记残留 | 加回 `ops/station-bin/_old.sh` ⇒ FAIL | ☑ 夹具 PASS |
| C11 | 同名复制 | 根/归档同名 `_*` 件 ⇒ FAIL | ☑ 夹具 PASS |
| C12 | `agent-cli` 代码面 | 剥注释后无 `[dD]:\RPC` | ☑ ALL PASS |

---

## 4. M4 站上部署与冒烟

### 4.1 部署

| # | 判据 | 状态 | 证据 |
|---|---|---|---|
| D1 | 三站备份 `*.bak-p2big-20261028`（B 11 / A 11 / C 10） | ☑ | `ls` 计数：11 / 11 / 10 |
| D2 | `install -m 755` + 逐件 `bash -n` rc=0 | ☑ | 部署脚本逐件打印 `OK <file> <md5>`，语法失败即 `exit 6`（未触发） |
| D3 | B 站只读冒烟 4/4 | ☑ | 见 §4.2 |
| D4 | A/C 部署；`gates` **36/36** | ☑ | A 11 件、C 10 件；`gates` 可达 3/3 · 一致 36/36 |
| D5 | watchdog oneshot | ☑ | B `rc=0` + journal `Finished`；A `rc=0`；C 无 unit，直接跑二进制 `rc=0`（GTT WARN 属预期） |
| D6 | `rpc-nodes` / `ocrun` / `backup-memories.sh` | ☑ | `ocrun` 三站；`rpc-nodes` A/B（C 无此件）；`backup-memories.sh` 三站均无（手动件，不部署） |

### 4.2 B 站只读冒烟

| # | 命令 | 实测 | 状态 |
|---|---|---|---|
| S1 | `load-gate 1` | `[OK]` / `ALL PASS`，rc=0（need=1G avail=42G used=82G） | ☑ |
| S2 | `load-mem-gate 1` | `OK: MemAvailable 42G >= 1G + 12G`，rc=0 | ☑ |
| S3 | `infer-list B` | rc=0，**14** 行，含 `davidau-q38-27b-q4k` / `all-minilm-l6-v2-embedding` | ☑ |
| S4 | `conf-get /etc/llama-instances/glm-5.3-flash.env MODEL_PATH` | 输出 `/data/models/gguf/unsloth/GLM-5.3-Flash-GGUF/GLM-5.3-Flash-UD-IQ4_XS.gguf`，rc=0 | ☑ |

### 4.3 明确不跑

`infer-load` 实弹加载、`infer-unload` 实弹卸载、`ocrun` 真派发、`backup-memories.sh` 真备份。

---

## 5. M5 门禁与回归

| # | 门禁 | 判据 | 读数 | 状态 |
|---|---|---|---|---|
| G1 | `py-tests` | 65/65（62 既有 + 3 新增） | `结果: 65/65 通过 · 用时 58.8s` | ☑ |
| G2 | `rpc_check --quick` | 0 红；两项新门禁绿 | `绿灯 41 · 黄灯 2 · 红灯 0` | ☑ |
| G3 | 全量 `rpc_check` | 0 红 | `绿灯 49 · 黄灯 3 · 红灯 0` | ☑ |
| G4 | `gates` | 36/36 | `可达 3/3 站 · 站上件一致 36/36` | ☑ |
| G5 | `scripts` | 未登记 0；冻结 29 | `扫描 67 · 入口 4 · 拆分模块 7 · 站上运行时 27 · 冻结存量 29 · 未登记 0` | ☑ |
| G6 | `doclinks` | 0 失效 | `3962 条 · 已登记例外 2 · 失效 0`（改 3 条归档链接） | ☑ |
| G7 | `md-tables` | 新增 0 | `表 2467 张 · 违规 28（冻结 28 · 新增 0）` | ☑ |
| G8 | CI（push 后） | 两 job 绿 | run [`40633787470`](https://github.com/StormstoutLau/RPC/actions/runs/40633787470)：`py-tests` ✓ · `shellcheck` ✓（首跑 `40633143267` 因夹具时钟粒度假阴性，已修 `78bbcfd8`） | ☑ |

---

## 6. M6 不变式

| # | 不变式 | 落点 | 状态 |
|---|---|---|---|
| N1 | `STATION_BINS` 12 件路径不变 | `gates 36/36`；无路径改名 | ☑ |
| N2 | 站上件内容变更仅限 prologue + 登记守卫 | 见 §8 审计表（逐文件） | ☑ |
| N3 | 库不设选项 | `shell-strict` 库断言 | ☑ |
| N4 | 归档件只 `git mv`，内容零改动 | `git diff --cached -M --summary`：**164** 条 rename、**0** 条非 100% | ☑ |
| N5 | `frozen_ops_scripts` 只减不增 | 192 → 29 | ☑ |
| N6 | 扫文本门禁清单同步 | `scripts` / `syntax` / `doclinks` / `gates` / `mirror`（手册计数 50→52）全部复跑通过 | ☑ |
| N7 | 不新增 daemon / 子命令 / 入口 | diff 无新 `.service`、无新 CLI 入口；新增仅测试/归档 README/spec | ☑ |

---

## 7. M7 残留、回滚与边界

| # | 项 | 状态 | 说明 |
|---|---|---|---|
| R-1 | 回滚（仓库） | 备用 | 按提交 revert（测试 / #5 / 8A / 门禁 / 文档） |
| R-2 | 回滚（站上） | 备用 | `cp -a <file>.bak-p2big-20261028 <file>` → `bash -n` → md5 |
| R-3 | 回滚（归档） | 备用 | `git mv` 回 `ops/station-bin/` + 恢复登记 |
| R-4 | 归档后静态覆盖 | 已订正 | `syntax` 仍扫全部 tracked（按扩展名）；仅 `scripts` 治理计数下降 |
| R-5 | `load-gate` 豁免 | 已记录 | 报告型门禁；`allow.why` 写明；改语义须重审 |
| R-6 | 非 `_` 前缀一次性件 | 边界 | `repro-*.sh` 等仍在根目录（`REPRO-RUNBOOK.md` 引用）；另立 |
| R-7 | #8B / #8C | 边界 | `rpc_check` / `agent-cli` 体量未降（另立 spec） |

---

## 8. #5 守卫审计表（对应 N2）

| 文件 | prologue | 守卫改写（业务上容忍失败） |
|---|---|---|
| `ops/rpc-nodes` | `set -u` → 严格 | 4 处 `[ ] &&` → `if`（`node_selected` / `wait_port` / 过滤器命中 / 存活探测） |
| `infer-load` | `-uo` → 严格 | 6 处 `&&` → `if`；4 处取数加 `\|\| true`（ds4 别名 / `grep -c` / GTT / 端口与密钥解析）；`fi \|\| { exit 7; }` 保留显式出口 |
| `infer-unload` | `-uo` → 严格 | 4 处 `&&` → `if`；2 处 `\|\| true`（远端 `was` / GTT 取数） |
| `infer-list` | 无 → 严格 | 9 处 `&&` → `if`；3 处 `\|\| true`（`find` / `peer_scan` / 文件计数） |
| `llama-serve-instance` | `set -u` → 严格 | 2 处 `&&` → `if`（RPC 等待、`-ngl`）；回退告警改 `if` |
| `rpc-serve-instance` | `set -u` → 严格 | 仅 prologue（原有 `\|\| { exit 1; }` 安全） |
| `load-mem-gate` | 无 → 严格 | 仅 prologue |
| `wait-gtt-release` | 无 → 严格 | prologue + `AVAIL=0` 初始化（`-u` 下循环外引用） |
| `conf-get` | `-uo` → 严格 | 仅 prologue（`command -v \|\| true` 已有） |
| `cluster-watchdog` | 无 → 严格 | 4 处 `\|\| true`（`inst_port` / ACTIVE / GTT / 对端 ssh）+ 2 处 WARN `if`；**远端探测改引用型 heredoc**（修掉 `$1` 本地展开的潜伏 bug） |
| `ocrun` | `set -u` → 严格 | `cmd; rc=$?` → `if 成功/否则取 rc`（`-e` 下原写法会在赋值前中止） |
| `backup-memories.sh` | `set -u` → 严格 | 2 处轮换/清单管道加 `\|\| true`（无备份时 `ls` rc≠0） |
| `load-gate` | **不变（豁免）** | 报告型门禁：四条规则必须跑完再给结论 |

---

## 9. 验收结论

**通过**（2026-10-28）。

- **M1-M6** 全部 ☑；**M5 G8** 由 CI run `40633787470` 闭环（`py-tests` + `shellcheck` 两 job 绿）。
- 关键读数：`py-tests 65/65` · `quick 41/2/0` · `full 49/3/0` · `gates 36/36` · `scripts 未登记 0 / 冻结 29` · `doclinks 0 失效` · `md-tables 新增 0`。
- **过程中的真实收获（两个，都是“静默失败”同族）**：
  1. 开 `-u` 后 `cluster-watchdog` 的远端探测当场暴露「单引号串内嵌 `awk '{print $1}'` ⇒ `$1` 本地展开」的潜伏缺陷 —— 部署前修复并重新冒烟。
  2. CI 首跑 `g170②` 在 Windows runner 上暴露夹具的**时钟粒度**假阴性（`.run-marker` 与产物同秒 ⇒ `find -newer` 判不更新）—— 显式错开三档 mtime（`78bbcfd8`）后本地与 runner 一致。
- **提交**：实施 `522ddf90`（195 文件，含 164 条 100% rename）· 验收修正 `78bbcfd8`；均已推送。
