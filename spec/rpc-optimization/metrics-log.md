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

### A3a 补测与结论更正 — 2026-09-29（三机形态）

> **背景**: C 站 2026-09-08/09 入群, **从未应用 A3a**（初始 0/0/1/0 + TB 全 auto）; A/B 两站 08-28 已持久化。本次对 C 逐项增量应用并复测三段六向。
> **口径**: 与 08-28 同法（TCP 1B 往返 ×5000, python 探针, 非 ICMP）。

**逐项 before/after（TCP-RTT p50, µs）**:

| 阶段 | A→B | B→A | A→C | C→A | B→C | C→B |
|---|---|---|---|---|---|---|
| 基线（C 未调优; socket 均早于套件创建） | 20.3 | 18.9 | 130.4 | 130.4 | 130.4 | 130.4 |
| C + busy_read/busy_poll=100（socket **未重建**） | — | — | 130.7 | **19.6** | 130.6 | **19.4** |
| C + tcp_fastopen=3 / tcp_low_latency=1 / TB power=on | — | — | 130.5 | 19.4 | — | 18.8 |
| ★ **重启 C 侧服务进程后**（唯一变量） | 20.2 | 19.8 | **18.5** | 19.4 | **18.1** | 18.8 |

**判定**:
1. **A3a 有效, 且远大于 08-28 的估计**: 调优 + 重启后 C 相关段 TCP-RTT p50 由 **130.4 → ~19µs（×6.8 削减）**, 六向收敛 18–20µs。
2. ★★ **机理（08-28 未识别）**: `net.core.busy_read` / `busy_poll` 在 **socket 创建时读取并黏附于该 socket** ⇒ **既有连接不吃参数**。证据链（同机同链路、单变量）: C 的 echo server 建于套件之前 → 应用 sysctl 后 A→C 仍 130.5µs; **仅重启该进程一次** → 立即 19.4µs。
3. ⚠ **更正 08-28 第 5 条结论**: 原文"p50 130µs 三阶段不变 → 中位数由链路物理延迟主导（20G 协商速率）"**不成立** —— 被测 socket 早于 sysctl 创建, 从未吃到 busy poll。正确表述: 130µs 是**未调优 socket** 的中位值, 调优并重启后 ≈ 19–20µs; "20G 决定 p50 下限"的推论一并撤回。
4. ★ **对 tg 的含义 — 已实测: 端到端增益为 0（2026-09-29 晚）**: 08-28 的 tg128 +1.0% 是在 **A-B 段**（两端本已调优）上测的, 因而**未包含 C 站的 6.8× 改善**。三机 RPC 拓扑下 C 端点为 `rpc-server` 绑定 10.10.11.3（B-C 段）⇒ C 侧 RPC socket 过去一直是 130µs 档。按 A2 口径（38.7 命令/token）若命令全落 B-C 段, 每 token 约省 4.3ms（对 87ms/token ≈ 5%）。
   **实测（同口径 `flow bench --go` · `max_tokens=128` · 三机 GLM-5.3-Flash）**: 调优后 **tg 128 tok @ 11.4 t/s**（4 次采样 11.4 / 11.4 / 11.5 / 11.4）; 同日 C **未调优**的锚 = `pp 413 tok @ 85.7 · tg 128 tok @ **11.4**` ⇒ **逐位一致, Δ < 1%（噪声内）**。加载/卸载经统一入口 rc=0, 拓扑 = B head + A/C worker。
   ⇒ **结论: RTT 税基本身不是 decode 的约束** —— 与既有判读「decode = 内存带宽 bound, 跨链延迟即使压到 7µs 也只能挤出个位数 %」同向; 也说明按"命令数 × RTT"的**线性外推高估**了延迟税在关键路径上的占比。A3a 的真实价值回到: ① **busy-poll 削 socket 唤醒下限**（08-28: pp512 +4.1%）; ② **TB 保活的可靠性**（消 idle retimer 振荡）。**tg 无收益。**
5. **落体**: C 站本次补齐 `/etc/sysctl.d/99-usb4net-lowlatency.conf` + `usb4net-lowlatency.service`（enabled/active）; A/B 漂回 `auto` 的 TB 设备（`0-2`/`1-2` 等）已重置 `on`; 三站现全部 100/100/3/1 + TB 全 on。测量后探针进程已清理, 三站无引擎在服务。
6. **部署前提（新增）**: **应用 A3a 后必须重启 llama.cpp 服务 / RPC 端点**, 否则既有 socket 保持旧值 —— 08-28 未写下的部署条件。
7. **坑记录（2026-09-30 定位）**: C 站落体那条**一次性 `ssh` 作业卡死 ~8h 未返回** —— 根因：外层 PowerShell **双引号**串里，送远端 bash 的循环变量 `$f` **先被 PowerShell 吃掉**（变空）⇒ 远端实收 `printf %s= ; cat ; done` ⇒ ★ **`cat` 无参数 ⇒ 读 stdin ⇒ 永久阻塞** ⇒ ssh 永不返回（`state.json` 长期 `Running`）。★ 与 `O-117`（PS 吃掉反引号转义）**同族**：*转义 / 变量在到达远端 shell 之前被本地吃掉*。**修法**：远端命令整体用**单引号**（PS 不展开），或变量写 `\$f`。⚠ 该作业 **C 段其实已完成**（conf + service `enabled`/`active` + `100/100/3/1`）；**A/B 段在 hang 点之后，从未执行**。
8. **补验（2026-09-30 · 只读探针）**: 第 5 条「A/B 漂回 `auto` 的 TB 设备已重置 `on`」「三站 TB 全 `on`」**原先不由那条卡死作业佐证**（其 A/B 段未跑）⇒ 本轮独立 `cat` 复验：**三站各 6 个 `power/control` 全 `on` · sysctl `100/100/3/1` · `usb4net-lowlatency.service` `enabled`+`active`** ⇒ **该断言成立**（此后有实测依据）。

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

> **2026-10-11 追记（E1 实测，原表保留不回滚）**：本表原预测"合并后协议 5.1.0 → 6.0.0"；**实际 `master-23b0202a` 的 RPC 协议 = `v8.0.0`**（A 站 worker 启动打印 `Starting RPC server v8.0.0`）。
> 且 **`-sm tensor` 首测即失败**（worker `ggml_vk_build_graph` SIGSEGV，**加载期**）⇒ 本表"合并后本集群升级评估"整体**按 No-Go 重判**。详见本文件文末「PR #26610 形态验证执行结论」节。

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

## 6. Phase 6 — #26578 DSV4_HC 融合算子 A/B 两机实测对照（2026-09-10）

**目的**: 实测 llama.cpp #26578（vulkan DSV4_HC_COMB/PRE/POST 融合，9/7 merged）对 V4-Flash 的 decode 收益；引擎升级走 UPGRADE_SOP 三站原子切换。

**口径**（同 before/after，固定不变）：A/B 两机 RPC 层分布（B head llama-server + A worker ggml-rpc-server，10.10.10.1:50052 USB4 直连），V4-Flash-0731-MXFP4 单文件 156G，`-sm layer` **无 -ngl 99**，`-c 8192 -t 16`，`/v1/chat/completions` max_tokens=512 三次取中值（timings.predicted_per_second）。

| 引擎 | commit | decode 中值 (t/s) | prompt (t/s) | HC 融合日志信号 |
|---|---|---|---|---|
| **BEFORE**（旧） | master-d2e206c4（8/31，无 #26578） | **9.56**（9.55/9.58/9.56） | 11.2–22.8 | `resolve_fused_ops: fused DeepSeek V4 HC pre/comb/post not supported, set to disabled`（6 条, 均命 RPC 慢路径） |
| **AFTER**（新） | master-91f6a6cf（9/10 构建, 含 #26578 + #27970 sparse-fa） | **14.02**（13.99/14.16/14.02） | 24.7–31.2 | **零 resolve_fused_ops 警告**（HC 融合在 Vulkan0 本地生效） |
| **Δ** | — | **+46.7%** | +▶ | 与 #26578 声称 decode 1.50× 高度吻合 |

- 三站引擎同构升级：B 单点构建（worktree 隔离 0d18aaa 源码树）→ MANIFEST(79 条) → tar 分发 A/C → patchelf `$ORIGIN`（新 cmake 产物 RUNPATH 硬编码 B 站 build 路径，修正后 A/C 可跑）→ 原子切换 symlink → `check_llama_version.py --deep` 三站指纹+79 文件 md5 全等 ✅
- 引擎版本: v0.4.0-dev (build 1533, commit 91f6a6cf), rpc_protocol v6.0.0
- 布防/清理: A(原 gpt-oss)/C(原 nemotron) 先行卸载, load-gate 语义由 wait-gtt-release 确认 avail≥90G; 实测后 head/worker 清理 + GTT 回收
- 证据: B 站 `/tmp/v4f_before_20260910013818/` `/tmp/v4f_after_20260910021831/` + 主控 `spec/rpc-optimization/v4f-26578-evidence-20260910/`
- **结论**: #26578 在本集群（Vulkan, gfx1151, 两机层分布）**实测 decode +46.7%（9.56→14.02 t/s）**，与上游声明一致 → **升级闭环**；V4-Flash 现役慢评（tg 6.6 记录）同步更新为 ≥14 t/s 级。
- ★ **2026-09-28 复核（独立重测，同引擎 `master-91f6a6cf`、同口径、同命令）**: decode **14.06 t/s**（14.06 / 14.02 / 14.07）· prompt **24.6 t/s** ⇒ **复现 14.02**；★ 由此**排除**「本集群双机 ~17 t/s」的说法（~17 是上游 PR **单机**数字 11.16→16.77，E3）。
- ⚠ **顺带实测（运维事实）**: **`cluster.py load deepseek-v4-flash-0731`（unsloth/HIP + RPC）对该模型 OOM** —— 563 s 后被 SIGKILL（`llama-server was stopped by the operating system (signal 9), most likely out of memory`）⇒ 现役形态仍是**手工 `/opt` 两机**（`ggml-rpc-server --device Vulkan0 -c` worker + head `-sm layer`，**无 `-ngl 99`**），与 TRACKER §2.5「分布式一律 `/opt`」一致。

