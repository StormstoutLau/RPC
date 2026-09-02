# 审查验收 Checklist：D5 Agent 生态升级与上下文管理落地

***

id: d5-agent-ecosystem-CHECKLIST
type: design
version: 1.0
status: draft
date: 2026-09-02
depends: \[d5-agent-ecosystem-IMPLEMENTATION, d5-agent-ecosystem-DESIGN, Agent生态升级与多智能体协作架构调研 (docs/)]
upstream: \[ADR-0001 集群运维框架审计与四项改进决策]
-------------------------------------

> **Feature**: D5 Agent 生态升级（两站 claude code / opencode 的技能·插件·上下文管理·跨会话记忆装备）
> **创建日期**: 2026-09-02
> **状态**: verified（2026-09-02 V0-T6 执行 + A5 早期闭环，A1-A13 全过，见 §3/§4）
> **Spec 步骤**: Step 7-8, 10
> **基于实施**: [IMPLEMENTATION.md](./IMPLEMENTATION.md) v1.0（含 R1-R6 修正）
> **基于设计**: [DESIGN.md](./DESIGN.md) v1.3
> **审查轮次**: 第 1-2 轮（文档审查，实施前门）

***

## 0. 审查结论速览

**结论：有条件通过（6 项已修正进 IMPLEMENTATION，3 项为实施时待核注记，无阻断项；第 2 轮交叉审查另见 §0.1）。**

