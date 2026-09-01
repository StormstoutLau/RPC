#!/bin/bash
# B 站批量删除 (2026-09-01 用户裁决: 3 qwen 蒸馏 + MiniMax GGUF + MiniMax AWQ)
set -u
echo "=== 删除前 ==="
df -h /data | tail -1

echo "=== 0. 前置安全: 无运行实例 ==="
pgrep -af "llama-server|rpc-server" | grep -v grep || echo "(无进程, 安全)"

echo "=== 1. HauhauCS 目录内容 (确认只删目标) ==="
ls /data/models/gguf/HauhauCS/
echo "--- chatqaq 目录内容 ---"
ls /data/models/gguf/chatqaq/

echo "=== 2. 删 3 个 qwen 蒸馏 repo ==="
sudo rm -rf /data/models/gguf/HauhauCS/Qwen3.5-122B-A10B-Uncensored-HauhauCS-Aggressive
sudo rm -rf /data/models/gguf/chatqaq/Qwen3.6-27B-Claude-Mythos-Distilled-MTP-GGUF
sudo rm -rf /data/models/gguf/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF
echo "rc=$?"
# publisher 空目录清理 (非空自动跳过)
sudo rmdir /data/models/gguf/HauhauCS 2>/dev/null && echo "HauhauCS/ 空目录已删" || echo "HauhauCS/ 非空保留: $(ls /data/models/gguf/HauhauCS 2>/dev/null | tr '\n' ' ')"
sudo rmdir /data/models/gguf/chatqaq 2>/dev/null && echo "chatqaq/ 空目录已删" || echo "chatqaq/ 非空保留: $(ls /data/models/gguf/chatqaq 2>/dev/null | tr '\n' ' ')"

echo "=== 3. 删 MiniMax GGUF (llmfan46 整目录) ==="
sudo rm -rf /data/models/gguf/llmfan46
echo "rc=$?"

echo "=== 4. 删 MiniMax AWQ (vLLM) ==="
sudo rm -rf /data/models/MiniMax-M2.7-AWQ-G32-STRIX-2H
echo "rc=$?"

echo "=== 5. 删 4 个 conf ==="
sudo rm -f /etc/llama-instances/qwen3.5-122b-a10b-uncensored-hauhaucs-aggressive.env
sudo rm -f /etc/llama-instances/qwen3.6-27b-claude-mythos-distilled-mtp.env
sudo rm -f /etc/llama-instances/qwen3.8-27b-uncensored-hauhaucs-aggressive-mtp.env
sudo rm -f /etc/llama-instances/m27-q4ks.env
echo "rc=$?"

echo "=== 6. 死链复查 ==="
find /data/models/gguf -xtype l 2>/dev/null | head -5
echo "死链数: $(find /data/models/gguf -xtype l 2>/dev/null | wc -l)"

echo "=== 7. infer-list 复核 (删除项应消失) ==="
infer-list 2>/dev/null | grep -iE "m27|qwen3.5-122b|qwen3.6-27b|qwen3.8-27b|nemotron" || echo "(全部消失)"

echo "=== 8. 删除后 ==="
df -h /data | tail -1
echo DONE_B_DEL
