# `dogfood-cards/` —— 吃狗粮卡面专用目录

> **建立：2026-09-24（Scott 裁定）** · **本目录 tier = `public`**（登记于 `inventory/sensitivity.yaml`）

## 为什么单独建这个目录

`test-cards/`（历史卡区）在真值表里是 **`local-only`**，理由是其卡面**含 proj 路径 / 站标识 / 站上落点**。
而**卡正文会进 prompt**（一手实测：`prompt.txt` = `[proj:x]` + task 行 + **正文全文**），
⇒ 一张"声明 `public` 却走 `test-cards/` 旧卡面"的卡，**本身就带着 C3 指纹出网**（实测 `01a` 卡正文写了
`ls -1 /home/scott-lau/agent-workspaces`，随 openrouter 请求原样发出）。

⇒ 把**干净卡面**与旧卡区物理分开：**本目录下的卡，本体即可出网**。

## 写卡纪律（从一手取证得出，不是风格偏好）

| # | 纪律 | 依据（一手） |
|---|---|---|
| 1 | **正文禁写"本项目/站点的身份与拓扑"** —— 站 IP · 站点主机名（`*.local`）· **工作站用户名** · 本仓路径（`D:\RPC\...`）· 站上用户目录（`~<user>/...`） | 正文进 prompt；而 scrubber **刻意不含** IP/主机名/Linux 路径/用户名（`Get-ScrubRules` 注释：那类的正确防线是**档位**，不是正则） |
| 1b | ⚠ **精度限定（2026-09-24 自我修正）**：**通用 OS 路径不受此限** —— `/sys/class/drm` · `/proc/meminfo` · `/usr/bin/free` 这类"任何 Linux 都一样"的路径**不构成本项目披露**（依据 = 那份裁定的判据轴②"**是否构成新披露**"）。禁的是**带本项目身份**的绝对路径 | 同上的裁定 §1 |
| 2 | **`accept` 用相对路径**（`test -f out/x.json`），**不要**写 `cd /home/...` | [`agent-cli.ps1:1772`](../../../ops/station-bin/agent-cli.ps1) 执行前已 `( cd "$W" && eval "$c" )` ⇒ 绝对 `cd` 是冗余 |
| 3 | **带附件的出网卡必须写 `attach-egress: ok`** | `Get-AttachEgressReject`：有附件 ∧ 后端出网 ∧ 未声明 ⇒ **`REJECT … exit 4` 整单拒**（不是丢附件） |
| 4 | **附件内容不经 scrubber** ⇒ 附件必须本身是 `public` 档 | 附件走 `scp` 原文；scrubber 只改 `$promptFull`（含附件**文件名**，不含内容） |
| 5 | **要脱敏就别用附件** —— 受限输入应**内嵌进卡正文**（只在正文会过 scrub） | 同上 |
| 6 | 声明 `public`/`sanitized` **且带输入**时，**逐项写 `input-provenance`**，每项须在 `sensitivity.yaml` 有 `tier`，且**卡档位不得宽于该项** | `CROSS-PROJECT-WORK-STANDARD §4`；⚠ **该义务目前未被机判**（2026-09-24 全仓核对：`input-provenance` 在 `ops/` 下**零命中**） |
| 7 | ★ **卡的射程 = 平台注册的工作区根**（实测 `~/agent-workspaces` **可读**）—— 该根**之外**的站上路径（`~/scripts`、`/proc`、系统目录）**不要指示模型去读** | **一手实测（2026-09-24）+ 一次自我修正**：A2 首跑的 `cd ~/scripts …` 被 `permission requested: external_directory (/home/scott-lau/scripts/*); auto-rejecting` 拒（= O-30 第一条第二实例，`TASK_RC=9`）；**但同一批 A1 的 `ls -1 ~/agent-workspaces` 成功**（工作区**根**可读）⇒ 边界**不是**"工作区内/外"，而是**白名单**（含工作区根；`~/scripts`、`/proc` 均不在）。⇒ 工作区根之外的取证**由主控 ssh 直接做**；agent 可安全依赖的是**可执行命令**（`infer-list`/`free -m`/`ss -ltn`/`hostname` —— A1 正是靠这些成功）。⚠ **白名单的确切边界未定**（`~/.config/opencode/` 下**无显式 `permission` 配置** ⇒ 走默认；待查 opencode 默认规则） |

