#!/bin/bash
# b5m1a_meta.sh — B5m1a 元数据侦察 (只读): GLM 00001 远端 size/sha256 + 残片前缀校验
set -uo pipefail
DIR="$HOME/.lmstudio/models/unsloth/GLM-5.3-Flash-GGUF"
F="$DIR/GLM-5.3-Flash-UD-IQ4_XS-00001-of-00005.gguf"
API="https://hf-mirror.com/api/models/unsloth/GLM-5.3-Flash-GGUF/tree/main"
URL="https://hf-mirror.com/unsloth/GLM-5.3-Flash-GGUF/resolve/main/GLM-5.3-Flash-UD-IQ4_XS-00001-of-00005.gguf"

echo "=== local fragment ==="
ls -la "$F" 2>/dev/null || echo "LOCAL_ABSENT"
LSIZE=$(stat -c %s "$F" 2>/dev/null || echo 0)
echo "LSIZE=$LSIZE"

echo "=== fuser 写冲突检查 ==="
if fuser "$F" >/dev/null 2>&1; then echo "BUSY: 文件被占用!"; else echo "not_busy"; fi

echo "=== remote meta (hf-mirror API tree) ==="
curl -sS --connect-timeout 20 --max-time 60 "$API" -o /tmp/b5m1a_tree.json || echo "API_FAIL"
python3 - <<'EOF'
import json
try:
    d = json.load(open('/tmp/b5m1a_tree.json'))
except Exception as e:
    print("PARSE_FAIL", e); raise SystemExit
for f in d:
    if not isinstance(f, dict):
        continue
    p = f.get('path', '')
    if '00001-of-00005' in p or p.endswith('mmproj-F16.gguf'):
        lfs = f.get('lfs') or {}
        print(f"META|{p}|size={f.get('size')}|lfs_size={lfs.get('size')}|sha256={lfs.get('oid')}")
EOF

echo "=== prefix check: remote[0:LSIZE] vs local ==="
if [ "$LSIZE" -gt 0 ] && [ "$LSIZE" -lt 500000000 ]; then
  END=$((LSIZE-1))
  curl -sS --connect-timeout 20 -r "0-$END" -o /tmp/b5m1a_prefix.bin "$URL"
  RSIZE=$(stat -c %s /tmp/b5m1a_prefix.bin 2>/dev/null || echo 0)
  echo "RSIZE=$RSIZE (expect $LSIZE)"
  if [ "$RSIZE" = "$LSIZE" ]; then
    LH=$(sha256sum "$F" | awk '{print $1}')
    RH=$(sha256sum /tmp/b5m1a_prefix.bin | awk '{print $1}')
    echo "LOCAL_SHA=$LH"
    echo "REMOTE_PREFIX_SHA=$RH"
    if [ "$LH" = "$RH" ]; then echo "PREFIX_MATCH=YES"; else echo "PREFIX_MATCH=NO"; fi
  else
    echo "PREFIX_MATCH=SIZE_MISMATCH"
  fi
else
  echo "PREFIX_CHECK_SKIPPED (LSIZE=$LSIZE)"
fi
echo "=== B5M1A_META_DONE ==="
