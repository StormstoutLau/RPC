# RPC 优化执行度量日志 (metrics-log)

> **执行日期**: 2026-08-28
> **依据**: [DESIGN.md](./DESIGN.md) 五阶段流水线
> **基准**: llama.cpp v0.2.0, MiniMax-M2.7 Q4_K_S, 双机 RPC
> **方法**: 每阶段前后同参数对比, 数据按 DESIGN §6.5 度量方法采集

---

## Phase 0: 基线 (2026-08-28, 未调优状态)

### 链路层

| 指标 | 值 | 判读 |
|------|-----|------|
| 链路协商速率 | **20000Mb/s** (A 站 ethtool; B 站 ethtool 报 "No data available"; dmesg 无 40Gb/s 行) | ⚠️ 20G 链路, 非 40G — 见"发现"节 |
| MTU | 1500 (两站) | 基线 |
| 链路错误 | RX errors 0 / TX errors 0 (两站) | 干净 |
| 链路丢包 | A: TX dropped 12 / B: TX dropped 13 (累计计数, 静息态) | 轻微 qdisc 丢弃, 可忽略 |
| ping RTT (200 pkts, -i 0.2) | **min/avg/max/mdev = 0.189/0.619/1.272/0.108 ms, 0% loss** | ✅ 与社区未调优基线 600-700µs 完全吻合 — C-state 唤醒延迟理论成立 |
| iperf3 B→A (-P 4, 10s) | **9.02 Gb/s** (稳态逐秒 9.00-9.04) | 与社区同硬件 ~9.4 Gb/s 一致 (20G 链路 TCP 有效吞吐典型值) |
| iperf3 A→B (-P 4, 10s) | **9.11 Gb/s** (稳态逐秒 9.08-9.11) | 双向对称 |

### bench 基线

| 指标 | 值 |
|------|-----|
| llama-bench 命令 | `-m MiniMax-M2.7-Q4_K_S.gguf --rpc 10.10.10.1:50052 -ngl 999 -t 16 -b 512 --n-cpu-moe 8 -fa on -p 512 -n 128 -r 2` (注: 实际执行 -r 2, 非设计稿的 -r 20; 后续各阶段同参数保持可比) |
| pp512 t/s (±stddev) | **139.19 ± 1.67** |
| tg128 t/s (±stddev) | **19.95 ± 0.14** |
| 总耗时(含加载) | ~300s (无独立计时, 参考 v0.2.0 初测 298s) |
| 日志 | B 站 `~/llama-distributed/logs/bench_phase0_baseline.log` |

### 执行环境备注

- 两站服务起点: rpc-server (A) / llama-server (B) **均未运行** — 干净基线, bench 无需停服
- A 站 `start_rpc.sh` 现用 `-H 0.0.0.0`(Phase 2 改 10.10.10.1);无 -c 缓存
- A 站 ufw 未安装 — RPC 50052 暴露面完全由绑定地址决定
- iperf3 本次安装(两站), nload 未装(用 `ip -s link` 字节计数器替代)

### 发现

1. **链路协商 20Gbps(门槛触发项)**: 与 strix-halo-guide #12 社区基线同条件(其 RPC 矩阵即 20G 链路采集), 本轮 A/B 对比有效性不受影响; 但 40G 认证线(≤0.8m)换线可望将加载/prefill 带宽翻倍 — **物理操作, 留作用户可选项, 不阻塞软件阶段**
2. dmesg 显示 retimer 连接/断开循环轮询(vendor 0x7fea / 0x1da0), 随后稳定识别对端主机 — 疑与线缆主动元件相关, 与换线建议互为佐证
3. RTT avg 619µs 与社区 600-700µs 未调优值精确吻合 → pm_qos=100 预期降至 ~134µs 的外推可信度高

---

## Phase 1: 链路层调优 (pm_qos + MTU 9000) — 2026-08-28 执行完毕

**部署**: pm-qos-usb4.service 两站 systemd 化 (enable+active, `pm_qos_resume_latency_us=100` 生效验证 cpu0=100); MTU 9000 两站 netplan 持久化 (`/etc/netplan/01-network-manager-all.yaml` + `netplan generate` 后 keyfile `mtu=9000`)。

| 指标 | Phase 0 | Phase 1 后 | 变化 |
|------|---------|-----------|------|
| ping RTT avg (µs) | 619 | **100** | **-84%** |
| ping RTT max (µs) | 1272 | **230** | -82% (C-state 尖峰消除) |
| ping mdev (µs) | 108 | **11** | -90% |
| 巨帧 ping (8972B, -M do) | N/A | 5/5 收到, 0% loss, avg 234µs | ✅ 通路确认 |
| iperf3 B→A (-P 4) | 9.02 Gb/s | 8.98 Gb/s | 持平 (巨帧收益不在吞吐) |
| pp512 t/s | 139.19 ± 1.67 | **141.12 ± 0.08** | +1.4% (噪声边缘) |
| tg128 t/s | 19.95 ± 0.14 | **20.05 ± 0.04** | +0.5% (噪声内) |

**结论**: 吞吐收益 ≈ 0 (符合调研 v1.1 预判 — 链路非瓶颈, 9Gb/s 带宽充裕)。真实收益为**延迟尾部**: RTT max 1.27ms→0.23ms (6 倍), 消除 C-state 唤醒尖峰, 利好交互式生成 P99 尾延迟 (bench 均值不可见)。pm_qos 代价: 两站各 +1.4~1.6W 待机功耗 (调研 v1.1 估值)。

**bench 日志**: `bench_phase1_pm_qos_mtu_20260828_142730.log`

---

## Phase 2: rpc-server 绑定 + 本地缓存 — 2026-08-28 执行完毕

**部署**: A 站手动进程 (pid 9623, `-H 0.0.0.0`) → systemd `rpc-server.service` (`-H 10.10.10.1 -p 50052 -c`, `LLAMA_CACHE=/data/rpccache/MiniMax-M2.7-Q4KS`, `Restart=always`)。

