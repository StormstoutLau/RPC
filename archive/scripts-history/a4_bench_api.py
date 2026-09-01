#!/usr/bin/env python3
# a4_bench_api.py — A4: vLLM OpenAI API 吞吐实测 (TTFT/TPOT/PP/TG)
# 口径对齐 llama-bench -p <P> -n <N>: PP = prompt_tokens/TTFT, TG = gen_tokens/(total-TTFT)
# 用法: python3 a4_bench_api.py --host 127.0.0.1 --port 8081 --prompt-tokens 512 --gen-tokens 128 --repeats 3
import argparse
import json
import time
import urllib.request


def bench_once(host, port, model, prompt, gen_tokens, seed):
    url = f"http://{host}:{port}/v1/completions"
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": gen_tokens,
        "temperature": 0.0,
        "seed": seed,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    ttft = None
    n_chunks = 0
    usage_completion = None
    with urllib.request.urlopen(req, timeout=1200) as resp:
        for line in resp:
            if not line.startswith(b"data:"):
                continue
            body = line[5:].strip()
            if body == b"[DONE]":
                break
            chunk = json.loads(body)
            if "usage" in chunk and chunk["usage"]:
                usage_completion = chunk["usage"].get("completion_tokens")
            ch = chunk.get("choices")
            if ch and ch[0].get("text"):
                if ttft is None:
                    ttft = time.perf_counter() - t0
                n_chunks += 1
    total = time.perf_counter() - t0
    if ttft is None:
        ttft = total
    ntok = usage_completion if usage_completion else n_chunks
    return ttft, total, ntok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8081)
    ap.add_argument("--model", default="minimax-m2")
    ap.add_argument("--prompt-tokens", type=int, default=512)
    ap.add_argument("--gen-tokens", type=int, default=128)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--warmup", type=int, default=1)
    args = ap.parse_args()

    # 确定性但前缀唯一的 prompt: 数字序列 (每 token 互异, 杜绝跨 run prefix 命中)
    import random
    rng = random.Random(42 + args.prompt_tokens)
    vocab = [f"{i}" for i in range(1000)]
    prompt = " ".join(rng.choices(vocab, k=args.prompt_tokens))

    # warmup (不计入)
    for _ in range(args.warmup):
        bench_once(args.host, args.port, args.model, "Hello", 4, 0)
        bench_once(args.host, args.port, args.model, prompt, 8, 0)

    rows = []
    for r in range(1, args.repeats + 1):
        # 每 run 独立随机 seed: prompt 内容互异, 杜绝 prefix cache 命中
        rng_r = random.Random(1000 + r)
        prompt_r = " ".join(rng_r.choices(vocab, k=args.prompt_tokens))
        ttft, total, ntok = bench_once(
            args.host, args.port, args.model, prompt_r, args.gen_tokens, r)
        decode_t = total - ttft
        pp = args.prompt_tokens / ttft if ttft > 0 else 0
        tg = ntok / decode_t if decode_t > 0 else 0
        rows.append((ttft, total, ntok, pp, tg))
        print(f"  run{r}: TTFT={ttft*1000:.0f}ms total={total:.1f}s "
              f"ntok={ntok} PP={pp:.1f} tok/s TG={tg:.2f} tok/s", flush=True)

    # 中位数摘要
    def med(idx):
        vals = sorted(row[idx] for row in rows)
        return vals[len(vals) // 2]
    pp_m = med(3)
    tg_m = med(4)
    ttft_m = med(0)
    print(f"SUMMARY p{args.prompt_tokens} g{args.gen_tokens}: "
          f"PP={pp_m:.1f} tok/s TG={tg_m:.2f} tok/s TTFT={ttft_m*1000:.0f}ms "
          f"(median of {args.repeats}, vLLM minimax-m2 TP=2)")


if __name__ == "__main__":
    main()
