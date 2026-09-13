# 三机群文档升级 + C 站对标 A/B 配置补齐

## Context

用户将 A/B 两站"双机推理集群"升级为 A/B/C 三站群。C 站（seaviv, 上海影核 SEAVIV AideaStation R1 Plus, Ryzen AI Max+ 395 / gfx1151 / 128G 统一内存 / 192.168.1.37）自 2026-09-08/09 已接入大部分基础（模型传输、opencode/claude 双 CLI+插件复刻、_station_ready 注入链、agent-cli.ps1 ROUTE_TABLE 加 gpt-oss-c/nemotron-c）。现有三份"双机"文档仍是 A/B 双机语义，且实测发现 C 站多项对标 A/B 的配置 gap 与 cluster.py 漂移。任务：**文档更新为三机群状态 + C 站配置补齐对标 A/B**。

用户已确认：**动作范围 = 文档 + 配置补齐**；gttsize 值需先对照后端/社区调研再定（已完成，见下）。

## 调研结论（2026-09-09 只读实测 + 社区核查）

### 1. gttsize 与后端关系（用户指定调研项）— 结论：与后端无关
- **gttsize（GTT）是内核 amdgpu 驱动的"系统内存→GPU 地址空间映射池"上限，平台级参数，Vulkan/ROCm(HIP) 后端共用同一池**（AMD 官方 Strix Halo 优化文档：GTT = 用户进程 GPU 可映射系统内存池；默认约为总内存 50%；AI 框架优先 GTT-backed allocation）。
- **三站实测**：A `6.17.0-40` / B `6.17.0-23` **gttsize=120000 + ttm.pages_limit=30720000**；C 站 `7.0.0-31` gttsize=120000 + pages_limit=32000000 → **C 站 gttsize 与 A/B 一致**。
- **memory 硬规则 `amdgpu.gttsize=126976` 是过时条目**：该值源于 GMKtec EVO-X2（2G carveout, lemonade issue #2631）与 DwarfStar/DS4 场景，非本集群（A/B/C 均 0.5G/4G carveout + 128G）。
- 社区主流值：`131072`(128G: Framework/ignasivt/der toolbox) / `126976`(~124G: EVO-X2) / `120000`(AMD 官方 trillion-cluster 指南 + 本集群)。**AMD 官方指南 = gttsize=120000 + pages_limit=30720000，与 A/B 完全一致**。
- **处置**：gttsize **保持 120000**（不改），修正 memory 硬规则值 120000；C 站 pages_limit 32000000 vs A/B 30720000（+125G 档 bit）差异可保留或统一为 30720000（与 A/B 同款）——建议统一，需用户确认。

### 2. C 站内核漂移（唯一硬规则违反）
- 实测 `uname -r = 7.0.0-31-generic`，但 memory 硬规则要求 C 站 6.17.0-23（9/8 曾 GRUB 子菜单索引 1>4 切过）。GRUB_DEFAULT="1>4" 仍在，疑似重启后菜单索引漂移或内核回滚。**动作有重启风险，列为决策点 D2。**

### 3. C 站配置 gap 台账（对照 A/B 实测）
| 项 | A/B 站 | C 站实测 | 处置 |
|---|---|---|---|
| infer-load / infer-list / infer-unload | ✅ /usr/local/bin | ❌ 仅 llama-serve-instance | 补装（Phase 1）|
| load-mem-gate / wait-gtt-release（OOM 三件套）| ✅ | ❌ | 补装（Phase 1）|
| cluster-watchdog / backup-memories | ✅ | ❌ | 补装（Phase 1, 低优先）|
| /etc/llama-instances conf | 每模型 .env | 仅 qwen3.8-27b-mtp.env | 参照 B 站同名 env 补 gpt-oss/nemotron（Phase 1）|
| opencode | 1.18.25 + codex-memory@0.6.5 + DCP + cluster-litellm provider | ✅ 同款 | — |
| claude | settings.json + 插件复刻 | ✅ | — |
| 模型 | /data/models/gguf/lmstudio-community/ | ✅ gpt-oss + nemotron | — |
| 引擎 | /opt/llama.cpp + ~/.unsloth/llama.cpp | ✅ | — |
| 环网 | thunderbolt MAC 绑定 + 静态路由 | ✅ thunderbolt0/1 UP + 双出口路由 | — |
| 管理网 | 固定 IP + .local | ✅ eno1 192.168.1.37 单路由 | — |
| avahi/.local | ✅ .local | ⚠️ avahi active + seaviv.local 本机可解析（与 DEV-LOG"无 .local"记载矛盾）| 主控站实测解析（Phase 1a）|
| UMA/BIOS | 0.5G/512M | ✅ 4G（成功形态, HIP 全通）| — |
| beszel-agent | ✅ | ✅ active | — |

