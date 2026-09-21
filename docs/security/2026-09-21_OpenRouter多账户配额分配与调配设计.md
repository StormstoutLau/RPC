# OpenRouter 多账户配额分配与调配 —— 方案设计（2026-09-21）

> **状态：设计稿，待批准后实施。** 本文只做设计，未改任何配置/代码。
>
> **结论先行**
> 1. **现状（实测）**：控制台 + A/B/C **四端共用 1 把 key**（同一账户）⇒ 1000/天是**四端共享**的。判据：逐端 `GET /api/v1/key` 的 **`creator_user_id` 四端相同**（`user_3BqB4sUNPR6fJOcVQQdE0CsKMUr`）。
> 2. **⚠ 一条重要的文档更正（实测推翻旧结论）**：`GET /api/v1/key` **现已返回 `free_model_daily_requests: {used, limit, remaining}`**（实测 `8/1000/992`）。⇒ [ADR-0003](../../adr/ADR-0003-OpenRouter密钥与egress路由管理.md) 与[密钥轮换清单](2026-09-13_密钥轮换清单.md) 里"**OpenRouter 无免费请求剩余数 API ⇒ 每日计数只能本地自建**"的说法**已过时**：计数可以**服务端权威**，本地计数器（`.egress_daily.json`）不再是唯一依据。
> 3. **分发管道已建好、零代码改动**：正本 `secrets/stations/<站>/openrouter.key` → `cluster.py secrets push` → 站上 `~/.config/rpc/openrouter.key`；站上 `opencode.jsonc` 用 **`{file:...}` 引用** ⇒ **每站换 key 不会破坏三站配置一致性判据**。
> 4. **分配（用户裁定）**：旧 key → **A**；两把新 key → **B / C**。控制台（第 4 个消费者）**待定**，见 §2 的分析。
> 5. **调配机制**：用户要求"单站额度到顶可借用另两站"。**推荐"控制台式指派"**（§4-A）—— 因为 `opencode` 的 key 是**启动时解析的静态引用**，运行时换成"推文件 + 重启站内 agent"；**不推荐**"站内多 key 代理"（会把每站明文面从 1 把扩到 3 把，与 ADR-0003 D5「明文面收敛」直接冲突）。

---

## 1. 现状实测（2026-09-21）

| 端 | key 正本 | `creator_user_id` | `free_model_daily_requests` | tier |
|---|---|---|---|---|
| console | `secrets/openrouter.key` | `user_3BqB4sUNPR6fJOcVQQdE0CsKMUr` | 8 / 1000 / 992 | paid |
| A | `secrets/stations/A/openrouter.key` | 同上（**同账户**） | 8 / 1000 / 992 | paid |
| B | `secrets/stations/B/openrouter.key` | 同上 | 8 / 1000 / 992 | paid |
| C | `secrets/stations/C/openrouter.key` | 同上 | 8 / 1000 / 992 | paid |

⇒ **distinct accounts = 1**。今天全集群只用了 **8 次**免费档请求。

### 1.1 既有的分发管道（可直接复用，无需改代码）
| 环节 | 事实 |
|---|---|
| 正本 | `secrets/stations/{A,B,C}/openrouter.key`（**文件已存在**，现装同一把；`.gitignore` 覆盖 `secrets/`） |
| 下发 | `python ops\cluster.py secrets push` —— SFTP → 站上 `~/.config/rpc/openrouter.key`（**600**，目录 700） |
| 站上配置 | `~/.config/opencode/opencode.jsonc` 写 **`"apiKey": "{file:~/.config/rpc/openrouter.key}"`**（**引用，不含明文**） |
| **不撞门禁** | `rpc_check.py` 的 `stations` 判据只比 **`opencode.jsonc` / `~/.claude/settings.json` 的 sha256**，**不比 key 文件** ⇒ **每站不同 key 不会误报"三站不一致"** |
| 覆盖保护 | `STATION_MINTED = {"unsloth.key"}`（站内每次加载重铸）；**`openrouter.key` 不在其中** ⇒ push 正常覆盖，**无需 `--force`** |
| 既有流程 | [密钥轮换清单](2026-09-13_密钥轮换清单.md)：吊销 → 生成 → 覆盖 `secrets/stations/<st>/` → `secrets push` → **重启站内 agent** |

