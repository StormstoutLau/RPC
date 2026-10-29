"""`infer-load` 的**就绪循环早退**契约（2026-10-29，O-179 §5-5）。

为什么用静态断言
----------------
真站复现一次「加载必然失败」的成本很高（要么等满超时、要么动生产），
而失效方式非常具体：**循环里只看 HTTP、不看进程/单元死活**。实测两次：

  · systemd 路径：conf 的 `LLAMA_SERVER_BIN` 指向不存在的引擎 ⇒ 单元
    `exit 127` 立刻 failed，脚本仍 curl 300 次 × 3s，最后只报"健康检查
    超时" —— 真因在 journal 里，还占着调用方 15min。
  · unsloth 路径：`MODEL_PATH` 不存在 ⇒ studio 5s 内退出，但**端口解析
    循环**仍走满 40×3s（白等 2min）。
  · 更严重：unsloth 健康循环用**裸 curl + `$?`** ⇒ `set -e` 下首次连接
    失败（curl rc=7）就终止整个脚本 —— 无任何 ERROR，退出码 7 还会被误读
    成"RPC 节点失败"。这类只能用文本判据拦住。

判据
----
1. `[6a]` unsloth 保存 `UN_PID=$!`；
2. 端口解析循环（40×3s）与健康循环（120×3s）都判"进程已退且没有 studio
   在跑" ⇒ 打日志尾部 + `exit 1`；
3. 判死**在** 成功 `exit 0` 之后（正常就绪不受影响）；
4. `[6a]` curl 必须写在 `if`/`||` 里，**不得**出现 `$? -eq 0`；
5. `[7]` 健康循环用 `systemctl is-failed` 判单元已 failed，failed 时打
   `ExecMainStatus` + journal 尾部并 `exit 1`，同样在 `exit 0` 之后；
6. 两条路径都**保留**超时兜底（早退只补快路，不删慢路）。

用法: py tests\\test_infer_load_ready.py
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

    # ---- [6a] unsloth ----
    un_block = slice_between(src, "UN_PID=$!", "# ---- [6b]")
    # 只看代码行：注释里会引用「裸 curl + $?」这个反模式作为说明，不该算违规。
    un_code = "\n".join(l for l in un_block.splitlines() if not l.lstrip().startswith("#"))
    port_block = slice_between(src, "for i in $(seq 1 40); do", "\n  done")
    health_block = slice_between(src, "for i in $(seq 1 120); do", "\n  done")

    need("unsloth 启动后保存 pid（UN_PID=$!）",
         "UN_PID=$!" in src,
         "不存 pid 就无法回答『它是不是已经死了』")
    need("[6a] 有统一的判死判据（kill -0 + pgrep studio）",
         'kill -0 "$UN_PID"' in un_block and "pgrep -f '[u]nsloth studio run'" in un_block,
         "只 kill -0 父 pid ⇒ studio 若 fork/重执行会误报死亡")
    need("[6a] 端口解析循环也判死（不白等 40×3s）",
         "_un_dead" in port_block,
         "实测：studio 5s 内退出，旧实现仍走满 2min 才进健康检查")
    need("[6a] 端口解析循环判死后打日志尾部",
         "tail -n" in port_block and "UN_LOG" in port_block,
         "只说『退出了』而不给真因 ⇒ 仍要人工翻日志")
    need("[6a] 健康循环判死 + 打日志尾部",
         "_un_dead" in health_block and "tail -n" in health_block,
         "只看 /v1/models ⇒ studio 崩了也要空等 6min")
    need("[6a] 判死分支 exit 1",
         "exit 1" in health_block,
         "早退必须失败，不能静默继续")
    need("[6a] curl 不得靠 `$? -eq 0` 判断（set -e 下 rc=7 会直接终止脚本）",
         "$? -eq 0" not in un_code,
         "裸 curl + $? ⇒ 首次连接失败(7)即以 7 退出，且没有任何 ERROR（实测）")
    need("[6a] curl 写在 if 条件里（或 `|| _ok=0` 兜底）",
         "if curl -sf" in health_block or "|| _ok=0" in health_block,
         "同样的 set -e 陷阱，换一种写法也要能活下来")
    i_ok = health_block.find("exit 0")
    i_dead = health_block.find("_un_dead")
    need("[6a] 先判成功、再判死亡（正常就绪不被早退抢走）",
         i_ok >= 0 and i_dead >= 0 and i_ok < i_dead,
         "顺序反了（或缺少其一）⇒ 刚起的进程在首轮检查前就被判死")
    need("[6a] 超时兜底日志仍保留",
         "unsloth 健康检查超时" in src,
         "早退只是快路，慢路（真慢启动）不能删")

    # ---- [7] systemd ----
    sd_block = slice_between(src, "for i in $(seq 1 300); do", "\ndone")
    need("[7] 健康循环用 systemctl is-failed 判单元已 failed",
         "systemctl is-failed" in sd_block and "llama-server@${ALIAS}" in sd_block,
         "只 curl /health ⇒ 单元 exit 127 也要空等 15min（G1 实测）")
    need("[7] failed 时打印退出码（ExecMainStatus）",
         "ExecMainStatus" in sd_block,
         "不打退出码 ⇒ 分不清 127(路径悬空) 与 1(参数错)")
    need("[7] failed 时附 journal 尾部",
         "journalctl" in sd_block,
         "真因通常只在单元日志里")
    need("[7] failed 分支 exit 1",
         "exit 1" in sd_block,
         "早退必须失败")
    i_ok7 = sd_block.find("exit 0")
    i_fail7 = sd_block.find("systemctl is-failed")
    need("[7] 先判成功、再判 failed（正常就绪不被早退抢走）",
         i_ok7 >= 0 and i_fail7 >= 0 and i_ok7 < i_fail7,
         "顺序反了（或缺少其一）⇒ 刚启动的单元在首轮 curl 前被判死")
    need("[7] 仍然 15min 超时兜底",
         "健康检查 15min 超时" in src,
         "真慢启动路径不能因早退而丢兜底")

    print("\nRESULT: " + ("ALL PASS" if not fails else f"{len(fails)} FAILED -> {fails}"))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
