# 设计文档：原始评审 P1 四条修复

---

id: review-p1-remediation-DESIGN
type: design
version: 1.0
status: draft
date: 2026-10-27
depends: [ADR-0004, ADR-0014]
upstream: null

---

> **Feature**: 修复 2026-10-21 原始评审报告 RPC 段的四条 P1——模型定位、conf 引号/转义、ds4 coordinator 监听默认、Web UI token——在不引入新 daemon、不改变推理引擎路线的前提下，把四处"默认不安全 / 同源规则脱钩 / 文本读写不一致"收敛为可判定的契约。
> **创建日期**: 2026-10-27
> **状态**: draft（Step 2 DESIGN；实施展开见 [IMPLEMENTATION.md](./IMPLEMENTATION.md)）
> **Spec 步骤**: Step 2（DESIGN）
> **基于调研**: [原始评审 P1 社区外部锚点调研](../../docs/research/2026-10-26_原始评审P1_社区外部锚点调研.md) · [原始评审报告复核矩阵](../../docs/research/2026-10-26_原始评审报告复核_RPC.md)
> **代码基线**: `0c53fcc3`（`main`；行号为该基线快照）

---

## 1. 设计目标

1. **#3 模型定位**：站上只保留**一份**"别名 → 模型文件"规则；`infer-load` 首次生成 conf 与 `infer-list` 共用同一实现，按**文件**枚举，不再假设固定目录深度。
2. **#4 conf 写入**：conf 的写入口只有**一个**（双引号 + 转义 + 原子替换）；读入口与之**逐字节一致**（bash `source`、`cluster.py` 解析、`rpc_check` 权重存在性检查）。
3. **#7 ds4 监听**：安全默认 = `127.0.0.1`；PP 必须由编排层**显式**传 coordinator 的直连段 IP；传不出即**响亮中止**，绝不退回 `0.0.0.0`。
4. **#10 Web token**：常量时间比较；`?token=` 只作 **loopback 一次性引导**换 HttpOnly Cookie，随后 302 剥离 query；所有响应 `Referrer-Policy: no-referrer`；日志不再出现完整 token。

**不做**（P2，见调研 §5.4）：

- 不扫荡 `set -euo`（#5）、不改遗留 systemd 单元（#6）、不收敛全部硬编码（#9）、不拆文件/分目录（#8）、不接 CI。
- 不引入常驻控制器 / 第二管理入口（ADR-0004）。
- 不做完整 OAuth/JWT 资源服务器；不改变 ds4/llama.cpp 引擎内部。
- 不为 #7 新增门禁（只在启动日志留痕；门禁告警列入 P2）。

---

## 2. 设计依据

### 2.1 调研结论 → 设计决策

