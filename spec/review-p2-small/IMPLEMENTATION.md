# 实施文档：原始评审 P2 小批次（#6 / #9 / CI）

---

id: review-p2-small-IMPLEMENTATION
type: design
version: 1.0
status: draft
date: 2026-10-27
depends: [review-p2-small-DESIGN]
upstream: null

---

> **Feature**: 收掉 P2 里改动小、确定性高的三项：#6 两份遗留 systemd 单元的键段位、#9 活跃运行时身份收敛、CI（`py-tests` + `shellcheck`）。
> **创建日期**: 2026-10-27
> **状态**: draft（Step 4 设计评审已复核，记录见 §12.5；实施按 §10 顺序待启动）
> **Spec 步骤**: Step 3（IMPLEMENTATION）
> **基于设计**: [DESIGN.md](./DESIGN.md)
> **基于调研**: [P2 小批次社区外部锚点调研](../../docs/research/2026-10-27_原始评审P2小批次_社区外部锚点调研.md)
> **代码基线**: `2b9ba875`（`main`；行号为该基线快照）

---

## 1. 实施范围

| # | 交付物 | 落位 | 类型 |
|---|---|---|---|
| T1 | `llama-server.service` 段位修正 | [llama-server.service](../../ops/llama-server.service) | 修改 |
| T2 | `rpc-server.service` 段位修正 | [rpc-server.service](../../ops/rpc-server.service) | 修改 |
| T3 | `SERVICE_USER` 单点 + 面板 URL 改 IP | [cluster_const.py](../../ops/cluster_const.py) | 修改 |
| T4 | `cluster.py` 从 `cluster_const` 导入 `SERVICE_USER` | [cluster.py](../../ops/cluster.py) | 修改 |
| T5 | `infer-load` 身份/路径收敛 | [infer-load](../../ops/station-bin/infer-load) | 修改 |
| T6 | `infer-unload` 身份/路径收敛 | [infer-unload](../../ops/station-bin/infer-unload) | 修改 |
| T7 | `infer-list` NODE 表去 `.local` | [infer-list](../../ops/station-bin/infer-list) | 修改 |
| T8 | `cluster-watchdog` `SERVICE_USER`/`PEER` 收敛 | [cluster-watchdog](../../ops/station-bin/cluster-watchdog) | 修改 |
| T9 | `agent-cli.ps1` workspace/主机收敛 | [agent-cli.ps1](../../ops/station-bin/agent-cli.ps1) | 修改 |
| T10 | CI workflow | `.github/workflows/ci.yml` | 新增 |
| T11 | #6 先验红测试 | `tests/test_systemd_units.py` | 新增 |
| T12 | #9 先验红测试 | `tests/test_identity_literals.py` | 新增 |
| T13 | CI 结构测试 | `tests/test_ci_workflow.py` | 新增 |
| T14 | 站上件部署与 README 登记 | 三站 `/usr/local/bin`、[station-bin README](../../ops/station-bin/README.md) | 修改/部署 |

**边界（不做）**：

- 不碰 #5 `set -euo`、#8 拆文件/分目录。
- 不碰 `agent-cli-smoke.sh`（Windows Git Bash，`id -un` 语义不同）与 179 个冻结探针。
- 不改 `ops/*.service` 的 `User=`/`Group=`（部署身份，systemd 不能 env 展开）。
- CI 不 ssh 三站、不跑 `rpc_check` 全量、不持有 secret。
- 不新增 `requirements.txt`；CI 直接 `pip install paramiko pyyaml`。

---

## 2. 工程约定

| 项 | 值 | 依据 |
|---|---|---|
| Python | 3.12，仅 stdlib + `pyyaml`（测试） | 既有 py-tests |
| Shell | bash；站上件 LF | `.gitattributes` |
| PowerShell | PS 5.1 兼容（`agent-cli.ps1` 现状） | Windows 主控 |
| CI | `.github/workflows/` YAML；`permissions: contents: read` | GitHub 官方 |
| 站上部署 | SFTP → 备份 → `install -m 755` → `bash -n` → md5 | station-bin README |
| 退出码 | 测试 0/1；CI job 由 `run` 退出码决定 | 既有 |
| 提交粒度 | 代码 + 测试 + workflow 一个批次；站上部署单独核验 | 本仓纪律 |

