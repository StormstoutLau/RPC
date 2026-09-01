#!/bin/bash
# B5j 资源采集: DeepSeek RPC 加载后两站内存/GTT
echo "B站 $(hostname):"
free -g | awk 'NR==2{print "  used "$3"G / "$2"G"}'
cat /sys/class/drm/card*/device/mem_info_gtt_used 2>/dev/null | awk '{printf "  GTT %.1fG\n", $1/1073741824}'
echo "A站:"
ssh 192.168.1.11 'free -g | awk "NR==2{print \"  used \"\$3\"G / \"\$2\"G\"}; cat /sys/class/drm/card*/device/mem_info_gtt_used 2>/dev/null | awk "{printf \"  GTT %.1fG\n\", \$1/1073741824}"'
df -h /data 2>/dev/null | tail -1 | awk '{print "  B /data: "$3" used, "$4" avail"}'
ssh 192.168.1.11 'df -h /data | tail -1 | awk "{print \"  A /data: \"\$3\" used, \"\$4\" avail\"}"'