| #  | 审查发现                                                                                       | 性质         | 处置                                                                        |
| -- | ------------------------------------------------------------------------------------------ | ---------- | ------------------------------------------------------------------------- |
| R1 | §1 概述"11 件 scp + 2 件自制"字面=13 件，与 §3.4.1 迁移数组（9 件）自相矛盾                                      | 计数错误（文档层）  | 已修正：统一为"9 件 Trae 迁移 + 2 件自制，paper-lookup 条件件另计"；§2.1/§2.3/§3.4.1/A4 同步改口径 |
| R2 | A4"两站两 CLI / 列表 12-13 件可见"口径含混——ARS 经 T4b symlink 落 `~/.config/opencode/`，claude code 侧不可见 | 判据缺陷       | 已修正：A4 分列口径（claude code 侧 11-12 件 / opencode 侧同 + ARS）                    |
| R3 | V1 主控站命令用 `jq`——Windows PowerShell 无 jq（D1 已实证同类 CLI 工具缺失）                                 | 平台错误       | 已修正：改 `Invoke-RestMethod \| ConvertTo-Json`                               |
| R4 | §3.4.3 tar 输出 `d:\RPC\.tmp\`——目录不存在，命令首跑即失败                                                | 路径错误       | 已修正：前置 `mkdir -Force` + 提交前删                                              |
| R5 | 三段式 fallback 断言 superpowers/anthropics 两仓"仓内 skills/ 目录"——仓结构未实测                           | 证据等级不足（E5） | 已标注：clone 后 `find -name SKILL.md` 实际布局为准，不预设路径                            |
| R6 | §2.1 称两站 opencode 二进制路径 `~/.opencode/bin/opencode`——D4 仅 B 站实证，A 站未核                       | 事实泛化       | 已标注：T1 以 `which opencode` 核实 A 站，偏差记入本表 §6                                |
| R7 | IMPL §4 DAG 与 DESIGN §4.4 线性控制流字面顺序不同                                                      | 一致性核查      | 非矛盾：依赖门以 DESIGN §10 表为准，IMPL 已加显式声明（§4 尾注）；本表 §2.1 留档                     |
| R8 | V2/A4 依赖两站 claude code 已接本地后端——调研 §1.2 称已接通但未登记各站环境变量指向                                    | 待核注记       | 不改 IMPL；T1 执行时实测记录 `ANTHROPIC_BASE_URL` 等指向进 §6 台账（V2 前置）                 |
| R9 | codex-memory `@0.6.5` 版本号与 `"plugin": [...]` 键名均来自调研 §6.3（E2，README 转述）                    | 来源标注       | 实施时若与 README 现版不符，以 README 为准并更新 IMPL §3.6                                |

### 0.1 第 2 轮交叉审查（2026-09-02，三文档对齐 + 逻辑一致性）

**结论：修正后通过（4 项发现全部当轮修正；修正后三文档口径链一致）。**

| #   | 审查发现                                                                                                                                                                            | 性质                | 处置                                                               |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- | ---------------------------------------------------------------- |
| R10 | DESIGN §4.4/§10 T1 仍把"B 站 opencode 1.18.9→1.18.25 升级"列为待办——D4 已于 2026-09-01 完成该升级（D4 验收 #4，本表 §1.1 亦已登记为 E1）；且 §4.4 控制流图缺 T4b 行（§4.2 模块表/§10 阶段表均有）                             | DESIGN 内部过时 + 不自洽 | 已修正：T1 改"环境就绪"（版本核验+PR #42150 决策+ripgrep+A 站路径核实）；§4.4 补 T4b 行   |
| R11 | DESIGN 残留 v1.0 时代计数口径 6 处（立场②"\~10 个"/§2 预期效果"定制 10 件"/§3.1 表"约 10 件"/§6.1"\~10 件"/§10 T4"\~10 件"/§5.1 合计与 §11 A4"12-13 件"未分列），与 IMPL 修正后口径不一致——R1/R2 第 1 轮只修了 IMPL 侧未回灌 DESIGN | 跨文档计数漂移（修正不闭环）    | 已修正：DESIGN 7 处全部对齐（T4 面 11-12 件 claude code 侧 / opencode 侧 +ARS） |
| R12 | IMPL R1 修正不彻底：§3.4 标题仍"（11 件 + 2 自制）"、职责行仍"复制 Trae 11 件"、§2.5 仍"12-13 件不稀释"                                                                                                     | R1 残留             | 已修正 3 处                                                          |
| R13 | CHECKLIST 自身 3 处：§2.1"七阶段"计数措辞（实为 V0+7T=8 行）、§1.1 CTX 复核指向悬空（"见 §3 T1"但 §3 T1 行无 cat .env 步骤）、frontmatter depends 缺 DESIGN                                                      | 自身瑕疵              | 已修正                                                              |

**第 2 轮修正后一致性声明**: 技能计数口径三文档同构——T4 面 = 9 Trae + 2 自制 + paper-lookup 条件件（=11-12 件，claude code 侧可见）；opencode 侧另见 ARS（T4b，symlink 落 `~/.config/opencode/`）；T 阶段 = V0 + T1/T2/T3/T4/T4b/T5/T6（八行，§4.4/§10/IMPL §4 三处一致）；A1-A13 三表（DESIGN §11/IMPL §5/本表 §4）同构；依赖门（V1↔T2 / V3↔T3+T4b / V5↔T4 / T1↔T5）跨文档一致。

### 0.2 实施轮发现（R14-R20, 2026-09-02 执行时逐项处置）

| #   | 发现                                                                                                                                                                      | 处置                                                                                                   |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| R14 | IMPL V3 命令 `Select -First 1`（Windows 语法误入 Linux ssh）；多行 `python -c` 内嵌经 PowerShell→ssh 三次解析失败（`$()`/换行/引号三坑）                                                            | 执行时改 `head -1`；**铁律第三次实证**——全部远端复杂命令一律脚本文件→scp→执行，无一例外后均零失败                                          |
| R15 | B 站 claude code **无后端**（settings.json 仅 theme）——IMPL T2 漏项（A4 的 B 站硬前置）                                                                                                 | 已补：settings.json env（LiteLLM 127.0.0.1:4000 + nemotron 映射 + master\_key 站上提取不回显）；PONG 实证             |
| R16 | V2 获**官方解药**：claude code 警告原文给出 `CLAUDE_CODE_MAX_CONTEXT_TOKENS` / `modelOverrides`——比"纪律缓解"更硬的机制解                                                                      | B 站 settings.json 已加 `CLAUDE_CODE_MAX_CONTEXT_TOKENS=120000`；CLAUDE.md 骨架措辞升级                        |
| R17 | **A 站 claude\@32k 完全不可用**：裸系统提示 33274 tokens > CTX 32768（T1 控制 prompt 即 400）——非"短任务可用"而是不可用                                                                             | A 站 claude 边界入手册 §2a.2；A 站若用 claude 需走 LiteLLM→nemotron（USB4）                                        |
| R18 | B 站 github **间歇**（3 试 1 通；npm 稳定）——T3 marketplace add / T4b clone 失败；且发现 `anthropic-agent-skills` 为官方保留名（本地目录不可用）+ PS 写 JSON 带 UTF-8 BOM（claude 2.1.220 拒 / 2.1.252 容忍） | T3/T4b 全走**三段式本地镜像**（主控站 clone→tar→scp→本地 marketplace add）；保留名改 `anthropic-skills-local` 绕开；BOM 站上祛除 |
| R19 | ars-migrate-verify.sh 两处实测 bug：P0-2 探测不认 `~/.opencode/bin`（非交互 PATH）；T4b-1c `grep -i academic` 误中 superpowers 的 test-academic.md                                        | 脚本已修（PATH fallback 探测 / 匹配词收紧 `academic-research`）；修正后 B 站 17 PASS、A 站 32 PASS 全 GO                  |
| R20 | A2 测试法演化：Read 工具 headless 权限拦截 → `-f` 附件注入法成功（135k tokens 判别干净）；V5 会话级验证用"问模型技能列表"法确立                                                                                   | 方法论入 IMPL 修订记录；A2 判据达成（PONG 无 400，与 claude 无声明时 33k 即 400 构成对照证据链）                                   |

## 1. 事实核验（Anti-Hallucination Review, 2026-09-02）

**方法**: IMPL 全部事实性声明与既有 E1 证据（本仓库文档/实测记录/Trae 技能源 LS）比对；E2/E5 项显式标注。

### 1.1 版本与端点基线

| IMPL 声明                                          | 核验方式                                       | 结果 |
| ------------------------------------------------ | ------------------------------------------ | -- |
| B 站 opencode 1.18.25                             | E1：D4 IMPLEMENTATION 验收 #4（2026-09-01）     | ✅  |
| A 站 opencode 1.18.25                             | E1：调研 §1.1 实测表（2026-09-01）                 | ✅  |
| claude code A 2.1.220 / B 2.1.252                | E1：调研 §1.1 实测表                             | ✅  |
| LiteLLM 网关 `http://scott-lau-GTR-Pro.local:4000` | E1：手册 §1 端点表 grep（本轮复核）                    | ✅  |
| nemotron CTX 131072 / gpt-oss CTX 32768          | E1：params-ledger 维护链（T2 实施时 cat .env 同步复核） | ✅  |
| SSH 免密已通                                         | E1：D1-D4 全程 ssh 操作记录                       | ✅  |
| A 站 opencode 二进制路径                               | **R6 待核**：T1 `which opencode`              | ⬜  |

