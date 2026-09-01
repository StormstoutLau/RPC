#!/bin/bash
# B5k: A-only 模型同步工具 (B 站拉取 A 站, 因 B→A ssh 互通已由 infer-load 验证)
# 用法:
#   b5k_sync.sh            — dry-run, 显示差异 (A-only 可同步 / B-only 信息)
#   b5k_sync.sh --go       — 实际 rsync A-only 模型 → B 站
#   b5k_sync.sh --go --usb4 — 走 USB4 网 (10.10.10.1, 闲时快, 默认走管理网 192.168.1.11)
#   b5k_sync.sh --go --verify — 同步后双端 sha256 校验 (B5q-3, DESIGN §6)
# 测试缝隙: MODEL_ROOT / A_HOST (tests/b5q/test_b5k_verify.sh)
set -uo pipefail
MODEL_ROOT="${MODEL_ROOT:-/data/models/gguf}"
A_MGMT="scott-lau-nex.local"  # mDNS (IP 漂移免疫; 2026-08-31 实锤: A 11→33 漂移致裸 IP 不可达)
A_USB4="10.10.10.1"
A_HOST="${A_HOST:-$A_MGMT}"

GO=0; USB4=0; VERIFY=0
for a in "$@"; do
  case "$a" in
    --go)     GO=1 ;;
    --usb4)   USB4=1 ;;
    --verify) VERIFY=1 ;;
    *) echo "FATAL: 未知参数: $a" >&2; exit 3 ;;
  esac
done
[ "$USB4" = "1" ] && [ "$A_HOST" = "$A_MGMT" ] && A_HOST="$A_USB4"

# ---- B5q: sync_dir — mkdir 父目录 + rsync (集成验收发现的 code 11 回归修复) ----
sync_dir() { # sync_dir <src_dir> [dst_dir] — dst 缺省 = src (A/B 同 MODEL_ROOT 路径约定)
  local src="$1" dst="${2:-$1}"
  mkdir -p "$dst" || { echo "FATAL: mkdir 失败: $dst" >&2; return 1; }
  rsync -aP --partial --info=progress2 "${A_HOST}:${src}/" "${dst}/"
}

# ---- B5q-3: manifest / 校验函数 (sha256sum -c 兼容) ----
gen_manifest() { # gen_manifest <model-dir> — 生成 <dir>/.sha256 (每 .gguf 一行)
  local d="$1"
  ( cd "$d" && sha256sum *.gguf > .sha256 ) || { echo "FATAL: manifest 生成失败: $d" >&2; return 1; }
}
verify_dir() { # verify_dir <model-dir> — 本地校验; 失败非零退出且点名文件 (B5m1/7.11 教训: 显式暴露)
  local d="$1"
  ( cd "$d" && sha256sum -c .sha256 )
}

main() {
# A-only 模型目录 (publisher/model 级; -L 跟随软链 — B5m2 收编后模型目录是软链)
A_LIST=$(ssh "${A_HOST}" "find -L ${MODEL_ROOT} -mindepth 2 -maxdepth 2 -type d" 2>/dev/null | sort)
B_LIST=$(find -L "${MODEL_ROOT}" -mindepth 2 -maxdepth 2 -type d 2>/dev/null | sort)

A_ONLY=()
while IFS= read -r d; do
  [ -z "$d" ] && continue
  [ -d "$d" ] || A_ONLY+=("$d")
done <<< "$A_LIST"

B_ONLY=()
while IFS= read -r d; do
  [ -z "$d" ] && continue
  ssh "${A_HOST}" "[ -d '${d}' ]" 2>/dev/null || B_ONLY+=("$d")
done <<< "$B_LIST"

echo "=== A-only 模型 (${#A_ONLY[@]} 个, 可同步到 B) ==="
for d in "${A_ONLY[@]:-}"; do
  [ -z "$d" ] && continue
  SZ=$(ssh "${A_HOST}" "du -smL '${d}'" 2>/dev/null | cut -f1)
  echo "  ${d}  (~${SZ}M)"
done

echo "=== B-only 模型 (${#B_ONLY[@]} 个, 信息 — B 独有, 无需同步) ==="
for d in "${B_ONLY[@]:-}"; do
  [ -z "$d" ] && continue
  echo "  ${d}"
done

if [ "$GO" != "1" ]; then
  echo "--- dry-run 结束 (加 --go 执行同步; --go --usb4 走 USB4 链路; --go --verify 附加双端校验) ---"
  exit 0
fi

# 实际同步 (排除分片安全: rsync 全目录, 含 .part 等; --partial 断点续传)
TOTAL=${#A_ONLY[@]}
i=0
for d in "${A_ONLY[@]:-}"; do
  [ -z "$d" ] && continue
  i=$((i+1))
  echo "[$i/$TOTAL] rsync ${d}"
  sync_dir "$d" || echo "FATAL: rsync 失败: ${d} (继续下一目录)" >&2
done
echo "=== 同步完成 ==="
df -h /data | tail -1

# ---- B5q-3: 双端校验 (可选, 加时 — DESIGN 决策 7) ----
# 范围 = 本次 A_ONLY + 有 .sha256 标记的历史同步目录:
#  - 实锤① A_ONLY-only 是假阳性 (空转时 bit-rot/文件缺失检不出) → 历史标记目录纳入
#  - 实锤② 范围 = A 侧全部则误伤双端独立模型 (gpt-oss-120b 等, A/B 各自下载) → 无标记目录跳过
# B 端未同步的目录显式跳过; 检出坏文件后 rm 该目录重跑 --go 修复 (it_tamper2 路径)
if [ "$VERIFY" = "1" ]; then
  FAILED=0
  while IFS= read -r d; do
    [ -z "$d" ] && continue
    if [ ! -d "$d" ]; then
      echo "[verify] 跳过 (B 端未同步): ${d}"
      continue
    fi
    # 范围闸门: 本次 A_ONLY ∨ 历史标记; 其余 = 双端独立, 非 b5k 管理
    if [[ ! " ${A_ONLY[*]:-} " =~ " $d " ]] && [ ! -f "${d}/.sha256" ]; then
      echo "[verify] 跳过 (双端独立, 非 b5k 管理): ${d}"
      continue
    fi
    [ -f "${d}/.sha256" ] || { echo "[verify] 首次: 生成 manifest ${d}/.sha256"; gen_manifest "$d" || { FAILED=1; continue; }; }
    echo "[verify] B 端校验: ${d}"
    verify_dir "$d" || { echo "FATAL: B 端校验失败: ${d}" >&2; FAILED=1; }
    echo "[verify] A 端校验: ${d}"
    ssh "${A_HOST}" "cd '${d}' && sha256sum -c -" < "${d}/.sha256" || { echo "FATAL: A 端校验失败: ${d} (源与 B 不一致)" >&2; FAILED=1; }
  done <<< "$A_LIST"
  [ "$FAILED" = "1" ] && { echo "=== 校验失败 (至少一个文件不一致) ===" >&2; exit 6; }
  echo "=== 双端校验通过 ==="
fi
}

# main guard: source 不执行 (测试可注入调用函数)
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  main "$@"
fi
