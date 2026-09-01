# UPGRADE_SOP.md — llama.cpp Vulkan 后端两站原子升级 SOP

> **Feature**: vulkan-version-control（M4 交付物）
> **前置**: 第 0 步已完成（9859 已版本化，`/opt/llama.cpp` 为 symlink）
> **适用**: 升级到上游新版本（tag 形如 v0.2.0 / b10xxx）
> **原则**: 两站视为一个原子整体 — B 站单点构建，产物分发，symlink 同步切换

---

## 升级六步流程

### 1. 停服务

```bash
# B 站 (Master)
ssh scott-lau@scott-lau-GTR-Pro.local "pkill -x llama-server"
# A 站 (Worker) rpc-server 可保留运行（不影响文件切换），但建议一并重启以加载新库
```

### 2. B 站构建（唯一构建源）

```bash
ssh scott-lau@scott-lau-GTR-Pro.local '
  mkdir -p ~/src/llama.cpp ~/build ~/dist
  cd ~/src/llama.cpp && git fetch --tags
  git checkout <目标tag>            # 例: v0.2.0
  cmake -B ~/build/llama-<ver> -DGGML_VULKAN=1 -DGGML_RPC=ON -DCMAKE_BUILD_TYPE=Release
  cmake --build ~/build/llama-<ver> --config Release -j $(nproc)
'
# 安装到新版本目录（不动 symlink）:
ssh scott-lau@scott-lau-GTR-Pro.local '
  sudo mkdir -p /opt/llama.cpp-<ver>
  sudo cp -a ~/build/llama-<ver>/bin/* /opt/llama.cpp-<ver>/   # 按实际产物路径调整
'
# 写 MANIFEST（复用 gen_manifest.sh）+ 打 tar:
ssh scott-lau@scott-lau-GTR-Pro.local '
  bash /tmp/gen_manifest.sh /opt/llama.cpp-<ver>
  sudo tar -czf ~/dist/llama-<ver>.tar.gz -C /opt llama.cpp-<ver>
  sudo chown scott-lau:scott-lau ~/dist/llama-<ver>.tar.gz
'
```

### 3. 分发到 A 站 + MD5 校验

```bash
scp scott-lau@scott-lau-GTR-Pro.local:~/dist/llama-<ver>.tar.gz /tmp/   # 或主控站中转
scp /tmp/llama-<ver>.tar.gz scott-lau@scott-lau-NEX.local:/tmp/
ssh scott-lau@scott-lau-NEX.local '
  sudo tar -xzf /tmp/llama-<ver>.tar.gz -C /opt/
  cd /opt/llama.cpp-<ver> && sed -n "/\[md5\]/,\$p" MANIFEST | tail -n +2 | md5sum -c
'
# 校验失败 → 立即中止升级，回第 2 步重传
```

### 4. 原子切换（A 先 B 后）

```bash
# A 站
ssh scott-lau@scott-lau-NEX.local 'sudo ln -sfn llama.cpp-<ver> /opt/llama.cpp && /opt/llama.cpp/llama-cli --version'
# A 站重启 RPC worker
ssh scott-lau@scott-lau-NEX.local 'bash /llama-distributed/start_rpc.sh'
#   → 检查日志 "Starting RPC server vX.Y.Z"（协议版本，与旧版 v4.0.1 对比 = 兼容性第一信号）

# B 站
ssh scott-lau@scott-lau-GTR-Pro.local 'sudo ln -sfn llama.cpp-<ver> /opt/llama.cpp && /opt/llama.cpp/llama-cli --version'
```

### 5. 冒烟测试（必须通过才视为升级成功）

```bash
# B 站启动推理服务（复用 run_server.sh，加载大模型约 4 分钟）
ssh scott-lau@scott-lau-GTR-Pro.local "bash ~/llama-distributed/run_server.sh 8080"
# PONG 冒烟:
curl http://192.168.1.15:8080/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"m","messages":[{"role":"user","content":"Reply exactly: UPGRADE_PONG"}],"max_tokens":1024}'
# 同时运行巡检:
bash D:/RPC/scripts/check_llama_version.sh --deep
```

### 6. 收尾 / 回滚

**收尾**：
```bash
# 巡检通过 + 冒烟通过后:
# 保留最近 2 个版本目录（<ver> + 9859），更旧的删除
sudo rm -rf /opt/llama.cpp-<旧旧版本>
# 更新 提速调研报告.md / 分布式推理.md 的版本记录
```

**回滚**（分钟级，I5 不变式保障旧目录仍在）：
```bash
ssh scott-lau@scott-lau-NEX.local  'sudo ln -sfn llama.cpp-9859 /opt/llama.cpp && bash /llama-distributed/start_rpc.sh'
ssh scott-lau@scott-lau-GTR-Pro.local 'sudo ln -sfn llama.cpp-9859 /opt/llama.cpp && bash ~/llama-distributed/run_server.sh 8080'
# 重跑巡检 + 冒烟
```

---

## 日常巡检（升级间隔期）

```bash
bash D:/RPC/scripts/check_llama_version.sh          # 指纹级（秒级）
bash D:/RPC/scripts/check_llama_version.sh --deep   # 全量 MD5（分钟级）
```

两站不一致 = 有人单独动过其中一站 → 立即按回滚流程对齐。

## 应急后备（B 站不可用时）

A 站 HTTPS 直下源码 tarball 自行构建（实测可达 codeload）：
```bash
ssh scott-lau@scott-lau-NEX.local '
  curl -L https://codeload.github.com/ggml-org/llama.cpp/tar.gz/refs/tags/<tag> -o /tmp/llama-src.tar.gz
  # 构建流程同第 2 步（注意: 应急路径会引入编译环境漂移风险，恢复后须用 B 站产物重新对齐）
'
```
