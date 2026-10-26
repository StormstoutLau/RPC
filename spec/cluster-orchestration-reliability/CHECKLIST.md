# 审查验收 Checklist：集群编排与 RPC 选路可靠性加固

---

id: cluster-orchestration-reliability-CHECKLIST
type: design
version: 1.0
status: accepted
date: 2026-10-26
depends: [cluster-orchestration-reliability-IMPLEMENTATION, cluster-orchestration-reliability-DESIGN]
upstream: null

---

> **Feature**: 修复 `cluster.py` 统一编排的四个失败语义缺口（未知态误作忙、worker 普通引擎未卸载、回收失败不传播、预检晚于销毁），使任何非理想返回都表现为**响亮中止**。
> **创建日期**: 2026-10-26
> **状态**: 已验收
> **Spec 步骤**: Step 7-8, 10
> **基于实施**: [IMPLEMENTATION.md](./IMPLEMENTATION.md)
> **基于设计**: [DESIGN.md](./DESIGN.md)
> **基于调研**: [社区外部锚点调研](../../docs/research/2026-10-26_集群编排与RPC选路可靠性_社区外部锚点调研.md)
> **代码基线**: `d11141bb`（`main`，本地 ahead 1）
> **审查轮次**: 第 1 轮（Step 7 验收门定义，实施前）；第 2 轮（Step 10 实施后验收，2026-10-26，**有条件通过**——见 §13.2）；第 3 轮（终验，2026-10-26，**验收通过**）

---

## 0. 验收门总览

本文定义 Step 9 实施完成后、Step 10 验收时逐项勾选的门。**未勾选的 P0 项禁止判"通过"**。

| 门 | 内容 | 章节 | 项数 | 级别 |
|---|---|---|---|---|
| M1 | 交付物 | §1 | 9 | **P0** |
| M2 | 功能（含先验红证据） | §2 | 6 | **P0** |
| M3 | 接口 | §3 | 16 | **P0** |
| M4 | 测试用例 + 偏差锚点 | §4、§5.1 | 20 | **P0** |
| M5 | 回归锚点 | §5.2 | 6 | **P0** |
| M6 | 不变式 + 错误处理 | §6、§7 | 20 | **P0** |
| M7 | 门禁 + 性能量级 + 兼容性 | §9 | 11 | **P0** |
| M8 | 真站故障注入 | §8 | 4 | **P0**（需授权） |
| M9 | 文档闭环 + ADD 审计 | §10、§11、§12 | 24 | **P1** |

> **编号消歧**：§1 的 `T1-T9` 是**交付物**编号（同 IMPLEMENTATION §1）；§4 的 `T1-T14` 是**测试用例**编号（同 DESIGN §10.4）。两者命名空间独立；引用时须带章节（如"§4 T5"）。

**明确不在本轮验收范围**（不设门，验收时不得据此判失败或通过）：

- 不验收"`asset-unreadable` / `asset-not-file` / `asset-not-dir` 在真站复现"——防御性分支，只验单测。
- 不验收 `.hgn` 同尺寸损坏的检出——`min_bytes` 只抓截断/未完成/挂错。
- 不验收 K8s/Envoy/Terraform 机制等价性——只迁移判定语义。
- 不验收 `Conflicts=`（Q1 已裁**不采纳**，2026-10-26；理由见 DESIGN §5.5 / §12 Q1）。
- 不做性能基准对比——只验"预检不引入可感知延迟"的量级判据（§9.2）。

### 0.1 Step 7 复核发现（已修入 IMPLEMENTATION）

编写本 checklist 时对实施文档骨架做了可验收性复核，发现 4 处缺陷，已全部修正：

| 严重性 | 发现 | 落点 | 处置 |
|---|---|---|---|
| P2 | `check_halogen_assets` 的 `warn` 只收集未返回 ⇒ 不可达站信息静默丢失，D3「WARN 可见」未落地 | IMPLEMENTATION §4.5 (b) | `note` 计入跳过站例数；有 warn 无 detail 时返回 `WARN` |
| P2 | `_host_path_for` 根映射（`cont="/"`）丢前导 `/`，拼出 `hostx` | IMPLEMENTATION §5.3 | `best_cont == "/"` 时返回 `best_host + inner` |
| P3 | 预检 shell 目录分支未区分"不可读"与"空目录"（`ls` 空输出 ⇒ 误报 `asset-empty-dir`） | IMPLEMENTATION §5.3 | 加 `-r`/`-x` 判定，不满足输出 `unreadable` |
| P2 | D1 词表计数写成"四行 → 七行"，实为 6 码 → 9 码 | IMPLEMENTATION §11.2、本文 §10 | 改为「6 码 → 9 码」并列出码名 |

---

## 1. 交付物验收

