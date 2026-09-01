#!/usr/bin/env python3
# nemotron 16k needle 上下文实测: 多针检索 + 首尾定位
import json, time, urllib.request

API = "http://127.0.0.1:8080/v1/chat/completions"

# 构造 ~15k token 文档: 每段 ~60 token × 250 段
paras = []
NEEDLE_POS = 120  # 中段埋针
for i in range(250):
    if i == NEEDLE_POS:
        paras.append("ARCHIVE NOTE 7A: The vault access code for the Geneva repository is XJX-3391-QUASAR. "
                     "This code supersedes all earlier codes and must be quoted verbatim in full.")
    if i == 30:
        paras.append("LOG 30: Chief engineer Marissa Chen approved the coolant budget at 4.2 million francs on March 3rd.")
    if i == 220:
        paras.append("LOG 220: The final shipment of tantalum capacitors left the Osaka plant on December 18th, lot 88-B.")
    paras.append(f"Record {i:04d}: sensor grid readings nominal. Station {i%37} reported throughput at "
                 f"{100 + i%50} units per cycle, with drift coefficient {(i%13)*0.007:.3f} and calibration offset "
                 f"{(i%7)*0.02:.2f} microvolts. Maintenance window {i%11} closed without incident. The duty roster "
                 f"lists operator {chr(65+i%26)}.{chr(97+i%26)} for shift {i%3}, and the pipeline pressure held at "
                 f"{2000 + (i*13)%400} kilopascals throughout the interval. Archive checksum {i*7919%99991:05d}.")

doc = "\n".join(paras)
print(f"文档字符数: {len(doc)}, 估算 token: ~{len(doc)//4}")

prompt = (f"以下是设备运行档案:\n\n{doc}\n\n"
          "基于以上档案回答三个问题, 每题一行:\n"
          "1. Geneva 金库访问代码是什么 (完整引用)?\n"
          "2. 谁批准了冷却剂预算, 金额是多少?\n"
          "3. 最后一批钽电容何时离开大阪工厂, 批号是多少?")

body = {"model": "nvidia-nemotron-3-super-120b-a12b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0, "max_tokens": 1024, "stream": False}
req = urllib.request.Request(API, data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"})
t0 = time.time()
with urllib.request.urlopen(req, timeout=1800) as r:
    d = json.loads(r.read().decode())
el = time.time() - t0
u = d.get("usage", {})
print(f"耗时 {el:.1f}s | prompt_tokens={u.get('prompt_tokens')} completion_tokens={u.get('completion_tokens')}")
print(f"等效 prefill ~{u.get('prompt_tokens',0)/el:.0f} t/s (含生成)")
print("--- 回答 ---")
print(d["choices"][0]["message"]["content"])
print(f"finish={d['choices'][0].get('finish_reason')}")
# 判分
c = d["choices"][0]["message"]["content"]
checks = {
    "针1 (XJX-3391-QUASAR)": "XJX-3391-QUASAR" in c,
    "针2 (Marissa Chen / 4.2 million)": ("Marissa Chen" in c or "Chen" in c) and ("4.2" in c),
    "针3 (December 18 / 88-B)": ("18" in c and "88-B" in c),
}
for k, v in checks.items():
    print(f"[{'PASS' if v else 'FAIL'}] {k}")
