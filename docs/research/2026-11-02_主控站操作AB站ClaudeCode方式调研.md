# 主控站操作 A/B 两个工作站 Claude Code 的便捷方式调研

- **日期**: 2026-11-02
- **授权**: 用户 2026-11-02「如果需要再主控站上操作 A B 两个工作站的 claude code 有什么方便的方式 请调研」
- **性质**: **只读调研 + 落档**。未改任何代码 / 配置 / 站上状态
- **证据级别**: **E1** = 本仓读码与既有实测 · **E2** = 官方文档 · **E3** = 第三方
- **射程**: 只回答「主控站用什么方式驱动 A/B 站的 `claude`」；**不**回答「该不该接」「用哪个模型」

---

## 0. 结论前置（五句）

1. ★★ **官方已把「远端 claude」当一等形态**：Claude Code Desktop 有 **SSH 会话**（在远端机器上跑，断开 Desktop 后任务仍可继续）；官方另有 **`claude remote-control`**（在远端起 server，从任意设备接管同一会话）。两者都不是本项目自造。
2. ★★ **本仓已有合规通道**：`agent-cli task -HostName A|B -Cli claude` —— 一次性任务、按卡 `readonly` 动态传权限、证据链落盘。**不建议**在主控直接裸 `ssh A "claude -p ..."`，那会绕过 route / readonly / evidence 三层。
3. ★★ **交互式最省 = `ssh -t A claude`**；要**断线不丢会话**就套 `tmux`（官方 remote-control 文档明确建议在远端把 `claude` 放进 `tmux` 或 `screen`）。
4. ★★ **图形化最省 = Desktop 的 SSH 会话**（能看 diff、断连保活）；但它与 `remote-control` 都可能**依赖 claude.ai 订阅**，本仓走 `apiKeyHelper → OpenRouter + halogen`，该路径是否满足订阅条件**未证**。
5. ★★ **明确不推荐**：`code-server` / `ttyd` / `wetty` —— 新增**入站监听 + 常驻服务**，与 ADR-0004「零自加载 · 无 daemon」直接冲突；也不建议把工作站当「远程 IDE 后端」。

---

## 1. 可选方式盘点

| 方式 | 命令形态（示例） | 交互性 | 断线保活 | 新增常驻面 | 合规判定 | 证据 |
|---|---|---|---|---|---|---|
| **A. 本仓派发** | `agent-cli.ps1 task -Card <卡> -HostName A -Cli claude` | 一次性 | 不涉及 | 无 | ★ **合规首选**（有卡、有 accept、有证据链） | E1 |
| **B. SSH 交互** | `ssh -t A claude` | 交互 | ✗ 断线即丢 | 无 | 合规（人工操作，不产生证据链） | E1 |
| **C. tmux + SSH** | `ssh A "tmux new -d -s cc claude"` 然后 `ssh -t A "tmux attach -t cc"` | 交互 | ✓ | tmux 用户态会话（非开机自启） | ★ **合规**（见 §3） | E2 官方建议 + E3 社区主流 |
| **D. Desktop SSH 会话** | Desktop 配 `SSH Host / Port / Identity File` | 图形 + 交互 | ✓（断开后任务继续） | Desktop 本机应用，站上**不装东西** | 合规；受管环境需 `sshHostAllowlist` | E2 官方 |
| **E. `claude remote-control`** | 远端 `claude remote-control`（在 tmux 内），主控从 claude.ai 接管 | 图形/移动 | ✓（需 tmux 保会话） | 会话级 server（随会话走，非开机自启） | 需评估：**账号依赖**（见 §3） | E2 官方 |
| **F. cc-connect（飞书）** | B 站已部署；A 站未接 | 移动端 | ✓（长连接） | 常驻 `rpc-bridge`（ADR-0015 唯一例外） | B 站合规；**A 站受多实例约束** | E1 + 本轮 IM 调研 |
| **G. code-server / ttyd** | 站上起 web IDE / 终端 | 图形 | ✓ | **入站端口 + 常驻服务** | ✗ 违 ADR-0004，且新增入站面 | E1 判断 |
| **H. 自建 MCP 包装** | 把 `agent-cli task` 暴露为 MCP 工具 | 会话内工具调用 | 不涉及 | 无（stdio MCP） | 合规，但需维护一个 server | E1 判断 |

---

## 2. 按场景的推荐路径

| 场景 | 推荐 | 理由 |
|---|---|---|
| **有卡的一次性任务**（要验收/证据/可复跑） | **A** `agent-cli task` | 唯一带 `readonly` / route / evidence 的通道；失败可追 |
| **手动探索、改代码、多轮对话** | **B** 或 **C** | 零新增面；C 解决断线丢会话 |
| **在主控想边看 diff 边对话** | **D** Desktop SSH 会话 | 官方形态，站上不装东西；需桌面版与账号 |
| **手机/异地接管** | **F**（B 站已通）或 **E** | F 已有现成桥接；E 是官方原生但依赖账号 |
| **多站并行编排** | 主控脚本按站分发（`ops/` 已有形态） | 与 [ClaudeCode 本地集群分析](../2026-09-23_Ds工作区扫描_对agent编排与D7的可借鉴分析.md) 的「形态 A」一致 |
| **想用网页终端** | ✗ 否决 **G** | 入站面 + 常驻，ADR-0004 不允许 |

