# docs/ 框架与模型调研分类索引（2026-09-09）

> **维护说明（2026-09-09）**: 对 `docs/` 散落的推理框架/模型调研文档执行归类收敛——已并入 `spec/` 域或归档；本索引只指路不重复正文。归类规则（将并入 spec）见下方"文档地图"。

## 已归并（spec 侧主文档）

| 原 docs 文档 | 归并去向 | 状态 |
|------|---------|------|
| DSpark与Flash模型加速框架调研.md | `spec/model-eval/FRAMEWORK-SURVEY-2026-09.md` 附录 H.1 | 已归档 `.merged.bak.20260909` |
| llama后端盘点与ds4部署方案_20260908.md | `FRAMEWORK-SURVEY` 附录 H.2 | 已归档 |
| DwarfStar部署深入调研_20260908.md | `FRAMEWORK-SURVEY` 附录 H.2/H.3 | 已归档 |
| MiniMax-M3调研_20260908.md | `FRAMEWORK-SURVEY` 附录 H.3 | 已归档 |
| GLM-5.3-Flash-分布式部署调研.md | `FRAMEWORK-SURVEY` 附录 H.4 | 已归档 |
| Qwen3.8-Flash-Next_StrixHalo部署调研.md | `spec/model-eval/MODEL-SOURCING-2026-09.md` 附录 H.1 | 已归档 |
| Qwen3.8-Flash-Next社区实测调研_20260909.md | `MODEL-SOURCING` 附录 H.2 | 已归档 |
| gpt-oss-120b后训练生态与Astra蒸馏调研_20260908.md | `MODEL-SOURCING` 附录 H.3 | 已归档 |
| RPC协议瓶颈调研.md | `spec/rpc-optimization/research/` | 已移入 spec |
| RPC串行跨链社区优化调研.md | `spec/rpc-optimization/research/` | 已移入 spec |
| AMD395分布式推理高性能互连方案调研.md | `spec/rpc-optimization/research/` | 已移入 spec |
| AMD平台算子层优化与USB4分布式调研.md | `spec/rpc-optimization/research/` | 已移入 spec |
| unsloth引擎对比测试_20260908.md | `spec/infer-load/research/` | 已移入 spec |
| C站unsloth推理验证_20260908.md | `spec/infer-load/research/` | 已移入 spec |
| 双机推理服务化与编排框架调研.md | `spec/operator-optimization/research/` | 已移入 spec |
| 模型路径统一方案A_20260909.md | `spec/operator-optimization/research/` | 已移入 spec |

## 保留在 docs（角色不同，不归并）

| 文档 | 角色 |
|------|------|
| V4-Flash-0731加载崩溃根因分析_20260908.md | E 类事故根因（回溯保留）|
| V4复现-无rpccache与环网异常落档_20260908.md | E 类事故根因 |
| A站挂死根因分析_20260901.md | E 类事故根因 |
| C站硬件身份与BIOS更新源分析_20260908.md | E 类事故根因 |
| 三调研报告审计.md | G 类审计 |
| 双机剩余优化空间评估.md | G 类评估 |
| 提速调研报告.md | G 类历史调研 |
| DEV-LOG-* | F 类 DevLog |
| 双机推理集群使用手册.md / 分布式推理.md / SSH_OPENCODE_SETUP.md 等 | F 类手册/运维文档 |

## 维护规则

1. 新调研 → 直接进对应 spec 域（model-eval / rpc-optimization/research / infer-load/research / operator-optimization/research）
2. docs 仅保留：事故根因（E）、审计（G）、手册/DevLog（F）——非调研角色
3. 本索引更新时机：任何"docs ↔ spec"归并动作后