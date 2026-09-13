#!/bin/bash
echo "== 9/1 运行残留 (inference.conf / run_server.sh) =="
cat /llama-distributed/inference.conf 2>/dev/null | head -25
echo "--- run_server.sh CMD 部分 ---"
grep -nE "CMD|rpc|ot|split|ngl" /llama-distributed/run_server.sh 2>/dev/null | head -15
echo
echo "== 是否有 fit/ot 记录 =="
ls -la /tmp/*.conf /tmp/*v4* 2>/dev/null | head
grep -riE "split-mode|override-tensor|--rpc" /tmp/*.log /tmp/*.sh 2>/dev/null | head -10