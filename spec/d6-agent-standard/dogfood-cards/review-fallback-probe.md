---
proj: dogfood
task: 在 out/ 下写恰好一个文件 out/fallback-ok.txt（唯一一行 FALLBACK_OK），stdout 只输出一行 DOGFOOD_FALLBACK_OK
model: ultra
cli: opencode
sensitivity: public
readonly: true
timeout_s: 300
accept:
  - test -f out/fallback-ok.txt
  - grep -qx 'FALLBACK_OK' out/fallback-ok.txt
evidence-manifest:
  version: 1
  subjects:
    - name: missing-product
      path: missing-product.md
      state: out/missing-product.md
      digest: sha256
---
> **本卡 = `D7-CC #8` 回退分支的真实 run 探针**：卡**声明**了 `missing-product.md`（`state: out/missing-product.md`），
> 而产出者**不写该文件** ⇒ collect 应报 `EVM_STATE_MISS` ⇒ runDir **无**该件 ⇒ review 的 `Resolve-ReviewProduct`
> 应走**回退**（期望逐字 `REVIEW_PRODUCT: agent-output.txt (source=fallback)`）。
> ★ 对照：**声明优先**分支（`source=evidence-manifest.subjects`）已于 2026-10-04 真跑过；本卡补的正是**另一分支**。
> 【输出】`out/fallback-ok.txt` 一行 `FALLBACK_OK`；stdout 一行 `DOGFOOD_FALLBACK_OK`。

## 任务描述

1. 创建 `out/`（若缺）；
2. 写 `out/fallback-ok.txt`，内容**恰好一行**：`FALLBACK_OK`；
3. stdout **只**输出一行：`DOGFOOD_FALLBACK_OK`。

（不要写其它文件；**不要**创建 `missing-product.md`。）