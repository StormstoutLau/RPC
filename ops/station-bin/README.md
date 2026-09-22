# station-bin/ — 两站 /usr/local/bin 推理框架的仓库快照

> 快照时间: 2026-09-04 · 来源: B 站（两站 md5 一致，见下）
> 用途: 版本控制 + 灾难恢复参照。修改站侧脚本时**先改这里（review）再同步上站**，保持两站一致。

## 文件清单

| 文件                   | 站侧路径                                | 说明                                         |
| -------------------- | ----------------------------------- | ------------------------------------------ |
| infer-load           | /usr/local/bin/infer-load           | 加载入口（默认后端 unsloth；--backend 回退 llama-rpc/single/vllm；显式后端同时决定 RPC 与否 + 写运行时覆盖层） |
| infer-unload         | /usr/local/bin/infer-unload         | 卸载（含 unsloth 清理 + F2：rpc-server 未运行时跳过 GTT 等待 + 2026-09-15：停**全部** worker 的 rpc-server） |
| infer-list           | /usr/local/bin/infer-list           | 模型清单（建议后端=unsloth，embedding/AWQ 特殊）          |
| llama-serve-instance | /usr/local/bin/llama-serve-instance | systemd 实例包装器（回退路径用）                        |
| cluster-ttl          | /usr/local/bin/cluster-ttl          | 空闲 TTL 自动卸载检查器（60s oneshot，**默认关**；见下 P2-5）  |
| load-gate            | /usr/local/bin/load-gate            | **加载前内存门禁**（4 条硬规则：used+need+12G≤total / avail≥need+12G / 已有 llama RSS+need+12G≤total / loadavg1>8 WARN）；默认查本机，可传 peer 站 |
| load-mem-gate        | /usr/local/bin/load-mem-gate        | 内存门（12G 垫）                                 |
| wait-gtt-release     | /usr/local/bin/wait-gtt-release     | GTT 回收等待                                   |

## 两站一致性

修改后核对：`md5sum /usr/local/bin/<file>`（两站必须一致）。
当前（2026-09-17，**三站一致**）：infer-load `e474b761...`、infer-unload `6ff2a3b3...`、llama-serve-instance `0cf134f6...`。
（下表 2026-09-04 的旧值已作废，保留仅为历史：infer-load `229c1328...`(B)/`09e8b60e...`(A)、infer-unload `dc948d63...`、infer-list `5b6d40fc...`。）
（infer-load `e474b761` = 2026-09-17 遗留 1+2 修复版：头部注释改为实测口径 + **移除 `LLAMA_SERVER_PATH` 注入**；前一版 `d57a9021...` 已备份为 `/usr/local/bin/infer-load.bak-20260917-llamaserverpath`。详见 [TRACKER §2.6](../../spec/upstream-tracker/TRACKER.md)。）
**2026-09-22 补登记 `load-gate`**（此前本表漏列 ⇒ 该件无部署记录、无 md5 基线）：当前值 **`07ad7e01...`**（**三站一致**，且 == 仓库副本 [load-gate](./load-gate)，0 个 CR）。本次改动 = 4 处 peer ssh 补 `-o BatchMode=yes`；改法是"先改仓库副本 → 三站 `cp -a` 备份（备份 md5 == 原 `6acec519...`，逐站核过）→ `install -m 755` → 逐站核新 md5 + `bash -n` + 跑 `load-gate 1` 回归"；回滚 = 三站 `sudo cp -a /usr/local/bin/load-gate.bak-20260922 /usr/local/bin/load-gate`。

## 空闲 TTL 自动卸载（2026-09-15, P2-5，**默认关**）

**件**：`cluster-ttl`（检查器，本目录）+ `ttl.env`（配置模板 → `/etc/llama-instances/ttl.env`）
+ `../cluster-ttl.service` / `../cluster-ttl.timer`（60s oneshot）。**装即 disabled**，显式
`cluster.py ttl enable` 才生效。

**行为**：引擎空闲 ≥ `TTL_IDLE_SECONDS`（默认 1800s）即执行 `infer-unload`（会一并停掉全部 RPC worker）。

**空闲判据**（为什么不能更省事）：llama.cpp `/metrics` 全是累计计数器，**没有**"最后请求时间"，
故取差分 —— `Δtok>0` 活跃、`Δtok=0` 且在途请求为 0 才计空闲；`pid` 变化或计数器下降 ⇒ 时钟重新起算。
`/metrics` 不可用或计数器缺失 ⇒ **不动作**（不拿别的信号冒名顶替）。`requests_processing>0` 或
`/slots` 有 busy 槽 ⇒ 判活跃，**绝不打断在途请求**。

**三层闸门**：`TTL_ENABLED=0`（默认，只演练）→ `TTL_DRY_RUN=1`（只演练）→ `cluster.py ttl check --go`（真卸）。