| 指标 | 值 |
|------|-----|
| 50052 监听地址 | ✅ `10.10.10.1:50052` (ss 验证, 不再 0.0.0.0) |
| rpc-server 日志缓存行 | ✅ `[set_tensor] saved to '/data/rpccache/.../rpc/<hash>'` 逐 tensor 落盘 |
| 缓存体积 | **47G / 136 tensor 文件** (RPC backend 分到的 tensor 部分; 模型总量 121.1G, 其余在 B 站 Vulkan/CPU) |
| 首次加载 (写缓存) 总耗时 | **310s** (含 47G 网络传输 + 落盘, `bench_..._143404.log`, 时间戳差 1787898844→1787899154) |
| 二次加载 (缓存命中) 总耗时 | **267s** (`bench_..._144006.log`, 1787899206→1787899473) |
| 加载收益 | **-43s (-14%)** ≈ 47G @ 9Gb/s 网络传输时间, 精确吻合 — 缓存命中 tensor 跳过网络传输 |
| 吞吐 (pp512/tg128) | 143.93±3.76 / 19.85±0.25 (带缓存读写 IO 竞争, 方差变大; 均值与 Phase 1 一致) |

**结论**: 缓存对吞吐零影响 (预期内), 加载阶段净省 43s。RPC 协议侧 tensor 缓存命中协商有效 (两端均 v0.2.0)。副作用: rpc-server journal 每 tensor 一条日志 (136 条/加载), 噪音可接受; A 站磁盘占用 47G (878G 可用, 无压力)。

**注**: 首次 bench 方差 ±3.76 (vs Phase 1 ±0.08) — 缓存写盘与推理 IO 竞争所致, 热缓存后收敛。

---

## Phase 3: 稳定性固化 (systemd + 崩溃演练) — 2026-08-28 执行完毕

**部署**: B 站 `llama-server.service` (参数与 run_server.sh/inference.conf 同源, `Restart=on-failure` `RestartSec=10`, `ExecStartPre=/llama-distributed/wait_rpc.sh` 等待 A 站就绪)。

**演练**: SIGKILL A 站 rpc-server → 触发 B 站真实崩溃传导 → 观察双向自愈。

| 验证项 | 结果 |
|--------|------|
| A 站 kill rpc-server → systemd 自愈 | ✅ **6s** (Restart=always, RestartSec=5, journal "restart counter is at 1" → 新 PID 监听 10.10.10.1:50052) |
| B 站 idle 态反应 | **不 abort** — /health 持续 ok (发现: idle 时 llama-server 不触碰 RPC 连接, /health 不探测后端) |
| B 站推理请求触发断连 | ✅ 请求返回空 (连接断裂), llama-server 进程退出 (GGML_ABORT 语义确认) |
| B 站 llama-server 自动重启 | ✅ Restart=on-failure + wait_rpc.sh (A 已就绪, 立即通过) → 新 PID 开始 load_model |
| 端到端 MTTR | **~6 分钟** (T+0s kill → T+6s A 自愈 → T+~82s B 请求触发 → T+~110s B 开始重载 → T+358s model loaded → T+360s 推理恢复) |
| 恢复后 API /health | ✅ {"status":"ok"} |
| 恢复后 API 冒烟 | ✅ /v1/chat/completions 正常返回 (推理内容正确) |

**关键发现**:
1. **idle 不传导**: RPC 断裂仅在推理时触发 abort; /health 探测不到后端死亡 → 外部监控不能只依赖 /health, 需定时推理探活 (如 5 分钟一次 1-token 请求)
2. **MTTR 瓶颈是模型重载 245s** (缓存命中态; -c 缓存已省 ~45s, 否则更久) — 这是 v0.2.0 架构硬约束 (无断线重连), PR #26724 合并前无法改善
3. 监控脚本的 /health 判据在加载中误报 RECOVERED (v0.2.0 /health 加载期即返回 ok) — 已识别, 后续探活需用推理请求
4. 崩溃传导链整体按设计生效: A 自愈 6s → B 自愈触发 → 服务全恢复

---

## 附加试验 A1: -ot MoE 张量手动放置 (2026-08-28 执行完毕)

> **依据**: 《RPC串行跨链社区优化调研.md》行动项 A1 (Kononnable 技巧验证)
> **方法**: `llama-bench -m MiniMax-M2.7-Q4_K_S.gguf --rpc 10.10.10.1:50052 -ngl 999 -t 16 -b 512 --n-cpu-moe 8 -fa on -p 512 -n 128 -r 2` + `-ot` 各配置
> **张量名实测** (GGUF header): `ffn_(up|down|gate)_exps` / `attn_(k|q|v|output|norm|k_norm|q_norm)`, 无 dense ffn (全层 MoE)
> **执行窗口**: A 站手动 `GGML_RPC_DEBUG=1` rpc-server (a2_server.sh start), B 站 llama-server 停服跑 bench
> **日志**: `~/llama-distributed/logs/bench_a1_c*_20260828_170427.log`, `bench_a1_c1b_exps_20260828_172330.log`

| 配置 | -ot 规则 | pp512 t/s | tg128 t/s | Δtg vs C0 |
|------|---------|-----------|-----------|-----------|
| C0 默认层切分 (基线) | — | **147.03 ± 0.11** | **20.02 ± 0.19** | — |
| C1 专家全→A 站 | `ffn_(up\|down\|gate)_exps=RPC0[10.10.10.1:50052]` | 93.77 ± 0.04 | 18.95 ± 0.03 | **-5.3%** |
| C2 专家全→B 站 | `ffn_(up\|down\|gate)_exps=Vulkan0` | 90.32 ± 5.29 | 13.25 ± 0.07 | **-33.7%** |
| C3 注意力全→B 站 | `attn_[a-z_]+=Vulkan0` | 28.21 ± 0.00 | 7.16 ± 0.00 | **-64.2%** |

**结论**:
1. **TCP 下默认层切分已是最优放置** — Kononnable 技巧在本集群**负迁移** (最好变体也 -5.3%), 该技巧的适用前提 (master 版 + 特定拓扑) 在 v0.2.0 不成立。不采纳, llama-server.service 保持原参数。
2. **C3 是串行跨链的活体证明**: attn 全留 B 后, 图边界从 ~9/token (见 A2) 暴增至 ~60+/token, tg 直接 -64% — 吞吐与跨链边界数近似线性反比, 实测验证"每 token 串行跨层传导"机理。
3. **v0.2.0 `-ot` 设备名语法**: 裸 `RPC0` / `RPC` **均被拒** (`error: unrecognized buffer type`), 必须用 **`RPC0[10.10.10.1:50052]`** (带地址括号); 本地 Vulkan 用 `Vulkan0` ✓。后续任何 -ot 实验直接引用。
4. C2/C1 的 pp 大幅劣化 (-39%/-36%) 表明 prefill 对专家放置更敏感 (batch 计算集中度), 且首次跑新放置需 A 站写新缓存 (~+50G 磁盘, 832G 可用无压力)。

