#!/bin/bash
# Incremental rebuild master Vulkan llama-engine (qwen35 + draft-mtp) (2026-09-06)
set -u
SRC=/home/scott-lau/llama.cpp
LOG=/tmp/qwen27_build.log
echo "=== start rebuild $(date '+%F %T') ===" > "$LOG"
cmake --build "$SRC/build" -j32 >> "$LOG" 2>&1
RC=$?
echo "=== BUILD_RC=$RC ===" >> "$LOG"
echo "=== artifact info ===" >> "$LOG"
stat -c '%s bytes %y' "$SRC/build/bin/llama-server" >> "$LOG" 2>&1
"$SRC/build/bin/llama-server" --version >> "$LOG" 2>&1
echo "=== qwen35/draft-mtp in new binary ===" >> "$LOG"
strings "$SRC/build/bin/llama-server" | grep -ac 'qwen35' >> "$LOG"
strings "$SRC/build/bin/llama-server" | grep -ac 'draft-mtp' >> "$LOG"
echo "=== DONE ===" >> "$LOG"