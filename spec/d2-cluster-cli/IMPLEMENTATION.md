# 实施文档：D2 集群聚合操作（cluster CLI + 状态总览）

---
id: d2-cluster-cli-IMPLEMENTATION
type: design
version: 1.0
status: draft
date: 2026-09-01
depends: [d2-cluster-cli-RESEARCH]
upstream: null
---

> **Feature**: D2 集群聚合操作
> **创建日期**: 2026-09-01
> **状态**: verified（D2 基础 2026-09-01 验收 9 项全过，CHECKLIST v1.1；框架管理扩展 2026-09-13 — CHECKLIST §3.2）
> **Spec 步骤**: Step 5-6
> **基于调研**: [RESEARCH.md](./RESEARCH.md)
> **决策来源**: [ADR-0001](../../adr/ADR-0001-集群运维框架审计与四项改进决策.md) §决策 3（D2）

---

## 1. 实施概述

单文件 `ops/cluster.py`（Python 3.11 + paramiko，无第三方 Web 框架）+ `ops/cluster_web.py`（Web UI 按需服务），提供 6 个子命令：`status`（三站+网关状态聚合，可选 `--html` 出快照页、`--frames` 追加框架级视图）、`load <alias> [--backend ...]`（自动路由到正确站，支持后端四线切换）、`frames`（三站框架级运行状态一览）、`unload`（三站幂等卸载）、`e2e`（直连三站引擎 :8080 冒烟，网关已退役）、`web`（浏览器傻瓜式管理 UI）。模型→站路由表硬编码于文件顶部。总原则：**只聚合已有 infer-\* CLI，不复制其逻辑**（llama.cpp 命令行构造、内存门控、GTT 等待全部委托站内既有机制）。框架管理为 2026-09-13 扩展：C 站 2026-09-09 已纳入三站清单，本轮补 `frames` 探测、`--backend` 切换、claude frame 与 Web UI。

## 2. 工程细节

### 2.1 技术栈

| 组件 | 技术 | 版本 | 验证状态 |
|------|------|------|---------|
| 语言 | Python | 3.11.16 (主控站 venv) | ✅ E1 |
| SSH | paramiko | 5.0.0 | ✅ E1（pip show） |
| HTTP | urllib.request | 标准库 | ✅ |
| HTML | 单文件内嵌 CSS | 无框架 | — |

依赖零新增：paramiko 已装于主控站 hermes venv（`C:\Users\Peng\.hermes\hermes-agent\venv\Scripts\python.exe`，SSH_OPENCODE_SETUP.md 记录的既定解释器）。

### 2.2 依赖版本验证

无新依赖。唯一外部约定：两站 `infer-load/infer-list/infer-unload` 已部署（E1，A 站 D4 补齐）。

### 2.3 文件结构

```
ops/
├── cluster.py          # 本交付物 (CLI + web 命令入口, ~300 行)
├── cluster_web.py      # Web UI 按需服务 (纯 stdlib http.server + paramiko, 2026-09-13)
└── cluster_status.html # status --html 的输出物 (运行时生成, gitignore)
```

## 3. 模块实施

### 3.1 常量层（路由表）

```python
STATIONS = {
    "A": {"host": "scott-lau-NEX.local",      "user": "scott-lau"},
    "B": {"host": "scott-lau-GTR-Pro.local",  "user": "scott-lau"},
    "C": {"host": "192.168.1.37",             "user": "scott-lau"},   # seaviv (2026-09-09 纳入)
}
STATION_PORT = {"A": 8080, "B": 8080, "C": 8080}   # A/B/C 均 8080 (原 C=18080 为过时值)
ROUTE = {  # alias 前缀 -> 站
    "gpt-oss-120b": "A",          # A 站单机速度档 (conf 在 A)
    "qwen3.8-27b": "C",           # C 站专属键 (置于尾部保前缀匹配序)
    # 其余一律 B 站 (nemotron 主力 + llama-rpc 类)
}
DEFAULT_STATION = "B"
BACKENDS = {"unsloth", "llama-rpc", "llama-single", "vllm"}   # infer-load --backend 白名单
RPC_MODELS = {"deepseek-v4-flash-0731", "gpt-oss-120b-fable-5-distilled", "qwen3.8-flash-next"}
# llama-rpc 类需 A 站 rpc-server 配合, load 时打印手动步骤提示而非静默失败
```

