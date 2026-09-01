#!/usr/bin/env bash
# a4_vllm_launch.sh — A4: vLLM TP=2 启动器 (B站=head+API, A站=worker, Ray over thunderbolt0)
# 基于 ayysasha/Strix-halo-dual-optimized launch/vllm-inner.sh 适配 lemonade 便携构建 (无 toolbox)
# 用法: bash a4_vllm_launch.sh [port]   (默认 8081)
# 前置: 两站 ~/vllm-rocm 已解压, ~/moe-shim ~/moe-configs 已部署, 模型已下载
# 注意: 启动前自动停 llama.cpp 服务释放两站显存 (llama-server@B, rpc-server@A)
set -uo pipefail
PORT="${1:-8081}"
# B5i (2026-08-30): 模型目录可参数化 (默认 M2.7 AWQ; MoE tuned-config 为 M2.7 专用)
MODEL_DIR_ARG="${2:-}"

# ---- 拓扑 ----
HEAD_IP=10.10.10.2            # B站 (GTR-Pro) TB IP
WORKER_IP=10.10.10.1          # A站 (NEX) TB IP
WORKER_USER=scott-lau
WORKER_SSH="scott-lau@scott-lau-NEX.local"
IFACE=thunderbolt0

# ---- 路径 (两站统一 ~/vllm-rocm; python 版本动态检测: build 实为 3.14) ----
VLLM_HOME=/home/scott-lau/vllm-rocm                 # head (B站)
PY=$(ls "$VLLM_HOME"/bin/python3.* | head -1)
SITE=$(ls -d "$VLLM_HOME"/lib/python3.*/site-packages | head -1)
ROCMLIB="${VLLM_HOME}/lib:${SITE}/_rocm_sdk_core/lib:${SITE}/_rocm_sdk_libraries/lib"
WORKER_VLLM_HOME=/home/scott-lau/vllm-rocm          # worker (A站, 同路径)
WORKER_PY="$PY"
WORKER_ROCMLIB="$ROCMLIB"
# B5m2 (2026-08-30): head 模型路径统一为 /data/models (软链 → ~/models 实体, 两站对称)
# B5i: 第2参数可覆盖 (目前仅 M2.7 AWQ 有 MoE tuned-config, 其他 AWQ 需自配 config)
HEAD_MODEL_DIR="${MODEL_DIR_ARG:-/data/models/MiniMax-M2.7-AWQ-G32-STRIX-2H}"
WORKER_MODEL_DIR="${HEAD_MODEL_DIR}"
SHIM_DIR=/home/scott-lau/moe-shim                # 两站同路径
CONFIG_DIR=/home/scott-lau/moe-configs           # 两站同路径
MOE_CONFIG_NAME="E=256,N=768,device_name=Radeon_8060S_Graphics,dtype=int4_w4a16.json"
MODEL_ALIAS=/tmp/model-alias

log() { echo "[a4-launch] $(date '+%H:%M:%S') $*"; }

# ---- 0. 停 llama.cpp 服务释放显存 (B5i: 模板实例 + 旧单体兼容) ----
log "Stopping llama.cpp services on both nodes..."
sudo systemctl stop 'llama-server@*' 2>/dev/null || true
sudo systemctl stop llama-server 2>/dev/null || true
ssh -o BatchMode=yes "$WORKER_SSH" "sudo systemctl stop 'rpc-server@*' 2>/dev/null; sudo systemctl stop rpc-server 2>/dev/null" || true

# 等待两站 GTT 释放 (llama-server 卸载 ~60GB 模型需数秒-数十秒, sleep 3 不够会撞
# "Free memory ... less than desired GPU memory utilization" 瞬态错误)
wait_gtt_free() {  # $1=tag, $2=ssh target (空=本地)
  for i in $(seq 1 90); do
    if [ -n "$2" ]; then
      used=$(ssh -o BatchMode=yes "$2" "cat /sys/class/drm/card*/device/mem_info_gtt_used 2>/dev/null | head -1")
    else
      used=$(cat /sys/class/drm/card*/device/mem_info_gtt_used 2>/dev/null | head -1)
    fi
    [ -z "$used" ] && used=0
    if [ "$used" -lt 2000000000 ]; then
      log "$1 GTT released (used=${used}B)"; return 0
    fi
    sleep 2
  done
  log "WARN: $1 GTT still busy after 180s"
}
wait_gtt_free "B(head)" ""
wait_gtt_free "A(worker)" "$WORKER_SSH"

