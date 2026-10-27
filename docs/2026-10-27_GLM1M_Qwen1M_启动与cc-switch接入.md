# GLM-5.3-Flash 1M（A+B）+ Qwen3.8-Flash 1M（C）启动与 cc-switch 接入

> **日期**: 2026-10-27
> **类型**: 运维执行记录（H 类 · 阶段依据）
> **范围**: ① A+B 以 1M ctx 启动 GLM-5.3-Flash；② C 站以 1M ctx 启动 halogen qwen3.8-flash-next；③ 在主控 cc-switch 写入两条本地 provider + 两条 SSH 隧道，供 Claude Code / Claude Desktop 使用。
> **状态**: 已执行并复验。**未修改仓库代码**；站上 conf 与 cc-switch DB 已变更，仓库侧台账/手册已同步。
> **关联**: [params-ledger §1.4](../spec/infer-load/params-ledger.md) · [手册 §3.3 / §3.4](三机推理集群使用手册.md) · [cc-switch 既有做法 §11.4](2026-10-20_p019独立复验_异基座模型配置分析.md)

---

## 1. 最终服务状态

| 站 | 角色 | 服务 | 状态 | 关键读数 |
|---|---|---|---|---|
| B | head | GLM-5.3-Flash-UD-IQ4_XS + MTP（变体引擎 `glm5next-20260928`） | **READY** | `/props n_ctx=1048576`；进程 `-c 1048576 --n-cpu-moe 8 --tensor-split 0.60,0.40`；冒烟 12.5 t/s（MTP draft 9 / accept 4）；**GTT 101.5G（余 24.3G）· RAM 26G 可用** |
| A | worker | `ggml-rpc-server` 10.10.10.1:50052 | **active** | **GTT 99.3G（余 26.6G）· RAM 29G 可用** |
| C | 独立 | halogen qwen3.8-flash-next（v2 `.hgn`） | **READY** | `context=1048576` · `kv_pool_positions=1048576` · YaRN factor 4.0 · KV int8 |

> 注：A 站无 `:8080`（worker 只开 50052），`cluster.py status` 显示 A STOPPED 属正常。

---

## 2. GLM-5.3-Flash 1M（A+B）

### 2.1 配置变更（B 站 `/etc/llama-instances/glm-5.3-flash.env`）

```
CTX=1048576
N_CPU_MOE=8
EXTRA_FLAGS="-fa on --spec-type draft-mtp --tensor-split 0.60,0.40"
```

- **原生 ctx = 1,048,576**（`estimate` 读出：46 层 · 全注意力 12/46 · head_dim 512），**不需要 YaRN**。
- **1M KV 估算**：q8_0 约 **12.75 GiB**（只算 12 个全注意力层）。
- 备份：
  - `glm-5.3-flash.env.bak-ctx65536-20261026`（改 CTX 前）
  - `glm-5.3-flash.env.bak-ncpumoe0-20261026`（改 N_CPU_MOE 前）
  - `glm-5.3-flash.env.bak-pre-ts045-20261027`（首次切分试验前：1M + 无 ts）
  - `glm-5.3-flash.env.bak-ts6040-ctx512k-20261027`（512K + 0.60,0.40）

### 2.2 为什么 `N_CPU_MOE=8`（关键教训）

首次以 `N_CPU_MOE=0` + `CTX=1048576` 加载：head 起服务后 **worker A 的 Vulkan 设备丢失**：

```
terminate called after throwing an instance of 'vk::DeviceLostError'
  what():  vk::Queue::submit: ErrorDeviceLost
#8 ggml_vk_preallocate_buffers(...)
#9 ggml_vk_mul_mat_vec_q_f16(...)
```

head 侧逐字：`Remote RPC server crashed or returned malformed response`，随后 systemd 重启（`NRestarts=2`），进入 7 分钟级崩溃循环。

- A 站当时 **GTT 101.8G / 125.8G**（余 24G），1M KV/预分配 buffer 放不下 ⇒ device lost。
- 将 `N_CPU_MOE=8`（部分 MoE 专家放 CPU）后：**A GTT 101.8 → 79.4G**，一次加载成功。
- 代价：约 **−22% decode**（`infer-load` 注释既有实测），小 prompt 实测 **12.4 t/s**（MTP 生效）。

### 2.3 加载命令与复验

```bash
py -3.12 ops/cluster.py load glm-5.3-flash --engine glm5next-20260928 --worker A
```

复验：

- `/props` → `n_ctx: 1048576`，`model_path` = GLM IQ4_XS；
- 进程 cmdline 含 `-c 1048576 --n-cpu-moe 8 --spec-type draft-mtp --tensor-split 0.60,0.40`；
- 最小生成 HTTP 200（`/v1/messages` 与 `/v1/chat/completions` 均通）。

