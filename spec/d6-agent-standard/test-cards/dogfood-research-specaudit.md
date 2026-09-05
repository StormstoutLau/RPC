---
proj: paper
task: 对 D:\Paper 的 phase2 规格文档做结构化审读，产出一份规格-实现对照审读文档写入 out/.dogfood_spec_audit.md；不修改任何既有文件
model: gpt-oss
cli: opencode
sensitivity: local-only
readonly: true
timeout_s: 900
accept:
  - cd /home/scott-lau/agent-workspaces/paper && test -f out/.dogfood_spec_audit.md && grep -q '## 缺失项' out/.dogfood_spec_audit.md && grep -q '## 风险' out/.dogfood_spec_audit.md && grep -q '## 建议' out/.dogfood_spec_audit.md
---
## 任务描述

你是规格审读员，对工作区 `docs/` 下的 phase2 相关文档做**结构化审读**（只读，全程不创建/修改/删除任何既有或新增文件）。

调研输入：读取 `docs/` 下 `spec_phase2.md` 与 `architecture_phase2.md`（若文件确不在工作区，改用 `docs/` 下任意 `*phase2*.md` 或 `*architecture*.md`，并在输出中注明实际读的文件名）；若 `paper_cli/phase2/*.py` 存在则抽样对照实现。

产物：在 `out/.dogfood_spec_audit.md` 写入**规格-实现对照审读文档**，必须包含以下 **3 个 `##` 章节**（标题逐字一致）：

- `## 缺失项`：规格声明但实现空缺 / 实现里存在但规格未覆盖的条目清单，至少 3 条（每条给出 规格出处/实现位置/差距一句话）
- `## 风险`：至少 3 条可落地的风险（结合 phase2 实际实现，禁止泛泛"缺乏测试"式结论）
- `## 建议`：按优先级给出可执行建议，至少 3 条

最后在 stdout 输出单行结束标记 `DOGFOOD_TASK4_OK`。不要输出其他结论块（审读主体在文件里，stdout 只需该标记）。