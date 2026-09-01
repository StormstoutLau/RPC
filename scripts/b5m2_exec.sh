#!/bin/bash
# b5m2_exec.sh — B5m2 执行: ①删 AWQ .cache 下载垃圾 ②B站删 M2.7 Q4_K_M-merged ③GGUF/AWQ 软链收编 /data/models
# 用法: bash b5m2_exec.sh   (两站通用; B 站额外做 ②)
set -uo pipefail
log() { echo "[b5m2 $(hostname -s) $(date '+%H:%M:%S')] $*"; }

AWQ_A="/data/models/MiniMax-M2.7-AWQ-G32-STRIX-2H"
AWQ_B="$HOME/models/MiniMax-M2.7-AWQ-G32-STRIX-2H"
AWQ="$([ -d "$AWQ_A" ] && echo "$AWQ_A" || echo "$AWQ_B")"

echo "=== 0. 前置检查 ==="
# vLLM/Ray 不在跑 (在跑则 .cache 可能被占用, 中止)
if pgrep -f 'vllm.entrypoint[s]|ray::' >/dev/null 2>&1; then
  log "ABORT: vLLM/Ray 进程在跑, 先 a4_cleanup"; exit 1
fi
log "vLLM/Ray 未运行, 继续"

echo "=== 1. 删 AWQ .cache 下载垃圾 ==="
if [ -d "$AWQ/.cache" ]; then
  N=$(find "$AWQ/.cache" -type f | wc -l)
  SZ=$(du -sh "$AWQ/.cache" | cut -f1)
  log "rm -rf $AWQ/.cache ($N files, $SZ)"
  rm -rf "$AWQ/.cache"
else
  log "no .cache (already clean)"
fi
# 验证: 模型本体无损
M=$(find "$AWQ" -maxdepth 1 -name 'model-*.safetensors' | wc -l)
[ "$M" = "32" ] && log "AWQ 32 分片 OK" || { log "ERROR: AWQ 分片数=$M (expect 32)"; exit 1; }
[ -f "$AWQ/config.json" ] && log "AWQ config.json OK" || { log "ERROR: config.json 丢失"; exit 1; }

echo "=== 2. B 站专属: 删 M2.7 Q4_K_M-merged (用户决策: 保留现役 heretic Q4_K_S) ==="
if [ "$(hostname -s)" = "scott-lau-GTR-Pro" ]; then
  D="$HOME/.lmstudio/models/lmstudio-community/MiniMax-M2.7-GGUF"
  if [ -d "$D" ]; then
    log "目录内容 (删除前确认):"; ls -la "$D"
    log "rm -rf $D"
    rm -rf "$D"
  else
    log "目录已不存在"
  fi
  # 验证: 现役文件 + 服务
  F="$HOME/.lmstudio/models/llmfan46/MiniMax-M2.7-ultra-uncensored-heretic-GGUF/MiniMax-M2.7-BF16-ultra-uncensored-heretic-Q4_K_S.gguf"
  [ -f "$F" ] && log "现役 heretic Q4_K_S OK ($(stat -c %s "$F")B)" || { log "ERROR: 现役文件丢失!"; exit 1; }
  systemctl is-active llama-server | grep -q active && log "llama-server active OK" || log "WARN: llama-server 非 active"
fi

echo "=== 3. GGUF/AWQ 软链收编 /data/models (不搬文件) ==="
if [ "$(hostname -s)" = "scott-lau-GTR-Pro" ] && [ ! -d /data ]; then
  sudo mkdir -p /data && sudo chown scott-lau:scott-lau /data
fi
mkdir -p /data/models/gguf
# LM Studio repo 目录 → /data/models/gguf/<publisher>/<repo> 软链
N=0
for pub_dir in "$HOME"/.lmstudio/models/*/; do
  pub=$(basename "$pub_dir")
  mkdir -p "/data/models/gguf/$pub"
  for repo_dir in "$pub_dir"*/; do
    [ -d "$repo_dir" ] || continue
    repo=$(basename "$repo_dir")
    ln -sfn "$repo_dir" "/data/models/gguf/$pub/$repo"
    N=$((N+1))
  done
done
log "GGUF 软链 $N 个 repo → /data/models/gguf/"
# AWQ 路径对称 (B 站: ~/models → /data/models 同构)
if [ -d "$AWQ_B" ] && [ ! -e "$AWQ_A" ]; then
  ln -sfn "$AWQ_B" "$AWQ_A"
  log "AWQ 软链: $AWQ_A → $AWQ_B"
fi

echo "=== 4. df after ==="
df -h / | tail -1
echo "=== B5M2_EXEC_DONE ==="
