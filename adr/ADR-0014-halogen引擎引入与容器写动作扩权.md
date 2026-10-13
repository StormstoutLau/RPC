# ADR-0014: halogen 引擎引入（A 站 · 测试性）+ 容器管理扩权（只读 → 写动作）

---------------------------------------------------------------------

id: ADR-0014
type: adr
version: 2.1
status: accepted
date: 2026-10-10
updated: 2026-10-11
depends: [ADR-0004, ADR-0012]
upstream: [ADR-0004]

---------------------------------------------------------------------

> **Feature**: ① **立项引入**第三方 OCI 推理引擎 **halogen**（`ghcr.io/peonist-ai/halogen-flash-server`，
> 用于给 **Qwen3.8-Flash-Next** 做本地加速，**三站 · 测试性** —— A 站首发，B/C 于 v2.1 复用落地）；
> ② 把 `ADR-0012` 的容器管理能力**从「只读」扩到「写动作」**（`pull` / `up` / `down`）——
> 仍走**唯一管理面** `ops/cluster.py`，**默认 `--plan`、`--go` 才动手**，**不新增并列脚本**。
> **创建日期**: 2026-10-10 ｜ **修订**: 2026-10-11（**v2.0**：A 站真部署落地 + D7/D8 新增；**v2.1**：B/C 复用落地真部署 + D7 前置解 + ports.yaml scope 同步）
> **状态**: accepted（**立项 + A/B/C 三站真部署已落地**；`containers` 子命令见 §验证 · V6/V6.1 见 §验证）
> **适用**: 三站 halogen 测试性部署的准入、端口真值、安全边界；`cluster.py containers` 写动作的授权边界
> ★ 本 ADR **不**改变宿主 `dockerd` / `containerd` 的系统服务归属，**不**为 halogen 的**生产可靠性**背书。

---------------------------------------------------------------------

## 元数据

| 字段   | 值 |
| ---- | ---- |
| 编号   | ADR-0014 |
| 日期   | 2026-10-10 |
| 状态   | accepted |
| 决策者 | Scott (鹏) |
| 相关文档 | [ADR-0004](ADR-0004-统一管理入口为唯一管理面.md)（唯一管理面）· [ADR-0012](ADR-0012-A站容器栈纳管.md)（A 站容器栈纳管 · **D5 明文排除推理栈背书**）· [Qwen3.8 系列本地推理加速调研](../docs/research/2026-10-01_Qwen3.8系列本地推理加速调研.md)（§5 三闸 / §7 站选择 / §8.1 P1–P3 / §9 未核清单）· [`inventory/ports.yaml`](../inventory/ports.yaml) · [`ops/station-bin/load-gate`](../ops/station-bin/load-gate) |
| 取代   | 无（新增）；对 `ADR-0012` **D2 的增量**（只读 → 只读 + 写动作），**不取代** `ADR-0012` |

**证据等级约定**: E1=本会话实测；E2=前会话实测留档；E3=外部文档；E4=推断。

---

## 背景（Context）

1. **需求**：为 **Qwen3.8-Flash-Next**（站上已有 BYO GGUF，三站齐备，`UD-IQ4_XS` 三片 ≈ 93.7 GB）
   寻求**本地推理加速**。第三方 OCI 引擎 **halogen** 提供了一条**非 llama.cpp** 的路径：
   镜像 `ghcr.io/peonist-ai/halogen-flash-server`（**v0.17.4**；**镜像体积未公开**，E3 上游），
   容器内服务端口 **8730**、对外发布端口 **8731**；BYO GGUF 额外只需 draft head
   **`qwen38-flash-next-mtp.hgn`（1.42 GiB）** + tokenizer（E3 上游）。引擎**单硅片写死、无 RPC / 无多机**。
2. **★ 不能搭 `ADR-0012` 的车（E1，本仓读档）**：`ADR-0012` **D5 明文排除**
   ——「本 ADR **不**为任何推理栈（vLLM / kyuz0 / ds4）背书 …… **不**新增任何镜像、**不**改变引擎拓扑」。
   ⇒ halogen 的引入**必须另立 ADR**（本条），且**不得**被读成 `ADR-0012` 的延伸。
   （调研文档 §8 与 §11 两处均已写明此边界，本条与之一致、**不造第二份裁定**。）
