#!/bin/bash
# a4_verify_model.sh — 两站模型完整性核对: 文件数/字节数/清单MD5
# 用法: bash a4_verify_model.sh  (各站本地运行, 输出可直接对比)
set -uo pipefail
case "$(hostname -s)" in
  *NEX*|*nex*) DIR=/data/models/MiniMax-M2.7-AWQ-G32-STRIX-2H ;;
  *)           DIR=/home/scott-lau/models/MiniMax-M2.7-AWQ-G32-STRIX-2H ;;
esac
[ -d "$DIR" ] || { echo "MODEL_DIR_MISSING: $DIR"; exit 1; }
cd "$DIR"
echo "n_files: $(ls -1 | wc -l)"
echo "total_bytes: $(cat * 2>/dev/null | wc -c)" > /dev/null  # 不要真cat, 换du
echo "total_bytes_du: $(du -sb . | cut -f1)"
echo "total_bytes_ls: $(ls -l --block-size=1 | grep -v '^total' | grep -v '^d' | awk '{s+=$5} END {print s+0}')"
ls -1 | sort | md5sum | awk '{print "list_md5:", $1}'
# 每文件字节清单的MD5 (名+大小), 两站应一致
for f in $(ls -1 | sort); do printf '%s %s\n' "$f" "$(stat -c%s "$f")"; done | md5sum | awk '{print "filesig_md5:", $1}'
# 关键小文件抽查
for f in config.json tokenizer.json tokenizer_config.json model.safetensors.index.json generation_config.json; do
  [ -f "$f" ] && echo "$f: $(stat -c%s "$f") bytes" || echo "$f: MISSING"
done
echo "VERIFY_DONE"