| # | 交付物 | 落位 | 判据 | 状态 | 证据 |
|---|---|---|---|---|---|
| T1 | 三态探针与选路 | [cluster.py](../../ops/cluster.py) | `classify_worker_probe` / `probe_worker_state` / `resolve_rpc_worker` 三函数存在且签名同步 | ☑ | L1266/L1281/L1313，签名与 DESIGN §4 一致（Step 10 核） |
| T2 | 回收契约 | cluster.py | `_reclaim_containers` 返回 tuple；`reclaim_and_unload` 存在且 `steps` 恒 2 项 | ☑ | L877 `-> tuple`；L898 `-> dict`，steps 恒 `containers`+`infer-unload`（E7 用例实测） |
| T3 | 7 个调用点改造 | cluster.py L792/L915/L1052/L1221/L1331/L1355/L1372 | `grep -n "_reclaim_containers(" ops/cluster.py` 仅命中 def 行 + `reclaim_and_unload` 内 1 处；7 个业务调用点均为 `reclaim_and_unload(` | ☑ | grep 仅 L877(def)+L909(内部 1 处)；7 调用点 = L792/L1098/L1230/L1465/L1576/L1596/L1613（行号因预检函数插入而漂移，见 §11.3 P3-1） |
| T4 | 容器预检 | cluster.py | `_host_path_for` / `classify_container_assets` / `preflight_container` + `sh_single_quote` | ☑ | L927/L932/L957/L998 |
| T5 | 配方 `assets` | [cluster_const.py](../../ops/cluster_const.py) | 三项资产（v2 / ngram / tokenizer），无新增 host 路径字段 | ☑ | L167-170（60GiB/45GiB/min_entries 1）；host 路径由 `_host_path_for` 从 volume 派生 |
| T6 | 门禁扩展 | [rpc_check.py](../../ops/rpc_check.py) | `check_aliases` 站级判据 + `check_halogen_assets` 注册且 `quick: False` | ☑ | L4930-4957 站级判据；L4975 + L9958 注册（`quick: False`，位于 engine 前） |
| T7 | 先验红夹具 | [test_cluster_pure.py](../../tests/test_cluster_pure.py) | T1-T14 + D1-D4 锚点全有对应用例 | ☑ | 单测 ALL PASS（T1-T14 + D1a-D1c/D2/D3/D4/E6/E7） |
| T8 | 手册回写 | [三机推理集群使用手册](../../docs/三机推理集群使用手册.md) | §3.3 行为矩阵六行替换 + 「`load` 即独占该站」一句 | ☐ | **待 Phase 7** |
| T9 | O-176 登记 | [OPEN-ISSUES.md](../d6-agent-standard/OPEN-ISSUES.md) | O-176 存在，引用 DESIGN §1 与调研 §3 | ☐ | **待 Phase 7** |

---

## 2. 功能验收

| # | 验收项 | 判据 | 级别 | 状态 | 证据 |
|---|---|---|---|---|---|
| F1 | 单元测试全绿 | `py -3.12 tests\test_cluster_pure.py` 退出码 0，ALL PASS | P0 | ☑ | Step 10 复跑 EXIT=0 ALL PASS（含验收期补测 E6/E7） |
| F2 | **先验红证据** | Phase 0 的 FAIL 输出已逐字留存（至少含 `_rw` 12 条与 `_probe_worker_busy` AttributeError 两类），且记录时间先于 Phase 1 代码改动 | **P0** | ☑ | [phase0-red.log](./phase0-red.log) 尾部 `RESULT: 33 FAILED`，FAIL 列表含 `_rw` 迁移 12 条（RPC load 系列）与 T3-T7 编排（`_probe_worker_busy` 桩路径）；先于 Phase 1 留存 |
| F3 | 容器加载正常路径不回归 | qwen 容器加载至 `/health` READY，`[1/4]`-`[4/4]` 四段日志齐全 | P0 | ☑ | Phase 6 真站 A 站 `load qwen3.8-flash-next-a --backend halogen`：PREFLIGHT ok=True → [1/4] UNLOADED ✓ → [2/4] 镜像在站 ✓ → [3/4] docker run → [4/4] READY（health ok · api 0.18.13 · ctx 262144），EXIT=0 |
| F4 | RPC 加载正常路径不回归 | A 忙时 GLM 自动选 C（`source=auto`），加载成功 | P0 | ☑ | Phase 6 真站：选路输入 `10.10.10.1=busy(halogen+port8080) 10.10.11.3=busy(port8080)` ⇒ `RPC_AUTO_WORKER source=auto target=10.10.11.3 station=C`，回收范围 B/C（A 站 qwen 保留），GLM 双机 READY（17:37:56，health `{"status":"ok"}`），EXIT=0 |
| F5 | 行为矩阵与实现一致 | 手册 §3.3 六行与 DESIGN §7 行为矩阵逐字对齐 | P1 | ☑ | Phase 7 T8 已回写：手册 L953-960 六行与 DESIGN L436-443 逐字一致（仅引用块 `>` 前缀差异），六场景一一对应（2026-10-26） |
| F6 | 缺失即未知生效 | 单站探针失败时 `RPC_AUTO_WORKER` 打印 `=unknown(ssh-failed: ...)`，不打印 `busy` | P0 | ☑ | Phase 6 真站命中：C 站 ssh 停止 ⇒ 选路输入 `10.10.11.3:50052=unknown(ssh-failed: NoValidConnectionsError...)`（无 busy 字样），选路中止不静默退化；单测 T3 侧同证 |

---

## 3. 接口验收

### 3.1 签名一致性（对照 DESIGN §4）

| # | 接口 | 判据 | 状态 |
|---|---|---|---|
| I1 | `classify_worker_probe(ok, out) -> dict` | 两键 `state` / `reason`；`ok=False` 恒 `unknown` | ☑ L1266-1278 代码核 |
| I2 | `probe_worker_state(station) -> dict` | 只读，SSH 超时 20s，不写站上状态 | ☑ L1281-1292（timeout=20，命令只读） |
| I3 | `resolve_rpc_worker(conf_target, candidates, probe, explicit) -> dict` | 四键 `target`/`station`/`source`/`reason`；`source` 七值封闭 | ☑ L1313；七值在单测输出全部出现（explicit/explicit-invalid/conf/auto/fallback/none/aborted-unknown） |
| I4 | `_reclaim_containers(station) -> tuple[bool, str]` | 返回值不是裸 bool；detail 三态（`ssh:` / `port8080-still-busy` / `""`） | ☑ T8/T9 用例 |
| I5 | `reclaim_and_unload(station) -> dict` | `steps` 恒 2 项，名称固定 `containers` / `infer-unload`；不抛异常 | ☑ E6/E7 用例（异常就地捕获） |
| I6 | `preflight_container(alias, station) -> dict` | 三键 `ok`/`problems`/`image_missing`；零写动作 | ☑ L998-1056 函数体只读（INV5） |
| I7 | `_host_path_for(spec, inner) -> str` + `classify_container_assets(spec, observed) -> list[str]` | 无法映射返回 `""`；problems 空 = 通过 | ☑ T13a-d + T10 前置用例 |
| I8 | `check_halogen_assets(ctx) -> (verdict, note, detail)` | 与 `CHECKS` 三值约定一致 | ☑ L5005-5009 三分支 FAIL/WARN/PASS |

