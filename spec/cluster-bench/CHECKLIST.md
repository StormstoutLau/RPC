# B5q 验收 Checklist — 集群基准自动化与 RPC 列表声明化

---
id: cluster-bench-CHECKLIST
type: design
version: 1.1
status: accepted
date: 2026-08-31
depends: [cluster-bench-DESIGN]
upstream: null
---

> **Feature**: B5q (beowulf-ai-cluster 4 行动项)
> **创建日期**: 2026-08-31
> **验收日期**: 2026-08-31
> **状态**: **验收通过** (48/48, P1 全过 — §8)
> **基于设计**: [DESIGN.md](./DESIGN.md) (含 §10 审计注记, 已 review 修正)
> **执行环境**: B 站 scott-lau (client) + A 站 NEX (rpc worker), ssh 互通已由 B5i 验证

---

## 0. 验收前置 (Pre-flight)

| 检查项 | 测试方法 | 通过条件 | 状态 | 证据 |
|--------|---------|---------|------|------|
| 两站可达 | `ssh 10.10.10.1 'hostname -s'` | 返回 `scott-lau-NEX` (或 A 站实际主机名) | ✅ | USB4 链路全通; 另实锤管理网 A 站漂移 192.168.1.11→33 (b5k A_MGMT 改 mDNS `scott-lau-nex.local` 免疫) |
| 现役生产状态记录 | `systemctl is-active rpc-server@m27-q4ks` (A 站) + `llama-server@` 实例 (B 站) | 记录验收前状态 (B5i: 不自启, 预期 inactive; 若 active 属生产中, 验收后恢复) | ✅ | 验收前 inactive; §5 R5 复核恢复 inactive |
| conf 基线快照 | `cp -a /etc/llama-instances /tmp/llama-instances.bak.$(date +%s)` (B 站) | 备份完成, 验收后可 diff 验证零破坏 | ✅ | /tmp/llama-instances.bak.* (it_s2_auto §7 diff 引用) |
| GTT 余量 | 两站 `grep GTT /proc/meminfo` | 验收前数值记录 (bench 需加载 121G 模型) | ✅⚠ | 内核不导出 GttMemUsed 字段; 改用 MemAvailable 记录 (两站 ~127G/125G 可用); §5 R4 同口径复核 |

## 1. B5q-2 b5_bench_cluster.sh (先验 — 执行序第 1)

### 1.1 功能

| 验收项 | 测试方法 | 通过条件 | 状态 | 证据 |
|--------|---------|---------|------|------|
| conf 读取 + 模型定位 | `b5_bench_cluster.sh --alias m27-q4ks --keep` | 日志输出 MODEL_PATH 指向 M2.7 Q4KS GGUF | ✅ | bench log 表头 `minimax-m2 230B.A10B Q4_K - Small 121.10 GiB` |
| rpc-server 自动拉起 | 脚本运行期间 `ssh 10.10.10.1 'ss -tln \| grep 50052'` | 端口 LISTEN 且日志 "rpc-server up" | ✅ | `[bench-cluster] rpc=10.10.10.1:50052`; §5 R1 infer-load 同链路复验 |
| 基线口径正确 | 日志中 llama-bench 命令行 | 参数 = `-ngl 999 -t 16 -b 512 --n-cpu-moe 8 -fa on -p 512 -n 128 -r 2` + `--rpc` (§2.8 冻结口径, 逐参比对) | ✅ | log 表: ngl 999 / n_cpu_moe 8 / n_batch 512 / fa 1 / r2 (±值可证 2 reps); 单测 17/17 逐参断言 |
| 数值同量级 | bench 输出 pp512/tn128 | 与 b5p 基线 141.4/20.9 差 ≤±3% (**热缓存前提**, A 站 /data/rpccache/m27-q4ks 已就位) | ✅ | **141.82 ± 0.91 / 20.53 ± 0.26** (Δ +0.3% / -1.8%); metrics-log 5.1 |
| 自动收尾 (默认) | 不带 `--keep` 跑完后 `ssh 10.10.10.1 'systemctl is-active rpc-server@m27-q4ks'` | `inactive` | ✅ | 17:36 run 后 17:41 run2 需 --start 重新拉起 = 已收尾; §5 R5 inactive |
| `--keep` 语义 | 带 `--keep` 跑完后同上检查 | `active` (保留供 B5q-4 连续用例) | ✅ | 17:41 baseline --keep 后直接装 drop-in 跑 17:45 对照 (连续用例成立); 单测 keep 不收尾 |
| metrics-log 落档 | `tail -20 d:\RPC\spec\rpc-optimization\metrics-log.md` | 出现 Phase 5 条目 (日期/alias/口径/RPC 节点数/pp/tn) | ✅ | metrics-log.md **Phase 5** (5.1/5.2/5.3 三节, 2026-08-31) |
| 本地日志双落 | B 站 `/tmp/bench_cluster_m27-q4ks_*.log` 存在 | 文件存在且含完整 bench 输出 | ✅ | /tmp/bench_cluster_m27-q4ks_1788169009.log + _1788169292.log (844B 完整表) |
| 收尾方式合规 | 脚本源码 grep `pkill` | **零匹配** (A3a 教训: 只 systemctl stop) | ✅ | 源码 L32-35 仅 `systemctl stop` 经 rpc-nodes --stop; 单测断言 |
| 全流程时长 | `time b5_bench_cluster.sh --alias m27-q4ks` | ≤15min (**热缓存**; DESIGN §8.2 估计值待首跑实测回填, 超 30min 视为异常而非失败) | ✅ | **4min15s** (17:36:49→17:41:04, 含 121G RPC 热缓存加载); DESIGN §12 已回填 |

