# 实施文档：D5 Agent 生态升级与上下文管理落地

***

id: d5-agent-ecosystem-IMPLEMENTATION
type: design
version: 1.0
status: draft
date: 2026-09-02
depends: \[d5-agent-ecosystem-DESIGN v1.3]
upstream: \[ADR-0001 集群运维框架审计与四项改进决策]
---

> **Feature**: D5 Agent 生态升级（两站 claude code / opencode 的技能·插件·上下文管理·跨会话记忆装备）
> **创建日期**: 2026-09-02
> **状态**: implemented（2026-09-02 V0-T6 执行完毕；实施发现 R14-R20 与回退决策见 CHECKLIST §0.2/§5；A5 次日引用验收待补录）
> **Spec 步骤**: Step 5-6
> **基于设计**: [DESIGN.md](./DESIGN.md) v1.3（所有阶段/验收/不变式编号均引自该版）
> **基于调研**: [Agent生态升级与多智能体协作架构调研.md](../../docs/Agent生态升级与多智能体协作架构调研.md)（§8.5-§8.9 三轮审计后 E1 结论）

***

## 1. 实施概述

八个阶段：**V0 验证门**（V1 配置格式 / V2 claude code 窗口基数 / V3 外网连通 / V5 技能加载，\~30min）→ **T1 环境就绪**（版本核验 + PR #42150 决策 + ripgrep 预装）→ **T2 上下文配置**（两站 opencode limit.context + compaction；claude code CLAUDE.md 骨架）→ **T3 原生插件**（superpowers + document-skills，路径由 V3 裁决）→ **T4 定制迁移**（ops/agent-skills/ git 化 → 9 件 Trae 迁移 + 2 件自制，paper-lookup 条件件另计）→ **T4b ARS 原生部署**（timpara 移植版，走已有验证脚本）→ **T5 记忆试点**（B 站 codex-memory）→ **T6 收尾**（手册 + 台账 + CHECKLIST）。

全部操作幂等可重跑；每个阶段独立回滚；不触碰推理层（infer-load / 网关 conf / systemd 服务面），A8 e2e 回归保底。

## 2. 工程细节

### 2.1 技术栈与版本基线

| 组件          | A 站 (NEX)                                                              | B 站 (GTR-Pro)                         | 锁定策略                             |
| ----------- | ---------------------------------------------------------------------- | ------------------------------------- | -------------------------------- |
| opencode    | 1.18.25                                                                | 1.18.25（D4 已验收）                       | 锁版本；PR #42150 决策见 §3.1           |
| claude code | 2.1.220                                                                | 2.1.252                               | 不升级（已支持 plugin 机制；A11 登记）        |
| LiteLLM 网关  | —                                                                      | `http://scott-lau-GTR-Pro.local:4000` | 不动（D1 域）                         |
| 后端模型        | gpt-oss（conf CTX 32768）                                                | nemotron（conf CTX 131072）             | 不动（infer-load 域）                 |
| ripgrep     | apt 待装                                                                 | apt 待装                                | `apt install ripgrep`（#23891 预防） |
| 技能源         | c:\Users\Peng.trae-cn\skills\（9 件迁移 + paper-lookup 条件件；自制 2 件不取自 Trae） | —                                     | 只读源，不修改                          |
| ARS 源       | timpara/opencode-academic-research（git 定版 tag）                         | 同                                     | 不追 main                          |

**SSH 端点**：`scott-lau@scott-lau-NEX.local` / `scott-lau@scott-lau-GTR-Pro.local`（免密已通）。opencode 二进制路径 `~/.opencode/bin/opencode`（B 站 D4 实证；A 站 T1 以 `which opencode` 核实，若不同记入 CHECKLIST）。

### 2.2 版本控制与台账

