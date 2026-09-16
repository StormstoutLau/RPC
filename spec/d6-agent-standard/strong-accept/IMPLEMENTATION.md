# 实施文档：strong-accept（主控站侧 golden 测试，防模型自证）

---
id: d6-strong-accept-IMPLEMENTATION
type: implementation
version: 1.4
status: implemented
date: 2026-09-09
depends: [d6-strong-accept-DESIGN v1.2, d6-strong-accept-RESEARCH v1.0, d6-agent-standard-DESIGN v1.4, d6-agent-standard-IMPLEMENTATION v1.0]
upstream: null
---

> **Feature**: strong-accept（O-12——主控站侧独立 golden 测试，消除"模型自写测试自证通过"）
> **创建日期**: 2026-09-09
> **状态**: **implemented v1.4（V0 验证门通过 + A15c 全闭环，2026-09-09）**——M1-M4 全链落地 agent-cli.ps1；V0 dogfood 全链 exit 0（ACCEPT_GOLDEN_OK=1 / accept_golden.passed=true / NOT_OBSERVED）；TAMPERED 安全侧失败实证；golden FAIL（exit 9 双义契约消歧）与 source 缺失（exit 2 abort）两负例跑通；离线单测 9/9 绿。V0 完整复盘 = §11。详情 see CHECKLIST §2.8（A15b/c/d 全 ☑）/ OPEN-ISSUES O-12
> **Spec 步骤**: Step 5-6
> **基于设计**: [DESIGN.md](./DESIGN.md) v1.2（Step 4 修复批完成：P1+P2 清零）
> **基于调研**: [RESEARCH.md](./RESEARCH.md) v1.0
> **v1.1 修订记录**（2026-09-09 主控会话，与 agent-cli.ps1 实码核对后）：M3 bash 段修正 `ACCENT_GOLDEN_OK`→`ACCEPT_GOLDEN_OK` 统一；非法管道 `cmd="..." | base64 -d`→`echo ... | base64 -d`；basename 改为主控站预计算 `$goldenBase` 字面量（弃 `$(basename $source)` 防 PS heredoc 求值）；补 `GOLDEN_ACTIVE` 默认行/激活与 L757 退出守卫扩展、L755 .meta printf 扩展；M1 补嵌套分支**插在顶层键分支之前**的 if/elseif 顺序说明；M2 补 `$goldenBase` 计算与注入链 a/b/c 三步
> **v1.2 修订记录**（2026-09-09 主控会话，执行 §9.4 复审 P1+P2 修复批）：P1-1 REPO_ROOT 改为新增 Script 变量 + 两层上公式（一层上 = `d:\RPC\ops` 错误已实证）；P2-1 stale 分支双清零（`$accept_ok`/`$accept_golden_ok` 置 null，fail-safe 语义声明 + §5.1/§8.2 行为变化记录）；P2-2 collect 补 `.accept-golden-output.txt` scp 拉取 + runDir Move；P2-3 status 显式判定 `$acceptGoldenPassed`；P3 顺带：P3-4 锚点 off-by-one 批量校正、P3-5 输出文件名统一带点、P3-6 `$g`/`$accept_golden_ok` 初始化补全
> **v1.3 实施记录（2026-09-09 Step 9）**：①agent-cli.ps1 落码——M1 Get-FrontMatter 嵌套分支前置（L505-510 新 elseif）+ `$Script:REPO_ROOT`（L40-42，两层上公式）；M2 golden 注入块（sync 后、$body 前，L710-762：source abort/checksum/tar+scp 洁净注入/`$goldenBlock` 构造）；M3 $body heredoc 默认行+`$goldenBlock` 插值（L796-802）+ .meta printf 扩 `ACCEPT_GOLDEN_OK`（L826）+ exit 9 守卫双判据（L830-831）；M4 collect 解析/双清零/`$acceptGoldenPassed`/run.json `accept_golden`/输出拉取（L843/848/856/862-866/872-874/910/925-933/940）②V0 素材：`golden/path_guard_golden.py`（10 断言 + 哨兵 `GOLDEN_SENTINEL_7f3a9c21d5e84b62c0f1a9e3d7b5c4a0`）、`test-cards/dogfood-strong-accept.md`（source+cmd 指向 golden）③验收：`_fm_golden_test.ps1` 9/9 绿、ParseInput 0 err、`bash -n` 0、REPO_ROOT=d:\RPC ✓；smoke 4 SKIP（后端未加载，端到端待跑）④**derived-requirement 登记**：`.meta` 恒出 `ACCEPT_GOLDEN_OK`（无 golden 卡也出，默认行保证）——非 DESIGN 明文，已登记 CHECKLIST §2.8/OPEN-ISSUES O-12
> **v1.4 V0 实装记录（2026-09-09，run 183302 gpt-oss exit 0）**：V0 全链通过（详见 CHECKLIST §2.8 A15b）。**V0 实测发现并修复 2 项**：①远端 golden 解压 `tar -xzf`→`-xf`（现役 sync 链 L246/L260 用 plain tar `-cf`/`-xf`，`-xzf` 实测报 "not in gzip format" 致解压失败→`.golden/` 空→checksum 比对失败触发 GOLDEN_TAMPERED；这也**反向实证了不变式 5 安全侧失败**）；②collect 拉 `.accept-golden-output.txt` 包 try/catch（TAMPERED/FAIL 前该文件不产生，EAP=Stop 下 scp NativeCommandError 抛错污染退出）——修复后 `$accGoldTxt = $null` + Test-Path 防护（L849-854/942）。**PS5.1 BOM 教训复习**：Edit 操作曾剥离 agent-cli.ps1 BOM → 运行时按 ANSI 读中文注释致语法崩溃（L48-63 ROUTE_TABLE "Unexpected token"），已补回 BOM（IMPL §2.3 纪律）——**后续编辑 agent-cli.ps1 后必须核对 BOM 头 EF BB BF**

---

## 1. 实施概述

在 D6 agent-cli wrapper（`d:\RPC\ops\station-bin\agent-cli.ps1`，唯一实现文件）内实现 `accept-golden`：任务卡新增 front-matter 字段（单对象 source↔cmd，可选），主控站在任务派发前将 golden 测试注入远端工作区 `.golden/`（保留 source basename，注入前清空），远端在 self-accept 判据**之前**执行 golden 判据（独立计分 `ACCEPT_GOLDEN_OK`），执行前用**嵌入融合脚本字面量**的权威 checksum 做防篡改比对，`.meta` 与 `.agent-run.json` 落契约来源分级。

