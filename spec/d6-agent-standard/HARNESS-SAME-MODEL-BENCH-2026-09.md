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