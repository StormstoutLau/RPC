#!/bin/bash
echo "== ~/.unsloth/llama.cpp 结构 =="
ls -la ~/.unsloth/llama.cpp 2>/dev/null | head -40
echo "== llama-server/llama-cli 二进制 =="
find ~/.unsloth -name "llama-server" -o -name "llama-cli" 2>/dev/null | head
echo "== llama.cpp 版本信息（若二进制） =="
for b in $(find ~/.unsloth -name "llama-server" 2>/dev/null | head -1); do echo "BIN=$b"; "$b" --version 2>&1 | head -3; done
echo "== 是否存在 .venv_t5 */* 与 unsloth_studio venv 里的后端选择脚本 =="
ls ~/.unsloth/studio/ 2>/dev/null
echo "== 版本/更新相关文件 =="
find ~/.unsloth -maxdepth 3 \( -iname "*version*" -o -iname "*llama*cpp*" -o -iname "*backend*" -o -iname "*.lock" \) 2>/dev/null | head -30
echo "== 是否有 git 仓库可 pin commit =="
ls -la ~/.unsloth/llama.cpp/.git 2>/dev/null && echo "HAS_GIT" || echo "NO_GIT_DIR at ~/.unsloth/llama.cpp"
echo "== studio venv 中后端分发元数据 =="
find ~/.unsloth/studio -maxdepth 3 -iname "*.json" -path "*backend*" 2>/dev/null | head