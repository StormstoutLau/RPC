# 审查验收 Checklist：D5 Agent 生态升级与上下文管理落地

---

id: d5-agent-ecosystem-CHECKLIST
type: design
version: 1.0
status: draft
date: 2026-09-02
depends: [d5-agent-ecosystem-IMPLEMENTATION, d5-agent-ecosystem-DESIGN, Agent生态升级与多智能体协作架构调研 (docs/)]
upstream: [ADR-0001 集群运维框架审计与四项改进决策]
---

> **Feature**: D5 Agent 生态升级（两站 claude code / opencode 的技能·插件·上下文管理·跨会话记忆装备）
> **创建日期**: 2026-09-02
> **状态**: 待实施（第 1 轮文档审查已完成，见 §0）
> **Spec 步骤**: Step 7-8, 10
> **基于实施**: [IMPLEMENTATION.md](./IMPLEMENTATION.md) v1.0（含 R1-R6 修正）
> **基于设计**: [DESIGN.md](./DESIGN.md) v1.3
> **审查轮次**: 第 1-2 轮（文档审查，实施前门）

---

## 0. 审查结论速览

**结论：有条件通过（6 项已修正进 IMPLEMENTATION，3 项为实施时待核注记，无阻断项；第 2 轮交叉审查另见 §0.1）。**

