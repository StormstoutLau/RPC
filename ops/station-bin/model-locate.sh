#!/bin/bash
# model-locate.sh — 模型定位唯一实现（P1 #3）
#
# 契约: spec/review-p1-remediation/DESIGN.md §4.1
#   先枚举 gguf **文件**，再按路径分组（覆盖三种落点）：
#     gguf/<repo>/<f>.gguf             -> 模型 = <repo>            (NF == 2)
#     gguf/<repo>/<Model>-GGUF/…/<f>   -> 模型 = <Model>           (NF >= 3)
#   主文件优先级: 合并单文件(排除分片/mmproj, >1G) > 分片首片 > 任意非 mmproj。
#
# 被 infer-load / infer-list source；纯函数、无副作用、不写文件、不启进程。
# root 默认 /data/models/gguf；参数只用于测试。
# 输出字段以 | 分隔；model_file_for_alias 不解析该分隔，含 | 的路径也能取到。

_model_alias_of() {  # <dir> -> 别名（含 minimax 重映射）
  local a
  a=$(basename "$1" | sed 's/-GGUF$//' | tr 'A-Z' 'a-z')
  case "$a" in minimax-m2.7*) a="m27-q4ks" ;; esac
  printf '%s' "$a"
}

_model_main_gguf() {  # <dir> -> 主 gguf（空 = 无 gguf）
  local full="$1" F
  F=$(find -L "$full" -name '*.gguf' ! -name '*-of-0000*.gguf' ! -name 'mmproj*' \
        -size +1G -printf '%s %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
  [ -z "$F" ] && F=$(find -L "$full" -name '*-00001-of-*.gguf' 2>/dev/null | head -1)
  [ -z "$F" ] && F=$(find -L "$full" -name '*.gguf' ! -name 'mmproj*' 2>/dev/null | head -1)
  printf '%s' "$F"
}

model_scan() {  # [root] -> alias|model_dir|size_mb|main_gguf
  local root="${1:-${MODEL_ROOT:-/data/models/gguf}}" d full F SZ a
  find -L "$root" -mindepth 2 -name '*.gguf' ! -name 'mmproj*' -printf '%P\n' 2>/dev/null \
  | awk -F/ '{ print (NF == 2) ? $1 : $1"/"$2 }' | sort -u \
  | while IFS= read -r d; do
      [ -z "$d" ] && continue
      full="$root/$d"
      F=$(_model_main_gguf "$full")
      [ -z "$F" ] && continue
      SZ=$(du -smL "$full" 2>/dev/null | cut -f1)
      a=$(_model_alias_of "$d")
      printf '%s|%s|%s|%s\n' "$a" "$d" "${SZ:-0}" "$F"
    done
}

model_aliases() {  # [root]
  model_scan "${1:-${MODEL_ROOT:-/data/models/gguf}}" | awk -F'|' '{print $1}' | sort -u
}

model_file_for_alias() {  # <alias> [root] -> 主 gguf 绝对路径；找不到 rc=1
  local want="${1:-}" root="${2:-${MODEL_ROOT:-/data/models/gguf}}" d F
  [ -n "$want" ] || return 1
  # 不解析 model_scan 的 | 切分：直接重走目录 + 同一别名规则，路径含 | 也不受影响。
  d=$(find -L "$root" -mindepth 2 -name '*.gguf' ! -name 'mmproj*' -printf '%P\n' 2>/dev/null \
      | awk -F/ '{ print (NF == 2) ? $1 : $1"/"$2 }' | sort -u \
      | while IFS= read -r x; do
          [ "$(_model_alias_of "$x")" = "$want" ] && { printf '%s\n' "$x"; break; }
        done)
  [ -n "$d" ] || return 1
  F=$(_model_main_gguf "$root/$d")
  [ -n "$F" ] || return 1
  printf '%s\n' "$F"
}