**关键设计决策（Step 5 落定）**：
- **零新文件**：全部改动收敛在 `agent-cli.ps1` 一处；golden 测试文件由任务卡 `source` 指向 spec 树，非 wrapper 内置
- **MVP 单对象**：一个 `source` 对应一个 `cmd`（DESIGN §10.1 schema 定位）；多 golden 升级为列表随 V2
- **P3 三项处理声明**：P3-1 exit 9 双义复用为有意决策（契约层消歧）；P3-2 已在 DESIGN v1.2 命名统一中解决；P3 .meta 通道扩展在此实现；P3 accept/golden 无 timeout 为已知限制保持与 self-accept 一致（§6.3）

## 2. 工程细节

### 2.1 技术栈

| 组件 | 技术 | 版本 | 验证状态 |
|------|------|------|---------|
| wrapper | PowerShell 脚本 | PS 5.1（Windows 主控站）| ✅ 现役运行 |
| 远端执行 | bash（Ubuntu A/B/C 站）| set -u 严格模式 | ✅ 现役运行 |
| checksum | sha256sum（远端）/ Get-FileHash（主控站）| Ubuntu 自带 / PS 内建 | ✅ 无需新依赖 |
| 传输 | tar + scp（GNU tar 现役调用 $Script:GNU_TAR）| 复用 D6 L1 同步链 | ✅ 现役运行 |
| 测试 | agent-cli-smoke.sh + 离线 PS 单测 | 复用 D6 | ✅ 现役运行 |

**零新增依赖**——全部复用现役工具链。

### 2.2 文件结构

```
d:\RPC\ops\station-bin\
├── agent-cli.ps1                 # 唯一改动文件（M1-M4 全部模块）
└── agent-runs.log                # 台账（现役，本 feature 不改格式）

spec\d6-agent-standard\strong-accept\
├── DESIGN.md     (v1.2)
├── RESEARCH.md   (v1.0)
├── IMPLEMENTATION.md             # 本文档
└── golden\                        # golden 测试源（任务卡 source 指向此处，样例）
    └── path_guard_golden.py       # 首个 golden（随首个 dogfood 卡落地）
```

### 2.3 兼容性

| 项 | 结论 |
|---|---|
| 无 `accept-golden` 的任务卡 | **行为完全不变**——Get-FrontMatter 新增键不影响既有键解析；golden 段为空时跳过全部新逻辑 |
| 远端脚本 ASCII-only | ✅ 严格保持（golden cmd 经 base64 传输，避免引号/中文注入）|
| 主控站 PS5.1 UTF-8 BOM | ✅ 改动保持 BOM（D6 教训）|
| 远端 `sha256sum` | Ubuntu 自带，无冲突 |

## 3. 模块实施

### 3.1 M1: FrontMatter 扩展

#### 职责

解析任务卡新增 `accept-golden` 字段（单对象 source↔cmd，缩进嵌套）。来自 DESIGN §3.2 M1。

#### 实施位置

`agent-cli.ps1` `Get-FrontMatter`（现 L486-522）。

#### 接口签名（构造后哈希表条目）

```powershell
$h['accept-golden'] = @{ source = ''; cmd = '' }   # 顶层键（新）
$curKey = 'accept-golden'                            # 嵌套续行标记（仿 accept 列表 $curKey 模式）
```

#### 实施要点（解析逻辑扩展）

- 哈希表 `$h` 初始化补 `'accept-golden' = @{ source=''; cmd='' }`
- **分支顺序（关键）**：现 parser 为 if/elseif 链（顶层键 L499-505 → accept 列表项 L507-508 → body L510）——缩进的 `  source:` **会先命中顶层键正则** `^\s*([A-Za-z_\-]+)\s*:`（`\s*` 允许前导空白）因不在白名单被静默丢弃。故新嵌套分支必须**插在顶层键分支之前**：
  ```powershell
  if ($inFreq -and $curKey -eq 'accept-golden' -and $l -match '^\s{2,}(source|cmd)\s*:\s*(.+)$') {
      $h['accept-golden'][$matches[1].ToLower()] = $matches[2].Trim()
  }
  elseif ($inFreq -and $l -match '^\s*([A-Za-z_\-]+)\s*:\s*(.*)$') { ... 现有逻辑 ... }
  ```
- 顶层 `accept-golden:` 出现时设置 `$curKey='accept-golden'`（与现 `accept` 列表 L503-504 平行；注意：顶层键分支内 `if ($k -eq 'accept') { $curKey = 'accept' }` 处须补 `elseif ($k -eq 'accept-golden') { $curKey = 'accept-golden' }`）
- 空值语义：`source` 或 `cmd` 任一为空 → 视为"无 golden"（等价于未配置），不进 golden 流程

#### 低效操作排除

| 潜在低效 | 排除措施 |
|---------|---------|
| 正则二次扫描整卡 | 嵌套判断在单次 foreach 内完成，不新增文件读取 |

### 3.2 M2: Golden 注入

#### 职责

主控站校验 source → 算权威 checksum → 清空并注入远端 `.golden/`。来自 DESIGN §3.2 M2 / 不变式 3（洁净）。

#### 实施位置

`agent-cli.ps1` `Invoke-Task`，嫁接在 acceptB64 构造（现 L688-692）之前、融合脚本 $body 构造（L697）之前。

#### 接口签名

```powershell
# 输入：$fm['accept-golden']（非空） 输出：$goldenActive / $goldenSha / $goldenCmdB64 / $goldenBase（前三者供 M3/M4 使用）
$g = $fm['accept-golden']                                        # 赋值点（v1.2 P3-6 补）
$goldenActive = [bool]($g.source -and $g.cmd)                   # 布尔输出（v1.2 补：M4 status 判定/输出拉取引用）
if ($goldenActive) {
  $gSrc      = Resolve-Path (Join-Path $Script:REPO_ROOT $g.source) -ErrorAction Stop   # 缺失 → catch
  # → GOLDEN_SOURCE_MISSING: <path>, exit 2（主控站 abort，不派发）
  $goldenBase  = [IO.Path]::GetFileName($gSrc)               # 命名规则：basename 原样保留（P2-2 上调 P1）
  $goldenSha   = (Get-FileHash -Algorithm SHA256 $gSrc).Hash.ToLower()   # 权威校验和，主控站仅算 1 次（§9.3）
  $goldenCmdB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($g.cmd))
  # M2 注入链（时序：sync 完成后、$body 构造前——不变式 3；复用现 tar+scp 同步模式）
  #   a) $Script:GNU_TAR --force-local -C (Split-Path $gSrc) -cf $env:TEMP/golden-<guid>.tgz $goldenBase
  #   b) scp $env:TEMP/golden-<guid>.tgz → $W/.golden.tgz
  #   c) ssh 远端（清空注入 = P2-3 洁净：.golden 恒等于当次注入内容，残留即不洁净）：
  #      rm -rf "$W/.golden" && mkdir -p "$W/.golden" \
  #        && tar -xzf "$W/.golden.tgz" -C "$W/.golden" && rm "$W/.golden.tgz"
}
```

