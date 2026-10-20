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

## 考虑的替代方案（Alternatives Considered）

> 2026-09-25 节名统一（原名「否决/比较对象」），**内容未改**。

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

**免费档每日计数（2026-09-16，G13/O-07 扩展）**

**问题（用户）**：OpenRouter 当前 20 请求/分、最高 1000 请求/日，可否建立"免费额度每日计数机制"。

**调研（E2，2026-09-16）——先厘清两个出站源**：`opencode/*` 免费档走 **opencode 官方 zen**（`api.opencode.ai`+`zen/v1`，无 API 可查额度）；而 **OpenRouter**（`openrouter.ai`，本框架 `openrouter` provider / review commercial / egress 探针）是独立 egress 源。用户问的是 OpenRouter。

**OpenRouter 免费档限额（官方限制页 + 社区，2026）**：
- **20 请求/分**（固定，充值不升）；**每日 50（从未充≥$10）/ 1000（曾累计充≥$10，一次性解锁永久生效）**。
  - ★★ **2026-10-20 带上下文重取（E3）· 两处收窄**：**(1)** 官方 limits 页逐字「you can make up to **20 requests per minute**」—— ★ **该页【未】写"per account"**，且这段挂在「apply to certain types of requests, **regardless of account status**」这句引子下 ⇒ ★★ **仓内曾流传的「20 请求/分/**账户**」限定词 = 官方文本不支持的加工**。**(2)** 官方 SDK 页逐字：`free_model_daily_requests` = 「daily request quota **for the account that owns the key** … the counter **resets at UTC midnight**」· `limit` = 「ceiling depends on **total credits purchased** and is **independent of `is_free_tier`**」⇒ ★ **日界 = UTC**；★ 且**不看 `is_free_tier`** ⇒ 仓内 `_free_quota()` 的 `is_free_tier` 推断 = **代理判据（待裁 · R4）**。★ 详见**下方 2026-10-20 块**。两页出处见 [裁决分析稿 §5.4](../docs/2026-10-20_O-147丙落点偏离设计稿_裁决分析.md)。
- 429 响应带 `X-RateLimit-*` 头（服务器真值）；**429 计入每日配额**；**跨 key 全局治理**（多建 key 不能绕过）。
  - ★★ **2026-10-20 就地收窄（E2 实测）**：原句写的是「**429/失败请求仍计入每日配额**」，实测**只对 429 成立**、**对 400 类客户端错误不成立** —— 连打 **20 次全 400**（服务端逐字 `{"error":{"message":"JSON parsing failed"}}`，纯客户端问题）后，账户 `KMUr` 的 `free_model_daily_requests.used` **纹丝未动**（**5 → 5**）。⚠ **429 那一半本轮【没测到】**（20 次全 `200`、零 429）⇒ **按原样保留**：既不冒认、也不否认。★ 出处与判据 = [docs/2026-10-20_O-147丙落点偏离设计稿_裁决分析.md](../docs/2026-10-20_O-147丙落点偏离设计稿_裁决分析.md) **§10.8**。
- **关键：OpenRouter 不提供"免费请求剩余数"的可查询 API** —— `GET /api/v1/key` 的 `usage` 是 **credits 用量**（免费档恒 0），不反映免费请求数。官方"检查限额"指引实际只覆盖 credits/402。

> ### ⚠ 更正（2026-09-21，实测推翻上一条）—— **服务端现已提供按 key 的免费请求计数**
>
> 上文"**不提供**"**已过时**。实测 `GET /api/v1/key`（Bearer = 该端 key）现返回：
> ```json
> {"creator_user_id":"user_…",                          // 账户身份（拆分验收判据）
>  "is_free_tier":false,
>  "free_model_daily_requests":{"used":8,"limit":1000,"remaining":992},   // ← 就是"免费请求剩余数"
>  "usage_daily":0,"usage_weekly":0,"usage_monthly":0,  // 付费 credits 口径（:free 模型恒 0）
>  "limit":None,"limit_remaining":None}                 // 信贷额度（新账号可能非 null）
> ```
> **实测要点（四条，均 2026-09-21 采）**
> 1. **确实计数 `:free` 模型请求**：B 站一次 `opencode -m openrouter/…:free` + 一次裸 `POST /v1/chat/completions`（`nvidia/…:free`）⇒ B **0→2**；C 站一次 ⇒ **0→1**；而 console/A **保持 8 不变**（证明**按账户隔离**）。同两次调用 `usage*` 仍为 0（`:free` 模型无 credits 成本）。
> 2. **⚠ 有分钟级延迟（要紧）**：调用后 **20 秒内读仍为 0**，约 **4 分钟后**才显示 2/1。⇒ 该字段**不能当"调用前实时闸门"**（会造成"以为没用额度而超额"），**只适合巡检/预警/事后对账**。
> 3. **口径必须分开**：`:free` 请求数看 `free_model_daily_requests`；付费模型看 `usage_daily`/`usage_monthly`（credits）。**两者不可混算**。
> 4. **账户级 vs key 级未区分**：该字段随 key 返回，与上文"跨 key 全局治理"一致（**账户级**）；本次**未能实测区分**（console/A 本就是同一把 key），不冒认。
> 其它：`GET /api/v1/activity` → **403**（不可用）；`GET /api/v1/credits` → `{total_credits,total_usage}`（**账户级**，非 key 级）。
>
> **⇒ 修正结论**：**"本地自建计数"不再是唯一手段**；服务端计数**已可用但延迟分钟级** ⇒ 设计上应**两者并用**：服务端为**权威（巡检/预警/对账）**，本地 `.egress_daily.json` 降级为**实时近似 + 交叉验证**（可发现"未被记录的调用方"）。
> **⚠ 已知待改（`egress` 显示）**：`_parse_egress`（`cluster.py` L1106）现在读的是 **`limit_remaining`（信贷余量）** 却显示成"**余 N**"，易被误读为"配额剩余"；且 L1253 仍打印"OpenRouter 无免费请求剩余 API"的**过时提示**。两处应随本次更正一并改（读 `free_model_daily_requests` + 双口径展示）。
> **现状（本次分配后）**：console+A = 账户 `…KMUr`（共用一把，8/1000/992）；B = 新账户 `…LEF3y`（0/1000/1000）；C = 新账户 `…svcX`（同）—— 三者 `paid`、各自 1000/天，**已实测按账户隔离**。详见 [多账户配额分配与调配设计](../docs/security/2026-09-21_OpenRouter多账户配额分配与调配设计.md)。
> ★ **2026-10-20 追加**：**console+A 与 A 站【确系同一把 key】**（sha256 前 12 位逐字相同 = `5847f7de8218`）⇒ ★ 账户 `KMUr` **在册只有一把 key**；★ "跨账户隔离"**取到第 2 条读数**（打 A 20 次后，B/C 的 `used` **零位移** 22→22 · 2→2）⇒ 该句结论**被加强**（详见下方 2026-10-20 块 · R5 与跟进）。
>
> ### ★★ 2026-10-20 口径清理（用户令「执行批次①：裁定 R1 并清理 ADR-0003 口径」）
>
> **背景**：本日 `O-147` 乙+丙 落地后，先查出其丙"**落点偏离设计稿 §6**"，再对 OpenRouter 前提做了一次**实测核查**（20 次 `:free` + 等 ≥300s + 四端点读数）。⇒ 本节 = **一次裁定 + 四处口径清理**。★ 逐项依据 = [待裁清单稿](../docs/2026-10-20_待裁事项依赖链与执行顺序.md) §4① · [裁决分析稿](../docs/2026-10-20_O-147丙落点偏离设计稿_裁决分析.md) §7/§10/§10.8。
>
> **R1（本地计数器的落点）⇒ 裁【丙：废弃 `.egress_daily.json`、单件承载】** —— 理由三条：**①** 旧件**按构造恒 0**（`_egress_bump` **全仓零调用点** + `ops/.egress_daily.json` **盘上不存在** ⇒ `cmd_egress` 的旁证行**恒印 `0/1000`**，本日 `py ops/cluster.py egress` 实测见到）⇒ **"维持两件"= 留一个死件**；**②** **同名两件**易被读错（两件都叫"本地计数"、而定义域不同 = 一个 ⊂ 另一个）；**③** 与"**分片 = 一个计数器 + 求和**"的规范形态同构（Firestore sharded counter / CRDT G-Counter）。★ 另：该件**覆盖面不含** `review` 判官出网等路径 ⇒ 已由**新件的"覆盖面写死 + 服务端差值"**取代（见 R2）。⚠ **实施面【待落】**：删/改 `cluster_egress.py`（`EGRESS_DAILY_FILE` · `_egress_daily` · `_egress_bump` · `_egress_save` + `cmd_egress` 旁证行）· `cluster.py` 重导出清单 · `.gitignore` L36 —— ★ 它动的是**行为面**（`cmd_egress` 的用户可见输出 + 写入面）⇒ **本批未动，另裁/另落**。
>
> **R2（本地计数的角色）⇒ 写进本 ADR**：本地/派发侧计数从"**旁证（实时近似 → 交叉验证）**"**升格为"派发决策的实时依据"**（`O-147` 乙+丙 的用法）。★ 这是**角色变更**（比形状变更更重）：上文"两者并用"那句只说了"服务端 = 权威"，**从未提"按站"这一维**，故在此**显式定性**。★ **覆盖面写死**：`ops/.egress_station.json` **只覆盖"默认出网档（`ultra` / `free-1m` / `lightning`）的 `task` 派发"** —— **不含** per-station 别名（`ultra-a/-b/-c`，它们**不进候选 ⇒ 不 bump**）· `review` 判官出网 · 人手动 TUI ⇒ ★ 故「**服务端 `used` − 该件 sum**」的差值 = **其余出网路径** ⇒ **这才是可解释的"未被记录的调用方"口径**（替换旧件那条**从未生效**的旁证）。
>
> **R3（两处口径就地更正）⇒ 即刻更正（纯文字、零行为）**：**①** 「**写入手 `_egress_bump()`**」**从未接线** —— 实测：**全仓零调用点**（仅定义 + `cluster.py` 重导出），该件**盘上不存在** ⇒ 下文那句"写入手…须在发请求前自增"**从未生效**（= 一面**假防线**）；**② 日界口径** —— 旧件代码用 `datetime.date.today()`（**本地日**），而注释与本 ADR 写"**UTC 日**滚动归零" ⇒ **代码与文档不符**；★ **裁定：日界一律以 UTC 为准**（官方 SDK 页逐字"resets at **UTC midnight**"）· 新的派发侧件**本就已是 UTC** ✓。
>
> **R5（口径边界 · 只登记）**：官方 SDK 页逐字「Accounts and endpoints **exempt from free-model limits** … **are not gated by it**, so `remaining` is the **tier policy rather than an enforced ceiling**」⇒ ★ 本仓三账户 `is_free_tier=false`（曾充值）**是否属 exempt【未核】**；若属，则 `remaining` 在它们身上是**档位政策值**、**不是硬闸** ⇒ **"服务端 = 权威"仍可作巡检/对账，但"打满即被拒"这一预期可能不成立**。★ **本批只登记，不为此实测**（它**不改变**"按站计数选站"的算法）。
>
> **R6（"20 请求/分"的引用 · 本批只落一半）**：★ 官方文本**未**写"per account"（见上文 L193 的 2026-10-20 收窄段）⇒ 仓内多处**加工出**的「**/账户**」限定词**不再成立**。★ **本批落**：本 ADR（L193）与 `cluster_egress.py` 相邻文案；⚠ **其余 ≈30 处（`agent-cli.ps1` L3903 / L4134 / **L5636** · 各文档）【未扫】** ⇒ **登记随批**（清单见裁决分析稿 §10.6 / §10.8）。
>
> ⚠ **本块零行为变更**：**未删旧件 · 未改 `_free_quota()` · 未改任何 `state` / 判据 / 门禁**。★ **未裁/未做清单** = [待裁清单稿](../docs/2026-10-20_待裁事项依赖链与执行顺序.md) §0。
>
> ### ★★ 2026-10-20 · 批次②（R4 + X1）【已裁并落】（用户令「按建议方案执行 R4 和 X1 的裁定与落地」）
>
> ★ 本块与上块**分开记账**：上块逐字写着"**本块零行为变更**"、且"**未改 `_free_quota()`**"—— ★ **那两句只对批次①成立**，本块**改的就是它**（故另起一段，避免把两批混成一句）。
>
> **R4 ⇒ 裁【甲】（日限额依据：**直读 `free_limit`** + 兜底如实报出）** —— 落点 `ops/cluster_egress.py`：新增 `_free_quota_effective(info) -> (quota, source)`（`source ∈ {'limit','fallback-50'}`）；`cmd_egress` 的旁证行改调它并**打印来源**（`限额来源: limit(直读服务端 free_limit)` / `★兜底档 fallback-50`）；`_free_quota()` **保留**为兜底（档位真值源只有 `free_limit` 一个）；`ops/cluster.py` 门面**新增重导出** `_free_quota_effective`（漏了会被门禁 `facade` 判红 —— 消费者引用的符号必须在门面可达名里）。
> ★ **先验红**：`tests/test_cluster_pure.py` 新增 7 条用例 ⇒ **实现前全红**（`<缺 _free_quota_effective>`）；**变异自证**：把兜底改成**非保守档** ⇒ 4 条 fail-closed 用例**当场红**（还原即绿）。
> ★ **同源对照（非恒真）**：样本 `is_free_tier=false` 但 `limit=50` ⇒ **甲（直读 50）≠ 乙（推断 1000）**—— ★ 对照项**刻意在测试里本地重写**（不复用生产函数），否则"实现一改、对照就跟着改"= 判据被实现拖着走。
> ★ **真跑**（`py ops/cluster.py egress`，只读 `GET /key`、零模型配额）：旁证行逐字 `本地计数(旁证, 仅主控侧入口) 0/1000 (限额来源: limit(直读服务端 free_limit))`，与四端 `free 25/1000 · A 25/1000 · B 22/1000 · C 2/1000` 一致。
>
> **X1 ⇒ 裁【甲】（`egress_pick` 段进 `.agent-run.json` · **X1′=甲 全量**）** —— 落点 `ops/station-bin/agent-cli.ps1`：新增**纯函数** `New-EgressPick`（五键 `alias` / `basis` / `candidates` / `chosen` / `route_station`，键序写死）；**主路**（`Invoke-Task` 的出网档派发点 L2496-2516）与**备路**（`Invoke-Task-Claude` 的选站点 L4513-4526）**各**建段，并在**两处 `Set-Content … .agent-run.json` 之前**注入 —— 与 `exec_host` / `d7_guard` **同址同法**（"先注入、后写盘"）；⚠ **绝不事后写**：该件**字节**被 `review.json.l1.record_sha256` 钉住（`O-139` 已写死）。★ **"跑过才加"**：主路只在**默认出网档**派发出现；备路只在 `$useStation`（真有站可选）出现。
> ★ **夹具** `_fm_golden_test.ps1` 新增 **8 条 `X1-egress⑬–⑳`**：形状 + 值直通 + **同源对照（只换依据 ⇒ `basis`/`chosen` 必不同）** + 候选去空 + ★★ **AST 判相对位置**（"注入 < 写盘"、**两处各判一次**）+ 防"只落一处" + 夹具内置**先验红**（写盘后才注入的样本上该判据为假）+ 结构护栏（两路各恰一处调 `New-EgressPick`）。
> ★ **手工变异自证**：把主路注入行**真挪到** `Set-Content` **之后** ⇒ `X1-egress⑰` **当场红**（`pass=624 fail=1`）⇒ 复原即 **625/0**。
> ★ **真跑两向（同源对照）**：同一张 `spec/d6-agent-standard/dogfood-cards/glob-probe.md`（`model: ultra`）连发两次 —— **① 状态件在**（`{C:0,B:1,A:1}`）⇒ `EGRESS_PICK: ultra route_station=B -> station=C candidates=C,A,B basis=local-count`（run `202610201702375715`，`exec_host=192.168.10.37` = C 站）；**② 删掉状态件**（fail-closed 轮转）⇒ `EGRESS_PICK: ultra route_station=B -> station=A candidates=A,B,C basis=fail-closed-rotation`（run `202610201703259134`，`exec_host=scott-lau-NEX.local` = A 站）⇒ ★★ **同一输入、只换依据 ⇒ `chosen` 与 `basis` 双双翻转**，且两次 `.agent-run.json` 的 `egress_pick` 与控制台行**逐字一致**（两载体互证）。
> ⚠ **诚实边界（不扩项）**：`exec_host` 由 `Resolve-D7Hosts -Station $station` **派生自 `$station`** ⇒ 它是**选站结论的投影**、**不是**"远端机器"的独立观测（同族：`Get-ActualStation` 正是为 claude 路"投影报错站"而建的读侧判据 · 见 `O-147` 格内已登记的边界）；本段落进证据链的是**选站结论**，不是机器实测。
>
> **门禁读数（本批末）**：`_fm_golden_test.ps1` **625/0**（617 + 8）· `py ops/rpc_check.py --quick` **39 绿 / 2 黄 / 0 红** · `py tests/run_py_tests.py` **52/52**。
> ★ **仍未做（**本批射程外**，如实）**：**R7**（`O-148` 的"发作 ⇒ 就地修 / 修不动 ⇒ 降级 + 留痕"）· **X2**（守门人可机判）· **R8**（同账户第二把 key · 需人工动作）· **R6** 剩余 **≈30 处引用清扫**（本批只有 ADR 的 L193 那半已在批次①落）· **X3**（同族另两处引用）。★ ~~**R1 实施面**~~ ⇒ ✅ **已在批次③落**（见下）。
>
> ### ★★ 2026-10-20 · 批次③（**R1 实施面**：清理旧件四件）【已裁并落】（用户令「继续执行 R1 实施面，清理旧件四件」）
>
> **裁【丙】· 废弃旧件 ⇒ 本地计数面「单件承载」**。★ **落点四件**：
> **①** `ops/cluster_egress.py`：删 `EGRESS_DAILY_FILE` · `_egress_daily()` · `_egress_bump()` · `_egress_save()`；★ 新增读者 `_egress_station_today(path=None)`（读**派发侧** `ops/.egress_station.json` ⇒ `(per_station, reason)`）与常量 `EGRESS_STATION_FILE`。
> **②** `cmd_egress` 的**旁证行** ⇒ **改**为**对账行**（"单件承载"+"差值"口径）：逐字读数（本批真跑）`限额 1000 (来源: limit(直读服务端 free_limit))` · `派发侧计数 1/1000 (A=1 B=0 C=0) [按站·UTC]` · `▸ 对账: 服务端(主控行) used=27 − 派发侧 1 = 26 ⇒ 其余出网路径(review 判官 / per-station 别名 / 手动 TUI)`。★ **不可判就不印 0**（读不到 ⇒ 如实说"**不可判**"）—— 旧件那套"跨日自动归零"正是把"**昨天没记账**"读成"**今天没用额度**"。
> **③** `ops/cluster.py`：重导出清单**删四件**、加 `EGRESS_STATION_FILE` / `_egress_station_today`（⚠ 门禁 `facade` 会因"消费者引用了不存在的门面名"**当场红** ⇒ 两边删/加**必须同步**）。
> **④** `.gitignore`：删 `ops/.egress_daily.json` 那条忽略规则（该件**按构造恒 0**、盘上也不存在），并把两处相邻注释的"同 `.egress_daily.json` 家族"改指 `.or-borrow.json` / `.egress_station.json`。
> ★ **先验红（8 条 · `tests/test_cluster_pure.py`）**：① 旧件四件"**真的不在了**"（防死件复活）· ② 可判态读数正确 · ③–⑦ **fail-closed 五态**（缺件 / 坏 JSON / 缺 `by_station` / 值非法 / **跨 UTC 日**）⇒ **实现前全红**（① 报"仍可达: [四个名字]"）。★ 判据用**注入式路径**（写系统 TEMP、**不落仓**）= 离线真跑。
> ★★ **真跑当场抓到一个「夹具假绿」（本批最有价值的一条）**：夹具②–⑦ 原本用 **python 的写形状**（`write_text(..., 'utf-8')` ⇒ **无 BOM**）冒充生产者，而**真写侧**是 PS5.1 的 `Set-Content -Path … -Encoding UTF8` ⇒ 落 **UTF-8 BOM**（实测首 3 字节 `EF BB BF`）⇒ 读者用 `utf-8` 时**真路径下"永远不可判"**，而夹具**全绿**。⇒ 已三件：**(a)** 补 `R1-⑧`（**带 BOM 的件必须可判** —— 补上后**当场红**）**(b)** 读者改 `utf-8-sig`（有/无 BOM 通吃）**(c)** 该教训写进读者 docstring（"**夹具的形状必须取自真生产者**"）。★ 与既有纪律同族（`O-21` 的"注入式夹具抓不到真站形态"）。
> ★ **门禁读数**：`_fm_golden_test.ps1` **625/0** · `rpc_check.py --quick` **39 绿 / 2 黄 / 0 红** · `py-tests` **52/52**。
> ⚠ **仍未做（本批射程外，如实）**：**`FREE_QUOTA_PAID` 现为"仅定义 + 重导出"**（模块内**已无消费者** —— 它是 **R4 的语义产物**：档位真值源已收到 `free_limit`）⇒ ★ **本批不顺手删**（不在 R1 射程），**登记为待裁**；另 `_free_quota(is_free_tier=None)` 的**入参已不参与判档**（保留只为签名兼容）。