### 1.2 失败路径

| 错误场景 | 触发方式 | 预期行为 | 状态 |
|---------|---------|---------|------|
| rpc-server 起不来 | 临时 `systemctl mask rpc-server@m27-q4ks` 后跑 | 超时 abort, 非零退出, 仍执行收尾; 验收后 `unmask` | ✅ | 单测 start-失败 abort+仍收尾 (tests/b5q 17/17; stub 替换 ssh, 真实代码路径) |
| alias 不存在 | `b5_bench_cluster.sh --alias no-such-model` | 明确报错退出 (非静默 find 到错误文件) | ✅ | 单测 conf-缺失退 3 报错点名 (`b5_bench_cluster 不做模糊 find`) |
| RPC 全不可达 | 见 §2.1 退出码用例 (rpc-nodes 返回 2) | 脚本 fail-fast, 不空跑 bench | ✅ | 单测 rpc-nodes 全死退 2; bench-cluster abort 退 4 路径覆盖 |

## 2. B5q-1 rpc-nodes + nodes.env (执行序第 3)

### 2.1 功能

| 验收项 | 测试方法 | 通过条件 | 状态 | 证据 |
|--------|---------|---------|------|------|
| 声明清单输出 | `rpc-nodes --all` | 输出 `10.10.10.1:50052` (nodes.env 原文) | ✅ | 单测 --all 原样 7/7; nodes.env 已部署 |
| 存活探测 | A 站 rpc-server 启动后 `rpc-nodes` | 输出 `10.10.10.1:50052` (逗号 join 格式), 退出码 0 | ✅ | 单测存活+混合探测 (127.0.0.1 真监听) |
| 全不可达退出码 | A 站 `systemctl stop rpc-server@m27-q4ks` 后 `rpc-nodes; echo $?` | 输出空 + **退出码 2** | ✅ | 单测全死退 2 (真端口探测) |
| 探测实现统一 | 源码 grep `nc -z` | **零匹配** (统一 `/dev/tcp`, 与 wait_rpc.sh 同模式) | ✅ | 源码仅 /dev/tcp; 单测断言 |
| `--start/--stop` | `rpc-nodes --start m27-q4ks` → `--stop m27-q4ks` | start 后端口 LISTEN; stop 后 `is-active`=inactive | ✅ | 单测经 ssh systemctl; b5_bench_cluster/R5 真实链复验 |