#### 实施要点

- **`$Script:REPO_ROOT`（v1.2 P1-1 修复：新增变量，非现役引用）**：agent-cli.ps1 现役 Script 变量表（GNU_TAR/REMOTE_USER/WORKSPACE_ROOT/PROJECTS/TMP_ROOT/ROUTE_TABLE/AGENTSYNC_TEMPLATES）中无此键，须在 Script 头部区（L35-39 先例）**新增**：`$Script:REPO_ROOT = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent`——**两层上**（agent-cli.ps1 位于 `d:\RPC\ops\station-bin\`，一层上 `Split-Path $PSScriptRoot -Parent` = `d:\RPC\ops` 是错的，两层上 = `d:\RPC`），source 相对 `d:\RPC` 解析
- 注入时序（不变式 3）：sync 已完成后、$body 构造前，先 scp golden 包 → 远端 `rm -rf .golden && mkdir && tar -xzf`
- 权威 checksum 只算主控站源文件，注入远端后**不再落盘任何清单文件**（P1-1 修订：字面量随 $body 走，不产生 `.golden.sha256`）

### 3.3 M3: Golden 执行

#### 职责

远端在 self-accept **之前**执行 golden 判据，先做防篡改比对再执行，输出 `ACCEPT_GOLDEN_OK`。来自 DESIGN §3.2 M3 / 不变式 5（P1-1）。

#### 实施位置

`agent-cli.ps1` 融合脚本 $body heredoc（现 L697-759），在 accept gate（L729-746）**之前**插入 golden 段。

#### 接口签名（远端 bash 段，插入 $body heredoc）

```bash
# —— 默认行（恒注入 $body）：未配置 accept-golden 时 .meta 仍恒出 ACCEPT_GOLDEN_OK=1（derived-requirement，§9.2 登记）
GOLDEN_ACTIVE=0; ACCEPT_GOLDEN_OK=1

# —— golden 子段（仅当 $g.source -and $g.cmd 时由 PS 拼入 heredoc；插在 accept 区初始化 L731 之后、L732 if 之前）
GOLDEN_ACTIVE=1
GOLDEN_SHA="$goldenSha"            # 字面量（P1-1 锚点：主控站算好，不落盘工作区）
GOLDEN_BASE="$goldenBase"          # 字面量（basename 原样保留——P2-2 上调 P1；勿用 $(basename $source)——PS heredoc 会求值）
GOLDEN_CMD_B64="$goldenCmdB64"     # 字面量（base64：防引号/中文注入——ASCII 纪律）
echo "$GOLDEN_SHA  $W/.golden/$GOLDEN_BASE" | sha256sum -c >/dev/null 2>&1   # 防篡改比对（不变式 5）
TAMPER_RC=$?
if [ $TAMPER_RC -ne 0 ]; then
  echo "GOLDEN_TAMPERED"
  ACCEPT_GOLDEN_OK=0
else
  echo "$GOLDEN_CMD_B64" | base64 -d > "$W/out/.golden-cmd.txt"
  ( cd "$W" && eval "$(cat "$W/out/.golden-cmd.txt")" ) > "$W/out/.accept-golden-output.txt" 2>&1
  GOLDEN_RC=$?
  [ $GOLDEN_RC -ne 0 ] && { echo "GOLDEN_FAIL rc=$GOLDEN_RC"; ACCEPT_GOLDEN_OK=0; }
fi
echo "ACCEPT_GOLDEN_OK=$ACCEPT_GOLDEN_OK"
```

**L757 退出守卫扩展**（golden 与 self 任一激活判据未通过 → exit 9；P3-1 双义复用，契约层 `accept_golden.passed`/`accept.passed` 消歧）：

```bash
if { [ "$GOLDEN_ACTIVE" -eq 1 ] && [ "$ACCEPT_GOLDEN_OK" -ne 1 ]; } \
 || { [ -n "$ACCEPT_B64" ] && [ "$ACCEPT_OK" -ne 1 ]; }; then exit 9; fi
```

**L755 .meta printf 扩展**：format 追加 `ACCEPT_GOLDEN_OK=%s\n`，尾部补上 `"$ACCEPT_GOLDEN_OK"` 实参（与 L753 区 `echo ACCEPT_GOLDEN_OK=` 同步）。

> ⚠️ **PS heredoc 转义纪律（执行时适用）**：golden 子段内远端变量 `$W`/`$GOLDEN_*` 在 `@"..."@` 中必须反引号转义（`` `$W `` 先例 L726/L731）；三个**字面量** `$goldenSha`/`$goldenBase`/`$goldenCmdB64` 是 PS 变量**直接插值、不转义**。

#### 实施要点

- **执行顺序**：golden 段在 self accept 循环（L732）之前（不变式 2：golden 优先且不可被替代）
- **超时**：golden 判据与 self accept 一致**不加 timeout wrap**（P3 已知限制，见 §6.3）
- `.accept-golden-output.txt`（带点前缀，与现役 `.accept-output.txt` L734 对齐——v1.2 P3-5 统一）独立于 self 通道输出文件回收（契约独立可观测；主控站拉取见 §3.4 P2-2）
- **退出语义**：golden 失败 → `ACCEPT_GOLDEN_OK=0` → 整任务 failed `exit 9`（与 self accept 同码复用，P3-1 有意决策）

### 3.4 M4: 契约扩展

#### 职责

`.meta` 落 `ACCEPT_GOLDEN_OK`；主控站解析并写入 `.agent-run.json` 的 `accept_golden` 字段。来自 DESIGN §3.2 M4 / §4.2。

#### 实施位置

- 远端：`.meta` printf（现 L755）补 `ACCEPT_GOLDEN_OK` 行（echo L753 区同步）
- 主控站：collect 区（现 L763-792）——初始化/解析 L771-779 + **stale 清零 L782-785**（P2-1）+ **`.accept-golden-output.txt` scp 拉取**（P2-2，对齐 L770 先例）+ runDir Move-Item（对齐 L846 先例）；run.json 构造（现 L817-840）+ status 判定（L826）+ ConvertTo-Json（L843）

#### 接口签名

