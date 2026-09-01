#!/bin/bash
# a4_diag_platform.sh — vLLM platform 探测诊断
export LD_LIBRARY_PATH=/home/scott-lau/vllm-rocm/lib:/home/scott-lau/vllm-rocm/lib/python3.14/site-packages/_rocm_sdk_core/lib:/home/scott-lau/vllm-rocm/lib/python3.14/site-packages/_rocm_sdk_libraries/lib
/home/scott-lau/vllm-rocm/bin/python3.14 <<'EOF'
import torch
print("torch.hip:", torch.version.hip, "avail:", torch.cuda.is_available())
from vllm.platforms import current_platform
print("current_platform:", current_platform)
print("device_type:", current_platform.device_type)
try:
    print("platform_name:", current_platform.device_name())
except Exception as e:
    print("device_name ERR:", e)
from vllm import platform
EOF
echo "DIAG_PLATFORM_DONE"
