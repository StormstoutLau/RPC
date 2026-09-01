#!/bin/bash
# asset_inventory_a.sh — A 站模型资产盘点
echo "=== A 站磁盘 ==="
df -h / /data 2>/dev/null | grep -v tmpfs
echo
echo "=== A 站 /data 顶层 ==="
sudo du -sh --max-depth=2 /data 2>/dev/null | sort -rh | head -15
echo
echo "=== A 站 /home/scott-lau 顶层 ==="
sudo du -sh --max-depth=1 /home/scott-lau 2>/dev/null | sort -rh | head -10
echo
echo "=== A 站全盘 GGUF (>2G) ==="
sudo find /home/scott-lau /data -name "*.gguf" -size +2G -printf "%s\t%p\n" 2>/dev/null | sort -rn | awk '{printf "%8.1fG\t%s\n", $1/1073741824, $2}'
echo
echo "=== A 站 rpccache ==="
sudo du -sh /data/rpccache 2>/dev/null
