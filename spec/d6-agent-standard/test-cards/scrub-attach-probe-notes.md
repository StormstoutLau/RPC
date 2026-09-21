# `scrub-attach-probe.md` 的用法与判读（runner 说明，**刻意不在卡内**）

> ⚠ **为什么说明不在卡里**：卡的 `body`（front-matter 之后的一切）会**原样进 prompt**。
> 2026-09-21 首跑（run `202609220005298044`）踩到两处自伤，本文件就是对它们的修法：
> 1. **正文说了"不要调用任何工具"**，却又要求它报告"你在 `.attach/…` 里看到的路径" ⇒ **自相矛盾**，
>    等于禁止 agent 完成实验组。（实测：转录里 `tool_use blocks=0` ⇒ 它一次工具都没调。）
> 2. **runner 说明（含判读表）留在 body 里** ⇒ 它进了 prompt：既多出 2 处被抹的路径副本
>    （解释那 3 次 `SCRUB[win-path]` 命中里的 2 次），又把**期望答案**提前告诉了被测对象 ⇒
>    对自述式探针是**污染**。
> ⇒ 故本卡只留**被测内容**；说明放这里。

## 用途

把 [scrubber 规则扩充裁定 §5-3 / §6-P3](../../../docs/security/2026-09-21_scrubber规则扩充裁定与影响面.md) 里那条
**只有代码路径判定、未经实测**的结论 ——「**附件内容不经 scrubber**（`scp`/`Copy-Item` 原文，主路 L1227/L1230、
claude 路 L2290）」—— 升到**实测**。

**为什么值得测**：DESIGN §9 不变式②（"消毒在控制台完成，出网字节里没有敏感形态"）语义上覆盖"到达 agent 的一切输入"，
而 `Invoke-Scrubber` 实际只作用于 `$promptFull`。若卡同时满足「附件含敏感内容」+「模型指向云端」，
则**附件内容会原样进云端上下文**（agent 按 prompt 提示"按需读取"它）⇒ 该不变式在附件上是**空的**。

## 设计：一次 run 内含对照组

同**一个** Windows 路径植两处，只差经过谁：

| | 位置 | 经过什么 | 期望 |
|---|---|---|---|
| **LINE1** | 卡 `body`（本任务描述） | **必经 scrubber**（只作用于 `$promptFull`） | `[REDACTED-PATH]` |
| **LINE2** | 附件 `.attach/scrub-probe.txt` | **不经** scrubber（复制原文） | `D:\Paper\agent-out\secret.xlsx` |

⇒ **自对照**：两侧同串、只差路径，结论不需要跟历史 run 比。

**LINE1 是控制组，也是"这次 run 有效"的前提**：若 LINE1 是**原路径**，说明消毒闸没跑到
（另一类问题）⇒ **整张卡作废**，不能拿 LINE2 得结论。

**为什么用 Windows 路径做样串**（而不是 `sk-`/`AKIA`/私钥块）：它**同时**满足两个约束 ——
① 被 `win-path` 规则覆盖（正文侧必被抹 ⇒ 控制组成立）；② **不触发**本地 `secrets` 门禁（其正则只有 `sk-`）
也**不触发**远端 GitHub push-protection（无该形态的 detector）⇒ 可**入库**、可复跑。
⚠ 凭据类样串做不到：卡片没法运行时拼接（见 `_scrubber_coverage_test.ps1` 顶部注释）。

## 跑法

```powershell
powershell -ExecutionPolicy Bypass -File ops\station-bin\agent-cli.ps1 task paper `
  -Card spec\d6-agent-standard\test-cards\scrub-attach-probe.md `
  -Attach ops\station-bin\attach-test\scrub-probe.txt
```

