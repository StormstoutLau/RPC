# G1 二期——`--continue` Continue-vs-Spawn 决策表

---

>
> id: d6-agent-G1-continue-decision
> type: design
> version: 1.0
> status: draft
> date: 2026-09-12
> depends: [d6-agent-standard/DESIGN.md §9.6-2, d6-agent-standard/OPEN-ISSUES.md O-21③/O-24, d6-agent-standard/BLINDSCAN-v2-orchestration.md §4/§8.5]
> upstream: [d6-agent-standard/DESIGN.md]

---

## 1. 背景与目标

**现状**（O-24 P0-① 已落地，agent-cli.ps1 $body）：首跑 RC≠0 后，resume loop **无脑 `--continue` ≤2 次**（`continue-timeout-s` 独立预算）。这是"续跑**执行体**"，但缺少"该续还是该重启"的**决策层**：

- Anthropic §9.6-2 六行决策表被 DESIGN 引证为 G1 续接路由规则，**未展开**；
- BLINDSCAN BS-4 指出：**决策表必须显式纳入 context-rot 维度**，否则被"continue 方便"误导——`--continue` 只带摘要不带细节，重复续跑在 context 已污染时毫无价值甚至有害；
- BLINDSCAN §4（Thariq 五选择框架）："继续"是最差 default；**rewind 优于纠错续跑**；**subagent 是上下文管理手段而非并行工具**；1M 窗口 rot 约 300-400K 起；`/compact` 有损。

**本决策表目标**：在 resume loop 进入第 2 次及后续续跑前，判定"沿用同一 session（`--continue`）" **vs** "另起新 session（`--fork`/spawn）"，把无脑重试升级为 context 感知路由。

---

## 2. 决策输入

### 2.1 各模型窗口真值（context 上限，profile/L2 实测）

| 模型 | 窗口 | 来源 |
|---|---|---|
| gpt-oss（本地） | 131072 | L2 路由测试非硬编码哨兵 |
| lightning（nemotron-3.5-lightning-free）| 262144 | L2 路由 / BS-4 |
| ultra / free-1m（nemotron-3-ultra-free）| 1M | BS-4（rot 300-400K 起）|
| qwen nothink flavor | 8192 | profile 表 |
| qwen think flavor | 32768 | profile 表 |
| qwen long flavor | 262144 | profile 表 |

### 2.2 context 占用感知来源（化合规与可测性）

opencode 无头 run **不打印 session context 占用**（§3.1 已弃 session-id 解析）。可从可测信号推算：

1. **本跑实际消耗**：`.agent-output.txt` 末尾 + `.agent-run.json` 的 `usage.total_tokens`（若可解析）；
2. **累计占用估计**：首跑 + 已续跑次数所累积的 token 量（近似 = Σ各跑 usage，prompt 重读量已被 --continue 摘要压缩）；
3. **profile 窗口**：`Resolve-Profile` 已给出 context 上限（§2.1 表）。

> **组合规则**：`占用率 = Σ续跑 usage / profile 窗口`。无法解析 usage 时降级为**保守上界估算**（首跑质量 ×（续跑次数+1），宁高勿低，避免 rot）。

---

## 3. Continue-vs-Spawn 决策表

**触发点**：resume loop 在**每次续跑后、决策下一次**时评估。轮廓：首跑失败 → 决策① → 续跑1 → 决策② → 续跑2（retry 上限仍 ≤2，本表只改变"续跑 2 次"里的分支，不增加 retry 次数）。

评估优先级从高到低（命中即走对应分支）：

| # | 判定条件 | 占用率阈值 | 决策 | 理由 |
|---|---|---|---|---|
| C0 | **任务已近完成**（accept/golden 差一步，输出尾部含完成态）| 任意 | `--continue`（同 session）| 续跑成本最小，最接近目标 |
| C1 | **context 未过 rot 阈值** | < 窗口×50%（1M 档 ~500K；262k 档 ~131K；本地上限同比例）| `--continue`（同 session）| 仍在安全区，续跑有效 |
| C2 | **context 进入 rot 区** | ≥ 窗口×50% 且 < 窗口×80% | `--fork`（新 session 继承任务目标，不带污染上下文）| BS-4：--continue 只带摘要；fork 保原会话、净化上下文 |
| C3 | **context 接近极限** | ≥ 窗口×80% | **spawn 新任务卡** / 标记 REVIEW_NEEDED 转人工 | 同 session 无续跑价值，重开或升级 |
| C4 | **同局重复失败**（RC≠0 且与上次失败同一命中断点，如同一 golden cmd）| 任意 | **不续跑**，标记 REVIEW_NEEDED（失败模式诊断先行）| 续跑治标不治本；防止同错重跑烧 token |

