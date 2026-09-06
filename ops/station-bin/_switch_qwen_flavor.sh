#!/bin/bash
# _switch_qwen_flavor.sh - L1 instance-layer flavor switch for qwen3.8-27b-mtp.
# Runs ON the B station (R14-style, pushed via scp + ssh by _switch_qwen_flavor.ps1).
# Given a flavor name + base64 of the flavor preset env, it atomically swaps the CTX/
# template in /etc/llama-instances/qwen3.8-27b-mtp.env and reloads the systemd unit,
# with the memory-release + mem-gate + /props verification guards.
#
# Usage (run on B):  bash _switch_qwen_flavor.sh <flavor> <preset_b64>
#   flavor: nothink | think | long
#   preset_b64: base64 of ops/station-bin/qwen-flavor-<flavor>.env
#
# Hard gates applied (project memory):
#   - backup active conf BEFORE overwrite (hard rule)
#   - wait-gtt-release after stopping old engine (never fixed sleep)
#   - load-mem-gate BEFORE starting new engine
#   - verify runtime n_ctx via /props (NOT /v1/models n_ctx_train - O-21 lesson)
#
# NOTE: this is a MANUAL tool - user triggers it in an idle window. It does NOT
# auto-run and it DOES interrupt the running instance for the reload duration.
set -uo pipefail

FLAVOR="${1:-}"; PRESET_B64="${2:-}"
CONF=/etc/llama-instances/qwen3.8-27b-mtp.env
UNIT="llama-server@qwen3.8-27b-mtp"
PORT=18080

# ---- expected runtime n_ctx per flavor ----
case "$FLAVOR" in
  nothink) EXPECT_NCTX=8192;   MEM_GB=32 ;;
  think)   EXPECT_NCTX=32768;  MEM_GB=36 ;;
  long)    EXPECT_NCTX=262144; MEM_GB=48 ;;
  *) echo "ERR: bad flavor '$FLAVOR' (use nothink|think|long)"; exit 2 ;;
esac

[ -n "$PRESET_B64" ] || { echo "ERR: missing preset_b64"; exit 2; }
[ -f "$CONF" ] || { echo "ERR: no active conf $CONF"; exit 1; }

echo "[switch] flavor=$FLAVOR expect_n_ctx=$EXPECT_NCTX mem_gb=$MEM_GB"

# ---- [1] backup active conf (hard rule: destructive op backup first) ----
URL=$(echo "$FLAVOR" | tr '[:lower:]' '[:upper:]')
BAK="/etc/llama-instances/qwen3.8-27b-mtp.env.bak.flavor"
[ -f "$BAK" ] || sudo cp "$CONF" "$BAK"
echo "backup: $BAK"
echo "backup CTX: $(grep -E '^CTX=' "$BAK")"

# ---- [2] deploy preset (decode base64 -> temp -> sudo overwrite active conf) ----
TMP=$(mktemp)
echo "$PRESET_B64" | base64 -d > "$TMP"
grep -q '^CTX=' "$TMP" || { echo "ERR: preset has no CTX= (decode fail?)"; rm -f "$TMP"; exit 2; }
sudo cp "$TMP" "$CONF"
rm -f "$TMP"
echo "deployed CTX: $(grep -E '^CTX=' "$CONF")"

# ---- [3] stop old engine (releases GTT) ----
echo "[mem] stop $UNIT ..."
sudo systemctl stop "$UNIT" 2>/dev/null || true

# ---- [4] wait-gtt-release (async GTT reclaim; 30-90s typical) ----
echo "[mem] wait-gtt-release ..."
if bash "$(dirname "$0")/wait-gtt-release" 2>/dev/null; then
  : # local copy present
elif [ -f /home/scott-lau/wait-gtt-release ]; then
  bash /home/scott-lau/wait-gtt-release || { echo "ERR: GTT not released"; exit 3; }
else
  # inline fallback: poll MemAvailable until >=100G
  for i in $(seq 1 36); do
    AV=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
    if [ "$AV" -ge 102400 ]; then echo "[gtt-wait][inline] OK ${AV}G"; break; fi
    sleep 5
  done
  [ "$AV" -ge 102400 ] || { echo "ERR: GTT inline timeout AV=${AV}G"; exit 3; }
fi

# ---- [5] load-mem-gate (MemAvailable >= model GB + 12G buffer) ----
echo "[mem] load-mem-gate ${MEM_GB}G ..."
if bash "$(dirname "$0")/load-mem-gate" "$MEM_GB" 2>/dev/null; then
  :
elif [ -f /home/scott-lau/load-mem-gate ]; then
  bash /home/scott-lau/load-mem-gate "$MEM_GB" || { echo "ERR: mem gate reject"; exit 4; }
else
  AV=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  [ $((AV - MEM_GB*1024)) -ge 12288 ] || { echo "ERR: no gate, AV=${AV}G < ${MEM_GB}+12G"; exit 4; }
  echo "[mem-gate][inline] OK ${AV}G >= ${MEM_GB}+12G"
fi

# ---- [6] start new engine ----
echo "[start] $UNIT ..."
sudo systemctl start "$UNIT"

# ---- [7] health poll (port 18080) ----
OK=0
for i in $(seq 1 120); do
  if curl -sf --max-time 2 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then OK=1; break; fi
  sleep 3
done
[ "$OK" = 1 ] || { echo "ERR: health 6min timeout port=$PORT"; journalctl -u "$UNIT" -n 20 --no-pager 2>/dev/null; exit 5; }
echo "[start] READY :$PORT"

# ---- [8] verify runtime n_ctx via /props (O-21: /v1/models n_ctx_train is misleading) ----
NC=$(curl -s -m4 "http://127.0.0.1:$PORT/props" 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin).get("default_generation_settings",{}).get("n_ctx"))' 2>/dev/null)
echo "runtime n_ctx = $NC (expect $EXPECT_NCTX)"
if [ "$NC" = "$EXPECT_NCTX" ]; then echo "VERIFY_OK n_ctx=$NC"; echo "--SWITCH_DONE flavor=$FLAVOR--"; exit 0; fi
echo "VERIFY_FAIL n_ctx=$NC expect=$EXPECT_NCTX"; exit 6