| 调研结论（外部锚点） | 本仓缺口 | 设计决策 | 证据 |
|---|---|---|---|
| GNU `find` 的 `-maxdepth` 是相对起点的层数 | `infer-load` 用 depth-2 目录找仓库，仓库级直放（depth-1）必漏 | 改为**文件级枚举 + 路径分组**；抽共享 `model-locate.sh` | 调研 §3.1；E1 |
| ShellCheck SC2086：未引用展开会分词/glob | conf 写入值不加引号 | 写入口统一 `KEY="<escaped>"` | 调研 §3.2；E1 |
| GNU sed 替换串中 `&`/分隔符/`\` 需转义 | `sed -i` 就地改 conf，`$2` 未转义 | **弃用 `sed -i`**；`mktemp` + 原子 `mv`；显式检查 rc | 调研 §3.2；E1 |
| Bash `%q` 只保证 shell 可重读，不保证文本解析器可读 | `rpc_check` 用 `tr -d '"'` 读 `MODEL_PATH` | 不采用 `%q`；采用双引号 + 有限转义；读侧同步升级 | 调研 §1.1/§3.2；E1 |
| CWE-1327：`0.0.0.0` = 全接口暴露 | ds4 coordinator 默认 `0.0.0.0` | 默认 `127.0.0.1`；PP 显式传直连段 IP；缺失即中止 | 调研 §3.3；E1 |
| PostgreSQL/Ollama 默认回环，暴露须显式 | 单机 ds4 也默认全接口 | 单机默认回环；PP 由编排层传参 | 调研 §3.3；E3 |
| Python `hmac.compare_digest` 避免内容相关短路 | Web token 用 `==` | `compare_digest`；失败统一 401 | 调研 §3.4；E1 |
| RFC 6750 §2.3：URI query 中的 token 很可能被记录 | `?token=` 长期留在 URL/日志 | 仅 loopback 一次性引导 → Cookie + 302；日志脱敏 | 调研 §3.4；E3 |
| MDN `Referrer-Policy: no-referrer` | 响应未设 referrer 策略 | 所有响应加 `no-referrer` | 调研 §3.4；E3 |

### 2.2 约束

| 约束 | 来源 | 对设计的影响 |
|---|---|---|
| 唯一管理面 = `cluster.py`；不新增并列入口/daemon | ADR-0004 | 共享库只被既有站上脚本 `source`，不新增服务 |
| halogen 容器路径与 `CONTAINER_MODELS` 单一真值 | ADR-0014 | 本批不碰容器路径；#3 只改 llama 模型库定位 |
| 站上是 bash，不保证 Python | `ops/station-bin` 现状 | `model-locate.sh` / `conf-lib.sh` 必须是纯 bash；Python 解析只在主控侧 |
| 站上件部署一致性由 `STATION_BINS` 逐字节 md5 判 | `rpc_check.py` | 新共享库必须加入 `STATION_BINS` 并部署到 `/usr/local/bin/` |
| conf 只被 bash `source`，不是 systemd `EnvironmentFile` | 调研 §1.1 | 不引入 systemd 引号规则；以 bash + 文本解析器双读者为准 |
| 既有退出码 `0/1/2` | ADR/既有调用方 | 本批只用 `0/1`；不新增数字码 |

### 2.3 职责边界

- **职责内**：`ops/station-bin/infer-load`、`infer-list`、新增 `model-locate.sh`/`conf-lib.sh`/`conf-get`；`ops/cluster.py` 的 `_parse_conf`/`_build_infer_load_cmd`/`_load_ds4_pp`/新增 `_pp_listen_ip`；`ops/cluster_web.py` 的鉴权/引导/响应头/日志；`ops/rpc_check.py` 的 `[mpath]` 读取与 `STATION_BINS`；测试与文档。
- **职责外**：引擎内部（llama.cpp/ds4）；权重分发；systemd 单元定义；P2 五项；容器路径。

### 2.4 现状事实（E1，代码基线 `0c53fcc3`）

| # | 事实 | 位置 |
|---|---|---|
| 3 | `ALL_ALIASES` 已是文件级；但首次生成 conf 的 `REPO` 仍是 `-mindepth 2 -maxdepth 2 -type d` | [infer-load L70](../../ops/station-bin/infer-load#L70)、[L115](../../ops/station-bin/infer-load#L115) |
| 3 | `infer-list scan()` 已按文件分组；三种落点由 `cluster_model` 定义 | [infer-list L63-L82](../../ops/station-bin/infer-list#L63-L82)、[cluster_model.py L46-L53](../../ops/cluster_model.py#L46-L53) |
| 4 | conf 首次生成 `MODEL_PATH=${F}`；`_set_conf_key` 用 `sed -i` 且 `$2` 未转义 | [infer-load L135-L150](../../ops/station-bin/infer-load#L135-L150)、[L174-L189](../../ops/station-bin/infer-load#L174-L189) |
| 4 | 文本读者：`rpc_check` 用 `tr -d '"'`；`cluster._parse_conf` 只剥引号、不反转义 | [rpc_check.py L5066](../../ops/rpc_check.py#L5066)、[cluster.py L236-L245](../../ops/cluster.py#L236-L245) |
| 7 | coordinator 默认 `PP_LISTEN:-0.0.0.0`；`_load_ds4_pp` 未传 `PP_LISTEN` | [infer-load L392-L396](../../ops/station-bin/infer-load#L392-L396)、[cluster.py L1535-L1544](../../ops/cluster.py#L1535-L1544) |
| 7 | B-C 直连段 IP：B=`10.10.11.1`、C=`10.10.11.3` | [inventory/net.yaml L59-L68](../../inventory/net.yaml#L59-L68) |
| 10 | `_auth_ok` 用 `==`；启动日志打印含 token 的 URL | [cluster_web.py L399-L400](../../ops/cluster_web.py#L399-L400)、[L1437-L1438](../../ops/cluster_web.py#L1437-L1438) |

---

## 3. 架构设计

### 3.1 共享层与部署

新增三个站上件（**同一份实现，两处消费**）：

| 文件 | 职责 | 部署 |
|---|---|---|
| `ops/station-bin/model-locate.sh` | 纯函数：模型枚举、别名、主 gguf 选择 | `/usr/local/bin/model-locate.sh` |
| `ops/station-bin/conf-lib.sh` | 纯函数：conf 转义、原子写、读 | `/usr/local/bin/conf-lib.sh` |
| `ops/station-bin/conf-get` | CLI 薄壳：`conf-get <file> <key>` | `/usr/local/bin/conf-get` |

主控侧新增：

| 文件 | 职责 |
|---|---|
| `ops/conf_parse.py` | Python 侧 conf 解析（与 `conf-lib.sh` 同一格式）；`cluster._parse_conf` 委托它 |

**source 定位**（站上脚本）：优先 `BASH_SOURCE[0]` 的实路径，其次 `command -v`，再退到 `/usr/local/bin`：

```bash
_self=${BASH_SOURCE[0]}
[ "${_self#*/}" = "$_self" ] && _self=$(command -v -- "$_self" || true)
HERE=$(cd "$(dirname "$(readlink -f "$_self")")" && pwd)
. "$HERE/model-locate.sh"
```

**部署纪律**：三个新件加入 `rpc_check.py` 的 `STATION_BINS`；`stations` 门禁的逐字节 md5 会强制"仓库副本 == 站上件"。

### 3.2 #3 数据流

```
model-locate.sh
  model_scan(root) ──> alias|dir|size_mb|main_gguf
        ├── infer-list scan()        （清单）
        └── infer-load 首次生成 conf （model_file_for_alias）