---

## 3. 任务分解

### T1/T2（#6）：两份遗留单元

1. `llama-server.service`：把 `StartLimitIntervalSec=0` 从 `[Service]`（L16）移到 `[Unit]`（`Description`/注释之后）；`Restart=on-failure`、`RestartSec=10` 留在 `[Service]`。
2. `rpc-server.service`：同型，`StartLimitIntervalSec=0` 从 L15 移到 `[Unit]`；`Restart=always`、`RestartSec=5` 留在 `[Service]`。
3. 两文件头注各加一行：`# 历史快照：当前未部署（实测 disabled/inactive）；保留作参考。`
4. 不动 `rpc-server@.service`（已正确）。
5. 测试：`tests/test_systemd_units.py`（见 §9）。

### T3/T4（#9）：主控 Python

1. `cluster_const.py`：
   - `STATIONS` 后新增 `SERVICE_USER = STATIONS["B"]["user"]`，注释"三站同服务用户；换身份只改 `STATIONS`"。
   - 面板 URL（L192-194）从 `.local` 改 LAN IP：B `192.168.10.32`、A `192.168.10.33`。
2. `cluster.py`：
   - `from cluster_const import (...)` 增加 `SERVICE_USER`。
   - 删除 L2237 的 `SERVICE_USER = "scott-lau"` 字面。
3. 测试：`tests/test_identity_literals.py` 覆盖这两个文件。

### T5（#9）：`infer-load`

| 位置 | 现状 | 改法 |
|---|---|---|
| L18 | `AWORK="scott-lau@scott-lau-NEX.local"` | `AWORK="$(id -un)@10.10.10.1"`（A-B 直连段 IP） |
| L309-310 | `/home/scott-lau/vllm-rocm/...` | 本机命令 `$HOME/vllm-rocm`；远端 ssh 字符串用 `\$HOME/vllm-rocm`（远端展开） |
| L343 | `wait_gtt ... "scott-lau@${W_IP}"` | `"$(id -un)@${W_IP}"` |
| L352 | `exec bash /home/scott-lau/scripts/a4_vllm_launch.sh` | `exec bash "$HOME/scripts/a4_vllm_launch.sh"` |
| L366 | `DS4_HOME="${DS4_HOME:-/home/scott-lau/ds4}"` | `"${DS4_HOME:-$HOME/ds4}"` |
| L501 | `RPC_USER:-scott-lau` | `RPC_USER:-$(id -un)` |
| L556-557 | `cd /home/scott-lau`；`UN_LOG="/home/scott-lau/.unsloth/run-${ALIAS}.log"` | `cd "$HOME"`；`UN_LOG="$HOME/.unsloth/run-${ALIAS}.log"` |
| L399/L518 注释 | 含 `scott-lau` 的历史注释 | 不改（测试剥注释后不扫；L518 是历史教训，保留） |

### T6（#9）：`infer-unload`

| 位置 | 现状 | 改法 |
|---|---|---|
| L21 | `/home/scott-lau/vllm-rocm/bin/ray` | `$HOME/vllm-rocm/bin/ray` |
| L29 | `RPC_USER="${RPC_USER:-scott-lau}"` | `RPC_USER="${RPC_USER:-$(id -un)}"` |

### T7（#9）：`infer-list`

1. `NODE` 表（L33-35）改为：
   ```bash
   declare -A NODE=(
     [A]="$(id -un)@192.168.10.33"
     [B]="$(id -un)@192.168.10.32"
     [C]="$(id -un)@192.168.10.37"
   )
   ```
2. 删除 `.local` 兜底（LAN 已静态，见 `net.yaml` L110-120）；`peer_scan` 的候选循环自然退化为单地址。
3. 更新头部注释（L12/L23-27）：写明"LAN 已静态，按 IP；`.local` 兜底已退役"。
4. `SELF` 的 `hostname -s` 映射保留（本站识别，不是 SSH 身份）。

### T8（#9）：`cluster-watchdog`

