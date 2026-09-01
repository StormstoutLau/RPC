#!/bin/bash
# speedtest_asset.sh — 测试 GitHub release asset (objects.githubusercontent CDN) 速率
F=/tmp/asset_test.bin
timeout 15 curl -sL -o "$F" https://github.com/ggml-org/llama.cpp/releases/download/v0.2.0/llama-bench-linux-x64.zip 2>/dev/null
SZ=$(stat -c%s "$F" 2>/dev/null || echo 0)
echo "release-asset 直连: $(( SZ/15/1024 )) KB/s (下载 $(( SZ/1024 )) KB)"
rm -f "$F"