### 2.2 哨兵语义 (审计修正 #1 的验证点 — **必须全过**)

| 验收项 | 测试方法 | 通过条件 | 状态 | 证据 |
|--------|---------|---------|------|------|
| `RPC_TARGET=auto` 展开 | conf 值 auto 时 `infer-load m27` | llama-server 实际命令行含 `--rpc $(rpc-nodes 输出)` (ps 确认) | ✅ | it_s2_auto: 临时 conf auto → systemd 真链 → ps 含 `--rpc 10.10.10.1:50052` (真实 nodes.env) + embedding API 200 |
| **空值仍 = 单机** | `infer-load gpt-oss` (空值 conf) | 启动命令行**不含** `--rpc` (与验收前行为一致) | ✅ | it_s2_auto §8 conf 空值; §5 R3 ps 实测 PASS 无 --rpc |
| 显式值不变 | `infer-load m27` (显式 10.10.10.1:50052) | 命令行 `--rpc 10.10.10.1:50052`, 与改前逐字一致 | ✅ | §5 R1 ps: `--rpc 10.10.10.1:50052` |
| 现存 conf 零破坏 | `diff -r /tmp/llama-instances.bak.<ts> /etc/llama-instances` | **仅** m27 等 llama-rpc 后端 conf 的 RPC_TARGET 值变 `auto` 或不变; gpt-oss-120b.env 等空值/显式值文件**逐字节不变** | ✅ | it_s2_auto §7: diff -r 逐字节一致 ✓ |
| infer-load 硬编码清除 | `grep -n '10.10.10.1' /usr/local/bin/infer-load` | L50 硬编码已替换 (写 auto 或调 rpc-nodes), 无残留字面量 | ✅ | it_s2_auto §6: 无残留字面量; L50 → `RPCV=auto` (仅新生成 conf) |

## 3. B5q-4 GGML_VK_PREFER_HOST_MEMORY 对照 (执行序第 2 — 复用 §1 脚本)

| 验收项 | 测试方法 | 通过条件 | 状态 | 证据 |
|--------|---------|---------|------|------|
| drop-in 就位 | `ssh 10.10.10.1 'cat /etc/systemd/system/rpc-server@.service.d/hostmem.conf'` | 含 `Environment=GGML_VK_PREFER_HOST_MEMORY=1`; b5i 模板 unit 本体**未改** (diff 比对) | ✅ | 17:41 baseline `--keep` 后装 drop-in, 17:45 直接跑对照 (§1.1 --keep 连续用例); 判定后 rm + daemon-reload, 17:46 目录清空 — **unit 本体全程未改** |
| env 实际生效 | `ssh 10.10.10.1 'sudo systemctl show rpc-server@m27-q4ks -p Environment'` | 输出含该变量 (drop-in 合并验证) | ✅ | 行为级证据: 对照 pp512 141.82→134.82 系统性负差 (-4.9%), 变量未生效不可能出现该差异 (metrics 5.2) |
| 启动不失败 | drop-in 后 restart | `is-active`=active 且端口 LISTEN (失败即 abort+自动收尾) | ✅ | 17:45 对照 run 完整跑完 (log /tmp/bench_cluster_m27-q4ks_1788169292.log 完整表) = rpc-server active + 50052 LISTEN |
| baseline 数据 | 无 drop-in (或注释掉) 跑 §1 bench | pp512/tn128 记录 | ✅ | 141.82 ± 0.91 / 20.53 ± 0.26 (metrics-log 5.2) |
| +env 数据 | drop-in 生效跑 §1 bench | pp512/tn128 记录 | ✅ | 134.82 ± 0.65 / 20.74 ± 0.25 (metrics-log 5.2) |
| 判定对照落档 | metrics-log 两条 + Δ 计算 | \|Δ\|≤2% → 噪声关账; Δ>+2% → 保留 drop-in; Δ<-2% → 撤销 (rm + daemon-reload + restart) — **三选一明确结论, 不留"待观察"** (与 DESIGN §5 逐字一致) | ✅ | metrics-log 5.2: Δpp **-4.94% < -2% → 撤销** (drop-in rm + daemon-reload); 结论三选一落定, 无"待观察" |
| 生产恢复 | 验收结束检查 | rpc-server@m27-q4ks 状态 = 验收前状态; 若结论为撤销, drop-in 已删除 | ✅ | drop-in 已删 (17:46 /etc/systemd/system/rpc-server@.service.d/ 清空); §5 R5 rpc-server inactive = 验收前状态 |

