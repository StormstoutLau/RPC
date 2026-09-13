---
model: gpt-oss
readonly: true
timeout-s: 120
continue-timeout-s: 60
---
任务：只读身份验证。取得固定标记字符串，写入 out/o17_readonly.txt，内容首行为 O17_READONLY_OK|passed。不要修改任何源文件（本任务为 readonly，锁应为共享模式）。