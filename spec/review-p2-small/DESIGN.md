# 设计文档：原始评审 P2 小批次（遗留单元 / 身份收敛 / CI）

---

id: review-p2-small-DESIGN
type: design
version: 1.0
status: draft
date: 2026-10-27
depends: [ADR-0004, ADR-0006]
upstream: null

---

> **Feature**: 收掉原始评审 P2 里**改动小、确定性高**的三项——#6 两份遗留 systemd 单元的键段位、#9 活跃运行时的用户名/主机名收敛、CI（GitHub Actions 跑 `py-tests` + `shellcheck`）；#5 `set -euo` 扫荡与 #8 拆大文件/分目录明确另立大 spec。
> **创建日期**: 2026-10-27
> **状态**: draft（Step 2 DESIGN；实施展开待 Step 3）
> **Spec 步骤**: Step 2（DESIGN）
> **基于调研**: [原始评审 P2 小批次 · 社区外部锚点调研](../../docs/research/2026-10-27_原始评审P2小批次_社区外部锚点调研.md)
> **代码基线**: `2b9ba875`（`main`，已推送；行号为该基线快照）

---

## 1. 设计目标

1. **#6 单元自洽**：两份遗留单元里的 `StartLimitIntervalSec=0` 回到 `[Unit]`；`[Service]` 不再含该键。不改变任何活单元；不部署、不重启。
2. **#9 身份收敛**：把"活跃运行时"的字面 SSH 身份与 mDNS 主机名收敛为**每个执行域一条派生规则**：
   - 站上 bash（以服务用户执行）→ `$(id -un)` / `$HOME`；
   - 主控 Python → `STATIONS` 单点；
   - 主控 PowerShell → 单一常量块 + IP 拓扑；
   - systemd 单元 → 部署身份（systemd 不能 env 展开，明确列为已记录边界）。
3. **CI 落地**：一个 workflow、两个 job——Windows 跑 `tests/run_py_tests.py`，Ubuntu 跑 `shellcheck --severity=error`；**不**在 CI 里 ssh 三站、不持有任何 secret。

**不做**（P2 其余项）：

- 不做 #5 `set -euo` 全仓扫荡；不做 #8 拆 `rpc_check.py` / `cluster.py` / `agent-cli.ps1` / `station-bin` 分目录。
- 不改冻结探针（`_a*`/`_b*`/`_qwen*`）、历史文档、`archive/`。
- 不改 systemd 单元的 `User=`/`Group=`（见 §5 替代方案与 §6 不变式）。
- 不加第三方针对 shellcheck 的 action；不引入 `requirements.txt`（CI 直接 `pip install paramiko pyyaml`）。

---

## 2. 设计依据

| 调研结论（E3/E1） | 本仓缺口 | 设计决策 | 证据 |
|---|---|---|---|
| `StartLimitIntervalSec`/`StartLimitBurst` 是 `[Unit]` 键 | 两份遗留单元写在 `[Service]`，systemd 忽略 | 移到 `[Unit]`；两份文件各 1 行 | 调研 §1.1/§2 |
| `rpc-server@.service` 已按正确段位修过（2026-09-29） | 同型修法已有先例 | 复用其注释口径，不另造 | 该文件 L15-17 |
| 两份单元在 A/B 均 `disabled/inactive`，C 无 | 修了不影响运行时 | 只改仓库快照 + 头注"历史快照" | 调研 §1.1 站上实测 |
| `User=` 只接受单一用户名/UID；`%u` 系统单元恒 root | 单元不能靠 env/说明符跟随部署用户 | 单元身份列为**部署身份**；不尝试动态派生 | 调研 §2（systemd.exec/unit） |
| 站上脚本以服务用户执行（ssh 用户，非 root） | `scott-lau@host`、`/home/scott-lau` 散落 | `$(id -un)` / `$HOME` | 调研 §1.2 |
| `cluster-watchdog` 由 root oneshot 执行（unit 无 `User=`） | 不能用 `id -un`（会是 root） | 保留 `SERVICE_USER` 单点缺省 + 可覆盖；`chown` 用它 | 调研 §1.2；d1-watchdog 单元 |
| GitHub Actions 工作流必须在 `.github/workflows/` | 仓库无 `.github` | 新增 `ci.yml` | 调研 §2 |
| `setup-python` 推荐 `permissions: contents: read` | 无 CI 权限面 | workflow 顶部只给读权限 | 调研 §2 |
| Ubuntu 24.04 runner 预装 ShellCheck 0.9.0 | 无需安装/第三方 action | 直接 `shellcheck --severity=error` | 调研 §2 |
| Windows runner 有 PowerShell 与 Git Bash | py-tests 的平台假设匹配 | `py-tests` 跑 `windows-2022` | 调研 §1.3/§2 |

