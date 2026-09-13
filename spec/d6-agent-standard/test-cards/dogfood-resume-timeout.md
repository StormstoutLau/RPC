---
proj: paper
task: O-24 P0-① resume 验证卡 - 任务极慢必被 timeout 杀，验证失败->--continue 续跑循环出线
model: gpt-oss
cli: opencode
sensitivity: local-only
readonly: false
timeout_s: 4
---
## 任务描述
Write out the numbers 1 to 1000000 one per line, enumerating every integer. Do not stop until done.