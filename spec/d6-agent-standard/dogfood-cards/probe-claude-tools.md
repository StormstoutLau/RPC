---
proj: dogfood
task: 工具面探针：如实报告你被允许使用的工具，并用其中一个工具真的创建一个文件作为自证
model: claude
cli: claude
sensitivity: public
readonly: false
timeout_s: 300
accept:
  - test -f out/probe-tools.md
  - grep -q '^PROBE_DONE' out/probe-tools.md
---
## 任务描述

**这是一次「工具面」探针**（目的是判定本执行器**是否具备工具调用能力**，不是内容任务）。

请**依次**做三件事，并把结果写进当前工作目录下的 `out/probe-tools.md`：

1. **自证工具可用**：用你的 **shell / 命令执行**工具真的运行一次命令，打印一行固定文本（建议 `echo PROBE_BASH_OK`）。
   ★ **这一步必须真的执行**，不要用文字声明代替。
2. 用你的**读文件**工具读一次当前的任务提示文件 `out/.prompt.txt`（若该文件不存在，则在产物里注明）。
3. 把下列事实**逐行**写进 `out/probe-tools.md`（**第一行必须是 `PROBE_DONE`**）：

```
PROBE_DONE
BASH_USED=1_or_0
BASH_EVIDENCE=<你执行命令得到的原文输出>
READ_USED=1_or_0
TOOLS_DECLARED=<你被允许使用的工具名，逗号分隔；若一个都没有写 NONE>
SELF_REPORT=<一句话：你能创建文件吗>
```

### 硬性要求

- ★ **不许臆造**：`BASH_EVIDENCE` 必须是你**真的跑出来**的输出；`BASH_USED` / `READ_USED` 必须如实。
- ★ **若你没有任何工具可调用**（连写文件也不行）⇒ **不要假装写出任何文件**，改为在 stdout **只输出一行**：
  `PROBE_NO_TOOLS`
- **不要**读除上述提示文件之外的任何文件；**不要**探索仓库；**不要**产生 `out/probe-tools.md` 之外的任何文件。
- 产物尽量短（≤ 20 行）。