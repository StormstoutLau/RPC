# 审查验收 Checklist：D2 集群聚合操作

***

id: d2-cluster-cli-CHECKLIST
type: design
version: 1.0
status: pending
date: 2026-09-01
depends: \[d2-cluster-cli-IMPLEMENTATION, d2-cluster-cli-RESEARCH]
upstream: null
--------------

> **Feature**: D2 集群聚合操作（cluster.py + 状态总览）
> **创建日期**: 2026-09-01
> **状态**: 已验收（基础 §3 九项 + 框架扩展 §3.2 10-18 共 18 项全勾）
> **Spec 步骤**: Step 7-8, 10
> **基于实施**: [IMPLEMENTATION.md](./IMPLEMENTATION.md)
> **基于调研**: [RESEARCH.md](./RESEARCH.md)
> **审查轮次**: 第 1 轮（文档审查，实施前门）

***

## 0. 审查结论速览

**结论：有条件通过（1 项已修正、2 项待实施内落实、2 项用户裁决）。** 文档层抓出 4 处问题：P1（关键，已修正进 IMPLEMENTATION）、P2/P3（实施内必须落实）、P4（验收项缺口，已补）。

| #  | 审查发现                                                                                                                                           | 性质        | 处置                                                                                                                         |
| -- | ---------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------------------------------------------------------------------------------------------------------------------------- |
| P1 | IMPL §3.3 的 load 流程会**先卸载后加载但未串 GTT 等待**——同站换模型时，旧模型 GTT 未释放，新模型虽过 load-mem-gate 的 12G 垫也可能在 GTT 叠加期误判/等待；且 paramiko 命令未持锁，连续两次 load 会并发触发站内加载 | 逻辑缺陷（文档层） | 已修正 IMPL §3.3：load 前先查 `:8080/health`，READY 则先调 `infer-unload` 并**轮询 GTT 释放**（wait-gtt-release 由站内 unload 已含），未 READY 直接加载 |
| P2 | RESEARCH §3.2 的 infer-list 输出表格**列对齐与实测不完全一致**（实测"位置"列有 `AB`/`B` 两宽度，文档表格渲染偏移）——若实施按固定列宽解析会错位                                                  | 契约风险      | 实施约束：**不解析 infer-list 表格做路由**（已在 RESEARCH §4.3 定死），status 展示仅原样透传。已在 IMPL §3.2 实施要点补注                                      |
| P3 | e2e 需要两模型已加载，但 IMPL 未写清"未加载时的行为"                                                                                                               | 行为缺口      | 已补 IMPL §3.5：e2e 前置检查——任一路由未 READY 时打印 `cluster.py load <对应模型>` 提示并 exit 3（区别于路由故障的 exit 1）                                |
| P4 | 验收表缺"连续 load 幂等"项（P1 的回归验证）                                                                                                                    | 验收缺口      | 已补验收 #9                                                                                                                    |

## 1. 文档一致性验收（Step 8）

### 1.1 RESEARCH ↔ IMPLEMENTATION 对齐

| 检查项                                           | 状态 | 说明                           |
| --------------------------------------------- | -- | ---------------------------- |
| RESEARCH §3.1 Python/paramiko → IMPL §2.1 技术栈 | ☑  | 一致，含解释器绝对路径约定                |
| RESEARCH §3.3 路由表 → IMPL §3.1 常量层             | ☑  | ROUTE 3 行 + RPC\_MODELS 集合一致 |
| RESEARCH §3.4 静态快照 → IMPL §3.2                | ☑  | --html 生成物、不自动刷新一致           |
| RESEARCH §3.5 端点清单 → IMPL status 数据源          | ☑  | health 端点、key 读取路径一致         |
| 无文档间矛盾                                        | ☑  | P1-P4 修正后交叉核对                |

### 1.2 IMPLEMENTATION ↔ 本 checklist 对齐

| 检查项                                     | 状态               |
| --------------------------------------- | ---------------- |
| IMPL 4 子命令 + 8+1 验收项在本 checklist §3 全覆盖 | ☑（#9 为本轮补入 IMPL） |
| 本 checklist 验收项可追溯 IMPL 章节              | ☑                |

### 1.3 与 ADR-0001 / 既有规范的一致性

