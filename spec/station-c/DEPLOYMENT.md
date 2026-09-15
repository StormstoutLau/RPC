# C 站（seaviv）安装与配置落档

> 状态：纵深部署完成（2026-09-07）+ HIP llama 引擎实测落地（gpt-oss，2026-09-12）｜后续：A-C 直连恢复 / 环网 failover 硬化 /
> 落档人：Scott｜基于工程 memory 与实测记录整理

---

## 1. 概览

| 项 | 值 |
|---|---|
| 主机名 / 用户 | `seaviv` / `scott-lau` |
| 管理 SSH | `scott-lau@192.168.1.37`（eno1 网线，DHCP；WiFi 192.168.1.24 已弃用，2026-09-08） |
| 硬件 | AMD Ryzen AI Max 395（Strix Halo），128G UMA，Radeon 8060S（gfx1151） |
| 集群定位 | 第三推理节点（A/B 现役，C 扩容）；RPC 节点、后续 ROUTE_TABLE 候选 |
| 内核（最终） | `6.17.0-23-generic`（对齐 B；HWE 7.0.0-28/-31 保留可回滚） |
| 引擎 | `llama-server(qwen3.8-27b-mtp)` systemd，PORT 18080，nothink 档 ctx8192；`llama-server(gpt-oss-120b-MXFP4)` HIP llama-systemd，PORT 8080，ctx131072（2026-09-12） |
| ROCm | `/opt/rocm` 7.2.1 用户态就位，`rocminfo` 在 6.17 下探到 gfx1151×2 |
| 管理面板 | Cockpit `https://192.168.1.37:9095`（socket drop-in 端口=9095，eno1）；Beszel agent→B hub `10.10.11.1:8090` |

---

## 2. 部署决策记录（D-*）

- **D-1 内存解锁**：GRUB `amdgpu.gttsize=120000 ttm.pages_limit=30720000`（与 A/B 同参）。**必须 update-grub 后重启**（首次只改 /etc/default/grub 不生效，实测踩坑）。
- **D-2 模型来源**：B(GTR-Pro) 为模型源站（`/data/models/gguf/Jackrong/Qwen3.8-27B-MTP-GGUF/`），rsync 至 C `~/models/qwen3.8-27b-mtp/`（Q8_0 29G + mmproj 1.8G）。**C 站直连 GitHub 443 不通，llama.cpp 源码用 B 站 rsync（同 commit 0d18aaa）而非 clone**。
- **D-3 引擎档位**：nothink（ctx8192，B 站实测最优 5/5；froggeric jinja，no `--reasoning-format deepseek`——llama.cpp #24671）。Draft-MTP 投机解码开启。
- **D-4 环网拓扑**：三段独立子网（A-B `10.10.10.0/24`、B-C `10.10.11.0/24`、A-C `10.10.12.0/24`），B 双口居中；三站 `ip_forward=1`（sysctl.d 持久化）。A 站经 B 的回程路由（netplan 持久化）。
- **D-5 A-C 直连优先（方案 1）**：A→10.10.11/24 主 via C(10.10.12.3, m102)、备 via B(10.10.10.2, m200)；C→10.10.10/24 对称。实测直连段吞吐 9.2Gbps vs 经 B 仅 31Mbps → **直连路径提质 ~290×**。
- **D-6 软件源**：主源（cn.archive+noble 全组件）本就一致；追加 NodeSource node20（claude code 依赖）+ Docker 官方源。LunarG/Chrome 不盲从（C 站无桌面需求）。
- **D-7 内核同步 B**：6.17.0-23 替换 7.0.0-31 为默认；hold 6 meta 防 HWE 升级拉回；7.0 保留回滚。
- **D-8 ROCm 取舍**：amdgpu-install 用户态（7.2.1）安装成功；内核模块 DKMS 在 6.17 可编译（实证）但 7.0 失败；**最终 purge amdgpu-dkms 对齐 B（内嵌 amdgpu + KFD）**。ROCm 可用性以 6.17+内嵌 KFD 为基线。

---

## 3. 实施记录（关键步骤与实测）

