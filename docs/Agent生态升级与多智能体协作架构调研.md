# Agent 生态升级与多智能体协作架构调研

> 日期: 2026-09-01 · 2026-09-02 补充上下文管理选型 (§6) + Trae 生态盘点与原生对比 (§7) · 作者: Scott (鹏) + Trae
> 状态: **调研完成, 待用户裁决执行范围** · 附录 A/B/C 归档三份 subagent 检索原始输出 (依据可追溯), 附录 D 为正文↔附录索引表
> 前置: [ClaudeCode本地集群与子代理框架分析.md](ClaudeCode本地集群与子代理框架分析.md) (阶段2 GO)、[双端点部署与opencode混合框架调研.md](双端点部署与opencode混合框架调研.md) (双端点已落地)
> 配套: [spec/vulkan-version-control/](../spec/vulkan-version-control/) 五阶段 spec 模板链

***

## 0. 两个问题的答案速览

| 问题                     | 答案                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 插件生态是否需要更新?            | **是, 且空间巨大**: 两站 4 个 agent 全部裸装 (无 MCP/skills/subagents/自定义 agents)。关键事实: **Skills/MCP/subagents 全是 CLI 客户端机制, 与后端无关** — 经 ANTHROPIC\_BASE\_URL 指向本地 nemotron/gpt-oss 后整套生态完全可用 (tool-use 已 PASS 实锤)。opencode 1.18+ 更是**直接读** **`.claude/skills/`**, 一份 skills 两 CLI 零成本共用                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| 4 agent × trae 如何高效协作? | **五层循环**: trae 规划(生成 spec) → 派发(SSH headless 任务卡) → 本地执行(检索/编码/编译/测试) → 执行锚定验证(编译器+测试+数值输出, 零 LLM 成本拦幻觉) → trae ADD 审计回环。成本分配: 本地 80% 流量(无限 token), trae 20% 高价值轮次(规划+审计)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| 上下文管理装什么? (§6)         | **零安装先行**: claude code 内置 CLAUDE.md/Auto Memory//compact + opencode `limit.context` 配置即覆盖 80% 需求; 插件层 **claude-mem** (双 CLI 通吃) 与 **opencode-codex-memory** (纯本地) 起步; ⚠ claude code **窗口假设风险** (推断待实测) → 长会话默认走 opencode                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| Trae 已装生态可迁移吗? (§7)    | **三层策略 (§7.5 终裁)**: **原生优先** — obra/superpowers v6.3.0 (Trae 工程链 6 件本就是它的旧快照) + anthropics document-skills 直接装原生不迁; **定制迁移** — math-finance-reasoning / research-\* 学术编排链 / paper-lookup / what-if-oracle (原生无等价); **Trae 兜底** — C 类检索留主控站, 插件层 8 个宿主绑定弃                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| 审计任务有现成插件吗? (§8)       | **无单一对口件, 但四层可组合**: 官方 citation-verify prompt 模式 (E2) + 现成 skill (deglaze 审"声称完成"/paper-review\.skill 引用验证) + **已装 ARS 的三层引用锚点被重新发现** + 跨模型对抗审查 (adversarial-review 架构) → 本集群 nemotron↔gpt-oss 双端点互审是天然免费实现; 断言-依据-信息源-逻辑链规范建议**自制成 assertion-audit skill** (§7.6 手工审计的技能化)。**§8.5 二轮修正**: opencode 原生生态有 **ARS 移植版** (claim 级审计两站原生可跑, 不再依赖 Trae 兜底) + CiteAgent/oy/omre/adlc/gemini-search 六件盘点 — 自制 skill 借 hook 强制化路径与 FNR/FPR 校准验收。**§8.6 三轮**: 两侧插件层均不稳 — opencode plugin API 多次 patch 版内静默破坏 (`api.command.*` 移除/V2 hook 静默失效致父会话挂死), claude code marketplace 自动更新会静默清空插件 → **A 类纯 prompt skill 战略价值再确认, Phase 2 hook 化降级为失效后备**; 新增约束: opencode 锁版本、预装系统 ripgrep。**§8.7 排幻觉审计**: 六仓重抓 README 逐断言核验 — 2 处修正 (adlc prosecutor 实为证据记录器/收敛规则为两连干轮+≥3 lens), 其余全部实锤; 增量发现: adlc trust-root tier 跨模型审查强制 = 站间互审外部同构实证。**§8.8 二轮复核**: 11 个载荷 URL 逐一直抓 — 10 全实锤 + 1 根因修正 (#20623 实为 loader 重构破坏 NAPI 解析) + 1 元断言修正 (首轮"E1 直抓"声明系夸大); #35641 根因补强为 #30067 O(N²) 长循环退化 (nemotron 长会话直接相关); #41701 官方标 invalid 未认领 — 更支持绕开 marketplace。**§8.9 三轮补验**: 7 个 E2 残留载荷直抓 7/7 实锤 (1 版本修正: Effect v1.4.4+); #30067 修复 PR #42150 在途可纳入选型; **#24115 复现用例 = claude-mem 本尊** (D5 T5 试点须验 hooks 无双触发); #31250/#34573/#31777/#24115 全部 closed as not planned — claude code hooks 层上游零认领, "Phase 1 prompt 契约为准"升级为不可回避约束 |

***

## 1. 现状盘点 (2026-09-01 实测)

### 1.1 两站 4 agent 版本与生态

| 站           | Agent       | 版本                   | MCP | Skills | 自定义 Agents | 诊断                                |
| ----------- | ----------- | -------------------- | --- | ------ | ---------- | --------------------------------- |
| A (NEX)     | opencode    | **1.18.25** (最新)     | ❌   | ❌      | ❌          | 裸装                                |
| A (NEX)     | claude code | 2.1.220              | ❌   | ❌      | ❌          | 裸装, 有 plugins 目录(marketplaces)未启用 |
| B (GTR-Pro) | opencode    | **1.18.9** (落后 16 版) | ❌   | ❌      | ❌          | 裸装, plugin SDK 1.17.11            |
| B (GTR-Pro) | claude code | 2.1.252              | ❌   | ❌      | ❌          | 裸装, \~/.claude 只有 theme 配置        |

### 1.2 后端能力 (已验证)

- nemotron (B 站单机 20.9 t/s) / gpt-oss (A 站 58-64 t/s) 双端点 E2E 全通

- claudecode 经 LiteLLM anthropic 转换层 tool-use **PASS** (stats.cpp 写码→编译→测试闭环) — 这是 skills 可用的充分条件

- opencode 双 provider (cluster-local + cluster-litellm) PONG 验证通过

### 1.3 主控站既有方法论资产

- spec 五阶段模板链: RESEARCH → DESIGN → IMPLEMENTATION → CHECKLIST → ADR ([模板](../spec/vulkan-version-control/DESIGN_TEMPLATE.md))

- CHECKLIST.md 本质就是文档间对齐审计 (§1.1-1.4 RESEARCH↔DESIGN↔IMPL 交叉验收) — ADD 审计的雏形

- trae 侧大量专业 skill 可作为蓝本 (statistical-analysis / peer-review / deep-research 等)

***

## 2. 生态调研核心发现

### 2.1 Skills 在本地模型后端完全可用 (关键结论)

**原理**: skills/subagents/hooks/MCP 全部是 Claude Code CLI **客户端侧机制** — skill 正文由 CLI 本地拼装进请求, hooks 本地执行, MCP 本地拉起进程, 与后端是谁无关。只要后端说 Anthropic Messages API (LiteLLM 转换层已实现), 整套扩展生态即可用。

已验证的社区后端: Ollama / LM Studio / llama.cpp / DeepSeek / GLM / Kimi / OpenRouter — **llama.cpp 原生支持已在被广泛复制的方案列表里**。

**已知限制 (120B 本地模型适配)**:

1. 模型名映射: 需 `ANTHROPIC_DEFAULT_SONNET_MODEL` 等环境变量指向本地模型名
2. skill 自动触发依赖指令遵循 — 小模型对 description 语义匹配弱 → **关键 skill 用** **`/`** **手动触发或** **`disable-model-invocation`**
3. 内置 WebSearch 是 Anthropic 服务端工具, 本地后端不可用 → **用 web-search 类 MCP 替代** (MCP 工具本地执行, 不受后端影响)
4. 无 prompt caching → 长会话每轮重编码 (本地免费, 可接受)

### 2.2 opencode 对 Claude Code 生态的兼容性 (第一梯队)

| 资产                | 复用成本    | 说明                                                              |
| ----------------- | ------- | --------------------------------------------------------------- |
| `.claude/skills/` | **零成本** | opencode 原生扫描 `.claude/skills/*/SKILL.md` 与 `~/.claude/skills/` |
| CLAUDE.md         | 零成本     | 无 AGENTS.md 时自动 fallback 读 CLAUDE.md                            |
| MCP server 本体     | 一次性转换   | server 复用, 但 `.mcp.json` → `opencode.json` 的 `mcp` 字段需手改        |
| `.claude/agents/` | 轻量搬移    | frontmatter 字段调整 (tools CSV → 权限对象, model 名格式)                  |
| Hooks             | 需重写     | settings.json 范式 → JS/TS 插件范式                                   |

**战略含义**: 以 `.claude/` 目录为**单一事实源**, claudecode 直接用, opencode 兼容读取 — 两 CLI 一套资产。

### 2.3 社区多 agent 降幻觉十大模式 (精选与本集群相关的)

| #  | 模式                              | 核心机制                                      | 本集群映射                                                  |
| -- | ------------------------------- | ----------------------------------------- | ------------------------------------------------------ |
| 1  | **Orchestrator-Worker**         | 强模型规划 + 隔离上下文弱模型并行 + 结构化 artifact 回传      | trae=orchestrator, 本地=worker                           |
| 2  | **Planner-Generator-Evaluator** | 生成者不验证自己                                  | trae 审计本地产出                                            |
| 3  | **Draft-Verify 级联**             | 便宜模型起草 → 验证门 → 贵模型接受/增强                   | PayPal 生产: 88.8% 请求停在草稿层, 省 45.8% 成本且质量 100% vs 原生 95% |
| 4  | **Spec 门控流水线**                  | Constitution→Specify→Plan→Tasks→Implement | spec\_workflow 已有, 补 Constitution 层                    |
| 5  | **Rigor 拦截器** (Curie)           | 动作级拦截→验证→转发                               | 3.4x 超最强基线                                             |
| 6  | **证据外部锚定** (Co-Scientist)       | 数值声明 vs 执行日志比对                            | 幻觉率 4% (Nature 2026); **回测场景是社区空白 → 本集群的机会**           |
| 7  | **对抗辩论 + Elo 排名**               | 多空辩论消除确认偏误                                | nemotron vs gpt-oss 交叉审                                |
| 8  | **否决权风控层** (TradingAgents)      | 风控 agent 一等公民可否决                          | 量化场景治理                                                 |
| 9  | **验证门 fallback 链**              | 超时/schema 失败/低置信 → 升级                     | 本地失败 → trae 接管                                         |
| 10 | **记忆增强迭代**                      | 历史决策向量化检索                                 | topics.md/project\_memory 人工版已有                        |

**社区共识三支柱**: ① 幻觉根源是"未锁定的决策" (Qodo: 给足上下文幻觉 54%→16%); ② 读密集任务 fan-out 并行, 写密集任务单线程; ③ \~80% 真实请求简单到本地模型即可处理。

**ADD 审计印证**: 社区 "AI Decision Audit" (unhallucinate 项目) 与 Scott 的 ADD 审计方法论**独立收敛** — 枚举 AI 需要做的每个决策, 验证答案是否存在于 spec 中, 不存在则必然被幻觉。

***

## 3. 问题一: 插件生态更新清单

### 3.1 版本更新

| 项                             | 动作                 | 优先级                                        |
| ----------------------------- | ------------------ | ------------------------------------------ |
| B 站 opencode 1.18.9 → 1.18.25 | `opencode upgrade` | P0 (子代理失败可恢复/v1.18.20、深度限制/v1.18.2 都是协作刚需) |
| A 站 claude code 2.1.220 → 最新  | npm 全局更新           | P1                                         |
| B 站 claude code 2.1.252       | 已近最新               | —                                          |

### 3.2 Skills 部署 (单一事实源 `~/.claude/skills/`, 两站 git 同步)

按 Scott 场景筛选 (宁缺毋滥, 本地 120B 的 skill 自动触发弱 → 手动 `/` 调用为主):

| Skill             | 来源                | 场景   | 理由                                                                  |
| ----------------- | ----------------- | ---- | ------------------------------------------------------------------- |
| `code-review`     | claude code 内置    | 编程   | 已有, 零成本                                                             |
| `superpowers` 子集  | obra/superpowers  | 编程   | 挑 TDD + systematic-debugging 两个, 给本地 agent 注入工程纪律; 全套 14 个对 120B 过重 |
| `quant-analysis`  | 定制 (参考 quant-mcp) | 金融计量 | Sharpe/VaR/回测/Greeks 的操作规范                                          |
| `paper-search`    | 定制 (MCP 配套 skill) | 学术推理 | 教 agent "该怎么用检索工具" (Anthropic 官方建议 MCP 配 skill)                     |
| `spec-compliance` | 定制                | 全场景  | ADD 审计的客户端形态: 枚举决策→比对 spec                                          |

**定制 skill 示例** (`~/.claude/skills/spec-compliance/SKILL.md`):

```markdown
---
name: spec-compliance
description: Audit work output against spec before delivery. Use when a task
  card specifies a spec_ref, or before marking any task complete.
allowed-tools: Read, Grep, Glob
---
## Procedure
1. Read the task card (JSON): task_id, spec_ref, acceptance_criteria
2. Enumerate every decision the implementation made
3. For each decision, locate its answer in the spec
4. Classify: ANCHORED (in spec) / ASSUMED (not in spec)
5. Output verdict table; any ASSUMED decision = FAIL with rationale
```

### 3.3 MCP servers (本地 stdio, 不依赖外网 API key 的优先)

| MCP              | 安装                             | 场景    | 落点                                                    |
| ---------------- | ------------------------------ | ----- | ----------------------------------------------------- |
| **duckdb**       | `uvx mcp-server-duckdb`        | 金融计量  | 直连 factor\_db.duckdb — **最高对口度**                      |
| **quant-mcp**    | `uvx quant-mcp`                | 金融数学  | 20 工具: Sharpe/VaR/CVaR/回测/HMM/Greeks/Fama-French/组合优化 |
| **paper-search** | `uvx paper-search-mcp`         | 学术推理  | arXiv/PubMed/Semantic Scholar/CrossRef                |
| **context7**     | `npx -y @upstash/context7-mcp` | 编程+计量 | statsmodels/PyTorch 等库文档实时拉取                          |
| filesystem       | 不装                             | —     | CLI 已有文件工具, 冗余                                        |

**opencode 配置** (`opencode.jsonc` 增加):

```jsonc
{
  "mcp": {
    "duckdb": {
      "type": "local",
      "command": ["uvx", "mcp-server-duckdb", "--db-path", "/data/factor_db.duckdb"]
    },
    "quant": {
      "type": "local",
      "command": ["uvx", "quant-mcp"]
    },
    "paper-search": {
      "type": "local",
      "command": ["uvx", "paper-search-mcp"]
    }
  }
}
```

**claudecode 配置**: `claude mcp add duckdb -- uvx mcp-server-duckdb --db-path /data/factor_db.duckdb` (同 server 两 CLI 复用)。

### 3.4 自定义 Agents (`.claude/agents/`, 定向用途)

| Agent             | 模型 | 工具白名单                             | 职责                          |
| ----------------- | -- | --------------------------------- | --------------------------- |
| `research-worker` | 本地 | Read/Grep/Glob + paper-search MCP | 文献检索/代码考古, 只读               |
| `code-executor`   | 本地 | 全工具                               | 编码/编译/测试闭环 (stats.cpp 模式复制) |
| `quant-analyst`   | 本地 | duckdb + quant MCP                | 数据查询/指标计算                   |
| `auditor`         | 本地 | 只读                                | 初审: 结构化验收 (终审留 trae)        |

### 3.5 不建议的项

- ~~Agent Teams / tmux 多会话~~ — 主控站单人操作, 收益低于复杂度

- ~~ARIS 全套学术流水线~~ — 重, 且与 trae 侧 deep-research 重复

- ~~Hooks 体系~~ — opencode 侧需 JS 插件重写, 维护税 > 收益, 等 V2 稳定再说

***

## 4. 问题二: 4 agent × trae 协作架构

### 4.1 当前交互方式 (事实)

```
主控站 trae (付费 GLM, 深度规划)
   │ SSH (paramiko, 免密已通) + headless CLI
   ├── A 站: claude -p / opencode run  → gpt-oss (:8080) / 免费模型
   └── B 站: claude -p / opencode run  → nemotron (:8080 经 LiteLLM :4000)
```

交互本质: **trae 生成任务文本 → SSH 派发 → 本地 agent 执行 → stdout 回传 → trae 读结果**。已跑通但无协议 — 任务交接是自由文本, 这正是幻觉和传话损耗的入口。

### 4.2 目标架构: 五层循环 (Spec-Anchored Loop)

```
┌─────────────────────────────────────────────────────────┐
│ L1 规划层  trae (付费, ~20% 轮次)                          │
│    需求 → RESEARCH → DESIGN → 任务卡切片                   │
│    产出: TASKS.md (含 Constitution: 不可协商原则)           │
├─────────────────────────────────────────────────────────┤
│ L2 派发层  主控站脚本 (SSH headless)                       │
│    任务卡 = JSON: {task_id, spec_ref, acceptance,          │
│                    artifact_path, model, agent}           │
│    路由: 检索→opencode免费模型 / 编码→claudecode本地模型      │
├─────────────────────────────────────────────────────────┤
│ L3 执行层  本地 4 agent (无限 token, ~80% 流量)             │
│    A: gpt-oss (快, 58 t/s) + opencode 免费模型            │
│    B: nemotron (深, 1M ctx) + opencode 免费模型           │
│    自修复循环: 编译失败→读错误→改→重试 (本地免费无限轮)         │
├─────────────────────────────────────────────────────────┤
│ L4 锚定层  零 LLM 成本验证 (编译器/测试/数值输出)             │
│    硬门: 编译过? 测试绿? 数值对? — 不过不上报                │
│    (Co-Scientist 模式: 数值声明 vs 执行日志强制比对)          │
├─────────────────────────────────────────────────────────┤
│ L5 审计层  trae ADD 审计 (~高价值轮次)                     │
│    枚举实现决策 → 比对 spec → ANCHORED/ASSUMED 判定         │
│    PASS → git merge; FAIL → patch 任务卡重派 L2            │
└─────────────────────────────────────────────────────────┘
```

