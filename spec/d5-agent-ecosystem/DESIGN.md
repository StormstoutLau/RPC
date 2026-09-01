# 设计文档：D5 Agent 生态升级与上下文管理落地

***

id: d5-agent-ecosystem-DESIGN
type: design
version: 1.2
status: draft
date: 2026-09-02
depends: \[Agent生态升级与多智能体协作架构调研 (docs/, 2026-09-02 含 §7.6 排幻觉审计版 + §8 审计任务补充调研; §8.5-§8.9 经三轮排幻觉审计: 18 载荷直抓 17 实锤 3 修正, 全部 E1)]
upstream: \[ADR-0001 集群运维框架审计与四项改进决策]
-------------------------------------

> **Feature**: D5 Agent 生态升级（两站 claude code / opencode 的技能·插件·上下文管理·跨会话记忆装备）
> **创建日期**: 2026-09-02
> **状态**: 草稿（待 Scott review）
> **Spec 步骤**: Step 3-4
> **基于调研**: [Agent生态升级与多智能体协作架构调研.md](../../docs/Agent生态升级与多智能体协作架构调研.md)（含 §7.6 审计 + §8.5-§8.9 三轮排幻觉审计，本文所有决策仅引用审计后 E1 结论）

***

## 1. 设计意图

两站 4 个 agent CLI（A/B 站 × claude code / opencode）目前**裸装**（调研 §1.1 实测：无 MCP / skills / subagents / 自定义 agents），nemotron 与 gpt-oss 的推理能力没有配套的执行生态，长 agent 任务受上下文管理缺失制约。本设计把两站 CLI 装备为"有工程纪律、有学术工具、有记忆、有窗口预算"的执行层，为调研 §4.2 五层循环（trae 规划 → 派发 → 本地执行 → 锚定验证 → 审计回环）提供本地执行侧的地基。

**核心设计立场**（继承审计后结论）：

1. **原生优先**：有更优原生插件的不迁移（superpowers v6.3.0 / anthropics document-skills）
2. **定制迁移**：原生无等价的 Scott 资产才 scp 迁移（\~10 个）
3. **Trae 兜底**：C 类外网依赖检索永久留主控站
4. **验证先行**：审计遗留的 4 个"待验证"项（F4/F5/V3/V5）设为 V0 验证门，**不通过则改道**

## 2. 预期效果

| 维度    | 现状                                   | 预期（完成后）                                                              |
| ----- | ------------------------------------ | -------------------------------------------------------------------- |
| 技能可见性 | 两站 `/` 命令列表为空（无技能）                   | 两站两 CLI 均可列出并触发 superpowers 全链（brainstorm→plan→TDD→execute）+ 定制 10 件 |
| 文档产出  | 无                                    | 两站可直接产 docx/pdf/pptx/xlsx（anthropics 生产级件，含验证-修复循环）                  |
| 上下文预算 | opencode 对自定义端点无窗口认知，长会话无界增长直到后端 400 | `limit.context` 声明后 auto-compact 在触线前触发（V1 验证后生效）                    |
| 跨会话记忆 | 每会话从零开始                              | B 站 codex-memory 试点：隔日会话能回答"上次做了什么"（闲置 6h 后台提取）                      |
| 协作地基  | 五层循环只有架构图                            | 本地执行侧就绪，为后续任务卡协议（独立 spec）提供可派发目标                                     |

**非目标（明确不承诺）**：不提升模型本身能力；不解决 B 站外网可达性（只做探测与改道）；不实现 trae 侧任务卡协议（独立后续 spec）。

## 3. 设计依据

### 3.1 调研结论 → 设计决策