**结论（2026-09-16；⚠ 已被上方 2026-09-21 更正部分推翻："**无服务器剩余 API**"不再成立）**：可以建，但只能"本地自建"计数（无服务器剩余 API）：
- 统一入口 `egress` 增强：读 `GET /api/v1/key` 的 **`is_free_tier`**（True→日限额 50 / False→1000），并显示**主控本地每日计数**（`.egress_daily.json`，UTC 日滚动归零）+ 达 80% 预警。
  - ★ **2026-10-20 就地更正（R4 裁【甲】· 已落）**：上面「读 `is_free_tier`（True→50 / False→1000）」是**代理判据** —— 官方 SDK 页逐字「`limit` … the ceiling depends on **total credits purchased** and is **independent of `is_free_tier`**」（见上文 L193 的 2026-10-20 收窄段）⇒ ★ **日限额的依据改【直读】** `free_model_daily_requests.limit`（落点 = `cluster_egress.py` 的 `_free_quota_effective`）；`_free_quota()` **退化为 fail-closed 兜底**（`free_limit` 缺 / `None` / 非数 / ≤0 ⇒ 取**保守档 50**，且 `cmd_egress` **如实报出**"取兜底档" —— **判不了 ≠ 通过**，也不许静默）。★ 历史上**同一事实本就有两处来源**（`cmd_egress` 的旁证行用推断 · 借用流程 L275/L325 **直读**）⇒ 本改动 = **把孤例收回权威字段**。
  - ★★ **2026-10-20 就地更正（R1 裁【丙】· 已落）**：上面那句「显示**主控本地每日计数**（`.egress_daily.json`，UTC 日滚动归零）」**已不再成立** —— 该件连同其四件代码符号 **已废弃删除**，本地计数面改**单件承载** = **派发侧** `ops/.egress_station.json`（按站、UTC 日界，写侧 = `agent-cli.ps1` 的 `Write-EgressStationPick`）；`cluster.py egress` 的那行现为**对账行**（`服务端 used − 该件 sum` ⇒ 其余出网路径）。详见下方「2026-10-20 · 批次③」块。
