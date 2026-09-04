# 开放日志：D6 agent-cli wrapper MVP（Open Issues 台账）

***

id: d6-agent-standard-OPEN-ISSUES
type: open-issues
version: 1.0
status: active（维护中）
date: 2026-09-04
depends: \[d6-agent-standard-CHECKLIST v1.0, d6-agent-standard-DESIGN v1.4, BLINDSCAN-v2-orchestration]
upstream: \[d6-agent-standard-CHECKLIST, d6-agent-standard-DESIGN]
-------------------------------------

> **用途**: D6 所有未决问题的**单一真值台账**——登记 P3 残留、BS 验证门、升级项、风险、跨站扇出待办。状态变更必须回写本表，禁止散落各处。
> **来源**: CHECKLIST §7.2（ADD 审计发现）/ §10（后续行动）/ §5（性能注记）/ §6（兼容性注记）、BLINDSCAN BS 验证门、DESIGN §11.3（分期移交）、ARCHITECTURE §8（演进预留）
> **关闭标准**: 问题闭环 = 代码/文档修复 + 实机复验证据回填本表

***

## 1. 未决问题总览

| ID | 类别 | 严重度 | 简述 | 状态 | 归属批次 |
|----|------|--------|------|------|---------|
| O-01 | 功能缺口 | P3 | --attach 传输未实现（IMPL M4/S8 声明；param 块无 Attach，attach 恒 []） | 🔴 open | 二期(G1) 或最小实现 |
| O-02 | 功能缺口 | P3 | workspace --archive 占位 echo 未演进（T1 stub） | 🔴 open | 二期 |
| O-03 | 纪律 | P3 | A11/A12 probe 产物未持久化（证据腐化，仅文字实录在盘） | ⚪ 已登记·后续遵守 | 纪律项 |
| O-04 | 纪律 | P3 | ledger 追加非沙箱安全：沙箱会话运行 wrapper 时 Add-Content agent-runs.log 被拒（14:50 丢台账行） | ⚪ 已登记 | 纪律项 |
| O-05 | 性能 | P3 | sync 62.3s 微超 60s 预算 4%；IMPL §5 sync/task 口径重叠 | ⚪ 已登记 | 二期/口径修正 |
| O-06 | 兼容性 | ⚠ 部分 | S6 中文**路径/文件名**未测（内容级已测，路径级可选未执行） | ⚠ 待验证 | Cpp_Hub 前 |
| O-07 | 验证 | P2 | zen 限额（429/quota）真实触发未发生（退出码 7 定义置位） | ⏳ 待真实触发 | 事件驱动 |
| O-08 | 升级 | P3 | F1 后端并发探测未实现（降级为 queue_s 观测先行） | ⏳ 挂起 | V2/并发 fan-out |
| O-09 | 验证 | — | BS-1 跨工作区并行 isolate_db（SQLite 写锁序列化） | 🔴 open | V2 fan-out 前置 |
| O-10 | 验证 | — | BS-2/跨站 编排层并发 HTTP fan-out 落地（L1 已验证，L2/L3 未做） | ✅ L1 pass | V2 |
| O-11 | 验证 | — | 跨站扇出 L2 端到端（真实 readonly 卡）+ L3 回归（agent-cli-smoke + A 抽检） | 🔴 open | V2 |
| O-12 | 功能 | P3 | strong accept：附主控站侧 golden 测试（防模型自写测试自证通过，P1b 遗留） | 🔴 open | 下一任务卡设计时 |
| O-13 | 预置 | — | G8 预置批次：R/sympy/重资产（Cpp_Hub 前） | ⏳ 挂起 | Cpp_Hub 试点前 |
| O-14 | 依赖 | — | 网关 auth 遗留：B:4000 LiteLLM 401 根因已改定（后端换载 key 不同步，非 master_key 哈希） | 🔴 open | 运维修复 |
| O-15 | 演进 | — | claude 路径 + --continue（G1 二期，Continue-vs-Spawn 决策表） | 🔴 open | 二期 |
| O-16 | 演进 | — | review --peer 站间互审 / trae 派发（任务卡=接口） | 🔴 open | D7+ |
| O-17 | 演进 | — | readonly 层 2 锁激活（V2 按任务卡字段细化） | 🔴 open | V2 |
| O-18 | 约束 | P1 | 同站内多并发被统一内存带宽顶起（~2.8× 恶化）；落地铁律=扇出优先跨站各 1 并发 | ✅ 已定案 | 架构导入 |

## 2. 各未决项详情

### O-01：--attach 传输未实现
- **证据**: CHECKLIST §6 S8——param 块无 --Attach 参数，attach 恒 []；IMPL M4 声明未交付；schema 字段在、传输通道不在
- **方案**: 随 claude 路径二期同批（G1），或最小实现独立 tar+scp `.attach/`
- **关闭判据**: `task --attach <f>...` 后远端工作区含附件 + .agent-run.json attach 非空 + 产物回收

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

### O-05：sync 性能微超 + 口径重叠
- **证据**: CHECKLIST §5——sync 62.3s（预算 <60s，超 4%）；IMPL §5 sync(<60s)/task(<30s 含 sync) 口径互斥
- **方案**: .meta 侧免 du；预算表改"已同步增量口径"
- **关闭判据**: 预算表口径单一化 + sync 增量达标

### O-06：中文路径/文件名未测
- **证据**: CHECKLIST §6 S6——内容级中文已验证（UTF-8 修复），路径/文件名级可选未执行
- **方案**: Cpp_Hub 试点前补用例（含中文路径样本）
- **关闭判据**: 含中文路径的任务卡端到端跑通

