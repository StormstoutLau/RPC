# 调研文档：strong-accept（主控站侧 golden 测试，防模型自证）

---
id: d6-strong-accept-RESEARCH
type: design
version: 1.0
status: draft
date: 2026-09-09
depends: [d6-agent-standard-CHECKLIST v1.0, d6-agent-standard-DESIGN v1.4, d6-agent-standard-OPEN-ISSUES v1.0]
upstream: null
---

> **Feature**: strong-accept（O-12——主控站侧独立 golden 测试，消除"模型自写测试自证通过"）
> **创建日期**: 2026-09-09
> **状态**: draft（草稿，Step 1-2 调研中）
> **Spec 步骤**: Step 1-2
> **任务来源**: O-12（OPEN-ISSUES 登记：accept 用模型自写测试属自证通过；强验收应附主控站侧 golden 判据）

---

## 1. 调研目标

**核心问题**（基于 O-12 定义与 D6 现状，实施前细化）:

1. D6 当前 accept 机制的**自证缺口**在哪——`accept` 命令在远端执行模型自写测试文件（`pytest test_<model>.py`），ACCEPT_OK 来自该文件退出码，而该文件由被验收的模型自己编写 → 模型可生成"使其实现通过"的宽松测试（reward hacking / sycophancy 变体）。如何机械封死？
2. 主控站侧 golden 测试的**形态**是什么——与现有 accept 机制如何共存（替代 vs 补充）？判据如何定义（`accept-golden` 字段？主控站独立 pytest？）
3. **成本/收益边界**——golden 测试需人工预写（建模任务规格的独立断言），对 D6 任务卡生态的增量成本 vs 防自证的收益如何平衡（哪些卡必须 golden，哪些可豁免）？

## 2. 调研方法

### 2.1 使用的工具

| 工具 | 用途 | 查询 |
|------|------|------|
| Read/Grep | D6 accept 机制源码审计（agent-cli.ps1 L688-758） | `accept` / `ACCEPT_OK` / `Get-FrontMatter` |
| Read | F:\Spec_Workflow 独立验证先例（independent-verify） | DESIGN/RESEARCH 形态映射 |
| WebSearch | 社区"agent 自写测试自证"实证 + 独立验证方案 | `self-written tests self-certification golden tests` |
| WebFetch | arXiv:2602.07900（agent 自写测试无价值实证） | arXiv 摘要 |

### 2.2 调研范围

- **时间范围**: 2024-2026（LLM agent 验证研究密集期）
- **领域**: AI 编码 agent 验证 / 测试自证 / golden test / builder-checker 分离
- **排除**: 非 agent 验证的一般软件测试方法论（如传统 TDD 全谱系）

## 3. 调研发现

### 3.1 D6 accept 机制现状：自证缺口已源码级确认

**【E1】** `agent-cli.ps1` L688-758：accept 判据 = 任务卡 front-matter 的 `accept:` 列表，**在远端工作区以 `cd $W && eval "$c"` 执行**（L740），`ACCEPT_OK` 由每条命令退出码判定（L741-743）。典型代码卡 accept 为 `./.venv/bin/python -m pytest paper_cli/tests/test_path_guard.py -q`——**该测试文件由被验收的模型在任务中自写**。

**【E1】** D6 验收史实（CHECKLIST §2.6 A14 行，根因编号 P1b 记录）：A14 取证发现模型自写 `validate_classification`（非卡规格 `is_well_formed_code`），"11 passed" 系自证通过——**自证缺口已被 D6 自身实测暴露**，O-12 正是该事故的正式化。

**【E1】** 当前 accept 无"测试来源"区分：主控站预置测试与模型自写测试**同通道执行**，无法区分。O-12 的缺口 = 缺乏**主控站权威的、独立于模型的**判据源。

### 3.2 社区实证：agent 自写测试确实"几乎无用"

#### arXiv:2602.07900（Rethinking the Value of Agent-Generated Tests，2026-02）

- **作者**: SMU / SJTU / ByteDance 团队
- **验证状态**: ✅ WebSearch 确认（arXiv 摘要 + 二手转述交叉）
- **关键结论**:
  - Claude 写自写测试 ~83% 任务，GPT-5.2 几乎从不（~0.6%），**两者 SWE-bench 解决率差仅 ~3 分**（74.4% vs 71.8%）→ 自写测试与任务成败**不相关**
  - 自写测试内容：**打印语句多于断言**（value-revealing prints > asserts）；关系/范围式断言仅 3-8%
  - 强制 gpt-5.2 写测试（~500 任务）→ **净变化为零**；强制 gemini 多写 → 净减 5 成功
  - 结论：**agent 自写测试 = "observational feedback channel"（调试通道），非 QA**——与 D6 自证问题完全一致
