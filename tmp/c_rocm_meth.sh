#!/bin/bash
# C 站: 查看 amdgpu-install 卸载帮助与官方卸载脚本
set +e
echo "=== 1. amdgpu-uninstall 是否存在 ==="
ls -la /usr/bin/amdgpu-uninstall /usr/sbin/amdgpu-uninstall 2>/dev/null || echo '(无独立 uninstall 脚本)'
echo "=== 2. amdgpu-install 完整帮助 (uninstall 相关行) ==="
amdgpu-install --help 2>&1 | grep -B2 -A6 -i uninstall | head -30
echo "=== 3. dpkg -L amdgpu-install 里的卸载脚本 ==="
dpkg -L amdgpu-install 2>/dev/null | grep -iE 'uninstall|\.sh$' | head -10
echo "=== 4. 官方文档卸载命令 (grep amdgpu-uninstall) ==="
grep -rle 'amdgpu-uninstall' /usr/share/amdgpu-install/ 2>/dev/null | head -3