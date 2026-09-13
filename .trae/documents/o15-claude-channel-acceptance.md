# O-15 claude 备通道 — 实机验收暂时方案

> 状态: ✅ 暂时方案落档（2026-09-12）。正式验收执行环境为**主控站**，需先行解决 agent-cli.ps1 的 UTF-8 加载问题。
> 关联台账: `spec/d6-agent-standard/OPEN-ISSUES.md` O-15（关闭判据见下）。
> 关闭判据原文: `agent-cli task <proj> --card <task.md> --cli claude` 可用，超时后自动 `--continue` 续接（claude local 分支，需在 UTF-8 运行时 + 已装 claude 的控制台实测）。

---

## 0. 背景与验收前提

- O-15 claude 备通道已实现（`--cli claude` + `--continue` 续接），见 OPEN-ISSUES O-15"当前状态"。
- 本方案为**暂时验收方案**：CLI 机制冒烟可在任何装有 `@anthropic-ai/claude-code` 且有登录态的机器验证；**完整 `agent-cli task --cli claude` 验收必须在主控站**执行（依赖资产路径 + 控制台本地兜底续跑，不依赖 ssh / 站内算力）。
- **前提问题（必须先行解决）**: 主控站为 Windows PowerShell 5.1 + CP936 代码页；agent-cli.ps1 含中文 PS 字符串字面量在 CP936 下裸 `powershell -File` 解析失败。

---

## 1. s0 — agent-cli.ps1 加载方式（验收前置，必须先解决）

两种可行方案：

1. **UTF-8 BOM 临时文件加载（推荐，已验证可行）**: 薄加载器读取 agent-cli.ps1 以 UTF-8（no BOM）读出源码，再以 **UTF-8 带 BOM** 写回临时文件后执行。
   ```powershell
   $src = 'D:\RPC\ops\station-bin\agent-cli.ps1'
   $tmp = Join-Path $env:TEMP 'ac-utf8-load.ps1'
   $code = [IO.File]::ReadAllText($src, [System.Text.UTF8Encoding]::new($false))
   [IO.File]::WriteAllText($tmp, $code, [System.Text.UTF8Encoding]::new($true))
   & $tmp route --model claude        # 探测性路由验证
   Write-Output ("EXIT=" + $LASTEXITCODE)
   ```
2. **直接修复源文件为 UTF-8 带 BOM**（根治，但需复审全文件；本次验收建议先走方案 1，不阻塞验收）。

验收门 s0: 通过薄加载器执行 `route --model claude` 能正确解析（无中文字符串解析报错，返回 exit 0）。

---

## 2. s1 — 前置准入验证

```powershell
& $loader route --model claude        # ROUTE_TABLE 命中 claude 条目（claude-sonnet-4-5）
& $loader route --model claude-opus   # claude-opus-4-1
claude --version                      # claude CLI 已安装
claude auth status                    # 已有登录态（author 走 claude 自身）
```

验收门 s1: 三命令均成功，ROUTE_TABLE 返回期望模型 id 与 station=''（控制台本地）。

---

## 3. s2 — 执行器隔离验证

确认 `--cli claude` 分支正确路由到 `Invoke-Task-Claude`，且未知 cli 被拒绝。

```powershell
& $loader task <proj> --card <min.md> --cli notexist   # 期望 REJECT unknown-cli (notexist) + exit 2
& $loader task <proj> --card <min.md> --cli claude     # 期望走 Invoke-Task-Claude（本地 headless 分支）
```

验收门 s2: 未知 cli 拒绝 exit 2；claude 分支命中（可打印 CLI=claude route_station= 空）。

---

## 4. s3 — 全链验收核心流程（主控站）

```powershell
$loader task <proj> --card <dogfood-task.md> --cli claude --timeout-s 900
```

预期链路（镜像 opencode 全生命周期，契约与 DESIGN §6.2 一致）:
- 首跑: `claude -p "" --model claude-sonnet-4-5`（stdin 喂组装 prompt）
- golden → accept → 状态机 → `ledger` + `.agent-run.json`（`cli='claude'`）
- 产物回收、状态落库齐全

验收门 s3: 全链跑通，run.json 记录 `cli='claude'`，产物回收完整，状态机闭环。

---

## 5. s4 — 续接（--continue）故障演练

用超时/失败卡验证独立续跑预算与恢复链路。

```powershell
$loader task <proj> --card <timeout-task.md> --cli claude   # 卡内 timeout_s 很小，制造首跑失败
```

预期: 首跑 RC≠0 → `claude --continue -p "" --model <id>` 续接（≤2 次，独立 `continue-timeout-s` 预算）；续跑仍失败则 `final .agent-state.json` 记 `ST=failed`（G1 C4，非静默 done）。

验收门 s4: 续接循环触发且 cap=2 正确；失败语义正确（RC≠0 → ST=failed）；`.meta` 视失败补 `REVIEW_NEEDED`。

---

## 6. 验收边界（3 个已知，需在验收时关注）

1. **accept/golden 命令 shell 语义**: accept/golden 采用 **bash 语义**，与本地 Windows PowerShell 的 `Invoke-Expression` 存在兼容性差异。验收时若卡在 accept/golden 判定，需区分"机制缺陷"与"shell 语义边界"。
2. **attach 沙箱写权限**: attach 功能会写入 `projRoot\.attach` 文件，主控站 PowerShell 沙箱下可能存在写权限问题；验收前确认该路径可写。
3. **系统依赖 D:\Paper 作为 cwd**: agent-cli 系统依赖 `D:\Paper` 作 cwd 直接读取项目源；验收需确认该依赖路径在当前主控站存在且可读。

---

## 7. 验收通过判据汇总

| 门 | 判据 |
|----|------|
| s0 | 薄加载器 `route --model claude` exit 0，无 CP936 中文解析报错 |
| s1 | claude CLI 已装 + 有登录态；ROUTE_TABLE 命中 station='' |
| s2 | 未知 cli exit 2；claude 分支命中 |
| s3 | 全链跑通，run.json `cli='claude'`，产物回收 + 状态机闭环 |
| s4 | 续接触发 + cap=2 正确；失败语义正确（ST=failed） |

全部通过 → O-15 关闭判据满足（对照 OPEN-ISSUES O-15）。本方案为暂时方案，正式固定验收流程可在主控站闭链后固化进手册。