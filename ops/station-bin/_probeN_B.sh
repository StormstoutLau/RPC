#!/bin/bash
echo "== B站 找 nemotron GGUF =="
find /data /home/scott-lau /opt/models -maxdepth 6 -iname "*.gguf" 2>/dev/null | grep -i nemotron | head
echo "== B站 /data 相关目录 =="
ls -d /data/models/gguf/*/ 2>/dev/null | head
echo "== B站 当前运行模型进程（确认 nemotron 在跑哪） =="
ps -eo args 2>/dev/null | grep -iE "llama-server|vllm|nemotron" | grep -v grep | head
echo "== B站 nemotron 大小（若找到源文件） =="
find /data /home/scott-lau /opt/models -maxdepth 7 -iname "*nemotron*.gguf" -exec ls -lh {} \; 2>/dev/null | head