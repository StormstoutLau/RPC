# DEV-LOG-009: llama.cpp v0.2.0 升级执行（UPGRADE_SOP 首次实战）

> **日期**: 2026-08-27 ~ 08-28
> **Feature**: 按 UPGRADE_SOP.md 执行 9859 → v0.2.0 两站原子升级
> **结果**: ✅ 升级成功，pp512 +47%，tg128 +2.6%，API 冒烟通过

---

## 1. 升级前后性能对比（llama-bench，同参数，RPC 双机）

| 指标 | 9859 基线 | v0.2.0 | 变化 |
|------|----------|--------|------|
| pp512 (prompt 处理) | 96.61 ± 9.41 t/s | **141.87 ± 0.15 t/s** | **+47.0%** |
| tg128 (生成) | 19.64 ± 0.11 t/s | **20.15 ± 0.10 t/s** | **+2.6%** |
| 方差 | pp 波动 ±9.4 | pp 波动 ±0.15 | 稳定性大幅提升 |
| bench 总耗时 | 305s | 298s | -2% |

- 参数：MiniMax-M2.7 Q4_K_S，`--rpc 10.10.10.1:50052 -ngl 999 -t 16 -b 512 --n-cpu-moe 8 -fa on`，`-r 2`
- 日志：`bench_9859_20260827_232616.log` / `bench_v020_20260828_001910.log`（B 站 `~/llama-distributed/logs/`）
- API 冒烟：`/health` ok、`content: 'API_PONG'`、finish stop（V020_PONG 用例同过）
- 附注：源码 tarball 构建（无 .git），`--version` 显示 `0.2.0-dev (build 0, commit unknown)`，属预期；SOP 建议后续用 git clone 获得正式 build 号

**结论**：prefill 收益（+47%）符合社区报告（新版 Vulkan FA/MMQ 优化主要利好 pp）；tg 微增 2.6% —— 社区 MTP 1.7-2.2x 需换 MTP 权重模型才可解锁，当前 MiniMax-M2.7 无 MTP 头，纯内核优化的 tg 收益有限（符合预期，避免过度归因）。

## 2. SOP 执行记录与偏差

| SOP 步骤 | 执行 | 偏差 |
|---------|------|------|
| 1 停服务 | ✅ 两站进程清零 | 无 |
| 2 B 站构建 | ✅ ccache 加持 2.5 分钟完成 | ⚠️ 偏差 1: GitHub 直连仅 49-64 KB/s，clone 不可行 → 主控站下载 tarball 经 LAN scp（见发现 1） |
| 3 分发校验 | ✅ tar MD5 一致 + A 站 83/83 MANIFEST 校验 | 无 |
| 4 原子切换 | ✅ A 先 B 后，巡检指纹一致 | ⚠️ 偏差 2: 首次切换失败，v0.2.0 二进制 RUNPATH 内嵌构建目录绝对路径（见发现 2） |
| 5 冒烟 | ✅ bench + API 双冒烟 | 无 |
| 6 收尾 | ✅ 9859 目录保留（回滚目标在位） | 无 |

## 3. 新发现（记入发现日志）

### 发现 1（网络层）：GitHub 限速的绕行方案实战
- **现象**: B 站直连/codeload/ghfast 镜像全部 49-64 KB/s；A 站 mihomo 代理节点失效（google 204 也超时）
- **解法**: 主控站（有可用代理）浏览器下载 tarball → LAN scp 到 B 站（35MB 秒级）→ B 站解压编译
- **教训**: **升级 SOP 网络路线增加"主控站中转"通道**；应急后备（A 站 codeload 直下）实测同样受限速，不可依赖
- **状态**: 已绕过；SOP 已更新认知

### 发现 2（构建层）：v0.2.0 RUNPATH 指向构建目录（9859 无此问题）
- **现象**: 新编译的 `llama-cli` RUNPATH = `/home/scott-lau/build/llama-v0.2.0/bin:`（绝对路径），部署到 `/opt` 后 `libllama-*-impl.so` 解析失败；9859 的 RUNPATH 是可移植的 `$ORIGIN`
- **根因推测**: 新版 CMake 默认（或 GGML_BACKEND_DL 组合下）把构建目录写入 RUNPATH；tarball 源码无 .git，`0.2.0-dev` 状态可能也相关
- **两层修复**: ① patchelf 44 个主二进制不够——`libllama-cli-impl.so` **自身 NEEDED `libllama-server-impl.so`**（新版二进制内部依赖链），② 最终对全部 73 个 ELF 逐一 patchelf `--set-rpath '$ORIGIN'` 后通过
- **固化**: fix_runpath_v2.sh 已入 D:\RPC\scripts\，**未来每次升级构建后必须跑此脚本**（或调研 CMake 侧 `CMAKE_BUILD_RPATH_USE_ORIGIN=ON` 一步到位，待下轮验证）
- **状态**: 已修复

