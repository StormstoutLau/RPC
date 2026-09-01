# 设计文档：RPC 双机链路分层优化

---

id: rpc-optimization-DESIGN
type: design
version: 1.0
status: draft
date: 2026-08-28
depends: [d:\RPC\RPC协议瓶颈调研.md (v1.2), DEV-LOG-009-v020-upgrade.md]
upstream: null

---

> **Feature**: 基于《RPC协议瓶颈调研.md》结论，对 A/B 双机 USB4 RPC 链路执行分层优化
> **创建日期**: 2026-08-28
> **状态**: 草稿（待 review）
> **Spec 步骤**: Step 3-4
> **基于调研**: [RPC协议瓶颈调研.md](../../docs/RPC协议瓶颈调研.md)（下文简称"调研"）

---

## 1. 设计目标

在不更换 llama.cpp 二进制、不动内核主线的前提下，分五阶段收割调研确认的 RPC 优化项：

1. **性能**: tg128 在 20.15 t/s 基线上获得链路层收益（诚实预期 **+2% 级**，非大数字——decode 大头在协议层，见调研 §6.1 修正 1）
2. **加载**: 冷启动 4.4 min 级 → 二次启动 A 侧秒级（`-c` 缓存）
3. **稳定性**: 消除"A 站 rpc-server 崩溃 → B 站 llama-server 整进程 GGML_ABORT"的单点传导（systemd 兜底，调研 §6.4A）
4. **可归因**: 每阶段前后跑同一 bench 命令，数据回填，反效果即回退

**非目标**: decode 数量级提升（属 PR #26610 协议层红利，本方案只做跟踪）；训练场景优化。

## 2. 设计依据

### 2.1 调研结论 → 设计决策映射

| 调研发现 | 设计决策 | 引用 |
|---------|---------|------|
| pm_qos=100: RTT 600-700µs→134µs, tg +2%, 功耗实测仅 +1.5W/机 | Phase 1 第一项 | 调研 §6.1 修正 2 / §6.3 |
| MTU 9000: 同硬件社区 RPC 标配，加载/prefill 吞吐↑，tg 持平 | Phase 1 第二项 | 调研 §6.2A |
| `-c` 缓存: 二次启动 A 侧网络流量归零；磁盘 ~70GB；必须 per-model 目录 | Phase 2 | 调研 §6.3 / #12954 |
| rpc-server 协议无认证，`-H 0.0.0.0` 会暴露于家庭 LAN | Phase 2 绑定 10.10.10.1 | 调研 §6.2C |
| RPC 崩溃传导无重连，PR #26724 未合并 | Phase 3 systemd Restart 兜底 | 调研 §6.4A |
| 软 RoCE (rxe) 收益不确定（-5%~+10%），回退开关零损失 | Phase 4 **默认搁置**，设决策门 | 调研 §6.3 |
| PR #26610 协议 6.0.0 无向后兼容 + 已知 `-sm tensor` hang bug | Phase 5 合并后等一个补丁周期再升 | 调研 §6.3 |
| ~~GGML_RPC_LOAD_THREADS~~（PR #26291 未合并，v0.2.0 无此变量） | **不纳入方案** | 调研 §6.2B (v1.2 作废) |
| thunderbolt-ibverbs: decode 收益个位数，内核模块维护成本高 | **不纳入**，仅长期备选 | 调研 §6.1 修正 1 |
| RADV 792MB 分配墙为潜伏雷（触发条件：升级 Mesa / 换 Q8） | 风险登记，不主动处置 | 调研 §6.4C |

### 2.2 职责边界

- **职责内**: 系统层（sysfs / MTU / systemd / rpc-server 启动参数）与度量方法学
- **职责外**: llama.cpp 二进制升级（归 UPGRADE_SOP 流程，Phase 5 仅触发）；Vulkan 算子优化（归《AMD平台算子层优化与USB4分布式调研.md》行动项）；模型层 MTP（归 Tier 2 换模型路线）

## 3. 架构设计

### 3.1 五阶段流水线

```
Phase 0 基线度量 ──→ Phase 1 链路层调优 ──→ Phase 2 服务参数改造 ──→ Phase 3 稳定性固化
 (15 min)            (pm_qos + MTU)          (-H 绑定 + -c 缓存)       (systemd + 崩溃兜底)
                          │                                               │
                          ▼                                               ▼
                 Phase 4 软RoCE试点(可选,默认搁置)              Phase 5 升级跟踪(事件驱动)
                 [决策门: 仅当 1-3 吃完仍不达标]                  [订阅 PR #26610/#26490/#26724]
```