### 3.2 子命令 status

#### 职责

一屏聚合：两站 llama /health、当前加载实例（`systemctl is-active` + 已加载别名）、LiteLLM 存活、infer-list 快照。

#### 接口签名

```python
def cmd_status(html: bool) -> None:
    # 数据源: 两站并行 exec: curl -s localhost:8080/health; systemctl is-active llama-server@*
    #         主控站 urllib: LiteLLM /health/liveliness (key 从 secrets/litellm_master.key 读)
    # 终端: 表格输出; --html: 写 ops/cluster_status.html 并打印 file:/// 路径
```

#### 实施要点

- 两站查询并行（threading.Thread × 2，超时 8s；单站不可达标 `UNREACHABLE` 不阻塞另一站）
- HTML 为快照页（生成时刻数据 + 各面板链接：Beszel/Cockpit A/B + 手册路径），**不自动刷新**——重新运行即刷新，避免常驻进程
- key 读取路径 `d:\RPC\secrets\litellm_master.key`（不硬编码，RESEARCH §3.1 契约）
- infer-list 输出**原样透传**展示（审查 P2：实测"位置"列 AB/B 宽度不一，固定列宽解析会错位；且路由决策不依赖该表格——RESEARCH §4.3 已定死硬编码路由表）

### 3.3 子命令 load

#### 职责

`cluster.py load <alias前缀>` → 自动路由正确站并执行该站 infer-load。

#### 接口签名

```python
def cmd_load(alias: str) -> int:
    # 1. 精确/前缀匹配 ROUTE; 未命中走 DEFAULT_STATION="B"
    # 2. RPC_MODELS 命中 -> 打印双机手动步骤 (A 站起 rpc-server + B 站 infer-load) 后退出码 2
    # 3. 其余: paramiko exec "infer-load <alias>", 实时回传 stdout/stderr
    # 4. 完成后自动 curl :8080/health 确认 READY
```

#### 实施要点

- 输出实时流式（paramiko channel recv，非结束后一次性——加载需 40s~3min，用户需看进度）
- exit code：0=READY / 1=加载失败 / 2=RPC 类需手动 / 3=e2e 前置未加载
- **换模型串行化（审查 P1）**：load 前先查该站 `:8080/health`——READY 则先 `infer-unload`（站内已含 wait-gtt-release 的 GTT 等待）并确认返回后再加载新模型；未 READY 直接加载。**禁止**在 unload 完成前发出第二个 infer-load（防 GTT 叠加期并发加载）
- **不做**内存预检：站内 load-mem-gate 已有 12G 垫（委托，不复制）

### 3.4 子命令 unload

两站并行 `infer-unload`（幂等，未加载站返回即成功），汇合后打印两站 GTT 释放结果。

### 3.5 子命令 e2e

直连流三站引擎 `:8080/health` 冒烟（网关已退役 2026-09-13，ADR-0002 决策 C 落地，集群改直连各站引擎端口）。三站均可达→exit 0；任一离线→exit 1（区别于 unload 未加载的 exit 0）。**退出码契约（重写后）**：0=三站引擎全部在线冒烟通过 / 1=某一站引擎离线（打印哪站 + 排查指引，先 `status` 看加载态，再 `load <对应模型>`）。LiteLLM 网关不再作为 e2e 检查项。

### 3.6 低效操作排除

- 不用 asyncio（threading 足够，两站并发而已）
- 不解析 infer-list 动态推导路由（误路由风险 > 维护 3 行 dict 的成本）
- 不做 TUI/watch 模式（快照哲学，ADR"不做第四个面板"边界）

### 3.7 推理框架统一管理（2026-09-13 扩展）

#### 职责

三站框架级运行状态一览 + 后端四线切换 + 浏览器 Web UI，统一收口到 cluster.py 的单一 CLI 入口，免记各站 ssh/手动命令。

#### 子命令

- `frames`：三站并行探测 llama-server / unsloth / vllm / litellm / opencode / claude 的 RUNNING / STOPPED / Unknown 状态，恒 exit 0。
- `status --frames`：在 status 输出尾部追加框架级视图（复用同一探测）。
- `web`：按需起浏览器管理 UI（ops/cluster_web.py）——三站框架状态自动刷新 + 点按钮加载/换后端/卸载；Ctrl-C 即停不常驻。

