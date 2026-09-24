---
proj: dogfood
task: 依据随卡附件的方言摘录，产出一份"同名不同义"对照表 + 统一字典候选轴，写入 out/dialect-map.md；只写这一个新文件
model: ultra
cli: opencode
sensitivity: public
input-provenance: "spec/d6-agent-standard/dogfood-cards/inputs/d7-dialect-excerpt.md"
attach-egress: ok
readonly: false
timeout_s: 1200
accept:
  - test -f out/dialect-map.md
  - test "$(grep -c '^|' out/dialect-map.md)" -ge 8
  - grep -q 'L1' out/dialect-map.md
  - grep -qE 'Textbook|Open_Data' out/dialect-map.md
---
> **本卡 = U-2 双卡的「分析提案」层**（`b1b`）：出网档（`public` + 人工脱敏摘要），产出含**统一字典候选轴**。
> 与之配对的「转录底稿」层 = [b1a-u2-dialect-map-transcribe.md](b1a-u2-dialect-map-transcribe.md)（`local-only` + 全文，**只转录原文**）。
> ⇒ U-2 目标「建映射、不迁移权威源」**两层都要**：底稿求真、分析求用。裁定见 [DEV-LOG-014](../../../docs/DEV-LOG-014-decision-refinement.md) D1。

## 任务描述

**输入 = 随本卡提供的附件**（主控以 `--attach` 传入的 `d7-dialect-excerpt.md`）。
**你没有别的资料，也不要去猜原文还有什么。** 本卡的产出是**分析**，不是抄写。

### 唯一产物：`out/dialect-map.md`（相对工作目录根）

必须包含以下**四节**（顺序不变，节标题逐字）：

#### 1. `## 对照表`

**一张表**，四列：`| 符号 | 出处 | 该处含义 | 与同符号其它含义的关系 |`

- **每一行 = 一个"符号 × 出处"组合**（同一符号在 5 个出处出现 ⇒ 就是 5 行）
- 最后一列只允许三种取值之一：`独占`（该符号只此一义）· `冲突`（与同符号其它处含义不同）· `同名不同义-族内`（同一出处里该符号还有第二套含义，如 L 族）

#### 2. `## 冲突清单`

逐条列出"**同名不同义**"的组合对，每条给出：**符号** · **两个冲突出处** · **一句话说明差异**（为什么它们不能互相替代）。

#### 3. `## 统一字典候选轴`

针对上面每个符号族，提出**一个**建议的统一轴（即："这个符号本来该用来表达什么"），并说明：
**为什么这个轴比现状好** · **哪些原有的含义无法塞进这个轴**。

#### 4. `## 无法判断项`

**凡附件里没有明说的，一律登记在此**（例如：某族在附件里只有"存在"没有含义 ⇒ 写在这里）。
格式：`- <项> ：缺什么信息才能判断`。
⚠ **这一节不得为空** —— 如果真的一无所缺，写 `- （无）` 并在下一行说明你如何确认附件已完整。

### 硬性要求

1. **不许编造**：附件没写的一律进第 4 节，**不要用常识补齐**（本卡的验收就是看你会不会"看着像就填"）。
2. **不要修改附件**；**不要**在产物里粘贴附件全文（产物是**你的分析**，不是拷贝）。
3. `out/dialect-map.md` 必须能被 `grep '^|'` 命中 ≥ 8 行（对照表的行数下限）。
4. **stdout 只输出一行**：`DOGFOOD_B1_OK`
5. 除 `out/dialect-map.md` 外**不产生任何文件**。