| 调研发现（审计后）                                                                                      | 设计决策                                                          | 引用              |
| ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------- | --------------- |
| Skills/MCP/subagents 全是 CLI 客户端机制，与后端无关（tool-use 已 PASS 实锤）                                    | 生态装备在两站本地推进，不动推理层                                             | 调研 §2.1         |
| opencode 1.18+ 直读 `.claude/skills/`，与 claude code 零成本共用                                        | `~/.claude/skills/` 为单一事实源，一站配置两 CLI 生效                       | 调研 §2.2         |
| Trae superpowers 血统 6 件 = obra/superpowers 旧快照（E1 级逐字实证）；原生 v6.3.0 更全                          | 工程链装原生，不迁 Trae 快照                                             | 调研 §7.5 / 审计通过项 |
| anthropics document-skills 是 Claude.ai 文档功能同源生产级实现                                             | 文档处理装原生                                                       | 调研 §7.5         |
| 定制资产（math-finance-reasoning / research-\* 链 / paper-lookup / what-if-oracle）原生无等价              | scp 迁移约 10 件                                                  | 调研 §7.5 终裁表     |
| C 类检索依赖外网 API key；B 站有 github exit 28 史                                                        | 检索永久留主控站 trae；V3 探测决定 plugin 安装路径                             | 调研 §7.3-③       |
| opencode 配置格式两来源冲突（审计 F5）                                                                      | V1 验证门：以官方 schema 为准，不预设格式                                    | 审计 F5           |
| "claude code 200k 假设陷阱"系推断非实证（审计 F4）                                                           | V2 验证门：`/context` 看窗口基数，再定 claude code 长会话策略                  | 审计 F4           |
| 记忆层选型：codex-memory（纯本地）先行 → claude-mem（worker→LiteLLM 是门）P2                                    | 分两批，P2 前先过 V4 验证                                              | 调研 §6.3         |
| 多 agent 工作流 token \~15x（NVIDIA 引 Anthropic）                                                    | 上下文配置（P0）先于一切插件                                               | 调研 §6 引言        |
| opencode 长会话 O(N²) delta 累积（50-80 轮退化，#30067 E1 直抓；修复 PR #42150 在途）                            | T1 版本锁定选型时评估纳入含修复版本；nemotron 长会话为直接受影响面                       | 调研 §8.6.1/§8.9  |
| claude code hooks 层四缺陷全部 closed as not planned（#31250 绕过/#34573 丢弃/#31777 证书/#24115 双触发，上游零认领） | 自制 skill 以 Phase 1 prompt 契约为准从工程偏好**升级为不可回避约束**；hook 化仅作失效后备 | 调研 §8.8/§8.9    |
| #24115 复现用例 = claude-mem 本尊（hooks 双触发）                                                         | claude-mem P2 试点验收项强制含"hooks 无双触发"                            | 调研 §8.9         |
| adlc trust-root tier 强制跨模型审查（provider 异于 author，fail-closed）                                   | 站间互审（nemotron↔gpt-oss）设计获外部同构实证，可作验收引用                        | 调研 §8.7/§8.5    |
| gemini-search 诚实披露"结构过滤≠密码学溯源"                                                                 | assertion-audit 契约须显式声明证明力边界（防把结构校验当溯源保证）                     | 调研 §8.7         |
| opencode plugin API Effect 化始于 v1.4.4（`ask()` 返回 Effect）                                       | 记入插件开发约束台账（本设计不开发 plugin，仅备查）                                 | 调研 §8.6.1/§8.9  |

### 3.2 相关 ADR

| ADR      | 决策                         | 对本设计的影响                                    |
| -------- | -------------------------- | ------------------------------------------ |
| ADR-0001 | 收尾→重构→聚合→加固顺序；运维层补全而非重写推理层 | D5 属"生态装备"层，不触碰 infer-load / 网关，与 D1 看门狗正交 |

### 3.3 职责边界

**职责内**：两站 CLI 的技能目录、插件安装、opencode provider 上下文配置、记忆层试点、安装验证门。
**职责外**：推理服务本身（infer-load 域）；LiteLLM 网关配置（D1 已定）；trae 侧任务卡协议与派发脚本（后续独立 spec）；模型选型（model-eval 域）。

