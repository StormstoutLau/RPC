# 调研文档：D4 收尾清理（Agent 生态升级前置）

---
id: d4-closeout-RESEARCH
type: design
version: 1.0
status: draft
date: 2026-09-01
depends: []
upstream: null
---

> **Feature**: D4 收尾清理
> **创建日期**: 2026-09-01
> **状态**: draft
> **Spec 步骤**: Step 1-2
> **决策来源**: [ADR-0001](../../adr/ADR-0001-集群运维框架审计与四项改进决策.md) §决策 1

---

## 1. 调研目标

**核心问题**:
1. ADR-0001 D4 列出的收尾项，逐项的**精确现状**是什么？（残留文件、未提交内容、可合并内容）
2. 每项清理的**风险与回滚路径**是什么？（删错/提交错/升级失败怎么恢复）
3. B 站 opencode 1.18.9→1.18.25 升级的**机制与前置条件**是什么？

## 2. 调研方法

### 2.1 使用的工具

| 工具 | 用途 | 查询 |
|------|------|------|
| RunCommand (SSH) | 两站残留取证 | `grep -l 'sk-RPC-' /tmp/*`、`ls`、`file`、`--help` |
| RunCommand (git) | 未提交修改核对 | `git status --porcelain`、`git diff --stat` |
| Read | 文档内容核对 | 新建文本文档.txt、手册 §1.2 |

### 2.2 调研范围

- 两站 `/tmp`、`~/.config/opencode/`、`~/.opencode/`
- 主控站 d:\RPC git 工作区
- 排除：`/tmp` 中不含 key 的历史脚本（b6* 等约 15+ 个，属 D3 目录重构范畴，不在 D4 动）

## 3. 调研发现

### 3.1 key 残留全景（比 ADR-0001 多发现 1 处）

| # | 文件 | 站 | 内容 | 证据 |
|---|------|----|------|------|
| 1 | `/tmp/cca.sh` | B | `ANTHROPIC_AUTH_TOKEN=sk-RPC-...` 明文（第 3 行） | E1 `head -3` |
| 2 | `/tmp/e2e.sh` | B | `KEY="sk-RPC-..."` 明文（第 2 行） | E1 `grep -n` |
| 3 | `/tmp/litellm_config_20260901.yaml` | B | **新发现**——LiteLLM 配置临时副本，含 master_key | E1 `grep -l` |
| 4 | `/tmp/aoc.jsonc` | A | opencode 配置副本，apiKey 明文 | E1 `grep -l` |

> 注：探测脚本 `/tmp/d4probe.sh` 自身因含 grep 模式串被误匹配，非真实残留，处理时一并删除即可。

**风险评估**: 全部在局域网两站的 `/tmp`，无公网暴露面；但 `/tmp` 全局可读（其他本地用户/进程可扫），且违背"key 只在主控站 secrets/ 存放"的自定规范。清理优先级：中（内网 + 单用户机器，实际泄露概率低，但属卫生债）。

### 3.2 未提交 git 修改（3 个文件）

| 文件 | diff 内容 | 处置判断 |
|------|----------|---------|
| Agent生态升级与多智能体协作架构调研.md | 237 行变更——**附录 A-D 归档的后续格式重排**（上次 commit `7e00e31` 后外部工具触碰） | 内容已 commit 过，纯格式，直接提交 |
| 双机推理集群使用手册.md | 28 行变更——表格对齐重排（同上） | 同上 |
| gptoss_spec_test2.sh | 未核对内容 | **实施前先 `git diff` 核对**，确认无害再提交 |

### 3.3 新建文本文档.txt 内容核对

```
LiteLLM：http://scott-lau-GTR-Pro.local:4000 （带 Bearer key）
Beszel：http://scott-lau-GTR-Pro.local:8090
Cockpit：https://scott-lau-GTR-Pro.local:9095 / https://scott-lau-NEX.local:9095
```

三条 URL 与手册 §1.2 端口清单**逐条重复**（E1 比对），信息零增量 → 可直接删除，无需先合并（合并已完成于手册）。

### 3.4 B 站 opencode 升级机制

| 事实 | 证据 |
|------|------|
| 安装形态：自包含 ELF 二进制（179MB，`~/.opencode/bin/opencode`），非 npm/snap 包 | E1 `file` + `ls -la` |
| 版本：1.18.9（2026-07-29 构建） | E1 `--version` |
| **自带升级子命令**: `opencode upgrade [target]`，支持指定版本回滚 | E1 `--help` |
| 配置与版本解耦：`~/.config/opencode/opencode.jsonc` 升级不动 | 机制推断（E4，低风险） |
| 现有备份：`opencode.jsonc.bak/bak2/bak3` ×3 已散落 | E1 `ls`（顺带清理项） |

**升级风险**: 二进制替换失败（下载中断/磁盘满）→ 回滚 = 重跑 `opencode upgrade 1.18.9` 指定旧版本；cluster-litellm provider 配置不受影响。风险低。

**升级收益**（E3，来自生态调研附录 A）：v1.18.20 子代理失败可恢复、v1.18.2 agent 深度限制——均为子代理协作刚需，与 Agent 生态升级 P0 合并执行。

### 3.5 A 站现状（对照）

- opencode 已是 1.18.25（最新），无需动
- 残留仅 `/tmp/aoc.jsonc` + `/tmp/fixa.sh` + `/tmp/b5scripts/`（框架副本，D3 处理）；无 key 的 fixa.sh 可顺带删

## 4. 综合分析

### 4.1 关键发现总结

1. key 残留实为 **4 处**（ADR 记 3 处，调研新发现 `/tmp/litellm_config_20260901.yaml`）[置信度: ★★★★★ E1]
2. 全部残留可安全删除——四文件均为临时脚本/配置副本，原始信息分别存在于主控站 `secrets/`、B 站 `/home/scott-lau/litellm/config.yaml`（生产配置）、两站 opencode 生产配置 [置信度: ★★★★★ E1]
3. 3 个未提交修改中 2 个为纯格式重排（内容已在历史 commit），1 个需人工核对 [置信度: ★★★★☆]
4. txt 内容与手册零信息差，可直接删 [置信度: ★★★★★ E1]
5. opencode 升级为自带子命令的原子操作，带回滚路径 [置信度: ★★★★★ E1]

### 4.2 技术 landscape

不适用（纯运维收尾，无外部技术选型）。唯一外部依赖是 opencode 升级源（官方 CDN，网络已验证可达——B 站曾用 mihomo 代理，opencode upgrade 走 HTTPS，内网直连或经 A 站代理均可，实施时验证）。

### 4.3 对实施文档的输入

- 清理清单从 3 项扩为 4 项（+litellm_config yaml）
- 升级操作定型为 `opencode upgrade`（非手动下载替换）
- 提交操作前增加 gptoss_spec_test2.sh 人工核对门
