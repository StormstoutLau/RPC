#!/bin/bash
echo "== 新 infer-load 加载 gpt-oss-120b (unsloth 默认后端) =="
infer-load gpt-oss-120b 2>&1 | head -25
echo "[rc=${PIPESTATUS[0]}]"