---

## 3. 架构与改动面

### 3.1 改动清单

| # | 文件 | 类型 | 要点 |
|---|---|---|---|
| D1 | [llama-server.service](../../ops/llama-server.service) | 修改 | `StartLimitIntervalSec=0` → `[Unit]`；头注"历史快照/未部署" |
| D2 | [rpc-server.service](../../ops/rpc-server.service) | 修改 | 同上 |
| D3 | [cluster_const.py](../../ops/cluster_const.py) | 修改 | 面板 URL 改 LAN IP；新增 `SERVICE_USER = STATIONS["B"]["user"]`（单点） |
| D4 | [cluster.py](../../ops/cluster.py) | 修改 | 删除本地 `SERVICE_USER` 字面，改从 `cluster_const` 导入 |
| D5 | [infer-load](../../ops/station-bin/infer-load) | 修改 | `AWORK=$(id -un)@10.10.10.1`；`/home/scott-lau/*` → `$HOME/*`；`RPC_USER` 缺省 `$(id -un)` |
| D6 | [infer-unload](../../ops/station-bin/infer-unload) | 修改 | `$HOME/vllm-rocm`；`RPC_USER` 缺省 `$(id -un)` |
| D7 | [infer-list](../../ops/station-bin/infer-list) | 修改 | `NODE` 改 `$(id -un)@<LAN IP>`；去 `.local` 兜底；同步注释 |
| D8 | [cluster-watchdog](../../ops/station-bin/cluster-watchdog) | 修改 | `SERVICE_USER` 单点缺省 + `PEER` 改 IP（无 `.local`）；`chown` 用它 |
| D9 | [agent-cli.ps1](../../ops/station-bin/agent-cli.ps1) | 修改 | workspace 根用 `REMOTE_USER` 拼；主机函数**保留** `Get-TargetHost` 单一表（A/B `.local`、C IP）—— 它是 O-124 反查真值源，改 IP 会破坏批行 `station=` 反查 |
| D10 | `.github/workflows/ci.yml` | 新增 | 两个 job：`py-tests`（Windows）/ `shellcheck`（Ubuntu） |
| D11 | `tests/test_systemd_units.py` | 新增 | #6 先验红 |
| D12 | `tests/test_identity_literals.py` | 新增 | #9 先验红 |
| D13 | `tests/test_ci_workflow.py` | 新增 | CI 结构断言 |
| D14 | `ops/station-bin/README.md` | 修改 | 登记 `cluster-watchdog` 的 `SERVICE_USER`/`PEER` 部署变量与单元身份边界 |

**边界**：`agent-cli-smoke.sh` 是 Windows Git Bash 的 smoke 测试（`id -un` 会得到 Windows 用户，不是 `scott-lau`）⇒ **不进 #9 活跃清单**，列入测试白名单。单元 `User=`/`Group=` 同理（systemd 语义所限）。

### 3.2 #6 数据流

```
ops/*.service 快照
  [Unit]  ← StartLimitIntervalSec=0（systemd 真正读取的位置）
  [Service] ← Restart=... / RestartSec=...（类型专属）
```

无运行时数据流；站上两份单元保持 `disabled/inactive`，不部署、不 `daemon-reload`。

### 3.3 #9 派生规则

```
站上 bash（以服务用户执行）
  SVC_USER=$(id -un)        # infer-load / infer-unload / infer-list
  HOME=$HOME                # /home/scott-lau/* → $HOME/*
  SSH_TARGET=$(id -un)@<直连段或管理网 IP>

主控 Python
  STATIONS[st]["user"]      # 唯一真值
  SERVICE_USER = STATIONS["B"]["user"]   # 三站同用户；换身份只改 STATIONS

主控 PowerShell
  $Script:REMOTE_USER       # 单一常量块（agent-cli.ps1 L41）
  workspace = "/home/$Script:REMOTE_USER/..."
  station host = Get-TargetHost 单一表（A/B `.local`、C IP；O-124 反查真值源）

systemd 单元
  User=/Group= 字面量       # 部署身份，不做运行时派生（边界）
```

### 3.4 CI 数据流

```
push / pull_request
  ├─ py-tests (windows-2022)
  │    checkout → setup-python 3.12 → pip install paramiko pyyaml → python tests/run_py_tests.py
  └─ shellcheck (ubuntu-24.04)
       checkout → shellcheck --severity=error <活跃站上件清单>
```

