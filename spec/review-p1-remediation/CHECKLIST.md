# 审查验收 Checklist：原始评审 P1 四条修复

---

id: review-p1-remediation-CHECKLIST
type: design
version: 1.0
status: accepted
date: 2026-10-27
depends: [review-p1-remediation-IMPLEMENTATION, review-p1-remediation-DESIGN]
upstream: null

---

> **Feature**: 修复 2026-10-21 原始评审 RPC 段的四条 P1——#3 模型定位、#4 conf 引号/转义、#7 ds4 监听默认、#10 Web token——把"默认不安全 / 同源规则脱钩 / 文本读写不一致"收敛为可判定契约。
> **创建日期**: 2026-10-27
> **状态**: 已验收（第 1 轮单测 + 第 2 轮真站只读 + 第 3 轮 Web 端到端，全部通过；真站 ds4 PP 加载为按需待办，不阻塞）
> **Spec 步骤**: Step 5（验收）
> **基于实施**: [IMPLEMENTATION.md](./IMPLEMENTATION.md)
> **基于设计**: [DESIGN.md](./DESIGN.md)
> **基于调研**: [原始评审 P1 社区外部锚点调研](../../docs/research/2026-10-26_原始评审P1_社区外部锚点调研.md)
> **代码基线**: `d1d94b3a`（`main`，已推送）
> **审查轮次**: 第 1 轮（单测先验红→后验绿，2026-10-27）；第 2 轮（三站部署 + 真站只读证据）；第 3 轮（Web 真实进程 curl 端到端，2026-10-27）

---

## 0. 验收门总览

| 门 | 内容 | 章节 | 项数 | 级别 |
|---|---|---|---|---|
| M1 | 交付物 | §1 | 13 | **P0** |
| M2 | 功能 + 先验红证据 | §2 | 10 | **P0** |
| M3 | 接口与边界 | §3 | 10 | **P0** |
| M4 | 真站 / 端到端 | §4 | 12 | **P0**（E8 按需） |
| M5 | 门禁与回归 | §5 | 7 | **P0** |
| M6 | 不变式 | §6 | 7 | **P1** |
| M7 | 残留与待办处置 | §7 | — | P1/P3 |

**明确不在本轮验收范围**：

- 不验收真站 ds4 PP 实弹加载（需先卸现役 DS4 1M，见 §7 待办；编排/中止语义已由单测与干跑覆盖）。
- 不验收 P2 五项（#5 `set -euo` / #6 遗留 systemd / #8 拆文件 / #9 硬编码 / CI）。
- 不验收浏览器 UI 视觉行为（Cookie 协议面已由 curl 覆盖；手测列入 §7 可选项）。

---

## 1. 交付物验收

| # | 交付物 | 落位 | 判据 | 状态 | 证据 |
|---|---|---|---|---|---|
| T1 | Web 鉴权改造 | [cluster_web.py](../../ops/cluster_web.py) | `_token_eq`/`_mask_token`/`_startup_lines` 存在；`_auth_ok` 双通道 | ☑ | 源码核 + 单测 28 PASS |
| T2 | conf 写读共享库 | `ops/station-bin/conf-lib.sh` | `conf_escape`/`conf_set_kv`/`conf_get_kv`；无 `sed -i` | ☑ | test_conf_lib 12 PASS |
| T3 | conf 读取 CLI | `ops/station-bin/conf-get` | 薄壳；自定位 source | ☑ | B 站实测（§4 E1） |
| T4 | 主控 conf 解析 | [conf_parse.py](../../ops/conf_parse.py) | 与 conf-lib.sh 同一转义集；`cluster._parse_conf` 函数内委托 | ☑ | test_conf_parse 11 PASS；deps 门禁 0 违规 |
| T5 | infer-load 三项接入 | [infer-load](../../ops/station-bin/infer-load) | #3 `model_file_for_alias`；#4 `conf_escape`+`conf_set_kv`；#7 `--pp-listen` | ☑ | diff 核 + 单测；B 站冒烟 |
| T6 | infer-list 接入 | [infer-list](../../ops/station-bin/infer-list) | `scan()` 调 `model_scan`；`peer_scan` 发送共享函数；source 后断言 | ☑ | test_model_locate 源码断言；B 站 12 别名 |
| T7 | 模型定位共享库 | `ops/station-bin/model-locate.sh` | 三公开函数 + `_model_main_gguf` 单一优先级 | ☑ | test_model_locate 17 PASS |
| T8 | cluster.py 编排 | [cluster.py](../../ops/cluster.py) | `_pp_listen_ip`/`pp_listen` 参数/`_load_ds4_pp` 先取 IP | ☑ | test_cluster_pp_listen 24 PASS |
| T9 | rpc_check 接入 | [rpc_check.py](../../ops/rpc_check.py) | `[mpath]` 走 `conf-get`；`STATION_BINS` 12 件 | ☑ | diff 核；`gates 36/36` |
| T10 | 脚本治理登记 | [inventory/ops.yaml](../../inventory/ops.yaml) | 3 站上件 ∈ station_runtime；conf_parse ∈ entry_modules | ☑ | `scripts` PASS（未登记 0） |
| T11 | 5 个行为测试 | `tests/test_*.py` | 先验红留存 → 后验绿；`RESULT:` 行 | ☑ | §2 F1-F5 |
| T12 | 手册回写 | [三机推理集群使用手册](../../docs/三机推理集群使用手册.md) | §3.1 可选参数含 ds4/`--pp-listen` + 安全默认说明 | ☑ | L870-872 |
| T13 | 执行记录 + 索引 | [实施记录](../../docs/2026-10-27_P1四条修复实施记录.md) / [FRAMEWORK-INDEX](../../docs/FRAMEWORK-INDEX.md) | 两处可互相到达；doclinks PASS | ☑ | doclinks 3827 条 0 失效 |

