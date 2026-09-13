#!/bin/bash
# B->C rsync gpt-oss (C 父目录已建)
set +e
SRC="/data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/"
DST="/data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF"
rsync -e 'ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no' -a --info=progress2 "$SRC" scott-lau@192.168.1.37:"$DST/" 2>&1 | tail -2
echo "rsync_exit=${PIPESTATUS[0]}"
echo "=== C 校验 ==="
ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=no scott-lau@192.168.1.37 "ls -la $DST/ 2>/dev/null | grep -E 'gguf|总计'; echo size:\$(du -sh $DST 2>/dev/null | cut -f1); echo C_md5:\$(md5sum $DST/gpt-oss-120b-MXFP4.gguf 2>/dev/null | cut -d' ' -f1)"
echo "=== B md5 ==="
md5sum "$SRC/gpt-oss-120b-MXFP4.gguf" | cut -d' ' -f1
echo "DONE"