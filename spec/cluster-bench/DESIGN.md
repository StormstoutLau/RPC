# B5q 集群基准自动化与 RPC 列表声明化 — DESIGN

> **日期**: 2026-08-31
> **上游调研**: 《双机推理服务化与编排框架调研.md》v1.26 §6.25 (beowulf-ai-cluster 调研评估, **已 deep review 取证修正**)
> **执行站**: B 站 (主控/client) + A 站 (rpc worker)
> **范围**: beowulf 5 可借鉴点中的 4 个轻量行动项; 第 5 点 (多后端对照) 并入 B6 不单列; **不整体迁移 Ansible** (边界见 §6.25)

## 0. 依据 (审计后事实基线)

| 借鉴点 | beowulf 源码实证 (审计注记 #3-#6) | 我方现状差距 |
|--------|----------------------------------|-------------|
| RPC 列表声明式生成 | `llama_cpp-benchmark-cluster.yml`: `host_ips` 遍历 `groups[cluster][1:]` → `join(':50052,')` → `--rpc` | conf `RPC_TARGET` 与 bench 脚本均硬编码 `10.10.10.1:50052`, 多节点手拼 |
| 一键基准+自动收尾 | 同 play: `run_once` 跑 `llama-bench --rpc` → 末尾 `Ensure llama-rpc is stopped` | [b5p_lb_bench.sh](file:///d:/RPC/scripts/b5p_lb_bench.sh) 手工版: 起服务→bench→**不收尾不落档** |
| 下载 checksum 幂等 | `get_url force:false + checksum` (config 注释: 省略 checksum = 强制重下) | 下载侧已有 (lm-download 双验); **传输侧 b5k_sync 无校验**; 完整性教训 = B5m1/7.11 勘误 (B5m1a 行动项已撤销, 见报告 v1.5) |
| `GGML_VK_PREFER_HOST_MEMORY=1` | `example.config.yml` → 模板 `Environment=` 注入 rpc-server | rpc-server 路径**未实测** (llama-server 路径 DSpark 已用 `=ON`; 属不同进程不同路径) |

**审计修正声明**: 本设计不依赖 "fork 带 Strix Halo `__m128` 修复" 断言 (已推翻 — 实装为 geerlingguy 上游, 且 `4ff369a` patch 的是 dllama `sgemm.cpp`, 与我方 llama.cpp 路径无关)。4 个行动项均只依据上游 play 源码, 不受该修正影响。

## 1. 目标

1. C 站加入或临时多机基准时, RPC 节点列表**改一处配置**即生效 (声明式, 非 N 处硬编码)
2. 全集群 llama-bench 一条命令完成: 起 rpc-server → 基线口径 bench → 结果落 metrics-log → **自动收尾** (beowulf 模式)
3. 模型传输 (b5k_sync) 增加 sha256 终验, 补齐 B5m1/7.11 勘误完整性链条的传输段
4. `GGML_VK_PREFER_HOST_MEMORY=1` 在 rpc-server 路径的 A/B 对照实测, 零成本关账

## 2. 决策记录

1. **载体**: 纯 bash + systemd drop-in, 不引入 Ansible — beowulf 价值在**模式** (声明式列表/自动收尾/checksum) 不在工具链; 我方已有 systemd 模板 unit 体系 (B5i), Ansible 为其超集无净增益
2. **节点清单 = `/etc/llama-instances/nodes.env`** (B 站): beowulf 的 inventory 等价物。声明式 RPC_NODES, 探测存活后 join — 不自动发现 (IP 由 USB4 网段固定分配, 自动发现是过度工程)
3. **RPC 列表生成 = `rpc-nodes` helper** (B 站 /usr/local/bin): 读 nodes.env → 逐节点 `/dev/tcp` 探测 → 输出 join 列表; 供 infer-load 与 bench 脚本共用 (单一事实源)
4. **conf 的 RPC_TARGET 语义扩展 (哨兵值, 不动空值语义)**: **空值 = 单机** 的现行语义**保留不变** (审计实证: B 站 `gpt-oss-120b.env` 即空值单机, `llama-serve-instance` 以 `-n` 判空跳过 `--rpc`; 空改自动会静默翻转该模型行为); 新增哨兵 `RPC_TARGET=auto` = 运行时调 rpc-nodes。**已有显式值/空值的 conf 全部行为不变**
5. **bench 脚本 = `b5_bench_cluster.sh`** (B5q 主载体): b5p_lb_bench.sh 泛化 + 自动收尾 + metrics-log 追加。收尾用 `systemctl stop` (不用 pkill — A3a 教训: pkill -f 自杀坑)
6. **B5q-4 用 systemd drop-in 注入 env**: `/etc/systemd/system/rpc-server@.service.d/hostmem.conf` — 零侵入可增删 (不改 b5i 模板 unit 本体), `systemctl restart` 即生效
7. **B5q-3 校验粒度**: b5k_sync `--verify` 对每个 `.gguf` 双端并行 sha256 对比 (速度**实测 ~550MB/s/端**, 400GB ≈ 12min, 2026-08-31 集成验收回填 — 原估 ~500MB/s 偏保守 10%); manifest 生成 = b5j 合并后写 `<model>/.sha256`; 默认 dry-run/go 不校验 (加时验收, 闲时执行)
8. **基线口径冻结**: `-ngl 999 -t 16 -b 512 --n-cpu-moe 8 -fa on -p 512 -n 128 -r 2` (与 139.19 基线完全同参, 保证跨版本可比 — 不引入新口径)
9. **执行顺序**: B5q-2 (脚本) → B5q-4 (首个用例, 顺便验证脚本) → B5q-1 (rpc-nodes + infer-load 集成) → B5q-3 (b5k --verify)

## 3. B5q-1 RPC 列表声明化

### nodes.env (B 站, 新)

```bash
# /etc/llama-instances/nodes.env  — 集群 RPC 节点声明清单 (B5q)
# 格式: RPC_NODES 空格分隔 ip:port; C 站加入时追加一行即可
RPC_NODES="10.10.10.1:50052"
# RPC_NODES="10.10.10.1:50052 10.10.10.3:50052"   # C 站示例
```

### rpc-nodes helper (B 站 /usr/local/bin/rpc-nodes, 新)

```
rpc-nodes                # 输出存活节点 join 列表 (逗号分隔, 供 --rpc)
rpc-nodes --all          # 输出声明清单 (不做存活探测)
rpc-nodes --start <alias>  # 对各节点 systemctl start rpc-server@<alias> (经 ssh) 并等端口
rpc-nodes --stop <alias>   # 各节点 systemctl stop
```

- 探测: `timeout 2 bash -c 'echo > /dev/tcp/<ip>/<port>'` (b5i 已用此模式)
- 多节点语义: llama.cpp RPC 客户端对多 `--rpc` 目标按张量**分片承载** (依据: beowulf play 逗号 join 用法 + llama.cpp 官方 RPC 多服务器用法; 与我方现状语义同型 — A 站 rpc-server 即承载 B 站 llama-server 推送的张量分片, 见报告 6.13); 每节点须先起同 alias 的 rpc-server (per-alias 缓存 `LLAMA_CACHE=/data/rpccache/<alias>` 已由模板 unit 保证)
- 退出码: 0 至少一节点存活; 2 全不可达 (调用方 fail-fast)

### infer-load 集成点 (B5i 既有 CLI 增强, 不改接口)

- 生成/刷新 conf 时: 后端判定为 llama-rpc → 写 `RPC_TARGET=auto` (替代现硬编码 `10.10.10.1:50052`, B 站实装 infer-load L50)
- `infer-load`/`llama-serve-instance` 执行时: conf `RPC_TARGET` 值为 `auto` → 展开为 `$(rpc-nodes)` 输出 (临时增删节点不刷 conf); **空值仍 = 单机** (现行语义)

## 4. B5q-2 b5_bench_cluster.sh (一键集群基准)

```
b5_bench_cluster.sh [--alias m27-q4ks] [--pp 512] [--tn 128] [-r 2] [--keep]
```

流程 (beowulf `llama_cpp-benchmark-cluster.yml` 的 bash 等价物):

```
1. 读 conf /etc/llama-instances/<alias>.env → MODEL_PATH (**conf 不存在 → 明确报错退出**; 与 b5p 手工脚本的模糊 find 刻意不同 — 集群自动化要求确定性, CHECKLIST §1.2 有专项失败路径)
2. RPC 列表 = rpc-nodes --start <alias>   (A 站 systemctl start rpc-server@<alias> + 等端口就绪, b5p 模式)
3. llama-bench 基线口径 (§2.8 冻结参数) + --rpc <列表>  2>&1 | tee <log>
4. 自动收尾: rpc-nodes --stop <alias>     (除非 --keep; beowulf "Ensure stopped" 等价)
5. 追加结果到 spec/rpc-optimization/metrics-log.md (Phase 5, 日期+alias+口径+pp/tn 值)
```

- 日志: `d:\RPC\spec\rpc-optimization\` 与 B 站 `/tmp/bench_cluster_<alias>_<ts>.log` 双落
- 坑规避 (项目记忆): 收尾**只 systemctl stop 不 pkill**; ssh 单命令内不混合 kill/start

## 5. B5q-4 GGML_VK_PREFER_HOST_MEMORY 对照 (B5q-2 首个用例)

| 步 | 操作 |
|---|------|
| 1 | `b5_bench_cluster.sh --alias m27-q4ks` → baseline (无变量) |
| 2 | A 站: `sudo mkdir -p /etc/systemd/system/rpc-server@.service.d && sudo tee .../hostmem.conf` 写 `Environment=GGML_VK_PREFER_HOST_MEMORY=1` → `daemon-reload` |
| 3 | `rpc-nodes --stop m27-q4ks` → 再跑步骤 1 (restart 使 env 生效) |
| 4 | 结果对照落 metrics-log; **判定 (与 CHECKLIST §3 逐字一致)**: \|Δ\|≤2% → 噪声级关账 (预期 — APU 统一内存下 host/device 同物理内存, beowulf 该项针对独立显存 GPU); Δ>+2% → 保留 drop-in; Δ<-2% → `rm hostmem.conf` + daemon-reload + restart 恢复 |
| 5 | 无论结论如何, 恢复生产: `rpc-server@m27-q4ks` 状态回执行前 (B5i: 不自启, 手动按需 start) |

- 风险: rpc-server 因 env 改变分配策略导致启动失败 → 步骤 4 前先验证 systemctl start 成功 + 端口就绪 (b5_bench_cluster 内建等待, 失败即 abort 并自动收尾)

## 6. B5q-3 b5k_sync --verify (传输段 checksum)

- manifest: b5j 合并 (及 lm-download 收编) 后, 在 B 站 `<model-dir>/.sha256` 生成 `sha256` (每分片一行, `sha256sum` 输出格式, 直接可 `sha256sum -c`)
- `b5k_sync.sh --go --verify`: rsync 完成后, 对本次同步的每个目录:
  1. 无 `.sha256` → 生成后继续 (首次)
  2. 有 → A 站 `sha256sum -c .sha256` + B 站 `sha256sum -c .sha256` 双端验 (A 端验源完整, B 端验传输)
- 校验失败 → 明确报错该文件, 不静默 (B5m1/7.11 勘误教训: 完整性问题必须显式暴露)
- 与 beowulf `get_url checksum` 的关系: 语义等价 (存在即验, 失败即停); 断点续传能力 (rsync `--partial`) 为其超集

## 7. 不做清单 (边界, 沿 §6.25)

- **不迁 Ansible**: 我方 systemd 模板 unit + infer-* CLI 已覆盖 beowulf 全部部署语义且版本化更细
- **不引入 exo/dllama**: prev 排除结论维持 (AMD395 报告), beowulf 的 dllama play 含 fork 的 `sgemm.cpp` SSE/AVX patch — 与我方无关
- **多后端对照**: 归 B6 (spec/model-eval, 冻结待启动), 本 spec 不重复

## 8. 冒烟验收

1. `rpc-nodes` 输出 `10.10.10.1:50052`; 断 A 站服务后输出空且退出码 2
2. `b5_bench_cluster.sh --alias m27-q4ks` 全流程 ≤ 15min (**热缓存前提** — A 站 rpccache/m27-q4ks 已就位, 冷缓存首跑权重推送另计): bench 数值与 b5p (141.4/20.9) 同量级 (±3% 噪声), metrics-log 出现 Phase 5 条目, 收尾后 A 站 `systemctl is-active rpc-server@m27-q4ks` = inactive
3. B5q-4 产出对照两行数据 + 明确判定结论 (关账/保留/撤销) 落 metrics-log
4. `b5k_sync.sh --go --verify` 对任一小模型 (~1-2G) 双端校验通过; 人为截断一个文件后重跑 → 报错且不通过
5. 现有 conf 行为零变化 (回归: infer-load m27 照常; **gpt-oss-120b (空值单机) 照常单机** — 哨兵语义验证点)

## 9. 度量与落档

- **metrics-log Phase 5** (spec/rpc-optimization/metrics-log.md): 每次 b5_bench_cluster 一条 (日期/alias/口径/RPC 节点数/pp512/tn128/备注); B5q-4 对照两条 (±env)
- 实施完成后报告 6.25 补 "已实施 B5q" 回链; project_memory 报告索引更新

## 10. 审计注记 (2026-08-31, spec 规范 review)

对本文档初版逐断言取证 (B 站实装代码 + 项目档案), 修正 1 处逻辑矛盾 + 3 处表述:

| # | 初版断言 | 取证 | 处置 |
|---|---------|------|------|
| 1 | "conf RPC_TARGET 留空 = 自动 (调 rpc-nodes)" | B 站实装: `gpt-oss-120b.env` 有 `RPC_TARGET=`(空), `llama-serve-instance` L12 `[ -n "${RPC_TARGET:-}" ]` 判空跳过 `--rpc` → **空值现行语义 = 单机**; 留空改自动会静默翻转该模型行为, 与"不破坏现有 conf"自相矛盾 | **修正** (决策 4/§3): 改哨兵 `RPC_TARGET=auto`, 空值语义不动 |
| 2 | "b5m1a 完整性教训" | 报告 v1.5 勘误: **B5m1a 行动项已撤销** (GLM 00001 误判复盘, 00001 真为 header-only 小分片); 教训本体出自 B5m1/7.11 勘误 | **修正** (§0/§1 目标 3/§6): 改引 "B5m1/7.11 勘误教训" |
| 3 | "多 --rpc 是分片并行" + 探测方式两处不一致 (决策 3 `nc -z` vs §3 `/dev/tcp`) | beowulf play 逗号 join ✓; "分片" 与我方 6.13 机理 (A 站承载 B 站推送的张量分片) 同型, 但初版未标依据且措辞含混; 探测实际项目先例是 wait_rpc.sh 的 `/dev/tcp` | **修正** (§3): 改"张量分片承载"+双依据标注; 探测统一 `/dev/tcp` |
| 4 | NVMe ~500MB/s / 验收 ≤15min | 均为估计值, 项目无实测 (lm-download 46-52MB/s 是网络侧) | **精化**: 标注估计待首跑回填; 验收加"热缓存前提" |

**成立断言 (未改)**: infer-load L50 硬编码 `10.10.10.1:50052` ✓ (ssh 实查); b5p_lb_bench.sh 无收尾无落档 ✓ (源码); b5k_sync 无校验 ✓ (源码); metrics-log Phase 0-4 结构 + 4.6 审计节 ✓ (文件实读); b5p 141.4/20.9 ✓ (v1.26 记录); A3a pkill 坑 ✓ (memory); drop-in Environment= 追加语义 ✓ (systemd 规则); beowulf 上游 play 源码 4 项引用 ✓ (6.25 审计注记 #3-#6)。

**方法论沉淀**: 设计文档中"改变现有行为"类断言, 必须先实查**所有现存消费方**对该取值语义的实际处理 (此例: 空值在 llama-serve-instance/infer-load 两处的分支), 档案中被撤销的行动项 (B5m1a) 不得再作为教训引用。

## 11. 三文档一致性审查 (2026-08-31)

对 报告 6.25 / 本 DESIGN / CHECKLIST.md 三方交叉比对, 发现并修复 6 处:

| # | 不一致 | 处置 |
|---|--------|------|
| 1 | 报告 6.25 款目 1 建议 "自动收集各节点 USB4 IP" vs 决策 2 "不自动发现" (机制矛盾) | 报告改为 "声明式节点清单 rpc-nodes, 非自动发现" |
| 2 | §1 目标 3 残留 "b5m1a" (§0/§6 已改, 修正范围声明遗漏) | 目标 3 改引; §10 修正 #2 处置范围补 "§1 目标 3" |
| 3 | §4 流程 1 "模糊 find" vs CHECKLIST §1.2 "报错非静默 find" (行为矛盾) | §4 改 "conf 不存在 → 报错退出" (集群自动化要确定性, 与 b5p 手工模式刻意不同) |
| 4 | §5 判定 "负差→撤销" 无阈值 vs CHECKLIST "≥3% 负差"; 且 2%~3% 灰区双方未定义 | 统一为: \|Δ\|≤2% 关账 / Δ>+2% 保留 / Δ<-2% 撤销 (阈值连续无灰区, 两文档逐字一致) |
| 5 | CHECKLIST 缺 §8.2 "≤15min" 时长验收 | CHECKLIST §1.1 补时长项 (总 48 项) |
| 6 | 报告 "实施落档" 段未反映本文档二次审计与 CHECKLIST 配套 | 报告落档段补全三文档状态 |

**方法论沉淀**: 上游调研报告中的"建议"措辞必须与下游 DESIGN 的决策一致 (调研时设想的机制可能在设计阶段被否决 — 自动发现即此例); 数值判定阈值在设计/验收两文档必须**逐字一致且连续覆盖** (无未定义灰区)。

## 12. 实施记录 (2026-08-31, TDD 执行)

**单元层 Red-Green 完成: 31/31 GREEN** (测试 [tests/b5q/](file:///d:/RPC/tests/b5q) 本地版本化, B 站 `~/b5q-tests/` 执行; 真实代码优先 — 127.0.0.1 真监听端口探测, stub 仅替换外部副作用源 ssh/llama-bench/llama-server):

| 组件 | 结果 | 覆盖 |
|------|------|------|
| rpc-nodes | 7/7 | 缺 env 退 3 / --all 原样 / 全死退 2 / 存活+混合探测 / --start--stop 经 ssh 发 systemctl |
| b5_bench_cluster.sh | 17/17 | conf 缺失退 3 (不模糊 find) / 冻结口径**逐参**断言 / 默认收尾 / --keep 不收尾 / start 失败 abort+仍收尾 / 日志落盘 / metrics Phase 5 条目 |
| llama-serve-instance 哨兵 | 3/3 | auto→rpc-nodes 展开 / **空=单机 (审计修正 #1 防回归)** / 显式透传 |
| b5k_sync manifest/verify | 4/4 | main guard 可 source / .sha256 生成兼容 sha256sum -c / 完整通过 / 篡改**点名报错**非零退出 |

- **RED 证据**: 初跑 31 项全失败且均为功能缺失; 期间修正 2 处**测试自身缺陷** (TDD 纪律): ① 哨兵 T2 假通过 (grep 作用于不存在文件, 取反误判 pass — 加 server 真执行断言) ② 探测竞态 (start_listener 无就绪等待, 而默认探测模式按设计单次尝试 — 测试侧补就绪循环, 实现不改)
- **部署**: `rpc-nodes`/`b5_bench_cluster.sh` → /usr/local/bin; `nodes.env` → /etc/llama-instances; `llama-serve-instance`/`infer-load` 原地替换 (备份 `*.bak-b5q`); `b5k_sync.sh` → ~/scripts (main guard 重构); 源文件均版本化于 d:\RPC\scripts\
- **infer-load L50**: `RPCV=auto` (仅影响新生成 conf; 现有 conf 不重写)。集成验证归 CHECKLIST §2.2
- **回归**: b5k dry-run 行为不变 ✓; 现存 4 个 conf 逐字节不变 (gpt-oss-120b 空=单机 ✓, 其余显式值 ✓)
- **集成层已完成 (2026-08-31, CHECKLIST 48/48 验收通过)**: 真实 bench 全流程 4min15s (141.82/20.53, Δ ≤±2%) / B5q-4 GGML_VK 对照 Δpp -4.94% → 撤销 / b5k --go --verify 双端 (篡改 rc=6 点名 + 恢复 rc=0 + NVMe ~550MB/s/端 实测回填) / infer-load auto conf 真链实测 (ps 含 --rpc)。另修复 3 处验收中实锤问题: A_MGMT mDNS 化 (IP 漂移免疫) / sync_dir 父目录 TDD 修复 (套件 35/35) / verify 范围闸门 (A_ONLY ∨ .sha256 标记)
- **新坑记录**: 远程诊断命令含目标进程名字面量时 `pkill/pgrep -f` 自匹配杀掉自身 ssh 会话 (现场重演两次) — 用 `http[.]server` 括号技巧规避; 归入 A3a pkill 坑族
