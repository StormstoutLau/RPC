# 开发日志：D6 agent-cli wrapper 框架（Development Log）

***

id: d6-agent-standard-DEVELOPMENT-LOG
type: dev-log
version: 1.0
status: active（持续维护中）
date: 2026-09-03
depends: \[d6-agent-standard-DESIGN, d6-agent-standard-CHECKLIST, d6-agent-standard-OPEN-ISSUES]
upstream: \[d6-agent-standard-.* 全量文档]
------------------------------------------------------------------

> **用途**: D6 框架（主控站 agent-cli wrapper + 跨站派发 + 评审/看板/栅栏闭环）的**唯一演进史**——按里程碑时间线回溯记录「何时做了什么、为什么、验收证据、关联 O-xx」，并预留持续追加。与 DECISIONS（为什么这么做）互补，不重复其决策推演。
> **规则**: 新里程碑**追加在最新的日期章节顶部**（时间倒序）；每条含 日期 / 事件 / 涉及文件 / 验收证据 / 关联条目；闭环事件的验收证据以链接回填，不在此铺细节。
> **追加者**: 每次重要落地/闭环后由 Scott 或执行体回填。

***

## 历史回溯（2026-09-03 起）

### 2026-09-12 — 评审环 / 看板 / 栅栏门 / 批量闭环日

- **Cpp_Hub 试点全链路闭环（O-06/O-12 关闭，O-13 半收口）**: 轻量 C++ 工程（含中文源文件名 `因子计算_核心.cpp`/`因子计算_run.cpp`，git init）+ 补建 `agentsync-templates/cpp` 四型模板（兑现 IMPLEMENTATION 声明）；B 站预置编译链 `g++`/`cmake` + pytest。`test-cards/cpphub-001.md` 挂主控独立 golden（`cpphub_golden.py`，纯源码静态断言，避开 Win10 无编译链），端到端两次 run 均 `exit 0 / accept_golden.passed=true / GOLDEN_PASS`（最近 202609122223140613）。**试点验收桥接三项台账关项**: O-06 中文路径/文件名端到端（tar UTF-8 跨站无乱码+模型按原中文名编辑+golden 反替代检查）；O-12 strong accept 关闭判据「下一任务卡设计时落地 golden」达成；O-13 编译链就绪但 golden 未走真编译 → 半收口，R/sympy 单列。失败修复: agent-cli 项目未注册 → `PROJECTS` 补 `Cpp_Hub`；golden cmd 改系统 `python3`（A 站无 .venv）。关联: Cpp_Hub-001、O-06、O-12、O-13。

- **O-24 ④ 单机并发纪律入册（P0 收口，执行）**: O-18 铁律补单机语境——手册 §2 agent-cli 新增「并发纪律」条（单机勿就地叠并发，同一带宽顶起 ~2.8×，扇出优先跨站各 1）+ ARCHITECTURE §4「单机形态同样适用」锚点；手册「并发」条目同步更新 readonly 层 2 锁已激活（O-17）。OPEN-ISSUES O-24 ④ 标记入册。关联: O-24/O-17/O-18。

- **O-16 评审环落地（`agent-cli review`）**: JUDGE_TABLE 五源路由落盘主控 agent-cli.ps1（商业 API / ultra free / DS V4 RPC / M2.7 / 主控 opencode 备源），advisory 语义（score=不合格仍 exit 0 + 幂等复用 + `--overwrite` 重审）；judge=ultra 实测生成 review.json。关键教训：main judge 标 local 必须用站内模型（防敏感数据外发）；CoT judge max_tokens=8000、按源参数化；judge 调用 retry≤2；长产物评审取头尾截断。
  - 关联: O-16 closed；文件: agent-cli.ps1、THROUGHPUT-BASELINE.md、CLOSED-LOOP-ANALYSIS §3.2
