# SSH + opencode 远程调用配置排查记录

> 日期: 2026-07-30
> 作者: Scott (鹏)
> 关联文档: `MULTI_AGENT_TRIAL.md` (多模型能力验证)
> 状态: ✅ 已跑通，可投入生产

---

## 1. 背景与目标

### 1.1 目标
主控站 (Windows 10, 192.168.1.10) 通过 SSH 远程驱动 A/B 两台 Ubuntu 工作站上的 opencode CLI，让 agent 自主完成 C++ 编码任务（创建文件、编译、运行测试、迭代修复），实现多 Agent 并行开发工作流。

### 1.2 硬件拓扑

```
主控站 (Win10, 192.168.1.10)
   │ SSH + HTTP
   ├── A 站 (Ubuntu, scott-lau-NEX.local, 192.168.1.11)
   │         LM Studio: qwen3-coder-next
   │         opencode 1.18.8 (/snap/bin/opencode)
   │         mihomo (Clash) 代理: 127.0.0.1:7890
   │
   └── B 站 (Ubuntu, scott-lau-GTR-Pro.local, 192.168.1.15)
             LM Studio: gpt-oss-120b-fable-5-distilled / nemotron-3-nano / 多模型
             opencode 1.18.9 (~/.opencode/bin/opencode)
             ❌ 无 mihomo 代理 (之前文档记录错误, 实测 /root/clashctl/ 不存在)
             ✅ 改用 LM Studio 本地模型 (无需代理)
```

### 1.3 失败的旧方案 (call_llm.py)
之前的方案是主控站直接 HTTP 调用 A/B 站 LM Studio 的 `/v1/chat/completions` 端点：
- ❌ 只能一次性生成代码文本，agent 无法自己编译/测试
- ❌ 单点 bug（如 gpt-oss 的运算符优先级括号缺失）无法自修复
- ❌ 4 个模型测试通过率仅 61.5%~85.7%

### 1.4 新方案预期
用 opencode agent 替代裸 LLM 调用：
- ✅ agent 可读编译错误并自修复
- ✅ agent 可运行测试并迭代
- ✅ 主控站只需派发任务、拉取结果

---

## 2. SSH 配置排查全过程

### 2.1 初始尝试 (失败)

**操作**: 主控站 PowerShell 直接 SSH 登录
```powershell
ssh scott-lau-NEX "echo OK"
ssh scott-lau-GTR-Pro "echo OK"
```

**结果**: 两站都失败
- A 站: `Permission denied (publickey,password)`
- B 站: `Host key verification failed`

**诊断 1**: 主机名解析
```powershell
Resolve-DnsName scott-lau-NEX
Resolve-DnsName scott-lau-GTR-Pro
```
**输出**:
```
scott-lau-NEX.local     192.168.1.11
scott-lau-GTR-Pro.local 192.168.1.15
```
✅ mDNS 解析正常，但需用 `.local` 后缀。

### 2.2 密码登录排查

**操作**: 用 SSH_ASKPASS 传密码
```powershell
# 创建 askpass 脚本
"@echo 860129" | Set-Content -Path $env:TEMP\sshaskpass.bat
$env:SSH_ASKPASS = "$env:TEMP\sshaskpass.bat"
$env:SSH_ASKPASS_REQUIRE = "force"
ssh scott@scott-lau-GTR-Pro.local "echo OK"
```

**结果**: `Permission denied (publickey,password)`

**排查用户名**:
- 试 `scott@`: ❌ Permission denied
- 试 `peng@`: ❌ Permission denied
- 试 `scott-lau@`: ❌ Permission denied

**根因**: Windows OpenSSH 的 SSH_ASKPASS 在非 GUI 会话中传递密码存在已知兼容性问题，密码未正确传到 sshd。

### 2.3 paramiko 方案 (成功)

**思路**: 绕过 Windows ssh 命令，用 Python paramiko 库直接实现 SSH 协议登录。

**安装 paramiko**:
```powershell
pip install paramiko
```

**关键发现**: `python` 和 `pip` 指向不同环境！
```
python → C:\Users\Peng\.hermes\hermes-agent\venv\Scripts\python.exe (Python 3.11, 无 paramiko)
pip     → C:\Users\Peng\AppData\Local\Programs\Python\Python312\Scripts\pip.exe (Python 3.12, 有 paramiko)
```

**解决**: 用 Python 3.12 完整路径执行脚本。

