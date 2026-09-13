# D6 与单机 agent CLI 工作流闭环分析报告

---
id: d6-closed-loop-analysis
type: research
date: 2026-09-09
depends: [d6-agent-standard/OPEN-ISSUES.md O-24, d6-agent-standard/ARCHITECTURE.md, d6-agent-standard/CHECKLIST.md]
status: research
---

> **背景**: O-24（单机 agent CLI 工作流闭环断点）分析定案后，补社区实践调研，验证并细化 P0-P2 优先级，形成可落地的闭环设计依据。
> **单机形态定义**: 本机/单站独立运行 agent CLI（无第二站可分摊、换站、互审）——与跨站扇出（A/B/C RPC）相对。

---

## 1. 闭环模型（问题框架）

**agent CLI 工作流闭环** = 任务卡 → 派发 → 执行 → 验收 → 产物回收 → **评审** → **回写/终结** 的完整环。D6 已闭环主干（O-19/20/21/12 全 closed），单机形态缺 **评审** 与 **韧性（续接）** 两个环节。

```
任务卡 → ROUTE → 就绪门(O-19) → opencode(stdin) → accept/golden(O-12)
   ↑                                                      │
   └──── 回写 ledger/run.json ←──────── 产物回收 ──→ ◌ 评审缺口 ◌  ← O-24 断点①
                                                  ◌ 续接缺口 ◌  ← O-24 断点②
```

## 2. 社区实践调研（2026-09-09）

### 2.1 续接（断点②）——opencode 原生已支持，落地成本最低

opencode CLI 原生提供：
- `opencode run ... --continue/-c`（续最近会话）
- `opencode run ... --session <id>/-s`（续指定会话）
- `--fork`（续时分叉，保原会话）
- Hermes opencode skill 明确封装：`process submit/poll/log` 循环 + 会话 ID 落盘续接——**这正是 O-21 ③"--session --continue 循环"的社区成熟先例**，非自研。

**落地含义**: agent-cli.ps1 远端执行体（$body）可改为"首跑 + 超时/失败后 `--session <id> --continue` 重试循环"，复用现 promptB64 管道，改动收敛在 wrapper 一处。

### 2.2 评审（断点①）——三条社区路径，单机选型明确

| 路径 | 社区依据 | 单机适配 | 评估 |
|------|---------|---------|------|
| **A. 子代理评审（review subagent）** | opencode agents：`mode: subagent/prototype`、`permission: edit deny、bash deny` 只读评审代理（官方文档 review.md 示例）；`@review` 提及调用 | ✅ 单机原生，零额外架构 | **首选**——复用 opencode agents 机制，评审=读写受限的独立 agent |
| **B. Reflection 双角色循环**（生成→评审→修订）| Self-Refine/Reflection 模式：生产者+评审者分离，cap 2-4 轮避免过度修正；futureagi 三指标（pre-vs-post delta、over-correction、cost-per-improvement）| ✅ 可叠加在 A 上，"评审不通过则修订再评" | 增强环（非独立首步）|
| **C. LLM-as-judge 独立判官** | output.ai/neuralbase：**pass/fail 优于数字评分**、judge 用不同模型（同模 judge 有自证偏差，即 A14/golden 同源教训）、rubric 显式、temperature=0、先确定性检查后 LLM | ⚠️ 单机仅 1-2 引擎，异模 judge 受限 | **golden/确定性判据已有（O-12），LLM-judge 补"事实性/语义"层** |

**单机结论**: review 首选 **opencode review subagent（路径 A）**，配 pass/fail rubric（路径 C 语义）；多轮"不通过→修订→再评"用路径 B（cap 2-3 轮）。与 golden（确定性）分层：golden=可机械判定，review subagent=可判定+语义复核。

### 2.3 备通道（断点③）——单机死锁防护

- 社区：claude code `-p` headless + `--continue`（与 opencode 同型）；Hermes 同时封装 opencode/claude-code/codex 三个 skill = 多 CLI 互为 fallback 是社区标准做法
- 单机落地：O-15 G1 不须等二期——`agent-cli task --cli claude` 最小路径（ROUTE_TABLE 补 cli 键）即可，成本约等于当前 opencode 路径的复制

### 2.4 排队/治理（断点④）——社区经验与 O-18 一致

- neuralbase：生产 judge 调用必须超时+健康检查+失败快速降级（避免挂死）——对应 D6 的 `timeout`/重试纪律
- output.ai：**先确定性检查，后 LLM-judge**——单机弱资源下优先 goldon/脚本判据，LLM 评审后才做
- futureagi：reflection 需成本护栏（round budget）——单机算力受限，评审轮数必须封顶

## 3. 单机闭环设计（O-24 P0 落地草案）

### 3.1 续接（P0-①：`--continue` 循环）✅ 已实施（2026-09-09）