---

## 2. 主控站为什么需要 key？消费者是谁？（回答你的问题）

`secrets/openrouter.key`（主控正本）的实际消费点，**全部在本仓库内可查**：

| # | 消费方 | 注入路径 | 触发时机 | 量级判断 |
|---|---|---|---|---|
| ① | **D6 claude 备路**（`Invoke-Task-Claude`） | `~/.claude/settings.json` → `apiKeyHelper` → `~/.claude/or-key.cmd` → 读 `secrets/openrouter.key` | 仅在**主路 opencode rc=6（引擎死锁/超时）且 `AGENT_AUTO_FALLBACK=1`** 时（2026-09-21 落地） | **稀有**（只在死锁时） |
| ② | **review 的商业 judge** | `. _env_openrouter.ps1` → `REVIEW_COMMERCIAL_BASE/KEY/MODEL` → `agent-cli.ps1` 的 `JUDGE_TABLE['commercial']`（type=`http`）→ `Invoke-JudgeHttp` | 运行 `agent-cli review --model commercial` 时 | 按需（可能几十~几百次/轮评审） |
| ③ | **research-lookup skill**（parallel-cli） | `. _env_openrouter.ps1` → `OPENROUTER_API_KEY` / `OPENROUTER_BASE_URL` | 做文献检索时 | 按需 |
| ④ | **`cluster.py egress` 探针本身** | 直接读 `secrets/openrouter.key`（L1191） | **每次跑 `egress`** | 1 req/次（可忽略但**会计数**） |
| ⑤ | **hermes**（`~/.hermes`，**已登记分发点**） | `config.yaml` 的 `model.api_key` / env `OPENROUTER_API_KEY` | 按需 | 待确认是否仍指 OpenRouter（[F27](../research/2026-09-14_暴露问题调研.md)：hermes chat 只从 config 读 key） |

**结论**：主控的消费是 **①②③（+④ 探针）**，且**都是低频/按需**，与"站上 opencode 作为本地引擎全线停机时的 egress 兜底"（可能成批）量级不同。

⇒ **因此**：**主控与某一站共用一把 key 是可接受的**，前提是**能看见服务端计数**（§5 已经能）。若你要**严格隔离**，再加注册第 4 个账号给主控；不建议"主控不走出网"（那等于**关掉 D6 备路**，退回 2026-09-21 之前的状态）。

> ⚠ 待你确认：**主控先用哪把？**（建议：主控与 **A** 共用"旧账号"那把 —— 因为旧账号已 `paid` 且今天只用了 8 次；B/C 的**新账号**保持纯净给两站独享。）

---

## 3. 分配方案（3 把 key）

| 端 | 分配 | 说明 |
|---|---|---|
| **A** | **旧 key**（现存 `secrets/openrouter.key` 那套账户） | 已 `paid`（曾充 ≥$10 ⇒ 日限额 1000），无需重新注册 |
| **B** | **新 key #1** | 新账户 |
| **C** | **新 key #2** | 新账户 |
| **console** | **待定**（§2） | 建议与 A 共用 |

**分发步骤（批准后执行）**
1. 把 3 把 key 分别写入正本：`secrets/stations/A/openrouter.key`（旧）、`B/`、`C/`（新）—— **明文不经过对话**（由你写入或我建待填模板）
2. `python ops\cluster.py secrets push`
3. 重启三站 opencode（`{file:}` 引用在**启动时**解析）
4. **验收判据（可机判）**：逐端 `GET /api/v1/key` 的 **`creator_user_id` 必须互不相同（3 个）**；`secrets status` 三站指纹互不相同；门禁全量 PASS（尤其 `stations` 的 cfg sha 仍三站一致）

---

## 4. 额度调配机制（"单站到顶可借用另两站"）—— 设计

