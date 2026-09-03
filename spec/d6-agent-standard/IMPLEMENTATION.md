# 实施方案：D6 agent-cli wrapper MVP

***

id: d6-agent-standard-IMPLEMENTATION
type: implementation
version: 1.1
status: draft（Step 6 review 修正后）
date: 2026-09-03
depends: \[d6-agent-standard-DESIGN v1.3 (approved 2026-09-03, 含 F1 定案)]
upstream: \[d6-agent-standard-DESIGN]
-------------------------------------

> **Feature**: 主控站 agent-cli wrapper MVP（workspace + task 两命令，opencode 单路径）
> **Spec 步骤**: Step 5-6
> **基于设计**: [DESIGN.md](./DESIGN.md)（v1.3；并发模型 §4.1 / 契约 §6 / 不变式 §9 为实施锚点）
> **真值源**: 模型路由与 CLI 边界以调研 §2.1/§9.4 实测层为准（审计 R3/R11 遗产）
> **v1.1 修正记录**（Step 6 review）：M1 契约哈希三字段落地 / M2 A5 判据改同文件并发写 / M3 重资产预置通道归属 / M4 --attach 传输方案 / m1 readonly 记录 / m2 A13 网络失败注入方式

***

## 1. 版本基线（实施锚点，全部现状实测 2026-09-02/03）

| 组件 | 版本/状态 | 锁定机制 | 对实施的影响 |
| --- | --- | --- | --- |
| B 站 opencode | 1.18.25 | opencode.jsonc autoupdate=false | stdin 管道铁律（位置参数 bug G10） |
| A 站 opencode | 1.18.25 | snap hold=forever | 同上 |
| 两站 claude code | 2.1.258 | DISABLE_AUTOUPDATER=1 | MVP 不走 claude 路径（仅铁律 4 预留） |
| 内核 | A 6.17.0-40 / B 6.17.0-23 | GRUB 钉 + 六元包 hold | flock 依赖 util-linux，Ubuntu 自带 |
| 两站默认模型 | opencode/nemotron-3.5-lightning-free | 手册 §2a.4 纪律 | wrapper 永远显式 -m（不变式 3） |
| 主控站 tar | Git Bash GNU tar（`C:\Program Files\Git\usr\bin\tar.exe`） | — | **不用 Win10 内置 bsdtar**（无 -X 排除文件支持，见兼容矩阵 S1） |
| 主控站 ssh/scp | Win10 OpenSSH 内置 | — | R14 铁律：远端命令一律脚本落盘 |
| 试点项目 | D:\Paper（177 pytest） | git 仓库 | V0 手工工作区 + T5 端到端 |

## 2. 版本控制