## 4. 架构设计

### 4.1 整体架构

```
主控站 (Win10)                                A/B 站 (Ubuntu)
┌─────────────────────┐   scp/rsync    ┌──────────────────────────┐
│ skills 单一事实源     │ ────────────→ │ ~/.claude/skills/        │
│ d:\RPC\ops\agent-    │                │   ├── superpowers 原生件  │ ← claude code 读
│   skills/ (git 管)   │                │   ├── document-skills    │ ← claude code 读
│ (含定制迁移件快照)     │                │   └── 定制迁移件 ×10      │ ← 双 CLI 读
└─────────────────────┘                │ opencode.jsonc           │ ← limit.context (V1 后)
                                       │   + compaction           │
                                       │ 记忆层: codex-memory (P1) │
                                       └──────────────────────────┘
```

要点：

- **单一事实源在主控站 git 仓库内**（`ops/agent-skills/`），站上 `~/.claude/skills/` 是部署产物——延续 station-bin 约定（先改仓库再同步上站，md5 可比对齐）

- **superpowers 原生件例外**：它由 plugin 机制安装并自更新（V3 通外网时）或三段式装定版（V3 不通时），**不进**单一事实源（避免与 plugin 自更新冲突）；只在台账登记版本

- 记忆层是 CLI 会话级机制，**不违反零自加载**（无常驻 systemd 服务）；claude-mem worker 若 P2 装入则新增常驻进程，届时按 D1 先例更新零自加载豁免清单（本设计内不装）

### 4.2 模块划分

| 模块       | 职责                               | 输入                        | 输出                            | 依赖                |
| -------- | -------------------------------- | ------------------------- | ----------------------------- | ----------------- |
| M1 技能库   | 单一事实源 + 部署同步                     | 定制件 + 原生件版本登记             | 两站 `~/.claude/skills/`        | git / scp         |
| M2 上下文配置 | opencode 窗口声明与压缩策略               | conf CTX 实值（131072/32768） | limit.context + compaction 配置 | V1 验证             |
| M3 记忆层   | 跨会话记忆（B 站试点）                     | opencode 会话流              | memory markdown + SQLite      | opencode ≥1.18.25 |
| M4 原生插件  | superpowers + document-skills 安装 | plugin marketplace / 三段式  | 两站 claude code 技能集            | V3 验证             |
| M5 验证门   | V0 四项前置验证                        | 审计遗留待验证项                  | GO/NO-GO 逐项裁决                 | 无                 |

### 4.3 数据流

定制技能：主控站 `ops/agent-skills/` git commit → scp 两站 → CLI 会话触发（`/` 手动为主，120B 自动触发弱，调研 §2.1 限制①）。
原生插件：marketplace 安装（V3 通）或 主控站 clone → scp → 本地 plugin 目录 → settings.json enabledPlugins（V3 不通）。
上下文配置：站上 opencode.jsonc 手工编辑（一次性，V1 定格式）。
记忆：会话闲置 6h → codex-memory 用 opencode 已配置模型（本地端点）后台提取 → markdown/SQLite。

### 4.4 控制流

```
V0 验证门 (V1→V2→V3→V5, 任一失败只影响对应模块不改全局)
  → T1 B 站 opencode 1.18.9→1.18.25 升级 (调研 §3.1 P0 前置)
  → T2 上下文配置 M2 (V1 过门后)
  → T3 原生插件安装 M4 (V3 决定路径)
  → T4 定制技能迁移 M1 (scp ~10 件 + 触发验证)
  → T5 记忆试点 M3 (B 站 codex-memory)
  → T6 验收 + 台账/手册回填
```

## 5. 配置与部署接口

### 5.1 定制技能清单（M1 迁移范围，审计后终版）