---

## 2. 功能验收（先验红 → 后验绿）

| # | 验收项 | 判据 | 级别 | 状态 | 证据 |
|---|---|---|---|---|---|
| F1 | #10 先验红 | 实现前测试 FAIL（无 `_token_eq`/Cookie/302/Referrer-Policy） | **P0** | ☑ | 15 项 FAIL 留存于会话记录（`_token_eq 存在`…`非 loopback 错误 token ⇒ 401`），先于 cluster_web.py 改动 |
| F2 | #10 后验绿 | `test_cluster_web_auth.py` 全 PASS（28 断言） | **P0** | ☑ | `RESULT: PASS`；含 302/Set-Cookie 三属性/401 统一/空 token 边界（F-6 钉）/启动日志无完整 token |
| F3 | #4 先验红→绿 | `test_conf_parse.py`（ModuleNotFoundError → 11 PASS）；`test_conf_lib.py`（库缺失 → 12 PASS） | **P0** | ☑ | 三方逐字节一致（source / conf-get / conf_parse）；换行 rc=2 且原文件 md5 不变；无临时文件 |
| F4 | #3 先验红→绿 | `test_model_locate.py`（库缺失 → 17 PASS） | **P0** | ☑ | 三落点 + mmproj 排除 + 缺失 rc=1 + `infer-load` 无 `-maxdepth 2 -type d` |
| F5 | #7 先验红→绿 | `test_cluster_pp_listen.py`（无函数 → 24 PASS） | **P0** | ☑ | `_pp_listen_ip` 四段正向 + 同站/未知站空；编排先验后起；coordinator 无值即中止 |
| F6 | 统一入口全绿 | `py tests\run_py_tests.py` 59/59 | **P0** | ☑ | 提交 `d1d94b3a` 前后各跑一次，均 59/59 |
| F7 | #4 写入口唯一 | `infer-load` 无 `sed -i`；`_set_conf_key` 只是薄包装 | **P0** | ☑ | diff 核；Bug C（末行粘连）由整文件重写结构性消除 |
| F8 | #3 诊断增强 | alias 无匹配时打印候选列表 | P1 | ☑ | infer-load L109-113（两处：别名解析 + 文件定位） |
| F9 | #7 日志如实 | coordinator 打印实际 listen；单机注记"未显式传参" | P1 | ☑ | infer-load L420/L427 |
| F10 | #10 前端收敛 | 前端不再从 URL 取 token / 不写 localStorage；登录框初始隐藏 | P1 | ☑ | PAGE_HTML script 段 diff 核 |

---

## 3. 接口与边界

