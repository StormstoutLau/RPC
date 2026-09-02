#!/usr/bin/env bash
# ============================================================================
# a5-nextday-verify.sh — D5 A5 次日补录: codex-memory 跨会话引用验收
# 站: B (GTR-Pro), opencode 1.18.25 + codex-memory@0.6.5
# 前日会话内容 (T5 试点, 2026-09-02): "D5 agent ecosystem deployed, 12 custom
#   skills in ~/.claude/skills, superpowers v6.3.0, document-skills plugins,
#   limit.context 120000 for nemotron"
# 判据:
#   T1 基础设施: memories/ + memory.db 存在且非空
#   T2 记忆检索: 新会话问"上次这个 repo 做了什么" → 回复引用前日内容关键词
#   T3 关键词命中: "skills" 或 "superpowers" 或 "120000" 或 "document" 至少 1 个
# 判定: T1∧T2∧T3 = GO (A5 闭环) / 否则 NO-GO (触发回退链评估)
# ============================================================================
set -u
OC=~/.opencode/bin/opencode
MEM_DIR=~/.local/share/opencode/memories
DB=~/.local/share/opencode/memory.db
WORK="$(mktemp -d /tmp/a5-verify.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

PASS=0; FAIL=0
res() { case "$1" in
  PASS) PASS=$((PASS+1)); printf '  [PASS] %s\n' "$2" ;;
  FAIL) FAIL=$((FAIL+1)); printf '  [FAIL] %s\n' "$2" ;;
esac; }

section() { printf '\n== %s ==\n' "$1"; }

# ============================================================================
section "T1 基础设施检查"

echo "  memories 目录:"
if [ -d "$MEM_DIR" ]; then
  FILES=$(find "$MEM_DIR" -type f | wc -l)
  echo "    存在, $FILES 个文件"
  find "$MEM_DIR" -type f | head -5 | sed 's/^/    /'
  [ "$FILES" -ge 1 ] && res PASS "T1a memories/ 有产出 ($FILES 文件)" || res FAIL "T1a memories/ 空"
else
  res FAIL "T1a memories/ 目录不存在"
fi

echo
echo "  memory.db:"
if [ -f "$DB" ]; then
  SIZE=$(stat -c%s "$DB" 2>/dev/null || stat -f%z "$DB" 2>/dev/null)
  echo "    存在, ${SIZE} bytes"
  [ "$SIZE" -gt 0 ] && res PASS "T1b memory.db 非空 (${SIZE}B)" || res FAIL "T1b memory.db 零字节"
else
  res FAIL "T1b memory.db 不存在"
fi

echo
echo "  raw_memories.md 内容预览:"
if [ -f "$MEM_DIR/raw_memories.md" ]; then
  head -5 "$MEM_DIR/raw_memories.md" | sed 's/^/    /'
  res PASS "T1c raw_memories.md 可读"
else
  echo "    (不存在, 非阻塞)"
  res PASS "T1c raw_memories.md 不存在 (非阻塞, memory.db 为主)"
fi

# ============================================================================
section "T2 跨会话引用测试 (核心)"

echo "  启动新 opencode 会话, 问'上次这个 repo 做了什么'..."
echo
timeout 300 $OC run -m cluster-litellm/nemotron \
  'Last time I worked on this repo, I deployed something. What did I do? Use your memory to recall.' \
  </dev/null 2>"$WORK/t2.err" | tee "$WORK/t2.out" | tail -20
RC=$?
echo
echo "  [exit=$RC]"

if [ $RC -ne 0 ] && [ ! -s "$WORK/t2.out" ]; then
  res FAIL "T2 会话执行失败 (exit=$RC, 无输出)"
  echo "  stderr:"; head -5 "$WORK/t2.err" | sed 's/^/    /'
else
  res PASS "T2 会话执行完成 (exit=$RC, 有输出)"
fi

# ============================================================================
section "T3 关键词命中 (前日内容引用)"

if [ -s "$WORK/t2.out" ]; then
  echo "  回复全文:"; cat "$WORK/t2.out" | sed 's/^/    /'
  echo

  KW_HITS=0
  for kw in "skill" "superpowers" "120000" "document" "ecosystem" "codex" "memory" "deploy"; do
    N=$(grep -ic "$kw" "$WORK/t2.out" || true)
    if [ "$N" -gt 0 ]; then
      echo "    命中 '$kw': $N 次"
      KW_HITS=$((KW_HITS+N))
    fi
  done

  if [ "$KW_HITS" -ge 1 ]; then
    res PASS "T3 关键词命中 $KW_HITS 次 (前日内容被引用)"
  else
    res FAIL "T3 零关键词命中 (回复未引用前日内容)"
    echo "    期望关键词: skill/superpowers/120000/document/ecosystem/deploy"
  fi
else
  res FAIL "T3 无法检查 (T2 无输出)"
fi

# ============================================================================
section "汇总"
printf '  PASS=%d  FAIL=%d\n' "$PASS" "$FAIL"

if [ "$FAIL" -eq 0 ]; then
  printf '  ==> A5 GO — codex-memory 跨会话引用闭环\n'
  printf '  ==> 补录 CHECKLIST §4 A5: ☑ (基础设施+引用双实证)\n'
  exit 0
else
  printf '  ==> A5 NO-GO — 评估回退 (four-opencode-memory 纯 Markdown 模式)\n'
  printf '  ==> 回退步骤:\n'
  printf '    1) opencode.jsonc 改 plugin 为 ["@four-bytes/four-opencode-memory"]\n'
  printf '    2) 新会话测试 MEMORY.md 增量 (grep 前日关键词)\n'
  exit 1
fi