3. **★ 站选择 = A 站（E1，本会话 2026-10-10T19:29 实测）**：
   - **A 站是唯一容器栈就绪站**：`systemctl is-active docker` = `active`、有 `/usr/bin/dockerd`、
     docker 组齐、**`video` / `render` 组齐**（halogen 的 `--group-add` 前置）；
   - **B / C 站无 `dockerd` 二进制、无 `docker.service`**（B 还缺 `video` 组）⇒ 容器路径**只**在 A 站可行；
   - **`8730` / `8731` 三站均 FREE**；`ghcr.io` 三站可达（DNS `20.205.243.164`，HTTP 405 = registry 响应）；
   - A 站 IOMMU = **默认开**（无 `iommu` 内核参数；C 站为 `amd_iommu=off`）。
4. **★ `ADR-0012` 已立项但实现未落地（E1，本仓读档）**：`ADR-0012` **D2** 的首期能力
   `cluster.py containers status` **至今未实现**（其 V3 标「未做」；`DEVELOPMENT-LOG` 亦登记为未做）。
   ⇒ 本 ADR 在引入引擎的同时，**必须**把 `ADR-0012` D2 的只读首期**落地**，
   并把**写动作**（`ADR-0012` D2 预留的「日后若要」）**一并扩权**，否则「经统一入口执行 docker」无对象可用。
5. **风险面（E3，上游 + 常识）**：
   - **供应链**：镜像是**第三方**制品，且**体积未公开** ⇒ 拉取前**无法**预估占盘；
     digest **未钉死**；
   - **★ 引擎协议无鉴权**：上游配置表逐字 *"The engine protocol has no authentication; keep it unpublished."*
     ⇒ 宿主发布端口**必须**绑 **loopback**（`-p 127.0.0.1:8731:8731`），**不得** `0.0.0.0`；
   - 该引擎**与既有 llama.cpp / unsloth studio 栈并列**，属**另起拓扑**（非替换）。

---

## 决策（Decision）

### D1. **引入** halogen 引擎（立项）—— 单站 · A 站 · 测试性
在 **A 站**引入 `ghcr.io/peonist-ai/halogen-flash-server`（**v0.17.4**）作为**测试性**推理引擎，
用途 = 给 **Qwen3.8-Flash-Next** 做本地加速。形态：
- **BYO GGUF**：复用站上既有 `UD-IQ4_XS` 权重；额外只需 draft head `qwen38-flash-next-mtp.hgn`（1.42 GiB）+ tokenizer；
- **单硅片写死**：**无 RPC / 无多机** ⇒ 与既有 RPC 双机编排**无关**，**不**并入 `BACKENDS`；
- **测试性 ≠ 常驻**：**不**替代、**不**改动既有常驻引擎与拓扑；验证结束即按 `down` 回收。

### D2. 容器管理能力**从「只读」扩到「写动作」**（对 `ADR-0012` D2 的增量）
- 统一入口 `ops/cluster.py` **新增 `containers` 子命令**（`ADR-0004` D2：新管理能力 = 加子命令，**不新增并列脚本**）：
  - **`status`**（**只读**，落地 `ADR-0012` D2）：三站 `docker ps -a` / `docker images` / `docker compose ls` + 端口对账；
    **恒 `exit 0`** 且**必须显式报「无容器」**（`ADR-0012` D2 判据），**不得**打印空；
  - **`pull` / `up` / `down`**（**写动作**，`ADR-0012` D2 预留的「日后若要」）：
    ★ **默认 `--plan`（只打印将下发的命令，不连站执行）**，**`--go` 才动手**（与 `models` / `flow` / `egress borrow` 既有约定一致）。
  - **`install`**（**写动作**，★ **2026-10-11 v2.0 增量**，见 D8(a)）：给站上补 **dockerd / docker.service**
    （B/C 实测「**有 CLI、无 daemon**」）；**幂等**（已有 dockerd 且 `docker` active ⇒ 跳过），
    **默认 `--plan`、`--go` 才动手**；与 A 站配置对齐（apt 源 + systemd unit + ssh 用户进 `docker` 组 + `daemon.json` 镜像源）。
