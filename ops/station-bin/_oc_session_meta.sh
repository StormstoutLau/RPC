#!/bin/bash
# ADR-0007 缺口 8 (2026-09-18): 从站上 opencode 会话库取**本 run 的真实遥测**。
#   usage: _oc_session_meta.sh <workspace_dir> <since_epoch_ms> <out_file>
#
# 为什么在站上读、且为什么不是"猜数":
#   - 遥测是**执行侧观测**(会话库在站上), 与 .meta/.progress 同属"站上原件"; 主控侧只解析、不推断。
#   - headless run 的 stdout **不吐 usage**(见 cluster.py reqlog 注), 故不能从输出反推。
#   - 会话库由 opencode 自己按会话聚合 tokens/cost, 是**唯一可自证的口径**。
#
# 纪律:
#   - 只读打开(mode=ro) —— 绝不写站上库;
#   - **永不因遥测失败而影响任务结论**: 任何异常都以 SESSION_FOUND=0 落盘并 exit 0;
#   - **一定产出文件**(含失败情形) ⇒ 主控侧靠"文件存在 + FOUND 值"判定, 不靠"文件缺失"猜;
#   - 传递面: 本文件只经 **Copy-Item + scp + bash** 流转(PowerShell **从不读取其内容**) ⇒ 无
#     BOM/ANSI 解码面; 但**必须 LF** —— CRLF 会让远端 bash 直接失败(经典坑)。
set -u

WS="${1:-}"
SINCE="${2:-0}"
OUT="${3:-}"
if [ -z "$WS" ] || [ -z "$OUT" ]; then
  echo "usage: $0 <workspace_dir> <since_epoch_ms> <out_file>" >&2
  exit 2
fi

python3 - "$WS" "$SINCE" "$OUT" <<'PY'
import json
import os
import sqlite3
import sys

ws, since, out = sys.argv[1], int(sys.argv[2] or 0), sys.argv[3]
db = os.path.expanduser("~/.local/share/opencode/opencode.db")
lines = ["SESSION_SOURCE=opencode-db", "SESSION_FOUND=0"]


def emit():
    try:
        with open(out, "w") as f:
            f.write("\n".join(lines) + "\n")
    except OSError:
        pass


try:
    con = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
    rows = con.execute(
        "select id, slug, agent, model, cost, tokens_input, tokens_output, tokens_reasoning,"
        " tokens_cache_read, tokens_cache_write, time_created, time_updated"
        " from session where directory = ? and time_created >= ?"
        " order by time_created desc", (ws, since)).fetchall()
    if rows:
        r = rows[0]
        sid = r[0]
        tools = 0
        for (data,) in con.execute("select data from part where session_id = ?", (sid,)):
            try:
                if json.loads(data).get("type") == "tool":
                    tools += 1
            except (ValueError, TypeError):
                pass
        total = (int(r[5]) + int(r[6]) + int(r[7]) + int(r[8]) + int(r[9]))
        # 归属歧义判据(刻意选**与钟无关**的口径): 只有当**另一会话与本会话在时间上重叠**才算歧义 ——
        #   背靠背派发时上一轮的 time_updated 早于本轮的 time_created(两次时间都取自**同一台站钟**),
        #   故该判据不受主控/站钟偏斜影响; 反之 n>1 就报歧义会让"连跑两次"这种常态天天报警(噪声=判据被忽略)。
        ambiguous = 0
        if len(rows) > 1:
            for other in rows[1:]:
                if int(other[11]) >= int(r[10]):
                    ambiguous = 1
                    break
        lines = [
            "SESSION_SOURCE=opencode-db",
            "SESSION_FOUND=1",
            "SESSION_CANDIDATES=%d" % len(rows),
            "SESSION_AMBIGUOUS=%d" % ambiguous,
            "SESSION_ID=%s" % sid,
            "SESSION_SLUG=%s" % (r[1] or ""),
            "SESSION_AGENT=%s" % (r[2] or ""),
            "SESSION_MODEL=%s" % (r[3] or ""),
            "SESSION_COST=%s" % (r[4] if r[4] is not None else 0),
            "TOKENS_INPUT=%d" % int(r[5]),
            "TOKENS_OUTPUT=%d" % int(r[6]),
            "TOKENS_REASONING=%d" % int(r[7]),
            "TOKENS_CACHE_READ=%d" % int(r[8]),
            "TOKENS_CACHE_WRITE=%d" % int(r[9]),
            "TOKENS_TOTAL=%d" % total,
            "TOOL_USES=%d" % tools,
            "TS_CREATED_MS=%d" % int(r[10]),
            "TS_UPDATED_MS=%d" % int(r[11]),
        ]
except Exception as e:                      # noqa: BLE001  (遥测永不影响任务结论)
    lines.append("SESSION_ERR=%s" % type(e).__name__)

emit()
PY

# 兜底: python3 缺失/被杀 ⇒ 仍要留下"取不到"的显式记录(而不是没有文件)
if [ ! -f "$OUT" ]; then
  printf 'SESSION_SOURCE=opencode-db\nSESSION_FOUND=0\nSESSION_ERR=helper-fallback\n' > "$OUT"
fi
exit 0
