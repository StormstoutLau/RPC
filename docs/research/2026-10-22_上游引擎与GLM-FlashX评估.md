# 上游引擎与 GLM-5.3-Flash-X 评估（2026-10-22）

- **日期**: 2026-10-22
- **性质**: **调研 + 评估**（spec workflow 的"取证 + 判定"段）
- **对象**: ① 台账仍开的待办项 · ② llama.cpp 上游 delta（现役 `master-23b0202a` → HEAD `e197cef4`）· ③ halogen-flash-server `0.18.11` → `0.18.13` · ④ GLM-5.3-Flash-X 是否值得部署替换本地 GLM-5.3-Flash
- **射程**: **不改任何站上配置、不改代码、不改镜像 pin**；本文只给取证、判定与候选动作
- **证据等级**: E1 本次实测（GitHub API / 镜像仓库 / HF 镜像 API）· E3 外部一手（上游 CHANGELOG / OpenRouter API）· E4 推断（显式标注）
- **上游 PR 状态单一真值**: [spec/upstream-tracker/TRACKER.md](../../spec/upstream-tracker/TRACKER.md)（本文只引用，不另维护一份）

---

## 0. 一屏结论

| # | 问题 | 结论 | 建议动作 |
|---|---|---|---|
| 1 | **其他待办事项** | 台账仍开 **5 项**：`O-86`（等下游 U-1 迁移）· `O-138`（扫描已落，待按 P1 起）· `O-141`（P1/P2/P0 已落，P3 设计段已落）· `O-147`（乙+丙已落，余项已收口）· `O-148`（策略 + runbook + R7 已落） | 均**不阻塞**当前工作；逐项见 §1 |
| 2 | **llama.cpp 是否需要更新** | 现役 `23b0202a`（10-12）→ 上游 HEAD **`e197cef4`**（10-22T07:06Z）= **261 提交**，`behind_by=0`；**无 revert 命中我方**；但**无"必须升"的头部收益**（`-sm tensor` 根因无修复、GLM 换档门依旧） | **可升，但先影子 A/B（不切 symlink）**；权重 > 0 再排窗口（同 EV-13 手法） |
| 3 | **halogen 是否需要更新** | ✅ **已升级到 0.18.13（2026-10-22）**：0.18.12/13 均**未改 Flash checkpoint**、**temp=0 逐字节一致**；0.18.12「prompts 每个长度都更快」+ cache staging；0.18.13 流式拼接/短请求嵌套默认开 + NPU 故障不再拖垮容器 | **已完成**：新 pin `2e98dc53…` + 三站重建 + `/health` + greedy 冒烟 + `engine` 门禁 PASS；★ A/B：0.18.12 prefill 冷 8k/32k **未复现**（噪声内），0.18.13 短请求 TTFT **15.77→0.80 s**、流式中断 **15.96→0.85 s**（代价长 prompt prefill **+8.9%**）；详见 §3.3 |
| 4 | **GLM-5.3-Flash-X 是否值得部署替换本地 GLM-5.3-Flash** | **无开放权重 ⇒ 不可本地部署**：HF 镜像 `search=flashx` **0 条**、`search=glm-5.3` 前 100 条无 X 变体；只有 OpenRouter/云 API（`z-ai/glm-5.3-flashx`，1,048,576 ctx，$0.37/$1.25 per 1M） | **无替换对象**；如要更快 GLM，路径 = 主线引擎 + MTP（#29928）+ `glm5-next` 档（EV-11），不是 FlashX |

---

## 1. 待办盘点（只读台账）

来源：[OPEN-ISSUES.md](../../spec/d6-agent-standard/OPEN-ISSUES.md)。当前仍开 4 项（`O-147` 已于 2026-10-22 闭环），其余已闭环。

