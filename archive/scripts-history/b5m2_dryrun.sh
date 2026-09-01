#!/bin/bash
# b5m2_dryrun.sh — B5m2 干跑侦察 (只读): .incomplete 明细 / M2.7 双副本 / AWQ 目录结构
set -uo pipefail
echo "=== HOST ==="; hostname

echo "=== 1. .incomplete 全明细 (bytes|path) ==="
for base in /data/models "$HOME/models"; do
  [ -d "$base" ] || continue
  find "$base" -name '*.incomplete' -printf '%s|%p\n' 2>/dev/null | sort -t'|' -k2
done

echo "=== 2. .cache 目录还有什么 (非 .incomplete 文件) ==="
for d in /data/models/MiniMax-M2.7-AWQ-G32-STRIX-2H/.cache "$HOME/models/MiniMax-M2.7-AWQ-G32-STRIX-2H/.cache"; do
  [ -d "$d" ] || continue
  echo "--- $d ---"
  find "$d" -type f ! -name '*.incomplete' -printf '%s|%p\n' 2>/dev/null | head -10
  echo "subdirs: $(find "$d" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | tr '\n' ' ')"
done

echo "=== 3. AWQ 目录顶层 (排除 .cache) ==="
for d in /data/models/MiniMax-M2.7-AWQ-G32-STRIX-2H "$HOME/models/MiniMax-M2.7-AWQ-G32-STRIX-2H"; do
  [ -d "$d" ] || continue
  echo "--- $d ---"
  ls "$d" | grep -v '^\.cache$' | head -5
  echo "model files: $(find "$d" -maxdepth 1 -name 'model-*.safetensors' | wc -l), config: $(ls "$d"/config.json 2>/dev/null || echo MISSING)"
done

echo "=== 4. B 站: M2.7 双副本 + 服务指向 ==="
if [ "$(hostname -s)" = "scott-lau-GTR-Pro" ]; then
  for f in "$HOME/.lmstudio/models/llmfan46/MiniMax-M2.7-ultra-uncensored-heretic-GGUF/MiniMax-M2.7-BF16-ultra-uncensored-heretic-Q4_K_S.gguf" \
           "$HOME/.lmstudio/models/lmstudio-community/MiniMax-M2.7-GGUF/MiniMax-M2.7-Q4_K_M-merged.gguf"; do
    [ -f "$f" ] && echo "EXISTS|$(stat -c %s "$f")|$f" || echo "ABSENT|$f"
  done
  echo "--- llama-server service ExecStart ---"
  systemctl cat llama-server 2>/dev/null | grep -E '^ExecStart' || echo "SERVICE_UNIT_NOT_READABLE"
  echo "--- llama-server active? ---"
  systemctl is-active llama-server 2>/dev/null || true
fi

echo "=== 5. df before ==="
df -h / | tail -1
echo "=== B5M2_DRYRUN_DONE ==="
