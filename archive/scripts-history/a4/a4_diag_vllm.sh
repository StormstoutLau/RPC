#!/bin/bash
# a4_diag_vllm.sh — 复现 vLLM device inference 失败 (带 DEBUG)
export LD_LIBRARY_PATH=/home/scott-lau/vllm-rocm/lib:/home/scott-lau/vllm-rocm/lib/python3.14/site-packages/_rocm_sdk_core/lib:/home/scott-lau/vllm-rocm/lib/python3.14/site-packages/_rocm_sdk_libraries/lib
export VLLM_LOGGING_LEVEL=DEBUG
/home/scott-lau/vllm-rocm/bin/python3.14 -m vllm.entrypoints.openai.api_server --help 2>&1 | tail -30
echo "DIAG_VLLM_DONE"
