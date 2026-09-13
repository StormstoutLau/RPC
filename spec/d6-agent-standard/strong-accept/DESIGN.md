# 设计文档：strong-accept（主控站侧 golden 测试，防模型自证）

---
id: d6-strong-accept-DESIGN
type: design
version: 1.2
status: draft
date: 2026-09-09
depends: [d6-strong-accept-RESEARCH, d6-agent-standard-DESIGN v1.4, d6-agent-standard-OPEN-ISSUES v1.0]
upstream: null
---

> **Feature**: strong-accept（O-12——主控站侧独立 golden 测试，消除"模型自写测试自证通过"）
> **创建日期**: 2026-09-09
> **状态**: v1.2（Step 4 修复批完成：异基座复审 §9.4 P1×2/P2×3 + 复核 §9.5 分级修正已全部执行，P1+P2 清零，P3×4 转入 IMPLEMENTATION 处理并记录 §9.5；可进入 Step 5）
> **Spec 步骤**: Step 3-4
> **基于调研**: [RESEARCH.md](./RESEARCH.md) v1.0（异基座复审通过，P2 全部修复）

---

## 1. 设计目标

给 D6 accept 机制引入**主控站权威的、独立于模型的**验收判据源（`accept-golden`），消除"模型自写测试自证通过"（A14 事故 + arXiv:2602.07900 实证的自证失效）。核心：**测试来源信任分级**——golden（主控站权威判据）/ self（模型自写，现状）/ none（无判据）三态显式区分，golden 优先且不可被任务卡/模型降级。

**非目标**：不替代现有 `accept`（self 通道保留，用于非关键卡）；不实现 mutation testing 自动化（可选项，§10 风险）；不做 builder-checker 双模型（超出本 feature 范围，research 已标注）。

## 2. 设计依据

### 2.1 调研结论

| 调研发现 | 设计决策 | 引用 |
|---------|---------|------|
| D6 accept 在远端 eval 模型自写测试（agent-cli.ps1 L740），A14 已实测自证通过 | 引入 `accept-golden`：主控站预置权威判据（golden 内容不入 prompt；bash 读取可见性不承诺，见 §3.1 P1 注记）| RESEARCH §3.1 |
| arXiv:2602.07900：agent 自写测试与任务成败不相关（写/不写差 ~3 分）| golden 是**主控站权威判据**（模型不可自写测试自证，即消除"模型定义验收标准"），self 降级为弱验收（观测通道）| RESEARCH §3.2 |
| specification-first 是正确形态（主控站先写权威测试，模型实现时不可见）| golden 测试在任务派发**前**注入工作区 `.golden/`（防 list 默认展示；bash 读取可见性不承诺，见 §3.1 P1 注记）| RESEARCH §3.2/§4.1 |
| verify-anchor 模式可复用（权威判据前置 + 机械执行）| 复用**设计模式**（非代码）：主控站权威 + 机械判据 + 模型不可自写判据 | RESEARCH §3.3 |
| AfterVibe（arXiv:2607.09900）同方向 multi-tier verification | 本 feature 采用其"blind verification"思想（验证者不知实现）| RESEARCH §3.4 |

### 2.2 相关设计

| 文档 | 决策 | 对本设计的影响 |
|------|------|--------------|
| d6-agent-standard-DESIGN v1.4 §6.1 | 任务卡 front-matter schema（`accept:` 列表已存在）| `accept-golden` 为 schema 增量（字段可选，向后兼容）|
| d6-agent-standard-DESIGN v1.4 §6.2 | .agent-run.json 契约（`accept: {cmd, passed}`）| 契约补 `accept_golden` 观测字段（来源分级）|
| d6-agent-standard-DESIGN v1.4 §9 不变式 | 不变式 5（Model-visible means logged）| golden 结果落契约（扩展日志完备）|
| agent-cli.ps1 L681-683（wrapper 实现先例）| sanitized scrubber 门禁：`if ($sens -eq 'sanitized') { $promptFull = Invoke-Scrubber $promptFull }`（console 侧消毒后出站）| golden 内容不得进入 prompt = 同型门禁（消毒语义扩展）；不变式 1 以此为操作模板 |
| d6-agent-standard-CHECKLIST §2.6 A14（根因 P1b：任务卡正文未传输，模型自写宽松测试致 "11 passed" 自证通过）| A14 自证事故 | 本 feature 的直接动机 |
| d6-agent-standard-OPEN-ISSUES O-12 | strong accept 定义 | 本 feature 的任务来源 |

