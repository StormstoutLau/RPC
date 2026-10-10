# ADR-0014: halogen 引擎引入（A 站 · 测试性）+ 容器管理扩权（只读 → 写动作）

---------------------------------------------------------------------

id: ADR-0014
type: adr
version: 1.0
status: accepted
date: 2026-10-10
depends: [ADR-0004, ADR-0012]
upstream: [ADR-0004]

---------------------------------------------------------------------

> **Feature**: ① **立项引入**第三方 OCI 推理引擎 **halogen**（`ghcr.io/peonist-ai/halogen-flash-server`，
> 用于给 **Qwen3.8-Flash-Next** 做本地加速，**单站 · A 站 · 测试性**）；
> ② 把 `ADR-0012` 的容器管理能力**从「只读」扩到「写动作」**（`pull` / `up` / `down`）——
> 仍走**唯一管理面** `ops/cluster.py`，**默认 `--plan`、`--go` 才动手**，**不新增并列脚本**。
> **创建日期**: 2026-10-10
> **状态**: accepted（**立项**；`containers` 子命令见 §验证 · 真部署见「未实测登记」）
> **适用**: A 站 halogen 测试性部署的准入、端口真值、安全边界；`cluster.py containers` 写动作的授权边界
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
- **GPU 分组**：按上游 Docker 官方支持路径 `--group-add video --group-add render`（Podman 需 `keep-groups`，
  但站上只有 Docker ⇒ 走 Docker 路径）。
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
| V6 | halogen **真部署**（拉镜像 → 取 draft head → BYO GGUF 起容器 → 冒烟 + serial decode 短/长 ctx） | ⏳ **未做**（见下节 U2；本轮只做地基） |

---

## 未实测登记（不静默）

1. **`containers` 子命令与真部署分两批**：本轮只落地 **`ADR-0012` D2 + 本 ADR D2 的地基**
   （ADR / 子命令 / 端口登记 / `load-gate` 判据）；**halogen 真拉镜像与真部署未做** ⇒ V6 无对象。
2. **镜像 digest 未钉死、体积未实测** ：拉取前无法预估占盘；`docker pull` **未跑过一次**
   （与 `ADR-0012` 未实测登记 #4 同族：**「配置可达」≠「能拉到」**）。
3. **A 站 IOMMU = 默认开**（E1 已核内核参数）；但 **halogen 在该内核/驱动组合下是否可用，未实测**。
4. **`--group-add video/render` 的实际效果未验**：仅确认**组存在**，未确认容器内 GPU 可见。
5. **加速假设未验**：halogen vs 既有栈的 **serial decode** 对比**未做**（§8.1 P2 未执行）；
   ★ 若做，prompt set **必须写明**（否则口径不可复现）。
6. **与 A 站既有容器的相互影响未评**：`~/searxng` 等既有 compose 栈与本引擎的**资源竞争未测**。

---

## 修订历史

| 版本 | 日期 | 变更 |
|---|---|---|
| 1.0 | 2026-10-10 | 立项：D1–D6（halogen 引入 A 站测试性 / 容器写动作扩权 / 端口真值 / 安全边界 / 失效回退 / 供应链边界）；替代方案甲–己。承 `ADR-0004` · `ADR-0012`。 |