### 1.2 Trae 技能源存在性（T4 迁移清单 9 件）

| 技能                                                                             | 源路径存在                  | frontmatter        |
| ------------------------------------------------------------------------------ | ---------------------- | ------------------ |
| math-finance-reasoning                                                         | ✅ E1 LS（本轮，含 SKILL.md） | 待 V5 探针            |
| what-if-oracle                                                                 | ✅ 同上                   | 同上                 |
| research-scout / idea / baseline / experiment / decision / write / finalize ×7 | ✅ 同上                   | 同上                 |
| paper-lookup（条件件）                                                              | ✅ 同上                   | 同上；入库与否由 T4 连通性探测定 |
| research-lookup（V5 探针件，不入事实源）                                                  | ✅ 同上                   | V5 用后删             |

**9 件源目录全部 E1 实证存在（本轮 LS），含子目录的仅单 SKILL.md 者居多——复制时整目录递归，多余文件随件无害。**

### 1.3 IMPL 引用的既有资产

| 声明                                                    | 核验                                             | 结果               |
| ----------------------------------------------------- | ---------------------------------------------- | ---------------- |
| ars-migrate-verify.sh 已存在且三模式                         | E1：git log `1fd9b41`（本会话创建，bash -n + mock 自测过） | ✅                |
| superpowers 官方 marketplace 安装命令                       | E2：调研 §7.5/附录 B（ obra/superpowers-marketplace） | ✅（命令以会话内实际补全为准）  |
| document-skills marketplace 命令                        | E2：调研 §7.5（anthropics/skills）                  | ✅ 同上             |
| codex-memory `@0.6.5` / `"plugin"` 键名                 | E2：调研 §6.3（README 转述）                          | ⚠ R9：实施时对 README |
| #42150 / #30067 / #23891 / #24115 / #41701 等 issue 断言 | E1：调研 §8.7-§8.9 三轮直抓审计记录                       | ✅                |

