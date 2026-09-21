---
proj: paper
task: sanitized 附件旁路探针(P3) - 只回两行, 不读写任何文件
model: claude
cli: claude
sensitivity: sanitized
readonly: true
timeout_s: 120
---
## 任务描述

Echo probe。**不要**读写或修改任何文件，**不要**调用任何工具（本卡只需读上下文并回两行）。

同**一个** Windows 绝对路径被刻意植入了**两处**：

1. **本卡正文**（⇒ 出网前必经 scrubber 消毒）；
2. **附件 `.attach/scrub-probe.txt`**（⇒ 按 `Invoke-Scrubber` 的**唯一调用点**只作用于 `$promptFull`，附件内容**不**经它）。

请**严格**按下面两行回复，**不要**加任何其它文字、解释、前缀或标点（连"以下是"都别加）：

LINE1=<你在**本卡正文**里看到的那个 Windows 路径：逐字照抄；若你看到的是被替换过的形式，就照抄那个形式；若一个也没有，写 NONE>
LINE2=<你在 **`.attach/scrub-probe.txt`** 里看到的那个路径：逐字照抄；若没有，写 NONE>

（本卡正文里植入的路径就是这一条：D:\Paper\agent-out\secret.xlsx）

---

> **用途**：把 [scrubber 规则扩充裁定 §5-3 / §6-P3](../../../docs/security/2026-09-21_scrubber规则扩充裁定与影响面.md) 里那条**只有代码路径判定、未经实测**的结论 ——
> 「**附件内容不经 scrubber**（`scp`/`Copy-Item` 原文，主路 L1227/L1230、claude 路 L2290）」—— 升到**实测**。
>
> **为什么这值得测**：DESIGN §9 不变式②（"消毒在控制台完成，出网字节里没有敏感形态"）在语义上覆盖"到达 agent 的一切输入"，
> 而 `Invoke-Scrubber` 实际只作用于 `$promptFull`。若卡同时满足「附件含敏感内容」+「模型指向云端」，
> 则**附件内容会原样进云端上下文**（agent 按 prompt 提示"按需读取"它）⇒ 该不变式在附件上是**空的**。
>
> **设计：一次 run 内含对照组（这是本卡的可信度来源）**
> - **LINE1 = 控制组**：证明"这次 run 里消毒闸**真的工作了**"。若 LINE1 不是 `[REDACTED-PATH]` 而是原路径，
>   说明消毒**没跑**（是另一类问题）⇒ **本卡整张作废**，不能拿 LINE2 得结论。
> - **LINE2 = 实验组**：同一样串经附件进来。
> - **两侧同串、只差路径** ⇒ 结论不需要跟历史 run 比，**自对照**。
>
> **为什么用 Windows 路径做样串**（而不是 `sk-`/`AKIA`/私钥块）：它**同时**满足两个约束 ——
> ① 被 `win-path` 规则覆盖（正文侧必被抹 ⇒ 控制组成立）；② **不触发**本地 `secrets` 门禁（其正则只有 `sk-`）
> 也**不触发**远端 GitHub push-protection（无该形态的 detector）⇒ 可**入库**、可复跑。
> ⚠ 若换成凭据样串，就必须按段拼接（见 `_scrubber_coverage_test.ps1` 顶部注释），而**卡片没法运行时拼接**。
>
> **跑法**（**零站上引擎、零站上模型** —— claude 备路在 station-ready/sync 之前分支，走主控本地 spawn ⇒ OpenRouter 云端）：
> ```powershell
> powershell -ExecutionPolicy Bypass -File ops\station-bin\agent-cli.ps1 task paper `
>   -Card spec\d6-agent-standard\test-cards\scrub-attach-probe.md `
>   -Attach ops\station-bin\attach-test\scrub-probe.txt
> ```
> 成本：**1 次免费档请求**（`claude` = `thinkingmachines/inkling:free`）；不需要 `cluster.py load`。
>
> **判读**（在 run 归档里看 `agent-output.txt`，run 目录见控制台 `RUN_DIR=` / `d:\Paper\agent-out\<ts>\`）：
>
> | LINE1（控制组） | LINE2（实验组） | 结论 |
> |---|---|---|
> | `[REDACTED-PATH]` | `D:\Paper\agent-out\secret.xlsx`（原文） | ✅ **P3 假设成立**：消毒只作用于 prompt，**附件内容原样进云端** ⇒ 不变式②在附件上是空的 |
> | `[REDACTED-PATH]` | `[REDACTED-PATH]` | ⛔ **P3 假设被推翻**：附件**也**被消毒了（说明我看漏了一处调用点）⇒ 改裁定 §5-3 |
> | 原路径（未被抹） | 任意 | ⚠ **本卡作废**（控制组失败）：`sanitized` 闸没跑到，或 `$sens` 没解析成 `sanitized` ⇒ 先查 front-matter 与 `SANITIZED gate:` 行 |
> | `NONE` / 格式不符 | 任意 | ⚠ 模型没照格式回 ⇒ 加长/简化指令重跑，**别**据此下结论 |
>
> **顺带可判的两条**（同一 run 的产物，不必额外跑）：
> - 控制台应出现 `SANITIZED gate: scrubbing prompt (P1a)` + `SCRUB[win-path] hit: …` ⇒ 消毒闸**在 claude 路也生效**（这是 §5-1 新增的 block 判据所在的分支）。
> - `run.json` 的 `attach` 应为**对象数组**（含 `name`/`src`/`sha256`）而不是名字数组 ⇒ 附件身份在这条路上也有摘要（v2 证据面）。
>
> **诚实边界**：本卡只证明**一种形态**（win-path）经附件旁路。`Invoke-Scrubber` 的调用点只有一处（只吃 `$promptFull`），
> 故该结论**按机制外推**到其余 8 条规则；但"外推"就是外推，**不等于**逐条实测过。
>
> **本卡已做离线预检（2026-09-21，11/11 PASS，零网络）** —— 逐条确认了"这次 run 会给出二值结论"所需的四个前提：
> ① front-matter 真被解析成 `sensitivity: sanitized`（**这是最容易静默失效的一步** —— 本项目有 `Get-FrontMatter` 预置 18 键的恒真判据前科）；
> ② 植入串**确实进了** `$promptFull`（控制组的前提）；③ `Get-ScrubBlockReason` 返回 `''`（本卡不会被 fail-closed 拒发）；
> ④ 消毒后该串**消失**且出现 `[REDACTED-PATH]`（= LINE1 的期望值），而附件里**原样保留**（= LINE2 的期望值）。
> ⇒ 两侧期望值**必不相同**，故判读不需要跟历史 run 比，也**不会**出现"两侧一样、无法分辨"的退化。
