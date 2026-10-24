# O-138 · P3 可比吞吐 A/B（halogen · MTP 开/关 · 与 P1 同 prompt 形状）

- 日期：2026-10-24 · 站 C（192.168.10.37 · gfx1151 · 128 GB）· 引擎 halogen **0.18.13**
- 权重：盘上既有 `UD-IQ4_XS` GGUF（3 shards）+ 同目录 `qwen38-flash-next-mtp.hgn`
- 探针：`probe_halogen.py`（= P1 的 `probe.py` **逐字同逻辑**，仅 URL 参数化到 :8731）
- 公共参数：`HALOGEN_CTX=32768` · `HALOGEN_KV_SLOTS=1` · `HALOGEN_KV_POOL_POSITIONS=32768` · `HALOGEN_HOST_RESERVE_GIB=8`
- 请求：temperature 0 · `max_tokens=128` · `enable_thinking=false`（响应 `reasoning_tokens=0` ⇒ 已生效）· 每档 3 次（随机盐）

## 结果（decode，t/s，引擎自报 `timings.predicted_per_second`）

| 档 | Arm A：MTP 默认开 | Arm B：`HALOGEN_MTP=0` | 比 |
|---|---|---|---|
| 短 prompt（≈560 tok） | 36.95 · 40.86 · 40.44 ⇒ **均 39.42** | 29.39 · 27.68 · 29.85 ⇒ **均 28.97** | **1.36×** |
| 长 prompt（≈4.1k tok） | 35.14 · 35.60 · 37.16 ⇒ **均 35.97** | 27.72 · 29.64 · 28.08 ⇒ **均 28.48** | **1.26×** |

**对照（同探针形状的历史读数）**：llama.cpp Vulkan 现役（P1 · 2026-10-22）= **27.55 / 26.85** ⇒
halogen **MTP off ≈ llama.cpp（+5%/+6%）**；halogen **MTP on = +43% / +34%**。

## 投机统计

| Arm | `drafter` | draft/accept | 接受率 |
|---|---|---|---|
| A（短） | `mtp` | 109/53 · 113/64 · 115/61 | 0.49–0.57 |
| A（长） | `mtp` | 101/52 · 108/53 · 106/55 | 0.51–0.52 |
| B | `lookup` | 0/0 · 9/9 · 12/10（多数轮 0） | — |

⇒ 该 prompt（"写长段续写"散文）的接受率落在 **0.49–0.57**，与 LLMKube 报的 **prose 0.55–0.67** 同区间（枚举型任务会更高）。

## prefill（同一批请求，仅作参照，**不可与 P1 的 32k 数并列**）

- 短档：860–972 t/s（568 tok）· 长档：1698–1725 t/s（≈4.1k tok）
- ⚠ LLMKube 同 SoC 记录：**小 prompt 的最差档**（664 tok = 209 t/s）；我们这次短档 860 明显高于它，差异**未追因**（prompt 内容/引擎版本/功耗状态均可能），**不作结论**

## 诚实边界

1. **Arm B 不是"纯串行"**：`HALOGEN_MTP=0` 关掉了 MTP head，但 **prompt-lookup（PLD）仍在**（`drafter: "lookup"`，个别轮抽到 9–12 token 且全接受）⇒ 严格串行需再关 `HALOGEN_PLD=0`（本批未做）。
2. **3 次/档**：offsite.guru 实测 decode 轮间波动 ±6%（接受率依赖生成文本）⇒ 均值差 1.26–1.36× 远大于噪声，但**不宜当精确系数**。
3. **与 LLMKube 的差异未追因**：他们用 `UD-Q3_K_XL`(83.8 GiB) + ctx 65536 + KV f16，我们用 `UD-IQ4_XS` + ctx 32768 ⇒ **不同档不可互换**；但两边的 "MTP off ≈ 25–28 t/s" 与 "MTP on ≈ +30–36%" 两条结论互相印证。
4. 单站、单流、无并发；长 ctx（>32k）与质量锚**未测**。
