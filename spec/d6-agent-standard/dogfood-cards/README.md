# `dogfood-cards/` —— 吃狗粮卡面专用目录

> **建立：2026-09-24（Scott 裁定）** · **本目录 tier = `public`**（登记于 `inventory/sensitivity.yaml`）
>
> ⚠ **本 README 的 C3 内容已脱敏（2026-09-26，O-82 方案 A）**：按 `sensitivity.yaml` 表头的**出站口径裁定**
> （"唯一需脱密的是私有 API 凭据 / IP / **用户信息**"），把**站上用户名与绝对路径**换成占位符
> ⇒ **具体指纹不留、事实与教训一字不改**。
> ★ 起因是一手证据：站上 agent **读到本文件**并把里面的用户名抄进了产物（而**同一张卡的正文**明写"不得引入用户名"）
> ⇒ 证明"不要探索目录"在站上是**软约束**。详见 `spec/d6-agent-standard/OPEN-ISSUES.md` 的 **O-82**。

## 为什么单独建这个目录

`test-cards/`（历史卡区）在真值表里是 **`local-only`**，理由是其卡面**含 proj 路径 / 站标识 / 站上落点**。
而**卡正文会进 prompt**（一手实测：`prompt.txt` = `[proj:x]` + task 行 + **正文全文**），
⇒ 一张"声明 `public` 却走 `test-cards/` 旧卡面"的卡，**本身就带着 C3 指纹出网**（实测 `01a` 卡正文写了
**站上用户目录下的一个绝对路径** ⇒ 随 openrouter 请求原样发出）。

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
| 7 | ★ **卡的射程 = 平台注册的工作区根**（实测 `~/agent-workspaces` **可读**）—— 该根**之外**的站上路径（`~/scripts`、`/proc`、系统目录）**不要指示模型去读** | **一手实测（2026-09-24）+ 一次自我修正**：A2 首跑的 `cd ~/scripts …` 被 `permission requested: external_directory (~/scripts/*); auto-rejecting` 拒（= O-30 第一条第二实例，`TASK_RC=9`）；**但同一批 A1 的 `ls -1 ~/agent-workspaces` 成功**（工作区**根**可读）⇒ 边界**不是**"工作区内/外"，而是**白名单**（含工作区根；`~/scripts`、`/proc` 均不在）。⇒ 工作区根之外的取证**由主控 ssh 直接做**；agent 可安全依赖的是**可执行命令**（`infer-list`/`free -m`/`ss -ltn`/`hostname` —— A1 正是靠这些成功）。⚠ **白名单的确切边界未定**（`~/.config/opencode/` 下**无显式 `permission` 配置** ⇒ 走默认；待查 opencode 默认规则） |
| **7b** | ★★ **精度更正（2026-09-25 实测）—— 射程【不是"根"，而是"自己的 proj 目录"】**：根**只可列一层名字**（`ls -1 ..` **成功**），但**根下任何兄弟 proj 的子树【不可进】** | **一手实测（a3 首跑，2026-09-25）**：`ls -1 ..` ⇒ 成功列出**同级目录名**（含本项目在内共 4 个）；但它随后对其中一个兄弟 proj 依次试 `find` / `du -sk` / `stat` / `ls -1A` / `wc` ⇒ **5 条全部**被 `permission requested: external_directory (~/agent-workspaces/*); auto-rejecting` 拒 ⇒ **产物未生成** ⇒ `TASK_RC=9` / `ACCEPT_OK=0` / `COLLECT_FAIL`。<br>⚠ **与纪律 7 的差别（为什么必须改口径）**：7 说"射程 = 根"，读起来像"根以下均可读" ⇒ **a3 正是按这个理解写的，然后失败了**。| **只采自己的工作目录**（`$W`）。**不要**去 enumerate 兄弟 proj。若确需根层信息，只做 `ls -1 ..` 拿名字，**且别把它写进产物**（产物的兄弟目录名会随归档落盘 ⇒ 属他方项目名的**新披露面**）。★ **另加一条写卡纪律**：卡要**先写一个合格的空骨架产物、再逐项填** ⇒ 中途被拒也留得下产物（a3 v1 的产物**完全没生成**，正因为没这个顺序）。 |

### ★ 站上环境的五条硬约束（2026-09-24 入册；纪律 8/9/10 = O-30，纪律 11 = O-48，纪律 12 = O-58；均**实测**得出）

| # | 约束 | 依据（一手） | 写卡时怎么用 |
|---|---|---|---|
| **8** | **站上 agent 对 `/proc/*` 无读权限**（`permission requested: external_directory (/proc/*); auto-rejecting`） | A1 首跑实测：读 `/proc/meminfo` 的采集**全部不可行**；改 `free -m` 即成功 | 内存类采集**一律用 `free -m`**，**不要**指示模型读 `/proc/*` |
| **9** | **站上无 `nvidia-smi`**（三站是 **AMD UMA** 机型） | A1 首跑实测 `nvidia-smi: command not found`（rc=127） | GPU 采集走**回退链**：`rocm-smi` → `/sys/class/drm`；**不要**把 `nvidia-smi` 当硬依赖 |
| **10** | **`readonly: true` 与"必须落文件"互斥** | A1 首次实测：模型跑了 6 条命令、数据齐全，**但始终没写文件** ⇒ 只读卡的产物**永不落盘** | **要产物就必须 `readonly: false`**；只读只用于"纯输出型"卡 |
| **11** | ★ **站上限时一律 `timeout -k <grace> <dur>`**（裸 `timeout` **不算限时**）—— 裸 `timeout` 对**忽略 SIGTERM** 的子进程会**一直等**，不是"到点即杀" | **受控复现（B 站，2026-09-24）**：`timeout 2 bash -c 'trap "" TERM; sleep 6'` ⇒ rc=124 但**耗时 6s**；同命令加 `-k 1` ⇒ rc=137 **3s**。⇒ B 站曾有诊断进程活 **17.2h**（O-48） | **卡里 / 诊断 / 任何 ssh 到站上的限时命令**都写 `timeout -k 10 <秒> …`；⚠ 加 `-k` 后 KILL 生效时退出码是 **137**（非 124）⇒ 判"超时"须认 124 **和** 137 |