### 3.2 边界与异常输入

| # | 接口 | 边界输入 | 期望 | 状态 |
|---|---|---|---|---|
| I9 | `resolve_rpc_worker` | `candidates=[]` | `source="none"`, `target=None` | ☑ 单测「候选为空 ⇒ None」 |
| I10 | `resolve_rpc_worker` | `explicit` 不在 `known` | `source="explicit-invalid"`, `target=None` | ☑ 单测「显式目标未声明」 |
| I11 | `resolve_rpc_worker` | `probe` 为空字典 | 全 `unknown` ⇒ `aborted-unknown`（**不得**默认 free） | ☑ T1（夹具 `if not probe:` 空 dict ≡ None） |
| I12 | `resolve_rpc_worker` | `conf_target=None` 且存在 free | 选 free[0]，`source="auto"` | ☑ 单测「conf 未配置 ⇒ 取候选首个」 |
| I13 | `resolve_rpc_worker` | conf 忙且 `alts=[]` | `source="fallback"`, `target=conf`（DESIGN 规则 5d） | ☑ 单测「conf 忙且无其他候选 ⇒ 回退」 |
| I14 | `_host_path_for` | 未挂载路径 `/nope` | `""` | ☑ T13c |
| I15 | `_host_path_for` | volume 含 `host:/`，`inner="/x"` | `host/x`（不得拼成 `hostx`）；无根映射时返回 `""` | ☑ T13d（Step 7 修）+ T13c |
| I16 | `classify_container_assets` | `observed={}` | `image-missing` + 每资产 `asset-missing` | ☑ T12 + T10 |

---

## 4. 测试用例验收（T1-T14）

| # | 用例 | 注入 | 期望 | 状态 | 证据 |
|---|---|---|---|---|---|
| T1 | 两站 unknown | `probe={A:u,C:u}` | `target=None`, `source=aborted-unknown` | ☑ | ALL PASS |
| T2 | conf 忙 + 备选 unknown | `probe={A:busy,C:u}` | 中止，**不选 C**，**不回收 C** | ☑ | 纯函数层（target=None）+ T4 编排层（calls=[]） |
| T3 | conf unknown + 备选 free | `probe={A:u,C:free}` | 选 C，A **不被回收** | ☑ | `calls==["B","C"]` 且 `"A" not in calls` |
| T4 | 显式 worker unknown | `probe={C:u}`, `explicit=C` | 中止，回收调用次数 = 0 | ☑ | `calls==[]` 且 `built==[]` |
| T5 | worker 忙因普通引擎 | `probe={A:busy,C:busy(port8080)}` | B、C 都收到 `reclaim_and_unload`（`calls == ["B","C"]`） | ☑ | ALL PASS |
| T6 | head 卸载失败 | head `ok=False` | 中止，未调 `rpc-nodes --start` | ☑ | `runs` 无 `--start` |
| T7 | worker 卸载失败 | worker `ok=False` | 中止，rc=1 | ☑ | ALL PASS |
| T8 | 容器回收 SSH 失败 | `(False, "ssh:...")` | `reclaim_and_unload.ok=False`，`steps[0].ok=False` | ☑ | ALL PASS |
| T9 | 端口未释放 | 输出含 `PORT8080_STILL_BUSY` | `(False, "port8080-still-busy")` | ☑ | ALL PASS |
| T10 | 缺 checkpoint | `kind=missing` | `problems` 含 `asset-missing`，**回收 0 次** | ☑ | ALL PASS（回收 0 次由 INV3 调用顺序保证） |
| T11 | 缺 ngram / tokenizer 空 | `missing` / `entries=0` | `asset-missing` / `asset-empty-dir` | ☑ | T11a/T11b |
| T12 | 镜像缺失 | `image.present=False` | `image_missing=True`，**回收 0 次** | ☑ | ALL PASS（同上） |
| T13 | 宿主路径映射 | `/hgn/x`、`/tokenizer`、`/nope` | 映射正确 / 映射正确 / `""` | ☑ | T13a-d |
| T14 | aliases 站级缺口 | inventory 缺 A 站 `stations` | 门禁 FAIL，文案含"未声明" | ☑ | FAIL 且含「未声明 ... 模型库条目」 |

**双向自证**：T2 ↔ T3 只改 C 的状态（unknown ↔ free），选择必须翻转（中止 ↔ 选 C）。两用例须在同一测试文件中并列，便于对照。

---

## 5. 偏差锚点与回归

### 5.1 实施期偏差 D1-D4 的测试锚点

