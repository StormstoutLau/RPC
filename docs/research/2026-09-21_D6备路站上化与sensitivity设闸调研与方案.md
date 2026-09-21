# D6 备路站上化 + sensitivity 设闸 —— 调研与方案（2026-09-21）

> **状态：调研 + 方案 + P0 已实施 + P1 核对面完成（2026-09-21 当日）。** 本报告的起点是一条**已生效的策略洞**（§0.1）。**P0 止血已落地并双向自证**；**P1 的核对面已完成**（四开关实况入档 + 免费/付费档策略矩阵），并**顺带产生一次"加入又同日撤回"**（§4.1）。**P2–P5 未实施**。
>
> **落地摘要（详见 §4）**
> - **P0**（§4.1）：判据收敛为唯一纯函数（`local-only` × 后端出网性），**两个出网入口各判** —— `AUTO_FALLBACK` 调用点（**拒绝兜底**）+ `Invoke-Task-Claude`。
> - **P1 核对**（§4.1 + [报告全文](../security/2026-09-21_OpenRouter数据策略与隐私开关核对.md)）：隐私开关**不可机读**（`/api/v1/key` 不含、`is_management_key=false`、`/settings`·`/privacy` 实测 404）；四开关实况 = 1% 折扣**关** / 免费档 publish **关** / 付费档 train **关** / **免费档 train 开**；实测**免费档端点全部训练且全不可 ZDR**，付费档有合规端点。
> - **⚠ 一次"加入又当日撤回"**：曾加 `sanitized × 可能训练 ⇒ 拒绝` 硬闸，**当日撤回**（①与档位定义冲突 ②不对称⇒虚假安心 ③半吊子闸比没有闸更危险）⇒ **决定：不加该闸**。**且"关开关"不是一个动作**（关免费档开关 ≡ 放弃免费档，且会同时打断备路/judge/站上 opencode 三条链路）—— 风险登记为**已知风险、默认接受**，P3 只提供**可选的**合规后端（§5）。
> - 自证总账：夹具 **61/61**；实弹探针 **双向**（A/B `local-only` 必须被拒 + C/D `sanitized` 必须被放行）全绿；变异自证证明 A/B 与 C/D 互不遮蔽；`public` 原路径未被破坏。全量门禁 PASS。
> - **过程事故（已闭环）**：编辑工具剥掉三个 `.ps1` 的 BOM 而 `syntax` 门禁报 PASS ⇒ 已补 BOM 并把新证据补进 OPEN-ISSUES（§4.1 末）。
> - **报告全文**：[OpenRouter 数据策略与隐私开关核对](../security/2026-09-21_OpenRouter数据策略与隐私开关核对.md)。
>
> **结论先行**
> 1. **⚠ 发现一个已生效的策略洞（最高优先）**：`sensitivity: local-only` 的硬闸**只拦 `opencode/*` 型号**（3 处），而 **`Invoke-Task-Claude` 走云端 OpenRouter 却没有这道闸** ⇒ 今天它从"不可用（Not logged in）"变为"**真能用**"之后，**`local-only` 卡的 prompt 可以实际出网**。这破了 [DESIGN.md](../../spec/d6-agent-standard/DESIGN.md) §358 的不变式（"local-only 的 prompt 字节永不离开主控站→站内本地模型路径"）。
> 2. **影响面大**：`spec/d6-agent-standard/test-cards/` 里 **20/25 张卡是 `local-only`**（`dogfood-*`、`echo`、`o13-sympy`、`smoke-*`、`fallback-deadlock` 等）⇒ 不是边角情形。
> 3. **推荐架构（一举解决待做 2 与 3）**：**把 claude 备路整体搬到"站上执行"** —— ① 绕开主控 Trae 沙箱（工具调用被拦，[2026-09-14 §8.5](2026-09-14_OpenRouter接入与agentic-harness门禁调研.md) 已实证）；② **`local-only` 天然不出网**（站上 claude 现指 `http://127.0.0.1:8080` 本地引擎，实测 `apiKeyHelper` 只读站上 `unsloth.key`）。**一个改动同时闭合两条。**
> 4. **不推荐**"站内多 key 代理"（待做 1）：会把每站明文面 **1→3 把**，与 [ADR-0003 D5](../../adr/ADR-0003-OpenRouter密钥与egress路由管理.md) 的「明文面收敛」直接冲突；且项目**已退役 LiteLLM**，再加常驻网关与既有取向相悖。收益（RPM 级无缝切换）在当前"按站独立账户 + 已有借用机制"下很有限。
> 5. **补充防线（P1 核对面已完成）**：隐私开关**不可机读**（所以只能人工读表）；四开关实况 = 1% 折扣**关** / 免费档 publish **关** / 付费档 train **关** / **免费档 train 开**。曾据此加 `sanitized` 硬闸，**当日撤回**（§4.1）。⇒ **结论：不加该闸；"关开关"也不是一个动作** —— 该开关是使用免费档的**必要条件**（实测账户级 `(Free model training)` 拦截）⇒ 关它 ≡ 放弃免费档，且会**同时打断三条链路**（§5）。风险登为**已知风险、默认接受**。