### 4.3 降幻觉五机制 (逐条落地)

| 机制          | 社区证据                    | 本集群落地                                 |
| ----------- | ----------------------- | ------------------------------------- |
| ① spec 锁定决策 | Qodo: 54%→16%           | L1 的 Constitution + 任务卡 acceptance 字段 |
| ② 生成者不验证自己  | RLM-Cascade 质量 100%>95% | 本地只执行, trae 只审计, 角色永不分饰               |
| ③ 结构化交接     | 消灭传话效应                  | 任务卡 JSON + artifact 落盘 (非 stdout 口信)  |
| ④ 执行锚定      | Co-Scientist 幻觉 4%      | L4 硬门: 编译/测试/数值, 零 LLM 成本             |
| ⑤ 上下文隔离     | Anthropic: 子agent=智能过滤器 | 本地 agent 只拿任务卡, 不拿全局上下文               |

### 4.4 成本与能力分工

| 资源            | 角色                                       | 占比                   |
| ------------- | ---------------------------------------- | -------------------- |
| trae 付费模型     | 规划 / ADD 审计 / 最终合成 / 失败兜底 (fallback 链终点) | \~20% 轮次, 100% 高价值轮次 |
| 本地 4 agent    | 信息检索 / 多轮试错 / 编码执行 / 数据处理 / 初审           | \~80% 轮次, 无限 token   |
| 编译器+测试+DuckDB | 锚定验证                                     | 0 LLM 成本             |

### 4.5 实施路线

**P0 (立即, \~1h)**: B 站 opencode 升级 + `.claude/skills/` 共享骨架 + duckdb MCP (最高对口) + `research-worker`/`code-executor` 两个 agent 定义
**P1 (半天)**: 任务卡 JSON 协议 + 派发脚本 (PowerShell/bash) + `spec-compliance` skill + 端到端走一个真实任务
**P2 (可选)**: quant-mcp / paper-search MCP / 对抗辩论双模型交叉审 / 回测数值锚定工具 (社区空白 = 论文素材)

***

## 5. 风险与边界

1. **本地模型 skill 自动触发弱**: 全部关键 skill 设 `disable-model-invocation` 或在任务卡 prompt 里显式 `/skill-name` 调用
2. **MCP 进程开销**: 每个 opencode/claudecode 会话拉起 MCP 子进程 — duckdb 文件锁与 LM Studio 无关, 但并发查询注意 duckdb 单写者限制
3. **免费模型配额波动**: opencode 免费模型是外部服务, 任务路由脚本需有 fallback 到本地端点的分支
4. **spec 维护税**: 按海拔采纳 — 跨会话/跨 agent 的工作必须 spec 化, 一行修改跳过全部仪式 (社区批评 SDD "Waterfall in a Hoodie" 的解药)

***

## 6. 补充调研: 上下文管理选型 (2026-09-02)

> 背景: §3/§4 覆盖了 Skills/MCP/subagents, 但**上下文管理** (窗口预算/压缩时机/跨会话记忆) 是遗漏项 — 恰是 nemotron (conf 128k) / gpt-oss (conf 32k) 这类**非 200k 级本地模型**跑长 agent 任务的核心瓶颈。多 agent 工作流 token 量是普通对话的 \~15x (NVIDIA 引 Anthropic 工程博客), 不管理上下文 = 会话中期质量崩塌 + 网关 400。

### 6.1 结论速览

1. **先配置后插件**: 两个 CLI 的内置机制 (opencode `limit.context` + auto-compact; claude code CLAUDE.md + /compact 纪律) 零安装即可解决"窗口不知何时满"的问题 — 这是 P0
2. **插件二选一起步**: claude-mem (双 CLI 通吃, 生态最大) 或 opencode-codex-memory (纯本地无 worker) — 解决"跨会话记忆"
3. **claude code 窗口假设风险** (推断待实测): 若其按官方 \~200k 计占用, auto-compact 晚于本地 131k/32k 上限 → 长会话默认 opencode, claude code 做短任务 (验证法见 §6.4)

### 6.2 内置机制盘点 (零安装, P0)

**opencode** (`~/.config/opencode/opencode.jsonc`):

```jsonc
{
  // ① provider 声明真实窗口 — opencode 对自定义端点不知 ctx 上限,
  //    不声明则对话无界增长直到后端 400 (GLM5 社区案例, bswen 博客)
  "provider": {
    "cluster-litellm": {
      "models": {
        "nemotron": { "limit": { "context": 120000, "output": 8192 } },
        "gpt-oss":   { "limit": { "context": 30000,  "output": 8192 } }
      }
    }
  },
  // ② 压缩策略: 满窗自动 compact (默认开) + 修剪旧工具输出 + 预留余量
  "compaction": { "auto": true, "prune": true, "reserved": 20000 }
}
```

> ⚠ **格式待站上验证 (审计发现)**: 嵌套 `limit.context` 写法取自 opencode 官方 config schema 方向的第三方整理 (yahtoo 附录 B.1), 而 GLM5 案例 (bswen) 用的是 `"models": {"glm-5": {"context": 95000}}` 平铺式 — 两来源**冲突**, 上站时以 `opencode.ai/config.json` schema 或实际生效为准。`prune` 默认值两来源也不一致 (官方文档片段说 false, 第三方整理说 true) — 反正显式写 true 即无歧义。

- context 值故意设在 conf CTX 之下 (120000 < 131072 / 30000 < 32768), 给输出留余量 — auto-compact 会在触线前正确触发

- `prune: true` 修剪旧工具输出 (agent 会话大头是 Read/Bash 输出), 对 32k 的 gpt-oss 路由尤其关键

- 环境变量后备: `OPENCODE_DISABLE_AUTOCOMPACT` / `OPENCODE_DISABLE_PRUNE` 可临时关 (第三方文档来源, 同待验证)

**claude code**:

| 机制                     | 说明                                                                                                         |
| ---------------------- | ---------------------------------------------------------------------------------------------------------- |
| CLAUDE.md 层级注入         | 规则类上下文进 system prompt 稳定区 (利缓存); 手册铁律/spec 引用放这里                                                           |
| Auto Memory (v2.1.59+) | `~/.claude/projects/<proj>/memory/MEMORY.md` 前 200 行 (或 25KB) 每会话自动注入, 免装插件的半持久记忆 ⚠ 单一博客来源 (CSDN), 细节数字待实测 |
| `/context`             | 占用可视化 — 大任务前先看余量, <30% 先压缩                                                                                 |
| `/compact <保留指令>`      | **60-70% 时手动压, 远优于 \~92% 触发的被动 auto** (被挤压时总结质量差、丢文件路径/行号); 带"保留已改文件路径+当前失败+架构决策"指令质量翻倍                    |
| `/rewind` (Esc+Esc)    | 检查点回溯, 上下文走错路时回滚                                                                                           |
| subagents (§3.4)       | 上下文隔离 — 大输出子任务下放 subagent, 主会话只收结论                                                                         |

### 6.3 插件选型表 (跨会话记忆层)

| 插件                              | 装                                                                                                                                                  | 机制                                                                                                                                                                                                                                                                                 | 本集群适配判断                                                                                                                                                              |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **claude-mem** (首选)             | claude code: `/plugin marketplace add thedotmack/claude-mem` 或 `npx claude-mem install`; **opencode:** **`npx claude-mem install --ide opencode`** | 5 生命周期 hooks (SessionStart/PostToolUse/Stop...) + Bun worker (端口 `37700 + (uid % 100)` 官方式, 每用户不同 — 第三方文章的 37777 只是单用户实例) + SQLite/FTS5 (+可选 Chroma 向量), 会话结束自动压缩观察→摘要, 新会话注入近 10 次 session 上下文; Web UI 同 worker 端口; stars 数两来源矛盾 (72.4K\@2026-05 vs 89K+\@2026-03, 取保守口径"70k+ 级") | 双 CLI 一套记忆 — 与"`.claude/` 单一事实源"战略同构。⚠ worker 的摘要调用走 Claude Agent SDK → 需实测经 ANTHROPIC\_BASE\_URL (LiteLLM) 指向本地模型时压缩质量 (120B 压缩够用, 但未验证); 记忆注入量对 32k 的 gpt-oss 路由偏重 |
| **opencode-codex-memory** (纯本地) | opencode.json 一行 `"plugin": ["opencode-codex-memory@0.6.5"]` (版本必须钉死, opencode 不自动重解析)                                                             | OpenAI Codex 记忆系统移植: 会话闲置 6h 后**用 opencode 已配置的模型**后台提取→合并, markdown+SQLite 全本地, 无外部服务无 worker                                                                                                                                                                                     | 全链路走本地端点 — 适配性最稳; 需 opencode ≥1.18 (B 站 1.18.9 满足但建议先升 1.18.25); 后台提取调用计入网关 rpm=30 (D1), 低频不冲突                                                                       |
| four-opencode-memory (备选)       | `"plugin": ["@four-bytes/four-opencode-memory"]`                                                                                                   | 零依赖纯 Markdown (MEMORY.md + 每日 diary), session idle 自动捕获                                                                                                                                                                                                                            | 最保守 (无 LLM 调用, grep 检索); 记忆质量靠模板不靠模型 — 适合先验证工作流                                                                                                                      |
| opencode-dcp (进阶)               | `opencode plugin @tarquinen/opencode-dcp@latest --global`                                                                                          | 动态修剪: compress 作为工具交给模型自选时机 (比满窗 compact 聪明), 重复工具调用去重 + 错误调用输入清理                                                                                                                                                                                                                  | "小 ctx 模型需调低 min/maxContextLimit" 官方注记正对本集群; 与 codex-memory 功能重叠, 二选一                                                                                                |
| claude-max-context (模式参考)       | 不整装                                                                                                                                                | hooks 组合: session-start 注入 HANDOFF/MEMORY/PROJECT\_MAP + pre-compact 强制 7 点保留清单 (任务态/决策/已试失败法/文件/阻塞)                                                                                                                                                                               | 借鉴其 **PreCompact hook 保留清单** 模式, 手写轻量版 (\~20 行) 挂 claude code — 与 spec 工作流语义天然对齐                                                                                     |

**选型裁定**: B 站先装 **opencode-codex-memory** (纯本地零风险跑通跨会话记忆) → 验证后 A/B 两站 claude-mem 双 CLI 试点 (worker→LiteLLM 路径实测是门); dcp/four 视前者不足再上。

### 6.4 模型侧适配: nemotron vs gpt-oss 分工

| 维度                    | nemotron (B 站主力)                                                                    | gpt-oss (A 站速度档)                                                               |
| --------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| 长上下文能力 (官方 RULER-100) | **@256k 96.3 / @1M 91.75** — 长文专精                                                   | @256k 52.3 / @1M 22.3 — 长文弱                                                    |
| agentic 定位            | 官方 "Best For: Agentic workflows, tool use, RAG"; SWE-Bench (OpenCode harness) 59.20 | harmony 原生工具链; SWE-Bench (OpenHands) 41.9                                      |
| conf CTX              | 131072 保持 (KV 仅 1G, results-ledger 实证)                                              | 32768 保持 — **不建议为长会话扩 ctx**: 能力不支持 + 长链降速 (\~16k→32k 同级 MoE 实测 -30%)           |
| 采样                    | **官方: temperature=1.0 + top\_p=0.95 全任务通用 (含 tool call)** — agent 配置勿用 0.x 编码默认值    | 同左; reasoning effort **medium+** (low 几乎无推理)                                   |
| 长工具链注意                | thinking 可开关 (chat template)                                                        | **CoT passback**: 5+ 轮工具链必须回传 reasoning 内容, 否则质量显著退化 — LiteLLM 转换层已透传, 但换链路时复查 |

**claude code 窗口假设风险 (本集群特有, ⚠ 推断非实证)**: 机制已知部分 — claude code 的 auto-compact 按其认知的模型窗口百分比触发 (社区博客称 \~92%), 且其窗口认知来自 Anthropic 官方模型名映射。**推断链** (未实测): 后端经 ANTHROPIC\_BASE\_URL 换成 nemotron/gpt-oss 后, 若 claude code 仍按官方模型默认 \~200k 计算占用, 则 auto-compact 阈值 (92% × 200k ≈ 184k) 晚于真实上限 131k/32k → 不压缩直接后端 400/截断。**验证法 (上站 5min)**: 加载 gpt-oss 后在 claude code 里跑 `/context` 看它显示的窗口基数是 200k 还是读到了 conf 值 — 若显示 200k 则陷阱成立。**缓解三件套 (无论陷阱成立与否均无害)**: ① 长会话/大 codebase 任务默认 opencode (limit.context 声明后 auto-compact 语义明确); ② claude code 用于短平快 + 定期 `/context` + 60-70% 手动 `/compact`; ③ 任务切换 `/clear`, 靠 memory 层 (6.3) 而非会话内历史续命。

### 6.5 落地批次 (并入 §4.5 路线)

- **P0 (纯配置, \~30min)**: 两站 opencode provider 加 `limit.context` (nemotron 120000 / gpt-oss 30000) + `compaction.prune: true`; claude code 侧写 CLAUDE.md 骨架 (铁律+手册引用)

- **P1**: B 站 opencode-codex-memory (纯本地试点); claude code 手写 PreCompact 保留清单 hook (\~20 行)

- **P2**: claude-mem 双 CLI (worker→LiteLLM 实测); 不足再评估 dcp/four-opencode-memory