| # | 接口 | 边界输入 | 期望 | 状态 |
|---|---|---|---|---|
| I1 | `_token_eq` | 空 / 非 ASCII / 错误值 | False 且不抛 | ☑ 单测 |
| I2 | `_auth_ok` | Header、Cookie、双无、错误值 | 任一通过；全败 False | ☑ 单测 + §4 E4 |
| I3 | `conf_escape` | 换行 | rc=2，不写半行 | ☑ test_conf_lib |
| I4 | `conf_set_kv` | 非法键 / 文件缺失 / mktemp 失败路径 | rc=1，原文件不动 | ☑ 单测（失败路径清理） |
| I5 | `conf_get_kv` / `conf-get` | 缺失键 / 缺失文件 | rc=1 | ☑ 单测 + B 站 |
| I6 | `parse_conf` | 历史无引号 / 单引号 / 未知转义 `\q` / 空文本 | 兼容读取；未知转义原样 | ☑ test_conf_parse |
| I7 | `model_file_for_alias` | depth-1 / -GGUF / 量化子目录 / 缺失 | rc=0 命中 / rc=1 | ☑ 单测 + B 站 |
| I8 | `_pp_listen_ip` | B-C/C-B/A-C/A-B / 同站 / 未知站 | 对端段 IP / `""` | ☑ 单测（真实 net.yaml） |
| I9 | `_build_infer_load_cmd` | `pp_listen=None` / 合法 IP / 非法 IP | 不追加 / 追加 / ValueError | ☑ 单测 |
| I10 | `infer-load --pp-listen` | 非法字符 | 参数阶段 exit 1 | ☑ 白名单 case 语句（源码核） |

---

## 4. 真站 / 端到端验收

### 4.1 第 2 轮：三站部署与只读证据（2026-10-27）

| # | 项 | 判据 | 状态 | 证据 |
|---|---|---|---|---|
| E1 | conf-get 真站 | B 站 `conf-get /etc/llama-instances/glm-5.3-flash.env MODEL_PATH` 输出真实路径且 `test -f` 存在 | ☑ | `/data/models/gguf/unsloth/GLM-5.3-Flash-GGUF/GLM-5.3-Flash-UD-IQ4_XS.gguf` · EXISTS |
| E2 | 模型定位真站 | B 站 `model_file_for_alias davidau-q38-27b-q4k` 命中**仓库级直放**（depth-1） | ☑ | `.../davidau-q38-27b-q4k/Qwen3.8-27B-…-Q4_K_M.gguf`；`model_aliases` 12 个 |
| E3 | infer-list 真站 | B 站 `infer-list B` 表格正常，含 davidau 条目 | ☑ | 12 行；peer_scan 共享函数随 payload 发送 |
| E4 | 部署一致性 | 三站 5 个新/改站上件 md5 逐字节一致 | ☑ | `model-locate.sh c9e0374c…` · `conf-lib.sh 8a311f9e…` · `conf-get 54affdd6…` · `infer-load 184dc54c…` · `infer-list b33f6437…`；`gates 36/36` |
| E5 | 部署备份 | infer-load / infer-list 有 `.bak-p1review-20261027` | ☑ | 三站存在（README §两站一致性登记） |
| E6 | bash -n | 三站全部站上件语法检查通过 | ☑ | 部署命令内联 `bash -n` 全过 |

### 4.2 第 3 轮：Web 真实进程 curl 端到端（本机 9500 端口，2026-10-27）

> 背景：8899/8850/8866 三次落 Windows 保留端口段（WinError 10013，`netsh int ipv4 show excludedportrange` 证实；代码自带提示正确指路）⇒ 换 9500。该失败序列同时验证了 token 文件先行落盘与失败即 return 1 的顺序（见 §7 P3-1）。

| # | 请求 | 期望 | 实测 | 状态 |
|---|---|---|---|---|
| E7a | `GET /?token=<正确>` | 302 + `Location: /` + `Set-Cookie: rpc_token=…; HttpOnly; SameSite=Strict; Path=/` + `Referrer-Policy: no-referrer` + `Cache-Control: no-store` + 空 body | 全部命中 | ☑ |
| E7b | `GET /?token=wrong` | 401 + no-store + **无** Set-Cookie | 命中 | ☑ |
| E7c | `GET /` | 200 公开页 + Referrer-Policy | 命中 | ☑ |
| E7d | `POST /api/nope` 无凭据 | 401（do_POST 入口先鉴权） | 401 | ☑ |
| E7e | `POST /api/nope` + 正确 Cookie/Header | 非 401（鉴权通过后 404） | 404 | ☑ |
| E7f | `POST /api/nope` + 错误 Cookie | 401 | 401 | ☑ |
| E7g | `GET /api/status` 无凭据 | 401（不触发采集，≤10s） | 401 | ☑ |
| E7h | `GET /api/status` + 正确 Cookie | **200**（真实三站 SSH 采集端到端） | 200 | ☑ |
| E7i | token 文件 | 自动生成 `~/.local/share/rpc/web-token`，curl 用其值引导成功 | 命中 | ☑ |
| E7j | 进程清理 | 验收后 web 进程停止、端口释放 | ☑ | Win32_Process 复查 0 个 |

