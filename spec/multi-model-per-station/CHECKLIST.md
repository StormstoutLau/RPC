# 验收 Checklist：单站多模型共存 P0（容量门）+ P1（alias 级卸载）

---

id: multi-model-per-station-CHECKLIST
type: design
version: 1.0
status: in-review
date: 2026-10-28
depends: [multi-model-per-station-IMPLEMENTATION, multi-model-per-station-DESIGN]
upstream: null

---

> **Feature**: 按 [DESIGN](./DESIGN.md) 与 [IMPLEMENTATION](./IMPLEMENTATION.md) 验收 P0 容量门与 P1 alias 级卸载；`--keep` 默认关闭 ⇒ 旧语义逐字保留。
> **创建日期**: 2026-10-28
> **状态**: in-review（代码面 + 单测 + 门禁全绿；**真站共存实测未跑**，见 §2-G1）
> **Spec 步骤**: Step 5（验收）
> **代码基线**: `8031a406` → 本提交（未推送）

---

## 0. 验收门总览

| 门 | 内容 | 章节 | 项数 | 级别 | 结论 |
|---|---|---|---|---|---|
| M1 | 交付物 | §1 | 8 | **P0** | 全 ☑ |
| M2 | 真站行为 | §2 | 4 | **P0** | 全 ☑ |
| M3 | 默认行为零变化 | §3 | 6 | **P0** | 全 ☑ |
| M4 | 判据与边界 | §4 | 23 | **P0** | 全 ☑ |
| M5 | 门禁与回归 | §5 | 6 | **P0** | 全 ☑ |
| M6 | 残留与风险 | §6 | 6 | P1 | 6 条记录 |

---

## 1. 交付物（M1）

1. ☑ [DESIGN.md](./DESIGN.md)（含 §2 调研：仓库盘点 / 社区案例 / 容量算账）
2. ☑ [IMPLEMENTATION.md](./IMPLEMENTATION.md)（含 §4 偏差与事故如实记录）
3. ☑ 本 CHECKLIST
4. ☑ `infer-unload` alias 分支（位置参数、不 pkill、无参逐字不变）
5. ☑ `reclaim_and_unload` / `_reclaim_containers` 的 `alias` 形参（默认值保旧语义）
6. ☑ `_capacity_ok` 纯函数 + `_guard_capacity` 编排（exit 4）
7. ☑ `cluster.py load --keep`、`load --station A/B/C`（可组合）、`load --port N`、`cluster.py unload --alias/--station`
8. ☑ 测试：`test_cluster_pure.py` **22 条** + `test_infer_unload_alias.py` 9 条

## 2. 真站行为（M2）

| # | 判据 | 结论 |
|---|---|---|
| G1 | B 站同跑两个模型：`gpt-oss-20b` + `qwen3.8-27b-mtp` 同时 active，各自 `/health` 200 | ☑ **已完成（2026-10-29 02:47:47）** —— B 站 `load gpt-oss-20b --port 18081` → `load qwen3.8-27b-mtp --station B --keep --engine /opt/llama.cpp/llama-server`。终态：`llama-server@qwen3.8-27b-mtp` running + unsloth `gpt-oss-20b` 同在；`ss` 见 **18080**(llama-server) 与 **18081**(unsloth) 各自 LISTEN；GTT **44.2 / 117.2 GiB**（两模型同时常驻）；`/health` 18080 = `{"status":"ok"}`、18081 = unsloth 代理（`{"detail":"API endpoint not found"}`，该后端无 /health）。容量门读数 `alloc 97.4 GiB ≥ need 30.4 GiB`；端口门 18080 vs 18081 无冲突。**附带**：C 站同时存在 `halogen` 容器(:8080) + `llama-server@qwen3.8-27b-mtp`(:18080)，GTT 52.0/117.2 —— 容器与进程共存也实测成立。⚠ 首跑两处倒逼修复见 IMPLEMENTATION §4-5/6/7（站内 `--keep`、`--station` 吞 `--engine`、B 站引擎路径悬空） |
| G2 | 容量不足 ⇒ exit 4 且**未发**任何 `systemctl stop` / `docker rm` / `rpc-nodes --start` | ☑ 单测（`_cap("NO_FIT")==4` / `"UNKNOWN"==4` / `ok=False==4`）；顺序由 `cmd_load` 中「预检在分派之前」保证 |
| G3 | `infer-unload <alias>` 只停该别名（静态 9 条判据） | ☑ ALL PASS |
| G4 | 反向冲突预检仍先于容量门 | ☑ 真站只读复核 `A + gpt-oss-120b ⇒ 3` |

## 3. 默认行为零变化（M3）

