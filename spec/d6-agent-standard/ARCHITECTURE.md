# 架构文档：D6 agent-cli wrapper MVP

***

id: d6-agent-standard-ARCHITECTURE
type: architecture
version: 1.1
status: approved（与 DESIGN v1.4 / IMPLEMENTATION v1.2 实况对齐，2026-09-04；v1.1 补复杂度路由 M3/契约字段 + wrapper 稳定性 preflight/exit12，2026-09-07）
date: 2026-09-04
depends: \[d6-agent-standard-DESIGN v1.4 (approved), d6-agent-standard-IMPLEMENTATION v1.2, d6-agent-standard-CHECKLIST v1.0 (验收通过)]
upstream: \[d6-agent-standard-DESIGN, ADR-0002]
-------------------------------------

> **Feature**: 主控站 agent-cli wrapper MVP 的系统架构（工作区 + 任务卡 + 并发锁 + 敏感路由 + 跨站扇出）
> **状态**: approved（以已验收实现为准，非纸面设计）
> **真值源**: 与 IMPLEMENTATION §3 代码结构逐模块对齐；并发模型/退出码/契约 schema 以 DESIGN §4/§6/§8 与 CHECKLIST A1-A16 实测为准
> **本文件定位**: 单一入口描述系统「是什么」「怎么动」「边界在哪」，供维护者/后续 D7 开发者快速建立心智模型，不复述 DESIGN 的论证过程
> **跨项目标准引用**: D6 为多任务项目统一 agent-cli 调用标准（DESIGN 顶层目标），跨项目工作规范（立项→设计→派发→跨站执行→验收→入档五层）见 [CROSS-PROJECT-WORK-STANDARD.md](./CROSS-PROJECT-WORK-STANDARD.md)；三站执行规范调研输入见 [RESEARCH_2026-09-12_Cpp_Hub_3station.md](./RESEARCH_2026-09-12_Cpp_Hub_3station.md)。

***

## 1. 系统边界

```
                    ┌──────────────────────────────────────────────────┐
                    │                  主控站 Win10                    │
                    │                                                  │
                    │   agent-cli.ps1 (PowerShell 5.1 单文件 wrapper)   │
                    │   ├─ workspace / task 两命令面                    │
                    │   ├─ ROUTE_TABLE（模型别名→完整ID→站/网关 编译期表）│
                    │   ├─ 三档敏感路由 + sanitized scrubber            │
                    │   └─ 契约归一 .agent-run.json                      │
                    └──────────────┬───────────────────────────────────┘
                                   │  tar+scp / ssh（R14 脚本落盘铁律）
                    ┌──────────────┴───────────────────────────────────┐
                    │               A/B 站 Ubuntu                       │
                    │   ~/agent-workspaces/<proj>/                      │
                    │   ├─ .agent-lock      (flock 排它锁)              │
                    │   ├─ .agent-state.json (状态机)                    │
                    │   ├─ AGENTS.md + CLAUDE.md(薄壳)                  │
                    │   ├─ .agentsync       (排除清单)                  │
                    │   ├─ out/             (产物回收)                  │
                    │   └─ 项目文件子集                                  │
                    │   cwd=工作区 → opencode run -m <model> < .prompt   │
                    │   记忆: cwd 键控自动隔离                           │
                    └──────────────────────────────────────────────────┘
                                   │
                    ┌──────────────┴───────────────────────────────────┐
                    │  模型后端（按 M3 路由）                              │
                    │  ├─ 本地: A:8080 gpt-oss / B:8080 nemotron(直连)   │
                    │  ├─ 免费档: opencode → Zen 网关(美国托管, 出站)      │
                    │  └─ 跨站扇出: B ssh -NL 18081:127.0.0.1:8080 → A   │
                    │     (⚠ 2026-09-15 现状: 已改为 agent-cli --RemoteHost │
                    │      <站> + 站内 _station_ready.sh 自发现引擎端口,   │
                    │      无需隧道; 且 B:18081 现被 conf davidau-q38-    │
                    │      27b-q4k 声明占用)                              │
                    └──────────────────────────────────────────────────┘
```

