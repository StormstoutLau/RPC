#!/bin/bash
# asset_inventory.sh — B 站模型资产全量盘点 (.lmstudio + /data/models)
# 输出: 按模型名聚合, 显示 quant/大小/双库位置, 供去重裁定
echo "=== [1] .lmstudio 顶层模型目录 ==="
sudo du -smh --max-depth=2 /home/scott-lau/.lmstudio/models 2>/dev/null | sort -rh | head -40

echo
echo "=== [2] /data/models 顶层 (含软链解析 -L) ==="
sudo du -smhL --max-depth=2 /data/models 2>/dev/null | sort -rh | head -40

echo
echo "=== [3] /data/models 软链检查 (链接本体 vs 真实占用) ==="
ls -la /data/models/ 2>/dev/null | head -20
echo "--- /data/models/gguf ---"
ls -la /data/models/gguf/ 2>/dev/null | head -20

echo
echo "=== [4] 全盘 GGUF 清单 (size + 路径, 不跟随软链) ==="
sudo find /home/scott-lau/.lmstudio /data/models -name "*.gguf" -printf "%s\t%p\n" 2>/dev/null | sort -rn | awk '{printf "%8.1fG\t%s\n", $1/1073741824, $2}'

echo
echo "=== [5] 双库重叠检测: 文件名相同的 GGUF (basename 匹配) ==="
sudo find /home/scott-lau/.lmstudio /data/models -name "*.gguf" -printf "%s\t%f\t%p\n" 2>/dev/null | sort -t$'\t' -k2 | awk -F'\t' 'prev==$2 {print "DUP-NAME: "$2; print "  A: "p1; print "  B: "$3} {prev=$2; p1=$3}'
