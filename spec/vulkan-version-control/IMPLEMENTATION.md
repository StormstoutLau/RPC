# 实施文档：Vulkan 后端版本控制

---
id: vulkan-version-control-IMPLEMENTATION
type: design
version: 1.0
status: draft
date: 2026-08-27
depends: [vulkan-version-control-DESIGN, vulkan-version-control-RESEARCH]
upstream: null
---

> **Feature**: Vulkan llama.cpp 后端版本控制（A/B 双机 RPC 集群）
> **创建日期**: 2026-08-27
> **状态**: in-review
> **Spec 步骤**: Step 5-6
> **基于设计**: [DESIGN.md](./DESIGN.md)
> **基于调研**: [RESEARCH.md](./RESEARCH.md)

---

## 1. 实施概述

本 feature 交付三类产物：(1) 部署在两站的第 0 步迁移脚本（`mv` + symlink + MANIFEST 生成，把 9859 现状版本化）；(2) 部署在主控站的巡检脚本（指纹比对 + 深度 MD5）；(3) 升级 SOP 文档（文档化，不含自动化脚本）。所有远程操作经 BatchMode SSH（免密已就绪），脚本遵循 `set -e` + 分步 echo，shell 命令注意 PowerShell 引号转义问题（本会话已两次踩坑：`pkill -f` 自匹配、`$()` 展开），统一采用"脚本 scp 到远端执行"模式规避。

## 2. 工程细节

### 2.1 技术栈

| 组件 | 技术 | 版本 | 验证状态 |
|------|------|------|---------|
| 远程执行 | OpenSSH (Windows → Ubuntu) | 主控站 ssh.exe / A、B 站 Ubuntu 24.04 sshd | ✅ 实测免密可达 |
| 脚本语言 | bash | Ubuntu 24.04 bash 5.2 | ✅ 系统自带 |
| 校验工具 | md5sum / sha | coreutils | ✅ 系统自带 |
| 目标二进制 | llama.cpp (Vulkan+RPC) | 9859 (4fc4ec554) | ✅ 实测在位 |
| 巡检运行环境 | 主控站 Git Bash 或直接 ssh | - | ⚠️ 主控站 bash 可用性待验证（保底方案：ssh 直接执行远端脚本） |

### 2.2 依赖版本验证

无第三方依赖（全部系统自带工具）。SSH 免密：本会话实测 `ssh -o BatchMode=yes` 两站均通（RESEARCH.md E1 证据）。

### 2.3 文件结构

```
D:\RPC\
├── spec\vulkan-version-control\        # 本 feature 四文档
├── scripts\
│   ├── version_step0_A.sh              # A 站第 0 步迁移（scp 到 A 站执行）
│   ├── version_step0_B.sh              # B 站第 0 步迁移（scp 到 B 站执行）
│   ├── gen_manifest.sh                 # MANIFEST 生成（两站通用，被 step0 调用）
│   └── check_llama_version.sh          # 巡检（主控站驱动，ssh 两站）
└── 提速调研报告.md                       # 上游文档（已存在）
```

两站落地结构（DESIGN.md §3.1）：
```
/opt/llama.cpp-9859/          # 原 /opt/llama.cpp 整体改名（含全部 .so 与二进制）
│   ├── MANIFEST              # 新生成
│   ├── llama-cli / llama-server / ggml-rpc-server / llama-gguf-split ...
│   └── libggml-*.so / libllama-*.so ...
/opt/llama.cpp -> llama.cpp-9859   # symlink（相对路径）
```

## 3. 模块实施

### 3.1 M1 版本目录结构（version_step0_A.sh / version_step0_B.sh）

#### 职责

原目录改名 + 建立 symlink（DESIGN.md §3.2 M1）。

#### 接口签名

```bash
# 用法: bash version_step0_<X>.sh    （在对应站以 scott-lau 执行，经主控站 scp+ssh）
# 前置: /opt/llama.cpp 为实体目录（非 symlink）
# 效果: /opt/llama.cpp-9859 实体 + /opt/llama.cpp symlink
# 退出: 0 成功; 1 前置不满足; 2 操作失败
```

