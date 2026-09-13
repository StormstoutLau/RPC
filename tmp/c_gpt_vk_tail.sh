#!/bin/bash
# C 站: 从日志抓最近完整 timing (128 tok 那次)
set +e
echo "=== 最近 8 行 log ==="
tail -8 /tmp/c_gpt_vk.log
echo ""
echo "=== 所有含 eval/prompt 的 timing 行 ==="
grep -E 'prompt eval|eval time' /tmp/c_gpt_vk.log | tail -4