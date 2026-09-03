#!/bin/bash
SV=~/.unsloth/studio/unsloth_studio/lib/python3.13/site-packages/studio
echo "===== 关键函数 is_behind / 是否存在自动升级 ====="
sed -n '155,235p' "$SV/backend/utils/llama_cpp_freshness.py"
echo ""
echo "===== _SKIP_GGUF_BUILD / 安装期跳过开关 全仓库引用 ====="
grep -rn "_SKIP_GGUF_BUILD\|SKIP_LLAMA\|skip.*prebuilt\|UNSLOTH_PREBUILT_INFO" "$SV" --include=*.py 2>/dev/null | head -25
echo ""
echo "===== 本机 marker 文件 ====="
find ~/.unsloth -name "UNSLOTH_PREBUILT_INFO.json" 2>/dev/null -exec echo "FOUND:{}" \; -exec cat {} \; | head -30
echo ""
echo "===== 启动是否自动触发 prebuilt 安装/替换 (lifespan/install 触发点) ====="
grep -rn "install_llama_prebuilt\|llama_cpp_update\|def lifespan\|ensure.*prefix\|prebuilt.*(install\|update" "$SV/backend/main.py" "$SV/backend/routes/llama.py" 2>/dev/null | head -20