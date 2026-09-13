# DEV-LOG-011: D6 agent-cli wrapper MVP（设计与实施落地 + 跨站扇出验证）

> **日期**: 2026-09-04
> **Feature**: 主控站 agent-cli wrapper MVP——跨项目调用标准（工作区 + 任务卡 + 并发锁 + 敏感路由 + 跨站扇出）
> **规范交付物**: ARCHITECTURE.md / OPEN-ISSUES.md / DECISIONS.md（本日志为开发历程）
> **结果**: ✅ DESIGN v1.4 批准 + IMPLEMENTATION v1.2 + 验收 A1-A16 全过 + 修复批 P1a/P1b/P2 全闭环 + BS-2/跨站扇出 L1 实测通过

---

## 1. 最终状态

| 交付物 | 状态 | 位置 |
|--------|------|------|
| DESIGN.md | ✅ v1.4 approved（含 BP-1/BP-2 审计回灌） | spec/d6-agent-standard/DESIGN.md |
| IMPLEMENTATION.md | ✅ v1.2 draft→验收通过 | spec/d6-agent-standard/IMPLEMENTATION.md |
| CHECKLIST.md | ✅ 验收通过（A1-A16 全过，7.2 P3×5 登记） | spec/d6-agent-standard/CHECKLIST.md |
| BLINDSCAN-v2-orchestration.md | ✅ BS-2/跨站 L1 回填 | spec/d6-agent-standard/BLINDSCAN-v2-orchestration.md |
| agent-cli.ps1 | ✅ wrapper 主体（入 git） | ops/station-bin/agent-cli.ps1 |
| 手册 agent-cli 节 + 台账 §1.8 联动行 | ✅ | 使用手册 §2a.5 / params-ledger §1.8 |

## 2. 时间线

| 日期 | 里程碑 | 摘要 |
|------|--------|------|
| 2026-09-03 | 调研审计定稿 | Agent跨项目调用标准调研 v3.4.1（幻觉审计：1 剔除 + 2 修复 + 7 证据修正） |
| 2026-09-03 | DESIGN v1.0→v1.3 | 六项 minor 处理（F1 降级批准/F4 边界/F6 免费档出站/F7 重试适配）→ Review 通过 |
| 2026-09-03 | V0 六门（A1-A6） | 5 PASS + 1 部分验证（ad-hoc 笔记跨 cwd 可读→判据修正为"提取记忆不串"） |
| 2026-09-03 | T1-T3（A7-A10） | workspace/路由/锁全链：A7 同步+md5 一致；A8 路由拒绝；A9 锁互斥；A10 孤儿恢复 |
| 2026-09-03 | T3-T4（A11-A13） | 端到端本地/免费档/错误注入：A11 契约齐；A12 免费档路由；A13 超时→6 + 网络重试 |
| 2026-09-03 | T5 Paper 试点（A14） | 真实任务卡全链跑通 + 规格符合性闭环（clean-room 重跑 is_well_formed_code） |
| 2026-09-03 | 修复批 | P1a scrubber / P1b 正文传输 / P2 queue_s·run_s 时间语义 / P2 退出码 5 / P2 accept 多命令——全部实机复验（A8b/A15/A16） |
| 2026-09-03 | 验收签字 | CHECKLIST §9.2 验收通过（16.5/5=A档） |
| 2026-09-04 | BS-2 L1 | 直连 gpt-oss 编排层并发 HTTP 通过（52.1s ≪ 110.9s） |
| 2026-09-04 | 跨站扇出 L1 | A+B 跨站并发通过（ratio 0.71 ≤ 1.6）；同站叠并发被带宽顶起定案 |
| 2026-09-04 | 规范三文档 | 建立 ARCHITECTURE / OPEN-ISSUES / DECISIONS（本会话） |

## 3. 实测结果与结论

### 3.1 功能验收（A1-A16，详见 CHECKLIST §2）

- **V0 验证门（A1-A6）**: opencode 薄壳导入、claude 遮蔽（personal>project）、cwd 键控、A 站记忆、Bash 不锁、flock 跨 ssh——5 PASS + 1 判据修正
- **T0→T5**: workspace 建区同步、路由拒绝（锁/敏感/模型三拒绝规则）、锁互斥、孤儿恢复、端到端本地、免费档契约、错误注入、Paper 真实试点——A7-A16 全过