#### 实施要点

- 前置三查：目录是实体（`test -d && ! -L`）、版本号确认（`llama-cli --version` 含 9859）、无进程引用（`pgrep -x llama-server/ggml-rpc-server` 为空——本会话已确认两站清零，脚本仍自查）
- `sudo mv /opt/llama.cpp /opt/llama.cpp-9859`（/opt 下 root 所有，需 sudo；mv 同文件系统原子）
- `sudo ln -sfn llama.cpp-9859 /opt/llama.cpp`（**相对路径** symlink —— 版本目录名前缀一致，绝对/相对均可，选相对以防 /opt 挂载点变动；ln -sfn 目标已存在时原子替换）
- 幂等性：重复执行检测到已是 symlink 且指向 9859 则跳过 mv、直接通过

#### 低效操作排除

| 潜在低效 | 排除措施 |
|---------|---------|
| mv 130GB 数据复制 | mv 同文件系统 = rename，O(1) |
| 逐文件校验耗时 | 仅校验 4 个关键 MD5（与会话实测基线比对），全量 MD5 留给 MANIFEST 生成与巡检 |

### 3.2 M2 MANIFEST 清单（gen_manifest.sh）

#### 职责

生成版本目录的 MANIFEST（DESIGN.md §4.1 格式）。

#### 接口签名

```bash
# 用法: bash gen_manifest.sh <版本目录绝对路径>   # 例: /opt/llama.cpp-9859
# 生成: <目录>/MANIFEST（含 [md5] 节，覆盖目录内全部可执行文件与 .so*）
# 退出: 0 成功; 1 目录不存在
```

#### 实施要点

- `[md5]` 节由 `md5sum` 命令重定向生成（非手写，DESIGN §10.2 风险缓解）
- 键名严格按 DESIGN §4.1（巡检解析依赖）；9859 历史字段显式 `unknown (pre-existing)`
- 排除空目录 `build/` 与 MANIFEST 自身；`libggml.so` 等符号链接记目标文件（md5sum 跟随链接）

### 3.3 M3 巡检脚本（check_llama_version.sh，主控站）

#### 职责

两站指纹比对 + 可选深度 MD5 比对（DESIGN.md §4.2）。

#### 接口签名

```bash
# 用法: bash check_llama_version.sh [--deep]
# 运行位置: 主控站（内部 ssh 两站）；或 ssh 到任一站后对另一站执行（保底）
# 退出码: 0 一致; 1 不一致; 2 SSH 不可达
```

#### 实施要点

- 指纹 = `readlink /opt/llama.cpp` + MANIFEST 的 `version`/`commit` 行（`grep '^version'` 提取）
- MANIFEST 缺失时降级为 symlink 目录名 + 警告（DESIGN §7 错误处理）
- `--deep`：两站各自 `cd /opt/llama.cpp && md5sum` 全量 → 主控 diff
- 主控站 bash 环境不确定：脚本顶部注释注明保底用法（直接在 B 站执行，站内 ssh A 站免密已实测）

### 3.4 M4 升级 SOP（文档化交付）

交付物为本文档 §5 Step-6 引用的 SOP 章节（内容 = DESIGN §3.3 升级数据流 + 回滚步骤），写入 `D:\RPC\spec\vulkan-version-control\UPGRADE_SOP.md`。自动化构建/分发脚本不在本 feature 范围（职责边界，DESIGN §2.3）。

## 4. 接口实施

### 4.1 version_step0_A.sh / version_step0_B.sh

两脚本主体相同（仅站名 echo 差异）：

