# 任务书（无 front-matter 夹具 —— 复刻 Cpp_Hub `dispatch/TASK_*.md` 形态）

## 任务性质

**这是验证任务, 不是开发任务**: 不要读取或修改任何文件, 只回复一行。

## 执行步骤

请**只回复一行**: `TASKBOOK_NOFM_OK`。不要读取任何文件、不要执行任何命令。

## 备注（为什么留这张卡）

本卡**刻意不带 front-matter**, 用于验证 ADR-0007 前置项的处置: D6 路径遇到无 front-matter 卡应
**拒绝**（否则会静默退化为 `sensitivity=public` + `readonly=false` + **无 accept-golden**）,
只有显式传 `-Sensitivity` 才放行 —— 放行时 run.json 会记 `card.front_matter = false`。

**为什么这个"退化"要拦**: 2026-09-18 实测 —— 本卡首版要求 agent 执行命令并输出结果块, 而该 run
**既无 golden 也无 accept** ⇒ agent 跑偏（去读了一堆无关源文件）**照样 rc=0 通过**, **无人判**。
即: 无 front-matter 不只是"少几个字段", 而是**验收本身消失**。

它同时是"两种卡格式"里那一种（Cpp_Hub 手工任务书）的最小复刻:
`F:\Cpp_Hub\dispatch\TASK_*.md` 那批卡全部无 front-matter, 且**不**走本路径（走 bespoke dispatch 脚本）。