| **12** | ★ **ssh 传参必须防"远端 shell 二次解析"**：交替/管道类模式写成 `grep -E a\|b` 而**不加引号** ⇒ 远端把 `\|` 当**管道** ⇒ 拆出的词当命令跑，甚至**起一个裸 `opencode` TUI**（交互式、无 `-p`、无 EOF）⇒ `epoll_wait` **永不返回** | **一手实测（B 站，2026-09-25）**：站上留 **2 条**孤儿 —— `bash` 1-12:19（`do_wait`，子进程 `grep -icE error` 卡死）· `bash`+**`opencode`** **1-04:59**（`ep_poll`；47 fd，持 `opencode.db` **180MB** + wal/shm + `memory.db` + 两个 `opencode.log` 写 fd ⇒ 给同站共享 DB 的 run 加了一个**不明写者**）。⚠ 另含**作者本人当天踩的温和版**：`grep -e "[o]pencode run"` 经 PS 5.1→ssh 被**剥掉内层引号** ⇒ 远端报 `grep: run: 没有那个文件或目录` | 交替一律用**多枚免空格的 `-e`**（`grep -e A -e B`）；要整体加引号就**必须确认引号活到远端**（PS 5.1 会剥内层引号 ⇒ **优先前者**）；且**任何** ssh 到站上的一次性诊断命令都须被 `timeout -k 10 <秒>` **整体**包住（纪律 11）。⇒ 归因：**这不是 `timeout` 语义问题，O-48 的修法盖不住它**（本类来自**探针**，非派发链 4 处）。<br>★ **同日再踩两坑（同族）**：(a) **`pkill -f <模式>` 会自匹配携带该模式的 ssh 命令行** ⇒ 把整条会话连同**后续命令**一起杀掉（实测：后面的 `rm -rf` 没跑成、白留一个临时目录）⇒ 清进程请用 **pid**，或先用 `pgrep` 的 `[x]` 括号技巧核对；(b) 目标路径**可能已经是目录**（实测 `/tmp/opencode` 是既有目录）⇒ `ln -sf` / `cp` 会落进它**里面**而不是替换它 ⇒ 造探针请用**自建子目录** |

⇒ 这五条与纪律 7（**卡的射程 = 平台注册的工作区根**）是**同一族**：**站上沙箱的边界不靠读卡面猜，靠实测登记**。

### ★ 纪律 13：卡里内联**有单一真值的取值**时，**必须同时写真值源指针**（2026-09-26 入册）

**现象（一手）**：[`d7-p1-3-u3-edge-format-draft.md`](d7-p1-3-u3-edge-format-draft.md) 曾写
**「U-1（产物身份）**已定案**：算法 `sha256` · 截断 `[:16]` · 前缀 `u1:sha256:16`」** ——
而真值已是 **`[:32]` / `u1:sha256:32`**（**O-84** 裁定）⇒ 该卡正是**要给 D7 用的输入** ⇒ **陈旧副本会被下游继承**。

★ **为什么它比"没写"更危险**：它**自称"已定案"** ⇒ 读者**停止追问**（同族 = **O-87** 的"它不存在"：
**假事实比缺事实更容易把路封死**）。

**纪律**：卡里凡内联一个**有单一真值的取值** —— 截断长度 / 哈希前缀 / 端口 / 模型 id / 文件名约定 ——
**必须同时写出真值源指针**（如 `→ ops/rpc_check.py 的 U1_TRUNC` · `→ inventory/ports.yaml` · `→ secrets/openrouter.conf`），
**不要只写数字**。改动这类取值时，**先改真值源、再扫引用它的卡**。

⚠⚠ **为什么这条【不做判据】（实测，防下一个人重做）**：全仓 `[:NN]` 形 token **103** 处，
其中与真值 `32` **不一致的 62** 处 —— 而逐条看，**>93% 是合法的**（历史记档"由 `[:16]` 改为 `[:32]`" ·
描述下游现状"`factor_pipeline` 用 `[:16]`" · "5 种截断并存"）⇒ **做成判据就是一台假红机**。
（★ 同族三次：**O-87** 的存在性否定 · **O-69** 的卡面路径 token · 本条。）
⚠ 且 **`doclinks` / `spec-untested` 都读不到"卡里内联的取值"** ⇒ 本类**没有机制看住**，
**只靠这条纪律 + 审卡** —— 如实登记，**不假装已自动化**。

## 档位选择的正确顺序（`sensitivity.yaml` 的用法）

1. **先查输入**在真值表里的 `tier`（**未登记 = `local-only`**，fail-closed）；
2. 若输入**含 C1/C2**（未发表研究 / 他方未发表）⇒ **只能 `local-only`**（站内模型）；
3. 若输入的**唯一**敏感项是**凭据类**（且有固定格式前缀）⇒ 可用 `sanitized`（scrubber 会抹）；
4. 若输入**已不含 C1/C2/C3**（人工剔除后）⇒ 用 `public`，**保护来自"输入准备"，不来自档位**；
5. ⚠ **含 C3（IP/主机名/Linux 路径/用户名）的内容，`sanitized` 不提供保护** —— 不许靠它兜底。

## 第一批（2026-09-24 起草 · **5 张卡已全部跑完**）

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

## 第二批（2026-09-25 起草 · **待跑**）

> **定位**：D6 闭环已合上、吃狗粮通道本轮修好（O-56…O-66）⇒ **第一批"能不能跑通"的问题已解决**。
> 第二批问的是新问题：**"跑到今天，通道与判据还诚实吗"**。

| 卡（本目录） | 输入 | 档位 / 开关 | 站上引擎？ | 它回答什么 |
|---|---|---|---|---|
| [a3-workspace-accumulation.md](a3-workspace-accumulation.md) | 无 | `public` | ✗（出网档） | **站上工作区累计到什么程度** —— 量化 O-57 家族（跨 run 证据错配）的**根源**；**顺带**钉 README 纪律 7 那条未定的**沙箱可读边界** |
| [b3-gate-newjudges-falsegreen.md](b3-gate-newjudges-falsegreen.md) | `ops/rpc_check.py`（附件，已登记 `public`） | `public` + **`attach-egress: ok`** | ✗ | **B2 之后新增的那几项判据会不会假绿**（`py-tests` · `input-provenance` · `ps1-runstamp` · `stations` orphan 段 · `evidence` 第三态）—— 即 §13.0① 「**改门禁的任务本身要被门禁管**」 |

