# 统一基座模型实测 Agent Harness 调研（编码能力框架级对照）

***

id: d6-agent-standard-harness-same-model-bench
type: research
version: 1.0
status: reviewed
date: 2026-09-10
depends: \[d6-agent-standard-ARCHITECTURE, d6-agent-standard-PLUGIN-LEDGER]
upstream: null

***

> **Feature**: 局域网 OpenCode / Hermes / Claude Code 三 CLI 的"统一基座模型"Harness 编码能力对照调研——消除模型变量，聚焦 harness（agent harness）本身先进度。
> **动机**: 社区对三者的评价往往混入"厂商模型"差异（Claude Code 带 Opus、OpenCode 可接任意模型、Hermes 多模型）。需剥离模型，仅看 harness 编排层的差异（工具集/上下文管理/失败恢复/压缩）。
> **来源**: 第三方同基座 benchmark + 论文（见 §4 佐证）。

---

## 1. 核心结论（TL;DR）

1. **harness 而非模型决定编码质量的上限与下限**：北大实测 6 harness × 同一模型池，最好的 76.2 / 最差 52.4，**23.8 分全来自 harness**（与模型无关）。
2. **统一基座下 Claude Code 与 OpenCode 均在编码 harness 第一梯队**：aimultiple 用同一 Sonnet 4.6 测 17 harness，两者同处最高分档。
3. **Hermes 在主流"统一基座编码对照"中基本缺席**：它是通用 agent 而非纯编码 harness；但 **Claw-SWE-Bench 提供 `hermes_swebench` 适配器**，可补同基座测。
4. **harness 演化悖论**（皇后大学 ACM 论文）：固定模型下，harness 版本更新对 SWE-Bench 无统计显著提升，反而 token/工具调用近翻倍无质量增益。

---

## 2. 方法论：什么是"统一基座实测"

**对照组设计**：固定同一 LLM（reasoning_effort/temperature 等参数保持一致），只改变 LLM 外层的 harness，测量"代码正确率/任务解析率"差异。任何分数差 → 反映 harness 编排本身（上下文如何收集、shell 如何排序、结果如何自校验、失败如何恢复、压缩如何做），**与模型权重无关**。

```
变量:           模型(固定)  →  harness(唯一变量)
协议:           同任务 / 同 eval(Docker SWE-bench) / 同 pre-registered 参数
```

---

## 3. 关键第三方同基座实测

### 3.1 北大：6 harness × 同一模型池（2026-05）
- **设定**: 106 任务 × 6 harness × 同一模型池，5000+ 次运行。
- **结果**: 最好 76.2 / 最差 52.4 → **23.8 分差距全来自 harness**。
- 结论: harness 是"骑手与马的缰绳"——马（模型）已收敛，差距在 harness。

### 3.2 aimultiple：17 harness × Claude Sonnet 4.6（非推理）统一基座
- **设定**: 每个 CLI agent 用**同一个 Sonnet 4.6** 跑同一组 full-stack 规格任务；编辑器用 Opus 4.6。任何差异 → 反映 orchestration（上下文收集/命令序列/自校验/恢复）。
- **结果**: A-Code Bench 的 Cost vs Score 图上 **opencode 与 claude-code 同处最高分档**；codex / kimi-cli / grok-cli / gemini-cli 跟随；cursor/toolaidejo 在编辑档。

### 3.3 harness-bench：预注册 `claude-opus-4-8` + 12 实例 SWE-bench Verified mini-split
- **定位**: "**Not a model leaderboard. A harness leaderboard.**" 同一模型/同一任务/同一官方 SWE-bench eval，只有 harness 变。
- **Phase-1 已包装**: Claude Code · OpenCode · Pi / Oh My Pi。
- 协议: 预注册固定模型 `claude-opus-4-8`（reasoning low）+ 官方 `run_evaluation`，可选开源权重做稳健性检查。

### 3.4 皇后大学 ACM 论文（2026-07）：固定模型只看 harness 演化
- **设定**: 35 个 Qwen Code CLI 版本 × **固定 LLM** × 50 个分层 SWE-Bench Verified。
- **关键发现**: (i) harness 版本更新对 SWE-Bench **无统计显著提升**；(ii) 后期版本 token/工具调用近**翻倍却无质量增益**；(iii) 定位到特定 PR 引起质量波动。
- **启示**: 换 harness 版本 ≠ 提质量；质量回归常被误归因给模型，实为 harness。