| # | 偏差 | 必须有测试 | 状态 |
|---|---|---|---|
| D1a | `asset-unreadable` | 文件 `stat` 失败 / 目录 `-r` 或 `-x` 不满足 ⇒ `asset-unreadable`（**不得**降级成 `asset-missing` 或 `asset-empty-dir`） | ☑ 单测 D1a |
| D1b | `asset-not-file` | 配方 `kind=file` 但观测 `kind=dir` ⇒ `asset-not-file` | ☑ 单测 D1b |
| D1c | `asset-not-dir` | 配方 `kind=dir` 但观测 `kind=file` ⇒ `asset-not-dir` | ☑ 单测 D1c |
| D2 | `sh_single_quote` | 含单引号/空格的路径转义后仍是单个 shell 词 | ☑ 单测 D2 |
| D3 | `ssh true` 探可达 | 站不可达时返回 `("WARN", note, ...)`，`note` 含跳过站例数，**不**判 FAIL，且跳过信息不丢失 | ☑ 代码核 L4996-5008（warn → note 计数 → WARN 返回）+ full 门禁 3 站例可达 PASS |
| D4 | `_probe_map` | 目标不在 `RPC_WORKER_STATIONS` 时不入表（⇒ 选路判 unknown） | ☑ 单测 D4 |

### 5.2 回归锚点

| # | 回归项 | 判据 | 状态 |
|---|---|---|---|
| R1 | **fallback 分支**（Step 6 P1 锚） | 既有 `_rw(conf=_AW, cands=[_AW])` 的期望保持 `source == "fallback"`，迁移后不得改成 `aborted-unknown` | ☑ 单测「conf 忙且无其他候选 ⇒ 回退 conf(A) 并标 fallback」 |
| R2 | `parse_worker_busy` 行为不变 | 既有 3 条解析用例原样通过（DESIGN §10.1-6） | ☑ 3 条 PASS（空/halogen/双因去重） |
| R3 | `cluster_ssh.py` 零改动 | `git diff --stat ops/cluster_ssh.py` 为空 | ☑ Step 10 实测为空 |
| R4 | `rpc-nodes` 零改动 | `git diff --stat ops/rpc-nodes` 为空 | ☑ Step 10 实测为空 |
| R5 | 无新增脚本文件 | `check_scripts` 门禁 PASS；新增文件仅本 spec 文档 | ☑ scripts PASS（未登记 0）；新增 = spec 四件套 + 调研报告（另有 `.trae/documents/` 1 篇 IDE 工作文档，非脚本非交付物） |
| R6 | 退出码不变 | 各入口仍只返回 `0/1/2`；`grep "sys.exit(3"` 无命中 | ☑ ops/ 全目录零命中 |

---

## 6. 不变式验收（DESIGN §8）

| # | 不变式 | 验证方法 | 状态 |
|---|---|---|---|
| INV1 | 独占：`:8080` 同时只一个引擎/容器 | 回收/卸载串行于启动之前（代码顺序审查 + T5/T6/T7） | ☑ `_load_container_model` [0/4]预检→[1/4]回收→[3/4]run 顺序；T5-T7 中止路径均未到 run |
| INV2 | 未知不可破坏 | `unknown` 永不进入 free/busy 分支；T2/T4 断言回收次数 0 | ☑ `classify_worker_probe` 三态互斥（L1273-1278）；T4 编排 `calls==[]` |
| INV3 | 校验先于破坏 | `preflight_container` 调用行号 < 首个 `reclaim_and_unload` 行号；T10/T12 断言回收 0 次 | ☑ L1082 < L1098（同函数内）；预检失败 return 1 不触回收 |
| INV4 | 失败不吞 | 7 个调用点均消费 `ok`；`grep "_reclaim_containers("` 无裸调用 | ☑ grep 仅 def+内部 1 处；7 调用点均 `if not _r["ok"]: return 1` |
| INV5 | 预检只读 | `preflight_container` 函数体内无 `docker rm` / `docker run` / `infer-unload` / 重定向写 | ☑ L999-1056 逐行核：仅 `docker image inspect` + stat/ls 只读循环 |
| INV6 | 路径单一真值 | 配方无 host 路径字段；`_host_path_for` 只读 `volume` | ☑ assets 声明容器内路径；L932-955 仅读 `spec["volume"]` |
| INV7 | 缺失即未知 | `probe.get(c) or unknown`；I11 用例 | ☑ `_probe_map` 异常归单目标 unknown（L1306-1309）；T1/I11 |
| INV8 | 返回码不变 | 见 R6 | ☑ R6 |

---

## 7. 错误处理验收（DESIGN §7 / IMPL §7）

| # | 错误场景 | 触发方式 | 期望 | 状态 |
|---|---|---|---|---|
| E1 | 探针 SSH 失败/超时 | mock `ssh_run` 返回 `(False, ...)` | `unknown`；退出候选池 | ☑ 单测 T1 + T3 编排（`ssh-failed: timeout`） |
| E2 | 显式 worker unknown | `probe={C:u}` + `--worker C` | `aborted-unknown`，回收 0 次 | ☑ T4 纯函数 + T4 编排 |
| E3 | 容器回收 SSH 失败 | `(False, "ssh:...")` | 不抛异常，`ok=False` | ☑ T8 |
| E4 | 8080 超时未释放 | 输出含 `PORT8080_STILL_BUSY` | `ok=False`，打印保留 | ☑ T9（打印行保留在代码 L888） |
| E5 | `infer-unload` rc≠0 | mock `ssh_stream` 返回 1 | `steps[-1].ok=False` | ☑ T6/T7（`rc=1` 进 detail） |
| E6 | `infer-unload` 连接异常 | mock 抛 `SSHException` | 就地捕获，`detail` 形如 `SSHException: ...` | ☑ **Step 10 补测**（RuntimeError 代演，detail=`RuntimeError: connection reset`） |
| E7 | 容器步失败后跳过 unload | `_reclaim_containers` 返回 False | `steps[1].detail` 含 `skipped`，且 `ssh_stream` 未被调用 | ☑ **Step 10 补测**（detail=`skipped: containers failed`，stream 未触发） |
| E8 | 镜像不在站上 | `image_missing=True` | 后台拉取 + rc=1，**未回收** | ☑ 代码核 L1085-1093（pull detach + return 1 在回收前）+ T12 |
| E9 | 权重缺失/过小 | `missing` / `size<min_bytes` | `asset-missing` / `asset-too-small`，未回收 | ☑ T10/T11a（too-small 分支 L975-978 代码核） |
| E10 | 资产类型不符 | `kind` 与配方不符 | `asset-not-file` / `asset-not-dir`，未回收 | ☑ D1b/D1c |
| E11 | 资产不可读 | `stat` 失败 | `asset-unreadable`，未回收 | ☑ D1a |
| E12 | 容器启动后未就绪 | 既有 `/health` 轮询超时 | rc=1（行为不变） | ☑ [4/4] 段未改（L1113 起）；quick/full 门禁无回归 |