★ **一句话**：**任务走 A，人在走 B/C，图形走 D**；三者都不新增常驻面，差别只在「要不要证据链」。

---

## 3. 与 ADR 的关系（本仓特有约束）

| 约束 | 对本题的影响 |
|---|---|
| **ADR-0004 零自加载 · 无 daemon** | 排除 G（web IDE/终端）。C 的 tmux 是**用户态、按需启动**的会话进程，不开机自启 ⇒ 不构成 daemon；E 的 `remote-control` 是**会话级** server（随 claude 会话起停），同样不是开机常驻 —— 但它是**官方引入的新常驻形态**，若长期使用应在 ADR-0015 的例外清单里点名 |
| **ADR-0015 唯一常驻例外** | 目前只登记 `rpc-bridge`（cc-connect @ B 站）。A 站接 IM 仍受「同一飞书 app 多实例随机分发」限制（见 [IM 桥接调研](2026-11-02_多站IM桥接实例隔离与备选方案调研.md)） |
| **`readonly` 卡面契约** | 只有 **A** 通道会按卡动态传 `--permission-mode acceptEdits`；B/C/D/E 都是**人工会话**，不读卡面 ⇒ 不存在只读保证。**要只读保证就必须走 A** |
| **证据链** | 只有 A 会落 runDir / `run.json` / verdict；B/C/D/E 的产物留在 `work_dir` 或站上仓库，不进本仓证据面 |
| **D167 worker 固定入口** | A 通道的远端执行已收口到 `_worker_entry.sh`（版本门 + 透传），B/C/D/E 不经过它 ⇒ 版本钉只覆盖 A |

---

## 4. 未实测登记

1. **Desktop SSH 会话在本机版本是否可用**：官方文档确认有该能力，但本机 Claude Code `2.1.258` 的 Desktop 版本、以及是否需要 `sshHostAllowlist` 受管配置，**未验**。
2. **`claude remote-control` 在 halogen 后端下的兼容**：官方称会话跑在本地机器、保留本地 MCP 与配置；本仓 `ANTHROPIC_BASE_URL=127.0.0.1:8731`，remote-control 的账号校验是否接受 `apiKeyHelper` 路径**未证**。
3. **订阅前提**：`/desktop` handoff 官方写明需 claude.ai 订阅；本仓走 OpenRouter 免费档/本地引擎，是否有可用订阅**未核**。
4. **tmux 在 A/B/C 的安装与默认 shell**：社区主流形态，但三站是否已装 `tmux`、`ssh -t` 下中文/宽字符渲染是否正常，**未测**。
5. **A 站 cc-connect 的实例归属**：仍待用户选择「新建独立应用 / 单桥接路由」（见 IM 调研 §3），本轮不动。

---

## 5. 来源

### 本仓（E1）

- [`agent-cli.ps1`](../../ops/station-bin/agent-cli.ps1) 的 `-HostName` / `-Cli` / `task` 命令与 `Invoke-RemoteScript`
- [2026-09-21 D6 备路站上化调研](2026-09-21_D6备路站上化与sensitivity设闸调研与方案.md) §2.1（官方 SSH 一等概念、tmux + ssh 社区主流）
- [ClaudeCode 本地集群与子代理框架分析](../ClaudeCode本地集群与子代理框架分析.md) §2.2/2.3（主控 ssh -t 架构、形态 A/B）
- [2026-11-02 多站 IM 桥接实例隔离调研](2026-11-02_多站IM桥接实例隔离与备选方案调研.md)
- [ADR-0004](../../adr/ADR-0004-统一管理入口为唯一管理面.md) · [ADR-0015](../../adr/ADR-0015-飞书远程操作桥接引入.md)

### 官方文档（E2）

- [Claude Code Desktop application](https://code.claude.com/docs/en/desktop)（SSH 会话：远端机器运行、断开后任务继续）
- [SSH remote sessions in Claude Desktop](https://claude.com/docs/third-party/claude-desktop/ssh-remote-sessions)（`sshHostAllowlist` 受管配置）
- [Continue local sessions with Remote Control](https://code.claude.com/docs/en/remote-control)（`claude remote-control`；远端需 tmux/screen 保会话）
- [Claude Science · Remote compute clusters](https://claude.com/docs/claude-science/remote-compute-clusters)（用现有 `~/.ssh/config`、不在主机装东西）
- [Claude Code in the cloud](https://code.claude.com/docs/en/claude-code-on-the-web)（`--teleport` 把云会话接回终端）
