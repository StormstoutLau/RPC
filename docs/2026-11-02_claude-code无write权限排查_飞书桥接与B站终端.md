# Claude Code「无 write 权限」排查 —— 飞书桥接（cc-connect）与 B 站终端

- **日期**: 2026-11-02
- **授权**: 用户 2026-11-02「先帮我确认 B 站终端的 permissions 配置」→「查一下那次启动的 argv」→「排查飞书 Claude Code 的权限配置」→「先落档」
- **性质**: **只读排查 + 登记**。★ 未改任何代码 / 配置 / ADR / 台账；站上只执行读命令（`cat` / `ps` / `systemctl show` / `journalctl`）
- **证据级别**: **E1** = 本仓读码 · **E2** = 站上只读实测（命令 + 读数）· **E3** = 文档面
- **射程**: 只回答「为什么显示无 write、权限从谁下发、该不该与插件面统一管理」；**不**回答「要不要放开写」「halogen 性能」

---

## 0. 一屏（四句 · 改前快照）

> ★ **2026-11-02 11:33 已按方案乙执行**（放行 `Write` / `Edit` + 重启桥接 + 更新 ADR-0015），详见 §6.1。以下四句描述的是**变更前**的定性。

1. ★★ **飞书的「无 write」不是故障，是配置的直接必然**：cc-connect 拉起的 claude 进程 argv 明写 `--permission-mode dontAsk` + `--allowedTools Read,Grep,Glob,Bash`，白名单里**没有 `Write` / `Edit`**（E2）。
2. ★★ **B 站 `~/.claude/settings.json` 没有 `permissions` 段、没有 `defaultMode`、也没有 `settings.local.json`**（E2，全文 34 行已读）⇒ 交互式走默认模式（写操作弹批准，人能批）；`-p` / 桥接无人可批 ⇒ 拒写。后者与 `O-42` 同源。
3. ★★ **与 halogen 无关**：工具调用在 Claude Code 客户端执行，引擎只做推理；`ANTHROPIC_BASE_URL=127.0.0.1:8731` 只决定模型入口。
4. ★★ **与「插件管理」同族、但不同维度**：`inventory/plugins.yaml` 管「装了什么」（三维在 B 站实测全绿），权限面管「能做什么」—— 后者**没有任何真值条目、没有任何门禁断言**，这才是缺口。

---

## 1. 实测基线（E2，2026-11-02，B 站 `scott-lau@192.168.10.32`）

### 1.1 `~/.claude/settings.json`（926 B · 34 行 · 2026-10-30 15:30）

| 顶层键 | 值 |
|---|---|
| `env` | `ANTHROPIC_BASE_URL=http://127.0.0.1:8731` · `CLAUDE_CODE_MAX_CONTEXT_TOKENS=120000` · `CLAUDE_CODE_MAX_OUTPUT_TOKENS=32000` · `DISABLE_AUTOUPDATER=1` |
| `apiKeyHelper` | `/home/scott-lau/.config/rpc/claude-key.sh` |
| `enabledPlugins` | `superpowers@superpowers-marketplace` · `document-skills@anthropic-skills-local` |
| `extraKnownMarketplaces` | 两个本地目录源（`superpowers-local-marketplace` / `anthropic-skills`） |
| `theme` · `model` · `modelOverrides` | `dark` · `claude-opus-4-6` · 三档同名映射到 `main` |

★ **缺 `permissions` / `permissions.defaultMode` / `permissions.deny`**；`ls settings*.json` 仅此一个文件 ⇒ **无 `settings.local.json` 覆盖**。

### 1.2 `~/.cc-connect/config.toml`（710 B · 权限相关行 · **改前快照**）

```toml
[projects.agent.options]
work_dir = "/home/scott-lau/work"
mode = "dontAsk"
allowed_tools = ["Read", "Grep", "Glob", "Bash"]
disallowed_tools = ["WebSearch", "WebFetch"]
```

`allow_from = "ou_17cc1056823c006560df8095ca6c1bc7"`（本人）· `admin_from` **未设**。

### 1.3 运行时 argv（**改前** · pid 1561395 · 2026-10-30 17:22:14 启动）

