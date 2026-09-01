#!/bin/bash
# purge_old_kernels.sh — B 站删旧内核 (保留运行中 + 最新可用回退)
echo "运行内核: $(uname -r)"
echo "候选删除: 6.17.0-23 不动(运行中), 删 7.0.0-30 系 + 6.17.0-29 headers"
sudo apt-get purge -y linux-image-7.0.0-30-generic linux-modules-7.0.0-30-generic linux-modules-extra-7.0.0-30-generic linux-headers-7.0.0-30-generic 2>&1 | tail -2
sudo apt-get purge -y linux-headers-6.17.0-29-generic 2>&1 | tail -1
sudo apt-get autoremove -y 2>&1 | tail -1
echo "=== 清理后 ==="
df -h / | tail -1
dpkg -l | grep -E "^ii.*linux-(image|modules)-[0-9]" | awk "{print \$2}"