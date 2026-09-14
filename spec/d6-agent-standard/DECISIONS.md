# 决策记录：D6 agent-cli wrapper MVP

***

id: d6-agent-standard-DECISIONS
type: decisions
version: 1.1
status: approved（与 DESIGN v1.4 / CHECKLIST 验收实况对齐，2026-09-04；v1.1 补 D-16 复杂度路由 + D-17 wrapper 稳定性，2026-09-07；v1.2 补 D-18 ctx 一致性 radical fix B）
date: 2026-09-04
depends: \[d6-agent-standard-DESIGN v1.4, d6-agent-standard-CHECKLIST v1.0]
upstream: \[d6-agent-standard-DESIGN, ADR-0001, ADR-0002]
-------------------------------------

> **用途**: D6 所有关键技术决策的**单一登记册**——每个决策含：选了什么、否决了什么、依据、验收证据、ADR 关联。是自查与后续开发者追溯「为什么这么做」的入口。
> **范围**: 设计决策（DESIGN §3.1/§4.1/§5.1/§6）+ 方案取舍（DESIGN §7）+ 分期定案（F1/F4/F7）+ 架构级决策（跨站扇出/网关直连）。
> **不重复**: ADR-0002 的网关 fan-out 根因分析不在此重述，此处仅登记其决策引用。

***

## 1. 决策总览

| ID | 决策 | 选择 | 否决/比较对象 | 依据 | 验收证据 | 关联 |
|----|------|------|-------------|------|---------|------|
| D-01 | 编排形态 | PowerShell 单文件 wrapper | SDK 常驻 server / LLM coordinator / dsh 框架 | 公理1 确定性编排 + 零自加载不变式 + tar+scp 实证链 | 全 A 项 | DESIGN §7.1 |
| D-02 | 并发锁 | 工作区级 flock 双层锁 | — | Codex RwLock + 文件集粒度纪律 | A9/A10 + V0-6 | DESIGN §4.1 |
| D-03 | 同步链 | tar+scp + .agentsync 排除 | rsync | 主控站 Git Bash 无 rsync（实证） | A7 | DESIGN §3.1/§5.2 |
| D-04 | CLI 调用形式 | opencode 仅 stdin 管道；claude 仅 `< /dev/null` | 位置参数 | 1.18.25 位置参数挂死（日志实证） | A11/E2 state | DESIGN §9.1 |
| D-05 | 模型路由 | wrapper 编译期 ROUTE_TABLE，任务必填显式 -m | 隐式默认 | A 站默认曾漂移到外网模型（安全边界） | A8 | DESIGN §9.4 |
| D-06 | 敏感路由 | 三档硬路由（public/sanitized/local-only），local-only 不可覆写 | 靠人记忆 | 免费模型数据用于改进训练 | A8/A8b | DESIGN §2.1 |
| D-07 | 消毒正确性 | clean-room 任务卡 + 机械 scrubber 门禁 | LLM 自查 | 消毒正确性须机械可验证 | A8b | DESIGN §5.1 F2 |
| D-08 | 状态机 | running 带 PID/时间戳，done 最后写，孤儿可检 | 无状态/假完成 | dsh 孤儿锁语义 | A10 | DESIGN §6.3 |
| D-09 | 契约归一 | .agent-run.json 吸收 task-notification + queue_s/run_s 分离 | — | 双方字段并集 + Model-visible means logged | A11/A16 | DESIGN §6.2 |
| D-10 | 重试语义 | 仅网络类失败重试 1 次（≤2）；模型失败转人工 | Codex 沙箱升级重试 | 本系统无沙箱，语义等价 | A13/A15 | DESIGN §4.5 F7 |
| D-11 | 后端并发探测 | MVP 降级为 queue_s 观测先行 | 内建探测模块 | 排队观测先于探测（Scott 批准降级） | A16 | DESIGN §4.1 F1 |
| D-12 | 模型分层 | 分层轴=窗口+隐私非智力；四档模型分层实测 | 智力分层 | 免费档不劣质，13s 快于本地旗舰 3 倍 | A12 | DESIGN §9.4 |
| D-13 | 任务卡正文传输 | Get-FrontMatter 补 body 捕获，prompt=[proj:]+task行+正文全文 | 仅传 front-matter 一行 | P1b 修复：正文静默丢弃致模型自设计 | A8b/A14 | CHECKLIST §7.2 P1b |
| D-14 | 网关链路 | D6 链路绕 LiteLLM 网关，直连 B/A:8080 + ssh 隧道跨站 | 经网关 fan-out | ADR-0002 方案 C：消除配置漂移故障 | BS-2/跨站 L1 | ADR-0002 |
| D-15 | 跨站扇出 | fan-out 优先跨站各 1 并发；隧道 B:18081→A:8080 | 同站叠并发 | 同站被统一内存带宽顶起（1.7→4.8s） | 跨站 L1 | BLINDSCAN §8.7.6 |
| D-16 | 复杂度路由 | 按 复杂度/题型 分层映射推理参数（code/reason/short/long/doc，L0-L3） | 一律最高思考+满ctx | qwen3.8-27B 横测：代码题思考 94.9x cost、a1 空输出、deepseek 剥不动 qwen 标签 | 11/11 单测 + 吃狗粮 code/doc 两档 | DESIGN §6.4 |
| D-17 | wrapper 稳定性 | task 前置 fail-fast（PROFILE 干跑 + agent-out 可写探针 exit 12）+ ledger 先行 + collectOk 保护 | 任由 collect 崩溃吞落档 | run1 权限崩吞 ledger / run2 脱管静默退 | PREFLIGHT 早于 STATION_READY + collect=ok 落账 | DESIGN §11.3 |
| D-18 | ctx 一致性 | **引擎 ctx = 唯一真相**：`_station_ready` 探测引擎真实 n_ctx → `Resolve-Profile` 按 `min(intent, ENGINE_CTX)` clamp；`ENGINE_CTX>0` 覆盖静态 ctxMax 表；station-ready 前置到 profile 前 | 统一大 ctx / 同步 opencode client-limit | O-23 根因=三层 ctx 解耦（profile 元数据 ≠ opencode limit ≠ 引擎 `-c`）→ refdedupe 引擎 8192 < 请求 12536 → 400 挂死 | `_complexity_route_test` 16/16 + refdedupe 实机 RUN_S=111/TASK_RC=0/ACCEPT=1 无 400 | O-23 |
| D-19 | C++ golden 验收形态 | **后续 C++ 任务卡 golden 走真 `cmake` 编译**（非纯源码静态断言） | 维持静态断言（更快/主控免编译链） | O-13 半收口判据：`cmake` 真编译方满足 bit-exact 领域范式（CROSS-PROJECT §2 最高约束）与 golden 强验收初衷（防模型自写测试自证）；Cpp_Hub-001 静态断言仅为试点过渡 | 待首个真编译型 C++ 卡落地回填（golden cmd 调 `cmake` + 断言，本地 fallback 静态断言） | O-13 / O-12 |

