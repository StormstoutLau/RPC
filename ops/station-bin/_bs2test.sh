#!/bin/bash
# bs2-test.sh — BS-2: 实测网关单轮多 subagent 扇出 (3-sibling, message 传参)
set -u
MODEL="${1:-opencode/nemotron-3.5-lightning-free}"
OUT=/tmp/bs2-task.out
echo "== 目标: $MODEL =="
PROMPT="Trigger all three subagents NOW in one single message by issuing all three agent tool calls in the SAME turn (do not wait for one before the next): 
1. agent ars-researcher -> reply exactly RESEARCHER-OK
2. agent ars-reviewer -> reply exactly REVIEWER-OK
3. agent ars-writer -> reply exactly WRITER-OK
Emit all three tool calls together so they run in parallel. Then list which returned."
T0=$(date +%s%N)
opencode run -m "$MODEL" --agent build --dir /tmp/bs2-ws --format default "$PROMPT" 2>&1 | tail -30
E0=$(date +%s%N)
echo "wall_ms=$(( (E0-T0)/1000000 ))"
echo OK