**边界职责**（继承 DESIGN §3.3）：
- **职责内**：wrapper 编排、工作区生命周期、任务卡/契约/状态机、并发锁协议、敏感路由、.agentsync 模板
- **职责外**：两站 CLI 生态（D5）、模型加载与网关（infer-load）、trae 派发与站间互审（D7）、模型选型（model-eval）
- **D7 那两项已不再是"待定"**（2026-09-23 补）：`review --peer` 与 `trae 派发` 的**路线、阶段、依赖图与退出判据已定稿** ⇒
  后续 D7 开发者**从这里接着读**：[D6/D7 升级路线总表](../../docs/2026-09-23_D6-D7分阶段执行方案.md) **§4**（`D7-P0` 定案 → `D7-P1` 统一基座 → `D7-P2` 机械门与结论契约 → `D7-P3` 权限与编排 → `D7-P4` 多轮与收束）；
  **D6/D7 的边界判据**（`B-1` 需非产出方给结论 / `B-2` 需同产物多轮 / `B-3` 仅本次派发内的质量门）见 [D7 调研合并稿](../../docs/2026-09-23_D7调研_立项·机制·统一基座.md) **§1**。

## 2. 模块划分（对应 IMPLEMENTATION §3 代码结构）

| 模块    | 职责                                  | 输入                       | 输出                             | 依赖        |
| ----- | ----------------------------------- | ------------------------ | ------------------------------ | --------- |
| M1 workspace | 建区/同步/归档（tar+scp 推拉 + .agentsync 过滤） | proj 名, .agentsync       | 站上工作区目录                        | scp/ssh   |
| M2 task | 全链编排：sync→lock→run→collect→unlock      | 任务卡/命令行参数                | .agent-run.json + out/ 产物        | M1,M3,M4,M5 |
| M3 router | 模型→站映射 + 三档敏感路由 + 拒绝规则 + sanitized scrubber + **复杂度路由（Resolve-Profile）** | model, sensitivity, cli, complexity, taskType | 目标站+调用参数 + 推理参数档（context/max_output/thinking/flavor） | ROUTE_TABLE(编译进代码) |
| M4 lock/state | flock 获取/释放 + 状态机（孤儿检测）             | 工作区路径                    | 锁句柄 / .agent-state.json          | ssh        |
| M5 preflight+collect | **Preflight**（Assert-AgentOutWritable 探针，失败 exit 12）+ **collect**（逐件回收证据 + ledger 先行 + collectOk 保护 + **失败时保留 TEMP 件并打印 `EVIDENCE_LEFT_IN_TEMP=`**；2026-09-16 ADR-0005：5 个小件**合批单连接**回收） | 工作区路径 + projRoot | 主控站 <proj>/agent-out/<ts>/（**9 件**，见 §6 表）+ agent-runs.log 一行 | scp + 合批 base64 |
| 契约层    | .agent-run.json 归一（哈希三字段 + `accept_golden.sha256/base` + 观测字段；**实现为内联**，无独立 `Write-RunJson`） | 执行结果 + 时间戳               | run.json                          | 内联于 Invoke-Task / Invoke-Task-Claude |

**代码结构**（单文件幂等锚点，实施以 IMPLEMENTATION §3 为准，此处仅列边界）：
- `Invoke-RemoteScript`：唯一 ssh 出口，本地生成 `/tmp/agent-cli-run-<ts>.sh` → scp → `ssh bash`，杜绝 PowerShell 引号展开
- `Invoke-Workspace` / `Invoke-LockState` / `Invoke-Task` / `Invoke-Collect`
- `Invoke-Router`：拒绝规则 → sensitivity 检查 → scrubber → 调用参数
- `Resolve-Profile`（M3 内）：复杂度/题型 → 推理参数档（§6.4）
- `Assert-AgentOutWritable`（M5 前置）：agent-out 写探针，失败 return false
- `Write-RunJson`：契约归一
- exit code 分派：2/3/4/5/6/7/12（§5）

## 3. 数据流（task 单次执行）

