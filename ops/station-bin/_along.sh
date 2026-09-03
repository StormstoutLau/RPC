#!/bin/bash
export KEY=sk-unsloth-4a22add73a4afc3c0a1c473191144212
echo "launching opencode (1800s)..."
nohup timeout 1800 opencode run -m cluster-local/gpt-oss "Reply with exactly OPENCODE-UNSLOTH-OK" > /tmp/oc-long.txt 2>/tmp/oc-long.err </dev/null &
echo "opencode pid=$!"
sleep 2
echo "launching claude (1800s)..."
nohup env ANTHROPIC_BASE_URL=http://127.0.0.1:8080/v1 ANTHROPIC_AUTH_TOKEN=$KEY \
  ANTHROPIC_DEFAULT_SONNET_MODEL=gpt-oss-120b-MXFP4 CLAUDE_CODE_ATTRIBUTION_HEADER=0 \
  timeout 1800 claude -p "Reply with exactly CLAUDE-UNSLOTH-OK" > /tmp/claude-long.txt 2>/tmp/claude-long.err </dev/null &
echo "claude pid=$!"
sleep 3
echo "running procs:"; ps -eo pid,args | grep -E "[o]pencode run|[c]laude -p" | head