### 2.3 职责边界

- **职责内**：`accept-golden` 字段解析、golden 测试前置注入（主控站→工作区 `.golden/`）、远端执行 golden 判据、契约记录来源分级
- **职责外**：mutation testing 全自动化（可选加固，另立）；builder-checker 双模型验证（另一 feature）；claude 路径（二期 G1）
- **能力边界**：golden 测试**无法验证语义正确性**（如"论文论证是否严谨"）——仅可验证可机械判定的规格（数值/结构/行为）。语义层留给人/异基座审查（同 verify-anchor 边界）

## 3. 架构设计

### 3.1 整体架构

```
主控站（权威层）                     远端工作区（执行层）
─────────────────                   ────────────────────
任务卡 accept-golden:                .golden/  (防 list 默认展示)
  - pytest .golden/path_guard_golden.py   ├── path_guard_golden.py   ← 主控站预置
  - python .golden/verify.py              └── verify.py
        │                                    │
        ▼ 任务派发前注入                        ▼ accept 执行阶段
  golden 测试 tar → 工作区 .golden/  ←── ( cd $W && eval golden cmd )
        │                                    │
        ▼                                    ▼
  .agent-run.json 记录来源分级        ACCEPT_GOLDEN_OK (独立于 ACCEPT_OK)
  accept_golden: {cmd, passed, source: golden}
```

**关键分离**：golden 测试**主控站权威写入**（独立于模型实现的判据）→ 远端仅执行不生成。这是与现状 self-accept（模型在任务中自写测试）的本质区别。

> **P1 修复注记**：`.golden/` 为隐藏目录仅防 **list 工具默认展示**（sst/opencode #4689 实证 list 遵循 .gitignore，但 bash 工具不受约束）。**不承诺模型经 bash 工具读不到**（E2 实证）。核心价值 = 测试为独立实现（消除自证），非"模型不可见"。可见性由 V0 验证门实测后记录（定义见 §10.3）。

### 3.2 模块划分

| 模块 | 职责 | 输入 | 输出 | 依赖 |
|------|------|------|------|------|
| M1: FrontMatter 扩展 | 解析 `accept-golden` 字段（新增）| 任务卡 md | golden 命令 + source 路径（单对象）| **扩展** Get-FrontMatter（新增键 + 嵌套续行解析，仿 accept `$curKey` 模式，见 §10.1）|
| M2: Golden 注入 | 主控站打包 golden 测试 → **清空并**写入工作区 `.golden/`（P2-3）| golden 测试源路径 | 远端 `.golden/` 目录 + 权威 checksum（供 M3 比对）| tar+scp（复用同步链）|
| M3: Golden 执行 | 远端运行 golden 判据（与 accept 同通道但独立计分）| golden 命令列表 | `ACCEPT_GOLDEN_OK` + `accept-golden-output.txt` | 现有 accept 执行循环 |
| M4: 契约扩展 | .agent-run.json 记 `accept_golden` 字段 | 执行结果 | 契约文件 | Write-RunJson |

### 3.3 数据流

```
任务卡 --accept-golden--> M1 解析 --> golden 命令 + golden 测试路径
                                        │
M2: golden 测试源 → tar → scp → .golden/   （任务派发前；sync 之后、融合脚本之前，串行——不变式 3）
                                        │
opencode run（prompt 不含 golden 内容——不变式 1）
                                        │
M3: cd $W && eval golden_cmd → ACCEPT_GOLDEN_OK
                                        │
M4: 契约 .agent-run.json 补 accept_golden {cmd, passed, source}
```

### 3.4 控制流

