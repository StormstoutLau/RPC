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
| O-02 | 功能缺口  | P3   | workspace --archive 占位 echo 未演进（T1 stub）                                                                                                                                                                                                                                                                                                                                                                                                                        | 🔴 open                      | 二期                       | <br /> | <br /> |
| O-03 | 纪律    | P3   | A11/A12 probe 产物未持久化（证据腐化，仅文字实录在盘）                                                                                                                                                                                                                                                                                                                                                                                                                              | ⚪ 已登记·后续遵守                   | 纪律项                      | <br /> | <br /> |
| O-04 | 纪律    | P3   | ledger 追加非沙箱安全：沙箱会话运行 wrapper 时 Add-Content agent-runs.log 被拒（14:50 丢台账行）                                                                                                                                                                                                                                                                                                                                                                                       | ⚪ 已登记                        | 纪律项                      | <br /> | <br /> |
| O-05 | 性能    | P3   | sync 62.3s 微超 60s 预算 4%；IMPL §5 sync/task 口径重叠                                                                                                                                                                                                                                                                                                                                                                                                                  | ⚪ 已登记                        | 二期/口径修正                  | <br /> | <br /> |
| O-06 | 兼容性   | ⚠ 部分 | S6 中文**路径/文件名**未测（内容级已测，路径级可选未执行）                                                                                                                                                                                                                                                                                                                                                                                                                               | ⚠ 待验证                        | Cpp\_Hub 前               | <br /> | <br /> |
| O-07 | 验证    | P2   | zen 限额（429/quota）真实触发未发生（退出码 7 定义置位）                                                                                                                                                                                                                                                                                                                                                                                                                            | ⏳ 待真实触发                      | 事件驱动                     | <br /> | <br /> |
| O-08 | 升级    | P3   | F1 后端并发探测未实现（降级为 queue\_s 观测先行）                                                                                                                                                                                                                                                                                                                                                                                                                                 | ⏳ 挂起                         | V2/并发 fan-out            | <br /> | <br /> |
| O-09 | 验证    | —    | BS-1 跨工作区并行 isolate\_db（SQLite 写锁序列化）                                                                                                                                                                                                                                                                                                                                                                                                                           | 🔴 open                      | V2 fan-out 前置            | <br /> | <br /> |
| O-10 | 验证    | —    | BS-2/跨站 编排层并发 HTTP fan-out 落地（L1 已验证，L2/L3 未做）                                                                                                                                                                                                                                                                                                                                                                                                                  | ✅ L1 pass                    | V2                       | <br /> | <br /> |
| O-11 | 验证    | —    | 跨站扇出 L2 端到端（真实 readonly 卡）+ L3 回归（agent-cli-smoke + A 抽检）                                                                                                                                                                                                                                                                                                                                                                                                       | 🔴 open                      | V2                       | <br /> | <br /> |
| O-12 | 功能    | P3   | strong accept：附主控站侧 golden 测试（防模型自写测试自证通过，P1b 遗留）                                                                                                                                                                                                                                                                                                                                                                                                               | 🔴 open                      | 下一任务卡设计时                 | <br /> | <br /> |
| O-13 | 预置    | —    | G8 预置批次：R/sympy/重资产（Cpp\_Hub 前）                                                                                                                                                                                                                                                                                                                                                                                                                                 | ⏳ 挂起                         | Cpp\_Hub 试点前             | <br /> | <br /> |
| O-14 | 依赖    | —    | 网关 auth 遗留：B:4000 LiteLLM 401 根因已改定（后端换载 key 不同步，非 master\_key 哈希）                                                                                                                                                                                                                                                                                                                                                                                              | 🔴 open                      | 运维修复                     | <br /> | <br /> |
| O-15 | 演进    | —    | claude 路径 + --continue（G1 二期，Continue-vs-Spawn 决策表）                                                                                                                                                                                                                                                                                                                                                                                                             | 🔴 open                      | 二期                       | <br /> | <br /> |
| O-16 | 演进    | —    | review --peer 站间互审 / trae 派发（任务卡=接口）                                                                                                                                                                                                                                                                                                                                                                                                                            | 🔴 open                      | D7+                      | <br /> | <br /> |
| O-17 | 演进    | —    | readonly 层 2 锁激活（V2 按任务卡字段细化）                                                                                                                                                                                                                                                                                                                                                                                                                                   | 🔴 open                      | V2                       | <br /> | <br /> |
| O-18 | 约束    | P1   | 同站内多并发被统一内存带宽顶起（\~2.8× 恶化）；落地铁律=扇出优先跨站各 1 并发                                                                                                                                                                                                                                                                                                                                                                                                                    | ✅ 已定案                        | 架构导入                     | <br /> | <br /> |
| O-19 | 环境    | —    | 两站模型全卸载 → agent 层 opencode 连 8080 但 `/v1/models` 空无法推理；跨界代码任务另暴露 A 站工作区无 `.venv`（accept pytest rc=127）。4-agent 吃狗粮因此中止                                                                                                                                                                                                                                                                                                                                          | 🔴 open                      | 修环境 + O-13 预置联动          | <br /> | <br /> |
| O-20 | 功能缺陷  | P1   | Invoke-Workspace 同步目标站判定被 PowerShell 动态作用域污染：从 Invoke-Task 调用时 `$HostName` 解析为 SSH 主机串（非 'A'/'B'）→ `$station` 恒回退 'B' → **跨站任务源码流恒错推到 B，A 站任务在空壳工作区跑**（specaudit 卡虚构产物根因）                                                                                                                                                                                                                                                                                       | ✅ 已修复+实机验证                   | 2026-09-05               | <br /> | <br /> |
| O-21 | 性能/超时 | P1   | specaudit 卡 900s 硬超时/`exit1`——**三重返证后真根因尘埃落定**：①外层层 `timeout 900` 强杀正常推进 agent；②曾误判 opencode 对本地 passthrough 模型 64k 硬默认（根因实错）；③**决定性返证**：`/props` 运行时 `n_ctx=65536` 而 `/v1/models` 仅通告 `n_ctx_train=131072` → **服务端 llama-server 实以** **`-c 65536`** **加载**，那条 `exceeds the available context size` 是**服务端 400**，opencode 任何配置都无法抬升。修复=conf `CTX 65536→131072` 重载 A 站 gpt-oss；实机复验 `n_ctx=131072`、specaudit 卡重跑 `RUN_S=502/TASK_RC=0/ACCEPT=1` **全程无 65536 错误** | ✅ 已闭环（服务端 ctx 修复 2026-09-06） | 服务端 `-c 131072` 重载       | <br /> | <br /> |

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

