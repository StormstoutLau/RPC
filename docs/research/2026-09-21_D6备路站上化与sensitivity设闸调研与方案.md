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
  public      ──▶ 站上跑 claude + OpenRouter(默认, 能力强); 或站上本地引擎(不出网、零额度)
                  ⚠ **"本地=能力弱"是错的**(2026-09-21 用户更正 + 台账核对): 站上可跑
                  gpt-oss-**120b**(decode ~50tps) / nemotron-120B(~22) / **MiniMax-M2.7**(~21.5) /
                  qwen3.8-flash-next(~19) / deepseek-v4-flash ⇒ **能力不是分水岭**。
                  真正的差别是: ①**资源竞争**(与主路推理抢同一块统一内存/GPU)
                  ②**故障相关性**(同批引擎/驱动/KFD 栈) ③**冷启动**(未加载时备路要等加载)
                  ⇒ 故 `public` 的默认后端**先实测再定**(见 §3.4/§3.5)
                  ⚠ **测量 3 已执行并推翻一个前提**(§3.5): 信号类 `rc=6` 之后引擎**完全健康**
                  (首生成 1.07s、slot 干净) ⇒ 那类失败缺的是**预算**不是后端;
                  P3 的理由收敛为「绕开主控沙箱 / 给 local-only 合规兜底 / 故障域多样性」,
                  **不再包含"给信号类 rc=6 兜底"**
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
3. **把"每站独立账户"用于分流**：`public`/`sanitized` 的后端不该写死 —— **默认后端待定**，先按 §3.4 实测再定（⚠ 本节早先写死过"`public` 默认走站上本地引擎"，与 §3.1 冲突，已撤回该断言）

### 3.4 后端选型实测方案（"先实测再定"的操作化）

**要回答的不是"哪个快"，而是"备路场景下哪个后端可用"** —— 因为备路由 `rc=6`（引擎死锁/超时）触发，**那一刻站上往往正忙或正 wedge**，本地后端可能恰好不可用。

| # | 维 | 怎么测 | 判据（对照） |
|---|---|---|---|
| **0** | **台账取证（0 成本，先做）** | 从 [`inventory/models.yaml`](../../inventory/models.yaml) + [`THROUGHPUT-BASELINE.md`](../../spec/d6-agent-standard/THROUGHPUT-BASELINE.md) + 台账既有 `queue_s/run_s` 取真值 | 每个候选后端的 tps/显存/冷启**有出处**。⚠ 不许凭印象 —— 本轮已因"本地=20b 量级"这种印象错过一次 |
| **1** | 能力 | 固定题集（轻量 `echo`/`smoke-dispatch` + 一张真推理卡如 `o13-sympy`）**跨后端**跑同一批 | accept/golden 通过率 —— **"跑通"与"跑得对"分开报**（老教训：`rc=0` 不等于对） |
| **2** | 速度 | 同卡 `run_s` + decode tps | **冷启态与已加载态分开报**（冷启可能比云端慢一个量级） |
| **3** | **资源竞争** | 主路引擎**正在服务**时启动并使用备路引擎 | 主路吞吐掉落幅度；备路能否过 `load-gate` 内存门禁；对照 = 主路空闲时 |
| **4** | **故障相关性（决定性的那条）** | 构造主路 `rc=6`（`fallback-deadlock` 卡 / 真实站死锁，方法今天已用过），再试三路：**① 同站本地 ② 异站本地 ③ OpenRouter 云端** | 三路成功率 + 耗时。若①≈②（同因失效）而③独活 ⇒ **云端后端不可被本地替代** |
| **5** | **换站时的加载成本（原名"冷启动预算"，措辞已更正）** | ⚠ **派发链不加载引擎**（`_station_ready.sh` 只校验：未加载 ⇒ `ERR_NO_ENGINE exit 10`；主控 `Invoke-StationReady` 直接 throw `STATION_NOT_READY`）⇒ **"冷启动"目前不存在**，P3 若要用异站本地引擎**必须新增"加载"步骤**。故本维是**先定能力、再测成本**：<br>① 定：备路该不该承担加载？（否 ⇒ 未加载即 fail-closed/回落云端）<br>② 测 `T_load`：`infer-unload` → `infer-list` 确认未加载 → 计时 `cluster.py load` 直到 `READY_OK`，同时采站上 `free -g`/loadavg | ① **`T_load` ≤ 可接受上限？** 超了则"换站本地引擎"在交互式场景不可接受 ⇒ 只能 fail-closed 或回落云端<br>② **对照**：台账里同卡热态的 `queue_s/run_s`<br>⚠ 若结论是"要常驻"⇒ **与 [DESIGN §7.2](../../spec/d6-agent-standard/DESIGN.md) 的零自加载不变式②冲突**（否决理由写明"新增常驻进程即新增挂死面（A 站 KFD bug 族史）"）⇒ **要动不变式才能走**，须显式裁定 |

