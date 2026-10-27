"""#6 遗留 systemd 单元的键段位 —— 先验红（P2 小批次）。

断言：
  · ops/llama-server.service / ops/rpc-server.service 的 StartLimitIntervalSec 在 [Unit]；
  · [Service] 不含该键（写在 [Service] 会被 systemd 当 Unknown key 忽略）；
  · Restart / RestartSec 仍在 [Service]；
  · 负向夹具证明"键在 [Service]"能被判出；
  · 现役模板 rpc-server@.service 保持正确段位。

用法: py tests\\test_systemd_units.py
"""
import configparser
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
fails = []


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


def parse(path):
    cp = configparser.RawConfigParser(strict=False)      # systemd 允许重复键；无 % 插值
    cp.optionxform = str                                 # 不折叠键大小写
    cp.read(path, encoding="utf-8")
    return cp


for name in ("llama-server.service", "rpc-server.service"):
    p = ROOT / "ops" / name
    if not p.exists():
        chk(f"{name} 存在", False, str(p))
        continue
    cp = parse(p)
    chk(f"{name} [Unit] 有 StartLimitIntervalSec",
        cp.has_option("Unit", "StartLimitIntervalSec"))
    chk(f"{name} [Service] 无 StartLimitIntervalSec",
        not cp.has_option("Service", "StartLimitIntervalSec"))
    chk(f"{name} Restart 仍在 [Service]", cp.has_option("Service", "Restart"))
    chk(f"{name} RestartSec 仍在 [Service]", cp.has_option("Service", "RestartSec"))

# 负向夹具：键写在 [Service] 时必须能被判出（防测试空转）
bad = "[Unit]\nDescription=x\n[Service]\nStartLimitIntervalSec=0\n"
cp_bad = configparser.RawConfigParser(strict=False)
cp_bad.optionxform = str
cp_bad.read_string(bad)
chk("负向夹具：键在 [Service] 可被判出",
    (not cp_bad.has_option("Unit", "StartLimitIntervalSec"))
    and cp_bad.has_option("Service", "StartLimitIntervalSec"))

# 现役模板不应被本批改坏
tpl = ROOT / "ops" / "rpc-server@.service"
if tpl.exists():
    cp_t = parse(tpl)
    chk("rpc-server@.service [Unit] 有 StartLimitIntervalSec",
        cp_t.has_option("Unit", "StartLimitIntervalSec"))
    chk("rpc-server@.service [Service] 无 StartLimitIntervalSec",
        not cp_t.has_option("Service", "StartLimitIntervalSec"))

print("\nRESULT: " + ("PASS" if not fails else f"FAIL ({len(fails)} 项)") +
      " · 失败: " + (", ".join(fails) if fails else "无"))
sys.exit(0 if not fails else 1)
