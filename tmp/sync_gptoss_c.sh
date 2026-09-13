#!/bin/bash
# C 站: 建立模型目录 + 从 B 站 rsync gpt-oss-120b MXFP4 (60G)
set +e
SRC="/data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/"
DST="/data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF"
echo "=== 1. C 站建目录 ==="
mkdir -p "$DST" && echo "目录 OK: $DST"
echo ""
echo "=== 2. B->C rsync (速度/进度) ==="
ssh -o ConnectTimeout=8 scott-lau@192.168.1.32 "rsync -e 'ssh -o ConnectTimeout=10' -a --info=progress2 $SRC scott-lau@192.168.1.37:$DST/ 2>&1 | tail -5"
echo ""
echo "=== 3. C 站校验 ==="
ls -la "$DST/" 2>/dev/null
echo "size: $(du -sh "$DST" 2>/dev/null | cut -f1)"
md5sum "$DST/gpt-oss-120b-MXFP4.gguf" 2>/dev/null
echo "--- B 对照 ---"
ssh -o ConnectTimeout=8 scott-lau@192.168.1.32 "md5sum $SRC/gpt-oss-120b-MXFP4.gguf" 2>/dev/null
echo "DONE"