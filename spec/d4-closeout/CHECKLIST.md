# 审查验收 Checklist：D4 收尾清理

---
id: d4-closeout-CHECKLIST
type: design
version: 1.1
status: pending
date: 2026-09-01
depends: [d4-closeout-IMPLEMENTATION, d4-closeout-RESEARCH]
upstream: null
---

> **Feature**: D4 收尾清理
> **创建日期**: 2026-09-01
> **状态**: 待验收
> **Spec 步骤**: Step 7-8, 10
> **基于实施**: [IMPLEMENTATION.md](./IMPLEMENTATION.md)
> **基于调研**: [RESEARCH.md](./RESEARCH.md)
> **审查轮次**: 第 1 轮（2026-09-01 晚，反幻觉审查 + 文档一致性）

---

## 0. 审查结论速览

**结论：REVISION 后有条件通过。** 审查抓出 4 处幻觉/错误（H1-H4），已全部在文档中修订；新增 1 个操作项 T6（B 站僵尸 cron 清理）。修订后文档与本 checklist 一并提交，实施可启动。

| 审查发现 | 性质 | 处置 |
|---------|------|------|
| H1: IMPL 风险表虚构"E1 crontab 已核"（当时未核对） | 编造证据等级 | 已修正为实测双向核（systemd + crontab）；并催生 T6 |
| H2: "经 A 站 mihomo 代理"备选实际不可用（仅 127.0.0.1 监听） | 未验证机制假设 | 已改为"A 站下载 → scp"路径 |
| H3: gptoss_spec_test2.sh 疑含未知内容 | 补核后消除疑虑 | 实测纯 CRLF 差异，核对门关闭 |
| H4: 根因报告 F4"B 站无 bjork cron"被实测推翻 | 上游文档事实错误 | RESEARCH §3.6 勘误记录；主结论不受影响 |

## 1. 文档一致性验收（Step 8）

### 1.1 RESEARCH.md ↔ IMPLEMENTATION.md 对齐

| 检查项 | 状态 | 说明 |
|--------|------|------|
| RESEARCH §3.1 四处 key 残留 → IMPL T2 清理清单 | ☑ | 4 文件 + d4probe.sh + fixa.sh 一致 |
| RESEARCH §3.2 gptoss 纯 CRLF → IMPL T1 核对门关闭 | ☑ | 修订后两侧一致（§4.3 划线更新） |
| RESEARCH §3.4 升级机制 → IMPL T4 命令定型 | ☑ | `opencode upgrade` 子命令 + md5 锚点 |
| RESEARCH §3.6 发现 1 → IMPL T6 | ☑ | 僵尸 cron 清理含前置断言与回滚 |
| RESEARCH §3.6 发现 2 → IMPL T4 网络备选修正 | ☑ | 两处均已改为 scp 路径 |
| 无文档间矛盾 | ☑ | 审查后交叉核对 |

### 1.2 IMPLEMENTATION.md ↔ 本 checklist 对齐

| 检查项 | 状态 | 说明 |
|--------|------|------|
| T1-T6 全部操作在本 checklist 有验收项 | ☑ | §3 验收映射表 |
| 本 checklist 验收项可追溯到 IMPL | ☑ | 每项标 IMPL 章节号 |

### 1.3 与 ADR-0001 的边界一致性

| 检查项 | 状态 | 说明 |
|--------|------|------|
| D4 范围未膨胀（未吃进 D3 的目录重构内容） | ☑ | /tmp/b5scripts、b6* 脚本明确留在 D3 |
| T6 是否越界（超出 ADR D4 清单） | ☐ | **用户裁决项**：T6 属审查新发现的顺手清理，与 ADR-0001 D4.1 范围形式上略超（ADR 未列 cron）。建议接受（风险低、与根因报告 L0 闭环），但需用户点头 |

### 1.4 术语一致性

| 术语 | RESEARCH | IMPL | 本 checklist | 一致 |
|------|----------|------|------------|------|
| key 残留数 | 4 处 | 4 文件 | 4 处 | ☑ |
| 僵尸 cron | §3.6 发现 1 | T6 | §0 H4 | ☑ |
| opencode 版本对 | 1.18.9→1.18.25 | 同 | 同 | ☑ |

## 2. 反幻觉审查验收（本次审查核心）

### 2.1 证据等级抽查（全部 E1 声明重放或留痕）

