# station-bin/ — 两站 /usr/local/bin 推理框架的仓库快照

> 快照时间: 2026-09-02 00:14 · 来源: B 站（两站 md5 一致，见下）
> 用途: 版本控制 + 灾难恢复参照。修改站侧脚本时**先改这里（review）再同步上站**，保持两站一致。

## 文件清单

| 文件 | 站侧路径 | 说明 |
|------|---------|------|
| infer-load | /usr/local/bin/infer-load | 加载入口（含 F2 修复：RPC_TARGET 空时跳过 wait_gtt A） |
| infer-unload | /usr/local/bin/infer-unload | 卸载（含 F2 修复：rpc-server 未运行时跳过 A GTT 等待） |
| infer-list | /usr/local/bin/infer-list | 模型清单 |
| llama-serve-instance | /usr/local/bin/llama-serve-instance | systemd 实例包装器 |
| load-mem-gate | /usr/local/bin/load-mem-gate | 内存门（12G 垫） |
| wait-gtt-release | /usr/local/bin/wait-gtt-release | GTT 回收等待 |

## 两站一致性

修改后核对：`md5sum /usr/local/bin/<file>`（两站必须一致）。
当前（2026-09-02 00:14）：infer-load `e5a76cb8...` / infer-unload `bb23389b...` 两站一致。

## F2 修复记录（2026-09-02）

- **现象**: 双端点模式下 B 站 load/unload 固定空等 ~18min（A 站常驻 gpt-oss GTT 135G 永不 <2G，90 次×~12s SSH 轮询走满才 WARN 放行）
- **修复**: infer-load 按 `RPC_TARGET` 判空跳过；infer-unload 按 "A 站 rpc-server 是否本就运行" 判定跳过（RPC 模式行为不变）
- **实测**: nemotron 换载 20min → 2.7min；双站 unload 32s
- **备份**: 站侧 `*.bak-f2fix` ×2/站
