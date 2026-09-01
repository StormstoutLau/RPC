#!/bin/bash
# a4_diag_amdsmi.sh — amdsmi 探测诊断
export LD_LIBRARY_PATH=/home/scott-lau/vllm-rocm/lib:/home/scott-lau/vllm-rocm/lib/python3.14/site-packages/_rocm_sdk_core/lib:/home/scott-lau/vllm-rocm/lib/python3.14/site-packages/_rocm_sdk_libraries/lib
/home/scott-lau/vllm-rocm/bin/python3.14 <<'EOF'
try:
    import amdsmi
    print("amdsmi imported OK:", amdsmi.__file__)
    try:
        amdsmi.amdsmi_init()
        handles = amdsmi.amdsmi_get_processor_handles()
        print("processor_handles:", len(handles))
    except Exception as e:
        print("amdsmi_init/handles FAILED:", repr(e))
except Exception as e:
    print("import amdsmi FAILED:", repr(e))
EOF
echo "DIAG_AMDSMI_DONE"