```
任务卡解析 → M3 路由（sensitivity 检查 → model→站映射 → 消毒 → 参数拼装）
  → 复杂度路由 Resolve-Profile（PROFILE 干跑输出；L1-HINT 提示实例风味匹配，不改引擎）
  → M5 preflight（Assert-AgentOutWritable 探针；失败 → ABORT exit 12，提示 Settings UI）
  → M1 sync（tar 排除 .agentsync → scp → 解包; 首跑 --create 建区）
  → M4 取锁（flock -n; 失败 → 报占用者 PID 退出 3）
  → M4 写状态 running{pid, ts, task_id}
  → ssh 执行（本地生成远端脚本 → scp → `ssh bash`）
     opencode: echo "<prompt>" | opencode run -m <model> --format json
     [prompt 注入: [proj:<name>] 前缀 + 任务卡正文全文 + audit 契约(audit:true)]
  → 契约归一 .agent-run.json 落 out/（§6.2 schema）
  → ledger 先行（写 agent-runs.log，LEDGER_WARN try/catch）
  → M5 collect（out/ tar+scp 拉回主控站 <proj>/agent-out/<ts>/；collectOk 保护，失败打 COLLECT_FAIL + run.json.collect=failed）
  → M4 写状态 done + 释放锁
```

**关键不变式沿链**：
- prompt 在**离开主控站前**完成消毒（不变式 2）——scrubber 是 M3 内多出的前置门，不在远端重复
- out/ 单向流（不变式 6）：站上→主控站只回收 out/，永不以 out/ 反向覆盖主控站源文件
- 一切发给模型的输入落 .agent-run.json 哈希（不变式 5）

## 4. 并发模型（G11 双层锁，DESIGN §4.1）

```
层 1（粗，MVP 生效）: 工作区级排它锁 flock
  ~/agent-workspaces/<proj>/.agent-lock
  任何 task 执行前必须获得，执行期间持有，释放先写 done
  互斥面: wrapper-vs-wrapper（已验证 V0-6）
  ⚠ 已知边界: 不互斥 wrapper-vs-手动TUI（纪律告知缓解, F4 登记为 MVP 风险）

层 2（细，V2 才激活）: 任务卡 readonly 声明 【**2026-09-12 激活，DESIGN §4.1 / O-17 已闭环**】
  readonly: true  → 共享语义（research/分析可并行 fan-out）
  readonly: false → 排它语义（implementation 独占）
  实现: task $body 锁段按 readonly 选 flock 模式——readonly→`flock -s`（共享）/ 写→`flock -n`（排它），
  Codex RwLock 语义（读锁并行/写锁独占）；`LOCK_ACQUIRED/HELD` 行带 mode=shared|exclusive 可观测。
  锁与调度解耦: 真并发度由 slot-gate(O-25)+O-18 纪律约束，锁仅保证写安全。
  验证: 三断言互斥探针(RR/RW/WW)+ readonly/write 双路 e2e（run 2026091219355/2026091219415）全 PASS
```

**后端并发实况（2026-09-04 L1 实测，架构级输入）**：
- 两站 llama-server slots=1（is_processing 互斥）→ 同站多请求在后端排队
- **同站内 2 并发被统一内存带宽顶起**（单请求 1.7→4.8s，~2.8× 恶化，BS-2 L1）
- **跨站扇出真并行**（A+B 各 2 并发：A 串行 4 次 6.8s → cross_wall 4.8s，ratio 0.71；L1 实测源 `_bs2_cross.py` targets=[A,B,A,B]）
- **落地铁律：fan-out 优先跨站各 1 并发，勿同站叠并发**；~~跨站接入用 B 站 `ssh -NL 18081:127.0.0.1:8080` 无侵入隧道~~ → **2026-09-15 现状：跨站派发走 `agent-cli ... --RemoteHost <站>`（每站独立子进程 + 站内 `_station_ready.sh` 自发现引擎端口），隧道方案已不用**——`_bs2_fanout.py`/`_bs2_cross.py` 已按 ADR-0004 清减删除，且 B 站 18081 已被 conf `davidau-q38-27b-q4k`（llama-single）声明占用，隧道端口不再空闲。**并发铁律本身仍然有效**（跨站各 1 并发、勿同站叠）
- **单机形态同样适用（O-24 ④ 入册）**：单机独立跑多任务时也勿就地叠并发（同一带宽顶起 ~2.8×），应串行派发/手动限流；O-18 铁律无跨站豁免。并发纪律见手册 §2 agent-cli「并发纪律」。

## 5. 控制流（异常路径与退出码）

