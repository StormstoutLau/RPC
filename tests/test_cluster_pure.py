"""cluster.py 纯函数**特征测试**（characterization tests）—— 重构安全网（阶段 0）。

为什么要有这条：
    `cluster.py` 将被增量拆分为模块（见 docs/2026-09-23_cluster.py模块化重构_调研与方案.md），
    但 `tests/` 下此前**没有任何 cluster.py 的单元测试** ⇒ 搬运时若静默改变行为，无人能发现。
    本条测试把**要搬运的纯函数**当前行为逐条钉死，作为"搬运 = 行为不变"的判据。

纪律（来自社区 4000 行 god class 重构案例的教训）：
    **只锁当前行为，不顺手修任何东西** —— 即使看起来是 bug 也照锁（确属 bug 的用
    `# BUG-PIN:` 注释标出，另开改动去修，避免"测试网被钉在错误的期望上"）。

用法（退出码 0 = 全过；需带 paramiko 的解释器，如 Python312）：
    py tests\\test_cluster_pure.py
"""
import datetime
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))
sys.path.insert(0, str(ROOT / "tests"))
# ★ 2026-10-28（评审 #8 拆 cluster.py）：判据已按域搬进 `cluster_*.py`，函数读的是
#   **自己模块的全局** ⇒ 只在门面上打桩**不生效**（实测：`_load_rpc` 那次桩全部落空 ⇒
#   测试真的向站上派发了加载！）。⇒ 用代理，赋值同时落到所有已绑定该名字的模块。
from _cluster_proxy import cluster_proxy  # noqa: E402
C = cluster_proxy()

fails = []


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + extra if extra else ""))
    if not cond:
        fails.append(name)


# ── alias_of: 模型目录名 → infer-load 别名（含 minimax 重映射）──────────────
chk("alias_of: 剥离 -GGUF 后缀并小写",
    C.alias_of("Qwen3.8-27B-GGUF") == "qwen3.8-27b", C.alias_of("Qwen3.8-27B-GGUF"))
chk("alias_of: -GGUF 匹配大小写不敏感",
    C.alias_of("Foo-gguf") == "foo", C.alias_of("Foo-gguf"))
chk("alias_of: 无后缀原样小写",
    C.alias_of("davidau-q38-27b-q4k") == "davidau-q38-27b-q4k")
chk("alias_of: minimax-m2.7 前缀 → m27-q4ks",
    C.alias_of("MiniMax-M2.7-GGUF") == "m27-q4ks", C.alias_of("MiniMax-M2.7-GGUF"))
# BUG-PIN: 是**前缀**匹配而非全等 —— 任何以 minimax-m2.7 开头的目录都会被重映射。
# 锁当前行为（若有非 2.7 的 minimax 变体目录，会被错误映射；本次不修）。
chk("alias_of: minimax 前缀（非全等）也被重映射 [BUG-PIN]",
    C.alias_of("MiniMax-M2.7-SomethingElse") == "m27-q4ks",
    C.alias_of("MiniMax-M2.7-SomethingElse"))
chk("alias_of: 非 minimax 前缀不受影响",
    C.alias_of("MiniMax-M3.0-GGUF") == "minimax-m3.0", C.alias_of("MiniMax-M3.0-GGUF"))


# ── infer_quant: 从 gguf 文件名推断量化档（取最后一次匹配）─────────────────
chk("infer_quant: Q4_K_M（文档示例）",
    C.infer_quant("x-Q4_K_M-00001-of-00003.gguf") == "Q4_K_M",
    C.infer_quant("x-Q4_K_M-00001-of-00003.gguf"))
chk("infer_quant: UD-IQ4_XS 带 UD- 前缀整体命中",
    C.infer_quant("MiniMax-M2.7-UD-IQ4_XS-00001-of-00002.gguf") == "UD-IQ4_XS",
    C.infer_quant("MiniMax-M2.7-UD-IQ4_XS-00001-of-00002.gguf"))
chk("infer_quant: 带目录的入参只取 basename",
    C.infer_quant("/data/models/gguf/r/m/model-Q8_0.gguf") == "Q8_0",
    C.infer_quant("/data/models/gguf/r/m/model-Q8_0.gguf"))
chk("infer_quant: F16 大写档可命中",
    C.infer_quant("m-F16.gguf") == "F16", repr(C.infer_quant("m-F16.gguf")))
# BUG-PIN: `_QUANT_RE` 的 BF16/F16/F32 分支**大小写敏感**（Q\d 等分支同理要求大写 Q），
# 故文件名里的小写 `bf16`/`f16`/`f32` **不会被识别**。锁当前行为；若有小写命名的 gguf
# 会拿不到量化档（影响 conf 摘要显示），本次不修（另开改动）。
chk("infer_quant: 小写 bf16 不被识别 → 空串 [BUG-PIN]",
    C.infer_quant("m-bf16.gguf") == "", repr(C.infer_quant("m-bf16.gguf")))
chk("infer_quant: 无量化串 → 空串",
    C.infer_quant("plain-model.gguf") == "", repr(C.infer_quant("plain-model.gguf")))
chk("infer_quant: 非 .gguf 也照样解析（不校验扩展名）",
    C.infer_quant("x-Q4_K_M.bin") == "Q4_K_M", C.infer_quant("x-Q4_K_M.bin"))


# ── pick_representative: 多分片挑代表（必须优先 -00001-of-）───────────────
chk("pick_representative: 优先第一分片（乱序输入）",
    C.pick_representative(["/m/x-00002-of-00003.gguf", "/m/x-00001-of-00003.gguf"])
    == "/m/x-00001-of-00003.gguf")
chk("pick_representative: 无第一分片 → 排序取首",
    C.pick_representative(["/m/b.gguf", "/m/a.gguf"]) == "/m/a.gguf",
    C.pick_representative(["/m/b.gguf", "/m/a.gguf"]))
chk("pick_representative: 空列表 → 空串",
    C.pick_representative([]) == "")


# ── group_by_model: gguf 路径按 (repo, model_dir) 分组 ───────────────────
_g = C.group_by_model([
    "/data/models/gguf/repoA/modelX/f-00001-of-00002.gguf",
    "/data/models/gguf/repoA/modelX/f-00002-of-00002.gguf",
    "/data/models/gguf/repoB/direct.gguf",           # 仓库级直放 → model_dir 记空串
    "/elsewhere/ignored/f.gguf",                      # 不在 MODELS_ROOT → 跳过
    "/data/models/gguf/onlyone",                      # 段数不足 → 跳过
])
chk("group_by_model: 同模型多分片归一组",
    _g.get(("repoA", "modelX")) is not None and len(_g[("repoA", "modelX")]) == 2, str(list(_g)))
chk("group_by_model: 仓库级直放 gguf → model_dir 为空串",
    _g.get(("repoB", "")) == ["/data/models/gguf/repoB/direct.gguf"], str(list(_g)))
chk("group_by_model: 非 MODELS_ROOT 路径被忽略",
    not any(k[0] == "elsewhere" for k in _g), str(list(_g)))
chk("group_by_model: 段数不足被忽略",
    not any(k[0] == "onlyone" for k in _g), str(list(_g)))


# ── parse_model_meta: 解析 _MODEL_META_SCAN 输出 ────────────────────────
_meta = C.parse_model_meta(
    "===G===\n"
    "/data/models/gguf/r/m/f-00001-of-00002.gguf|8192|15|llama|8\n"
    "/data/models/gguf/r/m/f-00002-of-00002.gguf||||\n"
    "not-a-path|1|2|3|4\n"                            # 不以 / 开头 → 跳过
    "short|1|2\n"                                     # 段数不足 → 跳过
    "===P===\n"
    "qwen3.8-27b-mtp|32768|8080|unsloth|8|0|\n"
    "incomplete|1|2\n"                                # 段数不足 → 跳过
)
chk("parse_model_meta: G 段解析出 gguf 明细",
    _meta["gguf"]["/data/models/gguf/r/m/f-00001-of-00002.gguf"]
    == {"ctx": 8192, "file_type": 15, "arch": "llama", "head_count_kv": 8},
    str(_meta["gguf"].get("/data/models/gguf/r/m/f-00001-of-00002.gguf")))
chk("parse_model_meta: G 段空字段 → None（非 0/非异常）",
    _meta["gguf"]["/data/models/gguf/r/m/f-00002-of-00002.gguf"]
    == {"ctx": None, "file_type": None, "arch": "", "head_count_kv": None},
    str(_meta["gguf"].get("/data/models/gguf/r/m/f-00002-of-00002.gguf")))
chk("parse_model_meta: G 段非法/过短行被跳过",
    len(_meta["gguf"]) == 2, f"n={len(_meta['gguf'])}")