### 第三批（2026-09-25 起草 · **仪器卡**：O-68② 的验收探针 + O-67 的 fan-out 探针；**三张均已跑通**）

> **定位**：**验收件**（判据 V4/V5/V6，见 [DEV-LOG-014 §36.F](../../../docs/DEV-LOG-014-decision-refinement.md)）与
> **待裁项取证件**（O-67 的 fan-out 并行性）。
> 它们**不是**审计卡，而是**仪器卡**：形状刻意压到最小，只为压到被测的那条路径。

| 卡（本目录） | 输入 | 档位 / 开关 | 危险面？ | 它回答什么 |
|---|---|---|---|---|
| [v4-attach-golden-probe.md](v4-attach-golden-probe.md) | `ops/rpc_check.py`（附件，已登记 `public`） | `public` + `attach-egress: ok` + `accept-golden` | **是**（有附件 ∨ golden ⇒ 排他） | **V4**：per-run 改名后，**附件清单**与 **golden 产物**两条路径**仍能被正确回收**（`ATTACH_MANIFEST_LINES≥1` · `ACCEPT_GOLDEN_OK=1` · 站上 11 个后缀件齐全） |
| [v5-shared-readonly-probe.md](v5-shared-readonly-probe.md) | 无 | `public`，**`readonly: true`** | **否**（无附件 ∧ 无 golden ⇒ 共享） | **V5/V6**：这是**唯一**能造出"**同站同 proj 并存**"的形状 —— 探"两份 runDir 证据各自完整"与"6 并发 6/6 `exit=0`、无 `exit 3`" |
| [o67-egress-fanout-probe.md](o67-egress-fanout-probe.md) | 无 | `public`，**`readonly: true` + `decompose`（两片平衡）** | 否 | **O-67**：出网档 `decompose` 的并行性是**未验证假设**（代码自己的 `SPLIT_WARN` 承认）⇒ 用两片测"批墙钟是否真按 ~2× 缩短"。★ 两片**只能纯 stdout**（拆片器要求 readonly，而 readonly 与落文件互斥 ⇒ 纪律 10） |

> ⚠ `v5` 的卡面**刻意不写 `accept`**：站上 claude 通道在 `readonly` 下可能拒绝落文件，而本卡的判据是**框架证据件**是否各自完整（**不是**产物）⇒ 不落文件也应 `exit=0`。

### 第四批（2026-09-25 起草 · **D7 的吃狗粮卡**；「先跑一张再定」）

> **定位**：D7 早期工作的读入方案**验证件**。D7 决策文档登记为 `local-only`
> ⇒ 因**档位是文件级、敏感度是段落级**（[DEV-LOG-014 §33.5](../../../docs/DEV-LOG-014-decision-refinement.md)），
> 唯一可行的转换形态是**人工切 public 摘要** ⇒ 本批先**跑一张**验证"摘要够不够用"，再决定要不要起站内引擎。

| 卡（本目录） | 输入 | 档位 / 开关 | 它回答什么 |
|---|---|---|---|
| [d7-p0-1-adr-boundary-draft.md](d7-p0-1-adr-boundary-draft.md) | [inputs/d7-p0-boundary-excerpt.md](inputs/d7-p0-boundary-excerpt.md)（人工脱敏摘要） | `public` + **`attach-egress: ok`** | **摘要路线够不够**产出一份可用的 ADR 草案（`D7-P0-1`）· 以及**摘要相对原文缺什么**（卡面强制一节 `缺料与歧义`，并明写"不许补写附件里没有的内容"） |

> ✅ **首跑结论（run `202609260051398769`，2026-09-25）**：产物 **39 行 / 三节齐备 / 灰项 8-8 全覆盖**，
> 且 4 格**如实写 `依据不足`**（没猜）⇒ **摘要路线够用、不必起站内引擎**；缺料 6 条已逐条定性（含**原文一处笔误**"五处 vs 8 项"）。
> 详见 [DEV-LOG-014 §39.4](../../../docs/DEV-LOG-014-decision-refinement.md)。

### 第五批（2026-09-29 起草 · **A 清单：6 个"真·代码未实现"缺口的实现提案**；**三站并行 · 已全部跑完**）

> **定位**：`inventory/capability-inventory.yaml`（2026-09-27 读数）的 `absent` / `partial` 项里，挑出
> **6 个"登记明确未做"的缺口** ⇒ 出**设计提案**（**本轮不动实现**）。两批各 3 张、**跨站并行**
> （`batch` 派发器 = O-80）；清单 = [batches/imp-a.txt](batches/imp-a.txt) / [batches/imp-b.txt](batches/imp-b.txt)。

| 批 | 卡（本目录） | 输入 | 档位 / 开关 | 站 / 模型 | run | 结果 |
|---|---|---|---|---|---|---|
| IMP-A | [imp1-boundary-judge-wiring.md](imp1-boundary-judge-wiring.md) | 无 | `public` | A / `ultra-a` | `202609291929091622` | ✅ `exit=0`（RUN_S 71） |
| IMP-A | [imp2-cell-safety-judge.md](imp2-cell-safety-judge.md) | 无 | `public` | B / `ultra` | `202609291929092530` | ✅ `exit=0`（RUN_S 97） |
| IMP-A | [imp3-determinism-idempotence-judge.md](imp3-determinism-idempotence-judge.md) | 无 | `public` | C / `ultra-c` | `202609291929092399` | ✅ `exit=0`（RUN_S 127） |
| IMP-B | [imp4-executor-trace-design.md](imp4-executor-trace-design.md) | 无 | `public` | A / `ultra-a` | `202609291939005729` | ✅ `exit=0`（RUN_S 145） |
| IMP-B | [imp5-derived-view-design.md](imp5-derived-view-design.md) | 无 | `public` | B / `ultra` | `202609291939006123` | ✅ `exit=0`（RUN_S 83） |
| IMP-B | [imp6-invalidation-executor-design.md](imp6-invalidation-executor-design.md) | 无 | `public` | C / `ultra-c` | `202609291939006697` | ✅ `exit=0`（RUN_S 172） |

