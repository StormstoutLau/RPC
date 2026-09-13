#!/bin/bash
# 三站 ROCm 工具链现状核对 (ds4 部署可行性关键前提)
set +e
echo "############ A 站 (天钡 NEX) ############"
ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=no scott-lau@192.168.1.33 "
  echo '-- ROCm 目录 --'; ls -d /opt/rocm* 2>/dev/null | head -3
  echo '-- hipcc --'; which hipcc 2>/dev/null || echo '(无 hipcc)'
  echo '-- hipblas/rocblas/rocwmma dev 包 --'; dpkg -l 2>/dev/null | grep -cE 'hipblas|rocblas|rocwmma|hipcub'
  echo '-- gttsize/ttm --'; grep -oE 'amdgpu.gttsize=[0-9]*|ttm.pages_limit=[0-9]*|amd_iommu=[a-z]*' /proc/cmdline
  echo '-- UMA vram_total --'; cat /sys/class/drm/card1/device/mem_info_vram_total 2>/dev/null | xargs echo 'vram_total='
  echo '-- HIP 设备 --'; ~/.unsloth/llama.cpp/build/bin/llama-server --list-devices 2>&1 | head -2
"
echo ""
echo "############ B 站 (AZW GTR Pro) ############"
ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=no scott-lau@scott-lau-GTR-Pro.local "
  echo '-- ROCm 目录 --'; ls -d /opt/rocm* 2>/dev/null | head -3 || echo '(无系统 ROCm)'
  echo '-- hipcc --'; which hipcc 2>/dev/null || echo '(无 hipcc)'
  echo '-- hipblas/rocblas/rocwmma dev 包 --'; dpkg -l 2>/dev/null | grep -cE 'hipblas|rocblas|rocwmma|hipcub'
  echo '-- gttsize/ttm --'; grep -oE 'amdgpu.gttsize=[0-9]*|ttm.pages_limit=[0-9]*|amd_iommu=[a-z]*' /proc/cmdline
  echo '-- HIP 设备 --'; ~/.unsloth/llama.cpp/build/bin/llama-server --list-devices 2>&1 | head -2
"
echo ""
echo "############ C 站 (影核 R1 Plus) ############"
ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=no scott-lau@192.168.1.37 "
  echo '-- ROCm 目录 --'; ls -d /opt/rocm* 2>/dev/null | head -3 || echo '(无系统 ROCm — 已按指令移除)'
  echo '-- hipcc --'; which hipcc 2>/dev/null || echo '(无 hipcc — 需重装才可编译 ds4)'
  echo '-- hipblas/rocblas/rocwmma dev 包 --'; dpkg -l 2>/dev/null | grep -cE 'hipblas|rocblas|rocwmma|hipcub'
  echo '-- gttsize/ttm --'; grep -oE 'amdgpu.gttsize=[0-9]*|ttm.pages_limit=[0-9]*|amd_iommu=[a-z]*' /proc/cmdline
  echo '-- UMA vram_total --'; cat /sys/class/drm/card1/device/mem_info_vram_total 2>/dev/null | xargs echo 'vram_total='
  echo '-- HIP 设备 --'; ~/.unsloth/llama.cpp/build/bin/llama-server --list-devices 2>&1 | head -2
"
echo ""
echo "############ 对比总结 ############"
echo "ds4 ROCm 构建需要: hipcc/hipblas/hipblaslt/rocblas/rocwmma/hipcub dev 包"