# O-25 P1：槽位门（Slot Gate）实施计划

## Context

O-25 P0（吞吐基准表 + `.progress` 打点 + 派发前预估）已闭环。**P1 = 槽位门**，并入 O-08 / F1（后端并发探测）。

现状：`Invoke-StationReady`（[agent-cli.ps1](file:///d:/RPC/ops/station-bin/agent-cli.ps1#L151-L191)）派发前已用 `_station_ready.sh` 探测远端引擎，且已 curl `/slots` 取 `n_ctx`——但**只用于 ctx，未判断"槽位已满则拒/等"**。目前派发前不查槽位占用 → 若目标站已被占（跨站扇出并发、手动叠加、其他会话），任务会静默排队直至 900s timeout 被杀（O-23 类痛点）。

O-08 明确：F1 后端并发探测 = "调 /slots + 槽位占则拒/等"。O-18 铁律：同站不叠并发，扇出优先跨站各 1。**用户已决策：槽位满默认拒绝派发**，提供 `--slot-allow-busy` 显式放行。

目标：派发前查目标站 `/slots`，满则默认拒绝（杜绝静默排队），SLOT_* 记入 ledger，支持 `--slot-allow-busy` 覆盖。**仅对本地 in-cluster 引擎生效**（`cluster-litellm/*`），出站 egress（`opencode/*`）无站上引擎、跳过。

行为边界（L1，不做 V2 范畴）：
- 只做**单站**探测+门，不做跨站自动转派（转派属 V2 编排 / O-26）
- 只在**本地引擎**走门；外部 API / 无 `/slots` 引擎（SLOT_NA）放行+warn

## 方案

### 1. 新增远端脚本 `_slot_gate.sh`（`ops/station-bin/`）
仿 `_station_ready.sh` 的 ASCII + shebang 风格。入参=引擎端口；输出 SLOT_* 摘要；无 `/slots` 输出 `SLOT_NA`。

```bash
#!/bin/bash
# _slot_gate.sh — 探测 llama-server /slots 占用 (O-25 P1 槽位门)。用法: bash _slot_gate.sh <port>
set -uo pipefail
PORT="${1:-}"
[ -n "$PORT" ] || { echo "ERR_SLOT_PORT_NA"; exit 20; }
BODY=$(curl -s -m4 "http://127.0.0.1:$PORT/slots" 2>/dev/null)
echo "$BODY" | grep -q '"id"' || { echo "SLOT_NA (no /slots; non-llama or old engine)"; exit 0; }
python3 - "$BODY" <<'PY'
import sys, json
slots = json.load(sys.stdin)
busy  = sum(1 for s in slots if s.get('is_processing') or s.get('state')=='processing' or (s.get('n_past',0)>0))
queued= sum(1 for s in slots if s.get('queue',0))
print("SLOT_TOTAL=%d SLOT_BUSY=%d SLOT_QUEUE=%d" % (len(slots), busy, queued))
PY
```

### 2. 主控 `Invoke-SlotGate`（`agent-cli.ps1`）
仿 `Invoke-StationReady` 的 ssh-capture 模式（`$out = ssh ... 2>&1` + 返回对象），不走 `Invoke-RemoteScript`（它只 stream stdout 不返回字符串）。流程：scp `_slot_gate.sh` → `ssh "bash /tmp/_slot_gate.sh <port>"` → 解析 `SLOT_TOTAL/BUSY/QUEUE` 或 `SLOT_NA`。

返回 `@{ ok; na; slot_total; slot_busy; slot_queue }`。网络失败置 na=$true 放行（不因探测失败阻断派发）。

### 3. `Invoke-Task` 接入（station-ready 之后、Assert-AgentOutWritable 之前）
- 解析引擎端口：`$readyInfo.raw -match 'STATION_READY port=(\d+)'` → `[int]$Matches[1]`（`Invoke-StationReady` 返回值已含 `raw`）。
- **仅当** `$id -like 'cluster-litellm/*'` 走槽位门（本地引擎）；`opencode/*` 出站跳过（打印 `SLOT-GATE: skip (egress)`）。
- 决策：
  - `na` (=SLOT_NA 或探测失败)→ 放行 + `SLOT-GATE: na, allow` warn
  - `busy>=total` 或 `queue>0` → 无 `-SlotAllowBusy` → 打印 `SLOT_BUSY reject` + `return 24`；有 `-SlotAllowBusy` → 放行 + warn `SLOT_GATE_BUSY_ALLOWED`
  - idle → 放行，记录 SLOT_* 供 ledger
- 新增 param `-SlotAllowBusy`（CLI `--slot-allow-busy`），并在 task 命令分发处接线。

### 4. Ledger / run 对象记录
在 `$run`（[L1026](file:///d:/RPC/ops/station-bin/agent-cli.ps1#L1026)）加 `slot = [ordered]@{ gated; total; busy; queue; action }`（gated=是否走了门；action=allow/reject/na/egress/allow-busy）。与既有 `queue_s` 并列，向后兼容（缺失时前端可不展示）。

### 5. exit 档位
新档位 **24 = SLOT_BUSY reject**（非失败，明确语义，供编排层识别后转派）。

## 关键文件
- `d:\RPC\ops\station-bin\_slot_gate.sh`（新增）
- `d:\RPC\ops\station-bin\agent-cli.ps1`（`Invoke-SlotGate` + `Invoke-Task` 接入 + `-SlotAllowBusy` param + ledger 字段）

复用：`Invoke-StationReady` 的 port 解析（raw）、`_station_ready.sh` 的端口/ASCII 风格、`Invoke-RemoteScript` 的 scp 落盘模式（SlotGate 用 ssh-capture 分支）。

## 验证
1. **离线防护**：AST（`ReadAllText`+`ParseInput`）= 0 错；UTF-8 BOM 校验/补回（新增内容纯 ASCII）；`_fm_golden_test.ps1` pass=9/fail=0。
2. **真实探测**：手动 `bash _slot_gate.sh <port>` 在某站确认真实 SLOT_*（idle 时 busy=0）。
3. **门行为**：
   - 正常单任务（gpt-oss → A，idle）→ 放行，打印 `SLOT-GATE: total/busy/queue`，ledger 带 slot 字段。
   - 模拟 busy：临时对该站发一次推理请求占用后派发，无 `--slot-allow-busy` → exit 24 + `SLOT_BUSY reject`；带 `--slot-allow-busy` → 放行。
   - 出站模型（ultra）→ `SLOT-GATE: skip (egress)` 放行。
4. **回归**：`route --model gpt-oss` 冒烟 exit 0（证明 script 加载与既有功能不破坏）。