chk("parse_model_meta: P 段解析出 conf 参数（值为字符串）",
    _meta["params"]["qwen3.8-27b-mtp"]
    == {"ctx": "32768", "port": "8080", "backend": "unsloth",
        "threads": "8", "n_cpu_moe": "0", "rpc_target": ""},
    str(_meta["params"].get("qwen3.8-27b-mtp")))
chk("parse_model_meta: P 段过短行被跳过",
    len(_meta["params"]) == 1, f"n={len(_meta['params'])}")
chk("parse_model_meta: 空输入 → 两个空字典（不抛）",
    C.parse_model_meta("") == {"gguf": {}, "params": {}})


# ── _reqlog_aggregate: 加权口径聚合（minutes=None ⇒ 纯函数）─────────────
_recs = [
    {"t": 100, "d_prompt_tokens_total": 100, "d_tokens_predicted_total": 200,
     "d_prompt_seconds_total": 1.0, "d_tokens_predicted_seconds_total": 4.0,
     "dt_s": 10.0, "d_prompt_tokens_cached_total": 50, "d_n_decode_total": 2,
     "restart": False, "requests_processing": 1, "slots_busy": 1, "port": 8080},
    {"t": 200, "d_prompt_tokens_total": 100, "d_tokens_predicted_total": 300,
     "d_prompt_seconds_total": 1.0, "d_tokens_predicted_seconds_total": 6.0,
     "dt_s": 10.0, "d_prompt_tokens_cached_total": 50, "d_n_decode_total": 3,
     "restart": True, "requests_processing": 2, "slots_busy": 2, "port": 8081},
]
_a = C._reqlog_aggregate(_recs)
chk("_reqlog_aggregate: 计数与累加正确",
    _a["n"] == 2 and _a["p_tok"] == 200 and _a["g_tok"] == 500
    and _a["p_sec"] == 2.0 and _a["g_sec"] == 10.0 and _a["wall"] == 20.0
    and _a["cached_tok"] == 100 and _a["decode_n"] == 5 and _a["restarts"] == 1,
    f"n={_a['n']} g_tok={_a['g_tok']} restarts={_a['restarts']}")
chk("_reqlog_aggregate: 吞吐**加权**（Σtok/Σsec，非逐条比值均值）",
    _a["p_tps"] == 100.0 and _a["g_tps"] == 50.0,
    f"p_tps={_a['p_tps']} g_tps={_a['g_tps']}")
chk("_reqlog_aggregate: 墙钟口径字段存在（前端并列两列）",
    _a["p_tps_wall"] == 10.0 and _a["g_tps_wall"] == 25.0 and _a["g_busy_ratio"] == 0.5,
    f"p_wall={_a['p_tps_wall']} g_wall={_a['g_tps_wall']} busy={_a['g_busy_ratio']}")
chk("_reqlog_aggregate: peak/first/last/span/ports",
    _a["peak_proc"] == 2 and _a["peak_slots"] == 2 and _a["first"] == 100
    and _a["last"] == 200 and _a["span_s"] == 100 and _a["ports"] == {8080, 8081},
    f'{_a["first"]}-{_a["last"]} span={_a["span_s"]} ports={_a["ports"]}')
_e = C._reqlog_aggregate([])
chk("_reqlog_aggregate: 空输入 → 除数为 0 时速率给 None（不是 0/异常）",
    _e["n"] == 0 and _e["p_tps"] is None and _e["g_tps"] is None
    and _e["p_tps_wall"] is None and _e["g_busy_ratio"] is None and _e["span_s"] is None,
    f'p_tps={_e["p_tps"]} span={_e["span_s"]}')


# ── agent_ledger_freshness: 台账新鲜度（用最新一条 ts）────────────────────
chk("agent_ledger_freshness: 空列表 → 空字典",
    C.agent_ledger_freshness([]) == {})
_t1 = time.strftime("%Y%m%d%H%M%S", time.localtime(time.time() - 120))
_t2 = time.strftime("%Y%m%d%H%M%S", time.localtime(time.time() - 10))
_f = C.agent_ledger_freshness([{"ts": _t1, "label": "old"}, {"ts": _t2, "label": "new"}])
chk("agent_ledger_freshness: 取**最新** ts 对应的 label（非最后一行顺序）",
    _f.get("label") == "new", str(_f))
chk("agent_ledger_freshness: age_s 为 int 且 ≈ 10s（±5s 容差）",
    isinstance(_f.get("age_s"), int) and abs(_f["age_s"] - 10) <= 5, str(_f))
_bad = C.agent_ledger_freshness([{"ts": "garbage", "label": "L"}])
chk("agent_ledger_freshness: ts 不可解析 → age_s=None 但保留 label",
    _bad == {"label": "L", "age_s": None}, str(_bad))
try:
    C.agent_ledger_freshness([{"label": "no-ts"}])
    chk("agent_ledger_freshness: 缺 ts 键 → KeyError [BUG-PIN]", False, "未抛异常")
except KeyError:
    chk("agent_ledger_freshness: 缺 ts 键 → KeyError [BUG-PIN]", True)


# ── resolve_quant/infer_quant 的组合语义（ledger 优先）────────────────────
chk("resolve_quant: 无 ledger 登记时回退文件名推断（来源=filename）",
    (lambda r: r[1] in ("filename", "none"))(C.resolve_quant("__no_such_alias__", "m-Q4_K_M.gguf")),
    str(C.resolve_quant("__no_such_alias__", "m-Q4_K_M.gguf")))
chk("resolve_quant: 无登记且文件名无量化串 → ('', 'none')",
    C.resolve_quant("__no_such_alias__", "plain.gguf") == ("", "none"),
    str(C.resolve_quant("__no_such_alias__", "plain.gguf")))


# ── _free_quota_effective: 免费档日限额的【主口径】= 直读服务端 `free_limit` -------------------
#   （R4 裁【甲】· 2026-10-20）为什么钉它：`_free_quota(is_free_tier)` 是**代理判据** —— 官方 SDK 页逐字
#   「`limit` … depends on **total credits purchased** and is **independent of `is_free_tier`**」
#   （见 ADR-0003 L193 的 2026-10-20 收窄段 + L238 的就地更正）⇒ 主口径改为**直读**
#   `free_model_daily_requests.limit`；取不到 ⇒ fail-closed 兜底并**如实报出来源**（不静默）。
#   判据（先写死，后实施）：① 缺 / `None` / 非数 ⇒ 取 50 **且** `source='fallback-50'`；
#   ② ★ **同源对照**：`is_free_tier=False` 但 `limit=50` 的样本上，**直读（甲）与推断（乙）的结论必须不同**
#      —— 否则本组判据恒真（`limit` 与 `is_free_tier` 只在"从未充 / 已充过"两端重合）。
#   ⚠ 用 `getattr` 取函数：**先验红**时函数尚不存在 ⇒ 本组报 FAIL（而不是整文件崩掉）。
_fqe = getattr(C, "_free_quota_effective", None)


def _fqe_str(info):
    return str(_fqe(info)) if _fqe else "<缺 _free_quota_effective>"


def _legacy_proxy(info):
    """★ **旧口径（乙 · 代理判据）的参照实现** —— 只存在于本测试里，**不是**生产路径。

    规则 = 改动前的 `_free_quota(is_free_tier)`：`is_free_tier is False ⇒ 1000 else 50`。
    ★ 为什么要**本地**留一份：同源对照要求「甲（直读）与乙（推断）的结论必须不同」，否则本组判据恒真；
      对照项若复用生产函数，则生产函数一改，对照随之失效（**判据会被实现拖着走**）。
    """
    return 1000 if info.get("is_free_tier") is False else 50


chk("_free_quota_effective: 直读 free_limit（权威字段优先）",
    bool(_fqe) and _fqe({"is_free_tier": False, "free_limit": 1000}) == (1000, "limit"),
    _fqe_str({"is_free_tier": False, "free_limit": 1000}))
chk("_free_quota_effective: ★同源对照 —— is_free_tier=False 但 limit=50 ⇒ 直读 50（**不**按推断给 1000）",
    bool(_fqe) and _fqe({"is_free_tier": False, "free_limit": 50}) == (50, "limit"),
    _fqe_str({"is_free_tier": False, "free_limit": 50}))
chk("★甲/乙结论必须不同（否则本组判据恒真）: 直读 limit=50 vs 推断 is_free_tier=False",
    bool(_fqe) and _fqe({"is_free_tier": False, "free_limit": 50})[0] != _legacy_proxy({"is_free_tier": False}),
    f"直读={_fqe({'is_free_tier': False, 'free_limit': 50})[0] if _fqe else '?'} 推断={_legacy_proxy({'is_free_tier': False})}")
chk("_free_quota_effective: 缺字段 ⇒ fail-closed 50 且**如实报出** source='fallback-50'",
    bool(_fqe) and _fqe({"is_free_tier": False}) == (50, "fallback-50"),
    _fqe_str({"is_free_tier": False}))
