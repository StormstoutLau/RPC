---
proj: paper
task: 新增 paper_cli/ref_dedupe.py 功能模块 + 配套单测 test_ref_dedupe.py，pytest 全绿；不修改任何既有文件
model: nemotron
cli: opencode
sensitivity: local-only
readonly: false
timeout_s: 900
accept:
  - cd /home/scott-lau/agent-workspaces/paper && ./.venv/bin/python -m pytest paper_cli/tests/test_ref_dedupe.py -q
---
## 任务描述

你必须**实际创建两个新文件**：`paper_cli/ref_dedupe.py` 和 `paper_cli/tests/test_ref_dedupe.py`。禁止只分析/只解释/只总结——完成标准是两个文件真实存在且单测全绿。除新增这两个文件外，**不得修改或删除任何既有文件**。

### 文件 1：`paper_cli/ref_dedupe.py`

实现一个**纯函数式**文献条目重复判定模块（该工具属于 D:\Paper 文献整理链路的去重环节）。仅导入标准库。

定义数据类与函数：

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class EntryMeta:
    title: str
    authors: tuple[str, ...]
    year: int | None = None

def normalize_title(t: str) -> str:
    # 小写 + 去首尾/连续空白 + 去掉常见标点 (-:,;.'"()[]{} ) → 返回规范化串
    ...

def is_duplicate(a: EntryMeta, b: EntryMeta) -> bool:
    # 判据（全部成立才算重复）：
    #   1) normalize_title(a.title) == normalize_title(b.title)
    #   2) 作者交集非空：set(a.authors) & set(b.authors) 非空
    #   3) year 均可选：若两者都有 year 则 year 必须相等；有一个缺 year 则忽略 year 条件
    ...
```

边界要求：`normalize_title` 对 None/仅标点/空串返回空串而不抛异常；`is_duplicate` 在标题空串时一律 `False`（空标题不算重复）。

### 文件 2：`paper_cli/tests/test_ref_dedupe.py`

用 pytest 覆盖以下断言（函数式，无需 fixture），至少 10 条：
- `normalize_title('  The  Quick-Brown: Fox!  ')` → `'the quickbrown fox'`（大小写/空白/标点归一）
- 同一标题 + 有共同作者 + 同年 → `True`
- 同一标题 + 完全无共同作者 → `False`
- 同一标题 + 无共同作者但同年 → `False`（作者交集是硬条件）
- 同一标题 + 共同作者 + year 一个 None → `True`（缺 year 忽略）
- 同一标题 + 共同作者 + year 不同（如 2020 vs 2021）→ `False`
- 标题空串 + 任意 → `False`
- 标题归一化微小差异（大小写/连字符合并后）判定为重复
- `normalize_title('---')` → `''`（仅标点）
- `is_duplicate(a, a)` → `True`（自反）

最后运行 `pytest paper_cli/tests/test_ref_dedupe.py -q` 确认全绿。直接报告 pytest 通过行计数即可，不要附加与其无关的内容。