| 技能                                                                          | 依赖级             | 迁移理由（审计依据）                                                                                                                                                                                                            |
| --------------------------------------------------------------------------- | --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| math-finance-reasoning                                                      | A 纯 prompt      | 原生无等价（调研 §7.5 终裁⑤）                                                                                                                                                                                                    |
| what-if-oracle                                                              | A               | 原生无直接等价（§7.5⑥）                                                                                                                                                                                                        |
| research-scout / idea / baseline / experiment / decision / write / finalize | A ×7            | Research OS 编排链，原生无学术工作流等价（§7.5③）                                                                                                                                                                                     |
| ars-academic-pipeline                                                       | A               | 同上（§7.5③）；其三层引用锚点是学术审计的先行实现（§8.2 层2）；**部署源改用 opencode 原生移植版 timpara/opencode-academic-research**（§8.5 改判，两站原生跑不走 Trae 兜底）                                                                                             |
| assertion-audit（自制）                                                         | A               | 断言-证据等级-信息源-逻辑链输出契约——§7.6 手工审计协议技能化，生态无单一对口件（§8.3）；验收蓝本 = ARS v3.8 claim-audit 的 FNR<0.15/FPR<0.10 校准阈值（§8.5，E1 实锤）；契约须**显式声明证明力边界**（效仿 gemini-search"结构过滤≠密码学溯源"诚实披露，§8.7）；Phase 2 hook 强制降级为失效后备（§8.9：hooks 层上游零认领） |
| cross-examine（自制）                                                           | A               | 审查方规范：干净室自检+逐断言核验+结构化发现（§8.3，融合 #704 干净室/adversarial-review 怀疑论/deglaze 证据反驳）；收敛判据并入 adlc "**两连干轮+≥3 独立 lens**"（§8.7 修正后实锤）；跨模型审查立场获 adlc trust-root tier 外部同构实证（§8.5/§8.7）                                           |
| paper-lookup                                                                | B（REST 多数免 key） | P1 实测连通后定（§7.5②）                                                                                                                                                                                                      |
| **合计**                                                                      | 12-13 件         | 全部 A 级除 paper-lookup                                                                                                                                                                                                  |

### 5.2 opencode provider 声明（M2，格式以 V1 为准）

```jsonc
// 值取 conf CTX 之下留余量（120000 < 131072 / 30000 < 32768）
// 结构（嵌套 vs 平铺）与 prune 默认值以 opencode.ai/config.json schema 实测为准（审计 F5）
```

### 5.3 站侧落点

| 项           | 位置                                         |
| ----------- | ------------------------------------------ |
| 技能目录        | `~/.claude/skills/<name>/SKILL.md`（两站）     |
| opencode 配置 | `~/.config/opencode/opencode.jsonc`（两站）    |
| 记忆数据        | `~/.local/share/opencode/memories/`（B 站试点） |
| 版本台账        | `spec/d5-agent-ecosystem/` 内随 CHECKLIST 登记 |

## 6. 替代方案

### 6.1 方案 A：三层策略·原生优先（选择）

- 描述：原生 plugin 装 superpowers/document-skills，仅迁移原生无等价的定制件，C 类留主控站

- 优点：拿最新版与持续更新；迁移量最小（\~10 件 vs 213 件全迁）；维护责任外移（superpowers 上游）

- 缺点：依赖 plugin 安装路径可达（V3 门）；原生件不进单一事实源

- 选择理由：审计实证 Trae 工程链就是 superpowers 旧快照，迁它等于故意装旧版（§7.5 关键事实）

### 6.2 方案 B：全量迁移 Trae 213 件（否决）

- 描述：把主控站 Trae 技能目录整体 rsync 上站

- 优点：一步到位零挑选；离线完成不依赖外网

- 缺点：维护面 ×213；superpowers 旧快照与原生更新冲突；大量 C/D 类件站上不可用反而制造"看似有技能实则不可用"的幻觉温床

