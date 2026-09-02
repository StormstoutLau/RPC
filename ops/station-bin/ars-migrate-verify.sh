#!/usr/bin/env bash
# ============================================================================
# ars-migrate-verify.sh — D5 §5.4: ARS 移植版 (opencode 原生插件) 迁移验证
# 对应 spec/d5-agent-ecosystem/DESIGN.md §5.4:
#   V6-1   首装实测   (install.sh 落点 / 无越界写入 ~/.claude / 可卸载干净)
#   V6-2   plugin 组件故障面隔离 (禁用后 skills/commands 仍可用)
#   T4b-2  文件面冒烟 (skills/commands 存在 + frontmatter 合法) — 离线部分
#   T4b-3  claim-audit 硬门: 构造 fabricated 样本 + 打印人工执行指引 (MANUAL)
#   T4b-4  集成回归  (systemd enabled 面零新增)
# 不含: opencode 会话级触发与第二站人工复核 (对应验收 A4/A13 的会话部分)
#
# 用法 (站上执行):
#   ./ars-migrate-verify.sh                    # 全流程, 终态=已安装 (默认)
#   ./ars-migrate-verify.sh --leave-removed     # 全流程, 终态=已卸载
#   ./ars-migrate-verify.sh --installed         # 已装态核验 (T4b-1 第二站, 无基线对比)
#   环境变量 ARS_SRC 覆盖源目录 (默认 ~/tools/opencode-academic-research)
#
# 退出码: 0=GO (无 FAIL) / 1=NO-GO (有 FAIL) / 2=用法或前置错误
# 注意: 验证期间请勿开启 claude code / opencode 会话 (快照对比会被运行时文件污染)
# ============================================================================
set -u

ARS_SRC="${ARS_SRC:-$HOME/tools/opencode-academic-research}"
OC_CFG="$HOME/.config/opencode"
CLAUDE_DIR="$HOME/.claude"
MODE="full"

for arg in "$@"; do
  case "$arg" in
    --leave-removed) MODE="leave-removed" ;;
    --installed)     MODE="installed" ;;
    *) printf '用法错误: 未知参数 %s\n' "$arg" >&2; exit 2 ;;
  esac
done

WORK="$(mktemp -d /tmp/ars-verify.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

# ---------- 输出助手 ----------
PASS=0; FAIL=0; WARN=0; SKIP=0
res() { # res <PASS|FAIL|WARN|SKIP> <id> <desc>
  case "$1" in
    PASS) PASS=$((PASS+1)); printf '  [PASS] %-7s %s\n' "$2" "$3" ;;
    FAIL) FAIL=$((FAIL+1)); printf '  [FAIL] %-7s %s\n' "$2" "$3" ;;
    WARN) WARN=$((WARN+1)); printf '  [WARN] %-7s %s\n' "$2" "$3" ;;
    SKIP) SKIP=$((SKIP+1)); printf '  [SKIP] %-7s %s\n' "$2" "$3" ;;
  esac
}
section() { printf '\n== %s ==\n' "$1"; }

# ---------- 快照: 路径清单 + 类型 (symlink 记目标) ----------
snapshot() { # snapshot <dir> <outfile>
  if [ ! -e "$1" ]; then printf '__ABSENT__\n' > "$2"; return; fi
  ( cd "$1" 2>/dev/null && find . \( -type f -o -type l \) 2>/dev/null | sort | \
    while IFS= read -r p; do
      if [ -L "$p" ]; then printf '%s\tL->%s\n' "$p" "$(readlink "$p")"
      else printf '%s\tF\n' "$p"; fi
    done ) > "$2" 2>/dev/null
}
added()   { diff "$1" "$2" 2>/dev/null | sed -n 's/^> //p' | grep -v '^[[:space:]]*$'; }
removed() { diff "$1" "$2" 2>/dev/null | sed -n 's/^< //p' | grep -v '^[[:space:]]*$'; }

