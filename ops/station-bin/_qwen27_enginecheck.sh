#!/bin/bash
echo "=== master repo head ==="
git -C /home/scott-lau/llama.cpp log --oneline -1 2>/dev/null
echo "=== master llama-arch qwen35? ==="
grep -n "qwen35\|QWEN35" /home/scott-lau/llama.cpp/src/llama-arch.cpp 2>/dev/null | head
echo "=== master build/bin/llama-server version ==="
/home/scott-lau/llama.cpp/build/bin/llama-server --version 2>&1 | head -2
echo "=== master build qwen35 + draft-mtp strings ==="
strings /home/scott-lau/llama.cpp/build/bin/llama-server 2>/dev/null | grep -ai 'qwen35\|QWEN35' | head -4
strings /home/scott-lau/llama.cpp/build/bin/llama-server 2>/dev/null | grep -ai 'draft-mtp\|spec-type\|draft-mtp-simple' | head -6
echo "=== all llama-server binaries ==="
find /home/scott-lau /usr/local/bin -maxdepth 6 -name 'llama-server' -type f -executable 2>/dev/null | while read -r p; do
  v=$("$p" --version 2>&1 | grep -o 'build [0-9]*' | head -1)
  q=$(strings "$p" 2>/dev/null | grep -ac 'qwen35')
  m=$(strings "$p" 2>/dev/null | grep -ac 'draft-mtp')
  echo "$v | qwen35=$q draft-mtp=$m | $p"
done