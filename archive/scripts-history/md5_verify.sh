#!/bin/bash
# md5_verify.sh — MANIFEST md5 校验（中文 locale 兼容）
cd /opt/llama.cpp-v0.2.0 || exit 1
sed -n '/\[md5\]/,$p' MANIFEST | tail -n +2 | md5sum -c > /tmp/md5v.log 2>&1
FAIL=$(grep -cv '成功\|: OK' /tmp/md5v.log)
TOTAL=$(wc -l < /tmp/md5v.log)
echo "校验: $((TOTAL-FAIL))/$TOTAL 通过, 失败 $FAIL"
[ "$FAIL" -eq 0 ] || { grep -v '成功\|: OK' /tmp/md5v.log | head -5; exit 1; }
