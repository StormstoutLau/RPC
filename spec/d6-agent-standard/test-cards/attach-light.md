---
proj: paper
task: 读取工作区 .attach/inbox.txt 并原样输出其内容（单行），不要修改任何文件
model: nemotron
cli: opencode
sensitivity: public
readonly: true
timeout_s: 300
---
## 任务描述

工作区存在一个附件 `.attach/inbox.txt`（由 agent-cli --attach 传入）。你只需读取它，然后输出该文件中的一行原始文本。不要创建/修改任何文件，不要附加任何额外说明，只回显该行内容。