---
proj: dogfood
task: 为一个"纯文本台账（Markdown 表格）列数守恒"检查设计判据与参考实现，写入 out/cell-safety-design.md；只写这一个新文件
model: ultra
cli: opencode
sensitivity: public
input-provenance: none
readonly: false
timeout_s: 1800
accept:
  - test -f out/cell-safety-design.md
  - grep -q '列数' out/cell-safety-design.md
  - grep -q 'def ' out/cell-safety-design.md
  - grep -q '假绿' out/cell-safety-design.md
evidence-manifest:
  version: 1
  subjects:
    - name: cell-safety-design
      path: cell-safety-design.md
      state: out/cell-safety-design.md
      digest: sha256
---
## 任务描述

**背景（真实事故，已抽象）**：一份长期维护的**纯文本台账**用 **Markdown 表格**记录条目，每行是 `| 字段1 | 字段2 | ... |`。
一次事故：某个字段的文本里**出现了一个竖线字符**，作者**以为转义了**（写成了 `\|`），但解析器**仍按竖线拆行**
⇒ **该行被拆成了比表头更多的格**，字段错位，而且**很长时间无人发现**（没有任何检查器读"列数"）。

**要解决的**：设计一条**可机判**的判据，用来**发现"某一行被拆错格"**这类事故，并给出参考实现。

### 你的产物：`out/cell-safety-design.md`

必须包含以下四节，**节名照抄**：

1. `## 判据定义` —— 用**一句话**说清判据判什么（必须落到一个**可计算**的量）。并说明：**表头行**、**分隔行**（`|---|---|`）、**数据行** 三者的列数关系。
2. `## 参考实现` —— 给出一段 **Python 纯函数**（建议名 `check_table_columns`），输入是"一篇 markdown 文本"，输出是"违规行清单"。**代码不超过 40 行**。必须写清：**如何正确识别"单元格里的竖线"**（区分"拆格的分隔符"与"单元格内容中的竖线"），以及**代码围栏（```）内的内容如何处理**。
3. `## 边界用例` —— **至少 4 条**，每条一行：`输入（一句话）| 期望判定（合格/违规）| 为什么`。至少覆盖：① 一行的单元格内容里**含合法竖线**；② 某数据行**确实少了一格**；③ 表格出现在**代码围栏**里面；④ 表头本身被改坏。
4. `## 假绿` —— 这条判据在什么情况下会**报"合格"但其实没检**？至少给出 **2** 条（例如"整篇没有表格 ⇒ 空集 ⇒ 恒真"）。

### 硬性要求

1. **不许编造**：若某条语义你不确定，**明确写"不确定"**并说明缺什么，**不要猜**。
2. **不要引用、不要推测**任何具体项目 / 组织 / 主机 / 路径 / 人名。
3. 产物 **≤ 100 行**。
4. **stdout 只输出一行**：`DOGFOOD_IMP2_OK`
5. 除 `out/cell-safety-design.md` 外**不产生任何文件**（临时文件也不留）。