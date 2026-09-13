# #26578 DSV4_HC 融合算子 A/B 实测（含三站引擎升级）

## Context

TRACKER 复核（2026-09-10）确认：**#26578（Vulkan DSV4_HC_COMB/PRE/POST 融合算子）已 9/7 merged**，decode 收益 1.50× / prefill 1.12× —— 是本集群 V4-Flash 提速的最大单点。现役三站引擎 `/opt/llama.cpp` = master-d2e206c4（8/31 构建），含 indexer/transpose/#26500，但**缺 sparse-fa 与 DSV4_HC(9/7)**。8 月 8 日三站 V4-Flash 实测日志警告 `resolve_fused_ops: layer 28 ... HC pre/comb/post assigned to RPC`（HC 未融合慢路径）即为未升级特征。

目标：**在 A/B 两站实测 #26578 收益**（新旧引擎对照），全程按 UPGRADE_SOP 规范执行推理框架变更。用户已确认：**三站同构升级**（B 单点构建 → A/C 分发，保持 MANIFEST 一致）+ **新旧引擎对照**（升级前 A/B 旧引擎打基线）。

实测模型：`DeepSeek-V4-Flash-0731-MXFP4.gguf`（单文件 156G，A/B 两站 `/data/models/gguf/lmstudio-community/DeepSeek-V4-Flash-0731-GGUF/` 均已就位）。
成功形态（9/8/9/9 实证）：**`-sm layer` 层分布、不用 `-ngl 99`**（`-ngl 999`/`-ngl 99` 单机全量持有 = 9/8 崩溃根因，禁用以防止再次 OOM）、worker 带 `--cache`。
实测形态：B head（llama-server `--rpc 10.10.10.1:50052`）+ A worker（`ggml-rpc-server`），走 A-B USB4 直连（RTT ~0.14ms）。

## 关键约束（硬规则，违反即 ABORT）

1. **加载前 load-gate**：`load-gate <GB> [host...]` — used+need+12G≤total && avail≥need+12G && 已有 llama RSS+need+12G≤total。**A/C 必须先卸载现有模型再测**（A=gpt-oss 68G used / C=nemotron 91G used 占位）。
2. **禁止叠加加载**：A/C 现役实例必须先 `infer-unload` 杀净，确认 GTT 回落（`wait-gtt-release`) 再测。
3. **-ngl 99 禁止**：V4-Flash 只用 `-sm layer` 层分布（每机 <=80G）。
4. **worker `--cache`**：防每次全量推权重（9/9 教训）。
5. **引擎变更走 UPGRADE_SOP 六步**，三站同时切换，改后统一冒烟。

## 实施步骤

### Phase 0 — 预检（只读快照）
- 记录 B 站 git HEAD（`cd ~/llama.cpp && git log --oneline -1`）+ 当前 `readlink /opt/llama.cpp`
- 核对 A/B/C 现役进程与 GTT（`free -g` + `mem_info_gtt_used`）
- 确认 A、B 站 V4-Flash 模型 md5 一致（防止 before/after 变量）
- `cluster.py status` 三站基线

### Phase 1 — 卸载 A/C 模型（准备 A/B 实测内存）
- A 站：`infer-unload`（A 站 8080 gpt-oss）→ `wait-gtt-release`
- C 站：`infer-unload`（C 站 8080 nemotron 手动进程，pkill 兜底）→ `wait-gtt-release`
- 验证：A/C `free -g` avail ≥ 90G（V4-Flash head~76G + worker~76G + 12G 垫）
- ⚠️ 不卸载 B（B head 需要本地起 llama-server；B 当前无加载实例）

### Phase 2 — BEFORE 基线（旧引擎 master-d2e206c4，A/B 两机）
- A 站起 worker：`nohup /opt/llama.cpp/ggml-rpc-server --device Vulkan0 -c 50052 > /tmp/rpcA.log 2>&1 &`（`-c`=cache 布尔开关；监听 10.10.10.1:50052）
- B 站起 head：
  ```bash
  /opt/llama.cpp/llama-server \
    -m /data/models/gguf/lmstudio-community/DeepSeek-V4-Flash-0731-GGUF/DeepSeek-V4-Flash-0731-MXFP4.gguf \
    --rpc 10.10.10.1:50052 -c 8192 -sm layer --port 18099 --host 127.0.0.1 -t 16
  ```
- 等待 `model loaded`（~4-5min，含 A worker rpccache 命中）
- 确认日志无/有 HC 警告（预期：旧引擎仍报 `HC pre/comb/post assigned to RPC`）
- 计时测量（与 9/8/9/9 同口径）：`curl /v1/chat/completions` 中长生成（如 `12*13=? 逐步推理并输出全部步骤`，max_tokens 512），读返回值 `timings.predicted_per_second`；跑 3 次取中值；同时跑 llama-bench 模式不做（llama-bench 冻结口径 -ngl 999 不适用）
- 记录 BEFORE 数值 + 日志警告快照 → 落 metrics-log

