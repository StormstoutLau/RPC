# 审查验收 Checklist：D6 agent-cli wrapper MVP

***

id: d6-agent-standard-CHECKLIST
type: design
version: 1.0
status: pending
date: 2026-09-03
depends: \[d6-agent-standard-IMPLEMENTATION v1.2, d6-agent-standard-DESIGN v1.4 (approved, 含 BP-1/BP-2 对齐审计回灌)]
upstream: \[d6-agent-standard-DESIGN]
-------------------------------------

> **Feature**: 主控站 agent-cli wrapper MVP（workspace + task 两命令，opencode 单路径，试点 Paper）
> **创建日期**: 2026-09-03
> **状态**: 进行中（T0 六门 5 PASS + 1 部分验证；T1 A7 PASS；T2 A8/A9/A10 PASS；T3 A11/A12 PASS；T4-T5 待验收）
> **Spec 步骤**: Step 7-8, 10
> **基于实施**: [IMPLEMENTATION.md](./IMPLEMENTATION.md)（v1.2，含 M1-M4+m1-m2+BP-3/BP-4 修正）
> **基于设计**: [DESIGN.md](./DESIGN.md)（v1.4 approved，F1 定案为后续升级项目；BP-1 契约补 readonly 字段 / BP-2 别名映射表）
> **验收体系**: A1-A14（IMPLEMENTATION §7 命令化判据）+ 不变式 7 条（DESIGN §9）+ 文档一致性四表
> **对齐审计（2026-09-03 第二轮，BP-1/BP-2 修复后复核）**: readonly 链闭环（任务卡 §6.1 → 契约 §6.2 → IMPL T2 → A11 判据）；别名链闭环（§6.1 枚举 → §6.1 映射表 → IMPL ROUTE\_TABLE → A8 完整 ID/A12 别名双验证）

***

## 1. 文档一致性验收（Step 8）

### 1.1 调研 ↔ DESIGN 对齐

| 检查项                       | 状态 | 说明                            |
| ------------------------- | -- | ----------------------------- |
| DESIGN §3.1 十六条决策逐条引用调研章节 | ☑  | Review 时全引用命中（v1.1 review 记录） |
| 调研关键发现被 DESIGN 使用         | ☑  | G1-G14 全收编或显式移交               |
| 无文档间矛盾                    | ☑  | R3/R4 断裂已修（v3.4.1 审计）         |

### 1.2 DESIGN ↔ IMPLEMENTATION 对齐

| 检查项                         | 状态 | 说明                                                        |
| --------------------------- | -- | --------------------------------------------------------- |
| DESIGN 五模块（M1-M5）在 IMPL 有实施 | ☑  | T1-T3 映射                                                  |
| IMPL 接口与 DESIGN §5/§6 一致    | ☑  | 命令面/schema 一致                                             |
| DESIGN §9 不变式 7 条在 IMPL 有实施 | ☑  | 1/6→T2-T3；2/3→T2 路由；4→T3 铁律；5→T3 哈希三字段（v1.1 M1）；7→T4 门禁缓存 |
| 无设计未覆盖的实施                   | ☑  | v1.1 review 修正后闭环                                         |

### 1.3 IMPLEMENTATION ↔ CHECKLIST 对齐

| 检查项                           | 状态 | 说明      |
| ----------------------------- | -- | ------- |
| IMPL A1-A14 在本 checklist 有验收项 | ☑  | §2 全覆盖  |
| 本 checklist 验收项可追溯到 IMPL      | ☑  | 逐项标注 A# |

### 1.4 术语一致性

| 术语             | 调研                          | DESIGN | IMPL     | 一致 |
| -------------- | --------------------------- | ------ | -------- | -- |
| 工作区            | \~/agent-workspaces/<proj>/ | 同      | 同        | ☑  |
| 任务卡            | task.md front-matter        | §6.1   | §6.1 冻结  | ☑  |
| 契约文件           | .agent-run.json             | §6.2   | 同 schema | ☑  |
| 状态机            | .agent-state.json           | §6.3   | 同        | ☑  |
| sensitivity 三档 | public/sanitized/local-only | 同      | 同        | ☑  |

## 2. 功能验收（A1-A14，逐项回填证据）

### 2.1 T0：V0 六门（前置验证，**2026-09-03 已完成：5 PASS + 1 部分验证**）