### 附：agent-cli.ps1 PS5.1 编码隐患（2026-09-05 触发并修复）

- **症状**: 脚本加载即抛 ROUTE\_TABLE `Unexpected token '}'`/`assignment expression is not valid`（L42-52），端到端跑不通

- **根因**: 文件无 BOM 且含 UTF-8 中文注释（L39-41），PowerShell 5.1 按 ANSI/CP936 误读，吞掉注释行致 hashtable 错乱（运行时行号偏移 2 佐证）

- **修复**: 文件前插入 UTF-8 BOM（字节级 `0xEF 0xBB 0xBF` 前置，内容/LF 不变），ParseFile 归零 + 运行时恢复正常

- **教训**: `.ps1` 涉非 ASCII 一律保证 UTF-8 BOM；编辑后先 ParseFile 网关再跑

### O-02：workspace --archive 占位

- **证据**: CHECKLIST §7.2 P3（L214-216 echo stub）；R7 语义（archive 前不动站上记忆）已保守满足

- **方案**: 二期演进为正式归档（tar 打包 + 清理）

- **关闭判据**: `workspace --archive` 落地站上工作区归档目录 + 记忆不被动

### O-03：probe 产物证据腐化

- **证据**: CHECKLIST §7.2 P3；验收轮全盘递归搜索无 probe 实体；agent-runs.log 仅 3 行无 probe 行

- **方案**: 纪律固化——验收产物统一入 `D:\<proj>\agent-out`（A14 起已如此）

- **关闭判据**: 后续所有验证产物均落 agent-out（含 probe 类）

### O-04：ledger 沙箱写被拒

- **证据**: CHECKLIST §7.2 P3；14:50 run 丢台账行，run.json 不受影响

- **方案**: 纪律——wrapper 从非沙箱宿主运行；或台账移 d:\RPC 可写区

- **关闭判据**: 台账行数与 run.json 计数一致（无静默丢失）

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

### O-06：中文路径/文件名未测

- **证据**: CHECKLIST §6 S6——内容级中文已验证（UTF-8 修复），路径/文件名级可选未执行

- **方案**: Cpp\_Hub 试点前补用例（含中文路径样本）

- **关闭判据**: 含中文路径的任务卡端到端跑通

### O-07：zen 限额真实触发

- **证据**: CHECKLIST §4——退出码 7 定义置位，未真实触发（不可预约）

- **方案**: 事件驱动；首次发生即回填实测路径（429/quota → exit 7 + 降级提示命令）

- **关闭判据**: 真实触发一次并回填证据

