#!/bin/bash
# _slot_gate.sh - probe llama-server /slots occupancy (O-25 P1 slot gate). Usage: bash _slot_gate.sh <port>
# NOTE: ASCII only (no non-ASCII comment) - avoids BOM/concat pitfalls inherited across scp/ssh.
set -uo pipefail
PORT="${1:-}"
[ -n "$PORT" ] || { echo "ERR_SLOT_PORT_NA"; exit 20; }
BODY=$(curl -s -m4 "http://127.0.0.1:$PORT/slots" 2>/dev/null)
echo "$BODY" | grep -q '"id"' || { echo "SLOT_NA (no /slots; non-llama or old engine)"; exit 0; }
python3 - "$BODY" <<'PY'
import sys, json
try:
    slots = json.loads(sys.argv[1])
except Exception:
    print("SLOT_NA (slots parse failed)")
    sys.exit(0)
busy  = sum(1 for s in slots if s.get('is_processing') or s.get('state')=='processing' or (s.get('n_past',0)>0))
queued= sum(1 for s in slots if s.get('queue',0))
print("SLOT_TOTAL=%d SLOT_BUSY=%d SLOT_QUEUE=%d" % (len(slots), busy, queued))
PY