1. **单一事实源**：`d:\RPC\ops\agent-skills/`（新建，入 d:\RPC git 仓库）——站上 `~/.claude/skills/` 是部署产物，md5 可比对齐（A6）。例外两件不进事实源：superpowers/document-skills（plugin 机制自管理）、ARS（整仓 git 部署）——两者只登记版本进台账。
2. **台账落点**：`spec/d5-agent-ecosystem/CHECKLIST.md` 的 VERSIONS 表（superpowers 版本 / ARS tag+commit hash / 两站两 CLI 版本+锁定理由 / PR #42150 决策记录）。conf CTX ↔ limit.context 联动挂 params-ledger 维护链（DESIGN 不变式③）。
3. **站上配置备份**：改 `opencode.jsonc` 前 `cp opencode.jsonc opencode.jsonc.pre-d5`（每站一份，验收后按 D4 收敛惯例保留此一份）。

### 2.3 文件结构与落点

```
d:\RPC\ops\agent-skills\              # 新建，git 管理（单一事实源）
├── math-finance-reasoning/SKILL.md
├── what-if-oracle/SKILL.md
├── research-scout/SKILL.md           # ×7 research 链同构
├── research-idea/SKILL.md
├── research-baseline/SKILL.md
├── research-experiment/SKILL.md
├── research-decision/SKILL.md
├── research-write/SKILL.md
├── research-finalize/SKILL.md
├── assertion-audit/SKILL.md          # 自制（§3.4.2 全文）
├── cross-examine/SKILL.md            # 自制（§3.4.2 全文）
└── paper-lookup/SKILL.md             # 条件件（P1 连通后定）

站侧落点（两站同构）：
~/.claude/skills/<name>/SKILL.md      # T4 部署产物
~/.claude/CLAUDE.md                   # T2 claude code 全局骨架
~/.config/opencode/opencode.jsonc     # T2 增量合并（limit.context + compaction）
~/.config/opencode/                   # T4b ARS install.sh symlink 落点
~/tools/opencode-academic-research/   # T4b ARS 源目录（git 定版）
~/.local/share/opencode/memories/     # T5 记忆数据（B 站）
```

### 2.4 兼容性矩阵

| 接缝                               | 兼容性依据                                                         | 风险与对策                                                                                    |
| -------------------------------- | ------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Trae SKILL.md → claude code      | 格式同源（frontmatter name+description 必填，调研 §2.1）                 | V5 门单件实测加载；陌生字段仅告警不致命（站上摘除单件即可，DESIGN §7）                                                |
| claude code skills → opencode 双读 | opencode 1.18+ 原生扫描 `~/.claude/skills/*/SKILL.md`（调研 §2.2，E1） | 一站配置两 CLI 生效；A4 验收两侧各触发一次                                                                |
| opencode limit.context 两种写法      | 嵌套式 vs 平铺式两来源冲突（审计 F5）                                        | V1 门裁决；写入前先 `cat` 现有配置增量合并，**不覆盖既有 provider 字段**                                         |
| claude code plugin 安装路径          | marketplace 自动更新破坏链（#41701/#40153，上游零认领）                      | 插件面仅 2 件；每次升级后核验目录存在 + `/` 列表可见（DESIGN §12）；三段式 fallback 直接拷 skills 目录绕开 plugin 机制（§3.3） |
| codex-memory ↔ opencode 1.18.25  | README 只声明 ≥1.18（调研 §6.3）                                     | T5 试点 B 站单站先行；失败回退 four-opencode-memory                                                  |
| ARS install.sh ↔ 本集群             | README E1 实锤但未本集群实测                                           | V6 门（ars-migrate-verify.sh 三模式全跑）                                                        |

### 2.5 性能预算

| 预算                     | 值                                | 依据                                                |
| ---------------------- | -------------------------------- | ------------------------------------------------- |
| nemotron limit.context | 120000（< conf CTX 131072）        | 不变式③：余量给输出，auto-compact 触线前触发                     |
| gpt-oss limit.context  | 30000（< conf CTX 32768）          | 同上；prune 对 32k 路由尤其关键                             |
| 长会话轮数预算                | <50 轮/会话                         | #30067 O(N²)（50-80 轮退化，§8.9 E1）；PR #42150 未入版前的缓解 |
| 网关 rpm 影响              | codex-memory 闲置提取低频调用，rpm=30 不冲突 | 调研 §6.3 选型裁定                                      |
| compaction.reserved    | 20000                            | 调研 §6.2（gpt-oss 32k 路由压缩后仍留工作区）                   |
| skill 触发方式             | 手动 `/` 为主                        | 120B 自动触发弱（调研 §2.1 限制②）；定制 11-12 件不稀释             |

