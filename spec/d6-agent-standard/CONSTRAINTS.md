# 约束文件规范（CONSTRAINTS）：agent prompt 首槽的「约束层」

***

id: d6-agent-standard-CONSTRAINTS
type: spec
version: 0.1
status: draft（--plan 版；规范草案，未执行、未注入代码）
date: 2026-10-16
depends: \[d6-agent-standard-DESIGN v1.4, d6-agent-standard-dogfood-cards]
upstream: \[2026-10-16_Hermes-Agent编排对比与本框架可借鉴项调研 (docs/research/, v1.0 含 §3.5 论文级证据)]
------------

> **Feature**: 定义 agent prompt **首槽**「约束层」文件的 schema 与运行期不变式（agent-cli 注入点）
> **创建日期**: 2026-10-16
> **状态**: draft（--plan 版；规范草案，未执行、未注入代码）
> **依据**: [2026-10-16_Hermes-Agent编排对比与本框架可借鉴项调研.md](../../docs/research/2026-10-16_Hermes-Agent编排对比与本框架可借鉴项调研.md) §3.5（论文级证据：**身份声明近零增益、时而有害；增益来自「流程 + epistemic 约束 + 语域契约」**）
> **性质**: **只读方案** —— 本文只定规范与注入点方案；**不含任何代码写动作**（未改 `agent-cli.ps1`、未改 `cluster.py`、未推站）

***

## 1. 目的与定位

本框架的 agent 编排是**确定性 wrapper**（任务卡 + 单槽 + 工作区排它锁 + strong-accept）。**协议角色**（D7 的「主控站 / 工作站」，`PRM` / `PRW` 禁项）已定义「谁产出、谁裁决」，但**没有「立场 / 约束 / 语域」层**。

本规范补的正是这一层，且**按论文级证据把它的形态钉死为「约束文件」，不是「人设文件」**：

- ❌ **不写身份声明**（「你是资深 X / 专家」）—— 对客观任务近零增益（`2311.10054`：162 角色 × 4 模型 × 2410 题，in-domain 仅 +0.004；`2512.05858`：专家人格无一致增益），且引入**编造资历**（`2511.21569`）与**过度自信**（`2506.00582`）风险，长上下文还会**漂移**（`2402.10962`）。
- ✅ **只写三类内容**：**流程**（验证链 / 多采样 / 先检索后作答）、**epistemic 约束**（不确定即弃答 · 无源不述 · 区分「检索到的」vs「回忆出的」· 逐句给源）、**语域与格式契约**（英文语域 / 术语 / 单位 / LaTeX）。

## 2. 文件 schema

| 区 | 字段 / 内容 | 硬性要求 |
|---|---|---|
| front-matter | `name`（小写 + 连字符，**与文件名同名**）· `description`（≤1024）· `version` · `scope` | 对齐 agentskills.io 的 `name` / `description` 约定，**便于将来并入 skills 面** |
| **§A 流程** | 阶段图 / 验证链 / 采样与检索顺序 | **必填**，且**判据须可机读**（阶段名与顺序固定） |
| **§B 约束** | 弃答规则 · 无源不述 · 检索/回忆区分 · 逐句给源 · 拒绝把叙事当因果 | **必填**；每条须能对上一份**可核证据**（下条） |
| **§C 契约** | 语域（英文）· 术语 · 单位 · 引用格式 · 输出结构 | 必填；★ **推理段必须置于契约之外**（`2408.02442`：约束越严推理退化越大） |
| 禁止项 | 身份声明 · 资历声明 · 语气人设 · 与任务域无关的"角色扮演" | **出现即不合规** |

## 3. 运行期不变式（写死）

1. **首槽**：约束层文本**置于 prompt 最前**（对齐 `SOUL.md` 官方「system prompt 第 1 槽位」）。
2. **缓存纪律**：约束文件变更**默认下个 run 生效**，**禁止 run 中途改写**（`CLAUDE.md` 类实测：中途改**不失效 cache 但也不生效**）；易变内容放断点之后。
3. **推理顺序**：**先自由推理 → 后入格式契约**（`2408.02442`）。
4. **单一来源**：同一 run 只允许**一份**约束文件；**不叠加多份**（避免优先级歧义与 prompt 膨胀）。
5. **可复算**：run 终态须记录 `persona` 名 + `persona_sha256`，与文件字节一一对应。

## 4. 注入点方案（`--plan` 版，**未执行**）

> ★ **关键实测（E1）**：`ops/station-bin/agent-cli.ps1` 在**主控侧**组装 prompt 并 **base64 下发**（`printf '%s' "$promptB64" | base64 -d > "$W/out/.prompt.txt"`）⇒ **约束文件放仓库内即可，无需推站**（站上不需要该文件）。