### 3.2 关键修复批（验收审查后 P1a/P1b/P2，均实机复验）

| 修复 | 根因 | 证据 |
|------|------|------|
| P1a sanitized scrubber | IMPL 声明无实现；三档中档静默降级 public | A8b：植入样串 → 远端零明文 + 模型无 LEAK |
| P1b 任务卡正文传输 | Get-FrontMatter 只传 front-matter 一行，正文静默丢弃 | A8b：正文 469/2064 字符完整到达远端；模型按正文规格实现 |
| P2 queue_s/run_s | 时间戳位置测错量：QUEUE_S=全程、run_s 恒 0 | A16：QUEUE_S=2 / RUN_S=31 |
| P2 退出码 5 | PS5.1 NativeCommandError 地雷绕过分派 | A15：NETFAIL 前缀贯穿 → EXIT=5 |
| P2 accept 多命令 | 末行无 \n，while read 跳过末条 | A14 重跑：ACCEPT_CMD[1] 13 + [2] 29 passed，ACCEPT_OK=1 |

### 3.3 性能（CHECKLIST §5）

| 指标 | 预算 | 实测 | 判定 |
|------|------|------|------|
| workspace sync 增量 | <60s | 62.3s | ⚠ 微超 4%（P3，O-05） |
| wrapper 解析 | <2s | 0.40-0.44s | ✅ |
| task 端到端开销 | <30s | lock+collect ~10s | ⚠ 口径重叠（P3） |

### 3.4 并发 fan-out 实测（BLINDSCAN §8.7.5/§8.7.6 + project_memory）

- **BS-2（编排层并发 HTTP）**: 直连 gpt-oss 单轮 3-tool 仅返 1 个（模型内编译期并行不成立）；编排层 3 线程并行墙钟 52.1s ≪ 串行和 110.9s → fan-out 押编排层并发 HTTP 实证成立
- **跨站扇出**: A 串行 4 次 6.8s → A+B 各 2 并发 cross_wall 4.8s（ratio 0.71 ≤ 1.6）→ 数据面真并行
- **同站约束**: 同站内 2 并发被统一内存带宽顶起（1.7→4.8s，~2.8× 恶化）→ **落地铁律：扇出优先跨站各 1 并发**
- **客观判据迁移**: 该 llama-server 无 `/properties`，不能用 `engine_stats.running` → 改以墙钟收敛（并行 wall≈max≪sum）

## 4. 新发现（记入开放日志）

| # | 发现 | 影响 |
|---|------|------|
| 1 | headless opencode 写工作区外文件被 external_directory 权限自动拒绝（沙箱效果） | 任务产物应在工作区内（A5 额外出） |
| 2 | PS5.1 EAP=Stop 下原生命令 stderr 重定向抛 NativeCommandError 绕过分派 | 所有 ssh/scp 包 try/catch 归一网络类（A15） |
| 3 | 模型自写测试的 accept 属自证 | strong accept 需主控站侧 golden 测试（O-12） |
| 4 | LiteLLM 网关 401 真凶=后端换载 key 不同步（非 master_key 哈希） | D6 链路绕网关直连规避（O-14） |
| 5 | 统一内存带宽竞争 → 同站并行被预填充顶 | 目录扇出铁律；V2 应倾向跨站 |

## 5. 偏差与未做项

| 项 | 状态 | 原因 |
|----|------|------|
| --attach 传输 | 未实现→O-01 | 二期随 claude 路径同批，或最小实现 |
| workspace --archive | 占位 stub→O-02 | 二期；R7 语义已保守满足 |
| claude 路径 + --continue | 二期（O-15） | MVP 纵切单 opencode 路径 |
| review --peer / trae 派发 | D7+（O-16） | 预留任务卡接口 |
| readonly 层 2 锁 | V2（O-17） | MVP 仅记录不生效 |
| 后端并发探测 | 降级观测先行（O-08） | Scott 批准 F1 降级 |
| 中文路径/文件名用例 | 部分验证（O-06） | 内容级已测，路径级可选未执行 |

