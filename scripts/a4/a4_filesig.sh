#!/bin/bash
# a4_filesig.sh — 输出 每文件名+字节 清单 (两站 diff 用)
set -uo pipefail
case "$(hostname -s)" in
  *NEX*|*nex*) DIR=/data/models/MiniMax-M2.7-AWQ-G32-STRIX-2H ;;
  *)           DIR=/home/scott-lau/models/MiniMax-M2.7-AWQ-G32-STRIX-2H ;;
esac
cd "$DIR" || exit 1
for f in $(ls -1 | sort); do printf '%s %s\n' "$f" "$(stat -c%s "$f")"; done
echo "FILESIG_DONE"
