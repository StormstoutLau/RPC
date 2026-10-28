#!/bin/bash
echo "== A 站 infer-load 存在? =="
ls -la /usr/local/bin/infer-load 2>/dev/null && md5sum /usr/local/bin/infer-load || echo "A 无 infer-load"
echo "== A 站 LLAMA_SERVER_PATH =="
grep -iE "LLAMA_SERVER_PATH" ~/.bashrc ~/.profile 2>/dev/null
echo "== A 站 unsloth 路径 =="
ls ~/.local/bin/unsloth 2>/dev/null && echo "unsloth OK"
echo "== A 站 llama.cpp-vulkan =="
ls ~/llama.cpp-vulkan-b10715/llama-server 2>/dev/null && echo "vulkan b10715 OK"
echo "== A 站 conf =="
ls /etc/llama-instances/ 2>/dev/null | grep -iE "gpt-oss|nemotron"