```
task 命令 → 1) FrontMatter 解析（含 accept-golden）
         → 2) [golden 存在] 打包注入 .golden/（派发前）
         → 3) [golden 存在] prompt 构造时排除 golden 内容（不变式 1）
         → 4) station_ready → sync → lock → opencode run（golden 内容不入 prompt——不变式 1；bash 工具经文件系统读到 `.golden/` 的可能性不承诺，见 §3.1 注记）
         → 5) accept 执行：先 golden 判据（ACCEPT_GOLDEN_OK），再 self 判据（ACCEPT_OK）
         → 6) 契约记录来源分级
         → 7) 整任务通过条件：agent RC=0 AND golden 通过（若有）AND self 通过（若有）
```

## 4. 接口定义

### 4.1 任务卡 front-matter 扩展（schema 增量）

```yaml
---
# 现有字段不变（proj/task/model/cli/.../accept）
accept-golden:                                    # 新增（可选，O-12，单对象 source↔cmd）
  source: spec/d6-agent-standard/strong-accept/golden/path_guard_golden.py
  cmd: python -m pytest .golden/path_guard_golden.py -q
  # source: 主控站侧 golden 测试文件相对路径（随任务注入 .golden/，保留 basename——命名规则：不重命名）
  # cmd: 远端执行命令（工作区内；必须引用与 source 同 basename 的文件）
---
```

**约束**：
- `accept-golden` 与 `accept` 可共存——golden 优先且独立计分；两者任一失败 → 整任务 failed
- `accept-golden` 的 `cmd` 默认前缀 `cd $W && `（与 accept 同执行语义）
- golden 测试文件随 `source` 从主控站注入 `.golden/`，**golden 内容不入 prompt**（.agentsync 排除防回流 + 不变式 1；bash 工具读取可见性不承诺，见 §3.1 注记）
- **注入命名规则**：`.golden/` 内保留 source 的 basename（不重命名）——cmd 必须引用与 source 同 basename 的文件（首版示例曾 source=`path_guard_golden.py` 而 cmd 引用 `test_path_guard.py`，且 §6.2 布局图亦异名，属 P2-2 缺陷已在 v1.2 统一）

### 4.2 .agent-run.json 契约扩展

```json
{
  ...existing fields...,
  "accept": {"cmd": [...], "passed": true},
  "accept_golden": {                          # 新增（O-12）
    "cmd": ["python -m pytest .golden/path_guard_golden.py -q"],
    "passed": true,
    "source": "golden",                       # 来源分级：golden / self / none
    "hidden_from_model": true                 # 不变式 1 扩展语义：golden 内容未入 prompt（bash 工具可见性不承诺，见 §3.1 注记）
  }
}
```

### 4.3 信任分级（三态）

| 分级 | 判据源 | 适用 | 通过语义 |
|------|--------|------|---------|
| **golden**（主控站权威）| 主控站预置独立实现（非模型自写）| 有可判定规格的代码卡 | **主控站权威判据**（模型不可自写测试自证）——不承诺模型无法读到测试内容（详见 §3.1 P1 修复注记）|
| **self**（模型自写，现状）| 模型任务中自写 | 无 golden 的代码卡（弱验收）| 弱验收（观测通道，非 QA）|
| **none** | 无 | 调研/产物卡（grep 文件存在）| 无验收（依赖人工复查）|

> **信任分级注记（P1 修复，2026-09-09）**：golden 的核心价值 = **消除"模型定义验收标准"**（A14 事故根因：模型既写实现又写测试）。即使模型能读到 golden 测试内容（opencode bash 工具不受隐藏目录约束，E2 实证），测试仍是主控站独立实现——模型无法"写宽松测试让自己通过"。残余风险 = 模型读到测试后**针对优化**（教学提示问题），由 V0 验证门实测可见性 + 防篡改 checksum 兜底（§8 不变式 5）。故"强验收"措辞改为"主控站权威判据"，不承诺"模型无法游戏"（详见 §3.1 P1 修复注记）。

## 5. 替代方案

### 5.1 方案 A: 主控站 golden 测试注入（选择）

- 描述: 主控站预写权威测试 → 派发前注入 `.golden/` → 远端执行
- 优点: **消除"模型定义验收标准"**（测试为独立实现，模型不可自写自证）；与现有 accept 机制同构（复用执行循环）；任务卡 schema 增量最小
- 缺点: 需人工预写 golden 测试（成本）；golden 测试自身可能错（误拒正确实现）；模型可能读到测试后针对优化（诚实降级注记 §4.3）
- 选择理由: 调研结论 specification-first 的直接落地；成本可控（仅"有可判定规格"的卡需要）；解决 A14 核心问题

