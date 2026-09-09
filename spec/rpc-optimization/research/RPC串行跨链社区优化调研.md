# RPC 串行跨链问题的社区优化调研

> **日期**: 2026-08-28
> **作者**: Scott (鹏)
> **适用系统**: B 站 llama-server(client + 本地 Vulkan) + A 站 ggml-rpc-server(10.10.10.1:50052), USB4 thunderbolt-net TCP, llama.cpp v0.2.0 (协议 v5.1.0)
> **调研问题**: RPC 串行跨链(每 token 沿层边界在两机间串行往返、同步请求-响应锁死流水线)在开源社区有哪些优化方案, 各自状态与对本集群的适用性
> **定位**: 本文是《RPC协议瓶颈调研.md》(v1.2) §3.2 PR #26610 的深挖扩展, 并补充其未覆盖的传输层实测证据(#26421 大模型数据)、图缓存时间线、CVE 安全注记、研究原型(prima.cpp)与 fork 方案
> **关联文档**: 《RPC协议瓶颈调研.md》(母报告)、《AMD平台算子层优化与USB4分布式调研.md》(算子层)、《spec/operator-optimization/DESIGN.md》(双路径方案)、《spec/rpc-optimization/metrics-log.md》(基线)

---

## 一、执行摘要

1. **串行跨链有实测量化**: M3 Ultra 双节点跑 DeepSeek-V4-Flash, 单节点 tg 27.6 t/s → 双节点 TCP RPC 14.7 t/s, **损失 47%**; 这就是"两台 395 加起来不如一台跑满"的协议层机理 [4]。本集群 tg128 20.15(双机 Q4_K_S) vs 单机 Q3 ~32.8, 同构现象。
2. **社区优化分四层, 状态各异**:
   - **传输层 RDMA transport — 已合入 master**(Linux RoCEv2 先行, Apple TB5 #26421 于 2026-08 下旬合入), 自动协商零命令行改动;
   - **协议层 async + all_reduce — Open PR #26610**, 串行跨链的正解, 依赖 RDMA peer 直连, 协议 v6.0.0 无向后兼容;
   - **图缓存(GRAPH_RECOMPUTE) — v0.2.0 已有**(协议 v5.1.0), 已消除"元数据风暴"的图拓扑重发部分;
   - **研究原型 prima.cpp(ICLR 2026)** — 环形窗口并行, 场景错配, 仅思想参考。
3. **修正母报告 v1.2 的一个判断**: v1.2 认为"RDMA transport 对 decode 仅在小模型显著(0.6B +126%)"; #26421 新披露的 **DeepSeek-V4-Flash 双节点数据(TCP 14.7 → RDMA 22.37 t/s, +52%)** 表明: 只要串行跨链损失深(2 节点丢 47%), 硬件 RDMA 对大 MoE 的 decode 恢复同样显著。前提是**硬件 RDMA** — 我们 USB4 上只有软 rxe(收益不确定)。
4. **PR #26610 的关键拓扑教训(对本集群直接相关)**: Metal 上 `-sm tensor` tg2048 9.61 vs `-sm layer` 23.05 — **慢 2.4 倍**, 因为 client 与本地后端直连时 all-reduce 走"local<>RPC"中转路径。正确拓扑是 **llama-server 纯 client + 两站各跑 rpc-server**。当前 B 站"client+计算"拓扑正是那个反例结构。
5. **PR #26610 现状 = 等待 + 有硬缺陷**: 基座 #26490 尚 Open(需 2 个 approving review, WebGPU CI 失败, DSpark draft 无法加载); #26610 自身存在多 RPC 后端 hang(Qwen3-27B/0.6B 实测)、DSpark 不兼容、协议 6.0.0 无向后兼容(rgerganov 明确 "we don't care about backward compatibility")。
6. **本集群零成本可做两件事**: ① Kononnable 式 `-ot` 专家张量手动放置试验(TCP 下 `-sm layer` 的社区调优技巧, MiniMax-M2.7 是 MoE 直接适用); ② `GGML_RPC_DEBUG=1` 采证每 token 的 set/get 张量风暴规模, 为将来协议升级建立 before/after 基线。
7. **安全注记**: 图缓存特性(GRAPH_RECOMPUTE)存在历史 CVE-2026-39909(UAF, 影响 < b8585)。v0.2.0(2026-08 标签)远晚于 b8585, 不受影响; 且我们 rpc-server 已收敛绑定 10.10.10.1 点对点面。升级含图缓存的新版本时无需额外动作, 但提醒: **协议升级≠安全豁免, 每次 SOP 升级照常核对**。

**结论**: 串行跨链的社区解法主线清晰 — 传输层(RDMA, 已合入) + 协议层(async/all_reduce/uid cache, #26610 等合并) + 图缓存(已享受)。本集群当前无需新动作, 保持 v0.2.0 + 双路径策略; 新增两项零成本试验可选执行; #26490/#26610 合并是下一个升级触发器, 届时需同时做**拓扑改造**(纯 client + 双 rpc-server)才能吃到 all-reduce 红利。

---

## 二、串行跨链: 机制与证据

### 2.1 机制

`-sm layer`(层切分, RPC 默认)下一个 token 的执行路径:

```
B站: layer 0..k 计算 ──同步RPC──▶ A站: layer k+1..n 计算 ──同步RPC──▶ B站: 输出头
              ▲                                          │
              └──────────── 每层边界一次完整 RTT ──────────┘
```

三重税:
1. **同步请求-响应**: 客户端发出 `SET_TENSOR`(输入激活) → `GRAPH_COMPUTE` → 等待 → `GET_TENSOR`(输出), 每步都阻塞等待网络往返, GPU 与网络严格串行, 无法重叠 [5]。
2. **层边界激活传输**: 层切分使每个 token 在层边界传输激活张量, RTT × 边界数线性累积。
3. **小张量冗余**: KV 写入、embedding 等每 token 4B~20KB 级小包, 带宽利用率极低("tens of MB/s while link idles") [5]。

### 2.2 社区实测证据

**证据 1 — 每 token RPC 事务序列**(issue #22235, GGML_RPC_DEBUG 日志, 2026-04, build 8870)[6]:

```
[set_tensor] size: 20480      ← embedding/输入
[set_tensor] size: 4          ← 标量
[set_tensor] size: 16
[set_tensor] size: 8
[set_tensor] size: 8192       ← KV
[set_tensor] size: 1024
[graph_recompute] device: 0   ← 图缓存命中, 只发 uid 重算
[get_tensor] ...              ← 取回输出
```
每个 token 一轮, 全同步。**注意**: `graph_recompute` 出现说明图缓存(§3.2)在 2026-04 就已在主线工作, 每个图的拓扑不再重发 — "元数据风暴"已被图缓存解决了图拓扑部分, 剩余的是**小张量 set/get 往返本身**。

**证据 2 — 串行跨链的量化损失**(PR #26421 评论区, ryan5rdx, M3 Ultra ×2, DeepSeek-V4-Flash-0731 GGUF)[4]:

| 拓扑 | pp t/s | tg t/s | 判读 |
|---|---|---|---|
| 1 节点(单机) | 408.93 | **27.6** | 基线 |
| 2 节点 TCP RPC | 275.1 | **14.7** | decode **-47%** — 串行跨链税 |
| 2 节点 RDMA RPC | 290.0 | **22.37** | 恢复到单机的 81% — 传输层削税 |

同报告: Qwen3.6-27B 2 节点 TCP tg 18.0 → RDMA 22.5(+25%); 4 节点 17.7 → 19.8(+12%)。Qwen3-0.6B 2 节点 decode +126%(RPC 占比极高的小模型极端情形)。

**证据 3 — 本集群**: 双机 RPC Q4_K_S tg128 20.15 vs 单机 Q3 ~32.8(不同量化, 量级参考)。与 visorcraft"两台 395 decode 加起来不如一台"结论一致(见算子层调研 §一.3)。

---

## 三、社区优化方案分层

### 3.1 传输层: RDMA transport(已合入 master)

**状态**: Linux RoCEv2(libibverbs)路径先行合入 master; Apple TB5 路径 [PR #26421](https://github.com/ggml-org/llama.cpp/pull/26421)(ryan5rdx, +621-38, 8 文件)由 ggerganov 于 2026-08 下旬合入(本日页面快照显示 "yesterday"; 母报告 v1.2 审计记 8-25)。握手自动协商, 失败回退 TCP, 命令行零改动。

**机制**: 传输层把每次往返的固定延迟从 TCP 协议栈(本链路实测 RTT ~100µs, Phase 1 调优后)压到 RDMA 级(Apple TB5 官方口径微秒级; hellas.ai thunderbolt-ibverbs ~7µs)。串行跨链的"RTT × 层数"税被逐次削减。

**对串行跨链的作用** — #26421 内含两个微优化直接对症 [4]:
- `RPC_CMD_SET_TENSOR` 不再 flush → **小张量合并(coalescing)**, 对症 §2.1 税 3;
- `ggml_backend_rpc_synchronize` 强制 flush — 保证正确性边界。
作者自评"性能提升不大但无害且正确", 说明合并收益有限, 主要收益来自 RDMA 传输本身。

**本集群适用性**: 无硬件 RoCE NIC, 两条替代路径(软 rxe / thunderbolt-ibverbs)见母报告 §六与本文 §四。**注意**: Apple 实现不能直接照搬, Linux RDMA 路径要求构建时装 libibverbs(母报告行动项 6: `ldd` 确认, 未执行)。

### 3.2 图缓存: GRAPH_RECOMPUTE(v0.2.0 已享受)

**状态**: 已在主线 ≥2026-04(issue #22235 日志为证), 本地 v0.2.0 验证为协议 v5.1.0, 含 `graph_recompute`/`set_tensor_hash` 命令(见 DEV-LOG)。

**机制**: 客户端首次提交完整图拓扑, 服务端 stored_graph 缓存; 复用时只发图 uid 触发重算。**这已实现 #22850 建议的 "metadata registry" 一半** — 图拓扑不再每 token 重发。未解决部分: 输入张量 set/get 的同步往返(→ §3.3 的 async)与小张量哈希跳传(#22850 建议的 universal hashing, 至今无人实现)。

**衍生社区工作**: [PR #25406](https://github.com/ggml-org/llama.cpp/pull/25406)(Foxlight-Foundation, 2026-07-07, 已关闭未合入)尝试在 backend sched 层保持 split-graph uid 跨提交稳定以提高 RPC 端缓存命中率 — 方向与 #26610 的 "graph uid cache like CUDA" 重合, 由后者以另一种实现承接。

**安全注记**: CVE-2026-39909(CVSS v4 9.2, 2026-08-21 公开): b8585 之前的 GRAPH_RECOMPUTE 处理器存在 use-after-free(存图→释放缓冲→重算悬垂指针→远程任意读写, 无认证) [7]。v0.2.0(2026-08 标签, 主线构建号 ~b10300+ 时代)远晚于 b8585(≤2026-05), **不受影响**; 且 Phase 2 已将 rpc-server 收敛绑定 10.10.10.1 点对点面, 无公网暴露。此 CVE 从反面确认: 图缓存是真实在生产中被使用的特性, 也是攻击面 — 协议无认证的设计使**网络面收敛**是唯一现实防线(已做, 保持)。

### 3.3 协议层: PR #26610 async + all_reduce(串行跨链正解, Open)

[PR #26610 "RPC: add -sm tensor"](https://github.com/ggml-org/llama.cpp/pull/26610)(am17an, 2026-08-05, Open, 44 条讨论, 8 参与者, 基座为 [#26490](https://github.com/ggml-org/llama.cpp/pull/26490))。

**四项机制** [1]:
1. **async graph_compute** — 图命令发出即返回, 双端异步计算, 客户端不再阻塞等单端完成(对症 §2.1 税 1);
2. **custom all_reduce** — `COMM_ALLREDUCE` fire-and-forget, **RPC server 之间通过新增 comm port 直接对传 partial 张量**(rank0 先发, rank1 先收, 各自 async ADD), 归约流量不再经过 client 中转(对症税 2);
3. **graph uid cache like CUDA** — 双端图缓存, 复用只发 uid(`GRAPH_COMPUTE (uid) [GRAPH_RECOMPUTE on reuse]`);
4. **set_tensor_2d / get_tensor_2d** — 2D 传输 + `ne ≥ 32768` 时 F32→BF16 压缩, 削传输量。

**实测**(2×DGX Spark, RDMA, DeepSeek-V4 284B MXFP4 MoE, 145.63GiB)[1]:

| 切分 | pp2048 | tg128 |
|---|---|---|
| `-sm tensor`(#26610) | **619.36 ± 15.42** | **19.75 ± 0.39** |
| `-sm layer`(master, 近期数据) | ~400(作者口述, 当前版本会 crash) | ~15(同) |

张量切分对层切分: pp +55%, tg +32%。

**拓扑教训(重要)**[2][3]:
- ryan5rdx 在 2×M3 Ultra(RDMA, #26421)实测 DS4 MXFP4: `-sm layer` tg2048 **23.05** vs `-sm tensor` **9.61** — 张量切分反而慢 2.4 倍;
- am17an 诊断: 该测试 client 与本地 Metal 后端直连, all-reduce 走了 **"Metal<>RPC"中转路径**; 正确做法是 **两站各跑 rpc-server, llama-server 作纯 client**(`--rpc ip1,ip2 --device RPC0,RPC1`), 激活 **RPC<>RPC** all-reduce 直连;
- **映射到本集群**: 当前 B 站是 "client+本地计算" 拓扑 — 恰是那个慢 2.4 倍的结构。将来吃 #26610 红利的前提是拓扑改造: B 站改跑 ggml-rpc-server(本地 Vulkan), llama-server 独立成纯 client。

**已知缺陷(合并前硬伤)**[2][3]:
- `-sm tensor` 在 >1 个 RPC 后端拓扑下 **hang**(Qwen3-27B/0.6B/DS4 均复现, 无报错静默挂起);
- **DSpark 不兼容**: TP 切分下 "add across the split" 算子不支持(ryan5rdx); 基座 #26490 上 DSpark draft 模型直接加载失败(iSevenDays, master 正常);
- **协议 v6.0.0 无向后兼容**(rgerganov: "we don't care about backward compatibility... just bump the version to 6.0.0 and expect all peers to be running this version") — 合并即强制**两站原子升级**(UPGRADE_SOP 照跑);
- master 的 `-sm layer` 2-RPC 后端本身近期不稳定(crash 报告) — 社区正在烧入期。

**基座 #26490 状态**: DeepSeek4 `-sm tensor`(4×4090: PP +50%, TG 无增益), Open, 需 2 个 approving review, WebGPU CI 失败待处理 [8]。**链路: #26490(模型层张量切分) → #26610(RPC 协议支撑), 两者都合并后才有完整功能。**

### 3.4 研究原型: prima.cpp(ICLR 2026)

[prima.cpp](https://github.com/OpenCPIL/prima.cpp)(arXiv:2504.08791v3, ICLR 2026 会议论文, 代码 2026-06-30 导入)[9]:

- **Piped-Ring Parallelism (PRP)**: 设备连成**环**, 模型按"层窗口"(layer window)切成 N 段环形分配, **每 token 允许多轮环行**(如 6 设备各 3 轮), 用细粒度窗口重叠通信与计算/磁盘 IO;
- **Halda 调度器**: 异构感知(CPU/GPU 算力、磁盘、内存回收、OS)求解层分配与设备选择(NP-hard);
- 成绩: 4 台消费级设备 70B 达 674 ms/token(内存压力 <6%), 32B+投机解码 26 t/s; 对比 llama.cpp/exo/dllama **TPOT 低 5-17×**。

**判读**: 5-17× 的对比基线是**磁盘 offload + WiFi** 场景(其设计目标: 内存不足、慢盘、WiFi) — 与本集群"全模型驻 RAM + USB4 9Gb/s"完全错配, 数字不可外推。其**环形窗口**思想(把长串行链切成多轮小窗口、重叠通信与计算)是串行跨链问题的学术解法参考, 但它是独立代码库(fork 自 llama.cpp 早期版本, 8 commits), 无主线合入路径。**维持母报告 v1.2 结论: 不切换, 仅思想参考。**

### 3.5 未采纳提案与 fork 方案

**Issue #22850(2026-05, 已关闭)**[5]: 提出三建议 — 落地状态对照:

| #22850 建议 | 状态 |
|---|---|
| 元数据注册(只传 tensor id) | **图拓扑部分已由图缓存实现**(§3.2); 剩余小张量部分未做 |
| universal hashing(小张量也跳传) | 未实现, 无 PR 承接 |
| 异步流水线(计算与网络重叠) | **#26610 的 async graph_compute 实现**(§3.3) |

该 issue 因违反仓库 AI 使用政策(报告由 LLM 代写)被关闭, 但技术分析被 #26610 逐条间接验证 — "问题真实, 提案正确, 落地在上游"。

**Kononnable 的 `-ot` 手动放置技巧**(#26610 评论区)[3]: TCP/IP 下不使用标准 `-sm layer`, 手动把 MoE 专家张量路由到 RPC:

```
-sm layer -ts 0,1 -ot 'blk\.[0-1][0-9]?\.ffn_(up|down|gate|gate_up)_(ch|)exps=RPC0[127.0.0.1:50052]'
```
"有时能提升 TCP 下的性能"(单条目击报告, 非合入特性)。**对本集群: MiniMax-M2.7 是 MoE, 模式直接适用** — 详见 §四 A1。

**hydra_vortex fork**(ddvnguyen)[10]: 应用层 P/D 切分 + pipelined prefill(新增 PREFILL_BEGIN/CHUNK/RESUME/ABORT opcodes, 请求级流水线, 目标并发 2 时聚合 2-3×)。其 issue #21 记录了 RPC 共享后端并发下的 52s 静默停摆 + 崩溃传导(compute-lock 序列化疑点) — 又一份"RPC 串行化在真实负载下咬人"的证据。独立 fork, 维护成本高, **维持母报告"不追"结论**。

---

## 四、本集群适用性与行动建议

### 4.1 适用性矩阵

| 方案 | 状态 | 前置条件 | 本集群判定 |
|---|---|---|---|
| 图缓存(v5.1.0) | **v0.2.0 已享受** | — | 已在跑, 零动作 |
| RDMA transport(传输层) | master 已合入(v0.2.0 之后) | 构建+libibverbs; 硬件 RDMA 才有全额收益 | 无硬件 NIC; 软 rxe 试金石待做(母报告行动项 6/7); DS4-Flash +52% 证据将期待值上调 |
| #26610 async+all_reduce | Open(基座 #26490 也 Open) | 协议 6.0.0 两站原子升级 + **RDMA peer 直连** + 拓扑改造(纯 client+双 rpc-server) | **跟踪, 合并即触发升级 SOP**; hang bug 烧入期, 不抢跑 |
| `-ot` 专家张量手动放置 | 社区技巧, 非特性 | 无 | **零成本可试**(A1) |
| prima.cpp | 研究原型 | 切换代码库 | 不做 |
| hydra fork | 独立 fork | 切换维护链 | 不做 |
| 自打协议 patch(LZ4 等) | — | — | 不做(母报告已裁) |

### 4.2 行动项

| # | 行动 | 成本 | 预期 | 备注 |
|---|---|---|---|---|
| A1 | **`-ot` MoE 专家张量放置试验** ✅ **2026-08-28 已执行** | 每配置一次 bench, 零风险 | ±10% 量级, 实测说话 | **结果: 全部劣化, 不采纳** (C1 专家→A -5.3% / C2 专家→B -33.7% / C3 attn→B -64.2% vs 基线 tg 20.02)。默认层切分即 TCP 最优; C3 成为串行跨链机理的活体证明。设备名语法坑: 必须 `RPC0[10.10.10.1:50052]`, 裸 `RPC0`/`RPC` 被拒。数据见 metrics-log.md 附加试验 A1 |
| A2 | **`GGML_RPC_DEBUG=1` 采证** ✅ **2026-08-28 已执行** | 一次重启, 零风险 | 建立"小张量风暴"规模基线 | **结果: 每 token ~38.7 次 RPC 命令 / 903KB** (graph 8.93 + set 12.89/793KB + get 16.87/110KB); 带宽占用仅 0.02% — 串行跨链 = 纯延迟/命令数问题实锤; `-sm layer` 实际切分 ≈ 9 子图/token (非 1); RTT 税 ≈ 7.6%/token (下限)。#26610 升级后 before/after 锚点已建。数据见 metrics-log.md 附加试验 A2 |
| A3 | **跟踪 #26490 + #26610**(GitHub watch) | 零 | 合并 = 下一个升级触发器 | 升级时三件事联动: 两站原子 SOP / 协议 6.0.0 校验 / **拓扑改造**(B 站加跑 rpc-server, llama-server 转纯 client `--rpc 10.10.10.1,10.10.10.2 --device RPC0,RPC1`) |
| A4 | (承接母报告 6/7, 条件触发) `ldd` 确认 ibverbs 编入 + 软 rxe 试点 | 10 分钟级 | ±5%, DS4 证据后值得重估 | 若软 rxe 触发 transport 协商成功, 先拿传输层部分收益 |

> **A1/A2 执行后的认知修正** (2026-08-28): ① §3.5 Kononnable `-ot` 技巧判定从"零成本可试"降级为"**负迁移, 不适用本集群**" — 其收益前提 (master 版多 RPC 后端拓扑) 与 v0.2.0 单 RPC 端不同; ② A2 实测命令粒度 (4B/8B/32B 标量碎包 + 8×96KB/token) 使 #26610 四机制中 **set_tensor_2d/BF16 压缩与 async graph_compute 的预期收益同时上调** — 前者直接减半 96KB set 主体, 后者合并 9 子图串行等待。

### 4.3 对母报告 v1.2 的修正声明

- **v1.2**: "PR #26421 RDMA 使 0.6B 小模型 decode +126% — RPC 往返占比极高时传输层才显著; 本集群 230B MoE 不适用"。
- **修正**: #26421 后续披露的 **DeepSeek-V4-Flash 双节点 TCP 14.7 → RDMA 22.37(+52%)** 表明, 只要串行跨链损失足够深(双节点 -47%), 硬件 RDMA 对大 MoE decode 同样有恢复性收益。
- **保留的限定**: 该 +52% 来自 **Apple TB5 硬件 RDMA**(微秒级 RTT); 本集群 USB4 上唯一软路径 rxe 实测 ~9Gb/s / 65µs(hellas.ai), 延迟削减幅度远小于硬件 RDMA, 收益不可直接外推 — 软 rxe 仍是"试金石"定位, 不是"预期收益"。
- **杠杆排序不变**: decode 收益 模型层(MTP/DSpark) > 协议层(#26610) > 传输层; 但传输层从"基本无效"上调为"串行损失恢复型有效(硬件 RDMA 前提下)"。

---

## 五、参考来源

1. [PR #26610 "RPC: add -sm tensor"](https://github.com/ggml-org/llama.cpp/pull/26610)(am17an, 2026-08-05 开启, Open) — 四机制、时序图、Spark RDMA 实测(pp2048 619.36 / tg128 19.75)、rgerganov 评审(协议 6.0.0、文档化要求)
2. [PR #26610 评论区 ryan5rdx](https://github.com/ggml-org/llama.cpp/pull/26610#issuecomment-5188516731)(2026-08-05) — Metal RDMA 实测: `-sm tensor` tg2048 9.61 vs `-sm layer` 23.05; 多 RPC 后端 hang; DSpark/TP 不兼容
3. [PR #26610 评论区 am17an/Kononnable](https://github.com/ggml-org/llama.cpp/pull/26610)(2026-08-05) — RPC<>RPC all-reduce 拓扑说明(`--rpc ip1,ip2 --device RPC0,RPC1`)、master `-sm layer` crash 与 ~400pp/~15tg 口述、`-ot` 专家张量放置技巧
4. [PR #26421 "rpc: support apple RDMA as an RPC transport"](https://github.com/ggml-org/llama.cpp/pull/26421)(ryan5rdx, ggerganov 合并入 master, 2026-08 下旬) — Merged, +621-38; Qwen3-0.6B / Qwen3.6-27B / DeepSeek-V4-Flash 三组 TCP vs RDMA 实测; SET_TENSOR coalescing 微优化; GGML_RDMA_DEV
5. [Issue #22850 "Essential RPC performance degradation"](https://github.com/ggml-org/llama.cpp/issues/22850)(karambaso, 2026-05-09, Closed-AI政策) — 元数据风暴/HASH_THRESHOLD 10MB/同步阻塞三缺陷分析与三建议
6. [Issue #22235 "Qwen 3.5 over RPC+Vulkan generates gibberish"](https://github.com/ggml-org/llama.cpp/issues/22235)(anakayub, 2026-04-22) — GGML_RPC_DEBUG 每 token set/get/graph_recompute 事务日志(图缓存 2026-04 已在主线的证据)
7. [CVE-2026-39909](https://app.opencve.io/cve/CVE-2026-39909)(2026-08-21 公开) — GRAPH_RECOMPUTE 处理器 UAF, 影响 < b8585, CVSS v4 9.2
8. [PR #26490 "Deepseek 4: -sm tensor"](https://github.com/ggml-org/llama.cpp/pull/26490)(am17an, 2026-08-03, Open) — 基座 PR; 4×4090 PP +50%; WebGPU CI 失败; DSpark draft 加载失败报告
9. [prima.cpp](https://github.com/OpenCPIL/prima.cpp) / [arXiv:2504.08791v3](https://arxiv.org/pdf/2504.08791.pdf)(ICLR 2026) — Piped-Ring Parallelism、Halda、70B 674ms/token、TPOT 5-17×(磁盘 offload 基线)
10. [hydra_vortex issue #269 / llama.cpp fork issue #21](https://github.com/ddvnguyen/hydra_vortex/issues/269)(ddvnguyen, 2026-06) — 应用层 pipelined prefill opcodes; RPC 并发 compute-lock 52s 停摆案例

> **本地验证锚点**(非网络来源): v0.2.0 协议 v5.1.0、graph_recompute/set_tensor_hash 存在、transport 无 RDMA — 见 DEV-LOG 与《三调研报告审计.md》; 本集群基线见 metrics-log.md。

---

*v1.0 (2026-08-28): 初版。引用均为当日 GitHub 页面快照逐字核对; #26421 合并日期以页面 "yesterday"(≈8-27)为准, 母报告 v1.2 记 8-25, 差异不影响结论(均为 v0.2.0 标签之后)。*
