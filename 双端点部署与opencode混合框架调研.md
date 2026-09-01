# A 站双端点部署与 opencode 混合框架调研报告

> 日期: 2026-09-01 19:15 · 作者: Scott (鹏)
> 数据基础: 当日全库存 B6 评测 + nemotron 专项实测 + 本轮 opencode 活体验证
> 关联: [双机推理集群使用手册.md](双机推理集群使用手册.md) · [SSH_OPENCODE_SETUP.md](SSH_OPENCODE_SETUP.md) · [spec/model-eval/results-ledger.md](spec/model-eval/results-ledger.md)
> 状态: 可行性已实锤; 部署待用户裁决

---

## 摘要 (结论先行)

1. **A 站双端点完全可行** — 80G 级模型改变了架构最优解: RPC 对 nemotron 是 -17% decode 税而非必需; 推荐形态 B=nemotron (主力) + A=gpt-oss (速度档), 两站各自独立 :8080 端点
2. **opencode 可直接作为两站本地模型的 agent 外壳** — 本轮活体实验实锤: B 站 opencode headless (无 PTY/无代理/无 keyring) 经 LiteLLM 路由调用本地 nemotron 成功 (`PONG`, exit=0); 配置即插即用, 已留在 B 站
3. **opencode 内置免费云模型构成第三极** — 经 A 站 mihomo 代理可达 (本轮验证 models.dev via proxy = 200), 与两站本地模型形成 **三层混合框架**: A 本地 / B 本地 / 云端免费
4. **1+1>2 的真实来源是异构互验 + agent 能力**, 不是并行算力堆叠 — opencode 层让"生成→编译→测试→修复"闭环在每站本地完成, 跨站做交叉 review

---

## 一、A 站双端点部署可行性

### 1.1 资源核算 (全部当日实测)

| 维度 | 数值 | 判定 |
|---|---|---|
| A 站 GTT 可用 | ~108G | ✅ |
| nemotron 单站峰值 | 80G 权重 + 1G KV(128k) + buffer ≈ 86G | ✅ 余 22G |
| gpt-oss 单站峰值 | 59G + buffer ≈ 65G | ✅ 余 43G |
| A 站磁盘 | 1.4T 空闲 (22%) | ✅ |
| USB4 拷贝速度 | ~600MB/s (GLM 冷移实测) | gpt-oss 59G ≈ 17min / nemotron 80G ≈ 23min |
| A 站跑 nemotron | 已实测 decode 20.3 t/s, MemAvailable 余 39G | ✅ 同硬件等价 |
| deepseek 145G 上 A 单机 | 超 GTT 墙 | ❌ 仍只能双机 RPC |

### 1.2 RPC 税证据链 (为何弃 RPC 转双端点)

同口径对照实测 (nemotron, 2026-09-01):

| 指标 | 双机 RPC | 单机 | Δ |
|---|---|---|---|
| decode 512 | 17.3 t/s | 20.3 t/s | **+17%** |
| 长生成 2048 | 17.9 t/s | 20.7 t/s | +16% |
| 24k needle prefill | 156 t/s | 159 t/s | 持平 |
| 加载 | 165s | 120s | -27% |

机理: decode 逐 token 串行, 每 token ~38.7 次 RPC 跨链命令 (A2 结论); prefill 计算密集跨链占比可忽略。
**m27 时代 RPC 是被迫的 (121G 单机装不下); 80G 模型时代双端点才是最优解。**

### 1.3 推荐部署形态

| 站 | 模型 | 占用 | 角色与理由 |
|---|---|---|---|
| B | nemotron 80G | ~86G | **主力**: 1M ctx 长上下文; 网关 litellm 本机零跳; 兼容老 CPU 密集负载 |
| A | gpt-oss 59G | ~65G | **速度档**: decode 50+ t/s 冠军 (MoE 5.1B 激活); opencode 编程主力 |

分派理由: ① 网关在 B, 主力本机回环最快; ② A 是有挂死史的站 (已关案 90% 置信), 59G 负载更温和; ③ A 故障时 B 全功能自持; ④ 两模型架构异构 (mamba-hybrid vs transformer MoE) — 互验资产。

附带收益: LiteLLM 路由从"两名皆指 B:8080 靠 GTT 互斥语义"变为**模型名=实际模型** (`nemotron`→B 回环, `gpt-oss`→A 经 10.10.10.1 静态 IP, 免 DHCP 漂移)。

### 1.4 风险与缓解

