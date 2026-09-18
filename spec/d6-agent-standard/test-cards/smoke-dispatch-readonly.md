---
proj: paper
task: readonly 冒烟夹具（ADR-0007 缺口 4）—— 只回复指定 token，不改任何文件
model: gpt-oss-20b
cli: opencode
sensitivity: local-only
readonly: true
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
    - name: workspace-diff
      collect: "find . -newer .run-marker -type f -printf '%P\\n'"
      digest: sha256
---
## 任务描述

这是 **readonly** 卡的诊断夹具（[ADR-0007](../../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md) 缺口 4）。

请只回复以下单个 token，不要输出其他任何内容，**不要修改或创建任何文件**：

`SMOKE-READONLY-OK`

---
> **用途**：`readonly: true` 的"未越界"此前**无载体**（缺口 4）。本卡的 `evidence-manifest`
> 声明了一个 **`collect` 型 subject**（`workspace-diff`），其命令把 agent 运行窗口内被改动的
> 文件以**工作区相对路径**列出。判据 `diff-scope` 据此断言：readonly 卡的改动**只允许落在 `out/`**。
>
> ⚠ **为什么是 `find -newer` 而不是 `git diff`**：实测远端工作区**不是 git 仓库**
> （`paper` 两站 `git=NO`）⇒ `git diff` 会**静默返回空** = 假的"未越界"。载体必须与 git 无关。
> ⚠ **为什么 allow-path 含 `out/`**：多张 readonly 卡的交付物**就写在 `out/` 里**
> （如 `dogfood-research-modulemap.md` 的 accept 判的就是 `out/.dogfood_module_map.md`）
> ⇒ naive 的 "readonly ⇒ 零改动" 会**误杀合法运行**。
>
> **跑法**（与 write 夹具相同，模型需先在 B 站加载）：
> ```powershell
> python ops\cluster.py load gpt-oss-20b
> powershell -ExecutionPolicy Bypass -File ops\station-bin\agent-cli.ps1 task paper `
>   -Card spec\d6-agent-standard\test-cards\smoke-dispatch-readonly.md
> python ops\cluster.py agent chain ; python ops\cluster.py agent verify
> python ops\cluster.py unload
> ```