- 否决理由：违背审计精神——未验证可用性就上量，正是 §7.6 排幻觉要防的模式

### 6.3 方案 C：只做上下文配置不装生态（否决）

- 描述：仅 M2（limit.context + compaction），技能/插件/记忆全缓

- 优点：30 分钟完成，零风险

- 缺点：五层循环的本地执行侧仍是裸 CLI，检索/编排/工程纪律全缺；预期效果表大半不达

- 否决理由：与 ADR-0001"聚合"阶段意图不符；调研已实证生态在本地后端可用（§2.1）

## 7. 错误处理

| 错误场景                            | 处理方式                                                | 用户可见信息                 |
| ------------------------------- | --------------------------------------------------- | ---------------------- |
| V1 schema 校验失败（两种格式都不对）         | 按 opencode 报错提示修正，T2 阻塞但 T3-T5 照常                   | "上下文配置延后，其余模块不受影响"     |
| V3 外网不可达                        | 三段式装定版 superpowers（主控站 clone→scp→本地 plugin 目录）      | "原生插件走离线定版安装"          |
| V2 确认窗口基数 200k（陷阱成立）            | claude code 限短任务 + 手动 /compact 纪律写入手册；长会话锁 opencode | 手册新增小节                 |
| 定制技能站上触发异常（frontmatter 陌生字段，V5） | 从部署目录摘除该件，登记台账反例区                                   | 单件降级不影响整链              |
| codex-memory 后台提取失败（本地端点调用异常）   | 查 opencode 日志；记忆层整体回退 four-opencode-memory 备选       | "记忆试点降级为纯 Markdown 模式" |
| paper-lookup REST 不通（B 站）       | 该件永久留主控站（与 C 类同处置）                                  | 台账登记"站上不可用"            |

## 8. 不变式（ADD 审计依据）

1. **单一事实源不变式**：任何站上技能修改必须先改主控站仓库再同步（station-bin 同款约定）；站上直改视为违规
2. **零自加载不变式**：本设计不新增任何开机自启 systemd 服务（claude-mem worker 属 P2 且届时须先更新 D1 豁免清单）
3. **窗口余量不变式**：opencode 声明的 context 值必须 < 该路由 conf CTX 实值（120000<131072 / 30000<32768），改 conf 必须同步改声明（挂到 params-ledger 维护约定）
4. **迁移分级不变式**：上站的每件技能必须有审计可追溯的"原生无等价"依据（§7.5 终裁表），无依据不上站
5. **验证门不变式**：V0 四项未过对应的模块不得进入实施（V1↔M2，V3↔M4 路径选择，V5↔M1 单件，V2↔claude code 使用纪律）
6. **Phase 1 契约为准不变式**（§8.9 升格）：自制 skill（assertion-audit/cross-examine）长期以纯 prompt 契约运行；hook 化仅作失效后备且禁用 TUI `api.*` 面——claude code hooks 层四缺陷上游零认领（#31250/#34573/#31777/#24115）、opencode plugin API 有 patch 版内静默破坏史（#26557/OMO #5575），两侧 hook 面均不可作为承重路径
7. **证明力边界声明不变式**：assertion-audit 产出的断言表必须声明其校验的性质（结构过滤），不得表述为溯源保证——效仿 gemini-search 诚实披露（§8.7）

## 9. 幻觉排除审查（Step 4 Review）

### 9.1 设计基于已验证的调研结论

- [x] 所有设计决策可追溯到调研报告章节（§3.1 表逐行带引用；§8.5-§8.9 补充素材经三轮排幻觉审计，18 载荷 E1 直抓、3 处修正已回写并在 §8.7-§8.9 留痕）

- [x] 无未经验证的假设——审计遗留 4 项待验证全部显式设为 V0 验证门而非直接当真（F4/F5/V3/V5）

- [x] 无论证驱动的归因扭曲——"claude code 窗口假设风险"按审计降级为推断，设计只把它列为待验证项 + 无害缓解

