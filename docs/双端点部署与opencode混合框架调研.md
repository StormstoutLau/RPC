# A 站双端点部署与 opencode 混合框架调研报告（三机群形态更新版）

> 日期: 2026-09-01 19:15 · 作者: Scott (鹏) · **三机群更新 2026-09-10**
> 数据基础: 当日全库存 B6 评测 + nemotron 专项实测 + 本轮 opencode 活体验证
> 关联: [三机推理集群使用手册.md](三机推理集群使用手册.md) · [SSH_OPENCODE_SETUP.md](SSH_OPENCODE_SETUP.md) · [spec/model-eval/results-ledger.md](../spec/model-eval/results-ledger.md)
> 状态: **阶段 1+2 已执行完毕** (2026-09-01 20:30): gpt-oss 63G 已 rsync 至 A 站 (sha256 双端一致), A 站 llama-server@gpt-oss-120b 单机端点 READY, LiteLLM gpt-oss 路由改指 10.10.10.1:8080, 双路由 E2E 全通 (nemotron 单机 20.9 t/s / gpt-oss 58 t/s); A 站 opencode 双 provider (本机 + 跨站网关) PONG 验证通过

> **三机形态续记 (2026-09-09/10)**: 本文为 9/1 双端点决策史档，2026-09-10 按三机群状态完成正文更新。C 站 (seaviv, 192.168.1.37) 已于 2026-09-08/09 作为**第三独立端点**接入: UMA=4G 档 HIP 全通 (gpt-oss-120b decode 48.8 t/s), 常驻 nemotron-120B 手动引擎 :8080, opencode 1.18.25 + claude 2.1.258 双 CLI 直连 127.0.0.1:8080, infer-* 工具链/load-gate 三件套已补装 (与 A/B 同构)。**"80G 级模型=独立端点而非 RPC" 的论证结论对第三站同样成立**（原文 §1.2 RPC 税证据链、§1.3 推荐形态、§2 opencode headless 铁律均为三机形态的直接先例）。下文各节已按三机群实况标注。详见 [三机推理集群使用手册.md](三机推理集群使用手册.md) v1.8。

---

## 摘要 (结论先行, 三机群形态)

1. **双端点完全可行, 三机群扩展为"三独立端点"** — 80G 级模型改变了架构最优解: RPC 对 nemotron 是 -17% decode 税而非必需; 推荐形态 B=nemotron (主力) + A=gpt-oss (速度档) + **C=第三独立端点 (常驻 nemotron, 可换 gpt-oss)**, 三站各自独立 :8080 端点
2. **opencode 可作为三站本地模型的 agent 外壳** — 9/1 活体实验 (B 站 headless PONG) 已推广至三站: A/B/C 均装 opencode 1.18.25 + cluster-litellm provider, C 站直连 127.0.0.1:8080 (2026-09-09 验证 `OPENCODE-NEM-OK`)
3. **opencode 内置免费云模型构成独立一极** — 经 A 站 mihomo 代理可达, 与三站本地模型形成 **四层混合框架**: A 本地 / B 本地 / **C 本地** / 云端免费
4. **1+1>2 的真实来源是异构互验 + agent 能力** — 三站三血统 (nemotron mamba-hybrid / gpt-oss MoE / C 站同型补充视角) + agent "生成→编译→测试→修复"闭环, 跨站交叉 review; C 站加入扩大互验矩阵与故障容错面

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

### 1.3 推荐部署形态（三机群版）

| 站 | 模型 | 占用 | 角色与理由 |
|---|---|---|---|
| B | nemotron 80G | ~86G | **主力**: 1M ctx 长上下文; 网关 litellm 本机零跳; 兼容老 CPU 密集负载 |
| A | gpt-oss 59G | ~65G | **速度档**: decode 50+ t/s 冠军 (MoE 5.1B 激活); opencode 编程主力 |
| C | nemotron 80G (Q4_K_M) / 可换 gpt-oss 59G | ~83G / ~65G | **第三独立端点 (2026-09-09 接入)**: 常驻 nemotron 手动引擎; HIP 后端 gpt-oss decode 48.8 t/s; opencode/claude 直连 127.0.0.1:8080 |

