#!/bin/bash
# B5q TDD — b5k sync_dir 父目录 bug 回归测试 (集成层发现: code 11 mkdir failed)
# 契约: sync_dir <src_dir> [dst_dir] — 先 mkdir -p dst (含父目录) 再 rsync
#   dst 缺省 = src (A/B 同 MODEL_ROOT 路径约定); src/dst 分离供测试注入
B5K="${B5K:-/home/scott-lau/scripts/b5k_sync.sh}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0
t() { local n="$1"; shift
  if ( "$@" ) >/dev/null 2>&1; then PASS=$((PASS+1)); echo "  ok   $n"
  else FAIL=$((FAIL+1)); echo "  FAIL $n"; fi }

# A 侧: src/publisher/model/m.gguf (真实文件, 经 127.0.0.1 sshd rsync)
mkdir -p "$TMP/src/publisher/model"
printf 'X%.0s' {1..2048} > "$TMP/src/publisher/model/m.gguf"
# B 侧: dst 根存在但 publisher/ 不存在 (复现父目录缺失)
mkdir -p "$TMP/dst"
# 预热: localhost host key 收录 (rsync over ssh 前置; 测试环境依赖非实现缺陷)
ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes -o ConnectTimeout=3 127.0.0.1 true 2>/dev/null || true

echo "== sync_dir 父目录测试 =="
# T1 双参: B 侧父目录不存在 → mkdir 后 rsync 成功, 文件落位
t "sync-dir-creates-parent" bash -c "MODEL_ROOT='$TMP/src' A_HOST=127.0.0.1 bash -c \"
  source '$B5K'
  sync_dir '$TMP/src/publisher/model' '$TMP/dst/publisher/model'
\" && [ -f '$TMP/dst/publisher/model/m.gguf' ]"

# T2 单参缺省: dst = src 路径 (同路径约定, mkdir 幂等不破坏已有内容)
t "sync-dir-default-dst" bash -c "MODEL_ROOT='$TMP/src' A_HOST=127.0.0.1 bash -c \"
  source '$B5K'
  sync_dir '$TMP/src/publisher/model'
\" && [ -f '$TMP/src/publisher/model/m.gguf' ]"

# T3 内容保真: rsync 后 dst 文件 sha256 与源一致
t "sync-dir-content-fidelity" bash -c "MODEL_ROOT='$TMP/src' A_HOST=127.0.0.1 bash -c \"
  source '$B5K'
  sync_dir '$TMP/src/publisher/model' '$TMP/dst2/publisher/model'
\" && [ \"\$(sha256sum '$TMP/src/publisher/model/m.gguf' | cut -d' ' -f1)\" = \"\$(sha256sum '$TMP/dst2/publisher/model/m.gguf' | cut -d' ' -f1)\" ]"

echo "sync_dir: pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]
