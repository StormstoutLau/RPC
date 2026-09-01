#!/bin/bash
# B5q TDD — b5k_sync manifest/verify 函数测试 (契约 = DESIGN §6)
# 本地函数层; 双端远程路径由 CHECKLIST §4 集成覆盖 (声明)
B5K="${B5K:-/home/scott-lau/scripts/b5k_sync.sh}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PASS=0; FAIL=0
t() {
  local name="$1"; shift
  if ( "$@" ) >/dev/null 2>&1; then PASS=$((PASS+1)); echo "  ok   $name"
  else FAIL=$((FAIL+1)); echo "  FAIL $name"; fi
}

# 测试模型目录 (2 个假 .gguf)
MDIR="$TMP/root/publisher/model"
mkdir -p "$MDIR"
printf 'AAAA%.0s' {1..1024} > "$MDIR/part-00001-of-00002.gguf"
printf 'BBBB%.0s' {1..1024} > "$MDIR/part-00002-of-00002.gguf"

echo "== b5k_sync manifest/verify 函数测试 =="

# T1 可 source (main 有 guard, source 不触发网络同步逻辑)
t "sourceable-without-exec" bash -c "MODEL_ROOT='$TMP/root' A_HOST=127.0.0.1 bash -c \"source '$B5K' && echo AFTER_SOURCE\" | grep -q AFTER_SOURCE"

# T2 gen_manifest 生成 .sha256 (2 行, sha256sum -c 兼容)
t "gen-manifest" bash -c "MODEL_ROOT='$TMP/root' A_HOST=127.0.0.1 bash -c \"source '$B5K'; gen_manifest '$MDIR'\" && [ \$(wc -l < '$MDIR/.sha256') -eq 2 ] && (cd '$MDIR' && sha256sum -c .sha256)"

# T3 verify_dir 完整目录 → 退出 0
t "verify-intact" bash -c "MODEL_ROOT='$TMP/root' A_HOST=127.0.0.1 bash -c \"source '$B5K'; verify_dir '$MDIR'\""

# T4 篡改 → 非零退出 + 报错点名该文件 (B5m1/7.11 教训: 显式暴露)
printf 'X' | dd of="$MDIR/part-00001-of-00002.gguf" bs=1 seek=0 conv=notrunc 2>/dev/null
t "tamper-named-and-fails" bash -c "out=\$(MODEL_ROOT='$TMP/root' A_HOST=127.0.0.1 bash -c \"source '$B5K'; verify_dir '$MDIR'\" 2>&1); rc=\$?; [ \$rc -ne 0 ] && echo \"\$out\" | grep -q 'part-00001'"

# T5 默认 A_HOST = mDNS 名 (IP 漂移免疫范式, 2026-08-31 验收实锤: A 11→33 漂移致管理网不可达)
t "default-host-is-mdns" bash -c "v=\$(MODEL_ROOT='$TMP/root' bash -c \"source '$B5K'; echo \\\$A_HOST\"); echo \"\$v\" | grep -q 'scott-lau-nex.local'"

echo "b5k_verify: pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]
