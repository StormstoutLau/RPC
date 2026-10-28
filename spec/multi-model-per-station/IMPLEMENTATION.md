# 实施记录：单站多模型共存 P0（容量门）+ P1（alias 级卸载）

---

id: multi-model-per-station-IMPLEMENTATION
type: design
version: 1.0
status: in-review
date: 2026-10-28
depends: [multi-model-per-station-DESIGN]
upstream: null

---

> **Feature**: 按 [DESIGN](./DESIGN.md) 落 P0 容量门与 P1 alias 级卸载；`--keep` 是唯一开关，默认路径零变化。
> **创建日期**: 2026-10-28
> **状态**: in-review（代码面 + 单测 + 门禁已过；**真站共存实测未跑**，见 §5）
> **Spec 步骤**: Step 3（实施）→ Step 4（设计评审，待）→ Step 5（[CHECKLIST](./CHECKLIST.md)）
> **代码基线**: `8031a406`
> **实施提交**: 本文件所在提交（未推送）

---

## 1. 改动清单

| 文件 | 改动 | 性质 |
|---|---|---|
| [ops/station-bin/infer-unload](../../ops/station-bin/infer-unload#L6-L37) | 新增 `ALIAS="${1:-}"` 与 **alias 分支**（只停 `llama-server@<alias>` / 本地+远端 `rpc-server@<alias>`，不 pkill，`exit 0`）；`RPC_USER/SSHX/NODES_ENV_F/NODES_LIST` 上移到文件头供两种模式共用；无参路径**逐字保留** | 新增能力 + 重构（无参行为不变） |
| [ops/cluster_runtime.py](../../ops/cluster_runtime.py#L774-L832) | `_reclaim_containers(station, alias=None)`：非容器 alias ⇒ `skipped: keep`，不 `docker rm`；`reclaim_and_unload(station, alias=None)`：alias 非 None ⇒ `infer-unload <alias>`（`sh_single_quote` 包裹） | 签名扩展（默认值保持旧语义） |
| 同上 | 新增 `_capacity_ok(verdict)`（纯函数）与 `_guard_capacity(station, alias)`（exit 4）；容器模型直接放行并打印 `CAPACITY n/a` | 新增 |
| 同上 | `cmd_load(..., force=False, keep=False)`：① `keep and is_rpc` ⇒ exit 1；② 反向冲突预检后、任何分派前 ⇒ `_guard_capacity`；③ `_load_container_model` / `_cmd_load_c` / 通用路径的回收改传 `alias if keep else None` | 接线 |
| 同上 | `cmd_unload_on(station, alias=None)` / `cmd_unload(alias=None)`：alias 透传到三站（顺序不变：B 先，A/C 并行） | 签名扩展 |
| [ops/cluster.py](../../ops/cluster.py#L246-L296) | `load` 解析 `--keep`；`unload` 解析 `--alias` / `--station`（未知参数 exit 1）；门面重导出 `_capacity_ok` / `_guard_capacity`；用法与 `--keep` 说明 | CLI |
| [tests/test_cluster_pure.py](../../tests/test_cluster_pure.py#L489-L591) | 新增 11 条：容量判据 1 · `_guard_capacity` 4 · `--keep` RPC 拒绝 1 · alias 透传 1 · 容器步跳过/照常 1 · `unload --alias` 1（另含 O-178 段的安全网） | 测试 |
| [tests/test_infer_unload_alias.py](../../tests/test_infer_unload_alias.py) | 新文件 9 条静态判据：位置参数、alias 分支停 `@${ALIAS}`（不是 `@*`）、alias 分支**不含 pkill**、无参路径逐字保留 | 测试 |
| [ops/cluster_const.py](../../ops/cluster_const.py#L108-L117) | **P0 补强**：新增 `STATION_RESERVED_GIB = 8.0`（站级预留，理由=10-26 两次 device-lost 都发生在余 15~24G） | 新增常量 |
| [ops/cluster_runtime.py](../../ops/cluster_runtime.py#L1129-L1176) | **P0 补强**：`_uma_fit`（UMA 单池 `alloc = total − used − reserved`）+ `_station_gtt`（读 sysfs GTT 实账）；`_guard_capacity` 加**第 2 道**判据（estimate 之后），读不到 GTT ⇒ 回退并留痕 | 新增 + 接线 |
| [ops/cluster.py](../../ops/cluster.py#L155-L159) | 门面重导出 `_uma_fit` / `_station_gtt` / `STATION_RESERVED_GIB` | 重导出 |
| [ops/cluster_runtime.py](../../ops/cluster_runtime.py#L1235-L1312) | **P2**：`_port_clash`（纯函数）· `_model_port`（读站上 conf 的 `PORT`）· `_station_model_ports`（列站上在跑别名各自的 conf PORT）· `_guard_port`（撞口 ⇒ exit 5）；`cmd_load` 在容量门之后接线（仅 `--keep`） | 新增 + 接线 |
| [inventory/ports.yaml](../../inventory/ports.yaml#L83-L99) | **P2**：登记 `18080` 暴露面（`mode: on_demand`；注释写明「本表只登记端口号，alias→port 真值在站上 conf」） | 真值表 |
| [docs/派生视图_端口分配.md](../../docs/派生视图_端口分配.md) | `derived_view.py --emit` 重渲染（ports.yaml 改动后必须重出，否则 `derived-view` 门禁红） | 生成物 |
| [ops/cluster_runtime.py](../../ops/cluster_runtime.py#L1297-L1308) | **P2-余**：`_engine_port(station, alias, explicit)`（显式 > conf > 站默认）；`_build_infer_load_cmd(..., port=)`；`_guard_port(..., port=)`；`cmd_load(..., port=)` 校验 1–65535；`_cmd_load_c` / `_load_rpc` / `_load_ds4_pp` / `cmd_load_on` / 通用路径的**健康探测改按 alias 取端口** | 新增 + 接线 |
| [ops/cluster_flow.py](../../ops/cluster_flow.py#L58-L78) | **P2-余**：`cmd_e2e` 从「三站各探 :8080」改为「探每个在跑别名各自的端口」，无别名才回退站默认 | 改写 |
| [ops/station-bin/infer-load](../../ops/station-bin/infer-load#L208-L217) | **P2-余**：`--port` **落 conf**（`_set_conf_key PORT`），理由同 `--engine`：单元会重新 source conf；ds4 命名空间跳过 | 站上脚本 |
| [ops/cluster.py](../../ops/cluster.py#L265-L268) | `load --port N` 解析 + 用法；门面重导出 `_engine_port` | CLI |

**未改**（刻意）：`cmd_load_on`（web 按站路径，不支持 `--keep`）、`_load_rpc`（保持全站回收）、客户端 baseURL（P3）。

---

## 2. 先验红（逐字）

```
FAIL  位置参数解析存在（ALIAS="${1:-}"）
FAIL  有 alias 分支（if [ -n "$ALIAS" ]）
...
AttributeError: module 'cluster' has no attribute '_capacity_ok'
```

实现后：

```
RESULT: ALL PASS · 失败: 无            # test_infer_unload_alias.py
RESULT: ALL PASS                       # test_cluster_pure.py
```

---

## 3. 验证读数

| 命令 | 读数 |
|---|---|
| `py -3.12 tests\run_py_tests.py` | **70/70 通过**（62.8s；基线 69 + 新文件 1） |
| `py -3.12 tests\test_cluster_pure.py` | ALL PASS（新增 11 条全绿） |
| `py -3.12 tests\test_infer_unload_alias.py` | ALL PASS（9/9） |
| `py -3.12 ops\rpc_check.py --quick` | 41 绿 / 2 黄 / **0 红**（`doclinks` 因缺 CHECKLIST 曾红 1 次，补文件后复绿） |
| 真站只读复核 | `A + gpt-oss-120b ⇒ 3`（O-178 反向冲突仍生效）、`A + deepseek ⇒ 0` |
| 真站 GTT 读数（P0 补强） | `A ok=True used=103.1 total=117.2 alloc=6.1` · `B 78.3/117.2 alloc=30.9` · `C 24.6/117.2 alloc=84.6`（GiB，已扣预留 8） |
| 真站端口读数（P2） | `B 在跑 {'deepseek-v4-flash-0731': 8080}` · `qwen3.8-27b-mtp conf PORT=18080` · `gpt-oss-20b conf PORT=8080` ⇒ 端口门：qwen 放行（0）、gpt-oss-20b 撞 deepseek（5） |
| 站上脚本部署（P2-余） | A/B/C 三站 `infer-load` 37320B · `infer-unload` 5978B，与仓库**逐字节同尺寸**；`bash -n` 通过后才 install；备份 `*.bak-o179-20261029` |
| 真站 alias 卸载验证 | B 站 `infer-unload __nonexistent_alias__` ⇒ 只打 alias 分支日志、**空动作**；随后 `llama-server@deepseek` 仍 active、`:8080 {"status":"ok"}` |

---

## 4. 偏差与事故（如实记录）

1. **⚠ 测试误发真实加载（已恢复）**：首版用例写 `cmd_load(..., None, None, None, True)`，而 `cmd_load` 第 5 个位置参数是 `force`（不是 `keep`）⇒ `force=True` 越过了 O-178 反向冲突预检，**真的向 B 站派发了 `glm-5.3-flash` 加载**，把生产 `deepseek-v4-flash-0731` 换掉。
   - 发现方式：`test_cluster_pure` 超时（真加载要等健康检查），随后只读探测发现 B/A 已是 glm。
   - 恢复：`cluster.py load deepseek-v4-flash-0731` 重新加载（B head + A worker，1M ctx）。
   - 加固（**这三条现在是判据的一部分**）：
     · `keep=True` 必须**关键字**传参；
     · 该用例把 `_load_rpc` 钉成哨兵（返回 99 并记录），判据 = `rc == 1 and not _rpc_calls`；
     · `cmd_unload` 用例先断言 `cluster_runtime.reclaim_and_unload is <桩>` 再调用，桩没落到实现模块就**不调用**（返回 99）。
2. **三处既有桩需跟进签名**：`_reclaim_containers` 多了可选 `alias`，测试里 3 个 `lambda st:` 桩改成 `lambda st, al=None:`（否则 `TypeError`）。这是**签名扩展的必然连带**，不是行为改动。
3. **容量门只覆盖 gguf 模型**：容器模型（halogen）直接放行（DESIGN §4.2 / §8-3）。属登记过的缺口，不是遗漏。
4. **⚠ 站上脚本漂移（P2-余 期间发现，已修）**：P1 的 `infer-unload <alias>` 只进了仓库，**没部署** —— 三站 `/usr/local/bin/infer-unload` 仍是 2026-10-28 09:04 的旧版，而旧版**不解析参数**。后果不是「功能没生效」，而是**语义反了**：`cluster.py unload --alias X` 会退化成**全站清空**。已按「备份 → sftp → `bash -n` → install → grep 核对」部署到 A/B/C（`infer-load` 同批，因 `--port` 落 conf 也在站上脚本里），并做了一次**空动作验证**（`infer-unload __nonexistent_alias__` 后 deepseek 仍 active）。
   ⇒ 教训（已写进 CHECKLIST §6）：**改站上脚本 ≠ 改仓库**；凡 `cluster.py` 依赖的新语义，落地清单必须含「部署 + 站上核对」两步，否则本地门禁全绿而线上行为相反。

---

## 5. 未做（交 Step 5 / 后续阶段）

| # | 项 | 为什么没做 |
|---|---|---|
| 1 | **真站共存实测**（B 站先 `load gpt-oss-20b`，再 `load qwen3.8-27b-mtp-b --keep`，两个 `/health` 均 200） | 需要**先卸掉生产 deepseek**（B 站当前 84 GB / 125.8 GB，装不下这两者）⇒ 属破坏性操作，须由用户择时执行 |
| 2 | `18080` 未登记 `inventory/ports.yaml` | P2；现在登记会把「未实测端口」写进真值表 |
| 3 | 客户端寻址第二模型 | P3 |
| 4 | worker 站叠加第二个 head | DESIGN D-2：`--keep` 对 RPC 直接拒绝 |