- 写入手 `_egress_bump()`：由真正发 OpenRouter 免费请求的调用方（`opencode -m openrouter/...` / review 免费源）在发请求前自增。
  - ★★ **2026-10-20 就地更正（R3 + R1 裁【丙】· 已落）**：该"**写入手**"**从未接线**（实测全仓**零调用点**：只有定义 + 重导出）⇒ 它是一面**设计过却从未生效的假防线**；★ 且 `R1 裁【丙】` 后 `_egress_bump()` **已被删除** ⇒ 本句**整句作废**（不再是"待接线的写入手"，而是"**已废弃的死符号**"）。★ 连带：旧件用 `datetime.date.today()`（**本地日**）而注释与本 ADR 写"UTC 日" ⇒ **两套日界口径**；★ **裁定：日界一律以 UTC 为准**（官方 SDK 页逐字"resets at **UTC midnight**"）—— 新的派发侧件**本就已是 UTC** ✓。
- **实证（2026-09-16）**：主控 + A/B/C 四端 `tier=paid`（`is_free_tier=false`）→ **本账户已曾充 ≥$10，免费档日限额 = 1000/天**；四端同账户（`label` 一致）印证跨 key 全局治理。
- **诚实披露边界**：本地计数覆盖"主控侧入口能感知"的请求（wrapper/egress/review），**人手动 TUI 直调不在此计数** → 与 429 的 `X-RateLimit-*` 头交叉校准为准。