### 2.4 余量（P1 层切分后）

`--tensor-split 0.60,0.40`（A 60% / B 40%）把原来的 **B 121.3G / A 79.4G** 拉成 **B 101.5G / A 99.3G**：B GTT 余 **24.3G**、RAM 26G；A GTT 余 26.6G、RAM 29G；`gates` 最小余量 **+14G**。1M 仍 READY，MTP/速度未退化（12.5 t/s）。

> 2026-10-27 切分前的「B 只剩 4.47G、RAM 7.9G」是未切分状态；现已由 §6.7 解决。

---

## 3. Qwen3.8-Flash 1M（C）

### 3.1 启动方式

复用 v2 `.hgn` 配方，进程内追加三项 env（**不落 `CONTAINER_MODELS`**）：

```
HALOGEN_CTX=1048576
HALOGEN_ROPE_YARN=4
HALOGEN_KV8=1
```

`CONTAINER_MODELS` 刻意保持默认 262k（手册 §3.4：静态 YaRN 是能力档，不是日常档）。

### 3.2 复验

`/health` 逐字：

- `context: 1048576`
- `kv_pool_positions: 1048576`
- `rope_scaling: {type: yarn, factor: 4.0, original_context: 262144}`
- `version.api = 0.18.13`，`capability_probe: ok`

### 3.3 回退

- 当前容器保持 1M；下次不带上述 env 重载会回到 262k。
- 回退命令：`py -3.12 ops/cluster.py load qwen3.8-flash-next-c --backend halogen`（不带 1M env）。

---

## 4. cc-switch 接入（主控 Claude Code / Claude Desktop）

### 4.1 写入的 provider（`~/.cc-switch/cc-switch.db`）

| app_type | 名称 | 上游 Base URL | 模型映射 |
|---|---|---|---|
| `claude` | **GLM-5.3-Flash 1M (A+B)** | `http://127.0.0.1:18081` | `ANTHROPIC_MODEL=GLM-5.3-Flash-UD-IQ4_XS.gguf` |
| `claude` | **Halogen Qwen3.8 1M (C)** | `http://127.0.0.1:18082` | `ANTHROPIC_MODEL=qwen3.8-flash-next` |
| `claude-desktop` | **GLM-5.3-Flash 1M (A+B)** | `http://127.0.0.1:18081` | opus/sonnet/haiku/fable → GLM，`supports1m: true` |
| `claude-desktop` | **Halogen Qwen3.8 1M (C)** | `http://127.0.0.1:18082` | 同上 → qwen3.8-flash-next，`supports1m: true` |

- **未设为默认**（延续 2026-10-25 的做法：切换由用户在 cc-switch 中执行）。
- 认证 token 为占位串 `local-glm` / `local-halogen`（两条引擎都不校验 key）。
- DB 备份：`~/.cc-switch/cc-switch.db.bak-20261027-glm1m-qwen1m`；`PRAGMA integrity_check = ok`。

### 4.2 隧道

| 本机端口 | 目标 | 用途 |
|---|---|---|
| `127.0.0.1:18081` | B 站 `127.0.0.1:8080` | GLM 1M |
| `127.0.0.1:18082` | C 站 `127.0.0.1:8080` | qwen 1M |

常驻方式（**免管理员**）：

- 启动脚本：`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\cc-switch-tunnels.cmd`
- 内容：两条 `ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -L 127.0.0.1:<port>:127.0.0.1:8080 scott-lau@<站>`
- ⚠ 计划任务 `Register-ScheduledTask` / `schtasks` 均因**无管理员权限**被拒，故用用户启动目录。
- 隧道断开后：重跑该 `.cmd`，或重新登录触发自启。

### 4.3 使用

1. 启动 cc-switch：`C:\Users\Peng\AppData\Local\Programs\CC Switch\cc-switch.exe`。
2. **Claude Code**：cc-switch 的 Claude 页切到对应 1M provider；切回 `default` 恢复原 OpenRouter 配置。
3. **Claude Desktop**：供应商列表切到同名两项（proxy 模式）。

### 4.4 验证

经两条隧道、用**实际映射的 model 名**请求 `/v1/messages`：

| 隧道 | model | 结果 |
|---|---|---|
| 18081 | `GLM-5.3-Flash-UD-IQ4_XS.gguf` | **HTTP 200**（`type=message`，thinking 内容返回） |
| 18082 | `qwen3.8-flash-next` | **HTTP 200**（`model=halogen-qwen3.8-flash-next`） |

> 两条引擎都支持 Anthropic `/v1/messages`（GLM 是 llama.cpp server 的实现；qwen 是 halogen 原生）。

---

## 5. 经验与边界

