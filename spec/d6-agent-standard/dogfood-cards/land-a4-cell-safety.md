---
proj: dogfood
task: 把随卡内嵌的"表格列数守恒判据"底稿**落成可落地件**（判据纯函数 + 夹具断言草案 + 边界用例 + 假绿清单 + 接线说明），写入 out/land-a4.md；只写这一个新文件
model: ultra-a
cli: opencode
sensitivity: public
input-provenance: none
readonly: false
timeout_s: 1800
accept:
  - test -f out/land-a4.md
  - grep -q '## 判据纯函数' out/land-a4.md
  - grep -q 'def ' out/land-a4.md
  - grep -q '## 夹具断言草案' out/land-a4.md
  - grep -q '## 边界用例' out/land-a4.md
  - grep -q '## 假绿清单' out/land-a4.md
  - grep -q '## 接线说明' out/land-a4.md
evidence-manifest:
  version: 1
  subjects:
    - name: land-a4
      path: land-a4.md
      state: out/land-a4.md
      digest: sha256
---
## 任务描述

**背景（抽象）**：一个**长期维护的文档仓库**要把一份"检查判据的设计底稿"落成**可执行的检查项（gate）**。
该仓库的落地形态**已定型**，所有新判据**共用同一套落法**：

1. **判据本体 = 纯函数**（无副作用、确定、可单测）；
2. 由**独立的检查项**调用它（入参 = 一批文本；输出 = 违规清单 ⇒ 非空即判红）；
3. **先验红**：先"把真对象改坏" ⇒ 断言**必须变红**（否则是空转）；另需能"把判据改成恒真/恒空 ⇒ 断言必须红"（变异自证）；
4. 若判据读**真值表** ⇒ 表头须带**读数日期**（增长型载体必须带）；
5. **"没判 ≠ 判了且通过"**：**整篇无表 / 无可判对象** ⇒ **单列报数，不入分母**（不许静默算通过）。

**你的任务**：对下面内嵌底稿，产出**落地件**，写成 `out/land-a4.md`。

### 产物格式（小节名**照抄**、顺序照抄）

1. `## 判据纯函数` —— 一段 **Python 纯函数**，签名建议 `check_table_columns(md: str) -> list[tuple[int, str]]`（返回 `[(行号, 原因)]`，行号从 1 起）。**≤45 行**（可含两个以 `_` 开头的小助手）。必须显式写清三条口径：
   ① **空单元格计入**列数（`| a |  | c |` = 3 格）；② **分隔行必须紧邻表头行的下一行**（**不**跨空行/跨散文去找）；③ **代码围栏**（```` ``` ```` 与 `~~~`）内的伪表格**跳过**。
2. `## 夹具断言草案` —— **≥5 条**（每条一行 `断言名 | 条件`），至少含：
   · 一条**先验红**用（把某数据行的一格注一个**未转义竖线** ⇒ 该行被拆多格 ⇒ 违规清单**非空**）；
   · 一条**变异自证**用（把判据改成"恒返空" ⇒ 上述断言**必须红**）；
   · 一条 **"整篇无表 ⇒ 空集但单列报数（不入分母）"**。
3. `## 边界用例` —— **≥5 条表**：`输入（一句话） | 期望 | 为什么`。覆盖：① 单元格内含**合法转义竖线**；② 数据行**少一格**；③ 表格在**代码围栏**内；④ 表头被改坏（表头列数≠分隔行）；⑤ 表头行**缩进 ≥4 空格**。
4. `## 假绿清单` —— **≥3 条**，每条 `情形 | 为什么未检 | 修法`。⚠ 底稿原"假绿第 2 条"**已证不实**（算法在进数据行循环**之前**已比对分隔行列数 ⇒ 该情形**会**被报出）⇒ **不要照抄它**；改给**真实**假绿（如：表头行缩进 ≥4 空格被当成表格、`~~~` 围栏未识别、整篇无表恒真空转）。
5. `## 接线说明` —— 说清：检查项入参是什么、输出怎么报、**空集/无对象如何单列报数**、以及"新增一项检查时需同步哪些**计数**"。
6. `## 不确定项` —— 你没把握的，逐条说明缺什么（**不许猜**）。

