---
proj: dogfood
task: 为一个"生成物确定性 + 幂等性"检查设计判据与参考实现，写入 out/determinism-design.md；只写这一个新文件
model: ultra-c
cli: opencode
sensitivity: public
input-provenance: none
readonly: false
timeout_s: 1800
accept:
  - test -f out/determinism-design.md
  - grep -q '逐字节' out/determinism-design.md
  - grep -q '幂等' out/determinism-design.md
  - grep -q '假绿' out/determinism-design.md
evidence-manifest:
  version: 1
  subjects:
    - name: determinism-design
      path: determinism-design.md
      state: out/determinism-design.md
      digest: sha256
---
## 任务描述

**背景（抽象）**：一条流水线会产出若干**生成物**（文本文件 / 清单 / 报告）。
已知这类产物容易被"**非确定性**"污染：写入了**当前时间**、**递增序号 / 运行 id**、**绝对路径**、**字典序不稳定**的键顺序、
以及"**内容其实没变也照样重写**" ⇒ 于是同一输入跑两次得到**不同的字节**，diff 噪声盖住了真变化。

**要解决的**：设计一条**可机判**的判据，抓"**本该确定却不确定**"与"**内容未变却重写**"这两类。

### 你的产物：`out/determinism-design.md`

必须包含以下四节，**节名照抄**：

1. `## 判据定义` —— 用**一句话**分别定义两条子判据：
   **(a) 确定性** 与 **(b) 幂等性**。都要落到**可计算**的判据上（例如"同一输入跑两次，产物**逐字节一致**"）。
2. `## 双跑与比较` —— 说明：**对什么做快照** · **怎么做第二次运行**（是否需要在干净环境 / 是否需要固定随机种子）· **怎么做逐字节比较**（用哈希还是直接比对，是否要排序、是否要归一化换行符）。
3. `## 必须排除的噪声` —— 列出**至少 5** 类"天然非确定、必须排除或先归一化"的输入源（时间戳 / 运行 id / 绝对路径 / 临时目录名 / 并发调度顺序 …），每类一行并说明**为什么**。
4. `## 假绿` —— 这条判据在什么情况下会**报"通过"但其实没检**？至少 **2** 条；并说明**哪些生成物天然不可双跑**（若不能双跑，应如何**显式声明"不适用"**而不是静默跳过）。

### 硬性要求

1. **不许编造**：不确定的一律写"不确定"并说明缺什么，**不要猜**。
2. **不要引用、不要推测**任何具体项目 / 组织 / 主机 / 路径 / 人名。
3. 产物 **≤ 80 行**；代码块**不超过 10 行**。
4. **stdout 只输出一行**：`DOGFOOD_IMP3_OK`
5. 除 `out/determinism-design.md` 外**不产生任何文件**（临时文件也不留）。