chk("_free_quota_effective: free_limit=None ⇒ 兜底 50 + fallback-50（判不了 ≠ 猜）",
    bool(_fqe) and _fqe({"is_free_tier": False, "free_limit": None}) == (50, "fallback-50"),
    _fqe_str({"is_free_tier": False, "free_limit": None}))
chk("_free_quota_effective: 非数字串 ⇒ 兜底 50 + fallback-50",
    bool(_fqe) and _fqe({"is_free_tier": True, "free_limit": "abc"}) == (50, "fallback-50"),
    _fqe_str({"is_free_tier": True, "free_limit": "abc"}))
chk("_free_quota_effective: 0/负 ⇒ 兜底 50 + fallback-50（不把 0 当有效上限）",
    bool(_fqe) and _fqe({"is_free_tier": False, "free_limit": 0}) == (50, "fallback-50") and
                   _fqe({"is_free_tier": False, "free_limit": -3}) == (50, "fallback-50"),
    _fqe_str({"is_free_tier": False, "free_limit": 0}))


# ── R1 实施面（2026-10-20 · 裁【丙】）：旧件四件【已删】+ 派发侧件成为【单件承载】──────────────
#   裁【丙】= 废弃 `.egress_daily.json`（**恒 0 的死件** + 与写侧**两套日界口径**）⇒ 本地计数面
#   **单件承载** = 派发侧 `ops/.egress_station.json`（由 `agent-cli.ps1` 的 `Write-EgressStationPick` 写）。
#   ★ 两块判据：**(a) 旧件四件真的不在了**（防"删了又被加回来" —— 同一类死件复活的守卫）；
#     **(b) 新读者 `_egress_station_today` 的 fail-closed 五态**（缺件 / 坏 JSON / 结构不符 / 值非法 /
#        **跨 UTC 日** ⇒ 判不了，**不印 0、不猜**）。★ (b) 用**注入式路径**（写系统 TEMP、**不落仓**）
#        ⇒ 离线真跑（同 PS 侧状态件夹具的处置）。
_est = getattr(C, "_egress_station_today", None)
_GONE = ("EGRESS_DAILY_FILE", "_egress_daily", "_egress_bump", "_egress_save")
_still = [n for n in _GONE if hasattr(C, n)]
chk("R1-①(旧件四件已删): 门面上不再有 EGRESS_DAILY_FILE/_egress_daily/_egress_bump/_egress_save（防死件复活）",
    (not _still), f"仍可达: {_still}")
chk("R1-⑨(FREE_QUOTA_PAID 已删): 门面上不再有历史档位常量（档位真值源 = 服务端 free_limit）",
    not hasattr(C, "FREE_QUOTA_PAID"), "仍可达: FREE_QUOTA_PAID")

# ── RPC 加载前回收 halogen 容器 + worker 自动选路 ─────────────────────────
# 现场（2026-10-22）：`load glm-5.3-flash` 时 A/B/C 的 qwen halogen 容器未回收，
# 8080 仍由容器服务 ⇒ 远端 infer-load/健康检查命中 qwen，GLM 实际未起却报 READY。
# 2026-10-25：选路改为纯函数 resolve_rpc_worker（A 被 qwen 占用 ⇒ 自动改 C），
#   回收范围收窄到 head(B)+选中 worker；非 worker 站的 qwen 保留。
_MISSING = object()


def _swap(name, value):
    """替换属性并返回还原闭包 —— `C` 是**代理**，赋值会落到所有已绑定该名字的模块。

    ⚠ 为什么不能只换门面：拆分后 `_load_rpc` 等函数住在 `cluster_runtime`，它读的是
      **本模块全局**；只换 `cluster.<name>` 会让桩全部落空（实测真的向站上派发了）。
    兼容"属性尚不存在"（先验红阶段新函数还没写）。
    """
    old = getattr(C, name, _MISSING)
    setattr(C, name, value)

    def _restore():
        if old is _MISSING:
            try:
                delattr(C, name)
            except AttributeError:
                pass
        else:
            setattr(C, name, old)

    return _restore


def _rpc_reclaim_probe(worker=None, conf_target="", probe=None, reclaim=None,
                       alive="10.10.10.1:50052 10.10.11.3:50052",
                       decl="10.10.10.1:50052 10.10.11.3:50052"):
    """RPC 编排夹具。probe 键 = target(ip:port)；reclaim 键 = 站名。

    calls 记录"被要求回收的站"（只记 reclaim_and_unload 的入参）——
    T4 的"回收 0 次"与 T5 的"两站都收到"都靠它断言。
    """
    calls, built, runs = [], [], []
    probe = probe if probe is not None else {
        "10.10.10.1:50052": {"state": "free", "reason": ""},
        "10.10.11.3:50052": {"state": "free", "reason": ""},
    }
    reclaim = reclaim or {}
    by_station = {C.RPC_WORKER_STATIONS[ip]: v for ip, v in probe.items()
                  if ip in C.RPC_WORKER_STATIONS}

    def _reclaim_and_unload(st):
        calls.append(st)
        return reclaim.get(st) or {"station": st, "ok": True, "steps": []}

    def _ssh_run(st, cmd, **k):
        runs.append(cmd)
        return (True, decl) if cmd.startswith("rpc-nodes --all") else (True, alive)

    restores = [
        _swap("_reclaim_containers", lambda st, al=None: (True, "")),
        _swap("reclaim_and_unload", _reclaim_and_unload),
        _swap("ssh_stream", lambda *a, **k: 0),
        _swap("ssh_run", _ssh_run),
        _swap("_build_infer_load_cmd", lambda *a, **k: built.append((a, k)) or "true"),
        _swap("_conf_rpc_target", lambda st, al: conf_target),
        _swap("probe_worker_state",
              lambda st: by_station.get(st) or {"state": "unknown", "reason": "未探测"}),
        # 先验红期旧实现仍调 _probe_worker_busy；桩成"空闲"以隔离网络，
        # 且不会掩盖 T2/T4（旧代码在这些输入下选 conf/显式，断言照样红）。
        _swap("_probe_worker_busy", lambda st: ""),
    ]
    try:
        rc = C._load_rpc("glm-5.3-flash", "B", None, worker)
    finally:
        for _r in reversed(restores):
            _r()
    return rc, calls, built, runs


_rc_rpc, _reclaim_calls, _built, _runs = _rpc_reclaim_probe()
chk("RPC load 默认(无 conf): 自动选 A，**head(B) 先停、worker(A) 后停**（O-178），非 worker C 保留",
    _rc_rpc == 0 and _reclaim_calls == ["B", "A"] and _built
    and _built[-1][0][3] == "10.10.10.1:50052"
    and "rpc-nodes --start 'glm-5.3-flash' '10.10.10.1:50052'" in _runs,
    f"rc={_rc_rpc} calls={_reclaim_calls} built={_built} runs={_runs}")

# 2026-10-25 自动切换：A 有 halogen ⇒ 自动改 C，A 的 qwen 不被回收。
_rc_sw, _calls_sw, _built_sw, _runs_sw = _rpc_reclaim_probe(
    conf_target="10.10.10.1:50052",
    probe={"10.10.10.1:50052": {"state": "busy", "reason": "halogen"},
           "10.10.11.3:50052": {"state": "free", "reason": ""}})
chk("RPC load 自动切换: A 忙(halogen) ⇒ 选 C + 回收 B/C（A 的 qwen 保留）",
    _rc_sw == 0 and _calls_sw == ["B", "C"]
    and _built_sw[-1][0][3] == "10.10.11.3:50052"
    and "rpc-nodes --start 'glm-5.3-flash' '10.10.11.3:50052'" in _runs_sw,
    f"rc={_rc_sw} calls={_calls_sw} built={_built_sw} runs={_runs_sw}")

# 两站都忙 ⇒ 改用 C（回收 C，保 A）；只有 C 不可用时才回退 A。
_rc_fb, _calls_fb, _built_fb, _ = _rpc_reclaim_probe(
    conf_target="10.10.10.1:50052",
    probe={"10.10.10.1:50052": {"state": "busy", "reason": "halogen"},
           "10.10.11.3:50052": {"state": "busy", "reason": "halogen"}})
chk("RPC load 自动选路: 两站都忙 ⇒ 改用 C（回收 C，保 A）",
    _rc_fb == 0 and _calls_fb == ["B", "C"] and _built_fb[-1][0][3] == "10.10.11.3:50052",
    f"rc={_rc_fb} calls={_calls_fb} built={_built_fb}")

