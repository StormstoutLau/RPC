---
proj: paper
task: 对 D:\Paper 的 paper_cli 代码库做结构化调研，产出一份模块地图文档写入 out/.dogfood_module_map.md；不修改任何既有代码文件
model: nemotron
cli: opencode
sensitivity: local-only
readonly: true
timeout_s: 900
accept:
  - cd /home/scott-lau/agent-workspaces/paper && test -f out/.dogfood_module_map.md && grep -q '## 模块清单' out/.dogfood_module_map.md && grep -q '## 职责' out/.dogfood_module_map.md && grep -q '## 数据流' out/.dogfood_module_map.md && grep -q '## 缺口' out/.dogfood_module_map.md
---
## 任务描述

你是审查员，对工作区中的 `paper_cli/` 代码库做**结构化调研**（只读，不创建/修改/删除任何 `.py`/`.yaml` 等既有或新增代码文件）。

调研输入：遍历 `paper_cli/` 全部 `.py`（含 `phase2/` 子包、`rules/` 下四个 `.yaml`、`tests/` 下测试）——按需读取，不需要逐行读所有测试。

产物：在 `out/.dogfood_module_map.md` 写入一份**模块地图文档**，必须包含以下 **5 个 `##` 章节**（标题逐字一致）：

- `## 模块清单`：Markdown 表格列出主要模块（模块名 | 一句话职责 | 依赖哪些模块），至少覆盖 extractor/classifier/normalizer/organizer/scanner/schemas/main + phase2/* 主要成员
- `## 职责`：每个核心模块职责的一句话定性（非源码粘贴）
- `## 数据流`：谁调用谁的有向链（`A → B` 形式，至少 8 条真实调用边，来自 `import`/`from` 或函数调用证据）
- `## 边界`：模块间的依赖方向与循环依赖情况（有则点出，无则声明无）
- `## 缺口`：至少 3 条代码库层面的问题/缺口/改进建议（扣合实际代码，禁止泛泛）

最后在 stdout 输出单行结束标记 `DOGFOOD_TASK3_OK`。不要输出其他结论块（模块地图主体在文件里，stdout 只需该标记）。