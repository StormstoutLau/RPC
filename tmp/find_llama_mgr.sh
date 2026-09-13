#!/bin/bash
P=$(pgrep -x llama-server | head -1)
if [ -z "$P" ]; then echo "NO_LLAMA_SERVER"; exit 0; fi
echo "PID=$P EXE=$(readlink -f /proc/$P/exe)"
echo "CMD: $(tr '\0' ' ' < /proc/$P/cmdline 2>/dev/null | cut -c1-120)"
PP=$(ps -o ppid= -p "$P" | tr -d ' ')
echo "PPID=$PP"
while [ "$PP" != "0" ] && [ "$PP" != "1" ] && [ -n "$PP" ]; do
  ps -o pid,ppid,comm,args= -p "$PP" 2>/dev/null | cut -c1-90
  PP=$(ps -o ppid= -p "$PP" 2>/dev/null | tr -d ' ')
done
echo "=== TIMERS/UNITS ==="
systemctl list-units --type=service,timer --state=active --no-legend 2>/dev/null | grep -iE 'llama|infer|watch' | head -4