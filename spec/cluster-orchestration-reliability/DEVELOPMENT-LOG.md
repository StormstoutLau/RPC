# 开发日志：cluster.py 加载/换模失败语义收敛（Development Log）

***

id: cluster-orchestration-reliability-DEVELOPMENT-LOG
type: dev-log
version: 1.0
status: active（持续维护中）
date: 2026-10-26
depends: \[cluster-orchestration-reliability-DESIGN, cluster-orchestration-reliability-IMPLEMENTATION, cluster-orchestration-reliability-CHECKLIST]
upstream: \[d6-agent-standard-OPEN-ISSUES（O-175/O-176）, docs/三机推理集群使用手册 §3.3]
------------------------------------------------------------------

> **用途**: 本 spec（`cluster.py` 加载/换模路径四缺口 → 响亮中止）的**唯一演进史**——按时间线记录「何时做了什么、为什么、验收证据、教训」。与 [CHECKLIST.md](./CHECKLIST.md)（验收面）和 [DESIGN.md](./DESIGN.md)（决策面）互补，不重复其内容。
> **规则**: 新条目**追加在最新日期顶部**（时间倒序）；每条含 事件 / 涉及文件 / 验收证据 / 教训 / 关联条目。

***

## 2026-10-26 — **spec 全程落地：Step 1-10 + Phase 6 真站注入（6/6）+ Phase 7 文档回写（116/116）**

### 事件

- **根因（四缺口，DESIGN §1）**：`cluster.py` 加载/换模路径在非理想返回下产生静默半成品——① 未知态误作忙（`probe-failed` 字符串进"回收它"分支）· ② worker 普通引擎未卸载（只对 head `infer-unload`）· ③ 回收失败不传播（7 个调用点丢弃返回值）· ④ 预检晚于销毁（先回收再查镜像）。
- **Step 1-8（调研/设计/实施/验收门）**：外部锚点调研（K8s 三态探针 / device plugin 独占 / `kubectl drain` 结构化返回 / Terraform plan-apply / SLSA digest，见 [调研](../../docs/research/2026-10-26_集群编排与RPC选路可靠性_社区外部锚点调研.md) §3）→ DESIGN → IMPLEMENTATION → CHECKLIST → Step 8 文档对齐（W1-W3）。
- **Step 9 TDD 实施（Phase 0-5）**：**先验红** 33 FAILED（[phase0-red.log](./phase0-red.log)）→ 落地三态探针（`classify_worker_probe` / `probe_worker_state` / `resolve_rpc_worker` 六分支）、回收契约（`reclaim_and_unload` 结构化返回 + 7 调用点消费）、容器预检前置（`preflight_container`）、门禁新断言（`halogen-assets`）；单测 14 条 ALL PASS。
- **Step 10（第 2 轮验收）**：有条件通过 102/116——余项为 Phase 6 真站与 Phase 7 文档；ADD 审计补 E6/E7 纯函数用例。
- **Phase 6 真站故障注入（6/6 通过）**：F3 容器加载正常路径；F4+S2 auto 选路回收（B/C 手工占口引擎被 `infer-unload` 清掉、A 站 qwen 存活、GLM READY）；S3 ngram rename ⇒ 预检 `asset-missing` 中止旧服务不动；S4 镜像 rmi ⇒ `image-missing` + 后台拉取回位复绿；S1+F6 C 站 ssh 停止 ⇒ `unknown(ssh-failed)` ⇒ `aborted-unknown` 中止零回收。终态与初始基线一致（B 生产 qwen READY，A/C 空闲），门禁复证 PASS。
- **Phase 7 文档回写（本轮）**：T8 手册 §3.3 六行行为矩阵 + 「`load` 即独占」句（F5 与 DESIGN §7 逐字核对一致）；T9 [O-176](../d6-agent-standard/OPEN-ISSUES.md) 登记（缺口 2/3/4 落账 + 残留面 + S1 教训）；W3 / P3-1（IMPLEMENTATION §1 行号快照更新为现值 L792/L1098/L1230/L1465/L1576/L1596/L1613）/ P3-2（PF4 判据"约 6 次"→"约 9 次"）修正；本日志新建。统计 **116/116 · 0 待办**。

### 涉及文件

