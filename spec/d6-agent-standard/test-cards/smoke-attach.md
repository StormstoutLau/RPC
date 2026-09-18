---
proj: paper
task: readonly 附件夹具（ADR-0007 缺口 5）—— 读取 .attach 附件并回显两个 marker，不改任何文件
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
    - name: attach-manifest
      path: attach-manifest.txt
      digest: sha256
    - name: workspace-diff
      collect: "find . -newer .run-marker -type f -printf '%P\\n'"
      digest: sha256
---
## 任务描述

`--attach` 已把附件放进工作区 `.attach/` 目录。请做两件事：

1. 用 `cat` 读取 `.attach/fileA.md` 与 `.attach/docs/inner.txt`；
2. 只回复两行——它们的**原始内容**（即两个 marker 各一行），不要任何解释。

**不要修改或创建任何文件。**

---
> **用途**（[ADR-0007](../../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md) 缺口 5）：这是附件身份的**阶段 0.5 夹具**。
> 派发时用 `-Attach` 传入 [`attach-test/`](../../../ops/station-bin/attach-test/) 的 `fileA.md` + `fileB.txt` + `docs/`（含子目录，
> 覆盖 file/dir 两种形态），据以验收：run.json 的 `attach[]` 是否带 **sha256**（并由**站上** `attach-manifest.txt`
> 的逐文件 `sha256sum` 与主控侧对**源文件**的独立哈希**交叉验证**）。
>
> **为什么本卡也声明 `attach-manifest`**：声明它 ⇒ 该 run 的 v2 件集把**附件清单原件**一并入链
> （未声明的卡则只由 run.json 里的摘要钉住 —— 见 ADR-0007 的"上限"声明）。
>
> **摘要规则（供独立复算；实现只在 `agent-cli.ps1` 的 `Get-Sha256Lines` 一处）**：
> ① 清单行 = 站上 `sha256sum` 的 `<hex>  <relpath>`；② 按**首段路径**分组（`docs/inner.txt` → 附件 `docs`）；
> ③ 组内每行规范为 `"<relpath>:<sha256>"`，**按相对路径排序**后 `join("\n")` + 尾随换行，取其 `sha256`
> （**空行集 ⇒ `sha256("")`**，即空目录附件的摘要）。
> ④ run.json 的 `attach[].files` 应等于该组行数；`attach[].src` 为**主控侧**源路径（供跨域比对）。
>
> **跑法**（模型需先在 B 站加载）：
> ⚠ `-Attach` 是数组参数：用 `powershell -File` 调用时**逗号不会被拆成数组**（实测 `-Attach a,b,c` 会被当成
> **单个字符串** ⇒ 三个附件全部 `attach missing (skip)`）⇒ 必须在**当前会话**里用 `&` + `@(...)` 调用：
> ```powershell
> python ops\cluster.py load gpt-oss-20b
> & .\ops\station-bin\agent-cli.ps1 task paper `
>     -Card spec\d6-agent-standard\test-cards\smoke-attach.md `
>     -Attach @('ops\station-bin\attach-test\fileA.md',
>               'ops\station-bin\attach-test\fileB.txt',
>               'ops\station-bin\attach-test\docs')
> python ops\cluster.py agent chain ; python ops\cluster.py agent verify
> python ops\cluster.py unload
> ```
