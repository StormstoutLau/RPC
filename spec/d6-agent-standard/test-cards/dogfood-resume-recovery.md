---
proj: paper
task: O-24 P0-① 真实恢复场景v3 - 首跑在 900s 被 timeout 杀,续跑 --continue 用足独立预算(continue-timeout-s=900)完成产出
model: gpt-oss
cli: opencode
sensitivity: local-only
readonly: false
timeout_s: 900
continue-timeout-s: 900
accept:
  - test -f resume_recovery.txt && [ "$(grep -cE '^[0-9]+$' resume_recovery.txt)" -eq 8000 ]
---
## 任务描述
Create a file named `resume_recovery.txt` in the current directory containing the integers from 1 to 8000, one integer per line, strictly ascending, final line equal to 8000.

Rules:
- You MUST write the integers yourself from your own generation — never use `seq`, `awk`, a single-shot `python -c` range print, loops, or any bulk number generator.
- Write in batches of at most 400 integers per tool call (append to the existing file, do not lose earlier lines).
- After every batch, run `wc -l < resume_recovery.txt` and state the current line count.
- Do not stop until the file holds all 8000 integers and the count is 8000.

When finished, reply with the single token: RECOVERY-DONE.