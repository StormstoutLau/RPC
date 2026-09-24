---
proj: dogfood
task: 在 out/ 下**只写一个**文本文件（文件名由你自定，但必须以 .txt 结尾），内容单行 GLOB_PROBE_OK；stdout 只输出一行 DOGFOOD_GLOB_OK
model: ultra
cli: opencode
sensitivity: public
readonly: false
timeout_s: 300
accept:
  - test -f out/glob-probe.txt
  - grep -q GLOB_PROBE_OK out/glob-probe.txt
evidence-manifest:
  version: 1
  subjects:
    - name: glob-probe
      path: glob-probe.txt
      state: out/*.txt
      digest: sha256
---
> **本卡 = O-52「采集面 glob」的端到端复跑夹具**（用途 = 证明 `state` 用通配时，产物能按 `path` 落进 runDir）。
> ⚠ 与其它卡的**唯一区别**：产物名**不写死**（由 agent 自定）⇒ 只有 glob 才收得回。
> 判读：日志须出现 `EVM_STATE_GLOB: … out/*.txt -> out/<实名>.txt` + `EVM_STATE: pulled=1`，
> 且 runDir 内出现 `glob-probe.txt`（内容 `GLOB_PROBE_OK`）。

## 任务描述

**这是一次采集路径的烟测**（目的是验证"产物名事先不可知时能否收件"）。
请**只做两件事**：

1. 在当前工作目录下创建 `out/`（若不存在），并在其中写**恰好一个**文本文件：
   - **文件名由你自己定**（例：`note-1.txt`、`probe.txt`…），**但必须以 `.txt` 结尾**；
   - 内容**只有一行**：

```
GLOB_PROBE_OK
```

2. 在 stdout **只输出一行**：`DOGFOOD_GLOB_OK`

### 硬性要求

- **不要**读任何其它文件，**不要**探索仓库，**不要**解释你在做什么。
- ★ **只在 `out/` 下写这一个 `.txt` 文件**（**多个会被采集端拒绝** —— 采集要求通配**恰好匹配 1 个**）；
  临时文件也不要留在 `out/`。