**候选后端**（台账真值，非印象）：站上本地 = `gpt-oss-`**`120b`**（decode ~50tps）、`nemotron-120B`（~22）、`MiniMax-M2.7`（~21.5）、`qwen3.8-flash-next`（~19，长 ctx 塌缩到 ~6）、`deepseek-v4-flash`；云端 = OpenRouter 免费档 `inkling:free` / `nemotron-3-ultra:free`（**仅 harness 可用**）。

**⚠ 操作影响（必须先说清）**：③④⑤ 要**真实加载引擎** ⇒ 占站上统一内存/显存、`gates`·`engine` 门禁会转黄/红、做完**必须** `infer-unload` 清残留。⇒ **单独一轮做**，别夹在别的改动里。

**执行顺序**：0 → 1/2（轻量）→ 5（冷启，代价小）→ 3/4（重，需真死锁）。
**产物**：一张对照表 + 一句结论（`public`/`sanitized` 默认后端）写回 §3.1。

### 3.5 测量 3 实测结果（2026-09-21 已执行）——**它改写了 P3 的理由**

**方法**：B 站加载 `gpt-oss-20b` → 跑 `fallback-deadlock` 卡（`timeout_s=10`，输出 1..800）造**信号类** `rc=6` → **在同一条命令里**立刻探针（避免"下次工具调用才探"的延迟）。

| 观测量 | 值 |
|---|---|
| **cold 对照**（未加载） | `_station_ready.sh` ⇒ **`ERR_NO_ENGINE exit 10`**（0.18s）⇒ 探针**确实能区分状态** |
| `T_load`（11G 模型，B 站） | **7s**（`infer-load` 21:11:34 → 21:11:40 `READY ✓`） |
| `T_firstgen`（加载后**第一次**生成） | **1.54s**（`cached_tokens: 0`） |
| 预热态同请求 | **0.99s**（`cached_tokens: 871`）⇒ 冷代价 ≈ **0.55s** |
| **`rc=6` 后 +0s** 的 chat 往返 | **HTTP 200 / `PROBE_T=1.073s`** ⇒ 与空闲态**几乎无差** |
| `rc=6` 后 slot | `{"active":[],"count":0,"parallel_slots":4}` ⇒ **无残留 in-flight** |
| `rc=6` 后 loadavg | 2.06（空闲基线 1.37） |
| 主路台账 / 墙钟 | `…,local-only,6,2,20`（queue 2s / run 20s）；`dispatch_wall=33.4s` |

**结论（推翻一个前提）**
1. **信号类 `rc=6` 之后引擎完全健康**（首生成 1.07s、slot 干净、`/v1/models` 正常）⇒ 主路失败的原因是**预算不足**（`timeout 10` 掐断的是**客户端**），**不是引擎不可用**。
   ⇒ 这一类 `rc=6` 的正确修法是 **给足预算**（P4 的 `fallback-timeout-s`，或调 `timeout_s`），**不是换后端**。
2. `parallel_slots=4` ⇒ 被掐断的请求**不阻塞**后续请求 ⇒ "同站 slot 被前一个请求占死"这个担心**不成立**。
3. **换站的加载成本对小模型可接受**：`gpt-oss-20b` = load **7s** + 冷生成额外 **0.55s**。⚠ **大模型未测**（`deepseek-v4-flash` 145G / `m27-q4ks` 100G / `qwen3.8-flash-next` 87G / `nemotron-120B` 80G）。
4. ⚠ **P3 的理由因此收敛**（不再包含"给信号类 rc=6 兜底"）：

