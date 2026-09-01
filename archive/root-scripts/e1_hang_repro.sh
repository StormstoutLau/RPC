#!/bin/bash
# E1 判别实验 (2026-09-01, 按 A站挂死根因分析_20260901.md §6)
# 条件: L0 已删 bjork cron + L1 观测已布防
# 判据: 3 轮 16384 think 全过 → cron 干扰实锤, 关案; 中途挂 → 转判别实验 E2 (netconsole 取证)
set -u
LOG=/tmp/e1_hang_repro.log
NCLOG=/var/log/netconsole-a.log
API=http://127.0.0.1:8080/v1/chat/completions
ROUNDS=3

ts() { date '+%F %T'; }
log() { echo "[$(ts)] $*" | tee -a $LOG; }

> $LOG
log "=== E1 start: ${ROUNDS} rounds x 16384 think, L0 已删 cron ==="

# 0. A 站 console_loglevel 调 7 (info 级 hogged 也能镜像, 测后恢复)
log "A 站 console_loglevel 调 7 (取证覆盖)"
ssh -o ConnectTimeout=10 scott-lau@10.10.10.1 'sudo sysctl -w kernel.printk="7 4 1 7"' >> $LOG 2>&1

# 看门狗: 20s ping A 站, 3 连败 = 挂死判定 (对应 60s 止损链)
start_watchdog() {
  (
    fail=0
    while true; do
      if ! ping -c1 -W5 10.10.10.1 >/dev/null 2>&1; then
        fail=$((fail+1))
        echo "[$(ts)] WATCHDOG: ping fail x${fail}" >> $LOG
        if [ $fail -ge 3 ]; then
          echo "[$(ts)] HANG_DETECTED: A 站 60s 不可达 — netconsole 遗言见 B:/var/log/netconsole-a.log" >> $LOG
          exit 99
        fi
      else
        [ $fail -gt 0 ] && echo "[$(ts)] WATCHDOG: ping 恢复" >> $LOG
        fail=0
      fi
      sleep 20
    done
  ) &
  WD_PID=$!
}

PASS=0
for round in $(seq 1 $ROUNDS); do
  log "--- Round ${round}/${ROUNDS} begin ---"
  NCSIZE0=$(sudo stat -c%s $NCLOG 2>/dev/null || echo 0)
  start_watchdog
  t0=$(date +%s)
  resp=$(curl -s -m 3600 $API -H 'Content-Type: application/json' -d '{
    "model": "minimax-m2",
    "messages": [{"role": "user", "content": "Solve with exhaustive step-by-step reasoning: derive tight bounds for the number of distinct binary trees with n internal nodes, extend to m-ary trees with closed forms and asymptotics, then verify against small cases and discuss degenerate regimes. Reason at full depth."}],
    "max_tokens": 16384,
    "temperature": 0.7
  }')
  rc=$?
  t1=$(date +%s)
  kill $WD_PID 2>/dev/null
  wait $WD_PID 2>/dev/null

  if grep -q HANG_DETECTED $LOG; then
    log "Round ${round}: 看门狗判定挂死, E1 终止 → 转 E2 netconsole 取证"
    break
  fi
  if [ $rc -ne 0 ]; then
    log "Round ${round}: curl FAIL rc=${rc} (超时/连接失败) → 疑似挂死"
    break
  fi
  ct=$(echo "$resp" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("usage",{}).get("completion_tokens","?"))' 2>/dev/null)
  dur=$((t1-t0))
  tps=$(python3 -c "print(f'{($ct if str.isdigit(\"$ct\") else 0)/max($dur,1):.1f}')" 2>/dev/null)
  log "Round ${round} OK: ${ct} tokens / ${dur}s (~${tps} t/s)"
  PASS=$((PASS+1))

  # netconsole 增量检查 (挂死前兆/异常)
  NCSIZE1=$(sudo stat -c%s $NCLOG 2>/dev/null || echo 0)
  if [ "$NCSIZE1" != "$NCSIZE0" ]; then
    log "Round ${round}: netconsole 新增 $((NCSIZE1-NCSIZE0))B:"
    sudo tail -c +$((NCSIZE0+1)) $NCLOG | tee -a $LOG
  fi
done

# A 站 console_loglevel 恢复 4
ssh -o ConnectTimeout=10 scott-lau@10.10.10.1 'sudo sysctl -w kernel.printk="4 4 1 7"' >> $LOG 2>&1

log "=== E1 end: ${PASS}/${ROUNDS} pass ==="
if [ $PASS -eq $ROUNDS ]; then
  log "VERDICT: 3/3 全过 → cron 干扰实锤, 关案 (L0 有效)"
else
  log "VERDICT: 未全过 → 转 E2: sudo cat $NCLOG 找挂死最后遗言"
fi
touch /tmp/e1_done
