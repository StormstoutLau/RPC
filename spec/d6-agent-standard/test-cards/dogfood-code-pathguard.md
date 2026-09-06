---
proj: paper
task: 新增 paper_cli/path_guard.py 安全路径校验模块 + 配套单测 test_path_guard.py，pytest 全绿；不修改任何既有文件
model: gpt-oss
cli: opencode
sensitivity: local-only
readonly: false
timeout_s: 900
accept:
  - cd /home/scott-lau/agent-workspaces/paper && ./.venv/bin/python -m pytest paper_cli/tests/test_path_guard.py -q
---
## 任务描述

你必须**实际创建两个新文件**：`paper_cli/path_guard.py` 和 `paper_cli/tests/test_path_guard.py`。禁止只分析/只解释/只总结——完成标准是两个文件真实存在且单测全绿。除新增这两个文件外，**不得修改或删除任何既有文件**。

### 文件 1：`paper_cli/path_guard.py`

实现**路径越界防护**纯函数（防止"先解引用后写"导致的目录逃逸，用于 agent-out 回收场景的安全检查）。仅导入标准库。

```python
import os

def assert_safe_root(path: str, allowed_roots: list[str], allow_missing: bool = True) -> bool:
    # path 经 os.path.realpath 解析（展开符号链接 + 消除 '..'），必须严格落在 allowed_roots 中
    #   的"某一个"根之内；根自身也算合法。
    # 判据：
    #   1) real = os.path.realpath(path, strict=False)
    #   2) real == root 或 os.path.commonpath([real, root]) == root
    #   3) 若 real 不存在 且 allow_missing=False → 一律 False
    # 参数校验：path/allowed_roots 任一为 None 或空 → False；path 非 str → False
    # resolve 后仍在根内 → True，否则 False
    ...
```

`commonpath` 是 prefix 关系的正确判据（`os.path.commonpath([root+'/x', root]) == root`）；注意 `commonpath` 在盘符跨盘（Windows）会抛 ValueError——用 try/except 捕获返回 False。

### 文件 2：`paper_cli/tests/test_path_guard.py`

用 pytest 覆盖以下断言（函数式，无需 fixture），至少 10 条：
- 根内直接子路径 → `True`（`assert_safe_root(root+'/a/b.md', [root])`）
- 根自身 → `True`
- 同级逃逸（`root+'/../x'` 解析后出根）→ `False`
- 深层 `../` 逃逸（`root+'/a/../../../etc/passwd'`）→ `False`
- 绝对路径不在根内 → `False`
- 不存在路径 + `allow_missing=True` → `True`（trusted 前缀）
- 不存在路径 + `allow_missing=False` → `False`
- `path=None` / `allowed_roots=[]` → `False`
- `path` 非 str（如传入数字）→ `False`
- 多根场景：落在第二个根内 → `True`

最后运行 `pytest paper_cli/tests/test_path_guard.py -q` 确认全绿。直接报告 pytest 通过行计数即可，不要附加与其无关的内容。