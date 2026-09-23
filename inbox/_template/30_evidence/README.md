# 30_evidence — 交付证据束（<project>-<date>）

> **目的**：把"这一批产出就是这些、这批产出可被复验"钉成可机读证据束。
> 依据：ADR-0008（30_evidence 语义）+ ADR-0005/0007（证据流阶段）+ 合并实施计划批次 D。

## 结案时本目录须含

1. **`MANIFEST.sha256`** —— 钉死本次交付的证据件（标准 `sha256sum` 格式 `<hex>  <relpath>`）。
   **一条命令生成**（默认只出计划，`--go` 落盘）：

   ```powershell
   python ops/cluster.py inbox seal <project>-<date> --grade Reproduced --go
   ```

   钉的是项目根 `agent-out/<ts>/` 里**实际存在的全部证据件**（回收后的名字：
   `.agent-run.json` / `agent-output.txt` / `prompt.txt` / `card.md` / `stderr.txt` …）。
   ⚠ **不要**硬套固定 6 件清单（`AGENT_EVIDENCE_FILES`）—— 那是**链校验的"声明件"**，
   真实 run 常缺其中几件（`judgment-record.txt`/`accept-*` 只在配 accept/golden 的任务里有）。
   校验：在项目根下 `sha256sum -c <本清单绝对路径>`（忽略 `#` 行）。
   **未附本清单 → 不 `done`**（门禁对 `release`/`done`/`accepted-by-requester` 强判）；
   `done` 后本目录**冻结**（artifact freeze，不再改动）。
2. **交付分级标注**（写在 MANIFEST 注释头，由 `--grade` 写入）：
   - `Reproduced` = 内部同基座复验通过（ADR-0007 Phase 2）；
   - `Replicated` = 异基座独立审计通过（Phase 3 / cold mirror）。
3. **环境快照**：`cluster.py versions` 输出（三站引擎/uv/模型哈希/`--kv-cache` 参数）随证据束落档
   —— 社区"机器可读环境描述"的最低成本实现。（**尚未自动化**，当前为手工步骤。）

## 验收判据（重放语义声明）

> **"重放 = 重放验证，非重放生成"**（沿 ADR-0007）：可证伪的检查是
> 产物字节 vs 哈希、判据退出码、diff 路径白名单、输入快照哈希、脚本版本哈希；
> **不承诺**逐位一致再生成（temp=0 跑 1000 次得 80 个不同结果是生成层物理事实）。

复制本模板到新笔 `30_evidence/` 时删掉本说明，按上述三件落实。
