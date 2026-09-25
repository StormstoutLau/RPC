#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cluster_console — 控制台**显示宽度**与**按显示宽度填充**（`cluster*.py` 的共用底层件）。

为什么存在（D6-P3-1）: Python 的 `ljust` / 格式宽度（`{s:16s}`）数的是**码点**而非**显示列**
  ⇒ 含 CJK 时**必然错位**（实测：`明文扫描` = 4 码点但 **8 显示列**；`{title:16s}` 会补 **12** 个空格而非 8）。
  本模块把"显示宽度"收敛成**唯一实现**，供 `cluster.py` / `cluster_secrets.py` / `cluster_egress.py` /
  `rpc_check.py` 共用（既有 `_dw` / `_pad` 的实现**原样搬来**，不新写第二份）。

为什么放在**最底层（L0）**: 上面几个模块分处 L2/L3/L4 —— 若把工具留在 `cluster.py`（L4），
  L2/L3 去取就是**反向 import** ⇒ 门禁 `deps` 的层序断言会 FAIL。故本模块**零内部依赖**，与 `cluster_const` 同层。

规则（对照 ds 三条，逐条说明适用性）:
  · **歧义宽度（East Asian Ambiguous）按 1 列** —— `east_asian_width` 只把 `W`/`F` 计 2，
    而 `A` 自然计 1 ⇒ **等价于 ds 的 `ambiguousIsNarrow: true`**（已一致，无需额外开关）。
  · **边界放不下一个双宽字符** —— 本模块**只补 ASCII 空格**（宽恒 1）且**不截断**
    ⇒ 该问题**在本场景不出现**（截断才会切出"半个双宽字符"）。
  · **零宽组合标记跟随前字符** —— **未实现**（如实留白：本仓中文为主、组合标记罕见，优先级最低；
    若要支持，在 `disp_width` 里把 `unicodedata.category(c) in ("Mn", "Me")` 计 0）。
"""
import unicodedata

__all__ = ["disp_width", "pad"]


def disp_width(s) -> int:
    """字符串的**终端显示列数**（CJK/全角 = 2；其余含歧义宽度 = 1）。"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))


def pad(s, width: int, right: bool = False) -> str:
    """按**显示宽度**把 `s` 补到 `width` 列（`right=True` 为右对齐）。

    ⚠ 只补空格、**不截断** —— 超宽时原样返回（截断会切出"半个双宽字符"，正是要害所在）。
    """
    s = str(s)
    gap = " " * max(0, width - disp_width(s))
    return gap + s if right else s + gap
