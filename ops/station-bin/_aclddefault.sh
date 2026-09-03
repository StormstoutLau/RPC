#!/bin/bash
echo "== claude 用默认模型名(不设 ANTHROPIC_MODEL) =="
env -u ANTHROPIC_MODEL timeout 120 claude -p "Reply exactly CLAUDE-OK" < /dev/null 2>&1 | tail -8
echo "[rc=${PIPESTATUS[0]}]"