1. **`estimate` 的口径不是 RPC 切分口径**：它以「单站承载全部 146.1G 权重」计算 ⇒ 1M 报 `NO_FIT`；实际 RPC 把权重分到 B+A，且 `N_CPU_MOE=8` 释放 GTT 后装得下。**判断 RPC 类不能只看 estimate 的 NO_FIT**。
2. **1M 的第一约束是 GTT，不是模型原生 ctx**：GLM 原生支持 1M；失败来自 worker Vulkan 预分配。
3. **`N_CPU_MOE` 是 1M 的隐性前置**：回 65536 时可改回 0，恢复约 +22% decode。
4. **C 站 1M 是运行时能力档**：仓库配方仍 262k；要长期 1M 需显式写入配方（本轮刻意不做，避免短文本质量风险成为默认）。
5. **cc-switch 写入纪律**：先备份 DB；app 未运行时写入；provider 不设默认；隧道是 Base URL 可达性的前提。
6. **无管理员权限**：计划任务路走不通；用户启动目录是可用的替代。
7. **层切分不均是 1M 的真正瓶颈**：B 站 GTT 121.3G vs A 站 79.4G（A 还余 46.4G）；`N_CPU_MOE` 只是把压力从 GTT 换到系统内存，不是根因。优化方案见 §6；**2026-10-27 已用 `--tensor-split 0.60,0.40` 解决（§6.7）**。

---

## 6. 优化方案（层切分不均，待实施）

### 6.1 问题

| 站 | GTT 已用 / 总量 | 余量 | 说明 |
|---|---|---|---|
| B（head） | 121.36G / 125.83G | **4.47G** | 多数层 + `N_CPU_MOE=8` 的 CPU 专家 |
| A（worker） | 79.4G / 125.83G | **46.4G** | 余量充足 |

同硬件、同引擎，B 比 A 多承载约 **42G**；1M 时 B 是唯一瓶颈（4.47G），A 还有 46.4G。根因不是模型或 ctx，而是 **llama.cpp RPC 默认层分布 + `N_CPU_MOE=8`**；`infer-load` 没有暴露切分参数。

后果：1M 可加载但长 prefill 易 `DeviceLost`；B 站系统内存 7.9G，推送门禁必红；q4 KV 只能补 6.4G，属于治标。

### 6.2 目标（可验收）

- 1M READY，`/props n_ctx=1048576`；
- **B GTT 余量 ≥ 12G**，A GTT 余量 ≥ 12G（最低不得低于 8G）；
- **B 系统内存 ≥ 12G**（`gates` 推送门禁绿）；
- MTP draft/accept 不退化；128K/512K needle 冒烟通过；
- 任一档失败可只回滚 conf 并重载。

> **2026-10-27 状态：已达成（§6.7：B 101.5G / A 99.3G，`gates` +14G）。**

### 6.3 候选方案（按优先级）

| 优先级 | 方案 | 做法 | 预期 | 风险 / 前提 |
|---|---|---|---|---|
| P0 | 512K 安全档 | conf `CTX=524288`，`N_CPU_MOE=8` | B GTT 余 8～10.5G；先稳住 | 失去 1M；系统内存/推送门禁未必变绿 |
| **P1** | **层切分重平衡** | 在 `EXTRA_FLAGS` 追加 `--tensor-split 0.45,0.55`（B:A；当前设备数=2：本地 B + RPC A），从 512K 起试，逐档调比例 | B GTT 降到 ≤112G，A 承接更多层 | RPC 下 `-ts` 的索引/语义未验证；比例错会 device-lost；**只改 conf，不改代码** |
| P2 | 降 `N_CPU_MOE` | P1 成功后，8→6→0 逐档重载 | 释放 B 系统内存（推送门禁绿），恢复最多 +22% decode | GTT 反向增加；每档需记录 B/A GTT 与系统内存 |
| P3 | KV q4_0（不推荐） | 先 K q8_0 + V q4_0，保持 `-fa on` | 再省 3.2～6.4G | 质量悬崖/长文变慢/可能静默回退；官方用 FP8/BF16；`infer-load:533` 硬编码 q8_0，需改码 |

### 6.4 实施顺序

1. **P0**：日常切到 512K；1M 仅用于短上下文。
2. **P1**：`llama-server --help` 已确认支持 `-ts/--tensor-split`；当前 head 只有 **1 个 RPC worker**（`--rpc 10.10.10.1:50052`）⇒ `-ts` 两个值（本地 B、RPC A）。先在 512K 下试 `0.45,0.55`，记录 B/A GTT、系统内存、t/s、MTP；再上 1M。
3. **P2**：P1 达标后，再逐档降 `N_CPU_MOE`；每档只改一个变量，保留 conf 备份。
4. **P3**：仅在 P1/P2 仍不足且明确接受质量风险时做；先 128K needle A/B。

### 6.5 未验证点（必须先测）

