# 审查验收 Checklist：原始评审 P2 小批次（#6 / #9 / CI）

---

id: review-p2-small-CHECKLIST
type: design
version: 1.0
status: accepted
date: 2026-10-28
depends: [review-p2-small-IMPLEMENTATION, review-p2-small-DESIGN]
upstream: null

---

> **Feature**: 收掉 P2 里改动小、确定性高的三项——#6 两份遗留 systemd 单元的键段位、#9 活跃运行时身份收敛、CI（`py-tests` + `shellcheck`）。
> **创建日期**: 2026-10-28
> **状态**: 已验收（第 1 轮单测先验红→后验绿；第 2 轮三站部署/真站只读；第 3 轮全量门禁；第 4 轮 CI 首跑三修后两 job 全绿）
> **Spec 步骤**: Step 5（验收）
> **基于实施**: [IMPLEMENTATION.md](./IMPLEMENTATION.md)
> **基于设计**: [DESIGN.md](./DESIGN.md)
> **基于调研**: [P2 小批次社区外部锚点调研](../../docs/research/2026-10-27_原始评审P2小批次_社区外部锚点调研.md)
> **代码基线**: `49425f19`（`main`，已推送；本轮改动提交见 §7 R-1）
> **审查轮次**: 第 1 轮单测（2026-10-28）· 第 2 轮三站部署 + 真站只读（2026-10-28）· 第 3 轮全量门禁（2026-10-28）· 第 4 轮 CI 首跑（2026-10-28）

---

## 0. 验收门总览

| 门 | 内容 | 章节 | 项数 | 级别 |
|---|---|---|---|---|
| M1 | 交付物 | §1 | 14 | **P0** |
| M2 | 功能 + 先验红证据 | §2 | 9 | **P0** |
| M3 | 接口与边界 | §3 | 8 | **P0** |
| M4 | 真站 / 部署 | §4 | 9 | **P0** |
| M5 | 门禁与回归 | §5 | 7 | **P0** |
| M6 | 不变式 | §6 | 6 | **P1** |
| M7 | 残留与回滚 | §7 | — | P1/P3 |

**明确不在本轮验收范围**：

- #5 `set -euo` 扫荡、#8 拆大文件/分目录（另立大 spec）。
- 两份遗留单元的部署/启用（非活单元，只改仓库快照）。
- CI 首跑**修复过程**的逐次细节（结果见 §7 R-1；本轮只验收最终形态）。
- 179 个冻结探针、历史文档、`agent-cli-smoke.sh`（白名单）。

---

## 1. M1 交付物