### 发现 3（测量层）：locale 陷阱
- `md5sum -c` 在中文 locale 输出"成功"而非"OK"，`grep -c ': OK'` 得 0 —— 首次误读"0/83 通过"
- **处置**: md5_verify.sh 按 `成功|: OK` 双匹配；教训：校验脚本勿依赖英文输出

## 4. 当前集群状态

- 两站：`/opt/llama.cpp → llama.cpp-v0.2.0`（83 文件，MANIFEST 一致，巡检指纹一致）
- 9859 版本目录保留（回滚目标，一条 `ln -sfn` 分钟级回退）
- API 服务运行中：`http://192.168.1.15:8080`（MiniMax-M2.7 Q4_K_S）
- A 站 RPC：PID 14853，v0.2.0 后端加载正常（GFX1151 / KHR_coopmat / uma 识别齐全）

## 5. 下一步

1. **tg 提速转 Tier 2**：换 DeepSeek-V4-Flash-0731 + MTP（B 站已有 MXFP4 分片）或找 MiniMax MTP 权重版 —— tg 的 1.7-2x 在模型层不在内核层
2. 调研 `CMAKE_BUILD_RPATH_USE_ORIGIN=ON` 替代 patchelf（下次构建验证）
3. 提速报告 Tier 1.2-1.5 参数试验（`--n-cpu-moe 0`、KV q8_0、`--parallel 1`）—— 现在有了干净的 v0.2.0 基线
4. `rpc_protocol` 字段：新版日志不再打印 "Starting RPC server vX.Y.Z"，改由冒烟验证代替协议核对（SOP 认知更新）

## 6. 产物索引

| 产物 | 位置 |
|------|------|
| 升级 SOP（本次执行的依据） | D:\RPC\spec\vulkan-version-control\UPGRADE_SOP.md |
| 基线/升级后 bench 日志 | B 站 ~/llama-distributed/logs/bench_9859_* / bench_v020_* |
| build / assemble / fix_runpath_v2 / deploy / switch 脚本 | D:\RPC\scripts\ |
| 源码 tarball | 主控站 D:\RPC\llama.cpp-0.2.0.tar.gz + B 站 ~/llama.cpp-v0.2.0.tar.gz |

---

# 【追加】第 4 次 UPGRADE_SOP 实战：`master-91f6a6cf` → `master-23b0202a`（2026-10-12）

> **本文件自此成为「UPGRADE_SOP 各次实战」的连续日志**（首篇 = v0.2.0，见上）。
> **日期**: 2026-10-12 · **Feature**: vulkan-version-control · **授权**: Scott「执行升级 做好风险规避 回退 按照建议执行」→「按照 sop 执行升级」
> **结果**: ✅ **升级成功**（三站 `/opt/llama.cpp` = `llama.cpp-master-23b0202a`，`0.6.0-dev`）；★ **但同批的 `-sm tensor` 形态验证 = No-Go** ⇒ 生产**维持 `-sm layer`**。

## 1. 升级前后（同会话 A/B，`-sm layer` 档，V4-Flash）

| 指标 | 旧 `91f6a6cf`（9/10） | 新 `23b0202a` | 变化 |
|------|---------------------|---------------|------|
| 加载 | ✅ 390 s | ✅ 360 s | −7.7% |
| **prefill**（同一条 412-tok prompt） | 135.74 t/s | **182.42 t/s** | **+34.4%** |
| **decode**（max_tokens=512 ×3 中值） | 14.00 t/s | 13.80 t/s | **−1.4%** |
| 固定 prompt ×5 | 5/5 逐次可比 | 5/5 逐次可比 | 一致 |
| `GGML_ASSERT` / 崩溃 | 0 | 0 | 一致 |

★ 收益来源 = **#26610**（async graph_compute + LRU graph cache + 2D 传输）—— **其收益在 layer 档同样兑现，且兑现在 prefill 侧**（对齐 A2 实测：layer 档 38.7 命令/token，prefill 每 batch 命令数远多于 decode）。

## 2. ★★ #26610 `-sm tensor` 形态验证 = No-Go（本轮最重要结论）

