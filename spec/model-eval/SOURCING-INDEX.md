# model-eval 调研文档分类索引

> **维护说明（2026-09-09）**: 将 `spec/model-eval/` 下调研文档分类收敛为 **主文档 + 索引** 两层；新增调研结论直接并入对应主文档，实测数据入 `results-ledger.md`，本索引只指路不重复正文。
> **归档约定**: 已被吸收的原文档以 `.merged.bak.20260909` 后缀保留，非删除（可回溯）。

---

## 文档地图

| 类别 | 主文档 | 内容 | 状态 |
|------|--------|------|------|
| **模型选型** | [MODEL-SOURCING-2026-09.md](./MODEL-SOURCING-2026-09.md) | 三站分布式模型选型总览（四维榜首/候选清单/PR 动态/推荐路线）+ **2026-09-09 附录（附录 A-G：M2.7 & Q3.8F 量化档位/性能损失/社区反馈/契合度/单双站模型池/落地门）** | ✅ 主文档 |
| **推理框架选型** | [FRAMEWORK-SURVEY-2026-09.md](./FRAMEWORK-SURVEY-2026-09.md) | DwarfStar / vLLM / SGLang / llama.cpp RPC 对比（原 STRIX-HALO-DISTRIBUTED-FRAMEWORK-SURVEY 更名）| ✅ 主文档 |
| **实测台账** | [results-ledger.md](./results-ledger.md) | 模型基准/加载/冒烟实测记录（增量**追加**，不覆盖）| ✅ 台账 |
| **评测题库** | questions/ | 各维度评测 prompt 库 | ✅ 附属 |
| **spec 主体** | [DESIGN.md](./DESIGN.md) | model-eval 的设计文档（口径/流程）| ✅ |

## 按专题查找

| 想找什么 | 去哪 |
|----------|------|
| MiniMax-M2.7 全部（基线/量化/性能/反馈/契合）| MODEL-SOURCING 附录 A + C.1 + D |
| Qwen3.8-Flash-Next 全部（基线/量化/性能/反馈/契合）| MODEL-SOURCING 附录 B + C.2 + D |
| V4-Flash / GLM-5.3-Flash / Nemotron 选型 | MODEL-SOURCING 正文 §3-6 + FRAMEWORK-SURVEY §2-4 |
| M2.7 vs Q3.8F 谁做单站主力 | MODEL-SOURCING 附录 D.3（结论：Q3.8F 首选）|
| 单站能装哪些模型 | MODEL-SOURCING 附录 E.1 |
| 双站/RPC 吞吐模型 | MODEL-SOURCING 附录 E.2 + FRAMEWORK-SURVEY |
| 量化档怎么选（1-bit 警示/4-bit 甜点）| MODEL-SOURCING 附录 C（铁律）|
| llama.cpp 算子/PR 状态 | MODEL-SOURCING §6a 旁 + **upstream-tracker/TRACKER.md（活数据权威）** |
| 实测数字（某模型加载 t/s）| results-ledger.md |

## 关联锚点（跨 spec）

- `upstream-tracker/TRACKER.md` — llama.cpp PR/版本状态活数据（选型依赖的动态源）
- `project_memory.md` — 硬约束（load-gate/禁叠加/内存账本纪律）
- `d6-agent-standard/` — agent-cli 运行层（模型经 ROUTE_TABLE 引用）

## 维护规则（新增调研时）

1. 新模型/新证据 → 并入 MODEL-SOURCING（正文或新增附录节），不新建平行文档
2. 新实测 → results-ledger 追加行
3. 框架变化 → FRAMEWORK-SURVEY
4. 被并入的旧文档 → `.merged.bak.<date>` 归档保留
5. 本索引保持"只指路"——若正文移动，同步更新本表锚点