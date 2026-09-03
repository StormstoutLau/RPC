#!/bin/bash
echo "== 现有 llama-server 进程 =="
pgrep -af llama-server | head
echo "== 内存 (free) =="
free -g | head -3
echo "== gpt-oss 模型文件 =="
ls -lh /data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/ 2>/dev/null
echo "== 显存/GPU 内存 (strix halo unified) =="
cat /sys/class/drm/card*/device/mem_info_vram_total 2>/dev/null | awk '{print $1/1073741824" GB VRAM"}' | head -1
echo "== 现服务占用的内存/负载 =="
ps -o pid,pmem,rss,etime,cmd -p $(pgrep llama-server | tr '\n' ',' | sed 's/,$//') 2>/dev/null | head
echo "== unsloth studio run 模型参数 =="
U=~/.unsloth/studio/unsloth_studio/bin
$U/unsloth studio run --help 2>&1 | grep -iE "model|gguf|load|path|--model|-m " | head -20
echo "== 是否有现成模型在 unsloth 视图 =="
ls /home/scott-lau/.unsloth/study 2>/dev/null; find /home/scott-lau/.unsloth -maxdepth 3 -iname "*.gguf" 2>/dev/null | head