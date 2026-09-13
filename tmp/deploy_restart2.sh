#!/bin/bash
# 修复后重新部署 + setsid 启动 (PID 文件防重)
set -u
cp /tmp/dl_ms_enhanced.sh ~/bin/dl_ms_enhanced.sh
chmod +x ~/bin/dl_ms_enhanced.sh
rm -f ~/dl-ms.pid
cd ~
setsid nohup bash ~/bin/dl_ms_enhanced.sh > /tmp/dl_ms_enhanced.log 2>&1 < /dev/null &
echo "launched pid=$!"
sleep 5
echo "=== 进程 ==="
ps -eo pid,etime,cmd | grep dl_ms_enhanced | grep -v grep | cut -c1-100
echo "=== 20s 后分片3 大小 (应增长) ==="
sleep 20
stat -c "%s" ~/.lmstudio/models/lmstudio-community/Qwen3.8-Flash-Next-GGUF/UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00003-of-00003.gguf 2>/dev/null