### Phase 3 — 三站引擎升级（UPGRADE_SOP 六步，B 构建源）
沿用 SOP §2.0 三站化（B 单点构建 → A→C 分发 → 原子切换 → 冒烟）：
1. **停服务**：A/B/C kill 现役 llama-server（A/C 已卸载；B 在 BEFORE 后卸 head）
2. **B 构建**：
   ```bash
   cd ~/llama.cpp && git fetch origin && git checkout master && git pull
   git log --oneline -1   # 确认 commit ≥ #26578 merged (9/7)
   cmake -B ~/build/llama-master-<newcommit> -DGGML_VULKAN=1 -DGGML_RPC=ON -DCMAKE_BUILD_TYPE=Release
   cmake --build ~/build/llama-master-<newcommit> --config Release -j $(nproc)
   ```
3. **安装 + MANIFEST**：`/opt/llama.cpp-master-<newcommit>`，复用 gen_manifest（`/tmp/gen_manifest.sh` 若不存在则从 9859 目录抄）+ `md5sum -c` + plain tar
4. **分发**：scp tar → A、C；远端解包 + `md5sum -c` MANIFEST（失败即中止）
5. **原子切换**（A→B→C 依序 `ln -sfn llama.cpp-master-<newcommit> /opt/llama.cpp` + `llama-cli --version`）
6. **冒烟**：B 起 gpt-oss 或 qwen 单机实例 → PONG + `ops/check_llama_version.py --deep` 三站指纹一致
7. **验证 HC 融合就位**：`strings /opt/llama.cpp/libggml-vulkan.so | grep -i dsv4_hc`（预期含 HC_COMB/PRE/POST 符号）

### Phase 4 — AFTER 实测（新引擎 ≥9/7，A/B 同形态同参数）
- A worker + B head 同 Phase 2 命令（引擎路径不变，仍 `/opt/llama.cpp/...`）
- 同 3 次计时取中值；**关键信号：日志 `resolve_fused_ops` 不再报 HC→RPC（融合在 Vulkan 本地生效）**
- 同机对比：BEFORE vs AFTER（pp/tg/decode t/s）→ 差值即 #26578 收益（预期 decode +~50%）

### Phase 5 — 收尾与落档
- 清理：测后 `infer-unload` head/worker；`wait-gtt-release`
- metrics-log（spec/rpc-optimization/metrics-log.md）追加 Phase 6：BEFORE/AFTER 对照行 + 口径 + 引擎 commit
- TRACKER.md §1.2/#5 变更日志 + 手册 §10 更新（升级窗口判定³：小窗口已执行）+ MODEL-SOURCING §6a HCC 已落地
- 巡检 `check_llama_version.py --deep` 三站全绿；`cluster.py status`
- 决策记录：若 after-tg ≥ 9.2×1.2 判 #26578 生效闭环；若持平则查 resolve_fused_ops 日志定位

## 风险与回滚

| 风险 | 缓解 |
|---|---|
| 构建失败/新 commit 有问题 | 保留 `/opt/llama.cpp-master-d2e206c4` 旧目录；`ln -sfn` 秒级回滚 + 重跑冒烟 |
| V4-Flash 加载再次 OOM | 严格执行 `-sm layer` 无 `-ngl 99`；加载用 `load-gate 80` 预检；A/B 内存 ≤ 80G 阈值 |
| B 站 git 网络拉取失败 | 先验证 `git fetch` 可达（9/8 曾 codeload 正常）；失败则改用应急路径（A 站 codeload tarball） |
| 升级窗口中断现有服务 | 先卸载 A/C、B 无实例 → 无生产流量依赖；litellm 短暂空窗可接受 |
| manifest 工具缺失 | `gen_manifest` 从 `/opt/llama.cpp-9859/MANIFEST` 周边查找/复用对齐 |

## 验证清单（完成标准）
- [ ] A/C 卸载后 `free -g` avail ≥90G（before 前置）
- [ ] BEFORE 基线记录（旧引擎 A/B，含 HC→RPC 日志快照）
- [ ] 三站引擎原子升级完成，`check_llama_version.py --deep` 全绿，`strings` 证实 libggml-vulkan 含 DSV4_HC 符号
- [ ] AFTER 实测定值 + 日志 `resolve_fused_ops` 无 HC→RPC
- [ ] BEFORE vs AFTER 对照落 metrics-log + TRACKER 变更日志 + 手册 §10 更新
- [ ] 回滚预案演练可用（旧目录保留）

## 关键文件/工具
- 升级规范：`d:\RPC\spec\vulkan-version-control\UPGRADE_SOP.md`（六步流程）+ `TRACKER.md §2.5`（职责边界：分布式一律 /opt，unsloth 单站保持）
- 实测形态参考：`d:\RPC\docs\V4-Flash-0731加载崩溃根因分析_20260908.md` §7b（成功命令）+ TRACKER §5 变更日志 9/9 两机行
- 工具：`/usr/local/bin/infer-load/infer-unload/load-gate/wait-gtt-release`；`ops/check_llama_version.py`；`cluster.py`
- 模型：A/B 站 `DeepSeek-V4-Flash-0731-MXFP4.gguf`（156G）
- 落档：`spec/rpc-optimization/metrics-log.md`；`spec/upstream-tracker/TRACKER.md`；`docs/三机推理集群使用手册.md §10`