---

## 1. 集群现状（实测，2026-09-21）

### 1.1 `local-only` 闸的现状：**三处有、一处缺**
| 位置 | 判据 | 状态 |
|---|---|---|
| `agent-cli.ps1` L435-436（`Resolve-Model`） | `local-only` + `^opencode/` ⇒ `REJECT … exit 4`（无覆写通道） | ✅ |
| L968（`Invoke-Task` 主路） | 同上 | ✅ |
| L1805（路由 cmd） | 同上 | ✅ |
| **L1996-1999（`Invoke-Task-Claude`）** | 只校验"型号在表内 + `station=''`" ⇒ **无 local-only 判据** | ❌ **缺口** |
| **L1744-1756（`AUTO_FALLBACK` 调用点）** | 只判 `-AutoFallback` + `effectiveCli='opencode'` + `rc=6` ⇒ **不判 sensitivity** | ❌ **缺口** |

⇒ 两条实际出网路径：
- **直接**：卡写 `sensitivity: local-only` + `cli: claude` + claude 别名 ⇒ L968 放行（型号非 `opencode/*`）⇒ `Invoke-Task-Claude` ⇒ **OpenRouter**
- **经 fallback**：`local-only` 卡 + 站上本地型号（如 `gpt-oss-20b`）⇒ 正常走站上本地引擎 ⇒ 死锁 `rc=6` ⇒ `AUTO_FALLBACK` ⇒ `Invoke-Task-Claude -model claude` ⇒ **OpenRouter**

### 1.2 两种 claude 的落点（**关键差异**）
| | 主控 claude（今天改的） | 站上 claude（A 站实测） |
|---|---|---|
| `ANTHROPIC_BASE_URL` | `https://openrouter.ai/api` | **`http://127.0.0.1:8080`** |
| `apiKeyHelper` | `~/.claude/or-key.cmd` → 主控 `secrets/openrouter.key` | **`~/.config/rpc/claude-key.sh` → 站上 `unsloth.key`** |
| 出网 | **是（云端）** | **否（本机引擎）** |

⇒ **站上 claude 与站上 opencode 的"本地引擎"前提一致**：都是本机 `:8080`。这使"站上跑 claude"成为 `local-only` 的**天然合规后端**。

### 1.3 项目已有的实证（不是推测）
- **站上跑 claude 的完整工具任务可通**：2026-09-14 试点在 **B 站**跑了真实任务（FizzBuzz）成功
- **主控本地跑 claude 的工具调用被 Trae 沙箱拦**：`~/.claude/sessions/*` 等路径被阻，简单 `-p` 可过、带工具调用即挂（[2026-09-14 §8.5](2026-09-14_OpenRouter接入与agentic-harness门禁调研.md)）
- ⇒ 现状的 `Invoke-Task-Claude`（**控制台本地 spawn**）与"真正能用的路径"**不一致** —— 这是待做 2 的根因

---

## 2. 社区调研