| #  | 验收项              | 通过判据（IMPL §7）               | 状态 | 证据（输出摘要+时间戳）                                                                                                                                                                                                                                            |
| -- | ---------------- | --------------------------- | -- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A1 | V0-1 薄壳导入        | v0probe 会话回答含 AGENTS.md 标记句 | ☑  | opencode 读 CLAUDE.md 薄壳→Read AGENTS.md→原文复述 V0PROBE-MARKER-7391（B 站 2026-09-03 12:07）；A1b 对照 PASS：/tmp 下 Glob 0 matches→答"无"                                                                                                                            |
| A2 | V0-2 claude 遮蔽   | proj-test 项目技能可见不被遮蔽        | ☑  | opencode 会话列出 17 技能含 proj-test（与 12 用户级共存无遮蔽）（B 站 2026-09-03 12:05）                                                                                                                                                                                     |
| A3 | V0-3 cwd 键控      | v0probe 笔记不串到 /tmp 会话       | ⚠  | **部分验证/判据修正**：ad-hoc 笔记（memory\_add\_note）跨 cwd 可读（/tmp 会话经 memory\_search 命中 v0probe 笔记）——此为调研 §4.1 已知行为 G3（ad-hoc 全局平铺），wrapper \[proj:] 前缀补丁的设计依据而非缺陷。**提取路径的 cwd 键控**（真正的验证对象）需 6h 闲置→G6 已列自然覆盖（B 站 2026-09-03 12:08）。判据应修正为"提取记忆不串"而非"ad-hoc 笔记不串" |
| A4 | V0-4 A 站记忆       | A 站 memory\_add\_note 跨会话复述 | ☑  | A 站写入 astation-memory-test-5566→新会话 memory\_list/read 命中并全文复述（A 站 2026-09-03 12:15）                                                                                                                                                                     |
| A5 | V0-5 Bash 不锁     | 同文件并发写两行可读无损坏（v1.1 M2 判据）   | ☑  | 双 opencode 并发写 /tmp/v0probe-test.txt→cat 2 行 LINE-FROM-A/B 完好无损坏（B 站 2026-09-03 12:18）；**额外发现**：headless 模式 opencode 写工作区外文件被 external\_directory 权限自动拒绝（沙箱效果），wrapper 设计需注意任务产物应在工作区内                                                                  |
| A6 | V0-6 flock 跨 ssh | ssh2 取锁失败退出                 | ☑  | ssh1 持锁 sleep 15（HELD）→ssh2 flock -n 取锁 EXIT=1 失败→等待后 ssh1 完成（B 站 2026-09-03 12:18）；flock 跨独立 ssh 连接互斥语义正确                                                                                                                                              |

> T0 任一门不通过 → 记录 + DESIGN §11.1 改道 + 回灌，不硬闯。

### 2.2 T1：workspace（M1）