## 2. 方案取舍详情（DESIGN §7，四案）

### D-01 编排形态选型
| 方案 | 结论 | 核心理由 |
|------|------|---------|
| **A. PowerShell wrapper + 站上 flock** | **✅ 选择** | 零常驻服务；锁用 OS 原语；tar+scp 全实证链；审计三件套完整；与集群纪律兼容 |
| B. opencode SDK 常驻 server | 否决 | 常驻 server 违反零自加载不变式②；新增常驻进程即新增挂死面（A 站 KFD bug 史） |
| C. Anthropic coordinator（LLM 编排席） | 否决 MVP；D7+ 候选 | 实测仅证提示注入生效（worker spawn 未测）；LLM 编排违反公理 1；无任务卡审计痕迹 |
| D. dsh（DeepSeek Harness）整体引入 | 否决 | TS 全栈 developer preview 破坏性变更；不同构；价值已作设计模式吸收 |

## 3. 关键定案（分期/边界）

### F1：后端并发探测 → 降级为观测先行（Scott 2026-09-03 批准）
- **原案**: wrapper MVP 内建后端并发探测（调 /slots + 槽位占则拒/等）
- **定案**: MVP 观测先行——`.agent-run.json` 的 `queue_s` 天然记录排队时长；排队成常态再单独立项探测
- **效果**: A16 验证 queue_s/run_s 已可观测；O-08 挂起为升级项
- **后续注记（BS-2 L1）**: llama-server 该实例无 `/properties`，不能用 `engine_stats.running`，改以墙钟收敛作并行判据——探测方案若实现需另选客观判据

