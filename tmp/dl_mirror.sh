#!/bin/bash
# C 站直连 hf-mirror 下载两模型 UD-IQ4_XS (方案 A 实体目录), wget -c 断点续传
set -u
BASE=https://hf-mirror.com/unsloth
M_ROOT=~/.lmstudio/models/lmstudio-community
mkdir -p "$M_ROOT/MiniMax-M2.7-GGUF/UD-IQ4_XS"
mkdir -p "$M_ROOT/Qwen3.8-Flash-Next-GGUF/UD-IQ4_XS"

dl() { # $1=repo $2=dst-dir $3...=files(相对 repo)
  local repo="$1"; shift
  local dst="$1"; shift
  for f in "$@"; do
    local out="$dst/$(basename "$f")"
    [ -f "$out" ] || : > /dev/null
    echo ">>> downloading $repo/$f -> $out"
    timeout 3600 wget -q -c --show-progress=off --timeout=60 --tries=5 \
      "$BASE/$repo/resolve/main/$f" -O "$out" 2>&1 | tail -2
    echo "    exit=$? size=$(stat -c%s "$out" 2>/dev/null)"
  done
}

# M2.7 UD-IQ4_XS (4 分片)
dl "MiniMax-M2.7-GGUF" "$M_ROOT/MiniMax-M2.7-GGUF/UD-IQ4_XS" \
  UD-IQ4_XS/MiniMax-M2.7-UD-IQ4_XS-00001-of-00004.gguf \
  UD-IQ4_XS/MiniMax-M2.7-UD-IQ4_XS-00002-of-00004.gguf \
  UD-IQ4_XS/MiniMax-M2.7-UD-IQ4_XS-00003-of-00004.gguf \
  UD-IQ4_XS/MiniMax-M2.7-UD-IQ4_XS-00004-of-00004.gguf

# Q3.8F UD-IQ4_XS (3 分片)
dl "Qwen3.8-Flash-Next-GGUF" "$M_ROOT/Qwen3.8-Flash-Next-GGUF/UD-IQ4_XS" \
  UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf \
  UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00002-of-00003.gguf \
  UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00003-of-00003.gguf

echo "=== ALL DONE ==="
echo "M2.7:"; ls -la "$M_ROOT/MiniMax-M2.7-GGUF/UD-IQ4_XS/"
echo "Q3.8F:"; ls -la "$M_ROOT/Qwen3.8-Flash-Next-GGUF/UD-IQ4_XS/"