## 6. 后续跟踪

- 跨站扇出 L2（真实 readonly 卡）/ L3（agent-cli-smoke + A 抽检）回归（O-11）
- BS-1 isolate_db 验证（O-09）
- **strong accept golden 测试**（O-12）——下一任务卡设计时落地，防模型自写测试自证
- LiteLLM 网关 401 运维修复（O-14）
- Cpp_Hub 试点（依赖 O-06 中文路径 + O-13 环境预置）
- 升级回归三件套（G14）：agent-cli-smoke + 插件加载 + 记忆读写，并入升级窗口流程

## 7. 部署产物清单

| 文件 | 位置 | 说明 |
|------|------|------|
| agent-cli.ps1 | ops/station-bin/ | wrapper 主体（入 git） |
| agent-cli-smoke.sh | ops/station-bin/ | 4 CLI 冒烟定版脚本（4/4 PASS） |
| agentsync-templates/ | ops/station-bin/ | 四型模板（python/cpp/doc/lean4） |
| _bs2_l1.py / _bs2_fanout.py / _bs2_cross.py | ops/station-bin/ | BS-2 / 跨站扇出 L1 验证脚本 |
| ARCHITECTURE.md / OPEN-ISSUES.md / DECISIONS.md | spec/d6-agent-standard/ | 规范三文档（本会话新建） |
| BLINDSCAN-v2-orchestration.md | spec/d6-agent-standard/ | 并发 fan-out 调研 + L1 回填 |

> **安全纪律落实**: 全部 `.md` 变更已走 git add/commit/push（O-03 纪律：验收/文档产物不再仅文字实录）。

---

## 8. C 站（seaviv）第三站接入（2026-09-09）

> C 站（`seaviv`，192.168.1.37）纳入 D6 agent CLI 工作环境。**背景**：C 站模型目录已统一（方案 A），nemotron-120B 从 B 站传输到位（81G，12m22s @110MB/s，size 全一致）；B/C 站 V4-Flash 已卸载。

### 8.1 现状核查

| 项 | C 站 |
|---|---|
| claude | ✅ 2.1.258（与 A/B 同版） |
| node/npm | ✅ v20.20.2 / 10.8.2 |
| opencode CLI | ❌ 原为**桌面版**（`~/.config/ai.opencode.desktop`，无 `run` CLI）→ **已补装 1.18.25** |
| 引擎 | ✅ `~/.unsloth/llama.cpp` + `/opt/llama.cpp` |
| 模型 | ✅ nemotron-120B(81G) + gpt-oss-120b + qwen-27B |
| opencode.jsonc | 原仅 `$schema` → **已写入标准 provider 配置** |

### 8.2 执行动作

1. **opencode CLI 1.18.25**：复制 B 站 `~/.opencode/`（410M，ELF 本体）→ C 站解包 → 软链 `/usr/local/bin/opencode` + `~/.local/bin/opencode`。**绕开 npm 404 与 sudo**（B 站同款用户级安装）。
2. **opencode.jsonc**：写入标准 `cluster-litellm` provider（gpt-oss + nemotron 模型，baseURL 占位 8080），默认模型 `cluster-litellm/gpt-oss`。
3. **gpt-oss-120b 引擎**：`/opt/llama.cpp` Vulkan，`-c 131072 -ngl 999 --fit off --load-mode none`（25s 加载，`n_ctx=131072`）。**注意**：初起 `-c 4096` 致 opencode 请求 6115 tokens 超限 → 必须放大 ctx 匹配配置。
4. **`_station_ready.sh gpt-oss` 注入**：`INJECT_OK port=8080` + `INJECT_VERIFY_OK`（baseURL 幂等改写 8080）。
5. **agent-cli.ps1 三处改动**：ROUTE_TABLE 加 `gpt-oss-c`/`nemotron-c`（station=C）、`Get-TargetHost` 加 C 分支（→ `192.168.1.37`，C 无 avahi .local）、`Invoke-Workspace` station 判定加 `'C'`。
6. **主控站 ssh config**：补 `Host 192.168.1.37`（User scott-lau）——否则裸 `ssh 192.168.1.37` 用 Windows 用户名。