#### 接口签名

```python
BACKENDS = {"unsloth", "llama-rpc", "llama-single", "vllm"}   # --backend 白名单
FRAME_CMD = (... 'echo [claude]; pgrep -f "[c]laude-code" ...)  # 第 6 维 claude
def probe_frames(st: str) -> dict:   # 单站 {station, reachable, frames:{name:(status, detail)}}
def collect_frames() -> dict:        # 三站并行
def cmd_frames() -> int:             # 三站一览, 恒 exit 0
def cmd_load(alias: str, backend: str = None) -> int   # 新增 backend 透传
def cmd_web()/cluster_web.py         # Web UI 按需服务
```

#### 实施要点

- **框架探测单次 ssh 多命令**（`FRAME_CMD`）：`[u]`/`[v]`/`[c]` 前缀规避 pgrep 自匹配；llama 的 RUNNING 由 systemctl（A/B）或 pgrep llama-server（C 手动引擎）取其一判活。
- **claude 维**：`pgrep -f '[c]laude-code'` 判定该站 Claude Code 会话进程有无（RUNNING/STOPPED）。`[c]` 前缀规避探测命令自身自匹配（初版用 `[c]laude` 会误捕含 "claude" 子串的探测进程，已修复）。**语义边界**：反映本地 Claude Code 会话进程的有无，非主控↔该站连接握手。
- **判定序（`_frame_status`）**：running（进程实据）> inactive > active。**必须先判 `inactive` 再判 `active`**——否则 `inactive` 含子串 `active` 被误判 RUNNING（本轮实测 bug，已修复）。
- **`--backend` 白名单校验**：`load <alias> --backend <new>` 换后端一次命令完成（infer-load 已做站内互斥，无需先 unload）；非法后端 exit 1 并列出可选范围。
- **参数解析坑（本轮实测 bug，已修复）**：`load` 解析必须剔除 `--backend` 后紧跟的值，否则 alias 前缀被污染成 `"gpt-oss-120b unsloth"`。修复为 while 提取值并跳过。
- **llama-rpc 双机类**：显式 `--backend` 单机后端（非 llama-rpc）视为强制单机加载；未显式则 exit 2 打印双机手动步骤。
- **Web UI**：纯 stdlib `http.server.ThreadingHTTPServer` + paramiko 实现，零外部框架；`GET /` + `GET /api/status`（三站 frames JSON）+ `POST /api/load|backend|unload`，`/api/*` 需 `X-Auth-Token`（前端存 localStorage）；`redirect_stdout` 捕获 `cmd_load/cmd_unload` 日志回返，无需自造进程管理。
- **C 站**（2026-09-09 起）：常驻为手动 /opt/llama.cpp llama-server（Vulkan），infer-* 工具链已补装，load/unload 与 A/B 同路径（pkill 兜底管理手动引擎）。
- 探测全部经 paramiko（`ssh_run`），单站不可达标注 Unknown/UNREACHABLE，不阻塞他站。

### 3.8 统一入口四平面：凭据 / Provider / 出站（2026-09-14 扩展）

#### 职责

把「本地推理框架已有统一管理」延伸为**三站 agent API 配置 + 外部商业 API 的统一管理**，四平面收口同一 CLI：

| 平面 | 子命令 | 管理对象 | 动作 |
|------|--------|---------|------|
| ① 本地引擎 | `frames` / `load` / `unload` / `status` | 三站 llama/unsloth/vllm 进程与引擎 | 状态、加载、切后端、卸载 |
| ② 凭据 | `secrets {status\|scan\|push}` | 站内 `~/.config/rpc/*.key` | 巡检、明文门禁、正本下发 |
| ②b Provider | `providers` | opencode / claude / hermes 配置 | 聚合视图 + 漂移检测 |
| ③ 出站 | `egress` | OpenRouter 等外部商业 API | 健康、用量、余额 |
| 汇总 | `status --all` + `web` | 四平面 | 一屏视图 / 浏览器面板 |

#### 收敛约定（明文治理的落地形态）