- **相关性**: 直接证实 O-12 必要性——依赖模型自写测试作 accept 是**无效验收**（无论测试是否通过）

#### 独立验证分离（builder-checker 模式，First Mate / 2026-08）

- **关键结论**: 分离 builder（实现）与 checker（设计测试 + 评审）两个模型角色，**防"实现者决定自身正确性"**；checker 先于实现接收验收标准，独立设计测试。554 测试发现 38 缺陷（含 1 个 P1）
- **相关性**: 独立验证的价值实证——但需要第二个模型/角色，D6 集群可用（多站多模型）

#### Three-tier verification（specification-first / property-based / mutation，2026-04 教程推荐方案）

- **来源**: theneuralbase.com 教程站（非标准制定机构），证据等级 E3
- **关键结论**: AI 代码验证三层 = ①**specification-first 测试**（先于实现写测试，AI 填充实现，防自证）②property-based（Hypothesis/fast-check 生成边界）③**mutation testing**（mutmut/stryker 注入 bug 验证测试套件真能抓住）——**AI 自写测试因太宽松而失效，mutation 可验证测试质量**
- **相关性**: golden 测试的正确形态 = specification-first（主控站先写权威测试，模型不可见）+ mutation 可选加固

### 3.3 F:\Spec_Workflow 独立验证先例（可复用模式）

**【E1】** independent-verify（2026-09-09 刚闭环）：verify-anchor 只读命令——**"锚点真实性 = 确定性程序可判（文件存在 + 章节匹配 + 行号上界）"**，把审查臂从"读自报流"升级为"查系统真实状态"。核心模式：**主控站权威判据 + 机械执行 + 语义层留给人/异基座**。

- 与本 feature 映射：verify-anchor 验"锚点位置真实"，strong-accept 验"实现行为真实"——同为**压缩自证/表演空间**，一为位置层一为行为层
- **可复用层级 = 设计模式，非代码**：verify-anchor 是静态引用核查（只读文件系统），strong-accept 是动态行为验证（pytest 执行）——具体机制差异显著，不可直接复制代码；可复用的是"权威判据前置 + 机械执行 + 模型不可见"的抽象模式

### 3.4 相关工作补充

**AfterVibe**（arXiv:2607.09900，Meta，2026-07）：提出 multi-tier verification pipeline（specification extraction → blind regeneration → multi-tier grading），与 strong-accept 的 specification-first 方向高度相关。本调研未深入，标注为同方向相关工作。

## 4. 综合分析

### 4.1 关键发现总结

1. **D6 自证缺口已源码确认且曾被实测暴露**（A14 事故）——accept 通道不区分测试来源 [置信度: ★★★★★，E1 源码+史实]
2. **社区实证 agent 自写测试近无效**（arXiv:2602.07900：写与不写解决率差 ~3 分；强制写净零/净负）——O-12 不是理论担忧，是实证必要 [置信度: ★★★★☆，E2 二手转述]
3. **正确形态 = specification-first golden 测试**（主控站先写权威测试，模型实现时不可见；三层验证第一层）——与 D6"任务卡=干净室规格"设计天然契合 [置信度: ★★★★☆]
4. **mutation testing 可验证 golden 测试自身质量**（防 golden 太宽松）——高级加固项 [置信度: ★★★☆☆]
5. **独立验证模式已在 F:\Spec_Workflow 落地**（verify-anchor）——形态可复用（只读命令 + 机械判据）[置信度: ★★★★★，E1 本地实证]

### 4.2 技术 landscape

| 方案 | 机制 | 防自证效果 | 成本 |
|---|---|---|---|
| **主控站 golden 测试**（本 O-12 方向）| 主控站预写权威断言，模型不可见 | ✅ 强（模型无法游戏未知测试）| 人工预写成本 |
| builder-checker 双模型 | 第二模型独立设计测试 | ✅ 强（异基座）| 2× 推理成本 |
| mutation testing | 注入 bug 验测试套件 | ⚠️ 验证测试质量（间接）| 额外算力 |
| 保持现状（模型自写）| — | ❌ 已实证无效 | 零 |

