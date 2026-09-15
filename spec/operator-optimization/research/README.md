# operator-optimization 调研依据

> **2026-09-09 归并**: docs 下编排/运维相关调研移入本目录，作为 [DESIGN.md](../DESIGN.md) 的上游依据统一收敛（注：算子层调研《AMD平台算子层优化与USB4分布式调研.md》已归 `../rpc-optimization/research/`，本 DESIGN 继续引用）。分类索引见 `model-eval/SOURCING-INDEX.md`。

## 目录

| 文档 | 主题 | 角色 |
|------|------|------|
| [双机推理服务化与编排框架调研.md](./双机推理服务化与编排框架调研.md) | 双机推理服务化/编排/Cockpit/Beszel 选型（v1.14 全案）| 运维编排依据 |
| [模型路径统一方案A_20260909.md](./模型路径统一方案A_20260909.md) | 三站模型路径统一方案 A（执行完成）| 资产布局依据 |

## 维护规则

- 新增编排/运维调研 → 直接放入本目录并登记
- 算子层/协议层依据见 `../rpc-optimization/research/`
- 实测数据入 [metrics-log](../../rpc-optimization/metrics-log.md)（配合台账）