> ⚠ **6 张卡走的都是 `ultra`（同一 id `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`）的不同站**
> ⇒ **只跨了站、没跨族**（同一 `nvidia` 血统）。按 `D7-P0-3` 的 **J-1（跨族）**口径，
> 这只是"**同族多实例**"、**不构成认知多样性**（口径见 [model-families.yaml](../../../inventory/model-families.yaml) 表头）。
> ⇒ **后续派发应至少一张换族**：现成改法 = `lightning`（= `thinkingmachines/inkling:free`，钉 **B** 站、走 `opencode`）；
> 若要在 **A/C** 站也用 `inkling` 且仍走 `opencode`，须新增 `lightning-a` / `lightning-c` 别名
> （与 `ultra-a` / `ultra-c` **同构**：同一 id、不同 station）。

> ✅ **判读（主控独立复核，不采信模型自报）**：★ `imp1` 暴露 **`ADR-0009` 求值规则非穷尽** ⇒ 登记 **`O-115`（待裁）**；
> ⚠ `imp2` 参考实现 **2 处缺陷**（`_count_cols` 只数**非空**单元格；分隔行查找**跨空行**）·
> ⚠ `imp5` **自相矛盾**（`generated-at` 列进"确定性字段" vs `--check` 逐字节一致）·
> ✅ `imp6` 质量最好（可直接用）· `imp4` 采集点与本机群不符但**如实标注"不可核"**。
>
> ★ **`imp4` 的落地（A2，2026-09-29 本地落地 · 无派发）**：`executor-trace` 由"设计提案"落成**可机判件** ——
> 五采集点进 [`ops/station-bin/agent-cli.ps1`](../../../ops/station-bin/agent-cli.ps1)（`[cmd]/[env]/[fs]/[tool]/[artifact]`，
> 工具调用链**如实标 `uncore`**）· 新 gate `executor-trace` · Python 夹具
> [`tests/test_rpc_check_executor_trace.py`](../../../tests/test_rpc_check_executor_trace.py) 9/9 绿 · ps1 离线夹具 409/0。
> ⚠ 原判"采集点与本机群不符"已**就地核实**并改成可达命令（`uname`/`hostname`/`nproc`/`free -m`，**不读 `/proc`**）；
> 但 §2.2 的 **runtime 验收**（真派发后留痕件齐 + 与产物哈希交叉锚定）**未实测**（覆盖读数 0 个 run）。
> ★ **2026-09-30 更新（该结论已收口）**：覆盖读数 **11 个（齐段 11）**；且「与产物哈希交叉锚定」**已补判据**
> （门禁 `executor-trace` **第三段** —— 执行体不得自报哈希 · 留痕件 `ts` 须 == runDir 名 · 主控侧须有 `content_digest`；
> 读数 `ts 相符 11 · 自报 0 · ts 不符 0 · 无锚记录 0`）⇒ 见 [../A-LIST-LANDING-PLAN.md](../A-LIST-LANDING-PLAN.md) **「§2.4 读数刷新」**。
> 详见 [../A-LIST-LANDING-PLAN.md](../A-LIST-LANDING-PLAN.md) **§2.4** 与 `DEVELOPMENT-LOG.md` `2026-09-29（续④）`。
>
> ★ **`imp1` 的落地（A1，2026-09-29 本地落地 · 无派发）**：`d6-d7-boundary` 由"设计提案"落成**可机判件** ——
> 纯函数 `Resolve-D6D7Boundary` 进 [`ops/station-bin/agent-cli.ps1`](../../../ops/station-bin/agent-cli.ps1)
> （派发**前**对三键求值 ⇒ 按 [ADR-0009](../../../adr/ADR-0009-D6与D7分界判据.md) §2 **三分支**得唯一归属 ⇒ 落 `run.json` 的 `boundary`）·
> 三键入 `Get-FrontMatter` **白名单** · ps1 离线夹具
> [`_fm_golden_test.ps1`](../../../ops/station-bin/_fm_golden_test.ps1) **423/0**（+14 条 `a1-*`）· **无新 gate**（手册计数不变）。
> ⚠ **不采信模型自报**：原卡 §1.3 的"8 项灰色地带表 4/8 与 `ADR-0009` §3 不符"**已删表改指针**（不复制第二份真值）；
> 三键采用**下划线**命名（与非 kebab）；三键任一**未声明** ⇒ `resolved=false`（**不假装已判**）。
> 但 §2.2 的 **runtime 验收**（真派发后 `run.json` 含 `boundary` 键）**未实测**；且 `d6-d7-boundary` 为 **`partial`**
> （判据已接线留痕但**尚无消费方** ⇒ "算了没人用"；claude 本地备路早返回不带该键）。
> 详见 [../A-LIST-LANDING-PLAN.md](../A-LIST-LANDING-PLAN.md) **§2.5** 与 `DEVELOPMENT-LOG.md` `2026-09-29（续⑤）`。

### 第六批（2026-09-29 起草 · **跨族复核批**：`inkling` 判 `ultra` 的产物；**已跑完 + 发现 O-116**）

> **定位**：A 清单原 6 卡**全走 `ultra`**（同一 id，仅站不同）⇒ 按 `D7-P0-3` 的 **J-1** 口径只算
> **"同族多实例"、不构成认知多样性**。本批用**另一族**（`thinkingmachines/inkling:free` = `lightning`，钉 **B** 站）
> 对同一 6 份底稿做**独立缺陷复核**。清单 = [batches/xrev.txt](batches/xrev.txt)（**三行全 `station=B model=lightning`**）。

