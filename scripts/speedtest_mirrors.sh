#!/bin/bash
# speedtest_mirrors.sh — 测试 GitHub 镜像加速通道下载速率
URLS=(
  "https://ghfast.top/https://github.com/ggml-org/llama.cpp/archive/refs/tags/v0.2.0.tar.gz"
  "https://gh-proxy.com/https://github.com/ggml-org/llama.cpp/archive/refs/tags/v0.2.0.tar.gz"
  "https://ghproxy.net/https://github.com/ggml-org/llama.cpp/archive/refs/tags/v0.2.0.tar.gz"
)
for u in "${URLS[@]}"; do
  F=/tmp/mirror_test.bin
  rm -f "$F"
  timeout 12 curl -sL -o "$F" "$u" 2>/dev/null
  SZ=$(stat -c%s "$F" 2>/dev/null || echo 0)
  HOST=$(echo "$u" | cut -d/ -f3)
  echo "$HOST: $(( SZ/12/1024 )) KB/s"
  rm -f "$F"
done
