# ADR-0006: 控制面传输绑定 LAN IPv4 —— 消除 `*.local` 解析的 16s 与"控制面走公网 IPv6"

---------------------------------------------------------------------

id: ADR-0006
type: adr
version: 1.0
status: accepted
date: 2026-09-16
depends: \[ADR-0003, ADR-0004, ADR-0005]
upstream: \[ADR-0004]
---------------------------------------------------------------------

> **Feature**: 把主控站到三站的 ssh/scp 控制面**显式绑定到 LAN IPv4**，使每次连接从 **~16.2s → ~0.18s（≈90×）**，
> 并把"LAN 管理面真值"登记进 `inventory/net.yaml` + 加一条防漂移门禁断言。
> **创建日期**: 2026-09-16
> **状态**: accepted
> **适用**: 主控站 `~/.ssh/config`、[cluster.py](../ops/cluster.py) 的 `STATIONS`、[net.yaml](../inventory/net.yaml)、[rpc_check.py](../ops/rpc_check.py) 的 `stations` 断言

---------------------------------------------------------------------

## 背景（Context）

**触发**：[OPEN-ISSUES](../spec/d6-agent-standard/OPEN-ISSUES.md) 登记的"框架级：每次 ssh/scp 建连 14-17s"（ADR-0005 实施期间实测发现；当时通过"合批回收"把 collect 的连接数 8→4 规避了一部分）。

**测量（2026-09-16 实测，非推断）**：

| # | 测量 | 结果 |
|---|---|---|
| 1 | `ssh scott-lau-GTR-Pro.local true`（按名） | **16,200 ms** |
| 2 | `ssh -o User=scott-lau -o IdentityFile=… 192.168.1.32 true`（按 LAN IPv4 + 显式身份） | **184 ms** |
| 3 | `ssh 192.168.1.37 true`（C 站，config 里本就是 IP） | **198 ms** |
| 4 | `[System.Net.Dns]::GetHostAddresses('scott-lau-GTR-Pro.local')` | **17,016 ms**，且**只返回 IPv6**（`2409:8a20:…`，无 A 记录） |
| 5 | `Resolve-DnsName <名>` / `-LlmnrNetbiosOnly` | 337ms / 0ms，**均无结果**（DNS 客户端 API 解析不出 `.local`） |
| 6 | 站上 `echo $SSH_CONNECTION`（按名连进去） | `2409:8a20:…:c428 12342 → 2409:8a20:…:bd20 22` ⇒ **控制面实际走公网 IPv6** |
| 7 | 站上 `echo $SSH_CONNECTION`（按 IPv4 连进去） | `192.168.1.36 12343 → 192.168.1.32 22` ⇒ **走 LAN** |
| 8 | `ip -4 -o addr`（A / B / 主控） | A=192.168.1.33、B=192.168.1.32、主控=192.168.1.36；**A/B 均为 DHCP 租约**（`scope global dynamic`, `valid_lft` ~14.5h） |
| 9 | `ssh -G <名>`（Win32-OpenSSH 9.5p1） | 可用，能读出 `hostname` = 名字（⇒ 可作为门禁判据来源，**不需网络**） |

**根因**：Windows 解析 `*.local` 走 mDNS 兜底路径，耗时 ~16-17s 且**只给出公网 IPv6 地址** ⇒ ① 每次 ssh/scp 白付 16s；② 控制面**没走局域网**，而是经 ISP IPv6 绕行（依赖运营商 IPv6 与临时隐私地址）。

