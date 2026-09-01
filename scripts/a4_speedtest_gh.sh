#!/bin/bash
# a4_speedtest_gh.sh — B站测 GitHub 镜像通道对 vllm-rocm release asset 的速率
BASE="https://github.com/lemonade-sdk/vllm-rocm/releases/download/vllm0.25.2.dev0%2Brocm7.15.0a20260724.g752a3a504.d20260724-rocm7.15.0-gfx1151/vllm0.25.2.dev0%2Brocm7.15.0a20260724.g752a3a504.d20260724-rocm7.15.0-gfx1151-x64.part01-of-02.tar.gz"
for m in "https://ghfast.top/" "https://gh-proxy.com/" "https://ghproxy.net/"; do
  F=/tmp/gh_speed_test.bin
  rm -f "$F"
  timeout 15 curl -sL -o "$F" "${m}${BASE}" 2>/dev/null
  SZ=$(stat -c%s "$F" 2>/dev/null || echo 0)
  HOST=$(echo "$m" | cut -d/ -f3)
  echo "$HOST: $(( SZ/15/1024/1024 )) MB/s (15s: $(( SZ/1024/1024 )) MB)"
  rm -f "$F"
done
echo "GH_SPEEDTEST_DONE"
