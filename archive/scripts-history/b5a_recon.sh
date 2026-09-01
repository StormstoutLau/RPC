#!/bin/bash
# b5a_recon.sh — B5a 前置侦察 (B 站, 只读): 8080 模型名接受性 + pip/venv 可用性 + litellm 版本发现
set -u
echo "===== $(hostname -s) @ $(date '+%F %T') ====="

echo "--- [1] 8080 chat completion (model=minimax-m2, 后端是否接受任意 model 名) ---"
curl -s --max-time 90 -X POST http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"minimax-m2","messages":[{"role":"user","content":"Say OK"}],"max_tokens":8,"temperature":0}' \
  | head -c 500
echo; echo

echo "--- [2] python/venv/pip 基础设施 ---"
python3 --version
ls -d ~/hfenv ~/litellm-venv 2>/dev/null || echo "(hfenv/litellm-venv 目录探测)"
ls ~/hfenv/bin/ 2>/dev/null | head -8 || echo "hfenv 不存在或为空"
python3 -c "import venv; print('venv module OK')" 2>&1

echo "--- [3] litellm 版本发现 (tuna 镜像, 只查询不安装) ---"
python3 -m pip index versions litellm -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | head -4 || true

echo "--- [4] 端口 4000 占用检查 ---"
ss -tlnp 2>/dev/null | grep ':4000 ' || echo "4000 空闲"

echo "--- [5] 磁盘空间 (venv ~1-2G) ---"
df -h /home | tail -1