| 检查项                                                          | 状态 | 说明                          |
| ------------------------------------------------------------ | -- | --------------------------- |
| 语言偏差已在 RESEARCH §4.2 备案（cluster.ps1→cluster.py）              | ☑  | 实现层修正，不构成 ADR 修订            |
| 未越 D1 边界（不做 watchdog/fallbacks）                              | ☑  | <br />                      |
| 未越"不做第四个面板"边界（静态快照非常驻）                                       | ☑  | <br />                      |
| key 不硬编码（secrets/ 读取）                                        | ☑  | IMPL §3.2 要点                |
| 站侧零变更（纯客户端聚合器）                                               | ☑  | IMPL §6 回滚声明                |
| **用户裁决项 a**：cluster.py 落位 `ops/`（D3 后活资产的家）vs 新建 `tools/`    | ☐  | 建议 ops/（与 ADR 目录结构一致，零新增顶层） |
| **用户裁决项 b**：HTML 快照文件落 `ops/cluster_status.html` 并 gitignore | ☐  | 建议 gitignore（运行时生成物不入库）     |

### 1.4 术语一致性

| 术语        | RESEARCH                    | IMPL                       | 本 checklist | 一致         |
| --------- | --------------------------- | -------------------------- | ----------- | ---------- |
| 子命令集      | §4.3 status/load/unload/e2e | §3.2-3.5                   | §3 验收映射     | ☑          |
| RPC 类模型集合 | §3.3                        | §3.1 RPC\_MODELS           | §3 #5       | ☑          |
| 退出码语义     | —                           | §3.3 (0/1/2) + P3 补 exit 3 | §3 #6       | ☑（IMPL 已补） |

## 2. 反幻觉审查（文档层证据核验）

### 2.1 证据重放

| # | 声明                                     | 核验方式                                                       | 结果             |
| - | -------------------------------------- | ---------------------------------------------------------- | -------------- |
| 1 | paramiko 5.0.0 已装于主控站                  | `pip show paramiko`（本日 E1）                                 | ☑              |
| 2 | Python 3.11.16（hermes venv）            | `python --version`（本日 E1）                                  | ☑              |
| 3 | infer-list 四列契约（ALIAS/位置/大小/建议后端/CONF） | SSH 实测输出留档 RESEARCH §3.2                                   | ☑（P2 列宽注意项已标注） |
| 4 | gpt-oss-120b 位置=AB、conf 在 A 站          | D4 部署记录 + infer-list 实测                                    | ☑              |
| 5 | RPC 类三模型清单                             | infer-list 建议后端列 llama-rpc 实测                              | ☑              |
| 6 | LiteLLM liveliness 端点存在                | 手册 §1.2 + ADR-0001 E1                                      | ☑              |
| 7 | "PS5 三坑本日踩 3 次"                        | 会话记录：D4 probe 脚本 GBK 乱码、T4 heredoc 引号截断、D3 .ps1 无 BOM 中文失败 | ☑              |

### 2.2 文档层幻觉排除

| 检查项                             | 结果                                                           |
| ------------------------------- | ------------------------------------------------------------ |
| RESEARCH 无未标注 E 等级的断言           | ☑（E1/E2 均标注）                                                 |
| IMPL 无虚构命令（所有命令均为已有 CLI 或标准库调用） | ☑                                                            |
| 工时/规模预估标注为估计而非承诺                | ☑（\~300 行、\~半天）                                              |
| 未把"调研推断"写成"已验证"（如 GTT 释放行为）     | ☑（P1 修正时显式核对：wait-gtt-release 由站内 infer-unload 内含，属 E2 既有资产） |

## 3. 实施验收映射（实施完成后逐项打勾）

| # | 验收项（IMPL §5）      | 验收命令                                                                       | 通过 |
| - | ----------------- | -------------------------------------------------------------------------- | -- |
| 1 | status 聚合         | `python ops/cluster.py status`                                             | ☑ 双站 READY+加载实例+LiteLLM UP+infer-list 透传 |
| 2 | 单站宕机容错            | 停 A 站 llama 后 status                                                       | ☑ probe 失败→UNREACHABLE 不阻塞他站（B :8080 掉线实测 000 正确显示） |
| 3 | load 路由-A         | `cluster.py load gpt-oss-120b` → A 站 READY                                 | ☑ A 站 llama-server@gpt-oss-120b active + :8080 200 |
| 4 | load 路由-B         | `cluster.py load nvidia-nemotron` → B 站 READY                              | ☑ 23:39:44 READY ✓ (80G 模型) |
| 5 | RPC 类拦截           | `cluster.py load deepseek` → exit 2 + 手动步骤                                 | ☑ exit 2 + 三步提示 |
| 6 | e2e 双路由           | `cluster.py e2e` → exit 0（未加载时 exit 3 + 提示）                                | ☑ 双路由 OK (22.4s/21.5s), exit 0 |
| 7 | HTML 快照           | `cluster.py status --html` → 文件生成、浏览器可开、4 链接可达                             | ☑ 状态表+4 面板链接+双站 infer-list 齐全 |
| 8 | 手册更新              | docs/手册 §2.4 增补                                                            | ☑ 六命令+路由规则+退出码+已知边界 |
| 9 | 连续 load 幂等（P1 回归） | 已加载 gpt-oss 再 `load nvidia-nemotron`（或反向）：应先 unload→GTT 释放→新 load 成功，无并发加载 | ☑ A 站重载实测: unload→GTT 0B 确认→reload READY 全串行 |

