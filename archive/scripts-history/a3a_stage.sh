#!/bin/bash
# A3a: 分阶段应用 ayysasha USB4 低延迟套件 (两站通用, 需 sudo)
# 用法: sudo bash a3a_stage.sh <sysctl|tbpower|epp|revert_epp|status>
set -x
case "$1" in
sysctl)
  for kv in "net.core.busy_read=100" "net.core.busy_poll=100" "net.ipv4.tcp_fastopen=3"; do
    k="${kv%%=*}"; v="${kv##*=}"
    if cur=$(sysctl -n "$k" 2>/dev/null); then
      sysctl -w "$k=$v" >/dev/null
      echo "APPLIED $k: $cur -> $(sysctl -n "$k")"
    else
      echo "MISSING $k (skip)"
    fi
  done
  if sysctl -n net.ipv4.tcp_low_latency >/dev/null 2>&1; then
    sysctl -w net.ipv4.tcp_low_latency=1 >/dev/null
    echo "APPLIED tcp_low_latency: -> $(sysctl -n net.ipv4.tcp_low_latency)"
  else
    echo "MISSING net.ipv4.tcp_low_latency (modern kernel removed, skip)"
  fi
  ;;
tbpower)
  for f in /sys/bus/thunderbolt/devices/*/power/control; do
    if [ -e "$f" ]; then
      echo "TB_BEFORE $f=$(cat "$f")"
      echo on > "$f"
      echo "TB_AFTER  $f=$(cat "$f")"
    fi
  done
  ;;
epp)
  echo "EPP_BEFORE $(cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference)"
  for f in /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference; do
    echo performance > "$f"
  done
  echo "EPP_AFTER  $(cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference)"
  ;;
revert_epp)
  for f in /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference; do
    echo balance_performance > "$f"
  done
  echo "EPP_REVERTED $(cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference)"
  ;;
status)
  echo "== sysctl =="
  for k in net.core.busy_read net.core.busy_poll net.ipv4.tcp_fastopen; do
    echo "$k=$(sysctl -n "$k" 2>/dev/null)"
  done
  echo "tcp_low_latency=$(sysctl -n net.ipv4.tcp_low_latency 2>/dev/null || echo MISSING)"
  echo "== TB power =="
  for f in /sys/bus/thunderbolt/devices/*/power/control; do
    [ -e "$f" ] && echo "$f=$(cat "$f")"
  done
  echo "== EPP =="
  cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference
  ;;
esac
