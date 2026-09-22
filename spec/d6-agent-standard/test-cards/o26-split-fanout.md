---
model: gpt-oss
readonly: true
timeout-s: 900
continue-timeout-s: 900
decompose:
  - 只读分片1：读取工作区 .attach/_o26_src.txt 的第2行内容（以 SHARD-ONE 开头的行），整理为 1 行摘要写入 out/shard1.txt，内容前缀固定为 `O26_SHARD1_OK|`。不改动任何源文件。
  - 只读分片2：读取工作区 .attach/_o26_src.txt 的第3行内容（以 SHARD-TWO 开头的行），整理为 1 行摘要写入 out/shard2.txt，内容前缀固定为 `O26_SHARD2_OK|`。不改动任何源文件。
---

任务描述: O-26 拆分成2个只读分片的跨站并行验证主卡。任务不应由单个 agent 完整执行，只提供总上下文。