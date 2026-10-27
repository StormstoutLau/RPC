# 实施文档：原始评审 P1 四条修复

---

id: review-p1-remediation-IMPLEMENTATION
type: design
version: 1.0
status: draft
date: 2026-10-27
depends: [review-p1-remediation-DESIGN]
upstream: null

---

> **Feature**: 把 2026-10-21 原始评审 RPC 段的四条 P1（#3 模型定位、#4 conf 引号/转义、#7 ds4 监听默认、#10 Web token）落到可执行的改动点：一份模型定位、一份 conf 读写契约、一个安全默认、一条常量时间鉴权链。
> **创建日期**: 2026-10-27
> **状态**: draft（Step 3 IMPLEMENTATION；Step 4 设计评审见 §12）
> **Spec 步骤**: Step 3（IMPLEMENTATION）
> **基于设计**: [DESIGN.md](./DESIGN.md)
> **基于调研**: [原始评审 P1 社区外部锚点调研](../../docs/research/2026-10-26_原始评审P1_社区外部锚点调研.md) · [原始评审报告复核矩阵](../../docs/research/2026-10-26_原始评审报告复核_RPC.md)
> **代码基线**: `0c53fcc3`（`main`；行号为该基线快照，实施时以函数名锚点为准）

---

## 1. 实施范围

### 1.1 交付物

| # | 交付物 | 落位 | 类型 |
|---|---|---|---|
| T1 | Web 鉴权：常量时间比较 + Cookie/Header 双通道 + loopback 引导 + 响应头 + 日志脱敏（#10） | [cluster_web.py](../../ops/cluster_web.py) | 修改 |
| T2 | conf 共享库：转义、原子写、反转义读（#4） | `ops/station-bin/conf-lib.sh` | 新增 |
| T3 | conf 读取 CLI（#4） | `ops/station-bin/conf-get` | 新增 |
| T4 | 主控侧 conf 解析，`cluster._parse_conf` 委托（#4） | `ops/conf_parse.py`、[cluster.py](../../ops/cluster.py) | 新增 + 修改 |
| T5 | `infer-load` 写入口收敛（首次生成 + `_set_conf_key`）（#4） | [infer-load](../../ops/station-bin/infer-load) | 修改 |
| T6 | `rpc_check` 的 `[mpath]` 改走 `conf-get`（#4） | [rpc_check.py](../../ops/rpc_check.py) | 修改 |
| T7 | 模型定位共享库（#3） | `ops/station-bin/model-locate.sh` | 新增 |
| T8 | `infer-load` / `infer-list` 接入共享库（#3） | [infer-load](../../ops/station-bin/infer-load)、[infer-list](../../ops/station-bin/infer-list) | 修改 |
| T9 | ds4 监听默认与 `--pp-listen`（#7） | [infer-load](../../ops/station-bin/infer-load) | 修改 |
| T10 | 编排层 PP 直连段取址与传参（#7） | [cluster.py](../../ops/cluster.py) | 修改 |
| T11 | `STATION_BINS` 扩到 12 件 + README 清单（部署一致性） | [rpc_check.py](../../ops/rpc_check.py)、[README](../../ops/station-bin/README.md) | 修改 |
| T12 | 先验红 / 后验绿测试 | `tests/test_conf_parse.py`、`test_conf_lib.py`、`test_model_locate.py`、`test_cluster_pp_listen.py`、`test_cluster_web_auth.py` | 新增 |
| T13 | 手册与索引回写 | [三机推理集群使用手册](../../docs/三机推理集群使用手册.md)、[FRAMEWORK-INDEX](../../docs/FRAMEWORK-INDEX.md) | 修改 |

### 1.2 边界（不做）

- 不扫荡 `set -euo`（#5）、不改遗留 systemd 单元（#6）、不收敛全部硬编码（#9）、不拆文件/分目录（#8）、不接 CI（P2 五项）。
- 不新增 daemon、不新增并列管理入口（ADR-0004）；三个站上件只被既有脚本 `source`。
- 不改变 ds4 / llama.cpp 引擎内部；不为 #7 新增门禁（只在启动日志与手册留痕）。
- 不做 OAuth/JWT；不改容器路径与 `CONTAINER_MODELS`。
- 不自动执行会打断现役服务的真站 ds4 PP 加载（真站验证按需、需先卸旧实例）。

---

## 2. 工程约定

| 项 | 值 | 依据 |
|---|---|---|
| 站上件解释器 | `#!/bin/bash`（Ubuntu bash 5 / Git Bash 测试） | 既有 `ops/station-bin` 同栈 |
| 站上件行尾 | **LF** | [`.gitattributes`](../../.gitattributes) 已锁 `ops/station-bin/*` |
| 主控解释器 | `py -3.12`（需 paramiko） | `tests/run_py_tests.py` 既有约定 |
| 新依赖 | **零**：shell 只用 `find/awk/sed/mktemp/mv/chmod/sudo -n`；Python 只用 stdlib | DESIGN §2.2 |
| 退出码 | `0` 成功 / `1` 失败；`conf_set_kv` 额外用 `2` 表示"值非法" | DESIGN §4.3、§7 |
| 写操作纪律 | 关键写操作逐条 `\|\|` 检查；禁止 `eval`；禁止 `sed -i` 改关键 conf | 调研 §3.2 |
| 原子写 | `mktemp` 同目录 → 重写 → `mv` | DESIGN §4.3 |
| 部署 | SFTP 上传 + `install -m 755`，三站，逐站 md5 对账 | [station-bin README](../../ops/station-bin/README.md) |
| 日志前缀 | `[cluster-web]` / `[cluster]` / `[infer-load]` | 既有 |
| 测试出口 | `tests/test_*.py`，必须打印 `RESULT:` 汇总行 | [run_py_tests.py](../../tests/run_py_tests.py) |

**解释器边界**：`ops/conf_parse.py` 不导入 paramiko / 不导入 `cluster`；`cluster._parse_conf` 在函数内导入它，避免成为 `cluster_*.py` 的模块级依赖边。

---

## 3. 任务分解

### T1（#10）：Web 鉴权与引导

1. 新增模块级 `_token_eq(a, b)`：空值 / 非字符串 ⇒ False；否则 `hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))`（`compare_digest` 对非 ASCII `str` 会抛 `TypeError`，故统一转 bytes）。
2. `Handler._auth_ok`：候选 = `X-Auth-Token` 头 + `rpc_token` Cookie（`unquote` 后）；任一通过即 True。
3. `Handler.do_GET`：`/` 或 `/index.html` 且 query 含 `token` 时进入引导；仅当 `Handler._host` 与 `client_address[0]` 都是 loopback 才允许；校验通过 ⇒ `Set-Cookie` + `302 /`；否则 `401`。
4. 响应头：`_json` / `_text` / `_redirect` 统一 `Referrer-Policy: no-referrer`；`401` / `302` 追加 `Cache-Control: no-store`。
5. `log_message` 覆写：把 `?token=…` / `&token=…` 的**值**替换为 `***`（默认 `BaseHTTPRequestHandler` 会打印含 query 的 requestline）。
6. token 落点：显式 `--token` 不落盘；自动生成写 `~/.local/share/rpc/web-token`（0600，失败即 exit 1）；启动日志只打印路径 + `_mask_token()`。
7. 前端：删掉 `?token=` 自动登录 + `localStorage` 写入；手输 token 保留；登录框初始隐藏，仅 401 时显示（Cookie 用户不再看到登录框）。
8. 测试：`tests/test_cluster_web_auth.py`（见 §9）。