### 4.3 按需（不阻塞）

| # | 项 | 状态 |
|---|---|---|
| E8 | 真站 ds4 PP 实弹加载（验证 `--pp-listen` 端到端 cmdline） | ☐ 待办（§7） |

---

## 5. 门禁与回归

| # | 门禁 | 判据 | 状态 | 读数 |
|---|---|---|---|---|
| G1 | `py-tests` | 59/59 | ☑ | 含新增 5 测试；既有 54 无退化 |
| G2 | 全量 `rpc_check` | PASS 0 红 | ☑ | `d1d94b3a` 提交后全量：47 绿 / 3 黄 / 0 红 |
| G3 | `gates` | 站上件一致 | ☑ | **36/36**（12 件 × 3 站） |
| G4 | `id-census` | 真值一致 | ☑ | 10/10（RPC 25→26 行：`_mask_token` 新增 sha256 行；已 `--emit` 重出 + U4 §1 回写） |
| G5 | `scripts` / `deps` | 未登记 0 / 违规 0 | ☑ | 拆分模块 7 · 站上运行时 27；模块 8 · 懒加载 1（既有登记） |
| G6 | `doclinks` / `md-tables` / `doc-status` / `spec-untested` | 0 失效 / 新增 0 违规 | ☑ | 3827 链接 0 失效；2364 表新增 0；45 对一致；词表 109/109 |

---

## 6. 不变式复核（DESIGN §6）

| # | 不变式 | 落点 | 状态 |
|---|---|---|---|
| N1 | 单一写入口 | `conf_set_kv` 唯一；`_set_conf_key` 薄包装 | ☑ |
| N2 | 单一站上扫描 | `model_scan` 唯一实现；两脚本 source 同一库 | ☑ |
| N3 | 写读互逆 | 固定四类转义；三方逐字节一致（单测） | ☑ |
| N4 | 默认安全 | ds4 coordinator 无显式 IP 即中止；单机不传 `--listen` | ☑ |
| N5 | token 不入 URL/日志 | 引导 302 剥离；`log_message` 脱敏；启动横幅掩码 | ☑ |
| N6 | 无新 daemon/入口 | 3 个被 source 的库 + 1 个 CLI 薄壳 + 1 个懒加载模块；均已登记 ops.yaml | ☑ |
| N7 | P2 不扩权 | diff 范围仅 P1 四条 + 登记 + 文档 | ☑ |

---

## 7. 残留与待办

| # | 级别 | 项 | 处置 |
|---|---|---|---|
| P3-1 | P3 | `serve()` 先写 token 文件再绑定端口 ⇒ 启动失败（如保留端口段）时 token 文件已更新，与"无存活进程"短暂不符 | 观察项；无安全影响（文件 0600、每次启动覆盖、不外泄）；若后续重构 `serve` 顺带调整顺序 |
| P3-2 | P3 | Windows 上 token 文件 0600 为 best-effort（实测 NTFS Archive 属性）；POSIX 站上严格 | 已在 IMPLEMENTATION §12.3 声明；文档化即可 |
| TODO-1 | 按需 | 真站 ds4 PP 实弹加载（E8） | 需先卸现役 DS4 1M 并经用户授权；`_load_ds4_pp` 会自动传 `--pp-listen` |
| TODO-2 | 可选 | 浏览器 UI 手测（Cookie 自动携带、401 时登录框出现） | curl 已覆盖协议面；UI 层面按需 |
| TODO-3 | 可选 | `CHECKLIST.md` 是否入 `inventory/doc-status.yaml` 两处声明 | 与 DESIGN/IMPLEMENTATION 同口径（均未登记，doc-status PASS），维持现状 |

---

## 8. 验收结论

**验收通过**（2026-10-27）。

- **M1-M3**（交付物 / 功能 / 接口）：13 + 10 + 10 项全部 ☑，先验红证据完整（四条各自从"缺口可见"走到"断言全绿"）。
- **M4**（真站/端到端）：E1-E7 共 16 项 ☑；Web 端到端在真实进程上覆盖了引导 302、Cookie 三属性、常量时间鉴权双通道、401 统一语义、token 文件落点。
- **M5**（门禁）：提交 `d1d94b3a` 前后全量 `rpc_check` 均 PASS（47 绿 / 3 黄 / 0 红；黄灯均为存量已登记项）。
- **M6**（不变式）：7 条逐条有落点。
- **M7**：1 项 P3 观察项 + 3 项待办，均不阻塞；真站 ds4 PP 实弹加载留待下次 ds4 维护窗口。