### 3.1 接管与系统基线
- SSH 免密：主控 + GTR-Pro 公钥写入 C `authorized_keys`（C 站生成首对 key，pubkey 部署至 B 以支持 rsync 直推）。
- 初始内存 62G（BIOS/GRUB 未解锁）→ GRUB 参数 + update-grub + 重启 → **124G**（`/proc/cmdline` 验证 gttsize/pages_limit 在载）。

### 3.2 推理引擎
- llama.cpp 0d18aaa（源码树 rsync 自 B）；Vulkan build 补包：`glslang-dev glslang-tools spirv-tools spirv-headers`；**glslc 源自 B 站静态二进制拷贝**（noble 无 shaderc 包）。
- 引擎部署：`/etc/llama-instances/qwen3.8-27b-mtp.env`（模板自 B 适配路径）+ `llama-server@.service` + `llama-serve-instance` + froggeric jinja。
- 冒烟：`/props` n_ctx=8192 ✓、chat `finish_reason=stop` ✓、list-devices RADV GFX1151（121G）✓。

#### gpt-oss-120b 引擎（HIP llama，2026-09-12 落地）
- **背景 / 根因**：C 站默认 `infer-load` 以 **unsloth** 为后端、且虚拟设备名写死 **Vulkan0**，与 C 站实际不符——C 站无 unsloth 环境；设备被探测为 RADV GFX1151 / ROCm HIP（`ROCm0`），`--device Vulkan` 启动即 `Vulkan0 设备无效`失败。
- **处置**：改用 C 站 ROCm HIP build 的 `llama-server`（`/home/scott-lau/Applications/llama-gfx1151/llama-server`）。配置 `/etc/llama-instances/gpt-oss-120b.env`：`BACKEND=llama-single` + `LLAMA_SERVER_BIN=<HIP llama-server>` + `MODEL_PATH=/data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/gpt-oss-120b-MXFP4.gguf` + `PORT=8080`。经 `llama-server@gpt-oss-120b` systemd 托管运行。
- **格式坑**：追加 `LLAMA_SERVER_BIN` 时原文件无尾随换行导致其与 `BACKEND=` 行粘连、误读为单值 `llama-singleLLAMA_SERVER_BIN=`——用 `sed -i 's|^BACKEND=llama-singleLLAMA_SERVER_BIN=|BACKEND=llama-single\nLLAMA_SERVER_BIN=|'` 补换行修复。
- **验证（2026-09-12）**：`systemctl is-active` → `active`；`/health` → `{"status":"ok"}`；日志 `model loaded` / `server is listening on http://0.0.0.0:8080`；`/v1/chat/completions` 冒烟返回 HTTP 200 + `completion_tokens=16`（推理可用）。

### 3.3 环网
- B tbt1 → 10.10.11.1/24（NM「有线连接 4」）；C tbt0 → 10.10.11.3/24（NM「有线连接 3」）。
- A-C 段 10.10.12.0/24（A tbt1=…12.1、C tbt1=…12.3，mtu 9000 全段）；L2 计数器镜像实测证明 A-C 直连（RX/TX 逐字节对称）。
- 全向验证（iperf3 v3.16 / ping 50 包）：直连段 RTT avg 0.48ms、吞吐 9.06–9.25Gbps；A-B 9.11Gbps；**A-C 经 B 仅 31–35Mbps（B 转发瓶颈，已随 D-5 规避）**。

### 3.4 软件环境
- 5 deb：`amdgpu-install 30.30.1`(未运行安装器)、`clash-verge 2.4.5`、`docker-ce-cli 29.8.0` + `docker-desktop 4.74.0`、`lm-studio 0.4.14`、`trae-cn 1.107.1`。
- claude code CLI：NodeSource node20.20.2 + `npm -g @anthropic-ai/claude-code@2.1.258`（锁版本）；`~/.claude/settings.json`：`DISABLE_AUTOUPDATER=1`、`MAX_CONTEXT_TOKENS=120000`（base/auth 待路由决议）。
- 坑位记录：iperf3 安装 debconf 卡死锁 dpkg（kill 树 + `dpkg --configure -a` 恢复）；docker-ce-cli 依赖需官方源；npm 全局须 sudo（prefix /usr EACCES）；并发 apt 互抢锁。