### 2.1 远端/站上跑 claude（对应待做 2）
- **Anthropic 官方已把 SSH 主机当一等概念**：[Claude Code Desktop](https://code.claude.com/docs/en/desktop) 直接有 `SSH Host / Port / Identity File` 配置项；[Claude Science「Remote compute clusters」](https://claude.com/docs/claude-science/remote-compute-clusters) 用**你现有的 `~/.ssh/config`**、**不在主机上安装东西**、任务以 **detached 进程**跑、结束时回收产物。
- **社区主流形态 = `tmux + ssh`**：会话在服务端存活、断线不掉（[gist](https://gist.github.com/alxpck/d1e86d9a62e3fc5cf6c1ce52d0a02b10)）；native installer `curl -fsSL https://claude.ai/install.sh | bash`；**headless 登录用 paste-code 流程**（浏览器在本机打开登录 URL、把 code 贴回远端）——[aq.dev 指南](https://aq.dev/guides/run-claude-code-on-a-cloud-vm/)。
- **⇒ 对本项目**：站上跑 claude **不是变通，是官方支持的形态**；且本项目三站是 Ubuntu + 大内存（AMD 395 / 128G），正好是理想宿主。我们**已经有** ssh 通道与脚本化派发（`Invoke-RemoteScript`，R14 铁律 = 远端命令一律脚本落盘）。

### 2.2 多 key 轮换 / 网关（对应待做 1）
- 主流做法（[LLM Gateway failover](https://llmgateway.io/blog/how-we-handle-llm-provider-failover)：多 key 写在同一条环境变量 `KEY=sk1,sk2,sk3`，**逐 key 健康跟踪**，401/403 标记跳过、5xx 暂时跳过；熔断状态机 `CLOSED→OPEN→HALF_OPEN→DEAD`；退避重试；**状态持久化到磁盘以免重启后重试已限流的 key**）。
- 同类：[ApiKeyManager](http://raw.githubusercontent.com/SplashCodeDex/ApiKeyManager/HEAD/WhyThisProject.md)（Fastify 网关，客户端不接触 key；按 `x-app-id` 限流；审计环缓冲）；自托管 [LLM Gateway](https://llmgateway.io/products/ai-gateway)（AGPLv3，**按 key 的周期限额 / 提供商 RPM 上限 / 区域路由**）。
- **⇒ 对本项目**：模式成熟，但**不改变结论**（§0.4）：我们缺的从来不是"多 key 池"，而是"到顶后能换 key"——**这已由 `egress borrow` 提供**；剩下的 RPM 级切换属**分钟级自愈**，退避即可（`Invoke-JudgeHttp` 已有令牌桶 + 指数退避）。引入常驻网关的代价（新服务 + 明文面）**大于**收益。

### 2.3 数据留存策略（**对 `local-only` 决策决定性**）
- OpenRouter **默认不记录** prompt/completion："We do zero logging of your prompts/completions, even if an error occurs, unless you opt-in"；但它提供**"以日志换 1% 折扣"的 opt-in** ⇒ **必须确认未开**（[FAQ](https://openrouter.ai/docs/faq)）。
- **ZDR（Zero Data Retention）** 可在**账户级 / guardrail 级 / 请求级**（`provider.zdr`）强制，还能按模型组分别开（Anthropic / OpenAI / Google / 其它）——[ZDR 文档](https://openrouter.ai/docs/guides/features/zdr)。
- **但官方明确划界**：**ZDR 只保证"provider 不留存"，不改变"数据仍会到达 provider 并被模型处理"**，也**不覆盖"处理是否留在某国家/地区"**（那是 data residency / in-region routing 的事）。
- **⇒ 本方案的决定性依据**：**不能拿 ZDR 兜 `local-only`**。ZDR 是"不留存"，不是"不出网"。`local-only` 的要求是**不出网** ⇒ 必须走"站上本地引擎"这条物理路径。

---

## 3. 方案

### 3.1 推荐：claude 备路**站上化** + sensitivity 分流

**架构**
```
卡 sensitivity × claude 备路:
  local-only  ──▶ 站上跑 claude, 且必须用站上本地引擎(ANTHROPIC_BASE_URL=127.0.0.1:8080)
                  ⇒ 物理不出网。若所有站本地引擎都不健康 ⇒ **失败关闭(fail-closed)**, 明确报错, 绝不静默出网
  sanitized   ──▶ 站上跑 claude; 允许出网(OpenRouter, 按站独立 key); prompt 先过 scrubber(既有 P1a)
  public      ──▶ 站上跑 claude + OpenRouter(默认, 能力强); 或站上本地引擎(不出网但能力弱)
```

**关键设计点（逐条对应现状缺口）**
1. **选站**：优先选**与死锁站不同**的一站（死锁站的引擎可能已被 wedge）；**全站不健康 ⇒ fail-closed**，不退回控制台本地（Sandbox 拦）+ 不出网
2. **硬闸双点**：与既有三处同族，`local-only` + 任何"会出网的后端" ⇒ `REJECT … exit 4`，**无覆写通道**（owner-policy）。**必须在两处判**：
   - `Invoke-Task-Claude` 内（守直接入口）
   - **`AUTO_FALLBACK` 调用点**（守 fallback 入口）——**只判一处会漏**
3. **判据从"型号前缀"升级为"后端出网性"**：现有判据是 `id -match '^opencode/'`（把"出网"等同于"opencode/*"）。引入 claude 备路后，"出网"多了"OpenRouter"这一维 ⇒ 判据应改为**按后端的 `egress` 属性**（本地引擎 = 不出网；OpenRouter = 出网）**而非型号字面**。这是本次最值得改的结构点（避免"下次再加一个云端后端又漏一次"）
4. **证据面**：站上跑 ⇒ 归档件落点变成站上路径（沿用既有 `Invoke-Task-Claude` 的 v2 证据面改造：`evidence_manifest` + `attach[]` 带 sha256）；`usage` 仍明标"不采集"而非猜数
5. **预算**：今天已登记的"备路与主路共享卡的 `timeout_s`"是**独立缺陷**，站上化后仍存在 ⇒ 建议同时引入 `fallback-timeout-s`（卡可选，缺省取 `timeout_s`）
6. **登录/凭据**：站上 claude 用站上 `unsloth.key`（本地引擎）**无需 Anthropic 登录**；若要 `public` 走 OpenRouter，站上需有 OpenRouter key（**每站已有独立账户**，正好复用）

**改动清单（不实施，仅列点）**
- `Invoke-Task-Claude`：改为"站上执行"（ssh + 脚本落盘，遵 R14）；其后端按 `sensitivity` 选择本地引擎/OpenRouter
- `AUTO_FALLBACK` 调用点：加 `local-only` 前置判 + 选站逻辑（排除死锁站）
- 判据改造：`local-only` 闸从"型号前缀"改为"后端 `egress` 属性"（三处旧点 + 两处新点统一到一个函数）
- 卡 front-matter（可选）：`fallback-timeout-s`
- `capabilities`/文档：更新 [DESIGN.md](../../spec/d6-agent-standard/DESIGN.md) §358 不变式的表述（明确"claude 备路 = 站上本地引擎"）

### 3.2 不采用：站内多 key 代理（待做 1 的结论）
| 维度 | 评估 |
|---|---|
| 收益 | RPM 级无缝切换（**分钟级自愈**，退避即可）；日额度已由"每站独立账户 + `egress borrow`"覆盖 |
| 代价 | 每站明文面 **1→3 把**（撞 ADR-0003 D5）；引入常驻服务（与"已退役 LiteLLM"取向相悖）；多一处凭据回收面 |
| 结论 | **不做**。若将来出现"日额度频繁耗尽且借用不够"的实测证据，再立项 |

### 3.3 低成本补充防线（建议一并做）
1. **核对 OpenRouter 隐私设置**：确认未开"以日志换 1% 折扣"的 opt-in（默认是关的，但值得显式核一次并登记）
2. **`public`/`sanitized` 开 ZDR**（账户级或按 guardrail）：对"不出网但不想被留存"的流量加一层；**注意它不能替代 `local-only`**
3. **把"每站独立账户"用于分流**：`public` 默认走**站上本地引擎**（不出网、零成本），仅当本地不健康或需要更强模型时才走 OpenRouter ⇒ 同时省额度与缩暴露面

---

## 4. 建议实施顺序与验收判据

| 序 | 项 | 类型 | 说明 |
|---|---|---|---|
| **P0** | **止血**：在 `Invoke-Task-Claude` + `AUTO_FALLBACK` 调用点各加 `local-only` 拒绝（双点，~数行） | 代码 | ✅ **2026-09-21 已实施**（判据收敛为唯一纯函数，见 §4.1） |
| P1 | 核对 OpenRouter 隐私设置（opt-in 日志必须关）+ 登记 | 运维 | ✅ **核对面已完成**：开关**不可机读**（故只能人工读表）；四开关实况入档；免费/付费档策略矩阵实测。**结论**：① 已关；**免费档 train 开** ⇒ 加 `sanitized` 闸后**同日撤回**，改登记为已知风险。[全文](../security/2026-09-21_OpenRouter数据策略与隐私开关核对.md) |
| P2 | 判据统一：`local-only` 闸改为"后端 `egress` 属性" | 代码 | 结构性，防"再加云端后端又漏" |
| P3 | claude 备路**站上化**（ssh + 脚本落盘；后端按 sensitivity 分流；选站排除死锁站；fail-closed） | 代码 | 本方案主体 |
| P4 | 备路独立预算 `fallback-timeout-s` | 代码 | 独立缺陷，可与 P3 同批 |
| P5 | `public`/`sanitized` 开 ZDR（账户级/guardrail） | 运维 | 补充防线 |

**验收判据（必须双向自证）**
- **正**：`public` 卡经站上 claude + OpenRouter 跑通 ⇒ 归档件齐全、`evidence_manifest` 到 v2、`usage` 明标不采集
- **负（关键）**：构造 `local-only` 卡（a）直接 `-cli claude`（b）站上引擎死锁触发 `AUTO_FALLBACK` ⇒ **两条都必须被拒/或走站上本地引擎**，且要有**出网侧证据**（后端选择日志 / 无到 OpenRouter 的连接）
- **fail-closed**：全部站本地引擎不健康 + `local-only` ⇒ **报错而非出网**
- **还原**：改回后原路径复跑 PASS
- 全程过阶段 0.5 夹具 + 全量门禁

### 4.1 P0 落地与自证（2026-09-21 已实施）

**改动**（`ops/station-bin/agent-cli.ps1`）

| 位置 | 内容 |
|---|---|
| L905 `Get-SensitivityBackendReject` | **唯一判据**（纯函数，返回 '' = 放行 / 否则**原因 token**）：`local-only × 会出网 ⇒ 'local-only+egress'`；`sanitized`/`public` 恒放行。做成纯函数（不碰站、不碰文件系统）⇒ 夹具可按名提取离线单测（与 `Test-FallbackEligible` 同族） |
| `AUTO_FALLBACK` 调用点 | **拒绝兜底**（fail-closed，不是"兜底到别处"）⇒ `rc=4`；拒绝串带 tag `(fallback, <model>)` |
| `Invoke-Task-Claude` | 直接入口 ⇒ `rc=4`；拒绝串带 tag `(claude-direct, <id>)` |

**为何必须双点**：两条路径是**两个独立入口**（一个守"卡直接指定 claude"，一个守"主路死锁后自动转发"）—— 只判一处会漏，这正是本洞的成因。
**为何判据是"后端属性"而非"型号前缀"**：同一型号在不同通道下属性不同 —— `gpt-oss-20b` 走站上本地引擎（不出网），而 `claude` 走主控本地 spawn = 云端 OpenRouter（**出网**）。旧判据把"出网"等同于 `^opencode/` ⇒ 整个 claude 备路失守。`$backendEgress` 现硬编码 `$true`（`Invoke-Task-Claude` = 主控本地 spawn，`ANTHROPIC_BASE_URL` = `https://openrouter.ai/api`）；P2 会换成"按后端属性查表"。
**`AUTO_FALLBACK` 处为何返回 4 而不是原 `rc=6`**：刻意让"策略拒绝"盖过"超时" —— 否则调用方只看到 timeout 会**换站重试**（每次重试都再跑一遍本地引擎），策略事件被埋掉。原 rc 已在上一行 `TASK_DONE … exit=$code` 打印，未丢失。

**⚠ 同日**加入又撤回**的一条规则（必须留档）**：曾把判据扩展为 `sanitized × 可能训练 ⇒ sanitized+trains`，当日**撤回** —— 撤回理由（①与档位定义冲突 ②不对称⇒虚假安心 ③"免费档可能训练"是使用免费额度的固有代价）见 [P1 核对报告 §6.2](../security/2026-09-21_OpenRouter数据策略与隐私开关核对.md) 与 `Get-SensitivityBackendReject` 的函数注释。**撤回被做成可判的**：探针 C/D 例翻成"sanitized 必须**被放行**且真产出 claude run"，反向守卫不许加回。

**双向自证结果**

| # | 项 | 结果 |
|---|---|---|
| 1 | 阶段 0.5 夹具 `_fm_golden_test.ps1` | **61/61 PASS**（真值表 5 条 + 覆盖 2 条 + 备路档位前提 1 条） |
| 2 | 实弹探针正向（`public` 卡） | 兜底触发、证据面 v2、`accept` 在 Git Bash 下 `ACCEPT_RC[1]=0` ⇒ **原路径未被破坏** |
| 3 | 负例 **A**：`local-only` + `-cli claude`（直接入口） | `REJECT local-only+egress (claude-direct, thinkingmachines/inkling:free)`，`rc=4`，claude run 计数**不增** |
| 4 | 负例 **B**：`local-only` + 站上本地型号 + `AutoFallback`（兜底入口） | `REFUSED` + `REJECT local-only+egress (fallback, claude)`，`rc=4`，**不增** |
| 5 | **反向守卫 C/D**：`sanitized` × 两条路径 | **必须被放行**且 claude run **增加**（真到免费档）⇒ 撤回可判 |
| 6 | **变异自证**（拆掉那条闸重跑） | 只 **C/D 变红**（rc 4→6 且**各真跑出一个 claude run** = 真出境）⇒ 风险真实、且与 A/B 判据互不遮蔽 |
| 7 | 全量门禁 `rpc.ps1 check` | 见提交信息（15 绿 / 1 黄[已登记漂移] / 0 红） |

⇒ 第 3–4 条 + 第 6 条合起来证明：该洞**不是理论上的**（拆掉闸就真发请求），且探针**不是结构性失明**（此前教训：stub 型探针曾对真实 bug 完全免疫）。

**⚠ 过程事故（已闭环，值得记住；含一次根因更正）**：本轮编辑（`SearchReplace`）**把三个 `.ps1` 的 UTF-8 BOM 剥掉了**，而 `syntax` 门禁在那个时点**没报出来** —— 随后夹具**当场解析崩溃**。已用 `tmp/_restore_bom.ps1` 补回并复检 `parseErrors=0`。**⚠ 该行为是"间歇"的**：同一工具、同一批文件，另两轮编辑（P1 阶段、补语法阶段）**都保留了** BOM ⇒ **既不能假设保留、也不能假设必剥，只能按字节验**。
**⚠ 我最初写的根因是错的，此处更正**：曾推断"门禁的 `[Parser]::ParseFile` 走 .NET 解码（BOM-less 按 UTF-8）而执行走 ANSI ⇒ **结构性看不见**"。实测推翻：把 BOM-less 的中文 `.ps1` 交给那次 `ParseFile`，它**报了错**且行号全落在中文注释行 ⇒ **它与执行走同一条解码路径（ANSI/GBK）**。真正的缺陷是**间歇性 + 内容相关 + 报错不指根因**（是否吞掉换行取决于具体字节；报出来的行号指向注释行，看不出"加 BOM"这个修法）。
⇒ **已加确定性字节子判据**（`syntax` 的 `counts[".ps1-bom"]`：含非 ASCII 却无 BOM ⇒ FAIL），并顺带修了 `(ps1)` 明细缺文件名、失败数按错误行计（曾误导为"11 个文件坏了"，实际 1 个）两处报告缺陷。**自证 正/负/对照**三例齐（见 [OPEN-ISSUES 该行](../../spec/d6-agent-standard/OPEN-ISSUES.md)）。**纪律**：编辑过 `.ps1` 后提交前按字节验 BOM。

## 5. 风险与诚实边界
- **P0 只"止血"不"治本"**：`$backendEgress` 是**硬编码 `$true`**，而判据的**根**（既有三处闸按型号前缀判"是否出网"）未动 ⇒ 下次再加一个云端后端**仍会漏一次**。治本是 P2。
- **P0 的语义代价**：`local-only` 卡主路死锁 ⇒ 直接 `rc=4` **不再兜底**（原本会静默出网）。**有意**的失败关闭（宁可失败，不可静默外泄），但调用方需知道 `rc=4` 里可能含着一次"本该有的兜底"。
- **已被接受的已知风险（P1 的结论，不是遗漏）**：备路两型号都是 `:free`，而**免费档可能被训练且训练不可撤回**。这是**使用免费额度的固有代价**；曾为此加过 `sanitized × 可能训练` 硬闸，**当日撤回**（理由见 §4.1 与 [P1 报告 §6.2](../security/2026-09-21_OpenRouter数据策略与隐私开关核对.md)）。**该风险"默认接受"** —— 现有三档表达的是"能否出网"，**"是否可被训练"这一维在三档里没有位置**；要拦就得**新增一档并定义语义**（独立设计题），不能给 `sanitized` 打补丁。P3 提供**可选的**合规后端（"若将来某类流量单独不接受训练暴露"时用）。
- **⚠ 明确排除的一个动作："关闭免费档开关"**（早先曾把它写成 P3 之后的收尾步骤 —— **属于把手段当目的，已更正并移除**）。理由：该开关是使用免费档的**必要条件**（实测账户级 `(Free model training)` 拦截）⇒ **关它 ≡ 放弃免费档**；而免费档**不是只有备路在用** —— ① claude 备路（harness 轨）、② judge/review 的 judge 槽（`secrets/openrouter.conf`，裸 API 轨）、③ 站上 opencode 的 `provider.openrouter.models` 免费档优先级表（站内 egress）。**关开关 = 同时打断这三条链路**，收益（少一条暴露面）远小于代价。⇒ 若某类流量**单独**不接受训练暴露，正确做法是**把那条流量改走合规后端**（站上本地引擎 / 付费+`deny`·ZDR），**不是**关开关。**P3 的价值与关开关无关**，按 ①②③ 记（见 §4）。
- 站上化后**主控不再本地跑 claude** ⇒ 主控侧 `~/.claude/settings.json` 的 OpenRouter 配置（今天所改）**降级为"仅 review/research-lookup 使用"**，须在文档里同步，否则又是一处"文档与实况不符"
- 站上跑 claude 会占用站上 CPU/内存（claude CLI 本身不重，但工具调用会跑构建/测试 ⇒ 与站上推理争资源）⇒ 需实测一次资源影响
- `local-only` 的"不出网"是**本项目的策略要求**，非社区通行标准（社区多把 ZDR 当作"足够"）；本方案按**更严**的标准走

## 6. 关联
- [OpenRouter 数据策略与隐私开关核对](../security/2026-09-21_OpenRouter数据策略与隐私开关核对.md)（**P1 全文**：三个开关 / 不可机读的证据 / 免费档 vs 付费档实测矩阵 / 关闭开关的影响 / `sanitized` 闸的决策）
- [DESIGN.md §358 路由不变式](../../spec/d6-agent-standard/DESIGN.md)（被 §0.1 的洞破坏）
- [ADR-0003 OpenRouter 密钥与 egress 路由管理](../../adr/ADR-0003-OpenRouter密钥与egress路由管理.md)（D5「明文面收敛」= §3.2 的否决依据）
- [2026-09-14 OpenRouter 接入与 agentic-harness 门禁调研](2026-09-14_OpenRouter接入与agentic-harness门禁调研.md)（§8.5 主控沙箱实测；站上跑 claude 的先行实证）
- [2026-09-21 claude 备路免登录与后端选型调研](2026-09-21_claude备路免登录与后端选型调研.md)（主控侧免登录与 403 地区墙）
- [2026-09-21 OpenRouter 多账户配额分配与调配设计](../security/2026-09-21_OpenRouter多账户配额分配与调配设计.md)（每站独立账户 + 借用机制 = §3.3③ 的基础）
