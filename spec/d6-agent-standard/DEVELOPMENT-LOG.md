# 开发日志：D6 agent-cli wrapper 框架（Development Log）

***

id: d6-agent-standard-DEVELOPMENT-LOG
type: dev-log
version: 1.0
status: active（持续维护中）
date: 2026-09-03
depends: \[d6-agent-standard-DESIGN, d6-agent-standard-CHECKLIST, d6-agent-standard-OPEN-ISSUES]
upstream: \[d6-agent-standard-.* 全量文档]
------------------------------------------------------------------

> **用途**: D6 框架（主控站 agent-cli wrapper + 跨站派发 + 评审/看板/栅栏闭环）的**唯一演进史**——按里程碑时间线回溯记录「何时做了什么、为什么、验收证据、关联 O-xx」，并预留持续追加。与 DECISIONS（为什么这么做）互补，不重复其决策推演。
> **规则**: 新里程碑**追加在最新的日期章节顶部**（时间倒序）；每条含 日期 / 事件 / 涉及文件 / 验收证据 / 关联条目；闭环事件的验收证据以链接回填，不在此铺细节。
> **追加者**: 每次重要落地/闭环后由 Scott 或执行体回填。

***

## 历史回溯（2026-09-03 起）

### 2026-09-16 — provider 命名漂移修复 / 新模型入网 / C2 引擎面统一日

> 本章为补记（当日未即时落档，2026-09-16 晚由用户指示「修复记录 / 排查过程 / 决策依据完整落档」一次性回填）。
> 决策推演全文见 [ADR-0004 第五批 + 补记 + 补记二](../../adr/ADR-0004-统一管理入口为唯一管理面.md)、[ADR-0003 免费档计数/硬限速](../../adr/ADR-0003-OpenRouter密钥与egress路由管理.md)；本节只记**何时做了什么 / 怎么查出来的 / 证据**。

- **① provider 命名漂移修复（P0，命中「已闭环」的 G1 自身）—— 排查过程**:
  触发=用户「已定案的几个问题执行闭环」。**排查路径**：不读文档，直接从统一入口查三站 config 实况 ⇒ `~/.config/opencode/opencode.jsonc` **只有 `local` + `openrouter`**，`cluster-litellm` 已不存在；但 [agent-cli.ps1](../../ops/station-bin/agent-cli.ps1) 的 ROUTE_TABLE、[_station_ready.sh](../../ops/station-bin/_station_ready.sh) 的注入段、`agent-cli-smoke.sh`、`a5-nextday-verify.sh` **仍全部引用旧名**。`_station_ready.sh` 第[3]步**强制要求** config 存在 `cluster-litellm` 块（否则 `ERR_INJECT exit 11`），而它在**派发路径上** ⇒ **整条 `task` 派发门实际不可用**（不是"文档过时"，是门坏了）。
  **决策依据**：用户裁定「资产跟随现状」（不改 config 回旧名）。关键实测=**opencode 拒绝未在 `models` 中声明的模型名**（`local/nemotron` → UnknownError；`local/main` → 正常解析）⇒ 单纯塌成 `local/main` 会丢"风味/站点"语义 ⇒ 采「**在 `local` 下声明多模型 + 资产纯前缀替换**」。
  **落点**: 三站 `local.models` 声明 `gpt-oss`/`gpt-oss-20b`/`nemotron`/`qwen`/`qwen3.8-flash-next`(ctx 262144)/`m27-q4ks`（三站一致哈希 `d765c81f…`）；`agent-cli.ps1` ROUTE_TABLE 全量 → `local/*`、`$TpBench` 键改名并补 m27-q4ks(21.5)/flash-next(19)（取自 THROUGHPUT-BASELINE，无虚构）、slot-gate/split 判据 `-like 'local/*'`、review 默认 → `local/nemotron`；`_station_ready.sh` 注入目标改名；smoke 脚本补 C 站节；`cluster.py` `STATION_ROUTES` 补条目。
  **纪律沉淀**：**任何 provider / 别名 / 端口改名，必须 grep 全仓引用方（不只文档）**。
  关联: G1、O-14、ADR-0004 第五批。

- **② 新模型三站入网（m27-q4ks / qwen3.8-flash-next，UD-IQ4_XS）**: 取证先行 —— A 站两模型**都缺**、B/C 已有 ⇒ 实际只需 **C → A**（~202GB）。走 A↔C USB4 直连段（rtt 0.17ms）`rsync -a` 双路并行；**逐字节一致**（MiniMax 108,413,781,312 B；Qwen 93,682,584,224 B）。三站建 `~/.config/rpc/llama-instances/*.env`；[inventory/models.yaml](../../inventory/models.yaml) 登记（flash-next **保持默认路由 B**，不静默改既有行为）。⚠ 排查中踩坑：**PowerShell 会剥掉 ssh 命令里的内层双引号**（`nohup bash -c "…"` 被拆 ⇒ rsync 收到错参**静默不传**）⇒ 改写为无嵌套引用的独立后台命令 + `setsid nohup` + 日志。

- **③ 命名回归修正（当日引入、当日修，自曝）**: 上一步我**照模型技术名自造** `minimax-m2.7`，而站上规范别名是 **`m27-q4ks`**（`infer-load` 内本就带归一化 `sed 's/^minimax-m2.7.*/m27-q4ks/'`，`infer-list` 第一列即真值，`tests/b5q/*` 与 review judge 别名 `m27` 早已用它）⇒ 实测 `infer-load minimax-m2.7` 直接 **`ERROR: 无匹配`**，三站 `minimax-m2.7.env` 成**孤儿 conf**。**决策依据**：用户选「三项全做」= 全链改名 + 删孤儿 conf + 修 infer-load 匹配。**纪律**：**别名必须以 `infer-list` 的 alias 空间为准，不得照模型技术名自造**（已写入 `cluster.py` ROUTE 注释）。
  连带修 `infer-load` **匹配逻辑两缺陷**：原实现只有 `grep "^${PREFIX}"` ⇒ (a) **传精确别名也判歧义**（`gpt-oss-120b` 同时是 `gpt-oss-120b-fable-5-distilled` 的前缀 ⇒ `load gpt-oss-120b-b` exit 1）；(b) **PREFIX 未转义**（`.` 是正则通配）。改为「候选集全列 → 精确相等者胜出 → 否则才走唯一前缀」，比较用 shell `case` 按字面串。**验收**：`infer-load gpt-oss-120b` 不再报歧义、`zzz-nomatch` 仍报无匹配、三站 `bash -n` OK。

