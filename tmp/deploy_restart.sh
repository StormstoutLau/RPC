#!/bin/bash
# 部署脚本到持久目录 + setsid 独立驻留启动续传
set -u
mkdir -p ~/bin
cp /tmp/dl_ms_enhanced.sh ~/bin/dl_ms_enhanced.sh
chmod +x ~/bin/dl_ms_enhanced.sh
echo "deployed to ~/bin/dl_ms_enhanced.sh"
cd ~
setsid nohup bash ~/bin/dl_ms_enhanced.sh > /tmp/dl_ms_enhanced.log 2>&1 < /dev/null &
echo "launched pid=$!"
sleep 3
echo "=== 进程 ==="
ps -eo pid,cmd | grep dl_ms_enhanced | grep -v grep | cut -c1-100
sleep 25
echo "=== 状态 (续传点) ==="
tail -4 ~/dl-ms-status.txt
echo "=== 实时进度 ==="
cat ~/dl-ms-progress.txt 2>/dev/null