**ssh_setup.py 脚本** ([scripts/ssh_setup.py](file:///f:/Cpp_Hub/scripts/ssh_setup.py)):
```python
import paramiko, os

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=user, password=password, timeout=15)

# 读取本机公钥
with open(os.path.expanduser("~/.ssh/id_ed25519.pub")) as f:
    pub_key = f.read().strip()

# 追加到远程 authorized_keys
cmd = (
    f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
    f"grep -qF '{pub_key}' ~/.ssh/authorized_keys 2>/dev/null || "
    f"echo '{pub_key}' >> ~/.ssh/authorized_keys && "
    f"chmod 600 ~/.ssh/authorized_keys && echo KEY_INSTALLED"
)
stdin, stdout, stderr = client.exec_command(cmd)
```

**执行**:
```powershell
& "C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe" `
  f:\Cpp_Hub\scripts\ssh_setup.py scott-lau-GTR-Pro.local scott-lau 860129
```

**输出**:
```
[1/4] 密码登录成功
[2/4] 远程身份: scott-lau @ scott-lau-GTR-Pro
[3/4] 公钥: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5...
[4/4] 公钥已安装到远程 authorized_keys
```

### 2.4 免密验证

**操作**:
```powershell
ssh -o BatchMode=yes -o ConnectTimeout=10 scott-lau@scott-lau-NEX.local "echo A_OK; which opencode"
ssh -o BatchMode=yes -o ConnectTimeout=10 scott-lau@scott-lau-GTR-Pro.local "echo B_OK; which opencode"
```

**结果**:
| 站 | 用户名 | opencode 版本 | opencode 路径 | 免密 |
|---|---|---|---|---|
| A | scott-lau | 1.18.8 | `/snap/bin/opencode` | ✅ |
| B | scott-lau | 1.18.9 | `~/.opencode/bin/opencode` | ✅ |

### 2.5 主机密钥信任问题

**问题**: B 站首次免密登录报 `Host key verification failed`。

**根因**: 之前用 IP `192.168.1.15` 连接过，known_hosts 中存的是 IP 的密钥；现在改用 `scott-lau-GTR-Pro.local` 域名，被视为新主机。

**解决**: 首次连接加 `-o StrictHostKeyChecking=accept-new`:
```powershell
ssh -o StrictHostKeyChecking=accept-new scott-lau@scott-lau-NEX.local "echo OK"
```

### 2.6 SSH config 配置失败

**尝试**: 在 `~/.ssh/config` 中固化别名简化命令
```
Host scott-lau-NEX
    HostName scott-lau-NEX.local
    User scott-lau
    StrictHostKeyChecking accept-new
```

**失败**: Trae 沙箱安全策略禁止写 `~/.ssh/config`:
```
Refuse to delete or operate 'c:\users\peng\.ssh\config': path not in allowlist
```

**应对**: 改用完整形式 `scott-lau@scott-lau-NEX.local`，不依赖 config 别名。

### 2.7 SSH 排查小结

| 问题 | 根因 | 解决方案 |
|---|---|---|
| 主机名不解析 | 需 `.local` 后缀 (mDNS) | 用 `scott-lau-NEX.local` 全名 |
| 密码登录失败 | Windows SSH_ASKPASS 兼容性问题 | 改用 Python paramiko |
| python 缺 paramiko | `python`/`pip` 指向不同环境 | 用 Python 3.12 完整路径 |
| Host key verification | IP vs 域名视为不同主机 | `StrictHostKeyChecking=accept-new` |
| 无法写 ~/.ssh/config | Trae 沙箱限制 | 用完整 `user@host.local` 形式 |
| B 站 opencode 不在 PATH | 非交互 shell 不加载 .bashrc | 用全路径 `~/.opencode/bin/opencode` |

---

## 3. opencode 远程调用排查

### 3.1 opencode 配置检查

**A 站** (`~/.config/opencode/opencode.jsonc`):
```json
{
  "$schema": "https://opencode.ai/config.json",
  "disabled_providers": ["lm-studio-local"],
  "provider": {
    "lm-studio-local": {
      "name": "Local Provider",
      "npm": "@ai-sdk/openai-compatible",
      "options": { "baseURL": "http://localhost:1234/v1" },
      "models": { "gpt-oss-120b": { "name": "GPT-OSS-120B" } }
    }
  }
}
```

**B 站**: 仅默认配置 `{"$schema": "https://opencode.ai/config.json"}`

**可用模型** (两站相同，opencode 内置免费模型):
```
opencode/big-pickle
opencode/deepseek-v4-flash-free
opencode/laguna-s-2.1-free
opencode/mimo-v2.5-free
opencode/nemotron-3-ultra-free
opencode/north-mini-code-free
```

### 3.2 第一次远程调用尝试 (失败)

**操作**: 非交互 SSH 调用 opencode run
```bash
ssh scott-lau@scott-lau-NEX.local "cd /tmp && opencode run --model opencode/deepseek-v4-flash-free 'Say hello'"
```

**结果**: 无输出，超时。

**DEBUG 日志**:
```
timestamp=... level=INFO message="creating instance" directory=/tmp
timestamp=... level=INFO message=init
timestamp=... level=ERROR message="Failed to fetch models.dev" cause=Cause([Fail(TimeoutError)])
```

**根因 1**: `models.dev` 被墙，opencode 启动时尝试拉取模型元数据失败。

### 3.3 代理排查

**检查代理进程**:
```bash
ssh scott-lau@scott-lau-NEX.local "ps aux | grep -iE 'clash|mihomo' | grep -v grep"
```
**输出**:
```
root  2077  /root/clashctl/bin/mihomo -d /root/clashctl/resources -f /root/clashctl/resources/runtime.yaml
```

**检查代理端口**:
```bash
ss -tlnp | grep 7890
```
**输出**: `LISTEN 127.0.0.1:7890` ✅ mihomo 监听本地 7890。

**检查环境变量**:
```bash
env | grep -iE 'proxy|PROXY'
```
**输出**: 空 ❌

**根因 2**: mihomo 代理运行中，但代理配置在 GNOME 图形会话的环境变量中，非交互 SSH shell 不继承。

### 3.4 代理修复 (部分成功)

**操作**: SSH 调用时显式设置代理环境变量
```bash
ssh scott-lau@scott-lau-NEX.local "export http_proxy=http://127.0.0.1:7890 https_proxy=http://127.0.0.1:7890; cd /tmp && opencode run --model opencode/deepseek-v4-flash-free 'Say hello'"
```

**结果**: `EXIT=True`（退出码 0），但无 stdout 输出。

**代理验证**:
```bash
curl -sS --max-time 10 https://models.dev  # 仍超时 (SSL_ERROR_SYSCALL)
```
**结论**: 代理让 opencode 的 API 调用成功（opencode.ai 端点可达），但 models.dev 仍不可达（可能被 Cloudflare 单独屏蔽）。

### 3.5 交互式 PTY 模式 (成功)

**关键发现**: 加 `-t` 参数分配 PTY 后，opencode 能正常工作。

**操作**:
```bash
ssh -t scott-lau@scott-lau-NEX.local "export http_proxy=http://127.0.0.1:7890 https_proxy=http://127.0.0.1:7890; cd /tmp && opencode run -m opencode/deepseek-v4-flash-free 'Reply with exactly: PONG'"
```

**输出**:
```
> build · deepseek-v4-flash-free
PONG
```
✅ 成功！

### 3.6 opencode serve 模式 (失败)

**尝试**: 启动 headless server，主控站 HTTP API 调用
```bash
ssh -t scott-lau@scott-lau-NEX.local "opencode serve --port 4096 --hostname 0.0.0.0"
```

**Server 启动成功**:
```
opencode server listening on http://0.0.0.0:4096
```

**主控站 HTTP 调用**:
```python
# 创建 session
POST http://192.168.1.11:4096/session
→ {"id": "ses_04e2aa938ffelkwUXFhdQemg5o", "agent": "build"}

# 发送消息
POST http://192.168.1.11:4096/session/{sid}/message
body: {"parts": [{"type": "text", "text": "Say hello"}]}
```

**结果**: 401 认证失败
```json
{
  "error": {
    "name": "APIError",
    "data": {
      "message": "No provider available",
      "statusCode": 401,
      "responseBody": "{\"type\":\"error\",\"error\":{\"type\":\"ModelError\",\"message\":\"No provider available\"}}",
      "metadata": {"url": "https://opencode.ai/zen/v1/chat/completions"}
    }
  }
}
```

**根因 3**: opencode Zen 免费模型需要 opencode.ai 平台认证，认证 token 存在 GNOME keyring 中。serve 模式作为后台进程运行，无法访问 keyring。

**检查 keyring**:
```bash
secret-tool search service opencode  # 空
cat ~/.local/share/opencode/auth.json  # {}
```
**结论**: 认证 token 不在文件中，可能在 keyring 但 serve 进程无法读取，或需要 GUI 登录流程。

### 3.7 opencode run --auto 模式 (最终方案)

**思路**: 用 `ssh -t` + `opencode run --auto` 绕过 serve 模式的认证问题，让 agent 在 PTY 会话中自主完成任务。

**--auto 参数作用**: 自动批准所有非明确拒绝的权限（文件读写、shell 执行），无需人工确认。

**完整测试命令**:
```bash
ssh -t scott-lau@scott-lau-NEX.local \
  "export http_proxy=http://127.0.0.1:7890 https_proxy=http://127.0.0.1:7890; \
   mkdir -p /tmp/oc_codetest && cd /tmp/oc_codetest && \
   timeout 120 opencode run --auto -m opencode/deepseek-v4-flash-free \
   'Create a C++ file hello.cpp that prints Hello World. Then compile and run it.'"
```

**输出**:
```
> build · deepseek-v4-flash-free

← Write hello.cpp
Wrote file successfully.

$ g++ hello.cpp -o hello && ./hello
Hello World

Done. hello.cpp prints "Hello World" as expected.
```

✅ **完美！agent 自主完成：创建文件 → 编译 → 运行 → 验证输出**

### 3.8 opencode 排查小结

| 问题 | 根因 | 解决方案 |
|---|---|---|
| models.dev 超时 | 被墙 | 设置 http_proxy 指向 mihomo |
| 代理环境变量缺失 | 非交互 shell 不继承 GNOME 配置 | `export http_proxy=http://127.0.0.1:7890` |
| 无 stdout 输出 | 非交互模式输出被吞 | 加 `-t` 分配 PTY |
| serve 模式 401 | keyring 认证不可用 | 弃用 serve，改用 `run --auto` |
| 文件操作需确认 | 默认要求人工批准 | 加 `--auto` 自动批准 |

---

## 4. 最终工作模式

### 4.1 标准调用模板

```powershell
# A 站 (opencode 在 /snap/bin/)
ssh -t scott-lau@scott-lau-NEX.local `
  "export http_proxy=http://127.0.0.1:7890 https_proxy=http://127.0.0.1:7890; `
   mkdir -p /tmp/<task_name> && cd /tmp/<task_name> && `
   timeout <max_seconds> opencode run --auto -m opencode/deepseek-v4-flash-free `
   '<task_prompt>'"

# B 站 (opencode 在 ~/.opencode/bin/)
ssh -t scott-lau@scott-lau-GTR-Pro.local `
  "export http_proxy=http://127.0.0.1:7890 https_proxy=http://127.0.0.1:7890; `
   mkdir -p /tmp/<task_name> && cd /tmp/<task_name> && `
   timeout <max_seconds> ~/.opencode/bin/opencode run --auto -m opencode/deepseek-v4-flash-free `
   '<task_prompt>'"
```

### 4.2 完整任务工作流

```
1. 主控站: 准备 task prompt (VALIDATION_PROMPT.md)
2. SCP:    scp prompt.md scott-lau@station:/tmp/task/
3. SSH:    ssh -t ... opencode run --auto -m model 'prompt'
4. Agent:  自主创建文件 → 编译 → 测试 → 修复迭代
5. SCP:    scp -r scott-lau@station:/tmp/task/ f:\results\
6. 主控站: 用 scipy 基准验证数值正确性
```

### 4.3 关键参数说明

| 参数 | 作用 | 必要性 |
|---|---|---|
| `ssh -t` | 分配 PTY，继承 keyring 认证 | **必需** |
| `export http_proxy=...` | 通过 mihomo 代理访问 opencode.ai | **必需** |
| `--auto` | 自动批准文件操作和 shell 执行 | **必需** |
| `-m opencode/deepseek-v4-flash-free` | 指定免费模型 | **必需** |
| `timeout <N>` | 防止 agent 无限循环 | 推荐 |
| `--format json` | 输出 JSON 事件流（可解析） | 可选 |
| `--print-logs --log-level DEBUG` | 调试日志 | 仅调试用 |

### 4.4 可用模型

| 模型 ID | 说明 | 适合场景 |
|---|---|---|
| `opencode/deepseek-v4-flash-free` | DeepSeek V4 Flash (免费) | 通用编码（推荐首选） |
| `opencode/nemotron-3-ultra-free` | NVIDIA Nemotron Ultra (免费) | 数值密集型（基于 B 站测试结果） |
| `opencode/north-mini-code-free` | 代码专用模型 | 快速原型 |
| `opencode/big-pickle` | 通用大模型 | 复杂推理 |

---

## 5. 验证脚本与工具

### 5.1 SSH 配置脚本
[scripts/ssh_setup.py](file:///f:/Cpp_Hub/scripts/ssh_setup.py) — 用 paramiko 登录并安装公钥

```powershell
& "C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe" `
  f:\Cpp_Hub\scripts\ssh_setup.py <host> <user> <password>
```

### 5.2 opencode HTTP 客户端 (已弃用)
[scripts/opencode_client.py](file:///f:/Cpp_Hub/scripts/opencode_client.py) — 用于 serve 模式的 HTTP API 客户端

> ⚠️ 此脚本因 serve 模式 401 认证问题已弃用，保留作参考。生产环境用 `ssh -t + opencode run --auto` 模式。

### 5.3 快速验证命令

```powershell
# 验证 SSH 免密
ssh -o BatchMode=yes scott-lau@scott-lau-NEX.local "echo A_OK; opencode --version"
ssh -o BatchMode=yes scott-lau@scott-lau-GTR-Pro.local "echo B_OK; ~/.opencode/bin/opencode --version"

# 验证 opencode 可用性
ssh -t scott-lau@scott-lau-NEX.local `
  "export http_proxy=http://127.0.0.1:7890 https_proxy=http://127.0.0.1:7890; `
   opencode run -m opencode/deepseek-v4-flash-free 'Reply: PONG'"
```

---

## 6. 已知限制与风险

### 6.1 当前限制
1. **mDNS 依赖**: 主机名解析依赖 `.local` mDNS，若路由器关闭 mDNS 需改用 IP
2. **动态 IP**: A/B 站为动态 IP，IP 变化后需更新 known_hosts (`ssh-keygen -R <old_ip>`)
3. **代理依赖**: opencode Zen 免费模型必须经 mihomo 代理访问 opencode.ai
4. **PTY 依赖**: 必须用 `ssh -t`，非交互模式无法获取 keyring 认证
5. **timeout 必要**: agent 可能陷入循环，需用 `timeout` 限制最大执行时间
6. **Trae 沙箱限制**: 无法写 `~/.ssh/config`，必须用完整 `user@host.local` 形式

### 6.2 安全风险
1. **--auto 危险性**: agent 可自主执行任意 shell 命令，包括 `rm -rf`。建议:
   - 在 `/tmp/` 隔离目录中运行
   - 不在 agent 可访问目录放置敏感文件
   - 用 `timeout` 限制执行时间
2. **无密码 SSH**: 公钥已安装到 A/B 站，任何能访问主控站私钥的进程都可登录
3. **代理无认证**: mihomo 监听 `127.0.0.1:7890` 无密码保护

### 6.3 替代方案
若 opencode Zen 免费模型不可用，可回退到 LM Studio 本地模型：
- 修改 `~/.config/opencode/opencode.jsonc` 添加 LM Studio provider
- 用 `-m lm-studio-local/gpt-oss-120b` 调用本地模型
- 无需代理，但模型质量受 LM Studio 加载的模型限制

---

## 7. 排查决策树 (快速参考)

```
SSH 连接失败?
├── Permission denied
│   ├── 用户名错误? → 在 A/B 站本机执行 whoami 确认
│   ├── 密码错误? → 用 paramiko 验证 (Windows SSH_ASKPASS 不可靠)
│   └── 公钥未安装? → 运行 ssh_setup.py
├── Host key verification failed
│   └── ssh-keygen -R <host> 清理后用 accept-new 重连
└── Connection timeout
    └── 检查 mDNS: Resolve-DnsName <host>.local

opencode run 无输出?
├── 非 PTY 模式? → 加 ssh -t
├── models.dev 超时? → export http_proxy=http://127.0.0.1:7890
├── 文件操作被阻塞? → 加 --auto
└── 仍失败? → 加 --print-logs --log-level DEBUG 看日志

opencode serve 401?
└── keyring 认证不可用 → 弃用 serve, 改用 ssh -t + run --auto
```

---

## 8. 下一步计划

1. **派发完整编码任务**: 用 VALIDATION_PROMPT.md 测试 deepseek-v4-flash-free 在 opencode agent 模式下的 C++ 代码生成质量
2. **对比 agent vs 裸 LLM**: 同一 prompt，对比 opencode agent（可编译测试自修复）与 call_llm.py（一次性生成）的通过率
3. **并行任务派发**: 同时在 A/B 站派发不同模块的编码任务，验证多 Agent 并行开发工作流
4. **结果回传自动化**: 编写 SCP 拉取脚本，自动将远程项目目录同步回主控站验证

---

**文档版本**: 1.7
**最后验证**: 2026-07-30 18:15 (CST)
**验证状态**: A 站 16/16 (100%), B 站 Zen 直连 16/16 (100%), B 站 qwen3-coder-next 0% (死循环), B 站 qwen3.5-122b-uncensored 82.4% (14/17, 逆CDF失败)

---

## 附录 B: A 站 agent 实测结果与 B 站超时排查

> 实测日期: 2026-07-30
> 任务: 完整 C++ 编码（正态分布 + Black-Scholes 模型）
> 模型: opencode/deepseek-v4-flash-free
> 超时: 900 秒 (15 分钟)

### B.1 A 站实测结果 (✅ 成功)

**任务派发命令**:
```bash
ssh -t scott-lau@scott-lau-NEX.local "bash /tmp/oc_codetest/run_agent_task.sh"
```

**agent 自主完成的关键动作** (从 agent_log.txt 提取):
1. 创建完整项目结构: CMakeLists.txt + include/ + src/ + tests/
2. 实现 `normal_pdf/cdf/inv_cdf` 与 `bsm_call/put`
3. 编译 → 运行测试 → 读失败信息 → 修复代码 → 再编译 → 再测试
4. **关键修复**:
   - Acklam 算法系数交换 bug (肉眼难以发现的常数错位)
   - CDF 精度升级: 从有理近似改为 `std::erfc` (消除系统性偏差)
   - 逆 CDF 添加 Newton 精炼步骤 (将误差从 1e-5 降到 1e-9)
5. 全部 16 个测试通过

**结论**: agent 模式比裸 LLM 模式关键优势是**单点 bug 可自修复**。A 站任务中 3 个 bug 都不是一次性能写对的，但 agent 通过"编译-测试-读错误-修复"循环收敛到正确实现。

### B.2 B 站首次任务 (❌ 超时) 与根因排查

**首次命令** (使用 opencode Zen 远程免费模型):
```bash
ssh -t scott-lau@scott-lau-GTR-Pro.local \
  "export http_proxy=http://127.0.0.1:7890; \
   cd /tmp/oc_codetest && \
   timeout 900 ~/.opencode/bin/opencode run --auto -m opencode/deepseek-v4-flash-free \"$(cat TASK_PROMPT.md)\""
```

**结果**: `exit code 124` (timeout 终止)，agent_log.txt 仅 44 字节，只输出 `> build · deepseek-v4-flash-free` 后无任何动作。

**根因排查 (实测)**:
```bash
# 1. 检查 TASK_PROMPT.md 是否存在
ssh scott-lau@scott-lau-GTR-Pro.local "ls -la /tmp/oc_codetest/"
# ✅ TASK_PROMPT.md 存在 (5936 字节)

# 2. 基础 ping 测试 (不加代理)
ssh -t scott-lau@scott-lau-GTR-Pro.local "timeout 60 ~/.opencode/bin/opencode run --auto -m opencode/deepseek-v4-flash-free 'Reply: B_PONG'"
# ❌ 只输出 "> build · deepseek-v4-flash-free" 后 EXIT=True, 无 PONG

# 3. 检查 mihomo 代理
ssh scott-lau@scott-lau-GTR-Pro.local "curl -sS --max-time 10 -x http://127.0.0.1:7890 https://opencode.ai/zen/v1/models"
# ❌ curl: (7) Failed to connect to 127.0.0.1 port 7890 after 0 ms: Couldn't connect to server

# 4. 检查 mihomo 服务
ssh scott-lau@scott-lau-GTR-Pro.local "echo '860129' | sudo -S ls /root/clashctl/bin/"
# ❌ ls: 无法访问 '/root/clashctl/bin/': 没有那个文件或目录
# ❌ systemctl status mihomo → Unit mihomo.service could not be found
```

**根因**: **B 站从未安装 mihomo 代理服务**。之前 SSH_OPENCODE_SETUP.md 1.2 节记录的"B 站 mihomo 代理: 127.0.0.1:7890"是错误的（可能误把 A 站配置复制到 B 站描述）。opencode Zen 远程免费模型必须经代理访问 opencode.ai，B 站无代理 → opencode 启动后无法获取 LLM 响应 → agent loop 卡死 → 超时。

### B.3 B 站修复方案: 改用 LM Studio 本地模型 (✅)

**思路**: B 站有 LM Studio 运行在 localhost:1234，加载了 10+ 个本地模型。配置 opencode 使用 LM Studio 作为 provider，无需代理。

**Step 1: 配置 opencode provider**

写入 `~/.config/opencode/opencode.jsonc` (备份原配置为 `.bak`):
```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "lm-studio-local": {
      "name": "LM Studio Local",
      "npm": "@ai-sdk/openai-compatible",
      "options": { "baseURL": "http://localhost:1234/v1" },
      "models": {
        "gpt-oss-120b-fable-5-distilled": { "name": "GPT-OSS-120B-Fable5" }
      }
    }
  }
}
```

**Step 2: 验证 ping**
```bash
ssh -t scott-lau@scott-lau-GTR-Pro.local \
  "cd /tmp/oc_codetest && timeout 90 ~/.opencode/bin/opencode run --auto \
   -m lm-studio-local/gpt-oss-120b-fable-5-distilled 'Reply with exactly: B_LM_PONG'"
```

**输出**: `B_LM_PONG` ✅ (无需代理，直接调用本地 LM Studio)

**Step 3: B 站可用模型** (LM Studio /v1/models 返回):
- `gpt-oss-120b-fable-5-distilled` (主推，120B 蒸馏版)
- `deepseek-v4-flash`
- `qwen3.6-27b-mtp`
- `qwen3-coder-next`
- `oprover-32b`
- `minimax/minimax-m2.7`
- `qwen/qwen3-coder-30b`
- `leanstral-2603`
- `nvidia/nemotron-3-nano-4b`
- `text-embedding-all-minilm-l6-v2-embedding`

### B.4 B 站 vs A 站工作模式对比

| 维度 | A 站 | B 站 |
|---|---|---|
| opencode 版本 | 1.18.8 (/snap/bin/) | 1.18.9 (~/.opencode/bin/) |
| 模型来源 | opencode Zen 远程免费模型 | LM Studio 本地模型 |
| 代理需求 | ✅ 必须 (mihomo 127.0.0.1:7890) | ❌ 不需要 |
| 模型选择 | `opencode/deepseek-v4-flash-free` | `lm-studio-local/gpt-oss-120b-fable-5-distilled` |
| 网络依赖 | 强 (代理+opencode.ai) | 弱 (仅 localhost:1234) |
| 推理速度 | 快 (云端 GPU) | 慢 (本地 AMD 395 AI Max) |
| 模型质量 | DeepSeek V4 Flash | GPT-OSS 120B Fable5 蒸馏 |
| 适用场景 | 快速原型/简单任务 | 复杂推理/隐私敏感 |

### B.5 B 站标准调用模板 (修订)

```bash
# B 站 (LM Studio 本地模型, 无需代理)
ssh -t scott-lau@scott-lau-GTR-Pro.local \
  "cd /tmp/<task_name> && \
   timeout <max_seconds> ~/.opencode/bin/opencode run --auto \
   -m lm-studio-local/gpt-oss-120b-fable-5-distilled \
   '<task_prompt>'"
```

### B.6 agent 模式 vs 裸 LLM 模式对比 (基于 A/B 站实测)

| 维度 | 裸 LLM (call_llm.py) | opencode agent A 站 | opencode agent B 站 |
|---|---|---|---|
| 模型 | qwen3-coder / gpt-oss / fable5 / nemotron | opencode/deepseek-v4-flash-free | lm-studio-local/gpt-oss-120b-fable-5-distilled |
| 测试通过率 | 61.5%~85.7% (4 模型平均 ~71%) | **100% (16/16)** | **78.6% (11/14)** |
| 单点 bug 命运 | 永久存在 | agent 自修复 | 部分修复，逆CDF未收敛 |
| 修复迭代次数 | 0 (一次性生成) | 多轮 (3 次 bug 全部修复) | 5+ 轮 (CDF 修复, 逆CDF 失败) |
| 总执行时间 | ~30 秒/模型 | ~10 分钟 | 30 分钟 (timeout) |
| 输出形态 | markdown 文本 | 实际可编译的 C++ 项目 | 实际可编译的 C++ 项目 |
| 人工介入 | 需手动提取代码+编译+测试 | 零介入 | 零介入 |
| 跨平台验证 | N/A | ✅ GCC + MSVC 均通过 | ✅ GCC + MSVC 均通过 |

### B.7 B 站最终测试结果 (主控站 MSVC 本地编译验证)

**distribution 测试 (5/8 通过)**:
- ✅ DistributionTest.CdfBoundary
- ❌ DistributionTest.CdfMonotonicity (CDF 非单调)
- ❌ DistributionTest.InvCdfRoundTrip (逆CDF 不满足 round-trip)
- ✅ DistributionTest.InvCdfExceptions
- ✅ DistributionTest.CdfBaselineValues (agent 修复了 Abramowitz-Stegun 近似)
- ❌ DistributionTest.InvCdfBaselineValues (逆CDF 完全错误: inv(0.95)=-0.003 vs 期望 1.645)
- ✅ 其他 2 个测试通过

**BSM 测试 (6/6 通过)** ✅:
- ✅ BSMTest.BaselineValues
- ✅ BSMTest.PutCallParity
- ✅ BSMTest.BoundaryConditions
- ✅ BSMTest.ParameterValidation
- ✅ BSMTest.DeltaRange
- ✅ BSMTest.VegaNonNegative

### B.8 关键发现: gpt-oss 运算符优先级盲点确认

**memory 中的 lesson 完全应验**:
> gpt-oss 模型家族存在系统性运算符优先级盲点，逆 CDF 实现缺少外层括号导致计算错误

**B 站 agent 修复轨迹**:
1. 初始代码: Acklam 算法常数多项式缺少外层右括号 → 编译失败
2. 第一次修复: agent 加左括号但数量不对 → 仍编译失败
3. 第二次修复: 删除部分代码 → 编译成功但 inv_normal_cdf(0.95) 返回 -0.003 (期望 1.645)
4. 后续 5+ 轮迭代: agent 反复尝试修复逆 CDF 但每次都引入新的括号错误
5. 30 分钟超时: agent 未能收敛到正确的逆 CDF 实现

**对比 A 站 (deepseek-v4-flash-free)**:
- A 站 agent 同样遇到逆 CDF 括号问题
- A 站 agent 通过 Newton 精炼步骤绕过了 Acklam 算法的精度问题
- A 站 agent 最终用 `std::erfc` 替换 CDF 实现，消除了系统性偏差

**结论**:
- agent 模式能修复**普通** bug (编译错误、CDF 精度)
- agent 模式**无法修复模型系统性盲点** (gpt-oss 的运算符优先级)
- 对于 gpt-oss 模型，应在 prompt 中**显式标注括号结构**或**改用 nemotron 模型**

### B.9 改进建议

1. **prompt 工程**: 在 TASK_PROMPT.md 中对逆 CDF 算法添加显式括号标注:
   ```
   注意: Acklam 算法的多项式必须使用正确的括号嵌套:
   x = (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]);
   每个左括号必须有对应的右括号。
   ```
2. **模型选择**: 数值密集型任务（distribution, rng, 特殊函数）优先使用 nemotron-3-super 或 deepseek-v4-flash，避免 gpt-oss
3. **超时调整**: 本地模型 (LM Studio) 推理速度慢，timeout 从 900s 调整到 1800s+
4. **混合策略**: 用 B 站 gpt-oss 做非数值模块（BSM、portfolio、数据结构），用 A 站 deepseek-v4-flash 做数值模块

---

### B.10 重大修正: B 站无需 mihomo 代理 (2026-07-30 二次排查)

> 用户要求分析 B 站是否可以安装 mihomo 代理，排查过程中推翻了 B.2/B.3 节"必须装代理"的判断。

**触发问题**: B.2 节记录 B 站超时根因为"无 mihomo 代理 → opencode Zen 不可达"。但 B.3 节改用 LM Studio 后 B 站 gpt-oss 通过率仅 78.6%，远低于 A 站 100%。怀疑根因判断有误。

**二次排查实测**:

| 检查项 | B 站结果 | 含义 |
|---|---|---|
| `curl https://opencode.ai/zen/v1/models` | ✅ HTTP 200 | opencode Zen API **直连可达** |
| `curl https://github.com` | ✅ HTTP 200 | GitHub 直连可达 |
| `curl https://models.dev` | ❌ 超时 | models.dev 被墙 (但不影响核心功能) |
| `curl https://www.google.com` | ❌ 超时 | Google 被墙 |
| `opencode run -m opencode/deepseek-v4-flash-free 'Reply: B_DIRECT_PONG'` (无代理) | ✅ `B_DIRECT_PONG` | **opencode Zen 免费模型直接可用** |