- **复用** `cluster_ssh.ssh_run`（唯一建连入口）；写动作**须**以 `strict=True` 取远端退出码，
  **不**把「没抛异常」当成功（`ssh_run` 默认语义）。
- **零新入口、零新脚本**：不写一次性 `ssh + docker` 脚本（`ADR-0004` D2 正是要拦该形态）。

### D3. 端口真值收敛 —— `8730` / `8731` 一律进 `inventory/ports.yaml`
- **`8731`**（**宿主对外发布**）：`scope: [A]` · `bind: 127.0.0.1` · `mode: on_demand` ·
  `owner: "docker (halogen-flash-server)"` · `status: configured_but_stopped`
  ⇒ 未监听**不算故障**（豁免本表「声明在用却没监听」的反向对账）。
- **`8730`**（**容器内**端口）：按 `ADR-0012` D3 口径**同表登记**，说明其**不在宿主监听面**（无 scope 歧义）。
- `containers status` **对账**：把容器**已发布宿主端口**与 `ports.yaml` 比对，未登记即**报出**
  （把 latent 撞车从「下次 `up` 才发现」提前到**登记时可见**）。⚠ 站上占用对账的**权威**仍是 `rpc_check` 的 `ports` 断言，
  本条**不**复刻其站上扫描（**不造第二份真值**）。

### D4. 安全边界（**硬约束**，非建议）
- **必须 loopback 发布**：`publish` 的宿主绑定**只准** `127.0.0.1`（引擎协议无鉴权，见 §背景 5）；
  `containers` 的 `up` 对非 loopback 的 `publish` **报警**。
- **GPU 分组 = 数字 GID（★ 2026-10-11 实测回写，取代原「组名」写法）**：`--group-add 44 --group-add 992`
  （即 `video` / `render` 的 GID）。★ **原写法 `--group-add video --group-add render` 实测 `docker run` rc=125**
  —— `unable to find group render: no matching entries in group file`（**虽 host `/etc/group` 有 `render:x:992`**）
  ⇒ 容器运行时**按名字解析组会失败**，**按数字 GID 才过**。上游 Docker 路径的语义不变（仍是 Docker，非 Podman 的 `keep-groups`）。
- **不改宿主归属**：`dockerd` / `containerd` 的系统服务归属**不属**本 ADR 射程（承 `ADR-0012` D4）。

### D5. 失效条件与回退（默认可撤）
- **失效条件**：镜像拉取失败 / 与站上内核或驱动不兼容 / 冒烟或基准不达标 / 占盘不可接受 —— 任一即 **`down` 回收**。
- **回退**：回到既有 **unsloth studio（8080）** 路径；本 ADR **不动**既有引擎与端口。
- **状态**：本条**不**把 halogen 升格为常驻/default；升级须另裁（承 `ADR-0012` D5 的精神）。

### D6. 供应链与证据边界（**如实标注，不假装已受控**）
- 镜像是**第三方制品**、体积**未公开**、**digest 未钉死** ⇒ 本 ADR 只**立项**，
  **不**审查容器内权限、**不**审计镜像供应链；★ **别把「已纳管」读成「已合规」**（同 `ADR-0012` 后果一节）。
- **不足以支撑生产**：本条批准的是**测试性**验证，**不是**生产采用。

---

### D7. **「Qwen3.8-Flash-Next 默认执行框架 = halogen」**（用户裁定 2026-10-11；★ 本条即 D5 预留的「升级须另裁」）