| # | 判据 | 证据 | 结果 |
|---|---|---|---|
| M1-1 | 两份遗留单元段位修正 | [llama-server.service](../../ops/llama-server.service#L1-L8) · [rpc-server.service](../../ops/rpc-server.service#L1-L7) | ☑ |
| M1-2 | `SERVICE_USER` 单点 + 面板 URL 改 IP | [cluster_const.py](../../ops/cluster_const.py#L29-L34) · L193-198 | ☑ |
| M1-3 | `cluster.py` 从 `cluster_const` 导入 `SERVICE_USER` | [cluster.py](../../ops/cluster.py#L148-L152) · L2237 | ☑ |
| M1-4 | `infer-load` 身份/路径收敛（含 L556-557） | [infer-load](../../ops/station-bin/infer-load#L18) · L309-310/343/352/366/501/556-557 | ☑ |
| M1-5 | `infer-unload` 身份/路径收敛 | [infer-unload](../../ops/station-bin/infer-unload#L21-L29) | ☑ |
| M1-6 | `infer-list` NODE 去 `.local` | [infer-list](../../ops/station-bin/infer-list#L30-L34) | ☑ |
| M1-7 | `cluster-watchdog` `SERVICE_USER`/`PEER` 收敛 | [cluster-watchdog](../../ops/station-bin/cluster-watchdog#L7-L22) | ☑ |
| M1-8 | `agent-cli.ps1` workspace 根动态 | [agent-cli.ps1](../../ops/station-bin/agent-cli.ps1#L41-L43) | ☑ |
| M1-9 | CI workflow | [.github/workflows/ci.yml](../../.github/workflows/ci.yml) | ☑ |
| M1-10 | #6 测试 | [test_systemd_units.py](../../tests/test_systemd_units.py) | ☑ |
| M1-11 | #9 测试 | [test_identity_literals.py](../../tests/test_identity_literals.py) | ☑ |
| M1-12 | CI 测试 | [test_ci_workflow.py](../../tests/test_ci_workflow.py) | ☑ |
| M1-13 | station-bin README 登记 | [README.md](../../ops/station-bin/README.md#L22-L36) | ☑ |
| M1-14 | 本 CHECKLIST | 本文件 | ☑ |

---

## 2. M2 功能 + 先验红证据

| # | 判据 | 先验红 | 后验绿 | 结果 |
|---|---|---|---|---|
| M2-1 | #6 两份单元 `StartLimitIntervalSec` 在 `[Unit]` | 4 FAIL（两文件 × 段位） | **11 PASS / 0 FAIL** | ☑ |
| M2-2 | #6 负向夹具：键在 `[Service]` 可判出 | — | PASS | ☑ |
| M2-3 | #6 `rpc-server@.service` 未被改坏 | — | PASS（`[Unit]` 有、`[Service]` 无） | ☑ |
| M2-4 | #9 活跃清单 0 命中 | 7 FAIL（6 文件 + SERVICE_USER） | **13 PASS / 0 FAIL** | ☑ |
| M2-5 | #9 负向夹具（已知 host 可判出） | — | PASS（≥2 命中） | ☑ |
| M2-6 | #9 注释行不误报 | — | PASS | ☑ |
| M2-7 | #9 白名单（smoke 不在清单） | — | PASS | ☑ |
| M2-8 | CI workflow 结构合规 | 1 FAIL（文件不存在） | **3 PASS / 0 FAIL** | ☑ |
| M2-9 | CI 负向夹具（缺权限/jobs） | — | PASS（≥2 problems） | ☑ |

**先验红留存**：

- #6：`llama-server.service [Unit] 有 StartLimitIntervalSec` FAIL；`[Service] 无` FAIL；`rpc-server.service` 同型 2 FAIL。
- #9：`cluster_const.py`（3 处 URL）· `infer-load`（L18/309/310/343/352/556/557）· `infer-unload`（L21）· `infer-list`（3 行 NODE）· `cluster-watchdog`（L9）· `agent-cli.ps1`（L42/43）· `SERVICE_USER` 缺失。
- CI：`.github/workflows/ci.yml 存在` FAIL。

---

## 3. M3 接口与边界

| # | 判据 | 证据 | 结果 |
|---|---|---|---|
| M3-1 | 单元 `Restart`/`RestartSec` 仍在 `[Service]` | #6 测试 4 PASS | ☑ |
| M3-2 | 站上 bash 用 `$(id -un)` / `$HOME` | `infer-load`/`infer-unload`/`infer-list` diff | ☑ |
| M3-3 | `cluster-watchdog` 不用 `id -un`（root oneshot） | `SERVICE_USER="${SERVICE_USER:-scott-lau}"` | ☑ |
| M3-4 | `agent-cli.ps1` `Get-TargetHost` 保留 `.local`（O-124 真值源） | L262-266 · L878 | ☑（F-6 边界） |
| M3-5 | 单元 `User=`/`Group=` 不动 | 两份单元 diff 仅段位/头注 | ☑ |
| M3-6 | `STATIONS` 三处 `user:` 保留（唯一真值） | `cluster_const.py` L29-31 | ☑ |
| M3-7 | `agent-cli-smoke.sh` 未改 | git diff 无该文件 | ☑ |
| M3-8 | 冻结探针/历史文档未改 | git status 范围 | ☑ |

---

## 4. M4 真站 / 部署

| # | 判据 | 实测 | 结果 |
|---|---|---|---|
| M4-1 | 三站 `infer-load` md5 一致 | `891165f3840363ee0b6cd561bd86a059`（A/B/C） | ☑ |
| M4-2 | 三站 `infer-unload` md5 一致 | `0f1844a6c051c2ba6b9d19ce6688e98d`（A/B/C） | ☑ |
| M4-3 | 三站 `infer-list` md5 一致 | `98c084c4e21e074c261325a5a6de7bf4`（A/B/C） | ☑ |
| M4-4 | `cluster-watchdog` A/B 变体正确 | B/C `183c22b0f3e9130bb7b3c33ca7509bd9`；A `6abcd44f3195734026defd27b612d8fc` | ☑ |
| M4-5 | A 站 watchdog `PEER=192.168.10.32`；B 站 `192.168.10.33` | 站上 `grep '^PEER='` | ☑ |
| M4-6 | 站上 `bash -n` 通过 | 4 件 × 3 站部署时均 rc=0 | ☑ |
| M4-7 | `infer-list B` / `infer-list A` 能扫三站 | B 站输出 `AB`/`B` 位置；A 站同 | ☑ |
| M4-8 | 两份遗留单元仍非活 | A `rpc-server.service` disabled/inactive；B `llama-server.service` disabled/inactive | ☑ |
| M4-9 | 备份齐全 | 4 件 × 3 站 `*.bak-p2small-20261027` | ☑ |

**备注**：`cluster-watchdog` 不在 `STATION_BINS`（`gates` 不校验），故 A/B 变体差异是**预期**，不是漂移；README 已登记。

---

## 5. M5 门禁与回归

| # | 判据 | 实测 | 结果 |
|---|---|---|---|
| M5-1 | `py-tests` | **62/62 通过**（新增 3） | ☑ |
| M5-2 | `rpc_check` 全量 | **PASS · 47 绿 / 3 黄 / 0 红** | ☑ |
| M5-3 | `gates` | 站上件一致 **36/36** · 最小余量 6G | ☑ |
| M5-4 | `ps1-golden` | `FM_GOLDEN_TEST pass=663 fail=0` | ☑ |
| M5-5 | `doclinks` | 353 篇 / 3897 链接 / 失效 0 | ☑ |
| M5-6 | `md-tables` | 新增违规 **0**（存量冻结 28） | ☑ |
| M5-7 | `doc-status` / `spec-untested` / `secrets` / `syntax` / `scripts` | 全 PASS | ☑ |
| M5-8 | CI 实跑（GitHub Actions） | run `40593489402`：`py-tests 62/62`（windows-2022）· `shellcheck 0.9.0` 无 error（ubuntu-24.04） | ☑ |

**3 条黄灯均为存量**：`evidence`（37 条可重放 gap，存量）· `memory-gates`（引擎侧 `adhoc-notes-flat`，本仓关不了）· `stations`（`claude.mkt` 已登记漂移 `claude-plugins-official`）。

---

## 6. M6 不变式

| # | 判据 | 结果 |
|---|---|---|
| M6-1 | 活单元不动（只改仓库快照） | ☑ |
| M6-2 | 段位唯一（`[Unit]` 有、`[Service]` 无） | ☑ |
| M6-3 | 身份分域（bash `id -un` / Python `STATIONS` / PS 常量 / unit 部署身份） | ☑ |
| M6-4 | 不碰冻结面（smoke/archive/探针/历史文档） | ☑ |
| M6-5 | CI 无 secret / 无 SSH | ☑（结构测试 + 全文无 `secrets.`） |
| M6-6 | 不新增管理入口（无新 `cluster.py` 子命令） | ☑ |

---

## 7. M7 残留与回滚

| # | 项 | 状态 | 处置 |
|---|---|---|---|
| R-1 | CI 首跑（两个 job） | **已闭环** | 首跑两 job 红（`SC1071` / Windows cp1252）⇒ 二跑 `py-tests` 曝出「干净 checkout」三条（`tmp/` 缺失、`agent-chain.json` 未入库、夹具写死 `d:\RPC`）⇒ 逐条修；三跑仍红（runner 无 `Get-FileHash`）⇒ 改 .NET SHA256。终跑 run [40593489402](https://github.com/StormstoutLau/RPC/actions/runs/40593489402)：`py-tests 62/62`（windows-2022）· `shellcheck 0.9.0` 无 error（ubuntu-24.04）· 全绿。提交 `c574ac87` / `aabf8c68` / `d8ae5510` / `658dca70` |
| R-2 | `systemd` 单元 `User=`/`Group=` | 已记录边界 | systemd 不能 env 展开；换机统一改 4 文件 |
| R-3 | `agent-cli.ps1` `Get-TargetHost` `.local` | 已记录边界（F-6） | O-124 反查真值源；黄金夹具兜底 |
| R-4 | `cluster-watchdog` A/B 变体 | 已记录 | README 写明 A `PEER=192.168.10.32` |
| R-5 | `cluster-watchdog` 不在 `STATION_BINS` | 存量 | 不在本批扩 `gates` 射程；README 记录 md5 |
| R-6 | 回滚 | 可用 | 单文件 `git checkout`；站上 `cp -a *.bak-p2small-20261027`；CI 删除 workflow |

---

## 8. 结论

**验收通过**：M1-M6 全绿，M7 全项闭环（CI 首跑经三修后两 job 全绿）。#6 为仓库快照修正、#9 活跃运行时身份收敛、CI workflow 均已落地并有先验红/后验绿、三站证据与 CI 实跑结果。

**尚未闭环（不阻塞）**：

1. 两份遗留单元仍为历史快照（按设计不部署）。
2. #5/#8 仍待另立大 spec。