| #  | 验收项   | 通过判据                 | 状态 | 证据                                                                                                                                                                                                                                                                                                                                                                                                        |
| -- | ----- | -------------------- | -- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A7 | 建区+同步 | B 站四件套齐 + md5 与主控站一致 | ☑  | `workspace paper --create` → B 站 \~/agent-workspaces/paper/ 落位 AGENTS.md/CLAUDE.md/.agentsync/out 四件套；AGENTS.md 远端 md5 `0269e34849d151adcc6405b6f75cb722` 与主控站本地 staging md5 完全一致（主控站 2026-09-03 12:42-12:43）。前置修复：ssh config 补 User scott-lau（原默认解析为 peng 导致 publickey 拒绝）；here-string 中 `\$W` 被 PS 展开为空串→统一改 `` `$W `` 转义（`$Script:/$proj` 本地展开、`$W` 留给远端 bash）。archive/sync 路径 T1 placeholder，T5 前不再回填 |

### 2.3 T2：router + lock/state（M3+M4）

| #   | 验收项  | 通过判据                          | 状态 | 证据     |
| --- | ---- | ----------------------------- | -- | ------ |
| A8  | 路由拒绝 | model 缺失/未知→2；local-only+免费→4 | ☑  | `route --model does-not-exist` → REJECT exit 2；`route --sensitivity public`(无 model) → exit 2；`route --model lightning --sensitivity local-only` → REJECT exit 4（无覆写通道）；control `route --model nemotron --sensitivity local-only` → ROUTE ok exit 0（主控站 2026-09-03 13:07） |
| A9  | 锁互斥  | 并发第二 task→3 且报 PID            | ☑  | HSTD 标准格式持锁(pid 22191 存活)→并发标准 acquire → `LOCK_HELD owner_pid=22191` + exit 3（flock -n 非阻塞立即返回）（B 站 2026-09-03 13:13） |
| A10 | 孤儿恢复 | kill 后 orphaned 归档+新任务成功      | ☑  | 残留 running pid 22191(死)→acquire 孤儿检测→out/partial.txt 归档至 out/orphaned/→state 改写 orphaned→重取锁新 running pid 22682, exit 0（B 站 2026-09-03 13:16；二次验证 ORPHAN_RECOVERED pid=18948 亦通过） |

### 2.4 T3：task 全链 + collect（M2+M5）

| #   | 验收项   | 通过判据                                                                                        | 状态 | 证据     | <br /> |
| --- | ----- | ------------------------------------------------------------------------------------------- | -- | ------ | :----- |
| A11 | 端到端本地 | 退出 0 + 契约字段齐（含哈希三字段非空 + readonly 字段非 null）+ 产物回收 + stdin 管道运行时断言 + queue\_s 填充（BP-3/BP-4 补） | ☑  | `task probe --card test-cards/echo.md`(model nemotron, local-only) → TASK\_EXIT=0；.agent-run.json 契约齐：readonly=false(非null) + content\_digest=sha256:ba2b0b41... + prompt\_sha256=sha256:efd1803e... + attach=[] + queue\_s=14734(填充) + status=completed；产物 agent-output.txt 回收(含模型输出)；远端脚本 stdin 管道 `< .prompt.txt`：PIPE\_STDIN\_OK + opencode 无位置参数形式（inv 4 铁律，BP-3）；queue\_s 填充（BP-4）——B 站 2026-09-03 13:40。**期间修复**：Invoke-RemoteScript 用 `\$W` 反斜杠转义致 PS 展开为空串/grep 崩溃（A7 同类）→ 统一改反引号 `` `$ ``；ssh stdout 混入函数返回值→改 Write-Host 透出只返回退出码；sync tar `& $cmd` 数组展开异常 + `--exclude` 位置错→改 splatting + exclude 前置；D:\Paper 源码 5.6GB 超 200MB cap→验收改用 probe 最小工作区（M1 源码子集语义，Paper 大源码另行配置 .agentsync 属 T5） | <br /> |
| A12 | 免费档契约 | model 字段=opencode/... + 台账一行                                                                | ☑  | `task probe --card test-cards/echo.md --model lightning --sensitivity public` → model=opencode/nemotron-3.5-lightning-free（免费档完整 ID，路由正确）+ 台账行 `202609031343177444,probe,opencode/nemotron-3.5-lightning-free,public,0,0,0`；契约 status=completed exit=0 + content\_digest=sha256:7b71...（B 站 2026-09-03 13:43） | <br /> |

### 2.5 T4：错误路径 + 冒烟

| #   | 验收项  | 通过判据                                      | 状态 | 证据     |
| --- | ---- | ----------------------------------------- | -- | ------ |
| A13 | 错误注入 | 超时→6+failed{timeout}；网络注入→重试 1 次（禁杀 sshd） | ☐  | <br /> |

### 2.6 T5：Paper 试点

| #   | 验收项  | 通过判据                       | 状态 | 证据     |
| --- | ---- | -------------------------- | -- | ------ |
| A14 | 试点闭环 | pytest 判据回收 + git diff 无越界 | ☐  | <br /> |

## 3. 不变式验收（DESIGN §9 七条）

| 不变式                       | 验证方法（对应验收项）            | 状态 |
| ------------------------- | ---------------------- | -- |
| 1 锁不变式（done/failed 先于锁释放） | A9/A10 + state 文件时序检查  | ☐  |
| 2 路由不变式（local-only 字节不出站） | A8 拒绝 + 代码审查 M3 唯一出口   | ☐  |
| 3 显式模型不变式                 | A8（model 缺失→2）         | ☐  |
| 4 调用形式不变式（stdin 管道）       | A11 执行体审查 + 代码走查       | ☐  |
| 5 日志完备不变式（哈希三字段）          | A11（v1.1 M1：任一空即失败）    | ☐  |
| 6 单向流不变式（out/ 不被覆盖）       | A14 git diff 无越界       | ☐  |
| 7 门禁缓存不变式（重试不重审）          | A13 网络重试后 scrubber 不重跑 | ☐  |

## 4. 错误处理验收（DESIGN §8 退出码全表）