### 3.5 Claw-SWE-Bench（2026-06）：Claw 系 harness 同基座（含 Hermes）
- **设定**: 5 个 claw-adapter（`openclaw_swebench` / **`hermes_swebench`** / `zeroclaw_swebench` / `nanobot_swebench` / baseline）在 SWE-bench 对照 OpenClaw 系 harness。
- **价值**: **唯一原生为 Hermes 提供同基座 SWE 适配器**的基准，可测 Hermes 编码 harness 水平。
- **局限**: 属 OpenClaw 生态自测，非独立第三方 vs Claude/OpenCode 的跨 harness 对照。

---

## 4. 佐证来源

| 来源 | 类型 | 关键数字/结论 |
|---|---|---|
| [北大 harness 实测（dev.to 转述）](https://dev.to/dheerajakula/what-is-an-agent-harness-claude-code-vs-codex-cli-vs-opencode-2pn8) | 实验 | 106 任务×6 harness，76.2 vs 52.4，23.8 分来自 harness |
| [aimultiple agent-harness](https://aimultiple.com/fr/agent-harness) | 同基座 | 17 harness × Sonnet 4.6；opencode/claude-code 最高档 |
| [harness-bench (GitHub)](https://github.com/zenixos/harness-bench) | 预注册基准 | 固定 opus-4-8 + 12 SWE-bench；Phase-1: Claude/OpenCode/Pi |
| [皇后大学 ACM 论文 arXiv 2607.03691](https://arxiv.org/pdf/2607.03691v2) | 论文 | 35 QwenCode 版本×固定 LLM；无显著提升 + 2× 成本 |
| [Claw-SWE-Bench arXiv 2606.12344](https://arxiv.org/html/2606.12344v1) | 基准 | 5 claw adapter 同基座，含 `hermes_swebench` |
| [SWE-agent（Princeton 2024, arXiv 2405.15793）](https://arxiv.org/abs/2405.15793) | 论文 | 同模型文件窗 100 行→18% vs 全文件→12.7%（接口影响）|

---

## 5. 对机群的落地研判

### 5.1 统一基座对照的意义
- 你的机群已有**统一基座候选**（B 站 8095 Nemotron-120B / 8094 Q3.8F，均为 llama-server OpenAI 兼容端）。
- 三者 harness（Hermes / OpenCode / Claude Code）**都可指向同一本机端点** → 做出机群内真实同基座对照。

### 5.2 直接落地路线（推荐）
1. 用 **Claw-SWE-Bench**（有 `hermes_swebench` 适配器）或 **harness-bench**（可加 Hermes），在 B 站本地跑同基座 SWE。
2. 或自建轻量同基座：三 CLI 均指向 B 站 8095（Nemotron）→ 同批 domain_matrix / SWE-bench 任务 → 测 harness 本身。

### 5.3 预期
- **Claude Code / OpenCode**: 同基座下编码 harness 强（上下文压缩、LSP 闭环、失败恢复）。
- **Hermes**: 通用 agent harness，编码该强调短板被记忆/插件/`/goal` 长程能力补偿；需同基座测确认编码档位。

---

## 6. 待办/观察

- [ ] 落地机群内「统一基座（Nemotron-120B / Q3.8F ）× 三 harness」轻量对照
- [ ] 尝试把 Hermes 接入 Claw-SWE-Bench（`hermes_swebench` 适配器）或 harness-bench
- [ ] C 站 hermes CLI 安装收尾（uv sync 后台跑完）
- [ ] 演进对照警惕：换 harness 版本可能不提升 SWE 却增 token（皇后大学结论）

---

## 7. 机群内同基座对照 —— 落档方案（2026-09-29）

> **为什么单列**：§6 四条待办里**只有第 1 条需要"我们自己出数字"**（其余三条是外围：接基准 / 装 CLI / 警惕演化）。
> 本节把第 1 条写成**可执行方案**（臂设计 + 口径 + 夹具 + 验收），供后续排期。
> ⚠ **本节只是方案 —— 未跑任何实验**；§6 四条待办**仍全部未做**。

### 7.1 与 `§6.3` 的前提更正（**必须先看这条**）

`docs/research/2026-09-28_Textbook并发与派发机制可借鉴性调研.md` §6.3 用
「**A 站 `claude` 是"纯文本模式"（`CLAUDE_CODE_DISABLE_TOOLS=1`）**」推出"同一 CLI 有两种模式、结论相反"。
★ **该前提已被证伪**：`OPEN-ISSUES.md` 的 **O-111**（2026-09-28 三站实测）证明
**该变量三站都不存在**（手册那句是**错误陈述**）⇒ §6.3 举的那个例子**站不住**。
⇒ §6.3 的**框架**仍成立（"换 agent CLI"须拆成 **①换外壳 / ②换闭环**），但
**"无工具模式"这一支目前没有实例** —— 要用它，必须先补 O-111 的工具面探针。

### 7.2 三臂设计（**只改 harness**；模型与任务都固定）

| 臂 | harness | 说明 |
|---|---|---|
| ① | 裸 API 直连（本机 OpenAI 兼容端点，无外壳） | §6.1 的判定里它在"一次性问答/推理"类**胜出** |
| ② | opencode（**有工具**） | 现役路径；本仓实测过 |
| ③ | claude（**工具面待验**） | ⚠ 前置 = O-111 的只读探针（**目标站须先 load 引擎**） |

★ **③ 的前置未满足前，第三臂不可比** ⇒ 起步可**只跑 ①②**（两臂都跑得起来），③ 留到 O-111 闭环后补。

### 7.3 必须先固化的四个口径（否则数字不可比）

1. **同任务卡** —— 同一份卡面正文，逐字；不要各写一版。
2. **同模型** —— 同一个 alias / 同一个 id；⚠ **不要**一边走出网档、一边走本地引擎。
3. **同 ctx** —— `ctx` 与 `max_out` 一致；★ 引擎真实 `n_ctx` 是**唯一真相**（`D-18`）。
4. **记什么** —— **per-task 墙钟 + 通过率**。⚠ **不记 token**：无头 run **不吐 usage**，硬凑就是**编造值**
   （同 `O-39` 的处置：宁可不填，不硬编）。

### 7.4 夹具

- **优先用现成、有标注的条目**（**不必自造**）：本仓既有 `domain_matrix` gold 夹具 + 结果台账冒烟口径即可起步。
- 若要"成规模"，可借**外部项目**的有标注条目（例：某 Lean4 项目的 Greene 229 / Björk 720）——
  ⚠ 但那是**别家项目的资产**，须先过**档位**与引用规则（`sensitivity.yaml`）。

### 7.5 验收判据（可机判）

- **≥1 个真跑结果**：每臂每任务的 `run_s` 与**通过率**落档（**不是**"机制在位"就算过）。
- **先验红**：把两臂的**模型**改成不同 alias ⇒ **必须**在产物里体现出来
  （否则说明"模型固定"这条**根本没做**，而不是"做了没差异"）。
- **空对象**：某臂**跑不起来** ⇒ **只报数、不入分母**；**不许**算作"该臂更差"
  ——"**没验到**" ≠ "**验出问题**"。

### 7.6 如实登记（边界）

- ★ **本仓现有语料推不出结论**：吃狗粮 35 张卡里 **34 张 `cli: opencode`** + **1 张 `cli: claude`**
  （且那张是**通道烟测**，非质量对照）⇒ **harness 是恒定变量**，从未变过。
- ⚠ **一条轴缺口（登记在案）**：`docs/Agent-CLI技术选型调研_20260909.md` 的 7 个对比维度
  （本地模型一等公民 / 免费额度 / 确定性编排 / 权限边界 / 生态兼容 / 三站同构 / 集成成本）**没有"准确率 / 输出质量"这一维**
  ⇒ 即"换 / 不换 CLI"的**裁决轴从来不是质量轴**，而 §1 说明质量差异可达 **23.8 分**。
  ⇒ 两者**不冲突**，但也**没接上** —— 这正是本节要补的那一段。