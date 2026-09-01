# DEV-LOG-008: Vulkan 后端版本控制（vulkan-version-control）

> **日期**: 2026-08-27
> **Feature**: spec/vulkan-version-control
> **执行**: 完整 10 步 Spec 流程（F:\Spec_Workflow\SPEC_PROCESS.md v1.4 规范）
> **结果**: ✅ 验收通过（37/37 项，P1=0，P2×1 接受，P3×2 已处置）

---

## 1. 做了什么

为 A/B 双机 RPC 推理集群建立 llama.cpp（Vulkan+RPC）版本控制机制：

**文档链**（D:\RPC\spec\vulkan-version-control\）：
- RESEARCH.md — 实测 + 社区调研（含 E1 级证据与门禁）
- DESIGN.md — 版本目录 + symlink 原子切换架构（3 方案对比，I1-I5 不变式）
- IMPLEMENTATION.md — 5 个交付物工程细节（DR-1~3 派生需求登记）
- CHECKLIST.md — 37 项验收全过 + 取证矩阵（E1-E4）
- UPGRADE_SOP.md — 升级六步流程 + 回滚 + 应急后备

**实施产物**（D:\RPC\scripts\）：
- version_step0_A.sh / version_step0_B.sh — 两站版本化迁移（幂等）
- gen_manifest.sh — MANIFEST 清单生成（61 个 MD5 条目）
- check_llama_version.sh — 两站一致性巡检（指纹 + --deep 全量 MD5）
- acceptance_tests.sh — C5/C8/C9/C10 验收脚本

**两站落地状态**：
- `/opt/llama.cpp-9859/`（实体目录，含 MANIFEST）+ `/opt/llama.cpp` → symlink
- 三脚本（start_rpc.sh / run_inference.sh / run_server.sh）路径零改动
- 巡检验证：60 文件 MD5 两站完全一致

## 2. 决策依据

- 方案 A（版本目录+symlink）胜出：满足全部 5 条约束（路径稳定/目录隔离/原子切换/A 站无 git/零风险第 0 步）中成本最低
- 方案 B（git 就地部署）否决：A 站 git 协议不可达 + 无快速回滚
- 方案 C（官方预编译包）否决：通用 avx2 构建无多变体 CPU dispatch，失去构建追溯
- LM Studio 后端借用否决：无 libggml-rpc.so / 无 --rpc 参数（实测）

## 3. 遇到的问题（按 ADR-0009 精神记录的发现）

### 发现 1（环境层）：Windows ssh.exe 丢弃嵌套双引号
- **现象**: `bash -c "echo X"` 在远端变成 `bash -c echo X`（X 成 $0）；`printf "echo Y\n"` 只写入 "echo"
- **影响**: 所有经 PowerShell→ssh 的嵌套双引号命令不可靠
- **处置**: 统一改用"脚本 scp 到远端执行"模式；已写入本会话操作习惯
- **状态**: 环境约束，绕过

### 发现 2（工具层）：llama.cpp `--version` 输出到 stderr
- **现象**: `--version 2>/dev/null` 返回空；`2>&1` 才有输出
- **影响**: step0 初版版本检查误判"版本不匹配"
- **处置**: 全部改为 `2>&1`
- **状态**: 已修复

### 发现 3（shell 语义）：`set -euo pipefail` 下 glob 失败的连环杀
- **现象**: `ls "$HOME"/.../rpc_*.log`（引号内 glob 无匹配）→ ls 退出 2 → pipefail → set -e 杀脚本；同理 grep 无匹配退出 1
- **影响**: gen_manifest.sh 在 B 站（无 rpc 日志）静默死亡，A 站（有日志）正常——同一脚本两站不同结果，极具迷惑性
- **处置**: `|| true` 容错 + 显式判空
- **状态**: 已修复；这是"脚本在数据环境差异下静默失败"的典型案例

### 发现 4（基础设施）：B→A / B→B SSH 免密缺失
- **现象**: 巡检首跑 B 站 ssh A 站 Permission denied
- **根因**: 此前调研只验证了 B→A 的 ping/nc 端口连通，未验证 SSH 层
- **处置**: B 站生成 ed25519 密钥 → 主控站中转安装到 A 站 authorized_keys → B 站本机回环也补装
- **状态**: 已修复；**教训: "链路验证"必须验证到目标协议层，端口通 ≠ 应用通**

### 发现 5（设计偏差）：C5 降级语义
- 设计意图 "MANIFEST 缺失 → 警告"，实现为 "缺失 → NO_MANIFEST 指纹 → 判不一致 exit 1"
- 更严格（安全方向），按 P2 接受并记录，后续可加 --warn-only

## 4. 下一步

1. **升级 v0.2.0+**（按 UPGRADE_SOP.md 执行，独立 feature）— 收益：MTP 投机解码 / Vulkan KV 优化 / RPC 多线程加载（提速报告 Tier 1.1）
2. 升级前先跑 llama-bench 固化 9859 基线（提速报告第七节第 1 步）
3. 建议第二会话（异构基座）对本 feature 复审（RULE-4/5）
4. C5 的 --warn-only 模式（低优先级）

## 5. 产物索引

| 产物 | 位置 |
|------|------|
| spec 四文档 + SOP | D:\RPC\spec\vulkan-version-control\ |
| 脚本 ×5 | D:\RPC\scripts\ |
| 巡检用法 | `bash /tmp/check_llama_version.sh [--deep]`（B 站）或主控站 Git Bash |
| 上游调研 | D:\RPC\提速调研报告.md v1.1 §五/§六 |