- **触发（E1，用户原话）**：*"qwen 3.8 flash next 加载推理默认用 halogen 框架执行"*。
- **含义**：`qwen3.8-flash-next` 的**默认后端**由既有 llama.cpp / unsloth studio 路径改为 **halogen**（OpenAI 兼容 API，**三站**各自 `127.0.0.1:8731`）；既有路径**降为非默认 / 回退**。
- **联动面（须一并改，否则「默认」是空话）**：`ops/cluster.py` 的 `ROUTE` / `BACKENDS`（按站路由 `qwen3.8-flash-next-{a,b,c}`）；`ops/rpc_check.py` 的路由断言；`load-gate` 的容器占用判据；`inventory/models.yaml` 的 `route` 字段。
- **★ 前置已解（E1 2026-10-11）**：D7 要求「默认框架」在**三站**都成立 ⇒ 前提是 B/C **也能跑 halogen**。该前提由 **D8(a) 落地 + B/C 真部署**（见 §V6.1 实证）**已满足**：三站 `containers status` 均 `docker: active` 且各起 `halogen` 容器、`/health` = `ok`、冒烟同档。
  ★ 用户指令为「**D7 文档等 BC 复用配置成功后更新**」⇒ 本节**按 BC 复用成功**回写；**代码层**（`ROUTE`/`BACKENDS`/`rpc_check`/`load-gate`/`models.yaml`）仍**未改**，**待用户确认后**执行（见未实测登记 #8）。
- ⚠ 与 **D1「测试性 ≠ 常驻」** 的关系：D7 是**升格**，D1 是**引入形态**。D7 生效后，三站 halogen 从「测试性」变为「Qwen3.8-Flash-Next 的默认执行框架」。

### D8. **B/C 两站复用 A 站配方 —— ★ 已落地并真部署（E1 2026-10-11）**

- **用户要求**：*"B C 两站复用 A 站配置结果"*。
- **★ 实测起点（阻断事实）**：B/C **均有 docker CLI**（B `29.6.0` / C `29.8.2`，`/usr/local/bin/docker`）与 `video`/`render` 组、`/dev/kfd`、`/dev/dri`（GID **992**），但 **无 `dockerd` 二进制、无守护进程、无 `docker.service`**（`systemctl is-active docker` = `inactive`、`is-enabled` = `not-found`；`docker info` 只出 Client 段）⇒ **「有 CLI、无 daemon」**。
- **★ 用户裁定 = (a)**（2026-10-11）：给 B/C 装 `dockerd` / `docker.service`（**不**放开 A 站 loopback、**不**退为「只在 A 站跑」）。
- **★ 落地（E1）**：经统一入口 **`cluster.py containers install --go`**（新增动作，见 **D2** 增量）——
  B/C 由 apt 装 `docker-ce` + `containerd.io`（B：**修 dist-upgrade 改名** `.distUpgrade`→`.list`，源 tuna 镜像；C：源已活，`download.docker.com`）
  + `systemctl enable --now docker` + 把 ssh 用户 `scott-lau` 加进 `docker` 组 + `daemon.json` 对齐 A 站 4 镜像源。
  **结果**：B `dockerd 29.9.0` / C `dockerd 29.8.2`，`systemctl is-active docker` 均 **active**；
  `containers status` 三站 **docker: active**（A 站幂等自跳过 ⇒ 未改动）。
  ★ **另修**：B 站 docker CLI `currentContext=desktop-linux`（指向未启的 Docker Desktop socket ⇒ `docker` 全废）
  ⇒ `install` 脚本首尾均 `docker context use default` 对齐 A/C。
- **★ 真部署（E1，完成）**：B/C 经 `cluster.py containers up --go`（**照抄 A 站配方**：数字 GID 44/992 + `--ipc=host`
  + `--ulimit memlock=-1:-1` + `-v <UD-IQ4_XS>:/models`（rw）+ `HALOGEN_CHECKPOINT`/`HALOGEN_DOWNLOAD`/`HF_ENDPOINT`/`HF_HUB_DISABLE_XET`
  + `-p 127.0.0.1:8731:8731`）各起 `halogen` 容器 ⇒ `/health` = `ok`、冒烟（短 prompt）与 A 站**同档**
  （MTP serial：A `36.29` / B `34.27` / C `34.50` t/s）。实证见 **§V6.1**。
