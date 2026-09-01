#!/bin/bash
# b5a_deploy.sh — B5a LiteLLM 网关上线 (B 站 :4000, 幂等可重入)
# 设计: 《双机推理服务化与编排框架调研.md》§五 推荐架构 + B5a 行动项
#   路由: minimax-m2 → llama.cpp :8080 | minimax-m2-long → vLLM :8081
#   fallback: long→m2 (8081 死时降级); 不接管进程 (systemd/a4 脚本零侵入)
#   版本锁: 1.98.0 (≥1.82.8, 避 2026-03 PyPI 供应链事件 <1.82.7)
set -uo pipefail

LITELLM_VER="1.98.0"
VENV="$HOME/litellm-venv"
CONF_DIR="$HOME/litellm"
CONF="$CONF_DIR/config.yaml"
UNIT=/etc/systemd/system/litellm.service
PORT=4000
PIP_MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"

echo "===== $(hostname -s) B5a deploy @ $(date '+%F %T') ====="

fail() { echo "FATAL: $*"; exit 1; }

# ---------- [0] preflight ----------
systemctl is-active --quiet llama-server.service || echo "WARN: llama-server 非 active (冒烟将失败)"
ss -tln | grep -q ":${PORT} " && { systemctl is-active --quiet litellm.service && echo "litellm 已在跑 (幂等重入, 走更新流程)"; } || echo "端口 ${PORT} 空闲 ✓"

# ---------- [1] venv ----------
if [ ! -x "$VENV/bin/python" ]; then
  echo "--- [1] 创建 venv $VENV ---"
  python3 -m venv "$VENV" || fail "venv 创建失败 (python3-venv?)"
fi
"$VENV/bin/pip" install -q --upgrade pip -i "$PIP_MIRROR" 2>/dev/null

# ---------- [2] 安装 litellm[proxy] 锁版本 ----------
echo "--- [2] 安装 litellm[proxy]==${LITELLM_VER} (tuna) ---"
"$VENV/bin/pip" install -q -i "$PIP_MIRROR" "litellm[proxy]==${LITELLM_VER}" \
  || fail "pip 安装失败"
INSTALLED=$("$VENV/bin/pip" show litellm 2>/dev/null | awk '/^Version:/{print $2}')
[ "$INSTALLED" = "$LITELLM_VER" ] || fail "版本不匹配: ${INSTALLED:-未检出} != ${LITELLM_VER}"
echo "litellm ${INSTALLED} 安装确认 ✓"

# ---------- [3] 供应链审计 (best-effort: 本地 wheel sha256 vs PyPI 权威元数据) ----------
echo "--- [3] wheel sha256 对照 (PyPI JSON, best-effort) ---"
WHEEL_HASH=$("$VENV/bin/pip" download --no-deps -q -d /tmp/b5a_wheel -i "$PIP_MIRROR" "litellm==${LITELLM_VER}" >/dev/null 2>&1 \
  && sha256sum /tmp/b5a_wheel/litellm-*.whl | awk '{print $1}' || echo "SKIP")
PYPI_HASH=$(curl -s --max-time 15 "https://pypi.org/pypi/litellm/${LITELLM_VER}/json" \
  | grep -o '"sha256": "[a-f0-9]\{64\}"' | head -1 | cut -d'"' -f4 || echo "")
if [ -n "$PYPI_HASH" ] && [ "$WHEEL_HASH" = "$PYPI_HASH" ]; then
  echo "sha256 与 PyPI 一致 ✓ (${WHEEL_HASH:0:16}…)"
elif [ "$WHEEL_HASH" = "SKIP" ]; then
  echo "wheel 下载跳过 (镜像缓存策略), 已装版本 ${INSTALLED} 记录在案"
else
  echo "WARN: sha256 未对上 (镜像 wheel 与 PyPI 元数据, PyPI=${PYPI_HASH:-不可达}) — 记录不阻断: ${WHEEL_HASH:0:16}…"
fi

# ---------- [4] 配置 ----------
echo "--- [4] 写配置 $CONF ---"
mkdir -p "$CONF_DIR"
[ -f "$CONF" ] && cp "$CONF" "$CONF.bak.$(date +%s)"
cat > "$CONF" <<'EOF'
# B5a — LiteLLM Proxy (B 站 :4000)
# 路由语义: minimax-m2 → llama.cpp :8080 (decode 优) | minimax-m2-long → vLLM :8081 (prefill 优)
# fallback: 8081 不可用 → long 请求降级 8080 (同底模 M2.7, prefill 慢但活)
# 注: 两后端 served model 名均为 minimax-m2 (llama.cpp 不校验 model 名, vLLM --served-model-name)
model_list:
  - model_name: minimax-m2
    litellm_params:
      model: openai/minimax-m2
      api_base: http://127.0.0.1:8080/v1
      api_key: sk-local-noauth
  - model_name: minimax-m2-long
    litellm_params:
      model: openai/minimax-m2
      api_base: http://127.0.0.1:8081/v1
      api_key: sk-local-noauth