**区别于 zen（OP-07 原对象）**：zen 免费档无额度 API，"~100/天"未文档化，只能"本地计数 + 429 事件驱动"，O-07 维持该语义。

**硬规则限速（2026-09-16，用户拍板「RPM20 限速 + 429 退避」）**

决策（渐进，非全硬）：**RPM 20 硬限速 + 429 指数退避**；日 1000 维持软预警（用量 >50% 再升硬门）。只在"经过 wrapper 的出口"限速，opencode 内部 HTTP（`-m openrouter/...`）拦不到、仅靠 429 退避兜底。诚实边界见上节。

落地（`agent-cli.ps1` `Invoke-JudgeHttp`，即 review 源① commercial 唯一出口）：

| 机制 | 实现 | 验证 |
|---|---|---|
| **RPM20 令牌桶** | 最小 3s 间隔（`$Script:JudgeHttpLast` 进程内记上次），不足则 `Start-Sleep` 补足 | 假 OpenRouter（429→429→200）本地端到端：相邻请求被拉到 ≈3s（`+0.0→+2.9s`） |
| **429 指数退避** | `Invoke-WebRequest` 捕获状态码，`429 && attempt<3 → Sleep 2^(attempt-1)（1s/2s）重试`；第三次仍 429 才 throw | 同实验：429 后 `+2.9→+4.0s`（≈1s 退避）→ 200 `JUDGE_OK` |