### 4. cluster.py 漂移（d:\RPC\ops\cluster.py）
- `STATIONS["C"].host = "192.168.1.24"`（**过期**，应为 192.168.1.37；建议 seaviv.local 若主控可解析）
- `STATION_PORT["C"] = 18080`（实测 C 站引擎 **8080**）
- `C_ENGINE_UNIT = "llama-server@qwen3.8-27b-mtp.service"`（与 C 站常驻 nemotron 不符，需只读核实真实 unit）
- `PANELS` Cockpit C = `https://192.168.1.24:9095`（过期 IP）
- `ROUTE` 已含 `qwen3.8-27b→C` ✓；docstring/status/load 文案仍"两站"

### 5. 文档矛盾残留
- `d:\RPC\docs\C站硬件身份与BIOS更新源分析_20260908.md` §6.3 末行"HIP 定案不可用→Vulkan 兜底"与头部定案（UMA=4G HIP 全通）矛盾 → 加"已纠正"批注。

## 实施计划

### Phase 0 — 修复 cluster.py 漂移（前置，无风险）
文件：`d:\RPC\ops\cluster.py`
- L41 host：`192.168.1.24` → `seaviv.local`（若主控解析成功，Phase 1a 验证后；否则 `192.168.1.37`）
- L44 STATION_PORT C：`18080` → `8080`
- L48 C_ENGINE_UNIT：按 Phase 1a 只读核实结果修正（常驻 nemotron 的实际 unit/起停方式）
- L61 PANELS Cockpit C、L199 render_html 端口 `18080`→`8080`
- docstring L5-23/L16 与 status/load 文案："两站"→"三站"
- 验证：`python ops/cluster.py status` 三站 READY

### Phase 1 — C 站配置补齐
**1a. 只读核实（先取证，不改动）**
- C 站：`systemctl list-units 'llama-server@*'`（常驻 nemotron 的真实 unit）、pid 17579 父进程、`cat /etc/default/grub` + `/boot/grub/grub.cfg` 实际指向、`ls /lib/modules/<6.17.0-23>/`（确认映像存在）
- 主控站：`getent hosts seaviv.local`（解决 avahi 矛盾）
- C 站 netplan 文件核实 thunderbolt 是否 MAC 绑定

**1b. 补装工具链（从 `ops/station-bin/` 经 SSH/tar 同步，遵循 station-bin 纪律：除站特例行外 md5 一致）**
- `infer-load` / `infer-list` / `infer-unload` → C 站 `/usr/local/bin`
- `load-mem-gate` / `wait-gtt-release` / `load-gate`（OOM 防护三件套，memory 硬规则）
- `cluster-watchdog` / `backup-memories`（运维对齐）
- 参照 B 站 `/etc/llama-instances/gpt-oss-120b.env`、`nvidia-nemotron-3-super-120b-a12b.env` 为 C 站生成同款 conf（alias/MODEL_PATH/PORT=8080/BACKEND=unsloth 对齐）
- 验证：C 站 `infer-list` 出模型清单 + `infer-load gpt-oss` shell 校验（不实际重启常驻引擎）

### Phase 2 — 内核/GTT 决策点（需用户确认后执行，有重启风险）
- **D1（GTT）**：保持 `gttsize=120000`（与 A/B 一致，AMD 官方同值）；pages_limit 是否由 32000000 统一为 30720000 待确认。**修正 project_memory 硬规则值 120000**（126976 为过时错误条目）。
- **D2（内核）**：C 站回 6.17.0-23（GRUB 子菜单索引法重启，备份 /etc/default/grub + modules.dep 校验 + apt-mark hold 防漂移）；或记录待办不纳入本次。**默认建议记录待办**（当前 7.0.0-31 + Vulkan 实跑正常，切换引入重启停摆风险；硬规则修正为"7.0.0-31 观察运行，若 ROCm/HIP 再遇问题切 6.17.0-23"）。