### 4.0 先分清两类限流（**关键**，决定"借"还是"等"）
| 类型 | 量级 | 复位 | 正确应对 |
|---|---|---|---|
| **日额度**（`free_model_daily_requests`） | 1000/天/账户 | **UTC 日滚动** | **借用**（换 key）—— 当天内不会自己恢复 |
| **RPM** | 20 请求/分 | **分钟级** | **等待/退避**（换 key 属过度动作；且 `X-RateLimit-*` 头是服务器真值） |
| 429（任一原因） | — | — | 先**退避重试**（现有 `Invoke-JudgeHttp` 已有 RPM20 令牌桶 + 指数退避），**日额度类**才升级为借用 |

### 4.1 方案 A（**推荐**）：控制台式"指派/借用"
**原理**：主控是唯一的编排者，也是唯一能看到四端服务端计数的地方。

1. **巡检**：`cluster.py egress`（增强后，§5）逐端读 `free_model_daily_requests.remaining`
2. **判据**：某端 `remaining <= 阈值`（如 5%）⇒ 触发"指派"
3. **动作**：
   - 选一个 `remaining` 最充裕的**同侪** key（借用方）
   - 把借用方的 key **写入被借端**的正本 `secrets/stations/<被借端>/openrouter.key`（**覆盖**）
   - `secrets push <被借端>`；重启该站 opencode
4. **记账**：在 `secrets/`（或 `inventory/`）留一张 **借用台账**（谁借谁、UTC 日、原因、是否已归还）⇒ 使"该站当前用的是谁的 key"**可回答**
5. **归还**：UTC 日切后（`remaining` 复位）自动/手工推回本 key + 重启
6. **明文面**：每个站**任一时刻仍只有 1 个 key 文件** ⇒ **不扩大**（符合 ADR-0003 D5）

**代价/风险（诚实标注）**
- 换 key 需**重启站内 opencode** ⇒ 会打断该站在途任务（故只在**到顶**时做，属低频事件：日级，至多几次）
- 竞态：重启期间该站不可用；且**借用期间两站共用同一把 key** ⇒ 被借方的额度被两站共同消耗 ⇒ 台账必须记录，避免"借用方自己也到顶"
- 检知依赖主控巡检（非实时）；无巡检时，站上只会看到 429

### 4.2 方案 B（**不推荐，除非显式决策**）：站内多 key 代理
站上跑一个本地代理持有 **3 把 key** 做运行时轮换：opencode 的 `baseURL` 指向 `127.0.0.1:<port>`，代理在 429/额度尽时**秒级**切 key，**无需重启**。
- **优点**：切换无中断、可处理 RPM 级
- **代价（决定性）**：**明文面从"每站 1 把"扩到"每站 3 把"** —— 与 [ADR-0003 D5](../../adr/ADR-0003-OpenRouter密钥与egress路由管理.md) 的「明文面收敛到每站 1 个 600 文件」**直接冲突**；且引入一个新的常驻服务（与项目"按需/零自加载"倾向不合）
- ⇒ 若采纳，需要**显式决策 + ADR 更新**，并处理"代理自身凭据落点/权限/回收"

### 4.3 方案 C（最小）：只告警不调配
到顶就**退化为本地引擎或报错**，主控只报警不动作。最简单、零风险，但**不满足"借用"需求**。

### 4.4 推荐结论
**采纳方案 A**，并明确边界：
- 触发 = **日额度类**到顶（非 RPM）；RPM 走**退避**
- 借用顺序 = `remaining` 最多者优先；**禁止二次借用**（被借端自身到顶时不连锁）
- 一次借用**跨到 UTC 日切为止**；归还 = 日切后巡检发现复位 ⇒ 推回本 key
- **台账留痕**（可回答"某站某日在用谁的 key"），并进 `secrets status` 展示

---

## 5. 分账户计数与预警 —— 设计（**改为服务端权威**）