- 原先 `Invoke-RestMethod` → `Invoke-WebRequest -UseBasicParsing`（PS5.1 才能拿状态码）。
- ⚠ **BOM 坑再度踩中**：Edit 修改 `agent-cli.ps1` 剥掉 UTF-8 BOM → PS5.1 按 CP936 读中文注释级连误报 38 个语法错（全假阳性）；补回 `EF BB BF` 后 14 个 .ps1 全绿。**凡编辑此 .ps1 必查 BOM。**
- 测试桩局限：BaseHTTPRequestHandler 首连传输层不完整（一条 `NETFAIL`）且只 serve 3 次（`timeout`）——均测试桩问题，真实 OpenRouter 429 是标准 HTTP 响应、走正确退避路径。

详见 [2026-09-14_暴露问题调研.md](../docs/research/2026-09-14_暴露问题调研.md)（含方法论教训：P1/P2 初稿结论均因**未先检索既有记档**而出错）。

---

## 凭据单一真值修正（2026-09-16）

**触发**：全量门禁 `stations` 黄灯明细为 **B、C 两站** `claude.key` 与同站 `unsloth.key` 不一致（该告警此前被我误读为"C 站独有" —— 旧告警文案把 C 站情形**硬编码**进了消息体，B 站的同类告警看起来一模一样；文案缺陷已一并修掉）。