### 硬性要求
1. **不许编造**；读不出来 ⇒ 标"不确定"。
2. **不要引用/推测**任何具体项目、组织、主机、路径、人名。
3. **stdout 只输出一行**：`DOGFOOD_LAND_A4_OK`。
4. 除 `out/land-a4.md` 外**不产生任何文件**。

---

### 底稿（**已勘误** —— 照此落地，**勿回退**）

===== BEGIN 底稿（文件名 cell-safety-design · 勘误版） =====
## 判据定义

判据：**同一张表格内，所有数据行的列数必须等于表头行的列数**；列数 = 按**未转义竖线**分割后的单元格数（**空单元格计入**）。表头行、分隔行、数据行三者列数必须一致。

## 参考实现

```python
def check_table_columns(md: str) -> list[tuple[int, str]]:
    """返回 [(行号, 原因)], 行号从 1 起"""
    lines = md.splitlines()
    in_code, out, i = False, [], 0
    while i < len(lines):
        raw = lines[i]
        if raw.lstrip().startswith("```") or raw.lstrip().startswith("~~~"):
            in_code = not in_code; i += 1; continue
        if in_code:
            i += 1; continue
        head = raw.strip()
        if not head.startswith("|"):
            i += 1; continue
        hc = _count_cols(head)
        if hc == 0:
            i += 1; continue
        # 分隔行必须紧邻表头行的下一行（勘误②：不跨行去找）
        if i + 1 >= len(lines) or not _is_sep(lines[i + 1].strip()):
            i += 1; continue
        sc = _count_cols(lines[i + 1].strip())
        if sc != hc:
            out.append((i + 2, f"分隔行列数({sc})≠表头({hc})"))
        k = i + 2
        while k < len(lines) and lines[k].strip().startswith("|"):
            l = lines[k].strip()
            if _is_sep(l):
                k += 1; continue
            dc = _count_cols(l)
            if dc != hc:
                out.append((k + 1, f"数据行列数({dc})≠表头({hc})"))
            k += 1
        i = k
    return out

def _count_cols(line: str) -> int:
    body, parts, cur, esc = line.strip("|"), [], "", False
    for ch in body:
        if esc:
            cur += ch; esc = False
        elif ch == "\\":
            esc = True
        elif ch == "|":
            parts.append(cur); cur = ""
        else:
            cur += ch
    parts.append(cur)
    return len(parts)          # ★ 勘误①：空单元格计入

def _is_sep(line: str) -> bool:
    return "---" in line and all(c in "|-: \t" for c in line)
```

## 边界用例

| 输入 | 期望判定 | 为什么 |
|------|----------|--------|
| `| a \| b | c |` 表头+分隔+ `| x | y | z |` | 合格 | 单元格内 `\|` 被计为内容非分隔符 |
| 表头 3 列、分隔 3 列、数据行 `| a | b |` | 违规 | 数据行少一格（2≠3） |
| `| a |  | c |` 表头+分隔+ 3 格数据行 | 合格 | 中间空单元格**计入**（勘误①） |
| 代码围栏内含 `| a | b |` 伪表格 | 合格 | 围栏内内容完全跳过 |
| 表头被改成 `| a | b | c | d |` 但分隔仍 3 列 | 违规 | 表头列数(4)≠分隔列数(3) |

## 假绿

1. 全文无任何以 `|` 开头的行 ⇒ 返回空列表 ⇒ 恒判"合格"，实则未检查任何表格（**须单列报数，不入分母**）。
2. 表头行被缩进 ≥4 空格（GFM 视作代码块）⇒ 本实现 `strip()` 后仍当表格 ⇒ 判了一张并不存在的表。
3. `~~~` 围栏（早期实现只识别 ```` ``` ````）内的伪表格会被当真表判。
===== END 底稿 =====

> ⚠ 上表"假绿第 1 条"是**真**假绿（空集恒真）；请为它写出"如何**单列报数**避免静默通过"的接线说明。