---
proj: dogfood
task: 对给定主题写一句极简结论（只做本片范围，不做全局总结）
model: ultra
cli: opencode
sensitivity: public
readonly: true
timeout_s: 300
accept:
  - test -s out/shard-written.txt
decompose:
  - subject=路由层 | 用一句话说明「路由层」在这个抽象系统里的职责，写入 out/shard-written.txt
  - subject=缓存层 | needs=路由层 | 用一句话说明「缓存层」与路由层的关系，写入 out/shard-written.txt
---
> **`needs=` 探针（正向 · 方案 `a` 的"真跑层"）** —— 片2 `needs=路由层`（**引用可达**）。
> **期望读数**：`SPLIT_NEEDS: n=2 with_needs=1 status=ok` · `SPLIT_DONE` ·
> `join.json` 含 `needs_graph`（**标「派生非真值」**）。
> ⚠ **`needs` 不是执行顺序** —— 分片**并行**且互不可见（契约 §6.2-2「片间不共享锚点」）；
>   它只是**声明的血缘/读序**，对执行**零影响**（不排波次）。
> ⚠ `accept:` 是**必需**的（`TaskContract.accept` 非空 ⇒ 否则 D7 P0 硬拒 exit 3，见 2026-10-13「转硬拒」）。
