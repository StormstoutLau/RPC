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
import cluster as C                                    # noqa: E402

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

# ── RPC 加载前回收 halogen 容器：防「8080 仍由容器持有 ⇒ 健康检查假绿」────────
# 现场（2026-10-22）：`load glm-5.3-flash` 时 A/B/C 的 qwen halogen 容器未回收，
# 8080 仍由容器服务 ⇒ 远端 infer-load/健康检查命中 qwen，GLM 实际未起却报 READY。
def _rpc_reclaim_probe(worker=None, conf_target="",
                       alive="10.10.10.1:50052 10.10.11.3:50052",
                       decl="10.10.10.1:50052 10.10.11.3:50052"):
    calls, built, runs = [], [], []
    saved = (C._reclaim_containers, C.ssh_stream, C.ssh_run,
             C._build_infer_load_cmd, C._conf_rpc_target)
    try:
        C._reclaim_containers = lambda st: calls.append(st) or True
        C.ssh_stream = lambda *a, **k: 0

        def _ssh_run(st, cmd, **k):
            runs.append(cmd)
            if cmd.startswith("rpc-nodes --all"):
                return True, decl
            if cmd.startswith("rpc-nodes "):
                return True, alive
            return True, alive

        C.ssh_run = _ssh_run
        C._build_infer_load_cmd = lambda *a, **k: built.append((a, k)) or "true"
        C._conf_rpc_target = lambda st, al: conf_target
        rc = C._load_rpc("glm-5.3-flash", "B", None, worker)
    finally:
        (C._reclaim_containers, C.ssh_stream, C.ssh_run,
         C._build_infer_load_cmd, C._conf_rpc_target) = saved
    return rc, calls, built, runs


_rc_rpc, _reclaim_calls, _built, _runs = _rpc_reclaim_probe()
chk("RPC load: 先回收 A/B/C 三站 halogen 容器（防 8080 假绿）",
    _rc_rpc == 0 and _reclaim_calls == ["A", "B", "C"],
    f"rc={_rc_rpc} calls={_reclaim_calls}")
chk("RPC load: conf 无单 worker 目标时不传 --rpc-target（保留 auto/多节点语义）",
    _rc_rpc == 0 and _built and _built[-1][0][3] is None
    and "rpc-nodes --start 'glm-5.3-flash'" in _runs,
    f"built={_built} runs={_runs}")

# 2026-10-22 单 worker 指派：head 固定 B，worker 由用户选 A|C。
_rc_w, _calls_w, _built_w, _runs_w = _rpc_reclaim_probe(worker="C")
chk("RPC load --worker C: 映射 10.10.11.3:50052 并透传 --rpc-target",
    _rc_w == 0 and _calls_w == ["A", "B", "C"] and _built_w
    and _built_w[-1][0][3] == "10.10.11.3:50052"
    and "rpc-nodes --start 'glm-5.3-flash' '10.10.11.3:50052'" in _runs_w,
    f"rc={_rc_w} built={_built_w} runs={_runs_w}")
_rc_wa, _calls_wa, _built_wa, _runs_wa = _rpc_reclaim_probe(worker="A")
chk("RPC load --worker A: 映射 10.10.10.1:50052",
    _rc_wa == 0 and _built_wa and _built_wa[-1][0][3] == "10.10.10.1:50052",
    f"rc={_rc_wa} built={_built_wa}")

# 无 --worker 时从 conf 读出的单 worker 目标也应约束预启动与 infer-load。
_rc_c, _calls_c, _built_c, _runs_c = _rpc_reclaim_probe(conf_target="10.10.10.1:50052")
chk("RPC load 默认: conf 单 worker A ⇒ 预启动与 --rpc-target 都只带 A",
    _rc_c == 0 and _built_c and _built_c[-1][0][3] == "10.10.10.1:50052"
    and "rpc-nodes --start 'glm-5.3-flash' '10.10.10.1:50052'" in _runs_c,
    f"rc={_rc_c} built={_built_c} runs={_runs_c}")

# 2026-10-23: 显式 worker 的失败面 —— 死节点 / 未声明节点必须在加载前中止。
_rc_dead, _, _built_dead, _ = _rpc_reclaim_probe(
    worker="C", alive="10.10.10.1:50052")
chk("RPC load --worker C: 目标不在存活清单 ⇒ 加载前中止",
    _rc_dead == 1 and not _built_dead, f"rc={_rc_dead} built={_built_dead}")
_rc_undecl, _, _built_undecl, _ = _rpc_reclaim_probe(
    worker="C", decl="10.10.10.1:50052")
chk("RPC load --worker C: 目标不在 nodes.env 声明 ⇒ 加载前中止",
    _rc_undecl == 1 and not _built_undecl, f"rc={_rc_undecl} built={_built_undecl}")

# 非法/越界指派必须响亮拒绝（不静默退化）。
chk("load --worker B: 非法 worker 拒绝（head 固定 B，B 不能当 worker）",
    C.cmd_load("glm-5.3-flash", None, None, "B") == 1, "应 rc=1")
chk("load --worker 非 RPC 模型: 拒绝",
    C.cmd_load("gpt-oss-120b", None, None, "A") == 1, "应 rc=1")
chk("load --worker + 强制单机后端: 拒绝（矛盾组合）",
    C.cmd_load("glm-5.3-flash", "unsloth", None, "A") == 1, "应 rc=1")


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

print()
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED -> {fails}")
sys.exit(1 if fails else 0)
