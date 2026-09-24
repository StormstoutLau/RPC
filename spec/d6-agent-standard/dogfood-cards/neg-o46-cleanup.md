---
proj: dogfood
task: 受控失败夹具：写入 out/o46-probe.txt（内容一行 HELLO_O46），并在 stdout 只输出 DOGFOOD_NEG_OK；只写这一个文件
model: ultra
cli: opencode
sensitivity: public
readonly: false
timeout_s: 300
accept:
  - test -f out/o46-probe.txt
  - grep -q 'MUST_NOT_MATCH_THIS' out/o46-probe.txt
evidence-manifest:
  version: 1
  subjects:
    - name: o46-probe
      path: o46-probe.txt
      state: out/o46-probe.txt
      digest: sha256
---
> ⚠ **本卡是"受控失败"夹具**（用途 = 验证 O-46 缓解②「失败 run 主动清理远端残留」），**不是内容任务**。
> 裁定与依据见 [DEV-LOG-014](../../../docs/DEV-LOG-014-decision-refinement.md) D4。

## 任务描述

**这是一张"受控失败"夹具卡**。请**只做两件事**：

1. 在当前工作目录下创建 `out/o46-probe.txt`（目录不存在就先建），内容**只有一行**：

```
HELLO_O46
```

2. 在 stdout **只输出一行**：`DOGFOOD_NEG_OK`

### 硬性要求

- **不要**读任何其它文件，**不要**探索仓库，**不要**解释你在做什么。
- **不要**产生 `out/o46-probe.txt` 之外的任何文件。
- ⚠ **故意设计**：本卡 `accept` 第 2 条 `grep 'MUST_NOT_MATCH_THIS'` 在一个只含 `HELLO_O46` 的文件上**必然失败**
  ⇒ **验收必红** ⇒ 用来触发「**agent 成功但 accept 判红**」这条路径（`FINAL_RC=9`）。

> **预期（用于验证 O-46 缓解②）**：`TASK_RC=9` ⇒ collect 归档成功 ⇒ **清理远端残留**：
> `out/.meta` · `out/.progress` · `out/o46-probe.txt` · `.agent-lock` · `.agent-state.json` **应全部消失**；
> 同时 runDir 内**应保留**已拉回的 `o46-probe.txt` 与 `.meta`（**拉取先于清理**）。
