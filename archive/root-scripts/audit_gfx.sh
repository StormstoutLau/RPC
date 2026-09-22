#!/bin/bash
H="$(hostname)"
echo "=== HOST: $H ==="
echo "--- ~/App/llama-gfx1151 top ---"
ls "$HOME/App/llama-gfx1151/" 2>&1 | head -40
echo "--- llama-server binaries found ---"
find "$HOME/App/llama-gfx1151" -maxdepth 3 -name 'llama-server*' 2>/dev/null
echo "--- version check ---"
BIN="$(find "$HOME/App/llama-gfx1151" -maxdepth 1 -name 'llama-server' 2>/dev/null | head -1)"
if [ -n "$BIN" ]; then "$BIN" --version 2>&1 | head -5; else echo "no top-level llama-server"; fi
echo "--- /llama-distributed root ---"
ls -ld /llama-distributed 2>&1
ls -la /llama-distributed 2>&1 | head -20
echo "--- /data llama ---"
ls -d /data/llama* /data/*llama* 2>/dev/null || echo "no /data llama"
echo "=== done $H ==="