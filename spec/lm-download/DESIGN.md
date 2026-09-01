# LM Studio 下载断点续传方案 (CLI+镜像) — DESIGN

> **日期**: 2026-08-29
> **执行站**: B 站 (scott-lau-GTR-Pro, 192.168.1.15)
> **上游调研**: 《双机推理服务化与编排框架调研.md》v1.3 §7.7-7.9
> **需求**: 不等 GUI 下载, 直接用 CLI+hf-mirror 断点续传 B 站 8 个 .part, 校验收编

---

## 1. 背景与现状 (侦察实证, 2026-08-29 15:24)

- LM Studio GUI 下载任务全部 **paused / resumableFailure** ("Timed-out. Please try to resume.") — 不是慢速推进, 是超时暂停
- **LM Studio 进程当前未运行** (ps 无匹配) — 无写冲突, 无需停 GUI
- `.part` = 目标目录内纯顺序字节流 (offset 0 写起) — HTTP Range 续传可行
- `download-jobs-info.json` 内含每文件 `sha256` + `fileSizeBytes` — 校验链完整
- aria2 未安装 (需 apt); hf-mirror 单流 4.17MB/s 已验证 (B 站)

## 2. 任务清单 (manifest, 8 个 PART)

| # | 文件 | 总大小 | 已下载 | 剩余 |
|---|------|--------|--------|------|
| 1 | DeepSeek-V4-Flash MXFP4 00001/4 | 39.94GB | 13.81GB | 26.13GB |
| 2 | DeepSeek-V4-Flash MXFP4 00003/4 | 39.93GB | 26.96GB | 12.97GB |
| 3 | Qwen3.6-27B Q8_0 | 29.05GB | 27.41GB | 1.64GB |
| 4 | Qwen3.8-27B Q8_K_P | 31.46GB | 12.05GB | 19.41GB |
| 5 | GLM-5.3-Flash UD-IQ4_XS 00002/5 | 49.99GB | 1.11GB | 48.88GB |
| 6 | GLM-5.3-Flash UD-IQ4_XS 00003/5 | 49.61GB | 0.16GB | 49.44GB |
| 7 | GLM-5.3-Flash UD-IQ4_XS 00004/5 | 49.49GB | 5.34GB | 44.14GB |
| 8 | GLM-5.3-Flash UD-IQ4_XS 00005/5 | 7.73GB | 0.98GB | 6.75GB |

剩余合计 ≈ **209GB**。URL: `https://hf-mirror.com/<repo>/resolve/main/<file>` (json 内 hf-proxy URL 前缀替换)。
FINAL 文件 (DeepSeek 2/4 分片, Qwen3.8 mmproj, GLM 00001+mmproj) 不动。

## 3. 方案

```
每任务: aria2c -c (Range 续传原 .part) → 字节校验 → sha256 校验 → mv 收编
```

- **aria2 参数**: `-c -x16 -s16 --file-allocation=none --max-tries=10 --retry-wait=5 --auto-file-renaming=false --allow-overwrite=false -d <dir> -o downloading_<name>.part <mirror_url>`
  - `-c` = 对"浏览器式顺序下载"续传 (官方语义, 无 .aria2 控制文件也工作)
  - `--file-allocation=none` 必须 — 预分配 209GB 会假死
  - 串行执行 (一次一任务, 16 连接); 不并行多任务, 避免镜像限流 + 日志清晰
- **校验门槛 (mv 前, 双验)**: ① `stat -c%s` == fileSizeBytes; ② `sha256sum` == json sha256
- **收编**: `mv downloading_xxx.part <savePath>` (原子, 只改名)
- **GUI 任务清理**: 不编辑 download-jobs-info.json (LM Studio 内部状态, 编辑有覆写风险); 用户下次打开 GUI 后手动删任务条目 (文件已就位, 删任务不影响)
- **执行模式**: nohup 后台 + 日志, 预估 209GB @ 30-50MB/s ≈ 1.2-2 小时

## 4. 风险与缓解