```text
claude --output-format stream-json --input-format stream-json
       --permission-prompt-tool stdio --replay-user-messages --verbose
       --permission-mode dontAsk
       --allowedTools Read,Grep,Glob,Bash
       --disallowedTools WebSearch,WebFetch
       --append-system-prompt-file /home/scott-lau/.cc-connect/agent-prompts/cc-connect-system.md
```

★ 配置、unit、运行时 argv **三层逐字一致，无 override**。

### 1.4 进程与边界

| 项 | 实测值 | 判定 |
|---|---|---|
| `claude` 来源 | `/usr/local/bin/claude` | 无别名 / 无 wrapper；`.bashrc` / `.profile` / `.bash_aliases` 无定义 |
| claude 版本 | `2.1.258` | 与 `plugins.yaml` 的 `cli.claude` 期望一致 |
| 桥接服务 | `rpc-bridge` `ActiveState=active` · `UnitFileState=disabled` · `Restart=no` · `User=scott-lau` · `WantedBy=`（空） | 符合 ADR-0015 的「手工起、不自启」 |
| `work_dir` | `/home/scott-lau/work` · 属主 `scott-lau` · 可写 | 硬边界成立，且**不含**仓库生产目录 |
| 监听面 | 仅出站长连接（ADR 记录；本次未复测） | 见 §7 未实测 |
| 日志 | 无权限拒绝/错误；唯一权限相关条目 = `admin_from is not set — privileged commands blocked` | 符合 ADR 设计 |

---

## 2. 归因链：三个「不是」，一个「是」

| 候选根因 | 判定 | 依据 |
|---|---|---|
| halogen 引擎 | **不是** | 工具由客户端执行；引擎只回模型 token。`8731` 只决定模型入口 |
| `settings.json` 权限模式 | **不是** | 该文件无 `permissions` / `defaultMode`（§1.1）⇒ 它不可能造成桥接会话的拒写 |
| claude 版本 / 认证 | **不是** | `2.1.258` 正常；桥接端到端有 `turn complete` 记录 |
| **cc-connect 的 argv** | ★ **是** | `--permission-mode dontAsk` + 白名单不含 `Write`/`Edit`（§1.2 / §1.3） |

---

## 3. 三条通道的权限来源（不可用同一把尺子）

| 通道 | 权限由谁决定 | 现役值 | 期望行为 |
|---|---|---|---|
| `agent-cli.ps1` 的 `-p` | RPC 代码，按卡 `readonly` 动态 | writable 卡 `--permission-mode acceptEdits`；readonly 卡空串 | 产物卡**可写**、只读卡**不可写**（`O-42` 已修） |
| 终端交互式 `claude` | `~/.claude/settings.json` | **未设** ⇒ 默认模式 | 写操作**弹批准**，人在机前可批 |
| 飞书（cc-connect） | `config.toml` → 运行时 argv | `dontAsk` + 4 个只读工具 | **刻意只读**（ADR-0015 §3） |

---

## 4. 与 ADR-0015 §3 边界逐条对账

| 边界 | 要求 | 实测 | 判定 |
|---|---|---|---|
| 工作目录 | 单一 `work_dir`，不含生产目录 | `/home/scott-lau/work`，可写 | PASS |
| 飞书身份 | 仅白名单 user/群 | `allow_from` = 本人 | PASS（非白名单丢弃**未验**） |
| 应用权限 | `im:message` 收 + `im:message:send_as_bot` 回 | 无法从 CLI 读（开发者后台） | 未证，见 §7 |
| 工具权限 | `--allowedTools` 白名单，高危不放开 | `Read,Grep,Glob,Bash`，无 `Write`/`Edit` | PASS（**只读是预期**） |
| 特权命令 | 不放开 | `admin_from` 未设，五个命令全禁 | PASS |
| 进程身份 | 非 root | `User=scott-lau` | PASS |
| 网络面 | 仅出站、不新增监听 | ADR 记录，本次未复测 | 未证，见 §7 |
| 审计 | journald 三段 | `message received` / `audit: command_executed` / `turn complete` | PASS |

---

## 5. 与「agent 运行面真值」的关系

`inventory/plugins.yaml` 自述职责是「插件/技能面的三站同构基线」，采集口径只有三维：