### ★ 站上环境的五条硬约束（2026-09-24 入册；纪律 8/9/10 = O-30，纪律 11 = O-48，纪律 12 = O-58；均**实测**得出）

| # | 约束 | 依据（一手） | 写卡时怎么用 |
|---|---|---|---|
| **8** | **站上 agent 对 `/proc/*` 无读权限**（`permission requested: external_directory (/proc/*); auto-rejecting`） | A1 首跑实测：读 `/proc/meminfo` 的采集**全部不可行**；改 `free -m` 即成功 | 内存类采集**一律用 `free -m`**，**不要**指示模型读 `/proc/*` |
| **9** | **站上无 `nvidia-smi`**（三站是 **AMD UMA** 机型） | A1 首跑实测 `nvidia-smi: command not found`（rc=127） | GPU 采集走**回退链**：`rocm-smi` → `/sys/class/drm`；**不要**把 `nvidia-smi` 当硬依赖 |
| **10** | **`readonly: true` 与"必须落文件"互斥** | A1 首次实测：模型跑了 6 条命令、数据齐全，**但始终没写文件** ⇒ 只读卡的产物**永不落盘** | **要产物就必须 `readonly: false`**；只读只用于"纯输出型"卡 |
| **11** | ★ **站上限时一律 `timeout -k <grace> <dur>`**（裸 `timeout` **不算限时**）—— 裸 `timeout` 对**忽略 SIGTERM** 的子进程会**一直等**，不是"到点即杀" | **受控复现（B 站，2026-09-24）**：`timeout 2 bash -c 'trap "" TERM; sleep 6'` ⇒ rc=124 但**耗时 6s**；同命令加 `-k 1` ⇒ rc=137 **3s**。⇒ B 站曾有诊断进程活 **17.2h**（O-48） | **卡里 / 诊断 / 任何 ssh 到站上的限时命令**都写 `timeout -k 10 <秒> …`；⚠ 加 `-k` 后 KILL 生效时退出码是 **137**（非 124）⇒ 判"超时"须认 124 **和** 137 |

| **12** | ★ **ssh 传参必须防"远端 shell 二次解析"**：交替/管道类模式写成 `grep -E a\|b` 而**不加引号** ⇒ 远端把 `\|` 当**管道** ⇒ 拆出的词当命令跑，甚至**起一个裸 `opencode` TUI**（交互式、无 `-p`、无 EOF）⇒ `epoll_wait` **永不返回** | **一手实测（B 站，2026-09-25）**：站上留 **2 条**孤儿 —— `bash` 1-12:19（`do_wait`，子进程 `grep -icE error` 卡死）· `bash`+**`opencode`** **1-04:59**（`ep_poll`；47 fd，持 `opencode.db` **180MB** + wal/shm + `memory.db` + 两个 `opencode.log` 写 fd ⇒ 给同站共享 DB 的 run 加了一个**不明写者**）。⚠ 另含**作者本人当天踩的温和版**：`grep -e "[o]pencode run"` 经 PS 5.1→ssh 被**剥掉内层引号** ⇒ 远端报 `grep: run: 没有那个文件或目录` | 交替一律用**多枚免空格的 `-e`**（`grep -e A -e B`）；要整体加引号就**必须确认引号活到远端**（PS 5.1 会剥内层引号 ⇒ **优先前者**）；且**任何** ssh 到站上的一次性诊断命令都须被 `timeout -k 10 <秒>` **整体**包住（纪律 11）。⇒ 归因：**这不是 `timeout` 语义问题，O-48 的修法盖不住它**（本类来自**探针**，非派发链 4 处）。<br>★ **同日再踩两坑（同族）**：(a) **`pkill -f <模式>` 会自匹配携带该模式的 ssh 命令行** ⇒ 把整条会话连同**后续命令**一起杀掉（实测：后面的 `rm -rf` 没跑成、白留一个临时目录）⇒ 清进程请用 **pid**，或先用 `pgrep` 的 `[x]` 括号技巧核对；(b) 目标路径**可能已经是目录**（实测 `/tmp/opencode` 是既有目录）⇒ `ln -sf` / `cp` 会落进它**里面**而不是替换它 ⇒ 造探针请用**自建子目录** |

