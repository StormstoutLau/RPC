# adr/ — 架构决策记录

> **定位**：本目录只放**裁定**（定了什么、为什么、考虑过什么替代方案、何时重启）；**实现状态**看 [OPEN-ISSUES](../spec/d6-agent-standard/OPEN-ISSUES.md)。
> **纪律**：一份 ADR 一个决策；已裁定的**不删不改**，推翻要新开 ADR 并写「取代 ADR-XXXX」。
> **门禁**：每份必须有 `## 考虑的替代方案` 节且非空（`adr` 断言）。

## 15 份 ADR

| 编号 | 标题 | status |
|---|---|---|
| [ADR-0001](./ADR-0001-集群运维框架审计与四项改进决策.md) | 集群运维框架审计与四项改进决策 | proposed |
| [ADR-0002](./ADR-0002-网关401故障根因与fan-out路由决策.md) | 网关 401 故障根因与 fan-out 路由决策 | accepted |
| [ADR-0003](./ADR-0003-OpenRouter密钥与egress路由管理.md) | OpenRouter 密钥与 egress 路由管理 | accepted |
| [ADR-0004](./ADR-0004-统一管理入口为唯一管理面.md) | 统一管理入口为唯一管理面 | accepted |
| [ADR-0005](./ADR-0005-任务卡证据回收闭环.md) | 任务卡证据回收闭环 | accepted |
| [ADR-0006](./ADR-0006-控制面传输绑定LAN_IPv4.md) | 控制面传输绑定 LAN IPv4 | accepted |
| [ADR-0007](./ADR-0007-证据流阶段推进路线与改动验证闭环.md) | 证据流阶段推进路线与改动验证闭环 | accepted |
| [ADR-0008](./ADR-0008-跨项目受理区与目录治理.md) | 跨项目受理区与目录治理 | accepted |
| [ADR-0009](./ADR-0009-D6与D7分界判据.md) | D6 与 D7 分界判据 | accepted |
| [ADR-0010](./ADR-0010-DwarfStar第二引擎引入立项.md) | DwarfStar 第二引擎引入立项 | accepted |
| [ADR-0011](./ADR-0011-A4-vLLM-TP2-暂缓裁定.md) | vLLM TP=2 暂缓裁定 | accepted |
| [ADR-0012](./ADR-0012-A站容器栈纳管.md) | A 站容器栈纳管 | accepted |
| [ADR-0013](./ADR-0013-跨仓库使用本框架的准入与派发分界.md) | 跨仓库准入与派发分界 | accepted |
| [ADR-0014](./ADR-0014-halogen引擎引入与容器写动作扩权.md) | halogen 引擎引入与容器写动作扩权 | accepted |
| [ADR-0015](./ADR-0015-飞书远程操作桥接引入.md) | 飞书远程操作桥接引入 | accepted |

## 阅读顺序（新读者）

1. [ADR-0004](./ADR-0004-统一管理入口为唯一管理面.md) —— 治理总纲（单一管理面、零自加载）
2. [ADR-0009](./ADR-0009-D6与D7分界判据.md) —— D6（执行面）与 D7（结论面）的分界
3. [ADR-0013](./ADR-0013-跨仓库使用本框架的准入与派发分界.md) —— 跨仓库怎么用本框架
4. [ADR-0015](./ADR-0015-飞书远程操作桥接引入.md) —— 唯一常驻例外（`rpc-bridge`）
5. 其余按编号顺读

## 检索提示

- 按 `status` 筛：`py -3 ops/rpc_doc_index.py --type adr`（元数据来自各文件 YAML 头）。
- **ADR ≠ 待办**：裁定只说明方向；落地进度、证据与阻塞一律查 [OPEN-ISSUES](../spec/d6-agent-standard/OPEN-ISSUES.md)。
