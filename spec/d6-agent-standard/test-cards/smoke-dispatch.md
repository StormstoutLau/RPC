---
proj: paper
task: 冒烟夹具（ADR-0007 阶段 0.5）—— 只回复指定 token，不修改任何文件
model: gpt-oss-20b
cli: opencode
sensitivity: local-only
readonly: false
timeout_s: 300
accept:
  - true
accept-golden:
  source: ops/station-bin/golden/smoke_dispatch_golden.sh
  cmd: bash .golden/smoke_dispatch_golden.sh
evidence-manifest:
  version: 1
  subjects:
    - name: agent-output
      path: agent-output.txt
      digest: sha256
    - name: judgment-record
      path: judgment-record.txt
      digest: sha256
    - name: accept-output
      path: accept-output.txt
      digest: sha256
    - name: accept-golden-output
      path: accept-golden-output.txt
      digest: sha256
    - name: prompt
      path: prompt.txt
      digest: sha256
    - name: session-meta
      path: session-meta.txt
      digest: sha256
---
## 任务描述

这是用于**验证 `agent-cli.ps1` 改动**的最小端到端派发夹具（[ADR-0007](../../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md) 阶段 0.5）。

请只回复以下单个 token，不要输出其他任何内容，**不要修改或创建任何文件**：

`SMOKE-DISPATCH-OK`

---
> **用途**：凡改到派发/回收/裁决链的改动，先跑本卡确认整链未破 ——
> profile 解析 → prompt 构建 → sync → 远端执行 → accept 门 → golden 门 →
> 证据回收（6 件）→ run.json/台账落盘 → `agent chain`/`verify` 判定。
>
> **为什么入库而不放 `tmp/`**：ADR-0005 的等价夹具（`tmp/e2e-evidence-card.md`）因 `tmp/` 被
> `.gitignore` 而**已经丢失**（只剩黄金件残留在磁盘上）⇒ 夹具必须**入库**才可复跑。
>
> **跑法**（模型需先在 B 站加载）：
> ```powershell
> python ops\cluster.py load gpt-oss-20b
> powershell -ExecutionPolicy Bypass -File ops\station-bin\agent-cli.ps1 task paper `
>   -Card spec\d6-agent-standard\test-cards\smoke-dispatch.md
> python ops\cluster.py agent chain ; python ops\cluster.py agent verify
> python ops\cluster.py unload
> ```
