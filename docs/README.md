# docs/ — 操作记录与手册

> **定位**：本目录放**操作记录、手册、排查与决策落档**（多按日期命名）；**规范/判据**在 [spec/](../spec/README.md)，**裁定**在 [adr/](../adr/README.md)。
> **索引**：全仓有元数据的文档见 [INDEX.md](./INDEX.md) —— 由 `py -3 ops/rpc_doc_index.py --write` 生成，**禁止手工编辑**。

## 先看哪一篇

| 你要做什么 | 读哪一篇 |
|---|---|
| 起停引擎、跑模型、查端口与三站状态 | [三机推理集群使用手册](./三机推理集群使用手册.md) |
| 看某个决策为什么这么定 | [决策代志 DEV-LOG-014](./DEV-LOG-014-decision-refinement.md) |
| 找某主题的调研结论 | [research/README.md](./research/README.md)（主题路由；每个主题只有一个承载文档） |
| 找未决问题 / 待办 | [OPEN-ISSUES](../spec/d6-agent-standard/OPEN-ISSUES.md)（唯一真值台账） |
| 找上游 PR / 引擎基线 | [TRACKER](../spec/upstream-tracker/TRACKER.md)（活数据唯一真值） |

## 目录分类（按文件名形态）

| 形态 | 例子 | 说明 |
|---|---|---|
| 手册 | `三机推理集群使用手册.md` | **活文档**，随站上实况更新；改配置后必须回写 |
| 决策代志 | `DEV-LOG-*.md` | 按编号追加（§NNN），**只追加不改写** |
| 日期落档 | `YYYY-MM-DD_<主题>.md` | 一次操作/排查/方案的快照；结论进 spec 或台账 |
| 调研 | `research/` | 主题级承载文档，入口见其 README |
| 生成索引 | `INDEX.md` | **生成物**，禁止手工编辑 |

## 检索纪律（零成本，先立规矩）

1. **找事实/命令** ⇒ `Grep` 全文（全仓 8.8 MB，毫秒级）。
2. **找某主题的权威文档** ⇒ [research/README.md](./research/README.md)。
3. **找"谁引用了这篇"** ⇒ 门禁 `doclinks`（已被全量算过，失效 0）。
4. **按 type/status 筛** ⇒ `py -3 ops/rpc_doc_index.py --type research` / `--status todo`。
5. **不要**在本目录手写"全量清单" —— 那份清单是 [INDEX.md](./INDEX.md)。

## 新增文档规则

- 带 YAML front-matter（`id/type/version/status/date`）的文档会自动进 INDEX；写完跑 `--write` 重生成。
- 无 front-matter 的操作记录 ⇒ 按 `YYYY-MM-DD_主题.md` 命名。
- **一个主题只放一篇承载文档**；跨主题建链接，不复制内容（否则同一事实两处维护）。
