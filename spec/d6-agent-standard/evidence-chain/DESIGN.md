# agent 证据链 —— 实现级可行性落档（DESIGN）

> **日期**: 2026-09-17
> **上游**: [任务卡证据流_协同篡改威胁_补充调研.md](../../../docs/research/2026-09-17_任务卡证据流_协同篡改威胁_补充调研.md) §6.1
> **前置**: [任务卡证据流可重放性调研](../../../docs/research/2026-09-16_任务卡证据流可重放性调研.md) 阶段 0 已闭环（ADR-0005）
> **定位**: 实现级落档（数据结构 + 受影响文件 + 判定/测试 + 边界）。**已落地**（2026-09-17）—— 实现全部落在统一管理入口 [cluster.py](../../../ops/cluster.py) 的 `agent` 子命令下（符合 [ADR-0004](../../../adr/ADR-0004-统一管理入口为唯一管理面.md) 的"唯一管理面"要求）；`agent-cli.ps1` 与站上行为**零改动**。

---

## 0. 一句话交付

新增一个**主控独占、只读回放**的证据链：主控给每次 run 的回收字节算 `run_digest`，写入 `agent-chain.json`，并把链头镜像到冷路径。执行站任意后续篡改 ⇒ 断链在首个 diff 处可定位。**这不"防篡改"，只"把改的痕迹从 0 提到趋向 1"。**

---

## 1. 现网事实基线（改名把 b b0，避免臆测）