**真正的根因 (推翻 B.2)**:
- B 站**从未需要 mihomo 代理**。opencode.ai 在 B 站直连可达 (HTTP 200)。
- 之前 B 站任务超时的真正原因: **文档误导** — 基于错误记录的"B 站 mihomo: 127.0.0.1:7890"，我在命令中加了 `export http_proxy=http://127.0.0.1:7890`，但 B 站 7890 端口无服务 → opencode 所有 HTTP 请求被路由到死端口 → 卡死 → 超时。
- **教训**: 排查网络问题时，应先 `curl` 直连测试目标 API，而非基于文档假设必须走代理。A 站需要代理是因为其网络环境不同 (可能 ISP 或路由策略差异)，不能外推到 B 站。

**B 站 vs A 站网络环境对比**:

| 维度 | A 站 (scott-lau-NEX) | B 站 (scott-lau-GTR-Pro) |
|---|---|---|
| opencode.ai 直连 | ❌ 需代理 | ✅ 直连可达 |
| models.dev | ❌ 被墙 | ❌ 被墙 (不影响) |
| mihomo 服务 | ✅ `/root/clashctl/bin/mihomo` (systemd) | ❌ 未安装 |
| 代理端口 7890 | ✅ LISTEN | ❌ 无服务 |
| opencode Zen 可用方式 | 必须设 `http_proxy` | **直连，禁用代理** |

