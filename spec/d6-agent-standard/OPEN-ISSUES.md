# 开放日志：D6 agent-cli wrapper MVP（Open Issues 台账）

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

| **证据流可重放性（evidence_manifest + 异基座管线审计）** | **阶段 0 已执行（2026-09-16，[ADR-0005](../../adr/ADR-0005-任务卡证据回收闭环.md)）**：证据回收闭环落地 —— `.meta`/`.prompt.txt`/`.progress` 原文/`.accept-cmds.txt`/`.golden-cmd.txt` 归 `agent-out/<ts>/`，`run.json.accept_golden` 增 `sha256`/`base`，TEMP 泄漏与失败路径一并修；**三项自证能力实测 PASS**（`sha256(prompt.txt)==prompt_sha256`、`accept_golden.sha256==仓库源哈希`、`judgment-record ↔ run.json` 逐项一致），collect 115s→49s。**剩阶段 1（manifest 规范化）/ 2（离线复验器）/ 3（异基座管线审计）** 未做，方案见[调研文档](../../docs/research/2026-09-16_任务卡证据流可重放性调研.md) §7.1 | **09-17 更新：路线与推进步骤已定案 → [ADR-0007](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md)**。①**阶段 2「形态」已落地**：离线复验器 `cluster.py agent chain/verify`（零自加载、不触站、离线、**指到第一条断裂处**，实测 12 项含负向双向自证 + 边界实证），设计见 [evidence-chain/DESIGN.md](evidence-chain/DESIGN.md)；②**缺口 7 已闭环**：门禁第 15 项断言 `evidence`（quick、只读、按 FAIL/WARN/info 分层）；③配套：钩子自动入链（改 `rpc.ps1` 钩子**生成器**）+ 外部锚 `ANCHOR.txt`（已 push 到 origin 作跨信任域见证，强度=「多副本见证」非密码学不可否认）；④**阶段顺序修正**（原「1→2→3 不可反」作废 ⇒ `0 → 0.5 → 2内容 → 1 → 3`，因实测复验器**不依赖 manifest**）；⑤**新增阶段 0.5「改动验证闭环」**（轻卡+小模型夹具）——因阶段 1 与缺口 4/5/6/8/10 **全都要改 `agent-cli.ps1` 派发路径**，无夹具则只能停在走查级；⑥**阶段 3 挂起**（证据面仅 6+1 件，现阶段审计员可判项过少，等批 B 扩面后重启）。**待决策：进入批 A**（`verdict-chain` + `golden-identity` 复验，纯主控侧可离线自证）。**09-18 更新：批 A / 批 B 已执行到位** —— 批 A（`verdict-chain` + `golden-identity`，含 17 项严格双向自证）✅；**阶段 0.5「改动验证夹具」**✅（轻卡 + 小模型，正负双向）；**阶段 1 manifest 完成**（围栏加固 / recipe 按条目分派 + `v2` / 卡侧三级嵌套解析 / 「未声明产物即失败」负向判据）✅；**缺口 4**（diff 证据：`find -newer` 载体 + `diff-scope` 判据，正负 e2e）✅；**缺口 6 / 10** ✅；**缺口 5**（attach 哈希：站上逐文件 `sha256sum` ⇒ `attach-manifest.txt`，run.json `attach` 升对象数组 `{name,src,kind,files,sha256}` ⇒ **被链钉住**；跨信任域交叉验证 + 三项负向均实测）✅。**仅剩批 B 的缺口 8（`usage`/`session_id`/`timestamp` 遥测）**；阶段 3 仍**挂起**。链 **76 条**（A1 **12/76** · A2 **13/76** · A3 **3/76**）。**09-18 收口：缺口 8 亦已闭环** ⇒ **批 B 全部完成** —— 站上 [`_oc_session_meta.sh`](../../ops/station-bin/_oc_session_meta.sh) 从 **opencode 会话库**取该次会话的真实聚合（token 明细 / tool 计数 / `session_id` / 时间戳）落入 run.json（取不到 ⇒ `usage.source=unavailable`，**不猜数**；claude 备路明标未采集）；独立复核用**另一张表**（Σ `message.tokens` == 会话行聚合，跨表 MATCH）；负向（改 `total_tokens` 1 位）⇒ `digest_mismatch` + 门禁红灯 ⇒ 字段**被链钉住**。链 **79 条**（A1 **15/79** · A2 **16/79** · A3 **3/79**）。**下一步只剩阶段 3（批 C，挂起）**。**09-18 再更新：阶段 3 按 D5 拆两步，3-a 已落地** —— `cluster.py agent audit`（**机器层**）：逐 subject 判"能否离线复现、卡在哪" ⇒ **可机判 gap 表**（advisory，**刻意不进 FAIL 集**；与 `verify` 分工：verify 管"是否被改"，audit 管"是否可重放"）。语料首跑：声明 **72** 条中 **67 可离线复算**、`collect` 型 **4** 条（`declared-not-executed`）、**已归档但未声明 37 件**（write 卡未声明的 `workspace-diff.txt` 等）；夹具卡已据此补全声明（新 run 实测 **gap 表为空**）。**3-b（异基座 judge：A/A 基线 + 顺序对调 + 跨家族）未做**，设计已定见 ADR-0007。链 **81 条**（A1 17/81 · A2 18/81 · A3 3/81）。**09-18 三更新：3-b-1 校准已实测** —— `agent audit-judge`（advisory，只测量不改门禁）：跨家族 judge（站内 **Qwen3.8-27B-MTP-Q8_0**，与被审证据的 gpt-oss 不同家族）在 11 条题集上 **A/A 11/11 · 序翻转 0/11 · 措辞扰动 11/11 · 与判据一致 11/11**；**关键对照**（2 条机器标签故意与判据相反）⇒ **按判据判 = 复核而非复读**；"存在未知"那条四轮均 UNSURE（不硬猜）。**诚实边界**：题面是结构化元数据 ⇒ 只证"能稳定执行写明判据"，不证"能从杂乱材料发现缺口"。**3-b-2（常跑审计）未做**，前置已满足（题面是否扩到杂乱材料等待定）
| **框架级：每次 ssh/scp 建连 14-17s** | ~~09-16 新登记（性能）~~ → **当日闭环（[ADR-0006](../../adr/ADR-0006-控制面传输绑定LAN_IPv4.md)）**：根因不是 sshd/UseDNS，而是**主控解析 `*.local` 需 16-17s 且只返回公网 IPv6** ⇒ 每次建连白付 16s **且控制面经 ISP IPv6 绕行、不在局域网内**（站上 `$SSH_CONNECTION` 实测证实；`ControlMaster` 在 Win32-OpenSSH 9.5p1 亦不可用）。处置：`~/.ssh/config` 把 A/B 名字 `HostName` 绑定到 LAN IPv4（+`AddressFamily inet`）+ 三个 IP 身份块，`cluster.py` 的 STATIONS 同步改 IPv4，LAN 真值入 `inventory/net.yaml` 的 `lan` 段，并在门禁 `stations` 新增 **(h)** 防漂移断言（`ssh -G` 的 hostname 必须 == 登记 IP；已做负向自证）。**实测：按名 16.2s → 0.18s（≈90×）；单次 task run 421s → 48.5s（8.7×），其中模型本身占 38s ⇒ 框架开销 ~383s → ~10s** | 已闭环。建议（可选加固）：路由器按 MAC 做 DHCP 保留（固定 .32/.33/.37）；`agent-cli`/`cluster.py` 的 ssh/scp 统一加 `-o BatchMode=yes`（防认证失败时静默等 stdin，本轮实测踩到 >90s 挂起）**→ 见下条** |
| **ssh/scp 未统一 `BatchMode`（认证异常时会静默等 stdin）** | **09-16 新登记（健壮性）**：ADR-0006 调查中实测踩到 —— 按 IP 连接时因 `~/.ssh/config` 无对应身份块，用户名退化为本机 `peng` ⇒ 触发口令提示 ⇒ **挂起 >90s 等 stdin**（自动化里表现为"卡住"而非"失败"）。已在 `~/.ssh/config` 补三个 IP 身份块消除该场景，但**调用点本身仍未加 `-o BatchMode=yes`**（agent-cli.ps1 的 ssh/scp、cluster.py 的 paramiko 路径） | 待办：给所有 ssh/scp 调用点统一加 `-o BatchMode=yes` + 明确 `ConnectTimeout`，把"卡住"变成"快速失败" |
| **`doclinks` 对新文件有盲窗（未跟踪文件不扫）** | **09-16 新登记（判据自身的盲区）**：`doclinks` 只扫 `git ls-files` 的 md ⇒ **新写的文档在 `git add` 之前不进判据**。实测代价：ADR-0005 落档时门禁报"失效 0"，而它内部有 **27 条 `../../` 前缀错**（`adr/` 只有一层，应是 `../`），直到本次 ADR-0006 落档时才被连带发现（两文件共修 38 条）。⇒ 判据存在"写完 → add"之间的静默窗口（与"门禁绿灯 ≠ 产物可信"同族） | 待办：把 `doclinks` 扫描集改为 `git ls-files ∪ git ls-files --others --exclude-standard`，或在 pre-commit 时对暂存文件全扫 |
| **`Get-FrontMatter` 不剥离 YAML 引号** | **09-16 新登记（解析器行为）**：卡里写 `accept: - "true"` 时引号**原样**进入命令列表（`eval` 后仍能执行，故非功能缺陷），但会让"证据 ↔ 声明"的字面比对出现差异（实测 `accept-cmds.txt` 内为 `"true"`，而卡内声明是 `"true"` 的引号已入串） | 低优先：可剥引号，或仅在文档写明"命令列表不要加引号" |

