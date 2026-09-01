# B6 模型评测体系 DESIGN（方案落档，未实施）

> 状态：**设计冻结，待用户裁决启动**。本文档仅方案，不含任何实现。
> 前置依赖：B5i（infer-load 手动加载层）已上线 —— 评测体系的模型准入入口复用它。
> **v1.1 增补 (2026-08-31)**: 判分第四类 rubric + 深度推理题库 `questions/domain_matrix.md`（20 题, 已过审查 v1.1）接入。改动点: 非目标/决策 2/决策 4/目录结构/schema。

## 目标

对 A/B 两站库存模型及将来新下载模型建立**可复现、零幻觉、同口径**的质量测试体系，服务三个用户场景：长程学术推理、数理金融、复杂编程。副目标：为 #26610 升级 SOP 提供升级前后质量回归门。

## 非目标

- 不追求公开榜单绝对分数（新模型对公开基准全部污染，绝对分数无意义）
- 不做多并发压测（用户场景为单人长任务，batch=1 即真实负载）
- 不引入 lm-eval-harness 等重框架（依赖重；本项目判分四类：MCQ 匹配 / 代码沙箱执行 / 数值容差 / **rubric 量规**（v1.1 增），~200 行自研运行器足够）

## 决策记录

1. **基准选择**（公开定排序，自建定真值）：
   | 场景 | 基准 | 理由 |
   |---|---|---|
   | 长程学术推理 | GPQA-Diamond (198题) + RULER 16k/32k 子集 | MCQ 易判分；RULER 针对长上下文 needle/multi-hop |
   | 数理金融 | **自建 20-30 题闭式可验证题库**（期权定价闭式解 / 随机微积分推导 / 数值 sanity check） | 公开金融基准（FinQA 等）陈旧+污染；用户自建题库零污染且质量必然更高；判分=数值容差比对 |
   | 复杂编程 | HumanEval+/MBPP+ (evalplus) + LiveCodeBench | HumanEval+ 当冒烟门（新模型近饱和）；LiveCodeBench 时间窗防污染 |
   | Lean4（用户独有场景） | **miniF2F** (244题, Lean4) | 与 Research OS 形式化验证层同构，别家评测体系不覆盖 |
2. **自建金融题库是核心资产，不可委托**：用户亲自出题；本体系只提供题库格式（jsonl schema）与判分框架（数值容差），不代写题目。
   **v1.1 增**: 深度推理题库已建首版 [questions/domain_matrix.md](./questions/domain_matrix.md)（20 题 / 10 领域 / 概念-证明-计算-诊断-代码五型；范式 = ①标准概念解释 → ②应用到给定对象 → ③批判边界；前置自包含，无私有术语依赖；已过审查 v1.1——修正题干事实错误与数学结构缺陷各 1 处，审查注记见该文档尾部）。该题库来源于用户研究主题图谱（算子传导/Heston/最优执行/MIDAS/因子诊断/形式化验证等），**判分锚点与疑似幻觉标志随题携带**。
3. **运行器极简自研**（`scripts/b6_run_eval.py`，~200 行）：OpenAI 兼容 API 调用（走 :8080/:8081/:4000 均可），temperature=0 + 固定 seed，JSONL 逐题落盘。不用外部框架。
4. **判分四类**（v1.1: 三类 → 四类）：
   - MCQ：最终答案字段字符匹配（推理模型 reasoning_content 不参与判分，API 已天然分离）
   - 代码：Python 沙箱执行 + 单测（HumanEval+ 风格）
   - 数值：容差比对（金融自建题）
   - **rubric 量规（v1.1 增，覆盖证明/诊断类开卷题）**：
     - 量规 = 题库随题携带的「判分锚点 + 疑似幻觉标志」（domain_matrix.md 每题已内嵌）
     - 执行 = LLM-as-judge（本地集群强模型或外部强模型，**不得用被测模型自评**）；judge prompt 注入锚点为评分标准，命中锚点加分/命中幻觉标志判不合格
     - 分级 = 及格/良好/优秀三档（锚点已分层）
     - **人工抽检 ≥10%**（judge 本身会漂移；抽检不合格率 >20% 时该批 rubric 判分作废重判）
     - 复现性: judge 模型版本 + prompt 随结果落盘（同口径铁律延伸——rubric 判分结果须可追溯到 judge 配置）
5. **三级深度**：
   | 级别 | 题量 | 用途 | 触发 |
   |---|---|---|---|
   | 冒烟 | 5 题 | 新模型上线前必跑 | 每次 infer-load 新模型后 |
   （v1.1 增: domain_matrix 题库到三档的取题映射见其「组装指南」——冒烟档用 A3.1/B2.1/C2 数值与代码题, 深度档以 rubric 判分题为主） |
   | 准入 | 30-50 题 | 进生产前 | 模型首次纳入库存 |
   | 深度 | 100+ 题 | 横评 | 用户主动发起 |
