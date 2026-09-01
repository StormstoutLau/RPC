#!/bin/bash
# clean_b_crash.sh — 清理 crash 转储 + 查 usb4-network 服务
echo "=== [1] crash 文件与磁盘 ==="
df -h / | tail -1
echo "清理 5.8G llama-server crash 转储 (03:11, infer-load 停实例产生, 非新故障):"
sudo rm -f /var/crash/_opt_llama.cpp-master-d2e206c4_llama-server.1000.crash
ls -lt /var/crash/ | head -3
df -h / | tail -1
echo
echo "=== [2] usb4-network.service 状态与定义 ==="
systemctl status usb4-network.service --no-pager 2>&1 | head -8
systemctl cat usb4-network.service 2>/dev/null | head -15