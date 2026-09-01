#!/bin/bash
# B5q TDD — b5_bench_cluster.sh 单元测试 (契约 = DESIGN §4)
# 隔离: CONF_DIR/LOG_DIR/RPC_HELPER/BENCH_BIN 环境注入 (stub 只替换外部副作用源)
BENCH_SCRIPT="${BENCH_SCRIPT:-/usr/local/bin/b5_bench_cluster.sh}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PASS=0; FAIL=0
t() {
  local name="$1"; shift
  if ( "$@" ) >/dev/null 2>&1; then PASS=$((PASS+1)); echo "  ok   $name"
  else FAIL=$((FAIL+1)); echo "  FAIL $name"; fi
}

export CONF_DIR="$TMP/conf" LOG_DIR="$TMP/logs"
mkdir -p "$CONF_DIR" "$TMP/bin" "$LOG_DIR"

# stub rpc-helper: 记录调用; --start 输出 RPC 列表 (rc 可注入模拟故障)
cat > "$TMP/bin/rpc-helper" <<EOF
#!/bin/bash
echo "\$*" >> "$TMP/rpc_calls"
case "\$1" in
  --start) echo "127.0.0.1:25052"; exit \${STUB_START_RC:-0} ;;
  --stop)  exit 0 ;;
esac
exit 1
EOF
chmod +x "$TMP/bin/rpc-helper"
export RPC_HELPER="$TMP/bin/rpc-helper"

# stub llama-bench: 记录实际收到的参数
cat > "$TMP/bin/fake_bench" <<EOF
#!/bin/bash
printf '%s\n' "\$*" > "$TMP/bench_args"
echo "fake bench output pp512=141.4 tn128=20.9"
EOF
chmod +x "$TMP/bin/fake_bench"
export BENCH_BIN="$TMP/bin/fake_bench"

echo "MODEL_PATH=$TMP/fake.gguf" > "$CONF_DIR/m27-q4ks.env"
touch "$TMP/fake.gguf"

echo "== b5_bench_cluster 契约测试 =="

# T1 conf 不存在 → 报错退出 3 (确定性, 不模糊 find — DESIGN §4 修正)
t "missing-conf-exit3" bash -c "'$BENCH_SCRIPT' --alias no-such-model; [ \$? -eq 3 ]"

# T2 正常流程 → 退出 0
t "happy-path-exit0" "$BENCH_SCRIPT" --alias m27-q4ks

# T3 冻结口径逐参断言 (DESIGN §2.8)
for param in "-ngl 999" "-t 16" "-b 512" "--n-cpu-moe 8" "-fa on" "-p 512" "-n 128" "-r 2" "--rpc 127.0.0.1:25052" "-m $TMP/fake.gguf"; do
  t "frozen-param: $param" grep -q -- "$param" "$TMP/bench_args"
done

# T4 默认自动收尾 (--stop 被调用)
t "auto-stop-default" grep -q -- "--stop m27-q4ks" "$TMP/rpc_calls"

# T5 --keep 不收尾
rm -f "$TMP/rpc_calls" "$TMP/bench_args"
"$BENCH_SCRIPT" --alias m27-q4ks --keep >/dev/null 2>&1
t "keep-no-stop" bash -c "! grep -q -- '--stop' '$TMP/rpc_calls' 2>/dev/null && grep -q -- '--start m27-q4ks' '$TMP/rpc_calls'"

# T6 rpc 起不来 → 非零退出 且 仍收尾 (abort + cleanup)
rm -f "$TMP/rpc_calls" "$TMP/bench_args"
t "start-fail-abort-and-cleanup" bash -c "STUB_START_RC=1 '$BENCH_SCRIPT' --alias m27-q4ks; rc=\$?; [ \$rc -ne 0 ] && grep -q -- '--stop m27-q4ks' '$TMP/rpc_calls'"

# T7 日志双落 (LOG_DIR 内含完整 bench 输出)
t "log-file-contains-output" bash -c "grep -q 'fake bench output' '$TMP'/logs/bench_cluster_m27-q4ks_*.log"

# T8 metrics 条目 (Phase 5 + alias + 日期)
t "metrics-entry" bash -c "'$BENCH_SCRIPT' --alias m27-q4ks 2>&1 | grep -E 'Phase 5.*m27-q4ks.*rpc='"

echo "b5_bench_cluster: pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]