- **备选（未采纳）**：**(b)** 放开 A 站 `8731` 绑定（现 loopback）让 B/C 远程调用 ⇒ **直接撞 D4 硬约束**（引擎协议无鉴权）；
  **(c)** 暂只在 A 站跑。★ 上游事实：该引擎**单硅片写死、无 RPC / 无多机**（承 D1）⇒ 「B/C 复用」**不可能**靠 halogen 自己跨机。
- ⚠ **后续**：`8730` / `8731` 的 `inventory/ports.yaml` **scope 已由 `[A]` → `[A, B, C]`**（B/C 也 loopback 监听 8731，
  否则 `rpc_check --only ports` 反向对账会把 B/C 判为「有监听未登记」）。

---

## 考虑的替代方案（Alternatives Considered）

| # | 方案 | 为何不采纳 |
|---|---|---|
| 甲 | **不引入**，只用既有 llama.cpp / unsloth 栈 | 无法验证 halogen 的加速假设；且既有 `O-121` 裁「当前不引入第三方容器」针对的是**当时的候选**，本条的触发是**用户 2026-10-10 明示要测 halogen** ⇒ 需**重裁**而非沿用 |
| 乙 | **搭 `ADR-0012` 的车**（把它当作推理栈纳管的延伸） | `ADR-0012` **D5 明文排除**「不为任何推理栈背书 / 不新增镜像」⇒ 搭车 = **直接违反**该 ADR；且会造成「**同一栈两处裁定**」 |
| 丙 | 在 **B / C 站**部署（算力或负载更优） | **E1 实测**：B / C **无 `dockerd` 二进制、无 `docker.service`**（B 还缺 `video` 组）⇒ 容器路径**当场不可行** |
| 丁 | 写**一次性 `ssh + docker` 脚本**部署 | 正是 `ADR-0004` D2 与 `ADR-0012` D2 要拦的形态（**动作在入口之外发生**）；且新增 `ops/` 脚本会被 `scripts` 断言拦 |
| 戊 | 用 **Podman** 或**裸进程**方式运行 | 上游 Docker 支持路径明确（`--group-add`）；站上**只有 Docker**（Podman 的 `keep-groups` 需另装）⇒ 多引入一个运行时，收益不明 |
| 己 | 只做 `status`、**暂不做写动作**，部署时手敲 `docker` | 会把「真部署」逼回一次性 ssh 命令（= 丁 的变体）；`ADR-0012` D2 已预留写动作「仍是同一入口子命令」⇒ 现在一并落地更省一次返工 |

---

## 后果（Consequences）

**正面**
- halogen 的引入从「**管理面外**」变为「**有 ADR、有入口、有端口真值、有判据**」；
- `ADR-0012` D2 的**只读首期**（V3 长期挂账）**落地**，且写动作**一并**就位 ⇒ 第 4 步部署可**只经统一入口**完成；
- 复用 `cluster_ssh` + 加子命令 ⇒ **零新脚本**（`scripts` 断言不受影响）。

**代价 / 风险**
- `cluster.py` 增 `containers` 子命令 ⇒ 模块 docstring（用法表 + 子命令清单）须**同步**；
  ⚠ 新 `cmd_*` 符号**不**会触发 `facade` 断言 FAIL，只会让「无消费者引用」报数 +1 ⇒ **需人读报数**。
- **测试性部署会占用 A 站磁盘与（若有）GPU 显存** ⇒ 与既有常驻模型**竞争**；
  `load-gate` 的既有判据**看不见 docker 容器**（其 `rssm` 只统计 `llama-server` 等进程名）
  ⇒ 本条**顺带**给 `load-gate` 补「容器占用」判据（见 §验证 V4）。
- ★ **「已纳管」≠「已安全」**：供应链 / 容器内权限 / digest 均**未**受控（D6）。

---

## 验证（Validation）