| 场景             | 退出码  | 触发方式              | 状态 |
| -------------- | ---- | ----------------- | -- |
| model 缺失/未知    | 2    | A8                | ☐  |
| 锁占用            | 3    | A9                | ☐  |
| sensitivity 冲突 | 4    | A8                | ☐  |
| ssh 断连（重试 1 次） | 5    | A13               | ☐  |
| 超时             | 6    | A13               | ☐  |
| zen 限额         | 7    | 真实触发（不可预约，首次发生回填） | ☐  |
| 孤儿             | 0+警告 | A10               | ☐  |

## 5. 性能验收（IMPL §5 预算）

| 指标                  | 预算   | 实测     | 状态 |
| ------------------- | ---- | ------ | -- |
| workspace --sync 增量 | <60s | <br /> | ☐  |
| task 端到端开销          | <30s | <br /> | ☐  |
| wrapper 解析开销        | <2s  | <br /> | ☐  |

## 6. 兼容性验收（IMPL §4 S1-S8 抽查）

| 接缝                  | 验证点                         | 状态 |
| ------------------- | --------------------------- | -- |
| S1 GNU tar 排除       | A7（--sync 后站上无被排除文件）        | ☐  |
| S4 opencode json 容错 | A11（字段缺失时 null 不崩）          | ☐  |
| S6 中文路径             | T5 试点含中文文件名样本（可选）           | ☐  |
| S8 attach 传输        | A11 附带 attach 用例（可选，50MB 限） | ☐  |

## 7. ADD 审计（Step 10，验收后填）

### 7.1 Spec 质量门（Phase 0）

| 维度     | 得分（0-1） | 说明            |
| ------ | ------- | ------------- |
| 可测试约束  | <br />  | <br />        |
| 模块映射   | <br />  | <br />        |
| 接口契约   | <br />  | <br />        |
| 修正项    | <br />  | <br />        |
| 跨模块契约  | <br />  | <br />        |
| **总分** | /5      | **档位**: A/B/C |

### 7.2 ADD 审计发现

| 严重性 | 发现     | 证据     | 修复建议   |
| --- | ------ | ------ | ------ |
| P1  | <br /> | <br /> | <br /> |
| P2  | <br /> | <br /> | <br /> |
| P3  | <br /> | <br /> | <br /> |

### 7.3 ADD Iron Law 检查

- [ ] 测试通过的 4 类盲区已检查：断言恒真式 / 单文件检查盲区 / 设计文档独有约束无测试 / 修正阻断性项无测试

## 8. 文档完整性

| 文档                     | 存在 | 与实现一致    |
| ---------------------- | -- | -------- |
| 调研（docs/ v3.4.1）       | ☑  | ☐（验收后核对） |
| DESIGN.md v1.3         | ☑  | ☐        |
| IMPLEMENTATION.md v1.1 | ☑  | ☐        |
| CHECKLIST.md（本文件）      | ☑  | ☐        |
| 手册 agent-cli 节（T5 交付）  | ☐  | ☐        |
| 台账 §1.8 联动行（T5 交付）     | ☐  | ☐        |

## 9. 验收结论

### 9.1 验收统计

| 类别         | 总数  | 通过 | 失败 | 待办 |
| ---------- | --- | -- | -- | -- |
| 文档一致性      | 4 表 | 4  | 0  | 0  |
| 功能（A1-A14） | 14  | 0  | 0  | 14 |
| 不变式        | 7   | 0  | 0  | 7  |
| 错误处理       | 7   | 0  | 0  | 7  |
| 性能         | 3   | 0  | 0  | 3  |
| 兼容性        | 4   | 0  | 0  | 4  |

### 9.2 验收决定

- [ ] **验收通过**：A1-A14 全过 + 不变式 7 条全过 + P1 清零

- [ ] **有条件通过**：<条件>

- [ ] **验收失败**：<原因>

### 9.3 签字

| 角色  | 签字     | 日期     |
| --- | ------ | ------ |
| 实施者 | <br /> | <br /> |
| 审查者 | <br /> | <br /> |

## 10. 后续行动

| 行动                      | 责任人 | 期限           | 状态               |
| ----------------------- | --- | ------------ | ---------------- |
| T0 六门（A1-A6）            | 实施者 | T0 会话        | ☐                |
| T1-T5（A7-A14）           | 实施者 | 实施会话         | ☐                |
| F1 后端并发探测（升级项目）         | —   | V2/排队成常态时    | 挂起（DESIGN §11.3） |
| G8/G9 预置批次（R/sympy/重资产） | —   | Cpp\_Hub 试点前 | 挂起               |
| 手册/台账联动（T5）             | 实施者 | T5           | ☐                |