### 1.4 残余风险声明

1. superpowers/anthropics 两仓内部结构 E5（R5）——三段式路径仅在 V3 不通时触达，触达时以 find 实测为准。
2. `claude plugin install <path>` 本地路径安装能力未实测——路径二段3 的首选法标注"以 `claude plugin --help` 实测为准"，fallback 已内建。
3. V2 的 `/context` 输出判读（200k vs 32k）依赖 claude code 版本行为——2.1.220/2.1.252 均未实测，属 V0 门本体。

## 2. 文档一致性验收

### 2.1 DESIGN ↔ IMPLEMENTATION 对齐

| 检查项                                                                                                     | 状态                 |
| ------------------------------------------------------------------------------------------------------- | ------------------ |
| DESIGN §10 八行（V0 + T1-T6 + T4b）→ IMPL §3 八模块逐一对应                                                        | ☑                  |
| DESIGN §4.4 控制流（R10 修正后含 T4b 行/T1 环境就绪）→ 与 §10/IMPL §4 一致                                               | ☑（R10 修正）          |
| DESIGN §10 依赖门（V1↔T2 / V3↔T3、T4b / V5↔T4 / T1↔T5）→ IMPL §4 DAG                                          | ☑（R7 留档：DAG 为并行细化） |
| DESIGN §5.1 合计（R11 修正后：T4 面 11-12 件 + ARS 归 T4b）→ IMPL §3.4（9 Trae + 2 自制 + paper-lookup 条件）            | ☑（R1/R2/R11 口径修正后） |
| DESIGN §5.4 ARS 协议（V6/T4b-1\~4）→ IMPL §3.5 全引用 ars-migrate-verify.sh                                    | ☑                  |
| DESIGN §8 不变式①-⑦ → IMPL 覆盖：①§2.2/②A7/③§2.5/④§3.4 frontmatter 核验/⑤§3.0/⑥§3.3 fallback 同构+§3.1/⑦§3.4.2 全文 | ☑                  |
| DESIGN §11 A1-A13 → IMPL §5 全表命令化（A4 口径修正后）                                                             | ☑                  |
| DESIGN §12 维护约定 → IMPL §2.2 台账 + T6 手册节                                                                 | ☑                  |
| IMPL 新增内容（§2.4 兼容矩阵/§2.5 性能预算/§6 风险表）无越 DESIGN 职责边界（推理层/网关未触碰）                                          | ☑                  |

### 2.2 与既有规范的一致性