---

## 8. 真站故障注入（Phase 6，需用户授权）

> **前置**：维护窗口 + 用户明确授权；每项注入前记录"A 站 qwen 存活"基线，注入后必须恢复。

| # | 注入 | 手段 | 期望 | 恢复 | 状态 |
|---|---|---|---|---|---|
| S1 | 自动选路遇 unknown | 先占住 conf 目标站（加载一个模型使其 busy），再断开另一候选的 SSH | `RPC_AUTO_WORKER source=aborted-unknown`，`RECLAIM` 行数 0，conf 站服务存活 | 断网恢复 + 卸载占位模型 | ☑ 2026-10-26：注入 = A 站 load qwen 容器占 conf 站 + C 站 `stop ssh.socket ssh.service`（Windows 防火墙规则因 UAC 受限弃用；实测 C 站 sshd 为 socket activation，须同停 socket）。实测中止文案 = `RPC worker 选路失败: conf 10.10.10.1:50052 忙(halogen+port8080) 且其他候选均未知 ⇒ 中止 (不静默退化)`，EXIT=1，无 RECLAIM/回收动作；A 站 halogen Up + health ok、B 生产 qwen Up 13h + health ok。恢复 = C 站 `start ssh.socket ssh.service`；中途 sshd 全断致 B→C 兜底同拒，经用户物理重启恢复（ssh.service enabled 自启），事后复证三站无恙 |
| S2 | worker 被普通引擎占 8080 | 站上手工起 `llama-server` | 回收容器 + unload 引擎，无叠加 | kill 手工进程 | ☑ 2026-10-26：注入 = C 站 `/opt/llama.cpp/ggml-rpc-server` 改名 `ds4-server` 绑 0.0.0.0:8080（零模型依赖；真 llama-server 需 gguf 而 C 站无小模型，命令行含 ds4-server 走 infer-unload 真实清理路径）。实测 probe=busy(port8080) → auto 选 C → infer-unload 清掉（8080 消失，pgrep 无残留）。恢复 = 回收流程已清，unload 三站复证无残留 |
| S3 | ngram 文件缺失 | `mv` 移走 ngram | 预检 FAIL，**旧服务未停** | `mv` 移回 | ☑ 2026-10-26：注入 = A 站 `mv ngram.hgn → .bak`（运行中容器存活 Up + health ok——inode 仍打开，宿主 rename 无感）。实测 load = `PREFLIGHT ok=False :: asset-missing:/hgn/qwen38-flash-next-ngram.hgn` + 「未触碰旧服务 ⇒ 修正资产后重跑」，EXIT=1，无 [1/4]。恢复 = mv 回（51200246144 字节在位）→ preflight ok=True problems=[] |
| S4 | 镜像缺失 | `docker rmi` | `image-missing` + 后台拉取，旧服务未停 | 重新 pull / 恢复 tag | ☑ 2026-10-26：注入 = C 站 rm 两个遗留停止容器 + `docker rmi <tag@digest>`（注：C 站镜像为 digest-only 形态，`:0.18.13` tag 引用注入前已缺）。实测 load = `PREFLIGHT ok=False :: image-missing` + 「镜像未落地 ⇒ 已后台拉取」，EXIT=1（旁观察：problems 重复条目 `image-missing; image-missing`，行为正确，记 §11.3 旁注）。恢复 = 后台 pull ~80s 回位 → preflight ok=True |

**S1 的判定细节**：必须确认"中止"发生在选路阶段，日志含 `RPC_AUTO_WORKER source=aborted-unknown`，且 `RECLAIM` 行数为 0。显式 `--worker` 的 unknown 分支由单测 T4 覆盖，真站不重复。
> **真站实测修正（2026-10-26）**：aborted 分支的实现文案是 `RPC worker 选路失败: ... ⇒ 中止 (不静默退化)`——`RPC_AUTO_WORKER` 打印仅在选路**成功**时出现，aborted 路径无此行。判据按实现文案核验（中止发生点 + 无回收动作 + conf 站存活三点均满足）。

---

## 9. 门禁、性能与兼容性

### 9.1 门禁

| # | 命令 | 判据 | 状态 |
|---|---|---|---|
| G1 | `py -3.12 ops\rpc_check.py --quick` | PASS，新增违规 0 | ☑ 绿 39 · 黄 2（evidence/memory-gates 既有）· 红 0，EXIT=0 |
| G2 | `py -3.12 ops\rpc_check.py`（full） | PASS；`halogen-assets` 为 PASS 或有明确 WARN 原因 | ☑ 绿 47 · 黄 3（既有）· 红 0；`halogen-assets` PASS（真站 3 站例） |
| G3 | `py -3.12 ops\rpc_check.py --only doc-status,md-tables,doclinks` | PASS（本 spec 四文档入扫描后仍绿） | ☑ 绿 3 · 红 0（新增 0/失效 0/新增违规 0） |