⇒ 这五条与纪律 7（**卡的射程 = 平台注册的工作区根**）是**同一族**：**站上沙箱的边界不靠读卡面猜，靠实测登记**。

## 档位选择的正确顺序（`sensitivity.yaml` 的用法）

1. **先查输入**在真值表里的 `tier`（**未登记 = `local-only`**，fail-closed）；
2. 若输入**含 C1/C2**（未发表研究 / 他方未发表）⇒ **只能 `local-only`**（站内模型）；
3. 若输入的**唯一**敏感项是**凭据类**（且有固定格式前缀）⇒ 可用 `sanitized`（scrubber 会抹）；
4. 若输入**已不含 C1/C2/C3**（人工剔除后）⇒ 用 `public`，**保护来自"输入准备"，不来自档位**；
5. ⚠ **含 C3（IP/主机名/Linux 路径/用户名）的内容，`sanitized` 不提供保护** —— 不许靠它兜底。

## 当前批次（2026-09-24 起草 · **5 张卡已全部跑完**）

| 批 | 卡（本目录） | 输入 | 档位 / 开关 | 站上引擎？ |
|---|---|---|---|---|
| A | [a1-station-reality.md](a1-station-reality.md) | 无 | `public` | ✗（出网档） |
| A | [a2-station-scripts-drift.md](a2-station-scripts-drift.md) | 无（比对在主控做） | `public` | ✗ |
| B | [b1b-u2-dialect-map-analyze.md](b1b-u2-dialect-map-analyze.md) | [inputs/d7-dialect-excerpt.md](inputs/d7-dialect-excerpt.md)（**人工脱敏摘要**） | `public` + **`attach-egress: ok`** | ✗ |
| B | [b1a-u2-dialect-map-transcribe.md](b1a-u2-dialect-map-transcribe.md) | 全文 §11.1（附件） | `local-only`（站内） | ✓（站上 `m27-q4ks`） |
| B | [b2-gate-falsegreen-audit.md](b2-gate-falsegreen-audit.md) | `ops/rpc_check.py`（附件，已登记 `public`） | `public` + **`attach-egress: ok`** | ✗ |
| （烟测） | [smoke-claude-channel.md](smoke-claude-channel.md) | 无 | `public`（`cli: claude` 主控本地） | ✗ |
| （负向夹具） | [neg-o46-cleanup.md](neg-o46-cleanup.md) | 无 | `public`（**accept 故意必红** ⇒ 验 O-46② 清理） | ✗ |

⇒ **除 B1a 外都不需要站上引擎**（`opencode` 卡走 `model: ultra` = `openrouter/*` 出网档；烟测卡走 `cli: claude` 主控本地）。
> ✅ **B1 = 双卡两层，已裁**（[DEV-LOG-014](../../../docs/DEV-LOG-014-decision-refinement.md) D1）：**`b1a` = 转录底稿层**（只转录原文、站内、求真）· **`b1b` = 分析提案层**（含"统一字典候选轴"、出网、求用）。
> 二者是**不同层**、都属 U-2「建映射、不迁移权威源」的必需件 ⇒ **并存**（原「同一事实两处定义」的同名混淆已由改名消除）。

### ★ 本轮实测最终状态（2026-09-24 收口 · **全部跑完**）

