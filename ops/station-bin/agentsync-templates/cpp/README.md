# cpp — .agentsync 模板（Cpp_Hub 试点补建）

> **单一真值声明**：实际消费点为 `agent-cli.ps1` 内联 `$Script:AGENTSYNC_TEMPLATES['cpp']`（同步用排除清单）。
> 本目录为 IMPLEMENTATION §2「.agentsync 四型模板 ✅ 入 git」的登记兑现。**修改 .agentsync 排除规则时，唯一真值在 agent-cli.ps1 L82，勿在此处另存副本导致漂移。**
> 本文件仅作登记锚点 + 用途说明。

## 用途

`agent-cli workspace <proj> --sync` 时，远端工作区**永不覆盖**的资源类型排除清单（单向流不变式 6）。
对 cpp 工程，排除项含构建产物、第三方依赖、SOH 文件与运行时状态。

## cpp 排除清单（与 agent-cli.ps1 `cpp` 键一致）

| pattern | 原因 |
|---|---|
| `build/` | cmake/ninja 构建目录（产物不入同步） |
| `third_party/` | 大体积第三方依赖（重资产，O-13 范畴） |
| `*.o` / `*.a` / `*.so` | 编译中间物/静态库 |
| `.git/` | 由 git 独立管版本，不走 agentsync |
| `out/` | 产物输出（M5 单独 collect 回联） |
| `.agent-lock` `.agent-state.json` `.attach/` | D6 运行时状态/锁/附件 |

## 验证锚点

Cpp_Hub 试点（O-06 中文路径 + O-13 venv + O-12 golden）使用本模板：`src/因子计算_*.cpp`（含中文文件名）须经 `--sync` 正常推送，且 `build/` `out/` 被排除。