**B 站正确工作模式 (修订)**:

```bash
# B 站正确调用方式 (opencode Zen 直连, 无代理, 无 LM Studio)
ssh -t scott-lau@scott-lau-GTR-Pro.local \
  "unset http_proxy https_proxy; \
   cd /tmp/<task_name> && \
   timeout 900 ~/.opencode/bin/opencode run --auto \
   -m opencode/deepseek-v4-flash-free '<prompt>'"
```

**关键差异**: 与 A 站模板相比，B 站必须 `unset http_proxy https_proxy` (而非 `export http_proxy=...`)，否则 opencode 会尝试走不存在的代理 → 卡死。

**是否安装 mihomo 的结论**: **不安装**。
1. **不必要**: B 站直连 opencode.ai 可用，opencode Zen 免费模型直接可用
2. **更优方案**: B 站用 `opencode/deepseek-v4-flash-free` (远程免费, 云端 GPU, 无 gpt-oss 运算符盲点)，优于 LM Studio 本地 gpt-oss
3. **装 mihomo 的唯一场景**: 未来 B 站 agent 需访问 google scholar / arxiv 镜像 / google CDN 等被墙资源时，可 `scp` A 站 `/home/scott-lau/clash-for-linux-install/` 到 B 站安装

**B 站可用性最终确认**:
- ✅ opencode Zen 远程免费模型 (deepseek-v4-flash-free 等) — 直连可用，推荐首选
- ✅ LM Studio 本地模型 (gpt-oss-120b-fable-5-distilled 等) — localhost:1234 可用，但有 gpt-oss 盲点
- ❌ mihomo 代理 — 未安装，不需要

