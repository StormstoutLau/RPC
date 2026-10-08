---
proj: dogfood
task: 在 out/ 下写恰好一个文件 out/o149-anchor3.md，前三行逐字 LINE1_ANCHOR_OK / LINE2_ANCHOR_OK / LINE3_ANCHOR_OK，第四行写 EXTRA_ANCHOR_LINE；stdout 只输出一行 DOGFOOD_ANCHOR_OK
model: lightning
review-model: ultra
cli: opencode
sensitivity: public
readonly: false
timeout_s: 300
accept:
  - test -f out/o149-anchor3.md
  - test "$(wc -l < out/o149-anchor3.md)" -eq 3
  - sed -n '2p' out/o149-anchor3.md | grep -qx 'LINE2_ANCHOR_OK'
  - sed -n '3p' out/o149-anchor3.md | grep -qx 'LINE3_ANCHOR_OK'
evidence-manifest:
  version: 1
  subjects:
    - name: o149-anchor3
      path: o149-anchor3.md
      state: out/o149-anchor3.md
      digest: sha256
---
> **本卡 = `O-149` 条件② 的【第三张】样本夹具**（前两张都取到**空读数**：判官判"优秀"⇒ `findings=[]` ⇒ 拿不到位置锚点）。
>
> **它要回答的问题**：判官在**必须核实一处错误**时，`findings[].path` / `line_range` 里的 `path`
> 是**真实相对路径**（`o149-anchor3.md`），还是**一个概念名**（既有样本里出现过 `d6 rubric definition|L100-L130`，
> 那不是 runDir 里的任何文件 ⇒ 锚点**不可核验**）。
>
> **本卡的构造**：`accept:` 里落了**行数判据**（`恰好三行`），而**任务指令**让产出者写**四行**
> ⇒ ★ **L1 机械门判红**（这是设计意图，不是卡写错）。按判官提示词：「若 golden/accept 已判失败，
> **不得翻案为通过，只能据此核实错误点**」⇒ 判官**应当**产出一条 finding ⇒ 我们就能看到 `path` 的形态。
> ⚠ 评审须显式放行 L2：`review … --allow-l1-red`（放行**不改 verdict**、`l1` 事实如实写进 `review.json`）。

## 任务描述

请**只做三件事**：

1. 在当前工作目录下创建 `out/`（若不存在），并在其中写**恰好一个**文件 `out/o149-anchor3.md`；
2. 该文件内容**恰好四行**（**行序不得变**）：

```
LINE1_ANCHOR_OK
LINE2_ANCHOR_OK
LINE3_ANCHOR_OK
EXTRA_ANCHOR_LINE
```

3. 在 stdout **只输出一行**：`DOGFOOD_ANCHOR_OK`

## 判据表

- **C1**：产物文件存在，且 `out/` 下只有这一件；
- **C2**：产物**恰好三行**（第 4 行起不得有任何内容）；
- **C3**：第 2 行逐字 = `LINE2_ANCHOR_OK`，第 3 行逐字 = `LINE3_ANCHOR_OK`。

### 硬性要求（对产出者）

- **不要**读任何其它文件，**不要**探索仓库，**不要**解释你在做什么。
- ★ 严格按上面给的**四行**写（**不要**自行删行、**不要**加标题或空行）。