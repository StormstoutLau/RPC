#!/bin/bash
# a4_diag_model.sh — 诊断 get_model_path 对 /tmp/model-alias 的判定
set -uo pipefail
PY=/home/scott-lau/vllm-rocm/bin/python3.14
SITE=/home/scott-lau/vllm-rocm/lib/python3.14/site-packages
export LD_LIBRARY_PATH="/home/scott-lau/vllm-rocm/lib:${SITE}/_rocm_sdk_core/lib:${SITE}/_rocm_sdk_libraries/lib"
"$PY" <<'EOF'
import os, pathlib
p = "/tmp/model-alias"
print("exists:", os.path.exists(p))
print("islink:", os.path.islink(p))
print("isdir:", os.path.isdir(p))
print("realpath:", os.path.realpath(p))
print("target exists:", os.path.exists(os.path.realpath(p)))
cfg = os.path.join(p, "config.json")
print("config.json exists:", os.path.exists(cfg))
# 模拟 vLLM get_model_path 的判定
import huggingface_hub
print("HF_HUB_OFFLINE const:", huggingface_hub.constants.HF_HUB_OFFLINE)
print("get_model_path branch:", "local" if os.path.exists(p) else "snapshot_download")
EOF
echo "---GREP_ARGS---"
grep -o "model='[^']*'" /tmp/a4_vllm_launch.log | head -3
grep -o "model=[^ ,]*" /tmp/a4_vllm_launch.log | sort -u | head -5
echo "DIAG_MODEL_DONE"
