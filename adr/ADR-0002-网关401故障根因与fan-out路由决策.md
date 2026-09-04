# ADR-0002: 网关 401 故障根因分析与 fan-out 路由决策（绕网关编排层直连）

***

id: ADR-0002
type: adr
version: 1.0
status: accepted
date: 2026-09-04
depends: [BS-2-L1, BLINDSCAN-v2-orchestration]
upstream: null
--------------

> **Feature**: B 站 LiteLLM 网关 :4000 auth 401 故障的根因定位，及由此触发的路由决策——fan-out 与 agent 链路绕网关、走编排层直连 B/A 两站 8080。
> **创建日期**: 2026-09-04
> **状态**: accepted
> **适用**: D6 agent 标准框架的推理接通层、BS-2 扇出发起

***

## 元数据

| 字段   | 值 |
| ---- | ---- |
| 编号   | ADR-0002 |
| 日期   | 2026-09-04 |
| 状态   | accepted |
| 决策者  | Scott (鹏) + Trae (GLM-5.3/DeepSeek-V4-Flash) |
| 相关文档 | [BLINDSCAN-v2-orchestration.md](../spec/d6-agent-standard/BLINDSCAN-v2-orchestration.md)、[CHECKLIST.md](../spec/d6-agent-standard/CHECKLIST.md)、[DESIGN.md](../spec/d6-agent-standard/DESIGN.md)、[双机推理集群使用手册.md](../docs/双机推理集群使用手册.md) |
| 取代   | 无（新增） |

**证据等级约定**（本次会话实测，E1=本会话 SSH/本地实测；E2=前会话实测留档；E3=外部；E4=推断）：

- **E1** = 2026-09-04 本会话对 B 站（scott-lau-GTR-Pro.local）齐全命令输出，留档于 BLINDSCAN §8.7.5 与「审计记录」节
- **E4** = 未闭环、需后续验证（A 站直连链路）

## 范围声明（先于一切）

**本 ADR 只约束「agent/编排层如何接通后端」：决策 C = 绕开 LiteLLM 网关，编排层用并发 HTTP 直连 B/A 两站 unsloth llama-server(8080)。** 不改变推理架构本身（双端点拓扑、GTT 互斥、内存门控、模型加载分工）；不等同于删除网关服务（网关进程保留以便后续 heal/resume 语义问题）。A 站跨站直连链路当前因 A:8080 未监听而**部分待执行**，详见后果节。

## 背景（Context）

### 触发实例

2026-09-04 执行 BS-2 L1 验证时，B 站 LiteLLM 网关 :4000 全程 401 / Internal error。初始诊断（BLINDSCAN §8.7.5 首版）误判为「master_key 明文与库内哈希不匹配」，随后二次核实推翻该断言，定位到真实根因。本 ADR 固化修正后的根因与路由决策。

### 根因（二次核实，E1）

LiteLLM 网关 :4000 对 `master_key=sk-RPC-gz...` 也返回 401「Invalid token payload」，但该错误**逐字源自上游后端对过期占位 key 的拒绝**，非网关 frontdoor 校验失败。证据链：

1. **后端实例经换载重启、key 过期**：本地 8080 unsloth 实例于 9/4 03:24:25 重新拉起，加载 gpt-oss-120b-MXFP4，由 unsloth studio 生成 key `sk-unsloth-0895...`（E1，`ps -o lstart`）。
2. **网关 config 仍写旧占位 key**：config.yaml `nemotron` 路由 `api_key: sk-local-noauth`；且 config mtime 为 9/2 01:24 < 进程启动 9/3，litellm 加载的就是这份 config（排除「config 在启动后被改」）（E1，`stat` vs `ps -o lstart`）。
3. **复现铁证**：直打 8080 用 `sk-local-noauth` → `{"message":"Invalid token payload","type":"authentication_error"}`，**与网关 401 逐字一致**；同后端换真实 `sk-unsloth-0895...` → 200 OK（E1）。
4. **fallback 叠加失效**：网关回退到 `gpt-oss`→A(10.10.10.1:8080) 返回 Connection error——A 主机通（USB4 0.2ms/LAN .33 0.6ms）但 **8080 未监听**（E1）→ 双后端全挂 → 网关整体 401。
5. **与「AB 更新」关系**：是**更新/换载后配置不同步**（后端 key 变了、litellm 未重启同步、A 端未拉起），非更新损坏网关二进制。apt 更新（9/4 14:35）全是系统包（sssd/linux-firmware/libssh2/lemonade），liitellm 在独立 venv，不受影响（E1，dpkg.log）。

**结论**：网关 401 = ① 主路由 `nemotron` 后端占位 key 过期 + ② fallback `gpt-oss` 后端（A）当前下线。这是「中间层持有与后端不同步的状态」这一类故障，而**不是**对任意后端的本质缺陷。

### 事前已知支撑（E1，BS-2 L1）

