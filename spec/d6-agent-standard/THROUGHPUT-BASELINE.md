# model-flavor 吞吐基准表（O-25 P0-①）

> 状态: 🔵 基线版（2026-09-12）——复用 BLINDSCAN / 手册 / 项目实证数据入库，缺失档标注「待实测」。
> 用途: O-25 L0「派发前预估」数据源——派发时按任务卡 `complexity`+`max_output` 反推 ≈ token/t/s → 预估秒数；预算拆 prefill+decode 两相。
> 数据原则: **本地实测 > 外部案例**（铁律）。所有数字必须可回溯（实测日期+方法+日志路径）。缺失=nil，禁止编造。

## 1. 现役模型档吞吐矩阵

decode / prefill 单位 = t/s（token per second）。`-c`=引擎上下文；KV=量化精度。模型档 id 对齐 `infer-load` / `cluster.py` 别名（`spec/d2-cluster-cli`）。

| 模型档 id | 基座/规模 | 量化档 | 后端 | 部署形态 | KV | 运行站 | prefill t/s | decode t/s | 上下文敏感性 | 实测日期 | 方法/日志 | 数据来源 |
|---------|---------|-------|-----|--------|----|------|-----------|-----------|-----------|---------|---------|---------|
| `gpt-oss-120b` | gpt-oss 120B | MXFP4 | HIP(unsloth b10715) | 单站 | q8_0 | A | **112–138** | **49–53** | 低 | 2026-09-08 | unsloth studio run；载 45s | 手册 §8 实测定案 |
| `gpt-oss-120b` | gpt-oss 120B | MXFP4 | HIP(unsloth) | 单站 | q8_0 | C | **152** | **48.8** | 低 | 2026-09-08 | BIOS UMA FB=4G 后 | 手册 §8 实测定案 |
| `nemotron-120B` | Nemotron 120B | — | HIP vs Vulkan | 单站 | — | A | — | **HIP 20.5 / Vulkan 23.2** | 中 | 2026-09-08 | 同条件后端对比 | 手册实测定案 |
| `MiniMax-M2.7` | MiniMax M2.7 121G | UD-IQ4_XS | Vulkan(ROCm0) | 单机 | q4_0 | C | — | **21.5**（decode）/**22.1**（含 prompt） | 高（短题峰值 23-25，长 CoT 压 20-21） | 2026-09-11 | 用户测试题 16 题实跑（tmp/res_m27；117936 tok / 5490s） | 实测（用户测试题批量） |
| `deepseek-v4-flash-0731` | DeepSeek V4 Flash 146G | Q4(UD-Q4_XL) | Vulkan/RPC | **三站 RPC 分布式** | — | A+B+C | — | **~7.9** | 中 | 2026-09-01 | RPC 层分布；长 prompt 分片有劣化@Qwen | 手册实测定案 |
| `qwen3.8-flash-next` | Qwen3.8-Flash-Next 125B MoE | UD-IQ4_XS+ | Vulkan(C 站) | 单站 | f16 | C | — | 短 ctx **19–20**；>1K ctx **5.5–6.1** | **高（长 ctx 塌缩）** | HIP 实测 | HIP MoE bug→弃 HIP；Vulkan 待复测 | 手册 §8 / llama.cpp#27856 |

## 2. 缺失档（待实测补齐）

O-25 关闭判据①=「至少覆盖现役各模型档」。以下为现役但**数字待实测/待补**：

| 模型档 id | 缺项 | 补齐方法（llama-bench 模板） |
|---------|------|-------------------------|
| `gpt-oss-120b` Vulkan 单站 | decode/prefill 直测 | `llama-bench -m <gpt-oss-MMLU.gguf> -ngl 999 -t 16 -b 512 -fa on -p 512 -n 128 -r 2` |
| `nemotron-120B` Vulkan/HIP | prefill | 同上模板换模型 |
| `MiniMax-M2.7` 单机 Vulkan | pp/tg 分离基准（用户测试题为混合长 CoT 口径，非纯 tg128） | `llama-bench -m MiniMax-M2.7-Q4_K_S.gguf -t 16 -b 512 -fa on -p 512 -n 128`；已有用户测试题批量 22.1 t/s 作间接锚 |
| `deepseek-v4-flash-0731` | prefill | RPC 三站 `--rpc ... --n-cpu-moe 8 -p 512` |
| `qwen3.8-flash-next` Vulkan | decode 直测（HIP 数据仅为弃用参照） | C 站 Vulkan 短+长 ctx 各跑一档 |

## 3. 派生口径

- **agent budget 预估（O-25 L1 输入）**: `预估秒数 = prefill_sec + decode_sec`，其中
  - `prefill_sec ≈ min(ctx,_max_output) × min(_pp)` — prefill 读 prompt+l0 长上下文；长 ctx 档取低值（Qwen3.8/ M2.7 长 ctx 塌缩）
  - `decode_sec ≈ max_output / decode_tps` — 主项（agent 生成 token 为主）
  - 用**档位低值**做保守预估（避免 O-23 式硬超时误杀）,再按 O-25 §关闭判据③「非线性逼近 timeout_s」校准
- **`.progress` bytes_s 关联**: wrapper 产出为 UTF-8 文本字节流，`bytes_s ≈ decode_tps × avg_bytes_per_token`（中文 token ~3 B）。bytes_s 用于 run 中节拍，换算 token 吞吐需回表折 token 单位。

## 4. 维护纪律

- 复制数据入表必须带「实测日期 + 方法 + 日志/文档路径」三要素；只有 source 列非空的行可被 L0 预估信任。
- 每次引擎升级（llama.cpp / RPC 协议 / 内核 / KV 档位变更）后，受影响行**重新实测并更新日期**，防假清单（MANIFEST 同教训）。
- 新模型入库（infer-load 增加档）必须同步补吞吐行，否则 O-25 L0 对该档退化为 wall-clock 兜底。