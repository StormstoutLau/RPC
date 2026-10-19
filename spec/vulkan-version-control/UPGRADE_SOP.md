# UPGRADE_SOP.md — llama.cpp Vulkan 后端两站原子升级 SOP

> **Feature**: vulkan-version-control（M4 交付物）
> **前置**: 第 0 步已完成（9859 已版本化，`/opt/llama.cpp` 为 symlink）
> **适用**: 升级到上游新版本（tag 形如 v0.2.0 / b10xxx）
> **原则**: 两站视为一个原子整体 — B 站单点构建，产物分发，symlink 同步切换
>
> ★ **命名约定（2026-10-11 校正）**：本文 `<ver>` = `/opt/llama.cpp-<ver>` 的**标识**，
> **实测形态 = `master-<短commit>`**（如 `master-91f6a6cf`），**不是** `v0.2.0` 式版本号
> —— ★ **现役 symlink = `/opt/llama.cpp-master-23b0202a`**（三站一致，**2026-10-12 升级**；升级前为 `master-91f6a6cf`）。
> 下称"标识"为 `<id>`，`<ver>` 与 `<id>` 本文同义。

---

## 升级六步流程

### 1. 停服务

```bash
# B 站 (Master)
ssh scott-lau@scott-lau-GTR-Pro.local "pkill -x llama-server"
# A 站 (Worker) rpc-server 可保留运行（不影响文件切换），但建议一并重启以加载新库
```

### 2. B 站构建（唯一构建源）

> ★ **2026-10-11 路径校正（照旧文会在 `cd ~/src/llama.cpp` 处直接失败）** —— 以三站实测为准：
>
> | 项 | 旧文（已过期） | 实测现状（E1） |
> |---|---|---|
> | 源树 | `~/src/llama.cpp` | **按目标命名**：`~/src/llama.cpp-<id>`（先例 `llama.cpp-master-91f6a6cf` · `llama.cpp-glm5next-upstream`） |
> | 构建目录 | `~/build/llama-<ver>` | `~/build/llama-<id>`（先例 `~/build/llama-master-91f6a6cf`） |
> | 版本目录 | `/opt/llama.cpp-<ver>` | `/opt/llama.cpp-<id>`（★ 现役 symlink = `llama.cpp-master-23b0202a`，2026-10-12） |
> | MANIFEST 工具 | `bash /tmp/gen_manifest.sh` | 站上**无部署**（`/tmp` 重启即清）；仓库正本 = [gen_manifest.sh](../../archive/scripts-history/gen_manifest.sh)，**每次升级须先投放** |
> | ★ MANIFEST 工具的两个坑（2026-10-17 v0.7.0 构建实测，**已修**） | — | ① **正本行尾是 CRLF** ⇒ 站上 Linux `bash -n` 直接报「未预期的记号 `}`」（**Git Bash 不报** ⇒ 门禁 `syntax` 看不见，见文末「已知盲区」）；**投放前必须转 LF**。② 其 `build_host` / `build_date` / `cmake_flags` 三行**写死为迁移期话术**（`…(migration: pre-existing binaries)` / `2026-07-02 (binary mtime, pre-existing)` / `unknown (pre-existing)`）⇒ 给**新构建**用会**把假值写进证据件**（本仓最防的"过期但像真值"）。**两处已随本 SOP 修正**：行尾 = LF，三字段改读真实值（`hostname` / 二进制 mtime / 集群标准 cmake flags），`rpc_protocol` 取不到时如实写 `unknown` |
> | 定位方式 | `git checkout <tag>` | 站上源树 **`git tag` 为空**（未拉 tag）⇒ 用 commit sha（fetch 后 `checkout <sha>`），或先 `git fetch --tags` |
> | 上游 org | （未提） | 上游已迁 **`ggml-org/llama.cpp`**；站上现存树 origin 仍是旧 org `ggerganov/llama.cpp`（GitHub 重定向仍可 fetch，**建议对齐**） |
> | ★ 取源通道 | `git fetch --tags` / `git clone` | ⚠ **实测 git 协议不可用（2026-10-11，E1）**：B 站 `git ls-remote`/`git fetch` **挂起至超时 `exit=124`**（新旧 org 皆然）；主控站 `git ls-remote` **`Could not connect to port 443`**。而 **curl 通道全通**（`github.com`/`api.github.com`/`codeload` 均 200）⇒ **取源改走 codeload tarball**（= 本文末「取源通道」节），**不再依赖 git** |

