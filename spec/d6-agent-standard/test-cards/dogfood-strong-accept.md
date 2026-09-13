---
proj: paper
task: 新增 paper_cli/path_guard.py 安全路径校验模块，实现 assert_safe_root(path, allowed_roots, allow_missing=True)；不修改任何既有文件
model: gpt-oss
cli: opencode
sensitivity: local-only
readonly: false
timeout_s: 900
accept-golden:
  source: spec/d6-agent-standard/strong-accept/golden/path_guard_golden.py
  cmd: ./.venv/bin/python .golden/path_guard_golden.py
---
## 任务描述

你必须**实际创建新文件** `paper_cli/path_guard.py`。禁止只分析/只解释/只总结——完成标准是该文件真实存在且通过主控站 golden 判据（由 wrapper 在任务结束后以独立断言验证，非模型自写测试）。除新增该文件外，**不得修改或删除任何既有文件**。

### 文件：`paper_cli/path_guard.py`

实现**路径越界防护**纯函数（防止"先解引用后写"导致的目录逃逸，用于 agent-out 回收场景的安全检查）。仅导入标准库。签名与语义如下（主控站 golden 判据按此独立断言，不依赖你的任何测试文件）：

```python
import os

def assert_safe_root(path: str, allowed_roots: list[str], allow_missing: bool = True) -> bool:
    # path 经 os.path.realpath 解析（展开符号链接 + 消除 '..'），必须严格落在 allowed_roots 中的
    # "某一个"根之内；根自身也算合法（路径必须严格位于根下或就是根本身）。
    # 判据：
    #   1) real = os.path.realpath(path, strict=False)
    #   2) 存在某 root: real == root 或 os.path.commonpath([real, root]) == root
    #   3) 若 real 不存在 且 allow_missing=False → 一律 False
    #   4) path/allowed_roots 任一为 None 或空（[]）→ False；path 非 str → False
    # 命中根内 → True，否则 False
    ...
```

> 提示：`commonpath` 是 prefix 关系的正确判据（`os.path.commonpath([root+'/x', root]) == root`）；注意 `commonpath` 在盘符跨盘（Windows）会抛 ValueError——用 try/except 捕获返回 False（主控站 golden 用例含跨盘/多根场景，须稳健）。

完成后直接报告 "path_guard.py created" 即可，不要附加与其无关的内容。