### 5.5 qwen3.8-flash-next YaRN → 1M 实测 (2026-08-31 晚, 结论: 当前引擎不支持超 256K)

验证路径 (手册 §3.4 指令):

| 步 | 配置 | 实测 | 判定 |
|---|---|---|---|
| 基线 | CTX=262144 (原生) | `n_ctx_slot=262144` + model loaded, 加载 ~105s; KV 32k→262k 内存增量 ~6G (QSA 稀疏, **无全量线性增长** — 排幻觉修正成立) | ✅ 原生 256K 可用 |
| 扩展 | CTX=524288 + `--rope-scaling yarn --yarn-orig-ctx 262144 --rope-scale 2.0 -ctk q8_0 -ctv q8_0` | journal: `n_ctx_seq (524288) > n_ctx_train (262144) -- possible training context overflow`; `slot context (524288) exceeds training context - capping` → `n_ctx_slot=262144` | ❌ **YaRN 未生效, slot 被强制 cap 回 n_ctx_train** |

**结论**: qwen4exp 走 `ggml_rope_multi IMRoPE` 专用路径, `--yarn-*` **未被 qwen4exp.cpp 消费**, llama.cpp 判定无扩展 → 任意 `-c > 262144` 一律 cap 回 262144. **当前 master 构建 (d2e206c4) 无法对 qwen4exp 用 YaRN 扩展超 256K → 1M 不可达** (调研 §6.26 裂缝①实证裁决为负).

**1M 可达的唯一路径**: vLLM (Qwen3.8-Flash-Next-FP8 recipe `--rope-scaling '{"factor":4.0,...}' --max-model-len 1000000`), 需 day-0 镜像; 或等 llama.cpp 为 qwen4exp 接入 IMRoPE yarn 扩展 + memory_hybrid 稀疏后才可复测.

**收尾**: conf 已回退默认 (CTX=32768, EXTRA_FLAGS="-fa on "), health 200 恢复.

## Phase 6.2: 吞吐基准表建立与修正 (O-25 P0-①) — 2026-09-12

依据: D6 可观测性 O-25 关闭判据①「吞吐基准表至少覆盖现役各模型档」。制品: `spec/d6-agent-standard/THROUGHPUT-BASELINE.md`（基线版）。

### 三处数据修正（回溯自用户+实测采证）

| # | 项 | 修正处理 | 依据 / 来源层级 |
|---|---|---|---|
| 1 | MiniMax-M2.7 **双机 RPC (Q4_K_S, tg128 18.2-20)** | 整行删除 | RPC 量化档已删除，非现役；历史实录不回滚 |
| 2 | MiniMax-M2.7 **单机 decode** | 落定 **21.5 (decode) / 22.1 (含 prompt)** | 实测（用户测试题 16 题批量，`tmp/res_m27`，117936 tok / 5490s，UD-IQ4_XS / C 站 / q4_0 KV，短题峰值 23-25、长 CoT 压 20-21） |
| 3 | gpt-oss-120b **Vulkan ~23** | 整行删除（误归因） | ~23 实为 **nemotron-120B**(hiplz) 的 Vulkan decode，被误借推断 gpt-oss；gpt-oss 单站锚点以 HIP 直测 49-53 为准（A 站 49-53 / C 站 48.8，接近 50） |

### 结论
- gpt-oss-120b 单站 decode ≈ 49-53（用户确认"接近 50"达成一致）。
- MiniMax-M2.7 现役单机锚 = 22.1（agent 长 CoT 口径，非纯 tg128；短题可比出 24-25）。
- 教训（复用手册§1 防编造纪律）: 复制数据入表必须带「实测日期+方法+日志路径」三要素，只信 source 列非空的行；跨模型借数字推断（如 nemotron → gpt-oss）属归因漂移，禁止入锚。

## Phase 7: flow 运行记录 (2026-09-15 起, 由 `cluster.py flow` 自动追加)

| 日期 | flow | 目标 | 判据(口径) | 结果 | 证据 |
|---|---|---|---|---|---|
| 2026-09-15 17:46 | bench | gpt-oss-20b@B | API timings 口径 · max_tokens=128 · prompt 实测 468 tok | PASS | pp 468 tok 932.3 t/s · tg 128 tok 67.0 t/s |
| 2026-09-15 17:47 | bench | - | API timings 口径 · max_tokens=128 · prompt 实测 ? tok | FAIL | - |
| 2026-09-15 18:14 | paths | gpt-oss-120b-fable-5-distilled@B | API timings 口径 · 单机 vs 双机各一次实测 (同请求体, max_tokens=128) | PASS | 单机 tg=36.7 / 双机 RPC tg=30.6 |

> **更正说明（2026-09-15 18:50 追加，原行保留不回滚）**
>
> - **17:47 那行是负向测试的噪音，不是真实运行**：那是验证"无引擎且无 alias → fail-fast"时留下的。
>   已给 flow 加 `--no-ledger` 开关，此后负向测试不再落账（跑了的记录由退出码与输出留存，不需要占台账）。
> - **18:14 那行（paths）数据无效，不可用于决策**：当轮"单机"路径实际仍按双机跑 ——
>   根因是 `infer-load` 收到 `--backend llama-single` 后**只切了 `BACKEND`，没有清 conf 里的
>   `RPC_TARGET=auto`**，于是 A 站 rpc-server 照样被拉起。已修（见下），并给 `flow paths`
>   加了**后端生效性判据**（读 /proc/<pid>/cmdline 全文判断有没有 `--rpc`），
>   同类错误此后会被直接判为"该路径未按请求生效，数据不可用于对照"，不会再进台账。
> - 另：当时的"内存 +0.1G"是错的 —— UMA 下模型权重表现为 Cached，`MemAvailable` 差值测不出占用
>   （`_station_mem` 的 docstring 早记过这个坑）。已改用**引擎进程 RSS**。
> - **待办**：双机 RPC 路径当前**不可靠**（实测 `auto` 展开存在竞态 → 探测不到刚起的 A 站节点
>   即静默回退单机；预热后加载耗时异常且 llama-server 进程消失）。在该问题解决前，
>   `flow paths` 的"双机"列应视为**未取得有效数据**。
| 2026-09-15 19:34 | paths | gpt-oss-120b-fable-5-distilled@B | API timings 口径 · 单机 vs 双机各一次实测 (同请求体, max_tokens=128) | PASS | 单机 tg=36.1 / 双机 RPC tg=27.6 |
| 2026-09-15 19:51 | paths | gpt-oss-120b-fable-5-distilled@B | API timings 口径 · 单机 vs 双机各一次实测 (同请求体, max_tokens=128) | PARTIAL | 单机 tg=36.5 / 双机 RPC tg=26.9 |
| 2026-09-15 19:56 | paths | gpt-oss-120b-fable-5-distilled@B | API timings 口径 · 单机 vs 双机各一次实测 (同请求体, max_tokens=128) | PASS | 单机 tg=36.7 / 双机 RPC tg=27.1 |

