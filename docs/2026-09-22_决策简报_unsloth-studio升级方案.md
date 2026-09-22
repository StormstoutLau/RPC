# 升级决策简报 —— unsloth studio 升级（网关 UI 控制帧致本地 provider 压缩失效）

- **日期**: 2026-09-22
- **状态**: **三站收口完成**（A 已收口；B 试点通过 + 补齐 + `triton_kernels` 拷平；**C 已推**；`UNSLOTH_LLAMA_CPP_BACKEND=rocm` 落三站；性能测量完成）—— 详见 §七 / **§八**
- **触发**: 用户问「opencode 遗留问题是否必须注册」⇒ 定位 compaction 失败根因 ⇒ 用户令「评估升级方案」「先取证 A 的未知项」⇒ 本简报
- **关联**: [OPEN-ISSUES §O-23](../spec/d6-agent-standard/OPEN-ISSUES.md)（根因全文落档）· [DEVELOPMENT-LOG 2026-09-22 线二](../spec/d6-agent-standard/DEVELOPMENT-LOG.md)（第 ⑧ 条）

---

## 一、问题与根因（已定位，非推测）

**症状**: 本地 provider 上，opencode 一旦会话累积超阈、进入 `agent=compaction`，**压缩必然失败**（`AI_TypeValidationError`）⇒ 长任务**无法靠压缩自救**。

**⚠ 但触发条件是"潜伏"的（2026-09-22 用户追问后查明，更正此前记法）**: 生产配置 `limit.context=131072` + `compaction.reserved=20000` ⇒ **压缩阈值 = 111072 ≫ 引擎 `n_ctx`=32768** ⇒ **压缩在撞引擎上限前不可达**；本仓历史记录已给佐证（"`62079 < 131072-20000` ⇒ 不触发预压缩 ⇒ 直发 ⇒ 400"）⇒ **历史失败（52k/62k）全是服务端 400，与压缩无关**。本轮"压缩必崩"是**用 `limit.context=20001` 把阈值人为压到 1 token 才逼出的、生产不存在的条件** ⇒ **属实验设计瑕疵（把潜伏缺陷当活跃缺陷）**。**变为活跃的条件** = 把 `limit.context` 下调到 ≤ 引擎 ctx + reserved（**"对齐引擎档位"= 32768 ⇒ 阈值降到 12768**）。

**根因（三级，均有对照实验）**:

