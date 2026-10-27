"""CI workflow 结构断言 —— 先验红（P2 小批次）。

断言 .github/workflows/ci.yml：
  · 存在且 YAML 可解析；
  · permissions.contents = read（最小权限）；
  · 两个 job：py-tests（windows-2022）/ shellcheck（ubuntu-24.04）；
  · py-tests 用 setup-python 3.12，运行 python tests/run_py_tests.py；
  · shellcheck 以 --severity=error 运行；
  · 全文不含 secrets.。

用法: py tests\\test_ci_workflow.py
"""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CI = ROOT / ".github" / "workflows" / "ci.yml"
fails = []


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


def _steps(job):
    return job.get("steps") or []


def _runs(steps):
    return "\n".join(str(s.get("run", "")) for s in steps)


def _uses(steps):
    return " ".join(str(s.get("uses", "")) for s in steps)


def _with(steps, key):
    vals = []
    for s in steps:
        w = s.get("with") or {}
        if key in w:
            vals.append(str(w[key]))
    return vals


def _shell_targets(runs):
    """从 run 命令里抽出被 shellcheck 的仓内路径（去重保序）。"""
    seen, out = set(), []
    for tok in runs.replace("\\", " ").split():
        if tok.startswith("ops/") and tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def validate_ci(data, text):
    """纯函数：返回 problems 列表；空 = PASS。"""
    problems = []
    if not isinstance(data, dict):
        return ["workflow 不是 mapping"]

    on = data.get("on")
    if on is None:
        on = data.get(True)          # PyYAML 把未加引号的 on 解析为 True
    if not on:
        problems.append("缺 on")

    perms = data.get("permissions") or {}
    if perms.get("contents") != "read":
        problems.append("permissions.contents 不是 read")

    jobs = data.get("jobs") or {}
    for name in ("py-tests", "shellcheck"):
        if name not in jobs:
            problems.append(f"缺 job: {name}")
    if problems:
        return problems

    py = jobs["py-tests"]
    if "windows" not in str(py.get("runs-on", "")):
        problems.append("py-tests 不在 windows runner")
    steps = _steps(py)
    if "actions/setup-python" not in _uses(steps):
        problems.append("py-tests 缺 setup-python")
    if "3.12" not in _with(steps, "python-version"):
        problems.append("setup-python 未指定 3.12")
    if "tests/run_py_tests.py" not in _runs(steps):
        problems.append("py-tests 未运行 tests/run_py_tests.py")
    # Windows runner 默认 cp1252：run_py_tests.py 打印中文会 UnicodeEncodeError
    if not (py.get("env") or {}).get("PYTHONUTF8"):
        problems.append("py-tests 未设 PYTHONUTF8（Windows runner 编码）")

    sc = jobs["shellcheck"]
    if "ubuntu" not in str(sc.get("runs-on", "")):
        problems.append("shellcheck 不在 ubuntu runner")
    sc_runs = _runs(_steps(sc))
    if "--severity=error" not in sc_runs:
        problems.append("shellcheck 未用 --severity=error")
    # SC1071：非 shell 脚本（如 python）不能进 shellcheck 列表
    for rel in _shell_targets(sc_runs):
        f = ROOT / rel
        if not f.is_file():
            problems.append(f"shellcheck 目标不存在: {rel}")
            continue
        shebang = f.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
        shebang = shebang[0] if shebang else ""
        if not shebang.startswith("#!") or "bash" not in shebang:
            problems.append(f"shellcheck 目标非 bash: {rel} ({shebang})")

    if "secrets." in text:
        problems.append("workflow 含 secrets.")
    return problems


# 负向夹具：缺权限 + 含 secrets 必须被判出
bad = {"on": {"push": None}, "jobs": {}}
chk("负向夹具：缺 permissions/jobs 可被判出",
    len(validate_ci(bad, "secrets.X")) >= 2)

if not CI.exists():
    chk(f"{CI.relative_to(ROOT)} 存在", False, str(CI))
else:
    text = CI.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except Exception as e:                               # noqa: BLE001
        data = None
        chk("ci.yml YAML 可解析", False, f"{type(e).__name__}: {e}")
    if data is not None:
        chk("ci.yml YAML 可解析", True)
        problems = validate_ci(data, text)
        chk("ci.yml 结构合规", not problems, "; ".join(problems))

print("\nRESULT: " + ("PASS" if not fails else f"FAIL ({len(fails)} 项)") +
      " · 失败: " + (", ".join(fails) if fails else "无"))
sys.exit(0 if not fails else 1)
