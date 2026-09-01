#!/bin/bash
# B 站物理库补删 (软链视图已删, .lmstudio 物理文件残留) + Trash 核查
set -u
echo "=== 删除前 ==="
df -h /data | tail -1

echo "=== 1. 物理残留确认 (大小) ==="
sudo du -smL /home/scott-lau/.lmstudio/models/llmfan46/MiniMax-M2.7-ultra-uncensored-heretic-GGUF 2>/dev/null
sudo du -smL /home/scott-lau/.lmstudio/models/chatqaq/Qwen3.6-27B-Claude-Mythos-Distilled-MTP-GGUF 2>/dev/null
sudo du -smL /home/scott-lau/.lmstudio/models/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF 2>/dev/null

echo "=== 2. HauhauCS 物理库全部内容 (确认无其他保留项) ==="
ls /home/scott-lau/.lmstudio/models/HauhauCS/ 2>/dev/null
echo "--- llmfan46 ---"
ls /home/scott-lau/.lmstudio/models/llmfan46/ 2>/dev/null
echo "--- chatqaq ---"
ls /home/scott-lau/.lmstudio/models/chatqaq/ 2>/dev/null

echo "=== 3. 删物理文件 ==="
sudo rm -rf /home/scott-lau/.lmstudio/models/llmfan46/MiniMax-M2.7-ultra-uncensored-heretic-GGUF
sudo rm -rf /home/scott-lau/.lmstudio/models/chatqaq/Qwen3.6-27B-Claude-Mythos-Distilled-MTP-GGUF
sudo rm -rf /home/scott-lau/.lmstudio/models/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF
echo "rc=$?"
# publisher 空目录
for pub in llmfan46 chatqaq HauhauCS; do
  sudo rmdir /home/scott-lau/.lmstudio/models/$pub 2>/dev/null && echo "$pub/ 空目录已删" || echo "$pub/ 非空保留: $(ls /home/scott-lau/.lmstudio/models/$pub 2>/dev/null | tr '\n' ' ')"
done

echo "=== 4. B 站 Trash 核查 (GUI 删除≠释放教训) ==="
sudo du -sm /home/scott-lau/.local/share/Trash 2>/dev/null || echo "(无 Trash)"
sudo ls /home/scott-lau/.local/share/Trash/files/ 2>/dev/null | head -8

echo "=== 5. .lmstudio 剩余总量 ==="
sudo du -sm /home/scott-lau/.lmstudio/models 2>/dev/null

echo "=== 6. 残留模型清单 (物理库现存 repo) ==="
sudo find /home/scott-lau/.lmstudio/models -maxdepth 2 -type d -name "*GGUF*" 2>/dev/null | head -20

echo "=== 7. 删除后 ==="
df -h /data | tail -1
echo DONE_B2
