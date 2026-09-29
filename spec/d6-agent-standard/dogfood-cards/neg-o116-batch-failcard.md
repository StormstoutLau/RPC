---
proj: dogfood
task: O-116 负控卡（**故意用未登记模型别名 ⇒ 子进程 `REJECT unknown-model`、非零退出、零触站**）
model: o116-no-such-alias
sensitivity: public
readonly: false
timeout_s: 120
---
## 任务描述

**本卡是负控卡，不应被真正派发**：`model` 是一个**不在 `ROUTE_TABLE` 里的别名** ⇒
`task` 在**模型解析处**即 `REJECT unknown-model (…) exit 2`：
**无 prompt 组装、无触站、无 runDir、无 `TASK_DONE`**（成本 = 0）。

**它存在的唯一理由**：给 `batch` 的汇总器（**O-116**）造出"**首卡必失败 / 末卡成功**"的形状 ——
缺陷版汇总器在**整站日志**里取 `TASK_DONE` / `RUNSTAMP` 的**末行** ⇒ 首卡的 rc 被**末卡的 runDir**
覆盖 ⇒ 首卡被判 `exit=0` + `BATCH_DONE: 失败或未完成=0`（**判决级假绿**）。

## 判读（人工，不采信汇总的自报）

看 `batch` 汇总里本卡那一行：修好后必须是 **`exit≠0`（预期 2，以实测为准）+ `runDir=` 为空**；
若它显示 `exit=0`、或显示**别张卡**的 `runDir` ⇒ 汇总器又退回了"整站取末行"。