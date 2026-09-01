# 设计文档：Vulkan 后端版本控制

---
id: vulkan-version-control-DESIGN
type: design
version: 1.0
status: draft
date: 2026-08-27
depends: [vulkan-version-control-RESEARCH]
upstream: null
---

> **Feature**: Vulkan llama.cpp 后端版本控制（A/B 双机 RPC 集群）
> **创建日期**: 2026-08-27
> **状态**: in-review
> **Spec 步骤**: Step 3-4
> **基于调研**: [RESEARCH.md](./RESEARCH.md)

---

## 1. 设计目标

为 A/B 双机 RPC 推理集群的 `/opt/llama.cpp`（Vulkan + RPC 构建）建立版本控制机制：版本可追溯（MANIFEST）、升级可回滚（symlink 原子切换）、两站一致性可验证（MD5 巡检），并以零风险的第 0 步将现有 9859 部署迁移到受控状态。

## 2. 设计依据

### 2.1 调研结论

| 调研发现 | 设计决策 | 引用 |
|---------|---------|------|
| 部署零可追溯性（无源码/CMakeCache/git） | 每版本目录内置 MANIFEST 清单 | RESEARCH.md §3.1 实测记录 1 |
| RPC 协议无 ABI 稳定承诺（推断级，防御性） | 升级定义为两站原子事件 + 冒烟测试门禁 | RESEARCH.md §3.2 来源 2、§5.2 |
| so 内嵌版本号，同目录混版会链接错乱 | 版本目录级隔离 `/opt/llama.cpp-<ver>/` | RESEARCH.md §3.1 实测记录 1 |
| 三脚本硬编码 `/opt/llama.cpp/` 路径 | 该路径转为 symlink，脚本零改动 | RESEARCH.md §6.2 约束 1 |
| A 站无 git 但 HTTPS 可达；B 站直连可达 | B 站唯一构建源；A 站 tarball 直下仅作应急 | RESEARCH.md §3.1 实测记录 2 |
| LM Studio 后端无 RPC，不可借用 | 排除该分发渠道，git tag 为唯一版本源 | RESEARCH.md §3.1 实测记录 3 |
| 升级收益（MTP/KV/加载 3x）[待定] | 作为验收 A/B 项携带，不作为设计前提 | RESEARCH.md §5.4 (d) |

### 2.2 相关 ADR

无（本 feature 为基础设施，不产生需 ADR 记录的架构决策；symlink 方案 vs 替代方案的选择理由见 §5）。

### 2.3 职责边界

**职责内**：`/opt/llama.cpp` 的版本化、分发、切换、一致性巡检、回滚。

**职责外**（声明"不回答"）：
- llama.cpp 源码本身的构建优化（编译参数调优属提速 Tier 1，另行处理）
- 运行参数调优（`--n-cpu-moe`、KV 量化等，属提速报告 Tier 1.2-1.5）
- LM Studio 单机通道的管理
- 三机扩展（拓扑变化时另行设计）

**能力边界**（声明"回答不了"）：
- 无法保证升级后性能提升（社区数据间接支撑，验收时 A/B 实测）
- 无法自动检测 RPC 协议不兼容（依赖冒烟测试的显式 PONG 验证）

## 3. 架构设计

### 3.1 整体架构

```
主控站 (Win10, D:\RPC\scripts\)
  ├── version_control.ps1 / .sh   巡检：读两站 MANIFEST + md5 比对
  └── 升级 SOP（人工驱动，分步执行）

B 站 GTR-Pro（唯一构建源）              A/B 两站（运行端）
  ~/src/llama.cpp        git 仓库        /opt/llama.cpp-9859/     版本目录（含 MANIFEST）
  ~/build/llama-<ver>/   构建目录        /opt/llama.cpp-<new>/    未来版本目录
  ~/dist/llama-<ver>.tar.gz ──scp──→    /opt/llama.cpp → symlink → 当前版本目录
                                        （三脚本路径不变）
```

### 3.2 模块划分

| 模块 | 职责 | 输入 | 输出 | 依赖 |
|------|------|------|------|------|
| M1 版本目录结构 | 版本物理隔离 | 现有 `/opt/llama.cpp` | `/opt/llama.cpp-<ver>/` + symlink | 无 |
| M2 MANIFEST 清单 | 构建可追溯 | 版本目录内容 | `MANIFEST` 文件（commit/环境/参数/MD5） | M1 |
| M3 巡检脚本（主控站） | 两站一致性验证 | 两站 MANIFEST + md5sum | 一致/不一致结论 + 差异明细 | M2 |
| M4 升级 SOP | 原子化升级流程 | B 站新构建 | 两站 symlink 同步切换 + 冒烟通过 | M1-M3 |