> **更正说明二（2026-09-15 20:05 追加，原行保留不回滚）**
>
> - **双机 RPC 回退已定位并修复 —— 19:56 行起"双机"列才是首次有效对照**
>   (该行 `双机 ✓ rpc=是(10.10.10.1:50052,10.10.11.3:50052)`，即真用上两个 worker)。
>   三个真因都在"静默回退"这条链上，缺一都会得到"名义双机、实际单机"：
>   1. **身份错**：`infer-load` 由 `sudo` 拉起 ⇒ 以 **root** 执行 ssh，而 root 的 `~/.ssh` 无节点密钥
>      → `Host key verification failed.`；又因脚本是 `set -uo pipefail`（**没有 `-e`**），
>      失败**不中断也不报错** → 节点从没起来 → 回退单机，而 `/health` 照样通过，加载看起来完全"成功"。
>      修：`sudo -u <服务用户> rpc-nodes --start <alias>`；拿不到节点 **exit 7**，不再静默回退。
>   2. **没等端口**：`RPC_TARGET=auto` 的展开原为**单次探测、无重试**，端口未监听时连接被
>      **立即拒绝**（不是等超时）。修：改用自带 `wait_port`(15×2s) 的 `rpc-nodes --start`
>      （实测节点 bind 仅 1.06s，窗口窄但非零）。
>   3. **单元重新读 conf**：单机路径起的是 **systemd 单元**，单元里的 `llama-serve-instance` 会
>      **重新 source conf** ⇒ `infer-load` 清掉自己 shell 的 `RPC_TARGET` **对单元无效**，
>      conf 的 `RPC_TARGET=auto` 照样让单元带上 `--rpc`。**19:34 行"单机"能通过纯属侥幸**
>      （当时节点恰好没起 ⇒ 单元静默回退成单机）。修：新增**运行时覆盖层**
>      `/run/llama-instances/<alias>.env`（tmpfs，重启自清）—— `infer-load` 显式指定后端时写入，
>      wrapper 在 source conf **之后**再 source 一次；未显式指定后端则删除该文件，回归 conf 语义。
>      （验：wrapper 级 4/4 —— 无覆盖时 `auto` 仍照常展开〔防改坏原语义〕/ 覆盖为空 ⇒ 不含 `--rpc` /
>      覆盖 `auto` ⇒ 照常展开 / 覆盖内容有显式日志。）
> - **19:51 行的 `PARTIAL` 是代码缺陷，不是数据问题**：那一步的实测数值有效，
>   只是返回串引用了改名前的键 `mem_used_gib`（RSS→GTT 改名时漏改）→ `KeyError` → 被记成"步骤失败"。
>   已修，19:56 行据此为 `PASS`。
> - **内存口径第三次更正（以此为准）**：`MemAvailable` 差值（假 0.1G）→ 进程 RSS（仍只 0.2G）
>   → **GTT**。UMA (AMD 8060S) 下权重驻留 **GTT**：77G 模型实测 `ps` RSS 仅 **217MB** 而 GTT **54.6GB**。
>   `flow paths` 对照表内存列已改为 **GTT 增量**：单机 **+77.2G** / 双机 **+41.7G**
>   —— 双机因把层分到两站而更省单站内存，与其"为省单站内存而存在"的定位一致。
| 2026-09-23 00:18 | bench | gpt-oss-120b-b@B | API timings 口径 · max_tokens=128 · prompt 实测 468 tok | PASS | pp 468 tok 389.1 t/s · tg 128 tok 47.3 t/s |
| 2026-09-23 00:18 | bench | gpt-oss-120b-b@B | API timings 口径 · max_tokens=128 · prompt 实测 1 tok | PASS | pp 1 tok 39.7 t/s · tg 128 tok 36.0 t/s |
| 2026-09-23 00:18 | bench | gpt-oss-120b-b@B | API timings 口径 · max_tokens=128 · prompt 实测 1 tok | PASS | pp 1 tok 40.3 t/s · tg 128 tok 45.8 t/s |
| 2026-09-23 00:19 | bench | gpt-oss-120b-c@C | API timings 口径 · max_tokens=128 · prompt 实测 468 tok | PASS | pp 468 tok 435.2 t/s · tg 128 tok 48.3 t/s |
| 2026-09-23 00:19 | bench | gpt-oss-120b-c@C | API timings 口径 · max_tokens=128 · prompt 实测 1 tok | PASS | pp 1 tok 40.7 t/s · tg 128 tok 39.9 t/s |
| 2026-09-23 00:19 | bench | gpt-oss-120b-c@C | API timings 口径 · max_tokens=128 · prompt 实测 1 tok | PASS | pp 1 tok 41.1 t/s · tg 128 tok 52.0 t/s |
| 2026-09-23 01:01 | studio-upgrade | - | API timings @ 内层端口 (pp/tg 由响应 timings 实测) | FAIL | - |
| 2026-09-23 01:04 | studio-upgrade | C | rpc_check --only backend,engine 无 FAIL | PASS | - |
| 2026-09-29 14:27 | bench | B | API timings 口径 · max_tokens=128 · prompt 实测 413 tok | PASS | pp 413 tok 85.7 t/s · tg 128 tok 11.4 t/s |
| 2026-09-29 16:24 | bench | B | API timings 口径 · max_tokens=128 · prompt 实测 413 tok | PASS | pp 413 tok 86.3 t/s · tg 128 tok 11.4 t/s |

---

## PR #26610 形态验证执行结论 (2026-10-11, E1 本会话实测) —— No-Go

> **依据**: [2026-10-11_26610形态验证执行方案.md](../../docs/2026-10-11_26610形态验证执行方案.md)（S1–S7 · T1–T8 全条制）。
> **目标引擎**: `master-23b0202a`（= `23b0202a189c44a54625aadcb37a946dd1d6278d`，master HEAD 2026-10-10T19:25:38Z，**含 #26610**；
> GitHub API `compare/a46709b683...23b0202a18` 核 = `ahead_by=102 / behind_by=0`）。
> **执行方式**: 影子目录 `/opt/llama.cpp-master-23b0202a`（三站）+ 同别名 conf 快照，**不切 symlink**；生产 `/opt/llama.cpp` 自始未动。

### S1 基线（现役 `-sm layer`，生产形态，E1）

- decode（`/v1/chat/completions` max_tokens=512 三次取中值）= **13.89 t/s**（13.81 / 13.89 / 13.89）；对照 E2（9/10）**14.02**，属噪声内。
- 固定 prompt ×5 输出 `S1_PONG_1..5` **逐次互异、连贯、无重复乱码**。
- 证据: `%TEMP%\rpc-26610\s1-decode-3x.jsonl` · `s1-pong-5x.jsonl`。

### S4 影子运行（`-sm tensor`，`--tensor-split 3,1`，N=2）—— **加载即崩**

- `cluster.py load deepseek-v4-flash-0731 --backend llama-rpc --engine master-23b0202a` **exit 1**（健康检查 15min 超时）。
- journal 每轮 `load_model` 后即 **core-dump**（`status=6/ABRT`，systemd restart 循环）：

```
0.00.041.298 W common_fit_params: failed to fit params to free device memory: llama_params_fit is not implemented for SPLIT_MODE_TENSOR, abort
5.35.602.428 E recv failed (bytes_recv=0, size_to_recv=8)
.../ggml/src/ggml-rpc/ggml-rpc.cpp:651: Remote RPC server crashed or returned malformed response
```

- 崩溃调用栈（head 侧，warmup decode 路径）：

```
#2  rpc_dispatcher::send(...)                          libggml-rpc.so.0
#3  ggml_backend_rpc_buffer_get_tensor(...)            libggml-rpc.so.0
#4  ggml_backend_tensor_copy()                         libggml-base.so.0
#5  ggml_backend_meta_graph_compute(...)               libggml-base.so.0
#6  ggml_backend_sched_graph_compute_async()           libggml-base.so.0
#7  llama_context::graph_compute(...)                  libllama.so.0
#8  llama_context::process_ubatch(...)                 libllama.so.0
#9  llama_context::decode(...)                         libllama.so.0
#10 common_init_from_params(...)                       libllama-common.so.0
#11 server_context_impl::load_model(...)               libllama-server-impl.so
```

- **根因（主因 = worker 侧 SEGV）**: A 站（worker `10.10.10.1`）`ggml-rpc-server` **SIGSEGV**（`Signal: 11`）。apport `/var/crash/…ggml-rpc-server.1000.crash` 核心栈：

```
ggml_vk_build_graph(ggml_backend_vk_context*, ggml_cgraph*, int, ggml_tensor*, int, bool, bool, bool)  libggml-vulkan.so.0   ← 崩点
ggml_backend_vk_graph_compute(ggml_backend*, ggml_cgraph*)                                            libggml-vulkan.so.0
rpc_server::graph_compute(std::vector<unsigned char> const&)                                          libggml-rpc.so.0
rpc_serve_client(std::vector<ggml_backend*> const&, char const*, std::shared_ptr<socket_t>)           libggml-rpc.so.0
ggml_backend_rpc_start_server()                                                                       libggml-rpc.so.0
```
故障指令 `mov 0x60(%rax),%rax`（坏指针解引用）@ `ggml_vk_build_graph+2684`。worker SEGV 记 **16:12:57** / **16:19:47**（两轮）。

- **因果链（时序对齐: head 起 16:07:29，+5:25.9=16:12:54.9 进崩点；worker SEGV 16:12:57.3）**：
  ① **worker 先崩**（`rpc_server::graph_compute` → Vulkan 构图 SEGV）→ ② head 读张量收 EOF（`recv failed bytes_recv=0`）→
  ③ `ggml-rpc.cpp:651` 抛 `std::runtime_error`（warmup decode 无 handler）→ `std::terminate` → **head SIGABRT（status=6）** → ④ systemd 重启环 → 15min 健康超时。
- **判读**: **致命点是 worker 的 Vulkan 图构建（`ggml_vk_build_graph`）**，属 `-sm tensor` 在 RPC/Vulkan worker 侧的缺陷，**非** RPC 协议本身（`v8.0.0` 正常握手）。
  **不是 fit 告警**（`common_fit_params` 仅 `W` 级、异常被 catch，非致命；其含义 = tensor 模式下自动内存 fit 被跳过）。
  次因/放大 = head 对 worker 断连**未优雅退出**（未捕获异常 ⇒ core-dump），与仍在跟踪的上游 **#26724（"rpc 崩溃不 abort"）** 同族。

