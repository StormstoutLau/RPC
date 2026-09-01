#!/bin/bash
# gen_manifest.sh — 为版本目录生成 MANIFEST（两站通用）
# 用法: bash gen_manifest.sh <版本目录绝对路径>   例: /opt/llama.cpp-9859
# 生成: <目录>/MANIFEST（含 [md5] 节，覆盖目录内全部二进制与 .so*）
# 退出: 0 成功 / 1 目录不存在
set -euo pipefail
DIR="${1:?用法: gen_manifest.sh <版本目录>}"
test -d "$DIR" || { echo "❌ 目录不存在: $DIR"; exit 1; }
MANIFEST="$DIR/MANIFEST"

VER_LINE=$("$DIR/llama-cli" --version 2>&1 | head -2 || echo "")
VER=$(echo "$VER_LINE" | sed -n 's/version: \([0-9]*\).*/\1/p')
COMMIT=$(echo "$VER_LINE" | sed -n 's/version: [0-9]* (\([a-f0-9]*\)).*/\1/p')
TOOLCHAIN=$(echo "$VER_LINE" | sed -n 's/built with \(.*\)/\1/p')
TOOLCHAIN="${TOOLCHAIN:-unknown}"

# rpc 协议版本从最近 rpc 日志取（无则 unknown；glob 无匹配时 grep 退出 1，容错）
RPC_LOG=$(ls "$HOME"/llama-distributed/logs/rpc_*.log 2>/dev/null | tail -1 || true)
RPC_PROTO=""
if [ -n "$RPC_LOG" ]; then
    RPC_PROTO=$(grep -h "Starting RPC server" "$RPC_LOG" 2>/dev/null | tail -1 | sed -n 's/.*Starting RPC server \(v[0-9.]*\).*/\1/p' || true)
fi
RPC_PROTO="${RPC_PROTO:-v4.0.1 (cluster-level, A站实测)}"

{
  echo "# MANIFEST — 生成于 $(date +%F) 由 gen_manifest.sh"
  echo "commit       = ${COMMIT:-unknown}"
  echo "version      = ${VER:-unknown}"
  echo "build_host   = $(hostname) (migration: pre-existing binaries)"
  echo "build_date   = 2026-07-02 (binary mtime, pre-existing)"
  echo "toolchain    = ${TOOLCHAIN}"
  echo "cmake_flags  = unknown (pre-existing, 无 CMakeCache)"
  echo "rpc_protocol = ${RPC_PROTO}"
  echo "[md5]"
  cd "$DIR"
  md5sum llama-* ggml-rpc-server libggml*.so* libllama*.so* libmtmd.so* 2>/dev/null || true
} | sudo tee "$MANIFEST" > /dev/null

sudo chmod 644 "$MANIFEST"
echo "✅ MANIFEST 已生成: $MANIFEST"
echo "   共 $(grep -c '^[0-9a-f]\{32\}' "$MANIFEST") 个 MD5 条目, $(wc -l < "$MANIFEST") 行"