## 3. 模块实施

### 3.0 V0 验证门（\~30min，决定后续路径）

#### 职责

四项 GO/NO-GO 前置验证（V4 claude-mem 属 P2 范围外，不在本门）。

#### 接口签名（命令）

```powershell
# V3: B 站外网连通（github + npm registry，各 5s 超时）
ssh scott-lau@scott-lau-GTR-Pro.local "curl -sI --max-time 5 https://github.com | head -1; curl -sI --max-time 5 https://registry.npmjs.org | head -1"
```

```bash
# V1: 配置格式裁决（主控站有网，先抓 schema 定结构，再站上空跑验证）
#   1) 主控站 PowerShell（无 jq，用 ConvertFrom-Json）:
#      (Invoke-RestMethod https://opencode.ai/config.json).properties.provider | ConvertTo-Json -Depth 8
#      → 人工判读 models.<id> 是否含 limit.context 嵌套字段 → 记录结论进 CHECKLIST
#   2) B 站: 写最小试验配置（嵌套式）→ opencode run 冒烟 → 无 schema 报错即嵌套式成立
#      若报错改平铺式重试；两者皆败 → V1 NO-GO，T2 阻塞但 T3/T4/T4b/T5 照常
# V2: claude code 窗口基数（加载 gpt-oss 后）
#   A 站 claude code 会话内: /context → 记录显示的窗口基数（200k = 陷阱成立 / 读到 32k = 不成立）
# V5: 单件技能加载探针
#   scp research-lookup/SKILL.md 上 B 站 ~/.claude/skills/research-lookup/ →
#   claude code 会话启动无报错 + / 列表可见该件 → GO
```

#### 实施要点

- V1/V2/V3/V5 任一失败只影响对应模块（V1↔T2，V3↔T3/T4b 路径，V5↔T4），不改全局（DESIGN §4.4）

- V2 结果直接决定 T2 的 claude code 侧纪律文案措辞（陷阱成立 → 强制短任务+手动 /compact；不成立 → 建议性）

- 每项产出 GO/NO-GO + 证据（命令输出）进 CHECKLIST（A1）

### 3.1 T1 环境就绪

#### 职责

版本基线核验 + PR #42150 升级决策 + ripgrep 预装（对应验收 A10 前半）。

#### 接口签名（命令）

```bash
# 1. 版本核验（两站）
~/.opencode/bin/opencode --version        # 预期均 1.18.25
claude --version                          # A: 2.1.220 / B: 2.1.252（登记不升级）

# 2. PR #42150 决策（主控站有网执行）
#   查 https://github.com/sst/opencode/releases 中 >1.18.25 的版本说明是否含 #30067/#42150
#   决策树:
#     a) 修复已入某发布版 → 两站升级至该版 → PONG 冒烟 + hook 冒烟 + ARS/T5 全链重验
#     b) 修复未入版 → 保持 1.18.25 + 轮数预算 <50 纪律（手册 A12）
#   决策与理由记录进 CHECKLIST（A10 要求）
#   升级命令（仅分支 a）: ~/.opencode/bin/opencode upgrade && ~/.opencode/bin/opencode --version

# 3. ripgrep 预装（两站，#23891 首跑下载挂死预防）
sudo apt install -y ripgrep && command -v rg
```

#### 实施要点

- 升级分支（a）风险对冲：opencode 有 patch 版内 API 破坏史（#26557/OMO #5575，§8.6.1 E1）——升级后必跑：`opencode run -m cluster-litellm/nemotron 'reply PONG'` + T4b 已装态 `--installed` 模式重验 + T5 记忆功能复验；任一失败 → `opencode upgrade 1.18.25` 回滚

- claude code 不升级理由入台账：2.1.x 已含 plugin 机制；A 站 2.1.220 若遇 T3 版本不兼容报错，届时单独升级并重登台账（不预设）

