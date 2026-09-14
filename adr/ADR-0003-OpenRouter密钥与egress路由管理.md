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
- **站内 egress（D3③）的权衡（待 Phase 2 决策）**：三站 opencode 需持有 key 才能直连 OpenRouter，这与「key 只在主控 `secrets/`」存在张力。选项：(a) 受控分发（同一 key 复制至三站 opencode.jsonc，登记在密钥清单）；(b) 不做站内 egress，egress 仅限主控编排层。**当前不擅自分发，留待显式决策。**

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
1. 用户填入真实 key（`secrets/openrouter.key`）+ 选定默认模型（`secrets/openrouter.conf`）
2. 实测 `agent-cli review --model commercial` 端到端（回填 O-16 source ① 关闭证据）
3. Phase 2 决策：站内 egress 是否分发 key 至三站（D5）
4. 密钥清单登记：`docs/security/2026-09-13_密钥轮换清单.md` 追加 OpenRouter 条目（轮换/吊销流程）
5. 成本监控：OpenRouter 为付费 credits，建议纳入 `cluster.py` 或独立探针（`GET /api/v1/key` 查余额）

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
2. **`:free` 档受 agentic-harness 门禁**：裸 API 调 `thinkingmachines/inkling:free` → 403「only available on agentic harnesses」。故 **D3 用途三线的「裸 API judge」路线对 `:free` 模型不成立**——`:free` 只能经 harness（claude code/opencode 等）。改用付费档或非门禁模型方可走 `Invoke-JudgeHttp`。
3. **主控站 IPv6 到 openrouter.ai 黑洞**：`.NET Invoke-RestMethod`（`Invoke-JudgeHttp` 所用）优先 IPv6 → 超时；curl -4 / claude code 走 IPv4 → 200。**D3① 路线存在 IPv6 阻塞，须先修**（改走 `curl.exe -4` / hosts 强制 IPv4 / B 站中转）。

**新增实证（支持 D3③ harness 路线）**：claude code（v2.1.207）+ `ANTHROPIC_BASE_URL=https://openrouter.ai/api` + `ANTHROPIC_AUTH_TOKEN` + `ANTHROPIC_API_KEY=`（置空），`claude -p ... --model thinkingmachines/inkling:free` → **实测返回 OK**，门禁解除。故 **harness 类接入（claude code / opencode / hermes）是 `:free` 模型的正确落点**，本 ADR 的 egress 定位由「judge 裸 API」扩展为「**judge（非门禁模型）+ harness（门禁免费模型）双轨**」。