### T2（#4）：`conf-lib.sh`

1. `conf_escape <value>`：拒绝换行（rc=2）；按 `\\` → `\\\\`、`"` → `\"`、`$` → `\$`、`` ` `` → ``\` `` 顺序转义；NUL 在 bash 变量中不可表示，文档与测试只钉换行。
2. `conf_set_kv <file> <key> <value>`：键白名单 `[A-Za-z0-9_]+`；`mktemp` 同目录；`awk` 重写（替换首个匹配键并删除同名重复行，保留注释/顺序/其余行）；`tee` 写临时文件；`chmod --reference`；`mv -f` 原子替换；任一步失败清理临时文件并返回 1。
3. `conf_get_kv <file> <key>`：只读；取首个 `KEY=` 行；剥外层单/双引号；按固定转义集反转义；缺失/解析失败 rc=1。
4. `sudo` 处理：目标文件或目录不可写时用 `sudo -n`；`mktemp` 与 `tee` 都必须以同一身份执行（否则 root 创建的临时文件无法被当前用户重定向写入）。
5. 测试：`tests/test_conf_lib.py`（转义矩阵 + 三方一致性 + 拒绝换行不破坏原文件）。

### T3（#4）：`conf-get`

1. 定位自身实路径（`BASH_SOURCE[0]` → `readlink -f` → `command -v` 兜底），`source` 同目录 `conf-lib.sh`。
2. 直接 `conf_get_kv "$1" "$2"`，不加工输出。

### T4（#4）：`conf_parse.py` 与 `cluster._parse_conf`

1. `parse_conf(text)`：忽略空行/注释/无 `=` 行；键去空白；值按双引号反转义，未加引号的历史值同样按固定转义集反转义（未知 `\x` 原样保留）。
2. `get_value(text, key)`：缺失返回 `""`。
3. `cluster._parse_conf` 改为函数内 `from conf_parse import parse_conf` 并直接返回。
4. 测试：`tests/test_conf_parse.py` 钉住 8 类输入。

### T5（#4）：`infer-load` 写入口

1. 首次生成 conf 前：`MP_ESC=$(conf_escape "$F") || exit 1`；heredoc 行改为 `MODEL_PATH="${MP_ESC}"`。
2. `_set_conf_key` 保留为薄包装：`conf_set_kv "$CONF" "$1" "$2" || { log "ERROR: conf 写入失败 ($1)"; exit 1; }`；调用形状不变。
3. 删除 `sed -i` 与"追加前补换行"的特判（`conf_set_kv` 的整文件重写已保证末行换行，Bug C 被结构性消除）。

### T6（#4）：`rpc_check [mpath]`

1. `[mpath]` 段改为 `CG=$(command -v conf-get 2>/dev/null || echo /usr/local/bin/conf-get)`；`p=$("$CG" "$f" MODEL_PATH 2>/dev/null); rc=$?`。
2. `rc != 0` 或空值 ⇒ `NO_MODEL_PATH`（不静默 OK）；文件存在 ⇒ `OK`；否则 `MISSING <path>`。
3. 其它键（CTX/BACKEND 等）保持既有 `sed` 读取 —— 这些键不允许特殊字符。

### T7（#3）：`model-locate.sh`

1. `MODEL_ROOT` 可被环境覆盖，默认 `/data/models/gguf`；三个公开函数内部各自兜底默认值（便于 `declare -f` 送到对端执行）。
2. `model_scan [root]`：文件级 `find -L -mindepth 2 -name '*.gguf' ! -name 'mmproj*'` → 按路径分组（`NF==2` 取 `$1`，否则取 `$1/$2`）→ 每组选主 gguf（合并单文件 >1G → `-00001-of-*` → 任意）→ 输出 `alias|model_dir|size_mb|main_gguf`。
3. `model_aliases [root]`：`model_scan` 的 alias 去重排序。
4. `model_file_for_alias <alias> [root]`：用 `awk -F'|'` 精确匹配第一列，输出第 4 列起的完整路径（保留路径中的 `|`）；找不到 rc=1。
5. 别名规则与 `infer-list` 现行规则一致，含 `minimax-m2.7*` → `m27-q4ks`。

### T8（#3）：两脚本接入

1. `infer-load` 顶部 source `model-locate.sh` → `ALL_ALIASES=$(model_aliases)`（ds4 分支仍用 `/etc/ds4-instances/*.env` 覆盖）。
2. 首次生成 conf 的 `REPO` 定位整段替换为 `F=$(model_file_for_alias "$ALIAS")`；失败时打印 `model_aliases` 候选并 exit 1；`REPO=$(dirname "$F")` 仅用于分片大小统计。
3. 别名无匹配诊断补一行候选 alias 列表。
4. `infer-list.scan()` 改为 `model_scan` + 既有非 GGUF 分支；`peer_scan` 的 payload 同时发送 `_model_alias_of model_scan model_aliases model_file_for_alias` 与 `scan` 的函数定义。
5. 全仓断言：`infer-load` 不再含 `-maxdepth 2 -type d`。

### T9（#7）：`infer-load` ds4 监听

1. 参数解析新增 `--pp-listen <ip>`；字符白名单 `[0-9A-Fa-f:.]`，否则 exit 1。
2. ds4 分支 `source "$DS4_CONF"` 之后：
   - `_PP_EXPLICIT="${CLI_PP_LISTEN:-${PP_LISTEN:-}}"`；
   - `PP_LISTEN="${_PP_EXPLICIT:-127.0.0.1}"`；
   - `PP_ROLE=coordinator` 且 `_PP_EXPLICIT` 为空 ⇒ 打印"需要可被 worker 访问的直连段 IP，不能默认 0.0.0.0"并 exit 1；
   - `PP_ROLE=worker` 不使用该值；
   - 单机不向引擎传 `--listen`（HTTP 面仍显式 `--host 127.0.0.1`；PP 绑定默认值只在 coordinator 生效）。
3. coordinator 启动行 `--listen "${PP_LISTEN}"`；日志打印 `listen='${PP_LISTEN}'`。
4. usage 行补 `--pp-listen`。

### T10（#7）：`cluster.py` 编排

1. 顶部 `import ipaddress`。
2. `_pp_listen_ip(coord, worker) -> str`：只解析 [inventory/net.yaml](../../inventory/net.yaml) 的 `segments:` 段；段内 `{station: X, ip: ...}` 行建 `station→ip`；恰好一段同时含 coord/worker 时返回 coord 的 IP；找不到 / 多义 / IP 非法 ⇒ `""`。
3. `_build_infer_load_cmd(..., pp_listen=None)`：仅非空时追加 `--pp-listen '<ip>'`；`pp_listen` 非空但非法 ⇒ `ValueError`（防御性，正常路径已由 `_pp_listen_ip` 校验）。
4. `_load_ds4_pp`：**先**取 `pp_ip`，为空立即 return 1（尚未起 worker）；worker 命令不变；coordinator 命令传 `pp_listen=pp_ip`；打印实际值。

### T11（部署一致性）

1. `STATION_BINS` 增加 `model-locate.sh`、`conf-lib.sh`、`conf-get`，并更新"第 9 件"注释为 12 件。
2. `ops/station-bin/README.md` 文件清单增加三行；部署记录写明备份名、md5、`bash -n` 与 `conf-get` 冒烟。
3. 三站按"备份 → `install -m 755` → md5 对账 → `bash -n`"部署；新件的 md5 由 `stations` 门禁在运行期按仓库副本复算。

### T12（测试）

按 §9 的先验红矩阵先写失败断言，再实现至全绿；新增 5 个 `tests/test_*.py`，每个输出 `RESULT:`。

### T13（文档）

1. 手册补 `infer-load --pp-listen` 与 ds4 PP 显式传参示例；写明"coordinator 不再默认 0.0.0.0"。
2. `FRAMEWORK-INDEX.md` 增加本次执行记录一行（指向本 spec 与实施日志）。
3. `docs/2026-10-27_GLM1M_Qwen1M_启动与cc-switch接入.md` 不新增内容（它是 1M 服务记录，不与本批混写）。

---

## 4. 逐文件改造点

> 行号为 `0c53fcc3` 快照；实施时以函数名/锚点为准。所有站上件保持 LF。

### 4.1 新增 `ops/station-bin/model-locate.sh`

```bash
#!/bin/bash
# model-locate.sh — 模型定位共享库（infer-load / infer-list 共同 source）
# 契约: spec/review-p1-remediation/DESIGN.md §4.1；只读、无副作用。
# 规则: 先枚举 gguf 文件，再按路径分组（覆盖仓库级直放 / 模型目录 / 量化子目录）。

_model_alias_of() {  # <dir> -> 别名（含 minimax 重映射）
  local a
  a=$(basename "$1" | sed 's/-GGUF$//' | tr 'A-Z' 'a-z')
  case "$a" in minimax-m2.7*) a="m27-q4ks" ;; esac
  printf '%s' "$a"
}

_model_main_gguf() {  # <dir> -> 主 gguf（优先级: 合并单文件 > 分片首片 > 任意）
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
```

**要点**：

- 主文件选择抽成 `_model_main_gguf`，`model_scan` 与 `model_file_for_alias` 共用，避免第二份优先级规则。
- `model_file_for_alias` **不解析** `model_scan` 的 `|` 切分，而是直接重走目录 + `_model_alias_of` ⇒ 路径含 `|` 也不受影响。
- `model_scan` 的最后一列是完整路径；若调用方要切分，只能按**前 3 个** `|` 切（路径含 `|` 时改用 `model_file_for_alias`）。
- **已知限制（与旧 `infer-list` 相同，本批不扩大支持面）**：目录名本身含 `|` 时，`model_aliases` 与 `model_scan` 的字段切分无法表达该 alias；`model_file_for_alias` 仍可按完整 alias 取到文件。
- 同名 alias 跨仓库时取排序后的第一组（与旧 `head -1` 行为同量级）。
- 大小口径不变：`du -smL` 模型目录总量（分片头可能 header-only）。

### 4.2 新增 `ops/station-bin/conf-lib.sh`

```bash
#!/bin/bash
# conf-lib.sh — llama 实例 conf 的唯一写入口 / 读入口
# 格式: KEY="value"；转义集 \\ \" \$ \`；见 DESIGN §4.2/§4.3。

conf_escape() {  # <value> -> 转义后内容（无外层引号）；含换行 rc=2
  local v="${1-}"
  case "$v" in
    *$'\n'*) printf 'conf_escape: 值含换行，拒绝写入\n' >&2; return 2 ;;
  esac
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
```

**为什么 `mktemp`/`tee` 要同身份**：若 `mktemp` 走 `sudo -n` 而重定向由当前用户执行，临时文件是 root:root 600 ⇒ 普通用户写入失败；故统一用 `$su tee`。

**为什么删重复键**：`awk` 对同名键只保留首个并删除后续行 —— 否则后出现的重复键会在 `source` 时覆盖新值，形成"写了但没生效"。

### 4.3 新增 `ops/station-bin/conf-get`

```bash
#!/bin/bash
# conf-get <file> <key> — 输出反转义后的值；缺失/解析失败 rc=1
set -uo pipefail
_self=${BASH_SOURCE[0]}
case "$_self" in */*) ;; *) _self=$(command -v -- "$_self" || true) ;; esac
HERE=$(cd "$(dirname "$(readlink -f "$_self")")" && pwd)
. "$HERE/conf-lib.sh"
conf_get_kv "${1-}" "${2-}"
```

### 4.4 新增 `ops/conf_parse.py`

```python
"""llama 实例 conf 解析 —— 与 ops/station-bin/conf-lib.sh 同一格式（DESIGN §4.2）。"""
_ESC = {"\\": "\\", '"': '"', "$": "$", "`": "`"}


