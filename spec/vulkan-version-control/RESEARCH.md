# 调研文档：Vulkan 后端版本控制

---
id: vulkan-version-control-RESEARCH
type: design
version: 1.0
status: draft
date: 2026-08-27
depends: []
upstream: null
---

> **Feature**: Vulkan llama.cpp 后端版本控制（A/B 双机 RPC 集群）
> **创建日期**: 2026-08-27
> **状态**: in-review
> **Spec 步骤**: Step 1-2
> **调研前置**: 调研已于本会话完成（SSH 实测 + WebSearch 4 轮 16 查询），原始记录见 [D:\RPC\提速调研报告.md](../../提速调研报告.md) v1.1 第五、六节

---

## 1. 调研目标

**核心问题**:
1. A/B 双机 RPC 集群的 llama.cpp（Vulkan 后端）如何建立可追溯、可回滚、可保证两站一致的版本控制机制？
2. 现有部署（`/opt/llama.cpp`，9859/4fc4ec554）如何零风险迁移到受控状态？
3. 升级到上游 v0.2.0+ 的分发/切换流程如何设计？

## 2. 调研方法

### 2.1 使用的工具

| 工具 | 用途 | 查询/命令 |
|------|------|------|
| SSH 实测（主控站→A/B 站） | 部署勘察 | `ls /opt/llama.cpp/`、`md5sum`、`--version`、`find ~/.lmstudio` |
| WebSearch | 上游版本与社区调研 | llama.cpp Strix Halo / RPC / MTP / Vulkan 性能（4 轮 16 查询） |
| 搜索结果内联抓取 | issue/PR 细节 | #22850 / #24438 / #27544 / v0.2.0 release |
| 本地执行 | LM Studio 后端勘察 | extensions/backends 目录、`llama-server --help` |

### 2.2 调研范围

- **时间范围**: 2026-04 ~ 2026-08（llama.cpp b8xxx ~ v0.2.0）
- **领域**: llama.cpp 构建分发、ggml RPC 协议、Strix Halo (gfx1151) Vulkan 生态
- **排除**: Windows 侧部署、ROCm 生产化（调研结论已定 Vulkan 主线，见提速报告 §3.2）

## 3. 调研发现

### 3.1 现状实测（E1 级证据，2026-08-27 本会话执行，命令可重放）

#### 实测记录 1：部署现状

- **来源**: SSH 命令实测（A/B 两站）
- **验证状态**: ✅ 已验证（命令可重放）
- **关键结论**:
  - 两站 `/opt/llama.cpp` 仅含二进制 + `.so` + 空 `build/`，无源码、无 CMakeCache、无 git —— 零构建可追溯性
  - 版本 `9859 (4fc4ec554)`，GNU 11.4.0 构建；系统现装 gcc 13.3.0 —— 原构建环境不可复现
  - 两站关键产物 MD5 一致：`llama-cli`=126494d9…、`libggml-vulkan.so`=a5664d8f…、`libggml-rpc.so`=362a6987…、`libggml-cpu-zen4.so`=33dd2ce1…
  - RPC 协议版本：A 站 server 日志 `Starting RPC server v4.0.1`
  - 磁盘：两站各 ~900GB 可用；`.so` 内嵌版本号（`libllama-common.so.0.0.9859`）—— 同目录混放多版本会链接错乱
  - 脚本硬编码：A 站 `/llama-distributed/start_rpc.sh`、B 站 `/llama-distributed/run_inference.sh` + `inference.conf`、B 站 `~/llama-distributed/run_server.sh` 全部引用 `/opt/llama.cpp/`
- **与本 feature 的相关性**: 版本控制设计的全部起点约束

#### 实测记录 2：网络可达性

- **来源**: curl 实测（A 站）
- **验证状态**: ✅ 已验证
- **关键结论**: B 站 GitHub git+HTTPS 直连可达；A 站 git 协议无输出但 **HTTPS 可达**（`github.com: 200`、`codeload tarball: 200`，实测 1.8s）
- **相关性**: 决定 B 站为构建源，A 站 tarball 直下为应急后备

#### 实测记录 3：LM Studio 后端（借用分析）

- **来源**: 目录勘察 + `--help` + MD5
- **验证状态**: ✅ 已验证
- **关键结论**: 两站 vulkan-avx2-2.29.1（2026-08-22）MD5 一致，但 **无 `libggml-rpc.so`、无 `--rpc` 参数、无 `rpc-server` 二进制**；是 LM Studio fork（自研 engine 协议 + Node 绑定，`version: 1 (dd1ea52)`），版本号与上游 b 序号不对应 —— 不可借用于 RPC 链路，可作单机通道
- **相关性**: 否决"借用 LM Studio 后端"方案；附带发现 A 站 `~/Applications/llama-gfx1151/` 有 b1292 ROCm+RPC 历史构建（2026-06，仅作 ROCm 后备参考）

### 3.2 上游与社区

#### 来源 1：llama.cpp 官方仓库

