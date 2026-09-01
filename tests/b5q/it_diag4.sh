#!/bin/bash
# B5q §4 诊断: 4 个 rsync 后不存在的目录
echo '--- B 站磁盘 ---'
df -h /data | tail -1
echo '--- B 端 4 目录状态 ---'
for d in mradermacher/Qwen3.5-122B-A10B-Claude-Distill-v2-i1-GGUF mudler/Qwen3.6-35B-A3B-Claude-4.7-Opus-Reasoning-Distilled-APEX-GGUF TeichAI/gemma-4-31B-it-Claude-Opus-Distill-v2-GGUF TeichAI/Qwen3-14B-GPT-5.2-High-Reasoning-Distill-GGUF; do
  ls -ld "/data/models/gguf/$d" 2>&1 | head -1
done
echo '--- A 端 4 目录 (类型/大小) ---'
ssh 10.10.10.1 'for d in mradermacher/Qwen3.5-122B-A10B-Claude-Distill-v2-i1-GGUF mudler/Qwen3.6-35B-A3B-Claude-4.7-Opus-Reasoning-Distilled-APEX-GGUF TeichAI/gemma-4-31B-it-Claude-Opus-Distill-v2-GGUF TeichAI/Qwen3-14B-GPT-5.2-High-Reasoning-Distill-GGUF; do ls -ld "/data/models/gguf/$d"; du -smL "/data/models/gguf/$d" | cut -f1; done'
echo '--- 手动 rsync 试一个 (gemma, 看真实报错) ---'
rsync -aP --partial --info=progress2 "10.10.10.1:/data/models/gguf/TeichAI/gemma-4-31B-it-Claude-Opus-Distill-v2-GGUF/" "/data/models/gguf/TeichAI/gemma-4-31B-it-Claude-Opus-Distill-v2-GGUF/" 2>&1 | tail -5
