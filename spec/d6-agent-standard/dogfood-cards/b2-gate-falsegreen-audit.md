---
proj: dogfood
task: 审随卡附件的门禁脚本，逐项回答"该断言可能假绿吗 / 假绿条件是什么 / 是否已有反例用例"，写入 out/falsegreen.md；只写这一个新文件
model: ultra
cli: opencode
sensitivity: public
input-provenance: "ops/rpc_check.py"
attach-egress: ok
readonly: false
timeout_s: 1800
accept:
  - test -f out/falsegreen.md
  - test "$(grep -c '^- ' out/falsegreen.md)" -ge 10
  - grep -qE 'secrets|doclinks|inbox' out/falsegreen.md
evidence-manifest:
  version: 1
  subjects:
    - name: falsegreen
      path: falsegreen.md
      state: out/falsegreen.md
      digest: sha256
---
## 任务描述

**输入 = 随本卡提供的附件**（主控以 `--attach` 传入的一份 Python 门禁脚本）。
该脚本是"**改门禁的人自己写的门禁**"。你的任务是**给它做抗假绿审计**。

> **背景判据（本项目的核心教训）**：**"判据通过了，是因为它什么都没判"** —— 一条断言显示 `PASS`，
> 既可能因为它真的检了，也可能因为它**恒为真**、**范围为空**、**异常被吞**、**只测了自己**。
> 你的产出价值 = **找出后者**。

### 唯一产物：`out/falsegreen.md`（相对工作目录根）

- **每一项断言一行**，每行**以 `- ` 开头**，格式固定：

```
- <断言 id> ｜ 可能假绿: 是/否 ｜ 假绿条件: <一句话，具体到"什么情况下它会报 PASS 但实际没检> ｜ 已有反例: 有/无/未知
```

- 断言 id 用脚本里那一项自身的标识（如 `secrets` / `doclinks` / `inbox` / `ports` 之类）。
- **`可能假绿: 是` 的行，必须在下一行**（缩进 2 空格）给出**最小可构造的反例**：
  即"**怎么改一下就能让它报 PASS**"（**描述即可，不要真的去改任何文件**）。

产物末尾另起一节 `## 最危险的三条`：从你标"是"的项里挑三条，说明**为什么它比其它项更危险**。

### 硬性要求

1. **只读分析**：**不要修改附件的任何内容**，也不要在产物里粘贴大段源码。
2. **不许编造**：脚本里读不出来的（例如它依赖的**外部清单文件**内容）⇒ 标 `未知`，并在 `## 最危险的三条` 之后加一节 `## 无法判断项` 逐条说明缺什么。
3. 至少覆盖脚本中**全部顶层断言项**；若某项无法判断，也要**占一行**（标 `未知`）。
4. `out/falsegreen.md` 里 `^- ` 的行数 **≥ 10**。
5. **stdout 只输出一行**：`DOGFOOD_B2_OK`
6. 除 `out/falsegreen.md` 外**不产生任何文件**。
