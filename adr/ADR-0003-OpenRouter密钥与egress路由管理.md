# ADR-0003: OpenRouter API 密钥与 egress 路由管理

***

id: ADR-0003
type: adr
version: 1.0
status: accepted
date: 2026-09-14
depends: \[ADR-0002, d6-agent-standard-OPEN-ISSUES(O-16)]
upstream: \[ADR-0002]
-------------------------------------

> **Feature**: 引入 OpenRouter 作为 egress（出站）商业推理源，规范其密钥生命周期、注入机制、用途分级与路由定位。
> **创建日期**: 2026-09-14
> **状态**: accepted
> **适用**: D6 agent 标准框架的 egress 商业源、review judge 商业槽、research-lookup 学术检索

***

## 元数据

| 字段   | 值 |
| ---- | ---- |
| 编号   | ADR-0003 |
| 日期   | 2026-09-14 |
| 状态   | accepted |
| 决策者 | Scott (鹏) |
| 相关文档 | [ADR-0002](ADR-0002-网关401故障根因与fan-out路由决策.md)、[OPEN-ISSUES.md](../spec/d6-agent-standard/OPEN-ISSUES.md)（O-16）、[2026-09-13_密钥轮换清单.md](../docs/security/2026-09-13_密钥轮换清单.md)、agent-cli.ps1 JUDGE_TABLE |
| 取代   | 无（新增） |

**证据等级约定**: E1=本会话实测；E2=前会话实测留档；E3=外部文档；E4=推断。

---

## 背景（Context）

1. **O-16 商业 API 子路自 2026-09-12 空置**: review 评审环五源路由已落地（egress/local/http/http-local），其中 **source ① `commercial`（type=`http`）** 一直为 open：`JUDGE_TABLE['commercial']` 存在但需 ENV `REVIEW_COMMERCIAL_BASE/KEY/MODEL` 注入，未设时抛 `JUDGE_UNREADY` exit 7（[agent-cli.ps1 L1834-1835](../ops/station-bin/agent-cli.ps1)）。缺的正是「商业 API 端点/key 封装」。
2. **ADR-0002 已退役 LiteLLM 网关**: 决策 C（绕网关直连）的核心理由是消除「中间层持有与后端不同步状态」这一故障类；网关进程保留但不作为 agent 常用路由必经跳点。
3. **`secrets/` 密钥库已立规但当前为空**: 安全文档 [2026-09-13_密钥轮换清单.md L60](../docs/security/2026-09-13_密钥轮换清单.md) 已固化「新增任何密钥写入 `secrets/`，禁止硬编码进脚本/文档」；`.gitignore` 覆盖 `secrets/`、`*.key`。
4. **OpenRouter 已被多处声明依赖**: research-lookup skill 依赖 `OPENROUTER_API_KEY`（parallel-cli），文档多处引用其作为 Anthropic Messages API 兼容后端。

**结论**: 引入 OpenRouter 不是从零新建，而是**填补既有接口点的空缺**——`Invoke-JudgeHttp(base,key,model)` 已是通用 OpenAI 兼容客户端（L1761），OpenRouter 直插。

---

## 决策（Decision）

### D1. 密钥单一真值：`secrets/`
- 机密 key → `secrets/openrouter.key`（单行；`.gitignore` 已覆盖，绝不入库）。
- 非机密参数（base/model）→ `secrets/openrouter.conf`（`key = value`，`#` 注释）。
- **铁律**：key 只存 `secrets/`，禁止硬编码进脚本或文档（2026-09-13 历史重写事故的直接教训）。

### D2. 注入机制：dot-source loader（进程级 env）
- 新增 `ops/station-bin/_env_openrouter.ps1`，以 `. <path>` 加载，读 `secrets/` 并注入会话 env：
  - `REVIEW_COMMERCIAL_BASE/KEY/MODEL` → agent-cli `commercial` judge 槽
  - `OPENROUTER_API_KEY` / `OPENROUTER_BASE_URL` → research-lookup skill
- 只读不写、不回显完整 key（仅回显末 4 位）；占位符/空值即报错。
- 理由：符合 `ops/station-bin/_*.ps1` 惯例（同 `_r_sympy_provision.sh`），零常驻、零新依赖。