| # | 声明 | 复核方式 | 结果 |
|---|------|---------|------|
| 1 | key 残留 4 处（RESEARCH §3.1 表） | `grep -l 'sk-RPC-' /tmp/*` 两站（本会话两次执行） | ☑ 命中一致 |
| 2 | gptoss_spec_test2.sh 无内容变更 | `git diff gptoss_spec_test2.sh`（输出仅 LF/CRLF warning） | ☑ |
| 3 | B 站 cron 两条 bjork_deepfix | `crontab -l`（B 站） | ☑ 原文留档于 RESEARCH §3.6 |
| 4 | A 站 crontab 空 | `crontab -l`（A 站） | ☑ |
| 5 | `/tmp/bjork_deepfix/` 目录不存在 | `ls -la` 无输出 | ☑（僵尸判定的前提） |
| 6 | mihomo 仅 127.0.0.1:7890 | `ss -tlnp`（A 站） | ☑（H2 修正依据） |
| 7 | LM Studio :1234 = 000 | `curl` 超时 | ☑（cron 走失败分支佐证） |
| 8 | nemotron llama-server active | `systemctl is-active` + pgrep | ☑（T4 冒烟前提成立） |
| 9 | bak3 最新（时间戳） | `ls --time-style=full-iso`：15:55<17:00<17:39 | ☑（H 候选疑虑消除） |
| 10 | opencode 自带 upgrade | `--help` 输出 | ☑ |

### 2.2 幻觉修正落实验收

| # | 修正项 | 修正位置 | 验收 |
|---|--------|---------|------|
| H1 | 删除虚构"E1 crontab 已核"，换为实测双向核 | IMPL §6 风险表第 3 行 | ☑ |
| H2 | mihomo 备选改 scp 路径 | IMPL T4 实施要点 + RESEARCH §4.2 | ☑ |
| H3 | gptoss 核对门关闭（CRLF 实测） | RESEARCH §3.2 + IMPL T1 顺序图 | ☑ |
| H4 | F4 勘误 + 影响评估（主结论不动摇） | RESEARCH §3.6 发现 1 | ☑ |
| — | bak3 ⊇ bak2 疑虑消除（50 字节空配置） | IMPL T5 实施要点补核 | ☑ |

### 2.3 残余不确定性声明（诚实清单）

| 项 | 不确定性 | 处置 |
|----|---------|------|
| A 站挂死当时 B 站 cron 是否存在 | 不可回溯（无历史 crontab 快照） | RESEARCH §3.6 已如实标注"无法回溯" |
| opencode 升级后配置解耦 | E4 机制推断（未实际升级验证） | T4 冒烟 + T5 bak 保留兜底 |
| opencode 1.18.25 为最新版 | E3（subagent 检索，未亲测） | 升级目标若 404 则以 `opencode upgrade` 实际可用最新版为准 |
| B 站直连 opencode 官方 CDN | 未测 | T4 实施时验证，备选路径已备 |

## 3. 实施验收映射（T1-T6 执行时逐项打勾）

| 操作 | 验收项（IMPL §5 编号） | 验收命令 | 通过 |
|------|----------------------|---------|------|
| T1 | #1 工作区干净（提交后）+ #7 远端同步 | `git status --porcelain` / `git log origin/main -1` | ☐ |
| T2 | #2 /tmp 无 key | 两站 `grep -rl 'sk-RPC-' /tmp/` | ☐ |
| T3 | #3 txt 已删 | `Test-Path d:\RPC\新建文本文档.txt` | ☐ |
| T5 | #6 bak 收敛 ≤1/站 | `ls ~/.config/opencode/*.bak*` | ☐ |
| T6 | #9 前置断言 → #8 crontab 清空 | `crontab -l`（清理前后各一次） | ☐ |
| T4 | #4 版本 1.18.25 + #5 PONG 冒烟 | `--version` / `opencode run ... 'reply PONG'` | ☐ |

## 4. 验收通过标准

1. §3 全部 ☑（9 项验收全过）
2. §2.2 修正已 push（本轮 commit 含修订后两文档 + 本 checklist）
3. IMPL 状态 draft → verified；ADR-0001 D4 标注已完成
4. 若 T4 冒烟失败且 10 分钟内无法恢复 → 触发 IMPL T4 回滚路径，D4 以"T1-T3/T5/T6 完成、T4 降级"部分交付收档，遗留项记入 ADR-0001 §中性/需要后续行动

## 5. 审查签章

| 角色 | 结论 | 时间 |
|------|------|------|
| 反幻觉审查（Trae） | 4 处修正已落实，残余不确定性已声明，通过 | 2026-09-01 晚 |
| 用户终审 | ☐ 待签 | — |

## 修订历史

| 日期 | 变更 |
|------|------|
| 2026-09-01 | v1.1：第 1 轮反幻觉审查（H1-H4 修正 + T6 新增 + 9 项验收） |
