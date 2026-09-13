#!/bin/bash
echo "=== 全部相关进程 ==="
ps -eo pid,etime,cmd | grep -E "dl_ms_enhanced|wget" | grep -v grep | cut -c1-110
echo "=== 分片3 当前大小 (应增长) ==="
stat -c "%s %n" ~/.lmstudio/models/lmstudio-community/Qwen3.8-Flash-Next-GGUF/UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00003-of-00003.gguf 2>/dev/null
echo "=== 等待 30s 后 ==="
sleep 30
stat -c "%s %n" ~/.lmstudio/models/lmstudio-community/Qwen3.8-Flash-Next-GGUF/UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00003-of-00003.gguf 2>/dev/null
echo "=== PROGRESS 更新 ==="
cat ~/dl-ms-progress.txt 2>/dev/null
echo "=== STATUS 尾 ==="
tail -3 ~/dl-ms-status.txt