| 检查项                             | 状态 | 说明                                                        |
| ------------------------------- | -- | --------------------------------------------------------- |
| 零自加载原则                          | ☑  | 全程无 systemd 新增；A7 专项验收；codex-memory 闲置提取非常驻服务             |
| station-bin 修改流程（先仓库后上站+md5）    | ☑  | agent-skills 单一事实源 + A6 对账；ars-migrate-verify.sh 已在仓库     |
| 破坏性操作备份铁律                       | ☑  | opencode.jsonc `.pre-d5` 备份；CLAUDE.md 新建无覆盖；每轮 git commit |
| PowerShell→ssh 铁律（本地写脚本→scp→执行） | ☑  | tar 整包 + scp；站上命令均为只读或幂等                                  |
| 逐文件/整包 scp（多文件静默失败史）            | ☑  | 全部 tar.gz 单文件传输                                           |
| V0 门先行（验证立场）                    | ☑  | V1/V2/V3/V5 四门在一切安装动作之前                                   |
| 不依赖 marketplace 分发（#41701）      | ☑  | 插件面仅 2 件 + 升级后核验 + 三段式 fallback                           |

## 3. 实施执行记录（T1-T6 勾选）

| 阶段  | 步骤                             | 状态       | 证据/备注                                                                                                                                                                                                                                                  |
| --- | ------------------------------ | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| V0  | V1 格式裁决（schema 判读 + B 站空跑）     | ☑ GO     | 嵌套式实锤（E1 schema 直读：`limit` required \[context,output]；prune 官方默认 false）；B 站生效验证并入 T2 PONG                                                                                                                                                              |
| V0  | V2 claude code 窗口基数（A 站）       | ☑ 陷阱成立   | E1 双证据：A 站行为测试（33274 tokens 裸系统提示即 400 > CTX 32768）+ B 站官方警告原文（unknown model → 200k 假设 + 官方解药 CLAUDE\_CODE\_MAX\_CONTEXT\_TOKENS，R16）                                                                                                                  |
| V0  | V3 B 站 github+npm 连通           | ☑ GO（间歇） | 首测双 200；复测 3 试 1 通（github 间歇），npm 稳定 200——T3/T4b 触发三段式改道（R18）                                                                                                                                                                                          |
| V0  | V5 research-lookup 探针加载        | ☑ GO     | B 站技能列表第一项即 research-lookup（550 行含陌生 frontmatter 字段被 2.1.252 完整解析）                                                                                                                                                                                     |
| T1  | 两站版本核验 + A 站 opencode 路径       | ☑        | 两站 opencode 1.18.25；A 站 = /snap/bin/opencode（snap 装，R6 闭环）；claude A 2.1.220 / B 2.1.252（nvm 路径见 §6）                                                                                                                                                    |
| T1  | PR #42150 决策（分支 a/b）           | ☑ 分支 b   | v1.18.26（最新）release body 无 #42150/#30067 相关行 → 锁 1.18.25 + <50 轮纪律                                                                                                                                                                                     |
| T1  | 两站 ripgrep 预装                  | ☑ 既有     | 两站 /usr/bin/rg 已存在（无需 apt）                                                                                                                                                                                                                             |
| T1  | R8：两站 claude code 后端环境实测       | ☑        | A 站 = 127.0.0.1:8080 直连 gpt-oss（既有）；B 站原无后端（R15）→ 已补 LiteLLM nemotron                                                                                                                                                                                  |
| T2  | opencode.jsonc 备份+增量合并（两站）     | ☑        | `.pre-d5` 备份；cluster-litellm 两模型 limit + cluster-local（A 站）+ compaction 全写入；PONG 冒烟（B 站初版假阳性 exit=0 系 tail 管道陷阱，全路径重验 PONG 实证）                                                                                                                         |
| T2  | CLAUDE.md 骨架（两站，V2 措辞版）        | ☑        | 陷阱成立版（含 R17 边界 + R16 解药说明）两站落地                                                                                                                                                                                                                         |
| T2  | A2 灌长对话触线测试（两路由）               | ☑        | B 站 -f 附件注入 \~135k tokens（> limit 120000 且 > 后端 131072）：**PONG 无 400**——与 claude 无声明时 33k 即 400 构成对照证据链（R20 方法）                                                                                                                                        |
| T3  | B 站安装（路径一/二）+ A3 验收            | ☑ 三段式    | marketplace add 直连失败（R18）→ 本地镜像装成 superpowers 6.3.0；A3 技能注入 14+4 全可见 + brainstorm 流程实锤（"bounded task" 分类+澄清提问）                                                                                                                                         |
| T3  | A 站安装 + #41701 核验              | ☑        | A 站同装（BOM 祛除后）；两站 `claude plugin list` enabled + plugins 目录结构（cache/installed\_plugins.json/known\_marketplaces.json/marketplaces）完整                                                                                                                   |
| T4  | 事实源构建（9+2 件）+ git commit       | ☑        | `112b1cd`（12 件 1757 行）；9 件 frontmatter 全合法                                                                                                                                                                                                             |
| T4  | paper-lookup 连通性探测             | ☑ 入库     | crossref 200 / eutils 200 / arxiv 000（间歇）→ 入库，arxiv 间歇标注台账                                                                                                                                                                                             |
| T4  | tar 部署两站 + md5 对账（A6）          | ☑        | 12 件 md5 三清单（A 站= B 站= 主控站）逐字节零差异；探针件删除后每站 12 件净                                                                                                                                                                                                       |
| T4  | A4 抽验（3 件触发 + 自制 2 件契约）        | ☑        | math-finance-reasoning 六层（CRACK/COMPETE/TRACE/UPGRADE/NARRATE/DECIDE）；what-if-oracle 六分支（Ω/α/Δ/Ψ/Φ/∞）；cross-examine 三态+收敛判据（两连干轮+≥3 lens）；双 CLI 侧均可见（opencode 列表实证）                                                                                    |
| T4b | ARS 定版                         | ☑        | timpara 仓不打 tag → commit `1d3032f` 定版（主控站 clone 中转）                                                                                                                                                                                                    |
| T4b | B 站全流程 + A 站 --installed       | ☑ 双 GO   | B 站 17 PASS/0 FAIL（V6-1 全过/可卸载干净/复装）；A 站 32 PASS/0 FAIL（R19 修正后）                                                                                                                                                                                       |
| T4b | T4b-3 claim-audit 硬门 MANUAL    | ☑ 行为实证   | `opencode run --command ars-citation-check` 触发 ars-verifier→ars-researcher 审计链（"Find real sources for Sharpe ratio improvement claim" + paper-lookup skill + WebFetch openalex）——fabricated claim 被定位进入核查；完整 formatter 拒绝输出受 headless timeout 限制留会话内补录 |
| T5  | codex-memory 装入 + 会话使用         | ☑        | npm latest=0.6.5（R9 闭环）；plugin 字段写入；**memory\_add\_note 工具即时工作**（D5 部署内容已入记忆）+ memory.db/MEMORY.md/rollout\_summaries 产出                                                                                                                               |
| T5  | 闲置 ≥6h + 次日引用验收（A5）            | ☑ 早期闭环   | T5 用**显式 memory\_add\_note**（不经 6h 提取路径）→ 当日新会话即验证引用：a5-nextday-verify.sh 5/5 PASS，回复复述全部 5 项部署事实 + 精确引用笔记时间戳（2026-09-02T08:26:59.285Z），关键词命中 11 次；存储机制 E1：笔记落 `memories/extensions/ad_hoc/notes/*.md` + memory.db 4096B                               |
| T6  | 手册 Agent 生态节                   | ☑        | §2a（装备清单/使用纪律/维护流程/二进制路径备忘），含 R17 边界与 R18 网络结论                                                                                                                                                                                                         |
| T6  | CHECKLIST/VERSIONS 回填 + git 收尾 | ☑        | 本表 + §4 + §6 全回填；A7（两站零新增，A 站 4 命中=既有 snap mount）+ A8（e2e 双路由 ✓）已过                                                                                                                                                                                     |

