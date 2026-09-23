# 决策记录：D6 agent-cli wrapper MVP

***

id: d6-agent-standard-DECISIONS
type: decisions
version: 1.1
status: approved（与 DESIGN v1.4 / CHECKLIST 验收实况对齐，2026-09-04；v1.1 补 D-16 复杂度路由 + D-17 wrapper 稳定性，2026-09-07；v1.2 补 D-18 ctx 一致性 radical fix B；v1.3 补 D-20 D6/D7 路线权威源与编号，2026-09-23；v1.4 补 D-21~D-23 = D7 待裁 10/11/12 裁定，2026-09-24；v1.5 补 D-24~D-25 = D7 待裁 13/30 裁定（`MANIFEST.sha256` 的 `parent` 与算法标识形态），2026-09-24；v1.6 补 D-26~D-27 = D7 待裁 14/15 裁定（U-4 采用 H-1~H-4 · 结构性事实不得由 LLM 产生），2026-09-24）
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
| **D-20** | **D6/D7 路线的权威源与编号**（2026-09-23） | **① 路线唯一权威源 = `docs/2026-09-23_D6-D7分阶段执行方案.md`（标题「升级路线总表」）**；台账管登记、REMEDIATION-PLAN 管定级、调研/取证只提供依据；**② D7 批次统一为 `D7-P<阶段号>-<序号>`**（与 D6 的 `P0-1` 同构），**`D7-A..H` 两套字母族作废** | 不统一编号（沿用两套字母族） | 实测**两套 `D7-A..H` 用同一批字母表示不同的事**（`D7-B` 权限模型 vs 机械门先行 / `D7-D` 回写裁决 vs 权限模型 / `D7-G` 中断态 vs 统一基座）；且另有 `O-xx`（台账）、`W1~W4`（工作项）未建映射 —— 与 `U-2`（统一字典）同病 | 路线总表 §0（冲突实况）+ §9（旧→新映射，**永久留档**）；`rpc_check --quick` 11 绿 | [D7 调研合并稿](../../docs/2026-09-23_D7调研_立项·机制·统一基座.md) §13 · [DEV-LOG-012](../../docs/DEV-LOG-012-d6-d7-roadmap-and-impact.md) |
| **D-21** | **D7 待裁 10：先做 U-2（统一证据强度字典 + 方言映射表）**（2026-09-24，承接调研稿 §14.1 的 2026-09-23 分析） | **先做 U-2，并作为 D7-P1 的第一项** —— 它是待裁 11/12/13/14 的**共同前提**（都要引用"哪套档位 / 哪个 id 是哪个"）；输入**已现成**（§11.1 冲突清单可直接当词表输入）；产出 = **单一轴字典 + 方言映射表**，且**映射表本身可被门禁校验**（源词表变 ⇒ 下游红） | 先做 U-1（身份/算法）或先做 U-4（失效规则）；「不建字典、每次跨项目对齐时重读代码」（现状） | §11.1 实测：`L1/L2/L3` **同一符号 5 种含义**（`Paper` 元数据/正文/质检 · `Textbook` 结构/元数据/边 · `Open_Data` 官方/社区/实测 · `Macro_Data` 缓存 TTL L1–L5 **另**一套反爬 L1–L7 · `Fin_Agent` 标签粒度 **另**一套架构分层 L1–L4）；`A/B/C` ≥3 义 · `R1–R5` ≥2 义。成本**低**（建表 + schema，**不改任何生产链路**） | **待 D7-P1-1 落地回填**（字典 + 映射表落盘 + 门禁断言"源词表变 ⇒ 下游红"）；本裁定**不产代码 ⇒ 不改现有门禁 17 项（quick 11 绿）** | [D7 调研合并稿](../../docs/2026-09-23_D7调研_立项·机制·统一基座.md) §14 项 10 · §14.1 逐条第 10 行 · §11.1 · [路线总表](../../docs/2026-09-23_D6-D7分阶段执行方案.md) §4.3（D7-P1-1）· §8.2（C 组） |
| **D-22** | **D7 待裁 11：U-2 采用「建映射、不迁移权威源」**（2026-09-24） | **采用「建映射、不迁移权威源」** —— 各源项目**保留自家词表为权威**；U-2 只建**双向映射表 + 命名空间前缀**（前缀 = **机读必填字段**，不靠自觉）；权威源迁移**可委托但须显式 + 必配机械 drift check**，且**符合性判定不可继承** | 迁移权威源（A 仓 → B 仓、立单一权威）；前缀靠人自觉写（`CHK-R2` vs `R2` 那类） | §11.4 先例实测（`Cpp_Hub`↔`Spec_Workflow`）：机制**跑通了**（指针封堵 2026-08-17 提交 `96edc5c`；回流通道首次批量回流成功 → 框架 v1.3/v1.4）**但执行不完整** —— 封堵**半侧本地化**（`DIS-007` 未入库）、提交**未推送**（`ahead 11`）、**无机械 drift check**；且手工映射"一次性 / 无自动同步 / 无法验证漂移"。作为形态选择**成本零额外**；不做 ⇒ **重演一次，且这次是 9 个项目（≈4.5 倍代价）** | **待 D7-P1-1 落地回填**（与 D-21 同批）；本裁定**不产代码** | 同 D-21 §14 项 11 · §14.1 逐条第 11 行 · §11.4 · [基准调研](../../docs/2026-09-23_Spec_Workflow能否作为D6-D7工作流基准_调研.md) §6 三段式 / §8 复核实录（**该实录同时证明复核者自己也犯了同类符号冲突：`E1–E5`、`D6`**） |
| **D-23** | **D7 待裁 12：U-1 统一算法与蓝本**（2026-09-24） | **① 算法统一为 SHA256**；**② 蓝本取 `F:\Open_Data`** 的 `sha256(维度)[:32]`；**③ 四项同时写定** = 算法 + 截断长度 + 取值维度 + **算法标识前缀**（缺一 ⇒ 跨项目必撞车或误比）；**④ 不追溯重算历史**（只约束**写入侧新产物**）；**⑤ 算法标识写在 U-1 内部字段 / 清单头部伴随元数据，不进哈希行** ⇒ 保住 `sha256sum -c` | 沿用各家算法（md5/sha1/sha256 并存）；算法前缀写进 `MANIFEST.sha256` 哈希行（破坏 `-c`）；追溯重算历史 | §11.6 实测 **6 种 ID 构造 × 4 种截断长度**（`Open_Data` `sha256[:32]` · `Macro_Data` `sha256` 全 64 · `factor_pipeline` `sha256[:16]` · `Auto_Prover` `md5[:16]`＋`verdict_id` `[:12]` · `Fin_Agent` `md5` 全 32 · `Textbook` `sha256` 全 64 · 本仓 `inbox` `sha256sum` 全 64）；且 `Open_Data` **已把这类事故写成断言** —— `raster_id` "与 md5 **同长度不同语义** … **「同长度/同形态」不构成「同语义」**" | **待 D7-P1-2 落地回填**（首个新产物按四项写定 + `sha256sum -c` 仍 PASS）；**不追溯 ⇒ 存量 id 不动**（`Textbook` 20,236 条 KG 边等一概不重算） | 同 D-21 §14 项 12 · §14.1 逐条第 12 行 · §11.6 · [inbox/README §5](../../inbox/README.md)（`-c` 承诺）· [路线总表](../../docs/2026-09-23_D6-D7分阶段执行方案.md) §11.2-b 第 5 项 · 待裁 30 |
| **D-24** | **D7 待裁 13：给 `MANIFEST.sha256` 加 `parent`（形成 DAG）**（2026-09-24） | **加，但只加「清单级 parent」**：① 形态 = 头部 **`#` 注释行**（`# parent: <content-id>`，允许 0..n 行）；② 值 = **上游清单自身的内容哈希**（SHA256，按 D-23 的四项规则），**不得是时间戳或路径**；③ **绝不写进哈希行**；④ **逐件（边级）parent 不在本条** ⇒ 归 `D7-P1-3`（U-3 边格式，形态 = sidecar，**`provenance` 缺 ⇒ 边无效**）；⑤ 范围**只限交付侧 `30_evidence`** —— `00_handoff` 侧是"外部副本漂移基线"（钉外部原样，无上游产物）⇒ **不加**；⑥ **不追溯**已冻结清单 | 不加 `parent`（现状）· 把 `parent` 写进哈希行 · 逐件 parent 也塞进头部注释 · 给 `00_handoff` 侧也加 | §9.2.4 实况表：**依赖边 ❌ 缺**（证据链是 `prev_hash` **线性链，不是 DAG**）；§9.2.1 铁律 **"必须用内容寻址，不能用时间戳"**（Turbopack 原话："manually declaring and adding dependencies to a graph is prone to human errors"）；§14.1：**13 是 14 的硬前置** —— 无 `parent` ⇒ H-2 无从遍历依赖边 ⇒ H-1 成空话、H-2/H-3 空转（只能一律全量降级）。**★ 消费者核对（D6-P1 纪律，共 4 处）**：`cluster.py:_inbox_seal`（唯一写者）· `tests/test_inbox_seal.py:data_lines()`（**python 版 `-c` 复验器，已按 `#` 过滤 + 以 `<hex>  <relpath>` 解析**）· `rpc_check.py:check_inbox`（只判存在）· `inbox/_template/30_evidence/README.md` + `inbox/README §5`（对外承诺）⇒ **头部加行对 4 者全透明**；成本**低**（`sha256sum` 格式不动，只写伴随元数据） | **待落地回填**（seal 输出含 `# parent:` 行；`sha256sum -c` 正例全 OK；**篡改 1 件 ⇒ 恰好 1 条 FAILED** 反例，防恒真） | [D7 调研合并稿](../../docs/2026-09-23_D7调研_立项·机制·统一基座.md) §14 项 13 · §14.1 逐条第 13 行 · §9.2.1 / §9.2.4 · M-1 · [路线总表](../../docs/2026-09-23_D6-D7分阶段执行方案.md) §4.3（D7-P1-3）· §8.2（C 组） |
| **D-25** | **D7 待裁 30：算法标识前缀是否破坏 `sha256sum -c` 兼容性**（2026-09-24） | **采纳建议值 —— 不破坏**：① **算法标识不写进哈希行**，写**头部 `#` 注释 / 伴随元数据**（与 D-24 的 `parent` 同一位置）；② 哈希行格式**永久固定**为 `<64位hex><两空格><相对路径>`；③ 把「忽略 `#` 行」从**两处口头承诺升级为可机判回归用例**（正例 + 篡改反例），挂 `D7-P1-2` | 把算法前缀写进哈希行（`sha256:<hex>  path` 或追加第三列） | **本轮一手实测**（coreutils 8.32 / Git for Windows）：**正例** `# 注释行` + `<hex>  a.txt` ⇒ `a.txt: OK`、**exit 0**；**反例（关键）** `<hex>  a.txt  parent=abc` ⇒ `a.txt  parent=abc: FAILED open or read` ＋ `WARNING: 1 listed file could not be read`、**exit 1**（**整行被当作文件名**）；**中文注释头亦 OK**（本仓头部本就是中文）；且既有实践**已是该形态** —— `00_handoff/MANIFEST.sha256` 头部 5 行 `#`（其第 5 行自述"忽略开头 # 行"）· `_inbox_seal` 头部 6 行 `#` · `inbox/_template/30_evidence/README.md:19` 明记"忽略 `#` 行"。**⚠ 如实标注**：首测曾出现一次**不可复现**的 `EXIT=1`（同场景重跑即 0，当时 stderr 未捕获）⇒ **不作结论**；上列正/反例均在 `2>&1` 下复现 | **待 D7-P1-2 落地回填**：新用例须**先验红**（把标识写进哈希行 ⇒ 用例必须变红）；**站上 Linux coreutils 版本未实测** ⇒ 落地时在站上跑同一组正/反例；存量清单**不重算**（与 D-23 一致） | 调研稿 §14 项 30 · [inbox/README §5](../../inbox/README.md) · `inbox/_template/30_evidence/README.md` · [路线总表](../../docs/2026-09-23_D6-D7分阶段执行方案.md) §11.3 第 5 项 · D-23 |
| **D-26** | **D7 待裁 14：U-4 是否采用 H-1~H-4（含"无法安全判定 ⇒ 强制全量降级"）**（2026-09-24） | **采用（四条全采，照 RFC-0002 的 MUST 级语义，不改写）**，并加五条落地约束：① **每条配一条可机判判据**；② **H-3 的"降级"必须有可机判的呈现位** —— 落进 `D6-P0-1` 的「**非执行三分**」（`MODE_SKIP` 合法 / `SKIP_FAILED` 算失败 / `WARN` 环境降级），**禁止静默 skip**；③ **首靶 = `E:\Macro_Data\src\cleaning\revision_propagation.py`**，且**沿用该项目自己的命名**（它已命名为"**衍生关系图 + `revision_propagation_log`**"）；④ **边界**：只适用**派生产物**；**append-only 受理痕迹不纳入**（归属见待裁 32，未裁前不动受理目录）；⑤ **H-4 沿用既有惯例并升格为规则**：**原子写**（临时件 + rename），对齐 `_inbox_seal` 的 dry-run / `--go` 纪律 | 不采用（退回"一律全量重算"）· 只采 H-2（保守失效）不采 H-3 · 把"降级"落成**静默 skip** · 给 `Macro_Data` 另造第四种命名 | **★ 本轮一手（读真源码，非二手转述）**：该占位文件 **51 行** · `VERSION = "0.1"  # P0 占位版本` · `propagate()` **恒返** `{"status":"skipped","reason":"vintage_data_insufficient","vintage_date_count":1}` · 退出条件写死"vintage 积累 ≥3 个 vintage_date"。★ **它不是"忘了实现"，而是有意的、有名字的、有退出条件的占位**（Spec §4.1 vs §6.7 张力 ⇒ 依 §6.7 数据驱动决策取 P0 占位）；★ **它已带 `reason` 字段 ⇒ "降级"的语义已经在，只是无判据位** ⇒ 与 H-3 的接口天然对齐。调研稿 §9.2.4 实况表：**失效传播 0/9**；§12.1：三个项目**各自独立命名了同一待建模块**（`Macro_Data` ✅ 本轮已核；`Spec_Workflow` H6 · `Fin_Agent` 粗粒度开关 **本轮未复核**，如实标注） | **待 `D7-P1-4` 回填**：① 四条各一条判据；② `Macro_Data` 首靶改造（**改它不破坏任何现有流程** —— 现为 `method=None` 自动 `skipped`）；③ **反例须先验红**（把降级改成静默 skip ⇒ 用例必须红） | 调研稿 §14 项 14 · §14.1 逐条第 14 行 · §9.2.2 · §9.2.4 · §12.1 · M-2 · [路线总表](../../docs/2026-09-23_D6-D7分阶段执行方案.md) §4.3（D7-P1-4）· §8.2（D 组）· 待裁 32 |
| **D-27** | **D7 待裁 15：采纳"结构性事实不得由 LLM 产生"**（2026-09-24） | **采纳，并给出精确边界（防过度解读）**：① **结构性事实**（依赖边 / 产物 id / 清单 / 传播路径）**必须由确定性机制产生**（内容哈希 · 文件 IO 追踪 · 显式解析）；② **模型可以"提议"结构，但不得"成为"事实** —— 候选边 / 候选 id 须经**确定性机制独立复算**后才准入（复算不过 ⇒ 不入图）；这与本仓既有「**模型不自我盖章、`accept` 由主控断言**」**同源**；③ 与 **D-24** 直接咬合：`parent` 必须是**机制算出**的内容哈希，**不得是模型填的字符串**；④ **机械判据 = 可复算**：结构字段须能被独立重算并与落盘值一致（不符 ⇒ FAIL）；⑤ **采纳范围 = D7 全域**（**横切**待裁 12/13/14 的产生方式） | 让 LLM 直接"补"依赖边（不可验证却**像**事实，**比错误结论更坏**）· 只写进 docstring 当纪律（本仓已证"把设计假设写进 docstring **不足以防失效**"，见 O-34）· 读成"LLM 不得参与结构工作"（**过宽**，会切断"提议"这一正当来源） | RFC-0002 两条 invariant 原文：**"Edges SHOULD contain provenance. Edges without provenance are invalid."** 与 **"No AI in graph construction. Compiler graph facts MUST NOT depend on probabilistic model output."**；★ **本会话已验证**：`_gap_key` · `framework_version` · `MANIFEST` **都是"由内容 / 代码产生"**，而 **O-27 与 O-29 的根因都是"结构性事实两处不一致"** ⇒ 该规则**直接预防这两类**；反例：`Textbook` 的"完成态由文档声明"（§11.3） | **待 `D7-P1-3` / `P1-4` 回填**：边 / 清单的**复算判据** + 正反注入（**模型填一个错的 `parent` ⇒ 必须 FAIL**；机制算出 ⇒ PASS） | 调研稿 §14 项 15 · §14.1 逐条第 15 行 · §9.2.2 · §11.3 · M-3 · **D-24** |

