# llama.cpp RPC 协议瓶颈专项调研

> **日期**: 2026-08-28
> **作者**: Scott (鹏)
> **适用系统**: A 站 (scott-lau-NEX, Worker) + B 站 (scott-lau-GTR-Pro, Master), USB4 (thunderbolt0) 直连
> **当前状态**: llama.cpp v0.2.0, RPC 协议 v4.0.1, Vulkan/RADV, MiniMax-M2.7 Q4_K_S
> **基线**: 双机 RPC 生成 ~18.2 t/s (v0.2.0 升级后), 理论带宽上限 ~80 t/s
> **定位**: 《提速调研报告.md》第 2.2 节 RPC 协议损耗的专项深挖 + 社区方案追踪
> **v1.1 (2026-08-28)**: 盲区扫描增补 — 工程细节、风险矩阵、验证方法(第六节); 三处判断修正(7.1), 行动清单更新(第五节)
> **v1.2 (2026-08-28)**: 引用审计修正 — **PR #26291 实为未合并(行动项 4 前提作废)**、#22850 关闭性质、#26421 合并日期; 详见《三调研报告审计.md》

---

## 一、执行摘要

RPC 协议瓶颈已从"结构性债务、无人处理"演变为**上游活跃改造区**。2026-08 时点的关键变化:

1. **RDMA transport 已合入 master 并自动协商** — 握手时协商, 失败回退 TCP, 零命令行改动。Apple TB5 RDMA 实测小模型 decode **+226%**; Linux 走 libibverbs/RoCEv2。
2. **PR #26610 (Open) 是 RPC 协议的全面现代化**: async graph_compute、custom all_reduce、graph uid cache、2D 张量传输、F32→BF16 压缩、fire-and-forget 通信 — 直击 #22850 报告的全部四大缺陷。
3. **同硬件社区已跑通 USB4 直连 RDMA**: hellas.ai 的 thunderbolt-ibverbs 内核模块在 2×Strix Halo 128GB 上实现 ~48 Gb/s 单向、~7µs 延迟, 并实测 MiniMax-M2.7 TP=2 双机推理(与本集群同模型)。
4. **零成本立即可做**: `pm_qos_resume_latency_us=100`(Strix Halo 社区实测 USB4 RTT 600-700µs → 134µs, RPC tg128 +2%, stddev 显著收紧)。

**结论**: 短期吃 pm_qos + 参数调优, 中期跟踪 PR #26610 合并后升级, 长期可评估 thunderbolt-ibverbs 路线(工程量大, 同硬件已验证)。

**v1.1 盲区扫描三项核心修正**(细节与证据见第六节):

