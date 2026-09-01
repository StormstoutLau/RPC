#!/bin/bash
# B5q TDD — rpc-nodes 单元测试 (RED 先行, 契约 = DESIGN §3)
# 隔离: NODES_ENV/RPC_SSH 环境注入; 127.0.0.1 真实监听端口做探测 (真实代码, 非 mock)
RPC_NODES_BIN="${RPC_NODES_BIN:-/usr/local/bin/rpc-nodes}"
TMP="$(mktemp -d)"
LISTEN_PID=""
trap 'rm -rf "$TMP"; [ -n "$LISTEN_PID" ] && kill "$LISTEN_PID" 2>/dev/null' EXIT

PASS=0; FAIL=0
t() { # t <name> <cmd...> 子 shell 执行, 断言退出码 0
  local name="$1"; shift
  if ( "$@" ) >/dev/null 2>&1; then PASS=$((PASS+1)); echo "  ok   $name"
  else FAIL=$((FAIL+1)); echo "  FAIL $name"; fi
}
start_listener() { # 起监听并等就绪 (消除测试竞态: 默认探测模式按设计单次尝试, --start 才重试)
  python3 -m http.server "$1" --bind 127.0.0.1 >/dev/null 2>&1 &
  LISTEN_PID=$!
  local i
  for i in $(seq 1 10); do
    (exec 3<>/dev/tcp/127.0.0.1/"$1") 2>/dev/null && return 0
    sleep 0.3
  done
  return 1
}

PORT1=25052; PORT2=25053
echo "RPC_NODES=\"127.0.0.1:${PORT1} 127.0.0.1:${PORT2}\"" > "$TMP/nodes.env"
echo "RPC_NODES=\"127.0.0.1:${PORT1}\"" > "$TMP/start.env"
export NODES_ENV="$TMP/nodes.env"

echo "== rpc-nodes 契约测试 =="

# T1 缺 nodes.env → 退出码 3 (fail-fast, 非静默)
t "missing-env-exit3" bash -c "NODES_ENV='$TMP/nonexistent.env' '$RPC_NODES_BIN' --all; [ \$? -eq 3 ]"

# T2 --all 原样输出声明清单 (单行空格分隔)
t "all-outputs-declared" test "$("$RPC_NODES_BIN" --all 2>/dev/null)" = "127.0.0.1:${PORT1} 127.0.0.1:${PORT2}"

# T3 全不可达 → 空输出 + 退出码 2
t "all-dead-exit2" bash -c "out=\$('$RPC_NODES_BIN' 2>/dev/null); rc=\$?; [ \$rc -eq 2 ] && [ -z \"\$out\" ]"

# T4 存活探测: 单节点活 → 输出该节点 + 退出码 0
start_listener "$PORT1"
t "probe-alive" test "$("$RPC_NODES_BIN" 2>/dev/null)" = "127.0.0.1:${PORT1}"

# T5 混合: 只输出存活节点
t "probe-mixed-only-alive" bash -c "out=\$('$RPC_NODES_BIN' 2>/dev/null); [ \"\$out\" = '127.0.0.1:${PORT1}' ]"

# T6/T7 --start/--stop 经 ssh 发 systemctl (stub ssh 记录调用; 节点用活端口使 --start 等待立即通过)
cat > "$TMP/fake_ssh" <<EOF
#!/bin/bash
echo "\$*" >> "$TMP/ssh_calls"
exit 0
EOF
chmod +x "$TMP/fake_ssh"
rm -f "$TMP/ssh_calls"
t "start-calls-systemctl" bash -c "NODES_ENV='$TMP/start.env' RPC_SSH='$TMP/fake_ssh' '$RPC_NODES_BIN' --start m27-q4ks && grep -q '127.0.0.1 sudo systemctl start rpc-server@m27-q4ks' '$TMP/ssh_calls'"
t "stop-calls-systemctl" bash -c "NODES_ENV='$TMP/start.env' RPC_SSH='$TMP/fake_ssh' '$RPC_NODES_BIN' --stop m27-q4ks && grep -q '127.0.0.1 sudo systemctl stop rpc-server@m27-q4ks' '$TMP/ssh_calls'"

echo "rpc-nodes: pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]
