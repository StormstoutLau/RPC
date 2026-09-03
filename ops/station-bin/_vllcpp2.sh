#!/bin/bash
echo "== llama-server 符号链接关系 =="
ls -la ~/.unsloth/llama.cpp/llama-server ~/.unsloth/llama.cpp/build/bin/llama-server 2>/dev/null
echo "== llama_cpp_freshness 内容 =="
cat ~/.unsloth/studio/cache/llama_cpp_freshness 2>/dev/null; echo
ls -la ~/.unsloth/studio/cache/ 2>/dev/null | head
echo "== 版本来源提交文件 =="
grep -m1 "commit\|GIT_COMMIT\|VERSION\|build [0-9]" ~/.unsloth/llama.cpp/build/CMakeCache.txt 2>/dev/null | head
echo "== 后端决策逻辑（grep 关键 env/表） =="
SV=~/.unsloth/studio/unsloth_studio
grep -rl "UNSLOTH_LLAMA_CPP_BACKEND\|llama_cpp_freshness\|llama.cpp" "$SV" 2>/dev/null | head -20
echo "== llama_cpp_freshness 在代码里的引用 =="
grep -rn "llama_cpp_freshness" "$SV" 2>/dev/null | head
echo "== 版本 pin/更新栅栏逻辑 =="
grep -rn "UNSLOTH_LLAMA_CPP_BACKEND" "$SV" 2>/dev/null | head
echo "== 后端构建完成标记 =="
find ~/.unsloth/study ~/.unsloth/llama.cpp -maxdepth 3 -iname "*built*" -o -iname "*backend*" -o -iname "*installed*" 2>/dev/null | head