# 调研：三站 Claude Code 接本地 halogen + 手机经飞书远程操作

---

id: claude-halogen-feishu-2026-10-30
type: research
version: 1.0
status: draft
date: 2026-10-30
depends: [ADR-0014, ADR-0004, O-181]
upstream: null

---

> **问题**：① A/B 两站的 Claude Code 如何各自接入**本机** halogen qwen3.8 flash；② Claude Code 如何接飞书，实现手机远程操作。
> **结论（先说）**：① **只需改一行**（`ANTHROPIC_BASE_URL` → `127.0.0.1:8731`），当前 A/B 站上 claude **实际不可用**（指向的 8080 已无服务）；② 飞书侧推荐 **cc-connect**（长连接、无需公网 IP），但它是常驻进程，**与 ADR-0004「无 daemon」纪律冲突 ⇒ 须先立项**。
> **证据级别**：E1 = 本集群实测；E3 = 外网检索（未在本仓复现）。

---

## 1. 现状盘点（E1，2026-10-30 实测）

### 1.1 三站 claude 与端点

| 站 | claude | 二进制 | `ANTHROPIC_BASE_URL` | `:8080` | `:8731` |
|---|---|---|---|---|---|
| A | **2.1.258** | `/usr/local/bin/claude` | `http://127.0.0.1:8080` | ❌ 无服务 | ✅ 200 |
| B | **2.1.258** | `/usr/local/bin/claude` | `http://127.0.0.1:8080` | ❌ 无服务 | ✅ 200 |
| C | **2.1.258** | `/usr/bin/claude` | `http://127.0.0.1:8080` | ✅ 容器发布 | ✅ 200 |

**A/B 站 claude 当前不可用** —— 三站配置是 2026-10 早期统一模板（指向 8080），而 2026-10-29 起 halogen 容器在 A/B **只发布 8731**（刻意不占 8080，给 deepseek head 让位，见 `O-181`）⇒ 配置与实况脱钩。

### 1.2 三站 `~/.claude/settings.json`（三站逐字同构）

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:8080",
    "DISABLE_AUTOUPDATER": "1",
    "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "120000",
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "32000"
  },
  "apiKeyHelper": "/home/scott-lau/.config/rpc/claude-key.sh",
  "theme": "dark",
  "model": "claude-opus-4-6",
  "modelOverrides": {
    "claude-opus-4-6": "main",
    "claude-sonnet-4-6": "main",
    "claude-haiku-4-5": "main"
  }
}
```

（`enabledPlugins` / `extraKnownMarketplaces` 段略，与本题无关。）

### 1.3 halogen 端点事实（E1）

`GET 127.0.0.1:8731/v1/models` ⇒

```json
{"data":[{"id":"halogen-qwen3.8-flash-next","max_model_len":1048576,
          "max_tokens_cap":65536,"max_tokens_default":8192,
          "architecture":{"input_modalities":["text"],"output_modalities":["text"]}}]}
```

**halogen 接受 `model=main`**（E1）：`POST /v1/messages` 用 `{"model":"main",...}` ⇒ **200**，响应回显 `"model":"halogen-qwen3.8-flash-next"` ⇒ **引擎忽略客户端 model 名**（与 `inventory/ports.yaml` 的既有记载一致）。

> ⚠ **判据自证教训**：本结论前两次测试都报 `body: Input should be a valid dictionary...`，真因是 **shell 引号把 JSON 拆坏**（不是引擎拒绝）。第三次改用 `scp` 传 JSON 文件 + `--data-binary @file` 才得真值。⇒ 凡跨机发 JSON，**别在命令行里拼引号**。

### 1.4 C 站 claude 冒烟（E1）

`claude -p "reply exactly: OK" < /dev/null` ⇒ **rc=0**（走 `8080 → 容器 → halogen`，证明整套配置模式有效）。

⚠ 副作用观察：小 `max_tokens` 时 halogen 会把预算全花在 **thinking**（`stop_reason=max_tokens`，content 只有 `thinking` 块、无 `text`）⇒ 实际使用必须保证输出预算充足（现配 `32000` 可用）。

### 1.5 执行记录（2026-10-30 · E1）

已按 §2.1 完成接入：A/B 两站 `~/.claude/settings.json` 的 `ANTHROPIC_BASE_URL` 由 `http://127.0.0.1:8080` 改为 `http://127.0.0.1:8731`。

