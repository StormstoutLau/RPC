# 架构文档：D6 agent-cli wrapper MVP

***

id: d6-agent-standard-ARCHITECTURE
type: architecture
version: 1.0
status: approved（与 DESIGN v1.4 / IMPLEMENTATION v1.2 实况对齐，2026-09-04）
date: 2026-09-04
depends: \[d6-agent-standard-DESIGN v1.4 (approved), d6-agent-standard-IMPLEMENTATION v1.2, d6-agent-standard-CHECKLIST v1.0 (验收通过)]
upstream: \[d6-agent-standard-DESIGN, ADR-0002]
-------------------------------------

> **Feature**: 主控站 agent-cli wrapper MVP 的系统架构（工作区 + 任务卡 + 并发锁 + 敏感路由 + 跨站扇出）
> **状态**: approved（以已验收实现为准，非纸面设计）
> **真值源**: 与 IMPLEMENTATION §3 代码结构逐模块对齐；并发模型/退出码/契约 schema 以 DESIGN §4/§6/§8 与 CHECKLIST A1-A16 实测为准
> **本文件定位**: 单一入口描述系统「是什么」「怎么动」「边界在哪」，供维护者/后续 D7 开发者快速建立心智模型，不复述 DESIGN 的论证过程

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
                    └──────────────────────────────────────────────────┘
```

**边界职责**（继承 DESIGN §3.3）：
- **职责内**：wrapper 编排、工作区生命周期、任务卡/契约/状态机、并发锁协议、敏感路由、.agentsync 模板
- **职责外**：两站 CLI 生态（D5）、模型加载与网关（infer-load）、trae 派发与站间互审（D7）、模型选型（model-eval）

## 2. 模块划分（对应 IMPLEMENTATION §3 代码结构）

| 模块    | 职责                                  | 输入                       | 输出                             | 依赖        |
| ----- | ----------------------------------- | ------------------------ | ------------------------------ | --------- |
| M1 workspace | 建区/同步/归档（tar+scp 推拉 + .agentsync 过滤） | proj 名, .agentsync       | 站上工作区目录                        | scp/ssh   |
| M2 task | 全链编排：sync→lock→run→collect→unlock      | 任务卡/命令行参数                | .agent-run.json + out/ 产物        | M1,M3,M4,M5 |
| M3 router | 模型→站映射 + 三档敏感路由 + 拒绝规则 + sanitized scrubber | model, sensitivity, cli  | 目标站+调用参数（已消毒文本）              | ROUTE_TABLE(编译进代码) |
| M4 lock/state | flock 获取/释放 + 状态机（孤儿检测）             | 工作区路径                    | 锁句柄 / .agent-state.json          | ssh        |
| M5 collect | out/ 整包回收 + git diff 拉回                 | 工作区路径                    | 主控站 <proj>/agent-out/<ts>/       | tar+scp    |
| 契约层    | .agent-run.json 归一（哈希三字段 + 观测字段）      | 执行结果 + 时间戳               | run.json                          | Write-RunJson |

**代码结构**（单文件幂等锚点，实施以 IMPLEMENTATION §3 为准，此处仅列边界）：
- `Invoke-RemoteScript`：唯一 ssh 出口，本地生成 `/tmp/agent-cli-run-<ts>.sh` → scp → `ssh bash`，杜绝 PowerShell 引号展开
- `Invoke-Workspace` / `Invoke-LockState` / `Invoke-Task` / `Invoke-Collect`
- `Invoke-Router`：拒绝规则 → sensitivity 检查 → scrubber → 调用参数
- `Write-RunJson`：契约归一
- exit code 分派：2/3/4/5/6/7（§4）

## 3. 数据流（task 单次执行）

```
任务卡解析 → M3 路由（sensitivity 检查 → model→站映射 → 消毒 → 参数拼装）
  → M1 sync（tar 排除 .agentsync → scp → 解包; 首跑 --create 建区）
  → M4 取锁（flock -n; 失败 → 报占用者 PID 退出 3）
  → M4 写状态 running{pid, ts, task_id}
  → ssh 执行（本地生成远端脚本 → scp → `ssh bash`）
     opencode: echo "<prompt>" | opencode run -m <model> --format json
     [prompt 注入: [proj:<name>] 前缀 + 任务卡正文全文 + audit 契约(audit:true)]
  → 契约归一 .agent-run.json 落 out/（§6.2 schema）
  → M5 collect（out/ tar+scp 拉回主控站 <proj>/agent-out/<ts>/）
  → M4 写状态 done + 释放锁
  → 本地台账 agent-runs.log 追加一行（G13 观测累计）
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

层 2（细，V2 才激活）: 任务卡 readonly 声明
  readonly: true  → 共享语义（research/分析可并行 fan-out）
  readonly: false → 排它语义（implementation 独占）
  MVP 仅记录不生效（全部按排它处理）; schema 字段在, 语义 V2 启用
```

**后端并发实况（2026-09-04 L1 实测，架构级输入）**：
- 两站 llama-server slots=1（is_processing 互斥）→ 同站多请求在后端排队
- **同站内 2 并发被统一内存带宽顶起**（单请求 1.7→4.8s，~2.8× 恶化，BS-2 L1）
- **跨站扇出真并行**（A+B 各 1 并发：A 串行 4 次 6.8s → cross_wall 4.8s，ratio 0.71）
- **落地铁律：fan-out 优先跨站各 1 并发，勿同站叠并发**；跨站接入用 B 站 `ssh -NL 18081:127.0.0.1:8080` 无侵入隧道

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

**重试语义**（F7 适配注记）：仅网络类失败自动重试 1 次（≤2 总尝试）；模型/文件系统失败直接转人工。Codex 原"沙箱拒绝→升级重试"被重释为"网络失败重试"——本系统无沙箱概念，语义等价（都不无限重试）。

## 6. 密钥数据契约

| 类型       | 位置/文件                           | 关键字段                                                    |
| -------- | ------------------------------ | ------------------------------------------------------ |
| 任务卡     | <proj>/task-*.md（随 sync 进工作区）     | proj/task/model/sensitivity/readonly/timeout_s/accept     |
| 契约归一    | <proj>/agent-out/<ts>/.agent-run.json | 哈希三字段(prompt_sha256/content_digest/attach) + queue_s/run_s + readonly + accept.passed |
| 状态机     | <proj>/.agent-state.json           | state{ running/done/failed/orphaned } + pid + ts_start       |
| 台账      | 主控站 <proj>/agent-runs.log          | 观测累计（G13），一行/run                                      |

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
| claude 路径        | 铁律 4 已固化 `< /dev/null`；ROUTE_TABLE 已含 cli 列                     | 二期 (G1)   |
| --continue        | Continue-vs-Spawn 决策表（DESIGN §9.6-2）为路由规则                         | 二期 (G1)   |
| readonly 层2锁     | §4 层 2 schema 字段在                                              | V2        |
| 跨站扇出           | B:18081→A:8080 隧道已验证；路由表可按需加跨站模型名                            | V2 输入已就绪  |
| 后端并发探测         | 触发条件=queue_s 排队成常态；调 /slots + 槽位占则拒/等                        | 升级项 (F1)  |
| review --peer     | 站间互审协议                                                         | D7+       |
| trae 派发          | 任务卡 schema 冻结即接口                                                 | D7        |

***

**架构文档签字**: 与 IMPLEMENTATION 实况对齐（2026-09-04）。后续 DESIGN/IMPLEMENTATION 变更命中本架构任一边界/数据流/并发语义时，维护者必须同步更新本文件。