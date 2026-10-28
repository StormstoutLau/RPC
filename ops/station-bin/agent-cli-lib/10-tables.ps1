# 10-tables.ps1 —— agent-cli 的**表数据**（review-p2-split 8C；从 agent-cli.ps1 整段抽出，行为不变）
#   · $Script:ROUTE_TABLE  —— route 别名 -> @{ id; station; cli }
#   · $Script:JUDGE_TABLE  —— review judge 别名 -> @{ type; id; station; ctx; egress; compliance; maxtokens }
# ⚠ 表里的数据是**唯一真值**：门禁与离线夹具都按 AST 提取**真表**验证（`_fm_golden_test.ps1`）。
#   改表只改这里，别在入口再抄一份。
# ⚠ 本文件由入口按 `$Script:AGENT_CLI_LIBS` 的**声明顺序** dot-source；
#   **不得**用 $PSScriptRoot 互相找（`split` 的 BOM 副本落在 TEMP，根会算错）。

# ---------------- ROUTE_TABLE (BP-2 alias->full-id, T3 task uses; fixed here) ----------------
# NOTE (2026-09-16): provider 名已统一为 `local`（三站 opencode.jsonc 实况: 仅 local + openrouter）。
# 旧名 'cluster-litellm/*' 已不存在 —— 沿用会让 _station_ready.sh 注入 ERR_INJECT exit 11、整条派发门挂掉。
# 模型 id 现为 `local/<flavor>`，flavor 与 local.models 声明键一一对应（保留风味/站点语义）。
$Script:ROUTE_TABLE = @{
    # alias -> @{ id=full-id; station=target }
    'nemotron'   = @{ id = 'local/nemotron';                          station = 'B' }
    'qwen'       = @{ id = 'local/qwen';                              station = 'B' }
    'gpt-oss'    = @{ id = 'local/gpt-oss';                           station = 'A' }
    'gpt-oss-20b'= @{ id = 'local/gpt-oss-20b';                       station = 'B' }   # O-13 sympy 收口卡 (B 站 20b, 2026-09-14)
    # ⚠⚠ **2026-09-24 实测修正（推翻 2026-09-21 的"缺凭据"归因）：zen（`opencode/*`）不是缺凭据，而是"需要 tty"**。
    #   证据①（非 tty ⇒ 挂死）：`printf '只回复一个词: ZEN_OK' | timeout 45 opencode run -m opencode/nemotron-3.5-lightning-free`
    #     ⇒ `RC=124`（45s 零产出）；DEBUG 日志显示请求**已发出**（`llm runtime selected llm.provider=opencode`），
    #     且**无任何 401/403/credential 报错** ⇒ **不是凭据问题**（三站 `auth.json` 为空/不存在，`auth list` = 0 credentials）。
    #   证据②（伪 tty ⇒ 可用）：**同一模型**套 `script -qec "opencode run -m <zen-id>"` ⇒ **`RC=0`，43s 返回 `ZEN_OK`**。
    #   证据③（对照组）：`openrouter/*` **普通管道**即 `RC=0`（≈16s）⇒ **只有 zen 这一路要 tty**；TUI 能用亦因它是真 tty。
    #   ⇒ **恢复 zen 不需要登录/凭据**，只需让**非交互派发路径**提供伪 tty（`script -qec`，或 `ssh -tt`）。
    #   ⚠ 但 `script` 会把 PTY 回显（banner + ANSI 控制字符 + "脚本启动于…"）混入 stdout ⇒ 会污染
    #     `out/.agent-output.txt`（连带 O-37 的字节计数与产物解析）⇒ **改运行时前须先设计输出净化**。
    #   ⚠ 复验工具：`_probe_opencode_provider.sh` 只测**非 tty**形态 ⇒ 对 zen **恒报 `RC=124`**，
    #     **不能用来判 zen 死活**；判 zen 须用**伪 tty 对照**（实验组 `script -qec` + 对照组 `openrouter` 普通管道）。
    #   ⚠⚠ **运行时路由结论（2026-09-24，稳定性采样 + 社区佐证）**：**不建议把 zen 免费档接回本表**。
    #     采样（`_zen_stability_sample.sh` 7 轮）zen 仅 **1/5 成功**，其后连续 4 次 152s 零输出（限流/空闲流卡死）；
    #     **官方标注这些免费模型"限时提供·收集反馈"**（`Nemotron 3.5 Lightning Free` 等 = 限时实验资产、随时可下架）
    #     ⇒ 稳定性无保证，不进运行时路由。三档**维持 openrouter**（`harness_priority` 前两档），zen 仅**人工试点偶用**。
    #     详见台账 O-43。
    #   新 id 取 `secrets/openrouter.conf` 的 **`harness_priority` 前两档**（该键是**权威真值**，本表只镜像，
    #   **不新立模型清单**）—— 与 `claude`/`claude-opus` 同源；站上 `openrouter` provider 已有 key 且实测可用。
    #   ⚠ **别名命名的是"档位"（快 / 高保真 / 1M），不是厂商** —— 故重指不改名、调用方零改动。
    #   ⚠ `free-1m` 的"1M"是**原 zen 型号的属性**，新 id 的 ctx **未核**（JUDGE_TABLE 里那个 ctx 字段同此）。
    'lightning'  = @{ id = 'openrouter/thinkingmachines/inkling:free';            station = 'B' }   # 快档 (原 zen: opencode/nemotron-3.5-lightning-free)
    'ultra'      = @{ id = 'openrouter/nvidia/nemotron-3-ultra-550b-a55b:free';   station = 'B' }   # 高保真档 (原 zen: opencode/nemotron-3-ultra-free)
    'free-1m'    = @{ id = 'openrouter/nvidia/nemotron-3-ultra-550b-a55b:free';   station = 'B' }  # alias of ultra
    # 2026-09-24 (D3 / P2-3): per-station 出网档别名 —— 解锁**跨站并行**（O-18 安全区：跨站各 1 并发）。
    #   与既有 `m27-q4ks-a/-b` **同构**（**同一 id**、不同 station）⇒ 不违"本表只镜像、不新立模型清单"
    #   （该纪律禁的是新立**模型**；此处未引入新模型 id）。
    #   用途：**O-20 / O-28 RC① 的正解** —— task 的目标站只能由本表决定（`-HostName` 对 task 无效），
    #   故"要指定站"唯一通道就是 per-station 别名。
    #   ★★ **O-147（2026-10-20 就地更正）**：上句有**一个例外** —— **默认出网档**
    #      （`$Script:EGRESS_MULTI_ALIASES` = `ultra` / `free-1m` / `lightning`）的站位**改由
    #      【候选站排序】定**（依据 = 本地按站计数，用得少在前；读不到 ⇒ fail-closed 按站轮转）⇒
    #      ★ 上句"只能由本表决定"**只对【非默认出网档】成立**；★ **要指定站**仍只认 per-station 别名
    #      （它们**不进候选** —— 这正是本批刻意分开的那条界）。
    #   前提核查（2026-09-24 实测，已过）：三站 `opencode` 1.18.25 一致 · `~/.config/opencode/opencode.jsonc`
    #   **md5 全一致**(755975db…) · `~/.config/rpc/openrouter.key` **三站各异**（独立账户 ⇒ 限流互不干扰）。★ 但见 `O-148`（2026-10-08 就地更正）：账户独立 ✓，而 **A / C 站上 `openrouter.ai` 出网【间歇性】失败**（DNS 错误应答）⇒ ★「限流互不干扰」**不等于**「跨站腿随时可用」。
    'ultra-a'    = @{ id = 'openrouter/nvidia/nemotron-3-ultra-550b-a55b:free';   station = 'A' }
    'ultra-c'    = @{ id = 'openrouter/nvidia/nemotron-3-ultra-550b-a55b:free';   station = 'C' }
    # `O-147` 甲（2026-10-07）：**补 `ultra-b`** —— ★ 三站里原先只有 A / C 有 per-station 句柄 ⇒
    #   **连"轮询句柄"都不齐**（配额负载均衡 乙/丙 的前置）。⇒ 补齐 = **纯登记**（同 id、`station='B'`，
    #   与上面的 `ultra` **等价**）· ★ **不改调度 / 零行为变化**（站位仍由本表唯一决定）。
    'ultra-b'    = @{ id = 'openrouter/nvidia/nemotron-3-ultra-550b-a55b:free';   station = 'B' }
    # ── 2026-09-24 采样用别名（`harness_priority` 档 1/3/4/5）**已撤除**（Scott 裁定）──────────
    #   采样结论**已入台账 O-49**：5 档在 opencode harness 路径下**全部可用**（档4 `super-120b` 最快 23s）——
    #   且 conf 注记的"harness-only(403) / laguna 限流(429)"**两条在 harness 路径均不适用**。
    #   故**不需要**常驻别名：要用时按 O-49 的 id 临时加回（或直接 `-Model` 走已定稳定档 `ultra`）。
    #   ⚠ 撤除的是**本表条目**，**不是模型清单**（`harness_priority` 是权威真值，未动）。
    # C 站 (seaviv) 2026-09-09: gpt-oss 本地引擎已注入 8080; nemotron 模型已传待启
    'gpt-oss-c'  = @{ id = 'local/gpt-oss';                           station = 'C' }
    'nemotron-c' = @{ id = 'local/nemotron';                          station = 'C' }
    # 2026-09-16: m27-q4ks (MiniMax-M2.7) / qwen3.8-flash-next UD-IQ4_XS 三站齐备 (C 源 -> A/B 已同步)
    # ⚠ 别名必须用站上 infer-load alias 空间真值 (m27-q4ks), 不是模型技术名 (minimax-m2.7) —— 见 cluster.py ROUTE 注
    'm27-q4ks'       = @{ id = 'local/m27-q4ks';                      station = 'C' }
    'm27-q4ks-a'     = @{ id = 'local/m27-q4ks';                      station = 'A' }
    'm27-q4ks-b'     = @{ id = 'local/m27-q4ks';                      station = 'B' }
    'flash-next'     = @{ id = 'local/qwen3.8-flash-next';            station = 'C' }
    'flash-next-a'   = @{ id = 'local/qwen3.8-flash-next';            station = 'A' }
    'flash-next-b'   = @{ id = 'local/qwen3.8-flash-next';            station = 'B' }
    # full id directly (M3 dual representation)
    'local/nemotron'              = @{ id = 'local/nemotron';              station = 'B' }
    'local/qwen'                  = @{ id = 'local/qwen';                  station = 'B' }
    'local/gpt-oss'               = @{ id = 'local/gpt-oss';               station = 'A' }
    'local/m27-q4ks'              = @{ id = 'local/m27-q4ks';              station = 'C' }
    'local/qwen3.8-flash-next'    = @{ id = 'local/qwen3.8-flash-next';    station = 'C' }
    'opencode/nemotron-3.5-lightning-free'  = @{ id = 'opencode/nemotron-3.5-lightning-free';  station = 'B' }
    'opencode/nemotron-3-ultra-free'        = @{ id = 'opencode/nemotron-3-ultra-free';        station = 'B' }
    # (上面两条 zen full-id **仅作 full-id 解析之用**; ⚠⚠ 触发条件**不是凭据** —— 2026-09-24 实测:
    #  非 tty ⇒ RC=124 挂死 / 伪 tty(script -qec) ⇒ RC=0, 且 DEBUG 显示请求已发出、**无 401/403**;
    #  三站 auth.json 空或不存在、auth list = 0 credentials(2026-09-30 复测仍 0)
    #  ⇒ **它要的是 tty, 不是登录**。原文"补 opencode auth login 即可用"是**已推翻**的旧归因
    #  (见本表上方 2026-09-24 段, 以及台账 O-43 / O-07 的 2026-09-30 收口)。)
    # 站上 openrouter 的两个档位 full-id (与上面 local/* 同例: 使 `--model <id>` 与 env AGENT_FALLBACK_MODEL 可解析)
    'openrouter/thinkingmachines/inkling:free'          = @{ id = 'openrouter/thinkingmachines/inkling:free';          station = 'B' }
    'openrouter/nvidia/nemotron-3-ultra-550b-a55b:free' = @{ id = 'openrouter/nvidia/nemotron-3-ultra-550b-a55b:free'; station = 'B' }
    # O-15 claude 备通道 (2026-09-12): 控制台本地执行, station 空 = 不走 ssh. cli=claude 选中本地执行器.
    #   id = 传给 `claude -p --model` 的型号。
    #   ⚠ **2026-09-21 修正（实测，阻断级）**: 原为 **Claude 原生 id**(claude-sonnet-4-5 / claude-opus-4-1) ——
    #     控制台 claude 已切 **OpenRouter** 后，这些 id 会被 OpenRouter **路由到真实 Anthropic 上游** ⇒
    #     **必 403 `This model is not available in your region.`**（实测三个 Claude 原生 id 全 403；
    #     `thinkingmachines/*:free` 与 `nvidia/*:free` 均 `OK`）。⇒ 免登录只解决认证、**不解决可用性**。
    #   现 id 取 `secrets/openrouter.conf` 的 **`harness_priority`** 前两档（该键是权威真值，三处消费方从此镜像；
    #     本表只镜像其前两项，**不新立模型清单**）。
    #   别名 `claude` / `claude-opus` **保留原名** —— 它们命名的是**备通道档位**(默认/高保真)，不是厂商。
    'claude'       = @{ id = 'thinkingmachines/inkling:free';          station = ''; cli = 'claude' }   # 默认备份型号
    'claude-opus'  = @{ id = 'nvidia/nemotron-3-ultra-550b-a55b:free'; station = ''; cli = 'claude' }   # 高保真备路
    # full id 直传 (与上面 local/* 同例): 使 `--model <openrouter-id>` 与 env `AGENT_FALLBACK_MODEL` 可解析
    'thinkingmachines/inkling:free'          = @{ id = 'thinkingmachines/inkling:free';          station = ''; cli = 'claude' }
    'nvidia/nemotron-3-ultra-550b-a55b:free' = @{ id = 'nvidia/nemotron-3-ultra-550b-a55b:free'; station = ''; cli = 'claude' }
    # ── 2026-09-25: **站上 claude + OpenRouter** per-station 别名 ─────────────────────────────
    #   解锁的"锁": P3(2026-09-21) 把 claude 通道收窄成「local-only ⇒ 站上 + 站上本地引擎」/
    #   「其余 ⇒ 主控本地 spawn(OpenRouter)」⇒ 站上 claude **永远配不了 OpenRouter**。
    #   而 design 表里 `public`/`sanitized` 那一行本就写着"站上跑 claude + OpenRouter(按站独立 key)"
    #   (见 docs/research/2026-09-21_D6备路站上化与sensitivity设闸调研与方案.md §3.1) —— 那一支从未落地。
    #   与 `ultra-a`/`ultra-c` **同构**(同一 id、不同 station ⇒ 不新立模型清单)。
    #   用途: ① 三站各 1 并发且**各有独立 OpenRouter 账户** ⇒ 限流互不干扰;
    #         ② 绕开主控单点(3 个 claude 挤一台机器 + 一个账户)。
    #   ⚠ 站不可用 ⇒ **不作静默换站**(用户裁定 2026-09-25): 拒跑并**列出可用替代站**供裁定。
    'claude-a'     = @{ id = 'thinkingmachines/inkling:free';          station = 'A'; cli = 'claude' }
    'claude-b'     = @{ id = 'thinkingmachines/inkling:free';          station = 'B'; cli = 'claude' }
    'claude-c'     = @{ id = 'thinkingmachines/inkling:free';          station = 'C'; cli = 'claude' }
}
# JUDGE_TABLE: review-model alias -> @{type; id; station; ctx; egress; compliance}
#   type 'egress'      = opencode gateway on B (outbound, NOT for local-only)      [src ② ultra]
#   type 'local'       = console opencode CLI (npm i -g opencode-ai)               [src ⑤ main]
#   type 'http'        = OpenAI-compatible /v1 (commercial hook, ENV-injected)     [src ① commercial]
#   type 'http-local'  = OpenAI-compatible /v1 to station engine (load-gate)       [src ③ rpc / ④ m27]
# ⚠ **W1a (2026-09-21): `egress` 与 `compliance` 从"声明了但没人读"变成真判据** ——
#   此前 `compliance` **全仓只有声明、无任何读取点**（假防线，见 OPEN-ISSUES「消毒面 ≠ 出网面」缺口③），
#   实际生效的是"只挡 local-only"的窄判据。现在两个字段都由真值函数读取：
#     `Get-JudgeEgress`（读 `egress`；**缺字段 ⇒ 回退按 type 推、仍未知 ⇒ 视为出网**，fail-closed）
#     `Get-JudgeComplianceReject`（读 `compliance`；`all` = 全放行；**缺字段 ⇒ 拒**，fail-closed）
#   ⇒ **新增一个 judge 必须同时声明这两个字段**（夹具 `_fm_golden_test.ps1` 有覆盖率断言钉住）。
$Script:JUDGE_TABLE = @{
    # 2026-09-21: id 从 zen(`opencode/nemotron-3-ultra-free`, **当前不可用**) 重指到**站上 openrouter**;
    #   ctx 值经厂商 API 核实 (`/api/v1/models` ⇒ 1000000), 非沿用旧值。见 ROUTE_TABLE 处同一段说明。
    'ultra'       = @{ type='egress';      id='openrouter/nvidia/nemotron-3-ultra-550b-a55b:free'; station='B'; ctx=1000000; egress=$true;  compliance='public,sanitized'; maxtokens=2500 }
    'free-1m'     = @{ type='egress';      id='openrouter/nvidia/nemotron-3-ultra-550b-a55b:free'; station='B'; ctx=1000000; egress=$true;  compliance='public,sanitized'; maxtokens=2500 }
    'main'        = @{ type='local';       id='main-opencode-cli';               station='';  ctx=1000000; egress=$false; compliance='all'; maxtokens=4000 }
    # `commercial` 是 **ENV 注入**的外部 /v1(K 与 base 都由调用方给) ⇒ 默认按**出网**处理。
    #   若把它指向**本地**端点: 必须**同时**改 `egress=$false` 与 `compliance='all'`（两处一起改，别只改一处）。
    'commercial'  = @{ type='http';        id='commercial';                      station='';  ctx=131072;  egress=$true;  compliance='public,sanitized'; maxtokens=2500 }
    'm27'         = @{ type='http-local';  id='local/m27-q4ks';                  station='C'; ctx=131072;  egress=$false; compliance='all'; maxtokens=8000 }
    'rpc-v4flash' = @{ type='http-local';  id='cluster-v4flash';                 station='C'; ctx=1000000; egress=$false; compliance='all'; maxtokens=8000 }
}