- `-ts` 在 RPC 设备上的索引顺序（本地 B 是否固定为 N0）与 `--split-mode layer` 的交互；
- 层切分后 MTP draft 是否仍按预期分布；
- `N_CPU_MOE` 与 `-ts` 的交互（CPU 专家是否按层绑定到 B）；
- 1M prefill 峰值：建议 512K→768K→1M 逐档，不在 1M 直接做长文压测。

### 6.6 首档实测（2026-10-27，512K + `0.45,0.55`）

| 项 | 读数 |
|---|---|
| B GTT | **117.98G / 125.83G**（余 **7.85G**） |
| A GTT | **62.50G / 125.83G**（余 **63.33G**） |
| B 系统内存 | 113G used / **11G avail**（`gates` 余量 **-1G**） |
| A 系统内存 | 61G used / **63G avail** |
| MTP | draft 9 / accept 4；**12.5 t/s** |
| C qwen | 1M 仍 READY（未受影响） |

**结论**：
- `-ts` 已生效（argv 可见 `--tensor-split 0.45,0.55`），但方向与假设相反：B 从「512K 无切分的理论 ~114.9G」**升到 117.98G**，A 从 1M 的 79.4G **降到 62.5G** ⇒ 设备顺序更像 **RPC A 在前、本地 B 在后**；`0.45,0.55` 实际 = **A 45% / B 55%**。
- 当前 B 仍是瓶颈：GTT 7.85G、系统内存 11G，均未达 §6.2 的 ≥12G；`gates` 仍 -1G。
- **下一档**：`0.60,0.40`（A 60% / B 40%），预期 B GTT 降到 ~110G、系统内存回到 ≥12G；若 B 反而升高，则说明顺序相反，改用 `0.40,0.60`。

### 6.7 第二档实测（2026-10-27，`0.60,0.40`）

**512K 验证**（先低风险）：

| 项 | 读数 |
|---|---|
| B GTT | **90.98G / 125.83G**（余 **34.85G**） |
| A GTT | **89.49G / 125.83G**（余 **36.33G**） |
| B 内存 | **36G 可用**；`gates` 最小余量 **+24G** |
| MTP | draft 9 / accept 4；12.3 t/s |

**1M 验证**（同一切分）：

| 项 | 读数 |
|---|---|
| B GTT | **101.48G / 125.83G**（余 **24.35G**） |
| A GTT | **99.26G / 125.83G**（余 **26.57G**） |
| B 内存 | 98G used / **26G avail** |
| A 内存 | 95G used / **29G avail** |
| `gates` | **PASS，最小余量 +14G** |
| MTP | draft 9 / accept 4；**12.5 t/s** |
| C qwen | 1M 仍 READY（未受影响） |

**结论：P1 达标。**
- `0.60,0.40` 实际 = **A 60% / B 40%**（证实 A-first）；1M 下 B/A 基本均衡；
- GTT 余量 24–27G、系统内存 26–29G，推送门禁由 **-1G 转为 +14G**；
- MTP 与速度未退化（12.5 t/s，与切分前 12.5 持平）；
- **P2（降 `N_CPU_MOE`）现在可选**，不再是 1M 的前置；当前 8 档已满足 §6.2。

---

## 7. 回退手册

| 目标 | 操作 |
|---|---|
| GLM 回 65536（恢复 decode） | B 站 `sudo cp /etc/llama-instances/glm-5.3-flash.env.bak-ctx65536-20261026 /etc/llama-instances/glm-5.3-flash.env`；再把 `N_CPU_MOE` 改回 `0`；`cluster.py load glm-5.3-flash --engine glm5next-20260928 --worker A` |
| C qwen 回 262k | `cluster.py load qwen3.8-flash-next-c --backend halogen`（不带 1M env） |
| 全部卸载 | `cluster.py unload`（三站并行；会一并停 C） |
| cc-switch 回退 | 用 `cc-switch.db.bak-20261027-glm1m-qwen1m` 覆盖 DB（先退出 cc-switch） |
| 停隧道 | 结束两个 `ssh -N` 进程，或删除启动目录的 `cc-switch-tunnels.cmd` |

---

## 8. 关联文档

- [params-ledger §1.4](../spec/infer-load/params-ledger.md)：GLM CTX / N_CPU_MOE 的台账真值（本轮已回写）。
- [手册 §3.3](三机推理集群使用手册.md)：conf 调参与现役 CTX 清单（已回写）。
- [手册 §3.4](三机推理集群使用手册.md)：qwen 1M YaRN 配方与实测（既有）。
- [2026-10-20_p019独立复验 §11.4](2026-10-20_p019独立复验_异基座模型配置分析.md)：cc-switch + 18080 的上一轮做法（本轮沿用其「隧道 + 自定义 provider」模式）。