| 位置 | 现状 | 改法 |
|---|---|---|
| L9 | `PEER="scott-lau-NEX.local"` | `PEER="${PEER:-192.168.10.33}"`（B 站缺省；A 站部署设 `PEER=192.168.10.32`；看门狗走管理 LAN） |
| L10 | `PEER_USER="scott-lau"` | `SERVICE_USER="${SERVICE_USER:-scott-lau}"` + `PEER_USER="$SERVICE_USER"` |
| L18/21 | `chown scott-lau:scott-lau` | `chown "$SERVICE_USER:$SERVICE_USER"` |
| 头注 L7 | 两站 `.local` 差异 | 改为"两站仅 `PEER` IP 不同（B 站 `192.168.10.33` / A 站 `192.168.10.32`）" |

**为什么不用 `$(id -un)`**：`cluster-watchdog.service` 无 `User=`，由 root oneshot 执行 ⇒ `id -un` 会是 `root`。`SERVICE_USER` 单点缺省 + 可覆盖是正确的。

### T9（#9）：`agent-cli.ps1`

| 位置 | 现状 | 改法 |
|---|---|---|
| L42-43 | `/home/scott-lau/agent-workspaces` / archive | `"/home/$($Script:REMOTE_USER)/agent-workspaces"` / `.../agent-workspaces-archive` |
| L263/L265/L878 | `Get-TargetHost` 的 A/B `.local` / 默认 `.local` | **保留**：它是 O-124 `Get-StationLetterFromHost` 的唯一反查真值源；改 IP 会让批行 `station=` 反查失效（Step 5 F-6） |
| L41 | `REMOTE_USER='scott-lau'` | **保留**（单一常量；主控 Windows 用户名不是远端 Linux 用户，不能用 `$env:USERNAME`） |

### T10：CI workflow

新增 `.github/workflows/ci.yml`（内容同 DESIGN §4.3），注意：
- `"on":` **加引号**，防 PyYAML 把 `on` 解析为布尔 `True`；
- `permissions: contents: read`；
- `py-tests` 用 `windows-2022`，`shellcheck` 用 `ubuntu-24.04`；
- `shellcheck --severity=error` 只扫活跃站上件（列表见 DESIGN §4.3）；
- 不出现 `secrets.`。

### T11-T13：测试

- `test_systemd_units.py`：解析两份单元；正向断言段位；负向夹具证明"键在 `[Service]` 会 FAIL"。
- `test_identity_literals.py`：剥注释后扫活跃清单；模式 `scott-lau@` / 已知 mDNS 名 / `/home/scott-lau`；`agent-cli.ps1` 因 O-124 反查真值源只禁前两者与家目录（`HOST_MAP_FILES` 白名单）；负向夹具证明探测器非空转。
- `test_ci_workflow.py`：`yaml.safe_load` + 纯函数 `validate_ci`；正向 + 负向夹具（缺权限/含 secrets 必须 FAIL）。

### T14：站上部署

`infer-load` / `infer-unload` / `infer-list` / `cluster-watchdog` 是站上件；改仓库后必须：
1. 三站备份 `*.bak-p2small-20261027`；
2. `install -m 755`；
3. `bash -n`；
4. md5 对账（`gates` 36/36）；
5. README 更新"当前"md5 与部署记录。

`cluster_const.py` / `cluster.py` / `agent-cli.ps1` 是主控件；`agent-cli.ps1` 若也部署到站上/主控，按同一纪律（视部署现状）。

---

## 4. 逐文件改造点

### 4.1 `ops/llama-server.service`

```ini
[Unit]
Description=llama.cpp llama-server (MiniMax-M2.7 Q4_K_S, 双机 RPC Master, B 站)
# 历史快照：当前未部署（实测 disabled/inactive）；保留作参考。
# ...
StartLimitIntervalSec=0

[Service]
Type=simple
...
Restart=on-failure
RestartSec=10
# StartLimitIntervalSec 不在这里
```

### 4.2 `ops/rpc-server.service`

```ini
[Unit]
Description=llama.cpp RPC server (...)
# 历史快照：当前未部署（实测 disabled/inactive）；保留作参考。
# ...
StartLimitIntervalSec=0

[Service]
Type=simple
...
Restart=always
RestartSec=5
```

### 4.3 `ops/cluster_const.py`

