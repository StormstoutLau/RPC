#!/bin/bash
# a4_env_b.sh — B站环境: pip 用户态安装 huggingface_hub + hf_transfer (绕过 PEP 668)
# 用法: 经主控站 scp 到 /tmp 后 ssh 执行: bash /tmp/a4_env_b.sh
set -x
pip3 install --user --break-system-packages -q -i https://pypi.tuna.tsinghua.edu.cn/simple huggingface_hub hf_transfer 2>&1 | tail -2
python3 -m pip list --user 2>/dev/null | grep -iE 'huggingface|hf-'
ls -la ~/.local/bin/hf
echo "A4_ENV_B_DONE"