| 维度 | 现有 item | B 站实测 | 对账 |
|---|---|---|---|
| 版本 | `cli.claude` = `2.1.258` | `2.1.258` | 一致 |
| 插件集合 | `claude.plugins` / `claude.enabled` / `claude.mkt` | 两项插件、两个源 | 一致 |
| 技能数 | `claude.skills.n` / `claude.skills.names` | 本次未采 | 未测 |

**缺口 = 第四维「权限面」**：`defaultMode` / `permissions.allow.n` / `permissions.deny.n` / 桥接的 `permission_mode` 与 `allowed_tools` 均无条目，也无断言。⇒ 「无 write」只能靠人读配置发现，门禁看不见。

★ 采集口径的关键修正：**桥接权限应以运行时 argv 复算，而不是读 `config.toml`** —— 配置改了但进程未重启时，argv 才是事实（本次实测已证明两者当前一致，但该一致性本身也应成为判据）。

---

## 6. 候选处置（乙已执行，甲丙仅存档）

| 方案 | 内容 | 代价 | 判定 |
|---|---|---|---|
| **甲** | 维持只读：把「飞书只读」写成 `permissions` 维的**期望值**，并在 ADR-0015 §5.1 补一句「无 `Write`/`Edit` 是预期，不是缺陷」 | 零配置改动 | 原建议，**未采纳**（用户 2026-11-02 选乙） |
| **乙（已执行）** | 放开写：`allowed_tools` 增加 `Write` / `Edit`，重启桥接，并同步改 ADR-0015 §3 / §5.1 / §6 | 站上改动 + ADR 改动 + 手机端变为可写 | ★ **2026-11-02 11:33 已执行**，见 §6.1；`work_dir` 硬边界仍兜底 |
| 丙 | 改 `bypassPermissions` 或加 `--dangerously-skip-permissions` | — | ✗ **否决**：ADR-0015 D6 明令禁止 |

无论甲乙，**都不应**用「换引擎 / 改 halogen / 改 settings」来修 —— 三者与写权限无因果。

### 6.1 执行记录（2026-11-02 11:33，方案乙）

| 步 | 动作 | 结果 |
|---|---|---|
| 1 | 备份 `config.toml` → `config.toml.bak-20261102` | 成功（E2） |
| 2 | `allowed_tools` 追加 `Write` / `Edit` | 成功，第 16 行为 `["Read", "Grep", "Glob", "Bash", "Write", "Edit"]` |
| 3 | `sudo systemctl restart rpc-bridge` | `active`；`config loaded` 无错误；`MainPID=1788520`；飞书长连接重建 |
| 4 | 运行时 argv | ✅ **已验**（16:32:03，pid 1804784：`--allowedTools Read,Grep,Glob,Bash,Write,Edit`） |
| 5 | ADR-0015 §3 工具权限行 / §5.1 工具档位 / §6 未实测 | 已更新（§3 同时更正「白名单判据在 `config.toml`，不在 unit 的 `ExecStart`」） |
| 6 | 真实写文件 | ✅ **已验**（16:33:59 产出 `work/trae-cn-uninstall-record.md` 23,275 B；16:34:47 `turn complete tools=3` · `turn_duration=2m42.7s`；无 `denied` / `error`） |

★ **安全性论证（写进 ADR 的理由）**：`Bash` 原本就在白名单 ⇒ 变更前的「只读」只是**名义只读**（`cat > file` / `tee` 已可写任意可写路径）。放开 `Write` / `Edit` 不扩大实质能力面，只是把写变成**结构化、可被权限面区分与审计**的动作；实质边界仍是 `work_dir` + 非 root + 身份白名单。

---

## 7. 未实测登记

1. **终端交互式那次的 argv 不可复查**：`~/.bash_history` 仅记裸 `claude`（无参数），进程已退出；若当时确实报「无 write」，其启动参数无法还原。
2. **非白名单账号消息丢弃未验**（ADR-0015 §5「上线前」第 2 项）：无第二个飞书账号可自造，状态 `external`。
3. **飞书开发者后台的应用权限未从 CLI 读**：`im:message` / `im:message:send_as_bot` 的实际授予集需在后台核对。
4. **监听面未复测**：仅引用 ADR-0015 §5.1 的 `ss -ltnp` 记录（本次未重跑）。
5. **`slow agent send` 达 4m54s**（11-02 02:09，`response_len=24151`）：与权限无关，疑属 `O-180` / `O-183` 的长上下文 prefill 同族；未做上下文规模与被测时段的对照。
6. ~~放开 `Write` / `Edit` 后的运行时 argv 未核~~ → ✅ **2026-11-02 16:32–16:34 已闭环**：argv 含 `Write,Edit`；真实任务产物 `trae-cn-uninstall-record.md`（23,275 B）落于 `work_dir`。