### B.11 B 站修正版验证结果 (2026-07-30 17:10)

> 用 B.10 修正后的方式 (opencode Zen 直连, 无代理, 无 LM Studio) 重跑 B 站编码任务。

**任务参数**:
- 模型: `opencode/deepseek-v4-flash-free` (与 A 站相同)
- 超时: 1200 秒 (20 分钟)
- 配置: `~/.config/opencode/opencode.jsonc` 恢复为默认 (`{"$schema":"https://opencode.ai/config.json"}`)
- 命令: `ssh -t ... "unset http_proxy https_proxy; ... opencode run --auto -m opencode/deepseek-v4-flash-free ..."`

**执行结果**:
- ✅ exit=0 (正常退出，未超时)
- ✅ 总耗时 ~5 分钟 (16:47 启动 → 16:52 结束)
- ✅ **16/16 测试全部通过 (100%)**

**跨平台验证 (主控站 MSVC 编译)**:
- ✅ test_distribution: 9/9 通过
- ✅ test_bsm: 7/7 通过
- ✅ 总计 16/16 (100%)

**agent 修复轨迹**:
1. 首次编译 → 13/16 通过 (81%), 3 个精度问题:
   - DistributionTest.InvCdfRoundTrip (逆CDF精度)
   - DistributionTest.InvCdfReferenceValues (逆CDF精度)
   - BsmTest.ReferenceValues (BSM误差 4.7e-6, 略超 1e-6 阈值)
