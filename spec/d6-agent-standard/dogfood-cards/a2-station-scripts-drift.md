---
proj: dogfood
task: 读工作区 .attach/scripts-inventory.tsv（主控预置的站上 ~/scripts 快照清单），验证其良构并按四列规范复写为 out/station-scripts.tsv；只写这一个新文件，不读草稿之外任何站外目录
model: ultra
cli: opencode
sensitivity: public
attach-egress: ok
readonly: false
timeout_s: 600
accept:
  - test -f out/station-scripts.tsv
  - test "$(wc -l < out/station-scripts.tsv)" -ge 3
  - grep -q 'sha256' out/station-scripts.tsv
evidence-manifest:
  version: 1
  subjects:
    - name: station-scripts
      path: station-scripts.tsv
      state: out/station-scripts.tsv
      digest: sha256
---
## 任务描述

你是**只做整理**的取证 agent。**不要分析、不要比对、不要判断"哪个是新的"**——比对与 **freshness 判定由主控完成**，你只负责把主控预置的清单正确整理成良构 TSV。

> ⚠ **O-42/ADR-0007 落定（2026-09-24）：你【不】读站外目录（如 `~/scripts`）** —— 那超出你工作区的授权边界，opencode 权限模型会 auto-reject `external_directory`。快照已由主控预置到 `.attach/scripts-inventory.tsv`。

### 第一步：确认入参存在

```bash
test -f .attach/scripts-inventory.tsv && echo INVENTORY_PRESENT
```

若失败 ⇒ stdout 打印 `DOGFOOD_A2_BLOCKED` 并停止。

### 唯一产物：`out/station-scripts.tsv`（相对工作目录根）

- **第 1 行固定为表头**：`sha256<TAB>mtime_epoch<TAB>size<TAB>relpath`
- 其后**每行一项**，四字段用 **TAB** 分隔（不是空格）
- **数据来自 `.attach/scripts-inventory.tsv`**：其行本就是方块格式（或前三列 + 相对路径），你要**逐行转为上述四列规范**，去掉任何非表行（注释/空行）
- **不修改、不创建其它文件**

### 格式提示（等价命令，可自行等价实现）

```bash
{ printf 'sha256\tmtime_epoch\tsize\trelpath\n'; \
  awk -F'\t' 'NR>1 && NF>=4 && $1 ~ /^[0-9a-f]{64}$/ { print $1"\t"$2"\t"$3"\t"$4 }' \
    .attach/scripts-inventory.tsv; } > out/station-scripts.tsv
```

（若你的实现与上例不同，只要产物格式一致即可；**不要**为了跑通上例而修改任何既有文件。）

### 硬性要求

1. **不许编造**：只转录 `.attach/scripts-inventory.tsv` 中已有的行；查不到该文件 ⇒ `DOGFOOD_A2_BLOCKED`。
2. **不要读 `~/scripts` 或任何站外目录**；`external_directory` 越权在本卡为雷区。
3. **不读取任何站上源文件内容**（只整理清单，不算哈希）。
4. **stdout 只输出一行**：`DOGFOOD_A2_OK`
5. 除 `out/station-scripts.tsv` 与探针 `out/.write-test` 外**不产生任何文件**。

---

> **用途（拆两层，2026-09-24 · O-42 落定）**：站上 agent 沙箱只能访问工作区 `$W`；`~/scripts`（站外）autoreject by opencode `external_directory`（实测 A2 v1 崩溃于此）。
> **拆两层**：
> ① **agent 层（本卡）**：只验证「授权边界内的取证链路」——把主控预置到 `.attach/` 的站上脚本快照清单正确整理成良构 `out/station-scripts.tsv`。不越权。
> ② **主控层（freshness 判据，D6-P1-1 实弹）**：主控 ssh 站上 `~/scripts` **实时** `sha256sum`，与预置快照（即"预置时基线"）比对 → 判定新增/漂移。**不经 agent**、无权限问题。
>
> **跑法（同一命令做两件事，先主控预置、再派发）**：
> ```powershell
> # ① 主控取站上 ~/scripts 实时清单 → 本地 inventory.tsv（同时即"基线快照"）
> ssh <user>@<host> "cd ~/scripts 2>/dev/null && sha256sum * 2>/dev/null" | % { $p,$h=$_.Split(" "); "$h`t<raw_mtime>`t<raw_size>`t$p" } > tmp\scripts-inventory.tsv
> # ② 派发 A2 v2（-Attach 传快照）
> & .\ops\station-bin\agent-cli.ps1 task dogfood -Card spec\d6-agent-standard\dogfood-cards\a2-station-scripts-drift.md `
>     -Attach @('tmp\scripts-inventory.tsv')
> # ③ 主控 freshness 比对（实时 vs 预置快照）— 主控层判据
> ssh <user>@<host> "cd ~/scripts 2>/dev/null && sha256sum * 2>/dev/null" > tmp\scripts-live.tsv
> ...（主控 diff 两份，报新增/漂移）
> ```
> `state: out/station-scripts.tsv` ⇒ 该 run 的产物由 collect 段白名单拉回 runDir（O-40/A-1，与 A1 同机制）。