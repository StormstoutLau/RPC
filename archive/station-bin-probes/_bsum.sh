#!/bin/bash
echo "== 本机 (B) infer 脚本哈希 =="
md5sum /usr/local/bin/infer-load /usr/local/bin/infer-unload /usr/local/bin/infer-list | awk '{print $1}'
echo "== 当前模型 =="
ps -eo cmd | grep "[u]nsloth studio run" | grep -oE "gpt-oss[^ ]*" | head -1
ss -tln 2>/dev/null | grep ":8080" | awk '{print "8080 listening"}'