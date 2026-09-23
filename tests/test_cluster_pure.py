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
import sys
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


print()
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED -> {fails}")
sys.exit(1 if fails else 0)