```python
STATIONS = {
    "A": {"host": "192.168.10.33", "user": "scott-lau"},
    "B": {"host": "192.168.10.32", "user": "scott-lau"},
    "C": {"host": "192.168.10.37", "user": "scott-lau"},
}
# P2 #9: 站上服务用户单点（三站同用户）。换身份只改 STATIONS。
SERVICE_USER = STATIONS["B"]["user"]
...
PANELS = (
    ...
    ("Beszel 监控", "http://192.168.10.32:8090"),
    ("Cockpit B", "https://192.168.10.32:9095"),
    ("Cockpit A", "https://192.168.10.33:9095"),
)
```

### 4.4 `ops/cluster.py`

```python
from cluster_const import (
    STATIONS, STATION_PORT, ROUTE, STATION_ROUTES, BACKENDS,
    DEFAULT_STATION, RPC_MODELS, RPC_WORKER_IPS, DS4_PP_MODELS, CONTAINER_MODELS,
    HTML_OUT, SSH_TIMEOUT, PANELS, SERVICE_USER,
)
...
# 删除原 L2237 `SERVICE_USER = "scott-lau"`；改用导入值。
```

### 4.5 `ops/station-bin/infer-load`

```bash
AWORK="$(id -un)@10.10.10.1"
...
  ssh -o BatchMode=yes "$AWORK" "pkill -f '^ray::' 2>/dev/null; \$HOME/vllm-rocm/bin/ray stop -f 2>/dev/null" 2>/dev/null || true
...
    wait_gtt "worker(${W_IP})" "$(id -un)@${W_IP}"
...
exec bash "$HOME/scripts/a4_vllm_launch.sh"
...
  DS4_HOME="${DS4_HOME:-$HOME/ds4}"
...
  RPC_ALIVE="$(sudo -u "${RPC_USER:-$(id -un)}" "$RPCCMD" --start "${ALIAS}" ...)"
```

### 4.6 `ops/station-bin/infer-unload`

```bash
$HOME/vllm-rocm/bin/ray stop -f 2>/dev/null || true
RPC_USER="${RPC_USER:-$(id -un)}"
```

### 4.7 `ops/station-bin/infer-list`

```bash
declare -A NODE=(
  [A]="$(id -un)@192.168.10.33"
  [B]="$(id -un)@192.168.10.32"
  [C]="$(id -un)@192.168.10.37"
)
```

### 4.8 `ops/station-bin/cluster-watchdog`

```bash
PEER="${PEER:-192.168.10.33}"     # B 站缺省；A 站部署设 192.168.10.32（管理 LAN）
SERVICE_USER="${SERVICE_USER:-scott-lau}"
PEER_USER="$SERVICE_USER"
...
sudo mkdir -p "$STATE_DIR" && sudo chown "$SERVICE_USER:$SERVICE_USER" "$STATE_DIR"
...
sudo touch "$LOG" && sudo chown "$SERVICE_USER:$SERVICE_USER" "$LOG"
```

### 4.9 `ops/station-bin/agent-cli.ps1`

```powershell
$Script:REMOTE_USER = 'scott-lau'
$Script:WORKSPACE_ROOT = "/home/$($Script:REMOTE_USER)/agent-workspaces"
$Script:WORKSPACE_ARCHIVE_ROOT = "/home/$($Script:REMOTE_USER)/agent-workspaces-archive"
...
if ($station -eq 'A') { return 'scott-lau-NEX.local' }   # O-124 反查真值源，保留
return 'scott-lau-GTR-Pro.local'                          # B default，保留
...
if (-not $hostName) { $hostName = 'scott-lau-GTR-Pro.local' }
```

### 4.10 `.github/workflows/ci.yml`

见 DESIGN §4.3；`"on":` 加引号。

---

## 5. 接口实现

| 接口 | 输入 | 输出 | 失败语义 |
|---|---|---|---|
| `validate_ci(data, text)` | workflow dict + 原文 | `list[str]` problems | 空 = PASS |
| `test_systemd_units` | 单元文件 | 段位断言 | 键在 `[Service]` / 缺失 ⇒ FAIL |
| `test_identity_literals` | 活跃文件清单 | 命中列表 | 任一命中 ⇒ FAIL |
| `SERVICE_USER` | `STATIONS` | 字符串 | 缺 `STATIONS` 键 ⇒ KeyError（启动即失败） |

---

## 6. 兼容性与迁移

