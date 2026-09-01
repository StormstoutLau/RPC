# B5i 手动模型加载层 DESIGN

## 目标
手动加载模型（指定模型/后端/参数），消除开机自加载。B5m5 的完整形态。

## 决策记录
1. **载体**: llama 路径用 systemd 模板 unit（`llama-server@<alias>` / `rpc-server@<alias>`）→ Cockpit 服务页免费集成；vLLM 路径保持脚本（Ray 双机编排 20+ env 不适合 systemd）
2. **conf 外置**: `/etc/llama-instances/<alias>.env`（两站同路径）。首次 infer-load 自动生成默认 conf，之后改 conf + restart 即调参
3. **wrapper 启动**: systemd 不做 shell 展开（RPC 参数有无/单机分布式判定无法用 EnvironmentFile 表达）→ `llama-serve-instance <alias>` wrapper 读 conf 拼 args 后 exec llama-server
4. **alias 规则**: repo 目录名去 `-GGUF` 后缀小写；infer-load 支持唯一前缀匹配（`glm` → `glm-5.3-flash`）
5. **后端判定**（自动，可 --backend 覆盖）: B 站持有 + 权重>65G → llama-rpc；≤65G → llama-single；AWQ → vllm（仅 m27-awq 验证，MoE tuned-config 模型专用）；A 站独有 → 不可加载（标"需同步"，RPC client=B 站必须 mmap 本地文件）
6. **开机自启全部移除**: llama-server@B、rpc-server@A disable（用户裁决）；不保留默认实例（用户裁决）
7. **互斥**: infer-load 前停另一后端（a4_cleanup.sh / stop 旧实例）+ wait_gtt_free 两站
8. **CLI 部署位置**: B 站 /usr/local/bin（主控站 `ssh B infer-list`，Cockpit web 终端也可用）
9. **缓存路径**: A 站 `LLAMA_CACHE=/data/rpccache/<alias>`；现有 MiniMax-M2.7-Q4KS 目录 mv 为 m27-q4ks（同盘零拷贝）
10. **embedding 模型**: all-minilm 633 需 `--embedding`，conf 默认 EXTRA_FLAGS 注入，属边缘 case

## conf 格式 (B 站视角)
```bash
# /etc/llama-instances/glm-5.3-flash.env  (自动生成示例)
MODEL_PATH=/data/models/gguf/unsloth/GLM-5.3-Flash-GGUF/GLM-5.3-Flash-UD-IQ4_XS-00001-of-00005.gguf
PORT=8080
CTX=32768
THREADS=16
N_CPU_MOE=8
RPC_TARGET=10.10.10.1:50052   # 空 = 单机
EXTRA_FLAGS=-fa on
```
A 站同路径 conf 只用 alias（LLAMA_CACHE=/data/rpccache/<alias>），由 infer-load scp 同步。

## CLI 语义
```
infer-list                          # 两站扫描: alias/位置/大小/建议后端/conf状态
infer-load <prefix> [--backend B] [--port N] [--ctx N]
infer-unload                        # stop 两站 llama 实例 + vllm, 等 GTT 释放
```

## 冒烟验收
infer-list 全 30 repo → infer-load m27（现役模型回归）→ :8080 API 生成 OK → infer-unload → 两站 GTT <2G → 重新 load 验证 conf 持久 + LiteLLM 网关链路 (:4000) 正常。