**不进入 CI**：`rpc_check` 全量、`gates`、`stations`、`usb4`、`engine`（需三站 LAN/SSH）。它们继续由本地 pre-push 执行。

---

## 4. 接口与契约

### 4.1 systemd 单元契约

- `ops/llama-server.service` / `ops/rpc-server.service`：
  - `[Unit]` 含 `StartLimitIntervalSec=0`；
  - `[Service]` **不含** `StartLimitIntervalSec`；
  - `Restart` / `RestartSec` 保持原值（`on-failure`/10s、`always`/5s）；
  - 头注一行：`# 历史快照：当前未部署（实测 disabled/inactive）；保留作参考。`
- `ops/rpc-server@.service` 不动（已正确）。
- 判据：`tests/test_systemd_units.py` 用 INI 解析，逐文件断言。

### 4.2 身份契约

| 执行域 | 规则 | 允许的字面量 |
|---|---|---|
| 站上 bash | SSH 用户 `$(id -un)`；家目录 `$HOME`；站间地址用 IP | `SELF` 的 `hostname -s` 映射（本站识别） |
| 主控 Python | `STATIONS` 单点；`SERVICE_USER` 从它派生 | `STATIONS` 里的 `user: "scott-lau"`（唯一真值） |
| 主控 PowerShell | `REMOTE_USER` 单一常量；workspace 用它拼；主机走 `Get-TargetHost` 单一表（A/B `.local`、C IP） | `REMOTE_USER` 的缺省值一处；`Get-TargetHost` 的 3 个 host 串 |
| systemd 单元 | 部署身份 | `User=`/`Group=`（4 文件） |
| 冻结探针/文档/smoke | 不动 | 白名单 |

**禁止模式（活跃清单内）**：`scott-lau@`、已知 mDNS 名、`/home/scott-lau`（注释行剥除后再扫）；`agent-cli.ps1` 的 `Get-TargetHost` 三个 host 串是已记录白名单（O-124 反查真值源）。

### 4.3 CI 契约

```yaml
name: ci
on:
  push:
  pull_request:
permissions:
  contents: read
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  py-tests:
    runs-on: windows-2022
    timeout-minutes: 30
    env:
      PYTHONUTF8: '1'          # runner 默认 cp1252 ⇒ 中文输出会 UnicodeEncodeError
      PYTHONIOENCODING: 'utf-8'
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with:
          python-version: '3.12'
      - run: pip install paramiko pyyaml
      - run: python tests/run_py_tests.py
  shellcheck:
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v7
      - name: ShellCheck（仅 error 级 + 活跃站上件）
        run: |
          shellcheck --version
          shellcheck --severity=error \
            ops/rpc-nodes \
            ops/station-bin/infer-load \
            ops/station-bin/infer-unload \
            ops/station-bin/infer-list \
            ops/station-bin/llama-serve-instance \
            ops/station-bin/rpc-serve-instance \
            ops/station-bin/load-gate \
            ops/station-bin/load-mem-gate \
            ops/station-bin/wait-gtt-release \
            ops/station-bin/model-locate.sh \
            ops/station-bin/conf-lib.sh \
            ops/station-bin/conf-get
```

- **非 bash 脚本不进列表**：`cluster-ttl` 是 `#!/usr/bin/env python3` ⇒ 进 shellcheck 会 `SC1071`（Step 5 首跑实测）。`test_ci_workflow.py` 已按 shebang 防回归。

- **权限**：仅 `contents: read`；不使用 `secrets.*`。
- **并发**：同 ref 取消旧运行，避免排队。
- **平台**：`py-tests` 用 `windows-2022`（PowerShell 5.1 + Git Bash）；`shellcheck` 用 `ubuntu-24.04`（预装 0.9.0）。
- **不装第三方 action**：shellcheck 直接调用镜像预装版本。
- **超时**：30/10 分钟，防挂死。

---

## 5. 替代方案（为什么不做）

