#!/bin/bash
# b5i_deploy_b.sh — B5i B 站: 模板 unit + wrapper + CLI + disable 旧自启
# 幂等: 重复执行无副作用
set -uo pipefail
echo "===== $(hostname -s) B5i deploy @ $(date '+%F %T') ====="

# ---------- [1] conf 目录 ----------
sudo mkdir -p /etc/llama-instances
echo "conf 目录 ✓ /etc/llama-instances"

# ---------- [2] wrapper (读 conf 拼 args, exec llama-server) ----------
sudo tee /usr/local/bin/llama-serve-instance >/dev/null <<'EOF'
#!/bin/bash
# llama-serve-instance <alias> — 读 /etc/llama-instances/<alias>.env 启动 llama-server
# systemd EnvironmentFile 无法表达条件参数 (RPC 有无), 故用 wrapper
set -u
ALIAS="$1"
CONF="/etc/llama-instances/${ALIAS}.env"
[ -f "$CONF" ] || { echo "FATAL: conf missing: $CONF"; exit 1; }
source "$CONF"
[ -f "$MODEL_PATH" ] || { echo "FATAL: model missing: $MODEL_PATH"; exit 1; }

RPC_ARGS=""
if [ -n "${RPC_TARGET:-}" ]; then
  # 等 RPC server 就绪 (A 站 rpc-server@<alias> 可能仍在启动)
  HOST_P="${RPC_TARGET%%:*}"; PORT_P="${RPC_TARGET##*:}"
  for i in $(seq 1 90); do
    (exec 3<>"/dev/tcp/${HOST_P}/${PORT_P}") 2>/dev/null && { exec 3>&- 3<&-; break; }
    echo "[wait-rpc] ${RPC_TARGET} not ready (${i})..."
    sleep 2
  done
  RPC_ARGS="--rpc ${RPC_TARGET}"
fi
# EXTRA_FLAGS 有意不加引号 (word-split 展开)
exec /opt/llama.cpp/llama-server -m "$MODEL_PATH" $RPC_ARGS \
  -ngl 999 -c "${CTX:-32768}" -t "${THREADS:-16}" \
  --n-cpu-moe "${N_CPU_MOE:-0}" ${EXTRA_FLAGS:-} \
  --host 0.0.0.0 --port "${PORT:-8080}"
EOF
sudo chmod +x /usr/local/bin/llama-serve-instance
echo "wrapper ✓ /usr/local/bin/llama-serve-instance"

# ---------- [3] 模板 unit ----------
sudo tee /etc/systemd/system/llama-server@.service >/dev/null <<'EOF'
[Unit]
Description=llama.cpp instance %i (conf: /etc/llama-instances/%i.env)
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=scott-lau
Group=scott-lau
SupplementaryGroups=render video
ExecStart=/usr/local/bin/llama-serve-instance %i
Restart=on-failure
RestartSec=10
TimeoutStartSec=600

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
echo "模板 unit ✓ llama-server@.service (TimeoutStartSec 600 容 121G 加载)"

# ---------- [4] CLI: infer-list ----------
sudo tee /usr/local/bin/infer-list >/dev/null <<'EOF'
#!/bin/bash
# infer-list — 两站模型清单: alias/位置/大小/建议后端/conf 状态
AWORK="scott-lau@scott-lau-NEX.local"
scan() {  # $1=tag(本站路径前缀)
  find -L /data/models/gguf -mindepth 2 -maxdepth 2 -type d 2>/dev/null | while read -r d; do
    repo=$(echo "$d" | sed 's|/data/models/gguf/||')
    # 主 gguf 优先级: 合并单文件 (B5j 产物, 排除分片/mmproj) > 分片首片 (未合并)
    F=$(find -L "$d" -name '*.gguf' ! -name '*-of-0000*.gguf' ! -name 'mmproj*' -size +1G -printf '%s %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
    [ -z "$F" ] && F=$(find -L "$d" -name '*-00001-of-*.gguf' 2>/dev/null | head -1)
    [ -z "$F" ] && F=$(find -L "$d" -name '*.gguf' 2>/dev/null | head -1)  # embedding 等小模型
    [ -z "$F" ] && continue
    # 大小用 repo 总量, -L 跟随软链 (repo 是 B5m2 收编软链; 分片首片可能 header-only)
    SZ=$(du -smL "$d" 2>/dev/null | cut -f1)
    alias=$(basename "$d" | sed 's/-GGUF$//' | tr 'A-Z' 'a-z')
    case "$alias" in minimax-m2.7*) alias="m27-q4ks";; esac
    echo "${alias}|${repo}|${SZ}|${F}"
  done
}
# AWQ
for d in /data/models/*/; do
  case "$d" in */gguf/) ;; *)
    ST=$(find -L "$d" -name '*.safetensors' 2>/dev/null | wc -l)
    [ "$ST" -gt 0 ] && { SZ=$(du -m "$d" | cut -f1); echo "m27-awq|$(basename $d)|${SZ}|$d"; }
  ;; esac
