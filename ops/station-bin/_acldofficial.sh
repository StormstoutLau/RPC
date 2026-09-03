#!/bin/bash
echo "== claude 官方名 claude-sonnet-4-5 (指向8087) =="
ANTHROPIC_BASE_URL=http://127.0.0.1:8087 \
ANTHROPIC_AUTH_TOKEN=dummy \
ANTHROPIC_DEFAULT_SONNET_MODEL=claude-sonnet-4-5 \
timeout 120 claude -p "Reply exactly CLAUDE-OK" < /dev/null 2>&1 | tail -8
echo "[rc=${PIPESTATUS[0]}]"