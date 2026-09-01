#!/bin/bash
# B 站: 盘点删除目标 + nemotron conf + litellm 配置定位
set -u
echo "=== 1. 三个 qwen 蒸馏 repo ==="
for pat in "Qwen3.5-122B-A10B-Uncensored*" "Qwen3.6-27b*" "Qwen3.8-27b*"; do
  find /data/models/gguf -maxdepth 2 -iname "$pat" -type d 2>/dev/null | while read -r d; do
    echo "$d -> $(sudo du -smL "$d" 2>/dev/null | cut -f1)M"
  done
done
echo "=== 2. MiniMax GGUF (llmfan46) ==="
ls -d /data/models/gguf/llmfan46/MiniMax* 2>/dev/null
sudo du -smL /data/models/gguf/llmfan46/ 2>/dev/null
echo "=== 3. MiniMax AWQ (vLLM) ==="
ls -d /data/models/MiniMax* 2>/dev/null
sudo du -smL /data/models/MiniMax-AWQ 2>/dev/null
echo "=== 4. 相关 confs ==="
ls /etc/llama-instances/ | grep -iE "qwen3.5-122b|qwen3.6-27b|qwen3.8-27b|m27"
echo "=== 5. nemotron conf (ctx/参数) ==="
cat /etc/llama-instances/nvidia-nemotron-3-super-120b-a12b.env 2>/dev/null
echo "=== 6. litellm 配置定位 ==="
systemctl cat litellm 2>/dev/null | grep -E "ExecStart|WorkingDir" | head -3
sudo find /etc /opt /home/scott-lau -maxdepth 3 -name "*.yaml" -path "*litellm*" 2>/dev/null | head -3
echo "=== 7. litellm 配置中的 minimax 引用 ==="
sudo grep -rl "minimax-m2" /etc/litellm* /opt/litellm* 2>/dev/null | head -3
echo "=== 8. nemotron 架构确认 (GGUF 元数据) ==="
sudo journalctl -u llama-server@nvidia-nemotron-3-super-120b-a12b --no-pager 2>/dev/null | grep -iE "arch|KV|kv_cache|n_ctx" | head -8
echo DONE_B
