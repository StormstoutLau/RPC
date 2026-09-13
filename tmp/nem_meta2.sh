#!/bin/bash
# 尝试用 python gguf 读取 nemotron 元数据数值
set +e
M=/data/models/gguf/lmstudio-community/NVIDIA-Nemotron-3-Super-120B-A12B-GGUF/NVIDIA-Nemotron-3-Super-120B-A12B-Q4_K_M-00001-of-00003.gguf
python3 - <<PYEOF 2>/dev/null || echo "PY_GGUF_FAIL; fallback 用文件头解析"
import sys
try:
    from gguf import GGUFReader
except ImportError:
    sys.exit(1)
r = GGUFReader("$M")
keys = ['nemotron_h_moe.block_count','nemotron_h_moe.context_length','nemotron_h_moe.embedding_length',
        'nemotron_h_moe.attention.head_count','nemotron_h_moe.attention.head_count_kv',
        'nemotron_h_moe.expert_used_count','nemotron_h_moe.expert_count','nemotron_h_moe.expert_shared_count',
        'nemotron_h_moe.attention.key_length','nemotron_h_moe.attention.value_length']
for k in keys:
    try:
        f = r.get_field(k)
        print(k, '=', f.contents if hasattr(f,'contents') else f.data.tolist() if hasattr(f,'data') else f)
    except Exception:
        pass
PYEOF
echo "---"
# fallback: 直接 bin 读取 GGUF KV (用 strings + context)
echo "=== fallback: strings 提取数值上下文 ==="
for pat in 'block_count' 'head_count_kv' 'context_length' 'embedding_length' 'key_length' 'value_length' 'expert_count'; do
  echo "[$pat]"
  strings -n 4 "$M" 2>/dev/null | grep "$pat" | head -2
done
echo "DONE"