# 30_evidence — 交付证据束（<project>-<date>）

> **目的**：把"这一批产出就是这些、这批产出可被复验"钉成可机读证据束。
> 依据：ADR-0008（30_evidence 语义）+ ADR-0005/0007（证据流阶段）+ 合并实施计划批次 D。

## 结案时本目录须含

1. **`MANIFEST.sha256`** —— 钉死本次交付的证据件（标准 `sha256sum` 格式 `<hex>  <relpath>`，
   指向项目根 `agent-out/<ts>/` 的 `run.json`（含 `evidence_manifest`）+ 单 run 证据束
   `.meta` / `.prompt.txt` / `.progress` / `.accept-cmds.txt` / `.golden-cmd.txt` /
   `.workspace-diff.txt` / `.attach-manifest.txt` / `.session-meta.txt`）。
   **未附本清单 → 不 `done`**；`done` 后本目录**冻结**（artifact freeze，不再改动）。
2. **交付分级标注**（`GRADE.md` 或 MANIFEST 注释头）：
   - `Reproduced` = 内部同基座复验通过（ADR-0007 Phase 2）；
   - `Replicated` = 异基座独立审计通过（Phase 3 / cold mirror）。
3. **环境快照**：`cluster.py versions` 输出（三站引擎/uv/模型哈希/`--kv-cache` 参数）随证据束落档
   —— 社区"机器可读环境描述"的最低成本实现。

## 验收判据（重放语义声明）

> **"重放 = 重放验证，非重放生成"**（沿 ADR-0007）：可证伪的检查是
> 产物字节 vs 哈希、判据退出码、diff 路径白名单、输入快照哈希、脚本版本哈希；
> **不承诺**逐位一致再生成（temp=0 跑 1000 次得 80 个不同结果是生成层物理事实）。

复制本模板到新笔 `30_evidence/` 时删掉本说明，按上述三件落实。