1. ☑ `cmd_load` 不带 `--keep` ⇒ 回收调用与基线逐字相同（`reclaim_and_unload(station)`）
2. ☑ `cmd_unload()` 无参 ⇒ 三站全停，顺序 B 先 / A·C 并行不变
3. ☑ `infer-unload` 无参路径逐字保留（`@*` 通配 + pkill 仍在）
4. ☑ `_load_rpc` 未改（`--keep` 在入口 exit 1）
5. ☑ `cmd_load_on`（web/`--station` 按站路径）**默认路径不变**（`reclaim_and_unload(station)`）；仅新增可选 `port` / `keep`（G1 需要）
6. ☑ 基线 69 个测试全过（现 70 个）

## 4. 判据与边界（M4）

1. ☑ `FITS` / `TIGHT` 放行，与 `cmd_estimate` 同口径
2. ☑ `UNKNOWN` 不放行（判不了 ≠ 通过）
3. ☑ `est["ok"] == False`（缺 conf / 缺元数据）不放行
4. ☑ 容器模型跳过 estimate 并打印 `CAPACITY n/a`（登记为 P2 缺口）
5. ☑ alias 经 `sh_single_quote` 进站上命令（防注入）
6. ☑ `keep` + `is_rpc` ⇒ exit 1（head/worker GTT 同池未算清）
7. ☑ 同一 alias 的重载不算「叠加」：`--keep` 停掉同名实例后再加载（`_reclaim_containers` 对非容器别名返回 `skipped: keep`）
8. ☑ **P0 补强**：`_uma_fit` 四条边界（空站放行 / 已占 84G 拒绝 / 预留吃掉余量 / 已用超总量夹 0）
9. ☑ **P0 补强**：GTT 第 2 道 —— estimate 说 FITS 但 GTT 不足仍拒；GTT 足够放行；GTT 读不到回退 verdict；estimate 已 NO_FIT 时不因 GTT 空闲而放行
10. ☑ **P2**：`_port_clash` 四条（撞口点名 / 不撞 / 空表 / 两个别名同口）
11. ☑ **P2**：端口门三种结局 —— 撞口 exit 5 · 不撞放行 · 判不了（ssh 失败）留痕放行
12. ☑ **P2**：`ports.yaml` 登记 18080 后 `ports` 与 `inventory` 门禁仍绿；派生视图已重渲染（`--emit`）
13. ☑ **P2-余**：`--port` 非法/非数字 ⇒ exit 1（不碰网络）；合法值落进 `infer-load` 命令；未给则不出现
14. ☑ **P2-余**：`_engine_port` 三级优先级（显式 > conf > 站默认）；`_guard_port` 用显式端口仍能拦撞口
15. ☑ **P2-余**：三站脚本已部署且**逐字节同尺寸**；`infer-unload <bogus>` 真站空动作（deepseek 未受影响）
16. ☑ **keep 二修**：同别名重载真站通过 —— `load gpt-oss-20b --station B --keep` 连跑两次，第二次 12:28:38 停旧实例、12:29:00 READY（22s），deepseek(:8080) 全程 `{"status":"ok"}`
17. ☑ **keep 二修**：外部占用**早退** —— 直接 `infer-load qwen3.8-27b-mtp --keep --port 18081`（被 gpt-oss-20b 占着）⇒ `RC=1` 立即返回、打印占用者 cmdline、**未杀**对方、**未改** qwen conf（仍 `PORT="18080"`）
18. ☑ **keep 二修**：静态护栏 [test_infer_load_keep.py](../../tests/test_infer_load_keep.py) 12 条（只停本别名 / 按 MODEL_PATH 认领 / `pkill -P` / 不整体 pkill / 端口判定 / 早退 / 不 wait_gtt / 非 keep 路径不变 / PORT 落盘在门之后）
19. ☑ `_station_model_ports` 能解析 `PORT="18080"` 带引号形态（真站复核 `B → {'deepseek…': 8080}`）
20. ☑ **unload 二修**：alias 模式按 `MODEL_PATH` 认领 —— 真站 `unload --alias gpt-oss-20b` 命中 `pid=1460299 1460471`（studio + 子进程），18081 立刻消失、GTT 90→78.3、deepseek 仍 `{"status":"ok"}`
21. ☑ **unload 二修**：负例 `infer-unload qwen3.8-27b-mtp`（没在跑）⇒ 只打「未发现该模型的非 systemd 实例」，不误杀；alias 分支仍**不含全量 pkill**（[test_infer_unload_alias.py](../../tests/test_infer_unload_alias.py) 13 条）
22. ☑ **就绪循环早退（systemd）**：B 站把 qwen conf 的 `LLAMA_SERVER_BIN` 临时改成 `/bin/false` ⇒ `infer-load qwen3.8-27b-mtp --backend llama-single --keep` **0.411s** 返回 `RC=1`，打印 `Result=exit-code` / `ExecMainStatus=1` + journal 尾部（此前空等 15min 且只报"健康检查超时"）；事后 conf 已还原、`reset-failed`、deepseek 仍 `{"status":"ok"}`
23. ☑ **就绪循环早退（unsloth）**：C 站把 `MODEL_PATH` 临时指向不存在的 gguf ⇒ studio 5s 内退出，脚本 **10s** 返回 `RC=1` 并打 `ERROR: unsloth studio 已退出（端口未就绪…）` + 日志尾部（`GGUF file not found`）；**同时暴露并修掉**「裸 curl + `$? -eq 0`」在 `set -e` 下以 curl rc=7 静默终止脚本的旧缺陷（[test_infer_load_ready.py](../../tests/test_infer_load_ready.py) 16 条）