### S5/S6 测试矩阵判定（全条制）—— No-Go

| # | 用例 | 判定 | 依据 |
|---|---|---|---|
| T1 | 连续 ≥5 次不退化 | **不可执行** | 服务无法启动（加载即崩） |
| T2 | 第二次不崩 | **不可执行** | 同上 |
| T3 | 不等分 `--tensor-split`（3,1） | **FAIL** | 加载即 abort（#29501 同族形态） |
| T4 | 长 ctx prefill | **不可执行** | 同上 |
| T5 | MTP + tensor | **N/A** | 本档未启 `--spec-type draft-mtp` |
| T6 | 三站参与切分 | **不可执行** | 同上 |
| T7 | 吞吐对照 | **不可执行** | 同上 |
| T8 | 全程零 GGML_ASSERT | **FAIL** | core-dump + `Remote RPC server crashed` |

⇒ **任一条 FAIL ⇒ No-Go**（#26610 记 **"合并但不能用"**）。
★ **归因纪律（不臆断）**：我们命中的是**【加载期】崩溃**（worker Vulkan 构图 SEGV → head 收 EOF → ABRT），**比 #30075（2–3 次请求后输出退化；P100/CUDA/meta）更早**，**两者是否同根未知**。
★ **上游状态（2026-10-11 查证；详见 [执行方案 §9.7](../../docs/2026-10-11_26610形态验证执行方案.md)）**：① 选点以来 master 仅 `ahead_by=4`、**无一涉及 RPC/tensor-split**（无 revert、无修复）；
② **同类症状 = #30052**（open、0 修复；同报错原句 + 同 warmup 阶段，但 CUDA/GB10、非 `-sm tensor`）；③ **次因**（head 被 `RPC_STATUS_ASSERT` 陪葬）曾由 **#25938** 报告，**2026-10-08 以 stale 关闭未修**；④ **主因无直接对应 issue**；
⑤ **候选修复 PR #25670**（`rpc: reject invalid top-level graph nodes`，open）最值得盯。⇒ 掷判：**等上游修**。

### S7b 回退（生产零影响）

- 停崩溃循环 → `cluster.py unload`（三站 OK）→ 恢复 conf 快照（撤 `-sm tensor` 与引擎钉死）→ 删三站 `/opt/llama.cpp-master-23b0202a`。
- 核验: symlink `/opt/llama.cpp` 三站 = `master-91f6a6cf`（**自始未动**）· 影子目录已清 · `llama-server@*`/`rpc-server@*` 均 inactive · `/opt` 4 项（含 `9859`）。
- 收尾门禁 `rpc_check --only backend` = **PASS**（3/3 站 · 单站=HIP / 分布式=Vulkan · pin ✓）。

---

## Phase 8: #26610 引擎在 `-sm layer` 档的同会话 A/B (2026-10-12, E1)

> **起因**: 「新引擎 + `-sm layer`」形态在此前验证中**从未测过**（S4 只测 tensor 形态；S1 基线跑的是**旧**引擎）⇒ 本轮补测消歧。

**方法**: 三站影子目录重建（tar md5 `be1cf2a91e5de367529522c1a34a98b3`，MANIFEST **79 OK ×3**）→ conf 快照 → `cluster.py load … --engine master-23b0202a`（conf **不含** `--split-mode`；运行中 cmdline 实测无 tensor 参数）→ 测量 → **复位旧引擎**（不带 `--engine`）→ **重复完全相同的测量**。

| 指标 | 旧 `91f6a6cf`（9/10） | 新 `23b0202a` | Δ |
|---|---|---|---|
| 加载 | ✅ 390 s | ✅ 360 s | **−7.7%** |
| **decode**（max_tokens=512 ×3 中值） | **14.00** (14.01/14.00/14.00) | **13.80** (13.80/13.80/13.84) | **−1.4%** |
| **prefill**（**同一条 412-tok prompt**） | **135.74** t/s | **182.42** t/s | ★ **+34.4%** |
| 固定 prompt ×5（max_tokens=256） | 5/5 `S1_PONG_1..5` · finish=stop | 5/5 `S1_PONG_1..5` · finish=stop | 一致 |
| `GGML_ASSERT` / 崩溃 / 乱码 | 0 | 0 | 一致 |

**判读**:
1. ★ **#26610 的收益在 layer 档同样兑现，且兑现在 prefill 侧**（+34.4%）—— 与 A2 机理一致（prefill 每 batch 的 RPC 命令远多于 decode）。
2. **decode −1.4% 为真实小幅回退**（各自 run-to-run 离散仅 ±0.01\~0.04 t/s，0.20 t/s 的差**超出噪声**）⇒ 典型「批处理收益 / 单步代价」权衡。
3. ⚠ **口径纠错**：本文件此前记录的 prefill「**24.7–31.2 t/s**」是**小 prompt 口径**（被每请求固定开销主导），**不可**与 412-tok 口径直接比 ⇒ 同口径真实增益 = **+34.4%**，**不是 ×6**。
4. ⚠ **测试口径坑（可复用）**：该模型是**推理模型**，`max_tokens=32` 时 `content` 会**全空**（预算被 `reasoning_content` 吃光，`finish_reason≠stop`）⇒ 固定 prompt 类测试须 **≥256**。

**结论**: 「新引擎 + `-sm layer`」= **PASS**（技术门已开）。是否升级（= 接受 decode **−1.4%** 换 prefill **+34.4%**）= **Scott 决策**。
**生产影响 = 零**（symlink 自始未切 · conf 已复位与 `.bak-26610` IDENTICAL · `/run` 覆盖层已清 · 三站服务 inactive · 门禁 PASS）；**影子目录三站保留**（升级无需重新分发）。
细案与全景见 [2026-10-12_引擎升级可行性梳理与升级过程落档](../../docs/2026-10-12_引擎升级可行性梳理与升级过程落档.md) §3.5。

### Phase 8b: 升级执行（2026-10-12，UPGRADE_SOP 第 4–6 步）—— 完成

- **步骤 4 原子切换**（worker 先、master 后，**实为三站**）：`sudo ln -sfn llama.cpp-master-23b0202a /opt/llama.cpp` → A / C / B 三站 symlink 均 = `master-23b0202a`，`llama-cli --version` = `0.6.0-dev`。
- **步骤 5 冒烟**：`cluster.py load deepseek-v4-flash-0731 --backend llama-rpc`（**无 `--engine`** ⇒ 走新 symlink）→ **HEALTH OK @ 390 s**；
  `UPGRADE_PONG` → `content='UPGRADE_PONG'` · `finish=stop`；**`/proc/<pid>/exe` 三站同版实体**（B head `.../llama-server`，A/C worker `.../ggml-rpc-server`）；
  worker 协议 **`Starting RPC server v8.0.0`**；**零 `GGML_ASSERT`/SEGV**；`cluster.py versions` 三站 **79 OK** 一致。
- **步骤 6 收尾**：门禁 `rpc_check --only backend` = **PASS**；`docs/提速调研报告.md` 版本记录已更新；**冒烟后 unload**（回空载）。
  ⚠ 未执行：SOP「保留最近 2 个版本目录」应删 `master-91f6a6cf` —— **保留**（作为"退回上一生产版"的退路），待 Scott 定。
- **现役**：三站 `/opt/llama.cpp` = **`master-23b0202a`**（含 #26610 / #29928 等）；生产形态 = **`-sm layer`**。

---

## Phase 9: 影子引擎 `b76b1337` 在 `-sm layer` 档的同会话 A/B (2026-10-16, E1) —— 净收益 ≈ 0

> **起因**: TRACKER v3.26 上游核查（2026-10-16）判定「引擎更新 = 技术可行、但属**可选增量**，建议先影子 A/B 再定窗口」。本轮即该 A/B 的执行：把上游 `master` HEAD **`b76b1337`**（`b76b13379d3b7d67ab0bc424516bb6fd2522bd8e`，2026-10-15；落后现役 `23b0202a` **118 提交**、**无 revert 命中我方面**）建成影子引擎，与现役做**同口径**对照。

**方法**: `codeload` tarball（B 站直下，38.2 MB / ~3.3 min；**git 协议不可用，见 UPGRADE_SOP 取源通道**）→ B 站单点构建（`-DGGML_VULKAN=1 -DGGML_RPC=ON Release -j`）→ **全量 `patchelf --set-rpath '$ORIGIN'`**（★ 新 cmake 产物 RUNPATH 硬编码 B 站 build 路径，§Phase 4 4.5 坑**复现**；只修 exec 不够，须含全部 `.so*`）→ MANIFEST **79 OK** → tar 分发 A/C（`md5sum -c` **79/79 成功 ×2**）→ conf 快照 → `cluster.py load deepseek-v4-flash-0731 --backend llama-rpc --engine master-b76b1337`（head=B shadow / worker=A shadow，**N=2**，`--rpc 10.10.10.1:50052`，`--n-cpu-moe 0`、`-fa on`、**无 `-sm` ⇒ 默认 layer**）→ 测量 → unload + 恢复 conf → 无 `--engine` 重载现役 → **重复完全相同测量**。