| 风险 | 缓解 |
|------|------|
| aria2 -c 对 .part 行为不符预期 (截断/旁文件) | --auto-file-renaming=false + --allow-overwrite=false; 先单任务试跑 #3 (最小 1.64GB), 验证行为再跑其余 |
| hf-mirror 限流多连接 | 16 连接试跑观察; 若限速, 降 -x 或换时段 |
| 磁盘空间不足 209GB | pre-flight `df` 检查模型盘 |
| .part 前缀字节损坏 (LM Studio 超时写坏) | sha256 终验兜底; 失败则该文件 aria2 重下 (删 .part) |
| LM Studio GUI 中途被打开重试下载, 写冲突 | 脚本 pre-flight 检查 ps 无 LM Studio; 执行期间勿开 GUI (写入操作规程) |
| 半截 GGUF 被误收编 | 双验门槛 (字节+sha256) 不通过不 mv |

## 5. 验收标准

1. 8 个文件全部 FINAL, sha256 与 json 记录一致
2. `llama-server` (或 LM Studio) 能加载任一收编模型 (冒烟, 后续 B5m1 一并验)
3. 全程日志 + 度量落档 (下载速度实测 → 报告 7.8 预期值回填)

## 6. 度量

- 每任务: 续传字节数 / 耗时 / 平均速度 / aria2 退出码
- 汇总: 总吞吐 vs GUI 基线 (GUI 实际 ~0 — paused) vs hf-mirror 单流 4.17MB/s vs hf CLI 77.8MB/s

---

## 7. 执行结果 (2026-08-29 15:54–17:07, 全部完成)

**8/8 任务零失败, 8 个 .part 全部 sha256 校验通过并原子收编:**

| # | 文件 | 增量 | 耗时 | 速度 | sha256 |
|---|------|------|------|------|--------|
| 3(试跑) | Qwen3.6-27B Q8_0 | 1.5GB | 102s | 15MB/s | OK |
| 1 | DeepSeek 00001/4 | 24.9GB | 536s | 46MB/s | OK |
| 2 | DeepSeek 00003/4 | 12.4GB | 248s | 49MB/s | OK |
| 4 | Qwen3.8-27B Q8_K_P | 18.5GB | 372s | 49MB/s | OK |
| 5 | GLM 00002/5 | 46.6GB | 895s | 52MB/s | OK |
| 6 | GLM 00003/5 | 47.2GB | 1009s | 46MB/s | OK |
| 7 | GLM 00004/5 | 42.1GB | 886s | 47MB/s | OK |
| 8 | GLM 00005/5 | 6.4GB | 143s | 44MB/s | OK |

- **总增量 ~195GB, 总耗时 ~73 分钟 (含 sha256 校验), 稳态 46-52MB/s** — 为 hf-mirror 单流 (4.17MB/s) 的 ~11x, 接近 hf CLI 多连接水平 (77.8MB/s)
- **试跑任务 #3 (1.64GB) 先行验证了 aria2 -c 对 LM Studio .part 的续传语义** — 前缀字节无损 (全文件 sha256 与 LM Studio json 记录一致), 方案一次通过
- 产物: 四模型全部完整收编 — DeepSeek-V4-Flash MXFP4 (4/4 分片 156G) + Qwen3.6-27B Q8_0 (29G) + Qwen3.8-27B Q8_K_P+mmproj (31.5G) + GLM-5.3-Flash UD-IQ4_XS (5/5 分片+mmproj 155G)
- (8-30 复核: 8-29 晚曾误判 "GLM 00001 为 9.4MB 残片缺 46.6G" 并修正本节 — 后经 hf-mirror tree API 复核撤销: **00001 远端真实 size 即 9,429,859B (GGUF 分片 00001 常为 header-only 小分片), sha256 与 LFS oid 一致**; 全 6 文件复验 6/6 通过, "FINAL 文件不动" 的原始判定本来就正确。完整复盘见主报告 7.11。教训: 完整性判定必须对照远端权威元数据, 禁止用同模型分片均分外推)
- 磁盘: 收编后 B 站模型盘剩 552G
- 执行中发现并修复: pre-flight 的 pgrep "lm.?studio" 会误匹配 llama-server 的 `.lmstudio` 模型路径 (顺带发现集群现役 GGUF 位于 `~/.lmstudio/models/llmfan46/` — B5m1 盘点范围), 改用 **fuser 检查 .part 文件占用** 作为写冲突判据 (精确判据: 谁占用谁冲突, 与进程名无关)
- 遗留用户操作: 下次打开 LM Studio GUI 后手动删除 4 个下载任务条目 (文件已就位, 删任务不影响文件; 不删则误点"重试"会重下覆盖)
- 日志: B 站 `/tmp/lm_resume_main.log` (主) + `/tmp/aria2_task*.log` (分任务)
