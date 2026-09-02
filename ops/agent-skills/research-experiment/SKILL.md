---
name: "research-experiment"
description: "实验执行技能：运行实验代码验证假设，记录实验结果并更新研究图谱"
---

## When to Run

- 需要运行实验验证研究假设
- 创意选定后需要实现和测试
- 需要进行消融实验或对比实验
- 用户要求运行特定实验配置

## Instructions

### 1. 制定实验计划

从 idea 阶段的 artifact 和 decision 中获取：
- 选定创意的技术方案
- 需要验证的假设列表
- 基线对比方法

制定实验计划，包含以下实验组：

**实验组 A：主实验**
- 实现选定创意的完整方法
- 在目标数据集上运行
- 与所有基线方法对比

**实验组 B：消融实验**
- 逐一移除关键组件
- 验证每个组件的贡献
- 至少覆盖3个核心组件

**实验组 C：超参数敏感性实验**
- 对关键超参数进行网格搜索或随机搜索
- 记录性能随超参数变化的趋势
- 确定最优超参数配置

**实验组 D：鲁棒性实验（可选）**
- 在不同数据分布上测试
- 添加噪声或扰动测试
- 跨数据集泛化测试

### 2. 实现实验代码

使用 bash_exec 执行代码编写和运行：

**步骤 A：创建实验目录结构**
```
bash_exec(command="mkdir -p experiments/<experiment_name>/{src,configs,results,logs}")
```

**步骤 B：编写实验代码**
- 在 `experiments/<experiment_name>/src/` 下编写核心代码
- 在 `experiments/<experiment_name>/configs/` 下创建配置文件
- 确保代码可复现：固定随机种子、记录依赖版本

**步骤 C：编写运行脚本**
- 创建 `run.sh` 统一入口
- 支持通过参数切换不同实验配置
- 自动保存输出日志

### 3. 执行实验

**步骤 A：运行主实验**
```
bash_exec(command="cd experiments/<experiment_name> && bash run.sh --config configs/main.yaml 2>&1 | tee logs/main.log")
```

**步骤 B：运行消融实验**
```
bash_exec(command="cd experiments/<experiment_name> && bash run.sh --config configs/ablation_<component>.yaml 2>&1 | tee logs/ablation_<component>.log")
```

**步骤 C：运行超参数搜索**
```
bash_exec(command="cd experiments/<experiment_name> && python src/hparam_search.py --config configs/search.yaml 2>&1 | tee logs/hparam_search.log")
```

**注意事项：**
- 每个实验运行前检查 GPU/内存资源是否充足
- 长时间运行的实验使用后台模式，定期检查进度
- 实验失败时保存当前 checkpoint，便于恢复

### 4. 记录实验结果

对每个完成的实验，使用 artifact_record 保存：

```
artifact_record(
  artifact_type="experiment_result",
  title="<experiment_name> 实验结果",
  content="""
# <experiment_name> 实验结果

## 实验配置
- 方法: <方法名称>
- 数据集: <数据集>
- 随机种子: <seed>
- 超参数: <关键超参数>
- 硬件: <GPU型号/内存>

## 主结果
| 方法 | 指标1 | 指标2 | 指标3 |
|------|-------|-------|-------|
| Ours | <val> | <val> | <val> |
| Baseline1 | <val> | <val> | <val> |
| Baseline2 | <val> | <val> | <val> |

## 消融结果
| 配置 | 指标1 | 指标2 | Δ |
|------|-------|-------|---|
| Full method | <val> | <val> | - |
| w/o component_A | <val> | <val> | <delta> |
| w/o component_B | <val> | <val> | <delta> |

## 运行日志摘要
<关键日志片段和训练曲线描述>
""",
  tags=["experiment", "<method_name>", "<dataset>"]
)
```

### 5. 更新研究图谱

使用 research_graph_update 记录实验节点：

```
research_graph_update(
  node_type="experiment",
  node_id="<experiment_name>",
  status="completed",
  results="<关键指标摘要>",
  connections=[
    {"from": "idea:<idea_name>", "relation": "validates"},
    {"from": "baseline:<baseline_name>", "relation": "compares_with"}
  ]
)
```

### 6. 处理实验失败

如果实验未达预期：
1. 分析失败原因（代码bug/超参数不当/假设错误）
2. 如果是代码bug：修复后重新运行
3. 如果是超参数问题：调整后重新运行
4. 如果是假设错误：记录失败结果，回退到 idea 阶段重新选择

```
decision_record(
  stage="experiment",
  decision="<实验是否成功，是否需要调整>",
  rationale="<基于实验结果的分析>",
  outcome="<关键指标和与基线的对比>",
  next_action="analysis / idea"
)
```

### 输出格式要求

- 实验结果使用 Markdown 表格，数值保留3位有效数字
- 消融实验必须标注 Δ（与完整方法的差异）
- 所有实验配置必须完整记录，确保可复现
- 失败实验同样记录，不可丢弃
- 日志摘要包含训练损失和关键指标的变化趋势