### 8.3 端到端验证 ✅

```
STATION_READY port=8080 / ENGINE_CTX=131072 / INJECT_OK
TASK sync source -> paper (model=cluster-litellm/gpt-oss station=C sens=local-only)
TASK_RC=0 / ACCEPT_OK=1 / content_digest 已计算 / RUN_S=16
ledger += 202609090359252348,paper,cluster-litellm/gpt-oss,local-only,0,0,0
```

- opencode CLI 冒烟：`step_start → text:"OK" → step_finish` ✅
- wrapper task 全链（sync→station-ready→run→collect→契约）：`TASK_RC=0` ✅

### 8.4 边界与遗留

- **C 站无 avahi .local** → wrapper 用管理网 IP `192.168.1.37`（环网 10.10.11.3 留作 RPC，不用于 agent CLI）
- C 站 `~/.opencode/bin/opencode-1.18.9.bak` 为 B 站旧版本残留（随包复制），无害可删
- **accept.cmd=[] 空判据恒过**——echo 卡无 accept 定义 → `passed=true` 空转，属 D6 O-12（strong accept golden 测试）遗留

### 8.5 闭环补完（2026-09-09）✅

- **claude settings.json 修复**：原残缺（仅 DISABLE_AUTOUPDATER + MAX_CONTEXT_TOKENS）→ 补全 `ANTHROPIC_BASE_URL=127.0.0.1:8080` + AUTH_TOKEN + model 映射（`claude-opus-4-6→gpt-oss`，后切 nemotron）。冒烟 `stop_reason=end_turn`、`output_tokens=48`（gpt-oss）/ `154`（nemotron）。备份 `settings.json.bak-gptoss`。
- **nemotron 引擎切换**：停 gpt-oss → 起 nemotron-120B Q4_K_M（8080，`-c 131072 -n-cpu-moe 8 -fa on`），35s 加载。**补建软链** `~/.lmstudio/models/.../NVIDIA-Nemotron-3-Super-120B-A12B-GGUF` → `/data/models/gguf/lmstudio-community/`（rsync 直传未建软链，方案 A 架构缺口）→ 穿透验证 39G 首片可读。
- **双 CLI 验证**：opencode `cluster-litellm/nemotron` → `OPENCODE-NEM-OK` ✅；claude → `end_turn` ✅；`_station_ready.sh nemotron` → `INJECT_OK / ENGINE_CTX=131072 / MODEL_MATCH` ✅
- **C 站当前状态**：nemotron-120B 引擎常驻 8080（83G 内存），opencode/claude 双 CLI 均指向该引擎

### 8.6 插件复刻（B→C，2026-09-09）✅

C 站 claude/opencode 插件从 B 站全量复刻（tar+scp，103M→21M 压缩）：

| 资产 | B 站源 → C 站目标 | 验证 |
|---|---|---|
| claude 定制技能 ×12 | `~/.claude/skills/` | 12 技能可见 ✅ |
| claude 插件（superpowers 6.3.0 + document-skills）| `~/.claude/plugins/` + `~/tools/plugins/` | settings 引用 + 目录存在 ✅ |
| opencode ARS 学术链 | `~/.config/opencode/{agents,commands,plugins,skills}/` | agents 4 + commands 16 + skills 4 可见 ✅ |
| opencode-codex-memory@0.6.5 | `~/.cache/opencode/packages/` | 缓存就位 ✅ |
| claude settings.json | 合并 enabledPlugins + extraKnownMarketplaces（路径指向 C 站 `~/tools/plugins/`）| JSON VALID + claude 冒烟 end_turn ✅ |
| opencode.jsonc | 加 `plugin: ["opencode-codex-memory@0.6.5"]` + 默认模型改 nemotron | JSON VALID + run 冒烟 `PLUGIN-OK` ✅ |

**冒烟**：opencode `PLUGIN-OK` ✅ / ARS 技能可见 ✅ / claude `end_turn output_tokens=30` ✅

---

