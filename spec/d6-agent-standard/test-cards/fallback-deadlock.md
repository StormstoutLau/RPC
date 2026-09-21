---
proj: paper
task: 真实站点死锁 → claude 自动 fallback 实弹自证（用短预算强制远端 timeout 强杀）
model: gpt-oss-20b
cli: opencode
sensitivity: local-only
readonly: false
timeout_s: 10
continue-timeout-s: 5
accept:
  - true
---
## 任务描述

请把整数 `1` 到 `800` **逐个**输出，每行一个，不要省略、不要总结、不要用省略号。

---

> **用途**：验证 **真实站上 opencode 引擎死锁/超时**时 `AGENT_AUTO_FALLBACK=1` 的自动转 claude 备路
> （[OPEN-ISSUES 「D6 闭环审查 2026-09-21」](../../../spec/d6-agent-standard/OPEN-ISSUES.md) ②）。
>
> **为什么用短预算造"死锁"**：`timeout_s: 10` 刻意小于"输出 800 行"所需时间 ⇒ 远端
> `timeout 10 opencode run …` **强杀** ⇒ rc=124 ⇒ 映射为 **rc=6**（引擎超时哨兵，与 #17307
> 那类"引擎在预算内产不出终态"的**信号类等价**）。诚实边界：这**复现的是信号类**，
> 不是"引擎自身缺陷导致的挂死"；后者需故意错配 ctx 才会出现（O-23 场景），风险更高，未做。
>
> **跑法**（模型需先在 B 站加载）：
> ```powershell
> python ops\cluster.py load gpt-oss-20b
> $env:AGENT_AUTO_FALLBACK = '1'
> powershell -ExecutionPolicy Bypass -File ops\station-bin\agent-cli.ps1 task paper `
>   -Card spec\d6-agent-standard\test-cards\fallback-deadlock.md
> python ops\cluster.py unload
> ```
> 预期：主路 rc=6 → 打印 `AUTO_FALLBACK: opencode rc=6 -> local claude backup` → 转
> `Invoke-Task-Claude`（claude 未登录时该 run 记 `failed`，但**证据面 v2 照常归档**）。
