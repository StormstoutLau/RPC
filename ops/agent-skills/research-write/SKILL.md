---
name: "research-write"
description: "论文写作技能：撰写研究论文，使用LaTeX编排，编译并记录写作决策"
---

## When to Run

- 需要撰写研究论文或实验报告
- 分析完成后需要组织论文
- 需要修改或完善已有论文草稿
- 用户要求生成论文的某个章节

## Instructions

### 1. 准备写作素材

从 artifact 和 memory 中收集所有素材：
- 读取 `literature_review_*`：相关工作内容
- 读取 `experiment_result`：实验数据和表格
- 读取 `analysis_report`：分析结论和统计结果
- 读取 `figure` 类型 artifact：图表文件路径
- 读取 `research_idea`：方法设计的原始描述

### 2. 创建论文结构

使用 bash_exec 创建论文目录和模板：

**步骤 A：创建论文目录**
```
bash_exec(command="mkdir -p paper/{figures,sections}")
```

**步骤 B：创建 LaTeX 主文件**
```
bash_exec(command="cat > paper/main.tex << 'EOF'
\documentclass[conference]{IEEEtran}
% 或 \documentclass{article} 根据目标会议/期刊
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{amsmath}
\usepackage{hyperref}
\usepackage{algorithm}
\usepackage{algorithmic}

\title{<论文标题>}
\author{<作者信息>}

\begin{document}
\maketitle
\input{sections/abstract}
\input{sections/introduction}
\input{sections/related_work}
\input{sections/method}
\input{sections/experiments}
\input{sections/conclusion}
\bibliographystyle{plain}
\bibliography{references}
\end{document}
EOF")
```

### 3. 逐节撰写论文

按以下顺序撰写各章节：

**Abstract（摘要）**
- 1段，150-250词
- 包含：问题、方法、关键结果、贡献
- 最后写，但放在论文最前

**Introduction（引言）**
- 2-3段
- 第1段：问题背景和重要性
- 第2段：现有方法的局限性
- 第3段：本文方法和贡献列表

**Related Work（相关工作）**
- 基于文献综述改写
- 按方法类别组织，而非按论文逐个列举
- 明确本文与已有工作的区别

**Method（方法）**
- 3-4段 + 算法伪代码
- 问题形式化定义
- 方法整体架构描述
- 各组件详细说明
- 理论分析（如有）

**Experiments（实验）**
- 实验设置：数据集、基线、评价指标、实现细节
- 主结果：表格 + 分析
- 消融实验：表格 + 分析
- 超参数分析（可选）
- 定性分析（可选）

**Conclusion（结论）**
- 1-2段
- 总结贡献和发现
- 讨论局限性
- 展望未来工作

### 4. 编译论文

使用 bash_exec 和 latex_compile 编译：

**步骤 A：复制图表到论文目录**
```
bash_exec(command="cp analysis/figures/*.pdf paper/figures/")
```

**步骤 B：编译 LaTeX**
```
bash_exec(command="cd paper && pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex")
```

或使用 latex_compile：
```
latex_compile(tex_file="paper/main.tex", output_dir="paper/")
```

**步骤 C：检查编译错误**
- 如果编译失败，检查引用和图表路径
- 修复后重新编译
- 确保无 warning 和 error

### 5. 记录论文草稿

每次完成一个章节或完整草稿后，使用 artifact_record 保存：

```
artifact_record(
  artifact_type="paper_draft",
  title="论文草稿 v<版本号>",
  content="""
# 论文草稿 v<版本号>

## 变更摘要
- <变更1>
- <变更2>

## 章节完成状态
| 章节 | 状态 | 备注 |
|------|------|------|
| Abstract | 完成/草稿/未开始 | |
| Introduction | 完成/草稿/未开始 | |
| Related Work | 完成/草稿/未开始 | |
| Method | 完成/草稿/未开始 | |
| Experiments | 完成/草稿/未开始 | |
| Conclusion | 完成/草稿/未开始 | |

## 文件位置
- LaTeX源码: paper/main.tex
- 编译PDF: paper/main.pdf
""",
  tags=["paper", "draft", "v<版本号>"]
)
```

### 6. 记录写作决策

```
decision_record(
  stage="write",
  decision="<论文结构和写作策略>",
  rationale="<为什么选择这种组织方式>",
  outcome="<当前草稿完成度和质量评估>",
  next_action="finalize / analysis"
)
```

### 输出格式要求

- 论文使用 LaTeX 格式编写
- 表格使用 booktabs 样式（\toprule, \midrule, \bottomrule）
- 算法使用 algorithm + algorithmic 宏包
- 数学符号全文一致
- 引用使用 \cite{} 而非手写
- 图表引用使用 \ref{} 和 \autoref{}
- 编译产物为 PDF，无编译错误和警告