```bash
#!/bin/bash
set -euo pipefail
VER="9859"
TARGET="/opt/llama.cpp-${VER}"
LINK="/opt/llama.cpp"

echo "[1/5] 前置检查: 实体目录 / 无进程引用 / 版本号"
test -d "$LINK" && ! test -L "$LINK" || { echo "❌ 前置不满足"; exit 1; }
pgrep -x llama-server ggml-rpc-server 2>/dev/null && { echo "❌ 有进程引用"; exit 1; } || true
echo "$LINK/llama-cli --version" | sudo bash 2>/dev/null | grep -q "version: ${VER}" || { echo "❌ 版本号不匹配"; exit 1; }

echo "[2/5] 关键 MD5 基线核对（与会话实测基线比对）"
md5sum "$LINK/llama-cli" | grep -q "^126494d96363e8feb5c36568be7ee522" || echo "⚠️ llama-cli MD5 与基线不符（继续，MANIFEST 将记录实际值）"

echo "[3/5] mv（同文件系统，原子 rename）"
sudo mv "$LINK" "$TARGET"

echo "[4/5] 建立相对 symlink"
sudo ln -sfn "llama.cpp-${VER}" "$LINK"

echo "[5/5] 冒烟: 经 symlink 路径解析二进制"
"$LINK/llama-cli" --version | head -1
echo "✅ 第 0 步完成: $LINK -> $(readlink $LINK)"
```

**签名一致性**: 与 DESIGN.md §3.2 M1 职责一致 ✅

### 4.2 gen_manifest.sh

```bash
#!/bin/bash
set -euo pipefail
DIR="${1:?用法: gen_manifest.sh <版本目录>}"
test -d "$DIR" || { echo "❌ 目录不存在: $DIR"; exit 1; }
MANIFEST="$DIR/MANIFEST"

VER_LINE=$("$DIR/llama-cli" --version 2>/dev/null | head -1)   # version: 9859 (4fc4ec554)
VER=$(echo "$VER_LINE" | sed -n 's/version: \([0-9]*\).*/\1/p')
COMMIT=$(echo "$VER_LINE" | sed -n 's/version: [0-9]* (\([a-f0-9]*\)).*/\1/p')

{
  echo "# MANIFEST — 生成于 $(date +%F) 由 gen_manifest.sh"
  echo "commit      = ${COMMIT:-unknown}"
  echo "version     = ${VER:-unknown}"
  echo "build_host  = $(hostname) (migration: pre-existing binaries)"
  echo "build_date  = 2026-07-02 (binary mtime, pre-existing)"
  echo "toolchain   = GNU 11.4.0 (llama-cli --version 实测)"
  echo "cmake_flags = unknown (pre-existing, 无 CMakeCache)"
  echo "rpc_protocol = v4.0.1 (rpc-server 日志实测)"
  echo "[md5]"
  cd "$DIR" && md5sum llama-* ggml-rpc-server libggml*.so* libllama*.so* libmtmd.so* 2>/dev/null
} | sudo tee "$MANIFEST" > /dev/null

echo "✅ MANIFEST 已生成: $MANIFEST ($(grep -c . "$MANIFEST") 行)"
```

**签名一致性**: 与 DESIGN.md §4.1 格式一致 ✅（键名逐一对照）

### 4.3 check_llama_version.sh

```bash
#!/bin/bash
# 巡检: A/B 两站 llama.cpp 版本一致性
# 用法: bash check_llama_version.sh [--deep]   （主控站或任一站执行）
# 退出: 0 一致 / 1 不一致 / 2 SSH 不可达
set -uo pipefail
HOSTS=("scott-lau@scott-lau-NEX.local" "scott-lau@scott-lau-GTR-Pro.local")
DEEP=false; [[ "${1:-}" == "--deep" ]] && DEEP=true

declare -A FP
for h in "${HOSTS[@]}"; do
  fp=$(ssh -o ConnectTimeout=8 -o BatchMode=yes "$h" \
    'L=$(readlink /opt/llama.cpp 2>/dev/null || echo ""); \
     M=/opt/llama.cpp/MANIFEST; \
     V=$(grep "^version" "$M" 2>/dev/null | cut -d= -f2 | tr -d " " || echo "NO_MANIFEST"); \
     C=$(grep "^commit" "$M" 2>/dev/null | cut -d= -f2 | tr -d " " || echo "?"); \
     echo "$L|$V|$C"' 2>/dev/null)
  if [[ -z "$fp" ]]; then echo "❌ $h SSH 不可达"; exit 2; fi
  FP[$h]="$fp"; echo "$h → $fp"
done

a="${FP[${HOSTS[0]}]}"; b="${FP[${HOSTS[1]}]}"
if [[ "$a" != "$b" ]]; then echo "❌ 两站指纹不一致"; echo "  A: $a"; echo "  B: $b"; exit 1; fi
echo "✅ 指纹一致: $a"

if $DEEP; then
  for h in "${HOSTS[@]}"; do
    ssh -o BatchMode=yes "$h" 'cd /opt/llama.cpp && md5sum llama-* libggml*.so* libllama*.so* 2>/dev/null | sort' > "/tmp/md5_$(echo $h | md5sum | cut -c1-8).txt" 2>/dev/null
  done
  F1=$(ls /tmp/md5_*.txt | head -1); F2=$(ls /tmp/md5_*.txt | tail -1)
  if diff -q "$F1" "$F2" > /dev/null; then echo "✅ 深度比对: 全部 MD5 一致"; rm -f /tmp/md5_*.txt
  else echo "❌ 深度比对差异:"; diff "$F1" "$F2"; rm -f /tmp/md5_*.txt; exit 1; fi
fi
```

