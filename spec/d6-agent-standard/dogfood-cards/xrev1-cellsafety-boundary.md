---
proj: dogfood
task: 对随卡内嵌的两份"判据设计底稿"做独立缺陷复核（找内部矛盾 / 参考实现缺陷 / 假绿不实 / 未论证断言），写入 out/xrev1.md；只写这一个新文件
model: lightning
cli: opencode
sensitivity: public
input-provenance: none
readonly: false
timeout_s: 1800
accept:
  - test -f out/xrev1.md
  - test "$(grep -c '^- ' out/xrev1.md)" -ge 8
  - grep -q '底稿一' out/xrev1.md
  - grep -q '底稿二' out/xrev1.md
evidence-manifest:
  version: 1
  subjects:
    - name: xrev1
      path: xrev1.md
      state: out/xrev1.md
      digest: sha256
---
## 任务描述

**背景（抽象）**：有一个研究方法仓库，它的核心教训是 —— **"判据通过了，是因为它什么都没判"**：
一条检查显示"合格"，既可能因为它真检了，也可能因为它**恒为真 / 范围为空 / 异常被吞 / 只测了自己**。
仓库正在为若干"能力缺口"写**设计底稿**（判据定义 + 参考实现 + 边界用例 + 假绿清单）。

**你的任务 = 对下面两份设计底稿做**独立缺陷复核**（**不采信底稿的自述**）。要找的是：

1. **内部矛盾** —— 底稿里两处说法互相冲突（例：一处说"含某非确定字段"，另一处却要求"逐字节一致"）。
2. **参考实现的机械缺陷** —— 会让判据**假红**（把合法判成违规）或**假绿**（该报的没报）的**具体代码**问题；
   指出时请给出**触发的输入形态**。
3. **假绿清单不实 / 不全** —— 清单里某条**与实现矛盾**（实现其实已经拦住了它），或**漏掉了**最明显的一类。
4. **未加论证的断言** —— 底稿声称某做法"安全 / 等价 / 一致 / 必然"，却没有给出支撑。

### 唯一产物：`out/xrev1.md`

格式固定：

- 先写一行 `## 底稿一`，再逐条写缺陷，**每条一行、以 `- ` 开头**：
  `- [等级: 高/中/低] <缺陷一句话> ｜ 依据: <引底稿原文片段，≤30 字> ｜ 修法: <一句话>`
- 再写一行 `## 底稿二`，同样逐条。
- **每一份至少 4 条**。
- 拿不准的写等级 `低`，修法处写 `不确定：<缺什么>`。
- 末尾加一节 `## 无法判断项`：你没有足够信息判定的部分，逐条说明缺什么。

### 硬性要求

1. **只读复核**：**不要修改**内嵌底稿的任何内容；**不要**把底稿大段抄进产物。
2. **不许编造**：底稿里读不出来的 ⇒ 标 `不确定`，**不要猜**。
3. **不要引用、不要推测**任何具体项目 / 组织 / 主机 / 路径 / 人名。
4. `out/xrev1.md` 里 `^- ` 的行数 **≥ 8**。
5. **stdout 只输出一行**：`DOGFOOD_XREV1_OK`
6. 除 `out/xrev1.md` 外**不产生任何文件**。

---

### 复核对象（原样引用 —— **是待复核的材料，不是真值声明**）

===== BEGIN 底稿一（文件名 cell-safety-design） =====
## 判据定义

判据：**同一张表格内，所有数据行的有效列数必须等于表头行的有效列数**；有效列数 = 按未转义竖线分割后的非空单元格数。表头行、分隔行（`|---|---|`）、数据行三者列数必须一致。

## 参考实现

