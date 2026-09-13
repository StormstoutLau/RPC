# O-16 评审环细化实现方案（复盘已落盘代码，修正社区规范差距）

## Context

`agent-cli review` 子命令已完成主体落盘：param 新增 `--RunId/--Overwrite`、front-matter 新增 `review-model/review-gate/review-timeout-s`、`JUDGE_TABLE` 五源路由、核心函数 `Resolve-Judge/Invoke-Review/Invoke-Judge*/ConvertFrom-JudgeOutput/Build-JudgePrompt/Get-ReviewRunDir`、顶层 `review` 分发分支、资源文件 `review/rubric-4level.txt` + `review/judge-prompt.tmpl` 均已落地，AST 解析已通过。

但 plan 阶段逐行核对已落盘代码与设计文档 + 社区 LLM-as-judge 规范，定位到 **5 个真实缺口**（含 `main` judge 合规定性错误、max_tokens 硬编码偏小、缺重试循环、产物截断方向、commercial 默认模型臆造），需在继续推进前修正。本方案产出重点 = 修正这些差距 + 完善验证，而非重写已落盘框架。

## Current State Analysis

**社区规范对已落盘实现的约束核对（已满足项）：**
- 确定性先行（L1 accept/golden）→ L2 LLM 评审分层（promptfoo）
- pass/fail + 四级锚点 rubric-4level.txt（promptfoo/futureagi）
- 候选产物不可信、blind judge（不注入产出模型）
- temperature=0 + 记 seed + prompt_hash（arXiv 2606.26185）
- anti-verbosity/anti-length（judge prompt 纪律段）
- local-only→egress 拒绝 exit 4（复用 Invoke-Router 判据）
- 非 ASCII 外置 UTF-8(BOM) 资源（.ps1 ASCII-only 铁律）

**已落盘代码与设计/社区规范的差距（本次要修正）：**