| # | 审查发现 | 性质 | 处置 |
| - | ------- | ---- | ---- |
| R1 | §1 概述"11 件 scp + 2 件自制"字面=13 件，与 §3.4.1 迁移数组（9 件）自相矛盾 | 计数错误（文档层） | 已修正：统一为"9 件 Trae 迁移 + 2 件自制，paper-lookup 条件件另计"；§2.1/§2.3/§3.4.1/A4 同步改口径 |
| R2 | A4"两站两 CLI / 列表 12-13 件可见"口径含混——ARS 经 T4b symlink 落 `~/.config/opencode/`，claude code 侧不可见 | 判据缺陷 | 已修正：A4 分列口径（claude code 侧 11-12 件 / opencode 侧同 + ARS） |
| R3 | V1 主控站命令用 `jq`——Windows PowerShell 无 jq（D1 已实证同类 CLI 工具缺失） | 平台错误 | 已修正：改 `Invoke-RestMethod \| ConvertTo-Json` |
| R4 | §3.4.3 tar 输出 `d:\RPC\.tmp\`——目录不存在，命令首跑即失败 | 路径错误 | 已修正：前置 `mkdir -Force` + 提交前删 |
| R5 | 三段式 fallback 断言 superpowers/anthropics 两仓"仓内 skills/ 目录"——仓结构未实测 | 证据等级不足（E5） | 已标注：clone 后 `find -name SKILL.md` 实际布局为准，不预设路径 |
| R6 | §2.1 称两站 opencode 二进制路径 `~/.opencode/bin/opencode`——D4 仅 B 站实证，A 站未核 | 事实泛化 | 已标注：T1 以 `which opencode` 核实 A 站，偏差记入本表 §6 |
| R7 | IMPL §4 DAG 与 DESIGN §4.4 线性控制流字面顺序不同 | 一致性核查 | 非矛盾：依赖门以 DESIGN §10 表为准，IMPL 已加显式声明（§4 尾注）；本表 §2.1 留档 |
| R8 | V2/A4 依赖两站 claude code 已接本地后端——调研 §1.2 称已接通但未登记各站环境变量指向 | 待核注记 | 不改 IMPL；T1 执行时实测记录 `ANTHROPIC_BASE_URL` 等指向进 §6 台账（V2 前置） |
| R9 | codex-memory `@0.6.5` 版本号与 `"plugin": [...]` 键名均来自调研 §6.3（E2，README 转述） | 来源标注 | 实施时若与 README 现版不符，以 README 为准并更新 IMPL §3.6 |

### 0.1 第 2 轮交叉审查（2026-09-02，三文档对齐 + 逻辑一致性）

**结论：修正后通过（4 项发现全部当轮修正；修正后三文档口径链一致）。**

| # | 审查发现 | 性质 | 处置 |
| - | ------- | ---- | ---- |
| R10 | DESIGN §4.4/§10 T1 仍把"B 站 opencode 1.18.9→1.18.25 升级"列为待办——D4 已于 2026-09-01 完成该升级（D4 验收 #4，本表 §1.1 亦已登记为 E1）；且 §4.4 控制流图缺 T4b 行（§4.2 模块表/§10 阶段表均有） | DESIGN 内部过时 + 不自洽 | 已修正：T1 改"环境就绪"（版本核验+PR #42150 决策+ripgrep+A 站路径核实）；§4.4 补 T4b 行 |
| R11 | DESIGN 残留 v1.0 时代计数口径 6 处（立场②"~10 个"/§2 预期效果"定制 10 件"/§3.1 表"约 10 件"/§6.1"~10 件"/§10 T4"~10 件"/§5.1 合计与 §11 A4"12-13 件"未分列），与 IMPL 修正后口径不一致——R1/R2 第 1 轮只修了 IMPL 侧未回灌 DESIGN | 跨文档计数漂移（修正不闭环） | 已修正：DESIGN 7 处全部对齐（T4 面 11-12 件 claude code 侧 / opencode 侧 +ARS） |
| R12 | IMPL R1 修正不彻底：§3.4 标题仍"（11 件 + 2 自制）"、职责行仍"复制 Trae 11 件"、§2.5 仍"12-13 件不稀释" | R1 残留 | 已修正 3 处 |
| R13 | CHECKLIST 自身 3 处：§2.1"七阶段"计数措辞（实为 V0+7T=8 行）、§1.1 CTX 复核指向悬空（"见 §3 T1"但 §3 T1 行无 cat .env 步骤）、frontmatter depends 缺 DESIGN | 自身瑕疵 | 已修正 |

**第 2 轮修正后一致性声明**: 技能计数口径三文档同构——T4 面 = 9 Trae + 2 自制 + paper-lookup 条件件（=11-12 件，claude code 侧可见）；opencode 侧另见 ARS（T4b，symlink 落 `~/.config/opencode/`）；T 阶段 = V0 + T1/T2/T3/T4/T4b/T5/T6（八行，§4.4/§10/IMPL §4 三处一致）；A1-A13 三表（DESIGN §11/IMPL §5/本表 §4）同构；依赖门（V1↔T2 / V3↔T3+T4b / V5↔T4 / T1↔T5）跨文档一致。

## 1. 事实核验（Anti-Hallucination Review, 2026-09-02）

**方法**: IMPL 全部事实性声明与既有 E1 证据（本仓库文档/实测记录/Trae 技能源 LS）比对；E2/E5 项显式标注。

### 1.1 版本与端点基线

| IMPL 声明 | 核验方式 | 结果 |
| ------- | ------- | ---- |
| B 站 opencode 1.18.25 | E1：D4 IMPLEMENTATION 验收 #4（2026-09-01） | ✅ |
| A 站 opencode 1.18.25 | E1：调研 §1.1 实测表（2026-09-01） | ✅ |
| claude code A 2.1.220 / B 2.1.252 | E1：调研 §1.1 实测表 | ✅ |
| LiteLLM 网关 `http://scott-lau-GTR-Pro.local:4000` | E1：手册 §1 端点表 grep（本轮复核） | ✅ |
| nemotron CTX 131072 / gpt-oss CTX 32768 | E1：params-ledger 维护链（T2 实施时 cat .env 同步复核） | ✅ |
| SSH 免密已通 | E1：D1-D4 全程 ssh 操作记录 | ✅ |
| A 站 opencode 二进制路径 | **R6 待核**：T1 `which opencode` | ⬜ |

