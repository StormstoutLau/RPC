# cluster.py 推理框架统一管理切换 扩展方案

## Context（背景与目标）

用户要把「推理框架管理切换」做成**傻瓜式**——不必记站名/ssh/infer-* 底层命令，一条命令完成框架/后端的管理与切换。

现状盘点：
- **已有现成傻瓜式入口雏形**：`d:\RPC\ops\cluster.py`（主控站统一 CLI，Python3+paramiko），已有 `status/load/unload/e2e` 四子命令，覆盖三站（A/B/C），是对接各站已部署 `infer-load/infer-unload/infer-list` 的聚合器。ADR-0001 已定义其目标为「一步换模型」。
- **切换缺口**：`infer-load` 已支持 `--backend unsloth|llama-rpc|llama-single|vllm`（后端四线切换），但 `cluster.py` 的 `cmd_load` 只调 `infer-load '{matched}'`，**完全没有透传 backend**；也没有「框架级运行状态一览」。
- **三站里 `_switch_qwen_flavor`/`_reload_ctx` 仍是手动/单点工具**，非本次范围（本次统一到 cluster.py 命令面）。

本次明确需求（用户已确认）：① 后端四线切换（核心）② 框架运行状态一览 ③ C站纳入清单。落点：**扩展 cluster.py**。

约束：最小侵入、贴合 cluster.py 现有风格（顶格 docstring、STATIONS 常量、ssh_run/ssh_stream 复用、threading 并发、无第三方框架）。cluster.py 是 Python source，**无 PS5.1 中文限制**（该限制仅 PowerShell 侧）。

---

## 方案

### 1. 用法文档字符串（模块顶部 docstring）更新

```
python ops/cluster.py status [--html] [--frames]
python ops/cluster.py load <alias> [--backend unsloth|llama-rpc|llama-single|vllm]
python ops/cluster.py frames
python ops/cluster.py unload
python ops/cluster.py e2e
```

### 2. 常量：无 shell 注入风险的枚举白名单

在 `ROUTE` 附近新增：

```python
BACKENDS = {"unsloth", "llama-rpc", "llama-single", "vllm"}   # infer-load --backend 白名单
```

backend 来自枚举白名单校验，不经用户自由文本 → 无注入风险（远端 infer-load 亦二次校验，双保险）。

### 3. 后端四线切换（核心）——透传 `--backend`

- `def cmd_load(alias: str, backend: str = None) -> int:`
  - 白名单校验：`backend is not None and backend not in BACKENDS` → 打印白名单 + exit 1
  - 命令拼装改为：`f"infer-load '{matched}'" + (f" --backend {backend}" if backend else "")`
  - 配 `-C（_cmd_load_c）同样加 `backend=` 参数并透传。
- **切换语义确认（关键）**：`infer-load` 第 [3] 步独立于 backend 做互斥（`systemctl stop 'llama-server@*'` + `pkill unsloth` + `pkill vllm/ray`）。故「切后端」只需 `load <alias> --backend <new>` 一次，**无需先 unload**。若 conf 已存在，infer-load 只 `source` 不改写 BACKEND（仅首次生成写）→ **切换必须显式 `--backend`**，否则沿用 conf 旧值（此点写入用法注释）。
- **RPC 类交互**（RPC_MODELS）：显式 `--backend <某单机后端>`（非 llama-rpc）→ 视作强制单机加载，放行走正常路径；否则（backend 缺失或 = llama-rpc）→ 维持 exit 2 手动双机提示。

### 4. 框架运行状态一览

新增 `def probe_frames(st: str) -> dict`，单次 `ssh_run` 多命令检测各框架：

```python
cmd = ("echo '[llama]'; systemctl is-active 'llama-server@*' 2>/dev/null|head -1; "
       "pgrep -x llama-server >/dev/null && echo running; "
       "echo '[unsloth]'; pgrep -f '[u]nsloth studio run' >/dev/null && echo running; "
       "echo '[vllm]'; pgrep -f '[v]llm.entrypoint' >/dev/null && echo running; "
       "echo '[litellm]'; systemctl is-active litellm 2>/dev/null; "
       "echo '[opencode]'; pgrep -f opencode >/dev/null && echo running")
