#!/bin/bash
echo "== claude 复测 (确认稳定) =="
OUT=$(timeout 150 claude -p "Reply with exactly the single word CLAUDE-STABLE-OK" < /dev/null 2>&1)
RC=$?
echo "rc=$RC"
echo "out=$OUT" | head -5