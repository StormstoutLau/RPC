# 实施方案：D6 agent-cli wrapper MVP

***

id: d6-agent-standard-IMPLEMENTATION
type: implementation
version: 1.2
status: draft（Step 6 review + 对齐审计修正后）
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
├── $ROUTE_TABLE（哈希表，编译期固化 §9.4 路由 + DESIGN §6.1 别名映射表：nemotron→cluster-litellm/nemotron, gpt-oss→cluster-litellm/gpt-oss, lightning→opencode/nemotron-3.5-lightning-free, ultra/free-1m→opencode/nemotron-3-ultra-free, 拒绝未知——BP-2 修正：别名与完整 ID 双表示统一于此）
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

> **T1 实测补充（2026-09-03，Paper sync 排除配置）**：四型模板是**默认起点**，大源码项目必须配置项目级 `~/.agentsync`（D:\Paper 根目录若存在同名 `.agentsync`，`Get-AgentsyncExcludes` 优先读它，模板作 fallback）。实测 D:\Paper 5.6GB 超 200MB cap 被拒——根因是 `paper_origin/`(2.9GB) + `Paper_Organized_v2/`(2.6GB) 两个纯 PDF 资料库 + 全局 *.pdf(4960 个)。排除后降至 **7.0MB**（远低于 cap，B 站工作区源码齐全 + 0 PDF）。**经验**：① 顶层资料库目录整体排除最有效（`paper_origin/` 等）② 全局大文件类型一字排开（`*.pdf *.caj *.zip *.docx *.dta *.db *...`）③ 编译/缓存产物统一排除（`__pycache__/ .mypy_cache/ *.olean *.pyc .db`）④ 排除语法用 `--exclude=<pat>` 且 `--exclude` 必须置于 tar 位置参数 `.` **之前**（GNU tar 位置语义，非 `--exclude` 可任意放）。Paper 实际排除清单见 `D:\Paper\.agentsync`（paper_origin/ Paper_Organized_v2/ + PDF/caj/zip/office 等类型 + 编译缓存 + .git/tmp/out + D6 内部文件）。T5 Paper 试点因该配置不再因 sync 超限失败。

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

> **T5 实测补充（2026-09-03，A14 试点闭环，A14 PASS）**：真实任务卡 `test-cards/paper-pilot.md`（model nemotron / local-only / accept 双 pytest）已跑通。B 站工作区 opencode 实际创建 `paper_cli/code_check.py` + `paper_cli/tests/test_code_check.py`，accept 门控 pytest `11 passed`，classifier 回归 `29 passed` 独立复核通过，产物回收至 `D:\Paper\agent-out\<ts>\`，main git 无越界（单向流不变式 6）。
>
> **T5 期间 wrapper 三项补齐（A14 前置，均已在 agent-cli.ps1 落地）**：
> ① **accept 判据执行与产物回收（DESIGN §6.1 accept 字段落地，MVP 新增能力）**：Get-FrontMatter 扩展 accept 列表解析（`accept:` 键后 `- cmd` 行）；Invoke-Task 在 opencode 完成后于工作区顺序执行 accept 命令（bash 循环 `eval`，`( cd "$W" && eval "$c" )`），逐条记 ACCEPT_RC 至 `out/.accept-output.txt`，任一条非 0 即 ACCEPT_OK=0 → 远端 exit 9 → 主控站映射 exit 1 / status=failed，且 accept-output.txt 随 collect 回收、run.json 补 `accept.{cmd,passed}` 字段。**注意**：accept 循环内 bash 变量必须全部反引号 `` `$ `` 转义（`$ACCEPT_B64/$c/$arc/$i/$ACCEPT_OK`），否则 PS 双引号 here-string 会展开为空串；自增用 `((i++))` 而非 `i=$((i+1))`（后者 `$(( ))` 被 PS 当子表达式求值报"i not recognized"）。
> ② **Get-FrontMatter UTF-8 读取（PS5.1 默认 ANSI 坑，A14 卡点）**：原 `Get-Content $Path` 在 PS 5.1 以系统 ANSI(GBK) 读 UTF-8 卡，中文 prompt 变乱码（实测 `鏂板 code_check 鏍￠獙...`）→ 模型误判"已有等价功能（normalizer 处理 HTML tag）"只分析不落文件。改 `[System.IO.File]::ReadAllLines($Path, [System.Text.UTF8Encoding]::new($false))` 后中文 prompt 正常，模型正确落盘两个新文件。**教训**：ASCII 卡（echo/timeout）此前不暴露此坑，中文任务卡才触发。
> ③ **远端执行体补 `cd "$W"`（cwd=工作区）**：原 opencode 在 ssh 登录 home 运行（`Invoke-RemoteScript` 的 `bash /tmp/*.sh` 不 cd），读不到项目文件；echo 卡因不读文件未暴露。补 `cd "$W" || exit 5` 后方可让 agent 见 AGENTS.md + 项目源码。
>
> **A14 注记（模型运行时特性，非管线缺陷）**：opencode 写毕解决方案后自跑**全量 470 测试套件**（test_phase2_*）作最终校验，至 92% 被 1800s `timeout` kill（TASK_RC=124 → exit 6，run.json status=failed{timeout}）。交付物正确且 accept 门控通过（A14 判据回收成立），但 agent 因全量自验超过时间预算未以 exit 0 收束。反证 accept 门控独立于 agent 退出状态、仍准确回收判语——设计成立。**运维含义**：nemotron Q4 全量校验 paper 470 测试不现实，任务卡 timeout 需按验证规模给足（或 accept 限定目标子集，本例已限定 test_code_check + test_classifier）。