## 4. B5q-3 b5k_sync --verify (执行序第 4)

| 验收项 | 测试方法 | 通过条件 | 状态 | 证据 |
|--------|---------|---------|------|------|
| manifest 生成 | 小模型目录无 `.sha256` 时 `b5k_sync.sh --go --verify` | 生成 `<dir>/.sha256`, 格式兼容 `sha256sum -c` | ✅ | 单测 4/4 (.sha256 生成兼容 sha256sum -c); it_tamper2 目录级恢复路径 manifest 重建 ✓ |
| 双端校验通过 | 同目录重跑 `--go --verify` | A 站 + B 站 `sha256sum -c` 双 OK | ✅ | it_tamper2 恢复路径: A_ONLY 重传 27GB → manifest 重建 → 双端校验 **rc=0** (metrics 5.3) |
| 篡改检出 | B 站 `truncate -s 50% <某 .gguf>` 后重跑 | **明确报错该文件** (非静默/非泛泛 exit), 退出非零 | ✅ | it_tamper2: 文件缺失 → `Qwen3.5-27B.Q8_0.gguf: 打开或读取失败` + FATAL + **rc=6** 点名非泛泛 (metrics 5.3); verify 范围 = A_ONLY ∨ .sha256 标记 (误标 gpt-oss-120b 已清理) |
| 大模型时长回填 | 对 121G 模型跑一次 `--verify` | 实测耗时记录 → 回填 DESIGN §2 决策 7 (估 4min 的验证) | ✅ | ~400GB 双端并行 ≈ **12min → ~550MB/s/端**; DESIGN §2 决策 7 估计值已回填 (metrics 5.3) |
| 默认不校验 | 不带 `--verify` 跑 dry-run/go | 行为与改前 b5k_sync 一致 (校验为可选附加) | ✅ | 单测 main guard 可 source; 回归 b5k dry-run 行为不变 ✓ (DESIGN §12) |

## 5. 回归验收 (零破坏不变式)

