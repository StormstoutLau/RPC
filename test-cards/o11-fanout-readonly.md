---
model: ''
readonly: true
timeout-s: 900
continue-timeout-s: 900
accept:
  - test -s out/summary.txt && grep -q 'O11_FANOUT_OK' out/summary.txt
---

任务描述: 只读跨站并发测试。读取工作区 .attach/_o11_src.txt 的五行内容（首行以 O11 fan-out 开头，末行 quantum rope 结尾），将其整理为 4 行结构化摘要：第1行固定为 `O11_FANOUT_OK`（原样封号），后3行逐行总结源文件第2~4行。<br>
要求：不要修改任何源文件，只在 out/summary.txt 写入结果（每行一个条目）。输出到文件后，在最终答复里只输出 `DONE <你的站名>` 一行。