> **验收修复批（2026-09-03 16:30，验收审查后执行，四项全部实机复验）**：
> ① **P1a sanitized scrubber 落地**：`Invoke-Scrubber` 三模式正则（sk-密钥/邮箱/Win 绝对路径）+ 命中打印脱敏预览；`sens=sanitized` 时 prompt 在主控站编码前过滤（不变式 2）。A8b 植入三类样串实测：远端 .prompt.txt 零明文（grep count=0）+ 模型回复 A8B-PROBE-OK 无 LEAK。
> ② **P1b 任务卡正文传输（修复批新发现，严重度同 P1）**：Get-FrontMatter 原来只传 front-matter task: 一行（A14 时远端 prompt 仅 81 字节），**正文规格全部静默丢弃**——取证：model-authored code_check.py 实现的是 validate_classification（模型自设计）而非卡规格 is_well_formed_code，"11 passed"系模型自写实现+自写测试的自证通过。修复：Get-FrontMatter 补 body 捕获，prompt = [proj:] + task 行 + 正文全文（A8b 实证 469 字符完整到达远端）。**教训**：echo/timeout 类无正文依赖的测试卡永远暴露不了此缺陷；验收卡必须含正文依赖。
> ③ **P2-1 queue_s/run_s 语义修复**：远端脚本 R0/R1 双时间戳（R0=opencode 启动前、R1=完成），queue_s=(R0-Q0)/1e9（锁等待+入队）、run_s=(R1-R0)/1e9（生成墙钟）；.meta 补 RUN_S 行、run.json run_s 实填。A8b 实测 QUEUE_S=2（恰为 BP-4 sleep 2）/RUN_S=31。
> ④ **P2-2 退出码 5 落地**：**根因 = PS5.1 NativeCommandError 地雷**——EAP=Stop 下原生命令 stderr 重定向（`2>$null`/`2>&1`）直接抛异常（诊断脚本实证 TYPE: NativeCommandError），绕过退出码分派 → 实得 exit 1。修复：Test-RemoteReach/ssh exec 全部包 try/catch 归一网络类 + NETFAIL 前缀贯穿（探活/exec/scp 三层）+ entry catch 映射 exit 5；实机 `-RemoteHost <invalid>` → EXIT=5。
> ⑤ 附带修复：sync/create 的 scp 补 rc 检查（原 scp 失败会继续用陈旧 tar 解包）。全链回归：echo 卡 lightning 实测 exit 0 + QUEUE_S=2/RUN_S=20 + A11-PROBE-OK。
> ⑥ **验收判据多命令执行（paper-pilot 重跑实证，严重度 P2）**：A8b 的 accept 循环此前**只执行第一条命令**、第二条被静默丢弃——根因 1：`.accept-cmds.txt` 末行无换行（`$accept -join "\n"` 末条无 `\n`），`bash while read` **跳过未结尾的最后一行**（实测 `while IFS= read -r c` 对文武文件 total=1）；根因 2：`.meta` 的 printf 第 4 参数 `$ACCEPT_OK` 漏反引号，被 PS 插值成空串 → 主控侧 `ACCEPT_OK=` 始终读不到。修复：`while IFS= read -r c || [ -n "$c" ]`（保证处理末行）+ printf 补 `` `$ACCEPT_OK ``。**复验**：patch 后 paper-pilot 重跑，accept-output 现含 ACCEPT_CMD[1]（code_check 13 passed）+ ACCEPT_CMD[2]（classifier **29 passed** 回归），meta `ACCEPT_OK=1`，exit 0；且模型按正文规格实现 `is_well_formed_code`（非自设计）。**教训**：单命令 accept 卡永远暴露不了"末命令被丢"缺陷；多 accept 命令的卡才是判据完整执行的试金石。

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
| A11 | 端到端本地 | `task paper --card test-cards/echo.md --model nemotron` → 退出 0 + .agent-run.json 契约字段齐（**含 M1 哈希三字段非空：prompt_sha256/attach/content_digest**）+ agent-out\<ts>\ 有产物；**BP-3 附断言**：远端脚本落盘件 grep `opencode run -m` 前无位置参数形式（stdin 管道铁律运行时可见）；**BP-4 附断言**：queue_s 字段已填充（测试卡 flock 段前 sleep 2s 制造可测排队差） |
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