⚠ 下述 `git clone/fetch` 当前**不可用**（见上表「取源通道」行）；**现行取源 = 文末「取源通道」节的 codeload tarball**。git 通道恢复后可回到本节主路径。

```bash
# 0) MANIFEST 工具投放（站上无部署；正本在仓库）
scp archive/scripts-history/gen_manifest.sh scott-lau@scott-lau-GTR-Pro.local:/tmp/

# 1) 取源 + 构建（源树按目标命名，避免覆盖既有版本树）
ssh scott-lau@scott-lau-GTR-Pro.local '
  mkdir -p ~/build ~/dist
  test -d ~/src/llama.cpp-<id> || git clone https://github.com/ggml-org/llama.cpp ~/src/llama.cpp-<id>
  cd ~/src/llama.cpp-<id> && git fetch --tags
  git checkout <目标commit 或 tag>          # 站上无 tag ⇒ 用 commit sha 最稳
  cmake -B ~/build/llama-<id> -DGGML_VULKAN=1 -DGGML_RPC=ON -DCMAKE_BUILD_TYPE=Release
  cmake --build ~/build/llama-<id> --config Release -j $(nproc)
'
# 安装到新版本目录（不动 symlink）:
ssh scott-lau@scott-lau-GTR-Pro.local '
  sudo mkdir -p /opt/llama.cpp-<id>
  sudo cp -a ~/build/llama-<id>/bin/* /opt/llama.cpp-<id>/   # 按实际产物路径调整
'
# 写 MANIFEST + 打 tar:
ssh scott-lau@scott-lau-GTR-Pro.local '
  bash /tmp/gen_manifest.sh /opt/llama.cpp-<id>
  sudo tar -czf ~/dist/llama-<id>.tar.gz -C /opt llama.cpp-<id>
  sudo chown scott-lau:scott-lau ~/dist/llama-<id>.tar.gz
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
python ops/cluster.py versions      # 三站引擎指纹 + MANIFEST 全量 md5sum -c 完整性 (ADR-0004: 已并入统一入口)
```

### 6. 收尾 / 回滚

**收尾**：
```bash
# 巡检通过 + 冒烟通过后:
# 保留最近 2 个版本目录（<ver> + 9859），更旧的删除（变体目录 glm5next-* 另计，见 §6 校正）
sudo rm -rf /opt/llama.cpp-<旧旧版本>
# 更新 提速调研报告.md / 分布式推理.md 的版本记录
# 收尾必跑: 门禁 backend 断言会核「回滚基线 9859 三站在位 + /opt 后端 = Vulkan + 单站引擎 = HIP」
python ops/rpc_check.py --only backend     # 或 ops\rpc.ps1 check -Only backend
```

> **回滚基线由门禁守护（2026-09-17 起）**：`ops/rpc_check.py` 的 `backend` 断言核
> 「三站 `/opt/llama.cpp-9859` 在位」。**此前无任何门禁覆盖这件事**，实测 **C 站曾整份缺失 9859**
> 而门禁全绿 —— 即"C 站无法按本 SOP 回滚"这件事长期不可见。现已补回（从 A 站 tar 分发，
> 包 md5 + 清单 hash + MANIFEST 61/61 三重校验）并由断言守住。
> 同批清减：三站 `/opt/llama.cpp-master-d2e206c4`（v0.3.0，非回滚目标、零活引用）已删除
> 并 tar 备份到 `/data/backup/llama-cleanup-20260917/` ⇒ **当时**三站 `/opt` 恰为**规则要求的 2 个目录**
> （现役 symlink + 9859）。
> ⚠ **2026-10-12 校正（"恰为 2 个"→"4 项"均已过期）**：实测三站 `/opt` 为 **5 项** ——
> `llama.cpp`(symlink → **`llama.cpp-master-23b0202a`**) · `llama.cpp-9859`（回滚基线）·
> `llama.cpp-glm5next-20260928`（**特性分支变体轴**，走 `--engine` 并存）· **`llama.cpp-master-23b0202a`（现役实体）** ·
> `llama.cpp-master-91f6a6cf`（**上一生产版** —— SOP「保留最近 2 个」本应删它，**2026-10-12 刻意保留**为"退回上一生产版"的退路，**待裁**）。
> ⇒ "保留最近 2 个"仅指**稳定版本轴**（新版本 + `9859`）；**变体目录（`glm5next-*` 等）另计、不占该 2 个名额**。
>
> ⚠ **2026-10-17 再更新（三站实测为 6 项）**：在上一版 5 项基础上新增
> **`llama.cpp-v0.7.0-620d2225`** —— **版本变体（`v0.7.0` tag / commit `620d2225`）**，走 `--engine v0.7.0-620d2225` 并存，
> 供 Nemotron 3.5 Super VL（其支持在 **`tools/mtmd/models/nemotron-omni.cpp`**，文本主干仍 `nemotron_h_moe`）使用。
> 2026-10-17 于 B 站构建并分发三站：tar md5 `108222ecc374ca4ed4890332db228a56`（三站一致）·
> MANIFEST 79 条 `md5sum -c` 全通过 · **`/opt/llama.cpp` symlink 未动**（仍指 `master-23b0202a`）。命名取 `<label>-<sha>`。

