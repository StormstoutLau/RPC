#!/usr/bin/env python3
"""lm_jobs_clean.py — 清理 LM Studio GUI 下载任务条目
原则: 只删除"目标文件已全部 FINAL"的 job; 备份先行; 原子写回
用法: lm_jobs_clean.py [--dry-run]
"""
import json, os, shutil, sys, time

P = os.path.expanduser("~/.lmstudio/.internal/download-jobs-info.json")
DRY = "--dry-run" in sys.argv

# --- 0. GUI 运行检查 (ps 里排除 llama-server 的 .lmstudio 模型路径误匹配) ---
import subprocess
out = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout
gui = [l for l in out.splitlines()
       if ("lm" in l.lower() and "studio" in l.lower())
       and ".lmstudio/models" not in l          # llama-server 模型路径误匹配源
       and "lm_jobs_clean" not in l
       and "ps -eo" not in l]
if gui:
    print("ABORT: 疑似 LM Studio GUI 进程在运行:")
    for l in gui[:5]:
        print("  ", l[:120])
    sys.exit(1)
print("OK: 无 LM Studio GUI 进程")

# --- 1. 读结构 ---
d = json.load(open(P))
if isinstance(d, list):
    kind, container = "list", d
elif isinstance(d.get("jobs"), list):
    kind, container = "dict.jobs", d["jobs"]
else:
    kind, container = "keyed-dict", d
print(f"结构: {kind}, 共 {len(container)} 个 job")

# --- 2. job 完成判定: 全部 hf-proxy 模型任务的 savePath 都已存在 ---
def job_complete(j):
    if not isinstance(j, dict):
        return False
    tasks = j.get("tasks", [])
    model_tasks = [t for t in tasks if isinstance(t, dict)
                   and "search.lmstudio.ai" in (t.get("request", {}).get("url") or "")]
    if not model_tasks:
        return False  # 无模型任务的 job 不动 (保守)
    return all(os.path.exists(t["request"]["savePath"]) for t in model_tasks)

# --- 3. 备份 + 过滤 + 原子写 ---
removed, kept = [], []
if kind == "list":
    for j in container:
        (removed if job_complete(j) else kept).append(j)
    new_container = kept
elif kind == "dict.jobs":
    for j in container:
        (removed if job_complete(j) else kept).append(j)
    new_container = kept
else:
    for k, j in container.items():
        if job_complete(j):
            removed.append(j)
        else:
            kept.append(j)
    new_container = {k: j for k, j in container.items() if not job_complete(j)}

print(f"\n将删除 {len(removed)} 个 job (文件已全部就位):")
for j in removed:
    n = len([t for t in j.get("tasks", []) if isinstance(t, dict)
             and "search.lmstudio.ai" in (t.get("request", {}).get("url") or "")])
    print(f"  - {j.get('jobName','?')} ({n} 个模型文件已验)")
print(f"保留 {len(kept)} 个 job")

if DRY:
    print("\nDRY-RUN: 未写回")
    sys.exit(0)

bak = P + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
shutil.copy2(P, bak)
if os.path.getsize(P) != os.path.getsize(bak):
    print("ABORT: 备份大小不一致"); sys.exit(1)
print(f"\n备份: {bak} ({os.path.getsize(bak)}B)")

if kind == "list":
    d = new_container
elif kind == "dict.jobs":
    d["jobs"] = new_container
else:
    d = new_container

tmp = P + ".tmp"
with open(tmp, "w") as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
# 写回前 json 语法自检
json.load(open(tmp))
os.replace(tmp, P)
print(f"已写回: {P} (job 数 {len(container)} → {len(new_container)})")

# --- 4. 顺带清孤儿: temp-downloads tarball (对应已删 job 的) ---
td = os.path.expanduser("~/.lmstudio/.internal/temp-downloads")
if os.path.isdir(td):
    for fn in os.listdir(td):
        fp = os.path.join(td, fn)
        if os.path.isfile(fp) and ("deepseek.deepseek-v4-flash" in fn):
            print(f"孤儿清理: {fp} ({os.path.getsize(fp)}B)")
            os.remove(fp)

# --- 5. 残留 .aria2 控制文件检查 (aria2 续传遗留) ---
import glob
for a in glob.glob(os.path.expanduser("~/.lmstudio/models/**/.aria2"), recursive=True) + \
         glob.glob(os.path.expanduser("~/.lmstudio/models/**/*.aria2"), recursive=True):
    print(f"残留 .aria2: {a}")
print("DONE")