# 2026-10-22 单 worker 指派：head 固定 B，worker 由用户选 A|C。
_rc_w, _calls_w, _built_w, _runs_w = _rpc_reclaim_probe(worker="C")
chk("RPC load --worker C: 映射 10.10.11.3:50052 并透传 --rpc-target（回收 B/C）",
    _rc_w == 0 and _calls_w == ["B", "C"] and _built_w
    and _built_w[-1][0][3] == "10.10.11.3:50052"
    and "rpc-nodes --start 'glm-5.3-flash' '10.10.11.3:50052'" in _runs_w,
    f"rc={_rc_w} calls={_calls_w} built={_built_w} runs={_runs_w}")
_rc_wa, _calls_wa, _built_wa, _runs_wa = _rpc_reclaim_probe(worker="A")
chk("RPC load --worker A: 映射 10.10.10.1:50052（回收 B 先、A 后，O-178）",
    _rc_wa == 0 and _calls_wa == ["B", "A"]
    and _built_wa and _built_wa[-1][0][3] == "10.10.10.1:50052",
    f"rc={_rc_wa} calls={_calls_wa} built={_built_wa}")

# 无 --worker 时从 conf 读出的单 worker 目标也应约束预启动与 infer-load。
_rc_c, _calls_c, _built_c, _runs_c = _rpc_reclaim_probe(conf_target="10.10.10.1:50052")
chk("RPC load 默认: conf 单 worker A ⇒ 预启动与 --rpc-target 都只带 A（回收 B 先、A 后，O-178）",
    _rc_c == 0 and _calls_c == ["B", "A"] and _built_c
    and _built_c[-1][0][3] == "10.10.10.1:50052"
    and "rpc-nodes --start 'glm-5.3-flash' '10.10.10.1:50052'" in _runs_c,
    f"rc={_rc_c} calls={_calls_c} built={_built_c} runs={_runs_c}")

# 2026-10-23: 显式 worker 的失败面 —— 死节点 / 未声明节点必须在加载前中止。
_rc_dead, _, _built_dead, _ = _rpc_reclaim_probe(
    worker="C", alive="10.10.10.1:50052")
chk("RPC load --worker C: 目标不在存活清单 ⇒ 加载前中止",
    _rc_dead == 1 and not _built_dead, f"rc={_rc_dead} built={_built_dead}")
_rc_undecl, _, _built_undecl, _ = _rpc_reclaim_probe(
    worker="C", decl="10.10.10.1:50052")
chk("RPC load --worker C: 目标不在 nodes.env 声明 ⇒ 加载前中止",
    _rc_undecl == 1 and not _built_undecl, f"rc={_rc_undecl} built={_built_undecl}")

# ── 三态选路的编排级断言（T3-T7，见 DESIGN §10.4）─────────────────────────
_U_T = {"state": "unknown", "reason": "ssh-failed: timeout"}
_B_T = {"state": "busy", "reason": "halogen"}
_F_T = {"state": "free", "reason": ""}

_rc_t3, _calls_t3, _built_t3, _ = _rpc_reclaim_probe(
    conf_target="10.10.10.1:50052",
    probe={"10.10.10.1:50052": _U_T, "10.10.11.3:50052": _F_T})
chk("T3 编排: conf A unknown + C free ⇒ 选 C，A 不被回收",
    _rc_t3 == 0 and _calls_t3 == ["B", "C"] and "A" not in _calls_t3
    and _built_t3[-1][0][3] == "10.10.11.3:50052",
    f"rc={_rc_t3} calls={_calls_t3} built={_built_t3}")

_rc_t4, _calls_t4, _built_t4, _ = _rpc_reclaim_probe(
    worker="C", probe={"10.10.11.3:50052": _U_T})
chk("T4 编排: 显式 --worker C 但 C unknown ⇒ 中止且回收 0 次",
    _rc_t4 == 1 and _calls_t4 == [] and not _built_t4,
    f"rc={_rc_t4} calls={_calls_t4} built={_built_t4}")

_rc_t5, _calls_t5, _built_t5, _ = _rpc_reclaim_probe(
    conf_target="10.10.10.1:50052",
    probe={"10.10.10.1:50052": _B_T,
           "10.10.11.3:50052": {"state": "busy", "reason": "port8080"}})
chk("T5 编排: worker 被普通引擎占用 ⇒ B、C 都收到 reclaim_and_unload",
    _rc_t5 == 0 and _calls_t5 == ["B", "C"], f"rc={_rc_t5} calls={_calls_t5}")

_rc_t6, _calls_t6, _built_t6, _runs_t6 = _rpc_reclaim_probe(
    reclaim={"B": {"station": "B", "ok": False, "steps": [
        {"name": "infer-unload", "ok": False, "rc": 1, "detail": "rc=1"}]}})
chk("T6 编排: head(B) 卸载失败 ⇒ 中止，未调 rpc-nodes --start",
    _rc_t6 == 1 and not _built_t6
    and not any("--start" in c for c in _runs_t6),
    f"rc={_rc_t6} built={_built_t6} runs={_runs_t6}")

_rc_t7, _calls_t7, _built_t7, _ = _rpc_reclaim_probe(
    reclaim={"A": {"station": "A", "ok": False, "steps": [
        {"name": "infer-unload", "ok": False, "rc": 1, "detail": "rc=1"}]}})
chk("T7 编排: worker(A) 卸载失败 ⇒ 中止", _rc_t7 == 1 and not _built_t7,
    f"rc={_rc_t7} built={_built_t7}")

# 非法/越界指派必须响亮拒绝（不静默退化）。
chk("load --worker B: 非法 worker 拒绝（head 固定 B，B 不能当 worker）",
    C.cmd_load("glm-5.3-flash", None, None, "B") == 1, "应 rc=1")
chk("load --worker 非 RPC 模型: 拒绝",
    C.cmd_load("gpt-oss-120b", None, None, "A") == 1, "应 rc=1")
chk("load --worker + 强制单机后端: 拒绝（矛盾组合）",
    C.cmd_load("glm-5.3-flash", "unsloth", None, "A") == 1, "应 rc=1")

# ── O-178 × O-175 交点：反向冲突预检（2026-10-28）───────────────────────
# 现场：`infer-unload` 会停 `rpc-server@*`（本地 + 按 nodes.env 停远端），而
# `_load_container_model` / 普通 load 的第一步就是 `reclaim_and_unload(该站)`。
# ⇒ 在**正给别的模型当 worker** 的站上加载，必然停掉那个 worker ⇒ 对面 head 的
#   ggml-rpc 判「对端消失」⇒ `GGML_ABORT`（core-dump，30 天 12 次里的 7 次）。
# 判据必须是**拒绝**（不是警告）：这条通路一旦走通，崩的是另一台机器上的生产进程。
chk("O-178/O-175 冲突判定: 别的模型占着 worker ⇒ 报出该模型",
    C._worker_conflict(["rpc-server@deepseek-v4-flash-0731.service"], "gpt-oss-120b")
    == "deepseek-v4-flash-0731")
chk("O-178/O-175 冲突判定: 同一模型（重载自己）⇒ 不算冲突",
    C._worker_conflict(["rpc-server@glm-5.3-flash.service"], "glm-5.3-flash") == "")
chk("O-178/O-175 冲突判定: 没有 rpc-server ⇒ 无冲突",
    C._worker_conflict(["llama-server@glm-5.3-flash.service"], "x") == "")

_restore = _swap("_active_rpc_workers",
                 lambda st: (True, ["rpc-server@deepseek-v4-flash-0731.service"]))
# ★ 安全网：即使"预检"回归失效，也**绝不**落到真加载（2026-10-28 实测教训：桩错位
#   会把 `force` 当成 `keep`，真的向 B 站派发 load 并换掉生产模型）。这里把加载与回收
#   全部钉死成"记录+立即返回"，判据只看退出码。
_load_calls, _reclaim_dummy = [], []
_safe = [
    _swap("reclaim_and_unload", lambda st, al=None: (
        _reclaim_dummy.append((st, al)), {"station": st, "ok": True, "steps": []})[1]),
    _swap("ssh_stream", lambda st, cmd: (0)),
    _swap("_guard_capacity", lambda st, al: 0),
]
try:
    _rc_g = C._guard_worker_conflict("A", "gpt-oss-120b")
    _rc_gf = C._guard_worker_conflict("A", "gpt-oss-120b", True)
    _rc_gs = C._guard_worker_conflict("A", "deepseek-v4-flash-0731")
    _rc_gl = C.cmd_load("gpt-oss-120b-a", None, None, None)      # 按站路由到 A
finally:
    for _r in reversed(_safe):
        _r()
    _restore()
chk("O-178/O-175 预检: 冲突 ⇒ exit 3 · --force 放行 · 同一模型放行",
    _rc_g == 3 and _rc_gf == 0 and _rc_gs == 0,
    f"guard={_rc_g} force={_rc_gf} same={_rc_gs}")
