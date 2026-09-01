#!/bin/bash
# b5m1a_final_check.sh — 收官校验: GLM 全部 6 文件 sha256 对照远端 LFS oid (B5m4 已验过 00002-00005, 此处全量复验)
set -uo pipefail
DIR="$HOME/.lmstudio/models/unsloth/GLM-5.3-Flash-GGUF"
# 期望 sha256 (来自 hf-mirror tree API, 2026-08-29)
declare -A EXP=(
  ["GLM-5.3-Flash-UD-IQ4_XS-00001-of-00005.gguf"]=eec97673e9acb38f8682250e778f88991e731771bab8d3c0b787985949aacefa
  ["GLM-5.3-Flash-UD-IQ4_XS-00002-of-00005.gguf"]=7d64cf0395672c4322012841abec502ea7e20518299bb5e3069003f06f9e6de9
  ["GLM-5.3-Flash-UD-IQ4_XS-00003-of-00005.gguf"]=7c2c63c9c30f8060428fdf2ac935dbf2ee9ad8f771d62b6ae47a7f7f2c1520e7
  ["GLM-5.3-Flash-UD-IQ4_XS-00004-of-00005.gguf"]=06c90f191871317c92dd9d25a353b687aed44c50f3ac6c713e9fe410bc2d26dd
  ["GLM-5.3-Flash-UD-IQ4_XS-00005-of-00005.gguf"]=66ebf9ec85e04d3f44af674ae4f694acbc89cc53db75e42f2f4d3646bf321c0d
  ["mmproj-F16.gguf"]=96ccc182997646ad4405385a1987b1ac1e6adccd2669de43c3ea39692699ed27
)
ORDER=(
  "GLM-5.3-Flash-UD-IQ4_XS-00001-of-00005.gguf"
  "mmproj-F16.gguf"
  "GLM-5.3-Flash-UD-IQ4_XS-00005-of-00005.gguf"
  "GLM-5.3-Flash-UD-IQ4_XS-00004-of-00005.gguf"
  "GLM-5.3-Flash-UD-IQ4_XS-00003-of-00005.gguf"
  "GLM-5.3-Flash-UD-IQ4_XS-00002-of-00005.gguf"
)
PASS=0; FAIL=0
for f in "${ORDER[@]}"; do
  p="$DIR/$f"
  if [ ! -f "$p" ]; then echo "MISSING|$f"; FAIL=$((FAIL+1)); continue; fi
  h=$(sha256sum "$p" | awk '{print $1}')
  if [ "$h" = "${EXP[$f]}" ]; then
    echo "OK|$f|$(stat -c %s "$p")"
    PASS=$((PASS+1))
  else
    echo "SHA_MISMATCH|$f|local=$h|expect=${EXP[$f]}"
    FAIL=$((FAIL+1))
  fi
done
echo "SUMMARY: pass=$PASS fail=$FAIL (of ${#ORDER[@]})"
echo "=== B5M1A_FINAL_DONE ==="