```

- `[u]`/`[v]` 前缀规避 pgrep 自匹配（沿用 infer-load 手法）
- llama 的 RUNNING 由 `systemctl is-active`（A/B）或 `pgrep llama-server`（C 手动）取其一，**单一命令覆盖三站，无需按站分支**
- 输出：每站 section，各框架 RUNNING/STOPPED/Unknown + 端口/加载模型名
- `probe_station` 现有 curl `:8080/health` **不动**；帧探测是独立补充层

### 5. status --frames / 独立 frames 子命令

- `cmd_status(html, frames=False)` 增加第三参数；`--frames` 时在现有状态块后追加 `probe_frames` section（**默认输出逐字节不变**，兼容既有调用方）
- 新增 `frames` 子命令：更聚焦，复用同一 `probe_frames`，exit 恒 0（探测失败仅标 UNREACHABLE）
- **不新增独立 `backend` 命令**：conf 是站内生成物，`--backend` 一次性透传已覆盖 90% 场景；查询 conf 是调试类，交给 `status --frames` 即可（最小侵入）
- `--html` 面板**不加**框架列（避免列膨胀）；可选：在 infer-list PRE 后追加 frames PRE

### 6. 路由表与 C 站

- **backend 不影响路由**：alias→station 与后端解耦，ROUTE 不改
- C 站经 `ROUTE`（`qwen3.8-27b→C`）与 `_cmd_load_c`（走同 infer-* 路径，已补装到 C 站 `/usr/local/bin`）纳入；`_cmd_load_c` 需补齐 `--backend` 透传（否则 C 站手动引擎默认走 unsloth）
- 前缀歧义：`resolve_alias` 用 startswith 按 ROUTE 字典序匹配，`gpt-oss` 伞形命中 `gpt-oss-120b`→A 为期望语义；补一条注释约束「C 专属键置于 ROUTE 尾部」，不改 `resolve_alias`

### 7. 实施顺序与验证

1. 加 `BACKENDS` 常量 + `probe_frames` + `cmd_load`/`_cmd_load_c`/`cmd_status` 签名扩展 + `frames` 命令 + main() 分发 + docstring
2. 本地验证（无需远端、无模型加载）：
   - `python ops/cluster.py --help` 显示新用法
   - `python ops/cluster.py frames`（站不可达则标 UNREACHABLE，不崩）
   - `python ops/cluster.py load x --backend wat` → exit 1 白名单拒绝
   - `python ops/cluster.py status` 默认输出与改动前一致（回归兼容）
3. 远端实测（需站内 GTT 空闲，责任人 on-call）：`python ops/cluster.py load <alias> --backend vllm` 切后端后 `frames` 确认
4. 文档回写：`D:\RPC\spec\D2-cluster-cli\IMPLEMENTATION.md`（用法节）+ `CHECKLIST.md`（增 backend/frames 条目）+ `ADR-0001`（记录「backend 是站内概念、路由与后端解耦」决策）
5.「傻瓜式」落地证明：一条 `cluster.py load x --backend vllm` 完成后端切换（原先需 记站名+ssh+infer-load 三步 + 一层 backend flag 记忆）

---

## 关键文件

- `d:\RPC\ops\cluster.py`（主要修改：docstring / BACKENDS / probe_frames / cmd_load / _cmd_load_c / cmd_status / main()）
- `d:\RPC\ops\station-bin\infer-load`（只读参考，确认 backend 互斥与 source 语义，不改）
- `d:\RPC\spec\D2-cluster-cli\IMPLEMENTATION.md`、`CHECKLIST.md`（文档回写）
- `d:\RPC\adr\ADR-0001-集群运维框架审计与四项改进决策.md`（决策登记）

## 验证

1. **代码面**：新增 `BACKENDS` 白名单、`probe_frames`、backend 透传逻辑，Python 语法/风格与 cluster.py 一致
2. **命令面**：`--help` 展示新用法；`frames` 三站探测；非法 backend 拒绝
3. **回归**：`status` 默认输出不变；`load/unload/e2e` 原有行为不变
4. **端到端（需远端）**：`cluster.py load <alias> --backend <four>` 完成实际后端切换，`frame status` 确认切换生效