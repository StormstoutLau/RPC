#!/usr/bin/env python3
"""B5j 冒烟: DeepSeek-V4-Flash RPC 合并文件 API 生成验证 (两站资源一并采集)"""
import json, time, urllib.request, subprocess

URL = "http://127.0.0.1:8080/v1/chat/completions"
body = {
    "model": "deepseek-v4-flash",
    "messages": [{"role": "user", "content": "用一句话回答：法国的首都是哪里？"}],
    "max_tokens": 60,
}
t0 = time.time()
req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
try:
    r = json.loads(urllib.request.urlopen(req, timeout=180).read())
    dt = time.time() - t0
    content = r.get("choices", [{}])[0].get("message", {}).get("content", "")
    reasoning = r.get("choices", [{}])[0].get("message", {}).get("reasoning_content", "")
    usage = r.get("usage", {})
    print(f"HTTP OK {dt:.1f}s")
    print(f"content   : {content[:200]}")
    print(f"reasoning : {reasoning[:120] if reasoning else '(空)'}")
    print(f"usage     : {usage}")
except Exception as e:
    print(f"FAIL: {e}")
    raise SystemExit(1)

# 两站资源
for name, host in (("B", "127.0.0.1"), ("A", "192.168.1.11")):
    try:
        gtt = subprocess.check_output(
            ["ssh", host, "cat /sys/class/drm/card*/device/mem_info_vram_used 2>/dev/null | paste -sd, "],
            shell=False, timeout=15, text=True)
        free = subprocess.check_output(
            ["ssh", host, "free -g | awk 'NR==2{print $3\" used / \"$2\" total\"}'"], timeout=15, text=True).strip()
        print(f"站{name}: free={free} GTT={gtt.strip()}")
    except Exception as e:
        print(f"站{name}: 采集失败 {e}")