| # | 判据 | 状态 |
|---|---|---|
| V1 | `cluster.py containers status` 可跑、**恒 `exit 0`**、且**显式报「无容器」**（A 站） | ⏳ 本轮落地（见下节 U1） |
| V2 | `containers pull/up/down` **默认只出计划**；`--go` 才下发；写动作走 `ssh_run(strict=True)` | ⏳ 本轮落地（夹具 + 参数解析） |
| V3 | `8730` / `8731` 进入 `inventory/ports.yaml`，`inventory` + `ports` 两条断言 **PASS** | ⏳ 本轮落地 |
| V4 | `load-gate` 能看见 **docker 容器占用**（facts 行显示容器数/内存 + 有容器时 **WARN 级**判据）；★ **不改**既有三闸的算术判据 | ⏳ 本轮落地 |
| V5 | 门禁 `scripts` 未因本条新增未登记脚本；`run_py_tests` 全绿 | ⏳ 本轮复跑确认 |
| V6 | halogen **真部署**（拉镜像 → 取 draft head → BYO GGUF 起容器 → 冒烟 + serial decode 短/长 ctx） | ✅ **已做**（2026-10-11 · **A/B/C 三站**；A 站实证见 §V6，B/C 复用实证见 §V6.1） |

---

## §V6 实证（2026-10-11 · A 站 · E1）

**结论**：halogen 在 A 站**真部署上线并跑通冒烟**，`/health` = `status: ok`、`checkpoint_format: gguf`、
api/engine 均 `0.17.4`、`chat_template.probe: passed`、`drafter_weights_loaded: true`。
全程**只经** `ops/cluster.py containers pull/up/down`（含 `--plan` 预演），无一次性 ssh 脚本。

### 1. 镜像（供应链口径上修）
- **拉取路径**：`ghcr.io` 直连在 A 站**停滞**（8s RX ≈ 12–18 KB/s）⇒ 按用户拍板走南大域名替换
  **`ghcr.nju.edu.cn`**（实测 ≈ **5.5 MB/s**）。
- **落地**：镜像 **4.56 GB**，digest **`sha256:485cc8cb0adc7159b985772a5bbb368ab73bcb3d201eabbf32abb0cf6b655ca8`**
  （⇒ 本 ADR §D6「体积未公开 / digest 未钉死」在**本次实测**中**已获净值**，见未实测登记 #2）。
- ★ 域名替换**不改** digest 语义（同制品同摘要）；南大镜像为**社区镜像**，非上游背书。

### 2. 模型（BYO GGUF + 专用 head/tokenizer）
- **BYO GGUF**：复用 A 站既有 `UD-IQ4_XS`（`/data/models/gguf/lmstudio-community/Qwen3.8-Flash-Next-GGUF/UD-IQ4_XS/`，
  三片 ≈ 93.7 GB）——`HALOGEN_CHECKPOINT` 指向**任一分片**，兄弟片按名自寻。
- **★ 专用 head/tokenizer（用户 2026-10-11 纠正）**：halogen 用的是 Qwen3.8-Flash-Next 的**专用打包**
  （`peonist-ai/halogen-qwen3.8-flash-next`）；即便 BYO GGUF，也**必须**自该专用仓库取
  **MTP draft head** `qwen38-flash-next-mtp.hgn`（**1,523,566,720 B ≈ 1.42 GiB**）+ tokenizer。
  ⇒ 上游「BYO GGUF 免转换」**不等于**「站上既有权重即完整」。
- **取件走 `HALOGEN_DOWNLOAD`**（HF repo id，只取所需：head + tokenizer），需 **models 卷可写**（rw）。

### 3. 内存与端口
- 权重 **72.0 GiB** 锁定 + KV **14.4 GiB** + 工作 **12.8 GiB** = **99.2 GiB**，`host memory left 22.0 GiB`。
- **引擎 `127.0.0.1:8730`（未发布）**；**API 发布 `127.0.0.1:8731`**（loopback，守 D4）。

### 4. 冒烟（serial decode 短/长 ctx）
prompt set = **上游 `tools/eval-prompts.json`**（10 例：code/proof/proc/chat/prose × a/b）；
数据取自**引擎 ledger 行**（`serve_api: batch N tok in Xs = Y t/s`｜`mtp … R rounds, commit Z/round`）。

