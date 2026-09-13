#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工作区密钥脱敏：把 _secret_keys_replace.txt 中的字面密钥 + 正则规则替换为占位符。
只处理文本文件。替换值匹配 filter-repo 默认的 ***REMOVED***。"""
import re, pathlib

ROOT = pathlib.Path(r"d:\RPC")
RULE = pathlib.Path(r"d:\RPC\tmp\_secret_keys_replace.txt")
PLACEHOLDER = "***REMOVED***"

# 收集规则
literal = []
regex = []
for line in RULE.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line:
        continue
    if line.startswith("regex:"):
        regex.append(re.compile(line[len("regex:"):]))
    else:
        literal.append(line)

BINARY_EXT = {".pkl",".pth",".png",".jpg",".jpeg",".gif",".bin",".gguf",".zip",".docx",
              ".xlsx",".ppt",".pptx",".pyc",".whl",".tar",".gz",".so",".dll",".exe",".lock"}
# gitignore 的依赖目录
SKIP_DIR = {"node_modules",".git",".venv","venv"}

changed = 0
matched_files = []
for p in ROOT.rglob("*"):
    if not p.is_file():
        continue
    if any(part in SKIP_DIR for part in p.parts):
        continue
    if p.suffix.lower() in BINARY_EXT:
        continue
    # 只读文本，跳过超大
    try:
        if p.stat().st_size > 5_000_000:
            continue
        data = p.read_bytes()
        if b"\x00" in data[:1024]:
            continue  # 二进制
        text = data.decode("utf-8", "replace")
    except Exception:
        continue
    orig = text
    hit = False
    for k in literal:
        if k in text:
            text = text.replace(k, PLACEHOLDER); hit = True
    for rx in regex:
        if rx.search(text):
            text = rx.sub(PLACEHOLDER, text); hit = True
    if hit:
        p.write_text(text, encoding="utf-8")
        changed += 1
        matched_files.append(str(p))

print(f"changed files: {changed}")
for f in matched_files:
    print("  " + f)