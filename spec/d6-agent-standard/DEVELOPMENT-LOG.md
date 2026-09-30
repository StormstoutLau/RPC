# 开发日志：D6 agent-cli wrapper 框架（Development Log）

***

id: d6-agent-standard-DEVELOPMENT-LOG
type: dev-log
version: 1.0
status: active（持续维护中）
date: 2026-09-03
depends: \[d6-agent-standard-DESIGN, d6-agent-standard-CHECKLIST, d6-agent-standard-OPEN-ISSUES]
upstream: \[d6-agent-standard-.* 全量文档]
------------------------------------------------------------------

> **用途**: D6 框架（主控站 agent-cli wrapper + 跨站派发 + 评审/看板/栅栏闭环）的**唯一演进史**——按里程碑时间线回溯记录「何时做了什么、为什么、验收证据、关联 O-xx」，并预留持续追加。与 DECISIONS（为什么这么做）互补，不重复其决策推演。
> **规则**: 新里程碑**追加在最新的日期章节顶部**（时间倒序）；每条含 日期 / 事件 / 涉及文件 / 验收证据 / 关联条目；闭环事件的验收证据以链接回填，不在此铺细节。
> **追加者**: 每次重要落地/闭环后由 Scott 或执行体回填。

***

## 历史回溯（2026-09-03 起）

### 2026-09-30（续⑳） — **`O-124` 候选① 闭环（含【真跑验收】）+ `O-125` 候选① 落地（`backend` 拆字段）+ 新登记 `O-127`（批清单编码坑）**

> **定位**：承 `续⑲` 的"④ 未做（如实）" —— 本轮**专门**做 `O-124①` 与 `O-125①`；执行中**又踩到**一个真实缺陷，就地登记为 `O-127`。

**① `O-124` 候选① —— 让 `local` 档真的采纳 `station=`（`P1` · 判决级）**

- **根因（读码）**：`$stPref = [string]$r['station']`，而卡的自然写法 `model: claude` 在 `Resolve-Model` 里解析出的 **`station` 本就是空** ⇒ `$stPref` 恒空 ⇒ `P3_CANDIDATES: A,B,C (pref= ...)`**不带偏好** ⇒ 三行 `station=A/B/C` 全落第一站。**且 `Invoke-Task` 的 claude 分支把 `--remotehost` 整条丢弃**（批行的 `station=` 经它换成 host 串传到 `-hostName`，随即无人使用）。
- **修法**：新增纯函数 `Get-StationLetterFromHost`（host → 站字母，**唯一**反查点；⚠ `Get-TargetHost` 对**未知**输入默认返回 B 的 host ⇒ 反查须**建表查不到即 `''`**，不能逐个比）+ `Invoke-Task` claude 分支把 pin 反查后作 `-PreferredStation` 传下去 + `Invoke-Task-Claude` 在 route 无站时**回落**该值进 `-Preferred`（route 声明的站优先）+ `$useStation` 改为 `$backendLocal -or 路由站 -or pin`。
- ★★ **真跑验收（前后对比 · 同一张卡 `probe-claude-tools-local.md` · 都钉 `station=C`）**：

| | 修前（`_batch/20260930145623` 第 3 行） | 修后（`_batch/20260930193001`） |
|---|---|---|
| `P3_CANDIDATES` | `A,B,C (pref= avoid=)` | **`C,A,B (pref=C avoid=)`** |
| `P3_STATION_SELECT` | `station=A host=scott-lau-NEX.local` | **`station=C host=192.168.10.37`** |
| `.agent-run.json` | `station:A/main` | **`station:C/main`** |
| 批报告 `st=` | 请求值（与实况不符） | **`st=C`** ＝ 实际站 ⇒ **判据达成** |
| 耗时 / 退出 | 953 s（靠 resume 收口） | **225 s 一次过** · `ACCEPT_OK=1` |

- ⚠ **同时登记两处更正（实测）**：① 台账原文"**出网档 `st=` 与实况一致**"是**误读** —— `O-111` 出网档那批**同样没采纳 pin**（三行全在**主控本地**跑、`model` = 云端型号 `thinkingmachines/inkling:free`），之所以"看着一致"是 `Get-ActualStation` 取不到那两行 ⇒ **如实回落请求值**；② 本次把"**钉站 ⇒ 走站上出网**"这一**出网档行为变更**一并纳入候选①。

**② `O-125` 候选① —— `sensitivity` 拆出可选字段 `backend:`（`P2`）**

- **先列影响面（实测，非估）**：卡区共 **85 文件**（**75 张**写了 `sensitivity`：`public` 52 · `local-only` 21 · `sanitized` 2；6 张无 front-matter）· ★ **`backend` 键此前 `0` 张卡在用** ⇒ **迁移面为空** · `sensitivity.yaml` 已登记 **29 条** · 档位枚举 **4 档**。
- **决策 = 采纳候选①【推荐形态：只加可选字段 + 缺省推导】**（不做硬切、**不动任何存量卡**）。
- **落地四处**：① `Get-FrontMatter` 白名单加 `backend`（⚠ 该函数是**白名单解析**，漏登记 = "写了却没人读"）；② 新增纯函数 `Resolve-CardBackendLocal`（**唯一解析点**，返回 `ok`/`local`/`why`）；③ `Invoke-Task-Claude` 的 `$backendLocal` 改由它定，且 `$useStation` 改吃 `$backendLocal`（**要害**：`backend: local` + 更宽档位时**必须**仍走站上通道，否则落到主控本地 = **反而出网**）；④ 批清单读取顺带修（见下③）。
- **判据（fail-closed）**：`local-only` ∧ `backend: egress` ⇒ **REJECT（exit 4）**；**未知取值（拼错）⇒ REJECT**（不许静默退回推导值）。缺省（不写）与旧式**逐字等价**。
- **文档同步四处**：`inventory/sensitivity.yaml` 表头 · `dogfood-cards/README.md` 档位顺序第 6 条 · `CROSS-PROJECT-WORK-STANDARD.md` §4 卡契约 · `DESIGN.md` §6.1 卡样。
- ⚠ **未做（如实）**：**没有**新增 Python 侧"卡面静态扫"门禁 ⇒ 机判**只在派发时**；存量卡**不补**字段（按设计不需要）。

**③ 新登记 `O-127` —— 批清单的编码坑（执行中踩到，修在根因侧）**

- **症状**：新写的验收清单 `batches/o124-pref.txt` 首次派发即 `BATCH_ABORT: 清单里没有可解析的行`。
- **病因（实测）**：`Invoke-BatchTask` 用**裸 `Get-Content`** 读清单，而 PS 5.1 对 **BOM-less UTF-8** 文件按**系统 ANSI(GBK)** 解码 ⇒ 中文注释的某些字节对**吃掉换行** ⇒ 相邻两行并成一行 ⇒ 卡行被并进注释（以 `#` 开头 ⇒ 跳过）⇒ **0 行**。★ 同一份文件：**裸读 25→16 行 / kept=0**；**加 `-Encoding UTF8` ⇒ 33 行 / kept=1**。
- **修法（根因侧）**：清单读取改为 `Get-Content -LiteralPath $listFile -Encoding UTF8`（**与 BOM 无关**）。⚠ **不走"让文件带 BOM"的 workaround** —— 实测 Edit 类工具保存时会**丢 BOM**，那条路**本身不可靠**。

**④ 夹具与门禁**

- `_fm_golden_test.ps1`：**434 → 448**（`o124b①–⑥` · `o125①–⑥` · `o127` · **+1 条次序守卫**）；全绿 `pass=448 fail=0`。
- ★ **新增的次序守卫是有来历的**：`$backendLocal` 必须**早于** `$useStation` 解析 —— 实现**第一版正是放在其后**，PS 下 `$null` 直接**静默走错通道**（与本函数顶上那条"`$stPref` 必须在 `$useStation` 之后"同族）。同时按新字面量更新了既有的两条位置/结构断言（**守卫语义一字未改**，只跟字面量）。
- ⚠ **夹具编写须知（本次踩到，已写进夹具注释）**：`Assert-True "…"` 的**描述串不得以反引号结尾** —— `` `" `` 会被 PS 读成**转义引号** ⇒ 字符串不终止 ⇒ 报 `string is missing the terminator` 且**错报位置在文件末尾**（不在出错行）。
- 门禁：`--only syntax` PASS（BOM 未丢）· `--quick` **PASS · 38 绿 / 2 黄 / 0 红**（与 `续⑲` 同）。
- ⚠ **副作用（如实）**：为做上面的真跑验收，**C 站 `gpt-oss-120b` 引擎被加载**（`cluster.py load gpt-oss-120b-c`；前置状态 = C 站 STOPPED）—— 本次**未卸载**（站级卸载走 `cluster.py` 的 flow，不在本项范围）⇒ 需要时手工卸。

**关联**：`OPEN-ISSUES.md` **`O-124`**（✅ 已闭环）/ **`O-125`**（✅ 已闭环）/ **`O-127`**（✅ 已闭环）。

### 2026-09-30（续⑲） — **`O-123` 收口：9 条 `needs_decision`【全部裁完】**（U4×3 + U5×2 下裁并落回本体）+ `O-126` 候选① 落

> **定位**：承 `续⑰`（第二刀取证已备）。★ 用户裁 **【甲】**：4 条下裁（= **已裁 + 实现待落地**）+ `U5#6` **登记能力边界**。

**① 5 条裁定（全部落回规范本体 —— 不是只写台账）**

| 条目 | 裁定 | 落点 |
|---|---|---|
| `U4 #3`（影响面闭包化） | **自报位 ⇒ 可核验形态**：判定方**独立重算**为主判据 + 逐跳路径证据为辅；不一致 ⇒ 拒收 | [U4-INVALIDATION-RULES.md](./U4-INVALIDATION-RULES.md) §未实测登记 第 3 条 |
| `U4 #4`（只适用派生产物） | **落成可机判形态判据**：每项须带可核来源标记；显式非派生 ⇒ 硬拒；无标记 ⇒ 先软警+审计（灰度） | 同上 第 4 条 |
| `U4 #6`（增量等价） | **以「证伪」替代「证明」**：测例集 + 反例清单（含历史真实失效）+ 运行时自检 + 白名单 | 同上 第 6 条 |
| `U5 #4`（默认公理白名单） | **裁掉默认名单形态** ⇒ 必须显式声明（缺失即判不通过）+ 支持**显式空声明** | [U5-TRUST-BASIS.md](./U5-TRUST-BASIS.md) §未实测登记 第 4 条 |
| `U5 #6`（`min_recurrence` 阈值） | ★★ **登记为「能力边界」不裁**（同 `D7-CC #5` 先例）—— 取值是设计选择、schema 零实例；**当前不得参与自动判定** | 同上 第 6 条（`state` → `boundary`） |

★ 前 4 条共同性质：**只裁"该怎么做"、未改任何代码** ⇒ 索引 `state` 仍 `todo`（= **已裁 + 实现待落地**，同 `D7-CC #3`/`#8` 形态）；各条均写了 **再触发条件**。

**② 索引口径变化（同步测试打印，非写死）**
- `needs_decision` **5 → 0** ⇒ ★ **九条 `needs_decision` 至此【全部裁完】**（第一刀 4 条见 `续⑬/⑭`，第二刀 5 条见本节）。
- `state`：`todo 42 → 41` · `boundary 3 → 4`（`U5#6`）。
- `blocker`：`implementation 28 → 32` · `decision 6 → 1` · `none 7 → 8`。
- ⚠ 仍留一条 `blocker: decision`（`U1#5` namespace 治理）而 `needs_decision: false` —— ★ 二者**不矛盾**：前者是"**最近阻碍是人裁定**"，后者是"**文档明写未裁/待裁**"（定义不同，**不合并**）。

**③ `O-126` 候选① 已落**：夹 [`README`](./dogfood-cards/README.md) 第十一批段补**写卡侧纪律** ——
"卡面若要求可机判判据，**必须同时明写**『判据里每个数值必须标注来源，标不出就写 `待校准`』"，**审卡时按此核**。
⚠ **候选② 明确不采纳**（"裸数值 ⇒ 判不通过"需能机判裸数值，正则**易误杀**）。

**④ 未做（如实）**：`O-124` 候选①（让 `local` 档真的采纳 `station=`）与 `O-125` 候选①（把 `backend` 拆成独立字段）**本轮未做** ——
二者都动**执行路径/真值表 schema**，须在**专门一轮**里做（`O-125①` 尤其动全部卡面，**不能顺手改**）。
**关联**：`OPEN-ISSUES.md` **`O-123`**（◐ · 余"索引首个消费者"未接）/ **`O-126`**（◐）/ `O-124`（◐）/ `O-125`（◐）。

### 2026-09-30（续⑱） — **修「链档恒脏」**：钩子改写受跟踪文件却不暂存（改受管源 `ops/rpc.ps1` 生成器 + 重装）

> **症状**：每次提交后 `archive/evidence-chain/{ANCHOR.txt,agent-chain.json}` **恒为 ` M`** ⇒ **链档永远落后一次提交**。
> **机制**：`.git/hooks/{pre-commit,pre-push}` 里 `"$PY" ops/cluster.py agent chain` **改写**这两件**受跟踪**文件，
> 而钩子**不暂存** ⇒ 本次提交取的树是"**改写前**"的快照 ⇒ 提交后工作树 ≠ HEAD（**每提交必脏**）。

**① 正解位置（★ 不是手改钩子）**：钩子头写明「**由 `ops/rpc.ps1 install-hooks` 生成, 请勿手改**」，
且 `git config core.hooksPath` **为空** ⇒ **钩子本体不在版本管理内** ⇒ 改**受管源** [`ops/rpc.ps1`](../../ops/rpc.ps1)
的 `Install-HookEntry` 模板，再跑 `ops\rpc.ps1 install-hooks` 重装。★ 这样**修法本身可复现**（手改 `.git/hooks/` 只在本机生效、且下次重装即被覆盖）。

**② 修法**（`Install-HookEntry` 模板，紧跟 agent chain 那行之后）：
```powershell
if ($Name -eq 'pre-commit') { $lines += 'git add -- archive/evidence-chain/ANCHOR.txt archive/evidence-chain/agent-chain.json 2>/dev/null || true' }
```
- ★ **只 add 这两个路径** —— **不用 `git add -A`**（那会把无关改动**静默卷进**本次提交）；
- ★ **只在 pre-commit** —— pre-push 不产生提交，暂存反而留下"**已暂存但未提交**"的假象；
- 保持 **best-effort**（`|| true`），与既有的 `agent chain` 那行同风格。

**③ 验收（实测）**：重装后 —— `pre-commit` **含**该行 / `pre-push` **不含**（分别核过）·
两文件均 **UTF-8 无 BOM + `sh -n` rc=0** · ★★ **本提交之后 `git status` 对这两件为空 = 环路已断**。

**④ ⚠ 过程中我自己犯了一次（并已回滚）**：第一版把 `"exec ..."` 从 `$lines = @(...)` 数组里搬出，
并**追加了一个多行 `$lines += @(...)` 块** ⇒ `ops/rpc.ps1` **解析失败**（报 *"here-string 未闭合"*，
`parse errors = 2`；而 `git show HEAD:ops/rpc.ps1` 解析 **0 错** ⇒ 确认是自己改坏的）。
回滚后改用**单行标量追加**即成（`parse errors = 0`）。
⇒ ★ **纪律（本轮学到的）**：**改生成器 / 门禁脚本之前，先用 AST 解析器验一遍** ——
`[System.Management.Automation.Language.Parser]::ParseFile($p,[ref]$null,[ref]$errs)` 数 `$errs.Count`，
**别等 `install-hooks` 炸了才发现**。⚠ 且 `syntax` 门禁**只扫 15 个 ps1**（`ops/station-bin/`），
**不覆盖 `ops/rpc.ps1`** ⇒ 这类文件**没有门禁兜底**，只能靠自己先解析。

**⑤ ⚠ 提交时又被门禁拦了一次（BOM 丢）**：本次提交被 `syntax` **阻断** —— 明细 `.ps1-bom:15文件/**1失败**`。
根因：**保存 `ops/rpc.ps1` 时把它的 UTF-8 BOM 弄丢了**（实测 `git show HEAD:ops/rpc.ps1` → `BOM True`/6563 B；工作区 → `BOM False`/7410 B），
而门禁对 ps1 的解析**按有无 BOM 走不同解码**（无 BOM ⇒ 按系统 ANSI/GBK 读）⇒ **中文注释乱码 ⇒ 假解析错** ⇒ FAIL。
⇒ **修法**：把文件重写为 **UTF-8 with BOM**（内容一字未改）⇒ `syntax` **PASS**（`.ps1-bom:15文件/0失败`）· AST 解析 `0 错`。
★ **纪律（与本轮 ④ 合并成一条）**：**动 `.ps1`（尤其 `ops/rpc.ps1` 这类带 BOM 的生成器）之后，交提交前先跑 `--only syntax`** ——
它会同时兜住**语法**与**BOM**两件事，比只看 AST 解析多一层。⚠ 且本例说明 `syntax` 的 15 个 ps1 **包含 `ops/rpc.ps1`**（与 ④ 里"不覆盖"的判断相反，**已就地更正**）。

**关联**：`archive/evidence-chain/*`（钩子产出，2026-09-17 起 best-effort 入链）· `O-34`（门禁范围口径 / 手动跑与提交跑可能不同）· 发现者 = 本轮 `git status`。

### 2026-09-30（续⑰） — **`O-123` 第二刀（`U4×3 + U5×2`）5 卡跑完 + 主控逐张复核（全部可用）+ 新登记 `O-126`**

> **定位**：承 `续⑮`（一线建卡未派发）。★ 用户裁「继续」⇒ 派发 → 跑完 → **主控独立复核** → 回写。

**① 派发与结果**：批 `_batch/20260930162154`（清单 [ud45-dec.txt](./dogfood-cards/batches/ud45-dec.txt)）
⇒ **`BATCH_DONE: 卡=5 · 失败或未完成=0 · 清单错行=0`**；站分布 **A×2 / B×2 / C×1**（与计划一致）；`run_s` = **57 / 127 / 149 / 172 / 207 s**。

| 卡 | 索引条目 | 站 · 模型 | `run_s` |
|---|---|---|---|
| `ud4-closure-witness` | `U4 #3` | A · `ultra-a` | 127 |
| `ud4-derived-boundary` | `U4 #4` | B · `ultra` | 172 |
| `ud4-equivalence-proof` | `U4 #6` | C · `ultra-c` | 149 |
| `ud5-axiom-whitelist` | `U5 #4` | B · `lightning`（**跨族**） | 57 |
| `ud5-recurrence-threshold` | `U5 #6` | A · `ultra-a` | 207 |

★ **技术改进（与第十批的差别 · 已写进夹 README）**：本批**每张卡都声明了 `evidence-manifest.subjects`**
⇒ **产物真被回拉到 runDir**（第十批没声明 ⇒ 产物留站上、只能看终端回显）。机检：`accept.passed` **全 True** ·
**六节齐** · `^- ` **28–48**（卡的下限是 12）。

**② 主控逐张复核（不采信自报）⇒ ★ 5 份【全部可用】**（与第十批不同：**无实质错误、无与卡约束冲突**）
- `ud4-closure`：6 条候选逐条标「判据/纪律」· 反转条件 **3 条均可判** · 显式处理"换成证据后仍没人核"。
- `ud4-derived-boundary`：2 条反向 + 1 条**区分判据**（"边界靠文档声明 vs 被机判"）· 洗真信号给 3 条具体避法。
- `ud4-equivalence-proof`：★ **正面回答卡里点名的陷阱**（"测例全过但等价不成立"的假绿 → 反例清单须含历史真实失效 + 采样自检作第二道防线）· 写明"动实现前必须先留下 5 件制品"。
- `ud5-axiom-whitelist`：★★ **答中就要害** —— 识别"把『**无需声明**』误当『**未声明**』"，给出 `axioms: []` 显式空声明修法。
- `ud5-recurrence-threshold`：决策取"**可见性积累模式**"+ 阈值降级为人工视图提示；★ 回答"低复发静默升层"时**保留"不得自审"硬挡 + 新增"最低可见性门槛"可机判硬判据**。

**③ ★★ 本批最重要的共性发现 ⇒ 新登记 `O-126`（P2）**：**"可机判"被普遍用【凭空数值】满足** ——
5 份里 **4 份**在「验收判据」塞入**无校准依据**的阈值（`10MB` · `P99<200ms` · `≥95%` · `80%` · `≥90%` · `4 周` · `≥3 类` · `≥10%` · `100ms`）。
⚠ **对照组**：`ud5-axiom-whitelist` 零凭空数值、`ud4-equivalence-proof` 多为**相对基准** ⇒ ★ **不是必然，是"没被要求"时的默认捷径**。
⇒ **消费纪律（本轮已落）**：产物里的数字**一律不得当裁定值**（写在夹 `README` 第十一批段）。

**④ 回写**：`O-123` 状态格（第二刀已跑完、**5 条本身仍未裁**）· `O-126` **新行** · 夹 `README` **第十一批整段**（表 + 档位注 + 逐张判读 + 消费纪律）。
**⑤ 收尾（本轮）**：`rpc_check --quick` **PASS** · 提交**纳入钩子产出的 `archive/evidence-chain/{ANCHOR.txt,agent-chain.json}`**（★ 前几次提交漏带了它们 —— 钩子会改写但**不自动暂存**，这一条已如实记录）· 重写历史后删备份标签 `backup/pre-msgfix`。
**未做（如实）**：★ **5 条裁定本身**（本批只交决策线索；裁定须落回 `U4`/`U5` 规范本体）· `O-126` 的三条处置候选**未裁** · 索引**首个消费者**仍未接。
**关联**：`OPEN-ISSUES.md` **`O-123`**（◐）/ **`O-126`**（新增 · 待裁）/ `O-125`（◐）/ `O-124`（◐）· 卡 ×5 + 批清单见夹 `README` 第十一批段。

### 2026-09-30（续⑯） — **`O-124` / `O-125` 各落「候选②」**：报告改报实际站 · 耦合写进真值表与写卡 README

> **定位**：承 `续⑮`（两条新缺陷刚登记）。★ 用户裁「执行吧」，两条均取其**建议的最低限度候选 ②**（**不拆字段 / 不改选站逻辑**）。

**① `O-124`（② 已落）—— 批报告的 `st=` 改报【实际执行站】**

| 面 | 落点 |
|---|---|
| 判定本体 | [`agent-cli.ps1`](../../ops/station-bin/agent-cli.ps1) 新增**纯函数** `Get-ActualStation`：从站级日志的 `P3_STATION_SELECT` / `CLAUDE_EGRESS_STATION_SELECT` 取**最后一条**实际站（`''` = **不可判**） |
| 报告 | 逐卡改用它 ⇒ 请求站 ≠ 实际站时打 **`st=A(req=C)`**；**取不到就如实回落请求值**（**不假装知道**） |
| 夹具 | [`_fm_golden_test.ps1`](../../ops/station-bin/_fm_golden_test.ps1) `o124①–⑤`：local 档 / 出网档 / **无该行的边界** / **同名多行取末** / 接线 |
| ⚠ 仍开 | **候选①**（让 `local` 档**真的采纳** `station=`）：根因已定位 —— 卡 `model: claude` 解析出的 route **`station` 为空** ⇒ `$stPref=''` ⇒ 候选站顺序**未带偏好** |

**② `O-125`（② 已落）—— 把「档位 ∧ 后端」耦合写进两处人读面**

- [`inventory/sensitivity.yaml`](../../inventory/sensitivity.yaml) 表头新增整块「**第二个语义：同时选择执行后端**」（含一手实测 + 两条纪律 + 三个候选）；
- [`dogfood-cards/README.md`](./dogfood-cards/README.md)「档位选择的正确顺序」加第 **6** 条 —— ★ 核心一句：**"过分类"不只更安全，它同时换了一条执行链** ⇒ **两档结果不可当"同一实验的两个读数"**。

**验收**：`FM_GOLDEN_TEST` **434/0**（原 429 + `o124` 五条）· `rpc_check --quick` **PASS**。
**未做（如实）**：两条的**候选①**（`O-124` 采纳 pref / `O-125` 拆 `backend:` 字段）均**未裁、未动**。
**关联**：`OPEN-ISSUES.md` **`O-124`**（◐ 部分闭环）/ **`O-125`**（◐ 部分闭环）。

### 2026-09-30（续⑮） — **`O-111` 工具面实测闭环（两程探针）+ 挖出两条新缺陷（`O-124`/`O-125`）+ `O-123` 五条暂缓建卡**

> **定位**：承 `续⑭`。本轮把 `O-111` 从"真值已取证、工具面待触发"推到 **✅ 工具面已实测**；并在实测中**挖出两条新缺陷**（登记为 `O-124` / `O-125`）；同时把 `O-123` 的 5 条暂缓项**按已裁路线建卡**（摘要 + 卡 + 批清单）。

**① `O-111`：claude 工具面两程探针（前置 = 三站 load 引擎）**

| 程 | 卡 `sensitivity` | 实测后端 | 结果 |
|---|---|---|---|
| 首程 | `public` | **`mode=or`（OpenRouter）** —— `.agent-run.json` 的 `model` = `thinkingmachines/inkling:free` | 三站**均** `exit=0` · `accept.passed=true`（`test -f` + `grep -q '^PROBE_DONE'` **双 `ACCEPT_RC=0`**）· 站 `st` 与 host 一致 |
| 第二程 | `local-only` | **`mode=local`（站上引擎）** —— `ANTHROPIC_BASE_URL=http://127.0.0.1:8080` · `engine_ctx=131072` | **`ACCEPT_OK=1`** —— 但★ **三次全落在 A 站**（见 ②） |

★ **结论**：**claude 执行器【有】工具调用能力**（accept 过了 ⇒ **文件真的被写出来** ⇒ 写文件这个工具**真的被调用过**）⇒ 手册 §2a.4「A-claude 纯文本模式 / 无工具调用能力」**在行为层也被否证**（此前只证了"该开关不存在"）。
⚠ **两条如实保留**：① 本地档**慢**（首跑命中 300s 预算 `rc=124`、靠 resume 收口；`run_s` = 456 / 679 / 953 s）—— 与手册"3s 快速响应"**不符**；② claude 档**不采集 `usage`** ⇒ **"工具调用次数"这一读数拿不到**，只能用 accept 产物**间接**证。
★ **前置**：三站引擎原为 **STOPPED** ⇒ 本轮 `cluster.py load gpt-oss-120b-a/-b/-c` 三站齐载（同模型 ⇒ 单变量），跑完**已卸载**（复原）。

**② ★★ 新缺陷 `O-124`（P1 · claude 通道 `local` 档：`station=` 不被采纳 + 报告 `st=` 与实况不符）**

- **实测**：同卡三行 `station=A/B/C` ⇒ 三份 `.agent-run.json` **全部** `station:A/main`、三份站级日志**全部** `scott-lau-NEX.local`（= A 站）；而批报告打出 `st=C / st=A / st=B` ⇒ **报告错**。
- **机制（读码）**：`$backendLocal = ($sens -eq 'local-only')` ⇒ `route_station` 为空 ⇒ 站上脚本按 `P3_CANDIDATES: A,B,C` **顺序取第一个"本地引擎 ready"的站** ⇒ **批行 `station=` 没进 `pref=`**。
- ⚠ **只在该 `local` 档**：出网档（首程）`st=` 与实况**一致**（三站各自 host）。
- ⇒ **危害**：① 报告与实况不符（同族 `O-116`，错在**站**这一维）；② 「按站并行」失效（三次**串行**落同一站）。
- ⇒ ★ **这也是 `O-111` 本地档只测到 A 站的原因**（B/C 覆盖归它的再触发）。

**③ ★ 新缺陷 `O-125`（P2 · `sensitivity` 一字段双语义：内容档位 ∧ 后端选择）**

- **一手踩到**：为 `O-111` 写探针卡时**先按内容**判成 `public` ⇒ 该卡**跑成了出网档** ⇒ **没测到本地引擎通道**；补一张 `local-only` 卡才命中。
- ⇒ **危害**：「档位 = **人的判断**」而「执行路径 = 它的**副作用**」⇒ 同一处改动的后果**跨两个语义域**。

**④ `O-123` 五条暂缓：按已裁路线**建卡**（摘要 + 卡 + 批清单，★ **未派发**）**

