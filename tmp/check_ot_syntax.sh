#!/bin/bash
echo "== llama-server -ot 帮助 =="
/opt/llama.cpp/llama-server --help 2>&1 | grep -A2 -iE "override-tensor|-ot|tensor-split|-sm |split-mode" | head -20
echo
echo "== RPC 相关 =="
/opt/llama.cpp/llama-server --help 2>&1 | grep -iE "rpc|device" | head -8