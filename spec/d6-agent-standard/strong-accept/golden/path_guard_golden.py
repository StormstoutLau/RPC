#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GOLDEN authoritative criteria for spec/d6-agent-standard/strong-accept (O-12).

权威判据 = 主控站预置、独立于模型自写测试 (DESIGN §6.1)。模型不可自写测试自证通过。
本文件由 agent-cli.ps1 M2 伴随任务注入工作区 .golden/（保留 basename），M3 在 self-accept
之前以权威 checksum 防篡改后执行 (IMPLEMENTATION §3.3)。

-- GOLDEN_SENTINEL_7f3a9c21d5e84b62c0f1a9e3d7b5c4a0 --
哨兵 (V0 验证门, DESIGN §10.3): 回收模型输出时 grep 本哨兵值, 判断模型是否经工具读到 .golden/ 内容。
"""
import importlib.util
import os
import sys
import tempfile


PASS = 0
FAIL = 0


def check(name, got, expect):
    """记录一条断言, got/expect 均严格 bool 比较。"""
    global PASS, FAIL
    if got is expect:
        PASS += 1
        print("GOLDEN_CHECK[PASS] %s" % name)
    else:
        FAIL += 1
        print("GOLDEN_CHECK[FAIL] %s expect=%r got=%r" % (name, expect, got))


def load_target():
    """从远端工作区加载模型交付的 paper_cli/path_guard.py（不 import 模型自写测试）。"""
    p = os.path.join(os.getcwd(), "paper_cli", "path_guard.py")
    if not os.path.exists(p):
        raise FileNotFoundError("paper_cli/path_guard.py NOT FOUND - model did not deliver")
    spec = importlib.util.spec_from_file_location("path_guard", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "assert_safe_root"):
        raise AttributeError("assert_safe_root missing in delivered path_guard.py")
    return mod


def main():
    m = load_target()
    root = os.path.abspath(tempfile.mkdtemp(prefix="golden-root-"))
    root_b_sibling = os.path.join(root, "b")

    check("root 内直接子路径 True", m.assert_safe_root(os.path.join(root, "a", "b.md"), [root]), True)
    check("root 自身 True", m.assert_safe_root(root, [root]), True)
    check("同级逃逸 ../x False", m.assert_safe_root(os.path.join(root, "..", "x"), [root]), False)
    check("深层 ../ 逃逸 False", m.assert_safe_root(os.path.join(root, "a", "..", "..", "..", "etc", "passwd"), [root]), False)
    check("绝对路径不在 root 内 False", m.assert_safe_root("/etc/passwd", [root]), False)
    check("不存在 + allow_missing=True True", m.assert_safe_root(os.path.join(root, "missing", "f.md"), [root], allow_missing=True), True)
    check("不存在 + allow_missing=False False", m.assert_safe_root(os.path.join(root, "missing", "f.md"), [root], allow_missing=False), False)
    check("path=None False", m.assert_safe_root(None, [root]), False)
    check("allowed_roots 空 False", m.assert_safe_root(os.path.join(root, "a"), []), False)
    check("多 root 落在第二 root True", m.assert_safe_root(os.path.join(root_b_sibling, "c.md"), [root, root_b_sibling]), True)

    print("GOLDEN_RESULT: PASS=%d FAIL=%d" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())