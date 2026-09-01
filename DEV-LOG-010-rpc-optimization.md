# DEV-LOG-010: RPC 优化方案五阶段执行（Phase 0-3 落地）

> **日期**: 2026-08-28
> **Feature**: 基于《RPC协议瓶颈调研.md》v1.1 及 spec/rpc-optimization/DESIGN.md 五阶段方案
> **结果**: ✅ Phase 0-3 全部落地并验证；吞吐收益≈0（符合预判），延迟尾部 6 倍改善，加载 -43s，崩溃自愈 MTTR ~6min

---

## 1. 最终状态（两站巡检）

| 组件 | A 站 (scott-lau-NEX) | B 站 (scott-lau-GTR-Pro) |
|------|---------------------|--------------------------|
| pm-qos-usb4.service | active (pm_qos=100) | active |
| thunderbolt0 MTU | 9000 (netplan 持久化) | 9000 (netplan 持久化) |
| rpc-server.service | active, 监听 10.10.10.1:50052, -c 缓存 47G | — |
| llama-server.service | — | active, API /health ok |
| api 端点 | — | B:8080 / 主控: 192.168.1.15:8080 |

## 2. 各阶段结果（详见 spec/rpc-optimization/metrics-log.md）

### Phase 1: pm_qos + MTU 9000
- RTT: avg 0.619→**0.100ms (-84%)**, max 1.272→**0.230ms (-82%)**, mdev 108→11µs
- 吞吐: pp512 139.19→141.12 (+1.4%, 噪声边缘), tg128 19.95→20.05 (+0.5%, 噪声内) — **收益≈0**
- iperf3: 9.02→8.98 Gb/s (持平, 巨帧收益不在吞吐)
- 判读: 链路非瓶颈（调研 v1.1 预判成立）；真实价值在 P99 尾延迟（bench 均值不可见）

### Phase 2: rpc-server 收敛暴露面 + -c 缓存
- 50052: 0.0.0.0 → **10.10.10.1**（协议无认证，收敛到 USB4 专网）
- 缓存: 47G/136 tensor 文件 → A 站 /data/rpccache/
- 加载: 冷 310s → 热 **267s (-43s)** ≈ 47G@9Gb/s 传输时间（精确吻合，缓存命中跳过网络传输）

### Phase 3: systemd 双向自愈 + 崩溃传导演练
- **演练时间线**: T+0s kill A 站 rpc-server → T+6s A 自愈 → T+~82s B 推理请求触发 GGML_ABORT → T+~110s B 重启+wait_rpc → T+358s model loaded → T+360s 推理恢复
- **MTTR ~6 分钟**，瓶颈 = 模型重载 245s（缓存命中态）

## 3. 新发现（记入发现日志）

### 发现 1（协议行为）：idle 态 RPC 断裂不传导
- **现象**: kill rpc-server 后 B 站 idle llama-server 不 abort，/health 持续 ok；仅推理请求触发断连才退出
- **推论**: /health 不探测 RPC 后端 → 外部监控不能依赖 /health，需定时推理探活（1-token 请求）
- **影响**: 若 A 站夜间崩溃且无请求，次日首请求会 hang/失败 → 服务自愈链才启动；可接受（自愈闭环存在）

### 发现 2（监控误报）：v0.2.0 /health 加载期即返回 ok
- crash_drill.sh 的 RECOVERED 判据（/health ok）在模型加载中误报；真实恢复验证必须用推理请求
- 教训：探活判据 = 推理请求，不是 /health

### 发现 3（工具链）：PowerShell→ssh 多层转义是持续性陷阱
- `$(date)`/`$LOG`/`\"` 在 PowerShell 双引号→ssh→远程 bash 三层解析中被吞或误展开（本轮踩 3 次：bench 首跑无效、冒烟 JSON 损坏、监控启动失败）
- **规则（已验证）**: 含变量/引号/重定向的远程操作一律走"本地写脚本 → scp → ssh bash 执行"通道；纯只读查询可用简单命令
- 本轮新增脚本（d:\RPC\scripts\）: bench_phase1.sh / smoke_test.sh / crash_drill.sh / netplan-01-{A,B}.yaml

### 发现 4（netplan 持久化路径）：nmcli modify 对 netplan 生成连接不持久
- netplan-thunderbolt0 连接 keyfile 在 /run（tmpfs），nmcli modify 只改运行副本
- **正确路径**: 改 /etc/netplan/01-network-manager-all.yaml 加 `mtu: 9000` → `netplan generate` → keyfile 带持久值
- 途中 printf 远程写 yaml 因转义损坏（LF 丢失）→ 从 .bak 恢复 → 改用本地文件 scp 通道（安全规则再立功）

### 发现 5（rpc-server -c 日志噪音）: journal 每 tensor 一行 `[set_tensor] saved`（136 条/加载），journald 限速内无压力

## 4. 偏差与未做项

| 项 | 状态 | 原因 |
|----|------|------|
| bench -r 20 | 未执行, 用 -r 2 | -r 20 单轮 ~25min×多阶段成本过高; -r 2 方差已可判读（±0.04~0.08） |
| 软 RoCE (Phase 4) | 搁置 | 决策门未触发（1-3 阶段后吞吐未达标是因其非瓶颈, RoCE 无法改善算力瓶颈） |
| 链路 20G→40G 换线 | 留作用户可选项 | 物理操作, 不阻塞软件层; 社区数据加载带宽翻倍预期 |
| 主控站 40G 验证 | N/A | 20G 协商速率下 iperf3 9Gb/s 已与社区一致 |
| llama-server 断线重连跟踪 | 记入 Phase 5 事件驱动 | PR #26724 未合并, 当前架构重启是唯一恢复路径 |

## 5. 后续跟踪（Phase 5, 事件驱动）

- PR #26610 (async graph_compute, 协议 6.0.0 无向后兼容) — 合并后评估升级路径
- PR #26490 / #26724 (RPC 重连) — 直接改善 MTTR
- v0.2.x 后续 release 的 RDMA/RoCE 协商状态确认
- 40G 认证线缆（≤0.8m）采购后重跑 Phase 0 链路基线对比

## 6. 部署产物清单

| 文件 | 位置 | 说明 |
|------|------|------|
| pm-qos-usb4.service | 两站 /etc/systemd/system/ | pm_qos=100, 开机生效 |
| rpc-server.service | A 站 /etc/systemd/system/ | -H 10.10.10.1 -c, Restart=always |
| llama-server.service | B 站 /etc/systemd/system/ | 参数同源 inference.conf, Restart=on-failure |
| wait_rpc.sh | B 站 /llama-distributed/ | ExecStartPre 等待 A 站就绪 (755) |
| 01-network-manager-all.yaml | 两站 /etc/netplan/ (+.bak-mtumig 备份) | mtu 9000 持久化 |
| bench_phase1.sh / smoke_test.sh / crash_drill.sh | B 站 ~/llama-distributed/ + 主控 d:\RPC\scripts\ | 度量/冒烟/演练工具 |
| /data/rpccache/MiniMax-M2.7-Q4KS | A 站 | 47G tensor 缓存 |