### 9.2 性能量级（非基准）

| # | 指标 | 目标 | 实测 | 状态 |
|---|---|---|---|---|
| PF1 | 预检 SSH 次数 | 每次容器加载 ≤ 2 次（image inspect + 一次 stat 循环） | 2 次（L1008 inspect + L1037 stat 循环） | ☑ |
| PF2 | 预检附加延迟 | 秒级，不改变加载总时长量级（换模仍 ~3min 量级） | LAN 单连接 ~0.2s × 2 ≈ 亚秒级；full 门禁 halogen-assets 3 站例无感知拖长 | ☑ |
| PF3 | 探针超时 | 20s 单站，不因一个站拖死整体 | timeout=20（L1291）+ `_probe_map` 异常归单目标 unknown（D4） | ☑ |
| PF4 | full 门禁增量 | 约 9 次 SSH（3 站 × 3：探可达 + inspect + stat） | 实测 **9 次**，与判据一致（原判据"约 6 次"漏算 D3 探可达一次，Phase 7 已修正文案，见 §11.3 P3-2）；量级仍秒级 | ☑（P3-2 已闭环） |

### 9.3 兼容性

| # | 环境 | 判据 | 状态 |
|---|---|---|---|
| C1 | Python 3.12（Windows 主控） | `py -3.12` 跑通测试与门禁 | ☑ 单测/G1/G2/G3 均 `py -3.12` |
| C2 | 三站 Linux（A/B/C） | 预检 shell 在 `bash` 下语法通过（`sh -n` 或实跑） | ☑ G2 halogen-assets 真站 3 站例实跑 PASS（stat/-r/-x/wc\|tr 循环在 bash 下执行成功） |
| C3 | 无新依赖 | `pyproject` / 导入列表无新增第三方包 | ☑ 新函数仅用既有 `ssh_run`/`ssh_stream`/stdlib；deps 门禁 PASS |
| C4 | 既有调用方 | `cluster.py` CLI 参数、退出码、日志前缀向后兼容 | ☑ 退出码 0/1/2（R6）；前缀 `RPC_AUTO_WORKER`/`RECLAIM`/`PREFLIGHT` 在单测输出可见；CLI 参数面未改 |

---

## 10. 文档一致性验收（Step 8 执行）

### 10.1 三方对齐

| # | 检查项 | 判据 | 状态 |
|---|---|---|---|
| C5 | 调研 → DESIGN | DESIGN §2.1 每条外部锚点可回溯到调研报告章节 | ☑ 调研 §3.1-3.4 存在，§2.1 八行引用逐条落位（Step 8） |
| C6 | DESIGN → IMPLEMENTATION | §11.1 的 11 行映射逐行成立 | ☑ 含"Phase 0-6 细化为 0-7"与"T1-T14 → §9.1"（Step 8） |
| C7 | IMPLEMENTATION → CHECKLIST | 每个 T/Phase 在本 checklist 有验收项 | ☑ 交付物 T1-T9 ↔ §1；T1-T14 ↔ §4；D1-D4 ↔ §5.1（Step 8） |
| C8 | 无设计未覆盖的实施 | D1-D4 之外无新偏差；若有，先回写 §11.2 | ☑ Step 7 的 4 处发现均折入 D1/D3 登记，无新增偏差号（Step 8） |

### 10.2 术语一致性

| 术语 | DESIGN | IMPLEMENTATION | 一致 |
|---|---|---|---|
| `free` / `busy` / `unknown` | §4.2、§6 | §4.1、§5.1 | ☑ |
| `aborted-unknown` | §4.2 规则 1/3/5c/6 | §5.1 骨架 | ☑ |
| `fallback` | §4.2 规则 5d | §5.1 兜底分支 + I13/R1 | ☑ |
| `reclaim_and_unload` | §4.3 | §4.2、§5.2 | ☑ |
| `asset-*` 问题码 | §4.4 **9 码**（W1 已回写） | §5.3 **9 码** | ☑ |
| T1-T14 | §10.4 | §9.1 | ☑ |

### 10.3 已知待回写项

| # | 待回写 | 目标 | 状态 |
|---|---|---|---|
| W1 | `asset-unreadable` / `asset-not-file` / `asset-not-dir` 三码补入问题词表 | DESIGN §4.4 检查项表（6 码 → 9 码）+ §7 错误表补行 | ☑ Step 8 已回写 |
| W2 | 调用点计数 7 处 | DESIGN §2.4 / §9.1（Step 4 已改，Step 8 复核） | ☑ 两处均为 L792/L915/L1052/L1221/L1331/L1355/L1372 |
| W3 | 手册 §3.3 行为矩阵 | 与 DESIGN §7 六行逐字一致 | ☑ Phase 7 T8 已回写，F5 逐字核对一致（2026-10-26） |

---

## 11. ADD 审计（Step 10）

### 11.1 Spec 质量门

| 维度 | 得分（0-1） | 说明 |
|---|---|---|
| 可测试约束 | 0.9 | 规范序/问题码/source 七值/steps 契约全部可机判，T1-T14 逐条对号；扣 0.1 = PF4/E6/E7 三处判据精度瑕疵（均已登记并闭环） |
| 模块映射 | 1.0 | 三文件落位明确、零新文件、零新依赖；边界（不做）清单防扩散 |
| 接口契约 | 0.9 | 签名表 + 边界用例 I1-I16 齐；扣 0.1 = 文档引用行号为实施前快照（P3-1） |
| 修正项 | 0.9 | D1-D5 偏差全登记且测试锚点齐；Step 6/7 复核发现闭环在案；E6/E7 验收期补测属流程内修正 |
| 跨模块契约 | 0.9 | source 七值、9 问题码、`(ok, detail)`→`steps` 两级契约在 DESIGN/IMPLEMENTATION/CHECKLIST 三方一致（§10.2 全 ☑） |
| **总分** | **4.6/5** | **档位**: **A** |