### 3.2 T2 上下文配置

#### 职责

两站 opencode 声明窗口预算 + 压缩策略；claude code 写全局 CLAUDE.md 骨架（对应 A2、V2 结论回填）。

#### 接口签名（配置内容）

opencode.jsonc **增量合并**（保留既有 provider/其他字段，仅对 cluster-litellm 的模型条目加 limit + 顶层加 compaction；格式以 V1 裁决为准，下为嵌套式示例）：

```jsonc
{
  "provider": {
    "cluster-litellm": {
      "models": {
        "nemotron": { "limit": { "context": 120000, "output": 8192 } },
        "gpt-oss":   { "limit": { "context": 30000,  "output": 8192 } }
      }
    }
  },
  "compaction": { "auto": true, "prune": true, "reserved": 20000 }
}
```

claude code 全局骨架 `~/.claude/CLAUDE.md`（两站同文，V2 结论决定第 3 条措辞强度）：

```markdown
# 集群工作铁律（全局）

- 破坏性文件操作前先备份（.bak + 大小核验）；PowerShell 远端命令走本地脚本→scp→执行
- 修改 /etc/llama-instances/*.env 或 LiteLLM config.yaml 后必须同步 params-ledger.md
- [V2 陷阱成立 → 强制] 长会话/大 codebase 任务用 opencode；claude code 仅短任务，
  每 60-70% 占用手动 /compact（带保留指令），任务切换 /clear
- [V2 陷阱不成立 → 建议] 定期 /context 查余量，<30% 先压缩
- 完整规范见主控站《双机推理集群使用手册》与 d:\RPC 仓库 spec/
```

#### 实施要点

- **写入流程**（每站）：`cp opencode.jsonc opencode.jsonc.pre-d5` → `cat` 现有配置 → 增量合并编辑（PowerShell 远端铁律：本地编辑好全文 scp 覆盖，避免远端 sed）→ `opencode run` PONG 冒烟确认 provider 未被破坏

- **A2 测试法**：人为灌长对话（同一大文件反复 Read 数十次）观察 auto-compact 在 \~120k（nemotron 路由）/ \~30k（gpt-oss 路由）触发而非后端 400；`OPENCODE_DISABLE_AUTOCOMPACT` 环境变量留作排障后备（第三方来源，标注未验证）

- cluster-local provider 若含同名模型条目，同步加相同 limit（cat 时确认）

### 3.3 T3 原生插件（superpowers + document-skills）

#### 职责

两站 claude code 装工程链与文档技能（对应 A3；路径由 V3 裁决）。

#### 接口签名（命令）

```bash
# 路径一（V3 通）: B 站先行，claude code 会话内逐条执行
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
/plugin marketplace add anthropics/skills
/plugin install document-skills@anthropic-agent-skills
#   A 站: 直连失败则临时 https_proxy=http://127.0.0.1:<mihomo端口>（端口以站上 mihomo 配置为准）再试

# 路径二（V3 不通）: 三段式离线定版
#   段1 主控站: git clone --depth 1 https://github.com/obra/superpowers
#               git clone --depth 1 https://github.com/anthropics/skills
#   段2: tar.gz 整包 → scp 两站（规避逐文件 scp 静默失败史）
#   段3 站上: 解包后优先 `claude plugin install <path>`（能力以 `claude plugin --help` 实测为准）；
#             **fallback（与不变式⑥同构）**: 定位仓内技能目录（两仓结构未实测——E5，
#             以 clone 后 find -name SKILL.md 实际布局为准）拷入 ~/.claude/skills/ ——
#             superpowers/document-skills 本体是纯 prompt 技能集，绕开 plugin 机制零损失
```

#### 实施要点

- B 站先行验证后再推 A 站（降低双站同时翻车面）

- 版本登记台账：marketplace 安装记 plugin 版本号；三段式记 clone 的 commit hash

- **#41701 破坏链预防**（A11）：安装完成后立即核验 `~/.claude/plugins/` 目录结构存在 + `/` 列表可见；后续 claude code 每次升级后重跑此核验（DESIGN §12）

