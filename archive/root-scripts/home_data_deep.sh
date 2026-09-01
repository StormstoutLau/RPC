#!/bin/bash
# home_data_deep.sh — B 站 /home 与 /data 的重叠与大文件画像
echo "=== /home 顶层 ==="
sudo du -xh --max-depth=1 /home 2>/dev/null | sort -rh | head -6
echo
echo "=== /home/scott-lau 顶层 ==="
sudo du -xh --max-depth=1 /home/scott-lau 2>/dev/null | sort -rh | head -10
echo
echo "=== /data 顶层 ==="
sudo du -xh --max-depth=2 /data 2>/dev/null | sort -rh | head -12
echo
echo "=== GGUF 大文件 top15 (全盘 /home+/data) ==="
sudo find /home /data -name "*.gguf" -size +5G -printf "%s\t%p\n" 2>/dev/null | sort -rn | head -15 | awk '{printf "%.0fG\t%s\n", $1/1073741824, $2}'
echo
echo "=== 软链审计 (/data/models 是否为链接聚合) ==="
ls -la /data/models 2>/dev/null | head -3
ls -la /home/scott-lau/models 2>/dev/null | head -3