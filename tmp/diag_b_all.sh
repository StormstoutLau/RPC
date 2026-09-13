#!/bin/bash
echo "=== B站 所有相关进程 ==="
ps aux | grep -E 'scp|llama-server|run_questions|md5sum' | grep -v grep | awk '{print $2, $3"%", $4"%", substr($0, index($0,$11), 140)}'
echo ""
echo "=== Q3.8F runner.log ==="
tail -3 /tmp/res_q38f_fix2/runner.log 2>/dev/null
echo ""
echo "=== fable 传输日志 ==="
cat /tmp/fable_transfer.log 2>/dev/null | head -8
echo "日志内容终止"
echo ""
echo "=== fable md5 结果 ==="
cat /tmp/fable_b.md5 2>/dev/null || echo "md5 尚未完成"
echo ""
echo "=== 8094 健康 ==="
curl -s --max-time 4 http://127.0.0.1:8094/health 2>/dev/null
echo ""