| 场景                          | 处理                                  | 退出码   | 验收证据            |
| --------------------------- | ----------------------------------- | ----- | --------------- |
| model 缺失/不在路由表               | 拒绝，无隐式默认                           | 2     | A8              |
| 锁占用                         | 报占用者 PID/task_id 即退                 | 3     | A9              |
| sensitivity 冲突（local-only+远端） | 拒绝，无覆写通道                           | 4     | A8              |
| ssh 断连                      | 重试 1 次（门禁缓存不重审）→ 终败 NETFAIL    | 5     | A13/A15（PS5.1 NativeCommandError 地雷已绕） |
| 超时                          | kill → failed{timeout} → 释放锁 →        | 6     | A13/A14         |
| zen 限额（429/quota）            | 不重试远端 → 提示切本地模型命令（降级路径）         | 7     | 定义置位，未真实触发      |
| 孤儿（running+死 PID）            | 归档 out/ → orphaned → 允许重取锁          | 0+警告 | A10             |
| accept 判据                    | agent 完成但任一条判据失败 → 整任务 failed     | 9     | A14（ACCEPT_OK 回收） |
| agent-out 不可写                | 前置探针失败 → ABORT，提示 Settings UI        | 12    | D-17（PREFLIGHT-FAIL，实测） |

**重试语义**（F7 适配注记）：仅网络类失败自动重试 1 次（≤2 总尝试）；模型/文件系统失败直接转人工。Codex 原"沙箱拒绝→升级重试"被重释为"网络失败重试"——本系统无沙箱概念，语义等价（都不无限重试）。

## 6. 密钥数据契约

