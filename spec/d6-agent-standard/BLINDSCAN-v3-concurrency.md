# BLINDSCAN v3 —— **并发脆弱面扫描**（2026-09-23）

> **触发**：裁定 O-28 并发修复时，修完 RC①（站覆盖）/ RC②（ts 去重）后**又冒出 RC③/RC④**。
> ⇒ 判断"逐个撞"效率太低（**新冒出的两条都不在"路由/命名空间"层，而在"前置探针与工作区骨架"层**）
> ⇒ 改为**先扫面**：**枚举一切在派发前或运行中触碰共享文件系统 / 共享状态的步骤**，逐条判并发安全性。
> **方法**：沿用 `BLINDSCAN-v2-orchestration.md` 的三段式（**证据 / 判定 / 落点**）。
> **范围**：`ops/station-bin/agent-cli.ps1` 为主（主控侧 + 远端脚本内嵌段）；门禁与钩子只在被 agent-cli 触碰时纳入。
> **判据**："并发安全" = **同一 proj 在三个站上同时跑**时（O-26/O-18 允许的形态）不产生互相破坏。

---

## 0. 摘要

| 判定 | 条数 | 说明 |
|---|---|---|
| **✅ 安全** | 6 | 已有正确隔离（`RUN_TOKEN` / 远端 `flock` / ts 去重 / 只读） |
| **⚠ 不安全（并发送）** | **3** | 其中 **2 条比已登记的 RC③ 更严重** |
| **ℹ 说明性** | 4 | 不是缺陷，但**解释了 RC④ 的根因** |

**两条"比 RC③ 更严重"的**（**⚠ 见 §5：这两条判定已被本轮取证撤回/降级，保留原文以便追溯**）：
- **F-2**：[:2131](../../ops/station-bin/agent-cli.ps1) **删除共享固定路径** `agent-out\.agent-run.json` —— 并发时**A 的收尾会删掉 B 正在用的文件**（比"探针读失败"严重的多：**静默数据破坏**）。
- **F-3**：**`out/` 目录被 `.agentsync` 模板全局排除**（[:117-120](../../ops/station-bin/agent-cli.ps1)）⇒ **RC④ 的根因在此，无需再猜**。

