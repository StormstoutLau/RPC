# spec/ — 规格、判据与执行计划

> **定位**：本目录是**规范与判据**（做什么、怎么判、做到哪）；**裁定**在 [adr/](../adr/README.md)，**操作记录与手册**在 [docs/](../docs/README.md)。
> **索引**：带元数据的文档统一见 [docs/INDEX.md](../docs/INDEX.md)（含 `status` / `date`，可按字段筛）。

## 先看哪一篇

| 问题 | 落点 |
|---|---|
| 未决问题、状态、证据、下一步 | [d6-agent-standard/OPEN-ISSUES.md](./d6-agent-standard/OPEN-ISSUES.md)（**唯一真值台账**） |
| agent 标准（D6）与结论契约（D7） | [d6-agent-standard/DESIGN.md](./d6-agent-standard/DESIGN.md) · [d6-agent-standard/D7-PROTOCOL-CONCLUSION-CONTRACT.md](./d6-agent-standard/D7-PROTOCOL-CONCLUSION-CONTRACT.md) |
| 片间依赖边（`needs=`）设计与分期 | [graph-shard-dependency/DESIGN.md](./graph-shard-dependency/DESIGN.md) |
| 上游 PR / 引擎基线（活数据） | [upstream-tracker/TRACKER.md](./upstream-tracker/TRACKER.md)（**唯一真值**） |
| 模型评估与框架选型 | [model-eval/FRAMEWORK-SURVEY-2026-09.md](./model-eval/FRAMEWORK-SURVEY-2026-09.md) |

## 主题目录

| 目录 | 篇数 | 主题 |
|---|---|---|
| `d6-agent-standard/` | 136 | D6 wrapper 标准 + D7 协议 + 任务卡 + 台账 |
| `rpc-optimization/` | 12 | RPC 引擎/吞吐优化 |
| `vulkan-version-control/` | 10 | Vulkan 版本与回退 |
| `model-eval/` | 6 | 模型评估与框架选型 |
| `infer-load/` | 5 | 模型加载 |
| `cluster-orchestration-reliability/` | 4 | 集群编排可靠性 |
| `operator-optimization/` | 4 | 服务化与编排 |
| `graph-shard-dependency/` | 3 | 片间依赖边（乙 → 甲1 → 甲2） |
| 其余（`review-p1/p2-*`、`d1`–`d5`、`ds4-backend` 等） | 各 1–3 | 一次性专题或复核 |

## 写作纪律

- 每份 spec 三件套：`DESIGN.md`（为什么/怎么设计）· `IMPLEMENTATION.md`（分几步、每步验收）· `CHECKLIST.md`（可勾选判据）。
- **未实测必登记**：必须有 `## 未实测登记` 节（门禁 `spec-untested` 判）。
- **状态两处一致**：YAML `status:` 与正文状态行（门禁 `doc-status` 判）。
- **结论落台账**：闭环项在 `OPEN-ISSUES.md` 打 ✅；未闭环写证据与下一步。
