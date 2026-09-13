#!/bin/bash
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
export https_proxy=http://127.0.0.1:7890 http_proxy=http://127.0.0.1:7890
cd /home/scott-lau/.hermes/hermes-agent
echo "=== uv 可用性 ==="
command -v uv && uv --version || echo "无 uv"
echo ""
echo "=== venv 结构 (有无 python/pip) ==="
ls venv/bin/ 2>/dev/null | head -20
echo ""
echo "=== 用 uv sync 带项目安装(editable生成入口) ==="
timeout 240 uv sync --all-groups --editable 2>&1 | tail -15 || {
  echo "editable 失败, 尝试 uv pip install -e"
  timeout 240 uv pip install -e . 2>&1 | tail -10
}
echo ""
echo "=== 确认 hermes 入口 ==="
ls -la venv/bin/hermes 2>/dev/null && echo OK || echo "仍无入口, 试 uv run"
echo ""
echo "=== 试 uv run hermes --version ==="
timeout 60 uv run hermes --version 2>&1 | head -3