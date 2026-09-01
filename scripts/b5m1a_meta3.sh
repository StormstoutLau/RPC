#!/bin/bash
# b5m1a_meta3.sh — 修正: 分片在子目录 UD-IQ4_XS/ 下, 修正 API+URL 路径
set -uo pipefail
DIR="$HOME/.lmstudio/models/unsloth/GLM-5.3-Flash-GGUF"
F="$DIR/GLM-5.3-Flash-UD-IQ4_XS-00001-of-00005.gguf"
API="https://hf-mirror.com/api/models/unsloth/GLM-5.3-Flash-GGUF/tree/main/UD-IQ4_XS"
URL="https://hf-mirror.com/unsloth/GLM-5.3-Flash-GGUF/resolve/main/UD-IQ4_XS/GLM-5.3-Flash-UD-IQ4_XS-00001-of-00005.gguf"
LSIZE=$(stat -c %s "$F" 2>/dev/null || echo 0)

echo "=== 1. 子目录 tree (含 size/sha256) ==="
curl -sS --connect-timeout 20 --max-time 60 "$API" -o /tmp/b5m1a_tree3.json || echo "API_FAIL"
python3 - <<'EOF'
import json
try:
    d = json.load(open('/tmp/b5m1a_tree3.json'))
except Exception as e:
    print("PARSE_FAIL", e); raise SystemExit
for f in d if isinstance(d, list) else []:
    if not isinstance(f, dict):
        continue
    p = f.get('path', '')
    lfs = f.get('lfs') or {}
    print(f"META|{p}|size={f.get('size')}|lfs_size={lfs.get('size')}|sha256={lfs.get('oid')}")
EOF

echo "=== 2. Content-Length (带 -L) ==="
curl -sSIL --connect-timeout 20 --max-time 60 "$URL" | grep -iE 'HTTP/2|x-linked-size|content-length' | tail -3

echo "=== 3. 前缀校验 (带 -L) ==="
END=$((LSIZE-1))
curl -sSL --connect-timeout 20 --max-time 120 -r "0-$END" -o /tmp/b5m1a_prefix3.bin "$URL"
RSIZE=$(stat -c %s /tmp/b5m1a_prefix3.bin 2>/dev/null || echo 0)
echo "RSIZE=$RSIZE (expect $LSIZE)"
if [ "$RSIZE" = "$LSIZE" ]; then
  LH=$(sha256sum "$F" | awk '{print $1}')
  RH=$(sha256sum /tmp/b5m1a_prefix3.bin | awk '{print $1}')
  echo "LOCAL_SHA=$LH"
  echo "REMOTE_PREFIX_SHA=$RH"
  if [ "$LH" = "$RH" ]; then echo "PREFIX_MATCH=YES"; else echo "PREFIX_MATCH=NO"; fi
else
  echo "PREFIX_MATCH=SIZE_MISMATCH"
  head -c 100 /tmp/b5m1a_prefix3.bin 2>/dev/null | od -c | head -3
fi
echo "=== B5M1A_META3_DONE ==="
