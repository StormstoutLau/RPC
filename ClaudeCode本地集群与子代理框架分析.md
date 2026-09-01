# Claude Code CLI × 本地集群 × opencode 子代理框架分析

> 日期: 2026-09-01 19:35 · 作者: Scott (鹏)
> 数据基础: 本轮 B 站 claudecode 安装 + 全链路实验实锤 (非纸面推演)
> 关联: [双端点部署与opencode混合框架调研.md](双端点部署与opencode混合框架调研.md) · [SSH_OPENCODE_SETUP.md](SSH_OPENCODE_SETUP.md)
> 状态: **阶段 2 已验证 GO** (2026-09-01 20:18): claudecode+nemotron 真实编码任务 PASS (stats.cpp 写码→编译→测试闭环, 输出精确匹配, exit=0) — tool-use 经 litellm 转换层兼容性实锤; 阶段 3 的 A 站 gpt-oss 端点与 opencode 双 provider 亦已部署验证

---

## 摘要 (结论先行)

1. **B 站 claudecode 已装好** (2.1.252, npm/nvm node22 全局; A 站原有 2.1.220) — 两站 CLI 就位
2. **claudecode 接本地模型全链路实验成功**: `claude -p --model nemotron` 经 LiteLLM (anthropic `/v1/messages` 格式转换) → llama.cpp → nemotron 返回 `PONG`, exit=0 — **"本地 120B 模型依托 claudecode"主张实锤, 关键环节是 litellm 的 anthropic 协议转换层**
3. **子代理集群架构可行但有结构性约束**: claudecode 原生 SubAgent 机制**只能用 Anthropic 系模型**; 要指挥 opencode 免费模型, 正确形态是 **claudecode 作任务拆解规划层 (主站), opencode 作异构执行层 (子站)** — 借道 shell 而非原生 agent 协议
4. **比裸 API 高效的边界**: 对**工程实现类任务** (需 编译/测试/迭代修复) 提效显著 (旧档数据: 裸 LLM 调用 4 模型测试通过率仅 61.5-85.7%, agent 自修复闭环补齐); 对**纯推理/生成任务** (一次性问答) 提效为零甚至为负 (agent 外壳增加 token 开销与延迟)

---

## 一、本轮实验记录

### 1.1 claudecode 安装状态

| 站 | 版本 | 安装方式 | 状态 |
|---|---|---|---|
| A | 2.1.220 | nvm node v24.15.0 npm 全局 | 原有 (用户装) |
| B | **2.1.252** | nvm node v22.23.2 npm 全局 (本轮装) | ✅ 新装, PATH 已入 .bashrc |

安装: `npm install -g @anthropic-ai/claude-code` (4s, 无网络障碍 — npm registry 可直连, 与 github.com 直连不可达不同)。

### 1.2 关键实验: claudecode → litellm → 本地 nemotron

**链路**: `claude -p --model nemotron` → `ANTHROPIC_BASE_URL=http://127.0.0.1:4000` → litellm **`/v1/messages` (anthropic 格式)** → 转换为 OpenAI 格式 → llama.cpp :8080 → nemotron

**结果**:
- litellm `/v1/messages` 端点: 返回标准 anthropic 响应结构 (`content:[{type:"text",text:"PONG"}]`, usage, stop_reason) — **协议转换层存在且工作**
- claudecode headless (`claude -p`): **PONG, exit=0** — 完整跑通

**关键环境变量组合** (B 站实测):
```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:4000"   # 指向 litellm 而非 api.anthropic.com
export ANTHROPIC_AUTH_TOKEN="<litellm master key>"  # litellm key 冒充 anthropic key
export CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT=1  # 可选: 消除非识别模型警告
claude -p "..." --model nemotron
```

**排错记录** (首轮假阴性): 首次测试输出空 → 以为是 claudecode 兼容问题 → 定位发现是上一脚本的 infer-unload 已把模型卸掉 (8080 空转), **"链路断"与"模型未加载"症状相同** — 排查 litellm 报错必须先确认后端有模型 (curl :8080/health)。