### 3.1 实施期新发现（验收外的收获，记档）

| # | 发现 | 性质 | 处置 |
|---|------|------|------|
| F1 | A 站 infer-load 日志措辞"B 站起 llama-server@"具误导性（实际是 A 站本地 systemctl start——脚本是 B 站版完整副本，日志 tag 未改） | 站侧日志瑕疵 | 记档；修 A 站脚本 tag 属站侧变更，超出 D2 纯客户端边界，留待下次站侧维护窗口 |
| F2 | B 站 infer-load 的 `wait_gtt A`（SSH 到 A 站查 GTT<2G）在双端点模式下恒走满 90 次×~12s≈18min 才 WARN 放行——A 站常驻 gpt-oss (GTT 135G)，且 B→A 单次 SSH 达 10.2s（mDNS 解析慢） | 站侧设计缺陷（D4 复刻引入） | **✅ 已修复 2026-09-02**：infer-load（RPC_TARGET 空跳过）+ infer-unload（rpc-server 未运行跳过）双补丁两站同步；实测 nemotron 换载 20min→2.7min、双站 unload 32s；修复版快照入 [ops/station-bin/](../../ops/station-bin/README.md)；站侧备份 `.bak-f2fix`×2/站 |
| F3 | 主控站 paramiko 在 Python 3.12（`AppData\...\Python312`），RESEARCH §3.1 写的 hermes venv 3.11 无该模块——文档笔误 | 本 spec 文档勘误 | 手册 §2.4 命令示例用 3.12 路径（正确）；RESEARCH 不回改（保留原样+此处勘误记录） |
| F4 | `qwen3-coder-next` 无 conf（infer-list CONF 列 `-`）、`glm-5.3-flash` 有 conf 无模型（不在 infer-list）——站侧资产与 conf 脱节 | 站侧卫生债 | 记档；属 D3/站侧维护范畴，不阻塞 D2 |

### 3.2 框架管理扩展验收（2026-09-13 追加，对应 IMPL §3.7）

| # | 验收项 | 验收命令 | 通过 |
|---|--------|---------|-----|
| 10 | C 站纳入三站清单 | `status`/`frames` 输出含 C 站 (192.168.1.37) | ☑ 三站在列 |
| 11 | frames 三站框架一览 | `cluster.py frames`（恒 exit 0） | ☑ A/B/C llama/unsloth/vllm/litellm/opencode 真实返回 |
| 12 | status --frames 追加视图 | `cluster.py status --frames` | ☑ 复用同一探测追加 |
| 13 | 非法 backend 拒绝 | `load x --backend bad` | ☑ exit 1 + 打印可选白名单 |
| 14 | --backend 四线透传 | `load gpt-oss-20b --backend unsloth` → B 站 unsloth 起 :8080 | ☑ infer-load 日志确认 unsloth 后端、READY ✓ |
| 15 | 换后端一次命令（无需先 unload） | 已加载态下 `load ... --backend <new>` | ☑ infer-load 站内互斥 + GTT 释放后加载，不必手动卸载 |
| 16 | load 成功判定 exit 0 | `load` 完成后 $LASTEXITCODE | ☑ 见下方 F5 修复后 exit 0 |
| 17 | claude 框架探测 | `cluster.py frames` | ☑ 三站 claude 维均正确显示 STOPPED（实测 2026-09-13），`[c]` 前缀规避自匹配 |
| 18 | Web UI 按需服务 | `cluster.py web` + 浏览器 | ☑ AST/401 鉴权/三站 frames JSON/页面返回/非法 backend 拒绝(rc=1)+端口释放均验证（真实 load/unload 涉生产引擎未擅自触发） |

