---
proj: dogfood
task: 模型采样烟测：在当前工作区写 out/smoke.txt（内容单行 SMOKE_OK），并在 stdout 只输出一行 DOGFOOD_SMOKE_OK；只写这一个文件
model: ultra
cli: opencode
sensitivity: public
readonly: false
timeout_s: 300
accept:
  - test -f out/smoke.txt
  - grep -q SMOKE_OK out/smoke.txt
evidence-manifest:
  version: 1
  subjects:
    - name: smoke
      path: smoke.txt
      state: out/smoke.txt
      digest: sha256
---
> **本卡 = 出网档「模型可用性采样」夹具**（用途 = 判断某个 `openrouter/*` 免费档能否完成**最小产物型任务**）。
> 与 [`smoke-claude-channel.md`](smoke-claude-channel.md) 的分工：那张测 **`cli: claude` 通道**；本张测 **`opencode` + 任意 `-Model`**。
> 用法：`task dogfood -Card <本卡> -Model <出网档别名>`（别名须在 `ROUTE_TABLE` 内）。

## 任务描述

**这是一次模型可用性烟测**（目的是验证"该模型能否在限定时间内产出合格文件"，**不是**内容任务）。
请**只做两件事**：

1. 在当前工作目录下创建 `out/smoke.txt`（目录不存在就先建），内容**只有一行**：

```
SMOKE_OK
```

2. 在 stdout **只输出一行**：`DOGFOOD_SMOKE_OK`

### 硬性要求

- **不要**读任何其它文件，**不要**探索仓库，**不要**解释你在做什么。
- **不要**产生 `out/smoke.txt` 之外的任何文件。
- 若无法写文件 ⇒ stdout 只输出 `SMOKE_BLOCKED`（**不要**用 stdout 冒充产物）。

> **判读口径**（主控侧）：
> `ACCEPT_OK=1` ⇒ ✅ 该档可用；`ACCEPT_OK=0` 且 `agent-output` 有内容 ⇒ ⚠ 产出不合格；
> `agent-output` 近零字节且 `RUN_S` 接近 `timeout_s` ⇒ ❌ **生成侧停滞**（O-47 形态）。
