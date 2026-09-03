#!/bin/bash
LOG=/home/scott-lau/.unsloth/run-gpt-kvq.log
echo "== 关键：spawn 命令行 cache-type/上下文/KV =="
grep -oE "cache-type-k [a-z0-9_]+|cache-type-v [a-z0-9_]+" "$LOG" | sort -u
grep -oE "est. KV cache: [0-9.]+ GB" "$LOG" | head -1
grep -oE "\-c [0-9]+ " "$LOG" | tail -1
echo "== 模型加载后内存（q8_0 KV） =="
free -g | head -2
echo "== KEY =="
grep -oE "sk-unsloth-[a-f0-9]+" "$LOG" | tail -1