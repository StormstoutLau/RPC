#!/bin/bash
# C station: rebuild llama-server with GGML_RPC=ON (align A/B), Vulkan + RPC backends
set -e
cd ~/llama.cpp
cmake -B build -DGGML_VULKAN=ON -DGGML_RPC=ON -DCMAKE_BUILD_TYPE=Release > ~/cmake_rpc_c.log 2>&1 || { tail -15 ~/cmake_rpc_c.log; exit 1; }
nproc_v=$(nproc)
cmake --build build --config Release --target llama-server -j"$nproc_v" >> ~/cmake_rpc_c.log 2>&1 || { tail -15 ~/cmake_rpc_c.log; exit 1; }
echo "=== verify ==="
./build/bin/llama-server --version 2>&1 | head -2
./build/bin/llama-server --list-devices 2>&1 | head -4
echo "RPC check: $(./build/bin/llama-server --help 2>&1 | grep -c -- '--rpc')"
echo "BUILD_RPC_DONE"