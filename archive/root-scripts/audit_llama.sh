#!/bin/bash
H="$(hostname)"
echo "=== HOST: $H ==="
echo
echo "===== [A] MANIFEST existence + line counts ====="
for d in /opt/llama.cpp-9859 /opt/llama.cpp-master-d2e206c4 /opt/llama.cpp-v0.2.0 "$HOME/llama.cpp-vulkan-b10715" "$HOME/llama.cpp" "$HOME/.unsloth/llama.cpp"; do
  if [ -f "$d/MANIFEST" ]; then
    n=$(wc -l < "$d/MANIFEST")
    echo "$d : EXISTS ($n lines)"
  else
    echo "$d : NONE"
  fi
done
echo "-- /opt/llama.cpp (symlink) real MANIFEST --"
ls -ld /opt/llama.cpp 2>&1
REAL=$(readlink -f /opt/llama.cpp 2>&1)
echo "readlink -f /opt/llama.cpp -> $REAL"
if [ -f "$REAL/MANIFEST" ]; then n=$(wc -l < "$REAL/MANIFEST"); echo "$REAL/MANIFEST : EXISTS ($n lines)"; else echo "$REAL/MANIFEST : NONE"; fi

echo
echo "===== [C] MANIFEST md5 spot-check on /opt/llama.cpp-master-d2e206c4 ====="
for d in /opt/llama.cpp-master-d2e206c4 /opt/llama.cpp-v0.2.0 /opt/llama.cpp-9859; do
  if [ -f "$d/MANIFEST" ]; then
    echo "-- $d/MANIFEST (first 6 lines) --"
    head -6 "$d/MANIFEST"
    echo "--- md5sum -c (sample, incl ggml-rpc-server) ---"
    grep -E 'ggml-rpc-server|llama-server|\.so$' "$d/MANIFEST" | head -4 > /tmp/manif_sample_$$.txt
    (cd "$d" && md5sum -c /tmp/manif_sample_$$.txt 2>&1 | head -8)
    rm -f /tmp/manif_sample_$$.txt
    echo
  else
    echo "-- $d/MANIFEST : NONE --"
  fi
done
echo
echo "===== [B] ~/llama.cpp git HEAD ====="
( cd "$HOME/llama.cpp" && git rev-parse HEAD 2>&1)
echo
echo "===== [E] du -sh sizes ====="
for d in /opt/llama.cpp-9859 /opt/llama.cpp-master-d2e206c4 /opt/llama.cpp-v0.2.0 "$HOME/llama.cpp" "$HOME/llama.cpp-vulkan-b10715" "$HOME/.unsloth/llama.cpp"; do
  if [ -e "$d" ]; then s=$(du -sh "$d" 2>/dev/null | cut -f1); echo "$d : $s"; else echo "$d : ABSENT"; fi
done
echo
echo "===== [E] .git presence in ~/.unsloth/llama.cpp ====="
if [ -d "$HOME/.unsloth/llama.cpp/.git" ]; then echo ".unsloth/llama.cpp : HAS .git"; else echo ".unsloth/llama.cpp : NO .git (top-level)"; fi
if [ -d "$HOME/llama.cpp-vulkan-b10715/.git" ]; then echo "vulkan-b10715 : HAS .git"; else echo "vulkan-b10715 : NO .git"; fi
echo
echo "===== [D] running llama processes ====="
ps -eo pid,args 2>/dev/null | grep -Ei 'ggml-rpc-server|llama-server' | grep -v grep
echo "--- exe path resolution of rpc-server pids ---"
for pid in $(pgrep -f ggml-rpc-server 2>/dev/null); do
  echo "pid $pid exe: $(readlink -f /proc/$pid/exe 2>&1)"
  echo "pid $pid cwd: $(readlink /proc/$pid/cwd 2>&1)"
  echo "pid $pid cmdline: $(tr '\0' ' ' < /proc/$pid/cmdline 2>&1)"
done
echo
echo "===== [E] exhaustive llama dir search ====="
ls -d /opt/llama* /opt/*llama* "$HOME"/llama* "$HOME"/App/llama* "$HOME"/.unsloth/llama* /data/*llama* 2>/dev/null
echo
echo "===== [D] /opt/llama.cpp symlink llama-server --version ====="
/opt/llama.cpp/llama-server --version 2>&1 | head -2
echo "=== done $H ==="