### 9.2 替代方案审查

- [x] 3 个替代方案，各含明确否决理由（§6）

- [x] 否决理由可追溯到审计结论（B 方案否决直接引用 §7.6 审计精神）

### 9.3 职责边界审查

- [x] 职责边界清晰（§3.3，推理层/网关/任务卡协议均划出）

- [x] 不越界吞并其他研究范式

## 10. 实施阶段与测试

| 阶段                           | 内容                                                                                                                                                                                             | 测试方法                                                                                      | 依赖门 |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | --- |
| **V0 验证门** (\~30min, 决定后续路径) | V1: 站上空配置跑 opencode，按官方 schema 校验 limit.context 两种格式哪个生效；V2: 加载 gpt-oss 后 claude code `/context` 看窗口基数；V3: B 站 curl github + npm registry 连通性；V5: research-lookup 单件 scp 后 claude code 会话无报错加载 | 每项产出 GO/NO-GO 记录进 CHECKLIST                                                               | —   |
| **T1 升级**                    | B 站 opencode 1.18.9→1.18.25（npm 平台包路径，D4 已验证的备选法）；**选型时查 PR #42150（O(N²) 修复）是否已入发布版，入则选含修复版**（§8.9）；两站 `apt install ripgrep`（#23891 首跑下载挂死预防）                                                  | `opencode --version` + PONG 冒烟（调研 §1.1 同款）+ `command -v rg` 非空                            | —   |
| **T2 上下文配置**                 | 两站 opencode.jsonc 写 limit.context + compaction（V1 定的格式）                                                                                                                                        | 人为灌长对话（大文件反复 Read）观察 auto-compact 触发于 \~120k/30k 而非后端 400                                 | V1  |
| **T3 原生插件**                  | superpowers + document-skills 两站安装（V3 通=marketplace；不通=三段式）                                                                                                                                    | claude code 里 `/superpowers:brainstorm` 响应；docx 生成-验证循环跑一例                                | V3  |
| **T4 定制迁移**                  | 主控站建 `ops/agent-skills/` git 化 → scp \~10 件 → 两站验证                                                                                                                                             | 每件 `/` 列表可见 + 抽 3 件实际触发（math-finance-reasoning / what-if-oracle / research-scout）出预期结构化输出 | V5  |
| **T5 记忆试点**                  | B 站装 codex-memry（钉版本）→ 正常使用一个会话 → 闲置 6h 触发提取；**claude-mem 属 P2 范围外，V4 门通过后试点验收须含"hooks 无双触发"（#24115 复现用例即 claude-mem 本尊，§8.9）**                                                                | 次日新会话问"上次这个 repo 做了什么"，应能引用前日内容；检查 memories/ 目录有 markdown 产出                              | T1  |
| **T6 收尾**                    | 验收 + 手册（§2 网关容错后加"Agent 生态"节）+ 台账登记 superpowers 版本                                                                                                                                             | 验收标准全表过（§11）                                                                              | 全部  |

## 11. 验收标准