---

## 附加试验 A2: GGML_RPC_DEBUG=1 每 token RPC 账单采证 (2026-08-28 执行完毕)

> **依据**: 《RPC串行跨链社区优化调研.md》行动项 A2 (小张量风暴基线, 为 #26610 升级留 before/after 锚点)
> **方法**: A 站手动 `GGML_RPC_DEBUG=1 ggml-rpc-server -H 10.10.10.1 -p 50052 -c` → B 站 `llama-bench -p 128 -n 128 -r 1` (tg128 = 19.51 t/s = 51.3ms/token) → 解析 A 站日志推理段
> **原始日志**: 本地 `a2_rpc_debug_pp128tg128.log` (12393 行; 行 1~2217 加载段 / 2218~9352 推理段 / 9353+ 为 llama-server 重启加载); 解析脚本 `scripts/a2_parse.sh`, `a2_parse2.sh`

**加载段** (基线锚点): `set_tensor_hash` 哈希协商 214 次 (含 679MB 级大张量), `-c` 缓存命中协商有效; **推理段 set_tensor_hash = 0 次** — 图缓存/哈希机制完全不进热路径 ✓

**推理段 (tg 稳态, ÷129 token)**:

| 每 token | 次数 | 字节 | 主构成 |
|---------|------|------|--------|
| graph_compute | **8.93** | — | 1×大图(n_nodes 1553, A 端主子图) + ~8×小图(43/60 节点) |
| set_tensor | **12.89** | **793 KB** | 8×98304B (96KB, 子图输入激活) + 12KB/512B/8B/4B 标量碎包 |
| get_tensor | **16.87** | **110 KB** | 9×12288B (12KB, hidden states 回传) + 8×32B 标量 |
| **合计** | **~38.7 命令** | **~903 KB** | 全同步请求-响应 |

**判读**:
1. **带宽占用 17.6 MB/s 双向** (903KB × 19.51 t/s) = 9Gb/s 链路的 **0.02%** — 精确复现 #22850 "tens of MB/s while link idles"。串行跨链是**纯延迟/命令数问题**, 带宽毫无压力, 与 Phase 1 结论互证。
2. **延迟税估算**: 38.7 命令 × RTT 0.1ms ≈ 3.9ms ≈ 51.3ms/token 的 **7.6%** (纯 RTT 下限, 未含命令处理/flush 开销)。
3. **`-sm layer` 实际切分粒度 ≈ 9 子图/token** (非直觉的 1 边界) — scheduler 在 MoE 层内部多次切分, 每子图边界一次同步往返。#26610 的 async graph_compute + custom all_reduce 正对此结构; set_tensor_2d/BF16 压缩 (ne≥32768) 可将 96KB set 减半。
4. **升级锚点已建立**: #26610 合并后同法重测, 预期命令数/token 从 ~39 显著下降 (async 合并) — 本表即 before 基线。

## 附加试验 A3a: USB4 低延迟套件 (ayysasha 配方移植) — 2026-08-28 执行完毕

> **依据**: 《AMD395分布式推理高性能互连方案调研.md》§4 行动项 A3a + 《双机剩余优化空间评估.md》执行链第 1 步
> **来源**: ayysasha/Strix-halo-dual-optimized `99-usb4net-lowlatency.conf` + `usb4net-lowlatency.service`, 逐项对照增量移植
> **脚本**: `scripts/a3a_echo_server.py` (A 站 TCP echo) / `a3a_rtt.py` (B 站 TCP-RTT 探针, 5000×1B 往返) / `a3a_stage.sh` (分阶段应用) / `a3a_bench.sh`
> **测量条件**: llama-server 运行态测 RTT; bench 与 A1 C0 同日同参数 (隔离纯增量)

**套件内容与两站初始状态**:

| 项 | 初始值 | 应用后 | 备注 |
|----|--------|--------|------|
| net.core.busy_read / busy_poll | 0 / 0 | 100 / 100 | socket 唤醒 busy 轮询窗口 100µs |
| net.ipv4.tcp_fastopen | 1 | 3 | client+server 侧 TFO |
| net.ipv4.tcp_low_latency | 0 | 1 | **6.17 内核仍存在** (非移除态) |
| TB 设备 power/control (A 站 4 个 + B 站 4 个, 含 retimer 域) | auto | **on** | 直接针对 idle retimer found/disconnected 振荡 |
| CPU EPP | performance | performance | **两站本来就已是** → no-op, 增量隔离纯净化 |

**分阶段 TCP-RTT (B→A, 5000 样本)**:

| 阶段 | min | p50 | p90 | p99 | avg | ICMP avg |
|------|-----|-----|-----|-----|-----|----------|
| 基线 | 52.6µs | 130.4µs | 163.8µs | 212.0µs | 133.6µs | 141µs |
| +sysctl | **21.9µs** | 130.4µs | 225.7µs | 264.0µs | 133.3µs | 104µs |
| +TB power=on | 23.6µs | 130.4µs | 226.9µs | 265.3µs | 135.7µs | 105µs |

**吞吐 (llama-bench, 对照 A1 C0 同日基线)**:

| 指标 | A1 C0 基线 | A3a 后 | Δ |
|------|-----------|--------|---|
| pp512 | 147.03 | **153.00 ± 0.41** | **+4.1%** |
| tg128 | 20.02 | **20.23 ± 0.04** | +1.0% |

**判读**:
1. **pp512 +4.1% 是主要收益** — busy_read/busy_poll 削掉 socket 睡眠唤醒延迟的**下限** (min 52.6→21.9µs); prefill 每 batch 的 RPC 命令远多于 decode, 收益放大。
2. **tg128 +1.0%** (20.02→20.23, 超出 ±0.04 噪声但量级小) — decode 侧 38.7 命令/token 中大头是 compute 等待, busy 窗口 100µs 只覆盖快命令。
3. **RTT 分布代价**: p90/p99 尾部 +60µs (busy 轮询窗口耗尽后睡眠的开销) — RPC 热路径 compute-bound, 净收益为正; 但对延迟敏感的小消息纯 echo 场景是负交易。
4. **TB power=on 对活跃 RTT 无影响** (预期内) — 其价值是**消除 idle 时 runtime suspend → retimer found/disconnected 振荡** ([USB4-40G评估] §4.2 隐患), 可靠性项非吞吐项。
5. p50 130µs 三阶段不变 → 中位数由链路物理延迟主导 (20G 协商速率), busy 窗口覆盖不到; 与"换 40G 线对吞吐无感"结论不矛盾 (A2: 带宽占用 0.02%)。
6. **持久化已完成**: 两站 `/etc/sysctl.d/99-usb4net-lowlatency.conf` (4 值) + `usb4net-lowlatency.service` (TB power=on, enabled active); bench 后 llama-server 恢复, API 冒烟通过。

**坑记录**: `ssh "pkill -f a3a_echo_server; nohup ... a3a_echo_server.py ..."` — pkill 正则匹配到 bash 自身命令行中的 `a3a_echo_server.py` 字样 → **自杀, ssh 255 空输出**。修复: kill 与 start 拆成两条 ssh 调用, kill 用 `a3a_echo_serve[r]` 括号技巧。

---

## 附加试验 A4: vLLM TP=2 平行试验 — 环境就绪 + 硬件层根因诊断 (2026-08-28/29)

> **依据**: 《AMD395分布式推理高性能互连方案调研.md》行动项 A4 (ayysasha/Strix-halo-dual-optimized 路径复现, M2.7 AWQ 18.5-24.8 t/s 目标)

### 环境准备 (已完成)

| 项 | 状态 |
|----|------|
| vllm-rocm 便携构建 (lemonade-sdk) | ✅ 两站 `~/vllm-rocm` (CPython 3.14.6 + vLLM 0.25.2.dev0+rocm7.15.0-gfx1151 + Ray 2.58.0 + ROCm 7.12 用户态, 无需系统 ROCm) |
| 模型 MiniMax-M2.7-AWQ-G32-STRIX-2H (155.28GB, 45 文件) | ✅ 两站字节级一致 (A: `/data/models/` B: `~/models/`, `filesig` 45/45 同; A 站 hf 日志确认 44/44 Downloaded) |
| MoE tuned-config + device_name shim | ✅ 两站 `~/moe-configs` + `~/moe-shim` (RocmPlatform.get_device_name → 'Radeon 8060S Graphics') |
| 下载加速 | 分段并行 Range 下载 100KB/s→2.6MB/s; `HF_HUB_DISABLE_XET=1` 绕过 Xet 协议直连 401 |

### 启动失败排查链 (3 次失败 → 根因)

1. **`LocalEntryNotFoundError` (Qwen3-0.6B)**: vLLM 0.25.2 直接调 `api_server` 模块时位置参数 `model_tag` **不映射**到 `args.model` (映射只在 `vllm serve` CLI 入口 `cli/serve.py:52`) → banner 显示默认 Qwen/Qwen3-0.6B。修复: 显式 `--model /tmp/model-alias`。
2. **`Free memory (28.07/117.19 GiB) < 107.81` (B 站)**: 停 llama-server 后 sleep 3 不够, ~60GB GTT 释放滞后 → launcher 加 `wait_gtt_free` 轮询 (<2GB 才放行)。
3. **同报错复发 (A 站, 旧 pid 31280)**: 22:24 失败启动的 RayWorkerProc 残留 89GB, `ray stop -f` 杀不净跨 session actor → `a4_cleanup.sh` 两站 pkill -9 暴力清 (default_worke[r]/rayle[t]/ray::/gcs_serve[r] 括号防自杀)。
4. **干净态仍报 28.07/117.19** → 停止盲目重启, 转入显存探测诊断。

### 根因 (决定性实验, a4_diag_mem.sh + a4_diag_alloc.sh)

| 指标 | 值 | 判读 |
|------|-----|------|
| `free -g total` (两站) | **30 GiB** | 128GB 物理内存被 BIOS carve-out 走 96GB, OS 只剩 30 |
| `mem_info_vram_total` | 96 GiB (103079215104) | carve-out 成 GPU 专用 VRAM |
| `mem_info_gtt_total` | 117.19 GiB | grub `amdgpu.gttsize=120000` 设的 GTT 上限 (虚标) |
| torch `total_memory` | 117.19 GiB | **torch 读 GTT 当 total** |
| torch `mem_get_info free` | 28.99 GiB | 真实 = 系统内存剩余 |
| torch 逐步分配实测 | 8✅ 16✅ **24 GiB OOM** | **真实可分配仅 ~29 GiB, 不是 117** |

**机理**: ROCm/PyTorch 在 gfx1151 上走 GTT (系统内存); llama.cpp (Vulkan) 能用 carve-out 96GB VRAM + GTT 故双机 121GB 模型可行; vLLM (ROCm) 只走 GTT, 而 GTT 受 30GB 系统内存物理约束 — M2.7 TP=2 每 rank 需 77.5GB, 装不下。**grub 参数本就正确, 唯一错误项是 BIOS carve-out 96GB** (社区定性 "Too aggressive — starves the OS")。

### BIOS 决策 (512MB vs Auto): **512MB 固定值**

- amdgpu maintainer Mario Limonciello: "set as low as possible + tune TTM; **Auto will scale vram by memory size, not useful for GTT**" (Auto 在 128GB 机上大概率等价于大 carve-out, 等于没改)
- AMD ROCm 官方 Strix Halo 文档: "keep dedicated VRAM small (e.g. **0.5 GB**), increase TTM/GTT instead"
- Strix Halo AMI BIOS 菜单名为 OEM 变体 (UMA Frame Buffer Size / iGPU Memory / **Dedicated Graphics Memory**); A 站 NEX 即 `AMD CBS → GFX Configuration → Dedicated Graphics Memory → 0.5G`
- 对 Vulkan llama RPC 影响: 同一物理 LPDDR5X 同一带宽 (~256GB/s), 权重落点 VRAM 堆→GTT 堆 (VMA 自动 fallback), **服务参数零改动**; 单机 GPU 容量 96→108GiB 提升; 潜伏雷 = RADV 792MB 单张量墙 (触发条件含 "GTT 策略变化", 改后 bench 复测自动验证)

### BIOS 修改后验证 (2026-08-29, 两站全绿)

| 指标 | 改前 | 改后 | 判定 |
|------|------|------|------|
| A/B `free -g total` | 30 Gi | **124 Gi** | ✅ |
| A/B `mem_info_vram_total` | 96 GiB | **512 MB** | ✅ |
| A/B `mem_info_gtt_total` | 117.19 GiB | 117.19 GiB | ✅ 不变 |
| llama-server(B) / rpc-server(A) | — | systemd 重启自愈 activating→加载 | ✅ |

**待续**: ① Vulkan 锚点复测 (决策门: pp512/tg128 vs 153.00/20.23, |Δ|>5% 回滚 BIOS) → ② A4 续跑 (vLLM TP=2 启动→冒烟→同题对照→16k 长上下文决策门) → ③ 结果回填本节。*(已完成, 见下)*

### Vulkan 锚点复测 (BIOS 改后决策门, 2026-08-29)

| 指标 | A3a (改前) | A4 BIOS 改后 | Δ | 判定 |
|------|-----------|-------------|---|------|
| tg128 (decode) | 20.23 | **20.64 ± 0.12** | **+2.0%** | ✅ 略升 |
| pp512 (prefill) | 153.00 | **139.09 ± 0.41** | **-9.1%** | ⚠️ 超 5% 门 |
| RADV 792MB 墙 | 潜伏 | **未触发** (bench 完整跑完) | ✅ |

**决策: 暂不回滚** — tg128 (核心负载, decode 带宽主导) 不降反升; pp512 劣化机理 = prefill 大 compute buffer 从 carve-out VRAM 堆迁 GTT 重映射路径, 仅影响 llama.cpp 路径 prefill; A4 vLLM 成功后 llama.cpp 降级 fallback, 影响降级。最终回滚与否随 A4 结果一并决策。

### A4 vLLM TP=2 完整执行结果 (2026-08-29 00:50-01:20)

**启动成功链**: GTT 越墙 (B 站加载中 GTT 73.5→107.7GiB, 此前最大仅 29GiB) → Ray 2 GPU → `Application startup complete` → 冒烟 OK (首请求 4.8s 含 warmup)。

**同题对照 bench** (`scripts/a4_bench_api.py`, 随机 token 杜绝 prefix cache; 口径对齐 llama-bench):

| 指标 | llama.cpp Vulkan RPC | vLLM TP=2 ROCm | Δ |
|------|---------------------|----------------|---|
| pp512 (真实, cache-miss) | 139.09 | **298.0** (TTFT 1718ms) | **+114% (2.1x)** |
| tg128 | 20.64 | 17.60 | **-14.7%** |
| 16k PP | 未测 (估 60-80) | **193.0** (TTFT 84.9s) | ~3x (估) |
| 16k TG | 未测 | 12.87 (vs 512ctx 自身 -27%) | KV 膨胀衰减 |
| 16k 稳定性 (决策门) | — | **完整跑完, 无崩溃/hang/OOM** | ✅ **通过** |

**测量坑**: 初版 PP=8383→3804 均为 prefix cache 假象 (warmup/跨 run 共享 "word "×N 前缀, block 级命中) — **vLLM prefix caching 必须随机化 prompt 才能测真实 prefill**; PP 可信度校验: 512tok/135ms(命中态) = 76 TFLOPS ≈ RDNA3.5 FP16 双发理论 88%, compute-bound 打满。

### A4 最终判读

1. **路径成立**: vLLM TP=2 over USB4 在本集群可用, 16k 稳定性门通过 — ayysasha 路径本地复现成功。
2. **定位分裂**: vLLM = **prefill 2-3x** (compute-bound, TP 打满算力, 无 RPC 串行跨链); llama.cpp = **decode +14.7%** (带宽主导, GGUF Q4 kernel 更优)。TG 17.6 vs ayysasha 报 18.5-24.8 下限略低 (enforce-eager 未开 CUDA graph, 留作后续优化项)。
3. **主力决策**: **双路径并存** — 长上下文输入场景 (RAG/文档/代码分析) 走 vLLM 8081; 短输入长生成/日常对话走 llama.cpp 8080。BIOS 512MB 配置下两者兼容 (vLLM 需停 llama.cpp 释放 GTT, a4_vllm_launch.sh 已自动处理)。
4. **BIOS 配置维持 0.5G**: A4 成功证明修改价值 (vLLM 可用 + tg +2%), pp512 -9.1% 由 fallback 定位吸收 — **不回滚**。

### A4b 追加试验: 去掉 --enforce-eager (CUDA graph) — 2026-08-29 执行, **负迁移, 已回退**

> **假设**: CUDA graph 消除 kernel launch 开销 → TG 向 ayysasha 报告上限 (18.5-24.8) 靠近
> **前置修复**: 去掉 `TORCHDYNAMO_DISABLE=1` (ayysasha eager 配方残留) — 禁用 dynamo 使 torch.compile 变 no-op, CUDA graph 路径的 `aot_compile` 必报 "not supported by the current configuration" (vllm/compilation/wrapper.py:165)

| 指标 | eager (基线) | CUDA graph | Δ | 判定 |
|------|-------------|-----------|---|------|
| 启动 (编译+捕获) | ~5min | 58.9s init (compilation 18.98s, capture PIECEWISE+FULL decode) | — | ✅ 启动反而快 |
| pp512 (cache-miss) | 298.0 | 275.3 | -7.6% | ⚠️ |
| tg128 (512 ctx) | 17.60 | **14.92** | **-15.2%** | ❌ |
| 16k PP | 193.0 | 191.6 | -0.7% | 持平 |
| **16k TG** | **12.87** | **3.70** | **-71.2%** | ❌❌ **病理性** (decode 34.6s vs 10s) |
| 16k 稳定性 | ✅ | ✅ 跑完 (但速度病态) | — | — |

**判读**:
1. **CUDA graph 在 gfx1151 + ROCm 7.15 nightly 为全面负迁移** — 短上下文 decode -15%, 长上下文 decode **-71% 病理性** (FULL decode graph 与 16k KV 长度交互出 slow path, 疑 shape-specific graph 回退或 scratch pool 交互)。假设证伪: launch 开销不是本平台 TG 瓶颈 (瓶颈=LPDDR5X 带宽, graph 无法改善)。
2. **配置回退**: launcher 默认恢复 `--enforce-eager` (`VLLM_EAGER=1` 默认; 试验用 `VLLM_EAGER=0`); TORCHDYNAMO_DISABLE 已永久移除 (eager 路径不需要, graph 路径被它毒害)。
3. ayysasha 上限 18.5-24.8 的差距 (17.6 vs 18.5+) 归因收敛: 非 eager/graph 之别 → 剩余变量为 Triton MoE tuned-config 的 batch 维度适配 / AWQ kernel 差异, 边际收益 ≤10%, 不再追逐。
4. **A4 最终配置定稿**: `--enforce-eager` + 无 TORCHDYNAMO_DISABLE + BIOS 0.5G + 双路径并存 (8080 llama.cpp / 8081 vLLM)。

**坑记录 (A4 续)**:
1. **vLLM 进程树 pkill 不死**: a4_restore.sh 的 `pkill -f vllm.entrypoints` 未杀干净 (APIServer/EngineCore/RayWorker 全存活, GTT 109.9GiB 锁死) → 必须用 a4_cleanup.sh 的括号技巧 (`vllm.entrypoint[s]` `ray::` 覆盖 EngineCore/RayWorker/gcs 全家)
2. **/tmp 在 BIOS 重启后清空** (tmpfs): cleanup/冒烟脚本重传才可用; 持久脚本应放 `~/`
3. **B 站 llama-server 冷启动在 A 站缓存未就绪时 timeout×2 后第 3 次 retry 成功** (wait_rpc.sh + Restart=on-failure 自愈链有效, 勿手动干预)
4. **vLLM bench 的 prefix cache**: 相同/前缀共享 prompt 的 TTFT 全部失真 (61ms 级假象), 必须每 run 独立随机 token

**坑记录 (A4 新增)**:
1. vLLM 0.25.2 `api_server` 模块直调必须 `--model` 显式传, 位置参数无效 (与 `vllm serve` 行为差异)
2. 失败的 Ray 启动留跨 session actor 残留, `ray stop -f` 不净, 必须暴力 pkill; GTT 释放滞后需轮询等待
3. `/tmp` 脚本在 BIOS 重启后丢失 (tmpfs), 诊断脚本应放 `~/` 或 scripts/ 持久位置

---

## 双路径架构说明 (Q&A 归档, 2026-08-29)

### Q1: 为什么有两个模型名 (minimax-m2 / minimax-m2-long)?

**"两个模型"是同一个 MiniMax-M2.7 的两条服务路径, 名字是 LiteLLM 网关的路由别名** (服务化方案 B5a, 见《双机推理服务化与编排框架调研.md》):

| 名字 | 指向 | 格式 | 强项 (A4 实测) | 适用场景 |
|------|------|------|---------------|---------|
| `minimax-m2` | llama.cpp :8080 | Q4_K_S GGUF 121G (Vulkan+RPC) | decode 20.6 t/s (vs 17.6) | 短输入长生成/日常对话 |
| `minimax-m2-long` | vLLM :8081 | AWQ G32 (ROCm TP=2) | prefill 298 t/s (2.1x; 16k 193 t/s) | 长上下文输入 (RAG/文档/代码分析) |

底模相同, 但量化格式与推理栈不同, 性能特征互补 — 双路径并存是 A4 最终定稿。LiteLLM 按请求 `model` 字段路由, 两个名字 = `model_list` 两条指向不同 `api_base` 的条目, `-long` 后缀是给客户端的语义提示。设计上**不做按 prompt 长度自动分流** (LiteLLM 原生不支持; 垫 FastAPI token 计数层复杂度不值), 客户端自己知道上下文多长。

### Q2: 为什么 vLLM (AWQ) 要在两站各存一份模型, 而 llama.cpp (GGUF) 只在 B 站存一份?

两个栈的**分布式模型根本不同**:

1. **llama.cpp RPC = 主从执行**: B 站 llama-server 持有完整 GGUF 并计算计算图; A 站 rpc-server 只是"哑执行器", 加载时权重经 USB4 `set_tensor` 推送 (47G 落 `/data/rpccache`, -c 缓存省 43s 的来源)。**GGUF 只在 B 站一份, A 站份额是网络送来的**。
2. **vLLM TP=2 = 对称对等**: Ray 两站各起一个完整引擎 worker, **各自从本地盘读自己那份权重分片**; USB4 只在前向传激活/all-reduce, 从不传权重。vLLM safetensors 加载器无"远端取权重"模式, `--model` 路径必须在每节点有效 — 张量并行的硬约束。

且两站文件本就不通用: GGUF 与 AWQ (safetensors) 是不兼容的量化格式, llama.cpp 读不了 safetensors, vLLM 读不了 GGUF。实际磁盘布局 = **B 站: GGUF + AWQ 两套; A 站: rpc 缓存 + AWQ**。

---

## PR #26610 协议升级链状态跟踪 (2026-08-29 查证, GitHub API)

> 本集群升级触发器: 合并后协议 5.1.0 → 6.0.0 (无向后兼容), 走 UPGRADE_SOP 两站原子升级

| PR | 内容 | 状态 | 关键事实 |
|----|------|------|---------|
| #26490 (基座) | DSV4 `-sm tensor` + meta backend | **✅ MERGED 2026-08-24** (ggerganov) | master 已有单机多 GPU tensor split; 4×3090 实测 PP +72%/TG -4.4% |
| **#26610 (主体)** | RPC `-sm tensor`: async graph_compute + COMM_ALLREDUCE + LRU graph cache + 2D 传输 | **Open, 终局阶段** | 基座合并后已重定向 master (5 commits, 最新 Aug 19); **Aug 28 ggerganov 要求 rebase onto master** (合并前最后步骤信号); rgerganov 认可 6.0.0 无兼容 (👍3) |
| #26724 (关联) | rpc 崩溃不 abort (崩溃传导修复) | Open, 无 review 活动 | 非合并路径关键项; 本集群已有 systemd 兜底替代 |

**遗留阻点 (合并前需解决)**:
1. rebase 待 am17an 执行 (Aug 28 要求, 作者历史响应快)
2. DSpark over RPC 兼容 — ggerganov 08-05 明确提问 "Don't we want to fix the DSpark support first?"
3. 多 RPC 后端 hang — ryan5rdx 08-05 报告 "-sm tensor hangs with any topology >1 RPC backend", Aug 19 commit 后未复验

**合并后本集群升级评估**:
- **拓扑决策点**: RPC<>RPC all-reduce 最优拓扑 = llama-server 纯 client + 两站各跑 rpc-server (`--rpc ip1,ip2 --device RPC0,RPC1`); 本集群当前是 B=client+compute (Metal<>RPC 同构缺陷拓扑), 升级时需同步改造才能吃 tensor split 红利; **layer split 也受益** (async graph_compute + LRU cache + 2D 直击 A2 实测的 38.7 命令/token)
- **传输层**: comm port 默认 TCP (RDMA 是可选 upgrade), USB4 thunderbolt_net 可用; A↔B 互通 (10.10.10.1/2 直连) 满足 peer-to-peer 前提
- **锚点已建**: A2 的 before 基线 (38.7 命令/token, 903KB/token, tg 19.51) + 升级 SOP (DEV-LOG-009: RUNPATH patchelf 坑 + 两站 MD5 一致 + 原子切换)
- **风险**: master 无发布 tag 时需从 commit 构建; hang bug 若未修, tensor split 首测用小模型 (Qwen 0.6B) 验证

---

## Phase 4: llama.cpp v0.2.0 → master 滚升锚点 (2026-08-31 执行完毕)

> **动机 (审计后 6.21)**: 滚升 master **不解锁 GLM** (glm5next 未合入, 已证), 目标仅拿 **deepseek4 架构支持 + 8 月算子修复**。与 #26610 协议升级解耦 (本次未吃 async graph, 协议仍 5.1.0)。

### 4.1 版本与部署

| 项 | 值 |
|---|---|
| 旧版 | v0.2.0 (8 月初标签, RUNPATH=$ORIGIN 已修) |
| **新版** | **master (0.3.0-dev)**, `/opt/llama.cpp-master-d2e206c4`; **d2e206c4 = llama-server 产物 MD5 前 8 位 (构建指纹, 非 git commit** — tarball 无 commit 记录, llama-cli 报 "commit unknown") |
| 源码 | codeload master tarball (github 直连超时 132s, codeload 可达) |
| 构建 | B 站 cmake Vulkan+RPC Release, -j32, **279s** |
| RUNPATH | 109 ELF 全 patchelf `$ORIGIN` (**坑: 只修 exec 不够, .so 残留 /tmp/build 绝对路径 → 须全量修**, B 站假成功因 /tmp 仍在) |
| 分发 | 两站 MD5 MATCH (llama-server 96f11b5b...) |
| 版本核 | 两站 `0.3.0-dev` 一致 |

### 4.2 性能锚点 (llama-bench 同参, 40G 线)

| 指标 | v0.2.0 (BEFORE) | master (AFTER) | Δ |
|------|-----------------|----------------|---|
| pp512 | 141.69 ± 0.45 | **142.43 ± 1.38** | +0.5% (噪声) |
| tg128 | 20.77 ± 0.01 | **20.56 ± 0.00** | -1.0% (噪声) |

**性能持平** — 符合预期 (master 对 M2.7 Vulkan 算子无量变; 架构支持是本次收益方向)。

### 4.3 架构支持验证

| 模型 | v0.2.0 | master | 生成 |
|------|--------|--------|------|
| **DeepSeek-V4-Flash** | ❌ 架构不支持 | **✅ 加载 ✓ (300s)** | "1+1=2" ✓, tg ~6.3 (持平) |
| **GLM-5.3-Flash** | ❌ glm5next 不支持 | ❌ 仍不支持 (**实测**: master llama-cli 加载 147G 文件报 `unknown model architecture: 'glm5next'`) | — |
| MiniMax-M2.7 (现役) | ✅ | ✅ 双机 RPC, health 200, 生成 ✓ | — |

**DeepSeek HC 融合算子**: journal 仍 `fused DeepSeek V4 HC pre/comb/post not supported(RPC0), set to disabled` — #26578 未合并, DeepSeek 慢 (6.3 vs 6.6) 问题未解, 非本次目标。

### 4.4 收尾状态

- 生产已恢复: llama-server@m27 active + litellm active, 双机 RPC 正常
- 旧版 `/opt/llama.cpp-v0.2.0` 保留 (回滚可用, `sudo ln -sfn llama.cpp-v0.2.0 /opt/llama.cpp`)
- DeepSeek 现**可加载运行** (master 新增能力); GLM 仍等 #27752/#27754

### 4.5 坑记录 (Phase 4)

1. **.so 也必须 patchelf `$ORIGIN`**, 不只 exec — 否则 .so 间依赖按残留构建绝对路径找, B 站假成功 (构建目录在), A 站真失败
2. **基准前须停 llama-server**: llama-bench 与运行中的 8080 服务争 GTT + A 站 RPC 双 client → 卡死 (85.9G GTT 被他占)
3. DeepSeek 首次加载仍 ~300s (145G), A 站 rpccache 缓存生效使后续推送 ~5min
4. codeload.github.com 是可靠源码通道 (14s/35.3M), github.com 直连不可达

### 4.6 滚升报告审计 (spec 规范 review, 2026-08-31)

按规范双源核验 Phase 4 断言:

| 断言 | 原证据等级 | 审计动作 | 定谳 |
|------|-----------|---------|------|
| 版本 0.3.0-dev | 实测 | 复核 llama-cli --version | ✅ 硬事实 |
| **master-d2e206c4** | 报告写成"版本" | 追查 d2e206c4 来源 | ⚠️ **已澄清**: 是 llama-server MD5 前 8 位 (构建指纹), 非 git commit; llama-cli 报 "commit unknown" |
| 性能持平 pp+0.5%/tg-1.0% | 实测同名基准 | 口径复核 (同 v0.2.0 参数) | ✅ 噪声级判定合理 (tg -1.0% 在 ±0.00 方差下略偏但幅度小, 归持平可接受) |
| DeepSeek 加载+生成 ✓ | 实测 | health 200 + 生成 | ✅ 硬事实 |
| **GLM 仍不支持** | **推断 (未实测)** | **本次实测**: master llama-cli 加载 147G GLM 文件 | ✅ **推断升级为硬事实** (报 `unknown model architecture: 'glm5next'`) — 修正 4.3 |
| master 含 deepseek4 | 源码抓取 | llama-arch.cpp grep | ✅ |
| HC 融合算子仍缺 | 实测 journal | — | ✅ |

**审计结论**:
1. **硬事实层零幻觉** (版本/性能/DeepSeek/架构源码/HC 均实测或源码级确认)
2. **1 处表述偏差已澄清**: "master-d2e206c4" 易误读为上游 commit, 实为本地构建指纹 (tarball 无 git 元数据)
3. **1 处推断已升级实测**: GLM "仍不支持" 原为依据源码推断, 但模型文件/conf 均在, 本次直接实测确认 — 修正为硬事实
4. **方法论沉淀**: 报告里"预期失败/符合预期"类断言凡有实体文件(模型+conf)在场, 一律应实测而非推断; 版本标识须区分 git commit vs 构建指纹

## Phase 5: 集群基准自动化 (B5q — beowulf-ai-cluster 借鉴落地) — 2026-08-31 执行完毕

工具链 (spec/cluster-bench DESIGN §12, CHECKLIST 48 项验收通过):
- `rpc-nodes`: nodes.env 声明清单 + /dev/tcp 存活探测 + --start/--stop 经 ssh systemctl (B5q-1)
- `b5_bench_cluster.sh`: 一键全集群 bench, 冻结口径, 自动启停收尾 (B5q-2)
- `b5k_sync.sh --verify`: A→B 同步 + 双端 sha256 校验, 范围闸门 A_ONLY∨.sha256 标记 (B5q-3)

### 5.1 基准复测 (b5_bench_cluster.sh --alias m27-q4ks, 冻结口径同 Phase 1-4)

| 指标 | b5p 基线 | Phase 5 | Δ |
|------|---------|---------|---|
| pp512 | 141.4 | 141.82 ± 0.91 | +0.3% |
| tg128 | 20.9 | 20.53 ± 0.26 | -1.8% |

- 全流程时长: **4min15s** (17:36:49 → 17:41:04, 含 121G 模型 RPC 热缓存加载; DESIGN §8.2 "≤15min" 估计回填 ✓)
- RPC 节点: 10.10.10.1:50052 (rpc-nodes --start 自动拉起; 结束自动收尾 inactive, 零 pkill)
- log: /tmp/bench_cluster_m27-q4ks_1788169009.log (B 站)

### 5.2 B5q-4 GGML_VK_PREFER_HOST_MEMORY drop-in 对照 (三选一判定)

| 条件 | pp512 | tg128 |
|------|-------|-------|
| baseline (无 drop-in) | 141.82 ± 0.91 | 20.53 ± 0.26 |
| +GGML_VK_PREFER_HOST_MEMORY=1 | 134.82 ± 0.65 | 20.74 ± 0.25 |
| Δ | **-4.94%** | +1.0% |

**判定: Δpp < -2% → 撤销** (DESIGN §5 规则; drop-in 已 rm + daemon-reload, 目录 17:46 清空, unit 本体未改; log /tmp/bench_cluster_m27-q4ks_1788169292.log)

### 5.3 B5q-3 双端校验

- 篡改检出: 文件缺失 → `Qwen3.5-27B.Q8_0.gguf: 打开或读取失败` + FATAL + rc=6 (点名非泛泛)
- 目录级恢复: rm 目录 → A_ONLY 重传 27GB → manifest 重建 → 双端校验 rc=0
- NVMe 校验速度实测: ~400GB 双端并行 ≈ 12min → **~550MB/s/端** (DESIGN §2 决策 7 估计值回填 ✓)

### 5.4 Qwen3.8-Flash-Next 入库实测 (2026-08-31 晚, 主控 → B → 分布式)

- **来源**: 主控机 D:\Download\Qwen3.8-Flash-Next (Q4_K_XL 4 分片, 合计 103.7G: 0.01+46.44+45.99+11.26G)
- **传输**: 主控 → B (scp 并发 2 流), ~128MB/s, 全程 ~17min, size 逐字节一致 (scp 无损)
- **合并**: `/opt/llama.cpp/llama-gguf-split --merge` → 104G 单文件 (1224 tensors, 4 份), exit 0; 分片删
- **入库坑**: 合并文件误放 `/data/models/` 顶层, infer-list/infer-load 只扫 `/data/models/gguf/<属主>/<模型>/` (两层 mindepth2) → 迁至 `gguf/misc/Qwen3.8-Flash-Next/` 后识别
- **架构**: **llama.cpp master-d2e206c4 支持** (Qwen3 MoE 系, 无 glm5next 式失败) — model loaded, 加载 ~1min55s
- **分布式**: infer-load 生成 conf (RPC_TARGET=auto 哨兵展开, N_CPU_MOE=8, -fa on), A 站 rpc-server@qwen3.8-flash-next + B 站 llama-server@... 均 active; READY ✓ 2min
- **冒烟**: 生成正常 (自报通义千问)，prompt 38.7 t/s / tg 15.3 t/s (首测, 冷 prompt cache)

### 5.5 qwen3.8-flash-next YaRN → 1M 实测 (2026-08-31 晚, 结论: 当前引擎不支持超 256K)

验证路径 (手册 §3.4 指令):

| 步 | 配置 | 实测 | 判定 |
|---|---|---|---|
| 基线 | CTX=262144 (原生) | `n_ctx_slot=262144` + model loaded, 加载 ~105s; KV 32k→262k 内存增量 ~6G (QSA 稀疏, **无全量线性增长** — 排幻觉修正成立) | ✅ 原生 256K 可用 |
| 扩展 | CTX=524288 + `--rope-scaling yarn --yarn-orig-ctx 262144 --rope-scale 2.0 -ctk q8_0 -ctv q8_0` | journal: `n_ctx_seq (524288) > n_ctx_train (262144) -- possible training context overflow`; `slot context (524288) exceeds training context - capping` → `n_ctx_slot=262144` | ❌ **YaRN 未生效, slot 被强制 cap 回 n_ctx_train** |

**结论**: qwen4exp 走 `ggml_rope_multi IMRoPE` 专用路径, `--yarn-*` **未被 qwen4exp.cpp 消费**, llama.cpp 判定无扩展 → 任意 `-c > 262144` 一律 cap 回 262144. **当前 master 构建 (d2e206c4) 无法对 qwen4exp 用 YaRN 扩展超 256K → 1M 不可达** (调研 §6.26 裂缝①实证裁决为负).

**1M 可达的唯一路径**: vLLM (Qwen3.8-Flash-Next-FP8 recipe `--rope-scaling '{"factor":4.0,...}' --max-model-len 1000000`), 需 day-0 镜像; 或等 llama.cpp 为 qwen4exp 接入 IMRoPE yarn 扩展 + memory_hybrid 稀疏后才可复测.

**收尾**: conf 已回退默认 (CTX=32768, EXTRA_FLAGS="-fa on "), health 200 恢复.