1. **传输层升级对 decode 的收益预期下调至个位数** — 同硬件社区实测: decode 由算力与每 token 串行跨层传导主导, "换更快链路改变不了结论"(Skulk #329: TB 42.9 t/s vs LAN 45.4 t/s 在噪声内; strix-halo-guide #12 明示 "intrinsic to RPC's per-token sequential layer crossing, not to the link")。传输层红利集中在**加载、prefill、训练(FSDP 梯度同步)**场景; decode 的真正杠杆排序: 模型层 MTP > 协议层 PR #26610 > 传输层。
2. **崩溃传导风险(原报告空白)**: 当前 master(含 v0.2.0) 在 A 站 rpc-server 崩溃/OOM/断链时, B 站 llama-server **整个进程 GGML_ABORT**, 无重连机制; 修复 [PR #26724](https://github.com/ggml-org/llama.cpp/pull/26724) 尚未合并 — 必须以 systemd Restart 兜底。
3. **pm_qos 功耗代价实测仅 +1.5 W/机**(strix-halo-guide #13 三机对照实验, 远低于 v1.0 所写 5-15W); 且 v1.0 漏了 **MTU 9000** 这一同硬件社区 RPC 标配零成本项。

---

## 二、瓶颈机制确认(协议层)

issue [#22850](https://github.com/ggml-org/llama.cpp/issues/22850)(2026-05, karambaso, b9033)的深度剖析, 其机制描述在 v0.2.0 中仍然成立(该 issue 2026-05-08 关闭, state_reason=completed; 机制剖析被后续 PR 持续引用):

| # | 缺陷 | 机制 | 阶段影响 |
|:---|:---|:---|:---|
| 1 | **同步请求-响应** | 每个 op 每层一次 RPC 往返; `send_rpc_cmd` 严格阻塞等待响应 | decode batch=1 时纯延迟主导: 实测 RPC 比本地 PCIe 慢 28%~55% |
| 2 | **元数据风暴** | 每次图执行客户端深度遍历 `ggml_cgraph`, 重新序列化全部张量为 `rpc_tensor`(含固定大小 name 缓冲 `GGML_MAX_NAME`), 即使权重已在远端 | prefill 损失 >33%; 每层引入数百次小消息 |
| 3 | **小张量冗余传输** | `HASH_THRESHOLD=10MB` 以下 SET_TENSOR 跳过 hash 直接裸传; KV/激活更新几乎全部 <10MB | decode 期网络利用率极低(几十 MB/s 级), 带宽远未吃满 |
| 4 | **无数据压缩** | 传输无 LZ4 等压缩, 全裸传 | 带宽压力放大 |

**关键佐证**(与 A/B 集群同硬件同协议): kjaiswal 的 [10GbE Metal+CUDA 实测](https://github.com/kjaiswal/llama-cpp-distributed-benchmarks) — decode 每次往返 ~0.17ms, 7B 模型 decode 慢 2x, 72B 慢 47%; 而 prefill 反而因远端算力受益(7B +4.2x)。**证实: 瓶颈在延迟与协议开销, 不在带宽**。USB4 40Gbps 物理带宽远未用满, 当前 TCP/thunderbolt-net 路径的实际有效吞吐约 10 Gb/s 级。

### 2.1 加载路径瓶颈(已部分解决)

issue [#25890](https://github.com/ggml-org/llama.cpp/issues/25890): 535GB 模型加载 ~15 min, 单核 69% busy, NIC 95 核全闲 — 每张量串行 read+FNV hash+dispatch。**[PR #26291](https://github.com/ggml-org/llama.cpp/pull/26291) 审计核实仍 Open 未合并(v1.2 修正, 2026-08-28)** — v0.2.0(8-21 标签)不含 `GGML_RPC_LOAD_THREADS`, 该环境变量在当前二进制上无效; 加载并行化仍是未来项。剩余方向: 多 socket 分片发送(协议版本号升级)、rpc-server 本地 `-c` 缓存预填充。

---

## 三、社区优化方案全景

### 3.1 已合入 master — 立即可用

#### A. RDMA transport(自动协商)

[tools/rpc/README.md](https://github.com/ggml-org/llama.cpp/blob/master/tools/rpc/README.md) 官方文档:

- **机制**: 握手阶段协商 transport, 双方都支持 RDMA 则升级, 否则回退 TCP。**命令行零改动**。
- **Linux**: RoCEv2 网卡(如 Mellanox ConnectX), 经 libibverbs。构建时检测到库即编入。
- **macOS**: TB5 RDMA(librdma, macOS 26.2+)— [PR #26421](https://github.com/ggml-org/llama.cpp/pull/26421)(作者 ryan5rdx, 2026-08-25 由 ggerganov 合并; v1.2 修正日期)。
- **实测数据**(PR #26421, M3 Ultra, Qwen3-0.6B, layer parallel):

| 节点数 | prefill TCP→RDMA | decode TCP→RDMA |
|:---|:---|:---|
| 2 | 5296→7227 t/s (+36%) | 115.6→261.3 t/s (**+126%**) |
| 4 | 4007→6250 t/s (+56%) | 87.7→133.5 t/s (+52%) |

- **适用性判断**: 小模型收益巨大(RPC 占比高); 230B MoE 模型 RPC 往返占比相对小, 收益会衰减但仍可观。
- **Strix Halo 的问题**: 无硬件 RoCE NIC。可行路径见第四节(软 RoCE / thunderbolt-ibverbs)。

- **验证方法**(本集群): A 站 rpc-server 启动日志看 `transport : TCP (RDMA auto-negotiate enabled)` 行 — v0.2.0 构建于 B 站, 若编译时未装 libibverbs-dev 则该行可能缺失或显示纯 TCP。**需实测确认现有二进制状态**。

#### B. rpc-server 本地缓存(`-c`)

权重仅首次跨网传输, 重启后从 worker 本地盘加载(#25890 作者确认 reload 0 网络流量)。4.4 分钟冷启动的主因之一是权重全量跨网。**A 站 start_rpc.sh 加 `-c` 即可**。

#### C. `-ot` 张量覆盖 + RPC 专家 offload

master 现成功能, discussion [#27393](https://github.com/ggml-org/llama.cpp/discussions/27393) 演示语法:

```bash
-sm layer -ts 0,1 -ot "blk\.[0-9]?[02468]\.ffn_(up|down|gate|gate_up)_(ch|)exps=RPC0[10.10.10.1:50052],.ffn_(up|down|gate|gate_up)_(ch|)exps=CPU"
```

把部分专家权重放 RPC 远端、部分本地 CPU — **少量张量走 RPC 时延迟成本可接受**, 适合"GPU 放不下但 RPC 全切太慢"的中间态。Kononnable 的测试分支进一步做了 tensor-split 比例切分(`-ts 1,3,6e,4e`), 计划拆成独立 PR 逐步上游。

### 3.2 进行中 — PR #26610(协议现代化, 最重要的未来红利)

[PR #26610 "RPC: add -sm tensor"](https://github.com/ggml-org/llama.cpp/pull/26610)(am17an, Open):

**2026-08-29 状态跟踪**(API 查证):
- **基座 [#26490](https://github.com/ggml-org/llama.cpp/pull/26490) 已合并** (2026-08-24, ggerganov) — DSV4 `-sm tensor` + meta backend 进 master, 单机多 GPU tensor split 可用; #26610 基座已随之**重定向到 master** (5 commits, 最新 Aug 19 "address review comments")
- **2026-08-28 ggerganov 留言 "Please rebase on latest master"** — 合并前最后步骤的典型信号, PR 处于终局阶段
- rgerganov 已认可协议 **6.0.0 无向后兼容** ("we don't care about backward compatibility... expect all peers to be running this version", 👍3); review 要求的 mermaid 时序图已补
- Kononnable (08-20) 用 ConnectX-3 10GbE 弱 RDMA 复测 all-reduce, 延迟 1.63µs, 对性能差值存疑但无反对意见
- 遗留阻点: ① DSpark over RPC 兼容 (ggerganov 08-05 提问 "Don't we want to fix the DSpark support first?") ② 多 RPC 后端 hang (ryan5rdx 08-05: "-sm tensor hangs with any topology >1 RPC backend"; Aug 19 commit 后状态未知) ③ rebase 待作者执行
- 关联 [#26724](https://github.com/ggml-org/llama.cpp/pull/26724)(rpc 崩溃不 abort): Open, 无 review 活动, 非合并路径关键项

**四项协议改造, 每一项都对应 #22850 的一个缺陷**:

| 改造 | 对应缺陷 | 机制 |
|:---|:---|:---|
| **async graph_compute** | 同步请求-响应 | 子图异步下发, 客户端不阻塞等远端完成 |
| **graph uid cache(like CUDA)** | 元数据风暴 | 图按 uid 缓存在 server 端, 复用只需 `GRAPH_RECOMPUTE`, 不再重传全部 rpc_tensor |
| **set_tensor_2d / get_tensor_2d** | 小张量冗余 | 2D 切片级传输, 减少小消息数量 |
| **custom all_reduce + fire-and-forget** | 同步+往返开销 | COMM_ALLREDUCE 无响应等待; F32→BF16 cast(ne≥32768)传输量减半 |

- **实测**(2×DGX Spark, RDMA, DeepSeek-V4 284B MXFP4): pp2048 = 619 t/s, tg128 = 19.75 t/s
- **状态**: 作者明确 seeking feedback from ggerganov/rgerganov; CI 全绿; 协议结构大改(新增 comm port、rank 概念、子图切分), 合并周期可能较长
- **行动**: 订阅该 PR, 合并后按 UPGRADE_SOP 两站原子升级 — 这是 decode 速度的最大协议级红利

### 3.3 实验性 / 自研路线

#### A. thunderbolt-ibverbs(hellas.ai, 同硬件!)

[thunderbolt-ibverbs: We have InfiniBand at home](https://blog.hellas.ai/blog/thunderbolt-ibverbs/)(2026-05-28):

- **硬件完全一致**: 2×Strix Halo 128GB mini PC, USB4 直连
- **做法**: Linux 内核模块让 USB4/TB 口注册为 InfiniBand 设备, llama.cpp/vLLM 直接用 libibverbs
- **实测**:
  - ~48 Gb/s 单向(~95 Gb/s 双向, 4-HCA 聚合), vs 板载 2.5GbE ~2.3 Gb/s, vs 软RoCE-on-TBnet ~9 Gb/s
  - ~7µs 单向延迟(64B 单 QP), vs RXE/2.5GbE ~28µs, vs RXE/TBnet ~65µs
  - **MiniMax-M2.7 TP=2 双机推理跑通**(单机放不下, 正是本集群模型)
  - Gemma3 27B LoRA FSDP: Ethernet 1359s → USB4 RDMA 126s(**10.8x**)
- **代价**: 自编译内核模块; 前置的 thunderbolt 稳定性补丁已进 mainline(双向负载下 ring 中断锁死问题已修)
- **判断**: 这是 RPC 瓶颈的"换传输层"终极解, 同硬件已验证, 但维护成本高(跟随内核版本)

#### B. Strix Halo USB4 延迟调优(零成本, 同硬件实测)

[strix-halo-guide issue #13](https://github.com/hogeheer499-commits/strix-halo-guide/issues/13)(源自 [Level1Techs pdrayton 帖](https://forum.level1techs.com/t/benchmarking-usb4-performance-on-strix-halo/245299), 同为 Strix Halo RPC 双机):

| 措施 | 效果 | 成本 |
|:---|:---|:---|
| `pm_qos_resume_latency_us=100`(每逻辑 CPU) | USB4 ping RTT **600-700µs → 134µs**; RPC tg128 带宽受限负载 **+2%**, per-rep stddev 大幅收紧 | 每 CPU 一条 sysfs 写入; 代价: 禁最深 C-state, 每机 idle 功耗 +5-15W |
| yann 的 NHI throttle 补丁(`thunderbolt throttle=64`) | RTT 134 → 103µs; RPC 增益 ~1% | 编译内核模块, 收益/风险比一般 |
| mgeppert 零拷贝 DMA | 78 Gbps + ~1.5µs, 绕过 IP 栈 | 内核驱动项目, 研究性质 |

**pm_qos 是本集群最划算的即时项** — 与 llama.cpp RPC 的 per-op 往返延迟直接相关: RTT 每降 500µs, 每层每 op 都受益。

#### C. 民间 fork(hydra/ddvnguyen, 不建议跟进)

- RPC_CMD_RESOLVE_TENSOR(按名字绑定远端已驻留张量, 零权重传输)、pipelined prefill(prima.cpp PRP 模式, 2-3x 聚合吞吐)
- 工程活跃但属个人 fork 生态, rebase 成本高, 仅作思想参考

### 3.4 替代框架复核

| 框架 | 结论 |
|:---|:---|
| [prima.cpp](https://github.com/OpenCPIL/prima.cpp)(ICLR 2026 poster) | PRP 管道环并行 + Halda 调度, 比 llama.cpp 低 5-17x TPOT — 但核心场景是 **RAM 不足的磁盘 offload 家用集群**。本集群 128GB×2 全内存驻留, 其磁盘预取重叠收益不存在; 换框架还要放弃 Vulkan/MTP/RPC 生态。**不适用** |
| 软 RoCE (rxe) over thunderbolt-net | 免编译(装 rdma-core 即可), 但 hellas.ai 实测仅 ~9 Gb/s / 65µs, 且 VM 环境测试显示软 RoCE 可能比 TCP 更差(带宽 25%、CPU 翻倍)。**收益不确定, 可作为 RDMA transport 的低成本试金石** |
| exo / vLLM / hipEngine | 前次调研已排除(AMD Linux 不可用 / 服务器生态 / 单模型) |

---

## 四、与 A/B 集群的匹配分析

### 4.1 当前链路的实际画像

```
B 站 llama-server (Master, Vulkan)
   │  TCP over thunderbolt-net (USB4 IP, 10.10.10.x)
   │  同步请求-响应 × 每层每 op × 每 token
   ▼
A 站 ggml-rpc-server (Worker, Vulkan)
```

- 传输层: TCP(内核协议栈, 每消息系统调用+上下文切换)
- 协议层: v4.0.1(同步、元数据重传、无压缩)
- USB4 延迟层: 未经调优, RTT 可能高达 600-700µs(C-state 深睡唤醒)

三层都是损耗源, 社区方案恰好分层对应:

| 层 | 损耗 | 社区方案 | 状态 |
|:---|:---|:---|:---|
| USB4 物理/内核 | C-state 唤醒延迟 | pm_qos=100 | **立即可做, 零成本** |
| 传输层 | TCP 协议栈开销 | RDMA transport(已合入) + 软RoCE/TB-ibverbs | 半可用(无硬件 NIC) |
| 协议层 | 同步+元数据+无压缩 | PR #26610 | Open, 跟踪 |

### 4.2 预期收益折算(保守)

以 18.2 t/s 基线, 参考同硬件/同协议量级的实测数据:

| 措施 | 预期 | 依据 |
|:---|:---|:---|
| pm_qos=100 | +2% 左右, 稳定性显著提升, idle 仅 **+1.5W/机**(实测) | 同硬件 RPC tg128 实测(#13 三机对照) |
| MTU 9000(v1.1 新增) | tg 基本持平; 加载/prefill 吞吐↑, CPU 软中断↓ | #12 全 RPC 矩阵即 MTU 9000; #329 列为标配 |
| 软 RoCE(若编入) | -5% ~ +10%, 不确定 | RXE/TBnet 65µs vs TCP 103-134µs; VM 实测可能反效果 |
| rpc-server `-c` 缓存 | 加载 4.4min → 重启后 A 侧秒级(B 侧照常本地读盘) | #25890 作者实测 reload 0 网络 |
| PR #26610 合并升级 | decode 协议税大幅削减, 量级待实测 | async + uid cache + 压缩三管齐下 |
| thunderbolt-ibverbs | **decode 收益个位数(v1.1 下调)**; 加载/prefill/训练显著 | 7µs RTT 消除传输延迟, 但 decode 算力主导(#329/#12 反证) |

---

## 五、行动建议(按 ROI 排序)

| # | 措施 | 成本 | 预期 | 备注 |
|:---|:---|:---|:---|:---|
| 1 | **两站 pm_qos=100 + systemd 持久化** | 零, 可逆(echo 0 还原) | RTT 降 ~5x, RPC +2%, stddev 收紧 | 功耗实测 +1.5W/机; 单元文件见 6.3 |
| 2 | **两站 thunderbolt0 MTU 9000**(v1.1 新增) | 零 | 加载/prefill 吞吐↑, tg 持平 | 两端必须同时设; 验证命令见 6.5 |
| 3 | **A 站 rpc-server `-c` + LLAMA_CACHE** | 一行 + 目录规划 | 重启后 A 侧秒级, 冷启动大幅缩短 | 磁盘 ~70GB(修正); per-model 目录管理见 6.3 |
| 4 | ~~**B 站 `GGML_RPC_LOAD_THREADS=8`**~~ **(v1.2 作废)** | — | PR #26291 未合并, v0.2.0 无此变量, 设置无效 | 等合并升级后再启用; A 站 `-c` 缓存行动项不受影响 |
| 5 | **rpc-server 绑定 10.10.10.1**(v1.1 新增) | 一行 | 收敛无认证协议的暴露面 | 弃 AMD playbook 的 0.0.0.0 写法; 见 6.2C |
| 6 | **ldd 确认 libibverbs 编入状态** | 一条命令 | 决定软 RoCE 是否可试 | 未编入则 B 站装 dev 重编译, **两站同步换**(client 也需) |
| 7 | **试软 RoCE (rxe) over thunderbolt-net** | 10 分钟 | ±5%, 实测说话 | 步骤/风险/回退开关见 6.3; 反效果即弃 |
| 8 | **两站服务 systemd 化 + 顺序依赖**(v1.1 新增) | 一次性 | RPC 崩溃传导兜底(PR #26724 未合并) | Restart 策略见 6.4 |
| 9 | **订阅 PR #26610 / #26490 / #26724** | GitHub watch | 合并后升级 = decode 最大协议红利 | 协议 bump 6.0.0 **无向后兼容**, 强制两站原子升级 |
| 10 | (长期) **评估 thunderbolt-ibverbs** | 内核模块, 维护成本高 | 加载/prefill/训练显著; **decode 收益个位数**(v1.1 下调) | 仅当 1-9 吃完仍不达标时启动 |

**不建议**: 自改协议打 patch(#22850 的 LZ4/异步建议方向正确但 PR #26610 更完整, 等上游); 切 prima.cpp(场景不匹配); 追 hydra fork(维护成本)。

---

## 六、盲区扫描与工程细节补充(v1.1)

> 对前五节方案的系统性盲区扫描: 以同硬件(Strix Halo RPC 双机)社区实测数据交叉验证, 发现 3 处原判断需修正、10+ 处工程细节空白、2 处完全遗漏的风险面。按"修正 → 零成本补遗 → 工程细节 → 风险 → 度量"组织。

### 6.1 原判断修正(三处)

**修正 1: 传输层升级对 decode 的收益预期大幅下调**

- 原判断(v1.0 4.2 表): "thunderbolt-ibverbs 传输层瓶颈基本消除(7µs RTT)" — 暗示 decode 显著受益
- 反证(均为同硬件 Strix Halo RPC 实测):
  - Skulk [#329](https://github.com/Foxlight-Foundation/Skulk/issues/329): "TB is a **load-time lever, not a decode lever** — decode is latency-bound; 42.9 tok/s TB vs 45.4 LAN within noise"(120B 模型, USB4 与普通 LAN decode 在噪声内不可区分)
  - strix-halo-guide [#12](https://github.com/hogeheer499-commits/strix-halo-guide/issues/12)(MTU 9000 mesh + 20Gbps 链路): "The cost is **intrinsic to RPC's per-token sequential layer crossing, not to the link itself** — switching to a faster fabric probably wouldn't change the conclusion much"
  - 摊销数据(#12): 2n RPC 的 tg128 税: 18GB 模型 −20.3%, 86GB 模型 −13.9% — 模型越大 RPC 税占比越低; 230B MoE 的 ~18 t/s 中纯算力主导
- **修正结论**: decode 的杠杆排序 = 模型层(MTP) > 协议层(PR #26610) > 传输层。传输层升级(RDMA/ibverbs)的红利在**加载、prefill、FSDP 训练**(带宽主导场景); hellas.ai 的 10.8x 是 LoRA 训练梯度同步, 不可外推到推理 decode
- 例外说明: PR #26421 RDMA 使 0.6B 小模型 decode +126% — RPC 往返占比极高时传输层才显著; 本集群 230B MoE 不适用

**修正 2: pm_qos 功耗代价高估 3-10 倍**

- 原报告: "idle 功耗 +5-15W/机"(理论最坏估计)
- 实测(#13, 三机对照 + HA 电表 5s 轮询 + 对照机不动): **+1.36~+1.60 W/机**; 相对 pp512 峰值 ~250W / tg128 持续 ~150W, 热预算占比 <1%
- 附带实测: 整机功耗方差同步收紧(对照机 sd 0.62 不变, 调整机 2.47→0.29) — 长期稳定性净收益
- 下限认知: Strix Halo 的 USB4 RTT 物理下限 ~85µs(min)/103µs(avg)(已打 throttle 补丁), 比 Phoenix 7840u(19µs)高 5x — 平台特性, **调优不要追求 <100µs**

**修正 3: "-c 缓存磁盘需 ~130GB" 过度保守**

- 缓存只存本 RPC 节点分到的张量; `-sm layer` 五五切分下 A 站 ≈ **65-70GB**(Q4_K_S 230B 总 ~130GB)加少量 hash 元数据
- 真正的风险不是空间而是**目录管理**: 官方无 per-model 层级, 换模型/换 quant 后旧缓存永不自动清理([#12954](https://github.com/ggml-org/llama.cpp/issues/12954): "cache directory is going to explode to infinity")

### 6.2 零成本调优补遗(v1.0 遗漏的三项)

**A. MTU 9000(jumbo frames)— 同硬件社区 RPC 标配**

- 证据: #12 整个 RPC bench 矩阵即 MTU 9000 跑出("works fine, sub-ms latency, no observed packet loss"); Skulk #329 将 MTU 9000 + sysctl(rmem/wmem, netdev_max_backlog, BBR+fq)列为 "Low-effort, real throughput/CPU wins" 标配
- 操作(两站, 各 10 秒):

```bash
sudo ip link set dev thunderbolt0 mtu 9000 up
ping -M do -s 8972 -c 3 10.10.10.1   # 验证巨帧通路(载荷 8972 = 9000-20-28)
```

- 持久化: netplan 的 thunderbolt0 段加 `mtu: 9000`(两站)
- 风险: **两端必须同时设**, 单端设置 = 大包静默丢包黑洞; MTU 不自动协商
- 预期: 加载与 prefill 期吞吐↑、CPU 软中断↓; decode 收益小(延迟主导, 诚实预期 tg 持平)

**B. GGML_RPC_LOAD_THREADS — PR #26291 未合并, v0.2.0 无此功能 (v1.2 修正)**

- v1.0 误写 "已合入"; 审计核实 (2026-08-28, GitHub API): PR #26291 (作者 chuyqa, 2026-07-29 提交) **仍 Open 未合并** — v0.2.0 (8-21 标签) 不含该功能, B 站设置 `GGML_RPC_LOAD_THREADS=8` 无任何效果
- 该 PR 合并后的价值: 消除客户端单核串行 read+FNV hash+dispatch(#25890 的 69% 单核瓶颈), 与 A 站 `-c` 缓存正交
- 验证: 升级到含 #26291 的构建后, 冷启动加载时间前后对比

**C. rpc-server 绑定面收敛(安全加固)**

- 官方 [README](https://github.com/ggml-org/llama.cpp/blob/master/tools/rpc/README.md) 明确警告: RPC 处于 **"proof-of-concept, fragile and insecure, Never run on an open network"** — 协议**无任何认证**, 连上即可执行任意 ggml 算子、读写张量缓冲
- A 站 rpc-server 若按 AMD playbook 的 `-H 0.0.0.0` 写法, 50052 会同时暴露于家庭 LAN(192.168.1.x) — 本集群 A 站双网卡(192.168.1.11 + 10.10.10.1), 暴露面真实存在
- 加固: rpc-server 绑定 `-H 10.10.10.1`(只听 TB 口); B 站 `--rpc 10.10.10.1:50052` 不变; 或补充 ufw 仅放行 10.10.10.0/30 → 50052

### 6.3 各行动项工程细节与风险

**pm_qos=100**

- **不持久** — 重启即失效, 必须 systemd 化:

```ini
# /etc/systemd/system/pm-qos-usb4.service(两站)
[Unit]
Description=Cap CPU resume latency for USB4 RPC latency
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash -c 'for f in /sys/devices/system/cpu/cpu*/power/pm_qos_resume_latency_us; do echo 100 > "$f"; done'
ExecStop=/bin/bash -c 'for f in /sys/devices/system/cpu/cpu*/power/pm_qos_resume_latency_us; do echo 0 > "$f"; done'
[Install]
WantedBy=multi-user.target
```

- 验证: `cat /sys/devices/system/cpu/cpu0/power/pm_qos_resume_latency_us` = 100; `ping -i 0.2 -c 200 10.10.10.x` 前后对比(期望 avg 600-700µs → ~134µs)
- 风险: 深层 C-state 禁用(实测 +1.5W); 与 amd_pstate 无已知冲突
- **thunderbolt throttle 内核模块补丁不建议**: 收益仅 +1%(77.5 vs 76.8 t/s), 且 modprobe -r/insmod 循环存在 thunderboltN 接口不再注册的脆弱性(#13 实测), 两端必须同时打 — 收益/风险比差

**rpc-server `-c` 本地缓存**

- 启动行: `rpc-server -H 10.10.10.1 -p 50052 -c`
- 缓存路径: 默认 `$HOME/.cache/llama.cpp/rpc`, 用 `LLAMA_CACHE` 环境变量覆盖
- **per-model 目录管理(必做, #12954 实践)**:

```bash
export LLAMA_CACHE=/data/rpccache/MiniMax-M2.7-Q4KS   # 按模型+quant 分目录
mkdir -p "$LLAMA_CACHE"
rpc-server -H 10.10.10.1 -p 50052 -c
```

换模型/清理 = 直接删对应目录; 不做则多模型缓存膨胀不可管理
- 机制: 客户端发张量带 FNV hash, server 比对本地缓存命中则跳过传输 — B 站照常本地读盘, **网络流量归零**; 首次加载因写缓存略慢, 二次启动 A 侧秒级
- 风险:
  1. llama.cpp 升级后若 hash 策略变化 → 缓存静默失效(表现为重启后仍有全量网传) — 每次升级后首次重启用 `nload thunderbolt0` 观察流量
  2. 断电可留半写缓存文件 — 缓存目录放 ext4(勿 F2FS); 损坏表现为加载异常, 删目录重建即可
- 验证: rpc-server 启动日志 `local cache : <路径>`(无 -c 时显示 `n/a`); 二次加载 B 站日志的 load 阶段耗时

**RDMA transport 确认与软 RoCE 试点**

- 二进制确认(不必跑服务): `ldd /opt/llama.cpp/rpc-server | grep -i ibverbs`(或 ggml-rpc-server 实际文件名) — 无输出 = 未编入; B 站构建 v0.2.0 时未装 libibverbs-dev, **大概率未编入**, 以实测为准
- 编入路径: B 站 `sudo apt install libibverbs-dev rdma-core` → 按 UPGRADE_SOP 重编译(fix_runpath_v2.sh 照跑) → **两站同步换二进制**; 注意 client(B 站 llama-server)与 server(A 站 rpc-server)**都需要**带 verbs 的构建, 单边无效
- 软 RoCE 试点(两站, ~10 分钟):

```bash
sudo apt install rdma-core perftest
sudo rdma link add rxe0 type rxe netdev thunderbolt0
rdma link show        # 期望 state active
ibv_devinfo | head    # 确认 rxe0
# 可选摸底: ib_write_lat / ib_write_bw 两站对打
```

- llama.cpp 侧**零改动**: 握手自动协商; **连接必须打在 rxe 挂载的接口 IP 上**(RoCEv2 GID 由 netdev IP 派生) — `--rpc 10.10.10.1:50052` 现值即满足
- 回退开关: 任一端 `GGML_RPC_NO_RDMA=1` 强制回 TCP(A/B 对比测试用); 调试: `GGML_RPC_DEBUG=1`
- 诚实预期: hellas.ai 实测 RXE/TBnet ≈ 9 Gb/s / 65µs — 延迟比调优后 TCP(103-134µs)好约 2x, 但带宽远不及线速; **软 RoCE 走 CPU 拷贝路径, 占核与推理抢核**(VM 实测案例: CPU 翻倍、带宽仅 25%) — 若 tg 反降, 直接弃, 损失为零

**PR #26610 跟踪(协议现代化)**

- 状态复核(2026-08-28): 仍 **Open**, 3 commits, stack 于 PR #26490; rgerganov 要求补协议时序文档(已补 mermaid); review 明示 **"bump the version to 6.0.0, we don't care about backward compatibility"**
- 升级时的硬约束(新增认知):
  1. **协议 6.0.0 无向后兼容** → 两站必须同版本原子升级(SOP 流程语义从"建议"升为"强制"; 单边升级 = 握手直接失败)
  2. 引入 **comm port 新端口**(server 间直连, all_reduce 用) — 防火墙需多放行; A-B 直连拓扑已满足, 无需 mesh
  3. **已知 bug**: `-sm tensor` 在 >1 RPC 后端拓扑下 hang(ryan5rdx Qwen3-0.6B/27B 复现, ds4 连 `-sm layer` 也 break); master 上 `-sm layer` 曾 crash("Remote RPC server crashed") — **合并初期等一个补丁周期, 不抢首班车**
  4. 与 MTP/dspark 组合暂不兼容(跨切分 add 算子未支持)— 届时若已上 MTP 模型需取舍
  5. 本报告头部"RPC 协议 v4.0.1"无法从二进制验证(新版不打印版本号, DEV-LOG-009 发现 4); 以 #26610 review 语境推断当前 master 为 5.x — 协议核对以冒烟测试代替
- 订阅动作: Watch PR #26610 + **#26490**(stack 前置)+ **#26724**(崩溃修复, 见 6.4)

### 6.4 稳定性与故障行为(v1.0 完全空白)

**A. RPC 崩溃传导(最重要的遗漏风险)**

- 现状(master 含 v0.2.0): A 站 rpc-server 崩溃/OOM/被 kill → B 站 llama-server **整个进程 GGML_ABORT**("Remote RPC server crashed or returned malformed response"), 会话全丢, 无重连机制
- 修复 [PR #26724](https://github.com/ggml-org/llama.cpp/pull/26724)(2026-08-07, Open): 改为 endpoint 标记 failed + 后续操作快速失败, 进程存活 — 未合并, 跟踪
- 工程兜底(现在就能做):

```ini
# B 站 /etc/systemd/system/llama-server.service 关键段
[Service]
Restart=on-failure
RestartSec=10
StartLimitIntervalSec=0        # 禁 burst 限制, 允许无限重启
ExecStartPre=/bin/bash -c 'for i in $(seq 60); do timeout 1 bash -c "echo > /dev/tcp/10.10.10.1/50052" 2>/dev/null && exit 0; sleep 5; done; exit 1'
# A 站起不来时 B 站等待最长 5 分钟再放弃, 避免白加载
```

- A 站 rpc-server 同样 systemd 化, `Restart=always`(需 render/video 组权限)
- 认知: B 站重启 = 重新加载(-c 后 A 侧秒级, B 侧本地照常), RTO 分钟级而非热恢复

**B. USB4 链路层断链**

- 拔线/端口复位 → thunderbolt0 down → TCP RST → 同上 abort 路径
- **线缆与协商速率检查**: 社区实测存在链路协商在 **20Gbps** 的情况(#12: "negotiated 20 Gbps") — 用 `ethtool thunderbolt0 | grep Speed` 确认本集群实际值; 若非 40000Mb/s, 换 40Gbps 认证线(≤0.8m 雷电线)或换口
- **双 USB4 口陷阱**(Skulk #329 踩坑, 每站两口都适用): 若第二口也配 IP, link-local 路由全从最低 metric 口出 → "ICMP 通而 TCP 死"的非对称路由陷阱; 本集群单口单链路是正确拓扑, **第二口保持不配 IP**

**C. Vulkan/RADV 特有风险(同模型警示)**

- #12 实测: **MiniMax-M2.7 在 RADV 上存在单张量 ~792MB 分配墙**(wide-MoE 结构): `radv/amdgpu: Failed to allocate a buffer: 830472192 bytes` → leader 端报 "Remote RPC server crashed"; **ROCm allocator 可过**
- 本集群 Q4_K_S + RADV 25.2.8 + TTM 117GB 配置未触发 — 但属潜伏雷, 触发条件: 升级 Mesa、换 Q8 量化、GTT 策略变化
- 兜底: ROCm 7.2 后端(#12 社区 MiniMax 生产配置: 2n pp512 238.6 / tg128 21.4, 与本集群 Vulkan 20.15 同量级) — 仅作应急路线, 意味着放弃 Vulkan 生态更新

### 6.5 度量与验证方法学(数据回填用)

| 目标 | 命令 | 判读 |
|:---|:---|:---|
| 链路协商速率 | `ethtool thunderbolt0` | 应 40000Mb/s; 20000 = 换线/换口 |
| 链路错误/丢包 | `ip -s link show thunderbolt0` | errors/dropped 零增长 |
| 延迟基线/调优效果 | `ping -i 0.2 -c 200 10.10.10.1` | avg+mdev; pm_qos 前后(期望 600-700→134µs) |
| 巨帧生效 | `ping -M do -s 8972 -c 3 10.10.10.1` | 通 = 两端 MTU 9000 生效 |
| 带宽基线 | `iperf3 -c 10.10.10.1 -t 10 -P 4`(对端 `-s`) | TB 有效吞吐; `-P 4` 避开单流窗口限制 |
| RDMA 摸底 | `ib_write_lat` / `ib_write_bw` | rxe 试点前后对比 |
| RPC 网络流量 | A 站 `nload thunderbolt0` | -c 验证: 二次启动应接近 0 |
| 稳定性 | llama-bench `-r 20` 看 per-rep stddev | 社区惯例; pm_qos 后 stddev 大幅收紧 |
| pm_qos 生效 | `cat /sys/devices/system/cpu/cpu0/power/pm_qos_resume_latency_us` | =100 |

---

## 七、参考来源

| 主题 | 来源 |
|:---|:---|
| RPC 协议缺陷剖析 | [issue #22850](https://github.com/ggml-org/llama.cpp/issues/22850) |
| 加载单核瓶颈 + 3x 修复 | [issue #25890](https://github.com/ggml-org/llama.cpp/issues/25890) / [PR #26291](https://github.com/ggml-org/llama.cpp/pull/26291) |
| RPC 协议现代化(核心) | [PR #26610 "RPC: add -sm tensor"](https://github.com/ggml-org/llama.cpp/pull/26610) |
| RDMA transport 官方文档 | [tools/rpc/README.md](https://github.com/ggml-org/llama.cpp/blob/master/tools/rpc/README.md) |
| Apple RDMA 合并 + 实测 | [PR #26421](https://github.com/ggml-org/llama.cpp/pull/26421)(ggerganov 2026-08-27 合并) |
| 同硬件 USB4 RDMA | [thunderbolt-ibverbs (hellas.ai)](https://blog.hellas.ai/blog/thunderbolt-ibverbs/) |
| Strix Halo USB4 调优 | [strix-halo-guide #13](https://github.com/hogeheer499-commits/strix-halo-guide/issues/13) / [Level1Techs 帖](https://forum.level1techs.com/t/benchmarking-usb4-performance-on-strix-halo/245299) |
| RPC 10GbE 实测(延迟主导证据) | [kjaiswal/llama-cpp-distributed-benchmarks](https://github.com/kjaiswal/llama-cpp-distributed-benchmarks) |
| MoE 专家 RPC 切分 | [discussion #27393](https://github.com/ggml-org/llama.cpp/discussions/27393) |
| RPC 日志时间戳(transport 行样例) | [PR #27669](https://github.com/ggml-org/llama.cpp/pull/27669) |
| DGX Spark RDMA 集群参考 | [RustRunner/DGX-Llama-Cluster](https://github.com/RustRunner/DGX-Llama-Cluster) |
| 软 RoCE 性能陷阱 | [CSDN Soft-RoCE vs TCP 实测](https://blog.csdn.net/assembly8low/article/details/153145476) |
| **同硬件 RPC 全矩阵(1n/2n/3n, 含 MiniMax-M2.7)** | [strix-halo-guide #12](https://github.com/hogeheer499-commits/strix-halo-guide/issues/12) |
| **pm_qos 功耗/延迟实测 + USB4 调优阶梯** | [strix-halo-guide #13](https://github.com/hogeheer499-commits/strix-halo-guide/issues/13) |
| **RPC 崩溃传导修复(Open)** | [PR #26724](https://github.com/ggml-org/llama.cpp/pull/26724) |
| **同硬件 TB 调优(MTU/BBR/路由陷阱)** | [Skulk #329](https://github.com/Foxlight-Foundation/Skulk/issues/329) |
| **RPC 官方 README(缓存/RDMA/调试环境变量/安全警告)** | [tools/rpc/README.md](https://github.com/ggml-org/llama.cpp/blob/master/tools/rpc/README.md) |
| **-c 缓存目录管理实践** | [issue #12954](https://github.com/ggml-org/llama.cpp/issues/12954) |

---

**报告版本**: v1.1(2026-08-28 盲区扫描增补, v1.0 主体框架不变; 修正记录见 6.1)
**下一步**: 执行行动项 1-5(pm_qos / MTU 9000 / -c 缓存 / 加载线程 / 绑定面), 全部零风险零重启; 6-7 半天内完成; 数据按 6.5 度量方法回填