2. agent 尝试 WebFetch 查找 Acklam 系数 (超时) → Web Search (并行搜索)
3. agent 修复逆 CDF: Acklam 算法 + Halley 精炼步骤
4. agent 修复 CDF: 改用 `std::erfc` (机器精度)
5. 最终: 16/16 全通过

**三版对比 (A 站 / B 站 v1 LM Studio / B 站 v2 Zen 直连)**:

| 维度 | A 站 | B 站 v1 (LM Studio) | B 站 v2 (Zen 直连) |
|---|---|---|---|
| 模型 | opencode/deepseek-v4-flash-free | lm-studio-local/gpt-oss-120b-fable-5-distilled | opencode/deepseek-v4-flash-free |
| 代理 | ✅ mihomo (必须) | ❌ 无 (LM Studio 本地) | ❌ 无 (直连, 必须unset) |
| 测试通过率 | **100% (16/16)** | 78.6% (11/14) | **100% (16/16)** |
| 跨平台验证 | ✅ GCC+MSVC | ✅ GCC+MSVC | ✅ GCC+MSVC |
| 总耗时 | ~10 分钟 | 30 分钟 (timeout) | ~5 分钟 |
| 逆CDF修复 | ✅ Newton 精炼 | ❌ gpt-oss 盲点未修复 | ✅ Halley 精炼 |
| exit code | 0 | 124 (timeout) | 0 |

