# 实施文档：D4 收尾清理（Agent 生态升级前置）

---
id: d4-closeout-IMPLEMENTATION
type: design
version: 1.0
status: draft
date: 2026-09-01
depends: [d4-closeout-RESEARCH]
upstream: null
---

> **Feature**: D4 收尾清理
> **创建日期**: 2026-09-01
> **状态**: draft
> **Spec 步骤**: Step 5-6
> **基于调研**: [RESEARCH.md](./RESEARCH.md)
> **决策来源**: [ADR-0001](../../adr/ADR-0001-集群运维框架审计与四项改进决策.md) §决策 1（D4）

---

## 1. 实施概述

五个原子操作：①核对并提交 3 个未提交文件；②删除两站 4+2 处 /tmp key 残留与临时脚本；③删除 `新建文本文档.txt`（内容已并入手册 §1.2）；④B 站 opencode 升级 1.18.9→1.18.25 并验证；⑤清理两站 opencode 配置备份散落文件（保留最新 1 份）。全部操作可独立执行、可独立回滚，总时长 ~30min。完成后 D4 关闭，进入 D3 目录重构。

## 2. 工程细节

### 2.1 技术栈

| 组件 | 技术 | 版本 | 验证状态 |
|------|------|------|---------|
| 远程操作 | SSH (主控站 OpenSSH client) | - | ✅ 免密已通 |
| git | 主控站 d:\RPC 仓库 | main @ cd8f50d | ✅ |
| opencode | B 站自包含二进制 | 1.18.9 → 1.18.25 | ⚠️ 升级源连通性实施时验证 |

### 2.2 依赖版本验证

无新依赖引入。opencode upgrade 由官方二进制自更新，无 PyPI/npm 依赖。

### 2.3 文件结构

不新增文件。变更仅限：删除 6 个 /tmp 临时文件、1 个 txt、2-3 个 .bak、提交 3 个既有修改。

## 3. 模块实施

### 3.1 操作 T1：git 收尾提交

#### 职责

把工作区 3 个未提交修改落库，工作区归零。

#### 接口签名（命令）

```powershell
# 1. 人工核对门: gptoss_spec_test2.sh 的 diff 必须先看内容再决定
git diff gptoss_spec_test2.sh | Select-Object -First 60
# 2. 无害则一并提交 (格式重排 2 个 + 该脚本)
git add "Agent生态升级与多智能体协作架构调研.md" "双机推理集群使用手册.md" gptoss_spec_test2.sh
git commit -m "chore(d4): 格式重排落库 + gptoss_spec_test2 内容核对后提交"
git push
```

#### 实施要点

- **核对门不可跳过**：gptoss_spec_test2.sh 若含 key 或测试残骸 → 改为不提交，先脱敏
- 提交前 `git log --oneline -1` 确认基线 = cd8f50d
- 失败回滚：`git reset HEAD~1`（未 push 前）/ 无需回滚（纯格式提交）

### 3.2 操作 T2：/tmp key 残留清理（4 处）

#### 职责

消除两站 /tmp 的明文 key 残留，恢复"key 只在主控站 secrets/ 与 B 站生产 config.yaml"的存储规范。

#### 接口签名（命令）

```bash
# B 站 (一次清理 4 个: cca.sh / e2e.sh / litellm_config_20260901.yaml / d4probe.sh)
ssh scott-lau@scott-lau-GTR-Pro.local "rm -v /tmp/cca.sh /tmp/e2e.sh /tmp/litellm_config_20260901.yaml /tmp/d4probe.sh"

# A 站 (aoc.jsonc 含 key; fixa.sh 不含但同批临时物)
ssh scott-lau@scott-lau-NEX.local "rm -v /tmp/aoc.jsonc /tmp/fixa.sh"

# 验证 (两站各跑, 预期无输出 = 干净)
grep -rl 'sk-RPC-' /tmp/ 2>/dev/null
```

#### 实施要点