| P3 的原理由 | 实测后 |
|---|---|
| ✅ 绕开**主控 Trae 沙箱**（主控带工具调用的 claude 必挂） | **仍成立**（与 rc=6 无关） |
| ✅ 给 `local-only` 一个**合规兜底**（现状：local-only 死锁 ⇒ 直接 `rc=4` **零兜底**） | **仍成立** |
| ✅ **故障域 / 资源隔离** | **仍成立，且 §3.6(d) 给了实测支撑** —— 引擎被占满时同站备路要**排队 66.6s**（吃光预算），异站/云端不受影响。⚠ ~~"引擎自身挂死"~~ 那一类**无可控手法**（§3.6(a)：O-23 实为**客户端**挂死，引擎健康） |
| ❌ ~~给信号类 rc=6 兜底~~ | **已证不必要** —— 引擎是好的，缺的是预算 |

5. **"引擎自身挂死"这一类：无可控手法**（**不是"未做"，是"没有可复现动作"**）—— 详见 §3.6(a)：项目里已记录的两类"死锁/挂死"（`fallback-deadlock` 信号类、O-23 ctx 错配）**都是客户端侧**，引擎健康；驱动级（A 站 KFD 族）只能等自然发生。⇒ 这部分证据**只能靠"装好观测面等它发生"**，不能人造。

**顺带暴露两个缺陷（已登记 OPEN-ISSUES）**
- **"备路总墙钟预算"缺失**：`T_load` 与主控侧 sync/collect **都不在** `timeout_s` 内（实测 `dispatch_wall=33.4s` vs 卡预算 **10s**）⇒ 任何"换站 / 加载"方案都需要**另立总预算**；P4 的 `fallback-timeout-s` **不覆盖**它。
- **`agent-cli.ps1 task` 在 fallback-reject 路径上进程退出码 = 0**（日志却写 `REJECT … exit 4`）。而同文件的 `route`（exit 2）与 claude-station-reject（exit 4）**都正确传播** ⇒ **非普遍问题**，疑为已知的"函数返回值被管道污染"类（09-18 闭环过一次同类）。**未复现确认**。

### 3.6 第二轮实测：O-23 类问题重新定性 + 「引擎忙」实测（2026-09-21 已执行）

#### (a) O-23 的"挂死"是**客户端**挂死 —— 引擎健康

| 已记录的"死锁/挂死" | 真实机制 | 引擎状态 |
|---|---|---|
| `fallback-deadlock`（信号类 rc=6） | 远程 `timeout 10` 掐断**客户端** | ✅ 健康（§3.5：+0s 首生成 1.07s） |
| **O-23 ctx 错配** | 引擎**秒回 400**，`opencode` **不处理该 400** ⇒ 永久挂死 | ✅ 健康（回 400 不等于挂） |
| A 站 KFD bug 族史 | 驱动级 | ❓ **无可控手法**，只能等自然发生 |

