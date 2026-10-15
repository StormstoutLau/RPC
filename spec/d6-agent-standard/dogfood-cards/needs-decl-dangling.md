---
proj: dogfood
task: 对给定主题写一句极简结论（只做本片范围，不做全局总结）
model: needs-probe-invalid
cli: opencode
sensitivity: public
readonly: true
timeout_s: 300
accept:
  - test -s out/shard-written.txt
decompose:
  - subject=路由层 | 用一句话说明「路由层」在这个抽象系统里的职责
  - subject=缓存层 | needs=不存在的主体 | 用一句话说明「缓存层」与路由层的关系
---
> **`needs=` 探针（负向 · 悬空引用）** —— 片2 `needs=不存在的主体`（**未声明 ⇒ 无此片**）。
> **期望读数**：**在任何派发之前** `SPLIT_NEEDS_FAIL: …（未声明）… [exit 2]` · **零子进程**（站上零动作）。
> ⚠ **本卡刻意用一个无效 model**（`needs-probe-invalid`）—— 校验**早于** model 解析，
>   故它**必须**因 needs 而 exit 2；若它因"未知模型" exit 2，本用例就是**因错的原因通过**（假绿），须判红。
> 【本卡不对任何站产生动作】
