#!/bin/bash
# C station: guarded restart of llama-server@qwen3.8-27b-mtp (new GGML_RPC binary)
set -u
GATE_MIN_G=41
AV=$(free -g | awk 'NR==2{print $7}')
echo "=== MEM_GATE ==="
echo "AV_g=$AV"
if [ "$AV" -ge "$GATE_MIN_G" ]; then echo GATE_PASS; else echo "GATE_BLOCK_AV=$AV (need >=$GATE_MIN_G)"; exit 1; fi

echo "=== OLD PID/BIN ==="
OLDPID=$(systemctl show llama-server@qwen3.8-27b-mtp.service -p MainPID --no-pager | cut -d= -f2)
echo "main_pid=$OLDPID"
readlink -f "/proc/$OLDPID/exe" 2>/dev/null || echo old_exe_unreadable

echo "=== STOP ==="
sudo systemctl stop llama-server@qwen3.8-27b-mtp.service
echo "stopped rc=$?"

echo "=== WAIT_GTT_RELEASE ==="
for i in $(seq 1 30); do
  AV2=$(free -g | awk 'NR==2{print $7}')
  echo "  poll${i}: AV_g=$AV2"
  if [ "$AV2" -ge 100 ]; then echo GTT_RELEASED; break; fi
  sleep 5
done

echo "=== START ==="
sudo systemctl start llama-server@qwen3.8-27b-mtp.service
sleep 3
systemctl is-active llama-server@qwen3.8-27b-mtp.service

echo "=== NEW BIN ==="
NEWPID=$(systemctl show llama-server@qwen3.8-27b-mtp.service -p MainPID --no-pager | cut -d= -f2)
readlink -f "/proc/$NEWPID/exe" 2>/dev/null || echo new_exe_unreadable

echo "=== PROPS ==="
for i in $(seq 1 20); do
  N=$(curl -s --max-time 5 http://127.0.0.1:18080/props 2>/dev/null | grep -oE '"n_ctx":[ ]*[0-9]+' | head -1)
  if [ -n "$N" ]; then echo "$N"; break; fi
  sleep 3
done
echo "RESTART_DONE"