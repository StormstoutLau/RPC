#!/usr/bin/env python3
"""lm_jobs_inspect.py — 解析 LM Studio download-jobs-info.json (嵌套 tasks 结构)"""
import json, os
p = os.path.expanduser("~/.lmstudio/.internal/download-jobs-info.json")
d = json.load(open(p))
jobs = d if isinstance(d, list) else d.get("jobs", d)
items = jobs if isinstance(jobs, list) else list(jobs.values())
for j in items:
    if not isinstance(j, dict):
        continue
    print("=" * 60)
    print("jobName :", j.get("jobName", "?"))
    print("jobState:", j.get("jobState", "?"))
    print("fsPath  :", j.get("fileSystemPath", "?"))
    for t in j.get("tasks", []):
        if not isinstance(t, dict):
            continue
        dl = t.get("downloadTask") or t.get("download") or t
        print("  task:", t.get("taskType", t.get("type", "?")), "| state:", dl.get("state", "?"))
        print("    url :", str(dl.get("url", dl.get("sourceUrl", "?")))[:110])
        print("    prog:", dl.get("bytesReceived", dl.get("bytesLoaded", "?")), "/", dl.get("bytesTotal", "?"))
        print("    dest:", str(dl.get("destinationPath", dl.get("targetPath", dl.get("localPath", "?"))))[:130])