## 5. 门禁与回归（M5）

| 命令 | 读数 |
|---|---|
| `tests\run_py_tests.py` | ☑ **72/72** |
| `tests\test_cluster_pure.py` | ☑ ALL PASS |
| `tests\test_infer_unload_alias.py` | ☑ 13/13 |
| `tests\test_infer_load_ready.py` | ☑ 16/16（就绪循环早退 + `$?` 反模式） |
| `rpc_check.py --quick` | ☑ 41 绿 / 2 黄 / 0 红 |
| `deps` / `facade` | ☑ 未新增模块级依赖；门面新增 2 个名字可达（⊇ 296 基线） |

## 6. 残留与风险（M6）

1. ~~真站共存未跑（G1）~~ ⇒ **已跑通**（2026-10-29 02:47，§2-G1），机制与真站两条都覆盖
2. ~~`18080` 未进 `ports.yaml`~~ ⇒ ✅ 已登记（P2）
3. 客户端只认 `127.0.0.1:8080` ⇒ 第二个模型暂只能 `ssh + curl :18080`（P3 网关解决；**P3 前不要改客户端**）
4. ~~端口撞车无前置判据~~ ⇒ ✅ 已有 `_guard_port`（exit 5）；判不了（ssh 失败）仍留痕放行
5. worker 站禁止 `--keep`（D-2）⇒ 「单站多模型」当前只覆盖 head 站/独立站
6. 事故已恢复：误发 `glm-5.3-flash` 已由 `load deepseek-v4-flash-0731` 复原；三条加固判据见 IMPLEMENTATION §4
7. **配置漂移无护栏**：B 站 qwen conf 的引擎路径指向不存在的旧目录，`load` 不会预检 ⇒ status=127 后**空等 15min**。已登记为待做（IMPLEMENTATION §5-5），当前靠 `--engine` 显式指定绕过
8. **站上脚本与仓库是两份**：`infer-load` / `infer-unload` 改完必须部署 + 站上核对（本次两次踩到，见 IMPLEMENTATION §4-4/5）

---

## 7. 进度记录（append-only）