#### 3.2.1 实施期新发现（框架扩展，2026-09-13）

| # | 发现 | 性质 | 处置 |
|---|------|------|------|
| F5 | **`--backend` alias 污染 bug**：旧 `rest=[a for a in args[1:] if not a.startswith("--backend")]` 只过滤 `--backend` 本身，未剔除其后的值，导致 `load gpt-oss-120b --backend unsloth` 的 alias 被污染成 `"gpt-oss-120b unsloth"` | 逻辑缺陷 | ✅ 修复：while 提取后端值并跳过；4 组 case 回归（alias/backend 分离） |
| F6 | **health 判定契约对 unsloth 后端失效**：`/health` 返回 `{"detail":"API endpoint not found"}`（FastAPI OpenAI server 无该端点），`startswith('{"status"')` 判定失败——infer-load 站内已判 READY (rc=0)，cluster.py 却误报 exit 1 | 契约缺口 | ✅ 修复：以 infer-load rc=0 为主判据，health 探测降级为日志提示；load 前置串行化检查放宽为"任意 HTTP 响应"（infer-unload 幂等, 误判无害） |
| F7 | 主控直连 B:8080 被拒（WinError 10061）——unsloth 后端仅监听站内 127.0.0.1 | 已知拓扑 | 记档：health/审查须经 ssh 站内调用，非主控直连 |

### 3.3 统一入口四平面验收（2026-09-14 追加，对应 IMPL §3.8）

| # | 验收项 | 验收命令 | 通过 |
|---|--------|---------|-----|
| 19 | 站内凭据落点建立 | `secrets status` | ☑ A/B/C 均有 `~/.config/rpc`（700）+ key（600） |
| 20 | 明文门禁 | `secrets scan` | ☑ 三站命中 0 → exit 0 / PASS |
| 21 | opencode `{file:}` 引用解析 | 站内 `opencode debug config` | ☑ EXIT=0，未解析 `{file:` 计数 0，apiKey 为真实值 |
| 22 | claude `apiKeyHelper` 生效 | B 站 `claude -p ... --output-format json` | ☑ EXIT=0，`stop_reason=end_turn`（2.1.258） |
| 23 | 正本下发 | `secrets push` | ☑ 11 个文件（A 3 / B 4 / C 4），600 / 脚本 700 |
| 24 | 历史备份脱敏归档 | 归档目录明文 grep | ☑ A 13+1 / B 15+4 / C 2+3 归档，残留 0 |
| 25 | Provider 聚合 | `providers` | ☑ 三站 provider 集合 + key 形态 + 默认模型 + 漂移输出 |
| 26 | 出站探针 | `egress` | ☑ 主控+A/B/C 均 http=200，同一 key，0.6~1.8s |
| 27 | 四平面汇总 | `status --all` | ☑ ①引擎 + ②凭据 + ②b Provider + ③出站 同屏 |
| 28 | Web 平面面板 | `/api/planes` | ☑ 200，三平面 JSON（token 鉴权） |

#### 3.3.1 实施期新发现（统一入口，2026-09-14）

