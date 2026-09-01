#!/bin/bash
# a4_diag_torch.sh — 诊断 torch HIP 可见性
export LD_LIBRARY_PATH=/home/scott-lau/vllm-rocm/lib:/home/scott-lau/vllm-rocm/lib/python3.14/site-packages/_rocm_sdk_core/lib:/home/scott-lau/vllm-rocm/lib/python3.14/site-packages/_rocm_sdk_libraries/lib
/home/scott-lau/vllm-rocm/bin/python3.14 <<'EOF'
import torch
print("torch:", torch.__version__)
print("is_available:", torch.cuda.is_available())
print("device_count:", torch.cuda.device_count())
if torch.cuda.is_available():
    print("device_name:", torch.cuda.get_device_name(0))
    print("hip_version:", torch.version.hip)
EOF
echo "DIAG_TORCH_DONE"