## 9. 二期 G1 (O-15 claude 备通道) + V2 fan-out 前置 (O-09 isolate) (2026-09-12)

> 本批执行过程与问题排查落档，闭环证据同步记入 OPEN-ISSUES.md 对应条目（O-15/O-24/O-09/O-11）。本条为开发历程视角的过程复述。

### 9.1 范围与推进序

本批推进主线：**B 类（二期 G1 单机闭环韧性）** → 其中 O-24 P0-② 评审环已被 O-16 独立落地覆盖（闭环），核心落点为 **O-15 claude 备通道 + `--continue` 续接**；随后按 C 类（V2 fan-out）建议序推进 O-09（isolate）→ O-11（L2 跨站扇出）。A 类三件（O-22/O-14/O-25）同期清零。

### 9.2 O-15 claude 备通道（执行过程）

落地三改动到 `agent-cli.ps1`：
1. **ROUTE_TABLE 补 `cli` 键 + claude 模型条目**（`claude`→`claude-sonnet-4-5`、`claude-opus`→`claude-opus-4-1`，均 `station=''`=控制台本地，不入 ssh 站内工作区）
2. **`Get-FrontMatter` 原预留 `cli` 字段** → `Invoke-Task` 计算有效执行器 = `--cli` > route.cli > card.cli > `opencode`；`claude` 分支转 `Invoke-Task-Claude`
3. **`Invoke-Task-Claude`（本地 headless）**：stdin 喂 prompt → `claude -p "" --model <id>`（首跑），失败 ≤2 次 `claude --continue -p "" --model <id>`（续接，独立 `continue-timeout-s` 预算）；镜像 opencode 全生命周期 golden→accept→状态机→ledger+`.agent-run.json`（run.json 记 `cli='claude'`）

前提：控制台 `npm i -g @anthropic-ai/claude-code` + `claude auth login`。

### 9.3 问题排查（本批实机暴露，均已修复）

| # | 症状 | 根因 | 解决（落码） |
|---|------|------|------|
| 1 | **PS5.1 CP936 解析失败** | agent-cli.ps1 扩展后含中文的字符串字面量；`powershell -File` 默认 CP936 解码**无 BOM 的 UTF-8** 中文文件 → 字符错位 `@('...UNPARSEABLE')` | 中文字面量改 ASCII，文件存 **UTF-8 BOM**（依赖薄加载：读内容 → 带 BOM 写回临时文件 → `-File` 执行）。**教训：Edit 工具会剥离 BOM，编辑后必须 `[System.IO.File]::WriteAllBytes` 补回 `EF BB BF`** |
| 2 | **Date 绑定错** | `$body` 长度行 `SB0=$(( $(date +%s%N) / 1000000 ))` 内层 `$(date` 未转义 → PS 双引号 here-string 插值把 `date` 当 `Get-Date` 绑定 `-Date` 报错 | 内层 `$(` 补反引号（L984/L989） |
| 3 | **Sampler 卡死（O-25 P0-② live-progress）** | `sample_progress &` 在子 shell 运行，**fork 副本持有 `$SAMPLE=t`**，主脚本 `SAMPLE=f` 改不到子 shell → sampler 永续 → `wait $SPID` 永久阻塞（实机 30min 卡住，无 opencode，仅 sampler 存活） | teardown 改为 `kill $SPID; wait $SPID`。**任何带 sampler 的任务上线前都会卡死，为必修复项** |
| 4 | **TMP_ROOT 并发冲突** | agent-cli 控制台临时脚本（`agent-cli-attach-mkdir.sh` 等）在共享 `$env:TEMP\agent-cli` 用**固定名**；单控制台并发 L2 任务互撞写坏 | 每调用 `[Guid]::NewGuid()` 生成唯一 `agent-cli-{GUID}` 子目录 |
| 5 | **`--HostName` 路由无效** | `task` 命令的 `--HostName` 字母对实际路由不生效；`route_station` 打印的是模型 ROUTE_TABLE 默认站，非目标站 | 跨站任务必须显式 `--RemoteHost <ssh主机>`（代码只认 `$RemoteHost`） |