### D3. 用途三线（分级）
| # | 用途 | 载体 | 状态 |
|---|------|------|------|
| ① | **judge commercial 槽**（异源评审） | `review --model commercial` → JUDGE_TABLE type=http | 本期接入（填 O-16 缺口） |
| ② | **research-lookup 学术检索** | `OPENROUTER_API_KEY`（parallel-cli） | 本期接入（env 已注入） |
| ③ | **站内 agent egress 兜底** | 三站 opencode openrouter provider（本地引擎全停时） | **Phase 2**，见 D5 权衡 |
| ④ | 其他自定义用途 | 复用 `OPENROUTER_API_KEY`/`OPENROUTER_BASE_URL` | 预留 |

### D4. 合规分级：egress = 仅 public/sanitized
- OpenRouter 属**出站**，与 `ultra`（Zen）同类。`Invoke-Router` rule B 已硬约束：`local-only + egress → exit 4`（不可覆写）。
- 故 OpenRouter **只能服务 public/sanitized 任务**；`local-only` 一律拒。此门现成、无需新增代码。

### D5. 与 ADR-0002 的关系：直连注入，不复活网关
- OpenRouter 是**外部 egress 端点**，不持有本地后端 key → **不属** ADR-0002 所针对的「中间层状态漂移」故障类。
- 因此采用「loader 直连注入 env」，**不**经本地网关中转，与 ADR-0002 哲学一致。
- **站内 egress（D3③）的权衡 —— 已决策（2026-09-14 落地）**：采纳选项 **(a) 受控分发 + 引用化**。三站确实需持有 key 才能直连 OpenRouter，但「持有」不等于「散落」：
  - key 只落在 `~/.config/rpc/<name>.key`（目录 700 / 文件 600 / 无尾换行）单一落点；
  - `opencode.jsonc` 用官方 `{file:...}` 引用、`settings.json` 用 Claude Code `apiKeyHelper`，**配置文件内不含明文**；
  - 主控 `secrets/stations/<st>/` 为正本，轮换经 `cluster.py secrets push` 下发；
  - 历史明文备份脱敏归档至 `backups-keys-<date>/`。
  - 理由：选项 (b) 会让站内 agent 在本地引擎全停时失去兜底；而 (a) 在保留兜底的同时把明文面收敛到「每站 1 个 600 文件 + 1 个正本」，未破坏单一真值原则。

---

## 否决/比较对象

| 方案 | 结论 | 理由 |
|------|------|------|
| 复活 LiteLLM 网关做 OpenRouter 中转 | ❌ 否决 | 重引入中间层状态（ADR-0002 已裁该故障类）；OpenRouter 无本地 key 漂移问题，网关在此为纯开销 |
| key 硬编码进脚本/任务卡 | ❌ 否决 | 违反安全铁律；2026-09-13 因硬编码 unsloth key 被迫全量历史重写 |
| 仅会话级手动 `$env:` set | ⚠ 次选 | 简单但重启即丢、易漏；loader 可复用且集中校验，故取 loader |
| 三站直接分发 key（本期做） | ⏸ 延后 | 与单一真值原则冲突，需显式决策（见 D5） |

---

## 后果与待办

**已完成（Phase 1，console-side）**
- `secrets/openrouter.key` + `secrets/openrouter.conf`（模板，gitignore 覆盖）
- `ops/station-bin/_env_openrouter.ps1`（loader；AST 0 错误 + BOM 保留）
- 本 ADR

**待办**
1. ✅ 用户填入真实 key（`secrets/openrouter.key`）+ 选定默认模型（`secrets/openrouter.conf`）
2. ⏳ 实测 `agent-cli review --model commercial` 端到端（回填 O-16 source ① 关闭证据）—— 注意 `:free` 档不走此路（见实测补充）
3. ✅ Phase 2 决策：站内 egress 采用「受控分发 + 引用化」（D5）
4. ✅ 密钥清单登记：`docs/security/2026-09-13_密钥轮换清单.md` 已回写收敛状态与新轮换流程
5. ✅ 成本监控：`cluster.py egress` 已实现（`GET /api/v1/key` 查用量/余额，强制 IPv4）
6. ⏳ **密钥轮换**（用户动作）：OpenRouter 控制台 + unsloth studio 吊销旧 key —— 收敛只是止损，轮换才封堵已发生的暴露