### 5.2 方案 B: builder-checker 双模型（否决）

- 描述: 第二模型（异构）独立设计测试并评审实现
- 优点: 真"模型不可见"（异基座第二模型，实现模型接触不到测试）；无需人工预写
- 缺点: 2× 推理成本；需模型调度复杂度；调研标注"对 D6 集群可用但超范围"
- 否决理由（P1 修复后重述，2026-09-09）: golden 注入虽无法保证"模型不可见"（bash 工具可读隐藏目录），但仍**消除自证根因**（测试非模型自写）；builder-checker 是更强保证（真不可见）但 2× 成本 + 调度复杂度。本 feature 先以 golden 落地核心价值，builder-checker 保留为**未来增强**（当 golden 的"针对优化"残余风险被 V0 门实证为严重问题时启用）

### 5.3 方案 C: mutation testing 自动化（否决，可选）

- 描述: golden 测试就绪后跑 mutmut 验其能抓变异
- 优点: 验证 golden 测试自身质量
- 缺点: 额外算力；变异覆盖率阈值需人工定
- 否决理由: 作为本 feature 的可选加固（§10 风险缓解），非 MVP 必需

## 6. 数据结构

### 6.1 Golden 测试源（主控站）

```
spec/d6-agent-standard/strong-accept/golden/
└── path_guard_golden.py       # 例：独立实现的 10 条断言（非模型自写）
```

**设计要点**：golden 测试与任务卡规格**独立实现**（主控站人写或另起模型写），测试断言覆盖规格的可判定面（数值/结构/行为），不依赖模型交付的测试文件。

### 6.2 注入后工作区布局

```
~/agent-workspaces/<proj>/
├── .golden/                    # 防 list 默认展示（bash 读取可见性不承诺，见 §3.1 P1 注记）
│   └── path_guard_golden.py    # 注入后保留 source basename（命名规则：不重命名）
├── .agentsync                  # 排除 .golden/（防 sync 回流）
├── out/
└── paper_cli/                  # 模型实现交付区
```

## 7. 错误处理

| 错误场景 | 处理方式 | 用户可见信息 |
|---------|---------|------------|
| golden 测试源文件缺失 | task 派发前 abort（exit 2）| `GOLDEN_SOURCE_MISSING: <path>` |
| golden cmd 远端执行失败 | ACCEPT_GOLDEN_OK=0 → 整任务 failed（exit 9，经 wrapper 映射为 1）| `GOLDEN_FAIL` + accept-golden-output.txt |
| 模型改动 `.golden/` 内文件 | 执行前权威 checksum（脚本字面量）比对失败 → GOLDEN_TAMPERED | `GOLDEN_TAMPERED` |
| golden 文件被模型篡改（读→改→还原字节）| checksum 比对成功（字节已还原）无法检出（残余风险）；声明在 §10.2；由 V0 门记录 + builder-checker 升级路径缓解 | 无（已知残余风险）|

## 8. 不变式（ADD 审计依据）