**根因（与 D1 的"单一真值"原则冲突的具体形态）**：`claude.key` 是**引擎 key 的第二份拷贝**，而它**没有任何写入方** ——

| 文件 | 写入方 | 性质 |
|---|---|---|
| `~/.config/rpc/unsloth.key` | `infer-load`（每次 studio 加载**重铸**） | 站内产物，单一真值 |
| `~/.config/rpc/claude.key` | **无** | 拷贝；只能靠人工同步，必然陈旧 |
| `~/.config/rpc/claude-key.sh` | 主控正本 + `secrets push` | 取 key 脚本（原为 `cat claude.key`） |

实测两种陈旧形态都出现了：C 站是 09-14 密钥脱敏遗留的占位串（`sk-local-****` / `sk-unsloth-****`），B 站是"加载后 `unsloth.key` 变新、`claude.key` 仍旧"。**结论：这不是"C 站占位串是否有意"的问题（09-14 记为待确认项），而是结构缺陷 —— 任何一次 `infer-load` 都会使该站在下轮变黄。**

**决策**

| # | 决定 | 理由 |
|---|---|---|
| 1 | `claude-key.sh` 改为 `cat "$HOME/.config/rpc/unsloth.key"`，**`claude.key` 全量退役**（三站 + 正本） | claude 与 opencode 共用同一份引擎 key，消除第二定义点（与本仓既有纪律"抄一份就是第二个定义点"一致） |
| 2 | 门禁判据升级：`claude.key` vs `unsloth.key` **两文件互比** → **「apiKeyHelper 的实际输出 == 同站 `unsloth.key`」** | ① 旧判据测的是"两个文件"，新判据测的是"claude 真正拿到的 key"（功能判据）；② helper 不可用时输出 `SKIP`（由既有 `helper=` 行报出），不重复告警；③ 判据**不因构造而恒真** —— 仍能抓到"绕过 `infer-load` 手动改 key" |
| 3 | **不改 D1**（正本兜底保留），但补一条必需步骤：**`secrets push` 前必须先把站上真 key 回写正本** | `unsloth.key` 每次加载重铸 ⇒ 正本必然陈旧 ⇒ 直接 push 会**用旧 key 覆盖站上真 key**、打断该站 opencode/claude（本次执行时发现的真陷阱） |
| 4 | 否决备选"让 `infer-load` 同时写两个文件" | 留双份拷贝；且判据随即变成构造上恒真（失去绊线作用） |