### 3.3 数据流

巡检：主控站 ssh A/B → 各自读取 `$MANIFEST` 头部（版本指纹）→ 主控站比对；不一致时 → 深度模式逐文件 md5sum 比对 → 输出差异。

升级：B 站 git checkout tag → 构建 → 安装到新版本目录 + 写 MANIFEST → 打 tar → scp 至 A 站 → A 站解压 + md5 校验 → 两站先后切换 symlink → 冒烟测试。

### 3.4 控制流

第 0 步（本 feature 实施）：M1 → M2 → M3（不涉 M4 执行，M4 仅文档化）。
后续升级（独立 feature）：按 M4 SOP 人工分步执行。

## 4. 接口定义

### 4.1 MANIFEST 文件格式（M2）

```ini
# /opt/llama.cpp-<ver>/MANIFEST — 由 <生成脚本> 于 <日期> 生成
commit      = 4fc4ec554              # git 短 hash 或 tag（无源码时标注 unknown）
version     = 9859                    # llama-cli --version 输出的 build 号
build_host  = unknown (pre-existing)  # 构建机（9859 为历史部署）
build_date  = 2026-07-02 (binary mtime 推断)
toolchain   = GNU 11.4.0              # --version 输出
cmake_flags = unknown (pre-existing)  # 无 CMakeCache，标注未知
rpc_protocol = v4.0.1                 # rpc-server 日志实测
[md5]
<md5>  <filename>                     # 目录内全部二进制与 .so（含符号链接目标）
```

约束：键名固定（巡检脚本解析依赖）；历史版本允许 `unknown` 值但必须显式标注。

### 4.2 巡检脚本接口（M3）

```bash
# D:\RPC\scripts\check_llama_version.sh — 在主控站 Git Bash / 或 ssh 直接执行
# 用法: bash check_llama_version.sh [--deep]
# 输出: 退出码 0 = 两站一致; 1 = 不一致; 2 = 连接失败
# stdout: 版本指纹对比 + [--deep 时] 逐文件 MD5 差异表
```

核心逻辑（伪码）：
```
for host in A, B:
    fingerprint[host] = ssh host "readlink /opt/llama.cpp; head MANIFEST 的 version/commit 行"
if fingerprint[A] != fingerprint[B]: exit 1（输出差异）
if --deep:
    md5a = ssh A "cd /opt/llama.cpp && md5sum 按清单"
    md5b = ssh B 同上
    diff md5a md5b → 差异表; 非空则 exit 1
```

### 4.3 升级 SOP 接口（M4，文档化）

见 §3.3 升级数据流 + RESEARCH.md §6.2 约束。SOP 的可执行化（build/distribute 脚本）留待升级 feature 实施，本 feature 只交付 SOP 文档与第 0 步。

## 5. 替代方案

### 5.1 方案 A: 版本目录 + symlink 原子切换（选择）

- **描述**: `/opt/llama.cpp-<ver>/` 并列共存，`/opt/llama.cpp` 为指向当前版本的 symlink；升级/回滚 = `ln -sfn` 一步。
- **优点**: 三脚本零改动（调研约束 1 直接满足）；回滚分钟级；目录隔离规避 so 版本号混链（约束 2）；实现成本最低。
- **缺点**: symlink 本身是单点（误删需一条命令重建）。
- **选择理由**: 满足全部 5 条关键约束中成本最低者；缺点可控（重建命令写入 SOP）。

### 5.2 方案 B: git 仓库直接部署（否决）

- **描述**: `/opt/llama.cpp` 即 git clone，`git checkout` 切版本，产物就地构建。
- **优点**: 版本管理内建；可 diff/bisect。
- **缺点**: A 站无 git 网络可达性（实测）——两站无法对称；就地构建违背"单点构建防环境漂移"（GNU 11.4 vs gcc 13.3 教训）；升级时目录内容原地变化，无快速回滚（须重新 checkout+build，分钟级变十分钟级）。
- **否决理由**: A 站不可用 + 无原子回滚。

### 5.3 方案 C: 官方预编译包分发（否决）

- **描述**: 直接用上游 release 的 Linux Vulkan 预编译包。
- **优点**: 免构建。
- **缺点**: 通用 avx2 构建，无多变体 CPU dispatch（本集群依赖 `libggml-cpu-zen4.so` 自动选择）；RPC client 可用但两站仍需一致分发；构建参数不可控（MANIFEST 退化为下载记录）。
- **否决理由**: 构建形态不匹配 + 失去构建可追溯性设计目标。

