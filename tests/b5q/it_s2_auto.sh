#!/bin/bash
# B5q §2.2 补: auto 哨兵全链集成验证 (小模型 24M, 不扰生产) + conf 零破坏 diff
set -uo pipefail

echo '--- B 站 MiniLM 路径 ---'
MINILM=$(find -L /data/models/gguf -path '*MiniLM*' -name '*.gguf' 2>/dev/null | head -1)
echo "$MINILM"

echo '--- 1. 临时 conf (RPC_TARGET=auto) ---'
sudo tee /etc/llama-instances/b5qtest.env > /dev/null <<EOF
MODEL_PATH=${MINILM}
PORT=18080
CTX=2048
THREADS=2
N_CPU_MOE=0
RPC_TARGET=auto
EXTRA_FLAGS="--embedding"
EOF
cat /etc/llama-instances/b5qtest.env | grep RPC_TARGET

echo '--- 2. systemd 启动 (真实链: conf→unit→LSI wrapper→rpc-nodes→llama-server) ---'
sudo systemctl start llama-server@b5qtest
for i in $(seq 1 30); do
  systemctl is-active --quiet llama-server@b5qtest && break
  sleep 1
done
echo "unit: $(systemctl is-active llama-server@b5qtest)"

echo '--- 3. ps 验证 auto 展开 (--rpc 应=10.10.10.1:50052, 来自真实 rpc-nodes/nodes.env) ---'
sleep 2
ps -eo args | grep 'llama-server' | grep -v grep | grep b5qtest | head -1
ps -eo args | grep '/opt/llama.cpp/llama-server' | grep -v grep | grep -E '18080' | head -1

echo '--- 4. 端口可服务 (embedding API 冒烟) ---'
sleep 2
curl -s -m 10 http://127.0.0.1:18080/embedding -d '{"content":"hello"}' | head -c 120; echo

echo '--- 5. 清理 ---'
sudo systemctl stop llama-server@b5qtest
sudo rm /etc/llama-instances/b5qtest.env
echo "cleaned: $(systemctl is-active llama-server@b5qtest) / conf gone: $([ ! -f /etc/llama-instances/b5qtest.env ] && echo yes)"

echo '--- 6. infer-load 硬编码清除验证 ---'
grep -n '10.10.10.1' /usr/local/bin/infer-load || echo '(无残留字面量 ✓)'

echo '--- 7. conf 零破坏 diff (vs pre-flight 快照; 预期: m27/gpt-oss 等均不变) ---'
SNAP=$(ls -d /tmp/llama-instances.bak.* | sort | tail -1)
echo "snapshot: $SNAP"
sudo diff -r "$SNAP" /etc/llama-instances && echo '(逐字节一致 ✓)' || echo '(有差异 — 见上)'

echo '--- 8. gpt-oss-120b 空值单机确认 (未翻转) ---'
grep RPC_TARGET /etc/llama-instances/gpt-oss-120b.env