- **标题**: ggml-org/llama.cpp — v0.2.0 release
- **日期**: 2026-08-25
- **验证状态**: ✅ 已验证（WebSearch 摘录 release notes）
- **关键结论**: 自 v0.2.0 起语义化版本（X.Y.Z 标 stable，b 序号 tag 为 nightly）。当前部署 9859（2026-07-02 构建）落后约 1700 build。期间关键改动：MTP 投机解码主线化（PR #22673）、Vulkan KV 反量化单次化（b10517）、RPC 多线程加载（PR 26291，`GGML_RPC_LOAD_THREADS`）
- **与本 feature 的相关性**: 升级目标版本与 changelog 依据

#### 来源 2：RPC 性能缺陷 issue

- **标题**: issue #22850 "Essential RPC performance degradation"
- **作者/日期**: karambaso, 2026-05（build b9033）
- **验证状态**: ✅ 已验证（WebSearch 全文摘录）
- **关键结论**: RPC 同步请求-响应（每 op 每层往返）、元数据风暴（每次图执行重序列化张量元数据）、小张量冗余传输（<10MB 跳过 hash 裸传）；实测 RPC 比本地 PCIe 慢 28%~55%
- **与本 feature 的相关性**: 升级需两站原子切换的最强依据；协议行为细节

#### 来源 3：Vulkan+MTP+并行塌缩 issue

- **标题**: issue #27544 "spec + vulkan: Performance Drop with MTP n-max > 1 and -np > 1"
- **作者/日期**: Stoney49th, 2026-08-22（未解决）
- **验证状态**: ✅ 已验证
- **关键结论**: AMD Vulkan 特有组合塌缩（NVIDIA 不受影响）
- **与本 feature 的相关性**: 版本控制落地后启用 MTP 的运行参数约束（范围外，已记入提速报告 Tier 2 注意事项）

#### 来源 4：AMD 官方 Playbook

- **标题**: "Clustering Two Ryzen™ AI Halos with RPC"（developer.amd.com）
- **验证状态**: ✅ 已验证（WebSearch 摘录）
- **关键结论**: AMD 官方推荐两台 Halo 用 llama.cpp RPC 聚合跑 358B 模型；`amd-ttm --set 120` 配置共享内存
- **与本 feature 的相关性**: 架构路线官方背书（当前链路即此形态）

#### 来源 5：Strix Halo 社区调优

- **标题**: botAGI/strix-halo-multislot、kryoz/llama-strix-halo
- **验证状态**: ✅ 已验证（WebSearch 摘录）
- **关键结论**: 同硬件社区基线（32 并发聚合 236 t/s、内核参数组 +7~8%）—— 与版本控制正交，属 Tier 3 系统层
- **与本 feature 的相关性**: 范围外，引用为后续优化依据

## 4. 综合分析

### 4.1 关键发现总结