| 交付物 | 位置 | git |
| --- | --- | --- |
| agent-cli.ps1（wrapper 主体） | `d:\RPC\ops\station-bin\agent-cli.ps1` | ✅ 入 git（与 agent-cli-smoke.sh 同目录） |
| .agentsync 四型模板 | `d:\RPC\ops\station-bin\agentsync-templates\{python,cpp,doc,lean4}` | ✅ 入 git |
| 测试任务卡样例 | `d:\RPC\spec\d6-agent-standard\test-cards\`（V0/A 验收用） | ✅ 入 git |
| 站上产物 | `~/agent-workspaces/<proj>/**`（.agent-lock/.agent-state.json/out/） | 不入 git（部署产物，同 station-bin 约定） |
| 台账 | `d:\RPC\ops\station-bin\agent-runs.log` | 不入 git（运行时数据；入 .gitignore） |

## 3. agent-cli.ps1 内部结构（单文件，PowerShell 5.1 兼容）

```powershell
agent-cli.ps1
├── param 块（$Command, $Proj, $Card, $Model, $Cli, $Sensitivity, $Timeout, $Attach）
├── $ROUTE_TABLE（哈希表，编译期固化 §9.4 路由：nemotron→B, gpt-oss→A, lightning/ultra→Zen 免费, 拒绝未知）
├── Invoke-RemoteScript（R14：本地生成 /tmp/agent-cli-run-<ts>.sh → scp → ssh bash）
├── Invoke-Workspace（M1：tar 打包[.agentsync 过滤]→scp→远端解包；--create 建骨架）
├── Invoke-Router（M3：拒绝规则 → sensitivity 检查 → sanitized scrubber → 调用参数）
├── Invoke-LockState（M4：flock -n 获取 → .agent-state.json 读写 → 孤儿检测）
├── Invoke-Task（M2 全链编排）与 Invoke-Collect（M5：out/ tar 拉回）
├── Write-RunJson（.agent-run.json 归一，DESIGN §6.2 schema）
└── exit code 分派（2/3/4/5/6/7，DESIGN §8）
```

**关键实现约定**：
- **远端脚本模板**（Invoke-RemoteScript 生成）：`cd <workspace> && flock -n .agent-lock -c '<状态写+执行体>'` 或 flock 独占文件句柄模式；执行体含 `timeout <N>` 包裹 opencode 调用（超时 kill 在远端完成，主控站只读退出码）
- **opencode 调用**：`echo '<prompt>' | opencode run -m <model> --format json`（铁律 1；prompt 由任务卡正文 + `[proj:<name>]` 前缀 + audit 注入拼接，经远端脚本 heredoc 传入避免引号地狱）
- **queue_s/run_s 分离**：脚本内记录 flock 获取前/后两个时间戳（DESIGN §6.2）
- **Prompt 拼装在主控站**（sensitivity 检查/scrubber 必须在离开主控站前完成——不变式 2），远端脚本只接收已消毒文本

## 4. 兼容矩阵（接缝与对策）

| # | 接缝 | 风险 | 对策 |
| --- | --- | --- | --- |
| S1 | PowerShell ↔ tar 排除清单 | Win10 内置 bsdtar 无 `-X` | 调用 Git Bash GNU tar 全路径（D5 实证 Git Bash 存在）；.agentsync 逐行转 `--exclude` 参数（上限 64 行，超限报错提示精简） |
| S2 | PowerShell ↔ ssh 引号（R14） | 内联命令引号被 PS 展开 | 全部远端逻辑走脚本落盘（Invoke-RemoteScript 是唯一 ssh 出口） |
| S3 | flock 跨 ssh 会话语义 | 两个独立 ssh 连接是否互斥未验证 | V0-6 前置验证；不通过改道 mkdir 原子锁（DESIGN §11.1） |
| S4 | opencode --format json 输出 schema | 1.18.25 字段名未实测（session_id/usage 字段可能缺失） | T3 解析层做字段缺省容错；.agent-run.json 允许 null（schema 注明可选字段） |
| S5 | 免费档限额（G13） | 429/quota 报文格式未知 | 退出码 7 + 台账累计；首次触发后回填报文样例到本文件 |
| S6 | 中文路径/文件名跨 scp | tar 打包乱码 | 统一 UTF-8（tar 由 Git Bash 执行，locale 继承 Git Bash UTF-8） |
| S7 | 任务卡 front-matter 解析 | YAML 子集够用但边界（多行/引号） | 自写极简 parser 仅支持 `key: value` + accept 列表（schema 已冻结 DESIGN §6.1）；复杂值报错拒绝 |
| S8 | --attach 附件传输（M4） | 大附件撑爆 tar/scp | 独立打包 ≤50MB/文件；超限拒绝（退出码 2）提示分片；.attach/ 生命周期=单次 task（结束即回收） |

## 5. 性能预算

| 指标 | 预算 | 依据 |
| --- | --- | --- |
| workspace --sync 增量 | < 60s（<10MB 项目子集） | tar+scp USB4/千兆管理网实测 ~600MB/s 量级（glm 冷移先例） |
| task 端到端（不含模型生成） | < 30s 开销（sync+lock+collect） | 各环节秒级；生成时间由 timeout 900s 界定 |
| wrapper 脚本执行开销 | < 2s（纯 PowerShell 解析） | 单文件无模块加载 |
| 超时默认 | 900s（任务卡可覆盖） | DESIGN §4.5；B-claude 冷启动不在 MVP 路径（opencode 单路径） |
| queue_s 观测精度 | 秒级（date +%s 差值） | F1 定案：观测先行，非毫秒级需求 |

## 6. 阶段实施（T0-T5）

### T0：V0 六门手动验证（前置，不改任何 wrapper 代码）

用 ssh 手工在 B 站建最小工作区 `~/agent-workspaces/v0probe/`（AGENTS.md 写入标记句 + CLAUDE.md 薄壳 + .agent-lock 空文件），逐门跑验收命令（见 §7 A1-A6）。**任一门不通过 → 记录 + 走 DESIGN §11.1 改道列 + 回灌 DESIGN，不硬闯。**

### T1：M1 workspace（骨架 + 同步）

- agent-cli.ps1 骨架（param/ROUTE_TABLE/Invoke-RemoteScript 空转：远端 echo 探活）
- Invoke-Workspace：--create（建骨架含 AGENTS.md/CLAUDE.md 薄壳/.agentsync[out/ 排除]/out/）+ --sync（tar 排除推送）
- .agentsync 四型模板落盘（python: `__pycache__/ .venv *.egg-info raw_md/ new_papers/ *.duckdb`；cpp: `build/ third_party/ *.o`；doc: 空；lean4: `.lake/`）。**重资产预置通道归属（M3）**：cpp 型排除 `third_party/` 后站上缺编译依赖——`workspace --preset <tar>` 子命令（一次性推送重资产到 `~/agent-workspaces/<proj>/third_party/`，不计入常规 sync）**列 G8/G9 T0 批次实施**（与 R/CRAN sympy 预置同批，DESIGN §11.3 分期移交）；MVP 试点 Paper（python 型）不涉及，Cpp_Hub 试点前必须先过该批次
- 验收：A7

### T2：M3 router + M4 lock/state

- Invoke-Router：三拒绝规则（退出码 2/4/2）+ sanitized scrubber（正则清单：密钥模式 `sk-[A-Za-z0-9]{16,}`/邮箱/绝对路径 `D:\\`/`F:\\`；gitleaks 若主控站有则挂，无则纯正则版）
- Invoke-LockState：flock -n 获取/释放 + .agent-state.json 写 + 孤儿检测（running + PID 死 → 归档 orphaned）
- **readonly 记录（m1）**：任务卡 readonly 字段解析后写入 .agent-run.json（DESIGN 层 2 语义——MVP 仅记录不生效，全部按排它处理）；V2 激活时无需改 schema
- 验收：A8（路由拒绝）、A9（锁互斥）、A10（孤儿恢复）

### T3：M2 task 全链 + M5 collect

- Invoke-Task：sync→lock→run→collect→unlock 串联 + 远端执行体（timeout 包裹 + stdin 管道 + queue_s/run_s 时间戳）
- Write-RunJson：DESIGN §6.2 schema 落 out/.agent-run.json（S4 容错）。**契约哈希三字段（M1，不变式 5 落地）**：主控站计算 `prompt_sha256`（消毒后终版 prompt）+ `attach`（每个附件路径+sha256 对）+ 远端回收后计算 `content_digest`（agent 输出全文 sha256）——三字段任一为空即验收失败（A11 判据含此项）
- **--attach 传输（M4）**：attach 文件随 Invoke-Task 前置的附加 sync 传站——独立 tar 打包（不做 .agentsync 过滤，但限单文件 ≤50MB）→ scp 至工作区 `.attach/<ts>/` → prompt 中引用相对路径 `.attach/<ts>/<file>`；task 结束后 .attach/ 随 collect 一并回收，工作区不留副本
- Invoke-Collect：out/ tar+scp 拉回 `<proj>\agent-out\<ts>\`
- 台账 agent-runs.log 追加（CSV 一行：ts,proj,model,sens,exit,run_s,queue_s）
- 验收：A11（端到端 B 站本地模型）、A12（免费档路由 + 契约完整）

### T4：错误路径全家 + 冒烟扩展

- 超时（kill+failed{timeout}）/ ssh 断重试 1 次（门禁缓存语义：重试不重走 scrubber）/ 退出码全分派（2/3/4/5/6/7）
- agent-cli-smoke.sh 增补第四节：agent-cli task 端到端探活（G14 升级回归三件套之一）
- 验收：A13（错误注入）

### T5：Paper 试点端到端 + 收尾

- D:\Paper 建区（python 型 .agentsync）→ 真实任务卡（`model: nemotron, sensitivity: local-only, accept: pytest`）→ 跑通 → 产物回收
- 手册 §2a 增补 agent-cli 命令节；台账 §1.8 联动；CHECKLIST.md 全回填
- 验收：A14（试点闭环）

## 7. 验收标准（命令化，全部可脚本执行）

| # | 验收项 | 命令/判据 |
| --- | --- | --- |
| A1 | V0-1 薄壳导入 | B 站 v0probe 工作区 `echo 'AGENTS.md 里写了什么标记句? 按原文回答' \| opencode run` → 回答含标记句 |
| A2 | V0-2 遮蔽 | 工作区放 `.claude/skills/proj-test/SKILL.md` → 会话可见且不被用户级同名遮蔽 |
| A3 | V0-3 cwd 键控 | 在 v0probe 跑 memory_add_note → 换 /tmp 起新会话提问 → **不**复述 v0probe 笔记 |
| A4 | V0-4 A 站记忆 | A 站工作区 memory_add_note → 新会话能复述 |
| A5 | V0-5 Bash 不锁 | 双 ssh 会话**同目录**并发写：`ssh1 'echo \| opencode run "往/tmp/v0probe/test.txt追加一行A"' & ssh2 'echo \| opencode run "往/tmp/v0probe/test.txt追加一行B"'` → 文件存在、两行内容可读且**无损坏/无空文件**（注：M2 修正——原判据"写两个不同文件"测不出并发写冲突假设，必须同文件/同目录） |
| A6 | V0-6 flock 跨 ssh | ssh1 `flock -n ~/agent-workspaces/v0probe/.agent-lock -c 'sleep 30' &`；ssh2 `flock -n ... -c 'echo got'` → ssh2 失败退出 |
| A7 | workspace 建区 | `.\agent-cli.ps1 workspace paper --create` → B 站目录含四件套（AGENTS.md/CLAUDE.md/.agentsync/out/）+ md5 与主控站一致 |
| A8 | 路由拒绝 | `task --model 不存在` 退出码 2；`--sensitivity local-only --model opencode/nemotron-3.5-lightning-free` 退出码 4 |
| A9 | 锁互斥 | 后台跑长 task，并发第二个 → 退出码 3 且报占用者 PID |
| A10 | 孤儿恢复 | 手动 kill 远端进程 → 再跑 task → 检测 orphaned + out/ 归档 + 新任务成功 |
| A11 | 端到端本地 | `task paper --card test-cards/echo.md --model nemotron` → 退出 0 + .agent-run.json 契约字段齐（**含 M1 哈希三字段非空：prompt_sha256/attach/content_digest**）+ agent-out\<ts>\ 有产物 |
| A12 | 免费档契约 | 同卡 `--model lightning` → .agent-run.json model 字段=opencode/... + 台账一行 |
| A13 | 错误注入 | timeout_s: 5 卡死循环任务 → 退出码 6 + state=failed{timeout}；网络失败用 wrapper 可控注入模拟（无效 SSH 端口/断开网卡隧道——**禁止杀 sshd**，m2 修正：sshd 是站级服务，动它会误伤全站连接）→ 验证重试 1 次语义 |
| A14 | Paper 试点 | 真实任务卡跑通 → pytest accept 判据输出回收 + 主控站 git diff 无越界文件（单向流不变式 6） |

## 8. 风险表（含回滚动作）

| # | 风险 | 概率 | 回滚 |
| --- | --- | --- | --- |
| R1 | V0-6 flock 跨 ssh 证伪 | 中 | 改 mkdir 原子锁（DESIGN 已备改道）——T2 实现即切换 |
| R2 | S4 opencode json 字段缺 | 高 | 契约字段容错 null + T5 后补实测样例回填 schema 注记 |
| R3 | 免费档限额打满（试点期） | 中 | 试点任务卡默认 model: nemotron（本地）；免费档仅 A12 冒烟用一次 |
| R4 | scrubber 正则误杀（假阳性） | 低 | sanitized 拦截时打印命中行（脱敏后）供人工确认；白名单机制留 V2 |
| R5 | PowerShell 5.1 兼容性（哈希表/JSON） | 低 | ConvertFrom-Json/ConvertTo-Json 均为 PS5.1 内置；禁用 PS7 专属语法 |
| R6 | 站断电 mid-task | 低 | 孤儿检测（A10 已验收）+ out/ 归档不删 |
| R7 | wrapper 本身 bug 破坏工作区 | 低 | 单向流不变式 6（out/ 永不被覆盖推送）；workspace --archive 前不动站上记忆 |

## 9. 对 CHECKLIST 的输入

- T0-T5 每阶段完成即回填 CHECKLIST.md（含 A1-A14 逐项证据：命令输出摘要 + 时间戳）
- G14 回归三件套并入既有升级窗口流程（agent-cli-smoke.sh 第四节随 T4 交付）

***

**实施签字**: _________ 日期: _________
