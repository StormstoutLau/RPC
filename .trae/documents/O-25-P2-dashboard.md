# O-25 P2：单文件 HTML 看板（已完成 + 正在跑总览）实施计划

## Context

O-25 P0（吞吐基准表 + `.progress` 打点 + 派发前预估）已闭环，P1（槽位门，并入 O-08/F1）已落地。
**P2 = 关闭判据④：L3 看板能渲染「正在跑 + 已完成」总览。**

现全部观测数据已就位，看板是**纯前端消费已存在数据**，不改后端派发内核：

| 数据 | 载体 | 消费方 |
|---|---|---|
| 已完成总览 | `d:\RPC\ops\station-bin\agent-runs.log`（`ts,proj,id,sens,code,queue_s,run_s`） | 列表 |
| 单次详情 | `D:\Paper\agent-out\<ts>\.agent-run.json`（profile/slot/accept/output_bps/queue_s/run_s/model/sens/status） | 展开 |
| 运行中节拍 | 远端 `$W/out/.progress`（采样 `t=<st> bytes=.. bytes_s=..` / 终值 `t=end ...`） | 正在跑速度+ETA |
| 吞吐基准 | `spec/d6-agent-standard/THROUGHPUT-BASELINE.md` + `Get-ThroughputEstimate` | ETA 静态回退 |

> 注意：`.progress` 运行中在**远端站**，ledger/run.json 在**主控**。file:// 单文件无法 ssh，因此「正在跑」数据由生成器在扫描时顺带拉到主控再内联。

## 方案形态：生成器 → 内联单文件 HTML（file:// 打开）

**为什么是「生成器 + 内联快照」而非「HTML 直接 fetch 本地 JSON」**：浏览器对 `file://` 协议开启同源（Same-Origin）限制，`fetch('file:///...')` 在 Chrome 被 CORS 拦截。故 HTML 必须 self-contained——所有数据在生成时**内联进 `<script>` 的 JSON 字面量**，打开时零网络请求。

### 1. 生成器 `ops/station-bin/make-dashboard.ps1`（新增）
- **输入**：
  - 读 `agent-runs.log` → `@(completed[])`（最近 N=50 条；含 ts 解析→日期）
  - 遍历 `D:\Paper\agent-out\*\ .agent-run.json`（scan ledger 里出现的 proj 根）→ 按 ts 建立 run-detail 索引（含 slot/profile/accept/output_bps）
  - `--live`（可选）：ssh 到在跑任务的站点，scp 拉 `.progress` → 生成时刻的 bytes/bytes_s/墙钟 → 当前瞬时 t/s + ETA
- **输出**：`d:\RPC\ops\station-bin\dashboard.html`（单文件，数据内联，见 §3）
- **退出码**：0 = 成功；非 0 = 生成失败（不产生损坏 HTML，保留旧快照）
- **幂等**：每次全量重建；无状态、无 DB、无构建链

### 2. 生成器读数据的三条路径（file 协议兼容）
| 数据 | 路径/位置 | 生成器读取方式 |
|---|---|---|
| ledger | 主控本地 `agent-runs.log` | `Get-Content` 直接读 |
| run.json | 主控本地 `D:\Paper\agent-out\` | `Get-ChildItem` 递归遍历 |
| live .progress | 远端站（`cluster-litellm/*` 目标站） | `--live` 时 `scp` 拉回 temp → 内联 |

### 3. 看板 HTML 结构（一个 `<script data-dashboard>` 内联 JSON + 纯 JS 渲染）
- **tab 1 已完成总览**：表列 = ts/日期 / proj / model / sens / exit / status(completed·timeout·failed) / run_s / queue_s / output_bps / slot.action（gated时）/ 展开详情（profile、accept、digest）
- **tab 2 正在跑总览**（有 `--live` 数据才显示；无可 `no-live-data` 提示）：表列 = 站 / model / 已产出 bytes / 瞬时 bytes_s→t/s / 已跑 s / **ETA**（见 §4）
- 状态着色：status=completed 绿 / timeout 黄 / failed 红；slot=reject 灰标注
- 无外部依赖：纯内联 CSS + ES5 JS；双击 `file://` 直接打开

### 4. ETA 计算（两段式，只对正在跑）
- **已实时**：`.progress` 已产出 bytes 与墙钟 → 已跑时长
- **剩余**: `max_output − 已产出` / `bytes_s`（动态，运行中实测）**回退 → `max_output − 已产出` / 基准 decode_tps**（`Get-ThroughputEstimate` 静态）
- **已完成不显示 ETA**（`run_s` 就是实际耗时）；无 bytes_s 且无基准档 → 打印 `ETA NA`（no-bench 纪律，不打荒数字）

## 关键文件
- `d:\RPC\ops\station-bin\make-dashboard.ps1`（新增：生成器）
- `d:\RPC\ops\station-bin\dashboard.html`（生成产物，commit 后静态交付）

复用：`Invoke-SlotGate`/`Invoke-StationReady` 的 ssh-capture 模式（`--live` 拉 .progress）、`Get-ThroughputEstimate`（ETA 静态回退）、run.json 已有 `slot/output_bps` 字段。

## 验证
1. **生成器离线**：AST_OK + UTF-8 BOM（`[System.IO.File]::WriteAllBytes` 补 EF BB BF）；跑出 `dashboard.html` 不抛异常
2. **已完成区**：打开 dashboard.html，「已完成总览」逐字段与 `agent-runs.log` 最后条目一致；run.json 展开正确（含 slot/output_bps，旧 run 无 slot 字段须容忍缺失）
3. **正在跑区**：站点引擎在线 + 一真实任务，`make-dashboard -Live` 后 HTML 显示「正在跑」且 t/s 非零、ETA 合理；无可 `no-live-data`
4. **file:// 直开**：双击 HTML，控制台 0 网络请求、0 CORS 错误
5. **回归**：`_fm_golden_test` pass=9/fail=0（确认 agent-cli 未被破坏）

## 边界（L1，不做 V2）
- 生成**快照**，非实时推送；刷新 = 重跑生成器（近实时由用户/定时任务触发）
- 只读渲染，不派发/不停卡/不转派（操作属 V2 / O-26）
- 单 proj（paper）起步，多 proj 由 ledger `proj` 列扩展
- 不做 SSE/WebSocket/DB

## 交付物串联
P2 闭环后 O-25 关闭判据①-④ 全满足 → O-25 从「P0 完成」升级为「全判据闭环」，P2 变 P3 候选（ETA 精度/自动刷新）或直接收口。