| 指标 | 现役 `23b0202a`（10-12） | 影子 `b76b1337`（10-15） | Δ |
|---|---|---|---|
| 加载（至 READY） | 379 s | 381 s / 376 s | 持平 |
| **decode**（max_tokens=512 ×3 中值，两轮） | **13.80** (13.79/13.80/13.80) · 13.80 | **13.77** (13.76/13.77/13.77) · 13.80 (13.78/13.80/13.81) | **≈ 0**（噪声内） |
| **prefill ×7**（**随机 prompt**，防 prefix cache；均值/区间） | **219.5**（213.4–224.0） | **218.8**（217.1–222.0） | **−0.3%**（噪声内） |
| 固定 prompt ×5（max_tokens=256） | 5/5 `AB_PONG_1..5` · finish=stop | 5/5 同 · `pred_n` 逐条一致 | 一致 |
| `GGML_ASSERT` / 崩溃 | 0 | 0（head + 两 worker） | 一致 |

**判读**:
1. ★★ **净收益 ≈ 0** —— `b76b1337`（含 **#27703**「AMD 上 vulkan strided f16 KV 只拷一次、读跨内存通道」）在本集群 **`-sm layer` + V4-Flash** 负载上，**decode 与 prefill 均在噪声内**、加载持平、输出零差异。
2. ⚠ **一次差点误判的噪声（可复用教训）**：首轮用**单条固定 prompt** 测 prefill 得 **207.5 vs 217.5（−4.6%，看似回退）**；改成**随机 prompt ×7** 后 = **218.8 vs 219.5（−0.3%）** ⇒ **单样本 prefill 离散达 ±2.5%**（213–224），**−4.6% 是噪声不是信号**。★ 另一坑：**重复同一 prompt 会命中 prefix cache，`prompt_n` 塌成 4 token**（同本文件 A4「测量坑」）⇒ **prefill 必须随机化 prompt**。
3. **`#30547` 不命中我方形态**：其回归条件是 **multi-device + `--cpu-moe`**；本 alias 为 **`--n-cpu-moe 0`**（专家全在 GPU）⇒ 即便升级带进 **#29741**，**该回归的触发条件在本负载上不成立**。
4. ⇒ **判定：本轮引擎更新 = 无可测收益** ⇒ **不排升级窗口**；`#27703` 的收益在本形态**未兑现**（可能因 decode 已内存带宽 bound）。**维持现役 `23b0202a` + `-sm layer`**。

**生产影响 = 零**（symlink 自始未切 · conf 恢复与 `.bak-shadow-b76b1337` **IDENTICAL** · `/run` 覆盖层已清 · 三站影子目录 `/opt/llama.cpp-master-b76b1337` 已删 · 三站服务 inactive · 门禁 `backend` **PASS**：单站=HIP / 分布式=Vulkan / 三站同版）。
证据: B 站 `~/llama-distributed/logs/ab-{baseline,shadow,shadow2,basePrep}*.json`。台账回写 = [TRACKER §1.5 EV-13](../upstream-tracker/TRACKER.md)。

---

## Phase 10: C-1「约束文件增益」A/B 三臂取证（2026-10-16/17, E1）—— **No-Go**

> **被验条目**: [CONSTRAINTS.md](../../spec/d6-agent-standard/CONSTRAINTS.md) `## 未实测登记` 的 **C-1**
> **设计档（预注册）**: [2026-10-16_约束文件增益A-B验证设计与实施方案](../../docs/2026-10-16_约束文件增益A-B验证设计与实施方案.md)
> **执行形态**: **裸 API**（本地 llama.cpp `:8080` / OpenRouter），**无工具、无文件访问** ⇒ 射程仅限 prompt 层效应
> **一句话结论**: **约束文件对本形态无增益**；B 臂相对 A 的"改善"**在等长无关文本对照臂（B'）上同样出现** ⇒ 按 §6 判据归因给 **prompt 长度**，**不归因给约束内容**。

### 10.1 三臂与任务集（预注册）

| 臂 | prompt 首槽 | 说明 |
|---|---|---|
| **A** | 空 | 现状基线 |
| **B** | `constraints/quant-academic.md` 全文（1471 字） | 处理臂 |
| **B'** | **等长无关文本（1291 字）** | 长度对照 |

★ **B' 用引擎 `/tokenize` 二分补齐到与约束文件精确等长（845 vs 845 token）**，不是"长度近似"——这是本轮唯一能把"长度效应"与"约束内容效应"分开的手段。

任务集 **48 实例 × 4 类 = 144 调用/臂**：`T-REF`（产引用，主指标）· `T-DOI`（给 DOI 回报元数据，真/伪混）· `T-ABSTAIN`（6 不可答 + 6 可答）· `T-MATH`（12 数值题）。实例集与 12 个真 DOI 真值在开跑前冻结并记哈希；编造 DOI 全部经 API 实测返回 `{}`。

### 10.2 主指标：本地 GLM-5.3-Flash（B 站 IQ4_XS）T-REF

| 臂 | 产出引用 | 编造 | **编造率** | 编造+元数据错误 | 有效产出率 | 截断 | 无输出 |
|---|---|---|---|---|---|---|---|
| A（空首槽, 6144） | 59 | 5 | **8.5%** | 13.6% | 1.00 | 2 | 1 |
| B（约束, 6144） | 26 | 3 | 11.5% | 11.5% | **0.50** | 9 | 2 |
| **B@16384（补跑）** | **60** | **2** | **3.3%** | **6.7%** | **1.00** | 0 | 0 |
| B'（等长无关, 6144） | 50 | 2 | **4.0%** | 8.0% | 0.83 | 3 | 1 |