```powershell
# 初始化（L771 区，仿 $accept_ok = $null 先例——v1.2 P3-6 补）：
$accept_golden_ok = $null

# 解析（L778 后追加，仿 ACCEPT_OK 先例）：
if ($m -match 'ACCEPT_GOLDEN_OK=(\d+)') { $accept_golden_ok = [int]$matches[1] }

# stale 清零（L782-785 分支内追加——v1.2 P2-1 补；同分支顺带修 self 的 $accept_ok 为可选加固，本批一并执行）：
if ($metaTaskId -and $metaTaskId -ne "$ts") {
    $queue_s = 0; $run_s = 0
    $accept_ok = $null; $accept_golden_ok = $null    # 陈旧 meta 的判据旧值一律不采信（stale 为准丢弃）
}

# golden 显式判定（v1.2 P2-3 补——消除"仅靠 exit 9→1 隐式兜底"的耦合）：
$acceptGoldenPassed = $true
if ($goldenActive) { $acceptGoldenPassed = ($accept_golden_ok -eq 1) }   # $goldenActive = M2 布尔（$g.source -and $g.cmd）
# status 判定（L826 改）：
status = if ($code -eq 0 -and $acceptPassed -and $acceptGoldenPassed) { 'completed' } elseif ($code -eq 6) { 'timeout' } else { 'failed' }

# golden 输出拉取（collect 区，对齐 L770 先例——v1.2 P2-2 补）：
$accGoldTxt = Join-Path $env:TEMP "agent-cli-accept-golden-$ts.txt"
if ($goldenActive) { scp -q -o ConnectTimeout=10 "${hostName}:$W/out/.accept-golden-output.txt" "$accGoldTxt" 2>$null }
# ... L846 区对齐：if (Test-Path $accGoldTxt) { Move-Item $accGoldTxt (Join-Path $runDir 'accept-golden-output.txt') -Force }

# run.json 构造：有 accept-golden 才写键（无则省略 → schema 可选向后兼容）
if ($goldenActive) {
  $run['accept_golden'] = [ordered]@{
    cmd        = @($g.cmd)
    passed     = ($accept_golden_ok -eq 1)
    source     = 'golden'
    hidden_from_model = $true        # 不变式 1 扩展语义（golden 内容未入 prompt）
    sha256     = $goldenSha          # 2026-09-16 (ADR-0005 D3): 当次注入的权威 checksum
    base       = $goldenBase         #   此前只在主控变量 + 远端脚本字面量里 ⇒ 事后无法回答"跑的是不是这份"。
                                     #   只记于此、不另立 .sha256 文件（避免第二定义点）；与不变式 5 不冲突——
                                     #   不变式 5 约束的是**远端可见面**，而 run.json 在主控侧、模型不可见。
  }
}
```

#### 实施要点

- **stale 处理（v1.2 P2-1 修订）**：现状 stale guard（L782-785）只清零 queue_s/run_s，`$accept_ok` 旧值被采信（self 通道现状行为）。本批实施时**在 stale 分支同时置 `$accept_ok = $null` 与 `$accept_golden_ok = $null`**——golden 陈旧值不写入 `accept_golden`（防陈旧误判）。对 self 通道的行为变化（须在回归测试观察）：stale 时若卡含 self accept，`$acceptPassed = ($null -eq 1)` = False → status=failed——**fail-safe 语义**（陈旧 meta = 本次判据结果未知，未知按失败处理，不采信上一轮旧值），比现状"采信旧值"更安全；stale 本身是异常场景（O-22 注记），正常链路不受影响
- **status 显式判定（v1.2 P2-3 修订）**：golden 失败不再仅靠 exit 9→code=1 隐式兜底，`$acceptGoldenPassed` 显式纳入 status 条件（一行改动）；`accept`（self）字段保持原样；golden 失败时 `exit_code=9→1` 既有映射不变（L792），契约层靠 `accept_golden.passed` 与 `accept.passed` 消歧（P3-1）
- **golden 输出可观测（v1.2 P2-2 修订）**：`.accept-golden-output.txt` 由主控站在 collect 区拉取（golden 激活时）并 Move 入 runDir（`accept-golden-output.txt`），TAMPER/FAIL 用例取证文件可回收到本地

## 4. 接口实施

### 4.1 任务卡 front-matter（schema 增量落地）

```yaml
accept-golden:
  source: spec/d6-agent-standard/strong-accept/golden/path_guard_golden.py
  cmd: python -m pytest .golden/path_guard_golden.py -q
```

**签名一致性**: 与 DESIGN.md §4.1 一致 ✅（单对象，source 保留 basename，cmd 引用同名）

### 4.2 .agent-run.json 契约（新增键）

```json
"accept_golden": {
  "cmd": ["python -m pytest .golden/path_guard_golden.py -q"],
  "passed": true,
  "source": "golden",
  "hidden_from_model": true
}
```

**签名一致性**: 与 DESIGN.md §4.2 一致 ✅

## 5. 兼容性

### 5.1 向后兼容

| 场景 | 行为 |
|------|------|
| 无 `accept-golden` 字段 | Get-FrontMatter 新增键不影响既有 key 解析；golden 段为空 → M2/M3/M4 全部跳过；`.meta` 的 `ACCEPT_GOLDEN_OK` 恒为 1；run.json 不写 `accept_golden` 键；`$acceptGoldenPassed` 恒 $true → status 判定与现状等价 |
| 旧 run.json 读取 | 无 `accept_golden` 键的旧契约视为 self/none，兼容 |
| 远端无 `sha256sum` 场景 | Ubuntu 自带；若缺失（异常环境）→ GOLDEN_TAMPERED 误判为失败（安全侧失败，不放开白）|
| **stale meta（行为变化，P2-1）** | stale 时 `$accept_ok`/`$accept_golden_ok` 置 null：golden 无影响（旧版本无此键）；self accept 存在时 `acceptPassed=False` → status=failed（fail-safe，现状采信旧值可能误判 completed——回归测试 §8.2 须覆盖）|

### 5.2 依赖兼容

| 依赖项 | 来源 | 状态 |
|--------|------|------|
| `$Script:GNU_TAR`（现役 tar+scp）| D6 L1 | ✅ 现役 |
| `$Script:REPO_ROOT`（v1.2 P1-1：**新增** Script 变量，两层上公式）| 本 feature 新增 | 🆕 实施时落地 |
| `Get-FileHash`（PS 内建）| 系统 | ✅ |
| `sha256sum`（Ubuntu）| 系统 | ✅ |
| `ConvertTo-Json -Depth 6`（现 L843）| PS 内建，accept_golden 嵌套深度 ≤ 3 | ✅ |