| # | 方案 | 否决理由 |
|---|---|---|
| 6 | 归档/删除两份单元 | README 已作历史快照引用；移动制造链接噪声；删除丢历史。2 行修正更小且可机判 |
| 6 | 用 `%u` 让单元跟随部署用户 | 系统管理器下 `%u` 恒 `root`，会直接把服务跑成 root（E3） |
| 9 | 让 systemd 单元读 `inventory`/env | systemd 的 `User=` 只接受单一用户名/UID，不做环境变量展开（E3） |
| 9 | 全仓 139 处一次扫除 | 冻结探针不是运行路径；大扫除风险 > 收益；本批只收敛活跃面 |
| 9 | 站上 bash 用 `$USER` | `$USER` 可能为空/被 sudo 改写；`id -un` 是当前进程的真实用户 |
| 9 | `agent-cli-smoke.sh` 用 `$(id -un)` | 它跑在 Windows Git Bash，`id -un` 是 Windows 用户，不是远端 Linux 用户 ⇒ 白名单 |
| CI | 在 CI 跑 `rpc_check` 全量 | 公网 runner 无三站 LAN；不应持有内网密钥 |
| CI | 用 `ludeeus/action-shellcheck@master` | 多一个第三方供应链面；Ubuntu 镜像已预装 ShellCheck |
| CI | 全 Ubuntu 跑 py-tests | `test_rpc_check_ps1_golden` 依赖 PowerShell；平台性失败会污染回归信号 |

---

## 6. 不变式（Invariants）

1. **活单元不动**：两份遗留单元不部署、不 `systemctl`、不 `daemon-reload`；只改仓库快照。
2. **段位唯一**：`StartLimitIntervalSec` 只出现在 `[Unit]`；`[Service]` 不再出现。
3. **身份分域**：站上 bash、主控 Python、主控 PowerShell、systemd 各自一条派生规则；不跨域套用。
4. **不碰冻结面**：`agent-cli-smoke.sh`、`archive/`、179 个冻结探针、历史文档不改。
5. **CI 无 secret / 无 SSH**：workflow 只读仓库、只跑离线测试与静态检查。
6. **不新增管理入口**：CI 是仓库外编排，不是 `cluster.py` 子命令；不违反 ADR-0004。
7. **P2 不扩权**：不碰 #5/#8。

---

## 7. 错误处理

| 场景 | 行为 | 判据 |
|---|---|---|
| 单元键仍在 `[Service]` | `test_systemd_units.py` FAIL，点名文件/段位 | 先验红 |
| `StartLimitIntervalSec` 缺失 | 测试 FAIL（不能"没有键"也算过） | 同上 |
| 活跃文件出现 `scott-lau@` / `.local` / `/home/scott-lau` | `test_identity_literals.py` FAIL，打印文件+行 | 先验红 |
| `cluster-watchdog` 缺 `SERVICE_USER` | 用单点缺省 + 可覆盖；不静默空 chown | 脚本 `set -u` 已有 |
| CI workflow 缺 job / 权限过宽 / 含 `secrets.` | `test_ci_workflow.py` FAIL | 结构断言 |
| CI 首跑平台路径不符 | 修测试的路径发现（不改判据、不降平台） | 首跑观察 |
| `shellcheck` 报 error | job FAIL；只在 error 级阻断，warning 不阻断 | `--severity=error` |

---

## 8. 测试策略（Step 4/9 用）

### 8.1 先验红 / 后验绿

| # | 先验红场景 | 修复后断言 | 测试 |
|---|---|---|---|
| 6 | 解析两份单元，`StartLimitIntervalSec` 在 `[Service]` | 在 `[Unit]`，`[Service]` 无此键 | `test_systemd_units.py` |
| 6 | 把键删掉（负向夹具） | 测试仍 FAIL（"缺失"不算通过） | 同上 |
| 9 | 扫活跃清单，命中 `scott-lau@` / `.local` / `/home/scott-lau` | 0 命中 | `test_identity_literals.py` |
| 9 | 把 `agent-cli-smoke.sh` 加进扫描 | 仍 PASS（白名单） | 同上（白名单反向夹具） |
| CI | 无 `.github/workflows/ci.yml` | 文件存在、结构合规 | `test_ci_workflow.py` |
| CI | workflow 加 `secrets.X` / 权限写 | 测试 FAIL | 同上（负向夹具） |

### 8.2 单元 / 行为测试

- `test_systemd_units.py`：`configparser.RawConfigParser(optionxform=str)` 解析；不依赖 systemd 二进制；Windows/Ubuntu 均可跑。
- `test_identity_literals.py`：按行剥 `#` 注释后扫描；模式 `scott-lau@` / `.local` / `/home/scott-lau`；活跃清单 = §4.2 表；白名单 = `agent-cli-smoke.sh`/单元/文档/冻结探针（不扫）。
- `test_ci_workflow.py`：`yaml.safe_load`；断言 `on`、`permissions.contents=read`、两个 job、`runs-on` 平台、`setup-python` 3.12、`python tests/run_py_tests.py`、`shellcheck --severity=error`、文本无 `secrets.`。
- 全局：`py-tests`、`doclinks`、`md-tables`、`secrets`、`syntax`、`scripts`。

### 8.3 首跑与真站