> **次要维度**（并列任一命中即升级一档）：
> - **任务类型**：`reason`（思考型）context 增长快 → rot 阈值下浮 10%；`code/doc`（执行型）可略高。
> - **敏感度**：`local-only` 无出站选项 → C3/C4 一律回本地重开，禁止远程 spawn。
> - **失败模式**：超时/网络类（RC 因墙钟）→ 倾向 C1 continue；执行/验收类 → 警惕 C4。

---

## 4. rot 阈值表（落地速查）

| 档 | 窗口 | SAFE(continue) 上界 | ROT(fork) 区 | LIMIT(spawn/REVIEW) |
|---|---|---|---|---|
| ultra/free-1m | 1M | < 500K | 500-800K | ≥ 800K |
| lightning/long | 262144 | < 131K | 131-210K | ≥ 210K |
| gpt-oss | 131072 | < 65K | 65-105K | ≥ 105K |
| qwen think | 32768 | < 16K | 16-26K | ≥ 26K |
| qwen nothink | 8192 | < 4K | 4-6.5K | ≥ 6.5K |

---

## 5. 落地映射（wrapper 改动点）

本表是 **G1 决策层**，落在现有 resume loop 外层（`agent-cli.ps1` $body $CONT_ATTEMPT 循环）。保留既有不变式：

- retry 上限仍 ≤2（`.agent-run.json` 续跑前后各一行 RESUME 日志）；
- 分支仅作用于**第二次续跑**的形态：C0-C1 → `--continue`；C2 → `--fork`；C3/C4 → 终止循环、状态标 `REVIEW_NEEDED`；
- `--continue`/`--fork` 复用现有 base64 prompt + 独立 `continue-timeout-s` 预算，不新增参数面。

**工程约束**（遵守项目 hard rules）：
1. 修改 `agent-cli.ps1` 后核对 UTF-8 BOM + `_fm_golden_test.ps1` 离线回归（2026-09-09 V0 复盘）。
2. 二进制/脚本落盘 UTF-8 BOM；决策冒烟走 _continue 续接既有测试路径（CLOSED-LOOP §3.1）。

---

## 6. 验收判据（先写死，post 判定）

| # | 判据 | 通过标准 |
|---|---|---|
| A1 | C1 分支回归 | context < 50% 时失败续跑走 `--continue`，RESUME 日志在 |
| A2 | C2 分支 | context 进入 rot 区时续跑形态切 `--fork`（原 session 保留）|
| A3 | C3/C4 分支 | 不无脑重试；状态标 `REVIEW_NEEDED`，usage 不重复累烧 |
| A4 | retry 上限守住 | 任一卡续跑总数 ≤2，循环不失控 |
| A5 | 既有零倒退 | _continue 续接既有实测（dogfood-resume-recovery v3）不回归 |

---

## 7. 决策输入缺口（后续可补）

- **真实 context 读取**：若后续 vLLM 路径（L0）支持服务端 `/metrics`/usage 回传，决策表可从"估算"升级为"实测"，阈值更准。
- **C4 失败模式归因**：需先落 `.agent-output.txt` 断点指纹（同一 golden cmd 命中识别）——本表标为方向，实施时可与 O-24 断点④（单机治理调卡纪律）联动。

---

**状态**: 🔁 **C4 已落地（2026-09-12）**，C1-C3 保留文档准则（待 context 信号源）。决策表设计本身 finalized；C4 为唯一无信号依赖的机械守卫，已入 wrapper；C1-C3 因现役 opencode 无头 run 无 usage 信号（CLOSED-LOOP §3.1 实证），不作硬编码。

### §5 落地记录（2026-09-12，C4 守卫）

- **改动① 状态真实化**（agent-cli.ps1 $body）：final `.agent-state.json` 不再静默 `done`——`RC≠0` 时 `ST=failed`。
  ```bash
  ST=done; RN=0
  [ "$RC" -ne 0 ] && { ST=failed; RN=1; }
  ```
- **改动② `.meta` 落账**：`.meta` 新增 `REVIEW_NEEDED=%s`（=RN），失败任务供主控/collect 感知"失败未复核"。
- **验证**：BOM 补回（Edit 剥离→EF BB BF 确认）+ `ParseInput` UTF8 AST=0 错误 + `_fm_golden_test.ps1` pass=9 fail=0（zero regression）。
- **信号可行性硬约束（记录决策）**: C1-C3 占率路由需 context usage，但 wrapper 远端 `.agent-output.txt` 无该信号（CLOSED-LOOP §3.1 实证 opencode 无头 run 不打印 usage）→ 硬编码阈值是"从不触发的死代码/误触发的过度实现"，不做。C4 纯 RC 驱动，即时可上线。