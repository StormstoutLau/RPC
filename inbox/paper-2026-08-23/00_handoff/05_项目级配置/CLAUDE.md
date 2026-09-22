@AGENTS.md

## Claude 专属补充（薄壳）

- 上下文窗口由站上 `~/.claude/settings.json` 的 `CLAUDE_CODE_MAX_CONTEXT_TOKENS` 决定（当前 120000）。**勿依赖 200k 默认假设**——Claude Code 对未识别模型按 200k 估算，自动压缩阈值会失真。
- 模型名为未识别名（`claude-opus-4-6` → `modelOverrides` → `main`），走 plain 格式以获得较小的系统提示；**保持该自定义模型**，切回 Opus/Sonnet 档会恢复 200k 窗口假设。
- 占用 60–70% 时手动 `/compact`（附保留指令）；任务切换用 `/clear`。
- 冷缓存首条消息可能 70–110s（系统提示预填充），等待即可；同会话后续为秒级。
- headless 调用必须显式关 stdin：`claude -p "..." < /dev/null`，否则可能长时间等待输入。