分派理由 (两机版理由 A/B 沿用在三机): ① 网关在 B, 主力本机回环最快; ② A 是有挂死史的站 (已关案 90% 置信), 59G 负载更温和; ③ A/B 任一故障时其余站可自持 (C 加入后容错面更宽); ④ 模型架构异构 (mamba-hybrid vs transformer MoE) — 互验资产; C 站为 ODM 公板 + UMA 4G 档, 硬件层面与 A/B 差异 (carveout 档位) 已通过定案配置消除。

附带收益: LiteLLM 路由从"两名皆指 B:8080 靠 GTT 互斥语义"变为**模型名=实际模型** (`nemotron`→B 回环, `gpt-oss`→A 经 10.10.10.1 静态 IP, 免 DHCP 漂移)。**C 站不经 LiteLLM**: 直连 `192.168.1.37:8080` (或本机 127.0.0.1:8080), 三站并行无 GTT 互斥 (C 站与 A/B 无共站互斥关系)。

### 1.4 风险与缓解

| 风险 | 评估 | 缓解 |
|---|---|---|
| A 站独立长负载未长期验证 (E1 测的是 RPC 角色) | 低 (挂死根因=cron 已删) | netconsole+watchdog+Beszel 常驻在位; 首周观察 |
| 切 deepseek 会话需卸两端点回 RPC | ~5min/次 | 固化为脚本; A 站 rpccache 78G 保留复用 |
| OOM 三件套只在 B | 缺口 | 部署时同步拷 load-mem-gate / wait-gtt-release 到 A |
| 端点故障无热备 | 丢一路由 (另一路不受影响) | 可接受 (GTT 互斥决定了无热备) |

---

## 二、opencode 混合框架补充分析

### 2.1 三站 opencode 现状盘点（9/1 活体核查 + 9/9 C 站接入后复刻）

| 项 | A 站 | B 站 | C 站 (2026-09-09 接入) |
|---|---|---|---|
| opencode 版本 | **1.18.25** (/snap/bin/) | 1.18.25 (~/.opencode/bin/, 9/1 后已随锁升级对齐) | 1.18.25 (~/.opencode/bin/, 随 B 复制) |
| 自定义 provider 配置 | cluster-litellm (baseURL 指向本机 :8080) | cluster-litellm (baseURL 127.0.0.1:8080) | **cluster-litellm (baseURL 127.0.0.1:8080, C 站本地引擎)** |
| mihomo/代理 | ✅ 在跑, models.dev 经代理可达 (HTTP 200) | ❌ 无 (本地 provider 零外网依赖) | ❌ 无 (同 B 站语义) |
| 免费云模型 (Zen) 可用性 | ✅ (经代理 + PTY/keyring) | ❌ (无代理) | ❌ (无代理) |
| 插件 (codex-memory + DCP) | ✅ (2026-09-02) | ✅ | ✅ (2026-09-09 随 B→C 复刻) |
| 模型端点 | gpt-oss :8080 | nemotron :8080 | nemotron 常驻 :8080 / gpt-oss 可换 |

> 三站版本已统一 1.18.25（9/1 时 B 站 1.18.9 → 后续锁定升级对齐）；C 站 opencode 由 B 站用户级安装复制（绕开 npm 404），插件面与窗口预算随复刻一致（gpt-oss limit 120000 / nemotron 131072）。

### 2.2 关键实验: opencode headless 接本地集群 (本轮实锤)

**实验设计**: B 站 opencode 无 `-t` (不分配 PTY)、不设代理、无 keyring — 直接 `opencode run -m cluster-litellm/nemotron`。

**结果**: `PONG`, exit=0, 全链路 load-mem-gate → infer-load → opencode → litellm :4000 → llama.cpp :8080 → nemotron 生成。

**结论 (推翻旧档部分结论)**:
- 旧档 (SSH_OPENCODE_SETUP.md §3) 的 PTY 依赖**仅适用于 Zen 云模型** (keyring 认证需要 PTY 会话); 本地 OpenAI-compatible provider 完全免 PTY/keyring
- opencode 启动时 models.dev 拉取失败**不阻塞**自定义 provider (内嵌模型定义直接可用, 无需外网)
- B 站无代理不再是障碍 — 本地 provider 路径零外网依赖
- **三站推广 (2026-09-09)**: A/B/C 三站 headless 均验证通过 — C 站 opencode `cluster-litellm/nemotron` → `OPENCODE-NEM-OK`；C 站 claude (settings.json 指向 127.0.0.1:8080) → `end_turn` ✅。**本铁律为 D6 agent-cli headless 调用的直接依据**（见三机手册 §2a.4）。

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