- **站内唯一落点**：`~/.config/rpc/`（700）+ `<name>.key`（600，**无尾换行**）。key 仍是每站一份，但只此一处。
- **配置引用化**：`opencode.jsonc` → `apiKey: "{file:~/.config/rpc/<name>.key}"`（opencode 官方变量替换，支持 `~`，内容原样取用）；`.claude/settings.json` → `apiKeyHelper: /home/scott-lau/.config/rpc/claude-key.sh`（Claude Code 专用取 key 脚本）。
- **主控正本**：`secrets/stations/<st>/`（`.gitignore` 覆盖），经 `secrets push` 用 SFTP 下发并 chmod。
- **历史备份**：脱敏为 `***REMOVED***` 后归档至 `backups-keys-<date>/`（700）。

#### 接口签名

```python
RPC_DIR = "~/.config/rpc"
SECRETS_ROOT = Path(__file__).parent.parent / "secrets" / "stations"   # 主控正本
KEY_PAT = r"sk-(or-v1|unsloth|RPC|local|lm)-[A-Za-z0-9_-]{6,}"          # 明文指纹
def probe_secrets(st) -> dict          # 落点/权限/生效明文/归档明文/引用/helper
def _secrets_verdict(p) -> (state, note)   # OK | ATTENTION | UNREACHABLE
def cmd_secrets(action="status") -> int    # scan 有命中则 exit 1 (门禁语义)
def _secrets_push() -> int                 # SFTP 下发 .key=600 / .sh=700
def probe_providers(st) -> dict        # opencode 默认模型+provider key 形态; claude 形态
def _claude_forms(cl) -> dict          # env token 区分 ref / PLAIN / 占位符(nB)
def cmd_providers() -> int             # 聚合 + 默认模型/provider 集合漂移检测
def probe_egress_station(st) / probe_egress_master() -> dict
def cmd_egress() -> int                # OpenRouter /api/v1/key, 强制 IPv4
def _planes_compact()                  # status --all 的四平面一行摘要
```

#### 实施要点

- **明文只能治「散落」，不能治「持有」**：站点调用外部 API 必然持有 key。目标是把明文面收敛为「每站 1 个 600 文件 + 主控 1 个正本」，而非追求零落盘。
- **`{file:}` 验证靠 `opencode debug config`**：`opencode run` 在 B 站长时间无输出（`--pure` 与付费模型同样复现，与本次改造无关，未闭环），故采用 `debug config` 作为 acceptance gate——它输出**解析后**的配置，可直接断言「无残留 `{file:` + apiKey 为真实值」。
- **marker 拼接坑**：`opencode.jsonc` 无尾换行，探测脚本若用 `echo '### marker'` 分隔区块，marker 会被粘到上一行末尾导致解析失败。必须用 `printf '\n### x\n'` 前置换行。
- **claude env token 判定要分档**：A 站 `ANTHROPIC_AUTH_TOKEN` 值为本地占位符 `lmstudio`（8B），不是密钥。仅按「字段存在」判定会误报明文，须按 `ref / PLAIN(len≥20) / 占位符` 三档区分。
- **egress 强制 IPv4**：主控到 openrouter.ai 的 IPv6 路径黑洞（ADR-0003 实测），主控侧用 `curl.exe -4`、站内侧 `curl -4`，否则超时。
- **`/key` label 会回显 key 前段**：输出前必须过 `_mask_key()` 脱敏。
- 四平面探测均复用 `ssh_run` 并行线程，单站不可达不阻塞他站；`providers` / `egress` 恒 exit 0（观测语义），`secrets scan` 是唯一带门禁退出码的（有明文 → exit 1）。

#### 实测验收（2026-09-14）

| 项 | 结果 |
|----|------|
| 三站 `opencode debug config` | EXIT=0，未解析 `{file:` 计数 0，apiKey 为真实值（脱敏后可见前缀） |
| Claude Code 2.1.258 | 经 `apiKeyHelper` 于 B 站完成一轮对话（`stop_reason=end_turn`） |
| `secrets scan` | A/B/C 明文命中均 0 → PASS |
| `secrets push` | 11 个文件下发（A 3 / B 4 / C 4），权限 600（脚本 700） |
| `egress` | 主控+A/B/C 均 http=200，同一 key（label 一致），单程 0.6~1.8s |
| `web /api/planes` | 200，返回 secrets/providers/egress 三平面 JSON |

