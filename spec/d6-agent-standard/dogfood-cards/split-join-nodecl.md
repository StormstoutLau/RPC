---
proj: dogfood
task: 对给定主题写一句极简结论（只做本片范围，不做全局总结）
model: ultra
cli: opencode
sensitivity: public
readonly: true
timeout_s: 300
decompose:
  - 用一句话说明「路由层」在这个抽象系统里的职责
  - 用一句话说明「缓存层」与路由层的关系
---
> **split-join 探针（负向类）** —— `decompose:` 条目**不带** `subject=` ⇒ 期望 `SPLIT_JOIN` 报
> **`status=undeclared` + 未声明清单**（fail-closed：**不得**读成「无冲突」）。
> 【输出】每片在 `out/` 下写 `shardN.txt`（一行即可）。