# 实施记录：D3 目录重构

---
id: d3-restructure-IMPLEMENTATION
type: design
version: 1.0
status: verified
date: 2026-09-01
depends: []
upstream: null
---

> **Feature**: D3 仓库目录重构
> **创建日期**: 2026-09-01
> **状态**: verified（验收 5 项全过）
> **Spec 步骤**: Step 5-8（轻量执行记录——ADR-0001 §决策 2 已定型方案，无需独立 RESEARCH/DESIGN）
> **决策来源**: [ADR-0001](../../adr/ADR-0001-集群运维框架审计与四项改进决策.md) §决策 2（D3）

---

## 1. 执行结果

### 1.1 重构前后对照

| 位置 | 重构前 | 重构后 |
|---|---|---|
| 根目录 | 140 文件（19 md + 115 脚本 + 杂项） | 仅 4 项：LICENSE / .gitignore / 手册.bak（gitignore 内）/ llama.cpp tar（gitignore 内） |
| docs/ | — | 19 个 md（手册/调研×14/根因报告/SSH排查/DEV-LOG×3） |
| ops/ | — | 10 个活资产（llama-serve-instance/llama-server.service/rpc-server.service/rpc-nodes/nodes.env/netplan×2/usb4×3）+ lm-download/ 7 个 |
| archive/root-scripts/ | — | 98 个根目录一次性脚本 |
| archive/scripts-history/ | — | 110 个（a1-a4 基准×29 + a4/ 目录 23 + b5* 系列 58） |
| scripts/ | 127 个 | 已清空删除 |
| spec/ tests/ adr/ | 不动 | 不动 |

### 1.2 执行方式

全部 `git mv`（R 状态保历史可 blame）。分 6 批执行：docs 19 → ops 10 → 根目录脚本 98（按功能分 4 批）→ scripts 一次性脚本 110 → ops/lm-download 7 → 断链修复。

## 2. 断链修复记录

- 首轮扫描 57 处断链，分四类批量修复：
  1. docs/ 内 `spec/` 前缀 → `../spec/`（6 个文件）
  2. docs/ 内 `scripts/` 引用 → `../archive/scripts-history/` 或 `../ops/lm-download/`（lm_*/speedtest_* 归 ops）
  3. spec/operator-optimization/DESIGN.md `../../scripts/llama-server.service` → `../../ops/`
  4. spec/model-eval/questions/domain_matrix.md `./DESIGN.md` → `../DESIGN.md`（历史遗留顺手修复）
- 终验：全库 100+ md 文件扫描，真实断链 **0**（唯一剩余 `ADR-000X-...md` 为 DESIGN_TEMPLATE.md 中模板占位符，非真实链接）

## 3. 验收记录（2026-09-01 22:41）

| # | 验收项 | 结果 |
|---|--------|------|
| 1 | 根目录仅剩 LICENSE/.gitignore + gitignore 内文件 | ☑ |
| 2 | git 全程 R 状态（历史保留） | ☑ 224 个文件均为 rename |
| 3 | 断链终验 0（占位符除外） | ☑ |
| 4 | scripts/ 目录清空删除 | ☑ |
| 5 | spec/ adr/ tests/ 未动 | ☑ |

## 4. 遗留与注意

- PowerShell 5 脚本文件中文路径需 UTF-8 BOM（本轮 .ps1 无 BOM 触发 GBK 误读，改直接命令行解决——**老坑再次验证**）
- `双机推理集群使用手册.md.bak.20260901`、`llama.cpp-0.2.0.tar.gz`、`downloads/` 均在 .gitignore 内未入库，保留本地
- 手册位于 `docs/双机推理集群使用手册.md`——外部引用（如 B 站 shell 快捷方式）如有绝对路径引用需注意

## 修订历史

| 日期 | 变更 |
|------|------|
| 2026-09-01 | v1.0 执行完毕 + 验收通过 |
