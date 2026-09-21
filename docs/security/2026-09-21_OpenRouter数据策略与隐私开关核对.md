# OpenRouter 数据策略与隐私开关 —— 核对与实测（P1，2026-09-21）

> **状态：核对完成。** 产出：四开关实际状态入档、免费/付费档策略矩阵实测、一项代码改动（**同日加入又撤回**，见 §6）、两项 OPEN-ISSUES 登记。
>
> **结论先行**
> 1. **三个/四个开关都不可机读**：`/api/v1/key` 不含隐私开关；`is_management_key=false` ⇒ 无管理 API 权限；`/api/v1/settings`、`/api/v1/privacy` 实测 **404**（无此端点）。**唯一**可机读的隐私相邻字段是 `allowed_data_regions: ["global"]`。⇒ 状态只能从 dashboard 读（用户提供，见 §1.1）。
> 2. **实际状态（用户读 dashboard 确认）**：`1% 折扣` = **关**；`免费档 publish` = **关**；`付费档 train` = **关**；**`免费档 train` = 开**。⇒ **OpenRouter 自己不留存、不使用**（① 关）；**不会进公开数据集**（publish 关）；**付费流量不训练**（付费 train 关）；**唯一敞口 = 免费档可能被训练**。
> 3. **该敞口被实测量化**：备路型号 `nvidia/nemotron-3-ultra-550b-a55b:free` 无偏好 **200**，一加数据策略约束即 **404 `No endpoints found matching your data policy (Free model training)`**；加 ZDR 亦 **404 `(Zero data retention)`** ⇒ **该型号全部免费端点都训练、且都不满足不保留**。
> 4. **⇒ 该开关是"使用免费档"的必要条件 ⇒ "关开关"= "放弃免费档"，不是一个可选的收尾动作**（`claude-opus` 备路确证；`claude` 备路为推理，见 §5）。而免费档被**三条链路**共用 ⇒ **决定：开关保持开，且不把"关开关"列为任何后续步骤**（§6.1）。**P3 站上化的价值已重述为"绕开沙箱 / 摆脱免费额度与型号流动性 / 提供可选合规后端"，与关开关无关**（§7）。
> 5. **⚠ 本条为修正后的结论**：曾据此加过一条 `sanitized × 可能训练 ⇒ 拒绝` 的硬闸，**同日撤回** —— 理由见 §6（① 与档位定义冲突；② 不对称 ⇒ 虚假安心；③ 半吊子闸比没有闸更危险）。**"免费档可能训练且训练不可撤回"登记为已知风险**：P3 提供**可选的合规后端**（使"将来若某类流量不接受训练"成为可能），但**默认立场仍是"免费档 + 接受训练"** —— 现有三档（`local-only` / `sanitized` / `public`）表达的是"能否出网"，**"是否可被训练"这一维在三档里没有位置**（§6.3）。
> 6. **付费档有合规端点**（实测 `data_collection:"deny"` 可用；`zdr` 部分型号可用）⇒ 若某类流量**单独**不接受免费档的训练暴露，可把它**改走付费 + deny/ZDR**（§7），**而不必**关掉整个免费档。
> 7. **顺带发现**：账户**未完成 18+ 年龄确认** ⇒ Meta 系型号全部 `403`（§8）。

---

## 1. 开关清单与**实际状态**

| # | 开关 | 位置 | 官方默认 | **实测/实况** |
|---|---|---|---|---|
| ① | **OpenRouter Use of Inputs/Outputs**（以日志换 **1% 折扣**） | Settings → **Privacy** | Off by default | ✅ **关** |
| ② | **Input & Output Logging**（在 OpenRouter 侧存 prompt/completion，仅自己可见，Beta） | Workspaces → **Observability** | Off by default | ⬜ **未读**（与 ① 是两件独立的事，见 §1.2） |
| ③ | **Allow free endpoints that train on request data** | Settings → **Privacy** | — | ⚠ **开** |
| ③b | **Allow free endpoints that publish prompts** | Settings → **Privacy** | — | ✅ **关** |
| ③c | **Allow paid endpoints that train on request data** | Settings → **Privacy** | — | ✅ **关** |

> ③/③b/③c 是**三个独立开关**（官方原文："There are **separate settings for paid and free models**"）。§4 的实测矩阵正是围绕 ③ 展开的。

### 1.1 状态来源
全部由**用户在 dashboard 读取**后提供（API 不可读，见 §2）。这属"人工读表"证据 —— 与 §4 的两条**机读旁证**一致（见 §3）。