def _unescape(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s) and s[i + 1] in _ESC:
            out.append(_ESC[s[i + 1]]); i += 2
        else:
            out.append(c); i += 1
    return "".join(out)


def _value(raw: str) -> str:
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        q = v[0]
        v = v[1:-1]
        return _unescape(v) if q == '"' else v
    return _unescape(v)


def parse_conf(text: str) -> dict:
    d = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        d[k.strip()] = _value(v)
    return d


def get_value(text: str, key: str) -> str:
    return parse_conf(text).get(key, "")
```

### 4.5 `cluster.py`（L236-245 / L818-828 / L1517-1551）

```python
def _parse_conf(text: str) -> dict:
    """解析站上 conf。委托 ops/conf_parse（与站上 conf-lib.sh 同一转义规则）。"""
    from conf_parse import parse_conf      # 函数内导入：不成为 cluster_*.py 的模块级依赖边
    return parse_conf(text)
```

```python
def _pp_listen_ip(coord: str, worker: str) -> str:
    """coordinator 在 coord-worker 直连段上的 IP；找不到/多义/非法 → ""（不猜）。"""
    path = Path(__file__).resolve().parent.parent / "inventory" / "net.yaml"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    in_seg, seg, hits = False, {}, []
    def close_seg():
        if coord in seg and worker in seg and coord != worker:
            hits.append(seg[coord])
    for line in lines:
        s = line.strip()
        if s.startswith("segments:"):
            in_seg = True; continue
        if in_seg and s.startswith("routes:"):
            break
        if not in_seg:
            continue
        if s.startswith("- name:"):
            close_seg(); seg = {}; continue
        m = re.search(r"station:\s*([ABC])\b.*?\bip:\s*([0-9.]+)", s)
        if m:
            try:
                ipaddress.ip_address(m.group(2))
            except ValueError:
                continue
            seg[m.group(1)] = m.group(2)
    close_seg()
    return hits[0] if len(hits) == 1 else ""
