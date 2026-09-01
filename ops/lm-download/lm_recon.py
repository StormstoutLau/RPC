#!/usr/bin/env python3
"""lm_recon.py — 侦察: 提取 LM Studio 全部下载任务完整 URL/目标路径/字节数, 供 aria2 续传用"""
import json, os

p = os.path.expanduser("~/.lmstudio/.internal/download-jobs-info.json")
d = json.load(open(p))
jobs = d if isinstance(d, list) else d.get("jobs", d)
items = jobs if isinstance(jobs, list) else list(jobs.values())

def walk_tasks(j):
    """递归找 task 里的下载信息 (downloadTask 嵌套)"""
    out = []
    for t in j.get("tasks", []):
        if not isinstance(t, dict):
            continue
        # 找任意含 url/bytes 的 dict
        stack = [t]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                if "url" in cur or "downloadUrl" in cur:
                    out.append(cur)
                for v in cur.values():
                    if isinstance(v, (dict, list)):
                        stack.append(v if isinstance(v, dict) else v[0] if v else None)
                        if isinstance(v, list):
                            stack.extend(x for x in v if isinstance(x, dict))
                stack = [x for x in stack if isinstance(x, dict)]
    return out

print("### JOBS ###")
for j in items:
    if not isinstance(j, dict):
        continue
    print("=" * 70)
    print("jobName :", j.get("jobName", "?"))
    js = j.get("jobState", {})
    print("jobState:", js.get("type", "?") if isinstance(js, dict) else js)
    for t in j.get("tasks", []):
        if not isinstance(t, dict):
            continue
        # 打印整个 task 的 json 结构 (一次), 供人工判读字段名
        print("--- task ---")
        print(json.dumps(t, ensure_ascii=False, indent=1)[:2000])