**注意事项**:
- claudecode 对非 Anthropic 模型名仅警告不拒绝 ("unrecognized model" 不阻塞执行)
- 双格式端点并存: litellm 同时暴露 `/v1/chat/completions` (OpenAI, opencode 用) 和 `/v1/messages` (anthropic, claudecode 用) — **一个网关同时服务两种 agent CLI, 这是本架构的关键粘合层**
- claudecode 的系统提示词/工具调用是 Anthropic 格式, 经转换层给本地模型 — 复杂 tool-use 场景质量待验证 (本轮只测了纯文本对话)

### 1.3 与 opencode 实验对照 (上轮)

| 维度 | opencode | claudecode |
|---|---|---|
| 接本地模型路径 | OpenAI 兼容 provider (config jsonc) | ANTHROPIC_BASE_URL + AUTH_TOKEN 环境变量 |
| 转换层 | 不需要 (llama.cpp 原生 OpenAI 格式) | 需要 litellm /v1/messages anthropic 转换 |
| 免云依赖 | ✅ (本地 provider 完全离线) | ✅ (BASE_URL 重定向后不连 anthropic) |
| headless | ✅ | ✅ (`claude -p`) |
| 免费云模型 | Zen 系列 (需代理+PTY) | ❌ 无免费层 (必须订阅/API key; 本地重定向后无云依赖) |

---

## 二、子代理集群架构分析

### 2.1 用户设想的架构

```
主站点 (任务拆解/规划)
   │
   ├── claudecode (B 站) ←── 本地 nemotron 120B (1M ctx 主力)
   ├── claudecode (A 站) ←── 本地 gpt-oss 120B (待部署, 50+ t/s)
   │
   └── 子代理层: opencode 免费模型 (Zen 云, 经 A 站 mihomo)
```

### 2.2 结构性约束 (关键发现)

**claudecode 的原生 SubAgent 机制 (`~/.claude/agents/` 自定义 agent / Task 工具) 在设计上只与 Anthropic 模型生态深度耦合** — 模型名硬编码到 anthropic 系、工具调用格式为 Anthropic 专利 schema。给 claudecode 配 nemotron 后:
- ✅ 文本对话、文件操作、shell 执行可用 (经 litellm 转换)
- ⚠️ 原生 SubAgent (Task 工具派生 subagent) 行为不可预期 — 子 agent 同样走 ANTHROPIC_BASE_URL, 即同样用本地模型 (可行但无 Anthropic 质量)
- ❌ 不能直接把 opencode Zen 免费模型挂成 claudecode 的原生 subagent (协议不通)

**因此正确的混合架构是"shell 编排"而非"agent 协议"**:

```
主控站 (规划者角色: 人工或 claudecode)
   │ ssh -t
   ├── A 站: claudecode --model gpt-oss (本地)     ← 工程执行/编程
   ├── B 站: claudecode --model nemotron (本地)    ← 长上下文分析/审查
   └── A 站: opencode -m opencode/*-free (Zen 云)  ← 异构第三意见/免费容量
        ▲
        └── 三者互为子代理: 由主控站脚本 (或 B 站 claudecode 的 Bash 工具
            跨站 ssh 调用另两者) 编排 — "子代理"发生在 shell 层
```

### 2.3 编排形态选择

| 形态 | 实现 | 复杂度 | 适用 |
|---|---|---|---|
| **A. 主控站脚本编排** (推荐起步) | 主控站 PowerShell/Python 脚本按任务类型分发到三端点, 汇总结果 | 低 (~100 行) | 互验/投票/并行任务 |
| **B. claudecode 作总编排** | B 站 claudecode 在会话中用 Bash 工具 `ssh A站 'claude -p ...'` / `ssh A站 'opencode run ...'` 拉起子代理 | 中 (需 prompt 工程: 教会它用 ssh 编排) | 任务拆解自动化 — 用户"主站点做任务拆解"设想的实现 |
| C. opencode 互相调用 | 同理可让 opencode 作编排者 | 中 | 无明显增益, 不推荐双编排者 |