- 验收 A3：`/superpowers:brainstorm` 有响应且走设计先行流程；document-skills 产 docx 一例过其自带验证脚本

### 3.4 T4 定制技能迁移（9 件 Trae + 2 件自制）

#### 职责

建主控站单一事实源 → 复制 Trae 9 件 → 新建 2 件自制 → 打包部署两站（对应 A4/A6；依赖 V5 门）。

#### 3.4.1 事实源构建与迁移

```powershell
# 主控站: 建仓 + 逐件复制（源只读不动）
mkdir d:\RPC\ops\agent-skills
$skills = @('math-finance-reasoning','what-if-oracle','research-scout','research-idea',
            'research-baseline','research-experiment','research-decision','research-write',
            'research-finalize')
foreach ($s in $skills) {
  Copy-Item -Recurse "c:\Users\Peng\.trae-cn\skills\$s" "d:\RPC\ops\agent-skills\$s"
}
# 每件核验 frontmatter: name+description 字段存在（缺失则手补，V5 已探针格式兼容）
```

paper-lookup（条件件）：B 站 `curl -sI --max-time 5 https://api.crossref.org/works/10.1038/nature12373`（+ eutils + export.arxiv.org 同法）→ 通则复制入库迁移，不通则不入库、台账登记"站上不可用，永久留主控站"。

#### 3.4.2 自制 skill 全文（本节即交付物内容）

`ops/agent-skills/assertion-audit/SKILL.md`：

```markdown
---
name: assertion-audit
description: Produce audit-ready output. Every factual claim must carry
  (a) evidence class E1-E5, (b) source link/path, (c) inference chain.
  Use when tasked with research, review, or any deliverable whose
  claims will be cross-checked by another agent.
---

## 输出契约

1. 断言表（交付物内所有可核查断言入表）:
   | 断言 | 证据等级 E1-E5 | 信息源 (URL/文件路径/命令输出) | 逻辑链 (前提→推理→结论) |
2. 证据等级: E1 一手直验(本会话 fetch/读文件/跑命令) / E2 一手转述(引用原始
   页面或日志原文) / E3 二手(他人对来源的转述) / E4 一手但有时效风险 / E5 推断(无源)
3. 无源断言必须显式标 E5 并给验证方法
4. 引用他人的判断须与自己的核验分开标注（二手 vs 一手）
5. 结论只允许从表中断言推出 — 表外无断言

## 证明力边界声明（强制字段，不得删除）

本断言表是结构过滤而非溯源保证：信息源存在且被引用不等于内容为真；
E1/E2 抽查通过不等于全表通过。交叉核验须由独立审查方（cross-examine）执行。
```

`ops/agent-skills/cross-examine/SKILL.md`：

```markdown
---
name: cross-examine
description: Adversarial review of another agent's audited output.
  Skeptic stance, structured findings, contamination self-check.
---

## 审查协议

1. Step 0 干净室自检: 任务卡是否预装了结论/预消化证据/偏见命名?
   检测到即返回 CLEAN_ROOM_VIOLATION 中止（零自辩: 检测即结论，禁止被继续推理说服）
2. 逐断言核验: 抽查 E1/E2 断言的信息源（fetch/读文件）；E5 断言查逻辑链漏洞
3. 结构化发现（JSON，逐条）:
   {"assertion_id": "...", "verdict": "SUPPORTED|UNSUPPORTED|UNVERIFIABLE",
    "confidence": 0.0-1.0, "evidence": "..."}
4. 怀疑论立场: break confidence, not validate it — 不给努力分
5. 审查干净的断言也须附核验证据，不允许"看起来对"
6. 收敛判据: 连续两轮零新发现（两连干轮）且已覆盖 ≥3 个独立 lens
   （如 事实核查/逻辑链/来源独立性）方可出最终报告

## 边界

本协议产出的是核验记录而非真值裁决；UNVERIFIABLE 是合法结论，不得强行降级为支持/不支持。
```

