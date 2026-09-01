#!/bin/bash
# a4_diag_amdsmi2.sh — PYTHONPATH 方式加载 amdsmi
export LD_LIBRARY_PATH=/home/scott-lau/vllm-rocm/lib:/home/scott-lau/vllm-rocm/lib/python3.14/site-packages/_rocm_sdk_core/lib:/home/scott-lau/vllm-rocm/lib/python3.14/site-packages/_rocm_sdk_libraries/lib
export PYTHONPATH=/home/scott-lau/vllm-rocm/lib/python3.14/site-packages/_rocm_sdk_core/share/amd_smi
/home/scott-lau/vllm-rocm/bin/python3.14 <<'EOF'
import amdsmi
print("amdsmi OK:", amdsmi.__file__)
amdsmi.amdsmi_init()
h = amdsmi.amdsmi_get_processor_handles()
print("handles:", len(h))
amdsmi.amdsmi_shut_down()
print("AMD_SMI_WORKS")
EOF
echo "DIAG_AMDSMI2_DONE"