systemd_snapshot() {
  systemctl list-unit-files --state=enabled --no-legend 2>/dev/null \
    | awk '{print $1}' | sort
}

run_install() { ( cd "$ARS_SRC" && bash ./install.sh ) >> "$WORK/install.log" 2>&1; }

# ============================================================================
section "P0 预检"

[ -d "$ARS_SRC" ] || { printf '  [FAIL] 前置 ARS 源目录不存在: %s\n' "$ARS_SRC"; exit 2; }
[ -f "$ARS_SRC/install.sh" ] || { printf '  [FAIL] 前置 %s/install.sh 不存在\n' "$ARS_SRC"; exit 2; }
res PASS P0-1 "源目录与 install.sh 存在: $ARS_SRC"

OC_BIN="$(command -v opencode 2>/dev/null || true)"
[ -z "$OC_BIN" ] && [ -x "$HOME/.opencode/bin/opencode" ] && OC_BIN="$HOME/.opencode/bin/opencode"
[ -z "$OC_BIN" ] && [ -x /snap/bin/opencode ] && OC_BIN=/snap/bin/opencode
[ -n "$OC_BIN" ] \
  && res PASS P0-2 "opencode 已安装 ($("$OC_BIN" --version 2>/dev/null | head -1) @ $OC_BIN)" \
  || { res FAIL P0-2 "opencode 未安装 — V6 验证前提不成立, 中止"; exit 2; }
command -v rg >/dev/null 2>&1 && res PASS P0-3 "系统 ripgrep 存在 (#23891 预防)" \
                                 || res WARN P0-3 "系统 ripgrep 缺失 — grep/skill 工具有挂死风险, 建议先 apt install ripgrep"

SRC_TAG="$(cd "$ARS_SRC" && git describe --tags --always 2>/dev/null || echo 'no-git')"
SRC_HASH="$(cd "$ARS_SRC" && git rev-parse --short HEAD 2>/dev/null || echo 'n/a')"
printf '  [INFO] 源版本: tag=%s hash=%s\n' "$SRC_TAG" "$SRC_HASH"

SKILL_COUNT="$(find "$ARS_SRC" -name SKILL.md 2>/dev/null | wc -l)"
[ "$SKILL_COUNT" -ge 1 ] && res PASS P0-4 "源含 $SKILL_COUNT 个 SKILL.md" \
                         || res FAIL P0-4 "源内无 SKILL.md — 不像 ARS 仓, 核对部署源"