| 项 | 状态 | 下一步 / 卡点 |
|---|---|---|
| **O-86** | ⏳ 待触发 | **等下游 `U-1` 迁移落到 `Auto_Prover`**；本仓无可执行项。触发时先做下游收敛（`verdict_id` 3 处 → 1、`case_id` 2 套 → 1）再切 U-1 |
| **O-138** | ◐ P1 已执行（2026-10-22） | **P1 已完成**：C 站 Vulkan decode **27.55 / 26.85 t/s**（0.56k / 4.1k tok），详见 [metrics-log Phase 14](../../spec/rpc-optimization/metrics-log.md)；下一步 = C fallback 试 `N_CPU_MOE=0` @ 262k |
| **O-141** | ◐ 部分已落 | **P1/P2/P0 已落、P3 设计段已落**（[PROOF-STATE-GRAPH.md](../../spec/d6-agent-standard/PROOF-STATE-GRAPH.md)）；**下一步 = P3 实施段**，前置 = `Auto_Prover` 拿到**第一个真实形式化输入**（仍未满足） |
| **O-147** | ✅ **闭环（2026-10-22）** | 乙+丙、R7、X2、`EGRESS_PICK` 均已落；服务端 `free_model_daily_requests` **维持巡检/对账，不接派发闸门**（ADR-0003 点 2：分钟级延迟）；`FREE_QUOTA_PAID`（零消费者）已删除，R1-⑨ 防复活 |
| **O-148** | ⏳ 间歇 · 策略已定 | **处置策略 + runbook + R7（探针失败 ⇒ 降级 B 并留痕）已落**；**仅剩候选①「站上常驻加密解析」** = 动站上配置，**须显式点头**；当前无发作可复现，纪律仍是"先复现再改" |

> 结论：**O-147 已于 2026-10-22 闭环；其余四项**均为"等外部条件 / 待单独授权"，不构成本轮动作项。

---

## 2. llama.cpp 上游 delta

### 2.1 基线（E1）