| 类型       | 位置/文件                           | 关键字段                                                    |
| -------- | ------------------------------ | ------------------------------------------------------ |
| 任务卡     | <proj>/task-*.md（随 sync 进工作区）     | proj/task/model/sensitivity/readonly/timeout_s/accept + complexity/task-type（§6.4） |
| 契约归一    | <proj>/agent-out/<ts>/.agent-run.json | 哈希三字段(prompt_sha256/content_digest/attach) + queue_s/run_s + readonly + profile(§6.4) + collect(ok/failed) + accept{cmd,passed} + **accept_golden{cmd,passed,source,hidden_from_model,sha256,base}**（后两项 2026-09-16 ADR-0005 增） + **evidence_manifest**（阶段 1 + **路B 框架件基线合并**，2026-09-18：`subjects[]` = **框架固定件基线 ∪ 卡特有件**，按 `path` 去重（collect 型按 `name`）、**基线优先**。⚠ **语义已变**：阶段 1 是"卡声明什么就照收什么、且仅声明了的卡才落键"；路B 后**每个新 run 一律带此键**（卡**不写** manifest 也得到 `recipe v2`）—— 目的正是把此前 **71/84 个"零声明的 v1 真实 run"**拉进可重放性判定面（实测 `echo.md` 零声明仍得 10 条）。基线清单的**唯一定义点在产出方** `agent-cli.ps1` 的 `Get-FrameworkSubjects`（**不在审计侧** —— cluster.py 的 undeclared 判据仍动态枚举 runDir，故"不维护第二份框架件清单"的纪律不破）；基线**只列该次派发必产出件**：无 accept/golden 的 run 上 `accept-output`/`accept-golden-output` 实测不存在 ⇒ 二者**随门条件注入**（否则每个这类 run 假报 `missing-artifact`）。⚠ **2026-09-22 订正（原文"未覆盖：claude 备路暂不发射本键"已过时/为假）**：实测 claude 路的 run.json **确有本键**（subjects=5：`agent-output`/`prompt`/`stderr`/`card`/`review`，见 `Get-ClaudeFrameworkSubjects`）⇒ **两条路各有一份基线**；同日**基线新增 `review` 件**（`review` 子命令**事后**写 `review.json`）—— 它**非派发必有** ⇒ 走 `ephemeral` 的**第三态**语义（缺席 = 可合法缺席、**不是缺口**；裸列则每个未 review 的 run 都假报）。subject 键 = `name` / `path` / `collect` / `digest` / **`ephemeral`**（3-b-2 增：产物"设计上不进 runDir" ⇒ 审计单列为 `artifact-ephemeral-by-design`，**不是缺口**也不计入可离线复算）—— 卡侧同块内以 `#` 开头的行是注释、被忽略（有回归用例）） + ⚠ **`attach` 形状升级**（缺口 5，2026-09-18）：**有附件的新 run** 为对象数组 `{name, src, kind: file\|dir, files, sha256}`（摘要源于站上清单 ⇒ 落此即**被链钉住**）；**无附件 = `[]`**；**老 run = 名字数组** ⇒ 消费方须兼容两种形状（⚠ **2026-09-22 订正**：原文还写"**与 claude 备路 = 名字数组**"，实测**不成立** —— claude 路（本地支 run `202609220011097576` / `202609220005298044` 与站上支 run `202609221347542756`）**都已是对象数组**，与主路同形状 ⇒ 该分支的兼容负担已消失）。 + **遥测**（缺口 8，2026-09-18）：`session_id` 与 `timestamp_start/end` = **站上 opencode 会话库**那次会话的 id 与 `time_created/updated`；`usage` = `{source, total_tokens, tool_uses, input, output, reasoning, cache_read, cache_write, cost}`（`source` 取 `opencode-session-db` / `unavailable` / `not-collected-claude-path` —— **`0` 与"未采集"必须可区分**）。 + **卡身份**（ADR-0007 前置，2026-09-18）：`card = {path, sha256, bytes, front_matter}` —— 摘要为卡的**原始字节**（`Get-FileHash`，任何工具可独立复核）；**卡是最大的注入物**（决定 prompt/验收/golden/manifest 本身），此前 run.json/.meta 都不记卡 ⇒ 复跑无法定版。⚠ 无 front-matter 卡会**静默退化**（`readonly=false` / `sensitivity=public` / 无 accept-golden / 无 manifest ⇒ **验收本身消失**）⇒ 派发侧**要求显式 `-Sensitivity` 才放行**，`front_matter=false` 即该 run 走了这条路径 |
| **证据件**（2026-09-16 ADR-0005 / 09-18 ADR-0007） | <proj>/agent-out/<ts>/ | `agent-output.txt` / `accept-output.txt` / `accept-golden-output.txt` + **`judgment-record.txt`（远端 `.meta` 原文）/ `progress-trace.txt`（节拍原文）/ `prompt.txt`（输入全文）/ `accept-cmds.txt` / `golden-cmd.txt`**（claude 备路另有 `stderr.txt`）+ **`workspace-diff.txt`**（缺口 4：readonly 卡"未越界"载体，远端 `find -newer .run-marker` 产出）+ **`attach-manifest.txt`**（缺口 5：附件**注入字节**的逐文件 `<sha>  <relpath>`，在 agent 运行**前**采样）+ **`session-meta.txt`**（缺口 8：会话库遥测原件，与 run.json 的解析值对账）+ **`card.md`**（卡身份：**卡字节原文** —— 卡会改，只记 hash 无法复跑；含 front-matter，而 `prompt.txt` 只有正文）—— 使验收结论**可复核**而非"wrapper 转述"；由此获得五条自证能力：`sha256(prompt.txt) == prompt_sha256`、`accept_golden.sha256 == 仓库 golden 源哈希`、**附件逐文件哈希 == 主控侧对源文件的独立哈希（跨信任域）**、**遥测 == 会话库另一张表的聚合（跨表）**、**`card.md` 逐字节 == run.json `card.sha256`（且改卡后仍可复原当时版本）** |
| 状态机     | <proj>/.agent-state.json           | state{ running/done/failed/orphaned } + pid + ts_start       |
| 台账      | 主控站 `ops/station-bin/agent-runs.log`（**非** `<proj>/`，2026-09-16 订正） | 观测累计（G13），一行/run；**两处过时标注已于 2026-09-18 订正**：① `queue_s/run_s` 已接线（原 opencode 路径硬编码 `0,0`，缺口 6 闭环）；② diff 证据已闭环（`find -newer` ⇒ `workspace-diff.txt`，缺口 4 闭环）。⚠ **2026-09-22 补（列的语义）**：**`model` 列 = "实际执行身份"** —— 站上 claude 分支写 `station:<站>/<别名>`（如 `station:B/main`，实际跑的是**站上本地引擎**），其余写路由/别名指向的型号 id。**别把 model 当"云端型号"去判"该 run 是否出网"**（此前站上分支写路由 id ⇒ 会给"物理不出网"的 `local-only` run 报一个云端型号；详见 `cluster.py` 台账注释） |
| **审计/校准产物**（ADR-0007 阶段 3 + **路A**，2026-09-18） | **两层 + 水印**：机器产物 ⇒ `<proj>/agent-out/_audits/<ts>.json`（**不入仓**；与 runDir 同级、非数字名 ⇒ 证据链不当 run）；校准报告 ⇒ `spec/d6-agent-standard/evidence-chain/audits/`（**入仓**，人可读，随代码评审走）；**增量水印** ⇒ `ops/.audit-baseline.json`（**本地不入仓**，与 `ops/.egress_daily.json` 同族） | `python ops/cluster.py agent audit [--save\|--accept]`（3-a 可复现性审计）+ `agent audit-judge [--save]`（3-b 异基座校准：A/A / 序对调 / 措辞扰动 / 与判据一致 + "复核 vs 复读"对照）。**严重度严格按 D4**：可重放性缺口属**覆盖缺口 ⇒ 只 WARN，刻意不进 FAIL 集**（D4 原文：报 FAIL 会让判据因噪声被整体忽略）。**`--accept` 是水印的唯写点** —— 门禁 `rpc_check.py` 对仓库**全程只读**（唯一写动作是 `check_syntax` 的 tempfile）+ 门禁挂 pre-commit ⇒ **不能自动写水印**；副作用刻意接受：**"接受新缺口"是人的显式动作**（`--accept` 与 `--json` 因此互斥，exit 2）。**已挂门禁**：`evidence` 断言内（**同进程**，实测 `--only evidence` 0.38→0.393 s）只报**新增** gap、**逐条**打印；水印 = **单调并集 key 集合**（`<kind>\|<label>\|<sub>`，**不含会漂移的文本细节**）。**红线**：机器产物**绝不为每个 run 入仓** |

