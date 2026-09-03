#!/bin/bash
set -e
SRC=/usr/local/bin/infer-list
# 备份
sudo cp "$SRC" "$SRC.bak-unsloth-20260904"
# 修改建议后端逻辑: 默认 unsloth (除 vllm/embedding)
sudo python3 - "$SRC" <<'PY'
import sys,re
p=sys.argv[1]
s=open(p).read()
old='''  case "$a" in
    m27-awq) BE="vllm" ;;
    all-minilm*) BE="llama-emb" ;;
    *) if [ "$sz" -gt 66560 ]; then BE="llama-rpc"; else BE="llama-single"; fi ;;
  esac'''
new='''  case "$a" in
    m27-awq) BE="vllm" ;;
    all-minilm*) BE="llama-emb" ;;
    *) BE="unsloth" ;;
  esac'''
assert old in s, "pattern not found"
open(p,'w').write(s.replace(old,new))
print("infer-list 建议后端 -> unsloth (默认)")
PY
sudo chmod 755 "$SRC"
echo "== 冒烟 =="
/usr/local/bin/infer-list 2>&1 | head -10
echo "== 哈希 =="
md5sum "$SRC"