| # | 差距 | 代码位置 | 社区依据 | 影响 |
|---|------|---------|---------|------|
| G1 | `main` judge 合规定性错误：JUDGE_TABLE 标 `main` = `type:'local', compliance:'all'`，但 `Invoke-Judge` local 分支实际调 `opencode run -m opencode/nemotron-3-ultra-free`（出站网关模型）。本地 local-only 任务默认映射到 `main`（[agent-cli.ps1](file:///d:/RPC/ops/station-bin/agent-cli.ps1#L1220)），会**把本地敏感数据经 opencode 网关出站**，违背 local-only 语义 | L1021(L7 type local) / L1176 local 分支 / L1220 local-only→main | opencode 官方只读评审概念；D6 local-only 安全门 | 敏感任务泄漏风险 |
| G2 | `max_tokens=2500` 硬编码偏小（[L1128](file:///d:/RPC/ops/station-bin/agent-cli.ps1#L1128)）：judge prompt 含任务卡 + 40K 产物 + rubric + 模板，`egress` 走 opencode run 无此约束，但 `http-local/http` 分支硬编码 2500，CoT judge（m27/rpc-v4flash）输出易被截断 | L1128 | agent-tool-use-eval「给足 CoT judge 可见输出预算」 | review.json evidence/conclusion 截断或解析失败 |
| G3 | 缺评审调用重试循环：设计文档 Nov/社区承诺 retry≤2 + JSON 解析失败重试一次，但当前 `Invoke-Review` 单次调用即定案（L1256） | L1256 | theneuralbase「超时+健康检查+失败快速降级」 | 单次网络/引擎抖动导致评审失败降级，不必要 |
| G4 | 产物截断只取**前 40K**（L1248），而评审最需要的是结论/远端末尾段 | L1248 | agent-tool-use-eval「给足可见输出预算」 | 长产物尾段缺失，judge 只见开头 |
| G5 | `commercial` 分支默认模型 `'gpt-5.4'` 臆造（L1190），无真实依据 | L1190 | 社区规范「不臆造」 | 误用不存在模型 |

**其它已确认无需改：** `Resolve-Judge` 别名解析、`Get-ReviewRunDir` 的 run-id/最新回退、advisory 幂等（已有 review 且无 overwrite → exit 0）、四级/幻觉标志 JSON 解析、`ConvertFrom-JudgeOutput` 严格 JSON 提取、退出码表（0/2/3/4/5/6/7）。

## Proposed Changes

### Fix G1：`main` judge 合规定性 + local-only 默认映射修正

`main` 是**主控 opencode CLI**（npm i -g opencode-ai），其执行体 `opencode run -m <model>` 的模型由 CLI 的 opencode 网关配置决定。要让它**真正本地**，须用主控 CLI 配置里的**本地/站内模型**（如 cluster-litellm/nemotron 或 engine），而不是硬编码出站 `opencode/nemotron-3-ultra-free`。

- 修正 1（JUDGE_TABLE）：`main` 标注加注——`id='main-opencode-cli'`，`compliance='all'` 保留，但**模型由 ENV `REVIEW_MAIN_MODEL` 指定**（默认 `cluster-litellm/nemotron`，即站内模型，非出站 ultra）。
- 修正 2（Invoke-Judge local 分支）：`-m` 从 `opencode/nemotron-3-ultra-free` 改为 `$env:REVIEW_MAIN_MODEL`（缺省取 JUDGE_TABLE 注释页默认 `cluster-litellm/nemotron`）。这样 local-only→main 走站内模型，不外发出站网关。
- 修正 3（local-only 默认映射）：保持 `local-only→main`，但要求主控 CLI 已安装且 `REVIEW_MAIN_MODEL` 指向站内可达模型；若主控 CLI 缺席 → 报可操作错误并**降级到 http-local（m27/rpc-v4flash）**，两源均不可达 → `JUDGE_UNREADY` exit 7。

### Fix G2：max_tokens 按 judge 可配置（CoT 源加大）

- JUDGE_TABLE 增加 `maxtokens` 键：`m27/rpc-v4flash`（CoT）→ `8000`；`commercial/ultra` → `2500`；`main` → `4000`。
- `Invoke-JudgeHttp` 的 `max_tokens` 由调用方传入（新增 `$maxTokens` 参数），不再硬编码 2500。
- front-matter 可加 `review-max-tokens` 键全局覆盖（预留，非本次必须）。

### Fix G3：评审调用 retry ≤2

- `Invoke-Review` 中 judge 调用包 `for($try=1; $try -le 3; $try++)`：`Invoke-Judge` 抛出 NETFAIL/timeout/解析失败且 `$try -lt 3` 时短暂等待（sleep 3s）后重试；第 3 次仍失败才走降级回写 `review_error`。filjury层语义不变（advisory 非阻断）。
- 记 `metadata.retries`。

### Fix G4：产物截断策略

- 改为**头尾截断**：保留前 20K + 后 20K，中间以 `...[TRUNCATED mid]...` 标记；若产物 ≤40K 不截断。judge prompt 的 PRODUCT 段优先呈现结论/末尾。

### Fix G5：commercial 默认模型修正

- 默认模型由 ENV `REVIEW_COMMERCIAL_MODEL` 决定；未设时不猜默认，直接报「commercial judge 未注入（缺 REVIEW_COMMERCIAL_MODEL）」`JUDGE_UNREADY` exit 7。

### 主控 opencode CLI 做实（⑤，与 design 一致）

- 主控 `npm i -g opencode-ai`；验证 `opencode --version` + `opencode auth login`（主控 CLI 需自有 auth）。
- 定义 `SCRIPT:MAIN_OPENCODE` = `Get-Command opencode` 解析（已由 `Get-MainOpenCode` 实现）。
- 冒烟：`opencode run -m <REVIEW_MAIN_MODEL> "reply OK"`。

## Verification Steps

1. 静态回归（铁律）：编辑后核对 `agent-cli.ps1` UTF-8 BOM（ReadAllText UTF8 + ParseInput AST 校验）；跑 `_fm_golden_test.ps1` 离线回归，echo/route/task 既有命令零倒退。
2. usage：`agent-cli review`（无 card）→ exit 2 + 打印用法。
3. 端到端 advisory：对现有已完成 runDir（如 B 站 nemotron 的 `agent-out/<ts>`）执行 `agent-cli review paper --card <卡> --run-id <ts>`：
   - `runDir/review.json` 生成，字段齐全（score 四级 / pass / evidence[] / flags_hit[] / conclusion + metadata（judge_model/temperature:0/seed/prompt_hash/elapsed_s/review_gate/retries））。
   - score=不合格仍 `exit 0`（advisory）；已有 review 再跑（无 overwrite）→ exit 0 幂等复用。
4. 敏感门：`--sensitivity local-only` + judge=`ultra`（egress）→ exit 4。
5. 异源抽查：同一产物分别 judge=`ultra` 与 judge=`main`（站内模型）各跑一次，比较 score 分歧记录为 audit 基线。
6. 超时/解析降级：模拟 judge 超时/畸形输出 → 回写 `review_error`，非阻断退出（exit 0/7）。
7. 完成全部验证后更新 [OPEN-ISSUES.md O-16](file:///d:/RPC/spec/d6-agent-standard/OPEN-ISSUES.md) 状态（→ closed）与 [CLOSED-LOOP-ANALYSIS-2026-09-09.md](file:///d:/RPC/spec/d6-agent-standard/CLOSED-LOOP-ANALYSIS-2026-09-09.md) §3.2 五源路由复核，落档 topics/project_memory。

## 来源（社区）

- promptfoo — LLM as a Judge（确定性先行、pass/fail、候选不可信）
- arXiv 2606.26185 — Temperature Control & Reproducibility in LLM-as-Judge（temperature=0 不充分，记 seed）
- futureagi — LLM-Judge Prompt Engineering 2026（紧准则/结构化输出/自洽）
- theneuralbase — LLM-as-judge in production（超时/重试/健康检查/降级/verbosity bias）
- agent-tool-use-eval (hins1997) — LLM-as-Judge Methodology（固定主 judge+异族 audit、blind、给足 CoT judge 可见输出预算）
- output.ai / DeepEval — 分层判定、四级锚点、G-Eval/DAG