```

```python
def _build_infer_load_cmd(matched: str, backend: str, engine: str = None,
                          rpc_target: str = None, pp_listen: str = None) -> str:
    """拼装远端 infer-load 命令。pp_listen 仅 ds4 coordinator 使用，已由 _pp_listen_ip 校验。"""
    cmd = f"infer-load '{matched}'" + (f" --backend {backend}" if backend else "")
    if engine:
        cmd += f" --engine '{engine}'"
    if rpc_target:
        cmd += f" --rpc-target '{rpc_target}'"
    if pp_listen:
        try:
            ipaddress.ip_address(pp_listen)
        except ValueError as e:
            raise ValueError(f"非法 pp_listen: {pp_listen!r}") from e
        cmd += f" --pp-listen '{pp_listen}'"
    return cmd
```

```python
def _load_ds4_pp(alias: str, coord: str, worker: str) -> int:
    pp_ip = _pp_listen_ip(coord, worker)
    if not pp_ip:
        print(f"[cluster] 无法从 inventory/net.yaml 读出 {coord}-{worker} 直连段 IP "
              f"⇒ ds4 PP 中止 (不默认 0.0.0.0)。")
        return 1
    print(f"[cluster] PP listen: coordinator={coord} ip={pp_ip}")
    # [1/3] worker 先起（序不可反）
    rc = ssh_stream(worker, _build_infer_load_cmd(alias, "ds4"))
    ...
    # [2/3] coordinator 显式传直连段 IP
    rc = ssh_stream(coord, _build_infer_load_cmd(alias, "ds4", pp_listen=pp_ip))
    ...
```

### 4.6 `ops/station-bin/infer-load`

**L20-31 参数解析**：

```bash
PREFIX=""; BACKEND=""; PORT=""; CTX=""; THREADS=""; CLI_ENGINE=""; CLI_RPC_TARGET=""; CLI_PP_LISTEN=""
...
    --pp-listen) CLI_PP_LISTEN="$2"; shift 2 ;;
```

`--pp-listen` 白名单（放在 `log()` 定义之后、`[1]` 之前）：

```bash
if [ -n "${CLI_PP_LISTEN:-}" ]; then
  case "$CLI_PP_LISTEN" in
    *[!0-9A-Fa-f:.]*) log "ERROR: --pp-listen 非法 IP: '${CLI_PP_LISTEN}'"; exit 1 ;;
  esac
fi
```

**顶部 source 共享库**：

```bash
_self=${BASH_SOURCE[0]}
case "$_self" in */*) ;; *) _self=$(command -v -- "$_self" || true) ;; esac
HERE=$(cd "$(dirname "$(readlink -f "$_self")")" && pwd)
. "$HERE/model-locate.sh"
. "$HERE/conf-lib.sh"
```

**L70-72 别名**：

```bash
ALL_ALIASES=$(model_aliases)
```

ds4 分支的 `/etc/ds4-instances/*.env` 覆盖保持原样。

**L115-122 定位 + conf 生成**：

```bash
F=$(model_file_for_alias "$ALIAS") || {
  echo "ERROR: 模型文件未找到 (alias=$ALIAS)"
  echo "候选 alias: $(model_aliases | tr '\n' ' ')"
  exit 1
}
REPO=$(dirname "$F")
if echo "$F" | grep -q -- '-of-0000'; then SZ=$(du -smL "$REPO" | cut -f1); else SZ=$(( $(stat -c%s "$F") / 1048576 )); fi
...
MP_ESC=$(conf_escape "$F") || { echo "ERROR: MODEL_PATH 含非法字符 (换行)"; exit 1; }
sudo tee "$CONF" >/dev/null <<CEOF
...
MODEL_PATH="${MP_ESC}"
...
CEOF
```

**L174-189 `_set_conf_key`**：

```bash
_set_conf_key() {  # 幂等写/改实例 conf 的一行；失败即中止
  conf_set_kv "$CONF" "$1" "$2" || { log "ERROR: conf 写入失败 ($1, rc=$?)"; exit 1; }
}
```

**L392-396 ds4 coordinator**：

```bash
    coordinator)
      log "ds4 coordinator: ... listen='${PP_LISTEN}' pp=${PP_PORT} http=${HTTP_PORT}) ..."
      nohup "${DS4_HOME}/ds4-server" --rocm --role coordinator --layers "${PP_LAYERS:-}" \
        --listen "${PP_LISTEN}" "${PP_PORT}" \
        -m "$MODEL_PATH" -c "$CTX" --host 127.0.0.1 --port "$HTTP_PORT" \
        > "$DS4_LOG" 2>&1 &
      ;;
```

PP 值解析（`source "$DS4_CONF"` 之后）：

```bash
_PP_EXPLICIT="${CLI_PP_LISTEN:-${PP_LISTEN:-}}"
PP_LISTEN="${_PP_EXPLICIT:-127.0.0.1}"
case "$PP_ROLE" in
  coordinator)
    [ -n "$_PP_EXPLICIT" ] || {
      log "ERROR: PP coordinator 需要一个可被 worker 访问的直连段 IP (--pp-listen)，不能默认 0.0.0.0"
      exit 1
    }
    ;;
  worker) : ;;   # worker 不使用 PP_LISTEN
  *)       : ;;   # 单机：不向引擎传 --listen，HTTP 面仍 --host 127.0.0.1
esac
```

### 4.7 `ops/station-bin/infer-list`

**L63-90 `scan()`**：

```bash
scan() {
  model_scan
  for d in /data/models/*/; do
    case "$d" in */gguf/) continue ;; esac
    ST=$(find -L "$d" -name '*.safetensors' 2>/dev/null | wc -l)
    [ "$ST" -gt 0 ] && printf '%s|%s|%s|%s\n' "m27-awq" "$(basename "$d")" \
                                              "$(du -m "$d" | cut -f1)" "$d"
  done
}
```

**顶部 source 共享库**（与 `infer-load` 同一段）；**L96-105 `peer_scan` payload**：

```bash
payload="$(declare -f _model_alias_of model_scan model_aliases model_file_for_alias)
$(declare -f scan)
scan"
```

### 4.8 `ops/cluster_web.py`

**L399-400**：

```python
    def _auth_ok(self):
        cands = [self.headers.get("X-Auth-Token") or ""]
        raw = self.headers.get("Cookie") or ""
        for part in raw.split(";"):
            k, _, v = part.strip().partition("=")
            if k == "rpc_token":
                cands.append(unquote(v))
                break
        return any(_token_eq(c, self._token) for c in cands)
