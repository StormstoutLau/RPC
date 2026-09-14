# station-bin 脚本密钥脱敏影响并列清单（2026-09-13）

> 背景：git 历史重写（filter-repo）+ `_sanitize_worktree.py` 工作区脱敏后，`ops/station-bin/` 下脚本按密钥获取方式分为三类。
> 核心原则：**只读/查询类看 key 是否失效；含"写配置"逻辑类看是否会把 `***REMOVED***` 污染远端生产配置**（后者的破坏力远大于 key 失效，重跑即污染）。

---

## A. 已失效诊断脚本（key 硬编码被替换为占位符，直接跑认证失败）

> 只读/查询类，仅 key 失效，**不写生产配置**，故无污染风险；要复用需手动替换回新 key。

| 脚本 | 失效形态 | 用途 |
|------|---------|------|
| `_aconn.sh` / `_aconn2.sh` | `KEY=***REMOVED***` | opencode/claude 连通性测试 |
| `_acurl.sh` | `KEY=***REMOVED***` | 端点 curl 测试 |
| `_amodel.sh` | `KEY=***REMOVED***` | 模型 list 测试 |
| `_along.sh` | `export KEY=***REMOVED***` | 长对话测试 |
| `_bapi.sh` / `_btools.sh` / `_brawres.sh` | `KEY=***REMOVED***` | B 站 API/工具/原始响应测试 |
| `_acldcfg.sh` / `_anamechk.sh` / `_amsgchk.sh` / `_amsgchk2.sh` / `_aportchk.sh` / `_bportchk.sh` | 请求头内联 `***REMOVED***` | 配置/命名/消息/端口探测 |
| `_averifinfload.sh` / `_b120bverify.sh` / `_bfinalverify.sh` | `KEY=***REMOVED***` | 加载后验证 |
| `_bench.py` / `_bench2.py` / `_bench3.py` / `_bench4.py` | `KEY="***REMOVED***"` | 基准测试 |
| `_bs2_cross.py` / `_bs2_fanout.py` / `_bs2_gw_local.py` / `_bs2_l1.py` | `KEY=***REMOVED***` | BS2 跨站/扇出/网关实验 |

> 若 AI-A 关闭后无需复现，可整组删除；否则需检索替换回新 key。

## B. 可安全复用脚本（GOOD — 内部动态 grep 提取 key，与脱敏无关）

> 生产及复现核心脚本，运行时从 `~/.unsloth/*.log` 用 `grep -oE 'sk-unsloth-[a-f0-9]+'` 动态读取最新 key，**永不含硬编码**，脱敏零影响，**保持原样勿动**。

| 脚本 | 用途 |
|------|------|
| `infer-load` | 生产核心：加载管理主入口 |
| `repro-launch/health/probe/parallel.sh` | 复现 harness 四件套 |
| `_abench.sh` / `_akvqtest.sh` / `_bkvqtest.sh` | KV/基准 |
| `_afinal.sh` / `_agen2.sh` / `_ahealth.sh` / `_akvqchk.sh` / `_apre.sh` / `_apost.sh` / `_bs6.sh` | A/B 站测试与复现 |
| `REPRO-RUNBOOK.md` | 复现手册（仅文档第42行含正则，无密钥） |

## C. 危险写配置脚本（🚨 含写远端配置逻辑，重跑会把 `***REMOVED***` 注入生产，**切勿执行**）

> 这些脚本要么 key 内联被替换、要么替换逻辑被改坏，一旦运行会改写远端 `~/.config/opencode/opencode.jsonc` / `~/.claude/` 等生产配置。**需重写正确 key 后才能安全使用；当前状态一跑即污染。**

| 脚本 | 污染点 | 风险说明 |
|------|-------|---------|
| `_aopenfix.sh` | `key='***REMOVED***'` → 注入 opencode `cluster-local` apiKey | 重跑会写入占位符 key |
| `_aoe8080.sh` | `d[provider]['cluster-local']['options']['apiKey']='***REMOVED***'` | 写 opencode + claude token |
| `_bocfix.sh` | `"apiKey":"***REMOVED***"` | B 站 opencode 配置修复 |
| `_bocupdate.sh` | 内联 `apiKey:"***REMOVED***"` 块 | B 站 opencode 配置生成 |
| `_asynccli.sh` | `re.subn` 替换值为 `\1"***REMOVED***"` | **动态提取但替换值被改坏**，一跑把配置 key 洗成占位符 |
| `_bcldset.sh` / `_acldtoken.sh` | `ANTHROPIC_AUTH_TOKEN='***REMOVED***'` | 写 claude 环境 token |
| `_bkeyupdate.sh` | `KEY=***REMOVED***` 后接更新逻辑 | 更新 key 逻辑失效 |

> 处置建议：重写 key 值前，先用 `git log`/归档件找回这些脚本的原始正确逻辑；若已无复用价值，**优先删除**，避免误触污染生产配置。

**📌 处置状态（2026-09-13 已完成）：C 类全部 8 个脚本已在 shebang 后注入 `# [DEPRECATED 2026-09-13]...勿执行` 头部标注。保留文件（便于 git log 追溯原始逻辑），但视为废弃不可执行；如需复刻正确逻辑请经 `git log`/归档件，勿直接编辑重跑。**

---

## 使用红线

1. **C 类一律不跑**，重写或删除后再考虑。
2. **A 类**复用前必须全局替换回新 key（可用 `grep -rl '\*\*\*REMOVED\*\*\*' ops/station-bin/` 定位）。
3. **B 类**保持原样——它们靠 grep 动态取 key，天然免疫脱敏，是生产正确形态。
4. 任何写 opencode/claude 配置的操作，改完先备份远端 `*.jsonc` 再执行，并 `cluster.py e2e` 验证。