1. **golden 内容不进入 prompt**（可判：远端 `.prompt.txt` grep 不含 golden 内容，prompt_sha256 落契约可复核）——注意：不承诺模型经工具读不到 `.golden/`（P1 修复：bash 工具不受隐藏目录约束，E2 实证）；文件系统面不可见性由 V0 验证门实测记录，不设为不变式
2. **来源不可降级**：任务卡含 `accept-golden` 时，golden 判定**必须执行且通过**才可整任务成功；`accept` 通过不能替代 golden
3. **注入时序与洁净**：golden 测试在任务派发**前**注入 `.golden/`（模型开始前已就位，sync 后、融合脚本前，串行）；**M2 注入前先清空工作区 `.golden/`**——保证 `.golden/` 恒等于当次注入内容（跨任务陈旧残留排除；V0 哨兵测量不被旧文件污染；残留即视为不洁净）
4. **权威源唯一**：golden 测试的权威副本在主控站（`spec/.../golden/`），工作区 `.golden/` 是部署产物（可重建）
5. **防篡改（v1.2 P1-1 重述，可判形式）**：golden 执行前，远端 `.golden/` 全文件 checksum 与主控站权威值比对，不一致 → `GOLDEN_TAMPERED` 整任务 failed。**锚点（P1-1 修订）**：权威 checksum 以**字面量嵌入融合远端脚本** `$body` heredoc（主控站 `Get-FileHash` 计算、wrapper 每任务注入，与 `$acceptB64` 同通道先例 agent-cli.ps1 L730；脚本经 R14 落盘链每次任务新生成、**不在工作区常驻**——消除模型唯一读/写点；不再落盘 `.golden.sha256` 到工作区）。**残余风险**：模型理论上可读 /tmp 下脚本字面量并协同改写（读→改→还原字节与针对脚本修改均不可完全检测）——诚实声明于 §10.2，由 V0 门实测记录 + builder-checker 升级路径兜底（§5.2）
6. **golden 结果落契约**：golden 判定结果（cmd/passed）必须写入 `.agent-run.json`（D6 不变式 5"Model-visible means logged"的扩展）
7. **超时后 golden 仍执行**：agent 超时/被杀（RC=124→6）时 golden 判据仍照常执行并如实回收（对齐 D6 §6.2 accept"反证可观测"语义）

## 9. 幻觉抑制审查（Step 4 Review）

> **执行记录（2026-09-09 独立 pass，【自查·单视角】——RULE-4 声明）**：本清单在 v1.1 正文完稿后单独一轮核验勾选（非并发自查）。同一 agent 既写又审，结论带单视角偏差风险；**待用户手动切换异基座复审**（用户已确认将另起会话执行）。本轮自查发现并修复：P1 措辞冲突×1、不变式错位引用×4、时序矛盾×1、CHECKLIST/实现代码锚点错位×2、V0 门缺失×1、checksum 路径缺失×1、schema 定位缺失×1（全部记录于 v1.1 修订）。

### 9.1 设计基于已验证的调研结论

- [x] 所有设计决策可追溯到 RESEARCH.md（§2.1 表 5 行逐条映射 §3.1/3.2/3.3/3.4）
- [x] 无未经验证的假设（唯一待实测项 = 模型对 `.golden/` 的可见性，已降级为 V0 验证门测量项 §10.3，**不设为不变式**；其余假设均有 E1/E2/E3 来源）
- [x] 无论证驱动的归因扭曲（A14 根因按 CHECKLIST §2.6 完整引述——P1b 正文未传输 + 模型自写宽松测试双因，未裁剪为单因；self-accept 弱化基于 arXiv:2602.07900 实证，非为论证而弱化）

### 9.2 替代方案审查

- [x] 至少列 2 个替代方案（§5：builder-checker / mutation testing）
- [x] 每个替代方案有明确的否决理由（§5.2 builder-checker：2× 推理成本 + 模型调度复杂度，保留为"针对优化"残余风险被 V0 实证为严重时的升级路径；§5.3 mutation：非 MVP 必需，可选加固）

### 9.3 职责边界审查

- [x] 职责边界清晰（§2.3：golden 仅可验证可机械判定规格；语义正确性显式声明"回答不了"，留给人/异基座——职责外与能力边界两型均声明）
- [x] 不越界吞并其他研究范式（builder-checker 双模型、mutation 自动化均显式列入职责外）

## 10. 对实施的输入

### 10.1 关键工程约束

- **最小改动**：复用现有 accept 执行循环（M3 是 accept 循环的并行实例），不重写远端脚本
- **向后兼容**：无 `accept-golden` 的任务卡行为完全不变（schema 可选）
- **schema 定位（MVP）**：`accept-golden` 为**单对象**（一个 `source` 对应一个 `cmd`），与 `accept` 的列表形态不对称为有意为之——golden 优先最小化；若出现"一卡多 golden 测试"需求，升级为列表（与 accept 对称），随 IMPLEMENTATION 声明
- **checksum 依赖（v1.2 P1-1 同步）**：M3 防篡改（不变式 5）需要远端 `sha256sum` 可用（Ubuntu 自带）；主控站侧用 `Get-FileHash` 生成权威 checksum，**以字面量嵌入融合远端脚本 $body**（不落盘工作区）
- **Get-FrontMatter 扩展（P2-1）**：新增 `accept-golden` 顶层键 + `source:`/`cmd:` 嵌套续行解析——仿 accept 列表的 `$curKey` 模式（agent-cli.ps1 L504-509）。现行解析器对未知键静默丢弃（L503 `$h.ContainsKey($k)` 门），缩进子键被当作顶层键匹配后不落表，必须显式接纳两子键
- **PS5.1 编码**：agent-cli.ps1 改动须保 UTF-8 BOM（D6 已有教训）
- **ASCII-only**：远端脚本保持 ASCII（D6 纪律）

