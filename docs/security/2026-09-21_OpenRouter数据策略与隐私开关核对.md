# OpenRouter 数据策略与隐私开关 —— 核对与实测（P1，2026-09-21）

> **状态：核对完成，已产生一项代码改动（sanitized 硬闸）与两项登记。**
>
> **结论先行**
> 1. **三个开关都不可机读**：`/api/v1/key` 不含隐私开关；`is_management_key=false` ⇒ 无管理 API 权限；`/api/v1/settings`、`/api/v1/privacy` 实测 **404**（无此端点）。**唯一**可机读的隐私相邻字段是 `allowed_data_regions: ["global"]`。
> 2. **A 站账号「Allow free endpoints that train on request data」= 开**（用户读 dashboard 确认）。这与"`/models/user` 对 21 个 `:free` 型号**零过滤**"以及"`:free` 请求能跑通"两条机读证据**一致**。
> 3. **免费档的代价被实测量化**：备路型号 `nvidia/nemotron-3-ultra-550b-a55b:free` 无偏好 **200**，一加数据策略约束即 **404 `No endpoints found matching your data policy (Free model training)`**；加 ZDR 亦 **404 `(Zero data retention)`** ⇒ **该型号全部免费端点都训练、且都不满足不保留**。
> 4. **⇒ 关闭该开关 = `:free` 备路整体失效**（`claude-opus` 备路确证；`claude` 备路为推理，见 §5）。**故本轮决定：先不关**，改为**加 `sanitized` 硬闸**（§6，已实施并双向自证）。
> 5. **付费档有合规端点**（实测 `data_collection:"deny"` 可用；`zdr` 部分型号可用）⇒ "关免费档 + 改走付费"是一条**可行**的备选路。
> 6. **顺带发现**：账户**未完成 18+ 年龄确认** ⇒ Meta 系型号全部 `403`（§8）。

---

## 1. 三个开关（官方定义与默认值）