> **⚠ 现状注记 (2026-09-15) — D-14 / D-15 的"链路形态"部分已漂移，决策**意图**仍有效**：
> - LiteLLM 网关 `:4000` **已退役**（2026-09-13, ADR-0002 决策 C 的后续）⇒ D-14 里"绕网关"已无对象，"直连各站引擎端口"成为唯一链路
> - 跨站扇出**不再走 `ssh -NL 18081→A:8080` 隧道**：现行做法是 `agent-cli ... --RemoteHost <站>`，每站独立子进程 + 站内 `_station_ready.sh` **自发现引擎端口**（端口是每载随机/按 conf 的，硬编码隧道口本就会漂）。`_bs2_fanout.py`/`_bs2_cross.py` 已按 ADR-0004 清减删除；B 站 `18081` 现被 conf `davidau-q38-27b-q4k`（llama-single）声明占用
> - **D-15 的并发铁律本身不变**：fan-out 优先跨站各 1 并发、勿同站叠

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
| ADR-0002 | 网关 401 根因 + fan-out 路由决策：绕网关直连 B/A:8080 | D-14 直接继承：D6 模型链路绕 LiteLLM，跨站走 ssh 隧道（**2026-09-15 现状：网关已退役、隧道已弃用，见 §1 表下注记**） |

## 5. 决策维护规则

1. **新增决策必登记**: 任何影响 D6 架构/契约/路由/并发的新决策，必须在本表新增行（含依据+验收证据），禁止只在代码注释/会议口头记录
2. **决策链可溯**: 每个决策可反向追溯到调研章节/ADR/验收证据（DESIGN §3.1 已有决策→调研映射，本表补"→证据"闭环）
3. **变更审查**: 否决某既有决策时，必须新立决策行记录"改了什么/为什么"而非抹除原行——保留决策历史
4. **与 OPEN-ISSUES 联动**: 决策引发的未决项（含否决项的 D7+ 候选）同步登记 OPEN-ISSUES.md

***

**决策记录签字**: 与 DESIGN v1.4 / ADR-0002 / CHECKLIST 验收实况对齐（2026-09-04）。