```

模块级：

```python
def _token_eq(a, b) -> bool:
    if not a or not b:
        return False
    try:
        return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
    except (AttributeError, TypeError):
        return False


def _mask_token(t: str) -> str:
    return f"{t[:4]}…{hashlib.sha256(t.encode('utf-8')).hexdigest()[:8]}" if len(t) > 4 \
           else f"…{hashlib.sha256(t.encode('utf-8')).hexdigest()[:8]}"
```

**L402-416 响应头**：

```python
    def _common_headers(self, code):
        self.send_header("Referrer-Policy", "no-referrer")
        if code in (302, 401):
            self.send_header("Cache-Control", "no-store")

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._common_headers(code)
        self.end_headers()
        self.wfile.write(body)
```

`_text` 同构；新增：

```python
    def _redirect(self, location, cookie=None):
        self.send_response(302)
        self.send_header("Location", location)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", "0")
        self._common_headers(302)
        self.end_headers()
```

**L427-433 `do_GET` 引导**：

```python
    def do_GET(self):
        u = urlparse(self.path)
        path = u.path
        if path in ("/", "/index.html"):
            qs = parse_qs(u.query)
            if "token" in qs:
                if not self._bootstrap_allowed():
                    return self._json(401, {"error": "unauthorized"})
                cand = qs["token"][0] if qs["token"] else ""
                if not _token_eq(cand, self._token):
                    return self._json(401, {"error": "unauthorized"})
                cookie = f"rpc_token={quote(self._token, safe='')}; HttpOnly; SameSite=Strict; Path=/"
                return self._redirect("/", cookie=cookie)
            return self._text(200, self._page)
        ...
```

```python
    def _bootstrap_allowed(self):
        return (self._host in ("127.0.0.1", "localhost", "::1")
                and self.client_address[0] in ("127.0.0.1", "::1"))
```

**日志脱敏**：

```python
    def log_message(self, fmt, *args):
        msg = re.sub(r"([?&]token=)[^&\s\"]+", r"\1***", fmt % args)
        super().log_message("%s", msg)
```

**L1388-1451 `serve`**：

```python
    explicit = token is not None
    token = token or secrets.token_urlsafe(9)
    Handler._token = token
    Handler._host = host
    token_file = None
    if not explicit:
        p = Path.home() / ".local" / "share" / "rpc" / "web-token"
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(token + "\n", encoding="utf-8")
            os.chmod(p, 0o600)
            token_file = p
        except OSError as e:
            print(f"[cluster-web] 无法写 token 文件 {p}: {e} —— 请用 --token 显式指定")
            return 1
    ...
    for line in _startup_lines(port, token, token_file):
        print(line)
```

```python
def _startup_lines(port, token, token_file):
    return [
        "[cluster-web] 三机推理框架管理 UI 已启动 (按需服务, Ctrl-C 退出)",
        f"[cluster-web]   token: {_mask_token(token)}"
        + (f" (文件 {token_file})" if token_file else " (来自 --token)"),
        f"[cluster-web]   打开: http://127.0.0.1:{port}/  "
        f"(loopback 首次用 ?token= 引导；token 见{'文件' if token_file else '启动参数'})",
        f"[cluster-web]   监听: {port} (localhost 与 127.0.0.1 均可用)",
    ]
```

### 4.9 `ops/rpc_check.py`

**L5065-5068 `[mpath]`**：

```python
    "printf '\\n[mpath]\\n'; for f in /etc/llama-instances/*.env; do [ -e \"$f\" ] || continue; "
    "a=${f##*/}; a=${a%.env}; "
    "CG=$(command -v conf-get 2>/dev/null || echo /usr/local/bin/conf-get); "
    "p=$(\"$CG\" \"$f\" MODEL_PATH 2>/dev/null); rc=$?; "
    "if [ \"$rc\" -ne 0 ] || [ -z \"$p\" ]; then echo \"$a NO_MODEL_PATH\"; "
    "elif [ -f \"$p\" ]; then echo \"$a OK\"; else echo \"$a MISSING $p\"; fi; done; "
```

**L6028-6029 `STATION_BINS`**：

```python
STATION_BINS = ("infer-load", "infer-unload", "infer-list", "llama-serve-instance",
                "rpc-serve-instance", "cluster-ttl", "load-mem-gate", "wait-gtt-release",
                "load-gate", "model-locate.sh", "conf-lib.sh", "conf-get")
```

同段注释"第 9 件"改为"12 件"；README 的"9 件"同步。

---

## 5. 接口实现

### 5.1 站上接口

| 接口 | 输入 | 输出 | 失败语义 |
|---|---|---|---|
| `model_scan [root]` | 可选根目录 | `alias\|model_dir\|size_mb\|main_gguf` 每行 | 无匹配 ⇒ 空输出、rc=0（由调用方判空） |
| `model_aliases [root]` | 可选根目录 | 每行一个 alias | 空输出 |
| `model_file_for_alias <alias> [root]` | alias | 绝对路径一行 | 找不到 rc=1 |
| `conf_escape <value>` | 任意单行值 | 转义内容 | 换行 rc=2 |
| `conf_set_kv <file> <key> <value>` | 合法键 / 单行值 | 无输出 | IO 1 / 值非法 2 |
| `conf_get_kv <file> <key>` | — | 反转义值 | 缺失/解析失败 1 |
| `conf-get <file> <key>` | — | 同 `conf_get_kv` | 同上 |

### 5.2 主控接口

| 接口 | 输入 | 输出 | 失败语义 |
|---|---|---|---|
| `parse_conf(text)` | conf 文本 | `dict` | 不抛（宽松解析） |
| `get_value(text, key)` | conf 文本 + 键 | 值或 `""` | 不抛 |
| `_pp_listen_ip(coord, worker)` | 站代号 | IP 或 `""` | 找不到/多义/非法 ⇒ `""` |
| `_build_infer_load_cmd(..., pp_listen=None)` | 参数 | 远端命令 | 非法 IP ⇒ `ValueError` |
| `_token_eq(a, b)` | 候选/真值 | bool | 空/类型不符 ⇒ False |
| `_auth_ok()` | Header + Cookie | bool | 恒 401 语义由调用方统一 |

---

## 6. 兼容性与迁移

| 场景 | 兼容策略 |
|---|---|
| 历史 conf 值**无引号** | `conf_get_kv` / `parse_conf` 兼容；新写入一律加引号 |
| 历史 conf 值含**未知转义**（`\x`） | 原样保留（只消费 `\\ \" \$ \`` 四类） |
| 历史 conf 含**重复键** | 读侧取首个；写侧删除重复行（下一次写该键时收敛） |
| `rpc_check` 读 `MODEL_PATH` | 走站上 `conf-get`；其它键保持 `sed` |
| 旧 Web 书签仍带 `?token=` | loopback 下仍可用：校验后 302 到 `/`，Cookie 生效；非 loopback ⇒ 401 |
| 前端 `localStorage` 旧 token | 保留手输回退；Cookie 优先；不再写 query token |
| ds4 旧 conf 的 `PP_LISTEN=0.0.0.0` | 单机不使用；coordinator 若显式写了 `0.0.0.0` 仍会按 conf 使用 —— 手册要求改成直连段 IP；本批不强制改写旧 conf |
| 旧 `infer-list` 对端 | 本机 payload 会发送新函数定义，不要求对端先部署 |
| 部署顺序 | 先库、后调用方；`STATION_BINS` 在库部署后才扩，避免门禁假红 |

