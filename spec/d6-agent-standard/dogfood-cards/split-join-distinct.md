---
proj: dogfood
task: 对给定主题写一句极简结论（只做本片范围，不做全局总结）
model: ultra
cli: opencode
sensitivity: public
readonly: true
timeout_s: 300
decompose:
  - subject=路由层 | 用一句话说明「路由层」在这个抽象系统里的职责
  - subject=缓存层 | 用一句话说明「缓存层」与路由层的关系
---
> **split-join 探针（类②：主体各异）** —— 用于 `CONCLUSION #6` retire 的**类覆盖补齐**（`O-149`(a) 甲档）：
> 期望 `SPLIT_JOIN` 报 `n=2 · declared=2 · undeclared=0 · status=ok · **无同主体组**`（异主体 ⇒ **不发明"冲突"**）。
> 【输出】每片在 `out/` 下写 `shardN.txt`（一行即可）。