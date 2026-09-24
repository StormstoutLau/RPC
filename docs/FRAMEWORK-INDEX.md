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
| 三机推理集群使用手册.md（2026-09-09 由"双机推理集群使用手册.md"改名）/ 分布式推理.md / SSH_OPENCODE_SETUP.md 等 | F 类手册/运维文档 |

## D7 域（2026-09-23 新建 —— **例外登记**）

> **为什么在 `docs/` 而不在 `spec/`**：D7 目前只有**路线 + 调研**，**尚无实现**（一行代码未改）；
> 且这批文档被**受理机制 / 手册 / 台账**多处交叉引用（仅路线总表就有 9 处入站链接）。
> ⇒ **按下方"维护规则 1"本应进 spec 域**，此处**显式登记为例外**：
> **待 D7 进入实施阶段（`D7-P1` 落地）时，随实现的 spec 域一并迁入 `spec/d7-*/`。**

| 文档 | 角色 |
|---|---|
| 2026-09-23_D6-D7分阶段执行方案.md（**标题 = 升级路线总表**） | **D6/D7 路线唯一权威源**（含 §11 影响面 · §12 盲区扫描） |
| 2026-09-23_D7调研_立项·机制·统一基座.md | D7 **依据汇编**（立项边界 / 四问机制 / 九项目实测 / **36 条待裁**） |
| 2026-09-23_Spec_Workflow能否作为D6-D7工作流基准_调研.md | 基准评估（含 **§8 跨仓复核实录** —— 一次真实的独立主体复核） |
| 2026-09-23_二次裁定取证_证据与断言.md | 对 D6 方案的**逐项实测**（**推翻 5 处估算**） |
| 2026-09-23_Ds工作区扫描_对agent编排与D7的可借鉴分析.md | 27 项来源的**外部工作区场景扫描** |
| DEV-LOG-012-d6-d7-roadmap-and-impact.md | 阶段卷：D6/D7 路线厘清 + 影响面 + 盲区扫描（F 类 DevLog） |
| DEV-LOG-013-dogfood-execution.md | 阶段卷：**吃狗粮首次成批执行**（卡区建立 · 出网档派发 · 反例注入 · O-25 监测核对）（F 类 DevLog） |
| DEV-LOG-014-decision-refinement.md | 阶段卷：**待裁 4 点细化调研与执行**（B1 双卡 · O-41 拆分 · O-46 负向验证 · P2-3 出网档别名）（F 类 DevLog） |

## 维护规则

1. 新调研 → 直接进对应 spec 域（model-eval / rpc-optimization/research / infer-load/research / operator-optimization/research）
2. docs 仅保留：事故根因（E）、审计（G）、手册/DevLog（F）——非调研角色
3. 本索引更新时机：任何"docs ↔ spec"归并动作后
4. **D7 域例外**（2026-09-23）：D7 的路线/调研暂驻 `docs/`，**待其实施时迁入 `spec/d7-*/`**（见上节）