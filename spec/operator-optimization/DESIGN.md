# 算子层优化方案设计 (gfx1151 Vulkan / 双机 RPC + 单机双路径)

> **日期**: 2026-08-28
> **依据**: 《AMD平台算子层优化与USB4分布式调研.md》v1.1 (已审计) + 本集群 Phase 0-3 实测 ([metrics-log](../rpc-optimization/metrics-log.md))
> **现状基线**: 双机 RPC, MiniMax-M2.7 Q4_K_S 121.10 GiB, pp512 = 141.12±0.08, tg128 = 20.05±0.04 t/s
> **范围**: 算子层与算子-放置协同; 模型层 (DSpark 投机解码) / 协议层 (RPC) / 链路层 (40G 换线) 见各自专档

---

## 0. 结论摘要

1. **社区算子 PR 全部未合入主线** (#27332 / #26578 Open, #27554 已关由 issue #27553 承接) — 现阶段无版本可升, **纯跟踪, 事件驱动**; v0.2.0 → master 升级当前零收益。
2. **tg 20 t/s 的结构性瓶颈不是算子, 是 RPC 串行跨链**: 调研 §4.1 同构集群实证, 单机 decode ≈ 2× 双机 RPC (激活参数相近时)。算子层修复 (密度门/mmq tile) 只改善本地计算部分, 对 RPC 串行化无解。
3. **因此方案按双路径设计**: 容量路径 (双机 RPC Q4_K_S, 现状, 参数精调) + **速度路径 (B 站单机 UD-Q3_K_XL, 待建基线)**。算子 PR 落地后两条路径同时受益, 但单机路径收益全额传导。
4. **新变量**: USB4 链路 idle 振荡发现 ([40G 评估](../rpc-optimization/USB4-40G链路能力评估.md) §4.2) — 双机路径有可靠性风险, 单机路径免疫 → 强化单机路径优先级。
5. 立即可做的零成本项: llama-server 加 `-dio`、`-np` 并发避坑规范、KV q8_0 配置卫生、单机基线补测 (调研 §4.4 指出的盲区)。

---

## 1. 现状与约束清点

| 项 | 值 | 来源 |
|----|-----|------|
| 双机 RPC tg128 | 20.05 ± 0.04 t/s | Phase 1 bench (2026-08-28) |
| 双机 RPC pp512 | 141.12 ± 0.08 t/s | 同上 |
| 模型 | MiniMax-M2.7 Q4_K_S, 121.10 GiB, 230B.A10B, 62 层, 8 KV heads | /health + bench 日志 |
| 当前服务参数 | `-ngl 999 -c 32768 -t 16 -b 512 --n-cpu-moe 8 -fa on` | llama-server.service |
| RPC 缓存 | A 站 47G/136 tensors 已建 (加载 310→267s) | Phase 2 |
| Vulkan 后端 | RADV GFX1151, KHR_coopmat 矩阵核, fp16=1 | bench 设备行 |
| llama.cpp 版本 | v0.2.0 (8 月初标签), 落后 8 月中下旬 gfx1151 优化 wave | DEV-LOG-009 |
| B 站单机基线 | **缺失** (调研 §4.4 盲区) | — |

**硬约束**:
- Q4_K_S 121.10 GiB vs Linux GTT ~120 GiB → **单机装不下 Q4_K_S** (勉强塞入也会被 `llama_params_fit` 静默裁 ctx, 调研 §4.5A)
- RPC 路径存在 RADV 792MB 单张量分配墙 (M2.7 特有, strix-halo-guide #12); 单机 Vulkan 路径无此雷 (调研 §4.5A)
- 128k ctx 单机需 KV q8_0 + Q3 档以下 (0.129 MiB/token·q8 × 128k = 16.4 GiB)

---

## 2. 战略: 双路径定位

```
                    ┌─ 容量路径 (现状): 双机 RPC Q4_K_S 121G ──→ tg 20 t/s, 量化损失最小
                    │   定位: 质量优先 / 32k ctx / Q8 无损与 300B+ 模型的唯一通路
   MiniMax-M2.7 ───┤
                    │
                    └─ 速度路径 (待建): B 站单机 UD-Q3_K_XL 101.8G ──→ 预期 tg 29~33 t/s
                        定位: 交互优先 / 动态量化贴 Q4 质量 (LCB 76% vs 68%,
                        调研 §4.5C) / 免疫链路振荡与 RPC 串行化
```

**依据链**:
- 单机 M2.5 Q3_K_M 228.7B = 32.8 t/s vs 双机 RPC 同族 = 15.35~18.2 t/s (visorcraft + 本集群, 调研 §4.1)
- UD 动态量化同体积质量 > 标准 K-quant (snagnever LCB 实测, 调研 §4.5C)
- 链路 idle 振荡 → 双机路径 MTTR ~6min/次 (Phase 3 演练), 单机零此风险

**双机 RPC 保留场景**: Q8 无损 (162GB), 397B 级模型, 128k 长上下文 — 容量刚性时。

---

## 3. 算子 PR × 路径收益传导矩阵

| PR/Issue | 算子热点 | 实测收益 | 双机 RPC 传导 | 单机传导 | 触发动作 |
|----------|---------|---------|--------------|---------|---------|
| **#27332** 密度门 (Open, 8-18) | MUL_MAT_VEC_ID MMV dispatch 断崖 | B9 +36%, B16 +27%, B64 +21% | 部分 — 只修 B 站本地 MMV; 跨链串行不变; 且当前 -np=1 不触发断崖 | **全额** — MoE 并发场景 (-np ≥9) 直接收益 | 合并 → 下个 release → UPGRADE_SOP |
| **#27553** (issue, 承接 #27554) | K-quant int-mmq 大 tile (dense GEMM) | pp512 1.76× (dense) | 中等 — prefill 批量摊薄链路开销, pp 提升部分传导 | **全额** | 新 PR 出现 → 评估 → 升级 |
| **#26578** DSV4_HC 融合 (Open) | Sinkhorn comb chain 融合 | DeepSeek-V4-Flash decode 1.50× | N/A — MiniMax 无此算子; **DS4-Flash 部署的前置增强** | 同左 | 合并 → DS4-Flash 双机方案联动 |
| #15524 (已在 v0.2.0) | MUL_MAT_ID subgroup | 小 MoE +100~660% | 已吃到 | 已吃到 | 无 |
| Luce fork | 自定义 HIP kernel | decode 2.23× | 脱离主线版本管理, 不引入 — 仅上限参考 | 同左 | 不动作 |

**判读**: 算子 PR 是"免费的未来收益", 但**没有一个是现在能拿到的** (全部未合入)。当前可执行的优化全部在参数层与路径层。

---

## 4. Phase A — 零成本项 (无版本变更, 1 个会话内完成)

### A1. llama-server.service 加 `-dio` (防 hang 保险)
- 依据: 调研 §4.2, >100GiB 模型 llama-server RPC 加载 hang, 三重独立确认; 本集群 121.10 GiB 在临界区之上 (当前能加载疑似因 -c 缓存改变了路径, 不赌)
- 改动: `ExecStart` 追加 `-dio`; 顺带评估 `-ctk q8_0 -ctv q8_0` (KV 8.4→4.2 GiB, 为 ctx 扩展留余量)
- 代价: 一次服务重启 (~4-5 min, 缓存热加载)
- 文件: B 站 `/etc/systemd/system/llama-server.service` (主控源 [scripts/llama-server.service](../../scripts/llama-server.service) 同步改)

### A2. 单机速度档基线 (C3 cell, 调研 §4.5D 配置)
- 前提: 检查 `MiniMax-M2.7-UD-Q3_K_XL` (101.8G) 可用性 (llmfan46 repo / Unsloth dynamic); 缺失则退 IQ3_XS/M 变体并在日志标注
- 下载 101.8G → B 站 (注意主控站中转通道, DEV-LOG-009 发现 1)
- bench (见 §7 矩阵 C3)
- **判读**: tg ≥ 28 t/s → 速度路径成立, 进 §8 决策门; tg < 24 → 查 FA/ubatch/KV 配置后复测一次

### A3. `-np` 并发操作规范 (避坑, 纯文档)
- 当前默认 -np=1, 不触发断崖; **规范: 未来开并发时只用 ≤8 或 ≥24, 禁 9..16** (调研 §2.2, #25356)
- 落点: llama-server.service 注释行 + 本文档 §7

### A4. bench 协议固化
- bench 前必须 `sudo systemctl stop llama-server` (GTT 互斥), 完成后 `start`
- A 站 rpc-server 保持运行 (双机 cell 用; 单机 cell 不影响)

---

## 5. Phase B — 参数 A/B 实验矩阵 (双机路径精调)

**固定量**: 模型 Q4_K_S, `--rpc 10.10.10.1:50052 -ngl 999 -t 16 -fa on -p 512 -n 128 -r 2` (与 Phase 0/1 严格可比)

| Cell | 变量 | 假设 | 风险 |
|------|------|------|------|
| C0 | (复用 Phase 1 数据) — n-cpu-moe 8 基准 | — | — |
| C1 | `--n-cpu-moe 0` | 8 层专家回 GPU 提速 | GTT 挤压 → fit 裁 ctx / 分配失败; 观察 "context size reduced" 行 |
| C2 | `--n-cpu-moe 16` | 更多专家卸 CPU 减 GTT 压力, 换 ctx 余量 | CPU 专家算力慢, tg 可能反降 |
| C5 | `-b 1024 -p 1024` (及 2048 档) | prefill 大批摊薄 MUL_MAT_ID 与链路 per-op 开销 | 计算缓冲增长; 与 pp512 不同度量, 单独判读 |

**判读标准**: t/s 变化 > 3×stddev 才算信号 (Phase 1 实测 stddev 0.04~3.76, 按各 cell 实际值); C1/C2 结论写入 metrics-log, 最优值回写 llama-server.service。

---

## 6. Phase C — 事件驱动升级跟踪 (零工作量)

| watch | 触发 | 动作 |
|-------|------|------|
| PR #27332 (密度门) | merge | 等包含它的 release → UPGRADE_SOP (RUNPATH patch 流程复用) → 重跑 §7 全矩阵 |
| PR #26578 (DSV4 融合) | merge | 同上 + 联动 DS4-Flash 双机部署方案 (带 `-dio`) |
| issue #27553 (mmq 大 tile) | 新 PR 开出 | 评估 → 升级 → pp 复测 |
| **PR #27752 / #27754 (glm5next)** | merge (任一) | 升级后 GLM-5.3-Flash 才可 infer-load — **滚升 master 不解锁 GLM** (2026-08-31 审计: master llama-arch.cpp 无 glm5next, 已证) |
| strix-halo-guide #12 | RPC 基准征集更新 | 本集群 -ot 数据可投稿 (见 Phase D) |

**预期收益 (三 PR 齐落地后)**: 单机 decode +20~50% (MoE 并发), prefill +50~76% (dense); 双机 RPC 按 §3 矩阵打折。

> **2026-08-31 审计修正**: ① 本表不含"滚升 master 解锁 GLM"项 — 该假设已证伪 (master 源码无 glm5next, 须等架构 PR #27752/#27754); ② vLLM 算子优化 (AITER on_gfx9 解锁 / TunableOp / HIPGraph 去 enforce-eager) **不列入 Phase C 硬计划** — 均降级为"待验证社区声称", 须在本地 A4 构建同栈复测后才可能转正 (见 Phase E)。

---

## 7. 度量矩阵 (bench 命令)

```bash
# B 站执行; 前置: sudo systemctl stop llama-server
# C1/C2: 双机 RPC n-cpu-moe sweep
/opt/llama.cpp/llama-bench -m $Q4KS --rpc 10.10.10.1:50052 \
  -ngl 999 -t 16 -b 512 -fa on --n-cpu-moe {0|16} -p 512 -n 128 -r 2

# C3: 单机速度档 (UD-Q3_K_XL, 调研 §4.5D 同款配置)
/opt/llama.cpp/llama-bench -m $UDQ3XL \
  -ngl 999 -t 16 -b 512 -fa on --n-cpu-moe 0 \
  -c 65536 -ctk q8_0 -ctv q8_0 -p 512 -n 128 -r 2

# C4 (可选): 单机 Q4_K_S 容量边界记录
/opt/llama.cpp/llama-bench -m $Q4KS \
  -ngl 999 -t 16 -b 512 -fa on --n-cpu-moe 16 -c 16384 -p 512 -n 128 -r 2

# C5 (可选): prefill batch 敏感度
/opt/llama.cpp/llama-bench -m $Q4KS --rpc 10.10.10.1:50052 \
  -ngl 999 -t 16 -fa on --n-cpu-moe 8 -b 1024 -p 1024 -n 128 -r 2
```

**记录**: 每结果回填 `metrics-log.md` (执行时创建于本目录), 含 t/s±stddev、加载时间、GTT 观察行 ("context size reduced" 出现即记录)。

---

## 8. 决策门: 默认路径切换

| 条件 (C3 基线落地后) | 动作 |
|----------------------|------|
| C3 tg ≥ 28 t/s 且 UD-Q3 质量抽测可接受 (对话/代码各 3 样例) | **速度路径设为默认**: llama-server.service 换单机 Q3 配置; 双机 RPC 降为容量备用 (Q8/397B/128k) |
| C3 tg 24~28 | 双路径并存, 按任务选路径; 服务保持双机 (重启成本考量) |
| C3 tg < 24 | 查因 (FA 状态/ubatch/KV quant), 复测一次; 仍不达标 → 维持双机, 单机路线挂起至 PR 落地 |
| 40G 换线后双机 pp/tg 显著改善 | 重估本决策 (链路带宽翻倍改变 RPC 损失率分母) |

**质量抽测协议** (决策门前置): 同 prompt 三温度 (0/0.6/1.0) 对比 Q4_K_S 双机 vs UD-Q3 单机输出; 代码任务一道 (语法正确性) + 推理任务一道 (答案正确性)。

---

## 9. Phase D — `-ot` 张量放置实验 (社区空白, 可选)

- **变体**: 默认 layer split (现状) vs `exps` 定向放置 (`-ot "exps=RPC0"` + dense/attention 留 B 本地, 或反向)
- **机制**: MoE offload 惯例 "attention/dense→快端, 路由专家→大容量端" (Doctor-Shotgun 指南); 双 GPU RPC 变体无公开数据 — **本集群可产出社区级空白数据** (strix-halo-guide #12 征集中)
- **定位**: Phase A/B 落定后做; 单机路径若成为默认, 本项降级为纯社区贡献
- 预期: 理论上减少每 token 跨链数据量 (激活 << 权重), 但 decode 串行化本质不变 — 收益存疑, 数据价值 > 性能价值

## 10. Phase E — 门槛项 (不默认执行)

| 项 | 门槛 | 依据 |
|----|------|------|
| 40G 认证线换线 | 用户物理操作 | [40G 评估](../rpc-optimization/USB4-40G链路能力评估.md) — 或有 idle 振荡根治效果 (**2026-08-31 已执行**: 开博尔 0.5m 40G, 振荡消除, 性能噪声级) |
| ROCm 双栈 (kyuz0 toolbox) | 出现重 prefill 批量场景 (文档摘要/代码库索引) | 调研 §2.5: HIP pp +42~48% 理论空间, 维护成本高 |
| thunderbolt-ibverbs | 双机 decode 需求刚性化 | 95 Gb/s 研究级, 与版本 SOP 冲突 |
| Luce fork | 仅作上限参考 | decode 2.23×, 脱离主线管理 |
| **vLLM AITER / TunableOp / HIPGraph** | **本地 A4 构建同栈复测通过** | **待验证社区声称 (2026-08-31 审计)** — 仅 rag-suite issue 转述, BUILD-FIXES.md 原文字节核验零关键词; 与 A4b enforce-eager 负迁移我方实测冲突 → 现不采信, 不复现不定谳; 复现路径 = 解锁 AITER 3 patch + PYTORCH_TUNABLEOP_ENABLED=1 → before/after 复测 |

---

## 11. 风险登记

| 风险 | 等级 | 缓解 |
|------|------|------|
| UD-Q3 质量衰减 (vs Q4) | 中 | UD 动态量化已缓解 (LCB 76%>68%); §8 质量抽测协议把关 |
| C1 GTT 溢出 | 低 | bench 观察行即知, 失败无损 (回退 n-cpu-moe 8) |
| 单机 128k ctx 需求 | 中 | KV q8 + Q3 仍不够 → 该场景回双机 RPC (容量路径职责) |
| 长上下文衰减 (50k+ -10~-36%) | 低 | 交互场景 32k 内基本无损 (调研 §4.5B) |
| 链路 idle 振荡 (双机路径) | 中 | Phase 3 自愈链兜底 (已演练); 40G 换线可能根治; 单机路径免疫 |
| A/B 期间服务中断 | 低 | 停服窗口集中在一个会话; 完成后恢复 |
| 101.8G 模型下载受限 | 低 | 主控站中转通道 (DEV-LOG-009 发现 1); 失败退 IQ3 变体 |

## 12. 执行顺序 (建议单会话)

A1 (服务参数) → A4 (停服) → C1 → C2 → C5 → A2/C3 (单机基线, 含质量抽测) → 恢复服务 (按 §8 决策门选配置) → metrics-log + DEV-LOG-011 落档。

---

**关联文档**: [算子层调研](../../AMD平台算子层优化与USB4分布式调研.md) · [RPC 协议调研](../../RPC协议瓶颈调研.md) · [40G 链路评估](../rpc-optimization/USB4-40G链路能力评估.md) · [metrics-log (RPC)](../rpc-optimization/metrics-log.md) · [DEV-LOG-010](../../DEV-LOG-010-rpc-optimization.md)
