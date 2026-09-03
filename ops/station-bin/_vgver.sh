#!/bin/bash
echo "== llama-server --version =="
/opt/llama.cpp/llama-server --version 2>&1 | head -3
echo "== ggml lib 版本 =="
ls -l /opt/llama.cpp/libggml-vulkan.so* 2>/dev/null
ls -l /opt/llama.cpp/libggml*.so* 2>/dev/null | head
echo "== 目录是否有 git / 版本戳 =="
cd /opt/llama.cpp 2>/dev/null && { git describe --tags 2>/dev/null; git rev-parse HEAD 2>/dev/null; git log -1 --format='%h %ci %s' 2>/dev/null; } || echo "no-git at /opt/llama.cpp"
echo "== ggml 头版本 =="
grep -m2 "GGML_VERSION\|#define GGML_VERSION" /opt/llama.cpp/ggml/include/ggml.h 2>/dev/null | head
echo "== llama.cpp 版本声明 =="
grep -rm1 "LLAMA_VERSION\|llama.cpp version" /opt/llama.cpp/*.h /opt/llama.cpp/ggml/include/llama.h 2>/dev/null | head
echo "== 编译时间/源 =="
ls -la /opt/llama.cpp/CMakeCache.txt 2>/dev/null && grep -m3 "CMAKE_BUILD_TYPE\|GGML_VULKAN\|AMDGPU\|GGML_CUDA\|GGML_NATIVE" /opt/llama.cpp/CMakeCache.txt 2>/dev/null | head