**观测语义**（P2-1 修复后）：`queue_s` = 获锁→模型启动前（锁等待+入队）；`run_s` = 模型启动→完成（生成墙钟）。A8b 实测 QUEUE_S=2 / RUN_S=31。

## 7. 部署形态与非功能属性

| 属性      | 现状                                                              |
| ------- | --------------------------------------------------------------- |
| 部署形态   | 主控站 PowerShell 单文件 + 站上无程序性安装（工作区/锁/状态均为运行产物）                  |
| 零自加载   | 无常驻 server（否决方案 B）；两站 CLI 用后即停，随任务启停                        |
| 版本锁定   | 两站 opencode 1.18.25 / claude 2.1.258 已锁；wrapper 入 git 随仓库版本     |
| 性能基准   | wrapper 解析 0.40-0.44s；sync 增量 62.3s（微超 60s 预算 4%，P3）；task 端到端 lock+collect ~10s |
| 安全边界   | 三档敏感路由硬门，local-only 字节永不出主控站→本地路径；消毒在出站前完成（机械可验证）         |

## 8. 演进方向（架构预留接缝）

| 方向               | 预留接缝                                                            | 现在状态     |
| ---------------- | --------------------------------------------------------------- | -------- |
| claude 路径        | 铁律 4 已固化 `< /dev/null`；ROUTE_TABLE 需在 G1 补 cli 键 + claude 模型条目                     | 二期 (G1)   |
| --continue        | Continue-vs-Spawn 决策表（调研 §9.6-2）为路由规则                         | 二期 (G1)   |
| readonly 层2锁     | §4 层 2 schema 字段在                                              | V2        |
| 跨站扇出           | ~~B:18081→A:8080 隧道~~ **2026-09-15: 改 `agent-cli --RemoteHost <站>` + 站内自发现端口 (隧道方案弃用)**；路由表可按需加跨站模型名 | 已落地      |
| 后端并发探测         | 触发条件=queue_s 排队成常态；调 /slots + 槽位占则拒/等                        | 升级项 (F1)  |
| `review --peer`     | 站间互审协议 —— **已定稿**：批次见 [路线总表 §4](../../docs/2026-09-23_D6-D7分阶段执行方案.md)（`D7-P2` 机械门与结论契约 / `D7-P3` 权限与编排）<br>⚠ **"跨族"须靠判据保证**：**跨站不自动带来异构**（三站均可走 `openrouter`、可加载不同模型）⇒ 判据 = `judge.family ≠ producer.family` **与** `judge.input ≠ producer.input`（后者 = 盲写的机器化） | D7+       |
| trae 派发          | 任务卡 schema 冻结即接口 —— **已定稿**：见 [路线总表 §4](../../docs/2026-09-23_D6-D7分阶段执行方案.md)（六相 + 三信封，`D7-P0-2` 定案）                                               | D7        |
| 复杂度路由 L0       | per-request 推理参数（enable_thinking/max_tokens），需 vLLM 引擎              | 待 vLLM    |
| 复杂度路由 L1/L2/L3 | 实例风味 preset（nothink/think/long）+ opencode provider limit + prompt 尾注 | **已落地（D-16）** |
| wrapper 稳定性      | Preflight + ledger 先行 + collectOk（D-17）                              | **已落地** |