**验收**：三站 helper 输出长度 == 各站 `unsloth.key`（A 43 / B 44 / C 44）；三站 `claude.key` 已不存在；正本 vs 站上逐一 MATCH；**门禁 `stations` 凭据告警清零**（仅余 `inventory/plugins.yaml` 已登记的 A 站插件 `known_drift`）；三站 `infer-unload` OK。

**studio 日志的明文面（②，同日闭环）**：`~/.unsloth/run-<alias>.log` 是**引擎 key 的第三个明文落点**，且此前**完全不在审计视野内**（`secrets scan` 只探 `~/.config/rpc` 与两份配置及备份）。实测：studio **每次加载写 key 4 处**、权限 **775 目录 / 664 日志**（组与其他用户可读）、三站累积 **21 份 / 68 处明文 / 16 个历史 key 值**（含 `.pre-repro-*` 副本）。**关键判断**：该日志含 key 是**设计使然**（`infer-load` 正是从它 grep 取 key）⇒ 消除不掉，**故判据只能落在权限上**（目录 700 / 日志 600），而非"含不含 key"。处置：`infer-load` 输出改掩码 + 每次加载强制 chmod + 存量 21 份就地脱敏 + `stations` 门禁补 `unslothlog` 探针（判权限，含负向自证）+ 补登明文面表。详见 [DEVELOPMENT-LOG 2026-09-16 ⑩](../spec/d6-agent-standard/DEVELOPMENT-LOG.md)。