**这不是新问题，本仓已有两处同源证据**：
- [cluster.py:160-175](../ops/cluster.py#L160-L175) 的注释：*"原先每次 ssh_run 都用主机名重连 ⇒ 每次连接白付 ~14s。9 次串行即 130s（这正是 `/api/status` 129.6s 的根因，见 CHECKLIST F19）。**C 站一直用 IP 故从未受影响**。此处缓存解析结果…"* —— 即：**问题早已诊断出，但缓解只覆盖了长驻 web 进程的进程内缓存**；`agent-cli.ps1` 的 CLI ssh/scp 路径与 `cluster.py` 的每次 CLI 调用仍在白付。
- [cluster.py:89](../ops/cluster.py#L89) 的 C 站条目：*"seaviv.local 可解析但**保持 IPv4 规避 paramiko/IPv6**"* —— **C 站当年就是按本文的结论办的**。

⇒ 本 ADR 不是引入新理念，而是把 C 站的做法**推广到 A/B**，并把"绑定"这件事**登记成可断言的真值**。

---

## 决策（Decision）

### D1. `~/.ssh/config`：名字保留为别名，`HostName` 绑定到 LAN IPv4

```
Host scott-lau-NEX.local
    HostName 192.168.1.33
Host scott-lau-GTR-Pro.local
    HostName 192.168.1.32
Host 192.168.1.33 192.168.1.32 192.168.1.37
    User scott-lau / IdentityFile ~/.ssh/id_ed25519 / IdentitiesOnly yes
+ AddressFamily inet   # 不再尝试 IPv6
```

- **名字继续可用**（所有调用点、文档、人的习惯都不用改）⇒ 改动面最小。
- **`AddressFamily inet`**：不再尝试 IPv6（实测 `inet` 单项省 ~3s，且确保不回落公网 IPv6）。
- 三个 IP 也加身份块：按 IP 连接时**默认用户名会退化为本机用户 `peng`**，实测会**卡在 stdin 等口令（>90s 挂起）** —— 这是本次调查中真实踩到的坑。

### D2. `cluster.py` 的 `STATIONS`：A/B 改用 LAN IPv4

与 C 站既有做法一致（D1 的注释即其理由）。`resolve_host()` 对 IP 直接返回，省掉解析与缓存；`_HOST_CACHE` 对仍以主机名登记的站保留。

### D3. LAN 管理面真值登记进 `inventory/net.yaml`

新增 `lan:` 段（三站 LAN IPv4 / 主控 IP / 接口 / DHCP 现状 / 测量方式），与既有的 USB4 `segments` 并列。**"改了网络就改本表"** 的维护约定沿用 net.yaml 既有措辞。

### D4. 门禁加"防漂移"断言（并入既有 `stations` 检查，非新脚本）

判据：**`ssh -G <名>` 的 `hostname` 必须等于 `net.yaml` 登记的 LAN IP**（纯本地计算，无网络开销）。
- 不符 ⇒ FAIL 并提示"DHCP 可能已漂移，请更新 net.yaml 与 `~/.ssh/config`"。
- 这一条把 D1/D2 的**唯一代价（IP 绑定对 DHCP 的脆弱性）转成可检出的红灯**，而不是"ssh 连不上"的谜题。若站真的漂移，既有的可达性判定也会同时 FAIL（双覆盖）。

---

## 否决/比较对象

| 方案 | 否决理由 |
|---|---|
| **在 station 侧把 LAN 改静态**（netplan/NM `manual`） | 远程改网络有**失联风险**（net.yaml 已记录同类事故："A 站接口错位 → 重启后两段全断"）；且需与路由器 DHCP 池避让，易出地址冲突 |
| **在路由器做 DHCP 保留**（按 MAC 固定 .32/.33/.37） | 这是**最干净**的稳定化手段，但需操作者/路由器权限（本轮无法执行）⇒ 列为**建议**，落地后 D4 的红灯概率进一步降低 |
| **主控 hosts 文件写死名字→IP** | 与 D1 等效，但需管理员权限、影响面更大（所有程序而非仅 ssh/scp），且同样依赖 IP 稳定 |
| **扩大 `_HOST_CACHE` 缓存**（把解析结果落到文件/跨进程复用） | 治标：每次仍可能冷启动付一次 16s；且新增一个缓存机制（D3 新增能力）与失效策略；关键——**缓存解决不了"只解析出公网 IPv6"这个更严重的问题** |
| **关闭主控的 IPv6** | 影响面大（其它用途）、且不解决 16s 解析耗时本身 |
| **什么都不做，只用 ADR-0005 的"合批"绕** | 只减少连接数，不减少单次成本；agent-cli 每个 task run 仍有 10-20 次连接（实测 run 墙钟 ≈420s，模型仅占 21-53s） |

---

## 后果与待办

**收益**
1. **每次 ssh/scp：~16.2s → ~0.18s（≈90×）**；CLI 路径（`agent-cli.ps1` 的 station-ready / slot-gate / profile / sync / lock / collect）与 `cluster.py` 每次调用**同时**受益。
2. **控制面回到 LAN**（不再经 ISP IPv6 绕行）—— 安全性、可预期性、以及不依赖运营商 IPv6 与临时隐私地址。
3. 消除"按 IP 连接默认用户名退化 ⇒ 卡 stdin"的隐患（`~/.ssh/config` 的三个 IP 身份块）。
4. **机器级配置与 repo 真值之间有了一条可断言的绑定**（D4），使该改动可被门禁复核、可被后人复现。

**代价与风险**
- **DHCP 漂移**（A/B 是动态租约）⇒ 由 D4 断言 + 既有可达性判定**双重检出**；建议在路由器做 DHCP 保留以进一步稳定。
- `~/.ssh/config` 属**机器级资产、不在 repo 版本控制内** ⇒ 其内容以 ADR 文本 + `net.yaml` 的 lan 段 + D4 断言三重固化；备份见 `~/.ssh/config.bak-20260916`。
- 未在本轮处理（保持范围）：`agent-cli.ps1` / `cluster.py` 的 ssh/scp **未统一加 `-o BatchMode=yes`**（防"认证失败时静默等 stdin"，本轮实测踩到 >90s 挂起）—— 已登记为独立项。

---

## 实施记录（2026-09-16）

**落点**

| # | 文件/资产 | 改动 |
|---|---|---|
| 1 | `~/.ssh/config`（机器级） | A/B 拆为独立块并加 `HostName <LAN IPv4>`；新增 `Host <三个 IP>` 身份块；全部加 `AddressFamily inet`；备份 `config.bak-20260916`（228 字节，逐字节同） |
| 2 | [cluster.py](../ops/cluster.py) | `STATIONS` A/B 的 `host` 由 `.local` 名改为 LAN IPv4（与 C 站条目同注释口径） |
| 3 | [net.yaml](../inventory/net.yaml) | 新增 `lan:` 段（真值 + DHCP 现状 + 测量方式） |
| 4 | [rpc_check.py](../ops/rpc_check.py) | `stations` 断言新增子项：`ssh -G <名>` 的 `hostname` == net.yaml 登记的 LAN IP |

**验收证据（逐项实测）**

| # | 判据 | 结果 |
|---|---|---|
| V1 | `ssh -G` 展开（纯本地） | A→`hostname 192.168.1.33`、B→`hostname 192.168.1.32`、IP 块→`user scott-lau`，三者均 `addressfamily inet` ✅ |
| V2 | **按名连接耗时**（各 2 次） | A = **169 / 199 ms**、B = **182 / 171 ms**（改前 16,200 ms）⇒ **≈90×**，rc=0 ✅ |
| V3 | **控制面路径**（站上 `$SSH_CONNECTION`） | 三站均 `192.168.1.36 <port> → 192.168.1.{33,32,37}:22` ⇒ **回到 LAN**（改前 A/B 为 `2409:8a20:…`） ✅ |
| V4 | **门禁 (h) 的负向自证** | 把 net.yaml 的 B 站 IP 改成 `192.168.1.99` ⇒ `[FAIL] stations` + 明示"ssh 绑定 hostname=192.168.1.32, 而 net.yaml 登记 192.168.1.99 —— DHCP 可能已漂移…"，**退出码 1（阻断）**；还原后恢复 PASS（黄灯 1 = 既有 `known_drift`） ✅ |
| V5 | `net.yaml` 仍可解析 | `--only usb4` PASS ✅ |
| V6 | **端到端真跑**（同一张卡 `tmp/e2e-evidence-card.md`） | **单次 task run 421 s → 48.5 s（8.7×）**；其中 `RUN_S=38 s` 是模型本身 ⇒ **框架开销 ~383 s → ~10 s** ✅ |
| V7 | 产物完整性未受影响（旁证 ADR-0005） | run4 的 9 件齐全；`sha256(prompt.txt)==prompt_sha256`、`accept_golden.sha256==仓库源哈希`、`judgment-record ↔ run.json` **全 PASS**；`%TEMP%` 0 残留 ✅ |

**备注**
- `cluster.py` 的 `resolve_host()` 保持不变（IP 直接返回，省掉解析与缓存）；`_HOST_CACHE` 对仍以主机名登记的站继续有效。
- 本轮**未**改动的同类项：`cluster.py:150-151` 的 Beszel/Cockpit **URL** 仍用 `.local` 名（面向人的浏览器地址，非控制面）；`spec/vulkan-version-control/UPGRADE_SOP.md` 中的人工命令仍写名字（改名后依然可用，因为名字保留为别名）。

---------------------------------------------------------------------

## 关联

- 上游：[OPEN-ISSUES](../spec/d6-agent-standard/OPEN-ISSUES.md) "框架级：每次 ssh/scp 建连 14-17s"；[ADR-0005](ADR-0005-任务卡证据回收闭环.md)（其 D4d"合批回收"是本问题的第一层缓解）
- [cluster.py:160-175](../ops/cluster.py#L160-L175)（F19 诊断与进程内缓存的既有缓解）、[cluster.py:89](../ops/cluster.py#L89)（C 站"保持 IPv4"先例）
- [net.yaml](../inventory/net.yaml)（USB4 三角真值与"改了网络就改本表"约定）
- [ADR-0004](ADR-0004-统一管理入口为唯一管理面.md)（D3 新增能力的合法路径 —— 本 ADR 未新增脚本，均为既有资产的改动）