| # | 发现 | 性质 | 处置 |
|---|------|------|------|
| F8 | **marker 粘行**：`opencode.jsonc` 无尾换行，`echo '### opencode'` 与上一行末尾粘连 → 区块解析失败（JSONDecodeError: Extra data） | 解析缺陷 | ✅ 修复：区块 marker 统一改 `printf '\n### x\n'` 前置换行 |
| F9 | **claude env token 误报**：按「字段存在」判定明文，A 站占位符 `lmstudio`（8B）被误报为明文密钥 | 判定过粗 | ✅ 修复：`_claude_forms` 分 `ref / PLAIN(len≥20) / 占位符(nB)` 三档 |
| F10 | **`opencode run` "无输出"归因三次修正（2026-09-14）**：① 原记「B 站既有缺陷」→ ❌ 证伪（非站点、非缺陷）；② 本调研初稿「免费档低吞吐」→ ◐ 表述过强；③ 终版：**`opencode/*` 免费档间歇性慢**，合并采样 **10/17 ≈59%**（位置参数 6/9、stdin 管道 4/8 → **与调用形式无关**），失败恒为 rc=124 且输出字节>0（在生成，只是慢），叠加 `opencode run` 无默认总超时 → 表现为无反馈等待。**该现象手册 `§2a.4` 铁律 2 已于 2026-09-02 记档**（当时归因到调用形式；本轮 4/4 成功**未复现**该绝对表述） | 认知错误 + 可用性波动 | ✅ 已处置：`oCrun` 兜底包装落地三站（超时+自动切档），详见 [调研报告](../../docs/research/2026-09-14_暴露问题调研.md) §1/§4 |
| F11 | 大量 `sk-*` 命中为上游噪声：hermes 源码/测试、浏览器 voice 列表、IDE 语言包 | 误报源 | 记档：巡检须先排除 `/tests/`、`/website/`、`node_modules`、`__pycache__` 再判定 |
| F12 | 三站 opencode 默认模型不同（A/B `opencode/*` 免费档，C 本地 `cluster-litellm/*`）——经复核为手册 `§2a.4` 铁律 3 的既定策略，非历史残留 | 既定策略 + 缺兜底 | ✅ **已统一（2026-09-14）**：三站均为 `opencode/nemotron-3-ultra-free`，provider 集合均为 `{local, openrouter}`，`opencode.jsonc` sha256 三站一致（`2ae32379…`）；`providers` 不再报漂移。兜底由 `oCrun` 链承担 |
| F27 | **hermes 的 chat client 只从 config 路径读 key**：`.env` 的 `CUSTOM_API_KEY` 仅用于模型列表探测（`models.py::_custom_catalog` 链为 `model.api_key` → `CUSTOM_API_KEY` → `OPENAI_API_KEY` → `OPENROUTER_API_KEY`）。只设 env → 对话时 `HTTP 401: Invalid token payload`（同 key 直接 curl `:8080` 为 200） | 第三方机制（非我方缺陷） | ✅ 已处置：三站 `hermes config set model.api_key <unsloth key>`，config.yaml chmod 600，并**登记为新增密钥分发点**（密钥清单 §7） |
| F28 | **hermes 有 64K 上下文下限**：低于则拒绝（`Model main has a context window of 32,768 tokens, below the minimum 64,000`）。B 站当时加载的 gpt-oss-20b 为 `-c 32768` | 第三方约束 | ✅ 已处置：三站 `model.context_length = 131072`；后续任何 <64K 上下文的本地模型都会触发同一限制，需注意 |
| F29 | **hermes `config.yaml` 未能字节级统一** | 历史债 | ◐ **A 站遗留段落已清理（2026-09-14）**：顶层键 23 → 21（删废弃键 `provider: lmstudio` + unset `api_key`）、`.env` 删 `LM_API_KEY`、`models.json` 7 → 4 条（删 3 条 `:1234`）；备份 `*.bak-legacy-20260914`。**但文件仍非字节级相同**（A 为 21 个 hermes 标准段，B/C 为 `config set` 最小文件）——属"格式统一"，未做。另：仅存的 `lm-studio` 痕迹在 `API_SERVER_KEY` 的值里（功能键，`:8642` 无监听 ⇒ 轮换零风险，待定） |
| F16 | **诊断流程缺陷（本轮最大产出）**：P1/P2 初稿结论**均错**，根因是**调研前未检索既有记档**——手册 `§2a.4` 早已把该现象列为铁律（含日志实证），`ops/station-bin/agent-cli-smoke.sh` 是现成冒烟工具，全部漏读；且第 1 轮用 5 次采样（3 次失败）即下"B 站坏了"的定性 | 方法论 | ✅ 已立规：诊断类任务第一步固定为「检索 手册/spec/ADR/既有 smoke 脚本」；"某站坏了"类结论须 ≥5 次重复采样方可下笔（写入调研报告 §1.4） |
| F17 | **harness 门禁是「逐模型」而非「整个 `:free` 档」**（实测修正 ADR-0003 旧表述）：`thinkingmachines/*:free` 裸 API 403，`nvidia/*:free` 裸 API **200**。**由此发现并修掉一处现存 bug**：`secrets/openrouter.conf` 的 judge 槽（走裸 API）原填 harness-only 的 `thinkingmachines/inkling:free` → 必 403，已改为 `nvidia/nemotron-3-ultra-550b-a55b:free` | 配置缺陷 + 表述过笼统 | ✅ 已修：ADR-0003 表述收窄；用户指定 5 档优先级已落地三处镜像（conf `harness_priority` / 站内 `opencode.jsonc` / `oCrun` 链）。详见调研 §7 |
| F18 | **OpenRouter 区域封锁与限流是常态**：`muse-spark-1.2-contributor-free`（手册已记）、`google/gemini-2.5-flash` 403 区域封锁；`poolside/laguna-s-2.1:free` 429 上游限流 | 出站约束 | 记档：模型选型须实测；`laguna` 保留在优先级列表但标注"当前不可用"（不改用户指定序） |
| F19 | ✅ **已修（2026-09-14）**。原记「`/api/status` 129.6s，根因是串行 9 次 ssh」。**真因更根本：每次 ssh 都重新做 mDNS 解析，单次约 14s**（A 14.07s / B 14.10s），而 IP 直连仅 0.2s ⇒ 9 次串行白付 ~130s。C 站一直用 IP 故从未受影响 | 性能缺陷（根因认知修正） | 修复：① `cluster.py` 新增 `resolve_host()` **进程内解析缓存** + 统一 `_connect()`；② `cluster_web.py::_collect_status` 改用**已并行**的 `collect_frames()/collect_status()`；③ 新增 `with_list=False` 跳过慢的 `infer-list`。**实测热态 129.6s → 0.4s**（冷 16.5s 含首次解析） |
| F20 | ✅ **已修（2026-09-14）**。前端由「定时间隔触发」改为**「完成后自调度」+ in-flight 去重**（`statusBusy`/`planesBusy` 守卫）。**实测**：`setInterval(` 实际调用 0 次；30s 内串行完成 75 次请求（各 0.4s）；**8 并发全部 0.5s 内返回** | 设计缺陷（严重） | 修复见上。原「约 26 并发 × 9 ssh ≈ 234 连接」的风暴条件已消除 |
| F25 | **`infer-list` 自身耗时 10.3s**（三站一致，与 ssh/mDNS 无关）：这是 `/api/status` 修完 mDNS 后**残留的 10.8s 瓶颈**。CLI `status`/`status --all` 仍受其影响 | 脚本性能 | ✅ web 路径已跳过（`with_list=False`）；CLI 保留（该字段 CLI 要显示）。后续可优化 `infer-list` 本体 |
| F26 | **mDNS 解析是 cluster.py 全域慢的根因**：`*.local` 解析单次 ~14s，而 `ssh_run` 原先每次连接都解析。已用进程内缓存修复；**CLI 每进程仍付一次 ~14s**（`secrets scan` 实测 16.8s） | 环境/实现 | ✅ 已缓存修复；**可选进一步优化**：在 `C:\Windows\System32\drivers\etc\hosts` 加 `192.168.1.33 scott-lau-NEX.local` / `192.168.1.32 scott-lau-GTR-Pro.local`（需管理员），可让全部工具（含浏览器 PANELS 链接）免除该 14s |
| F21 | **页面无 agent 配置管理入口**：仅有 `/api/load\|unload\|backend`（本地引擎操作）；**不存在** `/api/secrets`、`/api/providers` ⇒ 三平面只能**观测**不能**管理**，"统一管理页面"名不副实 | 能力缺口 | 记档：观测层可用，管理层缺失 |
| F22 | **`providers` 观测有盲区**：不覆盖 provider `baseURL`、`claude.baseURL`、`claude.modelOverrides` 内容 ⇒ 漂移不可见。本次靠**旁路探测**才发现 A 站 `cluster-litellm` 指向**死端口 `:42387`**、`claude.baseURL` 指向未运行的 LM Studio `:1234` | 观测缺口 | ⏳ 待补：纳入 `providers` 采集 |
| F23 | **本地引擎忽略请求的 `model` 字段（决定性发现）**：B `:8080`(unsloth studio) 与 `:32837`(llama-server, `--alias`) 用 `__bogus_nonexistent__` 等不存在的模型名**均返回 200**，响应体回填真实模型名 ⇒ `model` 是纯装饰。**推论：三站 agent 配置可做到字节级统一**（模型标识类字段取任意常量即可），配置与"运行时加载什么模型"彻底解耦 | 认知修正（原判"modelOverrides 无法字面统一"错误） | ✅ 已记档：调研报告 §9；据此产出统一可行性结论与 4 项待决 |
| F24 | **`cluster-litellm` 三站语义互不相同**（名实不符）：B `:32837` 是 **unsloth studio 自拉的第二引擎**（与 `:8080` 同模型，差别在 `--parallel 4`），非网关残留；A `:42387` **确为死端口**；C `:8080` 指向正确但名不副实 | 命名债 + 认知修正 | 记档：统一时按 D-a/D-c 处置（B 保留则唯一有意差异；A 应删） |
| F13 | **A 站两把不同的 DeepSeek key（已取证消解 + 已处置）**：`~/.hermes/auth.json`/`.env` 一把（hash `1b179602ec`）、`~/.claude/cc-haha/providers.json` 另一把（hash `0404235950`）。**实测两把均被 DeepSeek 官方判定 invalid**（`/user/balance` 返回 `Authentication Fails, Your api key: ****xxxx is invalid`，无 key 对照组同为 401） | 明文死凭据 | ✅ 消解：不存在"哪把在用"，降级为清理死凭据。**cc-haha 已于 2026-09-14 移除**（A 48K+12K / B 18M+255M 安装介质；归档至 `~/.local/share/removed/`；A 站因 Trae 在运行而保留其 2 处内部状态）。详见调研 §3.2-3.4 |
| F14 | **B 站 `opencode.jsonc` 非法根级键 `cluster-local`**：与 `provider.cluster-local` 重复定义的 schema 外键 | 配置卫生 | ✅ 已修：移除该键（备份 `.bak-rootkey-20260914`），`opencode debug config` EXIT=0 且 `provider.cluster-local` 保留 |
| F15 | **OpenRouter 存在区域封锁**：8 个候选模型中 `google/gemini-2.5-flash` 返回 403 `This model is not available in your region.`；其余 7 个（deepseek 系 / qwen3.5-27b / glm-5 / llama-3.3-70b / kimi-k2 / mistral-small-3.2）均 200 | 出站约束（选型依据） | 记档：ADR-0003 选型须避开区域封锁档；已并入调研 §4 |