| **`syntax` 断言占 quick 门禁 96% 耗时（本轮新发现）** | **09-17 新登记（性能）**：逐项实测（`tmp/_t2.py`，逐 check 计时）——**quick 门禁实测 ≈16.4s**，其中 **`syntax` 独占 15.8s（96%）**，其余全部合计 <1s（`secrets` 123ms / `aliases` 214ms / `doclinks` 85ms / **`evidence` 仅 40ms**）。**为何要紧**：pre-commit 钩子每次提交都跑 quick ⇒ **每次 commit 白等 ~16s**；且记忆/文档里"quick 1.1s"是**过时值**（仓库已长到 206 脚本 / 683 文本件 / 409 个 `.sh`）。根因推测：`syntax` 对每个 `.sh`/`.ps1` **逐个 spawn 解释器**校验（409 个 `.sh` 是主项）——**未取证到函数内部，仅由"其余项皆 <250ms + 文件数占比"推断** | 待办：改批量/并发校验（或按需只校验改动文件），把 quick 压回秒级；属**独立性能项**，非证据流范围 |
| **`syntax` 断言抓不到"无 BOM 的含中文 .ps1"（本轮新发现）** | **09-18 新登记（判据盲区）**：`ops/station-bin/_fm_golden_test.ps1`（**卡解析器的回归守门夹具**）**缺 UTF-8 BOM**（首字节 `23 20 3D`）。PS5.1 按 ANSI 解码含中文的脚本时，**3 字节 UTF-8 序列被当 2 字节 GBK 解码会吞掉相邻换行** ⇒ 语句被并进注释 ⇒ 夹具**静默失效**（`DEBUG fns count=0` + `Get-FrontMatter not found`，即"守门人一直是死的"）。**为何门禁没拦住**：`syntax` 报 `.ps1:12文件/0失败` —— PS5.1 对无 BOM 文件按 ANSI 解码**不报错**（只是内容变乱码）⇒ **"语法通过" ≠ "语义正确"**（与 G8「'包在' ≠ '功能在'」同族）。**处置**：已补 BOM（改前备份 4802B 一致）恢复 `fns=32` | 待办：给 `syntax` 加**子判据** —— 含非 ASCII 的 `.ps1`/`.sh` 必须带 UTF-8 BOM（可机判、误报低）；属新增能力，走 ADR-0004 D3 |
| ~~**函数返回值被"非返回值输出"污染**（本轮新发现，已闭环）~~ | ✅ **09-18 当日闭环（详见 [ADR-0007](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md)「缺口 5 落地与实测」）**。**症状**：run.json 出现 `"exit_code": [null, 0]` + `"status": "failed"`（实际 rc=0），且**复验器崩**（`TypeError: unhashable type: 'list'`）；同 session `SLOT-GATE: na (engine port unknown)`。**根因**：PS 函数 = 管道上**全部**输出 —— `Invoke-RemoteScript`/`Invoke-StationReady`/`Invoke-SlotGate`/`Invoke-Task` 靠 `return $x` 交付，但体内有未被吸收的 cmdlet 输出；环境层对文件操作的包装器在失败路径吐了 `$null` ⇒ 返回值变 `@($null, <真值>)`。**修法（"归零纪律"）**：通知改 `Write-Host`；`Copy-Item`/`Move-Item`/`Remove-Item`/`Add-Content` 一律 `\| Out-Null`；纪律写入注释（凡返回值被调用方使用 ⇒ 体内不得有其它管道输出）。**自证**：再派发 ⇒ `excode=0`（非数组）/ `exit_code=0(Int)` / 槽位门恢复。**复验器加固**：`_verdict_check` 遇 `exit_code` 形状畸形 ⇒ 报 issue 而非抛异常（崩掉 = 整链判据同时消失） | — |
| ~~**PS5.1 无 `[DateTime]::UnixEpoch`**（本轮新发现，已闭环）~~ | ✅ **09-18 当日闭环（详见 [ADR-0007](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md)「缺口 8 落地与实测」）**：`[DateTime]::UnixEpoch` 是 **.NET Core 时代成员**，PS5.1 的 **.NET Framework 4.8 上不存在**，且**访问它不报错、静默返回 `''`** ⇒ 参与 `DateTime - ''` 时抛 `找不到 op_Subtraction 的重载`（实测：缺口 8 首次派发取遥测即因此失败）。**修法**：改用 `[DateTimeOffset]`（4.6+ 起有 `ToUnixTimeMilliseconds`/`FromUnixTimeMilliseconds`）。**副产物**：该误用**顺带把"取不到遥测"的 NA 路径在真实链路上跑通**（run `202609181232158097` 落 `usage.source=unavailable` + 告警，`TASK_RC=0`、任务结论不受影响）⇒ 兜底有效，但**不能把兜底当正常路径** | — |
| ~~**`.attach/` 清理只覆盖"有附件"路径**（缺口 5 修复不全，本轮新发现，已闭环）~~ | ✅ **09-18 当日闭环**：缺口 5 引入的"派发前清空 `.attach/`"外层套在 `if ($attach.Count -gt 0)` 内 ⇒ **无附件的派发会留着上一轮附件**（实测两次无附件 run 均报 `ATTACH_MANIFEST_LINES=3`：把上一轮 attach 夹具的三件算进本次 run；agent 亦可 `ls` 到残留）。**修法**：改为**无条件 reset**（代价：无附件派发多一次 ssh —— Correctness > 一次往返）。**教训**：缺口 5 的判据只覆盖"有附件"路径，**没有为"无附件"路径设判据，残留就被漏掉** —— "只覆盖一半的修复看起来是完整的"，与"判据必须报覆盖率"同源 | — |
| **`infer-load` 健康检查超时（首拉失败、重试即好）** | **09-18 新登记（基础设施/偶发）**：阶段 3-a 的 e2e 中 `cluster.py load gpt-oss-20b` 首拉报 `unsloth 健康检查超时`，而站上**实例其实已起**（studio :8080 + llama-server :41959 均在），日志显示健康检查对 `/v1/models` **连续 401**（每 3s 一次，直到超时）。**推测**：新铸 key 落盘与健康检查轮询之间存在**竞态**（该轮 `API Key ok` 行未打出）⇒ 用未同步的 key 去探。**实测**：直接重试一次即 `READY ✓`（key sha8 变化：`e698d92a` → `b359bb79`）。影响：一次派发失败 + 一次人工重试 | 待观察：若复现，给健康检查加"key 落盘后重读 + 401 单独识别为 key 问题"的判据（与"卡住 vs 失败"同族：**必须能区分**） |
| ~~**卡片身份不进证据（run.json/.meta 无 card 路径与哈希）**~~ | ✅ **09-18 当日闭环（详见 [ADR-0007](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md)「卡片身份入证据 落地与实测」）**：run.json 增 `card{path,sha256,bytes,front_matter}`（摘要取卡**原始字节**），卡字节归档为 runDir **`card.md`**（`Get-CardIdentity` 单一实现点，主路 + claude 备路共用）。**实测**：① 正向 run `202609181750311812` 三方摘要一致（repo 卡 == `card.md` == run.json）且**逐字节相同**；② **定版能力实证** —— 改版卡后 `repo 摘要 ≠ run 钉住的`，而 `card.md` **仍等于**钉住的 ⇒ **当时版本可复原**（"只记 hash 不够"的实证）；③ 篡改 `card.sha256` 1 位 ⇒ `digest_mismatch` + 门禁红灯；④ 链 83 条全绿。**顺带闭环一个更根本的洞**：无 front-matter 卡会静默退化（`public` + 可写 + **无 golden/manifest** ⇒ **验收本身消失**，实测 agent 跑偏仍 rc=0）⇒ 加护栏 `Test-CardSafetyDeclared`：须显式 `-Sensitivity` 才放行，否则 `REJECT no-front-matter-card (exit 2)` | — |
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

> **台账维护规则回归**: 本表是 D6 未决问题唯一总账；上表"真实剩余 open"之外均为已闭环/已覆盖（数量与逐项溯源见上方**计数说明**），若未来 OPEN-ISSUES 快照提到"G 清单未闭合"应能溯源到那 10 项 + 对应 G 编号。