A 站同款配置只需把 baseURL 换成本机端点 (双端点部署后 A 站 :8080 或经 USB4 的 litellm `http://10.10.10.2:4000/v1`)。**C 站同款配置**: baseURL 直接 `http://127.0.0.1:8080/v1` (C 站独立引擎, 不经 litellm), 9/9 已写入 C 站 `opencode.jsonc` 并验证 `INJECT_OK`。

### 2.3 三层混合框架设计（三机群版: 四极）

```
                        主控站 (Win10)
                       /      |        \      \
                  ssh -t    ssh -t    ssh     HTTP
                    /        |         \        \
            ┌──────┴──┐ ┌────┴─────┐ ┌──┴─────┐ ┌────┴────────┐
            │ A 站     │ │ B 站     │ │ C 站    │ │ 主控站直调    │
            │ opencode │ │ opencode │ │ opencode│ │ (脚本/API)   │
            │ 1.18.25  │ │ 1.18.25  │ │ 1.18.25 │ │             │
            └──┬───┬───┘ └──┬───┬───┘ └──┬──┬──┘ └──────┬──────┘
      层①     │   │层④      │   │        │  │           │
   本地 gpt-oss│  Zen免费模型 │  本地 nemotron │ 本地 nemotron
      :8080  │  (经mihomo)  │   :8080/:4000 │ (常驻)/gpt-oss
              │             │                │ (2026-09-09)
        (现役)         (A站专属)      (B站现役主力)   (C站现役)
```

| 层 | 位置 | 模型 | 认证 | 依赖 |
|---|---|---|---|---|
| ① 本地 gpt-oss | A 站 :8080 | 59G MXFP4, decode 50+ t/s | 无 | ✅ **现役** (双端点部署已生效) |
| ② 本地 nemotron | B 站 :8080 → litellm :4000 | 80G, 1M ctx, 96.5k needle 5/5 | litellm key (已配) | ✅ **现役主力** |
| ③ **C 站本地** (2026-09-09) | C 站 `192.168.1.37:8080` (或本机 127.0.0.1:8080) | 常驻 nemotron Q4_K_M (~83G) / 可换 gpt-oss | 无 (直连) | ✅ **现役** — 第三独立端点, 不经 litellm |
| ④ Zen 免费云模型 | opencode.ai | deepseek-v4-flash-free / nemotron-3-ultra-free / big-pickle 等 | keyring + PTY + 代理 | 仅 A 站可用 (有 mihomo) |

**层④与本地层的家族关系 (互验价值分析)** (同原三层):

| Zen 免费模型 | 本地对应 | 关系 |
|---|---|---|
| nemotron-3-ultra-free | 本地 nemotron-3-super | **同家族更高档** (Ultra > Super) — 可作本地 Super 的"升级参照" |
| deepseek-v4-flash-free | 本地 deepseek-v4-flash | 同款 — 无互验价值, 但本地版无限速/免费 |
| big-pickle / laguna / mimo | 无 | 独立血统 — 第三意见 |

### 2.4 1+1+1>3 在 opencode 层的实现形态 (价值排序)

**① 异构交叉 review (最高价值, 推荐首选; 三机矩阵扩大)**
- A 站 agent (gpt-oss 或 Zen) 写代码 → B 站 agent (nemotron) review; 反向亦然; C 站 (nemotron 同血统, 但 ODM 公板/独立端点) 作为第三 reviewer 与故障时候补
- 机理: mamba-hybrid / transformer-MoE / 云端模型三血统错误不相关 — Research OS 验证方法论 (judge ≠ 被测模型) 的运行时实例化; C 站加入后同血统双穿透 (A·C 可对 B 同族出交叉意见)
- opencode 使其可执行: agent 能真跑代码/编译/测试, review 基于运行证据而非纸面

**② 生成-验证流水 (agent 闭环价值)**
- 旧 call_llm.py 路线: 一次性生成, 4 模型测试通过率仅 61.5-85.7% (旧档 §1.3)
- opencode 路线: agent 读编译错误自修复, 创建→编译→运行→验证一体 — **这是"外壳"的本质增益, 与模型无关**

