#!/bin/bash
echo "== opencode run 重试 (240s) =="
timeout 240 opencode run -m cluster-local/gpt-oss "Reply with exactly the single word: OPENCODE-UNSLOTH-OK" > /tmp/oc-out.txt 2>/tmp/oc-err.txt
echo "rc=$?"
echo "--- stdout ---"; tail -20 /tmp/oc-out.txt
echo "--- stderr ---"; tail -20 /tmp/oc-err.txt