---

## 7. 错误处理实施

| 场景 | 实现动作 | 退出/响应 |
|---|---|---|
| alias 无匹配 | 打印 `model_aliases` 候选 + 原名 | `infer-load` exit 1 |
| 模型文件找不到 | 打印候选 + 原名 | exit 1 |
| conf 值含换行 | `conf_escape` rc=2；`conf_set_kv` 不创建临时文件 | exit 1 |
| `mktemp`/`tee`/`chmod`/`mv` 失败 | 清理临时文件，原 conf 不动 | rc=1；调用方 exit 1 |
| `conf-get` 缺失/非 0 | `NO_MODEL_PATH` | 门禁条目判红/告警 |
| `--pp-listen` 含非法字符 | 参数阶段拒绝 | exit 1 |
| coordinator 无显式 PP IP | 打印直连段要求 | exit 1 |
| `net.yaml` 读不到 / 段缺失 / 多义 | `_pp_listen_ip` 返回空 | `_load_ds4_pp` 在起 worker前 return 1 |
| token 文件写失败 | 打印错误 + 指示用 `--token` | `serve` return 1 |
| `?token=` 非 loopback | 401，不设置 Cookie | HTTP 401 |
| token 比较失败 | 统一 401 JSON，不回显 | HTTP 401 |
| Web 请求日志 | `log_message` 把 token 值替换为 `***` | 日志不含完整 token |

---

## 8. 不变式实施

| 不变式（DESIGN §6） | 实施落点 | 机器判据 |
|---|---|---|
| 1. 单一写入口 | `conf_set_kv` 是唯一关键键写入口；`_set_conf_key` 只是薄包装 | 源码断言 `infer-load` 无 `sed -i` |
| 2. 单一站上扫描 | `model_scan` 是唯一别名/定位实现；两脚本 `source` 同一库 | `test_model_locate.py` 源码断言 + 三落点行为 |
| 3. 写读互逆 | `conf_escape` / `conf_get_kv` / `parse_conf` 固定转义集 | `test_conf_lib.py` 三方逐字节比对 |
| 4. 默认安全 | 单机 ds4 不传 `--listen`；coordinator 无显式 IP 即中止 | `test_cluster_pp_listen.py` + 静态断言 |
| 5. token 不入 URL/日志 | loopback 引导 302 剥离 query；`log_message` 脱敏；启动日志掩码 | `test_cluster_web_auth.py` |
| 6. 无新 daemon/入口 | 仅新增两个被 `source` 的库 + 一个 CLI 薄壳 | 目录清单/门禁 |
| 7. P2 不扩权 | #5/#6/#8/#9/CI 未触碰 | diff 范围 |

---

## 9. 测试策略

### 9.1 先验红 → 后验绿矩阵

| # | 先验红场景（实现前必须 FAIL） | 修复后断言（实现后 PASS） | 测试文件 |
|---|---|---|---|
| 3 | 临时根目录造 `gguf/<repo>/<f>.gguf`（depth-1） | `model_aliases` 含 repo；`model_file_for_alias` 返回该文件 | `test_model_locate.py` |
| 3 | 造 `gguf/<repo>/<Model>-GGUF/<f>` 与 `.../<QUANT>/<f>` | 两者 alias 均为 `<model>`，主文件正确 | 同上 |
| 3 | 源码读 `infer-load` | 不再含 `-maxdepth 2 -type d` | 同上 |
| 4 | 值含空格/`&`/`\|`/`"`/`\`/`$`/`` ` ``/`*` | `source`、`conf_parse`、`conf-get` 三方逐字节一致 | `test_conf_lib.py` |
| 4 | 值含换行 | `conf_set_kv` rc=2，原文件逐字节不变 | 同上 |
| 4 | conf 键缺失 | `conf-get` rc=1 | 同上 |
| 7 | 未设 `PP_LISTEN` 起 coordinator | `infer-load` exit 1（静态/干跑断言） | `test_cluster_pp_listen.py` |
| 7 | `_pp_listen_ip("B","C")` / `("A","C")` / `("A","B")` | 返回 `10.10.11.1` / `10.10.12.1` / `10.10.10.1` | 同上 |
| 7 | `_build_infer_load_cmd` 含/不含 `pp_listen` | 含时追加 `--pp-listen '<ip>'`；非法 IP 抛 `ValueError` | 同上 |
| 10 | `/?token=<token>` | 302 + `Set-Cookie`（HttpOnly/SameSite=Strict/Path=/）+ 空 body | `test_cluster_web_auth.py` |
| 10 | 非 loopback + query token | 401，无 `Set-Cookie` | 同上 |
| 10 | Header / Cookie 鉴权 | 正确 ⇒ True；错误/空 ⇒ False | 同上 |
| 10 | 响应头 | 所有响应含 `Referrer-Policy: no-referrer`；401/302 含 `no-store` | 同上 |
| 10 | 启动日志 | `_startup_lines` 不含完整 token | 同上 |
| 10 | 源码 | `_auth_ok` 使用 `compare_digest` | 同上 |

### 9.2 测试实现要点

- **bash 定位**：`test_conf_lib.py` / `test_model_locate.py` 依次尝试 `shutil.which("bash")`、`C:\Program Files\Git\usr\bin\bash.exe`、`C:\Program Files\Git\bin\bash.exe`；**找不到即 FAIL**（不静默跳过）。
- **登录 shell**：Git Bash 必须以 `-lc`（或显式补 `/usr/bin` 到 PATH）执行 —— 2026-10-27 实测：非登录 shell 下 `dirname/mktemp/sed/find/awk` 全部 `command not found`，脚本会以"目录解析为空"的假象失败。
- **路径形态**：Windows 路径转 POSIX（`D:\RPC` → `/d/RPC`），复用 [rpc_check.py](../../ops/rpc_check.py) 的 `_posix` 同型逻辑。
- **变量传递**：特殊字符值走环境变量传入 shell，避免 PowerShell/cmd 二次转义；换行用例在 shell 内用 `$'a\nb'` 构造。
- **三方比对**：`source` 结果由 shell `printf` 输出；`conf_parse.get_value` 直接读文件；`conf-get` 作为子进程输出；三者逐字节比较。
- **Web 行为测试**：`Handler._token/_page/_host` 直接设值；`ThreadingHTTPServer(("127.0.0.1", 0))` 起临时端口；只访问 `/` 与 `/?token=`，不触发 SSH 聚合端点。
- **单元导入**：`test_cluster_pp_listen.py` 沿用 [test_cluster_pure.py](../../tests/test_cluster_pure.py) 的 `sys.path.insert(0, ROOT/"ops")` + `import cluster` 模式。
- **RESULT 行**：每个测试末尾打印 `RESULT: <通过数>/<总数> ...`。