| #   | 验收项           | 通过判据                                                                                                                                                                                                                    | <br /> |
| --- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :----- |
| A1  | V0 四项验证       | 每项有 GO/NO-GO 结论 + 证据（截图/命令输出）进 CHECKLIST                                                                                                                                                                                | <br /> |
| A2  | 上下文配置生效       | 灌长对话至 \~120k（nemotron 路由）触发 auto-compact，无后端 400；gpt-oss 路由同理 @\~30k                                                                                                                                                    | <br /> |
| A3  | 原生技能可用        | 两站 claude code：`/superpowers:brainstorm` 有响应且走设计先行流程；document-skills 产出的 docx 过其自带验证脚本                                                                                                                                  | <br /> |
| A4  | 定制技能可用        | 12-13 件在两站 `/` 列表可见（含自制 assertion-audit/cross-examine）；抽验 3 件触发出结构化输出（六层推理框架/what-if 分支表/research 卡片）；assertion-audit 触发样例含断言表+证据等级+证明力边界声明；cross-examine 触发样例含干净室自检+逐断言核验+结构化发现（SUPPORTED/UNSUPPORTED/UNVERIFIABLE 三态） | <br /> |
| A5  | 记忆生效          | T5 判据（次日引用前日内容 + memories/ 有产出）；若降级 four-opencode-memory 则验收 MEMORY.md 增量                                                                                                                                               | <br /> |
| A6  | 单一事实源对齐       | 两站 `~/.claude/skills/` 与主控站仓库 md5 一致（除各自站特有，应为零差异）                                                                                                                                                                      | <br /> |
| A7  | 零自加载不破        | 两站 `systemctl list-unit-files --state=enabled` 无新增推理/agent 相关自启服务                                                                                                                                                       | <br /> |
| A8  | e2e 回归        | `python ops/cluster.py e2e` 退出码 0（生态装备不碰推理链路，回归应为绿）                                                                                                                                                                     | <br /> |
| A9  | 文档回填          | 手册新增 Agent 生态节 + superpowers 版本入台账 + 本 spec CHECKLIST 状态更新                                                                                                                                                              | <br /> |
| A10 | 环境就绪（稳定性审计落地） | 两站 `command -v rg` 非空（#23891 首跑下载挂死预防）；`opencode --version` 输出与台账登记版本一致（锁版本核验）；含 PR #42150 选型决策记录（选/不选含修复版，含理由）进 CHECKLIST                                                                                              | <br /> |
| A11 | 版本锁定不破        | 两站 claude code 版本与 opencode 版本登记台账并有锁定理由；无自动升级通道激活（marketplace 自动更新关闭或插件面为空——#41701/#40153 破坏链预防）                                                                                                                       | <br /> |
| A12 | 长会话预算纪律       | 手册 Agent 生态节含轮数预算指引（O(N²) 退化阈值 <50 轮，#30067）；claude code 短任务+手动 /compact 纪律（V2 结论回填）                                                                                                                                    | <br /> |

## 12. 维护管理

| 维度               | 约定                                                                                                                                                     |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 定制技能变更           | 只改主控站 `ops/agent-skills/` → commit → scp 两站；站上热修须事后回灌仓库（同 station-bin 处置）                                                                              |
| superpowers 更新   | V3 通外网时 plugin 自更新；每次大版本后跑 A3 判据回归。**不追新**——锁定可用版本，升级窗口与 llama.cpp 升级窗（手册 §10）同批评估                                                                     |
| opencode 版本锁定    | 同内核锁定先例：选定版本后禁自动升级；升级窗口统一评估（含 PR #42150 O(N²) 修复进度，§8.9），升级后跑 hook 冒烟 + PONG 回归；plugin API 变更史（`api.command.*` 移除/V2 hook 静默失效/Effect 化 v1.4.4+）记入台账备查 |
| conf CTX 变更      | 改 `/etc/llama-instances/*.env` 必须同步 opencode limit.context（不变式③，挂 params-ledger 维护链）                                                                   |
| 记忆层数据            | `~/.local/share/opencode/memories/` 纳入常规备份范围（纯 markdown+SQLite，可直接 rsync）                                                                              |
| 溯源               | 本设计每个决策的依据锚定在调研报告 §2.2/§6/§7.5/§7.6/§8.5-§8.9（三轮审计后 E1）；后续引用本文时须连同调研锚点一起引                                                                              |
| claude-mem P2 升级 | 若 V4 门通过并入 claude-mem：每次版本变更须复验"hooks 无双触发"（#24115 复现用例即其本尊）；worker 常驻进程须先更新 D1 零自加载豁免清单（不变式②）                                                         |
| ARS 移植版跟踪        | timpara/opencode-academic-research 上游更新不追新；仅当上游 claim-audit 校准阈值变更（FNR/FPR）且本集群自制件依赖其蓝本时评估同步（§8.5）                                                     |
| 自制 skill 迭代      | assertion-audit/cross-examine 修改走主控站仓库→scp 流程（同定制技能变更）；重大修改后抽 1 个历史断言表做回归核验；证明力边界声明为强制字段不得删（不变式⑦）                                                      |
| claude code 版本   | 插件面维持最小（当前仅 superpowers/document-skills）；若必须经 marketplace 装件，每次升级后核验插件目录存在+`/` 列表可见（#41701 破坏链无上游认领）                                                   |

