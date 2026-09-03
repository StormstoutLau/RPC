#!/bin/bash
echo "== B claude 现状 (LiteLLM 4000, nemotron) =="
timeout 60 claude -p "Reply with exactly B-CLAUDE-CUR" < /dev/null 2>&1 | tail -6
echo "[rc=${PIPESTATUS[0]}]"