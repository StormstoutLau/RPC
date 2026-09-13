#!/bin/bash
echo "== RAM =="
free -g | head -2
echo "== GPU/VRAM =="
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader
elif command -v rocm-smi >/dev/null 2>&1; then
  echo "-- rocm product --"
  rocm-smi --showproductname 2>/dev/null | grep -iE 'card|gpu' | head -2
  echo "-- rocm memoverview --"
  rocm-smi --showmeminfo vram 2>/dev/null | head -6
fi