---
proj: dogfood
task: 只回复一行 T1_GOLDEN_PROBE_OK；不创建、不修改任何文件
model: ultra
cli: opencode
sensitivity: public
readonly: true
timeout_s: 300
accept-golden:
  source: ops/station-bin/golden/smoke_dispatch_golden.sh
  cmd: bash .golden/smoke_dispatch_golden.sh
---
## 任务描述

只做一件事：**输出一行** `T1_GOLDEN_PROBE_OK`。

不要创建、修改或删除任何文件；不要执行其它命令。

---

> **本卡用途（O-59 / T1 的 golden 探针，2026-09-25）**
> `readonly: true` **且无附件**、但 `accept-golden` 激活 ⇒ 危险面判据应把锁降为 **exclusive**（#6），
> 而 golden 的"重置 + 解包"已随 T1 移进**锁内落盘段**（§27.11-B #5/#7）。
> 复用的 golden 脚本 `smoke_dispatch_golden.sh` 是**任务无关**的：它只断 `.golden/` 存在、自身被注入到
> `.golden/`、cwd 为工作区根 ⇒ 可直接验证"注入在锁内依然生效"（判据 V4）。
