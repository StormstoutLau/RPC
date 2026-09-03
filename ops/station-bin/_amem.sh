#!/bin/bash
echo "== 顶层内存 =="
free -g | head -2
echo "== llama-server 各进程 RSS =="
ps -eo pid,rss,cmd | grep '[l]lama-server' | awk '{printf "pid=%s rss=%.1fG\n",$1,$2/1048576}'
echo "== unsloth studio (gpt-oss) python 父进程 RSS =="
ps -eo pid,rss,cmd | grep '[u]nsloth' | grep 'studio run' | awk '{printf "pid=%s rss=%.1fG\n",$1,$2/1048576}'
echo "== 模型实际权重占用(文件大小) =="
ls -la /data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/gpt-oss-120b-MXFP4.gguf | awk '{print $5/1073741824 " GB"}'