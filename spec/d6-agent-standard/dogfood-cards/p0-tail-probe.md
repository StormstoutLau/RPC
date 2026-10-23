---
proj: dogfood
task: 在 out/ 下写恰好一个文件 out/p0-tail-ok.txt（唯一一行 P0_TAIL_OK），stdout 只输出一行 DOGFOOD_P0TAIL_OK
model: ultra
cli: opencode
sensitivity: public
readonly: true
timeout_s: 300
evidence-budget:
  anchors: 1
  tool_calls: 2
accept:
  - test -f out/p0-tail-ok.txt
  - grep -qx 'P0_TAIL_OK' out/p0-tail-ok.txt
evidence-manifest:
  version: 1
  subjects:
    - name: p0-tail
      path: p0-tail-ok.txt
      state: out/p0-tail-ok.txt
      digest: sha256
---
> **P0 尾款确认真跑**：验证 TC/RR 的 `open` 桶清空 ——
> `evidence_budget` 由本卡**声明**（D2）· 无 golden ⇒ `golden.checksum` 不适用（D1）·
> `attempt`/`evidence` 走接线（D4/D3）⇒ 期望两条 `_GAPS_CLASS: open=[]`。
> 【输出】`out/p0-tail-ok.txt` 一行 `P0_TAIL_OK`；stdout 一行 `DOGFOOD_P0TAIL_OK`。

## 任务描述

1. 创建 `out/`（若缺）；
2. 写 `out/p0-tail-ok.txt`，内容**恰好一行**：`P0_TAIL_OK`；
3. stdout **只**输出一行：`DOGFOOD_P0TAIL_OK`。