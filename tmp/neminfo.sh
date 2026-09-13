#!/bin/bash
D=/home/scott-lau/.lmstudio/models/lmstudio-community/NVIDIA-Nemotron-3-Super-120B-A12B-GGUF
echo "== 分片 =="
ls -la "$D"/*.gguf
echo "== 分片大小(GiB) =="
du -h "$D"/*.gguf
echo "== 总量 =="
du -sh "$D"
echo "== 内存 =="
free -g | head -2 | tail -1
echo "== load-gate =="
ls -la /usr/local/bin/load-gate 2>/dev/null && echo 存在 || echo 不存在