### 11.2 测试通过的四类盲区

- [x] **断言恒真**：T2/T3 纯函数用例断言选路翻转（aborted-unknown ↔ auto）；"回收 0 次"由编排层 T4（`calls==[]` + `built==[]`）与 T3（`"A" not in calls`）独立断言——选路层与动作层分开钉死，"中止"与"选了但没回收"可区分。T10 前置用例（资产齐全 ⇒ problems 为空）防"恒 FAIL 也绿"。
- [x] **单文件检查盲区**：7 个调用点逐点 grep 核对（L792/L1098/L1230/L1465/L1576/L1596/L1613），非只看单点命中；`_reclaim_containers` 无第 8 处裸调用。
- [x] **设计独有约束无测试**：INV1-INV8 逐条映射到证据（§6 表）；INV3/INV5/INV6 除用例外附代码行号审查。
- [x] **修正阻断性项无测试**：Step 6 P1（fallback）→ R1 用例；D1 三码 → D1a/D1b/D1c 用例；均 PASS。

### 11.3 审计发现

| 严重性 | 发现 | 证据 | 修复建议 | 状态 |
|---|---|---|---|---|
| P1 | （无） | | | |
| P2 | （无） | | | |
| P3-1 | IMPLEMENTATION §1 与本文 §1 引用的调用点行号（L792/L915/L1052/...）为实施前快照；实施后因预检函数（~70 行）插入而漂移（现 L792/L1098/L1230/L1465/L1576/L1596/L1613） | Step 10 grep 实测（§1 T3 证据列已记现值） | 判据本身是 grep 形状而非行号，验收不受影响；Phase 7 已把 IMPLEMENTATION §1 T3 行更新为现值并保留设计期快照注记 | ☑ Phase 7（2026-10-26） |
| P3-2 | PF4 判据"约 6 次 SSH（3 站 × 2）"漏算 D3 探可达的 `true` 一次，实测 9 次（3 站 × 3） | §9.2 PF4 | 量级结论不变；Phase 7 已改判据文案为"约 9 次（3 站 × 3）" | ☑ Phase 7（2026-10-26） |
| P3-3 | E6/E7 原无直接单测（判据触发方式写 mock，但编排测试对 `reclaim_and_unload` 整体 mock，异常分支测不到） | Step 10 审计发现 | **已补**两条纯函数级用例（`_rau_e6`/`_rau_e7`，test_cluster_pure.py L630-671），复跑 ALL PASS | ☑ 已修复 |

---

## 12. 文档完整性

| 文档 | 存在 | 与实现一致 | 说明 |
|---|---|---|---|
| 调研报告（docs/research/） | ☑ | ☑ | C5 回溯核对（Step 8）；README 索引已登记 |
| DESIGN.md | ☑ | ☑ | Step 4 已收口；W1/W2 已回写（Step 8） |
| IMPLEMENTATION.md | ☑ | ☑ | Step 6 已收口 + D5 偏差（Step 9）；行号快照偏差见 §11.3 P3-1 |
| CHECKLIST.md（本文件） | ☑ | ☑ | Step 7 产出；Step 10 第 2 轮验收回填 |
| 手册 §3.3（T8） | ☑ | ☑ | Phase 7 已回写六行矩阵 + 「`load` 即独占」句（2026-10-26，F5 逐字核对一致） |
| O-176（T9） | ☑ | ☑ | Phase 7 已登记（OPEN-ISSUES L244，O-175 后：缺口 2/3/4 落账 + 残留面 + S1 socket-activation 教训） |
| 开发日志 | ☑ | ☑ | Phase 7 新建 [DEVELOPMENT-LOG.md](./DEVELOPMENT-LOG.md)（2026-10-26 全程条目） |

---

## 13. 验收统计与结论

### 13.1 统计（Step 10 填写）

| 类别 | 总数 | 通过 | 失败 | 待办 |
|---|---|---|---|---|
| 交付物 | 9 | 9 | 0 | 0（T8/T9 Phase 7 完成） |
| 功能 | 6 | 6 | 0 | 0（F5 Phase 7 核对一致；F3/F4/F6 Phase 6 真站通过） |
| 接口 | 16 | 16 | 0 | 0 |
| 测试 T1-T14 | 14 | 14 | 0 | 0 |
| 偏差锚点 D1-D4 | 6 | 6 | 0 | 0 |
| 回归 R1-R6 | 6 | 6 | 0 | 0 |
| 不变式 | 8 | 8 | 0 | 0 |
| 错误处理 | 12 | 12 | 0 | 0（E6/E7 验收期补测闭环） |
| 真站注入 | 4 | 4 | 0 | 0（S1-S4 Phase 6 真站全过，见 §8） |
| 门禁/性能/兼容 | 11 | 11 | 0 | 0（PF4 判据文案已修正，P3-2 闭环） |
| 文档一致性 | 13 | 13 | 0 | 0（W3 Phase 7 完成） |
| 文档完整性 | 7 | 7 | 0 | 0（手册 §3.3 / O-176 / 开发日志 Phase 7 完成） |
| ADD 审计 | 4 | 4 | 0 | 0 |
| **总计** | **116** | **116** | **0** | **0** |

### 13.2 验收决定（Step 10 填写）

