#!/bin/bash
# rpccache_gen.sh — A 站 rpccache 代际分析
systemctl is-active rpc-server.service
echo "---"
sudo find /data/rpccache/m27-q4ks/rpc -newermt '2026-08-29' -printf '%s\n' 2>/dev/null | awk '{s+=$1} END {printf "新代(8/29后): %.0fG\n", s/1073741824}'
sudo find /data/rpccache/m27-q4ks/rpc ! -newermt '2026-08-29' -printf '%s\n' 2>/dev/null | awk '{s+=$1} END {printf "旧代(8/29前): %.0fG\n", s/1073741824}'
echo "--- deepseek 同样分析 ---"
sudo find /data/rpccache/deepseek-v4-flash-0731/rpc -newermt '2026-08-31' -printf '%s\n' 2>/dev/null | awk '{s+=$1} END {printf "深seek 新代(8/31后): %.0fG\n", s/1073741824}'
sudo find /data/rpccache/deepseek-v4-flash-0731/rpc ! -newermt '2026-08-31' -printf '%s\n' 2>/dev/null | awk '{s+=$1} END {printf "深seek 旧代(8/31前): %.0fG\n", s/1073741824}'
