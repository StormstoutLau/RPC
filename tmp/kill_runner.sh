#!/bin/bash
# 按精确命令行停止 run_questions.py runner
for pid in $(pgrep -f "python3 /tmp/run_questions.py"); do
  kill "$pid" 2>/dev/null && echo "KILLED $pid"
done
sleep 1
if pgrep -f "python3 /tmp/run_questions.py" >/dev/null; then
  echo "STILL-ALIVE"
else
  echo "DEAD"
fi