**下发方向保护 + `secrets pull`（2026-09-16，同日闭环）**：⑨ 暴露的"正本陈旧覆盖站上真 key"陷阱，**未**采用"加一条常态黄灯"（那只会制造噪声、最后被整体忽略），而是**在危险动作上设闸 + 把正路做成一等入口动作**：

| 机制 | 设计 |
|---|---|
| 新增 `secrets pull [A\|B\|C]` | 把"站内产物"型凭据（`STATION_MINTED`，当前 = `unsloth.key`）**从站上收回**主控正本（SFTP 原始字节）—— 取代原先的手工 `scp`；**push 前先 pull 才是幂等的** |
| `push` 默认拒绝覆盖 | 站上已有且与正本不同 ⇒ **跳过**该文件并打印两条出路（`secrets pull <站>` / `secrets push --force`）；`--force` 保留强制能力 |
| `status` 增"站内产物"行 | `SECRETS_PROBE` 增 `[kv]` 段，只打**归一化指纹**（去换行后 sha256 前 12 位，**不打值**），显示"站上 vs 正本 一致/不一致 + 下一步" |

**验收**：负向（正本换成假值 ⇒ `push` 跳过该文件、**站上指纹未变**）／`--force` 生效（站上被覆盖）／`pull` 回写 + 幂等复跑报"已一致"／终态三站 `一致 ✓`（临时备份已删）。**顺带修** `_flow_rotate_status` 既有缺陷（把探针**原始文本**喂给期望 dict 的 `_secrets_verdict` ⇒ `TypeError`，且 `v != "OK"` 比 tuple ⇒ 该步恒判"需关注"）。

**落地件**：`ops/rpc_check.py`（`[cred]` 探针 + `stations` 判据 + 告警文案 + `secrets` 处置建议补掩码写法）、`ops/station-bin/infer-load`（输出掩码 + 每次加载强制 `chmod 700 ~/.unsloth` / `600 run-*.log`；三站已 `sudo install -m 755` 部署，sha `8155968d…`）、`ops/cluster.py`（`STATION_MINTED` / `secrets pull` / push 保护 / `status` 站内产物行）、`secrets/stations/{A,B,C}/claude-key.sh`（46B / LF）、`secrets/stations/{A,B,C}/claude.key`（删除）、[DEVELOPMENT-LOG 2026-09-16 ⑨⑩⑪](../spec/d6-agent-standard/DEVELOPMENT-LOG.md)、[密钥轮换清单现状注记](../docs/security/2026-09-13_密钥轮换清单.md)。
