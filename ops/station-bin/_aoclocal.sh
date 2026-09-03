#!/bin/bash
echo "=== A cluster-local 完整块 ==="
awk '/"cluster-local"/{f=1} f{print} f&&/^    },/{exit}' /home/scott-lau/.config/opencode/opencode.jsonc