#### 发现的漂移（已暴露，未擅自变更）

三站 opencode 默认模型互不相同：A `opencode/nemotron-3-ultra-free`、B `opencode/nemotron-3.5-lightning-free`、C `cluster-litellm/nemotron`。属配置漂移而非密钥问题，改变默认模型会影响站上行为，故仅由 `providers` 持续暴露，待显式决策。

## 4. 实施顺序与检查点

```
1. cluster.py 骨架 + 常量层 + paramiko 连接池
2. status (终端表格)          ── 验证: 两站+A/B 加载态正确显示
3. load/unload                ── 验证: load gpt-oss 落 A 站 / nemotron 落 B 站
4. e2e                        ── 验证: 双路由通 (需先 load 两模型)
5. status --html              ── 验证: 浏览器打开快照页, 链接可达
6. 手册 §2 增补 cluster.py 用法
```

## 5. 验收标准

| # | 验收项 | 命令 | 预期 |
|---|--------|------|------|
| 1 | status 聚合 | `cluster.py status` | 两站 health + 加载态 + LiteLLM 一屏 |
| 2 | 单站宕机容错 | 停 A 站 llama 后 status | A=inactive 不报错，B 正常 |
| 3 | load 路由-A | `cluster.py load gpt-oss-120b` | A 站加载，:8080 READY |
| 4 | load 路由-B | `cluster.py load nvidia-nemotron` | B 站加载 |
| 5 | RPC 类拦截 | `cluster.py load deepseek` | 退出码 2 + 手动步骤提示 |
| 6 | e2e | `cluster.py e2e` | 直连三站 :8080 冒烟，全在线 exit 0（网关退役后语义） |
| 7 | HTML 快照 | `cluster.py status --html` | 生成文件含数据+4 链接，浏览器可开 |
| 8 | 手册更新 | docs/手册 §2.4 | cluster.py 用法 3 行以上 |
| 9 | 连续 load 幂等（审查 P1 回归） | 已加载模型后再 load 另一模型 | 先 unload→GTT 释放→新 load 成功，无并发 |
| 10 | frames 三站框架一览 | `cluster.py frames` | 三站 llama/unsloth/vllm/litellm/opencode/claude 状态，恒 exit 0 |
| 11 | status --frames 追加视图 | `cluster.py status --frames` | 复用同一探测，尾部追加框架级视图 |
| 12 | 非法 backend 拒绝 | `cluster.py load x --backend bad` | exit 1 + 白名单提示 |
| 13 | --backend 四线透传 | `cluster.py load gpt-oss-20b --backend unsloth` | 换后端一次命令，infer-load 站内互斥，无需先 unload |
| 14 | C 站纳入三站清单 | `frames`/`status` | C 站在列，llama/unsloth/vllm/litellm/opencode/claude 可探测 |
| 15 | load 成功判定 exit 0 | `load` 完成后 $LASTEXITCODE | 以 infer-load rc 为准（F6 修复），health 探测降级为日志 |
| 16 | claude 框架探测 | `cluster.py frames` | 三站 claude 维正确显示（无会话 STOPPED），`[c]` 前缀不自匹配 |
| 17 | Web UI 按需服务 | `cluster.py web` + 浏览器 | 三站框架状态自动刷新，按钮加载/切后端/卸载，token 鉴权，Ctrl-C 即停 |

## 6. 风险与回滚

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| paramiko 对 A 站连接抖动（管理网 DHCP） | 中 | status 单站 UNREACHABLE | .local 名已免疫 IP 漂移；重试 1 次 |
| 主控站 venv 路径变动 | 低 | 脚本不可运行 | shebang 注释记录解释器绝对路径；备选系统 Python 3.12 装 paramiko |
| 路由表与新增 conf 脱节 | 中 | load 到无 conf 站报错 | 站内 infer-load 自身会报"无 conf"，错误信息足够定位；手册注明维护点 |

回滚：cluster.py 是纯客户端聚合器，删除即回滚，无站侧变更。

## 7. 交付物

- `ops/cluster.py`（含 usage 文档字符串）
- 手册 §2.4 增补（cluster.py 四子命令速查）
- 本 IMPLEMENTATION.md 状态 → verified（8 项验收全过）
- ADR-0001 §决策 3 标注：已完成