### 1.2 ① 与 ② 为什么必须分开看
官方明写 "You can enable one, the other, or both"：① 是**把数据交给 OpenRouter 用于改进产品**（换折扣）；② 是**存在 OpenRouter 侧但只给你自己看**、OpenRouter 不使用。
⇒ ① **关** 已经排除"OpenRouter 拿你的数据改进产品"；② 若开着也只是"给自己看的调试副本"，**不改变数据所有权**。故 ② 未读**不构成**结论缺口，但为完整仍列为待读。

### 1.3 官方另有一项**无法关闭**的匿名采样
> *"Anonymous Input Categorization: OpenRouter samples a small number of prompts for categorization to power our reporting and model ranking. If you are not opted in to OpenRouter use of inputs/outputs, any categorization of your prompts is stored completely anonymously and never associated with your account or user ID. The categorization is done by model with a zero-data-retention policy."*

⇒ 与账户开关无关、匿名、ZDR。**登记为已知事实**（不是可配置项）。

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
| 6 | ✅ 正向：备路的 prompt 不再可能被**训练**（但**留存**是另一维，见 §4 第 3 行：免费档连 ZDR 都不可用） | 目的本身 |
| 7 | `local-only` 不受影响（P0 已不让它出网） | 已实施 |

---

## 6. 本轮决策：**开关保持开（不列为动作）**；`sanitized` 闸**同日加入又撤回**

### 6.1 决定一：**开关保持开** —— 并且"关开关"这个动作**不存在**

**⚠ 此处更正过一次说法**（用户质询后复核）：早先写的是"先不关，等 P3 建好替代再关"，把"关开关"当成了一个**收尾步骤**。这是错的 ——

- 该开关是"使用免费档"的**必要条件**（实测账户级拦截 `(Free model training)`）⇒ **"关开关" ≡ "放弃免费档"**，二者是同一件事，不是"改一个配置"。
- 而免费档**不是只有备路在用**：① claude 备路（harness 轨）；② judge/review 的 judge 槽（`secrets/openrouter.conf`，裸 API 轨）；③ 站上 opencode 的 `provider.openrouter.models` 免费档优先级表（站内 egress）。**关开关 = 同时打断这三条链路**。
- 收益（少一条训练暴露面）**远小于**代价（三条链路失效 + 放弃引入 OpenRouter 的初衷）。

⇒ **结论：开关保持开；不把"关开关"列为任何后续步骤**（早先把它写成 P3 的后续待办，属于"把手段当目的"，已从各处移除）。
⇒ 若将来某类流量**单独**不接受训练暴露，正确做法是**把那条流量改走合规后端**（§7），而**不是**关开关。

### 6.2 决定二：`sanitized × 可能训练 ⇒ 拒绝` 硬闸 —— **撤回**（同日）

**曾做过什么**：把判据扩展为 `sensitivity × 后端属性`，新增规则 `sanitized × 可能训练/发布 ⇒ sanitized+trains`，在**两个出网入口**各判（`Invoke-Task-Claude` 直接入口 + `AUTO_FALLBACK` 兜底入口）。当时 4 例（2 类 sensitivity × 2 条路径）全绿 + 双变异自证。

**为什么撤回**（用户质询后复核）：

| # | 理由 |
|---|---|
| ① | **与档位定义冲突**：[DESIGN §5.1 L193](../../spec/d6-agent-standard/DESIGN.md) 定义 `sanitized` 为「含**可机判**敏感项 ⇒ 先机械 scrub 才可进远端」，**未**声明"抹完后剩余内容仍机密" ⇒ **抹完的等级 = `public`**。给一个"脱敏后等价于 public"的档位加比 public 更严的约束，**没有语义依据**。 |
| ② | **不对称 ⇒ 制造虚假安心**：真正用免费档的大头是 **`public`**（与本规则无关、**全开**），只挡 `sanitized` 会让人以为"训练风险已处理" —— **半吊子闸比没有闸更危险**。 |
| ③ | **"免费档可能被训练"是使用免费额度的固有代价**（引入 OpenRouter 的目的就是免费额度），**不是某个档位的特殊问题**。自洽立场只有两种：**全接受（除 `local-only`）** 或 **不接受（把那类流量单独改走合规后端：站上本地引擎 / 付费+`deny`·ZDR）** —— ⚠ 注意"不接受"**不是**靠"关免费档开关"实现（关它 ≡ 放弃免费档 + 打断三条链路，见 §6.1）。 |
| ④ | 顺带更正：我最初的依据里"可能**公开发布**"那半在 ③b（publish）= **关** 之后已不成立。 |

**撤回后的形态**：判据只剩**一条** —— `local-only × 会出网 ⇒ local-only+egress`（那条是**真洞**：prompt 根本不该出网，破 DESIGN §358）。撤回理由已**留档在 `Get-SensitivityBackendReject` 的函数注释里**，防止被再次加回。