done
B_LIST=$(scan)
A_LIST=$(ssh -o BatchMode=yes "$AWORK" "find -L /data/models/gguf -mindepth 2 -maxdepth 2 -type d 2>/dev/null | while read -r d; do
  F=\$(find -L \"\$d\" -name '*-00001-of-*.gguf' 2>/dev/null | head -1)
  [ -z \"\$F\" ] && F=\$(find -L \"\$d\" -name '*.gguf' -size +1G -printf '%s %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
  [ -z \"\$F\" ] && continue
  echo \"\$(basename \"\$d\" | sed 's/-GGUF\$//' | tr 'A-Z' 'a-z')\"
done")
printf "%-38s %-6s %-7s %-12s %s\n" "ALIAS" "位置" "大小" "建议后端" "CONF"
printf "%-38s %-6s %-7s %-12s %s\n" "-----" "----" "----" "--------" "----"
echo "$B_LIST" | while IFS='|' read -r a repo sz f; do
  [ -z "$a" ] && continue
  LOC="B"; inA=$(echo "$A_LIST" | grep -cx "$a" || true); [ "$inA" -ge 1 ] && LOC="AB"
  G=$(( sz / 1024 ))
  if [ -f "/etc/llama-instances/${a}.env" ]; then CF="✓"; else CF="-"; fi
  case "$a" in
    m27-awq) BE="vllm" ;;
    all-minilm*) BE="llama-emb" ;;
    *) if [ "$sz" -gt 66560 ]; then BE="llama-rpc"; else BE="llama-single"; fi ;;
  esac
  printf "%-38s %-6s %-7s %-12s %s\n" "$a" "$LOC" "${G}G" "$BE" "$CF"
done
# A 独有
echo "$A_LIST" | while read -r a; do
  [ -z "$a" ] && continue
  inB=$(echo "$B_LIST" | grep -c "^${a}|" || true)
  [ "$inB" -eq 0 ] && printf "%-38s %-6s %-7s %-12s %s\n" "$a" "A-only" "-" "(需同步B)" "-"
done
EOF
sudo chmod +x /usr/local/bin/infer-list
echo "CLI ✓ infer-list"

# ---------- [5] CLI: infer-load ----------
sudo tee /usr/local/bin/infer-load >/dev/null <<'EOF'
#!/bin/bash
# infer-load <alias前缀> [--backend llama-rpc|llama-single|vllm] [--port N] [--ctx N] [--threads N]
# 首次加载自动生成默认 conf (打印路径, 可编辑后 systemctl restart llama-server@<alias>)
set -uo pipefail
AWORK="scott-lau@scott-lau-NEX.local"
AWORK_IP=192.168.1.11

PREFIX=""; BACKEND=""; PORT=""; CTX=""; THREADS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --backend) BACKEND="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --ctx) CTX="$2"; shift 2 ;;
    --threads) THREADS="$2"; shift 2 ;;
    *) PREFIX="$1"; shift ;;
  esac
done
[ -n "$PREFIX" ] || { echo "用法: infer-load <alias前缀> [--backend ...] [--port N]"; exit 1; }

log() { echo "[infer-load] $(date '+%H:%M:%S') $*"; }

# ---- [1] 解析 alias (唯一前缀匹配) ----
MATCHES=$(find -L /data/models/gguf -mindepth 2 -maxdepth 2 -type d 2>/dev/null | \
  sed 's|/data/models/gguf/[^/]*/||; s|-GGUF$||' | tr 'A-Z' 'a-z' | sed 's/^minimax-m2.7.*/m27-q4ks/' | grep "^${PREFIX}" | sort -u)
