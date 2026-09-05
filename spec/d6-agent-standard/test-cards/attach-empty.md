---
proj: paper
task: 用 find 列出工作区 .attach/ 的全部目录（-type d），原样输出目录路径清单；不修改任何文件
model: nemotron
cli: opencode
sensitivity: public
readonly: true
timeout_s: 300
---
## 任务描述

工作区存在附件目录 `.attach/`，其中包含一个**空子目录** `emptydir`（无任何文件）。你只需：

1. 执行 `find .attach -type d` 递归列出 `.attach/` 下的全部目录；
2. 在原输出中确认并回显 `.attach/emptydir` 这条路径（空目录也要被列出来）。

直接输出 `find` 的原始结果即可，不要附加解释，不要创建/修改任何文件。