**证据**：判定行（pid/在途/Δtok/idle/阈值）进 journald；结论写
`/var/lib/cluster-ttl/state.json` 的 `last_action`（谁在何时被卸、依据）。

**实测**（B 站 gpt-oss-20b @ llama-single）：关时到期只演练不卸 ✓；在途请求判定
`在途=1 busy槽=1 Δtok=78.0 → 活跃` 未卸 ✓；真开后由 timer **62s** 自动卸载
（`idle 60s ≥ 3s`，GTT 12.5G → 0.3G）✓。细节见 `docs/2026-09-15_统一管理入口_深入分析与优化方案_v2.md` §A.6 P2-5。

## 双机 RPC 回退修复记录（2026-09-15）

**现象**：`--backend llama-rpc`"加载看起来成功"，实际是 master 单机在跑（命令行无 `--rpc`），`/health` 照样通过。
三个真因（缺一即可复现，详见 `docs/2026-09-15_统一管理入口_深入分析与优化方案_v2.md` §A.6 P2-4）：

1. **身份错**：infer-load 经 `sudo` 跑 ⇒ 以 root 执行 ssh，而 root 无节点密钥（`Host key verification failed.`）；
   `set -uo pipefail` 无 `-e` 把失败吞掉 → 节点从没起 → 回退单机。修：`sudo -u <服务用户> rpc-nodes --start <alias>`，
   拿不到节点 **exit 7**（拒静默回退）。
2. **没等端口**：`RPC_TARGET=auto` 展开是单次探测无重试 → 改用自带 `wait_port`(15×2s) 的 `rpc-nodes --start`。
3. **单元重新读 conf**：单机路径走 systemd 单元，单元里 wrapper 会**重新 source conf** → 清 infer-load 自己 shell 的
   `RPC_TARGET` 对单元无效（"名义单机、实际双机"）。修：**运行时覆盖层** `/run/llama-instances/<alias>.env`
   （tmpfs，重启自清）—— infer-load 在显式指定 `--backend` 时写入，wrapper 在 `source "$CONF"` **之后**再 source；
   未显式指定后端则删除该文件，回归 conf 语义。

**顺带**：`infer-unload` 原先只停 A 站 rpc-server（硬编码），C 站成为 worker 后每轮双机加载都在 C 留常驻
`rpc-server`（门禁 engine 项黄灯）。现改为「本站就地停 + master 侧按 `nodes.env` 停全部远端 worker」。

**验证**：wrapper 级 4/4；端到端 `flow paths gpt-oss-120b-fable-5-distilled --go` → 单机 `rpc=否 tg=36.7` /
双机 `rpc=是(A+C) tg=27.1`，PASS；unload 后 A/C worker 均 0；门禁 11 绿 / 1 黄 / 0 红。

## unsloth 改造记录（2026-09-04）

- **默认后端 unsloth**：infer-load 默认 `unsloth studio run`（KV q8_0，**引擎 = studio 自带 `~/.unsloth/llama.cpp/llama-server`（HIP/ROCm，`--device ROCm0`）**，端口按 conf 若占用自动+1 并日志标注实际端口），健康检查解析 API Key 后带认证 `/v1/models`。
  > 2026-09-17 订正：原文写"引擎=LLAMA_SERVER_PATH"**与实测不符**（该变量的缺省值指向 9/8 已清除的 `~/llama.cpp-vulkan-b10715`）；其注入已于本日移除。详见 [TRACKER §2.6](../../spec/upstream-tracker/TRACKER.md)。
- **回退**：`--backend llama-single|llama-rpc|vllm` 走原 systemd llama-server 路径。
- **infer-unload**：补充 `pkill -9 -f "[u]nsloth studio run"` 清理 unsloth 实例。
- **infer-list**：建议后端列默认 unsloth（embedding=llama-emb / AWQ=vllm 除外）。
- **实测**：A/B 两站 infer-load gpt-oss-120b → READY :8080（unsloth, KV q8_0, CTX 按 conf），chat 2+2=4；infer-unload 停实例 + GTT 回收。
- **备份**：站侧 `*.bak-unsloth-20260904`（两站）。

## F2 修复记录（2026-09-02）

- **现象**: 双端点模式下 B 站 load/unload 固定空等 \~18min（A 站常驻 gpt-oss GTT 135G 永不 <2G，90 次×\~12s SSH 轮询走满才 WARN 放行）

- **修复**: infer-load 按 `RPC_TARGET` 判空跳过；infer-unload 按 "A 站 rpc-server 是否本就运行" 判定跳过（RPC 模式行为不变）

- **实测**: nemotron 换载 20min → 2.7min；双站 unload 32s

- **备份**: 站侧 `*.bak-f2fix` ×2/站

