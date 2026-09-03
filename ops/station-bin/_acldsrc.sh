#!/bin/bash
echo "== ~/.claude.json 中 MXFP4/fable/8087/gpt-oss 命中 =="
grep -iE 'MXFP4|fable|8087|gpt-oss|unsloth' /home/scott-lau/.claude.json 2>/dev/null | head -30
echo
echo "== 是否有其他 claude 配置 =="
ls -la /home/scott-lau/.claude/ | head -20
echo "== ~/.config/claude ==="
ls -la /home/scott-lau/.config/claude 2>/dev/null | head
grep -iE 'MXFP4|fable|8087|gpt-oss' /home/scott-lau/.config/claude/settings.json 2>/dev/null | head