---
proj: dogfood
task: 仅供 split 使用的主卡（两片平衡负载）；不由单个 agent 完整执行
model: ultra
cli: opencode
sensitivity: public
readonly: true
timeout_s: 300
decompose:
  - 只读分片1：在 stdout **恰好输出 20 行**，第 n 行形如 `O67_S1|n|shard-one-line-n`（n 从 1 到 20，逐行递增，不要合并成一行）。不要写任何文件、不要读文件、不要解释。
  - 只读分片2：在 stdout **恰好输出 20 行**，第 n 行形如 `O67_S2|n|shard-two-line-n`（n 从 1 到 20，逐行递增，不要合并成一行）。不要写任何文件、不要读文件、不要解释。
---
## 主卡（只提供总上下文）

**本卡只用于 `split`**（`decompose` 两片，由拆片器 round-robin 到**两个不同站**并发派发）。
⚠ 本卡**不应**被单卡 `task` 直接执行 —— 它没有单一产物，`task` 模式下两片只会被当成上下文。

### 为什么把它做成"两片**平衡**、且**纯 stdout**"

- **平衡**：两片的指令长度、输出行数（各 20 行）、格式复杂度**逐项对齐** ⇒ 若两者耗时不同，那差异来自**站/网络**，不是任务本身。
- **纯 stdout**：拆片器**要求 `readonly: true`**（合并只支持只读卡），而站上硬约束是
  **`readonly` 与"必须落文件"互斥**（dogfood-cards README 纪律 10）⇒ 产物只能是 stdout，
  由拆片器的 per-shard 日志接住（`split-<cid>/shard<N>.log`）。

### 它要回答什么（台账 O-67）

代码自己在 egress 上打印的告警原文：「`cross-station each-1` **assumes per-station engines**；
egress **has single route, fanout may not parallelize**」——即"跨站各 1"这条纪律的前提
（每站各有本地引擎）在**出网档不成立**。⇒ 本卡用来实测：**出网档拆 2 片后，批墙钟是否真按 ~2× 缩短**。

> ⚠ **2026-09-25 首跑结果：并行成立**（`wall_ms=31396` ≈ 单片 + 开销，比串行下界 44s 低 12s+）
> ⇒ 代码里那句措辞**已按实测收窄**为"并行性取决于**账户/站粒度**"；上面引的是**当时**的原文（留作动机）。

判读口径（同一 run 内自证，不需要另跑串行基线）：

- 并行 ⇒ `SPLIT_DONE … wall_ms ≈ max(两片自身 run_s) + 启动/收集开销`
- 串行 ⇒ `wall_ms ≈ 两片 run_s 之和`
