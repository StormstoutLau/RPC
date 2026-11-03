# 文档索引（生成物）

> ⚠ 本文件由 `py -3 ops/rpc_doc_index.py --write` **自动生成**，**禁止手工编辑**。
> 权威源 = 各文档的 YAML front-matter（`id` / `type` / `version` / `status` / `date`）。
> 改文档头 → 重跑 `--write`；校验用 `--check`（不一致 exit 1）。

共 **242** 篇（不含 README / INDEX / 卡片目录 / archive）。

## adr/

| 文档 | id | type | status | date |
|---|---|---|---|---|
| [ADR-0001: 集群运维框架审计结论与四项改进决策](../adr/ADR-0001-集群运维框架审计与四项改进决策.md) | `—` | adr | — | — |
| [ADR-0002: 网关 401 故障根因分析与 fan-out 路由决策（绕网关编排层直连）](../adr/ADR-0002-网关401故障根因与fan-out路由决策.md) | `—` | adr | — | — |
| [ADR-0003: OpenRouter API 密钥与 egress 路由管理](../adr/ADR-0003-OpenRouter密钥与egress路由管理.md) | `—` | adr | — | — |
| [ADR-0004: 统一管理入口为唯一管理面（禁止重复生成一次性脚本）](../adr/ADR-0004-统一管理入口为唯一管理面.md) | `ADR-0004` | adr | accepted | 2026-09-15 |
| [ADR-0005: 任务卡证据回收闭环（阶段 0）—— 判据原始记录与输入全文归主控归档](../adr/ADR-0005-任务卡证据回收闭环.md) | `ADR-0005` | adr | accepted | 2026-09-16 |
| [ADR-0006: 控制面传输绑定 LAN IPv4 —— 消除 `*.local` 解析的 16s 与"控制面走公网 IPv6"](../adr/ADR-0006-控制面传输绑定LAN_IPv4.md) | `ADR-0006` | adr | accepted | 2026-09-16 |
| [ADR-0007: 证据流可重放性 —— 阶段推进路线修正 + 改动验证闭环](../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md) | `ADR-0007` | adr | accepted | 2026-09-17 |
| [ADR-0008: 跨项目受理区（RPC inbox）与目录治理](../adr/ADR-0008-跨项目受理区与目录治理.md) | `ADR-0008` | adr | accepted | 2026-09-23 |
| [ADR-0009: D6 与 D7 的分界判据（可机械判定）](../adr/ADR-0009-D6与D7分界判据.md) | `ADR-0009` | adr | accepted | 2026-09-26 |
| [ADR-0010: DwarfStar (ds4) 第二引擎引入立项（B 站单站试点）](../adr/ADR-0010-DwarfStar第二引擎引入立项.md) | `ADR-0010` | adr | accepted | 2026-09-28 |
| [ADR-0011: A4（vLLM TP=2）暂缓裁定 —— vLLM 路径的定位、门槛与重启条件](../adr/ADR-0011-A4-vLLM-TP2-暂缓裁定.md) | `ADR-0011` | adr | accepted | 2026-09-29 |
| [ADR-0012: A 站容器栈纳管（Docker / searxng）—— 纳入唯一管理面](../adr/ADR-0012-A站容器栈纳管.md) | `ADR-0012` | adr | accepted | 2026-09-30 |
| [ADR-0013: 跨仓库使用本框架的治理边界 —— 「受理（准入）」与「逐任务派发」分界](../adr/ADR-0013-跨仓库使用本框架的准入与派发分界.md) | `ADR-0013` | adr | accepted | 2026-10-03 |
| [ADR-0014: halogen 引擎引入（A 站 · 测试性）+ 容器管理扩权（只读 → 写动作）](../adr/ADR-0014-halogen引擎引入与容器写动作扩权.md) | `ADR-0014` | adr | accepted | 2026-10-10 |
| [ADR-0015: 飞书远程操作桥接引入（受控常驻例外）](../adr/ADR-0015-飞书远程操作桥接引入.md) | `ADR-0015` | adr | accepted | 2026-10-30 |

## docs/

