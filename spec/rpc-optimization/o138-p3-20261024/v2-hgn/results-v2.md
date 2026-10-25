# O-138 · P3 单变量对照：BYO GGUF vs 官方 v2 `.hgn` checkpoint（2026-10-25 · 站 C · E1）

## 结论（一句话）

**差异不是"格式开销 ~2%"，而是 `+47.5% / +50.8%`** —— 同一镜像、同一 ctx/槽/MTP、同一探针，只换 checkpoint：

| 档 | **BYO GGUF**（`UD-IQ4_XS`, 4.25 bpw） | **v2 `.hgn`**（4.16 bpw） | 比 |
|---|---|---|---|
| 短 ≈560 tok decode | **39.42** t/s（36.95/40.86/40.44） | **58.16**（54.06 / 61.83 / 58.59） | **1.48×** |
| 长 ≈4.1k tok decode | **35.97**（35.14/35.60/37.16） | **54.25**（54.30 / 51.92 / 56.53） | **1.51×** |
| prefill 短 | 860–970 | 1010 / 1395 / 1360 | +30~45% |
| prefill 长（≈4.1k） | 1698–1725 | 1988 / 1988 / 1998 | **+16%** |
| 驻留权重 | **72.0 GiB** | **62.1 GiB** | **−13.7%** |
| 接受率（draft） | 0.49–0.57 | 0.57–0.60 | 同区间 |

**v2 的 58.16 / 54.25 与官方 README 的 prose 54 t/s 吻合**（官方 73 = code、94 = 重复输出，均属其他 workload）。

## 冻结项（除 checkpoint 外全部一致）

- 镜像 `halogen-flash-server:0.18.13@sha256:2e98dc53…`（同一 digest）
- `context=262144` · `kv_pool_positions=524288` · **4 槽** · `max_tok=32768` · MTP `drafter 1`
- `reasoning_effort_default=xhigh` · `enable_thinking=false`（响应 `reasoning_tokens=0` 已验）
- 探针 `probe_halogen.py`（= P1 `probe.py` 同逻辑）· temp 0 · 每档 3 次 · `max_tokens=128`
- 站 C · 单流 · 无并发

## v2 的三个**隐含依赖**（换 checkpoint 时才会暴露，都必须随档记录）

1. **不自包含**：v2 必须配 `qwen38-flash-next-ngram.hgn`（47.68 GiB）在**同一目录**，否则启动被拒 ——
   逐字：`does not carry the model's lookup table, and qwen38-flash-next-ngram.hgn is not beside it`。
2. **需要 tokenizer**：引擎要求在 `/models` 下有 `tokenizer/`，或 `HALOGEN_TOKENIZER` 指一个**扁平** dir ——
   逐字：`no tokenizer.json in /tokenizer`。本次**借用 GGUF 目录里的 `tokenizer/`**（`-v …:/gguf:ro` + `HALOGEN_TOKENIZER=/gguf/tokenizer`），
   `/health.chat_template` = `/gguf/tokenizer/chat_template.jinja`。
3. **不需要 quality overlay**：`overlay: none needed (this checkpoint carries its own trunk precision)` ——
   与 w4b 时代需要 `.overlay.hgn` 不同。

## 为什么快 50%（**不追成定论**，只列可核事实）

- bpw 只差 0.19（4.25 → 4.16）⇒ **不足以解释 1.5×**，所以不是"位宽"。
- 两者**布局不同**：GGUF 走 llama.cpp tensor 布局再 repack（trunk = Q8_0 混 IQ4_XS，日志 `q8s32 502 / q4cp 43`）；
  v2 是引擎**自有精度与布局**（日志：`carries its own precision choices`）。
- 驻留权重 72.0 → 62.1 GiB（−13.7%）⇒ 每 token 读的字节更少，与带宽 bound 的方向一致。
- ⚠ **未做**：逐张量位宽对比、kernel 级 profile。**"自有布局的 MMA 更贴合"只是假设，没有测。**

## 复跑方式

```bash
# 起 v2（表与 checkpoint 同目录；tokenizer 借用 GGUF 目录）
sudo docker run -d --name halogen-v2 --device /dev/kfd --device /dev/dri \
  --group-add 44 --group-add 992 --ipc=host --ulimit memlock=-1:-1 \
  -p 127.0.0.1:8080:8731 -p 127.0.0.1:8731:8731 \
  -e HALOGEN_API_PORT=8731 -e HALOGEN_CHECKPOINT=/hgn/qwen38-flash-next-v2.hgn \
  -e HALOGEN_TOKENIZER=/gguf/tokenizer \
  -v /data/models/hgn/peonist-ai/halogen-qwen3.8-flash-next:/hgn \
  -v /data/models/gguf/lmstudio-community/Qwen3.8-Flash-Next-GGUF/UD-IQ4_XS:/gguf:ro \
  ghcr.nju.edu.cn/peonist-ai/halogen-flash-server:0.18.13@sha256:2e98dc53ed4a43b5600b11a80852eedfa573f4ffc3f10c64da01245f2a3217fc
```

