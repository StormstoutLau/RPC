---
proj: dogfood
task: 在当前目录的 out/ 下写恰好一个单行文本文件 out/v4-evidence.txt（内容 V4_EVIDENCE_OK）；stdout 只输出一行 V4_DISPATCH_OK
model: ultra
cli: opencode
sensitivity: public
input-provenance: "ops/rpc_check.py"
attach-egress: ok
readonly: false
timeout_s: 300
accept:
  - test -f out/v4-evidence.txt
  - grep -q V4_EVIDENCE_OK out/v4-evidence.txt
accept-golden:
  source: ops/station-bin/golden/smoke_dispatch_golden.sh
  cmd: bash .golden/smoke_dispatch_golden.sh
evidence-manifest:
  version: 1
  subjects:
    - name: v4-evidence
      path: v4-evidence.txt
      state: out/v4-evidence.txt
      digest: sha256
---
## 任务描述

**这是一次派发/回收链的烟测**（目的：验证"**带附件 + 带 golden** 的卡在证据件按 run 隔离后仍能被正确回收"）。
请**只做两件事**：

1. 在当前工作目录下创建 `out/`（若不存在），并在其中写**恰好一个**文本文件 `out/v4-evidence.txt`，
   内容**只有一行**：

```
V4_EVIDENCE_OK
```

2. 在 stdout **只输出一行**：`V4_DISPATCH_OK`

### 硬性要求

- **不要**读任何其它文件（随卡附件也不必读），**不要**探索仓库，**不要**解释你在做什么。
- `out/` 下**只留这一个文件**；临时文件不要留在 `out/`。

---

> **本卡用途（O-68② 的 V4 判据，2026-09-25）**
> 危险面 = **有附件 ∨ golden active** ⇒ 派发取**排他**租约；而 per-run 改名（D4–D6）改了
> `.attach-manifest` / `.golden-cmd` / `.accept-golden-output` 三个写点的**名字**。
> ⇒ 本卡是**唯一**同时压到"附件清单"与"golden 产物"两条路径的探针。
> 判读（全部要在一份日志里看见）：
> `ATTACH_STAGED=1` · `ATTACH_MANIFEST_LINES≥1` · `ACCEPT_OK=1` · **`ACCEPT_GOLDEN_OK=1`** ·
> `TASK_RC=0` · runDir 内出现 `accept-golden-output.txt`（内容含 `SMOKE_GOLDEN_OK`）。