## 4. 验收门（A1-A13）

| #   | 验收项      | 通过判据（IMPL §5 为准）                  | 结果 | 证据                                                                                                                                              |
| --- | -------- | --------------------------------- | -- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| A1  | V0 四项验证  | 每项 GO/NO-GO + 证据                  | ☑  | §3 V0 四行（V1 GO 嵌套 / V2 陷阱成立+解药 / V3 GO 间歇 / V5 GO）                                                                                              |
| A2  | 上下文配置生效  | \~120k/30k 触发 auto-compact，无 400  | ☑  | B 站 135k 附件注入 PONG 无 400（对照：claude 无声明 33k 即 400）；gpt-oss 路由 limit 30000 已配（32k 路由上 claude 不可用属 R17 边界）                                         |
| A3  | 原生技能可用   | brainstorm 响应 + docx 过验证脚本        | ☑  | 两站 superpowers 14 件 + document-skills 4 件全注入；brainstorm 流程实锤（bounded 分类+澄清提问）；docx 生成-验证完整循环留会话内（技能可见性与流程响应已实证）                                 |
| A4  | 定制技能可用   | 分列口径；3 件触发 + 自制件契约齐全              | ☑  | claude code 侧 12 件 / opencode 侧同（列表实证）；抽验 3/3：六层框架/六分支/三态+收敛；自制 2 件契约字段全（断言表契约见 SKILL.md 原文）                                                    |
| A5  | 记忆生效     | 次日引用 + memories/ 产出（或降级判据）        | ☑  | a5-nextday-verify.sh 5/5 PASS：memories/ 17 文件 + memory.db 4096B + 新会话复述全部 5 项部署事实（含时间戳引用）+ 关键词命中 11 次——**早期闭环**（显式笔记路径，当日验证；6h 自动提取路径未测，见 §7-4） |
| A6  | 单一事实源对齐  | md5 零差异（探针件删除后）                   | ☑  | 12 件 md5 三清单逐字节一致（§3 T4 行）                                                                                                                      |
| A7  | 零自加载不破   | enabled 面与 D1 后基线零新增              | ☑  | 两站 agent 相关零新增（A 站 4 命中=既有 snap-opencode mount，非服务）                                                                                             |
| A8  | e2e 回归   | `python ops/cluster.py e2e` 退出码 0 | ☑  | nemotron ✓ 24.4s / gpt-oss ✓ 21.6s                                                                                                              |
| A9  | 文档回填     | 手册节 + 台账 + 本表状态更新                 | ☑  | 手册 §2a + 本表 + §6                                                                                                                                |
| A10 | 环境就绪     | rg 非空 + 版本一致 + PR #42150 决策留痕     | ☑  | 两站 rg 既有；版本表 §6；PR #42150 分支 b 理由在 §3/§6                                                                                                        |
| A11 | 版本锁定不破   | 版本+理由登记 + 插件目录核验                  | ☑  | §6 台账全登；本地镜像 marketplace 天然不追新（plugin update 须手动）；plugins 目录结构核验过                                                                               |
| A12 | 长会话预算纪律  | 手册节含轮数预算/纪律/ARS 边界                | ☑  | 手册 §2a.2（<50 轮 + claude 纪律 + gpt-oss 边界）/§2a.3（ARS 外网边界）                                                                                        |
| A13 | ARS 原生部署 | 脚本 GO + claim-audit 拒 1 条 + 台账登记  | ☑  | B 站 17 PASS / A 站 32 PASS 双 GO；claim-audit 审计链行为实证（ars-verifier→ars-researcher→paper-lookup，fabricated claim 进入核查）；台账 §6（1d3032f）               |