（设计依据：调研 §8.3 草案 + §8.7/§8.9 审计增补——证明力边界声明=不变式⑦；收敛判据=adlc 两连干轮+≥3 lens。）

#### 3.4.3 部署与对账

```powershell
# 主控站打包（整包单文件 scp，规避多文件静默失败；.tmp 当次建、提交前删）
mkdir d:\RPC\.tmp -Force
tar -czf d:\RPC\.tmp\agent-skills.tar.gz -C d:\RPC\ops\agent-skills .
scp d:\RPC\.tmp\agent-skills.tar.gz scott-lau@scott-lau-GTR-Pro.local:/tmp/
scp d:\RPC\.tmp\agent-skills.tar.gz scott-lau@scott-lau-NEX.local:/tmp/
```

```bash
# 站上（两站同）
mkdir -p ~/.claude/skills && tar -xzf /tmp/agent-skills.tar.gz -C ~/.claude/skills/
# 对账: 站上 md5 清单 vs 主控站清单（A6 零差异）
cd ~/.claude/skills && find . -name SKILL.md -exec md5sum {} \; | sort
```

#### 实施要点

- 部署产物含 `research-lookup` 探针件（V5 用过）——**不入事实源**（C 类外网依赖），验收后从两站删除，避免"看似可用实则不可用"（DESIGN §6.2 B 方案否决理由）

- git 提交节奏：事实源构建后立即 `git add ops/agent-skills && git commit`（防覆盖铁律：每轮修改后立即 commit+push）

- A4 验收：两站两 CLI `/` 列表可见（claude code 侧 11-12 件 / opencode 侧同 + ARS——ARS symlink 落 `~/.config/opencode/`，claude code 不见，口径分列）+ 抽 3 件触发（math-finance-reasoning 六层框架 / what-if-oracle 分支表 / research-scout 卡片）+ assertion-audit 样例含断言表+证据等级+证明力边界 + cross-examine 样例含干净室自检+三态结构化发现

### 3.5 T4b ARS 原生部署

#### 职责

timpara/opencode-academic-research 定版部署两站（对应 A13；依赖 V3）。

#### 接口签名（命令）

```bash
# 段1 取源（V3 通: 站上直接 clone；不通: 主控站 clone 后 tar.gz scp）
git clone --depth 1 --branch <tag> https://github.com/timpara/opencode-academic-research ~/tools/opencode-academic-research
# 段2 验证脚本（已存在: ops/station-bin/ars-migrate-verify.sh, 签名/退出码见文件头）
#   scp 上站 → sed -i 's/\r$//' ars-migrate-verify.sh → chmod +x
./ars-migrate-verify.sh                  # B 站全流程（V6-1/V6-2 + T4b-2/4 自动化, 终态=已装）
./ars-migrate-verify.sh --installed     # A 站已装态核验（T4b-1 无基线模式）
# 段3 T4b-3 claim-audit 硬门（MANUAL, 网络可达侧）:
#   样本 ~/ars-claim-audit-sample.md（脚本已生成）→ ARS_CLAIM_AUDIT=1 会话内引用该文献
#   → 预期 5 类 HIGH-WARN 之一触发且拒绝输出 → 记录进 CHECKLIST
```

#### 实施要点

- `<tag>` 钉版不追 main；台账登记 tag + `git rev-parse --short HEAD` + install.sh 实测行为（V6-1 输出）

- 全流程模式终态=已装（B 站）；`--leave-removed` 仅用于首站验证失败后的暂不部署形态

- 脚本已知边界：symlink 判定在 git bash 有平台差异，站上 Ubuntu 实测为准（脚本头注记）

### 3.6 T5 记忆试点（B 站 codex-memory）

#### 职责

B 站单站跨会话记忆试点（对应 A5；依赖 T1 版本基线 + npm 连通）。

#### 接口签名（命令）

```bash
# B 站 opencode.jsonc 顶层加一行（版本钉死 @0.6.5，opencode 不自动重解析）
"plugin": ["opencode-codex-memory@0.6.5"]
# 重启 opencode 会话 → 正常使用一个会话（读几个 repo 文件、做一次小任务）
# 闲置 ≥6h 触发后台提取（用 opencode 已配置模型走本地端点）
# 次日验收: 新会话问"上次这个 repo 做了什么" → 应能引用前日内容
ls ~/.local/share/opencode/memories/    # 有 markdown/SQLite 产出
```

