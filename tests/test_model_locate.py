"""model-locate.sh（P1 #3）—— 文件级枚举 + 三种落点 + 主文件优先级。

覆盖 IMPLEMENTATION §9.1 #3 行：
  · `gguf/<repo>/<f>.gguf`（depth-1 仓库级直放）；
  · `gguf/<repo>/<Model>-GGUF/<f>.gguf`；
  · `gguf/<repo>/<Model>-GGUF/<QUANT>/<f>.gguf`；
  · `mmproj*` 排除；找不到 alias rc=1；
  · infer-load 不再含 `-maxdepth 2 -type d`；
  · infer-list 的 scan 调用 model_scan；peer_scan 发送共享函数。

用法: py tests\\test_model_locate.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
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
LIB = ROOT / "ops" / "station-bin" / "model-locate.sh"
chk("model-locate.sh 存在", LIB.is_file(), LIB)
if not BASH or not LIB.is_file():
    print("\nRESULT: FAIL (model-locate.sh 尚未实现)")
    sys.exit(1)

tmp = tempfile.mkdtemp(prefix="p1model-")
root = Path(tmp) / "gguf"
(root / "repoA").mkdir(parents=True)
(root / "repoB" / "Model-B-GGUF").mkdir(parents=True)
(root / "repoC" / "Model-C-GGUF" / "Q4_K_M").mkdir(parents=True)
(root / "repoD").mkdir(parents=True)
(root / "repoA" / "model.gguf").write_bytes(b"x")
(root / "repoB" / "Model-B-GGUF" / "model.gguf").write_bytes(b"x")
(root / "repoC" / "Model-C-GGUF" / "Q4_K_M" / "model.gguf").write_bytes(b"x")
(root / "repoD" / "mmproj-x.gguf").write_bytes(b"x")
(root / "repoD" / "notes.txt").write_text("no gguf", encoding="utf-8")

script = r'''
set -uo pipefail
. "$LIB"
echo "===ALIASES==="
model_aliases "$ROOT"
echo "===SCAN==="
model_scan "$ROOT"
echo "===FILES==="
for a in repoa model-b model-c nope; do
  out=$(model_file_for_alias "$a" "$ROOT"); rc=$?
  printf 'F|%s|%s|%s\n' "$a" "$rc" "$out"
done
'''

env = dict(os.environ, LIB=_posix(LIB), ROOT=_posix(root))
argv = [BASH, "-lc", script] if os.name == "nt" else [BASH, "-c", script]
p = subprocess.run(argv, capture_output=True, text=True, timeout=120, env=env)
out = p.stdout + p.stderr
print(out.rstrip())
if p.returncode != 0:
    chk("shell 脚本 rc=0", False, p.returncode)
else:
    sections = {"ALIASES": [], "SCAN": [], "FILES": []}
    cur = None
    for line in p.stdout.splitlines():
        if line in ("===ALIASES===", "===SCAN===", "===FILES==="):
            cur = line.strip("=")
        elif cur:
            sections[cur].append(line)
    aliases = set(sections["ALIASES"])
    chk("三种落点别名齐全", {"repoa", "model-b", "model-c"} <= aliases, aliases)
    chk("mmproj 不产生别名", "repod" not in aliases, aliases)
    scan = "\n".join(sections["SCAN"])
    chk("scan 含 depth-1 路径", "/repoA/model.gguf" in scan)
    chk("scan 含 -GGUF 路径", "/repoB/Model-B-GGUF/model.gguf" in scan)
    chk("scan 含量化子目录路径", "/repoC/Model-C-GGUF/Q4_K_M/model.gguf" in scan)
    files = {}
    for line in sections["FILES"]:
        if line.startswith("F|"):
            _, a, rc, path = line.split("|", 3)
            files[a] = (rc, path)
    for a, tail in (("repoa", "/repoA/model.gguf"),
                    ("model-b", "/repoB/Model-B-GGUF/model.gguf"),
                    ("model-c", "/repoC/Model-C-GGUF/Q4_K_M/model.gguf")):
        rc, path = files.get(a, ("?", ""))
        chk(f"model_file_for_alias {a}", rc == "0" and path.endswith(tail), (rc, path))
    rc, _ = files.get("nope", ("?", ""))
    chk("缺失 alias rc=1", rc == "1", rc)

src_load = (ROOT / "ops" / "station-bin" / "infer-load").read_text(encoding="utf-8")
src_list = (ROOT / "ops" / "station-bin" / "infer-list").read_text(encoding="utf-8")
chk("infer-load 不再用 depth-2 目录定位", "-maxdepth 2 -type d" not in src_load)
chk("infer-load 调用 model_file_for_alias", "model_file_for_alias" in src_load)
chk("infer-list scan 调用 model_scan", "model_scan" in src_list)
chk("infer-list peer_scan 发送共享函数",
    "declare -f _model_alias_of" in src_list and "model_file_for_alias" in src_list)

print("\nRESULT: " + ("PASS" if not fails else f"FAIL ({len(fails)} 项)") +
      " · 失败: " + (", ".join(fails) if fails else "无"))
sys.exit(0 if not fails else 1)