chk("O-178/O-175 预检接线: cmd_load 走到目标站时被拦住（不是死代码）",
    _rc_gl == 3, f"rc={_rc_gl}")

_restore = _swap("_active_rpc_workers", lambda st: (False, []))
try:
    _rc_unk = C._guard_worker_conflict("A", "gpt-oss-120b")
finally:
    _restore()
chk("O-178/O-175 预检: 判不了（ssh 失败）不阻断加载，但必须留痕",
    _rc_unk == 0, f"rc={_rc_unk}")

# ── O-179 单站多模型：P0 容量门 + P1 alias 级卸载（2026-10-28）───────────
# 准则从「同站禁止叠加」改为「按容量准入」：带 --keep 时才走 alias 级回收 + 容量门。
# 不带 --keep ⇒ 行为必须与基线逐字一致（69 个既有测试即判据）。
chk("O-179 容量判据: FITS/TIGHT 放行 · NO_FIT/UNKNOWN 拒绝（判不了≠通过）",
    C._capacity_ok("FITS") and C._capacity_ok("TIGHT")
    and not C._capacity_ok("NO_FIT") and not C._capacity_ok("UNKNOWN"))


def _cap(verdict, ok=True):
    """桩掉 estimate_load + GTT 读数，只验 estimate 判据到退出码的映射（不碰网络）。

    GTT 单独桩成「读不到」⇒ 走回退分支（GTT 门槛另有 `_cap_gtt` 覆盖）。
    """
    _r = _swap("estimate_load", lambda st, al: {
        "ok": ok, "verdict": verdict, "need_gib": 60.0, "mem": {"free": 20.0},
        "reasons": ["合成理由"], "advice": ["合成建议"]})
    _rg = _swap("_station_gtt", lambda st: (False, 0.0, 0.0))
    try:
        return C._guard_capacity("B", "qwen3.8-27b-mtp")
    finally:
        _rg()
        _r()


chk("O-179 容量门: NO_FIT ⇒ exit 4",
    _cap("NO_FIT") == 4)
chk("O-179 容量门: UNKNOWN ⇒ exit 4",
    _cap("UNKNOWN") == 4)
chk("O-179 容量门: ok=False（缺 conf/元数据）⇒ exit 4",
    _cap("FITS", ok=False) == 4)
chk("O-179 容量门: FITS ⇒ 放行",
    _cap("FITS") == 0)
chk("O-179 容量门: 容器模型不走 estimate（放行，P2 再补）",
    C._guard_capacity("C", "qwen3.8-flash-next") == 0)

# ★★ 这条**必须完全隔离**：`keep=True` 是关键字参数（曾用位置参数把 force 当成 keep ⇒
#   真的向 B 站派发 load，换掉了生产 deepseek）。同时把 `_load_rpc` 钉成哨兵：
#   万一"RPC 不支持 keep"那条判据被回退，结果是 99 而不是一次真加载。
_rpc_calls = []
_r1 = _swap("_active_rpc_workers", lambda st: (True, []))
_r2 = _swap("_load_rpc", lambda *a, **k: (_rpc_calls.append(a), 99)[1])
try:
    _rc_kr = C.cmd_load("glm-5.3-flash", None, None, None, keep=True)
finally:
    _r2()
    _r1()
chk("O-179 --keep 对 RPC 双机: 拒绝且**不落到真加载**",
    _rc_kr == 1 and not _rpc_calls, f"rc={_rc_kr} load_calls={_rpc_calls}")

_seen = {}
_r1 = _swap("_reclaim_containers", lambda st, al=None: (_seen.__setitem__("containers_alias", al), (True, ""))[1])
_r2 = _swap("ssh_stream", lambda st, cmd: (_seen.__setitem__("cmd", cmd), 0)[1])
try:
    C.reclaim_and_unload("B", "glm-5.3-flash")
    _seen["with_alias"] = True
    C.reclaim_and_unload("B")
    _seen["full_cmd"] = _seen["cmd"]
finally:
    _r2()
    _r1()
chk("O-179 alias 级卸载: 透传 infer-unload <alias>，无参仍是全停",
    _seen.get("cmd") is not None and _seen["full_cmd"] == "infer-unload"
    and _seen["containers_alias"] is None,
    f"_seen={_seen}")

_sent = []
_r = _swap("ssh_run", lambda st, cmd, timeout=None: (_sent.append(cmd), (True, ""))[1])
try:
    _ok_skip, _d_skip = C._reclaim_containers("B", "glm-5.3-flash")
    _n_after_skip = len(_sent)                       # 跳过必须发生在发命令**之前**
    _ok_cont, _ = C._reclaim_containers("B", "qwen3.8-flash-next")
    _n_after_container = len(_sent)
finally:
    _r()
chk("O-179 容器步: keep 下非容器别名不碰 docker；容器别名照常回收",
    _ok_skip and _n_after_skip == 0 and _ok_cont and _n_after_container == 1
    and "skipped" in _d_skip,
    f"ok_skip={_ok_skip} detail={_d_skip} sent(skip)={_n_after_skip} "
    f"sent(total)={_n_after_container}")

_unl = []


def _fake_reclaim(st, al=None):
    _unl.append((st, al))
    return {"station": st, "ok": True, "steps": []}


# ★ 先证明桩**真落到了实现所在模块**再调用 —— 否则一次"静默未生效"就是三站真卸载。
import cluster_runtime as _CR  # noqa: E402
_r = _swap("reclaim_and_unload", _fake_reclaim)
try:
    _stub_ok = _CR.reclaim_and_unload is _fake_reclaim
    _rc_u = C.cmd_unload("glm-5.3-flash") if _stub_ok else 99
finally:
    _r()
chk("O-179 unload --alias: 三站都只卸该别名",
    _stub_ok and _rc_u == 0 and len(_unl) == 3
    and all(a == "glm-5.3-flash" for _, a in _unl),
    f"stub_ok={_stub_ok} rc={_rc_u} calls={_unl}")

# ── O-179 P0 补强：UMA 单池口径 + 站级预留（借鉴 GPUStack §2.1/§2.2）────────
# 为什么是 (ok, alloc) 而不是 (ok, free)：判据要同时回答「放不放得下」和「还剩多少」，
# 后者在拒绝文案里必须能直接给出来（否则用户只能自己算）。
chk("O-179 UMA 口径: 空站 125.8G − 预留 8G ≥ 41G ⇒ 放行",
    C._uma_fit(125.8, 0.0, 8.0, 41.0) == (True, 117.8),
    f"{C._uma_fit(125.8, 0.0, 8.0, 41.0)}")
chk("O-179 UMA 口径: 已占 84G 再放 41G ⇒ 拒绝（alloc 33.8）",
    C._uma_fit(125.8, 84.0, 8.0, 41.0) == (False, 33.8),
    f"{C._uma_fit(125.8, 84.0, 8.0, 41.0)}")
chk("O-179 UMA 口径: 预留先吃掉余量 ⇒ 拒绝（alloc 7.8）",
    C._uma_fit(125.8, 110.0, 8.0, 8.0) == (False, 7.8),
    f"{C._uma_fit(125.8, 110.0, 8.0, 8.0)}")
chk("O-179 UMA 口径: 已用超过总量 ⇒ alloc 夹到 0（不返回负数）",
    C._uma_fit(125.8, 200.0, 8.0, 1.0) == (False, 0.0),
    f"{C._uma_fit(125.8, 200.0, 8.0, 1.0)}")


def _cap_gtt(verdict, gtt, need=60.0):
    _r1 = _swap("estimate_load", lambda st, al: {
        "ok": True, "verdict": verdict, "need_gib": need, "mem": {"free": 100.0},
        "reasons": [], "advice": []})
    _r2 = _swap("_station_gtt", lambda st: gtt)
    try:
        return C._guard_capacity("B", "qwen3.8-27b-mtp")
    finally:
        _r2()
        _r1()


chk("O-179 容量门(GTT): estimate 说 FITS 但 GTT 余量不足 ⇒ 仍拒（exit 4）",
    _cap_gtt("FITS", (True, 84.0, 125.8), need=60.0) == 4)
chk("O-179 容量门(GTT): GTT 足够 ⇒ 放行",
    _cap_gtt("FITS", (True, 0.0, 125.8), need=41.0) == 0)
chk("O-179 容量门(GTT): 读不到 GTT ⇒ 回退 estimate 的 verdict（放行但留痕）",
    _cap_gtt("FITS", (False, 0.0, 0.0), need=41.0) == 0)
chk("O-179 容量门(GTT): estimate 已判 NO_FIT ⇒ 不因 GTT 空闲而放行",
    _cap_gtt("NO_FIT", (True, 0.0, 125.8), need=41.0) == 4)