| 场景 | 策略 |
|---|---|
| 站上 `infer-list` 的 `.local` 兜底 | LAN 已静态（`net.yaml`），删除；若未来回 DHCP，按 ADR-0006 重新评估 |
| `cluster-watchdog` A 站 PEER | 部署时设 `PEER=192.168.10.32`；缺省只适配 B（管理 LAN） |
| `agent-cli.ps1` 主机表 | **不改**（O-124 反查真值源）；workspace 根动态，SSH 目标不变 ⇒ known_hosts 不变 |
| 单元 `User=` | 保持字面量；换机由安装者统一改 4 个文件（已记录边界） |
| CI 首跑 | 若 Windows runner 路径不符，修测试的 bash/powershell 发现，不降平台 |
| 站上件未部署 | `gates` 会报 md5 漂移；必须先部署再跑门禁 |

---

## 7. 错误处理实施

| 场景 | 动作 | 退出/响应 |
|---|---|---|
| `StartLimitIntervalSec` 在 `[Service]` | 测试 FAIL，点名文件 | 测试 exit 1 |
| 键缺失 | 测试 FAIL（缺失 ≠ 通过） | 同上 |
| 活跃文件命中禁止模式 | 测试 FAIL，打印文件:行 | 同上 |
| `SERVICE_USER` 缺 `STATIONS["B"]` | `KeyError`（启动即失败） | 进程退出 |
| CI 缺 `permissions` / 含 `secrets.` | `test_ci_workflow.py` FAIL | 测试 exit 1 |
| CI job 运行失败 | GitHub job FAIL；修路径/依赖，不放宽判据 | job exit ≠ 0 |
| `shellcheck` warning | 不阻断（`--severity=error`） | job PASS |
| 站上件部署失败 | `install`/`bash -n` 非 0 ⇒ 停止；保留备份 | 部署失败 |

---

## 8. 不变式实施

| 不变式（DESIGN §6） | 落点 | 判据 |
|---|---|---|
| 活单元不动 | 两文件只改段位/头注 | diff 范围 |
| 段位唯一 | 两文件 `[Unit]` 有、`[Service]` 无 | `test_systemd_units` |
| 身份分域 | bash `id -un` / Python `STATIONS` / PS 常量 / unit 部署身份 | `test_identity_literals` + 文档 |
| 不碰冻结面 | 活跃清单白名单 | 测试清单 |
| CI 无 secret / 无 SSH | workflow 文本扫描 + 无 `ssh` 步骤 | `test_ci_workflow` |
| 不新增管理入口 | CI 是仓库外编排；无新 `cluster.py` 子命令 | diff 范围 |
| P2 不扩权 | 不碰 #5/#8 | diff 范围 |

---

## 9. 测试策略

### 9.1 先验红 → 后验绿

| # | 先验红场景 | 修复后断言 | 测试 |
|---|---|---|---|
| 6 | 两份单元 `StartLimitIntervalSec` 在 `[Service]` | 在 `[Unit]`；`[Service]` 无 | `test_systemd_units.py` |
| 6 | 负向夹具：键在 `[Service]` | 测试 FAIL | 同上 |
| 9 | 活跃清单命中 `scott-lau@` / 已知 mDNS 名 / `/home/scott-lau` | 0 命中（`agent-cli.ps1` 的 `Get-TargetHost` 白名单除外） | `test_identity_literals.py` |
| 9 | 负向夹具：构造一行 `scott-lau@scott-lau-NEX.local` | 探测器 FAIL | 同上 |
| 9 | 白名单：`agent-cli-smoke.sh` 不在清单 | PASS | 同上 |
| CI | 无 `.github/workflows/ci.yml` | 文件存在 + 结构合规 | `test_ci_workflow.py` |
| CI | 负向夹具：缺 `permissions` / 含 `secrets.` | `validate_ci` 返回非空 | 同上 |

### 9.2 测试实现要点

- `test_systemd_units.py`：`configparser.RawConfigParser(optionxform=str)`；`read(path, encoding="utf-8")`；不依赖 systemd 二进制。
- `test_identity_literals.py`：
  - 剥注释（引号感知）：单/双引号内的 `#` 不算注释；
  - 活跃清单 = `cluster.py` / `cluster_const.py` / `cluster_web.py` / `rpc_check.py` / `infer-load` / `infer-unload` / `infer-list` / `cluster-watchdog` / `agent-cli.ps1`；
  - 白名单 = `agent-cli-smoke.sh`、`ops/*.service`、`docs/`、`archive/`、冻结探针（不扫）；
  - 反向夹具证明探测器非空转。