## 4. 验收通过标准

1. §3 全部 ☑（基础 9 项 + 框架扩展 10-18，共 18 项全过；统一入口扩展 19-28 全过）
2. P2/P3 约束在实施代码中可见（不解析表格路由 / e2e exit 3 语义）
3. IMPL 状态 draft → verified；ADR-0001 §决策 3 标注已完成
4. cluster.py 经 `python -m py_compile` 无语法错误（实施内自检项）

## 5. 审查签章

| 角色         | 结论                                           | 时间         |
| ---------- | -------------------------------------------- | ---------- |
| 文档审查（Trae） | 4 处问题（P1 逻辑缺陷/P2 契约风险/P3 行为缺口/P4 验收缺口）已处置，通过 | 2026-09-01 |
| 实施验收（Trae 执行） | 9 项全过；4 项实施期新发现（F1-F4）记档 §3.1 | 2026-09-01 23:45 |
| 用户终审       | ☑ 裁决项 a/b 已批（cluster.py 落 ops/、html 进 gitignore） | 2026-09-01 |

## 修订历史

| 日期         | 变更                               |
| ---------- | -------------------------------- |
| 2026-09-01 | v1.0：第 1 轮文档审查（P1-P4），IMPL 已同步修正 |
| 2026-09-01 | v1.1：实施完成，§3 九项全勾 + F1-F4 新发现记档 |
| 2026-09-13 | v1.2：框架管理扩展验收 §3.2（10-16 全勾）+ F5/F6/F7 新发现记档；IMPL §3.7 / ADR-0001 §3.4 回写 |
| 2026-09-13 | v1.3：claude 框架维（#17）与 Web UI（#18）验收补勾（实测三站 claude 均 STOPPED；web 鉴权/后端拒绝/端口释放离线验证）；IMPL §3.7 / 手册 §2.4 / ADR-0001 §3.4 同步 |
| 2026-09-14 | v1.4：统一入口四平面验收 §3.3（19-28 全勾）+ F8-F12 新发现记档；明文治理落地（三站 `{file:}`/`apiKeyHelper` 引用化 + 备份脱敏归档）；IMPL §3.8 / ADR-0003 / 密钥轮换清单 同步 |
| 2026-09-14 | v1.5：**更正 F10**（证伪"opencode 既有缺陷"，真因=默认模型免费档低吞吐，成功率 40%）+ 新增 F13（A 站两把 DeepSeek key 无单一真值）；新增调研报告 [2026-09-14_暴露问题调研.md](../../docs/research/2026-09-14_暴露问题调研.md)；ADR-0003 同步更正 |
| 2026-09-14 | v1.6：F13 取证消解（两把 DeepSeek key 均被官方判定 invalid，cc-haha 已停用）；F14 已修（B 站非法根级键）；F15 新增（OpenRouter 区域封锁实测）；默认模型统一待裁决 D1 |
| 2026-09-14 | v1.7：**F10 三次修正终版**（免费档间歇性慢、与调用形式无关、合并采样 ≈59%，且手册 `§2a.4` 两月前已记档）；**F12 修正**（默认模型漂移是既定策略非残留，故默认不动）；F16 新增（诊断流程缺陷：调研前未检索既有记档）；`oCrun` 兜底包装落地三站 |
| 2026-09-14 | v1.8：**cc-haha 移除执行**（A 48K+12K / B 18M+255M；归档 `~/.local/share/removed/`；A 站 Trae 在运行故保留其 2 处内部状态）；F13 状态更新为"已处置"；调研报告新增 §3.4 执行记录 |
| 2026-09-14 | v1.9：**F17 门禁精确化**（逐模型而非整档，`nvidia/*:free` 裸 API 200）并修掉 judge 槽必 403 的现存 bug；**用户指定 5 档 OpenRouter 优先级落地三处镜像**；F18 新增（区域封锁/限流实测）；调研报告新增 §7；ADR-0003 / 手册 `§2a.5` 同步 |
| 2026-09-14 | v2.0：**agent API 配置闭环审计 + 管理页面可用性审计**（调研报告 §8）。新增 F19（`/api/status` 129.6s，串行 9 ssh）/ F20（轮询无去重 → ssh 风暴）/ F21（页面无配置管理入口）/ F22（`providers` 观测盲区）。结论：配置**仅 2 个维度闭环**，页面**主面板实质不可用** |
| 2026-09-14 | v2.1：**A/B/C 配置统一可行性调研**（调研报告 §9）。F23 决定性发现（**本地引擎忽略 `model` 字段** ⇒ 三站配置可字节级统一）；F24 澄清 `cluster-litellm` 三站语义（B 为 studio 自拉第二引擎、A 为死端口）。结论：**可以完全统一**，剩 4 项待决（B 第二引擎 / A LM Studio / 统一命名 / 默认模型）+ 运行时不统一 |
| 2026-09-14 | v2.2：**F19/F20 已修并验收**——真因纠正为「**mDNS 每次解析 ~14s**」（非"串行"），修法=解析缓存 + 复用并行收集 + 跳过 `infer-list`；`/api/status` **129.6s → 0.4s（热）**，前端改「完成后自调度 + 去重」，8 并发 0.5s。新增 F25（`infer-list` 自身 10.3s）/ F26（mDNS 根因 + hosts 可选优化） |
| 2026-09-14 | v2.3：**A/B/C agent 配置统一执行完成**（调研报告 §9.9）。Phase 1 opencode+claude **字节级统一**（sha256 三站一致）+ claude 端到端验证；Phase 2 hermes **三站铺开**并用 `hermes -z` 端到端验证（`HERMES_OK`）。新增 F27（hermes key 只认 config 路径）/ F28（hermes 64K 上下文下限）/ F29（hermes config.yaml 未字节级统一）；F12 标记为已统一 |
| 2026-09-14 | v2.4：**A 站 hermes 历史遗留清理**（口径=LM Studio 时代）。`config.yaml` 顶层键 23→21（删 `provider: lmstudio` + unset `api_key`）、`.env` 删 `LM_API_KEY`、`models.json` 7→4（删 3 条 `:1234`）；全量备份 `*.bak-legacy-20260914`；验收 `config get model` 5 键完整 + `status` 仍 Custom endpoint。F29 更新为"遗留已清、文件仍非字节级相同" |
| 2026-09-16 | v2.5：**F26 根因根治（[ADR-0006](../../adr/ADR-0006-控制面传输绑定LAN_IPv4.md)）** —— 查明"每次 ssh 白付 ~14s"的真身是**主控解析 `*.local` 需 16-17s 且只返回公网 IPv6**（控制面实际**经 ISP IPv6 绕行、不在 LAN 内**；站上 `$SSH_CONNECTION` 证实；`ControlMaster` 在 Win32-OpenSSH 9.5p1 不可用）。处置 = `~/.ssh/config` 把 A/B 名字 `HostName` 绑定 LAN IPv4（**无需管理员，取代 F26 原 hosts 方案**）+ `cluster.py` STATIONS 改 IPv4 + LAN 真值入 `inventory/net.yaml` 的 `lan` 段 + 门禁 `stations` 新增 **(h)** 防漂移断言。实测按名 **16.2s → 0.18s（≈90×）**、单次 task run **421s → 48.5s**。**F26 闭环** |