| 项 | 值 | 取数 |
|---|---|---|
| 现役 | **`master-23b0202a`**（2026-10-12 升级） | [TRACKER §2.4](../../spec/upstream-tracker/TRACKER.md) |
| 上游 HEAD | **`e197cef4`**（2026-10-22T07:06:47Z「vocab : use Tekken pre-tokenizer for pixtral … (#30960)」） | `gh api repos/ggml-org/llama.cpp/commits/master` |
| 距离 | **`ahead_by=261` · `behind_by=0` · `total=261`** | `gh api …/compare/23b0202a...master` |
| revert | **无一条命中我方**（Vulkan / RPC / MoE / AMD-HIP） | 逐批核对（E1） |

### 2.2 命中我方的合并项（261 提交内，均已 Merged）

| PR | 标题（节选） | 合并 | 为什么相关 | 轴 |
|---|---|---|---|---|
| **#27703** | vulkan : copy strided f16 KV once on AMD so reads spread across memory channels | 10-15 | **decode 内存带宽墙**（我们最贵那条） | `/opt` Vulkan RPC |
| **#29741 + #30468** | vulkan: allow multiple devices to access gpu-visible host memory（+ fix issues） | 10-13 / 10-16 | 多设备 / RPC 的 host-visible 内存路径 | `/opt` Vulkan RPC |
| **#29533** | vulkan : split matmul dispatch when it would exceed maxComputeWorkGroupCount | 10-13 | **dispatch 维度超限**（GLM indexer 同族坑） | `/opt` Vulkan |
| **#30514** | kv-cache: honor PARTIAL_ONLY in the plain KV cache | 10-15 | 长 ctx / KV 复用 | 两轴 |
| **#29677** | model: fix "invalid vector subscript" when loading on a full GPU | 10-14 | **满 GPU 加载**（RPC 层切分） | `/opt` Vulkan RPC |
| **#30481** | ggml : improve RPC tensor transfer logs | 10-14 | RPC 排障可观测性 | `/opt` Vulkan RPC |
| **#30480 / #30613** | k-pool selection 因果掩码布局 / 跨层共享 k-pool 输入视图 | 10-14 / 10-16 | ⚠ **与 GLM 稀疏 indexer 同族（E4）**；只对**主线 `glm5-next`** 有意义 | 主线 GLM |
| **#30861** | llama : scale moe down projection per expert token | 10-21 | MoE（V4-Flash / GLM）数值路径 | 两轴 |
| **#30823** | qwen: reshape output to 2d instead of 3d | 10-20 | Qwen 系（Qwen3.8-27B / Flash-Next） | 单站 / 两轴 |
| **#28195** | HIP: use 64-row MMQ tiles for some quant types on RDNA3.5 | 10-14 | **仅 studio/HIP 单站轴**，`/opt` Vulkan 升级买不到 | HIP 单站 |

### 2.3 风险 / 在跟踪项

| 编号 | 标题（节选） | 状态（E1，10-22） | 判读 |
|---|---|---|---|
| **#30547** | vulkan: slower prompt processing with multi-device + cpu-moe MoE after #29741 | **Closed completed（10-16）** | ★ **上批的回归风险解除**；且我方 `--n-cpu-moe 0`，本就不命中 |
| **#30568** | Vulkan (Strix Halo gfx1151, **Windows**): MTP 吞吐在 `--spec-draft-n-max 4` 相对 3 腰斩 | Open | **仅 Windows**；三站 Linux ⇒ 不命中（**E4：未在本集群实测**） |
| **#29950** | GLM-5.3-Flash increased VRAM usage after PR#27773 | Open | 上主线 GLM 前**须核显存** |
| **#30093** | glm5-next + `--spec-type draft-dflash` 首请求 abort | Open | 主线 GLM + DFlash 路径风险 |
| **#30499** | meta: support GLM-5.3 next sm tensor | Open | 张量切分对 GLM 仍不可用 |
| **#30932** | glm5 : optimize inputs | Open | 主线 GLM 增量，未合 |
| **#30927** | model : fix qwen4exp layer inputs for DFlash drafters | Open | Qwen3.8 MTP/DFlash 路径，未合 |
| **#30277** | meta : enable tensor split for KDA hybrid models | **Closed 未合并（10-20）** | §1.4「GLM 天然不适合张量切分」旧判**维持** |

### 2.4 判定

1. **技术上可升**：无 revert 命中我方面，SOP 通道（codeload → 构建 → `patchelf $ORIGIN` → MANIFEST → 分发）10-12/10-16 已两次实战验证。
2. **但本轮没有"必须升"的头部项**：`-sm tensor` 的加载期 SIGSEGV 根因在上游**仍无修复**；GLM 的 arch 串换档门也**不由引擎升级解决**。
3. **收益预期应保守**：上一批 118 提交的影子 A/B（EV-13）实测 **decode/prefill 均在噪声内、净收益 ≈ 0**（[metrics-log Phase 9](../../spec/rpc-optimization/metrics-log.md)）。本批虽有 `#27703`（KV 带宽）与 `#30861`（MoE），但**没有理由假定会翻盘**。
4. **行动建议**：按 **EV-14** 做影子 A/B：
   - 候选 commit = `e197cef4`，**不切 symlink**；
   - 同 alias、同 `-sm layer`、conf 快照/恢复；
   - **prefill 用随机 prompt ×7**（防 prefix cache 把 `prompt_n` 塌成 4）；
   - decode / prefill / 加载时间 / 输出一致性 / 零 assert 五项判据；
   - 权重 ≤ 0 ⇒ 维持 `23b0202a`，不排窗口。

---

## 3. halogen 0.18.13 评估

### 3.1 版本与 digest（E1）

| tag | manifest digest | 说明 |
|---|---|---|
| **0.18.11** | `sha256:a5797467d2bff173e0c661d9700292bd55eac305faff68c86261ae35385ad6ad` | **升级前**（曾为现役 pin） |
| **0.18.12** | `sha256:b6403f1d07e22b719fb23d131d16d1ea27650da414dfaff734cfdd4fe18b9ba2` | 中间版（未部署） |
| **0.18.13** | `sha256:2e98dc53ed4a43b5600b11a80852eedfa573f4ffc3f10c64da01245f2a3217fc` | **曾为现役**（2026-10-22 → 10-29；created 2026-10-20T23:05Z） |
| **0.18.18** | `sha256:d6cb2a7d20211da675cd1f104a02f4bf4cb60e29afffbaadf8b0d495d332cc8a` | ✅ **现役**（2026-10-29 升级；上游 0.18.14–0.18.18，含 #204 queued-cancel、#212 /metrics 抓取拖慢短请求、#214 断连暂停占槽、#216 `</tool_call>` 截断） |

> **未单独取证的版本**：0.18.14 / 0.18.15 / 0.18.16 / 0.18.17 未单独部署，也未逐个取 manifest digest（本轮直接由 0.18.13 → 0.18.18）。0.18.18 的 digest 已与 `ghcr.io` 上游**逐字节一致**（南大镜像无改写）。

取数：`ghcr.nju.edu.cn/v2/peonist-ai/halogen-flash-server/manifests/<tag>` 的 `Docker-Content-Digest`。升级前 0.18.11 的仓库 digest 与旧 pin **逐字一致**；升级后 0.18.13 的仓库 digest 与新 pin **逐字一致** ⇒ 两次均未漂移。

### 3.2 CHANGELOG 要点（E1，上游 `CHANGELOG.md` 实读）

- **0.18.12**：
  - **「Prompts process faster at every length」**（两个 checkpoint 均更快）；
  - `HALOGEN_CACHE_STAGE=2` 默认（pinned staging buffer，减 host 搬内存导致的 GPU 队列停摆）；
  - 图像编辑支持 1–4 图；新增 `halogen:gpu_queues_evicted_seconds_total`；
  - **Flash checkpoint 不变 · temp=0 逐字节一致于 0.18.11**。
- **0.18.13**：
  - **流式回复在另一请求的长 prompt 读入时继续走**：`HALOGEN_ADMIT_SPLICE_MS=500`（默认，`FOR=all`）；长 prompt 首 token 约晚 5–7%，其它回复最长停顿从 18–22 s 降到约 1 s；
  - **短请求嵌套**：`HALOGEN_ADMIT_NEST=1`（默认，`MAX=1024` 新 token）；多占约 **0.33 GiB pinned host + 32 MiB GPU**；
  - NPU 故障不再拖垮容器（503 + 自动重启，`HALOGEN_NPU_RESTARTS=3`）；
  - **Flash checkpoint 不变 · temp=0 逐字节一致于 0.18.12**。

### 3.3 判定

**建议升级**，理由三条：

1. **风险低**：两个版本都声明 Flash checkpoint 不变、temp=0 逐字节一致；镜像 config 也确认 `HALOGEN_IMAGE_VERSION=0.18.13`、`HALOGEN_ARCH=gfx1151`。
2. **有实际收益面**：0.18.12 上游称「prompts 每个长度都更快」（★ **本集群冷 8k/32k 未复现**，见下）；0.18.13 的 splice/nest 对**多客户端并发**（claude code + opencode + 批处理）有公平性收益。⚠ 我方每站策略是**单引擎、通常单流**（`O-18`），所以 splice/nest 只在**真并发**时兑现 —— 本轮 A/B 已证实该收益**量级很大但有代价**。
3. **升级成本可控**：换 tag/digest → `docker pull` → 重建容器 → `/health` + 冒烟 + `rpc_check --only engine`（digest 漂移检查自动跟随新 pin）。

**执行结果（2026-10-22 · E1）**：

1. ✅ `CONTAINER_MODELS["qwen3.8-flash-next"]["image"]` 改为 `…:0.18.13@sha256:2e98dc53…`；
2. ✅ 三站后台 `docker pull` 新 digest（4.56 GB），落盘后 `docker image inspect` 三站均命中新 digest；
3. ✅ 逐站重建（B → A → C，复用 `_load_container_model` / `containers_plan("up")`）：三站 `/health` = `status:ok`、`version.api=engine=0.18.13`、`context=262144`、`kv_pool_positions=524288`、`prompt_cache.mode=2`；
4. ✅ 同一 greedy 请求（`enable_thinking=false`，`max_tokens=32`）三站均返回 `PONG`、`usage=18/3` 一致；`py -3 ops\rpc_check.py --only engine` **PASS**（含 digest 漂移判定）；
5. ✅ ADR-0014 新增 **§V6.2** 并记入修订历史（v2.2）；回滚 = 改回 `0.18.11@a5797467…` 后逐站 `load` 重建。

**定量 A/B（2026-10-22 · C 站单站 · E1）**：同 checkpoint / 同配方，冷 8k/32k prefill ×3 + 并发公平性 ×2。
- **0.18.12 的 prefill 提速未复现**：冷 8k/32k 相对 0.18.11 仅 **+0.3% / +0.6%**，与 0.18.11 末次复测的漂移（+0.05% / +0.24%）同量级 ⇒ **噪声**。
- **0.18.13 的并发公平性可复现**：短请求 TTFT **15.77 → 0.80 s（≈19.8×）**；流式最大中断 **15.96 → 0.85 s（≈18.8×）**；关闭 splice/nest 后回到 **15.78 / 16.04 s** ⇒ **归因成立**。
- **代价**：并发时长 prompt prefill **16.00 → 17.42 s（+8.9%）**（上游称 5–7%）。
- 完整表格与射程（仅 C 站 / 冷 8k/32k / `enable_thinking=false`）见 [ADR-0014 §V6.2](../../adr/ADR-0014-halogen引擎引入与容器写动作扩权.md#v62-实证--镜像升-01813-2026-10-22--e1)。原始 JSONL / probe / analysis = [spec/rpc-optimization/ab-halogen-20261022](../../spec/rpc-optimization/ab-halogen-20261022/)。

---

## 4. GLM-5.3-Flash-X 评估

### 4.1 它是什么（E3）

- **API-only 高速服务变体**：OpenRouter 上架 `z-ai/glm-5.3-flashx`，context **1,048,576**，价格 **$0.37 / $1.25 per 1M tokens**（E1：OpenRouter `/api/v1/models` 实读 `0.00000037 / 0.00000125` per token）。
- 第三方汇总（CloudPrice，E3）：320B/18B、1M ctx、131K output、2026-09-18；provider = OpenRouter / Tencent / Vercel。
- 同页还有 `z-ai/glm-5.3-flash`（hosted Flash），说明 **Flash 与 FlashX 是两个服务档**，不是同一份权重的两种量化。

### 4.2 无开放权重（E1）

| 检查 | 结果 |
|---|---|
| HF 镜像 `api/models?search=flashx` | **0 条** |
| HF 镜像 `api/models?search=glm-5.3&limit=100` | 100 条，**无任何 `flashx` / `flash-x` 变体**；可见 `zai-org/GLM-5.3-Flash-BF16`、`unsloth/GLM-5.3-Flash-GGUF`、`nvidia/GLM-5.3-Flash-*` 等 |
| 结论 | **FlashX 没有可下载权重** ⇒ **无法在本集群部署** |

### 4.3 与本地 GLM-5.3-Flash 的关系

- 本地现役：`unsloth/GLM-5.3-Flash-GGUF` 的 `UD-IQ4_XS`，**146.1 GiB 单文件** ⇒ RPC 双机 `-sm layer`；引擎 = `/opt/llama.cpp-glm5next-20260928` 变体（`--engine glm5next-20260928`），权重在 B 站（[cluster_const.py](../../ops/cluster_const.py)）。
- **FlashX 不是这份权重的"更快版本"**：它是**另一个服务形态**，没有本地制品 ⇒ **不存在"替换"动作**。
- 如果目标是"本地 GLM 更快"，现有路径只有：
  1. **换主线引擎 + 换一份 `glm5-next` 档**（EV-11，arch 串门）；
  2. **启用主线 MTP**（#29928 已 Merged 10-07）；
  3. 升级前先核 **#29950 的 VRAM 增**、**#30093 的 dflash abort**。
- 如果目标是"用 FlashX 的吞吐"，只能走 **API 出网**（`ADR-0003` egress）；⚠ 只对 `public`/`sanitized` 内容开放，`local-only` 不得出网。成本/质量**未在本仓实测**。

---

## 5. 待裁事项

| # | 事项 | 建议 |
|---|---|---|
| **D1** | 是否升级 halogen 到 **0.18.13** | ✅ **已执行（2026-10-22）**：三站已重建到 0.18.13、`/health` + greedy 冒烟 + `engine` 门禁 PASS；详见 §3.3 |
| **D2** | 是否排 llama.cpp **影子 A/B**（`e197cef4`，261 提交） | **建议排，但不紧急**；按 EV-14 做，权重 ≤ 0 就维持现役 |
| **D3** | 是否引入 **GLM-5.3-Flash-X** | **不做**：无开放权重，不可本地部署；如需 API 版另评成本/内容闸 |

---

## 6. 本调研**没做**的事（诚实边界）

- **已做**：拉取并运行 0.18.13、三站重建、正确性/可用性验证（§3.3）；**未做**其 prefill/并发收益的定量 A/B（收益数字仍来自上游 CHANGELOG 的声明）。
- **没有**为 261 提交做影子 A/B（只做了状态核对与风险筛查）。
- **没有**独立核 CloudPrice 的 320B/18B 参数与 131K output（E3 二手）。
- **没有**实测 OpenRouter FlashX 的延迟/质量/限额，也未核算与本地电费的成本对比。
- **没有**验证上游 tag 是否会被重推（只验证了当前 digest 与 pin 一致）。
- **已改**：`CONTAINER_MODELS.image` 的 pin（0.18.11 → 0.18.13）+ ADR-0014 §V6.2；**未改**任何其它站上配置或代码。

---

## 7. 引用

- 上游 PR 状态真值：[spec/upstream-tracker/TRACKER.md](../../spec/upstream-tracker/TRACKER.md)（§1.1 / §1.5 EV-14 / §2.4）
- 引擎升级 SOP：[UPGRADE_SOP.md](../../spec/vulkan-version-control/UPGRADE_SOP.md)
- 影子 A/B 先例：[metrics-log Phase 9](../../spec/rpc-optimization/metrics-log.md)
- halogen 上游变更：[CHANGELOG.md](https://github.com/peonist-ai/halogen-flash-server/blob/master/CHANGELOG.md)
- halogen 镜像标签：`https://ghcr.nju.edu.cn/v2/peonist-ai/halogen-flash-server/tags/list`
- OpenRouter 模型与价格：`https://openrouter.ai/api/v1/models`
- HF 镜像检索：`https://hf-mirror.com/api/models?search=flashx` · `…?search=glm-5.3&limit=100`
- 容器模型配方：[ops/cluster_const.py](../../ops/cluster_const.py)（`CONTAINER_MODELS`）
- 容器引擎 ADR：[ADR-0014](../../adr/ADR-0014-halogen引擎引入与容器写动作扩权.md)
- 出网治理：[ADR-0003](../../adr/ADR-0003-OpenRouter密钥与egress路由管理.md)
- 待办台账：[OPEN-ISSUES.md](../../spec/d6-agent-standard/OPEN-ISSUES.md)
