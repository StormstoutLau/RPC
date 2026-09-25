---
proj: dogfood
task: 读本卡正文内联的协议摘要，把六相协议定案为契约文档草案写入 out/d7-p0-2-protocol-freeze.md；只写这一个文件
model: ultra
cli: opencode
sensitivity: public
input-provenance: "spec/d6-agent-standard/dogfood-cards/inputs/d7-p0-2-protocol-excerpt.md"
readonly: false
timeout_s: 900
accept:
  - test -f out/d7-p0-2-protocol-freeze.md
  - grep -q TaskContract out/d7-p0-2-protocol-freeze.md
  - grep -q RunReport out/d7-p0-2-protocol-freeze.md
  - grep -q Verdict out/d7-p0-2-protocol-freeze.md
  - grep -q 六相 out/d7-p0-2-protocol-freeze.md
  - grep -q 主控站 out/d7-p0-2-protocol-freeze.md
  - grep -q 未实测 out/d7-p0-2-protocol-freeze.md
  - test "$(wc -l < out/d7-p0-2-protocol-freeze.md)" -ge 30
evidence-manifest:
  version: 1
  subjects:
    - name: d7-p0-2-protocol-freeze
      path: d7-p0-2-protocol-freeze.md
      state: out/d7-p0-2-protocol-freeze.md
      digest: sha256
---
## 任务描述

**输入 = 本卡正文第二节的内容**（它与一份已登记为 `public` 的摘要文件同源；你**不需要**去读别的文件）。
请产出 **`out/d7-p0-2-protocol-freeze.md`**（**只写这一个文件**），分三节：

### 1. 六相协议契约（定案稿）

按第二节给出的**六相状态机**、**状态名序列**、**三种信封的字段**、**三条红线**、**不变量**，
写出一份**可直接当契约用的定案稿**：每一相写"谁在何时产出什么（哪个信封）"。

### 2. 采纳 / 裁剪的逐项决定

对**每一项**（六相 · 状态名序列 · 三个信封 · 三条红线 · 不变量 · 角色禁项）给出：
`项 | 决定（采纳/裁剪/待定） | 理由（引用正文哪一条）`。
★ 若某项**无法**从正文判定该采纳还是裁剪 ⇒ 写 `依据不足`（**不许猜**）。

### 3. `## 未实测登记`

逐条列出"本契约里**尚未被任何真实运行验证过**的部分"（例如某个不变量从未机判过、某个信封字段从未被写过）。
这一节**必须存在**；没有就写一个字：`无`。
⚠ 硬要求：**未经实测的东西不得写成"已具备"**。

### 硬性要求

- ⚠ **不许补写正文里没有的内容**（正文是摘要，缺什么就写进第 3 节，**别用常识补齐**）。
- ⚠ 不要引入任何主机名、IP、用户名、凭据、盘符路径；不要引用正文外的编号。
- 只写 `out/d7-p0-2-protocol-freeze.md` 一个文件；不要探索目录。

---

## 第二节：协议摘要（本节即你的全部输入）

**六相**：`P0 立契 → P1 领取 → P2 执行 → P3 回收 → P4a 机械验证 → P4b 语义复核 → P5 裁决登记`
**状态名序列**：`drafted → dispatched → claimed → executing → collected → mech_verified →（可选）sem_verified → accepted | rejected`

**三种信封（字段级）**：
- **TaskContract**（主控站 → 工作站，P0）：`task_id` / 任务描述 / **`accept[]`（判据 + criteria_hash）** / `golden{ref, checksum}` / `inputs{ref, digest}` / `evidence_budget{anchors, tool_calls}` / `constraints`（禁止项） / `timeout_s` / `sensitivity` / `readonly`
- **RunReport**（工作站 → 主控站，P3）：`run_id` / `attempt` / `artifact{digest, size}` / `inputs_digest` / `exit_code` / `decisions[]`（八字段） / `evidence[]`（锚点） / `usage` / **无 verdict 字段**
- **Verdict**（主控站，P5，**仅登记**）：`verdict`（exit code）/ `phase` / `l1_results[]` / `l2_marks[]`（可选） / `redispatch?` / `recorded_at + seq`

★ **`RunReport` 刻意不含 verdict 字段** —— 产出方**不得自评**。

**三条设计红线（逐字）**：
1. **完成信号权只在主控站**；
2. **L1 机械门先于 L2 语义门，且 L2 无权改写**；
3. **判据与 golden 哈希在 P0 固化**（即"判据不能事后改"）。

**不变量（摘要含 3 条）**：**I-1 单写者**（事件流只有主控站可写，工作站只产出不落账） · **I-3 完成信号权在主控站** · **I-6 fail-closed**。

**角色禁项**：主控站"**不执行任务本体**"；工作站"**不自评通过、不写 verdict、不重派、不合并**"。

> **本卡用途（D7-P0-2，2026-09-26）**：D7 阶段门 P0 的第 2 项——把协议**定案**为契约文档，
> 并**登记"未实测"**（原文退出判据：契约文档落盘 + "未实测"显式标注，**不得进"已具备"清单**）。
