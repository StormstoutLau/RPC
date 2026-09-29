---
proj: dogfood
task: 为一个"派生输出不留档"的缺口设计"派生只读视图 + --check"的最小形态，写入 out/derived-view-design.md；只写这一个新文件
model: ultra
cli: opencode
sensitivity: public
input-provenance: none
readonly: false
timeout_s: 1800
accept:
  - test -f out/derived-view-design.md
  - test "$(wc -l < out/derived-view-design.md)" -ge 20
  - grep -q -- '--check' out/derived-view-design.md
  - grep -q '假绿' out/derived-view-design.md
  - grep -q '缺料与歧义' out/derived-view-design.md
evidence-manifest:
  version: 1
  subjects:
    - name: derived-view-design
      path: derived-view-design.md
      state: out/derived-view-design.md
      digest: sha256
---
## 任务描述

**背景（抽象，来自实测的现状）**：一个仓库里有很多**派生输出** —— 把若干**真值文件**（清单 / 配置 / 状态机定义）
渲染成人可读的视图（网页 / 终端表格 / 汇总）。实测这些视图**全部是运行时渲染、不留档**。

⇒ **后果**：**没有可 diff 的对象** ⇒ 无法做"**视图过期即红**"。于是"真值改了、视图没跟上"这类漂移
**只能靠人偶然发现**。

**已知的现成样板（另一工程，一句话）**：把派生视图**落成一份只读文档**，并配一个 `--check` 模式 ——
**重新渲染、与落档逐字节比对，不一致即红**。

### 你的产物：`out/derived-view-design.md`

必须包含以下五节，**节名照抄**：

1. `## 视图形态` —— 落档的视图长什么样（格式 / 是否含"生成时间"这类非确定字段 / 如何标注"这是派生、勿手改"）。
2. `## 落档与刷新` —— **谁**在**何时**刷新它（人？钩子？构建步骤？），以及**刷新失败**时如何显式暴露（**不许静默**）。
3. `## --check 判据` —— 逐条写清 `--check` **判什么**、**退出码**如何编码（一致 / 不一致 / 渲染失败 三者必须**可区分**），
   以及**防恒真**的一条（例如"改了真值 ⇒ 必须红"）。
4. `## 假绿` —— 这条判据在什么情况下会**报"一致"但实际没检**？至少 **3** 条（例如"渲染器与 `--check` 共用同一个错误 ⇒ 一起错"）。
5. `## 缺料与歧义` —— 上面没给出的（例如视图是否要进版本控制、与"单一真值"的边界怎么划）⇒ **如实列出**。

### 硬性要求

1. **不许编造**：不确定的一律写"不确定"并说明缺什么，**不要猜**。
2. **不要引用、不要推测**任何具体项目 / 组织 / 主机 / 路径 / 人名。
3. 产物 **≤ 80 行**；代码块**不超过 10 行**。
4. **stdout 只输出一行**：`DOGFOOD_IMP5_OK`
5. 除 `out/derived-view-design.md` 外**不产生任何文件**（临时文件也不留）。