#!/bin/bash
# C 站: 从 B rsync gpt-oss-120b MXFP4 (60G) - host key 已修复
set +e
SRC="/data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/"
DST="/data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF"
ssh -o ConnectTimeout=8 scott-lau@192.168.1.32 "mkdir -p /data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF; rsync -e 'ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no' -a --info=progress2 $SRC scott-lau@192.168.1.37:$DST/ 2>&1 | tail -3"
echo "=== 校验 ==="
ssh -o ConnectTimeout=8 scott-lau@192.168.1.37 "ls -la $DST/; du -sh $DST/; md5sum $DST/gpt-oss-120b-MXFP4.gguf"
echo "--- B 对照 ---"
ssh -o ConnectTimeout=8 scott-lau@192.168.1.32 "md5sum $SRC/gpt-oss-120b-MXFP4.gguf"
echo "DONE"