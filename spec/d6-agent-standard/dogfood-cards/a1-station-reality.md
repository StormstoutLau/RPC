---
proj: dogfood
task: 采集本站推理集群运行时实况（加载中的模型 / 显存 / 内存 / 工作区 / 监听端口），写入 out/station-reality.json；只写这一个新文件，不修改任何既有文件
model: ultra
cli: opencode
sensitivity: public
readonly: false
timeout_s: 600
accept:
  - test -f out/station-reality.json
  - grep -q '"station"' out/station-reality.json
  - grep -q '"loaded_models"' out/station-reality.json
  - grep -q '"as_of"' out/station-reality.json
---
## 任务描述

你是**只做采集**的取证 agent。**不要分析、不要建议、不要总结原因** —— 你的唯一产物是**一个文件**。

### 第一步（不要跳过）：先确认工作目录可写

```bash
mkdir -p out && echo ok > out/.write-test && cat out/.write-test
```

**若这一步失败，立刻停止并在 stdout 打印 `DOGFOOD_A1_BLOCKED`**（之后不要输出别的）—— 不要"改用 stdout 输出数据"来替代文件。

### 唯一产物：`out/station-reality.json`（相对工作目录根）

JSON 必须是**单个对象**，键名**逐字一致**：

| 键 | 类型 | 怎么取（**按此顺序，取到即止**） |
|---|---|---|
| `station` | string | `hostname` 的输出，**原样写**，不要猜 A/B/C |
| `as_of` | string | `date +%Y-%m-%dT%H:%M:%S%z` |
| `loaded_models` | array | **优先 `infer-list`**（站上工具）：取其表格里 `CONF` 列为 `✓` 的行的 `ALIAS`（表示该站已配置/已加载）；**若 `infer-list` 不可用**，退回 `ps -eo pid,args \| grep -E 'llama-server\|ggml-rpc-server' \| grep -v grep` 并解析 `--model` / `-m`。**每条为对象**：`{"alias":"...","source":"infer-list"}` 或 `{"alias":"...","path":"...","source":"ps"}`；**都没有 ⇒ `[]`** |
| `gpu` | object | 依次尝试：`nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader` → `rocm-smi --showmeminfo vram` → `ls -1 /sys/class/drm`（**通用系统路径，可用**）。**把成功的命令名放 `via`，其原始输出首行放 `raw`**；三条都失败 ⇒ `{"via":null,"raw":null}` 并把失败记进 `probe_errors` |
| `mem` | object | **必须用 `free -m`**（⚠ **不要读 `/proc/*`** —— 站上 agent 对 `/proc/*` 无读权限，实测会被 auto-reject，白费一轮）。取 `Mem:` 行的 total / available（数字），键名 `total_mb` / `avail_mb` |
| `uptime` | string | `uptime -p`（读不到写 `null`） |
| `listening_ports` | array | `ss -ltn` 的**本地端口号**（数字，去重升序）。**只取端口，不要取地址** |
| `workspaces` | array | `ls -1 ~/agent-workspaces` 的目录名（字符串数组）；不存在写 `[]` |
| `probe_errors` | array | **任何一条命令失败** ⇒ 追加 `{"cmd":"...","rc":N,"stderr_head":"..."}`；全部成功 ⇒ `[]` |

### 硬性要求

1. **必须真的写文件**。数据只放 JSON 里，**不要只在 stdout 打印**。写完用 `test -f out/station-reality.json && echo WROTE_OK` 自证。
2. **不许编造**。取不到 ⇒ `null` / `[]`，并记进 `probe_errors`。**宁可空，不可假**。
3. **不要读 `/proc/*`**；**`nvidia-smi` / `rocm-smi` 都可能不在 PATH** ⇒ 必须走回退链，别停在第一条。
4. 命令总数控制在 **12 条以内**；不要重复执行同一命令。
5. **stdout 最后只输出一行**：`DOGFOOD_A1_OK`（后面不要有别的输出行）。
6. 除 `out/station-reality.json` 与写入探针 `out/.write-test` 外**不产生任何文件**（临时文件也不留）。
