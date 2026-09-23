---
proj: dogfood
task: 通道烟测：在当前工作区写 out/smoke.txt，内容为单行 SMOKE_OK，并在 stdout 回显同一行
model: claude
cli: claude
sensitivity: public
readonly: false
timeout_s: 300
accept:
  - test -f out/smoke.txt
  - grep -q SMOKE_OK out/smoke.txt
---
## 任务描述

**这是一次通道烟测**（目的是验证 `claude` 执行器 + openrouter 后端这条链路，不是内容任务）。请**只做两件事**：

1. 在当前工作目录下创建 `out/smoke.txt`（目录不存在就先建），内容**只有一行**：

```
SMOKE_OK
```

2. 在 stdout **只输出一行**：`DOGFOOD_SMOKE_OK`

### 硬性要求

- **不要**读任何其它文件，**不要**探索仓库，**不要**解释你在做什么。
- **不要**产生 `out/smoke.txt` 之外的任何文件。
- 若无法写文件 ⇒ stdout 只输出 `SMOKE_BLOCKED`（不要用 stdout 冒充产物）。
