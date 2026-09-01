#!/usr/bin/env python3
"""lm_manifest.py — 生成续传 manifest: 全部任务的 URL/sha256/总大小/本地现状 → TSV"""
import json, os, glob

p = os.path.expanduser("~/.lmstudio/.internal/download-jobs-info.json")
d = json.load(open(p))
jobs = d if isinstance(d, list) else d.get("jobs", d)
items = jobs if isinstance(jobs, list) else list(jobs.values())

MIRROR = "https://hf-mirror.com"
print("# job\thf_mirror_url\tsave_path\tsha256\ttotal_bytes\tlocal_bytes\tstatus")

def local_state(save_path):
    """探测本地文件状态: 完成 / .part 进行中 / 无"""
    if os.path.exists(save_path):
        return os.path.getsize(save_path), "FINAL"
    part = os.path.join(os.path.dirname(save_path), "downloading_" + os.path.basename(save_path) + ".part")
    if os.path.exists(part):
        return os.path.getsize(part), "PART"
    return 0, "MISSING"

for j in items:
    if not isinstance(j, dict):
        continue
    jname = j.get("jobName", "?")
    for t in j.get("tasks", []):
        if not isinstance(t, dict):
            continue
        req = t.get("request", {})
        dl = t.get("download", {})
        if not req or not dl:
            continue
        url = req.get("url", "")
        save = req.get("savePath", "")
        if "search.lmstudio.ai/v1/hf-proxy/" not in url:
            continue  # 跳过 tarball 等非模型任务
        # hf-proxy URL → hf-mirror URL
        mirror_url = url.replace("https://search.lmstudio.ai/v1/hf-proxy/", MIRROR + "/").split("?")[0]
        lb, state = local_state(save)
        print("\t".join([
            jname, mirror_url, save, req.get("sha256", "?"),
            str(req.get("fileSizeBytes", "?")), f"{lb}({state})", dl.get("status", "?")
        ]))