---

## 8. 与既有文档的关系

| 文档 | 关系 |
|---|---|
| [ADR-0015 飞书远程操作桥接引入](../adr/ADR-0015-飞书远程操作桥接引入.md) | 边界真值；本稿只对账，**不改**其裁定 |
| [O-42](../spec/d6-agent-standard/OPEN-ISSUES.md) | `-p` 无写权限的**已修**先例（按 `readonly` 动态传 `acceptEdits`）；本稿的桥接通道是它的**第三方驱动变体**（argv 不由本仓拼） |
| [2026-10-30 三站 claude 接 halogen + 飞书调研](research/2026-10-30_claude-code三站halogen接入与飞书远程操作调研.md) | 通道背景（8731 寻址、cc-connect 选型）；**该文未涉及权限面**，本稿补这一维 |
| [inventory/plugins.yaml](../inventory/plugins.yaml) | 三维真值；本稿指出**第四维缺失** |
| [O-180](../spec/d6-agent-standard/OPEN-ISSUES.md) / [O-183](../spec/d6-agent-standard/OPEN-ISSUES.md) | 长上下文 prefill 同族（`slow agent send` 的可能来源，未归因） |

---

## 9. 长会话清理与桥接重启（2026-11-03 执行）

### 9.1 对象

B 站 `pid 1804784` —— 桥接用 `--resume 48915591-…` 保活的 claude 进程：

| 项 | 读数 |
|---|---|
| 形态 | `ppid 1788543`（cc-connect）· 状态 `Sl` · RSS **249 MB** |
| 进程龄 | **1 天 5 时 8 分** |
| 近 3 小时桥接日志 | **无任何条目**（无在途回合） |
| session 落盘 | 存在：`~/.claude/projects/-home-scott-lau-work/48915591-….jsonl` |

### 9.2 判定：可清理，上下文不丢

1. **transcript 已落盘** ⇒ 杀进程只丢内存态，`--resume` 可从 jsonl 重建对话。
2. **无在途工作** ⇒ 空闲而非死锁（`Sl` 态、CPU 累计仅分钟级）。
3. 它是**保活机制**不是 bug：手机端多轮对话共享上下文依赖 `--resume`。

### 9.3 执行（方式 A = 重启桥接）

```bash
sudo -n systemctl restart rpc-bridge
```

| 项 | 结果 |
|---|---|
| 服务 | `active`（新 pid 2258494） |
| 旧进程 1804784 | **已消失** |
| 新 claude | **未拉起**（按需：收到消息才 spawn） |
| 飞书连接 | `platform ready` + `wss://msg-frontier.feishu.cn` 已连 |
| 启动日志 | `reset_on_idle_mins not set, applying default … default_minutes=0` |

### 9.4 结构性成因（本次新发现）

启动日志逐字写着 **`reset_on_idle_mins` 未设 ⇒ 默认 `0`**。`0` = **空闲会话不回收**，所以桥接拉起的会话会一直常驻（本次实测 27 h+、249 MB）。

⇒ 若要字段级根治「空闲会话占内存」，需把 `reset_on_idle_mins` 设为非 0（如 60）。**代价**：超过该时长的会话被重置，`--resume` 的上下文保活随之失效（手机端多轮对话将从新会话开始）。**该取舍本次未做，仅登记。**

### 9.5 与门禁 `stations` 的关系

`stations` 的「长龄 orphan」判据把 `claude|opencode|timeout|defunct` 且 ≥6 h 一律报出 —— **合法的保活会话与真孤儿同形**（同一判据）。本次清理后 A/C 站 orphan 归零、B 站只剩这一个（随后随重启清除）。按 `ppid=cc-connect` 收窄判据属门禁射程改动，**未做**。
