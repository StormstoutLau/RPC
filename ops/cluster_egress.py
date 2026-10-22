#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cluster_egress — 出站域：出站平面 + OpenRouter 免费档计数 + 额度借用（`cluster.py` 拆分，阶段 2b）。

为什么存在：`cluster.py` 是单文件 5000+ 行；本模块收拢"主控与三站出网是否通、免费档日额度
用掉多少、到顶时如何借同侪的 key"这一整条出站链路。拆分方案见
docs/2026-09-23_cluster.py模块化重构_调研与方案.md。

边界（改之前先读）：
  · 依赖 `cluster_secrets._secrets_push`（额度借用要把同侪 key 推给目标站）⇒ 单向依赖，
    cluster_secrets **不**反向依赖本模块（无环）。
  · 额度借用**默认只出计划，`--go` 才写凭据** —— 这是本模块最要紧的安全约定，勿改默认值。
  · 账本落点: `ops/.egress_station.json`（**派发侧按站**日计数；★ **2026-10-20 R1 裁【丙】**：
    旧的主控侧单计数器 `ops/.egress_daily.json` **已废弃删除** ⇒ 本地计数面**单件承载**）
    / `ops/.or-borrow.json`（借用台账）；凭据池 `secrets/or-borrow/`。
  · `cluster.py` 显式重导出全部符号，外部调用点（cluster_web.py 的 cluster.probe_egress_station）
    与 cluster.py 内 cmd_egress/cmd_egress_borrow 分发均不变。