**结论**:
1. **B 站 opencode Zen 直连完全可用**, 通过率与 A 站一致 (100%)
2. **deepseek-v4-flash-free 模型质量稳定**, 在 A/B 两站表现一致
3. **之前 B 站 78.6% 低通过率是 LM Studio gpt-oss 运算符盲点所致**, 非 B 站环境问题
4. **B 站优于 A 站**: 无需代理维护, 网络配置更简单, 推理速度更快 (~5分钟 vs ~10分钟)
5. **A/B 站可完全对等使用**, 实现真正的多 Agent 并行开发

### B.12 B 站 qwen3-coder-next 测试 (2026-07-30 17:30)

> 用户要求测试 B 站 LM Studio 已加载的 qwen3-coder-next 模型 (因 opencode 免费模型存在额度限制)。

**任务参数**:
- 模型: `lm-studio-local/qwen3-coder-next`
- 超时: 1800 秒 (30 分钟, 本地模型)
- 配置: `~/.config/opencode/opencode.jsonc` 添加 `lm-studio-local` provider
- 命令: `ssh -t ... "unset http_proxy https_proxy; ... opencode run --auto -m lm-studio-local/qwen3-coder-next ..."`

**执行结果**:
- ❌ agent 陷入死循环, 被手动停止 (未自然退出)
- ❌ 总耗时 ~25 分钟 (17:02 启动 → 17:27 手动停止)
- ❌ **MSVC 编译直接失败** (语法错误: Acklam 括号缺失未修复)

**agent 行为分析**:
1. 首次编译: 10 个测试中 6 个通过 (60%), 4 个失败:
   - DistributionTest.NormalCdf
   - DistributionTest.InvNormalCdf
   - BsmTest.PriceWithDifferentParameters
   - BsmTest.Vega
2. agent 识别出 Acklam 算法括号问题, 开始用 `od -c` / `sed -n` / `xxd` 字符级调试
3. **陷入死循环**: 反复执行 `cat ... | sed -n '54p' | grep "1.0));"` 共 **273 次**, 每次输出 `(no output)`, 无任何修复动作
4. 25 分钟后仍未突破, 被手动停止

**死循环根因分析**:
- qwen3-coder-next 模型在 agent 模式下存在**重复命令循环**倾向
- 模型无法从"grep 无输出"这一反馈中推断出应改用其他方法 (如直接 write 替换整行)
- 与 gpt-oss 的"运算符盲点"不同, qwen3-coder-next 是"工具调用死循环" — 能识别问题但无法切换策略

**跨平台验证 (主控站 MSVC)**:
- ❌ 编译失败: `error C2059: syntax error: ';'` (distribution.hpp:63, Acklam 括号缺失)
- 未进入测试阶段

**四版对比 (A 站 / B 站 v1 / B 站 v2 / B 站 qwen)**:

| 维度 | A 站 | B 站 v1 (LM Studio) | B 站 v2 (Zen 直连) | B 站 qwen (LM Studio) |
|---|---|---|---|---|
| 模型 | opencode/deepseek-v4-flash-free | lm-studio-local/gpt-oss-120b-fable-5-distilled | opencode/deepseek-v4-flash-free | lm-studio-local/qwen3-coder-next |
| 代理 | ✅ mihomo (必须) | ❌ 无 (本地) | ❌ 无 (直连, unset) | ❌ 无 (本地) |
| 测试通过率 | **100% (16/16)** | 78.6% (11/14) | **100% (16/16)** | **0% (编译失败)** |
| 远程 GCC 首次通过率 | N/A | N/A | 81% (13/16) | 60% (6/10) |
| 跨平台 MSVC 验证 | ✅ 通过 | ✅ 通过 | ✅ 通过 | ❌ 编译失败 |
| 总耗时 | ~10 分钟 | 30 分钟 (timeout) | ~5 分钟 | ~25 分钟 (手动停止) |
| agent 行为 | 正常收敛 | 部分修复 | 正常收敛 | **死循环 (273次grep)** |
| exit code | 0 | 124 (timeout) | 0 | N/A (手动停止) |

**结论**:
1. **qwen3-coder-next 在 opencode agent 模式下表现最差** — 陷入工具调用死循环, 无法修复语法错误
2. **LM Studio 本地模型整体不如 opencode Zen 远程模型**:
   - gpt-oss-120b-fable-5-distilled: 78.6% (运算符盲点)
   - qwen3-coder-next: 0% (死循环)
   - deepseek-v4-flash-free (Zen): 100%
3. **opencode Zen 免费模型额度限制下的推荐策略**:
   - 首选: `opencode/deepseek-v4-flash-free` (Zen, 100% 通过率)
   - 额度耗尽时: `lm-studio-local/gpt-oss-120b-fable-5-distilled` (仅非数值模块, 避开运算符盲点)
   - **不推荐**: `lm-studio-local/qwen3-coder-next` (死循环风险)
4. **agent 死循环是新型失败模式**: 与 gpt-oss 的"模型盲点"不同, qwen3-coder-next 能识别问题但无法切换策略, 陷入重复工具调用。opencode 目前无内置的循环检测/打断机制, 需人工监控

### B.13 B 站 qwen3.5-122b-uncensored 测试 (2026-07-30 18:15)

> 用户要求测试 B 站 LM Studio 的 qwen3.5-122b-a10b-uncensored-hauhaucs-aggressive 模型 (122B MoE A10B uncensored 微调)。

**任务参数**:
- 模型: `lm-studio-local/qwen3.5-122b-a10b-uncensored-hauhaucs-aggressive`
- 超时: 1800 秒 (30 分钟)
- 配置: `~/.config/opencode/opencode.jsonc` 添加 `lm-studio-local` provider
- ping 测试: ✅ 通过 (输出 QWEN35_PONG)

**执行结果**:
- ❌ 超时退出 (exit=124, 30 分钟)
- ✅ MSVC 编译成功 (无语法错误, 优于 qwen3-coder-next)
- ⚠️ **14/17 测试通过 (82.4%)**:
  - test_bsm: 7/8 通过 (BenchmarkValues 失败, BS 价格误差超 1e-6)
  - test_distribution: 7/9 通过 (InvCdfRoundTrip + InvCdfBenchmarkValues 失败)

**agent 行为分析**:
1. 首次创建项目 → mkdir /project 权限错误 → 自动修正到 /tmp/oc_codetest/project (良好的自适应)
2. 首次编译测试 → 部分失败 (逆CDF精度问题)
3. agent 识别出 Acklam 算法系数错误, 用 Python 验证系数
4. **Python 验证时犯低级错误**: 把 C++ 注释 `//` 写进 Python 文件 → SyntaxError → 验证脚本无法运行
5. agent 尝试多种系数组合 (ascending/descending order), 但始终未找到正确系数
6. 30 分钟超时退出

