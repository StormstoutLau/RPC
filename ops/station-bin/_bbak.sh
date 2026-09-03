#!/bin/bash
set -e
echo "== 备份 B 站加载管理脚本 =="
sudo cp /usr/local/bin/infer-load /usr/local/bin/infer-load.bak-unsloth-20260904
sudo cp /usr/local/bin/infer-unload /usr/local/bin/infer-unload.bak-unsloth-20260904
sudo cp /usr/local/bin/infer-list /usr/local/bin/infer-list.bak-unsloth-20260904
ls -la /usr/local/bin/*.bak-unsloth-* 2>/dev/null
echo "backup done"