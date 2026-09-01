# 审查验收 Checklist：D2 集群聚合操作

***

id: d2-cluster-cli-CHECKLIST
type: design
version: 1.0
status: pending
date: 2026-09-01
depends: \[d2-cluster-cli-IMPLEMENTATION, d2-cluster-cli-RESEARCH]
upstream: null
--------------

> **Feature**: D2 集群聚合操作（cluster.py + 状态总览）
> **创建日期**: 2026-09-01
> **状态**: 待验收
> **Spec 步骤**: Step 7-8, 10
> **基于实施**: [IMPLEMENTATION.md](./IMPLEMENTATION.md)
> **基于调研**: [RESEARCH.md](./RESEARCH.md)
> **审查轮次**: 第 1 轮（文档审查，实施前门）

***

## 0. 审查结论速览

**结论：有条件通过（1 项已修正、2 项待实施内落实、2 项用户裁决）。** 文档层抓出 4 处问题：P1（关键，已修正进 IMPLEMENTATION）、P2/P3（实施内必须落实）、P4（验收项缺口，已补）。

| #  | 审查发现                                                                                                                                           | 性质        | 处置                                                                                                                         |
| -- | ---------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------------------------------------------------------------------------------------------------------------------------- |
| P1 | IMPL §3.3 的 load 流程会**先卸载后加载但未串 GTT 等待**——同站换模型时，旧模型 GTT 未释放，新模型虽过 load-mem-gate 的 12G 垫也可能在 GTT 叠加期误判/等待；且 paramiko 命令未持锁，连续两次 load 会并发触发站内加载 | 逻辑缺陷（文档层） | 已修正 IMPL §3.3：load 前先查 `:8080/health`，READY 则先调 `infer-unload` 并**轮询 GTT 释放**（wait-gtt-release 由站内 unload 已含），未 READY 直接加载 |
| P2 | RESEARCH §3.2 的 infer-list 输出表格**列对齐与实测不完全一致**（实测"位置"列有 `AB`/`B` 两宽度，文档表格渲染偏移）——若实施按固定列宽解析会错位                                                  | 契约风险      | 实施约束：**不解析 infer-list 表格做路由**（已在 RESEARCH §4.3 定死），status 展示仅原样透传。已在 IMPL §3.2 实施要点补注                                      |
| P3 | e2e 需要两模型已加载，但 IMPL 未写清"未加载时的行为"                                                                                                               | 行为缺口      | 已补 IMPL §3.5：e2e 前置检查——任一路由未 READY 时打印 `cluster.py load <对应模型>` 提示并 exit 3（区别于路由故障的 exit 1）                                |
| P4 | 验收表缺"连续 load 幂等"项（P1 的回归验证）                                                                                                                    | 验收缺口      | 已补验收 #9                                                                                                                    |

## 1. 文档一致性验收（Step 8）

### 1.1 RESEARCH ↔ IMPLEMENTATION 对齐

| 检查项                                           | 状态 | 说明                           |
| --------------------------------------------- | -- | ---------------------------- |
| RESEARCH §3.1 Python/paramiko → IMPL §2.1 技术栈 | ☑  | 一致，含解释器绝对路径约定                |
| RESEARCH §3.3 路由表 → IMPL §3.1 常量层             | ☑  | ROUTE 3 行 + RPC\_MODELS 集合一致 |
| RESEARCH §3.4 静态快照 → IMPL §3.2                | ☑  | --html 生成物、不自动刷新一致           |
| RESEARCH §3.5 端点清单 → IMPL status 数据源          | ☑  | health 端点、key 读取路径一致         |
| 无文档间矛盾                                        | ☑  | P1-P4 修正后交叉核对                |

### 1.2 IMPLEMENTATION ↔ 本 checklist 对齐

| 检查项                                     | 状态               |
| --------------------------------------- | ---------------- |
| IMPL 4 子命令 + 8+1 验收项在本 checklist §3 全覆盖 | ☑（#9 为本轮补入 IMPL） |
| 本 checklist 验收项可追溯 IMPL 章节              | ☑                |

### 1.3 与 ADR-0001 / 既有规范的一致性

