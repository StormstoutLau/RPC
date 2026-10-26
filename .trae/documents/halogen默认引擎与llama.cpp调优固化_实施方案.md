# halogen 默认引擎落地 + llama.cpp 调优固化 · 实施方案（v2 · 锚点校订版）

> v1 被驳回。本版先做**外部锚点核对**，把 v1 里属于推断/未验证的条目逐条列出并修正（见 §2「幻觉排除」），再据此细化步骤。
> 证据等级沿用本仓约定：E1 本会话实测 · E2 前会话实测 · E3 外部文档（含 URL）· E4 推断（需标注）。

---

## 1. Context

**问题 1：llama.cpp 调优无法固化。**
2026-10-21 的调优（`--parallel 1 -b 4096 -ub 1024 --cache-reuse 256`）把 claude 热轮从 85–96 s 压到 6.3 s，但一直是手工启动。
原因经读码钉死：`EXTRA_FLAGS` **只被 systemd 路径消费**（[llama-serve-instance L60](file:///d:/RPC/ops/station-bin/llama-serve-instance#L60) 逐字 `${EXTRA_FLAGS:-}`），
而默认后端 unsloth 的启动行（[infer-load L473-477](file:///d:/RPC/ops/station-bin/infer-load#L473-L477)）**完全不引用它** ⇒ 改 conf 对 unsloth 无效，`cluster.py load` 必回 studio 默认 `--parallel 4`。

**问题 2：ctx 档位定错（本会话实测）。**
该模型模板默认 `reasoning_effort=xhigh`，单轮深度推理实测输出 **25,174 tok（finish=stop）/ ≥32,000 tok（finish=length）**；
旧 `-c 131072` + `MAXC=120000` 只剩 11,072 tok 输出余量 ⇒ 长会话下必然截断。`-c 262144` 实测代价仅 GTT +4.1 GB，8k/32k 吞吐无损。

**问题 3：更优引擎未启用。**
同权重同文本 A/B（E1）：冷 prefill **5.6–7.1×**、热轮 **2–3.8×**、decode **1.6–3.3×**，且 halogen decode 不随深度衰减；
深度推理整轮 **11.6 min vs 29.3 min（2.5×）**。ADR-0014 D7 已裁定默认框架=halogen，代码层未落地。

**目标**：① 让 conf 真正成为 llama.cpp 的唯一真值点；② 把 `qwen3.8-flash-next` 默认引擎切到 halogen，三站覆盖；③ 每一步都能被外部锚点或本仓实测复核。

**已定决策（用户 2026-10-21）**：端点 → halogen 发布到宿主 8080（客户端零迁移）；固化 → 新增 `STUDIO_FLAGS`；范围 → 三站；镜像 → 升级 **0.18.11**；缓存 → 默认 2，可复现跑另开 1。

---

## 2. 锚点（每条外部结论都可点开复核）

| # | 结论 | 锚点 | 等级 |
|---|---|---|---|
| A1 | halogen 是真实项目：`peonist-ai/halogen-flash-server`（GitHub）+ HF 权重 `peonist-ai/halogen-qwen3.8-flash-next`；只跑 gfx1151 单硅片；0.7.0 起可直接读 llama.cpp GGUF | [上游 README](https://github.com/peonist-ai/halogen-flash-server) | E3 |
| A2 | 上游 0.18.0 参考数：prefill 8k/32k/131k = **1,821 / 1,740 / 1,675 t/s**；131k 是 32k 的 **96%**；temp=0 输出与 serial greedy **逐字节一致** | 同上 README 表格 | E3 |
| A3 | `HALOGEN_CTX=262144` 约束的是**单个请求**，不是分配；`HALOGEN_KV_POOL_POSITIONS` 默认 **2×CTX=524288** 才是内存旋钮（~28–29.5 KiB/位置）；`HALOGEN_KV_SLOTS=4` 只是延迟策略（~115 MB/槽）；请求准入时**预扣 prompt+max_tokens**；内存不够时启动日志会打 `LOWERING THE POOL TO N` | [docs/configuration.md](https://github.com/peonist-ai/halogen-flash-server/blob/main/docs/configuration.md) | E3 |
| A4 | `HALOGEN_PROMPT_CACHE=2`（默认）：100k 后续轮 **~2 s**，但**重复 prompt 的答案非逐字节相同**；`=1`：逐字节一致但 100k 后续轮 **~17 s（最坏 32 s）**，且 <32k 会话无收益 | 同上「Choosing a cache mode」 | E3 |
| A5 | Claude Code 接入：`ANTHROPIC_BASE_URL=http://<host>:8731`、`ANTHROPIC_API_KEY` 任意值（服务端**不校验 key 也不校验模型名**）、建议 `CLAUDE_CODE_MAX_OUTPUT_TOKENS=32000`；**自 0.18.1 起** `/v1/messages` 才会把超 `max_tokens_cap`(65536) 的请求钳制并记一行日志 | [docs/claude-code.md](https://github.com/peonist-ai/halogen-flash-server/blob/main/docs/claude-code.md) | E3 |
| A6 | 当前最新版 **0.18.11**（我们钉的是 0.17.4，早于 A5 的钳制修复） | [CHANGELOG](https://github.com/peonist-ai/halogen-flash-server/blob/main/CHANGELOG.md) | E3 |
| A7 | 独立第三方实测（2026-09-21，Strix Halo 128 GB，v0.12.1）：prefill **1,250 / 1,423 / 1,408 t/s** @10k/43k/147k；decode **43 / 38 / ~38 t/s**；75k 会话 99% 命中缓存时 **1.2 s**（冷 60 s）；**"prefill 到 160k 基本是平的"** | [offsite.guru 配置文](https://offsite.guru/blog/halogen-strix-halo/) | E3（独立） |
| A8 | 同文踩坑：**未设 `reasoning_effort` = xhigh，且 token budget 覆盖 thinking** ⇒ 某次 compaction 调用把 32,768 预算全烧在思考上、671 s 后 `finish_reason: length`，会话卡死 | 同上「Five things that cost me time」#1 | E3（独立） |
| A9 | 同文踩坑：`--group-add` **必须用数字 GID**（docker 按**容器内** `/etc/group` 解析组名，容器里没有 video/render）；与 ADR-0014 D4 的实测修正一致 | 同上 compose 段 | E3（独立） |
| A10 | 同文踩坑：prompt cache **以构建版本为键**，不清理会累积（他堆到 187 GB）；磁盘缓存必须是支持 direct I/O 的真实文件系统，tmpfs 会被静默拒绝 | 同上 #2 | E3 |
| A11 | llama-server 一手语义（**站上实际二进制的 `--help`**）：`-c` = 上下文大小；`-b` 默认 2048 / `-ub` 默认 512；`--parallel` = slot 数；`--cache-reuse N` = "min chunk size to attempt reusing from the cache **via KV shifting**"；`--kv-unified` = 单 KV 池跨序列共享 | 站上 `~/.unsloth/llama.cpp/build/bin/llama-server --help` | E1 |
| A12 | `--ctx-size` 是**跨所有序列的总 KV 预算**，`--parallel 1` ⇒ 单槽拿到全部预算（引用 llama.cpp discussion #4130 + server README） | [文章](https://alejandro.criadoperez.com/blog/Llama_server_memory) | E3 |
| A13 | 本会话实测（B 站，同文本、每档独立盐值）：llama.cpp 冷/热 8k **24.22/2.18 s**、32k **106.54/3.22 s**、65k **265.73/4.06 s**、84k **446.38/10.98 s**（decode 17.5→8.3 t/s）；halogen（0.17.4）8k **5.96/1.06 s**、32k **19.17/1.06 s**、65k **37.27/1.08 s**（decode 27.5/27.3/27.0） | 本会话探针，数据已入 [params-ledger §1.3](file:///d:/RPC/spec/infer-load/params-ledger.md#L59-L79) | E1 |
| A14 | 深度推理整轮：llama.cpp 29.3 min / 25,174 tok / 14.3 t/s；halogen 11.6 min / 29,206 tok / 42.0 t/s；审计类任务 halogen 撞 32k cap（`length`，56.5 t/s） | 同上 | E1 |
| A15 | `-c 262144` 实测 GTT **69.28→73.38 GB（+4.1 GB）**，8k/32k 吞吐无损（32k 冷 106.93 vs 106.54 s） | 同上 | E1 |

---

## 3. 幻觉排除（v1 里被推翻/需降级的条目）

| # | v1 的说法 | 核对结果 | 处置 |
|---|---|---|---|
| C1 | 「conf 的 `EXTRA_FLAGS` 是调优唯一真值点」 | **只对 systemd 的 `llama-single/llama-rpc` 成立**；unsloth（默认后端）不消费 | 方案改为新增 `STUDIO_FLAGS`（§4 步骤 1），并在手册纠正口径 |
| C2 | 「客户端零改动」 | **不成立**：Claude Code 需 `CLAUDE_CODE_MAX_OUTPUT_TOKENS`（否则按"模型完整输出上限"发请求，0.17.4 无钳制）；`ANTHROPIC_API_KEY` 需非空 | 步骤 5 增站上 settings 校验 + 步骤 6 增 claude 端到端 |
| C3 | 「8080 占用者会是 `docker-proxy`，加进白名单即可」 | **未验证**：daemon.json 未设 `userland-proxy`（默认 true），但未实测 `ss -ltnp` 的进程名 | 改为**先实测再改白名单**（步骤 6 的前置），不预设 marker |
| C4 | 「halogen 输出不可复现」 | **说过头了**：上游量化是 38 个续跑轮里 3 次不同，且都发生在 top-2 概率极近时；模式 1 可完全一致 | 按 A4 分层：默认 2；"可复现跑"用 env 覆写为 1（用户已裁定） |
| C5 | 「`CONTAINER_MODELS` 里写死 4 slots / pool」 | slots **不是**内存旋钮，pool 才是；且 pool 可能被启动时**自动下调** | env 只写必要项，保持镜像默认；验证步骤**必须查 `LOWERING THE POOL TO N`** |
| C6 | 「`_engine_api_ports()` 由 ports.yaml 真值表驱动」 | **仓内既有缺陷**：`rpc_check` 模块**从未 import yaml**，异常被 `except` 吞掉 ⇒ 恒返回 `('8080',)`（实测：手工复刻同函数得 `('8080','8731')`，调用函数得 `('8080',)`） | **不在本方案里顺手改**（会改变判据面），登记为待裁缺陷；本方案只依赖"8080 被检查"这一既成事实 |
| C7 | 「升级镜像只是顺手」 | **功能性理由**：0.18.1 才对 `/v1/messages` 超 cap 做钳制（A5），而默认引擎要接 claude | 升级列为步骤 2 的硬前置，digest 重新登记 |
| C8 | 「磁盘 cache 必须挂」 | 非必须：内存缓存已能给 100k 后续轮 ~2 s（A4）；磁盘 cache 只解决**重启后续跑** | 列为可选增强，不进主路径 |

---

## 4. 实施步骤

### 步骤 1 · 让 unsloth 路径能表达调优旗标（`STUDIO_FLAGS`）

**改 [ops/station-bin/infer-load](file:///d:/RPC/ops/station-bin/infer-load)**
- conf 模板（L132-142）增 `STUDIO_FLAGS=""`，注释：仅 unsloth 分支追加；**禁止**含 `-c/--ctx-size/-fa/--flash-attn`（CTX 与 flash-attn 由 wrapper 拥有）。
- unsloth 启动行（L473-477）末尾追加 `${STUDIO_FLAGS:-}`。
- 守卫：`STUDIO_FLAGS` 命中上述禁项即 `exit 1`（重复 `-c` 是 llama.cpp 硬失败面）。
- 依据：A11（`--cache-reuse` 的语义是 KV shifting，只在单槽保前缀时才有意义）+ 本会话 E1（studio 会把 `--parallel/-b/-ub/--cache-reuse` 透传到子进程 cmdline）。

**站上 conf（B 先做）**
```
CTX=262144
STUDIO_FLAGS="--parallel 1 -b 4096 -ub 1024 --cache-reuse 256"
```

**文档**：[DESIGN.md](file:///d:/RPC/spec/infer-load/DESIGN.md) conf 格式补该键；[手册 §3.3/§3.4](file:///d:/RPC/docs/三机推理集群使用手册.md#L785-L819) 把"改 EXTRA_FLAGS 调参"改成"unsloth 用 `STUDIO_FLAGS`，`EXTRA_FLAGS` 只对 llama-single/llama-rpc 生效"。

### 步骤 2 · 配方进常量层（镜像升级到 0.18.11）

**改 [ops/cluster_const.py](file:///d:/RPC/ops/cluster_const.py)**：新增 `CONTAINER_MODELS`（与 `DS4_PP_MODELS` 同构的"别名→特殊编排"表）：

```python
CONTAINER_MODELS = {
  "qwen3.8-flash-next": {
    "name": "halogen",
    "image": "ghcr.nju.edu.cn/peonist-ai/halogen-flash-server:0.18.11",   # 升级：A5 的 /v1/messages 钳制自 0.18.1
    "models_dir": "/data/models/gguf/lmstudio-community/Qwen3.8-Flash-Next-GGUF/UD-IQ4_XS",
    "checkpoint": "/models/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf",
    "device": ["/dev/kfd", "/dev/dri"], "group_add": ["44", "992"],       # A9：必须数字 GID（本站实测 44/992）
    "ipc": "host", "ulimit": ["memlock=-1:-1"],
    "publish": ["127.0.0.1:8080:8731", "127.0.0.1:8731:8731"],
    "env": ["HALOGEN_DOWNLOAD=peonist-ai/halogen-qwen3.8-flash-next",
            "HF_ENDPOINT=https://hf-mirror.com", "HF_HUB_DISABLE_XET=1"],
    "ready_timeout": 300,
  }
}
```
- **不写** `HALOGEN_CTX` / `HALOGEN_KV_POOL_POSITIONS` / `HALOGEN_KV_SLOTS`：保持镜像默认（A3），避免把"内存旋钮"写死成未经本站实测的值。
- `BACKENDS` 增 `"halogen"`。
- 拉镜像用既有 `cluster.py containers pull --go --detach`（多 GB 拉取会超 ssh exec 上限，该命令已内建 detach）。

### 步骤 3 · load / unload 走容器分支

**改 [ops/cluster.py](file:///d:/RPC/ops/cluster.py)**
- 新增 `_load_container_model(alias, station)`：
  1. 先回收：`infer-unload` + `docker rm -f <name> || true`（守「禁止同站叠加加载」）。
  2. 用**既有** `containers_plan("up", ...)`（L5508）生成命令 → 逐条 `ssh_run(strict=True, timeout=120)`（计划与执行同源）。
  3. 轮询 `http://127.0.0.1:8080/health` 至 `status: ok`（A3：冷启可能数分钟）；**读启动日志确认无 `LOWERING THE POOL TO N`**（C5）。
  4. 打印身份：`model` / `version.api` / `context` / `kv_pool_positions`。
- `cmd_load`（L810）/`cmd_load_on`（L980）：解析出 `(matched, station, backend)` 后分派 `if matched in CONTAINER_MODELS and backend in (None, "halogen")`。
- `cmd_unload`（L1020）/`cmd_unload_on`（L1010）：`infer-unload` 之后补 `docker rm -f <name> || true`。
- 子命令 docstring（L26-33）同步。

### 步骤 4 · 门禁与探针适配

- **[ops/rpc_check.py](file:///d:/RPC/ops/rpc_check.py)**：
  - **先实测**确定 8080 监听者进程名（`ss -ltnp` / 既有 `occupant_<port>` 探针），据实往 `_OCCUPANT_KINDS` 加一条 + 纳入 `_OCCUPANT_OK`（C3）。
  - 保留 `_engine_api_ports()` 现状；把 C6 的缺陷登记到 `spec/d6-agent-standard/OPEN-ISSUES.md`（只登记，不改判据）。
- **[ops/station-bin/_station_ready.sh](file:///d:/RPC/ops/station-bin/_station_ready.sh) L49**：`ENGINE_CTX` 增回退链 `/props`(n_ctx) → `/health`(context) → `/v1/models`(context_length)。halogen 只有后两者（A3/A5）。
- **[inventory/ports.yaml](file:///d:/RPC/inventory/ports.yaml#L60-L77) 8080**：`purpose` 改「本地推理引擎 API 面（后端随加载：unsloth studio | halogen 容器）」，`owner` 补 `| docker (halogen)`；8730/8731 口径不改。
- **[inventory/models.yaml](file:///d:/RPC/inventory/models.yaml#L108-L123)**：`route` 仍 `B`；note 补默认引擎=halogen；删掉已作废的「长 ctx 塌缩 5.5–6.1（HIP）」一句（A13 实测无反例）。

### 步骤 5 · 站上客户端配置

按 A5 核对每站（Qwen 走 8080 时）：
- `ANTHROPIC_BASE_URL` 指 8080（隧道/直连不变）；
- `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` **非空即可**（服务端不校验）；
- `CLAUDE_CODE_MAX_OUTPUT_TOKENS=32000`（留 pool 余量；0.18.11 也会钳制，但显式设更可控）；
- opencode 的 `local/qwen3.8-flash-next` 无需改 base_url。

### 步骤 6 · 三站验证（逐站串行）

每站：
1. `containers status` → docker active、镜像 0.18.11 在位、head+tokenizer 在盘。
2. **实测 8080 占用者进程名**（C3 的前置）→ 若与 `_OCCUPANT_KINDS` 不符则回步骤 4 补。
3. `load qwen3.8-flash-next-<s>` → `/health` = ok、`context=262144`、`kv_pool_positions=524288`、日志无 `LOWERING THE POOL`。
4. `/v1/models` id = `halogen-qwen3.8-flash-next`；`/v1/chat/completions` 与 `/v1/messages` 各 200。
5. **claude 端到端**：`claude -p ... --model qwen3.8-flash-next`（带 `CLAUDE_CODE_MAX_OUTPUT_TOKENS=32000`），确认 `tool_use` 往返与 `stop_reason`。
6. **深度推理回归**：同一 `audit_check` 探针，确认不再 `length` 截断（cap 65536）。
7. 回退：`load ... --backend unsloth` → 容器回收、studio 起、`/props.n_ctx=262144`、`total_slots=1`、cmdline 含 `--parallel 1`。
8. `unload --station <S>` → 容器与 studio 均无、8080/8731 无监听、GTT < 1 GB。

⚠ A 站现常驻 `gpt-oss-120b`，在其上 load qwen 会先卸掉它（既有行为，需在报告里如实标注）。

### 步骤 7 · 门禁与文档

- `py -3 tests/run_py_tests.py` 全绿；`test_rpc_check_ps1_golden.py` 全绿；`rpc_check --only ports` 三站无 FAIL。
- 文档：[ADR-0014](file:///d:/RPC/adr/ADR-0014-halogen引擎引入与容器写动作扩权.md) D7 落地 + 未实测登记 #8 关闭 + 版本 2.2（含新 digest、0.18.11 理由）；[params-ledger §1.3](file:///d:/RPC/spec/infer-load/params-ledger.md#L59-L79) 固化状态改「已固化」、G6 关闭、新增「缓存模式 2/1 分层」行；手册新增「引擎选择」小节。

---

## 5. 验证清单（DoD）

| # | 判据 | 方式 |
|---|---|---|
| V1 | conf 是唯一真值点 | `load --backend unsloth` 后 `/props` = `n_ctx 262144`、`total_slots 1`，子进程 cmdline 含 `--parallel 1` |
| V2 | 默认引擎 = halogen | `load qwen3.8-flash-next` ⇒ `/v1/models.id == halogen-qwen3.8-flash-next` |
| V3 | claude 可用 | 端到端 `tool_use` 往返成功、无 400 cap 报错 |
| V4 | 深度推理不截断 | 同探针 `finish_reason != length`（cap 65536） |
| V5 | 卸载完整 | 容器无、8080/8731 无监听、GTT < 1 GB |
| V6 | 门禁不回退 | `run_py_tests` 全绿 + ps1 golden 全绿 + ports 无 FAIL |
| V7 | 三站一致 | A/B/C 各跑 V1–V6 |

## 6. 风险与回退

| 风险 | 处置 |
|---|---|
| 0.17.4→0.18.11 是跨版本升级，行为有变 | 先在 B 站单站升+验（V1–V5），再推 A/C；digest 重新记入 ADR |
| pool 被自动下调 ⇒ 并发/长会话容量缩水 | 启动日志断言 `LOWERING THE POOL`；必要时降 `HALOGEN_MAX_TOK` 换 pool（A3） |
| 默认缓存模式答案非逐字节可复现 | 用户裁定：默认 2；"可复现跑"用 `HALOGEN_PROMPT_CACHE=1` 覆写（性能代价 A4 已量化） |
| 8080 被容器占用后回退 llama.cpp 撞端口 | 回退路径先 `docker rm -f` 再起 studio |
| 供应链未审计、引擎协议默认无鉴权 | 保持 loopback；`_OCCUPANT_OK` 只白名单"认得出的形态"，不把"已纳管"读成"已合规"（ADR-0014 D6） |
| A 站 gpt-oss 被顶掉 | 预期副作用，逐站记录 |
| 回退 | `load ... --backend unsloth` / `containers down --go --name halogen` |

## 7. 明确不做

- 不改 opencode/claude 的 base_url（8080 稳定）；不动 ADR-0014 的 D4/D6 安全结论。
- 不顺手修 C6（`_engine_api_ports` 缺 yaml）——只登记，避免同时改判据面。
- 不做多会话编排（保持默认 4 slots / pool 524288，不写死）。
- 不动 `reasoning_effort` 默认值（A8 已证 xhigh 会烧满预算，但降档需配质量 A/B，单列议题）。