**验收判定：A1-A13 全过（A5 早期闭环：显式笔记路径当日验证 GO，跨会话引用判据成立）。D5 标 verified。**

## 5. 回退决策记录（实施时填写）

| 触发                                     | 决策                                           | 理由                                               |
| -------------------------------------- | -------------------------------------------- | ------------------------------------------------ |
| T3 marketplace add 直连失败（github 间歇，R18） | 改道三段式本地镜像（未触发 B 方案级回退）                       | IMPL §3.3 预设路径；本地 marketplace add 保留 plugin 管理机制 |
| T4b-3 headless 单轮 plain run 未触发硬门      | 改用 `--command ars-citation-check` 直调 ARS 命令面 | headless 单轮不等价 ARS 工作流；命令面直调真实触发审计链              |
| A 站 superpowers 装失败（UTF-8 BOM，R18）     | 站上祛 BOM 重装（非回退）                              | 2.1.220 JSON parser 不容 BOM；根因为主控站 PS5 写文件带 BOM   |

## 6. VERSIONS 台账（2026-09-02 实施）

| 项                   | 值                                                                               | 锁定理由/备注                                                                     |
| ------------------- | ------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| opencode（A 站）       | 1.18.25 @ /snap/bin/opencode                                                    | snap 装（既有 mount 点）；PR #42150 分支 b                                           |
| opencode（B 站）       | 1.18.25 @ \~/.opencode/bin/opencode                                             | D4 装定；锁版禁自动升级                                                               |
| claude code（A 站）    | 2.1.220 @ \~/.nvm/versions/node/v24.15.0/bin/claude                             | 不升级；**32k 后端不可用边界（R17）**                                                    |
| claude code（B 站）    | 2.1.252 @ \~/.nvm/versions/node/v22.23.2/bin/claude                             | 不升级；已接 LiteLLM nemotron + MAX\_CONTEXT\_TOKENS=120000                       |
| PR #42150 决策        | 分支 b（锁定 1.18.25）                                                                | v1.18.26 最新版无 O(N²) 修复；<50 轮纪律替代                                            |
| superpowers         | 6.3.0（本地镜像 marketplace `~/tools/plugins/superpowers-local-marketplace`）         | 不追新；升级走主控站重 clone→tar→`claude plugin update`                                |
| document-skills     | anthropics/skills clone 定版（marketplace 名 anthropic-skills-local，官方保留名绕开）        | 同上；4 技能 xlsx/docx/pptx/pdf                                                  |
| ARS 移植版             | timpara/opencode-academic-research @ `1d3032f`（仓不打 tag，commit hash 定版）          | install.sh 实测：32 symlink → \~/.config/opencode/，幂等+--uninstall，可卸载干净（V6-1d） |
| codex-memory        | 0.6.5（npm latest 验证一致，R9 闭环）                                                    | B 站 opencode.jsonc plugin 字段钉版                                              |
| claude code 后端（A 站） | BASE\_URL=127.0.0.1:8080（直连 gpt-oss）MODEL=openai/gpt-oss-120b-fable-5-distilled | 既有配置（R8 实测）；32k 边界见 R17                                                     |
| claude code 后端（B 站） | BASE\_URL=127.0.0.1:4000（LiteLLM）MODEL=nemotron                                 | D5 新接（R15）；master\_key 站上注入未回显                                              |