## 6. 错误处理实施

### 6.1 错误场景与处理（来自 DESIGN §7）

| 错误场景 | 处理代码 | 用户可见信息 | 退出码 |
|---------|---------|-------------|--------|
| golden source 缺失 | `M2 主控站 catch` → 不派发 | `GOLDEN_SOURCE_MISSING: <path>` | 2 |
| golden cmd 失败 | 远端 `ACCEPT_GOLDEN_OK=0` → exit 9 → 主控站 L792 映射 1 | `GOLDEN_FAIL` + `.accept-golden-output.txt`（拉取至 runDir `accept-golden-output.txt`）| 1（远端 9）|
| `.golden/` 文件被改 | checksum 字面量比对失败 | `GOLDEN_TAMPERED` | 1（远端 9）|
| 读→改→还原字节 | 比对通过（残余风险，诚实声明）| 无 | ——（builder-checker 升级路径）|

### 6.2 exit 9 双义复用（P3-1 明示）

self-accept 失败与 golden 失败**均 exit 9** 为**有意决策**（D6 既有 L757 语义，新增 golden 不引入新码）——shell 层无法细分，靠契约层 `accept.passed` / `accept_golden.passed` 消歧。CHECKLIST 错误处理表须补"golden 失败 → ACCEPT_GOLDEN_OK=0 → exit 9 → 映射 1"验收行。

### 6.3 已声明已知限制

| 限制 | 说明 | 处理 |
|------|------|------|
| accept/golden 判据无 timeout | golden pytest 若挂死，远端脚本挂起直至 ssh 层防护 | 与 self-accept 现状一致（MVP 不改语义），CHECKLIST 记录为已知限制；V2 可统一加 wrap |
| 协同篡改不可完全检测 | 模型读 /tmp 脚本字面量并同改 golden 文件（P1-1 残余）| §10.2 诚实声明 + V0 门记录 + builder-checker 升级路径 |

## 7. 不变式实施

| 不变式（DESIGN §8） | 实施位置 | 验证方式 |
|--------------------|---------|---------|
| 1 golden 内容不入 prompt | prompt 构造（L670-675）不含 accept-golden 任何字段 | 远端 `.prompt.txt` grep 不含 `accept-golden`/golden 文件名；prompt_sha256 落契约 |
| 2 来源不可降级 | 远端 golden 段在 self accept 之前；`ACCEPT_GOLDEN_OK≠1` → exit 9 | TAMPER/FAIL 注入测试 |
| 3 注入时序与洁净 | M2 先 `rm -rf .golden` 再注入；时序在 sync 后、$body 前 | 冒烟观察 `/tmp/agent-cli-task-*.sh` 落盘顺序 + 远端 .golden 内容 == 当次注入 |
| 4 权威源唯一 | golden 源只在主控站 `spec/.../golden/`；远端 .golden 仅部署产物 | grep 主控站目录 |
| 5 防篡改 | checksum 字面量 + `sha256sum -c` 比对；**不落盘 .golden.sha256** | TAMPER 注入测试（改文件 → GOLDEN_TAMPERED）|
| 6 golden 结果落契约 | `.meta` 加 ACCEPT_GOLDEN_OK；run.json 加 accept_golden | 回收 .meta + run.json 断言 |
| 7 超时后 golden 仍执行 | golden 段在 opencode timeout（L726）之后独立执行 | A13 timeout 注入卡 + golden 并存 → 回收仍含 ACCEPT_GOLDEN_OK |

## 8. 测试策略

### 8.1 离线单测（主控站，Get-FrontMatter）

| 用例 | 输入 | 断言 |
|------|------|------|
| 解析 accept-golden | 带缩进 source/cmd 的卡 | `$h['accept-golden'].source/.cmd` 命中 |
| 无 accept-golden | 现有卡（paper-pilot/echo）| `$h['accept-golden'].source` 为空，其余字段不受影响 |
| 缩进子键 | 关键回归（旧 parser 会丢）| source/cmd 正确读入 |
| basename 校验 | source=`path_guard_golden.py` + cmd 引用同名 | 注入后文件存在性检查 |

### 8.2 冒烟/集成测试（真实链路）

| 用例 | 通过判据 |
|------|---------|
| **V0 验证门**（首个 golden dogfood 卡）| 配置 `accept-golden` + `.golden/` 哨兵 → 全链跑通：`ACCEPT_GOLDEN_OK=1`、`.meta` 字段、run.json `accept_golden.passed=true`；回收模型输出 -> VISIBLE / NOT_OBSERVED 记录（DESIGN §10.3）|
| **TAMPER 注入** | 任务执行前人为改 `.golden/*.py` → `GOLDEN_TAMPERED` + exit 映射 1 + run.json `accept_golden.passed=false` |
| **golden FAIL** | golden 断言必失败 → `GOLDEN_FAIL` + exit 1（远端 9）|
| **source 缺失** | 卡指向不存在路径 → `GOLDEN_SOURCE_MISSING` exit 2（不派发）|
| **stale meta（P2-1 回归）** | 人为预置上一轮 `.meta`（TASK_ID 不匹配）→ `$accept_ok`/`$accept_golden_ok` 置 null → self 卡 status=failed（fail-safe）；golden 卡无 `accept_golden` 键 |
| **回归** | `agent-cli-smoke.sh` A1-A16 全过；无 golden 卡行为不变（status 判定含 `$acceptGoldenPassed` 恒 true 分支，等价性由 A1-A16 验证）|

### 8.3 统计溯源（RULE-2）

CHECKLIST 验收统计只来自逐项核对表（每行附 run ts / grep 输出 / 退出码），禁止从通过总数推算。

## 9. 幻觉抑制审查（Step 6 Review）

### 9.1 依赖与接口

- [x] 零新增依赖（全部为现役工具，无虚构库/函数）——**附条件**：§9.4 P1-1 指出 `$Script:REPO_ROOT` 为虚构现役引用，须按修复建议落地（新增 Script 变量 + 正确公式）后方完全成立
- [x] 接口签名与 DESIGN.md §4 一致（accept_golden 单对象字段）
- [x] PS 内建 API 在 PS 5.1 可用（`[Convert]::ToBase64String`/`Get-FileHash` 均内建）

### 9.2 模块对齐（DESIGN §3.2 ↔ 实施）

- [x] M1-M4 每模块对应一处实施位置（均在 agent-cli.ps1）——实码锚点逐一比对通过（off-by-one 项见 §9.4 P3-4）
- [x] 无设计未覆盖的实施（golden 不在 DESIGN 中的行为——如 `.meta` 恒出 ACCEPT_GOLDEN_OK——须登记为 derived-requirement）——已登记于 §3.3 默认行注释与 §9.2；§10 Step 6 收尾须在 CHECKLIST 落 derived-requirement 正式条目