### 3.5 ROCm 与内核
- `amdgpu-install --usecase=rocm`（302 包 / 6.7GB / 28.4G 解压）→ `/opt/rocm` + hipcc 就位。**DDKMS：6.17 编译 through，7.0 失败**；purge 对齐 B。
- 切 6.17（`grub-reboot 'Advanced options…6.17.0-23-generic'`，next_entry 验证）→ uname=/6.17/.0-23、124G、Vulkan 正常；**rocminfo 在 6.17 探到 gfx1151×2**（7.0 空）。

#### 2026-09-12 运维核查（三事项实锤）
- **⚠️ 6.17 默认启动未钉住（已修复）**：实测当前运行 7.0.0-31 而非 6.17。根因 `GRUB_DEFAULT="1>4"` 子菜单索引越界（该子菜单仅 0–3）→ GRUB 回退首项 7.0；meta 包虽 hold 但未钉默认内核。**修复**：`GRUB_DEFAULT="1>2"`（子菜单索引 2=6.17.0-23 normal）+ `update-grub`，`grub.cfg` 已 `set default="1>2"`，重启后落定 6.17。6.17 条目 cmdline 自带 `amdgpu.gttsize=120000 ttm.pages_limit=32000000 amd_iommu=off`（pages_limit 31288 已记录，当前 32000000 属同档合法值）。
- **✅ 「双 GPU」为误报**：硬件单 GPU（`c6:00.0` 1002:1586，Strix Halo 单 die；`numactl`=1 node/32 CPU；`/dev/dri` 单 card）。KFD 报 2 node 系 **node0 空占位（simd/gfx/device_id 全 0）+ node1 真 GPU（gfx1151, simd80, gws64）** 的拓扑冗余噪音，不影响运行（详情另见 §4 O8）。
- **✅ 「下载文件夹 7.X AMD 驱动」= ROCm 安装器遗留**：`/home/scott-lau/下载/amdgpu-install_7.2.1.70201-1_all.deb` 即 D-8 当初安装 `/opt/rocm 7.2.1` 用的安装器，非待升级驱动，无需处理。

### 3.6 管理面板（Cockpit / Beszel）
- **Cockpit**：Ubuntu 自带 cockpit.socket→按 B 站模式 drop-in `/etc/systemd/system/cockpit.socket.d/10-port.conf`（`ListenStream=` 清 9090 + `=9095`，A 站 9090 被 mihomo 占用故全集群统一 9095）→ `https://192.168.1.37:9095` http_code 200。⚠️ 勿用 `/etc/cockpit/cockpit.conf` 改端口（实测不生效，须 socket drop-in）。
- **Beszel agent**：`/usr/local/bin/beszel-agent` + systemd `beszel-agent.service`（Environment：TOKEN + HUB_URL=`http://10.10.11.1:8090`(B hub) + KEY=hub 签发 ed25519）。**KEY 含空格/`+`，Environment= 整行须用引号包整赋值**（`Environment="KEY=ssh-ed25519 …+"`），行尾反斜杠续行会吞掉下一行 `ExecStart=` 导致 `Refusing`（踩坑 2 次）。
- 生效验证：`journalctl` `WebSocket connected host=10.10.11.1:8090` ✓；网络接口探测 wlp195s0 + thunderbolt0/1 ✓；`rocm-smi deprecated` WARN 为适配 F2K 的常见噪音，无碍。

---

## 4. 当前状态与已知问题（Open Issues）

