#!/bin/bash
LIB=/home/scott-lau/llama.cpp/build/bin/libllama.so
echo "=== spec-draft flags ==="
strings "$LIB" | grep -ai 'spec-draft\|draft-mtp\|draft-model\|--draft' | sort -u | head -20
echo "=== mtp tokens ==="
strings "$LIB" | grep -ai 'mtp' | sort -u | head -20