### 1.2 Trae 技能源存在性（T4 迁移清单 9 件）

| 技能 | 源路径存在 | frontmatter |
| -- | -------- | ----------- |
| math-finance-reasoning | ✅ E1 LS（本轮，含 SKILL.md） | 待 V5 探针 |
| what-if-oracle | ✅ 同上 | 同上 |
| research-scout / idea / baseline / experiment / decision / write / finalize ×7 | ✅ 同上 | 同上 |
| paper-lookup（条件件） | ✅ 同上 | 同上；入库与否由 T4 连通性探测定 |
| research-lookup（V5 探针件，不入事实源） | ✅ 同上 | V5 用后删 |

**9 件源目录全部 E1 实证存在（本轮 LS），含子目录的仅单 SKILL.md 者居多——复制时整目录递归，多余文件随件无害。**

### 1.3 IMPL 引用的既有资产

| 声明 | 核验 | 结果 |
| -- | --- | ---- |
| ars-migrate-verify.sh 已存在且三模式 | E1：git log `1fd9b41`（本会话创建，bash -n + mock 自测过） | ✅ |
| superpowers 官方 marketplace 安装命令 | E2：调研 §7.5/附录 B（ obra/superpowers-marketplace） | ✅（命令以会话内实际补全为准） |
| document-skills marketplace 命令 | E2：调研 §7.5（anthropics/skills） | ✅ 同上 |
| codex-memory `@0.6.5` / `"plugin"` 键名 | E2：调研 §6.3（README 转述） | ⚠ R9：实施时对 README |
| #42150 / #30067 / #23891 / #24115 / #41701 等 issue 断言 | E1：调研 §8.7-§8.9 三轮直抓审计记录 | ✅ |

### 1.4 残余风险声明

1. superpowers/anthropics 两仓内部结构 E5（R5）——三段式路径仅在 V3 不通时触达，触达时以 find 实测为准。
2. `claude plugin install <path>` 本地路径安装能力未实测——路径二段3 的首选法标注"以 `claude plugin --help` 实测为准"，fallback 已内建。
3. V2 的 `/context` 输出判读（200k vs 32k）依赖 claude code 版本行为——2.1.220/2.1.252 均未实测，属 V0 门本体。

## 2. 文档一致性验收

### 2.1 DESIGN ↔ IMPLEMENTATION 对齐

| 检查项 | 状态 |
| ----- | --- |
| DESIGN §10 八行（V0 + T1-T6 + T4b）→ IMPL §3 八模块逐一对应 | ☑ |
| DESIGN §4.4 控制流（R10 修正后含 T4b 行/T1 环境就绪）→ 与 §10/IMPL §4 一致 | ☑（R10 修正） |
| DESIGN §10 依赖门（V1↔T2 / V3↔T3、T4b / V5↔T4 / T1↔T5）→ IMPL §4 DAG | ☑（R7 留档：DAG 为并行细化） |
| DESIGN §5.1 合计（R11 修正后：T4 面 11-12 件 + ARS 归 T4b）→ IMPL §3.4（9 Trae + 2 自制 + paper-lookup 条件） | ☑（R1/R2/R11 口径修正后） |
| DESIGN §5.4 ARS 协议（V6/T4b-1~4）→ IMPL §3.5 全引用 ars-migrate-verify.sh | ☑ |
| DESIGN §8 不变式①-⑦ → IMPL 覆盖：①§2.2/②A7/③§2.5/④§3.4 frontmatter 核验/⑤§3.0/⑥§3.3 fallback 同构+§3.1/⑦§3.4.2 全文 | ☑ |
| DESIGN §11 A1-A13 → IMPL §5 全表命令化（A4 口径修正后） | ☑ |
| DESIGN §12 维护约定 → IMPL §2.2 台账 + T6 手册节 | ☑ |
| IMPL 新增内容（§2.4 兼容矩阵/§2.5 性能预算/§6 风险表）无越 DESIGN 职责边界（推理层/网关未触碰） | ☑ |

