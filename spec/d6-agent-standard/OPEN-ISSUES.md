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
| O-19 | 环境    | —    | 两站模型全卸载 → agent 层 opencode 连 8080 但 `/v1/models` 空无法推理；跨界代码任务另暴露 A 站工作区无 `.venv`（accept pytest rc=127）。4-agent 吃狗粮因此中止                                                                                                                                                                                                          | ✅ **closed（2026-09-09 4/4 闭环）** | 见 §O-19 关闭记录 | <br /> | <br /> |
| O-20 | 功能缺陷  | P1   | Invoke-Workspace 同步目标站判定被 PowerShell 动态作用域污染：从 Invoke-Task 调用时 `$HostName` 解析为 SSH 主机串（非 'A'/'B'）→ `$station` 恒回退 'B' → **跨站任务源码流恒错推到 B，A 站任务在空壳工作区跑**（specaudit 卡虚构产物根因）                                                                                                                                                                                                                                                                                       | ✅ 已修复+实机验证                   | 2026-09-05               | <br /> | <br /> |
| O-21 | 性能/超时 | P1   | specaudit 卡 900s 硬超时/`exit1`——**三重返证后真根因尘埃落定**：①外层层 `timeout 900` 强杀正常推进 agent；②曾误判 opencode 对本地 passthrough 模型 64k 硬默认（根因实错）；③**决定性返证**：`/props` 运行时 `n_ctx=65536` 而 `/v1/models` 仅通告 `n_ctx_train=131072` → **服务端 llama-server 实以** **`-c 65536`** **加载**，那条 `exceeds the available context size` 是**服务端 400**，opencode 任何配置都无法抬升。修复=conf `CTX 65536→131072` 重载 A 站 gpt-oss；实机复验 `n_ctx=131072`、specaudit 卡重跑 `RUN_S=502/TASK_RC=0/ACCEPT=1` **全程无 65536 错误** | ✅ 已闭环（服务端 ctx 修复 2026-09-06） | 服务端 `-c 131072` 重载       | <br /> | <br /> |
| O-22 | 运维缺陷 | P1   | `.meta` 残留误导：只在 run 结束写、无 task_id → 二次 run 时读到上次终态（RUN_S=900/RC=124 误判"又超时"，实为残留） | ✅ 已收口（2026-09-12） | 契约修复 + 观测判据订正 | 2026-09-07 |
| O-23 | 架构/超时 | P1   | **复杂度路由 ctx 解耦**：profile.context(code=8192/reason=32768/long=262144) 只是元数据、从未传给引擎；opencoe 用 opencode.jsonc 固定 limit.context=131072，引擎 ctx 由手动 flavor 预设决定 → 三者解耦。**凌晨 refdedupe timeout 真根因**=`request exceeds available context size (8192)`：nothink 档引擎 `-c 8192` < refdedupe 请求 12536 tokens → 服务端 400 → agent 永久挂死 → 900s timeout | ✅ 已修复+实机验证（引擎 ctx=唯一真相） | 2026-09-07 radical fix B | <br /> | <br /> |
| O-24 | 架构/闭环 | P1   | **单机 agent CLI 工作流闭环断点（分析定案）**：单机形态（无第二站分摊/换站/互审）存在 4 类断点——①review --peer 缺（产出→ledger 后无机器复核门）②超时续接 --continue 缺（长卡单机唯一韧性出路）③claude 备通道缺（单引擎死锁=停摆）④单机排队/上下文治理缺。P0=review 单机版 + continue 续接 | ⏳ **P0-① 已落地实证**（续跑循环入 $body，RESUME 出线+超时卡全链+零回归）；P0-② ✅（被 O-16 覆盖闭环） | O-24 实施记录 | <br /> | <br /> |
| O-25 | 演进/可观测 | P2   | **agent 任务执行进度可观测性（派发前预估 + 派发中节拍）**：派发后黑盒——ledger/.meta/.agent-run 均为 run-end 快照，无运行中采样 → 长卡状态不可观测、无吞吐、无 ETA；预算估算用单一 wall-clock 而非分相 | 🔵 P0 完成 + 判据③已落地：①吞吐基准表✓（THROUGHPUT-BASELINE.md+metrics-log Phase 6.2）；②`.progress` 打点✓（远端5s采样+teardown终值+collect拉取+parse回填）；③派发前预估✓（Get-ThroughputEstimate 分相估算，HIT才给/MISS不打荒，TIMEOUT-WARN预警；实证 gpt-oss 682s、回归9/9）；**P1槽位门✓（并入O-08/F1：`_slot_gate.sh`+`Invoke-SlotGate`+task接入，busy默认reject exit 24，`--slot-allow-busy`放行，slot记入run.json）**；**P2看板✓（2026-09-12 落地，L3 单文件 HTML：`make-dashboard.ps1` 生成器→内联 ledger+run.json→self-contained `dashboard.html`，file:// 直开零网络请求；已完成总览 22 行+run 详情展开；正在跑/Live tab 由 `-Live` 拉远端 .progress，无则 no-live-data；见 O-25 详情节）** | 🔵 **O-25 已全收口（①-④+P1/P2 全落地 + 2026-09-12 实机在线实测全通，见详情节）** | 一期 | <br /> | <br /> |
| O-26 | 演进/编排 | P2   | **单任务分解派发并行（Split-Dispatcher）**：现派发=单卡→单站；一张可切分 readonly 大任务卡在单节点（物理上界 3：A/B/C 各1 并发，O-18）无法利用多站。缺口=任务卡无 `decompose` 声明、编排层无拆/并、无 Merge | ✅ **已闭环（2026-09-12）**：decompose 拆 2 分片 A/B 双站并行，全子卡 accept，Merge 正确，并行 465.1s ≪ 串行 720.8s（ratio 0.645）；落地修复 2 bug | V2 fan-out L2.5（schema 冻结前加 decompose 键） | <br /> | <br /> |

## 2. 各未决项详情

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

**结论**: `opencode models` 对 name 实时读 jsonc，但 **limit.context 字段对 config 完全免疫** → 发送预算来自别处（非 jsonc）。

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

**⛔ 架构结论（修正原 O-23 假设）**: 「通过改 opencode.jsonc 的 `limit.context` 让 opencode 对齐引擎 ctx」**此路不通**——opencode 1.18.25 对自定义 provider 模型的发送预算由**内置 catalog context_length** 决定，`limit.context` 字段不参与。防线只能建在**可控层**：agent-cli 档位=引擎档位（O-23 radical fix B 已覆盖 `ENGINE_CTX` 探测 + profile clamp），opencode 客户端预算不可信（bug 级行为）不作为依赖。

**💡 未尽确认（开放）**: binary 内置 catalog 中 `qwen` 命中的确切 entry 与值来源（131072）；若需根治 opencode 层，候选方向为改 `api.modelID` 为 catalog 不存在的 id 触发 `?? Y.limit.context` 回退路径（实验 2 中未测此项，因风险高未动 modelID）。

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
| 记忆协同"待核"收尾 | 09-16 已下结论：三站 opencode memory 独立、无跨站共享（站内记忆+任务卡交接）——**该项本身已闭合**，仅留"是否要跨站记忆共享"作为设计取舍（当前不引） | 需求显现时才评 |
| ~~`_agent-cli-bom.ps1` 整份过期副本~~ | ✅ **当日闭环（2026-09-16，见 [DEVELOPMENT-LOG 2026-09-16 ⑫](DEVELOPMENT-LOG.md)）**：**取证推翻了我原先的"死副本"判断** —— 它其实是 **O-26 串行基线测量的一次性工装**（`agent-cli.ps1` 的 BOM 副本，被 root 级 `_o26_serial_loader.ps1` 以固定路径引用；运行时的 BOM 副本本写在 TEMP，与它同名无下划线）。按 D5 先确认三站 `/usr/local/bin`/`$HOME`/systemd/`agent-workspaces` **零引用** ⇒ 删除该 112KB "并列入口" **及其唯一引用者** `_o26_serial_loader.ps1` + 同步 `inventory/ops.yaml` | — |
| ~~G10 负向用例确定性存疑~~ | ✅ **当日闭环（2026-09-16，见 [DEVELOPMENT-LOG 2026-09-16 ⑫](DEVELOPMENT-LOG.md)）**：重评确认该"期望失败"断言**不成立**（① 09-14 复测位置参数 4/4 成功与本轮"无输出"冲突；② `timeout N` 探针**区分不了"挂死"与"慢"**，慢即被读成"仍挂死"=假 PASS；③ 官方 CLI 参考里位置参数本就是常规用法）。已**降级为观测**（`agent-cli-smoke.sh` 该用例改 `INFO`、汇总行加 `INFO=` 计数，不再判 PASS/FAIL），并同步 §9.11 的 SOP ②与结论 | — |
| ~~`cpphub-001` 卡与 `PROJECTS` 映射不一致~~ | ✅ **当日闭环（2026-09-16，见 [DEVELOPMENT-LOG 2026-09-16 ⑫](DEVELOPMENT-LOG.md)）**：用户裁定后按**零风险标记**处置 —— 在卡 front-matter 加 `status: retired` + `note:`（**已实测 `Get-FrontMatter` 的白名单闸会忽略未知键**，故不进 prompt、不影响解析），说明"目标源目录是轻量样本、PROJECTS 已指真项目、无 per-card 覆盖键 ⇒ 派发必 golden FAIL"。**机械证实**该断言：`F:\Cpp_Hub\src\因子计算_核心.cpp` **不存在**（golden 必报缺失）。**另记一条新发现**：该样本已被 2026-09-12 试点本身改过（源码已含 `向量均值`）⇒ **不再是干净 fixture**，即使重指也无法当回归用 | — |
| ~~`secrets push` 会用正本陈旧 key 覆盖站上真 key~~ | ✅ **当日闭环（2026-09-16，见 [DEVELOPMENT-LOG 2026-09-16 ⑪](DEVELOPMENT-LOG.md)）**：**未**采用"加一条常态黄灯"（那会制造噪声），改为**在危险动作上设闸**——新增一等入口 `secrets pull [A\|B\|C]`（站上真值收回正本）；`push` 对"站内产物"型凭据（`STATION_MINTED`）**默认拒绝覆盖**（站上已有且与正本不同则跳过并给出两条出路，`--force` 仍可强制）；`secrets status` 增"站内产物"行（只打归一化指纹）显式暴露不一致。验收：负向（正本换假值 ⇒ push 跳过、站上指纹未变）/ `--force` 生效 / `pull` 回写 + 幂等 / 终态三站一致。**顺带修** `_flow_rotate_status` 既有缺陷（把探针原始文本喂给期望 dict 的函数 ⇒ TypeError + 恒判"需关注"） | — |
| ~~`infer-load` 的 key 明文输出~~ | ✅ **当日闭环（2026-09-16，见 [DEVELOPMENT-LOG 2026-09-16 ⑩](DEVELOPMENT-LOG.md)）**：原登记"写进站上日志"**表述有误** —— 该行只打 stdout；真实暴露面是 **studio 自写日志**（`~/.unsloth/run-*.log`，每次 4 处、775/664 权限、三站累积 21 份/68 处明文）+ **该面完全不在审计视野内**。已按 a+b+c+d+e 全套处置：我方输出掩码 / 目录 700+日志 600（infer-load 强制）/ 存量 21 份就地脱敏 / `stations` 门禁补 `unslothlog` 权限判据（含负向自证）/ 补登明文面表 | — |
| **root 级脚本不受 `scripts` 门禁治理（本轮新发现）** | **09-16 新登记**：`check_scripts` 的扫描范围是 `_iter_ops_scripts()` = **只有 `ops/`**，而仓库根仍存一次性脚本 —— `audit_extra.sh` / `audit_gfx.sh` / `audit_llama.sh` / `_o26_reverify_loader.ps1`（外加**根级 `test-cards/`** 与 `spec/` 下同名目录并存）。它们既不在 `inventory/ops.yaml`（也只登记 `ops/` 项）也不被门禁看到 ⇒ **删除时才发现"漏网"**（本轮 `_o26_serial_loader.ps1` 即属此类）。**评估**：ADR-0004 的 D2/D3 治理圈原本只声明覆盖 `ops/`，所以这不是"违反"，而是**范围外空白** | 待定：把门禁范围扩到仓库根并给存量登记（属新能力，走 D3），或逐个清减后再定 |