### F4：TUI 并发边界登记为已知限制
- **边界**: flock 只互斥 wrapper-vs-wrapper，不互斥 wrapper-vs-手动 TUI
- **接受**: 缓解 = 纪律告知 + V0-5 联动验证；接受为 MVP 风险（同工作区手动作业并发写冲突概率低）

### F7：重试语义适配
- **原义**: Codex "沙箱拒绝→恰好一次去沙箱升级重试"
- **适配**: 本系统无沙箱，将"升级尝试"重释为"仅网络类失败重试"；模型/文件系统失败直接转人工；语义等价（都不无限重试），更贴合 CLI 场景

### BP-1/BP-2（对齐审计回灌，2026-09-03）
- **BP-1**: .agent-run.json 契约补 `readonly` 字段（MVP 仅记录，V2 激活语义）
- **BP-2**: 别名→完整 ID 映射表（nemotron/gpt-oss/lightning/ultra/free-1m）统一双表示，M3 路由按完整 ID 判定

### D-16：复杂度路由（2026-09-06/07，DESIGN §6.4）
- **原案**: 一律最高思考 + 满 ctx（曾作为追求质量的默认）
- **定案**: 按任务**复杂度（auto/short/standard/long）**与**题型（code/reason/concept/numeric/doc）**分层映射推理参数档 `{context,max_output,thinking,template,reasoning_format,flavor}`；优先级 `taskType > complexity > default`；`context=0` 哨兵上抛模型上限；`type∈{code,doc}` 强制 thinking OFF
- **实证**: qwen3.8-27B 横测——代码题思考开启 cost 94.9x、a1 空输出、`--reasoning-format deepseek` 剥不动 qwen thinking/response 标签（llama.cpp #24671）；默认 ctx8192+c2 禁思考 5/5
- **执行分层**: L1 实例层（llama-server preset 三风味 nothink/think/long，MVP 主路径）→ L2 opencode provider 层 → L3 prompt 变形 → L0 per-request（待 vLLM）
- **验收**: `_complexity_route_test.ps1` 11/11；吃狗粮 code 档（pathguard）+ doc 档（specaudit）均落 profile 正确

### D-17：wrapper 稳定性 fail-fast 加固（2026-09-07）
- **原案**: collect 阶段直接写 agent-out，失败即整个 wrapper 崩（EAP=Stop）
- **定案**: 三段加固——① task 前置 `Assert-AgentOutWritable` 探针（PROFILE 干跑后、station-ready/sync 前，失败 ABORT exit 12 + 提示进 Settings UI）；② ledger 写盘提前到 collect 之前（LEDGER_WARN try/catch）；③ agent-out 建目录+写盘包 collectOk try/catch（COLLECT_FAIL + `.agent-run.json` 落 `collect=ok/failed`，TASK_DONE 仍输出）
- **实证**: run1 权限崩吞 ledger、run2 脱管静默退（均失联无落档）；加固后 PREFLIGHT 早于 STATION_READY、`collect=ok` 落账、exit=0
- **遗留**: 新会话撤白名单自测 exit 12 判定为「搁置」（失败分支极薄、正常路径已覆盖，跨会话成本≫价值）

## 4. ADR 关联

| ADR      | 决策摘要                                    | 对 D6 的影响                                  |
| -------- | ---------------------------------------- | ---------------------------------------- |
| ADR-0001 | 收尾→重构→聚合→加固；运维层补全                        | D6 属调用标准层，不触碰 infer-load/网关/CLI 配置（D1/D5 域） |
| ADR-0002 | 网关 401 根因 + fan-out 路由决策：绕网关直连 B/A:8080 | D-14 直接继承：D6 模型链路绕 LiteLLM，跨站走 ssh 隧道       |

## 5. 决策维护规则

1. **新增决策必登记**: 任何影响 D6 架构/契约/路由/并发的新决策，必须在本表新增行（含依据+验收证据），禁止只在代码注释/会议口头记录
2. **决策链可溯**: 每个决策可反向追溯到调研章节/ADR/验收证据（DESIGN §3.1 已有决策→调研映射，本表补"→证据"闭环）
3. **变更审查**: 否决某既有决策时，必须新立决策行记录"改了什么/为什么"而非抹除原行——保留决策历史
4. **与 OPEN-ISSUES 联动**: 决策引发的未决项（含否决项的 D7+ 候选）同步登记 OPEN-ISSUES.md

***

**决策记录签字**: 与 DESIGN v1.4 / ADR-0002 / CHECKLIST 验收实况对齐（2026-09-04）。