### 2.2 与既有规范的一致性

| 检查项 | 状态 | 说明 |
| ----- | --- | ---- |
| 零自加载原则 | ☑ | 全程无 systemd 新增；A7 专项验收；codex-memory 闲置提取非常驻服务 |
| station-bin 修改流程（先仓库后上站+md5） | ☑ | agent-skills 单一事实源 + A6 对账；ars-migrate-verify.sh 已在仓库 |
| 破坏性操作备份铁律 | ☑ | opencode.jsonc `.pre-d5` 备份；CLAUDE.md 新建无覆盖；每轮 git commit |
| PowerShell→ssh 铁律（本地写脚本→scp→执行） | ☑ | tar 整包 + scp；站上命令均为只读或幂等 |
| 逐文件/整包 scp（多文件静默失败史） | ☑ | 全部 tar.gz 单文件传输 |
| V0 门先行（验证立场） | ☑ | V1/V2/V3/V5 四门在一切安装动作之前 |
| 不依赖 marketplace 分发（#41701） | ☑ | 插件面仅 2 件 + 升级后核验 + 三段式 fallback |

## 3. 实施执行记录（T1-T6 勾选）

| 阶段 | 步骤 | 状态 | 证据/备注 |
| ---- | --- | ---- | -------- |
| V0 | V1 格式裁决（schema 判读 + B 站空跑） | ⬜ | GO/NO-GO + 结论：嵌套式/平铺式 |
| V0 | V2 claude code 窗口基数（A 站 /context） | ⬜ | 记录基数：____（200k=陷阱成立/32k=不成立） |
| V0 | V3 B 站 github+npm 连通 | ⬜ | 记录 HTTP 状态码 |
| V0 | V5 research-lookup 探针加载 | ⬜ | claude code 启动无报错 + / 列表可见 |
| T1 | 两站版本核验 + A 站 opencode 路径 | ⬜ | `which opencode` 输出记 §6 |
| T1 | PR #42150 决策（分支 a/b） | ⬜ | 决策+理由记 §6；分支 a 需升级+三重重验 |
| T1 | 两站 ripgrep 预装 | ⬜ | `command -v rg` 输出 |
| T1 | R8：两站 claude code 后端环境实测 | ⬜ | ANTHROPIC_BASE_URL/MODEL 指向记 §6 |
| T2 | opencode.jsonc 备份+增量合并（两站） | ⬜ | `.pre-d5` 存在 + PONG 冒烟过 |
| T2 | CLAUDE.md 骨架（两站，V2 措辞版） | ⬜ | V2 结论回填 |
| T2 | A2 灌长对话触线测试（两路由） | ⬜ | ~120k/~30k 触发，无 400 |
| T3 | B 站安装（路径一/二）+ A3 验收 | ⬜ | 路径记录 + `/superpowers:brainstorm` + docx 验证 |
| T3 | A 站安装 + #41701 核验（目录+/列表） | ⬜ | 两站均记录 |
| T4 | 事实源构建（9+2 件）+ git commit | ⬜ | commit hash：____ |
| T4 | paper-lookup 连通性探测（crossref/eutils/arxiv） | ⬜ | 入库/留主控站，结论记录 |
| T4 | tar 部署两站 + md5 对账（A6） | ⬜ | 探针件删除后零差异 |
| T4 | A4 抽验（3 件触发 + 自制 2 件契约） | ⬜ | 双 CLI 口径分列记录 |
| T4b | ARS 定版 tag 确定 | ⬜ | tag：____ |
| T4b | B 站全流程（脚本 GO）+ A 站 --installed | ⬜ | 脚本输出贴录 |
| T4b | T4b-3 claim-audit 硬门 MANUAL | ⬜ | 触发类别：____ |
| T5 | codex-memory 装入 + 会话使用 | ⬜ | npm 通则装，不通则延后记录 |
| T5 | 闲置 ≥6h + 次日引用验收（A5） | ⬜ | 引用内容摘录 |
| T6 | 手册 Agent 生态节 + 回退决策记录 | ⬜ | 含 R9 处置结论 |
| T6 | CHECKLIST/VERSIONS 回填 + git 收尾 | ⬜ | commit hash：____ |