### 5.1 数据源（实测）
`GET /api/v1/key`（Bearer = 该端 key）返回：
```json
{"data":{
  "creator_user_id":"user_…",              // 账户身份 ← 拆分验收判据
  "free_model_daily_requests":{"used":8,"limit":1000,"remaining":992},
  "usage_daily":0,"usage_weekly":0,"usage_monthly":0,   // 付费 credits 口径
  "is_free_tier":false,
  "rate_limit":{"requests":-1,"interval":"10s","note":"deprecated"}
}}
```
- `/api/v1/activity` → **403**（不可用，勿依赖）
- `/api/v1/credits` → `{total_credits, total_usage}`（账户级，非 key 级）

### 5.2 设计
1. **`cluster.py egress` 增强**（唯一入口，不新增命令）：
   - 每端输出：`owner=<creator_user_id 短哈希>` · `free <used>/<limit> (<remaining>, <pct>%)` · `tier` · `rpm`
   - **4 端并排**，一眼看出"是否已拆成 3 个账户"（`distinct owners`）
   - 80% 预警（沿用既有约定）、100% 标红/标"已到顶"
   - **口径分离**：`:free` 请求数（`free_model_daily_requests`）vs **付费 credits**（`usage_daily`/`credits.total_usage`）—— 两者不可混算
2. **本地计数器 `.egress_daily.json` 的去留**：**降级为旁证**（服务端是快照、本地是流；两者可交叉验证"是否有未记录的调用方"），**不再作为唯一依据**；`_egress_bump()` 保留但不再是权威
3. **站上用量无需自计数**：服务端**按 key**统计 ⇒ 站上 opencode 的用量天然可见（**省掉一整块站上埋点工作**）
4. **预警阈值与动作**：`>=80%` 黄、`>=95%` 红、`<=0` 触发 §4 借用流程
5. **一条限度（诚实标注）**：`free_model_daily_requests` 只覆盖 **`:free` 档模型**；若将来用付费模型，须另看 `usage_*`/credits —— 判据要**两个口径都给**

---

## 6. 待批准 / 待实施清单（按序）

| # | 项 | 类型 | 前置 |
|---|---|---|---|
| 1 | **更正 ADR-0003 + 密钥轮换清单**里"无免费请求剩余 API"的过时结论（改为服务端权威 + 本地旁证） | 文档 | 无（**建议最先做**，因当前文档与实测矛盾） |
| 2 | 确认**主控用哪把 key**（建议：与 A 共用旧账号） | 决策 | — |
| 3 | 3 把 key 写入正本（A=旧 / B,C=新） | 配置 | 你提供 key |
| 4 | `secrets push` + 重启三站 opencode + **验收 3 个不同 `creator_user_id`** | 运维 | #3 |
| 5 | `egress` 增强（服务端权威计数 + 4 端并排 + 预警口径分离） | 代码 | 无 |
| 6 | **借用/指派机制**（方案 A：巡检→指派→台账→归还） | 代码/运维 | #4 #5 |
| 7 | 更新 [密钥轮换清单](2026-09-13_密钥轮换清单.md) 的"存放"表（从 1 把 → 3 把 + 借用台账） | 文档 | #4 |

> **不在本设计范围**（留待另议）：站内多 key 代理（方案 B）、D6 备路改站上执行、按 `sensitivity` 设闸（`local-only` 不走 OpenRouter 出网）—— 后者与本设计**正交但同样重要**，见 [2026-09-21 claude 备路免登录与后端选型调研](../research/2026-09-21_claude备路免登录与后端选型调研.md) §6。

## 7. 关联

- [ADR-0003 OpenRouter 密钥与 egress 路由管理](../../adr/ADR-0003-OpenRouter密钥与egress路由管理.md)（D5「受控分发 + 引用化」；本文 §1.1 是对它的现状印证）
- [密钥轮换清单（2026-09-13）](2026-09-13_密钥轮换清单.md)（轮换流程与落点表）
- [2026-09-14 OpenRouter 接入与 agentic-harness 门禁调研](../research/2026-09-14_OpenRouter接入与agentic-harness门禁调研.md)（`:free` 门禁、`is_free_tier` 与日限额 1000 的由来）
- [2026-09-21 claude 备路免登录与后端选型调研](../research/2026-09-21_claude备路免登录与后端选型调研.md)（主控为何现在也需要 OpenRouter：① D6 备路）
