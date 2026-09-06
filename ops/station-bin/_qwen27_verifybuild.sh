#!/bin/bash
BIN=/home/scott-lau/llama.cpp/build/bin
echo "=== bin contents ==="
ls -la "$BIN" | grep -iE 'llama-server|\.so|llama$' | head -30
echo "=== qwen35 in libllama / libggml ==="
for lib in "$BIN"/libllama.so "$BIN"/libggml.so "$BIN"/libllama-server-impl.so; do
  [ -f "$lib" ] && echo "-- $lib --" && strings "$lib" | grep -ac 'qwen35'
done
echo "=== draft-mtp in libs ==="
for lib in "$BIN"/libllama.so "$BIN"/libggml.so "$BIN"/libllama-server-impl.so; do
  [ -f "$lib" ] && echo "-- $lib --" && strings "$lib" | grep -ac 'draft-mtp'
done
echo "=== run new engine --version ==="
"$BIN/llama-server" --version 2>&1 | head -3