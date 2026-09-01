#!/bin/bash
# b5i_recon.sh — B5i 模型加载层侦察: 枚举 /data/models 结构 (B 站)
echo "===== $(hostname -s) /data/models 侦察 @ $(date '+%F %T') ====="
echo "--- [1] GGUF repo 列表 (publisher/repo) ---"
find /data/models/gguf -mindepth 2 -maxdepth 2 -type d 2>/dev/null | sort | while read -r d; do
  N=$(find -L "$d" -name '*.gguf' 2>/dev/null | wc -l)
  SZ=$(du -sLh "$d" 2>/dev/null | cut -f1)
  echo "  ${SZ}  ${N}个gguf  $d"
done
echo ""
echo "--- [2] GGUF 文件级明细 (repo 内多量化版本) ---"
find /data/models/gguf -mindepth 3 -name '*.gguf' 2>/dev/null | while read -r f; do
  SZ=$(du -hL "$f" 2>/dev/null | cut -f1)
  echo "  ${SZ}  $f"
done
echo ""
echo "--- [3] AWQ/safetensors 模型 (非 gguf 目录) ---"
find /data/models -maxdepth 1 -mindepth 1 -type d -o -maxdepth 1 -mindepth 1 -type l 2>/dev/null | grep -v '/gguf' | while read -r d; do
  SZ=$(du -sLh "$d" 2>/dev/null | cut -f1)
  ST=$(find -L "$d" -name '*.safetensors' 2>/dev/null | wc -l)
  echo "  ${SZ}  ${ST}个safetensors  $d"
done
echo ""
echo "--- [4] rpc cache 现状 (A 站用, 此处仅 B 站视角) ---"
ls /data/rpccache 2>/dev/null || echo "B 站无 rpccache (正确: 缓存只在 A 站)"
echo ""
echo "--- [5] 磁盘空间 ---"
df -h /data | tail -1