# ── O-179 P2：端口预留记录（真值 = 各别名 conf 的 PORT，不造第二张表）──────
# 现场缺口：两个别名的 conf 都写 PORT=8080（gpt-oss-20b / deepseek），`--keep` 叠加时
# 第二个会 bind 失败，只能靠 15min 健康超时发现。判据 = **同站已运行别名各自的 conf PORT**
# 与目标端口比对（不读 ss 猜占用者：ss 只知道"有人占"，不知道"是谁"）。
chk("O-179 端口冲突: 目标 8080 已被 'gpt-oss-20b' 占 ⇒ 报出该别名",
    C._port_clash(8080, {"gpt-oss-20b": 8080, "qwen3.8-27b-mtp": 18080}) == "gpt-oss-20b")
chk("O-179 端口冲突: 18080 无重叠 ⇒ 空",
    C._port_clash(18080, {"gpt-oss-20b": 8080}) == "")
chk("O-179 端口冲突: 站上没别的模型 ⇒ 空",
    C._port_clash(8080, {}) == "")
chk("O-179 端口冲突: 两个别名撞同一端口 ⇒ 也报（不只看第一个）",
    C._port_clash(18080, {"a": 18080, "b": 8080}) == "a")


def _port_guard(target, others, ok=True):
    _r1 = _swap("_model_port", lambda st, al: (target, "conf"))
    _r2 = _swap("_station_model_ports", lambda st, exclude=None: (ok, others))
    try:
        return C._guard_port("B", "qwen3.8-27b-mtp")
    finally:
        _r2()
        _r1()


chk("O-179 端口门: 与站上其它模型撞口 ⇒ exit 5",
    _port_guard(8080, {"gpt-oss-20b": 8080}) == 5)
chk("O-179 端口门: 端口不撞 ⇒ 放行",
    _port_guard(18080, {"gpt-oss-20b": 8080}) == 0)
chk("O-179 端口门: 判不了（ssh 失败）不阻断，但留痕",
    _port_guard(8080, {}, ok=False) == 0)

# ── O-179 P2-余：`load --port N` + 健康探测「按 alias 取端口」（2026-10-29）────
# 为什么必须做：`_cmd_load_c` / 通用路径 / `cmd_load_on` / ds4 / e2e 都写死 `127.0.0.1:8080`。
# 第二个模型绑 18080 后，这些探测会问候**别的模型**（或空端口），把失败伪装成超时。
chk("O-179 --port: 非法端口 ⇒ exit 1（且不碰网络）",
    C.cmd_load("glm-5.3-flash", None, None, None, port=70000) == 1)
chk("O-179 --port: 非数字 ⇒ exit 1",
    C.cmd_load("glm-5.3-flash", None, None, None, port="abc") == 1)
chk("O-179 --port: 落进 infer-load 命令",
    "--port 18081" in C._build_infer_load_cmd("x", "llama-single", None, port=18081))
chk("O-179 --port: 未给 ⇒ 命令里不出现 --port",
    "--port" not in C._build_infer_load_cmd("x", "llama-single"))

chk("O-179 端口门: 显式 --port 优先于 conf（撞口照样拦）",
    C._guard_port("B", "x", port=8080) == 5)


def _guard_port_with(others, port=None):
    _r = _swap("_station_model_ports", lambda st, exclude=None: (True, others))
    try:
        return C._guard_port("B", "x", port=port)
    finally:
        _r()


chk("O-179 端口门: 显式 18081 与站上 8080 不撞 ⇒ 放行",
    _guard_port_with({"a": 8080}, port=18081) == 0)

_r = _swap("_model_port", lambda st, al: (18080, "conf"))
try:
    _ep = C._engine_port("B", "qwen3.8-27b-mtp")
    _ep_expl = C._engine_port("B", "qwen3.8-27b-mtp", 18081)
finally:
    _r()
chk("O-179 探测端口: 按 alias 取 conf PORT；显式值优先",
    _ep == (18080, "conf") and _ep_expl == (18081, "cli"),
    f"alias={_ep} explicit={_ep_expl}")
chk("O-179 探测端口: 无 alias ⇒ 站默认 8080",
    C._engine_port("B") == (8080, "default"))


def _est_str(p):
    return str(_est(p)) if _est else "<缺 _egress_station_today>"


def _est_write(name, obj):
    p = Path(tempfile.gettempdir()) / name
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj), encoding="utf-8")
    return p


_today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
_p1 = _est_write("egress_st_ok.json", {"date": _today, "by_station": {"A": 1, "B": 0, "C": 2}, "last_used": "C"})
_r1 = _est(_p1) if _est else None
chk("R1-②(可判): 今日件 + 实名按站 ⇒ (dict, '') 且 sum == 3（**单件承载**读数正确）",
    bool(_est) and (_r1[1] == "") and (sum(_r1[0].values()) == 3),
    _est_str(_p1))
_p2 = Path(tempfile.gettempdir()) / "egress_st_none.json"
if _p2.exists():
    _p2.unlink()
chk("R1-③(fail-closed·缺件): 文件不存在 ⇒ (None, 原因非空) —— **不印 0**（判不了 ≠ 0）",
    bool(_est) and (_est(_p2)[0] is None) and bool(_est(_p2)[1]),
    _est_str(_p2))
_p3 = _est_write("egress_st_stale.json", {"date": "1970-01-01", "by_station": {"A": 9}})
chk("R1-④(fail-closed·跨 UTC 日): `date` 不是今天 ⇒ 判不了（日界与写侧同口径 = UTC）",
    bool(_est) and (_est(_p3)[0] is None), _est_str(_p3))
_p4 = _est_write("egress_st_bad.json", "{ not json")
chk("R1-⑤(fail-closed·坏 JSON): 解析失败 ⇒ 判不了（绝不静默当 0）",
    bool(_est) and (_est(_p4)[0] is None), _est_str(_p4))
_p5 = _est_write("egress_st_nostation.json", {"date": _today, "last_used": "A"})
chk("R1-⑥(fail-closed·结构不符): 缺 `by_station` ⇒ 判不了",
    bool(_est) and (_est(_p5)[0] is None), _est_str(_p5))
_p6 = _est_write("egress_st_badval.json", {"date": _today, "by_station": {"A": "x"}})
chk("R1-⑦(fail-closed·值非法): 某站计数非整数 ⇒ 判不了（不按半个计数对账）",
    bool(_est) and (_est(_p6)[0] is None), _est_str(_p6))
# ★★ **真生产者形状**（本批真跑当场抓到：夹具此前用 **python 的写形状**（`write_text(..., 'utf-8')`，**无 BOM**）
#   冒充生产者 —— 而**真写侧**是 PS5.1 的 `Set-Content -Path … -Encoding UTF8`，它落 **UTF-8 BOM**
#   ⇒ `json.loads` 见 `\ufeff` 直接抛 ⇒ **真路径下"永远不可判"**，而夹具全绿 = **假绿**。
#   ★ 教训与前案同族：**夹具的"形状"必须取自真生产者**（见 O-21 的"注入式夹具抓不到真站形态"）。
#   ⇒ 判据升级：**带 BOM 的件必须可判**（读者须用 `utf-8-sig`）。
_p7 = Path(tempfile.gettempdir()) / "egress_st_bom.json"
_p7.write_bytes(b"\xef\xbb\xbf" + json.dumps({"date": _today, "by_station": {"A": 5}}).encode("utf-8"))
chk("R1-⑧(★真生产者形状): 写侧 PS5.1 落 **BOM** ⇒ 带 BOM 的件**必须可判**（不得用 python 写形状冒充生产者）",
    bool(_est) and (_est(_p7)[0] is not None), _est_str(_p7))
for _p in (_p1, _p3, _p4, _p5, _p6, _p7):
    try:
        _p.unlink()
    except Exception:
        pass


# ── _container_cleanup_cmd: 无容器时不得误报 PORT8080_STILL_BUSY ──────────
# 现场（2026-10-22 C 站）：`docker rm -f <不存在>` 也返回 0 ⇒ 旧写法把它当成
# "确实删到了容器"，随后等 8080 空满 480s，打印 `PORT8080_STILL_BUSY` —— 假阳性。
_cmd = C._container_cleanup_cmd()
chk("cleanup: 先探容器存在再删（docker container inspect 在 docker rm 之前）",
    "docker container inspect" in _cmd
    and _cmd.index("docker container inspect") < _cmd.index("docker rm -f"),
    _cmd[:200])
chk("cleanup: 不再用 `docker rm -f … && { 等 8080 }` 的无条件等待形状",
    "docker rm -f halogen >/dev/null 2>&1 &&" not in _cmd,
    _cmd[:200])