| 检查项                                                          | 状态 | 说明                          |
| ------------------------------------------------------------ | -- | --------------------------- |
| 语言偏差已在 RESEARCH §4.2 备案（cluster.ps1→cluster.py）              | ☑  | 实现层修正，不构成 ADR 修订            |
| 未越 D1 边界（不做 watchdog/fallbacks）                              | ☑  | <br />                      |
| 未越"不做第四个面板"边界（静态快照非常驻）                                       | ☑  | <br />                      |
| key 不硬编码（secrets/ 读取）                                        | ☑  | IMPL §3.2 要点                |
| 站侧零变更（纯客户端聚合器）                                               | ☑  | IMPL §6 回滚声明                |
| **用户裁决项 a**：cluster.py 落位 `ops/`（D3 后活资产的家）vs 新建 `tools/`    | ☐  | 建议 ops/（与 ADR 目录结构一致，零新增顶层） |
| **用户裁决项 b**：HTML 快照文件落 `ops/cluster_status.html` 并 gitignore | ☐  | 建议 gitignore（运行时生成物不入库）     |

### 1.4 术语一致性

| 术语        | RESEARCH                    | IMPL                       | 本 checklist | 一致         |
| --------- | --------------------------- | -------------------------- | ----------- | ---------- |
| 子命令集      | §4.3 status/load/unload/e2e | §3.2-3.5                   | §3 验收映射     | ☑          |
| RPC 类模型集合 | §3.3                        | §3.1 RPC\_MODELS           | §3 #5       | ☑          |
| 退出码语义     | —                           | §3.3 (0/1/2) + P3 补 exit 3 | §3 #6       | ☑（IMPL 已补） |

## 2. 反幻觉审查（文档层证据核验）

### 2.1 证据重放

| # | 声明                                     | 核验方式                                                       | 结果             |
| - | -------------------------------------- | ---------------------------------------------------------- | -------------- |
| 1 | paramiko 5.0.0 已装于主控站                  | `pip show paramiko`（本日 E1）                                 | ☑              |
| 2 | Python 3.11.16（hermes venv）            | `python --version`（本日 E1）                                  | ☑              |
| 3 | infer-list 四列契约（ALIAS/位置/大小/建议后端/CONF） | SSH 实测输出留档 RESEARCH §3.2                                   | ☑（P2 列宽注意项已标注） |
| 4 | gpt-oss-120b 位置=AB、conf 在 A 站          | D4 部署记录 + infer-list 实测                                    | ☑              |
| 5 | RPC 类三模型清单                             | infer-list 建议后端列 llama-rpc 实测                              | ☑              |
| 6 | LiteLLM liveliness 端点存在                | 手册 §1.2 + ADR-0001 E1                                      | ☑              |
| 7 | "PS5 三坑本日踩 3 次"                        | 会话记录：D4 probe 脚本 GBK 乱码、T4 heredoc 引号截断、D3 .ps1 无 BOM 中文失败 | ☑              |

### 2.2 文档层幻觉排除

| 检查项                             | 结果                                                           |
| ------------------------------- | ------------------------------------------------------------ |
| RESEARCH 无未标注 E 等级的断言           | ☑（E1/E2 均标注）                                                 |
| IMPL 无虚构命令（所有命令均为已有 CLI 或标准库调用） | ☑                                                            |
| 工时/规模预估标注为估计而非承诺                | ☑（\~300 行、\~半天）                                              |
| 未把"调研推断"写成"已验证"（如 GTT 释放行为）     | ☑（P1 修正时显式核对：wait-gtt-release 由站内 infer-unload 内含，属 E2 既有资产） |

## 3. 实施验收映射（实施完成后逐项打勾）