```

- 规则：先 `find -L root -mindepth 2 -name '*.gguf'`（**文件级**），按路径分组：
  - `gguf/<repo>/<f>` → 模型 = `<repo>`；
  - `gguf/<repo>/<Model>-GGUF/<f>` 或更深 → 模型 = `<Model>`（`-GGUF` 去掉）。
- 别名归一化（含 minimax 重映射）只在库内做一次；`infer-list` 与 `infer-load` 不再各写一套。
- 主文件优先级保持现状：合并单文件（排除 `-of-0000`/`mmproj`，>1G）→ `-00001-of-*` → 任意。
- 找不到别名时，`infer-load` 打印 `model_scan` 的候选 alias 列表（诊断），再退出 1。

### 3.3 #4 数据流

```
infer-load ── conf_set_kv ──> conf 文件（KEY="escaped"，原子 mv）
                                  │
                    ┌─────────────┴─────────────┐
               bash source                文本读者
            （llama-serve-instance）     ├─ cluster.conf_parse.py
                                        └─ rpc_check [mpath] → conf-get
```

- 写入口：`conf_set_kv`（唯一）；首次生成 conf 的 `MODEL_PATH` 也走 `conf_escape`。
- 读入口：`source` 是运行时主读；文本读者用 `conf_parse.py` 或 `conf-get`，与写入的转义规则**逐字节互逆**。
- 不再使用 `sed -i` 改关键 conf；原子替换保留文件权限与注释行顺序。

### 3.4 #7 数据流

```
cluster.py _load_ds4_pp(alias, coord, worker)
  ├── _pp_listen_ip(coord, worker)  ← inventory/net.yaml 直连段（B-C: 10.10.11.1 / .3）
  ├── worker:  infer-load --backend ds4          （先起）
  └── coord:   infer-load --backend ds4 --pp-listen <coord_ip>  （后起）
```

- `infer-load` 单机（`PP_ROLE` 空/`single`）：`PP_LISTEN` 默认 `127.0.0.1`。
- `PP_ROLE=coordinator` 且未显式 `--pp-listen`/`PP_LISTEN`：**中止**，报"PP coordinator 需要一个可被 worker 访问的直连段 IP；不能默认 0.0.0.0"。
- `PP_ROLE=worker`：不使用 `PP_LISTEN`。
- 启动日志打印实际绑定地址（`listen=<ip>`）。
- `_davidau_start.sh` 作为一次性脚本保留 `0.0.0.0`，但在文件头标注"仅隔离网段、非生产路径"。

### 3.5 #10 数据流

```
GET /?token=T  ── loopback? ──> compare_digest(T, token)
    │                              ├─ 失败 → 401
    │                              └─ 成功 → Set-Cookie: rpc_token=T; HttpOnly; SameSite=Strict; Path=/
    │                                        302 /   （query 剥离）
    └─ 非 loopback → 401（禁用 query 引导）

