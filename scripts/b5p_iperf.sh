#!/bin/bash
# B5p: 40G 新线 iperf3 带宽测试 (基线: 20G 线 ~9.4Gbps)
S=10.10.10.1   # A 站

run() {
  local label="$1"; shift
  echo "=== $label ==="
  iperf3 -c "$S" "$@" -t 8 2>&1 | tail -4
  echo
}

run "B→A 单流"
run "A→B 单流 (-R)" -R
run "B→A 4 并行" -P 4
run "A→B 4 并行 (-R)" -R -P 4
