---
proj: dogfood
task: 为一个"任务派发"框架设计"执行侧过程留痕"的最小机制，写入 out/executor-trace-design.md；只写这一个新文件
model: ultra-a
cli: opencode
sensitivity: public
input-provenance: none
readonly: false
timeout_s: 1800
accept:
  - test -f out/executor-trace-design.md
  - test "$(wc -l < out/executor-trace-design.md)" -ge 20
  - grep -q '采集点' out/executor-trace-design.md
  - grep -q '假绿' out/executor-trace-design.md
  - grep -q '缺料与歧义' out/executor-trace-design.md
evidence-manifest:
  version: 1
  subjects:
    - name: executor-trace-design
      path: executor-trace-design.md
      state: out/executor-trace-design.md
      digest: sha256
---
## 任务描述

**背景（抽象，全部来自实测的现状）**：一条"任务派发"框架把任务派给**远端执行体**（一个会调用工具的 agent），
执行结束后由主控侧**回收固定的证据件**。与"过程"最接近的两件证据是：

- 一件是**输出字节的时间序列** —— 形如 `t=<秒> bytes=<累计输出字节> bytes_s=<速率>`，**每 5 秒一行**；
  它只记录**吞吐曲线**，**不记录"做了什么"**；
- 一件是**工作区改动摘要** —— 实测**为空**（0 行）。

⇒ **核心问题**：判据**只能看产物，看不到过程**。站上执行体**改过哪些文件 / 跑过哪些命令**，
主控侧**查不到**。这是"幻觉抑制"最缺的一类证据 —— 因为**它怎么得出这个结论**，正在视野之外。

### 你的产物：`out/executor-trace-design.md`

必须包含以下五节，**节名照抄**：

1. `## 要抓什么` —— 列出**最小充分集**（**不超过 5 项**），每项一行：`抓什么 | 为什么必须有它`。
2. `## 在哪抓（采集点）` —— 对上面每一项，说明**采集点**在哪（执行体内部？远端外壳？主控侧？文件系统快照？），
   并说明**为什么选它**（可信度 / 成本 / 对执行体侵入性）。
3. `## 可核条件` —— **前提是"执行体不可信"**：它可能撒谎、可能漏报、可能篡改自己的记录。
   说明这套留痕**凭什么可核**（例如：由**执行体外**的一方产生 · 可由第三方复算 · 与产物哈希交叉锚定）。
   凡做不到"不信任仍可核"的项，**明确标出**。
4. `## 假绿` —— 这套留痕在什么情况下会**看起来有证据、实际没证据**？至少 **3** 条。
5. `## 缺料与歧义` —— 上面没给出的（例如"命令"如何归一化、二进制/交互式命令怎么处理）⇒ **如实列出**。

### 硬性要求

1. **不许编造**：不确定的一律写"不确定"并说明缺什么，**不要猜**。
2. **不要引用、不要推测**任何具体项目 / 组织 / 主机 / 路径 / 人名。
3. 产物 **≤ 80 行**；代码块**不超过 10 行**。
4. **stdout 只输出一行**：`DOGFOOD_IMP4_OK`
5. 除 `out/executor-trace-design.md` 外**不产生任何文件**（临时文件也不留）。