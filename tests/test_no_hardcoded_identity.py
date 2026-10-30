"""O-177 #9：三个站脚本不得再写死身份 / 地址 / 家目录。

为什么是静态判据
----------------
这三件都在别处运行（smoke 在主控、_switch 被 ps1 推 B 站、infer-list 在三站），
用真站跑一遍既慢又只能覆盖当前用户名。而失效方式很具体：有人又把
`scott-lau@…` 或 `/home/scott-lau` 写回去 —— 换用户 / 换机器就静默失效。

判据
----
1. 代码行（去注释）不得含裸 `scott-lau@`（默认值只允许写成 `${RPC_USER}@<host>`）；
2. `_switch_qwen_flavor.sh` 代码行不得含 `/home/scott-lau`；
3. 三者都带**可覆盖的默认值**（变量 + `:-` 兜底），默认行为不变；
4. `infer-list` 的站名映射用 `${ST_HOST_x:-<host>}`，不再写字面 case 分支。

用法: py tests\\test_no_hardcoded_identity.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "ops" / "station-bin"
fails = []


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


def code_lines(path):
    out = []
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        out.append((i, line))
    return out


def bad_lines(path, needle, allow=None):
    hits = []
    for n, line in code_lines(path):
        if needle not in line:
            continue
        if allow and allow in line:
            continue
        hits.append((n, line.strip()[:100]))
    return hits


def main() -> int:
    smoke = BIN / "agent-cli-smoke.sh"
    switch = BIN / "_switch_qwen_flavor.sh"
    lst = BIN / "infer-list"
    for p in (smoke, switch, lst):
        if not p.is_file():
            print(f"FAIL: 找不到 {p}")
            return 1

    for p in (smoke, switch, lst):
        h = bad_lines(p, "scott-lau@")
        chk(f"{p.name}: 无裸 scott-lau@ 身份", not h, h)

    h = bad_lines(switch, "/home/scott-lau")
    chk("_switch_qwen_flavor.sh: 无写死家目录 /home/scott-lau", not h, h)

    smoke_txt = smoke.read_text(encoding="utf-8", errors="replace")
    for v in ("HOST_A", "HOST_B", "HOST_C"):
        chk(f"agent-cli-smoke.sh: {v} 有可覆盖默认值",
            f'{v}="${{{v}:-' in smoke_txt)

    lst_txt = lst.read_text(encoding="utf-8", errors="replace")
    for v in ("ST_A_IP", "ST_B_IP", "ST_C_IP"):
        chk(f"infer-list: {v} 有可覆盖默认值", f'{v}="${{{v}:-' in lst_txt)
    chk("infer-list: 站名映射走 ${ST_HOST_x:-} 而不是字面分支",
        "${ST_HOST_A:-" in lst_txt and "${ST_HOST_B:-" in lst_txt and "${ST_HOST_C:-" in lst_txt)

    switch_txt = switch.read_text(encoding="utf-8", errors="replace")
    chk("_switch_qwen_flavor.sh: 家目录由服务用户推导（getent + nodes.env）",
        "getent passwd" in switch_txt and "SU_HOME" in switch_txt
        and "s/^RPC_USER=//p" in switch_txt)

    print("\nRESULT: " + ("ALL PASS" if not fails else f"FAIL ({len(fails)} 项) · " + ", ".join(fails)))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
