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
| 7 | ★ **卡的射程 = 工作区**（`~/agent-workspaces/<proj>`）：**不要指示模型去读工作区外的目录** | **一手实测（2026-09-24，A2 首跑失败的直接原因）**：`permission requested: external_directory (/home/scott-lau/scripts/*); auto-rejecting` ⇒ 站上 agent 对外部目录**一律 auto-reject**（= O-30 第一条的第二实例）。⇒ 要取证**工作区外**的站上实况（`~/scripts`、`/proc`、系统目录），**必须由主控 ssh 直接做**；agent 只能跑**可执行命令**（如 `infer-list`/`free -m`/`ss -ltn` —— A1 正是靠这个成功的） |

## 档位选择的正确顺序（`sensitivity.yaml` 的用法）

1. **先查输入**在真值表里的 `tier`（**未登记 = `local-only`**，fail-closed）；
2. 若输入**含 C1/C2**（未发表研究 / 他方未发表）⇒ **只能 `local-only`**（站内模型）；
3. 若输入的**唯一**敏感项是**凭据类**（且有固定格式前缀）⇒ 可用 `sanitized`（scrubber 会抹）；
4. 若输入**已不含 C1/C2/C3**（人工剔除后）⇒ 用 `public`，**保护来自"输入准备"，不来自档位**；
5. ⚠ **含 C3（IP/主机名/Linux 路径/用户名）的内容，`sanitized` 不提供保护** —— 不许靠它兜底。

## 当前批次（2026-09-24 起草 · **4/4 已就位**）

| 批 | 卡（本目录） | 输入 | 档位 / 开关 | 站上引擎？ |
|---|---|---|---|---|
| A | [a1-station-reality.md](a1-station-reality.md) | 无 | `public` | ✗（出网档） |
| A | [a2-station-scripts-drift.md](a2-station-scripts-drift.md) | 无（比对在主控做） | `public` | ✗ |
| B | [b1-u2-dialect-map.md](b1-u2-dialect-map.md) | [inputs/d7-dialect-excerpt.md](inputs/d7-dialect-excerpt.md)（**人工脱敏摘要**） | `public` + **`attach-egress: ok`** | ✗ |
| B | [b2-gate-falsegreen-audit.md](b2-gate-falsegreen-audit.md) | `ops/rpc_check.py`（附件，已登记 `public`） | `public` + **`attach-egress: ok`** | ✗ |

⇒ **四张卡都不需要站上引擎**（全部走 `model: ultra` = `openrouter/*` 出网档）。

> **首轮实测状态（2026-09-24）**：**A1 ✅ 通过**（117s）· **B2 ✅ 通过**（789s，含附件 + `attach-egress`）·
> **A2 ❌ 设计错误**（要读工作区外的 `~/scripts` ⇒ `external_directory` **auto-reject**；须改设计，
> 或把该取证**改为由主控 ssh 直接做** —— 见纪律 7）· **B1 未跑**。

### ⚠ 派发前必读：出网档的**落站事实**（2026-09-24 一手读 `ROUTE_TABLE`）

- `opencode` 通道的出网档 **`lightning` / `ultra` / `free-1m` 全部 `station = 'B'`**（`agent-cli.ps1` ROUTE_TABLE）
  ⇒ **四张卡并行 = 全部落在 B 站同站**（无法靠"换站"错开；要跨站需先给 A/C 增出网档别名 = 改运行时脚本）。
- **同站叠并发对"出网卡"是否适用 O-18（~2.8×）—— 未实测**：O-18 是**本地引擎推理**的带宽现象；出网卡**无本地推理**，
  且实测 run 里 `slot.gated = false`（slot gate 只对本地引擎通道生效）。⇒ **技术上无闸拦**，但**属未验证假设** ⇒ 首轮建议先 **2 张并行**取证。
- 另一条**不改代码**就能错开的路：`cli: claude` 的备路在**主控本地**执行（`station = ''`），走同一 openrouter ⇒ 可与 B 站卡真并行（代价：执行器不同）。
- openrouter 侧上限 = **20 请求/分/账户**（B 站独立账户）⇒ 4 张卡远低于上限 ✓（实测见 `cluster.py egress`）。

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
| **同站同 proj 有互斥锁** | `LOCK_ACQUIRED … mode=exclusive`（per-`(proj,站)`；O-28 RC① 记录过 `LOCK_HELD` 同一 owner） | **同 proj 的两张卡不能并行** ⇒ 第二张会撞锁 |
| **出网档只落 B 站** | `ROUTE_TABLE`：`lightning`/`ultra`/`free-1m` 全 `station='B'` | 于是"换站错开"也做不到 ⇒ **本目录四张卡只能串行** |

⇒ 要真正并行，两条**需要额外动作**的路：① 给 `A`/`C` 增出网档别名（改 `ROUTE_TABLE` = 改运行时脚本，另案）；
② 一张走 B 站 opencode、另一张走**主控本地** `cli: claude` 备路（`station=''`，同走 openrouter，代价是执行器不同）。

### ★ 首轮派发已实测的两点（2026-09-24）

- **A1 ✅ 通过**：`ACCEPT_OK=1 / TASK_RC=0 / RUN_S=117`，产物 `out/station-reality.json` 合格且诚实
  （`nvidia-smi`/`rocm-smi` 均 127 ⇒ 回退链落到 `/sys/class/drm`，两条失败**如实**记进 `probe_errors`）。
- ★ **产物不在 run 目录**：卡的产物只落在**站上工作区**（`~/agent-workspaces/dogfood/out/`），主控 run 目录
  只收 `agent-output.txt` 等固定证据件，`workspace-diff.txt` 为**空**（`WORKSPACE_DIFF_LINES=0`）
  ⇒ **要拿产物必须另行回收**，或按 ADR-0007 在卡里声明 `evidence-manifest.subjects`。

> ⚠ **B1 的档位已定案 = `public` + 摘要**（Scott 2026-09-24）：不再走 `sanitized`，也不再走站内。
> 理由：`sanitized` 对 C3 类不提供保护（见 `inventory/sensitivity.yaml` 表头），保护必须前移到**输入准备**这一步。
