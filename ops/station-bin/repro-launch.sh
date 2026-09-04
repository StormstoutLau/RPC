#!/bin/bash
# repro-launch.sh — 取key并在站上后台启动复现打压 (避免内联引号陷阱)
KEY=$(grep -oE 'sk-unsloth-[a-f0-9]+' "$HOME/.unsloth/run-gpt-oss-120b.log" | tail -1)
echo "keylen=${#KEY}"
nohup bash /tmp/repro-fire.sh "$KEY" 8080 > /tmp/repro-fire.out 2>&1 &
echo "started pid=$!"