**撤回也做成可判的**（这是关键）：探针 `_probe_fallback.ps1` 的 C/D 例从"必须被拒"**翻成"必须被放行且在免费档上真产出 claude run"** —— 谁再把那条无依据的闸加回来，**C/D 立刻变红**。实测：A/B `[拒]` rc=4 且 claude run 不增；C/D `[放行]` claude run **增加**（真到免费档）；夹具 61/61。

### 6.3 撤不掉的：训练**不可撤回**（登记为已知风险，默认接受）

"出网/临时留存"可以遗忘，**被训练进权重则不可撤回**。这是**真实且质**的差别。但注意它**不构成**一条可执行的闸：

- 现有三档表达的是"**能否出网**"（`local-only` / `sanitized` / `public`），**"是否可被训练"这一维在三档里没有位置** ⇒ 想拦就得**新增一档并定义其语义**（那是一个独立的设计题目，不是给 `sanitized` 打补丁 —— 这正是 §6.2 撤回的原因）。
- 故：**默认接受**该风险（因为它与"使用免费额度"是同一件事），并保留两条**可选的**出路：① 某类流量**单独**改走付费 + `deny`/ZDR；② 走 P3 的站上本地引擎。

---

## 7. 合规后端评估（是"哪些流量需要换后端"时的手册，**不是**"为关开关做准备"）

| 路 | 性质 | 代价 / 适用场景 |
|---|---|---|
| **默认（免费档，即现状）** | 可出网 + **可能被训练** | **本轮立场**：这是使用免费额度的固有代价。**仅 `local-only` 不在此列**（P0 已拦：它根本不出网） |
| **站上本地引擎（P3 站上化）** | **全合规**：不出网、不花钱、不训练 | 需实现 P3；站上资源占用待实测。**适用**：将来某类流量**单独**不接受训练暴露时 |
| **付费型号 + `provider:{data_collection:"deny"}`** | 合规（实测可用）；ZDR 需挑型号 | 花钱；型号要换；"型号流动性高"这一点付费档同样有 |
| 换其他 `:free` 型号 | 仍**可能训练** | 换不掉这一维 —— 免费档 ⟺ 全训练 |
| ~~关掉免费档开关~~ | **已排除** | 等于放弃免费档，且会**同时打断三条链路**（§6.1）—— 不是"换后端"，是"砍能力" |

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

- 开关的**实际状态**全部由**用户读 dashboard** 提供（① 关 / ③ 开 / ③b 关 / ③c 关）；② 未读。API 侧**没有**这些开关 ⇒ 本报告的机读结论是"**不可机读**"，不是"读出来是关"。
- **③c（付费档 train）= 关 的状态**来自用户读表；§3 有一条**旁证**（`/models/user` 少了 3 个 `-contributor` 型号）但**不构成确证**（§8 已排除一个竞争解释，却无法排除"另有 guardrail 所致"）⇒ 本报告刻意不把"旁证"写成"确证"，两者**结论一致**但证据强度不同。
- **⑧ 免费档型号流动性高**（本轮 3 个 `:free` 已整体下架）⇒ §4/§5 的**型号级**结论有时效性；**档位级**结论（免费档端点全训练）在本轮抽样中一致。
- **本报告有过一次结论反转**（§6.2：`sanitized` 闸加入又撤回）。留档原因：① 让"为什么撤回"可被未来的人复查；② 防止被无依据地再加回。**不删改历史判断，只在原地标注修正**。

---

## 10. 关联

- [D6 备路站上化与 sensitivity 设闸调研与方案](../research/2026-09-21_D6备路站上化与sensitivity设闸调研与方案.md)（P0 止血 + P3 站上化；本报告的 §6 是其中 P1 的落地）
- [ADR-0003 OpenRouter 密钥与 egress 路由管理](../../adr/ADR-0003-OpenRouter密钥与egress路由管理.md)（凭据/出站平面治理）
- [OpenRouter 多账户配额分配与调配设计](2026-09-21_OpenRouter多账户配额分配与调配设计.md)（§5 第 4 条影响的就是这套机制）
- [DESIGN.md §358 路由不变式](../../spec/d6-agent-standard/DESIGN.md)
- 官方：[Data Collection](https://openrouter.ai/docs/guides/privacy/data-collection/) / [Provider Logging](https://openrouter.ai/docs/guides/privacy/provider-logging/) / [Input & Output Logging](https://openrouter.ai/docs/guides/features/input-output-logging) / [Provider Routing](https://openrouter.ai/docs/guides/routing/provider-selection)