## 证据

`v2c_health.json` · `v2c_startup.log` · `v2c_probe_420.txt` · `v2c_probe_3300.txt`
（前两次失败：`v2_startup.log` = 缺 ngram 表；`v2b_startup.log` = 缺 tokenizer）

---

## 追加：MTP 投机调参矩阵（2026-10-25 · 同站 · 每臂重启后测，各 3 次）

问题 = "当前配置是否最快"。三臂只改投机参数：`A0` 默认（自适应、gate 0.90）· `A1` 强制 `HALOGEN_MTP_DEPTH=3` · `A2` 放宽 `HALOGEN_MTP_GATE_P=0.80`。

| 档 | A0 默认 | A1 depth=3 | A2 gate=0.80 |
|---|---|---|---|
| 短 420 | 55.27（51.6–57.8）· acc 0.53 | 51.63（50.3–53.8）· acc 0.39 | **56.03**（55.2–56.7）· acc 0.54 |
| 长 3300 | 53.31（50.9–54.6）· acc 0.56 | 60.58（**47.1–86.6**）· acc 0.48 | 55.13（53.2–58.1）· acc 0.56 |
| prefill 420 / 3300 | 1256 / 1992 | 1278 / 1997 | 1273 / 2000 |

**判读**

- ★ **A1 不能作为默认**：长 prompt 均值最高（60.58）但**区间 47.1–86.6**（同臂内极差 1.8×），且短 prompt **反而更慢**（−6.6%）⇒ 这是"有时很快"的配置，不是"稳定更快"。
- ★ **A2 的 +0.8 / +1.8 t/s（≈+1.4% / +3.4%）落在噪声带内**（同臂 3 次的极差本身就有 6%）。
- ⇒ **默认（自适应 + gate 0.90）就是当前的稳定最优点**；没有任何一臂给出"可安全采纳"的提速。
- ⚠ 与上一节 v2c 读数（58.16 / 54.25）的差异同属 ±6% 轮间波动 ⇒ 两批合并看：**短 ≈56–58 · 长 ≈54**。
- 已把容器**恢复为 A0 默认**（`RESTORED_BASELINE`），矩阵臂不留在生产位上。

---

## 追加：(a) 512-token 输出复核 + (b) 1M YaRN/KV8（2026-10-25 · 同站 · v2 配方）

### (a) 128-token 窗口有没有高估？—— 没有

同配方（v2 + MTP 默认 + 262k ctx + bf16 KV），只把 `max_tokens` 从 128 改成 512：

| 档 | 128 tok（`v2c_probe_*`，基线） | 512 tok（`longout_*_512`） | 差 |
|---|---|---|---|
| 短 420 | 58.16（54.1 / 61.8 / 58.6）· acc 0.60 | 57.99（55.0 / 57.8 / 61.1）· acc 0.58 | **−0.3%** |
| 长 3300 | 54.25（54.3 / 51.9 / 56.5）· acc 0.57 | 56.08（53.4 / 54.8 / 60.0）· acc 0.57 | **+3.4%** |

- 两档差都落在矩阵已经量到的 ±6% 轮间带内 ⇒ **128-token 窗口没有高估**；58.16 / 54.25 可继续当基线用。
- 512 这两组都是 **run3 > run2 > run1 单调上升**（55.0→57.8→61.1；53.4→54.8→60.0），128 组（每次 2.5–4.5 s）没有这个爬坡 —— 更长的一次 decode 让 GPU 时钟爬满。若有偏差，128-token 是**略偏保守**的那一端。
- 接受率两档几乎不变（0.58 / 0.57 vs 0.60 / 0.57）⇒ 差异不是投机命中率引起的。

### (b) 1M YaRN + KV8：能力换速度

配置实测（`yarn_health.json` / `yarn_startup.log`，非推断）：

| 项 | 默认 | 1M YaRN + KV8 |
|---|---|---|
| `context` / `slot_ctx` / `kv_pool_positions` | 262,144 / 262,144 / 524,288 | **1,048,576 / 1,048,576 / 1,048,576** |
| `kv_cache` | bf16 | **int8**（16,712 B/position） |
| `rope_scaling` | 无 | **static YaRN ×4**（over native 262,144；attention scale 1.138629） |
| `max_tok`（日志口径） | 32,768 | **16,384**（`HALOGEN_MAX_TOK 32768 is capped at 16384 here`） |
| 常驻 | 62.1 权重 + 14.4 KV + 12.5 工作 = **89.0 GiB** | 62.1 + **16.3** + 8.0 = **86.4 GiB** |
| 槽 | 4 槽 / 524,288 池 | 4 槽 / **一个** 1,048,576 池 |

**速度**（128-token 窗口，与默认同探针）

