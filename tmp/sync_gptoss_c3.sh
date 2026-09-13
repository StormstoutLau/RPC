#!/bin/bash
# 在 B 站直接执行 B->C rsync (host key 已确认 OK)
set +e
SRC="/data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/"
DST="/data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF"
echo "=== rsync 开始 ==="
rsync -e 'ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no' -a --info=progress2 "$SRC" scott-lau@192.168.1.37:"$DST/" 2>&1 | tail -3
echo "rsync_exit=$?"
echo "=== C 侧校验 ==="
ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=no scott-lau@192.168.1.37 "ls -la $DST/ 2>/dev/null; echo size:\$(du -sh $DST 2>/dev/null | cut -f1); md5sum $DST/gpt-oss-120b-MXFP4.gguf 2>/dev/null"
echo "=== B 对照 md5 ==="
md5sum "$SRC/gpt-oss-120b-MXFP4.gguf"
echo "DONE"