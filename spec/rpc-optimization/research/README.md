# rpc-optimization 调研依据

> **2026-09-09 归并**: docs 下 4 篇互连/RPC 层调研移入本目录，作为 [DESIGN.md](../DESIGN.md) 的上游依据统一收敛（原 docs 位置已移除，不再归档独立副本）。分类索引见 `model-eval/SOURCING-INDEX.md`。

## 目录

| 文档 | 主题 | 角色 |
|------|------|------|
| [RPC协议瓶颈调研.md](./RPC协议瓶颈调研.md) | RPC 协议层瓶颈 + 上游改造（RDMA/PR#26610）| DESIGN 主依据 |
| [RPC串行跨链社区优化调研.md](./RPC串行跨链社区优化调研.md) | RPC 串行跨链优化方案 | 补充依据 |
| [AMD395分布式推理高性能互连方案调研.md](./AMD395分布式推理高性能互连方案调研.md) | USB4/Thunderbolt 互连方案 | 互连层 |
| [AMD平台算子层优化与USB4分布式调研.md](./AMD平台算子层优化与USB4分布式调研.md) | Vulkan 算子层优化 | 算子层（operator-optimization 亦引用）|

## 维护规则

- 新增 RPC/互连层调研 → 直接放入本目录，登记上表
- DESIGN.md `depends` 只列被引用的调研（保持最小依赖）
- 实测数据入 `../rpc-optimization/metrics-log.md`（DESIGN 配套台账）