- `test_ci_workflow.py`：
  - `yaml.safe_load`；`"on":` 已加引号；
  - `validate_ci` 正向/负向；
  - 文本扫描 `secrets.`。
- 全局：`py-tests`（62/62）、`doclinks`、`md-tables`、`secrets`、`syntax`、`scripts`、`gates`。

### 9.3 真站/CI 证据

| 项 | 期望 |
|---|---|
| 站上件部署 | 三站 `infer-load`/`infer-unload`/`infer-list`/`cluster-watchdog` md5 一致；`bash -n` 通过；`gates 36/36` |
| 活单元 | 保持 `disabled/inactive`；不 `daemon-reload` |
| CI 首推 | 两个 job 结果记录；失败按 §7 处置 |
| 本地全量 | `py-tests 62/62`；`rpc_check` 0 红 |

---

## 10. 实施顺序

1. **#6**：写 `test_systemd_units.py` → 跑红 → 改两个单元 → 跑绿。
2. **#9 测试**：写 `test_identity_literals.py` → 跑红（留存命中）。
3. **#9 主控 Python**：`cluster_const.py` + `cluster.py` → 测试部分转绿。
4. **#9 站上 bash**：`infer-load` / `infer-unload` / `infer-list` / `cluster-watchdog` → 测试全绿。
5. **#9 PowerShell**：`agent-cli.ps1` → 测试全绿。
6. **站上部署**：三站备份 → 部署 4 件 → `bash -n` → md5 → `gates`。
7. **CI**：写 `test_ci_workflow.py` → 红 → 写 workflow → 绿。
8. **README/登记**：station-bin README 更新 md5/部署变量；必要时 `inventory/ops.yaml`（若新增脚本，本批不新增）。
9. **全量**：`py tests\run_py_tests.py` + `rpc_check` 全量。
10. **首推**：观察 CI 两个 job；记录结果。

---

## 11. 与设计的一致性对齐

| DESIGN 条目 | 实施落点 | 一致性 |
|---|---|---|
| §3.1 T1-T14 | §1 T1-T14 | 一致 |
| §4.1 单元契约 | §4.1/§4.2 | 一致 |
| §4.2 身份契约 | §4.3-§4.9 + 测试清单 | 一致 |
| §4.3 CI 契约 | §4.10 | 一致（`"on":` 加引号是实现细节） |
| §6 不变式 | §8 | 逐条有落点 |
| §7 错误处理 | §7 | 逐条有动作 |
| §8 测试策略 | §9 | 先验红矩阵对应 |
| §10 实施输入 | §10 | 顺序一致 |

**显式边界**：

- `cluster-watchdog` 的 `SERVICE_USER` 保留 `scott-lau` 缺省（root oneshot，不能 `id -un`）；测试只禁 `scott-lau@`/已知 mDNS 名/家目录，允许裸用户名。
- `agent-cli.ps1` 的 `REMOTE_USER` 保留单一常量（Windows 用户名 ≠ 远端 Linux 用户）；其 `Get-TargetHost` 三个 host 串是 O-124 反查真值源，测试白名单。
- 单元 `User=`/`Group=` 不动（systemd 语义）。
- 主控 Python 的 `STATIONS` 三个 `user:` 值是**唯一真值**，允许裸用户名。
- 站上脚本里 `sudo -u "${RPC_USER:-$(id -un)}"` 属既有模式（`sudo -u` 显式指定目标用户）。

**裸用户名允许点清单**（测试不禁裸 `scott-lau`，只禁 `scott-lau@` / `.local` / `/home/scott-lau` 三模式；以下为全部允许点）：

| 文件 | 位置 | 理由 |
|---|---|---|
| `cluster_const.py` | `STATIONS` 三个 `user:` | 主控身份唯一真值 |
| `cluster_const.py` | `SERVICE_USER = STATIONS["B"]["user"]`（派生，非字面） | — |
| `cluster.py` | 导入（无字面） | — |
| `cluster-watchdog` | `SERVICE_USER="${SERVICE_USER:-scott-lau}"` | root oneshot 缺省，单点 |
| `agent-cli.ps1` | `$Script:REMOTE_USER = 'scott-lau'` | 主控常量块单点 |
| `agent-cli.ps1` | `Get-TargetHost` 的 A/B `.local` + 默认 `.local` | O-124 反查真值源（Step 5 F-6） |
| `ops/*.service` | `User=`/`Group=`（不在扫描范围） | 部署身份 |