### O-07：zen 限额真实触发
- **证据**: CHECKLIST §4——退出码 7 定义置位，未真实触发（不可预约）
- **方案**: 事件驱动；首次发生即回填实测路径（429/quota → exit 7 + 降级提示命令）
- **关闭判据**: 真实触发一次并回填证据

### O-08：后端并发探测（F1 降级项）
- **证据**: DESIGN §11.3——MVP 观测先行 queue_s 被动记录；探测模块系后续升级项目（Scott 2026-09-03 批准降级）
- **触发条件**: queue_s 数据显示排队成为常态
- **方案**: 调 /slots + 槽位占用则拒/等；随 V2/并发 fan-out 实施
- **前置已解除**: P2-1 已修，queue_s/run_s 已可观测

### O-09：BS-1 isolate_db
- **证据**: CHECKLIST BS 门；SQLite 写锁序列化问题成立（并发5.2ms vs 串行3.0ms，busy_timeout=5000ms 排队非死锁）
- **L1 验证判据**: 隔离后并发两写耗时 < 现役基线；busy 命中归零
- **方案**: 并行写任务各自 `XDG_DATA_HOME` 隔离 db
- **关闭判据**: L1 判据通过 → V2 fan-out 前置解除

### O-10：BS-2/跨站 编排层并发 HTTP
- **证据**: CHECKLIST §2.6 BLINDSCAN §8.7.5/§8.7.6——**L1 已通过**
  - BS-2: 直连 gpt-oss 编排层 3 线程并行 52.1s ≪ 串行和 110.9s
  - 跨站: A 串行 4 次 6.8s → A+B 各 2 并发 cross_wall 4.8s（ratio 0.71 ≤ 1.6）
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
- **方案**: T0 独立批次；Cpp_Hub 试点前完成
- **关闭判据**: Cpp_Hub 工作区可编译（依赖就绪）

### O-14：LiteLLM 网关 401 运维遗留
- **证据**: project_memory 2026-09-04 根因改定——B:4000 401 真凶为**后端换载后 key 不同步**（8080 unsloth 9/4 重载自带 sk-unsloth-*，litellm 仍 9/3 旧进程写死占位 sk-local-noauth），非最初所记 master_key 哈希
- **方案**: ①config 改真实 key + 重启 litellm；②拉起 A:8080；或绕网关走直连
- **当前状态**: D6 链路已绕网关直连 B/A:8080（ADR-0002 方案 C），故 O-14 属运维遗留不阻塞 D6

### O-15：claude 路径 + --continue
- **证据**: DESIGN §5.1 二期命令面 + §9.6-2 Continue-vs-Spawn 决策表
- **方案**: G1 二期；ROUTE_TABLE 已含 cli 列；铁律 4（`< /dev/null`）已固化
- **关闭判据**: `agent-cli task --cli claude` + `--continue <session>` 可用

### O-16：review --peer / trae 派发
- **证据**: DESIGN §5.1 二期命令面；review --peer 站间互审协议；trae 派发以任务卡 schema 为接口
- **方案**: D7+（站间互审）/ D7（trae 五层循环对接）

### O-17：readonly 层 2 锁激活
- **证据**: DESIGN §4.1 层 2；schema 字段在，MVP 仅记录（全部按排它）
- **方案**: V2 按任务卡 readonly 字段细化（共享/排它语义）
- **前置**: O-09/O-10（并发能力）解锁后才有并行场景

### O-18：同站并发带宽约束（已定案）
- **证据**: BLINDSCAN §8.7.6 + CHECKLIST——同站内 2 并发 1.7→4.8s（~2.8× 恶化），收益纯来自跨站分摊
- **结论（铁律）**: 扇出优先跨站各 1 并发，勿同站叠并发
- **状态**: ✅ 已定案并导入 ARCHITECTURE §4

## 3. 风险台账（继承 DESIGN §11.2，实况更新）

| 风险                       | 缓解                                  | 现状/状态                        |
| ----------------------- | ----------------------------------- | --------------------------- |
| PowerShell→ssh 引用陷阱（R14）   | 全部远端逻辑走脚本落盘；CI 冒烟含端到端 task        | ✅ 已铁律化 + 冒烟覆盖               |
| llama-server 单槽排队致超时     | timeout 默认 900s 宽裕 + queue_s 观测定位   | ⚠ 同站并发现排队（O-18）             |
| zen 免费档限额无预警            | G13 本地 log 累计 + 降级提示（exit 7）        | ⏳ 未触发（O-07）                 |
| 站断电状态残留                 | 孤儿检测 + out/ 归档不删                    | ✅ A10 双次验证                 |
| .agentsync 误排除致任务缺文件    | task 失败报缺文件路径 → 修排除清单重 sync        | ✅ 已建项目级覆盖（Paper 5.6GB→7.0MB） |
| 网关 auth（LiteLLM 401）     | 绕网关直连（ADR-0002 方案 C）已规避；遗留 O-14    | ⚠ 运维项                        |

## 4. 台账维护规则

1. **单一真值**: 本文件是 D6 未决问题的唯一总账；代码注释/检查清单中的待办引用本表 ID，不在别处维护副本
2. **状态机**: `🔴 open` / `⏳ 挂起` / `⚠ 待验证` / `✅ 已定案/已闭环`；每项含清晰的关闭判据
3. **回填证据**: 任何项闭环必须回填实机证据（命令输出摘要 + 时间戳 + 产物路径），拒绝"口头关闭"
4. **批次关联**: 二期(G1)/V2/D7+ 项随对应阶段开启时从本表摘取为任务；本表保持 open 直至批次交付
5. **随审更新**: 每次验收/ADD 审计/升级窗口 review 后同步本表（新增/状态变更/证据回填）

***

**开放日志签字**: 2026-09-04 立案，随 D6 演进维护。