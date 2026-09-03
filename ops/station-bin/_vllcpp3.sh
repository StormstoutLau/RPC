#!/bin/bash
SV=~/.unsloth/studio/unsloth_studio/lib/python3.13/site-packages/studio
echo "===== llama_cpp_freshness.py (全文) ====="
cat "$SV/backend/utils/llama_cpp_freshness.py" 2>/dev/null | head -160
echo ""
echo "===== 检查 install marker / is_behind / 离线 语义 ====="
grep -n "is_behind\|read_install_marker\|write_install_marker\|offline\|skip\|max_age\|CACHE\|no_network\|never" "$SV/backend/utils/llama_cpp_freshness.py" 2>/dev/null | head -40