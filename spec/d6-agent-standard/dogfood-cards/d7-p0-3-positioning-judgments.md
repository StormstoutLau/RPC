---
proj: dogfood
task: 读本卡正文内联的定位与判据摘要，把定位三要素与两条判据定稿成可机判形式写入 out/d7-p0-3-positioning-judgments.md；只写这一个文件
model: ultra
cli: opencode
sensitivity: public
input-provenance: "spec/d6-agent-standard/dogfood-cards/inputs/d7-p0-3-positioning-excerpt.md"
readonly: false
timeout_s: 900
accept:
  - test -f out/d7-p0-3-positioning-judgments.md
  - grep -q 独立执行主体 out/d7-p0-3-positioning-judgments.md
  - grep -q 能力最小化 out/d7-p0-3-positioning-judgments.md
  - grep -q 可审计收束 out/d7-p0-3-positioning-judgments.md
  - grep -q producer.family out/d7-p0-3-positioning-judgments.md
  - grep -q judge.input out/d7-p0-3-positioning-judgments.md
  - grep -q 未实测 out/d7-p0-3-positioning-judgments.md
  - test "$(wc -l < out/d7-p0-3-positioning-judgments.md)" -ge 30
evidence-manifest:
  version: 1
  subjects:
    - name: d7-p0-3-positioning-judgments
      path: d7-p0-3-positioning-judgments.md
      state: out/d7-p0-3-positioning-judgments.md
      digest: sha256
---
## 任务描述

**输入 = 本卡正文第二节的内容**（它与一份已登记为 `public` 的摘要文件同源；你**不需要**去读别的文件）。
请产出 **`out/d7-p0-3-positioning-judgments.md`**（**只写这一个文件**），分三节：

### 1. 定位定稿

按第二节的**定位三要素**，写出定稿：**要素名 + 它在"派发/复核"流程里可观察到的形态**
（即：一个外人**凭什么看出**这条要素成立/不成立）。

### 2. 两条判据的**可机判形式**

把 `judge.family ≠ producer.family` 与 `judge.input ≠ producer.input` 各写成**可机判形式**：
- **判据表达式**（用什么字段、什么比较）；
- **它需要什么真值表/登记才能判**（逐项列出）；
- **当前是否可判**（可判 / 前置缺失）—— 若前置缺失，明确写出**缺的是哪张表**。

### 3. `## 未实测登记`

逐条列出"本定稿里尚未被任何真实运行验证过的部分"。这一节**必须存在**；没有就写一个字：`无`。
⚠ 硬要求：**前置缺失的判据不许写成"已具备"**。

### 硬性要求

- ⚠ **不许补写正文里没有的内容**（缺什么写进第 3 节，**别用常识补齐**）。
- ⚠ 不要引入任何主机名、IP、用户名、凭据、盘符路径。
- 只写 `out/d7-p0-3-positioning-judgments.md` 一个文件；不要探索目录。

---

## 第二节：定位与判据摘要（本节即你的全部输入）

**定位（原文逐字）**：D7 该立项；定位 = "**独立执行主体 + 能力最小化 + 可审计收束**"，
且"**跨族异构**"应作为一条**可机判判据**。

**两条判据**：
- **J-1**：`judge.family ≠ producer.family` —— 复核方与产出方**模型家族不同**。
- **J-2**：`judge.input ≠ producer.input` —— 复核方**不得只吃产出方的输入**（否则只是复读同一前提）。

> ⚠ 二者的**可机判**取决于一件事：**"某个模型属于哪个家族"与"某站当前能加载哪些模型"必须可查**
> ⇒ 需一张 **"站 ↔ 已加载模型"真值表**（原文列为后续批次的前置项；**该表当时尚未登记**）。

**前置事实（原文已撤回原断言，此更正必须保留）**：原文曾断言"三站是同构硬件 + 同批模型族 ⇒ 三站互审在模型家族维度上仍同质"——
**该断言不成立，已撤回**。实测：三站均可走**出站**、且**可加载不同模型**；本地至少 **4 族**
（gpt-oss / nemotron / MiniMax-M2.7 / Qwen3.8-flash-next），出站再加族。
⇒ **但"跨站"本身不等于"跨族"**：它取决于**派发时选了哪个模型**。

**收益性质（原文结论）**：多站**不快**（跨站串行 RPC 损失 47%、同站叠并发恶化 ~2.8×、跨站并行物理上界 = 3）
⇒ **D7 的收益必须来自结构性（独立主体 / 可审计 / 可重算），不是吞吐。**

**最大缺口（原文结论，须标"未具备"）**：统一证据强度字典 · 机读产物身份与依赖边 · 失效传播
（后两项在九个项目里的实测结果 = **0/9**）。

> **本卡用途（D7-P0-3，2026-09-26）**：D7 阶段门 P0 的第 3 项——定位与判据定稿
>（原文退出判据：两条判据写成**可机判形式**；并登记"站↔已加载模型"真值表为后续前置）。
