#!/bin/bash
echo "== 当前 gpt-oss spawn 的上下文 =="
ps -eo args | grep "[l]lama-server" | grep gpt-oss | grep -oE "\-c [0-9]+" | head -1
echo "== unsloth load 日志里的 context 声明 =="
grep -oE "\-c [0-9]+ " /home/scott-lau/.unsloth/run-gpt-8080-minthink.log | tail -1
grep -iE "context|KV cache" /home/scott-lau/.unsloth/run-gpt-8080-minthink.log | tail -3
echo "== 内存余量 =="
free -g | head -2
echo "== gpt-oss 原生 max (GGUF 头) =="
/home/scott-lau/llama.cpp-vulkan-b10715/llama-server --help 2>&1 | head -1
~/.unsloth/studio/unsloth_studio/bin/python -c "print('model native 128k')"