#!/bin/bash
echo "== 后台 claude 请求探针：8087 是否有新连接/请求 =="
ss -tnp 2>/dev/null | grep 8087 | head
echo "== 最近 llama-server 请求日志（若存在） =="
ls -lt /home/scott-lau/.unsloth/studio/server/*.log 2>/dev/null | head -3
tail -5 /home/scott-lau/.unsloth/studio/server/*.log 2>/dev/null | head -20