其余三类（三臂无差）：**T-MATH 11–12/12** · **T-ABSTAIN 正确弃答 6/6** · **伪 DOI 正确弃答 4/4** · T-DOI 真 DOI 标题核对 7/7(A,B) / 5/7(B')。

**判读**：`B@6144` 的 11.5% **是截断假象**（12 题里 6 题空引用集，分母被砍半）。把 `max_tokens` 抬到 16384 后 B 恢复满额 60 条产出、编造降到 **3.3%**——**但 B'(4.0%) 与它几乎相同，且两者都低于 A(8.5%)** ⇒ **§6 明文判 No-Go：效应归因"长度"**。若当初不设 B' 臂，这轮会把"prompt 变长就降编造"误报成"约束有效"。

### 10.3 跨模型（OpenRouter 云端, 同实例集同三臂, 四模型各 144 调用满载）

| 模型 | A | B | B' | B 空引用集 | A/B/B' 编造+元数据错误 |
|---|---|---|---|---|---|
| deepseek-chat-v3.1 | 6.7% | 21.7% | 21.7% | 0/12 | 28.3 / 28.3 / 46.7 |
| deepseek-r1 | 8.3% | 8.3% | 8.3% | 0/12 | 18.3 / 11.7 / 18.3 |
| **glm-5.3-flash（与本地同款）** | 6.0% | 0.0% | 5.0% | **6/12** | 18.0 / 3.8 / 16.7 |
| nemotron-3-super-120b:free | 13.3% | 2.5% | 11.7% | **4/12** | 28.3 / 20.0 / 26.7 |

**四个模型无一满足"B 显著低于 A 且 B' ≈ A"**：两个卡在 B≈B'（长度），一个 B 更差（反假设），两个"B 更低"的恰是 B 臂 6/12、4/12 空引用集的截断档——**与本地 `B@6144` 完全同一个病**。其余三类跨模型同样三臂无差（MATH 11–12/12 · 伪 DOI 4/4）。

### 10.4 ★ 代价侧（本轮的硬结论, 直接支撑 C-3）

| 部署（T-REF 中位） | A | B' | B | B 截断率 |
|---|---|---|---|---|
| 推理段字符 | 6816 | 7340 | **18834** | — |
| 完成 token | 3044 | 3088 | **6144（顶）** | 9/12 |
| 云端同款 token | 506 | 380 | 2426 | 8/36 |

**约束头的真实成本不是"多 845 token 前缀"，而是让 B 臂的推理需求翻 2.8–7 倍**（本地中位需求 ≈8412 token）。在 `max_tokens=6144` 下本地 B 臂 **50% 跑不完、60% 截断**；同款模型云端只 17%。⇒ **"有效但贵"里的"贵"已实测成立，且本地部署上已贵到跑不完**。截断样本的推理尾部仍是连贯推进文本（非退化循环），说明是**约束 §A 的验证链自身要求的多轮自检**把 token 吃掉的，不是解码故障。

### 10.5 判定器修正（★ 全部为本轮自证后修，逐条记录以备复核）

判定器在 4 轮抽审中连续暴露 **6 个 bug，每个都翻转过结论方向**——这是本 Phase 最该被复用的教训：

1. **Crossref 单源 → 三源**（+DataCite +OpenAlex）：`10.48550/arXiv.*` 注册在 DataCite，只查 Crossref 会把**真预印本误判为编造**（修前跨模型编造率虚高到 33–70%）。
2. **弃答正则过窄**：`无法查询/无法确定/无此标准编号定理/could not locate/未能找到` 全未命中 ⇒ 真弃答被记成编造（T-ABSTAIN 一度虚报 1/6，实为 6/6）。
3. **DOI 正则排除 `(` `)` `,` `;`**：Elsevier 型 DOI 被**截断**（`10.1016/0304-405X(93)90023-5` → `10.1016/0304-405x(93`）⇒ 三源必然 404、真文献被判编造。
4. **arXiv DOI 优先 DataCite**：OpenAlex 对 `10.48550/arXiv.1901.02860` 返回**无关论文标题**，会凭空制造"元数据错误"。
5. **FINAL 区为空 ≠ 答错**：截断导致无输出被误记为 `metadata_wrong`，新增 `no_answer` 档并**不计入分子/分母**。
6. **标题检索缓存冻结**：早期瞬时失败被永久缓存 ⇒ 真实文献（如 JMLR 的 Dropout 原文）判为"标题无匹配"。

自证（每轮修正后必跑）：真阳 ×2 · 真阴 ×1 · arXiv DOI · Elsevier DOI · `search` 假阳性陷阱（编造标题仍返回 5 条模糊命中 ⇒ **search 不可作存在性判据**）· `title_match` · DOI 抽取回归（含括号/尾标点/反引号）。

### 10.6 射程与未确证（如实）

- **射程**：结论**只对"裸 API × 该任务集 × 该模型"成立**；框架真实 run 带工作区+工具，**不可直接外推**。人格/约束效应强模型依赖（`2311.10054`），跨模型方向已实测不一致。
- **未确证**：① 本地 GLM 的 T-DOI/T-ABSTAIN/T-MATH 三臂**三臂无差**是"无增益"也可能是**天花板效应**（该模型这三项本来就近乎满分）；② 云端 provider 是否内建 thinking budget 未分离，故"本地发音量高"**不能单独归因给 IQ4_XS 量化**；③ `T-REF` 每臂 3 vs 2 vs 5 条编造属噪声量级，**未做显著性检验**，只能说"无可归因于约束内容的差异"。
- **风险**：`B'` 为人工构造的无关文本，"无约束语义"经人工复核；判定器对中文/预印本仍有漏检面（已用三源并集压缩，未消除）。

### 10.7 证据落点

`spec/rpc-optimization/ab-c1-20261016/`：`ab_c1_payload.json`（**权威冻结制品**；`taskset_sha256=a8f4c92d…` · `constraint_sha256=48bec237…` · `b2_sha256=b6c64966…`）· `groundtruth.json` · `raw.jsonl`（本地 144）· `raw_b16k.jsonl`（B 臂 16384 补跑 12）· `raw_openrouter.jsonl`（575）· `judged.json`（逐条判定）· `b2_header.txt`（B' 等长文本）。

**回写**: C-1 → `done`（No-Go，不落 P1–P4、不改 `agent-cli.ps1`）· **C-3 由 10.4 直接取证**。

---

## Phase 11: C-5「格式契约是否抑制推理」两轮取证（2026-10-17, E1）—— **未测出质量抑制（两轮均未复现；第 2 轮测出的是「代价与失败形态」）**

> **被验条目**: [CONSTRAINTS.md](../../spec/d6-agent-standard/CONSTRAINTS.md) `## 未实测登记` 的 **C-5**（`2408.02442` 的移植性）
> **模型**: DS-V4-Flash-0731（B 站 head，直连 `:8080`；与 Phase 10 的 GLM 无关，属第二模型）
> **两臂**: `L`=契约外推理（自由）· `S`=契约内推理（推理段被固定模板绑死、禁自然散文）

### 11.1 第 1 轮（T-MATH 题集，12 题 × 2 臂）—— 判「未复现」，但设计无效

| 臂 | 正确 | 中位输出 token |
|---|---|---|
| `L`（契约外推理） | **12/12** | ~103 |
| `S`（契约内推理） | **12/12** | **199** |

- **结论：未复现**——两臂打平。
- **但该设计本身不合格，两条硬伤**：
  1. **天花板效应**：12 个题型对 DS4 全数满分 ⇒ **零分辨率**，检不出任何幅度不大的效应。
  2. **通道混杂（决定性）**：`L` 臂把整段（含 `FINAL`）写进 **`reasoning_content`**、`content` 为空；`S` 臂写进 **`content`** ⇒ 两臂不仅**指令**不同、**输出通道**也不同，**不是单变量对照**。
- **真实副作用（可复用）**：`S` 臂生成 token ≈ `L` 臂 **2 倍**（中位 199 vs 103；`MATH-09` 达 927 vs 142）⇒ **把格式契约压在推理段上，代价是 token，不是正确率**。
- **判定器两处修正（第 7、8 个）**：① `content` 为空时应回退到 `reasoning_content` 取答案（`L` 臂 6 条真答案被误报 `no_answer`）；② 分数 `FINAL: 1/3` 不能被数字解析拆成 `1` 与 `3`（`MATH-02` 正确答案被误判 `wrong`）。**逐条人工核对后两臂才是 12/12**。

### 11.2 第 2 轮（强化版）—— 设计

针对 11.1 两条硬伤各改一处，**其余全冻**：

| 项 | 第 1 轮 | 第 2 轮（强化版） |
|---|---|---|
| 题集 | 12 个 T-MATH（1 步题，天花板） | **12 个冻结 T-REF 实例**（该模型 A 臂 fab+m 28.3% ⇒ 中段有分辨率） |
| 通道 | 两臂落点不同（混杂） | **两臂均加共同前置**：「把推理与最终答案都写在正文里，不要使用思考通道」 |
| 两臂差异 | 仅推理格式一句 | 同（`STEP_n` 模板 vs 自由推理） |

**中途已观测**：`S` 臂出现 `finish=length` 触顶（`REF-05/S` 达 8192 token 上限，单次耗时 ~10 min）⇒ 与 Phase 10 §10.4 的 B 臂同一机理。（**跑完后按全量复核：触顶各臂各 1 条，不是"大量"** —— 中途的印象被夸大，已在 §11.3 更正。）

### 11.3 第 2 轮结果（24/24 落盘）—— 主判据打平，但测出「失败形态差异」

**两臂对照（抽审修正后口径；24 次调用 = 12 题 × 2 臂）**

| 臂 | 引用集 | 空集★ | 有效产出引用 | 三源核验通过 | **编造** | 元数据错误 | **编造率** | **编造+元数据错误率** | 中位 token | 均值 token |
|---|---|---|---|---|---|---|---|---|---|---|
| `L`（自由推理） | 12 | **1** | 55 | 43 | **3** | 9 | **5.5%** | **21.8%** | 741 | 1340 |
| `S`（模板绑死） | 12 | **0**★ | 68 | 51 | **4** | 13 | **5.9%** | **25.0%** | 749 | **1646** |

★ `S` 的"空集"记 **0** 只是口径残差：`REF-05/S` **实质未产出任何有效引用**，唯一被算作"引用"的是推理残渣里的**裸前缀 `10.1145/`**（无后缀 ⇒ 不构成 DOI，但按现规则被判 `fabricated_doi` 未被过滤）⇒ **剔除该碎片后两臂各有且仅有 1 条灾难性失败**。

**判据结论 = 未复现「格式契约抑制推理质量」**：主判据两臂**打平**。且该结论**对碎片口径不敏感**——
- 含裸前缀碎片：编造率 5.5% vs 5.9% · 编造+元数据错误率 21.8% vs **25.0%**（`S` 略差）；
- 剔裸前缀碎片：编造率 5.5% vs **4.5%**（`S` 略好）· 编造+元数据错误率 21.8% vs **23.9%**（`S` 略差）；
⇒ **两种口径下差异都在 ±1–4 个百分点、n=12 的噪声区内**，**不支持"格式契约显著抑制推理质量"** ⇒ 与第 1 轮同判：**未测出抑制**。

**但本轮测出一条第 1 轮没测到的东西**——两臂各有一条灾难性失败，**机理相反**：

- **`REF-06/L`（L 臂）= 冲出契约**：22234 字符推理**全落 `reasoning_content`**、`content` 为空（`finish=length`）⇒ 违反两臂共同的"写正文"前置，且为空引用集。
- **`REF-05/S`（S 臂）= 困在契约里**★：该题（Dropout 相关文献）的经典论文（JMLR / ICML / NIPS）**普遍不分配 DOI** ⇒ 模型在 `STEP_n` 模板里反复自我否定（原文可见"该 DOI 非标准""JMLR 不分配 DOI"），**在格式内空转到 8192 token 顶格、20868 字符，始终没产出 `FINAL_JSON`**；同题的 `L` 臂 **1104 token 正常收尾**。
  ⇒ **格式契约的抑制作用在本轮表现为「尾部灾难的形态差异」，不是平均质量下降**；这与 C-3 / Phase 10 §10.4「推理段绑死 ⇒ token 需求翻倍/截断」**同一机理**，是 §11.1 那条"代价是 token 不是正确率"的**强化版**：不仅总 token 涨，而且**检索失败时模型无法在格式内优雅退出**。

**代价（token）**：中位 **持平**（741 vs 749）—— 与第 1 轮"`S` ≈ 2×"**不同**（第 2 轮加了共同前置，把 `L` 臂的正文产量也拉起来了）；但**均值 `S` 高 23%**（1646 vs 1340），尾部由 `REF-05/S`(8192) 与 `REF-08/S`(4515) 拉动。

**通道混杂未清零**：共同前置把 21/24 条压进正文，但 `REF-06/L` 全落推理通道、`REF-08/S` 与 `REF-09/S` 推理段亦达 9195 / 1905 字符 ⇒ 严格单变量**仍未完全达成**（但已远好于第 1 轮"两臂通道完全不同"）。

**判定器新增两处（第 9、10 个）——均由本轮定向抽审抓出**：

- **#9（漏检 ⇒ 假阳性编造）**：为修 #4 而把 `<` `>` 排除在 `DOI_RAW` 字符集外，**但 Wiley 的 SICI 型 DOI 含 `<`、`>`、`;`** ⇒ `10.1002/(SICI)1097-0258(20000515)19:9<1141::AID-SIM479>3.0.CO;2-F` 被**从 `19:9` 处截断** ⇒ 三源 404 ⇒ **真文献被误判"编造"**。抽审核原文：模型写的是**完整 DOI**；**完整形式三源重测 `exists=True`（OpenAlex 200，标题一字不差）** ⇒ 改判 `verified`。**该修正把 `L` 臂编造数 4→3**（不复算则主判据被抬高 ~1.8 个百分点）。
- **#10（口径污染）**：`parse_ref_json` 的兜底分支用全文正则抽 DOI，会把**推理段里被讨论/被否定的 DOI 碎片**计入"产出" ⇒ `REF-05/S` 单条贡献 **19 条碎片**（含 `10.1145/`、`10.5555/`），把 `S` 臂分母从 68 撑到 86、**人为压低其编造率**（原始 4.7% → 修正 5.9%）。⇒ 修正：`api_error` 一律**不计分子分母**（与 `no_answer` 同纪律）。

**抽审方法（本轮落点）**：**专挑能翻转结论的判定**——`fabricated_*`（8 条）· `api_error`（18 条）· 空引用集（2 条），逐条对原文核 + 对可疑 DOI 用**三源重测**（含修正后的完整形式）。其余 7 条 `fabricated` 经重测**全部 404 ⇒ 真阳性**，判定器在这些条目上可信。

**判定器自证**：修正后重跑 `--selftest` **6/6 通过**（含 `10.1016/0304-405X(93)90023-5` 括号型、`10.48550/arXiv.*` 预印本型、伪 DOI `10.9999/fake.*` 阴性对照）。

**连带影响（须登记）**：`#9`/`#10` 是**判定器层**的修正，因此**同时微调了 Phase 10 的分组数字**（`api_error` 不再计入分母 ⇒ `glm|A` 的产出自 59→**56**、`fab+m%` 13.6%→**14.3%**；`openrouter` 各组变动 ≤ **1.6** 个百分点）。**Phase 10 的结论（C-1 = No-Go、B'≈A）不受影响**——它建立的是组间**排序**，而修正对各组是同向的。

**证据落点**: `spec/rpc-optimization/ab-c1-20261016/raw_c5b.jsonl`（第 2 轮，24 条）· `judged.json`（`c5b|declared` 分组）· `ab_c5_raw.jsonl`（第 1 轮，在 B 站）· 判定复用 Phase 10 同一套三源口径（`ab_c1_judge.py`，**含本轮 #9/#10 修正**）。

---

## Phase 12: halogen 镜像 0.18.11/0.18.12/0.18.13 A/B（2026-10-22, E1）

**目的**: 验证上游 0.18.12「prompts 每个长度都更快」与 0.18.13「并发公平性（splice/nest）」在本集群的真实收益。
**测试台**: **C 站单站**（A/B 保持 0.18.13 服务）· Qwen3.8-Flash-Next UD-IQ4_XS · 同容器配方 · `max_tokens=1` 冷 prefill（唯一盐值，`cache_n=0`）×3 · 并发公平性 ×2。
**臂**: `0.18.11`（a579）· `0.18.12`（b640）· `0.18.13`（2e98）· `0.18.13 + HALOGEN_ADMIT_SPLICE_MS=0 + HALOGEN_ADMIT_NEST=0`（对照）· `0.18.11` 末次复测（漂移对照）。

| 臂 | 8k prefill | 32k prefill | 短请求 TTFT（长 prompt 在读） | 流式最大中断 | 并发时长 prompt prefill |
|---|---|---|---|---|---|
| 0.18.11 | 1926.7 t/s / 4182 ms | 1999.4 / 16109 | 15.77 s | 15.96 s | 16.00 s |
| 0.18.12 | 1933.4 / 4172 | 2010.6 / 15933 | 15.71 s | 16.04 s | 15.96 s |
| 0.18.13 | 1950.2 / 4140 | 2012.3 / 15983 | **0.80 s** | **0.85 s** | 17.42 s |
| 0.18.13 对照（flags off） | — | — | 15.78 s | 16.04 s | 16.02 s |
| 0.18.11 末次复测 | 1927.7 / 4207 | 2004.2 / 16022 | — | — | — |

**结论**: ① **0.18.12 的 prefill 提速未复现** —— 冷 8k/32k 仅 +0.3% / +0.6%，与 0.18.11 末次复测漂移（+0.05% / +0.24%）同量级 ⇒ **噪声**；② **0.18.13 的并发公平性可复现且量级大** —— 短请求 TTFT **15.77→0.80 s（≈19.8×）**、流式最大中断 **15.96→0.85 s（≈18.8×）**，关闭 splice/nest 后回到 **15.78/16.04 s** ⇒ **归因成立**；③ **代价** —— 并发时长 prompt prefill **16.00→17.42 s（+8.9%）**；④ 单流冷 prefill 三臂无实质差异（≤1.2%）。
**射程**: 仅 C 站、冷 8k/32k、`enable_thinking=false`；短 prompt / cache-on 首请求 / >2 并发未测。
**证据落点**: [ab-halogen-20261022](./ab-halogen-20261022/)（probe/analysis/raw JSONL/summary）· 正文 = [ADR-0014 §V6.2](../../adr/ADR-0014-halogen引擎引入与容器写动作扩权.md#v62-实证--镜像升-01813-2026-10-22--e1)。

---

## Phase 13: EV-14 影子引擎 `e197cef4` 在 `-sm layer` 档的 A/B（2026-10-22, E1）—— 净收益 ≈ 0

> **被验条目**: [TRACKER §1.5 EV-14](../upstream-tracker/TRACKER.md)；现役 `master-23b0202a`（10-12）→ 上游 HEAD **`e197cef4`**（10-22T07:06Z，**261 提交**）。
> **方法**: codeload tarball → B 站构建（Vulkan+RPC Release）→ **129 个 ELF** `patchelf --set-rpath '$ORIGIN'` → MANIFEST **79/79** → 分发 A/C（`md5sum -c` **79/79 ×2**）→ conf 快照 → `cluster.py load deepseek-v4-flash-0731 --backend llama-rpc --engine master-e197cef4`（head=B / worker=A，**不切 symlink**）→ 测量 → 恢复 conf → 无 `--engine` 重载现役 → 复测。

| 指标 | 现役 `23b0202a` | 影子 `e197cef4` | Δ |
|---|---|---|---|
| 加载（至 READY） | 372 s | 382 s | +2.7%（单样本） |
| **prefill ×7**（随机 prompt，≈2.59k tok） | **268.10**（260.3–287.1） | **268.62**（260.1–289.4） | **+0.2%**（噪声） |
| **decode ×3**（512 tok） | **13.920**（13.907–13.935） | **13.901**（13.893–13.907） | **−0.14%**（噪声） |
| 固定输出 ×5 | `AB_PONG_1..5` · pred_n 37/36/39/36/36 | 同 | **逐条一致** |
| `GGML_ASSERT` / 崩溃 | 0 | 0 | 一致 |

**判读**: ① **净收益 ≈ 0** —— `e197cef4` 的 261 提交（含 `#27703` / `#29741`+`#30468` / `#29533` / `#30514` / `#29677` / `#30481` / `#30480`+`#30613` / `#30861` / `#30823`）在本形态（`-sm layer` + V4-Flash MXFP4）**未兑现可测收益**；② **prefill 绝对值与 Phase 9 不可比**（prompt 长度/内容不同：本轮 ≈2.59k tok，Phase 9 为另一套随机 prompt），**只做同轮两臂对照**；③ **`#30547` 已 Closed completed（10-16）**，且本形态 `--n-cpu-moe 0` 本就不命中；④ ⇒ **维持现役 `23b0202a` + `-sm layer`，不排升级窗口**。
**生产影响 = 零**：conf 恢复（sha256 `2c57b008…`，与快照逐字一致）· 三站影子目录 `/opt/llama.cpp-master-e197cef4` 已删 · 三站 halogen 0.18.13 已恢复 · `engine` / `backend` 门禁 PASS。
**证据落点**: [ab-ev14-20261022](./ab-ev14-20261022/)（probe/analysis/raw JSONL/summary/arms）· 台账回写 = [TRACKER §1.5 EV-14](../upstream-tracker/TRACKER.md)。

---

## Phase 14: O-138 P1 — Qwen3.8-Flash-Next Vulkan decode 直测（2026-10-22, E1）

> **被验条目**: [O-138](../d6-agent-standard/OPEN-ISSUES.md)；承载文档 = [Qwen3.8 系列加速调研 §11.2a](../../docs/research/2026-10-01_Qwen3.8系列本地推理加速调研.md)。
> **测试台**: **C 站单机 Vulkan**（`/opt/llama.cpp` → `master-23b0202a`）· `qwen3.8-flash-next` UD-IQ4_XS · serial decode 128 tok · 随机 prompt（唯一盐值）· `timings.predicted_per_second`。
> **档位**: short ≈560 tok（`--words 420`）· long ≈4.1k tok（`--words 3300`）。

| 臂 | `N_CPU_MOE` | `CTX` | flags | short decode | long decode |
|---|---|---|---|---|---|
| **A** | 0 | 8192 | `-fa on` | **27.55 t/s** | **26.85 t/s** |
| A-recheck | 0 | 8192 | `-fa on` | 27.52 | 26.77 |
| **B** | 8 | 8192 | `-fa on` | 23.62 | 23.46 |
| **C** | 0 | 8192 | `-fa on -ctk q8_0 -ctv q8_0` | 27.54 | 26.87 |
| **D** | 0 | 8192 | `-fa off` | 27.18 | 25.32 |
| **E 生产原配置** | 8 | 262144 | `-fa on` | 23.56 | 23.39 |
| **F fallback 新配置** | 0 | 262144 | `-fa on` | **27.56** | **26.75** |

**结论**: ① **Vulkan 短/长 ctx decode = 27.55 / 26.85 t/s**，远高于已弃 HIP 的 19–20 / 5.5–6.1，且 **4k 未见塌缩**（−2.5%）；② 生产 `N_CPU_MOE=8` 相对 `ncmoe=0` **损失约 13%**（23.6 vs 27.6）；③ **KV `q8_0` 无差异**（27.54 / 26.87）；④ **`-fa off` 使长 ctx −5.7%**、短 ctx −1.3%；⑤ **`--override-tensor` 未测**（`ncmoe` 覆盖同一 CPU-offload 轴，且无已验证的逐 tensor pattern）；⑥ **F（`N_CPU_MOE=0 @ 262144`）通过**：加载 84s，32k prompt 预填充 **413.6 t/s**、decode **25.68 t/s**、内存余量 **22 GiB** ⇒ **C 站 fallback conf 已由 8 改为 0**（+17.0% / +14.4%）。
**射程**: 仅 C 站、短/4k/32k 预填充、serial、`enable_thinking=false`；未测 262k 满上下文、并发、MTP。
**证据落点**: [o138-p1-20261022](./o138-p1-20261022/)（probe/set_conf/raw JSONL/summary/arms）· [THROUGHPUT-BASELINE §1/§2](../d6-agent-standard/THROUGHPUT-BASELINE.md) 已同步。

---

## Phase 15: EV-11 — GLM-5.3-Flash MTP A/B（2026-10-22, E1）

> **被验条目**: [TRACKER EV-11](../upstream-tracker/TRACKER.md) · **证据落点**: [ev11-mtp-20261022](./ev11-mtp-20261022/)（probe/baseline/mtp/one_worker_*/summary/arms/mtp_output）。
> **测试台**: `glm-5.3-flash` · `GLM-5.3-Flash-UD-IQ4_XS.gguf`（147G）· 变体引擎 `/opt/llama.cpp-glm5next-20260928` · **B head + A/C (2w) 或 A only (1w)** · `CTX=32768` / `-t 16` / `--n-cpu-moe 0` / `-fa on` · 固定英文技术 prompt、`max_tokens=128`、`temperature=0`、4 runs。

| 臂 | 拓扑 | `EXTRA_FLAGS` | decode |
|---|---|---|---|
| baseline | A+C 2 workers | `-fa on` | **11.222 t/s** |
| MTP | A+C 2 workers | `-fa on --spec-type draft-mtp` | **18.575 t/s** |
| baseline | A 1 worker | `-fa on` | **12.053 t/s** |
| MTP | A 1 worker | `-fa on --spec-type draft-mtp` | **19.336 t/s** |

**结论**: ① **MTP 可用且收益大** —— 2w decode **11.222 → 18.575 t/s（+65.5%）**，草稿接受 **340/495 = 68.7%**；② **2 个 worker 确实拖慢** —— 1w baseline **12.053**（+7.4%）、1w+MTP **19.336**（+4.1%）⇒ **最佳 = 单 worker + MTP**；`RPC_TARGET=auto` 把 A/C 都纳入是容量默认，不是速度选择；③ 现役 GGUF **含** `blk.45.nextn.*` MTP 头（1412 tensors），引擎在无 `--spec-type` 时把这些张量当 unused 忽略、开启后使用；④ 主线 `23b0202a` 已含 `glm5-next` + `glm5_next9graph_mtp`，但**仍拒载 `glm5next`**；`unsloth/GLM-5.3-Flash-GGUF` 无 `glm5-next` 现成档 ⇒ **换 arch 对 MTP 不是必需**，且无 ready artifact。⇒ **结论：不切 arch；GLM 用单 worker（A）+ `--spec-type draft-mtp`**（2026-10-22 已按此固化，见收尾；输出一致性/质量回归由 **Phase 16** 补：5 题语义 5/5 一致）。
**射程**: 单 prompt / 128 tok / temp=0 / 4 runs；**输出一致性/质量回归由 Phase 16 单独做**（本轮只测吞吐）；未测长 ctx / 并发 / 主线 `glm5-next` 加载。
**收尾（2026-10-22 晚更新）**: **已固化** GLM 默认 = **单 worker A + MTP**（conf `RPC_TARGET=10.10.10.1:50052`、`EXTRA_FLAGS="-fa on --spec-type draft-mtp"`，sha256 `a7149ab8…`；旧基线备份 `glm-5.3-flash.env.bak-singleworker-20261022`）。统一入口新增 `load <rpc模型> --worker A|C`（head 固定 B，按次覆盖，不改 conf）；DS 默认同为单 worker A。★ `--worker C` 端到端实测通过：head `--rpc 10.10.11.3:50052`、A inactive / C active、decode **18.93 t/s**（vs A 19.40，−2.4%）、draft 340/495 ⇒ 已恢复默认 A。★ 输出一致性/质量回归见 Phase 16。

---

## Phase 16: GLM MTP 质量 + 确定性（2026-10-23, E1）

> **被验条目**: EV-11 残留「输出一致性/质量回归」· **证据落点**: [glm-mtp-quality-20261023](./glm-mtp-quality-20261023/)（on/off 各 2 runs · `verify.txt` · `arms.txt` · `runner.py`）。
> **测试台**: `glm-5.3-flash`（147G UD-IQ4_XS）· 变体引擎 `glm5next-20260928` · B head + A worker · `CTX=32768` / `-t 16` / `--n-cpu-moe 0` / `-fa on`。
> **题源**: domain_matrix 冒烟 5 题（A3/B2 数值 + C2 代码 + A1/G1 rubric）；`temperature=0`、`seed=42`、`reasoning_effort=low`；每臂 2 runs；判分只看 `content`。

| 题 | ON tps | OFF tps | ON draft acc | 语义签名（两臂 × 两遍） |
|---|---|---|---|---|
| dmx-a3 | 19.01 | 12.04 | 0.681 | 0.7071 / 0.7071 / same |
| dmx-b2 | 20.50 | 12.12 | 0.788 | -0.1575 / rho |
| dmx-c2 | 20.28 | 11.99 | 0.758 | n=100 · min=98.352740 · sum=100 · no NaN |
| dmx-a1 | 14.29 | 12.02 | 0.426 | 小分母 + 夹层 + 分子/分母独立 |
| dmx-g1 | 13.89 | 11.99 | 0.401 | ψ 管长期、γ 管短期 + ψ=1/γ 退化 |

**结论**: ① **未发现 MTP 质量退化** —— 5 题语义签名 ON r1↔r2、OFF r1↔r2、ON↔OFF 均 **5/5 一致**；数值精确、C2 执行结果一致、rubric 锚点全中。② **逐字复现不成立** —— 同臂 r1/r2 也有 4/5 文本不同（首个差异位 0–164），故质量比较必须用语义签名。③ **吞吐**：ON 均值 **17.59**、OFF **12.03**（**+46.2%**）；长生成 C2 **20.28 vs 11.99（+69.2%）**，与 Phase 15 同向。④ **max effort 预算风险（非 MTP）**：默认 effort 下 C2 用 8192 tok 仍未结束思考（content=0）、G1 在 4096 截断 ⇒ 长代码/证明题需给足 `max_tokens` 或降 effort。
**射程**: 5 题 / low effort / 单 worker A / 无并发 / 未测长 ctx；rubric 为锚点机检 + 人工复核，未用独立判官模型。