- **O-25 P1 槽位门落地**: `ops/station-bin/_slot_gate.sh`（远端 `/slots` 探测）+ `Invoke-SlotGate`；仅本地 `cluster-litellm/*` 引擎走门，egress `opencode/*` skip；busy≥total 或 queue>0 → exit 24 SLOT_BUSY reject（`--slot-allow-busy` 放行），slot 记入 run.json。并入 O-08/F1。
- **O-25 P2 看板落地**: 纯 file:// 单文件方案 — `make-dashboard.ps1` 生成器 → `dashboard.html`（self-contained，内联 ledger+run.json，完成区 22 行三态 + 运行中/Live 拉 `.progress`）。离线验证通过（BOM/AST/生成/ _fm_golden_test 9/9）。
- **批量闭环（总览表与详情节对齐）**: O-09（BS-1 isolate_xdg，L1 PASS 消除 SQLite 写锁串行化）、O-10（并入 O-11）、O-11（跨站扇出 L2 端到端 + L3 回归，`o11-fanout-readonly.md` 双站并发 ACCEPT_OK/GOLDEN_OK）、O-15（claude 备通道 + `--continue`）、O-17（readonly 层 2 锁）、O-24（P0-①--continue 实证 + P0-②被 O-16 覆盖）。
- **O-26 分解派发闭环**: decompose 拆 2 分片 A/B 双站并行，并行 465.1s ≪ 串行 720.8s（ratio 0.645）；落地修复 2 bug（`Start-Process .ExitCode` 偶发 null、`$MyInvocation` 派发无 BOM 副本）。
- **C 站 gpt-oss-120b HIP 引擎落地**: 改用 `/home/scott-lau/Applications/llama-gfx1151/llama-server`（ROCm HIP，`ROCm0`）；修复 `BACKEND=` 无尾随换行粘连 bug；port 8080，`/health ok` + `/v1/chat/completions` HTTP 200。关联: station-c/DEPLOYMENT.md。
- **台账同步**: OPEN-ISSUES 总览表状态回写对齐详情节（O-09/10/11/15/17/24），遵循单一真值。

### 2026-09-11 — M2.7 实跑 + 五源评审路由定案

- MiniMax-M2.7（C 站，121G UD-IQ4_XS，Vulkan/ROCm0）16 题批量实跑（tmp/res_m27，117936 tok / 5490s），decode 21.5 / 22.1 t/s。入库 THROUGHPUT-BASELINE.md。
- 五源评审路由（CLOSED-LOOP-ANALYSIS §3.2）定案，替代 review subagent 单一路径 → 2026-09-12 落地。

### 2026-09-10 — 同模型横向基准

- HARNESS-SAME-MODEL-BENCH-2026-09 建立（同模型、多后端/多站横向对比基准）；A 站 Hermes Agent 插件生态盘点并入 PLUGIN-LEDGER §6。

### 2026-09-09 — 单机闭环韧性批 + strong-accept

- **--continue 续接循环落地**: front-matter `continue-timeout-s` 独立预算键（续跑不继承首跑已耗尽预算）；真实恢复场景实测（dogfood-resume-recovery v3）→ 手册 §2a.5。关联: O-24 P0-①。
- **strong-accept 落地（O-12）**: M1-M4 全链（front-matter 解析 / .golden/ 洁净注入 / 权威 checksum 防篡改 / .meta+run.json 契约）；V0 验证门 PASS（ACCEPT_GOLDEN_OK=1、哨兵 NOT_OBSERVED）、TAMPERED 安全侧失败实证；修复 tar `-xzf→-xf`、collect 静默。
- **O-19 4/4 闭环**: 两站模型全卸载致空推理 中止场景全链修复。
- **三站插件统一**: DCP(codex-memory 0.6.5 + @tarquinen/opencode-dcp)+codex-memory 三站同构安装；PLUGIN-LEDGER 建立。
- **CLOSED-LOOP-ANALYSIS-2026-09-09**: 单机工作流 4 类断点（review 缺 / --continue 缺 / claude 备通道缺 / 单机排队治理缺）分析定案。
- **回归框架**: `_fm_golden_test.ps1`（离线回归 9/9）。

### 2026-09-08 — 分布式引擎深化 + 事故铁律

