#!/bin/bash
# b5m1_verify.sh — B5m1 补采证据 (只读)
# 1) A 站 df; 2) GLM 00001 分片缺失确认 (B); 3) .incomplete 残留统计 (两站);
# 4) 跨站重复抽样 sha256 (gpt-oss-20b 12GB, 验证 "同名同字节=同文件" 假设)
echo "=== HOST ==="; hostname

echo "=== DF ==="
df -h / /data 2>/dev/null | awk '!seen[$1]++'

echo "=== GLM dir full listing (若存在) ==="
ls -la "$HOME/.lmstudio/models/unsloth/GLM-5.3-Flash-GGUF/" 2>/dev/null || echo "GLM_DIR_ABSENT"

echo "=== .incomplete 残留统计 ==="
for base in /data/models "$HOME/models"; do
  [ -d "$base" ] || continue
  find "$base" -name '*.incomplete' -printf '%s|%p\n' 2>/dev/null \
    | awk -v b="$base" '{t+=$1; n++} END{printf "INCOMPLETE|%s|count=%d|bytes=%d (%.1f GiB)\n", b, n, t, t/1073741824}'
done

echo "=== B 站 .lmstudio 中等文件明细 (1MB-100MB) ==="
find "$HOME/.lmstudio/models" -type f -size +1M -size -100M -printf '%s|%p\n' 2>/dev/null | sort -t'|' -k2 | head -20

echo "=== sha256 抽样: gpt-oss-20b-MXFP4.gguf (12.1GB, ~1min) ==="
F="$HOME/.lmstudio/models/lmstudio-community/gpt-oss-20b-GGUF/gpt-oss-20b-MXFP4.gguf"
if [ -f "$F" ]; then
  sha256sum "$F"
else
  echo "SAMPLE_FILE_ABSENT"
fi

echo "=== B5M1_VERIFY_DONE ==="