**风险**
- 付费服务，需用量监控防超支
- 出站面扩大（虽已由 rule B 约束 local-only），敏感任务须确认走站内模型

---

## 关联

- [ADR-0002](ADR-0002-网关401故障根因与fan-out路由决策.md)：网关退役与直连哲学（本 ADR 与之对齐）
- [OPEN-ISSUES.md](../spec/d6-agent-standard/OPEN-ISSUES.md) O-16：商业 API 子路（本 ADR 填 source ①）
- [2026-09-13_密钥轮换清单.md](../docs/security/2026-09-13_密钥轮换清单.md)：密钥存储规范
- `ops/station-bin/agent-cli.ps1`：JUDGE_TABLE（L1657）+ Invoke-JudgeHttp（L1761）

---

## 实测补充（2026-09-14，E1）

完整调研见 [2026-09-14_OpenRouter接入与agentic-harness门禁调研.md](../docs/research/2026-09-14_OpenRouter接入与agentic-harness门禁调研.md)。三项关键发现**修正/细化了本 ADR 的原始假设**：

1. **密钥合法**（`/api/v1/key` 200，usage=0，无 limit，非 free tier）。
2. **`:free` 档的 harness 门禁是「逐模型」而非「整档」**（2026-09-14 实测修正原表述）：裸 API 调 `thinkingmachines/inkling:free` → 403「only available on agentic harnesses」；但 **`nvidia/nemotron-3-ultra-550b-a55b:free`、`nvidia/nemotron-3-super-120b-a12b:free` 裸 API 返回 200**。故原判「D3① 裸 API judge 路线对 `:free` 不成立」**需收窄**：对 `thinkingmachines/*` 成立（只能经 harness），对 `nvidia/*` **不成立**（裸 API 可用）。
   - **据此已修正一处现存 bug**：`secrets/openrouter.conf` 的 judge 槽原填 `thinkingmachines/inkling:free`（harness-only）→ 裸 API 必 403；已改为通用的 `nvidia/nemotron-3-ultra-550b-a55b:free`。
   - 结论：**egress 双轨表述更新为「harness 轨（全部 `:free`）+ 裸 API 轨（裸可用档，含部分 `:free`）」**。

**OpenRouter 模型优先级（2026-09-14 用户指定）**：权威清单在 `secrets/openrouter.conf` 的 `harness_priority` 键，三处镜像（站内 `opencode.jsonc` 的 `provider.openrouter.models`、站内 `oCrun` 默认链、[调研报告 §7](../docs/research/2026-09-14_暴露问题调研.md)）：

| 序 | 模型 | harness | 裸 API | 判定 |
|----|------|---------|--------|------|
| 1 | `thinkingmachines/inkling:free` | ✅ | 403 | 仅 harness |
| 2 | `nvidia/nemotron-3-ultra-550b-a55b:free` | ✅ | **200** | **通用（judge 槽已用此档）** |
| 3 | `thinkingmachines/inkling-small:free` | ✅ | 403 | 仅 harness |
| 4 | `nvidia/nemotron-3-super-120b-a12b:free` | ✅ | **200** | **通用** |
| 5 | `poolside/laguna-s-2.1:free` | ❌ 限流 | 429 | 当前不可用（保留占位） |
3. **主控站 IPv6 到 openrouter.ai 黑洞**：`.NET Invoke-RestMethod`（`Invoke-JudgeHttp` 所用）优先 IPv6 → 超时；curl -4 / claude code 走 IPv4 → 200。**D3① 路线存在 IPv6 阻塞，须先修**（改走 `curl.exe -4` / hosts 强制 IPv4 / B 站中转）。

**新增实证（支持 D3③ harness 路线）**：claude code（v2.1.207）+ `ANTHROPIC_BASE_URL=https://openrouter.ai/api` + `ANTHROPIC_AUTH_TOKEN` + `ANTHROPIC_API_KEY=`（置空），`claude -p ... --model thinkingmachines/inkling:free` → **实测返回 OK**，门禁解除。故 **harness 类接入（claude code / opencode / hermes）是 `:free` 模型的正确落点**，本 ADR 的 egress 定位由「judge 裸 API」扩展为「**judge（非门禁模型）+ harness（门禁免费模型）双轨**」。

---

## 实施补充（2026-09-14，站内收敛 + 统一入口）

**明文治理（D5 落地）**