后续请求：X-Auth-Token 头 或 rpc_token Cookie → compare_digest → 200
```

- `?token=` 只允许在 **loopback 绑定**时做引导；`--host 0.0.0.0` 时禁用，并要求显式 `--token` + header。
- 所有响应加 `Referrer-Policy: no-referrer`。
- token 落点：`--token` 优先；否则生成后写 `~/.local/share/rpc/web-token`（0600）；启动日志只打印路径与掩码（前 4 位 + 短 hash），不打印完整 token/URL query。
- 前端保留手动 token 输入（header 回退），但不再把 query token 存 localStorage；Cookie 由浏览器自动携带。

---

## 4. 接口定义

### 4.1 `model-locate.sh`

```bash
model_scan [root]                 # 输出 alias|model_dir|size_mb|main_gguf；root 默认 /data/models/gguf
model_aliases [root]              # 输出去重 alias（每行一个）
model_file_for_alias <alias> [root]  # 输出主 gguf 绝对路径；找不到输出空、rc=1
```

- 纯函数，无副作用；不写文件、不启动进程。
- `root` 参数只用于测试；生产调用不带参数。
- 输出字段不含裸 `|`（路径中的 `|` 作为字段内容保留；消费者按**前 3 个** `|` 切分，最后一个字段为完整路径）。若路径含 `|`，调用方必须用 `model_file_for_alias` 而不是 `model_scan` 的切分。
- 别名归一化与 `infer-list` 现行规则一致（含 `minimax-m2.7.*` → `m27-q4ks`）。

### 4.2 conf 格式（规范）

```
KEY="value-with-escapes"
```

- 转义集：`\\` → `\`、`\"` → `"`、`\$` → `$`、`` \` `` → `` ` ``。
- 值内**禁止**换行与 NUL；写入侧检测到即报错（rc=2），不写半行。
- 读取侧兼容历史未加引号的值；新写入一律加双引号。
- 空值写 `KEY=""`；读取侧返回空串。

### 4.3 `conf-lib.sh`

```bash
conf_escape <value>               # 输出转义后的内容（不带引号）；含换行/NUL ⇒ rc=2
conf_set_kv <file> <key> <value>  # 原子写；成功 rc=0，失败 rc=1（临时文件清理）
conf_get_kv <file> <key>          # 输出反转义值；缺失/解析失败 rc=1
```

- `conf_set_kv`：`mktemp` 同目录 → 按行重写（保留注释/顺序）→ `chmod --reference` → `mv`；任一步 `||` 清理并返回 1；不使用 `sed -i`。
- `conf_get_kv`：只读；不修改文件；按规范反转义。
- `conf-get` 是 `conf_get_kv "$1" "$2"` 的薄壳，便于 `rpc_check` 的 SSH 命令调用。

### 4.4 `conf_parse.py`（主控侧）

```python
parse_conf(text: str) -> dict[str, str]     # 反转义；忽略注释/空行
get_value(text: str, key: str) -> str       # 缺失返回 ""
```

- `cluster._parse_conf` 委托 `parse_conf`；`estimate_load` 的 `MODEL_PATH` 自动获得反转义。
- `rpc_check` 的 `[mpath]` 改用站上 `conf-get`；其他简单键（CTX/BACKEND 等）保持既有 `sed` 读取（这些键不允许特殊字符）。

### 4.5 `infer-load` 变更契约

- **#3**：`REPO`/`F` 定位改为 `F=$(model_file_for_alias "$ALIAS")`；为空时打印 `model_aliases` 候选并退出 1；不得再出现 `-maxdepth 2 -type d`。
- **#4**：首次生成 conf 的 `MODEL_PATH=` 使用 `conf_escape`；`_set_conf_key` 内部改用 `conf_set_kv`；失败 `|| exit 1`。
- **#7**：新增 `--pp-listen <ip>`；优先级 **CLI > 环境变量 > conf**（在 `source` 之后用保存的 CLI 值覆盖）；`PP_ROLE=coordinator` 未给 → 退出 1；单机默认 `127.0.0.1`；日志打印实际值。
- 既有 `--backend/--port/--ctx/--threads/--engine/--rpc-target` 语义不变。