- 直连 gpt-oss-120b 3-tool 单轮仅 1 个 tool_call（模型内编译期并行不成立）。
- 编排层 3 线程并发 HTTP：wall 52.1s ≪ 串行和 110.9s（≈max，墙钟收敛）→ **后端数据面真并行**，节流在编排层，不在模型/网关。
- llama-server 无 `/properties`，`engine_stats.running` 不可用 → BS-2 客观判据改为墙钟收敛。

## 决策（Decision）

**方案 C —— 绕网关，编排层并发 HTTP 直连 B/A 两站 8080。**

1. agent 链路（opencode/claude）的 `cluster-litellm` 通路放弃，改用直连 8080 + 真实 `sk-unsloth-...` key；`cluster-local`/claude `ANTHROPIC_BASE_URL=:8080` 即为载体（B 站这些已直连，E1）。
2. fan-out 扇出押编排层并发 HTTP（与 BS-2 通过结论一致），不押模型单轮多 tool_call。
3. 网关进程保留不删除，但**不作为** agent 常用路由的必经跳点；其链路语义（rpm/fallback/虚拟 key）在有需要时另行评估。
4. A 站直连跨站扇出待 A:8080 拉起后续做（见后果）。

## 机制原理（为何有效）

- **消除状态漂移类故障**：直连后端 key 取自 unsloth studio 单一来源（`sk-unsloth-...`），不再有「网关 config 单独维护一套占位 key」的手动同步依赖。BS-2 已证 fan-out 本就该押编排层，网关在此链路中不提供扇出能力，属于纯转发开销。
- **职责对齐**：网关把「限流/熔断/多租户」集中化，但本地两站封闭局域网无此诉求；数据面并行在编排层即可获得。绕开网关 = 去掉一个与后端状态耦合的中间层，稳定性更优。

### 与既有 ADR/规则的关系

- 与 ADR-0001 D1.2「LiteLLM 跨模型 fallbacks + rpm」存在取舍：C 放弃网关 fallbacks/rpm，换稳定性。enforced decision：常用路由绕网关；网关保留但降级为显式备用，不参与默认 agent 链路。
- 与 D6 CHECKLIST 路由不变式（local-only 字节不出站）不冲突：仍是本地两端 8080 直连，无出站。

## 考虑的替代方案（Alternatives Considered）

### 替代方案 A: 修网关（改 `nemotron.api_key` → 真实 unsloth key + 重启 litellm）
- **优点**：恢复最快（~分钟）；保留 rpm/fallback/虚拟 key 语义。
- **缺点**：**保留本次故障的成因**——每次 unsloth 换载重铸 key，需手工改 config + 重启 litellm，且 `_bkeyupdate.sh` 目前只同步 opencode/claude、**未纳入 litellm**（这正是本次漏掉的环节）。中间层与后端状态耦合是结构性易错点。
- **否决理由**：稳定性依赖人工 key 同步纪律，易维护性差；网关在扇出上无增量价值。

### 替代方案 B: 只拉起 A 站 8080（补齐 fallback）
- **优点**：让网关 fallback 不浪费 600s 超时。
- **缺点**：**非独立修复**——主路由 `nemotron`(本地 8080) 仍 401，只拉 A 只是让「走到 A」成为可能，网关本身仍不可用。
- **否决理由**：没有主路由修复，B 无独立意义；其价值仅在配合 A 或跨站扇出时体现。

### 替代方案 C: 绕网关直连（采纳）
- 选型依据：稳定/易维护两维占优；与已通过 BS-2 结论自洽；消除「中间层状态漂移」这一类故障。
- 代价接受：丢网关语义（rpm/fallback/多租户 key）；nemotron 别名现载 gpt-oss 的语义变化；跨站需 A 上拉。

## 后果（Consequences）

### 正面
- 消除「网关持有与后端不同步 key」类故障（本次根因的直接解药）。
- agent 链路更简单：单一 key 来源（unsloth studio）+ 直连，无重启/双写。
- 与 BS-2 通过结论一致：fan-out 押编排层并发 HTTP，天然绕开网关方言与 auth。

### 负面 / 代价
- 丢失 LiteLLM 网关语义：rpm:30 限流、跨模型 fallbacks、usage-based-routing、虚拟 key、统一日志。若未来引入多租户/公网暴露需重新评估。
- `nemotron` 别名现直连 8080 载的是 gpt-oss-120b（非 nemotron 1M ctx）——若任务强依赖 nemotron 长上下文语义，需另行 reload nemotron 才能满足（本 ADR 不裁定模型选型）。
- 跨站扇出的第二后端 A:8080 当前未监听（A 主机通、端口闭），跨站直连链路**未闭环**，待 A 拉起后验证（见待验证项）。

### 中性 / 需要后续行动
- `ops/cluster.py` 的 `LITELLM_BASE`（健康/状态聚合）保留指向网关；网关进程保留，用于显式备用或 health 观测。
- wrapper 别名（`agent-cli.ps1` 的 `nemotron→cluster-litellm/nemotron`）需改为直连 provider，避免继续打坏网关。
- 手册/params-ledger 需同步路由语义（nemotron 别名现为直连 8080 + 现载模型）。