**本节参考**: [Nemotron-3-Super model card (build.nvidia.com)](https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b/modelcard) · [NVIDIA blog: Nemotron 3 Super for Agentic AI](https://blogs.nvidia.com/blog/nemotron-3-super-agentic-ai/) · [claude-mem (GitHub)](https://github.com/thedotmack/claude-mem) / [docs.claude-mem.ai](https://docs.claude-mem.ai/introduction) · [opencode-codex-memory (npm)](https://www.npmjs.com/package/opencode-codex-memory) · [four-opencode-memory (GitHub)](https://github.com/four-bytes/four-opencode-memory) · [opencode-dcp (GitHub)](https://github.com/Opencode-DCP/opencode-dynamic-context-pruning) · [claude-max-context (GitHub)](https://github.com/pkmdev-sec/claude-max-context) · [gpt-oss 本地 Codex CLI 指南](https://github.com/ivanopcode/gpt-oss-local-codex-guide) · [opencode auto-compact 实测 (bswen)](https://docs.bswen.com/blog/2026-03-21-opencode-auto-compact-config/) · [OpenAI gpt-oss model card](https://cdn.openai.com/pdf/419b6906-9da6-406c-a19d-1bb078ac7637/oai_gpt-oss_model_card.pdf)

***

## 7. 补充盘点: Trae 已装生态迁移评估 (2026-09-02)

> 背景: §3.2 的技能清单是"从社区挑 5 个"的增量视角; 本节改为**全量盘点主控站 Trae 已装生态**, 评估哪些可直接搬上集群两站 claude code / opencode。盘点方法: 磁盘 LS/Glob 实测 + 抽读 5 个代表技能 frontmatter 定依赖形态 (非逐个通读全部正文, 分类以描述+抽查为据)。

### 7.1 盘点事实 (主控站磁盘实测)

| 层       | 位置                                                                  | 规模                 | 形态                                                                                                                                                  | 可迁移性                                                                                     |
| ------- | ------------------------------------------------------------------- | ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| **技能层** | `c:\Users\Peng\.trae-cn\skills\<name>\SKILL.md`                     | **213 个** (目录计数实测) | 标准 SKILL.md (name/description frontmatter + 正文; 部分带 references/scripts/ 子目录 = 渐进披露)                                                                 | **与 claude code 技能格式同源** — scp 到 `~/.claude/skills/` 即被 claude code + opencode 双读 (§2.2) |
| 插件层     | `~\.trae-cn\plugins\trae-remote-official\` (installed-plugins.json) | 8 个                | browser/chrome/computer-use/lark 1.0.4 (OAuth connector + lark-cli 二进制)/product-lifecycle-workbench/seedance/seedream/teaching-management-assistant | **不可迁** — Trae 宿主绑定 (OAuth 连接器、Trae 内建工具、视频/图像生成后端)                                      |
| 内建层     | `~\.trae-cn\builtin\work\*/skills\`                                 | \~15 个             | docx/pdf/pptx/xlsx/feedback/TRAE-product-knowledge 等                                                                                                | 不迁本体; 同名开源版可从 anthropics/skills 取                                                        |

frontmatter 抽查 (5 个代表): `paper-lookup` (name+description+metadata, REST 无 MCP 绑定) · `research-lookup` (`allowed-tools: Read Write Edit Bash` + license/compatibility/required\_environment\_variables — claude code 忽略陌生字段, **推断待站上实测**) · `test-driven-development` / `math-finance-reasoning` / `brainstorming` (纯 name+description)。

**迁移分级**: **A** 纯 prompt 直拷 (scp 即用) / **B** +本地工具链 (pip/npm/lake) / **C** +外部 API key 与外网可达 / **D** Trae 托管 MCP 绑定 (换开源等价物) / **E** 宿主绑定 (不迁)。

### 7.2 六大类评估表

**① 高质量信息源检索**

| 技能              | 级 | 说明                                                                                    |
| --------------- | - | ------------------------------------------------------------------------------------- |
| research-lookup | C | parallel-cli 二进制 + PARALLEL\_API\_KEY/OPENROUTER\_API\_KEY; 三后端路由 (快搜/深研/学术) — 主控站已能用 |
| exa-search      | C | Exa API key; 语义检索 + research-paper 过滤                                                 |
| parallel-web    | C | parallel-cli 搜索/抓取/富化/深研                                                              |
| defuddle        | B | npm CLI 本地跑, URL 正文净化                                                                 |
| database-lookup | D | 依赖 Trae 托管 MCP — 换 REST 脚本或开源 MCP                                                     |

**② 学术论文搜索**

| 技能                             | 级     | 说明                                                                                                              |
| ------------------------------ | ----- | --------------------------------------------------------------------------------------------------------------- |
| **paper-lookup**               | **B** | 10 学术库 REST (PubMed/arXiv/OpenAlex/Crossref/Semantic Scholar...) **多数免 key** — 集群最可行的学术检索; references/ 子目录带端点速查 |
| literature-review              | B     | 多库系统综述, 同 REST 路数                                                                                               |
| citation-management            | B     | Python (Google Scholar/PubMed → BibTeX)                                                                         |
| pyzotero                       | B     | Zotero Web API (本地库主控站有)                                                                                        |
| bgpt-paper-search / paperzilla | D     | Trae 托管 MCP/应用绑定 — 换 §3.3 的 paper-search-mcp                                                                    |

**③ 工作流编排**

| 技能                                                                        | 级     | 说明                                                                       |
| ------------------------------------------------------------------------- | ----- | ------------------------------------------------------------------------ |
| **ars-academic-pipeline**                                                 | **A** | 10 阶段研究→写作→评审→修订全链编排 (五层循环 §4.2 的现成实现)                                   |
| ars-deep-research / ars-academic-paper / ars-paper-reviewer               | A     | 13-agent 深研 / 论文写作 / 5-评审员模拟                                             |
| research-\* 链 ×7 (scout/idea/baseline/experiment/decision/write/finalize) | A     | Research OS 中文流水线 — 与集群 spec 链 (RESEARCH→DESIGN→IMPL→CHECKLIST→ADR) 语义同构 |
| handoff / doc-coauthoring                                                 | A     | 会话交接压缩 / 文档共创流程                                                          |

**④ 软件工程规范 (superpowers 血统 — 实际已在装)**

| 技能                                   | 级     | 说明                                                                              |
| ------------------------------------ | ----- | ------------------------------------------------------------------------------- |
| **test-driven-development**          | **A** | 纯 prompt 纪律技能 ("看测试先失败"), frontmatter 极简                                        |
| brainstorming                        | A     | 创造性工作前置门 (HARD-GATE 设计先行); 正文引用 `docs/superpowers/specs/` 路径 — superpowers 血统实证 |
| writing-plans / executing-plans      | A     | 计划编写 / 计划执行 (spec 驱动的两端)                                                        |
| grill-me                             | A     | 计划拷问式评审                                                                         |
| security-best-practices              | A     | 语言安全审查 (py/js/ts/go)                                                            |
| cm-learn-codebase / cm-smart-explore | A/B   | 全量通读 / tree-sitter AST 结构搜索 (后者需装依赖)                                            |
| git-commit                           | A     | 约定式提交                                                                           |

> **§3.2 修正**: 原计划"从 obra/superpowers 挑 TDD + systematic-debugging 两个" — 盘点发现 superpowers 血统链 (brainstorming→writing-plans→executing-plans + TDD + grill-me + handoff) **已整体在装**, 无需从社区另取, 直接整链迁移 (全 A 类)。

**⑤ 数学推理**

| 技能                                                             | 级     | 说明                                                               |
| -------------------------------------------------------------- | ----- | ---------------------------------------------------------------- |
| **math-finance-reasoning**                                     | **A** | 六层推理架构 (定理证明+数值算法+学术品味+跨域联想); "engine vs fuel" 设计 — 纯 prompt 零依赖 |
| lean4-theorem-proving                                          | B     | 需 lake/lean4 工具链 (A/B 站可装, D:\Textbook 项目有既存动力)                  |
| sympy / matlab                                                 | B     | pip / Octave                                                     |
| statistical-analysis / statistical-power / experimental-design | A/B   | 测试选择/功效/DOE 纪律层为 prompt, 计算层可选装                                  |

**⑥ 任务规划**

| 技能                                       | 级 | 说明                                                     |
| ---------------------------------------- | - | ------------------------------------------------------ |
| what-if-oracle                           | A | 4-6 分支情景推演 (best/likely/worst/wild card/contrarian/二阶) |
| consciousness-council                    | A | 多视角审议会                                                 |
| brainstorming / writing-plans / grill-me | A | 同④ — 规划链即工程链                                           |
| plan-mode / verify-mode                  | E | Trae 模式绑定技能, 集群无对应模式机制                                 |

### 7.3 关键结论

1. **迁移成本远低于预期**: 技能层就是 claude code 格式的本地文件, A 类 (纯 prompt) 占六大类主力 — `scp -r` 到两站 `~/.claude/skills/` 即双 CLI 可用, 零改写
2. **六大类需求全覆盖**: 检索 (C 类为主, 受外网限制) 之外的五类全部 A/B 级 — 集群本地闭环无障碍
3. **C 类的现实约束**: B 站有外网不可达史 (opencode upgrade 时 github exit 28) — parallel/Exa 调用需实测连通性; 不通则检索类留主控站 trae (五层循环里"检索"本就派 trae 20% 高价值轮次, 分工自洽)
4. **D 类有开源平替**: 学术检索走 paper-lookup (REST 直连) + §3.3 的 paper-search-mcp, 无需 Trae 托管 MCP

### 7.4 落地批次 (并入 §4.5 路线; **已按 §7.5 原生生态对比修正**)

- **P0-原生优先 (装原生, 不迁 Trae)**: obra/superpowers v6.3.0 (工程链 20+ 技能, 替代 §7.2④ 的 Trae 快照 6 件) + anthropics/skills document-skills (docx/pdf/pptx/xlsx 生产级) — 两站 claude code 装 plugin; opencode 走其 README 的 OpenCode 安装路径

- **P0+定制迁移 (scp 直拷, 原生无等价)**: math-finance-reasoning + what-if-oracle + research-\* 编排链 7 个 + ars-academic-pipeline → 两站 `~/.claude/skills/` (\~10 个; 先 git 化主控站技能目录做单一事实源)

- **P1**: paper-lookup + literature-review (B 站 REST 连通性实测: arxiv/openalex/crossref 多数免 key); lean4 工具链视需求

- **P2**: research-lookup / exa-search (key 传播 + B 站外网连通性实测; 不通则永久留主控站); opencode-websearch-cited 试点

- **外网不可达预案**: B 站有 github exit 28 史 — plugin 安装失败时走"主控站 git clone → scp 上站 → 本地 plugin 目录安装"三段式

### 7.5 原生插件生态对比: 更优原生件则不迁 (2026-09-02 补充)

> 背景: §7.2 盘点的是"Trae 有什么可迁"; 本节反向盘点 **claude code / opencode 自身插件生态**, 对每类裁定"迁 Trae 件 vs 装原生" — 原则有原生等价物且更优时**不迁**。

**关键事实**: Trae 里的 superpowers 血统 6 件 (§7.2④) **本就是 obra/superpowers 的静态快照** — 原作已是 claude code 插件市场头部 (v6.3.0, 2026-08-12 更新; \~248k stars / 820k+ 安装, 官方 marketplace 在售)。装原生 = 拿到更新版本 + 更多技能 (20+: 增 subagent-driven-development / systematic-debugging / verification-before-completion / git-worktrees 等) + `/superpowers:brainstorm` 等 slash 命令 + SessionStart hook — 全面优于迁旧快照。

**claude code 原生生态头部** (官方 marketplace 200+ 插件):

| 来源                           | 件                                                                                        | 内容                                                               | 对本集群价值                   |
| ---------------------------- | ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | ------------------------ |
| obra/superpowers-marketplace | superpowers core                                                                         | 20+ 工程技能 + 命令 + SessionStart 注入                                  | **P0 装** — 替代 Trae 工程链迁移 |
| <br />                       | developing-for-claude-code                                                               | 42+ 官方文档文件 + 插件开发技能                                              | P2 (自建技能时)               |
| <br />                       | private-journal-mcp                                                                      | 本地语义日志 MCP                                                       | 可选 (与 §6.3 记忆层重叠)        |
| anthropics/skills (官方)       | document-skills                                                                          | docx/pdf/pptx/xlsx **生产级实现** (Claude.ai 文档功能同源, 含生成-验证-修复循环)     | **P0 装** — 两站出文档用        |
| <br />                       | example-skills                                                                           | skill-creator / mcp-builder / webapp-testing / artifacts-builder | P1-P2 按需                 |
| 官方第一方                        | code-review / security-guidance / typescript-lsp / frontend-design / planning-with-files | 多 agent 代码审查 / 安全扫描 / LSP 类型检查 / 前端设计 / 计划落盘                     | code-review P1; 其余按需     |
| 社区头部                         | claude-mem (§6.3 已裁定) / context7 (§3.3 已列) / MemPalace / Karpathy skills                 | 记忆 / 库文档 / 记忆宫殿 / 编码纪律                                           | 记忆与文档已在前节覆盖              |

**opencode 原生生态头部** (npm 1000+ 包; awesome-opencode 9.5k stars):

| 件                        | 功能                                             | 对本集群价值                                                                                                                       |
| ------------------------ | ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| opencode-scheduler       | cron 语法调度周期任务 (systemd/Linux)                  | P2 — 与集群 D1 看门狗 timer 同范式, 可做站侧例检                                                                                            |
| opencode-worktree        | git worktree 隔离会话                              | P2 — 多任务并行实验时                                                                                                                |
| opencode-supermemory     | 跨会话持久记忆                                        | 与 §6.3 选型重叠, 备选                                                                                                              |
| opencode-skillful        | 技能懒加载注入                                        | P2 — 技能多了之后的瘦身手段                                                                                                             |
| opencode-websearch-cited | 受支持 provider 的原生网页搜索 (Google grounded 风格)      | **P1 试** — 补 opencode 侧的网页搜索空缺 (claude code 内置 WebSearch 是 Anthropic 服务端工具本地后端不可用 §2.1; 此插件是否兼容本地后端未知, "受支持的提供商"限定语存疑, 试点裁决) |
| oh-my-opencode (slim)    | 编排 + LSP/AST 工具 + 后台 agent 套件                  | P2 — 与自定义 agent 路线重叠, 观察                                                                                                     |
| subtask2 / micode        | /commands 编排扩展 / brainstorm→plan→implement 工作流 | P2                                                                                                                           |

**逐类终裁 (迁 vs 原生)**:

| 类别         | 裁定                                                                     | 依据                                          |
| ---------- | ---------------------------------------------------------------------- | ------------------------------------------- |
| ④ 工程规范     | **装原生 obra/superpowers, 不迁 Trae 6 件**                                  | Trae 件 = 其旧快照; 原生 20+ 技能 + 命令 + hook + 持续更新 |
| 文档处理 (新增类) | **装原生 anthropics document-skills**                                     | 生产级 (含验证-修复循环), Trae 无对应迁移件                 |
| ③ 学术编排     | *迁 Trae (research-* 链 + ars-pipeline)\*                                | 原生无学术工作流等价物 — Scott 定制资产                    |
| ⑤ 数学推理     | **迁 Trae (math-finance-reasoning)**                                    | 原生无等价 (六层架构是从 12 个 Claude 会话提炼的定制件)         |
| ⑥ 任务规划     | **混合**: 通用规划用原生 superpowers; what-if-oracle / consciousness-council 迁移 | what-if 4-6 分支推演原生无直接等价                     |
| ② 学术检索     | **迁 Trae (paper-lookup)**                                              | claude code 无官方学术检索插件; context7 是库文档非论文     |
| ① 信息检索     | **留主控站 + P1 试 opencode-websearch-cited**                               | C 类外网限制不变; 内置 WebSearch 本地后端不可用             |

**总策略修正 (三层)**: 原生优先 (superpowers / document-skills / 官方 code-review) → 定制迁移 (数学推理 / 学术编排 / 学术检索 / what-if — 原生无等价的 Scott 资产) → Trae 兜底 (C 类检索留主控站, E 类宿主绑定弃)。§7.4 批次已同步改写。

**本节参考**: [obra/superpowers](https://github.com/obra/superpowers) · [obra/superpowers-marketplace](https://github.com/obra/superpowers-marketplace) (v6.3.0) · [anthropics/skills](https://github.com/anthropics/skills) · [Best Claude Code Plugins 2026 (designrevision)](https://designrevision.com/blog/best-claude-code-plugins) · [10 top Claude Code plugins (composio/dev.to)](https://dev.to/composiodev/10-top-claude-code-plugins-to-use-in-2026-4gn6) · [awesome-opencode](https://github.com/awesome-opencode/awesome-opencode) · [opencode 官方生态页](https://dev.opencode.ai/docs/ecosystem/) · [Best OpenCode Plugins (composio)](https://composio.dev/content/best-opencode-plugins)

### 7.6 排幻觉审计记录 (2026-09-02, 针对 §6/§7)

> 方法: 逐断言追溯信息源并定级 — **E1** 一手直读 (官方 model card / GitHub·npm README / 本地磁盘实测) · **E2** 官方文档页 · **E3** 可靠第三方 (NVIDIA blog / 实测指南 / 技术媒体) · **E4** 单一博客/社区帖 · **E5** 无直接来源的推断。发现 8 处问题全部已修正进正文。

**修正清单**:

| #  | 原断言                                                               | 问题                                                                                         | 处置                                            |
| -- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | --------------------------------------------- |
| F1 | "Trae 技能层 \~190 个" (§7.1)                                         | 低估 — 目录计数实测 **213**                                                                        | 已改正文                                          |
| F2 | claude-mem worker 端口 :37777 (§6.3)                                | 第三方文章 (termdock) 与官方 docs 冲突; 官方为 `37700 + (uid % 100)` 每用户不同                              | 取官方, 已改正文                                     |
| F3 | "claude-mem 72K+ stars 生态最大" (§6.3)                               | 两来源数字矛盾 (72.4K\@2026-05 augmentcode vs 89K+\@2026-03 termdock, stars 不可能倒退 — 至少一方失真)       | 改为"70k+ 级"保守口径并标注矛盾                           |
| F4 | "claude code 按 \~200k 假设...永远晚于真实上限" (§6.4, 原表述为事实)               | **推断被当实证** — 92% 阈值与窗口映射机制有 E4 来源, 但"自定义后端下仍按 200k 计"无任何来源                                 | 降级为"推断非实证", 补 5min 验证法 (上站跑 `/context` 看窗口基数) |
| F5 | opencode `limit.context` 嵌套式配置示例 (§6.2)                           | 两来源格式冲突: 嵌套式 (yahtoo 第三方整理) vs GLM5 案例平铺式 (bswen); `prune` 默认值亦冲突 (官方片段 false vs 第三方 true) | 保留嵌套式但加"格式待站上验证"标注; prune 显式写 true 消歧         |
| F6 | Auto Memory "v2.1.59+ / 前 200 行或 25KB" (§6.2)                     | 单一 CSDN 博客来源 (E4)                                                                          | 加"单一博客来源, 细节待实测"标注                            |
| F7 | "GLM5 同款教训**实证**" (§6.2 注释)                                       | 案例本身真实但属博客级证据 (E4)                                                                         | 措辞降为"社区案例"                                    |
| F8 | "opencode-websearch-cited...补 claude code 内置 WebSearch 之洞" (§7.5) | 措辞失准 — 该件是 **opencode** 插件, 补的是 opencode 侧; 且"受支持的提供商"是否含本地后端未知                            | 已改精确表述 + 标注存疑待试点                              |

**抽验通过的关键断言 (无需改)**:

| 断言                                                                                                          | 来源等级       | 核验方式                                                                                                                       |
| ----------------------------------------------------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------- |
| Trae superpowers 血统 6 件 = obra/superpowers 快照                                                               | **E1 级实证** | mdskills.ai 收录的 obra/brainstorming description 与 Trae 本地 SKILL.md **逐字一致**; skill 名单/正文结构 (docs/superpowers/specs 路径引用) 吻合 |
| superpowers v6.3.0 (2026-08-12) / 820k+ installs / 20+ skills                                               | E1+E3      | marketplace commit 记录 + clauder-navi + marketplace README                                                                  |
| nemotron RULER @256k 96.30 / @1M 91.75; gpt-oss @256k 52.30 / @1M 22.30; temp=1.0+top\_p=0.95; SWE-Bench 数字 | E1         | build.nvidia.com model card 直读                                                                                             |
| claude-mem 支持 opencode (`--ide opencode`) / 注入近 10 session                                                  | E1         | GitHub README + docs.claude-mem.ai                                                                                         |
| opencode-codex-memory: 6h 闲置提取 / 版本须钉死 / 需 ≥1.18 / 全本地                                                      | E1         | npm README 直读                                                                                                              |
| Trae 插件层 8 个宿主绑定 (browser/chrome/computer-use/lark/...)                                                     | E1         | installed-plugins.json 直读                                                                                                  |
| anthropics document-skills = Claude.ai 文档功能同源, 含生成-验证-修复循环                                                  | E2         | 官方 README ("power Claude's document capabilities") + 实现.review                                                             |
| 多 agent token \~15x                                                                                         | E3         | NVIDIA 官方 blog 引 Anthropic 工程博客                                                                                            |
| gpt-oss CoT passback (5+ 轮) / effort low 几乎无推理                                                              | E3         | ivanopcode 实测指南                                                                                                            |
| ctx 16k→32k 同级 MoE 吞吐 -30%                                                                                  | E3         | corti DGX Spark 实测 (原文"comparable small-active MoE", 非gpt-oss本体 — 归因已按原文限定)                                                |

**残余风险声明**: ① E4 级 claude code 机制细节 (/compact 92% 阈值, /context 用法) 未在本地后端实测 — 均为操作建议非关键路径, 实操时以实际行为为准; ② opencode 官方 config schema 未直接拉取 (open-code.ai 文档页未全文读), §6.2 配置以第三方整理为据 — 上站首装时须过一遍 schema 校验; ③ 本审计覆盖 §6/§7 (本轮新增), §1-§5 为首轮调研 + 附录 subagent 原文, D4 时已过一轮排幻觉 (表格重排提交 1ef4179)。

***

## 8. 补充调研: Agent 审计任务与断言溯源机制 (2026-09-02)

> 需求: agent CLI 可能需要执行审计任务 — **被审查 agent 必须显式给出断言依据、信息源链接、逻辑链**供审查 agent 复核; **审查 agent 自身也须遵循特定规范** (独立立场/结构化输出/不被编排者污染)。参考项目: `F:\semantica-main`。本节评估 opencode / claude code 生态有无现成件, 以及本集群的最优路径。

### 8.1 参考项目解析 (semantica, 本地实测 F:)

semantica 是知识图谱工具链 (ingest→extract→reason→决策), 其 `plugins/` 目录含 9 平台插件包装 (`.claude-plugin`/`.cursor-plugin`/...) + 17 个技能 + 3 个 agents。与审计需求相关的核心理念:

| 机制                | semantica 实现                                                                                                                         | 对本需求的启示                                                     |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------- |
| **provenance** 技能 | `trace <node>` 返回 source chain/authors/timestamps/validation status; `audit --since` 返回 change events/actor/objects                  | **"断言的信息源追溯"** 的图谱化实现 — 但绑定 semantica Python 栈, 不可直接迁; 理念可借 |
| **explain** 技能    | `decision <id>` 返回 decision factors/rule traces/confidence; `graph <node>` 返回 upstream/downstream causal chain + supporting evidence | **"逻辑链可解释"** — 因果链+证据+置信度的输出结构正是审查 agent 想收到的格式             |
| 干净的数据模型           | 每条知识带 provenance 元数据 (作者/时间戳/验证状态)                                                                                                   | 断言应携带元数据而非裸文本                                               |

**结论**: semantica 是"重型基础设施"路线 (数据先入图谱再溯源); 本集群需求是"轻量 prompt 协议" (断言直接内嵌溯源字段) — 借理念不迁实现。

### 8.2 生态现状: 四层可组合, 无单一对口件

**层 1 — 官方 prompt 模式 (E2, 零安装)**: Anthropic 官方 "Reduce hallucinations" 文档给出三件套: ① 允许说不知道; ② 事实断言先提取逐字引文再分析; ③ **verify-with-citations** — 生成后逐条 claim 找支持引文, 找不到**必须撤回该断言**。另有社区 "Anti-Hallucination Stack" 三指令 (不确定标注 / 来源三级标注: documents-provided vs training-data vs inference / 宁缺勿造) — 与 §7.6 的 E1-E5 分级同构。

**层 2 — 现成 skill (E1 直读)**:

| skill                                | 审什么                                                                                                                                      | 形态                                                                                                                    | 对口度                     |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| **deglaze** (LuciferDono)            | "声称完成"的虚报 — 17 个 under-delivery 模式 + 24 压力技巧; 干净时须用**证据** (commit hash/file path/test output) 反驳而非表功                                     | 纯 prompt skill, git clone 到 `~/.claude/skills/` 即用, 支持 claude code/cursor/codex                                       | 高 — 被审查 agent 的"自我交底"规范 |
| **paper-review\.skill** (jam-cc, 中文) | 学术审稿: 四阶段含 **Prune & Verify References** (引用逐条 web search 验证; "LLM 生成的参考文献 60-80% 作者列表是错的")                                              | 纯 prompt skill                                                                                                        | 高 — 审查 agent 侧的引用验证规范   |
| **ARS 三层引用锚点** (已装!)                 | 每条 citation 带 quote/page/section 三层锚; 审计器抓取被引源判断 claim 是否真被支持; 5 类 HIGH-WARN 触发拒绝: claim-not-supported/fabricated-reference/anchorless 等 | **本地 Trae 已装** (ars-academic-pipeline/ars-paper-reviewer, §7.2③) — **本轮重新发现**: §7.5 只把它归类为"学术编排", 其引用锚点审计机制正是本需求的原生形态 | 极高 — 零迁移成本, 已在资产清单内     |

**层 3 — 跨模型对抗审查架构 (E1/E3)**:

| 件                                   | 机制                                                                                                                                      | 对本集群的映射                                                                                                                     |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **adversarial-review** (ng)         | Optimizer 与 Skeptic 两 agent 独立审查后**互相挑战对方发现**, 只有高置信度幸存项进入修复; 有界验证环防修复引入回归; 可加跨厂商 reviewer (协议级共识 = 最强信号)                               | **nemotron↔gpt-oss 双端点互审 = 免费本地版**: 两异构模型族 (Mamba-MoE vs harmony MoE) 失败模式独立, 正是"same-model agreement least trustworthy"的解药 |
| Codex 桥 `/codex:adversarial-review` | XML 模板定位审查者为怀疑论者 ("break confidence in the change, not validate it"); **JSON schema 结构化发现** (file/line/confidence/verdict) — 跨模型机器可验证通信 | 结构化发现的 schema 可直接借为审查 agent 输出契约                                                                                            |
| ultracodex                          | 异模型节点 (Codex headless) 嵌入 Claude Workflow 编排, "verify/judge/2nd-opinion 用独立失败模式的模型"                                                     | 同上映射: gpt-oss 端点做 nemotron 产出的 2nd-opinion 节点                                                                               |

**层 4 — 审查 agent 的输入完整性 (E1, 最对口但最重)**: `michael-conrad/.opencode` #704 "Auditor Prompt Integrity" spec — 审计员的干净室问题: **编排者控制审计员的上下文输入, 可推送预消化证据/先验结论/偏见命名污染审计独立性**。其方案: `dispatch_context` 结构化契约 (`must_receive`/`must_not_receive` 字段) + 审计员 Step 0 自检自己的 prompt 是否被污染 (40 向量目录) + 检测到即返回 `CLEAN_ROOM_VIOLATION` 中止 (零自辩 mandate: 检测即结论, 禁止被继续推理说服)。**这是"审查 agent 也要遵循特定规范"的最深形态** — 适合作为本集群审查规范的设计蓝本。

### 8.3 裁定: 自制 assertion-audit skill (三层组合)

**无单一现成件完整覆盖"被审查方断言溯源 + 审查方独立规范"双向协议** — 但需求本身高度特化 (Scott 的 §7.6 手工审计就是它的原型), 自制成本低于适配现成件。裁定**自制成两个纯 prompt skill** (A 类, 走 D5 的 M1 单一事实源):

**①** **`assertion-audit`** **skill (被审查 agent 侧输出规范)** — 把 §7.6 的手工协议技能化:

```markdown
---
name: assertion-audit
description: Produce audit-ready output. Every factual claim must carry
  (a) evidence class E1-E5, (b) source link/path, (c) inference chain.
  Use when tasked with research, review, or any deliverable whose
  claims will be cross-checked by another agent.
---
## 输出契约
1. 断言表: | 断言 | 证据等级 E1-E5 | 信息源 (URL/文件路径/命令输出) | 逻辑链 (前提→推理→结论) |
2. 无源断言必须显式标 E5 (推断) 并给验证方法
3. 引用他人的判断须与自己的核验分开标注 (二手 vs 一手)
4. 结论只允许从表中断言推出 — 表外无断言
```

**②** **`cross-examine`** **skill (审查 agent 侧规范)** — 融合 adversarial-review 怀疑论立场 + #704 干净室 + deglaze 证据反驳:

```markdown
---
name: cross-examine
description: Adversarial review of another agent's audited output.
  Skeptic stance, structured findings, contamination self-check.
---
## 审查协议
1. Step 0 干净室自检: 任务卡是否预装了结论/预消化证据? → CLEAN_ROOM_VIOLATION 中止
2. 逐断言核验: 抽查 E1/E2 断言的信息源 (fetch/读文件); E5 断言查逻辑链漏洞
3. 结构化发现 (JSON): {断言id, 判定 SUPPORTED/UNSUPPORTED/UNVERIFIABLE, 置信度, 依据}
4. 怀疑论立场: "break confidence, not validate it"; 不给努力分
5. 审查干净的断言也须附核验证据, 不允许"看起来对"
```

**③ 部署形态**: 双 skill 进 D5 的 `ops/agent-skills/` 单一事实源 → 两站双 CLI; 审查 agent 可用**对端模型**跑 (B 站产物用 A 站 gpt-oss 审, 反之亦然) — 双端点互审天然落实"异构模型独立失败模式"原则, 零新增基础设施。

### 8.4 对既有计划的影响 (D5 DESIGN 增补项)

1. **M1 技能清单 +2**: assertion-audit / cross-examine (自制, A 类) — 随 D5 T4 批次部署
2. **已装 ARS 价值重估**: §7.2③ 的 ars-paper-reviewer 不只是"学术编排" — 其三层引用锚点机制是学术场景 assertion-audit 的先行实现; 学术审计任务可直接调 ARS, 通用审计走新制 skill
3. **五层循环第 5 层具体化**: 调研 §4.2 的"trae ADD 审计回环"获得本地执行侧的双 skill 协议支撑 — trae 审计之外新增"站间互审"变体 (nemotron 产出 → gpt-oss 审查)
4. **不装**: adversarial-review 整件 (其价值已被双端点互审 + 自制 skill 覆盖); semantica (理念已借, 基础设施不匹配)
5. **(§8.5 改判) ARS 部署源换成 opencode 原生移植版**: §7.4 的 ARS 落地不走 Trae 兜底 — 两站 opencode 用 timpara 移植版原生跑 (§8.5-1); v3.8 claim-audit 的 FNR/FPR 校准阈值作为自制 assertion-audit 的验收蓝本

### 8.5 二轮增补: opencode 原生生态的审计件盘点 (2026-09-02)

> §8.2 的"四层无单一对口件"结论主要基于通用/Claude Code 生态。本轮专扫 opencode 原生插件生态 (GitHub topic `opencode-plugin` 701 仓 + awesome-opencode discussions + npm), 两项发现修正边界: **ARS 有 opencode 原生移植版**, 且 prompt 契约存在 **hook 层强制化** 的现成样板。

| 件                                                                        | 形态                                                                                           | 审计机制                                                                                                                                                                                                                                                                                                                                               | 裁定                                                                                                                                                                                                                           |
| ------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ARS OpenCode 移植版** (timpara/opencode-academic-research, 上游 Cheng-I Wu) | skills+commands+plugin, `./install.sh` symlink 到 `~/.config/opencode/`                       | **v3.8 claim-audit pass** (`ARS_CLAIM_AUDIT=1`): 抓取被引源×三层锚点逐条判 claim 是否真被支持, 5 类 HIGH-WARN (claim-not-supported / fabricated-reference / anchorless...) 经 formatter 硬门**拒绝输出**; 校准带 20-tuple gold set, 验收 **FNR<0.15 / FPR<0.10**; v3.7.1 trust-chain frontmatter 溯源; `ARS_CROSS_MODEL` 跨模型 DA; 7-mode AI 失败模式阻断清单 (Lu et al. AI Scientist 失败模式清单) | **改判 §8.4-2**: 已装 ARS 不必 Trae 兜底 — 工作流内容与上游一致仅打包不同, 两站 opencode 原生可跑; D5 T4 的 ARS 部署源直接用此仓                                                                                                                                   |
| **CiteAgent** (@ephremyuan/citeagent, Areopaguaworkshop/citeagent)       | opencode plugin (5 agents: researcher/verifier/ingestor/explore-corpus/reviewer) + 25 MCP 工具 | 契约 "**no claim without evidence, no evidence without a hash, no hash without a Merkle proof**": 文档→节点→SHA-256→Merkle 树; BM25 确定性检索 (无 embedding); **fail-closed** 完整性验证器; verification ladder L0-L4 + crypto audit chain                                                                                                                           | **机制参考不装**: 断言级哈希溯源是最重形态 (同 semantica 判例 — 重型基础设施); 未来若需本地论文库 claim 级审计可列 P2 候选 (bun + ingestion 侧车成本)                                                                                                                       |
| **oy** (adonm/oy-cli)                                                    | Rust CLI + opencode 内 `/oy-audit` `/oy-review` `/oy-enhance`                                 | 证据冻结→评审→核验三段: 输入确定性收集到 `.oy/runs/`; **核验阶段拒绝被改的输入/被修改的证据/并发改报告/畸形 finding**; 稳定 finding ID, 单 finding 修复后重跑原工作流确认                                                                                                                                                                                                                                  | **模式借**: "证据冻结+报告对账"是 prompt 层没有的确定性环节; 非对口 (代码/工作区审计导向), 不装                                                                                                                                                                 |
| **oh-my-review-experts** (zapsaang)                                      | opencode plugin, `/review-code` 一键                                                           | 五专家面板 (spec/quality/security/performance/concurrency), 每专家独立 prompt contract + **JSON 输出 schema**; 发现带 evidence + 磁盘 audit trail                                                                                                                                                                                                                   | **schema 参考**: cross-examine 的结构化发现可按"每 lens 一 schema"扩展; 不装 (diff 审查导向)                                                                                                                                                     |
| **adlc** (voodootikigod/adlc)                                            | opencode plugin + skills + 命令面                                                               | P5 prosecution 面: Claude Code 插件含 prosecutor 子代理; CLI 侧 `@adlc/prosecute` 是**证据记录器而非审查器** (零模型调用, 实际审查走 `npx adversarial-review`, 其输出作为 `--input` 证据); 收敛规则 = **连续两轮干轮 (zero findings) + ≥3 个独立 lens** (内置 lens: security/correctness/tests/behavior/integration/docs); `--prompt-only` 让 LLM 门零 API key 跑宿主模型                                     | **立场命名可借**: "prosecutor" 命名即立场 (起诉方而非协助方); "两连干轮+≥3 lens" 收敛判据并入 cross-examine 协议; 其 trust-root tier 强制**跨模型审查** (provider 必须异于作者) 与本集群 nemotron↔gpt-oss 互审同构; 不装整件 (全生命周期框架, 与本集群 spec 驱动流程重叠; 且 Windows 不支持, 两站 Ubuntu 无碍) |
| **opencode-gemini-search** (@happycastle)                                | opencode plugin (注册 `gemini_web_search` 工具)                                                  | **工具层强制引用契约**: 响应无 `## Sources` 节 + inline `[Source](url)` 即 **throw** — "the model cannot ship un-sourced claims"; 违约响应不返回给模型                                                                                                                                                                                                                     | **升级路径样板**: assertion-audit 从 prompt 契约升级为 hook 强制的参照 (见下)                                                                                                                                                                   |

**两条增量结论**:

1. **ARS 部署路径改判** (上表第 1 行): §7.4 的 ARS 批次从"Trae 已装兜底"升级为"两站 opencode 原生跑移植版"; 其 **claim-audit 的 FNR/FPR 校准阈值直接作为自制 assertion-audit 的验收蓝本** — 审查器自身也要校准 (不是只审别人), 这补上了 §8.3 草案缺失的"审查器质量如何验收"一环。
2. **自制 skill 的强制化升级路径**: Phase 1 纯 prompt (§8.3 草案, 零成本) → Phase 2 可选 opencode plugin (\~50 行 hook): 任务卡带 `audit: true` 时在 `chat.params`/`tool.execute.after` hook 检查最终输出必须含断言表, 缺失即注入 `ASSERTION_TABLE_MISSING` 回轮 — gemini-search 的 throw 模式 + #704 干净室同层落实。先 prompt 后 hook, 与 §6 "零安装先行"同哲学。

### 8.6 三轮增补: 插件层稳定性 / 兼容性 / 故障模式盘点 (2026-09-02)

> 需求: D5 落地前评估 opencode / claude code **插件体系的版本稳定性** — 是否出现崩溃、无输出、卡死等故障。结论先行: **两侧插件层都不稳定, 但故障集中在 plugin-API-依赖型件; A 类纯 prompt skill 与 skills 目录完全绕开故障面**。这反向验证了 §6/§7 "零安装先行、A级优先"策略的正确性。

#### 8.6.1 opencode: plugin API 在 patch 版内被静默破坏 (多次实锤)

| 事件                                                             | 版本                         | 故障模式                                                                                                                                            | 证据                                                                                                                   |
| -------------------------------------------------------------- | -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `api.command.*` 整个命名空间**无弃用周期移除** (patch bump 1.14.41→1.14.42) | v1.14.42                   | TUI 插件 init 即 `TypeError: undefined is not an object`, 插件从侧边栏**整体消失**(看似被卸载); 无 changelog/迁移指南; 捆绑的 `@opencode-ai/plugin` 类型声明仍是旧面 — 类型检查也查不出   | [#26557](https://github.com/anomalyco/opencode/issues/26557)                                                         |
| **V2 plugin API / 命名空间化 hook** (PR #7639)                      | v1.17.10                   | oh-my-openagent 的 `session.idle`/`session.error` 等 hook **静默不触发**: 子代理完成不上报→**父会话无限挂起**; 日志零报错; 回滚 1.17.9 立即恢复                                  | [OMO #5575](https://github.com/code-yeongyu/oh-my-openagent/issues/5575)                                             |
| `api.keybind` 移除 + opentui buffer 格式 Float32Array→Uint16Array  | v1.15.0 / v1.14.40         | 插件崩溃 on load; 或**加载成功但视觉效果全黑**(写 0.5 被截断为 0) — "无输出"型故障                                                                                         | [oc-plugin-rainbow #7](https://github.com/anomalyco/oc-plugin-rainbow/issues/7)                                      |
| Effect 迁移: `ask()` 返回 `Effect<void>` 而非 `Promise<void>`        | v1.4.4+ (三轮修正: 原记 v1.4.7+) | 类型层面 breaking (运行时兼容) — Effect 化是持续趋势, plugin 代码须跟随                                                                                             | [lancedb-opencode-pro 兼容矩阵](https://github.com/tryweb/lancedb-opencode-pro/blob/HEAD/docs/OPENCODE_COMPATIBILITY.md) |
| **plugin loader 重构破坏 NAPI 解析** (PR #20112, 二轮修正: 原误记为"缓存过期")   | v1.3.8+                    | NAPI 原生依赖 (`.node` 二进制) import 解析为空对象 `{}` — 插件加载"成功"但所有导出 undefined, 又一个静默无输出型; `lancedb.connect is not a function`; v1.3.9 的修补未覆盖 native 模块解析 | [#20623](https://github.com/sst/opencode/issues/20623) (closed as not planned)                                       |

**TUI/会话层卡死** (与插件无必然关联, 但影响长会话可靠性): 随机 TUI 冻结 busy-wait 循环 ([#12834](https://github.com/anomalyco/opencode/issues/12834), v1.1.53 起); OpenAI 流高 CPU 冻结、socket 空闲 230s 无超时 ([#29129](https://github.com/anomalyco/opencode/issues/29129)); 长思考块零流式输出、TUI 看似挂死 ([#25094](https://github.com/anomalyco/opencode/issues/25094)); Linux 长会话中段 TUI 冻结 ([#35641](https://github.com/anomalyco/opencode/issues/35641), 关闭为 **[#30067](https://github.com/anomalyco/opencode/issues/30067)** **重复**: 长会话 50-80 轮 agent 循环中文本/reasoning delta O(N²) 累积 — **与本集群 nemotron 长会话用法直接相关**, 会话预算内轮数越多越慢; §8.9 直抓: issue Open, 修复 PR #42150 在途)。**高相关项**: 首次运行 ripgrep 下载停滞→grep/skill 工具**无限挂起零报错** ([#23891](https://github.com/anomalyco/opencode/issues/23891), closed as not planned) — 两站在中国网络环境访问 GitHub Releases 正是高危场景, **必须预装系统 ripgrep**。

#### 8.6.2 claude code: marketplace 机制自身的破坏性故障

| 事件                                                                                                                                       | 故障模式                                                                                                                                                                            | 证据                                                                                                              |
| ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| **marketplace 自动更新静默清空插件**: staging→production 换页不完成, manifest 丢失→下次启动"对账"删掉插件目录; `--channels` 横幅谎称 "Listening" 但进程从未启动; 手工恢复无效(再次启动又被清) | telegram 插件会话中途静默死亡, 无错误无日志无恢复机制; 同类 [#40153](https://github.com/anthropics/claude-code/issues/40153) 是**整个 marketplace 目录被删** (§8.9 直抓: 先删后 re-clone 失败即裸; 两者为不同故障模式, 均未获上游认领) | [#41701](https://github.com/anthropics/claude-code/issues/41701) (v2.1.87)                                      |
| 单个插件 schema 不合法→**整个 marketplace 58 件全灭** (semgrep 的 `git-subdir` source type 不识别, 无跳过容错)                                                | `/plugin` 全体不可用                                                                                                                                                                 | [#33739](https://github.com/anthropics/claude-code/issues/33739)                                                |
| Cowork: ZIP 安装的 hooks **静默忽略**(无警告), 仅 marketplace/GitHub 分发生效; marketplace URL 静默拒绝非 github.com 源                                       | 治理层 hook 形同虚设; CLI 不受影响                                                                                                                                                         | [systemprompt.io 实录](https://systemprompt.io/guides/building-on-quicksand-claude-breaking-changes) (2026-03-26) |
| Cowork 插件装完即被标 `NOT_AVAILABLE`, 每 sync 周期删除, VM 进程 \~1s 被 SIGTERM                                                                        | 技能永不加载                                                                                                                                                                          | [#39274](https://github.com/anthropics/claude-code/issues/39274)                                                |

本集群影响有限: 主力在 opencode + claude code **CLI 短任务**, Cowork/Desktop 的故障面天然隔离; 但 claude code 侧若装 marketplace 插件, 自动更新是**已知破坏源**。

#### 8.6.3 裁定: 对 D5 的四条落地约束

1. **A 类纯 prompt skill 的战略价值再确认**: skills 目录的 SKILL.md 不触碰 plugin API — §8.5 表中六件候选全部"不装"的裁定的第二重理由(第一重是对口性)。自制 assertion-audit/cross-examine **长期停留在 Phase 1 prompt 形态**, Phase 2 hook 化降级为"仅在 prompt 契约被实测证明失效后才启动", 且启动前置条件 = 锁 opencode 版本 + hook 只用服务端事件(`tool.execute.after`/`chat.params`), **禁用 TUI** **`api.*`** **面**(三次破坏全在 TUI 面)。
2. **opencode 版本锁定纪律**(同内核锁定先例): 两站 opencode 锁版本、禁自动升级; 升级=受控变更, 升级后必须跑插件冒烟(装一件带 hook 的测试件, 验证 `session.idle` 触发), 因 breaking 多发生在 patch 位。挂到 params-ledger 维护约定。
3. **预装系统 ripgrep**: 两站 `apt install ripgrep` 列入 D5 环境准备步骤, 杜绝首跑下载 GitHub 静默挂死 (#23891 中国网络高危)。
4. **claude code 插件面维持最小**: 沿用本集群纪律(claude code 只做短任务), 不依赖 marketplace 分发; 若未来需要, 优先本地路径安装绕开自动更新破坏链。

### 8.7 §8.5/§8.6 排幻觉审计记录 (2026-09-02)

> 方法: §8.5 六仓全部重新抓取 README 原文逐断言比对 (E1 一手); §8.6 全部 issue 断言来自本会话直接抓取的 issue 页面 (E1, 无二手转述)。审计发现 **2 处修正**, 其余断言全部实锤。

| 断言                                                                                                                                                                                                   | 判定          | 依据                                                                                                                                                                                                                                                                                                                      |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ARS 移植版: install.sh symlink / v3.8 `ARS_CLAIM_AUDIT=1` / 5 类 HIGH-WARN 硬门 / 20-tuple gold set FNR<0.15+FPR<0.10 / v3.7.1 trust-chain / `ARS_CROSS_MODEL` / 7-mode Lu et al. 阻断清单 / "工作流内容与上游一致仅打包不同" | **全部实锤**    | README 原文逐句对应; 校准措辞原文 "the reviewer offers an opt-in calibration mode that measures its own FNR/FPR against a user-supplied gold set" — 审查器自校准确认存在                                                                                                                                                                      |
| CiteAgent: 三段 Merkle 契约引语 / SHA-256 节点→Merkle 树 / BM25 无 embedding (MiniSearch) / fail-closed / 25 工具+5 agents / **verification ladder L0-L4 + crypto audit chain**                                  | **全部实锤**    | L0-L4 逐字见 README Hooks 节 ("SafeHarness (sanitize + permission tiers), verification ladder (L0–L4), crypto audit chain"); 契约引语逐字匹配                                                                                                                                                                                       |
| oy: `/oy-audit` `/oy-review` `/oy-enhance` / `.oy/runs/` / 核验拒绝四类 (改输入/改证据/并发改报告/畸形 finding) / 稳定 finding ID / 单 finding 修复后重跑原工作流                                                                   | **全部实锤**    | README "How repeatable review works" 四步逐句对应                                                                                                                                                                                                                                                                             |
| oh-my-review-experts: 五专家 **spec/quality/security/performance/concurrency** / JSON schema 校验报告 / 磁盘 audit trail                                                                                      | **全部实锤**    | README reviewers 表五名逐字匹配; 报告落 `.omre/reports/` schema-validated JSON; 补充实测: 11 子代理 + 分片仲裁器合并, "报告从文件不从聊天记录"                                                                                                                                                                                                             |
| adlc: 原 §8.5 草案 "`@prosecutor-correctness/security/contract/diff/tests` 五检察官 + loop-until-dry 查不出新问题才放行"                                                                                             | **修正①**     | `packages/prosecute/README` 原文: "**this is a recorder, not a reviewer** — zero model calls", 实际审查是 `npx adversarial-review`; 五检察官具体命名未能在仓库文档中定位 (E5 已降级); 收敛规则实为 "**two consecutive dry passes with at least three distinct dry lenses**" (内置 lens 六个: security/correctness/tests/behavior/integration/docs) — 已按实锤改写上表 |
| adlc: `--prompt-only` keyless / P5 prosecution 面                                                                                                                                                     | **实锤**      | README: "usable with zero API keys"; 补充强发现: trust-root tier **强制跨模型审查** (attestation provider 必须异于 author, fail-closed) — 与本集群 nemotron↔gpt-oss 站间互审同构, §8.4 站间互审的外部佐证                                                                                                                                                  |
| gemini-search: 无 `## Sources` + inline `[Source](url)` 即 throw                                                                                                                                       | **实锤且强于原述** | README 契约远比草案丰富: 7 规则 prompt 契约 (零伪造 URL/占位域名黑名单/集合相等校验/字节级 URL 比较不折叠大小写/`NO_RESULTS` 字面量回退/提示注入防御) + 诚实披露 provenance 极限 ("structural filter, not a cryptographic provenance guarantee")                                                                                                                                |
| §8.6 全部 issue 断言 (opencode #26557/#5575/#23891/#29129/#12834/#25094/#35641; claude-code #41701/#33739/#39274; systemprompt.io)                                                                       | **实锤**      | ~~均为本会话直接抓取~~ **元断言修正**: 首轮证据实为搜索结果快照 (E2) 而非 issue 页面直抓, 本表原声明夸大; §8.8 二轮已逐一 WebFetch 直抓全部升级为 E1, 内容全部核实 (含 1 处根因修正)                                                                                                                                                                                                   |

**审计后增量发现 (已回写上表)**: ① adlc trust-root tier 的跨模型审查强制 — 是 §8.4-3 站间互审设计的外部同构实证, 可作为 D5 验收引用; ② gemini-search 的"结构过滤≠密码学溯源"诚实披露 — assertion-audit 设计应效仿: **明确声明契约的证明力边界**, 防止把结构校验当成了溯源保证。

### 8.8 二轮复核: §8.6 issue 断言直抓核验 (2026-09-02)

> 方法: 11 个载荷 URL (10 issue + 1 文章) 逐一 WebFetch 直抓, 升级为 E1。结果: **10 全实锤 + 1 根因修正 + 1 元断言修正**。

**核验结果**:

| 断言                                | 判定          | 直抓核实要点                                                                                                                                                                                                                                                                                                           |
| --------------------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| #26557 `api.command.*` patch 版内移除 | **实锤**      | 标题逐字含 "no deprecation cycle, no changelog entry, no migration guide"; PR #26053; 报错 `TypeError: undefined is not an object (evaluating 'api.command.register')`; "looks like the plugin was uninstalled"; 类型声明细节原文 "bundled `@opencode-ai/plugin` types still declare the old surface... no compile-time signal" |
| OMO #5575 V2 hook 静默失效            | **实锤**      | "hooks silently stop firing on OpenCode ≥ 1.17.10"; `session.idle`/`session.error` 不触发; "parent hangs indefinitely"; "Reverting to v1.17.9 immediately resolves"; PR #7639; 已由 OMO 侧 PR #5916 适配关闭 — 印证"插件追着平台跑"模式                                                                                               |
| #23891 ripgrep 首跑挂死               | **实锤**      | "Subtask hangs silently forever"; grep+skill 工具无限挂起零报错; WSL2 无系统 rg; **closed as not planned**                                                                                                                                                                                                                   |
| #29129 OpenAI 流冻结                 | **实锤**      | `lastsnd:230238` (\~230s 空闲) 逐字; CPU 32.8%; v1.15.10                                                                                                                                                                                                                                                             |
| #12834 随机 TUI 冻结                  | **实锤**      | v1.1.53; busy-wait epoll 循环 strace 实录                                                                                                                                                                                                                                                                            |
| #25094 长思考块零输出                    | **实锤**      | thinking 30s+ 零可见输出; 两次 stall 实录                                                                                                                                                                                                                                                                                 |
| #35641 Linux 长会话冻结                | **实锤+根因补强** | 关闭为 **#30067 重复**: 长会话 50-80 轮 agent 循环 delta O(N²) 累积 — 已回写 §8.6.1, 与 nemotron 长会话用法直接相关                                                                                                                                                                                                                        |
| #41701 marketplace 自动更新破坏         | **实锤+状态披露** | v2.1.87; staging→production 换页不完成; manifest 丢失被对账清除; "Listening" 横幅但进程不启; **被官方标** **`invalid`** **标签后 closed as completed** — 上游未认领, 修复不可期, 更支持绕开 marketplace                                                                                                                                                   |
| #33739 schema 全灭                  | **实锤**      | semgrep index 56 `git-subdir` 不识别; \~58 插件全灭; "no skip tolerance" 逐字                                                                                                                                                                                                                                             |
| #39274 Cowork 插件秒删                | **实锤**      | `NOT_AVAILABLE` 每 sync 周期删除; VM 进程 \~1s SIGTERM; **closed as not planned**                                                                                                                                                                                                                                       |
| systemprompt.io ZIP hooks 静默忽略    | **实锤**      | 原文 "Hooks defined in plugins uploaded via ZIP are silently ignored in Cowork. Not just HTTP hooks. All hooks"; "Claude Code CLI is unaffected"; 非 github.com 源拒绝逐字确认                                                                                                                                             |

**修正记录**:

1. **#20623 根因修正**: 原表记"跳版本升级→插件缓存过期"有误 — 实际根因是 **v1.3.8 plugin loader 重构 (PR #20112) 破坏 NAPI 原生模块解析** (与缓存/跳版本无关), 已改写 §8.6.1。
2. **元断言修正**: §8.7 原表声明 §8.6 证据"均为本会话直接抓取"系夸大 (实为搜索快照 E2) — 已在 §8.7 表内更正; 本节直抓完成后才真正达成 E1。教训: **审计记录中的证据等级声明本身也要被审计**。

**二轮增量发现 (claude code hooks 层故障, 来自已核实文章的汇总表; §8.9 三轮已逐一直抓升级 E1)**: hooks 双重触发 ([#24115](https://github.com/anthropics/claude-code/issues/24115), marketplace 源+已装缓存各触发一次)、PreToolUse "blocking" hooks 被模型**无告警绕过** ([#31250](https://github.com/anthropics/claude-code/issues/31250))、plugin `hooks.json` 的 command hooks 静默丢弃 ([#34573](https://github.com/anthropics/claude-code/issues/34573))、Let's Encrypt ECDSA 证书被拒 ([#31777](https://github.com/anthropics/claude-code/issues/31777))。**对 D5 的含义**: 自制 skill Phase 2 若走 claude code hook 路线, 31250/34573 表明 hook 执行本身不可靠 — 再添一条"Phase 1 prompt 契约为准"的理由。

### 8.9 三轮补验: 承重断言直抓升级 (2026-09-02)

> 方法: 文档内引用但证据仍为 E2 的 7 个载荷 (5 个 claude code issue + #30067 + lancedb 兼容矩阵) 逐一 WebFetch 直抓。结果: **7/7 实锤, 1 处版本修正**。

| 断言                                    | 判定               | 直抓核实要点                                                                                                                                                                                                                                                                                                                                 |
| ------------------------------------- | ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| #30067 O(N²) 长循环退化 (§8.6.1 承重断言)      | **实锤+细节补强**      | 标题逐字 "text/reasoning delta accumulation is O(N²); long agent loops hang at 50-80 turns"; headless `opencode run` 实测 \~50 轮起每步 6s→30s→60s→100s+; perf: `__memmove_avx_unaligned_erms` 30.27% CPU + 7 个 JSC HeapHelper GC 线程常驻; 根因 `session/processor.ts` 两处 `text += chunk` rope 反复扁平化; **issue Open, 修复 PR #42150 已在途** — 版本锁定选型时可评估纳入 |
| #40153 marketplace 目录删除               | **实锤**           | auto-update **先删目录后 re-clone**, re-clone 失败(网络/限速)即裸; `Plugin X not found in marketplace Y`; closed as not planned; v2.1.86; 与 #41701 是**两种不同故障模式**(文件级删除 vs 非破坏性更新后静默初始化失败) — #41701 作者本人明确区分, §8.6.2 "同类"表述准确                                                                                                                        |
| #31250 PreToolUse 静默绕过                | **实锤+nuance 披露** | hook 注册+模式匹配验证正确但**未触发**, 锁文件未建, 模型谎称 "impossible to circumvent"; **closed as not planned**; nuance: 该 issue 混合两层故障(hook 基础设施未触发 + 模型不自执行 mandatory 程序), 单报告者, Windows                                                                                                                                                                 |
| #34573 command hooks 静默丢弃             | **实锤**           | plugin `hooks.json` 的 **command hooks 仅在 PreToolUse/PostToolUse 被丢弃**, 同事件 prompt hooks 正常, 生命周期事件(SessionStart/Stop/PreCompact 等) command hooks 正常; `/hooks` 菜单证实缺失; 最小复现(timestamp 日志脚本)失败; closed as not planned; v2.1.63                                                                                                           |
| #31777 ECDSA 证书被拒                     | **实锤**           | Let's Encrypt **E7 中间证书**被拒 "unknown certificate verification error"; 捆绑 TLS 忽略系统 CA 库 + 全部三个环境变量 (NODE\_EXTRA\_CA\_CERTS/SSL\_CERT\_FILE/NODE\_TLS\_REJECT\_UNAUTHORIZED); curl/node/openssl 同机均正常; closed as not planned; v2.1.71; 报告者目标服务器即 systemprompt.io 本身                                                                      |
| #24115 hooks 双重触发                     | **实锤+高相关**       | 根因: 同一 `hooks.json` 在 marketplace 源目录与已装缓存 (`~/.claude/plugins/marketplaces/` 与 `~/.claude/plugins/cache/`) **两处均被加载**; closed as not planned; **复现用例正是 claude-mem\@thedotmack 9.0.17** — 本集群 D5 候选插件本尊, 若装须检查双触发副作用                                                                                                                   |
| lancedb-opencode-pro 兼容矩阵 (Effect 断言) | **实锤+版本修正**      | 矩阵逐行: v1.2.0-1.3.7 稳定 / v1.3.8-1.3.13 conditional / v1.3.14+ 恢复 / **v1.4.4 起** **`ask()`** **返回 Effect**; 矩阵将 v1.3.8-13 症状记为 "fresh install 可用, 跳版本升级后失效" — 与 #20623 的 loader 重构根因**相容**(重构致缓存内旧解析路径失效), 非矛盾; 修正: Effect 化始于 **v1.4.4** 非 v1.4.7, 已改 §8.6.1                                                                            |

**修正记录**: ① Effect 断言版本 v1.4.7+ → **v1.4.4+** (§8.6.1 已改); ② 二轮增量发现中 4 个 claude code issue 由 E2 (文章汇总表) 升级为 E1 (直抓), 上文已加注。

**对 D5 的增量含义**: ① #30067 修复 PR #42150 在途 — opencode 版本锁定选型时评估是否选含此修复的版本 (O(N²) 是 nemotron 长会话的直接性能税); ② #24115 复现用例 = claude-mem 本尊 — D5 T5 记忆插件试点若选 claude-mem, 验收项须含"hooks 无双触发"; ③ #31250/#34573/#31777/#24115 四件全部 closed as not planned — claude code hooks 层的可靠性问题**上游零认领**, "Phase 1 prompt 契约为准"从工程偏好升级为不可回避约束。

**本节参考**: \[F:\semantica-main (本地实测: plugins/skills/{provenance,explain}/SKILL.md, .claude-plugin/plugin.json)] · [Anthropic: Reduce hallucinations (官方)](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations) · [Anti-Hallucination Stack (claudecodeclub)](https://www.claudecodeclub.ai/free-resources/anti-hallucination-stack) · [deglaze (GitHub)](https://github.com/LuciferDono/deglaze) · [paper-review.skill (GitHub)](https://github.com/jam-cc/paper-review.skill) · [adversarial-review (GitHub)](https://github.com/ng/adversarial-review) · [ultracodex (GitHub)](https://github.com/KingGyuSuh/ultracodex) · [Codex 桥 adversarial-review 解析 (harnez.ai)](https://harnez.ai/posts/codex-plugin-claude-code/) · [Auditor Prompt Integrity spec (michael-conrad/.opencode#704)](https://github.com/michael-conrad/.opencode/issues/704) · [ARS 三层引用锚点 (brightcoding 评测)](https://prompts.brightcoding.dev/blog/stop-writing-papers-alone-claude-code-ars-is-the-secret-weapon-top-researchers-use) · [Claude Code Operator's Guide (evidence discipline)](https://macollins27.github.io/cc-guide/claude-code-guide.pdf) · §8.5: [ARS OpenCode 移植版 (timpara/opencode-academic-research)](https://github.com/timpara/opencode-academic-research) · [CiteAgent (Areopaguaworkshop/citeagent)](https://github.com/Areopaguaworkshop/citeagent) · [oy (adonm/oy-cli)](https://github.com/adonm/oy-cli) · [oh-my-review-experts (zapsaang)](https://github.com/zapsaang/oh-my-review-experts) · [adlc (voodootikigod/adlc)](https://github.com/voodootikigod/adlc) · [opencode-gemini-search (@happycastle)](https://github.com/happycastle114/opencode-gemini-search) · §8.6: [opencode#26557 api.command 移除](https://github.com/anomalyco/opencode/issues/26557) · [OMO#5575 V2 hook API 静默失效](https://github.com/code-yeongyu/oh-my-openagent/issues/5575) · [opencode#23891 ripgrep 下载挂死](https://github.com/anomalyco/opencode/issues/23891) · [opencode#29129 流冻结](https://github.com/anomalyco/opencode/issues/29129) · [claude-code#41701 marketplace 自动更新清空插件](https://github.com/anthropics/claude-code/issues/41701) · [claude-code#33739 官方 marketplace schema 全灭](https://github.com/anthropics/claude-code/issues/33739) · [systemprompt.io: Building on Quicksand](https://systemprompt.io/guides/building-on-quicksand-claude-breaking-changes)

***

## 9. 补充调研: Hermes Agent 编排机制与社区编排案例 (2026-09-04)

> 背景: 主控站已安装 Hermes Agent（`C:\Users\Peng\.hermes\hermes-agent`，Nous Research）。本节 = Hermes 编排**源码实读**结论 + 社区编排**框架**综述。与 §2/附录 C（多 agent 降幻觉）互补——附录 C 讲「实践纪律」，本节讲「编排框架机制」。spec 侧落点见 `spec/d6-agent-standard/BLINDSCAN-v2-orchestration.md §8.6.3`。

### 9.1 Hermes 编排架构（源码证据）

| 模块 | 职责 | 关键机制（源码行证） |
| --- | --- | --- |
| `tools/delegate_tool.py` | 子代理委托（单/批） | `DELEGATE_BLOCKED_TOOLS` 子代理禁用 `delegate_task/clarify/memory/send_message/cronjob`（防递归/用户交互/共享内存/副作用/越权调度）；`_DEFAULT_MAX_CONCURRENT_CHILDREN=10`；批模式用 `DaemonThreadPoolExecutor(max_workers=max_children)` **join 自身**——fan-out 必须全部完成才产出一份汇总，父轮次用 `wait()` 短超时轮询以支持中断退出（避免 `as_completed()` 卡死）。子代理各自独立 `task_id` → 独立 terminal session + file-ops 缓存（**工作区隔离**） |
| `agent/subagent_lifecycle.py` | 子代理生命周期（插件契约） | 状态机 `PENDING→STARTING→RUNNING→(SUCCEEDED/FAILED/INTERRUPTED/CANCELLED)`；`_EXECUTOR=DaemonThreadPoolExecutor(max_workers=8)`；终端态保留 3600s 后清理；handle 用 **HMAC capability 校验**防伪造；`role ∈ {leaf, orchestrator}`——嵌套委托靠 `orchestrator` 角色显式授予，非模型自决 |
| `tools/async_delegation.py` | 异步委托/并行工作流 | 持久化 daemon executor（不随 `with` 块销毁）；`_persist_dispatch/_persist_completion` **落盘任务记录**，跨进程重启可恢复；完成经 `process_registry.completion_queue` 回传；批模式逐任务持久化+单份合并结果回传 |
| `agent/moa_loop.py` | MoA（Mixture of Agents） | 非模型工具、斜杠命令标记单轮 MoA；`call_llm` 并行查询**参考模型**（`_MAX_REFERENCE_WORKERS=8`），全 in-flight 收集完成后由**聚合器**综合；一次性（参考模型互不可见、无迭代）；带 PII 脱敏 |
| `batch_runner.py` | 离线批量数据跑批 | `multiprocessing.Pool(processes=num_workers)` 批并行；每批独立 `batch_*.jsonl` + 增量写 + `os.fsync`；`checkpoint.json` + **按内容匹配已完成 prompt** 的 resume（不靠索引）——崩溃后只补未完成 |

### 9.2 Hermes 官方路线

**官方 issue #344（multi-agent 愿景）**：当前 `delegate_task` 是「委派」非「多智能体」——子代理**不可互谈、不可共享状态、无依赖感知**（批任务全平行）、无崩溃恢复、无健康监控、无重试、无合成步骤。拆出的子 issue 借鉴 CAMEL-AI/OpenPlanter：验收准绳+独立裁判（#356）、Inception harden 子代理 prompt（#375）、对抗式辩论（#376）、共享内存池（#377）。**这印证「依赖 DAG、可恢复重放、健康监控」是编排的普遍空缺**（对照 D6 BS-4/BS-5）。

### 9.3 社区编排案例对比（2026-03/04 综述）

| 框架 | 编排模型 | 持久化/恢复 | 与本集群的相关点 |
| --- | --- | --- | --- |
| **Gas Town**（Mayor/Polecats） | 层次+角色：Mayor 编排分发，Polecats 并行 worker | **git hooks 作状态机**，靠 git 历史跨重启存活 | 「git 即状态」异构版任务卡；但状态在 git 非独立 DB |
| **OpenAI Agents SDK**（Swarm 继任） | Mesh/handoff：Agent 间握手转移 | 无状态+外部 memory | 最小抽象；D6 是单工作区排它锁，非自由握手，不需要 |
| **LangGraph 1.0** | 图/DAG：节点=agent，边=转移；条件分支/并行边/子图 | **逐步 checkpoint** + `interrupt()` 时间旅行调试 | BS-5「按 key 重放」可借鉴其 checkpointed state |
| **CrewAI**（v1.10+，46K★） | 角色/团队 + Flows（事件驱动确定性骨架） | `@persist()` 工作流状态**可恢复**；agents 持久认知记忆 | 角色分工+Flow 骨架分离 = 确定性控制面与推理面解耦，与 D6「确定性 wrapper + agent 推理」同构 |
| **AutoGen** | Group chat：多 agent 对话环 | 弱（无生产部署/重试） | 反例：缺恢复即不可生产 |
| **Temporal**（非 agent 专用） | 持久执行平台；workflow 落库 + 从 checkpoint 重放 | **内建重试语义/状态管理** | BS-5 耐久性参考底座 |
| **Tonbi / Hermes Kanban** | **SQLite 看板为唯一事实源**；调度器分发卡片→代理；并行 worker；崩溃即取未完成卡片续跑 | 单 SQLite 文件，无消息队列无轮询；自愈（死任务回收重生） | **与本集群高度同构**：任务卡 + 单文件状态 + 崩溃续跑 + 事件驱动 + 可审计 |

### 9.4 与本集群的关系（D6 V2 落点摘要）

1. **工作区隔离已验证成熟范式**: Hermes 子代理独立 `task_id`、Tonbi 单看板——D6「单工作区单写者」与业界隔离思路一致，**保留**。
2. **BS-5 可吸收两种成熟持久化**: batch_runner「按内容 resume」+ LangGraph/CrewAI「@persist/checkpoint」，叠加现有「任务卡 key + 孤儿锁幂等」→ 二期重放更稳。
3. **BS-2（网关纯串行扇出）的规避备选**: Hermes 用 `ThreadPoolExecutor` **进程内真并行**绕开网关 parallel_tool_calls 方言问题 → 提示 D6 若要「单轮多子代理发起」，**同站进程内多线程**可作规避备选（代价：同站统一内存带宽竞争，回 BS-6 结论，仍倾向跨站扇出）。
4. **编排「依赖 DAG / 健康监控 / 崩溃恢复」普遍空缺**: 连 Hermes 官方都把「委派→多智能体」列为未竟愿景、CrewAI 用 Flow 骨架补确定性、Temporal 用外部平台补耐久 → D6「确定性 wrapper + 任务卡状态机」方向正确，**无需追这些框架**。

**本节参考**: 本机 `C:\Users\Peng\.hermes\hermes-agent` 源码（delegate_tool.py / subagent_lifecycle.py / async_delegation.py / moa_loop.py / batch_runner.py）· [Hermes Agent 官方文档](https://hermes-agent.nousresearch.com/docs/) · [Hermes Agent GitHub](https://github.com/NousResearch/hermes-agent) · [Hermes multi-agent 愿景 issue #344](https://github.com/NousResearch/hermes-agent/issues/344) · [Agent Orchestration Frameworks Compared (getbeam)](https://getbeam.dev/blog/agent-orchestration-frameworks-compared-2026.html) · [Top 5 Open-Source Agent Orchestration Platforms (orloj)](https://www.orloj.dev/blog/top-5-agent-orchestration-platforms) · multi-agent topology 综述（附录 C 已有链接）

---

# 附录 A: OpenCode CLI 生态调研全文 (subagent 检索原始输出)

> 检索时间: 2026-09-01 · 检索工具: Trae general\_purpose\_task subagent (web 调研)
> 归档目的: 正文 §2.2/§3 的依据溯源

**背景说明**：OpenCode 于 2025-06-19 由 SST（Serverless Stack）团队发布，2026 年该团队更名为 **Anomaly**，仓库已从 `sst/opencode` 迁移至 **`anomalyco/opencode`**（旧链接自动重定向）。MIT 协议，GitHub Star 超 18 万，支持 75+ LLM 供应商（通过 models.dev），提供 TUI / Desktop（beta）/ Web / SDK 多形态。

## A.1 最新版本号及 Changelog 要点

**最新稳定版：v1.18.25（2026-08-28 发布，GitHub Releases API 确认）**；npm 包名 `opencode-ai`，可通过 `opencode upgrade` 升级、`opencode doctor` 体检。

v1.18 系列（2026 年 7-8 月）要点：

- **Desktop v2 默认启用**（桌面端 beta 转正推进中）；同时存在 **V2 引擎（`opencode2`，beta）** 双轨并行，支持 standalone 模式，V1 已能读取 V2 配置字段保持兼容。

- **v1.18.2**：Agent 深度限制（防止子代理无限嵌套）。

- **v1.18.19**：Cloudflare AI Gateway 原生 OpenAI/Anthropic passthrough；Codex 速率限制对齐 ChatGPT 订阅额度。

- **v1.18.20**：子代理失败可恢复（surface resumable `task_id`）、大量网络错误重试强化、`opencode run` 下子代理权限请求应答。

- **v1.18.23**：Cloudflare AI Gateway 第三方 provider 路由修复；Azure 支持 Entra ID CLI 登录。

- **v1.18.17**：会话压缩（compaction）保留完整近期轮次、Vertex AI 多区域 Gemini 路由。

- 历史里程碑：v1.0.190 起 **Skills 原生化**；v1.1.48（2026-01）Skills 可作为斜杠命令调用。

## A.2 MCP 支持方式与配置语法

配置入口：项目根 `opencode.json` / `opencode.jsonc`，全局 `~/.config/opencode/opencode.json`，`$schema: "https://opencode.ai/config.json"`。支持 **本地（stdio）** 与 **远程（Streamable HTTP）** 两类，工具自动注入 LLM 上下文（按名称引用，如 `use the xxx tool`）。

**V1 语法（当前稳定版，顶层** **`mcp`** **字段）：**

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    // 本地 stdio 服务器
    "filesystem": {
      "type": "local",
      "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
      "environment": { "MY_VAR": "{env:MY_VAR}" },  // {env:NAME} 占位符替换
      "enabled": true,
      "timeout": 30000
    },
    // 远程 Streamable HTTP 服务器
    "context7": {
      "type": "remote",
      "url": "https://mcp.context7.com/mcp",
      "headers": { "CONTEXT7_API_KEY": "{env:CONTEXT7_API_KEY}" },
      "oauth": false   // 纯 API Key 认证时必须显式关闭，否则 401 会被误判为 OAuth 挑战
    },
    // 远程 + 预注册 OAuth 客户端
    "sentry": {
      "type": "remote",
      "url": "https://mcp.sentry.dev/mcp",
      "oauth": { "clientId": "{env:CLIENT_ID}", "clientSecret": "{env:CLIENT_SECRET}", "scope": "tools:read tools:execute" }
    }
  }
}
```

- OAuth 默认自动发现（PKCE + 动态客户端注册 + token 刷新），凭据存于项目配置之外；组织可通过 `.well-known/opencode` 下发默认服务器。

- 支持**按 agent 覆盖 MCP**（agent frontmatter / `agent` 配置内的 `mcp` 字段）。

- CLI 管理命令：`opencode mcp auth <name>`、`opencode mcp auth list`、`opencode mcp logout <name>`、`opencode mcp debug <name>`（诊断 OAuth/连接）。**没有** `claude mcp add` 式的 `opencode mcp add`，添加服务器主要靠编辑配置文件。

**V2 语法（beta，结构改为嵌套 + snake\_case）：** 服务器放入 `mcp.servers.<name>`，`enabled` 改为语义相反的 `disabled`，OAuth 字段为 `client_id/client_secret`，新增 `codemode`（默认 true，工具经 Code Mode 暴露）与 `cwd` 选项。

## A.3 Agent / 子代理自定义（Custom Agents）

两类代理：**primary**（Tab 键循环切换，内置 Build 全工具 / Plan 受限只读）与 **subagent**（内置 General、Explore、Scout；通过 **@mention** 或主代理自动派发调用）。v1.18.20 后子代理失败可恢复。

**方式一：Markdown + YAML frontmatter（推荐）**，放 `.opencode/agents/<name>.md`（项目）或 `~/.config/opencode/agents/<name>.md`（全局）：

```markdown
---
description: Reviews code for quality and best practices
mode: subagent              # primary | subagent | all
model: anthropic/claude-sonnet-4-5
temperature: 0.1
steps: 20                   # 最大迭代步数（旧 maxSteps 已弃用）
color: "#4CAF50"
permission:                 # 新权限系统（旧 tools 布尔写法已弃用，会自动迁移）
  edit: deny
  bash:
    "*": ask
    "git diff": allow
  skill:
    "internal-*": deny
---
You are in code review mode. Focus on code quality, bugs and security.
```

**方式二：JSON 配置**（`opencode.json` 的 `agent` 字段，可覆盖内置代理如 `plan`）。未知 frontmatter 键会自动收集进 `options` 并透传给 provider（如 `thinking`、`budget_tokens`）。

调用方式：`opencode --agent <name>`、TUI 内 @mention、Tab 切换。社区有大量现成 agent 集合（如 Shakudo-io/opencode-agents）。

## A.4 Skills 与插件机制

**Skills（v1.0.190 起原生）**：原生 `skill` 工具 + **懒加载**（仅 name/description 预载入工具 schema，正文按需读取），遵循 Agent Skills 开放标准（agentskills.io）。发现路径（项目级向上遍历至 git 根）：

- `.opencode/skills/<name>/SKILL.md`（原生）、`~/.config/opencode/skills/`（全局）

- **兼容路径：`.claude/skills/`、`.agents/skills/`（项目与全局均可）**

```markdown
---
name: git-release                      # 1-64 字符，小写+单连字符，须与目录名一致
description: Create consistent releases and changelogs   # 1-1024 字符
license: MIT
compatibility: opencode
metadata: { audience: maintainers }
---
## What I do
- Draft release notes from merged PRs ...
```

权限控制：`permission.skill` 支持 glob 模式（`"internal-*": "deny"`、`"experimental-*": "ask"`），可按 agent 覆盖或整体禁用 `skill` 工具；另可在配置中用 `skills.paths` 添加自定义目录。2026 年初起 skills 可直接作为 `/skill-name` 斜杠命令调用。原社区插件 `opencode-skills` 已归档（功能被官方 PR #5930 / #6000 吸收）。

**插件（`@opencode-ai/plugin`** **SDK）**：JS/TS 模块（Bun 运行时，直接写 TS），两种加载方式——本地 `.opencode/plugins/*.ts` 与 `~/.config/opencode/plugins/`（自动加载）；npm 包写入配置（启动时 bun 自动安装缓存到 `~/.cache/opencode/node_modules/`）：

```jsonc
{ "plugin": ["opencode-helicone-session", "opencode-wakatime", "@my-org/custom-plugin"] }
```

```typescript
// .opencode/plugins/custom-tools.ts
import { type Plugin, tool } from "@opencode-ai/plugin"
export const CustomToolsPlugin: Plugin = async (ctx) => {
  return {
    "tool.execute.before": async (input, output) => { /* 拦截/改写工具执行 */ },
    tool: {
      mytool: tool({
        description: "This is a custom tool",
        args: { foo: tool.schema.string() },
        async execute(args) { return `done: ${args.foo}` }
      })
    }
  }
}
```

可用 hook：`event`（session.idle 等全事件）、`tool.execute.before/after`、`shell.env`、`experimental.session.compacting` 等；外部依赖放 `.opencode/package.json`（启动时自动 `bun install`）。另有自定义命令 `.opencode/command/*.md`（支持 `$ARGUMENTS`、`$SHELL{}` 模板变量）。V2 有 `@opencode-ai/plugin/v2` API。

## A.5 与 Claude Code 生态的兼容性

| 资产                              | 能否复用    | 说明                                                                                                                                                                    |
| ------------------------------- | ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **CLAUDE.md**                   | ✅ 直接    | 官方 fallback：无 `AGENTS.md` 时自动读取项目/全局 `CLAUDE.md`                                                                                                                      |
| **Skills（.claude/skills/）**     | ✅ 直接    | 原生扫描 `.claude/skills/*/SKILL.md` 与 `~/.claude/skills/`，同一份文件双工具共用；未知 frontmatter 字段（`allowed-tools`、`user-invocable` 等）被忽略                                            |
| **MCP server 本体**               | ✅（协议标准） | server 进程/URL 完全复用；**但不读取** **`.mcp.json`** **/** **`~/.claude.json`**，需转换写入 `opencode.json`                                                                          |
| **Agents（.claude/agents/）**     | ⚠️ 需转换  | 同为 Markdown+frontmatter，搬到 `.opencode/agents/` 并调整字段（`tools: Read, Edit` CSV → 权限对象；`model: sonnet` → `anthropic/claude-sonnet-4-5`）；有 claude-to-opencode 等 porter 工具 |
| **Commands（.claude/commands/）** | ⚠️ 需搬迁  | 复制到 `.opencode/command/`，内容基本通用                                                                                                                                       |
| **Hooks**                       | ❌ 需重写   | Claude 的 settings.json+脚本范式 ≠ opencode 的 JS/TS 插件范式                                                                                                                   |
| **互操作**                         | ✅       | 支持 ACP（Agent Client Protocol），Claude Code 可经 skill 委派任务给 opencode；Multi-CLI 类 MCP server 可让多 CLI 互调                                                                   |

**MCP 配置转换示例**（Claude Code `.mcp.json` → `opencode.json`）：

```json
// Claude Code: .mcp.json                    // OpenCode: opencode.json
{ "mcpServers": {                            {
  "github": {                                  "$schema": "https://opencode.ai/config.json",
    "command": "npx",                          "mcp": {
    "args": ["-y", "@modelcontextprotocol/server-github"],    "github": {
    "env": { "GITHUB_TOKEN": "ghp_xxx" }                        "type": "local",
  },                                                             "command": ["npx", "-y", "@modelcontextprotocol/server-github"],
  "deepwiki": {                                                  "environment": { "GITHUB_TOKEN": "{env:GITHUB_TOKEN}" }
    "type": "http",                                             },
    "url": "https://mcp.deepwiki.com/mcp"                       "deepwiki": {
  }                                                               "type": "remote",
}                                                                 "url": "https://mcp.deepwiki.com/mcp"
                                                                }
                                                              }
                                                            }
```

**结论**：opencode 对 Claude Code 生态兼容性在同类工具中属于第一梯队——规则文件与 Skills **零成本复用**，MCP server **低成本转换**（一次性配置改写），agents/commands 需轻量搬移，hooks 需重写为插件；配合 ACP 还能与 Claude Code 双向协作。

**A 附录来源**:

- [OpenCode 官方 Changelog（dev.opencode.ai）](https://dev.opencode.ai/changelog)

- [GitHub Releases – anomalyco/opencode](https://github.com/anomalyco/opencode/releases)

- [官方文档：MCP Servers](https://opencode.ai/docs/mcp-servers) / [V2 MCP 文档](https://opencode.ai/v2/docs/mcp-servers)

- [官方文档：Agents（中文）](https://opencode.ai/docs/zh-cn/agents/)

- [官方文档：Skills](https://opencode.ai/docs/skills/) / [Plugins](https://open-code.ai/ko/docs/plugins)

- [opencode-skills 插件归档说明（原生 Skills 迁移指南）](https://github.com/malhashemi/opencode-skills)

- [OpenCode/ClaudeCode/Codex 目录兼容性对比](https://kimigao.com/blog/opencode-claudecode-codex-skills-folder-compatibility/)

- [官方文档：Rules（Claude Code 兼容）](https://opencode.ai/docs/fr/rules/)

- [OpenCode-Book：自定义 Agent 配置](https://github.com/0xtresser/OpenCode-Book/blob/main/ZH/%E7%AC%AC06%E7%AB%A0_Agent%E7%B3%BB%E7%BB%9F/6.5_%E8%87%AA%E5%AE%9A%E4%B9%89Agent%E9%85%8D%E7%BD%AE.md)

- [opencode.school MCP 认证排障 PR #151](https://github.com/opencodeschool/opencode.school/pull/151/files)

- [OpenCode 介绍与安装指南（CSDN）](https://blog.csdn.net/xilinxiayue/article/details/163199629)

***

# 附录 B: Claude Code CLI 扩展生态调研全文 (subagent 检索原始输出)

> 检索时间: 2026-09-01 · 检索工具: Trae general\_purpose\_task subagent (web 调研)
> 归档目的: 正文 §2.1/§3.2/§3.3 的依据溯源

## B.1 Agent Skills 机制（.claude/skills 与 SKILL.md）

**核心机制**：Skill = 一个文件夹 + 一个 `SKILL.md`（大小写敏感）。遵循渐进式披露（progressive disclosure）三级加载：① YAML frontmatter（name/description）常驻系统提示词用于路由判断；② SKILL.md 正文仅在相关时加载；③ `scripts/`、`references/`、`assets/` 按需加载。因此长参考材料平时几乎零 token 成本。

**存放位置与优先级**（同名冲突时 enterprise > personal > project；plugin 用 `plugin-name:skill-name` 命名空间隔离）：

| 级别 | 路径                                 | 生效范围            |
| -- | ---------------------------------- | --------------- |
| 企业 | managed settings 下发                | 全组织             |
| 个人 | `~/.claude/skills/<name>/SKILL.md` | 本人所有项目          |
| 项目 | `.claude/skills/<name>/SKILL.md`   | 仅本项目（可入 git 共享） |
| 插件 | `<plugin>/skills/<name>/SKILL.md`  | 启用插件处           |

**SKILL.md frontmatter 主要字段**：`name`（必填，kebab-case ≤64 字符）、`description`（必填，**自动触发的主信号**，建议写清 "Use when..."）、`allowed-tools`（预授权工具，支持 `Bash(git:*)` 作用域语法）、`argument-hint`、`model`、`disable-model-invocation`（仅允许用户 `/` 手动触发）、`user-invocable`、`mode`、`context: fork` + `agent:`（在 subagent 中运行）、`hooks`、`version/license`。正文支持动态上下文注入（行首 `` !`git diff HEAD` `` 会在加载前执行并内联输出）和 `$ARGUMENTS`/`$1` 位置参数。**自定义 slash commands 已合并进 skills**（`.claude/commands/` 旧格式仍兼容，同名时 skill 优先）。另有 monorepo 嵌套目录发现、live change detection（免重启）等特性。

**开放标准**：Claude Code skills 遵循 **agentskills.io 开放标准**，同一 SKILL.md 可跨 Claude Code、Codex CLI（`.codex/skills/`）、GitHub Copilot（`.github/skills/`，兼容 `.claude/skills/`）、OpenCode、Gemini CLI、Cursor 使用；Claude Code 在标准之上扩展了 invocation control、subagent 执行、动态注入。

**官方与社区集合**：

- **anthropics/skills**（官方，\~21.8k+ stars）：`document-skills`（docx/pdf/pptx/xlsx，source-available）、`mcp-builder`、`webapp-testing`、`algorithmic-art`、`brand-guidelines`、`skill-creator`（元技能，用来造 skill）、`template-skill` + Agent Skills 规范与模板。安装：`/plugin marketplace add anthropics/skills` → `/plugin install document-skills@anthropic-agent-skills`。

- **obra/superpowers**（社区最流行，MIT，2026 年官方 marketplace 收录，安装量 68–82 万级）：14 个方法论 skills——brainstorming → writing-plans → subagent-driven-development → test-driven-development（强制红绿重构）→ systematic-debugging → requesting/receiving-code-review → verification-before-completion 等，本质是给模型注入工程纪律。

- 其他：claude-code-plugins-plus（240+ 插件/185 skills）、VoltAgent/awesome-agent-skills、awesome-claude-skills 系列、BbgnsurfTech/claude-skills-collection（汇总索引）、claude-academic-toolkit（38+ 学术 skills）、ARIS（自主科研流水线）。

## B.2 Subagents 多代理机制（.claude/agents）

**机制**：每个 subagent 是一个 Markdown 文件（项目级 `.claude/agents/` 可入 git；用户级 `~/.claude/agents/`），拥有**独立上下文窗口**、独立系统提示、独立工具白名单与权限，干完活只把摘要返回主对话——核心价值是保护主上下文 + 并行 + 约束。

**frontmatter 字段**：`name`、`description`（Claude 靠它决定何时自动委派）、`model`（sonnet/opus/haiku/inherit，搜索类任务用 haiku 省钱）、`tools`（白名单，如 `Read, Grep, Glob`；可用 `Task(agent-type)` 语法限制可派生的下级）、`memory: project|user`（2026 新增的跨会话持久记忆）、`maxTurns`、`permissionMode`。

**内置 subagents**：`Explore`（Haiku、只读、代码检索）、`Plan`（plan mode 下做调研）、`general-purpose`（全工具）。**注意 subagent 不自动继承 CLAUDE.md 和会话历史，需在 prompt 中显式传递上下文**；subagent 原则上不能再派生 subagent。

**2026 年生态**：新增 **Agent Teams**（跨多个 Claude Code 会话的 peer-to-peer 协作，配 tmux 分屏，区别于单会话内的 subagent）、会话 fork、`SubagentStart/SubagentStop` hooks、向 subagent 预载 skills、前台/后台运行、`/agents` 交互式向导。Skill 与 subagent 的分工：**Skill 管规则（做什么怎么做），subagent 管干活（独立执行单元）**。

## B.3 Hooks 与 MCP 集成

**Hooks**：在 `settings.json` / `.claude/settings.json` / `.claude/settings.local.json` 的 `hooks` 键配置，三层结构：事件 → matcher（工具名正则，可匹配 MCP 工具 `mcp__server__tool`）→ handler。2026 年事件已扩展到 \~26 个：`SessionStart/End`、`UserPromptSubmit`、`PreToolUse`（exit code 2 可阻断工具调用）、`PostToolUse`、`Stop`、`SubagentStop`、`PreCompact/PostCompact`、`Notification`、`PermissionRequest`、`TaskCreated/Completed`、`CwdChanged`、`FileChanged` 等。handler 四种类型：**command**（stdin 收 JSON）、**http**（POST 到远端）、**prompt**（让 LLM 判断）、**agent**（可实际动手验证的子代理）；可用 `$CLAUDE_PROJECT_DIR` 引用项目内脚本。hooks 也可写进 skills 和 agents 的 frontmatter。典型用法：PreToolUse 拦截 `rm -rf`、PostToolUse 自动 prettier 格式化、Stop 时跑测试。

**MCP**：四种传输（`claude mcp add --transport http|sse|stdio|ws`），stdio 用 `--` 分隔服务端命令；三种 scope（local 默认 / project 写入 `.mcp.json` 可入 git / user）。支持 `claude mcp add-json`、从 Claude Desktop 导入、claude.ai connectors 复用、OAuth 认证、MCP tool search（大量工具时按需加载）、elicitation 交互。官方定位的类比：**MCP 提供厨房（连接与工具），Skills 提供食谱（工作流知识）**，两者是互补关系；Anthropic 官方甚至建议 MCP 集成方配一个 skill 来教用户"该怎么用这套工具"。

## B.4 编程 + 学术推理 + 金融数学/计量场景的实用组件

| 场景           | 推荐 Skills                                                                                                                                     | 推荐 MCP servers                                                                                                                                                                                                                                  |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **代码审查/TDD** | 内置 bundled `/code-review`、`/debug`、`/verify`；superpowers（test-driven-development、systematic-debugging、requesting-code-review）                 | GitHub/GitLab MCP（读 PR/issue）                                                                                                                                                                                                                   |
| **学术文献**     | ARIS（idea→review→paper 自主流水线）、claude-academic-toolkit（文献综述/答辩/发表写作）                                                                           | **Ariadne**（系统性综述 83 工具：Semantic Scholar/OpenAlex/arXiv 多源检索、PRISMA 筛选、引文网络、BibTeX/LaTeX 导出）、**zotero-mcp / zotero-library-mcp**（本地 Zotero 库检索、PDF 标注、任意 CSL 引用格式、DOI/arXiv/ISBN 入库）、paper-search 类 MCP（arXiv/PubMed/Semantic Scholar/CrossRef） |
| **LaTeX/写作** | 各学术工具包自带 latex skill；skill-creator 自建论文模板 skill                                                                                               | latex 编译类 MCP（如 research-tools 的 latex\_compile）、Ariadne 的 IEEE/ACM 模板导出 + Overleaf 上传                                                                                                                                                          |
| **数据/计量分析**  | 官方 `xlsx` skill、data-analysis-assistant（含多个统计子代理）、CSV summarizer                                                                              | DuckDB/PostgreSQL MCP（本地数据查询）、**FRED**（宏观指标：利率、CPI、VIX、收益率曲线）、Context7（实时拉取 statsmodels/PyTorch 等库文档）                                                                                                                                           |
| **金融/量化**    | Claude Equity Research、Anthropic 2026-05 发布的 10 个金融 agent 模板（Model Builder:DCF/LBO/可比公司；Earnings Reviewer；Valuation Reviewer 等，技能+连接器+子代理三合一） | **quant-mcp**（20 工具：风险指标 Sharpe/VaR/CVaR、回测、HMM 市场状态识别、regime-aware 蒙特卡洛、期权 Greeks、DCF/Piotroski/Altman、Fama-French 因子归因、组合优化，数据源全免费）、Financial Modeling Prep、Moody's（6 亿公司数据）                                                                  |
| **Web 搜索**   | 内置 WebSearch/WebFetch                                                                                                                         | Tavily、Brave Search、Exa（结构化检索）                                                                                                                                                                                                                  |

## B.5 Skills 能否在非 Anthropic 后端（本地模型经 ANTHROPIC\_BASE\_URL）下工作？

**结论：可以正常工作，且已有大量实证。** 原理：skills/subagents/hooks/MCP 全部是 **Claude Code CLI 客户端侧机制**——skill 正文与 subagent 定义由 CLI 在本地拼装进请求，hooks 由 CLI 在本地执行，MCP 由 CLI 在本地拉起进程，与后端是谁无关。只要后端说 **Anthropic Messages API** 协议，整套扩展生态即可用。

**已验证的后端**：① **Ollama**（v0.14.0+，2026 年 1 月起原生支持 Anthropic Messages API，`ANTHROPIC_BASE_URL=http://localhost:11434`）；② **LM Studio**（0.4.1+ 原生 `/v1/messages`）；③ **llama.cpp**（llama-server 原生支持，Mac 上跑 Qwen3.5-35B 等已是被广泛复制的方案）；④ **DeepSeek**（`https://api.deepseek.com/anthropic`）；⑤ **智谱 GLM**（Z.ai 官方推出 ¥20/月起的 GLM Coding Plan 专供 Claude Code 等十余款编码工具）；⑥ **Kimi、MiniMax、OpenRouter**（"Anthropic Skin" 端点，需将 `ANTHROPIC_API_KEY` 置为空串并 `/logout` 清缓存）、NVIDIA NIM（经 free-claude-code 等代理）。实证项目 ARIS 明确声明其 skills 工作流 "GLM、MiniMax、Kimi、LongCat、DeepSeek 均已测试，零 Claude/OpenAI API 依赖"。

**已知限制与注意事项**：

1. **模型名映射**：Claude Code 内部按 haiku/sonnet/opus 三档请求，需设 `ANTHROPIC_DEFAULT_SONNET_MODEL/HAIKU_MODEL/OPUS_MODEL` 指向本地模型名，或在 Ollama 里 `ollama cp qwen3-coder:30b claude-sonnet-4-6` 做别名，否则报 model-not-found。
2. **工具调用质量是真正瓶颈**：Claude Code 每一轮都是 function call，弱模型会 malform `tool_calls` 导致循环（有文档记录 480B 级开源模型在 30K token 后出现工具调用幻觉回退）。选型看 BFCL/τ-bench/SWE-bench，而非文风。
3. **skill 自动触发依赖指令遵循能力**：小模型对 description 语义匹配和"何时该用 skill"的判断明显弱于 Claude，建议对关键 skill 用 `/` 手动触发或设 `disable-model-invocation`。
4. **服务端工具不可用**：内置 WebSearch 属 Anthropic 服务端工具，第三方后端一般不支持（claude-code-router 生态里靠转换器打补丁，如某 fork 专门修 Gemini 的 finish\_reason 才让 subagent 跑通）；**替代方案是接 web-search 类 MCP server**——MCP 工具是本地执行的，不受后端影响。同理 `prompt`/`agent` 类型 hooks 内部要调 LLM，需后端可用。
5. **无 prompt caching**：本地后端每轮重编码全部历史，长会话延迟和成本上升；30 秒/轮的体验底线要求约 15 tok/s 以上生成速度。
6. 多后端混合可用 **claude-code-router**（按任务路由到不同厂商，subagent 用 `<CCR-SUBAGENT-MODEL>` 标记路由）或 claude-code-delegate-local（主会话留在 Anthropic、子代理外派本地模型）。

## B.6 安装配置示例

**① 最小 Skill**（`~/.claude/skills/summarize-changes/SKILL.md`）:

```markdown
---
description: Summarizes uncommitted changes and flags risks. Use when the user
  asks what changed, wants a commit message, or asks to review their diff.
allowed-tools: Bash(git diff:*), Bash(git log:*), Read
---
## Current changes
!`git diff HEAD`
## Instructions
Summarize the changes above in 2-3 bullets, then list risks (missing error
handling, hardcoded values, tests needing updates).
```

**② Subagent**（`.claude/agents/code-reviewer.md`）:

```markdown
---
name: code-reviewer
description: Expert code review specialist. Use proactively after writing or modifying code.
tools: Read, Grep, Glob, Bash
model: inherit
---
You are a senior code reviewer. Run `git diff` first; organize findings as
Critical / Warning / Suggestion, each with file:line and a concrete fix.
```

**③ Hooks**（`.claude/settings.json`）:

```json
{ "hooks": { "PreToolUse": [ { "matcher": "Bash",
      "hooks": [ { "type": "command", "if": "Bash(rm *)",
        "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/block-rm.sh" } ] } ],
  "PostToolUse": [ { "matcher": "Write|Edit",
      "hooks": [ { "type": "command",
        "command": "prettier --write \"$CLAUDE_TOOL_INPUT_FILE_PATH\" 2>/dev/null || true" } ] } ] } }
```

**④ MCP**:

```bash
claude mcp add --transport http notion https://mcp.notion.com/mcp
claude mcp add --scope project --transport stdio quant -- uvx quant-mcp
claude mcp add zotero -- uvx zotero-library-mcp   # 学术文献
/plugin marketplace add anthropics/skills          # 官方 skills 市场
/plugin install document-skills@anthropic-agent-skills
/plugin marketplace add obra/superpowers-marketplace && /plugin install superpowers@superpowers-marketplace
```

**⑤ 本地/第三方后端**（PowerShell 示例）：

```powershell
# Ollama(需 v0.14+)
$env:ANTHROPIC_BASE_URL="http://127.0.0.1:11434"
$env:ANTHROPIC_API_KEY="ollama"; $env:ANTHROPIC_AUTH_TOKEN="ollama"
$env:ANTHROPIC_MODEL="qwen3-coder:30b"
$env:ANTHROPIC_DEFAULT_SONNET_MODEL="qwen3-coder:30b"
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL="qwen3-coder:30b"
$env:ANTHROPIC_DEFAULT_OPUS_MODEL="qwen3-coder:30b"
claude
# 或 DeepSeek: BASE_URL=https://api.deepseek.com/anthropic
# 或 GLM(Z.ai Coding Plan)/OpenRouter(https://openrouter.ai/api,API_KEY 需显式置空)
```

## B.7 总结论

1. Claude Code 已形成 **Skills（知识层）+ Subagents/Agent Teams（执行层）+ Hooks（确定性控制层）+ MCP（连接层）+ Plugins（分发层）** 五位一体的扩展体系，且 Skills 通过 agentskills.io 成为跨工具开放标准，复用性极强。
2. 编程场景首选 superpowers + 内置 `/code-review`；学术场景用 ARIS/Ariadne/zotero-mcp + paper-search MCP；金融计量场景用 quant-mcp + FRED + 官方金融 agent 模板；web 检索建议用 MCP 而非依赖服务端 WebSearch。
3. **Skills 在非 Anthropic 后端完全可用**——它们是纯客户端机制；前提是后端实现 Anthropic Messages API（Ollama/LM Studio/llama.cpp/DeepSeek/GLM/Kimi/OpenRouter 均已支持），并做好模型名映射；体验上限取决于后端模型的工具调用与指令遵循能力，而非机制本身。

**B 附录来源**:

- [Extend Claude with skills — Claude Code 官方文档](https://code.claude.com/docs/en/skills)

- [Create custom subagents — Claude Code 官方文档](https://docs.anthropic.com/en/docs/claude-code/sub-agents)

- [Hooks reference — Claude Code 官方文档](https://code.claude.com/docs/en/hooks)

- [Connect Claude Code to tools via MCP — 官方文档](https://code.claude.com/docs/en/mcp)

- [anthropics/skills — GitHub](https://github.com/anthropics/skills)

- [obra/superpowers — GitHub](https://github.com/obra/superpowers)

- [Claude Academic Toolkit — GitHub](https://github.com/rafeeqinea/claude-academic-toolkit)

- [ARIS: Auto-claude-code-research-in-sleep — GitHub](https://github.com/AuroraSxh/Auto-claude-code-research-in-sleep)

- [Ariadne 学术研究 MCP — LobeHub](https://lobehub.com/mcp/cgarryza-ariadne)

- [zotero-mcp — GitHub](https://github.com/richardjlyon/zotero-mcp)

- [zotero-library-mcp — PyPI](https://pypi.org/project/zotero-library-mcp/)

- [quant-mcp — GitHub](https://github.com/irohan0/quant-mcp)

- [Top 8 Claude Skills for Finance and Quantitative Developers — Snyk](https://snyk.io/jp/articles/top-claude-skills-finance-quantitative-developers/)

- [Pairing Claude Code with Local Models — KDnuggets](https://www.kdnuggets.com/pairing-claude-code-with-local-models)

- [OpenRouter × Claude Code 集成指南](https://openrouter.ai/docs/guides/coding-agents/claude-code-integration)

- [claude-code-router — GitHub](https://github.com/musistudio/claude-code-router)

- [claude-code-delegate-local — GitHub](https://github.com/fegone/claude-code-delegate-local)

- [SKILL.md Format Reference(skillshelf)](https://github.com/timctfl/skillshelf/blob/main/skillmd-specs.md)

- [Claude Code 多 Agent 协作：Subagents 与 Agent Teams(腾讯云开发者社区)](https://cloud.tencent.com/developer/article/2652960)

- [2026 Claude Code 配置指南(CSDN)](https://blog.csdn.net/qq_73472828/article/details/160851280)

- [华尔街金融 agent 模板发布报道(掘金)](https://juejin.cn/post/7640524650062446644)

***

# 附录 C: 多 Agent 协作降幻觉社区最佳实践调研全文 (subagent 检索原始输出)

> 检索时间: 2026-09-01 · 检索工具: Trae general\_purpose\_task subagent (web 调研)
> 归档目的: 正文 §2.3/§4.2/§4.3 的依据溯源

## C.1 精炼结论（6条）

**1. 幻觉的根源是"未锁定的决策"，不是模型能力。** 社区已收敛到一个共识：AI 在 spec 缺失时会替你做决定，而这些决定就是幻觉。Qodo 数据显示给足上下文后幻觉率从 54% 降至 16%；"unhallucinate" 项目明确使用 **AI Decision Audit**（即 ADD 审计的社区对应物）：枚举代码生成中 AI 需要做的每一个决策，验证答案是否存在于 spec 中——不存在则必然被幻觉。这与你"设计方案→实施方案→质量审计→ADD审计"多轮迭代的路线完全一致，且社区正在独立收敛到同一方法论。

**2. Anthropic vs Cognition 之争已被调和：可分解性是唯一决策变量。** Anthropic 多agent研究系统（Opus 规划 + Sonnet 子agent执行）在广度优先研究任务上超单 agent 90.2%，但代价是 \~15x token；Cognition《Don't Build Multi-Agents》指出编码任务因隐式决策冲突不适合并行。2026 年社区结论：**读密集、可并行分解的任务 → fan-out 多agent；写密集、共享状态的任务 → 单线程连续上下文**。中间态用 pipeline（顺序传递）而非 orchestrator-worker。

**3. 强弱模型分工的经济学已成熟：draft-verify 模式质量不降反升。** RLM-Cascade（PayPal 生产环境）用 DeepSeek 起草、Opus 验证/增强，88.8% 请求停在草稿层，省 45.8% 成本，且质量基准 100% vs 原生 Opus 的 95%——验证者同时充当质量过滤器。FrugalGPT 级联（59–98% 节省）、RouteLLM（85% 节省保 95% 质量）构成完整谱系。**关键洞察：\~80% 的真实请求简单到小模型即可处理。**

**4. 多agent降低幻觉的机制不是"多个脑子"，而是三件事：上下文隔离（子agent是"智能过滤器"，只返回压缩后的结构化 artifact）、结构化交接（JSON schema 而非自由文本，消灭"传话效应"）、验证闭环（生成者不验证自己）。**

**5. SDD 的社区实践已分层：Spec-First（文档引导）→ Spec-Anchored（spec 与代码同步演化）→ Spec-as-Source（代码是一次性产物）。** 但批评同样成立：有损压缩（5万 token 需求 elicitation 压成 1.5万 token markdown）、维护税（spec 与代码同步是持续成本）、小任务仪式开销。成熟做法是**按海拔采纳**：跨会话/跨agent存活的工作必须 spec 化，一行修改跳过全部仪式。

**6. 学术场景的黄金模式是"rigor 拦截 + 证据外部锚定"：** Curie 的 Inter-ARM 拦截每个 agent 动作（拦截→验证→转发），较最强基线提升 3.4x；Google Co-Scientist（Nature 2026）用 Elo 辩论锦标赛排名假设 + 对 ChEMBL/UniProt 交叉验证 + 验证模块将论文数值声明与代码执行日志比对，幻觉率压到 4%。

## C.2 分领域核心数据

### C.2.1 Orchestrator-Worker 成熟案例

| 案例                 | 架构                                                                                    | 数据                                                              |
| ------------------ | ------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Anthropic Research | Opus lead + 3–5 并行 Sonnet subagent + 独立引用核查 pass                                      | +90.2%（广度优先研究eval）；token 解释 BrowseComp 80% 方差                   |
| Claude Code        | 三层：主会话 / subagents（`.claude/agents/` 自定义，YAML+MD）/ Agent Teams                        | 成本：单会话 1x → subagent 2–4x → 3-agent team \~15x → 5+ team \~25x+ |
| 内置 subagent 分工     | Explore（Haiku，只读）、Plan、General-purpose、Bash                                           | 只读探索用最便宜模型，写操作才升级                                               |
| 生产案例               | cqwerty.com 25 agent 纯 Hook 编排（Git 作为agent间通信总线）；BuzzSuite 12-agent 5波执行，52 文件零 TS 错误 | —                                                               |

社区最佳实践：lead 只持有高层计划+子agent摘要（不持有细节）；子agent返回 JSON schema artifact（含 key\_finding / sources / confidence）；限制嵌套深度（subagent 生成 sub-subagent 是反模式）；git worktree 隔离并行写操作。

### C.2.2 Plan Mode / SDD 实践

- **GitHub Spec Kit**（\~69k stars，MIT，agent 无关，30+ 工具可用）：`Constitution → Specify → Clarify → Plan → Tasks → Analyze → Implement` 七阶段，每阶段人工审查。Constitution 阶段锁定不可协商原则（架构约束/编码规范/安全规则），是降低幻觉的核心杠杆——所有后续决策对齐它。

- **Kiro**（AWS，GA 2025.11）：`requirements.md（EARS 语法：WHEN [条件] THE SYSTEM SHALL [行为]）→ design.md → tasks.md` 三阶段门控 + 任务依赖分析并行执行（大 spec 实施时间降至 1/4）。批评集中在定价（vibe/spec 请求分离导致重度用户 $550+/月）与厂商锁定。

- **BMAD Method**（\~35k stars）：虚拟敏捷团队（Analyst→PM→UX→Architect→PO 验证），planning 阶段用 web UI、execution 阶段切 IDE。

- **Plan mode（Claude Code/Cursor）**：本质是"短暂的 spec"——只读探索+人批准后才执行，但不版本化。定位：短生命周期任务的轻量替代。

### C.2.3 模型分工与幻觉抑制

- **级联触发器（2026 共识）**：超时 / 重试耗尽 / **JSON schema 验证失败** / 置信度阈值未过 → 升级到贵模型。其中 validation gate 是最常被忽略却最有效的——它拦截"看起来合法的错误答案"。

- **RAG 接地**：幻觉 8% → 0.3%（生产数据）。检索先行 + 引用强制。

- **交叉验证三形态**：(a) 对外部数据库锚定（Co-Scientist 对 ChEMBL/UniProt）；(b) 对执行日志锚定（数值声明 vs 代码实际输出）；(c) 多源一致性（多agent独立检索后比对）。

- **多模型投票/辩论**：Co-Scientist 的 Elo 锦标赛（两两辩论动态排名）优于一次性打分；TradingAgents 的多空辩论消除确认偏误。

- **对本架构直接可抄的**：RLM-Cascade 的规则路由——简单 agentic 轮次直接走本地模型（\~2% Opus 成本），schema 关键的工具调用轮次直通强模型，复杂轮次走 draft→verify。

### C.2.4 学术/量化研究 Agent 案例

| 系统                                            | 核心机制                                                                                            | 量化结果                          |
| --------------------------------------------- | ----------------------------------------------------------------------------------------------- | ----------------------------- |
| **Curie**（UMich，开源）                           | Intra-agent rigor（策略校验：计划对齐目标、setup 可复现）+ Inter-ARM 拦截转发 + 实验知识模块                               | 3.4x 超最强基线                    |
| **Co-Scientist**（DeepMind+100 机构，Nature 2026） | 7-agent：Supervisor + 生成/评审/排名(Elo)/进化/Meta-review/Proximity；三阶段 Generation→Reflection→Evolution | 幻觉率 4%；两天解决十年超级细菌问题（AMR 假设）   |
| **TradingAgents**（UCLA/Tauric，AAAI 2025）      | 4分析师→多空辩论→Trader→风控团队（否决权）→PM；LangGraph 状态机；ChromaDB 记忆学习历史决策                                   | 累计收益/Sharpe/最大回撤全面超单 agent 基线 |
| **AI Scientist v2**                           | 端到端：文献→想法→实验→写作                                                                                 | 已产出 workshop 级论文              |

TradingAgents 的两个可复用细节：(1) 结构化 `AgentState`（各报告+辩论状态+决策结果统一对象）消灭自然语言传话的信息损耗；(2) 风控 agent 是一等公民带**否决权**，不是顾问——这是量化场景治理的关键设计。

## C.3 可复用架构模式清单（10 模式完整版）

| #  | 模式                              | 结构                                                                    | 幻觉抑制机制                 | 适用                      |
| -- | ------------------------------- | --------------------------------------------------------------------- | ---------------------- | ----------------------- |
| 1  | **Orchestrator-Worker**         | 强模型规划 + N 个隔离上下文弱模型并行 + 结构化 artifact 回传                               | 上下文隔离=智能过滤；压缩交接        | 读密集、可分解（文献扫描/多源数据采集）    |
| 2  | **Planner-Generator-Evaluator** | 规划、生成、批评三角色分离                                                         | 生成者不验证自己               | 任何高风险产出                 |
| 3  | **Draft-Verify 级联**             | 便宜模型起草 → 验证门（schema/置信度/超时）→ 贵模型接受/增强/重写                              | 验证者=质量过滤器；80% 请求停在草稿层  | 高吞吐流水线（三机集群+云端强模型的天然形态） |
| 4  | **Spec 门控流水线**                  | Constitution → Specify → Clarify → Plan → Tasks → Implement，阶段间人工/审计门 | 决策前置锁定；spec 提供可 QA 的基准 | 跨会话存活的工作（工具链/论文项目）      |
| 5  | **Rigor 拦截器**（Curie 式）          | 每个 agent 动作：拦截 → 策略验证 → 转发                                            | 动作级而非输出级验证             | 实验执行、数据管道               |
| 6  | **证据外部锚定**（Co-Scientist 式）      | 数值声明 vs 执行日志比对；关键证据 vs 外部数据库                                          | 幻觉无处藏身                 | 计量结果、论文数值               |
| 7  | **对抗辩论 + Elo 排名**               | 多空/正反 agent 结构化辩论，两两对决动态排名                                            | 消除确认偏误；多轮竞争淘汰弱假设       | 假设筛选、策略评估               |
| 8  | **否决权风控层**（TradingAgents 式）     | 风控 agent 一等公民，可否决执行                                                   | 单点过度自信被制度性拦截           | 交易/生产系统治理               |
| 9  | **验证门 fallback 链**              | 超时/重试/schema 失败/低置信 → 逐级升级                                            | 拦截"看起来合法的错答案"          | 本地↔云端混合                 |
| 10 | **记忆增强迭代**                      | 历史决策+结果向量化存储，检索注入                                                     | 同类错误不重犯                | 长期研究项目                  |

## C.4 对 Research OS 的直接映射（3点）

1. **三机集群的天然形态 = Pattern 3 + 9**：A/B 工作站跑本地模型做检索/草稿/数据清洗（80% 流量），云端强模型只做规划、审计、最终合成；validation gate 用 schema 校验（便宜且确定）而非 LLM 判断。
2. **ADD 审计与社区收敛点重合**："AI Decision Audit" 的表述说明该模式已有独立命名和开源实现，可在论文/工具文档中直接引用对齐（unhallucinate, Qodo 2025）。
3. **量化研究 agent 的缺失环节 = Pattern 6**：社区有 Co-Scientist 的日志比对，但**没有**针对回测的场景——"论文声明数值 vs 回测引擎实际输出"的强制比对是空白，与形式化验证层（Lean4）可形成互补：Lean4 验证理论，日志锚定验证数值。

**C 附录来源**:

- [Anthropic: How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)

- [Multi-agent is not an architecture decision. It is a workload decision.](https://agenticlab.sunilprakash.com/signal/003-multi-agent-decision-variable/)

- [Orchestrator-Worker vs Pipeline vs Swarm: How to Choose a Multi-Agent Topology](https://dreaming.press/posts/orchestrator-worker-vs-pipeline-multi-agent.html)

- [Research Report: Claude Code Multi-Agent Coordination for Software Development](https://github.com/pjloury/multi-agent-research)

- [How to Use a Smart Orchestrator Model to Direct Cheaper Sub-Agent Models in Claude Code](https://www.mindstudio.ai/blog/smart-orchestrator-cheaper-sub-agent-models-claude-code)

- [unhallucinate (AI Decision Audit / spec-driven-dev)](https://github.com/stineluca-ctrl/unhallucinate)

- [Spec-Driven Development: Spec Kit vs Kiro vs Tessl](https://dreaming.press/posts/spec-driven-development-spec-kit-vs-kiro-vs-tessl.html)

- [Spec-Driven Development: Four Approaches in Detailed Comparison](https://github.com/LLM-Coding/Spec-Driven)

- [Spec-Driven Development Is Waterfall in a Hoodie](https://airisingtrends.com/spec-driven-development-ai-coding-agents/)

- [RLM-Cascade: Response-Level Speculative Decoding for Cost-Efficient LLM API Serving](https://arxiv.org/html/2606.22840v1)

- [Cascade and Self-Verification: Try the Cheap Model First, Upgrade If Needed](https://jonathanding.github.io/llm-learning/en/articles/cascade-self-verification/)

- [How to Build a Fallback Model Chain](https://dreaming.press/posts/how-to-build-a-fallback-model-chain-cheap-model-frontier-backstop.html)

- [Curie: Toward Rigorous and Automated Scientific Experimentation with AI Agents](https://arxiv.org/pdf/2502.16069v2)

- [Google DeepMind's AI Co-Scientist now plans experiments, runs lab equipment, and writes scientific papers](https://the-decoder.com/google-deepminds-ai-co-scientist-now-plans-experiments-runs-lab-equipment-and-writes-scientific-papers/)

- [Nature｜Google 7智能体科研团队 Co-Scientist](https://sts.hunnu.edu.cn/info/1132/1247.htm)

- [TradingAgents: Multi-Agents LLM Financial Trading Framework (arXiv)](https://arxiv.org/pdf/2412.20138v3.pdf)

- [The TradingAgents Playbook: Multi-Agent AI in Financial Services](https://www.ruh.ai/blogs/tradingagents-playbook-multi-agent-ai-financial-services)

- [A Survey of AI Scientists](https://arxiv.org/pdf/2510.23045)

***

# 附录 D: 正文结论 ↔ 附录依据 索引表

| 正文结论                   | 依据出处                       | 关键数据                                                 |
| ---------------------- | -------------------------- | ---------------------------------------------------- |
| §2.1 Skills 本地后端可用     | 附录 B §B.5                  | llama.cpp 在已验证后端列表; ARIS 零 Claude API 依赖实证           |
| §2.1 四条已知限制            | 附录 B §B.5 注意事项 1-5         | 模型名映射/工具调用瓶颈/自动触发弱/WebSearch 不可用/无 caching           |
| §2.2 opencode 兼容性第一梯队  | 附录 A §A.5                  | skills 零成本/MCP 一次性转换/agents 轻搬移/hooks 重写             |
| §2.2 单一事实源策略           | 附录 A §A.4 + §A.5           | opencode 原生扫 `.claude/skills/` 与 `~/.claude/skills/` |
| §2.3 模式3 draft-verify  | 附录 C §C.1 结论3 + §C.2.3     | RLM-Cascade: 88.8% 停草稿层, 省45.8%, 质量 100% vs 95%      |
| §2.3 模式6 执行锚定          | 附录 C §C.1 结论6 + §C.2.4     | Co-Scientist 幻觉 4% (Nature 2026)                     |
| §2.3 ADD 审计独立收敛        | 附录 C §C.1 结论1              | Qodo 54%→16%; unhallucinate 项目                       |
| §2.3 回测锚定是社区空白         | 附录 C §C.4 映射3              | "论文数值 vs 回测输出"强制比对无现成实现                              |
| §3.2 superpowers 只取子集  | 附录 B §B.1                  | 14 个方法论 skills, 安装量 68-82 万级                         |
| §3.3 quant-mcp 工具清单    | 附录 B §B.4 金融/量化行           | 20 工具: Sharpe/VaR/CVaR/回测/HMM/Greeks/FF/组合优化         |
| §3.3 MCP 配置语法          | 附录 A §A.2                  | opencode V1 mcp 字段 + claude mcp add 对应命令             |
| §4.2 读密集fan-out/写密集单线程 | 附录 C §C.1 结论2              | Anthropic +90.2% vs Cognition 批评的调和                  |
| §4.3 五机制数据             | 附录 C §C.1 结论1/3/4 + §C.2.3 | 见索引各行                                                |
| §5.1 手动触发建议            | 附录 B §B.5 注意事项3            | 小模型 description 语义匹配弱                                |
| §5.4 按海拔采纳             | 附录 C §C.1 结论5              | SDD 三分层 + 批评 (有损压缩/维护税/仪式开销)                         |

