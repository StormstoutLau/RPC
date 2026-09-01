#!/bin/bash
# B5q TDD — llama-serve-instance RPC_TARGET 哨兵语义测试 (契约 = DESIGN 决策 4)
# 三态: auto→展开 / 空→单机 / 显式→原样 (审计修正 #1 的防回归测试)
LSI="${LSI:-/usr/local/bin/llama-serve-instance}"
TMP="$(mktemp -d)"
LISTEN_PID=""
trap 'rm -rf "$TMP"; [ -n "$LISTEN_PID" ] && kill "$LISTEN_PID" 2>/dev/null' EXIT

PASS=0; FAIL=0
t() {
  local name="$1"; shift
  if ( "$@" ) >/dev/null 2>&1; then PASS=$((PASS+1)); echo "  ok   $name"
  else FAIL=$((FAIL+1)); echo "  FAIL $name"; fi
}

export CONF_DIR="$TMP/conf"
mkdir -p "$CONF_DIR" "$TMP/bin"
touch "$TMP/fake.gguf"

# stub llama-server: 记录实际参数 (验证真实命令行构造, 非验证 stub)
cat > "$TMP/bin/fake_server" <<EOF
#!/bin/bash
printf '%s\n' "\$*" > "$TMP/server_args"
exit 0
EOF
chmod +x "$TMP/bin/fake_server"
export LLAMA_SERVER_BIN="$TMP/bin/fake_server"

# PATH 注入 stub rpc-nodes (auto 展开来源)
cat > "$TMP/bin/rpc-nodes" <<EOF
#!/bin/bash
echo "127.0.0.1:25052"
EOF
chmod +x "$TMP/bin/rpc-nodes"
export PATH="$TMP/bin:$PATH"

# 真实监听端口 (wait-rpc 循环用真实 /dev/tcp 探测)
python3 -m http.server 25052 --bind 127.0.0.1 >/dev/null 2>&1 & LISTEN_PID=$!

mkconf() { # mkconf <rpc-target-value>
  cat > "$CONF_DIR/testm.env" <<EOF
MODEL_PATH=$TMP/fake.gguf
PORT=18080
CTX=1024
THREADS=1
N_CPU_MOE=0
RPC_TARGET=$1
EXTRA_FLAGS="-fa on"
EOF
}

echo "== llama-serve-instance 哨兵语义测试 =="

# T1 auto → 展开为 rpc-nodes 输出
mkconf "auto"; rm -f "$TMP/server_args"
"$LSI" testm >/dev/null 2>&1
t "auto-expands" grep -q -- "--rpc 127.0.0.1:25052" "$TMP/server_args"

# T2 空 → 单机 (不含 --rpc) — 审计修正 #1 防回归 (须断言 server 真被启动)
mkconf ""; rm -f "$TMP/server_args"
"$LSI" testm >/dev/null 2>&1
t "empty-stays-single" bash -c "[ -f '$TMP/server_args' ] && ! grep -q -- '--rpc' '$TMP/server_args'"

# T3 显式值 → 原样透传
mkconf "127.0.0.1:25052"; rm -f "$TMP/server_args"
"$LSI" testm >/dev/null 2>&1
t "explicit-passthrough" grep -q -- "--rpc 127.0.0.1:25052" "$TMP/server_args"

echo "rpc_target sentinel: pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]