### 4.6 `cluster.py` 变更契约

- `_build_infer_load_cmd(matched, backend, engine=None, rpc_target=None, pp_listen=None)`：仅在 `pp_listen` 非空时追加 `--pp-listen '<ip>'`（IP 由 `_pp_listen_ip` 校验，防注入）。
- `_pp_listen_ip(coord, worker) -> str`：读 `inventory/net.yaml` 的直连段（`segments`），返回 coordinator 在该段的 IP；找不到/多义 → 抛错/返回空，由 `_load_ds4_pp` **在起 worker 之前**中止。
- `_load_ds4_pp`：先 `_pp_listen_ip`，再起 worker，最后 `--pp-listen <ip>` 起 coordinator；顺序不变。
- 本批不新增 CLI 子命令。

### 4.7 `cluster_web.py` 变更契约

- `_auth_ok`：取 `X-Auth-Token` 头或 `rpc_token` Cookie；两者都用 `hmac.compare_digest` 与 `_token` 比较；空值/类型不符 → False；失败响应固定 `401 {"error":"unauthorized"}`。
- `do_GET`：`/?token=` 仅在 `self.client_address[0]` 为 `127.0.0.1`/`::1` 且 `--host` 为 loopback 时进入引导；校验通过 → `Set-Cookie` + `302 /`；否则 401（不回显 token）。
- `_json`/`_text`/302：统一加 `Referrer-Policy: no-referrer`；401/302 不缓存（`Cache-Control: no-store`）。
- 启动日志：不打印完整 token；打印 token 文件路径（auto 生成时）与掩码；打印 `http://127.0.0.1:<port>/`（无 query）。
- `--host` 非 loopback：禁用 query 引导；启动日志显式告警"仅允许 header/cookie 鉴权"。

### 4.8 `rpc_check.py` 变更契约

- `[mpath]` 块：`p=$(conf-get "$f" MODEL_PATH)`；`conf-get` 缺失/非 0 → 该条按 `NO_MODEL_PATH` 或显式错误处理，不静默通过。
- `STATION_BINS` 增加 `model-locate.sh`、`conf-lib.sh`、`conf-get`；`stations` 门禁的 md5 对账自动覆盖。
- 不新增 #7 门禁；仅在文档/手册记录"ds4 绑定实际值看启动日志"。

---

## 5. 替代方案（为什么不做）

