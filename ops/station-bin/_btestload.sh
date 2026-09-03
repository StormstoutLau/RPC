#!/bin/bash
echo "== 测 infer-load gpt-oss-20b 走 unsloth 后端 (轻量 11G, 不破坏 gpt-oss-120b) =="
timeout 200 infer-load gpt-oss-20b 2>&1 | head -20
echo "=[rc=${PIPESTATUS[0]}]=>"