| 时间 | 事件 | 读数 |
|---|---|---|
| 2026-10-28 | 调研 + DESIGN（仓库盘点 / 社区案例 / 容量算账） | B 站 GTT 125.8G；gpt-oss-20b 11.5G + qwen3.8-27b 29.5G = 41G 权重 |
| 2026-10-28 | P0 容量门 + P1 alias 级卸载落地（先验红 → 实现） | `run_py_tests` **70/70** · `rpc_check --quick` **41 绿 / 2 黄 / 0 红** |
| 2026-10-28 23:22 | ⚠ 测试误发 `glm-5.3-flash`（`keep` 位置参数写成 `force`），生产 deepseek 被换 | 只读探测确认 B/A 已变 glm |
| 2026-10-28 23:31 | 恢复完成：`load deepseek-v4-flash-0731` | B `READY ✓ :8080`（1M ctx）· A `rpc-server@deepseek` · C qwen 容器全程未动 |
| 2026-10-28 | 提交 `8541c04b`（未推送） | 9 文件 +730/−38；工作区干净 |
| 待办 | G1 真站共存（`gpt-oss-20b` + `qwen3.8-27b-mtp-b --keep`） | 需先卸生产 deepseek（B 站 84/125.8G），**等用户择时** |
| 2026-10-28 | GPUStack 可复用性分析落档（[docs/research](../../docs/research/2026-10-28_gpustack可复用性分析.md)） | 三块可复用：UMA 口径 / 端口簿记 / 路由语义；整体不可 pip 复用 |
| 2026-10-28 | **P0 补强**：`_uma_fit` + `_station_gtt` + `STATION_RESERVED_GIB=8` | 真站读数 A 103.1/117.2（alloc 6.1）· B 78.3（30.9）· C 24.6（84.6）GiB |
| 2026-10-29 | **P2 端口预留记录**：端口门（exit 5）+ `ports.yaml` 登记 18080 + 派生视图重渲染 | 真站：B 在跑 deepseek@8080；qwen 18080 放行(0)；gpt-oss-20b 8080 撞 deepseek(5) |
| 2026-10-29 | **P2-余**：`load --port N`（infer-load 落 conf）+ 6 处探测改按 alias 取 + `cmd_e2e` 逐别名探 | 单测 ALL PASS；`--port` 落 conf 让 systemd 单元路径也生效 |
| 2026-10-29 | ⚠ **发现站上脚本漂移并修复**：P1 的 `infer-unload <alias>` 未部署 ⇒ `unload --alias` 会退化成全站清空 | 三站已部署（备份 `*.bak-o179-20261029`）+ 空动作验证（deepseek 仍 active） |
| 2026-10-29 02:08 | G1 准备：`unload --station B` 后 `load gpt-oss-20b --port 18081` | READY 02:08:14，`--port` 落 conf=18081；GTT 11.8 |
| 2026-10-29 02:25 | G1 首跑 **失败**（配置缺陷，非代码）：B 的 qwen conf 引擎指向不存在的 `/home/scott-lau/llama.cpp/build/bin/llama-server` ⇒ status=127，且**空等 15min** 健康超时 | 首跑同时暴露「外层 `--keep` 被站内 `[3]` 互斥段打回原形」⇒ 补 `infer-load --keep` 并部署（38587B/三站） |
| 2026-10-29 02:47:47 | **G1 通过**：`load qwen3.8-27b-mtp --station B --keep --engine /opt/llama.cpp/llama-server` | B 站 18080 `{"status":"ok"}` + 18081 unsloth 同时在线；GTT **44.2/117.2 GiB** |
| 2026-10-29 02:48 | 收尾：`unload --alias qwen --station C` + `unload --station B`，随后重载生产 deepseek | 见下方还原记录 |
| 2026-10-29 02:55:16 | **生产已还原**：`load deepseek-v4-flash-0731` | B `READY :8080`（1M ctx, 6m37s）· A `rpc-server@deepseek` worker · C 仅 `halogen` 容器（:8080 `{"status":"ok","model":"halogen-qwen3.8-flash-next"}`，GTT 24.6/117.2） |
| 2026-10-29 12:22 | keep 二修前首跑：**直接 exit 1**（`set -e`+pipefail 让空 grep 的赋值失败） | 修复：探测管道加 `\|\| true` |
| 2026-10-29 12:25 | keep 二修验证：同别名重载仍失败，`ss` 显示占用者 pid 是 `unsloth` | 查明：studio argv 里**没有** `(<alias>)`，归属判据改为 **MODEL_PATH** |
| 2026-10-29 12:29 | **同别名重载通过**：第二次 `--keep` 停旧启新 22s | 期间发现 `--port` 被拒仍落 conf ⇒ 推迟到端口门之后；连带修引号解析 |
| 2026-10-29 12:35 | **外部占用早退通过**：`RC=1`、不杀他人、conf 不变 | 测试实例已按 MODEL_PATH 精确清理，deepseek 未受影响 |
| 2026-10-29 13:04 | **unload 二修通过**：`unload --alias gpt-oss-20b` 真的停掉了 unsloth（此前"成功但什么都没停"） | 命中 studio+子进程两个 pid；18081 关闭、GTT 78.3、deepseek `{"status":"ok"}`；负例不误杀 |
| 2026-10-29 15:07 | **就绪循环早退（systemd）**：B 站临时 `/bin/false` ⇒ **0.411s** `RC=1`，打出 `Result=exit-code` / `ExecMainStatus=1` + journal 尾部（此前空等 15min 且只报超时） | conf 已还原、`reset-failed`、deepseek `{"status":"ok"}` |
| 2026-10-29 15:19 | **就绪循环早退（unsloth）**：C 站临时无效 gguf ⇒ studio 5s 退出、脚本 **10s** `RC=1` 并直出 `GGUF file not found`；顺带修掉「裸 curl + `$?`」在 `set -e` 下以 rc=7 静默终止脚本的旧缺陷 | 三站部署（备份 `*.bak-o179-ready2-20261029`，44096B/`a423db86`）；C 站 conf 已还原、halogen 与 :8080 正常 |

