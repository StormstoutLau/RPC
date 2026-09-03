#!/bin/bash
echo "== claude settings.json 全文 =="
cat /home/scott-lau/.claude/settings.json
echo
echo "== 8087 有效模型名 =="
curl -s --max-time 30 http://127.0.0.1:8087/v1/models -H "Authorization: Bearer sk-unsloth-581f55854cb263e3ebbc3ba7914b9191" | python3 -c "import sys,json;print([m['id'] for m in json.load(sys.stdin)['data']])"