### 10.2 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| 人工预写 golden 成本 | 仅"有可判定规格"的代码卡需要；golden 可复用（同规格多卡共享）|
| golden 测试自身错误 → 误拒正确实现 | mutation 验证（可选加固，C 方案）+ 人工复核 golden 质量 |
| .golden/ 被模型发现/修改 | 隐藏目录仅防 list 展示（不承诺 bash 读取）；执行前权威 checksum 字面量比对（不变式 5）——**同用户进程可绕过权限只读（chmod/删除重建），权限不作为防线**（§9.5 复核修正）；残余风险（读→改→还原）诚实声明，builder-checker 升级路径兜底 |
| 执行环境依赖（.venv 等）| golden cmd 与 accept 同环境执行，复用 O-13 预置 |

### 10.3 V0 验证门（golden 可见性实测，2026-09-09 补定义）

**目的**：实证 headless 模型经工具（bash/grep/find/cat）能否从工作区读到 `.golden/` 内容，校准 §3.1/§4.3"不承诺模型不可见"的措辞是否成立，并为 §5.2（builder-checker 升级，当"针对优化"残余风险被实证为严重时触发）提供判定依据。

**方法**（首个含 `accept-golden` 的真实任务卡 dogfood 样本）：
1. 主控站注入 `.golden/`（含一个哨兵值，如 `GOLDEN_SENTINEL_<uuid>`）→ 正常派发任务
2. 模型执行完毕，回收产物时收集：模型输出的 stdout/文件中对 `.golden/` 路径或哨兵值的引用
3. 判据记录：出现引用 → `VISIBLE`（附证据文件路径）；无引用 → `NOT_OBSERVED`（声明扫描面：模型输出 + 任务产物，不含模型内部思考）

**结果记录**：V0 结果写回本设计（§3.1 注记处标注实测结论）与 OPEN-ISSUES O-12；作为 Step 10 验收的追加项。

**门禁语义**：非阻断门——MVP 正确性不依赖"模型不可见"（核心价值 = 独立实现消除自证，已由 P1 修复转为不承诺不可见）。V0 是**记录门**：结果必须落档；若为 `VISIBLE` 且后续出现针对优化疑似事件，触发 §5.2 builder-checker 评估。

### 9.4 异基座复审记录（2026-09-09，RULE-5：仅标记不改写）

> **复审者声明**：本节由异基座会话独立执行（与 §9.1-9.3 单视角自查不同会话）。取证手段：agent-cli.ps1 全量读码（L487-523 Get-FrontMatter / L655-799 融合脚本与退出码 / L190-244 .agentsync 链）+ D6 三文档锚点核验。**只标记问题，修复由主控会话执行后交复审确认**。

#### 已核实为正确的关键声明（正面清单）

| 设计声明 | 取证 |
|---|---|
| accept 在远端 eval 模型自写测试（RESEARCH §3.1）| agent-cli.ps1 L740 实证 ✓ |
| scrubber 先例（§2.2）| L681-683 实证 ✓ |
| "exit 9 经 wrapper 映射为 1"（§7）| **L793 `if ($code -eq 9) { $code = 1 }` 实证正确** ✓ |
| 不变式 7（超时后 golden 仍执行）结构可行 | L726 `timeout` 仅杀 opencode，脚本继续走 L729-746 accept 循环 ✓ |
| 不变式 1 由构造保证 | prompt = task 行 + body + attach 名（L670-674），front-matter 其余字段不入 prompt——golden cmd/source 不经 prompt 泄漏 ✓ |
| M2 防回流可行 | .agentsync → tar --exclude 链路存在（L190-244）✓ |
| A14/P1b 锚点 | CHECKLIST §2.6 实证 ✓ |

