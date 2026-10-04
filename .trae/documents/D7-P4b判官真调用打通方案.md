# D7 P4b「判官真调用」打通方案（先取证 · 后续定档）

> 状态：**已执行（2026-10-04）** —— Step 0 / 1 / 2 / 3 / 4 全部落地；判官真调用**已打通**（首次 `sem_verified`）。执行结果见文末 §六。

---

## Context（为什么做这件）

D7 六相协议的 **P4b 语义复核**从未真正跑成。实测根因不是判据缺失，而是**判官调用链的最后一跳断了**：

- 判官别名解析优先级（[agent-cli.ps1 L5561-5568](file:///d:/RPC/ops/station-bin/agent-cli.ps1#L5561-L5568)）：`--model` > 卡面 `review-model` > `local-only` 默认 `main` > 其余默认 `ultra`。
- C 段真跑时产出者是出网档 `ultra` ⇒ 自审门排除同名 ⇒ [`Select-Reviewer`](file:///d:/RPC/ops/station-bin/agent-cli.ps1#L5412-L5459) 按「跨档优先 + alias 序」选到 **`m27`**（`type=http-local`）。
- `m27` 分支要求 `$env:REVIEW_HTTP_BASE`（[L5170-5176](file:///d:/RPC/ops/station-bin/agent-cli.ps1#L5170-L5176)），未设 ⇒ 抛 `JUDGE_UNREADY` ⇒ 判官调用失败 ⇒ `$judgeObj` 为空 ⇒ 按设计**如实**传 `-L2Ran $false`（[L5828-5833](file:///d:/RPC/ops/station-bin/agent-cli.ps1#L5828-L5833)）⇒ 相序列走 `collected → mech_verified → accepted`，**无 `sem_verified`**。

**目标产出**：让判官**真调用一次并返回可解析 JSON** ⇒ 走成功路径（[L5933-5934](file:///d:/RPC/ops/station-bin/agent-cli.ps1#L5933-L5934)：`-L2Ran $true`）⇒ 相序列含 `sem_verified`、`review.json.d7_verdict.l2_marks[]` 与结论契约 `contract.ok` 首次拿到**真样本**。

**解锁的 5 项**（[untested-index.yaml](file:///d:/RPC/inventory/untested-index.yaml#L65-L79)）：
D7-PROTOCOL-CONTRACT **#5（P4b）** · D7-PROTOCOL-CONCLUSION-CONTRACT **#1 / #2 / #3 / #8**（均卡在"判官真调用/零 `review.json`"）。

---

## 一、取证结论（E1，本轮只读实测）

### 1.1 为什么主控碰不到站上引擎
- 判官 `http-local` 由**主控进程**直发 HTTP（[`Invoke-JudgeHttp` L5079-5125](file:///d:/RPC/ops/station-bin/agent-cli.ps1#L5079-L5125)）。
- 站上引擎已绑回环：`llama-serve-instance` 硬编码 `--host 127.0.0.1 --port ${PORT:-8080}`（[L51-61](file:///d:/RPC/ops/station-bin/llama-serve-instance#L51-L61)），`inventory/ports.yaml` 的 `expect_bind: 127.0.0.1`（[L56-68](file:///d:/RPC/inventory/ports.yaml#L56-L68)）。
- 全仓现役站上访问姿势 = 「`ssh <站>` + `curl 127.0.0.1:8080`」；**无任何主控直连站上引擎的先例，也无隧道先例**。
- ⇒ **2026-10-03 的绑定加固（`0.0.0.0 → 127.0.0.1`）与 `REVIEW_HTTP_BASE` 这条老路直接冲突** ⇒ 这是"墙"的第一层。

### 1.2 A/C 引擎栈差异的根因（站上 conf 实证）
| | A 站 | C 站 |
|---|---|---|
| `:8080` 进程 | `/opt/llama.cpp/llama-server`（Vulkan 分布式二进制） | `unsloth studio run`（代理层）→ 真 llama-server 在随机端口 |
| conf `BACKEND` | **无该行**（未迁移） | `BACKEND=unsloth`（conf 内原话注释：「原: `BACKEND=llama-single` + `LLAMA_SERVER_BIN=llama-gfx1151`(实验件) -> 改为 unsloth (studio HIP)」，2026-09-17） |
| `/v1` 鉴权 | **免 key** | **需 API key**（实测 `Not authenticated`） |
| systemd | `llama-server@gpt-oss-120b.service`（active） | 无该单元（studio 另起） |

- 两者 `PORT=8080` / `RPC_TARGET=` 相同，**唯一差别 = A 未迁移到 `BACKEND=unsloth`**。
- 但 `ports.yaml` 把 8080 的 owner 登记为 **`unsloth studio (后端 llama-server)`** ⇒ **A 站 8080 的占用者与登记不符**。
- 门禁 `backend`（[rpc_check.py L5894-5940](file:///d:/RPC/ops/rpc_check.py#L5894-L5940)）只查「studio 可执行件在 + 后端=HIP + `/opt` 是 Vulkan + 回滚基线」——**不查"8080 上实际跑的是哪条路径"** ⇒ 该不一致**在门禁层不可见**（同 `O-144` 的射程缺口形态）。

### 1.3 相关的规则面（决定"怎么做才合法"）
- **ADR-0004 D1**：管理操作只走 `ops/cluster.py`（+ web 同入口），**不新增并列入口**。
- **D2**：真实差异**可登记**，但登记动作要在 review 可见（同 `plugins.yaml::known_drift` 纪律）。
- **D3**：新增脚本三条合法路径（并入入口 / 登记 `station_runtime` / `frozen_ops_scripts` + 说明）；探针放 `tmp/`。
- `infer-load` 已在 `station_runtime` 登记（统一路径），默认后端即 `unsloth`。
- ⚠ `infer-load` 经 `sudo` 跑会以 root 执行 ssh（无节点密钥）——见 `ops/station-bin/README.md` 的既有注意事项 L86。

---

## 二、判官目标对照（★ 待裁）

前提：引擎**忽略请求里的 `model` 字段**（[ports.yaml L65-67](file:///d:/RPC/inventory/ports.yaml#L65-L67) 逐字：「传 `__bogus__` 仍返回 200」）⇒ 传什么 id 都返回结果，但 **`review.json.metadata.judge_model` 必须记真**（否则=本仓头号失败形态）。

| 方案 | 目标 | 载入动作 | key | 记录对齐 | 代价 |
|---|---|---|---|---|---|
| **① 载 m27-q4ks 到 C**（推荐） | C（判官表 `m27` 的 `station='C'`） | `infer-load m27-q4ks`（**顶掉 C 现有 gpt-oss**，单槽） | 需（`~/.config/rpc/unsloth.key`） | ✅ id 与 station **均对齐** | 一次加载 + 占位；C 的 gpt-oss 需事后重载 |
| ② 载 m27-q4ks 到 A（对齐后） | A | 同上 | 需 | ✗ station 应为 C ⇒ 需改判官表 | 同 ① + 改表 |
| ③ 用已载 gpt-oss，不动模型 | A 或 C | **无** | 需（若 studio） | ✗ 需**新增/订正** `JUDGE_TABLE` 项（id=`gpt-oss-120b-MXFP4`） | 改判官关键表 + `_fm_golden_test` 覆盖率断言 |

**推荐 ①**：最忠于原设计（id/station 天然对齐、零改判官表），且 `m27-q4ks.env` 在 **A/C 都已有 conf**（`PORT=8080`）。

---

## 三、分步方案

### Step 0 — 对齐 A 站引擎到 unsloth（用户已裁）
- 走**统一路径**：站上 `infer-load`（已登记 `station_runtime`），把 A 的 `gpt-oss-120b` 切到 `BACKEND=unsloth`（对齐 C 的形态）；如需直改 `/etc/llama-instances/gpt-oss-120b.env`，**必须同步 `/run/llama-instances/` 覆盖层**（`llama-serve-instance` L12-22 会重新 source）。
- 落地后：A 站 8080 占用者 = studio，与 `ports.yaml` 登记一致。
- ⚠ **后果**：A 的 `/v1` 将**改为需要 key**（studio 特性）——"A 免 key"这一便利消失，判官目标对照表需按此重估。
- ⚠ 注意 `sudo`/节点密钥坑（README L86）。

### Step 1 — 甲·SSH 隧道取证（零改码，先拿铁证）
手工运行态，**不进仓**（符合 D3「探针放 tmp / 不新增并列入口」）：
1. 确保目标站已加载目标模型（8080 单槽）。
2. **加载之后**再读该站 `~/.config/rpc/unsloth.key`（`infer-load` 每次加载会**重铸**该 key，顺序不能反）。
3. 主控开隧道：`ssh -N -L 18080:127.0.0.1:8080 <站 host>`（A=`scott-lau-NEX.local`、C=`192.168.10.37`）。
4. 设 `$env:REVIEW_HTTP_BASE='http://127.0.0.1:18080/v1'`、`$env:REVIEW_HTTP_KEY='<key>'`。
5. 跑 `agent-cli.ps1 review <proj> -Card <card> -RunId <ts>`。
6. 取证完关闭隧道；**key 不进日志/不落盘**。

### Step 2 — 判官目标（§二 待裁后执行）
按裁定的方案执行载入/表项调整，再重复 Step 1 的第 3–5 步。

### Step 3 — 回写索引与台账（取证成功后）
- `inventory/untested-index.yaml`：D7 #5 与结论契约 #1/#2/#3/#8 的 `gist` 记真读数（`state` 是否改按"射程是否仍缺"判，**不预设**）。
- `spec/d6-agent-standard/D7-PROTOCOL-CONTRACT.md` §未实测登记 5；`D7-PROTOCOL-CONCLUSION-CONTRACT.md` 对应条目；`OPEN-ISSUES.md` 相关条目（`O-135`/`O-136`）。
- 若 A 对齐落地 ⇒ 同步 `ports.yaml` / 相关注记，使"A 站 8080 占用者"事实可见。

### Step 4 — 门禁验证
`py ops/rpc_check.py`（期望 绿 45 · 黄 3 · 红 0）· `py tests/test_untested_index_sync.py`（ALL PASS）· `ps1-golden` 535/0 · `py-tests` 48/48 · `spec-untested` 报数随动。

---

## 四、未决与风险
1. **判官目标**（§二）待裁。
2. **隧道是手工态**、不可复现 ⇒ 若要把这条路变成可复现，须另立「丁·站上 curl」（改 `http-local` 分支，复用 `Invoke-RemoteCapture`，同 `egress` 分支姿势）——**属另一件**，须先改裁 + 补离线夹具。
3. **`O-140` 时序约束**：`review.json` 是证据链钉住的 subject ⇒ 对**已入链** run 做 review 会撞 `digest 不符`（门禁 `evidence` FAIL）。正确姿势 = **在该 run 入链之前 review**；否则须 `--allow-after-chain` 并事后恢复归档件字节。⇒ 取证宜用**新派发的卡**先评后链。
4. A 站对齐会**改变其 `/v1` 鉴权要求**（免 key → 需 key），影响面需在落地时确认（station provider 配置是否已带 key）。

---

## 五、验证方法（怎么算"打通了"）
一次成功的 review 应出现**铁证**（stdout + `review.json`）：
- stdout：`REVIEW score=… pass=… judge=local/m27-q4ks elapsed_s=…`；`D7_VERDICT_OK: Verdict 信封字段级合法`；`D7_PHASES: collected -> mech_verified -> sem_verified -> accepted`。
- `review.json`：`d7_verdict.l2_marks[]` **非缺席**（此前 L2 没跑 ⇒ 缺席）；`contract.ok` 为真样本；`metadata.judge_model` = 目标站**实际加载**的模型名（不得为假）。
- 门禁四项（Step 4）全绿。

---

## 六、执行结果（2026-10-04 · 已落地）

**Step 0 — A 站对齐 unsloth【已落】**：`py ops/cluster.py load gpt-oss-120b --backend unsloth`（统一入口；自动路由 A）。
读数：`READY ✓ :8080 (unsloth gpt-oss-120b)` · A 站 `/v1` 由 `noauth=200`（llama-single）变为 **`auth=200 / noauth=401`**（studio）⇒ **与 C 站同形态、且与 `ports.yaml` 登记的 owner 一致**。
★ 根因取证（读码）：A 站 conf **无 `LLAMA_SERVER_BIN`** ⇒ `llama-serve-instance` L58 `exec "${LLAMA_SERVER_BIN:-/opt/llama.cpp/llama-server}"` 缺省即 `/opt/llama.cpp/llama-server`（Vulkan 分布式二进制）—— 这精确解释了对齐前 A 站 8080 的占用者。
⚠ **候选发现（未立条目）**：门禁 `backend` 只查「studio 可执行件 + HIP + `/opt` 是 Vulkan」，**不查"8080 上实际跑的是哪条路径"** ⇒ A 站"未迁移"这一状态在门禁层**不可见**（同 `O-144` 射程缺口形态）。是否立条目待裁。

**Step 2 — 判官目标【已落，站位有调整】**：由方案 ① 的 **C** 改为 **B** —— 理由：B 站**离线（无引擎在服务）⇒ 零位移**；而 C 正在服务 gpt-oss（载 m27 会顶掉它）。★ 记录仍为真：`m27` 表项的 `station='C'` 对 `http-local` 分支**不参与**（只 `egress` 分支用 `station`，见 agent-cli.ps1 L5132），唯一必须为真的是 **`id`**。
命令：`py ops/cluster.py load m27-q4ks-b --backend unsloth`。
⚠ **`infer-load` 报的健康检查超时是竞态、不是加载失败**：引擎已起（`/v1/models`→401 表示在服务）、GTT 113 GB 已驻留；`infer-load` 铸 key 与 studio 生效之间有先后差 ⇒ **事后三处 key 同 sha8、`/v1/models`→200**。

**Step 1 — 甲·隧道取证【已成】**：`ssh -N -L <port>:127.0.0.1:8080 scott-lau-GTR-Pro.local` + `REVIEW_HTTP_BASE=http://127.0.0.1:<port>/v1` + `REVIEW_HTTP_KEY=~/.config/rpc/unsloth.key`（在站上读）。
**铁证**（run **`202610042342034271`**，卡 `dogfood-cards/glob-probe.md`，判官 `m27`）：
- `REVIEW score=pass pass=True judge=local/m27-q4ks elapsed_s=89`
- `D7_PHASES: collected -> mech_verified -> **sem_verified** -> accepted`（**首次出现 `sem_verified`**）
- `review.json`：`metadata.call_code=0` · `retries=0` · **`contract.ok=true`** · **`d7_verdict.l2_marks[]` 非缺席** · `d7_guard` 全 0 且 `transition.hops=3` · `self_review_guard=ok` · `PRH` **分离**。

**Step 3 — 回写【已落】**：契约 2 份（`D7-PROTOCOL-CONTRACT.md` §未实测 5 · `D7-PROTOCOL-CONCLUSION-CONTRACT.md` §未实测 1/2/3/8）· 索引 5 条（D7 `n:5`；结论 `n:1/n:2/n:3/n:8` → `state=partial`）· 台账 `O-136`。
**Step 4 — 门禁【全绿】**：`py ops/rpc_check.py` → **PASS · 绿 45 · 黄 3 · 红 0**；索引对账 **ALL PASS**（`todo` 21→18 · `partial` 23→26 · `blocker` `run` 14→15 / `implementation` 26→25）。

**★ 关键口径：`/v1` 鉴权** —— 引擎只认 **`Authorization: Bearer <key>`**（`x-api-key` 实测 401）；key 取 **`~/.config/rpc/unsloth.key`**（= `infer-load` 从 studio 日志 grep 并落盘的那把；与 `~/.unsloth/studio/auth/.cli_api_key_*` 同值）。

⚠ **未做（如实）**：① **未提交 / 未 push**（工作树有改动）；② **B 站仍载 m27-q4ks**（GTT ≈113 GB，取证后**未卸载**）—— 待定是否 `cluster.py unload m27-q4ks-b`；③ 可复现化（丁）**未立项**；④ 出网判官（ultra/commercial）真调用**仍未跑**；⑤ `PRH` 定档仍缺读数（2 条）。
⚠ **安全问题（如实报告）**：本轮一次探测命令的 `printf` 把 **studio key 明文**回显进了会话记录（该写法已停用）⇒ 建议**轮换**该 key。

---

## 七、补充执行（2026-10-05 · 用户追加 5 项）

1. **提交【已落】**：`194db3a`（7 文件；钩子把 run `202610042342034271` 入链 ⇒ 证据链 295→296）。
2. **B 站回收【已落】**：⚠ 用户给的 `cluster.py unload m27-q4ks-b` **语法并不存在** —— `cluster.py unload` 是**三站并行卸载**（`cmd_unload()` L989，会连 A/C 一起停），**无 `--station`**。⇒ 按**意图**改跑 `ssh scott-lau-GTR-Pro.local infer-unload`：`models_http=000` · 进程空 · **GTT 113 GB → 566 MB** ✓（顺带停掉两个**空闲** rpc-server worker；A/C 跑单机、不依赖）。
3. **key 轮换【未成 · 待你裁】**：C 站重载（`py ops/cluster.py load gpt-oss-120b-c --backend unsloth`）后 key **sha8 未变（仍 `56bf7d0b`）** ⇒ **studio 复用持久化的 key，重载不重铸**。取证：`unsloth studio --help` **无 key/auth/rotate 选项**；`auth/.cli_api_key_cli_*` 时间戳仍是 **9月23**；`~/.config/rpc/unsloth.key` == 该文件（同 sha8）。⇒ 唯一可行路 = **删除/替换** `~/.unsloth/studio/auth/.cli_api_key_cli_*` 再重启（**未官方支持、未验证**）—— 属**改 studio 内部件**，**未擅自动手**。
4. **出网判官真跑【已成】**：run `202610050017146963`（产出者 `local/gpt-oss` ⇒ 判官落 `ultra`）：`judge_model=openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` · `call_code=0` · `elapsed_s=144` · `contract.ok=true`（`verdict=reject` · 1 finding）· `l2_marks` 非缺席 · `score=不合格`。★ 至此 **本机档（m27）与出网档（ultra）两面均有真跑样本**（此路**不需要**隧道/引擎 —— egress 走 ssh 到 B 跑 opencode）。
   ⚠ 关键：**产出者不得与判官同名** ⇒ 想测出网判官，须用**本机档产出**（否则自审门排除 `ultra` ⇒ 回落到需 `REVIEW_HTTP_BASE` 的 `m27`）。
5. **`backend` 门禁缺维【调研完 · 待裁是否立项】**：见 §八。

## 八、`backend` 门禁缺"8080 实际占用者"一维（调研 · 待裁）

**缺口为真（读码取证）**：`_BACKEND_CMD`（[rpc_check.py L5859-5888](file:///d:/RPC/ops/rpc_check.py#L5859-L5888)）只收**磁盘上的件** —— `~/.unsloth/.../llama-server` 的 `ldd` · `/opt/llama.cpp/{llama-server,ggml-rpc-server}` 的 `ldd` · `/etc/environment` 的 pin · studio 套件版本；判据（L5921-5944）只问"**这两条路径的二进制在不在、后端类型对不对**"。⇒ **从不问「:8080 上到底是谁在听」**。
**实证**：对齐前 A 站跑的是 `/opt/llama.cpp/llama-server`（Vulkan 二进制）占着 8080，而 `backend` 判据**PASS**（它只确认该二进制存在且是 Vulkan）⇒ "未迁移"这一状态**在门禁层不可见**（同 `O-144` 形态）。

**修法候选**（纪律：**先报数、不改灯** —— 同 `O-143` 两步走）：
- **(甲) 只加报数**：`_BACKEND_CMD` 增一段"8080 占用者"（`ss -ltnp` 或按端口取 pid → `readlink /proc/<pid>/exe` + cmdline），分类 `studio` / `opt-vulkan` / `other` / `none`，**只打、不进判定**（零假红、零门槛变更）。
- **(乙) 加判据**：占用者 ∉ 期望 ⇒ WARN/FAIL。★ 代价：**判据变更须先验红 + 夹具**；且 `ports.yaml` 已登记「`mode: on_demand` · **未监听属正常**」⇒ 必须先定义"没加载时算不算违规"。
- **(丙) 不立项**：登记为**已知射程边界**（"门禁判的是**装了什么**、不判**在跑什么**"）。

**建议（非裁决）**：**先只做甲**（报数），观察是否真出现"占用者 ≠ 登记 owner"的实例，再谈乙（**先量后定档**）。⚠ 若选乙，须先明确"8080 空闲"这一**合法态**（`ports.yaml` 已写）。

## 九、上游 / 根因调研结论（2026-10-05 · 用户令「先查上游是否有轮换口子」「先调研原因再给方案」）

### 9.1 key 轮换：**上游有受支持口子**（不是野路子）
站上读码（`unsloth_cli/commands/studio.py` L699-748）：
- `_cli_api_key_secret_path()` = `STUDIO_HOME/auth/.cli_api_key_<safe>_<digest>`（与实测文件逐字一致）；
- ★★ `_create_api_key_inprocess(name)` 的 docstring 逐字 = *"Return a raw API key for \*name\*, **minting only when the cached one is dead**"*，逻辑为：
  `cached = _read_cli_api_key_secret(name)`；`if cached and storage.validate_api_key_with_credential(cached, touch=False): return cached`；**否则** `storage.create_api_key(...)` + `_write_auth_secret(_cli_api_key_secret_path(name), raw_key)`。
⇒ **"重载不重铸"的根因 = cached 仍有效 ⇒ 走 `return cached`**（是设计，不是 bug）。
⇒ **受支持的轮换路径 = 让 cached 失效**：① 删 `~/.unsloth/studio/auth/.cli_api_key_*`（下次启动即 mint 并落盘）；或 ② 在 `auth.db` 里撤销该 key。
⚠ 无 `rotate`/`revoke` 专用子命令，`unsloth studio --help` 也没有 —— **但"删缓存 ⇒ 重新 mint"就在上游设计内**（同函数里那行 `Warning: … the next one will create another key` 逐字为证）。

### 9.2 `backend` 缺维的**根因**（不是"忘了写"，是分工缝隙）
- `check_backend` 判**装机面**：「studio 二进制在不在 + 后端=HIP · `/opt` 二进制在不在 + 后端=Vulkan + pin + 套件版本」。
- `check_engine`（[rpc_check.py L5799-5832](file:///d:/RPC/ops/rpc_check.py#L5799-L5832)）判**运行面**，但其职责逐字 = "**就绪 + 残留检测（内存被占着但没有服务）**"，判据是 `classify_engine_band(ports, rss, n_proc)` ⇒ **只问"在不在服务 / 是不是残留"，不问"服务的是哪条路径的引擎"**。
⇒ ★ **"运行中的引擎来自哪条路径"这一维落在两个门禁的缝里，两边都不判**。
- ★ 更深一层（A 站静默停在旧路径的机制）：**`BACKEND` 这个 conf 键只被 `infer-load` 消费**；systemd 单元走 `llama-serve-instance`，它**只读 `LLAMA_SERVER_BIN`（缺省 `/opt/llama.cpp/llama-server`）、完全不读 `BACKEND`**。A 的 conf 两者都没有 ⇒ 单元启动即落 `/opt`。⇒ "conf 缺 `BACKEND`" **既不等于"未迁移"，也不被任何门禁读**。
⇒ **修正后的建议**：若立项，**落点应是 `engine`（运行面）而非 `backend`（装机面）** —— 它已拥有"在服务"这一事实，加"占用者分类"是**报数扩展**（与 `O-143`「先报数」同构）；`backend` 保持"装机面"职责不变（**不动它的语义**）。

## 十、Auto_Prover 前置与 A 站形态**冲突**（2026-10-05 · **证伪"A 站未迁移"**）

**用户假设成立**（"是不是 Auto_Prover 测试把对齐拉回去了"），硬证据：
- A 站 journal 逐字：`00:36:23 sudo[58247] COMMAND=/usr/bin/systemctl stop llama-server@*` → `00:36:25 sudo[58268] COMMAND=/usr/bin/systemctl start llama-server@gpt-oss-120b` → `Started llama-server@gpt-oss-120b.service`。**这正是 `infer-load --backend llama-single` 的签名动作**（`BACKEND` 只被 `infer-load` 消费；systemd 单元只认 `LLAMA_SERVER_BIN`，A 的 conf 两者都空 ⇒ 落 `/opt/llama.cpp/llama-server`）。
- **Auto_Prover 把这条写为运行前置**：`proof_pipeline/config.py:145` · `docs/CONTROL_PACK_CLOSURE.md:91` · `docs/CHECKLIST_T6_B26.md:46` · `docs/DECISIONS.md:728/744` 逐字 —— *"A 站须 `infer-load gpt-oss-120b --backend llama-single`（默认 unsloth 后端仅 127.0.0.1 + 强制 key，**主控不可直连**）"*；其 `llm_base_url=http://192.168.10.33:8080`（主控直连 A 站）⇒ 与 unsloth **结构性不兼容**。

**三条更正（如实）**：
1. ★★ **"A 站未迁移到 unsloth" 不是缺陷，而是外部消费者的硬前置** ⇒ 本方案 **Step 0（A→unsloth）与既有消费者冲突**，**应视为无效/已自然回滚**（不是故障）。
2. **`ports.yaml` 把 8080 owner 登记为 `unsloth studio`，与 A 站实况/需求不符** ⇒ 真缺口 = 「**登记口径没把各站消费者的约束写进去**」。
3. ★ **实现层误判（活体检查抓到）**：`/opt/llama.cpp` 是 **symlink → `/opt/llama.cpp-master-91f6a6cf`** ⇒ 按 `readlink -f` 的 exe 会把**当前基线**误标 `opt-variant`（应为 `opt-vulkan`）；应**以 cmdline 为准**（cmdline 保留未解析的 `/opt/llama.cpp/llama-server`）。另：studio 的监听进程 exe 是 **python 启动器**（身份只在 cmdline 里）—— 同一处修正即可覆盖。

**未做（如实）**：本轮**不改代码口径**（用户 2026-10-05 裁「先落档发现」）⇒ `ops/rpc_check.py` 与夹具的改动**留在工作树、未提交**；A 站维持 **llama-single**（Auto_Prover 形态）；`O-146` 已按此更新为「只落发现、不落代码」。