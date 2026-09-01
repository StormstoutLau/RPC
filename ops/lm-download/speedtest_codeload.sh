#!/bin/bash
# speedtest_codeload.sh — 测试 codeload tarball 下载速率
# 用法: PROXY=1 bash speedtest_codeload.sh  (PROXY=1 时走 127.0.0.1:7890)
if [ "${PROXY:-0}" = "1" ]; then
  export https_proxy=http://127.0.0.1:7890 http_proxy=http://127.0.0.1:7890
fi
F=/tmp/codeload_test.bin
timeout 15 curl -sL -o "$F" https://codeload.github.com/ggml-org/llama.cpp/tar.gz/refs/tags/v0.2.0 2>/dev/null
SZ=$(stat -c%s "$F" 2>/dev/null || echo 0)
echo "速率: $(( SZ/15/1024 )) KB/s (15s 已下载 $(( SZ/1024/1024 )) MB)"
rm -f "$F"
