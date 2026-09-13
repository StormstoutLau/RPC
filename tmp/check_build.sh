#!/bin/bash
echo "=== llama.cpp dir ==="
ls ~/llama.cpp 2>/dev/null | head -8 || echo "NO llama.cpp dir"
echo "=== build processes ==="
pgrep -af 'cmake|git|make' 2>/dev/null | head -6 || echo "no build procs"
echo "=== build dir ==="
ls ~/llama.cpp/build/bin/llama-server 2>/dev/null && echo BUILD_OK || echo "not built yet"