"""
import datetime
import json
import re
import subprocess
import threading
import time
from pathlib import Path

from cluster_const import STATIONS
from cluster_secrets import SECRETS_ROOT, _secrets_push
from cluster_ssh import ssh_run

# ── 出站平面 (egress) ──────────────────────────────────
# 探针目标: OpenRouter /api/v1/key (幂等只读, 返回用量/余额)。
# 铁律: 强制 IPv4 —— 主控到 openrouter.ai 的 IPv6 路径黑洞 (ADR-0003 实测), 故一律 curl -4。
EGRESS_URL = "https://openrouter.ai/api/v1/key"
EGRESS_SEP = "__META__"


def _mask_key(s: str) -> str:
    """OpenRouter /key 的 label 会回显 key 前段, 输出前必须脱敏。"""
    return re.sub(r"(sk-[A-Za-z0-9_-]{4})[A-Za-z0-9_-]+", r"\1***", s)


def _parse_egress(body: str) -> dict:
    try:
        d = (json.loads(body) or {}).get("data") or {}
    except Exception:
        return {}
    # is_free_tier: True=从未充≥$10 → 免费档日限额 50; False=曾充≥$10 → 1000 (一次性解锁永久生效)
    # ⚠ **2026-09-21 更正(实测)**: 本函数原先只取 `limit_remaining`(信贷余量), 把它当"配额"显示 ⇒
    #   既**误标**(见 cmd_egress 的"余 N"), 又**漏掉了真正的免费请求配额**。实测 `/api/v1/key` 现返回
    #   `free_model_daily_requests{used,limit,remaining}`(服务端权威免费请求计数) + `creator_user_id`
    #   (账户身份) —— 旧述"OpenRouter 无此 API"已过时, 见 ADR-0003 更正块。
    #   **两个口径必须分开**: `free_model_daily_requests` = `:free` 档模型请求数;
    #   `usage*` / `limit_remaining` = **付费 credits** 口径(免费模型恒 0)。
    #   ⚠ 该服务端计数**有分钟级延迟**(实测 ~20s 不变、~4min 到位) ⇒ 只适合巡检/预警/对账, **不可当实时闸门**。
    fdr = d.get("free_model_daily_requests") or {}
    return {"usage": d.get("usage"), "remaining": d.get("limit_remaining"),
            "limit": d.get("limit"), "is_free_tier": d.get("is_free_tier"),
            "label": _mask_key(str(d.get("label", ""))),
            # 2026-09-21 新增: 账户身份 + 免费请求配额(服务端权威)
            "owner": str(d.get("creator_user_id") or ""),
            "free_used": fdr.get("used"), "free_limit": fdr.get("limit"),
            "free_remaining": fdr.get("remaining")}


def _egress_cmd(keyexpr: str) -> str:
    return (f"K=$({keyexpr} 2>/dev/null); "
            "if [ -z \"$K\" ]; then echo 'NO_KEY'; else "
            f"curl -4 -s -m 12 -w '{EGRESS_SEP}http=%{{http_code}} t=%{{time_total}}' "
            f"-H \"Authorization: Bearer $K\" {EGRESS_URL}; fi")


# ── OpenRouter 免费档每日计数 (2026-09-16 建; **2026-09-21 更正口径**; **2026-10-20 R1 裁【丙】**) ──
# ⚠ **旧述(2026-09-16)："OpenRouter 不提供免费请求剩余数的可查询 API ⇒ 每日计数只能本地自建"**
#   —— **已被实测推翻**：`GET /api/v1/key` 现返回 `free_model_daily_requests{used,limit,remaining}`
#   (+ `creator_user_id` 账户身份)。详见 ADR-0003 的 2026-09-21 更正块。
# **现口径(两者并用)**：
#   · **服务端(权威)**：`free_model_daily_requests` —— 逐端展示与预警以此为准；
#     ⚠ **但有分钟级延迟**(实测 ~20s 不变、~4min 到位) ⇒ **不可当"调用前实时闸门"**，只适合巡检/预警/对账。
#   · **本地(派发侧 · 单件承载)**：`ops/.egress_station.json`（**按站**计数；写侧 = `agent-cli.ps1` 的
#     `Write-EgressStationPick`，在**默认出网档派发**时写）。
#     ★★ **2026-10-20 R1 裁【丙】**：原"主控侧单计数器" `ops/.egress_daily.json` + `_egress_daily()`
#        / `_egress_bump()` / `_egress_save()` / `EGRESS_DAILY_FILE` **已废弃删除** —— 依据三条：
#        ① 该件**按构造恒 0**（写入手 `_egress_bump()` **全仓零调用点** + 该件**盘上不存在**）；
#        ② 与派发侧件**同名两件**（都叫"本地计数"、定义域不同 = 一个 ⊂ 另一个）易被读错；
#        ③ 两件**日界口径不同**（旧件用 `datetime.date.today()` = **本地日**，派发侧用 **UTC**）。
#        ⇒ 旧件"未被记录的调用方"那一半口径**由本读者 + 差值接管**（见 `cmd_egress` 的对账行）。
# 免费档限额：20 请求/分 且 每日 50(从未充≥$10) / 1000(曾累计充≥$10, is_free_tier=false, 一次性解锁永久生效)。
# 429 带 X-RateLimit-* 头(服务器真值), **429 计入每日配额**, 且**按账户**治理(多建 key 不能绕过同一账户)。
# ★ 2026-10-20 就地收窄(E2 实测; 与 ADR-0003 L194 的 2026-10-20 更正同源): 原写"**429/失败仍计入每日配额**"
#   ⇒ 实测**只对 429 成立** —— 连打 20 次全 **400**(客户端) 后该账户 used **纹丝未动**(5→5)
#     ⇒ **400 类客户端错误【不】计**; ⚠ 429 那半本轮**未测到**(20 次全 200) ⇒ 保留原样: 不冒认、也不否认。

FREE_QUOTA_FREE = 50     # ★ 现役用途 = `_free_quota()` 的 **fail-closed 兜底档**（判不了 ⇒ 取保守）
FREE_ALERT_RATIO = 0.8
EGRESS_STATION_FILE = Path(__file__).resolve().parent.parent / "ops" / ".egress_station.json"


def _egress_station_today(path=None):
    """读**派发侧按站计数件** `ops/.egress_station.json`（UTC 日界）⇒ `(per_station, reason)`。

    · 可判 ⇒ `({"A": n, "B": n, "C": n}, "")`
    · 不可判 ⇒ `(None, "<原因>")` —— ★ **fail-closed**：**不印 0、不猜**（"判不了 ≠ 0"）——
      五种：缺件 / 坏 JSON / 缺 `by_station` / 某站计数非整数 / **`date` 不是今天(UTC)**。

    ★ 为什么不"自动归零"（与已删的旧件 `_egress_daily()` 的关键差别）：跨日时**判不了**比**报 0** 更诚实
      —— 报 0 会让人把"昨天没记账"读成"今天没用额度"（本仓头号失败形态：判据在跑 ≠ 判据在判）。
    ⚠ **schema 的唯一定义点在写侧**（`agent-cli.ps1` 的 `Write-EgressStationPick`：`{date, by_station,
      last_used}`）—— 本处**只读不改**；schema 一旦改形状，这里会 **fail-closed**（宁可判不了，不猜）。
    ⚠⚠ **编码必须 `utf-8-sig`**（★ 本批真跑当场抓到的真缺陷）：写侧是 PS5.1 的 `Set-Content … -Encoding
      UTF8` ⇒ **落 UTF-8 BOM**（实测首 3 字节 `EF BB BF`）⇒ 用 `utf-8` 读会留下 `\ufeff` ⇒ `json.loads`
      直接抛 ⇒ **真路径下"永远不可判"**。★ 而离线夹具当时用 **python 的写形状**（无 BOM）⇒ **夹具全绿、
      真路径全坏**（"夹具形状 ≠ 真生产者形状"= 假绿）。`utf-8-sig` 对**有/无 BOM 都能读** ⇒ 两侧同源。
    ★ `path` 可注入（默认 `EGRESS_STATION_FILE`）⇒ 夹具可**离线真跑**六态（写系统 TEMP、不落仓）。
    """
    p = path or EGRESS_STATION_FILE
    try:
        raw = Path(p).read_text(encoding="utf-8-sig")
    except Exception:
        return None, "状态件不存在/不可读"
    try:
        d = json.loads(raw)
    except Exception:
        return None, "状态件不是合法 JSON"
    if not isinstance(d, dict):
        return None, "状态件顶层不是对象"
    if d.get("date") != datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"):
        return None, "状态件的 date 不是今天(UTC) ⇒ 跨日/陈旧"
    bs = d.get("by_station")
    if not isinstance(bs, dict) or not bs:
        return None, "状态件缺 by_station / 为空"
    out = {}
    for k, v in bs.items():
        try:
            n = int(v)
        except Exception:
            return None, f"状态件 by_station['{k}'] 不是整数"
        if n < 0:
            return None, f"状态件 by_station['{k}'] 为负"
        out[str(k)] = n
    return out, ""


def _free_quota(is_free_tier=None):
    """★ **fail-closed 兜底档**（R4 裁【甲】· 2026-10-20）—— 判不了时取**保守档 50**。

    ⚠ **本函数不再是主口径**：它原用 `is_free_tier` 反推 50/1000（`False ⇒ 1000`），而官方 SDK 页逐字
      「`limit` … the ceiling depends on **total credits purchased** and is **independent of
      `is_free_tier`**」（见 ADR-0003 L193 的 2026-10-20 收窄段）⇒ ★ 那是**代理判据**：
      `is_free_tier` 是"是否**曾**充值"的布尔，而档位看的是"**总充值额**"，两者只在"从未充 / 已充过"
      两端重合。⇒ 主口径已改为**直读**服务端权威字段 `free_model_daily_requests.limit`
      （`_free_quota_effective`）。
    ★ 本函数**保留**为 `free_limit` 取不到时的兜底（`cluster.py` L545 仍重导出它）；参数**保留但不参与判档**
      —— 档位真值源只有 `free_limit`。★ 兜底**必须如实报出**（调用方不许静默）。
    """
    return FREE_QUOTA_FREE


def _free_quota_effective(info: dict):
    """免费档日限额【主口径】= **直读**服务端权威字段 `free_limit`；取不到 ⇒ 兜底并**如实报出来源**。

    返回 `(quota, source)`，`source ∈ {'limit', 'fallback-50'}`。

    为什么直读（R4 裁【甲】· 2026-10-20）：官方 SDK 页逐字「`limit` … depends on **total credits
    purchased** and is **independent of `is_free_tier`**」⇒ 用 `is_free_tier` 反推档位 = **代理判据**；
    且 `_parse_egress`（L61）**早已**把该字段解析成 `free_limit`，借用/指派流程（L275 / L325）**本就直接读**
    ⇒ 本改动 = 把孤例**收回权威字段**（消掉"同一事实两处表达"）。
    ★ 兜底为什么取 50 而不是按 tier 猜 1000：`free_limit` 取不到 ⇒ **判不了** ⇒ fail-closed 取保守档，
      且**报出来源**（"判不了 ≠ 通过"，也不许静默）。
    """
    fl = info.get("free_limit")
    try:
        n = int(fl)
    except Exception:
        n = 0
    if n > 0:
        return n, "limit"
    return _free_quota(), "fallback-50"


def probe_egress_station(st: str) -> dict:
    """单站出站探测 (走站内 ~/.config/rpc/openrouter.key)。"""
    res = {"station": st, "reachable": False, "http": "?", "time": "", "info": {}, "note": ""}
    ok, out = ssh_run(st, _egress_cmd("cat ~/.config/rpc/openrouter.key"), timeout=25)
    if not ok:
        res["note"] = "站不可达"
        return res
    res["reachable"] = True
    res["note"] = out.strip()
    if "NO_KEY" in out:
        res["http"] = "NO_KEY"
        return res
    body, _, meta = out.rpartition(EGRESS_SEP)
    for kv in meta.split():
        if kv.startswith("http="):
            res["http"] = kv[5:]
        elif kv.startswith("t="):
            res["time"] = kv[2:][:5]
    res["info"] = _parse_egress(body)
    return res


def probe_egress_master() -> dict:
    """主控出站探测 (走主控正本 secrets/openrouter.key; curl.exe -4 规避 IPv6 黑洞)。"""
    res = {"station": "主控", "reachable": True, "http": "?", "time": "", "info": {}, "note": ""}
    keyfile = Path(__file__).parent.parent / "secrets" / "openrouter.key"
    if not keyfile.exists():
        res["http"] = "NO_KEY"
        res["note"] = f"{keyfile.name} 不存在"
        return res
    lines = [l.strip() for l in keyfile.read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.strip().startswith("#")]
    if not lines:
        res["http"] = "NO_KEY"
        res["note"] = "key 文件无有效行"
        return res
    try:
        cp = subprocess.run(
            ["curl.exe", "-4", "-s", "-m", "12", "-o", "-",
             "-w", EGRESS_SEP + "http=%{http_code} t=%{time_total}",
             "-H", f"Authorization: Bearer {lines[0]}", EGRESS_URL],
            capture_output=True, text=True, timeout=40)
    except Exception as e:
        res["http"] = "ERR"
        res["note"] = f"{type(e).__name__}: {e}"
        return res
    body, _, meta = cp.stdout.rpartition(EGRESS_SEP)
    for kv in meta.split():
        if kv.startswith("http="):
            res["http"] = kv[5:]
        elif kv.startswith("t="):
            res["time"] = kv[2:][:5]
    res["info"] = _parse_egress(body)
    return res


def _egress_probe_all() -> dict:
    """主控 + 三站 **并行**探测(不打印) —— `egress` 展示与额度借用共用同一份快照, 避免重复联网。"""
    res = {"主控": probe_egress_master()}
    threads = []
    for st in ("A", "B", "C"):
        t = threading.Thread(target=lambda s=st: res.__setitem__(s, probe_egress_station(s)))
        t.start(); threads.append(t)
    for t in threads:
        t.join()
    return res


def cmd_egress() -> int:
    """出站平面探针: 主控 + 三站 -> OpenRouter (健康/用量/余额)。恒 exit 0, 仅供观测。"""
    res = _egress_probe_all()

    owners = {}
    for name in ("主控", "A", "B", "C"):
        r = res.get(name, {})
        info = r.get("info") or {}
        if r.get("http") != "200":
            print(f"{name:4s} : FAIL  http={r.get('http')}  {(r.get('note') or '')[:70]}")
            continue
        # owner: 账户身份短标签(用于识别"是否已拆成独立账户")
        own = info.get("owner") or ""
        own_short = own[5:13] if own.startswith("user_") else (own[:8] or "?")
        if own:
            owners.setdefault(own, []).append(name)
        # 口径①: 免费档请求配额(服务端权威) —— 拆账后这才是"每站 1000/天"要看的东西
        fu, fl, fr = info.get("free_used"), info.get("free_limit"), info.get("free_remaining")
        if fl:
            pct = (100.0 * (fu or 0) / fl) if fl else 0.0
            quota = f"free {fu}/{fl} (余 {fr}, {pct:.1f}%)"
            warn = "  ⚠≥80%" if pct >= 80 else ""
        else:
            quota = f"free {fu}/? (余 {fr})"
            warn = ""
        # 口径②: 付费 credits(与①不可混算; 免费模型恒 0)
        cred = info.get("remaining")
        cred_s = "credits 无限额" if cred is None else f"credits 余 {cred}"
        ft = "free" if info.get("is_free_tier") is not False else "paid"
        print(f"{name:4s} : OK    http=200  {r.get('time','')}s  owner={own_short}  "
              f"{quota}  {cred_s}  tier={ft}{warn}")

    print()
    if owners:
        parts = " / ".join(f"{'+'.join(v)}={k[5:13] if k.startswith('user_') else k[:8]}"
                           for k, v in owners.items())
        print(f"[egress] 账户: {len(owners)} 个独立 owner ({parts})")
    print("[egress] ⚠ 服务端免费请求计数**有分钟级延迟**(实测 ~20s 不变、~4min 到位)")
    print("         ⇒ 仅供巡检/预警/事后对账; **不可当\"调用前实时闸门\"**(会误判为未用额度)")

    # ── 派发侧计数**对账行**（2026-10-20 · R1 裁【丙】+ R2 口径）────────────────────────────────
    #   ★ **单件承载**：本地计数面只有一件 —— `ops/.egress_station.json`（按站，写侧在 `agent-cli.ps1`）。
    #     旧件 `.egress_daily.json` 及其四件符号**已删除**（理由见上方「免费档每日计数」块）。
    #   ★ **覆盖面写死**（ADR-0003 的 R2）：只覆盖「**默认出网档**（ultra / free-1m / lightning）
    #     的 `task` 派发」—— **不含** per-station 别名（不进候选 ⇒ 不 bump）· `review` 判官出网 ·
    #     人手动 TUI。⇒ ★ 故「**服务端 used − 该件 sum**」= **其余出网路径** ⇒ 这才是可解释的
    #     "未被记录的调用方"口径（替换旧件那条**从未生效**的旁证）。
    #   ★ 限额仍**直读**服务端权威字段（R4 裁【甲】）—— 见 `_free_quota_effective`；取不到 ⇒ 兜底如实。
    info_m = res.get("主控", {}).get("info") or {}
    q, q_src = _free_quota_effective(info_m)
    srv_used = info_m.get("free_used")
    per_st, why = _egress_station_today()
    src = ("limit(直读服务端 free_limit)" if q_src == "limit"
           else "★兜底档 fallback-50(⚠ free_limit 缺/非法 ⇒ fail-closed；判不了 ≠ 通过)")
    print(f"[egress] 限额 {q} (来源: {src})")
    if per_st is None:
        # ⚠ **不可判就如实说"不可判"** —— 绝不印 0（"判不了 ≠ 0"；旧件那套"跨日自动归零"正是这么骗人的）
        print(f"[egress] 派发侧计数 **不可判** ({why}) ⇒ 不与上面\"主控\"行对账（判不了 ≠ 0）")
    else:
        tot = sum(per_st.values())
        byst = " ".join(f"{k}={per_st[k]}" for k in sorted(per_st))
        ratio = (tot / q) if q else 0
        warn = " ⚠ 已达阈值80%" if ratio >= FREE_ALERT_RATIO else ""
        print(f"[egress] 派发侧计数 {tot}/{q} ({byst}) [按站·UTC]{warn}")
        if isinstance(srv_used, int) and srv_used >= tot:
            print(f"         ▸ 对账: 服务端(主控行) used={srv_used} − 派发侧 {tot} = {srv_used - tot}"
                  " ⇒ 其余出网路径(review 判官 / per-station 别名 / 手动 TUI)")
        else:
            print(f"         ▸ 对账: **判不了**（服务端 used={srv_used} 取不到或 < 派发侧 {tot}）"
                  " —— 服务端计数有分钟级延迟，别急着读成'异常'")
    print("[egress] 20 请求/分 fixed(充值不升) · **429 计入配额**(⚠ 400 类客户端错误**实测【不】计** —— 2026-10-20 收窄) · 限额按**账户**治理(多建 key 不能绕过同一账户)")
    print()
    print("[egress] 注: `:free` 档模型受 agentic-harness 门禁, 裸 API 调用返回 403;")
    print("         须经 claude code / opencode 等 harness 调用 (见 ADR-0003)。")
    return 0


# ── OpenRouter 额度借用 / 归还 (2026-09-21) ────────────────────────────
# 起因(用户要求): "单站额度到达上限, 可以调用其他两站的 API"。
# 语义: 日额度是**按账户**的(1000/天, UTC 日滚), 单站到顶后**当天不会自愈** ⇒ 只能"借"。
# 采用**控制台式指派**(设计稿 §4.1 方案 A): 把"剩余最多的同侪"的 key **临时推给被借端**。
#   为什么**不**用"站内多 key 代理": 那会把每站明文面 1→3 把, 与 ADR-0003 D5「明文面收敛」直接冲突。
#   ⇒ 本方案下**每站任一时刻仍只有 1 个 key 文件**; 代价 = 借用期间两站共用同一账户额度(故必须台账)。
#
# 安全设计(逐条都是"不静默 / 可逆"):
#   · **默认只出计划**: 不带 `--go` **绝不写任何凭据** —— 与 `flow --plan/--go`、`ttl check --go` 同习惯。
#   · **可逆**: 借用前把被借端的**自有 key 原样**存到 `secrets/or-borrow/<ST>.own.key`
#     —— 该目录在 secrets **根**、**不在** `secrets/stations/<ST>/` 下 ⇒ `push` 永不下发它
#     (不会在站上多暴露一份 key)。归还 = 拷回正本 + 只推该站。
#   · **禁二次借用/禁连锁**: 被借端已在借用状态 ⇒ 拒绝(先归还); 借出方自身也在借用 ⇒ 拒绝。
#   · **只对"日额度穷尽"**: 阈值 95%(留 5% 裕度, 因服务端计数有**分钟级延迟**);
#     RPM(20/分)类属分钟级自愈 ⇒ **应退避而非借用**(退避已由 Invoke-JudgeHttp 兜)。
#   · **同账户不借**: 用服务端 `creator_user_id` 判"是否同一账户"(A 与主控同账户 ⇒ 互借无意义)。
#   · **台账**: `ops/.or-borrow.json`(与 `.egress_station.json` 同域, 已 gitignore)
#     ⇒ "某站某日在用谁的 key"**可回答**; 归还即从台账移除。
OR_POOL_DIR = Path(__file__).resolve().parent.parent / "secrets" / "or-borrow"
OR_BORROW_FILE = Path(__file__).resolve().parent.parent / "ops" / ".or-borrow.json"
OR_BORROW_AT = 0.95      # 免费配额用量 >= 95% 视为"到顶"


def _or_pct(info: dict):
    """免费配额用量比例(0~1); 取不到(缺字段/请求失败)返回 None —— **不可判不猜**。"""
    fl, fu = info.get("free_limit"), info.get("free_used")
    if not fl:
        return None
    return (fu or 0) / fl


def _or_info(snap: dict, nm: str) -> dict:
    return (snap.get(nm, {}) or {}).get("info") or {}


def _or_state() -> dict:
    try:
        d = json.loads(OR_BORROW_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        d = {}
    if not isinstance(d.get("borrows"), dict):
        d = {"borrows": {}}
    return d


def _or_state_save(d: dict) -> None:
    try:
        OR_BORROW_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:
        print(f"[borrow] 台账写入失败: {e}")


def _or_master_key_file(st: str) -> Path:
    return SECRETS_ROOT / st / "openrouter.key"


def _or_own_key_file(st: str) -> Path:
    return OR_POOL_DIR / f"{st}.own.key"


def _or_read_key(p: Path):
    if not p.exists():
        return None
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        s = ln.strip()
        if s and not s.startswith("#"):
            return s
    return None


def _or_line(snap: dict, nm: str) -> str:
    """扫描行: <名> owner=<短> free used/limit(余R, P%)  [借用中]"""
    info = _or_info(snap, nm)
    ow = info.get("owner") or ""
    ow_s = ow[5:13] if ow.startswith("user_") else (ow[:8] or "?")
    fl, fu, fr = info.get("free_limit"), info.get("free_used"), info.get("free_remaining")
    p = _or_pct(info)
    q = f"{fu}/{fl} (余 {fr}, {p*100:.1f}%)" if p is not None else f"{fu}/? (余 {fr})"
    if snap.get(nm, {}).get("http") != "200":
        return f"  {nm:4s} owner=?      probe FAIL (http={snap.get(nm, {}).get('http')})"
    return f"  {nm:4s} owner={ow_s}  free {q}"


def cmd_egress_borrow(argv: list) -> int:
    """额度借用/归还。用法:
         cluster.py egress borrow                          # 只出**建议**(不写任何凭据)
         cluster.py egress borrow --to B --from C [--go]   # 借用(默认只出计划)
         cluster.py egress borrow --restore B [--go]       # 归还自有 key
    """
    go = "--go" in argv

    def _arg(flag):
        return argv[argv.index(flag) + 1] if flag in argv and argv.index(flag) + 1 < len(argv) else None

    to_st, from_st, restore = _arg("--to"), _arg("--from"), _arg("--restore")
    state = _or_state()
    borrows = state["borrows"]

    # ---------- 归还 ----------
    if restore:
        st = restore.upper()
        if st not in STATIONS:
            print(f"[borrow] 未知站: {restore} (可选 A|B|C)"); return 1
        own, mk = _or_own_key_file(st), _or_master_key_file(st)
        if not own.exists():
            print(f"[borrow] {st} 站无自有 key 备份({own}) ⇒ 它当前**不是**借用状态(借用时才会写该备份)")
            print(f"         若确需重置, 请手工把该站正本换回自有 key, 再 `secrets push {st}`")
            return 1
        if not go:
            print(f"[borrow] PLAN 归还 {st}: {own.name} → {mk.name}  然后 `secrets push {st}`")
            print("         (未带 --go ⇒ **未改动任何凭据**)")
            return 0
        mk.write_bytes(own.read_bytes())
        borrows.pop(st, None)
        _or_state_save(state)
        # 归还成功后**消费掉**备份: 主本已等于自有 key ⇒ 备份冗余; 删掉可让"无备份 == 非借用状态"
        #   这一语义自洽(否则留下陈旧备份, 下次 `--restore` 会对非借用站"成功"一次, 语义含糊)。
        try:
            own.unlink()
        except Exception:
            pass
        print(f"[borrow] ✅ 已把 {st} 站自有 key 写回正本: {mk}")
        rc = _secrets_push(only=st)
        print(f"[borrow] secrets push {st} rc={rc}  (站内无需重启: {{file:}} 每次调用解析)")
        return rc

    # ---------- 显式借用 ----------
    if to_st or from_st:
        if not (to_st and from_st):
            print("[borrow] 需同时给 --to 与 --from (或只跑 `egress borrow` 看建议)"); return 1
        t, f = to_st.upper(), from_st.upper()
        if t == f or t not in STATIONS or f not in STATIONS:
            print(f"[borrow] 站名须为 A|B|C 且互不相同 (得 to={t} from={f})"); return 1
        if t in borrows:
            print(f"[borrow] {t} 已在借用状态(借自 {borrows[t].get('from')}, 起于 {borrows[t].get('since')})")
            print(f"         ⇒ 先归还: cluster.py egress borrow --restore {t} --go"); return 1
        if f in borrows:
            print(f"[borrow] 借出方 {f} 自身也在借用中 ⇒ **禁止连锁借用**"); return 1
        fk, tk = _or_read_key(_or_master_key_file(f)), _or_read_key(_or_master_key_file(t))
        if not fk or not tk:
            print(f"[borrow] 读不到正本 key (from={bool(fk)} to={bool(tk)})"); return 1
        snap = _egress_probe_all()
        fi, ti = _or_info(snap, f), _or_info(snap, t)
        if fi.get("owner") and fi.get("owner") == ti.get("owner"):
            print(f"[borrow] {t} 与 {f} 服务端报告**同一账户**(owner={str(fi.get('owner'))[5:13]}) ⇒ 借用无意义")
            return 1
        fr_ = fi.get("free_remaining")
        print(f"[borrow] 借出方 {f}: free 余 {fr_} (owner={str(fi.get('owner'))[5:13]})")
        print(f"[borrow] 被借端 {t}: free 用量 {(_or_pct(ti) or 0)*100:.1f}%")
        if fr_ is not None and fr_ <= 0:
            print(f"[borrow] 借出方 {f} 自身已无剩余 ⇒ 拒绝(不能把两站一起拖到顶)"); return 1
        if not go:
            print(f"[borrow] PLAN 借用 {t} ← {f}:")
            print(f"         ① 存 {t} 自有 key → {_or_own_key_file(t).relative_to(SECRETS_ROOT.parent.parent)}")
            print(f"         ② {_or_master_key_file(f).name} 的内容 → {_or_master_key_file(t)}")
            print(f"         ③ `secrets push {t}`(只推该站) + 记台账 {OR_BORROW_FILE.name}")
            print("         ⚠ 借用期间 {0} 与 {1} 共用同一账户额度; 归还: `egress borrow --restore {0} --go`".format(t, f))
            print("         (未带 --go ⇒ **未改动任何凭据**)")
            return 0
        OR_POOL_DIR.mkdir(parents=True, exist_ok=True)
        own = _or_own_key_file(t)
        own.write_bytes(_or_master_key_file(t).read_bytes())          # ① 原样保存自有 key
        _or_master_key_file(t).write_bytes(_or_master_key_file(f).read_bytes())   # ② 换成借出方 key
        borrows[t] = {"from": f, "since": datetime.date.today().isoformat(), "own": own.name}
        _or_state_save(state)                                        # ③ 台账
        print(f"[borrow] ✅ {t} 站正本已换为 {f} 的 key; 自有 key 备份于 {own}")
        rc = _secrets_push(only=t)
        print(f"[borrow] secrets push {t} rc={rc}  (站内无需重启: {{file:}} 每次调用解析)")
        print(f"[borrow] ⚠ 记得日切后归还: cluster.py egress borrow --restore {t} --go")
        return rc

    # ---------- 无参数: 快照 + 建议(只读) ----------
    snap = _egress_probe_all()
    print("[borrow] 逐端(服务端免费请求配额; ⚠ 计数有分钟级延迟):")
    for nm in ("主控", "A", "B", "C"):
        tag = ""
        if nm in borrows:
            tag = f"   ← 借用中(借自 {borrows[nm].get('from')}, 起于 {borrows[nm].get('since')})"
        print(_or_line(snap, nm) + tag)
    print()
    print(f"[borrow] 台账 {OR_BORROW_FILE.name}: {json.dumps(borrows, ensure_ascii=False) if borrows else '(无借用)'}")
    recs = []
    for t in ("A", "B", "C"):
        p = _or_pct(_or_info(snap, t))
        if p is None or p < OR_BORROW_AT or t in borrows:
            continue
        own_t = _or_info(snap, t).get("owner")
        cands = [(f, _or_info(snap, f).get("free_remaining") or 0)
                 for f in ("A", "B", "C")
                 if f != t and f not in borrows and _or_info(snap, f).get("owner")
                 and _or_info(snap, f).get("owner") != own_t]
        if not cands:
            recs.append(f"  {t} 站已到顶, 但**无可借同侪**(另两站同账户/也在借用) ⇒ 只能退避或等 UTC 日切")
            continue
        f, rem = max(cands, key=lambda x: x[1])
        recs.append(f"  {t} 站 free 用量 {p*100:.1f}% ≥ {OR_BORROW_AT*100:.0f}% ⇒ 建议借用 {f}(余 {rem}):\n"
                    f"      cluster.py egress borrow --to {t} --from {f} --go")
    print()
    if recs:
        print("[borrow] ⚠ 建议(仅日额度穷尽才借; RPM 类请退避):")
        for r in recs:
            print(r)
    else:
        print("[borrow] 无需借用(无站点达到阈值)")
    print("\n[borrow] 说明: 借用=把同侪 key 临时推给该站(**明文面不扩大**, 每站仍 1 个 key 文件);")
    print("         RPM(20/分)属分钟级自愈 ⇒ 应退避而非借用; 到 429 也应先退避。")
    return 0
