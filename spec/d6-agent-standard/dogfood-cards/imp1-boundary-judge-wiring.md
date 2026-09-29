---
proj: dogfood
task: 为一条"任务派发/复核"编排链设计三个"层级归属判据"的机读求值方案，写入 out/boundary-judge-design.md；只写这一个新文件
model: ultra-a
cli: opencode
sensitivity: public
input-provenance: none
readonly: false
timeout_s: 1800
accept:
  - test -f out/boundary-judge-design.md
  - test "$(wc -l < out/boundary-judge-design.md)" -ge 20
  - grep -q 'B-1' out/boundary-judge-design.md
  - grep -q 'B-2' out/boundary-judge-design.md
  - grep -q 'B-3' out/boundary-judge-design.md
  - grep -q '求值点' out/boundary-judge-design.md
  - grep -q '缺料与歧义' out/boundary-judge-design.md
evidence-manifest:
  version: 1
  subjects:
    - name: boundary-judge-design
      path: boundary-judge-design.md
      state: out/boundary-judge-design.md
      digest: sha256
---
## 任务描述

**背景（抽象）**：一条"任务派发"编排链把**任务卡**派给执行体产出，再由**复核方**给结论。
链条里有两层职责：

- **层 D6** = **单次派发内部**的质量门（判官抽检 / 验收签收）；
- **层 D7** = 需要**非产出方主体**给结论、且/或需要在**同一产物上多轮往返**（改完再审）的跨主体复核闭环。

**现状问题**：这两层的**归属目前靠人看过产物之后判断** ⇒ 新增场景无法在**派发前**自动落层。

**已有的三条判据（原样给出，不要改写其含义）**：

- **B-1**：是否需要一个"**非产出方**"的主体来给结论？**是 ⇒ 归 D7**
- **B-2**：是否在同一产物上需要**多轮往返**（改完再审）？**是 ⇒ 归 D7**
- **B-3**：是否只是"**这一次派发内部**"的质量门？**是 ⇒ 归 D6**

**求值规则（互斥且穷尽）**：`B-1=是` 或 `B-2=是` ⇒ 归 **D7**；`B-3=是` 且 `B-1=否` 且 `B-2=否` ⇒ 归 **D6**。

### 你的产物：`out/boundary-judge-design.md`

必须包含以下四节，**节名照抄**（用 `##` 二级标题）：

1. `## 判定输入` —— 为 B-1 / B-2 / B-3 **各一条**，给出三者：
   **字段名**（机读用，建议英文小写下划线）· **取值域**（如 `true/false`，或一个封闭枚举并列出成员）· **谁在何时提供**（受理方 / 派发方 / 产出方；受理阶段 / 派发前 / 产出后）。
2. `## 求值点` —— 说明这三个布尔在**派发链的哪一个节点**可以被求值，并说明为什么该节点满足"**在产出开始之前就能算出**"。若现有信息做不到，**明确指出需要新增什么前置信息**。
3. `## 灰色地带对照表` —— 一张**三列表**：`场景 | 归属(D6/D7) | B-1/B-2/B-3 取值`，覆盖这 **8** 个场景（照抄场景名）：
   判官抽检（断言 + 判官校准）｜受理阶段的协商回环（评审 ⇄ 修订）｜需求方验收签收｜跨站派发｜站间互审｜异构复审编排｜多轮续聊（审→改→再审）｜agent 派生边表 / 多 agent 树。
4. `## 缺料与歧义` —— 上文**没有给出**的东西（例如"同一产物"如何机读界定、"非产出方主体"用什么字段判定），**如实列出**。

### 硬性要求

1. **不许补写本卡未给出的机制细节**。凡本卡没写的，一律进 `## 缺料与歧义`，**不要自行虚构**。
2. **不要引用、不要推测**任何具体项目 / 组织 / 主机 / 路径 / 人名 —— 只按上面的抽象描述作答。
3. 产物 **≤ 80 行**；代码块**不超过 5 行**。
4. **stdout 只输出一行**：`DOGFOOD_IMP1_OK`
5. 除 `out/boundary-judge-design.md` 外**不产生任何文件**（临时文件也不留）。