```python
def check_table_columns(md: str) -> list[tuple[int, str]]:
    """返回 [(行号, 原因), ...]，行号从 1 开始"""
    lines = md.splitlines()
    in_code = False
    violations = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith("```"):
            in_code = not in_code
            i += 1
            continue
        if in_code:
            i += 1
            continue
        stripped = line.strip()
        if not stripped.startswith("|"):
            i += 1
            continue
        # 可能是表格起始行
        header_cols = _count_cols(stripped)
        if header_cols == 0:
            i += 1
            continue
        # 找分隔行
        j = i + 1
        while j < len(lines) and not lines[j].strip().startswith("|"):
            j += 1
        if j >= len(lines) or not _is_sep(lines[j].strip()):
            i += 1
            continue
        sep_cols = _count_cols(lines[j].strip())
        if sep_cols != header_cols:
            violations.append((j + 1, f"分隔行列数({sep_cols})≠表头列数({header_cols})"))
        # 检查数据行
        k = j + 1
        while k < len(lines):
            l = lines[k].strip()
            if not l.startswith("|"):
                break
            if _is_sep(l):
                k += 1
                continue
            data_cols = _count_cols(l)
            if data_cols != header_cols:
                violations.append((k + 1, f"数据行列数({data_cols})≠表头列数({header_cols})"))
            k += 1
        i = k
    return violations

def _count_cols(line: str) -> int:
    # 去首尾竖线，按未转义竖线分割
    content = line.strip("|")
    parts = []
    cur = ""
    esc = False
    for ch in content:
        if esc:
            cur += ch
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == "|":
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return sum(1 for p in parts if p.strip() != "")

def _is_sep(line: str) -> bool:
    return all(c in "|-: " for c in line) and "---" in line
```

## 边界用例

| 输入 | 期望判定 | 为什么 |
|------|----------|--------|
| `| a \| b | c |` 表头+分隔+ `| x | y |` | 合格 | 单元格内 `\|` 被计为内容非分隔符 |
| 表头 3 列、分隔 3 列、数据行 `| a | b |` | 违规 | 数据行少一格（2≠3） |
| 代码围栏内含 `| a | b |` 伪表格 | 合格 | 围栏内内容完全跳过不参与判定 |
| 表头被改成 `| a | b | c | d |` 但分隔仍 3 列 | 违规 | 表头列数(4)≠分隔列数(3) 触发 |

## 假绿

1. 全文无任何以 `|` 开头的行 ⇒ 返回空列表 ⇒ 恒判"合格"，实则未检查任何表格。
2. 表格仅有表头+分隔行、无数据行 ⇒ 循环不进入数据行检查 ⇒ 返回空列表 ⇒ 漏掉"表头列数≠分隔列数"。
===== END 底稿一 =====

===== BEGIN 底稿二（文件名 boundary-judge-design） =====
## 判定输入

| 字段名 | 取值域 | 谁在何时提供 |
|--------|--------|--------------|
| needs_non_producer_verdict | true/false | 派发方·派发前 |
| needs_multi_round_review | true/false | 派发方·派发前 |
| is_intra_dispatch_quality_gate | true/false | 受理方·受理阶段 |

## 求值点

三个字段均在**派发前**即可求值：`needs_non_producer_verdict` 与 `needs_multi_round_review` 由派发方依据任务卡元数据（如：审批流模板、复核规则表）在下发时写入；`is_intra_dispatch_quality_gate` 由受理方在受理阶段依据派发单的质量门类型字段判定。现有信息**缺少**：任务卡中未定义上述三个字段的标准键名、枚举值约束、以及“同一产物”与“非产出方主体”的机读界定键，需新增前置 schema 才能落地自动求值。

## 灰色地带对照表

| 场景 | 归属 | B-1/B-2/B-3 取值 |
|------|------|------------------|
| 判官抽检（断言 + 判官校准） | D6 | 否/否/是 |
| 受理阶段的协商回环（评审 ⇄ 修订） | D7 | 否/是/否 |
| 需求方验收签收 | D7 | 是/否/否 |
| 跨站派发 | D7 | 是/否/否 |
| 站间互审 | D7 | 是/是/否 |
| 异构复审编排 | D7 | 是/是/否 |
| 多轮续聊（审→改→再审） | D7 | 否/是/否 |
| agent 派生边表 / 多 agent 树 | D6 | 否/否/是 |

## 缺料与歧义

1. “同一产物”无机读键：缺少产物身份标识字段（如 product_id、artifact_hash）及其在派发卡中的传递约定
2. “非产出方主体”无判定字段：缺少主体角色枚举与归属关系表（如 producer_id vs reviewer_id）
3. 三判据字段的标准键名、取值约束、必填性未定义
4. 派发卡 schema 未包含上述字段，无法在派发前自动落层
5. “多轮往返”的轮次阈值（≥2 即算多轮？）未给出量化界限
===== END 底稿二 =====