| 风险 | 评估 | 缓解 |
|---|---|---|
| A 站独立长负载未长期验证 (E1 测的是 RPC 角色) | 低 (挂死根因=cron 已删) | netconsole+watchdog+Beszel 常驻在位; 首周观察 |
| 切 deepseek 会话需卸两端点回 RPC | ~5min/次 | 固化为脚本; A 站 rpccache 78G 保留复用 |
| OOM 三件套只在 B | 缺口 | 部署时同步拷 load-mem-gate / wait-gtt-release 到 A |
| 端点故障无热备 | 丢一路由 (另一路不受影响) | 可接受 (GTT 互斥决定了无热备) |

---

## 二、opencode 混合框架补充分析

### 2.1 两站 opencode 现状盘点 (本轮活体核查, 2026-09-01 19:00)

| 项 | A 站 | B 站 |
|---|---|---|
| opencode 版本 | **1.18.25** (/snap/bin/, 已升级) | 1.18.9 (~/.opencode/bin/) |
| 自定义 provider 配置 | 有样例 (lm-studio-local → localhost:1234, 现 disabled) | **本轮已写入 cluster-litellm provider** |
| mihomo 代理 | ✅ 在跑, models.dev 经代理可达 (HTTP 200) | ❌ 无 (符合旧档结论) |
| 免费云模型 (Zen) 可用性 | ✅ (经代理 + PTY/keyring) | ❌ (无代理; 但可经 A 端代理或只用本地) |

### 2.2 关键实验: opencode headless 接本地集群 (本轮实锤)

**实验设计**: B 站 opencode 无 `-t` (不分配 PTY)、不设代理、无 keyring — 直接 `opencode run -m cluster-litellm/nemotron`。

**结果**: `PONG`, exit=0, 全链路 load-mem-gate → infer-load → opencode → litellm :4000 → llama.cpp :8080 → nemotron 生成。

**结论 (推翻旧档部分结论)**:
- 旧档 (SSH_OPENCODE_SETUP.md §3) 的 PTY 依赖**仅适用于 Zen 云模型** (keyring 认证需要 PTY 会话); 本地 OpenAI-compatible provider 完全免 PTY/keyring
- opencode 启动时 models.dev 拉取失败**不阻塞**自定义 provider (内嵌模型定义直接可用, 无需外网)
- B 站无代理不再是障碍 — 本地 provider 路径零外网依赖

**B 站配置已留档** (`~/.config/opencode/opencode.jsonc`, provider 名 `cluster-litellm`, 含 litellm key 内嵌):

```jsonc
{
  "provider": {
    "cluster-litellm": {
      "name": "Cluster LiteLLM",
      "npm": "@ai-sdk/openai-compatible",
      "options": { "baseURL": "http://127.0.0.1:4000/v1", "apiKey": "<litellm master key>" },
      "models": {
        "nemotron": { "name": "Nemotron 3 Super 120B (local)" },
        "gpt-oss": { "name": "GPT-OSS 120B (local)" }
      }
    }
  }
}
```

A 站同款配置只需把 baseURL 换成本机端点 (双端点部署后 A 站 :8080 或经 USB4 的 litellm `http://10.10.10.2:4000/v1`)。

### 2.3 三层混合框架设计

```
                        主控站 (Win10)
                       /      |        \
                  ssh -t    ssh -t     HTTP
                    /         |          \
            ┌──────┴──┐ ┌────┴─────┐ ┌────┴────────┐
            │ A 站     │ │ B 站     │ │ 主控站直调    │
            │ opencode │ │ opencode │ │ (脚本/API)   │
            │ 1.18.25  │ │ 1.18.9   │ │             │
            └──┬───┬───┘ └──┬───┬───┘ └──────┬──────┘
      层①     │   │层③      │   │            │
   本地 gpt-oss│  Zen免费模型 │  本地 nemotron │
      :8080  │  (经mihomo)  │   :8080/:4000  │
              │             │                │
        (待部署)         (A站专属)      (B站现役主力)
```

| 层 | 位置 | 模型 | 认证 | 依赖 |
|---|---|---|---|---|
| ① 本地 gpt-oss | A 站 :8080 (待部署) | 59G MXFP4, decode 50+ t/s | 无 | 双端点部署完成后生效 |
| ② 本地 nemotron | B 站 :8080 → litellm :4000 | 80G, 1M ctx, 96.5k needle 5/5 | litellm key (已配) | **已就绪 (本轮验证)** |
| ③ Zen 免费云模型 | opencode.ai | deepseek-v4-flash-free / nemotron-3-ultra-free / big-pickle 等 | keyring + PTY + 代理 | 仅 A 站可用 (有 mihomo) |