`ops/cluster.py`（选路/回收/预检/调用点）· `ops/cluster_const.py`（配方 `assets`）· `ops/rpc_check.py`（`check_aliases` 站级校验 + `halogen-assets`）· `tests/test_cluster_pure.py`（T1-T14）· `docs/三机推理集群使用手册.md`（§3.3）· `spec/d6-agent-standard/OPEN-ISSUES.md`（O-176）· 本 spec 四件套 + 本日志。

### 验收证据

先验红 `RESULT: 33 FAILED`（phase0-red.log）→ 单测 `ALL PASS`（含 E6/E7）→ Phase 6 真站六项（CHECKLIST §8 逐字实录）→ 门禁 halogen-assets + engine 绿（2/0/0）→ 116/116（CHECKLIST §13.1）。

### 第 3 轮终验（2026-10-26 · 验收通过）

- **门条件核对**：§13.1 统计 116/116 · 0 待办；P0 全过；P1（F5）已核对一致；无 P1/P2 审计发现遗留。
- **复证读数（逐字）**：`tests\test_cluster_pure.py` ⇒ `RESULT: ALL PASS` / `EXIT=0`；全量门禁 `py ops\rpc_check.py` ⇒ `PASS · 绿灯 47 · 黄灯 3 · 红灯 0`（黄灯 = `evidence` 可重放 gap 37 存量 · `memory-gates` 引擎侧无门通道 1 条 · `stations` 已登记 `known_drift`；`py-tests` 54/54）；三站引擎态 `可达 3/3 站 · 在服务 1 站`（B 站生产 qwen）。
- **落位**：CHECKLIST front matter `status: pending → accepted`、正文「待验收 → 已验收」、§13.2 翻「验收通过」（有条件通过行标注为被取代并取消勾选）、§13.3 增第 3 轮签字、§14「第 3 轮终验」→ ☑；复跑 `doc-status/md-tables/doclinks` PASS（词表 105/105，`accepted` 合 checklist 档词表）。
- **未结（旁议，不阻断验收）**：B 站 GLM conf `CTX=65536` vs 台账 32768 核对；`Conflicts=` 是否另立 ADR（Q1）。

### 教训（Phase 6 实测沉淀）

1. **C 站 sshd 是 systemd socket activation**：`stop ssh.service` 后 `ssh.socket` 仍持 22 按需拉起；须同停 socket。**socket 停后 22 无监听，任何来源（含 B→C 兜底）都 Connection refused，唯一恢复 = 物理重启**（ssh.service enabled 自启已复证）——故障注入前必须先探通恢复路径。已入 O-176 残留面 (c)。
2. **Windows 主控防火墙写动作 UAC 受限**：`New-NetFirewallRule` Access denied ⇒ 注入手段改站上 `sudo systemctl stop ssh`（sudo -n 免密已验证）。
3. **S2 无完整小模型可注入**：C 站 0 gguf、A/B 无完整小模型 ⇒ 用 `/opt/llama.cpp/ggml-rpc-server` 改名 `/tmp/ds4-server` 占 8080——命令行含 `ds4-server` 恰好走 `infer-unload` 的 `pkill -9 -f '[d]s4-server'` 真实清理路径，busy 探测与清理两判据都真实。
4. **nohup 后台进程令 paramiko 等不到 EOF**（持 stdout 管道）⇒ 回显超时不等于注入失败，用独立探针（`probe_worker_state` = busy）证实后不重跑。
5. **PowerShell 内联 `python -c` 引号地狱** ⇒ 一律 Write 临时脚本文件再执行；临时脚本用完即删（本轮 p6_*.py 全部清理）。
6. **长行台账的编辑锚点**：OPEN-ISSUES 新行是 **6 格**形态（行尾无 `<br />` 填充格），锚点前先用字节级 grep 验证行尾真实形态，不凭视觉记忆。

### 关联条目

`O-175`（worker 自动避让，本 spec 前置）· `O-176`（本 spec 落账 + 残留面）· `ADR-0004`（唯一管理面/零 daemon）· `ADR-0014`（容器写动作扩权）· 手册 §3.3（行为矩阵消费方）· CHECKLIST §14 行动表（Phase 6/7 已勾，终验轮待做）。