***

## 9. 记忆层评估：opencode-codex-memory 与本地模型上下文（2026-09-09 源码审计）

> **背景**: C 站插件复刻（B→C）后，评估 codex-memory@0.6.5 是否能解决「本地模型上下文窗口有限条件下处理长任务」。以下基于插件源码逐行审计（`~/.cache/opencode/packages/opencode-codex-memory@0.6.5/dist/src/*.js`），非二手转述。

### 9.1 机制本质（codex 两阶段记忆移植）

| 组件 | 机制 | 源码证据 |
|---|---|---|
| 记忆注入 | 每会话把 `memory_summary.md` **截断至 2500 token** 后注入 system prompt（`experimental.chat.system.transform` hook）| source.js: `MEMORY_SUMMARY_TOKEN_LIMIT = 2500` + `truncateToTokens`；index.js: `output.system.push(memoryPrompt)` |
| 按需检索 | dedicated_tools 下模型**主动调 memory_read/search/list 工具**读 MEMORY.md / rollout_summaries/（支持 line_offset/max_lines 行窗口）| tools/memory.js `memory_read` |
| 记忆生成 | 会话结束/空闲时 `memorize-extract`（提取 transcript→JSON）+ `memorize`（整合 diff→MEMORY.md/summary/skills）两个 **subagent** | opencode.json agent 契约（permission 全 deny，仅 memory 工作区可写） |

### 9.2 能力边界判定（对 D6 本地模型）

| 档位 | 结论 | 依据 |
|---|---|---|
| **✅ 跨会话持久化** | 真实解决「会话边界」——上一会话结论/决策/代码结构沉淀 MEMORY.md，下会话经 2500-token 摘要 + 按需检索取回 | 突破的是会话边界，非上下文窗口；分次会话带关键结论是有效用法 |
| **⚠️ 单会话长任务** | 部分缓解——摘要注入为常数开销（不随任务增长），按需检索不占满上下文；但摘要=压缩损失，且 subagent 整合质量受**同一本地模型**能力上限约束 | 正确架构但对本地模型有质量天花板 |
| **❌ 上下文物理扩大** | 不解决——若任务本身需 100k token 代码驻留，插件只在**会话间隙**生效；单次 `opencode run` 仍撞服务端 ctx 硬上限（O-21 教训） | 注入不影响引擎 `-c` |

### 9.3 对 D6 的落地定位（互补而非替代）

- **记忆插件 = 任务卡之上的一层**：任务卡保证每次 run 在窗口内（O-21 调卡纪律），记忆插件保证多次 run 之间不丢上下文。**两者互补，缺一不可**。
- **适用场景**：跨会话研究/写作（Paper 试点、调研多轮）✅；单会话超长读码/重构（specaudit 类）❌ 须走 O-21 四方向；关键任务（数值/金融正确性）⚠️ 本地记忆整合可能污染，须 accept golden 测试（O-12）兜底。
- **风险登记**：本地模型提取/整合的记忆可能引入错误结论 → 后续会话带错误记忆；subagent 整合为额外算力成本。

### 9.4 DCP（Dynamic Context Pruning）落地：单会话内动态压缩（2026-09-09 社区调研 + C 站冒烟）

> **背景**: 评估 codex-memory 后，调研 opencode 生态"动态压缩"插件（社区反馈良好者），选定 DCP 落地。以下机制基于官方 README + 社区 issue 实测（#552 本地模型对照 / #573 token 燃烧 / #551 stale 边界）。