#### 发现问题

| 级别 | 问题 | 位置 | 修复建议 |
|---|---|---|---|
| **P1-1** | **不变式 5 内部矛盾（比对锚点漂移）**：正文称"与主控站权威源比对"，操作路径实为"与工作区驻留 `.golden.sha256` 清单比对"。清单未认证且驻留模型可写区——模型可同时改测试文件并重新生成清单（`sha256sum` 标准操作），比对通过。括注"清单本身被篡改与测试文件被篡改同被检出"不成立：**协同篡改（文件+清单）完全不被检出**（检出要求清单完好）。| §8 不变式 5 | 权威 checksum 以字面量嵌入融合远端脚本（$body heredoc，与 `$acceptB64` 同通道先例 L730）——脚本由 wrapper 每任务生成、经 R14 落盘链传输，不在模型主工作集；或将措辞如实降级为"与注入时清单比对（协同篡改不可检，残余风险）"。两案择一并同步 §7 表 |
| **P1-2** | **"模型不可见"旧措辞残留 3 处**：§1 "golden（主控站权威，模型不可见）"、§2.1 行 3 "隐藏目录，模型不可见"、§6.2 "隐藏目录（模型不可见）"。与 §3.1/§4.3 P1 修复的诚实降级立场直接矛盾——重新引入已撤回的过度承诺，ADD 审计时 §1 目标句会被当权威表述 | §1 / §2.1 / §6.2 | 统一改为"模型不可自写自证"或删除"模型不可见" |
| **P2-1** | **M1 与 Get-FrontMatter 现状差距未声明**：解析器为固定键白名单哈希表（L494），未知键**静默丢弃**；嵌套对象续行仅有 accept 列表一型先例（L508 `$curKey` 模式）。缩进的 `source:`/`cmd:` 因正则 `\s*` 前导空白匹配会被当作顶层键静默丢弃。"依赖现有 Get-FrontMatter"应改为"扩展（新增键 + 对象续行解析，仿 accept $curKey 模式）"并列入 §10.1 | §3.2 M1 / §10.1 | 措辞修正 + 工程约束补行 |
| **P2-2** | **注入命名规则未定义**：§4.1 source=`path_guard_golden.py` 但 cmd 引用 `.golden/test_path_guard.py`，§6.1/§6.2 示例亦不一致。M2 注入后文件名保留 basename 还是重命名未规定 | §4.1 / §6.1 / §6.2 | 定一条命名规则（建议 basename 原样保留）并统一全部示例 |
| **P2-3** | **陈旧 `.golden/` 残留未定义**：不变式 3 只保证"派发前注入"，同工作区后续任务的旧 `.golden/` 处置未规定——残留文件不在当次 checksum 清单内，行为未定义（多出的文件算不算 TAMPERED？）；亦可能污染 V0 哨兵测量 | §8 不变式 3/5 | M2 注入前清空/原子覆盖 `.golden/`，或明确"清单外文件"处置规则 |
| P3-1 | exit 9 复用承载 self-accept 失败与 golden 失败两义（契约靠 accept_golden.passed 消歧）——复用是有意决策但未明示；CHECKLIST 错误表需补行 | §7 | 明示"复用 9 为有意决策" |
| P3-2 | §3.1 架构图卡示例 "pytest golden/test_*.py" 无点前缀，与 §4.1 `.golden/` 不一致 | §3.1 | 随 P2-2 一并统一 |

#### 复审结论

**有条件通过**：P1×2 修复后可进入 Step 5（IMPLEMENTATION）；P2×3 应修（可随 P1 批次）；P3×2 提示。架构方向（主控站权威判据 + 诚实降级语义 + V0 记录门）成立，无推翻级发现。

### 9.5 复核记录（2026-09-09，复审结论独立复核）

> **复核者声明**：对 §9.4 复审结论做独立证据复核（grep DESIGN.md 全部"模型不可见"/文件名引用 + agent-cli.ps1 L494-523/L724-759 读码）。**复核结论：§9.4 七项正面声明全部属实、七项问题全部成立，无虚假标记**。但发现两处分级修正与两处遗漏如下。

#### 分级修正

