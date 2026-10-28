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
| M2 | 真站行为 | §2 | 4 | **P0** | 3 ☑ / 1 ◐（G1 待跑） |
| M3 | 默认行为零变化 | §3 | 6 | **P0** | 全 ☑ |
| M4 | 判据与边界 | §4 | 7 | **P0** | 全 ☑ |
| M5 | 门禁与回归 | §5 | 5 | **P0** | 全 ☑ |
| M6 | 残留与风险 | §6 | 6 | P1 | 6 条记录 |

---

## 1. 交付物（M1）

1. ☑ [DESIGN.md](./DESIGN.md)（含 §2 调研：仓库盘点 / 社区案例 / 容量算账）
2. ☑ [IMPLEMENTATION.md](./IMPLEMENTATION.md)（含 §4 偏差与事故如实记录）
3. ☑ 本 CHECKLIST
4. ☑ `infer-unload` alias 分支（位置参数、不 pkill、无参逐字不变）
5. ☑ `reclaim_and_unload` / `_reclaim_containers` 的 `alias` 形参（默认值保旧语义）
6. ☑ `_capacity_ok` 纯函数 + `_guard_capacity` 编排（exit 4）
7. ☑ `cluster.py load --keep`、`cluster.py unload --alias/--station`
8. ☑ 测试：`test_cluster_pure.py` **19 条** + `test_infer_unload_alias.py` 9 条

## 2. 真站行为（M2）

| # | 判据 | 结论 |
|---|---|---|
| G1 | B 站 `load gpt-oss-20b` → `load qwen3.8-27b-mtp-b --keep`，两个 `llama-server@` 同时 active、8080 与 18080 各自 `/health` 200 | ◐ **未跑** —— 需先卸生产 deepseek（B 站 84/125.8 GB），属破坏性操作，须用户择时 |
| G2 | 容量不足 ⇒ exit 4 且**未发**任何 `systemctl stop` / `docker rm` / `rpc-nodes --start` | ☑ 单测（`_cap("NO_FIT")==4` / `"UNKNOWN"==4` / `ok=False==4`）；顺序由 `cmd_load` 中「预检在分派之前」保证 |
| G3 | `infer-unload <alias>` 只停该别名（静态 9 条判据） | ☑ ALL PASS |
| G4 | 反向冲突预检仍先于容量门 | ☑ 真站只读复核 `A + gpt-oss-120b ⇒ 3` |

## 3. 默认行为零变化（M3）

1. ☑ `cmd_load` 不带 `--keep` ⇒ 回收调用与基线逐字相同（`reclaim_and_unload(station)`）
2. ☑ `cmd_unload()` 无参 ⇒ 三站全停，顺序 B 先 / A·C 并行不变
3. ☑ `infer-unload` 无参路径逐字保留（`@*` 通配 + pkill 仍在）
4. ☑ `_load_rpc` 未改（`--keep` 在入口 exit 1）
5. ☑ `cmd_load_on`（web 按站路径）未改
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

## 5. 门禁与回归（M5）

| 命令 | 读数 |
|---|---|
| `tests\run_py_tests.py` | ☑ **70/70** |
| `tests\test_cluster_pure.py` | ☑ ALL PASS |
| `tests\test_infer_unload_alias.py` | ☑ 9/9 |
| `rpc_check.py --quick` | ☑ 41 绿 / 2 黄 / 0 红 |
| `deps` / `facade` | ☑ 未新增模块级依赖；门面新增 2 个名字可达（⊇ 296 基线） |

## 6. 残留与风险（M6）

1. 真站共存未跑（G1）⇒ 达标结论仅覆盖「机制正确」，**不覆盖**「两模型真能同时 READY」
2. `18080` 未进 `ports.yaml` ⇒ `ports` 门禁站上对账会黄（P2）
3. 客户端只认 `127.0.0.1:8080` ⇒ 第二个模型暂只能 `ssh + curl :18080`（P3）
4. 端口撞车无前置判据 ⇒ 靠 `llama-server` 绑定失败 + 健康检查超时**响亮失败**（P2）
5. worker 站禁止 `--keep`（D-2）⇒ 「单站多模型」当前只覆盖 head 站/独立站
6. 事故已恢复：误发 `glm-5.3-flash` 已由 `load deepseek-v4-flash-0731` 复原；三条加固判据见 IMPLEMENTATION §4

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