- 删除前逐文件 `ls -la` 确认存在性（RESEARCH §3.1 已核对内容，无需重读）
- **不删** `/tmp/b5scripts/`（框架副本，D3 归档处理）
- **不删** B 站其他 b6* 历史脚本（不含 key，D3 范畴）
- 回滚：无需（四文件均为一次性副本，原始信息在 secrets/ 与生产 config）

### 3.3 操作 T3：新建文本文档.txt 删除

#### 职责

清除零信息量的临时笔记（内容与手册 §1.2 逐条重复，RESEARCH §3.3 已核对）。

#### 接口签名（命令）

```powershell
git rm "新建文本文档.txt"; git commit -m "chore(d4): 删除临时端点笔记 (内容已并入手册 §1.2)"
```

#### 实施要点

- 前置断言：`Select-String "LiteLLM" 双机推理集群使用手册.md` 命中（手册已含该信息）
- git rm 保留历史（需要时可从历史找回）

### 3.4 操作 T4：B 站 opencode 升级

#### 职责

补齐子代理协作刚需特性（v1.18.20 子代理失败可恢复 / v1.18.2 agent 深度限制），与 Agent 生态升级 P0 对齐版本。

#### 接口签名（命令）

```bash
# 1. 升级 (自带子命令, 原子替换)
ssh scott-lau@scott-lau-GTR-Pro.local "~/.opencode/bin/opencode upgrade"
# 2. 验证
ssh scott-lau@scott-lau-GTR-Pro.local "~/.opencode/bin/opencode --version"   # 预期 1.18.25
# 3. 冒烟: provider 配置不受影响
ssh scott-lau@scott-lau-GTR-Pro.local "cd /tmp && timeout 120 ~/.opencode/bin/opencode run -m cluster-litellm/nemotron 'reply PONG' 2>&1 | tail -2"
```

#### 实施要点

- 升级前记录当前二进制 md5（回滚锚点）：`md5sum ~/.opencode/bin/opencode > /tmp/oc_bin.md5.bak`
- **回滚路径**：`opencode upgrade 1.18.9`（官方支持指定版本降级）
- 冒烟失败（provider 不识别等）：先 `opencode doctor` 自检，再查 `~/.config/opencode/` 是否被迁移工具改动；配置备份见 T5 保留策略
- 网络备选（**审查修正**：A 站 mihomo 仅监听 127.0.0.1，B 站不能直接引用）：B 站直连失败时，在 A 站本机经 mihomo 代理下载新版本二进制 → `scp` 传 B 站 → 覆盖 `~/.opencode/bin/opencode`（保留旧二进制为 `.old` 先备份）

#### 低效操作排除

- 不重装（npm/安装脚本全量重装）——179MB 二进制自升级即原子替换，重装引入依赖链风险

### 3.5 操作 T5：opencode 配置备份收敛

#### 职责

消除 `.bak` 散落（B 站 3 个 + A 站 1 个），保留语义清晰的最近一份。

#### 接口签名（命令）

```bash
# B 站: 保留 bak3 (最新), 删 bak/bak2
ssh scott-lau@scott-lau-GTR-Pro.local "rm -v ~/.config/opencode/opencode.jsonc.bak ~/.config/opencode/opencode.jsonc.bak2"
# A 站: bak-0910 为当日唯一备份, 保留
```

#### 实施要点

- 删除前 `diff bak3 bak2` 确认 bak3 ⊇ bak2 信息（若 bak3 更旧则保留实际最新者）。**审查补核**：时间戳实测 bak(15:55) < bak2(17:00) < bak3(17:39)，bak3 最新 ✓；且三个 bak 均 50 字节（近乎空配置），删除 bak/bak2 零风险
- 生产配置 `opencode.jsonc` 本身在 git 外（两站本地文件），T4 升级失败时的恢复依赖保留下来的这份 bak

### 3.6 操作 T6：B 站僵尸 cron 清理（审查新增）

#### 职责

移除 B 站 crontab 中两条引用已不存在目录 `/tmp/bjork_deepfix/` 的僵尸条目，消除"未来目录重建后被意外激活"的隐患（条目内容与 A 站挂死根因同构，见 RESEARCH §3.6 发现 1）。