**形态 B 的诚实评估**: claudecode 拿本地 nemotron 做总编排时, 其"拆解质量"受限于 nemotron 的指令跟随能力 (B6 评测: 概念题良好, 无 GPT/Claude 级规划力)。**更强的做法是主控站的 TRAE/Claude (云端强模型) 做拆解, 两站 CLI 只做执行** — 用户已有此习惯 (本会话工作模式)。

### 2.4 比裸 API 高效吗? (分场景诚实评估)

| 任务类型 | 裸 API (call_llm.py 模式) | agent CLI (claudecode/opencode) | 判定 |
|---|---|---|---|
| 一次性问答/推理 | 直接生成, 最快路径 | agent 外壳加系统提示+工具 schema 开销 (~2-4k token), 更慢 | **裸 API 胜** |
| 代码需编译测试迭代 | 生成后人工看错→改 prompt→重生成 (旧档: 4 模型通过率 61.5-85.7%, 需多轮) | agent 读编译错误自修复, 一次任务多轮内部迭代 | **agent 胜 (本质增益)** |
| 长文档分析 | 单次调用即可 (nemotron 96.5k needle 5/5) | 同质量, 但 agent 可分块+工具辅助 | 持平 (agent 略慢) |
| 多模型互验 | 自写 orchestrator (需开发) | 框架内 shell 编排 | agent 略胜 (省开发) |

**结论**: "更高效"成立于 **agent 闭环价值** (编译-测试-修复迭代) 与 **本地模型零成本无限速** (对比 API 按量计费); 不成立于纯生成速度 (外壳有开销)。B6 评测已证本地模型质量 5/5, 与免费云模型互验架构上是 **成本 ($0) + 隐私 (全本地) + 异构 (三血统)** 的组合优势。

### 2.5 风险与未知

| 风险 | 评估 |
|---|---|
| claudecode 复杂 tool-use (Edit/Bash 工具链) 经转换层给本地模型, 格式兼容性只测了文本对话 | **本轮未验证** — 需实测一个真实编码任务 (阶段 2 门) |
| claudecode 系统提示词为 Claude 调优 (数千 token), 本地模型跟随质量未知 | 中风险 — nemotron B6 概念题良好但非 GPT 级指令跟随 |
| claudecode 对话历史/会话机制在 BASE_URL 重定向下是否完整 | 低 (会话本地存储, 与 API 端点无关) |
| Zen 免费模型可用性/限速 | 旧档已知风险, 不进关键路径 |
| 两站 claude 版本差异 (2.1.220/2.1.252) | 低 — 建议统一 |

---

## 三、实施清单 (三阶段)

### 阶段 1: 已完成 (本轮)
- ✅ B 站 claudecode 2.1.252 安装
- ✅ claudecode → litellm (/v1/messages) → nemotron 全链路实验

### 阶段 2: 真实任务验证 (~30min, 决定 go/no-go)
1. claudecode (本地 nemotron) 执行一个真实编码任务 (如: 写 C++ 单文件程序+编译+测试), 验证 tool-use 经转换层的兼容性
2. 同任务用 opencode (本地) 跑, 对照
3. 同任务用 opencode Zen 免费模型 (A 站, 经代理) 跑, 三方对照

### 阶段 3: 子代理集群成型 (依赖双端点部署, 报告见双端点调研)
4. A 站 gpt-oss 部署 (双端点调研阶段 1)
5. A 站 claudecode 配置 (ANTHROPIC_BASE_URL 指向本站端点)
6. 编排脚本 (主控站 ~100 行: 任务分发/结果汇总/分歧标记)
7. 手册 + memory + git commit

---

## 附录: 本轮实验数据

- B 站 claude 安装: /tmp/cci.sh 输出 (2.1.252, 4s)
- litellm /v1/messages 响应: /tmp/cct2_run.out (标准 anthropic 结构, PONG)
- claude headless: 同文件 (PONG, exit=0, unrecognized_model 警告不阻塞)
- 对照 opencode 实验: 上轮 /tmp/oclt_run.out
