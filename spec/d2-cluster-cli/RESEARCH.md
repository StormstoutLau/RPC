# 调研文档：D2 集群聚合操作（cluster CLI + 状态总览）

---
id: d2-cluster-cli-RESEARCH
type: design
version: 1.0
status: draft
date: 2026-09-01
depends: []
upstream: null
---

> **Feature**: D2 集群聚合操作
> **创建日期**: 2026-09-01
> **状态**: draft
> **Spec 步骤**: Step 1-2
> **决策来源**: [ADR-0001](../../adr/ADR-0001-集群运维框架审计与四项改进决策.md) §决策 3（D2）

---

## 1. 调研目标

**核心问题**:
1. 主控站聚合入口的最小可靠实现形态是什么（语言/传输/解析）？
2. 模型→站点的路由规则如何确定（哪些模型加载到哪站）？
3. 状态总览页的数据源与形态（不越"不做第四个面板"的 ADR 边界）？

## 2. 调研方法

### 2.1 使用的工具

| 工具 | 用途 | 查询 |
|------|------|------|
| RunCommand (SSH) | 两站接口形态取证 | `infer-list` 输出、Python/SSH 版本 |
| RunCommand (本地) | 主控站运行时盘点 | Python/paramiko/PS 版本 |
| Read | 既有文档 | 手册 §2-3（快速开始/infer-* 语义）、ADR-0001 |

### 2.2 调研范围

- 两站 infer-\* CLI 的输出契约
- 主控站可用运行时（Python 3.11 venv + paramiko 5.0.0 / PS 5.1）
- 排除：D1 范畴（watchdog/fallbacks）、UI 框架选型（明确不做）

## 3. 调研发现

### 3.1 实现语言：Python 而非 ADR 草拟的 PowerShell

ADR-0001 §决策 3 原文写"cluster.ps1（30 行）"。**调研后修正为 Python 单文件 `cluster.py`**，依据：

| 维度 | PowerShell 5.1 | Python 3.11 + paramiko |
|------|---------------|----------------------|
| 远程执行 | ssh.exe 子进程（引号转义噩梦） | paramiko exec_command（结构化传参，零转义） |
| 中文输出 | GBK/UTF-8/BOM 三坑，**本日实测踩坑 3 次**（gb2312 乱码 / BOM 导致 bash 报错 / heredoc 引号截断） | 原生 UTF-8 |
| JSON 解析 | ConvertFrom-Json（PS5 对深嵌套有限制） | 原生 |
| 已验证度 | 手册 §2 示例可用但每条命令都是引号雷区 | SSH_OPENCODE_SETUP.md 记录 paramiko 免密已跑通（E2） |

paramiko 免密通道是既有资产（E2，主控站 `~/.ssh/id_ed25519` → 两站 authorized_keys）。

### 3.2 infer-\* CLI 输出契约（E1，2026-09-01 实测）

```
ALIAS                                  位置 大小  建议后端 CONF
-----                                  ---- ----    -------- ----
gpt-oss-120b                           AB   59G     llama-single ✓
deepseek-v4-flash-0731                B    145G    llama-rpc    ✓
nvidia-nemotron-3-super-120b-a12b      B    80G     llama-rpc    ✓
```

- **位置列**：`AB` = 两站均有副本；`B`/`A` = 仅单站；`A` 情形当前只有 gpt-oss-120b（AB）
- **建议后端**：`llama-single`（单机）/ `llama-rpc`（双机 RPC）/ `llama-emb`
- **CONF**：✓ = 该站已有 /etc/llama-instances/ 配置
- 当前加载状态可经 `systemctl is-active llama-server@*` 或 `:8080/health` 查询

### 3.3 模型→站点路由规则（E1 推导）

| 模型 | 路由站 | 依据 |
|------|-------|------|
| gpt-oss-120b | **A 站** | conf 在 A（D4 部署，单机速度档） |
| 其余全部 | **B 站** | conf 均在 B（nemotron 单机 + llama-rpc 类） |
| llama-rpc 类（deepseek 145G 等） | B 站发起，但需 A 站 rpc-server | 双机 RPC 模式，超出 D2 单命令边界 → 标注"手动两步" |

路由表硬编码于 cluster.py 顶部常量（3 行 dict），模型增删时手工同步——**不解析 infer-list 动态推导**（避免误路由到无 conf 的站）。

### 3.4 状态总览页形态

排除法：
- ~~Cockpit API 聚合~~：需鉴权 token，页面嵌套复杂
- ~~cluster.py serve 常驻 HTTP~~：又一个要管的服务，违背最小运维面
- **选定：`cluster.py status --html` 生成静态快照页**（单文件 HTML，含双站 health/infer-list/LiteLLM 状态/Beszel+Cockpit 链接），主控站浏览器直接开本地文件，重新生成即刷新。零常驻、零 CORS（llama.cpp 的 /health 虽有 CORS 头，但静态方案连这都不依赖）。

### 3.5 端点清单（E1，来自手册 §1.2）

| 目标 | 端点 |
|------|------|
| A 站 llama | `http://scott-lau-NEX.local:8080/health` |
| B 站 llama | `http://scott-lau-GTR-Pro.local:8080/health` |
| LiteLLM | `http://scott-lau-GTR-Pro.local:4000/health/liveliness`（key） |
| Beszel | `http://scott-lau-GTR-Pro.local:8090`（链接） |
| Cockpit A/B | `https://*.local:9095`（链接，自签证书） |

## 4. 综合分析

### 4.1 关键发现总结

1. 实现语言改 Python（paramiko 通道复用 + 规避 PS5 三坑）[置信度: ★★★★★ E1+E2]
2. 路由表硬编码 3 行 dict，不动态推导 [置信度: ★★★★☆，模型增删需手工维护是已知成本]
3. 状态页用静态快照（--html），零常驻服务 [置信度: ★★★★★]
4. llama-rpc 类模型超出单命令边界，UI 标注手动流程 [置信度: ★★★★★]

### 4.2 对 ADR-0001 的偏差申报

- ADR §决策 3 写"cluster.ps1"，本调研修正为 **cluster.py**（理由 §3.1）。语言替换属实现细节，不改变决策语义（主控站聚合入口 + status/load/unload/e2e 四子命令 + 单页总览），**不构成 ADR 修订**，仅在此备案。
- ADR 中"~半天"工时预估维持。

### 4.3 对实施文档的输入

- 子命令集：`status` / `load <alias>` / `unload` / `e2e` / `bench`（可选后置）
- status 数据源：两站 health + 两站 infer-list + LiteLLM 状态，输出对齐终端表格
- e2e：经 LiteLLM 双路由各发 1 个 8-token 请求
- 交付物：`ops/cluster.py`（D3 后 ops/ 是活资产的家）