**③ 多极投票 (准确性增益, 需开温度)**
- 同题发层①②③④ 各自作答, 多数决; temp=0 时同模型双实例零增益 (输出逐位相同), 必须开温度
- 层④免费云模型让"第三意见"零硬件成本 — 但有可用性/限速风险, 不宜进关键路径
- **三机优势**: 原先双机"1+1>2"依赖 A·B 两血统; 加 C 后 A/B/C 三站可同时并行两任务互验, 且 C 站常驻 nemotron 与 B 同模型 — "同模型跨站复跑"可作**采信度判据**(异站同模型输出一致 → 高置信), 无需另开 temp 或多模型成本

**明确不可行的期待**: 跨机投机解码 (draft/verify 须同进程 KV); PD 分离 (llama.cpp 无此能力)。

### 2.5 约束与风险 (承旧档 + 本轮修正)

| 项 | 旧档结论 | 本轮修正/确认 |
|---|---|---|
| PTY 依赖 | "必须 ssh -t" | **仅 Zen 云模型**; 本地 provider 免 PTY (本轮实锤) |
| models.dev 拉取 | 被墙致超时 | 本地 provider 不依赖; A 站经代理 200 可达 |
| 代理 | A 有 B 无 | 确认现状不变 (C 同 B); 层④限 A 站 |
| `--auto` 安全 | agent 可任意 shell (含 rm -rf) | 维持: /tmp 隔离目录 + timeout + 不放敏感文件 |
| 版本碎片 | A 1.18.8 / B 1.18.9 | **已统一三站 1.18.25** (2026-09-09 C 站随 B 复制) |
| key 内嵌 | — | opencode.jsonc 含 litellm key (B 站本地文件, 不入 git); 注意 ~/.config/opencode 权限; C 站 key 为 placeholder (直连本地不经 litellm) |
| 引擎管理 | systemd llama-server 单元 | A/B 沿用; **C 站常驻引擎为手动进程** — 已补装 infer-* 工具链 + load-gate (OOM 三件套) 对齐管理 (2026-09-09) |

---

## 三、实施清单（三机群状态回填）

### 阶段 1: 双端点部署 ✅ **已完成** (2026-09-01)
1. ✅ A 站基础: load-mem-gate / wait-gtt-release 已拷 + /data/models/gguf 已建
2. ✅ rsync gpt-oss 59G B→A (sha256 双端校验)
3. ✅ A 站 llama-server@gpt-oss 单元 (单机不接 RPC) → A :8080 现役
4. ✅ LiteLLM gpt-oss → 10.10.10.1:8080 + 双端点 E2E 全通
5. ✅ 手册 §2.2 / project_memory / git commit

### 阶段 2: 三站 opencode 配置 ✅ **已完成** (2026-09-01 双站 + 2026-09-09 C 站)
6. ✅ A 站 cluster provider (baseURL 本机 :8080 gpt-oss)
7. ✅ B 站就绪 (9/1) → 版本统一 1.18.25 (三站)
8. ✅ A 站 Zen 免费模型可经代理 + PTY 使用; C 站直连本地 (OPENCODE-NEM-OK 9/9)

### 阶段 3: 互验工作流（三机矩阵, 进行中）
9. ⏳ 主控站 orchestrator 脚本扩展: 同题并行发三端点/四极 → 交叉判分 → 分歧标记 (可复用 agent-cli 跨站扇出 `_bs2_fanout.py` / `_bs2_cross.py` 先例)
10. ✅ opencode 工作流已固化为手册章节 (§2a.4 headless 铁律 + agent-cli-smoke 4 CLI 冒烟)

---

## 附录: 数据来源

- 单机 vs RPC 对照: spec/model-eval/results-ledger.md (2026-09-01 17:40 补充节)
- gpt-oss tg 50-54 t/s + ngram 投机负收益: 同账本 (18:00 节)
- nemotron 架构/KV/needle: 同账本 (16:00-17:10 节)
- opencode 旧档: SSH_OPENCODE_SETUP.md (2026-07-30)
- 本轮 opencode 活体验证: B 站 /tmp/oclt_run.out (headless PONG, 2026-09-01 19:00)
- **C 站接入数据 (三机群更新)**: [DEV-LOG-011 §8 C 站接入](DEV-LOG-011-d6-agent-standard.md) (2026-09-09) + [C站硬件身份与BIOS更新源分析](C站硬件身份与BIOS更新源分析_20260908.md) (UMA=4G 定案) + C 站实测 (2026-09-09/10: 常驻 nemotron :8080 / `cluster.py status` 三站 READY / load-gate 三件套已装)
