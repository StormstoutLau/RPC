---
proj: paper
task: 新增 code_check 校验模块并通过其单测 + classifier 回归
model: nemotron
cli: opencode
sensitivity: local-only
readonly: false
timeout_s: 1800
accept:
  - cd /home/scott-lau/agent-workspaces/paper && ./.venv/bin/python -m pytest paper_cli/tests/test_code_check.py -q
  - cd /home/scott-lau/agent-workspaces/paper && ./.venv/bin/python -m pytest paper_cli/tests/test_classifier.py -q
---
## 任务描述

你必须**实际创建两个新文件**：`paper_cli/code_check.py` 和 `paper_cli/tests/test_code_check.py`。禁止只分析、只解释、只总结——完成标准是这两个新文件真实存在且单测通过。除创建这两个新文件外，不得修改或删除任何既有文件。

### 文件 1：`paper_cli/code_check.py`

实现且仅实现一个纯函数：

```python
def is_well_formed_code(code: str | None) -> bool:
```

`code` 表示一份内部文献编号。返回 `True` 当且仅当其满足 ALL：
1. 非空（`None` 与空串都返回 `False`）；
2. 由两段组成，用连字符分隔：`PREFIX-NUM`；
3. `PREFIX` 为 2-5 个大写 ASCII 字母（如 `ISA`、`QF`），不含数字；
4. `NUM` 为 3-8 位十进制数字（如 `2024`、`000123`）；
5. 总长度不超过 40 个字符。

字符串必须完全匹配上述结构，不允许前后空白。除标准库外不导入任何其他模块。

### 文件 2：`paper_cli/tests/test_code_check.py`

用 pytest 为 `is_well_formed_code` 编写覆盖全部边界的断言（函数式断言，不需要 fixture）：
- `None` → `False`；空串 `""` → `False`；
- 合法样例 `"ISA-2024"` → `True`；
- 合法样例 `"QF-000123"` → `True`；
- 缺连字符（如 `"ISA2024"`）→ `False`；
- 多段（如 `"ISA-20-24"`）→ `False`；
- 前缀含小写（如 `"isa-2024"`）→ `False`；
- 前缀含数字（如 `"I1A-2024"`）→ `False`；
- 前缀过短/过长（如 `"A-2024"` 单字母、`"ABCDEF-2024"` 六字母）→ `False`；
- 数字段带非数字（如 `"ISA-20A4"`）→ `False`；
- 数字段过短/过长（如 `"ISA-12"` 两位数、`"ISA-123456789"` 九位）→ `False`。

### 完成标准

在 `paper_cli` 目录下执行 `./.venv/bin/python -m pytest paper_cli/tests/test_code_check.py -q` 应全绿；且既有 `paper_cli/tests/test_classifier.py` 的 29 个用例仍旧全绿。这就是验收判据，两者都必须通过才算完成。