| 事实（实证于 agent-cli.ps1 / cluster.py） | 出处 |
|---|---|
| Console 侧构造 `.prompt.txt` 并比对回收字节 `prompt_sha256`（台账） | [agent-cli.ps1 L1048](../../../ops/station-bin/agent-cli.ps1#L1048) |
| Console 侧算判据源哈希 `goldenSha`，**嵌入 fused 脚本 literal，不写入 worksite**（inv 5 "无 .golden.sha256 manifest"） | [agent-cli.ps1 L933](../../../ops/station-bin/agent-cli.ps1#L933) |
| 远端 fused 脚本自行写 `.meta`（TASK_RC/ACCEPT_OK/ACCEPT_GOLDEN_OK/REVIEW_NEEDED）⇒ **builder 自述** | [agent-cli.ps1 L1107](../../../ops/station-bin/agent-cli.ps1#L1107) |
| 远端写 `.agent-output.txt` / `.accept-golden-output.txt` / `.golden-cmd.txt` | [agent-cli.ps1 L1048/L965/L964](../../../ops/station-bin/agent-cli.ps1#L1029) |
| 主控写 `<agent-out>/<ts>/.agent-run.json` 终态快照（status/exit_code/cli/model/run_s/output_bytes/slot/profile/accept/collect/usage） | [cluster.py 调 `_agent_detail`；写了 `.agent-run.json`](../../../ops/cluster.py#L3056) |
| 主控独立信任域（与执行站 A/B/C 异机）→ 证据链接外置 head 的物理前提成立 | 调研 §1/§6.1 |

---

## 2. 数据结构

### 2.1 `run_digest`（主控重算，不落远端）
就地可重算 ⇒ 必须由**回收回来的字节**决定。设计：

```text
run_digest = sha256(
  sha256(.agent-output.txt 字节)  ‖
  sha256(.accept-golden-output.txt 字节) ‖
  sha256(.meta 字节)             ‖
  sha256(.prompt.txt 字节)       ‖
  golden_sha        # ← 见 2.2 键实现点
)
```

- 分簇哈希 + 拼接再整体哈希：任一簇被改 ⇒ 整体变，且 diff 定位到簇。
- **不用"整文件字节流 + 顺序分隔符"**：回收的 5 个字节面暴露为原样，难逃主控重算；分簇使负向测试可精确到"哪个文件"。

### 2.2 `golden_sha` 重算问题 —— 已被 ADR-0005 关闭（原"关键坑"作废）

初稿判定：`goldenSha` 只活在 fused 脚本内存（[L933](../../../ops/station-bin/agent-cli.ps1#L933)），回收字节里没有它 ⇒ 主控异地重算会缺输入。

**实现期取证纠正**：ADR-0005（2026-09-16）已把它落进 `.agent-run.json` 的 `accept_golden.sha256`（[L1263](../../../ops/station-bin/agent-cli.ps1#L1263)）。因此**无需新增落盘字段**，也**不另抽 `golden_sha` 入 recipe**：只要把 `.agent-run.json` 的**字节**纳入 digest，即同时覆盖「当次注入的是哪份 golden」与「status/accept 判词是否被翻」。

> 教训归档：初稿把"内存变量→落盘"当成本次必做项，实际同行已做过。**开工前先 grep 目标字段是否已存在**，比在文档里推演更省事（与"判据先行"同一条纪律）。

### 2.3 已实现的数据结构（以代码为准）

```text
recipe v1:  run_digest = sha256( "v1\n" + 逐件 "name:hex|-\n" )      # 分簇: 逐件先算 sha256, 再整体哈希
入链件 (AGENT_EVIDENCE_FILES, 6 件):
  .agent-run.json · judgment-record.txt · agent-output.txt ·
  accept-output.txt · accept-golden-output.txt · prompt.txt
缺件记 `-`（老 run 无详情 / collect 部分失败属正常, **不等于篡改** ⇒ 不得拿"缺件"当告警）
```

```json
{
  "version": 1, "recipe": "v1",
  "entries": [ { "proj": "...", "run_id": "<ts>", "digest": "...", "prev": "<上条 digest|->",
                 "files": {"<name>": "<hex|->"}, "recipe": "v1", "chained_at": "..." } ],
  "head":    { "proj": "...", "run_id": "...", "digest": "..." }
}
```

- **append-only**：旧条目永不改写；`prev` 链接**入链次序**（日志序），**不是 ts 序** —— 扫描补录时按 ts 排候选，但插入次序即链接次序，故 ts 交错的并发派发不会破坏链。
- **改 recipe 必须 bump `AGENT_DIGEST_RECIPE`**，否则历史条目全部误判断链（已写入代码注释 + 复验期 `recipe_mismatch` 判据）。

---

## 3. 外部锚（三级：锚 → 链 → 证据）

| 级 | 文件 | 钉什么 | 能否重算 |
|---|---|---|---|
| ① 锚 | `archive/evidence-chain/ANCHOR.txt`（**入库**） | 链文件**字节**（`chain_sha256`）+ 冷路径字节 + head + 条数 + recipe | ❌ **不可重算**（它记录的是历史状态） |
| ② 链 | `ops/station-bin/agent-chain.json`（不入库）；冷路径镜像 `archive/evidence-chain/agent-chain.json`（不入库） | 每 run 的归档证据 digest（含 prev 链） | ✅ 可由归档重算（digest 确定性已实测） |
| ③ 证据 | 各 `agent-out/<ts>/` 回收件 | 原始字节 | — |

- **判定**：`anchor_mismatch`（锚与链不符 → 链被整体重写）/ `cold_mismatch`（冷路径与链不符）/ `digest_mismatch`（归档件被改，**定位到条与件**）/ `chain_break`（prev 不闭合）。
- **`chain` 不静默重锚**：锚与链不符时 `agent chain` **刻意不动锚**（否则攻击者重写链后跑一次 chain 就把痕迹抹平）；确要重锚须显式 `--reanchor`。已实测。
- **为什么只把锚入库**：链体积随 run 数线性增长且**可重算**（入库是噪声）；锚不可重算，且一页纯文本、人类可读，**可 git 提交并 push 到 origin** ⇒ 由 **GitHub remote** 充当第 3 个信任域的见证。
- ⚠ **强度诚实（关键，不许含糊）**：
  1. 该锚**只在 `git push` 到 origin 后才成立**；只提交不推送 = 仍在本地单点。
  2. 持推送凭据者可改写后强推 ⇒ 严格说这是"**多副本见证**"强度，**不是密码学不可否认**。
  3. 本机冷路径仍与链同盘 ⇒ 它防的是"顺手改一处"，防不了"知道要改三处的人"。
  4. 真 T2 级需额外手段（外部介质 / RFC3161 时间戳 / 独立见证者）。**本次未做，且明确不宣称已具备。**

---

## 4. 受影响文件（实际改动，2026-09-17 已落地）

| 文件 | 改动 | 状态 |
|---|---|---|
| `ops/cluster.py` | 新增 `AGENT_CHAIN` / `AGENT_CHAIN_COLD` / `AGENT_DIGEST_RECIPE` / `AGENT_EVIDENCE_FILES` 常量 + `_sha256_file` / `_run_digest` / `_chain_load` / `_chain_runs` / `agent_chain_append` / `agent_chain_verify`；`cmd_agent` 增 `chain`、`verify` 两个动作 | ✅ 已实现 |
| `ops/station-bin/agent-chain.json` | 链本体（主控独占，**唯一新增写动作**）；`archive/evidence-chain/agent-chain.json` 为其冷路径镜像 | ✅ 已生成（67 条）|
| `ops/station-bin/agent-cli.ps1` | **零改动**。原计划"补 golden_sha 落盘"经取证已由 ADR-0005 完成（§2.2）；且 collect 段已保证各证据件 Move 落地，无需动 fused 逻辑 | ✅ 不动（降风险；亦避开该 .ps1 的 BOM 陷阱）|
| `ops/station-bin/agent-cli-smoke.sh` | 未改 —— 负向测试用一次性手工篡改完成（见 §5），不值得固化成常跑脚本 | ⬜ 有意不做 |
| `archive/evidence-chain/ANCHOR.txt` | **外部锚**（一页纯文本，**入库**）；`agent chain` 生成，`verify` 判 `anchor_mismatch` | ✅ 已实现（遗留#3）|
| `ops/rpc_check.py` | 新增第 15 项断言 `evidence`（`quick=True`，**只读**）：issues ⇒ **FAIL**，未入链/缺锚 ⇒ **WARN** | ✅ 已实现（遗留#1）|
| `ops/rpc.ps1` | `Install-HookEntry` 生成的钩子在调门禁**前**加一行 best-effort `agent chain`（`\|\| true`，不阻断提交）⇒ pre-commit **与** pre-push 均自动入链 | ✅ 已实现（遗留#2）|
| `.gitignore` | 链 JSON 两处排除（体积大且可重算）；**ANCHOR.txt 刻意不排除**（唯一不可重算的锚） | ✅ 已实现（遗留#3）|

---

## 5. 判定 / 测试（实测结果，2026-09-17）

| # | 判定 | 通过标准 | 实测 |
|---|---|---|---|
| 1 | 白盒重算 | 对同一 run：`agent verify` 重算 digest == 链内记录，稳定 | ✅ 且**更强**：删除链后由原始字节重建，head digest 精确复现原值 `83486e3b767c15ad` ⇒ digest 确定性 + 备份字节恢复无误 |
| 2 | 回放链 | 逐条 `prev` 与前一条 `digest` 全匹配 | ✅ 67 条全绿 |
| 3 | 冷路径对称 | 冷路径与当前链条目逐条 digest 一致 | ✅ 一致；T2 中人为制造不一致即报 `cold_mismatch` |
| 4 | 负向 T1 | 手工改归档证据任一字节 → 报 digest_mismatch 并定位到文件 | ✅ 对 head run 的 `agent-output.txt` 追加 1 字节（46→47）⇒ `✗ [66] digest_mismatch 变了: agent-output.txt`，**精确到条与件** |
| 5 | 负向 T2（非协同） | 改链本体任一字段 → 报 chain_break + cold_mismatch | ✅ 改第 1 条 digest 前 8 位 ⇒ 三项齐报（`[0] digest_mismatch` + `[1] chain_break` + `cold_mismatch`） |
| 6 | 回归 | `ops\rpc.ps1 check` 无新增 FAIL | ✅ 全量 **绿灯 15 / 黄灯 1 / 红灯 0**（唯一黄灯是已登记的 A 站插件漂移，与本改动无关） |

**遗留三项补齐后的追加实测（同日）**：

| # | 项 | 判据 | 实测 |
|---|---|---|---|
| 7 | 外部锚一致 | 锚与链不符 ⇒ `anchor_mismatch` | ✅ 改链第 1 条 digest ⇒ **4 类齐报**（`digest_mismatch`+`chain_break`+`cold_mismatch`+`anchor_mismatch`） |
| 8 | **`chain` 不静默重锚**（关键负向） | 篡改后跑 `chain`（无 `--reanchor`）⇒ 锚**必须不动** | ✅ 锚哈希前后相同；`verify` 仍 FAIL（篡改信号保住）。若此处"自动修复"= 攻击者跑一次 chain 即抹平痕迹 ⇒ 设计缺陷 |
| 9 | 门禁 FAIL 路径自证 | 篡改归档件 ⇒ 门禁 `evidence` **必须 FAIL 且 rc=1** | ✅ `[FAIL] ✕ evidence` + 明细 `[66] paper/… digest 不符, 变了: agent-output.txt`，红灯 1；恢复后回 PASS |
| 10 | **钩子自动入链端到端** | 造一个未入链 run ⇒ 跑钩子 ⇒ 应被自动入链 | ✅ 钩子前 `verify` 报 `▲ 覆盖缺口: 1 个 run 尚未入链 · paper/209901…`；钩子后 **67→68、未入链 0、锚 entries=68**、门禁 PASS |
| 11 | 清理后重建自证 | 删假 run + 删链 ⇒ 重建须复现 | ✅ 回到 **67 条**，head digest 复现 `83486e3b767c15ad`，假 run 零残留 |
| 12 | `rpc.ps1` 编辑安全 | BOM 必须保住 + AST 0 错误 | ✅ `EF BB BF` 保住（改前已备份）；PowerShell AST 解析 **0 错误**（该 .ps1 曾有"剥 BOM → PS5 崩"前科） |

**附：诚实边界的实证（非通过项，是"上限"的证明）** —— 完整协同篡改（改证据 + 重算 digest + 同步改链 **与** 冷路径）⇒ `verify` **PASS**。这**不是缺陷**，而是 §3/§6 已声明的物理上限；本次把它**实测出来**而非写在纸上。

> 自证纪律：`agent verify` 的通过条件是"重算 digest 逐条等于链内记录"，**不存在"跑了但没比"的假通过**（T1/T2 均先证明它能 FAIL，再证明恢复后能 PASS —— 判据双向自证）。

---

## 6. 诚实边界（白纸黑字）

1. **不防 T3**（执行站 + 主控密钥/库全泄露）：真 T3 一切审计设施失效（调研 §7.2）。
2. **不防"提前不记录"**：跳过埋点的空窗，链条无从察觉（需 §6.2 观测方旁证，本文不含）。
3. **不证"判据真的在站上跑过且结果为 0"**：只为"回收字节一致 + 未被主控侧之外后续改"；judgement 级不可独立证真（调研 §5 红线）。
4. **不引第三方公证/区块链**：冷路径镜像已足够匹配 T3 未稳场景。

---

## 7. 结论与用法

**已落地**（2026-09-17，代码在 [cluster.py](../../../ops/cluster.py)）：

```bash
python ops/cluster.py agent chain            # 补录未入链的 run (幂等; 写链+冷路径+外部锚)
python ops/cluster.py agent chain --reanchor # 显式重锚 (仅在确认锚过期时用; 会抹掉"锚≠链"信号)
python ops/cluster.py agent verify           # 复验: digest + prev 链 + 冷路径 + 外部锚; 有 gap 则 rc=1
python ops/cluster.py agent verify --json    # 同上, 机器可读 (供门禁/CI 接)
ops\rpc.ps1 check                            # 门禁第 15 项 evidence 自动覆盖以上 (只读)
```

- **自动入链**：git `pre-commit` / `pre-push` 钩子（由 `ops\rpc.ps1 install-hooks` 生成）在门禁前跑
  `agent chain`（best-effort，不阻断提交）。**钩子是生成物，不要手改** —— 改 `Install-HookEntry` 后重跑
  `install-hooks`。
- **外部锚激活**：`agent chain` 生成/更新 `archive/evidence-chain/ANCHOR.txt` → **提交并 `git push` 到
  origin** 才算建立跨信任域见证（只提交不推送 ≈ 仍在本地，见 §3）。

- **收益**：归档证据事后被改动 ⇒ `verify` 报 `digest_mismatch` 并**定位到条与件**；链本体被改 ⇒ `chain_break`；冷路径不同步 ⇒ `cold_mismatch`。三项均在 §5 实测过。
- **不变更任何站上行为**：`chain`/`verify` 是纯主控侧本地文件操作，`agent-cli.ps1` **零改动**（避开 BOM 陷阱与派发路径风险）。
- **不加常驻服务、不引入依赖**：链是普通 JSON，读/写/验都是纯标准库。
- **明确不宣称**：不防"证据 + 链 + 冷路径"的完全协同篡改（§5 已实测其可 PASS），不防 T3，不证 judgement 级真伪（§6）。

**遗留三项 —— 已全部解决（2026-09-17 同日）**：

| 原遗留 | 解法 | 状态 |
|---|---|---|
| ① `agent verify` 未接门禁 | `rpc_check.py` 第 15 项断言 `evidence`（`quick=True`，**只读**，进 pre-commit 与 pre-push）。**严重度分开**：issues ⇒ FAIL；未入链/缺锚 ⇒ WARN | ✅ |
| ② `chain` 无自动触发点 | `rpc.ps1 Install-HookEntry` 生成的钩子在门禁**前**加 best-effort `agent chain`（`\|\| true` 不阻断）。钩子是**生成物**"请勿手改" ⇒ 必须改生成器（已改 + 重新 install-hooks + 端到端实测） | ✅ |
| ③ 冷路径非跨信任域锚 | 新增**外部锚** `ANCHOR.txt`（钉链文件字节，**入库**）+ `anchor_mismatch` 判据 + git push 到 origin 作见证。**强度诚实见 §3** | ✅（强于"同盘冷路径"，**不等于**密码学不可否认）|

**仍明确不做的**（边界，非遗漏）：
1. **派发后即时入链**（把窗口压到最小）需改 `agent-cli.ps1` 的派发关键路径 —— 该路径**无法在无活模型/活站时端到端验证**，且 DESIGN 初判"收益/风险比不划算"。现由"钩子入链 + 门禁报覆盖缺口"兜住：**窗口存在但可见**。
2. **真 T2 级锚**（外部介质 / RFC3161 / 独立见证者）—— 需第三方或人工介质，本次明确不做且不宣称。
3. `agent-cli.ps1` 的 BOM 与派发路径**零改动**（保持该文件为"只读资产"）。

## 8. 关联

- 上游：《任务卡证据流可重放性调研》阶段 0（ADR-0005）+ 《协同篡改威胁补充调研》§6.1
- [strong-accept/DESIGN.md](../strong-accept/DESIGN.md)（golden 既有实现，digest 复用其 sha256 语义）
- 实现文件：[agent-cli.ps1](../../../ops/station-bin/agent-cli.ps1)、[cluster.py](../../../ops/cluster.py)