**核心原则**:

1. **基线先行**: Phase 0 未完成不得进入 Phase 1（没有基线的优化 = 不可归因）
2. **单批单测**: 每个 Phase 的变更集跑同一 bench 命令，前后对比，数据回填 `metrics-log.md`
3. **全程可逆**: 每项变更均有一步回退命令（见各 Phase 回退行）
4. **两站同步**: MTU 等"单端不生效"项必须两站同时变更（调研 §6.2A 黑洞风险）

### 3.2 变更分层与归因维度

| Phase | 层 | 变更对象 | 主要影响维度 |
|-------|-----|---------|------------|
| 0 | 度量 | 无变更 | 建立对照 |
| 1 | USB4 物理/内核 | sysfs + netplan | RTT / 加载吞吐 |
| 2 | rpc-server 启动行 | 绑定面 + 缓存 | 加载时间 / 安全 |
| 3 | 进程管理 | systemd 单元 | RTO / 崩溃传导 |
| 4 | 传输层 | rxe 模块 | tg（不确定） |
| 5 | 协议层 | 二进制升级（SOP） | decode 全维度 |

各 Phase 影响维度基本不重叠，即使同批变更也可按维度归因。

## 4. 各阶段详细设计

### Phase 0: 基线度量（前置，~15 min，两站）

**目的**: 为所有后续 A/B 对比建立对照组；同时摸底两个潜伏风险（链路协商速率、丢包）。

```bash
# B 站执行（A 站按需对打）
ethtool thunderbolt0 | grep -i speed        # 判读: 应 40000Mb/s; 20000 = 换 40Gbps 认证线(≤0.8m)或换口
ip -s link show thunderbolt0                # 判读: errors/dropped 零增长
ping -i 0.2 -c 200 10.10.10.1               # 记录 avg+mdev (预期未调优 600-700µs)
iperf3 -c 10.10.10.1 -t 10 -P 4             # A 站 -s; TB 有效吞吐基线
llama-bench -m MiniMax-M2.7-Q4_K_S.gguf --rpc 10.10.10.1:50052 \
  -ngl 999 -t 16 -b 512 --n-cpu-moe 8 -fa on -r 20    # 与 DEV-LOG-009 同参数, -r 20 看 per-rep stddev
```

**产出**: `spec/rpc-optimization/metrics-log.md` 基线表（链路速率 / RTT / 带宽 / pp512 / tg128 ± stddev）。

**门槛**: 若 ethtool 显示 20000Mb/s，**优先换线重测**（物理层问题会污染所有后续归因）。

### Phase 1: 链路层调优（零成本，~30 min，两站）

#### 1a. pm_qos_resume_latency_us = 100（systemd 持久化）

调研 §6.3 已给出完整单元文件（`/etc/systemd/system/pm-qos-usb4.service`，oneshot + RemainAfterExit）。

- **验证**: `cat /sys/.../cpu0/power/pm_qos_resume_latency_us` = 100; ping 均值降至 ~134µs 级
- **回退**: `systemctl stop pm-qos-usb4 && systemctl disable pm-qos-usb4`（ExecStop 即 echo 0）
- **预期**: tg +2% 级，per-rep stddev 大幅收紧（同硬件实测，调研 §6.1 修正 2）
- **不做**: thunderbolt throttle 内核补丁（收益 +1%，modprobe 循环有接口不注册脆弱性，调研 §6.3）

#### 1b. thunderbolt0 MTU 9000

```bash
sudo ip link set dev thunderbolt0 mtu 9000 up      # 两站同时执行
ping -M do -s 8972 -c 3 10.10.10.1                 # 通 = 巨帧生效(载荷 8972=9000-20-28)
```

- **持久化**: 两站 netplan 的 thunderbolt0 段加 `mtu: 9000`
- **回退**: `ip link set dev thunderbolt0 mtu 1500` + 移除 netplan 行
- **预期**: 加载/prefill 吞吐↑、CPU 软中断↓；**tg 持平**（诚实预期，延迟主导）
- **风险**: 两端必须同时设，单端 = 大包静默丢包黑洞（Phase 1b 执行顺序: 两站 ssh 各就位后同步回车）

#### 1c. 验证与数据回填