# ---- 1. 预检: 模型/shim/config/venv 就位 ----
test -f "${HEAD_MODEL_DIR}/config.json" || { log "ERROR: head model missing"; exit 1; }
test -x "$PY" || { log "ERROR: $PY missing (extract vllm-rocm first)"; exit 1; }
test -f "${SHIM_DIR}/sitecustomize.py" || { log "ERROR: shim missing on head"; exit 1; }
test -f "${CONFIG_DIR}/${MOE_CONFIG_NAME}" || { log "ERROR: tuned config missing on head"; exit 1; }
ln -sfn "${HEAD_MODEL_DIR}" "${MODEL_ALIAS}"
ssh -o BatchMode=yes "$WORKER_SSH" \
  "test -f '${WORKER_MODEL_DIR}/config.json' \
   && test -x '${WORKER_PY}' \
   && test -f '${SHIM_DIR}/sitecustomize.py' \
   && test -f '${CONFIG_DIR}/${MOE_CONFIG_NAME}' \
   && ln -sfn '${WORKER_MODEL_DIR}' '${MODEL_ALIAS}'" \
  || { log "ERROR: worker preflight failed"; exit 1; }

# ---- 2. ROCm 库路径 (动态检测 site-packages) ----
export LD_LIBRARY_PATH="${ROCMLIB}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

# ---- 3. head 运行时 env (ayysasha §9 完整配方) ----
export HF_HUB_OFFLINE=1          # 模型全本地, 阻断 vLLM 对 HF 的 HEAD 探测 (B 站无法直连)
export VLLM_HOST_IP="${HEAD_IP}"
export GLOO_SOCKET_IFNAME="${IFACE}"
export NCCL_SOCKET_IFNAME="${IFACE}"
export NCCL_IB_DISABLE=1
export NCCL_IB_GID_INDEX=1
export NCCL_NET_GDR_LEVEL=0
export RAY_DISABLE_METRICS=1
export RAY_EXPERIMENTAL_NOSET_ROCR_VISIBLE_DEVICES=1
export RAY_memory_monitor_refresh_ms=0
export VLLM_ROCM_USE_AITER=0
export OMP_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false
# TORCHDYNAMO_DISABLE=1 已移除: 禁用 dynamo 会让 torch.compile 变 no-op,
# CUDA graph 路径 (非 --enforce-eager) 的 aot_compile 必报 "not supported"
export RAY_CGRAPH_get_timeout=1800
export VLLM_SLEEP_WHEN_IDLE=1
export VLLM_USE_DEEP_GEMM=0
export VLLM_USE_FLASHINFER_MOE_FP16=0
export VLLM_USE_FLASHINFER_SAMPLER=0
# gfx1151 长上下文稳定性 env 块 (ayysasha A/B 验证: 60k PP +12% / TG +7%)
export HSA_NO_SCRATCH_RECLAIM=1
export AMDGCN_USE_BUFFER_OPS=0
export PYTORCH_HIP_ALLOC_CONF='expandable_segments:True'
export HIP_FORCE_DEV_KERNARG=1
export SAFETENSORS_FAST_GPU=1
# MoE tuned-config + shim (head) + amdsmi (vLLM 0.25.2 platform 探测必需, 在 _rocm_sdk_core/share)
export VLLM_TUNED_CONFIG_FOLDER="${CONFIG_DIR}"
export PYTHONPATH="${SHIM_DIR}:${SITE}/_rocm_sdk_core/share/amd_smi${PYTHONPATH:+:${PYTHONPATH}}"

# ---- 4. Ray 集群 (bin/ray 已修 shebang) ----
log "Cleaning up old Ray (both nodes)..."
"$VLLM_HOME/bin/ray" stop -f 2>/dev/null || true
ssh -o BatchMode=yes "$WORKER_SSH" \
  "export LD_LIBRARY_PATH='${WORKER_ROCMLIB}'; \
   '${WORKER_VLLM_HOME}/bin/ray' stop -f 2>/dev/null" 2>/dev/null || true