**层③与本地层的家族关系 (互验价值分析)**:

| Zen 免费模型 | 本地对应 | 关系 |
|---|---|---|
| nemotron-3-ultra-free | 本地 nemotron-3-super | **同家族更高档** (Ultra > Super) — 可作本地 Super 的"升级参照" |
| deepseek-v4-flash-free | 本地 deepseek-v4-flash | 同款 — 无互验价值, 但本地版无限速/免费 |
| big-pickle / laguna / mimo | 无 | 独立血统 — 第三意见 |

### 2.4 1+1>2 在 opencode 层的实现形态 (价值排序)

**① 异构交叉 review (最高价值, 推荐首选)**
- A 站 agent (gpt-oss 或 Zen) 写代码 → B 站 agent (nemotron) review; 反向亦然
- 机理: mamba-hybrid / transformer-MoE / 云端模型三血统错误不相关 — Research OS 验证方法论 (judge ≠ 被测模型) 的运行时实例化
- opencode 使其可执行: agent 能真跑代码/编译/测试, review 基于运行证据而非纸面

**② 生成-验证流水 (agent 闭环价值)**
- 旧 call_llm.py 路线: 一次性生成, 4 模型测试通过率仅 61.5-85.7% (旧档 §1.3)
- opencode 路线: agent 读编译错误自修复, 创建→编译→运行→验证一体 — **这是"外壳"的本质增益, 与模型无关**

**③ 三层投票 (准确性增益, 需开温度)**
- 同题发层①②③ 各自作答, 多数决; temp=0 时同模型双实例零增益 (输出逐位相同), 必须开温度
- 层③免费云模型让"第三意见"零硬件成本 — 但有可用性/限速风险, 不宜进关键路径

**明确不可行的期待**: 跨机投机解码 (draft/verify 须同进程 KV); PD 分离 (llama.cpp 无此能力)。

### 2.5 约束与风险 (承旧档 + 本轮修正)

| 项 | 旧档结论 | 本轮修正/确认 |
|---|---|---|
| PTY 依赖 | "必须 ssh -t" | **仅 Zen 云模型**; 本地 provider 免 PTY (本轮实锤) |
| models.dev 拉取 | 被墙致超时 | 本地 provider 不依赖; A 站经代理 200 可达 |
| 代理 | A 有 B 无 | 确认现状不变; 层③限 A 站 |
| `--auto` 安全 | agent 可任意 shell (含 rm -rf) | 维持: /tmp 隔离目录 + timeout + 不放敏感文件 |
| 版本碎片 | A 1.18.8 / B 1.18.9 | A 已升 1.18.25, 差异拉大 — 建议统一升级 B 站 |
| key 内嵌 | — | opencode.jsonc 含 litellm key (B 站本地文件, 不入 git); 注意 ~/.config/opencode 权限 |

---

## 三、实施清单

### 阶段 1: 双端点部署 (~40min, 待批准)
1. A 站基础: 拷 load-mem-gate / wait-gtt-release + 建 /data/models/gguf
2. rsync gpt-oss 59G B→A (USB4 ~600MB/s, sha256 双端校验, 复用 glm_cold_move.sh 模板)
3. A 站 systemd llama-server@gpt-oss 单元 (单机, 不接 RPC)
4. LiteLLM 加路由 gpt-oss → http://10.10.10.1:8080/v1 + restart + 双端点 E2E
5. 手册 §2.2 / project_memory / git commit

### 阶段 2: opencode 双站配置 (~10min)
6. A 站 opencode.jsonc 加 cluster provider (baseURL 指向本机 :8080 gpt-oss)
7. B 站已就绪 (本轮完成); 统一两站 opencode 版本 (可选)
8. 验证 A 站 Zen 免费模型仍可用 (经代理 + PTY)

### 阶段 3: 互验工作流 (可选, ~1h)
9. 主控站 orchestrator 脚本 (~50 行): 同题并行发两端点 → 交叉判分 → 分歧标记
10. opencode 工作流固化为手册章节 (ssh -t 模板已有旧档 §4.1)

---

## 附录: 数据来源

- 单机 vs RPC 对照: spec/model-eval/results-ledger.md (2026-09-01 17:40 补充节)
- gpt-oss tg 50-54 t/s + ngram 投机负收益: 同账本 (18:00 节)
- nemotron 架构/KV/needle: 同账本 (16:00-17:10 节)
- opencode 旧档: SSH_OPENCODE_SETUP.md (2026-07-30)
- 本轮 opencode 活体验证: B 站 /tmp/oclt_run.out (headless PONG, 2026-09-01 19:00)