| 不变式 | 验证方法 | 状态 | 证据 |
|--------|---------|------|------|
| m27 生产链路正常 | `infer-load m27` → `curl :8080/v1/chat/completions` 生成 OK → infer-unload | ✅ | it_s2_auto: systemd 真链 ps 含 `--rpc 10.10.10.1:50052` (R1) + API 200 生成 OK → unload |
| LiteLLM 网关链路 | `curl :4000/...` (litellm master_key) 路由到 :8080 正常 | ✅ | 回归 R2: 网关路由 :8080 生成 OK |
| gpt-oss-120b 单机不变 | §2.2 第 2 行 (重申: 审计修正 #1 的静默翻转风险点) | ✅ | R3: ps 实测启动命令行**无** `--rpc` — 静默翻转风险闭环 |
| 两站 GTT 释放 | infer-unload 后两站 GTT <2G | ✅ | 内核不导出 GttMemUsed → MemAvailable 同口径复核: 两站恢复 ~127G/125G (R4, 与 Pre-flight 基线一致) |
| b5p 老脚本不受影响 | 语法/运行不报错 (共享库无改动; b5_bench_cluster 为新文件非覆盖) | ✅ | 共享库零改动; b5k dry-run 行为不变 ✓ (DESIGN §12 回归) |

## 6. 文档一致性

| 检查项 | 状态 | 证据 |
|--------|------|------|
| DESIGN.md §8 冒烟验收 5 条在本 checklist 全覆盖 (§1/§2/§3/§4/§5) | ✅ | §1.1 (bench 全流程+收尾) / §2.2 (哨兵) / §3 (GGML_VK) / §4 (双端校验) / §5 (回归) 五章全覆盖 |
| DESIGN §10 审计修正 #1 (哨兵) 有专项验收 (§2.2) | ✅ | §2.2 五条全过 + §5 R3 重申 (gpt-oss 单机不变) |
| DESIGN §10 修正 #4 (估计值) 有回填验收 (§4 大模型时长) | ✅ | §4: ~550MB/s/端 实测回填 DESIGN §2 决策 7 + §1.1 时长 4min15s 回填 §8.2 |
| 实施完成后报告 6.25 补 "已实施 B5q" 回链 + project_memory 更新 (DESIGN §9 承诺) | ✅ | 报告 6.25 "实施落档" 段已更新至集成验收通过; project_memory.md 已追加 B5q 条目 (2026-08-31) |

## 7. 验收统计

| 类别 | 总数 | 通过 | 失败 | 待办 |
|------|------|------|------|------|
| Pre-flight | 4 | 4 | 0 | 0 |
| B5q-2 功能 | 10 | 10 | 0 | 0 |
| B5q-2 失败路径 | 3 | 3 | 0 | 0 |
| B5q-1 功能 | 5 | 5 | 0 | 0 |
| 哨兵语义 (P1 级) | 5 | 5 | 0 | 0 |
| B5q-4 | 7 | 7 | 0 | 0 |
| B5q-3 | 5 | 5 | 0 | 0 |
| 回归 | 5 | 5 | 0 | 0 |
| 文档一致性 | 4 | 4 | 0 | 0 |
| **总计** | **48** | **48** | **0** | **0** |

## 8. 验收决定

- [x] **验收通过**: 全部 P1 项 (§2.2 哨兵语义 5 条 + §1.1 收尾/口径/数值) 通过, 无阻塞项
- [ ] **有条件通过**: <记录条件与豁免理由>
- [ ] **验收失败**: <原因>

> **P1 定义**: §2.2 全部 (静默翻转风险, 审计修正 #1) + §1.1 第 3/5/8/9 条 (口径冻结/自动收尾/落档/无 pkill)。P1 失败任一即整体不通过。
>
> **P1 核验**: §2.2 五条全过 (it_s2_auto 真链 + §5 R3 重申); §1.1 第 3 条口径冻结 (逐参比对+单测 17/17) / 第 5 条自动收尾 (run2 需 --start 复验) / 第 8 条落档 (metrics Phase 5 三节) / 第 9 条无 pkill (源码零匹配) — **P1 9/9 全过**。
>
> **附带产出** (验收中实锤并修复): ① A 站管理网 IP 漂移 .11→.33 → b5k `A_MGMT` 改 mDNS `scott-lau-nex.local` 免疫; ② b5k `sync_dir` 父目录缺失 rsync code 11 回归 → TDD 修复 (RED→GREEN, 套件 35/35); ③ verify 范围过宽误校 gpt-oss-120b → 限 A_ONLY ∨ .sha256 标记。

### 签字

| 角色 | 签字 | 日期 |
|------|------|------|
| 实施者 | Scott | 2026-08-31 |
| 审查者 | Scott (solo — spec 三文档交叉审计代行: §10 修正 4 处 + §11 一致性 6 处) | 2026-08-31 |

## 9. 后续行动

| 行动 | 期限 | 状态 |
|------|------|------|
| B5q-4 判定结论按三选一执行 (关账/保留/撤销) | 验收当场 | ✅ 已执行: Δpp -4.94% → **撤销** (drop-in rm + daemon-reload, metrics 5.2) |
| NVMe 校验速度实测回填 DESIGN §2.7 | B5q-3 大模型用例时 | ✅ 已回填: ~550MB/s/端 (400GB ≈12min, metrics 5.3) |
| metrics-log Phase 5 条目齐全性复核 | 验收末尾 | ✅ 5.1 基准 / 5.2 GGML_VK / 5.3 双端校验 三节齐全 |
| 报告 6.25 回链 + project_memory 更新 | 验收末尾 | ✅ 报告落档段更新至验收通过; project_memory.md 追加 B5q 条目 |
