---
proj: dogfood
task: 在 out/ 下写恰好一个文件 out/o149-anchor.md，其前三行逐字为 LINE1_ANCHOR_OK / LINE2_ANCHOR_OK / LINE3_ANCHOR_OK；stdout 只输出一行 DOGFOOD_ANCHOR_OK
model: lightning
review-model: ultra
cli: opencode
sensitivity: public
readonly: false
timeout_s: 300
accept:
  - test -f out/o149-anchor.md
  - test "$(wc -l < out/o149-anchor.md)" -eq 3
  - sed -n '2p' out/o149-anchor.md | grep -qx 'LINE2_ANCHOR_OK'
  - sed -n '3p' out/o149-anchor.md | grep -qx 'LINE3_ANCHOR_OK'
evidence-manifest:
  version: 1
  subjects:
    - name: o149-anchor
      path: o149-anchor.md
      state: out/o149-anchor.md
      digest: sha256
---
> **本卡 = `O-149` 条件②（`D7-PROTOCOL-CONCLUSION-CONTRACT` #3「判官侧相对根一致性」）的补样本夹具**。
> **它要回答的问题**：真样本里判官给出的 `anchor` 一直是**「名字 + 行号」且指向 rubric 概念**（`d6 rubric definition|L100-L130`），
> **没有一条落到【被评产物】上** ⇒ 「意见带可核验位置」这半**仍未成立**。
> ⇒ 本卡把 `accept:` 判据**故意写成【逐行】判据**（第 2/3 行必须逐字等于给定串）——
> 若判官真在**核判据**，它的 `anchor` 就**应当**落在**被评产物**（`o149-anchor.md`）的行区间上，
> 而不是落在它自己的 rubric 概念上。
>
> **本批组合（2026-10-08 实况修正后选定）**：产出者 `lightning`（出网 · B 站）/ 判官 `ultra`（出网 · B 站）。
> ★ **双腿均不需要站上本地引擎** —— 实况取证：**A 站无引擎**（`:8080` 无响应）· **C 站被 unsloth studio 占用**
> （跑 `gpt-oss-120b-MXFP4`，且其 key 与站上 `~/.config/rpc/unsloth.key` **不符** ⇒ `Not authenticated`）· B 站出网正常（`O-148`）。
> ★ **判官仍取 `ultra`**（与既有两个样本**同一判官**）⇒ 差异可归因于**本卡**，而不是判官换了。
>
> **判读（本卡的读数就长这样）**：
> - **正向（期望）**：`review.json.d7_verdict.l2_marks[].merged.findings[].anchor` 的**名字段 = 被评产物名**（`o149-anchor.md`）
>   且**带行号**（形如 `o149-anchor.md|L2-L2`）⇒ **类②「指向被评产物」**（与既有两个样本的"指 rubric 概念"**不同类**）。
> - **若仍指向 rubric 概念** ⇒ 判官侧相对根一致性**仍不成立**，本卡的结论 = **负读数**（如实登记，不改判据）。
> - ⚠ **射程（勿读过头）**：本卡只补**样本**；`state` 是否改判**不由本卡决定**（须按 `O-149` 甲的类覆盖档综判）。

## 任务描述

**这是一次判据锚点的取样任务**（目的是看判官把"意见位置"锚在哪，**不是**内容任务）。
请**只做三件事**：

1. 在当前工作目录下创建 `out/`（若不存在），并在其中写**恰好一个**文件 `out/o149-anchor.md`；
2. 该文件的**前三行**必须**逐字**是（**行序不得变、不得多行、不得少行**）：

```
LINE1_ANCHOR_OK
LINE2_ANCHOR_OK
LINE3_ANCHOR_OK
```

3. 在 stdout **只输出一行**：`DOGFOOD_ANCHOR_OK`

### 硬性要求

- **不要**读任何其它文件，**不要**探索仓库，**不要**解释你在做什么。
- ★ **不要**在 `out/` 里留任何临时文件（采集端要求 `out/o149-anchor.md` 这一件）。
- ★ 文件内容**只有那三行**（不要加标题、不要加空行、不要加解释）。