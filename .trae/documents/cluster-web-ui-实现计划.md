# cluster.py web — 傻瓜式推理框架管理 Web UI 实现计划

## Context（为什么做）

`cluster.py` 已是集中式 CLI 聚合入口（status/frames/load/unload/e2e），但"傻瓜式"仍停在命令行——用户要**点到就能加载/切后端/卸载**的可视化操作，而不是记忆命令。

本计划新增 `cluster.py web` 按需服务：主控站起一个轻量 HTTP 服务，浏览器单页同时做到**三站框架状态可视 + 按钮操作代理**。用完 Ctrl-C 退出即停、不常驻，不违背"纯客户端聚合器 + 站内自足 / 零自加载"哲学（主控站非推理站，按需起服务可接受）。

**形态已由用户确认**：`cluster.py web 按需服务`（非静态快照、非复制命令混合版）。

## 关键约束（已核实）

- 主控实际解释器 `C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe`（3.12.10）
- 可用库：`http.server`(stdlib ✓)、`paramiko`(✓)、`flask`(✓)、`fastapi`(✗)、`uvicorn`(✓)、`pydantic`(✓)
- **决策：用 stdlib `http.server`**（`ThreadingHTTPServer`）+ `paramiko`。零新增依赖，与 `cluster.py` 现有纯 stdlib+paramiko 风格一致；接口只有 3~4 个端点，手动路由不复杂，不引入 flask。

## 架构

**新增文件** `ops/cluster_web.py`（服务 + 前端单页 + 操作代理），复用 cluster.py 现成函数：
- `from cluster import ssh_run, ssh_stream, probe_frames, cmd_load, cmd_unload, BACKENDS, ROUTE, STATION_PORT, STATIONS`（同目录直接 import）

**cluster.py 薄转发**：新增 `web` 子命令，`import cluster_web; sys.exit(cluster_web.serve(args))`，docstring 加一行用法。

## 服务设计（ops/cluster_web.py）

```
cluster.py web [--host 127.0.0.1] [--port 8095] [--token <可选>]
```

- 默认绑 `127.0.0.1:8095`（本机浏览器安全免鉴权调试）；`--host 0.0.0.0` 才开放局域网
- token：未提供则随机生成；启动打印 `URL + token`；前端首次 401 弹框存 `localStorage`，请求带 `X-Auth-Token` header（防局域网/DNS-rebinding 误操作）

### 端点

| 方法/路径 | 入参 | 行为 | 返回 |
|---|---|---|---|
| GET `/` | – | 返回内嵌单页 HTML | text/html |
| GET `/api/status` | – | 聚合三站 `probe_frames`（含引擎 :8080 health + 加载实例） | JSON `{time, stations:{A/B/C:{reachable,frames:{llama:["RUNNING",detail],...},engine,loaded}}}` |
| POST `/api/load` | `{alias, backend?}` | `redirect_stdout` 捕获→`cmd_load(alias, backend)` 同步执行（最长 ~3min） | `{rc, log}` |
| POST `/api/unload` | – | 同上→`cmd_unload()` 三站并行 | `{rc, log}` |
| POST `/api/backend` | `{alias, backend}` | 同上→`cmd_load(alias, backend)`（换后端一次命令） | `{rc, log}` |

- 所有 `/api/*` 统一鉴权头校验；`/` 公开
- 操作端点同步阻塞 + 前端 spinner：点击→按钮禁用转圈→完成后刷新 `/api/status` 并显示聚合 `log`（含 GTT 释放、READY 等）。**v1 不做 SSE 实时进度**（避免过度工程；加载日志最终全量返回足够）

### 前端单页（内嵌 HTML，沿用 render_html 视觉风格）

- 三站卡片/表格：每站 `reachable` + 框架行 `llama/unsloth/vllm/litellm/opencode`（RUNNING 绿/STOPPED 灰/Unknown 红）+ 引擎 :8080 + 加载实例
- 操作区：**模型输入**（下拉建议`ROUTE`+`RPC_MODELS` 常用别名 + 可自定义输入）+ **后端下拉 `BACKENDS`** + 三个按钮：`加载`、`切换后端`、`三站卸载`
- 自动轮询 `/api/status`（如 5s）；操作中暂停轮询
- 首次 401 → 弹 token 输入框存 `localStorage`
- 零外部 CDN（纯原生 JS + fetch），file/单页自包含

## 复用点（不重复造轮子）

- `cluster.ssh_run` / `ssh_stream` / `probe_frames` / `_frame_status`：框架状态探测
- `cluster.cmd_load`（含 backend 白名单校验、RPC 类 exit2 分支、P1 换载串行化）、`cluster.cmd_unload`
- `cluster.BACKENDS` / `ROUTE` / `RPC_MODELS` / `STATION_PORT` / `STATIONS`：下拉数据源

## 改动文件

1. **新增** `d:\RPC\ops\cluster_web.py`（~200 行：serve 解析 + ThreadingHTTPServer + handler + 单页 HTML 常量 + 任务捕获执行）
2. **修改** `d:\RPC\ops\cluster.py`：
   - 顶部 docstring 用法/子命令加 `web`
   - `main()` 加 `web` 分支：`import cluster_web; return cluster_web.serve(sys.argv[1:])`
   - `import io, contextlib`（捕获日志用；web 模块内做，cluster.py 仅转发）

## 验证（端到端）

1. `python ops/cluster.py web` 起服务，控制台打印 URL+token
2. `Invoke-RestMethod -Uri http://127.0.0.1:8095/api/status -Headers @{X-Auth-Token=$t}` → 返回三站 frames JSON（实测有无引擎均正确）
3. 浏览器开 URL → 登录填 token → 三站框架状态渲染
4. `POST /api/load {alias:"gpt-oss", backend:"unsloth"}` → rc=0 + log 含 READY；`/api/status` 刷新确认 unsloth RUNNING
5. `POST /api/backend` 切后端一键生效；`POST /api/unload` 三站卸载 → frames 变 STOPPED
6. `Ctrl-C` 退出、`netstat` 确认端口释放（不残留）
7. 无 token 请求 `/api/status` → 401

## 边界与不做

- 不做实时进度流（SSE）、不做模型库扫描、不做持久化；鉴权为局域网级别（非公网安全目标）
- 后端切换仍需引擎在线/内存门控约束（沿用 infer-load 站内判定），web 只是代理，不重复实现
- token 不落盘明文（进程内存 / 用户 localStorage）