- **现象**：影子引擎 + `--split-mode tensor --tensor-split 3,1` ⇒ **加载期（warmup decode）即崩**，服务从未起来。
- **根因（worker 侧，有 core 为证）**：`ggml-rpc-server` 处理 RPC `GRAPH_COMPUTE` 时于 **Vulkan 构图 `ggml_vk_build_graph` SIGSEGV**（`Signal: 11`；apport core 栈 `ggml_vk_build_graph ← ggml_backend_vk_graph_compute ← rpc_server::graph_compute ← rpc_serve_client`）；head 收 EOF 后 `ggml-rpc.cpp:651` 抛未捕获异常 ⇒ SIGABRT（次因 = #26724 族"worker 崩则 head 陪葬"）。
- **判定**：T3/T8 FAIL、余条不可执行 ⇒ **"合并但不能用"**；**等上游**（挂 #30075 · 同类 #30052 · 次因 #25938；候选修复 PR #25670 仍 open）。已向 #30052 提交本集群数据点（comment `6110101711`）。
- **回退**：全程**生产零影响**（影子目录 + 同别名 conf 快照；symlink 自始未切）。

## 3. 顺带：单站引擎轴退役（`~/llama.cpp`）

三站删 `~/llama.cpp`（0d18aaa / Vulkan，逐站本地构建、无 MANIFEST/门禁/回滚、三站实测**不可复现**）；唯一 2 个 `llama-single` 别名（`qwen3.8-27b-mtp` / `davidau-q38-27b-q4k`）conf 归位 `/opt/llama.cpp`，**等价性冒烟 + 对照臂 PASS**；tar 备份 `/data/backup/single-engine-retire-20261012/`（各 300 MB，**保留**）。

## 4. ★ 顺带修 3 个工具缺陷（执行中实测发现）

| # | 缺陷 | 影响 | 修法 |
|---|------|------|------|
| **A** | `ops/cluster.py` `_cmd_load_c` **不接/不传 `engine`** | **C 站 `--engine` 被静默丢弃**（对 GLM 的 `--engine glm5next-*` 是同族风险面） | 增 `engine` 形参 + 改走 `_build_infer_load_cmd` |
| **B** | `ops/station-bin/infer-load` 的 `ALL_ALIASES` 只扫 depth-2 目录 | "仓库级直放"别名（`davidau-q38-27b-q4k`）**无法解析**（同缺陷 `infer-list` 9/15 已修、`infer-load` 未同步） | 改为与 `infer-list` 同规则（按 gguf 文件分组） |
| **C** | `_set_conf_key` 追加**不保证末行换行** | conf 末行无换行时**拼行** ⇒ llama-server `invalid argument: --metricsLLAMA-RPC-SERVER-BIN=…` **启动失败**（实测咬到 C 站 qwen conf） | 追加前补换行 |

⇒ `infer-load` 修复后**推三站**（md5 `2dd2f6cfc74a60889fda25f50a24c5b7`）；另将 **`load-gate` 对齐仓库版**（ADR-0014，`f082f8c689…`，此前三站落后未部署）⇒ `gates` PASS（站上件 **27/27**）。

## 5. 验收 / 证据

| 项 | 值 |
|----|----|
| 冒烟 | `UPGRADE_PONG` = `content='UPGRADE_PONG'` · `finish=stop` |
| 落地核验 | `/proc/<pid>/exe` 三站 = `/opt/llama.cpp-master-23b0202a/{llama-server,ggml-rpc-server}` |
| worker 协议 | `Starting RPC server v8.0.0`（v6.0.0 → v8.0.0，**无向后兼容**） |
| 巡检 | `cluster.py versions` 三站 `md5sum -c` **79 OK** 一致 |
| 门禁 | 全量 **绿灯 45 / 黄灯 3 / 红灯 0**（3 黄均既有已登记项） |
| 回滚 | `sudo ln -sfn llama.cpp-9859 /opt/llama.cpp`（**三站**）；★ `master-91f6a6cf` **刻意保留**为"退回上一生产版"退路 |
| 详证 | [2026-10-12_引擎升级可行性梳理与升级过程落档.md](2026-10-12_引擎升级可行性梳理与升级过程落档.md) · [2026-10-12_单站引擎轴不一致调研与统一方案.md](2026-10-12_单站引擎轴不一致调研与统一方案.md) · [metrics-log Phase 8/8b](../spec/rpc-optimization/metrics-log.md) · [TRACKER §2.4 / §2.5](../spec/upstream-tracker/TRACKER.md) |