### O-08：后端并发探测（F1 降级项）

- **证据**: DESIGN §11.3——MVP 观测先行 queue\_s 被动记录；探测模块系后续升级项目（Scott 2026-09-03 批准降级）

- **触发条件**: queue\_s 数据显示排队成为常态

- **方案**: 调 /slots + 槽位占用则拒/等；随 V2/并发 fan-out 实施

- **前置已解除**: P2-1 已修，queue\_s/run\_s 已可观测

### O-09：BS-1 isolate\_db

- **证据**: CHECKLIST BS 门；SQLite 写锁序列化问题成立（并发5.2ms vs 串行3.0ms，busy\_timeout=5000ms 排队非死锁）

- **L1 验证判据**: 隔离后并发两写耗时 < 现役基线；busy 命中归零

- **方案**: 并行写任务各自 `XDG_DATA_HOME` 隔离 db

- **关闭判据**: L1 判据通过 → V2 fan-out 前置解除

### O-10：BS-2/跨站 编排层并发 HTTP

- **证据**: CHECKLIST §2.6 BLINDSCAN §8.7.5/§8.7.6——**L1 已通过**

  - BS-2: 直连 gpt-oss 编排层 3 线程并行 52.1s ≪ 串行和 110.9s

  - 跨站: A 串行 4 次 6.8s → A+B 各 2 并发 cross\_wall 4.8s（ratio 0.71 ≤ 1.6）

- **剩余**: L2 端到端（真实 readonly 卡）+ L3 回归

- **方案**: fan-out 优先跨站各 1 并发（同站叠并发被带宽顶起）；跨站走 B:18081→A:8080 隧道

### O-11：跨站扇出 L2/L3

- **L2**: 真实 readonly 任务卡跨站分发端到端

- **L3**: agent-cli-smoke + A 抽检回归

- **前置**: O-10 L1 已过，隧道方案已验证

### O-12：strong accept（golden 测试）

- **证据**: CHECKLIST §7.2 P1b 遗留——accept 用模型自写测试属自证通过；强验收应附主控站侧 golden 测试

- **方案**: 任务卡 accept 之外，主控站侧预置独立 golden 判据（实现与测试分离）

- **关闭判据**: 下一任务卡设计时落地 golden 测试

### O-13：G8 环境预置

- **证据**: DESIGN §3.3——R/CRAN noble-cran40 + sympy；wrapper 不感知仅登记

- **方案**: T0 独立批次；Cpp\_Hub 试点前完成

- **关闭判据**: Cpp\_Hub 工作区可编译（依赖就绪）

### O-14：LiteLLM 网关 401 运维遗留

- **证据**: project\_memory 2026-09-04 根因改定——B:4000 401 真凶为**后端换载后 key 不同步**（8080 unsloth 9/4 重载自带 sk-unsloth-\*，litellm 仍 9/3 旧进程写死占位 sk-local-noauth），非最初所记 master\_key 哈希

- **方案**: ①config 改真实 key + 重启 litellm；②拉起 A:8080；或绕网关走直连

- **当前状态**: D6 链路已绕网关直连 B/A:8080（ADR-0002 方案 C），故 O-14 属运维遗留不阻塞 D6

### O-15：claude 路径 + --continue

- **证据**: DESIGN §5.1 二期命令面 + 调研 §9.6-2 Continue-vs-Spawn 决策表

- **方案**: G1 二期；ROUTE\_TABLE 需补 cli 键 + claude 模型条目（现仅 id/station）；铁律 4（`< /dev/null`）已固化

- **关闭判据**: `agent-cli task --cli claude` + `--continue <session>` 可用

### O-16：review --peer / trae 派发

- **证据**: DESIGN §5.1 二期命令面；review --peer 站间互审协议；trae 派发以任务卡 schema 为接口

- **方案**: D7+（站间互审）/ D7（trae 五层循环对接）

### O-17：readonly 层 2 锁激活

- **证据**: DESIGN §4.1 层 2；schema 字段在，MVP 仅记录（全部按排它）

- **方案**: V2 按任务卡 readonly 字段细化（共享/排它语义）

- **前置**: O-09/O-10（并发能力）解锁后才有并行场景

### O-18：同站并发带宽约束（已定案）

- **证据**: BLINDSCAN §8.7.6 + CHECKLIST——同站内 2 并发 1.7→4.8s（\~2.8× 恶化），收益纯来自跨站分摊

- **结论（铁律）**: 扇出优先跨站各 1 并发，勿同站叠并发

- **状态**: ✅ 已定案并导入 ARCHITECTURE §4

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
