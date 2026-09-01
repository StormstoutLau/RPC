# USB4 40Gbps 链路能力评估

> **日期**: 2026-08-28
> **执行**: 依据 DEV-LOG-010 后续链路能力分析（软硬件 40G 支持判定）
> **结论**: 软硬件均支持 40Gbps，唯一障碍在物理层（线缆）；同时发现当前链路 idle 态振荡隐患

---

## 1. 评估背景

Phase 0 实测链路协商速率 20000Mb/s（20G），调研报告曾指出 40G 认证线缆换线可望加载带宽翻倍，留作用户可选项。本轮系统采集两站 USB4 控制器、链路状态、驱动信息，判定 40G 支持能力，为换线决策提供依据。

## 2. 硬件层判定：支持

| 检查项 | A 站 (scott-lau-NEX) | B 站 (scott-lau-GTR-Pro) | 判定 |
|--------|---------------------|--------------------------|------|
| SoC USB4 控制器 | Strix Halo USB4 Host Router ×2 (`1022:158d`/`158e`) + PCIe USB4 Bridge (`1022:150a`) ×2 | 同 (`1022:158d`/`158e`/`150a`/`150b`) | ✅ USB4 规范 40Gbps，双控制器 |
| 对端 router 代际 | `0-2/generation = 4` | `1-2/generation = 4` | ✅ Gen4 = USB4（非 TBT3），全链路 USB4 |
| 对端识别 | `0-2: Intel Corp. scott-lau-GTR-Pro` (vendor 0x8086) | `1-2: Linux scott-lau-NEX` (vendor 0x1d6b) | XDomain 双主机互联正常 |
| Retimer | A 侧 `0-0:2.1` vendor=0x7fea + `0-0:2.2` vendor=0x1da0 | B 侧 `1-0:2.1` vendor=0x1da0 | ⚠️ 存在 retimer（主动元件），见 §4 |

## 3. 软件层判定：支持，零改动

| 检查项 | A 站 | B 站 | 判定 |
|--------|------|------|------|
| 内核版本 | 7.0.0-30-generic | 6.17.0-23-generic | ✅ USB4 40G 隧道支持成熟（6.x 起） |
| 内核驱动 | `thunderbolt` + `thunderbolt_net` 已加载 | 同 | ✅ |
| ACPI USB4 _OSC | `OS supports/controls USB3+DP+PCIe+XDomain` | 同 | ✅ 内核完整接管 USB4 特性协商 |

**换 40G 线后自动协商，无需任何配置变更。**

## 4. 当前链路问题（两项）

### 4.1 协商速率 20G（降级）

- `ethtool thunderbolt0` → Speed: **20000Mb/s**（A 站实测）
- USB4 Gen3x2（40G）链路训练失败 → 降级至 Gen2 级别速率

### 4.2 链路 idle 态振荡（新发现，比降级更严重）

采集期间实测（boot 后持续 3 小时）：
- 两站 retimer `found/disconnected` 循环，间隔 1~2s（`vendor=0x7fea/0x1da0` 交替重枚举）
- 对端 router 周期性重枚举（`new host found` 反复出现）
- A 站 `thunderbolt0` netdev 一度消失，几十秒后重建
- 规律：**数据流时稳定**（当日 310s/267s 模型加载 122G 传输零中断），**idle 时振荡**（疑似链路低功耗状态 CLx 切换唤醒失败）

**风险传导**：振荡期间 netdev 消失会直接断 RPC 连接 → B 站推理请求触发 GGML_ABORT → 依赖 Phase 3 自愈链恢复（MTTR ~6min）。idle 振荡 + `发现 1（idle 不传导）`叠加意味着：若振荡发生在无请求时段，下次请求才触发崩溃。

## 5. 根因判定

20G 降级 + retimer 振荡共同指向**信号完整性差**：
- Gen3 每通道 10Gbps 对线缆质量要求远高于 Gen2 的 5Gbps → 训练失败降级
- 降级后 CLx（链路低功耗）唤醒仍不稳定 → idle 态反复重训练

瓶颈在**当前线缆**（非 USB-IF 认证 40G / 过长 / 质量问题）。Retimer 均在主板侧（非线缆内），当前线缆大概率为被动线；若长度 >0.8m，被动线物理上无法支持 40G。

## 6. 换线建议

- **必须**: USB-IF 认证 **USB4 40Gbps** 或 **Thunderbolt 4** 认证线，被动线 **≤0.8m**
- **陷阱**: 市面大量"USB4 线"实为 20Gbps（Gen2x2）；认准明确 40Gbps 标识或 TB4 认证 logo
- **推荐型号**（社区验证充分）: CalDigit TB4 0.8m / Cable Matters TB4 0.8m

## 7. 换线后验证清单

```bash
# 1. 协商速率（期望 40000Mb/s）
ethtool thunderbolt0 | grep Speed
# 2. 链路稳定性（期望: 无 retimer found/disconnected 循环、无重复 new host found）
sudo dmesg | grep -iE 'retimer|new host' | tail -20
# 3. 带宽（期望 20~30 Gb/s，USB4 网络隧道协议开销后）
iperf3 -c 10.10.10.1 -P 4 -t 15
# 4. 重跑 Phase 0 bench 对比（加载/冷加载为带宽敏感项）
bash ~/llama-distributed/bench_phase1.sh
# 5. idle 振荡复查（静置 10 分钟观察 dmesg 增量）
```

## 8. 预期收益（克制估计）

| 项 | 当前 (20G) | 换 40G 后 | 依据 |
|----|-----------|----------|------|
| iperf3 吞吐 | 9 Gb/s | 20~30 Gb/s | USB4 网络隧道开销后典型值 |
| RPC 冷加载传输 (47G) | ~45s | ~20s | 带宽敏感 |
| bench pp512 | 141 t/s | <5% 提升 | prefill 非纯带宽瓶颈 |
| bench tg128 | 20 t/s | 无变化 | 延迟主导，非带宽 |
| idle 断链风险 | 存在（振荡） | 预期消除 | 信号完整性恢复 |

## 9. 与既有文档关系

- 补充 [DEV-LOG-010](../../docs/DEV-LOG-010-rpc-optimization.md) §4 遗留项"链路 20G→40G 换线"的判定依据
- 呼应 [RPC协议瓶颈调研.md] §6.1 链路层措施及 [AMD平台算子层优化与USB4分布式调研.md] 传输层天花板章节
- Phase 3 自愈链（DEV-LOG-010 §3）是 idle 振荡风险的兜底，已验证有效