log "Starting Ray head (B) on ${HEAD_IP}..."
"$VLLM_HOME/bin/ray" start --head --node-ip-address "${HEAD_IP}" --port 6379 \
  --num-cpus 8 --num-gpus 1 --disable-usage-stats --include-dashboard=false

log "Starting Ray worker (A) on ${WORKER_IP}..."
ssh -o BatchMode=yes "$WORKER_SSH" "bash -s" <<WORKER_SCRIPT
export VLLM_HOST_IP=${WORKER_IP}
export HF_HUB_OFFLINE=1
export GLOO_SOCKET_IFNAME=${IFACE}
export NCCL_SOCKET_IFNAME=${IFACE}
export NCCL_IB_DISABLE=1
export NCCL_IB_GID_INDEX=1
export NCCL_NET_GDR_LEVEL=0
export RAY_DISABLE_METRICS=1
export RAY_EXPERIMENTAL_NOSET_ROCR_VISIBLE_DEVICES=1
export RAY_memory_monitor_refresh_ms=0
export OMP_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false
export RAY_CGRAPH_get_timeout=1800
export HSA_NO_SCRATCH_RECLAIM=1
export AMDGCN_USE_BUFFER_OPS=0
export PYTORCH_HIP_ALLOC_CONF='expandable_segments:True'
export HIP_FORCE_DEV_KERNARG=1
export SAFETENSORS_FAST_GPU=1
export VLLM_TUNED_CONFIG_FOLDER=${CONFIG_DIR}
export PYTHONPATH=${SHIM_DIR}:${SITE}/_rocm_sdk_core/share/amd_smi
export LD_LIBRARY_PATH='${WORKER_ROCMLIB}'
'${WORKER_VLLM_HOME}/bin/ray' start --address=${HEAD_IP}:6379 --node-ip-address ${WORKER_IP} \
  --num-cpus 8 --num-gpus 1 --disable-usage-stats
WORKER_SCRIPT

log "Waiting for Ray cluster (2 GPUs)..."
for i in $(seq 1 60); do
  if "$VLLM_HOME/bin/ray" status 2>/dev/null | grep -qE '/2\.0 GPU|/2 GPU'; then
    log "Ray ready (2 GPUs online)."
    break
  fi
  if [ "$i" -eq 60 ]; then log "ERROR: Ray cluster not ready after 60s"; exit 1; fi
  sleep 1
done

# ---- 5. vLLM serve (TP=2, Ray backend) ----
log "Launching vllm serve on 0.0.0.0:${PORT} ..."
# NB: vLLM 0.25.2 直接调 api_server 模块时, 位置参数 model_tag 不会映射到 args.model
# (映射只在 `vllm serve` CLI 入口 cli/serve.py:52 发生), 必须显式 --model
# eager 开关: 默认开 (2026-08-29 实测 CUDA graph 在 gfx1151+ROCm nightly 为大幅负迁移:
# 512ctx TG 14.92 vs eager 17.60 (-15%), 16k TG 3.70 vs 12.87 (-71%, 病理性), PP 275 vs 298)
# 试验 CUDA graph 时: VLLM_EAGER=0 bash a4_vllm_launch.sh
EAGER_FLAG="--enforce-eager"
if [ "${VLLM_EAGER:-1}" = "0" ]; then EAGER_FLAG=""; fi
exec "$PY" -m vllm.entrypoints.openai.api_server \
  --model "${MODEL_ALIAS}" \
  --served-model-name minimax-m2 \
  --host 0.0.0.0 --port "${PORT}" \
  --tensor-parallel-size 2 --distributed-executor-backend ray ${EAGER_FLAG} \
  --gpu-memory-utilization 0.92 --max-model-len 196608 --max-num-seqs 1 --max-num-batched-tokens 20480 \
  --dtype auto --load-format safetensors --ignore-patterns "original/**/*" --trust-remote-code \
  --tool-call-parser minimax_m2 --reasoning-parser minimax_m2 --enable-auto-tool-choice