> **⚠ 本节的两条"最严重"判定，在修复取证时被我自己撤回 —— 见 [§5 取证后更正](#5-取证后更正2026-09-23本轮)。
> 教训：扫描也会过度推断；**判定必须能被代码事实证伪，否则不许写成"确定"**。**

---

## 1. 共享资源清单（逐条判定）

| # | 资源 | 证据（使用点） | 判定 | 依据 |
|---|---|---|---|---|
| **F-1** | `<projRoot>/agent-out` 的**写探针** | [:620-630](../../ops/station-bin/agent-cli.ps1) `Assert-AgentOutWritable`：`Set-Content -Path $probe`（**固定名探针**） | ⚠ **并发不安全** | **= 已登记的 RC③**：多进程对**同一固定探针路径**同时写/读 ⇒ 实测 `PREFLIGHT-FAIL … **Stream was not readable**` + ABORT exit 12，**而同批次另一次却成功** |
| **F-2** | `agent-out\.agent-run.json` 的**删除** | [:2131](../../ops/station-bin/agent-cli.ps1) `Remove-Item (Join-Path $projRoot 'agent-out\.agent-run.json')` | ⚠⚠ **并发不安全（静默破坏）** | **共享固定路径的删除**：并发时 **A 的收尾删掉 B 正在使用的 `.agent-run.json`** ⇒ B 的产物**无声丢失**（不是报错，是丢）。**这比 F-1 严重**：F-1 是"随机失败"，F-2 是"随机数据丢失" |
| **F-3** | `out/` 目录（站侧） | **`.agentsync` 四类模板全部含 `out/`**（[:117-120](../../ops/station-bin/agent-cli.ps1)：`python`/`cpp`/`doc`/`lean4` 皆有 `'out/'`）＋ 骨架创建 [:331](../../ops/station-bin/agent-cli.ps1) `New-Item "$stag\out"` | ⚠ **= RC④ 的根因** | **staging 的 `out/` 被模板排除 ⇒ tar 不携带空目录 ⇒ 站上首次派发无 `out/`** ⇒ 远端脚本写 `out/.agent-output.txt` 直接 `not found`（实测 C 站）。**根因确定，无需再猜** |
| **F-4** | `ops/station-bin/agent-runs.log`（ledger） | [:2009](../../ops/station-bin/agent-cli.ps1) / [:2742](../../ops/station-bin/agent-cli.ps1) `Add-Content`（追加单行） | ◐ **实测可用，理论待加固** | **实测**：并发两进程各写一行、两行都完整（`ledger+=…` ×2）⇒ **当前可用**。但 `Add-Content` **无显式互斥**，依赖单行小于缓冲的偶然性 ⇒ **应加固**（见 §3） |
| **F-5** | `%TEMP%\agent-cli-ev-<ts>`（evidence 暂存） | [:1834](../../ops/station-bin/agent-cli.ps1) | ✅ **安全（间接）** | 依赖 ts 唯一；**RC② 修复后 ts 已去重** ⇒ 目录不复用 |
| **F-6** | `<projRoot>\agent-out\<ts>`（runDir） | [:2017-2028](../../ops/station-bin/agent-cli.ps1) | ✅ **安全（间接）** | 同上；且 [:2028](../../ops/station-bin/agent-cli.ps1) 的 `dir` 字面量含多余 `<`/`>`（`"agent-out\<$ts>"`）⇒ 实为**普通名字**，但**唯一性来自 ts** ⇒ 无害（另见 §3 附带项） |
| **F-7** | `$Script:TMP_ROOT` | [:51](../../ops/station-bin/agent-cli.ps1) `Join-Path $env:TEMP ("agent-cli-" + $RUN_TOKEN)` | ✅ **安全** | 早已 per-invocation 隔离（**这是本仓并发设计的正确样板** —— 其余共享路径应照此办） |
| **F-8** | 远端 `$W/out/*`（`.prompt.txt` / `.agent-output.txt` / `.meta` / `.accept-output.txt`） | [:1677](../../ops/station-bin/agent-cli.ps1) / [:1726](../../ops/station-bin/agent-cli.ps1) / [:1808](../../ops/station-bin/agent-cli.ps1) | ✅ **安全** | 由 `$W/.agent-lock` 的 **flock** 保护（同 proj 同站串行）；跨站文件本身不同 |
| **F-9** | 远端 `$W/.agent-lock` / `.agent-state.json` | [:578](../../ops/station-bin/agent-cli.ps1) / [:593](../../ops/station-bin/agent-cli.ps1) / [:1620](../../ops/station-bin/agent-cli.ps1) | ✅ **安全** | **per-(proj, 站)** 且用 **`flock`（真锁）** ⇒ 这是本仓**并发最正确的一处** |
| **F-10** | `Assert-AgentOutWritable` 的**两次调用**（task / split 各一） | [:1416](../../ops/station-bin/agent-cli.ps1) / [:2208](../../ops/station-bin/agent-cli.ps1) | ⚠ 与 F-1 同源 | 同一探针被两个入口调用 ⇒ 修复要**同时**覆盖两处 |
| **F-11** | `ops/.audit-baseline.json` | 门禁 `evidence` 读 · `cluster.py agent audit --accept` 写 | ◐ **未被 agent-cli 触碰** | 不在本次范围；但**并发跑门禁**会互踩 ⇒ 留作 D6-P1 的检查项 · **⚠ 2026-09-23 后续（本行保留原状，只加标注）**：路径已变（→ `inventory/audit-baseline/<host>.json` 分片，见台账 **O-33**）；**且"按机分片"只治了跨机、未治同机** ⇒ 同机两个 `--accept` 并发仍是 read-modify-write 竞态（**留在下文**，见 O-33 追加） |
| **F-12** | `archive/evidence-chain/*`（链与锚） | git hook（+ `cluster.py agent chain`） | ◐ **未被 agent-cli 触碰** | 已在 `.gitignore` 说明里标注"跨机一致当前无收益"；**并发提交**仍可能互踩 ⇒ 同上留作检查项 |
| **F-13** | `.agentsync` 模板**本身** | [:117-120](../../ops/station-bin/agent-cli.ps1) | ℹ **说明性** | 模板**同时排除** `out/` / `.agent-lock` / `.agent-state.json` / `.attach/` ⇒ **设计上认为这些"不该上站"**，但**远端脚本又必须写 `out/`** ⇒ **两处假设互相矛盾**（见 §2） |

---

## 2. 三条判定的要点（为什么它们是真问题）

### F-2（最严重）：**共享固定路径的删除 = 静默数据破坏**

`.agent-run.json` 先在 `<projRoot>/agent-out/` 下**暂存**、collect 时移入 `agent-out/<ts>/`，最后 `Remove-Item` 清暂存。
⇒ 并发时：**A 的 `Remove-Item` 会命中 B 正在写/正准备移动的那一份** ⇒ **B 的 run 记录无声消失**。
⇒ 这类失败**不会报错**（`-ErrorAction SilentlyContinue`，见 [:2131](../../ops/station-bin/agent-cli.ps1)）⇒ **比 F-1 的"随机 abort"隐蔽得多**。
⇒ **修法方向**：暂存路径**按 ts（或 RUN_TOKEN）命名**，而不是共享固定名 —— **与 `TMP_ROOT` 的样板同法**。

### F-3（RC④ 根因）：**模板排除 `out/` 与"远端必须写 `out/`"互相矛盾**

- 模板（四类全含 `'out/'`）⇒ sync 不带 `out/` ⇒ 空目录不入 tar ⇒ **站上没有 `out/`**；
- 而远端脚本第一件事就是写 `$W/out/.agent-output.txt`（[:1677](../../ops/station-bin/agent-cli.ps1)）⇒ **必然 not found**。
⇒ 为何**既有三站偶尔能跑**？因为那些工作区的 `out/` **早先已有文件**（tar 会带非空目录）⇒ **"空目录丢失"只在全新工作区暴露** ⇒ 与 RC④ 的实测（**只有 C 站报错**）完全吻合。
⇒ **最鲁棒的修法**：**远端脚本在写之前 `mkdir -p "$W/out"`** —— 一行，且**与"空目录不被携带"这一事实相容**（不依赖任何 tar 行为）。

### F-1（RC③）：**门本身成了随机失败源**

`Assert-AgentOutWritable` 是**派发前的前置门**，却用**固定名探针**读回校验 ⇒ 并发下 `Stream was not readable` ⇒ **ABORT exit 12**。
⇒ 危害不在"失败"，而在**它把"并发"伪装成"环境不可写"**（错误归因）⇒ 运维会去查权限，而真因是并发。

---

## 3. 建议修法（按优先级）+ 注入设计

| 优先级 | 修什么 | 怎么修 | 注入用例（须正反） |
|---|---|---|---|
| **P0** | **F-2** 共享固定路径删除 | 暂存 `.agent-run.json` 改为**按 ts / RUN_TOKEN 命名**（照 `TMP_ROOT` 样板） | 并发两 run ⇒ **两份 `.agent-run.json` 都在**（反例：改前 A 的清理删掉 B 的） |
| **P0** | **F-3**（RC④） | **远端脚本写之前 `mkdir -p "$W/out"`**（不依赖 tar 携带空目录） | **全新工作区**（删掉站侧 `out/`）首跑 ⇒ 不报 not found；反例：`local/*` 卡在无引擎时仍 exit 10 |
| **P1** | **F-1**（RC③） | 探针改用 **per-invocation 名**（`$RUN_TOKEN`）**或**改为"写固定名 + 唯一内容 + 读回比对"的**幂等**形态 | 并发两 run ⇒ 均 `PREFLIGHT …WRITABLE`；反例：真把 `agent-out` 设为只读 ⇒ 仍须 ABORT 12 |
| **P2** | **F-4** ledger | `Add-Content` 外包一层**文件锁**（或改 `cluster.py` 统一追加） | 并发 10 行 ⇒ 行数==10 且无交错 |
| **P2** | **F-10** 两处调用 | 与 F-1 同步改（否则 split 入口仍带病） | — |
| **ℹ** | **F-11 / F-12** | 先**登记**（并发跑门禁/并发提交），不在本轮 | — |

**★ 一条跨条目纪律（从本扫描得出）**：
> **凡"共享路径"，要么带 per-invocation 身份（`RUN_TOKEN`/ts），要么走真锁（flock）。**
> 本仓已有两个正确样板（`TMP_ROOT` 的 token、远端 `.agent-lock` 的 flock）——
> **新代码只要照抄二者之一即可，不需要发明第三种。** 而 F-1/F-2 恰是**两处漏照抄**。

---

## 4. 与既有条目的关系

| 条目 | 关系 |
|---|---|
| **O-28** | 本扫描是它的**面级扩展**：RC①/RC② 已修；**RC③** = F-1；**RC④** = F-3（**根因由本扫描定位**）；新增 **F-2**（严重度高于 RC③） |
| **O-26** | `decompose` 拆片并行**已闭环** ⇒ 但它的两处 `Assert-AgentOutWritable`（F-10）**同样带 F-1 的病** |
| **O-18** | "跨站各 1 并发"是**允许并发的架构铁律** ⇒ 本扫描列出的 F-1/F-2/F-3 是**该铁律的落地缺口** |
| **O-11 / O-17** | V2 并发与 readonly 锁的既有工作 ⇒ 本扫描**不重复它们**，只看"派发链自身的共享路径" |
| **BLINDSCAN-v2-orchestration** | 同构文档（三段式方法沿用）；v2 管"编排可靠性盲区"，v3 管"并发共享面" |

---

## 5. 取证后更正（2026-09-23 本轮）—— **扫描自身的两处过度推断**

修复 P0 时逐条取证，**F-2 与 F-3 的判定都与代码事实矛盾**，故撤回/降级：

| 原判定 | 取证事实 | 更正 |
|---|---|---|
| **F-2**「共享固定路径的删除 ⇒ **静默数据破坏**」 | **全文件仅 :2131 一处**引用该**共享固定名** `agent-out\.agent-run.json`，且**无任何写入方** —— 本函数写的是 **per-`<ts>`** 的 `$runDir\.agent-run.json`（[:2102](../../ops/station-bin/agent-cli.ps1)） | ❌ **撤回"数据破坏"**。它是**死路径清理**（删不到东西）。**已删除**该行 —— 理由：制造"共享固定路径是活路径"的**审查误导** + `SilentlyContinue` 掩盖一切 + 若将来有人恢复写该名会**立刻变成真破坏**。**从 P0 降为"代码腐化清理"（已完成）** |
| **F-3**「模板排除 `out/` ⇒ 站上无 `out/`」 | **远端脚本第 4 行就有 `mkdir -p "$W" "$W/out"`**（[:1598](../../ops/station-bin/agent-cli.ps1)）—— 站侧**自建 `out/`**，不依赖 tar 是否携带空目录 | ❌ **撤回"根因在此"**。⇒ **RC④ 真因待现场诊断**（推断与代码矛盾 ⇒ 不能再猜） |

**⇒ 两条纪律（本扫描最重要的产物）**：

1. **"缺陷"必须能被代码事实证伪，否则不许写成"确定"。**
   本轮我在扫描里下了两个**没有代码证据支持**的严重判定（F-2 假设该路径有写入方；F-3 忽略了远端已自建目录）。
   **与 O-27 的"预存断言缺陷"同源教训：判据必须从代码语义推导，不能凭想象。**
2. **死路径清理要删，不要留。** 留着它的代价是**误导审查** —— 本轮我被那个路径**误导了一次**。

**⇒ RC④ 的正确下一步（替代"凭推断修"）——站上现场取证三样并比对**：

- `/tmp/agent-cli-task-<该次 ts>.sh` 的**行 61** 实际内容（错误正报在那里）；
- 该次脚本里 `W=` 的**实际值**；
- 该次前后 `ls -la "$W/out"` 的实况。

**在拿到这三样之前，不修、不猜。**

---