```
远端执行体（$body）改造（已落地 agent-cli.ps1）：
  首跑:  opencode run -m $id < .prompt.txt
  RC≠0 时 ≤2 轮续跑（`--continue` 按 workspace 隔离续本次会话）：
     echo $CONT_B64 | base64 -d | timeout $continueTimeout opencode run --continue -m $id >> .agent-output.txt
  continue-timeout-s（front-matter）: 独立续跑预算；缺省/0 = 沿用 timeout_s
```
- **设计实证（驱动简化）**: opencode 无头 run 不打印 ses_ → 弃 session-id 解析；session 按 path 隔离 → `cd $W` 后 `--continue` 精确续本次（A 站双 run 同 session 实证）；模型名须全限定
- **全链验证**: 超时卡 RESUME[1]/[2] 出线 + cap=2 + TASK_RC=124→excode=6（timeout 语义保持）+ echo 回归零倒退
- **✅ 独立预算已实施（2026-09-09）**: 新增 front-matter 键 `continue-timeout-s`，续跑在**自身独立的 `timeout` 进程**下运行（不继承已耗尽的首跑预算）——首跑 900s 被消费后，续跑仍拿到全新完整 900s。解决了原"续跑与首跑同预算"的 V2 项。真实恢复场景实测（`dogfood-resume-recovery.md` v3，timeout_s=900 + continue-timeout-s=900）结果见手册 §2a.5（2026-09-09）。

### 3.2 评审（P0-②）——五源评审路由（2026-09-11 定案，替代 review subagent 单一路径）

**架构调整**: 评审执行者从"站上 opencode subagent 单一路径"升级为**五源路由**，核心诉求=判分模型与产出模型**严格异源**（规避自证偏差，对齐 model-eval rubric 铁律"不得用被测模型自评"）+ 主控站商业算力不占站资源。

```
评审输入（产物 + accept/golden + 卡正文 + rubric）
     │
     ├─ 评审执行者路由（按优先级 / ⑤ 为备选）：
     │    ① 主控站评审（trae / 商业 API，默认）：高并发/时间敏感；判分异源，主控侧隐藏判据承接 golden 的强隔离机制
     │    ② ultra free（B 站 opencode，Zen 网关美国托管出站，1M ctx，免费）：显式指定 review-model: ultra
     │        用于超大产物全局评审/长上下文一致性；限非敏感任务（出站）
     │    ③ DS V4 Flash（三站 RPC 分布式）：显式指定，长上下文/本地合规，非时间敏感
     │    ④ M2.7（C 站单机，CoT 24t/s）：显式指定，深度 CoT 评审，非时间敏感
     │    ⑤ 主控站 opencode CLI【备选】：主控侧 npm 装 `opencode-ai`，直连 ultra/本地模型；
     │        与 ①trae 同源、wrapper 闭环全在主控；仅当 ① 执行者不可用/需隔离时启用
     │
     → 输出结构化多级 JSON → 回写 ledger/review.json（run.json 平行键 review）
```

> **五源布局（异源 + 上下文 + 算力正交；⑤ 备选）**：
> | 源 | 形态 | ctx | 成本/算力 | 适用 | 合规 |
> |---|---|---|---|---|---|
> | ① 主控站（trae/商业） | 主控侧 | 大 | 付费/主控 | 高并发/时间敏感/默认 | 站内 |
> | ② ultra free | opencode 网关出站 | **1M** | 免费 | 超大产物/长ctx一致性 | ⚠️非敏感 |
> | ③ V4 Flash RPC | 三站分布 | 1M | 站算力 | 长ctx本地合规 | 站内 |
> | ④ M2.7 | C 单机 | 128K | 站算力 | 深度 CoT | 站内 |
> | ⑤ 主控 opencode CLI | 主控侧（备选） | 大 | 免费/主控 | ① 不可用/需执行者隔离 | 站内 |

**调度规则（负载纪律）**:
1. **默认主控站评审优先**：review 未显式指定执行者时走主控站（trae 执行或商业 API）——快、并发高、不占站算力，且判分与产出一端在主控侧、异源隔离最彻底。
2. **本地评审仅显式指定**：任务卡 front-matter `review-model` 声明（`ultra` / `rpc-v4flash` / `m27`），调度器按 alias 路由；本地/opencode 网关评审 **绝不自动拉起**——必须显式触发（仿 V4-Flash 双机加载需手动过 load-mem-gate 前例，防无预警占用资源）。
3. **load-gate 硬门（防叠加）**：本地评审（V4 RPC/M2.7）拉起前复用现有 `load-gate <GB> [host]` 检查 need+12G≤avail + 无已有进程 RSS 叠加 + RPC 三站总和预算（对齐 2026-09-08 死机事故铁律）；ultra free 走 opencode 网关出站，不占站内存，但需确保非敏感。
4. **仅显式 + 非时间敏感**：本地/网关评审不做自动调度，不干预站状态。

**分级**: 保持四级 `优秀/良好/合格/不合格`（延续 rubric 现状，不改判分口径）。