| # | 方案 | 否决理由 |
|---|---|---|
| 3 | 只修 `infer-load` 的 `REPO`，保留两套规则 | 两个同源脚本仍会再次脱钩；评审的根因是"规则重复" |
| 3 | 站上跑 Python 复用 `cluster_model` | 站上不保证 Python 依赖；违反既有 bash 约束 |
| 4 | 直接 `printf '%q'` | `rpc_check` 的文本解析器不认 `$'...'`；会读错权重路径（E1） |
| 4 | 只加引号、不转义 | 路径含 `"`/`$`/`` ` `` 时 `source` 展开或截断 |
| 4 | 拒绝所有特殊字符 | 评审场景是含空格路径；拒绝合法路径不是修复 |
| 5 | 改为 JSON/TOML | 改动面过大，且 bash `source` 不再直接可用 |
| 7 | 保持 `0.0.0.0` + 防火墙 | CWE-1327 明确不建议依赖外部缓解；默认即暴露 |
| 7 | 默认取本机直连段 IP | 多直连段站（B 有 A-B/B-C）无法无歧义推导；必须由编排层按 PP 对显式给 |
| 10 | 完整 OAuth/JWT | 本地单用户 UI 过重；不解决"token 在 URL"这一具体风险 |
| 10 | query token + 短 TTL | 仍会进历史/Referer/日志；短 TTL 不改变泄露面 |
| 10 | 只改 `compare_digest` | 时序侧信道关了，URL/日志泄露仍在 |

---

## 6. 不变式（Invariants）

1. **单一写入口**：只有 `conf_set_kv` 写 llama 实例 conf 的关键键。
2. **单一站上扫描**：`model_scan` 是 `infer-load`/`infer-list` 的唯一别名/定位实现。
3. **写读互逆**：任意合法值经 `conf_set_kv` 后，`source`、`conf_parse.py`、`conf-get` 三者读出的值逐字节相同。
4. **默认安全**：ds4 单机默认 `127.0.0.1`；PP 无显式直连 IP 即中止。
5. **token 不出现在 URL/日志**：除 loopback 引导的瞬时请求外，完整 token 不进入 URL、响应体、启动日志。
6. **无新 daemon/入口**：所有改动落在既有脚本/函数/门禁。
7. **P2 不扩权**：不顺手改 #5/#6/#8/#9/CI。

---

## 7. 错误处理

| 场景 | 行为 | 退出/响应 |
|---|---|---|
| 别名找不到 | 打印 `model_aliases` 候选 + 原名 | `infer-load` exit 1 |
| 模型目录空/无 gguf | 打印目录与候选 | exit 1 |
| conf 值含换行/NUL | 拒绝写入，保留原文件 | `conf_set_kv` rc=2；`infer-load` exit 1 |
| `mktemp`/`mv` 失败 | 清理临时文件，保留原文件 | rc=1；调用方 `exit 1` |
| conf 键缺失 | `conf-get` rc=1 | `rpc_check` 记 `NO_MODEL_PATH`（不静默 OK） |
| PP coordinator 无显式 IP | 打印"需要直连段 IP" | `infer-load` exit 1 |
| `net.yaml` 找不到 PP 段 | `_pp_listen_ip` 返回空 | `_load_ds4_pp` 在起 worker 前 exit 1 |
| `?token=` 非 loopback | 401，不设置 Cookie | HTTP 401 |
| token 比较失败/长度不符 | 401，统一响应 | HTTP 401 |
| Cookie/Header 均无 | 401 | HTTP 401 |
| Web 启动端口占用 | 既有行为（换端口提示） | 不变 |

---

## 8. 测试策略（Step 9 用）

### 8.1 先验红 / 后验绿

| # | 先验红场景 | 修复后断言 |
|---|---|---|
| 3 | 仓库级直放 `gguf/<repo>/<f>.gguf` + 无 conf | 修复前 `repo not found`；修复后生成 conf 且 `MODEL_PATH` 指向该文件 |
| 4 | 路径含空格 + `&` + `\|` | 修复前 `source` 丢值/`sed` 污染；修复后 `source`、`conf_parse`、`conf-get` 三者逐字节一致 |
| 7 | 未设 `PP_LISTEN` 起 ds4 PP | 修复前 cmdline 含 `0.0.0.0`；修复后 coordinator 中止；显式 `--pp-listen` 时 cmdline 含该 IP |
| 10 | 请求 `/?token=<token>` | 修复前 `==`、token 留在 URL；修复后 `compare_digest`、302 + `Set-Cookie`、响应/日志不含完整 token |

### 8.2 单元 / 行为测试

- **#3**：临时 `root` 下造三种落点；断言 `model_aliases`、`model_file_for_alias`、`model_scan` 的 alias/路径/大小；断言源码不再含 `-maxdepth 2 -type d`。
- **#4**：转义矩阵（空格、`&`、`\|`、`"`、`\`、`$`、`` ` ``、`*`）；`source` 与 `conf_parse`/`conf-get` 三方比对；原子性（只读目标目录/注入 `mv` 失败）不遗留半文件；换行/NUL 拒绝。
- **#7**：`_pp_listen_ip` 单测（B-C 段、找不到段、多义段）；`_build_infer_load_cmd` 含/不含 `--pp-listen`；`infer-load` 的 coordinator 无显式值静态断言/干跑中止。
- **#10**：启动 loopback server；`/?token=` → 302 + `Set-Cookie` + 无 token body；Cookie 鉴权 200；Header 鉴权 200；非 loopback query 401；`Referrer-Policy` 头；日志 grep 无完整 token；源码断言 `compare_digest`。
- **全局**：`py-tests`、`doclinks`、`md-tables`、`stations`（新站上件 md5）、`gates`（不因本批退化）。

---

## 9. 验收标准