### 9.3 低效操作排除

- [x] 不新增文件读取（单次 foreach 内完成 front-matter 扩展）
- [x] checksum 只在主控站算 1 次（不重复 Get-FileHash）
- [x] 远端 golden 段无冗余 I/O（base64 单次解码）

> **§9.1-9.3 勾选执行记录（2026-09-09，随 §9.4 复审一并核验）**：9.1 第一项"零新增依赖"核验通过——`Get-FileHash`/`[Convert]::ToBase64String`/`sha256sum`/GNU tar 均现役或系统内建，**但 §3.2 引用的 `$Script:REPO_ROOT` 为虚构现役引用**（见 §9.4 P1-1），勾选附条件：须按 §9.4 修复后该声明方成立。其余各项（接口签名一致、PS5.1 API 可用、M1-M4 单点落位、derived-requirement 登记、低效排除）核验通过。

### 9.4 异基座复审记录（2026-09-09，RULE-5：仅标记不改写）

> **复审者声明**：本节由切换模型后的会话独立执行（与 v1.1 修订会话不同模型；但该会话保留了 v1.1 编辑上下文，非完全冷启动——结论仍带单视角偏差风险，修复后建议冷启动会话终审确认）。取证手段：agent-cli.ps1 全量读码（L486-522 Get-FrontMatter / L558-760 Invoke-Task 全流程：sync L625→attach L632-664→prompt L669-685→acceptB64 L687-691→$body L697-759 / collect L763-792 / run.json L794-852）+ 全部行号锚点逐一比对 + `$Script:*` 变量 grep。**只标记问题，修复由主控会话执行后交复审确认**。

#### 已核实为正确的关键声明（正面清单）

| 实施声明 | 取证 |
|---|---|
| M1 解析器结构（if/elseif 链、`$curKey` 先例、白名单哈希、缩进子键被顶层正则吞掉）| agent-cli.ps1 L493-509 逐行比对 ✓（嵌套分支前置的必要性论证成立）|
| M2 嫁接时序（sync 后、$body 前，串行）| L625 sync → L632-664 attach → L687-691 acceptB64 → L697 $body：注入点合法存在 ✓ |
| tar+scp 注入链先例 | L244/L279 `GNU_TAR --force-local` 现役 ✓ |
| M3 插入位置（L731 `ACCEPT_OK=1` 后、L732 if 前）| 实码比对 ✓；`set -u` 下 `GOLDEN_ACTIVE`/`ACCEPT_GOLDEN_OK` 默认行恒定义 ✓ |
| 不变式 7 结构（timeout L726 仅杀 opencode，脚本继续）| L726-757 实证 ✓ |
| sha256sum -c 比对格式（双空格、失败→TAMPERED 路径、文件缺失→安全侧失败）| bash 语义正确 ✓ |
| L757 守卫扩展语法（`{ } || { }` 组合、set -u 安全）| 语法正确 ✓ |
| M4 stale 丢弃意图、exit 9→1 映射、run.json 可选键向后兼容 | L771/L782-785/L792/L838 实证 ✓ |
| heredoc 转义纪律（`$W` 反引号转义 vs PS 字面量插值）| 与 L726/L731 先例一致 ✓ |
| §2.1 零外部依赖（除 REPO_ROOT 外）| grep `$Script:*` 全表核对 ✓ |
| smoke 脚本存在（§8.2 回归判据）| `ops/station-bin/agent-cli-smoke.sh` 实存 ✓ |

#### 发现问题