| # | 项 | 状态 / 处置 |
|---|---|---|
| O1 | **A-C 直连段 down（retimer 抖动）** | ✅ **已关闭（重插线缆）**：用户物理重插后两侧 tbt1 回归，路由恢复直连优先（A↔C ttl=64、引擎可达）。恢复流程：C 侧 tbt1 自动激活；A 侧 `nmcli con up 'thunderbolt1'` |
| O2 | **静态路由无自动 failover** | 主 nexthop 不可达不回落备路由（工程教训）；环网冗余硬化待做（多路径/监控切换） |
| O3 | C 站未纳入 agent-cli ROUTE_TABLE | **部分收口（2026-09-15 核实）**：统一入口侧已纳入 —— `cluster.py STATION_ROUTES` 有 `gpt-oss-120b-c` / `nvidia-nemotron-3-super-120b-a12b-c` / `qwen3.8-27b-mtp-c`，`STATIONS["C"]`/`STATION_PORT["C"]` 均已修正；C 站 station_runtime 工具链 11/11 实装（infer-load/unload/llama-serve-instance/load-gate/load-mem-gate/wait-gtt-release/cluster-ttl/cluster-watchdog/reqlog/plugin-probe/gguf-meta）。**剩**：agent-cli `$ROUTE_TABLE`（模型别名→站）仍无 C 条目 —— 现行派发走 `--RemoteHost 192.168.1.37`，是否需要给 C 加模型别名待定 |
| O4 | ROCm HIP llama 后端未实测 | ✅ **已实测（2026-09-12）**：gpt-oss-120b-MXFP4 经 HIP llama-server 加载 (PORT 8080, ctx131072)，health ok + 推理冒烟通过 |
| O5 | `claude` base URL/auth 未配 | ✅ **已解决（2026-09-09）**：C 站 `~/.claude/settings.json` baseURL = `http://127.0.0.1:8080/v1`（直连本地引擎，不经网关），claude 会话实测 `end_turn` ✅（见 [双端点调研 §2.2](../../docs/双端点部署与opencode混合框架调研.md)） |
| O7 | gpt-oss 引擎已就绪，未纳入 agent-cli ROUTE_TABLE | **同 O3**：统一入口 `STATION_ROUTES` 已含 C 站条目、`STATION_PORT["C"]=8080`；agent-cli `$ROUTE_TABLE` 仍无 C 模型别名（走 `--RemoteHost`） |
| O8 | ROCm 报“gfx1151×2”双设备 | **确认为误报**（2026-09-12）：物理单 GPU（gfx1151 单 die），KFD node0 为空占位（属性全 0）、node1 为真 GPU。观测时勿据 `×2` 误判双卡，真实可用计算在 node1 |
| O6 | AMD 官方 amdgpu 源 commit（repo.radeon.com 6.3.3/7.2）与 B 的 `Enabled:no` 差异 | C 保持 amdgpu 源存在但 DKMS purge；不进 apt 自动升级路径 |

---

## 5. 回滚与运作指引

- **内核回滚**：GRUB 菜单 7.0.0-31（保留）→ 或 `grub-reboot` 指定后重启；DKMS 无依赖（已 purge）。
- **环网回退**：静态路由配置在 NM/netplan 持久，回 B 段主路径即 `metric 102/200` 现状；A-C 恢复直连优先只需 tbt1 netdev 起来 + 对应连接 UP（metric 配置仍在）。
- **引擎**：`systemctl start|stop llama-server@qwen3.8-27b-mtp`；切档复用 B 站 `_switch_qwen_flavor.ps1` 模式（nothink 默认）。gpt-oss：`systemctl start|stop llama-server@gpt-oss-120b`；回 unsloth/`Vulkan0` 后端仅作为反例不推荐（设备无效）。
- **重要**：A/C 路由改动后若执行 `netplan apply`，A 站 tbt1 连接会被重激活踢走——需重 `nmcli con up 'thunderbolt1'`（已知坑）。

---

## 6. 待办（Next Steps）

1. HIP llama 后端实测（O4）——**2026-09-12 已由 gpt-oss-120b 落地**；qwen3.8 亦可用 HIP 档复用
2. A-C 直连恢复（O1）——物理线缆/boltctl，恢复后路由回直连优先
3. 环网 failover 硬化（O2）——多路径路由或监控脚本
4. C 站接入 agent-cli ROUTE_TABLE（O3）+ 引擎并行调度（O7）——qwen3.8(18080) 与 gpt-oss(8080) 并存 + claude 网关接入（O5）
5. 复用节点登记：nodes.env（RPC_NODES）、cluster-bench DESIGN §3 已同步 C=10.10.11.3:50052