| # | 验收判据 | 证据 |
|---|---|---|
| 3 | 三种落点均能被 `infer-list` 与 `infer-load` 识别；仓库级直放首次加载生成正确 `MODEL_PATH` | 单测 + 真站临时 alias（Step 9） |
| 4 | 特殊字符路径写入后 `source`/`conf_parse`/`conf-get` 三方一致；失败不破坏原 conf | 单测 + 站上 `conf-get` 实测 |
| 7 | 单机 ds4 绑定 `127.0.0.1`；PP 无显式 IP 中止；显式 IP 时 cmdline/日志为该 IP | 单测 + ds4 PP 干跑/真站 |
| 10 | `compare_digest`；`?token=` loopback 302+Cookie；非 loopback 401；无完整 token 日志/URL | 行为测试 + 源码断言 |
| 全局 | 不新增 daemon/入口；P2 五项未动；既有门禁 PASS | `rpc_check` 全量 |

---

## 10. 对实施的输入（Step 3 展开）

1. **文件**：
   - 新增：`ops/station-bin/model-locate.sh`、`ops/station-bin/conf-lib.sh`、`ops/station-bin/conf-get`、`ops/conf_parse.py`。
   - 修改：`ops/station-bin/infer-load`、`ops/station-bin/infer-list`、`ops/cluster.py`、`ops/cluster_web.py`、`ops/rpc_check.py`（`STATION_BINS` + `[mpath]`）。
   - 测试：`tests/` 下新增 shell/Python 测试；更新 `rpc_check --only py-tests` 的覆盖。
2. **顺序**（调研 §5.1）：#10 → #4 → #3 → #7；#4 与 #3 共享"写操作显式检查"模板，但不扩到 #5。
3. **部署**：三个站上件走既有"改仓库 → 核对 → 部署 → md5 对账"流程；`STATION_BINS` 是部署清单真值。
4. **回滚**：单文件级回滚（站上备份 + 仓库 revert）；Web 侧可回退到 header-only；ds4 侧可回退 `PP_LISTEN` 显式值。

---

## 11. 风险与未决

| 风险 | 影响 | 缓解 |
|---|---|---|
| bash 反转义器实现复杂 | 特殊字符路径读错 | 固定转义集 + 三方比对 fixture；不引入 `eval` |
| `BASH_SOURCE` 在 PATH 调用下解析失败 | 共享库 source 不到 | `readlink -f` + `command -v` 双路径；启动即失败 |
| 新站上件未部署 | `stations` md5 红 / 功能缺 | `STATION_BINS` + 部署检查；先部署再改调用 |
| `net.yaml` PP 段缺失/多义 | ds4 PP 无法起 | `_pp_listen_ip` 失败即中止（不猜） |
| Cookie 方案与现有 localStorage 冲突 | 前端鉴权回退 | Header 与 Cookie 双通道；手动输入保留 |
| 行号快照漂移 | 文档引用过期 | 本文以 `0c53fcc3` 为基线；实施时以函数名/锚点为准 |
| 旧 conf 含未转义特殊字符 | 新读侧解析差异 | 读取侧兼容未加引号；发现歧义报错而非静默 |

**待决问题**：

- **Q1**：`--pp-listen` 用 CLI 还是环境变量？本文选 **CLI**（显式、可审计、避免 `source` 覆盖）。
- **Q2**：`rpc_check` 用站上 `conf-get` 还是主控 Python 解析？本文选 **`conf-get`**（现有 SSH 命令是 shell；避免把整份 conf 拉回主控）。
- **Q3**：自动 token 的落点？本文选 `~/.local/share/rpc/web-token`（0600）；若已有约定则沿用。
- **Q4**：`claude-desktop` / Web UI 是否需要 Cookie 持久化？本文用会话 Cookie（无 `Max-Age`），关闭浏览器即失效。

---

## 12. 附：与既有 spec 的关系

- 本 spec **不**修改 [cluster-orchestration-reliability](../cluster-orchestration-reliability/DESIGN.md) 的加载/回收语义；#7 只改 ds4 监听参数与编排传参。
- #10 与 [D7 六相协议](../d6-agent-standard/D7-PROTOCOL-CONTRACT.md) 无关；Web UI 鉴权不进入 agent 契约。
- 本 spec 的台账归属：[O-177](../../spec/d6-agent-standard/OPEN-ISSUES.md)（原始评审复核登记）。