**落地改动**（全部在主控站 wrapper，站上零改动）:
- `agent-cli.ps1` 新增 `review` 子命令；复用现 ROUTE/attach/prompt/产物回收链路
- front-matter 新增 `review-model` 键（alias → 执行者路由）
- 商业 API 调用层（endpoint/key 待注入，见 O-16 缺口登记）
- 输出契约: `{task, run_id, output:{score(四级), pass, evidence[], flags_hit[], conclusion}, metadata:{judge_model, temperature:0, prompt_hash}}`

**✅ 落地实证（2026-09-12，O-16 closed）**:
- **review 子命令端到端落盘**: JUDGE_TABLE 五源路由 + `Resolve-Judge/Invoke-Review/Invoke-Judge*/ConvertFrom-JudgeOutput/Build-JudgePrompt/Get-ReviewRunDir` + 顶层 `review` 分发分支 + 资源 `review/rubric-4level.txt`/`judge-prompt.tmpl`，全部在主控 `agent-cli.ps1`，站上零改动。
- **实测 juge=ultra（② egress B）**: 真实生成 `review.json`，字段齐全（四级 score / pass / evidence[] 五维各含 hit+reasoning / flags_hit[] / conclusion + metadata: temperature:0 / seed / prompt_hash / elapsed_s / review_gate / retries）。
- **advisory 语义验证**: score=不合格 仍 `exit 0`（不阻断任务）；幂等（已有 review 无 overwrite → exit 0 复用）+ `--overwrite` 强制重审均通过。
- **韧性**: JSON 解析失败自动重试 1 次成功（retries=1，对齐 theneuralbase「超时+重试+快速降级」）。
- **敏感门**: local-only + egress judge(`ultra`) → `exit 4`。
- **社区差距修正（G1-G5）**: ⑤ main judge 由 ENV `REVIEW_MAIN_MODEL`（默认站内 `cluster-litellm/nemotron`，非出站 ultra，保 local-only 安全）；CoT judge（③④）`max_tokens=8000`、commercial/ultra=2500、main=4000；评审调用 retry≤2 + 记 `metadata.retries`；产物头尾截断（前 20K + 后 20K）；commercial 默认模型不再臆造（缺 `REVIEW_COMMERCIAL_MODEL` 报 `JUDGE_UNREADY`）。
- **静态回归**: `.ps1` UTF-8 BOM 恢复、AST errors=0、既有 `route`/`task` 命令零倒退。
- 实现详见 [review-ring-refinement-O16.md](file:///d:/RPC/.trae/documents/review-ring-refinement-O16.md)。
- 与 spec_workflow "异基座复审"对接：review 输出可作为复审机器基线

### 3.3 分层判据（金字塔）

| 层 | 判据 | 机制 | 来源 |
|----|------|------|------|
| L1 确定性 | accept pytest / golden（O-12）| 脚本 | 已落地 |
| L2 评审路由 | 三源（商业 API 默认 / V4 RPC 显式 / M2.7 显式），rubric 只读评审，四级判分 | 主控 wrapper + 商业/本地引擎 | **本 O-24 P0** |
| L3 修订循环 | 不通过 → 修订 → 再评（cap 2-3）| Reflection | 增强 |
| L4 人工/异基座 | spec_workflow 复审 | 会话 | 现有 |

## 4. 落地风险与护栏

| 风险 | 护栏 |
|------|------|
| review subagent 与主模型同引擎 → 自证偏差 | 评审 agent 固定另一引擎（单机时仍用 golden 判据兜底确定性部分）|
| 续接循环死循环（反复失败）| `--continue` retry 上限 2，超限转人工/标记 REVIEW_NEEDED |
| 评审成本叠加 | L2 round budget=1（单轮评审），L3 才额外轮 |
| 评审误判（过审/错杀）| review.json 留存 + 可人工覆写状态 |

## 5. 结论

- **P0 两项均有社区成熟先例，非自研**：续接=opencode `--continue`（Hermes 已封装），评审=opencode review subagent（官方 agents 机制）
- **落地成本**：wrapper 一处改动（$body 续接循环）+ 1 子命令（review）+ 1 agent 配置（review.md）——不引入新框架
- **O-24 关闭判据保持**：① review 落地回写 ledger + ② --continue 超时续跑闭环 即主体闭环

## 6. 来源

- opencode 官方 CLI/Agents 文档（--continue/--session/--fork、subagent review.md 示例）
- Hermes Agent opencode skill（会话续接 submit/poll/log 循环先例）
- Self-Refine / Reflection 模式（juejin Rust 实现、zhongzhuzhou 技术综述）
- futureagi reflection 三指标（pre-vs-post delta/over-correction/cost-per-improvement）
- output.ai LLM-as-judge best practices（pass/fail>数字、同模 judge 陷阱、确定性检查先行）
- theneuralbase LLM-as-judge in production（超时/健康检查/降级）
- 本集群实证：O-19/20/21/12 闭环记录、A14 golden 教训