#!/bin/bash
# C station: install base toolchain (align to B: git 2.43, gcc 13.3, cmake 3.28, pip)
set -e
echo "=== apt update ==="
sudo apt-get update -qq 2>&1 | tail -2
echo "=== install toolchain ==="
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  git build-essential cmake python3-pip python3-dev python3-venv \
  curl wget tar pkg-config vulkan-tools libvulkan-dev \
  tmux htop 2>&1 | tail -5
echo "=== verify versions ==="
echo "git: $(git --version 2>&1)"
echo "gcc: $(gcc --version 2>&1 | head -1)"
echo "cmake: $(cmake --version 2>&1 | head -1)"
echo "python3: $(python3 --version 2>&1)"
echo "pip3: $(pip3 --version 2>&1)"
echo "curl: $(curl --version 2>&1 | head -1)"