| # | 拟改动 | 文件 / 位置 | 说明 |
|---|---|---|---|
| P1 | 新增 `--persona <name\|none>` 参数（缺省 = `none` = 现状） | `ops/station-bin/agent-cli.ps1` 参数块（顶层 cmdlet 定义处） | 已在 `inventory/ops.yaml` 的 `station_runtime` 清单 ⇒ **改动合规**（不新增并列脚本，合 ADR-0004 D2） |
| P2 | 注入：拼 `.prompt.txt` 前，读 `spec/d6-agent-standard/constraints/<name>.md`，将其前置 | `agent-cli.ps1` 的 `Invoke-Task` 拼 prompt 段（`.prompt.txt` 生产点） | 约束文件**主控侧读取**；顺序 = 首槽 |
| P3 | 审计：把 `persona` / `persona_sha256` 写入 `runDir/.agent-run.json` | `agent-cli.ps1` 终态契约写作点 | ★ `prompt.txt` **已在证据链 subjects**（`AGENT_EVIDENCE_FILES`）⇒ 输入全文**自动覆盖**，无需新增证据件 |
| P4 | 回退 | 同 P1 | `--persona none`（或缺省）= **逐字回旧行为**，零迁移成本 |

**门禁预判**：改 `.ps1` ⇒ 必过 **BOM + LF**（`syntax` 的 `.ps1-bom` 维度）与 `ps1-golden`（`FM_GOLDEN_TEST`）· 不改 `ops/` 目录结构 ⇒ `scripts` 断言无新登记 · 本 md 若在 `spec/d6-agent-standard/` 顶层 ⇒ 受 `doc-status` / `spec-untested` 约束（见文末节）。

## 5. 验收（正 / 负向，可机读）

- **正**：(a) 带 `--persona <name>` 的 run：`.agent-run.json` 含 `persona` / `persona_sha256`，且 `sha256(约束文件) == persona_sha256` ✔ (b) prompt 首槽 == 约束文件内容 ✔
- **负**：(c) 不带 `--persona`：行为与现状**逐字一致**（回归）✔ (d) 改约束文件后**同一 run 内** prompt 不变、**新 run** 才变 ✔
- **A/B（已做 → No-Go）**：**带 / 不带 / 等长无关文本**三臂对照（48 实例 × 4 类 × 3 臂；本地 GLM-5.3-Flash + OpenRouter 四模型）。结论：**B 臂的改善在等长无关对照臂（B'）上同样出现** ⇒ 效应归因 **prompt 长度**、**不归因约束内容** ⇒ 本框架内**无增益**，**不落 P1–P4**。依据 [metrics-log Phase 10](../rpc-optimization/metrics-log.md)（§3.5 的论文级证据仍为 **E3**；本框架内结论以 Phase 10 为准）。

***

## 未实测登记

> 本规范为 **draft（--plan 版）**：下列条目**尚无本框架内实测**，如实登记，落地前须逐条取证。

| # | 条目 | 状态 | 缺什么 |
|---|---|---|---|
| C-1 | 约束文件对**本框架任务**（低幻觉 / 英文语域 / 深度推理）的**实际增益** | **`done` — No-Go** | 已实测：B 臂相对 A 的"改善"在**等长无关文本对照臂（B'）**上同样出现 ⇒ 归因 **prompt 长度**，不归因约束内容；跨模型四模型无一满足"B<A 且 B'≈A"。证据 [metrics-log Phase 10](../rpc-optimization/metrics-log.md)。**不落 P1–P4、不改 `agent-cli.ps1`** |
| C-2 | 注入后 **prompt 首槽**是否真被模型优先遵循（长上下文漂移，`2402.10962`） | `todo` | 长 run（≥8 轮/长 ctx）下的漂移观测 |
| C-3 | 约束文件注入对 **token 预算 / 上下文占用**的代价 | **`done`** | 已实测：前缀仅 **+845 token**，但**推理段需求翻 2.8–7×**（本地 T-REF 中位 6816 → 18834 字符；`max_tokens=6144` 下 B 臂 **50% 跑不完 / 60% 截断**）⇒ 成本不在前缀而在推理 ⇒ [Phase 10 §10.4](../rpc-optimization/metrics-log.md) |
| C-4 | `--persona` 与 **ROUTE_TABLE 路由 / 敏感度硬路由**的交互 | `todo` | 交叉用例（persona × local-only 卡） |
| C-5 | 格式契约对**推理质量的抑制**在本框架模型上是否复现（`2408.02442` 结论移植性） | **`partial`（两轮；均**未测出**质量抑制，已测出**代价与失败形态**）** | **第 1 轮**（12 个冻结 T-MATH 题 / DS-V4-Flash-0731）：两臂**均 12/12** ⇒ **天花板，无分辨率**；且自由臂落 `reasoning_content`、格式臂落 `content` ⇒ **通道混杂**，非单变量。**第 2 轮**（强化版：改 12 个冻结 **T-REF** 题 + 两臂共同前置"写正文"）：主判据**两臂打平**（编造率 5.5% vs 5.9% · 编造+元数据错误率 21.8% vs 25.0%，`S` 略差、n=12 落在噪声内）⇒ **仍未复现抑制**；但测出**失败形态差异**——`REF-05/S` 因"经典论文普遍无 DOI"而在 `STEP_n` 模板内**空转至 8192 token 顶格、无 `FINAL_JSON`**（同题 `L` 臂 1104 token 正常收尾），`REF-06/L` 反向**冲出契约**（22234 字符全落推理通道、正文空）⇒ **格式契约的代价在「尾部灾难 + token」而非平均质量**（与 C-3 / Phase 10 §10.4 同源）。详见 [metrics-log Phase 11](../rpc-optimization/metrics-log.md) |