- 改法：`python3` 读 JSON → 只改 `env.ANTHROPIC_BASE_URL` 一个键 → 原缩进写回（其余字段逐字不动）；
- 备份：`~/.claude/settings.json.bak-o183-20261030`（两站各一份）；
- 三站冒烟 `claude -p "reply exactly: OK" < /dev/null`：

| 站 | BASE_URL | rc | 输出 |
|---|---|---|---|
| A | `8731`（已改） | **0** | 真实回复（带集群规则上下文） |
| B | `8731`（已改） | **0** | 真实回复 |
| C | `8080`（**未改**） | **0** | 真实回复 |

⇒ A/B 由「当前不可用」转为可用；C 未动、仍可用。

---

## 2. A/B 接入本机 halogen（方案 · 已执行见 §1.5）

### 2.1 改一处

三站 `~/.claude/settings.json` 的 `env.ANTHROPIC_BASE_URL`：

```diff
- "ANTHROPIC_BASE_URL": "http://127.0.0.1:8080"
+ "ANTHROPIC_BASE_URL": "http://127.0.0.1:8731"
```

其余**逐字不动**：
- `model=claude-opus-4-6` + `modelOverrides → main` —— halogen 忽略 model 名，已验证；
- `apiKeyHelper` —— halogen 不校验凭据，helper 返回非空即可；
- `CLAUDE_CODE_MAX_CONTEXT_TOKENS=120000` —— **保留**。它是防 `O-180`（88 万 token prefill 撞 600 s 看门狗）的保护值，不能因 halogen 支持 1M 而调大；
- `CLAUDE_CODE_MAX_OUTPUT_TOKENS=32000` —— 在 `max_tokens_cap=65536` 内，保留。

C 站可选统一到 `8731`（少一跳 `docker-proxy`），非必须。

### 2.2 验证与回滚

```bash
# 站上
claude -p "reply exactly: OK" < /dev/null      # 期望 rc=0 且有文本输出
# 回滚：把 8731 改回 8080 即可（A/B 改回后【不可用】，属已知状态）
```

### 2.3 风险

| 风险 | 说明 |
|---|---|
| 只改 claude、不改 halogen | A/B 的 `8731` 是**唯一**引擎口；若容器停，claude 立刻不可用（与 8080 时代相同） |
| 未来若恢复 deepseek head | B 站 8080 会被 head 占；此时 claude 指 8731 反而**互不干扰**（这正是本方案的好处） |
| 三站配置漂移 | 三站 settings 是**各自文件**、不在仓库真值内 ⇒ 改完需人工确认三站一致（或后续纳入 `agent-cli` 下发） |

---

## 3. 飞书接 Claude Code（E3 检索 + 约束分析）

### 3.1 站上网络前置（E1）

| 域名 | HTTP | 说明 |
|---|---|---|
| `open.larksuite.com` | **200** | 可达 |
| `open.feishu.cn` | **404** | 可达（根路径 404 属正常，非阻断） |

⇒ 站上具备访问飞书开放平台的出网能力。

### 3.2 三个候选（E3，未在本仓复现）

| 方案 | 形态 | 适配度 | 备注 |
|---|---|---|---|
| **cc-connect**（`chenhg5/cc-connect`） | npm / Homebrew / 单二进制；`config.toml` 配 `agent=claudecode` + `platform=feishu`；**长连接、无需公网 IP**；带 Web 管理界面 | ★★★ | 同时支持 11 个平台，未来可扩 |
| **remote_claude**（`yyzybb537/remote_claude`） | 专做飞书：接收 Claude 输出 + 手机发指令 | ★★ | 更轻，单一用途 |
| **飞书官方 CLI**（`npx @larksuite/cli`） | 让 Claude **操作**飞书（文档/消息） | ★ | 方向相反（是 Claude→飞书，不是手机→Claude） |