| 级别 | 问题 | 位置 | 修复建议 |
|---|---|---|---|
| **P1-1** | **`$Script:REPO_ROOT` 虚构现役引用 + 构造公式错一层（阻断）**：agent-cli.ps1 全文无 REPO_ROOT（grep 实证，现役 Script 变量仅 GNU_TAR/REMOTE_USER/WORKSPACE_ROOT/PROJECTS/TMP_ROOT/ROUTE_TABLE/AGENTSYNC_TEMPLATES）。且文档给出的公式 `Split-Path $PSScriptRoot -Parent` 求值为 `d:\RPC\ops`（agent-cli.ps1 位于 `d:\RPC\ops\station-bin\`），golden source `spec/d6-agent-standard/...` 相对它解析不存在 → **首个 dogfood 卡必 GOLDEN_SOURCE_MISSING abort（exit 2）**，feature 不可用 | §3.2 M2 接口签名 + 实施要点 | 声明 REPO_ROOT 为**新增** Script 变量（`$Script:REPO_ROOT = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent`，即两层上 = `d:\RPC`），或直接以 `$Script:REPO_ROOT` 相对注入点显式赋值；同步修 §9.1 第一项勾选附条件 |
| **P2-1** | **stale guard 描述与代码现状不符且实施指令含糊**：§3.4 称"golden 同样以 stale 为准丢弃（accept_golden 不写入）"，但现状 stale guard（L782-785）**只清零 queue_s/run_s，不清 `$accept_ok`**——self accept 在 stale 时旧值被采信。文档既未指出这一现状不对称，也未给出 golden 清零的实施位置（`$accept_golden_ok = $null` 初始化仿 L771 + stale 分支补清零）| §3.4 实施要点 | 实施时补：L771 区初始化 `$accept_golden_ok = $null`；stale 分支同时置 `$accept_golden_ok = $null`（顺带修 self 的 `$accept_ok` 清零为可选加固，须显式声明是否纳入本批）|
| **P2-2** | **collect 未拉取 `.accept-golden-output.txt`**：§3.3 承诺"独立于 accept-output.txt 回收（契约独立可观测）"，但 M4 实施位置与 §10 Step 4 均未列 scp 拉取（现状 L770 仅拉 `.accept-output.txt` 且仅在 self accept 存在时）→ golden 输出滞留远端，TAMPER/FAIL 用例（§8.2）的取证文件拿不回来 | §3.3 / §3.4 / §10 Step 4 | Step 4 清单补两行：collect 区 scp `.accept-golden-output.txt`（golden 激活时）+ runDir Move-Item（对齐 L770/L846 先例）|
| **P2-3** | **status='completed' 与 golden 的耦合为隐式且未声明**：L826 `status = if ($code -eq 0 -and $acceptPassed)` 只含 self 通道 `$acceptPassed`；golden 失败当前**仅靠 exit 9→code=1 隐式兜底**为 failed。§3.4 未声明此隐式耦合，也未声明是否引入 `$acceptGoldenPassed` 显式变量——V2 若改退出码或映射，golden 失败可能漏判 completed | §3.4 实施要点 | 至少明示"status 由 exit 9→1 隐式覆盖 golden 失败（现状自洽）"；建议本批即引入 `$acceptGoldenPassed` 并纳入 status 条件（一行改动，消除隐式耦合）|
| P3-4 | **行号锚点系统性 off-by-one**：exit 9 映射实际 **L792**（doc 写 L793）；collect 解析实际 L773-779、stale L782-785（doc 写 L774-786/L783-786）；run.json 构造实际 L817-840、ConvertTo-Json 实际 L843（doc 写 L818-841/L844）| §3.4 / §6.1 表 | 批量校正 ±1（ADD 审计锚点纪律）|
| P3-5 | **输出文件名不一致**：M3 代码段用 `.accept-golden-output.txt`（带点，与现役 `.accept-output.txt` L734 一致 ✓），但 §3.3 实施要点与 §6.1 错误处理表写 `accept-golden-output.txt`（无点）| §3.3 要点 / §6.1 表 | 统一带点前缀 `.accept-golden-output.txt`（含 P2-2 的 scp 拉取同名）|
| P3-6 | **M4 片段变量来源未声明**：`$g` 全文无赋值语句（应 `$g = $fm['accept-golden']`，M2 片段直接以 `if ($g.source...)` 使用）；`$accept_golden_ok` 初始化未声明（仿 L771 `$accept_ok = $null` 先例）；`-ne $null` 建议改 `$null -ne $x` 左侧写法（PS null 比较坑）| §3.2 / §3.4 接口签名 | M2 片段首行补 `$g = $fm['accept-golden']`；M4 补初始化与写法 |

#### 复审结论

**有条件通过**：P1×1（REPO_ROOT 虚构引用 + 公式错层——首个 dogfood 卡必 abort，阻断级）修复后可进入 Step 9 实施；P2×3 应修（可随 P1 批次一并，均为小改动：stale 清零指令、golden 输出拉取、status 显式判定）；P3×3 提示。M1/M3 的核心解析逻辑、注入链、防篡改比对、退出守卫经实码比对**全部成立**；v1.1 修订记录中自报的 6 项缺陷修复经逐项核验属实。

#### P1+P2 修复批执行记录（v1.2，主控会话 2026-09-09）

| 项 | 状态 | 落点 |
|---|---|---|
| P1-1 REPO_ROOT 虚构引用 + 公式错层 | ✅ 改为**新增** Script 变量 + 两层上公式（`Split-Path (Split-Path $PSScriptRoot -Parent) -Parent` = `d:\RPC`）；§5.2 依赖表登记为新增项；§10 Step 2 补 REPO_ROOT 解析正确性测试 | §3.2 M2 / §5.2 / §10 Step 2 |
| P2-1 stale guard 描述与代码不符 | ✅ 实施指令落地为代码片段（stale 分支双清零）；fail-safe 行为变化声明（self 卡 stale → failed，比采信旧值安全）+ §5.1 兼容表新增行 + §8.2 补 stale 用例 | §3.4 / §5.1 / §8.2 / §10 Step 4 |
| P2-2 collect 未拉取 golden 输出 | ✅ M4 片段补 `$accGoldTxt` scp（golden 激活时）+ runDir Move（对齐 L770/L846 先例）；§6.1 表补拉取落点 | §3.4 / §6.1 / §10 Step 4 |
| P2-3 status 隐式耦合 | ✅ `$acceptGoldenPassed` 显式判定纳入 status 条件（一行改动）；`$goldenActive` 在 M2 片段补布尔输出（定义来源完整） | §3.2 / §3.4 |
| P3-4 锚点 off-by-one | ✅ L793→L792、L774-786→L771-779/L782-785、L818-841→L817-840、L844→L843 批量校正 | §3.4 / §5.2 / §6.1 |
| P3-5 文件名不一致 | ✅ 统一带点 `.accept-golden-output.txt`（远端），拉取落 runDir `accept-golden-output.txt`（对齐 `.accept-output.txt` → `accept-output.txt` 现役先例） | §3.3 / §6.1 / §10 Step 3 |
| P3-6 变量来源未声明 | ✅ M2 片段补 `$g = $fm['accept-golden']` 赋值 + `$goldenActive` 布尔；M4 补 `$accept_golden_ok = $null` 初始化；`if ($goldenActive)` 替代 `-ne $null` 写法 | §3.2 / §3.4 |

**P1+P2 清零，P3×3 顺带全清。** 本修复批由保留 §9.4 复审上下文的会话执行（非冷启动）——按复审者声明，建议冷启动会话终审确认后再进入 Step 9 实施。

---


## 10. 实施步骤（TDD，Step 9 执行）

### Step 1: M1 FrontMatter 扩展 + 离线单测先行

- 文件: `agent-cli.ps1`（Get-FrontMatter）
- 内容: 新增 `accept-golden` 键 + 嵌套续行分支；先写 §8.1 离线单测脚本断言解析
- 测试: §8.1 四用例全过后才进入下一步（TDD）

### Step 2: M2 注入 + 主控站校验

- 文件: `agent-cli.ps1`（Script 头部区 + Invoke-Task）
- 内容: **新增 `$Script:REPO_ROOT`（两层上公式，P1-1）**；`$g`/`$goldenActive` 赋值；source 存在性 abort（exit 2）、Get-FileHash 算权威值、rm -rf + tar/scp 注入
- 测试: source 缺失用例 + 远端 .golden 内容断言 + REPO_ROOT 解析正确性（golden source 实文件命中，非 GOLDEN_SOURCE_MISSING 误报）

### Step 3: M3 远端 golden 段

- 文件: `agent-cli.ps1`（$body heredoc）
- 内容: checksum 字面量比对 → golden cmd base64 执行 → ACCEPT_GOLDEN_OK + `.accept-golden-output.txt` + `.meta` 新行
- 测试: TAMPER + FAIL 注入用例

### Step 4: M4 契约扩展

- 文件: `agent-cli.ps1`（collect 解析 + run.json）
- 内容: 初始化/解析 `ACCEPT_GOLDEN_OK`（L771/L778 区）；**stale 分支双清零（P2-1）**；**status 显式判定 `$acceptGoldenPassed`（P2-3）**；**`.accept-golden-output.txt` scp 拉取 + runDir Move（P2-2）**；写 accept_golden 字段（无 golden 省略）
- 测试: run.json 断言（passed/source/hidden_from_model）+ §8.2 stale 用例

### Step 5: V0 验证门（首个 dogfood）

- 文件: `test-cards/dogfood-strong-accept.md`（新）+ `golden/path_guard_golden.py`（新）
- 内容: 含哨兵 `.golden/` 的真实代码卡
- 测试: §8.2 V0 用例 + 结果写回 DESIGN §3.1 注记与 OPEN-ISSUES O-12

### Step 6: 回归 + 文档收尾

- 内容: smoke A1-A16 全过；CHECKLIST 补错误处理行（golden 失败/exit 9 双义）；derived-requirement 登记（.meta 恒出 ACCEPT_GOLDEN_OK）
- 测试: §8.2 回归用例

---

## 11. V0 验证门执行复盘（2026-09-09，完整经验教训落档）

> 本节记录 V0 验证门真实执行全程（run 182435 TAMPERED / run 183302 通过 / run 184115 back-compat）暴露的问题与教训。**已修复项入实码，纪律性教训入 project_memory**（跨会话约束）。

### 11.1 执行中暴露的问题（按发现顺序）

| # | 问题 | 根因 | 修复 | 教训类别 |
|---|------|------|------|---------|
| V0-1 | `agent-cli.ps1` 编辑后运行时语法崩溃（`ROUTE_TABLE` "Unexpected token '}'" L48-63）| Edit 操作剥离文件 **UTF-8 BOM**，PS5.1 按 ANSI(GBK) 解码中文注释 → 乱码破坏词法 | 补回 BOM 头（EF BB BF）；**验证通行证：BOM 检查 + `[Parser]::ParseFile`（注意 PS5.1 ANSI 坑——用 `ReadAllText` UTF8 + `ParseInput`，见 _fm_golden_test.ps1 注释）** | 工具链纪律（§2.3 早已记载, 实操再犯——教训：**编辑后必查 BOM**）|
| V0-2 | A 站 `infer-load gpt-oss-120b` unsloth 后端失败（`invalid device: Vulkan0` → 健康检查超时）| A 站脚本默认 unsloth 路径硬编码 `--device Vulkan0`（`~/.local/bin/unsloth` 用 **b10715 旧 llama-server**，其 Vulkan 设备枚举与 `/opt/llama.cpp` master 不同；A 站 AMD gfx1151 实际设备名 `Vulkan0: AMD Radeon Graphics (RADV GFX1151)` 仅被 `/opt` master 识别）| 改用 **`infer-load ... --backend llama-single`**（systemd → `/opt/llama.cpp/llama-server`，`--list-devices` 确认 `Vulkan0` 有效）| 环境拓扑（sst smoke 注释假设 A 站 8080 本地引擎；`cluster-litellm/gpt-oss` 实测指向 A 站本地 8080，非 B 站网关）|
| V0-3 | `PATH` 注入的 tarball 远端解压失败 → `.golden/` 空 → `GOLDEN_TAMPERED` | **压缩格式不匹配**：主控 `tar -cf` 生成 **plain tar**，远端注入脚本写成 `tar -xzf`（期望 gzip）→ `not in gzip format` | 远端 `-xzf` → `-xf`（与现役 sync 链 L246/L260 `-cf`/`-xf` 对齐）| 压缩语义（**充要教训：主控打什么档、远端解什么档，参照现役同步链先例，勿自创**）|
| V0-4 | collect 阶段 `scp .accept-golden-output.txt` 抛 `NO_SUCH_FILE` 错误（PS EAP=Stop → NativeCommandError 污染退出码）| TAMPERED 路径下 golden 未执行 → 输出文件不产生；无 try/catch 保护 | `$accGoldTxt` scp 包 try/catch（缺失即置 null + Test-Path 防护）| Fail-safe 输出拉取（**判据失败路径的输出文件可能不存在，collect 必须容忍**）|

### 11.2 安全侧失败的正确性验证（正向结果）

V0-1 修复前首次跑 dogfood（run 182435）因 **V0-3 注入失败 → checksum 比对 `GOLDEN_TAMPERED` → `ACCEPT_GOLDEN_OK=0` → exit 9 → 主控映射 failed**：
- 该意外路径 **精确验证了不变式 5 的 fail-safe 语义**——`.golden/` 内容任何不一致（无论模型篡改还是注入故障）都不放行
- `.meta` 记录 `ACCEPT_GOLDEN_OK=0` 且 run.json `accept_golden.passed=false` 完整落契约
- 修复后 run 183302 正常通过，确认 TAMPERED 只在高危路径触发

### 11.3 遗留用例补跑（A15c 全闭环，2026-09-09）

| 项 | 状态 | 实证 |
|---|------|------|
| golden **FAIL** 用例（cmd 必败 → `GOLDEN_FAIL`）| **☑ 已执行** | run 202609091855364954（card `dogfood-golden-fail.md`, cmd=`false`）：远端 `GOLDEN_FAIL rc=1` + `ACCEPT_GOLDEN_OK=0` + `TASK_RC=0`/`ACCEPT_OK=1`（模型侧成功）→ exit 9 → 主控映射 1 → run.json `exit_code=1 status=failed` + `accept_golden.passed=false` + `accept.passed=true`——**契约层双 passed 字段成功消歧 exit 9 双义（P3-1）** |
| golden **source 缺失** 用例（`GOLDEN_SOURCE_MISSING` exit 2）| **☑ 已执行** | card `dogfood-golden-source-missing.md`（source 指向不存在路径）：sync 完成后 M2 catch → `GOLDEN_SOURCE_MISSING: ...does-not-exist_xxx.py (resolved under D:\RPC)` → **EXIT_CODE=2**，派发前 abort、不启会话 ✓ |

### 11.4 跨会话纪律（已落 project_memory，2026-09-09）

1. **编辑 `agent-cli.ps1` 后必须核对 UTF-8 BOM**（EF BB BF）+ 跑 `_fm_golden_test.ps1` 离线回归（其 AST 提取即语法门）
2. **remote 脚本的 tar 压缩档必须与现役同步链一致**（plain `-cf`/`-xf`），新增远端解压先查主控打包参数
3. **判据失败路径的输出文件可能缺席**，collect 对 optional 文件一律 try/catch + Test-Path
4. **A 站 gpt-oss 引擎用 `--backend llama-single` 加载**（`/opt/llama.cpp` master 识别 gfx1151 Vulkan0；unsloth b10715 路径对 A 站设备名失效）
5. **TAMPERED = 安全侧失败是特性**（不变式 5 的 fail-safe），故障排查先区分"注入故障"与"真实篡改"——本次 V0-3 即注入故障误触发

---

**Review 签字**: _________ 日期: _________