### 4.3 研究空白（本 feature 填补）

- D6 的 accept 机制**无测试来源信任分级**——golden（主控站权威）/ self（模型自写）/ none 三态未区分。本 feature 引入 `accept-golden` 概念：主控站侧独立判据，模型不可见、任务卡不可覆盖

## 5. 幻觉抑制审查（Step 2 Review）

### 5.1 文献验证

| 引用 | arXiv/DOI | 验证方式 | 状态 |
|------|-----------|---------|------|
| arXiv:2602.07900 | 2602.07900 | **WebFetch 原页确认**（v2 2026-04-09，Zhi Chen 等，SMU/SJTU，cs.SE）| ✅ 已验证 |
| builder-checker（First Mate）| — | WebSearch 确认 | ✅ |
| three-tier verification | — | WebSearch 确认 | ✅ |
| LLM self-correction 调查（TACL 2024）| — | WebSearch 间接确认 | ⚠️ 未直接读原页（设计不依赖）|

### 5.2 技术声明验证

| 声明 | 来源 | 验证状态 |
|------|------|---------|
| D6 accept 在远端 eval 模型自写测试 | agent-cli.ps1 L740 源码 | ✅ E1 |
| A14 曾发现自证通过 | CHECKLIST §7.2 P1b | ✅ E1 |
| verify-anchor 模式可复用 | F:\Spec_Workflow 实盘 | ✅ E1 |

### 5.3 待修正项

- [x] arXiv:2602.07900 编号 WebFetch 原页最终确认（**已完成**：v2，Zhi Chen 等，cs.SE）
- [x] builder-checker 的"554 测试 38 缺陷"为二手数据，设计引用时标注来源等级（**已完成**：§3.2 标注 E2）
- [x] three-tier verification 来源等级下调（**已完成**：§3.2 改为"教程推荐方案"，标注 E3）
- [x] verify-anchor 可复用性精确化（**已完成**：§3.3 明确"设计模式可复用，代码不可直接复用"）
- [x] 补入 AfterVibe 相关工作（**已完成**：§3.4 标注同方向工作）

> **RULE-4 自查声明**: 本调研为单 agent 完成，Review 属 `自查（单视角）`。依据 SPEC_PROCESS RULE-4，建议设计阶段由异基座会话复审。

## 6. 对设计的输入

### 6.1 可用的技术方案

1. **accept-golden 字段**（主控站侧预置）：任务卡新增 `accept-golden:` 列表，命令在主控站侧（或"主控站权威 + 远端执行"混合）执行，模型不可见、不可改
2. **golden 测试前置注入**：规格确认后、任务派发前，主控站把权威测试写入工作区（`.golden/` 目录，模型不可见或只读），accept 指向 `.golden/`
3. **mutation 加固（可选）**：golden 测试就绪后跑 mutmut 验其能抓变异

### 6.2 关键约束

- **模型不可见**：golden 测试在任务 prompt 中不得暴露（防模型针对优化）——与 D6 不变式 2（消毒出站前）同类约束
- **任务卡不可覆盖**：`accept-golden` 优先级高于 `accept`，模型/agent 无法降级
- **与现有 accept 共存**：golden 是补充（非替代）——调研卡（纯产物 grep）无 golden 需求可豁免

### 6.3 风险

- **人工预写成本**：每个代码卡需主控站先写权威测试——对任务卡生态是增量负担；缓解：仅"有可判定规格"的代码卡需要
- **golden 测试自身可能错**：主控站断言错误 → 误拒正确实现；缓解：mutation 验证 + 人工复核
- **模型不可见的执行环境差异**：golden 测试在远端跑可能依赖 .venv/依赖——需与工作区预置（O-13）联动

## 7. 参考文献

- [Rethinking the Value of Agent-Generated Tests for LLM-Based Software Engineering Agents](https://arxiv.org/abs/2602.07900)（arXiv:2602.07900，SMU/SJTU/ByteDance）
- [Should AI coding agents test their own code?](https://www.developer-tech.com/news/ai-coding-agents-test-own-code/)（First Mate builder-checker）
- [Verify with tests](https://theneuralbase.com/llm-for-coding/learn/intermediate/verify-with-tests/)（three-tier verification）
- F:\Spec_Workflow spec/independent-verify/（本地先例）
- F:\Spec_Workflow SPEC_PROCESS.md（spec 流程规范）

---

**Review 签字**: _________ 日期: _________
