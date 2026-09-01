#!/usr/bin/env python3
# nemotron_ctx100k.py — 100k token needle 实测 (conf CTX=131072)
import json, time, urllib.request

API = "http://127.0.0.1:8080/v1/chat/completions"

paras = []
N = 1150  # ~100k tokens
needles = {
    55:   "ARCHIVE 7A: The vault access code for the Geneva repository is XJX-3391-QUASAR.",
    300:  "LOG 300: Chief engineer Marissa Chen approved the coolant budget at 4.2 million francs on March 3rd.",
    560:  "MEMO 560: The reactor containment pressure ceiling was revised to 61.8 bar by Dr. Osei.",
    820:  "NOTE 820: Tantalum capacitor shipment lot 88-B left Osaka on December 18th.",
    1080: "FINAL 1080: The inspection deadline was moved to November 30th by the Lyon office.",
}
for i in range(N):
    if i in needles:
        paras.append(needles[i])
    paras.append(f"Record {i:04d}: sensor grid readings nominal. Station {i%37} throughput {100 + i%50} units/cycle, "
                 f"drift {(i%13)*0.007:.3f}, calibration offset {(i%7)*0.02:.2f} microvolts. Window {i%11} closed clean. "
                 f"Operator {chr(65+i%26)}.{chr(97+i%26)} on shift {i%3}, pipeline pressure {2000 + (i*13)%400} kPa. "
                 f"Archive checksum {i*7919%99991:05d} verified against ledger {i%97}.")

doc = "\n".join(paras)
print(f"文档字符数: {len(doc)}, 估算 token ~{len(doc)//4}")

prompt = (f"以下是设备运行档案:\n\n{doc}\n\n"
          "基于档案回答五个问题, 每题一行:\n"
          "1. Geneva 金库访问代码 (完整引用)?\n"
          "2. 谁批准了冷却剂预算, 金额多少?\n"
          "3. 反应堆安全壳压力上限被谁修订为多少?\n"
          "4. 钽电容批次号与离开日期?\n"
          "5. 检查截止日期被改到哪天, 由哪个办公室?")

body = {"model": "nvidia-nemotron-3-super-120b-a12b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0, "max_tokens": 1024, "stream": False}
req = urllib.request.Request(API, data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"})
t0 = time.time()
with urllib.request.urlopen(req, timeout=3000) as r:
    d = json.loads(r.read().decode())
el = time.time() - t0
u = d.get("usage", {})
print(f"耗时 {el:.1f}s | prompt_tokens={u.get('prompt_tokens')} completion_tokens={u.get('completion_tokens')}")
print(f"等效 prefill ~{u.get('prompt_tokens',0)/(el - u.get('completion_tokens',0)/17.5):.0f} t/s (扣除 decode 17.5)")
print("--- 回答 ---")
print(d["choices"][0]["message"]["content"])
c = d["choices"][0]["message"]["content"]
checks = {
    "针1 XJX-3391-QUASAR": "XJX-3391-QUASAR" in c,
    "针2 Marissa Chen + 4.2": "Chen" in c and "4.2" in c,
    "针3 Osei + 61.8": "Osei" in c and "61.8" in c,
    "针4 88-B + 18": "88-B" in c and "18" in c,
    "针5 November 30 + Lyon": ("30" in c and "Lyon" in c),
}
for k, v in checks.items():
    print(f"[{'PASS' if v else 'FAIL'}] {k}")