# ── CONTAINER_MODELS 生产配方：v2 自包含 + GGUF 只作冷回退 ─────────────────
# 现场（2026-10-25）：v2 `.hgn` 实测**不挂 GGUF 目录**即可跑（tokenizer 21MB 独立搬出、
# MTP head 由 checkpoint 自带）⇒ 生产全切 halogen，GGUF 仅留一站当冷回退。
_cm = C.CONTAINER_MODELS["qwen3.8-flash-next"]
_envd = dict(e.split("=", 1) for e in _cm.get("env", ()) if "=" in e)
_mounts = set()
for _v in _cm.get("volume", ()):
    _parts = _v.split(":")
    if len(_parts) >= 2:
        _mounts.add(_parts[1])
_ckpt_env = _envd.get("HALOGEN_CHECKPOINT", "")
chk("recipe: checkpoint 指向 v2 .hgn（不再用 GGUF 三片）",
    str(_cm.get("checkpoint", "")).endswith("qwen38-flash-next-v2.hgn"),
    str(_cm.get("checkpoint")))
chk("recipe: HALOGEN_CHECKPOINT 落在已挂载 volume 内",
    any(_ckpt_env.startswith(m.rstrip("/") + "/") for m in _mounts),
    f"{_ckpt_env} vs {sorted(_mounts)}")
chk("recipe: HALOGEN_TOKENIZER=/tokenizer 且有独立挂载",
    _envd.get("HALOGEN_TOKENIZER") == "/tokenizer" and "/tokenizer" in _mounts,
    f"{_envd.get('HALOGEN_TOKENIZER')} vs {sorted(_mounts)}")
chk("recipe: 不再带 HALOGEN_DOWNLOAD / HF_ENDPOINT（GGUF 引导路径已退役）",
    "HALOGEN_DOWNLOAD" not in _envd and "HF_ENDPOINT" not in _envd,
    str(sorted(_envd)))

# ── RPC worker 选路（纯函数）：A 被 qwen/halogen 占用时自动改 C ──────────────
# 现场（2026-10-25）：三站都跑 qwen halogen；GLM/DS 的 conf RPC_TARGET 固定 A，
# 且 `_load_rpc` 会回收三站容器 ⇒ A 的 qwen 被杀。选路纯函数只做决策，不碰站。
_AW = "10.10.10.1:50052"
_CW = "10.10.11.3:50052"
_CANDS = [_AW, _CW]


_F_ = {"state": "free", "reason": ""}
_B_ = {"state": "busy", "reason": "halogen"}
_U_ = {"state": "unknown", "reason": "ssh-failed: timeout"}


def _rw(conf, probe=None, explicit=None, cands=None):
    """选路纯函数夹具。probe 键 = target(ip:port)。

    probe=None/空 dict ⇒ 全 free（保持迁移前 12 条用例可读）；非空 dict 不补默认，
    这样才能表达"缺键 = unknown"（T1/T2）。
    """
    cs = _CANDS if cands is None else cands
    if not probe:                      # 空 dict / None 都等价"全空闲"（旧 busy={} 语义）
        probe = {t: {"state": "free", "reason": ""} for t in cs}
    return C.resolve_rpc_worker(conf, cs, probe, explicit)


d = _rw(_AW)
chk("rpc-worker: 未指定且 conf 空闲 ⇒ 选 conf(A)",
    d["target"] == _AW and d["station"] == "A" and d["source"] == "conf", str(d))
d = _rw(_AW, {_AW: _B_, _CW: _F_})
chk("rpc-worker: conf(A) 被 halogen 占用、C 空闲 ⇒ 自动改 C",
    d["target"] == _CW and d["station"] == "C" and d["source"] == "auto", str(d))
d = _rw(_AW, {_AW: _B_, _CW: _B_})
chk("rpc-worker: 两站都忙 ⇒ 改用 C（回收 C，保 A）",
    d["target"] == _CW and d["source"] == "auto" and "回收" in d["reason"], str(d))
d = _rw(_AW, {_AW: _B_}, cands=[_AW])
chk("rpc-worker: conf 忙且无其他候选 ⇒ 回退 conf(A) 并标 fallback",
    d["target"] == _AW and d["source"] == "fallback", str(d))
d = _rw(_AW, {}, explicit=_CW)
chk("rpc-worker: 显式 --worker C ⇒ 选 C（显式优先）",
    d["target"] == _CW and d["source"] == "explicit", str(d))
d = _rw(_AW, {_AW: _B_, _CW: _F_}, explicit=_CW)
chk("rpc-worker: 显式 C 不受 A 忙影响",
    d["target"] == _CW and d["source"] == "explicit", str(d))
d = _rw(_AW, {}, explicit="10.10.99.99:50052")
chk("rpc-worker: 显式目标未声明 ⇒ target=None（可响亮中止）",
    d["target"] is None and d["source"] == "explicit-invalid", str(d))
d = _rw(None, {})
chk("rpc-worker: conf 未配置 ⇒ 取候选首个", d["target"] == _AW and d["source"] == "auto", str(d))
d = _rw(None, {_AW: _B_, _CW: _F_})
chk("rpc-worker: conf 未配置且首个忙 ⇒ 取下一个空闲",
    d["target"] == _CW and d["source"] == "auto", str(d))
d = _rw(_AW, {}, cands=[_CW, _AW])
chk("rpc-worker: 候选顺序被尊重（C 在前但有 conf A ⇒ 仍 A）", d["target"] == _AW, str(d))
d = _rw(_AW, {}, cands=[])
chk("rpc-worker: 候选为空 ⇒ None（判不了 ≠ 选默认）",
    d["target"] is None and d["source"] == "none", str(d))
d = _rw("10.10.99.99:50052", {})
chk("rpc-worker: conf 不在候选 ⇒ 从候选自动选，不凭空用 conf",
    d["target"] == _AW and d["source"] == "auto", str(d))
# 同源对照（防恒真）：同一输入只改 A 的状态（free → busy）⇒ 选择必须翻转
_d1, _d2 = _rw(_AW, {}), _rw(_AW, {_AW: _B_, _CW: _F_})
chk("rpc-worker 同源对照: 只改 busy(A) ⇒ 选站翻转",
    _d1["target"] == _AW and _d2["target"] == _CW, f'{_d1["target"]} -> {_d2["target"]}')

# ── T1-T4：未知态不得进入可回收分支（DESIGN §10.4）────────────────────────
d = _rw(_AW, {_AW: _U_, _CW: _U_})
chk("T1: 两站 unknown ⇒ aborted-unknown，target=None",
    d["target"] is None and d["source"] == "aborted-unknown", str(d))
d = _rw(_AW, {_AW: _B_, _CW: _U_})
chk("T2: conf 忙 + 备选 unknown ⇒ 中止（不选 C、不回收 C）",
    d["target"] is None and d["source"] == "aborted-unknown", str(d))
d = _rw(_AW, {_AW: _U_, _CW: _F_})
chk("T3: conf unknown + 备选 free ⇒ 选 C", d["target"] == _CW and d["source"] == "auto", str(d))
d = _rw(_CW, {_CW: _U_}, explicit=_CW)
chk("T4: 显式 worker unknown ⇒ aborted-unknown（显式也须探测）",
    d["target"] is None and d["source"] == "aborted-unknown", str(d))
chk("rpc-worker busy 解析: 空输出 ⇒ 空闲", C.parse_worker_busy("") == "", "")
chk("rpc-worker busy 解析: halogen ⇒ 单个忙因",
    C.parse_worker_busy("halogen\n") == "halogen", C.parse_worker_busy("halogen\n"))
chk("rpc-worker busy 解析: 双因去重且排序",
    C.parse_worker_busy("port8080\nhalogen\nhalogen\n") == "halogen+port8080",
    C.parse_worker_busy("port8080\nhalogen\nhalogen\n"))

# ── T8/T9：回收契约（薄壳，mock ssh_run）──────────────────────────────────
def _reclaim_shell(ok, out):
    restore = _swap("ssh_run", lambda st, cmd, **k: (ok, out))
    try:
        return C._reclaim_containers("A")
    finally:
        restore()


_r8 = _reclaim_shell(False, "ssh: timeout")
chk("T8: 容器回收 SSH 失败 ⇒ (False, 'ssh:...')",
    isinstance(_r8, tuple) and len(_r8) == 2 and _r8[0] is False
    and str(_r8[1]).startswith("ssh:"), str(_r8))
_r9 = _reclaim_shell(True, "PORT8080_STILL_BUSY\n")
chk("T9: 端口未释放 ⇒ (False, 'port8080-still-busy')",
    isinstance(_r9, tuple) and _r9 == (False, "port8080-still-busy"), str(_r9))


