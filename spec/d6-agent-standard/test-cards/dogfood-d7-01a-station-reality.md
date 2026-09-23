---
proj: dogfood
task: 采集本站推理集群运行时实况（加载中的模型 / 显存 / 内存 / 工作区 / 监听端口），写入 out/station-reality.json；只写这一个新文件，不修改任何既有文件
model: ultra
cli: opencode
sensitivity: public
readonly: true
timeout_s: 600
accept:
  - cd /home/scott-lau/agent-workspaces/dogfood && test -f out/station-reality.json
  - cd /home/scott-lau/agent-workspaces/dogfood && grep -q '"station"' out/station-reality.json
  - cd /home/scott-lau/agent-workspaces/dogfood && grep -qE '"loaded_models"' out/station-reality.json
  - cd /home/scott-lau/agent-workspaces/dogfood && grep -q '"as_of"' out/station-reality.json
---
## 任务描述

你是**只做采集**的取证 agent。**不要分析、不要建议、不要总结原因** —— 你的唯一产物是一个 JSON 文件。

### 唯一产物：`out/station-reality.json`

在当前工作区根下创建 `out/station-reality.json`（若 `out/` 不存在则先创建）。**不要修改任何其它文件。**

JSON 必须是**单个对象**，至少含以下键（键名逐字一致）：

| 键 | 类型 | 怎么取 |
|---|---|---|
| `station` | string | **本站标识**。可用 `hostname`，或从 `/etc/hostname` 读；**原样写机器名**，不要猜 A/B/C |
| `as_of` | string | 采集时刻，格式 `YYYY-MM-DDTHH:MM:SS%z`（如 `2026-09-23T14:05:11+0800`），用 `date +%Y-%m-%dT%H:%M:%S%z` |
| `loaded_models` | array | **本站当前实际加载/可服务的模型**。**优先用站上工具 `infer-list`**（若在 PATH 中）；取不到再退回：`ps -eo pid,comm,args \| grep -E 'llama-server\|ggml-rpc-server'` 解析 `-m` / `--model` 参数给出模型路径或别名。**每条必须是对象**，含 `alias`（或 `path`）与 `source`（取值 `infer-list` 或 `ps`） |
| `gpu` | object | `nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader` 的**原文行**放到 `raw` 键；若能解析则另给 `mem_total_mb` / `mem_used_mb`（数字）。取不到就写 `{"raw": null}` |
| `mem` | object | 从 `/proc/meminfo` 取 `MemTotal` / `MemAvailable`，单位 MB，键名 `total_mb` / `avail_mb`（数字） |
| `listening_ports` | array | `ss -ltn` 的本地端口号（数字，去重升序）；取不到写 `[]` |
| `workspaces` | array | `ls -1 /home/scott-lau/agent-workspaces` 的目录名列表（字符串数组）；目录不存在写 `[]` |
| `probe_errors` | array | 上述**任何一条命令失败**时，把 `{"cmd": ..., "rc": N, "stderr_head": "..."}` 追加进来。**全部成功则为 `[]`** |

### 硬性要求

1. **不许编造**。取不到的值按上表写 `null` / `[]`，并把失败记进 `probe_errors`。**宁可空，不可假**。
2. **JSON 必须可被 `grep` 直接命中**：键名带双引号、无 BOM。
3. **命令最少化**：不要重复执行同一命令；总执行次数控制在 10 条以内。
4. **stdout 只输出一行**：`DOGFOOD_A1_OK`（后面不要有任何其它输出行）。
5. 除 `out/station-reality.json` 外**不产生任何文件**（临时文件也不留）。
