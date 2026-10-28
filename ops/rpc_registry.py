#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""断言清单 `CHECKS` 的唯一填充点（review-p2-split 8B-3）。

为什么单独一层：`CHECKS` 是 `rpc_common` 里的**共享可变列表**（域模块要读它，
又不能反向 import 门面）；把 455 行字面量留在门面会让「门面 ≤500 行」落空。
⚠ 填充必须**幂等**（`if not CHECKS:`）—— 脚本方式跑时模块名是 `__main__`，
`cluster.py` 等再 `import rpc_check` 会执行第二遍模块体（8B-2 实测 52→104）。
"""
from rpc_common import CHECKS
from rpc_protocol import (
    U1_PREFIX, U1_TRUNC, check_dialect, check_edges, check_id_census, check_id_storage,
    check_input_provenance, check_projects, check_promotion, check_u1_identity,
)
from rpc_docs import (
    check_adr, check_derived_view, check_determinism, check_doc_status, check_doclinks,
    check_executor_trace, check_ledger_status, check_md_tables, check_model_families,
    check_spec_untested,
)
from rpc_d6 import (
    check_capability_inventory, check_conclusion_ledger, check_evidence, check_inbox,
    check_interruption, check_memory_gates, check_mirror, check_multi_round, check_ps1_golden,
    check_ps1_runstamp, check_py_tests, check_review_catalog, check_rubric_blindspot,
)
from rpc_governance import (
    check_artifacts, check_cluster_deps, check_facade, check_inventory, check_scripts,
    check_secrets, check_sensitivity, check_shell_strict, check_station_layout, check_syntax,
)
from rpc_stations import (
    check_aliases, check_backend, check_engine, check_gates, check_halogen_assets, check_impact,
    check_models, check_plugins, check_ports, check_stations, check_usb4,
)

if not CHECKS:
    CHECKS.extend([
    {"id": "secrets", "title": "明文扫描", "fn": check_secrets, "quick": True,
     "fix": "删除明文密钥, 或加入 SECRET_ALLOW 并写明原因(不允许静默放行); "
            "文档里引用样串/占位串时**掩码为 sk-xxx-****** (2026-09-16 增: 未掩码的样串会命中本判据); "
            "⚠ 报『豁免未命中 N』= 那条白名单**已不再需要** ⇒ **把它从 SECRET_ALLOW 删掉**（D6-P0-2 防腐化）"},
    {"id": "syntax", "title": "语法检查", "fn": check_syntax, "quick": True,
     "fix": "按明细里的行号修语法; 扩展名与内容不符的应解包或改名"},
    {"id": "scripts", "title": "脚本治理", "fn": check_scripts, "quick": True,
     "fix": "管理操作请走统一入口 (ops/cluster.py <sub> / web 卡片), 不要新增一次性脚本; "
            "确需独立脚本则在 inventory/ops.yaml 登记并在提交信息里说明理由 (ADR-0004)"},
    {"id": "shell-strict", "title": "站上 shell 严格模式", "fn": check_shell_strict, "quick": True,
     "fix": "review-p2-big #5：把 prologue 改成 `set -euo pipefail`，并给『业务上容忍失败』的命令补显式守卫"
            "（逻辑或短路 / `if !` / 取值兜底）；被 `source` 的库不得改调用方选项；"
            "确需豁免（如报告型门禁 `load-gate`）⇒ 在 `inventory/ops.yaml` 的 `shell_strict.allow` 登记 why。"
            "⚠ 报『豁免未命中』= 该文件已变严格 ⇒ **删掉那条豁免**（防腐化）"},
    {"id": "station-layout", "title": "station-bin 布局", "fn": check_station_layout, "quick": True,
     "fix": "review-p2-big #8A：`ops/station-bin/` 根目录只放部署件 / 入口运行时件 / 在跑夹具；"
            "一次性 `_*` 探针请 `git mv` 到 `archive/station-bin-probes/`（不改内容），并从 "
            "`inventory/ops.yaml` 的 `frozen_ops_scripts` 删登记；确需在根目录新增 `_*` ⇒ 先改 "
            "`station_bin_layout.root_keep` 并说明理由；⚠ 报『白名单腐化』= 该文件已不存在 ⇒ 删掉白名单项"},
    {"id": "deps", "title": "cluster 模块依赖方向", "fn": check_cluster_deps, "quick": True,
     "fix": "P2-1: ① 新 `ops/cluster_*.py` 模块 ⇒ 必须在 `inventory/ops.yaml` 的 `cluster_layers` 登记层次; "
            "② 模块级 import 成环 ⇒ 拆环，或把其中一条改成**函数内懒加载**（并登记 `cluster_lazy_allow`）; "
            "③ 层序越界（反向/同层）⇒ 调整层次或改依赖方向（只允许依赖**严格下层**）; "
            "④ 反向懒加载未登记 ⇒ 登记原因，或调层; ⚠ 报『未命中登记 N』= 那条登记已可移除（删掉）"},
    {"id": "adr", "title": "ADR 替代方案节", "fn": check_adr, "quick": True,
     "fix": "P2-2: ADR 必须有 `## 考虑的替代方案（Alternatives Considered）` 节"
            "（模板: spec/vulkan-version-control/ADR_TEMPLATE.md），节体内**至少 1 个列表项 或 2 个表格行(表头+数据)**"
            " —— 要写「考虑过/否决了什么」，不是只写标题; **恰 1 个**（改名后别留旧节）; "
            "旧名 `否决/比较对象` / `被否的方案` 一律换规范名; "
            "⚠ 范围只含 adr/ADR-*.md —— DECISIONS.md 是表格载体（列在结构上已保证槽位、值可为 `—`），不在范围"},
    {"id": "model-families", "title": "模型家族表（双向对账）", "fn": check_model_families, "quick": True,
     "fix": "D7-P3-1 前置：`inventory/model-families.yaml` 的成员必须与 `inventory/models.yaml` 的 alias "
            "**双向对上** —— ① 成员不在 `models.yaml` ⇒ **孤儿引用**（删掉或改 alias）; "
            "② `models.yaml` 里的 alias **没被任何族收** ⇒ 按**权重血统**归族"
            "（蒸馏/微调**归基座族**，微调者记 `note`，**不改族**）; ③ 一族缺 `basis` ⇒ 补划分依据。"
            "⚠ 本判据**不判族分得对不对**（那要人读血统），只判「**没有一个 alias 没被归类**」与「引用不悬空」。"
            "⚠⚠ 它也**不提供**「站↔**已加载**模型」—— 那**不是** `models.yaml` 的 `stations`（库中有）"
            "或 `conf`（配过实例）; 见 yaml 的 `linked_state`（**未实测**）"},
    {"id": "ledger-status", "title": "台账状态可机读", "fn": check_ledger_status, "quick": True,
     "fix": "O-93: `spec/d6-agent-standard/OPEN-ISSUES.md` 的**每行**状态格必须**以标记开头**"
            "（`✅`=已闭环 · `◐`=已登记未处置 · `⏳`=待触发或待裁 · `🔵`=部分收口）——**允许加粗包裹**"
            "（如 `**✅ …**`，判据会先剥 `**`/`_`/空白）。"
            "\n\n⚠ **只认格首** ⇒ **引文里的 ✅ 不会被误当状态**（这正是「按整行找 ✅」那种口径会错的地方）。"
             "⚠ 状态格子**不在固定第几格**：本表列数不齐（表头声明 8 列、行有 6/8 格、另有行含裸竖线被拆），"
             "同一列在老行是状态、新行是证据 ⇒ 判据取「**第一个**格首带标记的格」。"
             "\n📊 note 里报出「数据行 N · 状态可机读 M · ✅ 闭环 X · **仍开着 Y**」，明细含**仍开着的 ID 清单** "
             "⇒ 排优先级**不再依赖人读**。"
             "\n⚠⚠ **它不判什么**：「应该闭环多少」**不判** —— 「开着」**不是错误**；也**不判**状态写得对不对"
             "（那仍要人读）。别把本判据读成「台账已被审计」。"
             "\n⚠ 若明细指出某行「状态不可机读」⇒ 给那行补一个格首标记即可（**不要**只改文案）。"},
    {"id": "spec-untested", "title": "规范类文档的未实测登记节", "fn": check_spec_untested, "quick": True,
     "fix": "O-91: **规范类文档**（`spec/d6-agent-standard/U[0-9]-*.md` 与 `D7-PROTOCOL-*.md`）必须带"
            "**非空**的 `## 未实测登记` 节 —— 形状与判据 `adr` 同源（锚精确节名 · **恰 1 个** · "
            "节体 **≥1 列表项 或 ≥2 表格行** · 扫描**只到下一个 H2**，故 `### 子节` 属节体）。"
            "① 缺节 ⇒ FAIL；② 多于 1 个 ⇒ FAIL；③ 只写标题没写内容 ⇒ FAIL；"
            "④ **命中集为 0 ⇒ FAIL**（判据**没有对象** = 退化空判，本仓头号形态）。"
            "\n\n⚠⚠ **它不判什么（别读过头）**：**不判**「正文里有没有无证据断言」—— 那**不可机判**，"
            "**仍然是纪律**。本判据只保证「**那一节在、且非空**」。"
            "\n📊 note 里附一条 **报数（不判）**：E 级内联标注的「带具体取证 / 裸」分布 —— "
            "实测 ADR 侧 **57% 是裸标**，而「裸」**不等于「错」**，且**连计数都口径敏感**"
            "（同一棵树两个正则数出 4 vs 8）⇒ 做成 FAIL 会造假红，假红 → 例外名单 → 判据失效。"
            "\n★★ **O-123（2026-09-30）新增第四件事**：本判据**顺带消费** `inventory/untested-index.yaml` 的分诊"
            "（该索引由此**不再是叶子节点**）—— **报数** state / blocker / needs_decision 分布；"
            "**一条判据**：任一条 `needs_decision: true` ⇒ **WARN**（口径 =「**未裁项不许静默**」）。"
            "⚠ 索引缺失/不可解析/`items` 为 0 ⇒ **WARN（非 FAIL）** —— 索引自身的对账与闭集校验由 `py-tests` 判，"
            "**不在此处重复判**（判据只在一处）。"
            "\n⚠ **逃逸（如实记）**：新规范若取名不带 `U\\d-` 前缀，本判据**看不到它** —— "
            "spec 与 adr 实测**全部无 front-matter**（无 `type:` 可锚）⇒ 靠「命中集在输出里可见」缓解。"},
    {"id": "doclinks", "title": "文档链接可达", "fn": check_doclinks, "quick": True,
     "fix": "资源移动/改名后, 文档里的相对链接要跟着改 (注意别写重前缀: spec/<x>/ 里是 "
            "`../y` 不是 `../spec/y`, 引 docs/ 是 `../../docs/z`); 确有不可修的登记 DOCLINK_ALLOW; "
            "⚠ 报『豁免未命中 N』= 那条例外**已不再需要** ⇒ **把它从 DOCLINK_ALLOW 删掉**（D6-P0-2 防腐化）"},
    {"id": "inventory", "title": "真值登记", "fn": check_inventory, "quick": True,
     "fix": "端口/模型标识有变更时同步 inventory/*.yaml 真值表"},
    {"id": "artifacts", "title": "生成物清单", "fn": check_artifacts, "quick": True,
     "fix": "生成物**禁止手工编辑** —— 改源头 → 重跑 → 跑 --check (D6-P1-1); "
            "清单每条须给 `check`(真实断言 id) 或 `exempt`(豁免理由), 两者都缺 = 静默缺口会 FAIL"},
    {"id": "sensitivity", "title": "内容档位真值表", "fn": check_sensitivity, "quick": True,
     "fix": "O-51: sensitivity.yaml 是「内容→档位」的真值(权威源在自身) —— 断言其自洽: "
            "① path 必须真实存在 ② tier 必须 ∈ 封闭枚举 ③ **同一 path 不得两处不同 tier** "
            "④ default_tier 必须为 local-only (fail-closed)"},
    # O-66 (2026-09-25): 卡面 `input-provenance` 义务的**机判** —— 此前只在文档里（`ops/` 全域零命中）。
    {"id": "input-provenance", "title": "卡面输入来源义务", "fn": check_input_provenance, "quick": True,
     "fix": "O-66: 卡声明 `attach-egress: ok` 且 `sensitivity` ∈ {public, sanitized} 时，它**要带附件出网** ⇒ "
            "按 `CROSS-PROJECT-WORK-STANDARD §4` 必填 `input-provenance`：① 逐项本仓相对路径；"
            "② 每项须在 `inventory/sensitivity.yaml` 有 `tier`；③ 卡档位**不得宽于**该项 tier。"
            "确无本仓输入 ⇒ **显式写 `input-provenance: none`**（不要留空；留空 = 缺字段 ⇒ FAIL）。"
            "⚠ 报『none 可证伪性存疑』= **WARN 不阻断**：声明 none 却在正文提到 tier 严于本卡的已登记路径 —— "
            "『提到』不等于『读到』，机械判不出 ⇒ 请人工核一次：若确实读了，把它列进 `input-provenance` 或降档。"},
    # D7-P1-1 (2026-09-26): U-2 证据强度字典 + 方言映射表 —— 映射表自己的两种病
    #   （**漏项** / **源词表改了而映射表没重抽**）。
    {"id": "dialect", "title": "U-2 方言字典与映射表", "fn": check_dialect, "quick": True,
     "fix": "D7-P1-1: `inventory/dialect.yaml` 是「符号 × 出处 → 含义」的投影（**权威源在别处** ⇒ "
            "已登记进 `inventory/artifacts.yaml`，**禁止手工编辑语义**：改源 → 重抽 → 重跑）。"
            "本项判四件事：① `axis` / `namespaces` 是封闭枚举与白名单，映射行的 `namespace` **必填**"
            "（§11.4 教训①：前缀不靠人自觉写）；② `axis=not-assigned` 必须写 `axis_note`（说明属于什么轴），"
            "`axis_value=undefined` 必须写理由（堵「看着像就填」）；"
            "③ `coverage` 逐族行数与实际**双向**相等（`b1b` 实测漏过一行）；"
            "④ `sources` 的**源切片指纹**不符 ⇒ 红（这就是「源词表变了下游红」）。"
            "⚠ 报「读取失败 ⇒ 不可判」= **要修**，不是通过 —— 判不了不许当通过"},
    # D7-P1-3 (2026-09-26): U-3 依赖边格式 —— 最该被机器盯住的是**最容易缺的那个字段**。
    {"id": "u1-identity", "title": "U-1 产物身份（可复算）", "fn": check_u1_identity, "quick": True,
     "fix": "D7-P1 实现侧（U-1 落地）：`inventory/*.yaml` 里声明了 `u1:` 的，**身份必须可复算**。"
            "① 声明四项 `{namespace, identifier, version, identity}` 必须齐（只写 identity **无法复算**）；"
            "② `identity` 必须 **等于** 按 `(namespace, identifier, version)` 复算的结果 —— "
            f"★ 只判格式是**假绿**（随手编一个合规长度的 hex 就能过）；'身份'可判的含义只有『能从 (ns,id,ver) 复算』；"
            f"③ 声明了身份 ⇒ 文件**前 5 行内必须有** `# {U1_PREFIX}` 头部注释行（D-25：前缀进头部注释、"
            "不进哈希行 —— 进了哈希行整份 `sha256sum -c` 会一行都不被验，一手实测见 U1 spec §1.4）；"
            "④ **一个声明都没有 ⇒ FAIL**（本条会静默退化成空判 = 本仓头号失败形态）。"
            "\n\n算法/截断的**唯一真值**在 `ops/rpc_check.py` 的 `u1_identity()`（门禁与产出方同源）；"
            "取值与理由见 `spec/d6-agent-standard/U1-ARTIFACT-IDENTITY.md`。"
            "⚠ 哈希不可逆 ⇒ 本条只能判『声明可复算』，**不能**判『某个文件内容变了 ⇒ 身份该不该变』（那是 U-4 的事）"},
    {"id": "id-census", "title": "ID 站点计数（口径可复算）", "fn": check_id_census, "quick": True,
     "fix": "O-85: `inventory/id-site-census.yaml` 是**唯一真值**，口径的**唯一实现**在 `ops/id_site_census.py`。"
            "① 数值不符 ⇒ 项目变了（正常）⇒ 跑 `py ops/id_site_census.py --emit` 重出真值，"
            "**并回头复核下游结论**（U4 spec §1 表引用了这些数）；"
            "② **口径漂移（正则 / glob / 排除目录 / 是否含测试）⇒ 比数值漂移严重** —— "
            "口径一变，真值里**所有**数字立刻失去意义 ⇒ 必须重出 + 复核；"
            "③ 项目目录不可达 ⇒ **WARN**（它们在 `F:` / `E:` 等**本机才有**的盘上，换机器就没有）"
            "—— ⚠ 但**绝不静默通过**：报告里显式写 `可达 N/M` 与逐项目 `--`（D-26）。"
            "\n\n★ 这条断言的**存在理由**：U4 §1 表原来那一列「计数」**没有口径** —— "
            "Open_Data 换四种口径实测得 12 / 14 / 117 / 139，而表里写的是 34 ⇒ **数字没有定义**。"
            "⚠ 它只回答『有多少处哈希用法』，**不回答**『哪些是产物 ID』（那是 U-4 的 `affected`，仍未解）。"},
    {"id": "id-storage", "title": "ID 存储面（affected 生产者）", "fn": check_id_storage, "quick": True,
     "fix": "U-4: `inventory/id-storage-census.yaml` 是**唯一真值**，口径的**唯一实现**在 `ops/id_storage_census.py`。"
            "① 数值不符 ⇒ 存储变了（正常）⇒ 跑 `py ops/id_storage_census.py --emit` 重出真值，"
            "**并回头复核 U-4 的 `affected`**；"
            "② ★★ **角色不实 ⇒ FAIL**：声明 `primary_key` 就必须**回库里核过**（duckdb 查 "
            "`duckdb_constraints()` · sqlite 查 `PRAGMA table_info`）—— 声明与实测不一致，说明这张表在**自说自话**；"
            "③ **口径漂移**（形态档 / 取样上限 / role 取值域）⇒ 比数值不符**优先**判红；"
            "④ 存储不可达 ⇒ **WARN 不 FAIL**（库在 `F:`/`E:` 等别的盘）—— 但报 `不可达 N/M`，**绝不静默通过**。"
            "\n\n★ **它是什么**：把 2026-09-26 那次『开库手工数 affected』（duckdb + sqlite）变成**可复算的机制**。"
            "`py ops/id_storage_census.py --invalidate --changed <带 u1: 声明的文件>` 会串起三段："
            "**changed_ids（取声明）→ affected（本普查实测）→ `decide_invalidation()` 的处置**。"
            "⚠ 它只产出**决策**，不执行重算（执行侧仍未实现 —— U4 未实测第 10 条）；"
            "⚠ `affected` 的完整性取决于 `STORES` 清单，而**清单是线索不是事实**（已吃过两次亏）。"},
    {"id": "edges", "title": "U-3 依赖边格式", "fn": check_edges, "quick": True,
     "fix": "D7-P1-3: `inventory/edges.yaml` 的**实例**要满足 `U3-EDGE-FORMAT.md`（形状的单一真值）："
            f"① `src`/`dst` 必须是 **U-1 产物身份**形态 `{U1_PREFIX}:<{U1_TRUNC} 位小写 hex>`"
            "（U-1 与 U-3 咬合：写一条边就得先有一个合规身份）——"
            "★ 判据由 `u1_parse()` 给出，与 U-1 实现**同源**（此前这里另写了一份正则 = 同一事实两个定义点）；"
            "③ `provenance` 必填，形式 `<前缀>:<载荷>`，前缀 ∈ `provenance_prefixes`，"
            "**载荷允许含 `:`**（只按第一个 `:` 切分）；"
            "★ 「缺」= 字段不存在 / 空串 / 仅空白 / `null` / `unknown`·`none`·`n/a`·`null` / 前缀不在封闭集 / 载荷为空"
            " ⇒ **该边无效** ⇒ **FAIL**（⚠ 产出方的处置是 FAIL，**不是「丢掉这条边继续」** —— "
            "依据 D-26「禁止静默 skip」；「丢弃 / 降级」是**消费方**那一侧的 H-3 规则）；"
            "④ `(src,dst,kind)` 不得重复；⑤ **`edges` 为空必须给 `empty_reason`** —— "
            "空 ≠ 没事，门禁会把「0 条」显式报出来"},
    # D7-P1-5 (2026-09-26): U-5 晋升门 schema —— 判的是**schema 自身 + 三处实现的映射**（对象真实存在）。
    {"id": "promotion", "title": "U-5 晋升门 schema", "fn": check_promotion, "quick": True,
     "fix": "D7-P1-5: `inventory/promotion.yaml` 是共享记忆**准入形状**的单一真值。"
            "① `gate.required` / `gate.capacity`（field+max+policy）/ `gate.criteria` / `gate.structure` 四件都要有；"
            "② 判据的 `field`/`ref` 只能引用 `fields` 里的字段，`op`/`policy` 是封闭枚举，`$ref` 类型须与 field 一致；"
            "★ ③ **D-38 要求三种判据并存**（`success_rate` / `recurrence` / `verified`）—— 缺一即『发明第四种』；"
            "★ ④ **映射闭包**：`mapping_closure` 里三处实现的 `uses`/`criteria_used` 必须覆盖 schema 的**全部**"
            "字段与判据 —— **出现孤儿字段/孤儿判据 = 有一处没人用，就是变相发明第四种**；"
            "⑤ `entries` 为空必须给 `empty_reason`；⑥ `unverified` 必须登记本 schema 里**新设**的项"},
    {"id": "facade", "title": "门面符号可达性", "fn": check_facade, "quick": True,
     "fix": "P1-3: `cluster.py` 是统一门面, `cluster_web.py` 以 `import cluster` 复用其符号 —— "
            "缺符号即 FAIL 并点名『哪个符号·被谁引用』; 修法: 在 cluster.py 重导出(或改回引用处)"},
    {"id": "mirror", "title": "事实源↔镜像一致", "fn": check_mirror, "quick": True,
     "fix": "P1-2: ① M-1 手册 §1.3 判官行须与 `JUDGE_TABLE['main']` 的 id/egress/compliance 三项一致; "
            "② M-5/M-6 受理状态机真值(`inventory/inbox.yaml`)须与 inbox/README §3 白名单/状态表一致, "
            "且 `cluster_web.py`/`rpc_check.py` 消费同一真值(不得回归硬编码); "
            "③ #7/#9 真值的 `requires`(必需件)须齐全, 手册 §1.3 状态机段须逐个提到真值状态, "
            "README §5.3『交付态强判据』行须 == 真值 `manifest` 集 —— "
            "**改状态/必需件只改 `inventory/inbox.yaml` 一处**, 文档跟着改; "
            "④ O-50 手册声明的断言计数须 == 真实 `CHECKS`（**加/删断言后同步手册 §2.4 的 "
            "`# N 项断言 (quick Q + 全量 R)`**）; 手册**禁**再写『真实剩余 open = N 项』枚举或写死『门禁 N 绿』; "
            "⚠ M-2 已被 O-50 判为『不再维护第二份枚举』故不并入"},
    {"id": "ports", "title": "端口分配表自洽", "fn": check_ports, "quick": True,
     "fix": "按明细修 inventory/ports.yaml (缺字段/同组重复/跨组重叠/枚举拼错)"},
    {"id": "plugins", "title": "插件同构基线", "fn": check_plugins, "quick": True,
     "fix": "改插件/技能后同步 inventory/plugins.yaml; 无法立即修的真实差异登记 known_drift"},
    {"id": "impact", "title": "影响面反查", "fn": check_impact, "quick": True,
     "fix": "impact.yaml 登记的 consumer 路径不存在 —— 修正路径或删掉该条"},
    {"id": "aliases", "title": "别名解析契约", "fn": check_aliases, "quick": True,
     "fix": "以站上 conf 为准改 cluster.py 的 ROUTE/RPC_MODELS/STATION_ROUTES"},
    {"id": "evidence", "title": "agent 证据链", "fn": check_evidence, "quick": True,
     "fix": "digest/链/锚不符 = 归档证据或链被改动 ⇒ FAIL —— 用 `cluster.py agent verify` 定位到条与件, "
            "再追查改动来源(别急着 `--reanchor`, 那是把信号抹平); 有 run 未入链只是**覆盖缺口** ⇒ WARN, "
            "跑 `cluster.py agent chain` 补录(钩子已自动入链, 出现未入链说明钩子没跑或被 --no-verify 绕过); "
            "「可重放性审计: 新增 N 条」= **增量**可重放性缺口(同属覆盖缺口 ⇒ WARN, 刻意不进 FAIL 集) "
            "⇒ 先看逐条明细, **确认可接受**后跑 `cluster.py agent audit --accept` 推进水印(存量即不再重复报); "
            "若明细里是「已归档但未被任何 subject 覆盖」= 新证据件没进产出方基线 ⇒ 应改 "
            "`ops/station-bin/agent-cli.ps1` 的 `Get-FrameworkSubjects`(清单唯一真值在那里), 而不是接受它; "
            "「judge 校准已过期」= 判据(A/B)或稳定题集改过、校准报告没重跑 ⇒ 跑 "
            "`cluster.py agent audit-judge --save`(需站上在服务跨家族引擎)。这条把"
            "「改判据必须重跑校准」从**空头承诺**变成可判——报告自带 calib 指纹, 比对即可"},
    {"id": "inbox", "title": "受理区状态自洽", "fn": check_inbox, "quick": True,
     "fix": "按明细修: 缺 00_handoff/ = 转运包没冻结; STATE.json 缺失/非法/不在白名单 = 状态没走机读格式; "
            "状态内容不自洽(如 accepted 无受理决定) = 先补 10_admin/受理决定.md 再改状态 "
            "(依据 inbox/README §3 状态机, ADR-0008; 状态只由管理员改, 每次变更追加 40_state/LOG.md); "
            "★ **MANIFEST.sha256 重算不符 = 交付证据束被手改或源被改动**（生成物**禁手改**）⇒ "
            "**别去改清单**，走「改源头 → 重跑 → `cluster.py inbox seal <proj-dir> --go`」；"
            "核对用 `cluster.py inbox seal <proj-dir> --check`（与门禁同一实现）；"
            "报『MANIFEST 未校验 N』= 清单头写的项目根**不在本机**（换 clone/换机），不是篡改"},
    {"id": "ps1-golden", "title": "ps1 离线黄金夹具", "fn": check_ps1_golden, "quick": True,
     "fix": "P3-2: 跑 `powershell -NoProfile -ExecutionPolicy Bypass -File ops/station-bin/_fm_golden_test.ps1` "
            "看明细里的 FAIL 行。⚠ **先判「是回归还是夹具期望值陈旧」**："
            "若代码侧确有语义变更（看 agent-cli.ps1 里的注释/新件/O- 台账）⇒ 改**夹具期望值**并写明理由；"
            "若代码侧无变更 ⇒ **是回归**，改代码。⚠ 出站硬闸的判据本体在夹具里，本断言只负责让它**每次都被跑**"},
    # ── D7-P3-2 (2026-09-26): 编排层的两条判据（防 D7 变瓶颈 / 不新造账本）────────
    {"id": "conclusion-ledger", "title": "账本唯一性（不新造账本）", "fn": check_conclusion_ledger, "quick": True,
     "fix": "D7-P3-2『结论收束记账』：合并稿 §13.3 要求 D7 的结论留痕**复用既有追加式纪律、不新造账本**。"
            "`inventory/conclusion-ledgers.yaml` 是**账本的封闭集**（口径 = 只追加 ∧ 唯一写入者 ∧ 有独立校验）。"
            "① 报『**未登记的账本** <路径>』⇒ 有人在扫描口径内新造了一本 ⇒ **要么登记**，"
            "**要么把 `scan.globs` 口径说清**（口径不先定就量 = 本仓已吃过三次亏）；"
            "② 报『登记了 globs 却一条也没命中』= **登记腐化**（账本被删 / 改名 / glob 写错）；"
            "③ 报『登记的路径不存在』同②（`paths` 那一半）；"
            "④ 报『`not_a_ledger` 为空』= **没写下「什么不算账本」** ⇒ 下一个人会按『看着像』再建一本；"
            "⑤ 报『相撞』= 同一形态既登记为账本、又被声明不是账本（两处口径矛盾）；"
            "⑥ 报『扫描失败 ⇒ 不可判』= **要修**，不是通过。"
            "⚠ **它不判什么**：**不判账本内容**对不对，也**不判**『结论该不该进账本』（后者是纪律）。"
            "⚠ 扫描口径**窄**（只 `inbox/*/40_state/LOG.md`）⇒ **别名账本看不到**，"
            "这点已如实写在 yaml 的 `unverified` 里 —— 别把本项读成『账本已全覆盖』"},
    {"id": "review-catalog", "title": "标准复核目录（免终裁类目）", "fn": check_review_catalog, "quick": True,
     "fix": "D7-P3-2 / D-43：`inventory/review-catalog.yaml` 是**免终裁类目的清单**。"
            "① 准入门槛照抄 ITIL（**同一类被批准两次**）—— 报『`approvals` 未达门槛』或"
            "『`approval_anchors` 条数 ≠ `approvals`』= **只填数字拿不出锚点**（门槛没被真满足）；"
            "② 报『有类目但 `type_axis` 为空』= **类目没有浮出依据**（没有轴就没有『类』）；"
            "③ 报『孤儿字段』= `fields` 里有 `required` 没用的字段（装饰）；"
            "④ `entries` 为空**必须**给 `empty_reason` —— **空 ≠ 没事**，门禁会把「0 条」报出来；"
            "⑤ `ratio_target.judged` 标明这条目标是**判**还是**只报数**。"
            "⚠ **它不判什么**：**不判**类目选得对不对（那是人读血统 / 风险），"
            "也**不判**『该不该引入豁免』（D-48 要求先证它与结构 contain 不冲突）。"
            "⚠ 当前 `entries` **实测 0 条**（理由在 `empty_reason`，两条独立实测）——"
            "**别把本项读成『已有免终裁通道』**"},
    {"id": "memory-gates", "title": "记忆四道门 + 授权边界", "fn": check_memory_gates, "quick": True,
     "fix": "D7-P3-3 / D-47 / D-48：`inventory/memory-gates.yaml` 是**四道门**"
            "（write/retrieval/promotion/reuse）与**授权边界（结构性约束）**的单一真值。"
            "① 报『缺一道门』= D-47 要求四门齐；"
            "② 报『挂名假判』= 某门的 `judgment.ref` 指向一个**不存在**的 CHECKS id"
            "（判据写了但没人跑 —— 本仓最典型的一类假绿）；"
            "③ 报『`gate: none` 且本仓可控 ⇒ 红』= **私有→共享那一跳敞着**"
            "（MAPLE-Guard 点名的关键一跳）；**引擎侧**关不掉的无门通道只**点名 + WARN**（绝不静默）；"
            "④ 报『未登记的记忆面接触点』= 有代码新碰了记忆路径 ⇒ **要么登记**（写清为什么）**要么去掉**；"
            "⑤ 报『记忆出网嫌疑』= 同一行同现【记忆路径】与【跨机搬运令牌】（本模型里最贵的错误）；"
            "⑥ 报『隔离靠文本前缀』= 有人把**命名**升格成了**判据**（D-48：要靠结构 contain）；"
            "⑦ 报『登记的接触点不存在』= 登记腐化。"
            "⚠ 记忆路径的**唯一字面定义点**在 yaml 的 `egress.path_tokens`（角色名 → 路径）；"
            "改路径**只改那里**，不要在代码里再抄一份（本仓头号失败形态）。"
            "⚠ **它不判什么**：不判记忆**内容**，也**验不了门的效力** —— "
            "MAPLE-Guard 的 ASR 下降是**它自己的实验**，本仓没有投毒实验台 ⇒ "
            "**别把本项读成「记忆已安全」**"},
    {"id": "multi-round", "title": "多轮闭环 + 轮数上限", "fn": check_multi_round, "quick": True,
     "fix": "D7-P4-1（退出判据原文：多轮闭环可跑；**轮数上限有判据**）："
            "`inventory/multi-round.yaml` 是本仓**真实存在的重复执行闭环**的单一真值"
            "（★ 受理侧的协商回环**早就有**，路线总表 §11.2(a) 已裁「复用状态语义、不另建」）。"
            "① 报『`cap_state` 不在封闭集』= **漏写上限** —— 上限 / 无上限的理由 / 待谁裁，"
            "**三者必须显式其一**（不许靠「没写就是没有」）；"
            "② 报『`max_rounds` 与代码不符』= 真值表与 `agent-cli.ps1` **实提取**的上限不一致 "
            "⇒ 改真值表**或**改代码；"
            "③ ★★ 报『**未登记的散文上限**』或『散文上限与登记不符』= **注释里的上限落后于代码** —— "
            "本批实测**两处**都写 2 而代码是 3（O-46 改 cap 时注释没跟）；"
            "散文里的上限**逐处登记**，否则它会悄悄骗人；"
            "④ 报『缺 `stop_on_agreement`』= **正向终止条件**没写 —— 上限只管最多几轮，"
            "『什么时候可以停』是另一半（EASE 早停）；"
            "⑤ 报『`on_exceed_kind` 不在封闭集』= **超限时发生什么**必须是一个可枚举的动作"
             "（`escalate` / `terminate` / `fail-record`）—— 且已有上限却留 `undecided` ⇒ 上限只有一半；"
            "⑥ 报『`plus_extra` 锚点找不到』= 那段代码改了/删了（登记腐化）；"
            "⑦ 报『上限未定的闭环 …（待裁，点名）』= **WARN 不阻断**："
            "已如实登记、等裁定 ⇒ 但**点名在案，不许静默**。"
            "⚠ **它不判什么**：不判「多轮**跑通**了没有」—— 只验**上限与终止条件被写明**；"
            "`agent-resume` 的续接链与受理侧回环**本轮均未端到端实跑**（见 yaml 的 `unverified`）"},
    {"id": "interruption-untrusted", "title": "中断态两岸口径 + 不可信证据",
     "fn": check_interruption, "quick": True,
     "fix": "D7-P4-2（Ds 简报 11 / 18）：`inventory/interruption-and-untrusted.yaml` 是单一真值。"
            "① 报『缺 `main_side` / `station_side`』= **只有一端声明了口径** —— "
            "Ds 实测的死锁就出在「一端等待、一端失败」；两岸**都要**写；"
            "② 报『判出死锁风险却**没有 `mitigation`**』= 那个等待**没人管怎么终结** —— "
            "★ 注意：**风险由门禁算，不由你填**（自报 = 同一事实两个定义点）；"
            "③ ★★ 报『**规则算不出这条真事故**』= `history` 里那条已修死锁，按当前两岸动作"
            "**算不出非 none** ⇒ **判据是空转的**，先修 `deadlock_risk()` 的规则；"
            "④ 报『护栏是空头的』= 已修事故写的 `regression_guard` 在夹具/测试里**找不到**；"
            "⑤ ★★ 报『**自报不算声明**』= 某条不可信输入声称已在某文件里声明，"
            "但**那个文件里真找不到**该 marker（第 18 条落空）；"
            "⑥ 报『`declared: false` 却缺 `why_not`』= **「没声明」也要给理由**；"
            "⑦ 报『`trusted_inputs` 为空』= **什么不算不可信**没写，边界靠猜。"
            "⚠ **它不判什么**：只能核那句声明**在不在**，**判不了模型是否真遵守**；"
            "也**不做注入实验**（本仓没有实验台）⇒ **别读成「注入已防住」**。"
            "⚠ `interruptions` 只有 3 条 —— **不是穷举**（ssh 不可达 / 站断电等未登记）"},
    {"id": "rubric-blindspot", "title": "rubric 纪律 + 自环盲区登记",
     "fn": check_rubric_blindspot, "quick": True,
     "fix": "D7-P4-3（Ds 简报 15 / 12 / 21）：`inventory/rubric-and-blindspots.yaml` 是单一真值。"
            "① 报『rubric 里**找不到**必含句』= 某条**裁判纪律被人删了/改了措辞**"
            "（rubric 是纯文本资源，删一句没人知道）⇒ 补回来，或**同步改真值表**；"
            "② ★ 报『找不到 `ReadAllText`』= rubric/tmpl 的**读取退回了裸 `Get-Content`** —— "
            "PS 5.1 默认按 ANSI 读 ⇒ **中文资源会乱码**（本仓那条『UTF-8(BOM) 铁律』"
            "实际是靠**显式编码**兜住的）；"
            "③ 报『缺 `impl-same-source`』= **本仓最实质的盲区没登记**：三站互审走**同一份 "
            "`agent-cli.ps1`** ⇒ 实现层缺陷两侧同时出现，互审**结构上发现不了**；"
            "④ 报『缺 `why_blind`』= 没说清**为什么互审看不见**（那就不叫盲区登记，叫感想）；"
            "⑤ 报『`other_guard` 是 `na` 但缺 `why`』= **「没有替代机制」也要给理由**；"
            "⑥ 报『`derived_edges` 是 `deferred` 但缺 `condition`』= 触发条件没写死 ⇒ "
            "它会**永远挂着或悄悄做掉**。"
            "⚠ **它不判什么**：只核那几句**在不在**，**不判 rubric 全文写得好不好**（纯文本，语义不可机判）；"
            "盲区清单**不是穷举**；`derived_edges` 的触发条件是**跨仓事件**，本仓判不了"},
    # O-105 (2026-09-27): 能力盘点表 —— 动机 = "能力的存在性每次都要靠问一遍"
    #   （实测散落在 4 份调研正文里）⇒ 收成一张**可机核**的表；形态借自姊妹仓 P-050 RESEARCH §3.7。
    {"id": "capabilities", "title": "能力盘点（能力 → 载体 → 判定）",
     "fn": check_capability_inventory, "quick": True,
     "fix": "O-105：`inventory/capability-inventory.yaml` 是**能力层**的单一真值"
            "（与 ports/models/plugins 那类**事实**真值表分工不同：本表只**引用**它们，不复制事实）。"
            "① 报『缺 `metric` / `updated`』= **增长型计数没有口径或读数日期** —— "
            "口径一变，表里所有数字立刻失去意义（§87.6 的『同日漂移』就是这类失败）；"
            "② ★ 报『`carriers` 指的判据**不是已注册 CHECKS id**』= **挂名**"
            "（判据写了但没人跑 —— 本仓最典型的一类假绿）；"
            "③ 报『`carriers` 指的文件 / 真值表不存在』= **载体已腐化** ⇒ 改登记或补文件；"
            "④ 报『partial 缺 `gap`』= **缺哪一块没写清**（否则 partial 是个托词，"
            "读者无法判断它离 present 差多少）；"
            "⑤ ★ 报『absent 缺 `why`，或 `why_kind` 不在封闭集』= "
            "**「不做」也是一种结论，必须写下来**（不适用 / 未做 / 待裁 —— 三者含义不同）；"
            "⑥ 报『`self_id` 不在 items 里』= **「能力盘点」这项能力本身没被盘点**（自指缺口）；"
            "⑦ 报『声明的封闭集与判据实现不一致』= 改了代码没改表（或反之）"
            "⇒ **那时本判据自己就是假绿**。"
            "⚠ **它不判什么**：只保证「**有载体且可达**」，**不保证「载体真的管用」**"
            "（效力未被任何实验测过）；`verdict` 与 `gap` / `why` 均为**人工判断**且未经第二方复核；"
            "★ 「**漏了哪项能力**」**不可判** —— 没有权威清单可比对，只能靠新增时补"},
    # O-108 (2026-09-27): 文档状态声明的**两处位点** —— 动机 = `O-106` 落体时发现：
    #   同一文档在 front matter 与正文各写一份状态，**实例 12 处两处不等**（含 `draft` ↔ `verified`）。
    {"id": "doc-status", "title": "文档状态两处声明（判派生过期）",
     "fn": check_doc_status, "quick": True,
     "fix": "O-108：`inventory/doc-status.yaml` 是**两处状态声明**的单一真值"
            "（`semantics` 声明「谁是真值、谁是派生」；`freeze` 只装**存量**）。"
            "① ★ 报『两处不等』= **判为「派生过期」** ⇒ **先确认真值**：若取证显示 **fm 陈旧**，"
            "**先更新 fm**（那是真值更新）再让正文跟上；**稳态下**修法唯一 = **改正文行**"
            "（别改 fm 去迁就正文 —— 一改，那个面就变回「两处都可写」= 被 I-10 禁的形态）；"
            "② 报『冻结项**已自愈** / 已不再是两处都有』= **从 `freeze` 删掉**"
            "（防腐化 —— 同 `secrets` 的「豁免未命中」、`ops.yaml` 的冻结存量）；"
            "③ 报『缺 `semantics.single_write` / `derived`』= 本表**退化成一张豁免清单**了"
            "（没声明谁是真值，就只剩「不许红」这一个作用）；"
            "④ 报『`file` 不在仓里 / 缺 `why`』= 登记腐化 / **冻结没写理由**。"
            "⚠ **它不判什么**：① 它**验不了**「人是否只改 fm」（只能检出两处**不一致**）——"
            "**这正是 I-10 说的「检不出两处一致地错」**；② ★ **本面仍是两个位点** ⇒ "
            "本项是**降格处置**、**非 I-10 的完全实现**（彻底消除 = O-108 案①：只留 front matter）；"
            "③ **词表符合性**见 ⑤（O-109 起并入本项）；"
            "④ 射程**只到文档头 20 行**（口径写死在 `DOC_STATUS_HEAD`，§90.4 的教训）；"
            "⑤ ★ O-109（**第二段判据：词表符合性，按档**）：`inventory/doc-status.yaml` 的 `kind_source`"
            "登记「档 → 词表读取位点」—— 有模板档（design / checklist / adr）真值**在模板链**、"
            "无模板档（ledger / process）**在 yaml**；`kinds` 只登记无模板档的归属，判档按 `kind_rule`。"
            "报『token **不在档内**』= 该位点写了**词表外**的值 ⇒ 改回档内词（词表见报错列的集合）；"
            "报『**词表缺档**』= `kind_source.by_kind` 少了一档 ⇒ 补档（无模板档要同时补 `kinds` 归属）。"
            "⚠ **它只判 token 在不在档内**，**不判**「这个状态对不对」（状态位的**语义**对不对要人读）；"
            "★ **模板文件跳过**（`*_TEMPLATE.md` 的「状态」行是**词表本身**，不是实例值）"},
    {"id": "md-tables", "title": "md 表格列数守恒（防拆错格）",
     "fn": check_md_tables, "quick": True,
     "fix": "A4（2026-09-29）：同一张 markdown 表里 **分隔行 / 数据行** 的**格数**必须 == **表头**格数。"
            "报『**某行 N 格 ≠ 表头 M 格**』= 该行**被拆错格**（字段错位）—— 最常见的原因是"
            "**单元格文本里的竖线没转义**：写成**反斜杠 + 竖线**（`\\|`）即可；"
            "整行少/多一格（比如漏了个 `|`）⇒ 补齐。"
            "★ 口径（**唯一实现** = `md_table_scan`）：① **空单元格计入**格数；"
            "② 分隔行必须**紧邻**表头（不跨行找表）；③ 代码围栏（``` / ~~~）与 GFM 缩进码块**跳过**；"
            "④ 单元格里的转义竖线**不算分隔**。"
            "📊 note 报 `扫描 N 篇 · 表 T 张 · 违规 V（冻结 F · 新增 D）`；"
            "`表 0 张 ⇒ FAIL`（判据**无对象** = 退化空判，故「整篇没表 ⇒ 空集恒真」这种假绿被堵住）。"
            "⚠ 报『冻结条目**失配** / 指向**已不存在**的文件』= **从 `inventory/md-tables.yaml` 删掉对应条目**"
            "（冻结**只减不增** —— 修好了就清账，留着会烂成垃圾桶；同 `secrets` 的「豁免未命中」防腐化）；"
            "存量冻结的**逐条理由**在该 yaml 里（2026-09-29 上线时实测 28 处 / 13 个文件）。"
            "⚠ **它不判什么**：不判表格**内容**对不对，也不判文档该不该有表 —— 只判**格数守恒**。"},
    {"id": "determinism", "title": "确定性噪声口径（单一真值表）",
     "fn": check_determinism, "quick": True,
     "fix": "A5（2026-09-29）：噪声口径 = **单表** `inventory/determinism-noise.yaml`（所有「双跑 / 逐字节比对」"
            "类判据**引用**它，**不各写一份** —— 各写一份 = 同一事实两处表达，改一处漏一处）。"
            "报『缺 `updated`』= 增长型真值表必须带**读数日期**；报『`line-ending.normalize_to` 必须 LF』="
            "逐字节比对要求二进制一致（归一化只在**生产端**固化，比对端妥协 = 把噪声洗成假绿）；"
            "报『`applies_to` 含 X —— 不是真实断言 id』= **孤儿消费者**（无消费者的真值表会腐化）⇒ 改成真实 gate id；"
            "报『正则匹配不上代表样本』= 表里那条正则**检不出该类噪声**（坏正则）⇒ 修正则；"
            "报『有 match 但无自证样本』= 新增了可机检噪声却没给夹具 ⇒ 在 `_DET_SAMPLES` 补样本；"
            "报『`determinism: n/a` 缺 reason』= 天然不可双跑者必须写理由（**禁止静默跳过**）。"
            "⚠ **它不判什么**：不真的跑某条管线双跑（那要具体管线接入）—— 只钉住**口径单一真值 + 表可用性**。"},
    {"id": "derived-view", "title": "派生只读视图（真值→渲染→逐字节比对）",
     "fn": check_derived_view, "quick": True,
     "fix": "A3（2026-09-29）：清单类文档的**第二定义点**正解 —— 抄的那份改成**派生件**，"
            "从真值**渲染**出来（渲染器 = `ops/derived_view.py`；当前真值源 = `inventory/ports.yaml`；"
            "落档视图 = `docs/派生视图_端口分配.md`）。"
            "报『**过期**（声明 source-hash ≠ 当前）』= 真值改了但视图没重渲染 ⇒ 跑 `py ops/derived_view.py --emit`；"
            "报『**逐字节不一致**』= 视图被**手改**过 ⇒ 别手改，同样 `--emit` 覆盖（手改会被下次渲染冲掉）；"
            "报『**渲染链路故障**(rc=2)』= 读真值/解析 yaml/落档写入失败 ⇒ **先修渲染器**（这与「过期」不是一回事）；"
            "报『落档视图**缺 `source-hash` 行**』= 档头被删 ⇒ `--emit` 重出。"
            "★ **为什么判退出码而不在这里重实现比对**：三态（0 一致 / 1 过期·漂移 / 2 故障）由渲染器**单一定义**，"
            "门禁只做消费者 —— 各写一份 = 同一事实两处表达（本仓头号形态）。"
            "⚠ **它不判什么**：不判视图**内容**对不对（那是 `ports` 判据的事），只判「视图 == 真值的确定函数」。"},
    {"id": "executor-trace", "title": "执行侧过程留痕（五采集点）",
     "fn": check_executor_trace, "quick": True,
     "fix": "A2（2026-09-29）：治「判据只能看产物，看不到过程」—— 站上执行体改过哪些文件 / 跑过哪些命令"
            "此前**查不到**（既有两件：输出字节序列只记吞吐曲线、工作区改动摘要实测为空）。"
            "口径 = `dogfood-cards/imp4-executor-trace-design.md`：最小充分集**5 项**"
            "（cmd / env / fs / tool / artifact）。"
            "报『**缺采集点标记 X**』= `ops/station-bin/agent-cli.ps1` 里那一维**没被采集**"
            "（看着有留痕，实际缺维度）⇒ 补回该采集点（**别只补门禁**）；"
            "报『出现 `chain=core` / `chain=verified`』= **伪称执行体内部可核** —— 工具调用链由执行体**内部**产生"
            "（可篡改 / 漏报 / 伪造），**只能如实标 `uncore`**；"
            "报『runDir 的 executor-trace.txt **缺段**』= 落到仓的留痕件不齐（真缺陷）⇒ 查该次派发的采集链路。"
            "**锚定段**（2026-09-30 补）：报『**自报**』= 留痕件里出现执行体自报的产物哈希"
            "（`[artifact] hashes=` 必须是 `main-side` —— 执行体不可信，哈希只能由主控侧回收时算）⇒ 改采集点；"
            "报『**ts 不符**』= 留痕件不属于这一次（`ts=` ≠ runDir 名）⇒ 查归档 / 回收是否张冠李戴（`O-57` 同族）。"
            "⚠『覆盖 0 个』**不作为 FAIL**（本件尚未经真派发 ⇒ 覆盖率**未验**，报数不入分母）；"
            "⚠『无锚记录 N』同理**只报数**（主控侧没有该次 `content_digest` ⇒「没验到 ≠ 验出问题」）。"
            "⚠ **它不判什么**：逐条字面细节（两段写入 / `$Script:EV_FILES` 登记 / 主控归档 / `free -m` 而非 `/proc`）"
            "由**离线夹具** `_fm_golden_test.ps1` 守（见 `ps1-golden`）—— 本判据**不抄第二份**。"},
    # O-63 (2026-09-25): 取号并发夹具。**刻意 quick:False**（要起 8 个独立进程 + 两次 2.5s 共同释放时刻 ⇒ 约 6s）。
    {"id": "ps1-runstamp", "title": "ts 取号并发夹具", "fn": check_ps1_runstamp, "quick": False,
     "fix": "O-63: 跑 `powershell -NoProfile -ExecutionPolicy Bypass -File ops/station-bin/_runstamp_hammer.ps1 -N 8 -SelfTest`。"
            "两行**都要**在：`RUNSTAMP_HAMMER … PASS`（正向：8 进程 ts 全不同）+ "
            "`RUNSTAMP_HAMMER_SELFTEST … PASS`（负向：**同一把锤子**打旧实现必须检出撞车）。"
            "⚠ 只报负向 = **夹具是装饰**（正向根本没产生唯一 ts）；只报正向 = 负向没跑（少一行 ⇒ 本断言直接 FAIL）。"
            "⚠ 若出现 `dup:` ⇒ **真的撞了**：检查 `Get-UniqueRunStamp` 的原子原语是否被改回 "
            "`New-Item -ItemType Directory`（实测它会漏，uniq=11）—— 必须是 `[IO.File]::Open(..., CreateNew, ...)`"},
    # O-64 (2026-09-25): **测试套件接进门禁** —— 此前 21 套测试无任何机械执行者（"有测试 ≠ 有人在跑"）。
    #   实测依据与本项定位见 check_py_tests 的 docstring 与 PY_TESTS 上方注释（含 quick 取舍的实测值）。
    {"id": "py-tests", "title": "Python 测试套件(统一入口)", "fn": check_py_tests, "quick": False,
     "fix": "跑 `py tests/run_py_tests.py`（或 `-v` 看每题完整输出）⇒ 修明细里的 FAIL。"
            "⚠ **先判「是回归还是断言陈旧」**：若实现侧确有语义变更（看 `ops/station-bin/agent-cli.ps1` 的"
            "注释/O- 台账）⇒ 改**断言**并写明理由（**方向是改写断言，不是回退代码** —— 回退等于把修好的洞挖回来）；"
            "若实现侧无变更 ⇒ **是回归**，改代码。"
            "⚠ 报『总数 == 0』或『未解析到汇总行』= 入口本身坏了（如 discover 找不到测试）⇒ 先修入口 —— "
            "那是**比任何单条测试更严重**的失效（整批验证静默消失）"},
    {"id": "usb4", "title": "USB4 三角环链路", "fn": check_usb4, "quick": False,
     "fix": "地址/路由不符 => 对照 inventory/net.yaml 与归档 §6.3/§6.6; "
            "链路不通 => 先查 BIOS USB4 安全等级与是否冷启动(归档 §6.5)"},
    {"id": "gates", "title": "内存门禁", "fn": check_gates, "quick": False,
     "fix": "load-gate 缺失需补部署到 /usr/local/bin; 余量 ≤0 先卸载或清残留; "
            "loadavg>8 等负载回落再加载; 站上件与仓库副本不一致 => 这些件是站上件(改仓库不生效), "
            "按明细走「备份(cp -a, 核备份 md5 == 原 md5) → install -m 755 → 核新 md5 == 仓库副本」, "
            "或回滚站上版并改仓库侧; 清单见 rpc_check.py 的 STATION_BINS"},
    {"id": "halogen-assets", "title": "容器模型资产预检", "fn": check_halogen_assets,
     "quick": False,
     "fix": "按明细补资产/重分发权重；镜像缺失则 containers pull；不要先杀旧服务"},
    {"id": "engine", "title": "引擎态与残留", "fn": check_engine, "quick": False,
     "fix": "残留用 infer-unload 或清 llama/rpc 进程; 端口在听但 RSS 异常需查进程归属"},
    {"id": "backend", "title": "引擎后端与 studio 防线", "fn": check_backend, "quick": False,
     "fix": "默认单站引擎=HIP、分布式(/opt)=Vulkan 是本集群的**既定形态**; 后端变了先查是谁改的 "
            "(studio 自更新 / UPGRADE_SOP 升级 / 有人换构建) 再决定是否改期望值, 并把台账 §2.6 "
            "的后端矩阵同步; 回滚基线缺失 => 从同版本站 tar 分发补回 "
            "(UPGRADE_SOP §6: 保留 `<现役>` + `9859` 两个版本目录以支持分钟级回滚); "
            "**pin 未生效** => 落 `/etc/environment` 的 `UNSLOTH_LLAMA_CPP_BACKEND=rocm`"
            "(`.bashrc`/`.profile` 对非交互 ssh 无效, 见决策简报 §8.2); "
            "**缺 `X-Unsloth-Events`** => 升级 studio(简报 §三); "
            "**studio 版本或引擎构建不同版** => `cluster.py studio status` 看矩阵再决定是否同升; "
            "**引擎备份目录为空** => 引擎若被替换只能靠站间 tar(要求三站逐字节同版)或重下"},
    {"id": "models", "title": "模型库完整性", "fn": check_models, "quick": False,
     "fix": "孤儿 `cluster.py models link --go`; 断链 `cluster.py models prune --go`"},
    {"id": "stations", "title": "三站实况对账", "fn": check_stations, "quick": False,
     "fix": "conf/权重/凭据/端口/插件任一项不符 —— 见明细, 一律以站上实况为准改仓库侧"},
    # ★ 2026-10-13: `$PROJECTS` 数据化 —— 项目注册表**自洽**（`$PROJECTS` 的唯一真值）。
    #   ⚠ 它**不判** root 存在性（外盘可能离线 ⇒ 会假红）；存在性由 `workspace create` 在使用时判。
    {"id": "projects", "title": "项目注册表($PROJECTS 真值)", "fn": check_projects, "quick": True,
     "fix": "改 `inventory/projects.yaml`（`$PROJECTS` 的唯一真值）：① id 非空且**逐字**= 调用方使用的键；"
            "② status ∈ {active, retired}；③ since 形如 YYYY-MM-DD；④ root 非空字符串（**单引号**括起 Windows 路径）；"
            "⑤ **同一串不许属两条**。★ 新增项目 = 追加一条 `active`（**门禁不看人只看登记**）；"
            "退役 = 改 `retired` 而**不删**。⚠ 报『projects 为空』= 判据退化（无对象）"},
])
