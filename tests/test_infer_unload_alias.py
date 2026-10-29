#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`infer-unload` 的 **alias 级卸载**契约（O-179 P1，2026-10-28）。

为什么用静态断言
----------------
站上脚本在远端跑、且要 sudo；用真站去验"只停了一个"成本高、还会动生产。
而**失效方式很具体**：有人把 alias 分支删掉、或把它改成仍走通配 `llama-server@*`
（= 换个名字继续全站清空），或误把 `pkill` 挪进 alias 分支。这三类都能被文本判死。

判据
----
1. 有位置参数解析 `ALIAS="${1:-}"`；
2. **alias 分支**（从 `if [ -n "$ALIAS" ]` 到该分支的 `exit 0`）里：
   · 停的是 `llama-server@${ALIAS}` 与 `rpc-server@${ALIAS}`（**不是** `@*`）；
   · 按 conf 的 **MODEL_PATH** 认领 unsloth / 手起 llama-server / ds4（2026-10-29 二修：
     旧版"一律不 pkill"导致 `unload --alias <unsloth模型>` 什么也停不掉）；
   · 但**不得**含全量 pkill（那等于换个名字做全站清空）；判不出归属 ⇒ 只 WARN 不猜；
3. **无参分支**逐字保留 `'llama-server@*'` 与 `'rpc-server@*'`（默认行为不许变）。

用法: py tests\\test_infer_unload_alias.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SH = ROOT / "ops" / "station-bin" / "infer-unload"
fails = []


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


def main() -> int:
    if not SH.is_file():
        print(f"FAIL: 找不到 {SH}")
        return 1
    src = SH.read_text(encoding="utf-8", errors="replace")

    chk("位置参数解析存在（ALIAS=\"${1:-}\"）", 'ALIAS="${1:-}"' in src)

    head = src.find('if [ -n "$ALIAS" ]')
    chk("有 alias 分支（if [ -n \"$ALIAS\" ]）", head >= 0)
    if head >= 0:
        tail = src.find("exit 0", head)
        block = src[head:tail if tail > 0 else len(src)]
        chk("alias 分支逐字停 llama-server@${ALIAS}",
            "llama-server@${ALIAS}" in block, block[:120].replace("\n", " ⏎ "))
        chk("alias 分支逐字停 rpc-server@${ALIAS}",
            "rpc-server@${ALIAS}" in block)
        chk("alias 分支按 MODEL_PATH 认领非 systemd 实例（unsloth/手起 llama/ds4）",
            "MODEL_PATH=" in block and "/proc/${_p}/cmdline" in block
            and "pgrep -f '[u]nsloth studio run'" in block,
            "没有归属判据 ⇒ `unload --alias <unsloth模型>` 什么也停不掉（实测）")
        chk("alias 分支连带杀 studio 子进程（pkill -P）",
            'pkill -9 -P "$_p"' in block)
        chk("alias 分支**不含全量** pkill（不许换个名字做全站清空）",
            'pkill -9 -f "[u]nsloth studio run"' not in block
            and "pkill -9 -x llama-server" not in block
            and "pkill -9 -f '[d]s4" not in block,
            "全量 pkill 会杀掉同站其它模型（D-7）")
        chk("alias 分支：判不出归属时只 WARN、不退回全量",
            "WARN: 未取到" in block)
        chk("alias 分支的探测管道带 `|| true`（set -e + pipefail）",
            "pgrep -f '[u]nsloth studio run' || true" in block,
            "空命中会让赋值失败 ⇒ 脚本在『本来就没有实例』时退出非 0")
        chk("alias 分支不含通配 @* 的 stop（不许退化成全停）",
            "'llama-server@*'" not in block and "'rpc-server@*'" not in block)

    body = src[src.find("exit 0", head) + 6:] if head >= 0 else src
    chk("无参分支仍按通配停 llama-server@*",
        "'llama-server@*'" in body)
    chk("无参分支仍按通配停 rpc-server@*",
        "'rpc-server@*'" in body)
    chk("无参分支仍执行 pkill（unsloth/ds4/vllm 清理未被误删）",
        "pkill" in body)

    print("\nRESULT: " + ("ALL PASS" if not fails else f"FAIL ({len(fails)} 项)") +
          " · 失败: " + (", ".join(fails) if fails else "无"))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