**回滚**（分钟级，I5 不变式保障旧目录仍在）：
```bash
ssh scott-lau@scott-lau-NEX.local  'sudo ln -sfn llama.cpp-9859 /opt/llama.cpp && bash /llama-distributed/start_rpc.sh'
ssh scott-lau@scott-lau-GTR-Pro.local 'sudo ln -sfn llama.cpp-9859 /opt/llama.cpp && bash ~/llama-distributed/run_server.sh 8080'
# 重跑巡检 + 冒烟
```

---

## 日常巡检（升级间隔期）

```bash
python ops/cluster.py versions   # 三站指纹(RPC commit/rpc_protocol/单机 commit/LM Studio/opencode) + MANIFEST 全量 md5sum -c
```
> 2026-09-15 更新 (ADR-0004): 原 `check_llama_version.sh [--deep]` 已废弃并删除 —— 其能力
> (三站指纹比对 + MANIFEST 全量 md5sum -c) 已并入 `cluster.py versions`; 且旧脚本里 C 站 IP
> 仍是过时的 `192.168.1.24`(现为 192.168.1.37)。下方为历史记档, 保留供溯源。

两站不一致 = 有人单独动过其中一站 → 立即按回滚流程对齐。

## 取源通道（2026-10-11 实测：git 协议不可用 ⇒ 本通道为主路径）

> ★ **实测（2026-10-11，E1）**：三站 + 主控 **git 协议（HTTPS-git）均不可达** —— B 站 `git ls-remote`/`git fetch`
> **挂起至超时 `exit=124`**（新旧 org 皆然）；主控站 `git ls-remote` 报 **`Could not connect to port 443`**。
> **唯一可用通道 = curl 系**（`github.com` / `api.github.com` / `codeload.github.com` 三站实测 **200**）
> ⇒ **取源走 codeload tarball**；**查上游 commit 列表走 GitHub API**
> （`api.github.com/repos/ggml-org/llama.cpp/commits?sha=master&since=<ISO>`）。
> **优于原「应急路径」**：tarball 从**构建站 B 直下**，不引入 A 站编译环境漂移。

> ★★ **取源两条实测修正（2026-10-17，v0.7.0 构建踩出；两条都是"看着能跑其实不行"）**
>
> | # | 实测 | 后果 |
> |---|---|---|
> | ① | **codeload 不支持 byte range** —— `curl: (33) HTTP server doesn't seem to support byte ranges. Cannot resume.` | `curl -C -`（断点续传）**不是"慢"，是立刻报错** ⇒ 本通道**任何中断只能从零重下** |
> | ② | 流式响应**无 `Content-Length`** ⇒ 连接被提前切断时 curl 仍打印 **`100%`** | **"下载成功"是假象** ⇒ 唯一可信判据 = **`gzip -t`**（截断的 gzip 流必被识破）；`[ -s file ]` 与 curl 退出码**都不足以证明完整** |
> | ③ | 实测速率 **~32–38 KB/s**（B 站，稳定）；v0.7.0 源包 = **36.3 MiB**（对照 `llama-src-23b0202a.tar.gz` = 38,061,582 B） | 单次需 **~17–20 min** ⇒ `--max-time` 必须 ≥ **1800**（首跑用 900 只拿到 34.6 MB 即被切断） |

