#!/bin/bash
F=/home/scott-lau/.lmstudio/models/autotrust/gpt-oss-120b-Fable-5-Distilled-GGUF/gpt-oss-120b-Fable-5-Distilled-Q5_0.gguf
echo "== A站文件 =="
ls -la "$F"
du -h "$F"
echo "== A站 md5 (后台) =="
nohup md5sum "$F" > /tmp/fable_a.md5 2>&1 &
echo "a_md5_pid=$!"
echo "== scp 残留进程 =="
ps aux | grep -E 'scp.*fable' | grep -v grep || echo "scp 已结束"
echo "== B站源 md5 =="
cat /tmp/fable_b.md5 2>/dev/null
echo "== A站内存 =="
free -g | head -2