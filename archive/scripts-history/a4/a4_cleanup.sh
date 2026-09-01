#!/bin/bash
# a4_cleanup.sh — 两站彻底清理 Ray/vLLM 残留 (B 站运行, 清理两站)
# 背景: 22:24/22:39/22:47 三次失败启动在两站留下 RayWorkerProc/raylet 残留,
# ray stop -f 杀不干净跨 session 的 actor, 且 GTT 释放滞后导致下次启动撞显存墙
set -uo pipefail
WORKER_SSH="scott-lau@scott-lau-NEX.local"
VLLM_HOME=/home/scott-lau/vllm-rocm
PY=$(ls "$VLLM_HOME"/bin/python3.* | head -1)

log() { echo "[a4-cleanup] $(date '+%H:%M:%S') $*"; }

cleanup_local() {
  # ray 官方 stop (best effort)
  "$VLLM_HOME/bin/ray" stop -f 2>/dev/null || true
  # 暴力清残留: ray actor/worker/raylet/gcs/dashboard (括号技巧防 pkill 自匹配)
  pkill -9 -f 'default_worke[r]' 2>/dev/null || true
  pkill -9 -f 'rayle[t]' 2>/dev/null || true
  pkill -9 -f 'gcs_serve[r]' 2>/dev/null || true
  pkill -9 -f 'ray::' 2>/dev/null || true
  pkill -9 -f 'ray_[d]ashboard' 2>/dev/null || true
  pkill -9 -f 'raylet.conf\LogMonitor' 2>/dev/null || true
  pkill -9 -f 'vllm.entrypoint[s]' 2>/dev/null || true
  pkill -9 -f 'EngineCore[D]ata' 2>/dev/null || true
  pkill -9 -f 'ray/_private/runtime_en[v]' 2>/dev/null || true
  sleep 2
  local n=$(ps aux | grep -E 'default_worker|ray::|raylet|gcs_server|vllm.entrypoints' | grep -v grep | wc -l)
  local gtt=$(cat /sys/class/drm/card*/device/mem_info_gtt_used 2>/dev/null | head -1)
  echo "  $(hostname -s): remaining_procs=${n} gtt_used=${gtt:-NA}B"
}

log "Cleaning B (head)..."
cleanup_local
log "Cleaning A (worker)..."
ssh -o BatchMode=yes "$WORKER_SSH" "bash -s" <<'A_CLEANUP'
VLLM_HOME=/home/scott-lau/vllm-rocm
"$VLLM_HOME/bin/ray" stop -f 2>/dev/null || true
pkill -9 -f 'default_worke[r]' 2>/dev/null || true
pkill -9 -f 'rayle[t]' 2>/dev/null || true
pkill -9 -f 'gcs_serve[r]' 2>/dev/null || true
pkill -9 -f 'ray::' 2>/dev/null || true
pkill -9 -f 'ray_[d]ashboard' 2>/dev/null || true
pkill -9 -f 'vllm.entrypoint[s]' 2>/dev/null || true
pkill -9 -f 'EngineCore[D]ata' 2>/dev/null || true
pkill -9 -f 'ray/_private/runtime_en[v]' 2>/dev/null || true
sleep 2
n=$(ps aux | grep -E 'default_worker|ray::|raylet|gcs_server|vllm.entrypoints' | grep -v grep | wc -l)
gtt=$(cat /sys/class/drm/card*/device/mem_info_gtt_used 2>/dev/null | head -1)
echo "  $(hostname -s): remaining_procs=${n} gtt_used=${gtt:-NA}B"
A_CLEANUP
log "Cleanup done."