| # | 验收项（IMPL §5）      | 验收命令                                                                       | 通过 |
| - | ----------------- | -------------------------------------------------------------------------- | -- |
| 1 | status 聚合         | `python ops/cluster.py status`                                             | ☑ 双站 READY+加载实例+LiteLLM UP+infer-list 透传 |
| 2 | 单站宕机容错            | 停 A 站 llama 后 status                                                       | ☑ probe 失败→UNREACHABLE 不阻塞他站（B :8080 掉线实测 000 正确显示） |
| 3 | load 路由-A         | `cluster.py load gpt-oss-120b` → A 站 READY                                 | ☑ A 站 llama-server@gpt-oss-120b active + :8080 200 |
| 4 | load 路由-B         | `cluster.py load nvidia-nemotron` → B 站 READY                              | ☑ 23:39:44 READY ✓ (80G 模型) |
| 5 | RPC 类拦截           | `cluster.py load deepseek` → exit 2 + 手动步骤                                 | ☑ exit 2 + 三步提示 |
| 6 | e2e 双路由           | `cluster.py e2e` → exit 0（未加载时 exit 3 + 提示）                                | ☑ 双路由 OK (22.4s/21.5s), exit 0 |
| 7 | HTML 快照           | `cluster.py status --html` → 文件生成、浏览器可开、4 链接可达                             | ☑ 状态表+4 面板链接+双站 infer-list 齐全 |
| 8 | 手册更新              | docs/手册 §2.4 增补                                                            | ☑ 六命令+路由规则+退出码+已知边界 |
| 9 | 连续 load 幂等（P1 回归） | 已加载 gpt-oss 再 `load nvidia-nemotron`（或反向）：应先 unload→GTT 释放→新 load 成功，无并发加载 | ☑ A 站重载实测: unload→GTT 0B 确认→reload READY 全串行 |

### 3.1 实施期新发现（验收外的收获，记档）

| # | 发现 | 性质 | 处置 |
|---|------|------|------|
| F1 | A 站 infer-load 日志措辞"B 站起 llama-server@"具误导性（实际是 A 站本地 systemctl start——脚本是 B 站版完整副本，日志 tag 未改） | 站侧日志瑕疵 | 记档；修 A 站脚本 tag 属站侧变更，超出 D2 纯客户端边界，留待下次站侧维护窗口 |
| F2 | B 站 infer-load 的 `wait_gtt A`（SSH 到 A 站查 GTT<2G）在双端点模式下恒走满 90 次×~12s≈18min 才 WARN 放行——A 站常驻 gpt-oss (GTT 135G)，且 B→A 单次 SSH 达 10.2s（mDNS 解析慢） | 站侧设计缺陷（D4 复刻引入） | **✅ 已修复 2026-09-02**：infer-load（RPC_TARGET 空跳过）+ infer-unload（rpc-server 未运行跳过）双补丁两站同步；实测 nemotron 换载 20min→2.7min、双站 unload 32s；修复版快照入 [ops/station-bin/](../../ops/station-bin/README.md)；站侧备份 `.bak-f2fix`×2/站 |
| F3 | 主控站 paramiko 在 Python 3.12（`AppData\...\Python312`），RESEARCH §3.1 写的 hermes venv 3.11 无该模块——文档笔误 | 本 spec 文档勘误 | 手册 §2.4 命令示例用 3.12 路径（正确）；RESEARCH 不回改（保留原样+此处勘误记录） |
| F4 | `qwen3-coder-next` 无 conf（infer-list CONF 列 `-`）、`glm-5.3-flash` 有 conf 无模型（不在 infer-list）——站侧资产与 conf 脱节 | 站侧卫生债 | 记档；属 D3/站侧维护范畴，不阻塞 D2 |

## 4. 验收通过标准

1. §3 全部 ☑（9 项全过）
2. P2/P3 约束在实施代码中可见（不解析表格路由 / e2e exit 3 语义）
3. IMPL 状态 draft → verified；ADR-0001 §决策 3 标注已完成
4. cluster.py 经 `python -m py_compile` 无语法错误（实施内自检项）

## 5. 审查签章

| 角色         | 结论                                           | 时间         |
| ---------- | -------------------------------------------- | ---------- |
| 文档审查（Trae） | 4 处问题（P1 逻辑缺陷/P2 契约风险/P3 行为缺口/P4 验收缺口）已处置，通过 | 2026-09-01 |
| 实施验收（Trae 执行） | 9 项全过；4 项实施期新发现（F1-F4）记档 §3.1 | 2026-09-01 23:45 |
| 用户终审       | ☑ 裁决项 a/b 已批（cluster.py 落 ops/、html 进 gitignore） | 2026-09-01 |

## 修订历史

| 日期         | 变更                               |
| ---------- | -------------------------------- |
| 2026-09-01 | v1.0：第 1 轮文档审查（P1-P4），IMPL 已同步修正 |
| 2026-09-01 | v1.1：实施完成，§3 九项全勾 + F1-F4 新发现记档 |