#### 实施要点

- 插件经 npm registry 拉取——**V3 的 npm 探测是硬前置**；npm 不通则 T5 延后（试点性质不阻塞 T6 收尾），不改用手工 vendor（避免引入未审计的本地插件加载路径）

- 回退链：codex-memory 异常 → `four-opencode-memory`（零依赖纯 Markdown）→ A5 判据改为 MEMORY.md 增量

- rpm 影响：后台提取低频调用，rpm=30 网关限流不冲突（§2.5）；若观测到 retry-after 背压，查 LiteLLM 日志确认来源

- claude-mem 属 P2（V4 门），本阶段不装——若未来装入，验收强制含"hooks 无双触发"（#24115 复现例即其本尊，§8.9）

### 3.7 T6 收尾

#### 职责

手册/台账/CHECKLIST 回填（对应 A9/A12 及 A10 后半）。

#### 交付内容

1. **手册新增"Agent 生态"节**（排在网关容错节后）：轮数预算指引（<50 轮/会话 + O(N²) 根因一句话）、claude code 短任务纪律（V2 结论措辞）、ARS 外网依赖边界（claim-audit/检索类命令可用性以 V3 为准）、技能手动 `/` 触发纪律、单一事实源变更流程（改仓库→commit→scp 两站）
2. **CHECKLIST.md**：A1-A13 逐项验收记录 + VERSIONS 台账表（§2.2 第 2 条所列五项）+ V0 四门 GO/NO-GO 证据
3. **git 收尾**：全部变更 commit + push；工作区归零

## 4. 实施顺序与检查点

```
V0 验证门 (V1‖V2‖V3‖V5 并行, ~30min)
  ├─ V1 GO ──────────────┐
  ├─ V3 GO ────┐         │
  └─ V5 GO ──┐ │         │
             │ │         │
T1 环境就绪 (版本核验+PR#42150 决策+ripgrep; 独立于 V0 可先行)
  │          │ │         │
  ├─<V3>─ T3 原生插件 (B 站先行 → A 站)      ── 验证: A3
  ├─<V5>─ T4 定制迁移 (事实源 → tar 部署)    ── 验证: A4/A6
  ├─<V3>─ T4b ARS 部署 (验证脚本全跑)        ── 验证: A13
  └─<V1>─ T2 上下文配置 (opencode+CLAUDE.md) ── 验证: A2
                │
T5 记忆试点 (B 站; 依赖 T1+npm, 含 6h 闲置窗口)── 验证: A5
                │
T6 收尾 (手册+台账+CHECKLIST+commit)           ── 验证: A9/A12
                │
最终: A7 零自加载 + A8 e2e 回归 + A10/A11 版本锁定核验 → 全表过 → status: verified
```

T5 的 6h 闲置窗口是唯一不可压缩的等待项——安排在 T2-T4b 执行期间启动闲置计时（并行不阻塞）。

本图是 DESIGN §4.4 线性控制流的并行细化（依赖门以 DESIGN §10 表为准）：T2/T3/T4/T4b 互不依赖，可乱序或并行；字面顺序差异不构成与 DESIGN 的矛盾。

## 5. 验收标准（对应 DESIGN §11，附命令）