## 13. 对实施的输入

### 13.1 关键工程约束

1. PowerShell→ssh 铁律：远端操作一律本地写脚本→scp→执行（PowerShell `$(cmd)` 本地执行陷阱）
2. 中文路径：主控站仓库路径全英文（`ops/agent-skills/`），规避 PowerShell 中文乱码史
3. 逐文件 scp（多文件静默失败史）
4. B 站 opencode 升级走 npm 平台包备选法（官方 upgrade exit 28 史，D4 已验证）

### 13.2 风险与缓解

| 风险                                                                                                                         | 缓解                                                                                                                     |
| -------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| opencode 1.18.25 与 codex-memory 兼容性未知（README 只说 ≥1.18）                                                                     | T5 试点先行 B 站单站，失败回退 four-opencode-memory（零依赖纯 Markdown）                                                                 |
| 技能过多稀释 120B 指令遵循（自动触发误判率升）                                                                                                 | 全部关键技能手动 `/` 触发纪律（调研 §2.1 限制②）；P2 视需要上 opencode-skillful 懒加载                                                           |
| claude-mem worker→LiteLLM 路径未验证                                                                                            | 已隔离在 P2（本设计范围外），V4 验证门独立裁决                                                                                             |
| 审计 F4 陷阱若成立，claude code 长会话踩 400                                                                                           | V2 验证 + 无害缓解三件套已内建（§10 T2 无关，claude code 侧纪律入手册）                                                                       |
| opencode plugin API patch 版内静默破坏（`api.command.*` 移除、V2 hook 静默失效致父会话挂死、loader 重构破坏 NAPI 解析，调研 §8.6.1，E1）                   | 技能全走 A 类纯 prompt（零 plugin API 依赖）；opencode 锁版本禁自动升级（不变式⑥），升级后跑 hook 冒烟；自制 skill Phase 2 hook 化降级为失效后备且禁用 TUI `api.*` 面 |
| opencode 长会话 O(N²) delta 累积（#30067，50-80 轮退化——nemotron 长会话主用法直接受影响）                                                        | T1 选型评估含 PR #42150 修复的版本；未含修复前长会话控制在退化阈值内（轮数预算入手册）                                                                     |
| claude code hooks 层四缺陷上游零认领（#31250 blocking 绕过/#34573 command hooks 丢弃/#31777 证书/#24115 双触发，全部 closed as not planned，§8.9） | 不变式⑥：Phase 1 prompt 契约为准，hook 面不承重                                                                                     |
| 首跑 ripgrep 从 GitHub Releases 下载停滞 → grep/skill 工具无限挂死零报错（调研 §8.6.1 #23891，closed as not planned，中国网络高危）                    | T1 环境准备强制两站 `apt install ripgrep` + `command -v rg` 验收                                                                 |
| claude code marketplace 自动更新静默清空插件目录（调研 §8.6.2；#41701 官方标 invalid 未认领，#40153 先删后 re-clone 失败即裸）                            | claude code 插件面维持最小、不依赖 marketplace 分发；未来需要时本地路径安装                                                                     |

***

**Review 签字**: \_\_\_\_\_\_\_\_\_ 日期: \_\_\_\_\_\_\_\_\_