- 5 张卡（卡面即**人工 public 摘要**，抽象掉一切项目名 / 路径 / 主机名 / 内部标识）+ 批清单 [ud45-dec.txt](./dogfood-cards/batches/ud45-dec.txt)（干跑实测 **行=5 · 可用=5 · A=2 B=2 C=1**）：
  `ud4-closure-witness`(U4#3) · `ud4-derived-boundary`(U4#4) · `ud4-equivalence-proof`(U4#6) · `ud5-axiom-whitelist`(U5#4) · `ud5-recurrence-threshold`(U5#6)。
- ★ 每张卡均声明 **`evidence-manifest.subjects`**（⇒ 产物会被回拉到 runDir，供主控独立复核）· 六节结构（事实认定 / 候选处置 / 决策+反转条件 / 可执行步骤 / 验收判据 / 不确定项）· accept 含**机读锚点**（小节名 + `^- ` 条数下限）· stdout 单个哨兵行。
- ⚠ **边界（如实）**：摘要是**人写的**，**不是原文的等价替换** ⇒ 卡结论只对"摘要所描述的问题结构"负责。**派发待用户过目摘要后再定**。

**验收（本轮）**：`rpc_check --quick` **PASS**（数值见提交记录）· 探针 6 份 `.agent-run.json` 全 `exit_code=0` · 两批 `BATCH_DONE: 失败或未完成=0`。
**本轮未做（如实登记）**：`O-123` 五条的**派发与复核** · `O-124`/`O-125` 的**修法裁定**（两条均只登记 + 建议，未裁）· `O-111` 的 B/C 本地档覆盖。
**关联**：`OPEN-ISSUES.md` **O-111**（✅ 闭环）/ **`O-124`**（新增 · 待裁）/ **`O-125`**（新增 · 待裁）/ **`O-123`**（续⑭ 口径不变）· 卡 = [probe-claude-tools.md](./dogfood-cards/probe-claude-tools.md) / [probe-claude-tools-local.md](./dogfood-cards/probe-claude-tools-local.md) / `ud4-*.md` ×3 / `ud5-*.md` ×2 · 批清单 = [o111-tools.txt](./dogfood-cards/batches/o111-tools.txt) / [o111-tools-local.txt](./dogfood-cards/batches/o111-tools-local.txt) / [ud45-dec.txt](./dogfood-cards/batches/ud45-dec.txt)。

### 2026-09-30（续⑭） — **O-118 甲落地 + O-122 两裁执行/立项 + O-123 `#4` 裁与索引 `blocker` 字段**

> **定位**：承 `续⑬`（`#3`/`#8` 已裁）。本轮把 `O-123` 剩的两件（`D7-CC #4` 裁定 + 索引结构缺口）办掉，
> 并把 `O-118` / `O-122` 从"待裁"推到"已裁 + 已落地/已立项"。★ 全程遵守「**裁**必须落回规范本体」与「**不做也是结论**」。

**① `O-123` / `D7-CC #4`（`line_range` 越界）⇒ 裁「登记为不可判 + 保持形态校验」**

| 面 | 落点 |
|---|---|
| 规范本体 | [D7-PROTOCOL-CONCLUSION-CONTRACT.md](./D7-PROTOCOL-CONCLUSION-CONTRACT.md) §未实测登记 **第 4 条**（原"未裁" ⇒ 三条理由 + 再触发条件） |
| 索引 | `n:4`：`state` **todo → boundary** · `needs_decision` **true → false** · `refs: [O-123]` |
| 口径 | `state` 分布 **todo 43→42 / boundary 2→3**；`needs_decision` **6→5** |

★ **为何只剩"不可判"**：① `Test-FindingShape` 是**纯函数**（无产物入参）；② 相对根 `#3` **实现未落地** ⇒ 校验器**不知道打开哪个文件**；
③ 判官**看不到**被指产物（`#8`）⇒ 连"被指文件有几行"的前提都不成立。⇒ 「无效」「警告」都落地不了，同 `O-22`/`O-119` 的「**不可判 ≠ 通过**」。

**② `O-123` / 索引结构缺口 ⇒ 新增 `blocker` 字段（闭集）**

- 字段：`blocker ∈ { run | implementation | decision | external | none }` —— 回答「**卡在哪**」（现行 `state` **记不出"没跑"与"没实现"之别**，两者成本差一个数量级）。
- 53 条**逐条填值** + 索引头写明语义 + [`tests/test_untested_index_sync.py`](../../tests/test_untested_index_sync.py) 加**闭集校验**与 `blocker` 分布**算出来打印**。
- ★ **实测分布**（同步测试打印，非写死）：`run 10 · implementation 28 · decision 6 · external 2 · none 7`；★ 抽样印证「`D7-PROTOCOL-CONTRACT` 9 条**全 `implementation`**」。

**③ `O-118` ⇒ 裁【甲】并**已落地**：wrapper 侧"同一步重复 N 次 ⇒ 判循环并终止续跑"**

- 承前置问：**换 CLI（Codex）买不到**循环检测（其 `auto_review` = **批准面/沙箱**；未见拦"同一条无害命令重复 N 次"的证据）⇒ 治死循环的正确位置在 wrapper。
- [`ops/station-bin/agent-cli.ps1`](../../ops/station-bin/agent-cli.ps1) `$body`：首跑后**只读** `out/.agent-output.txt` 统计"**同一行重复数**"（**排除空行**以降假阳）⇒ 超阈值 `LOOP_DETECTED=1` ⇒ **续跑 `while` 加 `LOOP_DETECTED -eq 0` 闸**；`.meta` 与 `executor-trace` **各显式报** `LOOP_DETECTED`（可审计、不静默）。
- ⚠ **如实标注**：`LOOP_N=20` 是**设计选择、未实测**（已知样本 273 ⇒ 20 远离它）；假阳代价**被限制在"不给续跑"**（不杀首跑 = `timeout -k 10` 的职责 · 不改 rc）。
- **验收**：夹具 [`_fm_golden_test.ps1`](../../ops/station-bin/_fm_golden_test.ps1) `o118①–⑤`（**静态 3 + 行为 2**）⇒ **429/0**；★ **变异自证**：删掉 `while` 的闸 ⇒ `o118②` **红**（`428/1`），**字节级恢复**（sha256 前后一致）。
- ★★ **顺带记一条夹具侧老坑**：`& $bashPath -c $cmd` 走 **PS 原生参数** ⇒ `-cmd` 串里**不得含双引号**（实测 `echo "AA BB CC"` 只吐 `AA` ⇒ 命令被截断）。本段用**单引号/裸词**改写；`.ps1` **正文侧不受限**（那是写进文件的 bash）。

**④ `O-122` 两裁：①`8080` 谁让位 = **searxng 让位**（**已执行**）· ②Docker 栈纳管 = **走 ADR-0004 立项**（**ADR 已立**）**

| # | 裁定 | 落地 |
|---|---|---|
| ① | A 站 `~/searxng/docker-compose.yml` 宿主端口 **`8080:8080` → `8888:8080`** + `SEARXNG_BASE_URL` 同步 | **已执行（经 `cluster_ssh.ssh_run` = ADR-0004 的 SSH 层，未新造入口）**；备份 `docker-compose.yml.bak_20260930`；sha256 `c8ef140f…` → `af0f3260…` |
| ② | 该栈**纳入唯一管理面**（不新增并列入口） | 新立 [ADR-0012](../../adr/ADR-0012-A站容器栈纳管.md)（accepted；**实现未落地**，登记在案） |

- ★ **选 8888 的依据（E1）**：它是该 skill 文档**自带示例端口**（`SEARXNG_URL=http://localhost:8888`）⇒ compose 与文档一致。⚠ 实测 `SEARXNG_URL` 站上**未设置**（无 shell profile / `environment.d` 绑定）⇒ 本项**同步的是文档口径**，非改绑定。
- **端口登记**：[`inventory/ports.yaml`](../../inventory/ports.yaml) 新增 `managed/8888`（`scope: [A]` · `mode: on_demand` + `status: configured_but_stopped` ⇒ **未监听不算故障**，豁免"声明在用却没监听"的反向对账）。★ 这正是此前「**冲突必须先裁谁让位，才谈得上登记**」的兑现。
- **校验器**：`docker compose config`（**离线可解析**，无需 daemon）实测 `published: "8888"`。

**验收（本轮）**：`test_untested_index_sync.py` **ALL PASS**（`规范 6 份 · 索引 53 · todo 42 / partial 5 / retired 3 / boundary 3 · needs_decision 5` · `blocker 分布` 见上）；
`pwsh … _fm_golden_test.ps1` **429/0**；`rpc_check --only ports,inventory,adr,doclinks,md-tables,scripts` **PASS · 6 绿 / 0 黄 / 0 红**（`adr 12 份` · 真值表 **32 端口**）。

**本轮未做（如实登记）**：`O-111` 三站工具面实测（**需先 load 本地引擎**，触 `load-gate`）· `O-123` 的 **5 条暂缓**（U4×3 + U5×2；裁「**人工 public 摘要 + 出网卡**」，摘要与派发**未做**）· `ADR-0012` D2 的 `containers status` **未实现**。
**关联**：`OPEN-ISSUES.md` **O-118 / O-122 / O-123** · [ADR-0012](../../adr/ADR-0012-A站容器栈纳管.md) · [inventory/untested-index.yaml](../../inventory/untested-index.yaml) · [inventory/ports.yaml](../../inventory/ports.yaml)。

### 2026-09-30（续⑬） — **O-123 两裁落地**：`D7-CC #3`（相对根 = `runDir`）与 `#8`（采纳候选① + 强制回退）已写进规范本体

> **定位**：承 `续⑫` 的两条加固。本轮把 `O-123` 待裁的 **2 条**下裁，**裁定落在规范原文**（不只是索引 / 台账）。

| # | 裁定 | 落点 | 索引影响 |
|---|---|---|---|
| ③ | `path` 相对根定为 **相对 `runDir`**；实现 = **外壳注入**（产物文本 + 产物相对 runDir 的名字），**不新造 `root` 字段** | §未实测登记 **第 3 条**（首段重写 + "裁定落地状态"） | `needs_decision` **true → false** |
| ⑧ | `$product` 取 **卡 `evidence-manifest.subjects[].path`（相对 runDir）**，**取不到即回退**（`agent-output.txt` → `accept-output.txt` → exit 3） | §未实测登记 **第 8 条**（加"已裁"段） | 无（本就 `false`） |

★ **两裁共同的性质**：**只定"该怎么做"，未改代码** ⇒ 两条 `state` 仍 `todo`（= "**已裁 + 待实现**"）。这是本仓既有形态（同 U1 #8）。
★ **口径变化（唯一）**：`needs_decision` **7 → 6**；索引**仍 53 条**、`state` 分布不变。

**验收**：`test_untested_index_sync.py` **ALL PASS**（`needs_decision 6`）；`py -3.12 ops/rpc_check.py --quick` ⇒ **PASS · 38 绿 / 2 黄 / 0 红**。
**关联**：`OPEN-ISSUES.md` **O-123**（`needs_decision` **7 → 6**；**`#4` 未动**）· [D7-PROTOCOL-CONCLUSION-CONTRACT.md](./D7-PROTOCOL-CONCLUSION-CONTRACT.md) §未实测登记 **第 3 / 8 条** · [inventory/untested-index.yaml](../../inventory/untested-index.yaml) · 提交 `857b26a`（续⑫）。

### 2026-09-30（续⑫） — **O-123 第二轮续证**：#3/#8 各自被加固（"相对根"的自洽解 = `runDir`；产物身份 = "卡已声明、review 不读"）

> **定位**：承 `续⑪` 的「#3 候选集已收缩、#8 已登记」。本轮仍**不下裁**，仅**继续细化分析调研** —— 沿 #8 追问"到底缺什么"，并回填 #3。

**③ `D7-CC #3` 的第二轮 —— 把"注入什么"定到具体字段**

| 面 | 读数（E1） |
|---|---|
| `$card` / `$fm` | `Invoke-Review` L4790 `$card`（卡路径）· L4804 `$fm = Get-FrontMatter $card`（**含 `evidence-manifest.subjects`**） |
| `$runDir` | L4828 `Get-ReviewRunDir` ⇒ **绝对路径**（`<projRoot>/agent-out/<runId>`） |
| ★ 产物已在 runDir | 收集段 L2998 `$stDst = Join-Path $runDir $rp` ⇒ 站上 `$W/<state>` **scp 到 `$runDir/<subjects[].path>`** |

⇒ ★★ **结论**：四个已知量**全在手**；`path` 相对根的**唯一自洽解 = `runDir`**（三条独立理由：判官看到的产物就在 runDir / 卡声明的 `subjects[].path` 本就相对 runDir / `line_range` 只能相对判官看到的那个文本）。**"相对仓根"仍不可实现**（结论不变）。

**⑧ 第 8 条的第二轮 —— 卡其实【声明了】产物身份，是 review 没读**

| 面 | 读数（E1） |
|---|---|
| 卡面 | `dec-cc` 卡 `evidence-manifest.subjects[0] = {name: dec-cc, path: dec-cc.md, state: out/dec-cc.md}` |
| 已被谁用 | **收集链路**（L2939-3001 过 `Test-EvmStatePull` 白名单 ⇒ scp 到 `$runDir/dec-cc.md`） |
| ★ 谁没用 | **`Invoke-Review`**（L4920 硬编码 `agent-output.txt`）—— 而 `$fm` 在 L4804 **已经读过** |

⇒ ★★ **候选集收窄为四选**：① 取 `$fm['evidence-manifest']['subjects'][].path`（**零新机制**）/ ② `--product` 显式入口 / ③ 从卡 `accept:` 反推（正则脆弱，次优）/ ④ **不做 + 写明"判官只看终端回显"为已知边界**。

★ **门禁实测旁证（同日 `--quick` 的 `evidence` 明细）**：存量 gap 有 **`dogfood/202609292038295460`：subject `xrev2` 声明的 `xrev2.md` 不在 runDir** ⇒ **候选① 的"已在 runDir"前提不成立**，**须带回退**（否则 `Invoke-Review` 走 `REVIEW_PRODUCT_MISSING` exit 3）⇒ ★ 由此见得 **声明 → runDir** 这一跳**有审计**（`evidence` 判据族），而 **runDir → 判官** 这一跳**无任何判据**（`review.$product` 不在审计内）。

★ **如实标注**：全仓**零个真实 `review.json`** ⇒ 后果**系从实现 + 卡面 + 一条真实 runDir 推定，不是跑出来的**。
★ **本轮不新增条目**（#3/#8 各自加固）⇒ 索引**仍 53 条**、`state` 分布与 `needs_decision` **不变**。

**验收**：`py-tests`（`test_untested_index_sync.py` 双向对账 **PASS**，索引 **53** 不变）；`py -3.12 ops/rpc_check.py --quick` ⇒ **PASS · 38 绿 / 2 黄 / 0 红**。
**关联**：`OPEN-ISSUES.md` **O-123** · [D7-PROTOCOL-CONCLUSION-CONTRACT.md](./D7-PROTOCOL-CONCLUSION-CONTRACT.md) §未实测登记（**第 3 条第二轮 + 第 8 条第二轮**）· [inventory/untested-index.yaml](../../inventory/untested-index.yaml) · `ops/station-bin/agent-cli.ps1`（`Invoke-Review` L4787-4941 / 收集段 L2939-3001 / `Merge-EvidenceSubjects` / `Test-EvmStatePull`）· `spec/d6-agent-standard/dogfood-cards/dec-cc-three-undefineds.md`。

### 2026-09-30（续⑪） — **O-123 续证**：`D7-CC #3` 的候选集被收缩（"相对仓根"对判官不可实现），并**续证出第 8 条缺口**（被评产物身份）

> **定位**：承 `续⑩` 的「#3/#4 取证已完成、待裁」。本轮**不下裁**，只**继续细化分析调研** —— 沿 #3 往下追问"判官到底能不能拿到一个根"。

**③ `D7-CC #3` 的续证 —— 把"未定义"升级为"对判官不可定义"（三条新证据）**

| 面 | 读数（E1） |
|---|---|
| 提示词字段 | `Build-JudgePrompt` 只替换 `{{RUBRIC}}`/`{{TASK}}`/`{{CARD_BODY}}`/`{{ACCEPT}}`/`{{GOLDEN}}`/`{{RUN_ID}}`/`{{PRODUCT}}` —— **无任何根字段** |
| ★ `-cardPath` | `Invoke-Review` 传了 `-cardPath $card`，而函数**收下从不使用** ⇒ **死参数**（判官连卡文件在哪都不知道） |
| 唯一路径来源 | `{{ACCEPT}}` 里卡的 `accept:` 串（`test -f out/…`）⇒ 那是**站上工作目录**相对（远端 `cd "$W"`）⇒ **既非 runDir 也非仓根** |

⇒ ★★ **候选集收缩**：`dec-cc` 卡所选的「**规定 path 相对仓库根**（`git rev-parse --show-toplevel`）」**在本架构下不可实现**（判官**无从知道**仓根）；「新增 `root` 字段」同理。**可实现方向只剩一个 = 由外壳把它知道的东西注入提示词**。

**⑧ 第 8 条新缺口 —— 被评产物的身份未定（★ 是 #3/#4 的前置）**

| 面 | 读数（E1） |
|---|---|
| 实现 | `$product = Join-Path $runDir 'agent-output.txt'`，回退 `accept-output.txt` —— **无第三来源、无 `--product`**（**不看卡声明**） |
| 它是什么 | 站上 `opencode run … > out/.agent-output.txt 2>&1` ⇒ **终端回显**（stdout+stderr） |
| ★ 实测 | 真实 runDir 的 `agent-output.txt` = **235 字节**（与 `.agent-run.json` 的 `output_bytes` 一致）= ANSI 色码 + `$ mkdir -p out` + `← Write out/dec-cc.md` + `DOGFOOD_DECCC_OK` |
| ★ 同目录 | 躺着卡声明的产物 `dec-cc.md`（卡 `accept:` 校验的正是它）⇒ **判官看不到它** |

⇒ ★★★ **链**：**#8（判官看不到被指的文件）⇒ #3（臆造的名字没法归一）⇒ #4（臆造的行号没法校）** —— **"意见带位置、可核验"这一契约基石，在本架构下三层都不成立**。

★ **如实标注**：全仓**零个真实 `review.json`** ⇒ 上述后果**系从实现 + 一条真实 runDir 推定，不是跑出来的**。

**验收**：`py-tests`（含 `test_untested_index_sync.py` 双向对账 **PASS**，索引 **52 → 53**）；`state` = todo **42 → 43** · partial 5 · retired 3 · boundary 2 · **`needs_decision` 7**（未变）。
**关联**：`OPEN-ISSUES.md` **O-123** · [D7-PROTOCOL-CONCLUSION-CONTRACT.md](./D7-PROTOCOL-CONCLUSION-CONTRACT.md) §未实测登记（**第 3 条续证 + 新增第 8 条**）· [inventory/untested-index.yaml](../../inventory/untested-index.yaml) · `ops/station-bin/agent-cli.ps1` 的 `Build-JudgePrompt` / `Invoke-Review` · `ops/station-bin/review/judge-prompt.tmpl` · 同日前十条 `续①–⑩`。

### 2026-09-30（续⑩） — **O-123 续**：`D7-CC #3/#4` 两条的**取证已完成**，并**取证出一条第 7 项新缺口**

> **定位**：承 `续⑨` 的「待下一步 2 条」。用户裁「#3 先跑取证 / #4 先裁语义」⇒ 本轮**执行取证**。

**③ `D7-CC #3`（`path` 相对根）—— ★★ 取证把"文档没写清"升级为"机制会静默失效"**

| 面 | 读数（E1） |
|---|---|
| **契约要求** | 本文 §3：以 `path` + `line_range`（**归一化后**）对齐成"锚点" |
| **实现** | `Merge-JudgeFindings` 的键 = `("{0}\|{1}" -f path.Trim(), line_range.Trim())` ⇒ ★ **只有 `.Trim()`** |
| **全仓归一化函数** | ★ **0 个**（`agent-cli.ps1` 内 `Normalize-` / `归一化` **零命中**） |
| **判据对 `path`** | `Test-FindingShape` **只判 `IsNullOrWhiteSpace`** ⇒ 绝对路径 / `./x` / 裸名 `a` **全部合法** |
| **提示词** | `judge-prompt.tmpl` 只写 `"path": "相对路径"` ⇒ **未说相对谁** |
| ★ **夹具实证** | 同一套 `cc-*` 里 `cc-1` 用 `'ops/a.py'`、`cc-2…cc-12` 用 `'a'` —— **两者都通过** |
| **真实产物** | ★ **全仓零个 `review.json`** ⇒ 契约**从未产出过真实产物** |

⇒ ★★ **后果（可证，非推测）**：`./ops/a.py` 与 `ops/a.py`、`Ops/A.py` 与 `ops/a.py` **会各自成为不同锚点**
⇒ 同一处意见**永不合并** ⇒ **`consensus` 静默失效、三分类退化为全 `unique`** —— 而"区分共识与孤例"正是本契约存在的理由。

★★★ **【超出规范原记的新缺口 ⇒ 已登记为第 7 条】**：原文只记"相对根**未定义**"；取证发现 **「契约要求归一化、实现只做 `Trim()`」= 契约↔实现不一致** —— **即使把相对根定死，缺归一化仍会裂开**。
⇒ 已就地写入 [`D7-PROTOCOL-CONCLUSION-CONTRACT.md`](./D7-PROTOCOL-CONCLUSION-CONTRACT.md) §未实测登记 **第 7 条** + 索引同步（**51 → 52 条**）。

**④ `D7-CC #4`（`line_range` 越界）—— ★★★ 取证发现它【与 #3 耦合】，这改变了裁定结构**

| 面 | 读数（E1） |
|---|---|
| 实现 | `Test-FindingShape` 正则 `^L\d+(-(L\d+)?)?$` ⇒ **纯形态** |
| ★ 代码注释 | **自己写明**「**不读文件核对行数** —— 见契约 §未实测登记 4」⇒ **该缺口有明确代码主** |
| 函数签名 | `param([object]$Finding)` ⇒ **无文件/行数入参**（纯函数） |
| 夹具 | `cc-1..cc-16` **无一条测越界**（纯函数无从测）⇒ 要做"越界即无效"，**夹具形态也得变** |

⇒ ★★★ **关键推论**：**在相对根未定之前，「越界」根本无从判定** —— **校验器不知道该打开哪个文件**
⇒ **「无效」与「警告」两个语义在本架构下都落地不了，只剩「不可判」可用**（与「**不可判 ≠ 通过**」同族，`O-22`/`O-119` 同口径）。

★ **如实标注**：全仓**零个真实 `review.json`** ⇒ 上述后果**系从实现与夹具推定，不是跑出来的**。

**验收**：`py-tests` **47/47**（含 `test_untested_index_sync.py` 双向对账 **PASS**，索引 **51 → 52**）· `--quick` **PASS 38 绿/2 黄/0 红** · `ledger-status` 仍开着 **6**。
**关联**：`OPEN-ISSUES.md` **O-123** · [D7-PROTOCOL-CONCLUSION-CONTRACT.md](./D7-PROTOCOL-CONCLUSION-CONTRACT.md) §未实测登记（**新增第 7 条**）· [inventory/untested-index.yaml](../../inventory/untested-index.yaml) · `ops/station-bin/agent-cli.ps1` 的 `Test-FindingShape` / `Merge-JudgeFindings` · `ops/station-bin/review/judge-prompt.tmpl` · `ops/station-bin/_fm_golden_test.ps1` 的 `cc-*` · 同日前九条 `续①–⑨`。

### 2026-09-30（续⑨） — **O-123 登记**：`untested-index` 的 9 条 `needs_decision` 取证（第一刀）⇒ **◐ 部分闭环（裁定待人）**

> **定位**：`OPEN-ISSUES.md` **O-123**（文档治理/未实测 · P2）—— 用户指令「分析如何闭环」，并裁定**第一刀 = 先裁那 9 条 `needs_decision`**。★ 本轮做的是 **Phase 1 档位核验 + Phase 2 派发取证**；**Phase 3 = 你逐条裁**（下表即摊开面）。

**★ Phase 1（档位核验）—— 它推翻了"3 卡"的预估**

`inventory/sensitivity.yaml` 里 **U3 / U5 / U4 / D7-CONCLUSION-CONTRACT 四份原未登记** ⇒ 按 `default_tier: local-only`（fail-closed）兜住 ⇒ 9 条里只有 1 条在已登记 public 面。逐份核验后：

| 规范 | 处置 | 依据 |
|---|---|---|
| `U3-EDGE-FORMAT` | ★ **补登记 public** | 内容源自**已登记 public 的卡面**（`dogfood-cards/` 整目录 = public）⇒ 与 `U1` **同款定档理由** |
| `D7-PROTOCOL-CONCLUSION-CONTRACT` | ★ **补登记 public** | 与已 public 的 `D7-PROTOCOL-CONTRACT` **同族同批**；主体为本仓自产契约设计；唯一外引 = **arXiv 公开论文** |
| `U4-INVALIDATION-RULES` | ⚠ **维持 local-only** | 原文明写「规则原文 = **Ontoly RFC-0002**」⇒ **他方材料** |
| ★ `U5-TRUST-BASIS` | ⚠ **维持 local-only**（**推翻我上一轮的初判**） | 含**他项目内部实现细节**（`FixMemory` / `discoveries/` / `run_p0a_v2_batch`）**且无 public 载体可引** ⇒ **先例不适用**，fail-closed |

⇒ **public 11 → 13**；**出网卡从 3 张修正为 2 张**。

**★ Phase 2（第十批 · 2 卡跨两站 · 已跑通）**

| 卡 | 覆盖 | 站 / 模型 | run | 结果 |
|---|---|---|---|---|
| [dec-cc-three-undefineds.md](./dogfood-cards/dec-cc-three-undefineds.md) | D7-CC 三条（`path` 相对根 / `line_range` 越界 / 三分类阈值 ≥2） | **A · `ultra-a`** | `202609300531207317` | ✅ `exit=0` |
| [dec-u1-truncation-mapping.md](./dogfood-cards/dec-u1-truncation-mapping.md) | U1-8（截断长度变更无映射路径） | **B · `lightning`**（**跨族**，照 J-1） | `202609300531207402` | ✅ `exit=0` |

⇒ `BATCH_DONE: 卡=2 · 失败或未完成=0`，**两卡各有自己的 runDir**（`O-116` 按卡切块在成功侧亦成立）。★ **本批覆盖 9 条里的 4 条**；**另 5 条（U4×3 + U5×2）暂缓**。

**★★ 主控独立复核（不采信模型自报）**
- `dec-u1` **可用**：6 节齐 · `^- ` 36 条 · 候选**逐条标了「判据 vs 纪律」**（卡要求）· 不确定项 6 条如实。⚠ 2 处表述瑕疵（步骤 2 把"要新建文件"与卡约束"只写一个文件"写在同一句再自我纠正）。
- ★ `dec-cc` **1 处实质错误 + 1 处内部矛盾 + 1 处与卡约束冲突**：**把给定材料的数字改错** —— 材料逐字写「生日阈值约 `2^64`，比 16 字符的 `2^32` 强」，产物写成「32 字符 ≈ **`2^128`**（比 16 字符 `2^64` 强）」⇒ **两数各放大 `2^64` 倍**（按 hex 字符数 n ⇒ 4n bit ⇒ 生日阈值 `2^(2n)` 复算：**材料对、产物错**）；且**同句**自述"具体数值未给出"⇒ **自相矛盾**；其步骤 5 要写 `out/dec-cc-evidence.md`，违反卡的"只产一个文件"。⇒ **可作线索、不可照抄**。

**★ Phase 3 —— 摊开给你逐条裁（7 条）**

| # | 条目 | 现状问题 | 候选（含 agent 建议，**仅供参考**） |
|---|---|---|---|
| 1 | D7-CC **`path` 相对根** | 契约要求 `path` 必填但**没规定相对谁**；文档自认最大未定项 | 甲：规定相对**仓根**（无 git 回退运行目录）· 乙：新增 **`root` 字段**显式声明 · 丙：什么都不做+写明约定 |
| 2 | D7-CC **`line_range` 越界** | 只校**形态**不校**行数**；"越界即无效"未裁 | 甲（**agent 建议**）：**保持纯函数**、越界降**警告 + 标记**（`out_of_bounds_suspected`）· 乙：**改为读文件、越界即无效**（代价：纯函数 → 需 I/O）· 丙：校验器**分两层**（配置开关） |
| 3 | D7-CC **三分类阈值 `≥2`** | 数值从**另一用途**推来，**无实测支撑** | 甲（**agent 建议**）：保留 2 + 新增可配 `consensus_min_judges` + 文档记"无实测支撑" · 乙：改为**动态 `ceil(J/2)`** · 丙：**跑最小实测**（历史夹具） |
| 4 | U1-8 **截断长度映射** | 无任何实现能把旧 `:16:` 映射到新 `:32:`；只能靠**口头纪律** | 甲（**agent 建议**）：**候选①（显式标注"旧代"）+ 显式映射表**（两阶段：无标注即**拒绝**不是警告）· 乙：候选②去自描述（⚠ **与 `D-25` 冲突**）· 丙：什么都不做 |
| 5-7 | **U4×3 + U5×2** | ★ **本批未取证**（档位未过） | 待选路线：**站内卡**（需 load 本地引擎）或 **人工 public 摘要** |

**验收**：`ledger-status` 数据行 **118 → 119**、**仍开着 5 → 6**（O-123 为 ◐）· `sensitivity` PASS（**public 11 → 13**）· 本批 `BATCH_DONE: 卡=2 · 失败或未完成=0`。★ **未起任何本地引擎**（两卡均走出网档）。
**关联**：`OPEN-ISSUES.md` **O-123** · [inventory/untested-index.yaml](../../inventory/untested-index.yaml) · [inventory/sensitivity.yaml](../../inventory/sensitivity.yaml)（补登记 2 条）· [tests/test_untested_index_sync.py](../../tests/test_untested_index_sync.py) · `O-80` / `O-116`（派发链）· `D7-P0-3` J-1（跨族）· 同日前八条 `续①–⑧`。

### 2026-09-30（续⑧） — **O-122 登记**：A 站 Docker/容器栈盘查 ⇒ **◐ 部分闭环（处置待裁）**

> **定位**：`OPEN-ISSUES.md` **O-122**（运维/治理 · P2）—— 用户指令「A 站 Docker daemon 检查一下是什么东西在跑」。★ 全部读数与三条风险**写在台账行内**，本节**只留索引** —— **不复制第二份**。

**一句话**：★ **A 站只有 `dockerd` 本体在空转（`Running: 0`，无任何容器）** —— 三个 unit（`docker.service`/`docker.socket`/`containerd.service`）**均 enabled**，自 **2026-09-16** 起 active ≈13 天，内存 50.9 M、13 天 CPU **2 min 42 s**。

**用途已查清（四条证据链）⇒ 它是「Agent 检索基础设施」的宿主**：`~/searxng/docker-compose.yml`（自建 SearXNG）· `~/.hermes/hermes-agent/optional-skills/research/searxng-search/`（hermes 的 searxng 检索技能，读 `SEARXNG_URL`）· 镜像 `mcp/paper-search` · hermes-agent 本体编排。★ 与本仓对得上：`PLUGIN-LEDGER` 的 **`web-searxng`**（⭐⭐⭐ 检索层）。

**三条风险/缺口**：**① 端口双重声明（latent）** —— searxng compose 写死 **`8080:8080`**，而 8080 是 **A 站推理引擎**的登记端口；★ 当前无冲突（8080 空闲 + searxng **容器已删** ⇒ 无自动重启风险），但**下次 `compose up` 会撞**。**② dockerd 与 containerd 生命周期不同步（根因未查）** —— dockerd 13 天 vs containerd 仅 1 d 19 h，且 **2026-09-28 09:45** dockerd 报 containerd 连接 **EOF**。**③ 两套 Docker 并存 + 配置双源** —— `docker-ce`（在跑）与 `docker-desktop`（装了未跑）；`daemon.json` 有**两份且 mirror 列表不同**（「同一事实两处表达」同族）。

★ **顺带结清 `O-121` 一条"未验"**：两份 `daemon.json` 均配了**国内 registry mirror** ⇒ 「直连 huggingface 不通但仍可能拉镜像」的**可能路径**。⚠ 仍只到"有配置"，**未实测拉取**。

★★ **本项最要紧的裁定 = `ports.yaml` 刻意【不登记】**：按该表自己的维护约定「**只登记实测过的端口；不确定的宁可不登记**」，searxng 当前**无监听且容器已删** ⇒ 现在登记**违反本表约定**；且按门禁「**跨组不得重叠**」约束，**searxng 一旦重起，8080 即变成跨 `managed`/`unmanaged` 的重叠声明 ⇒ 登记即 FAIL**。⇒ **必须先裁"谁让位"，才谈得上登记**（不能两个都写）。

**待裁两项**：① **8080 谁让位**（改 searxng 端口 / 接受现状并写明 / 删该 compose）；② **A 站 Docker 栈是否纳管**（与 `ADR-0004` 直接相关，现**不在任何管理面内**）。

**验收**：`ledger-status` 数据行 **117 → 118**、★ **仍开着 4 → 5**（O-122 为 **◐**，如实计入开着）。★ **本项只读**：未起/停服务、未删镜像容器、未改 compose、**未动 `ports.yaml`**；临时脚本在 `tmp/`（未入库）。
**关联**：`OPEN-ISSUES.md` **O-122** · 同域 **`O-121`**（kyuz0 容器路线）/ **`O-120`**（换栈）· `ADR-0004`（唯一管理面）· `inventory/ports.yaml` · `PLUGIN-LEDGER` · 同日前七条 `续①–⑦`。

### 2026-09-30（续⑦） — **O-121 登记**：`kyuz0/vllm-therock-gfx1151` 容器方案评估 ⇒ 裁「当前不引入」

> **定位**：`OPEN-ISSUES.md` **O-121**（栈/容器 · P2）—— 用户问「这个方案在本集群可行性 / 对比原生 vLLM」。★ 分析与对比**全在承载文档**里（[kyuz0 容器方案评估与现役 venv 对比](../../docs/research/2026-09-30_kyuz0容器方案评估与现役venv对比.md)），本节**只留索引** —— **不复制第二份**。

★★★ **本项最值钱的一条（纠正对比框架）**：**kyuz0 的容器与集群现役 `~/vllm-rocm` 不是"两条路线"，而是【同一条路线（TheRock）的两种封装】** —— 实测现役 venv 内含 `rocm_sdk` wheel **7.15.0** + **`amd_torch_device_gfx1151`** device 包 + `_rocm_sdk_libraries/lib/`（libhipblas/hipdnn/hipsolver/**librccl** 等整套 ROCm 库）。⇒ 真问题不是"容器 vs 原生"，而是「**社区策展的补丁容器**」vs「**AMD 官方渠道的 ROCm SDK wheel（三站逐字一致）**」。

**增量对账（6 条）⇒ 4 条无增量/封闭 · 2 条"可能有但未证"**：
**① 补丁 RCCL** ⇒ ❌ 无增量（本集群 RCCL **2.30.4** 已含官方 `gfx1151` 目标 + `rccl_lib_gfx1151.kpack`，**跨机 collective 已实测跑通**，见 `续⑥`）· **② vLLM gfx1151 device 补丁** ⇒ ❌ 无明确增量（venv 有 AMD 官方 device 包；⚠ **未逐行比对，属推断**）· **③ `tcmalloc` 防 shutdown 崩溃** ⇒ ◐ 可能有，**但本仓无对应症状** · **④ 策展模型表/benchmark** ⇒ ◐ 不可替代本仓 `model-eval` + `results-ledger` · **⑤ 容器化可复现** ⇒ ❌ 本集群以 venv + 三站逐字一致 + 门禁达成；且容器 = **新实体**（`ADR-0004`）· **⑥ RDMA 集群 TP=2** ⇒ ❌ 封闭（需 E810 + PCIe 槽）。

**E1 前置盘点（三站）**：**Ubuntu 24.04**（**非 Fedora**）⇒ 走 kyuz0 须先补 **Distrobox**（三站均无）· `docker` CLI 三站全有（**29.8.1**）但 **daemon 仅 A 站 active**（B inactive / C 无 unit）· 磁盘 **773 G / 790 G / 1.1 T** 可用 · `podman`/`toolbox` 全无 · HF 缓存仅剩 **48 KB 元数据**（权重已删）。

★ **判定**：**技术可行，但当前不必要** —— 核心增量已被 AMD 官方渠道覆盖。★ **若日后"容器化 vLLM"成真需求：应先评 `ROCm 官方容器`（`rocm/vllm-dev`，官方文档明载支持 gfx1151/gfx1150）**，而非此第三方镜像。★ **再触发条件**：① `ADR-0004` 立项 + `ADR-0011` 解除暂缓；② 容器化成为真需求；③ 出现 vLLM shutdown 崩溃症状。

**验收**：`--quick` **PASS · 38 绿 / 2 黄 / 0 红** · `ledger-status` 数据行 **116 → 117**、**仍开着 4**（★ O-121 **出生即闭环**）。★ **未碰站上任何配置**（未起容器服务、未拉镜像、未装 Distrobox）；临时脚本在 `tmp/`（未入库）。
**关联**：`OPEN-ISSUES.md` **O-121** · **`O-120`/RCCL 评估**（共用底层事实，不复制）· **`ADR-0011`**（vLLM 决策真值源 + 共同第一道门「零 GGUF 支持」）· **`ADR-0004`**（治理闸）· `AMD395 互连调研 §2.3` · `model-eval` · 同日前六条 `续①–⑥`。

### 2026-09-30（续⑥） — **O-120 登记**：RCCL（AMD 集合通信库）三问调研 ⇒ 裁「当前不部署（无消费方）」

> **定位**：`OPEN-ISSUES.md` **O-120**（栈/并发 · P2）—— 用户问「AMD 官方 RCCL 部署方案 / 模型支持度 / 当前集群是否有必要部署」。★ 数据与三问结论**全在承载文档**里（[RCCL 部署方案与本集群必要性评估](../../docs/research/2026-09-30_RCCL部署方案与集群必要性评估.md)），本节**只留索引** —— **不复制第二份**。

**三问一句话**：① **部署方案** = 非独立产品，随 ROCm 组件交付；ROCm 10 起 TheRock **按架构分包** ⇒ 本集群实装 `amdrocm-rccl10.0-gfx1151`（设备侧 kernel 在 `rccl_lib_gfx1151.kpack`）；传输面含 `socket` ⇒ **无 RDMA 也能跑**。② **模型支持度 = 伪命题** —— RCCL 在**框架层**被调用、不感知模型；真正变量是**引擎**（本集群只有 vLLM 会用，而它已由 `ADR-0011` 暂缓）。③ **必要性 = 当前不必要**（**不是做不到，是没有消费方**）。

**三条 E1 读数（站上实跑）**：
- ★ **装机盘面**：**B/C 已装**（`amdrocm-rccl10.0-gfx1151` 10.0.0-4，2026-09-28 随 rocm-migration 落地）· **A 站未装** ⇒ **三站不同构**（新登记的不一致面）。
- ★★ **单机能用**：`init_process_group('nccl')` + `all_reduce` **跑通**（`ALLREDUCE_OK sum=8.0`，RCCL **2.30.4** / gfx1151）。
- ★★ **跨机也能用（v2.0 修正）**：双机 B+C 经 USB4 直连段（`10.10.11.0/24`）**实测跑通** —— 双 rank `ALLREDUCE_OK sum=98304.0`、`exit=0`、**9 个 channel** 全走 `NET/Socket`、接口正确选中 `thunderbolt1/0`、延迟 **median 182.0 / 181.2 µs**（n=20，64 KiB bf16）。

★★★ **本轮最重要的一条：v1.0 的"跨机挂死"是【本测自身】的缺陷，不是环境问题（已就地更正）**
Scott 提供外部诊断清单后，我按第 2 条（**网卡绑定 ⇒ 静默挂死**）回头查自己的测试，发现：**v1.0 设的 `RCCL_SOCKET_IFNAME` 在 librccl 里根本不存在**（实测 `NCCL_SOCKET_IFNAME` 出现 3 次、`RCCL_SOCKET_IFNAME` **0 次**）⇒ 接口走**自动选择** ⇒ **静默挂死**。改用 **`NCCL_SOCKET_IFNAME`** 后**立刻跑通**。
★ **方法教训（已写进承载文档 §2.3）**：**设环境变量前必须先在库里 grep 名字** —— **"变量不存在"不报错、只静默失效**，并把人引向错误的根因。
★ 清单其余条目**逐条对账**（承载文档 §6）：**实测排除 1**（"RCCL 缺 gfx1151 原生支持" —— 本集群已被 ROCm 10 跨过）· **命中并据此修好 1**（网卡绑定）· **版本命中但形态未验 2**（CWSR 需 6.19-rc1：本机 6.17 在风险区间；**ROCr 1.21：实测命中该版本**）· **部分不成立 1**（`iommu=pt` 非本集群 collective 必要条件）· **不适用 3**（RCCL 2.27.7/gfx1201 死锁 · GIN 0 字节 · Ray 僵尸 Raylet —— 本测**不用 Ray**）· **未验 3**。

★★ **另一条就地更正**：[AMD395 互连调研](../../spec/rpc-optimization/research/AMD395分布式推理高性能互连方案调研.md) §2.3 的「**定制 librccl.so 补丁**（RCCL 对 gfx1151 仍有补丁需求）」**已过期** —— 那只对 **ROCm 7.x 线**成立（社区记录 2026-02）；本集群 ROCm 10.0 / RCCL 2.30.4 **有官方 gfx1151 目标 + 分架构包**。★ 顺带澄清一处易误读：ROCm 7.1.0 release notes 的"gfx1150/gfx1151 support enabled"归属 **ROCgdb**，**不是 RCCL**。

★ **两条 RCCL 自报前置（未修，如实登记）**：内核命令行**缺 `iommu=pt`**（RCCL 逐字警告"可致 hang 或不稳"；**B 缺、C 是 `amd_iommu=off`** ⇒ **非单变量**）· `RCCL_USE_AMD_SMI_LIB` 未设 ⇒ fabric 未启用。★ **但 v2.0 实测：未修 `iommu=pt` 也跑通了** ⇒ 它**不是**本集群 collective 的必要条件。

**验收**：`--quick` **PASS · 38 绿 / 2 黄 / 0 红** · `ledger-status` 数据行 **115 → 116**、**仍开着 4**（★ O-120 **出生即闭环** ⇒ **不改变开着数**，只增一行）。★ **未碰站上任何配置**（未装/未卸包、未改内核参数）；临时脚本在 `tmp/`（未入库），站上临时件与进程已清。
**关联**：`OPEN-ISSUES.md` **O-120** · **`ADR-0011`**（换栈前提 = 再触发条件）· **AMD395 互连调研 §2.3**（就地更正）· **CIRU/Skulk 调研 §2.2**（RCCL socket 341 µs 参照）· `rocm-migration DESIGN` D3 · `ADR-0004` · 同日前五条 `续①–⑤`。

### 2026-09-30（续⑤） — **O-110 闭环**（走 spec workflow：**补测 → 质量审计 → 逐条裁定 → 回写**）

> **定位**：`OPEN-ISSUES.md` **O-110**（并发/判据 · P2）—— 「`O-18` 的适用性未经『换栈 / 换模型规模』复核」。★ 数据与推演**全在承载文档**里（[O-110/O-112 实测文档](../../docs/research/2026-09-28_O-110同站并发实测与O-112单机容量核验.md) §3.3–§3.4 / §4.1 / §5 / §8），本节**只留索引** —— **不复制第二份**。

**本轮做了什么（D-2 段补测，站上 E1 实跑）**：把 `O-18` 的原始形态**按同量纲复刻** —— 同站（B）· 同模型（**gpt-oss-120b-MXFP4**，`-c 131072`，studio 默认 `--parallel 4`）· `/v1/chat/completions` · **墙钟**口径 · **每请求提示唯一**（排除 prompt cache）。装/卸只走 `ops/cluster.py`（`ADR-0004`），**测完已 unload 还原（三站 STOPPED）**；客户端是站上临时脚本（`tmp/`，**未入库**）。

**三条读数（两轮独立复跑：长提示档中位几乎逐位一致 · 短提示档有几 % 散布 ⇒ 比值稳定、绝对值别读到小数第二位）**：
- ★ **换口径后 `O-18` 的「~2.8×」站得住** —— 单请求 C=1→C=2 劣化 **1.95–2.75×**（短提示 **2.0–2.2×** · 长系统提示 **2.0×** · 长上下文 **2.13× / 2.48× / 2.75×**，**随上下文单调上升**）。
- ★★ **decode 口径的「聚合 +32–48%」在 prefill 主导负载下反号** —— 4 请求**总墙钟不降反升**（**+6% / +24% / +38%**）。
- ★ **口径冲突 = 量纲，不是矛盾**：decode 口径只算 decode（batching 摊薄权重读取 ⇒ 划算）· 墙钟含 prefill + 排队（prefill 无法互相摊薄 ⇒ 不划算）。

**判定修订**：**H-1a 收窄为「仅对 decode 主导负载成立」** · **H-1b ✅**（两口径同向）· **H-1c ✅ 且分档轴不止一个**（**上下文长度**是比模型规模**更强**的解释量）。⇒ `O-18` 的「跨站各 1 并发」纪律**不变**，改的是**物理依据**（已回写 `O-18` 行 + 承载文档 §4.1）。

**余项逐条裁定（用户逐条裁）**：**④ 已做** · **⑤ 记「待触发」**（**不是"不做"** —— `ADR-0011` 已裁 A4/vLLM 暂缓 ⇒ **前提不存在**）· **⑥ 已做**（按**实分 ctx** 口径）· **② Q3 档真实加载 = 裁「不做（明确关闭）」**（算术已给负数结论 + (B) 路线已可单机 ⇒ 不值一次 119 GiB 下载；**不设再触发条件**）· **③** `n_ubatch` 扫描**如实留着**（判据刻意固定默认）。

★ **顺带两处就地更正**：① `O-110` 原文「**300B 级层分布大模型**」**系误记** ⇒ 真值 = [BLINDSCAN-v2 §8.7.6](./BLINDSCAN-v2-orchestration.md)「**gpt-oss-120b-MXFP4 双机同权**」（**这才是本轮能直接对照的原因**；真值只在该文件，台账只放更正 + 指针）；② `cache_prompt:false` **被 studio 代理吞掉**（实测）⇒ 想强制全量 prefill 只能靠"每请求唯一提示"。

**验收**：`ledger-status` 仍开着 **5 → 4**（O-110 转 ✅）· `--quick` **PASS · 38 绿 / 2 黄 / 0 红** · `doclinks` 失效 0。
**关联**：`OPEN-ISSUES.md` **O-110** / **O-18**（口径限定已回写）· `ADR-0011`（换栈前提）· `BLINDSCAN-v2 §8.7.6`（O-18 读数真值源）· `ADR-0004`（唯一管理面）· tracker `§1.8-C`（H-1 出处）· 同日前四条 `续①/②/③/④`。

### 2026-09-30（续④） — **O-112 改判收口**：REAP 的 `D-2` 裁「不做（不立项）」

> **定位**：`OPEN-ISSUES.md` **O-112**（模型/容量 · P2）。★ 本条是**改判**（不落地）：依据已在**台账行内写全**，本节只留索引 —— **不复制第二份**。

**收口**：两段判据里 **D-1a 已实测**（2026-09-28）· **D-1b 已由 `O-114` 否决** ⇒ **只剩 `D-2`**（「(A) REAP 的真正对照」）；而 `REAP` / `剪枝` / `单机化` 在 `adr/`、`spec/upstream-tracker/`、`DECISIONS.md` **零命中** ⇒ `D-2` **从未立项、无裁定覆盖** ⇒ 本轮裁 **不做 `D-2`（不立项）**。

**五条依据**：① **(B) 路线（原模型 + Q2/IQ2，77–90 GiB）单机可行且留 ≥29 GiB**（D-1a 实测）· ② 本仓既裁「**若 B 已够，则 A 无必要**」· ③ 收益④（速度）**大概率不升甚至降**（REAP **只删专家、不改 top-k** ⇒ 单机须一站读全部活跃权重 ⇒ 带宽 **≈2×**）· ④ 代价⑥：上 (A) 必须先过 `ADR-0004` + `EV-4`，且 **不可逆** / **上游不支持** / **自维护线 1 → 2 条** / 校准 ≈**2×10⁸ tokens 前向** · ⑤ 本仓纪律「**不做也是一种结论，必须写下来**」。

★ **如实标注（不许读过头）**：② 里那个"够"**只在容量面成立** —— **准确率面从未实测**（D-1b 同题对照**已由 `O-114` 裁为不做**）⇒ 本条的准确措辞是「**不再投入去验 A（REAP）**」，**不是**"B 已足够"。
★ **再触发条件**：(B) 路线实测**不够用** · 或 **引擎迁移**（tracker `§1.8`）改变单机 / 双机前提。★ **无需过 ADR**（不新增栈、不新增实体）。

**验收**：`ledger-status` 仍开着 **6 → 5**（O-112 转 ✅）。**关联**：`OPEN-ISSUES.md` **O-112** / **O-114**（D-1b 否决）· [O-110/O-112 实测文档](../../docs/research/2026-09-28_O-110同站并发实测与O-112单机容量核验.md) · `ADR-0004` / `EV-4` · tracker `§1.8` · 同日前三条 `续①/②/③`。

### 2026-09-30（续③） — **O-07 改判收口**：zen 限额（429/quota）触发源已撤 ⇒ 裁「不适用」

> **定位**：`OPEN-ISSUES.md` **O-07**（验证 · P2 · 事件驱动）。原文 = 「zen 限额真实触发未发生（退出码 7 定义置位）」。
> ⚠ 本条是**改判**（非落地）：依据已在**台账行内写全**，本节只留索引 —— **不复制第二份**。

**裁定**：**触发源已撤 ⇒ 本条不适用**。依据（三处）：
- **zen 已撤出运行时路由**（`agent-cli.ps1` ROUTE_TABLE 注释 · 2026-09-24 起三档维持 openrouter）⇒ 该事件**不可能经派发路径触发**；
- **`exit 7` 在代码里无触发点**（`exit 7` 检索无命中）；429/quota 的**现实形态已转移**到 **OpenRouter free 档**
  （20 RPM + 指数退避 —— `ADR-0003` / [ops/cluster_egress.py](../../ops/cluster_egress.py) / `agent-cli.ps1` 的 RPM gate），**不走 exit 7**；
- 复核由用户提问触发（"opencode 是否已默认接 openrouter / 免费档要不要登录"）⇒ 顺带**三站只读实测（2026-09-30）**：
  `opencode` **1.18.25** 三站同 · `auth list` = **0 credentials** 三站同（A 的 `auth.json` 2 字节空、B/C 不存在）·
  `~/.config/rpc/openrouter.key` **三站各有**（73 B，2026-09-21）· `opencode.jsonc` **md5 三站全一致** `755975db…`（与 09-24 同值 ⇒ 未变）。

**同日三处同步（同一事实的三个表达，一次收齐）**：[ARCHITECTURE.md](./ARCHITECTURE.md) 退出码表该行
（`定义置位，未真实触发` → **路径已撤 ⇒ 不适用**）· `agent-cli.ps1` 的 zen full-id 注释
（原"补 `opencode auth login` 即可用"系**已推翻**的旧归因 ⇒ 改为"**它要的是 tty，不是凭据**"）·
台账 O-07 状态格（`⏳ 待真实触发` → `✅`）。

**验收**：`ledger-status` 仍开着 **7 → 6** · `ps1-golden` **424/0**（含 `o117` 守卫 —— 新注释**整句无 backtick**，刻意避开 `O-117` 同族）·
`syntax`（.ps1 15/0）· `--quick` **PASS · 38 绿 / 2 黄 / 0 红** · `doclinks` 失效 0。
★ **未碰站上**：`agent-cli.ps1` 不在 `STATION_BINS`（9 件）⇒ 不需三站同步。

**关联**：`OPEN-ISSUES.md` **O-07** · `ARCHITECTURE.md` 退出码表 · `agent-cli.ps1` ROUTE_TABLE ·
`ADR-0003`（OpenRouter 限速与配额）· **`O-43`**（zen 稳定性采样 —— 本条的近邻）· 同日前一条 `2026-09-30（续②）`（O-102 行尾射程闭环）。

### 2026-09-30（续②） — **O-102 行尾漂移闭环**（走 spec workflow：设计 → 实施 → 质量审计 → 回写）

> **定位**：`OPEN-ISSUES.md` **O-102**（工程形态/编码 · P3）。走**同型先例** `O21-ctx-closure-verification.md`
> 的报告体裁 ⇒ 新增 [O102-line-ending-closure-verification.md](./O102-line-ending-closure-verification.md)。
> ⚠ 全文（证据表 / 反例 / 射程声明）在报告里，本节只留索引 —— **不复制第二份**。

**复测推翻原登记的一半**：O-102 的三条"值得登记"里，**①「约定未声明」与 ③「既不可判也不可见」在它登记之后才被消掉**
（`.gitattributes` **2026-09-29 立**，commit `fc1ae8f`；`gates` 按字节比对 + 2026-09-29 实测抓到过假红）
⇒ 原文那句「**无 `.gitattributes`（`Test-Path` = False）**」**已过期**。

**残留收敛为一个可执行缺口并已修**：`.gitattributes` 射程漏 `ops/` 下其余 shell ——
`ops/llama-serve-instance`（34 行全 CRLF）· `ops/lm-download/*.sh`（3 个全 CRLF）；
★ **天然对照**：**同名**的 `ops/station-bin/llama-serve-instance` = 全 LF（在射程内）。
修复 = **单文件**（`.gitattributes`：`ops/station-bin/*` → `**`；新增那两类）+ 强制重落 4 件
（修复前 `i/lf w/crlf` ⇒ `git status` **只剩 `.gitattributes`** ⇒ **无内容 diff**）。

**审计（读数）**：先验红 `i/lf w/crlf` 4/4、CRLF=34/7/11/16 ⇒ 后验绿 `w/lf`、CRLF=0 ·
**变异自证**（`.git/info/attributes` 反向覆盖 `eol=crlf` ⇒ 强制重落 ⇒ **CRLF=34**；撤除 ⇒ 裸 LF=34）·
门禁 `--quick` **PASS · 38 绿 / 2 黄 / 0 红** · `syntax`(.sh 414/0) · `scripts`(未登记 0) · `doclinks`(失效 0)。
★ **写下一个反例**：`git checkout --` 与 `git checkout-index -f` **都不会**重落 ⇒ 必须"先移除再检出"。

**射程声明（含"不做"的裁定）**：射程 = 会被部署/执行的件；★ `archive/**` 与 `tests/b5q/**` 已裁**不处理**
（不面向执行）；⚠ 仍留着：全仓 `w/lf`/`w/crlf` 并存 · `w/mixed` 仍产生 · `ops/` 下 `.py` 仍 `w/crlf`。
**改判**：原文「未验（推测）⇒ 将来加字节判据会假红」⇒ **已验**（`gates` 就是，且已兑现一次）。

**关联**：`OPEN-ISSUES.md` **O-102**（状态已改 `✅`）· 前置 commit `fc1ae8f` · 判据 `gates` · 报告 `O102-line-ending-closure-verification.md`。

### 2026-09-30 — **A2 读数刷新 + 锚定段落地**：`executor-trace` 补第三段判据（原「runtime 验收未实测」收口）

> **定位**：接 [A-LIST-LANDING-PLAN.md](./A-LIST-LANDING-PLAN.md) **§2.4 读数刷新**。A2 落地时（2026-09-29）登记的
> 「runtime 验收**未实测**」有**两半** —— ① 真派发后**留痕件齐** ② **与产物哈希交叉锚定** ⇒ 本次逐半处理。

**① 读数刷新（发现的是一处「同一事实两处、一处过期」）**：§2.4 表 A2 行仍写 `覆盖：runDir 含该件 0 个`，
而门禁实测已是 **11 个（齐段 11）**（2026-09-29 落地时确为 0；此后经 7 个吃狗粮批真派发 ⇒ 已有对象）
⇒ 就地改写 + 新增「§2.4 读数刷新」块；**同一条事实的其余副本一并收**（`capability-inventory.yaml` 的
`executor-trace` 行 · 门禁 `CHECKS` 的 `fix` 自述）。⚠ **本日志旧条目不动**（只增不改）⇒ 旧读数留在
`2026-09-29（续⑤）` 章内，属「当时的真值」。

**② 锚定段落地（原缺口 = §2.2 要求的后半「与产物哈希交叉锚定」无判据）**：`ops/rpc_check.py` 的
`check_executor_trace` 由**两段**升为**三段**：
- ① 执行体**不得自报**哈希（`[artifact] hashes=` 必须 `main-side`；否则 **FAIL** —— 与 `chain=uncore` 同族）；
- ② 留痕件 `ts=` 必须 **== runDir 名**（归属不符 ⇒ **FAIL**，`O-57` 同族）；
- ③ 主控侧须有该次哈希记录（`.agent-run.json` 的 `content_digest`；**缺 ⇒ 只报数**，「没验到 ≠ 验出问题」）。

★ **先量后定档**：实施前实测 11 个含件 runDir ⇒ `ts` 11/11 相符 · `content_digest` 11/11 规范 ·
`hashes` 11/11 = `main-side` ⇒ **存量零违规**，①② 才敢判 FAIL。

**涉及文件**：[ops/rpc_check.py](../../ops/rpc_check.py)（+锚定段 / +`fix` 自述）·
[tests/test_rpc_check_executor_trace.py](../../tests/test_rpc_check_executor_trace.py)（+4 条，含 2 条**先验红**）·
[A-LIST-LANDING-PLAN.md](./A-LIST-LANDING-PLAN.md)（§2.4 读数刷新）·
[inventory/capability-inventory.yaml](../../inventory/capability-inventory.yaml)。
**验收证据**：夹具 **13/13**（9 → 13）· 门禁 `executor-trace` **PASS** ——
`机制：采集点 5/5 · 覆盖：runDir 含该件 11 个（齐段 11） · 锚定：ts 相符 11 · 自报 0 · ts 不符 0 · 无锚记录 0` ·
`--quick` **PASS · 38 绿 / 2 黄 / 0 红** · `doclinks` 失效 0 · `syntax` PASS。
⚠ **射程（如实）**：锚定段**不**比较「留痕件里的哈希值 == 主控侧哈希值」—— 留痕件**按设计不含哈希值**
（只声明 `hashes=main-side`）⇒ 其含义是「**同一对象 + 哈希权威在主控侧**」，**不是**「两个哈希值相等」。

**关联条目**：`O-57`（归属核对）· `O-89`（无 RESULT 汇总行 ⇒ 假通过）· A 清单 A2 · §2.2 / §2.4。

### 2026-09-29（续⑤） — **A 清单落地（A1）：D6/D7 分界判据求值 `Resolve-D6D7Boundary` 完整闭环（A 清单收官）**

> **定位**：接 [A-LIST-LANDING-PLAN.md](./A-LIST-LANDING-PLAN.md) §2.2 建议顺序的**收尾项**（A4 → A5 → A3 → A2 → **A1**）。
> A1 = `d6-d7-boundary` —— 治 [ADR-0009](../../adr/ADR-0009-D6与D7分界判据.md) §待验证项
> 「判据在**派发引擎中的实际求值 = 无代码**」：§2 的三条判据（B-1/B-2/B-3）此前**只有散文**，无机械求值。
> **载体 = `agent-cli.ps1`**（关键路径）⇒ 与 A2 **串行**（本项**后落**）。
> ★ 本项落地 ⇒ **A1–A6 六项全部落地**（§2.3/§2.4 的"设计底稿已勘误、代码未动"表述作废）。

- **① 三处代码改动（[ops/station-bin/agent-cli.ps1](../../ops/station-bin/agent-cli.ps1)）**：
  ㈠ **纯函数 `Resolve-D6D7Boundary`**（插于 `Select-Reviewer` 后 / `Invoke-Review` 前）——
  按 [ADR-0009](../../adr/ADR-0009-D6与D7分界判据.md) §2 **三分支（互斥且穷尽）**求值：
  `B-1∨B-2 ⇒ D7`（branch `B-1orB-2`）/ `B-3 ∧ ¬B-1 ∧ ¬B-2 ⇒ D6`（branch `B-3`）/
  **`¬B-3 ∧ ¬B-1 ∧ ¬B-2 ⇒ D6`（branch `convention`，约定归属，2026-09-29 由 `O-115` 补入）**。
  ㈡ **`Get-FrontMatter` 白名单登记三键**（`needs_non_producer_verdict` / `needs_multi_round_review` /
  `is_intra_dispatch_quality_gate`，默认 `''` = 未声明）—— ⚠ 该函数是**白名单解析**（未知键静默丢弃）⇒ 漏登记 = 假防线（O-81 同族）。
  ㈢ **`Invoke-Task` 派发前求值**（`require-gate` 块后）⇒ 结果落 `run.json` 的 `boundary` 键。
- **② 三处设计决定**：㈠ **纯函数 + 派发前求值** —— 三键**全部来自卡**、与运行结果**无关** ⇒ 可在产出开始前算
  （ADR-0009 §机制原理：判据问的是**流程形态**，不问产物主题）；㈡ **fail-soft 诚实性** —— 三键任一**未声明**
  （空串 / 非 `true|false`）⇒ `resolved=$false`、`layer` 空，**不假装已判**（"没判" ≠ "判了且归 D6"；
  与 `Resolve-SelfReviewGuard` 的"读不出 ⇒ 不默认放行"同族）⇒ **存量卡不带三键 ⇒ 归属不变**，只多一条 `unresolved` 留痕；
  ㈢ **命名口径 = 下划线**（与 §2 行 L117-118 及 [xrev1 卡](./dogfood-cards/xrev1-cellsafety-boundary.md) 一致）。
- **③ 夹具（离线黄金夹具，单条真函数 + 实际调用）**：[_fm_golden_test.ps1](../../ops/station-bin/_fm_golden_test.ps1)
  **409 → 423**（**+14 条** `a1-*`：8 组合逐个 + **穷尽自证**（`$miss.Count -eq 0`）+ 计数 2/6 +
  未声明/非枚举值 ⇒ 未求值 + 行为断言（写临时卡 ⇒ `Get-FrontMatter` 解析 ⇒ 喂求值）+ 接线断言 + 存量卡缺省 ⇒ `resolved=false`）。
  ℹ **A1 无新 gate** ⇒ **无新 Python 夹具**（本项判据本体即 `agent-cli.ps1` 的纯函数，由 `ps1-golden` 判据自动读该夹具）。
- **④ 先验红（改坏真对象 ⇒ 断言必须红）**：把 §2 **第三分支**改成 `return $null` ⇒ **3 条红**
  （`FAIL a1: ★否/否/否 ⇒ D6` / `★8 种取值组合全命中（落空者: false/false/false）` / `互斥穷尽 ⇒ D6/D7 计数 = 2/6`，
  `pass=420 fail=3`）⇒ **字节级恢复**后复跑 **423/0**（删第三分支 = §3 表 3 行灰项 `否/否/否`
  「受理阶段协商回环 / 需求方验收签收 / 跨站派发」求值落空 —— 正是 §1.3 点的 `O-115` 补丁要覆盖的形态）。
- **⑤ 连带改动**：**手册计数不变**（A1 无新 gate ⇒ 仍 **48 = quick 40 + 全量 8**）；
  [capability-inventory.yaml](../../inventory/capability-inventory.yaml) 新增能力项 `d6-d7-boundary`（`orchestration`，`partial`，carrier 仅 `{kind: file}`）
  + `pre-red` 的 evidence 读数 **409 → 423** + `unverified` 项数 **32 → 34**。
- **⑥ 读数**：`py ops/rpc_check.py --quick` = **PASS · 37 绿 / 3 黄 / 0 红**（**不变**，无新 gate）；
  `capabilities` = **能力 34 项 · present 22 / partial 9 / absent 3**；`py tests/run_py_tests.py -k rpc_check` = **36/36 ALL PASS**。
- **⑦ 如实标注**：§2.2 的 A1 **runtime 验收**（"1 次真派发后 `run.json` 含 `boundary` 键"）**未实测**（与 A2 同）；
  且 **`d6-d7-boundary` 是 `partial`** —— 判据**已接线并留痕**但**尚无消费方**（派发引擎不据此分流、无判据核 `run.json` 归属 ⇒ **算了没人用**）；
  **claude 本地备路**在 `Invoke-Task-Claude` 分支早返回，其 run 记录**不带**本键（另一条写入路径，未纳入 A1）。
- **⑧ 待裁（旧，未动）**：`evidence` 的**可重放 gap 新增 1 条**仍待用户裁定（同续③ ⑦ / 续④ ⑧）。

### 2026-09-29（续④） — **A 清单落地（A2）：执行侧过程留痕 gate `executor-trace` 完整闭环**

> **定位**：接 [A-LIST-LANDING-PLAN.md](./A-LIST-LANDING-PLAN.md) §2.2 建议顺序的**下一项**（A4 → A5 → A3 → **A2**）。
> A2 = `executor-trace`（能力盘点为 **absent**）—— 治「判据**只能看产物**，看不到**过程**」：
> 既有两件与"过程"最近的证据都不顶用（① 输出字节时间序列每 5 秒一行 = **吞吐曲线**，不记"做了什么"；
> ② 工作区改动摘要**实测为空**）⇒ 站上执行体**改过哪些文件 / 跑过哪些命令**，主控侧**查不到**。
> **载体 = `agent-cli.ps1`**（关键路径）⇒ 与 A1 串行；本项**先落**。

- **① 五采集点（最小充分集，口径 = [imp4 卡](./dogfood-cards/imp4-executor-trace-design.md)）**：
  在 [ops/station-bin/agent-cli.ps1](../../ops/station-bin/agent-cli.ps1) 五处落地 ——
  `$Script:EV_FILES` 登记 `.executor-trace.txt`（batch 拉回清单唯一真值）·
  body **启动器段**（fork 前）采 `[env]`（`uname`/`hostname`/`nproc`/`free -m`，**不读 `/proc`**）·
  body **尾部**追加 `[cmd]`（外壳 R0/R1/RC）`[fs]`（既有 `find -newer` 派生）`[tool]` `[artifact]` ·
  主控 **collect 段**归档为 `executor-trace.txt` · `Get-FrameworkSubjects` **基线**加该件（**只进主路**，claude 备路不产）。
- **② 两处设计决定**：㈠ **工具调用链如实标 `uncore`**（执行体内部产生 ⇒ 可篡改/漏报/伪造，**不得伪称已核**）；
  ㈡ **覆盖 0 个不作为 FAIL**（尚无真派发 ⇒ "没验到" ≠ "验出问题"，**报数不入分母**）。
- **③ 门禁 `executor-trace`**（`ops/rpc_check.py`，`quick: True`）：判**机制**（5 采集点逐个在位 + **负向自证**
  `chain=core`/`chain=verified` 不得出现）与**覆盖**（runDir 有件则须齐段；0 个只报数）。
  ⚠ **逐条字面细节**（两段写入 `>`/`>>` · `EV_FILES` 登记 · 主控归档 · `free -m` 而非 `/proc`）**留在离线夹具**
  `_fm_golden_test.ps1` ⇒ 门禁**不抄第二份**（本仓头号失败形态）。
- **④ 夹具双轨**：Python 夹具 [tests/test_rpc_check_executor_trace.py](../../tests/test_rpc_check_executor_trace.py) **9/9 绿**
  （**先验红** = 逐个删采集点 ⇒ 必须红且点名该标记 · **变异自证** · 负向自证 · 覆盖三态）；
  ps1 离线夹具 **409/0**（A2 加 **7 条**断言：5 采集点 + `uncore` 恰 1 处 + 两段写入 + 主控归档 + 负向）。
- **⑤ 连带改动**：手册计数 **47 → 48**（quick 39 → 40，[三机推理集群使用手册.md:258](../../docs/三机推理集群使用手册.md#L258)）；
  `capability-inventory.yaml` 的 `executor-trace` `absent → present`（carriers = gate + `agent-cli.ps1`）+
  `pre-red` 的 evidence 读数 **402 → 409**。
- **⑥ 读数**：`py ops/rpc_check.py --quick` = **PASS · 37 绿 / 3 黄 / 0 红**（36 → 37 = 新增 `executor-trace` 绿）；
  `capabilities` = 能力 33 项 · **present 22** / partial 8 / absent 3。
- **⑦ 如实标注**：§2.2 的 A2 **runtime 验收**（"1 次真派发后留痕件齐 + 与产物哈希**交叉锚定**"）**未实测**
  ⇒ 登记为**未实测**（覆盖读数 0 个 run 含该件）。
- **⑧ 待裁（旧，未动）**：`evidence` 的**可重放 gap 新增 1 条**仍待用户裁定（同续③ ⑦）。
- ⚠ **剩余 A1**（`boundary-judge` 派发前三分支求值，同改 `agent-cli.ps1`）⇒ 本地**串行**，下一步。

### 2026-09-29（续③） — **A 清单落地（A4 → A5 → A3，`land-a` 批）：三个新 gate 完整闭环**

> **定位**：接 [A-LIST-LANDING-PLAN.md](./A-LIST-LANDING-PLAN.md) §2.2 的**建议顺序**，把三份设计底稿
> （**已勘误**，见 §1）**落成可机判件**。三项 = 三个**互不共享代码面**的新 gate ⇒ 可并行立项。
> **执行方式（用户裁定）**：三项并行派**三站**产"落地件"（`ultra` 族零代码改动），主控则**本地**落地 + 独立复核。

- **① 吃狗粮：`land-a` 批（3 张产件卡 · 跨三站并行）**：[batches/land-a.txt](./dogfood-cards/batches/land-a.txt)（一站一卡）。
  三站**全部 `exit=0`**：`land-a4`@A `202609292125234284` · `land-a5`@B `202609292125234193` · `land-a3`@C `202609292125235028`
  （档位均 `public`、无附件）。卡与产件登记见 [dogfood-cards/README.md](./dogfood-cards/README.md) **第七批**。
- **② A4 → gate `md-tables`**（表格**列数守恒**）：`ops/rpc_check.py` 加纯函数 `md_table_scan` + `check_md_tables`；
  真值 = [inventory/md-tables.yaml](../../inventory/md-tables.yaml)（**28 条存量违规逐条冻结**，覆盖 13 个文件）。
  **修掉产件的 2 处参考实现缺陷**（只数**非空**单元格 ⇒ 漏空单元格；分隔行查找**跨空行**）。
  实测 `扫描 270 篇 · 表 1881 张 · 违规 28（冻结 28 · 新增 0）`；夹具 [tests/test_rpc_check_md_tables.py](../../tests/test_rpc_check_md_tables.py) **14/14 绿**；
  **先验红** = 向 `docs/分布式推理.md` 注入 2 列表头 + 3 格数据行 ⇒ `FAIL · 新增 1`（点到 `:612 row 行 3 格 ≠ 表头 2 格`）⇒ 字节级恢复（sha256 前后一致）。
- **③ A5 → gate `determinism`**（确定性/幂等 · **噪声口径单表**）：真值 = [inventory/determinism-noise.yaml](../../inventory/determinism-noise.yaml)
  （**7 类噪声**，可机检 5 类逐类带自证样本；含 `line-ending: LF` 归一策略）+ 消费侧纯函数 `det_manifest_diff`（**逐字节，比对端不归一化**）。
  夹具 [tests/test_rpc_check_determinism.py](../../tests/test_rpc_check_determinism.py) **14/14 绿**（含**真管线双跑实测** = 真读 `inventory/*.yaml` 两次 ⇒ 差异为空）；
  **先验红** = 坏正则 ⇒ `FAIL` 点名到该条 ⇒ 恢复后 sha256 一致。
- **④ A3 → gate `derived-view`**（派生**只读视图**）：新建 [ops/derived_view.py](../../ops/derived_view.py)（渲染 + `--check`，**三态退出码** 0 一致 / 1 过期·漂移 / 2 渲染链路故障）
  + 落档视图 [docs/派生视图_端口分配.md](../../docs/派生视图_端口分配.md)（真值 = `inventory/ports.yaml`）。
  **两处设计决定**：㈠ 档内**移除 `generated-at`**（§1.2 勘误：非确定字段入档 ⇒ 逐字节比对永远失败）；
  ㈡ `source-hash` 在**生产端**归一化行尾/BOM —— 否则 `core.autocrlf=true/false` 两台机器算出不同哈希 ⇒ 视图"**互相过期**"
  （正是 §3.2 旁证那条 `rpc_check.py:4429` 假红的机器版）。夹具 [tests/test_rpc_check_derived_view.py](../../tests/test_rpc_check_derived_view.py) **12/12 绿**
  （含**跨行尾/BOM 可复现**、先验红"改真值 ⇒ rc=1"、变异自证）；★ 途中实测发现 renderer 的**故障分支自己会崩**
  （`VIEW.relative_to(ROOT)` 在 VIEW 被指到仓外时抛 `ValueError`）⇒ 加 `_rel()` 兜底。
- **⑤ 连带改动（照纪律，不是"顺手"）**：手册计数 **46 → 47**（quick 38 → 39，[三机推理集群使用手册.md:258](../../docs/三机推理集群使用手册.md#L258)）；
  `py ops/id_site_census.py --emit` 重出真值（本仓 RPC **23 → 25** 行 / **5 → 6** 文件，因 `ops/derived_view.py` 贡献 `hashlib.sha256()` + `h.hexdigest()` 两行）
  + [U4-INVALIDATION-RULES.md](./U4-INVALIDATION-RULES.md) §1 表同步；`capability-inventory.yaml` 三项 `absent → present`。
  ★ **勘误一条**：§3.2 原写"新 `inventory/*.yaml` 必须登记进 `artifacts.yaml` 否则 FAIL" —— **是错的**（读码核实：`check_artifacts` **只遍历 `items`**，
  对 `inventory/*.yaml` 只要求"可解析"）。实证 = A4/A5 两个新 yaml **未登记**而 `artifacts` 仍 PASS。
- **⑥ 读数**：`py ops/rpc_check.py --quick` = **PASS · 36 绿 / 3 黄 / 0 红**（基线 35 → 36 = 新增 `derived-view` 绿）。
  ⚠ **剩余 A2 / A1**（同改 `agent-cli.ps1` 关键路径）⇒ 本地**串行**，未起。
- **⑦ 待裁（旧，未动）**：`evidence` 的**可重放 gap 新增 1 条**（`dogfood/202609292038295460` 的 `xrev2` 首跑失败 run 缺 subject）
  ⇒ 是否 `cluster.py agent audit --accept` 推进水印，仍待用户裁定。

### 2026-09-29（续②） — **跨族复核批（`inkling`）起批 + 模型族约束入册**

> **定位**：接上一章的"待裁项"，处置**最要紧的那一条**（§3.1 跨族复核批的形态）并**真的起批**。
> **背景（用户裁定）**：后续派发**不再全是 `ultra`**（nvidia 族），**至少换一个 `inkling`**
> （`thinkingmachines` 族）；落法 = **只用 `lightning`、钉 B 站**（**零代码改动**）。

- **① 模型族约束（新，长期）**：跨族复核类派发**一律走 `lightning`**（`openrouter/thinkingmachines/inkling:free`，站 B）——
  依据 = `D7-P0-3` 的 **J-1** 口径：原 A 清单 6 卡**全走 `ultra`（同一 id，仅站不同）**⇒ 只算"同族多实例"、**不构成认知多样性**。
  ⚠ 该约束**目前是行为约定**（写在批次文件注释 + 本文 + `A-LIST-LANDING-PLAN` §3.1），**未做机判**（如实标注）。
- **② 起跨族复核批（3 张卡 · 6 份底稿）**：新建
  [xrev1-cellsafety-boundary.md](./dogfood-cards/xrev1-cellsafety-boundary.md)（A4 + A1）·
  [xrev2-derivedview-executortrace.md](./dogfood-cards/xrev2-derivedview-executortrace.md)（A3 + A2）·
  [xrev3-invalidation-determinism.md](./dogfood-cards/xrev3-invalidation-determinism.md)（A6 + A5）；
  批次文件 = [batches/xrev.txt](./dogfood-cards/batches/xrev.txt)（**三行全 `station=B model=lightning`**）。
  卡面形态：底稿**原样内嵌卡正文**（`===== BEGIN/END =====` 标记，避开围栏嵌套）· 均 `public` · **无附件**（不触发 `attach-egress` 义务）·
  只读复核、产物文件名互不相同（`out/xrev{1,2,3}.md`）。
- **③ 形态裁定 = 候选 ①（单批 3 卡全钉 B）**，**依据 = 干跑 + 读码，非断言**：
  · 干跑（`AGENT_BATCH_DRYRUN=1`）逐字回显 `站分配 A=0 B=3 C=0` + 三行 `-> B (…) model=lightning`；
  · 机制依据：`batch` 分派 = "**每站一个 job、站内串行**"（[agent-cli.ps1:5121-5164](file:///d:/RPC/ops/station-bin/agent-cli.ps1#L5121-L5164)），
    站级 job 对每张卡**各起一次 `agent-cli task` 子进程** ⇒ 锁**每次子进程内取、退出即释放**
    ⇒ 3 张全钉 B 等价于 **3 次独立串行派发**（与候选 ② 同序）⇒ **不撞 `LOCK_HELD`**。
  ⚠ **两点如实标注**：(a) 干跑**只打印分配表、不取锁** ⇒ "不撞锁"**未被本次干跑实测**；
  (b) 三张全钉 B ⇒ **站间并行恒为 1** ⇒ 候选 ①/② **墙钟相同**，选①只为**一条命令**。
- **④ 派发**：`& ops/station-bin/agent-cli.ps1 batch dogfood -Card "spec/d6-agent-standard/dogfood-cards/batches/xrev.txt"`
  —— ⚠ **产物判读必须以 runDir / `out/xrev*.md` 为真值，模型自填不作证据**（本仓"看件不看日志"）。
- **⑤ `A-LIST-LANDING-PLAN.md` §3 细化**：§3.1 记入裁定 + 干跑回显 + 机制依据；
  §3.2/§3.3/§3.4 各补**主控建议**（统一噪声口径 / 本文常驻 / 单列一条 `invalidation-executor`），**均待用户点头**。
  ★ **§3.4 原判被本轮实测更正**：原写"新增能力项须同步 `capabilities` 计数断言与 `mirror` 的 `manual-counts`"
  ⇒ **不成立**：`capabilities` 判据（[rpc_check.py:6926](file:///d:/RPC/ops/rpc_check.py#L6926)）只核**结构 / 载体存在性 / 封闭集**，
  `manual-counts` 对的是 **`CHECKS` 断言项数** ⇒ **新增一条能力项零连锁改动**。
- **⑥ 批次结果（主控逐块核对 · `看件不看日志`）**：**2 成 1 败**（★ 官方汇总不可信，见 ⑦）——
  · `xrev1` `rc=0` → run `202609292037235965`，产物 `xrev1.md`（2958 B，`## 底稿一/底稿二/无法判断项` 齐，`^- ` **12 条**）；
  · `xrev3` `rc=0` → run `202609292039019829`，产物 `xrev3.md`（3436 B，`^- ` **12 条**）；
  · ⚠ `xrev2` **`rc=1` / `TASK_RC=9` / `ACCEPT_OK=0`** → run `202609292038295460`，**产物缺失**
    （`COLLECT_FAIL: … dogfood/out/xrev2.md: No such file or directory` ⇒ 模型未落文件；与 `O-47`（`inkling` B 站偶发停滞）同族）
    ⇒ **已单卡重派 ⇒ 成功**（run `202609292046072184` · `TASK_RC=0` · `ACCEPT_OK=1` · 产物 `xrev2.md` 3347 B · `^- ` **12 条**）
    ⇒ ★ **本批最终 3/3 到位**（`xrev2` 命中点与主控勘误一致：A3 的 `generated-at` ↔ "逐字节一致"冲突 · A2 的"不可核项列入可核条件"）。
- **⑦ ★ 发现并登记 `O-116`（P1 · 判决级假绿 · `batch` 汇总器）**：官方汇总三行**同一个 runDir**（末卡 xrev3 的）`exit=0`
  + `BATCH_DONE: 卡=3 · 失败或未完成=0` ⇒ **把 `xrev2` 的真失败掩盖成成功**。根因 = `Invoke-BatchTask` 汇总段
  `$done`/`$s2` 取**整站日志**末行（**只有 `$mark` 按卡过滤**）⇒ 逐卡 `$rc` 被**错 runDir** 的 `.agent-run.json` 覆盖。
  **未修**（在派发关键路径，须走 spec workflow）；证据 = `_batch/20260929203720/st-B.log` 逐块 vs 汇总。
  ⇒ ★ 再次印证本仓纪律 **"看件不看日志"**：若照抄官方汇总，本批会被误报成 **3/3 成功**。
- **⑧ 跨族复核的实质产出**：`xrev1`/`xrev3` 对 4 份底稿各给 **≥6 条**（等级 + ≤30 字原文依据 + 一句话修法），
  命中点与主控独立判读的勘误**一致**（A4「假绿条目与实现矛盾」· A5「逐字节一致 vs 排除临时目录」= §1 已删 `generated-at` 同族）
  ⇒ **J-1 跨族（`inkling` 判 `ultra` 的产物）确有增量**（`cross_family_verdict(ultra, inkling)` = `cross`，实测）。
- **⑨ `O-116` 闭环（用户裁定"先修" ⇒ 插到 A 清单落地批次之前）**：`Invoke-BatchTask` 汇总段**按卡切块取值**，
  修法 = 站级日志**一次切成"卡 → 块"**（块首 = 派发段写的 marker `=== CARD <卡> rc=<rc> ===`），
  逐卡的 `TASK_DONE`/`RUNSTAMP` **只在【本卡块内】取**（[agent-cli.ps1:5187-5216](file:///d:/RPC/ops/station-bin/agent-cli.ps1#L5187-L5216)）——
  原取**整站日志**末行 ⇒ **每张卡都拿到末卡的值** ⇒ 用**末卡** runDir 读 `.agent-run.json` ⇒ **覆盖逐卡 `rc`**（判决级假绿，同族 = `O-57` 跨 run 证据错配）。
  · **先验红（改码前）**：新夹具 `o80⑩`/`⑩b`/`⑩c` ⇒ `FM_GOLDEN_TEST pass=399 fail=3`（三红，其余 399 全绿）。
  · **改码后**：`pass=402 fail=0`。
  · **变异自证**（字节级备份 → 把 `$clines` 改回 `$txt` → 跑 → 恢复 `sha256` 逐字节一致 = True）：`pass=400 fail=2`（`⑩b`/`⑩c` 红）。
  · **runtime A/B（同批 `o116-rev.txt`，只差代码）**：修前 = 两卡同 `runDir` + `exit=0` + `失败或未完成=0` + batch `exit 0`（**假绿复现**）；
    修后 = 负控卡 `exit=2 src=log runDir=`（空）/ 探针卡自己 `ts` + `runDir` + `src=.agent-run.json` ⇒ `失败或未完成=1` + batch `exit 1`。
  · **验证组合**：`ps1-golden pass=402 fail=0` · `_scrubber_coverage_test 43/43` · `rpc check` 全量/`--quick` 均 `PASS · 33 绿 / 3 黄 / 0 红`。
  · **反向断言件（新）**：[neg-o116-batch-failcard.md](./dogfood-cards/neg-o116-batch-failcard.md)（故意未登记别名 ⇒ 零触站必失败）+
    [batches/o116-rev.txt](./dogfood-cards/batches/o116-rev.txt)（两行同钉 B ⇒ 同一站级日志）。
  · 状态格已回填 `OPEN-ISSUES.md` O-116 = **`✅ 已闭环（2026-09-29）`**。

### 2026-09-29（续） — **`O-115` 闭环 + 6 份产物勘误收敛 + `A-LIST-LANDING-PLAN.md` 建立**

> **定位**：接上一章"吃狗粮两批"的判读四条，处置 `O-115` 并**把 6 份提案收敛为可用设计底稿 + 落地排期**。
> **本轮仍未动实现**：交付物是**勘误结论 + 排期表 + 待裁项**，不是代码。

- **① `O-115` 闭环（用户裁"补第三分支"）**：`ADR-0009` §2 求值规则由**两分支改三分支**
  （新增 `B-3=否` 且 `B-1=否` 且 `B-2=否` ⇒ 归 D6）；`§3 自洽检查` 同步改判 ⇒ **无冲突行 · 无落空行**；
  `## 失效条件` 第一条追加"**已于 2026-09-29 被触发一次**"记录（**保留不放宽**）；`## 修订历史` 追加。
  ⚠ **第三分支的归属是"约定"而非判据推导**（该 3 项当前均由 D6 承载）；日后若改由 D7 承载须改落点并**整体重算 §3 表**。
  `OPEN-ISSUES.md` `O-115` 状态格 `⏳ 待裁` ⇒ `✅ 已闭环`。
- **② 6 份产物勘误（3 处，均"删第二定义点"而非打补丁）**：详见新建
  [A-LIST-LANDING-PLAN.md](./A-LIST-LANDING-PLAN.md) **§1**。
  · **`imp2`（A4）两处缺陷 + 一处自报不实**：`_count_cols` 末行 `return sum(1 for p in parts if p.strip() != "")`
  ⇒ **`return len(parts)`**（空单元格仍是"格"）；分隔行查找由**跨空行**改为**必须紧邻**；`## 假绿` 第 2 条与实现矛盾 ⇒ 替换用例。
  **实测证据**：勘误后 `check_table_columns` 过 **6/6 用例**（边界 1–4 + 勘误①②），临时验证脚本已跑通并删除。
  · **`imp5`（A3）矛盾**：处置 **A（推荐）——从档内移除 `generated-at`**（生成时间只进构建日志），
  "含确定性字段"改为"**只含**确定性字段（`source-hash` / `generator`）"；**不采用** B 案（比对前归一化该行，会造第二定义点）。
  · **`imp1`（A1）8 项灰色地带表 4/8 与 `ADR-0009` §3 不符** ⇒ **删表改指针**（不复制真值，防把模型幻觉升格为真值）。
- **③ 新建 [A-LIST-LANDING-PLAN.md](./A-LIST-LANDING-PLAN.md)**：A1–A6 ↔ 卡 ↔ 站·模型 ↔ run ↔ 产物行数一览（§0）·
  三处勘误（§1）· 逐项落地排期含**先验红点 / 验收判据 / 建议载体**（§2，建议顺序 **`A4 → A5 → A3 → A6 → A2 → A1`**）·
  三项待裁（§3）。
- **④ 承接上一章第 ④ 条（覆盖面偏窄）**：本轮**已裁定跨族落法 = 只用 `lightning`（`thinkingmachines` 族）钉 B 站**，
  **零代码改动**（不新增别名）；但**跨族复核批若排 3 张卡会全落 B 站**，是否撞同站互斥锁（`LOCK_HELD exit 3`）
  **尚未核实** ⇒ 须先 `AGENT_BATCH_DRYRUN=1` 干跑再定形态（**不许凭断言**）。
- **⑤ A6 落地：U-4 执行侧**（用户裁定"落地 imp6"）—— 把 `--invalidate` 的"**只产出决策**"补成"**决策 → 执行报告**"：
  · `ops/rpc_check.py` 新增纯函数 `execute_invalidation()`（**非 CHECKS 项**，与 `decide_invalidation` 同）
  + 两个封闭枚举 `U4_EXEC_STATUS`（`executed` / `partial-failed` / `not-executed` / `no-op`）· `U4_ITEM_STATUS`（`success` / `failed` / `n/a`）。
  · `ops/id_storage_census.py`：`--invalidate` 由**三段扩为四段**（④ 执行报告），新增**故意为空**的注册表 `EXECUTORS = {}`
  （空表即"执行侧未落地"的**机读证据**）。产出行由「⚠ 本命令只产出决策，不执行重算」改为**结构化执行报告**。
  · **防假绿硬约束**（imp6 稿）：整体成功**仅当**全部项 `success` ∧ 成功项 `version` **严格单调递增** ∧ 成功项数 > 0；
  否则一律 `partial-failed`（**禁报成功**）。执行器**抛异常 / 返回非法状态** ⇒ 落失败（fail-closed）。
  · **验收证据**：`tests/test_rpc_check_u4.py` 新增 **9 条执行侧用例 + 1 条先验红自证**（改坏 1 项 ⇒ `executed` 落回 `partial-failed`）⇒ **ALL PASS**；
  **runtime 实测三条路径**（原文逐字见 [U4-INVALIDATION-RULES.md](U4-INVALIDATION-RULES.md) §8）：
  真实 CLI（Open_Data 探针）⇒ `status=not-executed · 不适用 3` · 注入假执行器（全成功 + 版本递增）⇒ `executed` ·
  注入假执行器（1 项失败）⇒ `partial-failed · 成功 2 / 失败 1`。
  · ⚠ **射程**：`executed` **≠**"失效传播跑通"——注册表**为空** ⇒ 九项目 **0/9 未变**；只证明**汇总/门控框架**工作。
- **关联**：`O-115`（闭环）· `A-LIST-LANDING-PLAN.md`（新建）· `inventory/capability-inventory.yaml`（A 清单来源）·
  `inventory/model-families.yaml`（族口径）· `O-80`（`batch` 派发器）· `U4-INVALIDATION-RULES.md` §8（执行侧）。

### 2026-09-29 — **吃狗粮两批（`IMP-A` / `IMP-B`）：把 A 清单 6 个"真·代码未实现"缺口派给三站出设计提案**

> **定位**：从 `inventory/capability-inventory.yaml`（2026-09-27 读数）的待办项里挑出
> **6 个"登记明确未做"的实现缺口**（A 清单），用 `batch` 派发器（`O-80`）**跨站并行**出**设计提案**。
> **本轮只出提案、不动实现** ⇒ 产物先落 `tmp/dogfood-ws/agent-out/<run>/`，**逐份判读**（模型自填不作为证据）。

- **① 两批 6 卡全部跑通**（`batch` 派发器；每站串行 · 站间并行；**6/6** `exit=0` · `accept.passed=true` · `collect=ok`）：
  · **IMP-A**（19:29）—— `imp1` A/`ultra-a` run `202609291929091622`（RUN_S **71**，`boundary-judge-design.md` 31 行）·
    `imp2` B/`ultra` run `202609291929092530`（RUN_S **97**，`cell-safety-design.md` 94 行）·
    `imp3` C/`ultra-c` run `202609291929092399`（RUN_S **127**，`determinism-design.md` 28 行）。
  · **IMP-B**（19:38）—— `imp4` A/`ultra-a` run `202609291939005729`（RUN_S **145**，`executor-trace-design.md` 32 行）·
    `imp5` B/`ultra` run `202609291939006123`（RUN_S **83**，`derived-view-design.md` 38 行）·
    `imp6` C/`ultra-c` run `202609291939006697`（RUN_S **172**，`invalidation-executor-design.md` 41 行）。
  · 6 卡均 `sensitivity: public` · **无附件** · `readonly: false`；清单 = `dogfood-cards/batches/imp-a.txt` / `imp-b.txt`。
  · 墙钟 ≈ max(单片) ⇒ **跨站并行成立**（`O-67` 的 fan-out 假设再得一次正面佐证，仍非定论）。
- **② 判读四条（主控独立复核）**：★ `imp1` 暴露 **`ADR-0009` 求值规则非穷尽** ⇒ 新登记 **`O-115`（待裁）**；
  ⚠ `imp2` 参考实现 **2 处缺陷**（`_count_cols` 只数**非空**单元格 ⇒ 空单元格被误判；分隔行查找**跨空行** ⇒ 可把不合法表判合格）；
  ⚠ `imp5` **自相矛盾**（`generated-at` 列进"确定性字段" vs `--check` 要求**逐字节一致**）；
  ✅ `imp6` 质量最好（失败/降级三态 + 防假绿硬约束可直接用）· `imp4` 采集点与本机群不符，但**如实标注"不可核"**。
- **③ 证据链补录**：批次派发**不走** pre-commit 钩子 ⇒ 6 条未自动入链 ⇒ `cluster.py agent chain` 补录（**246 → 252 · 未入链 0**）。
- **④ ⚠ 为"本轮覆盖面"留一处已知偏窄的记录**：6 卡全走 `ultra`（**同一 id** `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`）的**不同站**
  ⇒ **只跨了站、没跨族**（同一 `nvidia` 血统）⇒ 按 `D7-P0-3` 的 **J-1（跨族）**口径只是"**同族多实例**"，
  **不构成认知多样性**（依据见 `inventory/model-families.yaml` 表头）。⇒ **后续派发须至少一张换族**。
- **关联**：`O-115`（新登记）· `O-80`（`batch` 派发器）· `O-67`（fan-out）· `inventory/capability-inventory.yaml`（A 清单来源）·
  `dogfood-cards/README.md` **「第五批」**。

### 2026-09-26 — **`D7-P1~P4` 实施回填**（本册此前只记到 09-23，**D7 全程未回填**）

> 本册规则写的是「每次重要落地/闭环后由执行体回填」，而 **`D7` 从 `P1` 到 `P4` 全程没回填**
> （只落在阶段卷）。⇒ 本章是**补记**：只记**与 D6 框架直接相关**的部分；D7 的逐批推演见
> [DEV-LOG-014](../../docs/DEV-LOG-014-decision-refinement.md) **§63~§83**。

- **① `agent-cli.ps1` 新增 6 个纯函数 + 4 处接线**（都在**既有派发链**上，未动关键路径）：
  `Resolve-L1Gate`（L1 门，**读 run 记录**）· `Test-FindingShape` / `Test-ConclusionContract` /
  `Merge-JudgeFindings`（结论契约 + Council 综合）· `Resolve-SelfReviewGuard`（不得自审）·
  `Select-Reviewer`（**自动避让**：先换后拒）。接线点：`Invoke-Review` 在**读产物之前**过 L1 门与自审门；
  卡面新增 `require-gate`（流程前置）与 `review-blind`（双盲重推导）。
  **验收证据**：离线夹具 `_fm_golden_test.ps1` **331 → 399**（`pass=399 / fail=0`）。
- **② 门禁：断言 36 → 42（quick 34）**，其中 **13 项**是 D7 落的（`model-families` /
  `conclusion-ledger` / `review-catalog` / `memory-gates` / `multi-round` /
  `interruption-untrusted` / `rubric-blindspot` 等）。**证据**：`ops/rpc_check.py --quick` 当场输出；
  手册 §2.4 的计数由门禁 `mirror` 对账。
- **③ 新增 7 张真值表**（`inventory/*.yaml`）：D7 的落体是**判据 + 真值表**，**不以架构文档为载体**
  —— 依据 `D7-P0` 的裁定「**D7 叠在 ADR-0005/0007 之上，不另造第二套**」。
- **④ ⚠ 本册与 [ARCHITECTURE.md](./ARCHITECTURE.md) 的"实况对齐"滞后**：两者都停在 **2026-09-07** 附近，
  而此后新增了 **5 个命令面**（`route`/`lock`/`split`/`review`/`batch`，合计 **7 个**）。
  **处置**：**只在 `ARCHITECTURE.md` 标注"已过期 + 以什么为准"**，**不就地改图**（ASCII 框线会错位）
  —— 一次**有验收的架构回填**是独立工作项。
- **⑤ 顺带回写 `docs/FRAMEWORK-INDEX.md` 的一条过期触发**：那条「待 D7 进入实施阶段…迁入 `spec/d7-*/`」
  的**条件早已达成而无人回写**，且原文"尚无实现（一行代码未改）"**已是事实错误**。
  ⇒ 迁移判定由「整批迁」改为**逐条判**，实际迁移**拆为独立待办**（见 `O-100`）。
- **⑤-b ★ 后续裁定（2026-09-26，`O-100` 已闭环）**：**4 份调研裁为「不迁」** ⇒ 新增 **`H 类`（阶段依据/取证）**
  **长期驻 `docs/`**。**判据（已一般化进索引维护规则）** = **「该文档的结论是否已被 spec 域吸收？」**
  —— 已被吸收、留在此的**只是过程与证据** ⇒ 留 `docs/`。
  **被否方案（迁）的实测代价**：**35 处入站引用 / 14 文件**（真链接 17 = 相对 15 + `file:///` 2），
  而 `doclinks` **只兜得住相对那 15 处**（`file:///` 那 2 处**它不判**）⇒ 迁完会**静默产生失效链接**；
  且收益仅"位置整齐" ⇒ **真实成本换形式整齐**。
  **附带勘误（已写进索引维护规则 4）**：`spec/d7-*/` **不是路径** —— 实测 `spec/` 下**无 `d7*` 目录**（**0**），
  D7 因 `D7-P0`「**不另造第二套**」而**无独立 spec 域** ⇒ 其产物**就在 `spec/d6-agent-standard/`**。
  关联: [OPEN-ISSUES](OPEN-ISSUES.md) **`O-100`** · [DEV-LOG-014](../../docs/DEV-LOG-014-decision-refinement.md) **§83**（D7 收口后未实测边界普查）
- **⑥ 另外两处「查过但不改」（检查回写的结论，一并留档）**：
  · **`IMPLEMENTATION.md` / `DESIGN.md`**：同为 **D6 MVP 范围**的文档（实测：grep `review`/`batch` 只命中
    "Step 6 review" 这类无关词）⇒ D7 落体**不在其射程内**，这与 `D7-P0` 的「不另造第二套」一致；
    ⚠ **但它们描述 `agent-cli.ps1` 内部结构时已过时**（D7 新增 **6 个纯函数 + 2 个卡面字段**未登记）
    ⇒ **点名在此，不就地改写**（同 ④ 的处置：该做的是**一次有验收的架构回填**）。
  · **`ADR-0009` 的"尚未在派发引擎中实现"仍然成立**（**不假改**）：它那三条是 **D6/D7 分界判据**
    （"归谁"），而引擎里接的是 `D7-P0-3` 的 **J-1/J-2 + 不得自审**（"同一产物上由谁复核"）——
    **两者互补但不同**，别把后者当成前者的落地。
  · ✅ 顺带核实**另一条回写义务已兑现**：`ADR-0009` 转 accepted 时登记「手册 §1.3 增『受理后归哪一侧』段」
    ⇒ 实测手册 §1.3 第 97 行**已有该段**（**这条回写做到了**）。

### 2026-09-23 — D6/D7 路线厘清 + 影响面反查 + 盲区扫描（**仅文档**；D6 侧无代码改动）

> 本阶段是**路线治理**，不是实现；**完整时间线见 [DEV-LOG-012](../../docs/DEV-LOG-012-d6-d7-roadmap-and-impact.md)**（阶段卷），本册只记与 **D6 框架**直接相关的三条。

- **① 路线唯一权威源确立**：`docs/2026-09-23_D6-D7分阶段执行方案.md` 由「分阶段执行方案」升级为**「升级路线总表」**（补 D7 五阶段 `D7-P0`~`P4` / 依赖图 / 退出判据 / 待裁归位）。**边界写死**：**路线 = 总表 · 登记 = `OPEN-ISSUES.md` · 定级 = `REMEDIATION-PLAN.md` · 依据 = 调研/取证**。决策登记见本册 [DECISIONS](DECISIONS.md) **D-20**。
- **② ★ D6-P1 的取证范围被实测推翻（影响本册后续批次）**：[执行方案 §3](../../docs/2026-09-23_D6-D7分阶段执行方案.md) 原写"合格镜像**只有 1 处**"、"真缺口**只剩门面 46 符号**" —— **两次取证漏扫了 `inbox`**。实况：**受理状态机有 ≥9 处知识副本**（6 处在代码：`rpc_check.INBOX_STATES` / `cluster_web.INBOX_STATES` / `_INBOX_NEXT` / `_ACTION+_ACTIVE_STATES` / 前端 JS 状态对 / `cluster.py` `seal` 提示语），且 `inventory/` **无任何 inbox 条目**（grep 零命中）⇒ **该状态机不受机读真值治理**。⇒ **D6-P1 的范围必须扩到受理机制**（新增 M-5/M-6 两条镜像断言），否则新增断言会**复制第 9 处副本**。
- **③ 两条元层缺口（已挂待裁）**：**D6 缺"门禁自审"** —— `D6-P0` 改的就是门禁自身，而"谁审改门禁的人"目前无对应项（D7 侧有 `D7-P2-3`「审判据自身」，**D6 侧无**）；**影响面口径未定义**（"需改/需复核/仅登记"三档混在一份清单里）。二者见路线总表 §12 盲区 **B2/B3**，待裁 **35/36**。
- **④ 与 D6 无关但须并列记住的一条**：**手册**（`docs/三机推理集群使用手册.md`）是**对外契约母版**，其 §1.3 已被实测出**当天即过期**（写"门禁 15 绿（quick 9）"，实测 **17 项 / quick 11**）⇒ **D6 有 8 个批次的产出要回流到手册**（路线总表 §11.4-C）。
  关联: 手册 §1.3、[CROSS-PROJECT-WORK-STANDARD](CROSS-PROJECT-WORK-STANDARD.md)（**其 §7 明文要求随 D6 演进而复核** —— 本轮由盲区扫描补回）。

### 2026-09-22 — D6 派发面安全加固收口日（P0–P5 与 W 系列全闭环；**两次定级被实测修正**）

> 本章为补记（09-21→09-22 未即时落档）。**范围声明**：09-17/09-18 的证据流工作落在 [ADR-0007](../../adr/ADR-0007-证据流阶段推进路线与改动验证闭环.md)，09-19/09-20 无独立条目；本节只记 **D6 安全/派发加固线**（09-21 裁定 + 09-22 实施）。
> 决策推演全文见 [REMEDIATION-PLAN](REMEDIATION-PLAN.md)（§5 定级 / §5.5 裁定 / §5.5.3-4 实施）与四份裁定：[scrubber 规则扩充](../../docs/security/2026-09-21_scrubber规则扩充裁定与影响面.md)、[ZDR 可行性](../../docs/security/2026-09-21_ZDR可行性裁定与影响面.md)、[OpenRouter 数据策略核对](../../docs/security/2026-09-21_OpenRouter数据策略与隐私开关核对.md)、[备路站上化调研](../../docs/research/2026-09-21_D6备路站上化与sensitivity设闸调研与方案.md)；本节只记**何时做了什么 / 怎么查出来的 / 证据**。

- **① `local-only` 闸不覆盖 claude 备路 ⇒ 敏感卡可实际出网（P0，安全洞）**: 洞是**惰性**的（此前该路不可用），2026-09-21 备路修通后**变活**；破的是 DESIGN 不变式②（"local-only 的 prompt 字节永不离开主控站"），影响面 = 25 张卡里 20 张。**修法演进两代**：先加硬闸 `Get-SensitivityBackendReject`（两个出网入口各判一次），再（W1a）把**判据接到真值源** —— `Get-BackendEgress` / `Get-JudgeEgress`（**fail-closed 默认：只有 `local/<flavor>` 不出网，其余一律出网**）。**为什么必须换**：旧判据是**白名单式前缀判据**（`^opencode/`），**每加一个云后端就漏一次**（已实付两次学费：claude 备路 / review judge）。**自证**：夹具 + ★"假想云端后端"负例 + **AST 断言"全仓不再按前缀判敏感度"** + 变异自证（拆闸 ⇒ 真跑出 claude run = 真出境）。
  关联: DESIGN §5.1、OPEN-ISSUES「local-only 闸不覆盖 claude 备路」。

- **② `local-only` 的 claude 通道站上化（P3）**: 不再"一律拒绝"，改走**站上 claude + 站上本地引擎**（物理不出网）；站上不可用 ⇒ `REJECT local-only-no-station-engine` **fail-closed（绝不退回主控本地=出网）**。**"不出网"的可判证据（非仅结构性）**：站上临时 settings 的 `apiKeyHelper` 指向**本地引擎 key** ⇒ 若请求打到 OpenRouter **必然 401**，而它 `rc=0` ⇒ **反证没去云**。同日复查又修两处"设计意图没落地"：`avoid`（优先避开死锁站）原本**无人填 env ⇒ 从未生效**；`pref` 会覆盖率 `avoid`（现两规则提进纯函数且 **avoid 胜过 pref**），判别性实弹 `avoid=''`⇒`B,A,C` vs `avoid=B`⇒`A,C,B`+SKIP×2。
  关联: DESIGN §2.1、调研 §3。

- **③ scrubber 规则扩充裁定 + 覆盖率夹具**: 判据 = **①可判性 × ②真敏感 × ③误伤≈0 × ④有出现路径**，四条全中才加 ⇒ **加 6 条凭据类 / 不加 8 条身份与拓扑类**。**硬证据**：本仓 run ID（`yyyyMMddHHmmssffff`）**恰好 18 位数字、全仓 204 处** ⇒ "长度判据"的身份证规则会把**主要证据句柄整片抹掉**（实测 3/3 命中），而 GB 11643 校验位判据 0/3。**私钥块改"拒发"**（fail-closed，退出码 4）—— 二分依据 = **能不能安全抹除**，同时消掉 DESIGN「命中即拦截」与「脱敏后远端」的旧张力。新建 `_scrubber_coverage_test.ps1`（**确定性函数 ⇒ 可做真值表**），**当轮即命中一个真 bug**：`win-path` 原用 `\S+`，**遇空格即断** ⇒ `C:\Program Files\…` 只被吃掉 `C:\Program` 而输出里**出现了 `[REDACTED-PATH]`**（"看起来已处理过"）。
  关联: 裁定 §6、`_scrubber_coverage_test.ps1`。

- **④ P3 附件旁路实测（自对照设计）**: 同一路径植两处（卡正文=控制组 / 附件=实验组）⇒ 正文侧被抹、**附件侧原样** ⇒ 不变式②的"消毒面"**不含附件**（此前未在任何文档写明）。**云端后果的硬证据**：claude 路转录显示 `tool_use`/`Read` ⇒ 原文**确实进了模型上下文**，不是模型猜的。探针卡与说明**刻意分开放**（说明留在 body 里会把期望答案提前告诉被测对象 = 污染）。
  关联: `test-cards/scrub-attach-probe.md` + `-notes.md`。

- **⑤ ZDR 裁定（P5）：不做，且它不是可执行动作**: ZDR 按 **model group** 分作用域，我们型号**全是 `:free` ⇒ 100% 落在 "All other models"** ⇒ 给该作用域开 = **本行那 5 类消费者全灭**；且 `local-only` **已强于 ZDR**（它现在根本不出网，而 ZDR 明确"不改变数据到达 provider"）⇒ 对它开 ZDR 是**降级**。⇒ **"允许出网但不允许留存"这个格子是空的**；**若将来真要 ⇒ 必须换付费型号**（已实测 `mistral-nemo`/`ling-3.0-flash` 连 `zdr` 都过）⇒ **"开 ZDR" ≡ "换后端"**。
  关联: ZDR 裁定全文、OPEN-ISSUES「备路全档依赖免费档开关」。

- **⑥ review 出网 = 缺口②（W1b）**: `Invoke-Review` 把**卡正文 + 产出原文**拼进判据提示词送 egress judge，**既无 scrub 也无 block** ⇒ 同一张 `sanitized` 卡"派发时被抹、review 时原样出网"。**⚠ 我自己的原推荐（本地 judge）被自己推翻**：决定性判据 = **档位语义一致性** —— `sanitized` 的**定义**就是"抹后可出网"，若 review 不走抹，**同一张卡的含义会取决于跑哪个子命令**；且本地 judge 会引入"引擎需在位"的新可用性依赖。⇒ 改为 `Resolve-ReviewPrompt`（**先 block（命中拒发）→ 只对 `sanitized` 抹 → 再发**），位置由夹具**位置断言**守住。同时闭环缺口③：`JUDGE_TABLE.compliance` **声明了但全仓无读取点 = 假防线** ⇒ 接线为 `Get-JudgeComplianceReject`（缺字段 ⇒ **拒**）。
  关联: REMEDIATION-PLAN §5.5.1、DESIGN §5.1「消毒面收口已实施」。

- **⑦ 附件默认不出网 + 显式放行（W4）**: 判据 = **可判性** —— 卡正文/judge 提示词**可判** ⇒ 抹后可出网；**附件形态不可判**（二进制/压缩/base64/UTF-16）⇒ 抹不出可测覆盖率 ⇒ 只会产出"抹了一半"的**假防线** ⇒ 只能靠**不出网**兜底。卡字段 `attach-egress: ok`（与 `review-model` 同属"**显式接受出网**"家族），两个通道各判一次。
  关联: DESIGN §6.1 + §5.1、CROSS-PROJECT-WORK-STANDARD §4。

- **⑧ `review.json` 进产出方基线（§5.5.4）+ 存量缺口由用户裁定接受**: W1b/W4 让 review 写出**新证据件** ⇒ 门禁当即报"已归档但未被任何 subject 覆盖" ⇒ 把 `review` 加进**两个按路基线**并带 **`ephemeral = $true`**（事后写入、非派发必有 ⇒ 裸列会让**每个未 review 的 run** 假报 `missing-artifact`；`ephemeral` 在此承担**第三态**："可合法缺席"）。**⚠ 关键**：manifest 是**派发时快照 ⇒ 不回溯** ⇒ 该 WARN **不会被修复消掉**；存量那条须 `agent audit --accept`（**按设计是人的显式动作**）⇒ 用户裁定后执行，水印 **15→16**，门禁 `evidence` 转 PASS。同批拿到**真实派发**的行为证据（修复前 `subjects=10` 无 `review` / 修复后 `=12` 含 `review(ephemeral=True)`、audit 未声明 0）。
  关联: REMEDIATION-PLAN §5.5.4、ARCHITECTURE §6。

- **⑨ 进程 rc 恒 0（W2）—— ⚠ 定级被实测修正**: 登记说"特定于 AUTO_FALLBACK 返回路径"，实测**不带 fallback 的普通超时 run 同样** `TASK_DONE exit=6` 而**进程 rc=0** ⇒ 真实范围 = **任何走过 `.attach/` reset 之后的派发 = 每一次真派发**（成功时看不出，**失败时被静默读成成功**）。**根因（测出来的）**：attach-reset 那行**裸调用** `Invoke-RemoteScript` 的 **int 返回值 0** 混进 `$code` ⇒ `$code = @(0, <真 rc>)`，而 `exit @(0,4)` = **0**（独立脚本三例钉死）。**两层修**：6 处裸调用一律 `| Out-Null`；新增出口守卫 `Resolve-ExitCode`（取**末元素**）让全部 5 个 `exit $code` 走它。**同族根因**：09-18「归零纪律」只覆盖 **cmdlet**、**漏了自定义函数的返回值**。**实测闭环**：同命令 ⇒ 日志 `exit 4` + **`PROC_RC=4`**。
  关联: OPEN-ISSUES「task 进程退出码」、ADR-0007「缺口 5」。

- **⑩ 站上 claude 的附件与项目工作区（W3，步 1 → 步 2 → 撤闸）**: 步 1 先加 **fail-closed 闸**（"站上+有附件 ⇒ 拒"，理由是**假绿灯**比"明确拒绝"危险）；用户裁定"把能力做出来"后步 2 **实装**：站上分支**复用主路同一套** `Invoke-Workspace -act sync`（`cwd = <WSROOT>/<proj>`，附件落**同一处** `.attach/`），任一步失败 ⇒ 非零退出 ⇒ **安全性质与旧闸等价**而危险形态变成"可用的能力"；**撤闸依据是实弹**（唯一 marker 只存在于附件 ⇒ 出现在 agent 输出里 ⇒ 附件在站上确实可读）。**⚠ 我自己的中间设计被自己推翻**：第一版给站上 claude 建了**自建 scratch 工作区**（只放附件）⇒ 它既是**第二套工作区概念**、又**不含项目文件**（项目相对路径仍解析不到且**无判据会因此报错**）。**⚠ 实施中自查避免一处回归**：`claude --continue` 是**按目录**恢复会话的 ⇒ 工作区名"每次唯一"会让**续接路径静默失效**。
  关联: REMEDIATION-PLAN §W3、OPEN-ISSUES「claude 路的附件面」。

- **⑪ 探针"守门人还活着"（治"判据自己死了没人知道"）**: `_probe_fallback.ps1` 有**硬编码提取清单**这一腐烂面，实测**静默烂过 8 天**（且**无自动调用点**）。加 `-SmokeOnly` 静态自检 + **由夹具调用它**；再进一步改"**提取全部函数**"（**不提清单就不会漏**）。⚠ **它换来的新失效模式也给了判据**：`stub` 必须在提取之后定义才生效（否则被真函数覆盖 ⇒ 可能**真的去 ssh**）⇒ 判据 = "存在性 + **顺序不变量**"。**首跑即命中一个潜伏漂移**（`Invoke-ClaudeFly-Station` 未提取，只因探针里站上探查必然失败才没爆）。
  关联: OPEN-ISSUES 同名行、`_fm_golden_test.ps1`。

- **⑫ 台账 / `.agent-run.json` 的 `model` 列 = "实际执行身份"**: 站上 claude 分支原先写**路由 id** ⇒ 一个 `local-only`（"物理不出网"）的 run 被记成**云端型号**。**⚠ 登记范围被实测放大**：原记"台账一列"，实测 **`.agent-run.json` 同样误导**（同一处 `$id`）⇒ **两个证据件都要改**（后者是机读终态快照、证据链真值源）。改为 `station:<站>/<别名>`（非站上分支保持 `$id`，那时它就是真值）；**不加列**（避免 schema 变更波及读取面），且**信息不丢**（请求的路由 id 可从归档的卡 + ROUTE_TABLE 复原）。**实弹前后对照**：台账末三行 —— 修复前两条写 `thinkingmachines/inkling:free`，修复后 `202609221347542756` 写 **`station:B/main`**。
  关联: OPEN-ISSUES「站上 claude 的两条边界」②、`cluster.py` 台账注释。

- **⑬ 落档审计（用户要求"检查工作是否完全落档"）**: 按"**工作项 → 该落在哪几处**"逐条核（而非只查改过的文件），查出 **6 处"说了与实现相反的话"**（比缺文档更危险）并修：探针说明卡的"站上变体不适用本卡"、"claude 备路暂不发射 evidence_manifest"（**为假**，实测 `subjects=5` 含 `review`）、"claude 备路 attach = 名字数组"（**为假**，**且同一句在两处定义点**：ARCHITECTURE §6 + DESIGN §6.2）、DESIGN §5.1 两处"待人裁/待人批"、§6.1 卡 schema 缺 `attach-egress`/`review-model`（**schema 双真值**）、台账行与 §8 rc 行 5 的语义缺记。
  关联: 提交 `0ca17f7`。

- **⑭ 门禁口径两项（决策简报 → 实施）**: 用户要求先出简报再执行。**简报本身的最大产出 = 两处登记原话都被实测推翻/精确化**：① `doclinks` 登记的"只扫 `git ls-files` ⇒ 新文档 `git add` 前不进判据"**不成立**（实测 `check_doclinks` 用 `ROOT.rglob("*.md")` **全工作区扫描**；用 `ls-files` 的是另一函数）⇒ **真盲区是判据自己放弃**：相对链接**越出仓库根**时返回"不可判定"、与 http/占位词混在同一桶（现不判 740 条）—— **这才是 09-16 那 27 条 `../../` 漏网的机制（不是没扫到，是扫到了但判据放弃）**；实测影响面：越界**相对**链 **2 条**（都是真错）、越界**非相对** **0 条** ⇒ 加判据**误报面为零**。② root 级登记"5 个一次性脚本"**不精确** ⇒ **4 脚本 + 1 目录**；且**不能整批处置** —— 3 个 `.sh` 全仓零引用，而 **`_o26_reverify_loader.ps1` 与根级 `test-cards/` 互为引用**（前者硬编码绝对路径调用后者）+ **6 处文档引用** ⇒ **活体工装**（09-16 `_agent-cli-bom.ps1` 教训的翻版，**区别是引用链仍活**）。
  **实施（用户裁定 A + 分类处置）**：① `_doclink_bad` 拆开两类（相对形态越界 ⇒ **失效且可判** + 原因串；非相对仍不判）+ 明细补原因 + 修 2 条越界链 ⇒ 复验 PASS 且**"不判"桶 740→738**；**对照自证**用**真实漏网**（判据加入前后同批数据 PASS→FAIL 点名 2 条，非合成样例）。② **三站前置取证全 none** → 3 个零引用脚本归档 `archive/root-scripts/`；`_o26_reverify_loader.ps1` **迁 `ops/station-bin/` 并登记**（冻结存量 184→185）+ **硬编码绝对路径改为由脚本位置推算仓库根** + **缺件即 `throw`**；4 张卡迁 `spec/.../test-cards/`、2 个附件源迁 `ops/station-bin/attach-test/`；根级 `test-cards/` 移除。**⚠ 迁移后门禁当场抓到**该文件"含中文却无 BOM"（`.ps1-bom:14文件/1失败`）⇒ 补 BOM —— 该判据再次自证。**自证**：`scripts` PASS（未登记 0）/ 三条新路径 True 且**两条旧路径 False** / `syntax` PASS。**第二步（扩范围到仓库根）**：✅ **同日已实施**（见下 ⑮）。**顺带新登记**：根另有 2 个 **gitignore 的**遗留物（`llama.cpp-0.2.0.tar.gz`、一个 `.bak`）⇒ 门禁与本次处置都覆盖不到 —— **✅ 同日已清理**（取证：`.bak` 内容 = 可达历史 `612064f^` 的 blob `992e5e48`，还原 523 行逐行一致 ⇒ 零信息损失；tar.gz = 上游 tag `v0.2.0`）。
  关联: [决策简报（待裁 → 已裁定并实施）](../../docs/2026-09-22_门禁口径决策简报_doclinks越界链与root级脚本范围.md)、OPEN-ISSUES 两行。

- **⑮ `scripts` 门禁治理圈扩到仓库根（第二步收口：两层谓词）—— "只减不增"从只有 `ops/` 变成覆盖根级**:
  **触发**：⑭ 的"仍未做"，用户裁定 **#5 = 两层谓词**、**#6 = 并入 `frozen_ops_scripts`**。
  **#5 为什么不是"全仓递归 + 排除表"**：那正是 ⑭ 登记原始需求的形态，但**每加一个项目目录就多一个定义点**（漏一项即假红/假绿）—— 本仓纪律是**判据只在一处定义**。**两层谓词**（`ops/**` ∪ **仓库根顶层文件**）**一个例外清单都不需要**：`spec/**`、`tests/**`、`archive/**` **天然**在圈外，而"顶层文件"恰好是 09-16 真正出事的形态（一次性东西**直接丢在仓库根**）。
  **改了什么**（[`rpc_check.py`](../../ops/rpc_check.py)）：新增范围谓词 **`_in_script_scope()`** 作唯一真值（注释里写明"**为什么不改成全仓递归**"，防后人改回去再挂一长串例外）；`_iter_ops_scripts()` ⇒ **`_iter_governed_scripts()`**（旧名与新行为不符；调用点**仅 1 处**，已同步）；`check_scripts` docstring 补范围。
  **#6 登记落点：并入 [`inventory/ops.yaml`](../../inventory/ops.yaml) 的 `frozen_ops_scripts`** ⇒ **登记表零改动**。**实测依据**：顶层被跟踪文件**只有 `.gitignore` 与 `LICENSE`**，二者在 **Python** 里 `suffix=''` ⇒ 走 shebang 分支、首行是 `#` 非 `#!` ⇒ **不被当脚本**。（⚠ PowerShell 的 `[IO.Path]::GetExtension('.gitignore')` 得 `.gitignore`，与 `os.path.splitext` **语义不同** —— 别被带偏。）
  **验收（双向自证；扫描源是 `git ls-files` ⇒ 探针必须**先 `git add`** 才进判据面）**：① 基线 **PASS · 212 · 未登记 0**；② 根级暂存 `tmp_top_check.sh` ⇒ **FAIL · 213 · 点名 `tmp_top_check.sh`**（**证明扩范围真的在判**）；③ 删掉 ⇒ **PASS · 212**；④ **`tests/` 下暂存未登记 `_tmp_scope_probe.sh` ⇒ 仍 PASS**（**证明两层定义不误扫目录内部** —— 缺这条就分不清"两层谓词"与"全仓递归"）。探针件均已 `git rm --cached` + 删除，工作区无残留。
  **教训（同族第 5 次）**：**"范围谓词"和"判据"一样，必须双向验** —— 只验"该红的红了"（根级 FAIL）会漏掉"不该红的红了"（把 `tests/**` 也扫进去），两个方向缺一不可。
  关联: [决策简报 §③](../../docs/2026-09-22_门禁口径决策简报_doclinks越界链与root级脚本范围.md)、OPEN-ISSUES「root 级脚本不受 `scripts` 门禁治理」、ADR-0004 D3。

- **⑯ ssh/scp 统一 `BatchMode`（09-16 登记的健壮性项闭环）—— "把卡住变成快速失败"**:
  **病**：认证异常时（典型 = `~/.ssh/config` 缺身份块 ⇒ 用户名退化为本机用户）OpenSSH 会**弹口令提示并阻塞等 stdin** ⇒ 自动化里表现为"卡住"（**实测挂起 >90s**）而不是"失败"。
  **范围**：严格按登记点名的两处（`agent-cli.ps1` 的 ssh/scp、`cluster.py` 的 paramiko 路径）—— 未擅自扩面（扩面属 ADR-0004 D3 新能力）。
  **改了什么**：① `agent-cli.ps1` **20 处**裸调用补 `-o BatchMode=yes`（另 9 处本就有）⇒ 全文件 **29 个 ssh/scp 调用点全部带 BatchMode**；首个调用点旁落**纪律注释**（为什么 + 守卫在哪）。② `cluster.py`：**paramiko 根本没有 BatchMode**（它不弹口令、认证失败即抛异常，"挂死"形态不存在）⇒ 这一侧真正的对应物是**超时上界** —— **实测上游源码**（paramiko 5.0.0）`banner_timeout` 默认 **15s**、`auth_timeout` 默认 **30s**（**两者不同源**），而原代码只给了 `banner_timeout` ⇒ "认证阶段卡住"要等 **30s** 而非 `SSH_TIMEOUT=8` ⇒ 补 `auth_timeout=timeout`；并**把另外 2 处重复的 `paramiko.SSHClient()` 收敛到唯一入口 `_connect`**（那正是漂移的滋生点）。
  **守卫（4 条，带自动调用点）**：`_fm_golden_test.ps1` **164 → 168** —— ① AST 数全文件 ssh/scp `CommandAst` 必须含 BatchMode；② `Start-Process -FilePath 'scp'` 形式的 scp 判其**参数数组赋值**；③ 用 **Python `ast`** 判 `cluster.py` 里 `SSHClient()` 调用恰 1 处、`connect` 恰 1 处；④ 其 `connect` 关键字必须含 `auth_timeout`。
  **验收（变异自证 4/4 全红 → 还原 168/168）**：摘一处 BatchMode ⇒ **缺 1 处并点名第 275 行**；摘 `$scpArgs` 里的 ⇒ 红；摘 `auth_timeout` ⇒ 红；多一个 `SSHClient()` 调用 ⇒ 红。
  **⚠⚠ 本轮最值钱的是"判据自身"的两个坑（我又犯了一遍）**：**(a) 文本判据第 5 次被注释骗** —— ③ 第一版用 `[regex]::Matches($text, 'paramiko\.SSHClient\(\)')` 数出 **2 处**，其中一处是 `_connect` 的 **docstring 里提到这个名字** ⇒ 改 Python `ast` 数真实调用节点。**(b) 断言打在了错的对象上** —— `Start-Process` 那处我把断言打在它自己的 `Extent.Text` 上，而该串里只有**变量名** `$scpArgs`（真值在**上一行赋值**里）⇒ 必红；修法是判"**真值所在的那一行**"。⇒ 两条都可推广：*断言要打真值载体，不是打引用它的那一行*；*"数某个名字出现几次"这类判据天然会被注释骗，有 AST 就必须用 AST*。
  **⚠ 新登记（不在本项点名范围内，待裁）**：扫描发现仓库还有 **3 个站上/一次性工具的 18 处**裸调用 —— `agent-cli-smoke.sh` **12 处**（5 处 `ssh -o ConnectTimeout=10 "$HOST_x" "pgrep …"` + **7 处 `ssh "$HOST_x" 'bash -s' <<'REMOTE'`，连 `-o` 都没有**）、`load-gate` **4 处**（`ConnectTimeout=5`）、`_switch_qwen_flavor.ps1` **2 处且只落在 scp 侧**（该文件 3 处 ssh 早已带 ⇒ **半修**）；**当前无守卫**（`.sh` 无可靠 AST 面）。**⚠⚠ 盘点脚本自身在同一个坑里翻了两次**：v1 正则要求 `ssh|scp` 后紧跟 `-`/词字符 ⇒ **漏掉 `ssh "$HOST_B"` 这类"主机是引号变量"形态共 6 处**（故 v1 的"6 处"实为 12）；v1 还把**注释与消息串**一起算了（`throw "NETFAIL: scp failed…"`、docstring 里的 `ssh 失败`、`echo "== A -> B ssh 连通 =="`、夹具样串全被误算 ⇒ **虚报 33 处**）。v2 = 只取 `#` 之前代码段 + **引号奇偶**判命中点是否在串内 + 逐行人工定夺 ⇒ 余 3 条 FP 已逐条确认（`cluster.py` docstring、`_probe_fallback.ps1` 的 `function ssh {}` **stub 定义**、`plugin-probe` **多行 docstring** 散文）。**⇒ 教训：盘点脚本的"形态清单"必须先拿已知样本验，否则漏项是静默的**（同"判据要先在已知会红的样本上验红"）；**"数名字出现几次"这类脚本的边界（跨行字符串、正则宽窄）必须显式声明**。**另一条实测事实（决定处置代价）**：`load-gate` 是**站上件** —— 实测三站 `/usr/local/bin/load-gate` 的 md5 **全为 `6acec519…`、与仓库副本一致**（副本 0 个 CR）⇒ **仓库副本即活体，但改完必须重新部署三站才生效**；而 `ops/station-bin/README.md` 的清单**没列 `load-gate`**（只列 `load-mem-gate`）⇒ 该件无部署记录、无 md5 基线（**登记缺口，另记**）。
  **方案 C 第一步（2026-09-22，用户裁定）**：只修 `_switch_qwen_flavor.ps1` 那 2 处 scp 半修（零风险、不触站），`agent-cli-smoke.sh`(12 处) 与 `load-gate`(4 处) 仍待裁。**动作**：2 处 scp 补 BatchMode + 文件头英文纪律注释（该件刻意 **ASCII-only** ⇒ 注释也用英文，免得踩 `.ps1-bom`）+ **纳入守卫**（夹具 168→**169**：AST 断言**扩到第二个 .ps1 入口**，且要求 **≥5 处命中**）。**变异自证 2/2 全红**：① 摘掉刚补的那处 ⇒ `实测 5 处 / 缺 1 处`；② 把断言指向一个**无 ssh/scp 调用**的 .ps1（`_probe_fallback.ps1`，只有 `function ssh {}` 的 **stub 定义**）⇒ `实测 0 处 / 缺 0 处` **仍红** —— 这是"**0 覆盖与 100% 通过必须可区分**"那条既有纪律的又一次落地（此前只在探针的"正对照"里用过，这次做成了**断言内置的下界**）。
  **方案 C 第二步（2026-09-22，用户裁定）—— `agent-cli-smoke.sh` 12 处收口**：该件是**升级窗口回归三件套**之一。12 处全补 `BatchMode=yes`（其中 **7 处 heredoc 形态连 `-o` 都没有**，同时补 `ConnectTimeout=10`）+ 文件头纪律注释；⚠ 特别记下 heredoc 形态的**额外风险**：它把 stdin 交给 heredoc，**无 tty 时 OpenSSH 会从 stdin 取口令** ⇒ 可能把脚本文本当口令送出去（比"挂住"更隐蔽）。**守卫**：`.sh` **无可用 AST** ⇒ 文本扫描兜底（夹具 169→**170**）—— 判据 = 只取 `#` 前代码段 + **引号奇偶**判命中点是否在串内 + **逐文件命中数恰为登记值**（`bare=0 total=12`）。**变异自证 2/2 全红**：① 摘掉一处 ⇒ `bare=1 total=12`；② 把扫描指向**无 ssh/scp 调用**的文件 ⇒ `bare=0 total=0` **仍红**。**⚠ 诚实边界**：文本判据的已知残留是**跨行字符串**判不出（`plugin-probe` 的多行 docstring 就是本类），且 `.sh` 没有 Python AST；这条边界**写进了断言注释**而不是留着不说。另验 `bash -n` **显式走 Git Bash**（PATH 的 `bash` 是 WSL —— 仓库既有教训）rc=0 + 0 CR。**剩余**：`load-gate` 4 处（需重新部署三站）。
  **方案 C 第三步（2026-09-22，用户裁定）—— `load-gate` 收口 + **首次走完"站上件的改动闭环"****：该件 4 处 peer ssh 全补 `BatchMode=yes`（显式 `ConnectTimeout=5` 保留）+ 头部纪律注释（并写明：加了之后认证/网络异常会**快速返回空值** ⇒ 落到**既有**的 `[ABORT] host 不可达` 分支，**fail-closed 语义本来就在**，此处只是把"卡住"去掉）。**这一步的真正难点不是改代码，而是它是站上件** —— 仓库副本改了不生效。闭环走法：① 夹具文本扫描扩到该件（逐文件登记值 `bare=0 total=4`，仍 **170/170**，**变异自证**：摘一处 ⇒ `load-gate bare=1 total=4` 红）；② 本地 `bash -n` + 0 CR；③ **三站逐站：先 `cp -a` 备份（核 `备份 md5 == 原 md5`）→ `install -m 755` → 核新 md5 == 仓库副本 + `MODE=755` + `bash -n`**；④ **回归实弹**：三站各跑 `load-gate 1` ⇒ 均 `[OK]` + `[load-gate] ALL PASS`（rc=0）；⑤ **补上登记缺口** —— `README.md` 此前**根本没列 `load-gate`**（只列 `load-mem-gate`）⇒ 已补该行 + md5 基线（`07ad7e01…`，三站一致）+ 回滚处方。**⚠ 两条诚实边界**：**(a) 未做"认证失败"实验**（要故意破坏认证）—— 直接证据只到"源码带 BatchMode + 三站跑的就是这份源码 + 无功能回归"；**(b) 新登记一条未收口项**："**仓库副本 vs 三站副本**的一致性**没有任何机器判据**"（只靠 README 手工 md5 约定），候选便宜实现 = `rpc_check.py` 的 `gates` 探针顺手加 `md5sum` 比对（不新增连接），但"可用"≠"与仓库一致"⇒ 属新能力（D3），待裁。
  关联: OPEN-ISSUES「ssh/scp 未统一 BatchMode」、ADR-0006（该缺陷是它的调查副产物）。

- **⑰ 把"站上件 == 仓库副本"从手工约定升级为机器判据（接入 `gates`）—— 判据接入当日就抓到真漂移**:
  **裁定（用户）**：把该一致性检查接进 `gates`（不再是"待裁"）。**实现**（[`rpc_check.py`](../../ops/rpc_check.py)）：新增 `STATION_BINS`（8 件，= `README.md` 文件清单里声明的站上件）；在既有健康探针 `_HEALTH_CMD` 末尾加一段 `===BINMD5===` 循环 `md5sum`（**零额外连接** —— 复用那条本来就跑的命令），`_parse_health_sections` 按既有的 `===NAME===` 机制自动分段；判据在 `check_gates` 里逐站比对**仓库副本**（期望值**运行期算** ⇒ **不立第二定义点**，也免掉"改了仓库忘改表"的漂移），不一致/缺失/清单写错三分支各有专属文案；`note` 加"站上件一致 N/M"**让通过时也可见**。
  **⚠ 首跑即抓到真漂移**（`wait-gtt-release`）：A/B = `40d6cfe4…`、C 与仓库 = `a60b1877…` ⇒ 违反 README"三站必须一致"；差异是**新版 vs 旧版**（`TOTAL*0.82` 相对总内存 vs `-ge 102400` 绝对 100G）；且 **A/B 那份首行带 UTF-8 BOM**（`.sh` 带 BOM 是明确的坑）⇒ 典型的"**改仓库 + 只部署了一站**"半部署。**处置（用户裁定"部署到 A/B"）**：同一套闭环推 A/B —— 备份（核备份 md5 == 原 md5）→ `install -m 755` → 核新 md5 == 仓库副本 + `MODE=755` + **`FIRST3=23212f` 字节级证明 BOM 已消除** + `bash -n` + **回归实弹** `timeout 20 wait-gtt-release` rc=0 ⇒ 复跑 **24/24 PASS**。
  **判据自证（两向）**：① **真漂移对照**（部署前 FAIL **点名 A/B** → 部署后 24/24）—— 与 ⑯ 同一个偏好：**用真实漏网，不用合成样例**；② **两条未触发过的分支各做一次变异**（加一个"仓库有、站上不部署"的件 ⇒ "取不到 md5"分支；加一个不存在的名字 ⇒ "清单该改"分支）⇒ 都按设计 FAIL 并点名 ⇒ 还原后 24/24 ⇒ 证明判据不是"只在 happy path 上绿"。**⚠ 顺带确证边界**：`_switch_qwen_flavor.sh` **不该**进清单（运行时推 `/tmp`，不部署到 `/usr/local/bin`）。
  **⚠ 两条设计取舍（写进代码注释）**：**(a) 为什么判 FAIL 而非 WARN** —— 接入前**实测过误报面**（8 件×3 站里 7 件本来就逐字节一致 ⇒ 误报面为零），且它与本站 `stations` 断言（conf/凭据/端口不符 ⇒ 以站上实况改仓库侧）**同一性质**；`gates` 是 `quick=False`（不进 pre-commit）⇒ **FAIL 不阻断提交**，只阻断全量门禁。**(b) 快照语义** —— 期望值取"仓库副本当前内容"，所以"改了仓库还没部署"也会被判出来，**这正是要的**（该件改仓库不生效）。
  关联: OPEN-ISSUES「站上件副本与仓库副本不一致」+「ssh/scp 未统一 BatchMode」、[station-bin/README.md](../../ops/station-bin/README.md)（手工 md5 约定已由本判据接管）。

- **纪律沉淀（本日产出，均可推广）**:
  1. **判据必须先在"已知会红/已知会绿"的对照上验，否则它只是"在跑"不是在判** —— 本日**三次**同族翻车：位置断言被**注释里的函数名**骗（改 AST 找实际命令调用）；AST 判据只判 `StatementBlockAst` 而**函数体是 `NamedBlockAst`（兄弟类不是子类）** ⇒ 顶层语句全被漏掉（删回 bug 也 PASS）；"探查 0 次"**可能是恒真的**（补正对照证明 0 有意义）。
  2. **定级必须查"流量"，不能只看"有没有源"** —— "有源"≠"有流"（review 出网一度被我报成 P0"活跃"，按存量卡与调用面修正为「结构性 P0 / 暴露面 P1」）。
  3. **"看起来能用的判据"本身就是风险** —— `model` 列看起来能判"是否出网"却**是错的**；`compliance` 声明看着像防线却**无读取点**（假防线）。
  4. **先问"系统里已有的那个概念能不能复用"，再动"新建一个"** —— 自建 scratch 工作区立刻造出**第二个定义点**。
  5. **撤闸的依据必须是行为证据**（唯一 marker 法），不是"代码看着对"。
  6. **文本判据会被注释骗**（本日第 4 次）⇒ 能 AST 就 AST；here-string 只能文本判时**锚定行首**。

- **验收（本日终态）**: 夹具 `_fm_golden_test` **164/164**、`_scrubber_coverage_test` **43/43**、`_probe_fallback` **pass**（含 `-SmokeOnly`）；门禁 **15 绿 / 1 黄 / 0 红**（黄灯 = 已登记的 `stations` 插件漂移）；证据链 **117 条、未入链 0**；三站引擎已 unload。

### 2026-09-22（线二）— opencode 发送预算口径修正：09-07 的旧架构结论被实测推翻

> **与上节的关系**: 上节记 **D6 派发面安全加固**；本节记 **opencode 客户端预算 / 引擎 ctx 解耦线（O-23）**，属**不同工作流**，仅同日。**触发**: 用户问「opencode 遗留问题是否必须注册」⇒ 先查上游、再复现 09-07 的三组实验 ⇒ **旧结论不成立**。**结论全文落档**: OPEN-ISSUES §O-23。

- **① 旧结论（09-07 实验 2/3）**: "1.18.25 对自定义 provider 的发送预算由**内置 catalog `context_length`** 决定，`limit.context` 对 config **完全免疫**"（依据：改 `limit.context` 后 `opencode models --verbose` 视图**仍 131072**；binary 反编译出 `J.context_length ?? Y?.limit.context`）。
- **② 复现失败（配置层四组探针）**: 同版本（B 站 1.18.25）重做 ⇒ **视图层完全跟随 config**：① 新增条目；② 改**已存在**条目（`qwen` 131072→12345、`m27-q4ks`→23456，**即时生效**）；③ **三个从 `opencode models` 全量列表里确证存在于 catalog 的 id**（`deepseek/deepseek-v4-flash`／`nemotron-3-ultra-free`／`gpt-oss-120b`）**全部读到写入值 12345** ⇒ **"撞名 ⇒ catalog 覆盖"不成立**。
  - **方法论教训（本轮最关键）**: 首轮拿 `qwen` 当"撞名臂"是**无效设计** —— 裸 id `qwen` 可能**根本不在 catalog 里**（catalog id 形如 `deepseek/deepseek-v4-flash`）⇒ "两臂都对"**什么也证明不了**。⇒ **撞名/冲突类实验必须先用枚举命令确认对照组真在名单里**。
- **③ 行为层实弹（判据从"视图"升级到"实际请求"）** —— B 站引擎 gpt-oss-20b **`ctx=32768`**、`compaction.reserved=20000`：
  - **短 prompt 两臂**（`limit=20001` 可用 **1** tok / `131072`）⇒ 均 **rc=0 + 引擎 200** ⇒ **`limit.context` 不是"发送前硬闸"**；
  - **94.5k 单次请求两臂** ⇒ **同一条错** `Message too long: 95037 tokens exceeds the **32768**-token context window`（`code: context_length_exceeded`）⇒ **硬闸数值 = 服务端 ctx**，与 config 的 20001／131072 **均无关**（该错由客户端预检还是服务端透传**未定**，两种解释都指向"硬闸来自服务端"）；
  - **多轮累积（3 轮 × ~8k tok，同一 session）** ⇒ `limit=20001` 臂**第 2 轮即出现 `agent=compaction`**、`limit=131072` 臂**三轮零压缩** ⇒ **`limit.context` 确实驱动 compaction 阈值**（两臂唯一变量）。
- **④ 修订后的机制**: `limit.context` **生效于"视图 + 压缩阈值"**，但**不构成"发送前硬闸"**；**实际硬闸 = 服务端（引擎 `n_ctx`）**。⇒ O-23 的修复（**agent-cli 档位=引擎档位**、`ENGINE_CTX` 探测 + profile clamp）**结论不变，仅理由改写**（"catalog 覆盖" → "客户端不作硬拦截"）；原候选根治方向（改 `api.modelID` 触发回退）**作废**。
- **⑤ 上游注册：不必**（对用户原问题的答案）: 决定性因素在**服务端**；上游同族已有 **5+3 条**（`#29555`/`#37456` closed-completed、**`#37544` 被 `not_planned`**、`#35863`/`#40524`/`#38835`/`#40908` open）；`#41104`（本地 ctx 发现 PR）**已提未并入**；我们落后 **7 个 patch**（1.18.25→1.18.32@09-21）而**近 8 个 release notes 无相关修复** ⇒ **升级不是解法、新开 issue 只会重复**。
- **⑥ 顺带查出（新登记）**: **压缩路径在本地 provider 上必然失败** —— `agent=compaction` 后紧跟 `level=ERROR … AI_TypeValidationError: Value: {"type":"reasoning_summary","duration_ms":9472}`（opencode 期望 `choices`/`error`）⇒ 累积超阈时任务**不是被压缩救回、而是直接 rc=1** ⇒ **"把 `limit.context` 对齐引擎档位"这一改进的收益，取决于先修此条**（实测该臂 turn2/turn3 均复现）。
- **⑦ 现场纪律**: 四次配置实验**全部先备份 → 后还原 → 核 md5 回到原值**（`755975dba0ff28cf64dff0e106000cb6`）；探针临时文件已删；跑完 `cluster.py unload`（**三站 OK**）。
- **⑧ 根因定位（同日续做"先定位根因"）**: **根因不在 opencode，而在网关** —— ① **网关注入非标准 SSE 帧**：三方 curl 对照 ⇒ studio `:8080` **流式命中 1**（`data: {"type":"reasoning_summary","duration_ms":179}`）、studio **非流式 0**、**直连 `llama-server :47059` 流式 0** ⇒ 帧由 **studio 注入**；② **为何只有压缩路径炸**（DEBUG 对照）：**普通 turn 命中 0 / TypeValidation 0 / rc=0**，**压缩 turn 命中 3 / TypeValidation 2 / rc=1** ⇒ 普通对话路径**容错丢弃**、压缩路径**严格 union 校验** ⇒ 必失败；③ **上游已确认并已修**：`unslothai/unsloth#10362`（closed **09-08**）正文逐字即本例（"UI control frames … carry no `choices`, so strict OpenAI clients fail schema validation"），修法 = 控制帧收进 **`X-Unsloth-Events` opt-in**；其自测 **"8 of 13 streams throw outright today"**；④ **我方不含该修复**（站上 studio 目录 `grep -rl X-Unsloth-Events` **无命中**）。**修法结论**：**升级 station 的 unsloth studio** 是唯一治本；"加该头"是**反向**、"改 baseURL 直连引擎端口"与 `_station_ready.sh` 的 **C2** 相悖 ⇒ 均不采纳。**边界（当日续做取证后更新）**：studio 版本**已取到 = `unsloth 2026.9.2`（PyPI 09-02，三站同版）** ⇒ "早于 #10362（09-05 提 / 09-08 关）"由推断**升级为日期直证**；PyPI **`2026.9.3`（09-08）为首个含修复候选**、latest = `2026.9.7`（09-18）、`2026.9.2` 仍可装 ⇒ **回滚可行**。**决策简报**: [docs/2026-09-22_决策简报_unsloth-studio升级方案.md](../../docs/2026-09-22_决策简报_unsloth-studio升级方案.md)。
- **⑨ 方案 A 执行（同日续做；用户裁定"B 试点 → 通过后立即推 A、C"）**: **B 站试点【通过】** —— 三条判据 ① 流内控制帧 **1→0** ② 压缩两轮 **rc=1/TypeValidation=2 → rc=0/TypeValidation=0**（压缩恢复可用）③ 引擎档位 **`ctx 32768` 未变**；版本 `unsloth 2026.9.2→2026.9.7`、`X-Unsloth-Events` **0→2**。**三个网络瓶颈与处置**（可复用）：`uv`→PyPI **IPv6 零进展** ⇒ 清华镜像 env 解卡；`bitsandbytes` GitHub 直链 **~30 KB/s**（asset 41.1 MiB，用 `gh api` 查大小**量化 ETA**后决定等）；`triton_kernels` 的 **`git fetch` 零字节卡死** ⇒ B 站收口（脚本自带 `skipped, no git` 分支）。**⚠ 范围外发现**：`studio update` **会替换 `~/llama.cpp` 引擎为 `unslothai/llama.cpp` latest（无跳过开关）** ⇒ A 执行中（编译中）、**C 已暂停**（freeze 零差异）。**另纠正两处简报假设**：`backend` 门禁**不查** studio 包版本（升级后仍 15 绿/1 黄/0 红）；`verify-install` **基线即 rc=1** ⇒ 不可用作完整性判据。详见 [决策简报 §七](../../docs/2026-09-22_决策简报_unsloth-studio升级方案.md)。
- **⑩ 方案 A 收口（同日续做；用户裁定 A 站"两者兼做"、B"补齐跑完"、C"暂缓"）**:
  - **A 站引擎面回归 → 已复原**：A 升级后引擎变为 **Vulkan-only `0.4.1-dev build 11030`**（`build/bin` 无 `libggml-hip.so`）⇒ `infer-load` 报 `invalid device: ROCm0`、门禁 `backend` **FAIL**（当时唯一红灯）。**根因（marker 对照）**：A 的 `UNSLOTH_PREBUILT_INFO.json` 记 **`host_profile.has_rocm: false` / `has_intel_gpu: true`** ⇒ 安装器按 `auto` 路由到 **Vulkan bundle**（B/C 的 marker 是 `rocm-gfx1151`）；**当场复测 `detect_host()` = `has_rocm=True, gfx1151`** ⇒ **update 时刻的探测误判**（**为何误判未定论**，未复现）。**处置**：B→A `tar` 分发同版引擎（1.9 G / **18 s**）⇒ A 回 `ROCm0`、`llama-server` md5 与 B **逐字节同**（`31d8787b…`）、旧引擎留 `~/.unsloth/llama.cpp.vulkan-b11030-20260922`。**门禁 `backend` PASS · 红灯 0**。
  - **`infer-load` 二修**（三站已部署，`gates` 站上件一致 **24/24**）：**不再硬编码设备名** —— 09-12 把 `Vulkan0` 改成硬编码 `ROCm0`，本次 update 把 A 翻回 Vulkan ⇒ **同一"硬编码"第二次成为必然失败因（方向相反）**。改为按引擎自身 `--list-devices` **实测选取**（ROCm 优先 → Vulkan → CUDA → 首个），`INFER_DEVICE` 仍最高优先，探测结果入日志。**两侧对照**：Vulkan 侧 `选中=Vulkan0`、ROCm 侧 `选中=ROCm0` + **端到端 `READY ✓` / rc=0**。
  - **调研（用户问"update 是否总覆盖原后端设置"）**：**默认会**。`effective_backend_request()` = 显式（CLI `--llama-backend` / env `UNSLOTH_LLAMA_CPP_BACKEND` / `UNSLOTH_FORCE_VULKAN`，`mandatory=True`）> **marker 历史选择（advisory，源码逐字"it is dropped for detection when the hardware or the published bundles no longer offer it"）** > 探测 ⇒ **探测说了算**；**只有显式 pin 拦得住**（help 逐字"A backend with no bundle for this host **fails rather than installing a different one**"）。可选值 `("auto","cpu","cuda","rocm","vulkan")`（`hip`=`rocm` 别名）。社区侧：当前官方文档仍列 `studio update`；2026-06 的 `v0.1.44/462/463/464-beta` 有 "DO NOT USE `unsloth studio update`" 的 breaking change（**当时版本系列**的告示）。⇒ **建议升级前 `export UNSLOTH_LLAMA_CPP_BACKEND=rocm`**。
  - **回滚机制（试点中一并确认）**：包回滚 ✅（`--package "unsloth==2026.9.2"`）；**引擎回滚 ❌**（update 无跳过开关，引擎恒取 `latest`）；⚠ **包回滚 ≠ 引擎回滚，且包回滚会再走一次引擎步** ⇒ **先备份引擎目录**。
  - **B 补齐**：**manifest 证据** = B **完全没有** `unsloth_install_manifest.json`（A/C 都有）⇒ 从未完成一次完整 pass；A 的 manifest 把 `single-env/data-designer.txt` 列为**声明需求** ⇒ B 缺的 `data-designer*` 确属未落地。**路径**：`install_python_stack.py` **可单独运行**（**不含引擎步**）⇒ 只补 Python 层、**不动引擎**；`triton_kernels` 走脚本自带的 `_has_working_git()=False` 分支（B 直连 GitHub **~33 KB/s**，`git fetch` 不可行；该包**仅训练加速**）⇒ **B 仍缺该项（三站唯一包差异）**。
  - **两处记录更正**：① 「`pyarrow` 25.0.1→23.0.1 降级」**撤销** —— 三站实测**全为 23.0.1**（含未升级的 C）；② §7.3「下载源码后本地编译」**不成立** —— marker 显示装的是 **`published` prebuilt**（`bundle_profile: linux-vulkan-x64`、`prebuilt_fallback_used: false`），真因是**选错变体**。
- **⑪ 第二轮收口（2026-09-23；用户五项指令：pin 落站 / C 推升级 / B 的 `triton_kernels` 拷平 / 完整落档 / 修平三个表块）**:
  - **pin 落三站 ⇒ 落 `/etc/environment` 而非 `.bashrc`/`.profile`**（关键：**非交互 ssh 读不到后两者** —— Ubuntu `.bashrc` 有 `case $- in *i*) return;; esac` 守卫、`.profile` 只被登录 shell 读；而 `/etc/environment` 经 **`pam_env.so`**（`/etc/pam.d/sshd:44`）对**非交互命令**亦生效）⇒ 这是唯一让"经 ssh 执行的 `studio update`"也受保护的落点，且 studio 子进程（含 UI 内更新按钮）继承同一会话环境。**断言**：三站 `effective_backend_request() == ('rocm', True)`（mandatory）。备份 `.bak-20260923`。
  - **C 站已推升级（studio 到位；引擎未动）**：原计划 `studio update` 被 **GitHub 出网**阻断（C 的 `github.com` 完全不通；A 的 mihomo 上游节点失效；控制站亦超时；仅 B 直连 ~35 KB/s）。**量化**：`latest`=`b11030-mix-5ff778e` 的 rocm-gfx1151 bundle **337.4 MiB**（对照 **vulkan bundle 仅 29.1 MiB**），各可用下源 35–79 KB/s ⇒ 337 MiB 需 1.3–2.7 h ⇒ **不是"慢"，是 C 上无通路**。**转用**：`install_python_stack.py` **本身就是更新器安装 `unsloth`+`unsloth-zoo` 的那一步**（源码逐字 `studio update` DOES NOT set `SKIP_STUDIO_BASE`；走 `pip_install()` ⇒ 尊重 constraints ⇒ **不换 ROCm torch**）⇒ 直调该函数，**只跳过 Node 与引擎两阶段**；两个 GitHub 依赖分别处置（`triton_kernels` 走自带 no-git 跳过分支；收尾的 bnb 强制重装 GitHub wheel 由 **B→C LAN 拷平同一 artifact** ⇒ 改为 `already this build -- keeping it`）。**结果**：17/17 `deps installed` + manifest 写出 + **引擎 md5 全程未变** ⇒ **三站引擎仍逐字节同版**；`unsloth` 由镜像 latest（已是 **2026.9.8**）**压回裁定目标 2026.9.7**。**判据**：`ctl=0`（前 2）、档位 `ctx 131072/:8080/ROCm0` 未变、帧/字节与 B **逐字节一致**（127 / 24869–24882）。**登记（不修）**：C 的 `manifest.package_version` 记 `2026.9.8` vs 站上 `2026.9.7` ⇒ 刻意不改（改即伪造 pass 记录）。
  - **性能测量（用户问"升级后有无提升"）**：B(9.7) vs C(9.2) 同硬件 / **同引擎二进制** / 同 conf ⇒ 唯一变量 = studio 版本。**⚠ 口径更正**：`flow bench` 的端口是**引擎内层端口**（**直连 `llama-server`、不过 studio**）⇒ 其 pp/tg 与 studio 版本无关。**结论：无吞吐提升、也无可归因回退**；**净改进 = 控制帧移除**（ctl 2→0、帧 130→127、字节 −~560 B/2.2%）；**净代价 = studio 注入前缀 +750 token**（经 studio `prompt_tokens` 871→1621，而**直连引擎同 payload 两站均 68** ⇒ 纯 studio 所致；可被 KV 前缀缓存命中 ⇒ 稳态不逐轮重付，但占 ctx）。**边界**：跨机非前后、单流 n=3、站内极差 40% ⇒ 分辨力 ~±10%。
  - **表块列数修平**：OPEN-ISSUES 三处表块（块1=8列：L48 补 1 填充格 / L51 去 1 填充格；块2/3=3列：9 行"只转义多余的内部管道"，成因是 prose 内未转义 `|`）⇒ **全文件 10 表块 / 异常 0**。**护栏**：逐行断言"删掉所插入的每个反斜杠后逐字还原原行"（首轮因**插入位置在后续插入后失效**而正确挡下）。**⚠ 可推广**：**"未转义管道数" ≠ "格数"**（GFM 允许省略行尾 `|`）⇒ 两个自写探针因此给出矛盾清单 ⇒ **判据必须固定口径**。
- **⑫ 把 studio 生命周期纳入统一管理框架 + A 站 mihomo 诊断（2026-09-23；用户裁定"完整三步"+"调研 mihomo 出网"）**:
  - **纳入框架（对照 ADR-0004）**：本轮 8 类动作里 **6 类是"管理操作"，却全在框架外**（内联 ssh + heredoc）；已在框架内的三处（`infer-load` 走 `STATION_BINS`+`gates`、`flow bench` 落账、`rpc_check` 对账）说明**缺的是 studio 生命周期这一整块**。落地三件：**① 断言扩展**——`check_backend`（改名"引擎后端与 studio 防线"）新增 **(e) pin 在位且**本会话**可见**(FAIL)、**(f) `X-Unsloth-Events` 修复在位**(FAIL)、**(g) studio 版本三站一致**(WARN)、**(h) 引擎逐字节同版⇒站间 tar 可复原**(WARN) + 备份目录清单；**② 入口**——`cluster.py studio status`（只读矩阵）+ `FLOWS["studio-upgrade"]`（预检→应用→验证→门禁→落账，`dry_default`）；**③ 期望值**——`_EXPECT_LLAMA_BACKEND="rocm"` 与既有 `_EXPECT_*` 同族。
  - **双向验证**：临时把 A 的 pin 改 `vulkan` ⇒ **FAIL + 摘要 `pin ✗` + 点名 A + exit=1**；恢复 ⇒ **PASS + `pin ✓ · studio 2026.9.7 · 引擎 同版 · 修复 ✓` + exit=0**；`flow studio-upgrade --station C --to 2026.9.7 --go` ⇒ **四步全绿 / PASS / 落账**，`--stage engine --go` ⇒ **明确拒绝并给指引**（"没升引擎"不该看起来像"升完了"）。
  - **设计取舍**：pin 的期望值**不进 `inventory/`**（该断言语义是"声明源引用未登记项"，pin 无声明源；同类期望值本就在常量层 ⇒ 放进去会是第二真值源）；判据取**会话可见**而非"文件有行"；关键事实**并入摘要行**（渲染层只在 FAIL/WARN 打印 detail）。
  - **A 站 mihomo：结论更正（推翻 §7.4 两条）** —— 不是"上游节点失效"，而是 **`runtime.yaml` 里 `proxies: []` / `proxy-groups: []`（43 行文件第 16/17 行）⇒ 从来没有节点**；唯一组 `GLOBAL.now=DIRECT`、`profiles/` 只有 `.gitkeep`、`profiles.yaml` 的 `use/profiles` 皆空、资源时间戳 4月6日。⇒ **"经 A 的代理"一直等于直连**（实测 github/api.github/ghproxy 直连与经代理**都 200**，耗时差只是波动）⇒ §7.4 的"A 的 clash 可用（0.46s）"是**直连成功被误归因**，"C 经隧道复用 A 的代理"**原理上不成立**（隧道通 ≠ 对端有出口）。
  - **解决方案（②已实测）**：① 配订阅（需用户提供 URL，唯一能真正提速）；② **零凭据：借 B 的直连** —— C 上 `ssh -f -N -D 11080 scott-lau@B` + `https_proxy=socks5h://127.0.0.1:11080` ⇒ `api.github.com` 200/0.82s、**ranged 4 MiB 实测 107 KB/s ⇒ 337.4 MiB ≈ 55 min**（优于 B 本机 35 KB/s 与 `ghproxy.net` 74 KB/s）；关隧道后 C 直连立刻回 `000`（对照有效）；③ 镜像兜底 `ghproxy.net`。
  - **三处踩坑（可推广）**：① **`\1` 在 Python 字符串里是八进制转义**（→ `\x01`）会把 sed 替换串毁掉 ⇒ 取数穿 Python 层时**反斜杠一律写 `\\`**（`\(` 只 warning、值仍对，两者表现不同）；② **`pkill -f "<模式>"` 会自匹配承载脚本自身**（脚本文本含该串）⇒ 本次把承载会话自己杀了、隧道未建（改到另一会话里清）；③ **台账"判据"列默认值写死成 bench 文案** ⇒ 新 flow 的行串台（改为自取该 flow 末步判据）。
- **关联**: [OPEN-ISSUES §O-23](OPEN-ISSUES.md)、[决策简报 §九/§十](../../docs/2026-09-22_决策简报_unsloth-studio升级方案.md)（纳入框架 + mihomo 诊断）。
- **⑬ 四项 D6 健壮性判据收口（2026-09-23；用户令"先解决这4个问题 按 todolist"）**:
  - **② `syntax` 缺 `ps1-bom` 子判据 —— 已实现在位，未新增**：D6 表 L720 ③ 滞后于实现 —— `rpc_check.py` **L430-454** 的 `(ps1-bom)` 判据（含非 ASCII 却无 BOM ⇒ FAIL）早在 **2026-09-21** 就已落地且计入 `counts`→`total_bad`→门禁 FAIL；`--only syntax` 实测输出含 `.ps1-bom:14文件/0失败`。**结论：该项无需做，只更新认知**。
  - **④a `doclinks` 未跟踪文件盲窗 —— 不存在**：doclinks 用 **`ROOT.rglob("*.md")` 扫磁盘**（非 syntax 的 `git ls-files`），D6 表把它与 syntax 的"未跟踪盲窗"误并。**实测**：会话新建未 git add 的 `ops_DOCLINK_PROBE.md`（tmp 外）仍被抓到 2 条失效 ⇒ 盲窗不存在，**该项无需做**。
  - **③ `syntax` 占 quick ~96% —— 优化完成 19.6s→6.7s**：先 cProfile 定位：**瓶颈是 412 次 `bash -n` 逐文件 fork（~17s），语法解析本身仅 ~0.3s**。中途排掉一个"合并外循环"的错误捷径（`bash -n` 只作用首个入口脚本，合并=静默降 0 覆盖，正好验证"判据须先在已知会红样本验红"）。**正解 = 并行分块**：新增 `_bash_lint_parallel`（`ThreadPoolExecutor`，默认 8 worker，`chunks=files[i::n]`，`seen` 口径保持"远端实处理文件总数"以保住"读到数!=喂入数⇒不可信"那条）。**双向自证**：注入坏 `.sh` 并 git add 后 ⇒ `.sh:413文件/1失败` 仍精确点名坏文件（并行不漏错）；删除后回绿；覆盖数 412/413、构建号、`0失败` 均不变。
  - **① 站上 `out/` per-run 陈旧守卫 —— 加主控侧一致性判据（用户裁定）**：取证确认站上侧已兜底大部分（`acquire` 把上一轮 `out/` 归档进 `orphaned/`、采样器 run 结束 `kill $SPID`+`wait`、`.agent-lock` flock）；**真正未覆盖** = "主控中止（kill ssh）但远端 body 仍跑"的孤儿采样器持续写**固定名** `.progress`，主控拉到的节拍无法自证属本次。**修**（不改站上件，agent-cli.ps1 是主控侧脚本）：证据回收段若 `.meta` 的 TASK_ID != 本次 ts（`$evStale`），则将 `.progress` 节拍置空并打 `EVIDENCE_STALE` **WARN（不改 rc，属覆盖缺口非篡改）** —— 复用既有 META_STALE 锚点，零新增连接。夹具 **170/170** 通过，四项门禁（syntax/scripts/doclinks/evidence）全 PASS。
  - **④b 锚年龄告警 / ④c 证据面留存目标 —— 仅记账（用户裁定）**：D6 表 L720 ④ 本就标注"社区调研待做判据（调研 §14.6，仅记账）"，本轮**不编码**，维持原定位仅记账。
> **本项的总教训**：D6 审查表（L720）的"待办"是 **2026-09-21 时的快照**，其中 ②③④a 的描述与当前实现**已有漂移**（②已实现、④a 不存在）——**动手前先取证（`--only` 实测 + 读代码），别照着滞后清单造无用功**；而 ③ 的真瓶颈要靠 **profile 而非猜**（两次直觉捷径都被实测推翻）。
- **关联**: [OPEN-ISSUES D6 闭环审查 L720](OPEN-ISSUES.md)（②③④a 已收口，④b/c 仍仅记账）。

### 2026-09-16 — provider 命名漂移修复 / 新模型入网 / C2 引擎面统一日

> 本章为补记（当日未即时落档，2026-09-16 晚由用户指示「修复记录 / 排查过程 / 决策依据完整落档」一次性回填）。
> 决策推演全文见 [ADR-0004 第五批 + 补记 + 补记二](../../adr/ADR-0004-统一管理入口为唯一管理面.md)、[ADR-0003 免费档计数/硬限速](../../adr/ADR-0003-OpenRouter密钥与egress路由管理.md)；本节只记**何时做了什么 / 怎么查出来的 / 证据**。

- **① provider 命名漂移修复（P0，命中「已闭环」的 G1 自身）—— 排查过程**:
  触发=用户「已定案的几个问题执行闭环」。**排查路径**：不读文档，直接从统一入口查三站 config 实况 ⇒ `~/.config/opencode/opencode.jsonc` **只有 `local` + `openrouter`**，`cluster-litellm` 已不存在；但 [agent-cli.ps1](../../ops/station-bin/agent-cli.ps1) 的 ROUTE_TABLE、[_station_ready.sh](../../ops/station-bin/_station_ready.sh) 的注入段、`agent-cli-smoke.sh`、`a5-nextday-verify.sh` **仍全部引用旧名**。`_station_ready.sh` 第[3]步**强制要求** config 存在 `cluster-litellm` 块（否则 `ERR_INJECT exit 11`），而它在**派发路径上** ⇒ **整条 `task` 派发门实际不可用**（不是"文档过时"，是门坏了）。
  **决策依据**：用户裁定「资产跟随现状」（不改 config 回旧名）。关键实测=**opencode 拒绝未在 `models` 中声明的模型名**（`local/nemotron` → UnknownError；`local/main` → 正常解析）⇒ 单纯塌成 `local/main` 会丢"风味/站点"语义 ⇒ 采「**在 `local` 下声明多模型 + 资产纯前缀替换**」。
  **落点**: 三站 `local.models` 声明 `gpt-oss`/`gpt-oss-20b`/`nemotron`/`qwen`/`qwen3.8-flash-next`(ctx 262144)/`m27-q4ks`（三站一致哈希 `d765c81f…`）；`agent-cli.ps1` ROUTE_TABLE 全量 → `local/*`、`$TpBench` 键改名并补 m27-q4ks(21.5)/flash-next(19)（取自 THROUGHPUT-BASELINE，无虚构）、slot-gate/split 判据 `-like 'local/*'`、review 默认 → `local/nemotron`；`_station_ready.sh` 注入目标改名；smoke 脚本补 C 站节；`cluster.py` `STATION_ROUTES` 补条目。
  **纪律沉淀**：**任何 provider / 别名 / 端口改名，必须 grep 全仓引用方（不只文档）**。
  关联: G1、O-14、ADR-0004 第五批。

- **② 新模型三站入网（m27-q4ks / qwen3.8-flash-next，UD-IQ4_XS）**: 取证先行 —— A 站两模型**都缺**、B/C 已有 ⇒ 实际只需 **C → A**（~202GB）。走 A↔C USB4 直连段（rtt 0.17ms）`rsync -a` 双路并行；**逐字节一致**（MiniMax 108,413,781,312 B；Qwen 93,682,584,224 B）。三站建 `~/.config/rpc/llama-instances/*.env`；[inventory/models.yaml](../../inventory/models.yaml) 登记（flash-next **保持默认路由 B**，不静默改既有行为）。⚠ 排查中踩坑：**PowerShell 会剥掉 ssh 命令里的内层双引号**（`nohup bash -c "…"` 被拆 ⇒ rsync 收到错参**静默不传**）⇒ 改写为无嵌套引用的独立后台命令 + `setsid nohup` + 日志。

- **③ 命名回归修正（当日引入、当日修，自曝）**: 上一步我**照模型技术名自造** `minimax-m2.7`，而站上规范别名是 **`m27-q4ks`**（`infer-load` 内本就带归一化 `sed 's/^minimax-m2.7.*/m27-q4ks/'`，`infer-list` 第一列即真值，`tests/b5q/*` 与 review judge 别名 `m27` 早已用它）⇒ 实测 `infer-load minimax-m2.7` 直接 **`ERROR: 无匹配`**，三站 `minimax-m2.7.env` 成**孤儿 conf**。**决策依据**：用户选「三项全做」= 全链改名 + 删孤儿 conf + 修 infer-load 匹配。**纪律**：**别名必须以 `infer-list` 的 alias 空间为准，不得照模型技术名自造**（已写入 `cluster.py` ROUTE 注释）。
  连带修 `infer-load` **匹配逻辑两缺陷**：原实现只有 `grep "^${PREFIX}"` ⇒ (a) **传精确别名也判歧义**（`gpt-oss-120b` 同时是 `gpt-oss-120b-fable-5-distilled` 的前缀 ⇒ `load gpt-oss-120b-b` exit 1）；(b) **PREFIX 未转义**（`.` 是正则通配）。改为「候选集全列 → 精确相等者胜出 → 否则才走唯一前缀」，比较用 shell `case` 按字面串。**验收**：`infer-load gpt-oss-120b` 不再报歧义、`zzz-nomatch` 仍报无匹配、三站 `bash -n` OK。

- **④ C2 引擎面统一为 studio 固定 `:8080`（本日最大决策，废弃 config 注入机制）—— 排查与决策链**:
  1. **问题起点**：前一步的注入机制把 `local.baseURL` **持久改写**成当次引擎端口（B 被写成 `:50889`）⇒ 任务后三站 config 漂移、`stations` 门禁转红（pre-push 拦下）。
  2. **探测（用户指示「先探测 studio 并发端点」）**：`unsloth studio run --help` 实证 `--host/--port/--path/--api-prefix/--reuse-port` 属 **managed flag 被拒收** ⇒ 内层 llama-server 端口**不可指定**（实测随机 40007/50031/50889）；且 `:8080` 是 **三协议网关**（OpenAI `/v1/chat/completions` 200、**Anthropic `/v1/messages` 200**、`/v1/responses`），`/v1/models` 自带 `context_length`，`/api/health` 免 key 200，`/slots` **404**。⇒ **C1（固定内层端口）不可行；C2 可行。**
  3. **slot-gate 数据源替换（选项 3 实测成功）**：`/api/inference/active-generations` 空载 `count=0`、忙态 `count=1` 且 `parallel_slots=4` ⇒ **优于 `/slots`**（直接给并发生成数+上限，无需逐槽聚合）。映射 `count→SLOT_BUSY` / `parallel_slots→SLOT_TOTAL` / `QUEUE=0` ⇒ **输出契约不变，`Invoke-SlotGate` 与 wrapper 零改动**。
  **落点**: [infer-load](../../ops/station-bin/infer-load) 加载后把 studio 重铸的 key **落盘** `~/.config/rpc/unsloth.key`；[_station_ready.sh](../../ops/station-bin/_station_ready.sh) **删注入 + 删端口发现**（端口固定 8080，判据 `/v1/models`(带 key) + `/props` + chat）；[_slot_gate.sh](../../ops/station-bin/_slot_gate.sh) 换数据源；[agent-cli.ps1](../../ops/station-bin/agent-cli.ps1#L208) 就绪断言 `INJECT_OK` → `CHAT_OK`；[cluster.py](../../ops/cluster.py) **读码确认无需改**（其 `curl :8080/health` + "任意 HTTP JSON 即在线" 判据本就覆盖 unsloth 的 `{"detail":…}` 404）。
  **验收（加载态端到端）**: `_station_ready` → `STATION_READY port=8080` + `CHAT_OK choices=1` + `READY_OK`(rc=0)；`_slot_gate 8080` → `SLOT_TOTAL=4 SLOT_BUSY=0`；wrapper 全链 `SLOT-GATE(idle,allow)` → `TASK_RC=0` → **`TASK_DONE exit=0`**；**claude `rc=0 / 36s / OK`**（此前必坏）；**config md5 全程恒定 `755975db…`**（注入不再发生）；三站 `infer-unload` OK。
  **连带修好**: ① claude 路径（其 `:8080` 目标一直正确，真因是 **key 陈旧**非端口）；② C 站 key 占位串（22B `sk-local-noauth…`，即门禁那盏黄灯）由落盘机制自动纠正。**【2026-09-16 更正】** 后半句当时是**错的** —— `infer-load` 只重铸落盘 `unsloth.key`，**从不写 `claude.key`**（claude 侧另存一份拷贝且无任何写入方），故占位串不会被自动纠正；真实修法见 ⑨。
  **诚实记录 —— 过程中修掉我自己两个判据缺陷**: (a) chat 就绪判据原看 `content` 非空 ⇒ **reasoning 模型在 `max_tokens` 小时把配额全给 thinking、无 `content` 字段** ⇒ 假失败；改看 `"choices"`。(b) 原请求**缺 `Content-Type: application/json`** ⇒ curl 默认 form-urlencoded ⇒ 引擎 Pydantic 报 `body: Input should be a valid dictionary`；**且旧实现的 `CHAT_OK` 一直是假阳性**（匹配到的 `"content":""` 来自非正常响应）——"能报 OK" ≠ "真的 OK"。
  关联: O-19、O-25 P1、ADR-0004 第五批 / 补记二。

- **⑤ OpenRouter 免费档每日计数 + 硬规则限速（G13/O-07 扩展）**: 调研先厘清**两个出站源**（zen vs OpenRouter）—— 用户问的是 OpenRouter。实证：20 请求/分（固定，充值不升）+ 每日 **50（从未充≥$10）/ 1000（曾累计充≥$10）**；429/失败**仍计入**配额；**跨 key 全局治理**；**无"免费请求剩余数"可查 API**（`GET /api/v1/key` 的 `usage` 是 credits）。⇒ 结论：**可建，但只能本地自建计数**。落地：`cluster.py egress` 读 `is_free_tier` 定档位 + `.egress_daily.json` 本地日计数（UTC 滚动）+ 80% 预警，调用方发请求前 `_egress_bump()`。**实证**主控 + A/B/C 四端 `tier=paid` ⇒ 本账户日限额 **1000/天**。
  **硬规则（用户拍板「RPM20 限速 + 429 退避」）**：`Invoke-JudgeHttp` 加 **最小 3s 间隔令牌桶** + **429 指数退避**（`attempt<3 → Sleep 2^(attempt-1)`）；`Invoke-RestMethod` → `Invoke-WebRequest -UseBasicParsing`（PS5.1 才能拿状态码）。**验证**：本地假 OpenRouter（429→429→200）端到端 —— 相邻请求拉到 ≈3s、429 后 ≈1s 退避 → `JUDGE_OK`。日 1000 维持软预警，**只在经 wrapper 的出口限速**（opencode 内部 HTTP 拦不到，靠 429 兜底）。
  ⚠ **BOM 坑再度踩中**：Edit 改 `agent-cli.ps1` 剥掉 UTF-8 BOM ⇒ PS5.1 按 CP936 读中文注释**级连误报 38 个语法错**（全假阳性）；补回 `EF BB BF` 后 14 个 `.ps1` 全绿。**凡编辑此 .ps1 必查 BOM。**
  详见 [ADR-0003](../../adr/ADR-0003-OpenRouter密钥与egress路由管理.md)；关联: G13、O-07、O-16。

- **⑥ G8 收口（三站补装）+ 环境隔离选型定案**: G8 原定案（sympy 装两站 / R 走 CRAN 4.6.x）**实际未落地** ⇒ 按用户拍板补装三站：sympy **1.14.0** / numpy 2.5.3 / scipy 1.18.1 / **antlr4 4.11.0** / **R 4.6.1**（CRAN noble-cran40，对齐主控）。功能级验收 `parse_latex(r'\frac{1}{2}')` → `simplify(x-1/2)==0` 全 True。
  两个留档坑（均为"判据自证"续集）：**antlr4 必须钉 4.11**（sympy 1.14 硬校验 `antlr4.__version__=="4.11"`，装最新 4.13.2 时 `import`/`pip show` **看着全对**，直到功能级 `parse_latex()` 才抛 ImportError ⇒ **"包在" ≠ "功能在"**）；**CRAN 源签名两连坑**（换新 key + `signed-by` keyring 必须 gpg 二进制格式，否则 `NO_PUBKEY` 后**静默回落默认源装了 4.3.3**，`apt install` 照样"成功" ⇒ 第一轮"安装成功"是假象）。
  环境隔离选型（问卷式假设"项目间依赖冲突"）：**不采用容器化/沙盒**，用**语言级**隔离（Python → venv/uv，R → renv），容器仅极端兜底（首选无 daemon 的 Apptainer）。四理由=威胁模型不同 / 零自加载纪律 / agent 外壳资产会被切断 / lockfile 对拍精度更优。**待办**：Cpp_Hub 对拍 R 依赖包（7 个）装**项目 renv，不装全局库**。
  关联: G8、G9、O-13；详见 [ADR-0004 附表](../../adr/ADR-0004-统一管理入口为唯一管理面.md)、[Agent调研 §9.10](../../docs/Agent跨项目调用标准与迁移复用调研.md)。

- **⑦ 统一入口能力增强 + 缺口综合汇总 + 文档去时态化**: ① `cluster.py providers` 增**两维**（`_ep_form()` 端点形态：`:4000` 标"⚠ 网关已退役"；`### mem` 记忆层：memory.db 大小 + MEMORY.md/summary 行数）—— 起因是用户问"是否还过 :4000 网关"与"记忆协同层现状"，而 `providers` 当时**答不了**⇒ 按 D3 路径① 给入口加能力而非新增脚本。**实测**：三站**零 `:4000`**（opencode/claude 全 `127.0.0.1:8080`）⇒ **已全直连**，用户记忆正确；**记忆层正主 = opencode 自带 memory**（`~/.local/share/opencode/memory.db` + `memories/MEMORY.md`），**非**文档所记的 `codex-memory` 独立命令（三站 `command -v` 均未命中）—— A 最饱满（MEMORY.md 88 行）、B/C 有库近空（内容在 `-wal` 待合并）。② G1-G14 缺口综合汇总入台账（见 [OPEN-ISSUES §6](OPEN-ISSUES.md)，结论 **8 闭环 / 5 已定案 / 1 待办**）。③ [Agent跨项目调用标准与迁移复用调研.md](../../docs/Agent跨项目调用标准与迁移复用调研.md)：§1.1 补 C 站现状、**§2.1 CLI 定版表去时态化**（原表仍是"直连/过网关混合 + B-claude→LiteLLM(4000)"的过时描述，改为按统一入口现状的**无时态形态表**）、§6 缺口清单补"当前完成情况"列、新增 §9.10（隔离选型）/§9.11（G14/G10 升级回归 SOP）。

- **⑧ Cpp_Hub 假子模块（unmapped gitlink）排查与吸收（A1，用户拍板）**:
  **症状**：`git status` 常驻 ` M spec/d6-agent-standard/Cpp_Hub`。
  **排查链（六条取证，全部机械可判定）**：① 该路径是 mode **160000** gitlink @`88f8fbf`，而 `.gitmodules` 不存在 ⇒ `git submodule status` 直接 `fatal: no submodule mapping`（**结构性非法**）；② 目录内是真 `.git` **库**（独立 2 条提交、**无 remote**、工作区 clean）；③ **决定性**：外层库对象库里那两个 commit **都不存在**（`git cat-file -t` → `fatal: could not get object info`）⇒ **内容零备份**：GitHub 远端同样只有指针，clone 后该目录为空；④ **引入点** = `5f2b395`（09-14 00:06 脱敏大提交里的广域 `git add` —— git 对"含 `.git` 的子目录"默认收成 gitlink）；⑤ **孤儿化** = `cc3b75c`（09-14 12:19 把 `PROJECTS['Cpp_Hub']` 改指 `F:\Cpp_Hub`，提交信息自认"**gitlink 薄壳**"，但**没顺手摘指针**）；⑥ **漂移源** = nested 09-15 20:19 第二条提交（`2666e88`）与记录指针分叉。
  **决策依据（A1）**：逐案对比 —— **B 正式 submodule** 须**为 6 文件 / 约 4KB 新建一个远端仓**、克隆语义全局变更（`--recurse-submodules`）、且噪声只是变形成"指针待更新"（**成因未切**）；**C 解除跟踪+忽略** 把最重的"内容无远端备份"原样留着（07-04 那类坑）；**D 冻结指针** 坏结构 100% 保留且 nested 一提交**必然复发**；**E 整体删除** 会失去 `cpphub-001` 的 golden 断言对象（比现状更不自洽）⇒ **A1 是唯一同时消掉「永久噪声 / 备份缺口 / 假子模块」三类危害且不引入新机制者**，且经核实 `agent-cli.ps1` **全文不读 git**（对 wrapper 零影响）、「试点须为 git 仓库」约束的是**站上工作区**而非主控样本（吸收不违反）。
  **执行（备份优先，遵守 07-04 教训）**：先在 OneDrive `RPC-backup/20260916-Cpp_Hub-gitlink/` 落 **`Cpp_Hub-all.bundle`**（`git bundle verify` = "The bundle records a complete history"）+ **整目录副本**（51 文件、与源**零差异**）；再删 `Cpp_Hub/.git` → `git rm --cached` 摘指针 → `git add` 吸收 6 个实体文件。
  **验收（4 项机械判据）**：① 6 个 blob 哈希与 nested **逐一相同**（`c89cd00a`/`4e19cf5c`/`a1ea2d40`/`f2581721`/`7aef6813`/`8f596feb`）⇒ **字节一致**，`autocrlf=true` 未改内容；② 同 6 个 blob 在外层库 `git cat-file -t` 现返回 `blob`（此前 fatal）⇒ **内容真入库**；③ `git write-tree` + `ls-tree -r` 显示该目录下 **6 条 `100644 blob`、零 `160000`** ⇒ clone 后必得这 6 个文件；④ 索引中 gitlink 计数 **0**、`agent-out/` 仍 `!!` 忽略（吸收的 `Cpp_Hub/.gitignore` 随目录生效）。门禁 quick **9 绿 / 0 黄 / 0 红**。
  **过程中我的验证写法又自曝一缺陷**：用 `git ls-files | git checkout-index --stdin` 做"索引实体化"取证时，**PowerShell 管道把路径啃坏**（4 个 ASCII 名报 `is not in the cache`、2 个中文名反而成功）⇒ **判据假失败**；改用 `write-tree`+`ls-tree` 机械取证。**"判据要先自证"再记一笔。**
  **关联登记（均经用户裁定）**：① **`cpphub-001` 卡与 `PROJECTS` 映射已不一致** —— 该卡 golden（`cpphub_golden.py`）断言 `src/因子计算_核心.cpp`（= 轻量样本结构），而 `Cpp_Hub` 自 `cc3b75c` 指 `F:\Cpp_Hub`（`include/cpphub/core/math.hpp` 结构），且 wrapper **无 per-card 源目录覆盖键**（sync 源严格取 `PROJECTS[$proj]`）⇒ **今天重跑必 golden FAIL**（真源卡是 `cpphub-beta`）—— **暂不动，仅登记**（见 [OPEN-ISSUES](OPEN-ISSUES.md)）。② **暂不加「unmapped gitlink」门禁断言**（该机制纯机械可判定、可正负自证，本可堵住复发路径），仅落档备查。

- **⑨ 凭据面单一真值修正（claude key 第二定义点，凭据黄灯清零）**:
  **症状**：全量门禁 `stations` 黄灯，明细是 **B 站与 C 站**（不止 C）`claude.key` 与同站 `unsloth.key` 不一致。
  **排查链**：① 走统一入口取实况（不翻站上文件）⇒ `secrets status` 只报"落点/权限"（三站全 OK）⇒ 它是**浅判据**，差异只在 `stations` 的深判据里；② 比对主控正本 ⇒ A/B 的 `claude.key == unsloth.key`（43B `sk-unsloth-<32hex>` 真 key），**C 站两份都是脱敏占位串**（`claude.key` 15B 与 `unsloth.key` 22B，均为 09-14 `5f2b395` 密钥脱敏残留的占位值）；③ 读 helper 真身 `secrets/stations/*/claude-key.sh` = `cat $HOME/.config/rpc/claude.key` ⇒ **`claude.key` 是引擎 key 的第二份拷贝**；④ 读 [infer-load](../../ops/station-bin/infer-load) ⇒ 它**只重铸落盘 `unsloth.key`**，`claude.key` **没有任何写入方** ⇒ 该文件必然陈旧（C 是脱敏遗留；A/B 只是 09-14 靠**人工**同步过一次才对上）；⑤ 站上实测 ⇒ **B 站 `unsloth.key`（44B `f738fdec…`）≠ 主控正本 B（43B `c0c883ff…`）** ⇒ **B 站早已被"加载后 key 变新、claude.key 仍旧"命中**（门禁那条**硬编码"C 站"的告警文案**让我上一轮误判为 C 独有 —— 文案本身也是缺陷，已一并修）。
  **决策依据（方案 A：单一真值）**：同一份密钥有**两个定义点**是病根（与 `cluster.py` 中"抄一份就是第二个定义点"的既有纪律同源）⇒ ① `claude-key.sh` 改读 `unsloth.key`（claude 与 opencode 共用一份，第二份拷贝**退役**）；② 门禁判据由"两文件互相比较"升级为「**helper 的实际输出 == 同站 `unsloth.key`**」—— 这是功能判据（claude 真正拿到的 key），且**不因构造而恒真**（仍能抓到"绕过 `infer-load` 手动改 key"）；③ 备选"让 `infer-load` 同时写两个文件"被否：留双份拷贝、且判据随即变成构造上恒真。
  **执行**：正本 3 个 `claude-key.sh` 改写（46B / LF / 逐字节自校）+ 删除 3 份 `claude.key` 正本 → C 站**真跑一次 `cluster.py load qwen3.8-27b-mtp`** 铸真 key（`sk-unsloth-<32hex>`，33s 就绪）→ **回写 B/C 站真 key 到主控正本** → `secrets push`（A 4 / B 3 / C 3，幂等）→ `rm` 三站遗留 `claude.key`（**`push` 是增量的、不剪枝**，必须显式删）→ 卸载 C 恢复状态。
  ⚠ **过程中发现一个真陷阱（我原定顺序差点踩）**：`secrets` 只有 `status|scan|push`（**单向下发、无回写**），而站上 `unsloth.key` 是**每次加载重铸**的 ⇒ 直接 `push` 会用正本里的陈旧 key **覆盖站上真 key**，把该站 opencode/claude 打断。正确顺序只能是「站上取真值 → **先回写正本** → 再 push 才幂等」，本次据此先回写了 B/C 两个站。
  **验收**：① 三站 helper 输出长度与各站 `unsloth.key` 一致（A 43 / B 44 / C 44）；② 三站 `claude.key` 已不存在，落点收敛（A = helper+openrouter+rpc+unsloth；B/C = helper+openrouter+unsloth）；③ 正本 vs 站上逐一 MATCH；④ **全量门禁 `stations` 凭据告警清零**（明细仅剩 A 站 `claude-plugins-official`，属 `inventory/plugins.yaml` 早已登记的 `known_drift`，非本次范围）；⑤ 三站 `infer-unload` OK。
  **两处新增登记（见 [OPEN-ISSUES](OPEN-ISSUES.md)）**：① **`infer-load` 的 key 明文输出** —— 原记为"写进站上日志"，**表述有误，已在 ⑩ 更正**：该行 `log` 只打 **stdout**（进调用方控制台/会话 transcript），而站上日志里的 key 是 **studio 自己**写的、且 `infer-load` 正是从该日志 grep 取 key；真实暴露面比原记大得多（含审计盲区），见 ⑩；② **`secrets push` 的正本陈旧覆盖危害**（上述陷阱）目前靠"加载后先回写正本"的人工纪律兜住，可考虑加门禁断言（"站上 `unsloth.key` ≠ 正本 ⇒ WARN"）。
  关联: O-16、ADR-0003 D1（正本兜底为已定案，本次不改设计，只补"回写"这一必需步骤）。

- **⑩ unsloth studio 日志的明文面收敛（审计盲区补齐 + 权限收紧 + 存量脱敏）**:
  **触发**：用户要求"对 ⑨ 登记的两点（文档明文/掩码写法、`infer-load` 的 key）调研是否需要修"。取证后**更正 ⑨ 的错误表述并扩大范围**。
  **取证的六条事实（全部实测）**：① `log()` 只 `echo` 到 **stdout**，不写文件（[infer-load:21](../../ops/station-bin/infer-load#L21)）⇒ 我方那行的暴露面是控制台/transcript，**不是**站上日志；② **studio 自己把 key 写进 `~/.unsloth/run-<alias>.log`，每次加载 4 处**（`infer-load` 正是 `grep -oE "sk-unsloth-…" "$UN_LOG"` 从它**取**key ⇒ "日志含 key"是**设计使然、消除不掉**）；③ 权限：`~/.unsloth` = **775**、`run-*.log` = **664** ⇒ **组与其他用户可读**；④ 存量累积无上限：A 站 **15 份**（含 2 份 `.pre-repro-*` 副本）、B 4 份、C 2 份 ⇒ 合计 **21 份日志 / 68 处明文 / 16 个历史 key 值**；⑤ **最关键**：`cluster.py secrets scan` 只探 `~/.config/rpc` + `opencode.jsonc` + `settings.json` 及备份，**从不看 `~/.unsloth/*.log`** ⇒ 这 68 处明文**在框架明文巡检的视野之外**（09-14 那轮"明文面收敛"未覆盖，现有门禁也永远发现不了）；⑥ 严重度不夸大：key 是 studio **每次加载重铸**的本地引擎令牌（仅绑 `127.0.0.1`）⇒ 历史值多已随实例销毁失效，真风险是"当前运行实例那把是活的 + 任何 `$HOME` 级备份会外流 + 审计盲区本身"。
  **决策（用户拍板全套 a+b+c+d+e）**：
  | 项 | 动作 | 落点 |
  |---|---|---|
  | a | 我方那行改**掩码**：`log "API Key: $UN_KEY"` → `log "API Key ok (len=… sha8=…)"` | `infer-load`（保留"同一把 key"的可关联性，不泄露材料） |
  | b | **权限收紧**（新加载 + 存量）：目录 `700`、日志 `600`；由 `infer-load` 每次加载强制 | `infer-load` 新增 2 行 chmod |
  | c | **存量就地脱敏**：`sed` 把日志里的 key 掩成 `sk-<prefix>-****` | 三站 21 份日志（**不留含 key 的备份** —— 备份会重建泄露面；改为"临时件+行数/命中数双校验+替换"，逐份校验通过才落盘） |
  | d | **补审计视野**：`stations` 门禁的 `[cred]` 探针新增 `unslothlog=dirperm/files/withkeys/loose`，判据落在**权限**（目录须 700、日志须 600）而非"含不含 key"（后者无法消除） | [rpc_check.py](../../ops/rpc_check.py) |
  | e | 补登「已知剩余明文面」 | [密钥轮换清单](../../docs/security/2026-09-13_密钥轮换清单.md) |
  **执行与验收**：① 三站备份原件 → scp → `sudo install -m 755` ⇒ 三站 sha 一致 `8155968d…`、`bash -n` OK；② 站上 21 份日志脱敏 ⇒ `withkeys 0`、行数逐份不变（校验不通过即 SKIP，未发生）；③ 目录 700 / 日志 600 ⇒ `loose 0`；④ **端到端实跑**（`infer-load` 在加载路径上，不能只靠 `bash -n`）：C 站 `load qwen3.8-27b-mtp` ⇒ `API Key ok (len=43 sha8=9de8ff4d)`（**输出已无明文**）+ `dir=700 / log=600`，随后卸载 C；⑤ **负向自证**：把 C 站目录改 755 + 一份日志改 644 ⇒ 门禁**确实报出**两条（"`~/.unsloth` 权限 755 (应 700)"、"1 份 run-*.log 权限非 600"），恢复后复跑无误报；⑥ 全量门禁 **13 绿 / 1 黄 / 0 红**（余黄灯仍是 `inventory` 已登记的 A 站插件 `known_drift`）；⑦ 新 key 按 ⑨ 的纪律**先回写主控正本**。
  **① 那一项的结论（文档掩码写法）**：**不改判据逻辑**，只在 `secrets` 检查的处置建议里补一句"文档引用样串/占位串请掩码为 `sk-xxx-****`" —— 把这条纪律**绑定到门禁输出**上，而不是只留在记忆里（同一坑曾在一次提交内踩两次）。

- **⑪ 凭据下发方向保护 + `secrets pull`（把"人工纪律"变成"入口动作 + 机制闸门"）**:
  **背景**：⑨ 登记的遗留 —— `secrets` 是**单向下发、无回写**，而站上 `unsloth.key` 每次加载重铸 ⇒ 直接 `push` 会用正本陈旧值**覆盖站上真 key**、打断该站 agent。此前只靠人工纪律（"加载后先回写正本"）+ 三处文档约束兜住。
  **决策（用户拍板"执行"）**：**不加"常态黄灯"式提醒**（那只会制造噪声、最后被人整体忽略），改为**在危险动作上设闸 + 把正路做成一等入口动作**：
  | 项 | 设计 |
  |---|---|
  | **新增 `secrets pull [A\|B\|C]`** | 把"站内产物"型凭据**从站上收回**主控正本（SFTP 原始字节）—— 这正是原先手工 `scp` 的那一步，现在是一等入口动作 |
  | **`push` 默认拒绝覆盖**"站内产物"型凭据 | 站上已有且与正本不同 ⇒ **跳过**并打印两条出路（`secrets pull <站>` / `secrets push --force`）；`--force` 保留强制能力 |
  | `SECRETS_PROBE` 增 `[kv]` + `status` 增"站内产物"行 | 只打**归一化指纹**（去换行后 sha256 前 12 位，**不打值**），显示"站上 vs 正本 一致/不一致 + 下一步" |
  | 类型显式化 | `STATION_MINTED = {"unsloth.key"}`（站内产物型：真值在站上，正本只是兜底） |
  **顺带修一处既有真缺陷（非本次引入）**：`_flow_rotate_status`（`flow rotate` 首步）把 `ssh_run` 返回的**原始文本**喂给期望 dict 的 `_secrets_verdict` ⇒ `p["reachable"]` **直接 TypeError**；即便不崩，下一行 `v != "OK"` 比的是 tuple ≠ str ⇒ 该步**恒判"需关注"**。改为直接调 `probe_secrets` 取状态串（并去掉那次多余的 `ssh_run("A","true")`）。**修复后实测**：`_flow_rotate_status({'go':False})` → `(True, '凭据落点/引用/权限: A=OK, B=OK, C=OK', [])`。
  **验收（正负双向 + 可回滚）**：① `status` 三站"站内产物"均 `一致 ✓`；② **负向**：把正本 C 换成假值 → `push` ⇒ `C 站 下发 2 个` + **跳过 `unsloth.key`**，站上指纹**未变**（`9de8ff4d…`）⇒ 闸生效；③ **`--force`** ⇒ `C 站 下发 3 个`、站上指纹变为假值 ⇒ 强制路径仍可用；④ **回滚**：用临时备份还原站上真 key → `secrets pull C` ⇒ `回写正本 1 个`；幂等复跑 ⇒ `已一致 -> 跳过`；终态三站 `一致 ✓`（C 回到 `9de8ff4d…`）；⑤ 临时备份删除；⑥ 全量门禁 **13 绿 / 1 黄 / 0 红**。
  **纪律**：**"危险动作 + 人工纪律"必须升级为"危险动作 + 机制闸门"**；且正路（回写）必须是一等入口动作 —— 否则人总会绕过它走捷径。

- **⑫ 三项 09-16 遗留闭环（清减 / G10 降级 / 卡片标记）**:
  **① `_agent-cli-bom.ps1` 清减 —— 取证推翻了我自己的判断**：原登记写"整份过期副本/死代码"；按 D5 **先查引用**时发现它是**活的** —— 运行时的 BOM 副本其实写在 **TEMP**（[agent-cli.ps1:1311-1322](../../ops/station-bin/agent-cli.ps1#L1311-L1322) 的 `$ChildScript = Join-Path $subDir 'agent-cli-bom.ps1'`），而 `ops/station-bin/_agent-cli-bom.ps1`（112KB）是 **O-26 串行基线测量的一次性工装**，被 root 级 `_o26_serial_loader.ps1` 以**固定路径**引用。**求证链**：三站 `/usr/local/bin` · `$HOME` · systemd · `agent-workspaces` **零引用** ⇒ 删除该"并列入口" **+ 其唯一引用者** `_o26_serial_loader.ps1`，并同步 `inventory/ops.yaml`（`frozen_ops_scripts` 181→180）。**验收**：门禁 `scripts` = 扫描 206 · 冻结 180 · 未登记 0；`syntax` .ps1 由 14 → **12 文件 / 0 失败**。**教训**：判"死代码"必须落到**引用反查 + 运行时同名件辨析**（同名 ≠ 同一物；`agent-cli-bom.ps1` 与 `_agent-cli-bom.ps1` 是两回事）。
  **② G10 负向断言 → 观测项**：重评确认"位置参数必挂死"**不是确定行为**，三条证据 —— 09-14 复测位置参数 4/4 成功（与本轮"无输出"**冲突**）；`timeout 25` 探针**区分不了"挂死"与"慢"**（慢即被读成"仍挂死" ⇒ **假 PASS**）；官方 CLI 参考里位置参数本就是常规用法之一（原 FAIL 文案"上游行为已变"会误导）。改法：`agent-cli-smoke.sh` 该用例改 `report … INFO`（`report()` 增 `INFO` 计数、汇总行加 `INFO=`），并同步 [Agent调研 §9.11](../../docs/Agent跨项目调用标准与迁移复用调研.md) 的 SOP ② 与结论。**验收（提取真实代码 + 桩替 ssh/引擎，跑三分支）**：引擎未加载 → `SKIP`；位置参数"有输出" → `INFO`（`FAIL=0`）；"空输出" → `INFO`（`PASS=0`）⇒ **两个方向的误判都被消除**。
  **③ `cpphub-001` 卡片标记（零风险机制，用户裁定后执行）**：在 front-matter 加 `status: retired` + `note:`，写明"目标源目录是轻量样本 · `PROJECTS` 已指真项目 · wrapper 无 per-card 覆盖键 ⇒ 派发必 golden FAIL"。**机制选型依据**：读 [Get-FrontMatter](../../ops/station-bin/agent-cli.ps1#L628-L637) 确认其白名单闸（`if ($h.ContainsKey($k))`）会**静默忽略未知键** ⇒ 标记不进 prompt、不影响解析，故这是"零风险标记"。**验收**：提取该函数直接调用 ⇒ `model/cli/sensitivity/timeout_s/accept-golden.cmd/task/body` 全部解析正确，且 `ContainsKey('status')=False`、`ContainsKey('note')=False`；**"必 golden FAIL"也机械证实** —— `F:\Cpp_Hub\src\因子计算_核心.cpp` **不存在**（golden 必报缺失）。**另记一条新发现**：该样本**已被 2026-09-12 试点本身改过**（源码已含 `向量均值`）⇒ **不再是干净 fixture**，即使重指也当不了回归用。
  **④ 顺带新登记（本轮发现）**：`scripts` 门禁的治理圈只有 `ops/`（[`_iter_ops_scripts`](../../ops/rpc_check.py) 显式限定 `rel.startswith("ops/")`；⚠ 该函数 **2026-09-22 已改名 `_iter_governed_scripts`**，见同页 [2026-09-22 ⑮](DEVELOPMENT-LOG.md)），仓库根仍有 5 个一次性脚本（`audit_extra.sh` / `audit_gfx.sh` / `audit_llama.sh` / `_o26_reverify_loader.ps1`，外加**根级 `test-cards/`**）**不被任何清单覆盖** ⇒ 已登记待定（扩展门禁范围属新能力，走 ADR-0004 D3）。

- **⑬ 任务卡证据回收闭环（[ADR-0005](../../adr/ADR-0005-任务卡证据回收闭环.md) 阶段 0）—— 让 verdict 从"转述"变"可复核"**:
  **触发**：用户提出"把取证矩阵从文档审查扩展到任务卡验收"（`evidence_manifest` + 异基座审计编排管线证据流）。调研（[2026-09-16 证据流调研](../../docs/research/2026-09-16_任务卡证据流可重放性调研.md)）结论：**前置条件不是 manifest，而是"证据根本不在手上"** ⇒ 先做阶段 0。用户裁定：**按 ADR 落档后执行**。
  **改了什么**（单文件 [agent-cli.ps1](../../ops/station-bin/agent-cli.ps1)，两条路径）：远端 opencode 路径新增**合批单连接回收**（`marker + base64`）把 `.meta → judgment-record.txt`、`.prompt.txt → prompt.txt`、`.progress → progress-trace.txt`、`.accept-cmds.txt`、`.golden-cmd.txt` 收进 `agent-out/<ts>/`；claude 备路补 `prompt.txt` + `stderr.txt` 并清理 scratch；`run.json.accept_golden` 增 **`sha256` / `base`**（当次权威 checksum，只此一处，不立第二份文件）；顺带修 `%TEMP%` 临时件泄漏 + 恒真守卫 + **collect 失败时保证据**（`EVIDENCE_LEFT_IN_TEMP=` / `EVIDENCE_LEFT_IN_SCRATCH=`）。
  **验收（三次端到端实跑，夹具 `tmp/e2e-evidence-card.md` + `tmp/e2e_evidence_golden.py`）**：① 9 件齐全；② **`judgment-record` ↔ `run.json` 逐项一致**（`TASK_RC=0`/`ACCEPT_OK=1`/`GOLDEN=1`、`QUEUE_S=2`/`RUN_S=21`）；③ **`sha256(prompt.txt) == prompt_sha256`**（新增自证能力，`e5a7027e…`）；④ `accept-cmds.txt == true`；⑤ **`accept_golden.sha256 == 仓库 golden 源哈希`**（新增能力，`739adc69…`）+ `base` 正确；⑥ `%TEMP%` 无残留；⑦ `progress-trace` 12 行；⑧ 离线回归 `_fm_golden_test.ps1` **9/9** + BOM 完好 + 门禁 `.ps1` 12 文件 0 失败。
  **三处踩坑（诚实记录）**：① **GNU tar 的 `host:path` 陷阱** —— 本地解包 `tar -C C:\…` 被当成远程主机（`Cannot connect to C: resolve failed`），加 `--force-local` 后又不认反斜杠路径 ⇒ **弃用 tar**，改纯 base64 文本通道；② **PS 5.1 原生命令参数解析**（`& $tar -czf $path` 把 `$path` 当 cmdlet 执行）⇒ 本文件既有**数组展开**手法是正解；③ **验证卡自身引号**（`accept: - "true"` 致命令列表里带引号）—— 我的断言错，非代码缺陷。
  **顺带测出的框架级问题（已登记）**：**每次 ssh/scp 建连 14-17s**（5 次采样；`inet` 仅省 3s、与 GSSAPI 无关、**ControlMaster 在 Win32-OpenSSH 9.5p1 不可用**）⇒ 这促成了 D4d"合批回收"：collect 连接数 8→4，**耗时 115s → 49s（省 66s/run）**；单次 task run 墙钟约 420s（其中模型运行仅 21-53s，其余是连接与 213M sync）。
  关联: ADR-0005、[OPEN-ISSUES](OPEN-ISSUES.md)（阶段 1/2/3 待做）、[调研文档 §7.1](../../docs/research/2026-09-16_任务卡证据流可重放性调研.md)。

- **⑭ 控制面传输绑定 LAN IPv4（[ADR-0006](../../adr/ADR-0006-控制面传输绑定LAN_IPv4.md)）—— 单次 task run 421s → 48.5s**:
  **触发**：⑬ 落档时顺带测出的"框架级：每次 ssh/scp 建连 14-17s"（[OPEN-ISSUES](OPEN-ISSUES.md)），用户裁定"先做"。
  **根因（实测，非推断）**：不是 sshd/`UseDNS`/GSSAPI，而是**主控（Windows）解析 `*.local` 需 16-17s 且只返回公网 IPv6**（`Dns.GetHostAddresses` = 17,016ms，结果仅 `2409:8a20:…`）；站上 `echo $SSH_CONNECTION` 证实**控制面实际经 ISP IPv6 绕行、不在局域网内**。`ControlMaster` 在 Win32-OpenSSH 9.5p1 **不可用**（`getsockname failed: Not a socket`）。**同源先例两处**：[cluster.py:160-175](../../ops/cluster.py#L160-L175) 早已诊断为 F19（`/api/status` 129.6s 根因）并只对长驻 web 进程做进程内缓存；[cluster.py:89](../../ops/cluster.py#L89) 的 C 站条目早已"保持 IPv4 规避 paramiko/IPv6"。
  **改了什么**：① `~/.ssh/config`（机器级，备份 `config.bak-20260916` 228B）—— A/B 名字保留为别名但 `HostName` 绑定 LAN IPv4、三个 IP 加身份块（否则用户名退化为本机 `peng` ⇒ **挂起 >90s 等 stdin**，实测踩到）、全部 `AddressFamily inet`；② [cluster.py](../../ops/cluster.py) `STATIONS` 的 A/B 改 LAN IPv4；③ [net.yaml](../../inventory/net.yaml) 新增 `lan:` 段（LAN 管理面真值 + DHCP 现状 + 测量方式 + 维护约定）；④ [rpc_check.py](../../ops/rpc_check.py) `stations` 断言新增 **(h)** 防漂移子项（`ssh -G <名>` 的 hostname 必须 == net.yaml 登记 IP，纯本地无网络开销）。
  **验收**：`ssh -G` 三行正确（含 `addressfamily inet`）；**按名 16,200ms → 169/199/182/171ms（≈90×）**；三站 `$SSH_CONNECTION` 均回到 `192.168.1.36 → 192.168.1.x:22`（改前 A/B 为公网 IPv6）；**门禁 (h) 负向自证**（把 net.yaml 的 B 站 IP 改成 `.99` ⇒ `[FAIL] stations` + 漂移提示 + 退出码 1 阻断，还原后恢复）；`usb4` 断言 PASS（net.yaml 仍可解析）；**端到端真跑：单次 task run 421s → 48.5s（8.7×）**，其中 `RUN_S=38s` 是模型本身 ⇒ **框架开销 ~383s → ~10s**；产物 9 件齐全 + 三项自证全 PASS + `%TEMP%` 0 残留。
  **顺带登记 1 项**：ssh/scp 调用点仍未统一加 `-o BatchMode=yes`（把"卡住"变"快速失败"）；建议（可选加固）路由器按 MAC 做 DHCP 保留。
  关联: [ADR-0006](../../adr/ADR-0006-控制面传输绑定LAN_IPv4.md)、[OPEN-ISSUES](OPEN-ISSUES.md)（该项闭环）、[ADR-0005](../../adr/ADR-0005-任务卡证据回收闭环.md)（其 D4d"合批回收"是本问题的第一层缓解）。

### 2026-09-15 — 管理面清减四批 + 文档漂移门禁日

> 补记（同 09-16 回填）。决策依据全文见 [ADR-0004 第一~四批](../../adr/ADR-0004-统一管理入口为唯一管理面.md)。

- **清减第一批（7 文件）**: D5 顺序（先补入口→验证→再删）**当场拦下我自己的误判** —— `check_llama_version.*` 看着"已被 `cluster.py versions` 覆盖"，逐条核对才发现**覆盖不完整**：入口的完整性列三站恒显"缺失"（**只找 `MANIFEST.md5`，站上文件叫 `MANIFEST`** ⇒ 长期假阴性）；旧脚本还有 **`rpc_protocol` 采集**与 **C 站旧 IP `192.168.1.24`**（现 `.37`，旧脚本对 C 本就 exit 2）。动作=先并入能力（`MANIFEST` fallback + `rpc_protocol` 纳入比对）→ 再删。顺带修 **locale 陷阱**：站上 `LANG=zh_CN.UTF-8` 使 `md5sum -c` 打印**"成功"**而非 `OK` ⇒ 按英文解析会把**全部通过读成全 FAILED**；修法 `LC_ALL=C md5sum -c`（与 memory 里"`free` 输出随 locale 变 ⇒ 改读 `/proc/meminfo`"同源复发）。**"能力看起来重复" ≠ "能力已被覆盖"**。
- **清减第二/三批（判据换成可机械判定，不需判断能力）**: 第二批=①自标 `DEPRECATED`/`勿执行`（8；重跑会把 `***REMOVED***` 占位符写进生产配置）②含占位密钥+认证必需（19；必然 401 的空壳）③靶子系统已退役（4，`_bs2_*`→LiteLLM `:4000`）⇒ 脚本 250→**219**，含占位密钥的 git 跟踪文件 36→**5**。引用反查**抓出真风险**：活跃手册 `_station-bin/REPRO-RUNBOOK.md` 仍教"key 重铸后**必须重跑 `_bkeyupdate.sh`**"，而该脚本已标"勿执行"⇒ **照手册操作会写坏生产配置**；已改为走入口（`secrets status/push` + `providers`）。第三批=**脚本显式引用不存在的靶子**（LiteLLM 网关簇 9 + claude 死端口 `:8087` 写配置 3）⇒ 219→**207**（冻结存量 193→**181**）。其中 `_acldset.sh`/`_acldoverride.sh` 会**整体覆盖**生产 `settings.json` 成死端口+`dummy` token，今天跑一次就把 claude 打断。
  ⚠ **本次核查中我自己踩了 `pgrep -f` 自匹配**：`ssh host 'pgrep -f litellm'` 三站**全报 RUNNING** —— 真因是 **ssh 那侧包装 shell 的命令行里就含该模式**，`pgrep -f` 匹配到自己；改用 `ps -eo args | awk` 才得真相（三站无 litellm 进程）。**纪律**：跨 ssh 的 `pgrep -f` 必然自匹配，进程存在性判据一律走 `ps args` / `pgrep -x` 并核对全文。
- **清减第四批 = 文档漂移审计（脚本的另一半：清的是文档）**: 方法四步（**实况取证 → 机械扫描 → 逐条核对防误报 → 分级处置**），核心纪律 **"机械命中" ≠ "真漂移"** —— 必须分**①真漂移（改）②历史记档（保留原文+加现状注记，不改写历史）③假阳性（不动）**。全仓 md 扫描结果：真需改文档内容的仅 **7 处**（派发/路由规则、退出码语义、隧道方案已废、网关路径、仓库路径前缀、C 站 open issues）；**失效相对链接 65 条**（病根都是"前缀写重"：`spec/<x>/` 里的 `../spec/y` → `spec/spec/y`）⇒ 限"**能唯一确定新目标**"才改，**65 → 4**（余 4 各有正当理由，不猜）。**关键产出 = 新增门禁断言 `doclinks`**（md 仓库内相对链接可达；外链/锚点/占位/库外不判）—— 文档漂移方向是单向的（代码改了会红，文档改了不会），**只能靠门禁不靠自觉**；且特意**放弃**判"语义过时"（需人读，判不准的项写门禁只会制造噪声）。门禁 13 → **14 项**（quick 8→9）。自证（正+负）：正 → 144 md / 840 链接 / 失效 0 PASS；负 → 注入一条坏链（配"好链/库外/占位/外链"四对照）⇒ **只报那一条**、exit 1。关联: ADR-0004 第四批、[OPEN-ISSUES §6](OPEN-ISSUES.md)。

### 2026-09-12 — 评审环 / 看板 / 栅栏门 / 批量闭环日

- **Cpp_Hub 试点全链路闭环（O-06/O-12 关闭，O-13 半收口）**: 轻量 C++ 工程（含中文源文件名 `因子计算_核心.cpp`/`因子计算_run.cpp`，git init）+ 补建 `agentsync-templates/cpp` 四型模板（兑现 IMPLEMENTATION 声明）；B 站预置编译链 `g++`/`cmake` + pytest。`test-cards/cpphub-001.md` 挂主控独立 golden（`cpphub_golden.py`，纯源码静态断言，避开 Win10 无编译链），端到端两次 run 均 `exit 0 / accept_golden.passed=true / GOLDEN_PASS`（最近 202609122223140613）。**试点验收桥接三项台账关项**: O-06 中文路径/文件名端到端（tar UTF-8 跨站无乱码+模型按原中文名编辑+golden 反替代检查）；O-12 strong accept 关闭判据「下一任务卡设计时落地 golden」达成；O-13 编译链就绪但 golden 未走真编译 → 半收口，R/sympy 单列。失败修复: agent-cli 项目未注册 → `PROJECTS` 补 `Cpp_Hub`；golden cmd 改系统 `python3`（A 站无 .venv）。关联: Cpp_Hub-001、O-06、O-12、O-13。

- **O-24 ④ 单机并发纪律入册（P0 收口，执行）**: O-18 铁律补单机语境——手册 §2 agent-cli 新增「并发纪律」条（单机勿就地叠并发，同一带宽顶起 ~2.8×，扇出优先跨站各 1）+ ARCHITECTURE §4「单机形态同样适用」锚点；手册「并发」条目同步更新 readonly 层 2 锁已激活（O-17）。OPEN-ISSUES O-24 ④ 标记入册。关联: O-24/O-17/O-18。

- **O-16 评审环落地（`agent-cli review`）**: JUDGE_TABLE 五源路由落盘主控 agent-cli.ps1（商业 API / ultra free / DS V4 RPC / M2.7 / 主控 opencode 备源），advisory 语义（score=不合格仍 exit 0 + 幂等复用 + `--overwrite` 重审）；judge=ultra 实测生成 review.json。关键教训：main judge 标 local 必须用站内模型（防敏感数据外发）；CoT judge max_tokens=8000、按源参数化；judge 调用 retry≤2；长产物评审取头尾截断。
  - 关联: O-16 closed；文件: agent-cli.ps1、THROUGHPUT-BASELINE.md、CLOSED-LOOP-ANALYSIS §3.2
- **O-25 P1 槽位门落地**: `ops/station-bin/_slot_gate.sh`（远端 `/slots` 探测）+ `Invoke-SlotGate`；仅本地 `cluster-litellm/*` 引擎走门，egress `opencode/*` skip；busy≥total 或 queue>0 → exit 24 SLOT_BUSY reject（`--slot-allow-busy` 放行），slot 记入 run.json。并入 O-08/F1。
- **O-25 P2 看板落地**: 纯 file:// 单文件方案 — `make-dashboard.ps1` 生成器 → `dashboard.html`（self-contained，内联 ledger+run.json，完成区 22 行三态 + 运行中/Live 拉 `.progress`）。离线验证通过（BOM/AST/生成/ _fm_golden_test 9/9）。
- **批量闭环（总览表与详情节对齐）**: O-09（BS-1 isolate_xdg，L1 PASS 消除 SQLite 写锁串行化）、O-10（并入 O-11）、O-11（跨站扇出 L2 端到端 + L3 回归，`o11-fanout-readonly.md` 双站并发 ACCEPT_OK/GOLDEN_OK）、O-15（claude 备通道 + `--continue`）、O-17（readonly 层 2 锁）、O-24（P0-①--continue 实证 + P0-②被 O-16 覆盖）。
- **O-26 分解派发闭环**: decompose 拆 2 分片 A/B 双站并行，并行 465.1s ≪ 串行 720.8s（ratio 0.645）；落地修复 2 bug（`Start-Process .ExitCode` 偶发 null、`$MyInvocation` 派发无 BOM 副本）。
- **C 站 gpt-oss-120b HIP 引擎落地**: 改用 `/home/scott-lau/Applications/llama-gfx1151/llama-server`（ROCm HIP，`ROCm0`）；修复 `BACKEND=` 无尾随换行粘连 bug；port 8080，`/health ok` + `/v1/chat/completions` HTTP 200。关联: station-c/DEPLOYMENT.md。
- **台账同步**: OPEN-ISSUES 总览表状态回写对齐详情节（O-09/10/11/15/17/24），遵循单一真值。

### 2026-09-11 — M2.7 实跑 + 五源评审路由定案

- MiniMax-M2.7（C 站，121G UD-IQ4_XS，Vulkan/ROCm0）16 题批量实跑（tmp/res_m27，117936 tok / 5490s），decode 21.5 / 22.1 t/s。入库 THROUGHPUT-BASELINE.md。
- 五源评审路由（CLOSED-LOOP-ANALYSIS §3.2）定案，替代 review subagent 单一路径 → 2026-09-12 落地。

### 2026-09-10 — 同模型横向基准

- HARNESS-SAME-MODEL-BENCH-2026-09 建立（同模型、多后端/多站横向对比基准）；A 站 Hermes Agent 插件生态盘点并入 PLUGIN-LEDGER §6。

### 2026-09-09 — 单机闭环韧性批 + strong-accept

- **--continue 续接循环落地**: front-matter `continue-timeout-s` 独立预算键（续跑不继承首跑已耗尽预算）；真实恢复场景实测（dogfood-resume-recovery v3）→ 手册 §2a.5。关联: O-24 P0-①。
- **strong-accept 落地（O-12）**: M1-M4 全链（front-matter 解析 / .golden/ 洁净注入 / 权威 checksum 防篡改 / .meta+run.json 契约）；V0 验证门 PASS（ACCEPT_GOLDEN_OK=1、哨兵 NOT_OBSERVED）、TAMPERED 安全侧失败实证；修复 tar `-xzf→-xf`、collect 静默。
- **O-19 4/4 闭环**: 两站模型全卸载致空推理 中止场景全链修复。
- **三站插件统一**: DCP(codex-memory 0.6.5 + @tarquinen/opencode-dcp)+codex-memory 三站同构安装；PLUGIN-LEDGER 建立。
- **CLOSED-LOOP-ANALYSIS-2026-09-09**: 单机工作流 4 类断点（review 缺 / --continue 缺 / claude 备通道缺 / 单机排队治理缺）分析定案。
- **回归框架**: `_fm_golden_test.ps1`（离线回归 9/9）。

### 2026-09-08 — 分布式引擎深化 + 事故铁律

- **叠加加载死机事故（A 站 kernel panic）**: C1(HIP 62G 常驻) + C2(再载 63G) 叠加 125G>124G。教训铁律升级: ①引擎对比测试必须串行+卸载确认 ②`-ngl -1` 单机高危 ③load-gate 硬规则（检查已有进程 RSS 叠加，旧 load-mem-gate 漏检项）。
- unsloth studio 单站 HIP 后端可用（gpt-oss 120B MXFP4: prefill 112-138 / decode 49-53 t/s）；同条件后端对比 nemotron-120B: HIP 20.5 vs Vulkan 23.2（Vulkan 略优）。
- C 站部署落地: 内核 6.17.0-23 钉住（GRUB 子菜单索引）、环网 thunderbolt MAC 绑定根治、UMA FB=4G、看门狗关闭、gpt-oss 引擎 BR。关联: station-c/DEPLOYMENT.md。

### 2026-09-06/07 — ctx 一致性 radical fix + wrapper 加固

- **O-21 服务端 ctx 修复闭环**: `/props` 实载 n_ctx=65536 而模型通告 131072 → 服务端 `-c 65536` 是 400 真根因；conf CTX 65536→131072 重载 A 站 gpt-oss，specaudit 重跑全程无错。
- **O-23 复杂度路由 ctx 解耦**: profile.context 只是元数据，从未传给引擎；opencode.jsonc 固定 131072；引擎 ctx 由 flavor 预设决定 → 三者解耦根治。D-18 radical fix B（引擎 ctx=唯一真相）。
- **D-16 复杂度路由 + D-17 wrapper fail-fast 加固**（DECISIONS v1.1）。O-22 `.meta` 残留误导收口。

### 2026-09-05 — 最小实现批

- **O-01 --attach 传输最小实现落地** + 端到端验证（schema 字段↔传输通道闭环）。
- **O-20 修复**: Invoke-Workspace 目标站判定被 PowerShell 动态作用域污染（`$HostName` 污染 → 恒回退 'B'），修复+实机验证。

### 2026-09-04 — 台账制度化 + BS 验证门 + 跨站架构

- **OPEN-ISSUES 台账建立**: 单一真值总账（P3 残留 / BS 验证门 / 升级项 / 风险 / 跨站待办），状态变更回写铁律。
- **DECISIONS 登记册建立**（v1.0，D-* 决策单一口径）。
- **BLINDSCAN-v2-orchestration §8**: 复现记录 + 跨站扇出调研。**BS 验证门 L1 全过**: BS-1 写锁串行化成立非危重（WAL+busy_timeout 排队非阻塞）；BS-2 gpt-oss 编排层 3 线程并行 52.1s≪串行 110.9s、跨站 A+B 并发 ratio 0.71 → **扇出押编排层并发 HTTP + 跨站各 1 并发**；BS-3 slot0-stuck 未命中（概率性不能免疫）；BS-6 并发≈串行。ADR-0001/0002 关联。
- **F1 后端并发探测** → 降级为观测先行（同站叠并发被带宽顶起）。

### 2026-09-03 — 框架奠基 + 验收通过

- **DESIGN v1.0 批准**（Step 3-4，含 F1 定案）；CHECKLIST 建立；IMPLEMENTATION v1.2 实施锚点落档。
- **V0 六门验证**（B/A 站实测）: A1 薄壳导入 / A2 claude 遮蔽 / A4 A 站记忆 / A5 bash 并发写不锁 / A6 flock 跨 ssh — 5 PASS + 1 部分验证。
- **A1-A16 功能全过 + 不变式 7/7 + 错误处理 6/6**: 路由拒绝（exit 2/4）、锁互斥（exit 3）、孤儿恢复、网络失败（exit 5）等全链路。
- **验收轮**: 有条件通过 → 修复批四项（P1a scrubber + P1b 任务卡正文传输 + P2-1 时间语义 + P2-2 退出码 5）全实机复验 → **验收通过（2026-09-03 16:30）**，质量门 4.5/5 档 A，遗留 P3×5 登记。
- **paper-pilot 试点闭环（A14）**: 真实任务卡 `test-cards/paper-pilot.md` 跑通（accept 双 pytest 11+29 passed，产物回收 D:\Paper\agent-out，main git 无越界）。
- **unsloth-a-station:** A 站 unsloth（b10715 HIP 引擎）就位。

***

## 持续追加模板（下方为新里程碑占位，按需复制上移）

### YYYY-MM-DD — <里程碑名>

- <事件>: <简述 + 验收证据链接 + 关联 O-xx>