---

## 12. 设计评审（幻觉排除，Step 4 第一遍）

### 12.1 已验证代码事实（E1）

| 断言 | 证据 |
|---|---|
| 两份单元键在 `[Service]` | `llama-server.service` L16；`rpc-server.service` L15 |
| `rpc-server@.service` 已在 `[Unit]` | L17 + 注释 L15-16 |
| 两份单元非活 | A `rpc-server.service` disabled/inactive；B `llama-server.service` disabled/inactive（2026-10-27 ssh 只读） |
| `cluster-watchdog` 无 `User=`（root oneshot） | d1-watchdog IMPLEMENTATION L84-91 |
| 站上 `infer-load` 以服务用户执行 | `cluster.py` 用 `ssh_stream(station, "infer-load ...")`，非 sudo |
| 仓库无 `.github` | `Get-ChildItem .github` 无输出 |
| py-tests 59/59 | 本地全量 |
| Ubuntu 24.04 预装 ShellCheck 0.9.0 | runner-images Ubuntu2404-Readme |
| `User=` 只接受单一用户名/UID；`%u` 系统单元恒 root | systemd.exec / systemd.unit |

### 12.2 外部事实（E3）

| 断言 | 依据 |
|---|---|
| `StartLimitIntervalSec` 属 `[Unit]` | systemd.unit(5) · Debian |
| `StartLimitIntervalSec=0` 关闭限速 | 同上 |
| GitHub workflow 必须在 `.github/workflows/` | GitHub Docs |
| `setup-python` 建议 `contents: read` | setup-python README |
| Ubuntu 24.04 镜像预装 ShellCheck | runner-images |
| ShellCheck `--severity=error` 只 error 级阻断 | ShellCheck 文档 |

### 12.3 实施时必须现场验证

| 项 | 验证方式 | 失败时 |
|---|---|---|
| Windows runner 有 Git Bash/PS 5.1 | CI 首跑 `py-tests` | 修测试路径发现，不降平台 |
| `actions/checkout@v7`/`setup-python@v7` 标签存在 | CI 首跑解析 | 改 `@v4`/`@v5` 并记录 |
| `agent-cli.ps1` 主机表 | **不改**（O-124 反查真值源）；只改 workspace 根 | 黄金夹具 `o124b` 三用例必须 PASS |
| `cluster-watchdog` A 站 PEER | 部署时设 `PEER=192.168.10.32`；首跑日志 | 改部署变量 |
| 站上件部署后 `gates` | `rpc_check --only gates` | md5/部署回滚 |
| ShellCheck 对活跃站上件是否有 **error** 级命中 | CI 首跑 `shellcheck` job（本机 Git Bash 无 shellcheck，无法预跑） | 逐条修；`--severity=error` 不放宽 |
| `configparser` 对 `%` 的插值 | 测试用 `RawConfigParser`（无插值） | 已在 §9.2 固化 |

### 12.4 不声称

- 不声称两份遗留单元会被部署/启用；它们只是仓库快照。
- 不声称 #9 消灭了所有字面量；单元 `User=`、`cluster-watchdog`/`agent-cli.ps1` 的单点常量是**已记录边界**。
- 不声称 CI 覆盖全量门禁；它只覆盖离线 py-tests + shellcheck。
- 不声称 Windows runner 一定通过；首跑需观察。

### 12.5 Step 4 评审记录（2026-10-27，第二遍）

> 方法：① 行号/段位对回 `2b9ba875` 工作区 Grep 复核；② DESIGN §3/§4 ↔ IMPLEMENTATION §1/§4 逐条比对；③ 实现者视角扫缺口（测试可行性 / `id -un` 语义 / CI 细节）。

**结论：PASS（6 项发现：5 项已修订入文，1 项确认为已记录边界）**。

**已修订（F-1～F-3、F-5、F-6）**：

