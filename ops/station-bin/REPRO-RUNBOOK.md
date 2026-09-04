# 卡死 Bug 复现 + 备份/重启预案 Runbook

> **建立日期**: 2026-09-04
> **对象**: B 站（scott-lau-GTR-Pro.local）unsloth 实例（gpt-oss-120b，KV q8_0，端口 8080）
> **目标 bug**: llama.cpp server 在 gfx1151（Strix Halo / Radeon 8060S）上的 **slot-0 多槽并行卡死**（社区 #20906 家族），表现为并发请求一个 slot 挂死、前端超时
> **关联文档**: 手册「双机推理集群使用手册.md」§10.1b；BLINDSCAN-v2 orchestration §BS-4；spec/d6 fuse 的 unsloth-a-station.md §8

***

## 0. 当前状态审计（2026-09-04 复现后）

| 检查项 | 结果 |
| --- | --- |
| 8080 监听 | LISTEN 127.0.0.1:8080 |
| `/v1/models` 健康 | **HTTP_200** |
| 残留 repro 进程 | 无（仅 health 脚本自身） |
| 复现判定 | **未复现 slot-0 卡死**；两并发长 prefill（1500 词）请求均完成，多槽 batching 正常 |
| 实例状态 | 稳定，可继续服务 |

**结论**: 该卡死为概率性/窗口性 bug，非必然触发；当前配置（KV q8_0、`-c32k`）下未见复现，但不能据此判定已免疫。

***

## 1. 备份与重启预案

### 1.1 前置备份（破坏性操作前必做，铁律）

在 `infer-load`/`infer-unload`/`pkill -9 llama-server` 等任何破坏性操作 **前**：

```bash
# 1) 配置与脚本哈希基准备份（主控站）
cp /etc/llama-instances/*.env /tmp/pre-repro-conf/ 2>/dev/null
md5sum /usr/local/bin/infer-load /usr/local/bin/infer-unload \
       ~/.config/opencode/opencode.jsonc ~/.claude/settings.json > /tmp/pre-repro-before.md5

# 2) 当前运行日志备份（B 站，蓝区保留）
ts=$(date +%Y%m%d%H%M%S)
cp ~/.unsloth/run-gpt-oss-120b.log ~/.unsloth/run-gpt-oss-120b.log.pre-${ts}
echo "backup: run-gpt-oss-120b.log.pre-${ts}"

# 3) 记录当前 API key（重启后会重铸，需比对）
grep -oE 'sk-unsloth-[a-f0-9]+' ~/.unsloth/run-gpt-oss-120b.log | tail -1 > /tmp/pre-repro-key.txt
```

验证：`ls -l` 确认 `.pre-${ts}` 大小与原日志一致；`cat /tmp/pre-repro-before.md5` 有 4 行。

### 1.2 重启流程（实例卡死/超时后的恢复）

```bash
# ① 停止当前实例（停旧 + 清残留，注意防自匹配）
sudo systemctl stop 'llama-server@*' 2>/dev/null || true
pkill -9 -f "[u]nsloth studio run" 2>/dev/null || true
pkill -9 -x llama-server 2>/dev/null || true

# ② 等待 GTT 内存释放（禁止固定 sleep；用 wait-gtt 逻辑轮询）
#    参考 infer-load 内 wait_gtt 实现，直到显存回落。

# ③ 重新加载（默认后端 unsloth，KV q8_0 保持）
infer-load gpt-oss --backend unsloth
```

### 1.3 key 重铸 → CLI 配置再同步（关键）

unsloth 每次重启 **重铸 API key**，所有指向 `:8080` 的 CLI 配置会失联。必须重跑 `_bkeyupdate.sh`：

```bash
# B 站执行；脚本会自动从最新 run log 提取 key 并写回
#   opencode.jsonc  provider.cluster-local.options.apiKey
#   settings.json   env.ANTHROPIC_AUTH_TOKEN
~/d6-agent-standard/station-bin/_bkeyupdate.sh   # 或 /ops/station-bin/_bkeyupdate.sh
# 脚本自检: 输出 "B-FINAL-OK" 且 [oc=0] 即通过
```

> 若 key 为占位脚本硬编码（`_bkeyupdate.sh` 内 KEY=… 是写死的），先改脚本从 log 提取，避免旧 key 回写。

### 1.4 复现后 / 启用后健康确认

```bash
bash /tmp/repro-health.sh   # 部署到 B 站后运行
# 通过判据: models HTTP_200 + 无残留 repro 进程 + 有 .pre-* 备份
```

***

## 2. 复现作业（存档）

### 2.1 复现方法（repro-fire.sh）

- 后端: unsloth llama-server，`gpt-oss-120b-MXFP4`
- 手段: 两并发 `POST /v1/completions`，各喂 **1500 词随机文本** prefill，`max_tokens=16` 短 decode（聚焦 prefill/batch 相位卡死），`stream=false`，`--max-time 300`
- 判定: 任一端 300s 超时且 rc 为空 → 挂起复现

### 2.2 结果

| 项 | 值 |
| --- | --- |
| A 请求（seed1） | 完成，非挂起 |
| B 请求（seed2） | 完成，非挂起 |
| 排空 batching | 两 slot 同批，正常 |
| 卡死 | **未复现** |

### 2.3 未复现的合理说明

- 卡死为概率性（窗口 + 内存布局 + 调度时序相关），当前稳定负载低，未达触发窗口
- 若需更大概率复现: 提高并发槽数、拉长 prefill、混入不同长度请求制造排空竞争，或切 HIP 后端交叉验证 logits

***

## 3. 回滚

- 配置: 从 `/tmp/pre-repro-conf/` 恢复 `.env`，重跑 `infer-load`
- 日志: 保留 `.pre-*` 供 diff，不覆盖
- CLI key: 用备份 key 或重跑 `_bkeyupdate.sh` 刷新