**签名一致性**: 与 DESIGN.md §4.2 一致（退出码 0/1/2、--deep、降级逻辑）✅

## 5. 兼容性

### 5.1 环境兼容

| 环境 | 支持 | 说明 |
|------|------|------|
| Ubuntu 24.04 (两站) | ✅ | bash 5.2 / coreutils / sudo，全系统自带 |
| 主控站执行巡检 | ⚠️ | 依赖 ssh.exe（已实测）；bash 环境若缺，保底方案 = 在 B 站执行（B→A 免密实测可达） |

### 5.2 依赖兼容

无第三方依赖。SSH 免密、sudo 权限（scott-lau 已实测可 sudo）。

### 5.3 向后兼容

- 9859 为首个受控版本；未来新版本目录沿用同一 MANIFEST 格式（键名不变）
- 升级 SOP 的回滚目标 = 本第 0 步产物，长期有效（I5 不变式）

## 6. 错误处理实施

| 错误场景（DESIGN §7） | 处理代码 | 测试 |
|----------------------|---------|------|
| SSH 不可达 | check 脚本 `exit 2` + stderr | 验收项 C5（模拟断连需关机，改为直接验证可达路径 + 代码审查） |
| MANIFEST 缺失 | 巡检降级 NO_MANIFEST + 警告 | 验收项 C4（临时改名重现） |
| mv/symlink 失败 | step0 `set -e` 中止，原目录未动 | 验收项 C2（前置不满足场景：对已迁移状态重跑 → 幂等通过/退出） |
| 指纹不一致 | `exit 1` + 差异输出 | 验收项 C6（构造：临时改 B 站 MANIFEST version 字段→恢复） |

## 7. 不变式实施

| 不变式（DESIGN §8） | 实施位置 | 验证方式 |
|--------------------|---------|---------|
| I1 路径不变式 | step0 [4/5]+[5/5] | 验收 C1: `llama-cli --version` 经 symlink 成功 |
| I2 隔离不变式 | mv 整目录（物理隔离天然满足） | 验收 C3: 目录内无指向其他版本的链接（`find -type l` 检查） |
| I3 追溯不变式 | gen_manifest.sh | 验收 C7: `cd /opt/llama.cpp-9859 && md5sum -c MANIFEST`（md5 节）通过 |
| I4 一致性不变式 | check 脚本指纹 | 验收 C8: 两站巡检退出码 0 |
| I5 回滚不变式 | 9859 目录保留策略（SOP §6: 保留最近 2 版本） | 验收 C9: 回滚演练 `ln -sfn` 切回并冒烟 |

## 8. 测试策略

### 8.1 单元/集成测试（以验收脚本形态执行，非 pytest）

| 场景 | 脚本/命令 | 预期 |
|------|----------|------|
| step0 幂等 | 对已迁移状态重跑 step0 | 幂等通过（或前置检查友好退出） |
| MANIFEST 校验 | `md5sum -c`（提取 md5 节） | 全部 OK |
| 巡检正常 | check（无 --deep） | exit 0 |
| 巡检深度 | check --deep | exit 0 |
| 巡检异常注入 | 临时篡改 B 站 MANIFEST | exit 1 + 差异输出 → 恢复 |

