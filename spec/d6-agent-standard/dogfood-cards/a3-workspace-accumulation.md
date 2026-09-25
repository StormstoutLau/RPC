---
proj: dogfood
task: 采集工作区内各项目目录当前累积的文件现状（文件数 / 体积 / 年龄 / 顶层项），并如实记录哪些路径被沙箱拒绝，写入 out/workspace-accumulation.json；只写这一个新文件
model: ultra
cli: opencode
sensitivity: public
readonly: false
timeout_s: 900
accept:
  - test -f out/workspace-accumulation.json
  - grep -q '"station"' out/workspace-accumulation.json
  - grep -q '"as_of"' out/workspace-accumulation.json
  - grep -q '"projects"' out/workspace-accumulation.json
  - grep -q '"probe_errors"' out/workspace-accumulation.json
  - ( grep -q '"name"' out/workspace-accumulation.json || grep -q '"cmd"' out/workspace-accumulation.json )
evidence-manifest:
  version: 1
  subjects:
    - name: workspace-accumulation
      path: workspace-accumulation.json
      state: out/workspace-accumulation.json
      digest: sha256
---
## 任务描述

你是**只做采集**的取证 agent。**不要清理或删除任何文件、不要分析原因、不要给建议、不要总结** ——
你的唯一产物是**一个文件**。

> ⚠ **本卡有一个诚实的"双结果"设计，先读这段再动手**：
> 你所在沙箱的**可读边界并未完全确定** —— 已知**你自己的工作目录**可读；
> **其同级目录（工作区根下的其它项目目录）是否可读，未经验证**。
> ⇒ 某条路径被**权限拒绝**时：**把它如实记进 `probe_errors`，然后继续下一条**；
> **不要为了绕开拒绝而换命令反复重试同一条路径**（换写法重试 = 白烧轮次，且会让本轮结果不可比）。
> ⇒ **"全被拒"也是合格结果**：那时 `projects` 写 `[]`、`totals` 写 0、`probe_errors` 记明原因即可。
> **不要为了凑数据而编造任何一项。**

### 第一步（不要跳过）：先确认工作目录可写

```bash
mkdir -p out && echo ok > out/.write-test && cat out/.write-test
```

**若这一步失败**，立刻停止并在 stdout 打印 `DOGFOOD_A3_BLOCKED`（之后不要输出别的）——
不要"改用 stdout 输出数据"来替代文件。

### 唯一产物：`out/workspace-accumulation.json`（相对工作目录根）

JSON 必须是**单个对象**，键名**逐字一致**：

| 键 | 类型 | 怎么取（**按此顺序，取到即止；取不到写 `null` / `[]`，并记进 `probe_errors`**） |
|---|---|---|
| `station` | string | `hostname` 的输出，**原样写**，不要猜 A/B/C |
| `as_of` | string | `date +%Y-%m-%dT%H:%M:%S%z` |
| `projects` | array | **先列工作区根**（你当前工作目录的**上一级**）的直接子目录名（`ls -1 ..`）。⚠ **只写目录名，不要写任何绝对路径**。每个子目录一项，结构见下 |
| `totals` | object | `{"project_count":N,"file_count":N,"du_kb":N}`：`project_count` = `projects` 长度；`file_count` / `du_kb` = 各项之和（取不到的项按 0 计入，并在 `probe_errors` 里体现） |
| `probe_errors` | array | **任何一条命令非 0 退出**（含**权限拒绝**）⇒ 追加 `{"cmd":"<原样>","rc":N,"stderr_head":"<首行,截 200 字>"}`；全部成功 ⇒ `[]` |

`projects` 里**每一项**（对象）的键：

| 键 | 类型 | 怎么取 |
|---|---|---|
| `name` | string | 子目录名（**相对名，不是路径**） |
| `file_count` | number | 该目录下文件总数：`timeout -k 10 60 find <name> -type f 2>/dev/null \| wc -l` |
| `du_kb` | number \| null | `timeout -k 10 60 du -sk <name> 2>/dev/null \| cut -f1`（`du` 不可用或超时 ⇒ `null` + 记 `probe_errors`） |
| `age_days` | number \| null | 该目录自身 mtime 距今天数：`echo $(( ( $(date +%s) - $(stat -c %Y <name>) ) / 86400 ))`（取不到 ⇒ `null`） |
| `top_entries` | array | `ls -1A <name>` 的**前 20 项**，每项 `{"name":"...","type":"file\|dir"}`（`-A` 是**必须的**：本卡关心的 `.attach/` 这类**点开头**目录，若用 `ls -1` 会被漏掉 ⇒ 结果会失真；用 `ls -la` 首列首字符判类型，判不出写 `"?"`） |
| `top_entries_truncated` | boolean | `ls -1A <name>` 行数 > 20 ⇒ `true`，否则 `false` |

### 硬性要求

1. **必须真的写文件**。数据只放 JSON 里，**不要只在 stdout 打印**。写完用 `test -f out/workspace-accumulation.json && echo WROTE_OK` 自证。
2. **不许编造**。取不到 ⇒ `null` / `[]`，并记进 `probe_errors`。**宁可空，不可假**。
3. **产物里不要出现绝对路径**（不要 `pwd`、不要 `~/...` 展开后的结果）——只写**相对名**。
4. **不要读 `/proc/*`**（站上 agent 对 `/proc/*` 无读权限，实测会被 auto-reject，白费一轮）。
5. **任何可能耗时的命令都要限时**，且必须写成 `timeout -k 10 <秒> <命令>`：**裸 `timeout` 不算限时**
   （对忽略 SIGTERM 的子进程会**一直等**）。⚠ 加了 `-k` 后，"被杀"的退出码是 **137**（不是 124）
   ⇒ 判"超时"要认 **124 和 137** 两种。
6. 命令总数控制在 **30 条以内**；**同一路径失败后不要重试**（换写法重试也算重试）。
7. **stdout 最后只输出一行**：`DOGFOOD_A3_OK`（后面不要有别的输出行）。
8. 除 `out/workspace-accumulation.json` 与写入探针 `out/.write-test` 外**不产生任何文件**（临时文件也不留）。