- **零站上引擎、零站上模型**：claude 备路在 station-ready/sync **之前**分支 ⇒ 主控本地 spawn ⇒ OpenRouter 云端。
- 成本：**1 次免费档请求**（`claude` = `thinkingmachines/inkling:free`）；不需要 `cluster.py load`。
- ⚠ **必须从 `d:\RPC` 之外的目录跑？不 —— 2026-09-21 起不必**：`Invoke-ClaudeFly` 现已**显式** `-cwd $projRoot`
  （此前不设 ⇒ 子进程继承控制台 cwd ⇒ 附件按相对路径**不可达**，实测 run `202609220005298044`）。
  回归守卫在 `_fm_golden_test.ps1` 的 `cwd:` 三条断言（结构断言；行为证据只有实弹能给）。
- 附件从哪来：`ops/station-bin/attach-test/scrub-probe.txt`（1 行，内容 = 那个路径）。

## 判读（看 run 归档的 `agent-output.txt`）

| LINE1（控制组） | LINE2（实验组） | 结论 |
|---|---|---|
| `[REDACTED-PATH]` | `D:\Paper\agent-out\secret.xlsx`（原文） | ✅ **P3 假设成立**：消毒只作用于 prompt，**附件内容原样进云端** ⇒ 不变式②在附件上是空的 |
| `[REDACTED-PATH]` | `[REDACTED-PATH]` | ⛔ **P3 假设被推翻**：附件**也**被消毒了（说明我看漏了一处调用点）⇒ 改裁定 §5-3 |
| 原路径（未被抹） | 任意 | ⚠ **本卡作废**（控制组失败）：`sanitized` 闸没跑到，或 `$sens` 没解析成 `sanitized` ⇒ 先查 front-matter 与 `SANITIZED gate:` 行 |
| `NONE` / 格式不符 | 任意 | ⚠ 先查 **agent 有没有真读** —— 看 claude 自己的转录 `~/.claude/projects/D--Paper/<session>.jsonl` 的 `tool_use` 计数与 `cwd`（**别**信 `run.json` 的 `usage.tool_uses`：claude 路是 `not-collected` 的**默认占位**，不是测量值） |

## 顺带可判的两条（同一 run 的产物，不必额外跑）

- 控制台应出现 `SANITIZED gate: scrubbing prompt (P1a)` + `SCRUB[win-path] hit: …` ⇒ 消毒闸**在 claude 路也生效**
  （这也是 §5-1 新增的 block 判据所在的分支）。
- `run.json` 的 `attach` 应为**对象数组**（含 `name`/`src`/`kind`/`sha256`）而不是名字数组 ⇒ 附件身份在这条路上也有摘要。

## 实测结果（2026-09-21）

**结论：P3 假设成立 —— 附件内容不经 scrubber，原样到达远端 agent 上下文**（两条路一致）。

| run | 路 | 执行器 / 模型（去向） | LINE1（控制组） | LINE2（实验组） | 备注 |
|---|---|---|---|---|---|
| `202609220005298044` | claude | 主控本地 / `inkling:free`（**云**） | `[REDACTED-PATH]` | **`NONE`** | ❌ **首跑作废** —— 卡自伤（正文禁止用工具）+ cwd 缺陷（附件不可达）；本文件开头两条就是这次修掉的 |
| **`202609220011097576`** | claude | 主控本地 / `inkling:free`（**云**） | `[REDACTED-PATH]` | **`D:\Paper\agent-out\secret.xlsx`** | ✅ **主证据**。转录 `~/.claude/projects/D--Paper/bc584929-….jsonl`：`cwd="D:\Paper"`、`tool_use blocks=2`、`Read`×1 ⇒ **真读了**，不是猜的 |
| `202609220018387887` | 主路 | 站上 opencode / zen（**云**） | `[REDACTED-PATH]` | —（零输出） | ⏱ **3×120s 超时、只出 banner**（`RUN_S=360`）⇒ 见下方"顺带发现 (C)"，**与 P3 无关** |
| `202609220025427213` | 主路 | 站上 opencode / 站上本地 `gpt-oss-20b` | `[REDACTED-PATH]` | `NONE` | **负向对照**（刻意不加 `-Attach`）：agent 真的去读了并报 `File not found: /home/scott-lau/agent-workspaces/paper/.attach/scrub-probe.txt` ⇒ ① `NONE` 的含义是"确实没有"；② 探针**不会恒答 yes**；③ **主路 cwd 就是站上工作区**（相对路径解析正确 ⇒ 反衬 claude 路那处 cwd 缺陷是**该路独有**） |
| **`202609220027063046`** | 主路 | 站上 opencode / 站上本地 `gpt-oss-20b` | `[REDACTED-PATH]` | **`D:\Paper\agent-out\secret.xlsx`** | ✅ 主路正向。输出里直接可见 `Read .attach/scrub-probe.txt` |

