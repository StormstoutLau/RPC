# C 站测试 MiniMax-M2.7 / Qwen3.8-Flash-Next（UD-IQ4_XS 档）

## Context

按框架规范（MODEL-SOURCING §附录/QUANTS 走查 + load-gate 硬规则）在 **C 站（seaviv, 192.168.1.37）** 单机测试两个模型：
- **MiniMax-M2.7 UD-IQ4_XS**：229B sparse MoE（10B active, 256 experts, 200K ctx），unsloth Dynamic 4-bit，~108G（4 分片）
- **Qwen3.8-Flash-Next UD-IQ4_XS**：125B MoE（6B active, 512 experts, 262K ctx 原生），unsloth Dynamic 4-bit，~93.7G（1 文件）

两模型均为 MODE_SOURCING 附录 A/B 的**单站 124G 推荐档**（D.3 结论：Q3.8F 单站首选、M2.7 编码补位）。**均不在库**（Q3.8F 只有 Q4_K_XL 111G 超单站；M2.7 三站全无）→ 需下载。二者同为"单站可跑性 + 性能实测"验证，为单机 agent 主力候选评估。

C 站环境：引擎 /opt/llama.cpp v0.4.0-dev (91f6a6cf, 三站同构)、infer-* + load-gate 三件套已装、UMA=4G（可用内存 121G）、磁盘余 1.4T。**网络：huggingface.co 直连不通，hf-mirror.com 可达**。

## 关键约束（硬规则）

1. **load-gate**（C 站已装）：加载前 need+12G ≤ avail。**M2.7 108G + 12G = 120G > C 站 avail ~116G → 数学 ABORT 风险**；Q3.8F 93.7+12=105.7 ≤ 116 ✅。
2. **禁止同站叠加**：两模型应串行加载（同站 GTT/UMA 互斥），换测先 `infer-unload` + `wait-gtt-release`。
3. **官方 imatrix 单一档铁律**：仅下载 unsloth `UD-IQ4_XS`，不混档（memory: 混合量化可 OOM）。
4. 引擎已含全部所需算子（qwen4exp/mimarmax 架构 8 月已合入）；Vulkan0。
5. 模型归档走方案 A（9/9 三站同构）：实体 `~/.lmstudio/models/lmstudio-community/<Repo>/`，`/data/models/gguf` 反向软链。

## 实施步骤

### Phase 0 — 下载（**C 站直连 hf-mirror 优先**，B 中转备选）
- **C 站直连（首选）**：preflight 已证 C 站 `hf-mirror.com` HTTP 200 可达。两种直拉方式：
  - **wget/curl 直拉分片 URL**（零依赖，最稳）：
    - `https://hf-mirror.com/unsloth/MiniMax-M2.7-GGUF/resolve/main/UD-IQ4_XS/MiniMax-M2.7-UD-IQ4_XS-0000{1..4}-of-00004.gguf`（108G / 4 分片）
    - `https://hf-mirror.com/unsloth/Qwen3.8-Flash-Next-GGUF/resolve/main/UD-IQ4_XS/<file>.gguf`（93.7G；文件名以 HF tree 实况为准，可能 1 文件或分片）
    - 直接落 C 站实体目录 `~/.lmstudio/models/lmstudio-community/...`（方案 A 结构），`wget -c` 支持断点续传
  - **pip 装 huggingface_hub**（备选）：`pip install -U huggingface_hub` 后 `HF_ENDPOINT=https://hf-mirror.com hf download ...`（依赖 pip 网络可用）
- **B 中转（备选）**：C 直连失败时走 B（B 已有 huggingface_hub 1.29.0）→ rsync B→C（管理网/环网），`b5k_sync.sh --verify` 语义双端校验
- 校验：各分片 size 与 HF 元数据一致；分片模型测前 md5 抽查

### Phase 1 — C 站归档 + conf
- 实体落位 + `/data/models/gguf/lmstudio-community/` 软链（若走 infer-list 扫描需属主目录两层结构）
- `infer-load <alias>` 生成 `/etc/llama-instances/<alias>.env`（MODEL_PATH/PORT=8080/CTX/EXTRA_FLAGS=-fa on/N_CPU_MOE 对齐 6.4 profile）；M2.7 N_CPU_MOE?（10B active，可 0；Q3.8F 6B active，0）

### Phase 2 — 加载 + 冒烟（先 Q3.8F 后 M2.7，均 load-gate 前置）
- **Q3.8F**：`load-gate 94`（预期 PASS）→ `infer-load qwen3.8-flash-next` → `/health` ok → chat 冒烟（reasoning/content 完整）+ 计时 3 次（t/s）
- **M2.7**：`load-gate 108` → **预期 ABORT（avail 116 < 120）** →
  - 若 ABORT：评估两步缓解——① 先 `infer-unload` 清 C 站余留（当前无加载，avail 应已 116）② `--load-mode mmap`（社区: 93-108G 文件 mmap 页按需进 RAM，实际占用可能 < 文件体积，124G 预算实际更宽裕）③ ctx 收窄（如 8-16K）
  - 加载成功后 chat 冒烟 + 计时 3 次
- 每模型测完 `infer-unload` + `wait-gtt-release`

### Phase 3 — 落档
- metrics-log（或 results-ledger）追加：两模型 C 站单机结果（加载态/内存峰值/t/s、冒烟通过/失败、HC/resolve 观测）
- MODEL-SOURCING 附录 E（单站模型池）打 ✓ 实测回填；QUANTS 结论校准
- 若 M2.7 贴线失败：记录"UD-IQ4_XS 单站 C 站 121G 物理不可行 → 换 UD-Q3_K_M 90-101G"的决策行。

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| M2.7 108G 超 C 站 load-gate（avail 116<120） | mmap 模式 + ctx 收窄重试；仍失败 → 换 UD-Q3_K_M（90-101G）并记录 |
| hf-mirror 下载慢/断 | 分片逐个下 + `wget -c` 断点续传（C 站直连）；仍失败才 B 中转 |
| 加载 OOM（kernel panic 历史） | load-gate 前置强制；不加 `-ngl 99`（单机全量为大模型 OOM 根因，用 `-sm layer` 或 mmap 承载）|
| 两模型并行占用 | 串行，换测先 unload + wait-gtt |
| Q3.8F mmproj 需对照粒度 | 文本优先（用户场景 core），mmproj 另立小 test |

## 验证清单
- [ ] 两模型下载完成 + 同步 C 站 + 双端校验
- [ ] Q3.8F UD-IQ4_XS C 站 load-gate PASS → 加载成功 → 冒烟 + 计时落档
- [ ] M2.7 UD-IQ4_XS load-gate 判定（PASS 或 ABORT 按缓解路径处理）→ 实测结论落档
- [ ] 两模型测后均 unload + GTT 回收
- [ ] MODEL-SOURCING 附录 E / QUANTS / metrics-log 回填

## 关键文件
- 模型选型：`spec/model-eval/MODEL-SOURCING-2026-09.md`（附录 A/B/D/E）
- 归档方案：`spec/operator-optimization/research/模型路径统一方案A_20260909.md`
- 工具：C 站 `/usr/local/bin/{load-gate,load-mem-gate,wait-gtt-release,infer-load,infer-list,infer-unload}`
- 引擎基线：`spec/upstream-tracker/TRACKER.md §2.4`（v0.4.0-dev 91f6a6cf）
- 落档：`spec/rpc-optimization/metrics-log.md`、`spec/model-eval/results-ledger.md`