| 文档 | id | type | status | date |
|---|---|---|---|---|
| [B站 USB4 无连接排查与归因归档 (2026-09-15)](2026-09-15_B站USB4无连接排查与归档.md) | `—` | docs | — | — |
| [统一管理入口 · 深入分析与优化方案 (v2)](2026-09-15_统一管理入口_深入分析与优化方案_v2.md) | `—` | docs | — | — |
| [统一管理入口 · 调研与优化方案（v1 ⚠️ 已废）](2026-09-15_统一管理入口调研与优化方案.md) | `—` | docs | — | — |
| [升级决策简报 —— unsloth studio 升级（网关 UI 控制帧致本地 provider 压缩失效）](2026-09-22_决策简报_unsloth-studio升级方案.md) | `—` | docs | — | — |
| [2026-09-22_门禁口径决策简报_doclinks越界链与root级脚本范围](2026-09-22_门禁口径决策简报_doclinks越界链与root级脚本范围.md) | `rpc-decisions-2026-09-22-doclinks-root-scripts` | decision-brief | 已裁定并实施 | 2026-09-22 |
| [D6 / D7 升级路线总表 —— 统一编号 · 阶段 · 依赖 · 退出判据](2026-09-23_D6-D7分阶段执行方案.md) | `—` | docs | — | — |
| [D7 调研（合并稿）—— 立项 · 机制 · 统一基座](2026-09-23_D7调研_立项·机制·统一基座.md) | `—` | docs | — | — |
| [决策简报 — D:\ds 工作区扫描：对 agent 编排（D6）与未来 D7（站间互审）的可借鉴分析](2026-09-23_Ds工作区扫描_对agent编排与D7的可借鉴分析.md) | `—` | docs | — | — |
| [Spec_Workflow 能否成为 D6/D7 工作流的「基准」—— 调研](2026-09-23_Spec_Workflow能否作为D6-D7工作流基准_调研.md) | `—` | docs | — | — |
| [决策简报 — cluster.py 模块化重构：可行性、仓内约束与社区调研](2026-09-23_cluster.py模块化重构_调研与方案.md) | `—` | docs | — | — |
| [决策简报 — inbox 受理区 community review 与改进建议（ADR-0008）](2026-09-23_inbox受理区_社区review与改进建议.md) | `—` | docs | — | — |
| [合并实施计划 — inbox 治理（受理协议 + 交付证据束）](2026-09-23_inbox治理_合并实施计划.md) | `—` | docs | — | — |
| [二次裁定取证 —— 8 项的证据与断言](2026-09-23_二次裁定取证_证据与断言.md) | `—` | docs | — | — |
| [决策简报 — 需求协商协议（问题1）与 交付证据束标准（问题2）社区调研](2026-09-23_受理协商协议与交付证据束_标准调研.md) | `—` | docs | — | — |
| [决策简报 — 多项目进度看板：自动跟踪 + 更新机制（社区调研与方案）](2026-09-23_项目进度看板_调研与方案.md) | `—` | docs | — | — |
| [决策简报 — Spec_Workflow / Spec_Runner 可借鉴分析：**降低幻觉** 与 **流程物理化**](2026-09-26_Spec_Workflow与Spec_Runner_可借鉴分析.md) | `—` | docs | — | — |
| [#26610（RPC `-sm tensor`）形态验证执行方案（可执行稿）](2026-10-11_26610形态验证执行方案.md) | `—` | docs | — | — |
| [主线引擎升级批次清单（评审稿）](2026-10-11_主线引擎升级批次清单.md) | `—` | docs | — | — |
| [D7 未闭环 P0 · `O-136` 闭合链 —— 设计与实施方案](2026-10-12_D7未闭环P0_O-136闭合链_设计与实施方案.md) | `—` | docs | — | — |
| [单站引擎轴（`~/llama.cpp`）A/B/C 不一致 —— 调研 + 统一方案](2026-10-12_单站引擎轴不一致调研与统一方案.md) | `—` | docs | — | — |
| [引擎升级可行性梳理 + 升级尝试/失败/反馈过程落档](2026-10-12_引擎升级可行性梳理与升级过程落档.md) | `—` | docs | — | — |
| [D7 未闭环 P0 尾款 · `TC/RR` 四项清空 —— 设计与实施方案](2026-10-13_D7未闭环P0尾款_TC-RR四项清空_设计与实施方案.md) | `—` | docs | — | — |
| [D7 未闭环 P1 · `CONCLUSION #6` 兑现 —— 设计与实施方案](2026-10-13_D7未闭环P1_CONCLUSION-6兑现_设计与实施方案.md) | `—` | docs | — | — |
| [`$PROJECTS` 数据化（项目注册表）—— 设计与实施方案](2026-10-13_项目注册表_PROJECTS数据化_设计与实施方案.md) | `—` | docs | — | — |
| [`split` 分片依赖声明（`needs:`）—— 设计与实施方案](2026-10-16_split分片依赖声明needs_设计与实施方案.md) | `—` | docs | — | — |
| [约束文件增益 A/B 验证设计与实施方案（C-1 取证）](2026-10-16_约束文件增益A-B验证设计与实施方案.md) | `—` | docs | — | — |
| [`O-147` 解除暂缓的方案 —— 设计与实施方案（★ **已实施并回写** · 2026-10-20）](2026-10-20_O-147_解除暂缓方案_设计与实施方案.md) | `—` | docs | — | — |
| [`O-147` 丙的落点偏离设计稿 —— 裁决分析（2026-10-20）](2026-10-20_O-147丙落点偏离设计稿_裁决分析.md) | `—` | docs | — | — |
| [`O-148` 站上出网「间歇性发作」的处置 —— 设计与实施方案](2026-10-20_O-148_站上出网发作处置_设计与实施方案.md) | `—` | docs | — | — |
| [`O-162` U-1 坐标语义（口径残余 + 根治后续项）—— 设计与实施方案](2026-10-20_O-162_U1坐标语义_设计与实施方案.md) | `—` | docs | — | — |
| [P-019 独立复验（`F:\Full_Weather`）—— 异基座模型的**派发配置分析**](2026-10-20_p019独立复验_异基座模型配置分析.md) | `—` | docs | — | — |
| [待裁事项：登记清单 · 依赖链 · 优先级 · 执行顺序（2026-10-20）](2026-10-20_待裁事项依赖链与执行顺序.md) | `—` | docs | — | — |
| [O-165 / O-166 判定根与 golden 注入：设计与实施方案](2026-10-23_O-165_O-166_判定根与golden注入_设计与实施方案.md) | `—` | docs | — | — |
| [GLM-5.3-Flash 1M（A+B）+ Qwen3.8-Flash 1M（C）启动与 cc-switch 接入](2026-10-27_GLM1M_Qwen1M_启动与cc-switch接入.md) | `—` | docs | — | — |
| [原始评审 P1 四条修复 · TDD 实施记录](2026-10-27_P1四条修复实施记录.md) | `—` | docs | — | — |
| [Claude Code「无 write 权限」排查 —— 飞书桥接（cc-connect）与 B 站终端](2026-11-02_claude-code无write权限排查_飞书桥接与B站终端.md) | `—` | docs | — | — |
| [Agent CLI 技术选型调研（opencode / Claude Code / Pi / Hermes / 其他）](Agent-CLI技术选型调研_20260909.md) | `—` | docs | — | — |
| [Agent 生态升级与多智能体协作架构调研](Agent生态升级与多智能体协作架构调研.md) | `—` | docs | — | — |
| [Agent CLI 跨项目调用标准与迁移复用调研](Agent跨项目调用标准与迁移复用调研.md) | `—` | docs | — | — |
| [A 站挂死 (Strix Halo NEX) 根因分析 — 2026-09-01](A站挂死根因分析_20260901.md) | `—` | docs | — | — |
| [Claude Code CLI × 本地集群 × opencode 子代理框架分析](ClaudeCode本地集群与子代理框架分析.md) | `—` | docs | — | — |
| [C 站硬件身份与 BIOS 更新源深入分析（2026-09-08）](C站硬件身份与BIOS更新源分析_20260908.md) | `—` | docs | — | — |
| [DEV-LOG-008: Vulkan 后端版本控制（vulkan-version-control）](DEV-LOG-008-vulkan-version-control.md) | `—` | docs | — | — |
| [DEV-LOG-009: llama.cpp v0.2.0 升级执行（UPGRADE_SOP 首次实战）](DEV-LOG-009-v020-upgrade.md) | `—` | docs | — | — |
| [DEV-LOG-010: RPC 优化方案五阶段执行（Phase 0-3 落地）](DEV-LOG-010-rpc-optimization.md) | `—` | docs | — | — |
| [DEV-LOG-011: D6 agent-cli wrapper MVP（设计与实施落地 + 跨站扇出验证）](DEV-LOG-011-d6-agent-standard.md) | `—` | docs | — | — |
| [DEV-LOG-012: D6/D7 升级路线厘清 + 影响面反查 + 盲区扫描](DEV-LOG-012-d6-d7-roadmap-and-impact.md) | `—` | docs | — | — |
| [DEV-LOG-013: 吃狗粮**首次成批执行** —— 卡区建立 · 出网档派发 · 反例注入 · 监测机制核对](DEV-LOG-013-dogfood-execution.md) | `—` | docs | — | — |
| [DEV-LOG-014: 待裁 4 点的细化调研与执行 —— B1 双卡 · O-41 拆分 · O-46 负向验证 · P2-3 出网档别名](DEV-LOG-014-decision-refinement.md) | `—` | docs | — | — |
| [docs/ 框架与模型调研分类索引（2026-09-09）](FRAMEWORK-INDEX.md) | `—` | docs | — | — |
| [SSH + opencode 远程调用配置排查记录](SSH_OPENCODE_SETUP.md) | `—` | docs | — | — |
| [V4-Flash-0731 加载崩溃根因分析（2026-09-08）](V4-Flash-0731加载崩溃根因分析_20260908.md) | `—` | docs | — | — |
| [V4 复现：无 rpccache 与环网异常落档（2026-09-08）](V4复现-无rpccache与环网异常落档_20260908.md) | `—` | docs | — | — |
| [llama 后端来源溯源分析（2026-09-08）](llama后端来源溯源分析_20260908.md) | `—` | docs | — | — |
| [D6 多项目跨站调用与隔离机制分析报告（2026-09-14）](research/2026-09-14_D6多项目跨站调用与隔离机制分析.md) | `—` | docs | — | — |
| [OpenRouter 接入与 agentic-harness 门禁调研（2026-09-14）](research/2026-09-14_OpenRouter接入与agentic-harness门禁调研.md) | `—` | docs | — | — |
| [暴露问题调研：opencode run 卡死 / 默认模型漂移 / A 站剩余明文面](research/2026-09-14_暴露问题调研.md) | `—` | docs | — | — |
| [任务卡证据流"可独立重放性"调研：evidence_manifest 字段 与 编排管线审计](research/2026-09-16_任务卡证据流可重放性调研.md) | `—` | docs | — | — |
| [分布式推理路线可行性调研：CIRU StrixLink / Skulk（含 vLLM 多机 TP 与 AMD 官方路线）](research/2026-09-16_分布式推理路线可行性调研_CIRU-Skulk-多机TP.md) | `—` | docs | — | — |
| [三站系统 ROCm 统一 7.2.4 — 工作总结报告](research/2026-09-17_ROCm三站统一7.2.4_总结报告.md) | `—` | docs | — | — |
| [任务卡证据流"协同篡改"威胁——补充调研](research/2026-09-17_任务卡证据流_协同篡改威胁_补充调研.md) | `—` | docs | — | — |
| [证据流审计「常跑」调研：触发点 / 成本 / 严重度 三件待定事](research/2026-09-18_证据流审计常跑_触发点与成本严重度调研.md) | `—` | docs | — | — |
| [D6 备路站上化 + sensitivity 设闸 —— 调研与方案（2026-09-21）](research/2026-09-21_D6备路站上化与sensitivity设闸调研与方案.md) | `—` | docs | — | — |
| [claude 备路「免登录 + 后端选型」调研（2026-09-21）](research/2026-09-21_claude备路免登录与后端选型调研.md) | `—` | docs | — | — |
| [DeepSeek V4 系列 · 调研与部署（本集群）](research/2026-09-28_DeepSeek-V4系列调研与部署.md) | `—` | docs | — | — |
| [DwarfStar (ds4) 前置核验与 ROCm 工具链安装决策（2026-09-28）](research/2026-09-28_DwarfStar前置核验与ROCm工具链安装决策.md) | `—` | docs | — | — |
| [DwarfStar (ds4) 集群部署专项方案](research/2026-09-28_DwarfStar部署专项方案.md) | `—` | docs | — | — |
| [GLM 系列本地推理部署（本集群）](research/2026-09-28_GLM系列本地推理部署.md) | `—` | docs | — | — |
| [O-110 / O-112 实测 —— 同站并发退化 vs 模型规模 · DS V4-Flash 单机容量核验](research/2026-09-28_O-110同站并发实测与O-112单机容量核验.md) | `—` | docs | — | — |
| [`D:\Textbook` 并发与派发机制可借鉴性调研](research/2026-09-28_Textbook并发与派发机制可借鉴性调研.md) | `—` | docs | — | — |
| [DeepSeek V4.1 Flash 在 RPC 集群上的部署路径调研](research/2026-09-28_V4.1-Flash部署路径调研.md) | `—` | docs | — | — |
| [Codex CLI 补充调研与接入评估（2026-09-29）](research/2026-09-29_CodexCLI补充调研与接入评估.md) | `—` | docs | — | — |
| [DwarfStar 专属量化清退方案](research/2026-09-29_DwarfStar专属量化清退方案.md) | `—` | docs | — | — |
| [控制面 LAN 地址漂移 · 失效归因与判据升级](research/2026-09-29_控制面LAN地址漂移_失效归因与判据升级.md) | `—` | docs | — | — |
| [路由器「桥 → 路由」模式切换 · LAN 寻址重建与静态化方案](research/2026-09-29_路由器模式切换_LAN寻址重建与静态化方案.md) | `—` | docs | — | — |
| [2026-09-30_RCCL部署方案与集群必要性评估](research/2026-09-30_RCCL部署方案与集群必要性评估.md) | `RESEARCH_2026-09-30_RCCL` | research | research | 2026-09-30 |
| [2026-09-30_kyuz0容器方案评估与现役venv对比](research/2026-09-30_kyuz0容器方案评估与现役venv对比.md) | `RESEARCH_2026-09-30_KYUZ0` | research | research | 2026-09-30 |
| [Hy4-preview（STQ1_0 档）在本集群的部署方案调研](research/2026-10-01_Hy4-preview-STQ1_0本集群部署方案调研.md) | `—` | docs | — | — |
| [Qwen3.8 系列（Flash-Next / 27B）本地推理加速调研](research/2026-10-01_Qwen3.8系列本地推理加速调研.md) | `—` | docs | — | — |
| [图结构编排升级潜力 · 与本地机群算力利用调研](research/2026-10-01_图结构编排升级潜力与机群算力利用调研.md) | `—` | docs | — | — |
| [Hermes Agent 编排对比 + 本框架可借鉴项调研与落地步骤](research/2026-10-16_Hermes-Agent编排对比与本框架可借鉴项调研.md) | `—` | docs | — | — |
| [`O-148` 站上出网间歇失败 —— 社区与一手数据调研（2026-10-20）](research/2026-10-20_O-148站上出网间歇失败_社区调研.md) | `—` | docs | — | — |
| [ADR-0014 开放项闭环调研（2026-10-22）](research/2026-10-22_ADR-0014开放项闭环调研.md) | `—` | docs | — | — |
| [上游引擎与 GLM-5.3-Flash-X 评估（2026-10-22）](research/2026-10-22_上游引擎与GLM-FlashX评估.md) | `—` | docs | — | — |
| [O-165 / O-166 调研：备路「执行点 / 判据点 / 注入点」三处 cwd 不一致](research/2026-10-23_O-165_O-166_备路判定根与golden注入_调研.md) | `—` | docs | — | — |
| [原始评审 P1 事项 · 社区外部锚点调研](research/2026-10-26_原始评审P1_社区外部锚点调研.md) | `—` | docs | — | — |
| [原始评审报告（2026-10-21）RPC 段复核](research/2026-10-26_原始评审报告复核_RPC.md) | `—` | docs | — | — |
| [集群编排与 RPC 选路可靠性 · 社区外部锚点调研](research/2026-10-26_集群编排与RPC选路可靠性_社区外部锚点调研.md) | `—` | docs | — | — |
| [原始评审 P2 小批次 · 社区外部锚点调研](research/2026-10-27_原始评审P2小批次_社区外部锚点调研.md) | `—` | docs | — | — |
| [GPUStack（`D:\gpustack-main`）可复用性分析](research/2026-10-28_gpustack可复用性分析.md) | `—` | docs | — | — |
| [原始评审 P2 大项 · `#5 set -euo` 与 `#8 拆文件/分目录` · 社区外部锚点调研](research/2026-10-28_原始评审P2大项_社区外部锚点调研.md) | `—` | docs | — | — |
| [原始评审 #8B / #8C 调研：`rpc_check.py` 与 `agent-cli.ps1` 的拆分边界](research/2026-10-28_原始评审P2拆分_8B8C_调研.md) | `—` | docs | — | — |
| [调研：三站 Claude Code 接本地 halogen + 手机经飞书远程操作](research/2026-10-30_claude-code三站halogen接入与飞书远程操作调研.md) | `claude-halogen-feishu-2026-10-30` | research | draft | 2026-10-30 |
| [Kyojin 与 Gufo 引擎现状 · 本集群部署可行性 · 与现有配置的优势劣势](research/2026-10-31_Kyojin与Gufo引擎现状与本集群部署可行性调研.md) | `research-kyojin-gufo-20261031` | research | active | 2026-10-31 |
| [接入 AutoResearchClaw 形成统一基座：当期图结构编排未解问题是否可解](research/2026-10-31_接入AutoResearchClaw统一基座_图编排未解问题是否可解_调研.md) | `research-arc-unified-base-graph-questions-2026-10-31` | research | done | 2026-10-31 |
| [片间依赖边：从「只记录」到「可执行」的调研](research/2026-10-31_片间依赖边从观测到执行_调研.md) | `research-graph-shard-dependency-2026-10-31` | research | done | 2026-10-31 |
| [主控站操作 A/B 两个工作站 Claude Code 的便捷方式调研](research/2026-11-02_主控站操作AB站ClaudeCode方式调研.md) | `—` | docs | — | — |
| [多站接入 IM 桥接：实例隔离问题与备选方案调研](research/2026-11-02_多站IM桥接实例隔离与备选方案调研.md) | `—` | docs | — | — |
| [文档分类归档与检索：是否需要 RAG / 知识图谱](research/2026-11-03_文档分类归档与检索_RAG与知识图谱选型调研.md) | `research-doc-archival-retrieval-rag-kg-2026-11-03` | research | done | 2026-11-03 |
| [station-bin 脚本密钥脱敏影响并列清单（2026-09-13）](security/2026-09-13_station-bin_密钥脱敏影响清单.md) | `—` | docs | — | — |
| [安全处置：密钥轮换清单（2026-09-13）](security/2026-09-13_密钥轮换清单.md) | `—` | docs | — | — |
| [OpenRouter 多账户配额分配与调配 —— 方案设计（2026-09-21）](security/2026-09-21_OpenRouter多账户配额分配与调配设计.md) | `—` | docs | — | — |
| [OpenRouter 数据策略与隐私开关 —— 核对与实测（P1，2026-09-21）](security/2026-09-21_OpenRouter数据策略与隐私开关核对.md) | `—` | docs | — | — |
| [ZDR 可行性裁定与影响面清单（P5，2026-09-21）](security/2026-09-21_ZDR可行性裁定与影响面.md) | `—` | docs | — | — |
| [scrubber 规则扩充裁定与影响面（2026-09-21）](security/2026-09-21_scrubber规则扩充裁定与影响面.md) | `—` | docs | — | — |
| [三机推理集群使用手册](三机推理集群使用手册.md) | `—` | docs | — | — |
| [三调研报告审计 — 断言追踪 / 引用核验 / 逻辑链 / 决策依据 / 幻觉排除](三调研报告审计.md) | `—` | docs | — | — |
| [AMD Ryzen AI Max+ 395 多机分布式推理完整技术文档](分布式推理.md) | `—` | docs | — | — |
| [双机部署剩余优化空间评估](双机剩余优化空间评估.md) | `—` | docs | — | — |
| [A 站双端点部署与 opencode 混合框架调研报告（三机群形态更新版）](双端点部署与opencode混合框架调研.md) | `—` | docs | — | — |
| [A/B 双机分布式推理提速调研报告](提速调研报告.md) | `—` | docs | — | — |
| [派生视图：端口分配（只读）](派生视图_端口分配.md) | `—` | docs | — | — |

## spec/

| 文档 | id | type | status | date |
|---|---|---|---|---|
| [agent 任务进度与吞吐可观测性 —— 集成进「统一管理入口」调研](../spec/agent-observability/research/agent任务进度与吞吐可观测性调研.md) | `—` | spec | — | — |
| [B5q 验收 Checklist — 集群基准自动化与 RPC 列表声明化](../spec/cluster-bench/CHECKLIST.md) | `cluster-bench-CHECKLIST` | design | accepted | 2026-08-31 |
| [B5q 集群基准自动化与 RPC 列表声明化 — DESIGN](../spec/cluster-bench/DESIGN.md) | `—` | spec | — | — |
| [审查验收 Checklist：集群编排与 RPC 选路可靠性加固](../spec/cluster-orchestration-reliability/CHECKLIST.md) | `cluster-orchestration-reliability-CHECKLIST` | design | accepted | 2026-10-26 |
| [设计文档：集群编排与 RPC 选路可靠性加固](../spec/cluster-orchestration-reliability/DESIGN.md) | `cluster-orchestration-reliability-DESIGN` | design | draft | 2026-10-26 |
| [DEVELOPMENT-LOG](../spec/cluster-orchestration-reliability/DEVELOPMENT-LOG.md) | `—` | spec | — | — |
| [实施文档：集群编排与 RPC 选路可靠性加固](../spec/cluster-orchestration-reliability/IMPLEMENTATION.md) | `cluster-orchestration-reliability-IMPLEMENTATION` | design | draft | 2026-10-26 |
| [审查验收 Checklist：D1 防挂死与容错补全](../spec/d1-watchdog-fault/CHECKLIST.md) | `—` | spec | — | — |
| [实施文档：D1 防挂死与容错补全](../spec/d1-watchdog-fault/IMPLEMENTATION.md) | `—` | spec | — | — |
| [调研文档：D1 防挂死与容错补全](../spec/d1-watchdog-fault/RESEARCH.md) | `—` | spec | — | — |
| [审查验收 Checklist：D2 集群聚合操作](../spec/d2-cluster-cli/CHECKLIST.md) | `—` | spec | — | — |
| [实施文档：D2 集群聚合操作（cluster CLI + 状态总览）](../spec/d2-cluster-cli/IMPLEMENTATION.md) | `d2-cluster-cli-IMPLEMENTATION` | design | verified | 2026-09-01 |
| [调研文档：D2 集群聚合操作（cluster CLI + 状态总览）](../spec/d2-cluster-cli/RESEARCH.md) | `d2-cluster-cli-RESEARCH` | design | draft | 2026-09-01 |
| [实施记录：D3 目录重构](../spec/d3-restructure/IMPLEMENTATION.md) | `d3-restructure-IMPLEMENTATION` | design | verified | 2026-09-01 |
| [审查验收 Checklist：D4 收尾清理](../spec/d4-closeout/CHECKLIST.md) | `—` | spec | — | — |
| [实施文档：D4 收尾清理（Agent 生态升级前置）](../spec/d4-closeout/IMPLEMENTATION.md) | `d4-closeout-IMPLEMENTATION` | design | verified | 2026-09-01 |
| [调研文档：D4 收尾清理（Agent 生态升级前置）](../spec/d4-closeout/RESEARCH.md) | `—` | spec | — | — |
| [审查验收 Checklist：D5 Agent 生态升级与上下文管理落地](../spec/d5-agent-ecosystem/CHECKLIST.md) | `—` | spec | — | — |
| [设计文档：D5 Agent 生态升级与上下文管理落地](../spec/d5-agent-ecosystem/DESIGN.md) | `—` | spec | — | — |
| [实施文档：D5 Agent 生态升级与上下文管理落地](../spec/d5-agent-ecosystem/IMPLEMENTATION.md) | `—` | spec | — | — |
| [A 清单（A1–A6）：设计底稿勘误与落地排期（2026-09-29）](../spec/d6-agent-standard/A-LIST-LANDING-PLAN.md) | `—` | spec | — | — |
| [架构文档：D6 agent-cli wrapper MVP](../spec/d6-agent-standard/ARCHITECTURE.md) | `—` | spec | — | — |
| [盲区扫描：V2 并发 fan-out 编排（BS-1..6）](../spec/d6-agent-standard/BLINDSCAN-v2-orchestration.md) | `—` | spec | — | — |
| [BLINDSCAN v3 —— **并发脆弱面扫描**（2026-09-23）](../spec/d6-agent-standard/BLINDSCAN-v3-concurrency.md) | `—` | spec | — | — |
| [审查验收 Checklist：D6 agent-cli wrapper MVP](../spec/d6-agent-standard/CHECKLIST.md) | `—` | spec | — | — |
| [D6 与单机 agent CLI 工作流闭环分析报告](../spec/d6-agent-standard/CLOSED-LOOP-ANALYSIS-2026-09-09.md) | `d6-closed-loop-analysis` | research | research | 2026-09-09 |
| [约束文件规范（CONSTRAINTS）：agent prompt 首槽的「约束层」](../spec/d6-agent-standard/CONSTRAINTS.md) | `—` | spec | — | — |
| [跨项目统一工作规范（CROSS-PROJECT WORK STANDARD）](../spec/d6-agent-standard/CROSS-PROJECT-WORK-STANDARD.md) | `—` | spec | — | — |
| [D7 结论契约（Conclusion Contract）—— 受限判定 + 结构化意见 + 综合分类](../spec/d6-agent-standard/D7-PROTOCOL-CONCLUSION-CONTRACT.md) | `—` | spec | — | — |
| [D7 协议契约（六相 · 三信封 · 三红线）](../spec/d6-agent-standard/D7-PROTOCOL-CONTRACT.md) | `—` | spec | — | — |
| [决策记录：D6 agent-cli wrapper MVP](../spec/d6-agent-standard/DECISIONS.md) | `—` | spec | — | — |
| [设计文档：D6 Agent 跨项目调用标准与 agent-cli MVP](../spec/d6-agent-standard/DESIGN.md) | `—` | spec | — | — |
| [DEVELOPMENT-LOG](../spec/d6-agent-standard/DEVELOPMENT-LOG.md) | `—` | spec | — | — |
| [G1 二期——`--continue` Continue-vs-Spawn 决策表](../spec/d6-agent-standard/G1-continue-spawn-decision.md) | `—` | spec | — | — |
| [统一基座模型实测 Agent Harness 调研（编码能力框架级对照）](../spec/d6-agent-standard/HARNESS-SAME-MODEL-BENCH-2026-09.md) | `—` | spec | — | — |
| [实施方案：D6 agent-cli wrapper MVP](../spec/d6-agent-standard/IMPLEMENTATION.md) | `—` | spec | — | — |
| [O-102 工作区行尾漂移 —— 修复闭环验证报告](../spec/d6-agent-standard/O102-line-ending-closure-verification.md) | `—` | spec | — | — |
| [O-21 specaudit 超时 / rc=1 修复闭环验证报告](../spec/d6-agent-standard/O21-ctx-closure-verification.md) | `—` | spec | — | — |
| [D6 剩余 Open 项推进计划（2026-09-14）](../spec/d6-agent-standard/OPEN-ISSUES-PLAN-2026-09-14.md) | `—` | spec | — | — |
| [开放日志：D6 agent-cli wrapper MVP（Open Issues 台账）](../spec/d6-agent-standard/OPEN-ISSUES.md) | `—` | spec | — | — |
| [A/B/C 三站 Agent CLI 插件台账（2026-09-09 起）](../spec/d6-agent-standard/PLUGIN-LEDGER.md) | `—` | spec | — | — |
| [证明状态图（P3）—— AND-OR 超图领域语义与最小闭环设计](../spec/d6-agent-standard/PROOF-STATE-GRAPH.md) | `—` | spec | — | — |
| [D6 开放项：优先级分析与修复计划（2026-09-21）](../spec/d6-agent-standard/REMEDIATION-PLAN.md) | `—` | spec | — | — |
| [RESEARCH: F:\Cpp_Hub 调用三台工作站执行之规范调研](../spec/d6-agent-standard/RESEARCH_2026-09-12_Cpp_Hub_3station.md) | `—` | spec | — | — |
| [model-flavor 吞吐基准表（O-25 P0-①）](../spec/d6-agent-standard/THROUGHPUT-BASELINE.md) | `—` | spec | — | — |
| [U-1 产物身份规范（内容寻址）](../spec/d6-agent-standard/U1-ARTIFACT-IDENTITY.md) | `—` | spec | — | — |
| [U-3 依赖边格式 Schema（统一基座 · 边）](../spec/d6-agent-standard/U3-EDGE-FORMAT.md) | `—` | spec | — | — |
| [U-4 失效规则 H-1~H-4（统一基座 · 失效传播）](../spec/d6-agent-standard/U4-INVALIDATION-RULES.md) | `—` | spec | — | — |
| [U-5 信任基座四问 V-1~V-4 + 晋升门 schema（统一基座 · 信任）](../spec/d6-agent-standard/U5-TRUST-BASIS.md) | `—` | spec | — | — |
| [未实测登记 · 按 `blocker` 分类的派工视图（`D6/D7` 规范面）](../spec/d6-agent-standard/UNTESTED-TRIAGE-PLAN.md) | `—` | spec | — | — |
| [quant-academic](../spec/d6-agent-standard/constraints/quant-academic.md) | `—` | spec | — | — |
| [agent 证据链 —— 实现级可行性落档（DESIGN）](../spec/d6-agent-standard/evidence-chain/DESIGN.md) | `—` | spec | — | — |
| [阶段 3-b 校准报告（20260918193642）](../spec/d6-agent-standard/evidence-chain/audits/AUDIT-JUDGE-20260918193642.md) | `—` | spec | — | — |
| [阶段 3-b 校准报告（20260919004146）](../spec/d6-agent-standard/evidence-chain/audits/AUDIT-JUDGE-20260919004146.md) | `—` | spec | — | — |
| [设计文档：strong-accept（主控站侧 golden 测试，防模型自证）](../spec/d6-agent-standard/strong-accept/DESIGN.md) | `d6-strong-accept-DESIGN` | design | verified | 2026-09-09 |
| [实施文档：strong-accept（主控站侧 golden 测试，防模型自证）](../spec/d6-agent-standard/strong-accept/IMPLEMENTATION.md) | `d6-strong-accept-IMPLEMENTATION` | implementation | verified | 2026-09-09 |
| [调研文档：strong-accept（主控站侧 golden 测试，防模型自证）](../spec/d6-agent-standard/strong-accept/RESEARCH.md) | `d6-strong-accept-RESEARCH` | design | draft | 2026-09-09 |
| [Unsloth Studio 调研落档：A站单机模型管理后端](../spec/d6-agent-standard/unsloth-a-station.md) | `—` | spec | — | — |
| [设计文档：ds4 (DwarfStar) 后端并入统一管理面](../spec/ds4-backend/DESIGN.md) | `ds4-backend-DESIGN` | design | draft | 2026-09-28 |
| [审查验收 Checklist：片间依赖边从「只记录」到「可执行」](../spec/graph-shard-dependency/CHECKLIST.md) | `graph-shard-dependency-CHECKLIST` | design | pending | 2026-10-31 |
| [设计：片间依赖边从「只记录」到「可执行」](../spec/graph-shard-dependency/DESIGN.md) | `graph-shard-dependency-DESIGN` | design | draft | 2026-10-31 |
| [实施文档：片间依赖边从「只记录」到「可执行」](../spec/graph-shard-dependency/IMPLEMENTATION.md) | `graph-shard-dependency-IMPLEMENTATION` | design | draft | 2026-10-31 |
| [B5i 手动模型加载层 DESIGN](../spec/infer-load/DESIGN.md) | `—` | spec | — | — |
| [推理实例参数台账 (params-ledger)](../spec/infer-load/params-ledger.md) | `—` | spec | — | — |
| [C 站 unsloth HIP 推理验证报告（2026-09-08）](../spec/infer-load/research/C站unsloth推理验证_20260908.md) | `—` | spec | — | — |
| [unsloth 单站后端现状 + 引擎精简对比测试（2026-09-08）](../spec/infer-load/research/unsloth引擎对比测试_20260908.md) | `—` | spec | — | — |
| [LM Studio 下载断点续传方案 (CLI+镜像) — DESIGN](../spec/lm-download/DESIGN.md) | `—` | spec | — | — |
| [B6 模型评测体系 DESIGN（方案落档，未实施）](../spec/model-eval/DESIGN.md) | `—` | spec | — | — |
| [推理框架选型调研（Strix Halo 集群，2026-09-08）](../spec/model-eval/FRAMEWORK-SURVEY-2026-09.md) | `—` | spec | — | — |
| [三节点（A/B/C）分布式开源模型备选调研 · 2026-09](../spec/model-eval/MODEL-SOURCING-2026-09.md) | `—` | spec | — | — |
| [model-eval 调研文档分类索引](../spec/model-eval/SOURCING-INDEX.md) | `—` | spec | — | — |
| [Domain Matrix — 面向本地模型的深度推理测试题集](../spec/model-eval/questions/domain_matrix.md) | `model-eval-questions-domain` | testbank | reviewed | 2026-08-31 |
| [B6 评测记分账本 (results-ledger)](../spec/model-eval/results-ledger.md) | `—` | spec | — | — |
| [验收 Checklist：单站多模型共存 P0（容量门）+ P1（alias 级卸载）](../spec/multi-model-per-station/CHECKLIST.md) | `multi-model-per-station-CHECKLIST` | design | in-review | 2026-10-28 |
| [设计：单站多模型共存（P0 容量门 + P1 alias 级卸载）](../spec/multi-model-per-station/DESIGN.md) | `multi-model-per-station-DESIGN` | design | draft | 2026-10-28 |
| [实施记录：单站多模型共存 P0（容量门）+ P1（alias 级卸载）](../spec/multi-model-per-station/IMPLEMENTATION.md) | `multi-model-per-station-IMPLEMENTATION` | design | in-review | 2026-10-28 |
| [算子层优化方案设计 (gfx1151 Vulkan / 双机 RPC + 单机双路径)](../spec/operator-optimization/DESIGN.md) | `—` | spec | — | — |
| [双机推理服务化与编排框架调研](../spec/operator-optimization/research/双机推理服务化与编排框架调研.md) | `—` | spec | — | — |
| [模型路径统一方案 A（2026-09-09）](../spec/operator-optimization/research/模型路径统一方案A_20260909.md) | `—` | spec | — | — |
| [审查验收 Checklist：原始评审 P1 四条修复](../spec/review-p1-remediation/CHECKLIST.md) | `review-p1-remediation-CHECKLIST` | design | accepted | 2026-10-27 |
| [设计文档：原始评审 P1 四条修复](../spec/review-p1-remediation/DESIGN.md) | `review-p1-remediation-DESIGN` | design | draft | 2026-10-27 |
| [实施文档：原始评审 P1 四条修复](../spec/review-p1-remediation/IMPLEMENTATION.md) | `review-p1-remediation-IMPLEMENTATION` | design | draft | 2026-10-27 |
| [验收 Checklist：原始评审 P2 大项（#5 站上 shell 严格模式 / #8A station-bin 分层）](../spec/review-p2-big/CHECKLIST.md) | `review-p2-big-CHECKLIST` | design | accepted | 2026-10-28 |
| [设计：原始评审 P2 大项（#5 站上 shell 严格模式 / #8A station-bin 分层）](../spec/review-p2-big/DESIGN.md) | `review-p2-big-DESIGN` | design | draft | 2026-10-28 |
| [实施文档：原始评审 P2 大项（#5 站上 shell 严格模式 / #8A station-bin 分层）](../spec/review-p2-big/IMPLEMENTATION.md) | `review-p2-big-IMPLEMENTATION` | design | draft | 2026-10-28 |
| [审查验收 Checklist：原始评审 P2 小批次（#6 / #9 / CI）](../spec/review-p2-small/CHECKLIST.md) | `review-p2-small-CHECKLIST` | design | accepted | 2026-10-28 |
| [设计文档：原始评审 P2 小批次（遗留单元 / 身份收敛 / CI）](../spec/review-p2-small/DESIGN.md) | `review-p2-small-DESIGN` | design | draft | 2026-10-27 |
| [实施文档：原始评审 P2 小批次（#6 / #9 / CI）](../spec/review-p2-small/IMPLEMENTATION.md) | `review-p2-small-IMPLEMENTATION` | design | draft | 2026-10-27 |
| [验收 Checklist：#8B 拆 `rpc_check.py` / #8C 拆 `agent-cli.ps1`](../spec/review-p2-split/CHECKLIST.md) | `review-p2-split-CHECKLIST` | design | accepted | 2026-10-28 |
| [设计：#8B 拆 `rpc_check.py` / #8C 拆 `agent-cli.ps1`](../spec/review-p2-split/DESIGN.md) | `review-p2-split-DESIGN` | design | verified | 2026-10-28 |
| [实施文档：#8B 拆 `rpc_check.py` / #8C 拆 `agent-cli.ps1`](../spec/review-p2-split/IMPLEMENTATION.md) | `review-p2-split-IMPLEMENTATION` | design | verified | 2026-10-28 |
| [三站系统 ROCm 统一装 7.2.4 — DESIGN](../spec/rocm-migration/DESIGN.md) | `—` | spec | — | — |
| [设计文档：RPC 双机链路分层优化](../spec/rpc-optimization/DESIGN.md) | `rpc-optimization-DESIGN` | design | draft | 2026-08-28 |
| [USB4 40Gbps 链路能力评估](../spec/rpc-optimization/USB4-40G链路能力评估.md) | `—` | spec | — | — |
| [RPC 优化执行度量日志 (metrics-log)](../spec/rpc-optimization/metrics-log.md) | `—` | spec | — | — |
| [v2 `.hgn` 下载笔记（2026-10-25）](../spec/rpc-optimization/o138-p3-20261024/download-notes.md) | `—` | spec | — | — |
| [O-138 · P3 可比吞吐 A/B（halogen · MTP 开/关 · 与 P1 同 prompt 形状）](../spec/rpc-optimization/o138-p3-20261024/results-ab.md) | `—` | spec | — | — |
| [O-138 · P3 前置验证：halogen + 现有 GGUF + 现有 mtp.hgn ⇒ MTP 是否自动生效](../spec/rpc-optimization/o138-p3-20261024/summary.md) | `—` | spec | — | — |
| [O-138 · P3 单变量对照：BYO GGUF vs 官方 v2 `.hgn` checkpoint（2026-10-25 · 站 C · E1）](../spec/rpc-optimization/o138-p3-20261024/v2-hgn/results-v2.md) | `—` | spec | — | — |
| [AMD395 平台分布式推理高性能互连方案调研](../spec/rpc-optimization/research/AMD395分布式推理高性能互连方案调研.md) | `—` | spec | — | — |
| [AMD 平台算子层优化与 USB4 直连分布式推理调研](../spec/rpc-optimization/research/AMD平台算子层优化与USB4分布式调研.md) | `—` | spec | — | — |
| [RPC 串行跨链问题的社区优化调研](../spec/rpc-optimization/research/RPC串行跨链社区优化调研.md) | `—` | spec | — | — |
| [llama.cpp RPC 协议瓶颈专项调研](../spec/rpc-optimization/research/RPC协议瓶颈调研.md) | `—` | spec | — | — |
| [C 站（seaviv）安装与配置落档](../spec/station-c/DEPLOYMENT.md) | `—` | spec | — | — |
| [上游跟踪台账：llama.cpp PR/Issue 状态 + 集群引擎基线（单一真源）](../spec/upstream-tracker/TRACKER.md) | `—` | spec | — | — |
| [ADR-<NNNN>: <决策标题>](../spec/vulkan-version-control/ADR_TEMPLATE.md) | `ADR-<NNNN>` | adr | proposed | YYYY-MM-DD |
| [审查验收 Checklist：Vulkan 后端版本控制](../spec/vulkan-version-control/CHECKLIST.md) | `vulkan-version-control-CHECKLIST` | design | pending | 2026-08-27 |
| [审查验收 Checklist：<feature_name>](../spec/vulkan-version-control/CHECKLIST_TEMPLATE.md) | `<feature-kebab>-CHECKLIST` | design | pending | YYYY-MM-DD |
| [设计文档：Vulkan 后端版本控制](../spec/vulkan-version-control/DESIGN.md) | `vulkan-version-control-DESIGN` | design | in-review | 2026-08-27 |
| [设计文档：<feature_name>](../spec/vulkan-version-control/DESIGN_TEMPLATE.md) | `<feature-kebab>-DESIGN` | design | draft | YYYY-MM-DD |
| [实施文档：Vulkan 后端版本控制](../spec/vulkan-version-control/IMPLEMENTATION.md) | `vulkan-version-control-IMPLEMENTATION` | design | in-review | 2026-08-27 |
| [实施文档：<feature_name>](../spec/vulkan-version-control/IMPLEMENTATION_TEMPLATE.md) | `<feature-kebab>-IMPLEMENTATION` | design | draft | YYYY-MM-DD |
| [调研文档：Vulkan 后端版本控制](../spec/vulkan-version-control/RESEARCH.md) | `vulkan-version-control-RESEARCH` | design | in-review | 2026-08-27 |
| [调研文档：<feature_name>](../spec/vulkan-version-control/RESEARCH_TEMPLATE.md) | `<feature-kebab>-RESEARCH` | design | draft | YYYY-MM-DD |
| [UPGRADE_SOP.md — llama.cpp Vulkan 后端两站原子升级 SOP](../spec/vulkan-version-control/UPGRADE_SOP.md) | `—` | spec | — | — |