#### 接口签名（命令）

```bash
# 1. 备份现 crontab (空 crontab 也能恢复)
ssh scott-lau@scott-lau-GTR-Pro.local "crontab -l > ~/crontab.bak-20260901"
# 2. 清空 (B 站仅这两条, 全清 = 精准清理)
ssh scott-lau@scott-lau-GTR-Pro.local "crontab -r"
# 3. 验证
ssh scott-lau@scott-lau-GTR-Pro.local "crontab -l"   # 预期: no crontab for ...
```

#### 实施要点

- **前置断言**：执行前 `crontab -l` 确认仍只有那两条 bjork_deepfix 条目（若有新增条目，改为逐条移除而非全清）
- 与根因报告 L0（A 站侧已清）形成双站闭环
- 回滚：`crontab ~/crontab.bak-20260901`

## 4. 实施顺序与检查点

```
T1 (git 提交; 核对门已关闭—纯 CRLF)
  └─> T2 (/tmp key 清理 ×4+2)  ── 验证: grep 无命中
        └─> T3 (txt 删除)      ── 验证: 手册含端点信息
              └─> T5 (bak 收敛) ── 验证: 每站 ≤1 个 bak
                    └─> T6 (B 站僵尸 cron) ── 验证: crontab -l 空
                          └─> T4 (opencode 升级+冒烟) ── 验证: 1.18.25 + PONG
                                └─> 最终: git status 干净 + commit + push
```

T4 放最后：升级是唯一有失败风险的操作，放收尾处不阻塞前序清理。

## 5. 验收标准

| # | 验收项 | 命令 | 预期 |
|---|--------|------|------|
| 1 | 工作区干净 | `git status --porcelain` | 空 |
| 2 | /tmp 无 key | 两站 `grep -rl 'sk-RPC-' /tmp/` | 无输出 |
| 3 | txt 已删 | `Test-Path d:\RPC\新建文本文档.txt` | False |
| 4 | B 站版本 | `opencode --version` | 1.18.25 |
| 5 | 升级后可用 | `opencode run -m cluster-litellm/nemotron 'reply PONG'` | PONG |
| 6 | bak 收敛 | `ls ~/.config/opencode/*.bak*` (两站) | 每站 ≤1 |
| 7 | 远端同步 | `git log origin/main -1` | 含 D4 commit |
| 8 | B 站 crontab 清空 | `ssh B站 "crontab -l"` | no crontab（且 ~/crontab.bak-20260901 存在） |
| 9 | T6 前置断言通过 | 清理前 `crontab -l` | 仅两条 bjork_deepfix 条目（若非，改逐条移除） |

## 6. 风险与回滚汇总

| 风险 | 概率 | 影响 | 回滚 |
|------|------|------|------|
| ~~gptoss_spec_test2.sh 含敏感内容被误提交~~ | ~~低~~ | — | **审查后消除**：实测纯 CRLF 差异无内容变更 |
| opencode 升级后 provider 配置不识别 | 低 | 低（冒烟即暴露） | `opencode upgrade 1.18.9` 降级 + bak 恢复 |
| 删除的 /tmp 文件实际仍被引用 | 极低 | 低 | 待删清单（cca.sh/e2e.sh/litellm yaml/aoc.jsonc/fixa.sh/d4probe.sh）经 `grep -rl /tmp/ /etc/systemd/system/` 与 crontab 双向核（B 站 systemd 无引用 E1；A 站 crontab 空 E1） |
| 升级出网失败 | 中 | 低 | A 站本机下载 → scp → 覆盖（审查修正后的正确路径） |
| crontab -r 误删未来新增条目 | 极低 | 中 | 前置断言（验收 #9）+ `~/crontab.bak-20260901` 恢复 |

## 7. 交付物

- 干净的 git 工作区 + push 记录
- 本 IMPLEMENTATION.md 状态更新为 verified（验收 7 项全过）
- ADR-0001 §决策 1 (D4) 状态标注：已完成