### 9.3 门禁与真站证据

| 门禁 | 期望 |
|---|---|
| `py-tests` | 新增 5 个测试全绿；既有测试不退化 |
| `doclinks` | 本文与 DESIGN 的相对链接可解析 |
| `md-tables` | 新增文档 0 条列数违规 |
| `stations` | 三站 12 件 md5 一致；新件 `bash -n` 通过 |
| `gates` | 不因本批新增 FAIL；`STATION_BINS` 扩项后仍 PASS |
| `spec-untested` | 新 spec 文档通过 |
| 真站只读证据（#3） | 在 B 站跑 `model_file_for_alias davidau-q38-27b-q4k`，验证 depth-1 落点；与 `infer-list` 行一致 |
| 真站只读证据（#4） | 在 B 站跑 `conf-get /etc/llama-instances/<alias>.env MODEL_PATH`，与 `test -f` 一致 |
| 真站按需证据（#7） | 需先卸现役实例并经用户同意；不在默认实施步骤内执行 |

---

## 10. 实施顺序

> 顺序依据：调研 §5.1（风险 × 成本）与部署依赖。

1. **#10**：改 `cluster_web.py` + 写 `test_cluster_web_auth.py`（先红后绿）→ `py-tests` 单跑通过。
2. **#4 本地**：新增 `conf-lib.sh` / `conf-get` / `conf_parse.py` + 两个测试 → 本地绿。
3. **#4 部署**：三站备份 → 部署两个站上件 → md5 + `bash -n` + `conf-get` 冒烟。
4. **#4 接入**：改 `infer-load` 写入口 + `rpc_check [mpath]` → 部署 `infer-load` → `rpc_check --only stations,py-tests` 绿。
5. **#3 本地**：新增 `model-locate.sh` + `test_model_locate.py` → 本地绿。
6. **#3 部署与接入**：部署 `model-locate.sh` → 改 `infer-load` / `infer-list` → 部署 → B 站只读证据。
7. **#7**：改 `infer-load` ds4 分支 + `cluster.py` → 单测绿 → 不自动做真站 PP 加载。
8. **#11 门禁**：`STATION_BINS` 扩项 + README 清单 → `rpc_check --only stations` 绿。
9. **#13 文档**：手册 + INDEX → `doclinks` / `md-tables` / `doc-status` 绿。
10. **全量**：`py tests\run_py_tests.py` + `rpc_check` 全量 → 记录证据。

**每步的"先红"要求**：新增测试必须先跑出 FAIL（证明测的是缺口），再实现至 PASS；否则该测试不算判据。

---

## 11. 与设计的一致性对齐

| DESIGN 条目 | 实施落点 | 一致性 |
|---|---|---|
| §4.1 `model_scan` / `model_aliases` / `model_file_for_alias` | T7 / §4.1 | 一致；额外约束"函数内部兜底默认 root"以支持 `declare -f` 传输 |
| §4.2 conf 格式与转义集 | T2 / §4.2 | 一致；NUL 以"bash 变量不可表示"处理，测试钉换行 |
| §4.3 `conf_escape` / `conf_set_kv` / `conf_get_kv` | T2 / §4.2 | 一致；`sudo -n` 与 `tee` 同身份是新增实现细节 |
| §4.4 `parse_conf` / `get_value` | T4 / §4.4 | 一致；函数内导入避免依赖图扩边 |
| §4.5 `infer-load` 变更 | T5 / T8 / T9 / §4.6 | 一致；`_set_conf_key` 保留为薄包装（调用形状不变） |
| §4.6 `cluster.py` 变更 | T10 / §4.5 | 一致；`_pp_listen_ip` 用行解析而非 PyYAML（零依赖） |
| §4.7 Web 变更 | T1 / §4.8 | 一致；新增 `log_message` 脱敏（DESIGN §3.5 "日志不含 token"的直接实现） |
| §4.8 `rpc_check` 变更 | T6 / T11 / §4.9 | 一致 |
| §6 不变式 | §8 | 逐条有落点 |
| §7 错误处理 | §7 | 逐条有动作 |
| §8 测试策略 | §9 | 先验红矩阵一一对应 |
| §10 实施顺序 | §10 | 一致（#10 → #4 → #3 → #7） |

**显式偏差（均不扩大射程）**：

1. **单机 ds4 不传 `--listen`**：DESIGN §3.4 的"单机默认 127.0.0.1"按"PP_LISTEN 变量默认值"落地；引擎单机绑定不在本批射程（无 `--listen` 参数证据），HTTP 面已由 `--host 127.0.0.1` 固定。
2. **`_pp_listen_ip` 行解析**：DESIGN 未规定解析器；选零依赖的行扫描，并用真实 `net.yaml` 三组断言钉住格式。
3. **Cookie 值 URL 编码**：DESIGN 未提；为防止用户 `--token` 含 `;`/空格破坏 `Set-Cookie`，写入时 `quote`、读取时 `unquote`。

---

## 12. 设计评审（幻觉排除，Step 4 第一遍）

> 本节目的是把"文档里写的"逐条对回代码/外部事实，标出**已验证**、**待实施时验证**、**不声称**三类。

### 12.1 已验证的代码事实（E1）