- [x] **验收通过**：全部 P0 项通过，P1 项有明确处置 —— **第 3 轮终验（2026-10-26）**：116/116 通过 · 0 失败 · 0 待办；单测 `RESULT: ALL PASS`（EXIT=0）· py-tests **54/54** · 全量门禁 **PASS（绿灯 47 · 黄灯 3 · 红灯 0）**，黄灯 3 项均为存量（`evidence` 可重放 gap 37 存量 · `memory-gates` 引擎侧无门通道 1 条 · `stations` 已登记 `known_drift`）
- [ ] **有条件通过**（第 2 轮结论，**已被第 3 轮终验取代**）：<条件> ① 代码/测试/门禁/文档面全绿（102 通过 · 0 失败），无 P1/P2 审计发现；② 剩余 14 项待办全部为**真站操作（Phase 6：S1-S4 注入 + F3/F4/F6 回归，需用户授权 + 维护窗口）与文档回写（Phase 7：T8/T9/F5/W3 + 开发日志）**，无代码缺口；③ P3-1/P3-2 判据文案修正随 Phase 7 落地。条件满足后做终验轮（第 3 轮）翻"验收通过"。
- **Phase 6 执行结果（2026-10-26）**：S1-S4 + F3/F4/F6 六项全部真站通过，无新增 P1/P2（S1 注入手段偏离已记录于 §8——Windows 防火墙 UAC 受限改用 C 站 stop ssh；S1 判定文案按实现修正见 §8 注）。终态与初始基线一致（B 生产 qwen 重载 READY，A/C 空闲），门禁 halogen-assets + engine 复证 PASS（绿 2 · 黄 0 · 红 0）。统计更新为 **109/116 通过 · 0 失败 · 7 待办**（余项均归 Phase 7）。
- **Phase 7 执行结果（2026-10-26）**：T8 手册 §3.3 回写（六行行为矩阵 + 「`load` 即独占」句 + 真跑记录更新为 Phase 6 读数，F5 逐字核对一致）；T9 O-176 登记（缺口 2/3/4 落账 + 残留面 + S1 socket-activation 教训）；W3 / P3-1 / P3-2 判据与注记修正；开发日志新建。统计更新为 **116/116 通过 · 0 失败 · 0 待办**。
- **第 3 轮终验结果（2026-10-26）**：门条件全部满足 ⇒ **翻「验收通过」**。复证读数：单测 `ALL PASS` · py-tests 54/54 · 全量门禁 `PASS（47/3/0）` · doc-status 词表 105/105（本文件 `status: accepted` 合 checklist 档词表）· 三站引擎态 `可达 3/3 站 · 在服务 1 站（B 站生产 qwen）`。§14 未结两项（B 站 GLM conf `CTX` 旁议 / `Conflicts=` ADR）均为**旁议事项，不在本 spec 验收射程内**，保持登记不阻断。
- [ ] **验收失败**：<原因>

### 13.3 签字

| 轮次 | 日期 | 结论 | 审查者 |
|---|---|---|---|
| 1（验收门定义） | 2026-10-26 | 待 Step 9 实施 | |
| 2（实施后验收） | 2026-10-26 | 有条件通过（102/116，0 失败，14 待办） | Trae (GLM-5.3-Flash) |
| Phase 6 执行确认 | 2026-10-26 | S1-S4 + F3/F4/F6 真站全过，终态复证 PASS（109/116） | Trae (GLM-5.3-Flash) |
| Phase 7 执行确认 | 2026-10-26 | T8/T9/F5/W3 + P3-1/P3-2 + 开发日志完成（116/116，0 待办） | Trae (GLM-5.3-Flash) |
| 3（终验） | 2026-10-26 | **验收通过**（116/116 · 单测 ALL PASS · 全量门禁 PASS 47/3/0） | Trae (DeepSeek-V4.1-Flash) |

---

## 14. 后续行动

| 行动 | 触发条件 | 状态 |
|---|---|---|
| Step 8 文档一致性对齐（含 W1-W3 回写） | 本文件确认后 | ☑ 2026-10-26 |
| Step 9 TDD 实施（Phase 0-5，先验红） | Step 8 通过后 | ☑ 2026-10-26 |
| Step 10 审查验收（第 2 轮，ADD 审计 + E6/E7 补测） | Step 9 通过后 | ☑ 2026-10-26（有条件通过，见 §13.2） |
| Phase 6 真站故障注入（S1-S4）+ F3/F4/F6 真站回归 | 用户授权 + 维护窗口 | ☑ 2026-10-26（见 §8 / §13.2，6/6 通过，终态复证 PASS） |
| Phase 7 手册回写 + O-176 登记（T8/T9/F5/W3）+ P3-1/P3-2 判据修正 + 开发日志 | 终验前 | ☑ 2026-10-26（116/116，见 §13.2） |
| 第 3 轮终验（翻"验收通过"，status → accepted） | Phase 6/7 完成后 | ☑ 2026-10-26（116/116；单测 ALL PASS；全量门禁 PASS 47/3/0） |
| B 站 GLM conf `CTX=65536` vs 台账 32768 核对 | 旁发现问题，另议 | ☑ 2026-10-26（站上实况 `CTX=65536`；变更来源 = O-168 甲 2026-10-24，备份 `glm-5.3-flash.env.bak-ctx32768-20261024`；台账 [params-ledger §1.4](../infer-load/params-ledger.md) 已由 32768 对齐为 65536，未改站上任何配置） |
| 若采纳 `Conflicts=` 另立 ADR（Q1） | 本轮不做 | ☑ 2026-10-26（**裁不采纳**：只覆盖 systemd 单元，管不到 halogen 容器（docker）与手工进程（Phase 6 S2 实证）；不隐含顺序 ⇒ 不能替代编排层卸载；不新增第二管理面（ADR-0004）。决定记于 DESIGN §5.5 / §12 Q1） |

---

**Review 签字**: _________ 日期: _________