| 卡 | 结果 | run | 通道 / 模型 | RUN_S |
|---|---|---|---|---|
| **A1** | ✅ `exit=0` | `202609241022501982` | opencode / `ultra`（出网） | 92 |
| **A2**（v2 重设计） | ✅ `exit=0` | `202609241101555466` | opencode / `ultra`（出网） | 36 |
| **B1a**（转录底稿） | ✅ `exit=0` | `202609241113114359` | opencode / `local/m27-q4ks`（**站内**） | 174 |
| **B2** | ✅ `exit=0` | `202609241608498832` | opencode / `ultra`（出网） | 581 |
| **smoke-claude** | ✅ `exit=0`（`ACCEPT_OK=1`） | `202609241047036207` | claude / `thinkingmachines/inkling:free` | 18 |

- **A1**：首跑 117s（`202609240057242849`）；其后为修 O-37 `t=0` 残留改卡并复跑 ⇒ 上表 92s 为**当前卡版**结果。
- **A2**：首跑 ❌ **设计错误**（读工作区外的 `~/scripts` ⇒ `external_directory` **auto-reject**，O-30 第二实例）；v2 重设计后 ✅。
- **B2**：唯一真实成功是**第 6 次**（前 5 次被上游 503/504 打断，见 O-46）；且**用 D6 派发链抓到了门禁自己的假绿**（O-41）。
- **smoke-claude**：首跑 ❌（`-p` 无写权限 ⇒ O-42）；加 `--permission-mode acceptEdits`（按卡 `readonly` 动态）后 ✅。

### ⚠ 派发前必读：出网档的**落站事实**（2026-09-24 一手读 `ROUTE_TABLE`；**09-24 晚 P2-3 已扩**）

- `opencode` 通道的出网档 **`lightning` / `ultra` / `free-1m` 默认 `station = 'B'`**；
- ★ **`ultra-a`（A 站）· `ultra-c`（C 站）已加**（[DEV-LOG-014](../../../docs/DEV-LOG-014-decision-refinement.md) D3 / P2-3）——
  与 `m27-q4ks-a/-b` **同构**（同一 id、不同 station）⇒ **可跨站错开**，不再"只能串行"。
  **前提核查（实测已过）**：三站 `opencode` 1.18.25 一致 · `opencode.jsonc` **md5 全一致** · `openrouter.key` **三站各异**（独立账户 ⇒ **限流互不干扰**）。
  ```powershell
  & ops/station-bin/agent-cli.ps1 task dogfood -Card "<卡>.md" -Model ultra-a   # 钉 A 站
  & ops/station-bin/agent-cli.ps1 task dogfood -Card "<卡>.md" -Model ultra-c   # 钉 C 站
  ```
- **同站叠并发对"出网卡"是否适用 O-18（~2.8×）—— 未实测**：O-18 是**本地引擎推理**的带宽现象；出网卡**无本地推理**，
  且实测 run 里 `slot.gated = false`（slot gate 只对本地引擎通道生效）。⇒ **技术上无闸拦**，但**属未验证假设** ⇒ 首轮建议先 **2 张并行**取证。
- 另一条**不改代码**就能错开的路：`cli: claude` 的备路在**主控本地**执行（`station = ''`），走同一 openrouter ⇒ 可与 B 站卡真并行（代价：执行器不同）。
- openrouter 侧上限 = **20 请求/分/账户**；三站密钥文件**各异**（实测 md5 三个值）⇒ **视为三账户独立配额**，跨站并行不互相挤占 ✓。

### 派发形态

```powershell
# ⚠ 直接用 PowerShell 调用时参数名是 `-Card` / `-Attach`（不是用法文本里的 `--card`；
#   `--` 形式会被当成位置参数 ⇒ "A positional parameter cannot be found that accepts argument '--card'"）
& ops/station-bin/agent-cli.ps1 task dogfood -Card "spec/d6-agent-standard/dogfood-cards/<卡>.md"
# B1 / B2 另需 -Attach（卡里已写 attach-egress: ok）:
& ops/station-bin/agent-cli.ps1 task dogfood -Card "...\b2-gate-falsegreen-audit.md" -Attach "ops/rpc_check.py"
```

### ⚠⚠ 并发纪律（2026-09-24 派发时实测修正）

