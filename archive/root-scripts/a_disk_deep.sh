#!/bin/bash
# a_disk_deep.sh — A 站磁盘深查 (大目录 + GGUF 全量)
echo "=== A 站 /data 顶层 ==="
sudo du -sh --max-depth=2 /data 2>/dev/null | sort -rh | head -15
echo
echo "=== A 站 /home/scott-lau 顶层 ==="
sudo du -sh --max-depth=1 /home/scott-lau 2>/dev/null | sort -rh | head -10
echo
echo "=== A 站 / 顶层 ==="
sudo du -xh --max-depth=1 / 2>/dev/null | sort -rh | head -10
echo
echo "=== A 站全盘 GGUF (所有) ==="
sudo find /home/scott-lau /data -name "*.gguf" -printf "%s\t%p\n" 2>/dev/null | sort -rn | awk '{printf "%8.1fG\t%s\n", $1/1073741824, $2}'
echo
echo "=== A 站 models 目录 (b5k 同步目标) ==="
ls -la /home/scott-lau/models/ 2>/dev/null | head -15
sudo du -shL /home/scott-lau/models 2>/dev/null