# ── E6/E7：reclaim_and_unload 的异常隔离与跳过语义（Step 10 验收补测）────
def _rau_e7():
    """容器步失败 ⇒ 跳过 unload（不发第二个写动作）。"""
    r1 = _swap("_reclaim_containers", lambda st, al=None: (False, "ssh:boom"))
    ran = {"stream": False}

    def _fake_stream(st, cmd):
        ran["stream"] = True
        return 0

    r2 = _swap("ssh_stream", _fake_stream)
    try:
        return C.reclaim_and_unload("B"), ran["stream"]
    finally:
        r1(); r2()


_r_e7, _streamed_e7 = _rau_e7()
chk("E7: 容器步失败 ⇒ steps[1].detail 含 skipped，且未发 infer-unload",
    _r_e7["ok"] is False
    and str(_r_e7["steps"][1]["detail"]).startswith("skipped")
    and not _streamed_e7, str(_r_e7))


def _rau_e6():
    """infer-unload 连接异常 ⇒ 就地捕获，不抛出。"""
    r1 = _swap("_reclaim_containers", lambda st, al=None: (True, ""))

    def _boom(st, cmd):
        raise RuntimeError("connection reset")

    r2 = _swap("ssh_stream", _boom)
    try:
        return C.reclaim_and_unload("B")
    finally:
        r1(); r2()


_r_e6 = _rau_e6()
chk("E6: infer-unload 连接异常 ⇒ 就地捕获，detail 含异常类型名，不抛出",
    _r_e6["ok"] is False
    and "RuntimeError" in str(_r_e6["steps"][1]["detail"]), str(_r_e6["steps"][1]))

# ── T10-T13：容器预检（纯函数，见 DESIGN §4.4）───────────────────────────
_SPEC_T = {
    "image": "halogen:test",
    "volume": ["/data/models/hgn/peonist-ai/halogen-qwen3.8-flash-next:/hgn",
               "/data/models/hgn/peonist-ai/qwen38-flash-next-tokenizer:/tokenizer:ro"],
    "checkpoint": "/hgn/qwen38-flash-next-v2.hgn",
    "assets": [
        {"path": "/hgn/qwen38-flash-next-v2.hgn", "kind": "file", "min_bytes": 60 * 1024**3},
        {"path": "/hgn/qwen38-flash-next-ngram.hgn", "kind": "file", "min_bytes": 45 * 1024**3},
        {"path": "/tokenizer", "kind": "dir", "min_entries": 1},
    ],
}
_HP = getattr(C, "_host_path_for", None)
_CA = getattr(C, "classify_container_assets", None)
_V2 = "/hgn/qwen38-flash-next-v2.hgn"
_NG = "/hgn/qwen38-flash-next-ngram.hgn"
_TK = "/tokenizer"


def _cls(observed):
    return _CA(_SPEC_T, observed) if _CA else None


_OK_OBS = {"image": {"present": True}, "assets": {
    _V2: {"kind": "file", "size": 60 * 1024**3},
    _NG: {"kind": "file", "size": 45 * 1024**3},
    _TK: {"kind": "dir", "entries": 5},
}}
chk("T10 前置(防恒真): 资产齐全 ⇒ problems 为空",
    _cls(_OK_OBS) == [], str(_cls(_OK_OBS)))

_p10 = _cls({**_OK_OBS, "assets": {k: v for k, v in _OK_OBS["assets"].items() if k != _V2}})
chk("T10: 缺 checkpoint ⇒ asset-missing（且回收 0 次由调用顺序保证）",
    _p10 is not None and any(x.startswith(f"asset-missing:{_V2}") for x in _p10), str(_p10))

_p11a = _cls({**_OK_OBS, "assets": {k: v for k, v in _OK_OBS["assets"].items() if k != _NG}})
chk("T11a: 缺 ngram ⇒ asset-missing",
    _p11a is not None and any(x.startswith(f"asset-missing:{_NG}") for x in _p11a), str(_p11a))

_p11b = _cls({**_OK_OBS, "assets": {**_OK_OBS["assets"], _TK: {"kind": "dir", "entries": 0}}})
chk("T11b: tokenizer 空目录 ⇒ asset-empty-dir",
    _p11b is not None and any(x.startswith(f"asset-empty-dir:{_TK}") for x in _p11b),
    str(_p11b))

_p12 = _cls({**_OK_OBS, "image": {"present": False}})
chk("T12: 镜像缺失 ⇒ problems 含 image-missing",
    _p12 is not None and "image-missing" in _p12, str(_p12))

chk("T13a: /hgn/x 映射到 volume 宿主路径",
    bool(_HP) and _HP(_SPEC_T, "/hgn/x")
    == "/data/models/hgn/peonist-ai/halogen-qwen3.8-flash-next/x",
    str(_HP(_SPEC_T, "/hgn/x")) if _HP else "<缺 _host_path_for>")
chk("T13b: /tokenizer 映射（忽略 :ro 后缀）",
    bool(_HP) and _HP(_SPEC_T, "/tokenizer")
    == "/data/models/hgn/peonist-ai/qwen38-flash-next-tokenizer",
    str(_HP(_SPEC_T, "/tokenizer")) if _HP else "<缺>")
chk("T13c: 未挂载路径 ⇒ 空串（判不了 ≠ 猜一个）",
    bool(_HP) and _HP(_SPEC_T, "/nope") == "", str(_HP(_SPEC_T, "/nope")) if _HP else "<缺>")
chk("T13d: 根映射不丢前导斜杠（Step 7 修）",
    bool(_HP) and _HP({"volume": ["/data/models:/"]}, "/x") == "/data/models/x",
    str(_HP({"volume": ["/data/models:/"]}, "/x")) if _HP else "<缺>")

# ── D1-D4：实施期偏差的锚点 ──────────────────────────────────────────────
_p_d1a = _cls({**_OK_OBS, "assets": {**_OK_OBS["assets"], _V2: {"kind": "unreadable"}}})
chk("D1a: 资产不可读 ⇒ asset-unreadable（不得降级成 asset-missing）",
    _p_d1a is not None
    and any(x.startswith(f"asset-unreadable:{_V2}") for x in _p_d1a)
    and not any(x.startswith(f"asset-missing:{_V2}") for x in _p_d1a), str(_p_d1a))

_p_d1b = _cls({**_OK_OBS, "assets": {**_OK_OBS["assets"], _V2: {"kind": "dir", "entries": 3}}})
chk("D1b: 配方要 file 但观测 dir ⇒ asset-not-file",
    _p_d1b is not None and any(x.startswith(f"asset-not-file:{_V2}") for x in _p_d1b),
    str(_p_d1b))

_p_d1c = _cls({**_OK_OBS, "assets": {**_OK_OBS["assets"], _TK: {"kind": "file", "size": 10}}})
chk("D1c: 配方要 dir 但观测 file ⇒ asset-not-dir",
    _p_d1c is not None and any(x.startswith(f"asset-not-dir:{_TK}") for x in _p_d1c),
    str(_p_d1c))

_SQ = getattr(C, "sh_single_quote", None)
chk("D2: sh_single_quote 把含空格/单引号的路径包成单个 shell 词",
    bool(_SQ) and _SQ("/a b/it's") == "'/a b/it'\\''s'",
    repr(_SQ("/a b/it's")) if _SQ else "<缺 sh_single_quote>")

_PM = getattr(C, "_probe_map", None)


def _pm_probe(states):
    restore = _swap("probe_worker_state",
                    lambda st: states.get(st) or {"state": "unknown", "reason": "未探测"})
    try:
        return _PM([_AW, "10.10.99.99:50052"]) if _PM else None
    finally:
        restore()


_m4 = _pm_probe({"A": {"state": "busy", "reason": "halogen"}})
chk("D4: _probe_map 只探可映射到站的目标（未声明目标不入表，⇒ 选路判 unknown）",
    _m4 is not None and _m4 == {_AW: {"state": "busy", "reason": "halogen"}}, str(_m4))

# ── T14：aliases 站级缺口（门禁，动态导入 rpc_check）──────────────────────
def _aliases_probe(models):
    try:
        import rpc_check as R
        import rpc_stations                     # 8B-3：check_aliases 本体已搬，打桩打在定义模块
        orig = rpc_stations.load_inventory
        rpc_stations.load_inventory = lambda: ({}, models)
        try:
            return R.check_aliases({})
        finally:
            rpc_stations.load_inventory = orig
    except Exception as e:                        # 导入失败也必须红，不得崩整条测试
        return "ERROR", f"{type(e).__name__}: {e}", []


_v14, _n14, _d14 = _aliases_probe({
    "qwen3.8-flash-next": {"alias": "qwen3.8-flash-next",
                           "stations": ["B", "C"], "conf": ["C"]}})
chk("T14: inventory 缺 A 站 stations 声明 ⇒ FAIL 且文案含'模型库条目'",
    _v14 == "FAIL" and any("模型库条目" in x for x in _d14), f"{_v14} {_d14}")

print()
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED -> {fails}")
sys.exit(1 if fails else 0)
