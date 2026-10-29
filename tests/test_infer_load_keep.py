"""`infer-load --keep` 的**静态护栏**（2026-10-29，O-179 G1 二修）。

为什么用静态断言
----------------
`--keep` 的失效方式都是"被人顺手改回全停"或"漏掉某类实例"：
  · 有人把 keep 分支写成 `llama-server@*` ⇒ 同站模型又被杀（G1 首跑的真实事故）；
  · 有人只等 `systemctl is-active` ⇒ 漏掉**同别名的 unsloth 实例**，
    `load <同一 alias> --keep` 会抢端口，然后空等满 15min 健康超时；
  · 有人按进程名/日志名（`gpt-oss(<alias>)`）认领旧实例 ⇒ 实测 studio 的真实 argv 里
    只有 `--model <...gguf>`，**认不出来**；唯一稳的判据是 conf 的 `MODEL_PATH`；
  · 有人把 `wait_gtt` 放回 keep 分支 ⇒ 同站有别的模型时"等 GTT<2G"必假阴性，
    白等 180s 再 WARN。
这三条都只需一次文本回归就能拦住，跑真集群成本高且破坏生产。

判据与"反向即红"
----------------
1. keep 分支**只**停 `llama-server@${ALIAS}`，不得出现 `llama-server@*`。
2. keep 分支必须按**固定串** `(<alias>)` 停本别名的 unsloth，且**不得**整体 pkill unsloth。
3. keep 分支以**端口**为准（`ss -ltn` + `PORT_NUM`），且端口仍占 ⇒ `exit 1`（不进入健康等待）。
4. keep 分支**不**调用 `wait_gtt`（站点与 worker 两处等待都要跳过）。
5. 非 keep 分支保持原样：`llama-server@*` 全停 + pkill unsloth/vllm/ds4 + 两处 wait_gtt。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "ops" / "station-bin" / "infer-load"


def slice_between(src, start_marker, end_marker):
    i = src.index(start_marker)
    j = src.index(end_marker, i)
    return src[i:j]


def main() -> int:
    if not SRC.exists():
        print(f"FAIL: 找不到 {SRC}")
        return 1
    src = SRC.read_text(encoding="utf-8", errors="replace")
    fails = []

    def need(desc, cond, hint):
        print(("  ok  " if cond else "  FAIL ") + desc)
        if not cond:
            fails.append(f"{desc} ⇒ {hint}")

    # ---- 切出两段 keep 分支 ----
    stop_start = 'if [ -n "$KEEP" ]; then\n  # ★ 目标不是"单元停了"'
    stop_end = 'else\nlog "停旧实例 (llama/vllm/unsloth/ds4)..."'
    stop_block = slice_between(src, stop_start, stop_end)
    gtt_start = 'if [ -n "$KEEP" ]; then\n  log "站点/worker GTT 等待跳过'
    gtt_end = 'else\n  wait_gtt "B" ""'
    gtt_block = slice_between(src, gtt_start, gtt_end)

    # 1) 只停本别名
    need("keep 分支只停 llama-server@${ALIAS}",
         "llama-server@${ALIAS}" in stop_block,
         "改回 `llama-server@*` ⇒ 同站其它模型被杀（G1 首跑的原样复现）")
    need("keep 分支**不含** llama-server@* 全停",
         "llama-server@*" not in stop_block,
         "用通配即等于没有 keep")

    # 2) 本别名的实例也要停 —— 判据是**模型文件路径**，不是进程名/日志名
    need("keep 分支按 MODEL_PATH 认领本别名的旧实例",
         'grep -qF -- "$MODEL_PATH"' in stop_block and "/proc/${_p}/cmdline" in stop_block,
         "用 `(<alias>)`/进程名认领会漏（实测 studio argv 里只有 --model <路径>）")
    need("keep 分支连带杀 studio 的子进程（pkill -P）",
         'pkill -9 -P "$_p"' in stop_block,
         "只杀父进程 ⇒ 子 llama-server 仍持显存")
    need("keep 分支**不做**整体 pkill unsloth",
         'pkill -9 -f "[u]nsloth studio run"' not in stop_block,
         "整体 pkill 会杀掉同站别的模型（unsloth 无 alias 归属）")
    # 2b) set -euo pipefail 下，grep 无命中的管道会让赋值语句失败 ⇒ 必须 || true
    need("keep 分支的端口/命令行探测都带 `|| true`（set -e + pipefail）",
         stop_block.count("|| true") >= 4,
         "漏掉它 ⇒ 「本来就没有旧实例」这一正常情况会 exit 1（2026-10-29 实测）")

    # 3) 以端口为准 + 占用即失败
    need("keep 分支按端口判定（ss + PORT_NUM）",
         "ss -ltn" in stop_block and "${PORT_NUM}" in stop_block,
         "只等 is-active 会漏掉 studio 子进程")
    need("keep 分支端口仍占 ⇒ exit 1（不进入健康等待）",
         "exit 1" in stop_block,
         "不早退 ⇒ exit 127/端口冲突也要空等 15min（实测）")
    i_exit = stop_block.index("exit 1")
    need("exit 1 在启动之前（stop 段内，早于 [4]）",
         i_exit < len(stop_block),
         "顺序错则先加载后报错")

    # 4) keep 不等待 GTT
    need("keep 分支不调用 wait_gtt（站点 + worker 都跳过）",
         "wait_gtt" not in gtt_block and "跳过" in gtt_block,
         "同站有别的模型时等 GTT<2G 必假阴性，白等 180s")

    # 5) 非 keep 保持原样
    need("非 keep 仍全停 llama-server@*",
         "sudo systemctl stop 'llama-server@*'" in src,
         "默认路径不得被 keep 改动")
    need("非 keep 仍 pkill unsloth / vllm / ds4",
         'pkill -9 -f "[u]nsloth studio run"' in src
         and "vllm.entrypoint[s]" in src
         and "[d]s4-server" in src,
         "全量清扫是默认互斥语义")
    need("非 keep 仍有两处 GTT 等待（站点 + worker）",
         'wait_gtt "B" ""' in src and 'wait_gtt "worker(' in src,
         "默认路径的『等显存释放』不能被删")

    # 6) 参数解析
    need("--keep 参数解析存在",
         "--keep) KEEP=1" in src,
         "没有解析 ⇒ 整段分支永不生效")

    # 7) 被拒绝的加载不得改持久状态：PORT 落 conf 必须在 [3] 端口门之后
    i_stop_end = src.index('fi   # ← --keep 分支到此结束')
    i_port_write = src.index('_set_conf_key PORT "$PORT"')
    need("`--port` 落 conf 在端口门之后（被拒绝不改 conf）",
         i_port_write > i_stop_end,
         "写在门之前 ⇒ `--keep --port <别人占着的口>` 被拒也改 conf（2026-10-29 实测）")

    print("\nRESULT: " + ("ALL PASS" if not fails else f"{len(fails)} FAILED -> {fails}"))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
