#!/bin/bash
# B 站: 将 nemotron 120B (3分片) rsync 到 C 站 LM Studio 目录
set +e
SRC_DIR=/home/scott-lau/.lmstudio/models/lmstudio-community/NVIDIA-Nemotron-3-Super-120B-A12B-GGUF
DST_HOST=scott-lau@192.168.1.37
DST_DIR=/home/scott-lau/.lmstudio/models/lmstudio-community/NVIDIA-Nemotron-3-Super-120B-A12B-GGUF

echo "=== 1. 源文件 ==="
ls -la "$SRC_DIR" | grep -E 'gguf|sha256'
echo "=== 2. 建目标目录 ==="
ssh -o ConnectTimeout=8 "$DST_HOST" "mkdir -p $DST_DIR" && echo "[OK] 目录已建"

echo "=== 3. rsync (81G, 管理网 ~110MB/s, 预计 ~12-15min) ==="
time rsync -a --info=progress2 --partial -e "ssh -o ConnectTimeout=8" "$SRC_DIR/" "$DST_HOST:$DST_DIR/"
RC=$?
echo "rsync rc=$RC"
[ $RC -ne 0 ] && { echo "!! rsync 失败"; exit 1; }

echo "=== 4. 大小核对 ==="
SRCSZ=$(du -sb "$SRC_DIR" | cut -f1)
DSTSZ=$(ssh -o ConnectTimeout=8 "$DST_HOST" "du -sb $DST_DIR" | cut -f1)
echo "源=$SRCSZ 目标=$DSTSZ"
[ "$SRCSZ" = "$DSTSZ" ] && echo "大小一致 ✅" || echo "大小不一致 ❌ (差 $(( (DSTSZ - SRCSZ) / 1024 / 1024 ))MB)"

echo "=== 5. 逐文件 size 对比 ==="
for f in "$SRC_DIR"/*.gguf "$SRC_DIR"/.sha256; do
  bn=$(basename "$f")
  ss=$(stat -c %s "$f")
  ds=$(ssh -o ConnectTimeout=8 "$DST_HOST" "stat -c %s $DST_DIR/$bn" 2>/dev/null)
  [ "$ss" = "$ds" ] && echo "[OK] $bn $ss" || echo "[MISS] $bn 源=$ss 目标=$ds"
done