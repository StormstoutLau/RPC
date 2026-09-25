# D7-P0 定案输入摘要（协议：六相状态机 + 三信封 + 三条红线）

> **这是什么**：`docs/2026-09-23_D7调研_立项·机制·统一基座.md` **§3.1** 的出站版（原文 → 本版：机制内容逐字保留）。
> **档位**：`public`（登记于 `inventory/sensitivity.yaml`）。
> **出站依据**：**2026-09-25 出站口径裁定**（Scott）—— D7 升级类材料可出站，
> **唯一需要脱密的是「私有 API 凭据 / IP / 用户信息」**；**本版不含**这三类（逐项已核）⇒ 作为「出站版」独立文件。
> ⚠ 本版**不承载原文档完整性**；缺失项就是缺失，**不许补**。

---

## 一、六相状态机（D7 的骨架）

```
P0 立契 → P1 领取 → P2 执行 → P3 回收 → P4a 机械验证 → P4b 语义复核 → P5 裁决登记
```

**状态机**：`drafted → dispatched → claimed → executing → collected → mech_verified →（可选）sem_verified → accepted | rejected`

## 二、三种信封（字段级）

| 信封 | 方向 | 字段 |
|---|---|---|
| **TaskContract** | 主控站 → 工作站（P0） | `task_id` / 任务描述 / **`accept[]`（判据 + criteria_hash）** / `golden{ref, checksum}` / `inputs{ref, digest}` / `evidence_budget{anchors, tool_calls}` / `constraints`（禁止项） / `timeout_s` / `sensitivity` / `readonly` |
| **RunReport** | 工作站 → 主控站（P3） | `run_id` / `attempt` / `artifact{digest, size}` / `inputs_digest` / `exit_code` / **`decisions[]`（八字段）** / **`evidence[]`（锚点）** / `usage` / **无 verdict 字段** |
| **Verdict** | 主控站（P5，仅登记） | `verdict`（exit code）/ `phase` / `l1_results[]` / `l2_marks[]`（可选）/ `redispatch?` / `recorded_at + seq` |

★ **`RunReport` 刻意不含 verdict 字段** —— 产出方**不得自评**。

## 三、三条设计红线（逐字）

1. **完成信号权只在主控站**；
2. **L1 机械门先于 L2 语义门，且 L2 无权改写**；
3. **判据与 golden 哈希在 P0 固化**（即"判据不能事后改"）。

> 原文注：这三条与 RULE-5「reviewer 只标记、永不改写」、与本机群"模型不自我盖章"（`accept` 由主控独立断言）
> **是同一条原则的三处独立表述** ⇒ 可信度因此很高。

## 四、不变量与角色禁项

- **六相不变量（I-1~I-6，本摘要含 3 条）**：**I-1 单写者**（事件流只有主控站可写，工作站只产出不落账）· **I-3 完成信号权在主控站** · **I-6 fail-closed**。
- **角色禁项**：主控站"**不执行任务本体**"；工作站"**不自评通过、不写 verdict、不重派、不合并**"。

## 五、该母版已给出的三条子命题结论（供定案时参考）

| 命题 | 结论 |
|---|---|
| **P-a**（每步由站上 agent CLI 执行） | **可行**，但必须接受两条：并行只能由**编排层**发起（agent 内自扇出已被实证否证）、gate 必须留在**编排层** |
| **P-b**（每 agent 嵌套微工作流） | **本仓判负**（收益"上下文隔离"在本仓不成立；代价"复利误差 p^N + 四重硬约束 + 递归退化"全数命中） |
| **P-c**（主控派发 + 审核） | **可行且优先级最高**（与本机群既有机制最同构） |

## 六、最高价值落点（原文结论）

**"异构验证的物理化"**（从"同机换模型"升级为"跨站跨家族"），**不是算力分摊**。