N=$(echo "$MATCHES" | grep -c .)
if [ "$N" -eq 0 ]; then echo "ERROR: 无匹配 '$PREFIX' (infer-list 查看)"; exit 1; fi
if [ "$N" -gt 1 ]; then echo "ERROR: 前缀歧义 ($N 匹配):"; echo "$MATCHES"; exit 1; fi
ALIAS="$MATCHES"

# ---- [2] 定位模型文件 + 生成 conf (若缺) ----
CONF="/etc/llama-instances/${ALIAS}.env"
if [ ! -f "$CONF" ]; then
  # 找 repo 目录
  REPO=$(find -L /data/models/gguf -mindepth 2 -maxdepth 2 -type d 2>/dev/null | \
    while read -r d; do a=$(basename "$d" | sed 's/-GGUF$//' | tr 'A-Z' 'a-z'); \
    case "$a" in minimax-m2.7*) a="m27-q4ks";; esac; [ "$a" = "$ALIAS" ] && echo "$d"; done | head -1)
  [ -z "$REPO" ] && { echo "ERROR: repo not found"; exit 1; }
  # 主权重优先级: 合并单文件 (B5j 产物, 排除分片/mmproj) > 分片首片 (未合并)
  F=$(find -L "$REPO" -name '*.gguf' ! -name '*-of-0000*.gguf' ! -name 'mmproj*' -size +1G -printf '%s %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
  [ -z "$F" ] && F=$(find -L "$REPO" -name '*-00001-of-*.gguf' | head -1)
  [ -z "$F" ] && F=$(find -L "$REPO" -name '*.gguf' | head -1)
  # 大小判定: F 为分片首片(未合并)→repo 总量 (防首片 header-only); F 为合并单文件→文件本身
  if echo "$F" | grep -q -- '-of-0000'; then SZ=$(du -smL "$REPO" | cut -f1); else SZ=$(( $(stat -c%s "$F") / 1048576 )); fi
  # 后端默认判定
  if [ -z "$BACKEND" ]; then
    case "$ALIAS" in all-minilm*) BACKEND="llama-single";; *) \
      if [ "$SZ" -gt 66560 ]; then BACKEND="llama-rpc"; else BACKEND="llama-single"; fi ;;
    esac
  fi
  RPCV=""; [ "$BACKEND" = "llama-rpc" ] && RPCV="10.10.10.1:50052"
  NCM=0; [ "$BACKEND" = "llama-rpc" ] && NCM=8
  EMB=""; case "$ALIAS" in all-minilm*) EMB="--embedding";; esac
  sudo tee "$CONF" >/dev/null <<CEOF
# B5i 自动生成 ($(date '+%F %T')) — 可编辑后 systemctl restart llama-server@${ALIAS}
MODEL_PATH=${F}
PORT=${PORT:-8080}
CTX=${CTX:-32768}
THREADS=${THREADS:-16}
N_CPU_MOE=${NCM}
RPC_TARGET=${RPCV}
EXTRA_FLAGS="-fa on ${EMB}"
CEOF
  log "conf 生成: $CONF (backend=$BACKEND)"
fi
source "$CONF"
[ -n "$PORT" ] && PORT_NUM="$PORT" || PORT_NUM="${PORT:-8080}"

# ---- [3] 互斥: 停另一后端 ----
log "停旧实例 (llama/vllm)..."
sudo systemctl stop 'llama-server@*' 2>/dev/null || true
if pgrep -f 'vllm.entrypoint[s]' >/dev/null 2>&1; then
  log "停 vLLM (Ray 双机)..."
  pkill -f 'vllm.entrypoint[s]' 2>/dev/null || true
  pkill -f '^ray::' 2>/dev/null || true
  /home/scott-lau/vllm-rocm/bin/ray stop -f 2>/dev/null || true
  ssh -o BatchMode=yes "$AWORK" "pkill -f '^ray::' 2>/dev/null; /home/scott-lau/vllm-rocm/bin/ray stop -f 2>/dev/null" 2>/dev/null || true
fi