| 场景 | serial decode | MTP |
|---|---|---|
| 短 ctx（`code_a`） | **27.83 t/s** | **51.87 t/s** |
| 长 ctx（≈30k） | **27.28 t/s**（**无塌缩**） | **39.35 t/s** |

- 长 ctx prefill ≈ **1595 t/s**（18.85 s）。
- 对照既有 llama.cpp 基线：**长 ctx 塌缩 5.5–6.1 t/s** ⇒ 本引擎**未复现该塌缩**（加速假设**初证**，口径须写明）。

### 5. 相对原设计的**三处修正**（★ 均为实测倒逼，非偏好）
1. **镜像域名**：`ghcr.io` → **`ghcr.nju.edu.cn`**（直连停滞）。
2. **`--group-add`**：原设计（D4）字面 `video` / `render` ⇒ `docker run` **rc=125**
   （`unable to find group render`，虽 host `/etc/group` 有 `render:x:992`）。改用**数字 GID**
   **`--group-add 44 --group-add 992`** → rc=0。★ **此为对 D4 字面的偏离**，须登记（见未实测登记 #7）。
3. **出网**：`huggingface.co` 从 A 站 `http=000` ⇒ 容器报 `[Errno 104] Connection reset by peer`
   （5 次重试全败，引擎 `no draft head …`）。加 `-e HF_ENDPOINT=https://hf-mirror.com`（实测 **8.8 MB/s**）；
   另 Xet 后端 **401** ⇒ 加 `-e HF_HUB_DISABLE_XET=1` 后方取到 tokenizer 并启动成功。

### 6. 副作用（已登记，未静默）
容器向站上**共享权重目录**（`…/UD-IQ4_XS/`）**写入**：`qwen38-flash-next-mtp.hgn`（1.5 GB，owner root）、
`tokenizer/`、`.cache/`（owner root）。⇒ 该目录**不再只读**；清理须 `down` + 手工删落物（见未实测登记 #9）。

---

## §V6.1 实证 —— B/C 复用（2026-10-11 · E1）

**结论**：B/C **照抄 A 站配方**（D8(a)）真部署成功，`containers status` 三站均 `docker: active` +
各 1 个 `halogen` 容器（`127.0.0.1:8731->8731/tcp`）；三站 `/health` = `status: ok`；冒烟（同一短 prompt，code-only）
三站**输出一致**、MTP serial 吞吐**同档**：**A `36.29` / B `34.27` / C `34.50` t/s**。

- **统一入口**：全程只经 `ops/cluster.py containers install --go`（补 daemon）+ `containers up --go`（起容器），
  无一次性 ssh 脚本（守 `ADR-0004` D2）。
- **镜像**：B/C 拉取落盘 **4.56 GB**，digest **`sha256:485cc8cb…f6b655ca8`**（与 A 站**同一制品**）。
- **取件**：B/C 首次起容器时经 `HALOGEN_DOWNLOAD` + `HF_ENDPOINT=https://hf-mirror.com` + `HF_HUB_DISABLE_XET=1`
  自 `peonist-ai/halogen-qwen3.8-flash-next` 取 head（`qwen38-flash-next-mtp.hgn` 1,523,566,720 B）+ tokenizer（≈ 60–90 s）。
- **加载**：GGUF repack（1166 tensors → 70.55 GiB）后 `/health` = ok（B ≈ 1 min，C ≈ 2 min）。
- **副作用（同 A 站，已登记）**：B/C 的 `UD-IQ4_XS/` 亦被写入 `qwen38-flash-next-mtp.hgn` / `tokenizer/` / `.cache/`（root 属主）。

---

## 未实测登记（不静默）

1. ~~**`containers` 子命令与真部署分两批**~~ **→ 已实测（2026-10-11 · A 站）**：V6 对象即本轮真部署，全程只经统一入口。
2. ~~**镜像 digest 未钉死、体积未实测**~~ **→ 已实测**：4.56 GB、digest `sha256:485cc8cb…f6b655ca8`（见 §V6 实证 1）。
   ⚠ **仍开放**：digest **未写入**任何 pin 文件/配置（本次仅记录，**未**固化为引用）。