| 约束 | 事实 | 后果 |
|---|---|---|
| **同站同 proj 有互斥锁** | `LOCK_ACQUIRED … mode=exclusive`（per-`(proj,站)`） | **同站**两张卡不能并行 ⇒ 第二张撞 `LOCK_HELD`（2026-09-24 **实测复现**，见下） |
| **出网档默认落 B 站** | `lightning`/`ultra`/`free-1m` 全 `station='B'`；**已加 `ultra-a`/`ultra-c`** | **可跨站错开** ⇒ 不再"只能串行"（P2-3 已落地） |

**★ 并发正反注入（2026-09-24 实测，D3/P2-3）**：

| 用例 | 配置 | 实测 |
|---|---|---|
| **正**（跨站并行） | 同刻派 `ultra-a`(A) + `ultra`(B) | ✅ **双 `LOCK_ACQUIRED`**（pid `2772113` / `3105818`）⇒ **无互撞** |
| **反**（同站仍串行） | 同刻派两张 `ultra`(同 B) | ✅ 第二张 **`LOCK_HELD owner_pid=3107489`** + `excode=3` ⇒ **锁未被削弱** |

⇒ 现在三条路都可用：① **跨站错开**（`ultra-a`/`ultra-c`，**首选**，同执行器同模型）；
② 同站串行（默认，无需动作）；③ 主控本地 `cli: claude` 备路并行（**代价：执行器不同**，结论可比性下降）。

### ★ 首轮派发已实测的两点（2026-09-24）

- **A1 ✅ 通过**：`ACCEPT_OK=1 / TASK_RC=0 / RUN_S=117`，产物 `out/station-reality.json` 合格且诚实
  （`nvidia-smi`/`rocm-smi` 均 127 ⇒ 回退链落到 `/sys/class/drm`，两条失败**如实**记进 `probe_errors`）。
- ★ **产物不在 run 目录**：卡的产物只落在**站上工作区**（`~/agent-workspaces/dogfood/out/`），主控 run 目录
  只收 `agent-output.txt` 等固定证据件，`workspace-diff.txt` 为**空**（`WORKSPACE_DIFF_LINES=0`）
  ⇒ **要拿产物必须另行回收**，或按 ADR-0007 在卡里声明 `evidence-manifest.subjects`。

> ⚠ **B1b（出网/分析层）的档位 = `public` + 摘要**（Scott 2026-09-24）：不走 `sanitized`。
> 理由：`sanitized` 对 C3 类不提供保护（见 `inventory/sensitivity.yaml` 表头），保护必须前移到**输入准备**这一步。
> （**B1a/转录层**读含研究内容的全文 ⇒ 必须 `local-only` + 站内，与本条不冲突。）

### ✅ 已裁：B1 = 双卡两层（原「同名两处定义」已消除）

| 层 | 卡 | 档位 | 产物性质 | 状态 |
|---|---|---|---|---|
| **转录底稿** | [b1a-u2-dialect-map-transcribe.md](b1a-u2-dialect-map-transcribe.md) | `local-only`（站内 `m27-q4ks`） | 三列转录：符号｜出处｜含义（**禁改写/禁脑补**） | ✅ run `202609241113114359` |
| **分析提案** | [b1b-u2-dialect-map-analyze.md](b1b-u2-dialect-map-analyze.md) | `public` + **`attach-egress: ok`**（出网） | 四节分析（含**统一字典候选轴**） | ⏳ 未跑 |

⇒ **裁定（[DEV-LOG-014](../../../docs/DEV-LOG-014-decision-refinement.md) D1）：两张都留** —— 二者是**不同层**（底稿求真 / 分析求用），删任何一个都丢真信息；
**改名（`b1a`/`b1b`）已消除原「同名两处定义」的混淆**。
> ⚠ 二者产物同名（均 `out/dialect-map.md`）：**不建议在同一 workspace 连跑**（后者覆盖前者）。
> 各自 run 的产物由 collect 段白名单**拉回各自 runDir**（O-40），故**证据不互相污染**；如需并跑，可将 `b1b` 的产物名改为 `out/dialect-map-analysis.md`。