**失败根因**:
- **Acklam 系数错误**: agent 用的系数 `a[0]=-1.98669330795061` 是错的, 正确值应为 `a[0]=-3.969683028665376e+01`
- **跨语言语法混淆**: agent 在 Python 脚本中写 C++ 注释 `//`, 导致 SyntaxError, 浪费时间
- **未使用 std::erfc**: CDF 仍用 Abramowitz-Stegun 近似, 精度不如 std::erfc (机器精度)
- **未添加 Newton/Halley 精炼**: 逆CDF 仅用 Acklam 多项式, 无精炼步骤

**五版对比 (A 站 / B 站 v1 / B 站 v2 / B 站 qwen / B 站 qwen35)**:

| 维度 | A 站 | B 站 v1 | B 站 v2 | B 站 qwen | B 站 qwen35 |
|---|---|---|---|---|---|
| 模型 | deepseek-v4-flash | gpt-oss-120b-fable5 | deepseek-v4-flash | qwen3-coder-next | qwen3.5-122b-uncensored |
| 来源 | Zen 远程 | LM 本地 | Zen 远程 | LM 本地 | LM 本地 |
| 通过率 | **100% (16/16)** | 78.6% (11/14) | **100% (16/16)** | 0% (编译失败) | 82.4% (14/17) |
| MSVC 编译 | ✅ | ✅ | ✅ | ❌ | ✅ |
| 耗时 | ~10min | 30min (timeout) | ~5min | ~25min (停止) | 30min (timeout) |
| 逆CDF修复 | ✅ Halley | ❌ 盲点 | ✅ Halley | ❌ 死循环 | ❌ 系数错误 |
| agent 行为 | 正常收敛 | 部分修复 | 正常收敛 | 死循环 | 跨语言语法混淆 |

**结论**:
1. **qwen3.5-122b-uncensored 排名第二** (82.4%), 优于 qwen3-coder-next (0%) 和 gpt-oss (78.6%), 但远低于 deepseek-v4-flash (100%)
2. **122B MoE 参数量未带来质量优势**: A10B 激活参数 + uncensored 微调, 在数值算法实现上仍不如 deepseek-v4-flash
3. **跨语言语法混淆是新型失败模式**: agent 在 Python 验证脚本中写 C++ 注释 `//`, 导致 SyntaxError — 表明模型对语言边界不敏感
4. **Acklam 系数是 agent 模式的共性难点**: 除 deepseek-v4-flash 外, 所有模型都未能正确实现 Acklam 算法 (系数错误/括号错误/死循环)
5. **LM Studio 本地模型整体不如 Zen 远程模型**: 4 次本地模型测试 (gpt-oss/qwen3-coder/qwen35) 最高仅 82.4%, 而 Zen 远程 deepseek-v4-flash 两次均 100%

**B 站 LM Studio 本地模型推荐排序 (2026-07-30 最终)**:
1. `qwen3.5-122b-a10b-uncensored-hauhaucs-aggressive` — 82.4%, 可用于非数值模块
2. `gpt-oss-120b-fable-5-distilled` — 78.6%, 仅非数值模块 (运算符盲点)
3. `qwen3-coder-next` — 0%, 禁用 (死循环)
4. **所有场景首选**: `opencode/deepseek-v4-flash-free` (Zen 远程, 100%)

---

## 附录 A: 直接 API 调用 vs opencode agent 调用本质差异

> 发现日期: 2026-07-30
> 背景: 4 个模型用直接 API 测试通过率 61.5%~85.7%, 所有失败都是单点 bug 无法自修复

### A.1 架构对比

```
直接调用 LM Studio API (call_llm.py):
   prompt → [LLM 生成文本] → 返回文本 → 结束
   单次请求, 无状态, 无工具

opencode 间接调用 (无插件):
   prompt → [LLM 生成] → 有 tool_call?
              ↑                ├── 是: 执行工具 → 结果回灌 LLM → 重新生成
              │                └── 否: 返回最终文本
              └──── 多轮循环, 直到完成或超时
```

### A.2 能力矩阵

| 维度 | 直接 API (call_llm.py) | opencode (无插件) |
|---|---|---|
| 调用模式 | 单轮请求-响应 | 多轮 agent 循环 |
| 文件读写 | ❌ | ✅ 内置 read/write_file |
| Shell 执行 | ❌ | ✅ 内置 bash (可跑 cmake/g++/ctest) |
| 编译测试 | ❌ 主控站手动 | ✅ agent 自主 cmake→build→test |
| 错误自修复 | ❌ 无法 | ✅ 读编译错误→改代码→重试 |
| 上下文记忆 | ❌ 无状态 | ✅ 会话内多轮记忆 |
| 工具调用 | ❌ | ✅ tool calling 协议 |
| 迭代收敛 | ❌ 一次性 | ✅ 直到测试通过或超时 |
| 输出形态 | 纯文本 markdown | 实际文件 + 命令执行结果 + 文本 |

### A.3 opencode 内置工具 (无需插件)

opencode 出厂自带这些工具, 不是插件提供的:
1. 文件工具: read, write, ls, grep, glob
2. Shell 工具: bash/exec (执行任意命令)
3. 任务工具: task (派生子 agent)
4. 诊断工具: diagnostics (LSP 诊断, 默认禁用可启用)

插件是**扩展**而非 agent 能力的**来源**:
```
opencode 能力 = 内置 agent loop + 内置工具 (文件/shell)  ← 核心, 无插件即有
             + 插件 (MCP/Git/LSP/Web 搜索/自定义)        ← 增强, 可选
```

### A.4 实测对比 (基于 4 模型直接 API 试验)

之前 call_llm.py 模式的失败都是**单点 bug 无法自修复**:

| 模型 | 单点 bug | 直接 API 通过率 | opencode agent 预期 |
|---|---|---|---|
| qwen3-coder | CDF 常数 p=0.3275911 错 | 61.5% | agent 编译后测试 normal_cdf(0.0)≠0.5 → 读错误 → 修复常数 |
| gpt-oss-120b | 逆 CDF 缺括号 | 66.7% | agent 运行测试 inv_normal_cdf(0.5)=1.0 → 读失败 → 加括号 |
| fable5 | 同上括号 bug | 71.4% | 同上 |
| nemotron | M_PI + gtest.h | 85.7% | agent 编译失败 → 读 MSVC 错误 → 修复 |

**关键洞察**: 这 4 个 bug 全是**编译期或测试期可发现**的。直接 API 模式下模型"生成完就走了"无法修复; opencode agent 模式下 agent 会自己编译、读错误、修复、再编译, 直到通过。

### A.5 一句话总结

直接 API 是"请人代写作业", opencode agent 是"雇了个能自己查资料、写代码、编译、跑测试、改 bug 的实习生" — 即使这个实习生没装任何额外工具插件, 他自带的"手(文件操作)和脚(shell 执行)"已经足以完成闭环。
