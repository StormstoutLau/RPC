"""O-35 引擎层并发验证（站上运行；只发 HTTP，不碰引擎配置）。

问句：**同一个本地引擎（:8080）能否并发行服务？最危险形态 = 输出错配（A 的 prompt 得到 B 的输出）。**
设计：两组**互不相同的哨兵串**，串行基线 vs 2 路并发，逐条判"是否只含自己的哨兵"。
"""
import json
import os
import threading
import time
import urllib.request

KEY = open(os.path.expanduser("~/.config/rpc/unsloth.key")).read().strip()
URL = "http://127.0.0.1:8080/v1/chat/completions"
T1 = "AAAA-1111-AAAA-1111"
T2 = "BBBB-2222-BBBB-2222"


def ask(tag, tok, ret):
    body = {"model": "gpt-oss-20b", "temperature": 0, "max_tokens": 768,
            "messages": [{"role": "user",
                          "content": f"只输出下面这一行，不要任何其他文字、不要解释：{tok}"}]}
    req = urllib.request.Request(
        URL, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            raw = r.read().decode()
        j = json.loads(raw)
        msg = j["choices"][0]["message"]
        # ★ 判据用**全响应体**（含 reasoning 字段）：错配会体现在**任何**字段里，
        #   只看 content 会被"推理打满预算 ⇒ content 被截断"掩盖（首轮即踩到）。
        ret[tag] = (round(time.time() - t0, 2), raw, None, j.get("usage"),
                    (msg.get("content") or "").strip())
    except Exception as e:  # noqa: BLE001
        ret[tag] = (round(time.time() - t0, 2), "", f"{type(e).__name__}: {e}", None, "")


def judge(tag, tok, other, out):
    dt, raw, err, usage, content = out[tag]
    own = tok in raw
    cross = other in raw
    verdict = "ERR:" + err if err else ("★错配" if cross else ("✓ 正确" if own else "✗ 未含哨兵"))
    ct = (usage or {}).get("completion_tokens")
    return (f"  {tag:10s} {dt:6.2f}s  own={own!s:5s} cross={cross!s:5s} {verdict}  "
            f"ctok={ct}  content={content[:34]!r}")


def main():
    print("=== 引擎层并发验证 (O-35) ===")
    print(f"哨兵: T1={T1}  T2={T2}")

    s = {}
    t0 = time.time()
    ask("serial-1", T1, s)
    ask("serial-2", T2, s)
    serial_wall = round(time.time() - t0, 2)
    for t in ("serial-1", "serial-2"):
        print(judge(t, T1 if t.endswith("1") else T2, T2 if t.endswith("1") else T1, s))
    print(f"  [串行] 墙钟合计 = {serial_wall}s")

    c = {}
    th = [threading.Thread(target=ask, args=("conc-1", T1, c)),
          threading.Thread(target=ask, args=("conc-2", T2, c))]
    t0 = time.time()
    for t in th:
        t.start()
    for t in th:
        t.join()
    conc_wall = round(time.time() - t0, 2)
    for t in ("conc-1", "conc-2"):
        print(judge(t, T1 if t.endswith("1") else T2, T2 if t.endswith("1") else T1, c))
    print(f"  [并发] 墙钟合计 = {conc_wall}s")

    errs = [1 for t in ("conc-1", "conc-2") if c[t][2]]
    mix = [1 for t in ("conc-1", "conc-2")
           if (T2 if t.endswith("1") else T1) in c[t][1]]
    print("\n=== 判据 (2 路) ===")
    print(f"  并发报错数        = {len(errs)}/{2}   (0 = 引擎接受并发)")
    print(f"  ★输出错配数       = {len(mix)}/{2}   (0 = 无张冠李戴)")
    print(f"  并发墙钟/串行墙钟 = {conc_wall}/{serial_wall} = "
          f"{round(conc_wall / serial_wall, 2)}×   (≈1 表示并行、≈2 表示排队)")

    # ── 压满引擎槽位（实测命令行 --parallel 4）⇒ 测**上限**而非仅"能并发" ──────────
    toks = {f"n4-{i}": f"CCCC-{i}{i}{i}{i}-CCCC-{i}{i}{i}{i}" for i in range(1, 5)}
    alltok = list(toks.values())
    q = {}
    th4 = [threading.Thread(target=ask, args=(k, v, q)) for k, v in toks.items()]
    t0 = time.time()
    for t in th4:
        t.start()
    for t in th4:
        t.join()
    w4 = round(time.time() - t0, 2)
    for k in toks:
        print(judge4(k, toks[k], alltok, q))
    e4 = [k for k in toks if q[k][2]]
    m4 = [k for k in toks if any(t != toks[k] and t in q[k][1] for t in alltok)]
    print(f"  [4 路] 墙钟合计 = {w4}s")
    print("\n=== 判据 (4 路, 压满槽位) ===")
    print(f"  报错数 = {len(e4)}/4   错配数 = {len(m4)}/4   "
          f"4路/串行 = {round(w4 / serial_wall, 2)}×")
    errs += e4
    mix += m4
    print("RESULT: " + ("PASS-并发安全" if not errs and not mix else "★发现问题 ⇒ 需 flock"))


def judge4(tag, tok, alltok, out):
    dt, raw, err, usage, content = out[tag]
    own = tok in raw
    cross = [t for t in alltok if t != tok and t in raw]
    verdict = "ERR:" + err if err else ("★错配" if cross else ("✓ 正确" if own else "✗ 未含哨兵"))
    return (f"  {tag:8s} {dt:6.2f}s  own={own!s:5s} cross={bool(cross)!s:5s} {verdict}  "
            f"ctok={(usage or {}).get('completion_tokens')}  content={content[:26]!r}")


if __name__ == "__main__":
    main()