### 9.4 O-09 isolate_xdg（执行 + 验证）

- **机制**：task 卡 front-matter `isolate-xdg: true` opt-in → 远程 `$body` 设 per-task `XDG_DATA_HOME=$W/.xdg`（opencode.db 独立）；仅隔离 data 目录（`~/.config/opencode` 含 provider baseURL 仍共享）；`memory.db` symlink 保留；`--continue` 同 $W 同 XDG 不受影响
- **L1 判据 PASS**（实机 B 站 `_bs1_iso.py`）：共享 db 并发 2 写 batch_wall=62.7ms（≈2.3×单写=串行化）→ 独立 db 并发 2 写 batch_wall=30.9ms（≈1.15×单写=真并行），比 A/B=0.49<1.0，busy_hits=0
- **auth 风险排除**：探测 B 站 opencode.db `credential/account/account_state` 全 0 行 → 直连 cluster-litellm 无外挂鉴权资产，Xdg 隔离不切断鉴权
- **计量教训**：初版探针写量过小（300 行）GIL 主导掩盖并行 → 改递归 CTE 20 万行放大工作量后显著

### 9.5 O-11 L2 跨站扇出（执行 + 结果）

- **卡片**：`test-cards/o11-fanout-readonly.md`（`readonly:true` + `--attach _o11_src.txt`）
- **执行**：同一秒并发派发 A（scott-lau-NEX.local, port 42387）+ B（scott-lau-GTR-Pro.local, port 39701）
- **结果**：两站独立 task 均 `state=done / TASK_RC=0 / ACCEPT_OK=1 / ACCEPT_GOLDEN_OK=1 / REVIEW_NEEDED=0`；consume 各自生成 `out/summary.txt` 含 `O11_FANOUT_OK` 且 accept rc=0；RUN_S 57/66s；`TASK remote excode=0` 落 ledger。**实机证明同模型跨站并行派发、附件注入、终端产物+accept+collect 全链可行**
- **边界**：生产 fan-out 走跨站各 1（O-18 铁律，物理上界 3：A/B/C 各 1）；`isolate-xdg` 为同站并行兜底可选闸，默认关闭

### 9.6 本批产物清单

| 文件 | 位置 | 说明 |
|------|------|------|
| agent-cli.ps1 | ops/station-bin/ | claude 备通道 + isolate-xdg + TMP_ROOT/Date/sampler 修复（入 git） |
| _bs1_iso.py | ops/station-bin/ | O-09 L1 判据验证探针 |
| test-cards/o11-fanout-readonly.md | test-cards/ | O-11 L2 测试用 readonly 卡 |
| test-cards/_o11_src.txt | test-cards/ | O-11 L2 附件源 |

### 9.7 下一批（O-26 Split-Dispatcher）

前置 O-25 P0 已满足（A 类清毕）→ 实现 decompose 声明 + 拆 N 子卡跨站各 1 + collect + Merge，过关闭判据。

## 10. O-26 Split-Dispatcher + O-17 层2锁（2026-09-12）

### 10.1 O-26 Split-Dispatcher（执行过程 + 问题排查）

- **方案**（用户选定：拆分成有序分片 + 跨站各1 + Split-Dispatcher + Merge，复用 task 全链）：
  - front-matter 新增 `decompose:` 有序分片列表；`split <proj> --card <master> --attach` 命令 → 解析分片、per-run BOM 副本派发 N 子进程（round-robin 跨站各1）、readonly Merge 按分片序拼装各子卡产物 → `merged-output.txt`。
  - 复用 `task` 命令全链路（sync→lock→run→collect→ledger），子卡 readonly，写型/强依赖任务不拆（`SPLIT_ABORT exit 2`）。
- **落地修复 2 bug**：
  - ① `Start-Process -PassThru` 读 `.ExitCode` 偶发 `$null` 误判失败 → 补 `$p.Refresh()`，并回退解析子日志 `TASK remote excode=` / `TASK_DONE exit=` / `ACCEPT_OK` 作为权威退出码（`SPLIT_PARTIAL_FAIL` 误报消除）。
  - ② 函数体内 `$MyInvocation.MyCommand.Path` 为 null → 子进程派发到无 BOM 原始文件（PS5.1 CP936 秒退）→ per-run 显式 `[IO.File]::WriteAllText($ChildScript, $scriptSrc, UTF8 BOM)` 生成 BOM 副本再派发（同 O-11 L2 机制）。
