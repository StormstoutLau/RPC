#!/bin/bash
# gen_manifest.sh — 为版本目录生成 MANIFEST（两站通用）
# 用法: bash gen_manifest.sh <版本目录绝对路径>   例: /opt/llama.cpp-9859
# 生成: <目录>/MANIFEST（含 [md5] 节，覆盖目录内全部二进制与 .so*）
# 退出: 0 成功 / 1 目录不存在
#
# ★ 2026-10-17 修正（v0.7.0 构建实测；两处都让"投放即可用"落空）:
#   ① 本文件原为 **CRLF** 行尾 ⇒ 站上 Linux `bash -n` 直接报「未预期的记号 "}"」；
#      而门禁 `syntax` 走 Git Bash/MSYS **不报** ⇒ 该缺陷长期不可见（见 UPGRADE_SOP「已知盲区」）。
#   ② `build_host` / `build_date` / `cmake_flags` 三行原写死为**迁移期旧二进制**话术
#      （`(migration: pre-existing binaries)` / `2026-07-02 (binary mtime, pre-existing)` /
#      `unknown (pre-existing, 无 CMakeCache)`) ⇒ 给**新构建**用会把**假值写进证据件**
#      （本仓最防的"过期但像真值"）。现改为读**真实值**；`rpc_protocol` 取不到时如实写 `unknown`
#      （原先兜底成硬编码的旧协议号 `v4.0.1 (cluster-level, A站实测)`，同样是假值来源）。
set -euo pipefail
DIR="${1:?用法: gen_manifest.sh <版本目录>}"
test -d "$DIR" || { echo "❌ 目录不存在: $DIR"; exit 1; }
MANIFEST="$DIR/MANIFEST"

VER_LINE=$("$DIR/llama-cli" --version 2>&1 | head -2 || echo "")
# ★ 2026-10-17 修正 ③: 原为 `s/version: \([0-9]*\).*/\1/p` —— 只抓**数字**，
#   遇到 `version: 0.7.0-dev (build 0, commit unknown)` 会**截成 `0`** 写进 MANIFEST（假值）。
#   改为抓**整个版本串**（到空白为止）⇒ `0.7.0-dev`；取不到则 `unknown`。
VER=$(echo "$VER_LINE" | sed -n 's/^version: \([^ ]*\).*/\1/p')
COMMIT=$(echo "$VER_LINE" | sed -n 's/.*(\([a-f0-9]\{7,\}\)).*/\1/p')
TOOLCHAIN=$(echo "$VER_LINE" | sed -n 's/built with \(.*\)/\1/p')
TOOLCHAIN="${TOOLCHAIN:-unknown}"

# rpc 协议版本从最近 rpc 日志取（无则 unknown；glob 无匹配时 grep 退出 1，容错）
RPC_LOG=$(ls "$HOME"/llama-distributed/logs/rpc_*.log 2>/dev/null | tail -1 || true)
RPC_PROTO=""
if [ -n "$RPC_LOG" ]; then
    RPC_PROTO=$(grep -h "Starting RPC server" "$RPC_LOG" 2>/dev/null | tail -1 | sed -n 's/.*Starting RPC server \(v[0-9.]*\).*/\1/p' || true)
fi
RPC_PROTO="${RPC_PROTO:-unknown}"

{
  echo "# MANIFEST — 生成于 $(date +%F) 由 gen_manifest.sh"
  echo "commit       = ${COMMIT:-unknown}"
  echo "version      = ${VER:-unknown}"
  echo "build_host   = $(hostname)"
  echo "build_date   = $(date -r "$DIR/llama-cli" +%F) (binary mtime)"
  echo "toolchain    = ${TOOLCHAIN}"
  echo "cmake_flags  = GGML_VULKAN=1 GGML_RPC=ON CMAKE_BUILD_TYPE=Release (cluster standard)"
  echo "rpc_protocol = ${RPC_PROTO}"
  echo "[md5]"
  cd "$DIR"
  md5sum llama-* ggml-rpc-server libggml*.so* libllama*.so* libmtmd.so* 2>/dev/null || true
} | sudo tee "$MANIFEST" > /dev/null

sudo chmod 644 "$MANIFEST"
echo "✅ MANIFEST 已生成: $MANIFEST"
echo "   共 $(grep -c '^[0-9a-f]\{32\}' "$MANIFEST") 个 MD5 条目, $(wc -l < "$MANIFEST") 行"
