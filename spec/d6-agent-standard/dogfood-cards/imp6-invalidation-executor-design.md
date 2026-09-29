---
proj: dogfood
task: 为一个"失效传播决策已能算、但执行侧未实现"的缺口设计最小执行形态，写入 out/invalidation-executor-design.md；只写这一个新文件
model: ultra-c
cli: opencode
sensitivity: public
input-provenance: none
readonly: false
timeout_s: 1800
accept:
  - test -f out/invalidation-executor-design.md
  - test "$(wc -l < out/invalidation-executor-design.md)" -ge 20
  - grep -q '前置校验' out/invalidation-executor-design.md
  - grep -q '假绿' out/invalidation-executor-design.md
  - grep -q '缺料与歧义' out/invalidation-executor-design.md
evidence-manifest:
  version: 1
  subjects:
    - name: invalidation-executor-design
      path: invalidation-executor-design.md
      state: out/invalidation-executor-design.md
      digest: sha256
---
## 任务描述

**背景（抽象，来自实测的现状）**：一个仓库能计算"**失效传播**"：
某个输入变了（`changed`）⇒ 找出受影响的派生产物（`affected`）⇒ 给出一个**处置决策**（形如
`action` / `class` / `reason` 三件）。该命令实测**只产出决策，不执行任何重算**（源码里明写"执行侧仍未实现"）。

**另有一条已知语义约束（实测得出，必须尊重）**：`affected` 传**空列表**与传 **"判不了"** 是**两件不同的事** ——
- **空列表** = "**已判定为空**"（真的没有下游）；
- **"判不了"** = 触发"**保守：强制全量降级**"。
⇒ 把前者错写成后者，会**白白付一次全量**。

### 你的产物：`out/invalidation-executor-design.md`

必须包含以下五节，**节名照抄**：

1. `## 执行形态` —— 从"已有决策"到"真的重算"，中间的最小步骤序列（**不超过 6 步**），每步一行：`步骤 | 输入 | 输出 | 失败时怎么办`。
2. `## 前置校验` —— 真正动手重算**之前**必须校验什么（例如：决策是否与当前真值同源 · 输入是否已冻结 · 是否缺 `affected`）。
   每条写清**不通过就不许执行**的理由。
3. `## 失败与降级` —— 区分三种结果并说明**为什么必须显式区分、不许静默**：
   `跳过（合法）` / `失败（算失败）` / `不适用（有理由）`。
4. `## 假绿` —— 这套执行在什么情况下会**报"成功"但实际没做**？至少 **3** 条
   （例如"部分覆盖成功 ⇒ 就当整体成功"）。并给出**防它**的一条硬约束。
5. `## 缺料与歧义` —— 上面没给出的（例如重算的**原子性**怎么做、并发怎么处理）⇒ **如实列出**。

### 硬性要求

1. **不许编造**：不确定的一律写"不确定"并说明缺什么，**不要猜**。
2. **不要引用、不要推测**任何具体项目 / 组织 / 主机 / 路径 / 人名。
3. 产物 **≤ 80 行**；代码块**不超过 10 行**。
4. **stdout 只输出一行**：`DOGFOOD_IMP6_OK`
5. 除 `out/invalidation-executor-design.md` 外**不产生任何文件**（临时文件也不留）。