- **叠加加载死机事故（A 站 kernel panic）**: C1(HIP 62G 常驻) + C2(再载 63G) 叠加 125G>124G。教训铁律升级: ①引擎对比测试必须串行+卸载确认 ②`-ngl -1` 单机高危 ③load-gate 硬规则（检查已有进程 RSS 叠加，旧 load-mem-gate 漏检项）。
- unsloth studio 单站 HIP 后端可用（gpt-oss 120B MXFP4: prefill 112-138 / decode 49-53 t/s）；同条件后端对比 nemotron-120B: HIP 20.5 vs Vulkan 23.2（Vulkan 略优）。
- C 站部署落地: 内核 6.17.0-23 钉住（GRUB 子菜单索引）、环网 thunderbolt MAC 绑定根治、UMA FB=4G、看门狗关闭、gpt-oss 引擎 BR。关联: station-c/DEPLOYMENT.md。

### 2026-09-06/07 — ctx 一致性 radical fix + wrapper 加固

- **O-21 服务端 ctx 修复闭环**: `/props` 实载 n_ctx=65536 而模型通告 131072 → 服务端 `-c 65536` 是 400 真根因；conf CTX 65536→131072 重载 A 站 gpt-oss，specaudit 重跑全程无错。
- **O-23 复杂度路由 ctx 解耦**: profile.context 只是元数据，从未传给引擎；opencode.jsonc 固定 131072；引擎 ctx 由 flavor 预设决定 → 三者解耦根治。D-18 radical fix B（引擎 ctx=唯一真相）。
- **D-16 复杂度路由 + D-17 wrapper fail-fast 加固**（DECISIONS v1.1）。O-22 `.meta` 残留误导收口。

### 2026-09-05 — 最小实现批

- **O-01 --attach 传输最小实现落地** + 端到端验证（schema 字段↔传输通道闭环）。
- **O-20 修复**: Invoke-Workspace 目标站判定被 PowerShell 动态作用域污染（`$HostName` 污染 → 恒回退 'B'），修复+实机验证。

### 2026-09-04 — 台账制度化 + BS 验证门 + 跨站架构

- **OPEN-ISSUES 台账建立**: 单一真值总账（P3 残留 / BS 验证门 / 升级项 / 风险 / 跨站待办），状态变更回写铁律。
- **DECISIONS 登记册建立**（v1.0，D-* 决策单一口径）。
- **BLINDSCAN-v2-orchestration §8**: 复现记录 + 跨站扇出调研。**BS 验证门 L1 全过**: BS-1 写锁串行化成立非危重（WAL+busy_timeout 排队非阻塞）；BS-2 gpt-oss 编排层 3 线程并行 52.1s≪串行 110.9s、跨站 A+B 并发 ratio 0.71 → **扇出押编排层并发 HTTP + 跨站各 1 并发**；BS-3 slot0-stuck 未命中（概率性不能免疫）；BS-6 并发≈串行。ADR-0001/0002 关联。
- **F1 后端并发探测** → 降级为观测先行（同站叠并发被带宽顶起）。

### 2026-09-03 — 框架奠基 + 验收通过

- **DESIGN v1.0 批准**（Step 3-4，含 F1 定案）；CHECKLIST 建立；IMPLEMENTATION v1.2 实施锚点落档。
- **V0 六门验证**（B/A 站实测）: A1 薄壳导入 / A2 claude 遮蔽 / A4 A 站记忆 / A5 bash 并发写不锁 / A6 flock 跨 ssh — 5 PASS + 1 部分验证。
- **A1-A16 功能全过 + 不变式 7/7 + 错误处理 6/6**: 路由拒绝（exit 2/4）、锁互斥（exit 3）、孤儿恢复、网络失败（exit 5）等全链路。
- **验收轮**: 有条件通过 → 修复批四项（P1a scrubber + P1b 任务卡正文传输 + P2-1 时间语义 + P2-2 退出码 5）全实机复验 → **验收通过（2026-09-03 16:30）**，质量门 4.5/5 档 A，遗留 P3×5 登记。
- **paper-pilot 试点闭环（A14）**: 真实任务卡 `test-cards/paper-pilot.md` 跑通（accept 双 pytest 11+29 passed，产物回收 D:\Paper\agent-out，main git 无越界）。
- **unsloth-a-station:** A 站 unsloth（b10715 HIP 引擎）就位。

***

## 持续追加模板（下方为新里程碑占位，按需复制上移）

### YYYY-MM-DD — <里程碑名>

- <事件>: <简述 + 验收证据链接 + 关联 O-xx>