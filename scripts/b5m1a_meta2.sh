#!/bin/bash
# b5m1a_meta2.sh — 修复诊断: ①tree json 全量结构 ②URL 响应头 ③带 -L 的前缀校验
set -uo pipefail
URL="https://hf-mirror.com/unsloth/GLM-5.3-Flash-GGUF/resolve/main/GLM-5.3-Flash-UD-IQ4_XS-00001-of-00005.gguf"
F="$HOME/.lmstudio/models/unsloth/GLM-5.3-Flash-GGUF/GLM-5.3-Flash-UD-IQ4_XS-00001-of-00005.gguf"
LSIZE=$(stat -c %s "$F" 2>/dev/null || echo 0)

echo "=== 1. tree json 全量 (paths only) ==="
python3 - <<'EOF'
import json
d = json.load(open('/tmp/b5m1a_tree.json'))
print("type:", type(d).__name__, "count:", len(d) if isinstance(d, list) else 'n/a')
for f in d if isinstance(d, list) else []:
    if isinstance(f, dict):
        print(f.get('path', '?'), f.get('size', '?'))
EOF

echo "=== 2. URL 响应头 (无 -L, 看重定向) ==="
curl -sSI --connect-timeout 20 --max-time 30 "$URL" | head -15

echo "=== 3. Content-Length (跟随重定向 HEAD) ==="
curl -sSIL --connect-timeout 20 --max-time 60 "$URL" | grep -iE 'HTTP/|content-length|x-linked-size|x-linked-etag' | head -10

echo "=== 4. 前缀校验 (带 -L) ==="
END=$((LSIZE-1))
curl -sSL --connect-timeout 20 --max-time 120 -r "0-$END" -o /tmp/b5m1a_prefix2.bin "$URL"
RSIZE=$(stat -c %s /tmp/b5m1a_prefix2.bin 2>/dev/null || echo 0)
echo "RSIZE=$RSIZE (expect $LSIZE)"
if [ "$RSIZE" = "$LSIZE" ]; then
  LH=$(sha256sum "$F" | awk '{print $1}')
  RH=$(sha256sum /tmp/b5m1a_prefix2.bin | awk '{print $1}')
  echo "LOCAL_SHA=$LH"
  echo "REMOTE_PREFIX_SHA=$RH"
  if [ "$LH" = "$RH" ]; then echo "PREFIX_MATCH=YES"; else echo "PREFIX_MATCH=NO"; fi
else
  echo "PREFIX_MATCH=SIZE_MISMATCH"
  head -c 200 /tmp/b5m1a_prefix2.bin 2>/dev/null | od -c | head -5
fi
echo "=== B5M1A_META2_DONE ==="