# ============================================================================
if [ "$MODE" = "installed" ]; then
  section "T4b-1 已装态核验 (无基线模式)"

  snapshot "$OC_CFG" "$WORK/cfg-now.txt"
  CFG_LINKS="$(sed -n 's/^\(.*\)\tL->.*$/\1/p' "$WORK/cfg-now.txt")"
  ARS_LINKS="$(printf '%s\n' "$CFG_LINKS" | grep -i 'academic\|/ars\|\./ars' || true)"
  [ -n "$ARS_LINKS" ] && res PASS T4b-1a "config 内发现 ARS symlink" || res FAIL T4b-1a "config 内未发现 ARS symlink"
  while IFS= read -r p; do
    [ -z "$p" ] && continue
    tgt="$(readlink -f "$OC_CFG/${p#./}" 2>/dev/null || true)"
    [ -n "$tgt" ] && [ -e "$tgt" ] && res PASS T4b-1b "symlink 有效: $p -> $tgt" \
                                || res FAIL T4b-1b "symlink 断链: $p"
  done <<EOF
$ARS_LINKS
EOF

  snapshot "$CLAUDE_DIR" "$WORK/claude-now.txt"
  CLAUDE_ARS="$(grep -i 'academic-research' "$WORK/claude-now.txt" || true)"
  [ -z "$CLAUDE_ARS" ] && res PASS T4b-1c "~/.claude 无 ARS 越界件" || res FAIL T4b-1c "~/.claude 出现 ARS 件: $CLAUDE_ARS"

  SYSTEMD_NOW="$WORK/systemd-now.txt"; systemd_snapshot > "$SYSTEMD_NOW"
  grep -qi 'ars\|academic' "$SYSTEMD_NOW" && res FAIL T4b-4a "systemd 出现 ARS 相关 enabled unit" \
                                            || res PASS T4b-4a "systemd 无 ARS 相关 enabled unit (当前态, 无基线对比)"
else
  # ---------------- full 模式: 快照 → 装 → 验 → 卸 → (复装) ----------------
  section "V6-1a 安装前快照"
  snapshot "$OC_CFG"     "$WORK/cfg-pre.txt"
  snapshot "$CLAUDE_DIR" "$WORK/claude-pre.txt"
  systemd_snapshot > "$WORK/systemd-pre.txt"
  res PASS SNAP "快照完成 (config / claude / systemd) → $WORK"

  section "V6-1b 执行 install.sh"
  if run_install; then res PASS V6-1b "install.sh 退出码 0 (日志: $WORK/install.log)"
  else res FAIL V6-1b "install.sh 失败 (日志: $WORK/install.log)"; fi

  section "V6-1c 落点与越界核验"
  snapshot "$OC_CFG"     "$WORK/cfg-post.txt"
  snapshot "$CLAUDE_DIR" "$WORK/claude-post.txt"

  CFG_ADDED="$(added "$WORK/cfg-pre.txt" "$WORK/cfg-post.txt" || true)"
  CFG_REMOVED="$(removed "$WORK/cfg-pre.txt" "$WORK/cfg-post.txt" || true)"
  printf '%s\n' "$CFG_ADDED"   > "$WORK/cfg-added.txt"
  printf '%s\n' "$CFG_REMOVED" > "$WORK/cfg-removed.txt"

  if [ -n "$CFG_ADDED" ]; then
    res PASS V6-1c1 "config 增量 $(printf '%s\n' "$CFG_ADDED" | grep -c .) 项 (见 cfg-added.txt)"
  else
    res FAIL V6-1c1 "config 零增量 — install.sh 可能未生效"
  fi
  [ -z "$CFG_REMOVED" ] && res PASS V6-1c2 "install.sh 未删除任何既有 config 文件" \
                       || res FAIL V6-1c2 "install.sh 删除了既有文件: $CFG_REMOVED"

  LINK_OK=0; LINK_BAD=0
  while IFS=$'\t' read -r p _t; do
    [ -z "$p" ] && continue
    case "$_t" in "L->"*) ;; *) continue ;; esac
    tgt="$(readlink -f "$OC_CFG/${p#./}" 2>/dev/null || true)"
    if [ -n "$tgt" ] && [ -e "$tgt" ]; then LINK_OK=$((LINK_OK+1))
    else LINK_BAD=$((LINK_BAD+1)); printf '  [INFO] 断链: %s\n' "$p"; fi
  done < "$WORK/cfg-post.txt"
  [ "$LINK_BAD" -eq 0 ] && [ "$LINK_OK" -ge 1 ] \
    && res PASS V6-1c3 "全部 $LINK_OK 个 symlink 落点有效 (readlink -f 目标存在)" \
    || res FAIL V6-1c3 "symlink 校验: 有效 $LINK_OK / 断链 $LINK_BAD"

  CLAUDE_ADDED="$(added "$WORK/claude-pre.txt" "$WORK/claude-post.txt" || true)"
  CLAUDE_ARS_WRITE="$(printf '%s\n' "$CLAUDE_ADDED" | grep -i 'academic' || true)"
  if [ -n "$CLAUDE_ARS_WRITE" ]; then
    res FAIL V6-1c4 "越界写入 ~/.claude: $CLAUDE_ARS_WRITE"
  elif [ -n "$CLAUDE_ADDED" ]; then
    res WARN V6-1c4 "~/.claude 有非 ARS 新增 (疑似运行时文件, 复核): $(printf '%s\n' "$CLAUDE_ADDED" | head -3)"
  else
    res PASS V6-1c4 "~/.claude 零变化 — 无越界写入"
  fi

  section "T4b-2 文件面冒烟 (离线)"
  FM_BAD=0; FM_OK=0
  for f in $(find "$ARS_SRC" -name SKILL.md 2>/dev/null); do
    if head -15 "$f" | grep -q '^name:' && head -15 "$f" | grep -q '^description:'; then
      FM_OK=$((FM_OK+1))
    else FM_BAD=$((FM_BAD+1)); printf '  [INFO] frontmatter 异常: %s\n' "$f"; fi
  done
  [ "$FM_BAD" -eq 0 ] && [ "$FM_OK" -ge 1 ] \
    && res PASS T4b-2a "$FM_OK 个 SKILL.md frontmatter 合法 (name+description)" \
    || res FAIL T4b-2a "frontmatter 异常 $FM_BAD 件 / 合法 $FM_OK 件"

  CMD_COUNT="$(find "$ARS_SRC" -path '*command*' -name '*.md' 2>/dev/null | wc -l)"
  [ "$CMD_COUNT" -ge 1 ] && res PASS T4b-2b "命令面存在 ($CMD_COUNT 个 command md)" \
                         || res WARN T4b-2b "未定位到 commands 目录 — 结构与预期不同, 人工复核"

  section "V6-2 plugin 组件故障面隔离"
  PLUGIN_PATHS="$(printf '%s\n' "$CFG_ADDED" | grep -i 'plugin' || true)"
  if [ -z "$PLUGIN_PATHS" ]; then
    res SKIP V6-2 "config 增量中无 plugin 组件 — 本版可能纯 skills/commands 打包, 无需隔离 (记录台账)"
  else
    MOVED=0; BROKEN=0
    while IFS= read -r p; do
      [ -z "$p" ] && continue
      full="$OC_CFG/${p#./}"
      case "$p" in *$'\t'*) p="${p%%$'\t'*}" ;; esac
      if [ -e "$full" ] || [ -L "$full" ]; then
        mv "$full" "$full.v6bak" && MOVED=$((MOVED+1)) || BROKEN=$((BROKEN+1))
      fi
    done <<EOF