| 卡（本目录） | 复核对象（内嵌底稿） | 档位 | 站 / 模型 | run | 结果 |
|---|---|---|---|---|---|
| [xrev1-cellsafety-boundary.md](xrev1-cellsafety-boundary.md) | A4 cell-safety + A1 boundary-judge | `public` | B / `lightning` | `202609292037235965` | ✅ `rc=0`（产物 2958 B · `^- ` 12 条） |
| [xrev2-derivedview-executortrace.md](xrev2-derivedview-executortrace.md) | A3 derived-view + A2 executor-trace | `public` | B / `lightning` | `202609292038295460` → 重派 `202609292046072184` | ⚠ 首跑 `rc=1`/`TASK_RC=9`/**产物缺失**（`O-47` 同族）⇒ 重派 ✅（3347 B · 12 条） |
| [xrev3-invalidation-determinism.md](xrev3-invalidation-determinism.md) | A6 invalidation-executor + A5 determinism | `public` | B / `lightning` | `202609292039019829` | ✅ `rc=0`（产物 3436 B · `^- ` 12 条） |

> ★ **本批直接暴露 `O-116`（P1 · 判决级假绿）**：官方汇总三行**同一个 runDir**（末卡 `xrev3` 的）+ `exit=0`
> + `BATCH_DONE: 失败或未完成=0` ⇒ 把 `xrev2` 的真失败**掩盖成成功**。根因 = `Invoke-BatchTask` 汇总段
> `$done`/`$s2` 取**整站日志**末行（只有 `$mark` 按卡过滤）⇒ 逐卡 `$rc` 被**错 runDir** 的 `.agent-run.json` 覆盖。
> ⇒ **已闭环（2026-09-29，走 spec workflow）**：修法 = 站级日志**按卡切块**取 `TASK_DONE`/`RUNSTAMP`；
> 详见 `OPEN-ISSUES.md` **O-116** 与 `DEVELOPMENT-LOG.md` `2026-09-29（续②）` **⑨**。
> **反向断言件**：[neg-o116-batch-failcard.md](neg-o116-batch-failcard.md)（故意用未登记别名 ⇒ 零触站必失败）·
> [batches/o116-rev.txt](batches/o116-rev.txt)（两行同钉 B ⇒ 同一站级日志，用于修前/修后 A/B 对照）。

### 第七批（2026-09-29 起草 · **领域件落地批**：3 张产件卡，把已勘误底稿落成"可落地件"；**跨三站并行 · 已全部跑完**）

> **定位**：A 清单剩余 5 项的**落地**（[A-LIST-LANDING-PLAN.md](../A-LIST-LANDING-PLAN.md) §2）。
> 本批只做**其中三项** —— **A4 / A5 / A3** = 三个**互不共享代码面**的新 gate ⇒ 可并行立项、**各派一站**；
> 另两项 **A2 / A1 同改 `agent-cli.ps1`（关键路径）** ⇒ **不由本批派**，走主控**本地串行**。
> 清单 = [batches/land-a.txt](batches/land-a.txt)（三行 = A/B/C 各一卡 = 一站一卡 ⇒ 无同站锁冲突）。
> **模型 = 三站全 `ultra` 族**（`ultra-a`@A / `ultra`@B / `ultra-c`@C，同一 id、分居三站、**零代码改动**）——
> 产**实现件**不涉认知多样性，跨族（`lightning`）留给复核批。档位均 `public`（卡面自含**已勘误底稿**、无附件）。

| 卡（本目录） | 落地对象 | 档位 | 站 / 模型 | run | 结果 |
|---|---|---|---|---|---|
| [land-a4-cell-safety.md](land-a4-cell-safety.md) | A4 表格列数守恒判据 | `public` | A / `ultra-a` | `202609292125234284` | ✅ `exit=0`（产物 `out/land-a4.md` 5709 B） |
| [land-a5-determinism.md](land-a5-determinism.md) | A5 确定性/幂等（含噪声真值表） | `public` | B / `ultra` | `202609292125234193` | ✅ `exit=0`（产物 `out/land-a5.md` 6634 B · 7 类噪声） |
| [land-a3-derived-view.md](land-a3-derived-view.md) | A3 派生只读视图 + `--check` | `public` | C / `ultra-c` | `202609292125235028` | ✅ `exit=0`（产物 `out/land-a3.md` · 6 条不确定项） |

> ✅ **落地结果（主控本地，2026-09-29）**：三项**均已完整闭环**（判据 + 注册 + 手册计数 + 夹具 + 先验红 + 字节级恢复自证）——
> A4 → gate `md-tables`（28 条冻结）· A5 → gate `determinism`（噪声单表，与 [`inventory/determinism-noise.yaml`](../../../inventory/determinism-noise.yaml) 同批落地）·
> A3 → gate `derived-view`（[`ops/derived_view.py`](../../../ops/derived_view.py) + [`docs/派生视图_端口分配.md`](../../../docs/派生视图_端口分配.md)）。
> 逐项读数与先验红证据见 [A-LIST-LANDING-PLAN.md](../A-LIST-LANDING-PLAN.md) **§2.4**。
> ★ 三份产件里主控**改了 3 处**再落地（**不采信模型自报**）：A4 参考实现 2 处缺陷（只数非空单元格 / 分隔行跨空行查找）·
> A3 `generated-at` 与逐字节一致**自相矛盾**（照 §1.2 勘误**移除 `generated-at`**）；A5 底稿噪声 7 类**收成单表**（§3.2 已裁）。

### 第八批（2026-09-29 起草 · **回写复核 + 挂起项拆解批**；4 张卡跨三站 · **已全部跑完**）

> **定位**：① 主控刚做的一批"台账 / 真值表**回写**"（读数刷新 · gap 重写 · 段头与射程修正 · 两条否决的理由分层与反链 ·
> 一条闭环上限由"未定"改 3）**没有第二方看过** ⇒ 派**另一族**（`lightning` = inkling 族）做**独立缺陷复核**（`xrev4`）；
> ② 三个**仍挂着**的项缺**可执行方案** ⇒ 各派一站拆解（`hang1` / `hang2` / `hang3`）。清单 = [batches/hang.txt](batches/hang.txt)。
> 档位均 `public`（卡面**自含抽象化材料**、**无附件** ⇒ 不触发 `attach-egress` 义务）。
> 站与模型：`xrev4` = B·`lightning`（另一族）· `hang1`/`hang3` = **A·`ultra-a`**（站内串行）· `hang2` = C·`ultra-c` ⇒ 站间并行度 3。
> ⚠ **首跑 4/4 失败**（`exit=255`，同族 `O-117`：PowerShell here-string 把 markdown 反引号当转义 ⇒ 注释被推出 `#`）⇒ 修 `O-117` 后**重派**本表结果。

| 卡（本目录） | 对象（内嵌抽象材料） | 档位 | 站 / 模型 | run | 结果 |
|---|---|---|---|---|---|
| [xrev4-writeback-audit.md](xrev4-writeback-audit.md) | 四段"台账 / 真值表回写"的独立缺陷复核 | `public` | B / `lightning` | `202609292327452548` | ✅ `exit=0`（`RUN_S` 107 · 产物 7191 B · `^- ` 23 条） |
| [hang1-evidence-gap-accept.md](hang1-evidence-gap-accept.md) | 「证据链新增 1 条可重放缺口 ⇒ 该不该推进水印」拆解 | `public` | A / `ultra-a` | `202609292327452588` | ✅ `exit=0`（`RUN_S` 109 · 产物 6290 B） |
| [hang2-memorygate-enginechannel.md](hang2-memorygate-enginechannel.md) | 「记忆面 1 条通道闸门在引擎侧、本仓关不掉」（现只点名+WARN）拆解 | `public` | C / `ultra-c` | `202609292327453524` | ✅ `exit=0`（`RUN_S` 151 · 产物 5406 B） |
| [hang3-runtime-acceptance.md](hang3-runtime-acceptance.md) | 「过程留痕 / 层级归属 两项**已落地但从未实测**」的运行验收拆解 | `public` | A / `ultra-a` | `202609292329463549` | ✅ `exit=0`（`RUN_S` 530 · 产物 10320 B） |

> ✅ **判读（主控**逐张独立复核**，不采信模型自报 · 2026-09-29）** —— 4 份均**格式达标**、**实扫无**本仓路径 / 主机名 / 用户名泄露；下述为**复核发现**（产物**可用**，但各有需裁的收尾项）：

> **`xrev4`（对四段回写的缺陷复核）**：4 段齐 · 23 条 · 末尾"无法判断项" 5 条。★ **复核本身有 3 处要裁**：
> ① ★ **自造数字** —— 修法写"含跳过项则应为 **141**"，而材料只给 `91` 与 `10`（把"5 个模板的 10 个位点"**误读成 5×10=50** 再相加），
> 按字面应为 **91+10=101**（**它要抓的就是"数字与被引读数不符"，自己却犯了**）；
> ② **误读门禁** —— 判"`capped` + `max_rounds:3` 与'无执行机制'**直接违反门禁规则**"，而门禁原文只要求"若 `capped`，
> 则**超限动作可枚举**"（回写已给 `on_exceed_kind: escalate`）⇒ **门禁不违反**；"无牙"是**另一件事**（已登"未实测登记"）；
> ③ **弱判** —— 指"'真实余缺只剩两条'是未论证断言"，而材料**已逐条列**那两条并说明原 ① 为何不成立（属**信息不足**，非未论证）。
> ⇒ 结论：**可作缺陷线索**，**不可照抄为结论**（3 处已在上列裁掉 / 改正）。

> **`hang1`（水印 `--accept` 拆解）**：6 节齐 · 37 条 · 5 类分类树（含"不可判 ⇒ 不推进水印"）· 步骤含"**推进水印前必须留记录**"· 验收含反向 —— **覆盖面达标**。
> ⚠ **一处内部矛盾（高价值）**：`## 判定输入` 第 4/5 条把"**取不到**"与"**无匹配 / 无同族**"混为一谈，写成"**无匹配 ⇒ 不可判**"；
> 而 `## 分类树` 的 A/B 判据正是"**基线清单无匹配 ⇒ 先修 / 改清单**"、C 判据正是"**历史无同族 ⇒ accept**"
> ⇒ **同一事实两处给出两种结局**（恰是本仓最忌的"两处表达 ⇒ 迟早一处过期"）。
> 另有：分类树 C 处置把"`accept`"与"**补录命令**"两个动作塞进一列（口径越界）；验收第 1 条"字段齐 ⇒ 事实完备"与"若干条取不到即不可判"**不闭合**。
> ⇒ 结论：**方案可用**，但**那两处冲突须先改**再采纳。

> **`hang2`（引擎侧无门拆解）**：6 节齐 · 分界表 8 行 · 候选 5 条（含"**什么都不做并写下理由**"）· 推荐 "候选 2+1+3" 且**失效重审条件已量化** · 反面 2 条 · 验收含反向 + 防假绿 —— **质量较好**。
> ⚠ 三点：① 分界表"本仓可控?"列出现 **`可控但无效`**，**越出闭集**（`可控` / `不可控` / `可观察但不可改`）；
> ② **两处表头被写成 `- ` 列表项** ⇒ 会虚增 `^- ` 计数（本卡无实质影响，计数远超阈值）；
> ③ 推荐里候选 3（影子索引）只给"**视资源启动**"，**未给可机判的启动条件**（对照：失效条件已量化）。
> ⇒ 结论：**可直接采纳为处置方案**（3 点属收尾项）。

> **`hang3`（两项运行时验收拆解）**：6 节齐 · 前置 7 · 步骤 8（**两项分开走**，明确第二次卡**多声明哪三键**）· 交叉锚定 3 问全答（谁算哈希 / 哪行承载 / 不一致判什么）·
> 验收 7（含负向 · 空对象 · 未求值 · 穷尽性 8 组合）· 失败形态 6（四条必含全）—— **本批最扎实的一份**。
> ⚠ 四点：① **射程漏验** —— 项一有一条"留痕件**只进主路**、本地备路**不产**"的已知射程，而步骤**只验了项二的备路射程**（`claude` 记录不含 `resolved`/`tier` 键），**没验项一**；
> ② **词表两处不一致** —— 步骤判据只查 `verified` **一个词**，验收判据却列 `verified`/`audited`/`validated` **三词**；
> ③ 自造量化阈值 `timeout_ms >= 3 * P99`（材料未给）；④ 把"哈希不一致"**自造映射**进失败形态②（虽用"推广"自曝，材料未归此类）。
> ⇒ 结论：**可直接采纳为 runtime 验收方案**（4 点属收尾项）。

> ★ **本批结论**：**无新 `O` 项** —— 4 份产物**未暴露仓库级新缺口**（`hang1`/`hang2`/`hang3` 所述事实面与本仓真值一致、无编造）；
> `xrev4` 的 3 处系**复核产物自身**的误判 / 数字错 ⇒ 教训 = "**复核也需二次判读**"（本轮已就地裁掉，不写新 `O`）。
> ⚠ **待裁（3 项）**：① `hang1` 的接受判据是否采纳 ⇒ 决定 **`evidence` 可重放 gap 那 1 条是否 `--accept`**
> 　（★ 门禁明细 = `dogfood/202609292038295460`：`subject 'xrev2' 声明的 xrev2.md 不在 runDir` —— 该 runDir 是 `xrev2` **首跑失败**那次，
> 　产物已在**重派** runDir `202609292046072184` ⇒ 按 `hang1` 分类树更像 **A/C（先修 / 补录）**，**不是 `--accept`**）；
> ② `hang2` / `hang3` 方案是否**落进各自目标档**（`hang2` → 记忆面门禁档；`hang3` → [A-LIST-LANDING-PLAN.md](../A-LIST-LANDING-PLAN.md) §2.4 / §2.5 的 runtime 段）；
> ③ Codex CLI 路径**甲**（wrapper 侧补"循环检测"判据）还是**乙**（走 `ADR` 裁引入）· 见 `OPEN-ISSUES.md` **`O-118`**。

### 第九批（2026-09-30 跑完 · **决策细化批**：3 张卡；跨两站）

> **定位**：承第八批判读的"**待裁（3 项）**"，**各要一个决策**（不是再拆解一遍）⇒ 三张卡 = 三个决策：
> `dec-ev1`（那条可重放缺口该不该 `--accept`）· `dec-mg2`（记忆面档**落法**）· `dec-al3`（落地计划档**落法**）。
> 清单 = [batches/dec.txt](batches/dec.txt)。档位均 `public`（卡面**自含抽象化材料**、**无附件**）。
> 站与模型：`dec-ev1` = A·`ultra-a`；`dec-mg2`/`dec-al3` = **B·`lightning`**（与产出这两份方案的 `ultra` 族**不同族** ⇒ 照 `J-1` 精神）⇒ B 站两张**站内串行**。
> ★ **如实登记**：本批**只一张跨族**（`lightning` 只钉 B 站；A/C 无同族别名，加别名要改 `ROUTE_TABLE`）。

| 卡（本目录） | 决策对象 | 档位 | 站 / 模型 | run | 结果 |
|---|---|---|---|---|---|
| [dec-ev1-evidence-gap.md](dec-ev1-evidence-gap.md) | 新增可重放缺口 1 条：该不该 `--accept` | `public` | A / `ultra-a` | `202609300003009903` | ✅ `exit=0`（`RUN_S` 219 · 产物 5386 B） |
| [dec-mg2-landing.md](dec-mg2-landing.md) | 引擎侧无门通道处置方案的**落法** | `public` | B / `lightning` | `202609300003009703` | ✅ `exit=0`（`RUN_S` 144 · 产物 8410 B） |
| [dec-al3-landing.md](dec-al3-landing.md) | 两项运行时验收方案的**落法** | `public` | B / `lightning` | `202609300005337385` | ✅ `exit=0`（`RUN_S` 162 · 产物 7037 B） |

> ✅ **判读（主控逐张独立复核，不采信模型自报 · 2026-09-30）** —— 三份均**格式达标**、**实扫无**本仓路径 / 主机名 / 用户名泄露。

> **`dec-ev1`（证据缺口决策）**：6 节齐 · 32 条。结论 = **「先查产出方基线清单、再决策」**（非必产出才接受；必产出且失败未产出 ⇒ 保留为缺口、追根因），
> 含「会不会把**真失败**洗白」专问 + 6 条验收（2 条反向）。⚠ 一处：材料已点明本例是**卡自己声明的产物**（非框架件），
> 而它把决策压在"该 subject@v2 是否在**基线清单**的必产出集合"上 ⇒ **杠杆可能不对位**（其 `不确定项` 已如实标注该疑）；
> 且「事实认定」先判死"证据缺陷"，与自承的关键事实未知**有张力**。⇒ 可用作**取证清单**。

> **`dec-mg2`（记忆面档落法）**：6 节齐 · 26 条。落点判定逐条钉"**能不能进本仓 / 落到哪一栏**"，4 条纪律冲突检查，落法要求**只改现有条目 + 只放指针**。
> ⚠ 一处：目标档**已有**同内容条目（`gate: none` + `controllable_by_us: false` + `why` + `evidence` 全在）⇒ 其"增量修改该条目"**实际净增 ≈ 0**，
> 真正增量只有 `unverified[]` 两条 + 沿革一行（`不确定项` 已诚实标注"需先读档再定位"）。⇒ **落法可用**。

> **`dec-al3`（落地计划档落法）**：6 节齐 · 33 条。选**就地（§2.4 / §2.5）+ 只加指针 + 不删"未实测"原句 + 指针附注方案已知缺陷**，反转条件齐。
> ⚠ 一处**实质误读**：其"常驻载体"写"**本决策文件（`dec-al3.md`）为常驻（★ 已裁 = 常驻）**" —— 那是把 §3.3 对**目标计划文档**的裁定
> **挪用**到自己的**产物文件**上（产物在 `tmp/` 下，**非常驻**）；另两处收尾：验收判据混入"本文件 `^- ` ≥ 12"这类**产物自检**（验收对象应是**落档动作**），
> 及"并入 §3 ⇒ 造第二份真值"依据偏弱。⇒ **落法可用**（挪用那句须先改）。

> ★ **本批结论**：**无新 `O` 项**（三份均**未暴露仓库级新缺口**；`dec-al3` 那处系**产物自身**误读 ⇒ 采纳前须改）。
> ⚠ **待裁（3 项，沿用第八批）**：① `dec-ev1` 的**取证步骤**是否执行（决定 `evidence` 那条是否 `--accept`）；
> ② `dec-mg2` / `dec-al3` 的**落法**是否落地；③ Codex CLI 路径甲 / 乙（`OPEN-ISSUES.md` **`O-118`**）。

### 第十批（2026-09-30 跑完 · **未实测索引的「9 条 needs_decision」取证批 · 第一刀**；2 张卡跨两站）

> **定位**：`inventory/untested-index.yaml`（6 份规范 `## 未实测登记` 节的**分诊索引**，51 条）里，
> 用户裁定**第一刀 = 先裁那 9 条 `needs_decision`**（只差一次裁定，占全量 ~18%）。
> ★ **本批只覆盖 9 条里【可出网面】的 4 条** —— 见下方"档位约束"。
> 清单 = [batches/untested-dec.txt](batches/untested-dec.txt)。卡面**自含抽象化材料、无附件** ⇒ 档位均 `public`。

| 卡（本目录） | 覆盖 | 档位 | 站 / 模型 | run | 结果 |
|---|---|---|---|---|---|
| [dec-cc-three-undefineds.md](dec-cc-three-undefineds.md) | 结论契约三个未定项（`path` 相对根 / `line_range` 越界 / 三分类阈值 ≥2） | `public` | A / `ultra-a` | `202609300531207317` | ✅ `exit=0` |
| [dec-u1-truncation-mapping.md](dec-u1-truncation-mapping.md) | 产物身份「截断长度变更后无映射路径」 | `public` | B / `lightning`（**跨族**，照 J-1） | `202609300531207402` | ✅ `exit=0` |

> ★ **档位约束（本批最重要的前置 —— 它把"3 卡"修正为"2 卡"）**：9 条按**所属规范的档位**分布，
> 而 `inventory/sensitivity.yaml` 里 **`U3` / `U5` / `U4` / `D7-PROTOCOL-CONCLUSION-CONTRACT` 四份原未登记**
> ⇒ 按 `default_tier: local-only`（fail-closed）兜住。逐份核验结论：
> **① 补登记 `public` 两份** —— `U3-EDGE-FORMAT`（内容源自**已登记 public 的卡面**，与 `U1` 同款定档理由）·
> `D7-PROTOCOL-CONCLUSION-CONTRACT`（与已 public 的 `D7-PROTOCOL-CONTRACT` **同族同批**；唯一外引是 arXiv 公开论文）；
> **② 维持 `local-only` 两份** —— `U4`（原文明写其规则原文来自**他方 RFC**）·
> ★ `U5-TRUST-BASIS`（含**他项目内部实现细节**且**无 public 载体可引** ⇒ 先例不适用，fail-closed）。
> ⇒ **本批覆盖 4 条**（dec-cc 3 + dec-u1 1）；**另 5 条（U4×3 + U5×2）暂缓** ——
> 要么走**站内卡**（需起本地引擎），要么先做**人工 public 摘要**。

> ✅ **判读（主控逐张独立复核，不采信模型自报 · 2026-09-30）** —— 两张**格式达标**。
> **`dec-u1` 可用**：6 节齐 · `^- ` 36 条 · 候选**逐条标了「判据 vs 纪律」**（卡要求）· 不确定项 6 条如实。
> ⚠ 2 处表述瑕疵（步骤 2 把"要新建文件"与卡约束"只写一个文件"写在**同一句再自我纠正**）。
> ★ **`dec-cc` 有 1 处实质错误 + 1 处内部矛盾 + 1 处与卡约束冲突**：**把给定材料的数字改错** ——
> 卡面逐字材料写「生日阈值约 `2^64`，比 16 字符的 `2^32` 强得多」，产物写成「32 字符 ≈ **`2^128`**（比 16 字符 `2^64` 强）」
> ⇒ **两个数各被放大 `2^64` 倍**（按 hex 字符数 n ⇒ 4n bit ⇒ 生日阈值 `2^(2n)` 复算：**材料是对的、产物是错的**）；
> 且它**同一句**自述"具体数值未给出故标不确定" ⇒ **自相矛盾**；其可执行步骤第 5 步要写 `out/dec-cc-evidence.md`，
> 而卡的硬性要求 5 明写**除 `out/dec-cc.md` 外不产生任何文件**。
> ⇒ **两产物均可作决策线索、不可照抄**（错误处已在 `O-123` 复核段逐条指出）。
> ★ 本批再次印证第八批 `xrev4` 的教训：**"复核也需二次判读"** —— 且这次是**主控自己的卡**被复核出实质错误。

### 批次派发（O-80，2026-09-26）—— "多张不同卡并发"

```powershell
& ops/station-bin/agent-cli.ps1 batch dogfood -Card "spec\d6-agent-standard\dogfood-cards\batches\o80-smoke.txt"
```
**清单格式**（逐行；`#` 注释、空行忽略）：`<卡路径> [station=A|B|C] [model=<别名>]`，示例 [batches/o80-smoke.txt](batches/o80-smoke.txt)。
**env 桥**（顶层 `param()` 块在本环境加不了新参数 ⇒ 走既有 env 模式）：`AGENT_BATCH_DRYRUN=1`（干跑，0 个新 runDir）· `AGENT_BATCH_PER_STATION`（v1 只支持 1）· `AGENT_BATCH_TIMEOUT_S`（默认 2400，超时**显式记未完成**）。
**调度**：**每站内部串行 · 站间并行**（并行度 = 站数 ≤ 3）；未钉站的按"当前最少"轮转 ⇒ 3 张卡 = A/B/C 各一。站是**真钉**的（父进程把站字母换成 host 串）⇒ **计划 == 现实**。
**产物/日志**：汇总表按 **runDir 为真值**（读 **`.agent-run.json`**，**不是** `run.json`）；⚠ **逐卡的 `runDir`/`exit` 取值必须限定在该卡自己的日志块内**（`O-116`：站级日志是"多卡顺序追加"，取整站末行 ⇒ 每卡都拿到末卡的值 ⇒ 判决级假绿，2026-09-29 已修）。每站日志在 `tmp/dogfood-ws/agent-out/_batch/<ts>/st-<站>.log`。
⚠ **v1 边界**：只支持**无附件**卡（带附件请单张跑）· 不做失败卡自动换站 · 不做产物归并。

### 两张卡的设计要点（不是风格，是依据）

- **`a3` 的"双结果"设计**：站上沙箱**可读边界并未完全确定**（已知工作目录可读；**同级目录未验证**）⇒
  卡里写明"**被拒就记 `probe_errors` 并继续，不要换写法重试**"，且 **"全被拒"也判合格**（`projects:[]`）。
  ⇒ 两种结果**都有用**：要么拿到累计数据，要么钉住边界。**避免"只有一种结果才算成功"** ⇒ 那会把未验证的假设当既定事实。
- **`a3` 的披露姿态**：产物**只写相对名 + 数字 + 时间**，**不写任何绝对路径**（不 `pwd`）——
  与 A1 同级（A1 也只记了 `hostname` 与目录**名**）。
- **`b3` 的收窄理由**：B2 已做过**全量**审计，**重复审旧的 = 白烧额度** ⇒ 卡里点名**五项**并要求"不多不少"。
  ⚠ 卡里同时写明"**下表的'判什么'只是路标，以脚本内文本为准，不要轻信本表**" —— 防"照抄卡里的描述当结论"。

> ⚠ **两张卡都还没跑**（起草 ≠ 派发）。派发前的合规核查已过（见下）。
> ⚠ `b3` 走**附件** ⇒ 必须 `attach-egress: ok`（否则 `REJECT … exit 4` 整单拒），且附件**不经 scrubber** ⇒
> 附件本身必须是 `public` 档（`ops/rpc_check.py` = `public`，已登记，用途即此）。


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