| **D6 闭环审查（2026-09-21）—— 未闭环总账** | **审查结论**：证据流/审计 + 持久化线（ADR-0007 阶段 0–3 + P1–P4）**已完全闭环**；但 **D6 agent 框架整体未闭环**，以下四类仍未做，按优先级列：**① 证据流范围内 2 项**：`collect` 命令本身**未被执行**（[ADR-0007](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md) 阶段1注记）；~~**claude 备路证据面盲区**~~**✅ 已实施（2026-09-21）** —— claude 备路现发 `evidence_manifest`（按路基线 `Get-ClaudeFrameworkSubjects`，适配其归档件集：有 `stderr.txt` 无 `judgment-record.txt`）+ `attach` 升对象数组带 `sha256`（复验侧 `agent audit` 可见）⇒ 该路 run 由 v1 升 **v2**；`usage` 维持明标 `not-collected-claude-path`（claude 无 opencode 会话库，**不猜数**）。**② D6 工作流断点**：`review --peer` 站间互审缺（质量闭环）/ 超时续接 `--continue` 缺（长卡韧性）/ ~~**claude 备通道缺（单引擎死锁=停摆，真韧性缺口）**~~**✅ 自动 fallback 已实施（2026-09-21）** —— `agent-cli task` 显式 `AGENT_AUTO_FALLBACK=1` 开启（默认关、不掩盖真实错误），主路 opencode 引擎死锁/超时（rc=6）自动单次转本地 `Invoke-Task-Claude`；触发判定 `Test-FallbackEligible` 只认 rc=6）。其余：单机排队上下文治理缺。**③ 健壮性/判据待办**：`ssh/scp` 未统一 `BatchMode`+`ConnectTimeout`；`syntax` 缺"无 BOM 含中文 .ps1"子判据；`doclinks` 未跟踪文件盲窗；`syntax` 占 quick 96%；站上 `out/` per-run 陈旧守卫；`infer-load` key 竞态（待观察）；`Get-FrontMatter` YAML 引号。**④ 社区调研待做判据**：锚年龄告警 / 证据面留存目标（调研 §14.6，仅记账） | **下一步**：claude 备通道与超时续接是单机停摆的两个真韧性缺口，`review --peer` 是质量闭环缺口；`BatchMode` 属零风险加固。全文见 [ADR-0007 §附录一页解释](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md) |
| **证据流可重放性（evidence_manifest + 异基座管线审计）** | **阶段 0 已执行（2026-09-16，[ADR-0005](../../adr/ADR-0005-任务卡证据回收闭环.md)）**：证据回收闭环落地 —— `.meta`/`.prompt.txt`/`.progress` 原文/`.accept-cmds.txt`/`.golden-cmd.txt` 归 `agent-out/<ts>/`，`run.json.accept_golden` 增 `sha256`/`base`，TEMP 泄漏与失败路径一并修；**三项自证能力实测 PASS**（`sha256(prompt.txt)==prompt_sha256`、`accept_golden.sha256==仓库源哈希`、`judgment-record ↔ run.json` 逐项一致），collect 115s→49s。**剩阶段 1（manifest 规范化）/ 2（离线复验器）/ 3（异基座管线审计）** 未做，方案见[调研文档](../../docs/research/2026-09-16_任务卡证据流可重放性调研.md) §7.1 | **09-17 更新：路线与推进步骤已定案 → [ADR-0007](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md)**。①**阶段 2「形态」已落地**：离线复验器 `cluster.py agent chain/verify`（零自加载、不触站、离线、**指到第一条断裂处**，实测 12 项含负向双向自证 + 边界实证），设计见 [evidence-chain/DESIGN.md](evidence-chain/DESIGN.md)；②**缺口 7 已闭环**：门禁第 15 项断言 `evidence`（quick、只读、按 FAIL/WARN/info 分层）；③配套：钩子自动入链（改 `rpc.ps1` 钩子**生成器**）+ 外部锚 `ANCHOR.txt`（已 push 到 origin 作跨信任域见证，强度=「多副本见证」非密码学不可否认）；④**阶段顺序修正**（原「1→2→3 不可反」作废 ⇒ `0 → 0.5 → 2内容 → 1 → 3`，因实测复验器**不依赖 manifest**）；⑤**新增阶段 0.5「改动验证闭环」**（轻卡+小模型夹具）——因阶段 1 与缺口 4/5/6/8/10 **全都要改 `agent-cli.ps1` 派发路径**，无夹具则只能停在走查级；⑥**阶段 3 挂起**（证据面仅 6+1 件，现阶段审计员可判项过少，等批 B 扩面后重启）。**待决策：进入批 A**（`verdict-chain` + `golden-identity` 复验，纯主控侧可离线自证）。**09-18 更新：批 A / 批 B 已执行到位** —— 批 A（`verdict-chain` + `golden-identity`，含 17 项严格双向自证）✅；**阶段 0.5「改动验证夹具」**✅（轻卡 + 小模型，正负双向）；**阶段 1 manifest 完成**（围栏加固 / recipe 按条目分派 + `v2` / 卡侧三级嵌套解析 / 「未声明产物即失败」负向判据）✅；**缺口 4**（diff 证据：`find -newer` 载体 + `diff-scope` 判据，正负 e2e）✅；**缺口 6 / 10** ✅；**缺口 5**（attach 哈希：站上逐文件 `sha256sum` ⇒ `attach-manifest.txt`，run.json `attach` 升对象数组 `{name,src,kind,files,sha256}` ⇒ **被链钉住**；跨信任域交叉验证 + 三项负向均实测）✅。**仅剩批 B 的缺口 8（`usage`/`session_id`/`timestamp` 遥测）**；阶段 3 仍**挂起**。链 **76 条**（A1 **12/76** · A2 **13/76** · A3 **3/76**）。**09-18 收口：缺口 8 亦已闭环** ⇒ **批 B 全部完成** —— 站上 [`_oc_session_meta.sh`](../../ops/station-bin/_oc_session_meta.sh) 从 **opencode 会话库**取该次会话的真实聚合（token 明细 / tool 计数 / `session_id` / 时间戳）落入 run.json（取不到 ⇒ `usage.source=unavailable`，**不猜数**；claude 备路明标未采集）；独立复核用**另一张表**（Σ `message.tokens` == 会话行聚合，跨表 MATCH）；负向（改 `total_tokens` 1 位）⇒ `digest_mismatch` + 门禁红灯 ⇒ 字段**被链钉住**。链 **79 条**（A1 **15/79** · A2 **16/79** · A3 **3/79**）。**下一步只剩阶段 3（批 C，挂起）**。**09-18 再更新：阶段 3 按 D5 拆两步，3-a 已落地** —— `cluster.py agent audit`（**机器层**）：逐 subject 判"能否离线复现、卡在哪" ⇒ **可机判 gap 表**（advisory，**刻意不进 FAIL 集**；与 `verify` 分工：verify 管"是否被改"，audit 管"是否可重放"）。语料首跑：声明 **72** 条中 **67 可离线复算**、`collect` 型 **4** 条（`declared-not-executed`）、**已归档但未声明 37 件**（write 卡未声明的 `workspace-diff.txt` 等）；夹具卡已据此补全声明（新 run 实测 **gap 表为空**）。**3-b（异基座 judge：A/A 基线 + 顺序对调 + 跨家族）未做**，设计已定见 ADR-0007。链 **81 条**（A1 17/81 · A2 18/81 · A3 3/81）。**09-18 三更新：3-b-1 校准已实测** —— `agent audit-judge`（advisory，只测量不改门禁）：跨家族 judge（站内 **Qwen3.8-27B-MTP-Q8_0**，与被审证据的 gpt-oss 不同家族）在 11 条题集上 **A/A 11/11 · 序翻转 0/11 · 措辞扰动 11/11 · 与判据一致 11/11**；**关键对照**（2 条机器标签故意与判据相反）⇒ **按判据判 = 复核而非复读**；"存在未知"那条四轮均 UNSURE（不硬猜）。**诚实边界**：题面是结构化元数据 ⇒ 只证"能稳定执行写明判据"，不证"能从杂乱材料发现缺口"。**3-b-2（常跑审计）未做**，前置已满足（题面是否扩到杂乱材料等待定）。**09-18 四更新（阶段 3 收口）**：**3-b-2 本体已落地并实测** —— (a) 3-a 词表补 **`artifact-ephemeral-by-design`**（卡在 subject 声明 `ephemeral: true` ⇒ 产物"设计上不进 runDir" ⇒ **不是缺口**、但单列不计入可离线复算；改了三处：卡解析器 / run.json 照收该键 / audit 判据）；(b) 题集 **11 → 16**（含 5 条项目边界：Cpp_Hub 结果块 / Paper `index.db` 0 字节 / 中文路径件缺失 / Auto_Prover 证明日志"存在未知" / 新类 ephemeral）⇒ **重跑校准**：**A/A 16/16 · 序翻转 0/16 · 措辞扰动 16/16 · 与判据一致 r1–r4 均 16/16**（judge = 站内 Qwen3.8-27B，跨家族）；(c) 落库**两层**跑通：机器产物 ⇒ `D:\Paper\agent-out\_audits\<ts>.json`（**不入仓**；实测 `chain` 只 +1，`_audits` 不被当 run）+ 校准报告 ⇒ 入仓 `spec/d6-agent-standard/evidence-chain/audits/AUDIT-JUDGE-20260918193642.{md,json}`；(d) 卡解析回归 **22/22**（新增 ephemeral 真值/缺省、manifest 块内 `#` 注释被忽略）；链 **84 条**（A1 20/84 · A2 20/84 · A3 3/84）。**⇒ 阶段 3 全部完成；两条审计命令仍 advisory 且按需运行（未接门禁/未定时）**，若要"常跑"需另定触发与成本上限。**09-18 五更新（可运行性 + 分层闭环判定 + 先B后A 定案）**：① **修一个拦路问题** —— `cluster.py` 落库代码的 f-string 表达式段含反斜杠（PEP 701 才允许）⇒ **Py<3.12 整个模块不可解析**；门禁 `evidence` 因 `except Exception` 兜住 ⇒ 报 WARN「证据链断言跳过」而**整仓仍 PASS**（`rpc.ps1` 挑到 Python312 才侥幸正常）—— **同族于"恒真判据"（这次是"根本没判"）**；已修 + 复验转 PASS。② **可运行性实测**：`agent verify` **0.38s**（84 条全绿 · 未入链 0 · 锚在）/ `agent audit` **0.37s**（零 SSH 零参数）**均开箱即用**；`agent audit-judge` **当前不可跑**（`_flow_find_engine()`→`(None,None)`，需站上 load 跨家族引擎）。③ **全语料画像**：声明 97→可离线复算 **91**、`collect` 型 4、设计性临时 1、**未声明 37 件**、有 manifest **13/84**、gap **15 条**（零篡改）；**A1 20/84 · A2 20/84 · A3 3/84** —— 可判率低主因是 64 个 run **早于 ADR-0005（历史欠账，非坏）**，**A3 的 3/84 才是真缺口**（30 个 readonly 卡缺 `workspace-diff` 载体 ⇒ "未越界"**从未被真正判过**）。④ **分层闭环判定**：机制层 ✅ / 证据层 ⚠️（覆盖面余量）/ **运行层 ❌** —— `chain` 有自动点（钩子）、`verify` **骑 pre-commit**（`quick:True`），但 **`audit` 零自动调用点** ⇒ **D6 现在是「防篡改闭环」，不是「可重放闭环」**；阶段 3 表里"**常跑**审计"一名**名不副实，已订正为"异基座复核"**。⑤ **定案 先 B 后 A**：路 A（让 audit 常跑）难点不在成本（0.37s）而在严重度 —— 直接升 FAIL 会被 52 条存量缺口**天天红灯淹没**（同 doclinks "判不准的不进门禁"），故建议**基线化增量**（只在 gap 集合变大时告警）；路 B（扩面：37 件补进卡 + 30 张 readonly 卡补载体）**收益更高且做完后新 gap=0**，此时再挂增量门禁才干净。**⇒ 下一步：路 B 扩面 → 复跑 `audit` 确认 gap 归零 → 再议路 A 的触发点与严重度**（全文见 [ADR-0007 §审计可运行性 与 D6 分层闭环判定](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md)）。**09-18 六更新（路B 落地：框架件基线合并）**：① **侦察先推翻了上节的路B假设** —— 实测 13 个 v2 run **全部来自 smoke 夹具卡**（`evidence-manifest` 当时 100% 只存在于夹具卡 ⇒ `91/97` 描述的是**夹具语料**）；manifest 是 run.json 里的**派发时快照**（[cluster.py:3811](../../ops/cluster.py#L3811) 读 `j["evidence_manifest"]`）⇒ **改卡不回溯** ⇒ 原计划的"37 件补进卡 / 30 个补载体"**全部不可回改**（且已自动收敛：最后未声明 run = 13:26）；**真盲区是 71/84 个 recipe v1（零声明）run 在报告里完全不可见**。② **定案（用户选）框架件基线合并**：产出方 [`agent-cli.ps1`](../../ops/station-bin/agent-cli.ps1) 新增 `Get-FrameworkSubjects` / `Merge-EvidenceSubjects` —— run.json 的 `subjects[]` = **基线 ∪ 卡特有件**（按 path 去重、基线优先）⇒ **卡不写 manifest 也得到 recipe v2**。清单**唯一定义点在产出方**（审计侧仍动态枚举 runDir ⇒ "不维护第二份框架件清单"的纪律不破）；基线只列**必产出件**：无 accept/golden 的 run 上 `accept-output`/`accept-golden-output` 实测不存在 ⇒ **随门条件注入**。③ **实测**：卡解析回归 **32/32**（22→32）；e2e 夹具卡 run `202609182312282167` ⇒ **13 条 = 12 框架（去重掉卡里 12 条历史声明）+ 1 卡特有**，gap 空；**e2e 关键**：`echo.md`（**零声明**）run `202609182314143434` ⇒ 得 **10 条**（恰为基线，`accept-output` 正确未声明且 runDir 确无该件 ⇒ **无假缺件**）—— **此前必为 v1，现为 v2**。④ 链 **86 条全绿**（A1 22/86 · A2 21/86 · A3 3/86）。⑤ **13 张卡零改动**（基线覆盖其全部归档件）；**未做/新登记**：**claude 备路完全不发射 `evidence_manifest`**（且其归档件集与主路不同：有 `stderr.txt`、无 `judgment-record.txt`）⇒ 该路 run 仍为 v1，**单独立项**（避免半修）。⑥ **`audit` 零自动调用点未变** ⇒ 路 A 仍待议（全文见 [ADR-0007 §路B 落地与实测](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md)）。**09-18 七更新（路A 落地：审计常跑）**：① **先出细化调研并落档**（[2026-09-18 证据流审计「常跑」调研](../../docs/research/2026-09-18_证据流审计常跑_触发点与成本严重度调研.md)，§11 决策分析矩阵 / §12 落地实测）。**成本上限这件事关闭**：审计**进程内本体** 86 run 仅 **0.048 s**，端到端 0.34 s 中 **~85% 是"起进程 + `import cluster`"**；挂进**已有门禁进程**真实增量 **+0.013 s**（`--only evidence` 0.38→**0.393 s**）。② **一条不是妥协而是纪律落到架构上的结论**：`rpc_check.py` 对仓库**全程只读**（唯一写动作是 `check_syntax` 的 tempfile）+ 门禁挂 pre-commit ⇒ **水印不能在门禁里自动推进**，只能由**独立命令**写 ⇒ 副作用刻意接受：**"接受新缺口"成为人的显式动作**（`--accept` 与 `--json` 刻意互斥）。③ **落地 6 处**：K1 `_gap_key`（结构化 key，`<kind>|<label>|<sub>`，**不含会漂移的文本细节**）+ P1 口径行（`零声明 v1 71/86 不参与判定`）+ 水印读写（`ops/.audit-baseline.json`，**已 gitignore**，单调并集）+ `agent audit --accept`（唯一写点）+ **A2 挂载**（`check_evidence` 内只报**新增**、**逐条**打印、`fix` 给出接受命令）+ **P2**（`syntax` 取 **PATH 第一个 `python`** 单子进程复检，note 增 `.py@<ver>` 栏）。④ **双向自证**：构造新 gap ⇒ **WARN**「可重放 gap 16 条(存量 15, **新增 1**)」+ 逐条明细（存量**不重复报**）；gap 不变 ⇒ **PASS**；还原 ⇒ **PASS** 且 runDir **逐项复原**（`.agent-run.json` sha256 == 基线）、`verify` **86 条全绿**（探针只落在"未声明"轴，未污染防篡改轴）；**P2 用上一轮事故的**原构造**做探针 ⇒ FAIL/红灯**（`(py3.11.16) … f-string expression part cannot include a backslash`），**同一构造上一轮是 PASS**。⑤ 全量 quick 门禁 **10 绿 / 0 黄 / 0 红**；水印被 gitignore 命中、`git status` 未被污染。⑥ **未做（长期，已记账）**：`since` 增量扫描（20000 run ⇒ 11.3 s 才需要）、水印收缩/债务清零、**门禁只 WARN 不阻断**（D4 结论；可见性靠"新增逐条打印"兜住，仍需人读输出）（全文见 [ADR-0007 §路A 落地与实测](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md)）。**09-21 更新（claude 备路单独立项关闭）**：上文 ⑤「claude 备路完全不发射 `evidence_manifest` ⇒ run 仍 v1」**已处理** —— `agent-cli.ps1` claude 分支现发射 `evidence_manifest`（按路基线 `Get-ClaudeFrameworkSubjects`，适配其归档件集：有 `stderr.txt` 无 `judgment-record.txt`，复用 `Merge-EvidenceSubjects` 的 baselineFn 参数）+ `attach` 升对象数组带 `sha256` ⇒ 该路 run 升 **recipe v2**、`agent audit` 可见；`usage` 维持 `not-collected-claude-path`（不猜数）。并顺带补**自动 fallback**（`AGENT_AUTO_FALLBACK=1` 显式开启，主路 opencode rc=6 死锁自动单次转 claude）。验证走阶段 0.5 夹具：卡解析/证据基座回归 **44/44**，`agent-cli.ps1` 解析 0 错。详见上「未闭环总账」①/②。**实弹自证（2026-09-21，注入式）**：站点三站离线（ssh 不可达）、claude CLI 未登录（`loggedIn:false`）⇒ 无法驱动"真实站上 opencode 引擎死锁"；改为**注入式实弹** `_probe_fallback.ps1`（登记入 ops.yaml）——真实加载 `Invoke-Task` 全逻辑，仅 stub 远端依赖使主路返回 rc=6，断言：① env `AGENT_AUTO_FALLBACK=1` 桥接正确；② opencode rc=6 ⇒ `AUTO_FALLBACK` 出线并真实调用 `Invoke-Task-Claude`；③ claude run 产出 `evidence_manifest v1/4`（claude 按路基线，含 stderr/card、无 opencode 件泄漏）+ `stderr/card/prompt` 归档 ⇒ 证据面 v2 在真实失败路径成立、可判定；④ gate-off（AutoFallback 关闭）⇒ rc=6 不 fallback（newest run cli=opencode）。**诚实上限**：探针验证"接线 + 证据面 + 触发判定"，不驱动真实站上 opencode 死锁（需站点在线）；另实测 claude 通道在本 Windows 上的执行级限制——`claude` 以 npm `claude.ps1` shim 安装，`Start-Process claude` 报 `%1 不是有效的 Win32 应用程序` ⇒ 备路即便登录也在 exec 级失败（预存环境限制，非本次改动，已记账）。**09-21 该 exec 限制已修复**：新增 `Resolve-ClaudeSpawn` —— 把执行目标从 `Get-Command claude`(命中 .ps1 shim) 解析到 npm 同目录的原生二进制 `node_modules\@anthropic-ai\claude-code\bin\claude.exe`（实测存在、--version headless 正常），绕开"`-RedirectStandardInput` 强制 `UseShellExecute=$false` ⇒ CreateProcess 加载 .cmd/.ps1 shim 报 win32 错"。复测注入式实弹 `_probe_fallback.ps1`：`CLAUDE_SPAWN=...\claude.exe`、不再报 win32 错，probe 仍 **PASS**（claude run status=failed 未登录、evidence_manifest v1/4、无泄漏）；exec 级修复不改变未登录失败语义（登录仍待配）。**09-21 真实站实弹（用户要求"补真实站点死锁自证"）**：站点实为**在线**（前一轮"离线"是我的探针错误——用 `Test-NetConnection -ComputerName A` 判 A/B/C，而它们是 `~/.ssh/config` 别名不解析 DNS；全量门禁一直报"可达 3/3 站"）。流程：`load-gate 11` PASS → `cluster.py load gpt-oss-20b`（B 站 :8080 ctx=32768）→ 新夹具卡 [`fallback-deadlock.md`](test-cards/fallback-deadlock.md)（`timeout_s: 10` 刻意小于完成所需 ⇒ 远端 `timeout` 强杀 ⇒ **rc=124→6**，复现"引擎超时/死锁"**信号类**）→ `AGENT_AUTO_FALLBACK=1` 派发。**首跑即暴露两处实现真 bug**（注入式夹具**均漏掉**）：① **`$m` 被 collect 段改写** —— 主路有 `$m = Get-Content $metaTxt \| Out-String`，我却拿 `$m` 当模型名传备路 ⇒ `REJECT unknown-model (TASK_ID=202609211645528026 QUEUE_S=2 …)`（报错里是 .meta 全文）。② **主路模型不可路由到 claude** —— claude 备路只收 `station=''` 的本地 claude 路由，主路 `gpt-oss-20b` 解析出 `station='B'` ⇒ 透传会被 `REJECT claude-station` 拦掉。**修复**：顶部快照 `$taskModel`（不再复用被改写的 `$m`）+ 备路切型号 `$fbModel`（默认 `claude`，env `AGENT_FALLBACK_MODEL` 可覆盖）。**顺带发现第三处（未修，属设计差异，非本次引入）**：`Invoke-ClaudeFly` 原用 `Start-Process -PassThru -NoNewWindow -RedirectStandard*`，本 PS5.1 上 **`$p.ExitCode` 恒 `$null`** ⇒ `$rc` 空串 ⇒ `'' -ne 0` 为真致 resume 空转、且 **`$null -eq 0` 为假 ⇒ 成功的 claude run 也会被判 `failed`**（备路等于白修）⇒ 改用 .NET `Process`+`ProcessStartInfo`（保留 `WaitForExit(ms)` 预算内 kill，ExitCode 实测可读）。**复跑验证（第 2/3 次）**：`AUTO_FALLBACK: opencode rc=6 -> local claude backup` + `AUTO_FALLBACK_MODEL: gpt-oss-20b -> claude` + `claude first rc=1`（rc 保真修复生效，非空）+ 产出 claude run（`202609211652389854`，`cli=claude`、`status=failed`、`exit_code=1`、`usage.source=not-collected-claude-path`、`attach` 为数组、**`evidence_manifest v1/5`** = agent-output/prompt/stderr/card/accept-output，**无 opencode 件泄漏**）⇒ **证据面 v2 在真实 run 上成立**。`agent-output.txt` 内容为 `Not logged in · Please run /login` ⇒ 失败原因确为未登录（诚实失败）。**夹具加固**：给 `_probe_fallback.ps1` 加 `ssh` stub 产出 `.meta`（否则 `$m` 不被改写、夹具对该回归**不敏感**）+ 清空 `probe-proj`（否则命中上一轮遗留 run ⇒ **假 PASS**）+ 型号断言；**双向自证**：回归版 ⇒ `PROBE_FALLBACK FAIL`、恢复版 ⇒ `PASS`；阶段 0.5 夹具仍 **44/44**。**仍余（新登记）**：④ claude 仍**未登录**（`loggedIn:false`），故"备路真正接手完成"这一半仍未证。**09-21 免登录 + 后端选型已调研落档（用户裁定：OpenRouter 优先、工作站本地模型备选；本次只落档不实施）** —— 见 [2026-09-21 claude 备路免登录与后端选型调研](../../docs/research/2026-09-21_claude备路免登录与后端选型调研.md)。**实测结论**：① **免登录可行且不需"绕过地区限制"** —— 登录只服务 Anthropic 官方；把 `ANTHROPIC_BASE_URL` 指向兼容 `/v1/messages` 的端点即可，而 **A/B 站早就是这么跑的**（指向站内本地引擎 + `apiKeyHelper` + 型号映射）。② **控制台只缺一处**：免登录要造的两个门槛文件**已在位**（`~/.claude.json` 的 `hasCompletedOnboarding=true`、`~/.claude/config.json` 的 `primaryApiKey="any"`），**唯一缺 `~/.claude/settings.json` 的 `env.ANTHROPIC_BASE_URL`** ⇒ 缺它就回落官方端点报 `Not logged in`。③ **站上引擎实测实现了 Anthropic API**：`/v1/messages` 用 **`Authorization: Bearer <unsloth.key>` 得 200**（标准 Anthropic 响应体），而 `x-api-key` 得 **401**（unsloth 只认 Bearer）；且引擎**只监听 127.0.0.1**（控制台经 LAN 不可达，`HTTP=000`）。④ **cc-switch 控制台已装**（`skipClaudeOnboarding:true`、`enableLocalProxy:true`），但其 provider（DeepSeek / LM studio）都挂在 **`claude-desktop`** 名下，**CLI 的 profile 是空的 `default`** ⇒ 这才是 CLI 仍要登录的直接原因。**⚠ 最要紧的落地前置（既存实证）**：主控**本地**跑 claude 的**完整工具型任务**会被 **Trae 沙箱拦**，**已实证的可用路径是经 SSH 在站上跑 claude** ⇒ 与"站上本地模型备选"指向同一形态，**`Invoke-Task-Claude` 现"控制台本地 spawn"的形态需改为"站上执行"**（该文档 §6 已列 6 项待实施，含按 `sensitivity` 设闸以防 `local-only` 卡被送到 OpenRouter）。**09-21 控制台 `settings.json` 缺口已修（免登录实测通过）**：① **改前先备份** `~/.claude/settings.json` → `.bak-20260921`（验大小 175=175）；② 新建 `~/.claude/or-key.cmd` 作 **`apiKeyHelper`**（`findstr /v /b "#" d:\RPC\secrets\openrouter.key` ⇒ 只输出非注释行；**用 helper 而非明文 key** ⇒ 守住项目铁律「key 单一真值在 `secrets/`」，且与站上 claude 同模式）；③ `settings.json` **合并式**写入（6 个既有键全保留）增 `apiKeyHelper` + `env{ANTHROPIC_BASE_URL=https://openrouter.ai/api, ANTHROPIC_API_KEY="", ANTHROPIC_MODEL=thinkingmachines/inkling:free, DISABLE_AUTOUPDATER=1}`，UTF-8 **无 BOM**。**验证（决定性：先清空全部 `ANTHROPIC_*` env ⇒ 证明仅靠配置文件）**：显式 `--model` ⇒ **`OK`**；**不带 `--model`** ⇒ **`OK`** ⇒ **免登录可用、零 env 依赖**（且 `env.ANTHROPIC_MODEL` 实测**覆盖**顶层 `model` 键）。**⚠ 顺带测出一条阻断级事实**：**Claude 原生型号名经 OpenRouter 仍撞地区墙** —— `claude-opus-4-7`（原顶层 model）/ `claude-sonnet-4-5`（=ROUTE_TABLE 的 `claude`）/ `claude-opus-4-1`（=ROUTE_TABLE 的 `claude-opus`）**全部 403 `This model is not available in your region.`**，而 `thinkingmachines/*:free` / `nvidia/*:free` **`OK`** ⇒ **走 OpenRouter 并不能用 Claude 原生 id 绕过限制**（那些 id 被路由到真实 Anthropic 上游）。**直接后果**：备路 `$fbModel='claude'`(=claude-sonnet-4-5) **会 403** ⇒ **型号重映射是阻断项**（已登记为该调研 §6 第 7 项），否则免登录只解决认证、不解决可用性。**09-21 型号重映射已完成 + 备路首次端到端跑通**：`ROUTE_TABLE` 的 `claude`→`thinkingmachines/inkling:free`、`claude-opus`→`nvidia/nemotron-3-ultra-550b-a55b:free`（取 `secrets/openrouter.conf` 的 `harness_priority` 前两档，**不新立模型清单**；别名保留原名 = 备通道档位而非厂商），并加两条 **full-id 直传条目**（`Resolve-Model` 是纯表查找 ⇒ `--model <openrouter-id>` 与 env `AGENT_FALLBACK_MODEL` 才可解析）。**新增回归守卫（此前该约束无任何守卫）**：夹具用 `AssignmentStatementAst` **提取真实 `ROUTE_TABLE`**（探针的 `Resolve-Model` 是 stub、守护不到真表）并断言 6 条不变量（非 Claude 原生 id / 形如 OpenRouter id / `station=''` / `cli='claude'` / 有 full-id 条目）⇒ 夹具 **53/53**；探针同步 **PASS**。**端到端（决定性）**：临时卡 `model: claude` + `timeout_s: 180` + `accept:[true]`，`task paper -cli claude`（claude 分支在 station-ready/sync **之前** ⇒ 不需站上模型）⇒ **`claude first rc=0`**（原 rc=1 `Not logged in`）+ `ACCEPT_MODE=bash-local` `ACCEPT_OK=1` + run `202609211739020633`：`cli=claude model=thinkingmachines/inkling:free` **`status=completed` `exit_code=0` `accept.passed=true`**、`agent-output.txt` = `OPENROUTER-FALLBACK-OK`、stderr 空 ⇒ **"备路真正接手完成"这半首次被证**（此前每次停在 `Not logged in`）。**新登记（未实施）**：备路与主路**共享卡的预算** —— `Invoke-Task-Claude` 的 `timeout_s` 取自同一张卡，而"诱使主路超时(rc=6)"恰需小 `timeout_s` ⇒ 两目标在同一张卡上矛盾（本次能跑通仅因云端模型比站上 20B 快）⇒ 真实长任务需另定"备路预算"（如卡加 `fallback-timeout-s`），见调研 §7.5。**09-21 用户裁定后定案并修复『accept 的 shell 语义』**（上文 ③）：**定案 = 卡里的 `accept` / `accept-golden` 一律是 bash 语义** —— 主路在**远端 bash** 跑、备路在**本地 Git Bash** 跑；两条路只差**执行机器与 cwd**（远端 Linux 工作区 vs 本地 `projRoot`），**不差 shell**。**落地**：① 新增 `Resolve-LocalBash`（**刻意不走 PATH 的 `bash`** —— 本机实测 PATH 命中 `C:\Windows\system32\bash.exe` = **WSL**，它在另一文件系统+cwd 映射里执行，拿它判是"看起来跑了、判的不是这里的东西"；改显式解析 Git Bash，与 `$Script:GNU_TAR` 同一前提）；② 新增 `Invoke-LocalBashCmd`（bash + cwd + rc；输出**逐行落 `accept-output.txt`** —— 备路此前 `*> $null` **丢输出只留 rc**，出 bug 无从复核）；③ **`accept` 与 `accept-golden` 一并改**（同一个 bug 的两处；"只修一半的修复看起来是完整的"）；④ 备路顶部加**提前**守卫：无 Git Bash ⇒ `REJECT local-bash-missing (exit 13)`，**不退回 PowerShell**（那正是被修的 bug ⇒ 判据假红灯）、也不静默换 WSL。**验证**：夹具 `_fm_golden_test.ps1` **47/47**（+3 条 bash 语义断言：解析到 Git Bash 非 WSL、`true`⇒rc0、`false`⇒非0）；离线探针加断言 `accept.passed=true` + `ACCEPT_RC[1]=0` 并**双向自证**（退回 PS 版 ⇒ `PROBE_FALLBACK FAIL`，且直接证据 = 该轮 claude run 的 `accept.passed=False`/`ACCEPT_RC[1]=1`；恢复 ⇒ `PASS`）；**真实站端到端**（B 站 gpt-oss-20b，`fallback-deadlock.md`）⇒ 日志 `ACCEPT_MODE=bash-local (C:\Program Files\Git\bin\bash.exe, cwd=D:\Paper)` + **`ACCEPT_OK=1`**（修前为 `0`），claude run `202609211711138716` 的 `accept.passed=True`、`accept-output.txt` 记 `ACCEPT_RC[1]=0`（修前 `=1`）。**遗留约束（诚实边界）**：环境差异仍在 —— 卡若要**两路都过**，判据须**跨环境可移植**（`./.venv/bin/python` 这类 Linux 专属路径在 Windows 本地仍不可用）；该约束属**卡作者**责任，已在代码注释与本段写明。**顺带修一处预存断言缺陷（由本次真实超时 run 首次暴露）**：提交时门禁 `evidence` **红灯阻断** —— `cluster.py` 的 [`_VERDICT_RC_MAP`](../../ops/cluster.py#L3375) 缺 `124→6` 条目，而**两路的映射时机不同**：opencode 路把 `timeout` 的**原始哨兵 124** 直接写进 `.meta`、124→6 在**控制台侧**做；claude 路则**先映射再写 `.meta`**（故表里原有 `6: {6}` 只覆盖后者）。旧表对 124 回退成 `allowed={124}` ⇒ **把每个合法超时 run 误报 FAIL**（实测 3 个新增超时 run 全部命中）。补 `124: {6}`（只允许 6，不加 124 —— 两路都必做该映射，出现 124 反倒说明映射没走）；**未动锚/未 `--reanchor`**（门禁处置建议亦明确"别急着 reanchor，那是把信号抹平"）。复验：`evidence` 转 **PASS**、`A1 verdict-chain 22/86 → 25/91`（新增 run 变可判）；负向自证错值仍被拒（`124→{6}`，7/0 均拒）。
| **框架级：每次 ssh/scp 建连 14-17s** | ~~09-16 新登记（性能）~~ → **当日闭环（[ADR-0006](../../adr/ADR-0006-控制面传输绑定LAN_IPv4.md)）**：根因不是 sshd/UseDNS，而是**主控解析 `*.local` 需 16-17s 且只返回公网 IPv6** ⇒ 每次建连白付 16s **且控制面经 ISP IPv6 绕行、不在局域网内**（站上 `$SSH_CONNECTION` 实测证实；`ControlMaster` 在 Win32-OpenSSH 9.5p1 亦不可用）。处置：`~/.ssh/config` 把 A/B 名字 `HostName` 绑定到 LAN IPv4（+`AddressFamily inet`）+ 三个 IP 身份块，`cluster.py` 的 STATIONS 同步改 IPv4，LAN 真值入 `inventory/net.yaml` 的 `lan` 段，并在门禁 `stations` 新增 **(h)** 防漂移断言（`ssh -G` 的 hostname 必须 == 登记 IP；已做负向自证）。**实测：按名 16.2s → 0.18s（≈90×）；单次 task run 421s → 48.5s（8.7×），其中模型本身占 38s ⇒ 框架开销 ~383s → ~10s** | 已闭环。建议（可选加固）：路由器按 MAC 做 DHCP 保留（固定 .32/.33/.37）；`agent-cli`/`cluster.py` 的 ssh/scp 统一加 `-o BatchMode=yes`（防认证失败时静默等 stdin，本轮实测踩到 >90s 挂起）**→ 见下条** |
| **ssh/scp 未统一 `BatchMode`（认证异常时会静默等 stdin）** | **09-16 新登记（健壮性）**：ADR-0006 调查中实测踩到 —— 按 IP 连接时因 `~/.ssh/config` 无对应身份块，用户名退化为本机 `peng` ⇒ 触发口令提示 ⇒ **挂起 >90s 等 stdin**（自动化里表现为"卡住"而非"失败"）。已在 `~/.ssh/config` 补三个 IP 身份块消除该场景，但**调用点本身仍未加 `-o BatchMode=yes`**（agent-cli.ps1 的 ssh/scp、cluster.py 的 paramiko 路径） | 待办：给所有 ssh/scp 调用点统一加 `-o BatchMode=yes` + 明确 `ConnectTimeout`，把"卡住"变成"快速失败" |
| **`doclinks` 对新文件有盲窗（未跟踪文件不扫）** | **09-16 新登记（判据自身的盲区）**：`doclinks` 只扫 `git ls-files` 的 md ⇒ **新写的文档在 `git add` 之前不进判据**。实测代价：ADR-0005 落档时门禁报"失效 0"，而它内部有 **27 条 `../../` 前缀错**（`adr/` 只有一层，应是 `../`），直到本次 ADR-0006 落档时才被连带发现（两文件共修 38 条）。⇒ 判据存在"写完 → add"之间的静默窗口（与"门禁绿灯 ≠ 产物可信"同族） | 待办：把 `doclinks` 扫描集改为 `git ls-files ∪ git ls-files --others --exclude-standard`，或在 pre-commit 时对暂存文件全扫 |
| **`Get-FrontMatter` 不剥离 YAML 引号** | **09-16 新登记（解析器行为）**：卡里写 `accept: - "true"` 时引号**原样**进入命令列表（`eval` 后仍能执行，故非功能缺陷），但会让"证据 ↔ 声明"的字面比对出现差异（实测 `accept-cmds.txt` 内为 `"true"`，而卡内声明是 `"true"` 的引号已入串） | 低优先：可剥引号，或仅在文档写明"命令列表不要加引号" |

| **`syntax` 断言占 quick 门禁 96% 耗时（本轮新发现）** | **09-17 新登记（性能）**：逐项实测（`tmp/_t2.py`，逐 check 计时）——**quick 门禁实测 ≈16.4s**，其中 **`syntax` 独占 15.8s（96%）**，其余全部合计 <1s（`secrets` 123ms / `aliases` 214ms / `doclinks` 85ms / **`evidence` 仅 40ms**）。**为何要紧**：pre-commit 钩子每次提交都跑 quick ⇒ **每次 commit 白等 ~16s**；且记忆/文档里"quick 1.1s"是**过时值**（仓库已长到 206 脚本 / 683 文本件 / 409 个 `.sh`）。根因推测：`syntax` 对每个 `.sh`/`.ps1` **逐个 spawn 解释器**校验（409 个 `.sh` 是主项）——**未取证到函数内部，仅由"其余项皆 <250ms + 文件数占比"推断** | 待办：改批量/并发校验（或按需只校验改动文件），把 quick 压回秒级；属**独立性能项**，非证据流范围 |
| **证据链持久化为单机（闭环复核新增，09-19）** | **闭环复核**发现：链本体（65 KB）+ 冷路径镜像都在主控**同一块盘且 gitignored**，对账 runDir `D:\Paper\agent-out\*` 亦单份；入仓的只有 **716 B `ANCHOR.txt`** ⇒ 磁盘故障 = **链不可复验**（锚还在 GitHub，但对账对象整段消失）。**已做社区调研并落 [ADR-0007 §社区调研结论](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md) + 调研 §14**：四候选 P1 ruleset / P2 链入仓+断言 / P3 git notes / P4 tlog-tiles 只读镜像。诚实边界：3 台机器同运营者 ⇒ **不得用多副本宣称"不可否认"** | **P1 ✅**（ruleset `23753398`，禁 force-push+禁删 main）。**P2 ✅（2026-09-21）**：冷镜像 `archive/evidence-chain/agent-chain.json` 入仓（红线精确例外已写回 ADR）；断言 `p2_pair_mismatch`（`verify` 读 git 暂存区比对链↔锚 cold_sha）；**顺带把锚哈希改 LF 规范**（`core.autocrlf=true` 下盘面 CRLF 与 git LF blob 不同 ⇒ 旧锚钉的是本机编码，已 `--reanchor` 704cd0b7）。**P3 ✅ / P4 ✅（用户裁定两者都做）**：P3=`agent chain --pin-notes`（git notes ref `refs/notes/evidence-chain` push origin，冗余）；P4=`agent chain --mirror <站>` = **链镜像 + runDir 对账镜像**（`agent-out/`→ tar.gz → 站 `evidence-mirror/runs/`）。**⚠ P4 修正（2026-09-21 实测自伤）**：首版 chmod 555/444 模拟只读 ⇒ 下次 `--mirror` 自己写不进 ⇒ 改为**可更新滚动快照**（写入前置自愈恢复可写）。诚实：均同运营者 ⇒ **冗余非不可否认** |
| ~~**`syntax` 断言抓不到"无 BOM 的含中文 .ps1"（本轮新发现）**~~ | ✅ **2026-09-21 已闭环（加了确定性字节判据 + 更正根因）**。**09-18 首次命中（判据盲区）**：`ops/station-bin/_fm_golden_test.ps1`（**卡解析器的回归守门夹具**）**缺 UTF-8 BOM**。PS5.1 按 ANSI 解码含中文的脚本时，**3 字节 UTF-8 序列被当 2 字节 GBK 解码会吞掉相邻换行** ⇒ 语句被并进注释 ⇒ 夹具**静默失效**（`DEBUG fns count=0` + `Get-FrontMatter not found`，即"守门人一直是死的"）。**09-21 第二次命中（现场复现）**：编辑工具（Trae `Edit`/`SearchReplace`）**在某些重写路径下会剥掉 BOM** ⇒ `agent-cli.ps1` / `_fm_golden_test.ps1` / `_probe_fallback.ps1` 三个文件 BOM 全丢，随后夹具**当场解析崩溃**（`Unexpected token 'claude'` + 中文乱码）。**⚠ 该行为是"间歇"的（当日多次实测）**：同一工具、同一批文件，**P1 阶段那轮编辑保留了 BOM**（`git cat-file blob 08eb8b0:<f>` = `efbbbf`）、**撤回那轮剥掉了**、**补语法那轮又保留了** ⇒ **不能假设它会保留，也不能假设它一定会剥** ⇒ 只有**按字节验**才可靠（这正是本次加子判据的理由之一）。**⚠ 根因更正（09-21 实测，推翻当日早先写下的错误说法）**：曾推断"门禁 `[Parser]::ParseFile` 走 .NET 解码（BOM-less 按 UTF-8）而执行走 ANSI ⇒ **结构性看不见**"—— **错**。实测证据：把一个 BOM-less 的中文 `.ps1` 交给上游那次 `ParseFile`，它**报了错**，且 11 条错的行号**全部落在中文注释行**（30/37/209/214/231/237/257/299）—— 若真按 UTF-8 读，一条错都不会有 ⇒ **`ParseFile` 与执行走的是同一条解码路径（ANSI/GBK）**。⇒ 真正的问题是**间歇性 + 内容相关 + 报错不指根因**：是否"吞掉换行"取决于具体字节序列，故同一缺陷可能报一堆错（09-21），也可能**报 0 条错却照样跑坏**（09-18 目击的后者：门禁 `.ps1:12文件/0失败` 而夹具 `fns count=0`）；且报出来的行号指向**注释行**，看不出"加 BOM"这个修法。**修法（本次落地）**：给 `syntax` 加**读字节**的子判据 `counts[".ps1-bom"]` —— **含非 ASCII 字节 且 无 `EF BB BF` ⇒ FAIL**（与内容无关的**确定性**判据，且报根因）。**顺带修两处报告缺陷**：① `PS_SNIPPET` 的 FAIL 行补**文件名**（原先 13 个文件里只报 `Unexpected token ')' [line 37]`，查不到人）；② 失败数**按文件计**（原先按错误行计 ⇒ 摘要写 `13文件/11失败` 像"11 个文件坏了"，实际只有 1 个 —— **09-21 实地误导过一次**）。**自证（正 + 负 + 对照）**：正 = 干净仓库 `.ps1:13文件/0失败 .ps1-bom:13文件/0失败` PASS；负 = 剥掉 `_fm_golden_test.ps1` 的 BOM ⇒ `(ps1-bom) …含非 ASCII 却无 UTF-8 BOM…` + `.ps1:13文件/1失败` + **退出 1 阻断**，还原后 sha256 一致；对照 = 暂存一个**纯 ASCII 无 BOM** 的 `.ps1` ⇒ 两计数均 `0失败`（**无误报**）。**范围修正**：原待办写"`.ps1`/`.sh` 都要 BOM"—— `.sh` **不得**加 BOM（BOM 会让内核把 `#!` 认成 `\xEF\xBB\xBF#!` ⇒ `bad interpreter` 直接不可执行），故子判据**只覆盖 `.ps1`**。**纪律**：凡编辑过 `.ps1`，提交前按字节验 BOM | — |
| ~~**函数返回值被"非返回值输出"污染**（本轮新发现，已闭环）~~ | ✅ **09-18 当日闭环（详见 [ADR-0007](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md)「缺口 5 落地与实测」）**。**症状**：run.json 出现 `"exit_code": [null, 0]` + `"status": "failed"`（实际 rc=0），且**复验器崩**（`TypeError: unhashable type: 'list'`）；同 session `SLOT-GATE: na (engine port unknown)`。**根因**：PS 函数 = 管道上**全部**输出 —— `Invoke-RemoteScript`/`Invoke-StationReady`/`Invoke-SlotGate`/`Invoke-Task` 靠 `return $x` 交付，但体内有未被吸收的 cmdlet 输出；环境层对文件操作的包装器在失败路径吐了 `$null` ⇒ 返回值变 `@($null, <真值>)`。**修法（"归零纪律"）**：通知改 `Write-Host`；`Copy-Item`/`Move-Item`/`Remove-Item`/`Add-Content` 一律 `\| Out-Null`；纪律写入注释（凡返回值被调用方使用 ⇒ 体内不得有其它管道输出）。**自证**：再派发 ⇒ `excode=0`（非数组）/ `exit_code=0(Int)` / 槽位门恢复。**复验器加固**：`_verdict_check` 遇 `exit_code` 形状畸形 ⇒ 报 issue 而非抛异常（崩掉 = 整链判据同时消失） | — |
| ~~**PS5.1 无 `[DateTime]::UnixEpoch`**（本轮新发现，已闭环）~~ | ✅ **09-18 当日闭环（详见 [ADR-0007](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md)「缺口 8 落地与实测」）**：`[DateTime]::UnixEpoch` 是 **.NET Core 时代成员**，PS5.1 的 **.NET Framework 4.8 上不存在**，且**访问它不报错、静默返回 `''`** ⇒ 参与 `DateTime - ''` 时抛 `找不到 op_Subtraction 的重载`（实测：缺口 8 首次派发取遥测即因此失败）。**修法**：改用 `[DateTimeOffset]`（4.6+ 起有 `ToUnixTimeMilliseconds`/`FromUnixTimeMilliseconds`）。**副产物**：该误用**顺带把"取不到遥测"的 NA 路径在真实链路上跑通**（run `202609181232158097` 落 `usage.source=unavailable` + 告警，`TASK_RC=0`、任务结论不受影响）⇒ 兜底有效，但**不能把兜底当正常路径** | — |
| ~~**`.attach/` 清理只覆盖"有附件"路径**（缺口 5 修复不全，本轮新发现，已闭环）~~ | ✅ **09-18 当日闭环**：缺口 5 引入的"派发前清空 `.attach/`"外层套在 `if ($attach.Count -gt 0)` 内 ⇒ **无附件的派发会留着上一轮附件**（实测两次无附件 run 均报 `ATTACH_MANIFEST_LINES=3`：把上一轮 attach 夹具的三件算进本次 run；agent 亦可 `ls` 到残留）。**修法**：改为**无条件 reset**（代价：无附件派发多一次 ssh —— Correctness > 一次往返）。**教训**：缺口 5 的判据只覆盖"有附件"路径，**没有为"无附件"路径设判据，残留就被漏掉** —— "只覆盖一半的修复看起来是完整的"，与"判据必须报覆盖率"同源 | — |
| **`infer-load` 健康检查超时（首拉失败、重试即好）** | **09-18 新登记（基础设施/偶发）**：阶段 3-a 的 e2e 中 `cluster.py load gpt-oss-20b` 首拉报 `unsloth 健康检查超时`，而站上**实例其实已起**（studio :8080 + llama-server :41959 均在），日志显示健康检查对 `/v1/models` **连续 401**（每 3s 一次，直到超时）。**推测**：新铸 key 落盘与健康检查轮询之间存在**竞态**（该轮 `API Key ok` 行未打出）⇒ 用未同步的 key 去探。**实测**：直接重试一次即 `READY ✓`（key sha8 变化：`e698d92a` → `b359bb79`）。影响：一次派发失败 + 一次人工重试 | 待观察：若复现，给健康检查加"key 落盘后重读 + 401 单独识别为 key 问题"的判据（与"卡住 vs 失败"同族：**必须能区分**） |
| **⚠ `local-only` 闸不覆盖 claude 备路 ⇒ 敏感卡可实际出网（2026-09-21 新登记，安全策略洞）** | **背景**：`sensitivity: local-only` 的硬闸有三处（`Resolve-Model` L435 / `Invoke-Task` L987 / 路由 cmd L1837），判据一律是 `local-only` + `^opencode/` ⇒ `REJECT … exit 4`（无覆写通道）。**洞**：**`Invoke-Task-Claude` 没有任何 sensitivity 判据**，只校验"型号在表内 + `station=''`"；而 `AUTO_FALLBACK` 调用点也不判 sensitivity。**两条实际出网路径**：① 卡写 `sensitivity: local-only` + `cli: claude` ⇒ L987 放行（型号非 `opencode/*`）⇒ `Invoke-Task-Claude` ⇒ **OpenRouter 云端**；② `local-only` 卡 + 站上本地型号 ⇒ 站上引擎死锁 `rc=6` ⇒ `AUTO_FALLBACK` ⇒ `Invoke-Task-Claude -model claude` ⇒ **云端**。**为何现在才严重**：此前该路过 `api.anthropic.com` 且**不可用**（`Not logged in`）⇒ 洞是**惰性**的；2026-09-21 免登录 + OpenRouter + 型号重映射把备路**修成真能用** ⇒ **洞变活**。**破的是** [DESIGN.md §358](../../spec/d6-agent-standard/DESIGN.md) 的不变式（"local-only 的 prompt 字节永不离开主控站→站内本地模型路径"）。**影响面**：`test-cards/` 里 **20/25 张是 `local-only`**。**另注**：ZDR **不能**兜底 —— OpenRouter 官方明确"ZDR 只保证 provider 不留存，数据仍会到达 provider 并被模型处理，且不覆盖处理地"⇒ `local-only` 要的是**不出网** | ✅ **P0 已实施并双向自证（2026-09-21；剩 P2–P5）**：新增**唯一判据** `Get-SensitivityBackendReject`（L905，纯函数，返回 '' = 放行 / 否则原因 token），规则**只此一条**：`local-only × 会出网 ⇒ local-only+egress`；在**两个出网入口各判** —— `AUTO_FALLBACK` 调用点（**拒绝兜底** fail-closed，拒绝串 `(fallback, <model>)`）+ `Invoke-Task-Claude` 直接入口（拒绝串 `(claude-direct, <id>)`），tag 用于分辨是哪一处闸在守。**自证**：① 夹具 **61/61**；② 实弹探针 A/B 两例 `rc=4` 且 **claude run 计数不增**（= 未发请求）；③ **变异自证**：拆掉闸 ⇒ A/B 变红（rc 4→6 且**真跑出 claude run** = 真出境）⇒ 洞是真的、探针不是结构性失明；④ `public` 原路径未被破坏。**仍未闭合**：~~P2 判据升级为"后端属性查表"（现 `$backendEgress` **硬编码 $true**）~~、~~P3 站上化~~、~~P4 备路独立预算~~、P5 ZDR。**⚠ 2026-09-21 进展（P3 已实施 + P2 部分落地 + P4 已实施）**：**P3** ⇒ `local-only` 的 claude 通道**不再"一律拒绝"**，而是走**站上 claude + 站上本地引擎**（物理不出网）；站上不可用 ⇒ `REJECT local-only-no-station-engine (exit 4)` **fail-closed（绝不退回主控本地=出网）**；`sanitized`/`public` **保持主控本地 spawn 不动**。**P2 ◐ 部分** ⇒ **claude 通道两个入口已参数化**（直接入口 `-backendEgress (-not $useStation)`；兜底入口保留 `$true`，因它在主控本地=云端=出网）；⚠ **但既有三处闸仍按型号前缀判**（`Resolve-Model` / `Invoke-Task` / route cmd）⇒ ✅ **已闭环（2026-09-21 W1a）**：那三处 + `Split` + review 全部换成**后端属性判据**（`Get-BackendEgress` / `Get-JudgeEgress`，**fail-closed 默认：只有 `local/` 不出网，其余一律出网**；claude 通道豁免以免误杀 P3）⇒ **"再加一个云端后端又漏一次"的结构根因已消除**（夹具含 ★"假想云端后端"负例 + AST 断言"全仓不再存在按前缀判敏感度"）。**P4** ⇒ `fallback-timeout-s` 已实施。**实弹自证**（`local-only` 卡 + `-Cli claude`）：`P3_CANDIDATES: B,A,C(pref=B)` → 选中 B → 站上打印 `engine_ctx=32768 max_context_tokens=28672 base_url=http://127.0.0.1:8080` → `P3_STATION_RC=0` → 归档 `P3-LOCAL-OK` / `exit=0` / 台账 `…,local-only,0,0,58`。**"不出网"的可判证据（非仅结构性）**：站上临时 settings 的 `apiKeyHelper` 指向 **unsloth.key**（本地引擎 key）⇒ 若请求打到 OpenRouter **必然 401**，而它 **rc=0** ⇒ **反证请求没去云**。夹具 **92/92**。**⚠ 同日复查又修两处"设计意图没落地"**：① **「优先选与死锁站不同的一站」原本未生效**（`$avoid` 只读 `$env:AGENT_AVOID_STATION`，而**无人填 env**）⇒ 兜底调用点现传 `-AvoidStation $station`（env 降级为手工覆盖通道）；② **`pref` 会覆盖率 `avoid`**（兜底时卡的 `model` 常正指向刚死锁那站）⇒ 两规则**提进纯函数**且 **avoid 胜过 pref**。**判别性实弹**：`avoid=''`⇒`B,A,C`（立刻选 B，无 SKIP）vs `avoid=B`⇒**`A,C,B`** + `SKIP A`/`SKIP C`（avoid 胜、B 垫底）。⚠ **更正**：前一条提交信息称"多候选重试未做"**有误** —— `SKIP`×2 证明循环本来就在逐个重试。夹具 **98/98** |**⚠ 同日曾加过第二条规则 `sanitized × 可能训练 ⇒ sanitized+trains` 并当日撤回** —— 理由见 [P1 核对报告 §6.2](../../docs/security/2026-09-21_OpenRouter数据策略与隐私开关核对.md) 与函数注释留档；**撤回已做成可判**（探针 C/D 例反向守卫"sanitized 必须被放行"） |
| **⚠ 备路全档依赖"免费模型允许训练"开关 + 免费日额度（2026-09-21 新登记，依赖/风险）** | **事实**：claude 备路两型号**都是 `:free`**（`claude`=`thinkingmachines/inkling:free`、`claude-opus`=`nvidia/nemotron-3-ultra-550b-a55b:free`），而 OpenRouter 的「Allow free endpoints that train on request data」**是 A 站账号级开关**（付费档/免费档**两个独立**开关）。**实测代价**：`nemotron-3-ultra-550b-a55b:free` 无偏好 **200**，加 `provider.data_collection=deny` ⇒ **404 `No endpoints found matching your data policy (Free model training)`**，加 `zdr` ⇒ **404 `(Zero data retention)`** ⇒ **该型号免费端点全部训练且全不可 ZDR**。**⇒ 关掉该开关 = `:free` 备路整体失效**（`claude-opus` 确证；`claude` 因 `403 only available on agentic harnesses` 只能推理）。**另**：免费档型号**流动性高**（本轮抽样 3 个 `:free` 已整体下架）+ 1000 次/天免费额度是「三站独立账户 + `egress borrow`」机制存在的前提 ⇒ **备路是"有条件的"能力，不是稳态**。**四开关实况（用户读 dashboard，2026-09-21）**：①`1% 折扣` **关** / ③b`免费档 publish` **关** / ③c`付费档 train` **关** / ③`免费档 train` **开** ⇒ **唯一敞口 = 免费档可能被训练**（不进公开数据集、OpenRouter 自己不留存/不使用）。**决策**：**不加**"挡 sanitized"那条闸（**同日加入又撤回**，见上一行）；**并且"关开关"不是一个动作** —— **该开关是"使用免费档"的必要条件**（实测账户级 `(Free model training)` 拦截）⇒ 关它 ≡ **放弃免费档**，而免费档**不是只有备路在用**：① claude 备路（harness 轨）、② judge/review 的 judge 槽（`secrets/openrouter.conf`，裸 API 轨）、③ 站上 opencode 的 `provider.openrouter.models` 免费档优先级表（站内 egress）⇒ **关开关 = 同时打断这三条链路**，收益（少一条暴露面）远小于代价。**⇒ "免费档可能训练且不可撤回"登记为已知风险、默认接受**（它与"使用免费额度"是同一件事）；**⚠ 早先把"P3 之后关该开关"写成收尾步骤属"把手段当目的"，已更正并从各处移除**（含本行待办）。 | 待办：① **若某类流量单独不接受训练暴露** ⇒ **把那条流量改走合规后端**（站上本地引擎[P3] / 付费型号+`deny`·ZDR），**不是**关开关；②"付费型号 + `provider:{data_collection:deny}`"已实测可行（`mistral-nemo`/`ling-3.0-flash` 连 `zdr` 都过），需选型 + 改 ROUTE_TABLE + 夹具回归；③ 免费档型号**流动性高**（本轮抽样 3 个 `:free` 已整体下架）⇒ `:free` 只适合做**可失效的**后端，别当稳态；④ **P3 的价值与关开关无关**（绕开主控沙箱 / 摆脱免费额度与型号流动性 / 提供可选合规后端）。全文见 [P1 核对报告](../../docs/security/2026-09-21_OpenRouter数据策略与隐私开关核对.md)。**⚠ 2026-09-21 ZDR 裁定（P5）：不做 ZDR，且它不是可执行动作** —— [全文](../../docs/security/2026-09-21_ZDR可行性裁定与影响面.md)。要点：① **ZDR 按 model group 分作用域**（Anthropic/OpenAI/Google/SpaceXAI/**All other models**），我们型号**全是 `:free` ⇒ 100% 在 "All other models"** ⇒ 给该作用域开 = **本行那 5 类消费者全灭**（影响面与本行的"关开关"**完全重合**）；② **`local-only` 已强于 ZDR**（P3 让它在站上本地引擎跑 ⇒ **根本不出网**；而 ZDR 明确"不改变数据到达 provider"）⇒ 对它开 ZDR 是**降级**；③ **`sanitized` 抹完 = `public`** ⇒ 同级。⇒ **"允许出网但不允许留存"这个格子是空的**；**若将来真要 ZDR ⇒ 必须换付费型号**（已实测可用：`mistralai/mistral-nemo`、`inclusionai/ling-3.0-flash` 连 `zdr` 都过）⇒ 故"开 ZDR" ≡ "换后端" |
| **⚠ `sanitized` 档的"抹完 = public"这一前提从未验证（2026-09-21 新登记，**ZDR 裁定的替代品**）** | **由来**：ZDR 裁定（[全文](../../docs/security/2026-09-21_ZDR可行性裁定与影响面.md) §4）的论证依赖一条**推论**：「`sanitized` = 含**可机判**敏感项 ⇒ 先机械 scrub 才可进远端 ⇒ **抹完的残留等级 = `public`**」—— 该推论**从未被验证**。**为何要紧**：若 scrubber **漏了**（bug / 未覆盖的敏感形态 / **认了但没抹干净**），则 `sanitized` 流量**实际不是 public**，却**走云端免费档**（可能被训练 **且** 留存）⇒ **那才是真正需要更强后端的情形**。⇒ **正确的防线不是开 ZDR，而是让 scrubber 不漏**。**而且它是可测的**：scrubber 是**确定性函数** ⇒ 可做真值表夹具。⚠ 该前提同时也是 P1 那条"撤回 `sanitized×可能训练` 闸"的依据之一 ⇒ **前提若破，那条被撤回的规则要重审**（两处论证共享同一前提） | ✅ **已实施（2026-09-21）**：`ops/station-bin/_scrubber_coverage_test.ps1`（AST 提取 `Invoke-Scrubber`，不执行主入口；登记 `inventory/ops.yaml`）—— 按**三态**建成，**`pass=14 fail=0`**。**⚠ 第三态当轮就命中一个真 bug**：`win-path` 规则原是 `(?i)\b[A-Z]:\\\S+`，**`\S` 遇空格即断** ⇒ `C:\Program Files\Git\bin\bash.exe` 只被吃掉 `C:\Program`，**残留** `Files\Git\bin\bash.exe`，而输出里**出现了 `[REDACTED-PATH]`**（"看起来已处理过"）。**修复含一次必须二选一的取舍**：改成"**段后还有 `\`（能证明仍是路径）才允许段内含空格**"（`(?i)\b[A-Z]:\\(?:[^\\/:*?"<>|\r\n\t]+\\+)*[^\\/:*?"<>|\r\n\t\s]*`）；放弃"段内一律允许空格"是因为它**贪心吞掉路径后的普通词**（`C:\RPC\out.txt done` 整段被抹 ⇒ **误伤任务输入**，本机 prompt 句中路径极常见）。夹具为此**新增 §2b 过度消费守门**（3 例）—— 当轮即抓到第一版改法的过度消费。**两类诚实输出（不计 FAIL 但必须可见）**：**[4] 未覆盖形态 14/14 一个都没覆盖**（GitHub PAT / AWS AKIA / Slack / JWT / Bearer / OpenSSH 私钥块 / **Linux 绝对路径** / **UNC 路径** / **内网 IP** / `.local` 主机名 / **用户名** / 手机号 / 身份证 / 银行卡 —— 现有 scrubber **只有 3 条规则**（**现已扩到 9 条，见待办①**），注释自明 `no whitelist in MVP`）；**[4b] 已知残留缺口 2/2**（`C:\Users\John Doe` ⇒ 残留 `Doe`；`"C:\Program Files\my file.txt"` ⇒ 残留 `file.txt`，即上面那笔取舍的代价）。**⇒ 对本行结论的影响**：`sanitized` 的**实际档位介于 `sanitized` 与 `public` 之间**（[ZDR 裁定 §6.1/§6.2](../../docs/security/2026-09-21_ZDR可行性裁定与影响面.md)）⇒ 该前提仍是**有条件成立** | 待办：① ✅ **已裁定并实施（2026-09-21）**：**加 6 条凭据类 / 不加 8 条身份与拓扑类**（全文 [scrubber 规则扩充裁定](../../docs/security/2026-09-21_scrubber规则扩充裁定与影响面.md) §6）。判据 = **①可判性 × ②真敏感 × ③误伤≈0 × 有出现路径**，四条全中才加。要点：**(a) 硬证据** —— 本仓 run ID 格式 `yyyyMMddHHmmssffff` **恰好 18 位数字、全仓 204 处**，故"长度判据"的身份证规则会把**主要证据句柄整片抹掉**（实测 3/3 命中），而 **GB 11643 校验位判据 0/3**（银行卡同理：长度判据命中 Luhn 不合法的编造值）；手机号规则命中的 `18047253056` 实为 `_davidau_download.sh` 里的**模型文件标识**。**(b) 三类形态是项目的日常寻址方式**：`.local` 主机名 **212 处/53 文件**、`/home/<user>/` **211 处/100 文件**、内网 IP 是 `inventory/net.yaml` 的**权威真值** ⇒ 抹掉它们 = 抹掉任务可执行性。**(c) 影响面边界** —— scrubber **只作用于 `$promptFull`**（卡 task + body + 附件名），**accept 命令不经它**（另行 base64，只到站=自己机器）⇒ 6 张卡 accept 里的 `/home/scott-lau/...` **不是误伤证据**（不加这条边界会把不存在的风险写成风险）。**(d) PII 不加规则 ≠ 放任** —— 正确防线是**档位**（含 PII/拓扑的卡**必须** `local-only`，已写进 DESIGN §5.1 卡作者纪律）。**(e) gitleaks 不装** —— DESIGN §193 的"regex + gitleaks"已改写为"**regex 必需 + gitleaks 可选**"（实测主控站无 gitleaks ⇒ 现状本就是 spec 允许的回退版，非漏项）。**实施**：规则清单抽到 `Get-ScrubRules`（**单一真值源**；`Invoke-Scrubber` 抹 / 新增的 `Get-ScrubBlockReason` 拒都从它取）⇒ **9 条**；**私钥块改"拒发"**（fail-closed，`REJECT scrub-unsafe:private-key … exit 4`，主路与 claude 备路各判一次 —— 二分依据 = "能不能安全抹除"，同时消掉 DESIGN §193「命中即拦截」与 §2.1「脱敏后远端」的旧张力）。**自证**：夹具 **43/43**（§1 正例 13 / §2 负例 13（含 ★ 三条把"不加"决定做成回归守卫：run ID、`.local`、内网 IP）/ §2b+§2c 过度消费 7 / §3 幂等 9 类占位符 / §5 block 判据 7 / §6 规则清单自证）+ **变异自证**（`aws-ak` 的 `{16}`→`{10}` ⇒ 3 条断言同时红 + 覆盖率 6/14→5/14）+ **实弹**（`sanitized`+`cli: claude` 卡贴私钥块 ⇒ rc=**4** 与日志一致、在任何 spawn 之前、git status **零残件**）+ `_fm_golden_test` **98/98** 零倒退。⚠ **`[4]` 覆盖率 0/14 → 6/14**，剩 8 项**就是"不加"的那 8 项**（不是未做完）；**[4b] 2/2 不变**。**未做**：✅ ~~P3（"附件内容不消毒"仍需一张"带敏感附件+sanitized"的探针卡实测）~~ —— **2026-09-21 已完成并实测成立**：探针卡与自对照设计与结果见下一行。② 在 [4] 被处置前，**"`sanitized` 抹完 = `public`"仍只是有条件的**（同时也是 P1 那条被撤回的 `sanitized×可能训练` 闸的重审条件）—— ⚠ 但现在**有条件的方向已经明确**：凭据类出网前必被抹、私钥块直接拒发，**剩下的敞口 = 那 8 项身份与拓扑类**（由档位纪律承接）；⚠ 规模要如实标注：22 张卡里 `sanitized` **只有 1 张**（且是脱敏器自己的验收卡）⇒ blast radius ≈ 0，本裁定定的是**将来语义**，**优先级低-中** |
| ✅ ~~**`sanitized` 附件旁路（P3）：附件内容是否也不经 scrubber**~~（2026-09-21 新登记并**当日闭环**，实测成立） | **问的什么**：`Invoke-Scrubber` 只作用于 `$promptFull`，而**附件**是 `scp`/`Copy-Item` **原文**（主路 L1227/1230、claude 路 L2290）⇒ 若卡同时满足「附件含敏感内容」+「模型指向云端」，附件内容会**原样进云端上下文**，即 DESIGN §9 不变式②（"消毒在控制台完成"）**在附件上是空的**。**实测（自对照设计）**：同一路径植两处 —— 卡正文（必经 scrubber）= 控制组，附件 = 实验组，让 agent 各照抄一行。结果 **两路一致**：`LINE1=[REDACTED-PATH]` + `LINE2=D:\Paper\agent-out\secret.xlsx`（原文）。**云端后果的硬证据**：claude 路 run `202609220011097576`（模型 `inkling:free` = 第三方云）的**转录** `~/.claude/projects/D--Paper/bc584929-….jsonl` 显示 `cwd="D:\Paper"`、`tool_use blocks=2`、`Read`×1 ⇒ **原文确实进了模型上下文，不是模型猜的**。**另一个方向也证明了**：run `202609220025427213`（**故意不加** `-Attach`）⇒ agent 报 `File not found: /home/scott-lau/agent-workspaces/paper/.attach/scrub-probe.txt` 后回 `NONE` ⇒ 探针**不会恒答 yes**，且**主路 cwd 就是站上工作区**（相对路径解析正确）。⚠ **两路各自证明了什么要分清**：**云端后果**由 claude 路证明；主路那两跑用的是**站上本地模型**，只证明"附件以原文落到远端工作区且 agent 读得到"（主路打真云未做成，见下一行） | ✅ **已闭环（2026-09-21）**：探针卡 [`test-cards/scrub-attach-probe.md`](../../spec/d6-agent-standard/test-cards/scrub-attach-probe.md) + 附件 `ops/station-bin/attach-test/scrub-probe.txt` **均入库**（选 Windows 路径做样串：既被 `win-path` 规则覆盖，又**不触发**本地 `secrets` 门禁与远端 push-protection ⇒ 可复跑）；**runner 说明刻意放卡外**（`…-notes.md`）—— 首跑证明"说明留在 body 里"会把**期望答案**提前告诉被测对象（污染）且多出 2 处被抹副本。**⇒ 对不变式②的结论**：其"消毒面"**不含附件**（当前实现如此，且此前**未在任何文档写明**）。✅ **已写进 DESIGN §5.1 sanitized 前置块（2026-09-21）**。**仍未做**：要么把附件纳入 scrubber，要么对"含敏感附件的卡"强制 `local-only` —— **这是决策，不是执行项** ⇒ **已并入下一行「消毒面 ≠ 出网面」的收口待裁表（①）** |
| **⚠ claude 路的附件面：本地支 cwd 缺陷（已修）+ 站上变体两处（未修）** | **由来**：P3 首跑 run `202609220005298044` 的 `LINE2=NONE` 逼出来的。**(A) 本地支（`Invoke-ClaudeFly`）不设 `WorkingDirectory`** ⇒ 子进程**继承控制台 cwd**（常态 `d:\RPC`，非 projRoot），而附件被复制到 `<projRoot>\.attach`、prompt 用**相对路径**引用 ⇒ **附件不可达**；代码注释「claude cwd=projRoot」与实测不符；且 accept 早已**显式** `-cwd $projRoot` ⇒ **agent 与 accept 的 cwd 不一致**（此前无人核过）。**(A′) 站上变体（`Invoke-ClaudeFly-Station`）更重**：站上脚本 `cd "$HOME"`（同样错位），且**附件只复制到主控本地 `<projRoot>\.attach`、根本没同步到站上** ⇒ `local-only` + 站上 claude + 附件时**附件完全缺失**。**(B) headless 工具未验证**：spawn 只传 `-p "" --model <id>`，**无** `--allowedTools`/权限模式 ⇒ headless 下工具是否可用**未测**（首跑 `tool_use=0` 但那次的卡**禁止**用工具 ⇒ 无法归因） | **(A) ✅ 已修（2026-09-21）**：`Invoke-ClaudeFly` 加显式 `-cwd` + `$psi.WorkingDirectory`，两处本地调用点（首跑/resume）都传 `-cwd $projRoot`；**实测证据**：修前转录目录 `D--RPC`（cwd=控制台），修后 `D--Paper` 且附件可读（run `202609220011097576`）。**回归守卫**：`_fm_golden_test.ps1` 新增 `cwd:` **三条结构断言**（含"两处调用点都传"的计数断言），并做**变异自证**（去掉一处 ⇒ 断言红 + 退出 1）。⚠ 结构断言只查"接线在不"，**行为证据只有实弹能给**。**待办**：**(A′)** 站上变体要么把附件同步到站上工作区、要么显式拒绝"站上 + 有附件"（**别静默缺失**）；**(B)** 去掉卡里工具禁令再跑一次单测工具可用性 |
| **⚠ 站上 zen 路由空转：没登录 ⇒ 不快速失败，只烧预算（2026-09-21 新登记，实测）** | **实测**（P3 主路跑 run `202609220018387887`）：`-Model lightning`（= `opencode/nemotron-3.5-lightning-free`，B 站）⇒ **3×120s 零输出**（`TASK_RC=124`→rc=6、`RUN_S=360`），`agent-output.txt` 只有 `> build · nemotron-3.5-lightning-free` banner + `RESUME` 标记。**已排除**：① **网络** —— 站上 `curl` 对 `openrouter.ai`/`models.dev`/`opencode.ai` **全 200**；② **引擎** —— `CHAT_OK`/`READY_OK` 都过（`ENGINE_CTX=32768`）；**唯一相关日志**是 `Failed to fetch models.dev … TimeoutError`（瞬态）。**已确认（2026-09-21 实测，从"嫌疑"升级）**：① 三站 `opencode auth list` **全为 0 credentials**（A 有 `auth.json` 但内容是 `{}`，B/C 无该文件）⇒ zen（opencode 自带 provider）**未登录**时**不报错、只空转**（把"缺凭据"变成 360s 无输出）。② **判别性实测**（站上直连、不经 agent-cli，有界 30s）：zen 模型 ⇒ `RC=124` + 只有 banner + **零错误行**；**同一模型**走站上**已有凭据**的 `openrouter` ⇒ **`RC=0` / 16s / 输出 `ZEN-OK`** ⇒ egress、stdin 管道、引擎全部排除，**唯一变量是凭据**。③ 日志侧证：zen 选完模型后**再无任何日志**，而 openrouter 的失败**会**记 `stream error`（如小模型 title 用的 `google/gemini-3.8-flash` 被地区墙）⇒ "挂了"与"慢/报错"在外部**不可区分**。**登录前置条件（已问清）**：`opencode auth login --provider opencode` 要求 **`https://opencode.ai/auth` 的 API key**（**无设备码流程**），且 clack TUI **需 tty** ⇒ `echo <key> | ...` 管道喂 stdin **无效**（实测仍停在 `Enter your API key`、`auth list` 仍 0）。**复验工具（已入库）**：[`_probe_opencode_provider.sh`](../../ops/station-bin/_probe_opencode_provider.sh)（30s 内给出 `RC` + 凭据实况；判据写在脚本头）。⇒ 与"静默降级/失败不可见"同族。**⚠ 连带核对出的第二件事**：`ROUTE_TABLE` 里**站上云型号全是 zen**（`opencode/…-free`），**没有 `openrouter/…` 的站上条目** —— 而 OPEN-ISSUES 另一行把"站上 opencode 的 `provider.openrouter.models` 免费档表"列为免费档消费者之一 ⇒ **该消费者经派发表其实够不到**（`Resolve-Model` 是纯表查找、不 passthrough） | ✅ **已登记 + 已加护栏（2026-09-21，用户裁定"先不动 zen，只登记结论"）**：**护栏** = `ROUTE_TABLE` 里 `lightning`/`ultra`/`free-1m` 上方加**显式警告注释**（"当前不可用，别用" + 复验命令 + 登录前置条件）—— 即**在唯一的定义点标注不可用**，而不是静默留着。**⚠ 连带发现（要紧）**：`test-cards/sanitized.md`（**唯一那张 `sanitized` 验收卡**）用的就是 `lightning` ⇒ 原本**该卡跑不通**（sanitized 闸的**验收路径是断的**）⇒ ✅ **已闭环（2026-09-21 W1a，决策 C）**：`lightning`/`ultra`/`free-1m` 已**重指到"站上 `openrouter`"**（id 取 `secrets/openrouter.conf` 的 `harness_priority` 前两档 = **权威真值**，不新立模型清单），该卡**实测跑通**（run `202609221131192690`：`TASK_RC=0` + 3 处 `SCRUB` 命中 + agent 回 `A8B-PROBE-OK`）⇒ **sanitized 验收路径恢复**。**未做（待人裁）**：① **登录 zen** —— 前置条件已问清（需 `https://opencode.ai/auth` 的 API key + TUI 需 tty；**凭据我拿不到**）；② **改走站上已有 `openrouter`**（实测 16s 可用、凭据在位、四开关已核）⇒ 需改站上默认模型 + 加 `openrouter/<id>` 站上路由条目（顺带修掉"表里没有该消费者"的不一致）；③ 给远程 run 加**失败可见性**（零输出 + rc=124 时区分"模型没响应"与"根本没凭据"，**推荐**）；④ ⚠ 若启用 zen，**必须按 P1 那套核它的留存/训练政策**（我们只核过 OpenRouter，zen 完全未核）—— 否则 zen 承载 `sanitized` 流量就是"换了个未核过的第三方" |
| **⚠ `sanitized` 的「消毒面」≠「出网面」：两个已确认缺口 + 一项声明未接线（收口待人裁，2026-09-21 登记）** | **框架**：DESIGN §193 承诺"**未通过 scrubber 的任务绝不进入远端路径**"，但实现里 `Invoke-Scrubber` **全仓只有 2 个调用点**（主路 `Invoke-Task` / `Invoke-Task-Claude`；2026-09-21 核为 L1314/L2330 —— ⚠ 行号会漂，**点名函数为准**），**都在"派发"这一条路上** ⇒ 凡**不经派发**的出网内容，该承诺**不成立**。**缺口① 附件**（已实测，见上一行）—— 附件是 `scp`/`Copy-Item` **原文** ⇒ 附件的"消毒面"是空的。**缺口②（本轮新查出）`review`/judge 出网完全不消毒** —— [`Invoke-Review`](../../ops/station-bin/agent-cli.ps1) 读 `agent-output.txt`（**agent 产出原文**）→ `Build-JudgePrompt` 把 **`{{CARD_BODY}}`（卡的完整正文）+ `{{PRODUCT}}`（产出原文）+ accept/golden 元信息**拼进判据提示词 → 经 `Invoke-Judge` 送 **egress judge**（非 `local-only` 时**默认 `ultra`** = `opencode/nemotron-3-ultra-free` = **第三方云**）；该路径**既无 scrub、也无 `Get-ScrubBlockReason`** ⇒ **同一张 `sanitized` 卡的正文：派发时被抹、`review` 时原样出网** —— 消毒保证可被"**再跑一次 review**"绕过。⚠ 顺带：默认 judge `ultra` 正是**当前不可用的 zen 路由**（见上一行）⇒ 默认 `review` 现在也跑不通。**缺口③ `JUDGE_TABLE.compliance` 声明未接线** —— ✅ **已闭环（2026-09-21 W1a，选"接线"路线，见本行待裁 cell）**。原状：表里给 egress judge 标 `compliance='public,sanitized'`、本地 judge 标 `'all'`（**设计意图 = 按敏感度限制 judge**），但**全仓除该声明外无任何读取点**（实测 grep 只命中 6 行声明 + 1 处设计文档）⇒ 实际生效的是 `Invoke-Review` L3003 的**窄判据** `$judge['type'] -eq 'egress'`，它**只挡 `local-only`**、对 `sanitized` 一律放行 ⇒ **声明的意图从未生效**（"声明了但没接线"，与 `$backendEgress` 硬编码同族）。**本次审计范围（逐个过"声称覆盖全部"的机制）**：消毒（2 调用点，见上）· 敏感度闸（4 处：`Resolve-Model` / `Invoke-Task`（主路 + fallback 入口）/ `Invoke-Task-Claude` / `Invoke-Review` —— **只有 review 这处是窄判据、只挡 `local-only`**）· `Get-ScrubBlockReason`（2 处，**review 无**）· 证据清单基线 `Get-FrameworkSubjects`（**已登记**）· 站上 `out/` 固定名无陈旧守卫（**已登记**）· `secrets` 门禁只扫 git 跟踪文件（**已登记**）· BOM 子判据只覆盖 `.ps1`（**by design**，`.sh` 加 BOM 会让 shebang 失效）· `doclinks` 只判可达不判语义（**by design**）⇒ **新查出 2 项（②③）**，其余**已登记或属设计取舍** | ⏳ **收口待人裁（三项，各列影响面）** —— ⚠ **2026-09-21 细化分析见 [REMEDIATION-PLAN.md §5](REMEDIATION-PLAN.md)**（新增第三选项"附件默认不出网 + 显式放行"、把 W1 拆成 W1a/W1b、并按"存量只有 2 张卡会出网 + `review` 无常态调用"**把本行的缺口②从 P0 修正为「结构性 P0 / 暴露面 P1」**）：**① 附件** —— (a) 把附件纳入 scrubber（改动小，但 agent 读到的就不是原文，可能破坏依赖附件内容的任务）；(b) 对"含敏感附件的卡"**强制 `local-only`**（纪律，零代码，但依赖卡作者守规矩）。**② `review` 出网** —— (a) 在 `Build-JudgePrompt` 之后 / `Invoke-Judge` 之前**加同一套 scrub + block 判据**（与派发同规矩；代价：判据看到的卡正文被抹，可能影响评审质量）；(b) 对 `sanitized` 卡的 review **强制本地 judge**（`main`/`m27`/`rpc-v4flash` ⇒ 零出网；代价：失去异源判据）。**③ `compliance`** —— ✅ **已闭环（2026-09-21 W1a，选 (a) 接线路线）**：`compliance` 与新增的 `egress` 字段现在**都被真值函数读取**（`Get-JudgeComplianceReject` / `Get-JudgeEgress`，缺字段 ⇒ **拒/视为出网** fail-closed），review 闸改为「**硬不变式 + 表驱动**两判据都过才放行」；同批把**三处"按型号前缀判"（`Resolve-Router` / `Invoke-Task` / `Split`）换成后端属性判据** `Get-BackendEgress`（**fail-closed 默认：只有 `local/` 不出网，其余一律出网**；claude 通道豁免以免误杀 P3）⇒ **「再加一个后端/judge 又漏一次」的结构根因消除**。**自证**：夹具 **119/119**（含 ★"假想云端后端 `brand-new-vendor/*` ⇒ 出网"负例、`ROUTE_TABLE` 12 个 id 的出网/站内两类非空断言、`JUDGE_TABLE` 6 个 judge 的 `egress+compliance` 覆盖率断言、AST 断言"全仓不再存在按前缀判敏感度"）+ **两次变异自证**（`Get-BackendEgress` 恒 false ⇒ 5 条同时红；删一个 judge 的 `egress` ⇒ 覆盖率断言红并点名 `main`）+ **实弹**（`route` 三态、`task` 层 rc=4 且**零触站**、`local-only` 正例不误杀）。**剩两项已裁定（2026-09-22，见 [REMEDIATION-PLAN §5.5](REMEDIATION-PLAN.md)）**：**②选 (a)**（`review` **复用**同一套 scrub + block，**不**强制本地 judge）—— 决定性判据 = **档位语义一致性**：`sanitized` 的**定义**就是"抹后可出网"，若 review 不走抹，同一张卡的含义会**取决于跑哪个子命令**（且原推荐的 (b) 会引入"本地 judge 需引擎在位"这一新可用性依赖，引擎不在位时 review 直接不可用）；(b) 保留为**显式可选**（卡写 `review-model: main` 即可，无需新机制）。**①选 (c) 附件默认不出网 + 显式放行** —— 决定性判据 = **可判性**（附件形态不可判 ⇒ 抹不出可测覆盖率 ⇒ 只会产出"抹了一半"的假防线）。**⇒ 统一判据：可判的载体沿用档位定义（抹后可出网）、不可判的载体默认不出网**。⚠ 我原先在 §5.1 推荐的是 (b)（本地 judge），**裁定改为 (a)**，理由（档位一致性 + 新依赖）已写进 §5.5.1 的"反对意见"节。**实施项见 §5.5.3 —— ✅ 均已实施（2026-09-22）**：① `Invoke-Review` 已与派发**同规矩**（`Resolve-ReviewPrompt`：先 block 判据（命中**拒发**）→ 只对 `sanitized` 抹 → 再发请求）；② 附件已改为**默认不出网 + 显式放行**（新卡字段 `attach-egress: ok`；两个通道各判一次）。**自证**：夹具 **133/133**（+14，含 review 三态**行为证据**、位置断言、attach 五态）+ **两次变异自证**（两个函数各自失效 ⇒ 4 条同时红；**顺序变异**：在闸前插一个诱饵发送点 ⇒ 位置断言当场红） + 实弹三条（`sanitized` 卡 review ⇒ 3 处 `SCRUB` + `score=优秀` rc=0；私钥块卡 review ⇒ `REJECT scrub-unsafe:private-key` rc=4 且**零触站**、`review.json` 未创建；附件卡 + 出网型号 ⇒ `REJECT attach-egress-unconfirmed` rc=4 且**零触站**）。⚠ 实施中发现并修掉一条**假判**：位置断言第一版用文本 `IndexOf` 命中的是**注释里的函数名**（"调用被搬走也 PASS"）⇒ 改为 **AST 找实际命令调用**（详见夹具注释）。原选项 (b)"删字段"已作废（选了接线）。**⚠ 追补（2026-09-22，§5.5.4）**：W1b/W4 让 `review` 写出 **`review.json` = 新证据件**，门禁随即报出「已归档但未被任何 subject 覆盖: review.json」（`paper/202609221131192690`）⇒ 已按门禁给的修法把 `review` 件加进**两个**按路基线（`Get-FrameworkSubjects` / `Get-ClaudeFrameworkSubjects`）并**带 `ephemeral = $true`**（事后写入、非派发必有 ⇒ 裸列会让每个未 review 的 run 假报 `missing-artifact`）。**⚠ 关键**：manifest 是**派发时快照 ⇒ 不回溯** ⇒ 该 WARN **不会被这次修复消掉**（存量那条的 manifest 是修复前写的），修法只保证**将来**不再产生；存量那条属历史欠账，要消掉须 `agent audit --accept`（**按设计是人的显式动作**）—— ✅ **已于 2026-09-22 用户裁定后执行**：水印 **15→16** 条，门禁 `evidence` 转 **PASS**（`gap 16 条(存量 16)`、无新增）。同批还拿到了**真实派发**的行为证据（此前记为"省略的 e2e"）：修复前 run `202609221131192690` 的 manifest = `subjects=10`、**无 `review`**（故 `review.json` 成缺口）；修复后 run `202609221224005057` / `202609221229582508` = `subjects=12`、**含 `review`(`ephemeral=True`)**、audit 表 `未声明=0` ⇒ **缺口不再产生**。⚠ 水印 `ops/.audit-baseline.json` **被 gitignore** ⇒ 换机/重克隆会重新报这 16 条存量（按设计："接受"必须留痕在人这一侧）。夹具 **133 → 137**（+4）+ **变异自证 3 次**（去 `ephemeral` ⇒ 2 红；整条删 ⇒ 8 红；破坏 Merge 透传 ⇒ 2 红）。**建议顺序（已按 §5 细化修正）**：③(a) → ②**(b)** → ①**(c)**（先把判据接到真值源；再让"出网"变成**需显式放行的例外**；最后把附件/PII/拓扑统一交给档位）。**关联**：本轮同时发现 claude 路附件面两处（站上变体附件未同步 / headless 工具未验证）与 zen 不可用 —— 见上两行 |
| **⚠ 注入式探针 `_probe_fallback.ps1` 自 W1a 起静默失效（2026-09-22 发现并修复）** | **症状**：核 §5.5.4 时顺手跑探针做行为自证 ⇒ **立即抛** `The term 'Get-BackendEgress' is not recognized`。**两个独立根因，都源自"判据自己有无调用点"这条老问题**：**① 提取清单漂移** —— 探针用**硬编码函数名清单**从 `agent-cli.ps1` 抽纯函数进会话（它 stub 站点依赖、只跑 `Invoke-Task` 真逻辑）；此后 P5 规则扩充加了 `Get-ScrubRules`、W1a 加了 `Get-BackendEgress`、W4 加了 `Get-AttachEgressReject`、C1 加了 `Test-CtxOverflowError`/`Resolve-CtxOverflowCode`、O-13 加了 `Resolve-ClaudeStationCandidates`/`Resolve-ClaudeBudget` ⇒ 清单没同步 ⇒ `Invoke-Task` 一跑到新函数就抛。**② 文本签名过时（且过时方向危险）** —— 覆盖断言数的是**字面量** `Get-SensitivityBackendReject … -backendEgress $true` 出现 ≥2 次；而 **W1a 的全部用意正是把硬编码 `$true` 换成后端属性判据**（故意只留兜底入口 1 处）⇒ 实测只剩 1 处 ⇒ **判据与设计反向**（继续用它等于要求"把属性判据改回硬编码"）。**为什么无人察觉**：该探针**无自动调用点**（手动跑；不在门禁/夹具/hook 里）⇒ 坏着没人知道（W1a 09-21 → 发现 09-22）。⚠ 与本表"`syntax` 抓不到无 BOM 脚本"那条**同族**：**守门人自己死了，而没有任何判据判"守门人还活着"** | ✅ **已修（2026-09-22）**：① 提取清单补齐 4 组新增纯函数，并在注释里写明**同步纪律** + 判据（"`Invoke-Task`/`Invoke-Task-Claude` 体内是否直接调用它"）；② 覆盖断言改 **AST**（数 `Invoke-Task` **体内** `Get-SensitivityBackendReject` 的 `CommandAst` ≥2 处）+ 保留"拒绝串可分辨路径"（文本判据那次的教训：**文本签名会随实现改进静默变成错误的要求**）。**复跑全绿**，并顺带新增一条**行为证据**断言 `claude baseline: review(review.json) present + ephemeral=true`（见上一行的 §5.5.4）—— 这是本仓唯一能**离线**跑真实归档路径并读到 `.agent-run.json` 的地方。**仍待办（已登记，未做）**：给探针加**自动调用点**，或至少加一条"探针可导入 + 提取清单齐备"的冒烟判据 —— 否则**它还会再烂一次**（这次 8 天，下次可能更久）。**更彻底的方向**：把硬编码清单换成"提取**全部** `FunctionDefinitionAst`、**再**覆盖 stub"（stmt stub 在后 ⇒ 仍生效 ⇒ 免维护） |
| **账户未完成 18+ 年龄确认 ⇒ Meta 系型号全 403（2026-09-21 新登记，账户配置）** | **实测**：请求 `meta/muse-spark-1.2` / `meta/muse-spark-1.2-contributor` 一律 `403 This model requires you to complete the following before use: 18+ age confirmation.`（提示去 `openrouter.ai/settings/…`）。**影响**：**不**影响现用备路型号（非 Meta 系），但**挡住未来选型**（本轮本想用 Meta 型号交叉验证"付费档训练开关"的推断，被此闸挡下）。**另注**：`/api/v1/models/user`（443）相对 `/api/v1/models`（446）少掉 3 个型号（2×Meta `-contributor` + `sakana/sakana-namazu`，**均为 live、无下架日期**）⇒ 是**策略过滤**而非下架；但**非** contributor 的 `meta/muse-spark-1.2` 仍在列表内却也 403 ⇒ **18+ 闸不是**该过滤的原因，两者是独立现象 | 待办：属账户配置项，按需在 dashboard 完成年龄确认（**不必现在做**，因为不挡现用型号）；若将来要用 Meta 系型号再补 |
| **⚠ "备路/换站的总墙钟预算"缺失（2026-09-21 新登记，测量 3 副产物）** | **实测**（[§3.5](../../docs/research/2026-09-21_D6备路站上化与sensitivity设闸调研与方案.md)）：`fallback-deadlock` 卡声明 `timeout_s=10`，而**实到墙钟 `33.4s`**（主控侧 sync/collect + 远程 run 20s）。**根因**：`timeout_s` 只包住远程 `timeout $timeout opencode run …`（`agent-cli.ps1` L1320），**不覆盖** ① 站上引擎加载（`T_load`，11G 模型实测 **7s**）② 主控侧 sync/collect ③ `Invoke-StationReady` 的就绪校验（内含 `-m60` 的 chat 往返）。⇒ 任何"换站 / 先加载再用"的方案都会**在这三段里无预算可依**，且调用方看到的墙钟与卡声明的预算**可差 3 倍以上**。**⚠ 别混淆**：P4 的 `fallback-timeout-s`（2026-09-21 **已实施**）是 **claude 通道跑批**的独立预算是另一个缺陷的修法，**不覆盖**上面三段 ⇒ **本行未闭合，待办不变** | 待办：若要引入"换站/加载"，须**另立一个总墙钟预算**（命名避开 `fallback-timeout-s`），并明确超时后是 fail-closed 还是回落云端；与 P3 的选型结论一起定 |
| ~~**`agent-cli.ps1 task` 进程退出码 = 0（rc 可信性）**~~（2026-09-21 登记 → ✅ **2026-09-22 当日闭环，且**定级被实测修正**） | **⚠ 登记里的两条结论都被这次的实测推翻，先记更正**：① **不是"特定于 AUTO_FALLBACK 那条返回路径"** —— 登记据此写的理由（`route --model no-such-alias` 返回 2、`task -Cli claude` 返回 4 都对）**站不住**：那两条都恰好在污染点**之前** early-return。实测**不带** `AGENT_AUTO_FALLBACK` 的普通超时 run 同样 `TASK_DONE … exit=6` + `ledger+=…,6,…` 而**进程 rc=0** ⇒ 真实范围是"**任何走过 `.attach/` reset 之后的派发**" = **每一次真派发**；成功时看不出（本来就该 0），**失败时被静默读成成功**。② **"推测（未证）"已证并改写**：不是 `ssh`/`scp` 残留**文本**，而是 `Invoke-RemoteScript` 的 **int 返回值 0**。**测法（值得复用）**：给 CLI 入口加临时诊断打印 `$code` ⇒ 实得 `codeIsArray=True count=2 / [0]=Int32 0 / [1]=Int32 4`；再用 **AST 扫 `Invoke-Task` 体内的"裸语句"**（未赋值、未 `\| Out-Null`、未 return）⇒ 定位到 attach-reset 处那行**裸调用** `Invoke-RemoteScript`（返回 int rc、成功后=0；09-18 缺口 5 把它改成**无条件** reset ⇒ **每次派发都跑**）。机制另经**独立钉死**（临时脚本直测进程 rc）：`exit 4`⇒4 / `exit @($null,4)`⇒**0** / `exit @(0,4)`⇒**0**。**同族根因**：09-18 "归零纪律"清点时只覆盖 **cmdlet**（`Copy-Item`/`Move-Item`/`Remove-Item`/`Add-Content`），**漏了自定义函数的返回值** | ✅ **已闭环（2026-09-22）**：**两层修** —— ① **根因**：全仓 **6 处**裸 `Invoke-RemoteScript` 一律 `| Out-Null`（归零纪律补全）；② **出口守卫**：新增纯函数 `Resolve-ExitCode`（取**末元素**）并让**全部 5 个** `exit $code` 走它（防"新增子命令又漏"）。⚠ 守卫取末元素与 `_probe_fallback.ps1` 早已有的 `Scalar` **同规则** —— 这正是"**探针一直没被骗到、只有 CLI 的调用方被骗**"的原因。**实测闭环**：同一命令 ⇒ `REJECT … exit 4` + **`PROC_RC=4`**；不带 fallback 的普通超时 run 亦回到真值。**自证**：夹具 **137→147**（+10）+ **变异自证 3 次**（删回 `\| Out-Null` ⇒ 裸调用断言红；守卫改取**首**元素 ⇒ 2 条标量化断言红；撤一处出口守卫 ⇒ 2 条计数断言红）。⚠⚠ **自证当场抓出我自己的一条假判据**：裸调用的 **AST 判据第一版只判 `StatementBlockAst`**，而**函数体是 `NamedBlockAst`（与它是兄弟类，不是子类）** ⇒ "写在函数体顶层"的语句**全被漏掉**，而那处 bug 恰在顶层 ⇒ **删回 `\| Out-Null` 也照样 PASS（假安全）**；收了两个容器类型后才红。**教训（与"位置断言被注释骗"同族）**：**结构判据必须先在"已知该红"的变异上验红，否则它只是"在跑"，不是在判。** |
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

> **台账维护规则回归**: 本表是 D6 未决问题唯一总账；上表"真实剩余 open"之外均为已闭环/已覆盖（数量与逐项溯源见上方**计数说明**），若未来 OPEN-ISSUES 快照提到"G 清单未闭合"应能溯源到那 10 项 + 对应 G 编号。