| # | 发现 | 处置 |
|---|---|---|
| F-1 | `infer-load` 改造点漏 **L556-557**（`cd /home/scott-lau` + `UN_LOG="/home/scott-lau/.unsloth/..."`，unsloth 后端启动路径）—— 漏改则 `test_identity_literals` 永远红 | §4.5 补两行改造点；注释行（L399/L518）明确"不改" |
| F-2 | "裸用户名允许点"散落在 §11 三行字里，测试判据不完整 —— 若实现者按"禁裸 scott-lau"实现会误报 | §11 补**允许点清单**表（5 处 + 单元），并明确测试只禁三模式 |
| F-3 | §9.2 写 `RawConfigParser` 但未说明为什么 —— 单元里 `%` 字符会被默认 `BasicInterpolation` 炸掉 | §12.3 验证表补一行"防 `%` 插值"，固化判据 |
| F-5 | `cluster-watchdog` 的 `PEER` 原走**管理 LAN**（`.local` 解析到 192.168.10.x），设计初稿误写 RPC 直连段 `10.10.10.x` | T8/§4.8/Q1 改 `192.168.10.33`（B）/ `192.168.10.32`（A） |
| F-6 | `agent-cli.ps1` 的 `Get-TargetHost` `.local` 是 O-124 `Get-StationLetterFromHost` 的**唯一反查真值源**；改 IP 会让批行 `station=` 反查失效（黄金夹具 `o124b` 三条） | T9/§4.9 改为**保留** host 表，只改 workspace 根；测试加 `HOST_MAP_FILES` 白名单 |

**已确认边界（F-4，不修，记录依据）**：

| # | 边界 | 依据 |
|---|---|---|
| F-4 | `infer-load` L310 的 ssh 远端命令串里写 `\$HOME/vllm-rocm`（**远端**展开）而非 `$HOME`（本地展开）—— 两者当前等价（同用户同 home 路径），但 `\$HOME` 语义更准（远端家目录） | §4.5 已注明；实现时二选一，测试判据不受影响 |

**行号复核结果**（全部命中）：`llama-server.service` L16；`rpc-server.service` L15；`rpc-server@.service` L17（已在 `[Unit]`）；`infer-load` L18/309/310/343/352/366/399/501/518/556/557；`infer-unload` L21/L29；`.github` 不存在。`doclinks` 已证 3897 条链接可达。

**行号漂移预警**：实施 #9 时 `infer-load` 行号会随改动下移（L309 之后每删一处 `/home/scott-lau` 行号不变，无插入行）⇒ 以"锚点文本"定位，不依赖行号。

---

## 13. 风险与回滚

| 风险 | 影响 | 缓解 | 回滚 |
|---|---|---|---|
| 站上件改了未部署 | `gates` 红；站上行为仍旧 | 先部署再跑门禁 | 部署新版或 `cp -a` 备份 |
| `id -un` 在 sudo 下变 root | SSH 选错用户 | 站上脚本由 ssh 以服务用户执行；`cluster-watchdog` 不用 `id -un` | 恢复脚本 |
| `cluster-watchdog` PEER 默认只适配 B | A 站误连 | README 注明 A 设 `PEER=192.168.10.32` | 改部署变量 |
| `agent-cli.ps1` 主机表被误改 | O-124 批行 `station=` 反查失效 | 保留 `Get-TargetHost` `.local` 表；黄金夹具 `o124b` 兜底 | 恢复三行 host |
| CI Windows 首跑失败 | PR/push 红 | 修路径/依赖，不放宽判据 | 删除 workflow 即回滚 |
| `actions/*@v7` 标签不存在 | job 无法启动 | 首跑观察；改 `@v4`/`@v5` | 改版本 |
| 身份测试误报（字符串内 `#`） | 测试假红 | 引号感知剥注释 + 负向夹具 | 调整剥注释逻辑 |
| 单元测试用 `configparser` 大小写 | 断言假红 | `optionxform=str` | 修正解析 |

**回滚粒度**：

1. 单文件 `git checkout -- <file>`。
2. 站上件 `sudo cp -a /usr/local/bin/<name>.bak-p2small-20261027 /usr/local/bin/<name>`。
3. CI 删除 `.github/workflows/ci.yml`。
4. 单元只改仓库，回滚无运行时影响。
