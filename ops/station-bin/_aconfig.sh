#!/bin/bash
echo "=== opencode.jsonc (全文) ==="
cat /home/scott-lau/.config/opencode/opencode.jsonc
echo
echo "=== claude settings.json ==="
cat /home/scott-lau/.claude/settings.json 2>/dev/null | grep -iE "BASE_URL|ANTHROPIC_AUTH|model|127.0.0.1|8080|8087"