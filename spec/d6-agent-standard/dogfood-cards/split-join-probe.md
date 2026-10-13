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
  - subject=路由层 | 用一句话说明「路由层」失效时的第一表征
  - subject=缓存层 | 用一句话说明「缓存层」与路由层的关系
---
> **split-join 探针（首例）** —— `CONCLUSION #6` 兑现的**首个真实 split 实例**（`readonly: true` ⇒ split 合法）。
> **声明式主体（载体①）**：`decompose:` 条目带 `subject=<X> | <task>` ⇒ 期望 `SPLIT_JOIN` 报出
> **同主体组**（shard1+shard2 同属「路由层」）+ `status=ok`（三片均有声明）。
> 【输出】每片在 `out/` 下写 `shardN.txt`（一行即可）。