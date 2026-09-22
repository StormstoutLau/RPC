# 升级决策简报 —— unsloth studio 升级（网关 UI 控制帧致本地 provider 压缩失效）

- **日期**: 2026-09-22
- **状态**: **待裁**（方案 A/B/C + 试点步骤与判据已备齐；本简报**不含未取证结论**）
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

版本面：`unsloth 2026.9.2 → 2026.9.7`、`unsloth_zoo 2026.9.1 → 2026.9.6`、`bitsandbytes 0.50.2 → 0.50.3.dev0`、**`pyarrow 25.0.1 → 23.0.1`（意外降级，待解释）**；包总数 **235 不变**；`X-Unsloth-Events` 命中 **0 → 2**。

### 7.3 ⚠ 范围外发现：`studio update` **会替换引擎**

- 日志：`requested llama.cpp tag: latest (repo: unslothai/llama.cpp)` → `installing prebuilt llama.cpp...` → `Downloading llama.cpp-source-<sha>.tar.gz（36.1 MiB）` → **随后本地编译**（A 站实测 **169** 个 cmake/g++ 进程）。
- **`--help` 无任何跳过引擎的开关**（仅 `--local` / `--package` / `--verbose` / `--verify`）。
- ⇒ **影响**：① **三站引擎版本将不一致**（B 引擎未动、A 被替换）；② 偏离引擎治理面 `/opt/llama.cpp-9859`（**注：update 目标是 `~/llama.cpp`；本次实测 `/opt/llama.cpp*` 三个入口未被触及**）；③ 需为 `~/llama.cpp` 面**另立回滚点**。
- **简报原评估遗漏此条**（仅提示"可能牵连引擎启动参数"，未料到**直接换二进制**）。

### 7.4 执行中遇到的三个网络瓶颈与处置（可复用）

| 瓶颈 | 现象 | 处置 |
|---|---|---|
| `uv` → PyPI 走 **IPv6**（Fastly `2a04:…`） | **8 分钟 CPU 仅 1s、零进展** | **清华镜像 env**（`UV_INDEX_URL`/`UV_DEFAULT_INDEX`/`PIP_INDEX_URL`）⇒ 解卡 |
| `bitsandbytes` 从 **GitHub release 直链**（`--no-cache-dir`） | 稳定 **~30 KB/s**（asset **41.1 MiB** ⇒ ~25 分钟） | 先用 `gh api` 查 **asset 大小** ⇒ **量化 ETA** 后决定"等"；A/C 走代理则快 |
| `triton_kernels @ git+https://github.com/triton-lang/triton.git` | `git fetch` **零字节卡死**（git 默认无低速超时 ⇒ 会挂数小时） | B 站**收口**（kill）；**脚本本身有 `triton kernels (skipped, no git)` 分支**；**A/C 已装 `triton_kernels 1.0.0` ⇒ 该步可跳过** |

- 公共 GitHub 代理（ghfast / ghproxy / gh-proxy）**实测均不可用**；**A 站本机 clash（`127.0.0.1:7890`）可用**（GitHub 握手 **0.46s**，对比直连 0 字节）；**C 站经 SSH 隧道复用 A 的代理**（实测有活跃连接）。

### 7.5 三站当前状态

| 站 | studio | `X-Unsloth-Events` | 引擎面 | 状态 |
|---|---|---|---|---|
| **B** | **2026.9.7** | **2** | 未动 | **试点通过**；但 update **未跑完**（卡 `triton_kernels` 后收口）⇒ **`triton_kernels` 缺失**（A/C 有 1.0.0） |
| A | **2026.9.7** | **2** | **替换中**（下载完、编译中） | 执行中 |
| C | 2026.9.2 | 0 | 未动 | **已暂停**（freeze 与基线**零差异**、Node 未装完、无锁残留） |

### 7.6 顺带纠正两处简报假设

1. **"三站 studio 版本不一致会致门禁 `backend` FAIL" —— 不成立**：B 升级后门禁仍 **15 绿 / 1 黄 / 0 红**、`backend` PASS（该断言查**引擎后端与 ROCm 串**，**不查 studio 包版本**）。
2. **`verify-install` 基线即 `rc=1`**（官方语义"安装未完成"）⇒ B 升级后仍 `rc=1`，**非本次造成** ⇒ 该判据**在本环境不可用作"完整性"判据**。
