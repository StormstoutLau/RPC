#!/bin/bash
echo "=== B unsloth CLI 版本 ==="
~/.local/bin/unsloth --version 2>&1 | head -2
echo "=== B ~/.unsloth 目录 ==="
ls ~/.unsloth/ 2>/dev/null
echo "=== B unsloth llama.cpp marker (后端) ==="
cat ~/.unsloth/llama.cpp/UNSLOTH_PREBUILT_INFO.json 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print('tag=',d.get('tag'),'source_commit=',d.get('source_commit'))" 2>/dev/null || echo "no marker (source build)"
echo "=== B 当前 model 目录 ==="
ls /data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/ 2>/dev/null