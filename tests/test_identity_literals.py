"""#9 活跃运行时身份字面量 —— 先验红（P2 小批次）。

扫描活跃运行时清单，剥注释后禁止：
  · scott-lau@        （SSH 身份写死）
  · /home/scott-lau   （家目录写死）
  · scott-lau-NEX.local / scott-lau-GTR-Pro.local / seaviv.local（已知 mDNS 主机名写死）

白名单（不扫）：agent-cli-smoke.sh（Windows Git Bash，id -un 语义不同）、
ops/*.service（User=/Group= 是 systemd 部署身份）、docs/、archive/、冻结探针。

允许裸用户名（测试只禁三模式）：STATIONS 的 user、cluster-watchdog 的
SERVICE_USER 缺省、agent-cli.ps1 的 REMOTE_USER。

用法: py tests\\test_identity_literals.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
fails = []

ACTIVE = [
    "ops/cluster.py",
    "ops/cluster_const.py",
    "ops/cluster_web.py",
    "ops/rpc_check.py",
    "ops/station-bin/infer-load",
    "ops/station-bin/infer-unload",
    "ops/station-bin/infer-list",
    "ops/station-bin/cluster-watchdog",
    "ops/station-bin/agent-cli.ps1",
]
PATTERNS = (
    "scott-lau@",
    "/home/scott-lau",
    "scott-lau-NEX.local",
    "scott-lau-GTR-Pro.local",
    "seaviv.local",
)
WHITELIST = ("ops/station-bin/agent-cli-smoke.sh",)
# O-124 反查真值源：agent-cli.ps1 的 .local 主机名是 Get-TargetHost/Get-StationLetterFromHost
# 的唯一拓扑表；改成 IP 会破坏批行 station= 反查（黄金夹具 o124b 三条）。故该文件只禁
# scott-lau@ 与 /home/scott-lau，不禁已知 mDNS 名。
HOST_MAP_FILES = {"ops/station-bin/agent-cli.ps1"}


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


def strip_comment(line):
    """剥行内注释；引号感知（单/双引号内的 # 不剥）。"""
    quote = None
    i = 0
    while i < len(line):
        c = line[i]
        if quote:
            if c == "\\" and quote == '"':
                i += 2
                continue
            if c == quote:
                quote = None
        else:
            if c in "'\"":
                quote = c
            elif c == "#":
                return line[:i]
        i += 1
    return line


def hits(text, patterns=PATTERNS):
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        body = strip_comment(line)
        for pat in patterns:
            if pat in body:
                out.append((n, pat, body.strip()[:120]))
    return out


# 负向夹具：探测器不能空转（用已知主机名，命中 scott-lau@ + mDNS 两模式）
chk("负向夹具：scott-lau@scott-lau-NEX.local 可被判出",
    len(hits("AWORK=\"scott-lau@scott-lau-NEX.local\"\n")) >= 2)
chk("负向夹具：注释行不算命中",
    hits("# 历史: scott-lau@x.local\n") == [])

for rel in ACTIVE:
    p = ROOT / rel
    if not p.exists():
        chk(f"{rel} 存在", False, str(p))
        continue
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as e:
        chk(f"{rel} 可读", False, str(e))
        continue
    found = hits(text, ("scott-lau@", "/home/scott-lau")
                 if rel in HOST_MAP_FILES else PATTERNS)
    detail = "; ".join(f"L{n} {pat} :: {body}" for n, pat, body in found[:6])
    chk(f"{rel} 无身份字面量", not found,
        detail if found else "")

# 白名单文件确实不在扫描清单
for rel in WHITELIST:
    chk(f"白名单不在活跃清单: {rel}", rel not in ACTIVE)

# 主控 Python 的 SERVICE_USER 必须是派生，不是字面
cc = (ROOT / "ops" / "cluster_const.py").read_text(encoding="utf-8")
chk("cluster_const.SERVICE_USER 从 STATIONS 派生",
    "SERVICE_USER = STATIONS" in cc)

print("\nRESULT: " + ("PASS" if not fails else f"FAIL ({len(fails)} 项)") +
      " · 失败: " + (", ".join(fails) if fails else "无"))
sys.exit(0 if not fails else 1)
