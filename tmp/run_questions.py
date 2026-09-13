#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""domain_matrix 20 题 runner — 单模型串行跑题，长思考等待 + 断点续跑。
用法: python3 run_questions.py <server_url> <questions.json> <out_dir> [--reasoning-preserve]
输出: out_dir/{qid}.jsonl — 每题 {id, answer, reasoning, usage, elapsed}
"""
import argparse, json, os, sys, time, urllib.request

def api(url, payload, timeout=3600):
    req = urllib.request.Request(
        url + "/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("server")
    ap.add_argument("questions")
    ap.add_argument("out_dir")
    ap.add_argument("--reasoning-preserve", action="store_true")
    ap.add_argument("--max-tokens", type=int, default=12000)
    ap.add_argument("--model-name", default="local")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    qs = json.load(open(args.questions, encoding="utf-8"))

    done = set()
    for f in os.listdir(args.out_dir):
        if f.endswith(".jsonl"):
            done.add(f[:-6])

    for q in qs:
        qid = q["id"]
        if qid in done:
            print(f"[skip] {qid} 已完成", flush=True)
            continue
        payload = {
            "model": args.model_name,
            "messages": [
                {"role": "system", "content":
                 "你是量化金融/数学领域的深度推理评测模型。以下是一道学术评测题。"
                 "请严格按『任务』分步作答：先给出完整推理过程，再给出最终结论。"
                 "中文作答；每步一个明确结论；对『深度』要求主动批判边界。若涉及代码请给出完整可运行代码。"},
                {"role": "user", "content": q["prompt"]},
            ],
            "temperature": 0.6,
            "top_p": 0.95,
            "max_tokens": args.max_tokens,
            "stream": False,
        }
        t0 = time.time()
        try:
            resp = api(args.server, payload)
            choice = resp["choices"][0]["message"]
            rec = {
                "id": qid,
                "title": q["title"],
                "answer": choice.get("content", ""),
                "reasoning": choice.get("reasoning_content"),
                "usage": resp.get("usage"),
                "elapsed": round(time.time() - t0, 1),
            }
        except Exception as e:
            rec = {"id": qid, "title": q["title"], "error": str(e),
                   "elapsed": round(time.time() - t0, 1)}
        with open(os.path.join(args.out_dir, f"{qid}.jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[done] {qid} {rec.get('elapsed', 0)}s", flush=True)

    print("ALL-DONE", flush=True)

if __name__ == "__main__":
    main()