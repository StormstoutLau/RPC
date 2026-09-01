#!/usr/bin/env bash
# lm_verify.sh — 清理后验证: json 有效 + 模型文件完整
set -u
python3 <<'EOF'
import json
d = json.load(open("/home/scott-lau/.lmstudio/.internal/download-jobs-info.json"))
jobs = d.get("jobs", [])
print("jobs 数:", len(jobs))
print("顶层 keys:", sorted(d.keys()))
EOF
echo "--- DeepSeek (应 4 分片, 无 .part) ---"
ls /home/scott-lau/.lmstudio/models/lmstudio-community/DeepSeek-V4-Flash-0731-GGUF/
echo "--- GLM (应 5 分片+mmproj, 无 .part) ---"
ls /home/scott-lau/.lmstudio/models/unsloth/GLM-5.3-Flash-GGUF/
echo "--- Qwen 两目录 (应各 1-2 文件, 无 .part) ---"
ls /home/scott-lau/.lmstudio/models/chatqaq/Qwen3.6-27B-Claude-Mythos-Distilled-MTP-GGUF/
ls /home/scott-lau/.lmstudio/models/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF/
echo "--- 全 models 树下残留 .part (应为空) ---"
find /home/scott-lau/.lmstudio/models -name "*.part" -o -name "downloading_*" 2>/dev/null
echo "VERIFY_DONE"