$PLUGIN_PATHS
EOF
    snapshot "$OC_CFG" "$WORK/cfg-isolated.txt"
    SKILLS_SURVIVED="$(sed 's/\t.*//' "$WORK/cfg-isolated.txt" | grep -i 'skill\|command' | wc -l)"
    RESTORED=0
    while IFS= read -r p; do
      [ -z "$p" ] && continue
      case "$p" in *$'\t'*) p="${p%%$'\t'*}" ;; esac
      full="$OC_CFG/${p#./}"
      [ -e "$full.v6bak" ] && mv "$full.v6bak" "$full" && RESTORED=$((RESTORED+1))
    done <<EOF
$PLUGIN_PATHS
EOF
    if [ "$BROKEN" -eq 0 ] && [ "$RESTORED" -eq "$MOVED" ] && [ "$SKILLS_SURVIVED" -ge 1 ]; then
      res PASS V6-2 "plugin 组件隔离 ($MOVED 项) 后 skills/commands 面仍可达 ($SKILLS_SURVIVED 项), 已恢复"
    else
      res FAIL V6-2 "plugin 隔离/恢复异常: moved=$MOVED broken=$BROKEN restored=$RESTORED survived=$SKILLS_SURVIVED — 人工检查 $OC_CFG"
    fi
  fi

  section "T4b-4 集成回归 (systemd)"
  systemd_snapshot > "$WORK/systemd-post.txt"
  SYSTEMD_ADDED="$(added "$WORK/systemd-pre.txt" "$WORK/systemd-post.txt" || true)"
  [ -z "$SYSTEMD_ADDED" ] && res PASS T4b-4a "enabled unit 零新增 (不变式②)" \
                        || res FAIL T4b-4a "新增 enabled unit: $SYSTEMD_ADDED"

  section "V6-1d 可卸载干净核验"
  UNLINKED=0; UNLINK_MISS=0
  while IFS= read -r p; do
    [ -z "$p" ] && continue
    case "$p" in *$'\t'*) p="${p%%$'\t'*}" ;; esac
    full="$OC_CFG/${p#./}"
    if [ -L "$full" ] || [ -e "$full" ]; then
      rm -rf "$full" && UNLINKED=$((UNLINKED+1)) || UNLINK_MISS=$((UNLINK_MISS+1))
    fi
  done < "$WORK/cfg-added.txt"
  snapshot "$OC_CFG" "$WORK/cfg-uninst.txt"
  UNINST_LEFT="$(added "$WORK/cfg-pre.txt" "$WORK/cfg-uninst.txt" || true)"
  UNINST_LOST="$(removed "$WORK/cfg-pre.txt" "$WORK/cfg-uninst.txt" || true)"
  if [ -z "$UNINST_LEFT" ] && [ -z "$UNINST_LOST" ] && [ "$UNLINK_MISS" -eq 0 ]; then
    res PASS V6-1d "清除 $UNLINKED 项增量后 config 恢复快照态 — 可卸载干净 (源目录保留, 免重传)"
  else
    res FAIL V6-1d "卸载后 config 未恢复: 新增残留=$(printf '%s\n' "$UNINST_LEFT" | head -3) 误删=$(printf '%s\n' "$UNINST_LOST" | head -3)"
  fi

  if [ "$MODE" = "full" ]; then
    section "终态: 复装"
    if run_install; then res PASS REINST "复装完成 — 终态=已安装"
    else res FAIL REINST "复装失败 — 当前为卸载态, 人工重跑 install.sh"; fi
  else
    section "终态: 保持卸载 (--leave-removed)"
    res PASS LEAVE "终态=已卸载 — 首站验证/暂不部署形态"
  fi
