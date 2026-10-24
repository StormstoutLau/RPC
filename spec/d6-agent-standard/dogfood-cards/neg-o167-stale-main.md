---
proj: dogfood
task: 受控负向夹具（O-167 主路）：不要在工作区创建/修改/删除任何文件；只在 stdout 输出一行 NEG167_NO_WRITE
model: ultra-b
cli: opencode
sensitivity: public
readonly: true
timeout_s: 120
accept:
  - test -f out/p0-tail-ok.txt
  - grep -qx 'P0_TAIL_OK' out/p0-tail-ok.txt
evidence-manifest:
  version: 1
  subjects:
    - name: p0-tail
      path: p0-tail-ok.txt
      state: out/p0-tail-ok.txt
      digest: sha256
---
> ⚠ **本卡是「受控负向」夹具**（用途 = 验证 `O-167` 的**主路**前置新鲜度判据：站上预置的**旧件**存在、
> 且内容恰好满足**两条 accept 命令**时，仍必须被 `STALE_PRODUCT` 挡住 ⇒ `ACCEPT_OK=0`），**不是内容任务**。
> 与 `neg-o46-cleanup`（受控**失败**夹具）同族：**判据要能拒，就必须有一个"该拒"的样本**。
> ⚠ **前置条件**：站上工作区 `out/p0-tail-ok.txt` 必须**先**被测试方手工预置为**旧件**
> （mtime 早于本轮 `.run-marker`）⇒ **本卡自身绝不能产出该文件**，否则负向不成立。
> ⚠ 为什么不让本卡"写一个错内容"：那样 accept 会因为**内容不符**变红 —— 那是**另一个判据**在拒，
> 不能证明"新鲜度判据"在拒。

## 任务描述

**这是一张受控负向夹具卡**。请**只做一件事**：

- 在 stdout **只输出一行**：`NEG167_NO_WRITE`

### 硬性要求（违反即本卡失效）

1. ★ **绝对不要**创建、修改、删除、移动**任何**文件（包括 `out/` 下的任何文件）。
2. **不要**读任何文件，**不要**探索仓库，**不要**解释你在做什么。
3. 若你发现自己**无法避免**写文件 ⇒ **只输出** `NEG167_WROTE`（便于测试方识别"负向构造已失效"）。