重跑 Phase 0 的 ping + llama-bench -r 20，回填 metrics-log.md。**判据**: tg 反降超 stddev 即回退 1a/1b 定位。

### Phase 2: rpc-server 启动参数改造（~1 h 含首次加载，A 站）

一次重启同时完成两项（影响维度不同，可归因: 绑定只改监听地址不影响性能；缓存只影响加载不影响 tg）:

#### 2a. 绑定面收敛

`rpc-server -H 10.10.10.1 -p 50052`（弃 0.0.0.0 写法；A 站双网卡，50052 不再暴露于 192.168.1.x）

- **验证**: `ss -tlnp | grep 50052` 仅显示 10.10.10.1:50052
- **回退**: 启动行改回 `-H 0.0.0.0`（仅应急，不建议）

#### 2b. `-c` 本地缓存 + per-model 目录

```bash
# A 站磁盘规划: df 确认缓存分区 ≥75GB 可用(Q4_K_S 五五切分 A 侧 ≈65-70GB + hash 元数据)
export LLAMA_CACHE=/data/rpccache/MiniMax-M2.7-Q4KS    # 按模型+quant 分目录(#12954 实践)
mkdir -p "$LLAMA_CACHE"
rpc-server -H 10.10.10.1 -p 50052 -c
```

- **验证**:
  1. 启动日志 `local cache : <路径>` 行（无 `-c` 显示 `n/a`）
  2. **首次**加载: 因写缓存略慢，B 站 nload 可见全量网传（正常）
  3. **二次**重启: A 站 `nload thunderbolt0` 流量 ≈ 0；B 站日志 load 阶段耗时对比
- **回退**: 去掉 `-c` 与 LLAMA_CACHE；缓存目录可直接 `rm -rf` 重建
- **工程约束**:
  1. 缓存目录放 **ext4**（勿 F2FS，断电半写文件风险，调研 §6.3）
  2. **每次 llama.cpp 升级后首次重启，用 nload 观察是否仍有全量网传** — hash 策略变化会静默失效缓存
  3. 换模型/换 quant = 新建对应目录；旧目录手动删除，否则无限膨胀

### Phase 3: 稳定性固化（两站，~1 h）

> 兜底对象: PR #26724 未合并前，A 站 rpc-server 崩溃/OOM → B 站整进程 GGML_ABORT 无重连（调研 §6.4A）。

#### 3a. A 站 rpc-server systemd 化

- `Restart=always`（含 `render`/`video` 组权限，Environment 带 LLAMA_CACHE，ExecStart 含 `-H 10.10.10.1 -p 50052 -c`）
- **副作用吸收**: 当前 A 站 rpc-server 为裸进程（DEV-LOG-009 PID 14853），本 Phase 将其纳入 systemd 管理

#### 3b. B 站 llama-server systemd 化

```ini
[Service]
Restart=on-failure
RestartSec=10
StartLimitIntervalSec=0        # 禁 burst 限制
ExecStartPre=/bin/bash -c 'for i in $(seq 60); do timeout 1 bash -c "echo > /dev/tcp/10.10.10.1/50052" 2>/dev/null && exit 0; sleep 5; done; exit 1'
# A 站起不来时 B 站最多等 5 分钟, 避免白加载
```

#### 3c. 故障演练（必做验证）

```bash
# B 站发起长生成任务期间, A 站模拟崩溃:
sudo systemctl kill -s KILL rpc-server
# 判读: B 站 llama-server abort 后 10s 内自动重启; ExecStartPre 等 A 站 rpc-server 自愈(Restart=always)
# 恢复后 API 冒烟: /health + V020_PONG 用例(DEV-LOG-009 同款)
```

- **认知登记**: RTO 为分钟级（B 侧重加载，-c 后 A 侧秒级），**非热恢复** — 会话丢失不可避免，目标是进程自动恢复。
- **回退**: `systemctl disable --now` 两单元，恢复原 run_server.sh 裸进程方式。

### Phase 4: 软 RoCE 试点（可选，默认搁置）

**决策门（按序满足才启动）**:

1. Phase 1-3 完成后 tg128 仍 < 期望阈值（用户定义）
2. `ldd /opt/llama.cpp/rpc-server | grep -i ibverbs` 有输出（未编入则需 B 站装 `libibverbs-dev rdma-core` 重编译 + **两站同步换二进制**，成本升为半天，预期仍不确定 → 基本等于放弃）

**试点步骤**（已编入时，10 min）:

```bash
sudo rdma link add rxe0 type rxe netdev thunderbolt0
rdma link show                      # state active
# RPC 连接打在 rxe 挂载接口 IP(10.10.10.1) — RoCEv2 GID 由 netdev IP 派生, 现值即满足
```

**A/B 对比开关**: `GGML_RPC_NO_RDMA=1`（强制回 TCP）/ `GGML_RPC_DEBUG=1`（调试）。

**判据（预注册，防事后合理化）**: tg128 对比 TCP 差值 > 2× stddev 才视为有效；**tg 反降直接弃**（rxe 走 CPU 拷贝路径，占核与推理抢核，VM 实测 CPU 翻倍/带宽 25% 案例，调研 §6.3）— 损失为零（`rdma link delete rxe0` 即回退）。

### Phase 5: 升级跟踪（事件驱动，零日常成本）

| 订阅对象 | 触发动作 |
|---------|---------|
| PR #26610（协议现代化）+ #26490（stack 前置） | 合并后 **等一个补丁周期**（已知 bug: `-sm tensor` 多 RPC 后端 hang、`-sm layer` 曾 crash、与 MTP 不兼容，调研 §6.3），再按 UPGRADE_SOP 两站原子升级 |
| PR #26724（崩溃修复） | 合并后升级时 Phase 3 的 Restart 兜底从"必要"降级为"纵深防御"（单元文件保留） |
| issue #27553（K-quant 大 tile，算子层） | 转交《AMD平台算子层优化》行动项跟踪 |

**升级硬约束登记**（写进升级 checklist）:

1. 协议 6.0.0 **无向后兼容** → 单边升级 = 握手直接失败，SOP 两站原子升级语义从"建议"升为"强制"
2. 新增 comm port 端口 → A-B 直连拓扑已满足，无需 mesh
3. 升级后首启验证 `-c` 缓存是否仍命中（nload 流量观察，Phase 2b 工程约束 2）
4. 若届时已上 MTP 模型: #26610 与 MTP 组合暂不兼容，需取舍

## 5. 替代方案

### 5.1 方案 A: 五阶段流水线（选择）

- 优点: 每批可归因、全程可逆、零风险项先行、风险项有预注册判据
- 缺点: 多次 bench 循环，总时长 ~半天
- 选择理由: 符合"不可归因的优化不做"原则；反效果可单步定位

### 5.2 方案 B: 一次性全做（否决）

- 描述: pm_qos + MTU + -c + systemd + rxe 一晚全部上线，只做前后总对比
- 否决理由: 软 RoCE 有反效果风险（±5% 不确定），混批后无法定位劣化来源；MTU 单端黑洞难排查

### 5.3 方案 C: 直上传输层终极方案 thunderbolt-ibverbs（否决）

- 描述: 编译内核模块，USB4 口注册为 InfiniBand 设备（~48 Gb/s / ~7µs）
- 否决理由: 同硬件实测 decode 收益**个位数**（"TB is a load-time lever, not a decode lever"，调研 §6.1 修正 1）；内核模块跟随内核版本维护成本高；收益集中在训练/加载，非本方案目标场景。仅当未来启动 FSDP 训练时重启评估

## 6. 错误处理

| 错误场景 | 处理方式 | 用户可见信息 |
|---------|---------|------------|
| MTU 单端设置 → 大包黑洞 | 巨帧 ping 失败即停，补设另一端 | `ping: local error: Message too long` |
| `-c` 缓存升级后静默失效 | nload 见全量网传 → 删缓存目录重建 | 加载时间回升至冷启动量级 |
| pm_qos 后 ping 无改善 | 检查 cpu 数量是否全部写入（16 核全写） | RTT 停留 600µs 级 |
| A 站 rpc-server 反复崩溃 | systemd Restart=always 日志 `journalctl -u rpc-server` | B 站 RTO 拉长至 5 min 等待上限 |
| 软 RoCE tg 反降 | `rdma link delete rxe0`，回退开关 GGML_RPC_NO_RDMA=1 | tg 低于 TCP 基线 |
| RADV 792MB 分配墙触发（升级 Mesa/换 Q8 时） | 应急切 ROCm 7.2 后端（同硬件社区 MiniMax 生产配置, tg128 21.4 同量级） | "Remote RPC server crashed" |

## 7. 不变式（Invariants）