## 验证（Validation）

### 已有实证（E1，本会话）

| 依据   | 命令/来源   | 状态 |
| ---- | --------- | -- |
| 直连 8080 用 `sk-local-noauth` → 「Invalid token payload」逐字复现网关 401 | `curl -H "Bearer sk-local-noauth" 127.0.0.1:8080/...` | ✅ |
| 直连 8080 用 `sk-unsloth-0895...` → 200 OK | 同上换 key | ✅ |
| litellm 进程(9/3 10:51)未重启、config(9/2 01:24)未被改 | `ps -o lstart` vs `stat config.yaml` | ✅ |
| 本地 8080 实例 9/4 03:24 重载 gpt-oss-120b-MXFP4 | `ps -eo lstart,cmd | grep llama-server` | ✅ |
| A:8080 未监听（主机通、端口闭） | `ping 10.10.10.1` vs `/dev/tcp/10.10.10.1/8080` | ✅ A:8080 待拉起 |
| B claude 已直连 8080、cluster-local 已直连(工作 key) | cat settings.json / opencode.jsonc | ✅ |
| BS-2 L1：编排层 3 并发 wall 52.1s≪串行 110.9s | `_bs2_fanout.py` | ✅ |
| apt 更新与 litellm 无关（venv 隔离） | dpkg.log 核对 | ✅ |

### 待验证项（E4，未闭环）

- A 站拉起 8080 后，跨站直连链路（编排层扇出到 B/A 各 2 并发）总耗时 ≤ A 串行×~1.6（BLINDSCAN §8.7.4 跨站判据）。
- `nemotron` 别名直连 8080 后，长上下文/gpt-oss 语义是否满足现有任务（若否，需 reload nemotron）。

### 失效条件（何时重审本 ADR）

- 若未来引入多租户/公网暴露/统一限流成为硬需求，需重审 C 的「丢网关语义」代价。
- 若 A:8080 跨站直连实测不收敛（赔率走坏），跨站扇出部分需回退到网关或其他方案。

## 修订历史

| 日期   | 变更 |
| ---- | -- |
| 2026-09-04 | 初始版本（含故障根因二次核实、方案 C 决策） |

***

## 审计记录（Anti-Hallucination Review, 2026-09-04）

**方法**：ADR 初稿完成后，对全部事实性声明与本次会话实测输出逐条比对；重点复核此前 BLINDSCAN/CHECKLIST/memory 中「master_key 哈希不匹配」误判是否已修正。

### A. 误判→修正记录（1 处，已同步更正 BLINDSCAN §8.7.5 / CHECKLIST / project_memory）

| # | 初始断言 | 二次核实事实 | 纠错性质 |
| - | -- | -- | ---- |
| 1 | 「网关 401 为 master_key 明文与库内哈希不匹配的独立 ops bug」 | 401 逐字源自上游后端对过期占位 key `sk-local-noauth` 的拒绝；litellm frontdoor 校验顺利进入路由与 fallback | **归因错误**——把后端 key 不匹配误认为网关 frontdoor key 配置损坏 |

### B. 正文声明核验（关键项）

| 正文声明 | 核验输出（2026-09-04） | 结果 |
| ---- | ---- | -- |
| 直连 8080 `sk-local-noauth` → Invalid token payload | curl 输出 `{"error":{"message":"Invalid token payload","type":"authentication_error"}}` | ✅ |
| 直连 8080 `sk-unsloth-0895...` → 200 | curl 输出 `{"id":"chatcmpl-...","choices":[{"message":{"role":"assistant","content":"Hello!..."}}]}` | ✅ |
| config `nemotron.api_key=sk-local-noauth` | `grep -nE 'master_key|api_key' config.yaml` | ✅ |
| litellm 进程未重启 | `ps -o lstart= -p 2637` → 四 9月3 10:51:09；config stat 9/2 01:24 | ✅ |
| 本地 8080 重载时间 | `ps -eo lstart,cmd` → 五 9月4 03:24:25 unsloth studio run gpt-oss-120b-MXFP4 | ✅ |
| A:8080 未监听 | `/dev/tcp/10.10.10.1/8080` 连接被拒绝；ping USB4/LAN 都通 | ✅ |
| B claude/cluster-local 已直连 | cat settings.json（:8080 + sk-unsloth）、opencode.jsonc（cluster-local :8080） | ✅ |

### C. 残余风险声明

1. A 站直连跨站扇出**未闭环**（A:8080 未监听），本 ADR 仅记录决策 C 与 B 站 immediate 执行；A 侧为 E4，待验证项已列。
2. `sk-unsloth-0895...` 为主控站 `_bkeyupdate.sh` 先验的写死值，本次实测有效；若 unsloth studio 重铸 key，需回填（与 ADR-0002 结论一致：key 单一来源，但回填仍是运维动作）。
3. dips 「nemotron 别名语义现载 gpt-oss」为现状描述（E1），是否 reload 属模型选型，不在本 ADR 决策范围。