| 档 | 默认 | YaRN/KV8 | 差 |
|---|---|---|---|
| 短 420 | 58.16 | 55.08（51.4 / 57.2 / 56.7）· acc 0.58 | −5.3%（中位 56.65 ⇒ −2.6%） |
| 长 3300 | 54.25 | 58.82（**69.5** / 52.3 / 54.6）· acc 0.61 | +8.4%（中位 54.61 ⇒ +0.7%） |
| prefill 420 / 3300 | 1010–1395 / 1988–1998 | 1029–1404 / 1993–2017 | 无变化 |

- ≤4k prompt 上 decode 与 prefill **都在噪声带内**；3300 那档均值被 run1 的 69.5（acc 0.72）拉高，按中位数只 +0.7%。
- ⚠ 这是**三项一起换**（ctx ×4、YaRN ×4、KV bf16→int8）的同档测量，**不是"YaRN 单独成本"的受控实验**；不要把 −5.3% 归给 YaRN。

**长 ctx 实测**（needle：标记埋在 prompt 开头，再在末尾追问）

| prompt_n | hit | prefill t/s | wall | 说明 |
|---|---|---|---|---|
| 131,404 | ✅ `ZQX-2149` | 1855.6 | 71.2 s | 原生窗口（262k）的一半 |
| 349,907 | ✅ `ZQX-FF96` | 1627.1 | 215.9 s | 已越过原生 262k |
| **898,899** | ✅ **`ZQX-D5E4`** | **1441.5** | 625.9 s | **窗（1,048,576）的 86%** |

- prefill 随长度缓降：131k → 350k → 899k = 1855.6 → 1627.1 → 1441.5 t/s（**−12.3% / −22.3%**），**没有悬崖**。
- ★ 结论成立：**1M 窗口是可用能力**（899k prompt 仍能正确取回开头埋的标记），不是"开得起来但读不进去"。
- 代价明确：`max_tok` 上限腰斩到 16,384、KV 必须 int8（池 16.3 GiB）。

**射程**：单站单流 · needle 是检索冒烟测试不是质量基准（temp 0、每个长度 1 次、答案就是原样复述标记） · 未测**满窗 1,048,576**（最高只到 898,899）· 未测并发多槽 · 未测 KV8 的精度损失与静态 YaRN 的短文本质量（下游质量另测）。

证据：`longout_420_512.txt` · `longout_3300_512.txt` · `yarn_health.json` · `yarn_startup.log` · `yarn_probe_420.txt` · `yarn_probe_3300.txt` · `yarn_needle_150k.txt` · `yarn_needle_400k.txt` · `yarn_needle_900k.txt` · `yarn1m_health.json` · `yarn1m_startup.log`（探针 = [`o138_needle.py`](../o138_needle.py)）

---

## 追加：v2 **自包含**验证 —— 不挂 GGUF 也能跑（2026-10-25 · 站 C · E1）

> 动因：退役 GGUF 的前置问题是「v2 是否还依赖 GGUF 目录」—— 此前的配方把 GGUF 目录挂在 `/gguf`，tokenizer 借的是它，**MTP head 也在它里面**（GGUF 档日志逐字 `draft head /models/qwen38-flash-next-mtp.hgn (1.5G)`）。

**做法**：把 `tokenizer/`（**22 MB**）复制到 `/data/models/hgn/peonist-ai/qwen38-flash-next-tokenizer`；容器**只挂** `/hgn` + 该 tokenizer 目录（`:ro`），**完全不挂 GGUF 目录**，其余配方不变。

| 项 | 读数 |
|---|---|
| `/health` | `context=262144` · `kv_pool=524288` · `checkpoint_format=hgn` · `chat_template=/tokenizer/chat_template.jinja` · **`drafter_weights_loaded=true`** · `drafter_default=mtp` |
| 启动日志 | **无 `draft head` 行**（GGUF 档有）· lookup table = `/hgn/qwen38-flash-next-ngram.hgn` · 常驻 **89.0 GiB** |
| decode 420 | **56.02**（57.14 / 57.05 / 53.87）· acc 0.56 · `drafter=mtp` |
| decode 3300 | **56.75**（54.70 / 59.72 / 55.83）· acc 0.63 · `drafter=mtp` |
| 对照（挂 GGUF 的默认档） | 58.16 / 54.25 ⇒ **−3.7% / +4.6%**（噪声带内） |

★ **结论**：v2 的运行时依赖只有三样 —— `qwen38-flash-next-v2.hgn` · 同目录的 `qwen38-flash-next-ngram.hgn` · **一个 tokenizer 目录（22 MB）**。**GGUF 目录不再是 v2 的运行依赖**，MTP head 由 checkpoint 自带（无需那 1.5 GiB 的 `qwen38-flash-next-mtp.hgn`）。

证据：`nogguf_health.json` · `nogguf_startup.log` · `nogguf_probe_420.txt` · `nogguf_probe_3300.txt`（容器已恢复默认 A0）