1. **基线不可跳过**: 任何性能变更前，Phase 0 基线数据必须已在 metrics-log.md
2. **单批单测**: 两个影响相同维度的变更不得同批上线（本设计中各 Phase 维度已错开，打破即违规）
3. **两站原子**: MTU 变更与二进制升级必须两站同步；单端变更属违规操作
4. **监听面**: rpc-server 永不监听 0.0.0.0（协议无认证，调研 §6.2C）
5. **缓存目录**: LLAMA_CACHE 必须按 模型-quant 分目录；缓存分区必须 ext4
6. **预注册判据**: Phase 4 的弃留判据在试点前登记（本文件 §4 Phase 4），不得事后放宽

## 8. 幻觉排除审查（Step 4 Review）

### 8.1 设计基于已验证的调研结论

- [x] 所有预期数字均引自同硬件（Strix Halo RPC 双机）社区实测，非跨平台外推
- [x] 明确拒绝外推: RDMA 对 0.6B 小模型 decode +126% **不适用**本集群 230B MoE（调研 §6.1 修正 1）
- [x] v1.2 已作废项（GGML_RPC_LOAD_THREADS）未混入方案
- [x] 预期收益按调研修正后口径书写（pm_qos +2% 而非 v1.0 的模糊乐观; 功耗 +1.5W 而非 5-15W）

### 8.2 替代方案审查

- [x] 3 个替代方案，各含否决理由（§5）
- [x] 最高成本方案（thunderbolt-ibverbs）有明确的重启评估条件，非永久否决

### 8.3 风险登记完整性

- [x] 调研 §6.4 三大风险面（崩溃传导 / USB4 断链 / RADV 分配墙）均有对应处置或登记
- [x] USB4 断链中的"链路协商 20Gbps"检查已前置到 Phase 0 门槛（防物理层污染归因）

## 9. 对实施的输入

### 9.1 关键工程约束

1. Phase 1b MTU: 两站 ssh 就位后同步执行；执行前确认无生产推理任务（巨帧黑洞窗口期）
2. Phase 2b: A 站先 `df` 确认 ≥75GB；首次加载变慢为预期现象，勿误判回退
3. Phase 3 systemd 单元: A 站 rpc-server 需 `render`/`video` 组；B 站 ExecStartPre 的 5 min 等待上限与 `-c` 配合后总 RTO 控制在分钟级
4. Phase 3c 故障演练**必做**（不演练的兜底 = 未验证的兜底）
5. 所有 bench 用 DEV-LOG-009 同参数（`-ngl 999 -t 16 -b 512 --n-cpu-moe 8 -fa on -r 20`），保证与 20.15 t/s 基线可比

### 9.2 实施产出物

| 产出 | 位置 |
|------|------|
| 度量日志（基线 + 各 Phase 回填） | spec/rpc-optimization/metrics-log.md |
| pm-qos-usb4.service / rpc-server.service / llama-server.service | 两站 /etc/systemd/system/ + 副本入 D:\RPC\scripts\ |
| 实施记录 | DEV-LOG-010（含偏差与发现，延续 DEV-LOG 体例） |

### 9.3 风险与缓解汇总

| 风险 | 缓解 |
|------|------|
| MTU 黑洞窗口 | 同步执行 + 巨帧 ping 立即验证 |
| 缓存 hash 静默失效 | 升级后 nload 例行检查（入 UPGRADE_SOP checklist） |
| rxe 抢核 | 预注册判据 + 一键回退 |
| 批间数据污染 | 单批单测不变式 + stddev 判读 |

---

**Review 签字**: _________ 日期: _________

## 附: 与调研行动项的对应关系（覆盖率核对）

| 调研 §五行动项 | 本设计 |
|--------------|--------|
| 1 pm_qos | Phase 1a |
| 2 MTU 9000 | Phase 1b |
| 3 -c 缓存 | Phase 2b |
| 4 ~~LOAD_THREADS~~（作废） | 不纳入（v1.2） |
| 5 绑定 10.10.10.1 | Phase 2a |
| 6 ldd 确认 ibverbs | Phase 4 决策门 2 |
| 7 软 RoCE 试点 | Phase 4（默认搁置） |
| 8 systemd 化 + 顺序依赖 | Phase 3 |
| 9 订阅三个 PR | Phase 5 |
| 10 thunderbolt-ibverbs 评估 | 替代方案 5.3（重启条件: FSDP 训练需求） |

覆盖率: 9/9 有效行动项全部承接（行动项 4 已被调研 v1.2 作废）。
