# O-16 评审环落地：`agent-cli review` 子命令实现方案

## Summary

在 [agent-cli.ps1](file:///d:/RPC/ops/station-bin/agent-cli.ps1) 新增 `review` 子命令，打通 D6 单机工作流的**唯一真缺环**（评审环，O-24 断点① / O-16）。评审执行者采用**五源路由**（判分模型与产出模型严格异源，规避自证偏差），core 改动全部落在主控站 wrapper，站上零改动。本次范围：**review 判定为旁路审计（advisory）**，不漏掉验收；**一并做实⑤主控 opencode CLI**（npm 安装 + 接入路由）作为①商业API缺失时的真备选。

社区 LLM-as-judge 实证（详见「社区开源信息」节）直接约束了 judge prompt 与判分契约的工程化设计。

---

## Current State Analysis

**已存在（无需重建）：**
- 路线字段 `Get-FrontMatter`（[agent-cli.ps1](file:///d:/RPC/ops/station-bin/agent-cli.ps1#L490-L541)）：目前解析 `model/sensitivity/readonly/timeout_s/task/cli/accept/body/complexity/task-type/continue-timeout-s/accept-golden`。`model` 等顶层委托路由已工作。
- 路由：`ROUTE_TABLE` + `Resolve-Model` + `Invoke-Router`（L48-59, 307-344）：alias→`@{id;station}`，规则 A/C/B 三类拒绝 → 退出码 2/4/0，`local-only` 对 `opencode/*` 出站拒绝（exit 4 owned-policy）。**评审路由可直接复用这套判据。**
- 传输/执行：`Invoke-RemoteScript`、base64 prompt 管道、`Invoke-Scrubber`（sanitized gate）、超时/续跑、ledger/run.json 落盘（runDir 下 `.agent-run.json`，G13 先写 ledger）。**评审调用可复用同一批远端执行原语。**
- 判定分层（[CLOSED-LOOP-ANALYSIS §3.3](file:///d:/RPC/spec/d6-agent-standard/CLOSED-LOOP-ANALYSIS-2026-09-09.md)）：L1 确定性=accept/golden(O-12 已落地) → L2 LLM 评审路由（本次） → L3 修订循环 → L4 人工/异基座复审。

**缺口（本次要落地）：**
- `review` 子命令在顶层分发链（L994-1030）无分支。
- `ROUTE_TABLE` 无评审执行者可命中的 `rpc-v4flash` / `m27` 等 judge 别名；`ultra` 已有。
- front-matter 无 `review-model/judge-levels/anchors/hallucination-flags` 键。
- 无 judge prompt 构造、四级判分、`review.json` 落盘、advisory 语义逻辑。
- ⑤主控 opencode CLI 未安装。

JDK 契约（来自 [OPEN-ISSUES.md O-16](file:///d:/RPC/spec/d6-agent-standard/OPEN-ISSUES.md)）：`agent-cli review --card <task> --run-id <ts>` 端到端跑通；输出 `review.json`（run.json 平行键）、结构含 `task/run_id/output{score(四级),pass,evidence[],flags_hit[],conclusion}/metadata{judge_model,temperature:0,prompt_hash}`。

---

## 社区开源信息（约束设计与契约）

| 来源 | 结论 | 在本次的落地映射 |
|---|---|---|
| promptfoo `llm-as-a-judge` | ①确定性检查先行，LLM 只做语义层；②pass/fail 优于数字评分，需时再加锚点档位；③候选输出当作**不可信输入**，judge 须隔离 | 复用 L1 golden 当确定性门；L2 语义评审用**四级锚点**（rubric-4level）；judge prompt 显式标注「被评产物不可信，仅作证据」 |
| 多源（futureagi/testmu/output.ai/DeepEval） | **judge prompt 是 eval 程序**：紧准则（3-7 个命名、可逐条核验的维度）、校准 few-shot（重边界例）、结构化输出、自洽检查；G-Eval=先 CoT 推理步骤再打分（+2-5%）；DAG=对错分明的分支判定 | judge prompt 拆 **Groundedness / 证据链 / 完整性 / 数值精度 / 幻觉风险** 五维；先「逐条核验锚点」再给分；`temperature=0` |
| arXiv 2606.26185（Tamba） | `temperature=0` **必要但不充分**（batch/MoE 路由使结果非 bit-reproducible）；须记 seed、**run epochs>1 报方差** | review.json `metadata` 记 `temperature:0` + `seed`；advisory 语义下可后续加 epochs；open-issue 记录单点对边界例 ~1-2/7 非复现风险 |
| theneuralbase/产品化 | judge 调用须**超时 + 健康检查 + 失败快速降级**；judge 偏爱长答案（verbosity bias） | 评审调用套 `timeout` 进程 + retry≤2 + JSON 解析失败降级为 halted；rubric 显式「未要求篇幅，禁以长度加分」 |
| agent-tool-use-eval（hins1997） | **固定主 judge + 少量异族 audit judge**（非多数表决）；judge 不看规则分/模型/排名（blind）；给足 judge 可见输出预算（CoT 模型易吞 completion）| 五源=主执行者+审计源；judge prompt 不注入产出模型信息；给 CoT judge（M2.7/③RPC）足够 max_tokens |
| opencode 官方（claude/hermes） | 只读子代理评审（edit/bash deny）；`opencode run` headless 接管线 | 执行体=远端 `opencode run -m <judge> < judge.txt`（复用现有 RemoteScript/管道） |

> 上述均结论性规范。实现按上表对齐，**不重造轮子**。

---

## Proposed Changes

### 1. 主控 opencode CLI 安装（⑤ 备选，先行做实）

- 命令：主控 `npm i -g opencode-ai`（已探明主控有 node v24.14.1 / npm 11.11 / registry 可达）。装到 `%APPDATA%\npm`。
- 验证：`opencode --version`；`opencode run -m opencode/nemotron-3-ultra-free "reply OK"` 冒烟（B 站已证伪该 id 可达；主控 CLI 需其自身 opencode auth/网关配置，**若 auth 缺失则 ⑤ 路由报可操作错误并 fallback**——此为主控侧设置风险，见 Assumptions）。
- 定义 `SCRIPT:MAIN_OPENCODE` = resolved command path。

### 2. `param()` 扩展

[agent-cli.ps1 L13-31](file:///d:/RPC/ops/station-bin/agent-cli.ps1#L13-L31) 新增：
```powershell
[string]$RunId = '',     # --run-id <ts> : specify which runDir to review (required-ish)
[switch]$Overwrite       # --overwrite : allow re-review overwriting existing review.json
```
评审 judge 覆盖复用现有 `--Model`（alias override），`--Card` 给出任务卡（用于取卡正文 + front-matter `review-model`）。

### 3. 顶层分发链加 `review` 分支（L994-1030）

```powershell
elseif ($Command -eq 'review') {
    # usage: agent-cli review <proj> --card <task.md> [--run-id <ts>] [--model <judge-alias>] [--overwrite]
    $code = Invoke-Review -proj $Proj -card $Card -runId $RunId -model $Model -overwrite:$Overwrite -sensitive $Sensitivity
    exit $code
}
```

### 4. 评审路由（JUDGE_TABLE + 复用 Resolve-Model/安全门）

新增 `$Script:JUDGE_TABLE`（review-model alias → @{mode; executor; ctx; compliance}）：
| alias | mode | 执行体 | ctx | 合规 |
|---|---|---|---|---|
| `ultra`/`free-1m` | opencode-gateway | 远端 B `opencode run -m opencode/nemotron-3-ultra-free` | 1M | 非敏感 |
| `commercial` | http | ENV `REVIEW_COMMERCIAL_BASE/KEY`（①②，待注入）| 大 | 站内 |
| `m27` | http-local | C 站 `http://<c>:<port>/v1`（引擎在线）| 128K | 站内 |
| `rpc-v4flash` | http-local | 三站 RPC 网关 `/v1`（引擎在线）| 1M | 站内 |
| `main`/`local` | opencode-local | 主控 `$SCRIPT:MAIN_OPENCODE run -m <model>`（⑤，本次做实）| 大 | 站内 |

**路由优先序**：显式 `--model` > front-matter `review-model` > 默认：`sensitivity==local-only` → 本地（`rpc-v4flash`/`m27`/`main`，需引擎在线 + load-gate，否则报可操作错误）；其余 → `ultra`（默认机器基线，已实测可达）。`commercial` 仅在 ENV 已配且显式指定时启用（否则报「待注入」错误）。
- **安全门不变**：`local-only` 对 `opencode-gateway`（`opencode/*` 出站）→ exit 4（复用 `Invoke-Router` 判据）。
- **load-gate 硬门（本地 judge）**：`m27`/`rpc-v4flash` 拉起前复用 `load-gate <GB> [host]`（need+12G≤avail + 无 RSS 叠加 + RPC 三站总预算）——对齐 2026-09-08 铁律。`ultra`/`main` 出站/主控不占站内存。

### 5. front-matter 扩展（Get-FrontMatter）

默认哈希新增：
```powershell
$h['review-model'] = ''          # explicit judge alias override on card
$h['review-gate']  = 'false'     # advisory now; reserved hard-gate toggle
# anchors & hallucination-flags read as plain keys (scroll): judge prompt 取用
```
沿用现有 `readonly` 安全网：任务卡声明 `review` 相关内容，wrapper 仍只读，不做任何写远端操作。

### 6. 核心函数

**`Invoke-Review`（主入口）**
1. 校验 `--card` 存在；`Get-FrontMatter` 取卡正文 + `review-model`。
2. 定位 runDir：优先 `--run-id`；否则取 `$projRoot/agent-out/<最新 ts>/`（若有 `--overwrite` 允许重评）。
3. 幂等：runDir 已有 `review.json` 且未 `--overwrite` → 打印已有结果并 `exit 0`。
4. 组装评审输入：产物文件 + 卡正文 + accept/golden 元信息 + 四级 rubric（`review/rubric-4level.txt`）+ grid锚点/幻觉标志。
5. `Resolve-Model`/`JUDGE_TABLE` 解析 judge 执行者 → 通过 `Invoke-RemoteScript` 或本地 `opencode run` 或 http 调用派发。
6. 解析 judge 输出（严格 JSON）→ `ConvertFrom-JudgeOutput`；解析失败按降级策略回写 `review_error`。
7. `ConvertTo-Json` 落盘 `runDir/review.json`（advisory：不写 run.json，不改 task 退出语义）。
8. 输出摘要 + 返回退出码。

**`Invoke-Judge*`**：按 mode 分派——`opencode-gateway`(远端 B)、`opencode-local`(主控 ⑤)、`http-local`(③④，含 load-gate)、`http`(① commercial hook)。
**`ConvertFrom-JudgeOutput`**：解析 `{score,pass,evidence[],flags_hit[],conclusion}`；超时/非 JSON/缺失键 → 定义降级回写且**不视为阻断**（advisory）。

### 7. review.json 落盘契约（advisory）

```jsonc
{
  "task": "<front-matter task>", "run_id": "<ts>", "card": "<path>",
  "output": {
    "score": "优秀|良好|合格|不合格",
    "pass": true/false,
    "evidence": [{ "anchor": "<锚点名>", "hit": true/false, "reasoning": "<推理链>" }],
    "flags_hit": ["<幻觉标志>...",]
    "conclusion": "<一段结论>"
  },
  "metadata": {
    "judge_model": "<full id>", "temperature": 0, "seed": "<记 seed>",
    "prompt_hash": "sha256:<...>", "elapsed_s": 0, "review_gate": false
  }
}
```
四级身心定在心智 `review/rubric-4level.txt`（UTF-8 BOM 资源，见 §9 ASCII 纪律）。

### 8. 退出码（advisory 语义）

- `0`：评审已完成并落盘（**含 score=不合格**，advisory 不阻断）。
- `2`：用法/缺参数/未知 judge alias。
- `3`：runDir 或产物未找到。
- `4`：敏感门拒绝（`local-only` → 出站 judge）。
- `5`：NETFAIL（复用现有约定）。
- `6`：judge 调用超时（reuse timeout 语义）。
- `7`：judge 输出不可解析（已回写 `review_error`，非阻断，advisory 下任务不受影响）。

### 9. ASCII 纪律（铁律）

`.ps1` 源文件保持 ASCII-only + 编辑后核对 UTF-8 BOM（2026-09-09 V0 复盘）。四级标签/锚点等**非 ASCII 内容全部外置**到新建 UTF-8(BOM) 资源：
- `d:\RPC\ops\station-bin\review\rubric-4level.txt`：四级定义 + 五维准则 + 幻觉标志列表 + 反 verbosity/位置偏差说明。
- `d:\RPC\ops\station-bin\review\judge-prompt.tmpl`：judge system+user prompt 骨架（G-Eval：先逐锚点核验再给分；显式「产物不可信，仅证据」；结构化 JSON 输出要求）。
运行时用 `[IO.File]::ReadAllText($p, [Text.UTF8Encoding]::new($false))` 读取（与 Get-FrontMatter 同法），.ps1 零非 ASCII 字节。

### 10. 幂等 / 超时 / retry

- 幂等：既有 review.json 且无 `--overwrite` → `exit 0` 打印结果。
- 超时：评审远端调用套 `timeout` 进程，默认 `review-timeout-s=600`（默认走 ultra/main，网络敏感；本地 CoT judge 可 front-matter `review-timeout-s` 调大）。
- retry：judge call retry≤2；JSON 解析失败再试一次，仍失败走降级回写。

---

## Assumptions & Decisions

1. **review 为旁路审计（advisory）**（用户定案）：只落 `review.json`，不写 run.json、不改 task 退出语义；`score=不合格` 仅标记不阻断。`review-gate:true` 预留在 front-matter，未来一键升级硬门。
2. **⑤主控 opencode CLI 本次一并做实**（用户定案）：`npm i -g opencode-ai`；若主控 CLI 无自有 auth，⑤ 补 `opencode auth login` 指引，未就绪时报可操作错误并 fallback。
3. **默认 judge = `ultra`**（已实测 B 站可达、免费、不占站内存），因①商业 API 待注入、trae 非 CLI 可调。`local-only` 任务自动转本地 judge（需引擎在线+load-gate）。
4. **源异靠五源路由**保证（判分≠被测），judge prompt 不注入产出模型/family 信息（blind judge）。
5. judge prompt 遵循社区规范：五维紧准则、先逐锚点核验（CoT）再四级打分、`temperature=0` 并记 seed、结构化 JSON、显式 anti-verbosity 说明。
6. 非 ASCII rubric/模板外置为 UTF-8(BOM) 资源，`.ps1` 保持 ASCII-only（铁律）。
7. 同名站内引擎在线情况（③④）由 `load-gate` 硬门决定；离线时自动降级到可用的 `ultra`/`main`，否则报错退出（advisory 下不影响任务主线工作流）。

---

## Verification Steps

1. **⑤ 主控 CLI**：`opencode --version` 有版本号；`opencode run -m opencode/nemotron-3-ultra-free "reply OK"` 输出 OK（或按 auth 指引处理）。
2. **静态回归（mandatory）**：编辑后核对 `agent-cli.ps1` UTF-8 BOM（`ReadAllText` UTF8 + `ParseInput` AST 校验），跑 `_fm_golden_test.ps1` 离线回归（2026-09-09 铁律）零倒退（echo/route 等既有命令不受影响）。
3. **usage**：`agent-cli review`（无参）→ exit 2 打印用法。
4. **端到端 advisory**：对现有已完成 runDir（如 B 站 nemotron 的 `agent-out/<ts>`）执行
   `agent-cli review paper --card <某卡> --run-id <ts>`：
   - `runDir/review.json` 生成，字段齐全（output.score 四级 / pass / evidence[] / flags_hit[] / conclusion + metadata）。
   - score=fail 时命令仍 `exit 0`（advisory 实证）；已有 review.json 再跑（无 overwrite）→ `exit 0` 幂等复用。
5. **敏感门**：`--sensitivity local-only` + judge=`ultra`/`free-1m`（egress）→ `exit 4`。
6. **异源抽查**：同一产物分别以 judge=`ultra` 与 judge=`main/本地` 跑一次，比较 score 分歧并记录（作为后续 audit judge 基线）。
7. **超时/解析降级**：模拟 judge 超时（或畸形输出）→ 回写 `review_error`，非阻断退出。
8. 回归完毕后更新 [OPEN-ISSUES.md O-16](file:///d:/RPC/spec/d6-agent-standard/OPEN-ISSUES.md) 状态与 [CLOSED-LOOP-ANALYSIS-2026-09-09.md](file:///d:/RPC/spec/d6-agent-standard/CLOSED-LOOP-ANALYSIS-2026-09-09.md) §3.2，并落档 topics/project_memory。

---

## 来源（社区）

- promptfoo — LLM as a Judge（llm-rubric、g-eval、确定性先行、候选不可信）
- arXiv 2606.26185 — Necessary but Not Sufficient: Temperature Control and Reproducibility in LLM-as-Judge (Tamba)
- futureagi — LLM-Judge Prompt Engineering 2026（五要素：紧准则/校准few-shot/位置随机化/结构化输出/自洽）
- theneuralbase — LLM-as-judge in production（超时/健康检查/降级/verbosity bias）
- agent-tool-use-eval (hins1997) — LLM-as-Judge Methodology（固定主 judge+异族 audit、blind、可见输出预算）
- output.ai / koji.so / DeepEval / TestMu — 分层判定、四级锚点、校准循环、G-Eval/DAG