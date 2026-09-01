#!/bin/bash
# share_dir_survey.sh — 共享模型目录可行性调研 (B 站侧)
echo "=== [1] infer-* 工具位置与类型 ==="
ls -la /usr/local/bin/infer-* 2>/dev/null
echo
echo "=== [2] infer-list 扫描路径 (源码中路径相关行) ==="
for f in /usr/local/bin/infer-list /usr/local/bin/infer-load; do
  if [ -f "$f" ]; then
    echo "--- $f (file type: $(file -b $f | cut -c1-40)) ---"
    grep -nE 'lmstudio|/data|SCAN|MODELS_|scan|models' "$f" 2>/dev/null | head -25
  fi
done
echo
echo "=== [3] infer 相关 lib/共享脚本 ==="
ls /usr/local/lib/infer* /etc/llama-instances/ 2>/dev/null | head -20
grep -rnE 'lmstudio|/data/models' /usr/local/lib/infer* 2>/dev/null | head -20
echo
echo "=== [4] LM Studio 配置 (模型目录) ==="
cat ~/.lmstudio/settings.json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
def walk(o,p=''):
    if isinstance(o,dict):
        for k,v in o.items(): walk(v,f'{p}.{k}')
    elif isinstance(o,list):
        for i,v in enumerate(o): walk(v,f'{p}[{i}]')
    else:
        s=str(o)
        if any(w in p.lower() for w in ('dir','path','model','download','root')) or '/data' in s or 'models' in s.lower():
            print(f'{p} = {s[:120]}')
walk(d)" 2>/dev/null || echo "(settings.json 解析失败)"
echo "--- lms CLI 目录查询 ---"
which lms 2>/dev/null && lms ls --paths 2>/dev/null | head -5
echo
echo "=== [5] ~/.lmstudio 内 .internal/目录配置文件 ==="
find ~/.lmstudio -maxdepth 2 -name "*.json" -not -path "*/models/*" 2>/dev/null | head -10
echo
echo "=== [6] vLLM AWQ 路径引用 (a4 脚本) ==="
grep -nE 'AWQ|models|MODEL' ~/scripts/a4_vllm_launch.sh 2>/dev/null | head -15
ls -la /data/models/MiniMax-M2.7-AWQ-G32-STRIX-2H 2>/dev/null
ls ~/models/ 2>/dev/null
