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