---
proj: paper
task: 递归列出工作区 .attach/ 全部内容，并原样回显其中三个文件的标记行；不修改任何文件
model: nemotron
cli: opencode
sensitivity: public
readonly: true
timeout_s: 300
---
## 任务描述

工作区存在附件目录 `.attach/`（由 agent-cli --attach 传入），其中包含多个文件和一个子目录。你只需做两件事：

1. 用 `ls -R` 或 `find` 递归列出 `.attach/` 的完整目录结构（含子目录与所有文件），不要遗漏任何一项；
2. 对以下三个文件，用 `cat` 打开并原样回显其内容：
   - `.attach/fileA.md`
   - `.attach/fileB.txt`
   - `.attach/docs/inner.txt`

直接展示三者的原始内容即可，不要附加任何解释，不要创建/修改任何文件。