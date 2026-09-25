---
proj: dogfood
task: 审随卡附件门禁脚本中【最近新增或改动过】的五项断言，逐项回答"可能假绿吗 / 假绿条件是什么 / 最小反例"，写入 out/falsegreen-new.md；只写这一个新文件
model: ultra
cli: opencode
sensitivity: public
input-provenance: "ops/rpc_check.py"
attach-egress: ok
readonly: false
timeout_s: 1800
accept:
  - test -f out/falsegreen-new.md
  - test "$(grep -c '^- ' out/falsegreen-new.md)" -ge 5
  - grep -q 'py-tests' out/falsegreen-new.md
  - grep -q 'input-provenance' out/falsegreen-new.md
  - grep -q 'ps1-runstamp' out/falsegreen-new.md
evidence-manifest:
  version: 1
  subjects:
    - name: falsegreen-new
      path: falsegreen-new.md
      state: out/falsegreen-new.md
      digest: sha256
---
## 任务描述

**输入 = 随本卡提供的附件**（主控以 `--attach` 传入的一份 Python 门禁脚本）。
该脚本是"**改门禁的人自己写的门禁**"。你的任务是给它做**抗假绿审计**。

> **背景判据（本项目的核心教训）**：**"判据通过了，是因为它什么都没判"** —— 一条断言显示 `PASS`，
> 既可能因为它真的检了，也可能因为它**恒为真**、**范围为空**、**异常被吞**、**只测了自己**。
> 你的产出价值 = **找出后者**。

> ⚠ **本卡是一次复审的"第二批"，范围被刻意收窄**：同一份脚本此前已有一轮**全量**抗假绿审计
> （那一轮的结论已归档）。**那轮之后，脚本里又新增/改动了几项断言。本卡只审这批新的。**
> **审旧的那批属于重复劳动，明确不要做**；把篇幅留给下面这五项。

### 只审这五项（**每项必须占一行，不多不少**）

下表只是**路标**——每项到底判什么，**以脚本内文本为准，不要轻信本表**：

| 断言 id | 它大致在判什么 |
|---|---|
| `py-tests` | 一个 Python 测试套件的执行结果 |
| `input-provenance` | 卡面"输入来源"义务的合规性 |
| `ps1-runstamp` | 一个"跨进程抢占"夹具的行为 |
| `stations` 的 **orphan 段** | 站上长龄孤儿进程 |
| `evidence` 的**第三态** | 一类"按设计就该缺件"的 run |

### 唯一产物：`out/falsegreen-new.md`（相对工作目录根）

- **每一项断言一行**，每行**以 `- ` 开头**，格式固定：

```
- <断言 id> ｜ 可能假绿: 是/否 ｜ 假绿条件: <一句话，具体到"什么情况下它会报 PASS 但实际没检"> ｜ 已有反例: 有/无/未知
```

- **`可能假绿: 是` 的行，必须在下一行**（缩进 2 空格）给出**最小可构造的反例**：
  即"**怎么改一下就能让它报 PASS**"（**描述即可，不要真的去改任何文件**）。

产物末尾另起一节 `## 最危险的三条`：从你标"是"的项里挑三条，说明**为什么它比其它项更危险**。

### 硬性要求

1. **只读分析**：**不要修改附件的任何内容**，也不要在产物里粘贴大段源码（引用一两个标识符即可）。
2. **不许编造**：脚本里读不出来的（例如它依赖的**外部清单/真值表文件**的内容）⇒ 标 `未知`，
   并在 `## 最危险的三条` 之后加一节 `## 无法判断项` 逐条说明**缺什么**。
   ⇒ 例如某判据的判定依赖一份**没有随附件提供**的清单：**不要猜那份清单长什么样**，标 `未知`。
3. 上表**五项每项必须占一行**（判不了也照样占一行、标 `未知`）。
4. `out/falsegreen-new.md` 里 `^- ` 的行数 **≥ 5**。
5. **stdout 只输出一行**：`DOGFOOD_B3_OK`
6. 除 `out/falsegreen-new.md` 外**不产生任何文件**（临时文件也不留）。