```bash
# 在 B 站（唯一构建源）直下源码 tarball；<ref> 例：v0.7.0 或 23b0202a18…
# ★ 定版命令（含上表三条修正）：从零单次长超时 + curl 自重试 + 外层轮次 + gzip -t 自证
ssh scott-lau@scott-lau-GTR-Pro.local '
  mkdir -p ~/src && cd ~/src
  TAR=llama-src-<id>.tar.gz
  for n in 1 2 3; do
    rm -f $TAR                                # 不支持 Range ⇒ 不能续传，只能重下
    curl -L --max-time 5400 --retry 5 --retry-delay 15 --retry-all-errors \
         https://codeload.github.com/ggml-org/llama.cpp/tar.gz/<ref> -o $TAR
    gzip -t $TAR && break
  done
  gzip -t $TAR || { echo "FAIL: tarball 不完整（本通道无法续传，只能重下）"; exit 1; }
  mkdir -p ~/unpack-<id> && tar -xzf $TAR -C ~/unpack-<id>
  mv ~/unpack-<id>/llama.cpp-* ~/src/llama.cpp-<id>
  # 构建流程同第 2 步（cmake … → /opt/llama.cpp-<id> → MANIFEST → tar）
'
```

> ⚠ **tarball 无 `.git` 元数据** ⇒ `git log`/`git tag` 不可用。核"目标 PR 是否在内"改用：
> `curl -sS "https://api.github.com/repos/ggml-org/llama.cpp/commits/<sha>"`（读 message）或直接对源码 `grep`。
> git 通道恢复后，可回到 §2 的 git 主路径。

---

## 已知盲区（门禁侧；2026-10-17 实测，**尚未根治**）

**`syntax` 断言看不见「CRLF 破坏 shell 语法」** —— 同一份 CRLF 的 `.sh`（实测样本 =
[gen_manifest.sh](../../archive/scripts-history/gen_manifest.sh)），两边的结论**完全相反**：

| 检查方 | `bash -n` 结果 |
|---|---|
| 门禁 `syntax`（走 **Git Bash / MSYS**） | **rc=0 通过** ⇒ 该栏报 `.sh:414文件/0失败`（**漏判**） |
| 部署靶子（**Linux bash**，站上实测） | **报错** `未预期的记号 "}" 附近有语法错误` |

⇒ 判据链用的是 **MSYS 的 bash**，而真正被执行的是 **Linux 的 bash**；对 CRLF 这类**字节级**属性
**结构性不可见** —— 与 ADR-0004 记的 `.ps1 BOM` 同一机理：**解析式判据抓不到字节级属性，
必须另加一个「读字节」的维度**（那条最终就是靠 `.ps1-bom` 字节判据解决的）。

**★ 已根治（2026-10-17，走完本仓「门禁判据变更流程」全流程）**：`ops/rpc_check.py` 的 `syntax` 新增
**`.sh-crlf` 字节维度**（`.sh` 与无扩展名 shebang 脚本**含任何 `0x0D`** ⇒ FAIL，**自带双向自证**：
LF 样本必不报 / CRLF 样本必报；自证失败则**拒绝给 PASS**）。

| 流程步 | 实测 |
|---|---|
| **先验红** | 判据一落地即抓到 **231 个真 CRLF 的 tracked `.sh`**（分布：`archive/scripts-history` 119 · `archive/root-scripts` 91 · `tests/b5q` 21；**`ops/**` 全为 LF**）⇒ 该缺陷族**长期完全不可见** |
| **射程说明（关键）** | **未扩大射程** —— 既有 `bash -n` 判据（`.sh:414`）**本就覆盖全部 tracked `.sh`**（含 `archive/`），新维度只是**在同一集合上另加一条字节判据** ⇒ **不设例外清单**（符合本仓"判据只在一处定义 / 例外清单会不断变长"的纪律） |
| **同源对照·反例** | 往一个 tracked `.sh` 注入 CRLF ⇒ **`(sh-crlf)` 精确点名该文件，而 `(sh)`（bash -n）那栏仍 `0 失败`** ⇒ **直接证明补上了盲区**（注入已还原，字节级） |
| **同源对照·正例** | 干净仓库 ⇒ **`.sh-crlf:424文件/0失败`**，`syntax` **PASS**（无误报） |
| **处置** | 231 个 CRLF 文件**已全部转 LF**（对 shell 脚本是行为等价的机械转换） |
| **台账闭环** | 本节 + [`TRACKER`](../upstream-tracker/TRACKER.md) v3.28 摘要 + 项目记忆 |

> 为何**不**改 `.gitattributes` 了事：那里的 `text eol=lf` 只覆盖**已登记前缀**（现仅 `ops/lm-download/*.sh`），
> 覆盖不到全仓；而**字节判据在 pre-commit 就能拦住**，且能覆盖站上产物与未来任何新路径。