| #   | 验收项      | 命令/方法                                                                      | 预期                                                                                                                                                   |
| --- | -------- | -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| A1  | V0 四项验证  | CHECKLIST 记录                                                               | 每项 GO/NO-GO + 证据                                                                                                                                     |
| A2  | 上下文配置生效  | 灌长对话至触线                                                                    | \~120k/30k 触发 auto-compact，无 400                                                                                                                     |
| A3  | 原生技能可用   | `/superpowers:brainstorm`；docx 生成-验证                                       | 响应且走设计先行；docx 过验证脚本                                                                                                                                  |
| A4  | 定制技能可用   | 两站两 CLI `/` 列表 + 抽验                                                        | claude code 侧 11-12 件（9 Trae + 2 自制 + paper-lookup 条件件）/ opencode 侧同 + ARS（symlink 经 `~/.config/opencode/`，claude code 不见——口径分列）；3 件出结构化输出；自制件契约字段齐全 |
| A5  | 记忆生效     | 次日会话问前日内容                                                                  | 引用成功 + memories/ 有产出                                                                                                                                 |
| A6  | 单一事实源对齐  | 站上 `find ~/.claude/skills -name SKILL.md -exec md5sum {} \| sort` vs 主控站同法 | 零差异（探针件删除后）                                                                                                                                          |
| A7  | 零自加载不破   | `systemctl list-unit-files --state=enabled`                                | 与 D1 后基线零新增                                                                                                                                          |
| A8  | e2e 回归   | `python ops/cluster.py e2e`                                                | 退出码 0                                                                                                                                                |
| A9  | 文档回填     | 手册/台账/CHECKLIST                                                            | Agent 生态节 + VERSIONS 表 + 状态更新                                                                                                                        |
| A10 | 环境就绪     | `command -v rg`；`opencode --version`；CHECKLIST                             | rg 非空；版本与台账一致；PR #42150 决策留痕                                                                                                                         |
| A11 | 版本锁定不破   | 台账 + 插件目录核验                                                                | 版本+理由登记；目录存在+列表可见                                                                                                                                    |
| A12 | 长会话预算纪律  | 手册 Agent 生态节                                                               | 轮数预算 + claude code 纪律 + ARS 边界                                                                                                                       |
| A13 | ARS 原生部署 | ars-migrate-verify.sh 全模式 + MANUAL 步骤                                      | 脚本 GO + claim-audit 拒绝 1 条 fabricated + 台账登记                                                                                                         |

## 6. 风险与回滚汇总

| 风险                                | 概率 | 影响        | 回滚                                            |
| --------------------------------- | -- | --------- | --------------------------------------------- |
| V1 两种格式均不生效                       | 低  | T2 阻塞     | 仅 T2 延后；`opencode.jsonc.pre-d5` 恢复            |
| opencode 升级（PR #42150 分支 a）破坏插件面  | 中  | T4b/T5 失效 | `opencode upgrade 1.18.25` 回滚（D4 已验证该路径）      |
| marketplace 安装的插件被自动更新清空（#41701）  | 低  | A3 失效     | 三段式 fallback（skills 直拷）；插件面仅 2 件可快速重装         |
| codex-memory 与 1.18.25 不兼容        | 中  | A5 失败     | four-opencode-memory 替换；再不行 T5 标记"延后"不阻塞验收其余项 |
| Trae 技能含 claude code 不识别字段        | 低  | 单件不加载     | V5 探针 + 单件摘除（DESIGN §7 处置）                    |
| 站上 opencode.jsonc 合并覆盖既有 provider | 低  | 推理调用断     | `.pre-d5` 备份恢复 + PONG 冒烟在每步写后执行               |
| scp/tar 传输静默损坏                    | 低  | A6 不齐     | md5 对账即暴露；重传                                  |
| ARS install.sh 越界写入               | 低  | 环境污染      | ars-migrate-verify.sh V6-1 已含越界检测与卸载核验        |

## 7. 交付物

1. `ops/agent-skills/`（11+2 件，git 管理）+ 两站部署
2. 两站 opencode.jsonc（limit.context + compaction）+ `~/.claude/CLAUDE.md` 骨架
3. 两站 superpowers + document-skills（台账登记版本）
4. 两站 ARS 移植版（tag+hash 登记台账）
5. B 站 codex-memory 试点（含回退决策记录）
6. 手册"Agent 生态"节 + CHECKLIST.md（A1-A13 记录 + VERSIONS 台账）
7. 本 IMPLEMENTATION.md 状态更新为 verified（验收全过后）

***

**Review 签字**: \_\_\_\_\_\_\_\_\_\_\_ 日期: \_\_\_\_\_\_\_\_\_\_\_