## 6. 数据结构

### 6.1 版本指纹（巡检用）

```bash
fingerprint = "<symlink 目标目录名>|<version 字段>|<commit 字段>"
# 例: "llama.cpp-9859|9859|4fc4ec554"
```

## 7. 错误处理

| 错误场景 | 处理方式 | 用户可见信息 |
|---------|---------|------------|
| ssh 连接失败 | 退出码 2，跳过该站 | `❌ <host> SSH 不可达` |
| MANIFEST 缺失/损坏 | 巡检报告警告，指纹取 symlink 目录名兜底 | `⚠️ <host> MANIFEST 缺失，指纹降级为目录名` |
| mv/symlink 操作失败（第 0 步） | 脚本 set -e 立即中止；原目录仍在（mv 原子性） | `❌ 第 N 步失败，未切换 symlink，服务路径未受影响` |
| 指纹不一致 | 退出码 1 + 差异明细 | `❌ 两站版本不一致: A=... B=...` |
| md5 深度比对差异 | 差异文件表 | `❌ 以下文件 MD5 不一致: ...` |

## 8. 不变式（Invariants）

1. **I1 路径不变式**: 任意时刻 `/opt/llama.cpp` 解析为一个存在的版本目录（symlink 或原目录，二选一）—— 三脚本的引用永不悬空。
2. **I2 隔离不变式**: 任一版本目录内的 `.so` 全部属于同一构建（目录级隔离，禁止跨目录符号链接到其他版本目录的产物）。
3. **I3 追溯不变式**: 每个版本目录存在 `MANIFEST`，`[md5]` 节覆盖目录内全部二进制与 `.so`；`md5sum -c` 在该目录下可校验通过。
4. **I4 一致性不变式**（稳态）: 巡检脚本指纹比对，A/B 两站 symlink 指向同名版本目录且指纹相同。
5. **I5 回滚不变式**: 切换 symlink 后的 5 分钟内，存在至少一个旧版本目录未被删除（回滚目标始终存在）。

## 9. 幻觉排除审查（Step 4 Review）

> [RULE-1] 本节为完稿后的独立复核 pass，非与正文同次写入。

### 9.1 设计基于已验证的调研结论

- [x] §2.1 表全部条目可追溯到 RESEARCH.md（逐行标注章节引用）
- [x] 无未经验证的假设（唯一假设"升级收益"已显式标 [待定] 并隔离在验收 A/B 项）
- [x] 无论证驱动的归因扭曲（方案对比基于实测约束，无案例裁剪）

### 9.2 替代方案审查

- [x] 列出 3 个替代方案（A/B/C）
- [x] B、C 各有明确否决理由（基于实测：A 站网络、构建形态）

### 9.3 职责边界审查

- [x] 职责外（4 项）与能力边界（2 项）显式声明（§2.3）

### 9.4 复核记录

| 项 | 结果 |
|---|---|
| 复核方式 | 独立 pass 逐条核对（自查·单视角，RULE-4） |
| 发现 1 | §4.1 MANIFEST 示例中 `[md5]` 节格式与 §8 I3 措辞需一致（已统一为"全部二进制与 .so"） |
| 发现 2 | 方案 C 否决理由中"RPC client 可用"表述含推测成分，已改写为事实性描述（两站一致性需求不变） |
| 发现数 | 2 项（均已当场修正） |

## 10. 对实施的输入

### 10.1 关键工程约束

1. 第 0 步操作顺序：`cp` 校验 → `mv` → `ln -sfn` → 冒烟 → 写 MANIFEST（mv 前不得建 symlink）
2. 9859 的 MANIFEST 允许 `unknown` 字段，但必须显式标注（不可留空或虚构）
3. 巡检脚本放主控站 `D:\RPC\scripts\`，通过 BatchMode ssh 执行（免密已就绪）
4. 脚本 set -e + 分步 echo，任何一步失败立即中止

### 10.2 风险与缓解

| 风险 | 缓解 |
|------|------|
| mv 期间恰好有进程启动引用旧路径 | 当前推理已停止（本会话实测确认两站进程清零）；脚本操作窗口 < 2s |
| symlink 误删 | I1 检查纳入巡检；SOP 含重建命令 `ln -sfn /opt/llama.cpp-<ver> /opt/llama.cpp` |
| MANIFEST 的 md5 与实际不符（手写错误） | 生成方式为脚本 `md5sum` 重定向，非手写；I3 验收用 `md5sum -c` 重放 |

---
---

**Review 签字**: [已复核·自查（单视角，RULE-4 标注）] 日期: 2026-08-27