3. ~~**A 站 IOMMU = 默认开，halogen 在该内核/驱动组合下是否可用未实测**~~ **→ 已实测**：A 站（内核 6.17.0-40-generic）**可用**，冒烟通过。
4. ~~**`--group-add video/render` 的实际效果未验**~~ **→ 部分实测**：容器内 GPU **可见且推理成功**；
   ⚠ 但生效值是**数字 GID**（44/992），**非** D4 字面的组名 —— 见 #7。
5. ~~**加速假设未验（serial decode 对比未做）**~~ **→ 初证实测**：短/长 ctx serial **27.83 / 27.28 t/s**、
   长 ctx 无塌缩（llama.cpp 基线 5.5–6.1）⇒ 加速假设**成立**（见 §V6 实证 4）。prompt set 已写明（`tools/eval-prompts.json`）。
6. **与 A 站既有容器的相互影响未评**（**仍开放**）：`~/searxng` 等既有 compose 栈与本引擎的**资源竞争未测**。
7. **★ D4 组名口径偏离未回写**（**新登记**）：实证用**数字 GID** 44/992 成功，D4 字面 `video`/`render` 失败（rc=125）；
   ⇒ 待用户在「(i) 回写 D4 为数字 GID / (ii) 保留组名但登记例外」间裁定。
8. **★ D7「默认执行框架 = halogen」落地未做**（**新登记**）：裁定已下（见 D7），但 `cluster.py` `ROUTE`/`BACKENDS`、
   `rpc_check` 路由断言、`load-gate`、`models.yaml` `route` **均未改**。
9. **★ 共享权重目录落物未清理**（**新登记**）：`down` 后 `qwen38-flash-next-mtp.hgn` / `tokenizer/` / `.cache/`（root 属主）
   仍留在 `UD-IQ4_XS/`；**未**定是否保留（复起加速）或删除。
10. ~~**B/C 复用 A 配方仍阻断**~~ **→ 已解（2026-10-11）**：用户裁定 **(a)** ⇒ 经 `containers install` 补 daemon + `containers up` 真部署，
    B/C `/health` = ok、冒烟同档（见 §V6.1）。⚠ **仍开放**：B/C 侧既有容器/负载与本引擎的**资源竞争未测**（与 #6 同类）；
    `8730/8731` 的 `ports.yaml` **scope 已同步 `[A, B, C]`**（见 D8 后续）。

---

## 修订历史

| 版本 | 日期 | 变更 |
|---|---|---|
| 1.0 | 2026-10-10 | 立项：D1–D6（halogen 引入 A 站测试性 / 容器写动作扩权 / 端口真值 / 安全边界 / 失效回退 / 供应链边界）；替代方案甲–己。承 `ADR-0004` · `ADR-0012`。 |
| 2.0 | 2026-10-11 | **A 站真部署落地**（V6 由「未做」→「已做」，新增 §V6 实证：镜像 digest/体积、BYO GGUF + 专用 head/tokenizer、内存/端口、冒烟短/长 ctx、**三处实测修正**、副作用）；新增 **D7**（Qwen3.8-Flash-Next 默认执行框架 = halogen，裁定已下/落地未做）与 **D8**（B/C 复用 —— 实测「有 CLI、无 daemon」阻断，备选 a/b/c）；未实测登记重排（#1–#5 标已实测、新增 #7–#10）。 |
| 2.1 | 2026-10-11 | **B/C 复用落地真部署**（D8(a)：`containers install` 补 daemon + `containers up` 照抄 A 配方；B/C `/health` ok、冒烟同档，新增 **§V6.1 实证**）；**D7 前置解**（三站均可跑 halogen ⇒ 默认框架前提已满足，代码层仍待确认）；`8730/8731` 的 `inventory/ports.yaml` **scope `[A]`→`[A, B, C]`**；未实测登记 #10 标已解。 |