---
model: gpt-oss
readonly: false
timeout-s: 120
continue-timeout-s: 60
---
任务：排它身份验证。将固定标记写入工作区新增文件 out/o17_write.txt，内容首行为 O17_WRITE_OK|passed。本任务允许写源文件（readonly:false，锁应为排它模式）。