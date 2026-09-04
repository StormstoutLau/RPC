#!/usr/bin/env python3
# BS-2 跨站扇出验证 (BLINDSCAN §8.7.4 L1 判据)
# 编排层在 B 站:
#   B_self   = http://127.0.0.1:8080   (B 站 gpt-oss-120b, key sk-unsloth-0895...)
#   A_tunnel = http://127.0.0.1:18081  (ssh 隧道 -> A 站 10.10.10.1:127.0.0.1:8080, key sk-unsloth-3ea8...)
# 实验:
#   1) A 串行基线: 4 个请求顺序打到 A_tunnel (代表"单站 4 个独立任务串行")
#   2) 跨站扇出:   2 并发打到 B_self + 2 并发打到 A_tunnel (A+B 各 2 次)
# 判据: cross_wall <= a_serial_sum * ~1.6  (对照 §8.4 同站并发仅微慢 3%)
#       且数据面真并行: cross_wall ~= max(单请求耗时) 而非 sum
# 报告 wall 收敛 + 每请求 tool_calls (直连模型单轮仅返 1, 故用纯生成计时而非 tool 并行)
import json, time, urllib.request, urllib.error, threading

B = ("http://127.0.0.1:8080/v1/chat/completions", "sk-unsloth-0895f5f165a09ae56b871dd52b074b94")
A = ("http://127.0.0.1:18081/v1/chat/completions", "sk-unsloth-3ea8ee000acbc1db06dcce310125d691")
MODEL = "gpt-oss-120b-MXFP4"
PROMPT = ("You are a data-parallel benchmark probe. "
          "Briefly summarize quant factor momentum in 2 sentences.")
REQS = 4          # 总请求数 (4 个独立任务)

def one(url, key):
    body = {"model": MODEL,
            "messages": [{"role": "user", "content": PROMPT}],
            "max_tokens": 64}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + key}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            d = json.loads(r.read().decode())
        return r.status, time.time() - t0, d
    except urllib.error.HTTPError as e:
        return e.code, time.time() - t0, str(e.read())[:120]
    except Exception as e:
        return -1, time.time() - t0, str(e)[:120]

print("="*60)
print("[1] A 串行基线: 4 次顺序打到 A (tunnel 18081)")
a_ser = []
for i in range(REQS):
    s, dt, d = one(*A)
    a_ser.append(dt)
    print(f"  [A-ser#{i+1}] s={s} dt={dt:.1f}s")
a_sum = sum(a_ser)
print(f"  A_SERIAL sum={a_sum:.1f}s avg={a_sum/REQS:.1f}s")

print("="*60)
print(f"[2] 跨站扇出: {REQS//2} 并发→B + {REQS//2} 并发→A")
# 构造请求列表: A 分配前 REQS//2, B 分配后 REQS//2 (或交替)
# 交替分配: 2 发 →A, 2 发 →B
targets = [A, B, A, B][:REQS]
res = [None]*REQS
t0 = time.time()
def w(i):
    res[i] = one(*targets[i])
ts = [threading.Thread(target=w, args=(i,)) for i in range(REQS)]
for t in ts: t.start()
for t in ts: t.join()
cross_wall = time.time() - t0
for i, (s, dt, _) in enumerate(res):
    where = "A" if targets[i] is A else "B"
    print(f"  [par#{i+1}->{where}] s={s} dt={dt:.1f}s")
print(f"  CROSS wall={cross_wall:.1f}s")

print("="*60)
print(f"A串行sum={a_sum:.1f}s  cross_wall={cross_wall:.1f}s  ratio=cross/a_ser_sum={cross_wall/a_sum:.2f}")
print(f"max_single={max(a_ser):.1f}s  cross_wall/max_single={cross_wall/max(a_ser):.2f}")
# 判据
if cross_wall <= a_sum * 1.6:
    print("判据: cross_wall <= A串行x1.6 ✅ 跨站扇出成立 (数据面并行收益)")
else:
    print("判据: cross_wall > A串行x1.6 ❌ 未收敛, 跨站扇出无收益")
# 真并行判据 (反向): cross ~ max 而非 sum
if cross_wall < a_sum * 0.5:
    print("真并行: cross_wall << A串行sum -> 两站数据面真并行 ✅")
else:
    print(f"真并行: cross_wall 接近 A串行sum -> 可能被串行化/带宽顶 (ratio={cross_wall/a_sum:.2f})")