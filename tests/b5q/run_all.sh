#!/bin/bash
# B5q TDD — 测试总入口
# 执行: bash run_all.sh (在 B 站; 环境缝隙见各测试文件头部)
DIR="$(cd "$(dirname "$0")" && pwd)"
TOTAL_FAIL=0
for tf in test_rpc_nodes.sh test_bench_cluster.sh test_rpc_target.sh test_b5k_verify.sh test_sync_dir.sh; do
  echo "----------------------------------------"
  bash "$DIR/$tf" || TOTAL_FAIL=$((TOTAL_FAIL+1))
done
echo "========================================"
if [ "$TOTAL_FAIL" -eq 0 ]; then echo "ALL SUITES GREEN"; exit 0
else echo "$TOTAL_FAIL SUITE(S) FAILING"; exit 1; fi