fi

# ============================================================================
section "T4b-3 claim-audit 硬门 — 样本准备 (MANUAL)"
SAMPLE="$HOME/ars-claim-audit-sample.md"
cat > "$SAMPLE" <<'EOF'
# fabricated-reference 验证样本 (T4b-3)

断言: 据文献 [1]，该方法可将策略夏普比率提升 300%。

[1] Zhang, Q., & Nobody, A. (2031). "A Study That Never Existed."
    Journal of Nonexistent Results, 99(1), 1-2.
    https://doi.org/10.9999/fake-doi-0000
EOF
res PASS T4b-3p "样本已写入 $SAMPLE"
cat <<'EOF'
  ------------------------------------------------------------------
  人工执行指引 (需外网可达侧, 网络可达侧=A 站或 V3 通时的 B 站):
  1) ARS_CLAIM_AUDIT=1 下让 opencode 会话读取该样本并产出引用该文献的摘要
  2) 预期: 5 类 HIGH-WARN 之一触发 (claim-not-supported /
     fabricated-reference / anchorless ...) 且 formatter 拒绝输出
  3) 通过后将触发类别与日志贴入 CHECKLIST (对应验收 A13)
  ------------------------------------------------------------------
EOF

# ============================================================================
section "汇总"
printf '  PASS=%d  FAIL=%d  WARN=%d  SKIP=%d\n' "$PASS" "$FAIL" "$WARN" "$SKIP"
printf '  快照与中间文件: %s (脚本退出自动清理, 需留存请在运行前设 WORK)\n' "${WORK:-/tmp/ars-verify.*}"
if [ "$FAIL" -eq 0 ]; then
  printf '  ==> GO\n'; exit 0
else
  printf '  ==> NO-GO\n'; exit 1
fi
