import json, glob, os, sys

def summarize(dir_path):
    files = sorted(glob.glob(os.path.join(dir_path, "*.jsonl")))
    tot_p = tot_c = tot_t = 0.0
    per = []
    for f in files:
        tid = os.path.splitext(os.path.basename(f))[0]
        p = c = e = 0
        try:
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    o = json.loads(line)
                    u = o.get("usage") or {}
                    p += u.get("prompt_tokens") or 0
                    c += u.get("completion_tokens") or 0
                    el = o.get("elapsed") or 0
                    e += el
        except Exception as ex:
            per.append((tid, "ERR", str(ex), 0, 0))
            continue
        t = p + c
        tps = (t / e) if e else 0
        per.append((tid, p, c, e, round(tps, 1)))
        tot_p += p; tot_c += c; tot_t += e
    print(f"== {dir_path} : {len(files)} 题 ==")
    for row in per:
        tid, p, c, e, tps = row
        if isinstance(tps, str):
            print(f"  {tid}: {p}")
        else:
            print(f"  {tid}: prompt={p} comp={c} elapsed={e:.0f}s decode_est={c/e:.1f} t/s total_est={tps:.1f} t/s")
    if tot_t > 0:
        print(f"  TOTAL: prompt={tot_p:.0f} comp={tot_c:.0f} elapsed={tot_t:.0f}s decode_est={tot_c/tot_t:.1f} total_est=(tot_p+tot_c)/t={ (tot_p+tot_c)/tot_t:.1f}")

if __name__ == "__main__":
    for d in sys.argv[1:]:
        summarize(d)