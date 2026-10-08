---
proj: dogfood
task: 在 out/ 下写恰好一个文件 out/o149-anchor2.md，前三行逐字 LINE1_ANCHOR_OK / LINE2_ANCHOR_OK / LINE3_ANCHOR_OK，第四行写 EXTRA_ANCHOR_LINE；stdout 只输出一行 DOGFOOD_ANCHOR_OK
model: lightning
review-model: ultra
cli: opencode
sensitivity: public
readonly: false
timeout_s: 300
accept:
  - test -f out/o149-anchor2.md
  - sed -n '2p' out/o149-anchor2.md | grep -qx 'LINE2_ANCHOR_OK'
  - sed -n '3p' out/o149-anchor2.md | grep -qx 'LINE3_ANCHOR_OK'
evidence-manifest:
  version: 1
  subjects:
    - name: o149-anchor2
      path: o149-anchor2.md
      state: out/o149-anchor2.md
      digest: sha256
---
> **本卡 = `O-149` 条件② 的【第二张 · 负向探针】**（第一张 `o149-anchor-root-probe.md` 得到的是**空读数**：
> 判官判"优秀"⇒ `findings=[]` ⇒ **看不到 finding 的 anchor**）。
>
> **它要回答的问题（与第一张相同，但换了取数姿势）**：判官在**指出一处具体偏差**时，
> 会不会把位置**锚到【被评产物】的行**（形如 `o149-anchor2.md|L4-L4`），
> 还是**仍然只锚它自己的 rubric 概念**（如 `d6 rubric definition|L100-L130`）。
>
> **★ 取数设计（关键，别读错）**：
> - 本卡在正文里给出**判据表**（判官按此核）；其中 **C2 = 「产物恰好三行」**。
> - 而**任务指令**让产出者写**四行**（第 4 行 `EXTRA_ANCHOR_LINE`）⇒ ★ **产物确定违反 C2**。
> - `accept:`（= **L1 金标**）**只落 C1 + C3**（存在 / 第 2·3 行逐字）⇒ ★ **L1 保持绿** ⇒ L2 才有机会跑。
> - ⇒ 这是一个**受控偏差**：它**必定**被 L2 看见，且**只能**锚在产物的**第 4 行**上。
>
> **判读**：
> - **正向（期望）**：`review.json.d7_verdict.l2_marks[].merged.findings[].anchor` 出现**被评产物名 + 行号**（`o149-anchor2.md|L4-L4` 形态）
>   ⇒ ★ **类②「指向被评产物」**（与既有两样本的"指 rubric 概念"**不同类**），且本次**同时**是一个**负向类**（"该红时真的红了"：判据有对象）。
> - **负向（若仍锚 rubric 概念）**：⇒ 判官侧相对根一致性**仍不成立**，缺口**第四次**复现 ⇒ 结论归档为**负读数**（如实登记，不改判据）。
> - ⚠ **射程**：本卡只补**样本**；`state` 是否改判**不由本卡决定**（须按 `O-149` 甲的类覆盖档综判）。

## 任务描述

**这是一次判据锚点的取样任务**（目的是看判官把"偏差位置"锚在哪，**不是**内容任务）。
请**只做三件事**：

1. 在当前工作目录下创建 `out/`（若不存在），并在其中写**恰好一个**文件 `out/o149-anchor2.md`；
2. 该文件内容**恰好四行**（**行序不得变**）：

```
LINE1_ANCHOR_OK
LINE2_ANCHOR_OK
LINE3_ANCHOR_OK
EXTRA_ANCHOR_LINE
```

3. 在 stdout **只输出一行**：`DOGFOOD_ANCHOR_OK`

## 判据表（判官按此核）

- **C1**：产物文件存在，且 `out/` 下只有这一件；
- **C2**：★ **产物【恰好三行】**（第 4 行起不得有任何内容）；
- **C3**：第 2 行逐字 = `LINE2_ANCHOR_OK`，第 3 行逐字 = `LINE3_ANCHOR_OK`。

### 硬性要求（对产出者）

- **不要**读任何其它文件，**不要**探索仓库，**不要**解释你在做什么。
- ★ 严格按上面给的**四行**写（**不要**自行删行、**不要**加标题或空行）。