⇒ **两路结论一致**。⚠ 但要看清**两路各自证明了什么**：**云端后果**由 claude 路证明（`inkling:free` 是第三方云，且转录显示原文进了模型上下文）；
主路那两跑用的是**站上本地模型**，故只证明"**附件以原文落到远端工作区且 agent 读得到**"（对端是自己机器）——
主路打**真云**未做成（见顺带发现 (C)）。

**每跑都成立的两条副产物**：控制台 `SCRUB total hits: 1`（只抹正文那一处 —— 说明 notes 移出 body 后污染已消除）+ `run.json` 的 `attach` 是**对象数组**（含 `name`/`src`/`kind`/`sha256`）。

### 顺带发现（都不是 P3，但都是实跑才暴露的）

**(A) claude 路 `Invoke-ClaudeFly` 不设 `WorkingDirectory` ⇒ 附件按相对路径不可达** —— ✅ **本轮已修**
（加显式 `-cwd $projRoot`；回归守卫 = `_fm_golden_test.ps1` 的 `cwd:` 三条断言，且做过变异自证）。
修前证据：转录目录是 `D--RPC`（cwd = 控制台 cwd）；修后变 `D--Paper` 且附件可读。

**(A′) claude 路的站上变体更重**：站上脚本 `cd "$HOME"`（同样错位），且 **附件只复制到主控本地 `<projRoot>\.attach`、根本没同步到站上**
⇒ `local-only` + 站上 claude + 附件时**附件完全缺失**。⏳ **未动，已登记待办**。

**(B) claude 路 spawn 不传任何工具/权限参数**（只有 `-p "" --model <id>`）⇒ headless 下工具是否可用**未验证**。
现有证据：首跑 `tool_use blocks=0`（但那次的卡**禁止**用工具 ⇒ 无法归因）。⚠ 下次若要单测这条，得**去掉卡里的工具禁令**再跑一次。

**(C) 站上 zen 路由空转：没有 `auth.json` ⇒ 不快速失败、只烧预算** —— 实测 `opencode/…-free` 在 B 站
**3×120s 零输出**（`TASK_RC=124`→rc=6）；排除了网络（站上 `curl` 对 `openrouter.ai` / `models.dev` / `opencode.ai` **全 200**）、
也排除了引擎（`CHAT_OK`/`READY_OK` 都过）；日志里只有一条 `Failed to fetch models.dev … TimeoutError`。
⚠ 连带核对：`ROUTE_TABLE` 里**站上云型号全是 zen**（`opencode/…-free`），**没有 `openrouter/…` 的站上条目**
⇒ 若要让主路真打到 OpenRouter，得**先加路由条目**（`Resolve-Model` 是纯表查找、不 passthrough）。
⇒ 这两条（zen 未登录 + 表缺站上 openrouter 条目）**已登记**。

## 诚实边界

- 本卡只证明**一种形态**（win-path）经附件旁路。`Invoke-Scrubber` 的调用点只有一处（只吃 `$promptFull`），
  故该结论**按机制外推**到其余 8 条规则；但"外推"就是外推，**不等于**逐条实测过。
- **站上变体（`local-only` + 站上 claude）不适用本卡**：那是另一套机制（站上脚本 `cd "$HOME"`），且
  claude 路的附件**只复制到主控本地 `<projRoot>\.attach`，根本没同步到站上** ⇒ 同类但更重，已登记待办。
- `model: claude` 走的是 OpenRouter **免费档**（可能被训练）—— 这正是 P3 要量化的敞口，不是意外。