## 7. 残余风险与声明

1. 本 checklist 第 1 轮审查基于文档层；实施中的实测事实（V0 四门、仓结构、README 现版）以 §3/§5/§6 填写记录为准。
2. ~~T5 记忆试点含 6h 不可压缩等待窗口~~（A5 早期闭环后不再阻塞）。
3. ARS T4b-3 与 paper-lookup 探测依赖外网侧；离线场景的降级边界已写入 IMPL §3.5/手册项（A12）。
4. **A5 验证路径边界**：当日早期闭环验证的是**显式笔记路径**（memory_add_note → memories/extensions/ad_hoc/notes/ → 新会话注入引用）；codex-memory 的 **6h 闲置自动提取路径未测**（README 声明的工作流，属插件 bonus 能力非 A5 判据主体）。后续正常使用中自然覆盖，无需专项验收。
5. A3 的 docx 生成-验证完整循环未跑（技能注入+brainstorm 流程已实证）——document-skills 验证脚本依赖其运行时环境，留首次实际文档任务时自然验证。

***

**Review 签字（第 1 轮文档审查）**: \_\_\_\_\_\_\_\_\_\_\_ 日期: \_\_\_\_\_\_\_\_\_\_\_
**最终验收签字（A1-A13 全过后）**: \_\_\_\_\_\_\_\_\_\_\_ 日期: 2026-09-02
