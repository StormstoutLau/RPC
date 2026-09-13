#!/bin/bash
H="$(hostname)"
echo "=== HOST: $H — extra llama dirs ==="
echo
for d in "$HOME/llama-distributed" "$HOME/llama-env" "$HOME/App/llama-gfx1151" "$HOME/App/llama-b1292-ubuntu-rocm-gfx1151-x64.zip" "$HOME/llama.cpp-v0.2.0.tar.gz"; do
  if [ -e "$d" ]; then
    echo "-- $d --"
    ls -la "$d" 2>&1 | head -15
    if [ -d "$d" ]; then echo "du: $(du -sh "$d" 2>/dev/null | cut -f1)"; fi
    echo
  fi
done
echo "=== /data llama ==="
ls -d /data/llama* /data/*llama* 2>/dev/null || echo "no /data llama"
echo "=== done $H ==="