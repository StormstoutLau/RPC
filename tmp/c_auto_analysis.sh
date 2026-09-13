#!/bin/bash
# C 站: 分析 Auto 档下 gpt-oss 可行性 + 内存账目
set +e
echo "=== 1. 内存账目 (Auto=64G carveout) ==="
free -g | head -2
sudo -n dmesg 2>/dev/null | grep -E 'VRAM|GTT|carveout' | head -5
echo "=== 2. GTT 总与模型需求 ==="
cat /sys/class/drm/card1/device/mem_info_gtt_total 2>/dev/null | xargs echo 'gtt_total='
echo "gpt-oss-120b MXFP4 = 60G 权重 + ~4G KV/c4096 => ~64G 需求"
echo "=> Auto 档承载能力: 系统可用 ~62G (含 gpt-oss 就死)"
echo "=== 3. 系统内存被 carveout 扣掉多少 ==="
echo "物理 124G - 系统 62G = carveout 消耗 ~62G (64G VRAM carveout excerpt)"
echo "=== 4. 检查 BIOS 档位线索 (dmidecode 无, 需查 iGPU 档位表不可读) ==="
echo "结论: 1G 档 HIP 死 / Auto 档内存不足 -> 需中间档(8G/16G/32G?) 需用户在 BIOS 测试"
echo "=== 5. 当前 gpt-oss 尝试会让系统 OOM 吗 (先 dry) ==="
echo "load-gate 60 已 ABORT (used 3G + 60G + 12G > 62G) -> 禁止加载, 安全"