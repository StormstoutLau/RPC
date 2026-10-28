#!/bin/bash
echo "== run-gpt-oss-20b.log 尾部 =="
tail -20 /home/scott-lau/.unsloth/run-gpt-oss-20b.log 2>/dev/null
echo "== 20b unsloth 是否 running =="
ps -eo pid,etime,cmd | grep "[u]nsloth.studio.run" | grep -i "gpt-oss-20b" | head
echo "== 8080 =="
ss -tln 2>/dev/null | grep ":8080" | awk '{print $4}'