1. 两站当前 MD5 一致性靠历史部署事实维系，无机制保障；构建环境已不可复现（GNU 11.4 vs 系统 gcc 13.3）[置信度: ★★★★★（实测）]
2. RPC 协议无 ABI 稳定承诺，任何一站单独升级会导致集群失效 [置信度: ★★★★★（issue #22850 佐证 + 防御性约束）]
3. LM Studio 后端不可借用（无 RPC 支持）；A 站 HTTPS 可达 GitHub tarball [置信度: ★★★★★（实测）]
4. 升级收益明确（MTP / KV 优化 / 加载 3x），版本控制是所有提速措施的前置设施 [置信度: ★★★★☆（社区基准间接支撑，本 feature 不依赖此断言成立）]

### 4.2 技术 landscape

- 上游分发形态：git tag（b 序号 nightly + vX.Y.Z stable）+ 官方预编译 release（Linux Vulkan 包存在，但为通用 avx2 构建，非本集群所需的 RPC + 多变体 CPU dispatch 形态）
- 社区实践：单机用户用预编译包/container（kyuz0 toolboxes / LM Studio）；双机 RPC 用户稀少，无成熟版本管理方案
- 官方路径：AMD Playbook 只讲首次搭建，不讲版本演进

### 4.3 研究空白

双机 RPC 集群的"单点构建 + 原子分发 + 一致性巡检"完整闭环，社区无现成方案 —— 本 feature 填补此空白。

## 5. 幻觉排除审查（Step 2 Review）

> [RULE-1] 本节为完稿后的独立复核 pass（见 §5.5 复核记录），非与正文同次写入。

### 5.1 文献验证

| 引用 | arXiv/DOI | 验证方式 | 状态 |
|------|-----------|---------|------|
| llama.cpp v0.2.0 release | - | WebSearch 摘录 release notes（vuink 镜像页含完整 commit 列表） | ✅ |
| issue #22850 | GitHub | WebSearch 全文摘录（含 LLM 分析报告原文） | ✅ |
| issue #27544 | GitHub | WebSearch 摘录（含完整 compose 配置） | ✅ |
| AMD Playbook | developer.amd.com | WebSearch 摘录（含 amd-ttm 命令） | ✅ |
| botAGI/strix-halo-multislot | GitHub | WebSearch 摘录（含 headline 数字表） | ✅ |

### 5.2 技术声明验证

| 声明 | 来源 | 验证状态 |
|------|------|---------|
| 两站 MD5 一致（4 文件） | 本会话 ssh md5sum 实测 | ✅ E1 可重放 |
| A 站 HTTPS 可达 GitHub | 本会话 `curl -sI` 实测（200, 1.8s） | ✅ E1 可重放 |
| LM Studio 后端无 RPC | 本会话 ls + `--help` 实测 | ✅ E1 可重放 |
| RPC 协议版本 v4.0.1 | A 站 rpc 日志（rpc_20260827_213815.log） | ✅ E1 |
| 现有二进制 GNU 11.4 构建 | `llama-cli --version` 输出 | ✅ E1 |
| "RPC 无 ABI 稳定承诺" | issue #22850 描述协议缺陷 + 官方文档无兼容承诺 | ⚠️ 推断级（无官方明文；按防御性约束处理，不依赖其反向成立） |

### 5.3 待修正项

- [x] "RPC 无 ABI 稳定承诺"标注为推断级，按防御性约束处理
- [x] 所有实测命令可重放（记录于提速调研报告 v1.1）

### 5.4 门禁（v1.4 D4）

- [x] (a) 无 FALSIFIED 断言
- [x] (b) 无 CONFLICT / STEP_GAP_OPEN
- [x] (c) 阻断性断言双源满足（MD5/HTTPS/LM Studio 均实测 + 提速报告在案；"无 ABI 承诺"单源已标注防御性，不作为设计的阻断依赖）
- [x] (d) 假设区条目："升级 v0.2.0 后性能提升"为 [待定]，显式携带进 DESIGN 作为验收 A/B 项（不作为设计前提）

### 5.5 复核记录

| 项 | 结果 |
|---|---|
| 复核方式 | 完稿后独立 pass 逐条核对（自查·单视角，RULE-4） |
| 文献引用 | 5 条全部可溯源（WebSearch 摘录在会话记录） |
| 实测声明 | 6 条 E1 + 1 条推断级已标注 |
| 发现 | 0 项（扫描范围：全部 §3/§5 条目） |

## 6. 对设计的输入

### 6.1 可用的技术方案

- 版本目录 + symlink 原子切换（`/opt/llama.cpp-<ver>/` 并列，`/opt/llama.cpp` 为软链 —— 三个脚本路径零改动）
- B 站单点构建 + tar/manifest 分发 + A 站 MD5 校验
- MANIFEST 清单（commit / 构建环境 / cmake 参数 / MD5 列表）内置于每个版本目录
- 主控站巡检脚本（读两站 MANIFEST + md5sum 比对）
- A 站 HTTPS tarball 直下（应急后备，仅 B 站故障时）

### 6.2 关键约束

1. `/opt/llama.cpp` 路径必须稳定（三脚本硬编码引用）
2. so 内嵌版本号 → 必须目录级隔离，禁止同目录混版
3. 升级 = 两站原子事件；切换后需 RPC 冒烟测试
4. A 站无 git，只能消费 B 站产物或 HTTPS tarball
5. 第 0 步（9859 版本化）必须零风险：仅 `mv` + `ln -sfn` + 写 MANIFEST，全程不停 A 站 rpc-server（当前服务已停止，操作窗口无风险）

### 6.3 风险

| 风险 | 等级 | 缓解 |
|------|------|------|
| mv + symlink 操作失误致服务不可用 | 低 | MD5 已在案；操作前 `cp -a` 备份清单；symlink 建立后立即冒烟 |
| 新版 RPC 协议不兼容（v4.0.1 → 新版） | 中 | 升级 SOP 强制冒烟测试拦截；回滚 = 改链 |
| B 站构建产物在 A 站系统库不兼容（glibc/mesa 差异） | 低 | 两站同为 Ubuntu 24.04 + mesa 25.2.8（已实测一致）；MANIFEST 记录环境供比对 |

## 7. 参考文献

1. ggml-org/llama.cpp — v0.2.0 release（2026-08-25）. https://github.com/ggml-org/llama.cpp
2. karambaso — issue #22850: Essential RPC performance degradation（2026-05）. https://github.com/ggml-org/llama.cpp/issues/22850
3. Stoney49th — issue #27544: spec + vulkan: Performance Drop with MTP n-max > 1 and -np > 1（2026-08-22）. https://github.com/ggml-org/llama.cpp/issues/27544
4. AMD — Clustering Two Ryzen™ AI Halos with RPC. https://developer.amd.com/playbooks/clustering-rpc-server/
5. 本地实测记录 — D:\RPC\提速调研报告.md v1.1（2026-08-27）第五、六节

---

**Review 签字**: [已复核·自查（单视角，RULE-4 标注）] 日期: 2026-08-27
