---
proj: dogfood
task: 只回复一行 V5_SHARED_OK；不创建、不修改、不删除任何文件
model: ultra
cli: opencode
sensitivity: public
readonly: true
timeout_s: 300
---
## 任务描述

只做一件事：在 stdout **输出一行** `V5_SHARED_OK`。

### 硬性要求

- **不要**创建、修改或删除任何文件（本卡是**只读**卡）。
- **不要**读任何文件、**不要**探索目录、**不要**解释你在做什么。

---

> **本卡用途（O-68② 的 V5/V6 探针，2026-09-25）**
> 本卡 = **`readonly: true` ∧ 无附件 ∧ 无 golden** ⇒ 危险面为假 ⇒ 租约取**共享**。
> 只有这一形状才能造出"**同站同 proj 并存**"的对照（带附件或 golden 的卡一律排他 ⇒ 凑不出并存）。
> - **V5**：同站同 proj 并发两张本卡 ⇒ 两份 runDir 证据**各自完整**、`TASK_ID` 各等于**自己的** ts、
>   且**无** `META_STALE` / `EVIDENCE_STALE`（改名前这里会收到对方的 `.meta`）。
> - **V6**：三站 × 两通道（opencode + claude）共 6 并发 ⇒ **6/6 `exit=0`**、**无 `exit 3`**、6/6 租约 `shared`。
> ⚠ 卡里**刻意不写 `accept`**：站上 claude 通道在 `readonly` 下可能拒绝落文件（实测形态），
> 而本卡的判据是**框架证据件**是否各自完整，**不是**产物 ⇒ 不落文件也应 `exit=0`。
