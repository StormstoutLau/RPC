# D:\Paper — 论文知识库项目

> 本文件是**项目指令单一源**（AGENTS.md 开放标准）。唯一编辑点在主控站 `D:\Paper\`；
> 站上 `~/agent-workspaces/paper/` 的同名文件是部署产物，**勿在站上编辑**。

## 项目性质

论文 PDF 的三阶段流水线：**Phase 1** 自动分类整理（paper2kg）→ **Phase 2** 全文提取（PDF → Markdown，四层流水线）→ **Skill 蒸馏**（论文 → 方法论 Skill）。
技术栈：Python 3.10+ / 单向数据流 / YAML 规则外置。

## Agent 工作约定

- **工作区**：`~/agent-workspaces/paper/`；产物一律落 `out/`（D6 约定回收目录）
- **不建 git 仓库**：站上工作区不初始化 git（避免与主控站双源）；源码修改靠 `out/` + diff 回收，由主控站 review 后 commit
- **记忆前缀**：`codex-memory` 的 ad-hoc 笔记全局平铺，首部必须带 `[proj:paper]`（唯一隔离手段）
- **破坏性操作**：覆盖/截断/批量替换前先 `.bak` 并验证大小；禁用 `Get-Content -TotalCount | Set-Content` 截断（PowerShell 5 对 LF 换行文件的解析陷阱）
- **中文路径**：一律 `os.rename(str)`，编码 UTF-8 / NFC 归一化

## 数据安全（Phase 1 / Phase 2 硬约束）

- 源目录（`paper_origin/`、`Paper_Organized_v2/`）**只读**
- `execute` 前必须先 dry-run 并确认；目标写入幂等（可重跑）
- 操作前备份 `index.db` / `phase2_tasks.db`

## 全量蒸馏任务纪律（当前主任务）

- **显式调用 `/paper-distill`** —— 本地 120B 模型对技能自动触发弱，必须点名调用
- **输入** `raw_md_full/<id>.md`（含 `## Page N` 分页标记，N = **物理页码**）
- **输出** `out/skills/<id>_skills.md`
- **上下文纪律**：分段读取，勿一次性载入全文；上下文占用保持 < 窗口 40%
- **锚点纪律**：每个锚点写入前回 `## Page N` 核对当页确有该定理/公式；宁可标 `[待核对]`，**不可编造**
- **落盘兜底**：若 `write` 工具超时/失败，改用 bash heredoc 分块写入（UTF-8 无 BOM），写完 `wc -c` 自证
- **自证**：产物文末必须附「## 蒸馏统计」（Skill 数 / Preconditions 数 / 锚点数）

## 敏感度

- **未发表论文**（来源在 `D:\Article\` 下 / 无 DOI / 人工标记）→ 任务卡 `sensitivity: local-only`，**禁止任何 egress**
- 已发表语料 → `public`