cc-connect 配置形态（E3，摘自其文档示例）：

```toml
[[projects]]
name = "rpc"
[projects.agent]
type = "claudecode"
[projects.agent.options]
work_dir = "/home/scott-lau/work"
mode = "default"

[[projects.platforms]]
type = "feishu"
[projects.platforms.options]
app_id = "cli_xxxx"
app_secret = "xxxx"
```

### 3.3 推荐链路

```
手机飞书 → 飞书开放平台（长连接，自建应用）
        → cc-connect（B 站常驻）
        → claude -p（本机 127.0.0.1:8731）
```

**装 B 站的理由**：它是 master（`nodes.env` 在此）、出网正常、且改 §2.1 后 claude 即用本地 halogen。装主控则多一条隧道依赖（`18082`）。

### 3.4 必须先解决的三个约束

| # | 约束 | 处置 |
|---|---|---|
| 1 | **ADR-0004「无 daemon」** —— cc-connect 是常驻进程，与「零自加载」纪律冲突 | ✅ **已立项 [ADR-0015](../../adr/ADR-0015-飞书远程操作桥接引入.md)**（2026-10-30）：唯一常驻例外 `rpc-bridge.service`，`Restart=no` + `systemctl disable` |
| 2 | **安全边界** —— 手机消息 = 任意指令入口 | 锁 `work_dir`（如 `/home/scott-lau/work`）、配工具白名单、开审批模式；**禁用** `--dangerously-skip-permissions` |
| 3 | **飞书应用配置** | 自建应用 + 权限 `im:message` / `im:message:send_as_bot`；开发者后台开启**长连接**接收方式（无公网回调） |

---

## 4. 建议顺序

| 步骤 | 内容 | 风险 |
|---|---|---|
| 1（可立即做） | 改 A/B 两行 → 三站 `claude -p` 冒烟 | 极低（纯配置，可一行回滚） |
| 2（已完成） | ✅ 已立 [ADR-0015](../../adr/ADR-0015-飞书远程操作桥接引入.md)：允许**唯一**常驻桥接（cc-connect @ B 站），`Restart=no` + `systemctl disable`，附安全边界 | 无 |
| 3（需凭证） | 建飞书自建应用、装 cc-connect、写 systemd 单元、冒烟 | 中（首次引入外网常驻面） |

---

## 5. 未实测登记

| 项 | 状态 | blocker |
|---|---|---|
| A/B 改 `8731` 后 claude 端到端（含工具调用、多轮） | **todo** | run |
| cc-connect 在本集群（Node 版本 / 长连接 / 与本地 halogen 的流式兼容） | **todo** | run |
| 飞书自建应用的权限最小集与审批交互（按钮回调） | **todo** | external（需飞书应用凭证） |
| 手机端体验（长回答分段、断线重连、thinking 展示） | **todo** | run |
| `open.feishu.cn` 根路径 404 是否影响长连接域名（应走 `open.larksuite.com`） | **boundary** | run |

---

## 6. 来源（E3）

- [cc-connect：把 Claude Code 接入微信和飞书](https://juejin.cn/post/7669024144831234054)
- [手把手教你用飞书远程指挥 Claude Code 干活](https://juejin.cn/post/7631050859780112394)
- [CcConnect 安装与部署方式](http://m.toutiao.com/group/7643725164496060963/)
- [cc-connect 配置示例（feishu / claudecode）](https://juejin.cn/post/7615074940828794899)
- [remote-claude：手机远程指挥 Claude Code](https://blog.csdn.net/zhangyanfei01/article/details/161030062)
- [飞书 CLI 官方](https://www.feishu.cn/feishu-cli)
- [飞书开放平台 MCP 概述](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/mcp_integration/mcp_introduction?lang=zh-CN)
- [Claude Code Remote Control](https://claudecowork.io/claude-code-remote-control)
