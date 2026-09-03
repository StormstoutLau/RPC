#!/bin/bash
echo "=== infer-load 尾部 (systemd 启动逻辑) ==="
sed -n '80,160p' /usr/local/bin/infer-load
echo
echo "=== llama-serve-instance ==="
cat /usr/local/bin/llama-serve-instance