| 级 | 事实 | 证据 |
|---|---|---|
| ① **网关**（unsloth studio `:8080`）在流式响应里**注入非标准 SSE 帧** | `data: {"type": "reasoning_summary", …}` | 三方 curl 同 prompt/model：studio 流式 **命中 1**／studio **非流式 0**／**直连 `llama-server :47059` 流式 0** ⇒ 帧由 **studio 注入** |
| ② **客户端路径差异** | 普通对话**容错丢弃**、压缩路径**严格 union 校验** | DEBUG 对照：**普通 turn 命中 0 / `TypeValidation` 0 / rc=0**；**压缩 turn 命中 3 / `TypeValidation` 2 / rc=1** |
| ③ **上游已确认并已修** | [unslothai/unsloth#10362](https://github.com/unslothai/unsloth/issues/10362)（**closed 2026-09-08**，16 评论）正文逐字即本例："UI control frames … **carry no `choices`, so strict OpenAI clients fail schema validation**"；修法 = 控制帧收进 **`X-Unsloth-Events` opt-in**（默认不发）；其自测 **"8 of 13 streams throw outright today"** | 站上 studio 目录 `grep -rl "X-Unsloth-Events"` **无命中** ⇒ 我方不含该修复 |

**被否的两条修法**（勿再试）:
- **加 `X-Unsloth-Events` 头** ⇒ **反向**（加了才会收到控制帧）；
- **改 `baseURL` 直连引擎端口** ⇒ 实测确实无控制帧，但与 [`_station_ready.sh`](../ops/station-bin/_station_ready.sh) 的 **C2「端口固定 8080、本脚本不改写任何配置」**相悖（"就地改写 baseURL"正是当年**留下死端口 + 三站 config 漂移**而被废弃的旧实现）。

---

## 二、实测事实（本简报全部结论的取证底账）

| 项 | 实测值 |
|---|---|
| **三站 studio 版本** | **A / B / C 全部** `unsloth 2026.9.2` + `unsloth_zoo 2026.9.1`（⇒ 门禁 `backend` 当前一致） |
| studio 体量 / 耦合 | `~/.unsloth/studio` **7.3G**；引擎**独立**在 `~/llama.cpp-vulkan-b10715`（1.9G，日志证实由 studio 拉起）；`torch 2.11.0+rocm7.13.0` |
| **升级入口** | **`unsloth studio update`** —— `--package <str>` **默认 `unsloth`** ⇒ **就是更新 `unsloth` 包本身**（非"只重建依赖"）；`--local` = 从本地 repo（反证默认 **PyPI**）；`--verify` **默认开**（更新后扫描损坏）；另有 `verify-install`（其**退出码**供官方 setup 走"已最新"快径） |
| **PyPI 版本线** | `2026.9.2`（09-02 13:07，**我方**）→ **`2026.9.3`（09-08 15:21）** → `9.4`(09-09) → `9.5`(09-16) → `9.6`(09-17) → **`9.7`(09-18 16:21，latest)** |
| **修复落点** | `2026.9.3` 与 **#10362 关闭日 + 上游 release `v0.1.806-beta` 发布日同日** ⇒ **第一个含修复的候选** |
| **回滚可行性** | `2026.9.2` **仍在 PyPI** ⇒ 可重装复原 ⇒ 基线**只需记版本 + venv 清单 + 关键 md5**，**不必整 7.3G 备份** |

**上游 release 线（studio）**: v0.1.804/805-beta(09-02) · **v0.1.806-beta(09-08)** · v0.1.807(09-09) · v0.1.808(09-16) · v0.1.810(09-17) · **v0.1.811-beta(09-18)**

---

## 三、方案与代价

| 方案 | 内容 | 代价 / 风险 | 收益 |
|---|---|---|---|
| **A 升级** | 三站升至 `unsloth 2026.9.7`（先 B 站试点） | 7.3G 级 venv 重建（含依赖下载）· **牵连引擎启动参数**（studio 是引擎启动方，注入 `-c`/`--chat-template-kwargs`/`--jinja`）⇒ 需回归 D1 档位与 O-23 的 `ENGINE_CTX` · **必须三站同升**（否则门禁 `backend` FAIL） | **治本**：压缩路径恢复可用 |
| **B 零站上改动** | 在 `opencode.jsonc` **根级** `compaction.auto` 设 **`false`** ⇒ 让"注定失败"的压缩不再发生 | 一处 config；⚠ **该配置项在 1.18.25 的语义**参见下文「B 验证记录」（**当日已实测**） | **已实测成立**：压缩不再触发；超引擎 ctx 时失败形态变为**明确的服务端 400**；**不依赖上游** |
| **C 不动** | 维持现状（agent-cli clamp 为唯一防线），台账已记 | 零成本 | — |

### B 验证记录（2026-09-22 当日实测，引擎 = B 站 gpt-oss-20b `ctx=32768`）

**关键更正（本轮先踩后纠）**: 第一版实验把 `"compaction": {"auto": false}` **插入到 `"models": {` 之前** —— 而该 config 的**顶层键**里**根本没有 `models`**（实测 `TOP_KEYS = [\$schema, autoupdate, compaction, model, plugin, provider]`，`models` 在 `provider.*` 之下）⇒ 插成了 **`provider` 的一级子键、被静默忽略** ⇒ 那一轮"`auto=false` 无效"的读数**无效**。
**纪律（新增）**: **配置类实验必须先断言"作用点真的改了"**（改后 `json.load` 读回并断言新值，再跑行为）——否则"没变化"可能只是**没改到**。

| 臂 | turn1 | turn2 | turn3 | 备注 |
|---|---|---|---|---|
| **`auto=false`** | rc=0 · compact=**0** | **rc=0** · compact=**0** | **rc=0** · compact=**0** | 自证 `auto_is_false = True`（读回断言） |
| 基线（`auto=true`） | rc=0 · compact=0 | **rc=1** · **compact=2** | rc=1 · compact=2 | 已知基线 |

**超引擎 ctx 的失败形态（单次 35 699 tok > 32 768，`auto=false`）**: **`compact=0`**（压缩确实未触发）+ **服务端 400** `Message too long: 35699 tokens exceeds the 32768-token context window`（`type=invalid_request_error`, `code=context_length_exceeded`）⇒ 失败**明确、可归因**。

**顺带发现（同源，与压缩无关）**: 同一控制帧也会打到 **`agent=title`** 子请求（日志 `agent=title small=true` 抛 `AI_TypeValidationError`）⇒ 这与**基线里"普通 turn `TypeValidation=1` 但 rc=0"**吻合 ⇒ **标题路径遇该帧会报错但不致命**（此前"普通 turn 命中 0"的表述据此更正为"**不致命**"）。

⇒ **B 的语义（完整）**: `auto=false` 不是"让压缩更早/更晚"，而是**彻底不走压缩** ⇒ ① 累积型任务**继续跑**（不再自杀）；② 撞引擎上限时由**服务端给出明确 400**；③ **但引擎上限不变 ⇒ 仍不能替代 clamp**。
**⚠⚠ 净效果限定（2026-09-22 用户追问后补）**: 在**当前生产配置**（`limit.context=131072` ⇒ 阈值 111072 ≫ 引擎 32768）下，**压缩本就不可达 ⇒ B 的净效果 ≈ 0**（它关掉的是一条走不到的路径）。**B 的真正价值 = 它是"下调 `limit.context`（对齐引擎档位 ⇒ 阈值降到 12768）"这一拟议改进的前置保险** —— 没有 B 就动 `limit.context`，会把潜伏缺陷激活成高频故障。⇒ **B 是缓解与保险，不是解法**。

**⚠ 收益边界（三方案共用）**: 升级**只买到"累积型长任务能被压缩救回"**；**单次请求超引擎 `n_ctx` 仍被服务端拒** ⇒ **agent-cli clamp 无论如何都要保留**（O-23 架构结论不变）。

**⚠⚠ 范围外发现（2026-09-22 执行中暴露，本简报原评估遗漏）**: `studio update` **不只升 Python 包 —— 它会把 `~/llama.cpp`（引擎）替换为 `unslothai/llama.cpp` 的 latest**，且 `--help` **无跳过开关** ⇒ 三站引擎一致性、`/opt` 治理面与回滚点均受影响。详见 [§七](#七执行记录与范围外发现2026-09-22-当日)。

---

## 四、试点步骤与判据（若选 A）

**B 站试点（6 步）**:
1. **记基线**: `unsloth --version` / `pip freeze` 清单 / 关键文件 md5 / 门禁快照（`backend`·`stations`·`models`·`engine`）
2. `unsloth studio update --verbose`
3. `unsloth studio verify-install`（核退出码）
4. **三条已建判据复验**（判据均在本轮已跑通）:
   - **流内 `reasoning_summary` 计数必须 = 0**（三方 curl 法：studio 流式 / studio 非流式 / 直连引擎流式）
   - **压缩两轮 rc=0**（多轮法：小 `limit.context` 探针 + 同 session 两轮）
   - `infer-load` **档位口径**与 **`ENGINE_CTX` 探测**未变
5. 门禁 `backend` / `stations` 复核（三站一致性断言）
6. **通过后再推 A、C**（三站同步，最后统一门禁）

**回滚**: `pip install unsloth==2026.9.2`（或 `update` 的对应机制）+ venv 清单复原。
⚠ **待试点时确认**：`update --package` 接的是**包名**（未必接版本 specifier）⇒ "指定版本/回滚"可能需绕到 pip 直装。

---

## 五、诚实边界（未取证 / 未验证）

1. **"修复在 `2026.9.3` 里"是日期同期性推断**（#10362 closed 09-08 + 该版 09-08 发布 + release v0.1.806-beta 同日），**未逐版核对变更内容**；最硬的验证就是试点第 4 步的"`reasoning_summary` 计数 = 0"。
2. **`compaction.auto=false` 的语义** —— ✅ **当日已实测**（见 §三「B 验证记录」）：**不再触发压缩**；超引擎 ctx 时失败形态 = 明确的服务端 400；**不替代 clamp**。**仍未知**：多轮累积"刚好撞引擎上限"时的逐步行为（本轮以**单次 35.7k** 代，未逐轮跑到上限）。
3. **`update` 能否指定版本**未验证（影响回滚路径的确定性）。
4. 本轮**未执行任何 `update`**；所有站上操作均为**只读**（版本/help/源码 grep/日志）。
5. **引擎面牵连程度未量化**：只知"studio 会注入启动参数"，**未**比对旧/新版的默认参数差异（试点第 4 步的"档位未变"是事后判据，非事前评估）。

---

## 六、待裁清单

| # | 待裁项 | 选项 |
|---|---|---|
| 1 | 是否开 **A 的 B 站试点**（含上述 6 步） | 现在做 / 押后 |
| 2 | 是否**先做 B**（`compaction.auto=false`，零站上改动） | ✅ **已验证成立（当日）** ⇒ 可**直接执行**（改一处 config + 三站同步） |
| 3 | **目标版本** | `2026.9.3`（最小变更）/ **`2026.9.7`（latest，推荐）** |
| 4 | **升级窗口** | 需三站**连续**窗口（B 试点 → A/C） |
| 5 | **回滚机制**是否先确认（`update` 版本可指定性） | 先确认 / 试点中一并确认 |
| 6 | 试点通过后**是否立即推 A、C** | 立即 / 另约窗口 |
| **7** | **A 完成前，任何"下调 `limit.context`（含对齐引擎档位）"的动作** | **一律禁止**（会激活潜伏缺陷；若确需动，**必须先落 B**） |

---

## 七、执行记录与范围外发现（2026-09-22 当日）

### 7.1 用户裁定
**B 站试点 → 通过后立即推 A、C**；**A 完成前禁止下调 `limit.context`**（待裁 7）。遇新变量时用户裁定：**让 A 跑完 + 暂停 C + 立即落档**。

### 7.2 B 站试点结果：**通过**

| 判据 | 升级前 | **升级后** |
|---|---|---|
| ① 流内控制帧 `reasoning_summary` | studio 流式 **1** | **0**（非流式标准、直连引擎 0） |
| ② 压缩两轮（probe `limit=20001`、`auto=true`） | turn2 **rc=1** / compact=2 / **TypeValidation=2** | **turn1 rc=0；turn2 rc=0 / compact=1 / TypeValidation=0** ⇒ **压缩恢复可用** |
| ③ 引擎档位 | `ctx 32768` / `:8080` | **未变** |

版本面：`unsloth 2026.9.2 → 2026.9.7`、`unsloth_zoo 2026.9.1 → 2026.9.6`、`bitsandbytes` 换成 GitHub continuous wheel；`X-Unsloth-Events` 命中 **0 → 2**。

**⚠ 本条两处后经复核更正（2026-09-22 晚，三站实测）**：
1. **「`pyarrow 25.0.1 → 23.0.1` 意外降级」不成立** —— A/B/C **三站实测 `pyarrow` 全为 `23.0.1`**（含**从未升级**的 C）⇒ 升级不可能造成它；原记的 `25.0.1` 基线**存疑**（疑为记录错位），已撤销该结论。
2. **「包总数 235 不变」不足以判定"未完成"** —— 该口径当时未与 A/C 对账。实测 A=261 / C=261 / **B=234**（freeze 计数），且 B **完全没有** `unsloth_install_manifest.json`（A/C 都有）⇒ "B 未完成一次完整 pass"这一结论**另由 manifest 证据支撑**，见 §7.8。

### 7.3 ⚠ 范围外发现：`studio update` **会替换引擎**

- 日志：`requested llama.cpp tag: latest (repo: unslothai/llama.cpp)` → `installing prebuilt llama.cpp...` → `Downloading llama.cpp-source-<sha>.tar.gz（36.1 MiB）` → **随后本地编译**（A 站实测 **169** 个 cmake/g++ 进程）。
- **`--help` 无任何跳过引擎的开关**（仅 `--local` / `--package` / `--verbose` / `--verify`）。
- ⇒ **影响**：① **三站引擎版本将不一致**（B 引擎未动、A 被替换）；② 偏离引擎治理面 `/opt/llama.cpp-9859`（**注：update 目标是 `~/llama.cpp`；本次实测 `/opt/llama.cpp*` 三个入口未被触及**）；③ 需为 `~/llama.cpp` 面**另立回滚点**。
- **简报原评估遗漏此条**（仅提示"可能牵连引擎启动参数"，未料到**直接换二进制**）。
- **⚠ 更正（2026-09-22 晚，以站上 marker 为准）**：装上的引擎是 **`published` prebuilt**（`UNSLOTH_PREBUILT_INFO.json`: `source: "published"`、`prebuilt_fallback_used: false`、`asset: app-b11030-mix-5ff778e-linux-x64-vulkan.tar.gz`、`bundle_profile: linux-vulkan-x64`；版本串 `built with GNU 11.4.0 … (Compiled by the Unsloth team)` = 其 CI 产物）⇒ 上文「随后本地编译」的**因果推断不成立**（当时观察到的 source 包下载与 169 个编译进程**应另有归属，未逐条追定**）。**真正发生的不是"编译回退"，而是"选错了 prebuilt 变体"** —— 见 §7.7。

### 7.4 执行中遇到的三个网络瓶颈与处置（可复用）

| 瓶颈 | 现象 | 处置 |
|---|---|---|
| `uv` → PyPI 走 **IPv6**（Fastly `2a04:…`） | **8 分钟 CPU 仅 1s、零进展** | **清华镜像 env**（`UV_INDEX_URL`/`UV_DEFAULT_INDEX`/`PIP_INDEX_URL`）⇒ 解卡 |
| `bitsandbytes` 从 **GitHub release 直链**（`--no-cache-dir`） | 稳定 **~30 KB/s**（asset **41.1 MiB** ⇒ ~25 分钟） | 先用 `gh api` 查 **asset 大小** ⇒ **量化 ETA** 后决定"等"；A/C 走代理则快 |
| `triton_kernels @ git+https://github.com/triton-lang/triton.git` | `git fetch` **零字节卡死**（git 默认无低速超时 ⇒ 会挂数小时） | B 站**收口**（kill）；**脚本本身有 `triton kernels (skipped, no git)` 分支**；**A/C 已装 `triton_kernels 1.0.0` ⇒ 该步可跳过** |

- 公共 GitHub 代理（ghfast / ghproxy / gh-proxy）**实测均不可用**；**A 站本机 clash（`127.0.0.1:7890`）可用**（GitHub 握手 **0.46s**，对比直连 0 字节）；**C 站经 SSH 隧道复用 A 的代理**（实测有活跃连接）。

### 7.5 三站当前状态

> **本节原表（2026-09-22 晚状态）已由 [§8.6](#86-三站现状第二轮收口后实测) 取代** —— 为避免"同一事实两张表"的漂移（本仓纪律：同一事实出现在多张表 ⇒ 改一处必须核另一处），此处只留指针，不重复列数。
> 口径统一说明：`X-Unsloth-Events` 现按 `…/site-packages/studio` 下**命中文件数**计，**三站均为 3**（此前 §7.2 记的"2"为早期不同扫描范围下的计数）。

**门禁（2026-09-22 晚复核）**：**15 绿 / 1 黄 / 0 红**；`backend` **PASS**、`gates` **站上件一致 24/24**、`engine` 三站可达且 **0 在服务**。

### 7.6 顺带纠正两处简报假设

1. **"三站 studio 版本不一致会致门禁 `backend` FAIL" —— 不成立**：B 升级后门禁仍 **15 绿 / 1 黄 / 0 红**、`backend` PASS（该断言查**引擎后端与 ROCm 串**，**不查 studio 包版本**）。
2. **`verify-install` 基线即 `rc=1`**（官方语义"安装未完成"）⇒ B 升级后仍 `rc=1`，**非本次造成** ⇒ 该判据**在本环境不可用作"完整性"判据**。

### 7.7 A 站引擎面回归：根因（已取证）→ 已收口

**现象**：A 升级 `verify-install` 跑完（`rc=0`），但推理面不可用 —— 引擎由 `0.3.0-dev (build 10715, Clang, ROCm0)` 变为 **`0.4.1-dev (build 11030, GNU, Vulkan-only)`**；`infer-load` 报 `invalid device: ROCm0`。

**根因（marker 对照，非推测）**：

| 站 | `UNSLOTH_PREBUILT_INFO.json` 关键字段 | 引擎设备 |
|---|---|---|
| B / C | `asset …-rocm-gfx1151.tar.gz` · `backend: rocm` · `gfx_target: gfx1151` · `host_profile.has_rocm: true` | `ROCm0` |
| **A** | `asset …-vulkan.tar.gz` · `bundle_profile: linux-vulkan-x64` · `backend: vulkan` · **`host_profile.has_rocm: false`** · **`has_intel_gpu: true`** · `rocm_gfx_target: null` | **`Vulkan0`** |

⇒ **A 站 update 时刻的硬件探测误判**（把 AMD 8060S 探成"无 ROCm + 有 Intel iGPU"）⇒ 安装器按 `auto` 路由到 **Vulkan bundle**。**当场复测（同一台 A）**：`detect_host()` 返回 `has_rocm=True, rocm_gfx_target='gfx1151', has_intel_gpu=False` ⇒ **探测误判是间歇/环境相关的，非硬件事实**。B 同测亦为 `has_rocm=True`。

**⚠ 诚实边界**：**为什么当时探成 `has_rocm=false`，未定论**（不排除"update 期间 venv 重建导致探测环境不完整"或探测本身的间歇缺陷）。本次**未**去复现该误判。

**修法（两层，用户裁定"两者兼做"）**：

1. **复原既定形态**：从 B 站 `tar` 分发同版引擎（`~/.unsloth/llama.cpp`，`build 10715 / ROCm`）到 A。**实测结果**：A 站 `llama-server --version` = `0.3.0-dev (build 10715, commit 92cedc867)`；`--list-devices` = `ROCm0`；**`llama-server` md5 与 B 站逐字节相同**（`31d8787b6e09bb0142ed2ef488423440`）；`libggml-hip.so` 在位、无 `libggml-vulkan.so`。旧 Vulkan 引擎**改名保留**为 `~/.unsloth/llama.cpp.vulkan-b11030-20260922`。
2. **`infer-load` 二修**（[infer-load](../ops/station-bin/infer-load)）：不再硬编码设备名，改为按引擎自身 `--list-devices` **实测选取**（`ROCm` 优先 → `Vulkan` → `CUDA` → 首个），`INFER_DEVICE` 仍为最高优先；探测结果写日志 ⇒ **"翻转过"与"没翻转"可区分**。

**两侧对照（判据先在已知会红/会绿的对照上验红）**：

| 对照 | 引擎 | `infer-load` 探测日志 | 结果 |
|---|---|---|---|
| Vulkan 侧（改前，A 原状） | `Vulkan0` | `候选=[Vulkan0] 选中=Vulkan0` | 判定正确（该值当日已实测可 `READY ✓`） |
| ROCm 侧（复原后，缺省无 `INFER_DEVICE`） | `ROCm0` | `候选=[ROCm0] 选中=ROCm0` | **端到端 `READY ✓ :8080`，`rc=0`** |

**收口判据（三站部署后实测）**：门禁 `backend` **PASS**（回到"单站=HIP / 分布式=Vulkan"）、`engine` PASS、`gates` PASS（**站上件一致 24/24**，含新 `infer-load`）；**红灯 0**。

### 7.8 B 站：确实没有一次"已完成 pass"（manifest 证据）→ 补齐执行

**证据（manifests 对照，2026-09-22 晚实测）**：

| 站 | `~/.unsloth/studio/unsloth_studio/unsloth_install_manifest.json` |
|---|---|
| A | 有（`package_version: 2026.9.7` · `steps_total: 16` · `completed_at_ms` 存在 · `requirement_files` **含 `single-env/data-designer.txt` 与 `…-deps.txt`**） |
| C | 有（`package_version: 2026.9.2` · `steps_total: 15`） |
| **B** | **完全没有该文件** ⇒ 从未写出过"已完成 pass" |

⇒ **B 的 `data-designer*` 等缺失项确属"声明需求未落地"**（A 的 manifest 把 `data-designer.txt` 列为 pass 输入），**不是"多装的东西"** ⇒ **"补齐"这一处置成立**。

**补齐路径（本次采用，避免牵连引擎）**：`install_python_stack.py` **可单独运行**（`python …/studio/install_python_stack.py`；其 `__main__` 只调 `install_python_stack()`，**不含任何 llama.cpp 引擎步骤**）⇒ 这是"只补 Python 层、不动 `~/.unsloth/llama.cpp`"的正规入口。
- `triton_kernels` 步骤：B 未装该包 ⇒ 会走 `pip install git+…`。B 直连 GitHub 实测 **~33 KB/s**（`curl https://github.com` 8s 仅收 268 KB）、B **无本地代理**，该 `git fetch` 不可行。该步骤（站上 `studio/install_python_stack.py` 内 `_triton_kernels_step`）的**作者级兜底**是 `_has_working_git()` 为假时打印 `triton kernels (skipped, no git)` 并返回（注释自陈"must not fail an update over a speedup that is already installed"，且该包**仅用于训练加速**）。
- **本仓采用的做法**：以 `/tmp/nogit/git`（`exit 127`）**前置**于 `PATH` ⇒ 断言 `_has_working_git()` 返回 `False`（先断言、再跑，见"配置类实验必须先断言作用点"纪律），再运行 `install_python_stack.py`。**代价**：B 侧 `triton_kernels` 仍缺（**三站唯一包差异，已登记**）。
- **配套安全措施**：运行前把 B 的 `~/.unsloth/llama.cpp` 改名保留（避免任何意外的引擎面牵连），确认无牵连后**已复位原位**（`--list-devices` = `ROCm0` 复核通过）。

**补齐结果（2026-09-23 00:05 实测）**：
- pass **跑完**（日志 `deps installed`，17 步）⇒ **B 包数 234 → 261 = A = C**；`unsloth_install_manifest.json` **已写出**（3.2 KB，含 `pass_inputs`（**含 `triton-kernels.txt`**）与 `step_results`；`known_unmet` 记 `single-env/data-designer-deps.txt: ["click 8.5.0"]` —— 已知的结构性未满足，**非本次引入**）。
- **引擎未被触碰**：`llama-server` md5 仍 `31d8787b…`、`--list-devices` 仍 `ROCm0`。
- **推理面复验**：`infer-load gpt-oss-20b`（缺省设备、新版脚本）⇒ 探测 `选中=ROCm0` + **`READY ✓ :8080` / rc=0**；流内 **`reasoning_summary=0`**（试点主判据在补齐后**仍成立**）；已 `infer-unload`，无残留。
- **残余差异（版本级，非缺失）**：B 的 `unsloth_zoo 2026.9.7` / `mcp 1.30.0` / `huggingface_hub 1.30.0` / `torchcodec 0.11.1` / `ruff 0.16.8` 等**略新于 A**（pass 取当次 latest）；`bitsandbytes` 形态不同（B 为 GitHub continuous wheel、A 为 PyPI `0.50.2`）。⇒ **三站唯一"缺失类"差异仍是 `triton_kernels`（仅 B 无）**，已登记。

### 7.9 调研结论：`studio update` **会**覆盖既有的后端设置（作者级证据）

**问题**（用户提出）：`unsloth studio update` 是否**总会**完全覆盖原来的后端框架设置？

**答：默认会，且是由"每次重新做硬件探测"驱动的；只有显式 pin 才拦得住。** 证据全部来自站上源码 `studio/install_llama_prebuilt.py`：

| 机制 | 事实 |
|---|---|
| **优先级** | `effective_backend_request()`：**CLI `--llama-backend` / env `UNSLOTH_LLAMA_CPP_BACKEND` / legacy `UNSLOTH_FORCE_VULKAN`** ⇒ `mandatory=True`（**显式**）；都没有时读 **marker 里的历史选择** ⇒ `mandatory=False`，即 **advisory** |
| **advisory 的含义** | 源码逐字："A stored choice is advisory: **it is dropped for detection when the hardware or the published bundles no longer offer it**" ⇒ **探测说了算** |
| **可选项** | `REQUESTABLE_BACKENDS = ("auto", "cpu", "cuda", "rocm", "vulkan")`，`hip` 为 `rocm` 别名 |
| **pin 的语义** | `--llama-backend` 的 help 逐字："record the choice, **so later updates keep it instead of re-detecting**. cuda and rocm (alias hip) also **opt out of the automatic Vulkan routes**. **A backend with no bundle for this host fails rather than installing a different one**; `auto` restores hardware detection and clears a recorded choice. … **Same effect as `UNSLOTH_LLAMA_CPP_BACKEND`**." |
| **落盘位置** | `<install_dir>/UNSLOTH_PREBUILT_INFO.json`（即 `~/.unsloth/llama.cpp/UNSLOTH_PREBUILT_INFO.json`） |
| **其它旋钮** | `UNSLOTH_LLAMA_FORCE_COMPILE` / `_REF`、`UNSLOTH_LLAMA_NO_SYSTEM_ROCM`、`UNSLOTH_ROCM_GFX_ARCH`、`UNSLOTH_LLAMA_CUDA_ARCHS`（**全部为 env，无 CLI 对应**） |
| **无"跳过引擎"开关** | `unsloth studio update --help` 仅 `--local` / `--package` / `--verbose` / `--verify` ⇒ 引擎步无法关闭 |

**社区 / 官方口径**：
- **当前官方文档**（如 Qwen3.5 fine-tune 页）仍把 `unsloth studio update` 列为 Studio 的更新方式之一。
- 但 **2026-06 的发布说明有一处 breaking change**：`v0.1.44-beta`（06-03）起，`v0.1.462 / .463 / .464-beta`（06-12）重复同一句 —— **"DO NOT USE `unsloth studio update` as packaging will not get the latest updates; use the provided curl/irm scripts"** ⇒ 那是**当时那个版本系列**的告示（理由是"拿不到最新打包"），**不是现行通则**；本仓仍以站上实测为准。
- AMD 侧官方文档（`docs/basics/amd`）自陈会 "auto install … **llama.cpp prebuilts**"，并称 "**llama.cpp ROCm prebuilts are provided daily**" ⇒ ROCm prebuilt **确实存在**，本仓遇到的是**选型/探测**问题，不是产物缺失。

**⇒ 本仓对策（建议，已部分落地）**：
1. **硬 pin**：升级前 `export UNSLOTH_LLAMA_CPP_BACKEND=rocm`（等价 `--llama-backend rocm|hip`）—— 这是**唯一能挡住"探测误判 ⇒ 换后端"的机制**，且选不到 bundle 时**显式失败**而不是悄悄换一个。
2. **鲁棒层**（已落地）：`infer-load` 设备实测选取 ⇒ 即使翻转也不再"必然失败"。
3. **哨兵**（已存在）：门禁 `backend` 断言 ⇒ 翻转**必红**（本次正是它抓到的）。

### 7.10 回滚机制（试点中一并确认 → 结论）

| 面 | 可行性 | 证据 / 命令 |
|---|---|---|
| **Python 包** | ✅ 可指定版本 | `--package <str>` 接的是 **pip specifier**（help 明示 "Package name to install/update"，默认 `unsloth`）⇒ `unsloth studio update --package "unsloth==2026.9.2"`；`2026.9.2` **仍在 PyPI** |
| **引擎（`~/.unsloth/llama.cpp`）** | ❌ **update 无此能力** | 引擎恒取 `--llama-backend`/发布的 `latest` tag，**无跳过开关**；`latest` 当前解析为 `b11030-mix-5ff778e` |
| **两者的耦合** | ⚠ **包回滚 ≠ 引擎回滚** | 执行包回滚**会再走一次引擎步**（A 站实测：引擎被替换）⇒ **回滚前必须先备份引擎目录** |

**三站现成回滚点（2026-09-22 晚实测在位）**：
- `~/.unsloth/llama.cpp.vulkan-b11030-20260922`（A 站，本次被替换掉的 Vulkan 引擎）
- `/opt/llama.cpp-9859`（三站均在位，门禁 `backend` 已核）+ `/opt/llama.cpp` → `llama.cpp-master-91f6a6cf`
- `infer-load` 旧版：三站 `/usr/local/bin/infer-load.bak-20260922`（md5 `e474b761198dde596b86ab0edfad19be`）
- **站间互备**：A 与 B 的 `llama.cpp` 引擎**逐字节同版**（md5 `31d8787b…`）⇒ 任一站可从另一站 tar 复原（实测 1.9 G / **18 s**）

---

## 八、第二轮收口与性能测量（2026-09-23）

**用户五项指令**：① `UNSLOTH_LLAMA_CPP_BACKEND=rocm` 落到站；② C 站推升级；③ B 的 `triton_kernels` 从 A 拷平；④ 升级排查分析全过程 + 性能测量结果完整落档；⑤ 修平 OPEN-ISSUES 三个表块列数不一致。

### 8.1 五项结果一览

| # | 项 | 结果 | 关键证据 |
|---|---|---|---|
| ① | **pin 落站** | ✅ 三站已落（**`/etc/environment`**） | `printenv` 非交互 ssh 生效；`effective_backend_request() == ('rocm', True)`（**mandatory**）；备份 `/etc/environment.bak-20260923`（md5 `f3377ed5…`） |
| ② | **C 站推升级** | ✅ studio 到位（**2026.9.7**）；**引擎未动** | 走"更新器 Python 阶段直调"（§8.3）；判据 ctl **0**、档位 `ctx 131072/:8080/ROCm0` 未变 |
| ③ | **B 的 `triton_kernels` 拷平** | ✅ | A→B tar；聚合指纹 `03e308bf…` 一致；`pip list 1.0.0` + `import OK`；A/B 差异只剩版本级 |
| ④ | **落档** | ✅ | 本 §八 + [OPEN-ISSUES §O-23](../spec/d6-agent-standard/OPEN-ISSUES.md) + [DEVELOPMENT-LOG 第 ⑪ 条](../spec/d6-agent-standard/DEVELOPMENT-LOG.md) |
| ⑤ | **表块列数修平** | ✅ | 全文件 **10 表块 / 异常 0**；逐行"删插入后逐字还原原行"断言通过（§8.5） |

### 8.2 pin 为什么落 `/etc/environment`（而不是 `.bashrc`/`.profile`）

| 候选机制 | 对**非交互 ssh**（我们的 `update` 调用方式）是否生效 | 结论 |
|---|---|---|
| `~/.bashrc` | ❌ Ubuntu 默认有 `case $- in *i*) ;; *) return;; esac` 守卫，非交互直接返回 | 不用 |
| `~/.profile` | ❌ 仅**登录** shell 读；`ssh host 'cmd'` 非登录 | 不用 |
| **`/etc/environment`** | ✅ **经 `pam_env.so`**（`/etc/pam.d/sshd:44` `session required pam_env.so`）对**每个 ssh 会话**（含非交互命令）设置 | **采用** |

**为什么这条重要**：`studio update` 走 ssh 非交互执行 ⇒ 若只写 `.bashrc`/`.profile`，**pin 等于没落地**。且 studio 进程（由 `infer-load` 经 ssh 拉起）继承该会话环境 ⇒ **UI 内的 "Update llama.cpp" 按钮同样受保护**。
**单一真值点**：只写一处，避免 `.bashrc`/`.profile`/`/etc/environment` 三处漂移。
**断言（作用点真的改了）**：三站 `llama_backend_from_env() = rocm`、`effective_backend_request() = ('rocm', True)`、`force_vulkan_requested() = False`。
**影响面**：该变量只被安装器读（预编译包选型）；运行时不读 ⇒ 对推理无副作用。**回滚**：`/etc/environment.bak-20260923`。

### 8.3 C 站推升级：被 **GitHub 出网**阻断 → 改用"更新器 Python 阶段直调"

**原计划**：与 A 同流程 `unsloth studio update`（pin 已生效）。**实测阻断**：
- C 站 `github.com` **完全不通**（`curl` 10 s 0 字节）；A 的 mihomo 在监听但**上游节点失效**（`api.github.com` 200 而 `github.com` 000）；**本仓 Windows 控制站到 GitHub 同样超时**；只有 **B 直连 ~33–35 KB/s** 可用。
- 量化影响：`latest` = **`b11030-mix-5ff778e`**，其 **`…-linux-x64-rocm-gfx1151.tar.gz` = 337.4 MiB**（对照：**Vulkan bundle 仅 29.1 MiB**）。各可用下源实测吞吐：B 直连 ~35 KB/s、A 经代理 ~79 KB/s、镜像 `ghproxy.net` ~74 KB/s ⇒ **337 MiB 需 1.3–2.7 小时**。
- ⇒ **不是"慢"，是"C 上没有任何可完成该 337 MiB 下载的通路"** ⇒ 引擎步不可完成。

**转用路径（不使用 `studio update`，但仍是更新器自己的入口）**：
- **关键源码事实**：`install_python_stack.py` **本身就负责安装 `unsloth` + `unsloth-zoo`** —— 源码逐字："`install.sh` sets `SKIP_STUDIO_BASE=1` to avoid reinstalling the core packages; **`studio update` does NOT set it, so unsloth + unsloth-zoo are reinstalled** to pick up new versions"（包名由 `STUDIO_PACKAGE_NAME` 指定，默认 `unsloth`）。且其安装走 `pip_install()` ⇒ **尊重 uv/constraints** ⇒ **不会换掉 ROCm torch**。
- ⇒ `studio update` = **Python 阶段** + **Node 阶段** + **引擎阶段**；C 只需第一阶段 ⇒ **直调 `install_python_stack.py`**，其调用方式与 `studio update` 内部完全一致（同一函数、同一 env 约定）。
- **两个 GitHub 依赖的处置**：`triton_kernels`（走脚本自带的 `_has_working_git()=False` 跳过分支；C 本就有该包 ⇒ 零损失）与**收尾阶段的 bitsandbytes 强制重装 GitHub wheel**（从 B **LAN 拷平同一 artifact** ⇒ 该步改为报 `bitsandbytes (AMD) is already this build -- keeping it`）。
- **结果**：`deps installed`（17/17）、**`unsloth_install_manifest.json` 写出**（3222 B）、**引擎 md5 全程未变**（`31d8787b…`）⇒ **三站引擎仍逐字节同版**。
- **版本压回**：镜像 latest 已是 **2026.9.8**（9.7 之后的 patch）⇒ 按裁定"目标版本 2026.9.7"压回 ⇒ **三站 studio 版本一致**。
- **登记一处不一致（不修）**：C 的 `unsloth_install_manifest.json` 记 `package_version: 2026.9.8`（**它写出那一刻的实况**），而站上现为 `2026.9.7`（事后按裁定压回）⇒ **刻意不改 manifest** —— 改它等于伪造 pass 记录；下次 update 会自然对齐。

**C 站判据（与 A 同口径）**：档位 `ctx 131072` / `:8080` / 设备 `ROCm0` **未变**；经 studio 流式 **控制帧 `ctl = 0`**（升级前 **2**）；帧数/字节 **127 / 24869–24882**，**与 B 站（2026.9.7）逐字节一致**。**全量门禁 15 绿 / 1 黄 / 0 红**。

### 8.4 性能测量："升级后的 unsloth 有性能提升吗" → **无提升，亦无回退证据**

**设计**：B（2026.9.7）vs **C（升级前 2026.9.2）**—— 同硬件、**同引擎 `build 10715`（md5 逐字节同）**、同 conf（`gpt-oss-120b`：同 `MODEL_PATH`/`CTX=131072`/`THREADS=16`/`N_CPU_MOE=0`/`RPC_TARGET` 空/`BACKEND=unsloth`）⇒ 唯一变量 = studio 版本。先测 C（未升级）后测 B，各 3 次。

**⚠ 口径更正（本轮自查）**：`cluster.py flow bench` 的端口来自 `_flow_step_probe_engine`，是**引擎内层端口**（如 `:43149`）⇒ 它**直连 `llama-server`、不过 studio** ⇒ **那组 pp/tg 与 studio 版本无关**，只能当"引擎层对照"，不能当"升级效果"。

| 层 | 指标 | B（2026.9.7） | C（2026.9.2） | 判读 |
|---|---|---|---|---|
| **引擎**（直连，flow bench） | tg ×3 | 47.3 / 36.0 / 45.8 t/s | 48.3 / 39.9 / 52.0 t/s | 站内极差 ~40% ⇒ **噪声内** |
| **引擎启动参数** | 全部 | `-c 131072` · `--flash-attn on` · `--no-context-shift` · `--parallel 4` · `--kv-unified` · `--cache-type-k/v q8_0` · `--spec-default` · `--chat-template-kwargs {"reasoning_effort":"high"}` · `-ngl -1` · `--fit off` · `--load-mode none` | **逐项相同**（唯一差异：B 多 `--video-fps 1`，与文本解码无关） | **无提升机制** |
| **网关/流式**（经 studio） | 控制帧 `ctl` | **0** | **2** | **确定性改进** |
| | 帧数 / 字节 | **127** / 24869–24882 | **130** / 25431–25446 | 每响应 **−3 帧 / −~560 B（−2.2%）** |
| | TTFT（中位） | 10.0 ms | 8.9 ms | 同量级 |
| | **`usage.prompt_tokens`** | **1621** | **871** | ⚠ **studio 注入前缀 +750 token** |
| **端到端稳态** | total（中位，缓存对齐后） | 1.66 s | 1.94 s | 站内极差 1.2–3.8 s ⇒ **噪声内** |

**⚠ 本轮新发现 —— studio 注入前缀 +750 token（归因已完成）**：同一请求，**经 studio** 时 `prompt_tokens` = 871（C/9.2）vs 1621（B/9.7），差 **750**，稳定复现（×3、两种消息长度）。**归因取证**：**直连引擎**（绕过 studio）同 payload，两站 `prompt_tokens` **均为 68** ⇒ 差额**完全由 studio 产生**（非引擎、非模板、非 payload）。**影响**：该前缀**可被 KV 前缀缓存命中**（`cached_tokens` 同步 +750）⇒ 稳态下**不逐请求重付**；但 ① 每请求多吃 ~750 token 的**上下文窗口**；② 首次/缓存失效时多付 ~750 token 的 prefill。**未追**：为什么要加这 750 token（未比对两版前缀内容）。

**⇒ 结论**：**升级不含吞吐提升**（引擎同二进制同参数，无机制），**也没有可归因的回退**（差异在跨机 + 单流噪声内）。**净收益 = 控制帧移除**（流更干净、每响应 −~560 B，且压缩路径恢复可用）；**净代价 = 注入前缀 +750 token 占 ctx**。

**诚实边界**：① 是**跨机对照**（B vs C），非同机前后；② 单流、n=3、站内极差达 40% ⇒ 分辨力约 ±10%，**只能支持"无显著差异"，给不出系数**；③ 要精确系数应做**同机前后**或 `llama-bench`（多轮 + stddev）。

### 8.5 OPEN-ISSUES 三个表块列数不一致：已修平（含度量口径教训）

**三个块的性质不同**（这才是修法不同的原因）：
- **块 1**（`§1 未决问题总览`，L24-52）：**真 8 列表**（`ID | 类别 | 严重度 | 简述 | 状态 | 归属批次 | <br /> | <br />`，尾部两列是空的 `<br />` 填充）。异常 2 行：**L48 少 1 格**（7 vs 8）、**L51 多 1 格**（9 vs 8）。
- **块 2 / 块 3**（§D6 闭环审查 两节）：**3 列表**（`条目 | 说明 | 待办`）。异常 9 行，成因是 **prose 内未转义的 `|`**（HTML→MD 转换残留，含 `<label>`/`<sub>` 与正则里的 `|`）。

**修法（零内容损失）**：
- 块 1：L48 **追加一个纯填充格**；L51 **去掉一个纯填充格**。
- 块 2/3：**只转义"多余"的内部管道** —— 保留 `首 |`、`条目后 |`、`尾 |`（有行尾 `|` 时再保留倒数第二个），其余转义为 `\|`。

**护栏（断言）**：对 9 行转义行，"**删掉所插入的每一个反斜杠后必须逐字还原原行**" + "新列数 = 3"；对 L48 "= 原行 + ` <br /> |`"、L51 "= 原行去掉一个填充格"。**首轮两条被判据正确挡下**（我记录了插入位置，但后续插入使位置失效 ⇒ ≥2 次转义的 3 行不还原）⇒ 改为**升序插入并按 `esc[i]+i` 记最终位置**后全部通过。**复核：全文件 10 表块 / 异常 0**。

**⚠ 度量口径教训（可推广）**：**"未转义管道数" ≠ "格数"** —— GFM 允许**省略行尾 `|`**，此时 `格数 = 管道数`（而非 `管道数 − 1`）。本轮两个自写探针正是因此给出**互相矛盾**的异常清单 ⇒ **判据必须固定用哪一个口径**（本仓取"**格数**"为准，并把它写进断言）。

### 8.6 三站现状（第二轮收口后实测）

| 站 | studio | 引擎（`~/.unsloth/llama.cpp`） | 包数 | pin 生效 | 状态 |
|---|---|---|---|---|---|
| **A** | **2026.9.7** | `build 10715` / `ROCm0`（md5 `31d8787b…`） | 264 | ✅ | 已收口 |
| **B** | **2026.9.7** | 同上（逐字节同） | 265 | ✅ | 试点通过 + 补齐 + `triton_kernels` 拷平 |
| **C** | **2026.9.7** | 同上（逐字节同） | 264 | ✅ | **已推**（Python 阶段）+ 判据通过 |

**门禁**：**15 绿 / 1 黄 / 0 红**（黄 = 既存 `claude-plugins-official` known_drift）；`backend` PASS、`gates` 站上件一致 **24/24**、`engine` 三站可达且 **0 在服务**。

**仍登记的两项差异**：① **引擎构建号**三站同为 `b10715`（**特此说明**：本轮**刻意没有**让 C 的引擎升到 `b11030` —— 既因 GitHub 阻断，也因"三站引擎同版"是本仓既定形态）；② `unsloth_zoo` B/C = `2026.9.7`、A = `2026.9.6`（版本级，非缺失）。
