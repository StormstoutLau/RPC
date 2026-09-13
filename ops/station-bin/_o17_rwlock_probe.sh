#!/bin/bash
# O-17 layer-2 rwlock probe (2026-09-12): verify flock shared/exclusive mutex matrix.
# Independent scratch lock file - does NOT touch real agent workspaces or engines.
# Asserts (Codex RwLock semantics):
#   RR parallel : shared + shared -> both OK (readers may be concurrent)
#   RW mutex    : shared + exclusive -> exactly one OK, other HELD
#   WW mutex    : exclusive + exclusive -> exactly one OK, other HELD
set -u
L="/tmp/_o17_probe_lk"
rm -f "$L"; : > "$L"

echo "=== RR (shared+shared) ==="
( exec 9>"$L"; if flock -s -n 9; then echo "RR_P1_OK"; sleep 1; else echo "RR_P1_HELD"; fi ) &
( exec 9>"$L"; if flock -s -n 9; then echo "RR_P2_OK"; sleep 1; else echo "RR_P2_HELD"; fi ) &
wait

echo "=== RW (shared+exclusive) ==="
( exec 9>"$L"; if flock -s -n 9; then echo "RW_R_OK"; sleep 1; else echo "RW_R_HELD"; fi ) &
sleep 0.2
( exec 9>"$L"; if flock -n 9; then echo "RW_W_OK"; sleep 1; else echo "RW_W_HELD"; fi ) &
wait

echo "=== WW (exclusive+exclusive) ==="
( exec 9>"$L"; if flock -n 9; then echo "WW_W1_OK"; sleep 1; else echo "WW_W1_HELD"; fi ) &
sleep 0.2
( exec 9>"$L"; if flock -n 9; then echo "WW_W2_OK"; sleep 1; else echo "WW_W2_HELD"; fi ) &
wait
echo "PROBE_DONE"