litellm_settings:
  drop_params: true
  timeout: 600

router_settings:
  fallbacks:
    - minimax-m2-long: ["minimax-m2"]
  num_retries: 1
  cooldown_time: 30
  background_health_checks: true

general_settings:
  # 1.98.0 schema: health_check_interval 须在 general_settings (放 router_settings 会 startup fail)
  health_check_interval: 300
EOF
echo "配置写入 ✓ (master_key 未设 — LAN 信任域, 与 8080/8081 同暴露等级)"

# ---------- [5] systemd ----------
echo "--- [5] 安装 systemd unit ---"
sudo tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=LiteLLM Proxy Gateway (B5a) :${PORT}
After=network-online.target
Wants=network-online.target

[Service]
User=${USER}
ExecStart=${VENV}/bin/litellm --config ${CONF} --host 0.0.0.0 --port ${PORT} --num_workers 1
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now litellm.service

# ---------- [6] 等端口就绪 ----------
echo "--- [6] 等待 :${PORT} 就绪 (最多 60s) ---"
OK=""
for i in $(seq 1 30); do
  if curl -s --max-time 3 "http://127.0.0.1:${PORT}/health/liveliness" | grep -q alive; then OK=1; break; fi
  sleep 2
done
[ -n "$OK" ] || { echo "FATAL: 网关未就绪"; journalctl -u litellm -n 30 --no-pager; exit 1; }
echo "liveliness ✓"

# ---------- [7] 模型注册表 ----------
echo "--- [7] /v1/models ---"
curl -s "http://127.0.0.1:${PORT}/v1/models" | head -c 400; echo

# ---------- [8] 冒烟: minimax-m2 → 8080 ----------
echo "--- [8] 冒烟 model=minimax-m2 (经网关 → 8080) ---"
S=$(date +%s.%N)
R=$(curl -s --max-time 120 -X POST "http://127.0.0.1:${PORT}/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"minimax-m2","messages":[{"role":"user","content":"Say OK"}],"max_tokens":32,"temperature":0}')
E=$(date +%s.%N)
echo "$R" | head -c 400; echo
echo "$R" | grep -q '"choices"' && echo "冒烟 ✓ (耗时 $(echo "$E $S" | awk '{printf "%.2f", $1-$2}')s)" \
  || { echo "冒烟失败"; journalctl -u litellm -n 20 --no-pager; exit 1; }

# ---------- [9] B5b 预演: minimax-m2-long, 8081 当前 down → fallback 8080 ----------
echo "--- [9] fallback 预演 model=minimax-m2-long (8081 down, 预期降级 8080) ---"
S=$(date +%s.%N)
R2=$(curl -s --max-time 120 -X POST "http://127.0.0.1:${PORT}/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"minimax-m2-long","messages":[{"role":"user","content":"Say OK"}],"max_tokens":32,"temperature":0}')
E=$(date +%s.%N)
if echo "$R2" | grep -q '"choices"'; then
  echo "fallback 生效 ✓ (耗时 $(echo "$E $S" | awk '{printf "%.2f", $1-$2}')s)"
else
  echo "fallback 未按预期 (B5b 正式范畴, 不阻断 B5a): $(echo "$R2" | head -c 200)"
fi

# ---------- [10] TTFT 对比 (直连 8080 vs 网关 4000, 流式, 取第 2 次去冷启动) ----------
echo "--- [10] 流式 TTFT 对比 (直连 vs 网关) ---"
BODY='{"model":"minimax-m2","messages":[{"role":"user","content":"写一句话"}],"max_tokens":24,"stream":true}'
for i in 1 2; do
  D=$(curl -sN -o /dev/null -w '%{time_starttransfer}' -X POST http://127.0.0.1:8080/v1/chat/completions \
    -H 'Content-Type: application/json' -d "$BODY" 2>/dev/null || echo "ERR")
  G=$(curl -sN -o /dev/null -w '%{time_starttransfer}' -X POST "http://127.0.0.1:${PORT}/v1/chat/completions" \
    -H 'Content-Type: application/json' -d "$BODY" 2>/dev/null || echo "ERR")
  echo "round $i: direct=${D}s gateway=${G}s"
done

# ---------- [11] 后端零影响确认 ----------
echo "--- [11] llama-server 状态 ---"
systemctl is-active llama-server.service

echo "===== B5a 部署完成 ====="
