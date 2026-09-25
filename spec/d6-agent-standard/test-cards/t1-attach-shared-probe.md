---
proj: dogfood
task: 列出工作区 .attach/ 下的全部文件名（不含子目录），只输出一行 T1_ATTACH_LIST: <逗号连接>；不修改任何文件
model: ultra
cli: opencode
sensitivity: public
attach-egress: ok
input-provenance: none
readonly: true
timeout_s: 300
---
## 任务描述

工作区 `.attach/`（由 `--attach` 注入）下有 **0..n 个文件**。

请只做两件事：

1. 用 `ls -1 .attach/` 列出其中**全部文件**名，按**字典序**排列；
2. **只输出一行**：`T1_ATTACH_LIST: ` 后接用**逗号**连接的文件名（若一个都没有，输出 `T1_ATTACH_LIST: (none)`）。

不要读取或输出文件**内容**，不要创建/修改/删除任何文件。

---

> **本卡用途（O-59 / T1 的探针，2026-09-25）**
> `readonly: true` ⇒ 远端 `flock -s`（**共享锁**）；`attach-egress: ok` ⇒ 允许带附件出网。
> 这两条凑在一起，才构成 O-59 危险序①（**共享锁下两 run 互删 `.attach/`**）的可达形态 ——
> 全仓现有带附件的卡要么是 `readonly:false`（本就 exclusive）、要么未声明 `attach-egress`（被闸拒）。
> **判据**：同站同 proj 并发两 run（各带**不同名**附件）⇒ 任一方输出里出现**对方**的文件名即证据成立。
