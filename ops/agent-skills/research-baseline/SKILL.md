---
name: "research-baseline"
description: "基线复现技能：克隆和运行基线方法代码，记录复现结果并对比已有工作"
---

## When to Run

- 需要复现基线方法以建立性能参照
- 需要对比已有工作的实验结果
- 文献调研完成后，需要验证关键基线方法的可复现性
- 用户明确要求运行或对比某个基线方法

## Instructions

### 1. 确定基线方法列表

从文献调研结果（memory 中的 `literature_review_*` 和 `paper_list_*`）中提取：
- 核心基线方法名称
- 对应论文和代码仓库链接
- 每个基线的关键指标和报告性能

按优先级排序：
1. 有开源代码且被广泛引用的方法
2. 有开源代码但引用较少的方法
3. 无开源代码但可手动实现的方法

### 2. 准备基线环境

对每个基线方法，使用 bash_exec 执行环境准备：

**步骤 A：克隆代码仓库**
```
bash_exec(command="git clone <repo_url> baselines/<method_name>")
```

**步骤 B：安装依赖**
```
bash_exec(command="cd baselines/<method_name> && pip install -r requirements.txt")
```

**步骤 C：准备数据集**
```
bash_exec(command="<数据下载和预处理命令>")
```

如果基线方法无开源代码，则：
- 基于论文描述创建实现框架
- 在 `baselines/<method_name>/` 下编写代码
- 标注实现为 "reimplementation"，非原始代码

### 3. 运行基线实验

**步骤 A：运行原始基线**
```
bash_exec(command="cd baselines/<method_name> && python <run_script> --config <config_file>")
```

**步骤 B：记录运行结果**
- 记录所有输出日志
- 提取关键指标数值
- 与论文报告的性能对比

**步骤 C：处理失败情况**
如果基线运行失败：
1. 检查依赖版本兼容性
2. 检查数据路径和格式
3. 尝试使用论文中的超参数
4. 如果仍失败，记录失败原因并跳过该基线

### 4. 记录基线结果

对每个成功运行的基线，使用 artifact_record 保存：

```
artifact_record(
  artifact_type="baseline_result",
  title="<method_name> 基线复现结果",
  content="""
# <method_name> 基线复现结果

## 基本信息
- 论文: <论文标题>
- 代码来源: <repo_url>
- 复现日期: <日期>

## 实验配置
- 数据集: <数据集名称>
- 硬件环境: <GPU/CPU/内存>
- 超参数: <关键超参数列表>

## 结果对比
| 指标 | 论文报告 | 复现结果 | 差异 |
|------|---------|---------|------|
| <metric1> | <val1> | <val2> | <diff> |

## 运行日志摘要
<关键日志片段>
""",
  tags=["baseline", "<method_name>", "<数据集>"]
)
```

### 5. 生成基线对比表

汇总所有基线结果，生成对比表：

```markdown
# 基线对比表

| 方法 | 数据集 | 指标1 | 指标2 | 复现状态 | 备注 |
|------|--------|-------|-------|---------|------|
| <method1> | <dataset> | <val> | <val> | 成功/失败 | <说明> |
| <method2> | <dataset> | <val> | <val> | 成功/失败 | <说明> |

## 关键发现
- <发现1>
- <发现2>

## 复现风险
- <风险1>
- <风险2>
```

### 6. 记录基线决策

```
decision_record(
  stage="baseline",
  decision="<选择了哪些基线方法，跳过了哪些>",
  rationale="<选择理由：代码可用性、引用量、与研究方向的相关性>",
  outcome="<复现成功率，关键性能数据>",
  next_action="idea"
)
```

### 输出格式要求

- 每个基线结果独立记录为 artifact
- 对比表使用 Markdown 表格格式
- 所有数值保留与论文一致的精度
- 失败的基线必须记录失败原因，不可省略
- 标注结果为 "reproduction" 或 "reported"（论文原始值）