6. **吞吐预算**（决定题库规模，tg 实测口径）：
   | 模型 | tg | 单题预算 (4096 tok) | 30 题准入套件 |
   |---|---|---|---|
   | m27-q4ks | 20.9 t/s | ~3.3 min | ~1.5 h |
   | DeepSeek-V4-Flash | 6.6 t/s | ~10 min | ~5 h → **只跑冒烟层** |
   | 单机 27-30B 级 | 未测 | 待定 | 预计 <1 h |
   推理模型（M2.7/DeepSeek R 系）`max_tokens` 须 ≥4096（先吐 reasoning 再作答）。
   **v1.1 实测修正 (2026-08-31 冒烟首测, qwen3.8-flash-next)**: reasoning_content **消耗 max_tokens 预算**——
   ① 代码题 4096 不足且 16384 仍思考失控 (18min 零产出) → 代码题必须**禁思考**: `"chat_template_kwargs": {"enable_thinking": false}` (实测 92s 出完整代码)；
   ② 概念/证明题: max_tokens ≥8192 + prompt 尾加"高效作答, 思考尽量精简" (实测 94s 正常)；
   ③ 数值短题 2048 够 (60s 内)。运行器按题型自动分型 (见 results-ledger 基础设施发现)。
7. **路径入账**：同一模型 llama.cpp 路径 vs vLLM 路径 = 账本不同行（量化不同：Q4_K_S vs AWQ）；m27 双路径各测一次。
8. **CTX 约束**：llama.cpp conf 默认 32768 —— 长程测试 >32k 需临时改 conf（KV cache 吃 GTT）或只走 vLLM 路径（196k）。
9. **复现性铁律**（引用 B5p 口径事故教训）：同模型同路径 before/after 必须同套件同参数；评测结果与性能基准一律分开记账，互不混用。
10. **与升级 SOP 耦合**：#26610 升级前后同套件重跑 → 性能（llama-bench）+ 质量（本体系）双锚点回归门。这是升级方案此前缺失的质量维度。
11. **互斥调度**：评测运行器串行驱动 `infer-load <alias>` → 跑套件 → `infer-unload` → 下一模型（GTT 互斥，一次一模型）。全库存 ~20 模型一轮分级跑（大模型只冒烟层）。

## 目录结构（规划）

```
spec/model-eval/DESIGN.md              # 本文档
scripts/b6_run_eval.py                 # 运行器 (~200 行)
data/eval/gpqa.jsonl                   # GPQA-Diamond
data/eval/minif2f.jsonl                # miniF2F (Lean4)
data/eval/humanevalplus.jsonl          # HumanEval+
data/eval/fin_custom.jsonl             # 金融自建题库 (用户出题)
spec/model-eval/questions/domain_matrix.md   # 深度推理题库 v1.1 (20题, 审查过)
data/eval/domain_matrix.jsonl          # domain_matrix 机器可读版 (待从 md 转换)
spec/model-eval/results-ledger.md      # 记分账本 (沿用 metrics-log.md 风格)
```

题库 jsonl schema（规划）：
```json
{"id": "fin-001", "suite": "fin_custom", "type": "numeric", "prompt": "...",
 "answer": {"value": 8.619, "tolerance": 0.01}, "max_tokens": 4096}
```

rubric 题型 schema（v1.1 增）：
```json
{"id": "dmx-a2", "suite": "domain_matrix", "type": "rubric", "prompt": "...",
 "rubric": {"anchors": ["L1 线性性被显式识别", "L2 控制收敛+密度导数 L¹"],
            "hallucination_flags": ["在 L1 上声称非线性所以难证"],
            "levels": {"pass": "...", "good": "...", "excellent": "..."}},
 "judge": {"model": "<judge 别名, 非被测模型>", "prompt_hash": "<落盘>"},
 "max_tokens": 4096}
```

## 执行阶段（启动后）

1. **阶段 1**：运行器 + GPQA-Diamond/miniF2f 两公开库，m27 全流程跑通（验证体系本身，~1.5h）
2. **阶段 2**：金融自建题库格式 + 判分框架（用户出题）
3. **阶段 3**：全库存轮扫（分级），账本首版

## 风险与边界

- 公开基准污染 → 分数仅作库存内相对排序
- glm-5.3-flash 无法参评（glm5next 架构未合入 llama.cpp v0.2.0）
- DeepSeek 吞吐限制 → 只进冒烟层（除非升级窗口后提速）
- Lean4 判分需 lean 工具链（miniF2f 全量证明验证重；阶段 1 可先只跑陈述句/level 1 子集或跳过）

## 冒烟验收（启动后）

`b6_run_eval.py --model minimax-m2 --suite gpqa --n 5` → 5 题 JSONL 落盘 + 判分报告 + 账本首行写入。