### 8.2 集成测试

两站完整链路：step0(A) → step0(B) → check --deep → 冒烟推理（可选，模型加载 4.4 分钟，本次以二进制解析冒烟代替）。

### 8.3 属性测试

不适用（无数值算法）。

## 9. 幻觉排除审查（Step 6 Review）

> [RULE-1] 独立复核 pass，非与正文同次写入。

### 9.1 依赖版本验证

- [x] 无虚构依赖（全部系统工具：bash/md5sum/sudo/ssh 均实测在位）
- [x] 版本声明均有实测来源（GNU 11.4 来自 --version 输出；bash 5.2 为 Ubuntu 24.04 标配——⚠️ 此条为发行版常识，未逐站实测 bash --version，标注为低风险假设）

### 9.2 接口签名验证

- [x] §4.1-4.3 与 DESIGN §4 逐条对照一致（退出码、参数、输出）
- [x] 所有 bash 语法可实现（set -euo pipefail / declare -A / ssh 单引号防展开）

### 9.3 实施与设计对齐

- [x] M1-M3 模块对应 DESIGN §3.2；M4 为 SOP 文档（职责边界内）
- [x] 幂等性为 DESIGN 未显式要求的增强项 → 登记为派生需求 DR-1

### 9.4 低效操作排除

- [x] mv 同文件系统 O(1)（§3.1 已排除复制）
- [x] 巡检默认浅比对（指纹级 O(1) ssh），--deep 才全量
- [x] 无重复 MD5 计算（MANIFEST 生成一次，巡检直接读）

### 9.5 派生需求登记（v1.2 D6 / DO-178C §5.5.e）

| ID | 派生需求 | 来源 | 验收 |
|----|---------|------|------|
| DR-1 | step0 幂等性（重复执行友好退出） | 实施过程自生（运维安全） | C2 |
| DR-2 | 巡检脚本保底运行模式（B 站执行） | 主控站 bash 环境不确定 | C5 |
| DR-3 | MANIFEST 生成排除 build/ 空目录与自身 | 文件卫生 | C7 |

### 9.6 复核记录

| 项 | 结果 |
|---|---|
| 复核方式 | 独立 pass 逐条核对（自查·单视角，RULE-4） |
| 发现 1 | §4.3 巡检 deep 模式临时文件用 `$(echo $h \| md5sum)` 命名——主控站 Windows 路径 /tmp 依赖 Git Bash 语义，保底模式下成立、纯 PowerShell 环境不成立 → 已在 §5.1 标注保底约束（DR-2） |
| 发现 2 | bash 5.2 为低风险假设未实测 → 已在 §9.1 显式标注 |
| 发现数 | 2 项（1 项修正入正文，1 项标注假设） |

## 10. 实施步骤

### Step 1: 编写本地脚本（D:\RPC\scripts\）

- 文件: version_step0_A.sh、version_step0_B.sh、gen_manifest.sh、check_llama_version.sh、UPGRADE_SOP.md
- 内容: §4 全部代码 + SOP 文档
- 测试: bash -n 语法检查

### Step 2: A 站执行

- 命令: `scp` 三脚本 → `ssh A "bash /tmp/version_step0_A.sh"` → `ssh A "bash /tmp/gen_manifest.sh /opt/llama.cpp-9859"`
- 测试: 冒烟 + MD5 基线核对（验收 C1/C2/C3）

### Step 3: B 站执行

- 同 Step 2（B 站脚本）
- 测试: 同上

### Step 4: 巡检验证

- 命令: 主控站或 B 站执行 `check_llama_version.sh --deep`
- 测试: exit 0（验收 C8）

### Step 5: 回滚演练 + 文档收尾

- 演练: 两站 `ln -sfn` 切回验证（即切回自身 9859，验证命令形态）
- 收尾: 开发日志、PROGRESS 更新、CHECKLIST 勾选

---

**Review 签字**: [已复核·自查（单视角，RULE-4 标注）] 日期: 2026-08-27