wait_gtt() {  # $1=tag, $2=ssh target (空=本地)
  for i in $(seq 1 90); do
    if [ -n "$2" ]; then
      used=$(ssh -o BatchMode=yes "$2" "cat /sys/class/drm/card*/device/mem_info_gtt_used 2>/dev/null | head -1")
    else
      used=$(cat /sys/class/drm/card*/device/mem_info_gtt_used 2>/dev/null | head -1)
    fi
    [ -z "$used" ] && used=0
    [ "$used" -lt 2000000000 ] && { log "$1 GTT released"; return 0; }
    sleep 2
  done
  log "WARN: $1 GTT 180s 未释放"
}
wait_gtt "B" ""
wait_gtt "A" "$AWORK"

# ---- [4] vLLM 路径 ----
if [ "$BACKEND" = "vllm" ]; then
  log "vLLM 路径: 调 a4_vllm_launch.sh (仅 m27-awq 验证)..."
  exec bash /home/scott-lau/scripts/a4_vllm_launch.sh
fi

# ---- [5] A 站 rpc-server (分布式) ----
if [ -n "${RPC_TARGET:-}" ]; then
  log "A 站起 rpc-server@${ALIAS} (cache /data/rpccache/${ALIAS})..."
  ssh -o BatchMode=yes "$AWORK" "sudo systemctl start rpc-server@${ALIAS}"
fi

# ---- [6] B 站 llama-server ----
log "B 站起 llama-server@${ALIAS} (port ${PORT_NUM})..."
sudo systemctl start "llama-server@${ALIAS}"

# ---- [7] 健康检查 (-f: 503 Loading model 不算就绪) ----
for i in $(seq 1 120); do
  if curl -sf --max-time 2 "http://127.0.0.1:${PORT_NUM}/health" >/dev/null 2>&1; then
    log "READY ✓ :${PORT_NUM} (llama-server@${ALIAS})"
    exit 0
  fi
  sleep 3
done
log "ERROR: 健康检查 6min 超时 — journalctl -u llama-server@${ALIAS} 排查"
exit 1
EOF
sudo chmod +x /usr/local/bin/infer-load
echo "CLI ✓ infer-load"

# ---------- [6] CLI: infer-unload ----------
sudo tee /usr/local/bin/infer-unload >/dev/null <<'EOF'
#!/bin/bash
# infer-unload — 停两站全部推理实例, 等 GTT 释放
set -uo pipefail
AWORK="scott-lau@scott-lau-NEX.local"
log() { echo "[infer-unload] $(date '+%H:%M:%S') $*"; }
log "停 B 站 llama-server@*..."
sudo systemctl stop 'llama-server@*' 2>/dev/null || true
if pgrep -f 'vllm.entrypoint[s]' >/dev/null 2>&1; then
  log "停 vLLM..."
  pkill -f 'vllm.entrypoint[s]' 2>/dev/null || true
  pkill -f '^ray::' 2>/dev/null || true
  /home/scott-lau/vllm-rocm/bin/ray stop -f 2>/dev/null || true
fi
log "停 A 站 rpc-server@*..."
ssh -o BatchMode=yes "$AWORK" "sudo systemctl stop 'rpc-server@*' 2>/dev/null; pkill -f '^ray::' 2>/dev/null; /home/scott-lau/vllm-rocm/bin/ray stop -f 2>/dev/null" 2>/dev/null || true
wait_gtt() {  # $1=tag, $2=ssh
  for i in $(seq 1 90); do
    if [ -n "$2" ]; then used=$(ssh -o BatchMode=yes "$2" "cat /sys/class/drm/card*/device/mem_info_gtt_used 2>/dev/null | head -1")
    else used=$(cat /sys/class/drm/card*/device/mem_info_gtt_used 2>/dev/null | head -1); fi
    [ -z "$used" ] && used=0
    [ "$used" -lt 2000000000 ] && { log "$1 GTT released (${used}B)"; return 0; }
    sleep 2
  done
  log "WARN: $1 GTT 未完全释放"
}
wait_gtt "B" ""
wait_gtt "A" "$AWORK"
log "UNLOADED ✓ (两站内存回收)"
EOF
sudo chmod +x /usr/local/bin/infer-unload
echo "CLI ✓ infer-unload"

# ---------- [7] disable 旧自启 (不停当前进程) ----------
sudo systemctl disable llama-server 2>/dev/null && echo "旧 llama-server 自启已 disable (进程不停, 由 infer-* 接管)" || echo "旧 unit 已 disable/不存在"

echo ""
echo "=== B 站部署完成 ==="
echo "下一步: A 站部署 (b5i_deploy_a.sh) → 冒烟 infer-load m27"
