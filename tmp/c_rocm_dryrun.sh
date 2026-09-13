#!/bin/bash
# C 站: amdgpu-install --dryrun --uninstall 预览
set +e
timeout 120 sudo -n amdgpu-install --dryrun --uninstall 2>&1 | tail -30
echo "dryrun_exit=$?"