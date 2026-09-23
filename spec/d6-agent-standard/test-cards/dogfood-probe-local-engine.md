---
proj: dogfood
task: 本地引擎通道探针（注入夹具）：当站上无引擎时，本卡必须 STATION_NOT_READY exit 10
model: nemotron
cli: opencode
sensitivity: local-only
readonly: true
timeout_s: 120
accept:
  - cd /home/scott-lau/agent-workspaces/dogfood && test -f out/probe-never-reached
---
## 本卡是注入夹具，不是真任务

**用途**：证明 `agent-cli.ps1` 的**站就绪门（station-ready）在本地引擎通道上仍然生效** ——
即 2026-09-23 按裁定 A 改成"按通道分流"后，**`local/*` 通道必须依旧在站上无引擎时 `exit 10`**。

判据（在**站上无引擎**这一前提下）：

| 卡的模型 | 后端属性 | 期望 |
|---|---|---|
| `nemotron`（`local/nemotron`） | **不出网** | **`STATION_NOT_READY: engine not loaded ... ` + `exit 10`**（本卡） |
| `ultra`（`openrouter/...`） | **出网** | `STATION_READY_SKIPPED: egress backend ...` 后**继续**（见 `dogfood-d7-01a-station-reality.md`） |

**为什么需要这张卡**：分流后的门若失去"本地引擎必须就绪"的语义，就会变成**假绿**（门还在、但不判了）。
本卡与 A1 卡构成**一对正反用例**：同一时刻、同一站、同样"无引擎"，**一个必须红、一个必须绿**。

`accept` 里的 `out/probe-never-reached` **永远不该存在** —— 它只在"本卡意外跑进了执行阶段"时才会被检查。