- **④ C2 引擎面统一为 studio 固定 `:8080`（本日最大决策，废弃 config 注入机制）—— 排查与决策链**:
  1. **问题起点**：前一步的注入机制把 `local.baseURL` **持久改写**成当次引擎端口（B 被写成 `:50889`）⇒ 任务后三站 config 漂移、`stations` 门禁转红（pre-push 拦下）。
  2. **探测（用户指示「先探测 studio 并发端点」）**：`unsloth studio run --help` 实证 `--host/--port/--path/--api-prefix/--reuse-port` 属 **managed flag 被拒收** ⇒ 内层 llama-server 端口**不可指定**（实测随机 40007/50031/50889）；且 `:8080` 是 **三协议网关**（OpenAI `/v1/chat/completions` 200、**Anthropic `/v1/messages` 200**、`/v1/responses`），`/v1/models` 自带 `context_length`，`/api/health` 免 key 200，`/slots` **404**。⇒ **C1（固定内层端口）不可行；C2 可行。**
  3. **slot-gate 数据源替换（选项 3 实测成功）**：`/api/inference/active-generations` 空载 `count=0`、忙态 `count=1` 且 `parallel_slots=4` ⇒ **优于 `/slots`**（直接给并发生成数+上限，无需逐槽聚合）。映射 `count→SLOT_BUSY` / `parallel_slots→SLOT_TOTAL` / `QUEUE=0` ⇒ **输出契约不变，`Invoke-SlotGate` 与 wrapper 零改动**。
  **落点**: [infer-load](../../ops/station-bin/infer-load) 加载后把 studio 重铸的 key **落盘** `~/.config/rpc/unsloth.key`；[_station_ready.sh](../../ops/station-bin/_station_ready.sh) **删注入 + 删端口发现**（端口固定 8080，判据 `/v1/models`(带 key) + `/props` + chat）；[_slot_gate.sh](../../ops/station-bin/_slot_gate.sh) 换数据源；[agent-cli.ps1](../../ops/station-bin/agent-cli.ps1#L208) 就绪断言 `INJECT_OK` → `CHAT_OK`；[cluster.py](../../ops/cluster.py) **读码确认无需改**（其 `curl :8080/health` + "任意 HTTP JSON 即在线" 判据本就覆盖 unsloth 的 `{"detail":…}` 404）。
  **验收（加载态端到端）**: `_station_ready` → `STATION_READY port=8080` + `CHAT_OK choices=1` + `READY_OK`(rc=0)；`_slot_gate 8080` → `SLOT_TOTAL=4 SLOT_BUSY=0`；wrapper 全链 `SLOT-GATE(idle,allow)` → `TASK_RC=0` → **`TASK_DONE exit=0`**；**claude `rc=0 / 36s / OK`**（此前必坏）；**config md5 全程恒定 `755975db…`**（注入不再发生）；三站 `infer-unload` OK。
  **连带修好**: ① claude 路径（其 `:8080` 目标一直正确，真因是 **key 陈旧**非端口）；② C 站 key 占位串（22B `sk-local-noauth…`，即门禁那盏黄灯）由落盘机制自动纠正。**【2026-09-16 更正】** 后半句当时是**错的** —— `infer-load` 只重铸落盘 `unsloth.key`，**从不写 `claude.key`**（claude 侧另存一份拷贝且无任何写入方），故占位串不会被自动纠正；真实修法见 ⑨。
  **诚实记录 —— 过程中修掉我自己两个判据缺陷**: (a) chat 就绪判据原看 `content` 非空 ⇒ **reasoning 模型在 `max_tokens` 小时把配额全给 thinking、无 `content` 字段** ⇒ 假失败；改看 `"choices"`。(b) 原请求**缺 `Content-Type: application/json`** ⇒ curl 默认 form-urlencoded ⇒ 引擎 Pydantic 报 `body: Input should be a valid dictionary`；**且旧实现的 `CHAT_OK` 一直是假阳性**（匹配到的 `"content":""` 来自非正常响应）——"能报 OK" ≠ "真的 OK"。
  关联: O-19、O-25 P1、ADR-0004 第五批 / 补记二。

- **⑤ OpenRouter 免费档每日计数 + 硬规则限速（G13/O-07 扩展）**: 调研先厘清**两个出站源**（zen vs OpenRouter）—— 用户问的是 OpenRouter。实证：20 请求/分（固定，充值不升）+ 每日 **50（从未充≥$10）/ 1000（曾累计充≥$10）**；429/失败**仍计入**配额；**跨 key 全局治理**；**无"免费请求剩余数"可查 API**（`GET /api/v1/key` 的 `usage` 是 credits）。⇒ 结论：**可建，但只能本地自建计数**。落地：`cluster.py egress` 读 `is_free_tier` 定档位 + `.egress_daily.json` 本地日计数（UTC 滚动）+ 80% 预警，调用方发请求前 `_egress_bump()`。**实证**主控 + A/B/C 四端 `tier=paid` ⇒ 本账户日限额 **1000/天**。
  **硬规则（用户拍板「RPM20 限速 + 429 退避」）**：`Invoke-JudgeHttp` 加 **最小 3s 间隔令牌桶** + **429 指数退避**（`attempt<3 → Sleep 2^(attempt-1)`）；`Invoke-RestMethod` → `Invoke-WebRequest -UseBasicParsing`（PS5.1 才能拿状态码）。**验证**：本地假 OpenRouter（429→429→200）端到端 —— 相邻请求拉到 ≈3s、429 后 ≈1s 退避 → `JUDGE_OK`。日 1000 维持软预警，**只在经 wrapper 的出口限速**（opencode 内部 HTTP 拦不到，靠 429 兜底）。
  ⚠ **BOM 坑再度踩中**：Edit 改 `agent-cli.ps1` 剥掉 UTF-8 BOM ⇒ PS5.1 按 CP936 读中文注释**级连误报 38 个语法错**（全假阳性）；补回 `EF BB BF` 后 14 个 `.ps1` 全绿。**凡编辑此 .ps1 必查 BOM。**
  详见 [ADR-0003](../../adr/ADR-0003-OpenRouter密钥与egress路由管理.md)；关联: G13、O-07、O-16。

- **⑥ G8 收口（三站补装）+ 环境隔离选型定案**: G8 原定案（sympy 装两站 / R 走 CRAN 4.6.x）**实际未落地** ⇒ 按用户拍板补装三站：sympy **1.14.0** / numpy 2.5.3 / scipy 1.18.1 / **antlr4 4.11.0** / **R 4.6.1**（CRAN noble-cran40，对齐主控）。功能级验收 `parse_latex(r'\frac{1}{2}')` → `simplify(x-1/2)==0` 全 True。
  两个留档坑（均为"判据自证"续集）：**antlr4 必须钉 4.11**（sympy 1.14 硬校验 `antlr4.__version__=="4.11"`，装最新 4.13.2 时 `import`/`pip show` **看着全对**，直到功能级 `parse_latex()` 才抛 ImportError ⇒ **"包在" ≠ "功能在"**）；**CRAN 源签名两连坑**（换新 key + `signed-by` keyring 必须 gpg 二进制格式，否则 `NO_PUBKEY` 后**静默回落默认源装了 4.3.3**，`apt install` 照样"成功" ⇒ 第一轮"安装成功"是假象）。
  环境隔离选型（问卷式假设"项目间依赖冲突"）：**不采用容器化/沙盒**，用**语言级**隔离（Python → venv/uv，R → renv），容器仅极端兜底（首选无 daemon 的 Apptainer）。四理由=威胁模型不同 / 零自加载纪律 / agent 外壳资产会被切断 / lockfile 对拍精度更优。**待办**：Cpp_Hub 对拍 R 依赖包（7 个）装**项目 renv，不装全局库**。
  关联: G8、G9、O-13；详见 [ADR-0004 附表](../../adr/ADR-0004-统一管理入口为唯一管理面.md)、[Agent调研 §9.10](../../docs/Agent跨项目调用标准与迁移复用调研.md)。

- **⑦ 统一入口能力增强 + 缺口综合汇总 + 文档去时态化**: ① `cluster.py providers` 增**两维**（`_ep_form()` 端点形态：`:4000` 标"⚠ 网关已退役"；`### mem` 记忆层：memory.db 大小 + MEMORY.md/summary 行数）—— 起因是用户问"是否还过 :4000 网关"与"记忆协同层现状"，而 `providers` 当时**答不了**⇒ 按 D3 路径① 给入口加能力而非新增脚本。**实测**：三站**零 `:4000`**（opencode/claude 全 `127.0.0.1:8080`）⇒ **已全直连**，用户记忆正确；**记忆层正主 = opencode 自带 memory**（`~/.local/share/opencode/memory.db` + `memories/MEMORY.md`），**非**文档所记的 `codex-memory` 独立命令（三站 `command -v` 均未命中）—— A 最饱满（MEMORY.md 88 行）、B/C 有库近空（内容在 `-wal` 待合并）。② G1-G14 缺口综合汇总入台账（见 [OPEN-ISSUES §6](OPEN-ISSUES.md)，结论 **8 闭环 / 5 已定案 / 1 待办**）。③ [Agent跨项目调用标准与迁移复用调研.md](../../docs/Agent跨项目调用标准与迁移复用调研.md)：§1.1 补 C 站现状、**§2.1 CLI 定版表去时态化**（原表仍是"直连/过网关混合 + B-claude→LiteLLM(4000)"的过时描述，改为按统一入口现状的**无时态形态表**）、§6 缺口清单补"当前完成情况"列、新增 §9.10（隔离选型）/§9.11（G14/G10 升级回归 SOP）。

- **⑧ Cpp_Hub 假子模块（unmapped gitlink）排查与吸收（A1，用户拍板）**:
  **症状**：`git status` 常驻 ` M spec/d6-agent-standard/Cpp_Hub`。
  **排查链（六条取证，全部机械可判定）**：① 该路径是 mode **160000** gitlink @`88f8fbf`，而 `.gitmodules` 不存在 ⇒ `git submodule status` 直接 `fatal: no submodule mapping`（**结构性非法**）；② 目录内是真 `.git` **库**（独立 2 条提交、**无 remote**、工作区 clean）；③ **决定性**：外层库对象库里那两个 commit **都不存在**（`git cat-file -t` → `fatal: could not get object info`）⇒ **内容零备份**：GitHub 远端同样只有指针，clone 后该目录为空；④ **引入点** = `5f2b395`（09-14 00:06 脱敏大提交里的广域 `git add` —— git 对"含 `.git` 的子目录"默认收成 gitlink）；⑤ **孤儿化** = `cc3b75c`（09-14 12:19 把 `PROJECTS['Cpp_Hub']` 改指 `F:\Cpp_Hub`，提交信息自认"**gitlink 薄壳**"，但**没顺手摘指针**）；⑥ **漂移源** = nested 09-15 20:19 第二条提交（`2666e88`）与记录指针分叉。
  **决策依据（A1）**：逐案对比 —— **B 正式 submodule** 须**为 6 文件 / 约 4KB 新建一个远端仓**、克隆语义全局变更（`--recurse-submodules`）、且噪声只是变形成"指针待更新"（**成因未切**）；**C 解除跟踪+忽略** 把最重的"内容无远端备份"原样留着（07-04 那类坑）；**D 冻结指针** 坏结构 100% 保留且 nested 一提交**必然复发**；**E 整体删除** 会失去 `cpphub-001` 的 golden 断言对象（比现状更不自洽）⇒ **A1 是唯一同时消掉「永久噪声 / 备份缺口 / 假子模块」三类危害且不引入新机制者**，且经核实 `agent-cli.ps1` **全文不读 git**（对 wrapper 零影响）、「试点须为 git 仓库」约束的是**站上工作区**而非主控样本（吸收不违反）。
  **执行（备份优先，遵守 07-04 教训）**：先在 OneDrive `RPC-backup/20260916-Cpp_Hub-gitlink/` 落 **`Cpp_Hub-all.bundle`**（`git bundle verify` = "The bundle records a complete history"）+ **整目录副本**（51 文件、与源**零差异**）；再删 `Cpp_Hub/.git` → `git rm --cached` 摘指针 → `git add` 吸收 6 个实体文件。
  **验收（4 项机械判据）**：① 6 个 blob 哈希与 nested **逐一相同**（`c89cd00a`/`4e19cf5c`/`a1ea2d40`/`f2581721`/`7aef6813`/`8f596feb`）⇒ **字节一致**，`autocrlf=true` 未改内容；② 同 6 个 blob 在外层库 `git cat-file -t` 现返回 `blob`（此前 fatal）⇒ **内容真入库**；③ `git write-tree` + `ls-tree -r` 显示该目录下 **6 条 `100644 blob`、零 `160000`** ⇒ clone 后必得这 6 个文件；④ 索引中 gitlink 计数 **0**、`agent-out/` 仍 `!!` 忽略（吸收的 `Cpp_Hub/.gitignore` 随目录生效）。门禁 quick **9 绿 / 0 黄 / 0 红**。
  **过程中我的验证写法又自曝一缺陷**：用 `git ls-files | git checkout-index --stdin` 做"索引实体化"取证时，**PowerShell 管道把路径啃坏**（4 个 ASCII 名报 `is not in the cache`、2 个中文名反而成功）⇒ **判据假失败**；改用 `write-tree`+`ls-tree` 机械取证。**"判据要先自证"再记一笔。**
  **关联登记（均经用户裁定）**：① **`cpphub-001` 卡与 `PROJECTS` 映射已不一致** —— 该卡 golden（`cpphub_golden.py`）断言 `src/因子计算_核心.cpp`（= 轻量样本结构），而 `Cpp_Hub` 自 `cc3b75c` 指 `F:\Cpp_Hub`（`include/cpphub/core/math.hpp` 结构），且 wrapper **无 per-card 源目录覆盖键**（sync 源严格取 `PROJECTS[$proj]`）⇒ **今天重跑必 golden FAIL**（真源卡是 `cpphub-beta`）—— **暂不动，仅登记**（见 [OPEN-ISSUES](OPEN-ISSUES.md)）。② **暂不加「unmapped gitlink」门禁断言**（该机制纯机械可判定、可正负自证，本可堵住复发路径），仅落档备查。

- **⑨ 凭据面单一真值修正（claude key 第二定义点，凭据黄灯清零）**:
  **症状**：全量门禁 `stations` 黄灯，明细是 **B 站与 C 站**（不止 C）`claude.key` 与同站 `unsloth.key` 不一致。
  **排查链**：① 走统一入口取实况（不翻站上文件）⇒ `secrets status` 只报"落点/权限"（三站全 OK）⇒ 它是**浅判据**，差异只在 `stations` 的深判据里；② 比对主控正本 ⇒ A/B 的 `claude.key == unsloth.key`（43B `sk-unsloth-<32hex>` 真 key），**C 站两份都是脱敏占位串**（`claude.key` 15B 与 `unsloth.key` 22B，均为 09-14 `5f2b395` 密钥脱敏残留的占位值）；③ 读 helper 真身 `secrets/stations/*/claude-key.sh` = `cat $HOME/.config/rpc/claude.key` ⇒ **`claude.key` 是引擎 key 的第二份拷贝**；④ 读 [infer-load](../../ops/station-bin/infer-load) ⇒ 它**只重铸落盘 `unsloth.key`**，`claude.key` **没有任何写入方** ⇒ 该文件必然陈旧（C 是脱敏遗留；A/B 只是 09-14 靠**人工**同步过一次才对上）；⑤ 站上实测 ⇒ **B 站 `unsloth.key`（44B `f738fdec…`）≠ 主控正本 B（43B `c0c883ff…`）** ⇒ **B 站早已被"加载后 key 变新、claude.key 仍旧"命中**（门禁那条**硬编码"C 站"的告警文案**让我上一轮误判为 C 独有 —— 文案本身也是缺陷，已一并修）。
  **决策依据（方案 A：单一真值）**：同一份密钥有**两个定义点**是病根（与 `cluster.py` 中"抄一份就是第二个定义点"的既有纪律同源）⇒ ① `claude-key.sh` 改读 `unsloth.key`（claude 与 opencode 共用一份，第二份拷贝**退役**）；② 门禁判据由"两文件互相比较"升级为「**helper 的实际输出 == 同站 `unsloth.key`**」—— 这是功能判据（claude 真正拿到的 key），且**不因构造而恒真**（仍能抓到"绕过 `infer-load` 手动改 key"）；③ 备选"让 `infer-load` 同时写两个文件"被否：留双份拷贝、且判据随即变成构造上恒真。
  **执行**：正本 3 个 `claude-key.sh` 改写（46B / LF / 逐字节自校）+ 删除 3 份 `claude.key` 正本 → C 站**真跑一次 `cluster.py load qwen3.8-27b-mtp`** 铸真 key（`sk-unsloth-<32hex>`，33s 就绪）→ **回写 B/C 站真 key 到主控正本** → `secrets push`（A 4 / B 3 / C 3，幂等）→ `rm` 三站遗留 `claude.key`（**`push` 是增量的、不剪枝**，必须显式删）→ 卸载 C 恢复状态。
  ⚠ **过程中发现一个真陷阱（我原定顺序差点踩）**：`secrets` 只有 `status|scan|push`（**单向下发、无回写**），而站上 `unsloth.key` 是**每次加载重铸**的 ⇒ 直接 `push` 会用正本里的陈旧 key **覆盖站上真 key**，把该站 opencode/claude 打断。正确顺序只能是「站上取真值 → **先回写正本** → 再 push 才幂等」，本次据此先回写了 B/C 两个站。
  **验收**：① 三站 helper 输出长度与各站 `unsloth.key` 一致（A 43 / B 44 / C 44）；② 三站 `claude.key` 已不存在，落点收敛（A = helper+openrouter+rpc+unsloth；B/C = helper+openrouter+unsloth）；③ 正本 vs 站上逐一 MATCH；④ **全量门禁 `stations` 凭据告警清零**（明细仅剩 A 站 `claude-plugins-official`，属 `inventory/plugins.yaml` 早已登记的 `known_drift`，非本次范围）；⑤ 三站 `infer-unload` OK。
  **两处新增登记（见 [OPEN-ISSUES](OPEN-ISSUES.md)）**：① **`infer-load` 的 key 明文输出** —— 原记为"写进站上日志"，**表述有误，已在 ⑩ 更正**：该行 `log` 只打 **stdout**（进调用方控制台/会话 transcript），而站上日志里的 key 是 **studio 自己**写的、且 `infer-load` 正是从该日志 grep 取 key；真实暴露面比原记大得多（含审计盲区），见 ⑩；② **`secrets push` 的正本陈旧覆盖危害**（上述陷阱）目前靠"加载后先回写正本"的人工纪律兜住，可考虑加门禁断言（"站上 `unsloth.key` ≠ 正本 ⇒ WARN"）。
  关联: O-16、ADR-0003 D1（正本兜底为已定案，本次不改设计，只补"回写"这一必需步骤）。

- **⑩ unsloth studio 日志的明文面收敛（审计盲区补齐 + 权限收紧 + 存量脱敏）**:
  **触发**：用户要求"对 ⑨ 登记的两点（文档明文/掩码写法、`infer-load` 的 key）调研是否需要修"。取证后**更正 ⑨ 的错误表述并扩大范围**。
  **取证的六条事实（全部实测）**：① `log()` 只 `echo` 到 **stdout**，不写文件（[infer-load:21](../../ops/station-bin/infer-load#L21)）⇒ 我方那行的暴露面是控制台/transcript，**不是**站上日志；② **studio 自己把 key 写进 `~/.unsloth/run-<alias>.log`，每次加载 4 处**（`infer-load` 正是 `grep -oE "sk-unsloth-…" "$UN_LOG"` 从它**取**key ⇒ "日志含 key"是**设计使然、消除不掉**）；③ 权限：`~/.unsloth` = **775**、`run-*.log` = **664** ⇒ **组与其他用户可读**；④ 存量累积无上限：A 站 **15 份**（含 2 份 `.pre-repro-*` 副本）、B 4 份、C 2 份 ⇒ 合计 **21 份日志 / 68 处明文 / 16 个历史 key 值**；⑤ **最关键**：`cluster.py secrets scan` 只探 `~/.config/rpc` + `opencode.jsonc` + `settings.json` 及备份，**从不看 `~/.unsloth/*.log`** ⇒ 这 68 处明文**在框架明文巡检的视野之外**（09-14 那轮"明文面收敛"未覆盖，现有门禁也永远发现不了）；⑥ 严重度不夸大：key 是 studio **每次加载重铸**的本地引擎令牌（仅绑 `127.0.0.1`）⇒ 历史值多已随实例销毁失效，真风险是"当前运行实例那把是活的 + 任何 `$HOME` 级备份会外流 + 审计盲区本身"。
  **决策（用户拍板全套 a+b+c+d+e）**：
  | 项 | 动作 | 落点 |
  |---|---|---|
  | a | 我方那行改**掩码**：`log "API Key: $UN_KEY"` → `log "API Key ok (len=… sha8=…)"` | `infer-load`（保留"同一把 key"的可关联性，不泄露材料） |
  | b | **权限收紧**（新加载 + 存量）：目录 `700`、日志 `600`；由 `infer-load` 每次加载强制 | `infer-load` 新增 2 行 chmod |
  | c | **存量就地脱敏**：`sed` 把日志里的 key 掩成 `sk-<prefix>-****` | 三站 21 份日志（**不留含 key 的备份** —— 备份会重建泄露面；改为"临时件+行数/命中数双校验+替换"，逐份校验通过才落盘） |
  | d | **补审计视野**：`stations` 门禁的 `[cred]` 探针新增 `unslothlog=dirperm/files/withkeys/loose`，判据落在**权限**（目录须 700、日志须 600）而非"含不含 key"（后者无法消除） | [rpc_check.py](../../ops/rpc_check.py) |
  | e | 补登「已知剩余明文面」 | [密钥轮换清单](../../docs/security/2026-09-13_密钥轮换清单.md) |
  **执行与验收**：① 三站备份原件 → scp → `sudo install -m 755` ⇒ 三站 sha 一致 `8155968d…`、`bash -n` OK；② 站上 21 份日志脱敏 ⇒ `withkeys 0`、行数逐份不变（校验不通过即 SKIP，未发生）；③ 目录 700 / 日志 600 ⇒ `loose 0`；④ **端到端实跑**（`infer-load` 在加载路径上，不能只靠 `bash -n`）：C 站 `load qwen3.8-27b-mtp` ⇒ `API Key ok (len=43 sha8=9de8ff4d)`（**输出已无明文**）+ `dir=700 / log=600`，随后卸载 C；⑤ **负向自证**：把 C 站目录改 755 + 一份日志改 644 ⇒ 门禁**确实报出**两条（"`~/.unsloth` 权限 755 (应 700)"、"1 份 run-*.log 权限非 600"），恢复后复跑无误报；⑥ 全量门禁 **13 绿 / 1 黄 / 0 红**（余黄灯仍是 `inventory` 已登记的 A 站插件 `known_drift`）；⑦ 新 key 按 ⑨ 的纪律**先回写主控正本**。
  **① 那一项的结论（文档掩码写法）**：**不改判据逻辑**，只在 `secrets` 检查的处置建议里补一句"文档引用样串/占位串请掩码为 `sk-xxx-****`" —— 把这条纪律**绑定到门禁输出**上，而不是只留在记忆里（同一坑曾在一次提交内踩两次）。

- **⑪ 凭据下发方向保护 + `secrets pull`（把"人工纪律"变成"入口动作 + 机制闸门"）**:
  **背景**：⑨ 登记的遗留 —— `secrets` 是**单向下发、无回写**，而站上 `unsloth.key` 每次加载重铸 ⇒ 直接 `push` 会用正本陈旧值**覆盖站上真 key**、打断该站 agent。此前只靠人工纪律（"加载后先回写正本"）+ 三处文档约束兜住。
  **决策（用户拍板"执行"）**：**不加"常态黄灯"式提醒**（那只会制造噪声、最后被人整体忽略），改为**在危险动作上设闸 + 把正路做成一等入口动作**：
  | 项 | 设计 |
  |---|---|
  | **新增 `secrets pull [A\|B\|C]`** | 把"站内产物"型凭据**从站上收回**主控正本（SFTP 原始字节）—— 这正是原先手工 `scp` 的那一步，现在是一等入口动作 |
  | **`push` 默认拒绝覆盖**"站内产物"型凭据 | 站上已有且与正本不同 ⇒ **跳过**并打印两条出路（`secrets pull <站>` / `secrets push --force`）；`--force` 保留强制能力 |
  | `SECRETS_PROBE` 增 `[kv]` + `status` 增"站内产物"行 | 只打**归一化指纹**（去换行后 sha256 前 12 位，**不打值**），显示"站上 vs 正本 一致/不一致 + 下一步" |
  | 类型显式化 | `STATION_MINTED = {"unsloth.key"}`（站内产物型：真值在站上，正本只是兜底） |
  **顺带修一处既有真缺陷（非本次引入）**：`_flow_rotate_status`（`flow rotate` 首步）把 `ssh_run` 返回的**原始文本**喂给期望 dict 的 `_secrets_verdict` ⇒ `p["reachable"]` **直接 TypeError**；即便不崩，下一行 `v != "OK"` 比的是 tuple ≠ str ⇒ 该步**恒判"需关注"**。改为直接调 `probe_secrets` 取状态串（并去掉那次多余的 `ssh_run("A","true")`）。**修复后实测**：`_flow_rotate_status({'go':False})` → `(True, '凭据落点/引用/权限: A=OK, B=OK, C=OK', [])`。
  **验收（正负双向 + 可回滚）**：① `status` 三站"站内产物"均 `一致 ✓`；② **负向**：把正本 C 换成假值 → `push` ⇒ `C 站 下发 2 个` + **跳过 `unsloth.key`**，站上指纹**未变**（`9de8ff4d…`）⇒ 闸生效；③ **`--force`** ⇒ `C 站 下发 3 个`、站上指纹变为假值 ⇒ 强制路径仍可用；④ **回滚**：用临时备份还原站上真 key → `secrets pull C` ⇒ `回写正本 1 个`；幂等复跑 ⇒ `已一致 -> 跳过`；终态三站 `一致 ✓`（C 回到 `9de8ff4d…`）；⑤ 临时备份删除；⑥ 全量门禁 **13 绿 / 1 黄 / 0 红**。
  **纪律**：**"危险动作 + 人工纪律"必须升级为"危险动作 + 机制闸门"**；且正路（回写）必须是一等入口动作 —— 否则人总会绕过它走捷径。

### 2026-09-15 — 管理面清减四批 + 文档漂移门禁日

> 补记（同 09-16 回填）。决策依据全文见 [ADR-0004 第一~四批](../../adr/ADR-0004-统一管理入口为唯一管理面.md)。

- **清减第一批（7 文件）**: D5 顺序（先补入口→验证→再删）**当场拦下我自己的误判** —— `check_llama_version.*` 看着"已被 `cluster.py versions` 覆盖"，逐条核对才发现**覆盖不完整**：入口的完整性列三站恒显"缺失"（**只找 `MANIFEST.md5`，站上文件叫 `MANIFEST`** ⇒ 长期假阴性）；旧脚本还有 **`rpc_protocol` 采集**与 **C 站旧 IP `192.168.1.24`**（现 `.37`，旧脚本对 C 本就 exit 2）。动作=先并入能力（`MANIFEST` fallback + `rpc_protocol` 纳入比对）→ 再删。顺带修 **locale 陷阱**：站上 `LANG=zh_CN.UTF-8` 使 `md5sum -c` 打印**"成功"**而非 `OK` ⇒ 按英文解析会把**全部通过读成全 FAILED**；修法 `LC_ALL=C md5sum -c`（与 memory 里"`free` 输出随 locale 变 ⇒ 改读 `/proc/meminfo`"同源复发）。**"能力看起来重复" ≠ "能力已被覆盖"**。
- **清减第二/三批（判据换成可机械判定，不需判断能力）**: 第二批=①自标 `DEPRECATED`/`勿执行`（8；重跑会把 `***REMOVED***` 占位符写进生产配置）②含占位密钥+认证必需（19；必然 401 的空壳）③靶子系统已退役（4，`_bs2_*`→LiteLLM `:4000`）⇒ 脚本 250→**219**，含占位密钥的 git 跟踪文件 36→**5**。引用反查**抓出真风险**：活跃手册 `_station-bin/REPRO-RUNBOOK.md` 仍教"key 重铸后**必须重跑 `_bkeyupdate.sh`**"，而该脚本已标"勿执行"⇒ **照手册操作会写坏生产配置**；已改为走入口（`secrets status/push` + `providers`）。第三批=**脚本显式引用不存在的靶子**（LiteLLM 网关簇 9 + claude 死端口 `:8087` 写配置 3）⇒ 219→**207**（冻结存量 193→**181**）。其中 `_acldset.sh`/`_acldoverride.sh` 会**整体覆盖**生产 `settings.json` 成死端口+`dummy` token，今天跑一次就把 claude 打断。
  ⚠ **本次核查中我自己踩了 `pgrep -f` 自匹配**：`ssh host 'pgrep -f litellm'` 三站**全报 RUNNING** —— 真因是 **ssh 那侧包装 shell 的命令行里就含该模式**，`pgrep -f` 匹配到自己；改用 `ps -eo args | awk` 才得真相（三站无 litellm 进程）。**纪律**：跨 ssh 的 `pgrep -f` 必然自匹配，进程存在性判据一律走 `ps args` / `pgrep -x` 并核对全文。
- **清减第四批 = 文档漂移审计（脚本的另一半：清的是文档）**: 方法四步（**实况取证 → 机械扫描 → 逐条核对防误报 → 分级处置**），核心纪律 **"机械命中" ≠ "真漂移"** —— 必须分**①真漂移（改）②历史记档（保留原文+加现状注记，不改写历史）③假阳性（不动）**。全仓 md 扫描结果：真需改文档内容的仅 **7 处**（派发/路由规则、退出码语义、隧道方案已废、网关路径、仓库路径前缀、C 站 open issues）；**失效相对链接 65 条**（病根都是"前缀写重"：`spec/<x>/` 里的 `../spec/y` → `spec/spec/y`）⇒ 限"**能唯一确定新目标**"才改，**65 → 4**（余 4 各有正当理由，不猜）。**关键产出 = 新增门禁断言 `doclinks`**（md 仓库内相对链接可达；外链/锚点/占位/库外不判）—— 文档漂移方向是单向的（代码改了会红，文档改了不会），**只能靠门禁不靠自觉**；且特意**放弃**判"语义过时"（需人读，判不准的项写门禁只会制造噪声）。门禁 13 → **14 项**（quick 8→9）。自证（正+负）：正 → 144 md / 840 链接 / 失效 0 PASS；负 → 注入一条坏链（配"好链/库外/占位/外链"四对照）⇒ **只报那一条**、exit 1。关联: ADR-0004 第四批、[OPEN-ISSUES §6](OPEN-ISSUES.md)。

### 2026-09-12 — 评审环 / 看板 / 栅栏门 / 批量闭环日

- **Cpp_Hub 试点全链路闭环（O-06/O-12 关闭，O-13 半收口）**: 轻量 C++ 工程（含中文源文件名 `因子计算_核心.cpp`/`因子计算_run.cpp`，git init）+ 补建 `agentsync-templates/cpp` 四型模板（兑现 IMPLEMENTATION 声明）；B 站预置编译链 `g++`/`cmake` + pytest。`test-cards/cpphub-001.md` 挂主控独立 golden（`cpphub_golden.py`，纯源码静态断言，避开 Win10 无编译链），端到端两次 run 均 `exit 0 / accept_golden.passed=true / GOLDEN_PASS`（最近 202609122223140613）。**试点验收桥接三项台账关项**: O-06 中文路径/文件名端到端（tar UTF-8 跨站无乱码+模型按原中文名编辑+golden 反替代检查）；O-12 strong accept 关闭判据「下一任务卡设计时落地 golden」达成；O-13 编译链就绪但 golden 未走真编译 → 半收口，R/sympy 单列。失败修复: agent-cli 项目未注册 → `PROJECTS` 补 `Cpp_Hub`；golden cmd 改系统 `python3`（A 站无 .venv）。关联: Cpp_Hub-001、O-06、O-12、O-13。

- **O-24 ④ 单机并发纪律入册（P0 收口，执行）**: O-18 铁律补单机语境——手册 §2 agent-cli 新增「并发纪律」条（单机勿就地叠并发，同一带宽顶起 ~2.8×，扇出优先跨站各 1）+ ARCHITECTURE §4「单机形态同样适用」锚点；手册「并发」条目同步更新 readonly 层 2 锁已激活（O-17）。OPEN-ISSUES O-24 ④ 标记入册。关联: O-24/O-17/O-18。

- **O-16 评审环落地（`agent-cli review`）**: JUDGE_TABLE 五源路由落盘主控 agent-cli.ps1（商业 API / ultra free / DS V4 RPC / M2.7 / 主控 opencode 备源），advisory 语义（score=不合格仍 exit 0 + 幂等复用 + `--overwrite` 重审）；judge=ultra 实测生成 review.json。关键教训：main judge 标 local 必须用站内模型（防敏感数据外发）；CoT judge max_tokens=8000、按源参数化；judge 调用 retry≤2；长产物评审取头尾截断。
  - 关联: O-16 closed；文件: agent-cli.ps1、THROUGHPUT-BASELINE.md、CLOSED-LOOP-ANALYSIS §3.2
- **O-25 P1 槽位门落地**: `ops/station-bin/_slot_gate.sh`（远端 `/slots` 探测）+ `Invoke-SlotGate`；仅本地 `cluster-litellm/*` 引擎走门，egress `opencode/*` skip；busy≥total 或 queue>0 → exit 24 SLOT_BUSY reject（`--slot-allow-busy` 放行），slot 记入 run.json。并入 O-08/F1。
- **O-25 P2 看板落地**: 纯 file:// 单文件方案 — `make-dashboard.ps1` 生成器 → `dashboard.html`（self-contained，内联 ledger+run.json，完成区 22 行三态 + 运行中/Live 拉 `.progress`）。离线验证通过（BOM/AST/生成/ _fm_golden_test 9/9）。
- **批量闭环（总览表与详情节对齐）**: O-09（BS-1 isolate_xdg，L1 PASS 消除 SQLite 写锁串行化）、O-10（并入 O-11）、O-11（跨站扇出 L2 端到端 + L3 回归，`o11-fanout-readonly.md` 双站并发 ACCEPT_OK/GOLDEN_OK）、O-15（claude 备通道 + `--continue`）、O-17（readonly 层 2 锁）、O-24（P0-①--continue 实证 + P0-②被 O-16 覆盖）。
- **O-26 分解派发闭环**: decompose 拆 2 分片 A/B 双站并行，并行 465.1s ≪ 串行 720.8s（ratio 0.645）；落地修复 2 bug（`Start-Process .ExitCode` 偶发 null、`$MyInvocation` 派发无 BOM 副本）。
- **C 站 gpt-oss-120b HIP 引擎落地**: 改用 `/home/scott-lau/Applications/llama-gfx1151/llama-server`（ROCm HIP，`ROCm0`）；修复 `BACKEND=` 无尾随换行粘连 bug；port 8080，`/health ok` + `/v1/chat/completions` HTTP 200。关联: station-c/DEPLOYMENT.md。
- **台账同步**: OPEN-ISSUES 总览表状态回写对齐详情节（O-09/10/11/15/17/24），遵循单一真值。

### 2026-09-11 — M2.7 实跑 + 五源评审路由定案

- MiniMax-M2.7（C 站，121G UD-IQ4_XS，Vulkan/ROCm0）16 题批量实跑（tmp/res_m27，117936 tok / 5490s），decode 21.5 / 22.1 t/s。入库 THROUGHPUT-BASELINE.md。
- 五源评审路由（CLOSED-LOOP-ANALYSIS §3.2）定案，替代 review subagent 单一路径 → 2026-09-12 落地。

### 2026-09-10 — 同模型横向基准

- HARNESS-SAME-MODEL-BENCH-2026-09 建立（同模型、多后端/多站横向对比基准）；A 站 Hermes Agent 插件生态盘点并入 PLUGIN-LEDGER §6。

### 2026-09-09 — 单机闭环韧性批 + strong-accept

- **--continue 续接循环落地**: front-matter `continue-timeout-s` 独立预算键（续跑不继承首跑已耗尽预算）；真实恢复场景实测（dogfood-resume-recovery v3）→ 手册 §2a.5。关联: O-24 P0-①。
- **strong-accept 落地（O-12）**: M1-M4 全链（front-matter 解析 / .golden/ 洁净注入 / 权威 checksum 防篡改 / .meta+run.json 契约）；V0 验证门 PASS（ACCEPT_GOLDEN_OK=1、哨兵 NOT_OBSERVED）、TAMPERED 安全侧失败实证；修复 tar `-xzf→-xf`、collect 静默。
- **O-19 4/4 闭环**: 两站模型全卸载致空推理 中止场景全链修复。
- **三站插件统一**: DCP(codex-memory 0.6.5 + @tarquinen/opencode-dcp)+codex-memory 三站同构安装；PLUGIN-LEDGER 建立。
- **CLOSED-LOOP-ANALYSIS-2026-09-09**: 单机工作流 4 类断点（review 缺 / --continue 缺 / claude 备通道缺 / 单机排队治理缺）分析定案。
- **回归框架**: `_fm_golden_test.ps1`（离线回归 9/9）。

### 2026-09-08 — 分布式引擎深化 + 事故铁律

- **叠加加载死机事故（A 站 kernel panic）**: C1(HIP 62G 常驻) + C2(再载 63G) 叠加 125G>124G。教训铁律升级: ①引擎对比测试必须串行+卸载确认 ②`-ngl -1` 单机高危 ③load-gate 硬规则（检查已有进程 RSS 叠加，旧 load-mem-gate 漏检项）。
- unsloth studio 单站 HIP 后端可用（gpt-oss 120B MXFP4: prefill 112-138 / decode 49-53 t/s）；同条件后端对比 nemotron-120B: HIP 20.5 vs Vulkan 23.2（Vulkan 略优）。
- C 站部署落地: 内核 6.17.0-23 钉住（GRUB 子菜单索引）、环网 thunderbolt MAC 绑定根治、UMA FB=4G、看门狗关闭、gpt-oss 引擎 BR。关联: station-c/DEPLOYMENT.md。

### 2026-09-06/07 — ctx 一致性 radical fix + wrapper 加固

- **O-21 服务端 ctx 修复闭环**: `/props` 实载 n_ctx=65536 而模型通告 131072 → 服务端 `-c 65536` 是 400 真根因；conf CTX 65536→131072 重载 A 站 gpt-oss，specaudit 重跑全程无错。
- **O-23 复杂度路由 ctx 解耦**: profile.context 只是元数据，从未传给引擎；opencode.jsonc 固定 131072；引擎 ctx 由 flavor 预设决定 → 三者解耦根治。D-18 radical fix B（引擎 ctx=唯一真相）。
- **D-16 复杂度路由 + D-17 wrapper fail-fast 加固**（DECISIONS v1.1）。O-22 `.meta` 残留误导收口。

### 2026-09-05 — 最小实现批

- **O-01 --attach 传输最小实现落地** + 端到端验证（schema 字段↔传输通道闭环）。
- **O-20 修复**: Invoke-Workspace 目标站判定被 PowerShell 动态作用域污染（`$HostName` 污染 → 恒回退 'B'），修复+实机验证。

### 2026-09-04 — 台账制度化 + BS 验证门 + 跨站架构

- **OPEN-ISSUES 台账建立**: 单一真值总账（P3 残留 / BS 验证门 / 升级项 / 风险 / 跨站待办），状态变更回写铁律。
- **DECISIONS 登记册建立**（v1.0，D-* 决策单一口径）。
- **BLINDSCAN-v2-orchestration §8**: 复现记录 + 跨站扇出调研。**BS 验证门 L1 全过**: BS-1 写锁串行化成立非危重（WAL+busy_timeout 排队非阻塞）；BS-2 gpt-oss 编排层 3 线程并行 52.1s≪串行 110.9s、跨站 A+B 并发 ratio 0.71 → **扇出押编排层并发 HTTP + 跨站各 1 并发**；BS-3 slot0-stuck 未命中（概率性不能免疫）；BS-6 并发≈串行。ADR-0001/0002 关联。
- **F1 后端并发探测** → 降级为观测先行（同站叠并发被带宽顶起）。

### 2026-09-03 — 框架奠基 + 验收通过

- **DESIGN v1.0 批准**（Step 3-4，含 F1 定案）；CHECKLIST 建立；IMPLEMENTATION v1.2 实施锚点落档。
- **V0 六门验证**（B/A 站实测）: A1 薄壳导入 / A2 claude 遮蔽 / A4 A 站记忆 / A5 bash 并发写不锁 / A6 flock 跨 ssh — 5 PASS + 1 部分验证。
- **A1-A16 功能全过 + 不变式 7/7 + 错误处理 6/6**: 路由拒绝（exit 2/4）、锁互斥（exit 3）、孤儿恢复、网络失败（exit 5）等全链路。
- **验收轮**: 有条件通过 → 修复批四项（P1a scrubber + P1b 任务卡正文传输 + P2-1 时间语义 + P2-2 退出码 5）全实机复验 → **验收通过（2026-09-03 16:30）**，质量门 4.5/5 档 A，遗留 P3×5 登记。
- **paper-pilot 试点闭环（A14）**: 真实任务卡 `test-cards/paper-pilot.md` 跑通（accept 双 pytest 11+29 passed，产物回收 D:\Paper\agent-out，main git 无越界）。
- **unsloth-a-station:** A 站 unsloth（b10715 HIP 引擎）就位。

***

## 持续追加模板（下方为新里程碑占位，按需复制上移）

### YYYY-MM-DD — <里程碑名>

- <事件>: <简述 + 验收证据链接 + 关联 O-xx>