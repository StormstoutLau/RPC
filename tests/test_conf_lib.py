"""conf-lib.sh + conf-get（P1 #4）—— 站上写/读入口的三方一致性。

覆盖 IMPLEMENTATION §9.1 #4 行：
  · 含空格 / `&` / `|` / `"` / `\\` / `$` / `` ` `` / `*` 的值：source / conf_get_kv / conf-get 三方逐字节一致；
  · 含换行 ⇒ rc=2 且原文件逐字节不变；
  · 注释与其它键保留、无临时文件残留；
  · 缺失键 rc=1；
  · conf_parse.py 能读回同一值。

需要能读到仓库路径的 bash（Windows 用 Git Bash）：
  py tests\\test_conf_lib.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

fails = []


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


def _posix(p) -> str:
    s = str(Path(p).resolve())
    if len(s) > 2 and s[1] == ":":
        return "/" + s[0].lower() + s[2:].replace("\\", "/")
    return s.replace("\\", "/")


def _bash():
    if os.name != "nt":
        return shutil.which("bash")
    for p in (r"C:\Program Files\Git\usr\bin\bash.exe",
              r"C:\Program Files\Git\bin\bash.exe"):
        if Path(p).is_file():
            return p
    return shutil.which("bash")


BASH = _bash()
chk("找到可用的 bash", bool(BASH), BASH)
if not BASH:
    print("\nRESULT: FAIL (未找到 bash，无法验证 station-bin)")
    sys.exit(1)

LIB = ROOT / "ops" / "station-bin" / "conf-lib.sh"
CG = ROOT / "ops" / "station-bin" / "conf-get"
chk("conf-lib.sh 存在", LIB.is_file(), LIB)
chk("conf-get 存在", CG.is_file(), CG)
if not (LIB.is_file() and CG.is_file()):
    print("\nRESULT: FAIL (conf 共享库尚未实现)")
    sys.exit(1)

VAL = 'a b&|"c\\d$e`f*g'
tmp = tempfile.mkdtemp(prefix="p1conf-")
conf = Path(tmp) / "sample.env"

script = r'''
set -uo pipefail
. "$LIB"
printf '# comment\nCTX=32768\nMODEL_PATH=/old/path.gguf\nTHREADS=16\n' > "$F"
conf_set_kv "$F" MODEL_PATH "$VAL"; RC=$?
printf 'SET_RC=%s\n' "$RC"
. "$F"
printf 'SRC=%s\n' "$MODEL_PATH"
printf 'GET=%s\n' "$(conf_get_kv "$F" MODEL_PATH)"
printf 'CLI=%s\n' "$(bash "$CG" "$F" MODEL_PATH)"
BEFORE=$(md5sum "$F" | cut -d' ' -f1)
conf_set_kv "$F" MODEL_PATH $'bad\nvalue'; NLRC=$?
AFTER=$(md5sum "$F" | cut -d' ' -f1)
printf 'NL_RC=%s\n' "$NLRC"
[ "$BEFORE" = "$AFTER" ] && printf 'UNCHANGED=yes\n' || printf 'UNCHANGED=no\n'
printf 'CTX=%s\n' "$(conf_get_kv "$F" CTX)"
conf_get_kv "$F" NOPE >/dev/null 2>&1; printf 'MISSING_RC=%s\n' "$?"
printf 'TMPLEFT=%s\n' "$(ls "$F".tmp.* 2>/dev/null | wc -l)"
'''

env = dict(os.environ, LIB=_posix(LIB), CG=_posix(CG), F=_posix(conf), VAL=VAL)
argv = [BASH, "-lc", script] if os.name == "nt" else [BASH, "-c", script]
p = subprocess.run(argv, capture_output=True, text=True, timeout=120, env=env)
out = p.stdout + p.stderr
print(out.rstrip())
if p.returncode != 0:
    chk("shell 脚本 rc=0", False, p.returncode)
else:
    kv = {}
    for line in p.stdout.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            kv[k] = v
    chk("conf_set_kv rc=0", kv.get("SET_RC") == "0", kv.get("SET_RC"))
    chk("source 读出原值", kv.get("SRC") == VAL, repr(kv.get("SRC")))
    chk("conf_get_kv 读出原值", kv.get("GET") == VAL, repr(kv.get("GET")))
    chk("conf-get CLI 读出原值", kv.get("CLI") == VAL, repr(kv.get("CLI")))
    chk("换行值 rc=2", kv.get("NL_RC") == "2", kv.get("NL_RC"))
    chk("拒绝后文件未变", kv.get("UNCHANGED") == "yes", kv.get("UNCHANGED"))
    chk("其它键保留", kv.get("CTX") == "32768", kv.get("CTX"))
    chk("缺失键 rc=1", kv.get("MISSING_RC") == "1", kv.get("MISSING_RC"))
    chk("无临时文件残留", kv.get("TMPLEFT") == "0", kv.get("TMPLEFT"))

    text = conf.read_text(encoding="utf-8")
    chk("写入形态为双引号", 'MODEL_PATH="' in text, text.splitlines()[2] if text else "")
    try:
        from conf_parse import get_value
        chk("conf_parse 读回原值", get_value(text, "MODEL_PATH") == VAL,
            repr(get_value(text, "MODEL_PATH")))
    except Exception as e:                               # noqa: BLE001
        chk("conf_parse 可导入", False, f"{type(e).__name__}: {e}")

print("\nRESULT: " + ("PASS" if not fails else f"FAIL ({len(fails)} 项)") +
      " · 失败: " + (", ".join(fails) if fails else "无"))
sys.exit(0 if not fails else 1)