**完整因果链（三个环节，每个都有已知修法）**：
1. 引擎 ctx 硬上限（我们设的 `-c ${CTX:-32768}`）
2. 超限 ⇒ llama.cpp 回 **400**（`request (N) exceeds the available context size (M)`，逐字出自其 `srv send_error`；社区返证 [anomalyco/opencode#11286](https://github.com/anomalyco/opencode/issues/11286)，本地亦存 [O21-ctx-closure-verification.md](../../spec/d6-agent-standard/O21-ctx-closure-verification.md)）
3. `opencode` **不识别**该错误串 ⇒ **永久挂死** ⇒ 我们这边表现为 `rc=6`

| # | 修法 | 状态 |
|---|---|---|
| ① | **提高 ctx** | 受统一内存约束；且有"agent 固定开销"下界（社区实测：单是 system prompt + 工具定义就 **19k~22k** tokens ⇒ ctx 低于 ~24k 则首轮必超） |
| ② | **开 context shift**（llama.cpp 官方对这条 400 的建议原文："try increasing the context size or **enable context shift**"） | ⚠ **我们主动关着** —— [infer-load L232](../../ops/station-bin/infer-load#L232) 写死 `--no-context-shift` |
| ③ | **客户端识别该错误串**（业界标准做法：litellm 的 `is_error_str_context_window_exceeded` + `context_window_fallbacks` 自动回切） | ❌ 我们**没有** —— `opencode` 不识别；而 `Test-FallbackEligible` 会把这类挂死**归入 rc=6** |

**⚠ (b) `--no-context-shift` 是一个"未被审视的启动旗标"**：它是随 unsloth 迁移那次提交（`5c712ce`）带进来的，**旁边没有理由注释**、也没有在 issue/ADR 里讨论过。后果是**超限时硬失败**而不是滚动截断 —— 这在"判据必须可信"的取向下有正当理由（静默截断会让结论不可信），**但那个理由从未被显式写下**，也没人核对过它与"客户端不处理 400 ⇒ 挂死"组合起来的代价。⇒ **应显式裁定**：要"硬失败"就得同时补 ③（客户端识别），否则就是"硬失败 + 挂死"。

> **⚠ 就地更正（2026-09-21 晚，见 §3.8(d) 第 4 条）**：上句"**随 `5c712ce` 带进来**"**不准确**。实查：该旗标在项目里**约二十处一致出现**（`infer-load` 之外还有 5 个 flavor `.env`、5 个手写启动脚本、[MODEL-SOURCING 模板](../../spec/model-eval/MODEL-SOURCING-2026-09.md)、崩溃根因分析文档的复现命令）⇒ 它是**项目级既有惯例**（横跨 unsloth 迁移），**不是某次迁移的偶然**。原文保留以便溯源；**其"理由从未写下"这一点仍成立**，已由 §3.8 补上。

**⚠ (c) ③ 对 P3 有直接冲击**：`Test-FallbackEligible` 只认 `rc=6` ⇒ 若"400 挂死"也落进 rc=6，**备路会去兜一个换后端也兜不住的错**（ctx 不够换到哪都不够）。⇒ 这与 P0 闸同族：**判据必须能区分"引擎不可用"与"配置/客户端错误"**。

#### (d) 「引擎忙」实测 —— **给 P3 补回一条可复现的支撑**

**方法**：B 站加载 `gpt-oss-20b`（`parallel_slots: 4`）⇒ 并发 4 个长生成占满 ⇒ 立刻发第 5 个请求（备路视角）。

| 观测量 | 值 |
|---|---|
| 占满后 `active-generations` | `{"active":[4 条…],"count":4,"parallel_slots":4}` |
| **第 5 个请求（"备路视角"）** | **`HTTP 200 / PROBE_T=66.57s`** ⇒ **排队等了 66.6 秒**，**不是拒绝、不是报错** |
| 释放后 | `PROBE_T=1.07s`、`count:0` ⇒ 完全恢复；三站复归未加载、无残留 |

**⇒ 结论（修正 §3.5 的悲观判断）**：备路的现实触发场景**不只是"引擎坏"**，还有**"引擎被占满"**。此时：

- **同站**本地备路 ⇒ 请求**静默排队**（O-25 已登记的痛点），等待**吃光它自己的预算**（P4 的 `fallback-timeout-s`）⇒ 若预算 < 排队时间 ⇒ **备路超时失败**。实测 66.6s **远超**多数卡的 `timeout_s`（如 `fallback-deadlock` 的 10s）。
- **异站**本地引擎（空闲）⇒ 立即可用。
- **云端** OpenRouter ⇒ 不共享本站队列，同样立即可用。

⇒ **"故障域/资源隔离"这条 P3 论据，现在有可复现的实测支撑了**（我上一条说"只剩未复现的驱动级担忧"是**过早**的判断，此处更正）：它不靠"引擎会坏"，而靠 **"引擎会被占满，而占满的等待会吃掉备路预算"**。

### 3.7 C1 实弹：「ctx 超限」是**两个形态**，落点完全不同（2026-09-21 已实施 + 实弹）

> 起因：§3.6(a) 认定"rc=6 里混着 ctx 超限 ⇒ 备路会兜错方向" ⇒ 决定**把它分出来**（用户裁定执行）。

#### (a) 实弹两级结果 —— 第一级就推翻了前提的一半

| 级 | 构造 | 实际命中 |
|---|---|---|
| **形态 B**（复现成功） | **456KB 卡（≈114k tokens）**，**B 站 `gpt-oss-20b`（引擎 ctx 32768）**，`timeout_s:20` | 错误体**逐字**：`Message too long: 104003 tokens exceeds the 32768-token context window … "code":"context_length_exceeded"` ⇒ **opencode（客户端）自己的长度校验** ⇒ **快速失败**（还 `RESUME[1]/[2]` 两轮各立即失败）⇒ **`rc=1`**，**不是 6** ⇒ **本就不触发 fallback** |
| **形态 A**（未复现） | 需要"**引擎实际 ctx < opencode 的 catalog 认知**"（O-23 的"预算不可信"） | **未发生** —— 本次实测**证明 opencode 对 `gpt-oss-20b` 的内置 catalog 就是 **32768、与引擎一致**（它自己算得出超了 ⇒ **请求根本没发出去**，所以走不到引擎的 400） |

**⇒ 两个形态必须分开记**：

| | 形态 A（危险） | 形态 B（不危险） |
|---|---|---|
| 400 来自 | **引擎侧**（llama.cpp `srv send_error`） | **客户端/SDK**（长度校验） |
| 客户端行为 | **不识别 ⇒ 永久挂死** | **快速失败** |
| 落点 | **rc=6** ⇒ **会被备路兜** | **rc=1** ⇒ 不触发备路 |
| 前提 | 客户端**低估**了占用（估算 ≤ catalog，实际 > 引擎 ctx） | 客户端**算得出**超限 |

**⚠ 顺带收窄一条旧结论**：O-23 的"opencode 的发送预算不可信"**至少对 `gpt-oss-20b` + 当前 opencode 版本已不成立**（catalog 与引擎恰好一致）。是否对**其它模型/版本**成立，**未测**。

#### (b) 实施（C1）

| 项 | 内容 |
|---|---|
| `Test-CtxOverflowError`（纯函数） | 认 **4 个逐字串**：llama.cpp 中段 `exceeds the available context size` / 类名 `ContextOverflowError` / `context_length_exceeded` / `Message too long`。**刻意不宽泛**（免得把普通输出误判成配置错误） |
| `Resolve-CtxOverflowCode`（纯函数） | **只 `rc=6` ⇒ `14`**；**其它 rc 一律不改** —— 理由：`rc=1` 是"agent 退出 1"这一大类，改写成 14 会**掩盖**该类的其它含义（与"rc 不可信"同源）；且形态 B **本就不触发 fallback** ⇒ 无需防兜错 |
| 落点 | `Invoke-Task` 内，**紧接 `$contentSha` 之后**（台账行 / run.json / `TASK_DONE` / fallback 判定**之前**）⇒ 四处 `$code` **一致** |
| 退出码登记 | `_VERDICT_RC_MAP` 加 `14: {14}`；DESIGN §8 加一行 |
| **双向自证** | 夹具 **81/81**（含 4 串真值表 + 不误判 + 空值不抛 + **`Resolve` 三向**：6⇒14 / 1⇒1 / 未命中不变 + **两条位置断言**守住"检测早于台账行、早于 fallback 判定"）；**形态 B 实弹证实**（诊断行出现、`exit=1` **未改写**、**无** `AUTO_FALLBACK` 行）；**形态 A 未被实弹证实也未被证伪** |

#### (c) 诚实边界

1. **形态 A 未复现** ⇒ `rc=14` 这条路径**只有夹具级证据**，没有实弹。判据是按已定性机制写的（llama.cpp 原文串逐字取自 O-21 记录），但**需要真正遇到时用归档件复核**。
2. **形态 A 在当前配置下难以自然发生**（catalog 与引擎一致）⇒ 它更可能出现在"**换模型/换 opencode 版本后 catalog 变了**"的时候 ⇒ 已登记为**可做项：把"引擎 ctx vs catalog 一致性"纳入巡检**（`_station_ready.sh` 已输出 `ENGINE_CTX`）。
3. **`--no-context-shift` 的裁定仍未做**（若要"硬失败"，就得同时补"客户端识别"那一环，否则形态 A 依然是"硬失败+挂死"）。
4. 顺带观察（**未修**）：形态 B 下 opencode 仍 `RESUME` 了 **2 轮**，每轮立即失败 ⇒ 确定性错误被重试了两次（浪费但无害）。

### 3.8 裁定：**保持 `--no-context-shift`**（2026-09-21；含实测证据 + 反对意见 + 两处对前文的更正）

#### (a) 先把"它是否真的生效"钉死（探针**绕过 opencode** 直接问引擎）

| 问 | 答（实测） |
|---|---|
| 旗标是否**到达**内层 `llama-server`？ | ✅ **到达，且出现两次**（studio 自拼一次 + 我们传的一次）：`… --parallel 4 --flash-attn on --no-context-shift -c 32768 --alias gpt-oss-20b-MXFP4 -ngl -1 --fit off --metrics … --device ROCm0 …` |
| 引擎自称 ctx | `n_ctx: 32768`、`total_slots: 4` |
| **行为是否真的变了**（直接发 ≈**76,650 tokens**，即 ctx 的 2.3 倍） | ✅ **HTTP 400**，0.26s（**即时拒绝**，未排队、未截断） |

#### ⚠ (b) 这次探针**顺带推翻了两件事**（对 §3.7 的更正）

**(1) 那条 400 是「引擎原生」的，不是「客户端校验」** —— 本探针**完全绕过 opencode**（直接 curl 引擎 `127.0.0.1:8080`），拿到的报文与"经 opencode 时"**逐字同款**：

```
{"error":{"message":"Message too long: 68076 tokens exceeds the 32768-token context window.
  Try increasing the Context Length in Model settings, or shorten the conversation.",
  "type":"invalid_request_error","param":"messages","code":"context_length_exceeded"}}
```

⇒ §3.7 把形态 B 定性为「**opencode（客户端/SDK）自己的长度校验**」**是错的** —— 它是**引擎**回的。
**(真值)** 经不经客户端，引擎**都是立即 400**；**唯一的区别在"客户端拿到 400 之后怎么做"**。⇒ §3.7 那张"形态 A/B"对照表按"400 来自谁"划分**不成立**，应按"**谁不处理它**"划分。

**(2) 报文措辞**已经变过**：O-21 记录的是 `request (N) exceeds the available context size (M)`；当前 llama-server 回的是 `Message too long: N tokens exceeds the M-token context window` + `"code":"context_length_exceeded"` ⇒ **llama.cpp 改过这段文案**。
⇒ 这**正好解释**了为什么我第一版判据（只认旧串）在实弹里**一个都没命中** ⇒ **判据串必须版本化**（见 (e)）。

**⇒ C1 的动机随之改变**：它针对的那条链（**400 ⇒ opencode 不识别 ⇒ 永久挂死 ⇒ `rc=6` ⇒ 备路兜错**）**在当前版本下不存在**（实测 opencode 拿到 400 是**快速失败 `rc=1`**）。`rc=14` 因此是**为旧版本 / 未来回退准备的防线**，**不是当前活跃缺陷**。

#### (c) 裁定：**保持 `--no-context-shift`**，**不开** context shift

| 选项 | 代价 | 与项目取向 |
|---|---|---|
| **保持（现状）** | 超 ctx ⇒ **硬失败 400** | ✅ 硬失败是**响亮**的：当前版本下客户端**快速失败 `rc=1`**（不挂死、不触发备路），且 C1 能**识别并诊断** ⇒ **可诊断的失败** |
| **开 context shift** | 旧 token **静默丢弃** ⇒ 请求"成功"，agent 在**不知道自己被截断**的前提下继续作答 | ❌ **静默降级**：结论建立在**残缺输入**上，而链路上**没有任何判据能发现** ⇒ 正是本项目所忌的"静默错误" |

**⇒ 选"硬失败"**：它**丢的是任务**；shift **丢的是可信度**。本项目的判据体系（证据流 / 归档 / 验收 / 基线）全都建立在"**输入完整**"之上 —— 静默截断会让**所有下游判据同时失真**，而且**不可回溯**（你不知道它丢了多少、丢了哪一段）。
**为什么这不是"在两个坏选项里挑"**：正解是**避免撞上限**（提高 ctx / 控制上下文增长），而**硬失败恰好把"撞上限"变成可见事件** ⇒ 它是"逼你去看"的机制；shift 会把它**藏起来**。

#### (d) 反对意见与剩余风险（诚实列出）

| # | 反对 / 风险 | 处置 |
|---|---|---|
| 1 | **若客户端将来回退到"挂死"** ⇒ 硬失败就变成挂死 | 由 **C1** 兜（识别 + `rc=14` + 不触发备路）⇒ **C1 是本裁定的配套依赖**，不是可选优化 |
| 2 | 硬失败会让**长会话后期**的任务直接失败（而 shift 至少能"跑完"） | **有意**：这是"**跑不完**"换"**跑错没人知道**"。要跑长会话 ⇒ 应提高 ctx 或换长 ctx 的 flavor，**不是**开静默截断 |
| 3 | O-21 的"环境修复 > 配置修复"要求根本解决 | 本裁定**不反对**那条 —— 提高 ctx / 控制上下文增长仍是正解；本裁定只决定"**撞上限时**要响亮还是要静默" |
| 4 | `--no-context-shift` 在项目里**约二十处一致出现却从未写下理由** | ✅ 本裁定**就是**把它写下来 —— 此前是**惯例**（且**不是**某次迁移偶然带入：`infer-load` 之外还有 5 个 flavor `.env`、5 个手写启动脚本、[MODEL-SOURCING 模板](../../spec/model-eval/MODEL-SOURCING-2026-09.md)），现在成为**有据之规** |

#### (e) 落地项：判据串**版本化**

现行 C1 判据含 4 串，此前未区分版本 ⇒ 按版本归类（**四个都留**：版本会变，少认一个就少一条防线）：
- **当前版**（2026-09-21 实测）：`Message too long`、`context_length_exceeded`
- **旧版**（O-21 记录，作**旧版兼容**）：`exceeds the available context size`、`ContextOverflowError`

---

## 4. 建议实施顺序与验收判据

| 序 | 项 | 类型 | 说明 |
|---|---|---|---|
| **P0** | **止血**：在 `Invoke-Task-Claude` + `AUTO_FALLBACK` 调用点各加 `local-only` 拒绝（双点，~数行） | 代码 | ✅ **2026-09-21 已实施**（判据收敛为唯一纯函数，见 §4.1） |
| P1 | 核对 OpenRouter 隐私设置（opt-in 日志必须关）+ 登记 | 运维 | ✅ **核对面已完成**：开关**不可机读**（故只能人工读表）；四开关实况入档；免费/付费档策略矩阵实测。**结论**：① 已关；**免费档 train 开** ⇒ 加 `sanitized` 闸后**同日撤回**，改登记为已知风险。[全文](../security/2026-09-21_OpenRouter数据策略与隐私开关核对.md) |
| P2 | 判据统一：`local-only` 闸改为"后端 `egress` 属性" | 代码 | ◐ **2026-09-21 部分落地（随 P3）**：**claude 通道的两个入口已参数化**（直接入口 `-backendEgress (-not $useStation)`；兜底入口保留 `$true` —— 它在主控本地 = 云端 = 出网，语义正确）。⚠ **既有三处仍按型号前缀判**（`Resolve-Model` L435 / `Invoke-Task` L987 / route cmd）⇒ "再加一个云端后端又漏一次"的结构根因**未消除**，仍未闭合 |
| P3 | claude 备路**站上化**（ssh + 脚本落盘；后端按 sensitivity 分流；选站排除死锁站；fail-closed） | 代码 | ✅ **2026-09-21 已实施（按用户裁定："按 sensitivity 分流"）** ⇒ `local-only` ⇒ **站上**跑 claude + **站上本地引擎**（物理不出网）；`sanitized`/`public` ⇒ **保持主控本地 spawn**（已实弹验证的路径**不动**）。**实现要点**：① 只换 **runner**（新增 `Invoke-ClaudeFly-Station`，与 `Invoke-ClaudeFly` **严格同契约** ⇒ 归档/accept/golden/usage/证据面/resume 循环**零改动**）；② 新增纯函数 `Resolve-ClaudeStationCandidates`（异站优先、被排除者排最后、空 ⇒ fail-closed）+ `Test-StationEngineReady`；③ **站上不可用 ⇒ `REJECT local-only-no-station-engine (exit 4)`，绝不退回主控本地（回退=出网）**；④ **P2 落定**：判据输入由"型号前缀"改为**后端属性** ⇒ 直接入口传 `-backendEgress (-not $useStation)`；⑤ 站上临时 settings **从引擎 `/props` 现读 `n_ctx` 自对齐** `CLAUDE_CODE_MAX_CONTEXT_TOKENS`（站上既有值 **120000** vs 引擎 **32768** ⇒ 不覆盖就自造"预算不可信"）。**实弹**：`local-only` 卡 + `-Cli claude` ⇒ `P3_CANDIDATES: B,A,C(pref=B)` → 选中 B → **`engine_ctx=32768 max_context_tokens=28672 base_url=http://127.0.0.1:8080`** → `P3_STATION_RC=0` → 归档 `agent-output.txt = P3-LOCAL-OK`、`exit=0`、台账 `…,local-only,0,0,58`。**不出网的可判证据（非仅结构性）**：站上临时 settings 的 `apiKeyHelper` 指向 **unsloth.key**（本地引擎 key）⇒ 若请求打到 OpenRouter，**必然 401**；而它 **rc=0** ⇒ **反证请求没去云**。**夹具 92/92**。<br>**⚠ 同日复查又修了两处"设计意图没落地"的缺口（非新需求 —— 是 P3 自己那条没生效）**：**(1)「优先选与死锁站不同的一站」实际未生效**：原版 `$avoid` **只读 `$env:AGENT_AVOID_STATION`**，而**没有任何代码在运行时填它** ⇒ 兜底时会**优先选中刚 rc=6 的那一站**（它的引擎"在服务" ⇒ 就绪探针通过，而它可能已被 wedge）。修法：**兜底调用点把主路死锁站传进来**（`-AvoidStation $station`），`$env` 降级为**手工覆盖通道**。**(2) `pref` 会覆盖率 `avoid`**（第二个交互缺陷）：兜底时卡的 `model` 常正指向**刚死锁的那一站**（`model: gpt-oss-20b` ⇒ B）⇒ 若无条件把 pref 提前，"避免死锁站"就被架空。修法：两条规则**提进纯函数**（`-Avoid -Stations -Preferred`，**次序不可交换**：avoid 胜过 pref，pref==avoid 时只能垫底）。**判别性实弹**（同一张卡、只切换 avoid）：`avoid=''`（pref=B）⇒ `P3_CANDIDATES: B,A,C` 且**立刻**选中 B（无 SKIP）；`avoid=B`（pref=B）⇒ **`A,C,B`** + `SKIP A` → `SKIP C` → 选中 B ⇒ **avoid 胜、B 垫底**（旧代码此处会打印 `B,A,C` 并立刻选中 B ⇒ 两行即判别依据）。`P3_STATION_SKIP` ×2 顺带证明**多候选逐个重试是真的**（⚠ **更正上一条提交信息里"多候选重试未做"的说法** —— 循环本来就在，我当时把"首个就绪"误读成"不重试"）。夹具 **98/98** |
| P4 | 备路独立预算 `fallback-timeout-s` | 代码 | ✅ **2026-09-21 已实施**：新增卡键 `fallback-timeout-s`（0 sentinel = 沿用 `timeout_s`）+ 纯函数 `Resolve-ClaudeBudget`（`first = fallback>0 ? fallback : timeout_s`；`resume = continue>0 ? continue : **first**` ← 该回落目标由 `timeout_s` 改为 `first`，防"首跑用备路、续接回落主路"错配）。自证：夹具 **69/69**（+8 条）+ **实弹双卡**（同一进程里卡未设 ⇒ `first=5 … first_src=timeout_s`；卡设 8 ⇒ `first=8 … first_src=fallback-timeout-s`）+ **变异自证**（让纯函数忽略 fallback ⇒ 恰 2 条相关断言变红）。⚠ **但它只覆盖"备路跑批"** —— **不覆盖**"换站/加载/就绪校验/sync-collect"那三段（见 §3.5 与 OPEN-ISSUES「总墙钟预算缺失」行） |
| P5 | `public`/`sanitized` 开 ZDR（账户级/guardrail） | 运维 | ⛔ **2026-09-21 已裁定：不做**（[全文](../security/2026-09-21_ZDR可行性裁定与影响面.md)）。**判据不是"ZDR 好不好"，而是"有没有流量需要它"**：① **ZDR 是按 model group 分作用域**（Anthropic/OpenAI/Google/SpaceXAI/**All other models**）—— 我此前"账户级一锅端"的说法**只对最后一个作用域成立**，已更正；我们现用型号**全是 `:free` ⇒ 100% 落在 "All other models"** ⇒ 给该作用域开 ZDR = **5 类消费者全灭**（备路×2 / judge 槽 / 站上 opencode 免费档表 / 档序备选）。② **`local-only` 已强于 ZDR**（**不出网** vs ZDR 明确"不改变数据到达 provider"）⇒ 对它开 ZDR 是**降级且违反不变式②**。③ **`sanitized` 抹完 = `public`** ⇒ 与 public 同级。⇒ **"允许出网但不允许留存"这个格子是空的**。**若将来真要 ZDR ⇒ 必须换付费型号**（已实测可用：`mistralai/mistral-nemo`、`inclusionai/ling-3.0-flash` 连 `zdr` 都过）⇒ **"开 ZDR"从来不是可执行动作，它是"换后端"的同义语**。**⚠ 裁定顺带发现的真正风险点**：②③ 依赖一条**从未验证的前提** ——「scrubber 抹得干净」⇒ 已登记**新可做项：`sanitized` scrubber 的覆盖率判据**（那才是 P5 的真正替代品） |

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
