#!/bin/bash
# C station: rebuild llama.cpp llama-server (Vulkan) - source already synced from B
set -e
cd ~/llama.cpp
rm -rf build
cmake -B build -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release > ~/cmake_c.log 2>&1 || { tail -20 ~/cmake_c.log; exit 1; }
nproc_v=$(nproc)
cmake --build build --config Release --target llama-server -j"$nproc_v" >> ~/cmake_c.log 2>&1 || { tail -20 ~/cmake_c.log; exit 1; }
echo "=== verify ==="
ls -la build/bin/llama-server
./build/bin/llama-server --version 2>&1 | head -2
echo "BUILD_DONE"