| # | 开关 | 位置 | 默认 | 官方出处 |
|---|---|---|---|---|
| ① | **OpenRouter Use of Inputs/Outputs**（以日志换 **1% 折扣**） | Settings → **Privacy** | **Off by default** | [Data Collection](https://openrouter.ai/docs/guides/privacy/data-collection/) |
| ② | **Input & Output Logging**（在 OpenRouter 侧存 prompt/completion，仅自己可见，Beta） | Workspaces → **Observability** | **Off by default** | [Input & Output Logging](https://openrouter.ai/docs/guides/features/input-output-logging) |
| ③ | **Allow … providers that train on request data** | Settings → **Privacy** | — | [Provider Logging](https://openrouter.ai/docs/guides/privacy/provider-logging/) |

**③ 的关键结构（易漏）**：官方原文 —— *"There are **separate settings for paid and free models**. … If you opt out of training in your account settings, OpenRouter will not route to providers that train."* ⇒ **付费档与免费档是两个独立开关**，本报告要区分对待。

**① 与 ② 是两件独立的事**（官方明写 "You can enable one, the other, or both"）：① 是**给 OpenRouter 用于改进产品**换折扣；② 是**存给你自己看**、OpenRouter 不使用。

---

## 2. 可机读性核对（实测，2026-09-21）

| 端点 | http | 说明 |
|---|---|---|
| `GET /api/v1/key` | **200** | 27 字段；**不含**任何 `log`/`train`/`privacy` 开关 |
| `GET /api/v1/auth/key` | **200** | 与 `/key` 同构 |
| `GET /api/v1/credits` | **200** | `total_credits` / `total_usage` |
| `GET /api/v1/models/user` | **200** | 见 §3（间接观测面） |
| `GET /api/v1/me`、`/api/v1/user`、`/api/v1/settings`、`/api/v1/privacy` | **404** | 不存在 |

`/api/v1/key` 里**唯一**隐私相邻字段：

| 字段 | 值 | 含义 |
|---|---|---|
| `allowed_data_regions` | `["global"]` | 无 in-region 限制（enterprise 才有） |
| `is_management_key` | `false` | ⇒ **无**管理 API 权限 ⇒ 设置只能从 dashboard 改/读 |
| `is_free_tier` | `false` | 曾充 ≥$10 ⇒ 免费档日限额 **1000**（非 50） |
| `free_model_daily_requests` | `used 13 / limit 1000 / remaining 987` | 服务端权威免费请求计数（分钟级延迟） |
| `creator_user_id` / `workspace_id` | `user_3BqB4sUNPR6fJOcVQQdE0CsKMUr` / `745c278c-…` | 账户身份（用于识别"是否已拆成独立账户"） |

⇒ **诚实边界**：`http=000`（相对路径直接喂 curl）与 `401`（把整文件当 bearer，未按 `cluster.py::probe_egress_master` 取"第一个非注释行"）是本轮踩到的两个**探针自身缺陷**，均已修正；上表为修正后结果。

---

## 3. 间接观测面：`/models/user` 的过滤（把"设置"变成"可观测后果"）

文档称 `/api/v1/models/user` 返回 "filtered by user provider preferences, **privacy settings** and guardrails"。

**实测**：`/api/v1/models` = **446** 个 id；`/api/v1/models/user` = **443** 个。差集 **恰好 3 个**：

| 被滤掉的型号 | 端点数 / status | 下架日期 |
|---|---|---|
| `meta/muse-spark-1.2-contributor` | 1 / status=**0**（可用） | 无 |
| `meta/muse-spark-1.3-contributor` | 1 / status=**0** | 无 |
| `sakana/sakana-namazu` | 1 / status=**0** | 无 |

**竞争解释已排除**：三者端点均 `status=0`（live）、无 `expiration_date` ⇒ **不是"模型下架"**，而是**策略过滤**。其中两个是 Meta 的 "**contributor tier**"（以数据换低价的档位）。

**但**：`meta/muse-spark-1.2`（**非** contributor 的同族付费型号）**仍在** `/models/user` 里，却在请求时同样 `403`（§8 的 18+ 闸）⇒ 说明**"18+ 闸"不是**过滤原因（否则非 contributor 的那个也该被滤掉）。

⇒ **本报告不把"付费档训练开关 = 拒绝"写成已确证事实**，只写成**有旁证支持的推断**（旁证：contributor 档在语义上正是"允许用你的数据"；且 filter 说明文档点名 privacy settings）。要确证仍需 dashboard。

---

## 4. 实测矩阵：免费档 vs 付费档 × 数据策略约束

方法：`POST /api/v1/chat/completions`，只差 `provider` 偏好（`max_tokens=8`）。**A 站 key**。

| 型号 | 档 | 无偏好 | `data_collection:"deny"` | `zdr:true` | `deny+zdr` |
|---|---|---|---|---|---|
| `nvidia/nemotron-3-ultra-550b-a55b:free`（**`claude-opus` 备路**） | 免费 | **200** (Nvidia) | **404** `(Free model training)` | **404** `(Zero data retention)` | **404** |
| `thinkingmachines/inkling:free`（**`claude` 备路**） | 免费 | **403** `only available on agentic harnesses` | 同 | 同 | 同 |
| `mistralai/mistral-nemo` | 付费 | 200 | **200** | **200** | **200** |
| `inclusionai/ling-3.0-flash` | 付费 | 200 | **200** | **200** | **200** |
| `ibm-granite/granite-4.0-h-micro` | 付费 | 200 | **200** | 404 | 404 |
| `meta-llama/llama-3.2-1b-instruct` | 付费 | 200 | **200** | 404 | 404 |
| `meta/muse-spark-1.2-contributor` / `meta/muse-spark-1.2` | 付费 | **403** `18+ age confirmation`（§8） | 同 | 同 | 同 |
| `z-ai/glm-4.5-air:free`、`mistralai/mistral-small-3.2-24b-instruct:free`、`qwen/qwen3-coder:free` | 免费 | **404** `unavailable for free`（已下架） | 同 | 同 | 同 |

**由表得到的三条事实**
1. **免费档 = 全部端点训练、且全部不可 ZDR**（错误串逐字点名 `Free model training` / `Zero data retention`）。
2. **付费档确实有"不存储"端点**（`deny` 四例全 200）；**ZDR 视型号而异**（mistral-nemo / ling-3.0-flash 有，granite / llama-3.2-1b 无）。
3. **免费档型号流动性高**：本轮抽样的 3 个 `:free` 已整体下架 ⇒ 任何"把 `:free` 当稳定依赖"的设计都脆。

---

## 5. 关闭「免费档允许训练」的影响（决策依据）

| # | 影响 | 证据强度 |
|---|---|---|
| 1 | **`claude-opus` 备路型号（nemotron:free）立即不可用** | **实测确证**（§4 第 1 行） |
| 2 | **`claude` 备路型号（inkling:free）大概率一并失效** | **推理**：它是 `403 agentic-harness-only`，裸 API 探不到其策略；但它与 nemotron 共用 BaseTen/DeepInfra 免费端点，而该开关是**账户级**的 |
| 3 | 免费档**连 ZDR 都做不到** | 实测确证 |
| 4 | **1000 次/天 免费额度作废** ⇒ 「三站独立账户 + `egress borrow`」额度调配机制**失去意义**（它管的就是免费额度） | 直接推论 |
| 5 | 要改必须**三个账号分别改**（A/B/C 是三个独立账户，只改一个等于没改） | 架构事实 |
| 6 | ✅ 正向：备路 prompt 不再流向"可能训练/公开发布"的 provider | 目的本身 |
| 7 | `local-only` 不受影响（P0 已不让它出网） | 已实施 |

---

## 6. 本轮决策：**先不关** + **加 `sanitized` 硬闸**（已实施）

**为什么不现在关**：关了备路**立刻**没了，而替代路（[P3 站上化](../research/2026-09-21_D6备路站上化与sensitivity设闸调研与方案.md)）还没建。顺序应是：**先建替代 ⇒ 再关开关**。

**取而代之的"小闸"**（与 P0 同族，已实施）：

| 项 | 内容 |
|---|---|
| 判据 | `Get-SensitivityBackendReject`（`agent-cli.ps1`）扩展为 **sensitivity × 后端属性**，返回拒绝原因 token：`local-only × 会出网 ⇒ local-only+egress`；**`sanitized × 可能训练/发布 ⇒ sanitized+trains`**；`public` 恒放行 |
| 判点 | **两处出网入口都判**：`Invoke-Task-Claude`（直接入口，tag `claude-direct`）+ `AUTO_FALLBACK` 调用点（兜底入口，tag `fallback`，**拒绝兜底** = fail-closed） |
| `backendTrains` 来源 | `$id -match ':free'`（**代理判据**：免费档 = 本账户实测"全部端点训练"的那一档）。⚠ 公开 API 不暴露端点级 `data_policy`（§3 实测），故暂不能直读；P2 应换成按后端属性查表 |
| 依据 | **脱敏 ≠ 同意进公开数据集**：`sanitized` 的定义是"scrub 后允许离开主控"，不等于同意 prompt 进第三方训练语料 |

**双向自证**（4 例 = 2 类 sensitivity × 2 条路径）

| 例 | 场景 | 结果 |
|---|---|---|
| A | `local-only` + `-cli claude` | `REJECT local-only+egress (claude-direct, thinkingmachines/inkling:free)`，rc=4，claude run **不增** |
| B | `local-only` + 站上本地型号 + `AUTO_FALLBACK` | `REFUSED` + `REJECT local-only+egress (fallback, …)`，rc=4，**不增** |
| C | `sanitized` + `-cli claude` | `REJECT sanitized+trains (claude-direct, …)`，rc=4，**不增** |
| D | `sanitized` + 站上本地型号 + `AUTO_FALLBACK` | `REFUSED` + `REJECT sanitized+trains (fallback, …)`，rc=4，**不增** |
| 正 | `public` 卡（原路径） | 兜底触发、证据面 v2、`accept` 在 Git Bash 下 `ACCEPT_RC[1]=0` ⇒ 未被破坏 |
| 变异 | 拆掉 `sanitized` 规则 | **只有 C/D 变红**（rc 4→6 且**真跑出 claude run** = 真出境请求），A/B 仍绿；还原后 sha256 逐字节一致 |

⇒ 变异结果同时证明：**该风险是真实的**（拆掉闸就会真发出请求），且**两条规则各自被独立覆盖**（不是"有个闸在跑"）。

**副作用（诚实记录）**：`sanitized` 卡的 `:free` 备路**现在被拒**。即 sanitized 卡若主路死锁，**不再有云端兜底**，直接 `rc=4`。这是有意的失败关闭；替代路见 §7。

---

## 7. 替代路评估（为"以后关开关"做准备）

| 路 | 合规性 | 代价 |
|---|---|---|
| **站上本地引擎（P3 站上化）** | **全合规**：不出网、不花钱、不训练 | 需实现 P3；站上资源占用待实测 |
| **付费型号 + `provider:{data_collection:"deny"}`** | 合规（实测可用）；ZDR 需选型号 | 花钱；备路型号要换；型号流动性同样存在 |
| 换其他 `:free` 型号 | **不合规**（免费档一律训练） | 无意义 |
| 保持现状（开关开 + 只有 `public` 走备路） | 部分合规 | **本轮选择**：`public` 是唯一无闸档 |

---

## 8. 顺带发现：账户未完成 18+ 年龄确认

请求 Meta 系型号（`meta/muse-spark-1.2`、`meta/muse-spark-1.2-contributor` 等）一律：

```
403 This model requires you to complete the following before use: 18+ age confirmation.
    Confirm at https://openrouter.ai/settings/pref…（截断）
```

- 不影响**现用**备路型号（非 Meta 系），但**挡住未来选型**（本轮本想用 Meta 型号交叉验证 §3 的推断，被此闸挡下）。
- 属**账户配置项**，不是缺陷；已登记。

---

## 9. 诚实边界

- ① 与 ③ 的**实际状态**由**用户读 dashboard** 提供（① 未读；③ 免费档 = **开**）。API 侧**没有**这些开关，本报告的机读结论是"**不可机读**"，不是"读出来是关"。
- **付费档 ③ 的状态未确证**（只有 §3 的旁证 + §8 排除一个竞争解释）；本报告刻意不写成定论。
- **`sanitized+trains` 的 `:free` 代理判据**依赖"账户免费档允许训练 = 开"。若某天该开关被关，`:free` 请求会直接 404 ⇒ 备路先失败，**不会**静默变成合规（失败方向安全）；但那时这条代理判据就**过严**了（应重新审）。
- 免费档型号**流动性高**（本轮 3 个已下架）⇒ §4/§5 的型号级结论有时效性，但**档位级结论**（免费档全训练）在本轮抽样中一致。

---

## 10. 关联

- [D6 备路站上化与 sensitivity 设闸调研与方案](../research/2026-09-21_D6备路站上化与sensitivity设闸调研与方案.md)（P0 止血 + P3 站上化；本报告的 §6 是其中 P1 的落地）
- [ADR-0003 OpenRouter 密钥与 egress 路由管理](../../adr/ADR-0003-OpenRouter密钥与egress路由管理.md)（凭据/出站平面治理）
- [OpenRouter 多账户配额分配与调配设计](2026-09-21_OpenRouter多账户配额分配与调配设计.md)（§5 第 4 条影响的就是这套机制）
- [DESIGN.md §358 路由不变式](../../spec/d6-agent-standard/DESIGN.md)
- 官方：[Data Collection](https://openrouter.ai/docs/guides/privacy/data-collection/) / [Provider Logging](https://openrouter.ai/docs/guides/privacy/provider-logging/) / [Input & Output Logging](https://openrouter.ai/docs/guides/features/input-output-logging) / [Provider Routing](https://openrouter.ai/docs/guides/routing/provider-selection)
