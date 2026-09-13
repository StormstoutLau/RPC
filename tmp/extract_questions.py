# -*- coding: utf-8 -*-
"""从 domain_matrix.md 提取题目本体（题干+前置概念+任务），剥离判分锚点/幻觉标志/输入输出约束。
输出 questions.json: [{id, title, prompt}] — prompt 为发给模型的完整题面（中文）。"""
import json, re

SRC = r"d:\RPC\spec\model-eval\questions\domain_matrix.md"
OUT = r"d:\RPC\tmp\questions.json"

with open(SRC, encoding="utf-8") as f:
    text = f.read()

# 按 ### {section}.{n}. 标题切分
sections = re.split(r"\n### ", text)
items = []
for sec in sections:
    m = re.match(r"([A-J])(\d+)\.\s*.+?\n", sec)
    if not m:
        continue
    qid = f"{m.group(1)}{m.group(2)}"
    # 去掉整体开头的行（标题之后的 --- 和前言若在第 n-1 节残留，这里以 ### 为界即可）
    body = sec.split("\n", 1)[1] if "\n" in sec else ""
    # header 段：题目行
    lines = body.splitlines()
    # 提取块
    keep = []
    cur = []       # 当前块文本（非目标小节前缓冲）
    title = ""
    in_exclude = None
    for ln in lines:
        st = ln.strip()
        if st.startswith("###") or st.startswith("---") or st.startswith("id:") or \
           st.startswith("type:") or st.startswith("version:") or st.startswith("status:") or \
           st.startswith("date:") or st.startswith("depends:") or st.startswith("upstream:"):
            continue
        if st.startswith("## "):
            continue
        # 跳过 frontmatter 尾部 '---'
        if st == "---":
            continue
        # 标题: "### A1. xxx `[概念] ..." 已在上层 regex 处理; 这里处理题目号行 "###" 开头已跳过
# 简化：逐节重建
questions = []
# 用更精确的分节：定位每节的属性行
pattern = re.compile(r"\n### ([A-J]\d+)\.\s+(.+?)\n")
matches = list(pattern.finditer(text))

for i, m in enumerate(matches):
    qid, title = m.group(1), m.group(2).strip()
    start = m.end()
    end = matches[i+1].start() if i+1 < len(matches) else len(text)
    chunk = text[start:end]

    # 提取字段块
    def grab(label):
        # 匹配 "- **前置概念**: ..." 或 "**前置概念**:"
        r = re.search(rf"-?\s*\**{label}\**\**[:：]\s*(.+?)(?=\n- |\n\*\*|\n### |\Z)", chunk, re.S)
        return r.group(1).strip() if r else ""

    premise = grab("前置概念")
    app = grab("应用对象")
    task = grab("任务·分步")

    prompt_parts = []
    if premise:
        prompt_parts.append(f"### 前置概念\n{premise}")
    if app:
        prompt_parts.append(f"### 应用对象\n{app}")
    if task:
        prompt_parts.append(f"### 任务\n{task}")

    questions.append({
        "id": qid,
        "title": title,
        "prompt": "\n\n".join(prompt_parts),
    })

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(questions, f, ensure_ascii=False, indent=2)

print(f"提取 {len(questions)} 题 -> {OUT}")
for q in questions:
    print(f"  {q['id']}: {q['title'][:40]} (prompt {len(q['prompt'])} chars)")