# O-21 specaudit 超时 / rc=1 修复闭环验证报告

- **验证对象**: opencode + 本地 llama-server 推理环境下，读码型 agent 任务报 `request (N tokens) exceeds the available context size (65536 tokens)`

- **修复动作**: 将 A 站 gpt-oss 服务端加载上下文由 `-c 65536` 抬升到 `-c 131072` 并重载引擎

- **验证日期**: 2026-09-06

- **验证结论**: 三层独立验证全部通过，O-21 判定为已闭环

***

## 1. 问题与现象

specaudit 读码卡在 A 站（gpt-oss）执行时：

| 观测     | 值                                                                          |
| ------ | -------------------------------------------------------------------------- |
| 外层强杀   | `timeout 900` 强杀仍在顺序读文件的 agent（900s → exit 6）                              |
| 重跑时长   | 497s 完成但 `exit 1`                                                          |
| 硬错误    | `request (78285 tokens) exceeds the available context size (65536 tokens)` |
| 配置修复无效 | 改 opencode `limit.context`/`context`/`limit.input`=120000 后，运行期仍按 65536 判定 |

该卡在 B 站（nemotron）900s 内可完成，两侧不对称指向上下文容量差异。

***

## 2. 根因演进（三重返证）

修复方向经过三次返证，逐步排除误判：

1. **初判（误）**：字段选错——只改 `limit.context` 无效，以为需 `context`+`limit.input`。
2. **复判（误）**：归因 opencode 1.18.25 对本地 passthrough 模型有 64k 硬默认，客户端配置无效。
3. **终判（实，决定性）**：报错文本 `request (N) exceeds the available context size (M)` **逐字出自 llama.cpp 服务端**（`srv send_error`，社区返证 [anomalyco/opencode#11286](https://github.com/anomalyco/opencode/issues/11286)）；且 `/v1/models` 只通告 `n_ctx_train`（训练上下文），**真实运行时上下文在** **`/props`**。

决定性证据（A 站实测）：

| 探针                     | 结果                                          | 含义           |
| ---------------------- | ------------------------------------------- | ------------ |
| `/v1/models`           | `n_ctx_train = 131072`                      | 训练上下文，误导性    |
| `/props`               | `default_generation_settings.n_ctx = 65536` | **真实运行时上下文** |
| `ps -ef`（llama-server） | `... -c 65536 ...`                          | 加载参数实锤       |

结论：**65536 是模型被加载时的** **`--ctx-size`**，opencode 的 `context`/`limit.input`/`limit.context` 只能控制 opencode 侧 compaction，抬不动服务端硬上限。此前 `604s/rc0` 的"成功"只是内容恰未超 64k 的巧合（假阳性）。

***

## 3. 修复动作

1. 备份 conf：`/etc/llama-instances/gpt-oss-120b.env` → `gpt-oss-120b.env.bak-ctx65536`
2. 修改 `CTX: 65536 → 131072`
3. 重载：`infer-load.new gpt-oss`（内部执行停旧实例 → pkill → wait-gtt 释放 → unsloth 重启）
4. 引擎新端口 `60207`（8080 仍为 unsloth 管理端，两层语义不变）
5. 就绪门重注入 opencode `cluster-litellm` 的 `baseURL` → `60207`

一键脚本：`ops/station-bin/_reload_ctx.sh`

***

## 4. 验证证据（三层）

### 4.1 服务端物理层

| 检查                  | 结果         | 证据来源                  |
| ------------------- | ---------- | --------------------- |
| `/props` 运行时 n\_ctx | **131072** | `_probe_ctx3.sh` 远端实测 |

### 4.2 错误消失对照层（决定性回归，防假阳性）

直接向新引擎 POST 一个**明确 >65536** 的请求，读取服务端真实 `usage.prompt_tokens`：

| 指标                  | 值                    |
| ------------------- | -------------------- |
| 请求文本长度              | 431,999 字符（72,000 词） |
| 服务端 `prompt_tokens` | **72,068（> 65,536）** |
| HTTP 响应             | **200 接受**           |

等价负载在旧引擎（`-c 65536`）必返回 400 `exceeds 65536`。判据由「run 巧合通过」升级为「**错误确实消失**」。

回归探针：`ops/station-bin/_ctx_overflow_probe.py`

### 4.3 功能层（真实任务）

specaudit 卡重跑（task `202609060017545026`，A 站 gpt-oss）：

| 指标              | 值                                    | 判据           |
| --------------- | ------------------------------------ | ------------ |
| `RUN_S`         | 502                                  | < 900 达标     |
| `TASK_RC`       | 0                                    | exit 0       |
| `ACCEPT_OK`     | 1                                    | 三章节 grep 通过  |
| 产物              | 3,577 B `out/.dogfood_spec_audit.md` | 存在           |
| stdout          | `DOGFOOD_TASK4_OK`                   | 完成信号         |
| `grep -c 65536` | 0                                    | agent 输出无该错误 |

agent 本次读满 12+ 个 `paper_cli/*.py` 及 2 份规格文档，无上下文错误。

***

## 5. 关闭判据核验

| 关闭判据                                                   | 是否满足                                  |
| ------------------------------------------------------ | ------------------------------------- |
| 配置/环境级修复落地后，specaudit 卡 900s 内 `ACCEPT_OK=1` 且产物引用真实文件 | 通过（`_reload_ctx.sh` 服务端修复 + 502s rc0） |
| 错误来源（`exceeds 65536`）在等价负载下不再出现                        | 通过（72068 token → HTTP 200）            |

两条判据均满足 → **O-21 关闭**（已同步更新 [OPEN-ISSUES.md](file:///D:/RPC/spec/d6-agent-standard/OPEN-ISSUES.md) 表格与详情段）。

***

## 6. 回归防护

- 留存回归探针 `_ctx_overflow_probe.py`（只需替换端口即复跑），作为服务端 ctx 上限的确定性门禁。

- 后续再遇 `exceeds available context size` 时，首查 `/props` 而非客户端配置。

***

## 7. 教训（标黑保留）

1. `exceeds available context size` 报错**先查服务端端点 ctx**（`/props`），不要先怀疑客户端。
2. `/v1/models` 的 `n_ctx`/`n_ctx_train` 是训练上下文；运行时上下文必须用 `/props` 的 `default_generation_settings.n_ctx`。探针字段选错会得出「引擎 131072、opencode 却 65536」的假矛盾。
3. 服务端硬上限面前，客户端所有超参（`context`/`limit.input`/`limit.context`）都是无效杠杆——**环境修复 > 配置修复**。
4. 单次 run 通过 ≠ 修复生效；必须对照「错误消失」而非「结果巧合」，并以服务端真实 token 计数为判据。

***

## 8. 关联变更 / 提交

- 提交 `9ea6160` fix(O-19/20/21)：agent-cli 站就绪门 + 目标站判定修复 + specaudit 服务端 ctx 根因闭环

- 新增脚本：

  - `ops/station-bin/_reload_ctx.sh`（ctx 重载）

  - `ops/station-bin/_ctx_overflow_probe.py`（回归探针）

  - `ops/station-bin/_probe_ctx3.sh`（/props 诊断）