### Phase 3 — 三份文档更新
**A. `d:\RPC\docs\双机推理集群使用手册.md`（v1.7→v1.8，操作真值，重点）**
- 头部版本历史加 v1.8 变更说明
- §1.1 硬件拓扑：两站图→三站图（C seaviv 192.168.1.37/seaviv.local, 环网 10.10.11/10.10.12, carveout 4G）
- §1.2 端口与服务清单：加 C 站 llama-server `:8080`；IP 漂移免疫规则补 C 站说明
- §2 快速开始：加 C 站快速路径（ssh scott-lau@192.168.1.37 / seaviv.local）
- §2.2 模型名路由语义：补 C 站启用模型（gpt-oss-c/nemotron-c 端点半托管说明）
- §2.4 cluster.py：路由规则小节对齐代码实况（含 C）+ 修后的 host/port
- §2a.1 装备清单："两站同构"→"三站同构"（C 站插件已复刻）
- §3 模型加载层：infer-* 三站；注明 C 站补装完成后的统一用法（未完成前标"半托管"）
- §8 监控：cluster-watchdog 明确**不纳入 C 站**（C 站看门狗禁用硬规则）
- §9 已知限制：删/改"C 站已购未装"→"C 站已接入运行（独立端点, 2026-09-09）"
- §10 升级窗口："两站原子升级"→"三站原子升级"

**B. `d:\RPC\docs\双端点部署与opencode混合框架调研.md`（决策史档）**
- 头部加"C 站落地续记"状态框：架构结论被三机形态继承；C 站第三独立端点 2026-09-09 接入。

**C. `d:\RPC\docs\双机剩余优化空间评估.md`（评估史档）**
- 头部加"三机形态"注记：§4 中"C 站容量档部署（ROCm+TTM 120GB）"已随 C 站落地为独立第三端点；A3a/A4/A6 结论不受影响。

**D. 附带**：`C站硬件身份与BIOS更新源分析_20260908.md` §6.3 末行加"已纠正（2026-09-08 晚，详见头部定案）"批注；FRAMEWORK-INDEX 引用核对（标题未变）。

### Phase 4 — 验证
1. `python ops/cluster.py status`：三站均可探测，C 站 host/port 正确
2. C 站补装后：`infer-list` 出清单、`load-gate <GB>` 输出、`_station_ready.sh` 注入 INJECT_OK
3. 三站一致性：`uname -r`、toolchain md5 对账、gttsize/pages_limit 汇总表
4. 主控 `getent hosts seaviv.local`（若成功则更新 agent-cli Get-TargetHost 注释与文档）
5. 冒烟：C 站 `curl seaviv.local:8080/health` + 一次 chat/completions；`cluster.py e2e`
6. 文档↔实机抽查：各节改后对照 cluster.py status / infer-list 输出

## 关键文件
- `d:\RPC\ops\cluster.py`（Phase 0 修复）
- `d:\RPC\ops\station-bin\`（infer-*/load-gate/wait-gtt-release 来源，同步 C 站）
- `d:\RPC\docs\双机推理集群使用手册.md`（Phase 3A，最大改动）
- `d:\RPC\docs\双端点部署与opencode混合框架调研.md`（Phase 3B）
- `d:\RPC\docs\双机剩余优化空间评估.md`（Phase 3C）
- `d:\RPC\docs\C站硬件身份与BIOS更新源分析_20260908.md`（§6.3 批注）
- `c:\Users\Peng\.trae-cn\memory\projects\-d-RPC--p2-276bf3ae08cef51bf77d\project_memory.md`（gttsize 硬规则 126976→120000 修正，附带）

## 风险与回滚
| 风险 | 缓解 |
|---|---|
| 内核 GRUB 切换重启（7.0.0-31→6.17.0-23）| 备份 /etc/default/grub；子菜单索引法（已固化经验）；modules.dep 校验；apt-mark hold。**默认不纳入本次（D2 记录待办）** |
| C 站常驻 nemotron 引擎停摆 | Phase 1 只读核实 unit 归属后再动；补装不触碰常驻进程；动作前 .bak |
| 文档↔实机漂移 | Phase 1 取证在 Phase 3 文档更新之前；未确证项标"待核"不臆断 |
| cluster.py 修改破坏三站 status | 改后立即 `cluster.py status` 验证；git 可回滚 |
| 脚本 BOM/编码 | 涉 PS/脚本编辑走规则（UTF-8 BOM + _fm_golden_test 回归）|