- CI 首推后观察 `py-tests` / `shellcheck` 两个 job；失败按 §7 处置。
- 站上脚本本批**不改部署**（`infer-load`/`infer-unload`/`infer-list`/`cluster-watchdog` 的改动若要生效，需按既有部署纪律推三站；是否随本批部署待 Step 3 决定）。⚠ 若不部署，仓库副本与站上件会漂移，`gates` 会红；因此**若改了站上件，必须部署**（见 §10）。

---

## 9. 验收标准

| # | 验收判据 | 证据 |
|---|---|---|
| 6 | 两份单元 `StartLimitIntervalSec` 在 `[Unit]`；`[Service]` 无 | 单测 + 文件 diff |
| 9 | 活跃清单 0 命中 `scott-lau@`/`.local`/`/home/scott-lau` | 单测 + grep |
| 9 | 站上件（若部署）三站 md5 一致；`gates 36/36` | `rpc_check --only gates` |
| CI | `.github/workflows/ci.yml` 存在、结构合规、无 secret | 单测 + 首推 job 结果 |
| 全局 | `py-tests` 62/62（新增 3）；`rpc_check` 0 红 | 全量门禁 |

---

## 10. 对实施的输入（Step 3 展开）

1. **顺序**：#6（2 文件 + 测试）→ #9（代码 + 测试）→ CI（workflow + 测试）。
2. **#9 的部署决策**：`infer-load`/`infer-unload`/`infer-list`/`cluster-watchdog` 是站上件；改动后必须按"改仓库 → 核对 → 三站部署 → md5 对账"推进，否则 `gates` 红。`cluster_const.py`/`cluster.py`/`agent-cli.ps1` 是主控件，不需要站上部署（`agent-cli.ps1` 若也部署到站上，需按同一纪律）。
3. **CI 首跑**：workflow 推送后观察；失败先修路径发现/依赖，不降平台、不放宽判据。
4. **回滚**：单文件 `git checkout`；站上件用 `.bak-p2small-20261027` 备份；CI 删除 workflow 即回滚。

---

## 11. 风险与未决

| 风险 | 影响 | 缓解 |
|---|---|---|
| `id -un` 在 `sudo` 下变成 root | SSH 选错用户 | 站上脚本由 ssh 以服务用户执行（非 sudo）；`cluster-watchdog` 保留 `SERVICE_USER` 缺省 |
| `cluster-watchdog` 的 `PEER` 默认只适配 B 站 | A 站需改一行 | README 注明"A 站设 `PEER=192.168.10.32`（管理 LAN）"；保留可覆盖 |
| `agent-cli.ps1` 主机表若改 IP | O-124 批行 `station=` 反查失效 | 保留 `Get-TargetHost` `.local` 表（Step 5 发现的 F-6）；workspace 根仍动态 |
| CI Windows 首跑 Git Bash/PowerShell 路径不符 | job 失败 | 先修测试路径发现；不降平台 |
| `actions/checkout@v7` / `setup-python@v7` 标签不存在 | workflow 失败 | 首跑观察；必要时改 `@v4`/`@v5` 并记录 |
| 站上件改了未部署 | `gates` 红 | §10 部署纪律；先部署再跑门禁 |

**待决问题（本文已裁）**：

- **Q1**：`cluster-watchdog` 的 `PEER` → **管理 LAN IP 缺省（B 站 `192.168.10.33`）+ 可覆盖**；A 站部署设 `192.168.10.32`。看门狗走 SSH 健康探测（管理 LAN），不是 RPC 直连段。
- **Q2**：`agent-cli-smoke.sh` → **白名单**，不纳入 #9 活跃清单。
- **Q3**：CI action 版本 → **major tag `@v7`**（可读性）；SHA 钉为可选 P3。
- **Q4**：CI 平台 → **windows-2022 + ubuntu-24.04**；首跑失败先修路径发现。

---

## 12. 附：与既有 spec 的关系

- 不改 [review-p1-remediation](../review-p1-remediation/DESIGN.md) 的 conf/模型定位/Web token 契约；本批只碰单元段位、身份与 CI。
- 不改 [d1-watchdog-fault](../d1-watchdog-fault/IMPLEMENTATION.md) 的看门狗单元形态；只改脚本内的 `SERVICE_USER`/`PEER` 默认与注释。
- 不改 [cluster-orchestration-reliability](../cluster-orchestration-reliability/DESIGN.md) 的加载/回收语义。
- 台账归属：[O-177](../d6-agent-standard/OPEN-ISSUES.md)（原始评审复核登记）；P2 小批次完成后在 CHECKLIST 中回写。