| 动作 | 结果 |
|------|------|
| 站内落点 | 三站 `~/.config/rpc/`（700）；A: openrouter/rpc/unsloth，B/C: openrouter/unsloth/claude（+ `claude-key.sh` 700） |
| opencode 引用化 | 三站 `opencode.jsonc` apiKey → `{file:...}`；`opencode debug config` 实测解析出真实 key、无残留 `{file:` |
| claude 引用化 | B/C `settings.json` 移除明文 `ANTHROPIC_AUTH_TOKEN`，改 `apiKeyHelper`；Claude Code 2.1.258 实测完成一轮对话 |
| 历史备份 | A 13+1 / B 15+4 / C 2+3 个备份文件脱敏归档；IDE Local History 2 处就地脱敏 |
| 巡检结果 | `cluster.py secrets scan` → 三站明文命中 0，PASS |

**关键实现事实**：`{file:~/.config/rpc/x.key}` 是 opencode 官方文档明确的「把 API key 放独立文件」写法，路径支持 `~`；文件须**无尾换行**（opencode 原样取用内容）。注：`opencode.jsonc` 本身无尾换行，探查脚本拼接 marker 时需前置换行，否则 marker 会被粘到上一行。

**统一入口（cluster.py 扩为四平面）**

| 平面 | 子命令 | 覆盖 |
|------|--------|------|
| ① 本地引擎 | `frames` / `load` / `unload` / `status` | 已有 |
| ② 凭据 | `secrets {status\|scan\|push}` | 新增：落点/权限/明文巡检/正本下发 |
| ②b Provider | `providers` | 新增：provider 集合、默认模型、凭据引用形态、漂移检测 |
| ③ 出站 | `egress` | 新增：主控+三站 → OpenRouter 健康/用量/余额（强制 IPv4） |
| 汇总 | `status --all` + `cluster.py web` | 新增：四平面一屏；Web 增 `/api/planes` 面板 |

**实测值（2026-09-14）**：主控与三站 `egress` 均 http=200，同一 key（`label` 一致），单程 0.6~1.8s，IPv4 绕开 IPv6 黑洞。

**发现的配置漂移（非密钥问题，待显式决策）**：三站 opencode 默认模型互不相同 —— A `opencode/nemotron-3-ultra-free`、B `opencode/nemotron-3.5-lightning-free`、C `cluster-litellm/nemotron`；A 站独有 `cluster-local`/`lm-studio-local`，B 站独有 `cluster-local`。已由 `providers` 持续暴露。

**未闭环（2026-09-14，三次修正后的终版）**：原记「`opencode run` 在 B 站无输出，疑为既有缺陷」**结论有误**。经三轮复核：① 证伪"站点问题/opencode 缺陷"（A/B 成功率一致、同一模型前后结论相反）；② 证伪"调用形式是主因"（位置参数 4/4 成功、stdin 管道 2/4，两种形式都间歇性慢，手册 `§2a.4` 铁律 2 的绝对表述本轮未复现）；③ **终版**：`opencode/*` 免费档（opencode 官方 zen，`api.opencode.ai` + `zen/v1`，外部出站且无 SLA）**间歇性慢** —— 合并采样 10/17 ≈59%，失败恒为 rc=124 且输出字节>0（在生成，只是慢）；叠加 `opencode run` 无默认总超时 → 表现为无反馈等待。

**同时暴露两个缺口**：
1. **可用性缺口**：既定策略（手册 `§2a.4` 铁律 3：默认免费档省本地算力 + 敏感内容显式 `-m` 本地）本身合理，但缺兜底 → 已用 `oCrun`（三站 `/usr/local/bin/ocrun`，超时+自动切档链：免费档 → OpenRouter 自持档 → 本地）补齐。
2. **合规缺口**：opencode 侧**无 local-only 技术门禁**，`Invoke-Router rule B` 不覆盖其自身请求；与 D4「egress 仅 public/sanitized」的一致性**依赖使用者自觉**。另注：免费档官方 Privacy 明文说明数据用于改进训练，风险高于普通付费 egress。**待后续加门禁**。

详见 [2026-09-14_暴露问题调研.md](../docs/research/2026-09-14_暴露问题调研.md)（含方法论教训：P1/P2 初稿结论均因**未先检索既有记档**而出错）。