| 断言 | 证据 |
|---|---|
| `_auth_ok` 当前用 `==` | [cluster_web.py L399-400](../../ops/cluster_web.py#L399-L400) |
| 启动日志当前打印含 token 的 URL | [cluster_web.py L1436-1438](../../ops/cluster_web.py#L1436-L1438) |
| `do_GET` 当前先剥 query 再比较 `/` | [cluster_web.py L427-433](../../ops/cluster_web.py#L427-L433) |
| `infer-load` 首次生成 conf 的 `REPO` 用 depth-2 目录 | [infer-load L115-118](../../ops/station-bin/infer-load#L115-L118) |
| `infer-load` 的 `MODEL_PATH=${F}` 无引号 | [infer-load L135-150](../../ops/station-bin/infer-load#L135-L150) |
| `_set_conf_key` 用 `sed -i` 且 `$2` 未转义 | [infer-load L174-189](../../ops/station-bin/infer-load#L174-L189) |
| coordinator 默认 `PP_LISTEN:-0.0.0.0` | [infer-load L392-396](../../ops/station-bin/infer-load#L392-L396) |
| `_load_ds4_pp` 未传 `PP_LISTEN` | [cluster.py L1517-1551](../../ops/cluster.py#L1517-L1551) |
| `_parse_conf` 只剥引号、不反转义 | [cluster.py L236-245](../../ops/cluster.py#L236-L245) |
| `rpc_check [mpath]` 用 `tr -d '"'` 读 `MODEL_PATH` | [rpc_check.py L5065-5068](../../ops/rpc_check.py#L5065-L5068) |
| `STATION_BINS` 当前 9 件 | [rpc_check.py L6028-6029](../../ops/rpc_check.py#L6028-L6029) |
| B-C 段 B=`10.10.11.1` / C=`10.10.11.3`；A-C 段 A=`10.10.12.1` | [net.yaml L58-L76](../../inventory/net.yaml#L58-L76) |
| `infer-list` 已按文件分组 | [infer-list L63-90](../../ops/station-bin/infer-list#L63-L90) |

### 12.2 外部事实（E3）

| 断言 | 依据 |
|---|---|
| `find -maxdepth` 相对起点计层，depth-1 仓库目录不会被 depth-2 命中 | 调研 §3.1（GNU Findutils） |
| `sed` 替换串的 `&`/分隔符/`\` 需转义；`sed -i` 非原子 | 调研 §3.2（GNU sed） |
| `printf '%q'` 产出 `$'...'`，文本解析器不认 | 调研 §3.2（Bash/GNU printf） |
| CWE-1327：`0.0.0.0` = 全接口暴露 | 调研 §3.3 |
| `hmac.compare_digest` 避免内容相关短路 | 调研 §3.4（Python docs） |
| RFC 6750 §2.3：URI query 中的 token 容易被记录 | 调研 §3.4 |
| `BaseHTTPRequestHandler.log_request` 会打印 requestline（含 query） | Python stdlib 行为；本批用 `log_message` 覆写兜住 |

### 12.3 实施时必须现场验证（不假装已验证）

| 项 | 验证方式 | 失败时 |
|---|---|---|
| 三站 `sudo -n` 可用 | `ssh <st> 'sudo -n true'` | `conf_set_kv` 失败 → 改用手工 `sudo` 部署或调整权限（响亮失败，不静默） |
| `ds4-server` 单机是否已有默认绑定 | 不验（本批不传 `--listen`） | 若后续评审要求收敛，单独立项（P2） |
| `conf-get` 在非交互 ssh 的 PATH | 部署后 `ssh <st> 'command -v conf-get'` | 用 `[mpath]` 的绝对路径回退 `/usr/local/bin/conf-get` |
| token 文件在 Windows 的 0600 语义 | `os.chmod` best-effort + 文档说明 | POSIX 站上仍严格 0600 |
| Cookie 与 `X-Auth-Token` 并存 | 行为测试 + 浏览器手测 | 保留 Header 回退，不影响旧用法 |

### 12.4 本地草图验证（2026-10-27）

> 目的：在写代码前先证明文档里的关键草图**可运行**，减少 Step 4 的"纸上正确"。

| 草图 | 验证 | 结果 |
|---|---|---|
| `conf-lib.sh` + `conf-get` | Git Bash 5.2.37：含空格 / `&` / 竖线 / 双引号 / 反斜杠 / `$` / 反引号 / `*` 的值写入 → `source` / `conf-get` / `conf_parse.py` 三方比对；换行拒绝后文件 md5 不变；注释与其它键保留；无临时文件残留 | **PASS**（三方逐字节一致；`chmod --reference` 可用） |
| `model-locate.sh` | 临时根目录造三种落点 + `mmproj` + 含竖线的目录；断言 alias/主文件/rc | **PASS**（三种落点、mmproj 排除、`model_file_for_alias` 对含竖线路径返回正确） |
| `_pp_listen_ip` | 对真实 [net.yaml](../../inventory/net.yaml) 跑 `(B,C)/(A,C)/(A,B)/(C,B)/(A,A)` | **PASS**（`10.10.11.1` / `10.10.12.1` / `10.10.10.1` / `10.10.11.3` / `""`） |
| `conf_parse.py` | 解析 `conf-lib.sh` 产出的 conf | **PASS**（原值逐字节还原；`\q` 未知转义原样保留） |

### 12.5 不声称

- 不声称 `ds4-server` 在**所有**单机形态都只绑回环；本批只保证**我们传的参数**不出现 `0.0.0.0`。
- 不声称新 `conf` 读侧能兼容任意历史脏值；只兼容"带/不带引号 + 固定四类转义"，歧义值按未知转义原样保留。
- 不声称 `model_scan` 的性能优于旧实现；它只消除两套规则，复杂度同量级。
- 不声称 Cookie 方案能防本机恶意进程；它只收敛"token 进 URL/日志"的泄露面。

---

## 13. 风险与回滚

| 风险 | 影响 | 缓解 | 回滚 |
|---|---|---|---|
| 新库未部署但调用方已改 | `infer-load`/`infer-list` source 失败、门禁红 | 部署顺序：先库后调用方；`STATION_BINS` 后扩 | 恢复调用方旧版（`git checkout` + 部署） |
| `conf_set_kv` 的 `sudo -n` 不可用 | 无法改 conf | 失败即 rc=1，不写半文件 | 手工编辑 conf（保留旧行为） |
| `chmod --reference` 不兼容 | 写入失败 | 测试先红 | 改用 `stat -c %a` + `chmod`（记录偏差） |
| `model_scan` 对超大模型库变慢 | 首次 conf 生成变慢 | 与 `infer-list` 同量级；`find` 单次 | 保留旧 `REPO` 代码路径（临时） |
| 名 alias 跨仓库 | 取到非预期模型 | 与旧 `head -1` 同语义；诊断打印候选 | 手工 conf 钉 `MODEL_PATH` |
| `net.yaml` 格式改动 | `_pp_listen_ip` 返回空 ⇒ PP 中止 | 测试钉真实三组；中止而非猜 | 旧行为（`0.0.0.0`）**不**恢复；改 conf 显式 `PP_LISTEN` |
| 旧 ds4 conf 显式 `PP_LISTEN=0.0.0.0` | coordinator 仍暴露 | 手册要求改直连段 IP；日志打印实际值 | 改 conf 为直连段 IP |
| Cookie 与旧 localStorage 冲突 | 前端提示/401 抖动 | 双通道 + 401 才显示登录框 | 纯 Header 模式（保留 `_auth_ok` 头分支） |
| Windows 行尾 CRLF | 站上脚本语法错误 | `.gitattributes` 已锁 LF；部署前 `bash -n` | 重新检出/`dos2unix` |
| 测试依赖 Git Bash | `py-tests` 在无 bash 环境红 | 明确 FAIL 信息（不静默跳过） | 在具备 Git Bash 的主控执行 |

**回滚粒度**：

1. **单文件**：`git checkout -- ops/<file>` → 重新部署 → `bash -n` → md5 对账。
2. **站上件**：`cp -a /usr/local/bin/<name> /usr/local/bin/<name>.bak-p1review-20261027`（部署前）→ 回滚时 `cp -a` 反向覆盖。
3. **Web**：停 `cluster.py web`，回到旧版本；Cookie 可留（无副作用）。
4. **ds4**：conf 里显式 `PP_LISTEN=<直连段 IP>` 即可脱离对 `_pp_listen_ip` 的依赖。
