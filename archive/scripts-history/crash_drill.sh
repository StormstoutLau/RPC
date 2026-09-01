#!/bin/bash
# crash_drill.sh — B 站侧监控: 崩溃传导演练期间轮询 health + 服务状态
LOG="$HOME/llama-distributed/logs/crash_drill_$(date +%Y%m%d_%H%M%S).log"
echo "monitor start $(date +%s) ($(date))" | tee "$LOG"
for i in $(seq 1 60); do
    TS=$(date +%s)
    H=$(curl -s --max-time 3 http://127.0.0.1:8080/health 2>/dev/null | tr -d '\n')
    S=$(systemctl is-active llama-server 2>/dev/null)
    echo "$TS loop=$i llama-server=$S health=${H:-NONE}" >> "$LOG"
    [ "$H" = '{"status":"ok"}' ] && [ $i -gt 6 ] && echo "$TS RECOVERED at loop=$i" >> "$LOG" && break
    sleep 10
done
echo "monitor end $(date +%s)" >> "$LOG"
tail -5 "$LOG"
