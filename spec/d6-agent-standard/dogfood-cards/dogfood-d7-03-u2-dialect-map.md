---
proj: dogfood
task: 只读附件调研稿的 §11.1 冲突清单（约第 709–731 行区间），把其中 L1/L2/L3·A/B/C·R1–R5 的三张表平铺成一张三列对照表（符号｜出处｜该处含义），写入 out/dialect-map.md；不读全文其它部分
model: local/m27-q4ks
cli: opencode
sensitivity: local-only
readonly: false
timeout_s: 1800
accept:
  - test -f out/dialect-map.md
  - test "$(grep -c '^|' out/dialect-map.md)" -ge 6
  - grep -q 'L1' out/dialect-map.md
  - grep -qE '[A-Za-z]:|/' out/dialect-map.md
evidence-manifest:
  version: 1
  subjects:
    - name: dialect-map
      path: dialect-map.md
      state: out/dialect-map.md
      digest: sha256
---
## 任务描述

你是**只做整理**的取证 agent。只读附件 `.attach/2026-09-23_D7调研_立项·机制·统一基座.md` 的 **§11.1**（约行 709–731：符号冲突），**不要**读全文其它部分（§11.2+ / §12 等都不碰）。

用 `Read` 带行区间只取那块（如 `Read ... region=700-735` 或等价），把其中的**三张冲突表**平铺成**一张三列对照表**写入 `out/dialect-map.md`。

### 唯一产物：`out/dialect-map.md`

**Markdown 表题**，有三列表头：

```
| 符号 | 出处 | 该处含义 |
|---|---|---|
```

**逐行转录这三张表（出处/含义全部用原文词，不改写、不脑补）**：

- **§11.1-(a) `L1/L2/L3` 5 种义**（第 714–718 行那张表：`D:\Paper` / `D:\Textbook` / `F:\Open_Data` / `E:\Macro_Data` / `F:\Fin_Agent`），**每个出处占一行**，含义 = 该行 `L1/L2/L3` 三列的原话。
- **§11.1-(b) `A/B/C` 3 种义**（第 720–721 行）：`Cpp_Hub`/`Spec_Workflow` 断言证据分级、`Macro_Data` 数据源可及性、`Cpp_Hub` 平台档位，**每种各一行**。
- **§11.1-(c) `R1–R5` 2 种义**（第 724–725 行）：`Open_Data` 幻觉修正分级、`Macro_Data` 冲突裁决规则码，**每种各一行**。

同符号多义 ⇒ 每种义**单独一行**（出处列用盘符+路径区分）。

**硬性要求**：

- **只转录原文**：含义列必须是原文词（如 `元数据` / `官方来源`），**不要总结、不要改写**。
- **出处列**必须含**盘符+路径**（`D:\Paper` 等）→ accept 判据会 grep。
- **不要写任何正文说明**、不要输出表以外的 Markdown 段落。
- **stdout 只输出一行**：`DOGFOOD_B1_OK`
- 除 `out/dialect-map.md` 外**不产生任何文件**。

> **用途（U-2 ⇒ `D7-P1-1` 前置，D-21/D-22 已裁）**：产出 **U-2 方言映射表的第一份实弹底稿**——将九项目里同一符号的多重含义按「符号｜出处｜含义」摊平，供 U-2「建映射、不迁移权威源」使用。
> **跑法**（`local-only`：读含研究内容文档 ⇒ 站内本地模型，不出网）：
> ```powershell
> python ops\cluster.py load m27-q4ks
> & .\ops\station-bin\agent-cli.ps1 task dogfood `
>     -Card spec\d6-agent-standard\dogfood-cards\dogfood-d7-03-u2-dialect-map.md `
>     -Attach @('docs\2026-09-23_D7调研_立项·机制·统一基座.md')
> python ops\cluster.py unload
> ```
> `state: out/dialect-map.md` ⇒ 产物由 collect 段白名单拉回 runDir（O-40/A-1）。