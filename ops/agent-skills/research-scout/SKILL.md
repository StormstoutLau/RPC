---
name: "research-scout"
description: "文献调研技能：搜索、筛选和整理领域文献，生成结构化文献综述并保存调研结果"
---

## When to Run

- 用户要求调研某领域文献
- 需要搜索和综述相关论文
- 研究项目启动时需要了解领域现状
- 需要补充或更新已有文献综述

## Instructions

### 1. 明确调研范围

根据用户需求或 quest brief，确定：
- 研究主题和关键词列表
- 时间范围（默认近3年）
- 目标论文数量（默认10-20篇核心文献）

### 2. 搜索论文

按以下顺序执行搜索，确保覆盖面：

**步骤 A：arXiv 搜索**
```
arxiv_search(query="<关键词>", max_results=20)
```
- 使用多个关键词组合分别搜索
- 优先搜索标题和摘要中的关键词
- 记录每篇论文的：arxiv_id、标题、作者、发表日期、摘要

**步骤 B：Semantic Scholar 搜索**
```
semantic_scholar_search(query="<关键词>", limit=20, fields="title,authors,year,abstract,citationCount,url")
```
- 补充 arXiv 未覆盖的会议和期刊论文
- 关注高引用论文（citationCount > 50）
- 记录每篇论文的：paperId、标题、作者、年份、引用数、摘要

### 3. 筛选和分类

对搜索结果进行筛选：
- 去除重复论文
- 按相关性排序（高/中/低）
- 按方法类型分类（如：理论方法、实证研究、综述论文）
- 标注每篇论文的核心贡献和局限性

### 4. 生成文献综述

按以下结构撰写文献综述：

```markdown
# 文献综述：<研究主题>

## 概述
<领域现状总结，2-3段>

## 核心文献

### <论文1标题>
- **来源**: arXiv / 会议名 / 期刊名
- **年份**: YYYY
- **核心贡献**: <1-2句>
- **方法**: <简要描述>
- **局限性**: <1-2句>

### <论文2标题>
...

## 研究趋势
- 趋势1: <描述>
- 趋势2: <描述>

## 研究空白
- 空白1: <描述>
- 空白2: <描述>

## 推荐方向
基于文献分析，推荐的研究方向
```

### 5. 保存调研结果

**保存文献综述到 memory：**
```
memory_write(
  key="literature_review_<主题关键词>",
  content="<文献综述完整内容>",
  tags=["literature_review", "<主题关键词>"]
)
```

**保存论文列表到 memory：**
```
memory_write(
  key="paper_list_<主题关键词>",
  content="<结构化论文列表>",
  tags=["paper_list", "<主题关键词>"]
)
```

### 6. 记录调研决策

```
decision_record(
  stage="scout",
  decision="<调研范围和策略的描述>",
  rationale="<选择这些关键词和数据库的理由>",
  outcome="<调研结果摘要：共搜索X篇，筛选Y篇核心文献>",
  next_action="baseline"
)
```

### 输出格式要求

- 文献综述使用 Markdown 格式
- 每篇论文信息完整且结构化
- 明确标注信息来源（arXiv ID 或 Semantic Scholar Paper ID）
- 研究空白和推荐方向必须基于文献分析，不可凭空臆断
