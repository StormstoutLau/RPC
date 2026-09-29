# O-102 工作区行尾漂移 —— 修复闭环验证报告

- **验证对象**: [OPEN-ISSUES.md](./OPEN-ISSUES.md) **O-102**（工程形态/编码 · P3）「工作区行尾约定未声明，且"漂移生成源"仍在工作」
- **修复动作**: **扩 `.gitattributes` 射程**（补 `ops/` 下其余**会被执行的 shell**）+ 强制重落 4 个件
- **验证日期**: 2026-09-30
- **验证结论**: **已闭环** —— 包含一处**如实裁定「不处理」**的射程声明（§5）

***

## 1. 问题与现象（原登记 ↔ 复测）

O-102 原登记（2026-09-26）三条「为什么值得登记」，2026-09-30 逐条复测：

| 原前提 | 复测结论 |
|---|---|
| ① **约定未声明** ⇒ "什么算规范"**无权威源**（原文：`无 .gitattributes`，`Test-Path` = False） | ✅ **已消掉** —— `.gitattributes` **已于 2026-09-29 立**（commit `fc1ae8f`，理由写明"已发生两次真故障"） |
| ② **生成源仍在工作**（编辑工具：局部插入不改既有约定） | ⚠ **仍成立** —— `w/mixed` 由 **6 → 14**；但**射程内**已由 `text eol=lf` **结构性**挡住 |
| ③ **既不可判也不可见** | ◐ **射程内已消掉**（`gates` 按**字节**比对「仓库副本 ↔ 站上实况」，且 2026-09-29 **实测抓到过一次假红**）；**射程外仍不可判** |

⇒ 于是把 ①③ 的残留**收敛为一个可执行的缺口**（§2）。

## 2. 缺口（实测，**不是推测**）

| 件 | 头 | 修复前 `w/` | 在射程? |
|---|---|---|---|
| `ops/llama-serve-instance` | `#!/bin/bash` | **CRLF 34 / 裸 LF 0** | ❌ **不在** |
| `ops/lm-download/speedtest_asset.sh` | `#!/bin/bash` | CRLF 7 / 0 | ❌ **不在** |
| `ops/lm-download/speedtest_codeload.sh` | `#!/bin/bash` | CRLF 11 / 0 | ❌ **不在** |
| `ops/lm-download/speedtest_mirrors.sh` | `#!/bin/bash` | CRLF 16 / 0 | ❌ **不在** |
| `ops/station-bin/llama-serve-instance`（**天然对照**） | `#!/bin/bash` | **LF 54 / 0** | ✅ 在 |

★ **同名的两件一个 LF 一个 CRLF** ⇒ 缺口是**真的**（射程内被保护、射程外没有）。
★ 另在复核**期间**发现第二处：`ops/station-bin/*` **不跨子目录** ⇒ 漏掉 `ops/station-bin/golden/*.sh`（现为 `w/lf`，属"**未被保护**"）。

## 3. 修法（最小改动 = **单文件**）

[.gitattributes](../..//.gitattributes) 的射程内：

- `ops/station-bin/*` → **`ops/station-bin/**`**（`**` 是严格超集，含子目录）；
- **新增** `ops/llama-serve-instance` · `ops/lm-download/*.sh`。

★ 4 个件修复前均为 **`i/lf w/crlf`**（**索引已是 LF**，只有**工作树**是 CRLF）⇒ 重落后 `git status` **只剩 `.gitattributes` 一处改动** ⇒ **不产生任何内容 diff**（修复不碰产物字节）。

## 4. 质量审计

- **先验红**：修复前 `git ls-files --eol` = `i/lf w/crlf`（4/4）· 字节 **CRLF=34 / 7 / 11 / 16**、裸 LF=0。
- **后验绿**：`w/lf`（4/4）· **CRLF=0**、裸 LF=34 / 7 / 11 / 16。
- **变异自证**（用 `.git/info/attributes` **反向覆盖**，**不动被跟踪文件**）：
  覆盖为 `text eol=crlf` ⇒ 强制重落 ⇒ **CRLF=34**（与修复前**逐位一致**）；撤除覆盖 ⇒ 重落 ⇒ **裸 LF=34**
  ⇒ ★ 证明**是这两行属性在管形态**，不是别的因素。
- **反例（写下来，防"以为它拦住了"）**：`git checkout --` 与 `git checkout-index -f` **都不会**重落
  （git 认为内容未变）⇒ **必须"先移除再检出"**。这条若不写，下一个人会以为"改了属性就生效"。
- **门禁**：`--quick` **PASS · 38 绿 / 2 黄 / 0 红**；`syntax`（`.sh` 414/0）· `scripts`（未登记 0）·
  `spec-untested` · `doclinks`（失效 0）· `artifacts`（inventory yaml 26/26 可解析）全 **PASS**。

## 5. 射程声明 +「不做」的裁定（本仓纪律：**不做也是一种结论，必须写下来**）

- **射程（改后）** = 会被**部署 / 执行**的件：`ops/station-bin/**` · `ops/rpc-nodes` ·
  `ops/llama-serve-instance` · `ops/lm-download/*.sh` · `ops/*.service` · `ops/*.timer`。
- ★ **已裁「不处理」**：`archive/**` 与 `tests/b5q/**` 的 `w/crlf`（原文实测：`.sh` 中 `w/crlf` 的 235 里
  **211 在 `archive/`**）—— 理由 = **不面向执行**，且原文已实测"无伤害路径"。
- ⚠ **仍如实留着（本闭环不消灭它们）**：
  1. **全仓仍 `w/lf` / `w/crlf` 并存**（射程刻意不铺全仓）⇒ 原文那句"**两种约定并存**"**依旧成立**；
  2. **`w/mixed` 仍在产生**（生成源 = 编辑工具）—— 射程内已结构性挡住，射程外无危害；
  3. **`ops/` 下 `.py` 仍 `w/crlf`**（`cluster.py` 等）⇒ 原文实测"Python 文本读入归一 ⇒ 无伤害"**仍成立**。

## 6. 对原文的两处改判

1. 原文「**未验（潜在，属推测）**：将来若加按字节 / 哈希的完整性判据 ⇒ CRLF 翻转会假红」
   ⇒ ★ **改判为「已验」**：`gates` **已经是**按字节判据（对站上件），且 **2026-09-29 已兑现过一次**
   （`infer-load` / `infer-unload` 工作树 CRLF vs 站上 LF ⇒ 假红）；**射程内已从源头挡住**。
2. 原文「无 `.gitattributes`（`Test-Path` = False）」⇒ **已过期**（2026-09-29 立）。

## 7. 关联与回写

- **台账**：[OPEN-ISSUES.md](./OPEN-ISSUES.md) O-102 状态 `◐ 已登记 · 未处置` → **`✅ 已闭环（2026-09-30）`**（附 §5 射程声明）。
- **落地记录**：[DEVELOPMENT-LOG.md](./DEVELOPMENT-LOG.md) `2026-09-30（续②）`。
- **前置**：commit `fc1ae8f`（`.gitattributes` 立，2026-09-29，ADR-0006 v1.3 同批）· 判据 = `gates`（站上件逐字节比对）。
- **未新增脚本**（`ADR-0004` 无需登记）· **未改任何产物字节**（§3）。