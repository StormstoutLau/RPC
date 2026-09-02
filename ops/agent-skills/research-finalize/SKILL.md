---
name: "research-finalize"
description: "最终交付技能：整理所有研究制品，生成SUMMARY.md并记录最终状态"
---

## When to Run

- 研究完成，需要整理最终成果
- decision 阶段判定研究终止（成功或失败）
- 用户要求汇总和交付研究成果
- 需要生成项目总结报告

## Instructions

### 1. 盘点所有制品

检索整个研究过程中产生的所有制品：

**文献调研制品：**
- `literature_review_*`：文献综述
- `paper_list_*`：论文列表

**基线制品：**
- `baseline_result`：基线复现结果

**创意制品：**
- `research_idea`：研究创意
- `idea_evaluation`：创意评估

**实验制品：**
- `experiment_result`：实验结果

**分析制品：**
- `analysis_report`：分析报告
- `figure`：可视化图表

**论文制品：**
- `paper_draft`：论文草稿和终稿

**决策制品：**
- `decision_record`：所有决策记录

### 2. 评估研究完成度

按以下维度评估：

```markdown
## 研究完成度评估

| 维度 | 完成度 | 说明 |
|------|--------|------|
| 文献调研 | <百分比>% | <说明> |
| 基线复现 | <百分比>% | <说明> |
| 方法设计 | <百分比>% | <说明> |
| 实验验证 | <百分比>% | <说明> |
| 结果分析 | <百分比>% | <说明> |
| 论文撰写 | <百分比>% | <说明> |

### 总体完成度: <百分比>%
### 研究状态: 成功 / 部分成功 / 未完成
```

### 3. 生成 SUMMARY.md

按以下模板生成研究总结：

```markdown
# 研究总结：<研究主题>

## 基本信息
- 研究主题: <主题>
- 开始日期: <日期>
- 完成日期: <日期>
- 研究状态: <成功/部分成功/未完成>

## 研究问题
<核心研究问题的描述>

## 方法概述
<提出方法的简要描述，1-2段>

## 关键结果

### 主实验结果
| 方法 | 指标1 | 指标2 | 指标3 |
|------|-------|-------|-------|
| **Ours** | **<val>** | **<val>** | **<val>** |
| Baseline1 | <val> | <val> | <val> |
| Baseline2 | <val> | <val> | <val> |

### 关键发现
1. <发现1>
2. <发现2>
3. <发现3>

### 统计显著性
<与最强基线的对比：p-value, Cohen's d>

## 研究贡献
1. <贡献1>
2. <贡献2>

## 局限性
1. <局限性1>
2. <局限性2>

## 未来方向
1. <方向1>
2. <方向2>

## 制品清单

| 类别 | 制品 | 路径 | 状态 |
|------|------|------|------|
| 文献综述 | <名称> | <路径> | 完成 |
| 基线结果 | <名称> | <路径> | 完成 |
| 实验结果 | <名称> | <路径> | 完成 |
| 分析报告 | <名称> | <路径> | 完成 |
| 图表 | <名称> | <路径> | 完成 |
| 论文 | <名称> | <路径> | 完成/草稿 |

## 决策历史
| 阶段 | 决策 | 理由 | 结果 |
|------|------|------|------|
| scout | <决策> | <理由> | <结果> |
| baseline | <决策> | <理由> | <结果> |
| idea | <决策> | <理由> | <结果> |
| experiment | <决策> | <理由> | <结果> |
| analysis | <决策> | <理由> | <结果> |
| write | <决策> | <理由> | <结果> |
```

### 4. 整理制品目录

使用 bash_exec 整理最终交付物：

**步骤 A：创建交付目录**
```
bash_exec(command="mkdir -p deliverables/{paper,figures,code,data,docs}")
```

**步骤 B：复制关键制品**
```
bash_exec(command="cp paper/main.pdf deliverables/paper/")
bash_exec(command="cp analysis/figures/*.pdf deliverables/figures/")
bash_exec(command="cp -r experiments/ deliverables/code/")
```

**步骤 C：生成 README**
```
bash_exec(command="cat > deliverables/README.md << 'EOF'
# 研究交付物

## 目录结构
- paper/     : 论文PDF和LaTeX源码
- figures/   : 所有图表
- code/      : 实验代码
- data/      : 数据和结果
- docs/      : 文献综述和分析报告
EOF")
```

### 5. 记录最终决策

```
decision_record(
  stage="finalize",
  decision="<研究最终状态：成功/部分成功/未完成>",
  rationale="<基于完成度评估和结果质量的判断>",
  outcome="<研究总结：关键成果和贡献>",
  next_action="end"
)
```

### 6. 更新研究图谱（终态）

```
research_graph_update(
  node_type="quest",
  node_id="<quest_id>",
  status="completed",
  results="<研究最终状态和关键指标>",
  connections=[]
)
```

### 输出格式要求

- SUMMARY.md 必须完整且自包含
- 所有制品路径必须有效
- 决策历史必须覆盖所有阶段
- 研究状态判断必须诚实：
  - 成功：假设验证，结果显著
  - 部分成功：部分假设验证，或结果不显著但有价值发现
  - 未完成：关键阶段缺失或失败
- 交付物目录结构清晰，README 完整
