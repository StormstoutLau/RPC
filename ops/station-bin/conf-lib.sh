#!/bin/bash
# conf-lib.sh — llama 实例 conf 的唯一写入口 / 读入口（P1 #4）
#
# 契约: spec/review-p1-remediation/DESIGN.md §4.2/§4.3
#   格式: KEY="value"
#   转义集: \\ -> \ , \" -> " , \$ -> $ , \` -> `
#   写: mktemp 同目录 -> awk 重写 -> chmod --reference -> mv（原子替换，不用 sed -i）
#   读: 只读；剥外层单/双引号后按同一转义集反转义
#
# 被 infer-load source；conf-get 是其 CLI 薄壳。纯函数、无副作用（写函数只碰目标 conf）。

conf_escape() {  # <value> -> 转义后内容（无外层引号）；含换行 rc=2
  local v="${1-}"
  case "$v" in
    *$'\n'*) printf 'conf_escape: 值含换行，拒绝写入\n' >&2; return 2 ;;
  esac
  # 顺序要紧: 先转义反斜杠，再转义引号/$/反引号（后续插入的 \ 不再被二次转义）。
  printf '%s' "$v" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/\$/\\$/g' -e 's/`/\\`/g'
}

_conf_su() {  # <file> -> "" 或 "sudo -n"
  if [ -w "$1" ] || [ -w "$(dirname "$1")" ]; then printf ''; else printf 'sudo -n'; fi
}

conf_set_kv() {  # <file> <key> <value>；成功 0 / IO 失败 1 / 值非法 2
  local file="${1-}" key="${2-}" val="${3-}" esc tmp mode su
  case "$file" in ''|*$'\n'*) return 1 ;; esac
  case "$key" in ''|*[!A-Za-z0-9_]*) printf 'conf_set_kv: 非法键 %s\n' "$key" >&2; return 1 ;; esac
  [ -f "$file" ] || { printf 'conf_set_kv: 文件不存在 %s\n' "$file" >&2; return 1; }
  esc=$(conf_escape "$val") || return 2
  su=$(_conf_su "$file")
  # mktemp 与 tee 必须同身份：若 mktemp 走 sudo 而重定向由当前用户执行，
  # 临时文件是 root:root 600 ⇒ 普通用户写不进去。
  tmp=$($su mktemp "${file}.tmp.XXXXXX") || return 1
  if ! CONF_KEY="$key" CONF_VAL="$esc" awk '
        BEGIN { k = ENVIRON["CONF_KEY"]; v = ENVIRON["CONF_VAL"]; done = 0 }
        index($0, k "=") == 1 { if (!done) { print k "=\"" v "\""; done = 1 } ; next }
        { print }
        END { if (!done) print k "=\"" v "\"" }
      ' "$file" | $su tee "$tmp" >/dev/null; then
    $su rm -f "$tmp"; return 1
  fi
  $su chmod --reference="$file" "$tmp" 2>/dev/null || { $su rm -f "$tmp"; return 1; }
  $su mv -f "$tmp" "$file" || { $su rm -f "$tmp"; return 1; }
  return 0
}

conf_get_kv() {  # <file> <key> -> 反转义值；缺失/解析失败 rc=1
  local file="${1-}" key="${2-}" line raw out ch esc
  case "$key" in ''|*[!A-Za-z0-9_]*) return 1 ;; esac
  [ -f "$file" ] || return 1
  line=$(awk -v k="$key" 'index($0, k "=") == 1 { print; exit }' "$file") || return 1
  [ -n "$line" ] || return 1
  raw=${line#*=}
  # 去首尾空白（与旧文本读者一致）
  raw="${raw#"${raw%%[![:space:]]*}"}"
  raw="${raw%"${raw##*[![:space:]]}"}"
  case "$raw" in
    \"*\") raw=${raw#\"}; raw=${raw%\"} ;;
    \'*\') raw=${raw#\'}; raw=${raw%\'} ;;
  esac
  out=""
  while [ -n "$raw" ]; do
    case "$raw" in
      \\*)
        esc=${raw:0:2}; raw=${raw:2}
        case "$esc" in
          '\\') out+='\' ;;
          '\"') out+='"' ;;
          '\$') out+='$' ;;
          '\`') out+='`' ;;
          *) out+="$esc" ;;
        esac
        ;;
      *) ch=${raw:0:1}; out+=$ch; raw=${raw:1} ;;
    esac
  done
  printf '%s\n' "$out"
}