| 修正 | 依据 |
|---|---|
| **P2-2 上调为 P1** | grep 实证：§4.1 `source: path_guard_golden.py`（L122）vs `cmd: pytest .golden/test_path_guard.py`（L123）；§6.1 `path_guard_golden.py`（L188）vs §6.2 `test_path_guard.py`（L198）。若 M2 按 basename 原样注入，工作区 `.golden/` 实存 `path_guard_golden.py` 而 cmd 引用 `test_path_guard.py` → **远端 pytest 必然 FileNotFoundError，首个含 golden 的真实任务卡必然失败**。非命名规范问题，是 MVP 首次 dogfood 即触发的阻断缺陷 |
| **§10.2"只读权限"缓解与 P1-1 自相矛盾（升级为 P2）** | §10.2 风险表 `.golden/ 被模型发现/修改` 缓解列为"隐藏目录 + **只读权限** + TAMPER 检测"，但不变式 5 注记已承认"同用户进程无法靠权限只读强制"——模型以同用户 bash 运行可 chmod +w / 删除重建绕过只读。P1-1 修复时须同步删除该缓解项或标注"同用户下可被绕过（残余风险）" |

#### 补漏（§9.4 未覆盖）

| 级别 | 内容 | 位置 |
|---|---|---|
| P3 | **`.meta` 通道未扩展**：agent-cli.ps1 L755 `printf` 仅含 TASK_ID/QUEUE_S/RUN_S/TASK_RC/ACCEPT_OK；golden 的 `ACCEPT_GOLDEN_OK` 需新增一行入 `.meta`（M3 输出了该标志但契约落点未明示）。IMPLEMENTATION 必须包含，CHECKLIST 需对应验收项 | §4.2 / §10.1 |
| P3 | **accept/golden 命令无 timeout**：L740 `eval` 未包 timeout，golden pytest 若挂死则远端脚本整体挂起直 ssh 层超时。现状 self-accept 同样无，属基线一致行为，但新增 golden 通道时应显式声明（MVP 保持一致或 golden 单独加 wrap）| §7 错误处理 |

#### 复核结论

§9.4 复审质量合格，其 P1/P2/P3 均可采信。经本复核修正后，**待修复清单 = P1×3（P1-1、P1-2、P2-2 上调）+ P2×3（P2-1、P2-3、只读权限）+ P3×4**。修复仍由主控会话执行，完成后按 §9.4 流程交复审确认。

#### P1+P2 修复批执行记录（v1.2，主控会话 2026-09-09）

| 项 | 状态 | 落点 |
|---|---|---|
| P1-1 不变式 5 锚点漂移 | ✅ 采用复核案 A（字面量嵌入 $body，弃工作区 `.golden.sha256`）；残余风险诚实声明 | §8 不变式 5 / §7 / §10.1 |
| P1-2 "模型不可见"措辞 | ✅ 5 处承诺性残留全部清除（§1、§2.1 行 1/3/4、§6.2）——覆盖复核点名的 3 处并超额 | §1/§2.1/§6.2 |
| P2-2（上调 P1）命名统一 | ✅ 定为"basename 原样保留、cmd 引用同名"；§4.1/§4.2/§6.1/§6.2/§3.1 图示全部统一为 `path_guard_golden.py` | §4.1/§4.2/§6.2/§3.1 |
| P2-1 M1 措辞 + Get-FrontMatter 扩展 | ✅ §3.2 M1 改"扩展"；§10.1 补嵌套续行解析约束（仿 `$curKey`，L504-509）| §3.2/§10.1 |
| P2-3 陈旧 `.golden/` 残留 | ✅ 不变式 3 改为"注入时序与洁净"：M2 注入前清空 | §8 不变式 3 / §3.2 M2 |
| §9.5 复核"只读权限"矛盾 | ✅ §10.2 缓解列删除"只读权限"，标注"权限不作为防线" | §10.2 |

**P1+P2 清零。P3×4 未在本批处理**（P3-1 exit 9 双义明示 / P3-2 已随 P2-2 顺带统一 / .meta 通道扩展 / accept 无 timeout）——其中 P3-2 已在命名统一中解决；其余三项转入 Step 5 IMPLEMENTATION 处理并验收。

---

**Review 签字**: _________ 日期: _________