- **实机验证（A/B 双站 2 分片）**：主卡 `test-cards/o26-split-fanout.md`（`decompose:[只读分片1,只读分片2]`）+ 共享附件 `_o26_src.txt`；shard1→A=`O26_SHARD1_OK|...`、shard2→B=`O26_SHARD2_OK|...`，`accept.passed:true`/`collect:ok`，merged 按序归并 rc=0。
- **关闭判据③（并行墙钟）**：串行基线 `SERIAL_TOTAL_MS=720841`（shard1→A 377.5s + shard2→B 343.3s）vs 并行 465.1s → **ratio 0.645（并行快 35%）**，对齐 BS-2。

### 10.2 O-17 readonly 层 2 锁激活（执行过程 + 问题排查）

- **问题**：DESIGN §4.1 层2锁 MVP 仅记录不生效，task $body 锁段硬编码排它 `flock -n`——readonly 任务被不必要地排它串行阻塞。
- **设计决策**（用户选定：锁调度解耦）：只改锁语义保证写安全；真并发度由 slot-gate（O-25）+ O-18 跨站各1纪律约束，勿同站叠并发 —— 单引擎 slot=1 仅 readonly 共享锁语法上存在，实际仍受 slot-gate 兜底，零 O-18 退化。
- **实现**（agent-cli.ps1 task $body）：
  - 新增 `$flockShared = if ($readonly) {'1'} else {'0'}`（PS 插值进远端脚本，注释全 ASCII）。
  - 锁段 `LOCK_SHARED=$flockShared; LOCK_FLAGS=""; [ "$LOCK_SHARED" = 1 ] && LOCK_FLAGS="-s"; if ! flock $LOCK_FLAGS -n 9 ...`；`LOCK_ACQUIRED/HELD` 行带 `mode=shared|exclusive` 可观测。
  - flock 即 RwLock：共享锁共存（readonly∥readonly）、共享×排它与排它×排它互斥，零新增依赖。
- **验证（三断言内核实证 + 双路 e2e）**：
  - 探针 `_o17_rwlock_probe.sh`（独立锁文件，A站）：RR 双 `OK` / RW `R_OK+W_HELD` / WW `W1_OK+W2_HELD` → flock RwLock 语义成立。
  - readonly e2e（`_o17_readonly.md`→A, run 202609121935547170）：`LOCK_ACQUIRED mode=shared`，exit=0。
  - write e2e（`_o17_write.md`→A, run 202609121941585236）：`LOCK_ACQUIRED mode=exclusive`，exit=0（排它回归零倒退）。
- **问题排查**：无历史缺陷；唯一注意点是新增注释必须 ASCII（PS5.1 CP936 解析纪律），AST 0 错误校验通过。

### 10.3 产物流（O-26 + O-17 新增/改动）

| 文件 | 位置 | 说明 |
|------|------|------|
| agent-cli.ps1 | ops/station-bin/ | O-26 decompose/split + O-17 层2锁（入 git） |
| _o17_rwlock_probe.sh | ops/station-bin/ | O-17 互斥断言探针 |
| test-cards/o26-split-fanout.md | test-cards/ | O-26 主卡（decompose 两分片） |
| test-cards/_o26_src.txt | test-cards/ | O-26 共享附件源 |
| test-cards/_o17_readonly.md | test-cards/ | O-17 readonly（→shared）回归卡 |
| test-cards/_o17_write.md | test-cards/ | O-17 write（→exclusive）回归卡 |

### 10.4 状态

O-26 ✅ / O-09 ✅ / O-11 ✅ / O-17 ✅ 全部闭环（2026-09-12），OPEN-ISSUES.md 台账同步；C 类 V2 fan-out 完成。遗留运维项：C 站 unsloth 加载 gpt-oss-120b Vulkan0 设备无效（三站并发物理上限暂 2：A/B）。