#### 9.4.1 生态选型（社区实测）

| 插件 | Star | 机制 | 本地模型反馈 |
|---|---|---|---|
| **DCP**（`@tarquinen/opencode-dcp`）| 3000+ | 模型自主调 compress 工具 + 自动去重 + 清除错误输出；只改请求副本不碰会话历史 | ✅ **本地模型实证可用**（qwen3.5-35b 实测正常）；⚠️ 有 bug：compress 反馈循环烧 738K tokens（#573）、stale 边界 ID（#551）|
| **Magic Context**（`@cortexkit/opencode-magic-context`）| 2000+ | 后台 historian 压缩 + 向量 DB + 跨会话记忆 + 衰减渲染 | ⚠️ **本地模型高风险**：qwen 实测首次压缩"脑叶切除"（写意大利语/只回数字 3 和 33）→ 被迫禁用回 DCP（#552）；3 bug 未修（#212）|
| lossless-opencode (LCM) | 小 | SQLite + FTS5/BM25 + 摘要 DAG | 新项目，反馈少 |
| ACM / context-guard / context-manager | — | 活跃上下文边界 / AGENTS.md 运行时注入 / 静态预索引 | 补充角色 |

**选定 DCP 理由**：本地模型实证可用 + 纯动态压缩（不引入跨会话复杂度，codex-memory 已负责记忆）+ 机制保守（只折叠 read/grep/glob/bash 成功输出，不碰用户消息/推理/错误）+ 与 codex-memory 互补（DCP 管会话内、codex-memory 管会话间）。

#### 9.4.2 三站安装与冒烟（2026-09-09）✅

| 站 | 安装 | 验证 |
|---|---|---|
| **C** | `opencode plugin @tarquinen/opencode-dcp@latest --global` → **3.1.15** | 工具注入 `compress` ✅ / 加载无错误 / nemotron 正常返回 |
| **B** | 同命令 → plugin 段追加成功 | 缓存就位 ✅ / dcp.jsonc 生成 ✅ / --print-logs 无错误 |
| **A** | 同命令，但**写入分裂**（新建 opencode.json 而非并入 .jsonc）→ 手动合并 plugin 段 + 删分裂 .json | 缓存就位 ✅ / dcp.jsonc 生成 ✅ / JSON VALID |

- 注册：opencode.jsonc plugin 段（与 codex-memory 并列）+ tui.json ✅（三站同构）
- `dcp.jsonc` 首次 run 自动生成（默认仅 schema）
- ⚠️ A 站坑：`opencode plugin --global` 在已有 .jsonc 主配置时**新建 .json** 而非并入 → 需手动合并（codex-memory 后追加 DCP）并删分裂文件
- 引擎级 run 冒烟在 A/B 站未做（两站无 llama 引擎运行）；安装/配置/加载层已验证完整

#### 9.4.3 职责边界（DCP vs codex-memory vs 内置 compaction）

- **DCP**：单会话内**动态压缩**——模型在 context 接近阈值时自主调 compress 折叠旧工具输出；去重 + 清错误自动跑
- **codex-memory**：跨会话**持久记忆**——2500-token 摘要注入 + 检索工具
- **内置 compaction**：opencode 原生压缩（O-21 治理的 64k 引擎 ctx 问题不受插件影响——**服务端 ctx 仍是唯一硬上限**，插件只在客户端请求副本层面工作）

#### 9.4.4 遗留/风险

- **冒烟仅验证工具注入 + 加载**——真正的动态压缩需长会话触发（模型自主调 compress），待真实长任务（specaudit 类）观察压缩质量（是否"脑叶切除"）
- **DCP 已知 bug**（#573 token 燃烧 / #551 stale 边界）——本地模型场景监控 compress 循环
- dcp.jsonc 当前为默认配置，可按引擎 ctx（131072）调 `compress.maxContextLimit`

***

**架构文档签字**: 与 IMPLEMENTATION 实况对齐（2026-09-04；v1.1 复核复杂度路由 + wrapper 稳定性 2026-09-07）。后续 DESIGN/IMPLEMENTATION 变更命中本架构任一边界/数据流/并发语义时，维护者必须同步更新本文件。