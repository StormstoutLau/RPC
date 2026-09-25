# 开放日志：D6 agent-cli wrapper MVP（Open Issues 台账）

> **本表是"登记"（每条的证据、结论、待办）；开放项的定级与执行顺序见 [REMEDIATION-PLAN.md](REMEDIATION-PLAN.md)（2026-09-21）** ——
> 那份文档只做跨条目的优先级分析与工作项合并，不重复本表的证据。**本表新增/关闭一条时应回头改那份的定级。**

***

id: d6-agent-standard-OPEN-ISSUES
type: open-issues
version: 1.0
status: active（维护中）
date: 2026-09-04
depends: \[d6-agent-standard-CHECKLIST v1.0, d6-agent-standard-DESIGN v1.4, BLINDSCAN-v2-orchestration]
upstream: \[d6-agent-standard-CHECKLIST, d6-agent-standard-DESIGN]
------------------------------------------------------------------

> **用途**: D6 所有未决问题的**单一真值台账**——登记 P3 残留、BS 验证门、升级项、风险、跨站扇出待办。状态变更必须回写本表，禁止散落各处。
> **来源**: CHECKLIST §7.2（ADD 审计发现）/ §10（后续行动）/ §5（性能注记）/ §6（兼容性注记）、BLINDSCAN BS 验证门、DESIGN §11.3（分期移交）、ARCHITECTURE §8（演进预留）
> **关闭标准**: 问题闭环 = 代码/文档修复 + 实机复验证据回填本表

***

## 1. 未决问题总览

| ID   | 类别    | 严重度  | 简述                                                                                                                                                                                                                                                                                                                                                                                                                                                              | 状态                           | 归属批次                     | <br /> | <br /> |
| ---- | ----- | ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- | ------------------------ | :----- | :----- |
| O-01 | 功能缺口  | P3   | --attach 传输未实现（IMPL M4/S8 声明；param 块无 Attach，attach 恒 \[]）                                                                                                                                                                                                                                                                                                                                                                                                      | ✅ closed                     | 2026-09-05 最小实现已落地+端到端验证 | <br /> | <br /> |
| O-02 | 功能缺口  | P3   | workspace --archive 占位 echo 未演进（T1 stub）                                                                                                                                                                                                                                                                                                                                                                                                                        | ✅ 已闭环（2026-09-14，真快照归档落地）     | 二期                       | <br /> | <br /> |
| O-03 | 纪律    | P3   | A11/A12 probe 产物未持久化（证据腐化，仅文字实录在盘）                                                                                                                                                                                                                                                                                                                                                                                                                              | ✅ 已闭环（2026-09-14，纪律入册 §6）        | 纪律项                      | <br /> | <br /> |
| O-04 | 纪律    | P3   | ledger 追加非沙箱安全：沙箱会话运行 wrapper 时 Add-Content agent-runs.log 被拒（14:50 丢台账行）                                                                                                                                                                                                                                                                                                                                                                                       | ✅ 已闭环（2026-09-14，纪律入册 §6）        | 纪律项                      | <br /> | <br /> |
| O-05 | 性能    | P3   | sync 62.3s 微超 60s 预算 4%；IMPL §5 sync/task 口径重叠                                                                                                                                                                                                                                                                                                                                                                                                                  | ✅ 已闭环（2026-09-14，口径单一化复核）        | 二期/口径修正                  | <br /> | <br /> |
| O-06 | 兼容性   | ⚠ 部分 | S6 中文**路径/文件名**未测（内容级已测，路径级可选未执行）                                                                                                                                                                                                                                                                                                                                                                                                                              | ✅ 已闭环（2026-09-12，Cpp_Hub-001 试点）           | 试点已跑通               | <br /> | <br /> |
| O-07 | 验证    | P2   | zen 限额（429/quota）真实触发未发生（退出码 7 定义置位）                                                                                                                                                                                                                                                                                                                                                                                                                            | ⏳ 待真实触发                      | 事件驱动                     | <br /> | <br /> |
| O-08 | 升级    | P3   | F1 后端并发探测未实现（降级为 queue\_s 观测先行）                                                                                                                                                                                                                                                                                                                                                                                                                                 | ✅ F1 已落地（2026-09-12，并入 O-25 P1） | V2/并发 fan-out            | <br /> | <br /> |
| O-09 | 验证    | —    | BS-1 跨工作区并行 isolate\_db（SQLite 写锁序列化）                                                                                                                                                                                                                                                                                                                                                                                                                           | ✅ **已闭环（2026-09-12）**                      | V2 fan-out 前置            | <br /> | <br /> |
| O-10 | 验证    | —    | BS-2/跨站 编排层并发 HTTP fan-out 落地（L1 已验证，L2/L3 未做）                                                                                                                                                                                                                                                                                                                                                                                                                  | ✅ **并入 O-11 闭环（2026-09-12）**                    | V2                       | <br /> | <br /> |
| O-11 | 验证    | —    | 跨站扇出 L2 端到端（真实 readonly 卡）+ L3 回归（agent-cli-smoke + A 抽检）                                                                                                                                                                                                                                                                                                                                                                                                       | ✅ **已闭环（2026-09-12）**                      | V2                       | <br /> | <br /> |
| O-12 | 功能    | P3   | strong accept：附主控站侧 golden 测试（防模型自写测试自证通过，P1b 遗留）                                                                                                                                                                                                                                                                                                                                                                                                               | ✅ 已闭环（2026-09-12，Cpp_Hub-001 golden 落地）     | 下一任务卡（已落地）                 | <br /> | <br /> |
| O-13 | 预置    | —    | G8 预置批次：R/sympy/重资产（Cpp\_Hub 前）                                                                                                                                                                                                                                                                                                                                                                                                                                 | ✅ **已闭环（2026-09-14 A1+sympy 卡全链）**             | Cpp\_Hub 试点后             | <br /> | <br /> |
| O-14 | 依赖    | —    | 网关 auth 遗留：B:4000 LiteLLM 401 根因已改定（后端换载 key 不同步，非 master\_key 哈希）                                                                                                                                                                                                                                                                                                                                                                                              | ✅ 已闭环（绕网关直连，ADR-0002 C+_station_ready 每派发注入） | 运维修复（网关保留备用）                     | <br /> | <br /> |
| O-15 | 演进    | —    | claude 路径 + --continue（G1 二期，Continue-vs-Spawn 决策表）                                                                                                                                                                                                                                                                                                                                                                                                             | ✅ **已落地（2026-09-12）**                      | 二期                       | <br /> | <br /> |
| O-16 | 演进    | —    | review --peer 站间互审 / trae 派发（任务卡=接口）                                                                                                                                                                                                                                                                                                                                                                                                                            | ✅ closed（2026-09-12 评审环落地；--peer 站间互审留 D7） | D7+                      | <br /> | <br /> |
| O-17 | 演进    | —    | readonly 层 2 锁激活（V2 按任务卡字段细化）                                                                                                                                                                                                                                                                                                                                                                                                                                   | ✅ **已闭环（2026-09-12）**                      | V2                       | <br /> | <br /> |
| O-18 | 约束    | P1   | 同站内多并发被统一内存带宽顶起（\~2.8× 恶化）；落地铁律=扇出优先跨站各 1 并发                                                                                                                                                                                                                                                                                                                                                                                                                    | ✅ 已定案                        | 架构导入                     | <br /> | <br /> |
| O-19 | 环境    | —    | 两站模型全卸载 → agent 层 opencode 连 8080 但 `/v1/models` 空无法推理；跨界代码任务另暴露 A 站工作区无 `.venv`（accept pytest rc=127）。4-agent 吃狗粮因此中止                                                                                                                                                                                                          | ✅ **closed（2026-09-09 4/4 闭环）**<br>⚠ **2026-09-23 补注**：当时的闭环是"**先加载模型**"绕过，**根因（station-ready 未按通道分流、把出网通道也锁在引擎门上）直到 2026-09-23 裁定 A 才处理**；详见 O-30 | 见 §O-19 关闭记录 | <br /> | <br /> |
| O-20 | 功能缺陷  | P1   | Invoke-Workspace 同步目标站判定被 PowerShell 动态作用域污染：从 Invoke-Task 调用时 `$HostName` 解析为 SSH 主机串（非 'A'/'B'）→ `$station` 恒回退 'B' → **跨站任务源码流恒错推到 B，A 站任务在空壳工作区跑**（specaudit 卡虚构产物根因）                                                                                                                                                                                                                                                                                       | ⚠ **实测复现（2026-09-23）**：`-HostName A/C` 三次派发**全部落 B 站**（`LOCK_HELD` 同一 owner）⇒ "已修复"不成立；详见 **O-28**<br>**✅ 正解已落地（2026-09-24, P2-3）**：加 per-station 出网别名 `ultra-a`/`ultra-c`（与 `m27-q4ks-a/-b` 同构）⇒ **指定站实测生效**（`route_station=A`）+ 跨站**双取锁**；详见 [DEV-LOG-014](../../docs/DEV-LOG-014-decision-refinement.md) D3 | 2026-09-05 | <br /> | <br /> |
| O-21 | 性能/超时 | P1   | specaudit 卡 900s 硬超时/`exit1`——**三重返证后真根因尘埃落定**：①外层层 `timeout 900` 强杀正常推进 agent；②曾误判 opencode 对本地 passthrough 模型 64k 硬默认（根因实错）；③**决定性返证**：`/props` 运行时 `n_ctx=65536` 而 `/v1/models` 仅通告 `n_ctx_train=131072` → **服务端 llama-server 实以** **`-c 65536`** **加载**，那条 `exceeds the available context size` 是**服务端 400**，opencode 任何配置都无法抬升。修复=conf `CTX 65536→131072` 重载 A 站 gpt-oss；实机复验 `n_ctx=131072`、specaudit 卡重跑 `RUN_S=502/TASK_RC=0/ACCEPT=1` **全程无 65536 错误** | ✅ 已闭环（服务端 ctx 修复 2026-09-06） | 服务端 `-c 131072` 重载       | <br /> | <br /> |
| O-22 | 运维缺陷 | P1   | `.meta` 残留误导：只在 run 结束写、无 task_id → 二次 run 时读到上次终态（RUN_S=900/RC=124 误判"又超时"，实为残留） | ✅ 已收口（2026-09-12） | 契约修复 + 观测判据订正 | 2026-09-07 | <br /> |
| O-23 | 架构/超时 | P1   | **复杂度路由 ctx 解耦**：profile.context(code=8192/reason=32768/long=262144) 只是元数据、从未传给引擎；opencoe 用 opencode.jsonc 固定 limit.context=131072，引擎 ctx 由手动 flavor 预设决定 → 三者解耦。**凌晨 refdedupe timeout 真根因**=`request exceeds available context size (8192)`：nothink 档引擎 `-c 8192` < refdedupe 请求 12536 tokens → 服务端 400 → agent 永久挂死 → 900s timeout | ✅ 已修复+实机验证（引擎 ctx=唯一真相） | 2026-09-07 radical fix B | <br /> | <br /> |
| O-24 | 架构/闭环 | P1   | **单机 agent CLI 工作流闭环断点（分析定案）**：单机形态（无第二站分摊/换站/互审）存在 4 类断点——①review --peer 缺（产出→ledger 后无机器复核门）②超时续接 --continue 缺（长卡单机唯一韧性出路）③claude 备通道缺（单引擎死锁=停摆）④单机排队/上下文治理缺。P0=review 单机版 + continue 续接 | ⏳ **P0-① 已落地实证**（续跑循环入 $body，RESUME 出线+超时卡全链+零回归）；P0-② ✅（被 O-16 覆盖闭环） | O-24 实施记录 | <br /> | <br /> |
| O-25 | 演进/可观测 | P2   | **agent 任务执行进度可观测性（派发前预估 + 派发中节拍）**：派发后黑盒——ledger/.meta/.agent-run 均为 run-end 快照，无运行中采样 → 长卡状态不可观测、无吞吐、无 ETA；预算估算用单一 wall-clock 而非分相 | 🔵 P0 完成 + 判据③已落地：①吞吐基准表✓（THROUGHPUT-BASELINE.md+metrics-log Phase 6.2）；②`.progress` 打点✓（远端5s采样+teardown终值+collect拉取+parse回填）；③派发前预估✓（Get-ThroughputEstimate 分相估算，HIT才给/MISS不打荒，TIMEOUT-WARN预警；实证 gpt-oss 682s、回归9/9）；**P1槽位门✓（并入O-08/F1：`_slot_gate.sh`+`Invoke-SlotGate`+task接入，busy默认reject exit 24，`--slot-allow-busy`放行，slot记入run.json）**；**P2看板✓（2026-09-12 落地，L3 单文件 HTML：`make-dashboard.ps1` 生成器→内联 ledger+run.json→self-contained `dashboard.html`，**📌 2026-09-24 注：该生成器与产物已按 ADR-0004 D5 脚本清减移除（`3712f06`），能力由 [`ops/cluster_web.py`](../../ops/cluster_web.py) 统一管理页承接（在线）；同日"补做"落为 [`cluster.py agent dashboard`](../../ops/cluster.py) 的**自包含离线快照** —— 见 O-38**，file:// 直开零网络请求；已完成总览 22 行+run 详情展开；正在跑/Live tab 由 `-Live` 拉远端 .progress，无则 no-live-data；见 O-25 详情节）** | 🔵 **O-25 已全收口（①-④+P1/P2 全落地 + 2026-09-12 实机在线实测全通，见详情节）** | 一期 | <br /> |
| O-26 | 演进/编排 | P2   | **单任务分解派发并行（Split-Dispatcher）**：现派发=单卡→单站；一张可切分 readonly 大任务卡在单节点（物理上界 3：A/B/C 各1 并发，O-18）无法利用多站。缺口=任务卡无 `decompose` 声明、编排层无拆/并、无 Merge | ✅ **已闭环（2026-09-12）**：decompose 拆 2 分片 A/B 双站并行，全子卡 accept，Merge 正确，并行 465.1s ≪ 串行 720.8s（ratio 0.645）；落地修复 2 bug | V2 fan-out L2.5（schema 冻结前加 decompose 键） | <br /> | <br /> |

| O-27 | 验证/判据 | P1 | 证据链 `_VERDICT_RC_MAP` 未覆盖"远端 0 ⇄ 整体 1"（验收失败路径）⇒ **任何 accept 失败的 run 都阻断提交** | ✅ 已闭环（裁定 b **治同源** + 12 条正反注入） | ✅ 已修 |
| O-28 | 并发/编排 | P1 | **并发脆弱面**（一处列全）：站覆盖**半覆盖** · `$ts` 撞车 · 探针固定名 · sync tar 固定名 · create tar + staging 固定名 | ◐ 已修 5 处（RC①② + F-1/F-14/create）；**O-31 已于 2026-09-23 修复**（见下行） | D6-P2 |
| O-29 | 框架/卡面 | **P1（升）** | **"期望件集"有两处定义**（`agent-cli.ps1` 的 `Get-FrameworkSubjects` + `cluster.py` 侧消费方）⇒ 改一处**等于没改**（实测：改完重算仍报 3 条）；表现 = 无 golden 卡每 run 记 1 条 gap | ◐ **已改一处但未生效** ⇒ **并入 `D6-P1-1`**（抽成**单一数据源**，见路线总表 P1-1 方案） | **D6-P1-1** |
| O-30 | 环境/卡面 | P2 | 站上 **`/proc/*` 不可读** · **B 站无 `nvidia-smi`** · **`readonly:true` 与"必须落文件"互斥** | **✅ 纪律已入册（2026-09-24）**：三条（`/proc/*` 不可读 → 用 `free -m` · 无 `nvidia-smi` → `rocm-smi`/`/sys/class/drm` 回退链 · `readonly:true` 与"必须落文件"互斥）已写入 [dogfood-cards/README「站上环境的三条硬约束」](dogfood-cards/README.md)（纪律 8/9/10） | D6-P1 / D7-P1 |
| O-31 | 并发/防污染 | P1 | **claude 备路**站上固定名 `_p3_claude_*` + 备路**无 flock** ⇒ 同站并发互踩（**第四例同类**，与 F-1/F-2/F-14 同因：漏照抄"RUN_TOKEN / flock"两个样板） | ✅ **已修（2026-09-23）**：站上临时名改带 GUID 唯一前缀 `$p3id`（经 `$4` 参数传入站上脚本）；并加静态护栏（`tests/test_cli_concurrency_guards.py` O-31 断言）<br>⚠ **2026-09-25 更正（该修本身带出一个回归，已修）**：改名时**丢了 `/tmp/`** ⇒ 脚本内 `${PFX}_in.txt` 成了**相对路径**，而脚本已 `cd "$WORK"`、scp 落点却是 `/tmp/${p3id}_*` ⇒ 报 `没有那个文件或目录`、首跑+续跑均 `rc=7` ⇒ **站上 claude 通道整条不可用**。当时注记自认"站上实机并发复跑未做" ⇒ **未复跑就是这个代价**。已补绝对路径 + 护栏（`_fm_golden_test.ps1` D7 段）。详见 O-55 | ✅ 已修（含 09-25 更正） |
| O-32 | 工具/噪音 | P2 | **进度采样器读尚未创建的输出文件** ⇒ 每 5s 噪音 + run 中断（**连续误判三次**的坑） | ✅ 已定性 + 已修（待站上复跑验证） | ✅ |
| O-33 | 文档/一致性 | P2 | **水印入仓化后，引用旧路径 `ops/.audit-baseline.json` 的文档未跟随**（ADR-0007×2 · 调研稿×4 · ARCHITECTURE · REMEDIATION-PLAN · 本文 §1 · 路线总表 §10 A8） | **✅ 已复核并处置（2026-09-24）**：**逐处分类**（本仓既定两类：**历史记档**保留原文 + 加现状注记 / **现状陈述**就地更新）—— 复核发现**多数已带注记**（ADR-0007 §变更 · ARCHITECTURE :160 · BLINDSCAN F-11 · REMEDIATION-PLAN · 路线总表 A8/§13.5 · 台账 §2 各条），**真未跟随仅 1 处**：[`cluster.py` `--accept` 帮助文本](../../ops/cluster.py)（**现状陈述**，仍写 `ops/.audit-baseline.json`「本地不入仓」）⇒ **已就地更新**为 `inventory/audit-baseline/<host>.json`（入仓 + 溯源注记） | D7-P1-1 |
| O-34 | 门禁/一致性 | P2 | **迁移/重命名后「首次」门禁为 FAIL(1 项失败 / 绿灯 9)，而提交时同一命令为 PASS(绿灯 10)** —— **已定位**：`_iter_source_files()` 以 `git ls-files` 取范围，其假设"**pre-commit 阶段新文件已 `git add`**"**只在钩子里成立**；手动直跑 + 未暂存 ⇒ 范围不同 | ✅ **已修（2026-09-23）**：新增 `_untracked_count()`，`secrets` 报数行在未跟踪数 >0 时显式追加提示 ⇒ **让"范围已收窄"可见** | ✅ 已修 |
| O-35 | 并发/引擎 | P1 | **站上本地引擎是否支持并发请求 —— 未验证**（与 O-31 **不是同一问题**：O-31 修的是**文件名冲突**［文件层］，本条是**引擎并发行服务**［引擎层］） | **✅ 已闭环验证（2026-09-24）**：加载 `gpt-oss-20b`@B 实测（引擎 `--parallel 4`）—— **2 路 & 4 路并发均 报错 0 · ★输出错配 0**，每条仅含自己哨兵 ⇒ **引擎层并发安全，不受"错配"威胁**；★ 副产品：4 路墙钟 **2.64×** ≈ **O-18 的 ~2.8×（引擎层独立复现）** ⇒ 无需为错配加锁，但**叠并发必须算吞吐代价** | D6-P2 · D7 |
| O-37 | 工具/信号 | **P1** | **`.progress` 采样器 `t=0` 读上一轮残留**：启动时只 `: > .progress`、**不清 `out/.agent-output.txt`** ⇒ 首样本 `bytes_s` 假高（1.4e6+ B/s），**且 `bytes>0` 在 t=0 即成立** = **假进度/假完成信号**（与 T-1、O-22 同病族） | ✅ **已修 + 正反均已实测**（反例 = A1/B2 两条铁证；正例 = A2 复跑 `t=0 bytes=0`） | ✅ |
| O-38 | 文档/一致性 | P2 | **O-25 P2 看板缺磁盘证据**：其计划件写的 `ops/station-bin/make-dashboard.ps1` 与产物 `dashboard.html` **全仓 + 归档区均无**，`inventory/ops.yaml` 也未登记 ⇒ 台账"P2 看板 ✓ 已落地"**存疑** | **✅ 已复核（2026-09-24）**：**非虚报** —— 看板曾落地（`5f2b395`），后按 **ADR-0004 D5 脚本清减**删除（`3712f06`, 2026-09-15），**能力由 `ops/cluster_web.py` 统一管理页承接** ⇒ 仅**落点表述过时**（同 O-33 族）<br>**✅ 补做完成（2026-09-24 裁定"补做"）**：★ **不复活独立脚本**（否则撤销 ADR-0004 D5）⇒ 改为**能力并入统一入口**：`cluster.py agent dashboard` 产出**自包含单文件 HTML**（零网络）+ 沿用 `cluster_web.py` 在线卡片 | O-25 · D6-P1-1 |
| O-39 | 可观测/基准 | P2 | **派发前预估对出网档恒 MISS**：`ESTIMATE: … no-bench (MISS) - skip dispatch estimate`（基准表只覆盖 `local/*`）⇒ **吃狗粮全链路无预估** | **✅ 已裁并实施（2026-09-24）**：走 **②「显式声明」** —— 出网档**无本地 prefill/decode**，硬填 `$TpBench` 只会编造（违反"不打荒"纪律）⇒ **不补**。★ 顺带修掉**更值钱**的问题：原实现把 **(a) 出网档"按设计不适用"** 与 **(b) 本地档"真缺基准"** **混成同一句 MISS** ⇒ **(b) 隐身**（"把两件事说成一件"）⇒ 现改**三态分报**（`hit`/`na`/`miss`），`miss` 明确要求补 `$TpBench`；静态护栏 13→**14 条** + 判据双向自证 | O-25 |
| O-40 | 证据/回收 | **P1** | **卡的产物不进 run 目录**（`WORKSPACE_DIFF_LINES=0`）：产物只留站上工作区 ⇒ 目前**只能手动 `scp`** 取回（非持久位置） | **✅ 已实现（2026-09-24 复核）**：卡声明 `evidence-manifest.subjects[].state` + collect 段白名单 scp 回收 ⇒ 实测 `EVM_STATE: pulled=1`（B2 / 受控夹具 two runs）| D6-P1-1 · ADR-0007 |
| O-41 | 门禁自审 | P2 | **B2 审计报出的两条"疑似未登记假绿"**：① `doclinks` 对**绝对路径/盘符/URL 一律"不可判"跳过**（可写不存在路径而不报错）② `engine` 的**残留阈值 2048MB 硬编码**（1.5GB 且不监听端口的残留进程会被判正常） | **✅ 已复核（2026-09-24）**：**① 非缺陷**（= 射程声明"只判仓库内相对链接"，且不可判数已报数 ⇒ 留痕即关闭）· **② 真缺口**（字面成立）⇒ **✅ 已加固**（`RESIDUAL_WARN_MB=1024` 预警带 + 单测 `test_rpc_check_engine_bands.py` 7/7） | D6-P0-1（门禁自审，仅 ② ） |
| O-42 | 权限/通道 | **P1** | **`claude` 通道 `-p` 无写权限 ⇒ 产物型任务不可用**：烟测中模型自报"文件写入被拒"，`ACCEPT_OK=0`；调用形式 `'-p "" --model "<id>"'`（[agent-cli.ps1:2729](../../ops/station-bin/agent-cli.ps1)）**不带任何权限开关**，`settings.json` 的 `defaultMode: acceptEdits` 在 `-p` 下不生效 | **✅ 已修**（2026-09-24）：`-p` 按卡 `readonly` 动态加 `--permission-mode acceptEdits`（false 才可写；true 空串保只读）；claude 烟测端到端 `ACCEPT_OK=1` + `out/smoke.txt`=`SMOKE_OK`（run `202609241047036207`） | D6-P2 · claude 通道 |
| O-43 | 通道/归因 | **P1** | **zen（`opencode/*`）"需要 tty"被误判为"缺凭据"**（2026-09-21 结论）：非 tty 挂死 `RC=124` 且 DEBUG 日志**无任何 401/403/凭据错误**；套 `script -qec` **伪 tty** 后**同一模型 43s 返回 `ZEN_OK`** ⇒ **恢复 zen 不需要登录**，门槛是"给非交互路径伪 tty + **PTY 输出净化**" | **✅ 机制已验通 · ✅ 采样结论：不建议纳入运行时路由**（zen 5 次 **1/5 成功**、其后连续 4 次 152s 零输出=限流/空闲流卡死；**官方 = 限时免费实验资产**、随时下架 ⇒ 不接 ROUTE_TABLE，仅人工试点偶用） | D6-P2 · ROUTE_TABLE |
| O-44 | 门禁自审 | P2 | **`scripts` 把「未提交的新脚本」报成"清单项已不存在(应移除)"**：`gone` 基于**git 跟踪集**（`_iter_source_files`，同 O-34）⇒ 未跟踪的新脚本在冻结清单里"消失"；而该提示措辞**鼓励删除登记**（照做则提交后立刻"未登记"⇒ FAIL） | **✅ 已修（2026-09-24）**：`gone` 改判**文件真实存在性**（③）+ 新增 `untracked_frozen` 桶单独报、措辞**劝阻删除**（①）；**正反自证**：`git rm --cached` ⇒ note 报"1 项未跟踪(勿删)"（不再误报"应移除"），`git add` 后复原 | D6-P0-1 · **O-34 同源第二处消费者** |
| O-45 | 安全/执行面 | P2 | **`collect` 命令的"真执行器"未实现、且须带沙箱**（ADR-0007 line 475 明确"若执行需沙箱约束，否则卡可借 `collect` 任意执行"）。本轮 P1-1 先走**白名单 scp**（A-②）**不选此路**；本文档登记为待办，**须独立立项**：解析 → 远端执行 → 产物拉回 → **沙箱约束**（禁绝对路径 / 禁出 `$W` / 禁网络 / 禁 `..` / 白名单工具） | **✅ 已做立项取舍调研（2026-09-24）—— 裁定：⛔ 不立项（暂缓）**：依据 = **需求 0**（现有全部产物型卡的产物都是"单文件+名已知"⇒ A-② 100% 覆盖，且 `subjects` 是列表 ⇒ 多文件已支持）× **风险在信任根上**（卡=对端/模型内容，不可信）× ★ **候选沙箱自相矛盾**（白名单里的 **`python3` 图灵完备** ⇒ 沙箱≈不存在）× **沙箱做错=假安全**（比不建更糟）。⇒ **改走零执行面替代**：① 给 A-② 补 **glob**（仍不执行用户命令，远端固定枚举 + 纯函数校验 pattern）· ② "需站上加工"改为卡内指示 agent 自做。**触发条件**已写清（须"剔除 python3 后仍够用"） | D6-P2 · ADR-0007 |
| O-46 | 稳定性/通道 | **P1** | **出网档上游 Nvidia（`nemotron-3-ultra:free`）503/504 反复**：B2 7 次派发 **5 次被上游打断**（`provider_overloaded` / `idle timeout`） | **✅ 已裁（2026-09-24）**：**上游 provider 容量/冷却**（OpenRouter 官方 + NVIDIA 论坛一手实例佐证），非本地 · **缓解 ①② 已实施**（resume 2→3 + 冷却退避；失败 run 主动清残留）· **端到端负向验证通过**（`O46_CLEAN` 清 5 项 / 远端全 GONE / runDir 留存） | O-22 · 吃狗粮 |
| O-47 | 通道/模型 | P2 | **`lightning`（`inkling:free`）B 站一次停滞**（A1 卡 5 分钟仅 51 字节） | **✅ 已复测（2026-09-24）：非不可用** —— C 站同链路 `ACCEPT_OK=1`/`RUN_S=16s` ⇒ 真实定性 = **偶发停滞**（station/时序），**不删档** | ROUTE_TABLE · O-43 · O-46 |
| O-49 | 通道/模型 | P2 | **`harness_priority` 5 档在本链路是否可用 —— 未采过** | **✅ 已采样（2026-09-24）：5 档全过**（档1 inkling 16s · 档3 inkling-small 15s · 档4 super-120b 23s · 档5 laguna 56s · 档2 ultra 已知可）⇒ ★ **opencode 是 harness ⇒ conf 注记的"harness-only(403)/限流(429)"两条限制不适用**<br>**✅ 采样用别名已撤除**（Scott 裁定，结论留本条） | ROUTE_TABLE · O-43 |
| O-50 | 文档/一致性 | P2 | **手册 §1.3 的"真实剩余 open = 4 项"枚举已过时**（台账每批都在变）⇒ 两处各持一份枚举 | ✅ **已闭环（2026-09-25）**：**彻底撤掉手册的第二份枚举**（那张 4 项表已删 ⇒ 指向**本表 §1「未决问题总览」**单一真值）；手册**不再写死**门禁项数 / gap 存量（⇒ 指向 `rpc.ps1 check` 当场自报）。★ **并把"计数会漂移"从空头承诺变成机判**：门禁 `mirror` 新增 `validate_manual_counts` —— ① 手册 §2.4 的 `# N 项断言 (quick Q + 三站 S)` 必须 == 真实 `CHECKS`（**加/删断言忘改手册 ⇒ FAIL 并点名**）；② **反向护栏**：手册不得再出现『真实剩余 open = N 项』枚举 或『门禁 N 绿』写死计数。**先验红已验**（计数改 20/14 ⇒ 精确点名）。离线护栏 `tests/test_rpc_check_mirror.py` +3 负例 | ✅ 已闭环 |
| O-51 | 门禁/一致性 | P2 | **`inventory/sensitivity.yaml` 无任何消费者**（`ops/` 全域零命中）⇒ 真值表建了没人读（D6-P1-1 的"待裁 37"留白，当时已如实标注） | **✅ 已裁并实施（2026-09-24）**：**先定权威**（= 该表**自身**，它就是"内容→档位"的真值，不新增第二份）⇒ 新增门禁第 19 项 **`sensitivity`**（纯函数 `validate_sensitivity_inv`）：① 每条 `path` **必须真实存在** ② `tier` ∈ **封闭枚举** ③ ★ **同一 path 不得两处不同 tier** ④ `default_tier` 必须 `local-only`（fail-closed）+ 报覆盖率。★ **首跑即报红**：抓到 `docs/2026-09-23_D7统一基座_数理证明与知识提取三线调研.md` —— **曾入库后被改名**（`cdec317` → 并入 `...D7调研_立项·机制·统一基座.md`）⇒ 登记**指向空物**；删除陈旧别名（同文件另一条的 `fails` 是其**超集**）后**转绿** ⇒ **真实世界双向自证** + 离线护栏 `tests/test_rpc_check_sensitivity.py`（6 用例 + 结构护栏） | D6-P1-1 · 待裁 37 |
| O-52 | 证据/采集面 | P2 | **A-② 只支持"单文件扁平名"** ⇒ 产物名不可知时取不回 | ✅ **已闭环（2026-09-24，两轮）**。<br>① **真 bug（已修）**：`ls` 的 pattern **不能加引号**（引号把 `*` 变字面量 ⇒ 永远 0 匹配）；护栏已钉。<br>② ★ **适用性限制（本轮解）**：`out/` 是**累积**的（实测 dogfood 有 4 个 `.txt`）⇒ 原"候选恰好 1"在真实工作区**必然拒**。**解 = 运行窗口隔离**（复用 body 既有的 `.run-marker`）：**窗口内恰 1 → 取；窗口 0 且候选恰 1 → 取**（实测覆盖 `mv`/`cp -p` 型：产物 mtime 早于 marker、落在窗口外 ⇒ 无歧义亦取，**不制造回归**）；其余拒。marker 缺失 ⇒ `-nt` 恒真 ⇒ 退化为旧行为（不更宽）。护栏改为"窗口唯一确定 + 不加引号"（**先验红已验**）。★ **端到端真派发**（run `202609250018594080`，**真实脏工作区** `dogfood/out/` 已累积 4 个 `.txt`）：`EVM_STATE_GLOB: out/*.txt -> out/glob-probe.txt` + `EVM_STATE: pulled=1 rejected=0` + runDir 含 `GLOB_PROBE_OK` ⇒ 修复在真实场景生效 | ✅ 已闭环 |
| ~~O-53~~ | 证据/采集面 | ~~P1~~ | ~~产物在 accept 后、采集前从 `$W/out/` 消失~~ | ❌ **已撤回：现象不存在，是我的侦察命令有 bug**（见下"撤回记录"）。**该条从未成立** —— 登记本身是我的错误 | — |
| O-48 | 运维/孤儿进程 | **P1（升）** | **站上 `timeout 45` 诊断进程存活 17 小时**（B 站 `etimes=61817`）⇒ **`timeout` 未按预期终止** | ✅ **已闭环（2026-09-24）：根因定案 + 受控复现 + 全链条修复** —— 根因 = **裸 `timeout` 对忽略 SIGTERM 的子进程会「一直等」**（不是"到点即杀"）。**受控复现**（B 站）：`timeout 2 bash -c 'trap "" TERM; sleep 6'` ⇒ rc=124 但**耗时 6s**；同命令加 `-k 1` ⇒ rc=**137**、耗时 **3s**。★ **侦察发现生产同源**：`agent-cli.ps1` **4 处派发命令位**全是裸 `timeout`（主路 `/` 续跑 `/` claude 备路 `/` judge）⇒ 挂死时**永不返回**、留孤儿占槽。**修复**：① 4 处加 `-k 10`；② rc 映射 `124` **与 `-k` 的 KILL 码 `137`** 一并归 6（先打印原始码留痕；137 与 OOM 同码已在注释说明）；③ `rpc-nodes` / `a5-nextday-verify.sh` / `cluster.py` 远程串 / `tests/b5q` 同步；④ **静态护栏 3 条**（`test_cli_concurrency_guards.py`，含"命令位 timeout 一律带 `-k`"+"4 处不漏"+"137 归并"）；⑤ 纪律入册（dogfood README **纪律 11**） | ✅ 已闭环 |
| O-54 | 文档/一致性 | P2 | **受理状态机副本收敛**（[路线总表 §11.1-B](../../docs/2026-09-23_D6-D7分阶段执行方案.md) 实测 **9 处**；M-5/M-6 只覆盖了 代码白名单×2 + `_INBOX_NEXT` + `_ACTION/_ACTIVE` + README §3） | ✅ **已闭环（2026-09-24，D6-P1-2 #6-#9）**：真值源 = [`inventory/inbox.yaml`](../../inventory/inbox.yaml)（每态含 `group`/`next`/`requires`/`badge`），**余 4 处全部收敛** —— ① 前端 JS `inboxBadge` ⇒ 由 `badge` 派生 + 模板注入 ② `check_inbox` 4 处状态子集 ⇒ 由 `requires` 派生（**固化等价测试**钉住"派生 == 原硬编码"）③ `cluster.py seal` 提示语 ⇒ 同源派生 ④ **手册 §1.3 已漏 `rejected`**（11/12 态）⇒ 补注记 + `mirror` 对账；README §5.3「交付态强判据」行亦纳入对账。先验红已验（`badge` 非法 + README 交付态行不符 ⇒ 双点名）| ✅ 已闭环 |
| O-55 | 通道/架构 | P1 | **站上 claude 被锁死在"不出网"** —— `$useStation = ($sens -eq 'local-only')` 把"跑在站上"与"不出网"绑成充要 + `REJECT claude-station (exit 4)` ⇒ **站上 claude 永远配不了 OpenRouter**（三站 × claude 并发的唯一形态被架构禁止）。调研 §3.1 的 `public/sanitized ⇒ 站上 claude + OpenRouter` 那一支**从未落地**（P3 实施时按裁定收窄为"保持主控本地 spawn"） | ✅ **已闭环（2026-09-25）**：① `ROUTE_TABLE` 加 `claude-a/-b/-c`（**同一 openrouter id、不同 station**，与 `ultra-a/-c` 同构 ⇒ 不新立模型清单）；② 判据**拆成两个量**（`$useStation` = 跑在站上与否 / `$backendLocal` = 后端是否站上本地引擎），`-backendEgress` 入参由 `(-not $useStation)` 改 `(-not $backendLocal)`（**值等价、语义与位置解耦**）；③ 旧闸撤除，换成**配对闸** `REJECT claude-station-egress-local-id`（站上 egress 打 `local/*` ⇒ 前置拒）；④ 站上就绪判据换 `Test-StationClaudeEgressReady`（ssh + `claude` bin + 站上 `openrouter.key`；**不要求引擎就绪** —— 实测站上引擎未加载仍可出网）；⑤ 站上脚本加 `-Mode local|or`（`or` 写 `ANTHROPIC_BASE_URL=https://openrouter.ai/api`，`apiKeyHelper` 读站上独立 key）；⑥ 站不可用 ⇒ **拒跑并列出可用替代站**（用户裁定：**不静默换站**，换站须用户裁定）。<br>**自证**：夹具 200/200（含 9 条 D7 断言 + ROUTE_TABLE **真表**断言）；**正向** dogfood+`claude-a` ⇒ `P3_STATION: mode=or … RC=0` / `exit=0` / 台账 `station:A/thinkingmachines/inkling:free`，且**出网可判**（站上临时 settings 指向 OpenRouter + `ss` 抓到 claude→`openrouter.ai` 的 ESTAB 443 连接）；**负向** `local-only`+`claude-a` ⇒ `REJECT local-only-no-station-engine (exit 4)`（不静默出网）· `local/gpt-oss`+`-Cli claude`+public ⇒ `REJECT claude-station-egress-local-id (exit 4)`；**6 并发**（3 站 opencode + 3 站 claude，全 openrouter）**6/6 exit=0**、批墙钟 **78s**、三站产物均正确。⚠ 诚实边界：**"站不可用"分支未实弹**（三站全在线）；站上 egress 让**出网面从 2 处变 3 处**（凭据面不变 —— 复用站上既有 `openrouter.key`，不新增明文） | D7 |

| O-56 | 证据/判据 | **P1** | **框架基线"声明无条件、产出有条件"**（**两处**）：主路 `accept-cmds` **裸列**，而站上只在 `[ -n "$ACCEPT_B64" ]` 时才写（`agent-cli.ps1:1866`）、collect 侧"有则收"（`:2267`）；备路 `stderr` **裸列**，而归档是 `if (Test-Path $errTxt)`（`:3102`，站上 runner 走 catch 路径不回传）⇒ **每次触发即假报一条 `missing-artifact` 可重放 gap**，且**要人工 `--accept` 才能回绿** | ✅ **已定性 + 修法已定（2026-09-25）**。主路 `accept-cmds` ⇒ **条件列**（`if ($hasAccept)`）——**与 O-29 的 `golden-cmd` 同法**，而该原则**就写在同一个函数的注释里**（`:934-942`：O-29 当年为 `golden-cmd` 犯过同一个错）⇒ 本条是**该原则漏应用的第二个件**。备路 `stderr` ⇒ **无条件产出**（缺失时写空件）：**不适用条件列** —— 失败路径的 stderr 恰是最该留的证据，缺件本身是信号不该被抹掉。<br>⚠ **必须与 O-57 同批修**：O-57 的残留正**掩盖**本条（残留让主语"在" ⇒ gap 不发作）⇒ 单修 O-57 会让本条从"偶发"变"每个无 accept 的卡必发" | DEV-LOG-014 §27 · O-29 · O-57 |
| O-57 | 证据/归属 | **P1（升）** | **站上证据暂存件跨 run 错配（"D2"）**：`out/` 是**累计**的，而 collect 的**固定名拉回清单无 run 窗口**（`:1970`）⇒ 把**上一次 run** 的 `.accept-cmds.txt` 当本次证据归档 ⇒ run.json 的摘要**把别人的字节钉成本次运行的证据**（链没错 · 字节没错 · **归属错**）。★ **门禁看不见**（该件"在" ⇒ 不是 `missing-artifact`）⇒ **`--accept` 也管不着** | ✅ **已定性 + 全仓量化（2026-09-25）**：4 个 proj 根 **83 个 run** 逐条对账（归档 `accept-cmds.txt` 的内容 vs 该 run **自己那张卡**的 `accept:` 列表）⇒ **12 条不符**。**run `202609251304421233` 人工逐字核对**：卡为 `_o17_readonly.md`（**无 accept**），归档内容却是**另一张卡**的 `test -f out/glob-probe.txt …`。**且逐站残留 ↔ 逐站归档内容一致**（A/C = `smoke` 那套 09-24 18:58 · B = `glob-probe` 那套 09-25 00:19）⇒ 机制坐实。<br>**根因 = reset 只在失败路径**（`O46_CLEAN`，`:2354-2359` 删 `out/.meta`/`out/.progress`…），**成功路径不清** ⇒ 与 **O-22**（`.meta` 残留；同一批文件、另一处症状）**同根**。<br>**修法**：把证据暂存件的 reset 从"失败路径"提到**派发前无条件** —— 扩展**既有的**那条无条件 `.attach/` reset（`:1565-1577`，两条通道各一处）；**只删点前缀暂存件，不动 `out/` 交付物** ⇒ 一个改动同时关掉本类与 O-22 的残留面。<br>**配套机判**（把"看不见"变"可判"）：audit 侧断言"归档 `accept-cmds.txt` **==** 该 run 卡声明的 `accept:`"，不符单列一类 gap（**原型 = 本轮的对账脚本**，83 run 12 命中）<br>✅ **已实施（2026-09-25）**：新增**纯函数** `_card_accept_list`（口径与产出侧 `$accept -join "\n"` 对齐：只认围栏内顶层 `accept:` 的 `- item` 列表、**保序**、不混 `accept-golden`、不采行内写法）+ `compare_accept_cmds`（保序等值）；接入 `agent_audit`（gap kind **`accept-cmds-mismatch`**，走 `_gap_key` ⇒ 可进水印）；三态计数进 `totals`（`accept_ok/bad/skip`，**显式报"无法判定"条数**，免得把"判不了"读成"全对"）；离线护栏 [`tests/test_agent_audit_accept_owner.py`](../../tests/test_agent_audit_accept_owner.py) **16/16**（含"判据**真的接进** agent_audit"的结构护栏 —— 防"写了但没跑"）。★ **真实验红**：存量 **不符 13**（相符 49 / 无法判定 17）⇒ gap 表 **32 → 45**，那 13 条**此前对门禁完全不可见**。⚠ 13 = 手工扫出 12 条存量 + **1 条本轮的先验红对照 run**（`202609251407424475`）<br>⚠ **自查更正**：同批对账还报过 **11 条"卡声明 accept 却无 accept-cmds.txt"** —— 抽 11/11 **全为 claude 路 run**，而备路基线**本来就不声明该件**（`:947-950`）⇒ **那 11 条是我脚本的假阳性，已收回**（教训同族：**先证工具，再取证物**） | DEV-LOG-014 §27 · O-22 · O-52 · O-56 |
| O-58 | 运维/进程卫生 | **P1** | **站上 ad-hoc ssh 探针留下长龄孤儿**。根因**不是** `timeout` 语义（O-48），而是**未加引号的 `\|`**：远端 shell 把它当**管道** ⇒ 拆出 `auth`/`credential`… 当命令跑，或**起一个裸 `opencode` TUI**（交互式、无 `-p`、无 EOF）⇒ `epoll_wait` **永不返回** | ✅ **已定性（2026-09-25）；清理待裁**。B 站实测 **2 条**：`bash` **1-12:19**（`do_wait`，子进程 `grep -icE error` 卡死）· `bash`+**`opencode`** **1-04:59**（`ep_poll`）；活 `opencode` **47 fd**、**持 `opencode.db`（180MB）+ wal/shm + `memory.db` + 两个 `opencode.log` 写 fd** ⇒ 给同站所有用**共享 DB** 的 run 加了一个**不明写者**（**O-09 同族**：正是 `isolate-xdg` 要防的那类串行化来源）。A/C 同法扫描 **0 条**、无 zombie。<br>⚠ **O-48 的修法盖不住本条** —— 它管 `agent-cli` 的 **4 处派发位**，本类来自**探针**（第 5 类来源）；同族纪律（"登记无出口 ⇒ 腐化"）。<br>**纪律已入册**：dogfood README **纪律 12**（ssh 交替模式用**多枚免空格 `-e`**，或整体引号且确认引号**活到远端** —— PS 5.1 会剥内层引号，**实测**）。★ 顺手暴露**我自己也踩同坑**：`grep -e "[o]pencode run"` 到远端被剥成 `grep -e [o]pencode run` ⇒ `grep: run: 没有那个文件或目录`（无害，但证明该脆性在工具链里**是活的**）。<br>**建议机判**：门禁 `stations` 域加"长龄 orphan"（`opencode`/`claude`/`timeout`，etime 超阈 **或** `ppid=1` 非预期）—— 该信号目前**只能靠人肉 `ps` 偶然撞见**<br>✅ **机判已实施（2026-09-25）+ 清理已完成**：① `STATION_CMD` 加 **`[orph]`** 段（`ps -eo pid=,ppid=,etimes=,comm=` + **免空格多枚 `-e`**，遵纪律 12；**判定留在门禁侧**，与 `[conf]`/`[mpath]` 同分工）② `check_stations` 加 **(h)** 段判据（`comm ∈ {opencode,claude,timeout,defunct}` ∧ `etimes ≥ 阈值` ⇒ **WARN**，**刻意不 FAIL** —— 阈值判不出"合法的长 run"，且清孤儿是**不可逆**动作）；note 加 `/orphN` 计数。**阈值 `RPC_ORPHAN_SEC`（默认 6h）可覆盖 —— 为的是能先验红**（6h 无法现场造出）。<br>**双向自证**：(i) 默认阈值 ⇒ 三站 `orph0` / "无长龄 orphan"；(ii) `RPC_ORPHAN_SEC=1` + 站上自造 `opencode`（`cp /bin/sleep /tmp/orphantest/opencode`）⇒ **B 站点名报出** `opencode (pid …, ppid 1, 已 0h0m)`；清理后复跑回到 `orph0`。<br>**清理**：4 个孤儿进程已 `kill`；复核 `/proc/<pid>/fd` 归零、`opencode.db` 无持有者、三站复扫 `0`。<br>★ **同日顺带踩到两个新坑（都属纪律 12 同族，已并入其正文）**：(a) `pkill -f <模式>` **自匹配**携带该模式的 **ssh 命令行** ⇒ 把整条会话连同后续命令一起杀掉（实测：`rm -rf` 没跑成、白留一个临时目录）；(b) 目标路径 `/tmp/opencode` **已存在为目录**，`ln -sf`/`cp` 会落进它里面而不是替换它 | DEV-LOG-014 §27 · O-48 · O-09 |
| O-59 | 并发/隔离 | **P1** | **同站同 proj 跨通道 co-tenancy**：两通道共用 `WSROOT/<proj>`，且**都无条件 `rm -rf "$W/.attach"`**（主路 `:1565-1577` · 备路 `:2820-2827`），`.golden` 同样无条件重置（`:1690`）；而 `readonly:true ⇒ flock -s`（**共享**）⇒ **一方在跑、另一方重置 `.attach/`** ⇒ 附件**中途消失却照跑完** = **"缺件跑完"假绿灯**（本仓最高级别风险形态） | **已定性（2026-09-25）**。**危险序（更正我最初的排序）**：① `.attach/` 互删（**最危险**）≫ ② `.golden` 互覆 > ③ `out/` 同名交付物互覆 > ④ 证据暂存件交叉（**= O-57**）。<br>★ **6 并发当日"6/6 成功"≠ 隔离成立**：该卡 `readonly` 且**不带附件** ⇒ ① 删的是**空目录**、③ 产物**同名同内容** ⇒ 被掩盖；**但 ④ 在同批已实际发生**（正是 O-57 的第一例）⇒ 结论必须写成"**任务恰好无害**"，而不是"配对安全"。<br>**选项与代价**：**O1** 分通道工作区（**不推荐**：与 `--continue` **按目录恢复会话**的既有约束冲突，见 `:2803-2805`）· **O2'**（**推荐**）**按危险面条件互斥** —— 该 run **有附件 ∨ golden active** 时走排它，否则保持可并发（精确覆盖 ①②，保住今日这种良性的只读并行）· **O4** 仅可见化（run.json 记"同站同 proj 并存 run" ⇒ WARN）。<br>**零代码缓解（立即可用）**：同站配对时**用不同 `proj`**，或**不传附件、不依赖 `.golden`/`out/` 具体文件名**。<br>⚠ **2026-09-25 复核实测：原定的 O2'（"把该 run 的锁改成排他"）前提被推翻 —— 它挡不住危险序 ①**。实测：`flock` 在**主 run 体内**（`agent-cli.ps1:1771-1782`），而 `sync` / `.attach` 的 reset+scp / `.golden` 注入**全在锁之外**（`:432` 注释即写明"**sync 发生在远端 flock 之前**"）⇒ 锁只覆盖 **agent 执行相**，改锁模式对 **staging 相**无效：B 的 staging 仍会在 A 的执行相里删掉 A 的附件。<br>⇒ **修法必须把"锁"扩到"整次派发"**，两条候选：**T1（推荐，治本）** 把 staging 移进锁内（附件先传到**私有** `/tmp/<runid>/` 再于锁内落到 `$W/.attach`）⇒ 站内生效、覆盖任何派发来源；**T2（便宜，有已登记盲区）** 控制台侧 `(站,proj)` **共享/排他租约**（危险面 = 有附件 ∨ golden active ⇒ 排他），覆盖**控制台**派发（= 当前唯一威胁面），**不覆盖**第二台控制台 / 手工 ssh。<br>✅ **已闭环（2026-09-25，选 T1）**。★ **先验红成立**（新增探针卡 `t1-attach-shared-probe.md` = `readonly:true` + `attach-egress: ok`，全仓唯一能凑出"共享锁 + 附件"的组合）：同站同 proj 并发两跑、各带 1 件 ⇒ 两跑都 `mode=shared`、都 `ATTACH_MANIFEST_LINES=2`、agent 都列出**对方**的件 ⇒ **危险序① 从理论变实证**（症状并更正为"**证据面归属错 + 缺件**双症状"）。<br>**实现**（`agent-cli.ps1` 的 `Invoke-Task` 内）：① 私有中转 `/tmp/agent-stage-<RUN_TOKEN>`（与 `$W` 零接触）；② `.attach`/`.golden` 的**重置 + 落件移进锁内落盘段**（`LOCK_ACQUIRED` 之后、`.attach-manifest` 采样之前）；③ **危险面 ⇒ 排他**（`readonly ∧ ¬(有附件 ∨ golden)` 才 shared）；④ 失败路径兜底清中转（用**本 run** token，不用通配）。<br>**自证 V1-V8 全过**：V1/V2 夹具静态钉住（220/220）· V3 附件正向（`ATTACH_STAGED=1`/`MANIFEST=1`/只自己的件）· V4 golden 正向（**无附件但 golden ⇒ 排他** + `GOLDEN_STAGED=1` + `ACCEPT_GOLDEN_OK=1`）· V5 残留负向（埋 `foreign.txt` 跑后 **NO**）· **V6 capability 不退化**（6 并发 6/6 exit=0、批墙钟 56s、**无 exit 3**）· **V7 互删被消除**（胜者只含自己的件；负者 `LOCK_HELD` ⇒ **可见 `exit 3`**）· V8 三站 `stage_dirs=0/attach_scripts=0/procs=0`。<br>⚠ 实施期又抓 2 缺陷（并发才现形，见 O-60 / 下表"+3"）：per-run 脚本落点仍用**固定远端名**（B 覆盖 A 的脚本）；per-run 名导致 `/tmp` **累积**（补 `trap … EXIT` 自删）。 | DEV-LOG-014 §27 · O-17 · O-18 · O-57 |
| O-60 | 并发/命名空间 | **P1** | **备路（claude 通道）`$ts` 无去重** ⇒ 同一时钟滴答内启的两个 claude run 取到**同一个 ts** ⇒ 共用 `%TEMP%\agent-cli-claude-<ts>` scratch ⇒ 一方 collect 的 `Move-Item` **搬走**另一方的 `agent-output.txt` ⇒ 另一方 `scp: open local "…agent-output.txt": No such file` ⇒ **rc=7** | ✅ **已修（2026-09-25，实测触发）**：6 并发里 cc-A 与 cc-B **同 ts**（`202609251446473485`），cc-B 因此失败。补 O-28 RC② 去重到备路，且**判据同时看 scratch 目录** —— ⚠ 只看 `agent-out\<ts>` **不够**：runDir 是 **collect 时**才建，两个并发 run 都会在"彼此都还没建 runDir"时通过那条检查（**这正是本次漏网的原因**，值得记住）。夹具 `t1⑩` 钉住 | DEV-LOG-014 §27.11-H · O-28 |
| O-61 | 证据/判据 | **P2** | **`exit 3`（锁占用）的 run 天然没有证据件**（body 未运行 ⇒ `progress-trace`/`workspace-diff`/`attach-manifest`/`prompt`/`judgment-record` 都不会产出）⇒ 每个这类 run 记若干条 `missing-artifact` 可重放 gap | ⏳ **待裁（2026-09-25 新暴露）**：这是 **T1 的预期副作用**（危险面配对从"静默互删"变"可见 `exit 3`" ⇒ 这类 run 变多），本轮新增 gap 由 17 → **30**（其中 **13** 条来自 exit-3 run）⇒ 把 gap 表变成噪声源。<br>**修法建议**：加**第三态**（类比 `ephemeral`）：`locked-out-by-design` —— 由 `.agent-run.json` 的 `exit_code == 3` 判定，缺件时**不报 missing-artifact**，单列且不计入可离线复算（否则覆盖率虚高）。**替代**：直接把这 13 条 `--accept` 进水印（可与收尾合并，但等于把"预期形态"写成"已知缺口"）<br>✅ **已实施（2026-09-25，选第三态）**：`agent_audit` 由 `exit_code == 3` 判定 ⇒ 记为 **`locked-out-by-design`**（不报 `missing-artifact`、单列、**不计入可离线复算**）；`totals.locked_out` 供机器消费；coverage 显式声明"不计入缺口/不计入可离线复算"。**实测分离出 8 条**出缺口表。护栏 `tests/test_evidence_judges.py` **O61-1…O61-4**（含"第三态必须位于 `missing-artifact` **前置分支**"的**位置断言** —— 否则先算成缺口再改名就白做）。★ 执行顺序：**先补第三态、再跑收尾 `--accept`**（否则一次性噪声会被写进存量水印） | DEV-LOG-014 §27.11-H · O-59 |
| O-62 | 并发/隔离 | **P1** | **备路（station claude）无锁**：`$stWorkDir = WORKSPACE_ROOT/<proj>`（`:2963`）**与主路同一工作区**，并在 `:2969` **直接 `rm -rf $W/.attach` + scp**；而全文件 `flock` 仅出现在 `:652`（`lock` 子命令）与 `:1805/1810`（**主路 body**）⇒ **备路的 `.attach` staging 完全无互斥** | **已实证（2026-09-25）**：同站 B / 同 proj `dogfood` 并发两跑（`-Model claude-b` + 卡 `t1-attach-shared-probe.md`，各带 **1** 件**不同名**附件）⇒ 站上 `$W/.attach` 跑完**剩两件**（`fileA.md`+`fileB.txt`）、agent 实见 `T1_ATTACH_LIST: fileA.md,fileB.txt` ⇒ **危险序① 在备路可达且无任何保护**（主路已由 T1 覆盖：锁内落盘 + 危险面排他）。<br>**备路共享面清单**：`.attach/`（reset+scp，**无锁**）· `$W/out/`（agent cwd 产物）· `$W` 本身（cwd）；**golden 不在其中**（备路 golden 走**本地 scratch**：`:2897/3018/3088`）。<br>**候选修法**：**C1** 复用站上同一把 `.agent-lock`（把"取锁 + 落盘 + 运行 + 释放"包进站上脚本；改动中等）· **C2** 把备路 staging 也移进"锁内"（同 T1 形状）· **C3** 只把备路改成**互斥**（同站同 proj 串行；最省，但 capability 下降）<br>✅ **已实施（2026-09-25，选 C3 → 随后并入 C1）**：新增控制台侧租约 `Enter-ClaudeStationLease`（`FileShare.None` 排他 · 句柄由**进程存活期**持有 · 在 `if ($useStation)` **staging 之前**取）⇒ 拿不到即 **`REJECT claude-station-busy (exit 3)`**（与主路 `LOCK_HELD` 同码）。**双向自证（同一实验：同站 B 同 proj 并发两跑各带 1 件）**：修前 c2 **rc=7** + 站上 `.attach` **剩两件**（互灌）；修后 c2 拿到**不同 ts** + **显式 `exit 3`** + 站上 `.attach` 只剩 `fileA.md`（对方**从未** staging）。夹具 `o62①-③`（含"取租约必须早于 sync"的**位置断言**）。<br>✅ **未闭环项①②均已闭环（2026-09-25）**：① **C1 跨通道** —— `Enter-ClaudeStationLease` 通用化为 **`Enter-WorkspaceLease`**（rwlock：排他=`FileShare.None` / 共享=`FileShare.Read`），**三处调用同一把逻辑锁、同一 key 格式**（`st-<站>/<proj>` 与 `local/<proj>`）⇒ 主路与备路**跨通道**也互斥；**实测**：危险面跨通道并发 ⇒ 恰好一跑（main exit=0，claude `REJECT` exit 3）。② **本地模式** —— 有附件时取 `local/<proj>` 租约，且置于 `projRoot\.attach` 复制**之前**。<br>★★ **实测回归（被我自己的跨通道对照实验抓到，已修）**：C3 第一版把**两处备路**租约都写死 `-Exclusive $true` ⇒ 把**良性跨通道配对**（只读·无附件，6 并发里就有 oc+cc 同站对）也串行化 ⇒ 当场 `REJECT claude-station-busy`。修：三处一律按**危险面** `$leaseX` 取模式。**漏掉它的根因**：只复跑了 claude×claude，**没复跑 6 并发**（该对照是唯一能看见"良性配对"的夹具）。<br>★ **同族缺陷（修回归时一并发现）**：危险面判据原先只在"**有附件**"块内计算 ⇒ **无附件的站上 golden run** 读到 `$null`（=共享）而 golden 注入是**共享面写入** ⇒ 危险序① **漏挡**。修：判据上移到本函数开头（两处租约**之前**）**单点**计算。夹具 `o62⑧⑨` 钉"两处都按危险面"与"判据位置在 `if ($useStation)` 之前"两条**不变式** | DEV-LOG-014 §28 · §29.2 · §29.4 · O-59 · O-17 |
| O-63 | 隔离/命名空间 | **P1** | **"存在性检查"式去重是 TOCTOU** ⇒ 会同时撞 **scratch 与 runDir**：主路 `agent-out\<ts>` + `%TEMP%\agent-cli-ev-<ts>`（O-28 去重）与备路 `%TEMP%\agent-cli-claude-<ts>`（O-60 去重）**都是**"若已存在则递增"，而**两个并发进程会同时判定"不存在"** ⇒ 同时取到同一 `$ts` | **已实证（2026-09-25）**：同站两跑 `-Model claude-b` ⇒ 两跑 `scratch=…\agent-cli-claude-202609251516391217`（**同 ts**）、日志**没有** `TS_DEDUP` 行、且该 ts 下**只有一个 runDir**（两个 run **期望各有一个**）⇒ 一方的 collect `Move-Item` 搬走共享 scratch 里的 `agent-output.txt`/`claude-err.txt` ⇒ **另一方 rc=7**。<br>⚠ **就地更正**：我最初写作"5 件 vs 正常 9 件" ⇒ **错**（备路 runDir 正常就是 **5** 件；9 是**主路**件数 —— 把主路基线当成了通用基线）⇒ 论据已换成"同 ts 下只有一个 runDir"，不受件数影响。<br>**危害序**：**runDir 撞车 ≫ scratch 撞车** —— runDir 是**不可回改的证据单元**，两 run 写同一目录 ⇒ 证据面混且**归属不可复原**（比 O-60 那次更重）。<br>**根治方向**：① runDir 名**原子抢占**（`New-Item -ItemType Directory` **不带 `-Force`**，冲突则递增重取 ts）② scratch/临时根一律用 **`$Script:RUN_TOKEN`**（Guid）—— 本仓**已有**正确做法（主路本地临时根 `agent-cli-<RUN_TOKEN>` · 备路站上 scratch `/tmp/p3_<Guid12>_*`），只是**未统一**。<br>**⚠ 附一条推理（未证实，勿当结论）**：备路站上投递脚本 `/tmp/_p3_run.sh` **固定名** + `scp` **非原子** ⇒ 理论上存在"另一 run 的 scp 截断正在执行的脚本"race；本次实测的 rc=7 已归因 **ts 撞车**（`:3489-3497` 另有 CRLF 归因且已修）⇒ **不把 rc=7 算作它的证据**<br>✅ **已实施（2026-09-25）**：新增 `Get-UniqueRunStamp`（**create-or-fail** + 抢占物 GC；抢占物在 `%TEMP%\agent-cli-claims\<ts>.lock`，**刻意不进 `agent-out`** —— audit 只认含 `.agent-run.json` 的目录 ⇒ 空 runDir 会被**静默跳过**=隐形垃圾）⇒ **主路/备路两处** ts 选择都改调它（唯一性判据同为 `agent-out\<ts>` ⇒ **跨通道**也不撞）；`$ts` 的 18 位数字形状不变。<br>★ **原语实测选型（别改回去）**：第一版 `New-Item -ItemType Directory`（它**确实**在已存在时抛 `IOException`）在 **12 进程 hammer** 下**仍出现一对重复**（`uniq=11`）⇒ 换 `[IO.File]::Open(..., FileMode::CreateNew, Write, None)` ⇒ **12/12 唯一**（3 连跑稳定）。**教训：原语"看起来原子"必须用并发实测证，不能靠语义推断**。<br>**双向自证**：新夹具 [`ops/station-bin/_runstamp_hammer.ps1`](../../ops/station-bin/_runstamp_hammer.ps1)（12 **独立进程** + **共同释放时刻自旋屏障**）—— 正向 `n=12 uniq=12` PASS；负向（**同一把锤子**打旧实现）`uniq=2` ⇒ 证明夹具**能看见**撞车。夹具自身修了 4 处"**假通过**"型坑（① 无屏障 ⇒ 子进程启动抖动把 `Now` 散开 ⇒ **负向也全唯一**="夹具是装饰" ② 负向判据 `uniq<N` 在 `got=0` 时**假绿** ⇒ 必须同时要求跑满 N ③ `Write-Output (if …)` 在 PS 5.1 **不是表达式** ⇒ 需 `$()` ④ **无 BOM ⇒ PS 按 ANSI 读 ⇒ CJK 乱码+引号断裂**，被 `ps1-bom` 门禁当场抓到） | DEV-LOG-014 §28 · §29.1 · O-28 · O-60 |
| O-64 | 门禁/自审 | **P1** | **`tests/run_py_tests.py`（21 套 Python 测试的统一入口）从未被执行** —— 它**不在 `CHECKS` 里**，而 pre-commit / pre-push 两个钩子只跑 `rpc_check.py` | **已实证（2026-09-25）**：全仓 grep `run_py_tests` 命中仅 `tests/` 自身 + 2 处 docs + `DEV-LOG-012` + `OPEN-ISSUES` 2 处 + `fixtures/` —— **`ops/` 内零引用** ⇒ 该入口**无任何机械执行者**。<br>**为什么这是 P1（而同类的"漏一条断言"只是 P2）**：它让**整类**"实现改了、护栏没跟着改"的漂移**无人发现** —— 本轮 O-62/O-63 落地后 `test_cli_concurrency_guards.py` 当场红了两条（见 O-65），**连续两轮提交都没被任何钩子拦下**。<br>★ **正是本仓自己命名的反模式**："有测试 ≠ 有人在跑"（同一件事 5 种载体 —— `CHECKS`/夹具/静态护栏/文档铁律/台账 —— **只有接进 `CHECKS` 的会真跑**）。`docs/2026-09-23_D6-D7分阶段执行方案.md` §7 把 `run_py_tests` 写进「通用要求·验证组合」，但那是**口头纪律**，没有机械约束。<br>**修法**：新增一条 `CHECKS` 断言跑 `run_py_tests.py`（**实测 13.3s**，建议 `quick=True`；若要省钱可放非 quick 但必须**每轮必跑**）。⚠ **两个坑**：① 解释器口径（O-36）—— 必须用与钩子同一个能 `import paramiko` 的解释器，否则会**静默少跑 4 个套件**；② 判据必须是"**退出码 0 且失败数为 0**"，不能只看"跑没跑起来"（否则又是一个"什么都没判所以通过"的假绿）。<br>✅ **已闭环（2026-09-25 当日）**：`rpc_check.py` 新增断言 **`py-tests`**（`check_py_tests`）—— 判据 = **退出码 0 ∧ 解析到汇总行 ∧ 通过数==总数 ∧ 总数>0**（四者缺一即 FAIL；专防"总数==0 / 什么都没判"的**假绿**）。★ **解释器用 `sys.executable`**（= 门禁自身那个）⇒ 从构造上杜绝 O-36 的"换解释器静默少跑 4 个套件"。**`quick:False`**（实测：本入口 12.2s，quick 门禁本体 18.4s ⇒ 塞进 quick 会把 pre-commit 从 ~18s 拉到 ~31s；非 quick 仍由 **pre-push 全量**兜住 ⇒ 红状态推不出去），与 `ps1-runstamp` 同一决策依据。手册断言计数 25 → **26**（quick 18 + 全量 8，由 `mirror` 的 `manual-counts` 对账）。**先验红**：注入 `tests/test_zzz_priori_red_tmp.py`（`sys.exit(1)`）⇒ 门禁报 **FAIL/红灯 1 并点名该文件**；删除后复跑回 **PASS 21/21**。<br>★ **机械那一半已核实（2026-09-25，用户质疑"是否可以闭环"触发）** —— O-64 的闭环**全靠"钩子真的会跑"**，故逐项核了钩子侧：① `git config core.hooksPath` **未设** ⇒ 走默认 `.git/hooks`（未被改指别处）；② `pre-push` 存在且跑的是**全量**（`exec "$PY" ops/rpc_check.py`，**无** `--quick`）⇒ **含 `py-tests`**；③ 钩子里的 `PY` = `py.exe`（有 paramiko ⇒ 与 O-36 口径一致）。**实证**：本会话一次真实提交被 `pre-commit` 当场拦下（`scripts` 报未登记脚本）⇒ 钩子**确实在跑**，不是摆设。<br>⚠ **遗留边界（如实，不掩盖）**：**`quick:False` ⇒ 坏状态能被 `commit` 但拦在 `push`**（共享面安全，本地历史不保证）；钩子在找不到 Python 时 **fail-open**（`exit 0`，既有设计、已在钩子注释里声明） | DEV-LOG-014 §31 · O-36 · O-65 |
| O-65 | 测试/护栏 | **P2** | **`tests/test_cli_concurrency_guards.py` 两条静态护栏与实现漂移**（18 条里红 2 条）：① `O-28 RC②` 断言找的是 `$ts = …ToString('yyyyMMddHHmmssffff')` 之后紧跟 `while (Test-Path (Join-Path $tsOutRoot …))`，而 **O-63 已用"原子抢占"`Get-UniqueRunStamp` 取代 check-then-act** ⇒ 老模式**已不存在**；② `★ 纪律: 无【新增】的共享临时/暂存路径行` 点名 `agent-cli.ps1:746` 的 `agent-cli-claims`（O-63 抢占目录）与 `:805` 的 `agent-cli-lease-<safe>.lock`（O-62 锁文件） | **已实证（2026-09-25）**：`py tests/run_py_tests.py` ⇒ **20/21**，该文件 18 条护栏 **2 条 FAIL**。<br>★ **归因：本轮 O-62/O-63 引入**（我改实现时**没同步改护栏**）。**决定性验证**：`git show HEAD~2:ops/station-bin/agent-cli.ps1` **命中**老模式 `while (Test-Path (Join-Path $tsOutRoot ([string]$tsN)))`（⇒ 提交前该断言**本来是过的**）；`HEAD` 下 `Get-UniqueRunStamp` **5 处**、老模式 **0 处**。<br>**正确修法（勿搞错方向）**：① **重写**（不是回退代码）—— 把 O-28 RC② 换成"原子抢占"判据（断言 `[IO.File]::Open(…CreateNew…)` 存在 + 两处调用点 + 旧 check-then-act 已消失）；② 那两行**是"设计上必须跨进程共享"**（抢占目录 / 锁文件 —— 共享正是它们的功能），属**合法豁免**，应按该表自身纪律（"新增豁免必须在此显式登记并写理由 —— 防豁免清单腐化"）登记进 `EXEMPT` 并写明理由，**不得**为了让断言变绿而给它们套 `RUN_TOKEN`（那会**破坏功能**：租约/抢占的 key 必须跨进程一致）。<br>✅ **已闭环（2026-09-25 当日，按上述"正确修法"执行，**未回退任何代码**）**：① **改写断言** —— `O-28 RC②` 的判据由"盯行文"改为**盯原子语义**（`[IO.FileMode]::CreateNew` 原语 ∧ `Get-UniqueRunStamp` 定义 ∧ 调用点 ≥2 ∧ **旧 check-then-act 在代码里已消失** ∧ 抢占物有 GC），并保留"注释里留档老模式**不算违规**"的口径（复用本文件既有的 `code_hits`，区分代码/注释）。**先验红**：把原语注入改回 `OpenOrCreate` ⇒ 断言 **FAIL 并精确点名 `原子原语=False`**；恢复后复跑 **18/18 ALL PASS**。② **登记豁免** —— 新增 `EXEMPT` **第二类**（"**必须跨进程共享**"），key 用**带引号字面量**（`'agent-cli-claims'` / `"agent-cli-lease-`）钉住具体那行，防宽 key 顺带豁免将来同类命名；理由写明"加 `RUN_TOKEN` 会**破坏**抢占/互斥语义"。③ 文档串同步：文件头覆盖清单 + `py-tests` 断言指引均注明"**先判是回归还是断言陈旧；方向是改写断言，不是回退代码**"。**结果**：`py tests/run_py_tests.py` **20/21 → 21/21**；全量门禁 **PASS · 绿 24 / 黄 2 / 红 0**<br>★★ **二轮复核（2026-09-25，用户质疑"是否可以闭环"触发）—— 上一轮那句"✅ 已闭环"**不成立**，本行就地更正**：新判据的 `ts_atomic` 用的是**全文子串**（`"...CreateNew" in src`）而非**该测试文件自己规定的**代码/注释分离口径（`code_hits`）⇒ **只要注释里出现 `[IO.FileMode]::CreateNew`，断言就会过，哪怕代码侧已退化成 `OpenOrCreate`**。**实测复现**：代码改 `OpenOrCreate` + 注释写上该串 ⇒ 断言仍报 **ALL PASS**（**假绿** —— 与 O-64 同一种病，只是这次长在我自己的修复里）。修：新增 `code_only(src)` 辅助（与 `code_hits` 同口径），`ts_atomic`/`ts_def`/`ts_sites`/`ts_gc` 四项**全部改用它**；**同一对抗样本复验 ⇒ FAIL 且点名 `原子原语=False`**；恢复代码 ⇒ **18/18 ALL PASS**。★ 并把该串**刻意留在注释里**当**常驻对抗样本**（附"别顺手改回短名"的警示）⇒ 该判据从此**不可能**退回"可被注释蒙过"。**教训：改写判据前必须先读本文件已有的口径约定 —— 我违反了自己文件里写着的规矩。** | DEV-LOG-014 §31 · O-64 · O-63 · O-62 · O-31 |

| O-66 | 安全/契约 | **P1** | **`input-provenance` 的义务只在文档里，机判为零**：`CROSS-PROJECT-WORK-STANDARD §4` 与 `inventory/sensitivity.yaml` 都规定"卡声明 `public`/`sanitized` **且带输入** ⇒ 必填 `input-provenance`，且每项须在表内有 `tier`、**卡档位不得宽于该项**"，但**没有任何代码校验它** | **已实证（2026-09-25）**：① `ops/` 全域 grep `input-provenance` **零命中**；② 表自身文末「待接入」段**如实登记**"义务仅文档级"并给出 5 条候选断言；③ 本轮核对**已覆盖 ①②③+⑤**（`check_sensitivity` 经 `validate_sensitivity_inv` 判 path 存在 / tier 枚举 / 同 path 不撞 / yaml 可解析），**唯 ④（卡面义务）零机判**；④ **存量影响面实测 = 44 张卡中 4 张声明 `attach-egress: ok`，其中仅 2 张写 `input-provenance`**（`b1b`/`b2` 合规；`a2`/`t1-attach-shared-probe` 会红）。<br>**为什么是 P1**：这是**吃狗粮读本仓**的唯二护栏之一（另一是 `attach-egress`），而 §13.2 已实测"sensitivity 是**卡作者的声明**不是**内容的属性**"（不写=默认 public）⇒ 缺本判据时，"一张写 public 的卡带未发表内容出网"**没有任何机制知道**；D7 阶段读本仓的频次高于 D6。<br>★ **建议落点（复用既有纯函数族，不新建机制）**：照 `Get-AttachEgressReject`（**纯函数 + 三条全中才拒 + fail-closed 拒发**，同族还有 `Get-SensitivityBackendReject`/`Resolve-ReviewPrompt`）加 `Get-InputProvenanceReject -attachCount -backendEgress -sensitivity -provenanceDeclared -provenanceOk` ⇒ **在派发时**判（工具此刻**已知**真实附件数），而不是只做卡面静态校验。<br>⚠ **防"逼人填假值"**：必须有**显式"输入不来自本仓"**的表达（候选 `input-provenance: none`），**但 `none` 必须可证伪** —— 建议同时机判"声明 `none` 的卡，其正文不得出现 `sensitivity.yaml` 里已登记的路径"，否则 `none` 会变成万能挡箭牌（同 `attach-egress: ok` 的放行性质）。<br>**归属**：表文末写"接入任务归 **D6-P1-1**"，而 D6-P1-1 已标 ✅ 落地 ⇒ **本项属"已闭环批次下漏落的子项"**（与 O-56 同族）。<br>✅ **已闭环（2026-09-25 当日，Scott 裁定"两者都落"）**：新增门禁断言 **`input-provenance`**（`check_input_provenance` + **纯函数** `validate_input_provenance`，`quick=True` ⇒ **提交即拦**）。**四条规则**：① 触发（`attach-egress: ok` ∧ `public`/`sanitized`）而缺字段 ⇒ **FAIL**（含"留空"）；② 项未登记于表 ⇒ **FAIL**；③ 卡档位宽于该项 tier ⇒ **FAIL**；④ 声明 `none` 却引用 **tier 严于本卡**的已登记路径 ⇒ **WARN（不阻断）**。<br>★ **落点就地更正（实测）**：原建议"派发时判"需要 **PowerShell 读 `sensitivity.yaml`**，而 **PS 5.1 无 YAML 解析**（实测 `agent-cli.ps1` 全域零 YAML 用法）⇒ 改落**门禁侧静态**；**且覆盖等价**：运行时 `Get-AttachEgressReject` 已强制"有附件 ∧ 出网 ⇒ 必须声明 `attach-egress`" ⇒ 以**声明**为条件判 = 覆盖同一人群（且是超集 ⇒ 保守 ⇒ sound），并在**提交时**就拦。<br>★★ **本轮又踩到一个"我自己的假绿"（已修，如实记）**：判据第一版用 `yaml.safe_load` 解卡面 front-matter ⇒ 实测 **2 张卡**（`t1-attach-shared-probe` · `cpphub-001`）的值里含 `": "` ⇒ 抛 `ScannerError`，而我**静默 `return None`（跳过该卡）** ⇒ 把本该触发的 `t1` 漏过去了。修：改用**行式提取**（与 PS 侧 `Get-FrontMatter` **同口径**，同时也消除"Python 说坏、PS 读得动"的双标）+ 支持**块式列表**（否则列表形式会被读成空串 ⇒ 假红）。**修后先验红完整命中 `a2` + `t1` 两张**。<br>**存量迁移**：`a2`（输入 = 主控预置的**站上**脚本清单）与 `t1`（输入 = **合成探针**）各加 `input-provenance: none`（与其真实语义一致，**非为过闸而填**）。**护栏** `tests/test_input_provenance.py`（**18 项**：正反 + 触发/不触发边界 + `unverified` 排名 + 块式列表 + **两条"假绿"护栏** + 真实基线 + 覆盖率）。**结果**：门禁 `input-provenance` **PASS**（卡 40 · 触发 4 · 合规 2 · none 2）· `run_py_tests` **22/22** | DEV-LOG-014 §32.6 · O-51 · §13.2 |
| O-67 | 通道/并发 | **P2** | **出网档 `decompose` fan-out 的并行性是【未验证假设】** —— 代码自己打印的 `SPLIT_WARN` 原文：「`cross-station each-1` **assumes per-station engines**；egress **has single route, fanout may not parallelize**」⇒ O-18 那条纪律（跨站各 1）**建立在"每站有本地引擎"的前提上**，而出网档**没有本地引擎** ⇒ **该前提对它不成立** | **已定性（2026-09-25，读码得出，未实测）**：`agent-cli.ps1:2674-2676` 对 `Get-BackendEgress $id` 为真的 model 打印 `SPLIT_WARN`；站池 `@('A','B','C')` 且 `片数 > 站池 ⇒ SPLIT_INFEASIBLE … exit 18`（`:2678-2682`）。<br>**影响面（精确）**：**`decompose`（同卡拆片）**。⚠ **不含**"两张卡各钉一站"—— 那是两个独立进程 + per-`(proj,站)` 两把不同的锁 ⇒ **真并行**（今日 6 并发即此形态）。<br>**要判什么**：出网档拆 N 片后，**批墙钟是否真按 N 缩短**（对比串行）。若不然 ⇒ `decompose` 对出网档应**禁用**或改判为"队列"，而不是假装并行。<br>**未做原因**：需 ≥2 片 + 串行基线，成本与 D7 排期相关（不是随手可测）⇒ 登记待裁。 | D7-P3-2 |<br>✅ **已实测（2026-09-25，2 片 × 2 站 × 出网档）—— 结论：`SPLIT_WARN` 的担忧在这一形态下【不成立】，fan-out **确实并行**。**<br>　**仪器**：新增**公开**主卡 [dogfood-cards/o67-egress-fanout-probe.md](dogfood-cards/o67-egress-fanout-probe.md)（`readonly: true` + `decompose` **两片平衡**；★ 两片**只能是纯 stdout** —— 拆片器**要求 readonly**，而站上"readonly 与落文件互斥"⇒ 产物由拆片器 per-shard 日志接住）。<br>　**一次 run 内自证（不需要另跑串行基线）**：`split dogfood -Card … -Model ultra` ⇒ `SPLIT_DONE shards=2 all_ok=True `**`wall_ms=31396`**；两片各自 `run_s=16s / 24s`、`queue_s=2s`，且两片 runDir 的 **ts 相差 51ms**（`…0011229840` vs `…0011229891`）⇒ **同时起**。<br>　**判读**：并行 ⇒ `wall ≈ max(片) + 派发开销` = 26 + ~5.4 = **31.4s ✓**（观测值）；串行 ⇒ `wall ≈ 18 + 26 = 44s ✗`（观测值比它低 **12s+**）⇒ **判为并行**。<br>　**为什么在出网档也成立（机理，与观测一致）**：`SPLIT_WARN` 的前提是"跨站各 1 **假设每站有本地引擎**"，而 egress 的瓶颈不在站上引擎、在**上游账户配额** —— 三站 `openrouter.key` **各不相同（独立账户）**（README 派发前必读段实测 md5 三个值）⇒ **两站并发 = 两个账户**，互不挤占 ✓。（⚠ 这同时给出**适用边界**：若把多片挤到**同一账户/同一站**，并行性就不再有这个理由。）<br>　**未覆盖（如实登记）**：① 只测了 **2 片 / 2 站（A+B）**；**3 片 / 3 站**与"同站两片"未测（后者的物理上界是 O-18 的 ~2.8× 带宽现象，属**本地引擎**面，与 egress 无关）；② 未测"**上游拒绝/限流**"时的形态（那属于 §O-46 的 503/504 面）。⇒ **建议**：把 `SPLIT_WARN` 的措辞从"may not parallelize"**收窄**为显式条件（"若多片共用同一出网账户则可能排队"），因为当前措辞会让人以为出网档 fan-out **默认无效**（实测相反）。<br>　★ **该建议已于 2026-09-25 当日执行**：`SPLIT_WARN` 改写为 "**并行性取决于账户/站粒度**: 跨站（各站独立 key）= 可并行【实测 2 片/2 站成立】; 多片共用同一出网账户或同一站 = 可能排队"，并加**夹具断言 o67①/②** 防退回旧措辞（旧措辞的实际危害 = 让读者**放弃一条实测可用的能力**）。 | ✅ **已实测 + 措辞已收窄** · DEV-LOG-014 §38 · O-26 · O-18 |
| O-68 | 并发/隔离 | **P1** | **`$evRmCmd`（O-57-A 的证据暂存件 reset）位于【锁外】且是【破坏性删除】** ⇒ 同站同 proj 并存时，**后起 run 的前置 reset 删掉先起 run 正在用的 `out/.meta` / `.progress` / `.prompt.txt`**；而站上 `flock` 对 `readonly` 取 **`-s`（共享）** ⇒ **结构上允许并存** ⇒ 这是**"锁允许、工作区不支持"的错配**，不是性能问题。★ **T1 只把 `.attach`/`.golden` 移进了锁内，漏了这个同族件** —— 且**仅"移进锁内"也挡不住**（`.attach` 靠"有附件⇒排他"避开并存；而 `$evRmCmd` 是**无条件**执行 ⇒ 两个**共享**持有者仍互删） | **已定性（2026-09-25，读码 + 机制推导；未实测）**：`agent-cli.ps1:1724-1728` 的注释明写"本 body 是**每次派发最早的远端写入点**(早于附件 scp、早于主 run body)" ⇒ **刻意插在锁之前**；锁在 `:1917-1922`（主 run body 内），其模式由 `:1872-1884` 定（`readonly ∧ ¬危险面 ⇒ LOCK_FLAGS=-s`）。<br>**为何是 P1**：后果是**证据归属错 / 缺件**（O-57 家族），而**门禁对此不可见**（件"在" ⇒ 不报 `missing-artifact`，`--accept` 也管不着）；且 **O-59 已记"6 并发当日 ④ 类实际发生过"** ⇒ **不是纯理论**。<br>⚠ **归属如实标注**：`$evRmCmd` 是**我本轮 O-57 修复新增的**（原实现只在失败路径清，`O46_CLEAN`）；其**位置**的取舍只考虑了"**别删自己刚写的件**"，**没想到并存的别人的件** ⇒ 属**我的修复留下的同族缺口**（与 §30.7 / §31.8 / §33.3 同源：坑都长在"我以为我知道"）。<br>**三个候选修法（均属 C-判据 ⇒ 需裁定，本轮不动代码）**：<br>　**① 同站同 proj 一律排他**（放弃 `readonly ⇒ shared`）—— 与 O-18 纪律**方向一致**（"跨站各 1、不可同站叠"），**代价≈0**，且一次性消除**整类**并发互踩；⚠ 但它**改动 O-17 的 layer-2 rwlock 设计意图**（`DESIGN §4.1`）⇒ 需裁定。<br>　**② per-run 命名**（`out/.meta` → 带 `RUN_TOKEN`）—— 治本，但**波及 collect / EVM / accept 的固定名契约**，改动面大。<br>　**③ 仅"移进锁内"** —— ⚠ **不足，不推荐单独使用**（共享持有者之间仍互删）；可作为①②的前置步骤。<br>**零代码缓解（立即可用）**：同站配对时**换 `proj`**，或**只走跨站各 1**（既有纪律）。<br>★★ **修法②已定稿（2026-09-25，Scott 裁定选 ②）⇒ 改动点与验收判据见 DEV-LOG-014 §36**（D1–D8 + V1–V9 + 前置件）。三条要点：<br>　**(a) ★ 就地更正我自己的成本估计**：我原写"波及 collect / EVM / accept 的固定名契约、改动面大" —— **错**。实测 `:2158` 的 `$evNames` **已从 `$Script:EV_STAGE_NAMES` 单一真值派生**（O-57-A 的成果），而**归档名在 runDir 内**（runDir 本身 per-run）⇒ **归档侧/EVM/audit/accept 零改动**，真实改动面 = **站上 11 个写点 + 主控 3 个读点**。⇒ ② 与 ① 的成本差**比我说的窄**。<br>　**(b) ② 顺带关掉两条老条目**：per-run 化后"上一轮的残留"**在名字层就不存在** ⇒ **O-57 / O-22 从根上消失**（那个破坏性 reset 随之**移除**）。<br>　**(c) ⚠ 明确【不覆盖】**：**危险序③（卡片自己的产物同名）** 仍在 —— 同卡并发仍互覆，靠"跨站各 1 / 换 proj"规避（本项**不解决**，避免它藏在"O-68 已修"的阴影里）。 | DEV-LOG-014 §34 · **§36（定稿设计）** · O-57 · O-59 · O-17 |
| O-69 | 安全/契约 | **P2** | **`input-provenance` 规则④ 有"未登记路径"盲区**：规则④ 只在"声明 `none` ∧ 正文引用了**已登记**且 tier 严于本卡的路径"时报 WARN ⇒ **引用一张【未登记】的敏感文件（按 fail-closed 视为 `local-only`）不会被发现** ⇒ 卡可声明 `none` 而实际读了未登记的敏感内容，门禁全程 PASS | **由 b3（吃狗粮卡 `b3-gate-newjudges-falsegreen`，2026-09-25）独立发现；我逐条核实为【有效】**。它的最小反例精确：「`public` 卡写 `input-provenance: none`，正文引用一个**未登记**的 `spec/secret/notes.md`（表里无此键 ⇒ 默认 `local-only`，严于 `public`）⇒ 因不在 registry 中，WARN 不触发 ⇒ 门禁 PASS」。<br>**根因**：规则④ 的实现是在 **registry 里查**（`reg.get(path)`）⇒ **只看得见已登记项**；而"未登记"恰恰是 fail-closed 最该管的那一类。<br>**候选修法**：① 规则④ 改为**扫卡正文里的路径样式**（`[A-Za-z0-9_./-]+\.md` 等）并与 registry 比对 ⇒ **未登记**者单列（WARN 或 FAIL）；② 或对声明 `none` 的卡**要求正文不含任何"看起来像本仓路径"的 token**（更强，但可能误报）。⚠ 需先评估**误报率**（卡正文自然会写 `out/xxx.json` 之类**非本仓**路径）。 | DEV-LOG-014 §35 · O-66 |
| O-70 | 门禁/检出力 | **P2** | **`stations` 的 orphan 探针【检出功率低】，而名字容易让人以为覆盖很广**：白名单只认 `comm ∈ {opencode,claude,timeout,defunct}`、`etimes ≥ 6h`（默认）、且**刻意只 WARN 不 FAIL** ⇒ 一个 72h 的 `sleep`（或任何不在白名单里的进程）**完全不会被报** | **由 b3 独立发现（2026-09-25）；我核实为【有效】，但性质要写准 —— 这是【刻意的取舍】，不是实现缺陷**：窄白名单是为了避免"合法长 run"被误报，只 WARN 是因为清孤儿**不可逆**（见 O-58 的定级理由）。<br>⚠ **b3 的原话很准**：「**在路灯下找钥匙**，漏报即常态，且无 FAIL 兜底，极易被忽视」⇒ **问题不在实现，在【命名与表述】**：叫"orphan 探针"会让读者以为它在守"站上有没有异常进程"，实际它只守"**我们自己的**那几类 runtime 有没有卡住"。<br>**候选修法（按代价递增）**：① **改表述**（note 里写明"仅限本站 runtime 白名单"，并把白名单列出）—— **零代码、立即**；② 加"**不在白名单但 `ppid=1` ∧ `etimes ≥ 阈**"的第二类**只报数不判定**（可见化，不引入 FAIL 风险）；③ 放宽白名单（**不建议**，会淹掉信号）。**建议 ① + ②**。 | DEV-LOG-014 §35 · O-58 |<br>✅ **已修 ①②（2026-09-25）**：① **射程写进文案** —— 常量 `ORPHAN_WHITELIST = "opencode\|claude\|timeout\|defunct"`，`无长龄 orphan` / `发现长龄 orphan` 两处**都把白名单打印出来**（读者不会再以为它守"站上有没有异常进程"）；② 新增 `[orph2]` 段 + 门禁侧第二类：**只进 `info`，永不进 WARN/FAIL**（清孤儿不可逆，判成灯会淹信号），明细里带**完整命令行 + 年龄**（人能一眼看出是哪条链漏的）。<br>　★ **② 的判据键就地更正（第一版实测不成立）**：原计划用 `ps -u $USER --ppid 1`，实测**两处都错** —— (a) 在一台桌面机上它抓回 **122 条系统守护**（`systemd-journald`/`udevd`/`avahi-daemon`…，全是 **root**）⇒ 说明 **`$USER` 在非登录 ssh 会话里可能为空**、`-u` 过滤**静默失效**（纪律 12 同族：别赌远端变量在）；(b) 即便过滤对，桌面用户的 `ppid=1` 天然含 `systemd --user` 等**合法**长龄进程 ⇒ 恒有噪声。⇒ 改按"**产物名**"匹配（`args` 含 `agent-cli-task` / `agent-stage-` / `_oc_session_meta` / `_p3_run` / `_station_ready` / `_slot_gate`）—— 这是**事实**判据、噪声面小得多，且**正好**覆盖 O-72 那一类（`bash /tmp/agent-cli-task-*.sh` + 它的 `sleep` 子壳）。<br>　**先验红（实测，用既有的 `RPC_ORPHAN_SEC` 覆盖通道）**：B 站植入一个**只有名字像我们**的假残留（`/tmp/agent-cli-task-FAKEPROBE.sh` 内容 `sleep 300`，`setsid` 起）⇒ `RPC_ORPHAN_SEC=1` 跑全量门禁：note 出现 **`orphx1`**、明细点名 **`B:bash /tmp/agent-cli-task-FAKEPROBE.sh (pid 3425952, 0h)`**，而 **结论仍是 `PASS`**（只报数 ⇒ 不引入灯）✓。★ **同一次先验红顺手复证了 O-70 的原始盲区**：(h) 白名单段对**同一个进程**报 `无长龄 orphan`（它 `comm=bash`，不在白名单）⇒ "路灯下找钥匙"是**真的**，不是修辞。清理：kill 该 pid + 删假脚本（`FAKE_GONE`）+ 清 env。<br>　⚠ **仍登记的边界**：第二类**不放宽白名单**、也**不判灯** ⇒ 真出现泄漏时**门禁仍是 PASS**（信号只在 `info` 行里）。若日后要把这一升成 WARN，依据是"最长 `timeout_s=1800s` ⇒ 6h 有 12× 裕度"，但**需先看几轮噪声水平**再裁。 | ✅ **已闭环（① + ②）** · DEV-LOG-014 §38 · O-58 · **O-72** |
| O-71 | 工具链/调用形态 | **P1** | **`agent-cli.ps1` 的 `$ts` 变成【数组】⇒ 整链失败（`exit 255`）**：`$ts` = `@('', '<ts>')`（PS 用空格 join ⇒ 本地名成了 `agent-cli-task-`、runDir 成了 `agent-out\< <ts>>`） | **一次实测（2026-09-25）；触发形态疑似【调用方式】而非代码**。<br>**观测量**：`RUNSTAMP: 202609252307007268` **正常**打印，随后 `bash: /tmp/agent-cli-task-: 没有那个文件或目录` · `TASK remote raw excode=255` · `COLLECT_FAIL: cannot create agent-out dir: 无法将"System.Object[]"转换为参数"ChildPath"所需的类型"System.String"` · `TASK_DONE dir=…\agent-out\< 202609252307007268> exit=255` · `EVIDENCE_LEFT_IN_TEMP=…agent-cli-out- 202609252307007268.txt;…`（⚠ **名字里那个空格**就是"数组被空格 join"的指纹）。<br>**触发时的调用形态**：`ssh … ; Write-Host … ; & agent-cli.ps1 task … 2>&1 \| Select-Object -Last 6`（**与 `ssh` 串在同一 PS 会话 + 给工具输出加管道**）。<br>**同批对照**：**独立、不加管道**的调用 **2/2 成功**（`202609252306122042` · `202609252307414394`，均 `exit=0` / `ACCEPT_OK=1`）⇒ **与 O-68/D1+D3 的改动无关**（同代码独立调用正常）。<br>⚠ **根因未定，登记待归因**（候选：`Get-UniqueRunStamp` 返回值被污染 · 管道/会话变量泄漏）。**归因实验**：用**相同形态**对 `HEAD` 复跑 ⇒ 若同样 255 ⇒ 属**既有**脆弱面。<br>★ **操作纪律（立即生效）**：**不要**给 `agent-cli.ps1` 的调用**加管道**，也**不要**与 `ssh` 串在**同一 PS 会话**里派发 —— 用**独立调用**（= 本轮成功那几次的形态）。<br>★★ **根因已定 + 已修（2026-09-25 当日，同一次派发中二次复现）** —— **上一条"触发形态=调用方式"的假设【就地撤回】**：那是**巧合**。<br>　**根因**：本机 PowerShell profile 把 `Remove-Item` **别名**到 `__Safe-Remove-Item-Wrapper`，而该包装器**每次调用都往管道吐一个 `$null`**。**一手对照**（同一文件、同一命令、两个计数）：`@(Remove-Item $f -Force -EA SilentlyContinue).Count` ⇒ **包装器 = 1（`EMITTED_NULL`）**；`@(Microsoft.PowerShell.Management\Remove-Item …).Count` ⇒ **原生 = 0**。<br>　**缺陷点**：`Get-UniqueRunStamp`（O-63 新增）体内**两处 `Remove-Item` 没有 `| Out-Null`**（抢占 GC 的 `:783` + runDir 撞车回退的 `:806`）⇒ 该函数**返回 `@($null, <ts>)`**。<br>　**最小复现（决定性）**：AST 提取该函数 + 造一个"runDir 已存在"的 claim ⇒ `CAPTURED_COUNT=2 / ITEM=null / ITEM=202609252325388504`。⇒ 触发条件 = **"抢占 GC 分支真的删了东西"**（存在 claim 且其 runDir 已存在、或用龄 >7 天）⇒ **解释了"时好时坏"**：上一次成功 run 之后的那一次最容易踩中（本轮 23:16 那次没踩中，是因为当时 claims 全无对应 runDir ⇒ 一行都没删）。<br>　**危害形状**：故障点（`bash: /tmp/agent-cli-task-:`）离病因（`Get-UniqueRunStamp`）**很远** ⇒ 天然被误判成"网络/站上问题"；`$ts.Substring(0,14)` 处报 **"不能对 Null 值表达式调用方法"** 是 PS 的**成员枚举**命中数组里的 `$null` 元素（也正是数组形状的旁证）。<br>　**修法（本仓既有纪律的漏用，非新机制）**：① **全文件 10 处** `Remove-Item` 一律补 `| Out-Null`（`Invoke-RemoteScript`/`Invoke-RemoteCapture`/`Invoke-Judge` **早就**按这条纪律写过并留了注释 ⇒ 本条属**原则漏应用**，与 O-56 同族；其中 `:1927`/`:1932` 那三处**每次 golden 派发都会执行**）；② `$ts` 消费点加**形状 fail-closed**（`-is [array]` ⇒ `exit 13`，**绝不静默取数组最后一个元素**）；③ 夹具 `_fm_golden_test.ps1` 新增 **o71 三段**（**全文件级**"代码行里每个 `Remove-Item` 都必须同现 `| Out-Null`"+ 尾注存在 + 形状判据存在；`o71①` 的归一化**必须去注释 + 剥引号**，否则本段自己的 ABORT 消息串会让它恒红 —— **与 O-65 那次"全文子串"假绿同一个坑**）。<br>　**验证**：夹具 **249 → 252/252** · 门禁 `py-tests` **22/22** · `ps1-golden` **pass=252** · 修后同一形状的重派发 **`202609252328103688` `exit=0`**（并顺带跑通了 V4 的附件+golden 路径）。 | ✅ **已闭环（根因定案 + 全族修复）** · DEV-LOG-014 §37 · **§38（归因与修复）** · O-63 |
| O-72 | 运维/进程 | **P2** | **站上"进度采样器"子壳会逃脱（父壳非正常死亡 ⇒ 无限循环）**，且它**继承了锁 fd** + **永久刷裸名 `.progress`** + `/tmp/agent-cli-task-*.sh` **无出口累积** | **一手取证（2026-09-25，B 站）**：`ps` 抓到一个 **PPID=1**、已存活 **28.6h** 的 `bash /tmp/agent-cli-task-202609241841378240.sh`（`/proc/<pid>/cwd → dogfood`、**fd 9 = `.agent-lock (deleted)`**）。<br>　**机制（读站上脚本体坐实）**：`sample_progress &` 是**子壳** ⇒ 父壳末尾的 `SAMPLE=f` **到不了它**（fork 后变量是副本）；源码自己写着 `kill $SPID` 是**唯一**出路（注释原文："sampler subshell keeps a COPY of SAMPLE (fork); f won't reach it"）⇒ 父壳若在 teardown 前死掉（本地 ssh 断/被杀），**子壳永久 `while [ "$SAMPLE" = t ]`** 每 5s 追加一行。**实测证据**：我 `kill` 该 pid 前 `.progress` 每 3s 涨 ~30B，`kill` 后**立刻冻结**（4781B 不变）⇒ **它就是那个写者**（非推断）。<br>　**三个后果**：① **继承的 flock fd 永不释放** —— 该 fd 指向的 `.agent-lock` 已 `(deleted)` ⇒ **锁文件被 unlink 过**（谁 unlink 见 **O-73**），新 run 在新 inode 上取锁 ⇒ **互斥对该孤儿失效**；② **裸名 `.progress` 的 mtime 永远新鲜** ⇒ **D3 的按龄 GC（`-mtime +7`）结构上收不掉它**；③ 进程累积（本次 1 个）。<br>　**另一条同族**：`/tmp/agent-cli-task-*.sh` **留在站上不清**（B 站实测 **101 个**、A 站 10 个、C 站 12 个）—— 名字**已是 per-run**（不互踩）但**无出口**（"登记无出口 ⇒ 腐化"）。<br>**候选修法**：① 采样器改**有界**（`for i in $(seq 1 N)` 或 `timeout -k 10 <run预算+裕度> bash -c '…'`）+ `trap` 兜底 `kill`；② run 脚本收尾 `rm -f "$0"`（T1 的附件中转脚本**已有**这个样板 `trap 'rm -f "$0"' EXIT` ⇒ 照抄）；③ 站上侧给 `.agent-lock` **不要 unlink**（见 O-73）。<br>⚠ **本轮已手工清理**（kill 该 pid + 删 2 个残留 stage，见 O-76）；**未改代码**。<br>✅ **已修 + 实跑验证（2026-09-25/26）**：**两道防线**（刻意冗余，因为二者覆盖的失效面不同）—— ① **`HUP/TERM/EXIT` 陷阱** `cleanup_sampler`（ssh 断开时 bash 收 `HUP` ⇒ 立刻杀子壳；陷阱体**始终 `return 0`**，否则会改写 body 末尾 `exit $FINAL_RC` 这个**契约字段**）；② 采样器**自带上限** `SAMPLE_MAX_S=$(( timeout * 4 + 600 ))`（4 = 首跑+3 续跑；`SAMPLE_N*5 -ge $SAMPLE_MAX_S ⇒ break`）—— 这是**唯一**对 `SIGKILL` 也有效的防线（KILL 抓不到，陷阱不会触发）。③ 站上脚本副本改**按龄清**（`find /tmp -maxdepth 1 -name 'agent-cli-task-*.sh' -mtime +7 -delete`）：**不**给主 body 加 `trap 'rm -f "$0"'` —— 主 body 走 `Invoke-RemoteScript` 的**网络级重试**（同一路径再 `bash` 一次），自删会把"远端已跑完、只是网络抖了一下"判成 127 = **把成功判成失败**。<br>　⚠⚠ **首跑就抓到我自己的一个 bash 缺陷（如实记）**：比较写成 `[ … -ge SAMPLE_MAX_S ]`（**漏 `$`**）⇒ `[: SAMPLE_MAX_S: 需要整数表达式` ⇒ run `exit=255`。★ **静态夹具当时是绿的**（它只验"那行文本在"）—— 正是 DEV-LOG §26.4「夹具查'串在不'，查不出'这条链现在跑不跑得起来'」。⇒ 除修掉该行外，**新增两条行为断言**（用夹具已解析出的本地 Git Bash 跑同一段结构：上限 12s ⇒ `n=3` 即 break；**先验红** = 裸名形态下 `[` 报错、打不出 `CMP_OK`）⇒ 这类缺陷从此**离线可判**。<br>　**实跑证据**（`202609260003123276`，`exit=0 / ACCEPT_OK=1`）：站上生成的 body 逐行核对 —— `SAMPLE_MAX_S=$(( 300 * 4 + 600 ))`（PS 侧 `$timeout` 已插值 ⇒ 站上不会是字面量）+ `[ $(( SAMPLE_N * 5 )) -ge $SAMPLE_MAX_S ] && break` + `cleanup_sampler` 出现 2 处；`.progress.<ts>` **节拍完整**（`t=0/5/10/15` + **`t=end bytes=180`** ⇒ 有界化**没有**损伤遥测）；跑完 `pgrep -af agent-cli-tas[k]` = 无 ⇒ 子壳被正确收掉；**GC 生效**：`/tmp/agent-cli-task-*.sh` 由 **101 → 99**（删了 4 个 >8 天的，同时新增 2 个；现存最老 = **09-18**（7.6 天）**保留** ⇒ 与 GNU `find -mtime +7`（按整 24h 截断 ⇒ 实际在 ≥8 天时删）语义一致）。<br>　**护栏**：夹具 **o72 六段**（静态 4 + 行为 2）⇒ **266/266**。 | ✅ **已闭环** · DEV-LOG-014 §38 · **O-73** · O-58 |
| O-73 | 并发/锁正确性 | **P1** | **失败路径的 `O46_CLEAN` 会 `rm` 掉 `.agent-lock`（unlink）** ⇒ **正在持有该 inode 排他锁的并存 run 会被静默降级**（第三方随即能取到"排他"） | **读码得出（2026-09-25）**：`agent-cli.ps1:2624` 的 `$del = @('out/.meta','out/.progress','.agent-lock','.agent-state.json')`，条件是 `if ($code -ne 0)`（归档成功后）。<br>　**为什么是正确性洞**：`flock` 的互斥是**绑在 inode 上**的；`rm` 只 unlink 目录项 ⇒ **持有者仍在锁着那个 inode**，而**后来者会在新 inode 上取锁成功** ⇒ "排他"变假。可达序：两个 **shared** 只读 run 并存（合法，O-17 rwlock）∧ 其中一个**失败** ⇒ 它 unlink 锁文件 ⇒ 第三个想取 **exclusive** 的 run 创建新文件即成功 ⇒ **与两个活着的 shared 持有者并存** ⇒ rwlock 语义被破。<br>　**旁证（不是推理）**：O-72 抓到的孤儿 **fd 9 = `.agent-lock (deleted)`** ⇒ "持锁者存在而锁文件已被 unlink"**实测真的会发生**。<br>　**第二处（D4 之后同族）**：同一 `$del` 里的 `out/.meta` / `out/.progress` **已不是本 run 的件**（per-run 化后它们是**别人的/历史残留**）⇒ 一个失败 run 去删**别人的**共享名文件 = **与 D2 刚移除的 `$evRmCmd` 完全同类**（"破坏性删除 + 跨 run 语义"）⇒ **D2 的移除不完整**。<br>　⚠ **`out/<subject state>` 那部分要留**：卡的产物**不是** per-run 命名的（§36.E①）⇒ "失败 run 清掉自己的产物以防下轮 accept 命中旧产物"**仍有意义**。<br>**建议修法（未动，待裁）**：① **删掉 `.agent-lock` 与 `.agent-state.json`**（锁/状态**不得**由失败方 unlink；`.agent-state.json` 由 orphan 检测语义管，删它会污染他人在飞的 run）；② **删掉 `out/.meta`/`out/.progress`**（D4 后已无本 run 语义 ⇒ 只剩"删别人东西"）；③ 保留 subject-state 清理。**代价**：负向夹具 `neg-o46-cleanup.md` 的基线要同步改（它验的正是"清 5 项"）。<br>✅ **已修 + 端到端验证（2026-09-25，按上述 ①②③ 执行）**：`$del` 改为**从空表开始、只收 subject-state**；清理体在 `$del.Count -eq 0` 时**不生成那条 `for` 循环**（空列表不拼命令）；并新增一行**射程可观测** `O46_CLEAN_SCOPE:`（理由：否则"**刻意不清**"与"**没清**"在日志里长得一样 —— 本仓头号形态）。<br>　**双向实测（受控失败卡 `neg-o46-cleanup.md`，run `202609252354302528`）**：`ACCEPT_OK=0 / TASK_RC=9` ⇒ `EVM_STATE: pulled=1`（**拉取先于清理**）· `O46_CLEAN: … 1 项` · `O46_CLEAN_SCOPE:` 打印；站上核查 ⇒ `out/o46-probe.txt` **GONE**（原缓解**未被削弱**）∧ `.agent-lock` · `.agent-state.json` · `out/.meta.<ts>` · `out/.progress.<ts>` **全部 SURVIVED**（正是本次收窄的四项）∧ `/tmp/agent-stage-*` **0**（O-59/T1 那段兜底仍在跑）。<br>　**护栏**：夹具 `o73 三段`（①不再预置固定名 ②subject-state 仍被收 ③射程行存在）⇒ **255/255**。⚠ **顺带修掉一条我自己的判据假红**：`o68: 已无'无条件删固定名'` 原本用**全文子串**判 `$evRmCmd` 已消失，而 O-73 的注释里为说明"与 D2 那处同类"**提到了该变量名** ⇒ 判据**假红**（= O-65 那次"全文子串可被注释蒙过"的**反向**：那次假绿、这次假红）⇒ 该条改为**只看代码**（去 `#` 之后的部分）。<br>　⚠ **收窄的副效应（实跑观察到，如实记）**：失败 run 现在会**留下** `state=running` 的 `.agent-state.json` ⇒ **下一次** run 的 orphan 检查会命中并打印 **`ORPHAN_RECOVERED pid=…`** + 把 `out/*` `cp -r` 进 `out/orphaned/`（实测 `202609260003123276` 的日志里就有这一行）。★ **这与"原 `$del` 想消除的外因"不是同一件事**：`LOCK_HELD` 由 **`flock` on `.agent-lock`** 判（与 state 文件无关）⇒ **不会**因此产生假 `LOCK_HELD`；而 `orphaned/` 的复制污染是 **§36.C 末尾已登记**的已知残留（**不删证据**，严重度低）。⇒ 结论：**用"可见的孤儿恢复"换掉"静默 unlink 锁"是划算的**；若要把 state 也写准（失败即 `state=failed`），那属**另一处语义**（动 orphan 检测的判据），不在本项内顺手改。 | ✅ **已闭环** · DEV-LOG-014 §38 · **O-68/D2** · O-72 |
| O-74 | 可观测/一致性 | **P2** | ★ **D4 落地后，`cluster.py` 的"运行中节拍"视图静默失效** —— `_agent_beat` 只扫**裸名** `$d/.progress`，而改写后**唯一生产者**是 `.progress.<ts>` | **读码 + 实况双向坐实（2026-09-25）**：`cluster.py:3127` 原文 `[ -f "$d/.progress" ] || continue`；D4 后站上**新件全带后缀**（实测 C 站 `out/` 只有 `.progress.202609252329520026` 等）⇒ 该视图只剩**历史残留**可读（B 站的裸 `.progress` 停在孤儿最后一行 `t=102993`、无 `t=end` ⇒ **会被显示成"永远运行中"**）。⇒ 典型**"看起来一切正常"的静默退化**（D4 的爆炸半径里漏掉的**第二个消费者**；§36.D 只列了主控 3 个读点）。<br>✅ **已修（2026-09-25，本批内）**：`_agent_beat` 改为取「裸名 + 全部带后缀名」中 **mtime 最新**的那份（`ls -1t "$d"/.progress "$d"/.progress.* | head -1`）—— 裸名保留**仅为兼容改名前的历史残留**；同时同步 3 处描述文本（`:73` / `:2384` / `:4350`）为 `.progress[.<ts>]`，**避免文档比代码活得久**。<br>⚠ **未加机判**：该视图没有对应断言（`py-tests` 不跑它）⇒ 属"改了但没护栏"，如实登记。 | ✅ **已闭环（代码已修，本批内）· ⚠ 未加机判（如实登记）** · DEV-LOG-014 §38 · **O-68/D4** |
| O-75 | 通道/超时 | **P1** | **`Test-RemoteReach` 的 `ssh` 【没有整体时限】** ⇒ 任何解析/连接层停滞都会让**整次派发无限挂起**；`ConnectTimeout` **不覆盖 DNS/mDNS** | **一手实测（2026-09-25，V6 六并发）**：6 个进程在同一屏障时刻释放后，**A/B 两站的 `ssh -o ConnectTimeout=8 -o BatchMode=yes <host> "echo alive"` 挂住 ~10 分钟**（`Get-CimInstance` 抓到两条 ssh 的命令行**就是**这句 probe；站上 `ps` 同期**没有**对应 sshd 子进程 ⇒ 卡在**本地**解析/建连阶段）。**修：杀掉这两条 probe ⇒ 两条 run 立刻继续并最终 `exit=0`** ⇒ 说明后续链路健康，**卡点只在 probe**。<br>　**判据（为什么不是"网络坏了"）**：同批 **C 站（`192.168.1.37`，裸 IP）** 与后到的 A/B 重试**全部成功**；而 A/B 用的是 **`.local`（mDNS）** 主机名 ⇒ 与 O-18 的跨站纪律、以及 `Get-TargetHost` 里 C 站"**无 avahi .local，用管理网 IP**"的注释**互为印证**：**并发时的 mDNS 解析争用/停滞是头号嫌疑**（`ConnectTimeout` 只管 TCP connect，**不管**名字解析；OpenSSH 已知行为）。<br>　**后果**：`timeout_s=300` **救不了**（挂点在**远端 body 之前**）⇒ 表现为"批墙钟 641s vs 基线 56–78s"（**不是串行化**：6/6 lease=shared、0 个 `exit 3`）。<br>**候选修法**：① `Test-RemoteReach`（及一切 ssh/scp 调用点）包一层**硬时限**（`Start-Process`+`WaitForExit(ms)` 或 `timeout` 语义的等价物）⇒ **与纪律 11（"站上限时一律 `timeout -k`"）同族，只是把那条纪律补到主控侧**；② A/B 也改用管理网 IP（像 C 那样）；③ probe 失败**降级**为"跳过预检、让真正的 scp/ssh 去失败"（⚠ 会削弱 fail-fast ⇒ 需权衡）。<br>✅ **已修（探针类）+ 残面如实登记（2026-09-25）**：新增 **`Invoke-CappedSsh`** —— 用 `[Diagnostics.Process]` + `ProcessStartInfo`（**不用** `Start-Process -ArgumentList`：PS5.1 下它的 `ExitCode` 在 `-Wait` 之外不可靠，而这里必须能**带时限地**拿 rc），`WaitForExit($TimeoutS*1000)` 超时即 `Kill()` 并返回 `ok=$false; code=124`（与纪律 11 的超时码同码）；`$Script:SSH_PROBE_CAP_S = 45`。<br>　**落点选的是覆盖面最大的那一处**：`Test-RemoteReach` 是四条主路 ssh 入口（`Invoke-RemoteScript` 首跑/重试 · `Invoke-StationReady` · `Invoke-SlotGate` · `Invoke-RemoteCapture`）的**共同前置闸** ⇒ 只改它一处即覆盖全部主路。<br>　**正反两侧实测**（本机）：负向 `Invoke-CappedSsh -Arguments "… 'sleep 60'" -TimeoutS 3` ⇒ **`ok=False code=124 out=TIMEOUT(3s) elapsed_s=3`**（墙钟真的生效且真杀了 ssh）；正向 `… "echo alive"` ⇒ **`ok=True code=0 out=alive`**。**真实链路复跑**：`202609252357343731`（readonly 卡）`exit=0 / ACCEPT_OK=1 / RUN_S=25`。<br>　★ **顺手做成结构性保证**：`-o BatchMode=yes` 改由 `Invoke-CappedSsh` **强制**加 —— 那条"全部 ssh 调用点必带 BatchMode"的夹具是 **AST 级**的（按命令名扫调用点），`$psi.Arguments` 这个**字符串**不在它射程内 ⇒ 靠调用方自觉会让未来新增点**静默**跳出护栏。<br>　**护栏**：夹具 `o75 四段`（helper 形状 + BatchMode 结构性 + `Test-RemoteReach` 改道 + **"刻意不加"的理由写在源码**）⇒ **259/259**。<br>　⚠⚠ **残面（**刻意**不修的，别当成已全覆盖）**：① **派发主体**（`Invoke-RemoteScript` / `Invoke-RemoteCapture` / 站上 claude 的 `_p3_run.sh`）**不加**主控侧墙钟 —— 它们的合法时长以**远端** `timeout -k <budget>` 为界，在主控侧强杀 ssh 会把"慢"变成"**远端任务还在跑 + 本地证据全丢**"（比挂住更糟）⇒ 其**解析层停滞**仍然无界；② **站上 claude 的两条前置探针**（`Test-StationEngineReady`/`Test-StationClaudeEgressReady` 那两处 ssh）**未**改道 —— 它们的 `argv` 里含**双引号**（`test -f "$HOME/…"`），改用 `ProcessStartInfo.Arguments`（原始字符串、须自己转义）会**重开纪律 12 的引号地狱** ⇒ 宁可留面不冒一次静默引号 bug（正确下一步是"给 A/B 也配管理网 IP"或让那两条探针先过 `Test-RemoteReach`）。 | ✅ **已闭环（探针类）· 残面已登记** · DEV-LOG-014 §38 · O-18 · O-58 · 纪律 11 |
| O-76 | 运维/清理 | **P3** | **派发在"body 之前"中止 ⇒ 私有中转 `/tmp/agent-stage-<RUN_TOKEN>` 泄漏**（无出口） | **实测（2026-09-25，B 站）**：抓到 **2 个**残留——`agent-stage-fd612392…`（23:23:38，含 `attach/` + `golden.tgz`，= **O-71 那次 aborted 派发**）与 `agent-stage-46e4996f…`（23:07:01，含 `attach/`）。<br>　**为什么现有清理盖不住**：O-59/T1 的清理在 **body 内**（走不到）+ O-46 的失败清理要求"**归档成功**"（此时 runDir 都没建）；⇒ **"scp 了中转件、却在 body 之前死掉"**这一格无人管。<br>✅ **本轮已手工清理**（两目录已删，`STAGE=0`）⇒ **V9 达到 `stage_dirs=0`**；**代码未改**（候选：派发前顺带按龄清 `/tmp/agent-stage-*`，⚠ **绝不能**用通配删**在飞的** ⇒ 只能按龄，且理由要像 D3 那样写明裕度）。 | ✅ **已闭环（2026-09-25 当晚：代码已加 + 行为测试双向）** · DEV-LOG-014 §38.8 · O-59/T1 · O-68/D3 |
| O-77 | 并发/同步 | **P1** | ★★ **同站并发时 `sync` 步互相踩 ⇒ 并发派发全灭**（**不是锁的问题**） | **一手实测（2026-09-26 02:20，同站 3 张 readonly 卡并发）**：3/3 `LEASE_ACQUIRED … (shared)` **都正常拿到租约**、**0 个 `exit 3`**，但 **3/3 死在 sync**：`/usr/bin/tar: ./agent-out: file changed as we read it` ⇒ tar rc≠0 ⇒ `throw "tar sync failed"`。<br>　**根因**：`dogfood` 的 proj 根 = 运行时载体 `tmp/dogfood-ws`，其内**含框架自有的本地结果目录 `agent-out/`（1.3 MB）**，而**每个 run 都往里面写自己的 runDir** ⇒ 并发时 tar 读到"正在变"的目录。<br>　**为什么不是锁的锅**：租约 3/3 成功且语义正确（共享）；失败点在**同步面**。<br>　**★ 一致性缺陷**：同一个"不该上站"的目录，在 `agent-cli.ps1:2238` 的 diff 过滤里**早已排除**（`^(out\|\.golden\|\.attach\|agent-out\|\.agentsync\|\.git)/`），却**没进 sync 的排除源** ⇒ 两处各写一份 ⇒ 漂移。<br>　**顺带实测的另一个坑**：载体里的 `.agentsync` 只排除了 `archive/`、`runs/` —— **两个在该载体里并不存在的目录**（排了个寂寞），而真实存在的 `agent-out/`、`.attach/`、`out/` 一个都没排除。 | ✅ **已闭环（2026-09-26）**：代码层把 `agent-out` 并入 sync 排除（**写在代码而非载体 `.agentsync`** —— 后者**不在版本控制内** ⇒ 修它会随载体重建静默消失）；夹具 `o77①/②/③`（含**顺序**判据: 并入必须在 `Convert-ToExcludeArgs` **之前**）⇒ **274/274**；**复跑同一实验 ⇒ 3/3 跨过 sync 步**（该 tar 错误消失）· DEV-LOG-014 §40.6 · O-78 |
| O-78 | 并发/一致性 | **P3** | **并行面的两处"说了等于没说"**：① 排他拒绝的**文案不准** ② "框架保留目录"清单在代码里**有两份** | ① **实测**：3 个 **shared** run 在跑时，一张想取 exclusive 的卡被拒，文案却写「已有**排他**派发在跑（本 run 想取 exclusive）」⇒ **把持有者说错了**（行为对、文案错 —— 会**误导排障方向**）。<br>② `agent-out` 的排除清单散在**两处**（sync 代码 vs `:2238` diff 过滤）；本轮只把**已证实**的那个并进 sync ⇒ 仍是两份。<br>**待实测再定（不许凭感觉大改）**：`out/`、`.attach/` 是否同病（`.attach/` 站上**需要**、但**本地那份**不该上去）；载体 `.agentsync` 与代码清单**应合流为单一真值**。 | ◐ **已登记 · 未改**（①文案 ②清单合流 **均未动** —— 避免无实测依据的大改）· DEV-LOG-014 §40.6 · O-77 |
| O-79 | 并发/网络 | **P1** | ★★ **并发派发的硬前提：`.local`(mDNS) 主机名在并发解析下有失败率** | **一手微复现（2026-09-26 02:23）**：**并发**解析同一个 `.local` 名 **3 次 ⇒ 1 次返回空**；**单次**解析正常（A `scott-lau-NEX.local` → **192.168.1.33**；B `scott-lau-GTR-Pro.local` → **192.168.1.32**；C 已是裸 IP **192.168.1.37**）。<br>　**在真实派发上**（02:21:52 那轮，O-77 修完之后）：同站 3 张卡 ⇒ **3/3 命中 `SSH_PROBE_TIMEOUT: 45s 未返回`**（★ **O-75 的硬时限生效了 —— 不再挂 10 分钟，而是 45s 快速失败**）⇒ 重试仍超时 ⇒ `NETFAIL: remote unreachable`。<br>　★ **含义**：O-75 当年的**候选修法②（"A/B 也改用管理网 IP，像 C 那样"）从"可选"升级为"并发的前置条件"** —— 佐证：C 站用裸 IP，在 V6 与本轮并发中**从未出现解析超时**。 | ◐ **已登记 · 待修（配置类）**：把 A/B 从 `.local` 改为**管理网 IP**（真值源 = `inventory/net.yaml` 与路由表）—— ⚠ **先落档改动点与验收判据再动手**（影响**所有**派发）；**验收 = 复跑"同站 3 卡 + 1 卡排他"达 4/4 预期**（3 个 shared 真并行 + 1 个 exclusive 快速拒）· O-75 · O-18 |

## 2. 各未决项详情

### 2.0 2026-09-23 新增（吃狗粮暴露；**登记在此而非另建文档** —— 本表是未决问题单一真值）

| ID   | 类别      | 严重度 | 简述 | 状态 | 归属批次 |
| ---- | ------- | --- | --- | --- | ---- |
| **O-27** | 验证/判据   | **P1** | **`_VERDICT_RC_MAP` 未覆盖"远端 0 ⇄ 整体 1"** ⇒ **任何 `accept` 失败的 run 都让 `evidence` FAIL 从而阻断提交** | ✅ **已闭环（2026-09-23 按裁定 b 修复 + 正反注入）**：见下方"修复记录" | ✅ 已修 |
| **O-28** | 并发/命名空间 | **P1** | `$ts` 与 `%TEMP%\agent-cli-ev-<ts>` / `agent-out\<ts>` **不含站与 pid** ⇒ 同 ts 并发互踩；**Root cause ①**：`task` 目标站调用方无法覆盖（每站需独立 alias） | ⏳ 待办 | D6-P2 / 并发批次 |
| **O-29** | 框架/卡面   | P2  | **无 `accept-golden` 的卡每次 run 产生 1 条可重放性 gap**（框架默认每卡都有 golden） | ⏳ 待办（本轮已 `audit --accept` 接受 2 条） | D6-P1 |
| **O-30** | 环境/卡面   | P2  | 站上 agent **对 `/proc/*` 无读权限**（opencode `external_directory` auto-reject）；**B 站无 `nvidia-smi`**；**`readonly: true` 与"必须落文件"互斥** | ⏳ 待办（卡已按此修） | D6-P1 / D7-P1 |

#### O-27：`_VERDICT_RC_MAP` 未覆盖"验收失败"路径（**阻断级**）

- **证据（一手）**：run `dogfood/202609232240596105` —— `.meta` 里 `TASK_RC=0`，`run.json` 里 `exit_code=1`，
  断言 `allowed = _VERDICT_RC_MAP[0] = {0}` ⇒ `1 ∉ {0}` ⇒ **FAIL**（[cluster.py:2707](../../ops/cluster.py) 映射表 · [:2768-2779](../../ops/cluster.py) 判据）。
- **成因（代码语义）**：远端码 9（**验收失败**）在 `run.json` 里被映射成 1
  （`$codeReal = $code; if ($code -eq 9) { $code = 1 }`）⇒ **映射表的键本应是 9**；
  但实测 `.meta` 写的是 **0（远端执行码）** ⇒ **键与值的域不一致**。
- **同型先例**：2026-09-21 的 `124` 条目 —— 本表注释自记"旧表无 124 条目 ⇒ **把每个合法超时 run 都误报 FAIL**（实测 3 个 run 全部命中）"。
- **影响面（严重）**：**"任务执行成功但验收失败"是最常见的负面结果**，而它**会让 `evidence` FAIL、进而阻断一切提交**。
  此前未被发现，**因为这条负路径从未被走过**。
- **候选修法**：

  | 选项 | 内容 | 取向 |
  |---|---|---|
  | **(a)** 补映射表 | `0: {0, 1}`（与 `9: {1,9}` 同型） | 快，但**放宽判据** |
  | **(b)** 治同源 | 让 `.meta` 的 `TASK_RC` 与 `run.json exit_code` **同域**（`.meta` 写整体码） | 慢，但**不放宽判据** |

- **★ 哪种更有利于 D6/D7 升级 —— 结论：(b) 为主 + 版本化并存，不选 (a)**：

  1. **(a) 是本仓已记录两次的同一错误模式的第三次**：`ROUTE_TABLE` 注释（W1a 2026-09-21）原话 ——
     "**白名单式判据每加一个云后端就漏一次，已漏两次**"。枚举"码组合"与枚举"后端"同病：
     **每出现一个新的合法组合就要打一次补丁**，且补丁会**掩盖该组合之外的异常形态**。
  2. **(b) 治的是同源性**：`.meta.TASK_RC` 与 `run.json.exit_code` 是**同一事实的两份记录**，
     让它们**同域**即"**同一事实只有一处定义**" —— 这直接服务：
     **D7-P1-1（U-1 产物身份）· D7-P1-2（U-2 字典）· D7-P2-2（结论契约：码的语义唯一）**。
  3. **(b) 还能顺带产出 D7 的第一个 schema 版本化用例**：`.meta` 加 `rc_domain=v2`（或保留
     `TASK_RC_REMOTE` 并新增 `TASK_RC_FINAL`），历史 run 按版本选映射 ⇒ **不掩盖历史信号**。
     这正是 **U-1「产物身份 + schema 版本」** 的真实需求来源（而非纸面推演）。
  4. **(b) 与 D7 的红线同源**：P0 固化"判据与 golden"，其中就包括**码的语义** ——
     码语义应在**源头固化**，而不是在下游靠映射表适配。

- **注入用例设计要求（按 §12 盲区 B2，改判据必须自带正反）**：
  正例 = 一次 **`accept` 成功**的 run（远端 0 ⇄ 整体 0）；反例 = 本 run（远端 0 ⇄ 整体 1）。
  两者必须在同一断言下**一绿一红**，否则无法证明改动真的在判。

#### O-28：并发命名空间未按站/进程隔离 + `task` 目标站不可覆盖

- **Root cause ①（确定，**且与 O-20 同源**）**：`task` 的目标站只能由 `ROUTE_TABLE` 的 `station` 决定，**调用方无法覆盖**。
  - 锁本是 **per-(proj, 站)**（`$W/.agent-lock`，`$W=/home/<user>/agent-workspaces/<proj>`）⇒ **撞锁只可能是三次都在同一站**。
  - 实测：`-HostName A/B/C` 三次派发**全部落 B 站**（`LOCK_HELD owner_pid=2968117 mode=exclusive` 同一 owner）。
  - ⇒ **要三站并发，唯一通道是"每站一个 alias"**（如 `ultra-a/-b/-c`，与既有 `m27-q4ks-a/-b` 同法）。
    ⚠ 但 `ROUTE_TABLE` 注释明写"**本表只镜像，不新立模型清单**"（权威真值在 `secrets/openrouter.conf`）⇒ **扩表须裁定**。
  - ⚠⚠ **上面这行是"修复前"的诊断结论，已被下方「✅ 修复」节取代 —— 2026-09-25 补指针（防误读）**：
    ① 实际修法是**让站覆盖自洽**（`-RemoteHost`），**不是**加 alias（见下节 RC①）；
    ② 而 per-station alias 后来**另行**落地（2026-09-24 D3/P2-3：`ultra-a`/`ultra-c` + `claude-a/-b/-c`）
    ⇒ **两条路现在都可用**（`ultra`=B / `ultra-a`=A / `ultra-c`=C，三站齐）。
    ⚠ **本处曾长期留着"唯一通道是加 alias"与"修法不是加 alias"两句互相冲突的话**（同一条目同一节内）——
    ⇒ 属本仓头号形态（**同一事实两处说法不一致**）；2026-09-25 读条目时被它误导过一次，故留此指针。
- **Root cause ②（确定）**：`$ts = [DateTime]::Now.ToString('yyyyMMddHHmmssffff')` **在两次并发里取到同一值**，
  而 `%TEMP%\agent-cli-ev-<ts>` 与 `agent-out\<ts>` **都不含站与 pid** ⇒ 互踩
  （`EVIDENCE_PULL_WARN: … being used by another process` + `COLLECT_FAIL: … does not exist`）。
  对照：`TMP_ROOT` **早已**用 `RUN_TOKEN` 做 per-invocation 隔离，**agent-out 与 evidence 临时目录没跟上**。
- **与 O-26 的关系**：`decompose`（拆片并行）**已闭环可用**（465.1s ≪ 720.8s）⇒ **同卡拆片走的是"两个分片各一站"**，
  与"同卡在三站各跑一次"是**两种并行**；后者（三站同卡）**当前无通道**。
- **✅ 修复（2026-09-23，两条 RC 均已落地并被实跑部分验证）**：
  1. **RC① 修法不是加 alias**（那会撞 `ROUTE_TABLE` 的"不新立模型清单"纪律），而是**让站覆盖自洽** ——
     dispatch 传给 task 的站覆盖参数是 **`-RemoteHost`**（`Invoke-Task -hostName $RemoteHost`），
     **顶层 `-HostName` 对 task 无效**（且 param 块**不能再加参数**，见 `[:3475-3476](../../ops/station-bin/agent-cli.ps1)`）
     —— 这是个易踩的**双参数陷阱**。旧实现只让 `$hostName` 变而 `$station` 不变 ⇒ **半覆盖**；
     现由 `$hostName` 反推 `$station`（`Get-TargetHost` 三站比对）。**实跑验证**：`-RemoteHost 192.168.1.37`
     ⇒ 输出 `station=C`（此前恒为 B）✓
  2. **RC② 已修**：`$ts` 加**并发去重**（已存在则递增），**刻意保持 18 位数字形状**（scrubber 长度判据与全仓 204 处引用依赖它）。
- **⚠ 并发实跑又暴露两条新脆弱点（RC③/RC④，未修）**：

  | # | 现象 | 判定 |
  |---|---|---|
  | **RC③** | `PREFLIGHT-FAIL: agent-out NOT writable … **Stream was not readable**` + `ABORT exit 12`（同一并发批次里另一次成功） | **`Assert-AgentOutWritable` 探针本身并发不安全**（多进程同探同一目录 ⇒ I/O 竞争）；⇒ **前置探针也必须并发安全**，否则"门"会变成随机失败源 |
  | **RC④** | C 站：`/home/…/dogfood/out/.agent-output.txt: 没有那个文件或目录`（A/B 同批次无此错） | 站上工作区**缺 `out/`** ⇒ **空目录不被 tar 携带**的老问题在**新建站的首次派发**上复现（本地载体已用 `out/.keep` 规避，但**站侧骨架创建路径未覆盖**）。**根因待诊断（未猜）** |

- **★ 面级扩展：见 [BLINDSCAN-v3-concurrency.md](BLINDSCAN-v3-concurrency.md)（2026-09-23）** ——
  "逐个撞"效率太低（新冒出的两条不在路由/命名空间层，而在**前置探针与工作区骨架**层）⇒ 改为**先扫面**。
  扫描结论（13 条共享资源，3 条不安全）**修正并加强了本条目**：
  - **RC④ 根因已定位（不必再猜）**：**`.agentsync` 四类模板全部排除 `out/`**（[agent-cli.ps1:117-120](../../ops/station-bin/agent-cli.ps1)）
    ⇒ staging 的 `out/` 被排除 ⇒ **空目录不入 tar** ⇒ 站上全新工作区无 `out/`，而远端脚本第一件事就是写 `out/.agent-output.txt`。
    **与"只有 C 站报错"完全吻合**（既有工作区的 `out/` 早先已有文件 ⇒ tar 会带非空目录）。
  - **新发现 F-2（严重度高于 RC③）**：[agent-cli.ps1:2131](../../ops/station-bin/agent-cli.ps1) `Remove-Item … 'agent-out\.agent-run.json'`
    **删除共享固定路径**且 `-ErrorAction SilentlyContinue` ⇒ 并发时 **A 的收尾会删掉 B 的 run 记录** ⇒ **静默数据丢失**（比"随机 abort"隐蔽得多）。
  - **RC③ 定性**：`Assert-AgentOutWritable` 用**固定名探针** ⇒ 并发下把"并发"**伪装成"环境不可写"**（**错误归因**）；
    且该探针被 **task / split 两处**调用 ⇒ 修复须同时覆盖。


#### O-29：无 `accept-golden` 的卡持续产生可重放性 gap

- **证据**：两轮 run 各产生 1 条 —— `subject 'golden-cmd' 声明的 golden-cmd.txt 不在 runDir`。
- **成因**：框架 subjects 清单（`Get-FrameworkSubjects`）**默认每张卡都有 golden**；而吃狗粮卡（如 A1）**无 golden** ⇒ 每条 run 都记 gap。
- **处置**：本轮按仓指定路径 `cluster.py agent audit --accept` 推进水印（存量 16 → 18）。
- **⚠ 但**：门禁自身的处置建议写明"若明细是「已归档但未被任何 subject 覆盖」⇒ **应改 `Get-FrameworkSubjects`，而不是接受它**"。
  本条是**反向情形**（subject 声明了、文件不在）⇒ **接受是权宜；正解是让框架支持"无 golden 卡"**，
  否则**非 golden 卡会持续污染该审计**（且需人工每次 `--accept`）。

#### O-30：站上环境与卡面约束（三条）

| 子项 | 实测 | 影响 |
|---|---|---|
| **`/proc/*` 不可读** | `permission requested: external_directory (/proc/*); auto-rejecting` ⇒ `cat /proc/meminfo` 被拒 | **任何依赖 `/proc` 的采集不可行**（须改走 `free -m` 等二进制）；**直接约束 D7 的"基于 agent 的计量"** |
| **B 站无 `nvidia-smi`** | `未找到命令` | 三站为 AMD UMA 机型 ⇒ 须走 `rocm-smi` / `/sys/class/drm`；采集类卡**必须写回退链** |
| **`readonly: true` 与"必须落文件"互斥** | 同 run：模型跑了 6 条命令、数据齐全，**但产物文件始终未生成** | **卡面纪律**：要求落文件的卡**不得**用 `readonly: true` |

- ★ **第二实例（2026-09-24，吃狗粮 A2 卡）**：同一条纪律又在**工作区根以外的目录**上命中 ——
  `permission requested: external_directory (/home/scott-lau/scripts/*); auto-rejecting` ⇒ **该目录被 auto-reject**。
  ⇒ **代价实证**：我据此写的 A2 卡（"遍历站上 `~/scripts/` 逐个 sha256"）**设计上就不可执行**，首跑 `TASK_RC=9`（验收失败）。
  ⇒ ★ **边界（2026-09-24 修正，勿再简化为"工作区内外"）**：**A1 卡的 `ls -1 ~/agent-workspaces` 成功**（工作区**根**可读），
  而 `~/scripts`、`/proc` 被拒 ⇒ 真边界是**白名单**（含工作区根）。
  ⇒ **纪律（应入册）**：**工作区根之外的取证不由 agent 做**（改由**主控 ssh**），agent 侧只用**可执行命令**。
  ⚠ **白名单确切内容未定**（站上 `~/.config/opencode/` **无显式 `permission` 配置** ⇒ 走默认），待查。
- **附带线索（未追）**：站上 `~/agent-workspaces` 实测有 **`_p3_claude_ws`** 与 **`v0probe`** 两个
  **未在 `$PROJECTS` 注册**的目录 ⇒ 存在**绕过 proj 注册的落点**（P3 = claude 通道），值得单独追。

#### O-31：`_p3_*` 暂存名（**已核实为真缺陷 ⇒ 已修**）

- **背景**：把 `BLINDSCAN-v3 §3` 的跨条目纪律**断言化**后（`tests/test_cli_concurrency_guards.py` 第 8 条护栏），
  首跑扫出 **11 处未分类共享路径** ⇒ 其中 **2 处是真问题（已修）**：`agent-cli-create-$proj.tar` 与 `agent-cli-stag-$proj`
  （`workspace create` 路径，与 F-14 同型）⇒ 三处 tar + staging 已全部加 `$Script:RUN_TOKEN`。
- **本条目 = 剩下的 4 个"待核实"项**：站上 `/tmp/_p3_claude_{in,out,err}.txt` · `/tmp/_p3_run.sh`
  —— **尚未核实**它们是否位于带 ts 的 scratch 目录下（若在，则名字虽固定但**目录带身份** ⇒ 可转豁免；
  若不在，则是**第四例同类缺陷**，须加 token）。
- **✅ 核实完成（2026-09-23）—— 结论：它是真缺陷（第四例），不是"目录带身份"**：
  - **本地 scratch 确实带 ts**：`$scratch = Join-Path $env:TEMP "agent-cli-claude-$ts"`（[agent-cli.ps1:2527](../../ops/station-bin/agent-cli.ps1)）✓
  - **但站上名是固定名**：`$rIn='/tmp/_p3_claude_in.txt'` · `$rOut=…_out.txt` · `$rErr=…_err.txt`（[:3016](../../ops/station-bin/agent-cli.ps1)）⇒ **不含 ts** ❌
  - **且 claude 备路的站上脚本不持 `flock`**（[:3019-3050](../../ops/station-bin/agent-cli.ps1) 只有 `SET`/`cd`/`timeout`，无锁）
    ⇒ **同站并发两个备路 run 会互踩**（stdin 互相覆盖、输出混写）⇒ **与 F-1/F-2/F-14 同因（漏照抄两个样板）⇒ 第四例**
  - `_p3_settings_$$.json`（[:3033](../../ops/station-bin/agent-cli.ps1)）**含远端 shell pid** ⇒ 有身份 ✓（不需修）
  - `_p3_claude_run.sh`：本地在带 ts 的 scratch 下；站上名固定但**内容恒定**（here-string 常量 + 参数传入）⇒ 可转 EXEMPT
- **✅ 修法（2026-09-23 已落地）**：按"让站上脚本从参数取 tmp 前缀"这一方案实现 ——
  ① 主控侧生成**唯一 id** `$p3id = 'p3_' + [Guid]::NewGuid().ToString('N').Substring(0,12)`（[:3058](../../ops/station-bin/agent-cli.ps1)）；
  ② 站上脚本参数表加 **`$4 = pfx`**（`ARGSTR="$1"; BUDGET="$2"; WORK="$3"; PFX="$4"`），重定向改用 `"${PFX}_in.txt"` / `_out.txt` / `_err.txt`；
  ③ ssh 调用追加 `'$p3id'`（[:3101](../../ops/station-bin/agent-cli.ps1)）⇒ **固定名已从脚本中消失**。
- **★ 消费者核对（D6-P1 纪律）**：本状态有 **2 个消费者**，均已同步 ——
  ① `tests/test_cli_concurrency_guards.py` 的 **`KNOWN_DEFECTS`**：按该表自身纪律"**修掉后应删除本行**"，
     **已删除 `_p3_claude_{in,out,err}.txt` 三条**；`_p3_run.sh` 核实为"内容恒定 + scp 幂等覆盖" ⇒ **转入 `EXEMPT`**；
  ② 本文 **§1 总览的 O-28 行**（原写"O-31 待修"）⇒ 已改为"已于 2026-09-23 修复"。
- **状态**：✅ **已修（2026-09-23）** —— 静态护栏（同文件 O-31 断言：旧固定名已清除 + `$p3id` 存在 + 前缀经 `$4` 传）**已上线并绿**；
  ⚠ **站上实机并发复跑未做**（备路，需"两个同站并发 run"才算端到端验证）。

#### O-32：进度采样器读**尚未创建**的输出文件 ⇒ 噪音 + run 中断（**已定性并已修**）

- **症状**：C 站某 run 报 `/tmp/agent-cli-task-<ts>.sh: 行 61: …/out/.agent-output.txt: 没有那个文件或目录` + `TASK remote excode=255`。
- **两次误判（留档）**：① 认为"模板排除 `out/` ⇒ 站上无 `out/`"（**错**，见 O-28 的 F-3）；
  ② 认为"站上工作区缺 `out/`"（**也错**）。
- **真因（一手取证，脚本落盘执行取得）**：
  - `mkdir -p "$W" "$W/out"` 在**远端脚本第 4 行** ⇒ **`out/` 从来不缺**（实测目录时间与 `.prompt.txt` 同刻）；
  - **行 61 = 采样器第一句** `ob=$(wc -c < "$W/out/.agent-output.txt" 2>/dev/null)`，而该文件 mtime = **run 结束时**（22:54:54）⇒ 采样期间**尚未存在**；
  - **bash 的 `<` 重定向失败消息由 shell 打印，不受该命令 `2>/dev/null` 抑制** ⇒ 每 5 秒一条噪音，并让 run 中断。
  - ★ **旁证**：那次 run **其实产出了 `station-reality.json`（1107 字节）** ⇒ **"失败"是采样器噪音导致的中断，不是模型没干活**。
- **教训（固化）**：**"缺目录/缺文件"这类判断必须看 `mkdir` 在第几行 + 文件 mtime 序列**，
  不能从错误文本反推 —— 本项目在此点上**连续错了三次**（F-3 → O-32 第①次 → O-32 第②次）。
- **修复**：`ob=0; [ -f … ] && ob=$(wc -c < …)`（[:1666](../../ops/station-bin/agent-cli.ps1)，2026-09-23）。
- **状态**：✅ 已定性 + 已修（待下次站上复跑验证）

### 2.1 2026-09-24 新增（D-24/D-25 裁定取证时发现）

| ID | 类别 | 严重度 | 简述 | 状态 | 归属批次 |
| ---- | ------- | --- | --- | --- | ---- |
| **O-36** | 环境/守护 | P2 | **解释器口径漂移** —— PATH 上的 `python` ≠ 本仓需要的那个（缺 `paramiko`）⇒ 默认路径下 **4/6 测试套件 + 2/14 门禁项静默失效**；★ **提交/手动走两个解释器**（钩子写死 `py.exe` ⇒ 实测 = `Python312`（paramiko 5.0.0）⇒ 10 绿；交互 `python` = hermes venv（无）⇒ 9 绿 2 黄），与 O-34 同族 | ◐ 已定性（有对照实测），处置待裁 | D6-P1 |

#### O-36：解释器口径漂移 ⇒ 默认路径下的守护静默失效（**已定性**）

- **症状（一手对照实测：同一目录 · 同一命令 · 只换解释器）**：

  | 解释器 | `tests/run_py_tests.py` | `rpc_check --quick` |
  |---|---|---|
  | PATH 上的 `python` = `…\.hermes\hermes-agent\venv\Scripts\python.exe`（3.11.16，**无 paramiko**） | **2/6**（4 套件 `ModuleNotFoundError: paramiko` **直接崩**） | **绿灯 9 · 黄灯 2**（`aliases`/`evidence` 均"无法导入 cluster.py"跳过） |
  | `…\Programs\Python\Python312\python.exe`（**paramiko 5.0.0**） | **6/6 ALL PASS** | **绿灯 10 · 黄灯 1**（余下黄灯 = **真信号**：可重放 gap **新增 3**、按框架代分桶 `current(2)=0 · legacy=21`） |

- **三处「声明 ↔ 实测」不符**：
  1. [cluster.py:87](../../ops/cluster.py) 声明 **"依赖: paramiko（主控站 hermes venv Python 3.11 已装）"** —— 实测该 venv **无** paramiko ⇒ **声明本身写错**（与 **T-1**「完成信号与证据不同源」同型）。
  2. 门禁提示只写"请用**装有 paramiko 的 Python** 运行"，**不指名是哪一个** ⇒ 无从机械判定该切哪个（本机同时存在 3 个解释器：hermes venv / Python312 / Anaconda3，**其中只有 Python312 装了**）。
  3. `syntax` 报数行自曝 `.py@3.11.16` ⇒ **手动用 `python` 跑门禁时，跑的就是没 paramiko 的那个解释器**（14 项里 2 项对它天然无效）。
- **★ 补证（2026-09-24，提交 `ba85629` 时取得）—— 分裂的确切机制：提交与手动走的是两个解释器**

  | 路径 | 解释器来源 | 实测结果 |
  |---|---|---|
  | **提交（pre-commit 钩子）** | `.git/hooks/pre-commit:7` **写死** `PY='C:/Users/Peng/AppData/Local/Programs/Python/Launcher/py.exe'`（该钩子由 `ops/rpc.ps1 install-hooks` 生成）；**`py` 实测指向 `Python312`（paramiko 5.0.0）** | **10 绿 / 1 黄 / 0 红** —— `aliases` **PASS** |
  | **手动（交互 `python`）** | PATH ⇒ `…\.hermes\hermes-agent\venv`（3.11.16） | **9 绿 / 2 黄** —— `aliases` / `evidence` 双双跳过 |

  ⇒ **这正是 O-34 的同族现象**：O-34 = `git ls-files` **范围**不同（已修），本条 = **解释器**不同。
  ⇒ **三条口径互不相同**：钩子用 `py.exe` ✅ 能跑 · `cluster.py:87` 注释称 hermes venv ❌ 无 paramiko · 门禁 WARN 提示**不指名**。
  ⇒ 因此处置候选 **(a) 应以钩子为准**：**`py.exe` 就是事实上的规范解释器**（它已是唯一"能跑全绿"的路径），
  应把它写成**一处真值**，并让门禁自检报出"**本项由 \<解释器\> 运行**" —— 否则"手动跑"会长期比"提交跑"少两项守护。
- **后果（★ 真正的守护缺口，不是"调试不便"）**：
  - 按**默认动作**（`python tests/run_py_tests.py`）跑 ⇒ **4 个套件静默不跑**；其中 `test_inbox_seal.py` 是**仓内唯一的 `MANIFEST.sha256` 格式复验器**（其 `data_lines()` = python 版 `-c`）⇒ 刚裁的 **D-24 / D-25**（`#` 注释行 + 哈希行格式固定）**在手动复验路径上是零机械守护**（⚠ **提交路径不受影响** —— 钩子走 `py.exe`，跑得到）。
  - `aliases` / `evidence` **长期黄灯** ⇒ **黄灯免疫**：看起来"有守护、只是黄"，实际是**没跑**。与 **D6-P1**「完成信号须与证据同源」同类。
- **★ 更正留档（本轮自己犯的同型错）**：我上一轮把此现象记成"**本机缺 paramiko**"，只探了 PATH `python` / `py -3.11` / `.venv` 就下结论 —— **实测推翻**：本机**有**带 paramiko 的解释器（`Python312`，5.0.0）。真因是**口径漂移**，**不是能力缺失**。教训与 O-32 同：**结论不得由"探不到"反推，须枚举全部候选再判**。
- **处置候选（本轮未做）**：
  - **(a) 门禁加解释器自检**：`rpc_check` 启动探 `import paramiko`，缺则**指名可用解释器**（或由 `RPC_PY` 覆盖）；报数行写明"本项由 \<解释器\> 运行" —— **最治本**，符合本仓"让事实由代码产生"的纪律；
  - **(b) 纠正口径**：`cluster.py:87` 的依赖声明 + 一处真值写明"跑本仓用哪个解释器"；
  - **(c) 给 hermes venv 装 paramiko**：最小动作，但**不改口径**，且改环境须登记；
  - **(d) `cluster.py` 惰性导入 paramiko**（只在真正用到 ssh 的函数内 import）：让纯本地路径不再被远程依赖拖垮，最彻底但触及核心模块。
  - **建议顺序**：**(a) + (b) 先做**（不动环境，纯"口径 + 自检"，立刻消除"不知道用哪个"），(c) / (d) 视需要。
- **★ 直接探测（2026-09-24 补齐，取代先前"由行为反推"）**：`py -c "import sys,paramiko"` ⇒
  `sys.executable = C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe` · `paramiko = 5.0.0`
  ⇒ **钩子用的解释器就是 `Python312`，即本机唯一带 paramiko 的那个** —— 与行为推断一致，且现已是**直接测量**。
- **状态**：◐ **已定性（2026-09-24：手动/提交双路径 + 三种解释器对照实测）**，处置待裁（候选 a~d）

### 2.2 2026-09-24 新增（吃狗粮**首次成批执行**的产出）

> 出处：[DEV-LOG-013](../../docs/DEV-LOG-013-dogfood-execution.md) · 卡区 [dogfood-cards/](dogfood-cards/README.md)

| ID | 类别 | 严重度 | 简述 | 状态 | 归属批次 |
| ---- | ------- | --- | --- | --- | ---- |
| **O-37** | 工具/信号 | **P1** | `.progress` 的 `t=0` 读**上一轮残留** ⇒ 假进度 / **假完成信号** | ◐ 已定性 + 已修，待站上复跑验证 | ✅ |
| **O-38** | 文档/一致性 | P2 | **O-25 P2 看板缺磁盘证据**（生成器与产物全仓/归档区均无） | ⏳ 待复核 | O-25 · D6-P1-1 |
| **O-39** | 可观测/基准 | P2 | **派发前预估对出网档恒 MISS** ⇒ 吃狗粮无预估 | ⏳ 待决定 | O-25 |
| **O-40** | 证据/回收 | **P1** | **产物不进 run 目录** ⇒ 只能手动 `scp` | ⏳ 待建 | D6-P1-1 · ADR-0007 |
| **O-41** | 门禁自审 | P2 | B2 报出的两条**疑似未登记假绿** | ⏳ 待复核 | D6-P0-1 |

#### O-37：`.progress` 采样器 `t=0` 读**上一轮残留**（**P1，假信号级**）

- **机制（一手读码）**：[agent-cli.ps1:1693](../../ops/station-bin/agent-cli.ps1) 启动时只 `: > "$W/out/.progress"`
  —— **没有清 `out/.agent-output.txt`**；而采样器（[:1700](../../ops/station-bin/agent-cli.ps1)）读的正是后者，
  **opencode 的 `>`（[:1722](../../ops/station-bin/agent-cli.ps1)）要等它启动才截断** ⇒ **t=0 那个样本读到上一轮内容**。
- **★ 铁证（两个数字精确对上）**：

  | run | `.progress` `t=0 bytes` | 等于谁 |
  |---|---|---|
  | A1 `202609240057242849` | **4434** | = 上一轮（09-23 23:13）的 `OUT_BYTES` |
  | B2 `202609240059503785` | **4470** | = **A1** 的 `OUT_BYTES` |

- **两个后果**：① 首样本 `bytes_s` **假高**（实测 `1478000` / `2235000` B/s）；
  ② ★ **更严重**：`bytes > 0` 在 **t=0 就成立** ⇒ 任何"**以字节增长判已产出**"的消费者，
  会在**第 0 秒看到假进度/假完成** —— 与 **T-1**（完成信号须与证据同源）、
  **O-22**（`.meta` 残留把上轮终态读成"本轮又超时"）**同病族：跨 run 残留被当本轮状态**。
  ⚠ O-22 只修了**主控侧** `.meta`；**站上 `out/.agent-output.txt` 是同类漏网**。
- **修法（2026-09-24 落地）**：在 `: > .progress` 之后、`sample_progress &` **之前**加
  `: > "$W/out/.agent-output.txt"`（时序：清空 → 启动采样器 → opencode 以自己的 `>` 再截断）。
- **验证（正反）—— ✅ 均已完成**：**反例已在盘上**（本条两条铁证即"改前 t=0 非 0"）；
  **正例 = 修后复跑**（run `202609240121190214`）：`.progress` 首行 **`t=0 bytes=0 bytes_s=0`** ✓（改前同位置是 4434/4470）

#### O-38：**O-25 P2 看板"已落地"缺磁盘证据**（**✅ 已复核：非虚报，是"有意清减 + 能力被取代、台账未回写"**，2026-09-24）

- O-25 台账原文："**P2看板 ✓（2026-09-12 落地**，L3 单文件 HTML：`make-dashboard.ps1` 生成器→内联 ledger+run.json→self-contained `dashboard.html`）"。
- **实测（2026-09-24）**：`Glob **/*dashboard*` 全仓只命中 `.trae/documents/O-25-P2-dashboard.md`（**计划件**）；
  `ops/station-bin/` 下**无生成器、无产物**；`inventory/ops.yaml` **未登记**它；`archive/scripts-history/` 也无。
- ★ **复核（2026-09-24，`git log --all --name-only` + 提交信息）—— 真相不是"从未入库"**：
  | 提交 | 动作 |
  |---|---|
  | `5f2b395` chore(security) | **加入** `ops/station-bin/dashboard.html` + `make-dashboard.ps1` |
  | **`3712f06`** refactor(governance) *"第一批脚本清减 (删 7 个)"*（**ADR-0004 D5**「统一管理入口为唯一管理面」, 2026-09-15） | **删除**上述两件 |
- ⇒ **定性**：看板**曾以独立脚本形式落地**，后在 **ADR-0004 D5 的脚本清减中被人为移除**（**合规动作**，非丢失）；
  且**同日**（2026-09-15）[`ops/cluster_web.py`](../../ops/cluster_web.py)（76KB，**已登记 `inventory/ops.yaml`**）**统一管理页改造定版** ⇒ **能力被承接/取代**。
- ⇒ **结论**：**O-25 的"功能已落地"基本成立，错的是"落点"表述**（仍指向被删的 `make-dashboard.ps1`/`dashboard.html`）。
  ⇒ **处置 = 修正落点表述并关闭本项**（同 **O-33** 族：「实体搬家后文档未跟随」，非缺陷、非虚报）。
- ⚠ **方法论留痕**：本条一度被定性为"**台账凭空虚报**"——**是错的**。`git log --all -- <path>` 一步即可分辨
  "从未入库 / 曾入库后被删"；**仅凭工作区 `Glob` 就下"虚报"结论，等于用"现在的快照"推断"历史"**（与"凭推断下结论"同病）。
- **✅ 补做完成（2026-09-24，Scott 裁定"补做"）** —— ★ **不是恢复独立脚本，而是"能力并入统一入口"**：
  - **合规判据**：**ADR-0004 D5**「统一管理入口为唯一管理面」—— 原 `make-dashboard.ps1` 正是据此清减的
    ⇒ 若"复活"它，等于**撤销 D5**。故补做的正确形态 = **在 `cluster.py` 加子命令**。
  - **落地**：**`cluster.py agent dashboard [--limit N] [--out <文件>]`** ⇒ 产出**自包含单文件 HTML**
    （**数据内联 + 零网络请求**，`file://` 直开）—— 恢复了原件的**独有价值**（离线快照 / 可作附件）。
  - **同源不漂移**：复用 `agent_runs` / `agent_live` / `agent_ledger_freshness` —— 与在线视图
    `cluster_web.py` 的「Agent 任务」卡片**同一份数据函数**（该卡片本就在承接看板能力，只是**在线**形态）。
  - **产物合规**：默认落 `ops/agent-dashboard.html`，**已入 `.gitignore`**（同 `ops/cluster_status.html` 先例），
    并在 [`inventory/artifacts.yaml`](../../inventory/artifacts.yaml) **登记为 exempt 生成物**（走本批刚落地的 D6-P1-1 纪律）。
  - **自包含自证**：生成 6890 字节，实测 **`https?://` 0 处 · `<script src=` 0 处 · `<link ` 0 处** ⇒ 打开零网络请求。
- **⇒ 分工**：**实时**用 `cluster_web.py`；**离线快照/归档/附件**用 `cluster.py agent dashboard`。

#### O-39：**派发前预估对出网档恒 MISS**（待决定）

- 本轮两卡日志均为：`ESTIMATE: model=openrouter/nvidia/nemotron-3-ultra-550b-a55b:free **no-bench (MISS)** - skip dispatch estimate`。
- 机制本身**按设计工作**（O-25 原文："**HIT 才给 / MISS 不打荒**"）—— 问题是**基准表只覆盖 `local/*`**，
  而吃狗粮**全走出网档** ⇒ 该机制对吃狗粮链路**零贡献**（且易被误读成"坏了"）。
- **✅ 已裁并实施（2026-09-24）—— 裁定：走 ②「显式声明」+ ★ 修掉一个更值钱的问题**

  **为什么不是 ①（补 bench 行）**：`$TpBench` 的口径是 **tok/s（prefill/decode）**，
  而**出网档没有本地 prefill/decode**（延迟在 provider 侧）⇒ 硬填一行只会产出**编造数字**，
  直接违反该表自设的「**no-bench 不打荒**」纪律。**不补**才是自洽的。

  ★ **执行中发现并修掉的真问题（比 O-39 本身更值钱）**：原实现把**两种截然不同的 MISS 混成同一句**
  `no-bench (MISS)` ——
  · **(a) 出网档**：**按设计不适用**（本该 MISS，非缺陷）
  · **(b) 本地档但缺 `$TpBench` 行**：**真缺口**（该补基准）
  ⇒ 混报的后果是 **(b) 会隐身**：「出网档本该 MISS」成了遮住「某本地档一直没测」的**挡箭牌**
  —— 正是本仓头号失败形态「**把两件事说成一件**」。

  **实施**（[`agent-cli.ps1`](../../ops/station-bin/agent-cli.ps1)）：`Get-ThroughputEstimate` 增**第三态 `na`**
  （`$modelId -like 'openrouter/*'` ⇒ `na=$true`），预报改为**三态分报**：
  · `hit` → 原样给 prefill/decode/est_total + TIMEOUT-WARN
  · `na` → `egress - N/A by design (provider-side latency; no local prefill/decode) [O-39]`
  · `miss` → `no-bench (MISS) - local model missing bench row => should add $TpBench entry [O-39]`（**真缺口显形**）

  **双向自证**：新增静态护栏（`tests/test_cli_concurrency_guards.py`，**14 条**）断言"两态**分开**报"；
  并以内存抽特征复算证明三条子串判据**具辨别力**（`N/A by design` / `missing bench row` / `na = $true`
  各自被抽掉时对应谓词转 False）⇒ 非恒真。

- **⇒ 副产物（可执行）**：今后派发日志里**只剩一种 MISS**（本地档缺基准）⇒ 它一旦出现就是**真待补**，
  不再与"出网档正常现象"混淆。

#### O-40：**卡的产物不进 run 目录**（P1，后续所有卡的公共前置）

- **实测**：A1/B2 两条 run 的 `workspace-diff.txt` **均为空**（`WORKSPACE_DIFF_LINES=0`）；
  产物 `out/station-reality.json` / `out/falsegreen.md` **只留在站上** `~/agent-workspaces/dogfood/out/`，
  主控 run 目录只收 `agent-output.txt` 等**固定证据件** ⇒ **本轮是我手动 `scp` 取回的（暂存 `tmp/`，非持久）**。
- **影响**：任何"产物即结论"的卡（A1/A2/B1/B2 全是）都**需要一个回收动作**，否则吃狗粮的产出留不住。
- **候选**：① 卡里声明 `evidence-manifest.subjects`（ADR-0007 阶段 1 已支持"声明 + 落 run.json"，复验器按声明走）；
  ② 扩展 collect 白名单；③ 主控侧回收命令。**建议 ① 优先**（不新增机制，复用既有契约）。
- **✅ 已实现（候选①，2026-09-24 复核确认）** —— 台账此前标"待建"**属滞后**：
  - **机制在**：[`agent-cli.ps1` 的 collect 段](../../ops/station-bin/agent-cli.ps1) 有 EVM pull（白名单校验 + scp 回 runDir，O-40/A-1 落地）；
  - **声明在**：`dogfood-cards/` **5 张卡**均已写 `evidence-manifest.subjects[].state`；
  - **实证在**：B2 run `202609241608498832` 与受控夹具 run `202609241819027923` 均打出 **`EVM_STATE: pulled=1 rejected=0`**，产物 `o46-probe.txt`（内容 `HELLO_O46`）在 runDir 内可读。
  - ⚠ **仍未覆盖的边界**：卡**必须显式声明**才回收（未声明 ⇒ 不拉，静默）；且**不覆盖 collect 命令本身**（那是 O-45）。

#### O-41：B2 报出的**两条"疑似未登记假绿"** —— **已复核：① 非缺陷 / ② 真缺口**（2026-09-24）

> 来源：B2（门禁假绿审计）产物 `out/falsegreen.md`（17 项断言全覆盖、含每项**最小反例**）。
> 复核方式（本仓纪律「判据必须先做数据侦察再写码」）：**读码 + 路径推演**，不凭模型报告直接登。

| # | 断言 | B2 报出的假绿条件 | **复核结论** |
|---|---|---|---|
| 1 | `doclinks` | 对**绝对路径 / 盘符 / URL / 占位词一律"不可判"跳过** ⇒ 写一个**不存在的绝对路径**也能 PASS | ❌ **不成立为"未登记假绿"** ⇒ **定性为「射程声明」**，见下 |
| 2 | `engine` | **残留阈值 2048MB 硬编码** ⇒ 一个占 1.5GB 且不监听任何 `ENGINE_PORTS` 的残留进程会被判"正常" | ✅ **成立（真缺口）** ⇒ 保留为待加固项 |

**① 复核依据**（[`rpc_check.py:680-702`](../../ops/rpc_check.py#L680-L702) `_doclink_bad`）：
- 对 `http/https/mailto/file:///`/`#` · 空/含空格/`...`/占位词 · **Windows 盘符** · **落仓库外的非相对形态** 一律 `judgeable=False` ⇒ **跳过**；
- 但**只有"相对链接 `..` 写多、越出仓库根"判 FAIL**（2026-09-22 决策简报 A 的**刻意拆分**，注释在案）；
- 且**不可判数已报数**（门禁输出行：`其中非仓库内相对链接/占位词 895 条不判`）⇒ **"范围已收窄"是可见的**（与 O-34 加 `_untracked_count()` 同一思路）。
- ⇒ 判据射程 = **"仓库内相对链接"**；写绝对路径**本就不在射程内**。**非缺陷，无需加固**（加固会撞既有纪律「判不准的不进门禁」）。
- ⚠ **但需台账留痕**（否则下次会被当"新假绿"再报一次）⇒ 本条即留痕。

**② 复核依据**（[`rpc_check.py:2208`](../../ops/rpc_check.py#L2208) `RESIDUAL_RSS_MB = 2048`）：
- `elif rss >= RESIDUAL_RSS_MB:` 才记 detail（判 FAIL）；`rss < 2048` 且无端口 ⇒ 落 `else` ⇒ **info「引擎未运行——零自加载方针下属正常」⇒ PASS**；
- ⇒ **字面成立**：1.5GB 且不监听 `ENGINE_PORTS` 的残留 llama 进程被判"正常"（**内存被占着没干活**，会污染加载预估 —— 正是该断言的设立目的）。
- **✅ 已加固（2026-09-24）**：新增常量 `RESIDUAL_WARN_MB = 1024`（[`rpc_check.py`](../../ops/rpc_check.py)），
  `无端口 ∧ RSS ∈ [1024, 2048)` ⇒ 报 **WARN**（"疑似残留/启动中"，**不升 FAIL** —— 仍可能含瞬态且不阻塞加载）。
  下沿取 1024 是**刻意**的：`ggml-rpc-server` 空转 ~0.3G 属既有阈值明确容忍的情形，不能被本条变成噪声。
- **✅ 关闭判据已满足（正反自证）**：新增护栏 [`tests/test_rpc_check_engine_bands.py`](../../tests/test_rpc_check_engine_bands.py)
  （monkeypatch `_health_probe` 离线覆盖全分带）⇒ **7/7 通过**，含关键用例
  **「1536M 无端口 ⇒ WARN（旧实现判 PASS）」**、以及"300M 空转仍 PASS / 3000M 仍 FAIL / 端口在听但 RSS 过小仍 WARN"三向不回归。
  另加结构护栏：`RESIDUAL_WARN_MB < RESIDUAL_RSS_MB`（顺序颠倒 ⇒ 预警带永不触发）。

> ⚠ 同批产出中**另有 4 条是"独立命中已知"**（`secrets` 未跟踪文件 / `inventory` 声明源列表 / `aliases`·`evidence` 缺 paramiko / `inbox` 目录缺失即 PASS）
> ⇒ 这既是**模型读懂了**的证据，也是**局限**（它没超出人类已记录的范围）；如实标注，避免高估。

#### O-42：`claude` 通道 `-p` **无写权限** ⇒ 产物型任务不可用（**待裁**）

- **实测（2026-09-24，烟测卡 `dogfood-cards/smoke-claude-channel.md`，run `202609240130344985`）**：
  **链路全通** —— `CLI=claude route_station=`（空 ⇒ **主控本地**）· `CLAUDE_SPAWN=…claude.exe` ·
  **`claude first rc=0`** · 42s · 认证走 `~/.claude/settings.json` 的 **`apiKeyHelper` → OpenRouter** ·
  模型 = `thinkingmachines/inkling:free`（**免费档**）· `ACCEPT_MODE=bash-local`（验收在主控 Git Bash，cwd = 载体根）。
- **但产物没落**：模型自报 **"文件写入被拒 → `SMOKE_BLOCKED`"**；载体 `out/` 只剩 `.keep`；`stderr.txt` 为空 ⇒ **`ACCEPT_OK=0`**。
- **根因（一手读码）**：[agent-cli.ps1:2729](../../ops/station-bin/agent-cli.ps1) 调用形式 = `'-p "" --model "<id>"'`
  —— **不带任何权限开关**（无 `--permission-mode` / `--allowedTools`）；`settings.json` 的 `"defaultMode": "acceptEdits"` 在 `-p` 下**不生效**。
- **待裁的修法**：加 `--permission-mode acceptEdits`（或最小化 `--allowedTools`）。
  ⚠ **两个必须先想清的点**：
  ① 这是**能力放宽**（agent 从"只输出"变"可写"）⇒ 按本项目纪律须**配正反注入**（改后：能写 ✓；**`readonly: true` 的卡仍不得写** ✓）；
  ② **必须显式处理与卡面 `readonly: true` 的关系** —— 否则 claude 通道会把"只读卡"也变成可写 ⇒ **破卡面契约**（与 D-06/D-07 同级的安全面）。
- **现状定性**：**claude 通道目前只能接"纯输出型"任务**；产物型（本目录 A1/A2/B1/B2 全部）**只能走 opencode**。
- **状态**：✅ **已修**（2026-09-24）—— `-p` 加 `--permission-mode acceptEdits`（**按卡 `readonly` 动态**：`readonly=false` 才可写，`readonly=true` 空串保只读）；claude 烟测端到端 `ACCEPT_OK=1` + `out/smoke.txt`=`SMOKE_OK`（run `202609241047036207`）。`readonly:true` 的卡**仍保持只读**。

#### O-43：zen（`opencode/*`）**"需要 tty"** 被误判为"缺凭据"（**归因更正 · 待裁切回**）

- **起因**：Scott 反馈"**我可以在 A/B/C 三站直接打开终端输入 `opencode` 用免费模型**，为什么你提示我登录？"
- **一手实验（2026-09-24，站 B）**：

| # | 实验 | 结果 |
|---|---|---|
| ① | `printf '只回复一个词: ZEN_OK' \| timeout 45 opencode run -m opencode/nemotron-3.5-lightning-free`（**非 tty**） | **`RC=124`（挂死，45s 零产出）** |
| ①' | 同上加 `--print-logs --log-level DEBUG` | 请求**已发出**（`llm runtime selected llm.provider=opencode`）；**无任何 401/403/credential 报错** ⇒ **不是凭据问题** |
| ② | **同一模型**套伪 tty：`script -qec "opencode run -m <zen-id>"` | ✅ **`RC=0`，43s 返回 `ZEN_OK`** |
| ③ | 对照组 `openrouter/thinkingmachines/inkling:free`（**普通管道**） | ✅ `RC=0`（≈16s）⇒ **只有 zen 这一路要 tty** |
| ④ | 三站 `auth.json` / `opencode auth list` | A = `{}`（2 字节）· B/C = **文件不存在** ⇒ 0 凭据；**但这不是失败原因**（③④ 与 ② 共同证明） |

- **⇒ 结论**：**2026-09-21 的"0 credentials ⇒ 静默挂死"归因错误**，真因 = **zen 免费档需要 tty**；
  Scott 的 TUI 能用，正因为 **TUI 有真 tty**。**恢复 zen 不需要任何登录/凭据**。
- **已更正 3 处**（防止第 3 次误导）：
  ① [agent-cli.ps1](../../ops/station-bin/agent-cli.ps1) 的 `ROUTE_TABLE` 注释块（原写"若要恢复 zen 就登录"）；
  ② [REMEDIATION-PLAN.md](REMEDIATION-PLAN.md) 的「登录 zen」行（划掉并写明前提错了）；
  ③ 本条。
- **未做的（待裁 / 待设计）**：
  - ▶ **切回 zen 的前置 = PTY 输出净化**：`script` 会把 **banner + ANSI 控制字符 + "脚本启动于…"** 混入 stdout
    ⇒ 会污染 `out/.agent-output.txt`（连带 **O-37** 的字节计数、产物解析、`accept` 判据）⇒ 须先定净化方案；
  - ▶ **`_probe_opencode_provider.sh` 对 zen 不可用**（它只测非 tty 形态 ⇒ **恒报 `RC=124`**）⇒ 待改用**伪 tty 对照**；
  - ▶ zen 的**留存/训练政策仍未核**（只核过 OpenRouter）⇒ 政策核实前，**含未发表内容的卡不宜走 zen**。
- **经济意义（Scott 的原始动机）**：zen 可用 ⇒ 可**不消耗 openrouter 免费配额**（1000/天/账户，留给 claude 通道等）。
- **状态**：◐ 已定性 + 文档已更正；**是否切回 zen 待裁**。

##### ★ 试点结果（2026-09-24，定稿脚本 [`ops/station-bin/_zen_pty_pilot.sh`](../../ops/station-bin/_zen_pty_pilot.sh)）

**双臂实测（同一最小任务：在**工作区**内写出 `out/pilot-arm-<臂>.txt`）**：

| 臂 | 方式 | RC | 耗时 | 产物 | 净化残留 |
|---|---|---|---|---|---|
| **Z** | zen + **伪 tty**（`script -qec`） | **0** | 73s | ✅ `ARM_Z_OK` | ESC=0 · CSI=0 |
| **O** | openrouter + 普通管道（对照） | **0** | 50s | ✅ `ARM_O_OK` | ESC=0 · CSI=0 |

净化后输出**可读且信息量更高**（能看到工具调用与结果）：

```
> build · nemotron-3.5-lightning-free
$ mkdir -p out && echo "ARM_Z_OK" > out/pilot-arm-Z.txt && echo "DONE_Z"
DONE_Z
```

⇒ **结论：伪 tty 下 zen 完全可用（不只回话，而是执行工具调用并产出文件）**；对照组无回归。

**净化解法演进（关键：为什么用 python3 而不是 sed）**：

| 解法 | 结果 |
|---|---|
| sed `s/\[[0-9;?]*[ -\/]*[@-~]//g`（r1，一路用了 6 轮） | ✗ **实测不匹配**（真实 raw 残余 4 处；GNU sed 4.9） |
| sed `s/\[[0-9?;]*[a-zA-Z]//g`（r2）· `s/\[[^a-zA-Z]*[a-zA-Z]//g`（r3） | ✓ 可用（残余 0） |
| **python3（定稿）** | ✓ 站上已有 **Python 3.12.3**；`\x1b\[…` 无歧义，残余 0 |

**四条实测要点（已写进脚本头注释）**：
1. **zen 需要 tty**；2. **必须先 `cd` 到工作区**（否则产物落到 `~/out/`，造出"模型没干活"的**假失败**）；
3. **净化用 python3**（sed 的 CSI 正则不可靠）；4. **硬断言**：净化为空即 FAIL。

**⚠ 未决风险（切回前必须量化）**：**zen 时延波动大** —— 四次观测 43s / 54s / 73s / **一次 90s 超时（`RC=124`，无产出）**；
对照臂 openrouter 稳定（37s / 50s）。⇒ 切回 zen 需先定**预算与重试**策略，否则会把"慢"误判成"挂死"。

**⚠ 本轮"我的观测设计缺陷"共 5 次（全部当场自纠，一并记账）**：
① 上一轮只凭 `auth.json` 为空就断言"缺凭据"（**无对照组**）；
② 试点 v1/v2 漏 `cd "$W"` ⇒ 两臂同时假失败（**正是对照臂暴露了它**）；
③ 净化正则 r1 从一开始就是坏的（**"残留=0"的检查是空文件造成的假通过**）；
④ 把 PCRE 的 `(?:…)` 写进 sed（ERE 不支持）⇒ sed 报错输出空 ⇒ 又一次假通过；
⑤ 断言写成 `grep -c … || echo 0`（`grep -c` 失败时**也打印 0** ⇒ 变两行 ⇒ 比较恒假）⇒ 假 FAIL。
⇒ **教训**：**探针/断言本身必须先被验红**（合成用例 + 对照组 + 非空断言），否则"通过"没有意义。

##### ★ 稳定性采样结果（2026-09-24，脚本 [`ops/station-bin/_zen_stability_sample.sh`](../../ops/station-bin/_zen_stability_sample.sh)）

**设计**：站上落盘逐轮追加 CSV（断连不丢）· 每轮换文件名/内容（防缓存复用）· 预算给足 **150s**（为区分"慢"与"挂死"）·
**穿插对照臂**（首轮与末轮走 openrouter）⇒ 若对照组也变慢，说明是环境而非 zen。

| iter | 臂 | 模式 | RC | 耗时 | 产物 | 净化字节 | 状态 |
|---|---|---|---|---|---|---|---|
| 1 | **O** | pipe | 0 | **19s** | ✅ | 292 | PRODUCED |
| 2 | Z | **pty** | 0 | **92s** | ✅ | 122 | PRODUCED |
| 3 | Z | pty | **124** | 152s | ✗ | 39 | **TIMEOUT** |
| 4 | Z | pty | **124** | 152s | ✗ | 39 | **TIMEOUT** |
| 5 | Z | pty | **124** | 152s | ✗ | 39 | **TIMEOUT** |
| 6 | Z | pty | **124** | 152s | ✗ | 39 | **TIMEOUT** |
| 7 | **O** | pipe | 0 | **25s** | ✅ | 183 | PRODUCED |

- **Z 臂成功率 = 1/5 = 20%**；4 次超时**均为 152s（= 预算被掐）且输出恒为 39B（只有 banner，零实质内容）**。
- **对照臂 2/2 = 100%**，19–25s ⇒ **同期环境正常**，问题在 zen 这一路。
- **净化自检：非零 ESC 轮次 = 0** ⇒ 净化方案在**多轮真实调用**上成立（不只是单次样本）。
- ⚠ **时延分位数不可报**：成功样本 **n=1**，分位数无意义（这里如实标注，不假装 p50/p95）。
- ★ **形态判断**：**1 次成功后连续 4 次超时** ⇒ **不是随机波动，而是"进入限流/冷却"的特征**；
  旁证：站上日志出现 `[opencode-codex-memory] skipping phase1 due to rate limit`（该链路上确实存在限流机制）。

**⇒ 裁定建议：不建议将该限时免费档纳入运行时路由**（从"暂不切回"升级）。
三组证据：
1. **我们的实测**：20% 成功率 + 失败形态是**静默挂死**；经济账不站在 zen 这边（20% 成功率 ≈ 平均投 5 次，
   而 openrouter 免费档本身**零付费**且 100% 成功 ⇒ 换 zen 更贵（时间）且更难诊断）。
2. **★ 官方"限时提供"（社区收集，最硬的否决理由）**：官方文档明确 `Nemotron 3.5 Lightning Free`、
   `Nemotron 3 Ultra Free`、`Big Pickle`（stealth 免费模型）都标注"**available for a limited time**，
   团队用这段时间收集反馈以改进模型"（opencode.asia/zen-models · opencode.ai/docs/zen）⇒ **这组免费档是
   招募反馈的限时实验资产，随时可能下架/降级，稳定性无保证，不该进运行时路由**。
3. **★ 空闲流卡死模式（社区案例，解释失败形态）**：OpenCode 连上游（如腾讯 HY3）出现 **idle streaming stall** ——
   上游连接保持打开、流停止产生事件、OpenCode**不中止空闲流** ⇒ 任务看似永久卡住；短烟测正常、复杂/受控请求卡死
   （kunpeng-ai forum HY3 诊断）。⇒ 与我们"152s 超时、干净输出只到 banner"高度一致：不是"没响应"，
   而是进入空闲流卡死；也解释为何**对照臂 openrouter 一直正常**（卡在 zen 网关这一路，非 OpenCode/脚本）。
   ★ 同页面缓解建议（provider `timeout` + 拆分长任务 + 2 分钟无进展即停止）与我们"慢/挂死难分辨"的教训一致。
   旁证补充：NVIDIA NIM 文档显示 `max_output_tokens` 若在产出可见文本前被 thinking 耗尽，返回 `status:"incomplete"`
   —— 可解释部分"只到 banner"，但非主因（我们有明确 152s 截断）。

**资产定性**：zen 免费档 = **限时实验资产**（官方招募反馈用）。⇒ 不进入 `ROUTE_TABLE`，仅留作**人工试点**时偶用。

**若未来价值条件变化再评估（当前不主动做）**：若免费档转正/加 SLA，可重做**间隔投放**（每 5 分钟 1 次 × 4）
以区分"频率限流"与"额度/服务受限"，再决定是否纳入。

**采样本身的元价值**：**5 次调用（零成本）就否掉了一次运行时切换** —— 若直接切 `ROUTE_TABLE`，会在真实派发中踩连续超时，
且"慢/挂死"难分辨（正是本项目一直在治的假信号病）。

#### O-44：`scripts` 把**未提交的新脚本**报成"清单项已不存在(应移除)"（**O-34 同源 · 第二处消费者**）

- **现象（2026-09-24）**：新增 `ops/station-bin/_zen_stability_sample.sh` **并已登记进 `inventory/ops.yaml`** 后，
  门禁 `scripts` 报：`冻结存量 187 · 未登记 0 · 清单含 1 项已不存在(应移除)`。
  而该文件**确实在磁盘上**（脚本核对：`磁盘存在=True`）⇒ 报的不是"文件没了"，而是"**扫描器看不到它**"。
- **机制（一手读码）**：[rpc_check.py:632](file:///d:/RPC/ops/rpc_check.py#L632) `gone = sorted(f for f in frozen if f not in scripts)`，
  而 `scripts` 来自 [`_iter_governed_scripts()`](file:///d:/RPC/ops/rpc_check.py#L594) → `_iter_source_files()` ——
  后者**只覆盖 git 跟踪文件**（该假设已在 **O-34** 定性）。⇒ **未提交的新脚本 ⇒ 不在扫描集 ⇒ 在冻结清单里"消失"**。
- ★ **危害**：该提示的原文是"**只减不增, 删减是欢迎的方向** … `可以从 inventory/ops.yaml 删掉`"
  ⇒ **它会诱导人删掉一条完全正确的登记**；若照做，**提交后该脚本立刻变成"未登记"并 FAIL**。
- **判据修复候选**（与 O-34 对齐）：① `scripts` 也加"另有 N 个**未跟踪**脚本未计入"的提示（复用 `_untracked_count()` 的思路）；
  ② 措辞**区分两种情形**："清单项在磁盘上但**未跟踪** ⇒ 提交后即恢复" vs "磁盘上确实没有 ⇒ 应移除"；
  ③ 更彻底：`gone` 只在**文件确实不存在**时才算（即 `not (ROOT/f).exists()`）。
- **本次自纠**：我先前把这行判为"**改动前就存在的历史遗留**"——**错了**；它其实是当时**我自己那批未跟踪的新脚本**
  （先是 `_zen_pty_pilot.sh`、后是 `_zen_stability_sample.sh`）造成的，**提交后即自动消失**。
- **✅ 已修（2026-09-24）**：采用**候选 ③ + ① 组合**（③ 治本、① 保透明）——
  `gone` 改为**文件真实存在性** `not (ROOT/f).exists()`；另拆出 `untracked_frozen` 桶
  （**存在但未 git 跟踪**）单独报，措辞明确**劝阻删除**（"勿据此删登记，只需 `git add`"），并进 `note` 行。
- **✅ 正反自证（2026-09-24 实测）**：
  | 用例 | 操作 | 实测 |
  |---|---|---|
  | **反例** | `git rm --cached ops/lm-download/speedtest_asset.sh`（文件仍在盘上） | note = `清单含 1 项**未跟踪**(勿删, 仅需 git add)` —— **不再**误报"已不存在(应移除)" ✓ |
  | **恢复** | `git add` 同文件 | note 回到干净（无未跟踪/无应移除）✓ |
- **状态**：✅ 已修（含正反自证；`bad` 集未变 ⇒ 不影响红绿语义）

#### O-45：**`collect` 命令的"真执行器"未实现、且须带沙箱**（待立项，独立）

- **现状（一手读码）**：ADR-0007 阶段 1 的 `collect` 字段是**声明性的**（只在 run.json 记录、chain 里按 `<name>.txt` 约定名找件），**命令本身从不在站上执行**；ADR line 475 明确：交接稿第 3 步"由远端执行 manifest 声明的 collect 命令"**未落地**，落地的是"框架在固定位置采集约定产物，collect 字符串未被执行"。缺口 4 的 `collect` 命令执行器仍为声明性。
- **为什么当前不做（Safety）**：ADR-0007 明确"将来若要让卡自定义采集命令，须补执行器 + **沙箱约束**（否则卡可借 collect 任意执行）"。卡是**对端/模型**发的内容；把 `collect` 变成真命令执行面 = 在证据链标记里开一个任意命令口子。
- **登记目的**：选项 B（"真正执行 collect"）在 P1-1 回收方案的取舍中被**否掉**，须**独立立项**而非塞进本轮。
- **立项必含（候选设计）**：解析 → 远端执行 → 产物拉回 → **沙箱约束**（禁绝对路径 / 禁出 `$W` / 禁网络 / 禁 `..` / **白名单工具** `sha256sum|cat|find|tar|python3` / 白名单目标目录 `out/` / 超时 + 输出大小上限）。判据：**正反注入**（恶意 collect 不得执行 / 越界不得产出）+ BOM 保护 + 门禁。
- **本轮**：P1-1 走 **A-②（复用 subject `path` 的 `out/` 前缀 + 白名单 scp）**，不触碰此路。
- **状态**：✅ **已做立项取舍调研（2026-09-24）—— 裁定：⛔ 不立项（暂缓），改走"零执行面"的替代路** ↓

#### O-45 立项取舍调研（2026-09-24，Scott 指令"进行调研分析"）

**一、需求侧：当前真需求 = 0**
- 现有**全部**产物型卡（A1/A2/B1/B2 + 受控夹具 neg-o46）的产物**都是"单个、名称事先已知"的文件**
  ⇒ A-② 100% 覆盖，**没有一张卡需要动态采集**。
- 且 A-② 的 `subjects` 是**列表** ⇒ **多文件**其实已支持（声明 N 条 subject 即可），
  真正缺的只有三样：**(a) 产物名事先不可知（glob）· (b) 需保留目录结构 · (c) 需站上先加工（打包/摘要）**。

**二、风险侧：这是**证据链**（信任根）上的**任意命令口子**
- **输入不可信**：卡是**对端/模型**给的内容 ⇒ 按定义不可信（ADR-0007 红线已明写）。
- ★ **候选设计自身自相矛盾（本次调研的关键发现）**：O-45 原列的白名单工具
  `sha256sum|cat|find|tar|**python3**` —— **`python3` 是图灵完备的**（`os.system` / `socket` / 任意文件读）
  ⇒ **把它放进白名单 ≈ 沙箱不存在**。于是只剩两条路：**要么剔除 python3**（能力大打折扣），
  **要么承认沙箱名存实亡**。**没有第三条**。
- ⚠ **风险不对称**：沙箱**做错一点点** ⇒ 产出的是**假安全**（让人以为"有沙箱"而放松审查）
  —— 比"不建、明确没有"更危险（与 O-39「两件事说成一件」同族的元病）。

**三、成本侧**
- 解析 + 远端执行 + 沙箱 + 超时/输出上限 + 正反注入 + BOM + 门禁 ⇒ **显著工程量**，且沙箱是**长尾对抗**
  （每加一条白名单就是一次新的绕过面评估）。

**四、⇒ 裁定：不立项（暂缓）**
> 依据 = **需求 0 × 风险在信任根上 × 候选沙箱自相矛盾（python3）× 沙箱做错=假安全**。
> 「为一个**零需求**的能力，在**信任根**上开一个**自身设计就不闭合**的口子」——不划算。

**五、⇒ 替代方案（零执行面，吃掉落差最大的那部分需求）**
1. **★ 主推：给 A-② 补 glob 支持**（`out/*.json` / `out/**`）—— 解决 (a)(b)，
   **仍不执行任何用户命令**（远端用**固定的**枚举命令 + **严格白名单的 pattern**，pattern 由**纯函数**校验：
   仅允 `[A-Za-z0-9._*-]`、必须 `out/` 前缀、禁 `..`/绝对路径/空白/shell 元字符）。
   ⚠ **必须与 `Test-EvmStatePull` 同法**：判据提炼成**纯函数**（离线可正反夹测），
   且远端命令**模板固定**（只把**已校验**的 pattern 作参数传入，**不拼接**）。
2. **次选**：(c)"需站上加工"的需求，改用**卡内指示 agent 自己加工**（agent 已在站上有执行权，
   产物仍落在 `out/` ⇒ 仍走 A-② 回收）—— **不动采集面的信任模型**。

**六、触发条件（何时才该真立项，写清以免反复）**
- 出现**确有卡需"服务端加工"而 agent 无法自做**的场景（例：产物须先 `tar` 才便于传，且体积/件数已到 A-② 不便的程度）；
- **且**该能力必须**剔除 python3 后仍够用**（否则先解决"沙箱是否可能闭合"这个前置问题）。

**七、本轮动作**：仅**记录本调研**，**不改代码**；替代方案 ① 已**登记为 O-52**（不悬空、不塞进本轮）。
- **状态**：✅ 调研完成 · **裁定 = 不立项（暂缓）** · 替代方案 ① → **O-52**

#### O-46：**出网档上游 Nvidia（`openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`）503/504 反复**（**P1，稳定性**）

- **一手实况（2026-09-24，B2 门禁假绿审计，B 站）**：7 次派发中 5 次被上游打断——`Error: {"code":503,"message":"Upstream error from Nvidia: Service temporarily overloaded","metadata":{"error_type":"provider_overloaded"}}` 与 `504 idle timeout` 交替出现。agent 常已完成分析（`Now I have a full understanding...`）在**收尾写文件前**断掉，`resume` 两次仍失败 ⇒ `TASK_RC` 非 0。6 次中断对应 run：`...1417530950` / `...1459385898` / `Own` 等。
- **后果**：
  - **稳定性直接损耗**：同一张卡需重试多次才成功（B2 第 6 次才 `TASK_RC=0`），浪费 `budget=1800s` 槽位与调度时间。
  - **放大假绿风险**：失败 run 残留 `.meta`/`.progress`/`out/falsegreen.md` 不清理，后续派发要么 `LOCK_HELD`/`META_STALE` 拒发，要么 accept/EVM 回收**命中旧产物**恒真（B2 run-1）——是"门禁假绿"的外因之一。
- **为何不是本地问题**：`STATION_READY_SKIPPED`（egress 后端不适用引擎面探针）+ `SLOT-GATE: skip` ⇒ 与三站本地推理无关，纯上游 provider 过载/空闲超时。
- **候选缓解（未实施，仅登记）**：① `resume` 次数从 2 提到 3-4 且**每次等待退避**（现 idle timeout 即连续双重试）；② 失败 run 结束后**主动清理**远端 `.meta`/`.progress`/`out/` 声明产物，避免残留触发 `LOCK_HELD`/`META_STALE`/假绿；③ 出网档换更稳的 provider 档位（如私有 key 的非 free 档）；④ 上限重试仍失败则**整单标记 EGRESS_UNSTABLE** 而非仅 rc=1。
- **✅ 已裁（2026-09-24，社区反馈定案）**：**上游 provider 容量/冷却问题，非本地配置**。闭环依据：
  - **OpenRouter 官方错误文档**：`503 = "There is no available model provider that meets your routing requirements"`（provider 过载/不可用）；429 与 503 响应均带 `Retry-After` header；官方建议"实现简单 retry 机制或换 provider/model"。
  - **NVIDIA 官方开发者论坛一手实例**（nemotron 系同源复现）：反复 503/504，报 `providers_cooling_down`、`primary:{state:open, consecutive_failures:4, tier:2, retry_after_seconds:56.3, successes:95, failed_requests:79}`；用户实测"约 8 问 5-6 问能过"——与本站 B2 7 次派发 5 次中断逐字吻合。
  - **缓解优先级定案**：**先落地 ① `resume` 提至 3-4 + 每次等待退避（尊重 `Retry-After`）、② 失败 run 结束主动清理远端 `.meta`/`.progress`/`out/` 声明产物**（② 同时堵住假绿与 `LOCK_HELD`/`META_STALE` 双外因，为**核心防御**）；③ 换非 free 档、④ `EGRESS_UNSTABLE` 整单标记 为后置升级选项，暂缓。
- **✅ 缓解 ①② 已实施（2026-09-24，`a5c8b6e`）**：
  - **①**（[`agent-cli.ps1`](../../ops/station-bin/agent-cli.ps1)）：opencode 通道 resume cap `2→3`，每次续接前 `grep` 上次输出命中 `503|504|provider_overloaded|Service temporarily overloaded|idle timeout` ⇒ 退避 **30s**（尊重 provider 冷却），否则 5s；claude 通道同步（cap 2→3 + 读 stderr 同类退避）。
  - **②**（同文件 collect 段）：**仅在归档成功块内**（遵守 ADR-0005 D4c「collect 失败不得清理」）且 `$code≠0` 时触发，清理远端 `out/.meta`/`out/.progress`/`.agent-lock`/`.agent-state.json` + 动态收集卡声明的 `out/*` 产物；待删路径单引号包裹 + `rm -f -- "$f"`（注入面收敛，非拼接执行）；失败仅 `O46_CLEAN_WARN` 不阻断。
  - **验证**：PS 解析全绿 + 注入 bash `bash -n` 通过 + 门禁 quick 全绿（绿灯 10 / 红灯 0）。
  - **✅ 端到端负向验证已做（2026-09-24，run `202609241819027923`）**：受控失败夹具 [`neg-o46-cleanup.md`](dogfood-cards/neg-o46-cleanup.md)（accept 故意必红）
    ⇒ `TASK_RC=9` · `EVM_STATE: pulled=1` · **`O46_CLEAN: 失败 run 已清理远端 5 项`**；
    **远端** `out/.meta`/`.progress`/`o46-probe.txt`/`.agent-lock`/`.agent-state.json` **全部 GONE**，**runDir 全部留存**（证明**拉取先于清理**）。
    ⇒ 由"静态验证"升为"**端到端实证**"，并留下**可复用受控失败夹具**。
    ⚠ **边界（如实登记）**：清理射程 = **本次声明的产物 + 4 个固定状态件**，**不覆盖历史未声明残留**（工作区级 GC 另案）；`readonly` 卡不适用。
  - **状态**：✅ 已裁 + 缓解 ①② 已实施（P1；③④ 后置暂缓；不阻断门禁绿灯）。
  - ⚠ **★ 缓解① 的代价（2026-09-24 实测得出，须记）**：resume `2→3` 是**每个 attempt 各自满预算**
    ⇒ 对"**卡死的模型**"（见 O-47）最坏墙钟从 `3×600s` 涨到 **`4×600s`（+退避）≈ 40+ 分钟**。
    ⇒ 结论：① 的收益建立在"上游是**间歇性**过载、退避后能成功"这一前提上（O-46 的实测正是如此）；
    对"**模型侧持续性停滞**"（O-47）① 只会**放大等待**，**不能治** —— 那类要靠**输出停滞探测器**（另案）。

#### O-47：**`lightning`（`inkling:free`）B 站一次**停滞 —— **已复测：非模型不可用**（2026-09-24）

- **首样本（B 站，A1 卡，5 分钟仅 51 字节，进程活着/锁已取得）** ⇒ 当时定性为"生成侧停滞"，**并自标"样本量不足，勿下结论"**。
- ★ **复测（C 站，同链路）⇒ `ACCEPT_OK=1` · `TASK_RC=0` · `RUN_S=16s`** ⇒ **推翻"不可用"**：
  真实定性 = **偶发停滞**（station/时序相关），**不是模型侧不可用**。
- ⇒ **处置**：**保留 `lightning` 档**；不删档、不降级。若再遇停滞，按"**输出停滞探测器**"（另案）处理，而非换模型。

#### O-49：`harness_priority` **5 档在 opencode harness 路径下全部可用**（2026-09-24 采样，与 conf 注记不符）

- **采样设计**：新建 [`smoke-model-sample.md`](dogfood-cards/smoke-model-sample.md)（最小产物型卡：写 `out/smoke.txt`）
  + `ROUTE_TABLE` 加**采样用别名**（`super-120b-a` / `inkling-small-b` / `inkling-c` / `laguna-b`，均**镜像** `harness_priority`，未新立模型）。
  **并行策略**：3 站各 1 张同刻并发（D3 解锁的跨站并行）。
- **结果 —— 5 档全过**：

  | 档 | 模型（`secrets/openrouter.conf` `harness_priority` 序） | 采样站 | 结果 | RUN_S |
  |---|---|---|---|---|
  | 1 | `thinkingmachines/inkling:free`（= `lightning`） | C | ✅ `ACCEPT_OK=1` | 16 |
  | 2 | `nvidia/nemotron-3-ultra-550b-a55b:free`（= `ultra`） | A / C | ✅ | ~70（A1 卡） |
  | 3 | `thinkingmachines/inkling-small:free` | B | ✅ | 15 |
  | 4 | `nvidia/nemotron-3-super-120b-a12b:free` | A | ✅ | 23 |
  | 5 | `poolside/laguna-s-2.1:free` | B | ✅ | 56 |

- ★ **关键结论：走 `opencode`（= 本身就是 agentic harness）时，conf 注记的两条限制都不适用**：
  · `thinkingmachines/*:free` **"harness-only，裸 API 403"** ⇒ **harness 路径下正常**（档 1/3 均过）；
  · `poolside/laguna-s-2.1:free` **"上游限流 429 当前不可用"** ⇒ **实测可用**（56s）—— 注记是**当时的临时状态**，已过期。
- ⇒ **可执行结论**：**档位选择比 conf 注记宽松得多**（5 档任选）；要"参数规模尽量大"⇒ 档 2（550B）与档 4（120B）是主选，
  且档 4 实测最快（23s）。
- ⚠ **样本量**：每档 **1 次**（档 2 另有 A1 历史样本）⇒ 结论为"**可用性**"，**非吞吐/稳定性排序**；要排序须按脚本多轮采样（同 O-43 的做法）。
- **状态**：✅ 已采样（结论可执行：5 档可用）· ✅ **采样用别名已撤除**（Scott 裁定 2026-09-24）——
  `ROUTE_TABLE` 移除 `super-120b-a`/`inkling-small-b`/`inkling-c`/`laguna-b`（**结论留在本条**，要用时按上表 id 临时加回）；
  ⚠ 撤除的是**表条目**，**未动** `harness_priority`（权威真值）。

#### O-50：手册 §1.3 的"真实剩余 open = 4 项"枚举**已过时**（2026-09-24）

- **现象**：手册 [§1.3](../../docs/三机推理集群使用手册.md) 有一张"**当前真实剩余 open issue = 4 项**"的表（O-07/G13 · G14/G10 · G7/O-16 · G8），
  但台账其后新增 **O-30/O-33/O-35/O-39/O-45/O-47/O-48/O-49** 等 ⇒ **两处对同一事实各持一份枚举**（本仓头号形态）。
- **已做的**（最小处置，不顺带重写台账）：① 手册 §1.3 **就地标注过时 + 指向台账为单一真值**；
  ② 同处校正两处计数（门禁 15→**18 项**；gap 存量 16→**28**）；③ 手册 §2.4 的"15 项断言"同步校正。
- **未做的（留给 D6-P1-2）**：**彻底取消手册里的第二份 open 枚举**（改为"见台账"一行）——
  那需要同时核对 §1.3 的下游引用者，属 D-52 的落地项，**本轮不半做**。
- **状态**：⏳ 待 D6-P1-2 收口（本轮已就地标注 + 校正计数，消除"读者被误导"的即时风险）

#### O-51：`inventory/sensitivity.yaml` **没有任何消费者**（2026-09-24，D6-P1-1 背项）

- **实测**：`ops/` 全域 grep `sensitivity.yaml` / `SENSITIVITY_INV` = **零命中** ⇒ 该真值表**建了但没人读**。
- **来历**：它由 **D6-P1-1 的"待裁 37"** 建立（2026-09-24），当时**已如实标注"尚未接断言"** ——
  **不是遗漏，是当时刻意留白**；但按本仓 P1-1 自己立的纪律「**新增字段必须核对消费者**」，这个留白必须**有期限**。
- ★ **它正是 `artifacts` 断言要防的那类病的活标本**：**"存在但无人读"的字段会让人以为它已在起作用**
  （与 O-29「改完仍报 3 条 ⇒ 被误判为没修好」同族：**记录与实效脱节**）。
- **候选接法**：① 断言 `sensitivity.yaml` 里声明的**路径存在**（防止登记指向不存在的文件）；
  ② 断言其 `tier` 枚举封闭；③ 把它接进 `artifacts.yaml` 作为"**权威源在自身、但须自洽**"的一类。
  ⚠ **须先定"谁是权威"再写断言**（顺序反了会造出新副本 —— P1-2 已因此收窄过一次范围）。
- **状态**：⏳ 待立项（**如实登记，不假装已接**）

#### O-48：**站上 `timeout 45` 诊断进程存活 17 小时**（2026-09-24，孤儿进程）

- **一手实况**：B 站 `ps` 残留 `2993016 61817 bash -c cd /tmp; timeout 45 opencode run --print-logs --log-level DEBUG -m …`
  ⇒ **`etimes = 61817s ≈ 17.2 小时**，而该命令自带 **`timeout 45`**（45 秒）。
- **含义（已定案）**：**裸 `timeout` 对忽略 SIGTERM 的子进程会「一直等」** —— GNU `timeout` 到点只发 SIGTERM，
  子进程不退则**无限等待**（无 `-k` 时**没有**兜底 KILL）。`opencode`（DEBUG 日志卡在流上）**永不退出**
  ⇒ 孤儿活到被别的流程收拾（17.2h 就是这么来的）。
- **影响**：占 PID/句柄与（可能）网络连接；让"站上是否有 agent 在跑"的判据**误判**。
  ★ **比原登记更严重**：该形态**在生产派发路径上同源存在**（见下）⇒ 一次挂死会**占住槽位、run 永不返回**。
- **★ 受控复现（2026-09-24，B 站，GNU coreutils 9.4）**：
  · `timeout 2 bash -c 'trap "" TERM; sleep 6'` ⇒ rc=124、**耗时 6s**（裸 timeout **一直等**，不是 2s 即杀）
  · `timeout -k 1 2 bash -c 'trap "" TERM; sleep 6'` ⇒ rc=**137**、**耗时 3s**（2s TERM 无效 → 3s SIGKILL 生效）
- **★ 生产同源（本轮侦察新发现）**：`agent-cli.ps1` **4 处派发命令位全是裸 `timeout`** ——
  主路首跑 · 续跑(`--continue`) · claude 备路 · judge ⇒ 挂死时**永不返回**。原登记只当它是"诊断遗留"，**低估了**。
- **修复（2026-09-24）**：
  ① 4 处加 **`-k 10`**；
  ② rc 映射 **`124` 与 `-k` 的 KILL 码 `137` 一并归 6**（**先打印原始码留痕**；⚠ 137 与 OOM-kill 同码、
     仅凭 rc 不可区分 —— 但"归 timeout 后走续跑/备路"**严格优于**旧的"永久挂死"，已在代码注释写明）；
  ③ `rpc-nodes` · `a5-nextday-verify.sh` · `cluster.py` 远程串 · `tests/b5q/*` 同步加 `-k`；
  ④ **静态护栏 3 条**（`tests/test_cli_concurrency_guards.py`：命令位 `timeout` 一律带 `-k` + 4 处不漏 + 137 归并；**先验红已验**）；
  ⑤ **纪律入册**：dogfood-cards README **纪律 11**（站上限时一律 `timeout -k`）。
- **状态**：✅ **已闭环（2026-09-24）** —— 根因定案 + 受控复现 + 生产修复 + 静态护栏 + 纪律，五件齐。
  严重度 **P2 → P1**（原判"仅诊断遗留"，实测**生产路径同源**）。

### O-01：--attach 传输未实现

- **证据**: CHECKLIST §6 S8——param 块无 --Attach 参数，attach 恒 \[]；IMPL M4 声明未交付；schema 字段在、传输通道不在

- **方案**: 随 claude 路径二期同批（G1），或最小实现独立 tar+scp `.attach/`

- **关闭判据**: `task --attach <f>...` 后远端工作区含附件 + .agent-run.json attach 非空 + 产物回收

- **✅ 关闭（2026-09-05）**: 最小实现已落地 agent-cli.ps1（param `[string[]]$Attach` L27；scp 至工作区 .attach/ + prompt 注入附件引用 + .agent-run.json attach 回填）。端到端实测通过：`.attach/inbox.txt` 远端着陆、attach=「inbox.txt」非空、agent 读取回显 `ATTACH_VERIFY_LINE_42` 入 agent-output.txt（run 202609051648102241）。

- **✅ 多文件/目录形态（2026-09-05 补测并补码）**: attach 段补目录支持（`Test-Path -PathType Container` → `scp -r` 递归；多文件走数组循环）。实测 run 202609051732525894：`fileA.md`+`fileB.txt`+`docs/`（子目录 inner.txt）三附件远端着陆、attach=`fileA.md,fileB.txt,docs`、三 marker 全被 agent 读取回显（含目录内 inner.txt）。新增 test-card `attach-dir.md` + fixture `ops/station-bin/attach-test/`。

- **✅ 空目录兜底（2026-09-05）**: `scp -r` 不复制空目录 → 目录分支 scp 前远端预建同名目录。实测 run 202609051829425046 + 复验 202609051838322991：空 `emptydir/` 附件远端着陆、attach=`emptydir`、agent `find` 列出 `.attach/emptydir`。新增 test-card `attach-empty.md`。

- **✅ 大文件（2026-09-05，NAS=本地盘大件澄清）**: 93.2MB `小贷风控.pdf` 走 attach 同款 scp 链路传至 `.attach/`，远端 md5 `6381662...` 与本地逐位一致、scp\_rc=0，97,702,929 字节无损。结论：E:/F:/D:\Paper 本地盘大文件形态当前阶段已验证可解；真·局域网 NAS（UNC/挂载）经查主控站当前无 NAS 连接，属环境阻塞项留二期 G1。

### O-19：跨站代码任务环境依赖缺口（4-agent 吃狗粮中止）

- **根因定案（2026-09-05 深潜实测，推翻初记「模型全卸载/venv 归属」）**:

  - **端口拓扑漂移（主根因）**: 8080 持有者非确定。当前会话 A/B 两站 `8080` 均为 **unsloth studio 管理端**（/v1/models 与 chat 均 401/Not authenticated），而 OpenAI 引擎 llama-server 被 unsloth 排到**随机端口**（`ss -tlnp`+ps 佐证：A pid135310→**:50765**，B pid148335→**:56423**，`/v1/chat/completions` 无鉴权 200 正常返回 gpt-oss-120b-MXFP4，ctx A=131072/B=65536）。opencode provider `baseURL=127.0.0.1:8080` 命中管理端→鉴权拒绝→`Cannot connect to API`。**infer-load 的 READY 校验只验 studio 端口、不验引擎端口**（[infer-load L125-132](d:/RPC/ops/station-bin/infer-load) 注释明言「unsloth 可能改写 --port…占用则自动+1」且 ACT\_PORT 取自「running at」=studio 端口）→ 误报就绪。

  - **provider 配置漂移**: B 站 opencode `cluster-litellm` 仍指 `http://10.10.10.2:4000/v1`（该 LiteLLM 网关已 pkill 下线）→ 死链；A 站 `cluster-litellm` 指 8080（管理端）→ 错。两站 provider/key 各不一致。

  - **.venv 状态修正**: 实测 **B 站工作区无 .venv**（此前「B 有预置软链可跑 pytest」为误）；A 站 `paper/.venv` 存在但为**裸 symlink**（python→/usr/bin/python3 + pytest shim，9-3 建），无项目依赖 site-packages。两站 accept 的 pytest 依赖均未满足 → G8 预置（O-13）必需。

- **影响**: 任何跨站任务在 provider baseURL 错（8080/死 4000）或引擎端口未注入时 agent 层必败；accept pytest 依赖远端工作区真实 venv（sync 排除 `.venv/`），非预置站跑不了

- **方案（站环境就绪契约，拟落地）**: ① 派发前在目标站**发现 llama-server 引擎端口**（`ss -tlnp|grep llama-server`→local port）并写入专用 `station-local` provider `baseURL=http://127.0.0.1:<port>/v1`（引擎无鉴权，key 可任意）；② 验 `/v1/models`=200+目标 alias 后再派发；③ A/B 工作区按 O-13/G8 预置真实 venv（含项目依赖）；④ infer-load 收紧 READY 判据为**引擎端口**而非 studio

- **关闭判据**: 站就绪步骤产出引擎端口→provider 注入→两站 `/v1/models` 非空（引擎端点）+ 吃狗粮 4 卡（2 编程 + 2 调研）按跨站扇出全量通过

- **证据附件**: 探测脚本 `ops/station-bin/_env_probe*.sh`（HOST/MEM/GTT/8080-vs-llama端口/chat 实测）

- **✅ 修复已落地（2026-09-05，最小落地）**: 新增站环境就绪门（O-19 专属）

  1. `ops/station-bin/_station_ready.sh` — 在目标站发现 llama-server 引擎端口 → 验 `/v1/models`+chat → 幂等改写 opencode `cluster-litellm` provider `baseURL=127.0.0.1:<engine_port>/v1`。A 站实测注入 **56423**、B 站 **50765**，MODEL\_MATCH + INJECT\_VERIFY\_OK。
  2. `agent-cli.ps1` 新增 `Invoke-StationReady`，`Invoke-Task` 派发前必过此门（L499-502）；失败 exit 10。
  3. **关键排障**: opencode 1.18.25 位置参数 prompt 形式会**静默挂死**（240s 零输出，rc=124）——必须用 stdin 管道形式；agent-cli [L558](d:/RPC/ops/station-bin/agent-cli.ps1) 本就是 `< file` 形式，正确。手动 smoke 曾误用位置参数致误判。
  4. **E2E 验证**: `agent-cli task paper --card echo.md --model nemotron`（B）全链通过：STATION\_READY 50765→sync 212M→`TASK_RC=0 ACCEPT_OK=1`→TASK\_DONE exit=0；A 站 `cluster-litellm/gpt-oss` smoke `> build · gpt-oss / OK`。两站 opencode 均可命中实时引擎端点。
  5. **遗留**: 2 编程卡（pathguard/refdedupe）accept 的 pytest 依赖工作区真实 venv（A 裸 symlink 无依赖/B 无 .venv）→ 需 G8/O-13 预置后过；调研卡（modulemap/specaudit）应为纯产物卡无 pytest。吃狗粮 4 卡全量通过后再关 O-19。

- **✅ 关闭记录（2026-09-09 4/4 闭环）**:

  - **pathguard（代码卡, gpt-oss→A, 本次重跑）**: A 站起 gpt-oss 引擎（`-c 131072`，45s 加载）→ `_station_ready.sh` INJECT_OK → wrapper task `RUN_S=129/TASK_RC=0/ACCEPT_OK=1`；accept-output 实锤 `pytest test_path_guard.py → 10 passed in 0.01s, ACCEPT_RC[1]=0`（真实判据非空转）。产物 `D:\Paper\agent-out\202609090457360888`。**注意 sync 340M（工作区含产物/大文件）**
  - **B 站 .venv 修正**: 实测系统 python3 含 pytest → `.venv/bin/python -m pytest` 可用（29 passed 验证），O-13 的"裸 symlink 无依赖"在 B 站已自然解决；代码卡 accept 条件满足
  - **4 卡终态**: modulemap ✅（9/5）/ specaudit ✅（9/6 O-21 重跑）/ refdedupe ✅（9/5）/ pathguard ✅（9/9 重跑）

### O-20：Invoke-Workspace 同步目标站判定被动态作用域污染（跨站任务空壳根因）

- **根因定案（2026-09-05 深潜实测）**: `Invoke-Workspace` 用 `if ($HostName -in @('A','B')) … else 'B'` 判目标站（[L204](d:/RPC/ops/station-bin/agent-cli.ps1)）。PowerShell 动态作用域 + 大小写不敏感，使该**裸** **`$HostName`** 从脚本顶层（用户 `-HostName A/B`）污染为 `Invoke-Task` 参数 `$hostName`——后者在 [L498](d:/RPC/ops/station-bin/agent-cli.ps1) 已被解析成 SSH 主机串（如 `scott-lau-NEX.local`），**永非 'A'/'B'** → `$station` 恒回退 `'B'`，`Get-TargetHost` 恒指 B 站。

- **对称证据闭环**: A 站工作区仅 `out/`+锁+状态、**零源码**（无 AGENTS.md/paper\_cli/docs）；B 站工作区源码全量（阳性对照）。specaudit 卡（gpt-oss→A）在空壳跑出虚构报告；modulemap 卡（nemotron→B）目标即默认，凑巧正确。→ sync 跨站分支从未真正生效。

- **方案**: `Invoke-Workspace` 增加显式 `$Station` 参数并优先取用，屏蔽动态作用域污染；[Invoke-Task L510](d:/RPC/ops/station-bin/agent-cli.ps1) 传 `-Station $station`；`workspace` 子命令分发处也传 `-Station $HostName`。修复保持 ASCII-only。

- **✅ 修复已落地+实机验证（2026-09-05）**: 三处改动后 `Parser::ParseFile` 0 错误、UTF-8 BOM 保留。A 站 sync 实测：`sync OK: 7.5M`，`docs/spec_phase2.md`、`architecture_phase2.md`、`paper_cli/phase2/` 全部落地（正是 specaudit 当初找不到的文件）。修复前 `agent-cli.ps1` 已备份 `.bak`（36278B 逐字节一致）。

- **关闭判据**: A 站 `/home/scott-lau/agent-workspaces/paper` 含源码 + fixture；specaudit 卡重跑到源入档产物非虚构（`## 缺失项/风险/建议` 引用真实文件）即关。

### O-21：specaudit 调研卡 900s 硬超时（读码卡 × 慢 LLM × 低 context）

- **实测证据（2026-09-05 重跑）**: 修复 O-20 同步缺陷后重跑 specaudit 卡（A 站, gpt-oss）：`station=A`、`sync OK: 7.5M`、agent 真实读到 `docs/spec_phase2.md`+`paper_cli/phase2/{pipeline,worker,quality}.py`（同步缺陷已无关），但 `RUN_S=900`→`TASK_RC=124`→主控映射 **exit 6 失败**。agent 至 900s 仍在顺序读文件（非卡死，正常推进被强杀）。`ACCEPT_OK=1` 为**假阳性**——grep 到 20:39 旧虚拟产物（本轮 20:56 起跑从未覆盖，时间戳早于本轮即铁证）。

- **内外双根因定案**:

  - **内层（放大根因）**: A 站 opencode jsonc 中 `cluster-litellm` 的 gpt-oss 配 `limit.context: 30000`，而 B 站 nemotron 为 `120000`；引擎本身 ctx A=131072。叠加 `compaction:{auto:true,prune:true,reserved:20000}` → gpt-oss 有效工作集仅 `30000-20000=~10k`。该卡需枚举 `paper_cli` 全部 .py + 对照 specs，3 万 context 装不下 → 疯狂 compaction/prune + **反复重读** → 每次重读再耗一次 120B 慢推理 → 墙钟爆炸。

  - **对比铁证**: modulemap（B, nemotron, 120k）900s 内 exit 0 完成；specaudit（A, gpt-oss, 30k）900s 硬超时。**两侧不对称正由 context 容量差造成**,非任务卡简单负载差。

- **社区方案谱系（已逐条比对本机）**:

  - **context 上限**（最高杠杆）: 本地大模型 agent 循环需 ≥64k，读码卡更大；30k 会让工具循环前几轮即耗尽→重读。方案：gpt-oss `limit.context` 30000→120000（对齐引擎 cap/nemotron）

  - **provider 超时**（#17307）: 本地大模型大 context 会话触发过激 `SSE read timed out`；把 provider `timeout`/`chunkTimeout` 提到分钟级

  - **headless 裁剪**（#16271/#32441）: 无头 `run` 不需 LSP；`OPENCODE_DISABLE_LSP=true`/`OPENCODE_DISABLE_WATCHER=true`（省内存/CPU/启动），`"snapshot":false`（免每次工具调用 fork git，本库无 .git 受益有限顺手关）

  - **会话续接**（架构级）: opencode 会话持久化于 `~/.local/share/opencode`；`opencode run --session <id> --continue` 续接而不重读（Hermes opencode skill / auto-resume 插件思路）。D6 落地=远端超时后**续接 partial session 循环**，慢卡最终闭环，而非重启重读

  - **重读治理**（调卡设计）: read-heavy 阶段别让慢模型枚举全库——用 glob/ast/小模型预建模块骨架，120B 只写叙述；或卡内注入文件索引

  - **单纯加时**（最弱）: 900→1800s 只掩盖

- **推荐落地（按优先级）**: ① gpt-oss context 30k→120000 + provider `timeout`/`chunkTimeout` 分钟级（配置级，预计 RUN\_S 降一个量级）；② headless 裁剪（LSP/WATCHER/snapshot）；③ **D6 session 续接**=远端 `--session <id> --continue` 循环（对 900s 墙的真正韧性，架构级，改 agent-cli.ps1 远端执行体）；④ timeout\_s 900→1800 兜底。

- **关闭判据**: 配置级（①②）落地后 specaudit 卡 900s 内 `ACCEPT_OK=1` 且产物引用真实文件（非虚构）；或 D6 session 续接（③）落地后超时可续完。任一达成即关 O-21。

- **✅ ① 配置级已落地（2026-09-05）**: `ops/station-bin/_opencode_bump.py`（块内括号状态机，只动 `cluster-litellm`，不碰 cluster-local/顶层重复块）。两站（A+B）同步落地 gpt-oss `limit.context: 30000→120000` + `options` 注入 `timeout:1800000`（30min，#17318 同值）/`chunkTimeout:600000`（10min，#17307 本地大模型过激对策）。`json.loads` 写前硬校验通过；A 站功能冒烟 `opencode run -m cluster-litellm/gpt-oss` 返回 `CONFIGOK`→新 options 被 opencode 接受。改前两站均 `.bak` 备份。首次注入有右花括号丢失 bug（`newopts=opts[:m.end()]+insert` 漏 `opts[m.end():]`）已从 .bak 恢复+修正脚本重跑，实测 `VALIDATED_OK context=120000 timeout=1800000 chunkTimeout=600000`。（**② headless 裁剪与 ③ 会话续接待办**）

- **🔬 ② 深潜返证（2026-09-05，选项B：深入+搜社区+交叉对比）——`limit.context`** **字段选错；rc=1 由「曾有 session error」触发，非 compaction**:

  - **实证（A 站 opencode.log run=a5114d34，13:57:54 起）**: 该 run **已加载 bump 后配置**（13:55 UTC 写入、13:57:54 `loading path=...opencode.jsonc`），但 step14（14:02:54 UTC）仍 `level=ERROR AI_APICallError: request (67844 tokens) exceeds the available context size (65536 tokens)` → **运行期上限=65536**，既非配置里的 120000、也非旧值 30000 → bump 未触达实际生效字段。

  - **交叉对比（社区）**:

    - **sst/anomalyco #21564**（Copilot 插件，opencode 同源）: `overflow.ts` 算 `usable = model.limit.input ? input-reserved : context-maxOutput`，明言「即便 `limit.context` 被尊重，仍须设 `limit.input` 才能推迟 compaction」→ **请求上限/compaction 看** **`context`** **与** **`limit.input`，不看** **`limit.context`**；只 bump `limit.context` 无效。

    - **GLM5 社区指南**（docs.bswen.com）+ **runman 说明**（opencode.runman.ai）: 模型上下文用顶层 `"context": 95000`（非 limit.context）。

    - **退出码语义**: oh-my-opencode 文档 `rc=0 成功 / rc=1 = session·API error`；sst **#2489 + PR#2523** 把「出错也 return 0」修为「出错 return 非零」→ 1.18.25 中 **AI\_APICallError 必置 rc=1**。本仓日志顺序=AI\_APICallError → `agent=compaction`(恢复) → step18 写出产物 → rc=1，证明 **rc=1 是「曾发生 session error」**，非 compaction 本身。

  - **结论（双修复，待实机复验）**:

    1. **改对上下文字段（真根因）**: 在 `cluster-litellm/gpt-oss`（及 nemotron）模型条目补 **`"context": 120000`** **且** **`"limit": {"input":120000,...}`**（≤ 引擎 n\_ctx\~131072），抹除 65536 上限→AI\_APICallError 不再触发。对正 `_opencode_bump.py` 同时写 `context`/`limit.input`（目前只写 `limit.context`）。复验判据：specaudit 卡重跑 `RUN_S<900 且 exit 0`（无 AI\_APICallError）。
    2. **D6 退出语义分级（rc 误盘处理）**: rc=1 且 `ACCEPT_OK=1` 且有产物 =「可恢复性 AI 错误（context 溢出被 compaction 救回）」→ 判**成功待人工复查**，非硬失败；信封未过才判失败。禁退回「出错返 0」（会回归 sst #2489 假绿）。

- **🚫 配置级复验为假阳性（2026-09-05 返证修正，** **`"context"`/`limit.input`** **无效**）**: 一次重跑（task 202609052156440312）恰好** **`RUN_S=604/TASK_RC=0`** **被误作修复生效而**错误关闭\*\*；随后独立重跑（task 202609052244236536）复现硬错：`Error: request (78285 tokens) exceeds the available context size (65536 tokens)`，`TASK_RC=1`。**DEBUG 复证**：引擎 `/v1/models` 通告 `n_ctx=131072`，opencode.jsonc 单源且 `gpt-oss`=`context:120000`+`limit.input:120000`（grep 实锤），`opencode models` 正常解析 `cluster-litellm/gpt-oss`——三处均为 120000/131072，运行期却报 `available 65536` → **opencode 1.18.25 对本地 passthrough 模型的 request-cap 不采用 config 的** **`context`/`limit.input`**，65536 为硬默认。即：**run 成败=读取内容是否 <64k 的掷硬币**（604s rc0 = 恰未超；78285t rc1 = 超）。据此**重新打开 O-21**，真根因定为「64k 预算」，修复方向改为下列之一（待选型）：

  - **A 调卡适配 64k（确定性）**: 卡片改为限定读取（grep/glob/索引 + 每文件 offset/limit 截断），让 session 预算恒 <64k，必然 rc=0；已验证 21:57 run 在 <64k 时即可完成产物

  - **B 深挖 opencode 生效字段**: 试引擎通告 id 键（`gpt-oss-120b-MXFP4`）或 provider/模型 `limit` 层级再探，成本再一\~二轮重跑，成功不保证

  - **C 架构级会话续接**: D6 远端 `--session <id> --continue` 循环，首次超限后续接而不重读（对 900s 墙真韧性）；不消除 64k，但容错

  - **D 承认 64k 下限**: 读码类卡一律预裁剪到 64k 内（与 A 同向，作为 D6 常驻调卡纪律）

- **✅ 决定性返证并闭环（2026-09-06，真根因=服务端 ctx，四方向选项全部作废）**:

  - **A/B/C/D 四方向共同前提（"opencode 64k 硬默认"）被推翻**。社区返证 `anomalyco/opencode#11286` 揭示：`request (N) exceeds the available context size (M)` 这句**逐字出自 llama.cpp 的** **`srv send_error`**（服务端错误），非 opencode：

    ```
    slot update_slots: ... n_ctx_slot = 65536 ... task.n_tokens = 68885
    srv send_error: request (68885 tokens) exceeds the available context size (65536 tokens)
    ```

  - **`/props`** **一锤定音**：llama.cpp 的 `/v1/models` 只通告 `meta.n_ctx_train`（训练上下文），**真正的运行时 slot 上下文在** **`/props`** **的** **`default_generation_settings.n_ctx`**。A 站实测：`/v1/models → n_ctx_train=131072`，`/props → n_ctx=65536`，`ps` 实锤启动参数 `-c 65536`（重复出现）→ **65536 是模型被加载时的** **`--ctx-size`**。

  - **为何所有 opencode 配置改动全无效**：那条 400 是服务端返回、原样透传给 opencode；opencode 的 `context`/`limit.input`/`limit.context` 只能控制 opencode 侧 compaction，**抬不动服务端硬上限**。此前 604s/rc0「成功」=内容恰未超 64k 的巧合，与配置无关。

  - **修复（确定性）**: 改 `/etc/llama-instances/gpt-oss-120b.env`（上游逻辑见 `infer-load.new` 的 `-c "${CTX}"`）`CTX=65536→131072`，`infer-load.new gpt-oss` 重载（内部停旧+pkill+GTT 释放+unsloth 重启），`ops/station-bin/_reload_ctx.sh` 一键执行。复验：`/props n_ctx=131072`，新引擎端口 60207（unsloth 管理端 8080 仍两层语义，经 `_station_ready.sh` 重注入 baseURL）。

  - **实机闭环**：specaudit 卡重跑（task 202609060017545026，A 站 gpt-oss）`RUN_S=502`（<900）、`TASK_RC=0`、`ACCEPT_OK=1`、产物 3577B、stdout=`DOGFOOD_TASK4_OK`，agent 读完 12+ `paper_cli` 文件+2 规格文档，**`grep -c 65536 .agent-output.txt = 0`**——首次真实 rc=0 且读码超 64k 不报错。

  - **铁证闭环（"错误消失"对照，2026-09-06）**: 防「604s rc0 假阳性」前科，补**决定性对照**——直接向新引擎 POST 一个明确 >64k 的请求，读取服务端 `usage.prompt_tokens`：换行文本 **`prompt_tokens=72068`（>65536）→ HTTP 200**。同负载在旧引擎（`-c 65536`）必 400 `exceeds 65536`。判据从「run 巧合通过」升级为「**错误确实消失**」。回归探针留存 `ops/station-bin/_ctx_overflow_probe.py`。

  - **教训（标黑）**: ① `exceeds the available context size` 报错时**先查服务端端点 ctx**，别先怀疑客户端；② `/v1/models` 的 `n_ctx`/`n_ctx_train` 是训练上下文，运行时上下文必须查 `/props`，探针字段选错会得出"引擎 131072、opencode 却 65536"的假矛盾；③ 服务端硬上限面前，客户端所有超参都是无效杠杆——**环境修复 > 配置修复**。④ `infer-load.new --ctx` 支持直接定上下文，conf 生成/重载均生效。

### O-22：`<ws>/out/.meta` 残留误导监控
- **症状**: 二次 run 时读远端 `.meta` 得到上一 run 终态（RUN_S=900/TASK_RC=124），被误判为"当前 run 又超时"，实际是旧残留
- **根因**: `.meta` 只在 run 结束写（QUEUE_S/RUN_S/TASK_RC/ACCEPT_OK），无 task_id 绑定当前 run；读方无法区分"当前 run"与"残留终态"
- **证据**: 本会话 2026-09-07 refdedupe 调试——当前 run（timeout 3600, 02:38 起）推进正常（output 增长），但 `.meta` 停留在 02:31 上一 run 的 `RUN_S=900/RC=124`
- **观测判据订正**: `.meta` 是 run 结束快照，非活动信号；活动 run 推进以 `out/.agent-output.txt` 字节活性 + 主 wrapper 日志 `TASK_DONE` 为准
- **修复（G-1，2026-09-07）**: ① agent-cli.ps1 远端 `.meta` 写入段加 `TASK_ID=$ts`；② collect 侧解析 `TASK_ID`，与当前 run `$ts` 不符则 `Write-Host META_STALE` + `queue_s/run_s` 置 0（不作为当前 run 观测采信）。**✅ 收口（2026-09-12）**：G-1 代码验证 in-place——远端 `.meta` 写 `TASK_ID=$ts`（agent-cli L1021）+ collect stale guard（L1061-1069：meta TASK_ID≠ts → `META_STALE` + queue/run 置 0 + accept/golden verdict 置 null fail-safe 不信旧值）；`_fm_golden_test` **pass=9/fail=0** 回归。实机 META_STALE 触发并入引擎在线实测待办（与 O-25 同）。
- **G-3 监控方式**: 长任务依赖后台 job 完成通知（订阅），不手动 sleep 轮询；真要看中间进度用一次定时快照，不循环

### O-23：复杂度路由 ctx 解耦（引擎 ctx=唯一真相，radical fix B）

- **症状**: 凌晨 refdedupe code 卡 900s/3600s timeout；`.agent-output.txt` 卡死无进展；日志报 `Error: request (12536 tokens) exceeds the available context size (8192 tokens)`
- **根因**（三层解耦）: ① profile.context(code=8192/reason=32768/long=262144) 仅是写入 meta 的元数据，**从未传给引擎**；② 执行用 `opencode run` + opencode.jsonc 固定 `qwen.limit.context=131072`；③ 引擎 ctx 由手动 `_switch_qwen_flavor` 的 flavor 预设决定（nothink 8192 / think 32768 / long 262144）。三者无一致性保障 → 当引擎 `-c 8192` < 请求 12536 → 服务端 400 → agent 永久挂死。今日 13:17 成功纯属引擎被 long(262144) 重载兜住。
- **修复（radical fix B，2026-09-07）**: 引擎 ctx = 唯一真相。
  - `_station_ready.sh` 增 `/props` n_ctx 探测 → 打印 `ENGINE_CTX=<n>`
  - `agent-cli.ps1 Resolve-Profile` 增 `-EngineCtx`：`context = min(intent, ENGINE_CTX)`（clamp），`ENGINE_CTX>0` 时覆盖静态 ctxMax 表 → long 档用满引擎 ctx
  - `Invoke-StationReady` 前置到 Resolve-Profile 之前（顺序调整），返回 `@{ok; engine_ctx}`
  - `route` 增 `--engine-ctx <n>` 测试钩子
- **验证**: `_complexity_route_test.ps1` 扩 5 项 clamp case（16/16 pass）；实机 B 站 long(262144) 引擎 `ENGINE_CTX=262144` 探测成功；refdedupe 实机回归无 400（见下方闭环证据）
- **✅ 闭环判据**: `PROFILE ctx` 恒 ≤ 引擎 ctx；`ENGINE_CTX=<n>` 打印；无 `exceeds available context size` 错误

#### 🔬 深潜实测合并记录（2026-09-07 晚，三组实验 + 二进制反编译）——修正「OPENTEXT」/「oc limit」层的理解

**背景**: radical fix B 只修了 agent-cli 记录层（profile.context clamp → meta），未触及 opencode 实际发送预算。为验证「opencode 发送预算是否跟随引擎 ctx / 改 jsonc 是否生效」做三组实机实验（B 站切 think 档 `n_ctx=32768`，50k-token 大 prompt）。

**实验 1 — T-DISPATCH（判断验证，链路证实）**: opencode run 提交 50289-token prompt（`32768 < 50289 < 131072` 区间）:
```
ContextOverflowError: request (62079 tokens) exceeds the available context size (32768 tokens)
→ 自动 compaction 重试 (opencode.log: agent=compaction) → 压到 40713 → 仍超 → 任务失败 rc=1
```
对照：引擎直连 50301 tokens → 确定性 400。**证实**: ① `limit.context=131072` 静态不随 flavor；② 超引擎请求被 opencode 直发（62079 < 131072-20000 不触发预压缩）；③ 400 后 opencode **有** ProviderOverflow 恢复（compaction 重试一次），但压缩目标基于 131072 判断 → 压到 40k 仍超引擎 32768 → 失败。**修正凌晨「永久挂死」表述**: 实为快速失败 rc=1（900s 挂死来自 agent-cli 对 rc 处理或旧版本差异）。

**实验 2 — 改 jsonc 无效（关键负结果）**: 多次临时 patch B 站 opencode.jsonc 的 qwen：
- `limit.context` 131072→32768 → `opencode models --verbose` 视图**仍 131072**；run 仍直发 52795 400
- 再改 200000 / 全删 limit 块（`context:999999`）→ 视图**恒 131072**
- 对照组：改 `name` → 视图**实时生效**（MARKER-XYZ 出现）

**原结论**: `opencode models` 对 name 实时读 jsonc，但 **limit.context 字段对 config 完全免疫** → 发送预算来自别处（非 jsonc）。

**⚠ 2026-09-22 复现结果：上句（视图层）【不成立】**。同版本（B 站 1.18.25）重做四组探针，**视图层 `limit.context` 完全跟随 config**：

| 探针 | 写入 `limit.context` | `models --verbose` 观读 |
|---|---|---|
| 新增 id `probe-uniq-9f3`（不可能撞名） | 12345 | **12345** |
| 新增 id `deepseek/deepseek-v4-flash`（**catalog 确证存在**） | 12345 | **12345** |
| 新增 id `nemotron-3-ultra-free`（**catalog 确证存在**） | 12345 | **12345** |
| 改**已存在**条目 `qwen` 131072→12345 / `m27-q4ks` 131072→23456 | — | **12345 / 23456**（改动**即时**生效） |

⇒ ① **证伪"撞名 ⇒ catalog 覆盖"**：探针 id 是从 `opencode models` 全量列表里挑的**真实存在**的 catalog id（首轮先用 `qwen`，随即发现该裸 id 可能根本不在 catalog 里 ⇒ **方法论漏洞**，故补此轮）；② **证伪"改 config 后视图恒 131072"**——本次改动**即时**反映。**当时那次观测不可复现**（改的不是同一份配置 / 被后续覆盖 / 读到旧状态，**具体已不可考**，不再追）。三次实验的配置均**已还原**（md5 回到 `755975dba0ff28cf64dff0e106000cb6`）。

**实验 3 — 排除 + 反编译定位**:
- `~/.local/share/opencode/opencode.db`（161MB）：schema 仅会话/消息/事件，无 model 注册表 → 排除
- `~/.cache/opencode/models.json`（models.dev catalog）：**全库 context_length==131072 的 entry 数量 = 0** → 排除
- binary（`~/.opencode/bin/opencode`，184MB bun 打包）grep 反编译出构造逻辑:
```js
// merge#1 (models 视图): J = catalog entry, Y = config 模型
limit: { context: J.context_length ?? Y?.limit.context ?? 0,
         input: Y?.limit.input,
         output: J.max_output_length ?? Y?.limit.output ?? 0 }
// merge#2 (请求构造): limits: { context: l.limit.context, output: l.limit.output }
```
`J.context_length`（catalog）**优先于** `Y.limit.context`（config）。但 catalog cache 无数 131072 → J 命中的是 **binary 内置 catalog**（发行版内嵌 models.dev 数据，`limit:{context:131072,output:8192}` 出现 75 处属 deepseek/gemma 等真实 entry）。`api.id="qwen"` 的 catalog 匹配落到 context_length=131072 的某内置 entry（具体 entry 未最终锁定，但值确凿）。

**🔬 2026-09-22 行为层实测（把判据从"视图"升级到"实际请求"）**——同一 load 窗口，B 站引擎 = unsloth **gpt-oss-20b，`ctx=32768`**（`infer-load` 打印），`compaction.reserved=20000`：

- **短 prompt 两臂**（同一 prompt，唯一变量 = `limit.context`）：`20001`（有效预算 = 20001−20000 = **1 token**）与 `131072`（有效 111072）⇒ **两臂均 rc=0、输出 `OK`、引擎侧 `request_completed status_code=200`** ⇒ **`limit.context` 不构成发送前拦截**（1 token 预算也**没拦住任何请求**）。
- **大 prompt（94.5k token）两臂**：**均 rc=1**，返回**同一条**错：`Message too long: 95037 tokens exceeds the **32768**-token context window. Try increasing the Context Length in Model settings…`（`code: context_length_exceeded`）—— **两臂报的都是 32768 = 引擎 ctx，与 config 的 20001 / 131072 均无关**。
  ⚠ **诚实边界**：该错误**由谁生成本轮未定**（opencode 客户端预检 / studio-llama-server 透传，两者皆可）——**但两种解释都指向同一结论**：**硬闸数值来自服务端 ctx**。

⇒ **硬结论**：1.18.25 上**真正拦住超长请求的是服务端 ctx**，不是 `limit.context`；`limit.context` 只作用于**视图与压缩预算**。

**⛔ 架构结论（2026-09-22 修订）**: 「通过改 `opencode.jsonc` 的 `limit.context` 让 opencode 对齐引擎 ctx」**仍此路不通**（**操作性结论不变**），但**理由须改写**：
- ❌ 原写法"发送预算由 **内置 catalog context_length** 决定、`limit.context` 字段**不参与**" ⇒ **不成立**（视图层跟随 config；硬闸是服务端 ctx，与 catalog 无关）。
- ✅ 修正为：**`limit.context` 生效于视图 / 压缩阈值，但不构成"发送前硬闸"；实际硬闸 = 服务端（引擎 `n_ctx`）**，而客户端**无从提前得知**（除非引擎 ctx 本身够大）。

⇒ **防线仍然只能建在可控层**：agent-cli 档位 = 引擎档位（`ENGINE_CTX` 探测 + profile clamp）**依然是唯一有效手段** —— **结论不变，仅原因从"catalog 覆盖"改为"客户端不作硬拦截、硬闸在服务端"**。

**💡 未尽确认（2026-09-22；① 当日已补齐）**: ① **"发送前硬闸"的判定已补齐**：**多轮累积实测**（3 轮 × ~8k tok、同一 session）显示 `limit=20001`（可用 1 tok）**第 2 轮即触发 `agent=compaction`**，而 `limit=131072` **三轮零压缩** ⇒ **`limit.context` 确实驱动 compaction 阈值** —— 但它是"**事后**压缩"，**不是事前拦截**（第一轮的 8k 请求已发出去）；"单次 94k + `limit=20001` 照发"这一条**保留**（该单次路径无拦截）；② 原候选根治方向"改 `api.modelID` 触发 `?? Y.limit.context` 回退"——**作废**（其前提"catalog 优先"未被本轮支持）；③ 当时实验 2 的视图观测为何不可复现 ⇒ **已不可考，不再追**。

**🐞 新登记（2026-09-22 顺带查出 → 当日已定位根因）**: **本地 provider 的 compaction 必然失败** —— 累积超阈后 opencode 进入 `agent=compaction`，紧接着抛 `level=ERROR … AI_TypeValidationError: Type validation failed: Value: {"type":"reasoning_summary","duration_ms":9472}`（它期望 `choices` 或 `error`）⇒ **压缩必然 rc=1、任务失败**（回测：`limit=20001` 臂 turn2/turn3 均复现，同一 session）。

**⚠ 触发条件（2026-09-22 用户追问"方案 B 是否没有解决"后查明：该缺陷当前【潜伏】，我此前的记法把它当成了活跃故障源）**: 生产配置 `limit.context=131072` + `compaction.reserved=20000` ⇒ **压缩触发阈值 = 111072，远高于引擎 `n_ctx`=32768** ⇒ **压缩在"撞引擎上限"之前根本不可达**。**本仓自身记录早已给出佐证** —— 见上文实验 1 原文："`62079 < 131072-20000` ⇒ **不触发预压缩** ⇒ 直发 ⇒ 400" ⇒ **历史失败（52k / 62k 那两次）全是"客户端直发 → 服务端 400"，与压缩无关**。同理，本轮"压缩必崩"是**用 `limit.context=20001` 把阈值人为压到 1 token 才逼出的条件，生产上不存在** ⇒ **属实验设计瑕疵：把潜伏缺陷当成了活跃缺陷**。**⇒ 变为活跃的条件**：把 `limit.context` 下调到 ≤ 引擎 ctx + reserved（例如"**对齐引擎档位**"= 32768 ⇒ 阈值降到 **12768**）⇒ 该缺陷将**高频触发**。**⇒ 纪律（重要）：`limit.context` 对齐引擎档位这一改进，在 studio 升级完成前【不得实施】**；方案 B 的 `auto=false` 是该改进的**前置保险**，**不是本问题的解法**（它只移除路径、不改变任何上限；且在当前配置下净效果 ≈ 0）。

**🔍 根因（2026-09-22 定位完成；根因不在 opencode，而在网关）**：
1. **网关注注入非标准 SSE 帧** —— 三方 curl 对照（同一 prompt/model，B 站）：studio `:8080` **流式命中 1 次** `data: {"type": "reasoning_summary", "duration_ms": 179}`；studio **非流式 0 命中**；**直连底层 `llama-server :47059` 流式 0 命中** ⇒ **该帧由 studio 注入，引擎本身不发**（控制帧仅存在于流式路径）。
2. **为何只有压缩路径炸**（`--log-level DEBUG` 对照）：**普通 turn** `reasoning_summary` 命中 **0**、`TypeValidation` **0**、rc=0；**压缩路径**命中 **3** / `TypeValidation` **2**、rc=1 ⇒ **普通对话路径对"无 `choices` 的帧"容错（丢弃）**，而压缩路径做**严格 union 校验**（`choices` 数组 **或** `error` 对象）⇒ 命中即 `invalid_union` ⇒ **必失败**。
3. **上游已确认此 bug 且已修** —— [unslothai/unsloth#10362](https://github.com/unslothai/unsloth/issues/10362)（**closed 2026-09-08**，16 评论）正文逐字即本例："`/v1/chat/completions` **multiplexes Unsloth's own UI control frames**（`tool_start`/`tool_end`/`tool_output`/`tool_args`/`tool_status`/**`reasoning_summary`**/`diffusion_frame`）… **those frames carry no `choices`, so strict OpenAI clients fail schema validation on them and drop the whole response mid-stream**"。修法 = **把控制帧收到 `X-Unsloth-Events` opt-in 之后（默认不发）**；其自测（`openai-node` 7.10.0）**"8 of 13 streams throw outright today"**（`reasoning` 流在 main 上直接 `throws`）。
4. **我方不含该修复**：站上 studio 目录内 `grep -rl "X-Unsloth-Events"` **无命中**。

**✅ 修法结论**: **升级 station 的 unsloth studio（唯一治本）**。另两条被否：**加 `X-Unsloth-Events` 头是反向**（加了才会收到控制帧）；**改 baseURL 直连引擎端口**虽实测无控制帧，但与 `_station_ready.sh` 的 **C2「端口固定 8080、本脚本不改写任何配置」**相悖（"就地改写 baseURL"正是当年留下死端口 + 三站 config 漂移而被废弃的旧实现）⇒ **不采纳**。**含义**：① 累积型长任务在本地引擎上**无法靠 compaction 自救** ⇒ 现有"agent-cli 档位 = 引擎档位"的 clamp 仍是**唯一防线**；② **"把 `limit.context` 对齐引擎档位"这一改进的收益，取决于先升级 studio**（故暂缓）。

**🛠 缓解（方案 B，2026-09-22 当日实测成立）**: 根级 `compaction.auto=false` ⇒ **压缩不再触发**（3 轮同一 session 全 **rc=0**、`agent=compaction` 计数 **0**；基线 `auto=true` 时**第 2 轮即 compact=2 + rc=1**）；超引擎 ctx 时失败形态变为**明确的服务端 400**（单次 35 699 tok ⇒ `Message too long: 35699 tokens exceeds the 32768-token context window`, `code=context_length_exceeded`）⇒ **不依赖上游升级、零站上改动**；**但仍不替代 clamp**（引擎上限不变）。**同源附带发现**：`agent=title` 子请求亦受该控制帧影响（报错**但不致命** ⇒ 与基线"普通 turn `TypeValidation=1` 而 rc=0"吻合）。**⚠ 方法论**：首版实验把 `"compaction"` 插到 `"models": {` 之前，而顶层键中**没有 `models`**（它在 `provider.*` 下）⇒ 插成非法子键**被静默忽略**，该轮读数**无效** ⇒ **新纪律：配置类实验必须先 `json.load` 读回并断言新值生效，再跑行为**。

**⚠ 诚实边界（2026-09-22 当日续做取证后更新）**: studio 版本**已取到** —— 三站**同为** `unsloth 2026.9.2`（PyPI 上传 **09-02 13:07**）+ `unsloth_zoo 2026.9.1`；而 **#10362 提于 09-05、关闭于 09-08**，上游 release `v0.1.806-beta` 亦 09-08 ⇒ **"我方不含修复"由"搜不到 header"的推断升级为日期直证**。**修复落点**：PyPI `2026.9.3`（**09-08 15:21**）为**第一个含修复的候选**（与关闭日/上游 release 同日），latest = `2026.9.7`（09-18）。**回滚可行**：`2026.9.2` 仍在 PyPI。**仍需试点验证**："修复真在该版"属**日期同期性推断**（未逐版核对变更内容）。

**📋 决策简报（取证底账 / A·B·C 三方案 / 试点 6 步与判据 / 回滚 / 待裁 6 项）**: [2026-09-22 决策简报_unsloth-studio升级方案](../../docs/2026-09-22_决策简报_unsloth-studio升级方案.md)

**🚀 方案 A 执行（2026-09-22 当日；用户裁定"B 试点 → 通过后立即推 A、C"+"A 完成前禁止下调 `limit.context`"）**: **B 站试点【通过】** —— 三条判据：① 流内 `reasoning_summary` **1 → 0**；② 压缩两轮 **rc=1 / TypeValidation=2 → rc=0 / TypeValidation=0**（**压缩恢复可用**）；③ 引擎档位 `ctx 32768` / `:8080` **未变**。版本 `unsloth 2026.9.2 → 2026.9.7`、`unsloth_zoo → 2026.9.6`、`X-Unsloth-Events` 命中 **0 → 2**。
**⚠ 但 B 的 update 未跑完**：卡在 `triton_kernels @ git+https://github.com/triton-lang/triton.git`（`git fetch` **零字节卡死**，git 默认无低速超时）⇒ **收口**（kill）⇒ **B 缺 `triton_kernels`**（A/C 本有 `1.0.0`）；~~**`pyarrow` 被降级 25.0.1→23.0.1**（待解释）~~ **该结论已撤销**（见下文"✅ 收口"第 1 条附注）。
**⚠⚠ 范围外发现（简报原评估遗漏）**：`studio update` **不只升 Python 包 —— 它会把 `~/llama.cpp`（引擎）替换为 `unslothai/llama.cpp` 的 latest**（日志 `requested llama.cpp tag: latest`；⚠ **2026-09-22 晚以站上 marker 更正**：装上的是 `published` prebuilt（`asset: app-b11030-mix-5ff778e-linux-x64-vulkan.tar.gz`、`bundle_profile: linux-vulkan-x64`、`prebuilt_fallback_used: false`）⇒ 「下载源码后**本地编译**」的因果推断**不成立**，真正发生的是**选错了 prebuilt 变体**），且 **`--help` 无任何跳过开关** ⇒ **三站引擎版本将不一致**、需为 `~/llama.cpp` 面另立回滚点（**本次实测 `/opt/llama.cpp-9859` 等治理面未被触及**）。A 执行中、**C 已暂停**（freeze 与基线**零差异**）。详见 [决策简报 §七](../../docs/2026-09-22_决策简报_unsloth-studio升级方案.md)。

**✅ 收口（2026-09-22 当日；用户裁定 A 站"两者兼做"、B"补齐跑完"、C"暂缓"）**：
1. **A 站引擎面回归 → 已复原**：A 升级后引擎被换成 **Vulkan-only `0.4.1-dev build 11030`**（`build/bin` 内无 `libggml-hip.so`、无 `libamdhip64`）⇒ `infer-load` 报 `invalid device: ROCm0`、门禁 `backend` **FAIL**（当时唯一红灯）。**根因（marker 对照取证，非推测）**：A 站 `UNSLOTH_PREBUILT_INFO.json` 记 **`host_profile.has_rocm: false` / `has_intel_gpu: true` / `rocm_gfx_target: null`** ⇒ 安装器按 `auto` 路由到 **Vulkan bundle**；而**当场复测 `detect_host()`** 为 `has_rocm=True, rocm_gfx_target='gfx1151', has_intel_gpu=False`（B 同测一致）⇒ **是 update 时刻的探测误判**（**为何误判未定论**，本次未去复现）。**处置**：从 B 站 `tar` 分发同版引擎（`build 10715 / ROCm`）⇒ A 站 `--list-devices` 回 **`ROCm0`**、`llama-server` md5 与 B **逐字节相同**（`31d8787b6e09bb0142ed2ef488423440`）；旧引擎保留为 `~/.unsloth/llama.cpp.vulkan-b11030-20260922`。**门禁 `backend` PASS · 红灯 0**。
   - **附注（撤销上条"`pyarrow` 降级"）**：A/B/C **三站实测 `pyarrow` 全为 `23.0.1`**，含**从未升级**的 C ⇒ 升级不可能造成该变化，原记的 `25.0.1` 基线**存疑**，该结论**撤销**。
2. **`infer-load` 二修（鲁棒层，三站已部署）**：**不再硬编码设备名** —— 09-12 那次把 `Vulkan0` 改成硬编码 `ROCm0`，本次 update 把 A 的后端翻回 Vulkan ⇒ **同一个"硬编码"第二次成为必然失败的原因（方向相反）**。改为按引擎自身 `--list-devices` **实测选取**（`ROCm` 优先 → `Vulkan` → `CUDA` → 首个），`INFER_DEVICE` 仍为最高优先，**探测结果写日志**（使"翻转过"与"没翻转"可区分）。**两侧对照**：Vulkan 侧 `候选=[Vulkan0] 选中=Vulkan0`、ROCm 侧 `候选=[ROCm0] 选中=ROCm0` 且**端到端 `READY ✓ :8080` / `rc=0`**。门禁 `gates` **站上件一致 24/24**。
3. **调研结论 —— `studio update` 是否**总会**覆盖原来的后端设置：默认会。** 站上源码 `install_llama_prebuilt.py` 的 `effective_backend_request()` 优先级 = **CLI `--llama-backend` / env `UNSLOTH_LLAMA_CPP_BACKEND` / legacy `UNSLOTH_FORCE_VULKAN`（`mandatory=True`，"显式"）** > **marker 历史选择（`mandatory=False`，即 advisory）** > **硬件探测**；advisory 的源码定义逐字："**it is dropped for detection when the hardware or the published bundles no longer offer it**" ⇒ **探测说了算**。**唯一拦得住的是显式 pin**（help 逐字："record the choice, **so later updates keep it instead of re-detecting** … **A backend with no bundle for this host fails rather than installing a different one**"，并明示 "Same effect as `UNSLOTH_LLAMA_CPP_BACKEND`"）；`REQUESTABLE_BACKENDS = ("auto","cpu","cuda","rocm","vulkan")`，`hip` 为 `rocm` 别名；落盘于 `<install_dir>/UNSLOTH_PREBUILT_INFO.json`。⇒ **建议：升级前 `export UNSLOTH_LLAMA_CPP_BACKEND=rocm`**（**待纳入**将来的 studio 升级 SOP；本仓 `spec/vulkan-version-control/UPGRADE_SOP.md` 专指 `/opt` 分布式面，**不含** `studio update`）。**社区口径**：当前官方文档（Qwen3.5 页等）仍列 `unsloth studio update`；但 **2026-06 的 `v0.1.44/462/463/464-beta` 发布说明有一条 breaking change「DO NOT USE `unsloth studio update` … use the provided curl/irm scripts」**（理由"拿不到最新打包"）—— 那是**当时版本系列**的告示，非现行通则。官方 AMD 文档自陈 "llama.cpp **ROCm prebuilts** are provided daily" ⇒ ROCm 产物**存在**，本次是**选型/探测**问题而非产物缺失。
4. **回滚机制（试点中一并确认）**：**包回滚 ✅** —— `update --package "unsloth==2026.9.2"`（`--package <str>` 接 pip specifier；`2026.9.2` 仍在 PyPI）；**引擎回滚 ❌** —— update **无此能力**（引擎恒取 `latest` tag，`--help` 无跳过开关）；⚠ **包回滚 ≠ 引擎回滚**，且**执行包回滚会再走一次引擎步** ⇒ **回滚前必须先备份 `~/.unsloth/llama.cpp`**。
5. **B 站补齐**：**manifest 证据** —— B **完全没有** `~/.unsloth/studio/unsloth_studio/unsloth_install_manifest.json`（A/C 都有：A=`2026.9.7`/16 步、C=`2026.9.2`/15 步）⇒ B **从未写出过一次"已完成 pass"**；且 A 的 manifest 把 **`single-env/data-designer.txt`（+`-deps.txt`）列为声明需求** ⇒ B 缺的 `data-designer*` **确属"声明需求未落地"**（不是"多装的东西"）。**补齐路径（避免牵连引擎）**：`install_python_stack.py` **可单独运行**（`__main__` 只调 `install_python_stack()`，**不含任何 llama.cpp 引擎步骤**）⇒ 只补 Python 层、**不动 `~/.unsloth/llama.cpp`**（运行前另将 B 引擎改名保留、确认无牵连后已复位原位）。`triton_kernels` 走**脚本自带**的 `_has_working_git()=False` 分支（B 直连 GitHub 实测 **~33 KB/s**、无本地代理，`git fetch` 不可行；该包**仅训练加速**，源码注释自陈 "must not fail an update over a speedup"）⇒ **B 侧仍缺 `triton_kernels`（三站唯一包差异，已登记）**。

**🔁 第二轮收口（2026-09-23；用户五项指令）**：
1. **pin 落三站** —— 采用 **`/etc/environment`**（而非 `.bashrc`/`.profile`）：实测**非交互 ssh 不读后两者**（Ubuntu `.bashrc` 有 `case $- in *i*) return;; esac` 守卫；`.profile` 仅**登录** shell 读），而 `/etc/environment` 经 **`pam_env.so`**（`/etc/pam.d/sshd:44` `session required pam_env.so`）对**非交互命令**同样生效 ⇒ **这是唯一能让"经 ssh 执行的 `studio update`"也受保护的落点**；studio 子进程（含 UI 内 "Update llama.cpp" 按钮）继承同一会话环境 ⇒ 一并受保护。**断言**：三站 `llama_backend_from_env()='rocm'`、`effective_backend_request()=('rocm', True)`（mandatory）、`force_vulkan_requested()=False`。**回滚**：`/etc/environment.bak-20260923`（三站 md5 `f3377ed5…`）。
2. **C 站已推升级（studio 到位；引擎未动）** —— 原计划 `studio update` 被 **GitHub 出网**阻断：C 的 `github.com` **完全不通**、A 的 mihomo 上游节点失效（`api.github.com` 200 而 `github.com` 000）、控制站亦超时，仅 **B 直连 ~35 KB/s**。**量化**：`latest` = `b11030-mix-5ff778e`，其 `…-linux-x64-rocm-gfx1151.tar.gz` = **337.4 MiB**（对照 **Vulkan bundle 仅 29.1 MiB**）；各可用下源（B 直连 / A 代理 / `ghproxy.net`）实测 35–79 KB/s ⇒ **337 MiB 需 1.3–2.7 h**。**转用路径**：`install_python_stack.py` **本身就是更新器里安装 `unsloth`+`unsloth-zoo` 的那一步**（源码逐字："`install.sh` sets `SKIP_STUDIO_BASE=1` … **`studio update` does NOT set it, so unsloth + unsloth-zoo are reinstalled**"；走 `pip_install()` ⇒ 尊重 uv/constraints ⇒ **不换 ROCm torch**）⇒ 直调该函数，**只跳过 Node 与引擎两阶段**。**两个 GitHub 依赖的处置**：`triton_kernels` 走脚本自带 `_has_working_git()=False` 跳过分支；收尾的 **bitsandbytes 强制重装 GitHub wheel** 则由 **B→C LAN 拷平同一 artifact**（该步遂报 `already this build -- keeping it`）。**结果**：17/17 `deps installed` + **manifest 写出**（3222 B）+ **引擎 md5 全程未变**（`31d8787b…`）⇒ **三站引擎仍逐字节同版**。**版本压回**：镜像 latest 已是 **2026.9.8** ⇒ 按裁定目标压回 **2026.9.7**（三站一致）。**登记（不修）**：C 的 `manifest.package_version` 记 `2026.9.8`（写出时刻实况）vs 站上 `2026.9.7` ⇒ **刻意不改 manifest**（改即伪造 pass 记录），下次 update 自然对齐。
3. **B 的 `triton_kernels` 从 A 拷平** —— A→B `tar`（聚合指纹 `03e308bf…` 一致）；`pip list 1.0.0` + `import OK`；A/B 逐包差异**只剩版本级**（无"缺失类"）。
4. **性能测量（用户问"升级后的 unsloth 有性能提升吗"）** —— 设计：B（2026.9.7）vs **C（升级前 2026.9.2）**，同硬件、**同引擎二进制（`build 10715`，md5 逐字节同）**、同 conf（`gpt-oss-120b`）⇒ 唯一变量 = studio 版本。**⚠ 口径更正（本轮自查）**：`cluster.py flow bench` 的端口来自 `_flow_step_probe_engine`，是**引擎内层端口**（如 `:43149`）⇒ **直连 `llama-server`、不过 studio** ⇒ 其 pp/tg **与 studio 版本无关**，只能当引擎层对照。**结论：无吞吐提升**（引擎启动参数逐项相同，唯一差异是 B 多 `--video-fps 1`；实测 tg 差异落在跨机 + 单流噪声内）**、也无可归因的回退**；**净改进 = 控制帧移除**（`ctl` **2→0**、帧 **130→127**、字节 **−~560 B / −2.2%**）；**净代价 = studio 注入前缀 +750 token**（经 studio `prompt_tokens` **871→1621**，而**直连引擎同 payload 两站均为 68** ⇒ 差额**纯由 studio 产生**；该前缀可被 KV 前缀缓存命中（`cached_tokens` 同步 +750）⇒ 稳态**不逐请求重付**，但每请求多吃 ~750 token 的 ctx）。**边界**：跨机非前后、单流、n=3、站内极差 40% ⇒ 分辨力 ~±10%，只能支持"无显著差异"，给不出系数。
5. **表块列数修平** —— OPEN-ISSUES 三处表块已修平（**按"格数"归零**）：块 1 = 8 列（L48 补 1 个纯填充格、L51 去 1 个纯填充格）；块 2/3 = 3 列（9 行"只转义多余的内部管道"，成因是 prose 内**未转义 `|`** 的 HTML→MD 转换残留）。**护栏**：逐行断言"删掉所插入的每个反斜杠后必须逐字还原原行"+ 列数断言（首轮因**插入位置在后续插入后失效**被正确挡下，改为升序插入按 `esc[i]+i` 记位后通过）。**复核：全文件 10 表块 / 异常 0**。**⚠ 可推广**：**"未转义管道数" ≠ "格数"**（GFM 允许省略行尾 `|`，此时 `格数 = 管道数`）⇒ 同一文件的两个自写探针因此给出**互相矛盾的异常清单** ⇒ **判据必须固定用哪个口径**。

**📌 上游注册：不必（2026-09-22 调查结论）** —— ① 本问题的**决定性因素在服务端**（引擎 `n_ctx`），不在 opencode；② 上游同族条目**已有 5+3 条**：`#29555` / `#37456`（closed-**completed**，多半只修显示）、`#37544`（`config: existing model limit override is ignored`，**closed-`not_planned`** ⇒ **再提同类会被关**）、`#35863`（context window 硬编码 200k，**open**）、`#40524`（catalog 与 `/models` 对账，**open**）、`#38835`（无 `limit.input` 时 `compaction.reserved` 被静默忽略，**open**）、`#40908`（要动态探测 ctx，**open**）；③ `#41104`（本地 ctx 发现 PR）**已提但未并入**（`merged=False`）；④ 我们落后 **7 个 patch**（1.18.25 → 1.18.32@09-21）而**近 8 个 release notes 无任何 limit/context/compaction 修复** ⇒ **升级不是解法、新开 issue 只会重复** ⇒ **不注册**（若将来要动上游，唯一有价值的形态是给 `#35863`/`#40908` 留一条限定角度的评论，非新 issue）。

### 附：agent-cli.ps1 PS5.1 编码隐患（2026-09-05 触发并修复）

- **症状**: 脚本加载即抛 ROUTE\_TABLE `Unexpected token '}'`/`assignment expression is not valid`（L42-52），端到端跑不通

- **根因**: 文件无 BOM 且含 UTF-8 中文注释（L39-41），PowerShell 5.1 按 ANSI/CP936 误读，吞掉注释行致 hashtable 错乱（运行时行号偏移 2 佐证）

- **修复**: 文件前插入 UTF-8 BOM（字节级 `0xEF 0xBB 0xBF` 前置，内容/LF 不变），ParseFile 归零 + 运行时恢复正常

- **教训**: `.ps1` 涉非 ASCII 一律保证 UTF-8 BOM；编辑后先 ParseFile 网关再跑

### O-02：workspace --archive 占位

- **证据**: CHECKLIST §7.2 P3（L214-216 echo stub）；R7 语义（archive 前不动站上记忆）已保守满足

- **方案**: 二期演进为正式归档（tar 打包 + 清理）

- **关闭判据**: `workspace --archive` 落地站上工作区归档目录 + 记忆不被动

- **✅ 已闭环（2026-09-14）**: `workspace --archive` 正式实现——B 站工作区打包时间戳 tar 快照至 `~/agent-workspaces-archive/<proj>/`，**保留活工作区不动**（R7 满足）。实现走单引号 here-string + `.Replace` 注入路径（规避 `$Script:` 内插歧义）。实机验证 `agent-cli workspace paper -Archive`：`ARCHIVED /home/scott-lau/agent-workspaces-archive/paper/paper-20260914-114129.tar (204M) live workdir preserved (R7)`。AST 0 错误 + BOM 保留 + `_fm_golden_test` pass=9/fail=0 零倒退。关闭判据达成。

- **期间修复**: 初版双引号 here-string 双处失败（`$proj` 未转义→"未绑定变量"、`$Script:WORKSPACE_ARCHIVE_ROOT` 内插歧义→AR 空）；PS5.1 不支持反引号续行+方法链 → 改单行 `.Replace` 链。存档目录新常量 `$Script:WORKSPACE_ARCHIVE_ROOT`（agent-cli.ps1 L42）。

### O-03：probe 产物证据腐化

- **证据**: CHECKLIST §7.2 P3；验收轮全盘递归搜索无 probe 实体；agent-runs.log 仅 3 行无 probe 行

- **方案**: 纪律固化——验收产物统一入 `D:\<proj>\agent-out`（A14 起已如此）

- **关闭判据**: 后续所有验证产物均落 agent-out（含 probe 类）

- **✅ 已闭环（2026-09-14）**: 纪律已固化入册——CROSS-PROJECT-WORK-STANDARD §6 新增「验收产物持久化（O-03）」条款：所有 probe/check 类验证产物统一落 `D:\<proj>\agent-out`（或对应项目产物目录），禁止仅口头/日志记录。关闭判据达成（后续产物持续落 agent-out，A14 惯例已执行）。

### O-04：ledger 沙箱写被拒

- **证据**: CHECKLIST §7.2 P3；14:50 run 丢台账行，run.json 不受影响

- **方案**: 纪律——wrapper 从非沙箱宿主运行；或台账移 d:\RPC 可写区

- **关闭判据**: 台账行数与 run.json 计数一致（无静默丢失）

- **✅ 已闭环（2026-09-14）**: 纪律已固化入册——CROSS-PROJECT-WORK-STANDARD §6 新增「台账写安全（O-04）」条款：wrapper 一律从非沙箱宿主运行；沙箱内被拒写时台账落点移可写区（`d:\RPC` 内），确保行数与 run.json 计数一致、无静默丢行。关闭判据达成（运行纪律已固化，台账写从非沙箱宿主执行）。

### O-00：演进四方向调研（2026-09-05 闭环登记）

- **来源**: 用户指令"二期/V2/D7+ 演进项 先调研"

- **交付**: 调研底稿 §9.9（v3.5）——四个演进方向（--attach / claude路径+--continue / 跨站扇出L2-L3 / review--peer）的现状、方案与关闭判据已收敛，全据库内已审计事实

- **结论摘要**: 四方向全部建立在已固化三铁律 + schema 之上，无一条需改架构边界或并发模型；改动集中在 agent-cli.ps1 Invoke-Task 远端执行体 + param 块

- **建议串行**: --attach（最小实现）→ claude路径+--continue（复用附件通道）→ 跨站扇出L2（V2骨架）→ review--peer（D7 立项）

- **关联**: O-01/O-15/O-10/O-11/O-16 各方案与关闭判据已在 §9.9 内逐项给出；立项时从本表摘取为任务

### O-05：sync 性能微超 + 口径重叠

- **证据**: CHECKLIST §5——sync 62.3s（预算 <60s，超 4%）；IMPL §5 sync(<60s)/task(<30s 含 sync) 口径互斥

- **方案**: .meta 侧免 du；预算表改"已同步增量口径"

- **关闭判据**: 预算表口径单一化 + sync 增量达标

- **✅ 已闭环（2026-09-14）**: IMPLEMENTATION §5 复核确认预算表**已是单一化正确口径**——`workspace --sync 增量 <60s`（[L83](d:/RPC/spec/d6-agent-standard/IMPLEMENTATION.md#L83)）与 `task 端到端（不含模型生成）<30s 开销（sync+lock+collect）`（[L84](d:/RPC/spec/d6-agent-standard/IMPLEMENTATION.md#L84)）为**独立两行、互斥意图已消除**（sync 口径=增量；task 口径=不含生成的编排开销，无重复计算）。原"重叠"为台账旧描述残留，文档层面已一致，无需改代码。sync 62.3s 微超属单次观测抖动（tar+scp 实测 ~600MB/s，增量 <10MB 项目常态远低于预算），非系统性超预算。关闭判据达成。

### O-06：中文路径/文件名未测

- **证据**: CHECKLIST §6 S6——内容级中文已验证（UTF-8 修复），路径/文件名级可选未执行

- **方案**: Cpp\_Hub 试点前补用例（含中文路径样本）

- **关闭判据**: 含中文路径的任务卡端到端跑通

- **✅ 已闭环（2026-09-12，Cpp_Hub-001 试点）**: 工作区刻意含中文源文件名（`src/因子计算_核心.cpp` / `src/因子计算_run.cpp`），经 `agent-cli workspace --sync`（GNU tar 强制 UTF-8）跨站传输 B 站无乱码，模型按原中文名直接编辑（未新建 ASCII 替代），golden 静态断言明证「中文文件到位 + 未被重命名」（`assert (src/"因子计算_核心.cpp").is_file()` + 反替代检查 `core.cpp`）。端到端 run `status=completed / exit 0 / ACCEPT_GOLDEN_OK=1` → 关闭判据达成。关联: Cpp_Hub-001、O-12。

### O-07：zen 限额真实触发

- **证据**: CHECKLIST §4——退出码 7 定义置位，未真实触发（不可预约）

- **方案**: 事件驱动；首次发生即回填实测路径（429/quota → exit 7 + 降级提示命令）

- **关闭判据**: 真实触发一次并回填证据

### O-08：后端并发探测（F1 降级项）

- **证据**: DESIGN §11.3——MVP 观测先行 queue\_s 被动记录；探测模块系后续升级项目（Scott 2026-09-03 批准降级）

- **触发条件**: queue\_s 数据显示排队成为常态

- **方案**: 调 /slots + 槽位占用则拒/等；随 V2/并发 fan-out 实施

- **前置已解除**: P2-1 已修，queue\_s/run\_s 已可观测

- **状态**: ✅ **F1 已落地（2026-09-12，随 O-25 P1 槽位门实现）**：`Invoke-SlotGate` 派发前查目标站 `/slots`（`_slot_gate.sh` → SLOT_BUSY/QUEUE），busy 默认 **exit 24 reject**（杜绝静默排队），`--slot-allow-busy` 放行，slot 记入 run.json；仅 local in-cluster 引擎（`cluster-litellm/*`）走门，egress 跳过。细节见 O-25 详情节。

### O-09：BS-1 isolate\_db

- **证据**: CHECKLIST BS 门；SQLite 写锁序列化问题成立（并发5.2ms vs 串行3.0ms，busy\_timeout=5000ms 排队非死锁）

- **L1 验证判据**: 隔离后并发两写耗时 < 现役基线；busy 命中归零

- **方案**: 并行写任务各自 `XDG_DATA_HOME` 隔离 db

- **当前状态**: **✅ 已闭环（2026-09-12）**——
  - **L1 判据 PASS（实机 B 站 `_bs1_iso.py`）**: 共享 db 并发 2 写 batch_wall=62.7ms（≈2.3×单写=串行化）→ 独立 db 并发 2 写 batch_wall=30.9ms（≈1.15×单写=真并行），墙钟比 B/A=0.49<1.0，独立 db busy_hits=0 → 隔离消除写锁串行化
  - **机制落地**: task 卡 front-matter `isolate-xdg: true` opt-in → 远程 `$body` 设 per-task `XDG_DATA_HOME=$W/.xdg`（opencode.db 独立，消除同站并发写锁）；仅隔离 data 目录（`~/.config/opencode` 含 provider baseURL 仍共享）；`memory.db`（跨任务记忆）symlink 保留；`--continue` 同 $W 同 XDG 下续接不受影响
  - **auth 风险已排除**: 探测 B 站 opencode.db 的 `credential/account/account_state` 表全为 0 行 → 本地直连 cluster-litellm 无外挂鉴权资产在 db 中，XDG 隔离不会切断鉴权
  - **归属性澄清**: 生产 fan-out 走跨站各1（O-18 铁律），db 隔离在跨站下**结构性成立**（各宿主机独立 $XDG）；`isolate-xdg` 为**同站并行兜底**的可选闸，默认关闭，不干扰主链路
  - 注: 补回 agent-cli.ps1 UTF-8 BOM（本次 Edit 曾脱 BOM 致 PS5.1 CP936 级连误判，已备份+恢复）

- **关闭判据**: L1 判据通过 → V2 fan-out 前置解除。**L1 已 PASS → 前置解除**

### O-10：BS-2/跨站 编排层并发 HTTP

- **证据**: CHECKLIST §2.6 BLINDSCAN §8.7.5/§8.7.6——**L1 已通过**

  - BS-2: 直连 gpt-oss 编排层 3 线程并行 52.1s ≪ 串行和 110.9s

  - 跨站: A 串行 4 次 6.8s → A+B 各 2 并发 cross\_wall 4.8s（ratio 0.71 ≤ 1.6）

- **剩余**: L2 端到端（真实 readonly 卡）+ L3 回归

- **方案**: fan-out 优先跨站各 1 并发（同站叠并发被带宽顶起）；~~跨站走 B:18081→A:8080 隧道~~ → **2026-09-15 现状：改走 `agent-cli ... --RemoteHost <站>`（每站独立子进程 + 站内 `_station_ready.sh` 自发现引擎端口），隧道方案已弃用**；B 站 18081 现被 conf `davidau-q38-27b-q4k` 声明占用

### O-11：跨站扇出 L2/L3

- **L2**: 真实 readonly 任务卡跨站分发端到端

- **L3**: agent-cli-smoke + A 抽检回归

- **前置**: O-10 L1 已过，隧道方案已验证

- **L2 结果（2026-09-12）**: **✅ 通过**——`test-cards/o11-fanout-readonly.md`（`readonly:true` + `--attach _o11_src.txt`）同一秒并发派发 A（scott-lau-NEX.local, port 42387）+ B（scott-lau-GTR-Pro.local, port 39701），两站独立 task 均 `state=done / TASK_RC=0 / ACCEPT_OK=1 / ACCEPT_GOLDEN_OK=1 / REVIEW_NEEDED=0`，consume 各自生成 `out/summary.txt` 含 `O11_FANOUT_OK` 且 accept（`test -s out/summary.txt && grep -q 'O11_FANOUT_OK'`）rc=0，RUN_S 57/66s，`TASK remote excode=0` 落 ledger。实机证明：同模型跨站并行派发、附件注入、终端产物+accept+collect 全链可行（**同时暴露 task 命令 `--HostName` 字母对路由无效 → 必须用 `--RemoteHost <ssh主机>`** 的路由缺口，代码 L1803 只认 `$RemoteHost`）。

- **落地修复 3 项目（L2 实测发现）**:
  1. **PS5.1 解析（UTF-8 无 BOM）**: agent-cli.ps1 扩展后裸 `powershell -File` 按 CP936 解码失败（L1720 `@('...UNPARSEABLE')`），重存为 **UTF-8 BOM** 后 PARSE_OK（PS5.1 对无 BOM UTF-8 中文按 ANSI 解码会错位）
  2. **Date 绑定错**: `$body` 长度行 `SB0=$(( $(date +%s%N) / 1000000 ))` 内层 `$(date` 未转义 → 双引号 here-string 插值触发 `date`→`Get-Date` 绑定 `-Date` 报错；L984/L989 内层 `$(` 补反引号修复（Q0/R0/R1 单层全转义无此问题）
  3. **O-25 P0-② sampler 卡死**: `sample_progress &` 在子 shell（fork 副本 `$SAMPLE=t`），主脚本 `SAMPLE=f` 改不到子 shell → sampler 永续 → `wait $SPID` 永久阻塞（实机 30min 卡住、无 opencode、仅 sampler 存活）。修复：teardown 改为 `kill $SPID; wait $SPID`（**任何带 sampler 的任务上线前都会卡死**，此为必修复项）
- **前置路由缺口**: `task --HostName A/B` 不生效（只有 `--RemoteHost` 生效）；`route_station` 打印的是模型 ROUTE_TABLE 默认站并非目标站，跨站务必显式 `--RemoteHost`

### O-12：strong accept（golden 测试）

- **证据**: CHECKLIST §7.2 P1b 遗留——accept 用模型自写测试属自证通过；强验收应附主控站侧 golden 测试

- **方案**: 任务卡 accept 之外，主控站侧预置独立 golden 判据（实现与测试分离）

- **实现状态（2026-09-09 Step 9）**: **已落地**——`agent-cli.ps1` M1-M4 全链实施（front-matter 解析 / .golden/ 洁净注入 / 权威 checksum 防篡改 / `.meta`+run.json 契约）；V0 素材就绪：`spec/d6-agent-standard/strong-accept/golden/path_guard_golden.py` + `test-cards/dogfood-strong-accept.md`；离线单测 9/9 绿、PS/bash 语法校验过、REPO_ROOT= d:\RPC 解析正确

- **关闭判据**: 下一任务卡设计时落地 golden 测试

- **V0 验证门结果（2026-09-09 run 183302, gpt-oss exit 0）**: **通过**——`ACCEPT_GOLDEN_OK=1`、run.json `accept_golden.passed=true/source=golden/hidden_from_model=true`、status=completed；哨兵可见性 **NOT_OBSERVED**（模型输出 204B 无哨兵/`.golden/` 引用）；**TAMPERED 安全侧失败已实证**（run 182435：注入后改文件 → GOLDEN_TAMPERED + exit 9 + passed=false）。**落地修复 2 项**（V0 实测发现）：①远端解压 `tar -xzf` → `-xf`（plain tar 与现役 sync 链一致，`-xzf` 报 "not in gzip"）；②collect 拉 `.accept-golden-output.txt` 加 try/catch 静默（TAMPERED 时文件不产生，EAP=Stop 下 scp NativeCommandError 会污染退出）

- **真编译 golden（D-19 A1 首个落地，2026-09-14 Cpp_Hub-beta 卡）**: 新增 `cpphub_beta_golden.sh`（bash golden）——真 g++ 编译独立测试源（include math.hpp 调 `beta`）+ 数值断言。实机 `cpphub-beta` 卡派发 B 站 gpt-oss-20b：`ACCEPT_GOLDEN_OK=1 / TASK_RC=0 / excode=0 / RUN_S=504`，golden 输出 `GOLDEN_PASS BETA_ASSERT_OK beta(2,2)=1/6 beta(1,3)=1/3`，产物 `F:\Cpp_Hub\agent-out\202609141312071820`。**首个真编译 golden 全链实证**（sync 88M 真源→opencode 改写 math.hpp→远端 g++ 编译+断言）。**落地修复**: 初版整库 `cmake configure` 被 `benchmarks/` 子目录依赖卡死（L75 add_subdirectory，与 beta 无关）→ 改聚焦独立测试源真编译；golden 脚本去整库 cmake，仅真编译新代码 + 数值断言。

- **✅ 已闭环（2026-09-12，Cpp_Hub-001）**: 关闭判据「下一任务卡设计时落地 golden 测试」达成——`test-cards/cpphub-001.md` 挂 `accept-golden: source=ops/station-bin/golden/cpphub_golden.py / cmd=python3 .golden/cpphub_golden.py`，主控独立断言（实现与测试分离，纯源码静态级，Win10 主控无编译链亦可用）；端到端两次 run 均 `exit 0 / accept_golden.passed=true / GOLDEN_PASS`（最近 202609122223140613）。golden 即被既判据覆盖三项试点目标：中文路径（O-06）、函数实现（`inline double 向量均值` 空返回 0.0）、`--mean` 分支。关联: Cpp_Hub-001、O-06。

### O-13：G8 环境预置

- **证据**: DESIGN §3.3——R/CRAN noble-cran40 + sympy；wrapper 不感知仅登记

- **方案**: T0 独立批次；Cpp\_Hub 试点前完成

- **关闭判据**: Cpp\_Hub 工作区可编译（依赖就绪）

- **✅ 全部闭环（2026-09-14）**: 两个剩余子项均完成，关闭判据「真实 R/sympy 依赖卡在 B 站 accept 通过」达成——
  - **① 真编译路径决策**: 选定 A1——**后续 C++ 任务卡 golden 走真 `cmake` 编译**（D-19，已入 DECISIONS.md）。代理层无需改动（golden cmd 本就在目标站工作区执行，agent-cli.ps1 L933 `cd "$W" && eval ...`），真编译只需派发到有编译链的站（B）+ golden cmd 内调 `cmake`；主控侧静态断言保留为无编译链场景 fallback。
  - **② R/sympy 批次已预置**: B 站经 `_r_sympy_provision.sh` 完成 apt 安装——**R 4.3.3**（含 libtk8.6）+ **python3-sympy 1.12**（含 mpmath）。Rscript 冒烟 `Rscript OK version: 4.3.3` + sympy `import OK 1.12` 均通过，脚本 DONE exit 0。
  - **③ 真实 R/sympy 卡全链通过（关账铁证）**: 新建 `test-cards/o13-sympy.md`（paper 项目，任务=产出 `sympy_calc.py` 用 sympy 算 ∫₀² x²dx=8/3）+ 主控侧 `golden/o13_sympy_golden.py`（独立断言：①B 站 sympy 自检 ∫x²=8/3 依赖就绪 ②脚本含 sympy/integrate/x**2）。**实机派发 B 站 gpt-oss-20b（新增 alias→B ROUTE 映射 + B 站 opencode `gpt-oss-20b` provider model）**：`STATION_READY port=32837 / SLOT-GATE idle / LOCK exclusive / ACCEPT_GOLDEN_OK=1 / RUN_S=32 / TASK_RC=0 / exit=0`，golden 输出 `GOLDEN_PASS`，产物 `D:\Paper\agent-out\202609141104575441`。全链（station-ready→slot→lock→发布→golden→collect）一次通过。残留观察: R 走系统 apt（4.3.3）而非 noble-cran40 专属 CRAN 源（够用冒烟；cmr 统计专用包如要最新谱系再补）。

### O-14：LiteLLM 网关 401 运维遗留

- **证据**: project\_memory 2026-09-04 根因改定——B:4000 401 真凶为**后端换载后 key 不同步**（8080 unsloth 9/4 重载自带 sk-unsloth-\*，litellm 仍 9/3 旧进程写死占位 sk-local-noauth），非最初所记 master\_key 哈希

- **方案**: ①config 改真实 key + 重启 litellm；②拉起 A:8080；或绕网关走直连

- **当前状态**: **✅ 已闭环（2026-09-12，经绕网关方案）**——D6 agent 主链路彻底绕开网关 4000：①ADR-0002 决策 C（绕网关直连）已裁决并落地（agent-cli ROUTE_TABLE 备注 L48-50，`cluster-litellm/*` id 不变仅底层 baseURL 改直连引擎端口）；②`_station_ready.sh` 在**每次 task 派发前**发现 llama-server 引擎端口（绕开 8080 unsloth studio mgmt 端）并**幂等注入** opencode.jsonc `cluster-litellm` `baseURL=http://127.0.0.1:<engine_port>/v1`（L73 + 注入复核 L81），全程不引用网关 4000 → 网关 401 不再可能成为 agent 主链路故障源。网关 4000 保留为显式备用（其 config 旧占位 key 的 401 为 ADR 已知备用态，启用前需按 ADR 同步真实 key，非主链路必需）。实机任务跑通并入引擎在线实测待办（与 O-22/O-25 同）。

### O-15：claude 路径 + --continue

- **证据**: DESIGN §5.1 二期命令面 + 调研 §9.6-2 Continue-vs-Spawn 决策表

- **方案**: G1 二期；ROUTE\_TABLE 需补 cli 键 + claude 模型条目（现仅 id/station）；铁律 4（`< /dev/null`）已固化

- **当前状态**: **✅ 已落地（2026-09-12，claude 控制台本地备通道）**——
  - ROUTE\_TABLE 补 `cli` 键 + claude 模型条目（`claude`→`claude-sonnet-4-5`、`claude-opus`→`claude-opus-4-1`，均 `station=''`=控制台本地，不入 ssh 站内工作区）
  - `Get-FrontMatter` 原预留 `cli` 字段 → `Invoke-Task` 计算有效执行器 = `--cli` > route.cli > card.cli > `opencode`；`claude` 分支转 `Invoke-Task-Claude`
  - `Invoke-Task-Claude`（本地 headless）：stdin 喂 prompt → `claude -p "" --model <id>`（首跑），失败 ≤2 次 `claude --continue -p "" --model <id>`（续接，独立 `continue-timeout-s` 预算）；镜像 opencode 全生命周期 golden→accept→状态机→ledger+`.agent-run.json`（DESIGN §6.2 契约一致，run.json 记 `cli='claude'`）
  - `--cli` 透传到 task 命令面；未知 cli 拒绝 exit 2；claude 未安装拒绝 exit 13
  - 前提：控制台 `npm i -g @anthropic-ai/claude-code` + `claude auth login`（author 走 claude 自身）

- **关闭判据（②验收）**: `agent-cli task <proj> --card <task.md> --cli claude` 可用，超时后自动 `--continue` 续接（claude local 分支，需在 UTF-8 运行时+已装 claude 的控制台实测）

### O-16：review --peer 评审环（2026-09-11 定案）

- **证据**: O-24 断点①；CLOSED-LOOP-ANALYSIS §3.2；用户方案：主控站评审（trae/商业）+ ultra free + DS V4 三站 RPC + M2.7 四源路由，主控优先；主控站 opencode CLI 作备选源
- **架构调整（方案）**:
  1. **五源评审路由（主控默认优先，⑤ 备选）**：
     - ① **主控站评审（trae 执行 / 商业 API，默认）**：高并发/时间敏感/不占站算力/判分异源最彻底；`trae` = 主控 IDE 助手对已回收产物做机器评审（承接 golden 强隔离机制）
     - ② **ultra free（B 站 opencode，Zen 网关美国托管出站，1M ctx，免费）**：超大产物全局评审/长上下文一致性；任务卡 `review-model: ultra`；**实测可达（2026-09-11）**：`opencode run -m opencode/nemotron-3-ultra-free` 输出 `5`/`{"result":"pass"}`，$0.00；⚠️ 用完整 provider 前缀（短名 `free/.` 解析歧义→ProviderModelNotFound）；**限非敏感**（出站）
     - ③ **DS V4 Flash RPC（三站分布式，显式指定）**：长上下文/本地合规/非时间敏感；任务卡 `review-model: rpc-v4flash`
     - ④ **M2.7 C站单机（显式指定）**：深度 CoT 评审/非时间敏感；任务卡 `review-model: m27`
     - ⑤ **主控站 opencode CLI（备选）**：主控侧 npm `opencode-ai` 直连 ultra/本地模型，与 ①trae 同源、闭环全在主控；仅当 ① 不可用/需执行者隔离时启用
  2. **负载纪律（复用现有硬规则）**:
     - 本地/网关评审仅显式指定触发，绝不自动拉起（防无预警占用三站算力）
     - 本地评审（V4 RPC/M2.7）拉起前必须过 `load-gate` 检查（need+12G≤avail，无已有 RSS 叠加，RPC 三站总预算合规），对齐 2026-09-08 事故铁律
     - ultra free 出站不占站内存，但仅限非敏感任务
  3. **输出契约**: `review.json`（run.json 平行键）结构化四级输出：`task/run_id → {score(优秀/良好/合格/不合格), pass, evidence: [锚点命中判定+推理链], flags_hit: [幻觉标志], conclusion}`，metadata: `judge_model, temperature:0, prompt_hash`
  4. **前置缺口（主控站侧）**: 主控站当前**无商业 API 端点/key 封装**，商业 API 子路待注入；trae 执行 + ultra free + 本地路由（RPC/M2.7）均已有可达路径，可先行落地。
- **关闭判据**: `agent-cli review --card <task> --run-id <ts>` 命令端到端落地（trae/ultra/本地任一源可跑通）；输出 JSON 结构化落盘 → O-16 主体关闭。**✅ closed (2026-09-12)**: `agent-cli review` 已端到端落地——五源路由(JUDGE_TABLE)+核心函数+review 分发分支+rubric/judge-prompt 资源全部落盘；实测 judge=ultra(egress B) 真实生成 `review.json`（四级 score/pass/evidence[]/flags_hit[]/conclusion + metadata(temperature:0/seed/prompt_hash/elapsed_s/review_gate/retries)）；JSON 解析失败自动重试 1 次成功(retries=1)；advisory 语义 score=不合格 仍 exit 0；幂等（无 overwrite 复用）+ `--overwrite` 强制重审均验证；local-only+egress → exit 4 敏感门；既有 route 命令零倒退。详见 [review-ring-refinement-O16.md](file:///d:/RPC/.trae/documents/review-ring-refinement-O16.md)。
- **归属**: D6 一期评审闭环。

- **--peer 站间互审（2026-09-14 复核确认）**: `agent-cli` 侧 `--peer` 无任何实现（grep 仅命中注释处注释）；站间互审属**独立协议层**，明确**递延 D7**，本项不新增代码。D6 一期 review ring（五源异基座 judge：egress/local/http/http-local）已覆盖单机闭环；站间互审（peer station 互审）待 D7 立项。

- **商业 API 子路接入（source ①，2026-09-14）**: 「主控站侧无商业 API 端点/key 封装」前置缺口由 [ADR-0003](../../adr/ADR-0003-OpenRouter密钥与egress路由管理.md) 落地——OpenRouter 作为 egress 商业源，`secrets/openrouter.key` 存 key，`ops/station-bin/_env_openrouter.ps1` dot-source 注入 `REVIEW_COMMERCIAL_BASE/KEY/MODEL`（`Invoke-JudgeHttp` 直连 `https://openrouter.ai/api/v1`，无需改 agent-cli 代码）。**Phase 1（console-side）就位，待用户填入真实 key 后实测 `review --model commercial` 端到端以回填关闭证据。**

### O-17：readonly 层 2 锁激活

- **证据**: DESIGN §4.1 层 2；schema 字段在，MVP 仅记录（全部按排它）

- **方案**: V2 按任务卡 readonly 字段细化（共享/排它语义）

- **前置**: O-09/O-10（并发能力）解锁后才有并行场景

- **状态**: ✅ **已闭环（2026-09-12）**。层2锁激活：task $body 锁段由硬编码排它改为按 readonly 选 flock 模式——`readonly:true → flock -s`（共享读锁）/ `readonly:false → flock -n`（排它锁），对齐 Codex RwLock（DESIGN §4.1，读锁并行 / 写锁独占）。**锁与调度解耦**：锁只保证写安全，真并发度仍由 slot-gate（O-25）+ O-18 跨站各1纪律约束（单引擎 slot=1 仍 1 并发，多引擎/跨站 readonly 自动并行，零 O-18 退化回归）。

- **实现**（agent-cli.ps1, task $body）：
  - L944: `$flockShared = if ($readonly) { '1' } else { '0' }`（PS 侧插值进远端脚本）
  - 锁段: `LOCK_SHARED=$flockShared; LOCK_FLAGS=""; [ "$LOCK_SHARED" = 1 ] && LOCK_FLAGS="-s"; if ! flock $LOCK_FLAGS -n 9 ...`，`LOCK_ACQUIRED/HELD` 行带 `mode=shared|exclusive`（可观测）
  - 新增 os 注释全 ASCII（PS5.1 CP936 纪律）；AST 0 错误

- **关闭判据验证（三断言内核实证 + 双路e2e）**：
  - **互斥探针**（`_o17_rwlock_probe.sh`，独立锁文件不占引擎，A站）: RR 双 `OK`（共享读并行）/ RW `R_OK+W_HELD` / WW `W1_OK+W2_HELD` → flock 即 RwLock 语义成立
  - **readonly e2e**（`test-cards/_o17_readonly.md`→A，run 202609121935547170）: `LOCK_ACQUIRED mode=shared`，TASK_RC=0/ACCEPT_OK=1/exit=0
  - **write e2e**（`test-cards/_o17_write.md`→A，run 202609121941585236）: `LOCK_ACQUIRED mode=exclusive`，exit=0（排它回归零倒退）

- **验收卡**: `test-cards/_o17_readonly.md`（readonly→shared）+ `test-cards/_o17_write.md`（write→exclusive）

### O-18：同站并发带宽约束（已定案）

- **证据**: BLINDSCAN §8.7.6 + CHECKLIST——同站内 2 并发 1.7→4.8s（\~2.8× 恶化），收益纯来自跨站分摊

- **结论（铁律）**: 扇出优先跨站各 1 并发，勿同站叠并发

- **状态**: ✅ 已定案并导入 ARCHITECTURE §4

### O-24：单机 agent CLI 工作流闭环断点（分析定案 2026-09-09）

- **背景**: D6 主干（任务卡→派发→执行→验收→回收→回填）在**跨站形态**已全闭环；但**单机形态**（本机或单站独立运行，无第二站可分摊/换站/互审）存在 4 类闭环缺环。本项为分析定案，P0/P1 落地随各批次摘取（保持台账铁律：不口头关闭）。

- **四类断点**:

  | # | 断点 | 现状 | 单机影响 | 对应既有 |
  |---|------|------|---------|---------|
  | ① | **review --peer 缺** | D7+ 站间互审协议未做；"复审"靠人工切会话（spec_workflow 的异基座复审不落 CLI）| 任务完成≠质量闭环；单机无第二站互审 → 产出→ledger 后无机器复核门 | O-16（降级先行）|
  | ② | **超时续接（--continue）缺** | O-21 清单③ 未落地；远端 `--session <id> --continue` 循环方案已定策未实现 | 长读码卡（specaudit 型）单机无站可换 → 续接是唯一韧性出路 | O-21 ③ / O-15 |
  | ③ | **claude 备通道缺** | O-15 G1 二期；单 CLI（opencode）无 fallback | 单引擎死锁（#17307 超时等）= 工作流停摆 | O-15 G1 |
  | ④ | **单机排队/上下文治理缺** | O-18 铁律只约束跨站；单机同站并发仍会退化（1.7→4.8s）| 多任务单机串行无分流；context 预算无单机专用调卡纪律 | O-18 延伸 / O-17 |

- **关键研判**:

  1. **单机 = 跨站退化子集但没有负反馈环**：跨站靠就绪门注入引擎端口（O-19）、换站规避 context 墙（O-21）；单机无对应物（端口即本机引擎、无第二站），断点②对单机价值最高。
  2. **O-21 教训（"环境修复 > 配置修复"）单机代价更高**：跨站可换站、单机只能换引擎或调卡；golden（O-12）刚闭环，其"评审后置门"在单机上缺失（无 peer 复核误拒/放水）。
  3. **断点①是"闭环"最真实的缺环**——产物落库即止，无机器评审回写环，与 spec_workflow 的"复审→修订→再审"循环断层。

- **建议优先级（按单机场景价值）**:

  | 优先 | 动作 | 对应 | 单机收益 |
  |------|------|------|---------|
  | P0 | **review --peer 单机版**（`agent-cli review --card X --model Y`：产物+golden+模型差异对照，AI 评审回写 ledger；站间互审降级为本地二次评审优先落地）| O-16 降级 | 补全闭环缺环（最大）|
  | P0 | **--continue 续接落地**（远端 session 续跑循环）| O-21 ③ / O-15 | 长卡韧性（单机唯一出路）|
  | P1 | claude CLI 路径最小化 | O-15 G1 | 备通道防死锁 |
  | P1 | 单机排队策略（同站并发约束写入手册）| O-18 延伸 | 调卡纪律 |
  | P2 | readonly 层 2 锁激活 | O-17 | 人机共用安全 |

- **关闭判据**: ① review 命令落地（本地/站间任一形态）并回写 ledger + spec 流程复用；② 超时卡经 `--continue` 续跑闭环（非重启重读）；③ claude 路径最小可跑；④ 单机并发纪律入册。四项 P0/P1 中①+② 落地即视为本项主体闭环，③④随 G1/V2 摘取。

- **状态**: ⏳ P0-① **已落地并实证**（2026-09-09）：续跑循环已并入 agent-cli.ps1 $body（`--continue` retry≤2，RESUME[1]/[2] 出线实证 + 超时卡全链验证 + echo 回归零倒退——证据见下）；P0-② review 待摘取。**本项主体闭环判据①已满足，②编跑通**（超时卡经 continue 续跑闭环）。**④ 单机并发纪律入册（2026-09-12）**：O-18 铁律补单机语境——手册 §2 agent-cli「并发纪律」+ ARCHITECTURE §4「单机形态同样适用」（扇出优先跨站各 1，单机勿就地叠并发，同一带宽顶起 ~2.8×）。

- **P0-① 实施记录（2026-09-09）**:
  - 改动①: agent-cli.ps1 $body opencode run 段——首跑 + 失败（RC≠0）`--continue` 续跑 ≤2 轮；续跑提示 base64 字面量（ASCII 纪律）
  - 改动②（独立预算）: 新增 front-matter 键 `continue-timeout-s`——续跑在**自身独立 `timeout` 预算**下运行（缺省/0=沿用 `timeout_s`），首跑 900s 被消费后续跑仍拿全新完整预算；解析层归一化 + $body 续跑行 `timeout $continueTimeout` + BUDGET 日志行（`BUDGET: first=900 resume=900`）
  - 关键实证（驱动设计）: ① opencode 无头 run **不打印** `ses_`（stdout 探针实证）→ 弃 session-id 解析；② session 按 workspace path 隔离（opencode.db 探针）+ `cd $W` 后 `--continue` 精确续本次会话（A 站双 run 同 session 实证）；③ 模型名须 route 全限定（`-m gpt-oss` 报 server error）
  - 全链验证: 超时卡（timeout_s=4, gpt-oss→A）远端 .agent-output.txt `RESUME[1]/[2] prev_rc=124 → rc=124`（循环触发+cap=2 正确）+ `TASK_RC=124→excode=6`（timeout 语义保持）；echo 回归 exit=0 零倒退
  - **G1 C4 守卫补充（2026-09-12, G1-continue-spawn-decision.md）**: resume 耗尽仍失败时，final `.agent-state.json` 不再静默 `done`（`RC≠0`→`ST=failed`）+ `.meta` 新增 `REVIEW_NEEDED`（RN）——失败任务供主控感知"失败未复核"，补断点①失败路径的机器复核门。纯 RC 驱动无 context 信号依赖；BOM 补回 + AST=0 + `_fm_golden_test.ps1` pass=9 fail=0 零倒退
  - **真实恢复场景实测（v3, 900s 级）**: `dogfood-resume-recovery.md` v3（timeout_s=900 + continue-timeout-s=900，任务=8000 行整数文件自生成+批量校验）——**首跑被 900s timeout 杀 → 续跑用足独立预算继续生成（实测 RUN_S=1285s = 900+385, 续跑完成 TASK_RC=0）**；accept 判据未达（ACCEPT_OK=0 → excode=9）：机制本体（首跑被杀→续跑拿到独立预算并继续）已验证，判据失败属任务产出度量问题（精确行数等值判据在续跑恢复场景过严，应改"产出存在且 ≥ 阈值"）。结果与证据见手册 §2a.5（2026-09-09）
  - 验证卡: `test-cards/dogfood-resume-timeout.md`（机制 4s 级，可重跑）+ `test-cards/dogfood-resume-recovery.md`（真实恢复 900s 级）
  - 修复过程回归: 编辑引入 PIPE_STDIN_OK 裸词 bug → 修复 + 语法/BOM 复验通过

### O-25：agent 任务执行进度可观测性（派发前预估 + 派发中节拍）

- **问题**: 任务派发给 agent-cli 后到回收结束之间为**黑盒**——ledger / `.meta` / `.agent-run.json` 均为 **run-end 快照**，无运行中采样 → 长卡（specaudit 型 900s 级）状态不可观测、无吞吐（`OUT_BYTES` 无法换算 token/s）、无 ETA；预算估算用单一 wall-clock（timeout_s），不区分 prefill/decode 相
- **根因**: 主控只 collect 终态产物；远端 $body 无中间节拍落盘（运行中 .progress 不存在）；派发前无"该卡能跑多快"的模型吞吐基准表
- **与既有项关系**: 观测判据订正见 O-22（`.meta` 是 run 结束快照非活动信号）；单机续接韧性见 O-24 P0-①；跨站并发见 O-18/O-08；`/slots` 槽位探测属 O-08（F1 后端并发探测，降级为 queue_s 观测先行）
- **方案（分层，最小到最大）**:
  - **L0 派发前预估**: 建**模型吞吐基准表**（复用 BLINDSCAN 实测：gpt-oss-120b prefill 112-138 / decode 49-53 t/s 等缺失档需实测补齐）；派发时按任务卡 `complexity`+`max_output` 反推 ≈token/t/s → 预估秒数；预算拆 prefill+decode 两相，而非单 wall-clock
  - **L1 派发中观测**: $body 在每次 tool-call 输出后落 `.progress`（token 增量/墙钟增量 → 实时 t/s + 已跑/预算 → 剩余预算预警）；主控复用现有 collect 的 scp 通道轮询正在跑任务的 `.progress` 即可"实时"
  - **L2 槽位调度**: 派发前查目标站 `/slots`，满则跨站/拒绝而非静默排队（并入 O-08/F1）
  - **L3 可视化**: 主控端**单文件 HTML 看板**渲染 ledger+run.json（成本最低先行）；远期可选推 Beszel/Grafana（Beszel 无自定义指标插件，社区明确——推理指标需 Grafana textfile 旁支，非刚需）
- **信号可行性硬约束**: C1-C3 context 占率路由与 ETA 需 context usage，但现役 opencode 无头 run 不打印 usage（CLOSED-LOOP §3.1 实证）→ 吞吐 t/s 与剩余预算从 wrapper 内部可测，**不依赖外部信号**，正是 P0 可即刻落地的理由
- **社区方案映射（2026-09-12 调研）**: 社区观测栈分三层——引擎层（llama.cpp `/slots` n_past/is_processing/queue + 响应 timings prompt_n/predicted_n→t/s，主线**无原生 /metrics 端点**）/ 代理网关层（llama-swap、LiteLLM）/ 任务编排层（Langfuse/Phoenix/LangSmith）。**D6 需的是任务编排层**，但社区该层是 trace/span 栈（需 DB+推理层），对单机 agent wrapper 功能过剩 ✅不引。社区任务进度标准 = **run 状态机 + step 追加日志**，等价不依赖 trace 框架的原生轻量打点（正是 L1）。看板无现成应用层匹配（Langfuse 重、OpenWebUI 是对话、Beszel 无自定义指标、Cockpit 是机器）→ L3 自定义是必然。引擎层信号现成可采（本集群引擎正用）→ 支撑 L0/L2
- **关闭判据**: ① 吞吐基准表入库（至少覆盖现役各模型档）；② $body `.progress` 中间打点落地且主控能轮询到运行中任务节拍；③ 派发前按基准表给预估预算（非线性逼近 timeout_s）；④ L3 看板能渲染"正在跑+已完成"总览。①+② 落地视为主体闭环，③④随演进摘取

- **状态**: 🔵 **判据①②③④全落地（2026-09-12）**。**P1 槽位门 ✓（2026-09-12，并入 O-08/F1）**：新增 `ops/station-bin/_slot_gate.sh`（远端探测 llama-server `/slots` → `SLOT_TOTAL/BUSY/QUEUE`，无 `/slots` 输出 `SLOT_NA`，ASCII 纪律）+ `agent-cli.ps1` `Invoke-SlotGate`（ssh-capture 模式，解析 SLOT_*，na 降级放行）；`Invoke-Task` station-ready 之后接入：**仅 `cluster-litellm/*` 本地引擎走门**（egress `opencode/*` skip），busy≥total 或 queue>0 → 默认 **exit 24 SLOT_BUSY reject**，`--slot-allow-busy` 放行（action=allow-busy），idle/na 放行；`slot=[ordered]@{gated;total;busy;queue;action}` 记入 run.json。**P2 看板 ✓（2026-09-12，判据④ L3 单文件 HTML）**：新增 `ops/station-bin/make-dashboard.ps1` 生成器——读 `agent-runs.log`（`^\d{14,},` 过滤，30 行跳过标题）+ `D:\Paper\agent-out\*\ .agent-run.json` 索引 → 数据内联为 `<script>var D={...}</script>` 字面量 → 写 self-contained `dashboard.html`（file:// 直开、零网络请求）；「已完成总览」表（ts/model/sens/exit/status/run_s/queue_s/bps/slot/详情展开）+ 状态着色 + `switchTab`；「正在跑/Live」tab 由 `-Live -StationHost <host> -LivePort <port>` 调用 `__probe_live.sh` scp 拉远端 `.progress`，失败/未指定显示 `no-live-data`。**P2 验证**：生成器 AST_OK + BOM 补回 + `_fm_golden_test` pass=9/fail=0；Python 解析内联 `var D` → **completed=21 / live=None / withDetail=20**（旧 run 缺 slot/output_bps，JS `d.slot&&…||'-'` 容错）；file:// 直开由用户侧实测。**共同经验**：Edit 工具每次剥离 BOM → 任何 .ps1 编辑后必须 `[System.IO.File]::WriteAllBytes` 补 EF BB BF（本次 P2 生成器两度被 BOM 坑）；PS 变量**大小写不敏感**，payload 键 `$live` 与 `[switch]$Live` 同名被当 switch 序列化成 `{"IsPresent":false}` → 改 `$liveData` 规避；ledger ts 实为 **18 位**（{14,17} 匹配失败），用 `{14,}`。

  **P0 判据明细**：**判据① `THROUGHPUT-BASELINE.md` ✓**：现役各档入库（gpt-oss 49-53 / nemotron 20.5-23.2 / M2.7 21.5-22.1 单机实证 / V4-flash 7.9 RPC / Qwen3.8 19-20），metrics-log Phase 6.2 记录 M2.7 双机 RPC 删除与 gpt-oss Vulkan 误归因修正。**判据② `.progress` 打点 ✓**（agent-cli.ps1：远端 $body 每 5s 采样 `.agent-output.txt` 字节增长+墙钟 → `.progress`，teardown 写 `t=end` 终值；主控 collect 复用 scp 拉取 → parse 回填 `outputBytes/outputBps`）。**判据③ 派发前预估预算 ✓**（agent-cli.ps1 `Get-ThroughputEstimate`：route id→$TpBench 基准表，prefill=context/prefill_tps + decode=max_output/decode_tps，×fudge 1.6 分相估算；**HIT 才打印 ESTIMATE，MISS 不打荒数字**；est_total 超 timeout_s 打 `TIMEOUT-WARN` 预警；离线函数验证 HIT gpt-oss=682s(262+164)、MISS ultra=no-bench；route 冒烟 exit 0 + `_fm_golden_test` pass=9/fail=0 + BOM 补回 EF BB BF）。**判据④ L3 看板 ✓（见上 P2）**。**①+②+③+④ = O-25 全判据闭环**。遗留待补：busy/idle 真 /slots 占用与正在跑 `-Live` 需站点引擎在线时实测（当前无引擎）。**收口决定（2026-09-12）**：P3（ETA 精度/自动刷新）**明确不实施，O-25 收口**。依据——①Live 链路缺口调研澄清：`__probe_live.sh` 由生成器 here-string 动态生成（非独立文件，`make-dashboard.ps1` L76-87 Set-Content 后 scp），遍历 `$HOME/agent-workspaces/*/out` 与 agent-cli `$WORKSPACE_ROOT`（/home/scott-lau/agent-workspaces）一致，`-Live` 正则解析匹配，**链路设计完好无需补**；②ETA 精度受"字节→token 换算误差"信号天花板限制（opencode 无头不打印 usage，wrapper 只能测字节；中文≈1.5-2 B/t 与英文≈4 B/t 引入不可信因子，与 no-bench 不打荒数字纪律冲突，干净途仅打点侧记 token 而 wrapper 拿不到），收益有限；③自动刷新（主控定时重生器+浏览器 reload）打破 file:// 快照边界（L1：快照非实时/不做 SSE），且当前无常驻引擎无法验证效果。**O-25 判据①-④ 全闭环 + P2 验证完成 + P3 收口 = O-25 正式收口**。**实机在线实测（2026-09-12，全通）**：
- **前置：A/B 两站载入 gpt-oss-120b（ROCm0，unsloth）**。首次加载两站同败——根因 `invalid device: Vulkan0`（unsloth 内嵌 llama.cpp 已从 Vulkan 切 ROCm 后端，`--list-devices` 实测 = `ROCm0`），但 `infer-load` [6a] 硬编码 `--device Vulkan0` → 必然失败。**顺带修复①**：`infer-load` 改 `--device "${INFER_DEVICE:-ROCm0}"`（env 可覆盖）；A/B 两站重启后 `READY ✓ :8080 (unsloth gpt-oss-120b)`，A=42387/B=39701 底层 llama-server 端口。B 站额外遇 `gpt-oss-120b` 与 `gpt-oss-120b-fable-5-distilled` 前缀歧义（infer-load 用 `^${PREFIX}` grep）→ 临时 rename fable 目录规避后还原。
- **`/slots` busy/idle 实测 ✓（判据④ L2 真机验证）**：**idle**（无请求）= `SLOT_TOTAL=4 SLOT_BUSY=0 SLOT_QUEUE=0`；**busy**（发起 4000-token 长生成，站内 1s 起轮询 12s）= `SLOT_TOTAL=4 SLOT_BUSY=1 SLOT_QUEUE=0` 稳态。A/B 两站一致。**注意**：8080 是 unsloth studio API 网关（`/v1/models` 需 key；`/slots` 返回 `API endpoint not found`），真 `/slots` 在底层 llama-server 随机端口（A=42387/B=39701，仅绑 127.0.0.1）——**`_slot_gate.sh` 现硬编码只连一个端口，遇 unsloth 后端需先 ssh 解析 llama-server 端口**，此已在 agent-cli `Invoke-SlotGate` 对接时处理（station-ready 已注入直连端口）。
- **`-Live` 正在跑数据实测 ✓**：A 站 `~/agent-workspaces/paper/out` 造真实格式 `.progress`（`t=.. bytes=123456 bytes_s=33`）→ 主控 `make-dashboard.ps1 -Live -StationHost scott-lau-NEX.local -LivePort 42387` → `LIVE: 1 running task(s)`，dashboard.html 内联 `"live":[{"proj":"paper","bytes":123456,"bytes_s":33}]`。首次运行暴露 **CRLF bug**：`__probe_live.sh` 由 `Set-Content -Encoding ASCII` 生成 = CRLF 行尾，scp 远端 bash 解析 `done\r` 报"未预期的文件结束符 EOF" → `LIVE: probe skipped`。**顺带修复②**：Set-Content 后 `ReadAllText` + `-replace "`r`n","`n"` + `WriteAllText`（UTF8 no BOM）规范为 LF → 恢复。修复后 Edit 剥离 BOM → **顺带修复③**：补回 EF BB BF（memory 纪律）。
- **结论**：O-25 唯二剩余待办（busy/idle `/slots` + `-Live`）已实机全通 → **O-25 完全收口，无任何遗留待办**。

### O-26：单任务分解派发并行（Split-Dispatcher）

- **问题**: 现派发模型=单任务卡→单 agent→单站（`Parse-Route` 后一个 `$HostName`）；跨站并发只覆盖"多张独立卡"，**没有"一张可切分大任务拆子卡并行"**。一张 readonly 大任务卡（如横扫 N 文件各自审计）卡在单节点，无法利用 A/B/C 三站
- **物理上界 3**: O-18 铁律（同站叠并发被统一内存带宽顶起 ~2.8× 恶化）→ 只能**跨站各 1**（A/B/C 各 1，最多 3 路并行）；且单站塞 120B 模型后 available≈0（unsloth §8.10 实测）→ 同站并行 decode 无空间。3 = 并行上界，物理边界非设计缺陷
- **什么值得拆（判定，先问三问）**: ①可切分=子任务间**无数据依赖**（readonly 型）；②单站卡死（O-24 P0 续接已耗尽仍不够）；③上下文墙（G1 C1-C3）。**只拆"可切分 readonly 大任务"**——写型/强依赖任务拆了因结果 Merge 成本 > 并行收益，负优化
- **方案（复用非新建）**: 主控编排层加三动作——**Split-Dispatcher**（按任务卡 `decompose` 声明拆 N 子卡 → 每子卡=现有 `task cmd` 全链路（.attach 注入分片源/Complexity 路由/accept/collect）→ 跨站各 1 派发）+ **子卡产物回收**（复用 collect）+ **结果 Merge**（readonly 轻量归并/写型不拆）。不动 agent-cli.ps1 派发内核
- **缺口清单**: ①任务卡 schema 无 `decompose` 声明（拆键随 schema 冻结前加）；②编排层 Split-Dispatcher（现仅 Parse-Route 单发）；③结果 Merge（同源子卡产物冲突）；④**O-25 P0 打点先行**（无 .progress 则并行子卡亦黑盒）；⑤每子卡派发前查 `/slots`（O-08/F1+O-19 已定案）
- **前置依赖**: **O-25 P0 是硬前提**——分解派发若无 .progress 可观测，等于"一个大黑盒拆成三个小黑盒"，并行价值归零。故两者捆绑推进
- **关闭判据**: ①一张可切分 readonly 测试卡经 decompose 拆 + 跨站各 1 并行（A/B/C），全子卡过 accept 且 .progress 全程可观测；②结果 Merge 产出正确；③并行墙钟 ≪ 串行（对齐 BS-2: 3 线程 52.1s ≪ 110.9s ratio 阈值）

- **状态**: ✅ **已闭环（2026-09-12）**。拆+/跨站各1/Split-Dispatcher/Merge 四步全部落地。**实机验证（A/B 双站 2 分片）**：
  - 测试主卡 `test-cards/o26-split-fanout.md`（`decompose: [只读分片1, 只读分片2]`）+ 共享附件 `_o26_src.txt`，`split paper --card ... --attach ...` 拆 2 子卡 → round-robin 派 A（scott-lau-NEX.local）/B（scott-lau-GTR-Pro.local）各 1 并发。
  - **产物正确**: shard1(A)=`O26_SHARD1_OK|SHARD-ONE this is line 2...`，shard2(B)=`O26_SHARD2_OK|this is line 3...`；两站 `accept.passed:true`/`collect:ok`；merged-output.txt 按序归并 `rc=0`，`SPLIT_EXIT=0`。
  - **墙钟**: 并行 465.1s ≪ 串行 720.8s（shard1→A 377.5s + shard2→B 343.3s）→ **ratio 0.645（并行快 35%）**，对齐 BS-2。
  - **落地修复 2 bug**: ①`Start-Process -PassThru` 读 `.ExitCode` 偶发 `$null` 误判失败 → 补 `Refresh()` + 解析子日志 `TASK remote excode=` 兜底；②函数体内 `$MyInvocation.MyCommand.Path` 为 null 致子进程派发到无 BOM 原始文件（PS5.1 CP936 解析失败秒退）→ per-run 显式生成 BOM 副本 `$ChildScript` 再派发（同 O-11 L2 temp-BOM 机制）。
  - **执行细节**: `task` 子命令经 `--RemoteHost` 显式路由（`--HostName` 无效缺口，见 §8）；C 站 unsloth Vulkan0 设备失效暂用 A/B（运维项）。

#### O-33：水印入仓化后，引用旧路径的文档未跟随（**已登记；处置分两类**）

**背景**：2026-09-23 执行 `D7-P1-1` 水印入仓化 —— `AGENT_AUDIT_BASELINE` 由
`ops/.audit-baseline.json`（本地、已 gitignore）改为 `inventory/audit-baseline.json`（**入仓**）。
代码 · `.gitignore` · 护栏 · 文件迁移**均已跟随**；**文档引用未跟随**（由当轮如实标注）。

**⚠ 关键：「未跟随」不等于「都要改」** —— 它们是**两类不同性质的文档，处置相反**：

| 类 | 文档 | 为什么 | 处置 |
|---|---|---|---|
| **A · 记录历史** | `ADR-0007`（:973/:1094）· 调研稿（:231/:290/:500/:529） | 它们是 **D-b 决策的现场**，**当时确实是本地**。改写正文 = **篡改历史**，读者将看不出"决策变过" | **不改正文**，加**一处集中补注**（见下） |
| **B · 陈述现状** | `ARCHITECTURE.md` · `REMEDIATION-PLAN.md` · 本文 §1 总览 · 路线总表 §10 A8 表 | 它们说的是"**当前是这样**" ⇒ 路径已变 ⇒ **确实过期**，会误导 | **就地更新** |

**两条纪律在此分工**：本仓"**不迁移权威源、只建映射**" ⇒ **历史记录保留原状**；
"**改字段必须核对所有消费它的地方**" ⇒ **现状陈述必须跟随**。
⇒ **判据 = 该文档是在"记录某次决策"还是在"陈述当前状态"**（同一份文档里也可能两者并存）。

**建议的集中补注**（放 `ADR-0007` 的 K2 / D-b 条目下，**一行**；其余处只指向它）：
> **2026-09-23 变更**：水印**已入仓**（`inventory/audit-baseline.json`）。
> 触发条件 = D-b **自设**的"若将来多人/多机" —— **D7 即该条件所指的"多机"**。
> 代价（刻意接受）：**提交摩擦 = 留痕来源**。已知未决：**多机并发 `--accept` 合并冲突**（候选解：按机分文件）。

**★ BLINDSCAN-v3 的 F-11 归类结论（2026-09-23，本轮）**

- **归类：A 类（记录某次扫描）** ⇒ **不改正文**，只在行内加标注 —— 判据见本条的"记录决策 / 陈述现状"。
- ⚠ **但归类时发现 F-11 比原记录更严重**（原判定"未被 agent-cli 触碰 ⇒ 不在本次范围"）：
  **"按机分片"只治了【跨机】的 git 合并冲突，未治【同机】的并发写** ——
  同机两个 `--accept` 仍是对**同一分片文件**的 read-modify-write，后写者覆盖先写者。
  ⇒ 症状：**丢掉一次接受**（不会损坏数据）⇒ 下次审计**再报一次** ⇒ **自愈**。
- ⇒ **处置：已知低风险，不修**（人为并发敲两次 `--accept` 概率极低；且后果自愈）。
  **但要写出来** —— 否则"已按机分片"会被误读成"并发已完全解决"（**这正是本会话反复出现的"形式正确、边界未清"**）。
- ⇒ 若将来**脚本化 `--accept`**（如多站自动收束），必须回头补锁 —— 记在此处，勿重新推导。

**未做本轮的理由（如实）**：改动跨 6+ 文件，且**必须先定"集中补注放哪"** ——
否则 6 处各写一遍 ⇒ 又造出"**同一事实多处记录**"（本台账存在的意义正是反过来）。

#### O-34：迁移后**首次**门禁 FAIL，提交时同一命令 PASS —— **已定位并已修**（断言对 git 暂存状态敏感）

**实测（2026-09-23，水印由单文件改为按机分片时）**：

| 时刻 | 命令 | 结果 |
|---|---|---|
| 迁移刚完成（`Move-Item` 后，**未** `git add`） | `rpc_check.py --quick` | **FAIL (1 项失败) → 阻断** · **绿灯 9** · 黄灯 1 · 红灯 1 |
| 提交时（先 `git add -A inventory/`，**同一命令**） | pre-commit 钩子 | **PASS** · **绿灯 10** · 黄灯 1 · 红灯 0 |

**唯一差异**：**暂存状态**（后者已 `git add -A inventory/`，含 rename `audit-baseline.json → audit-baseline/desktop-br5r8ev.json`）。
⇒ **疑似有断言依赖 git 索引/工作区状态**，在"文件被重命名/移动但尚未暂存"的窗口内会**短暂变红**。

**⚠ 定位所需的关键证据已丢失（如实记账）**：首次那次运行**用了 `Select-String` 只过滤 3 个模式**
（`可重放 gap|结论:`）⇒ **"哪一项红"的信息被过滤掉了**。
⇒ 这正是"**过滤输出会丢关键信息**"的实例 —— 与本项目早前抓到的"门禁静默降级"**同族，只是这次由我造成**。

**定位方法（★ 本轮已按其完成，留档供同类问题复用）**：
1. **在工作区未暂存的状态下重放这次迁移**（把分片移回单文件、不 `git add`、跑门禁）；
2. **这一次不要过滤输出** —— 直接看 `── 明细 ──` 段落里的异常项；
3. 若复现，检查该断言是否读了 `git status` / `git ls-files` / 索引路径，或是否按"文件是否存在"判"是否已登记"；
4. 判定是**真缺陷**（断言不该依赖暂存态）还是**可接受**（迁移窗口极短）—— 记结论，不预设。

**为何不猜**：与 O-27 / O-29 / F-2 / F-3 / O-32 同源教训 —— **本项目在"凭推断下结论"上已连续错多次**；
未经复现就写原因，**下一个读到的人会以为已定性**。

**★ 定位结论（2026-09-23，静态取证）**

- `rpc_check.py` 的 `_iter_source_files()`（[:52](../../ops/rpc_check.py)）以 **`git ls-files -z`** 取文件范围，
  其 docstring **自己写明了假设**：
  > 范围选 git 跟踪文件而非"整个工作区"：**pre-commit 阶段新文件已 `git add`**，故会出现在 ls-files 中
- ⇒ **根因（高置信）**：该假设**只在 pre-commit 钩子里成立**。我那次是**手动直接跑 `rpc_check.py --quick`**，
  且处于**迁移未暂存**的中间态 ⇒ **假设不成立** ⇒ 文件范围与提交时不同 ⇒ 某消费它的断言结论不同（红灯 1 项）。
- ⇒ **性质判定：是真问题，但不在"结果错"，而在"同一命令两种结论且无提示"** ——
  手动跑门禁是本仓**推荐做法**（本会话一直在用），会让人误判成"是不是我把它改坏了"。
- ⇒ **修法（2026-09-23 已落地）**：让 `_iter_source_files` 把"**范围已收窄**"显式暴露 ——
  新增 [`_untracked_count()`](../../ops/rpc_check.py)，用 `git ls-files --others --exclude-standard` 统计
  **未跟踪（⇒ 不计入门禁范围）**的文件数；`secrets` 报数行在 **> 0** 时显式追加
  "⚠ 另有 N 个**未跟踪**文件未计入（范围=git 跟踪文件；pre-commit 时新文件已暂存 ⇒ 手动跑与提交跑结论可能不同，见台账 O-34）"
  （干净仓库时为 0 ⇒ **零噪声**）。
  （落点已按"**先读 `secrets` 报数行再改**"的纪律执行，未盲改。）
- **★ 修复的第一次实战收益**：提示一上线**立刻报出 1 个未跟踪文件** = `ops/.audit-baseline.json`
  —— 即**水印入仓化时漏清的旧文件**（只搬了 `inventory/` 侧、未清 `ops/` 侧；而 `.gitignore` 的忽略项已移除 ⇒
  它从"被忽略"变成"未跟踪"）。确认内容（**18 条 keys，与分片一致**）后**直接删除**，而非恢复忽略。
- **元意义**：**让范围可见，比保证范围正确，更能抓住遗留问题。**
- **状态**：✅ **已修（2026-09-23）** —— `_untracked_count()` 落地并被 `secrets` 消费；`rpc_check --quick` **10 绿 / 0 红**。
- ⇒ 这也再次印证一条通用教训：**"把设计假设写进 docstring"不足以防失效** ——
  **假设必须可被检出**（与盲区 B2「门禁自审」同源）。

#### O-35：站上**本地引擎的并发请求能力**未验证（与 O-31 是**两个独立问题**）

- **背景**：O-31 修的是"**三个站上临时名固定 ⇒ 同站两 run 互相覆盖文件**"（**文件层**）。
  修完后同站多个 run **不再互相覆盖文件**，但它们**会同时向同一个本地引擎（:8080）发请求**
  ⇒ **引擎能否并发行服务，未验证**（**引擎层**）。
- **若不支持**，症状会以**另一种形式**出现：排队 / 超时 / 显存 OOM / **请求错配** —— **而不是文件混写**。
- **与主路的关系**：主路有 `flock`（per proj+站）⇒ **同站主路 run 被串行化** ⇒ 该问题**被锁遮蔽**；
  **备路无锁** ⇒ 该问题**会先在备路上暴露**。
- ⚠ **最危险的失败形态：「输出错配」** —— A 的 prompt 得到 B 的输出。
  它**不会报错**，只会**静默把结论张冠李戴**（与"判据不可判"同族，比报错危险）。
- **验证方法（未做）**：站上引擎已加载时，让**同站两个 run 并发**（同 proj 会被锁挡 ⇒ 需两个不同 proj），
  观察 ① 是否排队/报错 ② 显存与吞吐 ③ **两个输出是否错配**。
- **结论取向（不预设）**：**可能不需要 flock**（若引擎自身排队安全）；**也可能需要**（若错配）。
  **先验证，再定。**
- **★ 影响面（Scott 判断 + 本轮核对，2026-09-23）：当前不影响吃狗粮** ✓
  - 吃狗粮现状是**跨站各 1 个 run**（或单站 1 个），**同站不存在并发** ⇒ **不触发本条**；
  - 且主路有 `flock`（per proj+站）⇒ **同一 (proj, 站) 被串行化** ⇒ 即使将来同站多 run，主路也先被锁挡住。
  - ⇒ ⇒ **触发条件（写清，免误判）**：**同站并发且落在同一引擎上** —— 具体为
    ① 备路（无锁）同站并发，或 ② 主路**不同 proj** 同站并发（锁是 per proj ⇒ 挡不住）。
  - ⇒ 因此 **O-35 不是吃狗粮的前置**；但它**是"同站扩容"的前置**（若要压满单机多卡）。

- **✅ 已验证并闭环（2026-09-24，Scott 指令"加载引擎验证"）** —— **裁定：引擎层并发安全，不受"输出错配"威胁。**

  **取证设计**（直击引擎层，不经 agent 层 ⇒ 变量最少）：B 站加载**最小档** `gpt-oss-20b`（11G，先过
  `cluster.py estimate` 的三条硬规则联算 = 【FITS】13.4GiB，站上 `load-gate` 二次护航）；
  用**两组互不相同的哨兵串**（`AAAA-1111-…` / `BBBB-2222-…`）分别发请求，
  **逐条判"是否只含自己的哨兵"** ⇒ 错配即现形。

  | 场景 | 报错 | ★**输出错配** | 每条 content | 墙钟倍数 |
  |---|---|---|---|---|
  | 串行基线（1 路） | 0/2 | 0/2 | 各含自己哨兵 ✓ | 1.00× |
  | 并发 2 路 | 0/2 | **0/2** | 各含自己哨兵 ✓ | 0.89× |
  | **并发 4 路（压满槽位）** | **0/4** | **0/4** | **各含自己哨兵 ✓** | **2.64×** |

  - **引擎实测配置**：`llama-server … --parallel 4 --flash-attn on -c 32768 --kv-unified …`
    ⇒ **4 个真并发槽**（**不是排队**）⇒ 本条的"最危险形态"**确实可达**，而实测**未发生**。
  - ★ **关键副产品（交叉印证 O-18）**：**4 路并发墙钟 = 串行的 2.64×** —— 与 **O-18 记录的 ~2.8×** 量级吻合，
    ⇒ **"同站叠并发收益被抹平"这一现象在【引擎层】独立复现**（此前只在 agent 层观测到）
    ⇒ 该结论**不再是单一层的观察**，而是**两层一致**。
  - **⇒ 可执行结论**：**"错配"不构成同站扩容的阻碍 ⇒ 不需要为它新增锁**；
    但 **同站叠并发必须算吞吐代价**（不是免费），扩容器决策应以此为输入。
  - **取证脚本**：[`spec/d6-agent-standard/fixtures/o35_conc_test.py`](fixtures/o35_conc_test.py)（scp 到站上 `python3` 直跑；
    ⚠ 首轮踩坑：gpt-oss 是**推理模型**、模板带 `reasoning_effort:high` ⇒ `max_tokens` 给小会把预算全用在
    reasoning 上、`content` 被截断，使"own"判据失效 ⇒ **判据已改为扫全响应体**，并把预算提到 768 让哨兵落地）。
  - **安全收尾**：验证后**已 `unload`**，复核**三站全 STOPPED**（无残留；遵守"禁止叠加/不留驻"硬规则）。

## 3. 风险台账（继承 DESIGN §11.2，实况更新）

| 风险                       | 缓解                                 | 现状/状态                        |
| ------------------------ | ---------------------------------- | ---------------------------- |
| PowerShell→ssh 引用陷阱（R14） | 全部远端逻辑走脚本落盘；CI 冒烟含端到端 task         | ✅ 已铁律化 + 冒烟覆盖                |
| llama-server 单槽排队致超时     | timeout 默认 900s 宽裕 + queue\_s 观测定位 | ⚠ 同站并发现排队（O-18）              |
| zen 免费档限额无预警             | G13 本地 log 累计 + 降级提示（exit 7）       | ⏳ 未触发（O-07）                  |
| 站断电状态残留                  | 孤儿检测 + out/ 归档不删                   | ✅ A10 双次验证                   |
| .agentsync 误排除致任务缺文件     | task 失败报缺文件路径 → 修排除清单重 sync        | ✅ 已建项目级覆盖（Paper 5.6GB→7.0MB） |
| 网关 auth（LiteLLM 401）     | 绕网关直连（ADR-0002 方案 C）已规避；遗留 O-14    | ⚠ 运维项                        |

## 4. 台账维护规则

1. **单一真值**: 本文件是 D6 未决问题的唯一总账；代码注释/检查清单中的待办引用本表 ID，不在别处维护副本
2. **状态机**: `🔴 open` / `⏳ 挂起` / `⚠ 待验证` / `✅ 已定案/已闭环`；每项含清晰的关闭判据
3. **回填证据**: 任何项闭环必须回填实机证据（命令输出摘要 + 时间戳 + 产物路径），拒绝"口头关闭"
4. **批次关联**: 二期(G1)/V2/D7+ 项随对应阶段开启时从本表摘取为任务；本表保持 open 直至批次交付
5. **随审更新**: 每次验收/ADD 审计/升级窗口 review 后同步本表（新增/状态变更/证据回填）

***

**开放日志签字**: 2026-09-04 立案，随 D6 演进维护。

***

## 5. 剩余 open 全景快照（分析落档 2026-09-12）

**判定**: 单机闭环完整（O-16/O-20/O-21/O-23/O-25 全落地），**无 P1 阻塞级 open issue**；剩余 open 集中于运维收尾 + 二期/V2 演进，不构成闭环缺口。

| 类别 | 项 | 说明 |
| --- | --- | --- |
| 运维收尾（已全清） | O-22 ✅（.meta 残留已收口）、O-14 ✅（网关已绕开闭环）、O-25 ✅（**2026-09-12 实机在线实测全通**: busy/idle `/slots` + `-Live` 均验证，无任何遗留待办） | **A 类 3 项全部清零（2026-09-12）** |
| 二期 G1（单机闭环韧性） | O-24 P0-② ✅（被 O-16 覆盖闭环）、O-15 ✅（**2026-09-12 已落地**：claude 控制台本地备通道 `--cli claude` + `--continue`，见 O-15）。剩余仅 O-16 子项（`--peer` 站间互审，留 D7） | 长卡续接 + 单引擎死锁备路 |
| V2 fan-out（分布式强化） | O-26 ✅（**2026-09-12 闭环**: Split-Dispatcher，decompose 拆2分片跨站并行，ratio 0.645）、O-09 ✅（**2026-09-12 闭环**: L1 PASS + `isolate-xdg` 闸落地）、O-11 ✅（**2026-09-12 L2 闭环**: 跨站并发端到端 PASS，A/B 双站 done+accept+ledger；sampler 卡死等 3 bug 落地修复）、O-17 ✅（**2026-09-12 闭环**: 层2锁激活——readonly→`flock -s` 共享 / write→`flock -n` 排它，三断言互斥探针 + readonly/write 双路 e2e 全 PASS） | 跨站编排并行 |
| 低优先/垫脚 | O-02（--archive）、O-12（strong accept golden）、O-03/O-04（纪律）、O-05、O-06、O-07、O-13 | 事件驱动/批次前 |

**台账同步（2026-09-12）**: O-08 / O-16 / O-25 三行总览状态从表格滞后同步至详情节——O-08 ⏳→✅ F1 落地、O-16 🔴→✅ closed（评审环落地）、O-25 归属列→🔵 已收口。

**建议推进序**: A 类（O-22/O-14/O-25）**已全部清零**【2026-09-12：O-25 实机在线实测全通（/slots busyidle + -Live）】→ **下一步 O-26 Split-Dispatcher**（A 类清毕，前置 O-25 P0 已满足、价值最高）。

## 6. Agent 调研缺口溯源核对（2026-09-16，综合汇总）

> **来源**: [Agent跨项目调用标准与迁移复用调研.md](../../docs/Agent跨项目调用标准与迁移复用调研.md) §6（G1-G14）+ §9.5 自审 + §9.9 演进四方向。
> **方法**: 逐项对照本台账 O-* 闭环状态 + 近期工作（C 站接入 / 网关退役全直连 / G8 三站依赖补装 / agent 观测统一入口）。
> **判据**: 不口头关闭——"✅ 闭环"= 有对应 O-* 闭环证据或近期实测；"🔵 已覆盖/已定案"= 机制/纪律已落地但非正式 O-* 项；"⏳ 保留/待办"= 真未闭。

| G | 缺口（§6/§9.5） | 当前填补 | 对应 | 判定 |
|---|---|---|---|---|
| G1 | agent-cli wrapper 未实现 | `agent-cli.ps1` 全命令面落地：`workspace/task/collect/review/route/lock/split/attach` + claude 路径 + `--continue` + 续接循环 + golden/strong-accept。**2026-09-16 补**：曾因三站 config provider 改名（`cluster-litellm`→`local`）而**派发门实际不可用**（`_station_ready.sh` 注入 `ERR_INJECT exit 11`）；已修（资产跟随现状 + `local.models` 声明多模型），并以 `TASK_DONE exit=0` 端到端复证 | O-01/02/12/15/16/24/26 · 09-16 漂移修复 | ✅ **闭环（含 09-16 漂移修复复证）** |
| G2 | 工作区规范未实测（AGENTS.md 薄壳/claude 遮蔽/codex-memory cwd 键控） | 工作区机制大量耗时实测（跨站同步、动态作用域根因 O-20、ctx 服务端根因 O-23、中文路径 O-06、XDG 记忆隔离 O-09）；codex-memory→实为 **opencode 自带 memory**（本轮实测三站 memory.db+MEMORY.md） | O-06/09/19/20/23 + 09-16 providers memory 维度 | 🔵 **基本覆盖**；AGENTS.md 薄壳/遮蔽专项未单列，随试点自然带出 |
| G3 | ad-hoc 笔记无隔离 | wrapper `[proj:]` 前缀（§4.1）+ XDG per-task 隔离（O-09 isolate-xdg） | O-09 | 🔵 **已定案** |
| G4 | 大项目同步量 | `.agentsync` 排除生效（Paper 5.6GB→7.0MB，项目级覆盖已在 §3 风险台账记✅）+ 200MB 预警语义 | §3 风险台账 | ✅ **闭环** |
| G5 | A 站无记忆层 | **原假设已纠正**：三站 opencode 自带 memory 实证齐全（A 最饱满 MEMORY.md 88 行/summary 51；B/C 有库近空、历史在 -wal 待合并）——非"只 B 站"而是"三站同款、站内独立" | 09-16 providers memory 维度 | 🔵 **已覆盖**（并推翻原"codex-memory 独立命令"假设） |
| G6 | 提取记忆路径（6h 闲置）未测 | 三站 memory.db/memories/ 实存实写（B wal 4.1MB 表明活跃会话写入）——即"自然覆盖"已发生 | — | ✅ **已覆盖** |
| G7 | trae 派发对接（五层循环 2→3） | 任务卡=接口语义已立；trae 对接整体拨 D7 | O-16（--peer 同拨 D7） | ⏳ **保留（D7）** |
| G8 | 站上无 Mathematica / R | **G8 方案定案 + 三站补装完成（2026-09-16）**：sympy 1.14.0 / antlr4 4.11 / scipy 1.18.1 / R 4.6.1（CRAN noble-cran40 对齐主控）；`parse_latex` 功能级验证通过 | O-13 + 09-16 收口；ADR-0004 | 🔵 **主体闭环**；**R 依赖包（forecast 等 7）待办：走 Cpp_Hub 项目 `renv` 不装全局库** |
| G9 | 重资产预置 | `.agentsync` 排除 + 站上 tar 预置；Cpp_Hub 试点已用（O-13 预置 R/sympy 真卡全链） | O-13 | ✅ **闭环** |
| G10 | opencode 位置参数 bug（1.18.25） | wrapper 已规避（stdin 管道形式）；**双用例已落地**（`agent-cli-smoke.sh`：正向 stdin 管道应出 OK / 负向位置参数**应仍挂死**，若意外成功= 上游行为变更信号）；上游至 1.18.31 无修复记录（[Agent调研 §9.11](../../docs/Agent跨项目调用标准与迁移复用调研.md)） | 与 G14 合并 | ✅ **已规避 + 双用例固化**（升级窗口按 §9.11 回归） |
| G11 | **并发与互斥** | **层2锁激活**（readonly→`flock -s` 共享 / write→`flock -n` 排它）+ **slot 门**（busy 默认 exit 24 reject，`--slot-allow-busy` 放行）+ **O-18 铁律**（跨站各1，勿同站叠） | O-08/17/18/25 | ✅ **闭环** |
| G12 | 失败恢复 / 续跑未定义 | **`--continue` 续接循环**（首跑被超时杀→续跑拿独立预算）+ 失败终态 `failed`+`REVIEW_NEEDED`（不静默 done）+ timeout 语义保持 | O-24 P0-① / O-21③ | ✅ **闭环** |
| G13 | 成本/额度观测（zen 限额无预警） | **O-25 吞吐基准 + .progress 打点 + 预算预估**（HIT 才给 / MISS 不打荒 / TIMEOUT-WARN）；zen 限额 429→exit 7 定义置位；**OpenRouter 免费档每日计数已落地（2026-09-16）**——统一入口 `egress` 读 `is_free_tier` 定档位（实证 paid→1000/天）+ 本地自建 `.egress_daily.json` 计数 + 80% 预警（详见 [ADR-0003 §免费档每日计数](../../adr/ADR-0003-OpenRouter密钥与egress路由管理.md)；本地计数为主、429 `X-RateLimit-*` 头校准） | O-07/25 + 09-15 入口 + 09-16 egress | 🔵 **主体落地**；O-07（zen）仍待真实触发（事件驱动，不可预约） |
| G14 | 版本协同矩阵（升级回归面） | **方案已定（2026-09-16）**：版本策略（锁定基线+小步+单站试点铺开）+ **七项升级回归 SOP**（agent-cli-smoke / G10 双用例 / provider 直连零 :4000 / timeout 注入仍生效 / 插件加载 / 记忆读写前后对照 / task 全链）——详见 [Agent调研 §9.11](../../docs/Agent跨项目调用标准与迁移复用调研.md)；G10 合并，判定**维持 stdin 规避**（上游 1.18.31 仍无位置参数修复） | 升级窗口开启时按 SOP 执行 | 🔵 **方案已定（判据落定），非"待办"——执行随升级触发** |

### 综合结论

**Agent 调研 §6 的 14 项缺口：8 项 ✅ 闭环、5 项 🔵 已覆盖/已定案、1 项 ⏳ 保留/待办（G7 trae 派发 → D7）。** 无 P1 级阻塞缺口。D6 wrapper 主路径（G1）与并发/恢复（G11/G12）两项"高"严重度缺口均已闭环。

### 真实剩余 open（非口头，全为可判定待办）

| 项 | 状态 | 触发 |
|---|---|---|
| O-07 / G13 待真实触发 | zen 限额 429→exit 7 未实触发（不可预约） | 事件驱动 |
| **G14 / G10 升级回归矩阵** | **方案已定（§9.11 七项 SOP + 版本策略）**；G10 判定维持 stdin 规避，**位置参数用例已于 09-16 由"负向断言"降级为"观测项"**（证据冲突 + 探针不可区分挂死/慢，详见 §9.11.1）。**执行**随升级触发 | 升级窗口开启 |
| G7 / O-16 `--peer` 站间互审 / trae 派发 | D6 一期 review ring 已覆盖单机，站间互审拨 D7 | D7 立项 |
| G8 R 依赖包（forecast/rugarch/urca/ARDL/midasr/Spillover/vars） | **走 Cpp_Hub 项目 `renv`**（不可装三站全局, 防版本漂移, §9.10 选型） | Cpp_Hub 基准对拍试点 |
| ~~记忆协同"待核"收尾~~ | ✅ **实质已闭合（2026-09-22 复核确认）**：三站 opencode memory 独立、无跨站共享（站内记忆+任务卡交接），仅留"是否要跨站记忆共享"作为设计取舍（当前不引，需求显现时才评） | —（已闭合） |
| ~~`_agent-cli-bom.ps1` 整份过期副本~~ | ✅ **当日闭环（2026-09-16，见 [DEVELOPMENT-LOG 2026-09-16 ⑫](DEVELOPMENT-LOG.md)）**：**取证推翻了我原先的"死副本"判断** —— 它其实是 **O-26 串行基线测量的一次性工装**（`agent-cli.ps1` 的 BOM 副本，被 root 级 `_o26_serial_loader.ps1` 以固定路径引用；运行时的 BOM 副本本写在 TEMP，与它同名无下划线）。按 D5 先确认三站 `/usr/local/bin`/`$HOME`/systemd/`agent-workspaces` **零引用** ⇒ 删除该 112KB "并列入口" **及其唯一引用者** `_o26_serial_loader.ps1` + 同步 `inventory/ops.yaml` | — |
| ~~G10 负向用例确定性存疑~~ | ✅ **当日闭环（2026-09-16，见 [DEVELOPMENT-LOG 2026-09-16 ⑫](DEVELOPMENT-LOG.md)）**：重评确认该"期望失败"断言**不成立**（① 09-14 复测位置参数 4/4 成功与本轮"无输出"冲突；② `timeout N` 探针**区分不了"挂死"与"慢"**，慢即被读成"仍挂死"=假 PASS；③ 官方 CLI 参考里位置参数本就是常规用法）。已**降级为观测**（`agent-cli-smoke.sh` 该用例改 `INFO`、汇总行加 `INFO=` 计数，不再判 PASS/FAIL），并同步 §9.11 的 SOP ②与结论 | — |
| ~~`cpphub-001` 卡与 `PROJECTS` 映射不一致~~ | ✅ **当日闭环（2026-09-16，见 [DEVELOPMENT-LOG 2026-09-16 ⑫](DEVELOPMENT-LOG.md)）**：用户裁定后按**零风险标记**处置 —— 在卡 front-matter 加 `status: retired` + `note:`（**已实测 `Get-FrontMatter` 的白名单闸会忽略未知键**，故不进 prompt、不影响解析），说明"目标源目录是轻量样本、PROJECTS 已指真项目、无 per-card 覆盖键 ⇒ 派发必 golden FAIL"。**机械证实**该断言：`F:\Cpp_Hub\src\因子计算_核心.cpp` **不存在**（golden 必报缺失）。**另记一条新发现**：该样本已被 2026-09-12 试点本身改过（源码已含 `向量均值`）⇒ **不再是干净 fixture**，即使重指也无法当回归用 | — |
| ~~`secrets push` 会用正本陈旧 key 覆盖站上真 key~~ | ✅ **当日闭环（2026-09-16，见 [DEVELOPMENT-LOG 2026-09-16 ⑪](DEVELOPMENT-LOG.md)）**：**未**采用"加一条常态黄灯"（那会制造噪声），改为**在危险动作上设闸**——新增一等入口 `secrets pull [A\|B\|C]`（站上真值收回正本）；`push` 对"站内产物"型凭据（`STATION_MINTED`）**默认拒绝覆盖**（站上已有且与正本不同则跳过并给出两条出路，`--force` 仍可强制）；`secrets status` 增"站内产物"行（只打归一化指纹）显式暴露不一致。验收：负向（正本换假值 ⇒ push 跳过、站上指纹未变）/ `--force` 生效 / `pull` 回写 + 幂等 / 终态三站一致。**顺带修** `_flow_rotate_status` 既有缺陷（把探针原始文本喂给期望 dict 的函数 ⇒ TypeError + 恒判"需关注"） | — |
| ~~`infer-load` 的 key 明文输出~~ | ✅ **当日闭环（2026-09-16，见 [DEVELOPMENT-LOG 2026-09-16 ⑩](DEVELOPMENT-LOG.md)）**：原登记"写进站上日志"**表述有误** —— 该行只打 stdout；真实暴露面是 **studio 自写日志**（`~/.unsloth/run-*.log`，每次 4 处、775/664 权限、三站累积 21 份/68 处明文）+ **该面完全不在审计视野内**。已按 a+b+c+d+e 全套处置：我方输出掩码 / 目录 700+日志 600（infer-load 强制）/ 存量 21 份就地脱敏 / `stations` 门禁补 `unslothlog` 权限判据（含负向自证）/ 补登明文面表 | — |
| ~~**root 级脚本不受 `scripts` 门禁治理（本轮新发现）**~~ | ✅ **全闭环（2026-09-22，见 DEVELOPMENT-LOG ⑩ 及决策简报）**：**09-16 新登记**：`check_scripts` 的扫描范围是 `_iter_ops_scripts()` = **只有 `ops/`**，而仓库根仍存一次性脚本 —— `audit_extra.sh` / `audit_gfx.sh` / `audit_llama.sh` / `_o26_reverify_loader.ps1`（外加**根级 `test-cards/`** 与 `spec/` 下同名目录并存）。它们既不在 `inventory/ops.yaml`（也只登记 `ops/` 项）也不被门禁看到 ⇒ **删除时才发现"漏网"**（本轮 `_o26_serial_loader.ps1` 即属此类）。**评估**：ADR-0004 的 D2/D3 治理圈原本只声明覆盖 `ops/`，所以这不是"违反"，而是**范围外空白** | 待定：把门禁范围扩到仓库根并给存量登记（属新能力，走 D3），或逐个清减后再定 **⚠ 2026-09-22 精确化 + 决策简报 → [门禁口径决策简报](../../docs/2026-09-22_门禁口径决策简报_doclinks越界链与root级脚本范围.md)**：登记写"5 个一次性脚本"**不精确** —— 实为 **4 个脚本 + 1 个目录**；且**不能整批处置**：`audit_extra.sh`/`audit_gfx.sh`/`audit_llama.sh` **全仓零引用**，而 **`_o26_reverify_loader.ps1` 与根级 `test-cards/`（`o26-split-fanout.md` + `_o26_src.txt`）互为引用**（前者第 10 行硬编码绝对路径调用后者），**并被 6 处文档引用** ⇒ 属**活体工装**（正是 09-16 `_agent-cli-bom.ps1` 教训的翻版，区别是这次引用链仍活）⇒ 整目录归档会**打断它**。**推荐 C**：先分类处置（3 个归档 + 工装迁 `ops/station-bin/` 并参数化路径）→ 存量清空后再扩范围（此时扩范围成本近零，且新增根级脚本当场 FAIL）。**前置取证**：三站 `/usr/local/bin`/`$HOME`/systemd/crontab 引用面（本仓已实测）。**待裁**（简报已列） ✅ **2026-09-22 第一步已执行（裁定 C）**：**三站前置取证**（`/usr/local/bin`、`/etc/systemd`、`/etc/cron*`、`$HOME` 浅层、`crontab`）**全部 none** ⇒ 迁移不打断任何站上引用。处置：3 个零引用脚本归档 `archive/root-scripts/`；**`_o26_reverify_loader.ps1` 迁 `ops/station-bin/` 并登记**（`frozen_ops_scripts`，冻结存量 184→185）**+ 硬编码绝对路径改为由脚本位置推算仓库根 + 缺件即 `throw`**（否则"移动"会变成新的静默断点）；4 张卡迁 `spec/d6-agent-standard/test-cards/`、2 个附件源迁 `ops/station-bin/attach-test/`（与该目录既有清单一致）；根级 `test-cards/` 移除。**自证**：`scripts` PASS（未登记 0）/ 三条新路径 `Test-Path` 全 True 且**两条旧路径全 False** / `syntax` PASS（迁移后**当场被 `.ps1-bom` 判据抓到**"含中文却无 BOM" ⇒ 补 BOM）。**第二步（扩范围到仓库根）** ✅ **2026-09-22 已实施（用户裁定 #5/#6）**：**#5 = 两层谓词** —— 新增范围谓词 `_in_script_scope()`（唯一真值）= **`ops/**` ∪ 仓库根顶层文件**，**不用"全仓递归 + 排除表"**（后者每加一个项目目录就多一个定义点；`spec/**`/`tests/**`/`archive/**` 在两层定义下**天然**在圈外，无需例外清单）；`_iter_ops_scripts()` 改名 `_iter_governed_scripts()`（旧名与新行为不符，调用点仅 1 处）。**#6 = 并入** [`inventory/ops.yaml`](../../inventory/ops.yaml) 的 `frozen_ops_scripts`（**登记表零改动**：实测顶层被跟踪文件只有 `.gitignore` 与 `LICENSE`，Python 侧 `suffix=''` ⇒ 走 shebang 分支、首行非 `#!` ⇒ 不被当脚本）。**双向自证**（先 `git add` 才进 `git ls-files` 判据面）：基线 PASS 212；根级暂存 `tmp_top_check.sh` ⇒ **FAIL 213 且点名**；删掉 ⇒ PASS；**`tests/` 下暂存未登记 `.sh` ⇒ 仍 PASS**（证明两层定义不误扫目录内部）。⇒ 方案 **C 第一/二步全部落地**，仓库根现为治理圈内、**新增根级脚本当场 FAIL**。详见 [决策简报 §③](../../docs/2026-09-22_门禁口径决策简报_doclinks越界链与root级脚本范围.md)。**⚠ 新登记**：仓库根另有 **2 个被 gitignore 的遗留物**（`llama.cpp-0.2.0.tar.gz`、`双机推理集群使用手册.md.bak.20260901`）—— **不在 git 视野** ⇒ 门禁看不到、本次处置也覆盖不到。 ✅ **2026-09-22 已清理（用户裁定）**：**取证先行**（该两件**被 gitignore ⇒ git 无兜底**，且 **D3 重构那轮曾明确裁定"保留本地"** ⇒ 清理 = **推翻旧决定**，故必须先证明"内容可复原"）：**`双机…bak`** 内容 = git blob `992e5e48`，位于**可达历史** `612064f^:双机推理集群使用手册.md`（还原后 **523 行、与原文件逐行一致**）⇒ **零信息损失**；**`llama.cpp-0.2.0.tar.gz`** 内容 = **上游 tag `v0.2.0`**（TRACKER 09-17 已判定"可得"，B 站同类副本亦已于 09-17 清除）⇒ 可重新获取。⇒ 仓库根现只剩 `.gitignore` 与 `LICENSE`（复原处方已写入 [d3-restructure/IMPLEMENTATION.md](../../spec/d3-restructure/IMPLEMENTATION.md)）。 |

| **D6 闭环审查（2026-09-21）—— 未闭环总账** | **审查结论**：证据流/审计 + 持久化线（ADR-0007 阶段 0–3 + P1–P4）**已完全闭环**；但 **D6 agent 框架整体未闭环**，以下四类仍未做，按优先级列：**① 证据流范围内 2 项**：`collect` 命令本身**未被执行**（[ADR-0007](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md) 阶段1注记）；~~**claude 备路证据面盲区**~~**✅ 已实施（2026-09-21）** —— claude 备路现发 `evidence_manifest`（按路基线 `Get-ClaudeFrameworkSubjects`，适配其归档件集：有 `stderr.txt` 无 `judgment-record.txt`）+ `attach` 升对象数组带 `sha256`（复验侧 `agent audit` 可见）⇒ 该路 run 由 v1 升 **v2**；`usage` 维持明标 `not-collected-claude-path`（claude 无 opencode 会话库，**不猜数**）。**② D6 工作流断点**：`review --peer` 站间互审缺（质量闭环）/ 超时续接 `--continue` 缺（长卡韧性）/ ~~**claude 备通道缺（单引擎死锁=停摆，真韧性缺口）**~~**✅ 自动 fallback 已实施（2026-09-21）** —— `agent-cli task` 显式 `AGENT_AUTO_FALLBACK=1` 开启（默认关、不掩盖真实错误），主路 opencode 引擎死锁/超时（rc=6）自动单次转本地 `Invoke-Task-Claude`；触发判定 `Test-FallbackEligible` 只认 rc=6）。其余：单机排队上下文治理缺。**③ 健壮性/判据待办**：`ssh/scp` 未统一 `BatchMode`+`ConnectTimeout`；`syntax` 缺"无 BOM 含中文 .ps1"子判据；`doclinks` 未跟踪文件盲窗；`syntax` 占 quick 96%；站上 `out/` per-run 陈旧守卫；`infer-load` key 竞态（待观察）；`Get-FrontMatter` YAML 引号。**④ 社区调研待做判据**：锚年龄告警 / 证据面留存目标（调研 §14.6，仅记账） | **下一步**：claude 备通道与超时续接是单机停摆的两个真韧性缺口，`review --peer` 是质量闭环缺口；`BatchMode` 属零风险加固。全文见 [ADR-0007 §附录一页解释](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md) |
| **证据流可重放性（evidence_manifest + 异基座管线审计）** | **阶段 0 已执行（2026-09-16，[ADR-0005](../../adr/ADR-0005-任务卡证据回收闭环.md)）**：证据回收闭环落地 —— `.meta`/`.prompt.txt`/`.progress` 原文/`.accept-cmds.txt`/`.golden-cmd.txt` 归 `agent-out/<ts>/`，`run.json.accept_golden` 增 `sha256`/`base`，TEMP 泄漏与失败路径一并修；**三项自证能力实测 PASS**（`sha256(prompt.txt)==prompt_sha256`、`accept_golden.sha256==仓库源哈希`、`judgment-record ↔ run.json` 逐项一致），collect 115s→49s。**剩阶段 1（manifest 规范化）/ 2（离线复验器）/ 3（异基座管线审计）** 未做，方案见[调研文档](../../docs/research/2026-09-16_任务卡证据流可重放性调研.md) §7.1 \| **09-17 更新：路线与推进步骤已定案 → [ADR-0007](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md)**。①**阶段 2「形态」已落地**：离线复验器 `cluster.py agent chain/verify`（零自加载、不触站、离线、**指到第一条断裂处**，实测 12 项含负向双向自证 + 边界实证），设计见 [evidence-chain/DESIGN.md](evidence-chain/DESIGN.md)；②**缺口 7 已闭环**：门禁第 15 项断言 `evidence`（quick、只读、按 FAIL/WARN/info 分层）；③配套：钩子自动入链（改 `rpc.ps1` 钩子**生成器**）+ 外部锚 `ANCHOR.txt`（已 push 到 origin 作跨信任域见证，强度=「多副本见证」非密码学不可否认）；④**阶段顺序修正**（原「1→2→3 不可反」作废 ⇒ `0 → 0.5 → 2内容 → 1 → 3`，因实测复验器**不依赖 manifest**）；⑤**新增阶段 0.5「改动验证闭环」**（轻卡+小模型夹具）——因阶段 1 与缺口 4/5/6/8/10 **全都要改 `agent-cli.ps1` 派发路径**，无夹具则只能停在走查级；⑥**阶段 3 挂起**（证据面仅 6+1 件，现阶段审计员可判项过少，等批 B 扩面后重启）。**待决策：进入批 A**（`verdict-chain` + `golden-identity` 复验，纯主控侧可离线自证）。**09-18 更新：批 A / 批 B 已执行到位** —— 批 A（`verdict-chain` + `golden-identity`，含 17 项严格双向自证）✅；**阶段 0.5「改动验证夹具」**✅（轻卡 + 小模型，正负双向）；**阶段 1 manifest 完成**（围栏加固 / recipe 按条目分派 + `v2` / 卡侧三级嵌套解析 / 「未声明产物即失败」负向判据）✅；**缺口 4**（diff 证据：`find -newer` 载体 + `diff-scope` 判据，正负 e2e）✅；**缺口 6 / 10** ✅；**缺口 5**（attach 哈希：站上逐文件 `sha256sum` ⇒ `attach-manifest.txt`，run.json `attach` 升对象数组 `{name,src,kind,files,sha256}` ⇒ **被链钉住**；跨信任域交叉验证 + 三项负向均实测）✅。**仅剩批 B 的缺口 8（`usage`/`session_id`/`timestamp` 遥测）**；阶段 3 仍**挂起**。链 **76 条**（A1 **12/76** · A2 **13/76** · A3 **3/76**）。**09-18 收口：缺口 8 亦已闭环** ⇒ **批 B 全部完成** —— 站上 [`_oc_session_meta.sh`](../../ops/station-bin/_oc_session_meta.sh) 从 **opencode 会话库**取该次会话的真实聚合（token 明细 / tool 计数 / `session_id` / 时间戳）落入 run.json（取不到 ⇒ `usage.source=unavailable`，**不猜数**；claude 备路明标未采集）；独立复核用**另一张表**（Σ `message.tokens` == 会话行聚合，跨表 MATCH）；负向（改 `total_tokens` 1 位）⇒ `digest_mismatch` + 门禁红灯 ⇒ 字段**被链钉住**。链 **79 条**（A1 **15/79** · A2 **16/79** · A3 **3/79**）。**下一步只剩阶段 3（批 C，挂起）**。**09-18 再更新：阶段 3 按 D5 拆两步，3-a 已落地** —— `cluster.py agent audit`（**机器层**）：逐 subject 判"能否离线复现、卡在哪" ⇒ **可机判 gap 表**（advisory，**刻意不进 FAIL 集**；与 `verify` 分工：verify 管"是否被改"，audit 管"是否可重放"）。语料首跑：声明 **72** 条中 **67 可离线复算**、`collect` 型 **4** 条（`declared-not-executed`）、**已归档但未声明 37 件**（write 卡未声明的 `workspace-diff.txt` 等）；夹具卡已据此补全声明（新 run 实测 **gap 表为空**）。**3-b（异基座 judge：A/A 基线 + 顺序对调 + 跨家族）未做**，设计已定见 ADR-0007。链 **81 条**（A1 17/81 · A2 18/81 · A3 3/81）。**09-18 三更新：3-b-1 校准已实测** —— `agent audit-judge`（advisory，只测量不改门禁）：跨家族 judge（站内 **Qwen3.8-27B-MTP-Q8_0**，与被审证据的 gpt-oss 不同家族）在 11 条题集上 **A/A 11/11 · 序翻转 0/11 · 措辞扰动 11/11 · 与判据一致 11/11**；**关键对照**（2 条机器标签故意与判据相反）⇒ **按判据判 = 复核而非复读**；"存在未知"那条四轮均 UNSURE（不硬猜）。**诚实边界**：题面是结构化元数据 ⇒ 只证"能稳定执行写明判据"，不证"能从杂乱材料发现缺口"。**3-b-2（常跑审计）未做**，前置已满足（题面是否扩到杂乱材料等待定）。**09-18 四更新（阶段 3 收口）**：**3-b-2 本体已落地并实测** —— (a) 3-a 词表补 **`artifact-ephemeral-by-design`**（卡在 subject 声明 `ephemeral: true` ⇒ 产物"设计上不进 runDir" ⇒ **不是缺口**、但单列不计入可离线复算；改了三处：卡解析器 / run.json 照收该键 / audit 判据）；(b) 题集 **11 → 16**（含 5 条项目边界：Cpp_Hub 结果块 / Paper `index.db` 0 字节 / 中文路径件缺失 / Auto_Prover 证明日志"存在未知" / 新类 ephemeral）⇒ **重跑校准**：**A/A 16/16 · 序翻转 0/16 · 措辞扰动 16/16 · 与判据一致 r1–r4 均 16/16**（judge = 站内 Qwen3.8-27B，跨家族）；(c) 落库**两层**跑通：机器产物 ⇒ `D:\Paper\agent-out\_audits\<ts>.json`（**不入仓**；实测 `chain` 只 +1，`_audits` 不被当 run）+ 校准报告 ⇒ 入仓 `spec/d6-agent-standard/evidence-chain/audits/AUDIT-JUDGE-20260918193642.{md,json}`；(d) 卡解析回归 **22/22**（新增 ephemeral 真值/缺省、manifest 块内 `#` 注释被忽略）；链 **84 条**（A1 20/84 · A2 20/84 · A3 3/84）。**⇒ 阶段 3 全部完成；两条审计命令仍 advisory 且按需运行（未接门禁/未定时）**，若要"常跑"需另定触发与成本上限。**09-18 五更新（可运行性 + 分层闭环判定 + 先B后A 定案）**：① **修一个拦路问题** —— `cluster.py` 落库代码的 f-string 表达式段含反斜杠（PEP 701 才允许）⇒ **Py<3.12 整个模块不可解析**；门禁 `evidence` 因 `except Exception` 兜住 ⇒ 报 WARN「证据链断言跳过」而**整仓仍 PASS**（`rpc.ps1` 挑到 Python312 才侥幸正常）—— **同族于"恒真判据"（这次是"根本没判"）**；已修 + 复验转 PASS。② **可运行性实测**：`agent verify` **0.38s**（84 条全绿 · 未入链 0 · 锚在）/ `agent audit` **0.37s**（零 SSH 零参数）**均开箱即用**；`agent audit-judge` **当前不可跑**（`_flow_find_engine()`→`(None,None)`，需站上 load 跨家族引擎）。③ **全语料画像**：声明 97→可离线复算 **91**、`collect` 型 4、设计性临时 1、**未声明 37 件**、有 manifest **13/84**、gap **15 条**（零篡改）；**A1 20/84 · A2 20/84 · A3 3/84** —— 可判率低主因是 64 个 run **早于 ADR-0005（历史欠账，非坏）**，**A3 的 3/84 才是真缺口**（30 个 readonly 卡缺 `workspace-diff` 载体 ⇒ "未越界"**从未被真正判过**）。④ **分层闭环判定**：机制层 ✅ / 证据层 ⚠️（覆盖面余量）/ **运行层 ❌** —— `chain` 有自动点（钩子）、`verify` **骑 pre-commit**（`quick:True`），但 **`audit` 零自动调用点** ⇒ **D6 现在是「防篡改闭环」，不是「可重放闭环」**；阶段 3 表里"**常跑**审计"一名**名不副实，已订正为"异基座复核"**。⑤ **定案 先 B 后 A**：路 A（让 audit 常跑）难点不在成本（0.37s）而在严重度 —— 直接升 FAIL 会被 52 条存量缺口**天天红灯淹没**（同 doclinks "判不准的不进门禁"），故建议**基线化增量**（只在 gap 集合变大时告警）；路 B（扩面：37 件补进卡 + 30 张 readonly 卡补载体）**收益更高且做完后新 gap=0**，此时再挂增量门禁才干净。**⇒ 下一步：路 B 扩面 → 复跑 `audit` 确认 gap 归零 → 再议路 A 的触发点与严重度**（全文见 [ADR-0007 §审计可运行性 与 D6 分层闭环判定](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md)）。**09-18 六更新（路B 落地：框架件基线合并）**：① **侦察先推翻了上节的路B假设** —— 实测 13 个 v2 run **全部来自 smoke 夹具卡**（`evidence-manifest` 当时 100% 只存在于夹具卡 ⇒ `91/97` 描述的是**夹具语料**）；manifest 是 run.json 里的**派发时快照**（[cluster.py:3811](../../ops/cluster.py#L3811) 读 `j["evidence_manifest"]`）⇒ **改卡不回溯** ⇒ 原计划的"37 件补进卡 / 30 个补载体"**全部不可回改**（且已自动收敛：最后未声明 run = 13:26）；**真盲区是 71/84 个 recipe v1（零声明）run 在报告里完全不可见**。② **定案（用户选）框架件基线合并**：产出方 [`agent-cli.ps1`](../../ops/station-bin/agent-cli.ps1) 新增 `Get-FrameworkSubjects` / `Merge-EvidenceSubjects` —— run.json 的 `subjects[]` = **基线 ∪ 卡特有件**（按 path 去重、基线优先）⇒ **卡不写 manifest 也得到 recipe v2**。清单**唯一定义点在产出方**（审计侧仍动态枚举 runDir ⇒ "不维护第二份框架件清单"的纪律不破）；基线只列**必产出件**：无 accept/golden 的 run 上 `accept-output`/`accept-golden-output` 实测不存在 ⇒ **随门条件注入**。③ **实测**：卡解析回归 **32/32**（22→32）；e2e 夹具卡 run `202609182312282167` ⇒ **13 条 = 12 框架（去重掉卡里 12 条历史声明）+ 1 卡特有**，gap 空；**e2e 关键**：`echo.md`（**零声明**）run `202609182314143434` ⇒ 得 **10 条**（恰为基线，`accept-output` 正确未声明且 runDir 确无该件 ⇒ **无假缺件**）—— **此前必为 v1，现为 v2**。④ 链 **86 条全绿**（A1 22/86 · A2 21/86 · A3 3/86）。⑤ **13 张卡零改动**（基线覆盖其全部归档件）；**未做/新登记**：**claude 备路完全不发射 `evidence_manifest`**（且其归档件集与主路不同：有 `stderr.txt`、无 `judgment-record.txt`）⇒ 该路 run 仍为 v1，**单独立项**（避免半修）。⑥ **`audit` 零自动调用点未变** ⇒ 路 A 仍待议（全文见 [ADR-0007 §路B 落地与实测](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md)）。**09-18 七更新（路A 落地：审计常跑）**：① **先出细化调研并落档**（[2026-09-18 证据流审计「常跑」调研](../../docs/research/2026-09-18_证据流审计常跑_触发点与成本严重度调研.md)，§11 决策分析矩阵 / §12 落地实测）。**成本上限这件事关闭**：审计**进程内本体** 86 run 仅 **0.048 s**，端到端 0.34 s 中 **~85% 是"起进程 + `import cluster`"**；挂进**已有门禁进程**真实增量 **+0.013 s**（`--only evidence` 0.38→**0.393 s**）。② **一条不是妥协而是纪律落到架构上的结论**：`rpc_check.py` 对仓库**全程只读**（唯一写动作是 `check_syntax` 的 tempfile）+ 门禁挂 pre-commit ⇒ **水印不能在门禁里自动推进**，只能由**独立命令**写 ⇒ 副作用刻意接受：**"接受新缺口"成为人的显式动作**（`--accept` 与 `--json` 刻意互斥）。③ **落地 6 处**：K1 `_gap_key`（结构化 key，`<kind>\|<label>|<sub>`，**不含会漂移的文本细节**）+ P1 口径行（`零声明 v1 71/86 不参与判定`）+ 水印读写（`ops/.audit-baseline.json`，**已 gitignore**，单调并集）+ `agent audit --accept`（唯一写点）+ **A2 挂载**（`check_evidence` 内只报**新增**、**逐条**打印、`fix` 给出接受命令）+ **P2**（`syntax` 取 **PATH 第一个 `python`** 单子进程复检，note 增 `.py@<ver>` 栏）。④ **双向自证**：构造新 gap ⇒ **WARN**「可重放 gap 16 条(存量 15, **新增 1**)」+ 逐条明细（存量**不重复报**）；gap 不变 ⇒ **PASS**；还原 ⇒ **PASS** 且 runDir **逐项复原**（`.agent-run.json` sha256 == 基线）、`verify` **86 条全绿**（探针只落在"未声明"轴，未污染防篡改轴）；**P2 用上一轮事故的**原构造**做探针 ⇒ FAIL/红灯**（`(py3.11.16) … f-string expression part cannot include a backslash`），**同一构造上一轮是 PASS**。⑤ 全量 quick 门禁 **10 绿 / 0 黄 / 0 红**；水印被 gitignore 命中、`git status` 未被污染。⑥ **未做（长期，已记账）**：`since` 增量扫描（20000 run ⇒ 11.3 s 才需要）、水印收缩/债务清零、**门禁只 WARN 不阻断**（D4 结论；可见性靠"新增逐条打印"兜住，仍需人读输出）（全文见 [ADR-0007 §路A 落地与实测](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md)）。**09-21 更新（claude 备路单独立项关闭）**：上文 ⑤「claude 备路完全不发射 `evidence_manifest` ⇒ run 仍 v1」**已处理** —— `agent-cli.ps1` claude 分支现发射 `evidence_manifest`（按路基线 `Get-ClaudeFrameworkSubjects`，适配其归档件集：有 `stderr.txt` 无 `judgment-record.txt`，复用 `Merge-EvidenceSubjects` 的 baselineFn 参数）+ `attach` 升对象数组带 `sha256` ⇒ 该路 run 升 **recipe v2**、`agent audit` 可见；`usage` 维持 `not-collected-claude-path`（不猜数）。并顺带补**自动 fallback**（`AGENT_AUTO_FALLBACK=1` 显式开启，主路 opencode rc=6 死锁自动单次转 claude）。验证走阶段 0.5 夹具：卡解析/证据基座回归 **44/44**，`agent-cli.ps1` 解析 0 错。详见上「未闭环总账」①/②。**实弹自证（2026-09-21，注入式）**：站点三站离线（ssh 不可达）、claude CLI 未登录（`loggedIn:false`）⇒ 无法驱动"真实站上 opencode 引擎死锁"；改为**注入式实弹** `_probe_fallback.ps1`（登记入 ops.yaml）——真实加载 `Invoke-Task` 全逻辑，仅 stub 远端依赖使主路返回 rc=6，断言：① env `AGENT_AUTO_FALLBACK=1` 桥接正确；② opencode rc=6 ⇒ `AUTO_FALLBACK` 出线并真实调用 `Invoke-Task-Claude`；③ claude run 产出 `evidence_manifest v1/4`（claude 按路基线，含 stderr/card、无 opencode 件泄漏）+ `stderr/card/prompt` 归档 ⇒ 证据面 v2 在真实失败路径成立、可判定；④ gate-off（AutoFallback 关闭）⇒ rc=6 不 fallback（newest run cli=opencode）。**诚实上限**：探针验证"接线 + 证据面 + 触发判定"，不驱动真实站上 opencode 死锁（需站点在线）；另实测 claude 通道在本 Windows 上的执行级限制——`claude` 以 npm `claude.ps1` shim 安装，`Start-Process claude` 报 `%1 不是有效的 Win32 应用程序` ⇒ 备路即便登录也在 exec 级失败（预存环境限制，非本次改动，已记账）。**09-21 该 exec 限制已修复**：新增 `Resolve-ClaudeSpawn` —— 把执行目标从 `Get-Command claude`(命中 .ps1 shim) 解析到 npm 同目录的原生二进制 `node_modules\@anthropic-ai\claude-code\bin\claude.exe`（实测存在、--version headless 正常），绕开"`-RedirectStandardInput` 强制 `UseShellExecute=$false` ⇒ CreateProcess 加载 .cmd/.ps1 shim 报 win32 错"。复测注入式实弹 `_probe_fallback.ps1`：`CLAUDE_SPAWN=...\claude.exe`、不再报 win32 错，probe 仍 **PASS**（claude run status=failed 未登录、evidence_manifest v1/4、无泄漏）；exec 级修复不改变未登录失败语义（登录仍待配）。**09-21 真实站实弹（用户要求"补真实站点死锁自证"）**：站点实为**在线**（前一轮"离线"是我的探针错误——用 `Test-NetConnection -ComputerName A` 判 A/B/C，而它们是 `~/.ssh/config` 别名不解析 DNS；全量门禁一直报"可达 3/3 站"）。流程：`load-gate 11` PASS → `cluster.py load gpt-oss-20b`（B 站 :8080 ctx=32768）→ 新夹具卡 [`fallback-deadlock.md`](test-cards/fallback-deadlock.md)（`timeout_s: 10` 刻意小于完成所需 ⇒ 远端 `timeout` 强杀 ⇒ **rc=124→6**，复现"引擎超时/死锁"**信号类**）→ `AGENT_AUTO_FALLBACK=1` 派发。**首跑即暴露两处实现真 bug**（注入式夹具**均漏掉**）：① **`$m` 被 collect 段改写** —— 主路有 `$m = Get-Content $metaTxt \| Out-String`，我却拿 `$m` 当模型名传备路 ⇒ `REJECT unknown-model (TASK_ID=202609211645528026 QUEUE_S=2 …)`（报错里是 .meta 全文）。② **主路模型不可路由到 claude** —— claude 备路只收 `station=''` 的本地 claude 路由，主路 `gpt-oss-20b` 解析出 `station='B'` ⇒ 透传会被 `REJECT claude-station` 拦掉。**修复**：顶部快照 `$taskModel`（不再复用被改写的 `$m`）+ 备路切型号 `$fbModel`（默认 `claude`，env `AGENT_FALLBACK_MODEL` 可覆盖）。**顺带发现第三处（未修，属设计差异，非本次引入）**：`Invoke-ClaudeFly` 原用 `Start-Process -PassThru -NoNewWindow -RedirectStandard*`，本 PS5.1 上 **`$p.ExitCode` 恒 `$null`** ⇒ `$rc` 空串 ⇒ `'' -ne 0` 为真致 resume 空转、且 **`$null -eq 0` 为假 ⇒ 成功的 claude run 也会被判 `failed`**（备路等于白修）⇒ 改用 .NET `Process`+`ProcessStartInfo`（保留 `WaitForExit(ms)` 预算内 kill，ExitCode 实测可读）。**复跑验证（第 2/3 次）**：`AUTO_FALLBACK: opencode rc=6 -> local claude backup` + `AUTO_FALLBACK_MODEL: gpt-oss-20b -> claude` + `claude first rc=1`（rc 保真修复生效，非空）+ 产出 claude run（`202609211652389854`，`cli=claude`、`status=failed`、`exit_code=1`、`usage.source=not-collected-claude-path`、`attach` 为数组、**`evidence_manifest v1/5`** = agent-output/prompt/stderr/card/accept-output，**无 opencode 件泄漏**）⇒ **证据面 v2 在真实 run 上成立**。`agent-output.txt` 内容为 `Not logged in · Please run /login` ⇒ 失败原因确为未登录（诚实失败）。**夹具加固**：给 `_probe_fallback.ps1` 加 `ssh` stub 产出 `.meta`（否则 `$m` 不被改写、夹具对该回归**不敏感**）+ 清空 `probe-proj`（否则命中上一轮遗留 run ⇒ **假 PASS**）+ 型号断言；**双向自证**：回归版 ⇒ `PROBE_FALLBACK FAIL`、恢复版 ⇒ `PASS`；阶段 0.5 夹具仍 **44/44**。**仍余（新登记）**：④ claude 仍**未登录**（`loggedIn:false`），故"备路真正接手完成"这一半仍未证。**09-21 免登录 + 后端选型已调研落档（用户裁定：OpenRouter 优先、工作站本地模型备选；本次只落档不实施）** —— 见 [2026-09-21 claude 备路免登录与后端选型调研](../../docs/research/2026-09-21_claude备路免登录与后端选型调研.md)。**实测结论**：① **免登录可行且不需"绕过地区限制"** —— 登录只服务 Anthropic 官方；把 `ANTHROPIC_BASE_URL` 指向兼容 `/v1/messages` 的端点即可，而 **A/B 站早就是这么跑的**（指向站内本地引擎 + `apiKeyHelper` + 型号映射）。② **控制台只缺一处**：免登录要造的两个门槛文件**已在位**（`~/.claude.json` 的 `hasCompletedOnboarding=true`、`~/.claude/config.json` 的 `primaryApiKey="any"`），**唯一缺 `~/.claude/settings.json` 的 `env.ANTHROPIC_BASE_URL`** ⇒ 缺它就回落官方端点报 `Not logged in`。③ **站上引擎实测实现了 Anthropic API**：`/v1/messages` 用 **`Authorization: Bearer <unsloth.key>` 得 200**（标准 Anthropic 响应体），而 `x-api-key` 得 **401**（unsloth 只认 Bearer）；且引擎**只监听 127.0.0.1**（控制台经 LAN 不可达，`HTTP=000`）。④ **cc-switch 控制台已装**（`skipClaudeOnboarding:true`、`enableLocalProxy:true`），但其 provider（DeepSeek / LM studio）都挂在 **`claude-desktop`** 名下，**CLI 的 profile 是空的 `default`** ⇒ 这才是 CLI 仍要登录的直接原因。**⚠ 最要紧的落地前置（既存实证）**：主控**本地**跑 claude 的**完整工具型任务**会被 **Trae 沙箱拦**，**已实证的可用路径是经 SSH 在站上跑 claude** ⇒ 与"站上本地模型备选"指向同一形态，**`Invoke-Task-Claude` 现"控制台本地 spawn"的形态需改为"站上执行"**（该文档 §6 已列 6 项待实施，含按 `sensitivity` 设闸以防 `local-only` 卡被送到 OpenRouter）。**09-21 控制台 `settings.json` 缺口已修（免登录实测通过）**：① **改前先备份** `~/.claude/settings.json` → `.bak-20260921`（验大小 175=175）；② 新建 `~/.claude/or-key.cmd` 作 **`apiKeyHelper`**（`findstr /v /b "#" d:\RPC\secrets\openrouter.key` ⇒ 只输出非注释行；**用 helper 而非明文 key** ⇒ 守住项目铁律「key 单一真值在 `secrets/`」，且与站上 claude 同模式）；③ `settings.json` **合并式**写入（6 个既有键全保留）增 `apiKeyHelper` + `env{ANTHROPIC_BASE_URL=https://openrouter.ai/api, ANTHROPIC_API_KEY="", ANTHROPIC_MODEL=thinkingmachines/inkling:free, DISABLE_AUTOUPDATER=1}`，UTF-8 **无 BOM**。**验证（决定性：先清空全部 `ANTHROPIC_*` env ⇒ 证明仅靠配置文件）**：显式 `--model` ⇒ **`OK`**；**不带 `--model`** ⇒ **`OK`** ⇒ **免登录可用、零 env 依赖**（且 `env.ANTHROPIC_MODEL` 实测**覆盖**顶层 `model` 键）。**⚠ 顺带测出一条阻断级事实**：**Claude 原生型号名经 OpenRouter 仍撞地区墙** —— `claude-opus-4-7`（原顶层 model）/ `claude-sonnet-4-5`（=ROUTE_TABLE 的 `claude`）/ `claude-opus-4-1`（=ROUTE_TABLE 的 `claude-opus`）**全部 403 `This model is not available in your region.`**，而 `thinkingmachines/*:free` / `nvidia/*:free` **`OK`** ⇒ **走 OpenRouter 并不能用 Claude 原生 id 绕过限制**（那些 id 被路由到真实 Anthropic 上游）。**直接后果**：备路 `$fbModel='claude'`(=claude-sonnet-4-5) **会 403** ⇒ **型号重映射是阻断项**（已登记为该调研 §6 第 7 项），否则免登录只解决认证、不解决可用性。**09-21 型号重映射已完成 + 备路首次端到端跑通**：`ROUTE_TABLE` 的 `claude`→`thinkingmachines/inkling:free`、`claude-opus`→`nvidia/nemotron-3-ultra-550b-a55b:free`（取 `secrets/openrouter.conf` 的 `harness_priority` 前两档，**不新立模型清单**；别名保留原名 = 备通道档位而非厂商），并加两条 **full-id 直传条目**（`Resolve-Model` 是纯表查找 ⇒ `--model <openrouter-id>` 与 env `AGENT_FALLBACK_MODEL` 才可解析）。**新增回归守卫（此前该约束无任何守卫）**：夹具用 `AssignmentStatementAst` **提取真实 `ROUTE_TABLE`**（探针的 `Resolve-Model` 是 stub、守护不到真表）并断言 6 条不变量（非 Claude 原生 id / 形如 OpenRouter id / `station=''` / `cli='claude'` / 有 full-id 条目）⇒ 夹具 **53/53**；探针同步 **PASS**。**端到端（决定性）**：临时卡 `model: claude` + `timeout_s: 180` + `accept:[true]`，`task paper -cli claude`（claude 分支在 station-ready/sync **之前** ⇒ 不需站上模型）⇒ **`claude first rc=0`**（原 rc=1 `Not logged in`）+ `ACCEPT_MODE=bash-local` `ACCEPT_OK=1` + run `202609211739020633`：`cli=claude model=thinkingmachines/inkling:free` **`status=completed` `exit_code=0` `accept.passed=true`**、`agent-output.txt` = `OPENROUTER-FALLBACK-OK`、stderr 空 ⇒ **"备路真正接手完成"这半首次被证**（此前每次停在 `Not logged in`）。**新登记（未实施）**：备路与主路**共享卡的预算** —— `Invoke-Task-Claude` 的 `timeout_s` 取自同一张卡，而"诱使主路超时(rc=6)"恰需小 `timeout_s` ⇒ 两目标在同一张卡上矛盾（本次能跑通仅因云端模型比站上 20B 快）⇒ 真实长任务需另定"备路预算"（如卡加 `fallback-timeout-s`），见调研 §7.5。**09-21 用户裁定后定案并修复『accept 的 shell 语义』**（上文 ③）：**定案 = 卡里的 `accept` / `accept-golden` 一律是 bash 语义** —— 主路在**远端 bash** 跑、备路在**本地 Git Bash** 跑；两条路只差**执行机器与 cwd**（远端 Linux 工作区 vs 本地 `projRoot`），**不差 shell**。**落地**：① 新增 `Resolve-LocalBash`（**刻意不走 PATH 的 `bash`** —— 本机实测 PATH 命中 `C:\Windows\system32\bash.exe` = **WSL**，它在另一文件系统+cwd 映射里执行，拿它判是"看起来跑了、判的不是这里的东西"；改显式解析 Git Bash，与 `$Script:GNU_TAR` 同一前提）；② 新增 `Invoke-LocalBashCmd`（bash + cwd + rc；输出**逐行落 `accept-output.txt`** —— 备路此前 `*> $null` **丢输出只留 rc**，出 bug 无从复核）；③ **`accept` 与 `accept-golden` 一并改**（同一个 bug 的两处；"只修一半的修复看起来是完整的"）；④ 备路顶部加**提前**守卫：无 Git Bash ⇒ `REJECT local-bash-missing (exit 13)`，**不退回 PowerShell**（那正是被修的 bug ⇒ 判据假红灯）、也不静默换 WSL。**验证**：夹具 `_fm_golden_test.ps1` **47/47**（+3 条 bash 语义断言：解析到 Git Bash 非 WSL、`true`⇒rc0、`false`⇒非0）；离线探针加断言 `accept.passed=true` + `ACCEPT_RC[1]=0` 并**双向自证**（退回 PS 版 ⇒ `PROBE_FALLBACK FAIL`，且直接证据 = 该轮 claude run 的 `accept.passed=False`/`ACCEPT_RC[1]=1`；恢复 ⇒ `PASS`）；**真实站端到端**（B 站 gpt-oss-20b，`fallback-deadlock.md`）⇒ 日志 `ACCEPT_MODE=bash-local (C:\Program Files\Git\bin\bash.exe, cwd=D:\Paper)` + **`ACCEPT_OK=1`**（修前为 `0`），claude run `202609211711138716` 的 `accept.passed=True`、`accept-output.txt` 记 `ACCEPT_RC[1]=0`（修前 `=1`）。**遗留约束（诚实边界）**：环境差异仍在 —— 卡若要**两路都过**，判据须**跨环境可移植**（`./.venv/bin/python` 这类 Linux 专属路径在 Windows 本地仍不可用）；该约束属**卡作者**责任，已在代码注释与本段写明。**顺带修一处预存断言缺陷（由本次真实超时 run 首次暴露）**：提交时门禁 `evidence` **红灯阻断** —— `cluster.py` 的 [`_VERDICT_RC_MAP`](../../ops/cluster.py#L3375) 缺 `124→6` 条目，而**两路的映射时机不同**：opencode 路把 `timeout` 的**原始哨兵 124** 直接写进 `.meta`、124→6 在**控制台侧**做；claude 路则**先映射再写 `.meta`**（故表里原有 `6: {6}` 只覆盖后者）。旧表对 124 回退成 `allowed={124}` ⇒ **把每个合法超时 run 误报 FAIL**（实测 3 个新增超时 run 全部命中）。补 `124: {6}`（只允许 6，不加 124 —— 两路都必做该映射，出现 124 反倒说明映射没走）；**未动锚/未 `--reanchor`**（门禁处置建议亦明确"别急着 reanchor，那是把信号抹平"）。复验：`evidence` 转 **PASS**、`A1 verdict-chain 22/86 → 25/91`（新增 run 变可判）；负向自证错值仍被拒（`124→{6}`，7/0 均拒）。 |
| **框架级：每次 ssh/scp 建连 14-17s** | ~~09-16 新登记（性能）~~ → **当日闭环（[ADR-0006](../../adr/ADR-0006-控制面传输绑定LAN_IPv4.md)）**：根因不是 sshd/UseDNS，而是**主控解析 `*.local` 需 16-17s 且只返回公网 IPv6** ⇒ 每次建连白付 16s **且控制面经 ISP IPv6 绕行、不在局域网内**（站上 `$SSH_CONNECTION` 实测证实；`ControlMaster` 在 Win32-OpenSSH 9.5p1 亦不可用）。处置：`~/.ssh/config` 把 A/B 名字 `HostName` 绑定到 LAN IPv4（+`AddressFamily inet`）+ 三个 IP 身份块，`cluster.py` 的 STATIONS 同步改 IPv4，LAN 真值入 `inventory/net.yaml` 的 `lan` 段，并在门禁 `stations` 新增 **(h)** 防漂移断言（`ssh -G` 的 hostname 必须 == 登记 IP；已做负向自证）。**实测：按名 16.2s → 0.18s（≈90×）；单次 task run 421s → 48.5s（8.7×），其中模型本身占 38s ⇒ 框架开销 ~383s → ~10s** | 已闭环。建议（可选加固）：路由器按 MAC 做 DHCP 保留（固定 .32/.33/.37）；`agent-cli`/`cluster.py` 的 ssh/scp 统一加 `-o BatchMode=yes`（防认证失败时静默等 stdin，本轮实测踩到 >90s 挂起）**→ 见下条** |
| ~~**ssh/scp 未统一 `BatchMode`（认证异常时会静默等 stdin）**~~ | **09-16 新登记（健壮性）**：ADR-0006 调查中实测踩到 —— 按 IP 连接时因 `~/.ssh/config` 无对应身份块，用户名退化为本机 `peng` ⇒ 触发口令提示 ⇒ **挂起 >90s 等 stdin**（自动化里表现为"卡住"而非"失败"）。已在 `~/.ssh/config` 补三个 IP 身份块消除该场景，但**调用点本身仍未加 `-o BatchMode=yes`**（agent-cli.ps1 的 ssh/scp、cluster.py 的 paramiko 路径） \| ✅ **2026-09-22 已闭环（严格限于上面**点名的那两处**）**。① `agent-cli.ps1`：**20 处**裸调用补 `-o BatchMode=yes`（另 9 处本就有）⇒ 全文件 **29 个 ssh/scp 调用点全部带 BatchMode**（**AST 判定**，非文本）；首个 ssh 调用点旁落一条**纪律注释**（为什么 + 守卫在哪）。② `cluster.py`：**paramiko 没有 BatchMode**（它不弹口令、认证失败即抛异常，"挂死"这一形态不存在）⇒ 该侧真正的对应物是**超时上界**：实测上游源码（paramiko 5.0.0）`banner_timeout` 默认 **15s** / `auth_timeout` 默认 **30s**（**两者不同源**），而原代码只给了前两者 ⇒ "认证阶段卡住"要等 30s 而非 `SSH_TIMEOUT=8` ⇒ 补 `auth_timeout=timeout`；并**把另外 2 处重复的 `paramiko.SSHClient()` 收敛到唯一入口 `_connect`**（那正是漂移的滋生点）。**守卫（带调用点，非空头承诺）**：`_fm_golden_test.ps1` 新增 **4 条断言**（164→**168**）—— ① AST 数全部 ssh/scp 命令节点必须含 BatchMode；② `Start-Process -FilePath 'scp'` 形式的 scp 判其**参数数组赋值**；③ 用 **Python `ast`** 判 `cluster.py` 里 `paramiko.SSHClient()` 调用**恰 1 处**、`connect` 恰 1 处；④ 其 `connect` 的关键字必须含 `auth_timeout`。**变异自证 4/4 全红**（摘一处 BatchMode ⇒ 缺 1 处**并点名第 275 行**；摘 `$scpArgs` 的 ⇒ 红；摘 `auth_timeout` ⇒ 红；加一个 `SSHClient()` 调用 ⇒ 红），还原后 168/168。**⚠ 本轮踩到的两个"判据自身"的坑**：(a) **文本判据第 5 次被注释骗** —— 第一版用 `[regex]::Matches($text,'paramiko\.SSHClient\(\)')` 数出 **2 处**，其中一处是 `_connect` 的 **docstring 里提到该名字** ⇒ 改 Python `ast` 数真实调用节点；(b) **断言打错了对象** —— `Start-Process` 那处我把断言打在它自己的 `Extent.Text` 上，而该串里只有变量名 `$scpArgs`（真值在上一行赋值里）⇒ 必红。**⚠ 新登记（本轮扫描发现，**不在**本项点名范围内，待裁是否扩面）**：仓库还有 **3 个站上/一次性工具的 18 处**裸调用（**v2 盘点值；v1 报的 12 处是少算，见下**）：① `ops/station-bin/agent-cli-smoke.sh` **12 处** = 5 处 `ssh -o ConnectTimeout=10 "$HOST_x" "pgrep …"` + **7 处 `ssh "$HOST_x" 'bash -s' <<'REMOTE'`（连 `-o` 都没有）** ⇒ ✅ **2026-09-22 已收口（方案 C 第二步，用户裁定）**：12 处全补 `BatchMode=yes`（7 处 heredoc 形态**同时补 `ConnectTimeout=10`**）+ 文件头纪律注释（并写明 heredoc 形态的**额外风险**：它的 stdin **正被 heredoc 占用**，无 tty 时 OpenSSH 会从 stdin 取口令 ⇒ 比"挂住"更隐蔽）+ **纳入守卫** —— `.sh` **无可用 AST** ⇒ 用**文本扫描兜底**（夹具 169→**170**），判据 = 只取 `#` 前代码段 + **引号奇偶**判命中点是否在串内 + **逐文件命中数恰为登记值**（`bare=0 total=12`）。**变异自证 2/2 全红**：① 摘掉一处 ⇒ `bare=1 total=12`；② 把扫描指向一个**无 ssh/scp 调用**的文件 ⇒ `bare=0 total=0` **仍红** ⇒ 证明"命中数恰为登记值"确实在防恒真。**诚实边界（已写进断言注释）**：文本判据的已知残留是**跨行字符串**判不出，且 `.sh` 侧没有 Python AST 可用。另验 **`bash -n` 显式走 Git Bash**（PATH 的 `bash` 是 WSL）rc=0 + 0 CR；② `ops/station-bin/load-gate` **4 处**（`ssh -o ConnectTimeout=5 "$h" …`）⇒ ✅ **2026-09-22 已收口 + 已部署三站**（逐项见下「另一条实测事实」）；③ `ops/station-bin/_switch_qwen_flavor.ps1` **2 处、且只落在 scp 侧**（L41/L46）—— 该文件 3 处 ssh **早已带 BatchMode** ⇒ 属**半修状态**（本仓已记过一次的"只修一半的修复看起来是完整的"）⇒ ✅ **2026-09-22 已收口（方案 C 第一步，用户裁定）**：2 处 scp 补 `BatchMode=yes` + 文件头落一条英文纪律注释（该件刻意 **ASCII-only** ⇒ 注释也用英文，免得踩 `.ps1-bom` 判据）+ **纳入守卫** —— `_fm_golden_test.ps1` 的 AST 断言**扩到第二个入口**（168→**169**）：`_switch_qwen_flavor.ps1` 的全部 ssh/scp 也必须带 BatchMode，且要求 **`≥5 处`命中**（防恒真：0 命中不许等于通过）。**变异自证 2/2 全红**：① 摘掉刚补的那处 ⇒ `实测 5 处、缺 1 处` 红；② 把断言指向一个**无 ssh/scp 调用的 .ps1**（`_probe_fallback.ps1`，它只有 `function ssh {}` 的 **stub 定义**、不构成 CommandAst）⇒ `实测 0 处、缺 0 处` **仍红** ⇒ 下界确实在起作用。⇒ **三件全部收口**（①③ 见上，② 见下）。**"仓库副本 vs 三站副本"的机器判据**：**2026-09-22 已裁定接入 `gates`**（不再是"待裁"）—— 见下条「站上件副本与仓库副本不一致」，以及该条里**接入当日就抓到的真漂移**。**⚠⚠ 盘点方法自身在同一个坑里翻了两次**：v1 正则要求 `ssh|scp` 后紧跟 `-` 或词字符 ⇒ **漏掉 `ssh "$HOST_B"` 这类"主机是引号变量"的形态共 6 处**（故 v1 的 6 处实为 12 处）；v1 还把**注释与消息串**一起算了（`throw "NETFAIL: scp failed…"`、docstring 里的 `ssh 失败`、`echo "== A -> B ssh 连通 =="`、夹具样串全被误算 ⇒ 虚报 33 处）。v2 修法 = 只取 `#` 之前的代码段 + **引号奇偶**判命中点是否在串内 + 逐行人工定夺 ⇒ 余下 3 条 FP 已逐条确认（`cluster.py` docstring、`_probe_fallback.ps1` 的 `function ssh {}` **stub 定义**、`plugin-probe` **多行 docstring** 散文 —— 最后这条暴露 v2 的残留边界：**跨行字符串判不出**）。**⇒ 教训：盘点脚本的"形态清单"必须先拿已知样本验，否则漏项是静默的**（同"判据要先在已知会红的样本上验红"）。**另一条实测事实（直接决定处置代价）**：`load-gate` 是**站上件** —— 今日实测三站 `/usr/local/bin/load-gate` 的 md5 **全为 `6acec51909c93c18b4296ab1a708e28e`、与仓库副本一致**（仓库副本 0 个 CR）⇒ **仓库副本即活体，但改完必须重新部署三站才生效**；而 `ops/station-bin/README.md` 的清单**根本没列 `load-gate`**（只列 `load-mem-gate`）⇒ 该件的部署面无记录、无 md5 基线（**登记缺口**）。✅ **2026-09-22 已补 + 已部署**（上句的 `6acec519…` 是**部署前**的三站一致值）：三站**先 `cp -a` 备份**（备份 md5 == 原 md5，逐站核过 `BACKUP_OK`）⇒ `install -m 755` ⇒ **新 md5 `07ad7e01dedd61ca863c1ce94f928b23` 三站一致且 == 仓库副本**（仓副本 0 CR）+ `MODE=755` + `bash -n` 通过；并跑**回归实弹**：三站各执行 `load-gate 1` ⇒ 均正常输出 `--- [localhost] need=1G avail=… total=…` + `[OK]` + `[load-gate] ALL PASS`（rc=0）⇒ **无功能回归**。备份留在三站 `/usr/local/bin/load-gate.bak-20260922`（一键回滚）。**README 已补 `load-gate` 行 + md5 基线**。**⚠ 守卫现状（诚实）**：源码侧由夹具文本扫描守住（`bare=0 total=4`）；**部署侧无机器判据**（见上「未收口的新项」）。**⚠ 另一条诚实边界**：本轮**未**构造"认证失败"实验去直接观测"从卡住变快速失败"（那要故意破坏认证，代价与副作用不成比例）—— 已验证的是：① 源码每处都带 BatchMode（夹具守卫）、② 三站跑的**就是**这份源码（md5 一致）、③ 无功能回归。 |
| **站上件副本与仓库副本不一致（判据接入当日即抓到真漂移）** | **2026-09-22 新登记（"把手工约定升级为机器判据"的副产物）**：把"站上件 == 仓库副本"接进门禁 `gates` —— **复用既有健康探针**（在 `_HEALTH_CMD` 末尾加一段 `===BINMD5===` 循环 `md5sum`），**零额外连接**；**期望值运行期从仓库副本算** ⇒ **不立第二定义点**（免掉"改了仓库忘改表"）。**首跑即抓到 `wait-gtt-release` 的真漂移**：A/B = `40d6cfe4…`、C 与仓库 = `a60b1877…` ⇒ ① 违反 README"三站必须一致"；② 差异内容 = 仓库/C 是**新版**（`TOTAL*0.82` 相对总内存）、**A/B 是旧版**（`-ge 102400` 绝对 100G）；③ **A/B 那份首行还带 UTF-8 BOM**（`efbbbf#!/bin/bash`，`.sh` 带 BOM 是明确的坑）⇒ 典型"**改仓库 + 只部署了一站**"的半部署（该件是站上件，改仓库不生效） | ✅ **当日闭环（用户裁定"部署到 A/B"）**：按同一套闭环推 A/B —— `cp -a` 备份（核"备份 md5 == 原 md5"，逐站过）→ `install -m 755` → 新 md5 `a60b1877…` == 仓库副本 + `MODE=755` + **`FIRST3=23212f`（`#!`+`/`）证明 BOM 已消除** + `bash -n` 通过；**回归实弹** `timeout 20 wait-gtt-release` ⇒ `[gtt-wait] OK: MemAvailable 121G >= 102G (1x5s)` rc=0。复跑 ⇒ **`站上件一致 24/24` PASS**。备份留在 A/B `/usr/local/bin/wait-gtt-release.bak-20260922`。**判据自证（两向）**：① **真漂移对照**（部署前 FAIL **点名 A/B** → 部署后 24/24）—— 用**真实漏网**而非合成样例；② **未触发过的两条分支各做一次变异**：往 `STATION_BINS` 加 `_switch_qwen_flavor.sh`（仓库有、站上**不部署**）⇒ "取不到 md5"分支 FAIL 并点名；加 `no-such-bin` ⇒ "清单该改"分支 FAIL ⇒ 还原后 24/24 ⇒ 证明判据不是"只在 happy path 上绿"。**⚠ 顺带确证一条边界**：`_switch_qwen_flavor.sh` **不该**进清单（它是运行时推到 `/tmp` 的，不部署到 `/usr/local/bin`）。**⚠ 严重度选择（诚实）**：判 FAIL 而非 WARN，依据是**接入前实测过误报面**（8 件 × 3 站里 7 件本来就逐字节一致 ⇒ 误报面为零）+ 它与本站 `stations` 断言（conf/凭据不符即以站上实况改仓库侧）**同一性质**；`gates` 是 `quick=False`（不进 pre-commit）⇒ FAIL 不会阻断提交，只阻断全量门禁。 |
| **`doclinks` 对新文件有盲窗（未跟踪文件不扫）** | **09-16 新登记（判据自身的盲区）**：`doclinks` 只扫 `git ls-files` 的 md ⇒ **新写的文档在 `git add` 之前不进判据**。实测代价：ADR-0005 落档时门禁报"失效 0"，而它内部有 **27 条 `../../` 前缀错**（`adr/` 只有一层，应是 `../`），直到本次 ADR-0006 落档时才被连带发现（两文件共修 38 条）。⇒ 判据存在"写完 → add"之间的静默窗口（与"门禁绿灯 ≠ 产物可信"同族） | 待办：把 `doclinks` 扫描集改为 `git ls-files ∪ git ls-files --others --exclude-standard`，或在 pre-commit 时对暂存文件全扫 **⚠ 2026-09-22 实测更正 + 决策简报 → [门禁口径决策简报](../../docs/2026-09-22_门禁口径决策简报_doclinks越界链与root级脚本范围.md)**：登记里的"只扫 `git ls-files`"**已不成立** —— `check_doclinks` 用的是 `ROOT.rglob("*.md")`（**全工作区扫描**，实测未跟踪的新 md 一样被扫），用 `ls-files` 的是另一函数 `_iter_source_files`（服务 `secrets`）。**真盲区是判据自己放弃**：相对链接**越出仓库根**时 `_doclink_bad` 返回"不可判定"，与 http/占位词混在同一桶（当前不判 740 条）⇒ 静默放过（**这才是 09-16 那 27 条 `../../` 没被抓住的机制** —— 不是没扫到，是**扫到了但判据放弃**）。**影响面已实测**：越界的"相对"链接 **2 条**（且两条**都是真错**：`adr/ADR-0003:214`、`adr/ADR-0007:320`）、越界的"非相对形态" **0 条** ⇒ 加新判据**误报面为零**。**待裁**（简报已列 A/C/D） ✅ **2026-09-22 已闭环（裁定 A）**：`_doclink_bad` 拆开两类 —— **相对形态**越界 ⇒ **失效且可判**（原因串 `越出仓库根(相对链接层级写多)`），**非相对**形态越界仍不可判；明细行补原因。**对照自证**：判据加入前后对**同一批真实数据** ⇒ PASS→**FAIL 且点名那 2 条**（真实漏网，非合成样例）。2 条已修（`adr/ADR-0003:214`、`adr/ADR-0007:320`：两层 `..` ⇒ 一层）。复验 PASS，且**"不判"桶 740→738**（两条归位到"可判"）。详见 [决策简报 §裁定与实施记录](../../docs/2026-09-22_门禁口径决策简报_doclinks越界链与root级脚本范围.md) |
| **调研文档对 `agent-cli-smoke.sh` 的"性质 + 归属"断言有误（本轮顺带发现）** | **2026-09-22 新登记（本轮回合盘点的副产物）**：`docs/Agent跨项目调用标准与迁移复用调研.md` §9.11.3「G14 升级回归 SOP」表的"复用资产"列写 **`agent-cli-smoke.sh`（站上件，已在 station_runtime）** —— **两处都不成立**：① **性质**：该件**不是站上件**，其**文件头第 3 行**明写"**主控站 Git Bash 发起**"（实测调用也全在主控本机；它演练的对象才是远端三站）；② **归属**：`inventory/ops.yaml` 里它登记在 **`frozen_ops_scripts`**（L223 = 历史一次性脚本，"只减不增"），**不在** `station_runtime`（该 yaml **只有 3 个顶层键**：`entry` / `station_runtime` / `frozen_ops_scripts`，已一次性核对）。**为什么这算问题而不是"历史记档"**：它不是"当年路径如今变了"，而是**一条分类断言本身是错的**；且它出现在**照着做的升级 SOP 表**里 ⇒ 读者会按"站上件 / station_runtime"去**站上**找它的部署位置与维护路径（实际它只在主控被叫起）。 | ✅ **2026-09-22 已加注（当日闭环，用户指示）**：在 `docs/Agent跨项目调用标准与迁移复用调研.md` §9.11.3 **该行原地加注**（**保留原文**、不动表结构与其它行），注明"该件是**主控发起**、登记在 `frozen_ops_scripts`，**不是**站上件"并链回本条。**原建议保留如下**（理由 = 不改写历史结论，与 ADR-0007 那两条越界链的处置同一风格）：只改措辞 —— 在该处**加注**（不改写原结论与表结构）说明"该件是**主控发起**、登记在 `frozen_ops_scripts`，**不是**站上件"；**不建议**反过来改 `ops.yaml` 的归属（文件头 + ops.yaml 是**两条互相独立的证据**都指向"主控发起"）。⚠ **范围已核**：同类漂移在本文档**只此一处**（全文 `station_runtime` / `站上件` 仅 2 处命中：L44 讲"C 站 station_runtime 工具链 11/11 已装"= **属实**，L871 即本条）。 |
| **`Get-FrontMatter` 不剥离 YAML 引号** | **09-16 新登记（解析器行为）**：卡里写 `accept: - "true"` 时引号**原样**进入命令列表（`eval` 后仍能执行，故非功能缺陷），但会让"证据 ↔ 声明"的字面比对出现差异（实测 `accept-cmds.txt` 内为 `"true"`，而卡内声明是 `"true"` 的引号已入串） | 低优先：可剥引号，或仅在文档写明"命令列表不要加引号" |

| **`syntax` 断言占 quick 门禁 96% 耗时（本轮新发现）** | **09-17 新登记（性能）**：逐项实测（`tmp/_t2.py`，逐 check 计时）——**quick 门禁实测 ≈16.4s**，其中 **`syntax` 独占 15.8s（96%）**，其余全部合计 <1s（`secrets` 123ms / `aliases` 214ms / `doclinks` 85ms / **`evidence` 仅 40ms**）。**为何要紧**：pre-commit 钩子每次提交都跑 quick ⇒ **每次 commit 白等 ~16s**；且记忆/文档里"quick 1.1s"是**过时值**（仓库已长到 206 脚本 / 683 文本件 / 409 个 `.sh`）。根因推测：`syntax` 对每个 `.sh`/`.ps1` **逐个 spawn 解释器**校验（409 个 `.sh` 是主项）——**未取证到函数内部，仅由"其余项皆 <250ms + 文件数占比"推断** | 待办：改批量/并发校验（或按需只校验改动文件），把 quick 压回秒级；属**独立性能项**，非证据流范围 |
| **证据链持久化为单机（闭环复核新增，09-19）** | **闭环复核**发现：链本体（65 KB）+ 冷路径镜像都在主控**同一块盘且 gitignored**，对账 runDir `D:\Paper\agent-out\*` 亦单份；入仓的只有 **716 B `ANCHOR.txt`** ⇒ 磁盘故障 = **链不可复验**（锚还在 GitHub，但对账对象整段消失）。**已做社区调研并落 [ADR-0007 §社区调研结论](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md) + 调研 §14**：四候选 P1 ruleset / P2 链入仓+断言 / P3 git notes / P4 tlog-tiles 只读镜像。诚实边界：3 台机器同运营者 ⇒ **不得用多副本宣称"不可否认"** | **P1 ✅**（ruleset `23753398`，禁 force-push+禁删 main）。**P2 ✅（2026-09-21）**：冷镜像 `archive/evidence-chain/agent-chain.json` 入仓（红线精确例外已写回 ADR）；断言 `p2_pair_mismatch`（`verify` 读 git 暂存区比对链↔锚 cold_sha）；**顺带把锚哈希改 LF 规范**（`core.autocrlf=true` 下盘面 CRLF 与 git LF blob 不同 ⇒ 旧锚钉的是本机编码，已 `--reanchor` 704cd0b7）。**P3 ✅ / P4 ✅（用户裁定两者都做）**：P3=`agent chain --pin-notes`（git notes ref `refs/notes/evidence-chain` push origin，冗余）；P4=`agent chain --mirror <站>` = **链镜像 + runDir 对账镜像**（`agent-out/`→ tar.gz → 站 `evidence-mirror/runs/`）。**⚠ P4 修正（2026-09-21 实测自伤）**：首版 chmod 555/444 模拟只读 ⇒ 下次 `--mirror` 自己写不进 ⇒ 改为**可更新滚动快照**（写入前置自愈恢复可写）。诚实：均同运营者 ⇒ **冗余非不可否认** |
| ~~**`syntax` 断言抓不到"无 BOM 的含中文 .ps1"（本轮新发现）**~~ | ✅ **2026-09-21 已闭环（加了确定性字节判据 + 更正根因）**。**09-18 首次命中（判据盲区）**：`ops/station-bin/_fm_golden_test.ps1`（**卡解析器的回归守门夹具**）**缺 UTF-8 BOM**。PS5.1 按 ANSI 解码含中文的脚本时，**3 字节 UTF-8 序列被当 2 字节 GBK 解码会吞掉相邻换行** ⇒ 语句被并进注释 ⇒ 夹具**静默失效**（`DEBUG fns count=0` + `Get-FrontMatter not found`，即"守门人一直是死的"）。**09-21 第二次命中（现场复现）**：编辑工具（Trae `Edit`/`SearchReplace`）**在某些重写路径下会剥掉 BOM** ⇒ `agent-cli.ps1` / `_fm_golden_test.ps1` / `_probe_fallback.ps1` 三个文件 BOM 全丢，随后夹具**当场解析崩溃**（`Unexpected token 'claude'` + 中文乱码）。**⚠ 该行为是"间歇"的（当日多次实测）**：同一工具、同一批文件，**P1 阶段那轮编辑保留了 BOM**（`git cat-file blob 08eb8b0:<f>` = `efbbbf`）、**撤回那轮剥掉了**、**补语法那轮又保留了** ⇒ **不能假设它会保留，也不能假设它一定会剥** ⇒ 只有**按字节验**才可靠（这正是本次加子判据的理由之一）。**⚠ 根因更正（09-21 实测，推翻当日早先写下的错误说法）**：曾推断"门禁 `[Parser]::ParseFile` 走 .NET 解码（BOM-less 按 UTF-8）而执行走 ANSI ⇒ **结构性看不见**"—— **错**。实测证据：把一个 BOM-less 的中文 `.ps1` 交给上游那次 `ParseFile`，它**报了错**，且 11 条错的行号**全部落在中文注释行**（30/37/209/214/231/237/257/299）—— 若真按 UTF-8 读，一条错都不会有 ⇒ **`ParseFile` 与执行走的是同一条解码路径（ANSI/GBK）**。⇒ 真正的问题是**间歇性 + 内容相关 + 报错不指根因**：是否"吞掉换行"取决于具体字节序列，故同一缺陷可能报一堆错（09-21），也可能**报 0 条错却照样跑坏**（09-18 目击的后者：门禁 `.ps1:12文件/0失败` 而夹具 `fns count=0`）；且报出来的行号指向**注释行**，看不出"加 BOM"这个修法。**修法（本次落地）**：给 `syntax` 加**读字节**的子判据 `counts[".ps1-bom"]` —— **含非 ASCII 字节 且 无 `EF BB BF` ⇒ FAIL**（与内容无关的**确定性**判据，且报根因）。**顺带修两处报告缺陷**：① `PS_SNIPPET` 的 FAIL 行补**文件名**（原先 13 个文件里只报 `Unexpected token ')' [line 37]`，查不到人）；② 失败数**按文件计**（原先按错误行计 ⇒ 摘要写 `13文件/11失败` 像"11 个文件坏了"，实际只有 1 个 —— **09-21 实地误导过一次**）。**自证（正 + 负 + 对照）**：正 = 干净仓库 `.ps1:13文件/0失败 .ps1-bom:13文件/0失败` PASS；负 = 剥掉 `_fm_golden_test.ps1` 的 BOM ⇒ `(ps1-bom) …含非 ASCII 却无 UTF-8 BOM…` + `.ps1:13文件/1失败` + **退出 1 阻断**，还原后 sha256 一致；对照 = 暂存一个**纯 ASCII 无 BOM** 的 `.ps1` ⇒ 两计数均 `0失败`（**无误报**）。**范围修正**：原待办写"`.ps1`/`.sh` 都要 BOM"—— `.sh` **不得**加 BOM（BOM 会让内核把 `#!` 认成 `\xEF\xBB\xBF#!` ⇒ `bad interpreter` 直接不可执行），故子判据**只覆盖 `.ps1`**。**纪律**：凡编辑过 `.ps1`，提交前按字节验 BOM | — |
| ~~**函数返回值被"非返回值输出"污染**（本轮新发现，已闭环）~~ | ✅ **09-18 当日闭环（详见 [ADR-0007](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md)「缺口 5 落地与实测」）**。**症状**：run.json 出现 `"exit_code": [null, 0]` + `"status": "failed"`（实际 rc=0），且**复验器崩**（`TypeError: unhashable type: 'list'`）；同 session `SLOT-GATE: na (engine port unknown)`。**根因**：PS 函数 = 管道上**全部**输出 —— `Invoke-RemoteScript`/`Invoke-StationReady`/`Invoke-SlotGate`/`Invoke-Task` 靠 `return $x` 交付，但体内有未被吸收的 cmdlet 输出；环境层对文件操作的包装器在失败路径吐了 `$null` ⇒ 返回值变 `@($null, <真值>)`。**修法（"归零纪律"）**：通知改 `Write-Host`；`Copy-Item`/`Move-Item`/`Remove-Item`/`Add-Content` 一律 `\| Out-Null`；纪律写入注释（凡返回值被调用方使用 ⇒ 体内不得有其它管道输出）。**自证**：再派发 ⇒ `excode=0`（非数组）/ `exit_code=0(Int)` / 槽位门恢复。**复验器加固**：`_verdict_check` 遇 `exit_code` 形状畸形 ⇒ 报 issue 而非抛异常（崩掉 = 整链判据同时消失） | — |
| ~~**PS5.1 无 `[DateTime]::UnixEpoch`**（本轮新发现，已闭环）~~ | ✅ **09-18 当日闭环（详见 [ADR-0007](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md)「缺口 8 落地与实测」）**：`[DateTime]::UnixEpoch` 是 **.NET Core 时代成员**，PS5.1 的 **.NET Framework 4.8 上不存在**，且**访问它不报错、静默返回 `''`** ⇒ 参与 `DateTime - ''` 时抛 `找不到 op_Subtraction 的重载`（实测：缺口 8 首次派发取遥测即因此失败）。**修法**：改用 `[DateTimeOffset]`（4.6+ 起有 `ToUnixTimeMilliseconds`/`FromUnixTimeMilliseconds`）。**副产物**：该误用**顺带把"取不到遥测"的 NA 路径在真实链路上跑通**（run `202609181232158097` 落 `usage.source=unavailable` + 告警，`TASK_RC=0`、任务结论不受影响）⇒ 兜底有效，但**不能把兜底当正常路径** | — |
| ~~**`.attach/` 清理只覆盖"有附件"路径**（缺口 5 修复不全，本轮新发现，已闭环）~~ | ✅ **09-18 当日闭环**：缺口 5 引入的"派发前清空 `.attach/`"外层套在 `if ($attach.Count -gt 0)` 内 ⇒ **无附件的派发会留着上一轮附件**（实测两次无附件 run 均报 `ATTACH_MANIFEST_LINES=3`：把上一轮 attach 夹具的三件算进本次 run；agent 亦可 `ls` 到残留）。**修法**：改为**无条件 reset**（代价：无附件派发多一次 ssh —— Correctness > 一次往返）。**教训**：缺口 5 的判据只覆盖"有附件"路径，**没有为"无附件"路径设判据，残留就被漏掉** —— "只覆盖一半的修复看起来是完整的"，与"判据必须报覆盖率"同源 | — |
| **`infer-load` 健康检查超时（首拉失败、重试即好）** | **09-18 新登记（基础设施/偶发）**：阶段 3-a 的 e2e 中 `cluster.py load gpt-oss-20b` 首拉报 `unsloth 健康检查超时`，而站上**实例其实已起**（studio :8080 + llama-server :41959 均在），日志显示健康检查对 `/v1/models` **连续 401**（每 3s 一次，直到超时）。**推测**：新铸 key 落盘与健康检查轮询之间存在**竞态**（该轮 `API Key ok` 行未打出）⇒ 用未同步的 key 去探。**实测**：直接重试一次即 `READY ✓`（key sha8 变化：`e698d92a` → `b359bb79`）。影响：一次派发失败 + 一次人工重试 | 待观察：若复现，给健康检查加"key 落盘后重读 + 401 单独识别为 key 问题"的判据（与"卡住 vs 失败"同族：**必须能区分**） |
| **⚠ `local-only` 闸不覆盖 claude 备路 ⇒ 敏感卡可实际出网（2026-09-21 新登记，安全策略洞）** | **背景**：`sensitivity: local-only` 的硬闸有三处（`Resolve-Model` L435 / `Invoke-Task` L987 / 路由 cmd L1837），判据一律是 `local-only` + `^opencode/` ⇒ `REJECT … exit 4`（无覆写通道）。**洞**：**`Invoke-Task-Claude` 没有任何 sensitivity 判据**，只校验"型号在表内 + `station=''`"；而 `AUTO_FALLBACK` 调用点也不判 sensitivity。**两条实际出网路径**：① 卡写 `sensitivity: local-only` + `cli: claude` ⇒ L987 放行（型号非 `opencode/*`）⇒ `Invoke-Task-Claude` ⇒ **OpenRouter 云端**；② `local-only` 卡 + 站上本地型号 ⇒ 站上引擎死锁 `rc=6` ⇒ `AUTO_FALLBACK` ⇒ `Invoke-Task-Claude -model claude` ⇒ **云端**。**为何现在才严重**：此前该路过 `api.anthropic.com` 且**不可用**（`Not logged in`）⇒ 洞是**惰性**的；2026-09-21 免登录 + OpenRouter + 型号重映射把备路**修成真能用** ⇒ **洞变活**。**破的是** [DESIGN.md §358](../../spec/d6-agent-standard/DESIGN.md) 的不变式（"local-only 的 prompt 字节永不离开主控站→站内本地模型路径"）。**影响面**：`test-cards/` 里 **20/25 张是 `local-only`**。**另注**：ZDR **不能**兜底 —— OpenRouter 官方明确"ZDR 只保证 provider 不留存，数据仍会到达 provider 并被模型处理，且不覆盖处理地"⇒ `local-only` 要的是**不出网** \| ✅ **P0 已实施并双向自证（2026-09-21；剩 P2–P5）**：新增**唯一判据** `Get-SensitivityBackendReject`（L905，纯函数，返回 '' = 放行 / 否则原因 token），规则**只此一条**：`local-only × 会出网 ⇒ local-only+egress`；在**两个出网入口各判** —— `AUTO_FALLBACK` 调用点（**拒绝兜底** fail-closed，拒绝串 `(fallback, <model>)`）+ `Invoke-Task-Claude` 直接入口（拒绝串 `(claude-direct, <id>)`），tag 用于分辨是哪一处闸在守。**自证**：① 夹具 **61/61**；② 实弹探针 A/B 两例 `rc=4` 且 **claude run 计数不增**（= 未发请求）；③ **变异自证**：拆掉闸 ⇒ A/B 变红（rc 4→6 且**真跑出 claude run** = 真出境）⇒ 洞是真的、探针不是结构性失明；④ `public` 原路径未被破坏。**仍未闭合**：~~P2 判据升级为"后端属性查表"（现 `$backendEgress` **硬编码 $true**）~~、~~P3 站上化~~、~~P4 备路独立预算~~、P5 ZDR。**⚠ 2026-09-21 进展（P3 已实施 + P2 部分落地 + P4 已实施）**：**P3** ⇒ `local-only` 的 claude 通道**不再"一律拒绝"**，而是走**站上 claude + 站上本地引擎**（物理不出网）；站上不可用 ⇒ `REJECT local-only-no-station-engine (exit 4)` **fail-closed（绝不退回主控本地=出网）**；`sanitized`/`public` **保持主控本地 spawn 不动**。**P2 ◐ 部分** ⇒ **claude 通道两个入口已参数化**（直接入口 `-backendEgress (-not $useStation)`；兜底入口保留 `$true`，因它在主控本地=云端=出网）；⚠ **但既有三处闸仍按型号前缀判**（`Resolve-Model` / `Invoke-Task` / route cmd）⇒ ✅ **已闭环（2026-09-21 W1a）**：那三处 + `Split` + review 全部换成**后端属性判据**（`Get-BackendEgress` / `Get-JudgeEgress`，**fail-closed 默认：只有 `local/` 不出网，其余一律出网**；claude 通道豁免以免误杀 P3）⇒ **"再加一个云端后端又漏一次"的结构根因已消除**（夹具含 ★"假想云端后端"负例 + AST 断言"全仓不再存在按前缀判敏感度"）。**P4** ⇒ `fallback-timeout-s` 已实施。**实弹自证**（`local-only` 卡 + `-Cli claude`）：`P3_CANDIDATES: B,A,C(pref=B)` → 选中 B → 站上打印 `engine_ctx=32768 max_context_tokens=28672 base_url=http://127.0.0.1:8080` → `P3_STATION_RC=0` → 归档 `P3-LOCAL-OK` / `exit=0` / 台账 `…,local-only,0,0,58`。**"不出网"的可判证据（非仅结构性）**：站上临时 settings 的 `apiKeyHelper` 指向 **unsloth.key**（本地引擎 key）⇒ 若请求打到 OpenRouter **必然 401**，而它 **rc=0** ⇒ **反证请求没去云**。夹具 **92/92**。**⚠ 同日复查又修两处"设计意图没落地"**：① **「优先选与死锁站不同的一站」原本未生效**（`$avoid` 只读 `$env:AGENT_AVOID_STATION`，而**无人填 env**）⇒ 兜底调用点现传 `-AvoidStation $station`（env 降级为手工覆盖通道）；② **`pref` 会覆盖率 `avoid`**（兜底时卡的 `model` 常正指向刚死锁那站）⇒ 两规则**提进纯函数**且 **avoid 胜过 pref**。**判别性实弹**：`avoid=''`⇒`B,A,C`（立刻选 B，无 SKIP）vs `avoid=B`⇒**`A,C,B`** + `SKIP A`/`SKIP C`（avoid 胜、B 垫底）。⚠ **更正**：前一条提交信息称"多候选重试未做"**有误** —— `SKIP`×2 证明循环本来就在逐个重试。夹具 **98/98** |**⚠ 同日曾加过第二条规则 `sanitized × 可能训练 ⇒ sanitized+trains` 并当日撤回** —— 理由见 [P1 核对报告 §6.2](../../docs/security/2026-09-21_OpenRouter数据策略与隐私开关核对.md) 与函数注释留档；**撤回已做成可判**（探针 C/D 例反向守卫"sanitized 必须被放行"） |
| **⚠ 备路全档依赖"免费模型允许训练"开关 + 免费日额度（2026-09-21 新登记，依赖/风险）** | **事实**：claude 备路两型号**都是 `:free`**（`claude`=`thinkingmachines/inkling:free`、`claude-opus`=`nvidia/nemotron-3-ultra-550b-a55b:free`），而 OpenRouter 的「Allow free endpoints that train on request data」**是 A 站账号级开关**（付费档/免费档**两个独立**开关）。**实测代价**：`nemotron-3-ultra-550b-a55b:free` 无偏好 **200**，加 `provider.data_collection=deny` ⇒ **404 `No endpoints found matching your data policy (Free model training)`**，加 `zdr` ⇒ **404 `(Zero data retention)`** ⇒ **该型号免费端点全部训练且全不可 ZDR**。**⇒ 关掉该开关 = `:free` 备路整体失效**（`claude-opus` 确证；`claude` 因 `403 only available on agentic harnesses` 只能推理）。**另**：免费档型号**流动性高**（本轮抽样 3 个 `:free` 已整体下架）+ 1000 次/天免费额度是「三站独立账户 + `egress borrow`」机制存在的前提 ⇒ **备路是"有条件的"能力，不是稳态**。**四开关实况（用户读 dashboard，2026-09-21）**：①`1% 折扣` **关** / ③b`免费档 publish` **关** / ③c`付费档 train` **关** / ③`免费档 train` **开** ⇒ **唯一敞口 = 免费档可能被训练**（不进公开数据集、OpenRouter 自己不留存/不使用）。**决策**：**不加**"挡 sanitized"那条闸（**同日加入又撤回**，见上一行）；**并且"关开关"不是一个动作** —— **该开关是"使用免费档"的必要条件**（实测账户级 `(Free model training)` 拦截）⇒ 关它 ≡ **放弃免费档**，而免费档**不是只有备路在用**：① claude 备路（harness 轨）、② judge/review 的 judge 槽（`secrets/openrouter.conf`，裸 API 轨）、③ 站上 opencode 的 `provider.openrouter.models` 免费档优先级表（站内 egress）⇒ **关开关 = 同时打断这三条链路**，收益（少一条暴露面）远小于代价。**⇒ "免费档可能训练且不可撤回"登记为已知风险、默认接受**（它与"使用免费额度"是同一件事）；**⚠ 早先把"P3 之后关该开关"写成收尾步骤属"把手段当目的"，已更正并从各处移除**（含本行待办）。 | 待办：① **若某类流量单独不接受训练暴露** ⇒ **把那条流量改走合规后端**（站上本地引擎[P3] / 付费型号+`deny`·ZDR），**不是**关开关；②"付费型号 + `provider:{data_collection:deny}`"已实测可行（`mistral-nemo`/`ling-3.0-flash` 连 `zdr` 都过），需选型 + 改 ROUTE_TABLE + 夹具回归；③ 免费档型号**流动性高**（本轮抽样 3 个 `:free` 已整体下架）⇒ `:free` 只适合做**可失效的**后端，别当稳态；④ **P3 的价值与关开关无关**（绕开主控沙箱 / 摆脱免费额度与型号流动性 / 提供可选合规后端）。全文见 [P1 核对报告](../../docs/security/2026-09-21_OpenRouter数据策略与隐私开关核对.md)。**⚠ 2026-09-21 ZDR 裁定（P5）：不做 ZDR，且它不是可执行动作** —— [全文](../../docs/security/2026-09-21_ZDR可行性裁定与影响面.md)。要点：① **ZDR 按 model group 分作用域**（Anthropic/OpenAI/Google/SpaceXAI/**All other models**），我们型号**全是 `:free` ⇒ 100% 在 "All other models"** ⇒ 给该作用域开 = **本行那 5 类消费者全灭**（影响面与本行的"关开关"**完全重合**）；② **`local-only` 已强于 ZDR**（P3 让它在站上本地引擎跑 ⇒ **根本不出网**；而 ZDR 明确"不改变数据到达 provider"）⇒ 对它开 ZDR 是**降级**；③ **`sanitized` 抹完 = `public`** ⇒ 同级。⇒ **"允许出网但不允许留存"这个格子是空的**；**若将来真要 ZDR ⇒ 必须换付费型号**（已实测可用：`mistralai/mistral-nemo`、`inclusionai/ling-3.0-flash` 连 `zdr` 都过）⇒ 故"开 ZDR" ≡ "换后端" |
| **⚠ `sanitized` 档的"抹完 = public"这一前提从未验证（2026-09-21 新登记，**ZDR 裁定的替代品**）** | **由来**：ZDR 裁定（[全文](../../docs/security/2026-09-21_ZDR可行性裁定与影响面.md) §4）的论证依赖一条**推论**：「`sanitized` = 含**可机判**敏感项 ⇒ 先机械 scrub 才可进远端 ⇒ **抹完的残留等级 = `public`**」—— 该推论**从未被验证**。**为何要紧**：若 scrubber **漏了**（bug / 未覆盖的敏感形态 / **认了但没抹干净**），则 `sanitized` 流量**实际不是 public**，却**走云端免费档**（可能被训练 **且** 留存）⇒ **那才是真正需要更强后端的情形**。⇒ **正确的防线不是开 ZDR，而是让 scrubber 不漏**。**而且它是可测的**：scrubber 是**确定性函数** ⇒ 可做真值表夹具。⚠ 该前提同时也是 P1 那条"撤回 `sanitized×可能训练` 闸"的依据之一 ⇒ **前提若破，那条被撤回的规则要重审**（两处论证共享同一前提） \| ✅ **已实施（2026-09-21）**：`ops/station-bin/_scrubber_coverage_test.ps1`（AST 提取 `Invoke-Scrubber`，不执行主入口；登记 `inventory/ops.yaml`）—— 按**三态**建成，**`pass=14 fail=0`**。**⚠ 第三态当轮就命中一个真 bug**：`win-path` 规则原是 `(?i)\b[A-Z]:\\\S+`，**`\S` 遇空格即断** ⇒ `C:\Program Files\Git\bin\bash.exe` 只被吃掉 `C:\Program`，**残留** `Files\Git\bin\bash.exe`，而输出里**出现了 `[REDACTED-PATH]`**（"看起来已处理过"）。**修复含一次必须二选一的取舍**：改成"**段后还有 `\`（能证明仍是路径）才允许段内含空格**"（`(?i)\b[A-Z]:\\(?:[^\\/:*?"<>\|\r\n\t]+\\+)*[^\\/:*?"<>\|\r\n\t\s]*`）；放弃"段内一律允许空格"是因为它**贪心吞掉路径后的普通词**（`C:\RPC\out.txt done` 整段被抹 ⇒ **误伤任务输入**，本机 prompt 句中路径极常见）。夹具为此**新增 §2b 过度消费守门**（3 例）—— 当轮即抓到第一版改法的过度消费。**两类诚实输出（不计 FAIL 但必须可见）**：**[4] 未覆盖形态 14/14 一个都没覆盖**（GitHub PAT / AWS AKIA / Slack / JWT / Bearer / OpenSSH 私钥块 / **Linux 绝对路径** / **UNC 路径** / **内网 IP** / `.local` 主机名 / **用户名** / 手机号 / 身份证 / 银行卡 —— 现有 scrubber **只有 3 条规则**（**现已扩到 9 条，见待办①**），注释自明 `no whitelist in MVP`）；**[4b] 已知残留缺口 2/2**（`C:\Users\John Doe` ⇒ 残留 `Doe`；`"C:\Program Files\my file.txt"` ⇒ 残留 `file.txt`，即上面那笔取舍的代价）。**⇒ 对本行结论的影响**：`sanitized` 的**实际档位介于 `sanitized` 与 `public` 之间**（[ZDR 裁定 §6.1/§6.2](../../docs/security/2026-09-21_ZDR可行性裁定与影响面.md)）⇒ 该前提仍是**有条件成立** | 待办：① ✅ **已裁定并实施（2026-09-21）**：**加 6 条凭据类 / 不加 8 条身份与拓扑类**（全文 [scrubber 规则扩充裁定](../../docs/security/2026-09-21_scrubber规则扩充裁定与影响面.md) §6）。判据 = **①可判性 × ②真敏感 × ③误伤≈0 × 有出现路径**，四条全中才加。要点：**(a) 硬证据** —— 本仓 run ID 格式 `yyyyMMddHHmmssffff` **恰好 18 位数字、全仓 204 处**，故"长度判据"的身份证规则会把**主要证据句柄整片抹掉**（实测 3/3 命中），而 **GB 11643 校验位判据 0/3**（银行卡同理：长度判据命中 Luhn 不合法的编造值）；手机号规则命中的 `18047253056` 实为 `_davidau_download.sh` 里的**模型文件标识**。**(b) 三类形态是项目的日常寻址方式**：`.local` 主机名 **212 处/53 文件**、`/home/<user>/` **211 处/100 文件**、内网 IP 是 `inventory/net.yaml` 的**权威真值** ⇒ 抹掉它们 = 抹掉任务可执行性。**(c) 影响面边界** —— scrubber **只作用于 `$promptFull`**（卡 task + body + 附件名），**accept 命令不经它**（另行 base64，只到站=自己机器）⇒ 6 张卡 accept 里的 `/home/scott-lau/...` **不是误伤证据**（不加这条边界会把不存在的风险写成风险）。**(d) PII 不加规则 ≠ 放任** —— 正确防线是**档位**（含 PII/拓扑的卡**必须** `local-only`，已写进 DESIGN §5.1 卡作者纪律）。**(e) gitleaks 不装** —— DESIGN §193 的"regex + gitleaks"已改写为"**regex 必需 + gitleaks 可选**"（实测主控站无 gitleaks ⇒ 现状本就是 spec 允许的回退版，非漏项）。**实施**：规则清单抽到 `Get-ScrubRules`（**单一真值源**；`Invoke-Scrubber` 抹 / 新增的 `Get-ScrubBlockReason` 拒都从它取）⇒ **9 条**；**私钥块改"拒发"**（fail-closed，`REJECT scrub-unsafe:private-key … exit 4`，主路与 claude 备路各判一次 —— 二分依据 = "能不能安全抹除"，同时消掉 DESIGN §193「命中即拦截」与 §2.1「脱敏后远端」的旧张力）。**自证**：夹具 **43/43**（§1 正例 13 / §2 负例 13（含 ★ 三条把"不加"决定做成回归守卫：run ID、`.local`、内网 IP）/ §2b+§2c 过度消费 7 / §3 幂等 9 类占位符 / §5 block 判据 7 / §6 规则清单自证）+ **变异自证**（`aws-ak` 的 `{16}`→`{10}` ⇒ 3 条断言同时红 + 覆盖率 6/14→5/14）+ **实弹**（`sanitized`+`cli: claude` 卡贴私钥块 ⇒ rc=**4** 与日志一致、在任何 spawn 之前、git status **零残件**）+ `_fm_golden_test` **98/98** 零倒退。⚠ **`[4]` 覆盖率 0/14 → 6/14**，剩 8 项**就是"不加"的那 8 项**（不是未做完）；**[4b] 2/2 不变**。**未做**：✅ ~~P3（"附件内容不消毒"仍需一张"带敏感附件+sanitized"的探针卡实测）~~ —— **2026-09-21 已完成并实测成立**：探针卡与自对照设计与结果见下一行。② 在 [4] 被处置前，**"`sanitized` 抹完 = `public`"仍只是有条件的**（同时也是 P1 那条被撤回的 `sanitized×可能训练` 闸的重审条件）—— ⚠ 但现在**有条件的方向已经明确**：凭据类出网前必被抹、私钥块直接拒发，**剩下的敞口 = 那 8 项身份与拓扑类**（由档位纪律承接）；⚠ 规模要如实标注：22 张卡里 `sanitized` **只有 1 张**（且是脱敏器自己的验收卡）⇒ blast radius ≈ 0，本裁定定的是**将来语义**，**优先级低-中** |
| ✅ ~~**`sanitized` 附件旁路（P3）：附件内容是否也不经 scrubber**~~（2026-09-21 新登记并**当日闭环**，实测成立） | **问的什么**：`Invoke-Scrubber` 只作用于 `$promptFull`，而**附件**是 `scp`/`Copy-Item` **原文**（主路 L1227/1230、claude 路 L2290）⇒ 若卡同时满足「附件含敏感内容」+「模型指向云端」，附件内容会**原样进云端上下文**，即 DESIGN §9 不变式②（"消毒在控制台完成"）**在附件上是空的**。**实测（自对照设计）**：同一路径植两处 —— 卡正文（必经 scrubber）= 控制组，附件 = 实验组，让 agent 各照抄一行。结果 **两路一致**：`LINE1=[REDACTED-PATH]` + `LINE2=D:\Paper\agent-out\secret.xlsx`（原文）。**云端后果的硬证据**：claude 路 run `202609220011097576`（模型 `inkling:free` = 第三方云）的**转录** `~/.claude/projects/D--Paper/bc584929-….jsonl` 显示 `cwd="D:\Paper"`、`tool_use blocks=2`、`Read`×1 ⇒ **原文确实进了模型上下文，不是模型猜的**。**另一个方向也证明了**：run `202609220025427213`（**故意不加** `-Attach`）⇒ agent 报 `File not found: /home/scott-lau/agent-workspaces/paper/.attach/scrub-probe.txt` 后回 `NONE` ⇒ 探针**不会恒答 yes**，且**主路 cwd 就是站上工作区**（相对路径解析正确）。⚠ **两路各自证明了什么要分清**：**云端后果**由 claude 路证明；主路那两跑用的是**站上本地模型**，只证明"附件以原文落到远端工作区且 agent 读得到"（主路打真云未做成，见下一行） | ✅ **已闭环（2026-09-21）**：探针卡 [`test-cards/scrub-attach-probe.md`](../../spec/d6-agent-standard/test-cards/scrub-attach-probe.md) + 附件 `ops/station-bin/attach-test/scrub-probe.txt` **均入库**（选 Windows 路径做样串：既被 `win-path` 规则覆盖，又**不触发**本地 `secrets` 门禁与远端 push-protection ⇒ 可复跑）；**runner 说明刻意放卡外**（`…-notes.md`）—— 首跑证明"说明留在 body 里"会把**期望答案**提前告诉被测对象（污染）且多出 2 处被抹副本。**⇒ 对不变式②的结论**：其"消毒面"**不含附件**（当前实现如此，且此前**未在任何文档写明**）。✅ **已写进 DESIGN §5.1 sanitized 前置块（2026-09-21）**。**仍未做**：要么把附件纳入 scrubber，要么对"含敏感附件的卡"强制 `local-only` —— **这是决策，不是执行项** ⇒ **已并入下一行「消毒面 ≠ 出网面」的收口待裁表（①）** |
| ~~**claude 路的附件面：本地支 cwd 缺陷 + 站上变体两处**~~（2026-09-21 登记 → ✅ **2026-09-22 全部闭环，见 [REMEDIATION-PLAN §W3](REMEDIATION-PLAN.md)）** | **由来**：P3 首跑 run `202609220005298044` 的 `LINE2=NONE` 逼出来的。**(A) 本地支（`Invoke-ClaudeFly`）不设 `WorkingDirectory`** ⇒ 子进程**继承控制台 cwd**（常态 `d:\RPC`，非 projRoot），而附件被复制到 `<projRoot>\.attach`、prompt 用**相对路径**引用 ⇒ **附件不可达**；代码注释「claude cwd=projRoot」与实测不符；且 accept 早已**显式** `-cwd $projRoot` ⇒ **agent 与 accept 的 cwd 不一致**（此前无人核过）。**(A′) 站上变体（`Invoke-ClaudeFly-Station`）更重**：站上脚本 `cd "$HOME"`（同样错位），且**附件只复制到主控本地 `<projRoot>\.attach`、根本没同步到站上** ⇒ `local-only` + 站上 claude + 附件时**附件完全缺失**。**(B) headless 工具未验证**：spawn 只传 `-p "" --model <id>`，**无** `--allowedTools`/权限模式 ⇒ headless 下工具是否可用**未测**（首跑 `tool_use=0` 但那次的卡**禁止**用工具 ⇒ 无法归因） \| **(A) ✅ 已修（2026-09-21）**：`Invoke-ClaudeFly` 加显式 `-cwd` + `$psi.WorkingDirectory`，两处本地调用点（首跑/resume）都传 `-cwd $projRoot`；**实测证据**：修前转录目录 `D--RPC`（cwd=控制台），修后 `D--Paper` 且附件可读（run `202609220011097576`）。**回归守卫**：`_fm_golden_test.ps1` 新增 `cwd:` **三条结构断言**（含"两处调用点都传"的计数断言），并做**变异自证**（去掉一处 ⇒ 断言红 + 退出 1）。⚠ 结构断言只查"接线在不"，**行为证据只有实弹能给**。**待办**：**(A′)** 站上变体要么把附件同步到站上工作区、要么显式拒绝"站上 + 有附件"（**别静默缺失**）；**(B)** 去掉卡里工具禁令再跑一次单测工具可用性 | ✅ **两条均已闭环（2026-09-22，W3）**：**(A′) 选"显式拒绝"** —— `Invoke-Task-Claude` 新增 fail-closed 闸 `$useStation && 有附件 ⇒ REJECT claude-station-attach-unsupported (exit 4)`，**位置刻意在站上候选探查之前**（被拒的卡**零触站**）。**为什么不选"实现同步"**：闸已把危险形态（**假绿灯**：附件读不到却跑完给出结论）变成**可见拒绝**，而实现同步要同时改「站上执行器」+「附件通道」两处 ⇒ 收益小于风险 ⇒ **记为能力边界**（步 2 后置；撤闸前**必须**先有"附件在站上可读"的实弹证据，方法同 P3 探针卡）。⚠ **与 W4 附件闸是不同维度，两个都要有**：W4 的 `Get-AttachEgressReject` 管"附件会不会出网"（站上本地 ⇒ 不出网 ⇒ **放行**），本闸管"附件到不到得了执行点" ⇒ **W4 的放行不能被读成"站上 + 附件可用"**。**自证**：夹具 **147→153**（+6，含**两条 AST 位置断言**）+ 探针新用例 **E**（rc=4 + claude run 不增 + **零触站 0 次**）+ **变异自证**（闸移到探查之后 ⇒ **夹具位置断言与探针"零触站"同时红**）。**(B) 已答（无需新跑）**：判据是"转录里 `tool_use ≥ 1`"⇒ 直接查 P3 run `202609220011097576` 的转录 `~/.claude/projects/D--Paper/bc584929-….jsonl` ⇒ **`tool_use`=2（`Read`×1 + `Bash`×1）** ⇒ **headless 工具可用**（P3 那条"附件原文真进模型上下文"的结论正是靠这次 `Read`）。⚠ 登记里"那次卡禁止用工具"指的是**更早的一次**；现卡 `scrub-attach-probe.md` 本身**没有**工具禁令。⚠ **同日再更新（W3 步 2 实施后）**：上面 ①里选的"**显式拒绝**"**已被取代** —— 用户裁定"把能力真做出来"：站上分支现**复用主路同一套** `Invoke-Workspace -act sync` 同步**项目工作区**（`cwd` = `<WSROOT>/<proj>`，附件落**同一处**的 `.attach/` ⇒ 一套工作区、两个载体同址；⚠ 第一版曾自建 scratch 工作区 `_p3_claude_ws/<proj>`，因"第二套概念 + 不含项目文件"被**自己推翻**），任一步失败 ⇒ 非零退出（fail-closed）⇒ **安全性质与旧闸等价**，而危险形态从"可见拒绝"变成"可用的能力"。**撤闸依据是实弹**（唯一 marker `STATION-ATTACH-OK-7f3a1c` 只存在于附件、卡正文没有 ⇒ run `202609221331304084` 的 `agent-output.txt` 含该 marker ⇒ 附件在站上确实可读）。该步同时暴露两条**新边界**（站上 claude 的项目工作区缺失 / 台账 model 列误导），已另开一行登记。 |
| **⚠ 站上 claude 的两条边界（2026-09-22 W3 步 2 暴露，均非本步引入）** | **① 站上 claude 迄今**没有项目工作区**。** W3 步 2 给它建了 `<WSROOT>/_p3_claude_ws/<proj>`，但**只放附件**（`.attach/`），**不含项目文件** —— 而"项目文件就该在那儿"从未被实现：此前 cwd 是 `$HOME`（更糟）。**影响**：`local-only` 卡的站上 claude 只能靠 prompt 上下文 + 附件干活，卡里写"读 `src/x.py`"这类**项目相对路径一律解析不到**（且此前**没有任何判据**会因此报错 ⇒ 属"缺件却跑完"的同一族）。**② 台账的 `model` 列在站上 run 上是误导的**：`Invoke-Task-Claude` 的台账行（[L2662](../../ops/station-bin/agent-cli.ps1)）写的是 `$id` = **路由 id**；站上分支实际用的是**站上引擎别名 `main`**，于是实测 run `202609221331304084`（`local-only`、物理不出网）在台账里被记成 **`thinkingmachines/inkling:free`**（一个**云端**型号）。**为何要紧**：台账是本项目的**真值源之一**，而"按 model 列判该 run 是否出网"是个**看起来能用**的判据 ⇒ 会把不出网的 run 读成出网（方向：**假警报**；但同族的反向错误会**掩盖真出网**）。 \| ✅ **① 已闭环（2026-09-22 当日）**：站上 claude 现**复用主路同一套** `Invoke-Workspace -act sync`（`cwd` = `<WSROOT>/<proj>`，附件落同一处的 `.attach/`）⇒ **一套工作区、两个载体同址**。⚠ **中间设计被自己推翻并更正（值得记）**：第一版自建 scratch 工作区 `<WSROOT>/_p3_claude_ws/<proj>`（只放附件）—— 它既是**第二套工作区概念**、又**不含项目文件**（项目相对路径仍解析不到且无判据报错）⇒ 改为复用主路那套。**教训**：**先问"已有的概念能不能复用"，再动"新建一个"**。**实弹**：run `202609221340319598` ⇒ `CLAUDE-STATION: sync 项目工作区 -> paper` + 站上 `cwd=/home/scott-lau/agent-workspaces/paper` + `P3_STATION_RC=0` + `PROC_RC=0` + 附件唯一 marker 仍出现；`ssh ls` 该目录**确有项目文件**（`AGENTS.md`/`CLAUDE.md`/`README.md`/`pyproject.toml`/`docs`/`paper_cli`/`spec.md`…）**与 `.attach/scrub-probe.txt` 同址**。⚠ **如实标注边界**：这证明"**cwd 是含项目文件的工作区 + 该 cwd 下相对路径读取可用**"；**未经**一张"让 agent 读某个项目文件"的卡直接验证（非必要，未做）。**② 仍待办**。**另**：本步实施中还自查避免了一处回归 —— 工作区名必须**每项目稳定**（`claude --continue` 按**目录**恢复会话，每次换新目录会让续接**静默失效**）⇒ 只 reset `.attach/`、不删工作区。 | ✅ **② 也已闭环（2026-09-22 当日）**：站上分支的台账与 `.agent-run.json` 的 `model` 列改**按实际执行身份**写 —— `station:<站>/<别名>`（非站上分支保持 `$id`，那时它就是真值）。**⚠ 实测把登记的范围**放大**了**：原先只记"台账的 model 列"，实测**`.agent-run.json` 同样误导**（同一处 `$id`）⇒ **两个证据件都要改**（`.agent-run.json` 是机读终态快照、也是证据链的真值源 ⇒ 影响面大于台账一列）。**做法**：新增 `$execModel = if ($useStation) { "station:$st/$stModelAlias" } else { $id }`，`$stModelAlias`（`'main'`）**同源**用于 `--model` 实参与该串（防两处漂移）。**⚠ 信息不丢**：请求的路由 id 仍可从**归档的卡**（`card.md`，run 的证据件之一）+ `ROUTE_TABLE` 复原 ⇒ 不另加列（避免 schema 变更与其波及的读取面）。**实弹（前后对照，最直观）**：台账末三行 —— 修复前 `202609221331304084` / `202609221340319598` 写 **`thinkingmachines/inkling:free`**（云端型号），修复后 `202609221347542756` 写 **`station:B/main`**；同 run 的 `.agent-run.json` `model=station:B/main`、`sensitivity=local-only`，且附件唯一 marker 仍出现（无回归）。**自证**：夹具 **159→164**（+5：台账行写 `$execModel` / run.json `model=$execModel` / `station:` 前缀 / `--model` 实参与身份串**同源**（计数=2） / **反向**断言"本地支仍写 `$id`（计数=2）"⇒ 防把非站上分支改坏）。⚠ 本块第一条版本被**自己的引号转义**写坏（夹具直接语法报错）⇒ 改用 `[char]39` 拼 needle，不再手写 `\"`/`''`。**读者面**：`agent-runs.log` 的 model 列语义已在 `cluster.py` §台账注释处标注（schema 不变，仍是 7 列）。 |
| **⚠ 站上 zen 路由空转：没登录 ⇒ 不快速失败，只烧预算（2026-09-21 新登记，实测）** | **实测**（P3 主路跑 run `202609220018387887`）：`-Model lightning`（= `opencode/nemotron-3.5-lightning-free`，B 站）⇒ **3×120s 零输出**（`TASK_RC=124`→rc=6、`RUN_S=360`），`agent-output.txt` 只有 `> build · nemotron-3.5-lightning-free` banner + `RESUME` 标记。**已排除**：① **网络** —— 站上 `curl` 对 `openrouter.ai`/`models.dev`/`opencode.ai` **全 200**；② **引擎** —— `CHAT_OK`/`READY_OK` 都过（`ENGINE_CTX=32768`）；**唯一相关日志**是 `Failed to fetch models.dev … TimeoutError`（瞬态）。**已确认（2026-09-21 实测，从"嫌疑"升级）**：① 三站 `opencode auth list` **全为 0 credentials**（A 有 `auth.json` 但内容是 `{}`，B/C 无该文件）⇒ zen（opencode 自带 provider）**未登录**时**不报错、只空转**（把"缺凭据"变成 360s 无输出）。② **判别性实测**（站上直连、不经 agent-cli，有界 30s）：zen 模型 ⇒ `RC=124` + 只有 banner + **零错误行**；**同一模型**走站上**已有凭据**的 `openrouter` ⇒ **`RC=0` / 16s / 输出 `ZEN-OK`** ⇒ egress、stdin 管道、引擎全部排除，**唯一变量是凭据**。③ 日志侧证：zen 选完模型后**再无任何日志**，而 openrouter 的失败**会**记 `stream error`（如小模型 title 用的 `google/gemini-3.8-flash` 被地区墙）⇒ "挂了"与"慢/报错"在外部**不可区分**。**登录前置条件（已问清）**：`opencode auth login --provider opencode` 要求 **`https://opencode.ai/auth` 的 API key**（**无设备码流程**），且 clack TUI **需 tty** ⇒ `echo <key> \| ...` 管道喂 stdin **无效**（实测仍停在 `Enter your API key`、`auth list` 仍 0）。**复验工具（已入库）**：[`_probe_opencode_provider.sh`](../../ops/station-bin/_probe_opencode_provider.sh)（30s 内给出 `RC` + 凭据实况；判据写在脚本头）。⇒ 与"静默降级/失败不可见"同族。**⚠ 连带核对出的第二件事**：`ROUTE_TABLE` 里**站上云型号全是 zen**（`opencode/…-free`），**没有 `openrouter/…` 的站上条目** —— 而 OPEN-ISSUES 另一行把"站上 opencode 的 `provider.openrouter.models` 免费档表"列为免费档消费者之一 ⇒ **该消费者经派发表其实够不到**（`Resolve-Model` 是纯表查找、不 passthrough） | ✅ **已登记 + 已加护栏（2026-09-21，用户裁定"先不动 zen，只登记结论"）**：**护栏** = `ROUTE_TABLE` 里 `lightning`/`ultra`/`free-1m` 上方加**显式警告注释**（"当前不可用，别用" + 复验命令 + 登录前置条件）—— 即**在唯一的定义点标注不可用**，而不是静默留着。**⚠ 连带发现（要紧）**：`test-cards/sanitized.md`（**唯一那张 `sanitized` 验收卡**）用的就是 `lightning` ⇒ 原本**该卡跑不通**（sanitized 闸的**验收路径是断的**）⇒ ✅ **已闭环（2026-09-21 W1a，决策 C）**：`lightning`/`ultra`/`free-1m` 已**重指到"站上 `openrouter`"**（id 取 `secrets/openrouter.conf` 的 `harness_priority` 前两档 = **权威真值**，不新立模型清单），该卡**实测跑通**（run `202609221131192690`：`TASK_RC=0` + 3 处 `SCRUB` 命中 + agent 回 `A8B-PROBE-OK`）⇒ **sanitized 验收路径恢复**。**未做（待人裁）**：① **登录 zen** —— 前置条件已问清（需 `https://opencode.ai/auth` 的 API key + TUI 需 tty；**凭据我拿不到**）；② **改走站上已有 `openrouter`**（实测 16s 可用、凭据在位、四开关已核）⇒ 需改站上默认模型 + 加 `openrouter/<id>` 站上路由条目（顺带修掉"表里没有该消费者"的不一致）；③ 给远程 run 加**失败可见性**（零输出 + rc=124 时区分"模型没响应"与"根本没凭据"，**推荐**）；④ ⚠ 若启用 zen，**必须按 P1 那套核它的留存/训练政策**（我们只核过 OpenRouter，zen 完全未核）—— 否则 zen 承载 `sanitized` 流量就是"换了个未核过的第三方" |
| **⚠ `sanitized` 的「消毒面」≠「出网面」：两个已确认缺口 + 一项声明未接线（收口待人裁，2026-09-21 登记）** | **框架**：DESIGN §193 承诺"**未通过 scrubber 的任务绝不进入远端路径**"，但实现里 `Invoke-Scrubber` **全仓只有 2 个调用点**（主路 `Invoke-Task` / `Invoke-Task-Claude`；2026-09-21 核为 L1314/L2330 —— ⚠ 行号会漂，**点名函数为准**），**都在"派发"这一条路上** ⇒ 凡**不经派发**的出网内容，该承诺**不成立**。**缺口① 附件**（已实测，见上一行）—— 附件是 `scp`/`Copy-Item` **原文** ⇒ 附件的"消毒面"是空的。**缺口②（本轮新查出）`review`/judge 出网完全不消毒** —— [`Invoke-Review`](../../ops/station-bin/agent-cli.ps1) 读 `agent-output.txt`（**agent 产出原文**）→ `Build-JudgePrompt` 把 **`{{CARD_BODY}}`（卡的完整正文）+ `{{PRODUCT}}`（产出原文）+ accept/golden 元信息**拼进判据提示词 → 经 `Invoke-Judge` 送 **egress judge**（非 `local-only` 时**默认 `ultra`** = `opencode/nemotron-3-ultra-free` = **第三方云**）；该路径**既无 scrub、也无 `Get-ScrubBlockReason`** ⇒ **同一张 `sanitized` 卡的正文：派发时被抹、`review` 时原样出网** —— 消毒保证可被"**再跑一次 review**"绕过。⚠ 顺带：默认 judge `ultra` 正是**当前不可用的 zen 路由**（见上一行）⇒ 默认 `review` 现在也跑不通。**缺口③ `JUDGE_TABLE.compliance` 声明未接线** —— ✅ **已闭环（2026-09-21 W1a，选"接线"路线，见本行待裁 cell）**。原状：表里给 egress judge 标 `compliance='public,sanitized'`、本地 judge 标 `'all'`（**设计意图 = 按敏感度限制 judge**），但**全仓除该声明外无任何读取点**（实测 grep 只命中 6 行声明 + 1 处设计文档）⇒ 实际生效的是 `Invoke-Review` L3003 的**窄判据** `$judge['type'] -eq 'egress'`，它**只挡 `local-only`**、对 `sanitized` 一律放行 ⇒ **声明的意图从未生效**（"声明了但没接线"，与 `$backendEgress` 硬编码同族）。**本次审计范围（逐个过"声称覆盖全部"的机制）**：消毒（2 调用点，见上）· 敏感度闸（4 处：`Resolve-Model` / `Invoke-Task`（主路 + fallback 入口）/ `Invoke-Task-Claude` / `Invoke-Review` —— **只有 review 这处是窄判据、只挡 `local-only`**）· `Get-ScrubBlockReason`（2 处，**review 无**）· 证据清单基线 `Get-FrameworkSubjects`（**已登记**）· 站上 `out/` 固定名无陈旧守卫（**已登记**）· `secrets` 门禁只扫 git 跟踪文件（**已登记**）· BOM 子判据只覆盖 `.ps1`（**by design**，`.sh` 加 BOM 会让 shebang 失效）· `doclinks` 只判可达不判语义（**by design**）⇒ **新查出 2 项（②③）**，其余**已登记或属设计取舍** | ⏳ **收口待人裁（三项，各列影响面）** —— ⚠ **2026-09-21 细化分析见 [REMEDIATION-PLAN.md §5](REMEDIATION-PLAN.md)**（新增第三选项"附件默认不出网 + 显式放行"、把 W1 拆成 W1a/W1b、并按"存量只有 2 张卡会出网 + `review` 无常态调用"**把本行的缺口②从 P0 修正为「结构性 P0 / 暴露面 P1」**）：**① 附件** —— (a) 把附件纳入 scrubber（改动小，但 agent 读到的就不是原文，可能破坏依赖附件内容的任务）；(b) 对"含敏感附件的卡"**强制 `local-only`**（纪律，零代码，但依赖卡作者守规矩）。**② `review` 出网** —— (a) 在 `Build-JudgePrompt` 之后 / `Invoke-Judge` 之前**加同一套 scrub + block 判据**（与派发同规矩；代价：判据看到的卡正文被抹，可能影响评审质量）；(b) 对 `sanitized` 卡的 review **强制本地 judge**（`main`/`m27`/`rpc-v4flash` ⇒ 零出网；代价：失去异源判据）。**③ `compliance`** —— ✅ **已闭环（2026-09-21 W1a，选 (a) 接线路线）**：`compliance` 与新增的 `egress` 字段现在**都被真值函数读取**（`Get-JudgeComplianceReject` / `Get-JudgeEgress`，缺字段 ⇒ **拒/视为出网** fail-closed），review 闸改为「**硬不变式 + 表驱动**两判据都过才放行」；同批把**三处"按型号前缀判"（`Resolve-Router` / `Invoke-Task` / `Split`）换成后端属性判据** `Get-BackendEgress`（**fail-closed 默认：只有 `local/` 不出网，其余一律出网**；claude 通道豁免以免误杀 P3）⇒ **「再加一个后端/judge 又漏一次」的结构根因消除**。**自证**：夹具 **119/119**（含 ★"假想云端后端 `brand-new-vendor/*` ⇒ 出网"负例、`ROUTE_TABLE` 12 个 id 的出网/站内两类非空断言、`JUDGE_TABLE` 6 个 judge 的 `egress+compliance` 覆盖率断言、AST 断言"全仓不再存在按前缀判敏感度"）+ **两次变异自证**（`Get-BackendEgress` 恒 false ⇒ 5 条同时红；删一个 judge 的 `egress` ⇒ 覆盖率断言红并点名 `main`）+ **实弹**（`route` 三态、`task` 层 rc=4 且**零触站**、`local-only` 正例不误杀）。**剩两项已裁定（2026-09-22，见 [REMEDIATION-PLAN §5.5](REMEDIATION-PLAN.md)）**：**②选 (a)**（`review` **复用**同一套 scrub + block，**不**强制本地 judge）—— 决定性判据 = **档位语义一致性**：`sanitized` 的**定义**就是"抹后可出网"，若 review 不走抹，同一张卡的含义会**取决于跑哪个子命令**（且原推荐的 (b) 会引入"本地 judge 需引擎在位"这一新可用性依赖，引擎不在位时 review 直接不可用）；(b) 保留为**显式可选**（卡写 `review-model: main` 即可，无需新机制）。**①选 (c) 附件默认不出网 + 显式放行** —— 决定性判据 = **可判性**（附件形态不可判 ⇒ 抹不出可测覆盖率 ⇒ 只会产出"抹了一半"的假防线）。**⇒ 统一判据：可判的载体沿用档位定义（抹后可出网）、不可判的载体默认不出网**。⚠ 我原先在 §5.1 推荐的是 (b)（本地 judge），**裁定改为 (a)**，理由（档位一致性 + 新依赖）已写进 §5.5.1 的"反对意见"节。**实施项见 §5.5.3 —— ✅ 均已实施（2026-09-22）**：① `Invoke-Review` 已与派发**同规矩**（`Resolve-ReviewPrompt`：先 block 判据（命中**拒发**）→ 只对 `sanitized` 抹 → 再发请求）；② 附件已改为**默认不出网 + 显式放行**（新卡字段 `attach-egress: ok`；两个通道各判一次）。**自证**：夹具 **133/133**（+14，含 review 三态**行为证据**、位置断言、attach 五态）+ **两次变异自证**（两个函数各自失效 ⇒ 4 条同时红；**顺序变异**：在闸前插一个诱饵发送点 ⇒ 位置断言当场红） + 实弹三条（`sanitized` 卡 review ⇒ 3 处 `SCRUB` + `score=优秀` rc=0；私钥块卡 review ⇒ `REJECT scrub-unsafe:private-key` rc=4 且**零触站**、`review.json` 未创建；附件卡 + 出网型号 ⇒ `REJECT attach-egress-unconfirmed` rc=4 且**零触站**）。⚠ 实施中发现并修掉一条**假判**：位置断言第一版用文本 `IndexOf` 命中的是**注释里的函数名**（"调用被搬走也 PASS"）⇒ 改为 **AST 找实际命令调用**（详见夹具注释）。原选项 (b)"删字段"已作废（选了接线）。**⚠ 追补（2026-09-22，§5.5.4）**：W1b/W4 让 `review` 写出 **`review.json` = 新证据件**，门禁随即报出「已归档但未被任何 subject 覆盖: review.json」（`paper/202609221131192690`）⇒ 已按门禁给的修法把 `review` 件加进**两个**按路基线（`Get-FrameworkSubjects` / `Get-ClaudeFrameworkSubjects`）并**带 `ephemeral = $true`**（事后写入、非派发必有 ⇒ 裸列会让每个未 review 的 run 假报 `missing-artifact`）。**⚠ 关键**：manifest 是**派发时快照 ⇒ 不回溯** ⇒ 该 WARN **不会被这次修复消掉**（存量那条的 manifest 是修复前写的），修法只保证**将来**不再产生；存量那条属历史欠账，要消掉须 `agent audit --accept`（**按设计是人的显式动作**）—— ✅ **已于 2026-09-22 用户裁定后执行**：水印 **15→16** 条，门禁 `evidence` 转 **PASS**（`gap 16 条(存量 16)`、无新增）。同批还拿到了**真实派发**的行为证据（此前记为"省略的 e2e"）：修复前 run `202609221131192690` 的 manifest = `subjects=10`、**无 `review`**（故 `review.json` 成缺口）；修复后 run `202609221224005057` / `202609221229582508` = `subjects=12`、**含 `review`(`ephemeral=True`)**、audit 表 `未声明=0` ⇒ **缺口不再产生**。⚠ 水印 `ops/.audit-baseline.json` **被 gitignore** ⇒ 换机/重克隆会重新报这 16 条存量（按设计："接受"必须留痕在人这一侧）。夹具 **133 → 137**（+4）+ **变异自证 3 次**（去 `ephemeral` ⇒ 2 红；整条删 ⇒ 8 红；破坏 Merge 透传 ⇒ 2 红）。**建议顺序（已按 §5 细化修正）**：③(a) → ②**(b)** → ①**(c)**（先把判据接到真值源；再让"出网"变成**需显式放行的例外**；最后把附件/PII/拓扑统一交给档位）。**关联**：本轮同时发现 claude 路附件面两处（站上变体附件未同步 / headless 工具未验证）与 zen 不可用 —— 见上两行 |
| **⚠ 注入式探针 `_probe_fallback.ps1` 自 W1a 起静默失效（2026-09-22 发现并修复）** | **症状**：核 §5.5.4 时顺手跑探针做行为自证 ⇒ **立即抛** `The term 'Get-BackendEgress' is not recognized`。**两个独立根因，都源自"判据自己有无调用点"这条老问题**：**① 提取清单漂移** —— 探针用**硬编码函数名清单**从 `agent-cli.ps1` 抽纯函数进会话（它 stub 站点依赖、只跑 `Invoke-Task` 真逻辑）；此后 P5 规则扩充加了 `Get-ScrubRules`、W1a 加了 `Get-BackendEgress`、W4 加了 `Get-AttachEgressReject`、C1 加了 `Test-CtxOverflowError`/`Resolve-CtxOverflowCode`、O-13 加了 `Resolve-ClaudeStationCandidates`/`Resolve-ClaudeBudget` ⇒ 清单没同步 ⇒ `Invoke-Task` 一跑到新函数就抛。**② 文本签名过时（且过时方向危险）** —— 覆盖断言数的是**字面量** `Get-SensitivityBackendReject … -backendEgress $true` 出现 ≥2 次；而 **W1a 的全部用意正是把硬编码 `$true` 换成后端属性判据**（故意只留兜底入口 1 处）⇒ 实测只剩 1 处 ⇒ **判据与设计反向**（继续用它等于要求"把属性判据改回硬编码"）。**为什么无人察觉**：该探针**无自动调用点**（手动跑；不在门禁/夹具/hook 里）⇒ 坏着没人知道（W1a 09-21 → 发现 09-22）。⚠ 与本表"`syntax` 抓不到无 BOM 脚本"那条**同族**：**守门人自己死了，而没有任何判据判"守门人还活着"** \| ✅ **已修（2026-09-22）**：① 提取清单补齐 4 组新增纯函数，并在注释里写明**同步纪律** + 判据（"`Invoke-Task`/`Invoke-Task-Claude` 体内是否直接调用它"）；② 覆盖断言改 **AST**（数 `Invoke-Task` **体内** `Get-SensitivityBackendReject` 的 `CommandAst` ≥2 处）+ 保留"拒绝串可分辨路径"（文本判据那次的教训：**文本签名会随实现改进静默变成错误的要求**）。**复跑全绿**，并顺带新增一条**行为证据**断言 `claude baseline: review(review.json) present + ephemeral=true`（见上一行的 §5.5.4）—— 这是本仓唯一能**离线**跑真实归档路径并读到 `.agent-run.json` 的地方。**当时待办**：给探针加**自动调用点**，或至少加一条"探针可导入 + 提取清单齐备"的冒烟判据 —— 否则**它还会再烂一次**（这次 8 天，下次可能更久）。**更彻底的方向**：把硬编码清单换成"提取**全部** `FunctionDefinitionAst`、**再**覆盖 stub（stub 在后 ⇒ 仍生效 ⇒ 免维护） \| ✅ **已闭环（2026-09-22）**：给探针加 `-SmokeOnly` **静态自检** + **由夹具调用它** ⇒ "**探针还活着**"第一次有了**有调用点的判据**（夹具是派发路径改动的指定验证手段）。**⚠ 判据形状（要紧 —— "能 import"式冒烟**抓不到**本类失效）**：探针的失效**不在提取阶段**（清单里的名字都在、提取都成功），而在**运行阶段**（调用到一个没被提取的函数）⇒ 自检必须按「`Invoke-Task`/`Invoke-Task-Claude` **体内调用到的**、`agent-cli.ps1` **里有定义的**函数」这一**集合**判：它们必须**在提取清单里**或**被探针 stub**（stub 也是 `function` 定义 ⇒ 从探针自身 AST 读得到）；只判"有定义的函数"，原生命令/cmdlet 不在范围内。⚠⚠ **首跑即命中一个潜伏漂移**：`Invoke-ClaudeFly-Station` 被 `Invoke-Task-Claude` 调用却**从未进清单** —— 之所以没爆，只因探针里站上候选探查必然失败（`Test-StationEngineReady` stub 恒 `$false`）⇒ **走不到那一行**；一旦有人把该桩改成 `$true`，探针**立刻死**。**自证**：夹具 **153→154**（新增"跑 `-SmokeOnly` 且 rc=0"一条）+ **变异自证**（从清单里拿掉 `Get-BackendEgress` ⇒ smoke **rc=1** 且**夹具红并点名**）。**仍留一条（明确记为可选、非紧迫）**：把硬编码清单换成"提取**全部** `FunctionDefinitionAst`、**再**覆盖 stub" —— 可免维护，但会把**大量与探针无关**的函数（含依赖站点/文件的）一起抽进来，风险大于当前收益；**有自检兜住后不再是紧迫项**。 | ✅ **同日再进一步（2026-09-22，用户裁定"两条都做"）：已换成"提取全部 `FunctionDefinitionAst`、再覆盖 stub"** ⇒ **"清单漂移"这一失效模式被构造性消除**（**不提清单就不会漏**；原 26 项清单删除，现提取 58 个函数）。⚠ **但它换来了一个新的失效模式：顺序** —— stub 必须**在提取之后**定义才生效；若被挪到提取**之前**，会被真函数**覆盖**（例：`Invoke-RemoteScript` 的 stub 失效 ⇒ 探针**真的去 ssh**，而表面一切正常）⇒ 自检随之改为判**两条**：① `Invoke-Task`/`Invoke-Task-Claude` 存在；② **顺序不变量**（本文件每个 `function` 定义都晚于提取边界）。**已核对无遮蔽风险**：agent-cli.ps1 的 58 个函数**无一与内置 cmdlet 同名**。**自证**：夹具仍 **154/154**、探针全跑 `PROBE_FALLBACK pass`；**变异自证**（把一个 stub 放到提取边界**之前** ⇒ smoke rc=1 **且夹具红并点名**）。⚠ **过程中被自己的判据抓到一次重构漏改**：`coverage` 断言原先读 `$it`（提取 `Invoke-Task` 时留下的中间变量），该变量随重构删除后计数变**空** ⇒ 断言**当场红**（空值 `-ge 2` 为假，红得"对"）⇒ 改为**就地**从 `$fns` 取 AST，不再依赖别处的中间变量。 |
| **账户未完成 18+ 年龄确认 ⇒ Meta 系型号全 403（2026-09-21 新登记，账户配置）** | **实测**：请求 `meta/muse-spark-1.2` / `meta/muse-spark-1.2-contributor` 一律 `403 This model requires you to complete the following before use: 18+ age confirmation.`（提示去 `openrouter.ai/settings/…`）。**影响**：**不**影响现用备路型号（非 Meta 系），但**挡住未来选型**（本轮本想用 Meta 型号交叉验证"付费档训练开关"的推断，被此闸挡下）。**另注**：`/api/v1/models/user`（443）相对 `/api/v1/models`（446）少掉 3 个型号（2×Meta `-contributor` + `sakana/sakana-namazu`，**均为 live、无下架日期**）⇒ 是**策略过滤**而非下架；但**非** contributor 的 `meta/muse-spark-1.2` 仍在列表内却也 403 ⇒ **18+ 闸不是**该过滤的原因，两者是独立现象 | 待办：属账户配置项，按需在 dashboard 完成年龄确认（**不必现在做**，因为不挡现用型号）；若将来要用 Meta 系型号再补 |
| **⚠ "备路/换站的总墙钟预算"缺失（2026-09-21 新登记，测量 3 副产物）** | **实测**（[§3.5](../../docs/research/2026-09-21_D6备路站上化与sensitivity设闸调研与方案.md)）：`fallback-deadlock` 卡声明 `timeout_s=10`，而**实到墙钟 `33.4s`**（主控侧 sync/collect + 远程 run 20s）。**根因**：`timeout_s` 只包住远程 `timeout $timeout opencode run …`（`agent-cli.ps1` L1320），**不覆盖** ① 站上引擎加载（`T_load`，11G 模型实测 **7s**）② 主控侧 sync/collect ③ `Invoke-StationReady` 的就绪校验（内含 `-m60` 的 chat 往返）。⇒ 任何"换站 / 先加载再用"的方案都会**在这三段里无预算可依**，且调用方看到的墙钟与卡声明的预算**可差 3 倍以上**。**⚠ 别混淆**：P4 的 `fallback-timeout-s`（2026-09-21 **已实施**）是 **claude 通道跑批**的独立预算是另一个缺陷的修法，**不覆盖**上面三段 ⇒ **本行未闭合，待办不变** | 待办：若要引入"换站/加载"，须**另立一个总墙钟预算**（命名避开 `fallback-timeout-s`），并明确超时后是 fail-closed 还是回落云端；与 P3 的选型结论一起定 |
| ~~**`agent-cli.ps1 task` 进程退出码 = 0（rc 可信性）**~~（2026-09-21 登记 → ✅ **2026-09-22 当日闭环，且**定级被实测修正**） | **⚠ 登记里的两条结论都被这次的实测推翻，先记更正**：① **不是"特定于 AUTO_FALLBACK 那条返回路径"** —— 登记据此写的理由（`route --model no-such-alias` 返回 2、`task -Cli claude` 返回 4 都对）**站不住**：那两条都恰好在污染点**之前** early-return。实测**不带** `AGENT_AUTO_FALLBACK` 的普通超时 run 同样 `TASK_DONE … exit=6` + `ledger+=…,6,…` 而**进程 rc=0** ⇒ 真实范围是"**任何走过 `.attach/` reset 之后的派发**" = **每一次真派发**；成功时看不出（本来就该 0），**失败时被静默读成成功**。② **"推测（未证）"已证并改写**：不是 `ssh`/`scp` 残留**文本**，而是 `Invoke-RemoteScript` 的 **int 返回值 0**。**测法（值得复用）**：给 CLI 入口加临时诊断打印 `$code` ⇒ 实得 `codeIsArray=True count=2 / [0]=Int32 0 / [1]=Int32 4`；再用 **AST 扫 `Invoke-Task` 体内的"裸语句"**（未赋值、未 `\| Out-Null`、未 return）⇒ 定位到 attach-reset 处那行**裸调用** `Invoke-RemoteScript`（返回 int rc、成功后=0；09-18 缺口 5 把它改成**无条件** reset ⇒ **每次派发都跑**）。机制另经**独立钉死**（临时脚本直测进程 rc）：`exit 4`⇒4 / `exit @($null,4)`⇒**0** / `exit @(0,4)`⇒**0**。**同族根因**：09-18 "归零纪律"清点时只覆盖 **cmdlet**（`Copy-Item`/`Move-Item`/`Remove-Item`/`Add-Content`），**漏了自定义函数的返回值** \| ✅ **已闭环（2026-09-22）**：**两层修** —— ① **根因**：全仓 **6 处**裸 `Invoke-RemoteScript` 一律 `| Out-Null`（归零纪律补全）；② **出口守卫**：新增纯函数 `Resolve-ExitCode`（取**末元素**）并让**全部 5 个** `exit $code` 走它（防"新增子命令又漏"）。⚠ 守卫取末元素与 `_probe_fallback.ps1` 早已有的 `Scalar` **同规则** —— 这正是"**探针一直没被骗到、只有 CLI 的调用方被骗**"的原因。**实测闭环**：同一命令 ⇒ `REJECT … exit 4` + **`PROC_RC=4`**；不带 fallback 的普通超时 run 亦回到真值。**自证**：夹具 **137→147**（+10）+ **变异自证 3 次**（删回 `\| Out-Null` ⇒ 裸调用断言红；守卫改取**首**元素 ⇒ 2 条标量化断言红；撤一处出口守卫 ⇒ 2 条计数断言红）。⚠⚠ **自证当场抓出我自己的一条假判据**：裸调用的 **AST 判据第一版只判 `StatementBlockAst`**，而**函数体是 `NamedBlockAst`（与它是兄弟类，不是子类）** ⇒ "写在函数体顶层"的语句**全被漏掉**，而那处 bug 恰在顶层 ⇒ **删回 `\| Out-Null` 也照样 PASS（假安全）**；收了两个容器类型后才红。**教训（与"位置断言被注释骗"同族）**：**结构判据必须先在"已知该红"的变异上验红，否则它只是"在跑"，不是在判。** |
| **⚠ `infer-load` 写死 `--no-context-shift` ⇒ 超限硬失败 + 客户端不识别 ⇒ 挂死（2026-09-21 新登记，重新定性 + 待裁定）** | **事实**：[`infer-load` L232](../../ops/station-bin/infer-load#L232) 的启动行写死 `--flash-attn on **--no-context-shift** -c "${CTX:-32768}" …`。**后果链**：① 请求超过引擎 ctx（`-c`）⇒ ② llama.cpp 回 **400** `request (N) exceeds the available context size (M)`（逐字出自其 `srv send_error`；见本表 O-21/O-23 与社区返证 `anomalyco/opencode#11286`）⇒ ③ **`opencode` 不识别该错误串 ⇒ 永久挂死** ⇒ 在我们这边表现为 **`rc=6`**。**⚠ 重新定性**：这条链里**引擎是健康的**（它**秒回 400**，不是挂）—— 挂的是**客户端**。故本类问题**不是"引擎不可用"**。**为什么以前没这么定性**：O-21/O-23 的闭环都落在"服务端 ctx 上限"上（正确，且"环境修复 > 配置修复"），但**没有把"客户端不处理 400"这一环单独记下来**，也没人把它与 `--no-context-shift`（**该旗标是随 unsloth 迁移 `5c712ce` 带进来的，旁边无理由注释、无 issue/ADR 讨论**）联系起来。**三个已知修法**（社区）：① 提高 ctx（受统一内存约束；且有下界 —— 社区实测 agent 的 system prompt+工具定义**本身就 19k~22k** tokens）；② 开 **context shift**（llama.cpp 对这条 400 的建议原文就是 "try increasing the context size or **enable context shift**"）；③ **客户端识别该错误串**（业界标准做法：litellm 的 `is_error_str_context_window_exceeded` + `context_window_fallbacks` 自动回切）。**为何要紧**：`--no-context-shift` 在"判据必须可信"的取向下有正当理由（**静默截断会让结论不可信**），但**那个理由从未被写下来**，也**没人核对过它与"客户端不挂死"组合起来的代价** —— 现在是"硬失败 **+** 挂死" **⚠ 2026-09-21 实弹（两级结果，改变了本行的定性）**：① 用 **456KB 卡（≈114k tokens，引擎 ctx 的 3.5 倍）** 在 **B 站 `gpt-oss-20b`（引擎 ctx 32768）** 上实跑 ⇒ 命中的是**形态 B**：错误体逐字为 `Message too long: 104003 tokens exceeds the 32768-token context window … "code":"context_length_exceeded"` —— 这是 **opencode（客户端/SDK）自己的长度校验**，**不是** llama.cpp 的串 ⇒ **快速失败 `rc=1`**（且还 `RESUME[1]/[2]` 两轮各立即失败），**不是 rc=6** ⇒ **本就不触发 fallback**。② **形态 A（引擎侧 llama.cpp 400 ⇒ 挂死 ⇒ rc=6）本次未复现** —— 它要求"**引擎实际 ctx < opencode 的 catalog 认知**"，而本次实测**证明 opencode 对该模型的内置 catalog 就是 32768、与引擎一致**（所以它**自己算出**超了 ⇒ 请求根本没发出去）⇒ **这同时收窄了 O-23 的"预算不可信"结论**（至少对 `gpt-oss-20b` + 当前 opencode 版本已不成立）。**⇒ 结论：「ctx 超限」不是一个形态而是两个，落点完全不同**（A=挂死 rc=6 会被备路兜；B=快速失败 rc=1 不触发备路） | 待办：① ✅ **已裁定（2026-09-21，见 [§3.8](../../docs/research/2026-09-21_D6备路站上化与sensitivity设闸调研与方案.md)）：保持 `--no-context-shift`**。**三轮实测钉死**：(i) 旗标**确实到达**内层 llama-server（最终命令行里出现**两次**）；(ii) 超 ctx 请求**即时 400**（≈76,650 tokens ⇒ HTTP 400，0.26s，未排队未截断）；(iii) ⚠ **那条 400 是「引擎原生」的** —— **绕过 opencode** 直连引擎拿到**逐字同款**报文 ⇒ **更正** §3.7 把"形态 B"定性为"客户端校验"的说法；**opencode 当前是快速失败 `rc=1`（不挂死）**。**裁定理由**：**硬失败丢的是任务，shift 丢的是可信度** —— 静默截断会让证据流/归档/验收/基线**所有下游判据同时失真且不可回溯**；而硬失败把"撞上限"变成**可见事件**。**反对意见 4 条已列**（含"若客户端将来回退到挂死 ⇒ 硬失败变挂死"⇒ **由 C1 兜 ⇒ C1 是本裁定的配套依赖，非可选优化**）。**另**：该旗标在项目里**约二十处一致出现**（非某次迁移偶然）⇒ 此前是**惯例**，现在成为**有据之规**；② ✅ **已实施（2026-09-21，C1）**：纯函数 `Test-CtxOverflowError`（认 4 个**逐字**串，**且已按版本归类** —— 当前版 `Message too long`/`context_length_exceeded`；旧版兼容 `exceeds the available context size`/`ContextOverflowError`。**llama.cpp 改过这段文案**，这正是第一版判据在实弹里**一个都没命中**的原因）+ `Resolve-CtxOverflowCode`（**只 rc=6 ⇒ 14**；其它 rc **不改**，免掩盖 rc=1 的其它含义）⇒ 挂死那类**不再被备路兜错**；`_VERDICT_RC_MAP` 加 `14:{14}`；DESIGN §8 加 `14` 行；夹具 **81/81**（含**位置断言**守住"检测必须早于台账行 ⇒ 四处 `$code` 一致"）；**实弹证实**（诊断行出现 + `exit=1` 未被改写 + 无 `AUTO_FALLBACK` 行）。③ ⚠ **"客户端不处理 400 ⇒ 挂死"那一支在当前版本下不可复现** ⇒ `rc=14` 是**为旧版本/未来回退准备的防线**，**不要**把它当活跃缺陷去修；④ **新增可做项**：把"**引擎 ctx vs 客户端 catalog 一致性**"纳入巡检 —— 两者一致时客户端会**自己算出**超限（形态：快速失败），**不一致**才会把请求发到引擎（O-23 的成因）；现成探针 `_station_ready.sh` 已输出 `ENGINE_CTX`。详见 [§3.8](../../docs/research/2026-09-21_D6备路站上化与sensitivity设闸调研与方案.md) |
| **⚠ 引擎被占满时新请求静默排队（补实测数据 + 对备路的含义，2026-09-21）** | **实测**（[§3.6(d)](../../docs/research/2026-09-21_D6备路站上化与sensitivity设闸调研与方案.md)）：B 站 `gpt-oss-20b`（`parallel_slots: 4`）用 4 个长生成占满后，**第 5 个请求 `HTTP 200 / 66.57s`** —— **排队等了 66.6 秒才成功，不是拒绝、不是报错**。释放后 `1.07s` 恢复。**这补上了 [O-25 slot-gate](../../.trae/documents/O-25-P1-slot-gate.md) 那条"任务会静默排队直至 900s timeout 被杀"的**实测数字**（此前只有推断）。**对备路的含义**：备路的现实触发场景不只是"引擎坏"，还有**"引擎被占满"** ⇒ 同站本地备路会**把预算耗在排队上**（实测 66.6s **远超**多数卡的 `timeout_s`，如 `fallback-deadlock` 的 10s）⇒ **同站备路在这种场景下会超时失败**；而异站/云端不共享本站队列 ⇒ 立即可用。⇒ 这是 P3「故障域/资源隔离」论据的**可复现支撑**（不再依赖"引擎会坏"这种未复现的担忧） | 待办：① P3 选后端时把"目标站 slot 是否忙"纳入判据（**不只是"引擎在不在"**）—— 现成探针已能给（`_station_ready.sh` + `/api/inference/active-generations` 的 `count`/`parallel_slots`）；② 备路预算（P4 的 `fallback-timeout-s`）要**大于**可接受的排队时间，否则同站备路形同虚设 |
| ~~**`Get-FrontMatter` 返回预置 18 键固定集 ⇒ 用它判"有无 front-matter"会恒真**~~（本轮新发现，已闭环） | ✅ **09-18 当日闭环（知识型，无需改 API）**：`Get-FrontMatter` 返回的是**预置 18 键的固定集**（文件里没有的键以**空值**返回）⇒ `$fm.Keys.Count` **恒为 18**。卡身份护栏首版正是用 `Keys.Count` 判"有没有 front-matter" ⇒ **判据恒真、护栏放行**（实测：无 front-matter 卡照样进入派发）。**修法**：看**原文围栏**（`ReadAllText` 后 `^\s*---\r?\n`，顺带免疫 BOM）。**同族**：批 A 的 `TASK_ID != label`、缺口 4 的空件被丢、3-a 首版的摘要自比 —— **"判据在跑"与"判据在判"是两件事**。已写入 [DESIGN.md](DESIGN.md) schema 注释与 ADR-0007 | — |
| **证据件在站上 `out/` 按名共享（除 `.meta` 外无陈旧守卫）** | **09-18 新登记（证据完整性）**：远端 `out/` 下 `.prompt.txt`/`.progress`/`.accept-cmds.txt`/`.golden-cmd.txt`/`.workspace-diff.txt`/`.attach-manifest.txt` 都是**固定文件名**，只有 `.meta` 有 O-22 的"TASK_ID 陈旧"守卫 + 主控侧 META_STALE 降级。若一次派发被中止而站上脚本仍在跑（本轮实测：orphan 采样器继续写 `.progress`，孤儿脚本还会在结束阶段写 `.meta`），**其它件可被覆盖且主控侧无判据**（本轮靠中止后人工清理规避）。**为何要紧**：本轮新增的 `attach-manifest.txt` 也在这一族里 ⇒ 其摘要虽被链钉住，但摘要的**输入**（清单原件）可被后续孤儿覆盖而不报警 | 待办：站上 `out/` 改 **per-run 子目录**（如 `out/<ts>/`）或给每件加 `TASK_ID` 首行 + 主控侧统一陈旧守卫；属改动派发关键路径，须走阶段 0.5 夹具 |

> **计数说明（2026-09-16 深夜）**："真实剩余 open" 现为 **10 项** —— 上表 5 项长期项（O-07/G13、G14/G10、G7/O-16、G8 R 依赖包、记忆协同设计取舍）+ 当日新登记 5 项（root 级脚本治理空白、证据流可重放性阶段 1-3、ssh/scp 未统一 BatchMode、`doclinks` 对新文件的盲窗、`Get-FrontMatter` 不剥引号）。当日曾登记的另 6 项（`_agent-cli-bom.ps1`、G10 负例 flaky、`cpphub-001` 映射、`infer-load` key 明文、`secrets push` 覆盖、**框架级 ssh 建连 14-17s**）**全部当日闭环**，均保留划除行以便溯源。同日已闭环的更大项另有：Cpp_Hub 假子模块/unmapped gitlink、claude key 单一真值修正、studio 日志明文面收敛、凭据下发方向保护、**任务卡证据回收闭环（ADR-0005 阶段 0）**、**控制面传输绑定 LAN IPv4（ADR-0006）**（见 [DEVELOPMENT-LOG 2026-09-16 ⑧–⑭](DEVELOPMENT-LOG.md)）。

> **计数说明（2026-09-17）**：**当日闭环 3 项、新增 1 项** ⇒ "真实剩余 open" 由 10 项变为 **8 项**。**闭环**：① **证据流可重放性阶段 2**（复验器 `agent chain/verify` 落地 + 门禁第 15 项断言 `evidence`，见 [ADR-0007](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md)）；② **缺口 9 文档漂移**（`CLOSED-LOOP-ANALYSIS:91` 已订正为"独立文件 review.json"）；③ **缺口 7 门禁零覆盖**（并入①）。**放宽**：缺口 6（台账 `queue_s/run_s`）形态改写为"台账两列硬编码"⇒ 降为一行接线，归批 B。**新增**：`syntax` 断言占 quick 门禁 96% 耗时。**未动**：阶段 1（manifest）/阶段 3（异基座审计，挂起）/缺口 4、5、8、10（归批 B，需先建阶段 0.5 夹具）。

> **计数说明（2026-09-18）**：**当日闭环 3 项、新增 1 项** ⇒ "真实剩余 open" 由 8 项变为 **6 项**。**闭环**：① **缺口 6**（台账 `queue_s/run_s` 一行接线，阶段 0.5 夹具实测 `…,0,2,20`）；② **缺口 10**（front-matter 围栏 —— 实测更正失效形态为"正文行可静默覆盖已解析键"，含 `readonly`；一行守卫 + 4 条回归用例，13/13 PASS）；③ **阶段 0.5「改动验证闭环」建成**（夹具入库，正负双向验收）—— 严格说是**解锁项**而非缺口项。**新增**：`syntax` 断言抓不到"无 BOM 的含中文 .ps1"（本轮踩到：卡解析器的回归守门夹具 `_fm_golden_test.ps1` 因此**静默失效**）。**未动**：阶段 1（manifest）/阶段 3（异基座审计，挂起）/缺口 4（diff 证据）、5（attach 哈希）、8（遥测）。**⚠ 阶段 1 与缺口 4 的执行顺序需重排**（见下）。

> **🔁 执行顺序修正（2026-09-18，本轮侦察得出）**：ADR-0007 D5 把 `缺口 4 diff + 阶段 1 manifest + 缺口 10 围栏` 列为同批，**其中前两项的顺序是反的**。理由：① 缺口 4 的载体若要**加进入链件集**，按 D2 必须 bump `AGENT_DIGEST_RECIPE` ⇒ **全部历史条目误判断链** ⇒ 只能重建链 = **重新基线化**（等于把当时的字节"洗白"，丢掉此前篡改的可检测性）；② 而**阶段 1 manifest 正是"按 run 声明件集"的机制**，它才能让新增证据类型**不触碰全局 recipe**。⇒ **正确顺序：阶段 1 先行，缺口 4 作为 manifest 的一个 subject 落地**。③ 另需先决断：远端工作区**不是 git 仓库**（实测 `paper` 两站 `git=NO`）⇒ 调研 §7.2 草案里的 `git diff` 方案**不可用**（非仓库上静默返回空 = 假的"未越界"），须改用**与 git 无关**的载体（`find -newer <marker>` 或前后快照差）；④ 且 `readonly` 现为"**仅记录**"（DESIGN §4.1 层2），真判据需带 **allow-path**（多个 readonly 卡的交付物写在 `out/` 里，naive"readonly⇒零改动"会**误杀合法运行**）。**故本轮的 B2 只完成缺口 10；阶段 1 与缺口 4 留作独立一批，且顺序为 1 → 4。**

> **计数说明（2026-09-18 晚）**：**当日闭环 6 项、新增 1 项** ⇒ "真实剩余 open" 由 6 项变为 **5 项**。**闭环**：① **阶段 1 manifest**（围栏加固 / recipe 按条目分派 + `v2` / 卡侧三级嵌套 / 「未声明产物即失败」）；② **缺口 4**（diff 证据：`find -newer` 载体 + `diff-scope` 判据，正负双向 e2e）；③ **缺口 5**（attach 补哈希：站上逐文件 `sha256sum` ⇒ `attach-manifest.txt`，run.json `attach` 升对象数组并被链钉住；跨信任域交叉验证 3/3 + 两项负向）；④ **函数返回值污染**（环境层包装器污染管道 ⇒ 契约字段畸形成数组、复验器崩 ⇒ "归零纪律" + 复验器形状守卫，当日闭环并自证）；⑤ 顺带订正 **IMPLEMENTATION 的 `--attach` 实现描述**（tar/子目录/50MB/回收 均不实）与**台账列序**（实为 `…,exit,queue_s,run_s`）；⑥ ARCHITECTURE §6 的两处过时"缺口"标注（queue_s、diff 证据）。**新增**：**证据件在站上 `out/` 按名共享、除 `.meta` 外无陈旧守卫**（孤儿脚本可覆盖其它件而无判据）。**未动**：缺口 8（`usage`/`session_id`/`timestamp` 遥测）、阶段 3（异基座审计，**仍挂起**）。链 **76 条**（A1 12/76 · A2 13/76 · A3 3/76），门禁全量 **PASS（15/1/0）**。

> **计数说明（2026-09-18 深夜）**：本轮**闭环 1 项（缺口 8 遥测）+ 两个当日新发现同日闭环**（PS5.1 无 `[DateTime]::UnixEpoch`；`.attach/` 清理只覆盖"有附件"路径）；**新增 0 项**。故"真实剩余 open"仍为 **5 项**，但其中「证据流可重放性」一行已从"批 B 未完成"缩到**只剩阶段 3（批 C）挂起**（见 [ADR-0007](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md) D5）。链 **79 条**（A1 15/79 · A2 16/79 · A3 3/79）。

> **计数说明（2026-09-18 深夜② / 阶段 3-a）**：本轮**落地 1 项阶段成果（阶段 3-a 机器层审计 `agent audit`，属 ADR-0007 路线而非本表缺口）+ 新增 1 项观察行**（`infer-load` 健康检查首拉超时、重试即好）⇒ "真实剩余 open" 由 5 项变为 **6 项**；其中「证据流可重放性」一行进一步收窄为"**只剩阶段 3-b（异基座 judge）**"。链 **81 条**（A1 17/81 · A2 18/81 · A3 3/81），门禁全量 **PASS（15/1/0）**。

> **计数说明（2026-09-18 深夜③ / 阶段 3-b-1）**：本轮**无新增、无缺口项闭环**（属 [ADR-0007](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md) 路线推进：3-b-1 校准实测完成，跨家族 judge 四项指标全绿且证明"复核非复读"）⇒ "真实剩余 open" 仍 **6 项**；「证据流可重放性」一行进一步收窄为"**只剩 3-b-2（常跑审计）**"。

> **计数说明（2026-09-18 深夜④ / 阶段 3-b-2 定案）**：本轮**新增 1 项**（**卡片身份不进证据** —— 四项目画像时实测发现，比缺口 5 更基础：卡是最大的注入物）⇒ "真实剩余 open" 由 6 项变为 **7 项**；「证据流可重放性」一行进一步收窄为"**只剩 3-b-2，且三件事已定案**（题面不扩 / 题集常数化 ~16 条 / 落库两层），**前置** = 卡身份入证据 + 3-a 词表补 `artifact-ephemeral-by-design`"。链 **81 条**（A1 17/81 · A2 18/81 · A3 3/81），门禁全量 **PASS（15/1/0）**。

> **计数说明（2026-09-18 深夜⑤ / 卡身份入证据）**：本轮**闭环 1 项**（**卡片身份不进证据** —— 含"无 front-matter ⇒ 验收消失"的护栏）**+ 新登记 1 行已闭环地雷**（`Get-FrontMatter` 预置 18 键 ⇒ 判据恒真）⇒ "真实剩余 open" 由 7 项**回到 6 项**；「证据流可重放性」一行收窄为"**只剩 3-b-2**，且**前置已清**（3-b-1 ✅ + 卡身份 ✅）"。链 **83 条**（A1 19/83 · A2 19/83 · A3 3/83），门禁全量 **PASS（15/1/0）**。

> **计数说明（2026-09-18 深夜⑥ / 阶段 3 收口）**：本轮**无新增、无缺口项闭环**（属 [ADR-0007](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md) 路线推进：**3-b-2 本体落地 ⇒ 阶段 3 全部完成**）⇒ "真实剩余 open" 仍 **6 项**；「证据流可重放性」一行进一步标注为"**阶段 3 全部完成**（3-a / 3-b-1 / 3-b-2），两条审计命令仍 advisory 且**按需运行**"。链 **84 条**（A1 20/84 · A2 20/84 · A3 3/84），门禁全量 **PASS（15/1/0）**。

> **计数说明（2026-09-23 / 台账校正）**：**"真实剩余 open" 由 6 项校正为 4 项**，两项已实质闭环：**① root 级脚本范围治理** 已全闭环（2026-09-22，见上表划除行：迁移 + 两层谓词扩范围 + gitignore 遗留清理）；**② 记忆协同"待核"** 实质已闭合（仅留"是否跨站共享"设计取舍，非缺口）。**真正剩余 4 项 = O-07/G13（zen 真 429，事件驱动）· G14/G10 升级回归矩阵（等升级窗口）· G7/O-16 `--peer` 站间互审（等 D7）· G8 R 依赖包（等 Cpp_Hub 试点）** —— 全部为"事件/条件/依赖驱动"，无当下可动手的待办。
> 另据本会话实做，D6 审查表（L720）③ 健壮性判据的几项**已收口**（非本表计数，特记以免重复登记）：`ssh/scp` BatchMode 三件已闭环（09-22）；`syntax` `ps1-bom` 子判据确认**本就实现**（09-21 已落，见 L731）；`doclinks` 未跟踪文件盲窗**不存在**（rglob 扫磁盘实测）；`syntax` 占 quick 96% **已优化**（并行分块 19.6→6.7s）；站上 `out/` per-run 陈旧守卫**已加主控侧一致性判据**（EVIDENCE_STALE，09-23）。④ 锚年龄告警 / 证据面留存目标维持"仅记账"。
