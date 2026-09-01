#!/bin/bash
# 审计: 实测 GLM master 加载 (将 4.3 的"预期失败"推断升级为硬事实)
set -e
CONF=/etc/llama-instances/glm-5.3-flash.env
echo "=== conf ==="
cat $CONF 2>/dev/null | grep -E "MODEL_PATH|PORT|RPC_TARGET" || echo "no conf"
MODEL=$(grep '^MODEL_PATH=' $CONF 2>/dev/null | cut -d= -f2)
echo "GLM model: $MODEL"
[ -f "$MODEL" ] && echo "model exists ($(du -h "$MODEL" | cut -f1))" || echo "MODEL MISSING"

# 用 master llama-cli 直接加载验证架构 (不启 server, 捕获架构报错)
echo "=== master llama-cli 加载 GLM 架构测试 ==="
timeout 60 /opt/llama.cpp/llama-cli -m "$MODEL" -p "hello" -n 4 --no-display-prompt 2>&1 | tail -8
echo "EXIT=$?"