## 4. 验收门（A1-A13）

| # | 验收项 | 通过判据（IMPL §5 为准） | 结果 | 证据 |
| - | ----- | ---------------------- | ---- | ---- |
| A1 | V0 四项验证 | 每项 GO/NO-GO + 证据 | ⬜ | |
| A2 | 上下文配置生效 | ~120k/30k 触发 auto-compact，无 400 | ⬜ | |
| A3 | 原生技能可用 | brainstorm 响应 + docx 过验证脚本 | ⬜ | |
| A4 | 定制技能可用 | 分列口径见 IMPL §5；3 件触发 + 自制件契约齐全 | ⬜ | |
| A5 | 记忆生效 | 次日引用 + memories/ 产出（或降级判据） | ⬜ | |
| A6 | 单一事实源对齐 | md5 零差异（探针件删除后） | ⬜ | |
| A7 | 零自加载不破 | enabled 面与 D1 后基线零新增 | ⬜ | |
| A8 | e2e 回归 | `python ops/cluster.py e2e` 退出码 0 | ⬜ | |
| A9 | 文档回填 | 手册节 + 台账 + 本表状态更新 | ⬜ | |
| A10 | 环境就绪 | rg 非空 + 版本一致 + PR #42150 决策留痕 | ⬜ | |
| A11 | 版本锁定不破 | 版本+理由登记 + 插件目录核验 | ⬜ | |
| A12 | 长会话预算纪律 | 手册节含轮数预算/纪律/ARS 边界 | ⬜ | |
| A13 | ARS 原生部署 | 脚本 GO + claim-audit 拒 1 条 + 台账登记 | ⬜ | |

## 5. 回退决策记录（实施时填写）

| 触发 | 决策 | 理由 |
| ---- | --- | ---- |
| （如 V1 双格式皆败 / codex-memory 不兼容 / T4b 脚本 FAIL） | | |

## 6. VERSIONS 台账（实施时填写）

| 项 | 值 | 锁定理由/备注 |
| -- | -- | ---------- |
| opencode（A 站） | 1.18.25 | A 站二进制路径：____（R6） |
| opencode（B 站） | 1.18.25 | `~/.opencode/bin/opencode`（D4 实证） |
| claude code（A 站） | 2.1.220 | 不升级（plugin 机制已有） |
| claude code（B 站） | 2.1.252 | 同上 |
| PR #42150 决策 | 分支：a/b | 理由：____ |
| superpowers 版本 | ____ | marketplace 版本号或 clone commit hash |
| document-skills 版本 | ____ | 同上 |
| ARS 移植版 | tag：____ hash：____ | install.sh 实测行为记录：____ |
| codex-memory | 0.6.5（R9 对 README） | 键名/版本以 README 现版为准 |
| claude code 后端环境（A 站） | BASE_URL：____ MODEL：____ | R8 |
| claude code 后端环境（B 站） | BASE_URL：____ MODEL：____ | R8 |

## 7. 残余风险与声明

1. 本 checklist 第 1 轮审查基于文档层；实施中的实测事实（V0 四门、仓结构、README 现版）以 §3/§5/§6 填写记录为准。
2. T5 记忆试点含 6h 不可压缩等待窗口——验收可分两批（其余项先行，A5 后补）。
3. ARS T4b-3 与 paper-lookup 探测依赖外网侧；离线场景的降级边界已写入 IMPL §3.5/手册项（A12）。

---

**Review 签字（第 1 轮文档审查）**: ___________ 日期: ___________
**最终验收签字（全过后）**: ___________ 日期: ___________
