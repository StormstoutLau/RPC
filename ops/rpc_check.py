#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rpc 统一校验入口 (P0) —— 一条命令给结论。

被 `ops/rpc.ps1 check` 与 git hooks 调用。

设计铁律 (来自 docs/research/2026-09-14_暴露问题调研.md 的 CI/CD 分析):
  1. 断言清单化: 新增一条校验 = 往 CHECKS 加一条声明 + 写一个函数。
     目的: 避免"又一个脚本"式增长 —— 仓库现有 40+ 个手工校验脚本却没有总入口,
     而其中大部分从没被自动触发过。
  2. 退出码即门禁: 任一 FAIL -> exit 1, 供 pre-commit / pre-push 阻断。
  3. 结论先行: 先总表后明细; 跳过项、白名单项、不可达项都必须显式列出, 不做静默放行。

用法:
  python ops/rpc_check.py                  # 全量 (含三站配置比对)
  python ops/rpc_check.py --quick          # 仅本地快检 (pre-commit 用)
  python ops/rpc_check.py --only secrets,syntax
  python ops/rpc_check.py --list           # 只列断言清单
"""
import argparse
import ast
import concurrent.futures
import fnmatch
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── 断言 A1: 明文扫描 ─────────────────────────────────────────────
# 边界 (?<![A-Za-z0-9]) 用于排除 `task-2026...` 这类含 "sk-" 子串的误报。
# ⚠ 本清单与 `agent-cli.ps1` 的 `Get-ScrubRules`（出网前消毒，2026-09-21 扩到 9 条）**刻意不同**，
#   且**不要**为"对齐"去改：两者**作用域不同** —— 本处扫**仓库跟踪文件**（问"仓库里有没有真钥匙"），
#   那边扫**待出网 prompt**（问"出网字节里有没有敏感形态"）。裁定与理由见
#   docs/security/2026-09-21_scrubber规则扩充裁定与影响面.md §4 行 3。
SECRET_RE = re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}")

# 白名单: 需要"故意保留样串"的文件。每条必须写明原因, 且每次运行都会计数打印,
# 不允许变成静默放行。
SECRET_ALLOW = {
    "spec/d6-agent-standard/test-cards/sanitized.md":
        "脱敏器验收样串 (d6 CHECKLIST P1/A8b 判据要求此文件含样串)",
    "spec/d6-agent-standard/CHECKLIST.md":
        "文档正文引用 scrubber 正则与验收样串",
}


def _iter_source_files():
    """返回 (相对路径, 绝对路径) —— 以 git 跟踪文件为范围。

    范围选 git 跟踪文件而非"整个工作区": pre-commit 阶段新文件已 `git add`,
    故会出现在 ls-files 中; 而 tmp/ 等未跟踪目录不应参与提交门禁。

    ⚠ **2026-09-23（O-34）**：上面这条是**假设**，它**只在 pre-commit 钩子里成立** ——
    手动直跑（本仓推荐做法）若处于"文件已新建/重命名但未暂存"的中间态，范围会与提交时**不同**
    ⇒ **同一命令两种结论**。故配套 `_untracked_count()`，由消费者把它**显式报出来**，
    而不是让"范围已收窄"静默影响结论。
    """
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                             capture_output=True, check=True).stdout
        rels = [p for p in out.decode("utf-8", "replace").split("\0") if p]
    except Exception:
        rels = [str(p.relative_to(ROOT)).replace("\\", "/")
                for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]
    for r in rels:
        yield r, ROOT / r


def _untracked_count() -> int:
    """**未跟踪**（⇒ 不在门禁范围内）的文件数；`--exclude-standard` ⇒ 尊重 `.gitignore`。

    用途（O-34）：让"范围已收窄"**可见** —— 干净仓库/正常提交路径上恒为 0 ⇒ **零噪声**。
    """
    try:
        out = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "-z"],
                             cwd=ROOT, capture_output=True, check=True).stdout
        return len([p for p in out.decode("utf-8", "replace").split("\0") if p])
    except Exception:
        return 0


def _is_binary(path):
    try:
        with open(path, "rb") as fh:
            return b"\x00" in fh.read(8192)
    except OSError:
        return True


def _read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _mask(s):
    return s[:8] + "…" if len(s) > 9 else s


def allow_unhit(allow_keys, hit_keys):
    """**纯函数**（D6-P0-2）：豁免白名单里**未被命中**的项 ⇒ 应提示"该豁免已可移除"。

    为什么需要（**防腐化**）：豁免**失效后不会被告知** ⇒ 清单长期腐化（豁免留着、实际已不需要），
    而"**登记这个动作本身要在 review 里可见**"（ADR-0004 D2 纪律）⇒ 未命中必须**自报** ——
    **WARN（不阻断）**，因为"豁免多留一条"不是缺陷，但**必须被看见**（否则没人删）。
    """
    return sorted(set(allow_keys) - set(hit_keys))


def check_secrets(ctx):
    """扫描跟踪文件中的明文密钥形态。"""
    hits, allowed, scanned, skipped_bin = [], [], 0, 0
    for rel, path in _iter_source_files():
        if _is_binary(path):
            skipped_bin += 1
            continue
        text = _read_text(path)
        if "sk-" not in text:
            scanned += 1
            continue
        scanned += 1
        for i, line in enumerate(text.splitlines(), 1):
            for m in SECRET_RE.finditer(line):
                rec = (rel, i, _mask(m.group(0)))
                (allowed if rel in SECRET_ALLOW else hits).append(rec)
    detail = [f"{r}:{n}  {s}" for r, n, s in hits]
    for r, n, s in allowed:
        detail.append(f"(白名单) {r}:{n}  {s} —— {SECRET_ALLOW[r]}")
    # D6-P0-2: 豁免**未命中**（该文件里已无样串）⇒ **自报**，否则清单腐化无人知（可移除但没人删）
    _unhit = allow_unhit(list(SECRET_ALLOW), {r for r, _n, _s in allowed})
    for r in _unhit:
        detail.append(f"(豁免**未命中**) {r} —— {SECRET_ALLOW[r]} ⇒ "
                      f"该文件已无样串命中 ⇒ **该豁免已可移除**")
    note = f"扫描 {scanned} 个文本文件 (跳过 {skipped_bin} 个二进制), 命中 {len(hits)} 处"
    if allowed:
        note += f", 白名单 {len(allowed)} 处"
    if _unhit:
        note += f" · ⚠ 豁免未命中 {len(_unhit)} 条（已可移除，见明细）"
    # O-34: 范围 = git 跟踪文件；若此刻有未跟踪文件 ⇒ 本结论**可能**与 pre-commit 时不同，必须报出来。
    _un = _untracked_count()
    if _un:
        note += (f" · ⚠ 另有 {_un} 个**未跟踪**文件未计入（范围=git 跟踪文件；"
                 f"pre-commit 时新文件已暂存 ⇒ 手动跑与提交跑结论可能不同，见台账 O-34）")
    return ("FAIL" if hits else ("WARN" if _unhit else "PASS")), note, detail


# ── 断言 A2: 语法检查 ─────────────────────────────────────────────
PS_SNIPPET = r"""
$files = @($input | Where-Object { $_ -and $_.Trim() -ne '' })
foreach ($f in $files) {
  $tok = $null; $errs = $null
  [System.Management.Automation.Language.Parser]::ParseFile($f, [ref]$tok, [ref]$errs) | Out-Null
  if ($errs -and $errs.Count -gt 0) {
    foreach ($e in $errs) { "FAIL`t$f`t$($e.Extent.StartLineNumber)`t$($e.Message)" }
  }
}
"""

# ── P2 (ADR-0007 路A, 2026-09-18): 用 **PATH 第一个 `python`** 再编译一遍 .py ──────────
# 为什么单列: 上面那次 py_compile 用**当前解释器**, 而 rpc.ps1 挑的是"候选里**第一个能
#   `import paramiko` 的**" ⇒ 本机落到 **Python312**。后果实测(2026-09-18):
#   `cluster.py` 一行 f-string 表达式段含反斜杠(PEP 701 才允许) ⇒ 在 PATH 第一个
#   `python`(3.11.16) 下**整个模块不可解析**, 而 syntax 报 **0 失败**、evidence 因
#   `import cluster` 被 except 兜住只报 WARN ⇒ **判据静默消失、整仓仍 PASS**。
# 判据: 取 PATH 第一个 `python`(即人工敲 `python ops/cluster.py` 时真正会用的那个);
#   只要它与当前解释器**不同**, 就用它**一个子进程**批量编译(逐文件 spawn 会 43×0.2s)。
#   失败 ⇒ FAIL, 且明细**点名用了哪个解释器** —— 否则读者无从判断"该修语法还是该改声明"。
# 注: 这不是"多解释器矩阵"(不承诺支持任意旧版本), 只盯**人工实际会用的那个**。
PY_SNIPPET = r"""
import sys, os, py_compile, tempfile
td = tempfile.mkdtemp()
n = 0
for raw in sys.stdin.read().splitlines():
    f = raw.strip()
    if not f:
        continue
    n += 1
    try:
        py_compile.compile(f, cfile=os.path.join(td, "c%d" % n), doraise=True)
    except Exception as e:
        msg = str(e).strip().splitlines()
        print("FAIL\t%s\t%s" % (f, (msg[-1] if msg else type(e).__name__)[:160]))
print("SUMMARY\t%d" % n)
"""


def _py_version(exe: str) -> str:
    """取解释器版本 'X.Y.Z'；取不到返回 ''（**不抛** —— 这只是辅助信息，不该炸掉整个断言）。"""
    try:
        p = subprocess.run([exe, "-c", "import sys;print('%d.%d.%d' % sys.version_info[:3])"],
                           capture_output=True, cwd=ROOT, timeout=30)
        return (p.stdout or b"").decode("utf-8", "replace").strip() if p.returncode == 0 else ""
    except Exception:
        return ""


SH_LINT = ("n=0; while IFS= read -r f; do [ -z \"$f\" ] && continue; n=$((n+1)); "
           "if ! out=$(bash -n \"$f\" 2>&1); then printf 'FAIL\\t%s\\t%s\\n' \"$f\" \"$out\"; fi; "
           "done; printf 'COUNT\\t%s\\n' \"$n\"")

# ── shell 语法检查的三条修复 (2026-09-15，方案 v2 §A.6 P2-5 记录的那次事故) ────
# 旧实现把路径直接喂给裸 `bash -n`。本机 PATH 上的 `bash` 是 C:\Windows\system32\bash.EXE (WSL)，
# 它**看不到 D:\ / /d/ 形式的仓库路径** ⇒ `bash -n` 等于"文件不存在"，而旧代码把这种"读不到"
# 当成了"检查通过"：实测 447 个 .sh 报 0 失败，**往已跟踪文件注入语法错也不报**。
# 静默降级落在提交门禁自己身上，是本仓库最不能接受的一类错。故:
#   ① 显式找一个**能读到仓库路径**的 bash (Windows 上通常是 Git Bash)，并**实测它读得到**；
#   ② 统一传 POSIX 形态路径 (/d/RPC/...)；
#   ③ stdin 补尾换行 —— `while IFS= read -r` 会丢掉**没有换行结尾的最后一行**；
#   ④ **自证**: 先拿故意写错的临时文件验证"它真能判错"，做不到就整栏判 FAIL("不可信")，绝不报 PASS。
BASH_BROKEN_SAMPLE = "#!/bin/bash\nif [ 1 == ; then\n"


def _posix(p) -> str:
    """仓库内绝对路径 → POSIX 形态 (D:\\RPC\\x → /d/RPC/x)；任何 MSYS/Git Bash 都能读。"""
    s = str(p)
    if len(s) > 2 and s[1] == ":":
        return "/" + s[0].lower() + s[2:].replace("\\", "/")
    return s.replace("\\", "/")


def _bash_candidates():
    """候选 bash 列表 (去重、存在的)。PATH 上的排第一，其后是 Git for Windows 的常见落点。"""
    cands = [shutil.which("bash")]
    for env in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if not base:
            continue
        cands += [os.path.join(base, "Git", "bin", "bash.exe"),
                  os.path.join(base, "Git", "usr", "bin", "bash.exe"),
                  os.path.join(base, "Programs", "Git", "bin", "bash.exe")]
    seen, out = set(), []
    for c in cands:
        if c and c not in seen and os.path.exists(c):
            seen.add(c)
            out.append(c)
    return out


def _bash_can_read(bash: str) -> bool:
    """用**真实仓库 .sh** 探一下它能不能打开我们的路径 —— "空转"与"真检查"的分界就在这。"""
    probe = next((p for _, p in _iter_source_files()
                  if p.suffix.lower() == ".sh" and p.is_file()), None)
    if probe is None:
        return False
    try:
        r = subprocess.run([bash, "-c", f'test -f "{_posix(probe)}" && echo READABLE'],
                           capture_output=True, text=True, cwd=ROOT, timeout=30)
        return "READABLE" in (r.stdout or "")
    except Exception:
        return False


def _pick_bash():
    """返回 (bash 路径, 说明)。找不到可用的就返回 (None, 原因)。"""
    tried = []
    for b in _bash_candidates():
        if _bash_can_read(b):
            return b, ""
        tried.append(b)
    return None, (f"找不到能读到仓库路径的 bash (试过 {len(tried)} 个: {', '.join(tried) or '无'}) —— "
                  f"本栏**不可信**, 请装 Git for Windows 或把它的 bash.exe 放进 PATH")


def _bash_lint(files, bash: str) -> tuple:
    """用指定 bash 跑一遍 `bash -n`。返回 (bad, details, count_seen)。

    count_seen = 远端循环实际处理的文件数 —— 用它断言"真的读到了全部文件"，
    而不是只看"没有 FAIL 行"(那是空转也会有的结果)。
    """
    out = _run_with_stdin([bash, "-c", SH_LINT], [_posix(p) for p in files])
    bad, details, seen = 0, [], None
    for ln in out.splitlines():
        if ln.startswith("FAIL\t"):
            parts = ln.split("\t", 2)
            msg = (parts[2] if len(parts) > 2 else "").strip()
            name = parts[1] if len(parts) > 1 else "?"
            bad += 1
            details.append(f"(sh) {name if name not in ('1', '') else ''} {msg[:150]}".strip())
        elif ln.startswith("COUNT\t"):
            try:
                seen = int(ln.split("\t", 1)[1])
            except ValueError:
                seen = None
    return bad, details, seen


# ── shell 语法检查并行化 (2026-09-23, 第③项) ────────────────────────
# 为什么是**并行分块**而不是"合并外层循环"(第一条捷径):
#   `bash -n <file>` 只把第一个入口当脚本解析(source 进来的不算), 所以每个文件**必须**独立
#   fork 一次 `bash -n` —— 那把多个文件拼进同一次 bash 调用的"合并"做法, 只会检查第一个文件,
#   是静默降为 0 覆盖(本仓最忌讳)。cProfile 实测 syntax 19.6s 里 ~17s 卡在逐文件 fork 的
#   `_stdin_write`, 语法解析本身仅 ~0.3s ⇒ 并行分块是不**删除**任何判据、也不改 seen 口径的提速。
def _bash_lint_parallel(files, bash: str, workers: int = 8) -> tuple:
    """并行分块跑 `_bash_lint`。返回 (bad, details, seen_sum)。

    seen 口径保持"远端循环实际处理的文件总数" ⇒ 覆盖校验仍看它 == len(files)，
    不会因为并行而丢掉"读到数 != 喂入数 ⇒ 结果不可信"这条。
    """
    if not files:
        return 0, [], 0
    n = min(workers, len(files))
    chunks = [files[i::n] for i in range(n)]
    bad_total, seen_total, all_det = 0, 0, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as ex:
        futs = [ex.submit(_bash_lint, chunk, bash) for chunk in chunks]
        for f in futs:
            b, d, seen = f.result()
            bad_total += b
            all_det += d
            seen_total += (seen if seen is not None else 0)
    return bad_total, all_det, seen_total


def _iter_shebang_scripts():
    """git 跟踪文件里**无扩展名但带 shebang** 的脚本 → (rel, path, kind)。

    为什么必须有这一段: 站上件大多是**无扩展名**的 —— infer-load / infer-unload /
    llama-serve-instance / cluster-ttl / reqlog / load-gate …，.py/.ps1/.sh/.json 一个都不覆盖
    ⇒ 这批"真正跑在站上的东西"此前**完全不过语法门禁**，而它们恰恰最不能带语法错上站
    (改坏 infer-load 会让整条加载链断掉)。
    """
    known = (".py", ".ps1", ".sh", ".json")
    for rel, path in _iter_source_files():
        if path.suffix.lower() in known or not path.is_file() or _is_binary(path):
            continue
        head = _read_text(path).splitlines()[:1]
        if not head or not head[0].startswith("#!"):
            continue
        if "python" in head[0]:
            yield rel, path, "py"
        elif "/bash" in head[0] or head[0].rstrip().endswith("/sh"):
            yield rel, path, "sh"


def _run_with_stdin(argv, files):
    """把文件列表喂给 argv 的 stdin。

    两个都是**实测踩过**的坑, 少一个就会静默出错:
    ⚠ ① **必须走字节模式** (不是 `text=True`): Windows 上文本模式会把写给孩子进程的 stdin 里的
       `\\n` 翻成 `\\r\\n`; 子壳的 `while IFS= read -r` 只吃掉 `\\n`, 路径尾巴上留下 `\\r`
       ⇒ 每个路径都变成"不存在的文件"。表现为**全部文件报失败** (实测 447/447), 极易误判成
       "仓库全坏了"。`subprocess` **没有** `newline=` 参数 (传了会 TypeError), 故只能喂 bytes。
    ⚠ ② **必须补尾换行**: `while IFS= read -r` 遇到没有换行结尾的最后一行时 read 返回非 0,
       循环体**不执行** —— 少喂一个文件却毫无提示 (同一个 while-read 家族的两个不同坑)。
    """
    try:
        p = subprocess.run(argv, input=("\n".join(files) + "\n").encode("utf-8"),
                           capture_output=True, cwd=ROOT)
        return (p.stdout or b"").decode("utf-8", "replace")
    except Exception as e:
        return f"FAIL\t1\t(无法执行 {argv[0]}: {type(e).__name__})"


def check_syntax(ctx):
    """py_compile / PowerShell AST / bash -n / JSON 解析。"""
    by_ext = {}
    for rel, path in _iter_source_files():
        ext = path.suffix.lower()
        if ext in (".py", ".ps1", ".sh", ".json"):
            by_ext.setdefault(ext, []).append((rel, path))

    detail, counts = [], {}

    # .py
    py_files = by_ext.get(".py", [])
    bad = 0
    with tempfile.TemporaryDirectory() as td:
        for rel, path in py_files:
            # 扩展名与内容不符: .py 却是别的解释器 (门禁首个真实收获即此类, 见 _bs1.py 案例)。
            # 直接报"应改扩展名或解包", 而不是抛一句看不懂的 SyntaxError。
            head = _read_text(path).splitlines()[:1]
            if head and head[0].startswith("#!") and "python" not in head[0]:
                bad += 1
                detail.append(f"{rel}  扩展名与内容不符: 首行 '{head[0].strip()}' "
                              f"→ 应解包为真 Python 或改为对应扩展名")
                continue
            cfile = os.path.join(td, rel.replace("/", "_") + "c")
            try:
                import py_compile
                py_compile.compile(str(path), cfile=cfile, doraise=True)
            except py_compile.PyCompileError as e:
                bad += 1
                detail.append(f"{rel}  {str(e).strip().splitlines()[-1][:160]}")
            except Exception as e:
                bad += 1
                detail.append(f"{rel}  {type(e).__name__}: {e}")
    counts[".py"] = (len(py_files), bad)

    # ── P2: 再用 **PATH 第一个 `python`** 编译一遍（见 PY_SNIPPET 处说明）─────────────
    # 目的只有一个: 让"人工敲 `python ops/cluster.py` 会不会炸"成为**门禁判据** ——
    #   上面那次编译用的是门禁自己的解释器(rpc.ps1 挑的第一个带 paramiko 的), 两者可能不同版本。
    _alt = shutil.which("python")
    _cur_ver = "%d.%d.%d" % sys.version_info[:3]
    if not _alt:
        detail.append("(py-alt) PATH 上无 `python` ⇒ 【人工敲的那个解释器能否解析】该维度未验证")
    elif os.path.abspath(_alt) == os.path.abspath(sys.executable):
        detail.append(f"(py-alt) PATH 第一个 python 就是当前解释器({_cur_ver}) ⇒ 无需重复编译")
    else:
        _alt_ver = _py_version(_alt)
        if not _alt_ver:
            detail.append(f"(py-alt) PATH 第一个 python({_alt}) 取不到版本 ⇒ 该维度未验证")
        else:
            _abs2rel = {str(p): rel for rel, p in py_files}
            _out = _run_with_stdin([_alt, "-c", PY_SNIPPET], [str(p) for _, p in py_files])
            _fails, _seen = [], 0
            for _ln in _out.splitlines():
                if _ln.startswith("SUMMARY\t"):
                    _, _n = _ln.split("\t", 1)
                    _seen = int(_n.strip() or 0)
                elif _ln.startswith("FAIL\t"):
                    _, _f, _msg = _ln.split("\t", 2)
                    _fails.append(f"(py{_alt_ver}) {_abs2rel.get(_f, _f)}  {_msg}")
            bad_alt = len(_fails)
            detail += _fails
            if _seen != len(py_files):
                # 与 .sh 分支同一条纪律: 读到数 != 喂入数 ⇒ 结果不可信, 拒绝给 PASS
                bad_alt = len(py_files)
                detail.append(f"(py{_alt_ver}) 覆盖不全: 实际编译 {_seen} / 应有 {len(py_files)} 个"
                              f" (读到数 != 喂入数 ⇒ 结果不可信)")
            counts[f".py@{_alt_ver}"] = (len(py_files), bad_alt)
            detail.append(f"(py-alt) PATH 第一个 python = {_alt_ver}"
                          f"（≠ 门禁解释器 {_cur_ver}）⇒ 已按它复检 {_seen} 个 .py, 失败 {bad_alt}")

    # .ps1 —— 单次 PowerShell 调用处理全部文件 (避免逐文件起进程)
    ps_files = by_ext.get(".ps1", [])
    bad = 0
    if ps_files:
        exe = "powershell.exe"
        with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False,
                                         encoding="utf-8-sig") as fh:
            fh.write(PS_SNIPPET)
            tmp_ps = fh.name
        out = _run_with_stdin([exe, "-NoProfile", "-ExecutionPolicy", "Bypass",
                               "-File", tmp_ps], [str(p) for _, p in ps_files])
        try:
            os.unlink(tmp_ps)
        except OSError:
            pass
        # ⚠ 失败数按**文件**计(不是按错误行计): 一个文件多行报错只算 1 —— 否则摘要会写
        #   "13文件/11失败", 读起来像"11 个文件坏了"(2026-09-21 实地误导过一次: 实际只有 1 个文件)。
        #   明细里**必须带文件名**: 13 个文件里只报 "Unexpected token ')' [line 37]" 是查不到人的。
        #   且统一回**仓库相对路径**(snippet 收到的是绝对路径), 与其它断言的明细格式一致。
        rel_of = {str(p): rel for rel, p in ps_files}
        bad_files = set()
        for ln in out.splitlines():
            if ln.startswith("FAIL\t"):
                parts = ln.split("\t", 3)
                if len(parts) < 4:
                    bad_files.add(f"<unparsed:{ln[:40]}>")
                    detail.append(f"(ps1) {ln[:160]}")
                    continue
                _, fabs, lineno, msg = parts
                frel = rel_of.get(fabs.strip(), fabs.strip())
                bad_files.add(frel)
                detail.append(f"(ps1) {frel}  {msg[:160]}  [line {lineno}]")
        bad = len(bad_files)
    counts[".ps1"] = (len(ps_files), bad)

    # ── .ps1 子判据 (2026-09-21, ADR-0004 D3 路径①): 含非 ASCII 的 .ps1 **必须**带 UTF-8 BOM ──
    # 触发: 09-18(守门夹具静默失效) 与 09-21(编辑工具剥掉三个脚本的 BOM 后夹具当场解析崩溃)。
    # ⚠ **根因(2026-09-21 实测更正, 勿沿用早先的错误说法)**: `Parser::ParseFile` **不是**按 UTF-8 读
    #   BOM-less 文件, 它与 `powershell -File x.ps1` **走同一条解码路径(BOM-less ⇒ ANSI/GBK)**。
    #   实测证据: 把一个 BOM-less 的中文 .ps1 喂给上游那次 ParseFile ⇒ 报 11 条错, 行号**全部落在
    #   中文注释行**(30/37/209/214/231/237/257/299) —— 若真是按 UTF-8 读, 一条错都不会有。
    # ⇒ 所以上游那条判据**能抓到**, 但**只在乱码恰好破坏语法时**才抓到:
    #     3 字节 UTF-8 被当 2 字节 GBK 解码, 是否"吞掉相邻换行"**取决于内容** ⇒ 同样的缺陷在
    #     **不同内容下**可能报 11 条错, 也可能报 **0 条错却照样跑坏**(09-18 目击的正是后者: 门禁
    #     `.ps1:12文件/0失败`, 而夹具 `fns count=0`)。**间歇、内容相关、且报错指向注释行而不指根因**
    #     —— 这三条加在一起才构成"必须另加字节判据"的理由。
    # 本判据是**确定性**的(读字节, 与内容无关), 且**报的是根因**(含非 ASCII 却无 BOM)而非症状。
    # 判据: 有非 ASCII 字节 且 无 `EF BB BF` ⇒ FAIL。纯 ASCII 的 .ps1 **不受约束**(无 BOM 也安全, 不误报)。
    # 为什么**不**覆盖 .sh: `.sh` **不得**加 BOM —— BOM 会让内核把 `#!` 认成 `\xEF\xBB\xBF#!`
    #   ⇒ `bad interpreter` 直接不可执行。站上是 UTF-8 locale, 风险形态不同, 故不在此判。
    bad_bom = 0
    for rel, path in ps_files:
        try:
            raw = path.read_bytes()
        except OSError as e:
            bad_bom += 1
            detail.append(f"(ps1-bom) {rel}  读字节失败: {type(e).__name__}")
            continue
        if raw[:3] == b"\xef\xbb\xbf":
            continue
        if any(byte > 0x7F for byte in raw):
            bad_bom += 1
            detail.append(f"(ps1-bom) {rel}  含非 ASCII 却**无 UTF-8 BOM** ⇒ PS5.1 按 ANSI(GBK) "
                          f"解码可能吞掉换行致脚本静默损坏 ⇒ 修: 以 UTF-8 **带 BOM** 重写")
    counts[".ps1-bom"] = (len(ps_files), bad_bom)

    # ── shell 语法: .sh + **无扩展名的 shebang 脚本** (站上件), 共用一次 bash 调用 ──
    sh_files = [(rel, p) for rel, p in by_ext.get(".sh", [])]
    sb = list(_iter_shebang_scripts())
    sb_sh = [(rel, p) for rel, p, k in sb if k == "sh"]
    sb_py = [(rel, p) for rel, p, k in sb if k == "py"]

    bash, why = _pick_bash()
    bad_sh, bad_sb_sh = 0, 0
    if not bash:
        # 判"不可信"而不是 PASS —— 见 SH_LINT 上方的说明 (本仓库最忌讳的静默降级正在这里)
        bad_sh = len(sh_files)
        bad_sb_sh = len(sb_sh)
        detail.append(f"shell 语法检查不可信: {why}")
    else:
        # 自证 (双向对照): 好样本必须不报错、坏样本必须报**语法错**。
        # ⚠ 只断言"出现了 FAIL"是不够的 —— 我第一版就是这么写的, 结果在"所有路径都因为 CRLF
        # 变成不存在的文件"时, 自证依然"通过"(它测的其实是个不存在的文件)。必须校验**报错内容**。
        with tempfile.TemporaryDirectory() as td:
            good = Path(td) / "good.sh"
            broke = Path(td) / "broken.sh"
            good.write_text("#!/bin/bash\nset -u\nfor i in 1 2 3; do echo \"$i\"; done\n",
                            encoding="utf-8", newline="\n")
            broke.write_text(BASH_BROKEN_SAMPLE, encoding="utf-8", newline="\n")
            n_good, det_good, seen_good = _bash_lint([good], bash)
            n_broke, det_broke, seen_broke = _bash_lint([broke], bash)
        ok_self = (n_good == 0 and seen_good == 1
                   and n_broke == 1 and seen_broke == 1
                   and any("syntax error" in d for d in det_broke))
        if not ok_self:
            bad_sh, bad_sb_sh = len(sh_files), len(sb_sh)
            detail.append(
                f"shell 语法检查自证失败: {os.path.basename(bash)} 好样本报错/坏样本未被判为语法错"
                f" (good={n_good}/{seen_good} bad={n_broke}/{seen_broke}"
                f" detail={' | '.join(det_broke)[:80]}) → 本栏不可信, 拒绝给 PASS")
        else:
            # ③(2026-09-23): 业务 `.sh` 与无扩展名脚本**并行**检查。
            #   cProfile 实测: `bash -n` 必须逐文件 fork(见 _bash_lint_parallel 注释), syntax 的
            #   ~17s 全卡在 fork, 解析本身仅 0.3s ⇒ 并行分块(默认 8 worker)让 19.6s → ~3s 量级。
            #   自证(good/broke)保持串行独立 —— 那是"好样本必 0 错/坏样本必 1 错"的单文件判定。
            if sh_files:
                bad_sh, det, seen = _bash_lint_parallel([p for _, p in sh_files], bash)
                detail += det
                if seen != len(sh_files):
                    bad_sh = len(sh_files)
                    detail.append(f".sh 覆盖不全: 实际检查 {seen} / 应有 {len(sh_files)} 个"
                                  f" (读到数 != 喂入数 ⇒ 结果不可信)")
            if sb_sh:
                bad_sb_sh, det, seen = _bash_lint_parallel([p for _, p in sb_sh], bash)
                detail += det
                if seen != len(sb_sh):
                    bad_sb_sh = len(sb_sh)
                    detail.append(f"无扩展名脚本覆盖不全: 实际检查 {seen} / 应有 {len(sb_sh)} 个")
    counts[".sh"] = (len(sh_files), bad_sh)

    # 无扩展名脚本的 python 半边 (与 bash 无关, 总能查)
    bad_sb_py = 0
    if sb_py:
        with tempfile.TemporaryDirectory() as td:
            for rel, path in sb_py:
                cfile = os.path.join(td, rel.replace("/", "_") + "c")
                try:
                    import py_compile
                    py_compile.compile(str(path), cfile=cfile, doraise=True)
                except py_compile.PyCompileError as e:
                    bad_sb_py += 1
                    detail.append(f"(无扩展名/py) {rel}  {str(e).strip().splitlines()[-1][:140]}")
                except Exception as e:
                    bad_sb_py += 1
                    detail.append(f"(无扩展名/py) {rel}  {type(e).__name__}: {e}")
    counts["无扩展名"] = (len(sb), bad_sb_sh + bad_sb_py)

    # .json —— 严格 JSON (跳过 .jsonc: 允许注释, 非标准 JSON)
    json_files = by_ext.get(".json", [])
    bad = 0
    for rel, path in json_files:
        try:
            json.loads(_read_text(path))
        except Exception as e:
            bad += 1
            detail.append(f"{rel}  {type(e).__name__}: {str(e)[:140]}")
    counts[".json"] = (len(json_files), bad)

    total_bad = sum(b for _, b in counts.values())
    note = " ".join(f"{ext}:{n}文件/{b}失败" for ext, (n, b) in sorted(counts.items()))
    return ("FAIL" if total_bad else "PASS"), note, detail


# ── 断言 A13: 脚本治理 (ADR-0004「统一管理入口为唯一管理面」) ──────────
# 背景: ops/ 下积累了两百多个一次性脚本 (`_xxx.sh` 一片), 各自管一小块、与统一入口能力重复、
# 还要各自维护。规则: **所有管理操作从统一入口 (cluster.py / cluster_web.py) 执行**;
# 存量冻结(只减不增), 新增脚本必须登记 —— 登记这个动作本身就是 review 时能看见的留痕。
# 只写规则不绑定执行等于空头承诺, 故做成断言 (与 plugins 的 known_drift 同一套纪律)。
OPS_INV = ROOT / "inventory" / "ops.yaml"
SCRIPT_EXT = (".py", ".ps1", ".sh")


def _in_script_scope(rel):
    """脚本治理的**范围谓词** (两层): `ops/**` ∪ **仓库根顶层文件**。

    为什么不写成"全仓递归 + 排除表" (2026-09-22 裁定, 决策简报《门禁口径…root 级脚本范围》):
      · 全仓递归会把 `spec/**` (文档/卡片)、`tests/**` (夹具)、`archive/**` (已归档) 一并圈进来,
        而这些目录**天然**不是管理面; 要正确排除就得维护一张不断变长的例外清单 ——
        每加一个目录就多一个定义点, 漏一项就是假红/假绿 (本仓纪律: 判据只在一处定义)。
      · 两层谓词**不需要任何例外清单**: 顶层文件 = 有人把一次性的东西直接丢在仓库根,
        正是 2026-09-16 真正出事的形态 (根级 3 个零引用脚本); `ops/**` 是 ADR-0004 定义的管理面。
        目录内的散件由目录自身归位 (archive/ 归档、tests/ 夹具)。
      · 实测 (2026-09-22): 顶层被跟踪文件只有 `.gitignore` 与 `LICENSE`,
        二者在 Python 里 `suffix=''` ⇒ 走 shebang 分支、首行非 `#!` ⇒ 不被当脚本
        ⇒ 扩范围后**今日 0 项未登记**, 登记表零改动。
    注意: PowerShell 的 `[IO.Path]::GetExtension('.gitignore')` 得 `.gitignore`,
    与 Python 的 `os.path.splitext` 语义不同 —— 判据以 Python 侧为准。
    """
    return rel.startswith("ops/") or "/" not in rel


def _iter_governed_scripts():
    """受脚本治理约束的 git 跟踪**脚本** → [(rel, path)]。范围见 `_in_script_scope`。
    含无扩展名但带 shebang 的 (站上件常见)。"""
    for rel, path in _iter_source_files():
        if not _in_script_scope(rel) or not path.is_file():
            continue
        if path.suffix.lower() in SCRIPT_EXT:
            yield rel, path
        elif not path.suffix and not _is_binary(path):
            head = _read_text(path).splitlines()[:1]
            if head and head[0].startswith("#!"):
                yield rel, path


def check_scripts(ctx):
    """脚本治理 (范围: `ops/**` ∪ 仓库根顶层, 见 `_in_script_scope`):
    任何脚本必须在登记表里 (入口 / 站上运行时件 / 冻结存量)。"""
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过脚本治理断言 (不复现于 CI 环境即视为通过)", []
    if not OPS_INV.exists():
        return "FAIL", "inventory/ops.yaml 缺失 (本断言的登记依据)", []
    try:
        inv = yaml.safe_load(OPS_INV.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return "FAIL", f"inventory/ops.yaml 解析失败: {type(e).__name__}: {e}", []

    entry = list(inv.get("entry") or [])
    modules = list(inv.get("entry_modules") or [])      # 2026-09-23: 入口的拆分模块 (见 ops.yaml 注释)
    runtime = list(inv.get("station_runtime") or [])
    frozen = list(inv.get("frozen_ops_scripts") or [])
    known = set(entry) | set(modules) | set(runtime) | set(frozen)

    scripts = dict(_iter_governed_scripts())
    unknown = sorted(s for s in scripts if s not in known)
    missing_entry = [e for e in entry if not (ROOT / e).exists()]
    missing_module = [m for m in modules if not (ROOT / m).exists()]
    gone = sorted(f for f in frozen if not (ROOT / f).exists())          # O-44: 真不存在
    untracked_frozen = sorted(f for f in frozen                          # O-44: 存在但未 git 跟踪
                              if (ROOT / f).exists() and f not in scripts)

    detail = []
    if unknown:
        detail.append(f"新增未登记脚本 {len(unknown)} 个 —— 管理操作请优先给统一入口加子命令 "
                      f"(ops/cluster.py <sub>), 而非再写一个脚本:")
        detail += [f"  {s}" for s in unknown[:20]]
        if len(unknown) > 20:
            detail.append(f"  …另 {len(unknown) - 20} 个")
    if missing_entry:
        detail.append("统一入口件缺失: " + ", ".join(missing_entry))
    if missing_module:
        detail.append("入口拆分模块缺失 (登记了但文件不在): " + ", ".join(missing_module))
    if gone:
        detail.append(f"冻结清单里已不存在的 {len(gone)} 项可从 inventory/ops.yaml 删掉 "
                      f"(只减不增, 删减是欢迎的方向): " + ", ".join(gone[:8])
                      + (" …" if len(gone) > 8 else ""))
    # O-44 (2026-09-24): 与 `gone` 分开报 —— 这些**文件确实在**，只是本次扫描（git 跟踪集）没覆盖到。
    #   旧实现把它们并入 `gone` 并提示"已不存在、可从清单删掉" ⇒ **照做则提交后立刻变"未登记" FAIL**。
    #   措辞必须**明确劝阻删除**（O-34 同源：范围收窄必须让"收窄"本身可见）。
    if untracked_frozen:
        detail.append(f"冻结清单里 {len(untracked_frozen)} 项**文件存在但未被 git 跟踪**(未 `git add`) "
                      f"⇒ 本次扫描未计入, **勿据此删登记**(只需 `git add`): "
                      + ", ".join(untracked_frozen[:8]) + (" …" if len(untracked_frozen) > 8 else ""))
    bad = bool(unknown) or bool(missing_entry) or bool(missing_module)
    note = (f"扫描 {len(scripts)} 个脚本 · 入口 {len(entry)} · 拆分模块 {len(modules)} "
            f"· 站上运行时 {len(runtime)} · 冻结存量 {len(frozen)} · 未登记 {len(unknown)}")
    # 提示必须进 note: PASS 时明细块不打印, 只放 detail 等于没人看得到 (实测踩到)
    if gone:
        note += f" · 清单含 {len(gone)} 项已不存在(应移除)"
    if untracked_frozen:
        note += f" · 清单含 {len(untracked_frozen)} 项未跟踪(勿删, 仅需 git add)"
    return ("FAIL" if bad else "PASS"), note, detail


ARTIFACTS_INV = ROOT / "inventory" / "artifacts.yaml"


def check_artifacts(ctx):
    """生成物清单（D6-P1-1）：**"权威源在别处"的文件，有没有人真的在判它。**

    为什么单独立一项：本仓最贵的失败形态是"**判据通过了，是因为它什么都没判**"——
    而生成物特有的两种病是它的两个变体：
      · **静默缺口**：某文件是推导出来的，**既没人判、也没说明为什么不判** ⇒ 可以长期错着没人知道；
      · **挂名假判**：清单写了 `check: xxx`，但 `xxx` **不是真实断言 id**（改了名/删了项）⇒ 看着有人管。
    本项把这两者都变成 FAIL，并**报覆盖率**（"新增判据必须同时报覆盖率"）。

    第 ① 项（`inventory/*.yaml` 可解析）不是顺手加的：**解析不了 ⇒ 任何"重算 → 比对"都前提失效**，
    而失败会以"下游某个数掉了"的形式远距离显形（本会话已见过 `inventory` 报数掉到 0 仍 PASS 的同族）。
    """
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过生成物清单断言（不复现于 CI 环境即视为通过）", []
    detail = []

    # ① 前提：inventory 真值表必须**全部可解析**（"重算 → 比对"的前置）
    yaml_files = sorted((ROOT / "inventory").glob("*.yaml"))
    bad_parse = []
    for p in yaml_files:
        try:
            yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception as e:
            bad_parse.append(f"{p.name}({type(e).__name__})")
    if bad_parse:
        detail.append("inventory/*.yaml 解析失败 ⇒ 其下游一切'重算比对'前提失效: " + ", ".join(bad_parse))

    # ② 清单本身
    if not ARTIFACTS_INV.exists():
        return "FAIL", "inventory/artifacts.yaml 缺失（本断言的登记依据）", detail
    try:
        inv = yaml.safe_load(ARTIFACTS_INV.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return "FAIL", f"inventory/artifacts.yaml 解析失败: {type(e).__name__}: {e}", detail

    items = list(inv.get("items") or [])
    known_ids = {c["id"] for c in CHECKS}
    covered = exempt = 0
    for it in items:
        p = it.get("path") or "(缺 path)"
        ck, ex = it.get("check"), it.get("exempt")
        if ck and ex:
            detail.append(f"{p}: `check` 与 `exempt` **互斥**（要么判、要么说明豁免，不能既判又豁免）")
        elif ck:
            if ck not in known_ids:
                # 这一条正是"挂名假判"：看着有人管，其实那个 id 不存在（改名/删除后没人发现）
                detail.append(f"{p}: check={ck!r} **不是真实断言 id**（挂在没人跑的判据上 = 挂名假判）")
            else:
                covered += 1
        elif ex:
            exempt += 1
        else:
            # 这一条正是"静默缺口"
            detail.append(f"{p}: **既无 `check` 也无 `exempt`** ⇒ 静默缺口（没人判，也没说明为什么）")

    # ③ 覆盖率必须报（"判据可能什么都没判"的对抗措施）
    note = (f"生成物 {len(items)} 条 · 有断言覆盖 {covered} · 显式豁免 {exempt} "
            f"· inventory yaml 可解析 {len(yaml_files) - len(bad_parse)}/{len(yaml_files)}")
    return ("FAIL" if detail else "PASS"), note, detail


SENSITIVITY_INV = ROOT / "inventory" / "sensitivity.yaml"
# 封闭枚举 —— 与 `sensitivity.yaml` 表头第 29-33 行、及 `agent-cli.ps1` 的 `--Sensitivity` 三档一致
SENSITIVITY_TIERS = ("public", "sanitized", "local-only", "unverified")
SENSITIVITY_SECTIONS = ("documents", "contracts", "code")


def validate_sensitivity_inv(inv, exists_fn):
    """**纯函数**：`sensitivity.yaml` 的自洽判定（只吃解析后的对象 + 一个 exists 回调 ⇒ 离线可正反夹测）。

    O-51 的定性：该表**权威源在自身**（它就是"内容→档位"的真值），但**建了之后 `ops/` 全域零命中**
    ⇒ 是"**存在但无人读**"的活标本。⇒ 本判据把它的**自洽义务**接上（不新增第二份真值）：

      ① 每条 `path` **必须真实存在**（文件或目录）—— 否则登记指向不存在的东西 = **记录与实效脱节**；
      ② `tier` 必须 ∈ **封闭枚举**（拼错一个档位名不该静默通过）；
      ③ ★ **同一 `path` 不得在两处以"不同 tier"出现** —— "同一事实两个定义点"是本仓头号形态，
         各自看都对、合起来矛盾，且**没有一处会报警**。

    返回 `(bad_list, stats)`；`stats` 供上层**报覆盖率**（"新增判据必须同时报覆盖率"）。
    """
    bad = []
    seen = {}          # path -> (tier, section)
    n = 0
    per_tier = {}
    for sec in SENSITIVITY_SECTIONS:
        for it in (inv.get(sec) or []):
            n += 1
            p = (it or {}).get("path")
            tier = (it or {}).get("tier")
            if not p:
                bad.append(f"[{sec}] 有条目缺 `path`")
                continue
            if tier not in SENSITIVITY_TIERS:
                bad.append(f"[{sec}] {p}: tier={tier!r} 不在封闭枚举 {SENSITIVITY_TIERS}")
            else:
                per_tier[tier] = per_tier.get(tier, 0) + 1
            if not exists_fn(p):
                bad.append(f"[{sec}] {p}: **路径不存在** ⇒ 登记指向空物（记录与实效脱节）")
            if p in seen and seen[p][0] != tier:
                bad.append(f"{p}: **同一路径两处不同 tier**（{seen[p][1]}={seen[p][0]!r} vs {sec}={tier!r}）"
                           f" ⇒ 同一事实两个定义点，各自看都对、合起来矛盾且无人报警")
            else:
                seen[p] = (tier, sec)
    return bad, {"n": n, "tiers": per_tier}


def check_sensitivity(ctx):
    """`inventory/sensitivity.yaml` 的自洽断言（O-51：把"建了没人读"的真值表接上义务）。"""
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 sensitivity 真值表断言", []
    if not SENSITIVITY_INV.exists():
        return "FAIL", "inventory/sensitivity.yaml 缺失", []
    try:
        inv = yaml.safe_load(SENSITIVITY_INV.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return "FAIL", f"inventory/sensitivity.yaml 解析失败: {type(e).__name__}: {e}", []

    default_tier = inv.get("default_tier")
    bad, st = validate_sensitivity_inv(inv, lambda p: (ROOT / p).exists())
    if default_tier != "local-only":
        # fail-closed 的前提：未登记必须是**最严**档。若被改成 public/sanitized ⇒ 静默放宽，必须 FAIL。
        bad.append(f"default_tier={default_tier!r} —— 必须为 'local-only'（fail-closed：未登记不得默认放宽）")

    tiers = " · ".join(f"{k}={v}" for k, v in sorted(st["tiers"].items()))
    note = f"条目 {st['n']} 条 · 档位分布 {tiers} · default={default_tier} · 枚举 {len(SENSITIVITY_TIERS)} 档"
    return ("FAIL" if bad else "PASS"), note, bad


# ── D7-P1-1 (2026-09-26)：U-2 证据强度字典 + 方言映射表 ──────────────────────
# 目的：同一个符号（`L1` / `A` / `R1` / `E1`）在九个项目里指互不相干的东西；
#   「建映射、不迁移权威源」缺了它就只能靠人读文档记忆。而**映射表自己**最容易出的两种病是：
#     · **漏项**（实测：`b1b` 的对照表漏了摘要族 2 的第三行 `Cpp_Hub Tier 1/2`）⇒ 用 `coverage` 逐族点行数（**双向**：多也红）；
#     · **静默漂移**（源词表改了，映射表还是旧的）⇒ 用**源切片指纹**比对（这就是 D7-P1-1 退出判据的「源词表变了下游红」）。
# ★ 为什么必须**真读源文件**而不是只信登记：D7-P1-1 的教训②原文 =「映射表本身要能被门禁校验
#   （源词表变了下游要红）」。⚠ 但源在**别的仓库**（他方项目）⇒ 本仓**只能对账、不能强制**，
#   ⇒ 本断言把"源"定义成**本仓内的两个投影**（原文切片 + 出站版摘要），对它们做指纹；
#     他方源本身的变化**抓不到**，此事已在 `regeneration.why_not_automated` 如实登记（不假装能同步）。
# ★ 三处硬要求各有出处（§11.4 的三条教训）：
#   ① 命名空间前缀 = **必填字段**（不靠人自觉写前缀）⇒ `namespace` 必填且 ∈ 白名单；
#   ② 未定轴**不许硬塞**：`axis=not-assigned` 必须写 `axis_note`（说明它属于什么轴）；
#   ③ `axis=evidence-strength` 而逐级对应未知时，只允许写 `axis_value: undefined` + 理由
#      —— 堵住"看着像就填"（`b1b` 实测把 RPC 的 E1–E5 猜成了「官方>社区>实测>推断>无据」，输入里没有）。
# ── ★★ `U1#5`（2026-10-01 裁）：**命名空间注册表**（`inventory/namespaces.yaml` = 取值域的**唯一真值**）──
# 背景（**实测**）：U1 spec §1.3 曾把身份取值域指向 `dialect.yaml` 的 `namespaces`，而那份文件自称**生成物**
#   （"禁止手工编辑语义 —— 一律改源头 → 重抽"）⇒ ★★ **两条纪律互斗**：想新增一个 namespace **没有合法路径**
#   （改它 = 违反生成物纪律；走重抽 = 源里根本没有这一节）⇒ **取值域不该挂在派生视图上**。
# ⇒ 剥出成独立真值文件；`dialect`（U-2 映射行）与 `u1-identity`（U-1 身份声明）**都只读它**。
NAMESPACE_REG = ROOT / "inventory" / "namespaces.yaml"
NS_STATUS = ("active", "reserved", "retired")


def namespace_index(reg):
    """注册表 → `(by_id, alias2id)`。**唯一**解析点（消费者不许各自再建一份表）。"""
    by_id, a2i = {}, {}
    for n in ((reg or {}).get("namespaces") or []):
        if not isinstance(n, dict) or not n.get("id"):
            continue
        by_id[n["id"]] = n
        for a in (n.get("aliases") or []):
            a2i[a] = n["id"]
    return by_id, a2i


def validate_namespaces(reg):
    """**纯函数** → `(bad, notes)`：注册表自洽（三条治理规则的**机判本体**）。

    ① `id` 非空；② `status` ∈ `NS_STATUS`；③ `since` 形如 `YYYY-MM-DD`；
    ④ ★ **同一个字符串不许同时属于两条**（id 或 alias）—— 这是**唯一**会判红的**冲突**（治理规则②）。
    """
    bad, notes = [], []
    if not isinstance(reg, dict):
        return ["namespaces.yaml 顶层不是映射（结构改了？）"], notes
    items = reg.get("namespaces") or []
    if not items:
        bad.append("`namespaces` 为空 ⇒ 身份取值域没有内容（判据会退化成空判）")
    seen = {}
    for i, n in enumerate(items, 1):
        if not isinstance(n, dict):
            bad.append(f"`namespaces[{i}]` 不是映射: {n!r}")
            continue
        nid = n.get("id")
        if not nid:
            bad.append(f"`namespaces[{i}]` 缺 `id`")
            continue
        if n.get("status") not in NS_STATUS:
            bad.append(f"`namespaces[{i}]`({nid}) status={n.get('status')!r} 不在闭集 {list(NS_STATUS)}")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(n.get("since") or "")):
            bad.append(f"`namespaces[{i}]`({nid}) `since` 必须是 `YYYY-MM-DD`: {n.get('since')!r}")
        for token in [nid] + list(n.get("aliases") or []):
            if token in seen and seen[token] != nid:
                bad.append(f"★ **命名空间冲突**：{token!r} 同时属于 {seen[token]!r} 与 {nid!r} "
                           f"⇒ 同一个串不许出现在两条里（治理规则②）")
            seen.setdefault(token, nid)
    notes.append(f"命名空间 {len(items)} 条 · active "
                 f"{sum(1 for n in items if isinstance(n, dict) and n.get('status') == 'active')} · 字符串位点 {len(seen)}")
    return bad, notes


def namespace_domain_error(ns, reg):
    """★★ `U1#5` 判据：一个 `namespace` 取值是否合法 ⇒ 错误串，或 `None`（合法）。

    ★ 规则比"在不在名单里"**严一档**：必须是 **canonical `id` 且 `status: active`**。
      · 写 **alias**（如 `Open_Data`）⇒ **拒**，并提示应改写成 canonical id ——
        身份 = 对 `["<ns>","<id>","<ver>"]` 的哈希，**吃的是原字符串** ⇒ 放行别名会让同一产物**有两个身份**；
      · `retired` ⇒ **拒**（历史身份仍可复算，但**新声明不许用**，治理规则③）；
      · 未登记 ⇒ **拒**（fail-closed）。
    ⚠ 匹配一律**精确**（不做大小写 / 分隔符归一）—— 归一化会把"两个身份"藏起来。
    """
    by_id, a2i = namespace_index(reg)
    if ns in by_id:
        st = by_id[ns].get("status")
        if st == "active":
            return None
        return f"`namespace`={ns!r} 的状态是 `{st}` ⇒ 不得用于**新**声明（治理规则③：退役不删，但不许新用）"
    if ns in a2i:
        return (f"`namespace`={ns!r} 是 **alias**，身份里必须写 canonical id `{a2i[ns]!r}` —— "
                f"⚠ 别名若放行，同一个产物会有**两个身份**（哈希吃原字符串）")
    return f"`namespace`={ns!r} **未登记** ⇒ 拒（fail-closed；要新增须先写进 `inventory/namespaces.yaml`）"


def namespace_for_project(project, reg):
    """`项目名 → canonical namespace`（**消费侧**用，如 `--invalidate` 的 affected 归集）。

    ⚠ 只在**有登记时**才换算（id 或 alias 精确命中）；**未登记 ⇒ 原样返回**（与旧行为一致 —— 不猜）。
    """
    by_id, a2i = namespace_index(reg)
    if project in by_id:
        return project
    return a2i.get(project, project)


DIALECT_INV = ROOT / "inventory" / "dialect.yaml"
DIALECT_AXES = {"evidence-strength", "not-assigned"}
DIALECT_RELATIONS = {"独占", "冲突", "同名不同义-族内"}
DIALECT_UNKNOWN = "undefined"


def _dialect_norm(text):
    """与指纹登记**同口径**：CRLF→LF、逐行去尾空白、行尾统一 `\\n`。

    ⚠ 必须与写指纹时用的口径逐字一致 —— 差一个 `\\r` 就会让**每一次**跑都红（假红），
    而假红的下场是"把判据关掉"（比不判更坏）。
    """
    return "\n".join(l.rstrip() for l in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"))


def _dialect_slice(text, start_marker, next_prefix):
    """取"从首个 `start_marker` 行 到 下一个 `next_prefix` 行（不含）"的切片；找不到 ⇒ None。"""
    lines = _dialect_norm(text).split("\n")
    i = next((k for k, l in enumerate(lines) if l.startswith(start_marker)), None)
    if i is None:
        return None
    j = next((k for k in range(i + 1, len(lines)) if lines[k].startswith(next_prefix)), len(lines))
    return "\n".join(lines[i:j])


def validate_dialect(inv, read_text_fn, exists_fn, reg):
    """**纯函数** → `(bad, notes)`（离线可正反夹测，见 tests/test_rpc_check_dialect.py）。

    规则：① 轴是封闭枚举；★★ **命名空间白名单来自 `reg`（注册表），不再来自本文件**
             —— `U1#5`（2026-10-01）：取值域的真值唯一在 `inventory/namespaces.yaml`，本文件只是消费者；
          ② 每行映射的前缀必填；③ `coverage` 与实际行数**双向**相等（漏一行、多一行都红）；
          ④ `sources` 的 path 必须存在，且**复算指纹**必须与登记一致（源变 ⇒ 下游红）。
    """
    bad, notes = [], []
    if not isinstance(inv, dict):
        return ["dialect.yaml 顶层不是映射（结构改了？）"], notes

    # ── ① 轴 ────────────────────────────────────────────────────────────
    axis = inv.get("axis") or {}
    axis_id = axis.get("id")
    values = axis.get("values") or []
    vids = [v.get("id") for v in values if isinstance(v, dict)]
    if not axis_id:
        bad.append("`axis.id` 缺失")
    if not values:
        bad.append("`axis.values` 为空 ⇒ 字典没有轴（“单一轴字典”名不副实）")
    if len(vids) != len(set(vids)):
        bad.append(f"`axis.values` 的 id 有重复: {vids}")
    for v in values:
        if not (isinstance(v, dict) and v.get("id") and v.get("label")):
            bad.append(f"`axis.values` 有条目缺 id/label: {v!r}")

    # ── ② 命名空间白名单（前缀必填的值域）—— ★ `U1#5`：**从注册表读**，不从本文件读 ──
    #    ⚠ 只认 `status: active` 的 **canonical id**（alias 不许写进映射行 —— 同身份那条理由：
    #      "同一事实两处表达"的代价最大的一种就是别名放行 ⇒ 一个东西两个名字）。
    _by_id, _a2i = namespace_index(reg)
    ns_ids = [k for k, v in _by_id.items() if (v or {}).get("status") == "active"]
    if not ns_ids:
        bad.append("命名空间注册表 `inventory/namespaces.yaml` 里**没有 active 条目** ⇒ 「前缀必填」没有值域可查")

    # ── ③ 映射表 ────────────────────────────────────────────────────────
    mapping = inv.get("mapping") or []
    if not mapping:
        bad.append("`mapping` 为空 ⇒ 映射表不存在")
    seen_pair = {}
    for i, row in enumerate(mapping, 1):
        if not isinstance(row, dict):
            bad.append(f"`mapping[{i}]` 不是映射")
            continue
        ns, sym = row.get("namespace"), row.get("symbol")
        if not ns:
            bad.append(f"`mapping[{i}]` 缺 `namespace`（★ 前缀是**必填字段**，§11.4 教训①）")
        elif ns_ids and ns not in ns_ids:
            bad.append(f"`mapping[{i}]` 的 namespace={ns!r} **不在命名空间注册表"
                       f"（`inventory/namespaces.yaml`）的 active 白名单**里")
        if not sym:
            bad.append(f"`mapping[{i}]` 缺 `symbol`")
        if (ns, sym) in seen_pair:
            bad.append(f"`mapping[{i}]` ({ns}, {sym}) 与第 {seen_pair[(ns, sym)]} 行重复 "
                       f"⇒ 同一符号同一出处两处定义（本仓头号形态）")
        else:
            seen_pair[(ns, sym)] = i
        if row.get("relation") not in DIALECT_RELATIONS:
            bad.append(f"`mapping[{i}]` relation={row.get('relation')!r} 不在封闭枚举 {sorted(DIALECT_RELATIONS)}")
        ax = row.get("axis")
        if ax not in DIALECT_AXES:
            bad.append(f"`mapping[{i}]` axis={ax!r} 不在封闭枚举 {sorted(DIALECT_AXES)}")
            continue
        av, note = row.get("axis_value"), row.get("axis_note")
        if ax == "evidence-strength":
            if not av:
                bad.append(f"`mapping[{i}]` axis=evidence-strength 但缺 `axis_value`")
            elif av == DIALECT_UNKNOWN:
                if not note:
                    bad.append(f"`mapping[{i}]` axis_value=undefined **必须**写 `axis_note` 说明为何不可判 "
                               f"（不许“看着像就填”）")
            elif vids and av not in vids:
                bad.append(f"`mapping[{i}]` axis_value={av!r} 不在 `axis.values` 的 id 里")
        else:                                    # not-assigned
            if av not in (None, ""):
                bad.append(f"`mapping[{i}]` axis=not-assigned 却给了 `axis_value={av!r}` "
                           f"⇒ 既说不属此轴、又给了取值（自相矛盾）")
            if not note:
                bad.append(f"`mapping[{i}]` axis=not-assigned **必须**写 `axis_note`（说明它属于什么轴）")

    # ── ④ 覆盖对账（**双向**：漏行/多行都红）────────────────────────────
    cov = inv.get("coverage") or []
    if not cov:
        bad.append("`coverage` 缺失 ⇒ 没有“有没有漏项”的判据（`b1b` 漏过一行，正因缺这一段）")
    actual = {}
    for row in mapping:
        if isinstance(row, dict) and row.get("family"):
            actual[row["family"]] = actual.get(row["family"], 0) + 1
    for c in cov:
        if not isinstance(c, dict):
            bad.append(f"`coverage` 有条目不是映射: {c!r}")
            continue
        fam, want = c.get("family"), c.get("expected_rows")
        got = actual.get(fam, 0)
        if got != want:
            bad.append(f"`coverage` 不符: family={fam!r} 期望 {want} 行, 实际 {got} 行 "
                       f"⇒ 映射表**漏项**或 `coverage` 过期（两者必改其一）")
    for fam in sorted(set(actual) - {c.get("family") for c in cov if isinstance(c, dict)}):
        bad.append(f"`mapping` 里的 family={fam!r} 未在 `coverage` 登记 ⇒ 新增族没报行数")
    notes.append(f"映射 {len(mapping)} 行 / {len(actual)} 族")

    # ── ⑤ 冲突清单 / 不可判项（各自非空）─────────────────────────────────
    for key, need in (("conflicts", ("symbol", "sides", "why")), ("undecidable", ("item", "missing"))):
        items = inv.get(key) or []
        if not items:
            bad.append(f"`{key}` 为空 —— 这两节是“不许硬塞 / 不许猜”的落地处，空 = 没做")
            continue
        for i, it in enumerate(items, 1):
            if not isinstance(it, dict) or any(not it.get(f) for f in need):
                bad.append(f"`{key}[{i}]` 缺字段（须全有 {list(need)}）: {it!r}")
    notes.append(f"冲突 {len(inv.get('conflicts') or [])} 条 · 不可判 {len(inv.get('undecidable') or [])} 条")

    # ── ⑥ 源词表指纹（D7-P1-1 退出判据的「源词表变了下游红」）────────────
    srcs = inv.get("sources") or []
    if not srcs:
        bad.append("`sources` 为空 ⇒ 没有“源词表变了要红”的对象")
    n_ok = 0
    for s in srcs:
        if not isinstance(s, dict):
            bad.append(f"`sources` 有条目不是映射: {s!r}")
            continue
        p, want = s.get("path"), s.get("sha256")
        tag = s.get("id") or p
        if not p or not want:
            bad.append(f"`sources[{tag}]` 缺 path 或 sha256")
            continue
        if not exists_fn(p):
            bad.append(f"`sources[{tag}]` 的 path 不存在: {p} ⇒ 登记指向空物")
            continue
        try:
            text = read_text_fn(p)
        except Exception as e:                      # ⚠ 不静默跳过：读不到就是"判不了"，必须显式报
            bad.append(f"`sources[{tag}]` 读取失败（{type(e).__name__}）⇒ 本项**不可判**，"
                       f"不得当作通过: {p}")
            continue
        if s.get("whole_file"):
            got = hashlib.sha256(_dialect_norm(text).encode("utf-8")).hexdigest()
        else:
            sl = _dialect_slice(text, s.get("slice_start") or "", s.get("slice_next_prefix") or "# ")
            if sl is None:
                bad.append(f"`sources[{tag}]` 切片起点 {s.get('slice_start')!r} 在 {p} 里找不到 "
                           f"⇒ 结构改了（判据前提失效）")
                continue
            got = hashlib.sha256(sl.encode("utf-8")).hexdigest()
        if got != want:
            bad.append(f"`sources[{tag}]` **指纹不符** ⇒ 源词表变了下游没重抽。"
                       f"登记 {want[:12]}… / 实算 {got[:12]}… ⇒ 重抽映射表并更新 `sources[].sha256`")
        else:
            n_ok += 1
    notes.append(f"源 {len(srcs)} 处 · 指纹一致 {n_ok}")
    return bad, notes


def check_dialect(ctx):
    """D7-P1-1: U-2 证据强度字典 + 方言映射表（`inventory/dialect.yaml`）。"""
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 dialect 字典断言", []
    if not DIALECT_INV.exists():
        return "FAIL", "inventory/dialect.yaml 缺失（本断言的登记依据）", []
    try:
        inv = yaml.safe_load(DIALECT_INV.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return "FAIL", f"inventory/dialect.yaml 解析失败: {type(e).__name__}: {e}", []

    # ★ `U1#5`（2026-10-01）：白名单改从**注册表**读 —— 它是取值域的真值，本文件只是消费者。
    #   ⚠ 注册表缺失/不可解析 ⇒ **FAIL**（不是跳过）：白名单是本条判据的**值域**，没有它映射行无从判。
    if not NAMESPACE_REG.is_file():
        return "FAIL", "inventory/namespaces.yaml 缺失（`U1#5` 起它是命名空间取值域的唯一真值）", []
    try:
        reg = yaml.safe_load(NAMESPACE_REG.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return "FAIL", f"inventory/namespaces.yaml 解析失败: {type(e).__name__}: {e}", []
    ns_bad, ns_notes = validate_namespaces(reg)
    if ns_bad:
        return "FAIL", "命名空间注册表自身不自洽（见明细）", ns_bad

    def _read(rel):
        return (ROOT / rel).read_text(encoding="utf-8", errors="replace")

    bad, notes = validate_dialect(inv, _read, lambda rel: (ROOT / rel).exists(), reg)
    return ("FAIL" if bad else "PASS"), " · ".join(notes + ns_notes), bad


# ── D7-P1-3 (2026-09-26)：U-3 依赖边格式（`inventory/edges.yaml`）────────────
# 目的：统一基座的**边**要有**唯一形状**（`src`/`dst`/`kind`/`provenance`），
#   而最该被机器盯住的是那个**最容易缺**的字段 —— Ontoly RFC-0002 的 invariant 原文：
#     **"Edges SHOULD contain provenance. Edges without provenance are invalid."**
# ★ `provenance` 缺 ⇒ 边**无效**：这是 D7-P1-3 退出判据里"可机判"那一半。
# ★ 本仓当前是**产出方**（不是消费方）⇒ 无效边的处置**不是"丢弃继续"**，而是 **FAIL** ——
#   依据 **D-26**「H-3 的降级必须有机判呈现位、**禁止静默 skip**」：
#   丢掉一条边 = 把一次"判不了"悄悄变成"没有这条边"。（消费方那一侧才走 H-3 强制降级。）
# ★ **空清单 ≠ 没事**：`edges` 为空时**不 FAIL**，但**必须**给出 `empty_reason`，
#   并在 note 里**显式报"0 条"** —— 否则"没有对象"会被读成"一切正常"（本仓头号形态）。
# ★ `src`/`dst` 必须是 **U-1 产物身份**形态 ⇒ 本断言把 U-1 与 U-3 **咬合**在一起：
#   写一条边就得先有一个合规身份（这正是 `edges.yaml` 现在为空的原因，见其 `empty_reason`）。
EDGES_INV = ROOT / "inventory" / "edges.yaml"
EDGE_REQUIRED = ("src", "dst", "kind", "provenance")
# ── U-1 产物身份：**本仓唯一真值实现**（D-23 / D-25 · `spec/d6-agent-standard/U1-ARTIFACT-IDENTITY.md`）──
# ★ 为什么实现放这里：此前门禁 `edges` 用**正则**判 U-1 形态，而规范里"取值维度 / 截断 / 前缀 / 算法"
#   是**四项取值** ⇒ 两处各写一份 ⇒ 必然漂移（本仓头号形态："同一事实两个定义点"）。
#   ⇒ 实现与校验**同源**：`edges` 改调 `u1_parse`，`u1-identity` 用它**复算**。
U1_ALGO = "sha256"
U1_TRUNC = 32                 # 128 bit。★ **2026-09-26 Scott 裁定：改 `32`（对齐蓝本）** —— 原为 16。
                              #   `16` 的原理由（"既有 7 处里 `factor_pipeline` 同为 16 ⇒ 兼容面最大"）
                              #   **已被两轮自查实测推翻**（见 O-84）：
                              #     · `factor_pipeline` 实测（口径化后 = **21 行**，见 `ops/id_site_census.py`）
                              #       截断**项目内并存 5 种**
                              #       （`[:8]` / `[:12]` / `[:16]` / `[:32]` / md5 **全 64**）⇒ **并非"同为 16"**；
                              #     · `Auto_Prover` 的 `verdict_id` 根本不是 16（= `v_` + md5 + **12**）
                              #       ⇒ 原依据的另一半是**把 `case_id` 与 `verdict_id` 读成了一个字段**。
                              #   ⇒ 剩下的唯一硬依据是**蓝本**：D-23 明裁"蓝本取 `Open_Data`"，而它是 **`[:32]`**
                              #     （`collectors/{blackmarble,portwatch,eia}/collector.py` 的
                              #      `sha256("ns|d1|d2")[:32]` —— 3 处逐行核过）
                              #     ⇒ "与权威蓝本一致"优先于"与某个**待迁移**的下游项目部分一致"。
                              #   ⚠ 代价（已履行）：本仓已落地的 2 个 `u1:` 声明**一并重算** ——
                              #     D-23 的"不追溯重算"只针对**历史产物**；这 2 个是**规范自身的元数据**，
                              #     且**从未被任何外部消费** ⇒ 重算无副作用（若已外发过，就必须另立兼容路径）。
                              #   128 bit ⇒ 碰撞阈值 ≈ 2⁶⁴，比 16（≈ 2³²）**强**，代价只是 ID 长一倍。
U1_PREFIX = f"u1:{U1_ALGO}:{U1_TRUNC}"
U1_DEFAULT_VERSION = "0.0.0"  # 无版本者（spec §1.3）
# ── ★★ `U1#8`（2026-09-30 裁 / `O-123`）：**截断长度变更的映射表**（唯一真值源 = 本表；规范只指向它，不复述）──
# 背景：上面对 `U1_TRUNC` 的注释自己写着「这 2 个身份**从未被任何外部消费** ⇒ 重算无副作用
#   （**若已外发过，就必须另立兼容路径**）」—— **本表就是那条兼容路径**（把"永不改长度"这条口头纪律换成判据）。
# ⚠ **只登记真实发生过的那一次**（`16 → 32`，`O-84`，2026-09-26）；**不预置没发生的行**（预置 = 编历史）。
U1_TRUNC_MAP = (
    {"from_length": 16, "to_length": U1_TRUNC, "algorithm": U1_ALGO, "effective_date": "2026-09-26"},
)
# "旧代"标注的**字段名唯一字面定义点**（声明里带它 = 承认这是历史长度的身份）
U1_LEGACY_MARK = "legacy"


def _u1_prefix(trunc):
    """`u1:<algo>:<trunc>` —— **唯一**拼前缀的地方（历史长度复算也要用同一处拼法）。"""
    return f"u1:{U1_ALGO}:{trunc}"


def u1_canonical_bytes(namespace, identifier, version=U1_DEFAULT_VERSION) -> bytes:
    """U-1 的**哈希输入**：`["<ns>","<id>","<ver>"]` 的 RFC 8785 规范化 JSON 的 UTF-8 字节序列。

    ⚠⚠ **等价性边界（只在这一形状上声称，别外推）**：本实现用
      `json.dumps(..., ensure_ascii=False, separators=(',',':'))`，它与 RFC 8785（JCS）
      在本规范的输入形状 **`[str, str, str]`** 上等价：
        ① 无空白（`separators` 收紧）；
        ② 字符串转义只用 `\\b \\t \\n \\f \\r \\" \\\\` 与 `\\uXXXX`（**小写** hex）—— 这正是 JCS 对**字符串**的规定。
      ⚠ 本实现**不涉及** JCS 里更复杂的部分（数字的 ECMAScript 序列化、键的 UTF-16 排序）
        ⇒ 那两项**既不实现、也不声称**（输入已被限定为**字符串数组** ⇒ 用不到）。
      ⇒ 若将来有人把数字 / 字典塞进来，**先读这段**：那时它就不再是 JCS 了。
    """
    arr = [str(namespace), str(identifier), str(version)]
    return json.dumps(arr, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def u1_identity(namespace, identifier, version=U1_DEFAULT_VERSION, trunc=U1_TRUNC) -> str:
    """算出一个**合规的 U-1 产物身份**（形态 = `u1:<algo>:<trunc>` + `:` + `trunc` 位小写 hex）。

    ⚠ 取值（算法 / 截断）**只在本文件定义一次** ⇒ 这里**不重抄数字**（抄了就是第二个定义点）。
    ⚠ `trunc` 参数**只为** `U1#8` 的**历史长度复算**而存在（本函数每天都在 `U1_TRUNC` 上被调用，日常**不传**它）。
    """
    h = hashlib.sha256(u1_canonical_bytes(namespace, identifier, version)).hexdigest()[:trunc]
    return f"{_u1_prefix(trunc)}:{h}"


def u1_classify(identity, decl=None):
    """★★ `U1#8`（2026-09-30 裁 / `O-123`）：把身份串分类 ⇒ `(kind, info, reason)`。

    `kind` ∈ `('current', 'legacy', None)`：
      · `current` —— 前缀长度 = 当前 `U1_TRUNC` 且自描述一致（与 `u1_parse` 同口径）
      · `legacy`  —— 长度命中 `U1_TRUNC_MAP` 的 `from_length`，**且**声明里有"旧代"标注（`U1_LEGACY_MARK`）
      · `None`    —— 不合规（`reason` 给理由）

    ★ 两阶段（裁里的配套纪律，逐条落地）：
      ① **无"旧代"标注 ⇒ 【拒绝】**（**不是警告** —— 旧实现连"检测"都没有：它只会以格式为由静默失败，
         于是"该失败的旧身份"与"随手编的乱串"**同一种表现** ⇒ 无从区分）；
      ② **有标注 ⇒ 接受**，且 `info` **携带"旧代"标记**（`from_length`/`to_length`/`effective_date`），
         供消费方**自行降级**（= 结果里带得走的信息，而不是一句口头约定）。
    """
    if not isinstance(identity, str):
        return None, None, "身份不是字符串"
    m = re.match(r"^u1:([a-z0-9]+):(\d+):([0-9a-f]+)$", identity)
    if not m:
        return None, None, f"身份形态不合规（应形如 `{U1_PREFIX}:<{U1_TRUNC} 位小写 hex>`）: {identity!r}"
    algo, trunc, h = m.group(1), int(m.group(2)), m.group(3)
    if algo != U1_ALGO or len(h) != trunc:
        return None, None, (f"前缀自描述与实现不一致（algo={algo!r} 长度 {len(h)} ≠ 前缀写的 {trunc}）: {identity!r}")
    if trunc == U1_TRUNC:
        return "current", {"trunc": trunc, "legacy": False}, ""
    row = next((r for r in U1_TRUNC_MAP if r["from_length"] == trunc and r["algorithm"] == algo), None)
    if row is None:
        return None, None, (f"**从未作为 U-1 长度**的取值 `{trunc}`（也不在 `U1_TRUNC_MAP` 里）⇒ 拒收: {identity!r}")
    marked = bool(isinstance(decl, dict) and decl.get(U1_LEGACY_MARK))
    if not marked:
        return None, None, (f"★ 检测到**历史截断长度** `{trunc}`（现为 `{U1_TRUNC}`）**但声明缺「旧代」标注**"
                            f"（`{U1_LEGACY_MARK}`）⇒ **拒绝**（不是警告）：不标注会让旧身份被静默接受，"
                            f"标注则让结果携带旧代号、消费方可自行降级")
    info = {"trunc": trunc, "legacy": True, "from_length": row["from_length"],
            "to_length": row["to_length"], "effective_date": row["effective_date"]}
    return "legacy", info, ""


def u1_parse(s):
    """校验一个 U-1 身份字符串 ⇒ 返回 `(algo, trunc)`；不合规返回 `None`。

    ★ 判据里**唯一有信息量**的那部分 = **前缀自描述必须与实现一致**：
      前缀写的长度就得真的等于 hex 位数、写的算法就得是我们用的那个、hex 必须小写。
      ⇒ 若只判"有个 `u1:` 前缀"，那 D-25 的"前缀必须自描述"就退化成**装饰**。
    ⚠ 哈希**不可逆** ⇒ 本函数**只能**判形态与自描述一致性，**不能**判"这个身份是不是某个
      `(ns,id,ver)` 算出来的" —— 后者**必须**靠"声明 + 复算"（`u1_verify_declaration`）。
      （把这两件事混起来的后果是：任何人随手编一个**合规长度**的 hex 都能过。）
    """
    if not isinstance(s, str):
        return None
    m = re.match(r"^u1:([a-z0-9]+):(\d+):([0-9a-f]+)$", s)
    if not m:
        return None
    algo, trunc, h = m.group(1), int(m.group(2)), m.group(3)
    if algo != U1_ALGO or trunc != U1_TRUNC or len(h) != trunc:
        return None
    return algo, trunc


def u1_legacy_marker(decl):
    """★ `U1#8` ②：声明若是**旧代**（历史截断长度 + 带标注）⇒ 返回"旧代"标记；否则 `None`。

    供消费方**自行降级**用（标记 = `from_length`/`to_length`/`effective_date` —— 与 `U1_TRUNC_MAP` 同源）。
    """
    kind, info, _ = u1_classify((decl or {}).get("identity"), decl)
    return info if kind == "legacy" else None


def u1_verify_declaration(decl):
    """复算一个 `u1:` **声明**（`{namespace, identifier, version, identity}`）⇒ 返回错误串，或 `None` 表示通过。

    ★ 这才是"身份"这个词**唯一可判的含义**：身份不是一句自述，而是**能从 `(ns,id,ver)` 复算出来**。
      ⇒ 只判格式是**假绿**（编个 16 位 hex 就能过）；本条把"可复算"变成判据。
    ★★ **`U1#8`（2026-09-30 裁 / `O-123`）**：**历史截断长度**（`U1_TRUNC_MAP`）**必须带"旧代"标注**
      ⇒ 无标注**拒**（不是警告）；有标注 ⇒ 接受，但**结果携带旧代标记**（`u1_legacy_marker()`）。
    """
    if not isinstance(decl, dict):
        return "`u1` 必须是映射（namespace / identifier / version / identity）"
    miss = [k for k in ("namespace", "identifier", "version", "identity") if not decl.get(k)]
    if miss:
        return f"`u1` 缺字段: {miss} —— 四项都要写（只写 identity 就**无法复算**，那正是本条要防的）"
    # ★★ `U1#8`（2026-09-30 裁）：本行的旧写法是 `u1_parse(...) is None` ⇒ 历史长度会被**以格式为由**拦下
    #   （= 与"随手编的乱串"**同一种表现**，无从区分）。现改走 `u1_classify`：**历史长度只认"带旧代标注"的**，
    #   且**换把尺子再核一遍**（用历史长度复算）—— 即"接受"不等于"放行"，只是**兼容路径**。
    kind, info, why = u1_classify(decl["identity"], decl)
    if kind is None:
        return why
    want = u1_identity(decl["namespace"], decl["identifier"], decl["version"], trunc=info["trunc"])
    if want != decl["identity"]:
        return (f"`u1.identity` **复算不符** ⇒ 声明与取值自相矛盾："
                f"声明 {decl['identity']!r}；按 namespace={decl['namespace']!r} · "
                f"identifier={decl['identifier']!r} · version={decl['version']!r} 复算得 {want!r}")
    return None


U1_DECL_SCAN_DIR = ROOT / "inventory"
U1_HEADER_RE = re.compile(r"^#\s*u1:sha256:\d+\s*$")
# 与 U3-EDGE-FORMAT.md §4.2 的"视为缺"第 5 条同表
EDGE_DEAD_PROV = {"unknown", "none", "n/a", "null"}


def edge_provenance_invalid(prov, prefixes):
    """`(是否无效, 原因)` —— 按 `spec/d6-agent-standard/U3-EDGE-FORMAT.md` §4.1 的七条。

    ⚠ 切分**只按第一个 `:`** ⇒ 载荷**允许**含 `:`（`filetrack:v1:in=a,out=b` 是合法的）。
      这条是刻意留的：产物初稿既写"载荷禁含未转义 `:`"、又给了四条含 `:` 的示例 —— 自相矛盾。
    """
    if prov is None:
        return True, "字段不存在"
    if not isinstance(prov, str):
        return True, f"不是字符串（{type(prov).__name__}）"
    if prov == "":
        return True, "空串"
    if prov.strip() == "":
        return True, "仅含空白"
    if prov.strip().lower() in EDGE_DEAD_PROV:
        return True, f"命中禁用词 {prov.strip()!r}"
    if ":" not in prov:
        return True, "缺 `<前缀>:<载荷>` 形式"
    pref, _, payload = prov.partition(":")
    if prefixes and pref not in prefixes:
        return True, f"前缀 {pref!r} 不在封闭集 {sorted(prefixes)}"
    if payload.strip() == "":
        return True, "载荷为空（有前缀没有内容）"
    return False, ""


def validate_edges(doc):
    """**纯函数** → `(bad, notes)`（离线可正反夹测，见 tests/test_rpc_check_edges.py）。"""
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["edges.yaml 顶层不是映射（结构改了？）"], notes

    kinds = doc.get("kinds") or []
    prefixes = doc.get("provenance_prefixes") or []
    if not kinds:
        bad.append("`kinds` 为空 ⇒ `kind` 没有封闭枚举可判（凭常识补的 kind 会静默通过）")
    if len(kinds) != len(set(kinds)):
        bad.append(f"`kinds` 有重复项: {kinds}")
    if not prefixes:
        bad.append("`provenance_prefixes` 为空 ⇒ `provenance` 没有封闭集可判")
    if len(prefixes) != len(set(prefixes)):
        bad.append(f"`provenance_prefixes` 有重复项: {prefixes}")

    if "edges" not in doc:
        bad.append("**缺 `edges` 字段** ⇒ 无法区分「清单为空」与「忘了写」（空必须显式）")
        return bad, notes
    edges = doc["edges"] or []
    if not isinstance(edges, list):
        bad.append(f"`edges` 不是列表（{type(edges).__name__}）")
        return bad, notes

    seen, n_invalid = {}, 0
    for i, e in enumerate(edges, 1):
        if not isinstance(e, dict):
            bad.append(f"`edges[{i}]` 不是映射")
            n_invalid += 1
            continue
        miss = [f for f in EDGE_REQUIRED if not e.get(f)]
        if miss:
            bad.append(f"`edges[{i}]` **缺字段** {miss} ⇒ 该边无效（★ 产出方**不许写出**无效边）")
            n_invalid += 1
            continue
        for f in ("src", "dst"):
            if u1_parse(e[f]) is None:
                bad.append(f"`edges[{i}].{f}` 不是 U-1 产物身份形态 `{U1_PREFIX}:<{U1_TRUNC} 位小写 hex>`: {e[f]!r} "
                           f"（判据 = `u1_parse`，与 U-1 实现**同源** —— 此前这里另写了一份正则 = 同一事实两个定义点）"
                           f"⇒ 「边指向谁」没有唯一答案（U-1 与 U-3 必须咬合）")
                n_invalid += 1
        if kinds and e["kind"] not in kinds:
            bad.append(f"`edges[{i}].kind`={e['kind']!r} 不在 `kinds` 封闭枚举里")
            n_invalid += 1
        inv, why = edge_provenance_invalid(e.get("provenance"), set(prefixes))
        if inv:
            bad.append(f"`edges[{i}].provenance` **无效**（{why}）⇒ 该边**无效**。"
                       f"⚠ 产出方的处置是 **FAIL**，不是「丢掉这条边继续」—— 依据 D-26「禁止静默 skip」；"
                       f"「丢弃 / 降级」是**消费方**那一侧的规则（H-3）")
            n_invalid += 1
        key = (e.get("src"), e.get("dst"), e.get("kind"))
        if key in seen:
            bad.append(f"`edges[{i}]` 与第 {seen[key]} 行重复 (src,dst,kind) ⇒ 同一事实两处定义")
        else:
            seen[key] = i

    if not edges:
        why = str(doc.get("empty_reason") or "").strip()
        if not why:
            bad.append("`edges` 为空**且没有 `empty_reason`** ⇒ 空得没说法"
                       "（空 ≠ 没事：必须写明“为什么空”，否则会被读成“一切正常”）")
        else:
            notes.append("清单为空已显式报出 (不静默通过; empty_reason 已给)")
    notes.append(f"边 {len(edges)} 条 · 无效 {n_invalid} 条 · kind {len(kinds)} 项 · 前缀 {len(prefixes)} 项")
    return bad, notes


def check_edges(ctx):
    """D7-P1-3: U-3 依赖边清单（`inventory/edges.yaml`）。"""
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 edges 边格式断言", []
    if not EDGES_INV.exists():
        return "FAIL", "inventory/edges.yaml 缺失（本断言的登记依据）", []
    try:
        doc = yaml.safe_load(EDGES_INV.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return "FAIL", f"inventory/edges.yaml 解析失败: {type(e).__name__}: {e}", []
    bad, notes = validate_edges(doc)
    return ("FAIL" if bad else "PASS"), " · ".join(notes), bad


def check_id_census(ctx):
    """O-85: 让"ID 站点计数"**可复算**（此前那一列没有口径 ⇒ 数字不可复现）。

    ★ 这条判据的对象不是"数字对不对"，而是**数字有没有定义** —— 它比对
      `inventory/id-site-census.yaml` 与 `ops/id_site_census.py` 的**当场复算**结果。
    ⚠ **项目目录不可达 ⇒ WARN（不是 FAIL）**：那些项目在**别的盘**（`F:` / `E:`），
      换一台机器就没有 ⇒ 硬红会把"我的环境"变成"仓库的规则"。
      但**必须可见**（D-26：降级要有呈现位）—— 所以报 `可达 N/M` + 逐项目标 `--`，
      **绝不静默通过**。
    ★★ **O-87（2026-09-26 补）：note 里列出"可达项目根清单"（`id@root`）** —— 理由：
      本仓两次"假缺口"（把"我没搜到"写成"它不存在"）都是**关于外部世界的存在性否定**，
      而**答案本来就在这张表里**（`Macro_Data` 一直在 `E:` 盘；Open_Data / Auto_Prover 的库一直在 `F:` 盘）。
      只报计数（"可达 10/10"）**不列名** ⇒ 写结论的人看不到 ⇒ 于是继续写假缺口。
      ⇒ 把清单**摆进每轮门禁输出**，让"它其实在 `F:`/`E:`"当场可见（把"我没搜到"从**隐性推论**
      变成**可见事实**的对账）。
    ⚠⚠ **射程（不许读过头）**：本判据**不判**"文档里的存在性结论是否为真" —— 那一半**不可能干净地文本机判**：
      「不存在」在规范文档里**有歧义** = **本仓没有实现/判据**（合法，且"未实测登记"节**必须**能这么写）
      vs **外部世界没有那个东西**（危险推论）⇒ 实测三次收窄**仍出假阳性**（13 → 2 → 仍含 1 条误报）
      ⇒ **已放弃文本扫描**，见 `DEV-LOG-014` §53.1。本判据只保证：**事实可见**，
      且**清单本身不会静默缺项**（某项目缺 `root` ⇒ FAIL）。
    """
    import importlib.util
    try:
        import yaml  # noqa: F401
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 id-census 断言", []
    script = ROOT / "ops" / "id_site_census.py"
    if not script.is_file():
        return "FAIL", "ops/id_site_census.py 缺失（本断言的登记依据）", []
    spec = importlib.util.spec_from_file_location("_id_site_census", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    doc = yaml.safe_load(mod.CENSUS.read_text(encoding="utf-8")) or {}
    m = doc.get("metric") or {}
    drift = []
    if m.get("name") != mod.METRIC_NAME:
        drift.append("name")
    if m.get("regex") != mod.METRIC_REGEX:
        drift.append("regex")
    for k, v in mod.scope().items():
        if m.get(k) != v:
            drift.append(k)

    now = {p["id"]: p for p in mod.census()}
    mism, unreach, ok = [], [], []
    for p in doc.get("projects") or []:
        cur = now.get(p["id"])
        if cur is None:
            continue
        if not cur.get("reachable"):
            unreach.append(p["id"])
        elif not p.get("reachable") or (p.get("hits"), p.get("files")) != (cur["hits"], cur["files"]):
            mism.append(f"{p['id']}: 真值 {p.get('hits')}行/{p.get('files')}文件 ≠ 实测 {cur['hits']}行/{cur['files']}文件")
        else:
            ok.append(p["id"])

    total = len(doc.get("projects") or [])
    # O-87：**可达项目根清单** —— 让"本机到底有什么"每轮可见（理由见 docstring）。
    #   缺 `root` 的项目会被**静默漏出**清单 ⇒ 可见性降级 ⇒ 故下面 fail-closed（不是只报数）。
    projs = doc.get("projects") or []
    missing_root = [str(p.get("id")) for p in projs if not p.get("root")]
    reach_roots = [f"{p['id']}@{p.get('root')}" for p in projs if p.get("reachable") and p.get("root")]
    note = (f"口径 {m.get('name')}（{m.get('unit')}）· 真值一致 {len(ok)} 个 · "
            f"不符 {len(mism)} 个 · 不可达 {len(unreach)}/{total} · "
            f"可达项目根 {len(reach_roots)} 个: " + " · ".join(reach_roots))
    if missing_root:
        note += f" · ⚠ 无 root {len(missing_root)} 个"
    if drift:
        # 口径漂移比数值漂移严重：口径一变，真值里所有数字立刻失去意义
        return "FAIL", note, [f"**口径已漂移**（真值是用旧口径生成的）: {drift} ⇒ 重跑 --emit 并复核下游结论"] + mism
    if missing_root:
        return "FAIL", note, [f"**项目根清单缺项**（`root` 缺失 ⇒ 该项**读不出可达性** ⇒ O-87 的可见化"
                              f"**静默降级**）: {', '.join(missing_root)} ⇒ 在 `inventory/id-site-census.yaml` 补 `root:`"]
    if mism:
        return "FAIL", note, mism
    if unreach:
        return "WARN", note, [f"不可达（本次无法复算，**不当作通过**）: {', '.join(unreach)}"]
    return "PASS", note, []


def check_id_storage(ctx):
    """U-4: **存储面**普查 —— `affected` 的**生产者**（此前是"开库手工数"）。

    ★ 判什么：
      ① **数值/形态**与真值一致（`inventory/id-storage-census.yaml`）；
      ② ★★ **声明的 `role` 必须回库里核过** —— 声明 `primary_key` 而实测不是 ⇒ **FAIL**
         （"声明 ≠ 事实"是这个脚本唯一能咬住自己的地方，也最容易被写成自说自话）；
      ③ **口径漂移**（形态档 / 取样上限 / role 取值域）⇒ 比数值不符**优先**判红。
    ⚠ 存储不可达 ⇒ **WARN 不 FAIL**（库在别的盘），但报 `不可达 N/M` ⇒ **不静默通过**（D-26）。
    """
    import importlib.util
    try:
        import yaml  # noqa: F401
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 id-storage 断言", []
    script = ROOT / "ops" / "id_storage_census.py"
    if not script.is_file():
        return "FAIL", "ops/id_storage_census.py 缺失（本断言的登记依据）", []
    spec = importlib.util.spec_from_file_location("_id_storage_census", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    doc = yaml.safe_load(mod.CENSUS.read_text(encoding="utf-8")) or {}
    m = doc.get("metric") or {}
    drift = []
    if m.get("shape_sample_limit") != mod.MAX_SHAPE_SAMPLE:
        drift.append("shape_sample_limit")
    if m.get("role_domain") != ["primary_key", "record_key"]:
        drift.append("role_domain")

    now = {(s["project"], s["path"], s["table"], s["column"]): s for s in mod.census()}
    mism, unreach, badrole, ok = [], [], [], 0
    for s in doc.get("stores") or []:
        cur = now.get((s["project"], s["path"], s["table"], s["column"]))
        if cur is None:
            continue
        if not cur.get("reachable"):
            unreach.append(f"{s['project']}.{s['column']}")
        elif s.get("declared_role") == "primary_key" and cur.get("is_primary_key") is not True:
            badrole.append(f"{s['project']}.{s['column']}: 声明 primary_key 但**库里不是**"
                           f"（实测 is_primary_key={cur.get('is_primary_key')}）")
        elif (s.get("rows"), s.get("distinct")) != (cur.get("rows"), cur.get("distinct")):
            mism.append(f"{s['project']}.{s['column']}: 真值 {s.get('rows')}行/{s.get('distinct')}distinct "
                        f"≠ 实测 {cur.get('rows')}行/{cur.get('distinct')}distinct")
        else:
            ok += 1
    total = len(doc.get("stores") or [])
    rows = sum(s.get("rows") or 0 for s in (doc.get("stores") or []) if s.get("reachable"))
    note = f"存储 {total} 处 · 一致 {ok} · 角色不实 {len(badrole)} · 不符 {len(mism)} · 不可达 {len(unreach)}/{total} · 存量 {rows} 行"
    if drift:
        return "FAIL", note, [f"**口径已漂移**: {drift} ⇒ 重跑 --emit 并复核下游结论"] + badrole + mism
    if badrole or mism:
        return "FAIL", note, badrole + mism
    if unreach:
        return "WARN", note, [f"不可达 ⇒ 本次 **affected 不完整**（可见，不静默）: {', '.join(unreach)}"]
    return "PASS", note, []


def check_u1_identity(ctx):
    """D7-P1 实现侧（U-1 落地）：`inventory/*.yaml` 的 **U-1 身份声明必须可复算**。

    ★ 判什么（按信息量从高到低）：
      ① **复算**：文件声明 `u1: {namespace, identifier, version, identity}` ⇒ 按前三项重算**必须**等于 identity。
         只判格式是**假绿**（随手编一个 16 位 hex 就能过）—— 而"身份"这个词可判的含义只有"能从 (ns,id,ver) 复算"。
      ② **头部注释前缀**：既然声明了身份 ⇒ 前 5 行内必须**同时**有 `# u1:sha256:<N>` 头部注释行
         （D-25：前缀进头部注释、不进哈希行；U1 spec §1.4 要求"每文件首行"）。
      ③ ★ **至少 1 个声明**：一个都没有 ⇒ 本条判据**没有对象** ⇒ 判红。
         （否则它会**静默退化**成空判 —— 正是本仓头号失败形态"判据什么都没判"。）
      ★★ ④ **`namespace` 必须落在取值域里**（`U1#5`，2026-10-01）—— 取值域的真值 =
         `inventory/namespaces.yaml`（注册表）；**只认 `status: active` 的 canonical id**
         （写 alias / retired / 未登记 ⇒ 拒）。⚠ 本条此前**不存在**：旧判据只复算，
         于是 `namespace: 任何字符串` 都能过 ⇒ D-25 的"前缀必填 + 取值域封闭"**只有前半句落地了**。
         同时顺带判**注册表自身自洽**（`validate_namespaces`）。
    """
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 u1-identity 断言", []
    if not U1_DECL_SCAN_DIR.is_dir():
        return "FAIL", "inventory/ 缺失（本断言的登记依据）", []
    # ★★ `U1#5` ④：取值域的真值 = 注册表；缺失/不自洽 ⇒ **FAIL**（不是跳过 —— 没有值域就无从判）
    if not NAMESPACE_REG.is_file():
        return "FAIL", "inventory/namespaces.yaml 缺失（`U1#5` 起它是 namespace 取值域的唯一真值）", []
    reg = yaml.safe_load(NAMESPACE_REG.read_text(encoding="utf-8")) or {}
    ns_bad, ns_notes = validate_namespaces(reg)
    if ns_bad:
        return "FAIL", "命名空间注册表自身不自洽（见明细）", ns_bad
    ns_note = " · ".join(ns_notes)
    bad, declared, ok_recalc = [], 0, 0
    for p in sorted(U1_DECL_SCAN_DIR.glob("*.yaml")):
        text = p.read_text(encoding="utf-8")
        try:
            doc = yaml.safe_load(text) or {}
        except Exception as e:
            bad.append(f"{p.name}: YAML 解析失败 {type(e).__name__}: {e}")
            continue
        decl = doc.get("u1") if isinstance(doc, dict) else None
        if decl is None:
            continue
        declared += 1
        err = u1_verify_declaration(decl)
        # ★ `U1#5` ④：取值域 —— 与复算**分开报**（复算过不了 ≠ 取值域不对，反之亦然）
        if not err:
            err = namespace_domain_error(decl.get("namespace"), reg)
        if err:
            bad.append(f"{p.name}: {err}")
        else:
            ok_recalc += 1
        if not any(U1_HEADER_RE.match(l) for l in text.splitlines()[:5]):
            bad.append(f"{p.name}: 有 `u1:` 身份声明，但**前 5 行内没有** `# u1:sha256:{U1_TRUNC}` 头部注释行"
                       f"（D-25：前缀进头部注释；U1 spec §1.4 要求每文件首行）")
    if declared == 0:
        bad.append("`inventory/*.yaml` 里**一个 `u1:` 身份声明都没有** ⇒ 本条判据**没有对象**（= 空判）⇒ 判红；"
                   "U-1 的落地以『至少一个可复算的声明』为可判形式")
    # ⚠ 这两个数**算出来**，不写死 —— 上一版我在这里硬编码了"复算 0 处不符"，
    #   那正是刚修掉的"标签在说谎"同族（标签比事实硬）。
    notes = (f"已声明 U-1 身份 {declared} 个 · 复算+值域通过 {ok_recalc} 个（扫描 inventory/*.yaml）"
             f" · {ns_note}")
    return ("FAIL" if bad else "PASS"), notes, bad


# ── D7-P1-4 (2026-09-26)：U-4 失效规则 H-1~H-4（**判据库**，不是门禁项）────────
# ⚠⚠ **本节不是 `CHECKS` 项** —— 它不判本仓的任何状态（本仓没有失效传播实现，九项目 **0/9**）。
#   它是**参考实现**：把四条 MUST 级规则写成**可执行判据**，供将来的失效传播实现调用/对照。
#   ⇒ 因此**它当前没有任何生产消费者**（这件事已如实登记在
#     `spec/d6-agent-standard/U4-INVALIDATION-RULES.md` 的末节，不假装已接）。
#   ⇒ 但 D7-P1 的批级判据要求"**通过先验红**"（方案 §7）⇒ 必须有可执行的判据 + 注入用例，
#     纯纸面表达式过不了那一条（`tests/test_rpc_check_u4.py`）。
#
# 依据（原文，Ontoly RFC-0002，RFC 2119 措辞）：
#   H-1 "Incremental builds MUST be clean-build equivalent."
#   H-2 "Dependency invalidation MUST be conservative."
#   H-3 "If affected regions cannot be determined safely, the compiler MUST broaden
#        invalidation or fall back to a clean build."   ← ★ 本批的核心
#   H-4 "A failed build MUST NOT partially overwrite the last valid canonical graph artifact."
# 已裁（台账）：D-26 四条全采（照 MUST 语义）· **只适用派生产物** · H-3 的"降级"必须有机判
#   呈现位（落进 D6-P0-1「非执行三分」，**禁止静默 skip**）；D-27 结构性事实须**可复算**才准入；
#   D-51 受理目录**不纳入**失效传播。
#
# ★ 与「非执行三分」的映射（这是 D-26 那句"必须有呈现位"的落地）：
#     · 确实**无变更** ⇒ `action=none` + **MODE_SKIP**（"调用方不给" —— 这是**真的没事**）
#     · **无法安全判定影响面** ⇒ `action=full_rebuild` + **WARN**（能力降级：保守全量，**可见、不阻断**）
#     · 增量等价性**未能证明** ⇒ `action=full_rebuild` + **WARN**（同上）
#     · 重算**失败** ⇒ `action=none` + **SKIP_FAILED**（**算失败**；不得部分覆盖 ⇒ 不落盘）
#   ⇒ **硬不变量**：任何"**判不了**"的情形都**不得**落到 `MODE_SKIP` ——
#     那正是"静默 skip"的形态（把"判不了"悄悄变成"没事"）。用例 `u4⑦` 专门钉这一条。
U4_ACTIONS = ("none", "incremental", "full_rebuild")
U4_CLASSES = (None, "MODE_SKIP", "SKIP_FAILED", "WARN")
# ── U-4 **执行侧**（2026-09-29，A6 / `U4-INVALIDATION-RULES.md` 未实测第 10 条）──────────────
U4_EXEC_STATUS = ("executed", "partial-failed", "not-executed", "no-op")
U4_ITEM_STATUS = ("success", "failed", "n/a")


def decide_invalidation(changed_ids=None, affected=None, affected_is_closure=False,
                        incremental_equivalent=None, build_failed=False):
    """U-4 的四条规则 → `(action, class, reason)`。

    参数（= 判据的**输入契约**；将来的实现只需提供这五个）：
      · `changed_ids`            上游变更集（**派生产物**；受理目录按 D-51 不在其内）
      · `affected`               影响面判定的**结果集**；`None` 表示**无法安全判定**（H-3 的触发条件）
        ⚠⚠ **`[]` 与 `None` 语义不同，别写成 `[...] or None`**（O-88，2026-09-26）：
        `[]` = "**已判定为空**"（下游确实为空 ⇒ 无动作，**不是**"判不了"）；
        `None` = "**判不了**"（⇒ H-3 强制全量）。
        写成 `affected or None` 会把"已知为空"错误升格成"判不了" ⇒ **白白付一次全量**。
      · `affected_is_closure`    该结果集是否**已传递闭包化**（H-2：必须保守 = 只许扩大）
      · `incremental_equivalent` 增量结果是否**已证**与全量等价；`None` = **未证**（H-1）
      · `build_failed`           本次重算是否失败（H-4）

    返回 `(action, class, reason)`；`class` 只在"未执行/降级"时给值（正常路径为 `None`）。
    """
    if not changed_ids:
        # 真的没有变更 ⇒ 这是**唯一**允许落到 MODE_SKIP 的情形
        return "none", "MODE_SKIP", "变更集为空：确实无需动作（不是「判不了」）"
    if build_failed:
        # H-4：失败不得部分覆盖 ⇒ 不落盘、不动上一份有效产物；且**算失败**
        return "none", "SKIP_FAILED", "H-4 重算失败 ⇒ 不得部分覆盖，保留上一份有效产物（算失败）"
    if affected is None:
        # H-3：无法安全判定 ⇒ 强制全量；**可见但不阻断**（WARN），绝不静默 skip
        return "full_rebuild", "WARN", "H-3 影响面无法安全判定 ⇒ 强制全量降级（可见，禁止静默 skip）"
    if not affected and affected_is_closure:
        # ★ O-88（2026-09-26）：**有变更、但影响面为空且已闭包化** = 已判定「**确实没有下游**」。
        #   ⇒ 既不需要增量、也不需要全量 —— **没有任何东西要重算**（DEV-LOG-014 §54）。
        #   为什么这是"已判定"而不是"判不了"：`affected` 是**列表**（`None` 才是判不了，见上一条），
        #     且调用方**显式声明**它已闭包化 ⇒ 与 `incremental_equivalent=True` 同族的**调用方断言**。
        #   ⚠ H-1 在此分支**不适用**：它的语义是"**增量**结果必须与全量等价"，而下游为空 ⇒ **没有增量**
        #     ⇒ 该维度**不存在**（旧实现把它算作"未证" ⇒ 白白付一次全量；改动前实测见 §54.1）。
        #   ⚠ 顺序：必须在 H-3（`None`）**之后**（`[]` ≠ `None`）、H-1 **之前**。
        return "none", "MODE_SKIP", ("有变更但影响面为空且已闭包化（= 已判定：确实无下游）⇒ 无动作"
                                     "（既不增量也不全量：没有下游要重算）")
    if incremental_equivalent is not True:
        # H-1：增量必须与全量等价；**未证**不等于"等价"（fail-closed）
        return "full_rebuild", "WARN", "H-1 增量等价性未证 ⇒ 不得用增量（付全量代价）"
    if not affected_is_closure:
        # H-2：失效必须保守 ⇒ 未闭包化的结果集只许扩大
        return "full_rebuild", "WARN", "H-2 影响面未闭包化 ⇒ 保守起见取全量（宁可多算）"
    return "incremental", None, "四条规则全过：可安全增量"


def execute_invalidation(action, class_, reason, affected=None, executors=None):
    """U-4 **执行侧**：把 `decide_invalidation()` 的决策落成一份**执行报告**（`A6`，2026-09-29）。

    ⚠ 与 `decide_invalidation` 同：**不是 CHECKS 项**（本仓没有可判的对象）。
    ⚠ 它**自己不重算** —— 重算由**注册表**里的执行器做；本仓与九项目 **0/9** ⇒ 调用方默认传**空注册表**
      ⇒ 有活时整体报 `not-executed`（**不适用，带理由**）—— **绝不**在无执行器时报成功（防假绿）。

    入参：
      · `action` / `class_` / `reason` = `decide_invalidation()` 的三元输出（**原样传入**，本函数不重算决策）
      · `affected` = 同一份结果集（**必须与决策同源**）；`None`/空 = 全量（`full_rebuild` 射程）
      · `executors` = `{action: callable}`；`callable(target) -> {"status": ..., "version": int|None, "detail": ...}`

    返回 dict（键名即契约）：
      · `status` ∈ `U4_EXEC_STATUS`（**封闭枚举**：`executed` / `partial-failed` / `not-executed` / `no-op`）
      · `items` = 逐项 `{"target", "status"(∈ U4_ITEM_STATUS), "detail"}`
      · `aggregate` = `{n_success, n_failed, n_na, version_monotonic}`

    ★ 防假绿硬约束（imp6 设计稿）：**整体成功**仅当
      「**所有受影响项均 `success`** ∧ 成功项 `version` **严格单调递增** ∧ 成功项数 > 0」；
      否则**一律** `partial-failed`（**禁报成功**）。⚠ 无动作（`action=none`）**不算**"执行成功" ⇒ 单列 `no-op`。
    """
    if action not in U4_ACTIONS:
        raise ValueError(f"action={action!r} 不在封闭枚举 {U4_ACTIONS}")
    if class_ not in U4_CLASSES:
        raise ValueError(f"class={class_!r} 不在封闭枚举 {U4_CLASSES}")

    rep = {"action": action, "class": class_, "reason": reason, "items": [],
           "aggregate": {"n_success": 0, "n_failed": 0, "n_na": 0, "version_monotonic": None}}

    if action == "none":
        # 三种 `action=none` 的决策**语义不同**，不能同档：`MODE_SKIP` = 无需动作；`SKIP_FAILED`(H-4) = **算失败**
        rep["status"] = "no-op" if class_ == "MODE_SKIP" else "partial-failed"
        return rep

    # 有活（incremental / full_rebuild）：先看有没有注册执行器 —— 没有就**整体未执行**（不假装）
    executors = executors or {}
    runner = executors.get(action)
    targets = list(affected) if affected else ["<全量>"]
    if runner is None:
        rep["items"] = [{"target": t, "status": "n/a", "detail": f"无注册执行器（action={action}）⇒ 未执行"}
                        for t in targets]
        rep["aggregate"]["n_na"] = len(targets)
        rep["status"] = "not-executed"
        return rep

    versions = []
    for t in targets:
        try:
            r = runner(t) or {}
        except Exception as e:                      # 执行器抛异常 = **算失败**（绝不静默吞）
            r = {"status": "failed", "detail": f"{type(e).__name__}: {e}"}
        st = r.get("status")
        if st not in U4_ITEM_STATUS:                # 非法/缺失状态 ⇒ 落失败（fail-closed）
            st = "failed"
            r = dict(r, detail=f"执行器返回非法状态 {r.get('status')!r} ⇒ 按失败处理")
        rep["items"].append({"target": t, "status": st, "detail": r.get("detail", "")})
        if st == "success":
            rep["aggregate"]["n_success"] += 1
            if isinstance(r.get("version"), int):
                versions.append(r["version"])
        elif st == "failed":
            rep["aggregate"]["n_failed"] += 1
        else:
            rep["aggregate"]["n_na"] += 1

    agg = rep["aggregate"]
    agg["version_monotonic"] = (all(a < b for a, b in zip(versions, versions[1:]))
                                if versions else None)
    agg["all_success"] = (agg["n_failed"] == 0 and agg["n_na"] == 0 and agg["n_success"] > 0)
    rep["status"] = ("executed" if (agg["all_success"] and agg["version_monotonic"] is True)
                     else "partial-failed")
    return rep


# ── ★ U-4 批 1（2026-09-30）：三条「已裁 + 实现待落地」落成**可机判纯函数** ─────────
# 来源 = `O-123` 的裁定 + 派工视图 `spec/d6-agent-standard/UNTESTED-TRIAGE-PLAN.md` §8 批 1。
# ★ **只实现裁定的方向，不重新裁定**：
#   #3 「自报位 `affected_is_closure`」⇒ **判定方独立重算**（主判据）+ **逐跳路径证据**（辅），
#      二者**不一致即拒收**（`verify_affected_closure`）
#   #4 「只适用派生产物」（D-26/D-51）⇒ **可核来源标记** / 显式非派生**硬拒** /
#      无标记**软警 + 审计**（灰度期；白名单 = 裁点名的「洗信号」避法）
#   #6 「以**证伪**替代**证明**」⇒ 测例集覆盖代数性质 + 反例清单**须含历史真实失效**
#      + 运行时抽样自检 + **可开增量白名单**（`check_falsification_suite` / `runtime_selfcheck`）
# ⚠ 三条**共用一个口径**：**「判不了」≠「通过」**（同 `O-22`/`O-119`）——
#   "取不到图查询面" / "抽样为空" 一律落 `boundary`/`inconclusive`/`insufficient`，
#   **绝不**落 `consistent`/`ok`（那正是本仓头号形态「静默变成没事」的入口）。
# ⚠ 与 `decide_invalidation` 同：**不是 CHECKS 项**（本仓没有可判的对象 ⇒ 不新增 gate id）。
U4_CLOSURE_VERDICTS = ("consistent", "inconsistent", "boundary")
U4_ORIGINS = ("derived", "non-derived")
U4_DERIVED_VERDICTS = ("ok", "soft-warn", "hard-reject")
U4_ALGEBRAIC_PROPS = ("boundary", "idempotence", "commutativity")
U4_FALSIFY_VERDICTS = ("ok", "insufficient", "blocked")
U4_SELFCHECK_VERDICTS = ("consistent", "mismatch", "inconclusive")


def _edge_pair(e):
    """边实例 → `(dependent, dependency)`；方向 = **`src` 依赖 `dst`**（照 `inventory/edges.yaml` 的约定）。

    ⚠ 该方向约定**尚未写进 U3 schema**（台账 `O-83` 已登记）⇒ 本函数把它**显式写在一处**，
      不留给下游各自理解（"同一事实两个定义点"是本仓头号形态）。
    """
    if isinstance(e, dict):
        return e.get("src"), e.get("dst")
    if isinstance(e, (list, tuple)) and len(e) == 2:
        return e[0], e[1]
    return None, None


def recompute_closure(changed_ids, edges):
    """★ `U4#3`：判定方**独立重算**影响面闭包（**主判据**）。

    方向：**`src` 依赖 `dst`** ⇒ 变了的是被依赖的一侧（`dst`）时，影响面 = **依赖它的 `src`**（反向遍历）。
    返回 `sorted(list)`；⚠ **不含** `changed_ids` 自身（那是变更集，不是影响面）。
    ⚠ `edges` 为 `None`/空 ⇒ 返回 `None` = **判不了**（**不是**"没有下游" —— 那个区分是本仓头号形态）。
    """
    if not edges:
        return None
    deps = {}                                        # dependency -> [dependents]
    for e in edges:
        dep, dty = _edge_pair(e)
        if dep is None or dty is None:
            continue
        deps.setdefault(dty, []).append(dep)
    seen, out = set(changed_ids or ()), set()
    stack = list(changed_ids or ())
    while stack:                                     # 反向 BFS：谁依赖它
        for d in deps.get(stack.pop(), ()):
            if d not in seen:
                seen.add(d)
                out.add(d)
                stack.append(d)
    return sorted(out)


def verify_affected_closure(changed_ids, affected, edges=None, hops=None):
    """★ `U4#3`：**双轨核验** —— 独立重算（主判据）+ 逐跳路径证据（辅）；**不一致即拒收**。

    返回 `(verdict, detail)`，`verdict ∈ U4_CLOSURE_VERDICTS`：
      · `consistent`   —— 重算结果与调用方 `affected` **逐项一致**（且路径证据无冲突）
      · `inconsistent` —— **拒收**（自报与重算不符 / 路径证据与图不符 —— 后者视为**伪造**）
      · `boundary`     —— **判不了**：① 取不到图查询面（`edges` 空）；② 图面与本域**无交集**
        （不同域 ⇒ 它不是能裁决本域的查询面）。照 `O-123` 的再触发条件，此时**反转为
        「登记为边界 + 事后抽检」**，**不算通过**。

    `hops` = 逐跳路径证据：`[[affected_id, ..., changed_id], ...]`（沿依赖方向**倒着走**：
    每一跳 `(p[i], p[i+1])` 须是图里的一条边 `src 依赖 dst`）。⚠ 它**只是辅** ——
    只在重算**通过**后才用来加严（重算过不了 ⇒ 直接 `inconsistent`，不看证据）。
    """
    if edges is None or not edges:
        return ("boundary", "取不到依赖图查询面（edges 为空/未提供）⇒ 按 `O-123` 反转为"
                            "「登记为边界 + 事后抽检」—— **不算通过**")
    nodes = {x for e in edges for x in _edge_pair(e) if x is not None}
    if (changed_ids or affected) and not (nodes & (set(changed_ids or ()) | set(affected or ()))):
        return ("boundary", "图查询面与本域**无交集**（不同域，如产物→产物 vs 产物→存储列）"
                            "⇒ 判不了闭包 ⇒ 登记边界 + 事后抽检（**不算通过**）")
    want = sorted(recompute_closure(changed_ids, edges) or ())
    got = sorted(set(affected or ()))
    if got != want:
        miss = [x for x in want if x not in got]
        extra = [x for x in got if x not in want]
        return ("inconsistent",
                f"自报 `affected`({len(got)}) 与判定方**独立重算**({len(want)}) 不一致 ⇒ **拒收**"
                f"（漏算 {miss[:5]} · 多算 {extra[:5]}）")
    if hops:
        pairs = {_edge_pair(e) for e in edges}
        ch, wa = set(changed_ids or ()), set(want)
        for path in hops:
            p = list(path or ())
            if len(p) < 2 or any((p[i], p[i + 1]) not in pairs for i in range(len(p) - 1)):
                return "inconsistent", f"逐跳路径证据与图不符（**伪造**）⇒ 拒收: {p[:6]}"
            if p[0] not in wa or p[-1] not in ch:
                return "inconsistent", f"路径端点不在 affected/changed 内 ⇒ 拒收: {p[:6]}"
    return "consistent", f"独立重算与自报逐项一致（{len(want)} 项）⇒ 闭包**已核验**"


def check_derived_boundary(items, whitelist=()):
    """★ `U4#4`：把「**只适用派生产物**」（D-26）落成**可机判形态**（含 D-51 的受理目录排除）。

    `items` 每项 = `str`（= 无标记）或 `dict`：`id` · `origin`(`U4_ORIGINS`) · `source`（**可核来源标记**，
    如 `hash:…` / `filetrack:…` / `tool:…`）。`whitelist` = **合法无标记产物**（`O-123` 点名的
    「**先建白名单**」避法 —— 防"一律驳回"把合法的无标记产物一起挡掉，即**洗信号**风险）。

    规则（照裁定逐条）：
      · 显式 **`non-derived`** ⇒ **`hard-reject`**（上游变更集只能指派生产物）
      · `derived` **且有** `source` ⇒ 计入 ok
      · **无标记**（缺 `origin` / `derived` 但无 `source`）⇒ 灰度期 **`soft-warn` + 审计**；
        在**白名单**内 ⇒ 放行（不告警）
    返回 `(verdict, hard, unmarked, notes)`；`verdict` 取**最重**的一档（hard > soft > ok）。
    ⚠ **已知边界（如实记）**：`origin`/`source` 仍是**调用方自报** —— 本判据只判"**有没有**可核标记"，
      **不判标记真假**（那要另一条链，未裁未做）。
    """
    hard, unmarked, notes = [], [], []
    wl = set(whitelist or ())
    for it in items or ():
        if isinstance(it, dict):
            iid, origin, src = it.get("id"), it.get("origin"), it.get("source")
        else:
            iid, origin, src = it, None, None
        if origin == "non-derived":
            hard.append(iid)
            notes.append(f"{iid}: 显式标为**非派生产物** ⇒ **硬拒**（D-26/D-51）")
        elif origin == "derived" and src:
            continue
        elif iid in wl:
            notes.append(f"{iid}: 无标记但在**白名单**内 ⇒ 放行（不告警）")
        else:
            unmarked.append(iid)
            notes.append(f"{iid}: **无可核来源标记** ⇒ 软警 + 审计（灰度期，收敛后收紧为硬拒）")
    if hard:
        return "hard-reject", hard, unmarked, notes
    if unmarked:
        return "soft-warn", hard, unmarked, notes
    return "ok", hard, unmarked, notes


def check_falsification_suite(cases, counterexamples, transform=None, whitelist=()):
    """★ `U4#6`：**以「证伪」替代「证明」**（不证 H-1 的"等价"，改证"**不等价会失败**"）。

    三件（照裁定逐条）：
      ① **测例集** `cases` = `[{"id":…, "prop": <boundary|idempotence|commutativity>}, …]`
         —— 三类**代数性质须全覆盖**（否则测例集不足以证伪）
      ② **反例清单** `counterexamples` = `[{"id":…, "historical": bool, "kind": "real-failure"}, …]`
         —— ★ 须含**至少一条「历史真实失效」**（凭空造的反例不算；"新失效必入"是纪律，机判不了）
      ③ **白名单** `whitelist` 限定**可开增量**的变换；`transform` 不在其中 ⇒ **`blocked`**
    返回 `(verdict, missing_props, notes)`，`verdict ∈ U4_FALSIFY_VERDICTS`。
    ⚠ `cases` 空 / 反例缺历史项 ⇒ `insufficient`（**不算通过**）。
    """
    props = {c.get("prop") for c in (cases or ()) if isinstance(c, dict)}
    missing = [p for p in U4_ALGEBRAIC_PROPS if p not in props]
    hist = [c for c in (counterexamples or ()) if isinstance(c, dict)
            and c.get("historical") and c.get("kind") == "real-failure"]
    notes = []
    if missing:
        notes.append(f"测例集未覆盖代数性质 {missing} ⇒ 不足以证伪")
    if not hist:
        notes.append("反例清单**没有**「历史真实失效」项 ⇒ 不足以证伪（凭空造的反例不算）")
    if missing or not hist:
        return "insufficient", missing, notes
    if transform is not None and transform not in set(whitelist or ()):
        notes.append(f"变换 {transform!r} 不在**可开增量白名单**内 ⇒ 不得开增量（blocked）")
        return "blocked", missing, notes
    return "ok", missing, notes


def runtime_selfcheck(sample_full, sample_incr):
    """★ `U4#6` ②：**运行时自检**（第二道防线）—— 增量前后在受影响子图上**抽样核全量**。

    `sample_full` / `sample_incr` = `{key: value}`。返回 `(verdict, detail)`：
      · `consistent`   —— 抽样逐键相等
      · `mismatch`     —— **不一致 ⇒ 增量结果不可信**（须回落全量）
      · `inconclusive` —— **抽样为空 ⇒ 判不了**（**不算通过**！"没抽到" ≠ "没问题"）
    """
    sf, si = dict(sample_full or {}), dict(sample_incr or {})
    if not sf and not si:
        return "inconclusive", "抽样为空 ⇒ 自检**判不了**（**不是通过**）"
    bad = [k for k in set(sf) | set(si) if sf.get(k) != si.get(k)]
    if bad:
        return "mismatch", f"抽样不一致 {sorted(bad)[:5]} ⇒ 增量结果**不可信**（回落全量）"
    return "consistent", f"抽样 {len(sf)} 项一致"


# ── ★ D7 协议契约（A 段 · 2026-10-01）：三信封 + 六相状态机 + 8 条纯函数拦截 ──────────
# 真值源 = `spec/d6-agent-standard/D7-PROTOCOL-CONTRACT.md`（**唯一**；本库**逐字照其 §1**）。
# 性质 = **纯函数判据库** —— 与 `decide_invalidation` / `verify_affected_closure` 同族：
#   **不是 CHECKS 项**、**不新增 gate id**（协议链路的对象在站上，本仓**零个真实信封**
#   ⇒ 眼下**没有可判的对象** ⇒ 只能判「**给一份信封 / 一次状态迁移 / 一次动作，它合法吗**」）。
# ★ 三段式定位（用户 2026-10-01 裁）：**A 离线契约化 → B 外壳接线 → C 站上真跑**。
#   A 段把"文档约束"变成"**可被机械拒绝的规则**" ⇒ B/C 段才有判据可接。本批 = **只做 A**。
# ⚠⚠ 与规范 §未实测 1–6 的关系（**如实，不冒充实测**）：A 段**不动**六相真跑那 6 条
#   （它们要真的站上跑，属 B/C）⇒ A 段只收口 **7 / 8 / 9**（三红线 / 三不变量 / 角色禁项）。
# ⚠ 契约自身的两处含糊在 A 段**已裁**（落回规范 §1.1 / §1.5）：① `verdict` 词义冲突；
#   ② §2 五行"依据不足"的处置 = **只判键在不在、不判内部结构**（射程到此为止，**不补齐**）。

# 六相状态名序列（§1 末行逐字）+ 出边（照 §1 表的"相 → 产出/动作"）。
D7_PHASES = ("drafted", "dispatched", "claimed", "executing", "collected",
             "mech_verified", "sem_verified", "accepted", "rejected")
D7_TERMINAL = ("accepted", "rejected")
D7_TRANSITIONS = {
    "drafted":       ("dispatched",),
    "dispatched":    ("claimed",),
    "claimed":       ("executing",),
    "executing":     ("collected",),
    "collected":     ("mech_verified",),
    # P4b 可选：`mech_verified` 既可进语义复核，也可**直接**裁决（跳过 P4b）
    "mech_verified": ("sem_verified", "accepted", "rejected"),
    "sem_verified":  ("accepted", "rejected"),
    "accepted":      (),
    "rejected":      (),
}
# §1 每相的"谁"⇒ 迁移的**驱动角色**（P1/P2/P3 由工作站，其余由主控站）。
D7_MASTER, D7_WORKER = "master", "worker"
D7_TRANSITION_ACTOR = {
    ("drafted", "dispatched"):        D7_MASTER,   # P0 立契
    ("dispatched", "claimed"):        D7_WORKER,   # P1 领取
    ("claimed", "executing"):         D7_WORKER,   # P2 执行
    ("executing", "collected"):       D7_WORKER,   # P3 回收（工作站产出 RunReport）
    ("collected", "mech_verified"):   D7_MASTER,   # P4a 机械验证
    ("mech_verified", "sem_verified"): D7_MASTER,  # P4b 语义复核（可选）
    ("mech_verified", "accepted"):    D7_MASTER,   # P5（跳过 P4b）
    ("mech_verified", "rejected"):    D7_MASTER,
    ("sem_verified", "accepted"):     D7_MASTER,   # P5
    ("sem_verified", "rejected"):     D7_MASTER,
}

# 三信封（字段级，§1.1 逐字）。`nested` **只收摘要在字面上给出的子键**
# （`golden{ref,checksum}` / `inputs{ref,digest}` / `evidence_budget{anchors,tool_calls}` /
#  `artifact{digest,size}`）—— 摘要**没给**的一律**不判、不补**（§2 五行的处置）。
D7_ENVELOPES = {
    "TaskContract": {
        "required": ("task_id", "task_desc", "accept", "golden", "inputs",
                     "evidence_budget", "constraints", "timeout_s", "sensitivity", "readonly"),
        "nested": {"golden": ("ref", "checksum"),
                   "inputs": ("ref", "digest"),
                   "evidence_budget": ("anchors", "tool_calls")},
        "forbidden": (),
    },
    "RunReport": {
        "required": ("run_id", "attempt", "artifact", "inputs_digest", "exit_code",
                     "decisions", "evidence", "usage"),
        "nested": {"artifact": ("digest", "size")},
        # ★★ 红线「产出方不得自评」的**机判形态**：`RunReport` 刻意不含 verdict 字段（§1.1 ★）
        "forbidden": ("verdict",),
    },
    "Verdict": {
        "required": ("verdict", "phase", "l1_results", "recorded_at", "seq"),
        "nested": {},
        "forbidden": (),
    },
}
# 判官**四值**（属**结论契约** `D7-PROTOCOL-CONCLUSION-CONTRACT`；承载 = `judge-prompt.tmpl` +
# `Test-ConclusionContract` 的 `$enum`）—— ★ 与 D7 信封**顶层**的 `verdict`（exit code）**同名不同物**；
# A 段裁 = 靠**载体 + 值类型**机械切分：★ 本仓 `review.json` **顶层没有 `verdict` 键**，
# 四值落在**嵌套**的 `review.json.contract.verdict`（E1 读码：`Invoke-Review` 的 `$ccSection`）
# ⇒ 顶层键集**不相交**；即便有人把四值提到顶层，它是字符串 ⇒ 仍落拒。
D7_VERDICT_WORDS = ("accept", "revise", "reject", "uncertain")
D7_ENV_VERDICTS = ("ok", "reject")


def validate_envelope(kind, env):
    """★ D7 三信封的**离线校验器**（缺字段即拒；`RunReport` 含 `verdict` 即拒）。

    返回 `(verdict, reason)`，`verdict ∈ D7_ENV_VERDICTS`（**封闭两值**）。
    ⚠ **fail-closed**：`kind` 不在闭集 / `env` 不是对象 ⇒ **reject**（**不是**"跳过"）。
    ⚠ **射程（= §2 五行「依据不足」的处置，落回规范 §1.5）**：只判**顶层必需键在不在** +
      **摘要逐字给出的子键**；`constraints` / `decisions[]`（八字段）/ `sensitivity` /
      `redispatch?` 的内部结构**一律不判、不补** —— 摘要没给 ⇒ 补它就是**编真值**。
    ★ **红线 3 的机判入口**：`TaskContract.accept[]` 每项须同时有判据与 `criteria_hash`
      （§1.1 逐字「判据 + `criteria_hash`」）—— 没有它，"判据在 P0 固化"无从机判。
    """
    if kind not in D7_ENVELOPES:
        return "reject", (f"未知信封 kind={kind!r}（闭集 {tuple(D7_ENVELOPES)}）"
                          f" ⇒ 拒（fail-closed：未知一律不放行）")
    if not isinstance(env, dict):
        return "reject", f"信封 {kind} 不是对象（{type(env).__name__}）⇒ 拒"
    spec = D7_ENVELOPES[kind]
    miss = [k for k in spec["required"] if k not in env]
    if miss:
        return "reject", f"{kind} 缺必需字段 {miss} ⇒ 拒（缺字段即拒）"
    for k, sub in spec["nested"].items():
        v = env.get(k)
        if not isinstance(v, dict):
            return "reject", f"{kind}.{k} 不是对象（摘要逐字给出子键 {sub}）⇒ 拒"
        smiss = [s for s in sub if s not in v]
        if smiss:
            return "reject", f"{kind}.{k} 缺子键 {smiss} ⇒ 拒（逐字列出，不得省）"
    hit = [k for k in spec["forbidden"] if k in env]
    if hit:
        return "reject", (f"{kind} 含禁字段 {hit} ⇒ **拒** —— 产出方不得自评"
                          f"（§1.1 ★：`RunReport` 刻意不含 verdict 字段）")
    if kind == "TaskContract":
        acc = env.get("accept")
        if not isinstance(acc, list) or not acc:
            return "reject", "TaskContract.accept 必须**非空列表**（无判据 = 无从裁决）⇒ 拒"
        for i, item in enumerate(acc):
            if not isinstance(item, dict) or not item.get("criteria") or not item.get("criteria_hash"):
                return "reject", (f"TaskContract.accept[{i}] 须**同时**给判据与 `criteria_hash`"
                                  f" ⇒ 拒（红线 3 的机判入口：判据与 golden 哈希在 P0 固化）")
    if kind == "RunReport" and not isinstance(env.get("decisions"), list):
        return "reject", "RunReport.decisions 必须是列表（八字段在**每项**里；内部结构不判）⇒ 拒"
    if kind == "Verdict":
        v = env.get("verdict")
        if isinstance(v, bool) or not isinstance(v, int):
            return "reject", (f"Verdict.verdict 必须是**整数**（= exit code）；实得 {v!r}"
                              f" ⇒ 拒（★ 词义冲突的机械切分：判官四值 {list(D7_VERDICT_WORDS)}"
                              f" 属**结论契约**（嵌套落在 `review.json.contract.verdict`），**不属**本信封）")
    return "ok", f"{kind} 信封**字段级合法**（顶层 {len(spec['required'])} 项齐）"


def d7_transition(state, to_state, actor):
    """★ D7 六相状态机（P0–P5）的**纯函数**：合法迁移给下一态，非法给**拒绝理由**。

    返回 `(ok, next_state, reason)`；`next_state` 仅在 ok 时非 None。
    规则（照 §1 的状态名序列 + 每相的"谁"）：
      · **单链**：`drafted→dispatched→claimed→executing→collected→mech_verified`
      · `mech_verified` 分叉：`→sem_verified`（P4b **可选**）或**直接** `→accepted|rejected`
      · `sem_verified →accepted|rejected` · 终态**无出边**
      · ★ **角色约束**：P1/P2/P3 段由**工作站**驱动，P0/P4a/P4b/P5 由**主控站**驱动
        —— 角色不对 ⇒ **拒**（角色禁项的机判入口）。
      · ⚠ **不得跳过 L1**：`collected` **不能**直落 `accepted|rejected`（红线 2）。
      · ⚠ **fail-closed**：未知态 / 未知目标 / `actor` 不在闭集 ⇒ **拒**（不静默放行）。
    """
    if state not in D7_PHASES:
        return False, None, f"未知当前态 {state!r}（闭集 {D7_PHASES}）⇒ 拒（fail-closed）"
    if to_state not in D7_PHASES:
        return False, None, f"未知目标态 {to_state!r} ⇒ 拒（fail-closed）"
    allowed = D7_TRANSITIONS[state]
    if not allowed:
        return False, None, f"{state} 是**终态**（无出边）⇒ 拒绝任何迁移（到 {to_state}）"
    if to_state not in allowed:
        why = ("**不得跳过 L1 机械门**（红线 2：L1 先于 L2/裁决）"
               if (state == "collected" and to_state in D7_TERMINAL) else f"合法出边只有 {allowed}")
        return False, None, f"{state} → {to_state} **不是合法迁移**：{why} ⇒ 拒"
    if actor not in (D7_MASTER, D7_WORKER):
        return False, None, (f"未知角色 actor={actor!r}（闭集 {D7_MASTER}/{D7_WORKER}）"
                             f" ⇒ 拒（fail-closed）")
    want = D7_TRANSITION_ACTOR.get((state, to_state))
    if want is not None and actor != want:
        return False, None, f"{state} → {to_state} 应由**{want}**驱动，实为 {actor} ⇒ 拒（角色不对）"
    return True, to_state, f"{state} → {to_state} 合法（{want} 驱动）"


# ★ 8 条纯函数拦截 = **三红线 + 三不变量 + 两角色禁项**（§1.2 / §1.3 / §1.4 逐字）。
# ⚠ 红线 1 与不变量 I-3 **内容相同**（完成信号权在主控站）⇒ **同一实现登记两个规则 id**，
#   不写两份实现（"同一事实两处表达"是本仓头号失败形态）。
D7_BLOCK_RULES = (
    ("RL1", "红线 1 · 完成信号权只在主控站"),
    ("RL2", "红线 2 · L1 机械门先于 L2 且 L2 无权改写"),
    ("RL3", "红线 3 · 判据与 golden 哈希在 P0 固化"),
    ("I1",  "不变量 I-1 · 单写者（事件流只有主控站可写）"),
    ("I3",  "不变量 I-3 · 完成信号权在主控站"),
    ("I6",  "不变量 I-6 · fail-closed"),
    ("PRM", "角色禁项 · 主控站不执行任务本体"),
    ("PRW", "角色禁项 · 工作站不自评/不写 verdict/不重派/不合并"),
)
D7_WORKER_FORBIDDEN = ("self_accept", "write_verdict", "redispatch", "merge")


def _d7_blk_completion(actor=None):
    """RL1 ≡ I-3：**完成信号权只在主控站**（同一实现登记两个 id）。"""
    if actor == D7_MASTER:
        return True, "主控站发出完成信号（accepted/rejected）⇒ 合法"
    return False, f"{actor!r} 不得发出完成信号 ⇒ 拒（红线 1 / 不变量 I-3：完成信号权只在主控站）"


def _d7_blk_l1_l2(l1_results=None, l2_marks=None, l2_rewrites_l1=False):
    """RL2：**L1 机械门先于 L2，且 L2 无权改写 L1**。"""
    if l2_rewrites_l1:
        return False, "L2 改写了 L1 结果 ⇒ 拒（红线 2：L2 无权改写 L1）"
    if l2_marks and not l1_results:
        return False, "有 L2 结果却**无** L1 结果 ⇒ 拒（红线 2：L1 必须先于 L2）"
    return True, "L1 先于 L2 且 L2 未改写 L1 ⇒ 合法"


def _d7_blk_frozen(hash_p0=None, hash_now=None):
    """RL3：**判据与 golden 哈希在 P0 固化**（= "判据不能事后改"）。"""
    if not hash_p0 or not hash_now:
        return False, ("P0 固值或现值缺失 ⇒ **判不了** ⇒ 拒（fail-closed：取不到固值就不能"
                       "声称「未改」—— 红线 3 要求判据与 golden 哈希在 P0 固化）")
    if hash_p0 != hash_now:
        return False, (f"判据/golden 哈希与 P0 固值不符（{hash_p0!r} ≠ {hash_now!r}）"
                       f" ⇒ 拒（红线 3：判据不能事后改）")
    return True, "判据/golden 哈希与 P0 固值一致 ⇒ 合法"


def _d7_blk_single_writer(actor=None, target=None):
    """I-1：**单写者** —— 事件流只有主控站可写，工作站只产出不落账。"""
    if target != "events":
        return True, f"目标 {target!r} 不在本约束射程内（约束只覆盖 `events` 事件流）"
    if actor == D7_MASTER:
        return True, "主控站写事件流 ⇒ 合法"
    return False, f"{actor!r} 不得写 `events` 事件流 ⇒ 拒（不变量 I-1：单写者）"


def _d7_blk_fail_closed(decision=None):
    """I-6：**fail-closed** —— 判不了 ⇒ 拒，**绝不**落通过。"""
    if decision == "pass":
        return True, "决策**显式** `pass` ⇒ 放行"
    return False, (f"决策 {decision!r} 不是显式 `pass` ⇒ 拒（不变量 I-6：缺失 / 未知 / `reject`"
                   f" 一律**不得**静默通过）")


def _d7_blk_master_scope(actor=None, action=None):
    """角色禁项：**主控站「不执行任务本体」**。"""
    if actor == D7_MASTER and action == "execute_task":
        return False, "主控站**执行任务本体** ⇒ 拒（角色禁项：主控站只立契/验证/裁决，不执行）"
    return True, f"主控站未执行任务本体（action={action!r}）⇒ 合法"


def _d7_blk_worker_scope(actor=None, action=None):
    """角色禁项：**工作站「不自评通过、不写 verdict、不重派、不合并」**。"""
    if actor == D7_WORKER and action in D7_WORKER_FORBIDDEN:
        return False, f"工作站执行禁项 {action!r} ⇒ 拒（禁项集 {D7_WORKER_FORBIDDEN}）"
    return True, f"工作站未触禁项（action={action!r}）⇒ 合法"


# 规则 id → 实现（RL1 与 I3 **共用** `_d7_blk_completion`，见上）
D7_BLOCK_FNS = {
    "RL1": _d7_blk_completion, "I3": _d7_blk_completion,
    "RL2": _d7_blk_l1_l2,      "RL3": _d7_blk_frozen,
    "I1":  _d7_blk_single_writer, "I6": _d7_blk_fail_closed,
    "PRM": _d7_blk_master_scope, "PRW": _d7_blk_worker_scope,
}


def d7_block(rule, **ctx):
    """**统一入口**：按规则 id 调 8 条拦截之一 ⇒ `(ok, reason)`。

    ⚠ 未知规则 id ⇒ **拒**（fail-closed；**不**静默返回 ok）。
    """
    fn = D7_BLOCK_FNS.get(rule)
    if fn is None:
        return False, (f"未知规则 id {rule!r}（闭集 {[r for r, _ in D7_BLOCK_RULES]}）"
                       f" ⇒ 拒（fail-closed）")
    return fn(**ctx)


# ── ★★ D7 判据的**消费面**（B 段 · 2026-10-01）────────────────────────────────────
# 为什么要有：判据本体是**纯函数**（上面那一段），而**调用方是外壳**
#   （`ops/station-bin/agent-cli.ps1`）⇒ 若外壳**重写一份**判据，就是"同一事实两处表达"
#   （本仓头号失败形态）。⇒ 这里给一个**薄 CLI**：外壳把「信封 / 迁移 / 动作」喂进来，
#   判据**只在这一处**（同 `Invoke-GateCheck` 调 `py ops/rpc_check.py` 的既有形态）。
# ⚠ **不是 CHECKS 项、不新增 gate id**（同 A 段）；它**不读写仓库文件**（只读入参）
#   ⇒ 不进任何门禁的射程 —— 它的护栏是 `tests/test_rpc_check_d7_protocol.py` 的 CLI 用例。
# 退出码（三态，**不可混**）：`0` = ok · `1` = **reject**（判据给了拒绝理由）·
#   `2` = **无法判**（入参读不到 / 解析失败 ⇒ fail-closed，**不是** ok，也不冒充 reject）。
D7_CLI_EXIT_UNDECIDABLE = 2


def _d7_cli_read(src):
    """读一个 JSON 入参：`'-'` = stdin，其余 = 文件路径（`utf-8-sig` 容忍 BOM）。"""
    raw = sys.stdin.read() if src == "-" else Path(src).read_text(encoding="utf-8-sig")
    return json.loads(raw)


# ── ★★ B3（2026-10-01）：角色**同机**可见性判据 `PRH`（**不是拦截**，是"看得见"）──────────
# 裁定依据（用户 2026-10-01 裁【甲】；落点 = 契约 §1.4 的角色化 + §1.6 的三句裁）：
#   §1.4 的「主控站 / 工作站」= **角色**（主控角色驱动 P0/P4a/P4b/P5；工作站角色驱动 P1/P2/P3），
#   **不是机器** ⇒ 主控机器上的出网通道以 `worker` 角色登记，**不触** `PRM`。
#   ★ **但**"同一台机器既产出又裁决"这件事**必须被看见** —— 它直接影响裁决独立性
#     （红线 1「完成信号权只在主控站」真正想保的是"**产出方不得自评**"）。
# ⚠⚠ **它刻意不进 `D7_BLOCK_RULES` / `D7_BLOCK_FNS`**：那 8 条的口径是"三红线 + 三不变量 +
#   两角色禁项"，本项**不属于**其中任何一类；把"报数"混进"拦截"会让 8 条的计数失去意义
#   （同 `inventory/ops.yaml` 把 `entry_modules` 从 `entry` 拆出的理由）。
# ⚠ **不设阈值**（`O-126`：不许用凭空数值满足可机判）—— **先量后定档**：读数出来再由人裁
#   要不要把它升级为**拒**（= PRM 分析里的方案②「物理分离」）。
#   ★ 收紧条件（写死）：**同机占比有读数 + 用户裁「升级为拒」** ⇒ 才改调用方，**不改本判据**。
D7_HOST_SEP_RULE = "PRH"


def d7_host_separation(exec_host=None, arbiter_host=None):
    """`PRH`：**产出机 vs 裁决机**的同机可见性 ⇒ `(same, reason)`，`same ∈ {True, False, None}`。

    ⚠ **fail-closed 的方向在这里是"不可判"而不是"拒"**：缺任一 host ⇒ `same=None`
      （**不可判**）⇒ 调用方必须**如实报出**，**不许**静默读成"不同机"
      （本仓口径：判不了 ≠ 通过，同 `O-22` / `O-119`）。
    ⚠ 本判据**只判"是否同一台机器"**：它**不判**"该形态合不合规"（那是用户的裁）。
    """
    e = str(exec_host or "").strip()
    a = str(arbiter_host or "").strip()
    if not e or not a:
        return None, (f"判不了（exec_host={exec_host!r} / arbiter_host={arbiter_host!r}）"
                      f" ⇒ **不可判**（缺一即不可判，不得静默读成「不同机」）")
    if e == a:
        return True, (f"**同机**：产出机 == 裁决机 == {e} ⇒ 裁决独立性打折"
                      f"（红线 1 想保的「产出方不得自评」，此形态下**只有角色分离、无机器分离**）")
    return False, f"**分离**：产出机 {e} ≠ 裁决机 {a} ⇒ 机械独立"


def d7_cli(args):
    """**消费面**：按 `args` 跑对应判据 ⇒ 退出码（见上）。命中则返回 int，未命中返回 `None`。"""
    if not (args.d7_envelope or args.d7_transition or args.d7_block or args.d7_host_sep):
        return None
    try:                                  # 只在本入口改编码：门禁自身的输出行为**零改动**
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if args.d7_envelope:
        kind, src = args.d7_envelope
        try:
            env = _d7_cli_read(src)
        except Exception as e:
            print(f"D7_ENVELOPE undecidable {kind}: 读不到/解析失败 "
                  f"{type(e).__name__}: {e} ⇒ fail-closed")
            return D7_CLI_EXIT_UNDECIDABLE
        v, why = validate_envelope(kind, env)
        print(f"D7_ENVELOPE {v} {kind}: {why}")
        return 0 if v == "ok" else 1
    if args.d7_transition:
        a, b, actor = args.d7_transition
        ok, _nxt, why = d7_transition(a, b, actor)
        print(f"D7_TRANSITION {'ok' if ok else 'reject'} {a} -> {b} ({actor}): {why}")
        return 0 if ok else 1
    if args.d7_host_sep:
        # ★ 三态不可混：0 = 分离 · 1 = **同机**（判据确实给出了结论）· 2 = 不可判（缺 host）。
        #   ⚠ 调用方（外壳）对 `1` 按 **WARN** 处理（灰度，同 B1 的 gaps）—— 那是**调用方的政策**，
        #   不是本判据的语义（本判据只说"同不同机"）。
        e, a = args.d7_host_sep
        same, why = d7_host_separation(e, a)
        if same is None:
            print(f"D7_HOSTSEP undecidable: {why}")
            return D7_CLI_EXIT_UNDECIDABLE
        print(f"D7_HOSTSEP {'same' if same else 'separate'}: {why}")
        return 1 if same else 0
    try:
        ctx = _d7_cli_read(args.d7_ctx) if args.d7_ctx else {}
    except Exception as e:
        print(f"D7_BLOCK undecidable {args.d7_block}: ctx 解析失败 {type(e).__name__}: {e}"
              f" ⇒ fail-closed")
        return D7_CLI_EXIT_UNDECIDABLE
    if not isinstance(ctx, dict):
        print(f"D7_BLOCK undecidable {args.d7_block}: ctx 不是对象 ⇒ fail-closed")
        return D7_CLI_EXIT_UNDECIDABLE
    try:
        ok, why = d7_block(args.d7_block, **ctx)
    except Exception as e:
        # ★★ B2 实测抓到的**真缺陷**：`ctx` 与判据的**输入契约不符**（多传/拼错键）时，
        #   `**ctx` 展开会抛 `TypeError` ⇒ 进程**非零退出（1）** —— 而 1 在本 CLI 的语义是
        #   **reject**（判据给出了拒绝理由）⇒ **崩溃被冒充成"判据拒绝了"**（三态不可混被破坏）。
        #   ⇒ 归 **`undecidable`（2）**：这不是"判据说不行"，是"**判据没能跑**"（同 O-22/`O-119` 口径）。
        print(f"D7_BLOCK undecidable {args.d7_block}: ctx 与判据的输入契约不符 "
              f"（{type(e).__name__}: {e}）⇒ fail-closed —— **不是 reject**")
        return D7_CLI_EXIT_UNDECIDABLE
    print(f"D7_BLOCK {'ok' if ok else 'reject'} {args.d7_block}: {why}")
    return 0 if ok else 1


# ── D7-P1-5 (2026-09-26)：U-5 信任基座四问 V-1~V-4 + 晋升门 schema ────────────
# 两部分：
#   ① **四问各一条可机判判据**（`v1_definition_correspondence` / `v2_bridge_completeness` /
#      `v3_axiom_whitelist` / `v4_build_reproducible`）—— 纯函数，**不是** `CHECKS` 项
#      （本仓没有形式化信任基座的对象可判：**V-2 真空** · V-1/V-4 各仅 1 项目 · V-3 仅关键词级，见 D-37）；
#   ② **晋升门 schema**（`inventory/promotion.yaml`）—— ★ **这一半是 `CHECKS` 项**（`promotion`），
#      因为**被判的对象真实存在**（schema 自身 + 三处实现的映射）⇒ **不是空判**。
#
# ★ 已裁（台账 D-38）：把三处独立发明的晋升门**统一为一个 schema**（判据 = 成功率 / 复发次数 /
#   验证状态，**并存于同一 schema 的不同字段**），**不许发明第四种**。
#   ⇒ 本断言的**核心规则是"映射闭包"**：schema 里**不许有孤儿字段 / 孤儿判据** ——
#     一个没被任何一处实现用到的字段，就是**变相发明的第四种**。
# ★ 依据：合并稿 §6.3（V-1~V-4 规格书）· §11.5（三处晋升门实测）· §11.7（不得自审只能靠结构）
#   · 台账 D-37（四问列为验收项）· D-38（统一 schema）。
PROMOTION_INV = ROOT / "inventory" / "promotion.yaml"
PROMO_OPS = (">=", "<=", "==", ">", "<", "!=")
PROMO_POLICIES = ("lru", "fifo")
# D-38 的落地：这三种判据**必须并存**（各自来自一处真实实现）
PROMO_REQUIRED_CRITERIA = ("success_rate", "recurrence", "verified")


def _promo_cmp(lhs, op, rhs):
    """*纯*比较器（`op ∈ PROMO_OPS`）；类型不合 ⇒ `False`（**不抛** —— 一条脏条目不该炸掉整份判定）。"""
    try:
        if op == ">=":
            return lhs >= rhs
        if op == "<=":
            return lhs <= rhs
        if op == "==":
            return lhs == rhs
        if op == "!=":
            return lhs != rhs
        if op == ">":
            return lhs > rhs
        if op == "<":
            return lhs < rhs
    except TypeError:
        return False
    return False


def promotion_entry_verdict(entry, gate):
    """★ `U5#5`（2026-09-30 · 批 4）：把**一条真实条目**喂给 `gate` ⇒ `(ok, reasons, satisfied)`。

    ⚠⚠ **本批补的是一个真缺口，不只是"扩样例"**：此前 `validate_promotion` 只判 **schema 自身**
      （字段 / 判据 / 映射闭包 / `entries` 是不是列表）—— **从不把任何条目喂给 `gate.required` / `gate.criteria`**
      ⇒ 「实例 0 条」比它看起来更糟：**即便加一条，也没有任何东西会检查它**（schema 是"**只可读、不可走**"的）。
    ⇒ 本函数把 `gate` 变成**可走的**：`required` 缺 ⇒ 不可晋升；`criteria` **任一满足** ⇒ 可晋升；
      「字段没给」⇒ 该判据**不满足**（**不是**"跳过"、更**不是**"默认满足"）。
    ⚠ **不给阈值就不能假定**：`ref` 指向的门槛字段未给 ⇒ 该判据**不满足**（阈值未定 = `unverified` 已登记）
      —— **不许**替它填一个数（那正是 `O-126` 点名的"用凭空数值满足可机判"）。
    """
    if not isinstance(entry, dict):
        return False, [f"条目不是映射: {entry!r}"], []
    hard = []
    for f in (gate.get("required") or []):
        v = entry.get(f)
        if v is None or (isinstance(v, str) and not v.strip()):
            hard.append(f"缺必填字段 `{f}`（Spec_Workflow 原文：**缺锚点不得登记**）")
    satisfied, crit_note = [], []
    for c in (gate.get("criteria") or []):
        fld, op, ref = c.get("field"), c.get("op"), c.get("ref")
        if isinstance(ref, str) and ref.startswith("$"):
            rhs = entry.get(ref[1:])
            if rhs is None:
                crit_note.append(f"判据 `{c.get('id')}` **不满足**：门槛 `{ref[1:]}` 未给（阈值未定 ⇒ 不许假定）")
                continue
        else:
            rhs = ref
        lhs = entry.get(fld)
        if lhs is None:
            crit_note.append(f"判据 `{c.get('id')}` **不满足**：条目未给 `{fld}`")
            continue
        if _promo_cmp(lhs, op, rhs):
            satisfied.append(c.get("id"))
    if hard:
        return False, hard, satisfied
    if not satisfied:
        return False, crit_note + ["**没有任何判据满足** ⇒ 不得晋升（三种判据**任一**满足才可；"
                                   "并列语义本身仍是 `unverified` 登记项）"], []
    return True, [], satisfied


def validate_promotion(doc):
    """**纯函数** → `(bad, notes)`：晋升门 schema 的自洽 + **映射闭包** + ★ **逐条目走一遍门**。"""
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["promotion.yaml 顶层不是映射（结构改了？）"], notes

    fields = doc.get("fields") or []
    fids = [f.get("id") for f in fields if isinstance(f, dict)]
    if not fields:
        bad.append("`fields` 为空 ⇒ 判据没有字段可引用")
    if len(fids) != len(set(fids)):
        bad.append(f"`fields` 的 id 有重复: {fids}")
    for f in fields:
        if not (isinstance(f, dict) and f.get("id") and f.get("type")):
            bad.append(f"`fields` 有条目缺 id/type: {f!r}")
    ftype = {f["id"]: f.get("type") for f in fields if isinstance(f, dict) and f.get("id")}

    gate = doc.get("gate") or {}
    req = gate.get("required") or []
    if not req:
        bad.append("`gate.required` 为空 ⇒ 没有“必填”就没有门（Spec_Workflow 的『缺锚点不得登记』落不下）")
    for r in req:
        if r not in fids:
            bad.append(f"`gate.required` 的 {r!r} 不在 `fields` 里")

    cap = gate.get("capacity") or {}
    if not cap:
        bad.append("`gate.capacity` 缺失 ⇒ 容量件套没落地（Textbook `FixMemory` 的三件套之一）")
    else:
        if cap.get("field") not in fids:
            bad.append(f"`gate.capacity.field`={cap.get('field')!r} 不在 `fields` 里")
        if not isinstance(cap.get("max"), int) or cap.get("max", 0) <= 0:
            bad.append(f"`gate.capacity.max` 必须是正整数: {cap.get('max')!r}")
        if cap.get("policy") not in PROMO_POLICIES:
            bad.append(f"`gate.capacity.policy`={cap.get('policy')!r} 不在封闭集 {PROMO_POLICIES}")

    crit = gate.get("criteria") or []
    cids = [c.get("id") for c in crit if isinstance(c, dict)]
    if not crit:
        bad.append("`gate.criteria` 为空 ⇒ 没有任何晋升判据")
    if len(cids) != len(set(cids)):
        bad.append(f"`gate.criteria` 的 id 有重复: {cids}")
    for c in crit:
        if not isinstance(c, dict):
            bad.append(f"`gate.criteria` 有条目不是映射: {c!r}")
            continue
        cf, ref = c.get("field"), c.get("ref")
        if cf not in fids:
            bad.append(f"`criteria[{c.get('id')}].field`={cf!r} 不在 `fields` 里")
        if c.get("op") not in PROMO_OPS:
            bad.append(f"`criteria[{c.get('id')}].op`={c.get('op')!r} 不在封闭集 {PROMO_OPS}")
        if isinstance(ref, str) and ref.startswith("$"):
            tgt = ref[1:]
            if tgt not in fids:
                bad.append(f"`criteria[{c.get('id')}].ref` 引用了不存在的字段 {tgt!r}")
            elif cf in ftype and ftype.get(tgt) != ftype.get(cf):
                bad.append(f"`criteria[{c.get('id')}]` 的类型不匹配: {cf}({ftype.get(cf)}) "
                           f"{c.get('op')} {tgt}({ftype.get(tgt)})")
    miss_crit = [x for x in PROMO_REQUIRED_CRITERIA if x not in cids]
    if miss_crit:
        bad.append(f"**D-38 要求三种判据并存**，但缺 {miss_crit} ⇒ 那等于**发明第四种**或丢掉一种")

    struct = gate.get("structure") or []
    if not struct:
        bad.append("`gate.structure` 为空 ⇒ §11.7『不得自审只能靠结构』没落地")

    # ── ★ 映射闭包（本断言的核心：不许孤儿字段 / 孤儿判据）───────────────
    maps = doc.get("mapping_closure") or []
    if not maps:
        bad.append("`mapping_closure` 为空 ⇒ D-38『schema 须能被三处各自映射』**没有被判**")
    used_fields, used_crit = set(), set()
    for m in maps:
        if not isinstance(m, dict):
            bad.append(f"`mapping_closure` 有条目不是映射: {m!r}")
            continue
        mid = m.get("id")
        u = m.get("uses") or []
        cu = m.get("criteria_used") or []
        if not u:
            bad.append(f"`mapping_closure[{mid}]` 没声明 `uses`")
        if not cu:
            bad.append(f"`mapping_closure[{mid}]` 没声明 `criteria_used`（映射了却不用任何判据？）")
        for x in u:
            if x not in fids:
                bad.append(f"`mapping_closure[{mid}].uses` 含**不存在的字段** {x!r}")
        for x in cu:
            if x not in cids:
                bad.append(f"`mapping_closure[{mid}].criteria_used` 含**不存在的判据** {x!r}")
        used_fields |= set(u)
        used_crit |= set(cu)
    orphan_f = [f for f in fids if f not in used_fields]
    if orphan_f:
        bad.append(f"**孤儿字段** {orphan_f} ⇒ 没有任何一处实现用到它（= 变相发明第四种，D-38 不许）")
    orphan_c = [c for c in cids if c not in used_crit]
    if orphan_c:
        bad.append(f"**孤儿判据** {orphan_c} ⇒ 没有一处实现用它")
    notes.append(f"字段 {len(fids)} · 判据 {len(cids)} · 三处映射 {len(maps)}")

    if "entries" not in doc:
        bad.append("**缺 `entries` 字段** ⇒ 无法区分「没有条目」与「忘了写」")
    else:
        ents = doc["entries"] or []
        if not isinstance(ents, list):
            bad.append(f"`entries` 不是列表（{type(ents).__name__}）")
        elif not ents and not str(doc.get("empty_reason") or "").strip():
            bad.append("`entries` 为空**且没有 `empty_reason`** ⇒ 空得没说法")
        elif not ents:
            notes.append("实例 0 条 (空已显式报出, 不静默通过)")
        else:
            # ★ `U5#5`（批 4）：**逐条目走一遍门** —— 容量件套 + `gate.required` + `criteria`（任一满足）
            cap_max = (gate.get("capacity") or {}).get("max")
            if isinstance(cap_max, int) and len(ents) > cap_max:
                bad.append(f"`entries` {len(ents)} 条 > `gate.capacity.max`={cap_max} ⇒ 容量件套被绕过")
            n_ok = 0
            for i, e in enumerate(ents):
                ok_e, why, _sat = promotion_entry_verdict(e, gate)
                if ok_e:
                    n_ok += 1
                    continue
                eid = (e or {}).get("id", "?") if isinstance(e, dict) else repr(e)
                bad.append(f"`entries[{i}]`({eid}) **不可晋升**: " + " ; ".join(why))
            notes.append(f"实例 {len(ents)} 条 · **可晋升 {n_ok} · 拦截 {len(ents) - n_ok}**"
                         f"（判据 = `gate.required` + `gate.criteria` **任一满足**）")

    if not (doc.get("unverified") or []):
        bad.append("`unverified` 为空 ⇒ 本 schema 里**新设**的东西没被如实登记（新设项 = 最像“第四种”的地方）")
    return bad, notes


def check_promotion(ctx):
    """D7-P1-5: U-5 晋升门 schema（`inventory/promotion.yaml`）。"""
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 promotion 晋升门断言", []
    if not PROMOTION_INV.exists():
        return "FAIL", "inventory/promotion.yaml 缺失（本断言的登记依据）", []
    try:
        doc = yaml.safe_load(PROMOTION_INV.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return "FAIL", f"inventory/promotion.yaml 解析失败: {type(e).__name__}: {e}", []
    bad, notes = validate_promotion(doc)
    return ("FAIL" if bad else "PASS"), " · ".join(notes), bad


# ── U-5 的**四问判据**（V-1~V-4）—— 判据库，不是 CHECKS 项 ──────────────────
# ⚠ 不判本仓状态：**V-2 真空 · V-1/V-4 各仅 1 项目 · V-3 仅关键词级**（D-37 的实况）
#   ⇒ 本仓没有对象 ⇒ 只被测试驱动（与 U-4 的 `decide_invalidation` 同形）。
# ★ 四条判据各自对上一处"最接近"的实现（§6.3），并把它从"人看"升为"机判"——
#   尤其 V-3：原文要求「从**关键词级**升为**白名单级**」，本判据就是白名单比对。
def v3_axiom_whitelist(axioms, whitelist=None):
    """V-3 信任基座：**公理集必须 ⊆ 显式声明的白名单**。

    ★★ **`U5#4`（2026-09-30 裁 / `O-123`）：裁掉"默认名单"这一形态。**
      · `whitelist is None` = **根本没声明** ⇒ **判不通过**（fail-closed）。
        旧实现回落到 `("propext","Classical.choice","Quot.sound")` —— 而那是**原文举例**；
        本规范自己写着「**取自举例 ≠ 裁定**」⇒ 拿它当缺省 = **把举例升格成裁定**（本仓最典型的一类**假精确**）。
      · `whitelist == []` = **显式空声明** ⇒ **合法**（语义 = 「**确实不需要额外公理**」）。
        ★ 这正是本裁要区分的那对：**「确实不需要额外公理」 vs 「根本没声明」**（旧实现里二者**同值** ⇒ 无法区分）。
    ⚠ 空声明**不是**"判据恒真"：此时任何公理都落在白名单外 ⇒ 仍会红（见 `extra` 分支）。
    ⚠ 本函数第一版的自伤（历史，见 `docs/2026-09-23_D6-D7分阶段执行方案.md`）：把 `whitelist=[]` 与 `None` 混同
      ⇒ "白名单为空 ⇒ fail" 那段**永远到不了**。
    """
    if whitelist is None:
        return False, ["**未声明公理白名单** ⇒ 判不通过（本题已裁掉「默认名单」形态："
                       "「取自原文举例」**不等于裁定**；缺声明 = 判不了 ⇒ fail-closed）"]
    wl = tuple(whitelist)                       # 显式空 ⇒ 合法（"确实不需要额外公理"）
    extra = sorted(set(axioms or []) - set(wl))
    if extra:
        return False, [f"白名单外公理 {extra}（V-3 要求白名单级，不许关键词级放过）"]
    return True, []


def v4_build_reproducible(deps, ledger=None):
    """V-4 构建可复现性：**每个依赖都钉到 rev**，且 ledger 记版本与 input-hash。"""
    bad = []
    for d in (deps or []):
        if not isinstance(d, dict) or not d.get("name"):
            bad.append(f"依赖条目缺 name: {d!r}")
        elif not d.get("rev"):
            bad.append(f"依赖 {d.get('name')!r} **未钉 rev** ⇒ 第三方无法复现（V-4）")
    if not (ledger or {}).get("tool_versions"):
        bad.append("ledger 缺 `tool_versions`（构建工具/库版本）⇒ V-4 要求的可追溯缺失")
    if not (ledger or {}).get("input_hash"):
        bad.append("ledger 缺 `input_hash` ⇒ 无法判定“这份产物对应哪次输入”")
    return (not bad), bad


def v1_definition_correspondence(rows):
    """V-1 定义对应性：**官方陈述 ↔ 形式化定义**逐条对应，且每条**带锚点**。

    ⚠ 判据只能判"**对应关系被逐条写明且可追溯**"；"对应得对不对"仍需人 ——
       这条边界必须写进结论（不许把"有对照表"说成"定义正确"）。
    """
    bad = []
    if not rows:
        bad.append("对应表为空 ⇒ 无法判定定义对应性（形式化了别的东西也算通过）")
    for i, r in enumerate(rows or [], 1):
        if not isinstance(r, dict):
            bad.append(f"对应表第 {i} 行不是映射")
            continue
        miss = [k for k in ("claim", "formal", "anchor") if not r.get(k)]
        if miss:
            bad.append(f"对应表第 {i} 行缺 {miss} ⇒ 该条对应**不可追溯**")
    return (not bad), bad


def v2_bridge_completeness(steps):
    """V-2 桥接完整性：正文 → Lean 定理之间**每一跳都有记录**，且**首尾连续**（无缺失的一跳）。

    ⚠ D-37 实测 **V-2 真空**（九项目**没有一个**做这件事）⇒ 本判据是**新造的形式**，
       不是对既有实现的机判化（这一条必须与 V-1/V-3/V-4 区别对待）。
    """
    bad = []
    if not steps:
        bad.append("跳表为空 ⇒ 桥接完整性无从判定（而 V-2 实测是**真空**）")
        return False, bad
    for i, s in enumerate(steps, 1):
        if not isinstance(s, dict):
            bad.append(f"跳表第 {i} 条不是映射")
            continue
        miss = [k for k in ("from", "to", "evidence") if not s.get(k)]
        if miss:
            bad.append(f"跳表第 {i} 条缺 {miss} ⇒ 这一跳**没有记录**")
    for i in range(1, len(steps)):
        a, b = steps[i - 1], steps[i]
        if isinstance(a, dict) and isinstance(b, dict) and a.get("to") and b.get("from") \
                and a["to"] != b["from"]:
            bad.append(f"跳表**断链**：第 {i} 条到 {a['to']!r}，第 {i+1} 条从 {b['from']!r} 起")
    return (not bad), bad


# ── O-66 (2026-09-25)：卡面 `input-provenance` 义务（`CROSS-PROJECT-WORK-STANDARD §4` 的**机判**）──
# 义务原文：卡声明 `public`/`sanitized` **且带输入** ⇒ ① `input-provenance` 必填（逐项本仓相对路径）
#   ② 每项须在 `sensitivity.yaml` 有 `tier` ③ 卡的 `sensitivity` **不得宽于**该项的 `tier`。
#
# ★ 触发条件为什么用 `attach-egress` 而不是"实际附件数"（**覆盖等价，非权宜**）：
#   运行时 `Get-AttachEgressReject` 已强制"**有附件 ∧ 后端出网 ⇒ 必须声明 `attach-egress: ok`**"
#   ⇒ "出网带附件"这一 population 恰好是"声明了 `attach-egress`"的**子集**
#   ⇒ 以**声明**为条件做**静态**判 = 覆盖同一人群（且是**超集** ⇒ 保守 ⇒ sound），并**在提交时就拦**。
#   ⚠ 另一条路（派发时按真实 `$attach.Count` 判）需要 PowerShell 读 `sensitivity.yaml` ——
#     **PS 5.1 无 YAML 解析**（实测 `agent-cli.ps1` 全域零 YAML 用法）⇒ 得额外建"生成物 + 查表"链路。
#     静态侧**更简单且更早**，故选定。（决策与实测见 DEV-LOG-014 §32.6 的"就地更正"）
CARD_GLOB = "spec/**/*cards*/**/*.md"      # 卡区目录名含 `cards`（`dogfood-cards/` · `test-cards/`）
# tier 序（**不得宽于** = 卡 rank 必须 ≤ 输入 rank）；`unverified` 按 `local-only` 处置（表头 fail-closed）
TIER_RANK = {"local-only": 0, "unverified": 0, "sanitized": 1, "public": 2}
PROVENANCE_NONE = "none"                   # 显式"输入不来自本仓"（唯一认可的 token，刻意不收 n/a·null）
# ── O-69（2026-09-26）：规则 ④b 的两个常量 —— **都来自实测**（DEV-LOG-014 §56）──────────
# ④b 要补的盲区：④ 只看得见 **registry**（"已登记"）⇒ **未登记**的本仓敏感文件**完全不可见**。
#   实现时的两条过滤，每条都对应 §56 的一个实测数：
#     ① `PROVENANCE_OUTPUT_PREFIXES` = **产物面** —— 实测 20 张卡扫出 25 个候选，其中 **14 个是 `out/*`**
#        （那是**卡的产物**，不是读进来的输入）⇒ 不排除就是 **≥56% 误报**；
#     ② 判"是不是本仓"用 **事实**（`(ROOT / token).is_file()`），**不用**"顶层段像不像 registry"
#        —— 后者会**漏** `inventory/sensitivity.yaml` 这类（它是本仓文件，但顶层段不在 registry 里）
#        同族教训 = **O-87**："用'像不像'代替'是不是'"。
PROVENANCE_OUTPUT_PREFIXES = ("out/", "batches/", "golden/")
PROV_PATH_TOKEN_RE = re.compile(
    r"[A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:md|yaml|yml|json|jsonl|py|ps1|sh|csv|txt|db|duckdb)")


_FM_KEY_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$")


def _card_frontmatter(path):
    """提取卡面 front-matter（首个 `---` 包夹块）⇒ dict；**首行不是 `---` ⇒ None（不是卡）**。

    ★ 用**行式提取**而不是 `yaml.safe_load` —— 两条理由**都是本轮实测出来的**：
      · **严格 YAML 会炸**：实测 2 张卡（`t1-attach-shared-probe` · `cpphub-001`）的 `task:`/`note:` 值里含
        `": "` ⇒ `yaml.safe_load` 抛 `ScannerError`（与 2026-09-24 `sensitivity.yaml` 那次**同一个坑**）。
        第一版据此**静默 `return None`（= 跳过该卡）** ⇒ 把本该触发的 `t1` 漏过去了 = **我判据自己的假绿**
        （"什么都没判所以通过"—— 本仓头号形态，这次长在我当天新写的判据里）。
      · **权威读取器（PS 侧 `Get-FrontMatter`）本来就是行式的** ⇒ 行式提取与运行时**同口径**，
        避免"Python 说这卡坏、PS 却读得动"的**双标**（双标会把可派的卡判红）。
    ⇒ 同时支持**块式列表**（键后跟缩进 `- `）：否则 `input-provenance:` 写成列表会被读成空串 ⇒ **假红**。
    """
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    if not lines or lines[0].strip() != "---":
        return None
    out, key = {}, None
    for ln in lines[1:]:
        if ln.strip() == "---":
            return out
        if not ln.strip():
            continue
        if key and re.match(r"^\s+-\s+", ln):               # 块式列表项
            cur = out.get(key)
            if not isinstance(cur, list):
                cur = [] if not cur else [cur]
                out[key] = cur
            cur.append(ln.split("-", 1)[1].strip().strip('"').strip("'"))
            continue
        m = _FM_KEY_RE.match(ln)
        if m:
            key = m.group(1)
            out[key] = m.group(2).strip().strip('"').strip("'")
        else:
            key = None                                       # 非键非列表行 ⇒ 当前键结束
    return out                                               # 无闭合 `---`：PS 侧同样宽容 ⇒ 按已读到的算


def _sens_registry(inv):
    """`sensitivity.yaml` → `{path: tier}`（只取显式登记项；缺省档不在内）。"""
    reg = {}
    for sec in SENSITIVITY_SECTIONS:
        for it in (inv.get(sec) or []):
            p = (it or {}).get("path")
            if p:
                reg[p] = (it or {}).get("tier")
    return reg


def validate_input_provenance(cards, sensitivity_inv):
    """O-66：卡面 `input-provenance` 义务的**纯函数**判定（⇒ 离线可正反夹测）。

    `cards` = `[(label, frontmatter_dict, full_text)]`。返回 `(bad, stats)`；
    `bad` 里**两类后果不同**（故分桶返回给上层取最严）：
      · **FAIL 级**（规则 ① 缺字段 / ② 项未登记 / ③ 档位过宽）——**契约违规**
      · **WARN 级**（规则 ④ / **④b**）——"提到 ≠ 读到"，机械判不出，**只报不拦**
        · ④ = 正文出现 **tier 严于本卡**的**已登记**路径；
        · **④b（O-69，2026-09-26）** = 正文引用了**未登记**且**确实存在于本仓**的文件
          （④ 只看得见 registry ⇒ 未登记者原先**完全不可见**）
    """
    reg = _sens_registry(sensitivity_inv)
    default_tier = str(sensitivity_inv.get("default_tier") or "local-only")
    fail, warn = [], []
    n_trig = n_ok = n_none = 0
    for label, fm, body in cards:
        if not isinstance(fm, dict):
            continue
        ae = str(fm.get("attach-egress") or "").strip().lower()
        if ae not in ("ok", "yes", "true"):
            continue                                  # 未声明 ⇒ 运行时根本不放行出网附件 ⇒ 不触发
        tier = str(fm.get("sensitivity") or "").strip().lower() or default_tier
        if tier not in ("public", "sanitized"):
            continue                                  # local-only / unverified 本就不出网
        n_trig += 1
        prov = fm.get("input-provenance")
        if prov in (None, "", []):
            fail.append(f"{label}: 声明 `attach-egress` 且 `sensitivity={tier}` ⇒ **`input-provenance` 必填**"
                        f"（确无本仓输入请显式写 `input-provenance: {PROVENANCE_NONE}`）")
            continue
        entries = [str(e).strip() for e in (prov if isinstance(prov, list) else [prov]) if str(e).strip()]
        if len(entries) == 1 and entries[0].lower() == PROVENANCE_NONE:
            n_none += 1
            # 规则 ④（WARN 级）：`none` 必须**可证伪** —— 正文不得出现 tier **严于本卡**的已登记路径。
            #   ⚠ 只判"严于本卡"：卡天然会引用自身所在目录（实测 A2 写了 `dogfood-cards/...`，
            #     而该目录登记为 `public`）⇒ 若判"任何已登记路径"会**假红**（本轮实测踩到并收窄）。
            hits = sorted({p for p in reg
                           if TIER_RANK.get(reg.get(p) or default_tier, 0) < TIER_RANK.get(tier, 0)
                           and p.rstrip("/") in body})
            if hits:
                warn.append(f"{label}: 声明 `input-provenance: {PROVENANCE_NONE}`，但正文出现 **tier 严于本卡"
                            f"（{tier}）** 的已登记路径 {hits} ⇒ `{PROVENANCE_NONE}` 的可证伪性不成立"
                            f"（要么把该路径列进 `input-provenance`，要么把档位降到不宽于它）")
            # ★★ 规则 ④b（O-69，2026-09-26；仍属 **WARN 级 = 只报不拦**）：
            #   ④ 的盲区是"**只看得见 registry**" ⇒ 一张 `public` 卡声明 `none`、正文却引用了
            #   **未登记**的本仓文件时，④ **不触发** ⇒ 门禁全程 PASS（b3 的原始反例即此）。
            #   ④b 把它变可见：扫正文里的**路径样式 token**（**必须含 `/`** ⇒ 排除"裸文件名"这类
            #   散文里的普通词），再过两道过滤（**都来自 §56 的实测**）：
            #     ① 排除 `PROVENANCE_OUTPUT_PREFIXES`（卡的**产物**，不是输入）—— 实测消掉 14/25 误报；
            #     ② **事实**判"是不是本仓"：该路径在仓内**确实存在**（`is_file()`）
            #        ⚠ 刻意**不用**"顶层段 ∈ registry" —— 那会漏 `inventory/sensitivity.yaml` 这类
            #        （本仓文件，但顶层段不在 registry 里）。
            #   ⚠ 射程：只判"**提到**了未登记的本仓文件"，**不判**"真的读了它"（提到 ≠ 读到 ⇒ 故 WARN 不 FAIL）。
            cand = set()
            for tok in PROV_PATH_TOKEN_RE.findall(body):
                if "/" not in tok or tok in reg:
                    continue
                if tok.startswith(PROVENANCE_OUTPUT_PREFIXES):
                    continue                       # ① 卡的产物面
                if (ROOT / tok).is_file():
                    cand.add(tok)                  # ② 事实：确实是本仓**存在**的文件
            if cand:
                warn.append(f"{label}: 声明 `input-provenance: {PROVENANCE_NONE}`，但正文引用了 **未登记**且"
                            f"**确实存在于本仓**的文件 {sorted(cand)} ⇒ 未登记 = `{default_tier}`（fail-closed，"
                            f"严于本卡 `{tier}`）⇒ 要么把它列进 `input-provenance`，要么说明这些只是**提及**")
            continue
        n_ok += 1
        for e in entries:
            if e not in reg:
                fail.append(f"{label}: `input-provenance` 项 `{e}` **未登记**于 sensitivity.yaml"
                            f"（未登记 = `{default_tier}`，fail-closed）⇒ 先立项登记或改档位")
                continue
            et = reg[e] or default_tier
            if TIER_RANK.get(et, 0) < TIER_RANK.get(tier, 0):
                fail.append(f"{label}: 卡档位 `{tier}` **宽于**输入 `{e}` 的 tier `{et}`"
                            f" ⇒ 档位不得比它读的输入更宽")
    return fail, warn, {"cards": len(cards), "triggered": n_trig, "ok": n_ok, "none": n_none}


def check_input_provenance(ctx):
    """O-66：卡面 `input-provenance` 义务（规则见 `validate_input_provenance`）。

    为什么这条**非有不可**：`sensitivity` 是**卡作者的声明**，不是**内容的属性**（不写 = 默认 `public`）
    ⇒ 缺本判据时，"一张写 `public` 的卡带未发表内容出网"**没有任何机制知道**（§13.2 的实测结论）。
    """
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 input-provenance 断言", []
    if not SENSITIVITY_INV.exists():
        return "FAIL", "inventory/sensitivity.yaml 缺失（本断言的登记依据）", []
    try:
        inv = yaml.safe_load(SENSITIVITY_INV.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return "FAIL", f"sensitivity.yaml 解析失败: {type(e).__name__}: {e}", []
    cards = []
    for p in sorted(ROOT.glob(CARD_GLOB)):
        if p.name.lower() == "readme.md":
            continue
        fm = _card_frontmatter(p)
        if fm is None:
            continue
        try:
            body = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            body = ""
        cards.append((p.relative_to(ROOT).as_posix(), fm, body))
    fail, warn, st = validate_input_provenance(cards, inv)
    note = (f"卡 {st['cards']} 张 · 触发 {st['triggered']} 张（attach-egress ∧ public/sanitized）"
            f" · 合规 {st['ok']} · 声明 {PROVENANCE_NONE} {st['none']}")
    if fail:
        return "FAIL", note, fail + (["", "⚠ 以下为 WARN 级（不阻断）："] + warn if warn else [])
    if warn:
        # 规则 ④ 属"提到≠读到"⇒ 只报不拦（本仓 WARN 语义：执行后有非阻断发现）
        return "WARN", note + " · ⚠ none 可证伪性存疑 " + str(len(warn)), warn
    return "PASS", note, []



# ── P1-3 `facade`：`cluster.py` 必须**可达**其消费者引用的每一个 `cluster.<符号>` ──────────
FACADE = ROOT / "ops" / "cluster.py"
# 消费形态两种：`import cluster`（用 `cluster.<x>`）与 `import cluster as C`（用 `C.<x>`）
_FACADE_CONSUMER_RE = re.compile(r"^\s*import\s+cluster(?:\s+as\s+([A-Za-z_]\w*))?\s*$", re.M)
_FACADE_DIRS = ("ops", "tests")     # ★ tests 也是契约消费者（实测: test_inbox_seal 用 cluster.INBOX_ROOT 等）


def _strip_py_prose(text):
    """剥掉 `#` 注释与字符串字面量（含 docstring）—— **本仓纪律**：扫代码文本的断言必须区分"代码"与"注释"。

    ⚠ 为什么必须：首版只用正则扫原文 ⇒ 把**文档/注释里出现的 `cluster.py`** 当成引用（抽出符号 `py`）
    ⇒ **假红**。这与 D7-P1-1 那次（"已移除此项"的留档注释让断言假红）是**同一型**的坑。
    strings 用空格占位（避免把两侧代码粘成一个 token）；不做完整词法，够用即可。
    """
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == "#":
            while i < n and text[i] != "\n":
                i += 1
        elif c in "\"'":
            q, triple = c, text[i:i + 3] in ('"""', "'''")
            if triple:
                i += 3
                while i < n and text[i:i + 3] != q * 3:
                    i += 1
                i += 3
            else:
                i += 1
                while i < n and text[i] != q:
                    i += 2 if text[i] == "\\" else 1
                i += 1
            out.append(" ")
        else:
            out.append(c)
            i += 1
    return "".join(out)


def facade_names(text):
    """静态提取 `cluster.py` 对外的**可达名**（三种来源：定义 / 顶层赋值 / 导入重导出）。"""
    names = set(re.findall(r"^def\s+([A-Za-z_]\w*)", text, re.M))
    names |= set(re.findall(r"^class\s+([A-Za-z_]\w*)", text, re.M))
    names |= set(re.findall(r"^([A-Za-z_]\w*)\s*(?::[^=\n]+)?=", text, re.M))
    for braced, plain in re.findall(r"^from\s+[\w.]+\s+import\s+(?:\(([^)]*)\)|([^\n#]+))", text, re.M):
        for seg in (braced or plain or "").split(","):
            n = seg.strip().split(" as ")[-1].strip()
            if re.fullmatch(r"[A-Za-z_]\w*", n or ""):
                names.add(n)
    return names


def validate_facade(consumer_refs, names):
    """**纯函数**：`consumer_refs = {消费者文件名: {符号,...}}`、`names = 门面可达名集` ⇒ 离线可正反夹测。

    P1-3 的定性：本仓已拆出 5 个模块，`cluster_web.py` 用 `import cluster` 复用其符号
    ⇒ **这是一个跨文件的隐式契约**（门面重导出），而**此前门禁 19 项无一检查它**
    ⇒ 谁把符号搬走/改名，`cluster_web.py` 只在**运行到那条路径时**才炸。

    返回 `(bad, stats)`；`stats` 报**覆盖率**（消费者数 / 引用的不同符号数）。
    """
    bad = []
    all_syms = set()
    for consumer, refs in sorted(consumer_refs.items()):
        all_syms |= refs
        for s in sorted(refs):
            if s not in names:
                # 点名：**哪个符号 · 被谁引用**（照 `scripts` 断言"改了没登记就 FAIL 并点名"的成功范式）
                bad.append(f"{consumer} 引用的 cluster.{s} **在门面不可达**（搬走/改名/漏重导出？）")
    # 反向信息（不判死）：门面里"没有任何消费者引用"的名字 —— 只报数，便于日后清理
    orphan = sorted(n for n in names if n not in all_syms and not n.startswith("_"))
    return bad, {"consumers": len(consumer_refs), "syms": len(all_syms), "orphan": len(orphan)}


def check_facade(ctx):
    """P1-3：`cluster.py` 门面符号**可达性**（跨文件隐式契约的唯一机器约束）。"""
    if not FACADE.exists():
        return "FAIL", "ops/cluster.py 缺失（门面本体）", []
    consumer_refs = {}
    for d in _FACADE_DIRS:
        for p in sorted((ROOT / d).glob("*.py")):
            if p.name == FACADE.name or p.name.startswith("cluster_"):
                continue      # 门面自身 / 已拆出的子模块（后者用 `from cluster_xxx import`，不走门面）
            txt = _strip_py_prose(p.read_text(encoding="utf-8", errors="replace"))
            m = _FACADE_CONSUMER_RE.search(txt)
            if not m:
                continue      # 不 import cluster 的文件不构成门面契约（如 rpc_check.py 走子进程）
            alias = m.group(1) or "cluster"
            refs = {x for x in re.findall(rf"\b{re.escape(alias)}\.([A-Za-z_]\w*)", txt)
                    if not x.startswith("__")}
            if refs:
                consumer_refs[f"{d}/{p.name}"] = refs

    names = facade_names(_strip_py_prose(FACADE.read_text(encoding="utf-8", errors="replace")))
    bad, st = validate_facade(consumer_refs, names)
    note = (f"消费者 {st['consumers']} 个 · 引用不同符号 {st['syms']} 个 · 门面可达名 {len(names)} 个 "
            f"· 无消费者引用(仅报数) {st['orphan']} 个")
    return ("FAIL" if bad else "PASS"), note, bad


# ── D6-P1-2 M-1：`事实源 ↔ 镜像` 一致性（当前 1 处合格镜像：判官行）─────────────────────
MANUAL = ROOT / "docs" / "三机推理集群使用手册.md"
AGENT_CLI = ROOT / "ops" / "station-bin" / "agent-cli.ps1"
# M-5/M-6: 受理状态机「单一真值」及其文档镜像
INBOX_TRUTH_YAML = ROOT / "inventory" / "inbox.yaml"
INBOX_README = ROOT / "inbox" / "README.md"


def read_inbox_truth(path):
    """读受理状态机「单一真值」(`inventory/inbox.yaml` 的 `states:` 段) -> {state: {group, next}}。

    **纯函数**(只依赖传入路径): 便于单测与注入(正反用例)。
    失败**不静默兜底**(抛出) —— 由调用方报 FAIL / 由 check_inbox 落到空白名单(fail-closed)。
    """
    import yaml
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    states = data.get("states") if isinstance(data, dict) else None
    if not isinstance(states, dict):
        raise ValueError(f"{path} 缺 `states:` 映射段")
    return states


# 受理"必需件"键(requires)的封闭枚举 —— 与 inventory/inbox.yaml 的注释同步
INBOX_REQUIRES_KEYS = {"decide", "plan", "evidence", "manifest"}
# 看板徽章(badge)的封闭枚举 —— 与 inventory/inbox.yaml 同步 (cluster_web 注入前端)
INBOX_BADGE_VALUES = {"ok", "warn", "err", "none"}


def inbox_requires_sets(states, key):
    """**纯函数**: 从真值 `requires` 派生"需要某类件"的状态集。

    D6-P1-2 #7: check_inbox 原有 **4 处硬编码状态子集**, 现全部由真值派生(副本消失)。
    """
    return {s for s, sp in states.items() if key in ((sp or {}).get("requires") or [])}


def read_judge_main(text):
    """从 `agent-cli.ps1` 读 `JUDGE_TABLE['main']` 的三个契约字段（id / egress / compliance）。"""
    m = re.search(r"'main'\s*=\s*@\{([^}]*)\}", text)
    if not m:
        return None
    blob = m.group(1)

    def kv(key):
        mm = re.search(rf"{key}\s*=\s*([^;]+?)(?:\s*;|$)", blob)
        # `$false` ⇒ `false`：PS 的 `$` 前缀在手册里写作裸值，规范化后再比
        return mm.group(1).strip().strip("'\"") if mm else None
    return {k: (kv(k) or "").replace("$", "") for k in ("id", "egress", "compliance")}


def validate_mirror(judge, row):
    """**纯函数**：手册判官行 vs `JUDGE_TABLE['main']` —— 离线可正反夹测。

    P1-2 的定性（取证后大幅收窄）：原以为是"多组镜像"，实测**合格的只有 1 处** ——
    手册 §1.3 的判官行 vs `JUDGE_TABLE['main']`（**指向未来**：改一处而另一处不跟 ⇒ 运行时行为与文档不符）。
    其余（`ROUTE_TABLE`→手册 §2.2 / `ports.yaml`→手册 §1.2）已**显式豁免**（历史记档 / 精选视图）。
    ⚠ M-2（台账"剩余 open"↔手册"= 4 项"）**不在此断言内** —— 已由 **O-50** 裁定为"手册不再维护第二份枚举"
    ⇒ 加断言只会造一条**恒 WARN 的噪音**（对一个已决定不同步的数）。**这是分析结论，不是遗漏。**
    """
    bad = []
    if not judge:
        return ["agent-cli.ps1 里读不出 JUDGE_TABLE['main']（表结构变了？）"], {"n": 0}
    # ⚠ **每键的比对形态不同**（首版统一用 `k=v` ⇒ 对 `id` 造成**假红**：手册写的是
    #   `` `main-opencode-cli` ``（裸 id，无 `id=` 前缀）⇒ 判据必须尊重**各自自然的书写形态**，
    #   否则"判据本身在制造不一致"。egress/compliance 在手册里确实写作 `key=value`，故按该形态查。
    forms = (("id", lambda k, v: v in row),
             ("egress", lambda k, v: f"egress={v}" in row),
             ("compliance", lambda k, v: f"compliance={v}" in row))
    for k, hit in forms:
        v = judge.get(k)
        if not v:
            bad.append(f"JUDGE_TABLE['main'].{k} 读不出（值={v!r}）—— 事实源本身不可读")
        elif not hit(k, v):
            bad.append(f"手册 §1.3 判官行与事实源不一致：事实源 `{k}={v}`，"
                       f"但该串**未出现在**手册判官行里（改一处忘改另一处？）")
    return bad, {"n": 3}


def validate_inbox_mirror(states, readme_text):
    """**纯函数**: 受理状态机真值 ↔ README §3 白名单/状态表 + 真值自洽 (M-5/M-6)。

    收敛后(D6-P1-2)白名单/下一动作/分组都来自 `inventory/inbox.yaml` —— 两处代码**同源**,
    于是"两端白名单相等"退化为**恒真**(这就是假绿); **真正的漂移点是文档**:
    README §3 不能自动消费, 改了真值忘改文档不会报错。故此处补三道:
      · 真值自洽: 每态有 group ∈ {action,active,closed} + 非空 next
        (缺 group ⇒ 分组静默落进 closed = 真静默缺口; 缺 next ⇒ M-6 的键集缺口)
      · README §3「合法取值白名单」 == 真值键集 (= M-5 本体)
      · README §3 状态表首列 == 真值键集
    """
    bad = []
    for name, spec in sorted(states.items()):
        spec = spec or {}
        if spec.get("group") not in ("action", "active", "closed"):
            bad.append(f"inbox.yaml: 状态 {name!r} 的 group={spec.get('group')!r} 不合法 "
                       f"(须 ∈ action/active/closed; 缺省会静默落进 closed)")
        if not spec.get("next"):
            bad.append(f"inbox.yaml: 状态 {name!r} 缺 next (加了状态忘加下一动作 = M-6)")
        rq = spec.get("requires")
        if not isinstance(rq, list):
            bad.append(f"inbox.yaml: 状态 {name!r} 缺 requires 列表 "
                       f"(否则该态的『必需件』规则会**静默不适用**)")
        else:
            unk = sorted(set(rq) - INBOX_REQUIRES_KEYS)
            if unk:
                bad.append(f"inbox.yaml: 状态 {name!r} 的 requires 含未知键 {unk} "
                           f"(合法: {sorted(INBOX_REQUIRES_KEYS)})")
        if spec.get("badge") not in INBOX_BADGE_VALUES:
            bad.append(f"inbox.yaml: 状态 {name!r} 的 badge={spec.get('badge')!r} 不合法 "
                       f"(须 ∈ {sorted(INBOX_BADGE_VALUES)}; 前端徽章由它派生)")
    keys = set(states)
    # 只在 §3 段落内找白名单行/状态表(避免误抓别节里同形的表)
    sec = re.search(r"##\s*3\..*?(?=\n##\s)", readme_text, re.S)
    if not sec:
        bad.append("README 定位不到 §3 段落(标题结构改了?)")
    text = sec.group(0) if sec else readme_text
    m = re.search(r"合法取值白名单\*\*[:：]\s*(.+)", text)
    if not m:
        bad.append("README §3 找不到『合法取值白名单』行(文档结构改了?)")
    else:
        doc = set(re.findall(r"`([^`]+)`", m.group(1)))
        if doc != keys:
            bad.append(f"README §3 白名单与真值不一致: 文档多 {sorted(doc - keys)} / "
                       f"少 {sorted(keys - doc)} (改一处忘改另一处?)")
    tbl = set(re.findall(r"^\|\s*`([^`]+)`\s*\|", text, re.M))
    if tbl and tbl != keys:
        bad.append(f"README §3 状态表与真值不一致: 表多 {sorted(tbl - keys)} / "
                   f"少 {sorted(keys - tbl)}")
    return bad


def validate_manual_states(states, manual_text):
    """**纯函数**: 手册 §1.3 的「受理区位置 … 状态机」段必须**逐个提到**真值的每个状态 (#9)。

    D6-P1-2 #9: 手册是**对外契约母版**(Paper 项目 agent 据此写下游文档); 实测原图**漏了 `rejected`**
    (11/12 态)。此处只做 **⊇ 方向**(真值 ⊆ 手册) —— 手册与 README 图同族, 都是**主路径精选视图**,
    做"12 态全等"会**假红**(同 M-3 `ROUTE_TABLE` / M-4 ports 的豁免理由)。
    """
    m = re.search(r"受理区位置.*?受理流程与状态机见", manual_text, re.S)
    if not m:
        return ["手册 §1.3 定位不到『受理区位置 … 受理流程与状态机见』段(结构改了?)"]
    blk = m.group(0)
    miss = [s for s in sorted(states)
            if not re.search(rf"(?<![a-z\-]){re.escape(s)}(?![a-z\-])", blk)]
    if miss:
        return [f"手册 §1.3 状态机段漏了状态 {miss} (对外契约不全; 改真值后忘改手册?)"]
    return []


def validate_readme_requires(states, readme_text):
    """**纯函数**: README §5.3「交付态强判据」行 == 真值里 `requires` 含 `manifest` 的状态集。

    ⚠ 只钉**这一行**(它本就是精确枚举)。§5.3 其余用 `accepted+`/`release+` 的"+"记法是**有损人读摘要**,
    不做全等对账(会假红) —— 精确集由代码侧 `inbox_requires_sets` 从真值派生, 不靠文档。
    """
    want = inbox_requires_sets(states, "manifest")
    m = re.search(r"交付态强判据[^\n]*", readme_text)
    if not m:
        return ["README §5.3 找不到『交付态强判据』行(结构改了?)"]
    got = set(re.findall(r"`([^`]+)`", m.group(0)))
    if got != want:
        return [f"README §5.3『交付态强判据』行与真值不一致: 文档多 {sorted(got - want)} / "
                f"少 {sorted(want - got)}"]
    return []


# 手册 §2.4 的断言计数声明行（形如 `# 24 项断言 (quick 17 + 全量 7):`）
MANUAL_COUNT_RE = re.compile(r"#\s*(\d+)\s*项断言\s*\(quick\s*(\d+)\s*\+\s*全量\s*(\d+)\)")
# O-50：手册**不得**再长出"第二份枚举 / 写死计数" —— 这两类句式 = 同一事实两处定义
_MANUAL_BANNED = (
    (re.compile(r"真实剩余\s*open[^\n]{0,24}?=\s*[0-9]+\s*项"),
     "手册又出现『真实剩余 open = N 项』的**枚举式声明**（应指向 OPEN-ISSUES §1，别再抄一份）"),
    (re.compile(r"门禁\s*[0-9]+\s*绿"),
     "手册又**写死了门禁计数**（应指向 `rpc.ps1 check` 的当场自报）"),
)


def validate_manual_counts(manual_text, checks):
    """**纯函数**（O-50）：手册声明的断言计数 == 真实 `CHECKS`；并禁止第二份枚举/写死计数。

    为什么这样做（而不是像 M-2 那样对账"台账剩余项数"）：
      · **台账条数**每批都变 ⇒ 对账它只会造一条**恒 WARN 的噪音**（O-50 已判：手册**不再维护第二份枚举**）；
      · **断言项数**只在"加/删断言"时变，且**那时就该改手册** ⇒ 对账它是**精确、非噪音**的。
    ⇒ 把"手册计数会漂移"从空头承诺变成**机判**，同时用反向护栏堵住"再抄一份枚举"。
    """
    bad = []
    m = MANUAL_COUNT_RE.search(manual_text)
    if not m:
        bad.append("手册 §2.4 找不到『# N 项断言 (quick Q + 三站 S)』声明行（结构改了？）")
    else:
        n, q, s = (int(x) for x in m.groups())
        real = len(checks)
        rq = sum(1 for c in checks if c.get("quick"))
        rs = real - rq
        if (n, q, s) != (real, rq, rs):
            bad.append(f"手册声明的断言计数 ({n} = quick {q} + 三站 {s}) 与真实不符 "
                       f"(真实 {real} = quick {rq} + 三站 {rs}) ⇒ **加/删断言后忘了改手册 §2.4**")
        elif n != q + s:
            bad.append(f"手册计数**自相矛盾**: {n} ≠ quick {q} + 三站 {s}")
    for rx, why in _MANUAL_BANNED:
        mm = rx.search(manual_text)
        if mm:
            bad.append(f"{why}（命中 {mm.group(0)[:40]!r}）")
    return bad


def check_mirror(ctx):
    """P1-2: 事实源 ↔ 镜像 一致性 —— 2 处合格镜像(判官行 M-1 / 受理状态机 M-5+M-6+#7#9)。"""
    if not AGENT_CLI.exists() or not MANUAL.exists():
        return "WARN", "缺 agent-cli.ps1 或手册，跳过镜像断言", []
    bad = []
    manual_text = MANUAL.read_text(encoding="utf-8", errors="replace")
    # ── M-1: 手册 §1.3 判官行 ↔ `JUDGE_TABLE['main']` ─────────────────
    judge = read_judge_main(AGENT_CLI.read_text(encoding="utf-8", errors="replace"))
    row = next((l for l in manual_text.splitlines() if "JUDGE_TABLE['main']" in l), "")
    if not row:
        bad.append("手册 §1.3 里找不到判官行（`JUDGE_TABLE['main']` 那行）")
    else:
        bad += validate_mirror(judge, row)[0]
    # ── O-50: 手册的断言计数 == CHECKS（+ 禁"第二份枚举/写死计数"）─────────
    bad += validate_manual_counts(manual_text, CHECKS)
    # ── M-5/M-6 + #7/#9: 受理状态机真值 ↔ README §3 / 手册 §1.3 + 两处代码同源 ──
    n_state = 0
    if not INBOX_TRUTH_YAML.exists() or not INBOX_README.exists():
        bad.append("缺 inventory/inbox.yaml 或 inbox/README.md（状态机真值 / 文档镜像不在）")
    else:
        try:
            states = read_inbox_truth(INBOX_TRUTH_YAML)
        except Exception as e:
            bad.append(f"inventory/inbox.yaml 读不出（真值源坏了）: {e}")
        else:
            n_state = len(states)
            readme_text = INBOX_README.read_text(encoding="utf-8", errors="replace")
            bad += validate_inbox_mirror(states, readme_text)
            bad += validate_readme_requires(states, readme_text)
            bad += validate_manual_states(states, manual_text)
            # 两处代码**消费同一真值**(防"回归硬编码"): 直接核对运行时集合
            sys.path.insert(0, str(ROOT / "ops"))
            try:
                import cluster_web
                for nm, got in (("cluster_web.INBOX_STATES", set(cluster_web.INBOX_STATES)),
                                ("cluster_web._INBOX_NEXT", set(cluster_web._INBOX_NEXT))):
                    if got != set(states):
                        bad.append(f"{nm} 与真值不一致: 多 {sorted(got - set(states))} / "
                                   f"少 {sorted(set(states) - got)}（回归硬编码?）")
            except Exception as e:
                bad.append(f"导入 cluster_web 失败, 无法核对状态机消费面: {e}")
    j = judge or {}
    note = (f"合格镜像 2 处（判官行 3 字段 + 受理状态机 {n_state} 态 ↔ README §3/手册 §1.3/两处代码"
            f"+ 手册断言计数 ↔ CHECKS）· 事实源 id={j.get('id')} "
            f"egress={j.get('egress')} compliance={j.get('compliance')}")
    return ("FAIL" if bad else "PASS"), note, bad


# ── 断言: 文档内链接可达 (文档漂移的机械防线) ─────────────────────────
# 触发背景 (2026-09-15, ADR-0004 第四批"文档漂移审计"): 用户提出"三站配置实况与手册/派发表
# 存在漂移", 机械扫描全部 144 个 md 后查出 **65 条失效的仓库内相对链接** —— 典型两类:
#   ① 前缀写重: `spec/<x>/` 里写 `../spec/y` ⇒ 解析成 `spec/spec/y`; `../docs/z` 同理
#   ② 实体移动后未跟进: 脚本进 archive/、文档进 research/、C 站 IP/端口变更
# 这类漂移**此前没有任何门禁拦得住**, 只能靠人工翻文档 ⇒ 补此断言。
#
# 判据 (可机械判定, 零主观):
#   · 只查**仓库内相对链接** (http/https/mailto/#锚点/file:/// 一律不查)
#   · 解析后仍在仓库内、且路径不存在 ⇒ 记一条失效
#   · 解析后落到仓库外 (如 `../../../x`)、含占位符 (空格 / `...` / `url`) 或绝对盘符
#     ⇒ **跳过** (目标不可判定, 报出来是噪声)
# 真实差异可登记进 DOCLINK_ALLOW, 但**登记动作在 review 里必须可见** (同 known_drift 纪律)。
DOCLINK_ALLOW = {
    # (相对仓库根的 md 路径, 失效目标) -> 原因
    ("ops/agent-skills/what-if-oracle/SKILL.md", "references/scenario-templates.md"):
        "vendored 技能只收 SKILL.md, 其 references/ 未随仓库分发 (非本仓库文档漂移)",
}
DOCLINK_SKIP_PARTS = {".git", "node_modules", ".trae", "archive", "tmp"}
DOCLINK_LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


def _doclink_bad(p, base):
    """返回 (是否失效, 是否可判定, 原因)。可判定=解析后落在仓库内，**或相对链接越出仓库根**。

    ⚠ 2026-09-22（决策简报 A）：原先"越界 ⇒ 不可判定"把**两类东西混进同一个桶** ——
      (a) 合法但不可判的：http/占位词/Windows 绝对盘符/指向仓库外的**绝对**路径；
      (b) **真错误：相对链接的 `..` 写多了、越出仓库根**。
    (b) 用**纯路径运算**就能判（与目标文件是否存在无关），而 09-16 那 27 条 `../../` 漏网**正是落在它里**
    ⇒ 故拆开：(b) 判 FAIL，(a) 仍保持不可判。**影响面实测 = 2 条、误报面 = 0**（"越界的非相对形态" 0 例）。
    """
    if base.startswith(("http://", "https://", "mailto:", "file:///", "#")):
        return False, False, ""
    if not base or " " in base or "..." in base or base in ("url", "path", "link"):
        return False, False, ""
    if len(base) > 1 and base[1] == ":":          # Windows 绝对盘符
        return False, False, ""
    q = os.path.normpath(str(p.parent / base))
    root = os.path.normpath(str(ROOT))
    if not q.lower().startswith(root.lower() + os.sep):
        flat = base.replace("\\", "/")
        if flat.startswith("..") or "/.." in flat:
            return True, True, "越出仓库根(相对链接层级写多)"
        return False, False, ""                   # 落到仓库外的**非相对**形态 ⇒ 不可判定
    return (not Path(q).exists()), True, ("目标不存在" if not Path(q).exists() else "")


def check_doclinks(ctx):
    """文档链接可达: md 里的仓库内相对链接不得指向不存在的路径。"""
    n_md = n_link = n_bad = n_allow = n_skip = 0
    bad = []
    allow_hit = set()          # D6-P0-2: 记录**实际命中**的豁免键（未命中的要自报）
    for p in sorted(ROOT.rglob("*.md")):
        rel = p.relative_to(ROOT)
        if any(s in rel.parts for s in DOCLINK_SKIP_PARTS):
            continue
        n_md += 1
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for m in DOCLINK_LINK.finditer(line):
                base = m.group(2).strip().split("#")[0]
                n_link += 1
                hit, judgeable, reason = _doclink_bad(p, base)
                if not judgeable:
                    n_skip += 1
                    continue
                if not hit:
                    continue
                if (rel.as_posix(), base) in DOCLINK_ALLOW:
                    n_allow += 1
                    allow_hit.add((rel.as_posix(), base))
                    continue
                n_bad += 1
                bad.append((f"{rel.as_posix()}:{i}", base, reason))

    detail = []
    for loc, base, why in bad:
        detail.append(f"{loc}  ->  {base}" + (f"   【{why}】" if why else ""))
    # D6-P0-2: 豁免**未命中**（该处已不再失效）⇒ **自报**，否则清单腐化无人知
    _unhit = allow_unhit(list(DOCLINK_ALLOW), allow_hit)
    for key in _unhit:
        detail.append(f"(豁免**未命中**) {key[0]}  ->  {key[1]} —— {DOCLINK_ALLOW[key]} ⇒ "
                      f"该链接已不再失效 ⇒ **该豁免已可移除**")
    note = (f"扫描 {n_md} 个 md · 链接 {n_link} 条 (其中非仓库内相对链接/占位词 {n_skip} 条不判) "
            f"· 已登记例外 {n_allow} · 失效 {n_bad}")
    if _unhit:
        note += f" · ⚠ 豁免未命中 {len(_unhit)} 条（已可移除，见明细）"
    return ("FAIL" if n_bad else ("WARN" if _unhit else "PASS")), note, detail


# ── 断言: cluster 模块依赖方向 (D6-P2-1) ─────────────────────────────
# 目的: `cluster_*.py` 拆出 5 个模块后, "谁能 import 谁"原先**无任何约束** ⇒ 反向依赖会悄悄长回来。
# ★ 必须用 **AST** 而不是正则区分两类 import —— 正则分不清"这行 in 不 in 函数里", 会把两类混成一个桶
#   （本仓头号失败形态），而两者**语义不同**：
#   · **模块级** import = **导入期**依赖 ⇒ 有环 ⇒ `import` 当场就炸 ⇒ **真环, FAIL**；
#   · **函数内懒加载** import = **运行期**耦合 ⇒ 不构成导入环（它是**刻意打破环**的手段），
#     但**反向**（越层）懒加载仍是设计越界 ⇒ **未登记即 FAIL**（登记后 PASS，未命中会自报"已可移除"）。
CLUSTER_GLOB = "cluster*.py"
CLUSTER_LAYER_KEY = "cluster_layers"
CLUSTER_LAZY_ALLOW_KEY = "cluster_lazy_allow"


def _mods_of(node):
    """从单个 Import/ImportFrom 节点取模块名（`from . import x` 的相对形态不取）。"""
    if isinstance(node, ast.Import):
        return {a.name for a in node.names}
    if node.level == 0 and node.module:
        return {node.module}
    return set()


def _collect_imports(node, into):
    """递归收集 import，但**不进入函数体**（函数体里的 import 属"懒加载"，另行收集）。"""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if isinstance(child, (ast.Import, ast.ImportFrom)):
            into |= _mods_of(child)
            continue
        _collect_imports(child, into)


def cluster_dep_edges(text):
    """**纯函数**: 源码 → `(模块级边, 懒加载边)`（模块名 set；**未**过滤"是否本组模块"）。"""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return set(), set()
    top = set()
    _collect_imports(tree, top)
    lazy = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _collect_imports(n, lazy)      # 该函数体(含嵌套块)里的 import；再嵌套的函数由外层 walk 覆盖
    return top, lazy


def cluster_dep_graph(sources):
    """**纯函数**: `{模块名: 源码}` → `{"top": {u:{v}}, "lazy": {u:{v}}}`（只保留**组内**边，去自环）。"""
    g = {"top": {}, "lazy": {}}
    for name, text in sources.items():
        t, l = cluster_dep_edges(text)
        g["top"][name] = {v for v in t if v in sources and v != name}
        g["lazy"][name] = {v for v in l if v in sources and v != name}
    return g


def find_cycles(graph):
    """**纯函数**: 有向图找环 ⇒ `[[n1,n2,…,n1], …]`（DFS 三色；按名排序保证结论**确定**）。"""
    color = {n: 0 for n in graph}
    stack, cycles = [], []

    def dfs(u):
        color[u] = 1
        stack.append(u)
        for v in sorted(graph.get(u, ())):
            if color.get(v) == 1:
                cycles.append(stack[stack.index(v):] + [v])
            elif color.get(v) == 0:
                dfs(v)
        stack.pop()
        color[u] = 2

    for n in sorted(color):
        if color[n] == 0:
            dfs(n)
    return cycles


def validate_cluster_deps(graph, layers, lazy_allow):
    """**纯函数** → `(bad, notes, unhit)`。

    `layers` = 按层从底到顶的 `[[路径,…], …]`；`lazy_allow` = `[[上游, 下游, 原因], …]`。
    规则：① 新模块**必须**在 layers 登记层次；② 模块级图**不得成环**；③ 模块级边**只能向下**（严格下层）；
    ④ **反向**懒加载必须登记（未登记 ⇒ FAIL）；⑤ 已登记但**未命中** ⇒ `unhit`（自报"已可移除"，同 P0-2 纪律）。
    """
    bad, notes, unhit = [], [], []
    lvl = {}
    for i, layer in enumerate(layers):
        for p in layer:
            lvl[Path(p).stem] = i
    # ① 未登记模块 ⇒ 新模块必须声明站在哪一层
    for m in sorted(graph["top"]):
        if m not in lvl:
            bad.append(f"{m}: **未在 inventory/ops.yaml 的 `{CLUSTER_LAYER_KEY}` 登记层次** "
                       f"⇒ 新模块必须显式声明站在哪一层（否则依赖方向无人约束）")
    # ② 成环（模块级 = 导入期依赖 ⇒ 真环）
    for cyc in find_cycles(graph["top"]):
        bad.append(f"**模块级 import 成环**: {' → '.join(cyc)} ⇒ 导入期就会炸"
                   f"（要么拆环，要么把其中一条改成函数内懒加载 + 登记）")
    # ③ 层序：模块级边必须指向**严格下层**
    for u, vs in sorted(graph["top"].items()):
        for v in sorted(vs):
            if u in lvl and v in lvl and lvl[v] >= lvl[u]:
                bad.append(f"**层序越界**: {u}(L{lvl[u]}) → {v}(L{lvl[v]}) —— 只允许依赖**严格下层**")
    # ④ 反向懒加载：不构成环，但仍是越层 ⇒ 须登记
    allow = {(Path(a).stem, Path(c).stem): msg for a, c, msg in lazy_allow}
    hit = set()
    for u, vs in sorted(graph["lazy"].items()):
        for v in sorted(vs):
            if u in lvl and v in lvl and lvl[v] >= lvl[u]:
                if (u, v) in allow:
                    hit.add((u, v))
                    notes.append(f"反向懒加载**已登记**: {u}(L{lvl[u]}) → {v}(L{lvl[v]})")
                else:
                    bad.append(f"**未登记的反向懒加载**: {u}(L{lvl[u]}) → {v}(L{lvl[v]}) "
                               f"⇒ 要么调层，要么在 `{CLUSTER_LAZY_ALLOW_KEY}` 登记原因")
    unhit = allow_unhit(list(allow), hit)
    return bad, notes, unhit


def check_cluster_deps(ctx):
    """P2-1: `cluster_*.py` 依赖方向（未登记模块 / 成环 / 层序越界 / 反向懒加载）。"""
    files = sorted(ROOT.glob(f"ops/{CLUSTER_GLOB}"))
    if not files:
        return "WARN", f"ops/{CLUSTER_GLOB} 无匹配（本断言的登记依据）", []
    src = {p.stem: _read_text(p) for p in files}
    try:
        import yaml          # 与本文件其它断言一致: 函数内导入 ⇒ 缺 pyyaml 时降级而不是整仓报错
    except ImportError:
        return "WARN", "未安装 pyyaml ⇒ 层序无依据（跳过；装上后自动生效）", []
    try:
        inv = yaml.safe_load(OPS_INV.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return "WARN", f"inventory/ops.yaml 不可读 ⇒ 层序无依据: {type(e).__name__}: {e}", []
    layers = inv.get(CLUSTER_LAYER_KEY) or []
    if not layers:
        return "WARN", f"inventory/ops.yaml 缺 `{CLUSTER_LAYER_KEY}` ⇒ 层序无依据（不判）", []
    graph = cluster_dep_graph(src)
    bad, notes, unhit = validate_cluster_deps(graph, layers, inv.get(CLUSTER_LAZY_ALLOW_KEY) or [])
    for k in unhit:
        notes.append(f"⚠ 登记的反向懒加载**未命中**（已可移除）: {k[0]} → {k[1]}")
    n_top = sum(len(v) for v in graph["top"].values())
    n_lazy = sum(len(v) for v in graph["lazy"].values())
    detail = ["层序(底→顶): " + " < ".join("{" + ", ".join(Path(x).stem for x in l) + "}" for l in layers)]
    detail += bad + notes
    note = (f"模块 {len(src)} 个 · 层序 {len(layers)} 层 · 模块级边 {n_top} 条 · "
            f"懒加载边 {n_lazy} 条 · 违规 {len(bad)}")
    if unhit:
        note += f" · ⚠ 未命中登记 {len(unhit)}（已可移除）"
    return ("FAIL" if bad else ("WARN" if unhit else "PASS")), note, detail


# ── 断言: ADR 必留"考虑的替代方案" (D6-P2-2) ──────────────────────────
# 目的: ADR 是"非平凡改动必留决策"的载体; 而"**当时考虑过/否决了哪些方案**"最容易被**静默省略**
#   （写"我决定做什么"容易，写"我否掉了什么"难）⇒ 它是决策记录里**最该被机器盯住**的那一项。
# ★ 锚 = ADR 模板的**现名** `考虑的替代方案（Alternatives Considered）`（见 `spec/vulkan-version-control/ADR_TEMPLATE.md`；
#   ADR-0001/0002 与它同源，其余 6 份于 2026-09-25 由 `否决/比较对象` / `被否的方案` **改名**统一，内容未改）。
#   比较前**规范化**（去括号内容 / 空白 / 全半角）⇒ 防"半角括号 typo"这类**假红**（ADR-0001 历史形态）。
# ⚠ **范围只含 `adr/ADR-*.md`**，**不含** `spec/d6-agent-standard/DECISIONS.md` —— 后者是**表格载体**，
#   "否决/比较对象"是它的**列**（表格在结构上每行都有该槽位，且值可为 `—` 表"确无替代"）⇒
#   门禁的价值在**形状无保证**处；硬要求它也"非空"会假红（实测 D-02 / D-09 该列 = `—`）。
ADR_GLOB = "ADR-*.md"
ADR_DIR = ROOT / "adr"
ADR_CANON = "考虑的替代方案"
ADR_LEGACY = ("否决/比较对象", "被否的方案")


def _norm_head(s):
    """规范化标题用于比较：去括号内容 + 去空白 + 统一全半角括号 ⇒ 只留中文核心词。"""
    s = s.replace("（", "(").replace("）", ")")
    return re.sub(r"\s+", "", re.sub(r"\(.*?\)", "", s))


def validate_adr(text):
    """**纯函数** → `(bad, notes)`。

    规则（P2-2）：① **恰 1 个**规范节 `考虑的替代方案`；② 节体**非空**（≥1 列表项 **或** ≥2 表格行 = 表头+数据）；
    ③ **不得**留旧节名（`否决/比较对象` / `被否的方案`）。
    ⚠ 节体扫描**只到下一个二级标题为止** —— `### 替代方案 A` 是**子节**、属节体（ADR-0001/0002 的节体**全是**子节），
      若按"任意标题"截断会把它们判成空节。
    """
    lines = text.splitlines()
    heads = [(i, ln.strip()) for i, ln in enumerate(lines)
             if ln.startswith("## ") and not ln.startswith("### ")]
    canon = [(i, raw) for i, raw in heads if _norm_head(raw[3:]) == ADR_CANON]
    bad, notes = [], []
    for i, raw in heads:
        if _norm_head(raw[3:]) in {_norm_head(x) for x in ADR_LEGACY}:
            bad.append(f"第 {i + 1} 行仍是**旧节名** `{raw}` ⇒ "
                       f"统一为 `## {ADR_CANON}（Alternatives Considered）`")
    if not canon:
        bad.append(f"**缺** `## {ADR_CANON}（Alternatives Considered）` 节 ⇒ "
                   f"非平凡改动必须写明**考虑过 / 否决了哪些方案**")
        return bad, notes
    if len(canon) > 1:
        bad.append(f"有 **{len(canon)}** 个规范节（行 {[i + 1 for i, _ in canon]}）⇒ "
                   f"只允许 1 个（改名后残留旧节？）")
    i0 = canon[0][0]
    body = []
    for ln in lines[i0 + 1:]:
        if ln.startswith("# ") or (ln.startswith("## ") and not ln.startswith("### ")):
            break
        body.append(ln)
    n_item = sum(1 for b in body if re.match(r"^\s*(?:[-*+]|\d+\.)\s+\S", b))
    n_row = sum(1 for b in body
                if b.strip().startswith("|") and not re.match(r"^\s*\|[\s:|-]+\|\s*$", b))
    if n_item == 0 and n_row < 2:
        bad.append(f"第 {i0 + 1} 行 `## {ADR_CANON}…` 节**是空的**（列表项 {n_item} · 表格行 {n_row}）"
                   f"⇒ 只写了标题没写内容（需 ≥1 列表项 **或** ≥2 表格行 = 表头+数据）")
    else:
        notes.append(f"列表项 {n_item} · 表格行 {n_row}")
    return bad, notes


# ── O-91 (2026-09-26)：规范类文档必须带 **非空** 的 `## 未实测登记` 节 ──────────────
# 为什么要有：我们有"未实测登记"节（≈假设区），但**没有任何机制**保证它存在
#   ⇒ "写了规范、却没有任何未验证清单"可以**静默通过**。
# ★ 形状**直接复用** `validate_adr`（先例）：锚精确节名 · 恰 1 个 · 节体非空 · 扫描**只到下一个 H2**。
# ⚠⚠ **射程按文件名 glob 划**（本仓门禁的既有做法：`ADR-*.md` / `inventory/*.yaml` …）——
#   实测 `spec/d6-agent-standard/*.md` 共 **26 份**，含该节的只有 **5 份**；其余（ARCHITECTURE / DESIGN /
#   CHECKLIST / OPEN-ISSUES / DECISIONS …）**多数不是"规范"** ⇒ 一刀切会**当场红 21 份且大部分不该罚**。
# ⚠ **逃逸（如实写明，不假装没有）**：新规范若取名不带 `U\d-` 前缀，**本判据看不到它**。
#   实测 spec 与 adr **全部无 YAML front-matter**（没有 `type:` 之类的自描述锚可用）
#   ⇒ 只能靠"**命中集在门禁输出里可见**"缓解（改了名字时看得见）。
# ⚠⚠ **它不判什么（必须与 fix 文案同时读）**：**不判**"正文里有没有无证据断言" ——
#   那**不可机判**，**仍然是纪律**。省略这句，读者会以为"本判据绿了 = 断言已受控"（本仓头号形态）。
SPEC_DIR = ROOT / "spec" / "d6-agent-standard"
SPEC_UNTESTED_GLOBS = ("U[0-9]-*.md", "D7-PROTOCOL-*.md")
SPEC_UNTESTED_HEAD = "未实测登记"
# E 级**内联标注**（用于**报数**，不用于判）：`（E1）` = 裸；`（E1，<命令/文件>）` = 带具体取证。
# ⚠ 报数射程**刻意大于**判据射程：断言实际写在 `spec/d6-agent-standard/*.md` 与 `adr/ADR-*.md` 两处；
#   若只报那 5 份规范，会得到 `0 / 0` —— 而 `0 / 0` **会被读成「没问题」**（假绿）。
#   ⇒ 报数须覆盖"**放断言的地方**"，并在 note 里**写明射程**。
SPEC_EMARK_DIRS = (SPEC_DIR, ROOT / "adr")
SPEC_EMARK_RE = re.compile(r"（(E[1-5])([^）]*)）")
# ★ O-123（2026-09-30）：`inventory/untested-index.yaml`（6 份规范 `## 未实测登记` 节的**分诊索引**）。
#   在那之前它是**叶子节点**（全仓只有它自己和它自己的同步测试引用它）⇒ 本项把它的**分诊接上门禁**，
#   补掉"存在但无人读"那一半（同 `O-51` 的 `sensitivity.yaml` 形态）。
UNTESTED_INDEX = ROOT / "inventory" / "untested-index.yaml"


def validate_spec_untested(text):
    """**纯函数**：一份规范类文档是否满足"恰 1 个 `## 未实测登记` ∧ 节体非空"⇒ 返回 (bad, note)。

    ⚠ 节体扫描**只到下一个二级标题**为止（`### …` 是子节、**属节体**）—— 与 `validate_adr` 同规则；
      按"任意标题"截断会把子节判成空节。
    """
    lines = text.splitlines()
    heads = [(i, ln.strip()) for i, ln in enumerate(lines)
             if ln.startswith("## ") and not ln.startswith("### ")]
    canon = [(i, raw) for i, raw in heads if _norm_head(raw[3:]) == _norm_head(SPEC_UNTESTED_HEAD)]
    if not canon:
        return ([f"**缺** `## {SPEC_UNTESTED_HEAD}` 节 ⇒ 新规范必须给出「尚未被真实运行验证」的清单"
                 f"（⚠ 它**只**保证这一节存在，**不**保证「正文里没有无证据断言」）"], "")
    bad = []
    if len(canon) > 1:
        bad.append(f"有 **{len(canon)}** 个 `## {SPEC_UNTESTED_HEAD}` 节"
                   f"（行 {[i + 1 for i, _ in canon]}）⇒ 只允许 1 个")
    i0 = canon[0][0]
    body = []
    for ln in lines[i0 + 1:]:
        if ln.startswith("# ") or (ln.startswith("## ") and not ln.startswith("### ")):
            break
        body.append(ln)
    n_item = sum(1 for b in body if re.match(r"^\s*(?:[-*+]|\d+\.)\s+\S", b))
    n_row = sum(1 for b in body
                if b.strip().startswith("|") and not re.match(r"^\s*\|[\s:|-]+\|\s*$", b))
    if n_item == 0 and n_row < 2:
        bad.append(f"第 {i0 + 1} 行 `## {SPEC_UNTESTED_HEAD}` 节**是空的**"
                   f"（列表项 {n_item} · 表格行 {n_row}）⇒ 只写了标题没写内容"
                   f"（需 ≥1 列表项 **或** ≥2 表格行 = 表头+数据）")
        return bad, ""
    return bad, f"列表项 {n_item} · 表格行 {n_row}"


# ── O-93 (2026-09-26)：台账（`OPEN-ISSUES.md`）的「状态」必须**可机读** ────────────
# 为什么要有：本台账是**单一真值**，但它的状态列是**叙述文** ⇒ 无论按「列」还是按「整行有没有 ✅」
#   解析都会错。实测（同日三轮只读探针，同一棵树）**三种口径三个结果**：
#   按列 **27**（O-90/91/92 已闭环却被判成开着）· 按格首标记 **10** · 按整行含 ✅ **9**（把已关的判成开/反之）
#   ⇒ ★★ **两个方向都错**（既有假开、也有假关）；假关更危险（"看起来都没事了"）。
# ⇒ **规则：格首标记自证** —— 状态 = **第一个**格首是 `✅`/`◐`/`⏳`/`🔵` 的格，**与它落在第几格无关**。
#   ⚠ 为什么"与位置无关"而不是"第 N 格"：本表**列数不齐**（表头声明 8 列；老行 8 格、新行 6 格；
#     另有若干行含裸竖线被拆开）——**同一个第 5 格，老行是状态、新行是证据** ⇒ 位置取法根本不成立。
#   ⚠ 必须先**剥掉前导空白与加粗**（`**`/`_`）再判：实测 **22 行**的状态写成 `**✅ …**`，
#     直接写 `^✅` 会把它们判成"无状态" ⇒ **假开**（我最初的探针就是这么错的）。
#   ⚠ 取**第一个**而不是"恰一个"：老行的「归属批次」列会**复述** ✅（如 `✅ 已修`）—— 那是允许的。
LEDGER = ROOT / "spec" / "d6-agent-standard" / "OPEN-ISSUES.md"
LEDGER_ROW_RE = re.compile(r"^\|\s*(O-\d+)\s*\|")
LEDGER_LEAD_RE = re.compile(r"^[\s*_]*(✅|◐|⏳|🔵)")
LEDGER_CLOSED_MARK = "✅"


def parse_ledger_rows(text):
    """**纯函数**：解析台账行 ⇒ `[{id, line, status, cells}]`。`status` = 第一个格首带标记的格。

    ⚠⚠ **`status` 存的是「归一后」的文本**（剥掉前导 `**`/`_`/空白）—— 否则 `startswith('✅')` 对
      `**✅ …**` 会返回 False ⇒ **15 行被算成「仍开着」**（= 又一次假开；本批实测踩到，
      是靠"判据报数与独立探针报数不一致"抓出来的：判据 57/35 vs 探针 72/20）。
      ⇒ **教训：归一必须同时用于"匹配"和"比较"**，只对匹配归一照样会错。
    """
    rows = []
    for i, ln in enumerate(text.splitlines(), 1):
        m = LEDGER_ROW_RE.match(ln)
        if not m:
            continue
        cells = ln.split("|")[1:-1]
        status = ""
        for c in cells:
            if LEDGER_LEAD_RE.match(c.strip()):
                status = LEDGER_LEAD_RE.sub(r"\1", c.strip())   # 归一：只留标记开头
                break
        rows.append({"id": m.group(1), "line": i, "status": status, "cells": cells})
    return rows


def normalize_model_id(raw) -> str:
    """把产物里的 `model` 取值**归一到模型短名**（`D7-P3-1` 前置，2026-09-26）。

    ★★ **为什么必须归一（实测取的口径，不是设计出来的）**：取样 6 个真实 runDir，
      `run.json` 的 `model` 字段有**四种前缀形态** ——
        `local/gpt-oss-20b` · `cluster-litellm/gpt-oss-20b` ·
        `station:A/thinkingmachines/inkling:free` · `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`
      ⇒ 不归一就**没法和 `inventory/models.yaml` 的 `alias` 对上**。
    ★ 规则（**只剥外壳，不猜语义**）：① 取**最后一个 `/` 之后**的段；
      ② **再**去掉 `:` 之后的**尾参**。
    ⚠⚠ **顺序不能反（本批实测踩到）**：`station:A/thinkingmachines/inkling:free` 里 `:` 出现在
      **前缀中间**，若"先去尾参再取末段"会得到 `station`（整段被腰斩）⇒ 必须**先定位末段、再剥尾参**。
    """
    s = str(raw or "").strip()
    if not s:
        return ""
    return s.split("/")[-1].split(":", 1)[0].strip()


def model_key_variants(raw) -> list:
    """把 `model` 串展开成**候选键**（按优先级），供族表查询（`D7-P3-1`，2026-09-26）。

    ★★ **为什么不能只用一个键（实测 246 个真实 run 后得出）**：真实取值里既有
      `local/gpt-oss-20b`（本机档）也有 `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`（出网档）。
      · 只取**末段** ⇒ 丢掉 **vendor** ⇒ 而"谁家的"**正是族判定的依据**；
      · 只取全串 ⇒ 本地 alias（`m27-q4ks`）与出网串**不同形** ⇒ 一边对不上。
      ⇒ 展开成**多候选**、按"信息量从多到少"依次查，**首个命中者胜**；**全不命中 ⇒ 不可判**。
    候选顺序：① 剥掉已知**传输前缀**后的剩余路径（`nvidia/nemotron-…`）· ② 末段 · ③ 原串。
    ★ 只剥**已知**前缀（`local`/`cluster-litellm`/`opencode`/`openrouter`/`station:<X>`），
      **不猜**别的前缀语义（猜会把 `nvidia/…` 的 vendor 一起剥掉）。
    """
    s = str(raw or "").strip()
    if not s:
        return []
    parts = [x for x in s.split("/") if x]
    if not parts:
        return []
    known = {"local", "cluster-litellm", "opencode", "openrouter"}
    if parts[0] == "station" and len(parts) >= 2:
        rest = parts[2:]
    elif parts[0] in known:
        rest = parts[1:]
    else:
        rest = parts
    rest = [r.split(":", 1)[0] for r in rest]
    out = []
    if len(rest) >= 2:
        out.append("/".join(rest[-2:]))
    if rest:
        out.append(rest[-1])
    out.append(s)
    seen, res = set(), []
    for x in out:
        if x and x not in seen:
            seen.add(x)
            res.append(x)
    return res


def family_of(raw, index):
    """按**候选键**查族 ⇒ `(family_id | None, 命中的键)`。全不命中 ⇒ `(None, '')`。"""
    for k in model_key_variants(raw):
        if k in index:
            return index[k], k
    return None, ""


def load_family_index():
    """读 `inventory/model-families.yaml` ⇒ `{候选键: family_id}`（供 J-1 用）。

    ⚠ **覆盖边界以 yaml 为准，本函数不复制它**（防"同一事实两个定义点"）：
      覆盖 = `families[].members`（本地 alias）+ `outbound_models[].keys`（**出网/传输档**已登记键）
      + `endpoint_aliases_na` **不在索引里**（端点别名 ⇒ 查不到 ⇒ J-1 恒 `unknown`，是**有意**的）。
      2026-09-29 实测 `len(index)=21`；夹具 `tests/test_rpc_check_cross_family.py` 的 `C5` 就钉这一条。
    """
    import yaml
    F = yaml.safe_load((ROOT / "inventory" / "model-families.yaml").read_text(encoding="utf-8")) or {}
    idx = {}
    for fam in (F.get("families") or []):
        fid = str(fam.get("id") or "")
        for a in (fam.get("members") or []):
            idx[str(a)] = fid
    for ob in (F.get("outbound_models") or []):
        fid = str(ob.get("family") or "")
        if not fid:
            continue
        for k in (ob.get("keys") or []):
            idx[str(k)] = fid
    return idx


def cross_family_verdict(producer_raw, judge_raw, index) -> dict:
    """**J-1（跨族）** 的判定本体（`D7-P0-3` 的判据之一 ⇒ `D7-P3-1` 落地）。

    判据原式：`lookup_family(judge.model) != lookup_family(producer.model)`。
    三态（**禁止"基本通过"**）：
      · `cross`   ⇒ 跨族 ✅（异构成立）
      · `same`    ⇒ **同族 ⇒ 判据红**（"同族多实例"不构成认知多样性 —— Courtroom-MAD 的实测）
      · `unknown` ⇒ **任一模型不在族表里 ⇒ 不可判**；★ **fail-closed：绝不默认算"跨族"**
        （默认放行 = 把"没判"读成"通过"，本仓最防的形态）。
    """
    p, j = str(producer_raw or "").strip(), str(judge_raw or "").strip()
    if not p or not j:
        return {"verdict": "unknown", "reason": "缺 producer/judge 的 model", "unknown": []}
    fp, kp = family_of(p, index)
    fj, kj = family_of(j, index)
    if fp is None or fj is None:
        miss = [model_key_variants(x)[0] for x, f in ((p, fp), (j, fj)) if f is None]
        return {"verdict": "unknown",
                "reason": f"查不到族: {'; '.join(miss)}（多为**端点别名**或**未登记的出网模型**"
                          f" ⇒ **不可判，不是通过**）",
                "unknown": miss}
    if fp == fj:
        return {"verdict": "same", "reason": f"producer={p}({fp}) · judge={j}({fj}) **同族**",
                "producer": p, "judge": j, "family": fp}
    return {"verdict": "cross", "reason": f"{fp} vs {fj}", "producer": p, "judge": j,
            "families": [fp, fj]}


def cross_input_verdict(producer_sha, judge_sha) -> dict:
    """**J-2（输入独立）** 的判定本体：`hash(judge.input) != hash(producer.input)`。

    原料 = `run.json.prompt_sha256`（产出者输入）与 `review.json.metadata.prompt_hash`（判官输入）
    —— ★ 两者**都已在产物里**（2026-09-26 实测），故 J-2 **不需要新登记**。
    ⚠ **诚实边界**：摘要**不等**只能证明"送入的载荷不同"，**不能**证明"信息独立"
      （判官可能收到同一份内容的不同包装）⇒ 本判据是**下界**，如实登记。
    """
    p, j = str(producer_sha or "").strip(), str(judge_sha or "").strip()
    if not p or not j:
        return {"verdict": "unknown", "reason": "缺 producer/judge 的输入摘要"}
    if p == j:
        return {"verdict": "same", "reason": "**两侧输入摘要相同** ⇒ 判官看到的就是产出者看到的（不独立）"}
    return {"verdict": "cross", "reason": "两侧输入摘要不同（**下界证据**，不等于信息独立）"}


def check_model_families(ctx):
    """`D7-P3-1` 前置：模型**家族**表 ↔ `models.yaml` **双向对账**（2026-09-26）。

    判什么：① 本表可解析且族非空（防空判）；② `members` 里的 alias **必须**在 `models.yaml` 存在
            （否则 = **孤儿引用**）；③ **`models.yaml` 的每个 alias 恰属 1 族**（**漏项与重复都红** ——
            只做单向包含会漏掉「新模型没归类」，而那正是本表最容易腐化的方向）；
            ④ 每族必须有**非空 `basis`**（族划分依据）⇒ 堵「看着像就填」（与 `dialect.yaml` 同纪律）。
    ⚠ **不判什么**：**不判族分得对不对**（那要人读权重血统）。本判据只保证「**没有一个 alias 没被归类**」
       与「引用不悬空」。
    ⚠ **不提供什么**：它**不提供**「站↔**已加载**模型」—— 那是 `D7-P0-3` 判据 J-1 的**第二个输入**，
       与 `models.yaml` 的 `stations`（库中有）/ `conf`（配过实例）**不是一回事**（见 yaml 的 `linked_state`）。
    """
    try:
        import yaml
    except Exception as e:                                   # noqa: BLE001
        return ("WARN", f"缺 pyyaml（{type(e).__name__}）⇒ 本项不判", [])
    fam_p = ROOT / "inventory" / "model-families.yaml"
    mod_p = ROOT / "inventory" / "models.yaml"
    try:
        F = yaml.safe_load(fam_p.read_text(encoding="utf-8")) or {}
        M = yaml.safe_load(mod_p.read_text(encoding="utf-8")) or {}
    except Exception as e:                                   # noqa: BLE001
        return ("FAIL", f"yaml 不可解析: {type(e).__name__}: {e}", [])
    fams = F.get("families") or []
    aliases = [str(m.get("alias")) for m in (M.get("models") or []) if m.get("alias")]
    if not fams:
        return ("FAIL", "`families` 为空 ⇒ 空判（防『什么都没判』）", [])
    if not aliases:
        return ("FAIL", "`models.yaml` 无 alias ⇒ 空判", [])
    bad, owner = [], {}
    for f in fams:
        fid = str(f.get("id") or "?")
        if len(str(f.get("basis") or "").strip()) < 4:
            bad.append(f"族 `{fid}` 缺 `basis`（族划分依据）⇒ 堵『看着像就填』")
        mem = [str(x) for x in (f.get("members") or [])]
        if not mem:
            bad.append(f"族 `{fid}` 无成员 ⇒ 空族")
        for a in mem:
            if a not in aliases:
                bad.append(f"族 `{fid}` 的成员 `{a}` **不在 `models.yaml`**（孤儿引用）")
            elif a in owner:
                bad.append(f"`{a}` 同时属 `{owner[a]}` 与 `{fid}`（**重复归类**）")
            owner[a] = fid
    miss = [a for a in aliases if a not in owner]
    if miss:
        bad.append(f"**未归类**的 alias {len(miss)} 个：{', '.join(miss)} ⇒ 新模型必须归类")
    # 出网段同样要**对账**（2026-09-26 补：登记了没人查 = "存在但无人读"）
    obs = (F.get("outbound_models") or [])
    ob_owner = {}
    for ob in obs:
        fid = str(ob.get("family") or "")
        keys = [str(x) for x in (ob.get("keys") or [])]
        if not keys:
            bad.append(f"outbound 条目无 `keys`（family={fid or '?'}）⇒ 空条目")
        if not fid:
            bad.append(f"outbound 条目缺 `family`（keys={keys[:2]}）")
        if not str(ob.get("basis_from") or "").strip():
            bad.append(f"outbound `{keys[:1] or ['?']}` 缺 `basis_from`（口径来源）⇒ 堵『看着像就填』")
        for k in keys:
            if k in owner:
                bad.append(f"outbound 键 `{k}` 与本地族 `{owner[k]}` 的成员**同名** ⇒ **键冲突**"
                           f"（同一模型两处定义，查表结果取决于顺序）")
            if k in ob_owner:
                bad.append(f"outbound 键 `{k}` 被两条记录占用（`{ob_owner[k]}` 与 `{fid}`）")
            ob_owner[k] = fid
    note = (f"族 {len(fams)} · 成员覆盖 {len(owner)}/{len(aliases)} · "
            f"未归类 {len(miss)} · 出网 {len(obs)}/{len(ob_owner)}键 · 问题 {len(bad)}")
    detail = list(bad)
    if detail:
        return ("FAIL", note, detail)
    return ("PASS", note, [f"族: {', '.join(str(f.get('id')) for f in fams)}"])


def check_ledger_status(ctx):
    """O-93: 台账每行**状态可机读**（格首标记自证）—— 并报出「仍开着 N 条 + 清单」。

    ★ 判什么：① 每行都要有状态格（缺 ⇒ FAIL = 该行状态**读不出来**）；② 数据行 ≥1（防空判）。
    📊 **报数（不判）**：`✅ 闭环 X · 仍开着 Y` + 仍开着的 ID 清单 ⇒ **排优先级不再依赖人读**。
    ⚠⚠ **不判什么**：「应该闭环多少」**不判** —— 「开着」**不是错误**；本判据只保证「**读得到**」。
      也**不判**状态写得对不对（那仍要人读）—— 别把本判据读成"台账已被审计"。
    """
    if not LEDGER.is_file():
        return "WARN", f"{LEDGER.name} 不存在（本断言的登记依据）", []
    rows = parse_ledger_rows(_read_text(LEDGER))
    if not rows:
        return "FAIL", "**台账数据行 0 条** ⇒ 判据没有对象（表头/格式被改动过？防退化成空判）", []
    bad = [f"{r['id']}(L{r['line']})" for r in rows if not r["status"]]
    closed = [r["id"] for r in rows if r["status"].startswith(LEDGER_CLOSED_MARK)]
    opened = [r["id"] for r in rows if r["status"] and not r["status"].startswith(LEDGER_CLOSED_MARK)]
    note = (f"数据行 {len(rows)} · 状态可机读 {len(rows) - len(bad)} · "
            f"✅ 闭环 {len(closed)} · **仍开着 {len(opened)}**")
    detail = []
    if opened:
        detail.append("仍开着：" + " ".join(opened))
    if bad:
        detail.append("状态不可机读（缺格首标记 ⇒ 补 `✅`/`◐`/`⏳`/`🔵`）：" + " ".join(bad))
    return ("FAIL" if bad else "PASS"), note, detail


# ── O-144 甲（2026-10-06）：`needs_decision` 的**第二个来源 = 台账** ──────────────
# 依据（`O-144` 的根因）：`needs_decision` 原只认**规范文档措辞** ⇒ 台账（`OPEN-ISSUES.md`）里
#   写的"待裁"**结构性地反映不到索引** ⇒ `needs_decision: 0` 被误读成"本仓没有待裁项"。
# ★ 口径 = **实测收敛**（2026-10-06 只读探针，见 `O-144` 设计段）：
#   · **只认「待裁」二字** —— ⚠ **不用「未裁 / 未定」**：宽口径**引爆 34 条**，因为**已闭环**条目
#     正文常在讲"**当初**未裁 → 后来裁了"（**历史**）⇒ 会被读成"**当前**待裁"（= 假信号）；
#     窄口径 = **9 条**，恰好 = `D7-PROTOCOL-CONTRACT` #1–#9（经 `refs=O-136`）⇒ 与诊断吻合。
#   · **只扫该行的【自述面】**（简述格 + 状态格）—— 不扫 ID/类别/严重度/归属。
LEDGER_PENDING_MARK = "待裁"


def ledger_pending_ids(rows):
    """**纯函数**：从台账行取「**自述面明写「待裁」**」的 id 集合（`O-144` 甲）。

    `rows` = `parse_ledger_rows` 的产物（`[{id, line, status, cells}]`）。
    ⚠ **射程（如实）**：只扫 `cells[3]`（简述）+ `cells[4]`（状态）；只认「待裁」。
      ★ **已知误报面**：若某行正文**历史性地**提到"待裁"（如"曾待裁、已裁"），会被读成当前待裁 ——
        当前实测 0 例，但**该形态存在**（与 `O-153` 同族的"射程被读宽"风险）。
    """
    out = set()
    for r in (rows or []):
        if not isinstance(r, dict):
            continue
        cells = r.get("cells") or []
        txt = " ".join(str(c) for c in cells[3:5]) if len(cells) >= 5 else str(r.get("line") or "")
        if LEDGER_PENDING_MARK in txt:
            out.add(r.get("id"))
    return out


def _ledger_rows_for_triage():
    """读台账行供 `O-144` 甲用；★ **读不出 ⇒ `None`**（退回旧口径，不阻断）。

    ⚠ 为什么这里可以"静默退回"而不违 fail-closed：**台账自身的可读性另有判据**
      （`ledger-status`：缺状态格即 FAIL）⇒ **判据只在一处**，此处不回重复判。
    """
    try:
        return parse_ledger_rows(_read_text(LEDGER))
    except Exception:
        return None


def summarize_untested_triage(items, ledger_rows=None):
    """**纯函数**：消费 `untested-index.yaml` 的**分诊**（O-123 · 2026-09-30）⇒ 返回 `(warn, stats)`。

    ★ **这是该索引的【首个消费者】**（此前它是叶子节点：只有它自己和它自己的同步测试引用它）。
    ★ **判据**：某条被认定为「**待裁**」⇒ 点名 —— 口径 = 「**未裁项不许静默**」。
      而"待裁"有**两个来源**（`O-144` 甲，2026-10-06）：
        ① `needs_decision: true`（索引里**手写**的 —— 原口径，只在**规范文档明写**时填）；
        ② ★ **`refs` 指向的台账条目【明写「待裁」】**（新口径，`ledger_rows` 非 None 时才生效）。
      ⇒ 为什么必须补 ②（`O-144` 的根因）：台账里写的"待裁"原**反映不到索引** ⇒
        `needs_decision: 0` 会被**误读成"本仓没有待裁项"**（本仓 fail-closed 精神；同 `O-119` 的"不可判 ≠ 通过"）。
      ⚠ `ledger_rows=None`（缺参 / 台账读不出）⇒ **退回旧口径**（只认 ①），**不阻断**。
    📊 `stats` = 报数（`state` / `blocker` / `needs_decision` 分布）—— **只报不判**（本仓"标签比事实硬"教训）。
    ⚠⚠ **不判什么**（防读过头）：
      · 不判"**该闭环多少条**"（开着不是错误）；
      · 不判分诊**写得对不对**（那是人工判断）；
      · **不重做**闭集/对账校验 —— 那是 `tests/test_untested_index_sync.py` 的职责（**判据只在一处**）。
    """
    warn = []
    n = 0
    by_state, by_blocker, n_dec, n_via = {}, {}, 0, 0
    pending = ledger_pending_ids(ledger_rows) if ledger_rows is not None else set()
    for it in (items or []):
        if not isinstance(it, dict):
            continue
        n += 1
        st = str(it.get("state") or "?")
        bl = str(it.get("blocker") or "?")
        by_state[st] = by_state.get(st, 0) + 1
        by_blocker[bl] = by_blocker.get(bl, 0) + 1
        whose = f"{it.get('spec')}#{it.get('n')}"
        if it.get("needs_decision") is True:
            n_dec += 1
            warn.append(f"{whose}: `needs_decision: true` ⇒ **未裁项不许静默**"
                        f"（要么裁掉并落回规范本体，要么在索引里写明为何仍是 true）")
            continue
        via = [r for r in (it.get("refs") or []) if isinstance(r, str) and r in pending]
        if via:
            n_dec += 1
            n_via += 1
            warn.append(f"{whose}: `needs_decision` 字段为 false，但它 `refs` 指向的台账条目"
                        f"（{', '.join(via)}）**明写「待裁」** ⇒ **未裁项不许静默**"
                        f"（`O-144` 甲：来源已扩到台账 —— 请裁掉并落回规范本体，或把该行措辞改准）")
    stats = {"n": n, "state": by_state, "blocker": by_blocker,
             "needs_decision": n_dec, "needs_decision_via_ledger": n_via}
    return warn, stats


def check_spec_untested(ctx):
    """O-91: 规范类文档（`U[0-9]-*.md` / `D7-PROTOCOL-*.md`）必须带**非空**的 `## 未实测登记` 节。

    ★ 判什么：① **命中集 ≥1**（否则判据**没有对象** ⇒ FAIL，防退化成空判）；
      ② 每份**恰 1 个**该节；③ 节体**非空**；
      ④ ★ **O-123（2026-09-30）**：顺带**消费** `inventory/untested-index.yaml` 的分诊 ——
         **报数**（state / blocker / needs_decision 分布）+ **一条判据**（任一条 `needs_decision: true` ⇒ **WARN**，
         口径 = 「**未裁项不许静默**」）。⇒ 该索引由此**不再是叶子节点**（此前只有它自己的同步测试引用它）。
    ⚠⚠ **不判**：正文里有没有**无证据断言** —— 那不可机判、**仍是纪律**（见上方那段注释）。
      ⚠ 也**不判**分诊**写得对不对**，更**不重做**索引的对账/闭集校验（那是 `py-tests` 的职责 —— 判据只在一处）。
    📊 **附一条报数（不判）**：E 级内联标注里"带具体取证 vs 裸"的分布。
      ⚠ 为什么是**报数而不是判据**：实测 ADR 侧 **57% 是裸标**（`（E1）`），而"裸"**不等于"错"**
        （有的结论句本身不必带命令，命令写在同段别处）；且**连计数都口径敏感** ——
        同一棵树、两个正则（`（E[1-5]` vs 完整括号对）在 spec 侧数出 **4 vs 8**。
        ⇒ 做成 FAIL 会立刻造一批**假红**，而假红的结局是**被加进例外名单**（判据失效，O-70 同族）。
      ⚠ 也**不新开一个恒 PASS 的报数断言** —— 那正是"**判据什么都没判**"。
    """
    files = sorted({p for g in SPEC_UNTESTED_GLOBS for p in SPEC_DIR.glob(g)})
    if not files:
        return ("FAIL",
                f"spec/{SPEC_DIR.name} 下无匹配（{' / '.join(SPEC_UNTESTED_GLOBS)}）—— **判据无对象**", [])
    bad, summ, em_detail, em_bare, em_files = [], [], 0, 0, 0
    for p in files:
        text = _read_text(p)
        b, note = validate_spec_untested(text)
        bad += [f"{p.name}: {x}" for x in b]
        if note:
            summ.append(f"{p.stem}: {note}")
    # 📊 报数（**不判**）：射程 = "放断言的两个地方"（见 SPEC_EMARK_DIRS 的注释）
    for d in SPEC_EMARK_DIRS:
        for p in sorted(d.glob("*.md")):
            em_files += 1
            for m in SPEC_EMARK_RE.finditer(_read_text(p)):
                if m.group(2).strip(" ，,;；:："):
                    em_detail += 1
                else:
                    em_bare += 1
    n_bad_file = len({x.split(":", 1)[0] for x in bad})
    # ★ O-123（2026-09-30）：**索引分诊的消费者**（本条判据的第三件事，也是"叶子节点"缺口的另一半）。
    #   形态：**报数**（分布进 note）+ **一条判据**（`needs_decision: true` ⇒ WARN）。
    #   ⚠ 索引坏了/缺了 ⇒ **WARN 而非 FAIL**：本判据的对象是"规范的那一节"，索引是**附加消费对象**；
    #     索引自身的完整性/对账由 `py-tests`（`tests/test_untested_index_sync.py`）判 ⇒ **不在此处重复判**。
    tri_note, tri_warn = "", []
    try:
        import yaml
    except Exception:
        tri_warn = ["缺 pyyaml ⇒ **分诊无从消费**（本判据新增射程跳过；规范侧判定不受影响）"]
    else:
        if not UNTESTED_INDEX.is_file():
            tri_warn = [f"`inventory/{UNTESTED_INDEX.name}` 不存在 ⇒ **分诊无从消费**"]
        else:
            try:
                inv = yaml.safe_load(_read_text(UNTESTED_INDEX)) or {}
                tri_warn, tri = summarize_untested_triage(inv.get("items"), _ledger_rows_for_triage())
                _fmt = lambda d: " · ".join(f"{k}={v}" for k, v in sorted(d.items()))
                tri_note = (f" · **索引分诊** 条目 {tri['n']}"
                            f"（state {_fmt(tri['state'])}；blocker {_fmt(tri['blocker'])}；"
                            f"needs_decision {tri['needs_decision']}"
                            f"（其中 **{tri['needs_decision_via_ledger']} 条由台账 `refs` 推出**））")
                if tri["n"] == 0:
                    tri_warn = ["索引 `items` **为 0 条** ⇒ 分诊消费没有对象（防退化成空判）"]
            except Exception as e:
                tri_warn = [f"`inventory/{UNTESTED_INDEX.name}` 不可消费: {type(e).__name__}: {e}"]
    note = (f"规范 {len(files)} 份 · 违规 {n_bad_file} 份 · "
            f"E 标报数 带取证 {em_detail} / 裸 {em_bare}"
            f"（**报数，不判**；射程 = spec/d6-agent-standard/*.md + adr/ADR-*.md 共 {em_files} 份）" + tri_note)
    if not bad:
        note += f"（全部含 `## {SPEC_UNTESTED_HEAD}` 且非空）"
    if bad:
        return "FAIL", note, summ + bad
    if tri_warn:
        # 未裁项不许静默 ⇒ 非阻断发现（本仓 WARN 语义：执行后有发现、不拦提交）
        return "WARN", note, summ + tri_warn
    return "PASS", note, summ


def check_adr(ctx):
    """P2-2: `adr/ADR-*.md` 必须有"考虑的替代方案"节（恰 1 个 · 非空 · 不留旧节名）。"""
    files = sorted(ADR_DIR.glob(ADR_GLOB))
    if not files:
        return "WARN", f"adr/{ADR_GLOB} 无匹配（本断言的登记依据）", []
    bad, summ = [], []
    for p in files:
        b, notes = validate_adr(_read_text(p))
        bad += [f"{p.name}: {x}" for x in b]
        if notes:
            summ.append(f"{p.stem}: {notes[0]}")
    detail = summ + bad
    n_bad_file = len({x.split(":", 1)[0] for x in bad})
    note = f"ADR {len(files)} 份 · 节名统一 `{ADR_CANON}` · 违规 {n_bad_file} 份"
    if not bad:
        note += f"（全部含 `{ADR_CANON}` 节且非空）"
    return ("FAIL" if bad else "PASS"), note, detail


# ── 断言 A3: inventory 单点真值 (P1) ──────────────────────────────
# 目的: 阻止"改了这个忘了那个" —— 端口/模型标识变更时, 保证声明源与真值表一致。
#
# **对账模式, 不是文本扫描** (2026-09-14 实测修正, 详见文档 §11):
#   最初的设计是"扫描全仓库出现的端口/模型名, 未登记即 FAIL"。实测该方案不可行:
#     · 端口: 51 个"端口"里 19 个不是端口 (llama.cpp 提交号 9859、参数值 16384/4096/
#       1024、截断匹配 127/808...)。文本里的数字没有唯一语义。
#     · 模型: 以 gguf 结尾的强标识 114 个, 100% 是路径/文件名, 纯噪声。
#   改为只对**结构化声明源**做对账 —— 精确、零噪声、可长期维护:
#     (a) 入口及其拆分模块的端口常量 (如 STATION_PORT) 与模型路由常量 (如 ROUTE)
#         —— 见 DECL_CLUSTER_FILES (常量层 2026-09-23 抽到 cluster_const.py)
#     (b) docs/三机推理集群使用手册.md 的端点表格行
#   声明源里出现而 inventory 未登记 => FAIL, 并提示"登记真值"或"修正过期引用"。
INVENTORY_DIR = ROOT / "inventory"
DECL_CLUSTER_PY = ROOT / "ops" / "cluster.py"
# 2026-09-23 (阶段 1a 拆分): 声明源可能已搬到"入口的拆分模块"—— 常量层在 cluster_const.py。
# ⚠ **改这里之前先想清楚**: 不覆盖新模块会让本断言**静默降级**（实测: ROUTE/STATION_ROUTES
#   搬走后仍只扫 cluster.py ⇒ "声明源 3 模型标识" 掉成 "0"，而断言照旧 PASS —— 门禁空转的假绿）。
#   凡"常量层再拆分/搬家"，必须同步本清单。
DECL_CLUSTER_FILES = [ROOT / "ops" / "cluster.py", ROOT / "ops" / "cluster_const.py"]
DECL_MANUAL = ROOT / "docs" / "三机推理集群使用手册.md"

CONST_DICT_RE = r"^(?P<name>%s[A-Z_]*)\s*=\s*\{(?P<body>[^}]*)\}"
PORT_CONST_RE = re.compile(CONST_DICT_RE % r"[A-Z_]*PORT", re.M)
MODEL_CONST_RE = re.compile(CONST_DICT_RE % r"(?:[A-Z_]*ROUTE[A-Z_]*)", re.M)
MANUAL_PORT_RE = re.compile(r"(?:[A-Za-z0-9._\-]+|\*)?:(\d{4,5})\b")


def load_inventory():
    """读 inventory/*.yaml。返回 (ports: {int: 条目}, models: {str: 条目})。"""
    try:
        import yaml
    except Exception:
        return None, None
    ports, models = {}, {}
    if not INVENTORY_DIR.is_dir():
        return ports, models
    for f in sorted(INVENTORY_DIR.glob("*.yaml")):
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        for group, items in doc.items():
            # 纯登记用的段不参与"已声明真值"计算 (否则 known_broken_conf 里的 alias
            # 会被当成正常模型键, 掩盖它其实是坏的)
            if group in ("known_issues", "known_drift", "known_broken_conf"):
                continue
            if not isinstance(items, list):
                continue
            for it in items:
                if not isinstance(it, dict):
                    continue
                if isinstance(it.get("port"), int):
                    ports[it["port"]] = {**it, "_group": group, "_file": f.name}
                for key in ("alias", "engine_id"):
                    if it.get(key):
                        models[str(it[key])] = {**it, "_group": group, "_file": f.name}
    return ports, models


def _declared():
    """从声明源解析 (端口, 模型标识)。返回 ({port: [来源]}, {name: [来源]})。

    声明源 = 入口及其拆分模块 (DECL_CLUSTER_FILES) + 手册端点表。"""
    ports, models = {}, {}
    for src in DECL_CLUSTER_FILES:
        if not src.is_file():
            continue
        label = src.name
        text = _read_text(src)
        for m in PORT_CONST_RE.finditer(text):
            for v in re.findall(r":\s*(\d{2,5})", m.group("body")):
                ports.setdefault(int(v), []).append(f"{label}:{m.group('name')}")
        for m in MODEL_CONST_RE.finditer(text):
            # STATION_ROUTES 是**派生表** (键 = 站上真实别名 + 站后缀, 值 = (站, 真实别名)),
            # 不逐条登记到 inventory —— 那会与基础别名重复, 且引入双份要同步的真值。
            # 它的正确性由 aliases 断言的 (7) 子项校验 (更强: 含站维度, 要求 (别名,站) 已声明 conf)。
            if m.group("name") == "STATION_ROUTES":
                continue
            for k in re.findall(r"[\"']([^\"']+)[\"']\s*:", m.group("body")):
                models.setdefault(k, []).append(f"{label}:{m.group('name')}")
    if DECL_MANUAL.is_file():
        for i, line in enumerate(_read_text(DECL_MANUAL).splitlines(), 1):
            if not line.startswith("|"):
                continue
            for m in MANUAL_PORT_RE.finditer(line):
                ports.setdefault(int(m.group(1)), []).append(f"手册:{i}")
    return ports, models


def check_inventory(ctx):
    ports, models = load_inventory()
    if ports is None:
        return "WARN", "未安装 pyyaml, 无法读取 inventory/ (断言跳过)", []
    if not ports and not models:
        return "FAIL", "inventory/ 为空 —— 该断言需要真值表才能工作", []

    decl_ports, decl_models = _declared()
    unk_ports = {v: loc for v, loc in decl_ports.items() if v not in ports}
    unk_models = {t: loc for t, loc in decl_models.items()
                  if t not in models and t.lower() not in {k.lower() for k in models}}

    # 真值表自身的完整性: managed 分组每条必须有 purpose
    incomplete = [f"{f}:{p.get('purpose', '(无 purpose)')}"
                  for p, f in ((v, v["_file"]) for v in ports.values() if v["_group"] == "managed")
                  if not p.get("purpose")]

    detail = []
    for v, loc in sorted(unk_ports.items()):
        detail.append(f"声明源用了未登记端口 {v}  ({', '.join(sorted(set(loc))[:3])}) —— "
                      f"是有效端口就在 inventory/ports.yaml 登记, 否则修正该引用")
    for t, loc in sorted(unk_models.items()):
        detail.append(f"声明源用了未登记模型标识 `{t}`  ({', '.join(sorted(set(loc))[:3])}) —— "
                      f"是有效别名就在 inventory/models.yaml 登记, 否则修正该引用")
    detail += [f"inventory 条目缺 purpose: {x}" for x in incomplete]

    note = (f"对账: 声明源 {len(decl_ports)} 端口 / {len(decl_models)} 模型标识 · "
            f"真值表 {len(ports)} 端口 / {len(models)} 模型键 · "
            f"未登记 {len(unk_ports)} / {len(unk_models)}")
    if unk_ports or unk_models or incomplete:
        return "FAIL", note, detail
    return "PASS", note, []


# ── 断言 A6: 端口分配表自洽 (P1-4) ────────────────────────────────
# 目的: 让 inventory/ports.yaml 从"一份文档"变成"一份可断言的分配表"。
# 只做**表内自洽** (不碰站上, 故可进 quick 门禁); 站上占用对账在 stations 断言的 (g)。
#
# 为什么需要: 2026-09-15 首次做站上对账时暴露三类表本身的问题 ——
#   · 8090 登记为 "Beszel agent, scope [A, B]", 实际监听方是 B 站 beszel-hub
#     (A 站的 agent 是**出站**客户端, 不监听) → 分配表的 scope 与 owner 都会写错
#   · mountd/statd 的端口号被写死 (52591/53517/55723), 一天后全变 → 端口号不是真值
#   · 137/138/546/5353/3702/6665/724 等长期监听的系统端口从未登记 → 对账必红
INVENTORY_PORTS = INVENTORY_DIR / "ports.yaml"
VALID_SCOPE = {"master", "A", "B", "C"}
VALID_PROTO = {"tcp", "udp", "http", "https", "tcp+udp"}
VALID_MODE = {"always", "on_demand"}
# 内核临时端口段下界。三站实测 net.ipv4.ip_local_port_range = "32768 60999"。
# 该段端口随服务启动重分配 (NFS mountd/statd 即典型), 不能当作真值登记, 故对账豁免。
EPHEMERAL_MIN = 32768
ALL_STATIONS = ("A", "B", "C")


def _port_entries():
    """读 inventory/ports.yaml → {group: [entry, ...]}。

    文件不存在返回 {}; **解析失败抛异常** —— 刻意不吞:
    2026-09-15 实测教训 —— 初版把异常吞成 {} 后, 一个 `note:` 值的 YAML 语法错误
    让整张表变空, stations 断言随即报了 40+ 条"端口未登记"的**假象**,
    真正的错因 (第 142 行) 完全看不到。真值表解析失败必须立刻炸出来。
    """
    if not INVENTORY_PORTS.is_file():
        return {}
    import yaml
    doc = yaml.safe_load(INVENTORY_PORTS.read_text(encoding="utf-8")) or {}
    return {g: v for g, v in doc.items() if isinstance(v, list)}


def _scopes(e):
    """条目适用的站列表。**无 scope = 三站通用** (unmanaged 里的系统端口多如此)。"""
    s = e.get("scope")
    return [str(x) for x in s] if s else list(ALL_STATIONS)


def check_ports(ctx):
    """纯表内自洽: 结构 / 唯一 / 跨组重叠 / 枚举 / expect_bind 具体性。"""
    if not INVENTORY_PORTS.is_file():
        return "WARN", "inventory/ports.yaml 缺失 (端口分配表未建)", []
    try:
        entries = _port_entries()
    except Exception as e:
        return "FAIL", f"ports.yaml 解析失败: {type(e).__name__}: {str(e)[:180]}", []
    if not entries.get("managed"):
        return "FAIL", "ports.yaml 无可解析的 managed 分组", []

    detail = []
    groups = ("managed", "third_party", "unmanaged", "deprecated")

    # (1) 结构完整性: managed 要求 purpose/scope/bind/owner 四件套
    #     (scope 是"按站对账"的前提, bind 是"暴露面"的前提; 缺任一项该行就不可断言)
    for g, req in (("managed", ("purpose", "scope", "bind", "owner")),
                   ("third_party", ("purpose", "owner", "scope"))):
        for e in entries.get(g) or []:
            if not isinstance(e, dict):
                continue
            miss = [k for k in req if not e.get(k)]
            if miss:
                detail.append(f"{g} :{e.get('port', '?')} 缺字段 {', '.join(miss)}")

    # (2) 同一端口不得在同一分组内出现两次 (后者覆盖前者 = 静默丢条目)
    for g in groups:
        seen = {}
        for e in entries.get(g) or []:
            if not isinstance(e, dict) or not isinstance(e.get("port"), int):
                continue
            seen.setdefault(e["port"], []).append(e)
        for p, lst in sorted(seen.items()):
            if len(lst) > 1:
                detail.append(f"{g} 内端口 {p} 重复 {len(lst)} 次 —— 后者会覆盖前者")

    # (3) 跨分组不得重叠 —— 这是"分配表"的核心约束: 一个端口同一时刻只属于一类。
    #     deprecated 也纳入: 已退役端口若又出现在在用分组, 说明退役不彻底/登记过期。
    owner_of = {}
    for g in groups:
        for e in entries.get(g) or []:
            if isinstance(e, dict) and isinstance(e.get("port"), int):
                owner_of.setdefault(e["port"], []).append(g)
    for p, gs in sorted(owner_of.items()):
        if len(set(gs)) > 1:
            detail.append(f"端口 {p} 同时登记在 {', '.join(sorted(set(gs)))} 两个分组 —— "
                          f"应只在其中一处 (在用的进 managed/third_party/unmanaged, "
                          f"退役的只留 deprecated)")

    # (4) 枚举合法性 —— 拼错 scope/proto/mode 会让对账**静默失效**
    #     (如 scope 写成 "a" 则不匹配任何站; mode 写成 "ondemand" 则豁免规则不生效)
    for g in ("managed", "third_party", "unmanaged"):
        for e in entries.get(g) or []:
            if not isinstance(e, dict):
                continue
            p = e.get("port", "?")
            for s in (e.get("scope") or []):
                if str(s) not in VALID_SCOPE:
                    detail.append(f"{g} :{p} 的 scope 含非法值 {s!r} (合法: "
                                  f"{'/'.join(sorted(VALID_SCOPE))})")
            if e.get("proto") and str(e["proto"]).lower() not in VALID_PROTO:
                detail.append(f"{g} :{p} 的 proto 非法 {e['proto']!r} "
                              f"(合法: {'/'.join(sorted(VALID_PROTO))})")
            if e.get("mode") and str(e["mode"]) not in VALID_MODE:
                detail.append(f"{g} :{p} 的 mode 非法 {e['mode']!r} "
                              f"(合法: {'/'.join(sorted(VALID_MODE))})")

    # (5) expect_bind 必须是**具体地址** —— 它的用途是断言"暴露面没超预期",
    #     写成 * 或 0.0.0.0 则断言恒真, 等于没写。
    for e in entries.get("managed") or []:
        exp = (e or {}).get("expect_bind")
        if exp and ("*" in str(exp) or str(exp).startswith("0.0.0.0")):
            detail.append(f"managed :{e.get('port')} 的 expect_bind={exp!r} 不是具体地址, "
                          f"该断言会恒真")

    n_ports = len([1 for e in entries.get("managed") or []
                   if isinstance(e, dict) and isinstance(e.get("port"), int)])
    note = (f"分配表: managed {n_ports} · third_party {len(entries.get('third_party') or [])} · "
            f"unmanaged {len(entries.get('unmanaged') or [])} · "
            f"deprecated {len(entries.get('deprecated') or [])} · "
            f"dynamic {len(entries.get('dynamic') or [])}")
    if detail:
        return "FAIL", note, detail
    return "PASS", note, []


# ── 断言 A7: 插件/技能三站同构基线 (P1-5) ─────────────────────────
# 目的: 把 PLUGIN-LEDGER 的"三站完全同构"从**人工文字断言**改成可断言的真值。
# 为什么必须改: 2026-09-15 首次实测即推翻该结论 —— C 站 ARS 链的 25 个软链
# **全部是死链**(源目录 ~/tools/opencode-academic-research 在 C 站不存在), 而
# "只数软链个数"三站恰好都是 25, 手工核对显示"一致"。判据必须定在**可达性**上。
#
# 本断言(index)只做**纯本地**部分(可进 quick 门禁):
#   · items 结构自洽: id 唯一非空 / kind 合法 / expect 类型与 kind 匹配
#   · local_sources 对账: 仓库侧源(ops/agent-skills/*/SKILL.md)的名字集合必须
#     等于它所镜像的 item 的 expect —— 抓"仓库加了技能但没登记", 无需 ssh
#   · known_drift 必须指向存在的 item 与合法站, 且 extra 不得落在 expect 内
# 站上部分在 stations 断言的 (h) 子项 (复用同一次 ssh 往返)。
INVENTORY_PLUGINS = INVENTORY_DIR / "plugins.yaml"
PLUGIN_KINDS = {"scalar", "set", "count", "flag"}
PLUGIN_STATIONS = ("A", "B", "C")


def _plugins_doc():
    """读 inventory/plugins.yaml。文件缺失返回 {}; **解析失败抛异常**(同 ports)。"""
    if not INVENTORY_PLUGINS.is_file():
        return {}
    import yaml
    return yaml.safe_load(INVENTORY_PLUGINS.read_text(encoding="utf-8")) or {}


def _plugin_items(doc):
    """{id: item}。"""
    out = {}
    for it in doc.get("items") or []:
        if isinstance(it, dict) and it.get("id"):
            out[str(it["id"])] = it
    return out


def _plugin_scope(it):
    """item 适用的站; 无 scope = 三站通用。"""
    s = it.get("scope")
    return [str(x) for x in s] if s else list(PLUGIN_STATIONS)


def _plugin_diff(it, got):
    """把站上实得值与基线比对。返回 None=一致, 否则 (差异类, 明细)。

    set 类区分两种差异: ("extra", 只多出的元素) 与 ("diff", 明细) ——
    前者才有可能匹配 known_drift（已登记的多余项降 WARN），
    后者(少了元素/多出未登记元素)一律 FAIL。
    """
    kind, exp = it.get("kind"), it.get("expect")
    if kind == "count":
        try:
            return None if int(got) == exp else ("diff", [got, exp])
        except (TypeError, ValueError):
            return ("diff", [got, exp])
    if kind in ("scalar", "flag"):
        return None if got == exp else ("diff", [got, exp])
    if kind == "set":
        g = {x for x in str(got).split(",") if x}
        e = {str(x) for x in (exp or [])}
        if g == e:
            return None
        if not (e - g):
            return ("extra", sorted(g - e))
        return ("diff", [f"缺{sorted(e - g)}", f"多{sorted(g - e)}"])
    return ("diff", [f"未知 kind={kind!r}"])


def _plugin_src_names(path, glob):
    """仓库侧源的条目名。glob 形如 '*/SKILL.md' → 取条目所在目录名。"""
    files = sorted(path.glob(glob))
    names = set()
    for p in files:
        names.add(p.parent.name if len(p.parts) > len(path.parts) + 1 else p.name)
    return sorted(names)


def check_plugins(ctx):
    """纯本地: 基线结构自洽 + 仓库内源与登记值对账。"""
    if not INVENTORY_PLUGINS.is_file():
        return "WARN", "inventory/plugins.yaml 缺失 (插件同构基线未建)", []
    try:
        doc = _plugins_doc()
    except Exception as e:
        return "FAIL", f"plugins.yaml 解析失败: {type(e).__name__}: {str(e)[:180]}", []

    detail = []
    raw = [it for it in (doc.get("items") or []) if isinstance(it, dict)]
    items = _plugin_items(doc)

    # (1) 结构自洽
    dup = {}
    for i, it in enumerate(raw, 1):
        iid = it.get("id")
        if not iid:
            detail.append(f"items[{i}] 缺 id")
            continue
        dup[iid] = dup.get(iid, 0) + 1
        if it.get("kind") not in PLUGIN_KINDS:
            detail.append(f"{iid} 的 kind 非法 {it.get('kind')!r} "
                          f"(合法: {'/'.join(sorted(PLUGIN_KINDS))})")
        else:
            exp = it.get("expect")
            ok = (isinstance(exp, int) and not isinstance(exp, bool) if it["kind"] == "count"
                  else isinstance(exp, list) and bool(exp) and all(isinstance(x, str) for x in exp)
                  if it["kind"] == "set"
                  else isinstance(exp, str) and bool(exp) if it["kind"] == "scalar"
                  else exp in ("yes", "no"))
            if not ok:
                detail.append(f"{iid} 的 expect 与 kind={it['kind']} 不匹配: {exp!r}")
        if not it.get("purpose"):
            detail.append(f"{iid} 缺 purpose")
        for s in (it.get("scope") or []):
            if str(s) not in PLUGIN_STATIONS:
                detail.append(f"{iid} 的 scope 含非法站 {s!r}")
    for iid, n in sorted(dup.items()):
        if n > 1:
            detail.append(f"item id {iid!r} 重复 {n} 次 —— 后者会覆盖前者")
    if not items:
        detail.append("items 为空 —— 该断言需要基线才能工作")

    # (2) 仓库内源 → 登记值对账 (本地就能抓"加了技能没登记")
    for src in doc.get("local_sources") or []:
        if not isinstance(src, dict):
            continue
        name = src.get("name") or "?"
        mirrors = src.get("mirrors")
        path = ROOT / str(src.get("path") or "")
        glob = str(src.get("glob") or "*/SKILL.md")
        if mirrors not in items:
            detail.append(f"local_sources/{name} 的 mirrors={mirrors!r} 在 items 中不存在")
            continue
        if not path.is_dir():
            detail.append(f"local_sources/{name} 的路径不存在: {src.get('path')}")
            continue
        exp = items[mirrors].get("expect")
        if not isinstance(exp, list):
            detail.append(f"local_sources/{name} 镜像的 {mirrors} 不是 set 类, 无法对账")
            continue
        got = _plugin_src_names(path, glob)
        if got != sorted(exp):
            detail.append(
                f"仓库源 {src.get('path')} 与基线 {mirrors} 不一致: "
                f"源 {len(got)} 项 / 基线 {len(exp)} 项; "
                f"仅在源 {sorted(set(got) - set(exp)) or '无'}; "
                f"仅在基线 {sorted(set(exp) - set(got)) or '无'}")

    # (3) known_drift 自洽
    for kd in doc.get("known_drift") or []:
        if not isinstance(kd, dict):
            continue
        tag = f"known_drift({kd.get('station')}/{kd.get('id')})"
        if kd.get("id") not in items:
            detail.append(f"{tag} 指向不存在的 item")
        if str(kd.get("station")) not in PLUGIN_STATIONS:
            detail.append(f"{tag} 的 station 非法")
        if not kd.get("note"):
            detail.append(f"{tag} 缺 note (登记必须写明原因)")
        extra, exp = kd.get("extra"), (items.get(kd.get("id")) or {}).get("expect")
        if isinstance(extra, list) and isinstance(exp, list):
            inside = [x for x in extra if x in exp]
            if inside:
                detail.append(f"{tag} 的 extra 里有本就属于 expect 的元素 {inside} —— "
                              f"extra 只应列**多余项**")

    n_drift = len([k for k in (doc.get("known_drift") or []) if isinstance(k, dict)])
    note = (f"基线 {len(items)} 项 · 本地源 {len(doc.get('local_sources') or [])} 个 · "
            f"已登记漂移 {n_drift} 项")
    if detail:
        return "FAIL", note, detail
    return "PASS", note, []


# ── 断言 A?: 影响面反查表 (CI/CD Layer 3) ─────────────────────────
# inventory/impact.yaml 登记"每个模型/端口/配置被谁消费"。此断言保证:
#   (a) impact.yaml 存在且 YAML 合法
#   (b) 登记的每个 consumer 路径真实存在 (防"登记即漂移" —— 登记了却指向不存在的地方)
def check_impact(ctx):
    p = INVENTORY_DIR / "impact.yaml"
    if not p.is_file():
        return "WARN", "inventory/impact.yaml 缺失 (影响面反查表未建)", []
    try:
        import yaml
        doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return "FAIL", f"impact.yaml 解析失败: {type(e).__name__}: {e}", []
    missing = []
    checked = 0
    for section in ("models", "ports", "configs"):
        if section not in doc or not isinstance(doc[section], dict):
            continue
        for key, meta in doc[section].items():
            for c in (meta or {}).get("consumers", []):
                if not isinstance(c, str) or not c.strip():
                    continue
                checked += 1
                target = c.split(":", 1)[1] if c.startswith(("file:", "doc:")) else c
                if not (ROOT / target).exists():
                    missing.append(f"{section}/{key} → {c}  不存在")
    note = f"impact.yaml: {len(doc.get('models', {}))} 模型 / {len(doc.get('ports', {}))} 端口 / " \
           f"{len(doc.get('configs', {}))} 配置 · 校验 {checked} 条 consumer"
    if missing:
        return "FAIL", note, missing
    return "PASS", note, []


# ── 断言 A4: 别名解析契约 (回归护栏) ──────────────────────────────
# 为什么门禁要管这个 (2026-09-14):
#   刚修的 bug 是 cluster.py 的 ROUTE 键写成了缩写 (旧值 `qwen3.8-27b`, 站上真实别名
#   是 `qwen3.8-27b-mtp`)。因 resolve_alias 只做单向前缀匹配, 用户输入站上真实别名时
#   匹配失败 → 静默落到 DEFAULT_STATION → **加载到错误的站**, 且 B 站恰有同名 conf
#   故全程不报错。改数据只能修这一次; 故把 resolve_alias 的**契约**钉进门禁:
#     · 每个 ROUTE 键精确命中自己 (how=exact)
#     · 每个 RPC_MODELS 条目走 rpc 分支
#     · **任何 ROUTE 键的前缀都不得静默落默认站** (这正是缺陷类)
#     · 不存在的别名必须显式标 how=default
#     · 多个候选必须抛 AliasError, 不得静默取首个
#   断言**自更新**: 从 cluster 的常量派生用例, 不硬编码 ROUTE 内容。


def check_aliases(ctx):
    sys.path.insert(0, str(ROOT / "ops"))
    try:
        import cluster
    except Exception as e:
        return ("WARN",
                f"无法导入 cluster.py ({type(e).__name__}: {e}) — 该项需 paramiko; "
                f"请用装有 paramiko 的 Python 运行", [])

    detail, warn, n = [], [], 0

    # (1) ROUTE 键精确命中自己
    for key, st in cluster.ROUTE.items():
        n += 1
        got = cluster.resolve_alias(key)
        if got != (st, key, key in cluster.RPC_MODELS, "exact"):
            detail.append(f"ROUTE 键 {key!r} 未精确命中: 实得 {got}")

    # (2) RPC_MODELS 走 rpc 分支
    for m in sorted(cluster.RPC_MODELS):
        n += 1
        got = cluster.resolve_alias(m)
        if got != (None, m, True, "rpc"):
            detail.append(f"RPC_MODELS {m!r} 未走 rpc 分支: 实得 {got}")

    # (3) 核心不变式 (**双向**): 无论输入是 ROUTE 键的前缀, 还是它的**更长变体**,
    #     都不得静默落默认站。
    #     ⚠ 第一版护栏只测了"前缀"方向, 因而对本次真实 bug 无感 —— 真实方向恰恰相反:
    #       输入是站上真实别名 `qwen3.8-27b-mtp`, 而 ROUTE 键是缩写 `qwen3.8-27b`。
    #       注入旧值复验时护栏 PASS, 才发现测错了方向, 遂补上更长变体方向。
    for key in cluster.ROUTE:
        frags = [key[:cut] for cut in (len(key) - 1, max(2, len(key) // 2))
                 if 2 <= cut < len(key)]
        frags.append(key + "-mtp")            # 更长变体 (贴近真实别名形态)
        for frag in frags:
            n += 1
            try:
                _, _, _, how = cluster.resolve_alias(frag)
            except cluster.AliasError:
                continue                      # 明确报错 = 可接受 (不静默)
            if how == "default":
                detail.append(f"{frag!r} (来自 ROUTE 键 {key!r}) 静默落默认站 "
                              f"—— 要防的缺陷类: 用户输入更完整的别名会被送到错误的站")

    # (4) 不存在的别名必须显式标 default
    n += 1
    bogus = "__no_such_alias_xyz__"
    if cluster.resolve_alias(bogus) != (cluster.DEFAULT_STATION, bogus, False, "default"):
        detail.append(f"未知别名 {bogus!r} 未显式落到 default")

    # (5) 歧义必须报错 (打桩 ROUTE 制造共享前缀, 事后还原)
    snap = cluster.ROUTE
    try:
        cluster.ROUTE = {"__amb-a__": "A", "__amb-ab__": "B"}
        n += 1
        try:
            cluster.resolve_alias("__amb-a")
            detail.append("歧义输入未报错 (静默取首个候选 = 会误路由)")
        except cluster.AliasError:
            pass
    finally:
        cluster.ROUTE = snap

    # (6) inventory 里声明了 route 的别名, 必须真的路由到该站
    #     —— 这条才直接抓得住"路由键过期"的原始 bug: 旧值 qwen3.8-27b 时,
    #        解析站上真实别名 qwen3.8-27b-mtp 会报错/落错站, 与 inventory 的声明矛盾。
    _, models = load_inventory()
    for alias, meta in sorted((models or {}).items()):
        if alias != meta.get("alias") or not meta.get("route"):
            continue
        n += 1
        rt = meta["route"]
        try:
            st, _, _, how = cluster.resolve_alias(alias)
        except cluster.AliasError as e:
            detail.append(f"inventory 声明 {alias!r} -> {rt} 站, 但解析报错: {e}")
            continue
        if st != rt:
            detail.append(f"inventory 声明 {alias!r} -> {rt} 站, 实际解析为 {st} 站 (how={how})")

    # (7) 按站路由名 <-> inventory 的 conf 声明 双向一致
    #     · 路由名指向的 (station, 别名) 必须已声明有 conf (FAIL) —— 防止路由名指向一个站上不存在的东西
    #     · inventory 有 conf 的组合应配一个按站路由名 (WARN) —— 保证"能加载的都点得出来"
    declared_conf = set()
    for alias, meta in (models or {}).items():
        if alias != meta.get("alias") or meta.get("_group") == "non_model_conf":
            continue    # non_model_conf (如 rpc-nodes 读的 nodes.env) 不是可加载模型, 不该有按站路由名
        for st in (meta.get("conf") or []):
            declared_conf.add((str(alias), st))
    for name, (st, real) in sorted(cluster.STATION_ROUTES.items()):
        n += 1
        if (real, st) not in declared_conf:
            detail.append(f"按站路由名 {name!r} -> ({st}, {real!r}), 但 inventory/models.yaml "
                          f"未声明 {real} 在 {st} 站有 conf")
    named = {(real, st) for _, (st, real) in cluster.STATION_ROUTES.items()}
    gap = declared_conf - named
    if gap:
        warn.append("inventory 声明有 conf 但缺按站路由名: " +
                    ", ".join(f"{a}@{s}" for a, s in sorted(gap)))

    note = f"别名解析契约 {n} 例"
    if detail:
        return "FAIL", note, detail + [f"(WARN) {w}" for w in warn]
    if warn:
        return "WARN", note, warn
    return "PASS", note, []


# ── 断言 A5: 站上实况对账 (P2, 慢, 非 quick) ───────────────────────
# 把"站上实测"接进对账 —— 在此之前 inventory 只对账仓库内的声明源, 站上是否真的
# 与真值一致无从得知。三站各一次 ssh(合并命令), 做四件事:
#   (a) agent 配置 sha256 三站一致
#   (b) **路由键在目标站真实存在** —— 这条直接防住 §12 那个 bug 复发:
#       路由键过期(站上没这个别名) 会在这里立刻 FAIL, 而不是等用户 load 到错误的站
#   (c) conf 集合: inventory 声明的 conf 必须在站上存在 (缺 = FAIL);
#       站上有而 inventory 未声明 = WARN (可能是新模型/非模型条目, 不该阻断)
#   (d) bind 合规: inventory 里带 expect_bind 的端口, 若站上在监听则地址必须匹配
#   (e) **conf -> 权重存在性**: 每个 /etc/llama-instances/<alias>.env 里的 MODEL_PATH
#       必须真的存在 —— conf 在而权重没了 = load 必失败, 而这种事此前完全不可见。
#       已登记的缺失 (inventory/models.yaml 的 known_broken_conf) 记 WARN 不阻断, 但**新出现的
#       缺失会 FAIL** —— 避免"登记即遗忘"。2026-09-14 首跑即查出 2 处: glm-5.3-flash 与
#       qwen3.8-flash-next (后者还在 cluster.py 的 RPC_MODELS 里, 即被标为"可用"却加载不了)。
#
# 为什么模型侧只查 conf 与"点名几个路由键", 不做全量比对:
#   /etc/llama-instances/*.env 是**人工维护的命名集合**, 稳定可双向比对;
#   而 infer-list 反映模型库(下载即变), 全量比对必然天天误报 —— 故只做定点查询。
WATCHED = ["~/.config/opencode/opencode.jsonc", "~/.claude/settings.json"]

# 站上 LAN 地址采集命令 —— ★ **单一实现**：直连探针（本 STATION_CMD 的 [lanip] 段）与
#   USB4 降级通道（`_lanip_via_usb4` 经邻站中转）**共用同一条**，避免"同一事实两个定义点"。
#   · `scope global` 天然排除 `lo` 的 `scope host`（**不要**用 `grep -v lo` —— "global" 里就含 `lo`）；
#   · 整串**不含任何引号** ⇒ 可安全嵌进 `ssh <ip> "<cmd>"` 的双引号里（引号嵌套是本仓反复踩的坑）。
_LANIP_CMD = "ip -4 -o addr show scope global 2>/dev/null | cut -c1-160"

STATION_CMD = (
    "printf '\\n[cfg]\\n'; sha256sum " + " ".join(WATCHED) + " 2>/dev/null | cut -c1-16; "
    "printf '\\n[conf]\\n'; ls -1 /etc/llama-instances/*.env 2>/dev/null "
    "| xargs -r -n1 basename | sed 's/\\.env$//' | tr '\\n' ' '; echo; "
    "printf '\\n[bind]\\n'; ss -ltn 2>/dev/null | awk 'NR>1{print $4}' | tr '\\n' ' '; echo; "
    # (i) LAN 地址实况 (ADR-0006 v1.1 · D6, 2026-09-29): 站上**实际**的 global-scope IPv4。
    #   为什么必须从站上取（而不是像旧版那样只看 master 侧 `ssh -G` 的绑定）:
    #     旧判据的射程靠"别名"，C 站 `host: null` ⇒ **整站被跳过**，于是 2026-09-29 C 的
    #     LAN 由 .37 漂到 .8 时，门禁只报"可达 2/3 站"、**给不出根因**。
    #   ⚠ 本段**不新增连接** —— 搭在同一次合并 ssh 上（与 [bind]/[conf] 同源）。
    "printf '\\n[lanip]\\n'; " + _LANIP_CMD + "; "
    # UDP 侧单独一段 (P1-4): 系统里长期监听的 UDP 端口并不少 (nmbd/avahi/NetworkManager/
    # wsdd/netconsole/rpc.statd), 只查 TCP 会让它们对账时"看不见"。
    "printf '\\n[ubind]\\n'; ss -lun 2>/dev/null | awk 'NR>1{print $4}' | tr '\\n' ' '; echo; "
    # 插件面事实 (P1-5): 由站上工具一次性汇报 `id=value` 行, 判定留在门禁侧。
    # 不把采集逻辑内联在这里 —— JSONC 解析 + 目录遍历 + 软链可达性判断用 shell
    # 单行串写会变成转义地狱, 且三站口径无法保证一致。
    "printf '\\n[plug]\\n'; plugin-probe 2>/dev/null || true; "
    "printf '\\n[mpath]\\n'; for f in /etc/llama-instances/*.env; do [ -e \"$f\" ] || continue; "
    "a=${f##*/}; a=${a%.env}; p=$(sed -n 's/^MODEL_PATH=//p' \"$f\" | head -1 | tr -d '\"'); "
    "if [ -z \"$p\" ]; then echo \"$a NO_MODEL_PATH\"; "
    "elif [ -f \"$p\" ]; then echo \"$a OK\"; else echo \"$a MISSING $p\"; fi; done; "
    # (f) 凭据引用完整性 —— 2026-09-14 补: 起因是把 B/C 的 apiKeyHelper 抄进 A 站 settings.json
    # 时**没有把被引用的 claude-key.sh 一起部署**, 而所有断言都只看"配置文件是否一致",
    # 没有任何一条检查"被引用的文件是否存在"。此段专门堵这个盲区。
    "printf '\\n[cred]\\n'; "
    "HB=$(grep -o '\"apiKeyHelper\"[^,}]*' ~/.claude/settings.json 2>/dev/null | head -1 "
    "| sed 's/.*\"\\([^\"]*\\)\"$/\\1/'); "
    "if [ -z \"$HB\" ]; then echo 'helper=UNCONFIGURED'; "
    "elif [ ! -e \"$HB\" ]; then echo \"helper=MISSING:$HB\"; "
    "elif [ ! -x \"$HB\" ]; then echo \"helper=NOEXEC:$HB\"; "
    "else OUT=$(\"$HB\" 2>/dev/null | tr -d '\\n'); "
    "if [ -n \"$OUT\" ]; then echo \"helper=OK:${#OUT}\"; else echo \"helper=EMPTY:$HB\"; fi; fi; "
    "for P in $(grep -o '{file:[^}]*}' ~/.config/opencode/opencode.jsonc 2>/dev/null | sed 's/{file://;s/}//'); do "
    "Q=$(echo \"$P\" | sed \"s|~|$HOME|\"); "
    "if [ -s \"$Q\" ]; then echo \"ocfile=OK:$(basename \"$Q\")\"; else echo \"ocfile=BAD:$P\"; fi; done; "
    # 2026-09-16 (A) 判据升级: 原为「claude.key vs unsloth.key 两个文件互相比较」。实测该判据
    # 背后藏着结构缺陷 —— claude.key 是引擎 key 的第二份拷贝而**没有任何写入方** (infer-load
    # 每次加载只重铸落盘 unsloth.key), 于是它必然陈旧: C 站遗留脱敏占位串, A/B 只是靠人工
    # 同步过一次才对上, 且**下次加载即变黄**。改为比较「apiKeyHelper 的实际输出 vs 同站引擎
    # key」—— 这才是功能判据 (claude 真正拿到的 key), 且单一真值就是 unsloth.key。
    # helper 不可用时输出 SKIP (该情形已由上面 helper=EMPTY/MISSING/NOEXEC 报出, 不重复告警)。
    "UK=$(cat ~/.config/rpc/unsloth.key 2>/dev/null | tr -d '\\n'); "
    "if [ -z \"$OUT\" ]; then echo 'claudekey=SKIP_NO_HELPER'; "
    "elif [ \"$OUT\" = \"$UK\" ]; then echo 'claudekey=HELPER_EQ_UNSLOTH'; "
    "else echo 'claudekey=DIFFERS'; fi; "
    # (f2) unsloth studio 日志的明文面 (2026-09-16 增补): studio 每次加载都会把引擎 key 写进
    # ~/.unsloth/run-<alias>.log (实测每次 4 处), 而 infer-load 正是**从该日志 grep 取 key** ⇒
    # "日志含 key" 是设计使然、无法消除, 所以判据只能落在**权限**上:
    #   ~/.unsloth 须 700, run-*.log 须 600 (默认 umask 022 下是 775/664 ⇒ 组与其他用户可读)。
    # 顺带报"含 key 的日志份数 + 总份数", 供评估存量(实测三站曾累积 16 个历史 key / 64 处明文)。
    "DP=$(stat -c %a $HOME/.unsloth 2>/dev/null || echo NA); "
    "LF=$(ls -1 $HOME/.unsloth/run-*.log 2>/dev/null | wc -l); "
    "LK=$(grep -lE 'sk-(or-v1|unsloth|RPC|local|lm)-[A-Za-z0-9_-]{6,}' $HOME/.unsloth/run-*.log 2>/dev/null | wc -l); "
    "LL=$(find $HOME/.unsloth -maxdepth 1 -name 'run-*.log' ! -perm 0600 2>/dev/null | wc -l); "
    "echo \"unslothlog=dirperm:${DP} files:${LF} withkeys:${LK} loose:${LL}\"; "
    # (h) 长龄 orphan 探针 (O-58, 2026-09-25): 站上 ad-hoc ssh 探针/派发留下的僵尸/长龄进程。
    #   起因(一手实测): B 站留了 2 条 —— `bash` 1-12:19 与 `bash`+**活着的裸 `opencode`**
    #   1-04:59(47 fd、持**共享** `opencode.db` 180MB)；根因是**未加引号的 `|`** 被远端 shell
    #   当管道(纪律 12)。该信号此前**只能靠人肉 `ps` 偶然撞见** ⇒ 本段把它变机判。
    #   ⚠ 模式**不带空格**且用**多枚 `-e`**：带空格的引号经 PS/ssh 会被剥掉，远端 shell 会把
    #     模式后半当**文件名**(纪律 12, 实测 `grep: run: 没有那个文件或目录`)。
    #   只输出 `pid ppid etimes comm` 四列，**阈值与豁免全留在门禁侧**(与 [conf]/[mpath] 同分工)。
    "printf '\\n[orph]\\n'; ps -eo pid=,ppid=,etimes=,comm= 2>/dev/null "
    "| grep -e opencode -e claude -e timeout -e defunct | head -20; "
    # (i) O-70 第二类: 白名单**之外、但是我们自己的**残留（2026-09-25）—— **只报数, 不判定**。
    #   为什么需要: (h) 的白名单只认 4 个 comm ⇒ 实测那条**真孤儿**(`bash /tmp/agent-cli-task-*.sh`
    #     + 它的 `sleep` 子壳, 存活 **28.6h**, 见台账 O-72)**完全不在白名单里** ⇒ 只因人肉 `ps` 才发现
    #     = b3 说的"**在路灯下找钥匙**"。
    #   ⚠⚠ 第一版按 `ps -u $USER --ppid 1` 取 —— **实测两处都不成立**:
    #     ① 在一台桌面机上它抓到 **122 条系统守护**(`systemd-journald`/`udevd`/`avahi-daemon`…, 全是 **root**)
    #        ⇒ 说明 `$USER` 在**非登录 ssh 会话**里可能为空 ⇒ `-u` 过滤**静默失效**（纪律 12 同族: 别赌远端变量在）;
    #     ② 即便过滤对了, 桌面用户的 `ppid=1` 也天然包含 `systemd --user` 等**合法**长龄进程 ⇒ 恒有噪声。
    #   ⇒ 改成按**产物名**匹配(args 里出现我们自己的脚本名): 这是"事实"判据、噪声面小得多,
    #     且**正好**覆盖 O-72 那一类。阈值仍留在门禁侧(下面按 `ORPHAN_SEC` 判)。
    # ★★ 2026-09-26 结构性修法：**按 pgid 排除探针自己的整个进程组**（不再靠文本巧合）。
    #   起因（本轮实测）：直查时用 `pgrep -af agent-cli-task …` ⇒ **它自匹配了自己所在的命令行**
    #     ⇒ 说明"自匹配"是这条探针的**真实**风险，不是理论风险。
    #   旧版靠 `grep -v -e grep` 恰好挡住（自匹配行里也含 `grep` 一词）—— **侥幸成立**，
    #     代价是：**任何 args 里含子串 `grep` 的真残留会被静默排掉**（"路灯下找钥匙"的第二个面）。
    #   ⚠ 我曾以为"把排除键换成 `ps -eo`"是正解 —— **三站实测证伪**：那样会漏掉
    #     `grep -e agent-cli-task …` **进程自己**（其 args 含 `agent-cli-task` 却不含 `ps -eo`）⇒ 假阳性 1 行。
    #   ⇒ 现改为：`ps` 多输出一列 pgid + `awk` 剔除 `$2 == 自身 pgid`。
    #     shell / ps / grep / awk **同属一个进程组** ⇒ 一次全剔，**不依赖任何模式串**。
    #   ★ 实测对照（三站，注入假残留前后）：
    #       无残留 ⇒ **NEW 0 行**（旧版 0 行 / NAIVE 1 行假阳性）；有真残留 ⇒ **NEW 1 行，且只有真的那条**。
    #   ⚠ awk 把 pgid 列清空 ⇒ 输出行多一个空格；门禁侧用 `line.split()` 解析 ⇒ 不受影响（已实测）。
    "printf '\\n[orph2]\\n'; ps -eo pid=,pgid=,etimes=,args= 2>/dev/null "
    "| awk -v pg=$(ps -o pgid= -p $$ | tr -d ' ') '$2!=pg { $2=\"\"; print }' "
    "| grep -e agent-cli-task -e agent-stage- -e _oc_session_meta -e _p3_run -e _station_ready -e _slot_gate "
    "| head -20; "
)
# 刻意不取 infer-list: (1) 它自身约 10s+, 三站并行也要 30s+ (实测全量从 31s 涨到 60s);
# (2) 判定"别名在该站是否可用"本来就该看 conf —— infer-load 读的正是
#     /etc/llama-instances/<alias>.env, 模型库里有而 conf 没有的别名是 load 不了的。

SEC_RE = re.compile(r"^\[(\w+)\]$")


def _parse_sections(out):
    """按 [name] 分段解析远端合并命令的输出。"""
    sec, cur = {}, None
    for line in out.splitlines():
        m = SEC_RE.match(line.strip())
        if m:
            cur = m.group(1)
            sec[cur] = []
        elif cur is not None:
            sec[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in sec.items()}


def _ssh_g_hostname(alias):
    """`ssh -G <别名>` 的 hostname 字段 (**纯本地展开, 不建连**)。ssh 不可用返回 None。

    用于 ADR-0006 的 LAN 绑定对账: 名字是否仍被绑定到 net.yaml 登记的 LAN IPv4。
    """
    try:
        r = subprocess.run(["ssh", "-G", alias], capture_output=True, text=True,
                           timeout=20, encoding="utf-8", errors="replace")
    except Exception:
        return None
    for line in (r.stdout or "").splitlines():
        if line.lower().startswith("hostname "):
            return line.split(None, 1)[1].strip()
    return None


# ── LAN 地址对账（ADR-0006 v1.1 · D6，2026-09-29）──────────────────────────────
# 背景（一句话）：D4 的判据靠 `ssh -G <别名>`，于是 `host: null` 的 C 站**整站不在射程内**；
#   2026-09-29 C 的 LAN 由 .37 漂到 .8 时，6 项断言只报"可达 2/3 站"、**不给根因**
#   —— 正是 ADR-0006 D4 自己要消灭的那个"ssh 连不上的谜题"。
# 本节把判据换成"**站上实况** vs net.yaml 真值"，并在 LAN 不可达时**经 USB4 段向邻站中转**去问。
#
# 为什么判据与 IO **分开**：① 门禁侧只判不做 IO ⇒ **可先验红**（本仓纪律，见
#   tests/test_rpc_check_lan_drift.py）；② 直连与降级通道产出**同一种** `seen` ⇒ 判据只有一份。
def _local_lan_ip(probe_ip):
    """取**本机通往 probe_ip 那条路**上使用的源地址（= 本机的 LAN 管理面地址）。

    为什么用 UDP-connect 这个怪招：① **不发任何包**（UDP connect 只做路由选择），零流量、不打扰；
    ② 只用 stdlib（`ipconfig` 解析在中文 Windows 上字段名会变、且不可移植）；
    ③ 它回答的正是我们要问的问题 —— "**我用哪个地址去够那些站**"（而不是"本机一共配了哪些地址"）。
    失败返回 None（调用方按"无法判定"处理，**不猜**）。

    ★ 为什么主控也要判（2026-09-29 实测新增）：本轮排查中**主控自己的 LAN 先漂了**
      （`192.168.1.36` → `192.168.10.102`，整段换网），表现就是"三站全不可达" —— 又一个
      "可达 0/3 却不给根因"的谜题，且它比单站漂移**更彻底**（控制面全断）。
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((str(probe_ip), 9))
        return s.getsockname()[0]
    except Exception:
        return None
    finally:
        s.close()


def _parse_lanip(text):
    """解析 `ip -4 -o addr show scope global` 的原始输出 ⇒ [{iface, ip, cidr, dynamic}]。

    样例: `2: eno1    inet 192.168.1.8/24 brd 192.168.1.255 scope global dynamic noprefixroute eno1\\ ...`
    ⇒ 取行首的 `序号: 接口`、`inet <地址>/<前缀>`，并看整行里有没有 `dynamic`（DHCP）。
    ★ **这里也丢回环**（defense in depth）：真值源命令已用 `scope global` 过滤掉 `lo`，
      但**判据不该依赖调用方那半条 shell** —— 若将来有人动 `_LANIP_CMD`，`lo` 会变成
      "非 USB4 网段的唯一地址"而被误当成 LAN 地址。故解析层再过一遍。
    解析不出的行**忽略**（不猜）；全空 ⇒ 调用方走降级通道/报"无法判定"。
    """
    rows = []
    for ln in (text or "").splitlines():
        m = re.match(r"^\s*\d+:\s+(\S+)\s+inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)\s+(.*)$", ln)
        if not m or m.group(1) == "lo" or m.group(2).startswith("127."):
            continue
        rows.append({"iface": m.group(1), "ip": m.group(2),
                     "cidr": f"{m.group(2)}/{m.group(3)}",
                     "dynamic": "dynamic" in m.group(4)})
    return rows


def pick_lan_addr(rows, iface_hint, seg_nets):
    """从站上所有 global 地址里挑出**LAN 管理面**那一个。返回 ({...} | None, 原因串)。

    为什么需要挑：站上同时有 USB4 三段地址，都算 `scope global`。挑法（**先精后宽**）：
      ① 登记了 `iface` ⇒ **认接口**（最精确，且与 net.yaml 的声明同源）；
      ② 否则排除 USB4 各段的网段，剩下的**唯一**一个才算 LAN 地址；
      ③ 剩 0 个或多个 ⇒ **不猜**，返回原因（同本仓"解析失败不能表现成业务全错"纪律）。
      ④ ①命中但与②的候选集不一致（登记接口 ≠ 非 USB4 地址）⇒ 也返回原因 —— 那说明
         net.yaml 的 `iface` 与 `segments` 至少有一个是错的。
    """
    rows = rows or []
    lan_rows = [r for r in rows if not any(ipaddress.ip_address(r["ip"]) in n for n in (seg_nets or []))]
    if iface_hint:
        hit = [r for r in rows if r["iface"] == iface_hint]
        if len(hit) == 1:
            if lan_rows and hit[0]["ip"] not in {r["ip"] for r in lan_rows}:
                return None, (f"net.yaml 登记的 iface={iface_hint} 上的地址 {hit[0]['ip']} "
                              f"落在 USB4 网段内（与 segments 冲突）⇒ net.yaml 自相矛盾, 不猜")
            return hit[0], None
        if len(hit) > 1:
            return None, f"iface={iface_hint} 上有多个 global 地址 ({[r['ip'] for r in hit]}) ⇒ 不猜"
        return None, (f"net.yaml 登记的 iface={iface_hint} 在站上不存在（实测接口: "
                      f"{sorted({r['iface'] for r in rows})}）")
    if len(lan_rows) == 1:
        return lan_rows[0], None
    if not lan_rows:
        return None, "站上没有任何非 USB4 网段的 global 地址 ⇒ 该站 LAN 可能已断"
    return None, f"非 USB4 网段的 global 地址有 {len(lan_rows)} 个 ({[r['ip'] for r in lan_rows]}) ⇒ 不猜"


def validate_lan_addr(lan_doc, seen, seen_master=None):
    """★ 纯判据（D6）：`net.yaml §lan` 真值 vs **实测** LAN 地址。返回 (detail, warn, info)。

    detail(FAIL) = 实测 ≠ 真值 —— ★ 这里必须**带根因与修法**（本次改判据的全部意义所在）
    warn         = 判定**不成立**（探不到 / 解析不出 / 登记自相矛盾）或接口漂移
    info         = 射程声明：哪些站"没有可判的东西"必须**显式说出来**（不得像旧版那样静默跳过）

    seen        : {station: {"ip","iface","dynamic"} | {"error": "<原因>"} | None}
                  （None = 该站根本没采集到 ⇒ 也算"判定不成立"，**不是**通过）
    seen_master : {"ip": ...} | {"error": ...} | None —— **主控自身**的 LAN 地址。
      ★ 射程含主控的理由（2026-09-29 实测）：主控的 LAN 一漂，**三站全不可达** ——
        那是"可达 0/3 却不给根因"的最坏形态。主控地址就登记在 net.yaml §lan 的 `master.ip`。
    """
    detail, warn, info = [], [], []

    # ⓪ **主控自身**（先判它：它错了，下面三站的"不可达"是**同一个根因**，不是三个问题）
    m_want = ((lan_doc.get("master") or {}) or {}).get("ip")
    if m_want:
        if not seen_master:
            warn.append(f"master 自身 LAN 地址**无法判定**（net.yaml §lan.master 登记 {m_want}）")
        elif seen_master.get("error"):
            warn.append(f"master 自身 LAN 地址**无法判定**：{seen_master['error']}")
        elif seen_master.get("ip") and seen_master["ip"] != m_want:
            detail.append(
                f"★★ **master（本机）自身的 LAN 地址已漂移**: {m_want} → {seen_master['ip']} "
                f"—— ★ 这是**三站全部不可达**的根因（控制面源地址变了）；"
                f"先修 master（接到正确的网 / 或更新 net.yaml §lan.master 的登记），再谈各站")
        elif seen_master.get("ip"):
            info.append(f"master 自身 LAN 地址与真值一致: {seen_master['ip']}")
    for ent in (lan_doc.get("stations") or []):
        if not isinstance(ent, dict):
            continue
        st, want, iface_hint = ent.get("station"), ent.get("ip"), ent.get("iface")
        if not st or not want:
            warn.append(f"net.yaml §lan 有条目缺 station/ip, 本项无法判: {ent!r}")
            continue

        # ① master 侧**名字绑定**（ADR-0006 D1 的资产）—— 与站上实况是**两个不同的面**，都留着。
        alias = ent.get("host")
        if not alias:
            # ★ 射程**显式化**：旧版这里是一句 `continue`，于是"C 不在射程内"**无人知道**。
            info.append(f"{st} 站在 net.yaml 里无别名(host: null) ⇒ 无 master 侧绑定可判；"
                        f"该站由下面的『站上实况』覆盖（射程声明, 非跳过）")
        else:
            got = _ssh_g_hostname(alias)
            if got is None:
                warn.append(f"`ssh -G {alias}` 不可用 —— 无法核对 master 侧绑定 (该名应绑定到 {want})")
            elif got != want:
                detail.append(f"master 侧绑定漂移: `ssh -G {alias}` 的 hostname={got}, "
                              f"而 net.yaml §lan 登记 {want} ⇒ 同步 master ~/.ssh/config 与 net.yaml")

        # ② ★ 站上实况（D6 新增；不依赖别名 ⇒ 三站全覆盖）
        s = seen.get(st)
        if not s:
            warn.append(f"{st} 站 LAN 地址**无法判定**：直连采集不到，USB4 降级通道也没取回 ⇒ "
                        f"本项对该站**不成立**（不是通过）")
            continue
        if s.get("error"):
            warn.append(f"{st} 站 LAN 地址**无法判定**：{s['error']}")
            continue
        got, got_iface, dyn = s.get("ip"), s.get("iface"), s.get("dynamic")
        if not got:
            warn.append(f"{st} 站 LAN 地址**无法判定**：采集到但解析不出 (原始: {str(s)[:80]})")
            continue
        if got != want:
            detail.append(
                f"★ {st} 站 LAN 地址**已漂移**: {want} → {got} "
                f"(iface={got_iface}, scope={'dynamic/DHCP' if dyn else 'static'}) —— "
                f"这与「{st} 站不可达 / 依赖它的断言红灯」是**同一件事**, 根因在此。"
                f"修法: 同步三处真值 (inventory/net.yaml §lan · ops/cluster_const.py 的 STATIONS · "
                f"master ~/.ssh/config); 要**根治**见 ADR-0006 v1.1 的 D5")
        else:
            info.append(f"{st} 站 LAN 地址与真值一致: {got} (iface={got_iface})")
        if iface_hint and got_iface and iface_hint != got_iface:
            warn.append(f"{st} 站 LAN 地址所在接口已变: 实测 {got_iface}, net.yaml 登记 {iface_hint} "
                        f"⇒ 更新 net.yaml §lan 的 iface")
    return detail, warn, info


def _lanip_via_usb4(target, segs, live, ssh_run):
    """LAN 直连采集失败时，经**与该站有 USB4 直连的邻站**中转，去问它自己的 LAN 地址。

    ★ 这是 D6 的关键一步：它让「站不可达」与「地址漂移」**可区分**。
      2026-09-29 实测：C 的 LAN 已断（.37 消失），但经 `B → 10.10.11.3` 完全可达
      ⇒ 能问出它当时的真实地址（.8）—— 旧判据在这里只会吐一句"可达 2/3 站"。
    邻站与目标站的 USB4 地址**全部从 net.yaml §segments 派生**（不硬编码拓扑）。
    返回 (rows, err)：err=None 表示取回；否则是**响亮**的原因串（不静默、不降级成"通过"）。
    """
    cands = []
    for sg in (segs or []):
        if not isinstance(sg, dict):
            continue
        for e in (sg.get("ends") or []):
            if isinstance(e, dict) and e.get("station") == target and e.get("peer") and e.get("ip"):
                cands.append((e["peer"], e["ip"]))
    if not cands:
        return [], f"net.yaml §segments 里没有 {target} 站的 USB4 端点 ⇒ 无降级通道可走"
    errs = []
    for peer, ip in cands:
        if not live.get(peer):
            errs.append(f"邻站 {peer} 自身不可达")
            continue
        try:
            ok, out = ssh_run(peer, f'ssh -o BatchMode=yes -o ConnectTimeout=6 {ip} "{_LANIP_CMD}"',
                              timeout=40)
        except Exception as e:
            errs.append(f"经 {peer}→{ip}: {type(e).__name__}: {str(e)[:60]}")
            continue
        rows = _parse_lanip(out)
        if ok and rows:
            return rows, None
        errs.append(f"经 {peer}→{ip}: {'取回但解析不出' if ok else 'ssh 未成功'}")
    return [], f"降级通道全失败 ({'; '.join(errs)})"


def check_stations(ctx):
    sys.path.insert(0, str(ROOT / "ops"))
    try:
        import cluster
    except Exception as e:
        return ("WARN",
                f"无法导入 cluster.py ({type(e).__name__}: {e}) — 该项需 paramiko; "
                f"请用装有 paramiko 的 Python 运行 (见 ops/rpc.ps1 的解释器选择)", [])

    ports_inv, models_inv = load_inventory()
    # detail = 判定失败的项; info = 上下文 (仅在失败/告警时附带打印, 不参与判定)
    detail, warn, info = [], [], []

    live = {}
    for st in ("A", "B", "C"):
        ok, out = cluster.ssh_run(st, STATION_CMD, timeout=90)
        live[st] = _parse_sections(out) if ok else None

    unreachable = [st for st, v in live.items() if not v]
    reach = [st for st in ("A", "B", "C") if live.get(st)]

    # (a) agent 配置 sha256 三站一致
    for i, path in enumerate(WATCHED):
        vals = {st: (live[st].get("cfg", "").splitlines()[i:i + 1] or ["(缺失)"])[0]
                for st in reach}
        row = f"{path}  " + " ".join(f"{st}={v}" for st, v in sorted(vals.items()))
        if len(set(vals.values())) > 1:
            detail.append(f"三站不一致: {row}")
        else:
            info.append(f"三站一致: {row}")

    # (b) 路由键 / RPC 模型 必须在目标站真实存在 (判据用 conf —— infer-load 读的就是它)
    def has(st, key):
        return key in (live.get(st) or {}).get("conf", "").split()

    for key, st in cluster.ROUTE.items():
        if st in reach and not has(st, key):
            detail.append(f"ROUTE 键 {key!r} 在目标站 {st} 站无 conf —— 该键已过期, "
                          f"load 会失败或落错站 (站上 conf: "
                          f"{', '.join(sorted((live[st].get('conf') or '').split()))})")
    for m in sorted(cluster.RPC_MODELS):
        if not any(has(st, m) for st in reach):
            detail.append(f"RPC 模型 {m!r} 在所有可达站都无 conf")

    # (c) conf 集合: 声明的必须存在 (缺=FAIL); 多出来的 = WARN
    #     load_inventory 会扫 models.yaml 的每个顶层列表, 故 non_model_conf 里的
    #     nodes 也一并进入 models_inv (带 alias+conf 字段), 这里无需另开分支。
    declared_conf = {}
    for alias, meta in (models_inv or {}).items():
        if alias != meta.get("alias"):
            continue
        for st in (meta.get("conf") or []):
            declared_conf.setdefault(st, set()).add(alias)
    for st in reach:
        live_conf = set((live[st].get("conf") or "").split())
        miss = declared_conf.get(st, set()) - live_conf
        if miss:
            detail.append(f"{st} 站缺少 inventory 已声明的 conf: {', '.join(sorted(miss))} "
                          f"—— 站上被删或 inventory 过期")
        extra = live_conf - declared_conf.get(st, set())
        if extra:
            warn.append(f"{st} 站 conf 有未登记条目: {', '.join(sorted(extra))} "
                        f"(新模型请登记到 inventory/models.yaml; 非模型条目应清理)")

    # (d) bind 合规 (仅查声明了 expect_bind 的端口)
    for st in reach:
        binds = {}
        for tok in (live[st].get("bind") or "").split():
            if ":" in tok:
                addr, _, p = tok.rpartition(":")
                if p.isdigit():
                    binds[int(p)] = addr
        for port, meta in (ports_inv or {}).items():
            exp = meta.get("expect_bind")
            if not exp or port not in binds:
                continue
            got = binds[port]
            if got not in (exp, exp.replace("127.0.0.1", "localhost")):
                detail.append(f"{st} 站 :{port} ({meta.get('purpose', '?')}) 实际监听 {got}, "
                              f"inventory 要求 {exp} —— 暴露面超预期")

    # (e) conf -> 权重存在性
    broken = set()
    try:
        import yaml
        _doc = yaml.safe_load((INVENTORY_DIR / "models.yaml").read_text(encoding="utf-8")) or {}
        broken = {(it.get("station"), it.get("alias"))
                  for it in (_doc.get("known_broken_conf") or [])}
    except Exception:
        pass
    non_model = {a for a, m in (models_inv or {}).items() if m.get("_group") == "non_model_conf"}
    for st in reach:
        for line in (live[st].get("mpath") or "").splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            alias, status = parts[0], parts[1]
            where = parts[2] if len(parts) > 2 else "?"
            if status == "MISSING":
                if (st, alias) in broken:
                    warn.append(f"{st} 站 {alias} 权重缺失 (已登记 known_broken_conf): {where}")
                else:
                    detail.append(f"{st} 站 {alias} 的 conf 指向的权重不存在 → load 必失败 ({where})")
            elif status == "NO_MODEL_PATH" and alias not in non_model:
                warn.append(f"{st} 站 {alias}.env 无 MODEL_PATH, 且未登记为 non_model_conf")

    # (f) 凭据引用完整性 —— settings.json 的 apiKeyHelper / opencode 的 {file:...}
    #     必须"引用得到、非空、可执行"; 以及 claude helper 的输出是否等于同站引擎 key。
    for st in reach:
        for line in (live[st].get("cred") or "").splitlines():
            line = line.strip()
            if line.startswith("helper="):
                v = line.split("=", 1)[1]
                if not v.startswith("OK:"):
                    detail.append(f"{st} 站 claude apiKeyHelper 不可用 ({v}) —— "
                                  f"settings.json 引用的脚本不存在/不可执行/输出为空")
            elif line.startswith("ocfile="):
                v = line.split("=", 1)[1]
                if not v.startswith("OK:"):
                    detail.append(f"{st} 站 opencode provider 引用的凭据文件不可用 ({v}) "
                                  f"—— 不存在或为空")
            elif line.startswith("claudekey="):
                # 2026-09-16 (A): 判据改为「helper 输出 == 同站 unsloth.key」。SKIP_NO_HELPER
                # 不在此告警 (helper 自身的问题已由上面 helper= 行报出)。
                if line.split("=", 1)[1] == "DIFFERS":
                    warn.append(f"{st} 站 claude apiKeyHelper 的输出与同站引擎 key "
                                f"(~/.config/rpc/unsloth.key) 不一致 —— claude 走本地 :8080, "
                                f"必须与 opencode 用同一份引擎 key; 站上跑一次 infer-load 会重铸该 key")
            elif line.startswith("unslothlog="):
                # 2026-09-16 (f2): unsloth studio 日志的明文面 —— 判据是**权限**而非"含不含 key"
                # (studio 每次加载必写 key 进日志, 且 infer-load 依赖从日志取 key, 消除不掉)。
                kv = dict(p.split(":", 1) for p in line.split("=", 1)[1].split() if ":" in p)
                dp = kv.get("dirperm", "NA")
                loose = kv.get("loose", "0")
                wk = kv.get("withkeys", "0")
                if dp not in ("700", "NA"):
                    warn.append(f"{st} 站 ~/.unsloth 权限 {dp} (应 700) —— 该目录含 studio 每次"
                                f"加载写入的引擎 key 明文日志; 修: chmod 700 ~/.unsloth")
                if loose != "0":
                    warn.append(f"{st} 站 {loose} 份 run-*.log 权限非 600 (含 key 的共 {wk} 份) "
                                f"—— 修: chmod 600 ~/.unsloth/run-*.log")

    # (g) 站上监听端口 vs 分配表 (P1-4 占用对账)
    #     方向一 (FAIL): 站上在听、端口 < EPHEMERAL_MIN、且分配表里没有它 →
    #        真值表漏登记 (第一次跑就查出 137/138/546/5353/3702/6665/724 七类)。
    #        ≥ EPHEMERAL_MIN 的一律豁免: 该段是内核临时端口, 服务每次启动换号
    #        (NFS mountd/statd 即典型), 登记端口号必然过期。
    #     方向二 (WARN): 分配表声明在用、站上却没听 → 可能只是服务挂了。
    #        带 status 或 mode: on_demand 的条目豁免 (如 studio 的 8080 本就是按需启停)。
    try:
        port_entries = _port_entries()
    except Exception as e:
        # 解析失败必须报真因, 不能让下面的循环把"整张表读不出"表现成
        # 几十条"端口未登记"的假象 (2026-09-15 实测踩到), 故直接跳过整段对账。
        port_entries = None
        detail.append(f"ports.yaml 解析失败, 端口占用对账无法进行 —— "
                      f"{type(e).__name__}: {str(e)[:160]}")
    ignored_eph, checked_ports = 0, 0
    if port_entries is not None:
        by_port = {}
        for g in ("managed", "third_party", "unmanaged"):
            for e in port_entries.get(g) or []:
                if isinstance(e, dict) and isinstance(e.get("port"), int):
                    by_port.setdefault(e["port"], []).append((g, e))

        def _reg_covers(port, side, st):
            """分配表是否已登记该 (端口, 协议侧, 站)。

            proto 语义: tcp/http/https → TCP 侧; udp → UDP 侧;
                        tcp+udp → 两侧 (mihomo 的 mixed / DNS 端口即双栈);
                        缺省 → 两侧都算 (unmanaged 里的系统端口多不关心协议侧)。
            """
            for g, e in by_port.get(port, []):
                if st not in _scopes(e):
                    continue
                p = str(e.get("proto") or "").lower()
                if p == "udp" and side != "udp":
                    continue
                if p in ("tcp", "http", "https") and side != "tcp":
                    continue
                return True                  # tcp+udp 与缺省都覆盖两侧
            return False

        def _listening(st, sec):
            out = set()
            for tok in (live[st].get(sec) or "").split():
                if ":" in tok:
                    p = tok.rpartition(":")[2]
                    if p.isdigit():
                        out.add(int(p))
            return out

        for st in reach:
            for side, sec in (("tcp", "bind"), ("udp", "ubind")):
                for port in sorted(_listening(st, sec)):
                    checked_ports += 1
                    if _reg_covers(port, side, st):
                        continue
                    if port >= EPHEMERAL_MIN:
                        ignored_eph += 1
                        continue
                    detail.append(f"{st} 站 {side.upper()} :{port} 有监听但分配表未登记 —— "
                                  f"是常驻服务就登记到 inventory/ports.yaml "
                                  f"(我方 = managed, 他方 = third_party/unmanaged)")
            # 方向二
            for g in ("managed", "third_party"):
                for e in port_entries.get(g) or []:
                    if not isinstance(e, dict) or not isinstance(e.get("port"), int):
                        continue
                    if st not in [str(x) for x in (e.get("scope") or [])]:
                        continue      # 反向只查明确声明了该站的条目
                    if e.get("status") or str(e.get("mode") or "") == "on_demand":
                        continue
                    if (e["port"] in _listening(st, "bind")
                            or e["port"] in _listening(st, "ubind")):
                        continue
                    warn.append(f"{st} 站 :{e['port']} ({e.get('purpose', '?')}, "
                            f"owner={e.get('owner', '?')}) 声明在用但未监听 —— "
                            f"服务挂了? 若本就按需启停, 加 mode: on_demand")

    # (h) 插件/技能三站同构 (P1-5)
    #     站上 plugin-probe 汇报 `id=value` → 与 inventory/plugins.yaml 的 expect 逐项比对。
    #     known_drift 命中降 WARN, 但**只有"恰好多出已登记的那些"**才降级 —— 少了元素、
    #     或多了未登记的东西, 一律 FAIL (与 models.yaml 的 known_broken_conf 同一精神:
    #     已登记的可见不阻断, 但新差异不许被登记这件事糊过去)。
    try:
        pdoc = _plugins_doc()
    except Exception as e:
        pdoc = None
        detail.append(f"inventory/plugins.yaml 解析失败, 插件同构对账无法进行 —— "
                      f"{type(e).__name__}: {str(e)[:160]}")
    plugin_checked = 0
    if pdoc is not None:
        pitems = _plugin_items(pdoc)
        drift = {}
        for kd in pdoc.get("known_drift") or []:
            if isinstance(kd, dict) and kd.get("id") in pitems:
                drift[(str(kd.get("station")), str(kd.get("id")))] = \
                    sorted(str(x) for x in (kd.get("extra") or []))

        for st in reach:
            facts = {}
            for line in (live[st].get("plug") or "").splitlines():
                if "=" in line:
                    k, _, v = line.partition("=")
                    facts[k.strip()] = v.strip()
            if not facts:
                warn.append(f"{st} 站 plugin-probe 无输出 —— 站上未部署 "
                            f"ops/station-bin/plugin-probe (部署后重跑); 本子项对该站跳过")
                continue
            for iid, it in sorted(pitems.items()):
                if st not in _plugin_scope(it):
                    continue
                plugin_checked += 1
                got = facts.get(iid)
                if got is None:
                    detail.append(f"{st} 站 plugin-probe 未汇报 {iid} —— 站上脚本比基线旧, "
                                  f"需重新部署 ops/station-bin/plugin-probe")
                    continue
                diff = _plugin_diff(it, got)
                if diff is None:
                    continue
                reg = drift.get((st, iid))
                if diff[0] == "extra" and reg is not None and sorted(diff[1]) == reg:
                    warn.append(f"{st} 站 {iid} 多出已登记项 {diff[1]} "
                                f"(inventory/plugins.yaml 的 known_drift, 不阻断)")
                else:
                    detail.append(f"{st} 站 {iid} ({it.get('purpose', '?')}) "
                                  f"实得 {got!r} · 基线 {it.get('expect')!r} · 差异 {diff[1]}")

    # (h) LAN 地址对账 (ADR-0006 v1.1 · D6, 2026-09-29) —— 两个面：
    #     ① master 侧**名字绑定**（`ssh -G <别名>` == net.yaml 的 ip；D1 的资产，纯本地展开）；
    #     ② ★ **站上实况**（站上 `ip -4 -o addr` 的 LAN 地址 == net.yaml 的 ip；D6 新增）。
    #   为什么加②: ①的射程靠"别名"，`host: null` 的 C 站**整站被跳过** —— 2026-09-29 C 由
    #     .37 漂到 .8 时，6 项断言只报"可达 2/3 站"、**不给根因**（正是 D4 要消灭的谜题）。
    #   代价: ②搭在同一次合并 ssh 上（零新增连接）；**只有某站直连采集失败**时才多一次
    #     `邻站 → USB4` 的中转 ssh —— 而那种情况本来就已经在报红灯。
    try:
        net_doc = _net_doc() or {}
        lan_doc, segs = net_doc.get("lan") or {}, net_doc.get("segments") or []
    except Exception as e:
        lan_doc, segs = {}, []
        warn.append(f"net.yaml 解析失败, LAN 地址对账跳过 —— {type(e).__name__}: {str(e)[:120]}")
    seg_nets = []
    for sg in segs:
        try:
            seg_nets.append(ipaddress.ip_network(str(sg.get("cidr")), strict=False))
        except Exception:
            warn.append(f"net.yaml §segments 的 cidr 不可解析, 已忽略: {sg.get('cidr')!r}")
    seen_lan = {}
    for ent in (lan_doc.get("stations") or []):
        if not isinstance(ent, dict) or not ent.get("station"):
            continue
        st = ent["station"]
        rows, src = _parse_lanip((live.get(st) or {}).get("lanip")), "直连"
        if not rows:                                    # 直连采集不到 ⇒ 走 USB4 降级通道
            rows, err = _lanip_via_usb4(st, segs, live, cluster.ssh_run)
            src = "USB4 降级通道"
            if err:
                seen_lan[st] = {"error": err}
                continue
            info.append(f"{st} 站直连采集不到（LAN 不通?）, 已**经 USB4 降级通道**取回其真实地址")
        got, perr = pick_lan_addr(rows, ent.get("iface"), seg_nets)
        seen_lan[st] = got if got else {"error": f"{src}: {perr}"}
    # 主控自身：探针 = 真值里**第一个站的 ip**（UDP-connect 只做路由选择, 不发包）
    probe = next((e.get("ip") for e in (lan_doc.get("stations") or [])
                  if isinstance(e, dict) and e.get("ip")), None)
    seen_master = {"ip": _local_lan_ip(probe)} if probe else \
        {"error": "net.yaml §lan.stations 里没有可用的 ip ⇒ 无法判断本机走哪条路"}
    if probe and not seen_master.get("ip"):
        seen_master = {"error": f"无法确定本机通往 {probe} 的源地址（socket 失败）"}
    d_lan, w_lan, i_lan = validate_lan_addr(lan_doc, seen_lan, seen_master)
    detail += d_lan
    warn += w_lan
    info += i_lan

    # (h) 长龄 orphan (O-58, 2026-09-25) —— 站上 ad-hoc 探针/派发留下的僵尸 / 长龄进程。
    #   判据: comm ∈ {opencode, claude, timeout, defunct} 且 etimes ≥ 阈值。
    #   ⚠ **刻意只 WARN、不 FAIL**: 该阈值**判不出"合法的长 run"**(我们自己的长卡可以跑 >6h)
    #     ⇒ 需要人判。本条的价值是**把信号从"偶然人肉 ps"变成"每次全量门禁都报"**，
    #     不是自动清理(清孤儿是不可逆动作, 见 O-58 的裁定记录)。
    #   ⚠ 阈值可由 `RPC_ORPHAN_SEC` 覆盖 —— **为了能先验红**: 6h 的长龄进程无法现场造出来,
    #     而新判据必须双向自证(否则无从区分"判据对"与"判据恒假")。默认仍是 6h。
    # ★ O-70 (2026-09-25) **射程写准**: 本条**只守本站 runtime 白名单那几类**, 不是"站上有无异常进程"。
    #   依据(实测): O-72 那条真孤儿是 `bash` + `sleep`(存活 28.6h), **完全不在白名单** ⇒ 漏报。
    #   ⇒ ① 报数/告警文案里**列出白名单**; ② 另设 (i) `[orph2]` = 白名单外的 ppid=1 长龄进程,
    #     **只报数不判定**(见下), 补上"可见化"这一半。
    ORPHAN_WHITELIST = "opencode|claude|timeout|defunct"
    ORPHAN_SEC = int(os.environ.get("RPC_ORPHAN_SEC") or 6 * 3600)
    orphan_checked = 0
    for st in reach:
        stale = []
        for line in (live[st].get("orph") or "").splitlines():
            f = line.split()
            if len(f) < 4:
                continue
            pid, ppid, et, comm = f[0], f[1], f[2], " ".join(f[3:])
            if not et.isdigit():
                continue
            orphan_checked += 1
            et = int(et)
            if et >= ORPHAN_SEC:
                stale.append(f"{comm} (pid {pid}, ppid {ppid}, 已 {et // 3600}h{(et % 3600) // 60}m)")
        if stale:
            warn.append(f"{st} 站发现**长龄 orphan** (⚠ 射程 = 本白名单 `{ORPHAN_WHITELIST}` · ≥{ORPHAN_SEC // 3600}h；"
                        f"见台账 O-58/O-70): {'; '.join(stale)} —— ⚠ 正在跑的**合法**长 run 也会命中，先确认再清")
        else:
            info.append(f"{st} 站无长龄 orphan (白名单 `{ORPHAN_WHITELIST}` · ≥{ORPHAN_SEC // 3600}h)")
    # (i) O-70 第二类: **我们自己的**产物名命中的进程(不限于白名单 comm) —— **只报数, 永不进 warn/FAIL**。
    #   为什么分开: 白名单内那四类是我们的 runtime, 长龄基本=卡死; 而这一类的匹配键是"**我们的脚本名**",
    #     覆盖 `bash`/`sleep`/`find` 这些白名单看不到的形态(O-72 的真孤儿正是 `bash`+`sleep`) ——
    #     按已裁定的口径**只做可见化**(判成 WARN 会淹信号; 判成 FAIL 更糟, 清孤儿**不可逆**)。
    #   第三列是 `args`(完整命令行) ⇒ 直接打印出来, 人一眼能看出是哪条链漏的。
    orph2_checked = 0
    orph2_stale = []
    for st in reach:
        for line in (live[st].get("orph2") or "").splitlines():
            f = line.split()
            if len(f) < 3:
                continue
            pid, et, what = f[0], f[1], " ".join(f[2:])
            if not et.isdigit():
                continue
            orph2_checked += 1
            if int(et) >= ORPHAN_SEC:
                orph2_stale.append(f"{st}:{what[:70]} (pid {pid}, {int(et) // 3600}h)")
    if orph2_stale:
        info.append(f"白名单外但**属于我们**的长龄残留 {len(orph2_stale)} 条 (**只报数不判定**; 见台账 O-70): "
                    f"{'; '.join(orph2_stale[:5])}")

    if unreachable:
        info.insert(0, f"站点不可达 (未计入判定): {', '.join(unreachable)}")
    note = (f"可达 {len(reach)}/3 站 · 对账 cfg{len(WATCHED)}/ROUTE{len(cluster.ROUTE)}"
            f"/RPC{len(cluster.RPC_MODELS)}/conf{sum(len(v) for v in declared_conf.values())}"
            f"/bind{sum(1 for m in (ports_inv or {}).values() if m.get('expect_bind'))}"
            f"/port{checked_ports}(豁免临时段 {ignored_eph})/plugin{plugin_checked}"
            f"/weight{sum(1 for st in reach for _ in (live[st].get('mpath') or '').splitlines())}"
            f"/orph{orphan_checked}"
            f"/orphx{orph2_checked}"
            # ★ O-70 (2026-09-26): 把**第二类的 stale 条数**也放进 note —— 此前 note 只有 `orphx`
            #   （= 探针**见到几行**，与年龄无关），而"有几条超阈值"只在 >0 时才出现在 info 里
            #   ⇒ 采样时无法**直接读**这个数（只能靠"info 里有没有那行"，脆弱）。
            #   ⚠ 加这个数**不改灯的语义**（第二类仍只报告、不进 WARN/FAIL）；它只是让 O-70 的
            #     "先看几轮噪声水平再裁"这一步**有数据可读**。
            f"/orphxstale{len(orph2_stale)}")
    if detail:
        return "FAIL", note, info + detail + [f"(WARN) {w}" for w in warn]
    if warn:
        return "WARN", note, info + warn
    return "PASS", note, []


# ── 断言 A8..A11: 健康引擎 (P2-2) ─────────────────────────────────
# 目的: 把 rpc_check.py 从"提交门禁"扩成"集群健康引擎"—— 学 Ollama Herd 的
# "成体系的自检项 + 红黄绿 + 修复建议"形态 (方案 §A.2.2), 补齐方案 §5.3 P2-2 列的
# 维度里**尚未覆盖**的四块:
#   usb4   链路层: 三段地址/MTU/接口状态/六向直连/主备回程路由   (此前完全没覆盖)
#   gates  内存门禁: load-gate 可用性 + 当前余量 + loadavg       (此前完全没覆盖)
#   engine 引擎态: 就绪 + **残留检测**(内存被占着但没有服务)      (此前只看 conf/ROUTE)
#   models 模型库完整性: 孤儿/断链                                (此前只在 CLI, 未进门禁)
# (端口/凭据/配置一致性/插件同构已由 ports + stations 的 (a)(d)(f)(g)(h) 覆盖)
#
# ssh 往返控制: usb4/gates/engine 三项共用**一次**合并采集(每站), 并按站缓存 ——
# 否则 3 项 × 3 站 = 9 次往返, 门禁会慢到没人愿意跑。缓存只活在本进程内,
# 故 `--only` 单跑某项时同样只需 1 次/站。
INVENTORY_NET = INVENTORY_DIR / "net.yaml"
# 三段全部端点地址: 采集侧盲发 ping, 由门禁侧判定"哪些必须通"
NET_ENDS = ("10.10.10.1", "10.10.10.2", "10.10.11.1",
            "10.10.11.3", "10.10.12.1", "10.10.12.3")
ENGINE_PORTS = ("8080", "8081", "18080", "18081", "50052")


# ★ O-146（2026-10-05）：**8080 的占用者是哪条路径的引擎** —— 取数分类（**只报数、不进判定**）。
# 为什么需要（根因，读码取证）：`backend` 判**装机面**（两条路径的二进制在不在 + 后端类型），
#   `engine` 判**运行面**却只问"在不在服务 / 是不是残留" ⇒ **"运行中的引擎来自哪条路径"
#   落在两个门禁的缝里，两边都不判**（实测：A 站跑 `/opt/llama.cpp/llama-server` 占着 8080，
#   而 `backend` 照样 PASS ⇒ "未迁移"在门禁层不可见）。更深一层：`BACKEND` 只被 `infer-load`
#   消费，systemd 单元走 `llama-serve-instance`、只读 `LLAMA_SERVER_BIN`（缺省 `/opt/...`）。
# ★★ **O-146 乙′（2026-10-05 裁定）：占用者【进判定】** —— 作用域 = `ports.yaml` 里 `purpose` 含
#   "推理引擎" 的端口（**由真值表驱动、不硬编码**；现 = 8080）；`other`（认不出的东西占着）·
#   `unknown`（取不到 ⇒ 判不了）⇒ **WARN**；`{studio,opt-vulkan,opt-variant}` / `none` ⇒ 通过。
#   ★ 为什么**不**做"按站期望"（甲案）：A 站形态随**外部消费者**时变（实测 `gpt-oss-120b`↔
#   `MiniMax-M2.7`、`llama-single`↔`unsloth` 都出现过）⇒ 写死期望必生误报（SRE 共识：**静态阈值
#   是误报头号成因**；`O-143` 的 A 站 RSS 假阳性即先例）。外部依据：NIST SP 800-167 白名单 =
#   **有限已知集**（不声明"谁该在"）；path 类识别「单独用弱」⇒ 故本判据**只判"认不出/取不到"**，
#   **不判"身份是否正确"**。三者对照见 `O-146` 的多维表。
# ⚠ fail-closed：取不到 ⇒ `unknown`（**绝不**把"读不出"当 `none`）；`listening=True` 却说
#   `none`（LISTEN 段与占用者取数矛盾）⇒ 也记 `unknown`。
_OCCUPANT_KINDS = (("opt-vulkan", "/opt/llama.cpp/"),  # /opt/llama.cpp/（Vulkan 分布式路径 · ★ 当前基线）
                   ("opt-variant", "llama.cpp-"),      # /opt/llama.cpp-<变体>/（GLM 等特性分支）
                   ("studio", "unsloth"))              # studio 启动器（cmdline 含 `unsloth studio run`）
# ⚠⚠ **顺序承重（2026-10-05 活体检查抓到）**：`/opt/llama.cpp` 是 **symlink → `/opt/llama.cpp-master-<hash>`**
#   ⇒ 若按 `readlink -f` 的 **exe** 分类，**当前基线**会撞上 `llama.cpp-` 而被误标 `opt-variant`。
#   故：① **opt-vulkan 必须排在 opt-variant 之前**；② 分类用的 blob **含 cmdline**（cmdline 保留
#   **未解析**的 `/opt/llama.cpp/llama-server`）⇒ 当前基线稳定落 `opt-vulkan`，真变体（cmdline 里是
#   `/opt/llama.cpp-<名>/…`，**不含** `/opt/llama.cpp/`）才落 `opt-variant`。同理 studio 的监听进程
#   exe 是 **python 启动器**，其身份只在 cmdline ⇒ 必须看 cmdline。


def classify_engine_occupant(path, listening=False, cmdline=""):
    """把"占用 8080 的进程"归成一类（**唯一定义点**，纯函数 ⇒ 可离线单测）。

    ⚠⚠ **必须同时看 `cmdline`**（2026-10-05 活体检查抓到）：studio 的监听进程是**python 启动器**
    （实测 exe = `…/anaconda3/bin/python3.13`），**只看 exe 会把 studio 误报成 `other`** ⇒
    分类基于 `exe + cmdline` 的合并串（cmdline 里才有 `unsloth studio run --model …`）。
    """
    p = str(path or "").strip()
    c = str(cmdline or "").strip()
    if p in ("", "unknown") and not c:
        return "unknown"                 # 取不到 ⇒ 不可判（fail-closed，**绝不**当 none）
    if p == "none" and not c:
        # LISTEN 段说在听、占用者却说 none ⇒ 取数自相矛盾 ⇒ **不可判**（不是"没占用"）
        return "unknown" if listening else "none"
    blob = p + " " + c
    for kind, marker in _OCCUPANT_KINDS:
        if marker in blob:
            return kind
    return "other"


# ★★ O-146 乙′（2026-10-05）：**允许出现的占用者形态**（有限已知集，NIST SP 800-167 白名单同构）。
#   ⚠ 刻意**不**含"哪一站该跑哪个" —— 那正是被否的甲案（期望随外部消费者时变）。
_OCCUPANT_OK = ("studio", "opt-vulkan", "opt-variant")


def _engine_api_ports():
    """从 `inventory/ports.yaml` 取"**推理引擎 API**"端口（★ 真值表驱动，不硬编码）。

    判据 = 该端口条目的 `purpose` 含「推理引擎」（现 = 8080：`本地推理引擎 API (unsloth studio 对外面)`）。
    读不到/解析失败 ⇒ 退回 `("8080",)`（**fail-safe 到已知端口**，不是"跳过判定"）。
    """
    try:
        doc = yaml.safe_load(INVENTORY_PORTS.read_text(encoding="utf-8")) or {}
    except Exception:
        return ("8080",)
    out = []

    def _walk(o):
        if isinstance(o, dict):
            if "port" in o and "推理引擎" in str(o.get("purpose", "")):
                out.append(str(o["port"]))
            for _v in o.values():
                _walk(_v)
        elif isinstance(o, list):
            for _v in o:
                _walk(_v)

    _walk(doc)
    return tuple(out) or ("8080",)


# 残留阈值: 进程 RSS 超过它却没有引擎在服务 → 视为残留(占着内存不干活)。
# 取 2G: 正常单机 llama-server 的 RSS 是几十 G 量级, 而 ggml-rpc-server 空转也有 ~0.3G,
# 故 2G 能把"真占住了"和"进程刚起/空跑"分开 (本会话真的踩到过 62.6G 残留污染判定)。
RESIDUAL_RSS_MB = 2048
# O-41② (2026-09-24): **预警带下沿** —— `[1024, RESIDUAL_RSS_MB)` 且无引擎端口 ⇒ 报 WARN（不 FAIL）。
#   为什么需要: 旧实现只有"≥2G = 残留 FAIL"与"否则 = 正常"，**1024~2048M 这一段完全无声**
#   （O-41② 实测: 1.5G 无端口残留被判"正常"）。下沿取 1024 是为了**不误报 ggml-rpc-server 空转(~0.3G)**
#   与"进程刚起"这两种刻意容忍的情形 ⇒ 只覆盖"明显占住了但没在服务"的带。
RESIDUAL_WARN_MB = 1024


def classify_engine_band(has_ports, rss_mb, n_proc=None):
    """`engine` 断言的**唯一定义点**（O-143 乙，2026-10-03）—— 两分支共用同一份口径。

    返回 `(verdict, reason)`；`verdict ∈ {"FAIL","WARN",None}`（`None` = 无告警）；`reason` 是**不带站名**的短句。

    ★ 为什么必须集中: 修 O-143 之前，"进程刚起"这一情形在**无端口**分支被**刻意容忍**
    （见 `RESIDUAL_WARN_MB` 的注释），在**有端口**分支却按**裸 RSS** 判异常
    ⇒ **同一断言的两半对同一情形给出相反判定**。

    ★★ 判据依据的**更正**（2026-10-03 实测，E1）: **RSS 不是"引擎在不在服务"的证据** ——
    A 站在 **13h**、RSS **208M** 下实测推理 **56.6 t/s**、**GTT 68.75 GiB** 驻留
    （Vulkan/UMA 引擎的权重驻留**设备侧**）⇒ **"有端口 + RSS 小"不足以判异常**。
    故**有端口**分支改用**进程数**作判据:
      · `n_proc >= 1` ⇒ **在服务**（RSS / 进程龄 只作**报数**）
      · `n_proc == 0` ⇒ **端口在听但不是我们的引擎** ⇒ 疑似端口被占（WARN）
      · `n_proc` 读不出     ⇒ **退回旧的 RSS 口径**（「判不了 ≠ 通过」，不静默放过）

    ⚠ **射程（诚实登记，见台账 `O-143`）**: `n_proc >= 1` 只证明**站上有 llama 系进程**，
    **不证明 8080 的持有者就是它**（证到那一层须按端口取 pid —— 需 root，本门禁不具）。
    """
    if has_ports:
        if isinstance(n_proc, int):
            if n_proc <= 0:
                return "WARN", "端口在听但站上**无** llama 系进程 ⇒ 疑似端口被占"
            return None, None
        # 进程数读不出 ⇒ 退回旧口径（保守: 仍可能报，但不静默通过）
        if rss_mb < 1024:
            return "WARN", f"有引擎端口在听但 RSS 仅 {rss_mb}M（进程数读不出）⇒ 疑似异常进程/端口被占"
        return None, None
    if rss_mb >= RESIDUAL_RSS_MB:
        return "FAIL", (f"无任何引擎端口在听, 但 llama/rpc 进程仍占 {rss_mb // 1024}G RSS"
                        f" —— 内存被占着没干活, 会污染加载预估 (先 infer-unload / 清残留再加载)")
    if rss_mb >= RESIDUAL_WARN_MB:
        return "WARN", (f"有 llama 系进程占 {rss_mb}M 但无引擎端口在听 —— 疑似残留/启动中 "
                        f"(预警带 ≥{RESIDUAL_WARN_MB}M, FAIL 阈值 {RESIDUAL_RSS_MB}M)")
    return None, None

# ── 站上件"部署一致性"跟踪清单 (2026-09-22 裁定接入 gates) ──────────────────────
# 背景: 这些件是**站上件** —— 部署在 `/usr/local/bin/`, 仓库副本只是"快照"。
#   ⇒ **改仓库副本不生效**, 必须重新部署; 而"站上跑的那份是不是仓库这份"此前**没有任何机器判据**
#     (只靠 `ops/station-bin/README.md` 的**手工 md5 约定**) ⇒ 本清单把那条约定变成可判。
# ⚠ **期望值不在此处写死**: 真值源 = 仓库副本 `ops/station-bin/<name>` 自身(运行期算 md5)
#   ⇒ 不立第二定义点, 也免掉"改了仓库忘改表"这种漂移(与本仓"判据只在一处定义"同一条纪律)。
# 为什么只列这些: 它们是 `ops/station-bin/README.md` 文件清单里声明的站上件。
# ⚠ 为什么敢判 FAIL(而非 WARN): 接入前实测过**误报面** —— 8 个件 × 三站里 7 个本来就逐字节一致,
#   唯一不一致的 `wait-gtt-release` 是**真漂移**(A/B 落后一版且带 BOM), 已单独立项。
# 2026-09-29 补第 9 件 `rpc-serve-instance`(RPC worker 包装器, GLM-5.3-Flash 引擎变体需要)。
# ⚠⚠ 同日本项**顺带抓到一类系统性假红**: `core.autocrlf=true` 使仓库工作树里
#   `infer-load` / `infer-unload` 是 CRLF, 而站上是 LF ⇒ 逐字节比对必然 FAIL(内容其实一致)。
#   判据是对的(CRLF 的 shell 脚本在 Linux 上**真的**语法错误, 2026-09-29 部署时实测 203/EXEC 同类),
#   错的是**仓库工作树**: 已把这 2 件归一为 LF。改这几个件时务必确认行尾是 LF。
STATION_BINS = ("infer-load", "infer-unload", "infer-list", "llama-serve-instance",
                "rpc-serve-instance", "cluster-ttl", "load-mem-gate", "wait-gtt-release", "load-gate")

_HEALTH_CMD = (
    "echo '===ADDR==='; ip -o -4 addr show 2>/dev/null "
    "| awk '$4 ~ /^10\\.10\\./ {print $2, $4}'; "
    "echo '===LINK==='; for i in $(ls /sys/class/net 2>/dev/null | grep '^thunderbolt'); do "
    "echo \"$i $(cat /sys/class/net/$i/mtu 2>/dev/null) $(cat /sys/class/net/$i/operstate 2>/dev/null)\"; done; "
    "echo '===ROUTE==='; ip route show 2>/dev/null | while read -r dst rest; do "
    "case \"$dst\" in 10.10.*) via=$(echo \"$rest\" | sed -n 's/.*via \\([0-9.]*\\).*/\\1/p'); "
    "met=$(echo \"$rest\" | sed -n 's/.*metric \\([0-9]*\\).*/\\1/p'); "
    "echo \"$dst ${via:-direct} ${met:-0}\";; esac; done; "
    "echo '===PING==='; for t in " + " ".join(NET_ENDS) + "; do "
    "printf '%s ' \"$t\"; ping -c1 -W1 -q \"$t\" >/dev/null 2>&1 && echo OK || echo FAIL; done; "
    # ⚠ 列序: `ps -eo rss,etimes,comm` ⇒ $1=rss(KB) · $2=etimes(秒) · $3+=comm
    #   `etimes_min_s` = **最年轻**那个 llama 系进程的年龄 —— O-143 的"刚起"读数。
    #   ★ 本项**只报数**（判据阈值待读数足够后再定，见 O-126「不许凭空取数」）。
    "echo '===PROC==='; ps -eo rss,etimes,comm 2>/dev/null "
    "| grep -E 'llama-server|ggml-rpc-server|llama-cli' | grep -v grep "
    "| awk '{s+=$1; n++; if (n==1 || $2+0<m) m=$2+0} "
    "END {printf \"rss_mb=%d\\n\", s/1024; printf \"etimes_min_s=%d\\n\", m; "
    "printf \"n_proc=%d\\n\", n}'; "
    "echo '===LISTEN==='; ss -ltn 2>/dev/null | awk 'NR>1{print $4}' | sed 's/.*://' "
    "| grep -E '^(" + "|".join(ENGINE_PORTS) + ")$' | sort -u | tr '\\n' ','; echo; "
    # ★ O-146（2026-10-05）：**占用者是谁** —— 见 `classify_engine_occupant` 的注释（只报数）。
    "echo '===OCCUPANT==='; for P in " + " ".join(ENGINE_PORTS) + "; do "
    "L=$(ss -ltnp 2>/dev/null | awk -v s=\":$P\" '$4 ~ s\"$\"{print $NF}' | head -1); "
    "if [ -z \"$L\" ]; then printf 'occupant_%s=none\\n' \"$P\"; continue; fi; "
    "PID=$(printf '%s' \"$L\" | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2); "
    "E=$(readlink -f \"/proc/${PID:-0}/exe\" 2>/dev/null); "
    "C=$(tr '\\0' ' ' < \"/proc/${PID:-0}/cmdline\" 2>/dev/null | cut -c1-200); "
    "printf 'occupant_%s=%s\\n' \"$P\" \"${E:-unknown}\"; "
    "printf 'occupantcmd_%s=%s\\n' \"$P\" \"$C\"; done; "
    "echo '===MEM==='; awk '/MemTotal/{printf \"total_mb=%d \", $2/1024} "
    "/MemAvailable/{printf \"avail_mb=%d\", $2/1024}' /proc/meminfo; "
    "printf ' load1=%s' \"$(cut -d' ' -f1 /proc/loadavg)\"; "
    "printf ' loadgate=%s\\n' \"$(command -v load-gate >/dev/null 2>&1 && echo yes || echo no)\"; "
    "echo '===BINMD5==='; for f in " + " ".join(STATION_BINS) + "; do "
    "printf '%s=%s\\n' \"$f\" \"$(md5sum /usr/local/bin/$f 2>/dev/null | cut -d' ' -f1)\"; done"
)

_HEALTH_CACHE = {}


def _health_probe(st: str) -> dict:
    """单站合并采集 (链路/路由/连通/引擎/内存)。返回 {reachable, addr, link, route, ping, ...}。

    解析失败**显式标 reachable=False**, 绝不返回半份数据让下游误判
    (与 P1-4 的"解析失败不能表现成业务全错"同一原则)。
    """
    if st in _HEALTH_CACHE:
        return _HEALTH_CACHE[st]
    d = {"station": st, "reachable": False, "addr": {}, "link": {}, "route": {},
         "ping": {}, "rss_mb": None, "listen": [], "occupant": {}, "occupant_cmd": {}, "mem": {}, "binmd5": {}, "raw": ""}
    sys.path.insert(0, str(ROOT / "ops"))
    try:
        import cluster
    except Exception as e:
        d["error"] = f"无法导入 cluster.py ({type(e).__name__}) — 该组需 paramiko"
        _HEALTH_CACHE[st] = d
        return d
    ok, out = cluster.ssh_run(st, _HEALTH_CMD, timeout=120)
    d["raw"] = out or ""
    if not ok:
        d["error"] = out
        _HEALTH_CACHE[st] = d
        return d
    d["reachable"] = True
    sec = _parse_health_sections(out)
    for line in sec.get("ADDR", []):
        p = line.split()
        if len(p) >= 2 and "/" in p[1]:
            d["addr"][p[0]] = p[1].split("/")[0]
    for line in sec.get("LINK", []):
        p = line.split()
        if len(p) >= 3:
            d["link"][p[0]] = {"mtu": p[1], "state": p[2]}
    for line in sec.get("ROUTE", []):
        p = line.split()
        if len(p) >= 3:
            # ⚠ 同一目的地的**主备两条**路由必须并存 —— 早版按 dst 存单个 dict,
            # 后一条把前一条覆盖掉了, 于是"主备齐备"这件事根本查不出来
            # (2026-09-15 实测: A 站 10.10.11.0/24 的两条被压成一条, 误报主路由缺失)。
            d["route"].setdefault(p[0], []).append({"via": p[1], "metric": p[2]})
    for line in sec.get("PING", []):
        p = line.split()
        if len(p) >= 2:
            d["ping"][p[0]] = p[1]
    for line in sec.get("PROC", []):
        # rss_mb (合计) + etimes_min_s / n_proc (O-143 的"刚起"读数, 只报数不判 —— 见 _HEALTH_CMD 注)
        for _k in ("rss_mb", "etimes_min_s", "n_proc"):
            if line.startswith(_k + "="):
                try:
                    d[_k] = int(line.split("=", 1)[1])
                except ValueError:
                    pass
                break
    d["listen"] = [x for x in ",".join(sec.get("LISTEN", [])).split(",") if x]
    # ★ O-146：8080 占用者（**只报数**）—— `occupant_<port>=<exe 路径|none|unknown>`
    #   + `occupantcmd_<port>=<cmdline>`（⚠ 必须看 cmdline：studio 的监听进程是 python 启动器）
    for line in sec.get("OCCUPANT", []):
        if "=" in line:
            k, _, v = line.strip().partition("=")
            if k.startswith("occupantcmd_"):
                d["occupant_cmd"][k[len("occupantcmd_"):]] = v.strip()
            elif k.startswith("occupant_"):
                d["occupant"][k[len("occupant_"):]] = v.strip()
    mem_line = " ".join(sec.get("MEM", []))
    for tok in mem_line.split():
        if "=" in tok:
            k, _, v = tok.partition("=")
            d["mem"][k] = v
    # 站上件副本 md5 (name=hash) —— 与本次探测**同一条命令**取回, 零额外连接。
    # 值为空串 = 文件读不到(md5sum 失败) ⇒ 与"缺失"同义, 由判据那边报出来。
    for line in sec.get("BINMD5", []):
        if "=" in line:
            k, _, v = line.strip().partition("=")
            d["binmd5"][k] = v.strip()
    _HEALTH_CACHE[st] = d
    return d


def _parse_health_sections(out):
    sec, cur = {}, None
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("===") and s.endswith("==="):
            cur = s.strip("=")
            sec[cur] = []
        elif cur:
            sec[cur].append(line)
    return {k: [x for x in v if x.strip()] for k, v in sec.items()}


def _net_doc():
    """读 inventory/net.yaml。缺失返回 {}; **解析失败抛异常**。"""
    if not INVENTORY_NET.is_file():
        return {}
    import yaml
    return yaml.safe_load(INVENTORY_NET.read_text(encoding="utf-8")) or {}


# ── 断言: agent 证据链 (2026-09-17, spec/d6-agent-standard/evidence-chain/) ──
# 为什么门禁要管: 证据链的价值在**被日常撞见** —— 只靠"人工想起跑 agent verify",
#   归档被改动可以长期无人察觉(与本仓"判据必须自证不静默降级"同一纪律)。
# 严重度**刻意分开**(要紧):
#   · verify 报 issues (digest_mismatch / chain_break / cold_mismatch / anchor_mismatch /
#     run_dir_missing / recipe_mismatch) = **证据被改或链被重写** ⇒ FAIL。
#   · "有 run 未入链" = **覆盖缺口, 不是篡改** ⇒ WARN。否则每次派发后提交都被阻断,
#     这类判据会因噪声被整体忽略(doclinks "判不准的不进门禁" 同一条理由)。
def check_evidence(ctx):
    sys.path.insert(0, str(ROOT / "ops"))
    try:
        import cluster
    except Exception as e:
        return "WARN", f"cluster.py 无法导入 ({type(e).__name__}) — 证据链断言跳过", []
    try:
        r = cluster.agent_chain_verify()
    except Exception as e:
        return "FAIL", f"证据链复验异常: {type(e).__name__}: {e}", []
    if r.get("note"):
        return "WARN", f"证据链不可用: {r['note']}", []
    issues = r.get("issues") or []
    un = r.get("unchained") or []
    gaps = r.get("gaps") or []
    notes = r.get("notes") or []
    details = []
    for x in issues:
        k, loc = x.get("kind"), f"{x.get('proj')}/{x.get('run_id')}"
        if k == "digest_mismatch":
            details.append(f"[{x['index']}] {loc} digest 不符, 变了: "
                           f"{', '.join(x.get('files_changed') or []) or '(未知)'}")
        elif k == "chain_break":
            details.append(f"[{x['index']}] {loc} prev 链不闭合 (此条起不可信)")
        elif k == "run_dir_missing":
            details.append(f"[{x['index']}] {loc} 归档目录不在了")
        elif k == "recipe_unknown":
            details.append(f"[{x['index']}] {loc} recipe **不可验** (链={x.get('got')} 本工具知 "
                           f"{x.get('expect')}) —— 工具比链旧, 不得当作通过")
        elif k in ("verdict_mismatch", "golden_identity", "manifest_missing", "manifest_undeclared"):
            details.append(f"[{x.get('index')}] {x.get('detail')}")
        elif k == "anchor_mismatch":
            details.append(f"外部锚与链不符: {', '.join(x.get('diff') or []) or '(未列出)'}")
        elif k == "anchor_unreadable":
            details.append("外部锚不可读 archive/evidence-chain/ANCHOR.txt")
        elif k == "cold_mismatch":
            details.append(f"冷路径与链不符 (冷={x.get('cold_n')} 链={x.get('chain_n')})")
        else:
            details.append(str(x))
    cov = " · ".join(c.split(":")[0] + " " + c.split(":")[1].split("可判")[0].strip()
                     for c in (r.get("coverage") or []) if ":" in c)
    note = (f"证据链: {r.get('entries', 0)} 条 · 未入链 {len(un)} · "
            f"锚{'在' if r.get('anchor_present') else '缺'}" + (f" · {cov}" if cov else ""))
    # ── 增量审计（ADR-0007 路A，2026-09-18）: 只报**新增**可重放性缺口 ─────────────
    # 与上面 verify 的分工（**严格按 D4 三层，不许混**）:
    #   · verify 的 issues = 篡改/损坏 ⇒ **FAIL**
    #   · verify 的 gaps / 未入链 / 缺锚 = **覆盖缺口** ⇒ **WARN**
    #   · 本段 = **可重放性**缺口，同属"**没验到**"⇒ **只 WARN，不进 FAIL 集**
    #     （D4 原文: 属"没验到"不是"验出问题"; 报 FAIL 会让判据**因噪声被整体忽略**）
    # 增量水印（K1/K2）: 用**归一 key** 与基线比对 ⇒ 存量 52 条不刷屏、新增必被抓。
    #   基线由**显式命令** `cluster.py agent audit --accept` 推进 —— **门禁只读、不自己写**
    #   （本文件对仓库全程只读，唯一写动作是 check_syntax 的 tempfile; 门禁挂 pre-commit,
    #    自己写就会把工作区弄脏）。副作用刻意接受: "接受新缺口"是人的显式动作, 不静默抹平。
    try:
        ra = cluster.agent_audit(limit=0)
    except Exception as e:
        # ⚠ 这里**刻意 FAIL 而非 WARN**: `import cluster` 失败是**环境**问题(缺 paramiko),
        #   而 `agent_audit` 抛异常是**本仓自己的 bug** —— 2026-09-18 的 Py3.11 语法事故正是
        #   被上面的 `except Exception` 静默降级成 WARN ⇒ **判据消失而门禁照绿**。两者必须分开。
        return "FAIL", f"可重放性审计异常: {type(e).__name__}: {e}", details
    _base = cluster.agent_audit_baseline_load()
    _bkeys = set(_base.get("keys") or [])
    _cur = set(ra.get("gap_keys") or [])
    _pending = sorted(_cur - _bkeys)
    _gtext = {it["key"]: it["text"] for it in (ra.get("gap_items") or [])}
    note += (f" · 可重放 gap {len(_cur)} 条(存量 {len(_cur & _bkeys)}"
             + (f", **新增 {len(_pending)}**" if _pending else "") + ")")
    # 2026-09-23 (O-29 的 2c): **按框架代分桶** —— 判据演化后历史 gap 与新 gap 混在一起，
    #   "新增"会看起来永远清不完（本轮实测：改完判据仍报 3 条，我一度误判为"没修好"）。
    #   key 形状 `<fwver>|<kind>|<label>|<sub>`（**旧形状 3 段 ⇒ 记 legacy**）。
    #   真值源: `cluster.FRAMEWORK_SUBJECTS_VERSION`（与 `_gap_key` 同源，不另立常量）。
    def _fwv(_k: str) -> str:
        return _k.split("|", 1)[0] if _k.count("|") >= 3 else "legacy"
    _bk = {}
    for _k in _cur:
        _bk[_fwv(_k)] = _bk.get(_fwv(_k), 0) + 1
    if _bk:
        _curv = getattr(cluster, "FRAMEWORK_SUBJECTS_VERSION", None)
        _nc = _bk.get(_curv, 0)
        note += f" · 按框架代分桶: current({_curv})={_nc} · legacy={len(_cur) - _nc}"
    if _pending:
        details.append(
            f"**可重放性审计: 新增 {len(_pending)} 条** gap"
            f"（存量 {len(_cur & _bkeys)} 条已接受、不再重复报；逐条如下）"
            f" ⇒ 确认可接受后跑 `python ops/cluster.py agent audit --accept` 推进水印")
        for _k in _pending[:8]:
            details.append(f"    · {_gtext.get(_k, _k)}")
        if len(_pending) > 8:
            details.append(f"    · …另有 {len(_pending) - 8} 条（`cluster.py agent audit` 看全表）")

    # ── 校准可判（2026-09-18 闭环复核；D4 归类: 覆盖缺口 ⇒ **只 WARN，不阻断**）──────────
    # "改判据必须重跑校准"此前是**空头承诺** —— 校准报告不记判据文本/题集 ⇒ 改了没重跑无人能发现。
    # 本仓自己的纪律原文: "只写规则不绑定执行等于空头承诺, 故做成断言"。指纹机制之后它可判了:
    #   报告指纹 ≠ 当前"判据(A/B) + 稳定题集" ⇒ 报过期。
    # ⚠ 旧报告（生成于指纹机制之前，无 calib 字段）**不当作过期**, 只提示 —— 否则一上线就对历史假告警。
    try:
        _cs = cluster.agent_audit_calib_status()
        note += f" · 校准 {_cs.get('state', '?')}"
    except Exception as e:
        _cs = {"state": "no-report"}
        details.append(f"(info) 校准状态不可判: {type(e).__name__}: {e}")
    _calib_stale = (_cs.get("state") == "stale")
    if _calib_stale:
        details.append(
            f"**judge 校准已过期**（{_cs['file']} 指纹 {_cs['recorded'][:16]}… ≠ 当前 "
            f"{_cs['current'][:16]}…）—— 判据或稳定题集已改、报告没重跑 ⇒ 跑 "
            f"`python ops/cluster.py agent audit-judge --save`（需站上在服务**跨家族**引擎）")

    if issues:
        return "FAIL", note, details
    if gaps or _pending or _calib_stale or not r.get("anchor_present"):
        if not r.get("anchor_present"):
            details.append("外部锚未建立 → `cluster.py agent chain` 生成, 提交并 push 到 origin")
        for g in gaps[:6]:
            details.append(g)
        if len(gaps) > 6:
            details.append(f"…另有 {len(gaps) - 6} 项覆盖缺口/不可判 (见 `cluster.py agent verify`)")
        return "WARN", note, details
    for nt in notes[:3]:
        details.append(f"(info, 不告警) {nt}")
    return "PASS", note, details


def check_usb4(ctx):
    """USB4 三角环链路: 地址/MTU/接口状态 + 六向直连 + 主备回程路由 + 跨段生效性。"""
    if not INVENTORY_NET.is_file():
        return "WARN", "inventory/net.yaml 缺失 (链路真值未建)", []
    try:
        doc = _net_doc()
    except Exception as e:
        return "FAIL", f"net.yaml 解析失败: {type(e).__name__}: {str(e)[:180]}", []

    detail, warn, info = [], [], []
    live = {st: _health_probe(st) for st in ("A", "B", "C")}
    reach = [st for st in ("A", "B", "C") if live[st]["reachable"]]
    for st in ("A", "B", "C"):
        if not live[st]["reachable"]:
            detail.append(f"{st} 站不可达/采集失败: {live[st].get('error') or live[st].get('raw', '')[:120]}")

    n_addr = n_ping = n_route = 0
    for seg in doc.get("segments") or []:
        if not isinstance(seg, dict):
            continue
        name, want_mtu = seg.get("name", "?"), str(seg.get("mtu") or "")
        for end in seg.get("ends") or []:
            st = str((end or {}).get("station"))
            iface, ip = str((end or {}).get("iface") or ""), str((end or {}).get("ip") or "")
            if not st or not iface or not ip:
                detail.append(f"net.yaml 段 {name} 的端点字段不全: {end}")
                continue
            if st not in reach:
                continue
            n_addr += 1
            got = live[st]["addr"].get(iface)
            if got != ip:
                detail.append(f"{st} 站 {iface} 地址 = {got or '(无)'}, 真值 {ip} —— "
                              f"{name} 段地址不符(改过 netplan? 或接口错位)")
            lk = live[st]["link"].get(iface) or {}
            if not lk:
                detail.append(f"{st} 站 {iface} 不存在 —— {name} 段链路可能未枚举")
            else:
                if want_mtu and lk.get("mtu") != want_mtu:
                    detail.append(f"{st} 站 {iface} MTU = {lk.get('mtu')}, 真值 {want_mtu}")
                if lk.get("state") != "up":
                    detail.append(f"{st} 站 {iface} 状态 = {lk.get('state')} (应为 up)")

    # 六向直连: 每站 ping 它两个直连对端 (对端地址从线段两端推导)
    for seg in doc.get("segments") or []:
        if not isinstance(seg, dict):
            continue
        ends = [e for e in (seg.get("ends") or []) if isinstance(e, dict)]
        if len(ends) != 2:
            continue
        for i in (0, 1):
            me, peer = ends[i], ends[1 - i]
            st, tip = str(me.get("station")), str(peer.get("ip") or "")
            if st not in reach or not tip:
                continue
            n_ping += 1
            if live[st]["ping"].get(tip) != "OK":
                detail.append(f"{st} → {tip} ({seg.get('name')} 段直连对端) ping 不通 —— "
                              f"链路级问题, 先查 thunderbolt 枚举(见归档 §6.5)")

    # 主备回程路由: 主备**两条都要**(缺主路由实测降级 268×, 缺回程路由 100% 丢包)
    for r in doc.get("routes") or []:
        if not isinstance(r, dict):
            continue
        st, dst = str(r.get("station")), str(r.get("dst") or "")
        if st not in reach or not dst:
            continue
        got = live[st]["route"].get(dst) or []
        have = ", ".join(f"via {g['via']} m{g['metric']}" for g in got) or "无"
        for kind in ("primary", "backup"):
            spec = r.get(kind) or {}
            n_route += 1
            via, met = str(spec.get("via") or ""), str(spec.get("metric") or "")
            match = [g for g in got if g.get("via") == via]
            if not match:
                detail.append(f"{st} 站缺到 {dst} 的**{kind}**路由 (应 via {via} metric {met}); "
                              f"实有: {have} —— 见 inventory/net.yaml 的 routes 段 / 归档 §6.6")
            elif met and all(g.get("metric") != met for g in match):
                # metric 不符按 **FAIL** 判: 主备的 metric 决定优先级, 颠倒后跨段流量会走
                # 备路由(经第三方中转) —— 实测 9.46Gb/s → 35Mb/s (268×), 属功能回退而非风味问题。
                detail.append(f"{st} 站到 {dst} 的 {kind} 路由 (via {via}) metric="
                              f"{match[0].get('metric')}, 真值 {met} —— metric 决定主备优先级, "
                              f"不符会让跨段流量走错路径(实测降级 268×)")
    for st in reach:
        if st in {str(r.get("station")) for r in (doc.get("routes") or [])
                  if isinstance(r, dict)}:
            info.append(f"{st} 站到非直连段的路由: " +
                        "; ".join(f"{k} → " + ", ".join(f"via {g['via']} m{g['metric']}"
                                                        for g in v)
                                  for k, v in sorted(live[st]["route"].items())))

    # 跨段主路由生效性
    for cx in doc.get("cross_checks") or []:
        if not isinstance(cx, dict):
            continue
        st, tip = str(cx.get("from")), str(cx.get("to") or "")
        if st not in reach or not tip:
            continue
        n_ping += 1
        if live[st]["ping"].get(tip) != "OK":
            detail.append(f"{st} → {tip} 不通 ({cx.get('why')}) —— 跨段主路由未生效")

    note = (f"链路: 可达 {len(reach)}/3 站 · 地址 {n_addr} 端 · 连通 {n_ping} 向 · "
            f"路由 {n_route} 条(主备) · 段 {len(doc.get('segments') or [])}")
    if detail:
        return "FAIL", note, info + detail + [f"(WARN) {w}" for w in warn]
    if warn:
        return "WARN", note, info + warn
    return "PASS", note, info


def check_gates(ctx):
    """内存门禁: load-gate 可用性 + 当前余量 + loadavg。"""
    detail, warn, info = [], [], []
    live = {st: _health_probe(st) for st in ("A", "B", "C")}
    reach = [st for st in ("A", "B", "C") if live[st]["reachable"]]
    for st in ("A", "B", "C"):
        if not live[st]["reachable"]:
            detail.append(f"{st} 站不可达/采集失败: {live[st].get('error')}")

    bin_ok = bin_bad = 0
    for st in reach:
        mem = live[st]["mem"]
        try:
            total, avail = int(mem["total_mb"]), int(mem["avail_mb"])
        except (KeyError, ValueError):
            detail.append(f"{st} 站内存读数异常: {mem}")
            continue
        used = total - avail                      # 与站上 load-gate 同口径(used = total - avail)
        headroom = avail // 1024 - 12             # 12G 安全垫(load-gate 的 saf_mb)
        info.append(f"{st} 站 total {total // 1024}G / used {used // 1024}G / "
                    f"avail {avail // 1024}G → 单模型可加载上限约 {headroom}G")
        try:
            if float(mem.get("load1", 0)) > 8:
                warn.append(f"{st} 站 loadavg1={mem.get('load1')} > 8 —— 与 load-gate 同阈值, "
                            f"此时加载会明显变慢")
        except ValueError:
            pass
        if mem.get("loadgate") != "yes":
            detail.append(f"{st} 站 load-gate 不可用 (command -v 取不到) —— 站上加载门禁失效")
        if headroom <= 0:
            detail.append(f"{st} 站余量 {headroom}G ≤ 0 —— 当前**任何**模型都过不了门禁, "
                          f"需先卸载或清理残留")

        # ── 站上件部署一致性 (2026-09-22 裁定接入) ──────────────────────
        # 判据: `STATION_BINS` 里每个站上件, 三站副本必须**逐字节等于**仓库副本。
        # 为什么判 FAIL 而不是 WARN: 这是"**站上跑的不是我们 review 过的那份**" ——
        #   与本站 `stations` 断言(conf/凭据/端口不符即以站上实况改仓库侧)同一性质, 不是"判不准的噪声"。
        # 快照语义: 期望值取**仓库副本当前内容**(运行期算 md5) ⇒ "改了仓库还没部署"也会被判出来 ——
        #   这正是要的: 该件改仓库**不生效**, 必须走「改仓库 → 核对 → 部署」。
        got = live[st].get("binmd5") or {}
        for name in STATION_BINS:
            src = ROOT / "ops" / "station-bin" / name
            if not src.is_file():
                bin_bad += 1
                detail.append(f"STATION_BINS 里的 {name} 在仓库副本不存在 —— 清单该改(不是站上的问题)")
                continue
            exp = hashlib.md5(src.read_bytes()).hexdigest()
            have = got.get(name, "")
            if not have:
                bin_bad += 1
                detail.append(f"{st} 站 /usr/local/bin/{name} 取不到 md5 —— 站上缺件或读不到(权限)")
            elif have != exp:
                bin_bad += 1
                detail.append(f"{st} 站 /usr/local/bin/{name} 与仓库副本**不一致** "
                              f"(站上 {have[:8]}… / 仓库 {exp[:8]}…) —— 这是**站上件**, "
                              f"改仓库副本不生效: 核对后二选一(部署仓库版 / 回滚站上版)")
            else:
                bin_ok += 1

    note = (f"内存门禁: 可达 {len(reach)}/3 站 · "
            f"最小余量 {min([int(live[s]['mem'].get('avail_mb', 0)) // 1024 - 12 for s in reach] or [0])}G · "
            f"站上件一致 {bin_ok}/{bin_ok + bin_bad}")
    if detail:
        return "FAIL", note, info + detail + [f"(WARN) {w}" for w in warn]
    if warn:
        return "WARN", note, info + warn
    return "PASS", note, info


def check_engine(ctx):
    """引擎态: 就绪 + **残留检测**(内存被占着但没有服务)。

    全站停机**不是失败** —— 本项目是"零自加载"方针, 引擎按需启停。
    真正要抓的是"占着内存却没有服务": 本会话实测踩到过一次 A 站 62.6G 的测试残留,
    它污染了后续所有内存判定 (预估被误报 NO_FIT)。
    """
    detail, warn, info = [], [], []
    live = {st: _health_probe(st) for st in ("A", "B", "C")}
    reach = [st for st in ("A", "B", "C") if live[st]["reachable"]]
    running = 0
    for st in ("A", "B", "C"):
        if not live[st]["reachable"]:
            detail.append(f"{st} 站不可达/采集失败: {live[st].get('error')}")
    for st in reach:
        rss = live[st]["rss_mb"] or 0
        ports = live[st]["listen"]
        n_proc = live[st].get("n_proc")
        age = live[st].get("etimes_min_s")
        # ★★ O-143 乙（2026-10-03）：**判定集中到 `classify_engine_band`（唯一定义点）** ——
        #   本循环只负责**取数 + 呈现**：`info`/`note` 是报数，`detail`/`warn` 才来自判定。
        band, why = classify_engine_band(bool(ports), rss, n_proc)
        if ports:
            running += 1
            # ★ O-146（2026-10-05）：**占用者是哪条路径的引擎** —— 只报数（`classify_engine_occupant`
            #   是唯一定义点；**不参与 `classify_engine_band` 的判定**）。取不到 ⇒ `unknown`。
            _occ = live[st].get("occupant") or {}
            _ocmd = live[st].get("occupant_cmd") or {}
            _occ_txt = " ".join(
                f"{_p}:{classify_engine_occupant(_occ.get(_p, 'unknown'), listening=True, cmdline=_ocmd.get(_p, ''))}"
                for _p in ports)
            info.append(f"{st} 站引擎在服务: 端口 {','.join(ports)} · 进程 RSS {rss // 1024}G"
                        + (f" · 进程数 {n_proc}" if isinstance(n_proc, int) else "")
                        + (f" · 最短进程龄 {age}s"
                           if isinstance(age, int) and isinstance(n_proc, int) and n_proc > 0 else "")
                        + (f" · 占用者 {_occ_txt}" if _occ_txt else ""))
            # ★★ O-146 乙′（2026-10-05 裁定）：**占用者进判定** —— 作用域 = `ports.yaml` 驱动的引擎 API 端口。
            for _p in ports:
                if _p not in _engine_api_ports():
                    continue
                _k = classify_engine_occupant(_occ.get(_p, "unknown"), listening=True,
                                              cmdline=_ocmd.get(_p, ""))
                if _k in ("other", "unknown"):
                    _why = "认不出的形态" if _k == "other" else "取不到（判不了 ≠ 通过）"
                    warn.append(f"{st} 站引擎端口 {_p} 占用者**未登记/不可判**（{_k} = {_why}）"
                                f" —— 允许形态 {','.join(_OCCUPANT_OK)}；见 O-146")
        else:
            info.append(f"{st} 站引擎未运行 (RSS {rss}M) —— 零自加载方针下属正常")
        if band == "FAIL":
            detail.append(f"{st} 站**残留**: {why}")
        elif band == "WARN":
            warn.append(f"{st} 站{why}")

    _ages = [live[s].get("etimes_min_s") for s in reach
             if isinstance(live[s].get("etimes_min_s"), int)
             and (live[s].get("n_proc") or 0) > 0]   # ⚠ n_proc=0 的站不参与（否则 0 会污染 min）
    note = (f"引擎: 可达 {len(reach)}/3 站 · 在服务 {running} 站 · "
            f"总占用 {sum((live[s]['rss_mb'] or 0) for s in reach) // 1024}G"
            # ★ O-143 第一步：**只报数** —— 三站里最年轻的 llama 系进程年龄（判据判不了"刚起"时至少看得见）
            + (f" · 最短进程龄 {min(_ages)}s" if _ages else ""))
    if detail:
        return "FAIL", note, info + detail + [f"(WARN) {w}" for w in warn]
    if warn:
        return "WARN", note, info + warn
    return "PASS", note, info


# ── 引擎后端 + 回滚基线 (2026-09-17 新增) ───────────────────────────
# 为什么必须有这条: 原 14 项里**没有任何一项判定"HIP 还是 Vulkan"** —— `engine` 只查进程
#   残留/内存, `stations` 只对账 conf/端口/凭据/插件。后果**已经发生过**: 台账 §1 的
#   "对本集群影响"曾整片按"本集群 = Vulkan / 无 ROCm"写错, 而门禁 13 绿照过
#   (2026-09-17 订正, 见 TRACKER §2.6)。
# 判据(全部可机械判定, 不需要人读; 且都落到**二进制**而非配置文本):
#   (a) 三站 studio 自带引擎在位, 且 ldd 含 libggml-hip         <- 默认单站加载路径的后端
#   (b) 三站 /opt 的 llama-server 与 ggml-rpc-server 均含 libggml-vulkan <- 分布式路径后端
#   (c) 三站 studio 自带 ROCm 运行时版本串一致                  <- 防 studio 静默换 SDK 致三站分叉
#   (d) 三站回滚基线 /opt/llama.cpp-9859 在位                   <- UPGRADE_SOP §6 要求(实测 C 站曾缺失)
_BACKEND_CMD = (
    "echo '===STUDIO==='; "
    "B=\"$HOME/.unsloth/llama.cpp/build/bin/llama-server\"; "
    "if [ -x \"$B\" ]; then "
    "echo 'studio_exe=yes'; "
    "printf 'studio_ggml=%s\\n' \"$(ldd \"$B\" 2>/dev/null | grep -oE 'libggml-(hip|vulkan|cpu)[.]so' | sort -u | tr '\\n' ',')\"; "
    "printf 'studio_rocm=%s\\n' \"$(ls -1 \"$HOME/.unsloth/llama.cpp/build/bin\" 2>/dev/null | grep -oE 'libamdhip64[.]so[.][0-9][0-9.]*' | sort -uV | tail -1)\"; "
    "else echo 'studio_exe=no'; fi; "
    "echo '===OPT==='; "
    "printf 'opt_link=%s\\n' \"$(basename \"$(readlink -f /opt/llama.cpp 2>/dev/null)\")\"; "
    "for n in llama-server ggml-rpc-server; do "
    "P=\"/opt/llama.cpp/$n\"; "
    "if [ -x \"$P\" ]; then "
    "printf 'opt_%s=%s\\n' \"$n\" \"$(ldd \"$P\" 2>/dev/null | grep -oE 'libggml-(hip|vulkan)[.]so' | sort -u | tr '\\n' ',')\"; "
    "else printf 'opt_%s=missing\\n' \"$n\"; fi; "
    "done; "
    "echo '===ROLLBACK==='; "
    "printf 'rollback=%s\\n' \"$(ls -d /opt/llama.cpp-9859 2>/dev/null || echo missing)\"; "
    # ── (e)-(h) 2026-09-23 增: studio 套件的"防线/修复/同版/复原路径" ──────────
    # 为什么加: 2026-09-22 的 A 站翻转事故里, **引擎后端被 update 静默翻转**这件事
    #   是靠人工发现的, 而门禁当时只判"后端类型"(即 (a)) —— 它连"我们事先下的
    #   pin 是否真的生效"都不判。本轮把这四类事实变成取数, 判据见 check_backend。
    "echo '===SUITE==='; "
    "printf 'pin_file=%s\\n' \"$(grep -E '^UNSLOTH_LLAMA_CPP_BACKEND=' /etc/environment 2>/dev/null | tail -1 | cut -d= -f2-)\"; "
    "printf 'pin_seen=%s\\n' \"$(printenv UNSLOTH_LLAMA_CPP_BACKEND 2>/dev/null)\"; "
    "S=\"$HOME/.unsloth/studio/unsloth_studio/lib/python3.13/site-packages\"; "
    "printf 'studio_ver=%s\\n' \"$(ls -d \"$S\"/unsloth-[0-9]*.dist-info 2>/dev/null | sed -E 's|.*/unsloth-(.+)[.]dist-info|\\1|' | sort -V | tail -1)\"; "
    "printf 'events_files=%s\\n' \"$(grep -rl 'X-Unsloth-Events' \"$S/studio\" 2>/dev/null | wc -l)\"; "
    "printf 'engine_md5=%s\\n' \"$(md5sum \"$HOME/.unsloth/llama.cpp/build/bin/llama-server\" 2>/dev/null | cut -d' ' -f1)\"; "
    "printf 'engine_bak=%s\\n' \"$(ls -d \"$HOME/.unsloth/llama.cpp.\"* 2>/dev/null | xargs -r -n1 basename 2>/dev/null | tr '\\n' ',')\""
)
_EXPECT_STUDIO_BACKEND = "libggml-hip.so"      # 默认单站加载 = HIP/ROCm
_EXPECT_LLAMA_BACKEND = "rocm"                 # /etc/environment 里 pin 的期望值 (2026-09-23 增)
_EXPECT_DIST_BACKEND = "libggml-vulkan.so"     # 分布式 / RPC = Vulkan


def check_backend(ctx):
    """引擎后端(默认单站=HIP / 分布式=Vulkan) + 三站同构 + 回滚基线在位。"""
    sys.path.insert(0, str(ROOT / "ops"))
    try:
        import cluster
    except Exception as e:
        return ("WARN", f"无法导入 cluster.py ({type(e).__name__}) — 该项需 paramiko; "
                        f"请用装有 paramiko 的 Python 运行", [])

    detail, warn, info = [], [], []
    per = {}
    for st in ("A", "B", "C"):
        ok, out = cluster.ssh_run(st, _BACKEND_CMD, timeout=60)
        if not ok:
            detail.append(f"{st} 站不可达/采集失败: {out}")
            continue
        d = {}
        for line in (out or "").splitlines():
            if "=" in line and not line.startswith("==="):
                k, _, v = line.partition("=")
                d[k.strip()] = v.strip()
        # 采集成功但关键字段全缺 = 解析失败, 不能当"没问题"
        if not d.get("studio_exe") and not d.get("opt_link"):
            detail.append(f"{st} 站采集输出无法解析 (不做判定): {(out or '')[:120]!r}")
            continue
        per[st] = d

    rocm = {}
    for st, d in per.items():
        s_ggml = d.get("studio_ggml", "")
        if d.get("studio_exe") != "yes":
            detail.append(f"{st} 站 **默认单站引擎缺失**: ~/.unsloth/llama.cpp/build/bin/llama-server "
                          f"不可执行 —— `infer-load`(缺省 backend=unsloth) 会直接加载失败")
        elif _EXPECT_STUDIO_BACKEND not in s_ggml:
            detail.append(f"{st} 站 默认单站引擎**后端不是 HIP**: ldd=[{s_ggml}] "
                          f"(期望含 {_EXPECT_STUDIO_BACKEND}) —— 单站路径实际后端已变, "
                          f"台账 §2.6 的后端矩阵必须同步")
        else:
            info.append(f"{st} 站 默认单站 = HIP ✓ ({s_ggml.strip(',')})")
        rocm[st] = d.get("studio_rocm", "")
        for n in ("llama-server", "ggml-rpc-server"):
            v = d.get(f"opt_{n}", "")
            if v in ("", "missing"):
                detail.append(f"{st} 站 /opt/llama.cpp/{n} 不可执行 —— 分布式路径缺件")
            elif _EXPECT_DIST_BACKEND not in v:
                detail.append(f"{st} 站 /opt/llama.cpp/{n} **后端不是 Vulkan**: ldd=[{v}] "
                              f"(期望含 {_EXPECT_DIST_BACKEND})")
        rb = d.get("rollback", "")
        if not rb or rb == "missing":
            detail.append(f"{st} 站 **回滚基线缺失** /opt/llama.cpp-9859 —— UPGRADE_SOP §6 要求"
                          f"保留 `<现役>` + `9859` 两个版本目录以支持分钟级回滚")
        else:
            info.append(f"{st} 站 回滚基线在位 ({rb})")

    # (c) 三站 studio ROCm 运行时一致 —— 取不到时**不判**(取不到 ≠ 不存在), 显式告警
    vals = sorted({v for v in rocm.values() if v})
    if len(vals) > 1:
        detail.append("三站 studio 自带 ROCm 运行时**不一致**: "
                      + " / ".join(f"{s}={rocm[s]}" for s in sorted(rocm))
                      + " —— 三站可能跑在**不同 HIP 版本**上 (studio 静默换 SDK)")
    elif len(vals) == 1:
        info.append(f"三站 studio ROCm 运行时一致 ({vals[0]})")
    else:
        warn.append("三站均未取到 studio 自带 ROCm 版本串 —— 不做一致性判定 (取不到 ≠ 不存在)")

    # ── (e) pin 在位且**本会话可见** (2026-09-23 增) ────────────────────
    # 判据取「printenv 读得到」而不是「文件里有行」：门禁自身的采集与 `studio update` 是
    # **同一类会话**(非交互 ssh)，故读得到 = 安装器也能读到；只写文件 ≠ 生效
    # (`~/.bashrc` 有 interactive 守卫、`~/.profile` 只被登录 shell 读 —— 见决策简报 §8.2)。
    pins = {s: d.get("pin_seen", "") for s, d in per.items()}
    pinf = {s: d.get("pin_file", "") for s, d in per.items()}
    bad_pin = sorted(s for s, v in pins.items() if v != _EXPECT_LLAMA_BACKEND)
    if bad_pin:
        shown = " / ".join(s + "=会话「" + (pins.get(s) or "(空)") + "」文件「" + (pinf.get(s) or "(无)") + "」"
                           for s in bad_pin)
        detail.append("**" + " / ".join(bad_pin) + " 站 pin 未生效** (非交互 ssh 会话读不到 "
                      "`UNSLOTH_LLAMA_CPP_BACKEND`)： " + shown
                      + " —— 期望「" + _EXPECT_LLAMA_BACKEND + "」。这是「引擎后端被 update 静默翻转」的"
                        "**唯一防线** (显式请求 = mandatory；marker 里的历史选择只是 advisory，探测不认即丢)；"
                        "落点应为 /etc/environment (经 pam_env 对非交互命令亦生效)，见决策简报 §8.2")
    else:
        info.append("pin 在位且会话可见 ✓ (" + _EXPECT_LLAMA_BACKEND + ")")

    # ── (f) X-Unsloth-Events 修复在位 (2026-09-23 增) ──────────────────
    # 缺 = 网关注入无 `choices` 的控制帧 ⇒ 本地 provider 的 compaction 必然失败 (上游 #10362；本仓 O-23)
    noev = sorted(s for s, d in per.items() if (d.get("events_files") or "0") == "0")
    if noev:
        detail.append("**" + " / ".join(noev) + " 站不含 `X-Unsloth-Events` 修复** —— 网关会注入无 `choices` "
                      "的控制帧 ⇒ 本地 provider 的 compaction 必然失败 (上游 unsloth#10362；本仓 O-23)。"
                      "修法 = 升级 studio，见决策简报 §三")
    else:
        info.append("`X-Unsloth-Events` 修复三站在位 ✓")

    # ── (g) studio 版本三站一致性 (不一致 = WARN：滚动升级中间态可接受，但必须可见) ──
    vers = sorted({d.get("studio_ver") for d in per.values() if d.get("studio_ver")})
    if len(vers) > 1:
        warn.append("三站 studio 版本**不一致**：" + " / ".join(
            s + "=" + (per[s].get("studio_ver") or "?") for s in sorted(per))
            + " —— 本仓既定形态是「三站同升」；滚动升级中间态可接受，但口径不一致必须可见")
    elif len(vers) == 1:
        info.append("三站 studio 版本一致 ✓ (" + vers[0] + ")")

    # ── (h) 引擎逐字节同版 ⇒ 站间 tar 复原路径可用 (不同版 = WARN，非 FAIL：各站仍可各自下载) ──
    md5s = sorted({d.get("engine_md5") for d in per.values() if d.get("engine_md5")})
    if len(md5s) > 1:
        warn.append("三站引擎**构建不同版** (md5 不一致)：" + " / ".join(
            s + "=" + (per[s].get("engine_md5") or "?")[:12] for s in sorted(per))
            + " —— 「从同版站 tar 复原」这条分钟级回滚路径不可用 (实测 1.9 G / 18 s)，预案须按逐站写")
    elif len(md5s) == 1:
        info.append("三站引擎逐字节同版 ✓ ⇒ 站间 tar 可复原 (md5 " + md5s[0][:12] + "…)")
    baks = {s: (d.get("engine_bak") or "").strip(",") for s, d in per.items()}
    info.append("引擎面备份目录 (" + "~/.unsloth/llama.cpp.*" + ")： " + " / ".join(
        s + "=" + (baks.get(s) or "(无 — 引擎若被替换，只能靠站间 tar 或重下)") for s in sorted(baks)))

    if not per:
        return "FAIL", "后端: 三站均采集失败", detail
    tip = vals[0] if len(vals) == 1 else " / ".join(f"{s}:{rocm.get(s) or '?'}" for s in sorted(rocm))
    note = f"后端: 可达 {len(per)}/3 站 · 单站=HIP / 分布式=Vulkan · ROCm {tip}"
    # 摘要行必须带上「防线 / 修复 / 同版」三件事 —— info 明细只在 FAIL/WARN 时渲染 (见 main),
    # PASS 时不可见；而这三件事恰是"没红也想知道"的 (如"pin 还在不在位")。
    note += (" · pin " + ("✓" if not bad_pin else "✗")
             + " · studio " + (vers[0] if len(vers) == 1 else ("/".join(vers) or "?"))
             + " · 引擎 " + ("同版" if len(md5s) == 1 else (str(len(md5s)) + " 版不同"))
             + " · 修复 " + ("✗" if noev else "✓"))
    if detail:
        return "FAIL", note, info + detail + [f"(WARN) {w}" for w in warn]
    if warn:
        return "WARN", note, info + warn
    return "PASS", note, info


def check_models(ctx):
    """模型库完整性: 孤儿(物理库有/聚合视图无) + 断链(软链目标不存在)。"""
    sys.path.insert(0, str(ROOT / "ops"))
    try:
        import cluster
    except Exception as e:
        return ("WARN", f"无法导入 cluster.py ({type(e).__name__}) — 该项需 paramiko", [])

    detail, info = [], []
    reach = 0
    tot_o = tot_b = 0
    for st in ("A", "B", "C"):
        m = cluster._scan_models(st)
        if not m:
            detail.append(f"{st} 站模型库扫描失败 (站不可达?)")
            continue
        reach += 1
        orp, brk = m["orphans"], m["broken"]
        tot_o += len(orp)
        tot_b += len(brk)
        info.append(f"{st} 站: 物理库 {len(m['phy'])} / 聚合视图 {len(m['agg'])} / "
                    f"孤儿 {len(orp)} / 断链 {len(brk)}")
        for x in orp:
            detail.append(f"{st} 站孤儿 {x} —— 物理库有、聚合视图无: **权重在但清单看不到、"
                          f"也加载不了**; 修: `cluster.py models link --go`")
        for x in brk:
            detail.append(f"{st} 站断链 {x} —— 聚合视图软链目标不存在; "
                          f"修: `cluster.py models prune --go`")

    note = f"模型库: 可达 {reach}/3 站 · 孤儿 {tot_o} · 断链 {tot_b}"
    if detail:
        return "FAIL", note, info + detail
    return "PASS", note, info


# ── 断言: inbox 受理区状态自洽 (P1, quick) ──────────────────────────
# 目的: 阻止受理区目录与状态机漂移 —— 每个 <proj>-<yyyy-mm-dd>/ 必须满足
#   ① 有 00_handoff/ (需求方原件冻结区)
#   ② 40_state/STATE.json 存在、可解析、state ∈ 白名单
#   ③ 状态内容自洽 (accepted+ 须有 受理决定.md; plan-review/plan-revise 须有 20_plan;
#      release+ 须有 30_evidence 记录)
# 依据: ADR-0008 + inbox/README §3 状态机 (2026-09-23 扩展: waiting/协商回环/验收签收)
# D6-P1-2 M-5/M-6: 白名单**已收敛**到 inventory/inbox.yaml —— 由 check_mirror 对账(README §3 + 两处代码)
INBOX_DIR = ROOT / "inbox"
try:
    _INBOX_TRUTH = read_inbox_truth(INBOX_TRUTH_YAML)
except Exception:
    # fail-closed: 真值不可读 => 白名单为空 => 任何 STATE 都 FAIL;
    # 真正的报错点见 check_mirror(它会点名「inbox.yaml 读不出」)
    _INBOX_TRUTH = {}
INBOX_STATES = set(_INBOX_TRUTH)
INBOX_PROJ_RE = re.compile(r"^[^_].+-\d{4}-\d{2}-\d{2}$")   # <proj>-<yyyy-mm-dd>, 排除 _template


def check_inbox(ctx):
    """受理区状态自洽: 目录结构 + STATE.json 合法 + 状态内容自洽。"""
    n_dir = n_state = n_bad = n_mf_skip = 0
    bad = []
    if not INBOX_DIR.is_dir():
        return "PASS", "inbox/ 不存在, 跳过", []
    # 必需件状态集: 由真值 requires 派生 (D6-P1-2 #7: 原为 4 处硬编码子集, 已收敛到一处)
    need = {k: inbox_requires_sets(_INBOX_TRUTH, k) for k in INBOX_REQUIRES_KEYS}
    for d in sorted(p for p in INBOX_DIR.iterdir() if p.is_dir()):
        name = d.name
        if name.startswith("_") or not INBOX_PROJ_RE.match(name):
            continue
        n_dir += 1
        # ① 必须有 00_handoff/ (需求方原件冻结区)
        if not (d / "00_handoff").is_dir():
            n_bad += 1
            bad.append(f"{name}: 缺 00_handoff/ (需求方原件冻结区)")
            continue
        # ② STATE.json 存在且可解析, state ∈ 白名单
        state_file = d / "40_state" / "STATE.json"
        if not state_file.is_file():
            n_bad += 1
            bad.append(f"{name}: 缺 40_state/STATE.json (状态必须可机读)")
            continue
        try:
            state = json.loads(state_file.read_text(encoding="utf-8")).get("state")
        except Exception:
            n_bad += 1
            bad.append(f"{name}: STATE.json 不是合法 JSON")
            continue
        n_state += 1
        if state not in INBOX_STATES:
            n_bad += 1
            bad.append(f"{name}: STATE={state!r} 不在白名单 ({', '.join(sorted(INBOX_STATES))})")
            continue

        def _nonempty(p):
            """目录存在且至少有一个非 .gitkeep 文件。"""
            return p.is_dir() and any(x.is_file() and x.name != ".gitkeep" for x in p.iterdir())

        # ③ 状态内容自洽 (必需件集由真值 requires 派生 —— 见 inventory/inbox.yaml)
        if state in need["decide"]:
            if not (d / "10_admin" / "受理决定.md").is_file():
                n_bad += 1
                bad.append(f"{name}: STATE={state} 须有 10_admin/受理决定.md (受理通过依据)")
        if state in need["plan"]:
            if not _nonempty(d / "20_plan"):
                n_bad += 1
                bad.append(f"{name}: STATE={state} 须有 20_plan/ 派发计划 (非空)")
        if state in need["evidence"]:
            if not _nonempty(d / "30_evidence"):
                n_bad += 1
                bad.append(f"{name}: STATE={state} 须有 30_evidence/ 证据束记录 (非空)")
        # 2026-09-23 收紧: **交付态**必须真的钉死证据束，不能只是"目录非空"。
        #   为什么收紧: 原判据放个无关文件就能过 ⇒ "未附证据束不 done" 形同虚设（空转的软约束）。
        #   判据 = 30_evidence/MANIFEST.sha256 存在。
        #   `rejected-by-requester`(可能交付前就终止) 本态 requires 无 `manifest` ⇒ 不进本集。
        if state in need["manifest"]:
            if not (d / "30_evidence" / "MANIFEST.sha256").is_file():
                n_bad += 1
                bad.append(f"{name}: STATE={state} 须有 30_evidence/MANIFEST.sha256 (交付证据束未钉死); "
                           f"生成: cluster.py inbox seal {name} --go")

        # ④ 交付证据束 **freshness**（D6-P1-1 §11.1-C 纪律 2/3）：只要有 MANIFEST 就**重算 → 比对**
        #   ⇒ 把"生成物**禁手改**"从空头承诺变成**机判**（改源头没重跑 / 手改清单 ⇒ 当场对不上）。
        #   项目根取自 **MANIFEST 头注释**（自包含，换 clone 也能判）；根**不在本机** ⇒ **跳过并报数**
        #   （那是可移植性问题，不是"被手改" ⇒ 不 FAIL，但必须可见）。判据实现与 CLI `--check` **同一个**。
        mf = d / "30_evidence" / "MANIFEST.sha256"
        if mf.is_file():
            try:
                import cluster as _cluster
                mroot, _mok, _mmiss, mbad = _cluster.verify_manifest(mf.read_text(encoding="utf-8"))
            except Exception as e:
                n_bad += 1
                bad.append(f"{name}: MANIFEST 校验无法执行（导入/读取失败）: {type(e).__name__}: {e}")
            else:
                if mroot and not Path(mroot).is_dir():
                    n_mf_skip += 1
                elif mbad:
                    n_bad += 1
                    _shown = "、".join(x.split(":", 1)[0] for x in mbad[:3])
                    bad.append(f"{name}: MANIFEST.sha256 **重算不符 {len(mbad)} 条** ⇒ 证据束被手改或源被改动"
                               f"（如 {_shown}）；核对: cluster.py inbox seal {name} --check")

    note = f"受理目录 {n_dir} · 状态可机读 {n_state} · 违规 {n_bad}"
    if n_mf_skip:
        note += f" · MANIFEST 未校验 {n_mf_skip}（项目根不在本机）"
    return ("FAIL" if n_bad else "PASS"), note, bad


# ── 断言清单 (加校验 = 在此加一条 + 写一个函数) ─────────────────────
# fix 字段 = 该项失败/警告时的**处置建议** (健康引擎要求"红灯必须给出下一步", 而不是
# 只报"哪里不对")。main() 在结论区按严重度打印。
# ── 断言: agent-cli.ps1 离线黄金夹具接线 (D6-P3-2) ────────────────────
# 为什么: `ops/station-bin/_fm_golden_test.ps1` 是一份**离线单测**（用 AST 从 `agent-cli.ps1` 提取**真函数**
#   + **真 `ROUTE_TABLE` / `JUDGE_TABLE`**，185 条断言），覆盖出站硬闸与判定面：
#   `Get-SensitivityBackendReject`（`local-only × 出网 ⇒ REJECT`，**唯一规则**）、`Get-BackendEgress`
#   （fail-closed：只有 `local/<flavor>` 不出网）、`Get-JudgeEgress` / `Get-JudgeComplianceReject`、
#   `Test-EvmStatePull`、`Get-FrameworkSubjects` … 共 20+ 纯函数。
# ⚠ **它此前只靠"人记着跑"**（多份文档称其为铁律）⇒ **不在 `CHECKS` 里** ⇒ 两次重构后**无人发现**
#   夹具期望值已陈旧：① 模块化把 paramiko 下沉到 `cluster_ssh.py`（旧目标恒 `SSHClient=0`）；
#   ② O-29 把 `golden-cmd` 从裸列改成条件列（基线 11→10）⇒ **实测 179 pass / 6 fail**（2026-09-25）。
# ⇒ 本断言把它**接进统一门禁**：退出码 0 = PASS；非 0 ⇒ FAIL 并把尾部 + FAIL 行贴进明细。
#   **判据在夹具里，本断言只负责"让它每次都被跑"**（判据本体不复制，避免第二份实现）。
# ✅ **quick**：实测夹具整体 ≈ **1.9s**（一次 pwsh 启动 + 185 条断言 + 一次 python AST 探测）
#   ⇒ 放进 `--quick`，**由 pre-commit 钩子强制**（否则仍只是"跑全量才判"，等于没接线）。
# ⚠ 定义必须在本行**之前**（`CHECKS` 在模块级求值）。
PS1_GOLDEN = ROOT / "ops" / "station-bin" / "_fm_golden_test.ps1"
# O-63 (2026-09-25): 取号并发夹具 —— 与黄金夹具**分开**成一项，且 `quick:False`：
#   它要起 8 个 **独立进程** + 两次共同释放时刻(各 2.5s) ⇒ 约 6s；塞进 quick 会让 pre-commit 明显变慢。
#   但**必须接进 CHECKS** —— 否则就是本仓反复点名的"有测试 ≠ 有人在跑"。
PS1_RUNSTAMP = ROOT / "ops" / "station-bin" / "_runstamp_hammer.ps1"
# O-64 (2026-09-25): Python 测试的**统一入口**。此前它**不在 CHECKS 里** ⇒ 无任何机械执行者 ⇒
#   实测被两轮提交（59d97c3 / fd96a89）穿透：O-62/O-63 改实现后 `test_cli_concurrency_guards.py`
#   当场红两条，**没有任何钩子出声**。这正是本仓点名的"有测试 ≠ 有人在跑"。
# 为什么 `quick:False`（实测值，与 ps1-runstamp 同一决策依据）：本入口 **12.2s**，而 quick 门禁本体 18.4s
#   ⇒ 塞进 quick 会让 pre-commit 从 ~18s 涨到 ~31s（+66%）。**非 quick 仍能兜住**：pre-push 跑全量
#   ⇒ 红状态**推不出去**。若将来想让它更早暴露，把 CHECKS 里那项改成 quick=True 即可（一行）。
PY_TESTS = ROOT / "tests" / "run_py_tests.py"


def _decode_out(b: bytes) -> str:
    """PS 5.1 重定向时的输出编码随控制台（zh-CN 常见 cp936）⇒ 先 utf-8 再 cp936，最后兜底替换。"""
    for enc in ("utf-8", "cp936"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", "replace")


def check_ps1_runstamp(ctx):
    """O-63: 跑 `_runstamp_hammer.ps1`（ts **取号**的跨进程并发夹具）—— **退出码 0 才算过**。

    它守的是"两个并发派发拿到同一个 ts ⇒ 共用 scratch/runDir ⇒ 证据面混且归属不可复原"这条
    **不可回改**的失败（实测 2026-09-25）。夹具自带**双向**：正向（新实现 8 进程全不同 ts）+
    负向（**同一把锤子**打旧实现 ⇒ 必须检出撞车）⇒ **必须两行都在**才算过，否则"跑空了"也会通过。
    """
    if not PS1_RUNSTAMP.is_file():
        return "WARN", f"{PS1_RUNSTAMP.name} 不存在（本断言的登记依据）", []
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PS1_RUNSTAMP),
             "-N", "8", "-SelfTest"],
            cwd=ROOT, capture_output=True, timeout=180)
    except FileNotFoundError:
        return "WARN", "本机无 powershell ⇒ 跳过（夹具只能在 Windows 侧跑）", []
    except subprocess.TimeoutExpired:
        return "FAIL", "取号夹具超时（>180s）⇒ 可能挂死", []
    out = _decode_out(p.stdout or b"") + _decode_out(p.stderr or b"")
    lines = [ln.rstrip() for ln in out.splitlines() if ln.strip()]
    pos = next((ln for ln in lines if ln.startswith("RUNSTAMP_HAMMER ")), "")
    neg = next((ln for ln in lines if ln.startswith("RUNSTAMP_HAMMER_SELFTEST")), "")
    ok = bool(pos and "PASS" in pos) and bool(neg and "PASS" in neg) and p.returncode == 0
    note = f"取号并发夹具：{pos or '（无正向汇总行）'} · {neg or '（无负向汇总行）'}"
    if p.returncode != 0 and ok:
        note += f" · 退出码 {p.returncode}"
    # ⚠ 缺任一汇总行 ⇒ **直接 FAIL**（"什么都没跑"不得算过 —— 本仓"假绿"头号形态）
    detail = lines[-8:]
    return ("PASS" if ok else "FAIL"), note, detail


def check_py_tests(ctx):
    """O-64 (2026-09-25): 跑 `tests/run_py_tests.py`（`tests/` 下全部独立测试的统一入口）。

    为什么需要本断言：该入口此前**不在 CHECKS 里** ⇒ **无任何机械执行者** ⇒ 实测被两轮提交穿透
    （O-62/O-63 改实现后 `test_cli_concurrency_guards.py` 当场红两条，无钩子出声）。
    ★ 判据 = **退出码 0 ∧ 解析到汇总行 ∧ 通过数 == 总数 ∧ 总数 > 0**，四者缺一即 FAIL。
      为什么不能只看"跑起来了"：`总数 == 0`（例如入口被改坏、discover 返回空）或"什么都没判"
      都会通过 ⇒ 又落进本仓头号形态（**假绿**）。入口自身也已在"未发现测试"时退 1，这里是双保险。
    ⚠ 解释器用 **`sys.executable`**（= 门禁自身的解释器）—— 依据 O-36：换解释器会**静默少跑 4 个套件**
      （PATH 上的 `python` 与钩子用的 `py.exe` 是不同环境）。用 `sys.executable` 从构造上杜绝该漂移。
    """
    if not PY_TESTS.is_file():
        return "WARN", f"{PY_TESTS} 不存在（本断言的登记依据）", []
    try:
        p = subprocess.run([sys.executable, str(PY_TESTS)], cwd=ROOT,
                           capture_output=True, timeout=420)
    except subprocess.TimeoutExpired:
        return "FAIL", "Python 测试套件超时（>420s）⇒ 可能挂死", []
    out = _decode_out(p.stdout or b"") + _decode_out(p.stderr or b"")
    lines = [ln.rstrip() for ln in out.splitlines() if ln.strip()]
    m = re.search(r"结果:\s*(\d+)/(\d+)\s*通过", out)
    n_pass, n_tot = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    bad = next((ln for ln in lines if ln.startswith("失败:")), "")
    ok = bool(m) and n_tot > 0 and n_pass == n_tot and p.returncode == 0
    note = f"Python 测试套件: {n_pass}/{n_tot} 通过"
    if bad:
        note += f" · {bad}"
    if not m:
        note += " · ⚠ 未解析到汇总行（入口可能被改坏）"
    detail = [ln for ln in lines if "PASS" in ln or "FAIL" in ln][-15:]
    return ("PASS" if ok else "FAIL"), note, detail


def check_ps1_golden(ctx):
    """P3-2: 跑 `_fm_golden_test.ps1`（agent-cli.ps1 的离线黄金夹具）—— **退出码 0 才算过**。"""
    if not PS1_GOLDEN.is_file():
        return "WARN", f"{PS1_GOLDEN.name} 不存在（本断言的登记依据）", []
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PS1_GOLDEN)],
            cwd=ROOT, capture_output=True, timeout=300)
    except FileNotFoundError:
        return "WARN", "本机无 powershell ⇒ 跳过（夹具只能在 Windows 侧跑）", []
    except subprocess.TimeoutExpired:
        return "FAIL", "夹具超时（>300s）⇒ 可能挂死", []
    out = _decode_out(p.stdout or b"") + _decode_out(p.stderr or b"")
    lines = [ln.rstrip() for ln in out.splitlines() if ln.strip()]
    summary = next((ln for ln in reversed(lines) if "FM_GOLDEN_TEST" in ln), "").strip()
    fails = [ln for ln in lines if ln.startswith("FAIL")]
    note = f"离线黄金夹具：{summary or '（无汇总行）'}"
    if p.returncode != 0:
        note += f" · 退出码 {p.returncode}"
    detail = lines[-12:]
    if fails:
        detail += ["── FAIL 行 ──"] + fails[:15]
    return ("PASS" if p.returncode == 0 else "FAIL"), note, detail


# ── D7-P3-2 (2026-09-26)「结论收束记账」: 结论进**既有**追加式账本, **不新造账本** ────
#   合并稿 §13.3 原话：「D7 的结论留痕应**复用 `inbox` 的 `40_state/LOG.md` 追加式纪律**，
#   **不新造账本**。」下面的函数把「本仓有哪些账本」变成**封闭集** ⇒
#   「有人新造了第二本账本」从「靠人记得」变成**可机判**。
LEDGERS_INV = ROOT / "inventory" / "conclusion-ledgers.yaml"
LEDGER_SCAN_EXCLUDE_DIRS = (".git", "node_modules", ".venv", "tmp")


def _s(v):
    """取字符串（非字符串一律当空）—— 避免 `42.strip()` 这类调用把判据打崩。"""
    return v.strip() if isinstance(v, str) else ""


def _fnmatch_any(rel, globs):
    """相对仓库根的 posix 路径 是否命中任一 glob。

    ★ 口径 = **fnmatch 语义**（`*` **跨** `/`）—— 这是**显式选择**：本表要的是
      「**形状覆盖**」（防的是「新造一本长得像的」），不是「精确路径」（后者归 `doclinks`）。
      ⚠ 用 `PurePath.match` 会**不同**（它的 `*` 不跨分隔符）⇒ 两处口径会悄悄分叉。
    """
    return any(fnmatch.fnmatchcase(rel, g) for g in (globs or []) if g)


def validate_conclusion_ledgers(doc, scan_hits=None):
    """**纯函数**（D7-P3-2）：账本真值表自洽 + 「扫描命中 ⊆ 登记集」。

    ⚠ `scan_hits` = 相对仓库根的 posix 路径列表（由 `check_conclusion_ledger` 去扫）。
      `None` = **不判扫描**（单测合成样例时用）—— 它**绝不**表示「0 命中 ⇒ 通过」。
      「读不到 ≠ 通过」在本函数里的落法：`None` 时**不产出扫描结论**，
      而不是产出「扫描过了，没问题」。
    """
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["顶层不是映射（yaml 根应是 mapping）"], notes

    disciplines = doc.get("disciplines")
    if not isinstance(disciplines, list) or not disciplines:
        bad.append("`disciplines` 为空 ⇒ 没有封闭枚举就没有纪律（『缺锚点不得登记』同源）")
        disciplines = []
    elif any(not _s(d) for d in disciplines):
        bad.append("`disciplines` 里有非字符串 / 空串项")

    ledgers = doc.get("ledgers")
    if not isinstance(ledgers, list) or not ledgers:
        bad.append("`ledgers` 为空 ⇒ 本表**没有对象**（退化空判 = 本仓头号形态）")
        ledgers = []

    seen_ids, used_disc, ledger_globs = set(), set(), []
    for i, lg in enumerate(ledgers):
        at = f"ledgers[{i}]"
        if not isinstance(lg, dict):
            bad.append(f"{at} 不是映射")
            continue
        lid = _s(lg.get("id"))
        if not lid:
            bad.append(f"{at} 缺 `id`")
        elif lid in seen_ids:
            bad.append(f"{at} `id` 重复: {lid}（账本 id 是标识，不得复用）")
        else:
            seen_ids.add(lid)
            at = f"ledgers[{lid}]"
        # 账本三要素：唯一写入者 / 纪律出处 / 独立校验 —— 缺一即不可判
        for k in ("what", "writer", "truth_doc", "verify"):
            if not _s(lg.get(k)):
                bad.append(f"{at} 缺 `{k}` —— 账本三要素（唯一写入者 / 纪律出处 / 独立校验）缺一即不可判")
        disc = lg.get("discipline")
        if disc not in disciplines:
            bad.append(f"{at} 的 `discipline`={disc!r} 不在声明集 {disciplines} 里")
        else:
            used_disc.add(disc)
        gl = [g for g in (lg.get("globs") or []) if _s(g)]
        pa = [p for p in (lg.get("paths") or []) if _s(p)]
        if not gl and not pa:
            bad.append(f"{at} 既无 `globs` 也无 `paths` ⇒ 无法判它指的是哪个文件")
        ledger_globs += gl + pa

    # 孤儿纪律：声明了却没有任何账本用 ⇒ 装饰（同 promotion 的『孤儿字段』）
    for d in disciplines:
        if d not in used_disc:
            bad.append(f"孤儿纪律: `disciplines` 声明了 {d!r} 但**没有任何账本**用它 ⇒ 形同虚设")

    # ── ★★「不新造账本」的**正面表述**必须写下来（空 = 没写 ⇒ FAIL）─────────
    nal = doc.get("not_a_ledger")
    if not isinstance(nal, list) or not nal:
        bad.append("`not_a_ledger` 为空 ⇒ **没有写下「什么不算账本」** ⇒ 下一个人会按『看着像』再建一本")
        nal = []
    for i, it in enumerate(nal):
        if not isinstance(it, dict) or not _s(it.get("glob")) or not _s(it.get("why")):
            bad.append(f"not_a_ledger[{i}] 缺 `glob` 或 `why`（『什么不算账本』必须给理由）")
            continue
        # ── 交叉：同一形态**不能既登记为账本、又声明不是账本**（自相矛盾）──
        g = _s(it["glob"])
        clashed = [x for x in ledger_globs if fnmatch.fnmatchcase(x, g) or fnmatch.fnmatchcase(g, x)]
        if clashed:
            bad.append(f"`not_a_ledger` 的 {g!r} 与登记的账本形态 {clashed} **相撞**"
                       f"（既说是账本、又声明不是 ⇒ 两处口径矛盾）")

    scan = doc.get("scan") if isinstance(doc.get("scan"), dict) else {}
    if not [g for g in (scan.get("globs") or []) if _s(g)]:
        bad.append("`scan.globs` 为空 ⇒ 没有扫描口径就没有『未登记账本』这条判据")
    if not [d for d in (scan.get("exclude_dirs") or []) if _s(d)]:
        bad.append("`scan.exclude_dirs` 为空 ⇒ 会把 .git / 依赖目录一起扫进来（口径不完整）")

    # ── 扫描侧（`scan_hits is None` ⇒ **不判**，而不是判过）─────────────────
    if scan_hits is not None:
        for rel in scan_hits:
            if not _fnmatch_any(rel, ledger_globs):
                bad.append(f"★**未登记的账本**: {rel} —— 它在扫描口径内却不属于任何已登记账本 ⇒ "
                           f"要么登记进 `inventory/conclusion-ledgers.yaml`，要么把扫描口径说清")
        # 反向防腐化：登记了 globs 的账本**必须**有条目命中（登记了却扫不到 = 登记已腐化）
        for lg in ledgers:
            if not isinstance(lg, dict):
                continue
            gl = [g for g in (lg.get("globs") or []) if _s(g)]
            if gl and not any(_fnmatch_any(h, gl) for h in scan_hits):
                bad.append(f"账本 {_s(lg.get('id'))!r} 登记了 globs {gl} 却**一条也没命中** ⇒ "
                           f"登记腐化（账本被删 / 改名，或 glob 写错）")

    unv = doc.get("unverified")
    if not isinstance(unv, list) or not unv:
        bad.append("`unverified` 为空 ⇒ 本项自己未实测 / 未定的部分没登记")

    if not bad:
        notes.append(f"账本 {len(ledgers)} 本 · 纪律 {sorted(used_disc)} · 非账本点名 {len(nal)} 项")
        if scan_hits is None:
            notes.append("扫描：**未接扫描输入（不判，不算通过）**")
        else:
            notes.append(f"扫描命中 {len(scan_hits)} 处 · 全部已登记")
    return bad, notes


def _scan_ledger_hits():
    """按 `scan` 段扫盘，返回**相对仓库根**的 posix 路径（排序去重）。"""
    import yaml
    doc = yaml.safe_load(_read_text(LEDGERS_INV)) or {}
    scan = doc.get("scan") if isinstance(doc.get("scan"), dict) else {}
    exclude = set(scan.get("exclude_dirs") or []) | set(LEDGER_SCAN_EXCLUDE_DIRS)
    hits = []
    for g in (scan.get("globs") or []):
        if not _s(g):
            continue
        for p in ROOT.glob(g):
            if not p.is_file():
                continue
            rel = p.relative_to(ROOT).as_posix()
            if any(part in exclude for part in rel.split("/")):
                continue
            hits.append(rel)
    return sorted(set(hits))


def check_conclusion_ledger(ctx):
    """D7-P3-2: 「结论收束记账」—— 结论进**既有**追加式账本，**不新造账本**。"""
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 conclusion-ledger 断言", []
    if not LEDGERS_INV.exists():
        return "FAIL", "inventory/conclusion-ledgers.yaml 缺失（本断言的登记依据）", []
    try:
        doc = yaml.safe_load(_read_text(LEDGERS_INV)) or {}
    except Exception as e:
        return "FAIL", f"inventory/conclusion-ledgers.yaml 解析失败: {type(e).__name__}: {e}", []
    try:
        hits = _scan_ledger_hits()
    except Exception as e:
        # ⚠ **读不到 ≠ 通过**：扫描失败必须报出来，**不许**回落到「不判扫描」。
        return "FAIL", f"账本扫描失败（不可判 ⇒ 不许当通过）: {type(e).__name__}: {e}", []
    bad, notes = validate_conclusion_ledgers(doc, scan_hits=hits)
    # 盘上存在性：登记了 `paths` 的账本，文件必须真在（「登记腐化」的另一半）
    for lg in (doc.get("ledgers") or []):
        if not isinstance(lg, dict):
            continue
        for p in (lg.get("paths") or []):
            if not _s(p):
                continue
            if not (ROOT / p).exists():
                bad.append(f"账本 {_s(lg.get('id'))!r} 登记的路径不存在: {p} ⇒ "
                           f"登记腐化（换机器 / 被删 / 改名）")
    return ("FAIL" if bad else "PASS"), " · ".join(notes), bad


# ── D7-P3-2 (2026-09-26)「标准复核目录」: 免终裁类目清单（D-43 的退出判据之一）────────
REVIEW_CATALOG_INV = ROOT / "inventory" / "review-catalog.yaml"


def validate_review_catalog(doc):
    """**纯函数**（D7-P3-2）：标准复核目录的自洽（免终裁类目清单）。

    ★ 守的是 **D-43 的准入门槛**「同一类被批准两次」（ITIL 原话）。它最容易被绕开的方式是
      「把 `approvals` 填成 2 但**拿不出那两次的锚点**」⇒ 故
      `len(approval_anchors) == approvals` 是硬条件（只填数字 = 自说自话）。
    """
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["顶层不是映射（yaml 根应是 mapping）"], notes

    adm = doc.get("admission") if isinstance(doc.get("admission"), dict) else {}
    if not adm:
        bad.append("缺 `admission` 段 ⇒ 没有准入门槛，『类目』就退化成『我觉得安全』")
    if not _s(adm.get("rule")):
        bad.append("`admission.rule` 为空 ⇒ 门槛没有出处")
    ma = adm.get("min_approvals")
    if not isinstance(ma, int) or isinstance(ma, bool) or ma < 2:
        bad.append(f"`admission.min_approvals`={ma!r} 必须 ≥ 2 —— 门槛设成 1 或 0 ⇒ "
                   f"**每一类都是标准复核** = 判据恒真（本仓头号形态）")
        ma = 2
    if not isinstance(adm.get("type_axis"), str):
        bad.append("`admission.type_axis` 必须是字符串（未定义 ⇒ 置空串，**不是**省略该键）")
    if not _s(adm.get("type_axis_note")):
        bad.append("`admission.type_axis_note` 为空 ⇒ 类型轴的现状（有 / 无 / 为什么）没写下来")
    rt = adm.get("ratio_target")
    if not isinstance(rt, dict):
        bad.append("缺 `admission.ratio_target`（ITIL 的比例目标 —— 只报数，但必须登记）")
        rt = {}
    else:
        lo, hi, judged = rt.get("low"), rt.get("high"), rt.get("judged")
        if not (isinstance(lo, int) and isinstance(hi, int) and not isinstance(lo, bool)
                and not isinstance(hi, bool) and 0 < lo < hi <= 100):
            bad.append(f"`ratio_target` 的 low/high 非法: {lo}/{hi}（须 0 < low < high ≤ 100）")
        if not isinstance(judged, bool):
            bad.append("`ratio_target.judged` 必须是布尔 —— 它标明这条目标是**判**还是**只报数**")

    sch = doc.get("entry_schema") if isinstance(doc.get("entry_schema"), dict) else {}
    if not sch:
        bad.append("缺 `entry_schema` 段 ⇒ 类目的形状没定义 ⇒ 登进来的东西无法核对")
    stages = sch.get("exempt_stages")
    if not isinstance(stages, list) or not stages or any(not _s(s) for s in stages):
        bad.append("`entry_schema.exempt_stages` 必须是非空字符串列表（免哪一层 = 封闭枚举）")
        stages = []
    fields = sch.get("fields")
    fids = []
    if not isinstance(fields, list) or not fields:
        bad.append("`entry_schema.fields` 为空")
        fields = []
    for i, f in enumerate(fields):
        if not isinstance(f, dict) or not _s(f.get("id")):
            bad.append(f"entry_schema.fields[{i}] 缺 `id`")
            continue
        if not _s(f.get("note")):
            bad.append(f"entry_schema.fields[{i}]({_s(f.get('id'))}) 缺 `note` ⇒ 字段含义靠猜")
        fids.append(_s(f.get("id")))
    if len(fids) != len(set(fids)):
        bad.append("`entry_schema.fields` 的 `id` 有重复")
    req = sch.get("required")
    if not isinstance(req, list) or not req:
        bad.append("`entry_schema.required` 为空 ⇒ 没有必填就没有门")
        req = []
    for r in req:
        if r not in fids:
            bad.append(f"`entry_schema.required` 引用了不存在的字段 {r!r}")
    for fid in fids:
        if fid not in req:
            bad.append(f"孤儿字段: `entry_schema.fields` 有 {fid!r} 但 `required` 没用它 ⇒ 装饰")

    entries = doc.get("entries")
    if not isinstance(entries, list):
        bad.append("缺 `entries` 字段（『不存在』与『为空』必须可区分）")
        entries = []
    seen = set()
    for i, e in enumerate(entries):
        at = f"entries[{i}]"
        if not isinstance(e, dict):
            bad.append(f"{at} 不是映射")
            continue
        eid = _s(e.get("id"))
        if eid and eid in seen:
            bad.append(f"{at} `id` 重复: {eid}")
        seen.add(eid)
        at = f"entries[{eid or i}]"
        for k in req:
            v = e.get(k)
            if v is None or (isinstance(v, (str, list)) and not v):
                bad.append(f"{at} 缺必填 `{k}`")
        if e.get("exempt_from") and e["exempt_from"] not in stages:
            bad.append(f"{at} `exempt_from`={e['exempt_from']!r} 不在封闭枚举 {stages} 里")
        ap = e.get("approvals")
        if not isinstance(ap, int) or isinstance(ap, bool) or ap < ma:
            bad.append(f"{at} `approvals`={ap!r} 未达准入门槛 {ma}（D-43：同一类被批准两次）")
        anchors = e.get("approval_anchors")
        if not isinstance(anchors, list) or not anchors or any(not _s(a) for a in anchors):
            bad.append(f"{at} `approval_anchors` 必须是非空字符串列表")
        elif isinstance(ap, int) and not isinstance(ap, bool) and len(anchors) != ap:
            bad.append(f"{at} `approval_anchors` 有 {len(anchors)} 条但 `approvals`={ap} ⇒ "
                       f"**只填数字拿不出锚点** = 自说自话（D-43 的门槛没被真满足）")
        rv = e.get("review_every")
        if not isinstance(rv, int) or isinstance(rv, bool) or rv <= 0:
            bad.append(f"{at} `review_every` 必须是正整数（天）")

    # ★ 交叉：有类目却**没有类型轴** ⇒ 那些类目凭什么浮出来的？
    if entries and not _s(adm.get("type_axis")):
        bad.append("★ 有类目（`entries` 非空）但 `admission.type_axis` 为空 ⇒ "
                   "**类目没有浮出依据**（门槛是『同一类』，没有轴就没有『类』）")
    if not entries and not _s(doc.get("empty_reason")):
        bad.append("`entries` 为空却没有 `empty_reason` ⇒ **空不许当『没事』**（本仓已登记的假绿形态）")

    unv = doc.get("unverified")
    if not isinstance(unv, list) or not unv:
        bad.append("`unverified` 为空 ⇒ 本项自己未实测 / 未定的部分没登记")

    if not bad:
        notes.append(f"免终裁类目 {len(entries)} 条 · 准入门槛 min_approvals={ma} · "
                     f"类型轴 {'已定义' if _s(adm.get('type_axis')) else '**未定义**'}")
        if rt:
            notes.append(f"比例目标 {rt.get('low')}–{rt.get('high')}%"
                         f"（{'判' if rt.get('judged') else '**只报数、不判**'}）")
        notes.append(f"可豁免层 {stages}")
    return bad, notes


def check_review_catalog(ctx):
    """D7-P3-2: 标准复核目录（D-43 退出判据『免终裁类目有清单』）。"""
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 review-catalog 断言", []
    if not REVIEW_CATALOG_INV.exists():
        return "FAIL", "inventory/review-catalog.yaml 缺失（本断言的登记依据）", []
    try:
        doc = yaml.safe_load(_read_text(REVIEW_CATALOG_INV)) or {}
    except Exception as e:
        return "FAIL", f"inventory/review-catalog.yaml 解析失败: {type(e).__name__}: {e}", []
    bad, notes = validate_review_catalog(doc)
    return ("FAIL" if bad else "PASS"), " · ".join(notes), bad


# ── D7-P3-3 (2026-09-26)「记忆四道门」+ 授权边界写成**结构性约束** ────────────────
#   D-47：共享记忆做，但必须带四道门（write/retrieval/promotion/reuse）；
#         MAPLE-Guard（arXiv 2608.00426）：**私有→共享的"晋升"是攻击面的关键一跳**。
#   D-48：**不要指望"审得更准"，要靠"结构 contain"**（arXiv 2609.17648：JBR 100% 但 Unsafe 0%）。
#   D-40：**单人开发者是常态假设** ⇒ 授权边界只能写成结构性约束。
#   ⇒ 本判据判四件事：① 四门各有一条**真实存在**的判据（防"挂名假判"）；
#     ② 私有→共享的**每条通道**都要写明 `gate`（"无门"必须可区分于"刻意共享"）；
#     ③ 结构性约束**必须有判据**（没判据的仍只是纪律）；
#     ④ 记忆面的**接触点**是封闭集 + 记忆**不得出网**。
MEMORY_GATES_INV = ROOT / "inventory" / "memory-gates.yaml"
MEMORY_GATE_IDS = ("write", "retrieval", "promotion", "reuse")
MEMORY_CODE_EXTS = (".py", ".ps1", ".psm1", ".sh")


def extract_memory_symlinks(text, token):
    """从 `agent-cli.ps1` 提取**把记忆库文件做 symlink** 的行 → `[(行号, 行文本)]`。

    ★ 口径（写死，不许再含糊）：**该行同时含「记忆库文件名」与 `ln -`，且不是注释** ⇒ 算一条通道。
      为什么不是"含该文件名的每一行"：那会把**注释**与**只读探测**一起算进来，
      于是"通道数"这个数就不稳（本仓已因口径含糊连踩三次）。
    ⚠ `token` **由调用方从真值表传入**（不在本文件里硬编码路径）—— 这既是"单一真值"，
      也让本判据自己**不成为**记忆面接触点（否则它得把自己也登记进去）。
    """
    hits = []
    for i, ln in enumerate(text.splitlines(), 1):
        if ln.lstrip().startswith("#"):
            continue
        if token and token in ln and re.search(r"\bln\s+-", ln):
            hits.append((i, ln))
    return hits


def parse_symlink_paths(line):
    """从 symlink 行取出 `(src, tgt)` —— 取该行**最后两个**双引号串（`ln -sfn SRC TGT` 的实参）。"""
    qs = re.findall(r'"([^"]*)"', line)
    if len(qs) < 2:
        return None, None
    return qs[-2], qs[-1]


def scan_memory_touchpoints(path_tokens, bases=("ops", "tests")):
    """扫 `ops/` + `tests/` 下**可执行文件**里提到记忆路径的文件 → 相对仓库根的有序路径表。"""
    hits = []
    for base in bases:
        for p in sorted((ROOT / base).rglob("*")):
            if not p.is_file() or p.suffix.lower() not in MEMORY_CODE_EXTS:
                continue
            if any(x in p.parts for x in (".git", "__pycache__", "node_modules")):
                continue
            if any(t in _read_text(p) for t in path_tokens):
                hits.append(p.relative_to(ROOT).as_posix())
    return hits


def scan_memory_egress(files, path_tokens, carriers):
    """记忆**不得出网**：同一行同时出现【记忆路径】与【跨机搬运令牌】⇒ 命中。

    ⚠ 口径是**同一行**（不跨行）—— 局限（变量拼接/换行可逃）已登记在 yaml 的 `unverified`。
    """
    out = []
    for rel in files:
        for i, ln in enumerate(_read_text(ROOT / rel).splitlines(), 1):
            if ln.lstrip().startswith("#"):
                continue
            if any(t in ln for t in path_tokens) and any(c in ln for c in carriers):
                out.append((rel, i, ln.strip()[:160]))
    return out


def scan_isolation_by_text_prefix(marker, rel_files):
    """项目隔离**不得**以文本前缀为判据 ⇒ 在给定的**判据/测试实现**里找该标记。

    ★ 为什么要裁掉 `CHECKS` 注册表那一段：注册表里的 `fix` 是**给人读的处置说明**，
      不是判据实现 ⇒ 把它算进来会让本判据**自己触发自己**（口径错一次就永远是假红）。
      故：只扫 `CHECKS = [` 之前的**函数体**部分。
    """
    hits = []
    for rel in rel_files:
        p = ROOT / rel
        if p.is_dir():
            for f in sorted(p.glob("test_*.py")):
                t = _read_text(f)
                for i, ln in enumerate(t.splitlines(), 1):
                    if marker in ln:
                        hits.append((f.relative_to(ROOT).as_posix(), i, ln.strip()[:120]))
            continue
        t = _read_text(p)
        head = t.split("\nCHECKS = [")[0]
        for i, ln in enumerate(head.splitlines(), 1):
            if marker in ln:
                hits.append((rel, i, ln.strip()[:120]))
    return hits


def validate_memory_gates(doc, known_checks, touchpoint_hits=None):
    """**纯函数**（D7-P3-3）：四道门 + 通道 + 结构性约束的结构自洽。

    `known_checks` = 已注册的 `CHECKS` id 集合（由调用方传入；与 `validate_manual_counts` 同形）。
    ★ 传它是为了堵本仓最典型的一类假绿：**判据指向一个不存在的判据**（挂名）。
    `touchpoint_hits=None` ⇒ **不判接触点封闭集**（合成样例用）；**绝不**读成"没有接触点"。
    """
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["顶层不是映射（yaml 根应是 mapping）"], notes

    # ── ① 四道门：**缺一即红**（这就是退出判据「四门各一条判据」的机判）─────────
    gates = doc.get("gates")
    if not isinstance(gates, list) or not gates:
        bad.append("`gates` 为空 ⇒ 四道门没有对象（退化空判 = 本仓头号形态）")
        gates = []
    seen = {}
    for i, g in enumerate(gates):
        at = f"gates[{i}]"
        if not isinstance(g, dict):
            bad.append(f"{at} 不是映射")
            continue
        gid = _s(g.get("id"))
        if not gid:
            bad.append(f"{at} 缺 `id`")
        elif gid in seen:
            bad.append(f"{at} `id` 重复: {gid}")
        else:
            seen[gid] = g
            at = f"gates[{gid}]"
        if not _s(g.get("what")):
            bad.append(f"{at} 缺 `what`（这道门管什么）")
        if not _s(g.get("object")):
            bad.append(f"{at} 缺 `object`（本仓的判据对象）")
        # ★ `not_covers` **必填** —— 本仓已登记的假绿形态 = 把"部分覆盖"当"全覆盖"
        if not _s(g.get("not_covers")):
            bad.append(f"{at} 缺 `not_covers` ⇒ **没写清它不覆盖什么**（部分覆盖会被读成全覆盖）")
        j = g.get("judgment")
        if not isinstance(j, dict):
            bad.append(f"{at} 缺 `judgment` 段 ⇒ **这道门没有判据**（「没判」与「判了且通过」必须可区分）")
            continue
        kind = j.get("kind")
        if kind == "check":
            ref = _s(j.get("ref"))
            if not ref:
                bad.append(f"{at}.judgment 缺 `ref`")
            elif ref not in known_checks:
                bad.append(f"{at}.judgment.ref={ref!r} **不是已注册的 CHECKS id** ⇒ "
                           f"挂名假判（判据写了但没人跑）")
        elif kind == "na":
            if not _s(j.get("object_absent_why")):
                bad.append(f"{at}.judgment 是 `na` 但缺 `object_absent_why` ⇒ "
                           f"**「不做」也要写下来**（不适用必须给理由）")
        else:
            bad.append(f"{at}.judgment.kind={kind!r} 不在封闭集 {{check, na}} 里")
    for gid in MEMORY_GATE_IDS:
        if gid not in seen:
            bad.append(f"★ 缺一道门: {gid!r} —— D-47 要求 write/retrieval/promotion/reuse **四门齐**")
    for gid in seen:
        if gid not in MEMORY_GATE_IDS:
            bad.append(f"多出一道门 {gid!r} ⇒ 四门是**封闭集**（多出来的那门有没有判据？）")

    # ── ② 私有 → 共享的通道（"关键一跳"必须逐条写明门）──────────────────────
    bridges = doc.get("bridges")
    if not isinstance(bridges, list) or not bridges:
        bad.append("`bridges` 为空 ⇒ **关键一跳（私有→共享）没有对象**，四门里的 promotion/reuse 判不了")
        bridges = []
    ungated_engine, ungated_ours = [], []
    seen_b = set()
    for i, b in enumerate(bridges):
        at = f"bridges[{i}]"
        if not isinstance(b, dict):
            bad.append(f"{at} 不是映射")
            continue
        bid = _s(b.get("id"))
        if not bid or bid in seen_b:
            bad.append(f"{at} 缺 `id` 或 `id` 重复: {bid!r}")
        seen_b.add(bid)
        at = f"bridges[{bid or i}]"
        for k in ("channel", "why", "evidence"):
            if not _s(b.get(k)):
                bad.append(f"{at} 缺 `{k}`")
        if not isinstance(b.get("isolated"), bool):
            bad.append(f"{at} `isolated` 必须是布尔（「是否按项目/任务隔离」是**实测口径**，不是形容词）")
        if not isinstance(b.get("controllable_by_us"), bool):
            bad.append(f"{at} `controllable_by_us` 必须是布尔（决定这条通道该红还是该点名）")
        gate = b.get("gate")
        if gate == "none":
            if b.get("controllable_by_us") is True:
                ungated_ours.append(bid)
                bad.append(f"{at} ★ `gate: none` 且**本仓可控** ⇒ **红**：本仓能关却不关，"
                           f"正是 MAPLE-Guard 说的「关键一跳」敞着")
            else:
                ungated_engine.append(bid)
        elif gate == "by-design-shared":
            # "刻意共享"与"忘了关门"必须可区分 ⇒ 刻意共享要**给出理由**
            if not _s(b.get("why")):
                bad.append(f"{at} `gate: by-design-shared` 但 `why` 为空 ⇒ 与 `none` 无法区分")
        elif gate == "cwd-keyed":
            if not _s(b.get("key")):
                bad.append(f"{at} `gate: cwd-keyed` 但没写 `key`（按什么键控隔离？没键就不叫键控）")
        else:
            bad.append(f"{at} `gate`={gate!r} 不在封闭集 {{cwd-keyed, by-design-shared, none}} 里")

    # ── ③ 结构性约束：**每条必须有判据**（没判据的还只是纪律）────────────────
    scs = doc.get("structural_constraints")
    if not isinstance(scs, list) or not scs:
        bad.append("`structural_constraints` 为空 ⇒ **授权边界没有写成结构性约束**（D-48 的核心要求）")
        scs = []
    seen_sc = set()
    for i, s in enumerate(scs):
        at = f"structural_constraints[{i}]"
        if not isinstance(s, dict):
            bad.append(f"{at} 不是映射")
            continue
        sid = _s(s.get("id"))
        if not sid or sid in seen_sc:
            bad.append(f"{at} 缺 `id` 或 `id` 重复: {sid!r}")
        seen_sc.add(sid)
        at = f"structural_constraints[{sid or i}]"
        if not _s(s.get("rule")):
            bad.append(f"{at} 缺 `rule`")
        if not _s(s.get("why_structural")):
            bad.append(f"{at} 缺 `why_structural` ⇒ 没说明**为什么它是结构而不是「指望写清楚」**")
        jb = _s(s.get("judged_by"))
        if jb == "NA_UNIT":
            bad.append(f"{at} `judged_by: NA_UNIT` ⇒ **它就不是结构性约束** ⇒ "
                       f"请移到 `known_non_structural` 段并说明为什么"
                       f"（两段混用 = 把两件事说成一件，本仓头号形态）")
        elif jb not in known_checks:
            bad.append(f"{at} `judged_by`={jb!r} 不是已注册的 CHECKS id ⇒ "
                       f"**没判据的约束仍只是纪律**（「写成结构性约束」的含义就是有判据）")

    # ── ③b 如实登记：**今天还不是**结构性约束的授权边界（两段**不得混用**）────────
    kns = doc.get("known_non_structural")
    if not isinstance(kns, list) or not kns:
        bad.append("`known_non_structural` 为空 ⇒ 「今天还不是结构性约束」的边界没有登记"
                   "（「不是结构」这件事也必须写下来）")
        kns = []
    for i, k in enumerate(kns):
        at = f"known_non_structural[{i}]"
        if not isinstance(k, dict):
            bad.append(f"{at} 不是映射")
            continue
        kid = _s(k.get("id"))
        at = f"known_non_structural[{kid or i}]"
        for fld in ("rule", "today", "why_not_structural", "object_absent_why"):
            if not _s(k.get(fld)):
                bad.append(f"{at} 缺 `{fld}`")
        if kid and kid in seen_sc:
            bad.append(f"{at} 与 `structural_constraints` **出现同一个 id** {kid!r} ⇒ "
                       f"同一条边界被同时说成「是结构」和「不是结构」")

    # ── ④ 接触点封闭集（`None` ⇒ **不判**，而不是判过）──────────────────────
    tps = doc.get("touchpoints")
    if not isinstance(tps, list) or not tps:
        bad.append("`touchpoints` 为空 ⇒ 「记忆面接触点」没有封闭集 ⇒ 新开一条通道不会被发现")
        tps = []
    reg = []
    for i, t in enumerate(tps):
        if not isinstance(t, dict) or not _s(t.get("file")):
            bad.append(f"touchpoints[{i}] 缺 `file`")
            continue
        if not _s(t.get("why")):
            bad.append(f"touchpoints[{i}]({_s(t.get('file'))}) 缺 `why`")
        if not isinstance(t.get("egress"), bool):
            bad.append(f"touchpoints[{i}]({_s(t.get('file'))}) 的 `egress` 必须是布尔")
        reg.append(_s(t.get("file")))
    if touchpoint_hits is not None:
        for h in touchpoint_hits:
            if h not in reg:
                bad.append(f"★**未登记的记忆面接触点**: {h} ⇒ 要么登记进 `touchpoints`（含理由），"
                           f"要么把记忆路径从该文件里去掉")
        # ⚠「登记的接触点不存在」**不在这里判** —— 那是**盘上存在性**，属 `check_memory_gates`
        #   （本函数是纯函数：纯函数不碰盘）。放这儿会让合成样例悄悄跳过它。

    # ── ⑤ 出网口径 / 前缀口径 必填 ─────────────────────────────────────────
    eg = doc.get("egress")
    if not isinstance(eg, dict):
        bad.append("缺 `egress` 段 ⇒ 记忆「不得出网」没有口径")
    else:
        ptk = eg.get("path_tokens")
        if not isinstance(ptk, dict) or not ptk or not all(_s(v) for v in ptk.values()):
            bad.append("`egress.path_tokens` 必须是非空映射、且值非空 —— 角色名就是用途，"
                       "**不靠顺序**（顺序口径本仓已吃过亏）")
        if not [x for x in (eg.get("carrier_tokens") or []) if _s(x)]:
            bad.append("`egress.carrier_tokens` 为空 ⇒ 不知道什么算「跨机搬运」")
    tp = doc.get("text_prefix")
    if not isinstance(tp, dict) or not _s(tp.get("marker")) \
            or not [x for x in (tp.get("forbidden_in") or []) if _s(x)]:
        bad.append("`text_prefix` 段缺 `marker` / `forbidden_in`（缺席判据要点名它扫哪里）")

    unv = doc.get("unverified")
    if not isinstance(unv, list) or not unv:
        bad.append("`unverified` 为空 ⇒ 本项自己未实测 / 未定的部分没登记")

    if not bad:
        n_na = sum(1 for g in seen.values()
                   if isinstance(g.get("judgment"), dict) and g["judgment"].get("kind") == "na")
        notes.append(f"四门齐（{len(seen)}/4，其中判据 NA {n_na} 道）· 通道 {len(bridges)} 条 · "
                     f"结构性约束 {len(scs)} 条 · 非结构性（如实登记）{len(kns)} 条 · 接触点 {len(reg)} 个")
        notes.append(f"无门通道：本仓可控 {len(ungated_ours)} 条 / 引擎侧 {len(ungated_engine)} 条"
                     f"{'（点名: ' + ', '.join(ungated_engine) + '）' if ungated_engine else ''}")
        if touchpoint_hits is None:
            notes.append("接触点扫描：**未接扫描输入（不判，不算通过）**")
        else:
            notes.append(f"接触点扫描命中 {len(touchpoint_hits)} 个文件 · 全部已登记")
    return bad, notes


def check_memory_gates(ctx, doc=None):
    """D7-P3-3: 记忆四道门 + 授权边界（结构性约束）+ 接触点封闭集 + 不得出网。

    ★ `doc` 是可注入缝（测试用）：`None` ⇒ 从 `inventory/memory-gates.yaml` 读。
      为什么需要它：「**登记的接触点不存在**」与「备份落点」这类判断要吃**盘上实况**，
      而 `validate_memory_gates` 是纯函数 —— 没有这个缝，那两条只能靠合成样例"假装验过"。
    """
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 memory-gates 断言", []
    if doc is None:
        if not MEMORY_GATES_INV.exists():
            return "FAIL", "inventory/memory-gates.yaml 缺失（本断言的登记依据）", []
        try:
            doc = yaml.safe_load(_read_text(MEMORY_GATES_INV)) or {}
        except Exception as e:
            return "FAIL", f"inventory/memory-gates.yaml 解析失败: {type(e).__name__}: {e}", []

    # 0) 记忆路径的**唯一字面定义点**在真值表里 ⇒ 本文件**不硬编码**它们
    eg = doc.get("egress") if isinstance(doc.get("egress"), dict) else {}
    ptk = eg.get("path_tokens") if isinstance(eg.get("path_tokens"), dict) else {}
    ptokens = [v for v in ptk.values() if _s(v)]
    db_token = _s(ptk.get("db"))
    if not db_token:
        return "FAIL", "`egress.path_tokens.db` 缺失 ⇒ SC-1（记忆库 symlink）不可判；**不可判 ≠ 通过**", []

    # 1) 记忆面：接触点扫盘（扫不到 ≠ 通过 ⇒ 异常要报出来）
    try:
        tp_hits = scan_memory_touchpoints(ptokens)
    except Exception as e:
        return "FAIL", f"接触点扫描失败（不可判 ⇒ 不许当通过）: {type(e).__name__}: {e}", []

    bad, notes = validate_memory_gates(doc, known_checks={c["id"] for c in CHECKS},
                                      touchpoint_hits=tp_hits)
    # 1b) **盘上存在性**：登记的接触点必须真在（纯函数判不了这条 —— 它要碰盘）
    for t in (doc.get("touchpoints") or []):
        if isinstance(t, dict) and _s(t.get("file")) and not (ROOT / _s(t["file"])).exists():
            bad.append(f"登记的接触点不存在: {_s(t['file'])} ⇒ "
                       f"登记腐化（文件被删 / 改名 / 换机器）")

    # 2) SC-1：`agent-cli.ps1` 里**恰好一条**记忆库 symlink，且源必须在站级 $HOME 下
    if AGENT_CLI.exists():
        syms = extract_memory_symlinks(_read_text(AGENT_CLI), db_token)
        if len(syms) != 1:
            bad.append(f"★ 记忆面 symlink 实测 **{len(syms)} 处**（要求恰 1 处）⇒ "
                       f"共享面被扩容或判据没对象；行号 {[n for n, _ in syms]}")
        else:
            ln_no, ln_txt = syms[0]
            src, tgt = parse_symlink_paths(ln_txt)
            plane = doc.get("memory_plane") or {}
            guard = doc.get("plane_guard") or {}
            ok_pre = [p for p in (guard.get("allowed_source_prefixes") or []) if src and src.startswith(p)]
            forbid = [m for m in (guard.get("forbidden_source_markers") or []) if src and m in src]
            ok_suf = tgt and _s(guard.get("allowed_target_suffix")) and tgt.endswith(_s(guard["allowed_target_suffix"]))
            if not ok_pre:
                bad.append(f"{AGENT_CLI.name}:{ln_no} symlink 源 {src!r} 不在允许前缀 "
                           f"{guard.get('allowed_source_prefixes')} 里 ⇒ 共享面可能被指到工作区/项目目录")
            if forbid:
                bad.append(f"{AGENT_CLI.name}:{ln_no} symlink 源含禁止标记 {forbid} ⇒ "
                           f"记忆被搬进项目目录（= 把项目记忆写进共享层）")
            if not ok_suf:
                bad.append(f"{AGENT_CLI.name}:{ln_no} symlink 目标 {tgt!r} 不以 "
                           f"{guard.get('allowed_target_suffix')!r} 结尾")
            if not isinstance(plane.get("scope"), str) or not _s(plane.get("scope")):
                bad.append("`memory_plane.scope` 为空 ⇒ 记忆面的**共享面**没写下来")
            if not _s(plane.get("scope_evidence")):
                bad.append("`memory_plane.scope_evidence` 为空 ⇒ 共享面的**出处**没写（实测还是推断？）")
    else:
        bad.append("缺 agent-cli.ps1 ⇒ SC-1（记忆面路径常量）不可判；**不可判 ≠ 通过**")

    # 3) SC-2：记忆不得出网（同一行同现）+ 备份只落**站内** $HOME
    carriers = [t for t in (eg.get("carrier_tokens") or []) if _s(t)]
    eg_hits = scan_memory_egress(tp_hits, ptokens, carriers)
    for rel, ln_no, txt in eg_hits:
        bad.append(f"★ 记忆**出网**嫌疑: {rel}:{ln_no} ⇒ `{txt}`（同一行同现记忆路径与跨机搬运）")
    bscript = _s(eg.get("backup_script"))
    if bscript:
        if not (ROOT / bscript).exists():
            bad.append(f"`egress.backup_script` 指向的 {bscript} 不存在 ⇒ 登记腐化")
        else:
            var = _s(eg.get("backup_dir_var"))
            prefs = tuple(_s(x) for x in (eg.get("backup_dir_prefixes") or []) if _s(x))
            vals = [ln.split(var, 1)[1].strip() for ln in _read_text(ROOT / bscript).splitlines()
                    if ln.startswith(var) and not ln.lstrip().startswith("#")]
            if not vals:
                bad.append(f"{bscript} 找不到 `{var}` 赋值 ⇒ 备份落点不可判（不可判 ≠ 通过）")
            elif not any(v.startswith(prefs) for v in vals):
                bad.append(f"{bscript} 的 `{var}`={vals[0]!r} 不在站内前缀 {prefs} 里 ⇒ "
                           f"备份可能落到站外（记忆出网）")

    # 4) SC-3：项目隔离**不得**以文本前缀为判据（缺席判据）
    tp = doc.get("text_prefix") or {}
    marker = _s(tp.get("marker"))
    if marker:
        pref_hits = scan_isolation_by_text_prefix(marker, [x for x in (tp.get("forbidden_in") or []) if _s(x)])
        for rel, ln_no, txt in pref_hits:
            bad.append(f"★ 隔离**靠文本前缀**: {rel}:{ln_no} ⇒ `{txt}` —— "
                       f"把命名当边界（D-48：要靠结构 contain，不是「指望写清楚」）")

    if bad:
        return "FAIL", " · ".join(notes) if notes else "见明细", bad
    eng = [_s(b.get("id")) for b in (doc.get("bridges") or [])
           if isinstance(b, dict) and b.get("gate") == "none"]
    if eng:
        # 引擎侧无门通道：**点名 + WARN**（本仓关不了；但绝不静默 —— 明细里必须**逐个报名字**，
        #   ★ 只说"见 yaml"不算点名：那等于让读者自己去猜是哪一条）
        return "WARN", " · ".join(notes), [
            f"引擎侧无门通道 {len(eng)} 条（本仓关不了 ⇒ 只登记 + 点名）: " + ", ".join(eng)]
    return "PASS", " · ".join(notes), []


# ── D7-P4-1 (2026-09-26)「多轮闭环 + **轮数上限有判据**」────────────────────────
#   退出判据原文 = 「多轮闭环可跑；**轮数上限有判据**」。
#   ★ 先去找对象（本会话第四次）：受理侧**早就有**一个协商回环（`plan-review ⇄ plan-revise`，
#     路线总表 §11.2(a) 已实测标注「**已有原型 ⇒ 复用状态语义，而非另建**」）
#     ⇒ 本项不是"造多轮引擎"，而是**把本仓真实存在的闭环逐条钉住上限与终止条件**。
#   ★★ 本批实测抓到的真缺陷：**注释里的上限落后于代码** —— `agent-cli.ps1` 里**两处**
#     写 `retry <=2`，而代码分别是 `-lt 3` 与 `-le 3`（O-46 改 cap 时注释没跟）。
#     ⇒ 故本判据专门有 **`prose_caps` 封闭集**：散文里的上限必须逐处登记且与代码一致。
MULTI_ROUND_INV = ROOT / "inventory" / "multi-round.yaml"
LOOP_KINDS = ("advance", "retry")
LOOP_CAP_STATES = ("capped", "unbounded-by-design", "undecided")
ROUND_COUNTER_KINDS = ("file-glob", "shell-var", "state-log")
# 超限处置：**封闭枚举**（★ 刻意不是"扫散文里有没有『继续』" —— 那是文本口径，
#   实测会假红：`"超限 ⇒ 升级（不是继续）"` 里含「继续」就被判红）。
ON_EXCEED_KINDS = ("escalate", "terminate", "fail-record", "undecided")
CODE_CAP_RE = re.compile(r"-(?:lt|le)\s+(\d+)")


def extract_loop_cap(text, marker, op):
    """从目标文件里**实提取**循环上限：形如 `<marker> … <op> N` → `[(行号, N)]`。

    ★ 口径（**双锚**，写死）：**同一行**里既含 `marker` 又含 `<op> N`，且不是注释。
      为什么要双锚：只按 marker 找会把 `CONT_ATTEMPT=0` 这种**赋值行**也算进来
      —— 那正是"口径没定就量"的老毛病（本仓已连踩三次）。
    """
    rx = re.compile(re.escape(op) + r"\s+(\d+)")
    hits = []
    for i, ln in enumerate(text.splitlines(), 1):
        if ln.lstrip().startswith("#"):
            continue
        if marker in ln:
            m = rx.search(ln)
            if m:
                hits.append((i, int(m.group(1))))
    return hits


def scan_prose_caps(text, words):
    """扫**散文里的上限**：`<词> <= N`（口径写死：词集封闭 + 允许空格）→ `[(行号, N, 行)]`。"""
    out = []
    for i, ln in enumerate(text.splitlines(), 1):
        for w in words:
            m = re.search(re.escape(w) + r"\s*<=\s*(\d+)", ln)
            if m:
                out.append((i, int(m.group(1)), ln.strip()))
                break
    return out


def validate_multi_round(doc):
    """**纯函数**（D7-P4-1）：多轮闭环的结构自洽（轮次可数 · 上限或理由 · 正向终止 · 超限处置）。"""
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["顶层不是映射（yaml 根应是 mapping）"], notes

    loops = doc.get("loops")
    if not isinstance(loops, list) or not loops:
        bad.append("`loops` 为空 ⇒ 多轮闭环没有对象（退化空判 = 本仓头号形态）")
        loops = []
    seen, undecided = {}, []
    for i, lp in enumerate(loops):
        at = f"loops[{i}]"
        if not isinstance(lp, dict):
            bad.append(f"{at} 不是映射")
            continue
        lid = _s(lp.get("id"))
        if not lid or lid in seen:
            bad.append(f"{at} 缺 `id` 或 `id` 重复: {lid!r}")
        seen[lid or i] = lp
        at = f"loops[{lid or i}]"
        for k in ("what", "carrier", "evidence", "delta", "delta_note", "on_exceed"):
            if not _s(lp.get(k)):
                bad.append(f"{at} 缺 `{k}`")
        if lp.get("kind") not in LOOP_KINDS:
            bad.append(f"{at} `kind`={lp.get('kind')!r} 不在封闭集 {LOOP_KINDS} —— "
                       f"**状态推进型**与**同一步重试型**必须分开标（否则就是把两件事说成一件）")
        # ── 轮次**可数** ────────────────────────────────────────────────
        rc = lp.get("round_counter")
        if not isinstance(rc, dict):
            bad.append(f"{at} 缺 `round_counter` ⇒ **轮次从哪来**没写 ⇒ 上限无法核")
        else:
            if rc.get("kind") not in ROUND_COUNTER_KINDS:
                bad.append(f"{at}.round_counter.kind={rc.get('kind')!r} 不在封闭集 {ROUND_COUNTER_KINDS}")
            if not _s(rc.get("how")):
                bad.append(f"{at}.round_counter 缺 `how`（怎么数）")
            if rc.get("kind") == "file-glob" and not _s(rc.get("glob")):
                bad.append(f"{at}.round_counter 是 `file-glob` 但没给 `glob`")
            if rc.get("kind") == "shell-var" and not _s(rc.get("var")):
                bad.append(f"{at}.round_counter 是 `shell-var` 但没给 `var`")
        # ── 上限：**要么给数、要么给理由、要么点名待裁**（三条都不许空）────
        cs = lp.get("cap_state")
        if cs == "capped":
            mr = lp.get("max_rounds")
            if not isinstance(mr, int) or isinstance(mr, bool) or mr < 1:
                bad.append(f"{at} `cap_state: capped` 但 `max_rounds`={mr!r} 不是正整数")
        elif cs == "unbounded-by-design":
            if not _s(lp.get("unbounded_reason")):
                bad.append(f"{at} `cap_state: unbounded-by-design` 但缺 `unbounded_reason` ⇒ "
                           f"**「没有上限」必须给理由**（否则与「忘了写」无法区分）")
        elif cs == "undecided":
            if not _s(lp.get("needs_decision_by")):
                bad.append(f"{at} `cap_state: undecided` 但缺 `needs_decision_by` ⇒ "
                           f"**未定也要写清等谁裁**（点名，不许静默）")
            else:
                undecided.append(lid)
        else:
            bad.append(f"{at} `cap_state`={cs!r} 不在封闭集 {LOOP_CAP_STATES} ⇒ "
                       f"**漏写上限**是本项最要防的形态（上限/理由/待裁三者必须显式其一）")
        # ── EASE 式**正向终止**（"一致即停"）────────────────────────────
        if not _s(lp.get("stop_on_agreement")):
            bad.append(f"{at} 缺 `stop_on_agreement` ⇒ **正向终止条件**没写明 —— "
                       f"上限只管「最多几轮」，「什么时候**可以停**」是另一半（EASE 早停）")
        if not isinstance(lp.get("stop_on_agreement_machine_readable"), bool):
            bad.append(f"{at} `stop_on_agreement_machine_readable` 必须是布尔 "
                       f"（它是人判还是可机判，是 EASE 能不能自动早停的前提）")
        # ── 超限处置：**结构化**地声明"超限时发生什么" ───────────────────
        # ★★ 第一版这里是**文本禁令**（"不得出现『继续』"）⇒ 实测**当场假红**：
        #    `on_exceed: "超限 ⇒ 升级（不是继续）"` 里含「继续」就被判红。
        #    —— 又是"文本口径造假阳性"（本仓已因口径吃过多次亏）。
        #    ⇒ 改为**封闭枚举**：作者必须声明**处置的种类**，机器不猜措辞。
        oek = lp.get("on_exceed_kind")
        if oek not in ON_EXCEED_KINDS:
            bad.append(f"{at} `on_exceed_kind`={oek!r} 不在封闭集 {ON_EXCEED_KINDS} ⇒ "
                       f"**超限时发生什么**必须是一个可枚举的动作（不是一段散文）")
        elif cs == "capped" and oek == "undecided":
            bad.append(f"{at} 已有上限（`cap_state: capped`）却把 `on_exceed_kind` 留成 `undecided` ⇒ "
                       f"**上限没说清超限怎么办 = 上限只有一半**")

    # ── 散文上限：**封闭集**（本批实测抓到的真实缺陷形态）──────────────────
    pw = [_s(w) for w in (doc.get("prose_words") or []) if _s(w)]
    if not pw:
        bad.append("`prose_words` 为空 ⇒ 散文上限没有扫描口径（口径不先定就量 = 本仓吃过三次亏）")
    pcs = doc.get("prose_caps")
    if not isinstance(pcs, list) or not pcs:
        bad.append("`prose_caps` 为空 ⇒ **注释里的上限没人管** —— "
                   "实测它就会落后于代码（本批两处都写 2 而代码是 3）")
        pcs = []
    for i, p in enumerate(pcs):
        at = f"prose_caps[{i}]"
        if not isinstance(p, dict):
            bad.append(f"{at} 不是映射")
            continue
        f_, tok = _s(p.get("file")), _s(p.get("line_token"))
        at = f"prose_caps[{f_}:{tok or i}]"
        for k in ("file", "line_token", "why"):
            if not _s(p.get(k)):
                bad.append(f"{at} 缺 `{k}`")
        if not isinstance(p.get("expect"), int) or isinstance(p.get("expect"), bool):
            bad.append(f"{at} 的 `expect` 必须是整数（散文里应当写的那个数）")

    unv = doc.get("unverified")
    if not isinstance(unv, list) or not unv:
        bad.append("`unverified` 为空 ⇒ 本项自己未实测 / 未定的部分没登记")

    if not bad:
        n_cap = sum(1 for v in seen.values() if v.get("cap_state") == "capped")
        n_unb = sum(1 for v in seen.values() if v.get("cap_state") == "unbounded-by-design")
        kinds = sorted({_s(v.get("kind")) for v in seen.values()})
        notes.append(f"闭环 {len(seen)} 条 · kind {kinds} · 有上限 {n_cap} · 无上限(有理由) {n_unb} · "
                     f"**未定 {len(undecided)}**"
                     f"{'（点名: ' + ', '.join(undecided) + '）' if undecided else ''} · "
                     f"散文上限登记 {len(pcs)} 处（词集 {pw}）")
    return bad, notes


def check_multi_round(ctx, doc=None):
    """D7-P4-1: 多轮闭环 —— **轮数上限有判据**（含与代码**实提取**对账 + 散文上限封闭集）。

    ★ `doc` 是可注入缝（测试用）：`None` ⇒ 从 `inventory/multi-round.yaml` 读。
    """
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 multi-round 断言", []
    if doc is None:
        if not MULTI_ROUND_INV.exists():
            return "FAIL", "inventory/multi-round.yaml 缺失（本断言的登记依据）", []
        try:
            doc = yaml.safe_load(_read_text(MULTI_ROUND_INV)) or {}
        except Exception as e:
            return "FAIL", f"inventory/multi-round.yaml 解析失败: {type(e).__name__}: {e}", []

    bad, notes = validate_multi_round(doc)
    cache = {}

    def _text(rel):
        if rel not in cache:
            cache[rel] = _read_text(ROOT / rel)
        return cache[rel]

    # 1) ★★ 与**代码实提取**对账：每个 `cap_sites` 都要实测到**恰一处**上限；
    #    **各 site 必须同值**；且 `max_rounds == 该值 + plus_extra 之和`。
    #    ★ 为什么是**复数** site：本条闭环有**两份实现**（站上 bash body + 本地 PS）——
    #      那正是"同一事实两个定义点"最容易漂的地方（本批实测的注释漂移就发生在旁边）。
    for lp in (doc.get("loops") or []):
        if not isinstance(lp, dict):
            continue
        lid = _s(lp.get("id")) or "?"
        sites = [x for x in (lp.get("cap_sites") or []) if isinstance(x, dict)]
        if not sites:
            continue                      # 无代码侧实现（如受理侧回环）⇒ 不对账；**不是"通过"**
        caps = []
        for s in sites:
            rel = _s(s.get("file"))
            where = _s(s.get("where"))
            if not where:
                bad.append(f"loops[{lid}].cap_sites 有一条缺 `where` ⇒ 两个定义点必须可区分")
                where = "?"
            if not rel or not (ROOT / rel).exists():
                bad.append(f"loops[{lid}].cap_sites 的 file={rel!r} 不存在 ⇒ "
                           f"对账不可判（**不可判 ≠ 通过**）")
                continue
            hits = extract_loop_cap(_text(rel), _s(s.get("marker")), _s(s.get("op")))
            if len(hits) != 1:
                bad.append(f"loops[{lid}] 的 site({where})：在 {rel} 按锚点 "
                           f"({s.get('marker')!r}, {s.get('op')!r}) 实测到 **{len(hits)} 处**上限"
                           f"（要求恰 1 处）⇒ 要么上限多了个定义点、要么口径过期；"
                           f"行号 {[n for n, _ in hits]}")
                continue
            caps.append((where, hits[0][0], hits[0][1]))
        if not caps:
            continue
        if len({v for _, _, v in caps}) > 1:
            bad.append(f"loops[{lid}] **多处实现的上限不一致**: "
                       + " / ".join(f"{w}@{ln}={v}" for w, ln, v in caps)
                       + " ⇒ 同一事实两个定义点，必须同步（或合并为一处）")
            continue
        rel0 = _s(sites[0].get("file"))
        n_extra = 0
        for x in [y for y in (lp.get("plus_extra") or []) if isinstance(y, dict)]:
            anc, cnt = _s(x.get("anchor")), x.get("count")
            if not anc or not isinstance(cnt, int) or isinstance(cnt, bool):
                bad.append(f"loops[{lid}].plus_extra 缺 `anchor` 或 `count` 非整数")
                continue
            if anc not in _text(rel0):
                bad.append(f"loops[{lid}].plus_extra 的锚点 {anc!r} 在 {rel0} 里**找不到** ⇒ "
                           f"登记腐化（那段代码改了 / 删了）")
                continue
            n_extra += cnt
        code_cap = caps[0][2]
        want = code_cap + n_extra
        if isinstance(lp.get("max_rounds"), int) and lp.get("max_rounds") != want:
            bad.append(f"loops[{lid}] 的 `max_rounds`={lp.get('max_rounds')} 与代码**不符**："
                       f"实测循环上限 {code_cap}"
                       f"{f' + plus_extra {n_extra}' if n_extra else ''} = {want} ⇒ "
                       f"改真值表**或**改代码（两处必须同时说同一个数）")

    # 2) ★★ 散文上限：逐处核 + **完整性**（文件里每一处都要被登记）
    pw = [_s(w) for w in (doc.get("prose_words") or []) if _s(w)]
    pcs = [p for p in (doc.get("prose_caps") or []) if isinstance(p, dict)]
    for rel in sorted({_s(p.get("file")) for p in pcs if _s(p.get("file"))}):
        if not (ROOT / rel).exists():
            bad.append(f"prose_caps 指向的 {rel} 不存在 ⇒ 登记腐化")
            continue
        t = _text(rel)
        caps_all = {int(x) for x in CODE_CAP_RE.findall(t)}
        found = scan_prose_caps(t, pw)
        for ln_no, val, txt in found:
            covered = [p for p in pcs if _s(p.get("line_token")) and _s(p.get("line_token")) in txt]
            if not covered:
                bad.append(f"★**未登记的散文上限**: {rel}:{ln_no} ⇒ `{txt[:100]}` —— "
                           f"散文里的上限**逐处登记**，否则它会悄悄落后于代码")
        for p in pcs:
            if _s(p.get("file")) != rel:
                continue
            tok = _s(p.get("line_token"))
            lines = [(i, l) for i, l in enumerate(t.splitlines(), 1) if tok in l]
            if not lines:
                bad.append(f"prose_caps 登记的锚 {tok!r} 在 {rel} 里**找不到** ⇒ 口径过期（代码改了？）")
                continue
            if len(lines) > 1:
                bad.append(f"prose_caps 的锚 {tok!r} 在 {rel} 里命中 {len(lines)} 行 ⇒ 锚不唯一")
                continue
            ln_no, txt = lines[0]
            vals = [re.search(re.escape(w) + r"\s*<=\s*(\d+)", txt) for w in pw]
            got = next((int(m.group(1)) for m in vals if m), None)
            if got is None:
                bad.append(f"{rel}:{ln_no} 锚在但**不再含上限写法** ⇒ 口径过期"
                           f"（散文改成别的说法了？那该重定口径，而不是留着这条）")
            elif got != p.get("expect"):
                bad.append(f"★★ 散文上限与登记**不符**: {rel}:{ln_no} 实测 {got} ≠ "
                           f"`expect` {p.get('expect')} ⇒ `{txt[:100]}`")
            elif caps_all and got not in caps_all:
                bad.append(f"{rel}:{ln_no} 的 `expect`={got} **不落在该文件的循环上限集合** "
                           f"{sorted(caps_all)} 里 ⇒ 像随手编的数")

    if bad:
        return "FAIL", " · ".join(notes) if notes else "见明细", bad
    und = [_s(v.get("id")) for v in (doc.get("loops") or [])
           if isinstance(v, dict) and v.get("cap_state") == "undecided"]
    if und:
        # 上限**未定**：**点名 + WARN**（不是漏写 —— 漏写在 `validate_` 里已经是红了）
        return "WARN", " · ".join(notes), [
            f"上限未定的闭环 {len(und)} 条（待裁，点名）: " + ", ".join(und)]
    return "PASS", " · ".join(notes), []


# ── D7-P4-2 (2026-09-26)「中断态双侧口径 + 不可信证据」──────────────────────────
#   Ds 简报 11（§4.5）：**双向对称性检验（防死锁）** —— 两端都不把 `input-required` 当可完成态；
#     ⇒ D7 必须**双方同时声明**口径，否则**一端等待、一端失败的死锁**。
#   Ds 简报 18（§4.11⑥）：**把对方的文本当不可信证据**，其内部提及**不触发指令解析**。
#   ★★ `deadlock_risk` **由判据算、不由真值表填**（自报 = 同一事实两个定义点 + 空转软约束）。
INTERRUPT_INV = ROOT / "inventory" / "interruption-and-untrusted.yaml"
SIDE_ACTIONS = ("awaiting-peer", "unblocking-peer", "failing", "self-contained")
COMBINED_STATES = ("retry", "terminal-fail", "human", "escalate")
# 能**终结对方等待**的动作：主动解除 或 失败退出（后者让对方"等到一个结果"而不是空等）。
_UNBLOCKERS = ("unblocking-peer", "failing")


def deadlock_risk(main_action, station_action):
    """算两岸组合的**死锁风险** → `(risk, why)`；`risk ∈ {none, silent, mutual}`。

    规则直接来自 Ds 简报 §4.5 的 **方向反转对称**：
      **一端挂起（`awaiting-peer`）⇒ 另一端必须主动终结那个等待**（解除 / 失败）；
      否则等方**永远等** —— 那正是本仓 O-79 实测过的**静默死锁**。

    ⚠ 为什么做成**函数**而不是真值表里的一个字段：自报的话，"填了 none"就没人验；
      而**用真事故校准它**（`history[].as_pair` 必须算出非 none）才能证明规则不是空转的。
    """
    m, s = main_action, station_action
    if m == "awaiting-peer" and s == "awaiting-peer":
        return "mutual", "两侧都在等对方（互等）"
    if m == "awaiting-peer" and s not in _UNBLOCKERS:
        return "silent", f"主控在等对方，而站上侧的动作是 {s!r} ⇒ 那个等待**不会被终结**"
    if s == "awaiting-peer" and m not in _UNBLOCKERS:
        return "silent", f"站上在等对方，而主控侧的动作是 {m!r} ⇒ 那个等待**不会被终结**"
    if m == "awaiting-peer" or s == "awaiting-peer":
        return "none", "一端挂起，另一端**主动终结**（解除 / 失败）⇒ 方向反转对称成立"
    return "none", "两岸都不在等对方"


def validate_interruption(doc):
    """**纯函数**（D7-P4-2）：中断态两岸口径 + 不可信输入的结构自洽。"""
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["顶层不是映射（yaml 根应是 mapping）"], notes

    ips = doc.get("interruptions")
    if not isinstance(ips, list) or not ips:
        bad.append("`interruptions` 为空 ⇒ 中断态没有对象（退化空判 = 本仓头号形态）")
        ips = []
    seen, risky = set(), []
    for i, it in enumerate(ips):
        at = f"interruptions[{i}]"
        if not isinstance(it, dict):
            bad.append(f"{at} 不是映射")
            continue
        iid = _s(it.get("id"))
        if not iid or iid in seen:
            bad.append(f"{at} 缺 `id` 或 `id` 重复: {iid!r}")
        seen.add(iid)
        at = f"interruptions[{iid or i}]"
        # ★★「**两侧**都要声明」—— 缺一侧就是 Ds 说的"一端没写"
        for k in ("what", "main_side", "station_side", "evidence"):
            if not _s(it.get(k)):
                bad.append(f"{at} 缺 `{k}` ⇒ "
                           + ("**只有一端声明了口径**（Ds：一端等待、一端失败的死锁就出在这里）"
                              if k in ("main_side", "station_side") else "字段没写"))
        ma, sa = it.get("main_action"), it.get("station_action")
        for nm, v in (("main_action", ma), ("station_action", sa)):
            if v not in SIDE_ACTIONS:
                bad.append(f"{at} `{nm}`={v!r} 不在封闭集 {SIDE_ACTIONS} ⇒ "
                           f"**谁在等谁**无法判 ⇒ 死锁风险也就判不了")
        if it.get("combined") not in COMBINED_STATES:
            bad.append(f"{at} `combined`={it.get('combined')!r} 不在封闭集 {COMBINED_STATES}")
        if ma in SIDE_ACTIONS and sa in SIDE_ACTIONS:
            risk, why = deadlock_risk(ma, sa)
            if risk != "none":
                if not _s(it.get("mitigation")):
                    bad.append(f"{at} 判出死锁风险 **{risk}**（{why}）却**没有 `mitigation`** ⇒ "
                               f"没人管这个等待怎么被终结")
                else:
                    risky.append((iid, risk))

    # ── ★ 用**真事故**校准规则：历史死锁必须能被算出来 ──────────────────────
    hist = doc.get("history")
    if not isinstance(hist, list) or not hist:
        bad.append("`history` 为空 ⇒ **修掉的静默死锁没登记** ⇒ 它会回来（且没人知道当初为什么改）")
        hist = []
    for i, h in enumerate(hist):
        at = f"history[{i}]"
        if not isinstance(h, dict):
            bad.append(f"{at} 不是映射")
            continue
        hid = _s(h.get("id"))
        at = f"history[{hid or i}]"
        for k in ("symptom", "root_cause", "fix", "evidence"):
            if not _s(h.get(k)):
                bad.append(f"{at} 缺 `{k}`")
        pair = h.get("as_pair")
        if not isinstance(pair, dict) or pair.get("main_action") not in SIDE_ACTIONS \
                or pair.get("station_action") not in SIDE_ACTIONS:
            bad.append(f"{at} `as_pair` 必须给两侧动作（∈ 封闭集）—— "
                       f"它是**校准/先验红**：真事故必须能被 `deadlock_risk()` 算出来")
        else:
            got, why = deadlock_risk(pair["main_action"], pair["station_action"])
            exp = h.get("expected_risk")
            if exp not in ("silent", "mutual"):
                bad.append(f"{at} `expected_risk`={exp!r} 必须是 silent / mutual "
                           f"（历史死锁若算成 none，那它就不是死锁）")
            elif got != exp:
                bad.append(f"{at} ★★ **规则算不出这条真事故**：实测 {got!r} ≠ `expected_risk` {exp!r}"
                           f"（{why}）⇒ **判据是空转的**，先修规则")
        g = h.get("regression_guard")
        if not isinstance(g, dict):
            bad.append(f"{at} 缺 `regression_guard` ⇒ 修过的坑没有护栏")
        else:
            gk, gid = _s(g.get("kind")), _s(g.get("id"))
            if gk not in ("fixture", "test"):
                bad.append(f"{at}.regression_guard.kind={gk!r} 不在封闭集 {{fixture, test}}")
            elif not gid:
                bad.append(f"{at}.regression_guard 缺 `id`")
        # 历史条目的动作组合必须与 `interruptions` 里**当前**的处置不同（否则"修了什么"就没写清）

    # ── 不可信输入（第 18 条）─────────────────────────────────────────────
    uts = doc.get("untrusted_inputs")
    if not isinstance(uts, list) or not uts:
        bad.append("`untrusted_inputs` 为空 ⇒ 不可信证据没有对象")
        uts = []
    un_und = []
    for i, u in enumerate(uts):
        at = f"untrusted_inputs[{i}]"
        if not isinstance(u, dict):
            bad.append(f"{at} 不是映射")
            continue
        uid = _s(u.get("id"))
        at = f"untrusted_inputs[{uid or i}]"
        for k in ("id", "what", "carrier"):
            if not _s(u.get(k)):
                bad.append(f"{at} 缺 `{k}`")
        d = u.get("declared")
        if not isinstance(d, bool):
            bad.append(f"{at} 缺 `declared` 布尔 ⇒ **声明了没有**必须可判")
        elif d:
            if not _s(u.get("declared_in")) or not _s(u.get("marker")):
                bad.append(f"{at} `declared: true` 但缺 `declared_in` / `marker` ⇒ "
                           f"无法去文件里**真找**那句声明（自报不算）")
        else:
            if not _s(u.get("why_not")):
                bad.append(f"{at} `declared: false` 但缺 `why_not` ⇒ "
                           f"**「没声明」也要给理由**（否则与「忘了」无法区分）")
            else:
                un_und.append(uid)

    tis = doc.get("trusted_inputs")
    if not isinstance(tis, list) or not tis:
        bad.append("`trusted_inputs` 为空 ⇒ **什么不算不可信**没写 ⇒ 边界靠猜")

    unv = doc.get("unverified")
    if not isinstance(unv, list) or not unv:
        bad.append("`unverified` 为空 ⇒ 本项自己未实测 / 未定的部分没登记")

    if not bad:
        notes.append(f"中断态 {len(seen)} 条（两岸口径齐）· 有死锁风险的 {len(risky)}"
                     f"{'（' + ', '.join(f'{a}:{b}' for a, b in risky) + '）' if risky else ''} · "
                     f"已修事故 {len(hist)} 条 · 不可信输入 {len(uts)} 条（未声明的 {len(un_und)}"
                     f"{'：' + ', '.join(un_und) if un_und else ''}）· 不算不可信 {len(tis)} 类")
    return bad, notes


def check_interruption(ctx, doc=None):
    """D7-P4-2: 中断态两岸口径（防死锁）+ 不可信证据规则 + 已修死锁的回归护栏。

    ★ `doc` 可注入（测试用）；`None` ⇒ 读 `inventory/interruption-and-untrusted.yaml`。
      签名与 `check_memory_gates` / `check_multi_round` 同形 —— **第一参数必须是 `ctx`**
      （harness 以 `c["fn"]({})` 调用 ⇒ 少写 `ctx` 会把 `{}` 当成 `doc`，判据静默判错对象）。
    """
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 interruption 断言", []
    if doc is None:
        if not INTERRUPT_INV.exists():
            return "FAIL", "inventory/interruption-and-untrusted.yaml 缺失（本断言的登记依据）", []
        try:
            doc = yaml.safe_load(_read_text(INTERRUPT_INV)) or {}
        except Exception as e:
            return "FAIL", f"inventory/interruption-and-untrusted.yaml 解析失败: {type(e).__name__}: {e}", []

    bad, notes = validate_interruption(doc)

    # 1) ★★ `declared: true` ⇒ **去文件里真找**那句声明（自报不算）
    for u in (doc.get("untrusted_inputs") or []):
        if not isinstance(u, dict) or u.get("declared") is not True:
            continue
        rel, mk = _s(u.get("declared_in")), _s(u.get("marker"))
        if not rel or not mk:
            continue
        if not (ROOT / rel).exists():
            bad.append(f"untrusted_inputs[{_s(u.get('id'))}] 的 `declared_in`={rel!r} 不存在 ⇒ "
                       f"声明无处可查（**不可判 ≠ 已声明**）")
            continue
        if mk not in _read_text(ROOT / rel):
            bad.append(f"★ untrusted_inputs[{_s(u.get('id'))}] 声称已在 {rel} 里声明不可信，"
                       f"但**该文件里找不到** {mk!r} ⇒ **自报不算声明**（第 18 条落空）")

    # 2) ★★ 已修事故的**回归护栏必须真实存在**
    for h in (doc.get("history") or []):
        if not isinstance(h, dict):
            continue
        g = h.get("regression_guard")
        if not isinstance(g, dict):
            continue
        gk, gid = _s(g.get("kind")), _s(g.get("id"))
        if not gid:
            continue
        if gk == "fixture":
            if gid not in _read_text(ROOT / "ops" / "station-bin" / "_fm_golden_test.ps1"):
                bad.append(f"history[{_s(h.get('id'))}] 的回归护栏夹具 **{gid}** 在 "
                           f"`_fm_golden_test.ps1` 里找不到 ⇒ 护栏是空头的")
        elif gk == "test":
            if not (ROOT / "tests" / gid).exists():
                bad.append(f"history[{_s(h.get('id'))}] 的回归护栏测试 {gid} 不存在 ⇒ 护栏是空头的")

    if bad:
        return "FAIL", " · ".join(notes) if notes else "见明细", bad
    return "PASS", " · ".join(notes), []


# ── D7-P4-3 (2026-09-26)「rubric + 自环盲区」────────────────────────────────────
#   Ds 简报 15（§4.10④）：rubric **只管本次引入的问题**（防意见被历史债务淹没）。
#   Ds 简报 12（§4.7）：**自环盲区显式登记** —— 「自环永远走我方两端的善意实现；
#     异构第三方 A2A server 的真实差异未测」⇒ ds 的做法就是**登记**，本机群照做。
#   Ds 简报 21（§4.13）：派生边表 ⇒ ⚠ 路线总表 §4.5 已列**非范围** ⇒ 只登记**触发条件**。
RUBRIC_INV = ROOT / "inventory" / "rubric-and-blindspots.yaml"
BLINDSPOT_KINDS = ("implementation", "dispatch", "external")
GUARD_KINDS = ("check", "test", "na")


def validate_rubric_blindspot(doc, known_checks):
    """**纯函数**（D7-P4-3）：rubric 必含条 + 自环盲区 + 派生边条件。"""
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["顶层不是映射（yaml 根应是 mapping）"], notes

    # ── ① rubric：**已落盘**，把它关键的几句变成**可机核的存在性** ──────────────
    #   ★ 为什么核"必须含哪几条"：rubric 是**纯文本资源**，删掉一句没人会知道 ——
    #     而这几句正是它防住的偏差（历史债务 / 自证 / verbosity / 翻案 / 不可信输入）。
    rb = doc.get("rubric")
    if not isinstance(rb, dict) or not _s(rb.get("file")):
        bad.append("缺 `rubric.file` ⇒ rubric 落点没写（退出判据第 1 条就是「rubric 落盘」）")
        rb = {}
    mc = rb.get("must_contain")
    if not isinstance(mc, list) or not mc:
        bad.append("`rubric.must_contain` 为空 ⇒ **关键纪律被删掉也没人知道**")
        mc = []
    seen_mc = set()
    for i, m in enumerate(mc):
        at = f"rubric.must_contain[{i}]"
        if not isinstance(m, dict):
            bad.append(f"{at} 不是映射")
            continue
        mid = _s(m.get("id"))
        if not mid or mid in seen_mc:
            bad.append(f"{at} 缺 `id` 或 `id` 重复: {mid!r}")
        seen_mc.add(mid)
        at = f"rubric.must_contain[{mid or i}]"
        for k in ("marker", "why"):
            if not _s(m.get(k)):
                bad.append(f"{at} 缺 `{k}`")
    # ★ 读取方式必须**显式编码**（否则 PS 5.1 下中文资源会乱码）—— 这条是"防改回去"
    rd = rb.get("reader")
    if isinstance(rd, dict):
        if not _s(rd.get("file")) or not _s(rd.get("marker")):
            bad.append("`rubric.reader` 缺 `file` / `marker`")
        elif not _s(rd.get("why")):
            bad.append("`rubric.reader` 缺 `why` ⇒ 没说清为什么要显式编码")

    # ── ② 自环盲区：**显式登记**（第 12 条）────────────────────────────────
    bs = doc.get("blindspots")
    if not isinstance(bs, list) or not bs:
        bad.append("`blindspots` 为空 ⇒ **自环盲区没有登记**（第 12 条明写要显式登记）")
        bs = []
    seen_bs, na_guards = set(), []
    for i, b in enumerate(bs):
        at = f"blindspots[{i}]"
        if not isinstance(b, dict):
            bad.append(f"{at} 不是映射")
            continue
        bid = _s(b.get("id"))
        if not bid or bid in seen_bs:
            bad.append(f"{at} 缺 `id` 或 `id` 重复: {bid!r}")
        seen_bs.add(bid)
        at = f"blindspots[{bid or i}]"
        for k in ("what", "why_blind", "evidence"):
            if not _s(b.get(k)):
                bad.append(f"{at} 缺 `{k}` ⇒ "
                           + ("**盲区必须写清为什么互审看不见**" if k == "why_blind" else "字段没写"))
        if b.get("kind") not in BLINDSPOT_KINDS:
            bad.append(f"{at} `kind`={b.get('kind')!r} 不在封闭集 {BLINDSPOT_KINDS}")
        g = b.get("other_guard")
        if not isinstance(g, dict):
            bad.append(f"{at} 缺 `other_guard` ⇒ **本仓用什么别的机制覆盖它**必须写（没有就写 `na`）")
        else:
            gk, ref = _s(g.get("kind")), _s(g.get("ref"))
            if gk not in GUARD_KINDS:
                bad.append(f"{at}.other_guard.kind={gk!r} 不在封闭集 {GUARD_KINDS}")
            elif gk == "check":
                if ref not in known_checks:
                    bad.append(f"{at}.other_guard 指的判据 {ref!r} **不是已注册的 CHECKS id** ⇒ 挂名")
            elif gk == "test":
                if not ref or not (ROOT / "tests" / ref).exists():
                    bad.append(f"{at}.other_guard 指的测试 {ref!r} 不存在")
            elif not _s(g.get("why")):
                bad.append(f"{at}.other_guard 是 `na` 但缺 `why` ⇒ **「没有替代机制」也要给理由**")
            if gk == "na":
                na_guards.append(bid)
    # ★★ 本仓**最实质**的盲区：三站互审走**同一份实现** ⇒ 同源代码缺陷两侧同时出现
    if "impl-same-source" not in seen_bs:
        bad.append("★ 缺 `impl-same-source` 盲区 ⇒ **本仓最实质的那条没登记**："
                   "三站互审走**同一份 `agent-cli.ps1`** ⇒ 实现层缺陷会在两侧**同时**出现，"
                   "互审在结构上**不可能**发现它（与「跨站≠跨族」是**正交**的两件事）")

    # ── ③ 派生边表：**条件触发**（第 21 条 + §4.5 非范围）────────────────────
    de = doc.get("derived_edges")
    if not isinstance(de, dict):
        bad.append("缺 `derived_edges` 段 ⇒ 第 21 条**连登记都没有**（非范围不等于不写）")
    else:
        if de.get("status") not in ("deferred", "done"):
            bad.append(f"`derived_edges.status`={de.get('status')!r} 不在封闭集 {{deferred, done}}")
        elif de.get("status") == "deferred" and not _s(de.get("condition")):
            bad.append("`derived_edges` 是 `deferred` 但缺 `condition` ⇒ "
                       "**触发条件没写死 ⇒ 它会永远挂着或悄悄做掉**")
        if not _s(de.get("why")):
            bad.append("`derived_edges` 缺 `why`")

    unv = doc.get("unverified")
    if not isinstance(unv, list) or not unv:
        bad.append("`unverified` 为空 ⇒ 本项自己未实测 / 未定的部分没登记")

    if not bad:
        notes.append(f"rubric 必含 {len(seen_mc)} 条 · 自环盲区 {len(seen_bs)} 条"
                     f"（无替代机制的 {len(na_guards)}"
                     f"{'：' + ', '.join(na_guards) if na_guards else ''}）· "
                     f"派生边 status={de.get('status') if isinstance(de, dict) else '?'}")
    return bad, notes


def check_rubric_blindspot(ctx, doc=None):
    """D7-P4-3: rubric（含"只报本次引入的问题"）+ 自环盲区显式登记 + 派生边条件。"""
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 rubric-blindspot 断言", []
    if doc is None:
        if not RUBRIC_INV.exists():
            return "FAIL", "inventory/rubric-and-blindspots.yaml 缺失（本断言的登记依据）", []
        try:
            doc = yaml.safe_load(_read_text(RUBRIC_INV)) or {}
        except Exception as e:
            return "FAIL", f"inventory/rubric-and-blindspots.yaml 解析失败: {type(e).__name__}: {e}", []

    bad, notes = validate_rubric_blindspot(doc, known_checks={c["id"] for c in CHECKS})

    # 1) ★★ rubric 必含条：**去那个文件里真找**（不是自报"我写了"）
    rb = doc.get("rubric") if isinstance(doc.get("rubric"), dict) else {}
    rel = _s(rb.get("file"))
    if rel:
        if not (ROOT / rel).exists():
            bad.append(f"`rubric.file`={rel!r} 不存在 ⇒ **返回内容是个错误串**（`RUBRIC_UNAVAILABLE`），"
                       f"判官拿不到 rubric（**不可判 ≠ 通过**）")
        else:
            txt = _read_text(ROOT / rel)
            for m in [x for x in (rb.get("must_contain") or []) if isinstance(x, dict)]:
                mk = _s(m.get("marker"))
                if mk and mk not in txt:
                    bad.append(f"★ rubric 里**找不到**必含句 {mk!r}"
                               f"（id={_s(m.get('id'))}）⇒ 那条纪律被删了/改了措辞；"
                               f"改措辞请**同步改真值表**（别让它悄悄失守）")

    # 2) ★ rubric/tmpl 的读取必须**显式编码**（否则 PS 5.1 下中文资源乱码）
    rd = rb.get("reader")
    if isinstance(rd, dict) and _s(rd.get("file")) and _s(rd.get("marker")):
        rf = _s(rd["file"])
        if not (ROOT / rf).exists():
            bad.append(f"`rubric.reader.file`={rf!r} 不存在 ⇒ 读取方式不可判")
        elif _s(rd["marker"]) not in _read_text(ROOT / rf):
            bad.append(f"★ `{rf}` 里找不到 `{_s(rd['marker'])}` ⇒ "
                       f"**读取可能退回裸 `Get-Content`**（PS 5.1 默认 ANSI ⇒ 中文资源乱码）")

    if bad:
        return "FAIL", " · ".join(notes) if notes else "见明细", bad
    return "PASS", " · ".join(notes), []


CAPABILITY_INV = ROOT / "inventory" / "capability-inventory.yaml"
CAP_DOMAINS = ("verify", "identity", "orchestration", "meta")
CAP_VERDICTS = ("present", "partial", "absent")
CAP_BASIS = ("E1", "E2")
CAP_WHY_KINDS = ("na", "not-done", "pending-decision")
CAP_CARRIER_KINDS = ("file", "gate", "table")


def _ds(v):
    """日期字段取串：**接受 yaml 把裸日期解析出的 `date` / `datetime`**。

    ★ 为什么单独一个函数：`updated: 2026-09-27` 会被 yaml 解析成 **`datetime.date`**，
    而 `_s()` 对非字符串一律返回空 ⇒ 判据会报「缺 `updated`」，**而人看表里明明有** ——
    这是**口径陷阱**（同族：O-93 的『同一棵树三种口径三个结果』）。
    ⇒ 判据对**同一事实的不同合法写法**要宽容（裸日期 / 带引号都收），只对**真的没有**严格。
    """
    if isinstance(v, str):
        return v.strip()
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return ""


def validate_capability_inventory(doc, known_checks, exists_fn):
    """**纯函数**（O-105）：能力 → 载体 → 判定。

    ★★ 它要防的是「**能力的存在性靠自报**」—— 所以 present / partial **必须给可核载体**，
    判据去**仓里真找**（file 存在 / gate 是已注册 CHECKS id / table 在 inventory/）；
    absent **必须写理由**（本仓纪律:「不适用也是一种结论，必须写下来」）**与读数** `evidence`
    —— 「本仓没有这个机制」**本身也是断言**，absent **不豁免** evidence（真表首版即此错）。
    """
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["顶层不是映射（yaml 根应是 mapping）"], notes

    # ── ① 表级：口径 + 读数日期（它是**增长型载体**，没日期读者不知道是哪天的树）──
    m = doc.get("metric")
    if not isinstance(m, dict) or not (_s(m.get("name")) and _s(m.get("unit")) and _s(m.get("scope"))):
        bad.append("缺 `metric` 的 `name`/`unit`/`scope` ⇒ **增长型计数没有口径** —— "
                   "口径一变，表里所有数字立刻失去意义（§87.6 的『同日漂移』就是这类）")
    if not _ds(doc.get("updated")):
        bad.append("缺 `updated` ⇒ **没有读数日期** ⇒ 读者无法判断这表是哪一天的树")

    # ── ② 声明的封闭集 == 判据实现（防口径漂移：改了代码没改表 / 反之）──────────
    for k, allowed in (("domains", CAP_DOMAINS), ("verdicts", CAP_VERDICTS),
                       ("basis", CAP_BASIS), ("why_kinds", CAP_WHY_KINDS),
                       ("carrier_kinds", CAP_CARRIER_KINDS)):
        v = doc.get(k)
        if not isinstance(v, list) or tuple(v) != allowed:
            bad.append(f"`{k}`={v!r} 应为封闭集 {list(allowed)} ⇒ "
                       f"**声明的口径必须与判据实现一致**（不一致时，本判据自己就是假绿）")

    items = doc.get("items")
    if not isinstance(items, list) or not items:
        return bad + ["`items` 为空 ⇒ **判据没有对象**（退化空判，本仓头号形态）"], notes

    # ── ③ 逐项 ─────────────────────────────────────────────────────────────
    seen = set()
    for i, it in enumerate(items):
        at = f"items[{i}]"
        if not isinstance(it, dict):
            bad.append(f"{at} 不是映射")
            continue
        cid = _s(it.get("id"))
        if not cid or cid in seen:
            bad.append(f"{at} 缺 `id` 或 `id` 重复: {cid!r}")
        seen.add(cid)
        at = f"items[{cid or i}]"
        for k in ("domain", "what", "evidence"):
            if not _s(it.get(k)):
                bad.append(f"{at} 缺 `{k}`")
        if it.get("domain") not in CAP_DOMAINS:
            bad.append(f"{at} `domain`={it.get('domain')!r} 不在封闭集 {CAP_DOMAINS}")
        if it.get("basis") not in CAP_BASIS:
            bad.append(f"{at} `basis`={it.get('basis')!r} 不在封闭集 {CAP_BASIS} ⇒ "
                       f"**取证方式必须写明**（E1 读文件 / E2 跑命令）")
        vd = it.get("verdict")
        if vd not in CAP_VERDICTS:
            bad.append(f"{at} `verdict`={vd!r} 不在封闭集 {CAP_VERDICTS}")
            continue

        # ★★ 核心：有载体 ⇒ 必须**可达**（去仓里真找，不采信自报）
        if vd in ("present", "partial"):
            cs = it.get("carriers")
            if not isinstance(cs, list) or not cs:
                bad.append(f"{at} verdict={vd} ⇒ **必须给载体**（否则是自报）")
            else:
                for j, c in enumerate(cs):
                    cat = f"{at}.carriers[{j}]"
                    if not isinstance(c, dict):
                        bad.append(f"{cat} 不是映射")
                        continue
                    ck, ref = c.get("kind"), _s(c.get("ref"))
                    if ck not in CAP_CARRIER_KINDS:
                        bad.append(f"{cat}.kind={ck!r} 不在封闭集 {CAP_CARRIER_KINDS}")
                        continue
                    if not ref:
                        bad.append(f"{cat} 缺 `ref`")
                        continue
                    if ck == "gate" and ref not in known_checks:
                        bad.append(f"{cat} 指的判据 {ref!r} **不是已注册的 CHECKS id** ⇒ 挂名"
                                   f"（判据写了但没人跑 —— 本仓最典型的一类假绿）")
                    elif ck == "file" and not exists_fn(ref):
                        bad.append(f"{cat} 指的仓内文件 {ref!r} **不存在**")
                    elif ck == "table" and not exists_fn(
                            ref if "/" in ref else f"inventory/{ref}"):
                        bad.append(f"{cat} 指的真值表 {ref!r} **不存在**")
        if vd == "partial" and not _s(it.get("gap")):
            bad.append(f"{at} verdict=partial 但缺 `gap` ⇒ **缺哪一块必须写清**"
                       f"（否则 partial 是个托词，读者无法判断它离 present 差多少）")
        if vd == "absent":
            wk = it.get("why_kind")
            if wk not in CAP_WHY_KINDS:
                bad.append(f"{at} verdict=absent 但 `why_kind`={wk!r} 不在封闭集 {CAP_WHY_KINDS}"
                           f"（不适用 / 未做 / 待裁 —— 三者含义**不同**，混起来就不可判）")
            if not _s(it.get("why")):
                bad.append(f"{at} verdict=absent 但缺 `why` ⇒ "
                           f"**「不做」也是一种结论，必须写下来**")

    # ── ④ 自指：本表必须盘到自己（否则「能力盘点」这项能力本身没被盘点）────────
    sid = _s(doc.get("self_id"))
    if not sid:
        bad.append("缺 `self_id` ⇒ 表没有声明**哪一项是它自己**")
    elif sid not in seen:
        bad.append(f"`self_id`={sid!r} 不在 items 里 ⇒ "
                   f"**「能力盘点」这项能力本身没被盘点**（自指缺口）")

    unv = doc.get("unverified")
    if not isinstance(unv, list) or not unv:
        bad.append("`unverified` 为空 ⇒ 本项自己未实测 / 未定的部分没登记")

    if not bad:
        cnt = {}
        for x in items:
            if isinstance(x, dict):
                cnt[_s(x.get("verdict"))] = cnt.get(_s(x.get("verdict")), 0) + 1
        notes.append(f"能力 {len(seen)} 项 · present {cnt.get('present', 0)} / "
                     f"partial {cnt.get('partial', 0)} / absent {cnt.get('absent', 0)} · "
                     f"口径 {_s(m.get('name')) if isinstance(m, dict) else '?'} · 读数 {_ds(doc.get('updated'))}")
    return bad, notes


def check_capability_inventory(ctx, doc=None):
    """O-105: 能力 → 载体 → 判定（能力盘点表）。"""
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 capabilities 断言", []
    if doc is None:
        if not CAPABILITY_INV.exists():
            return "FAIL", "inventory/capability-inventory.yaml 缺失（本断言的登记依据）", []
        try:
            doc = yaml.safe_load(_read_text(CAPABILITY_INV)) or {}
        except Exception as e:
            return "FAIL", f"inventory/capability-inventory.yaml 解析失败: {type(e).__name__}: {e}", []

    bad, notes = validate_capability_inventory(
        doc, known_checks={c["id"] for c in CHECKS},
        exists_fn=lambda rel: (ROOT / rel).exists())

    if bad:
        return "FAIL", " · ".join(notes) if notes else "见明细", bad
    return "PASS", " · ".join(notes), []


# ── O-108 (2026-09-27): 文档状态声明的**两处位点** ────────────────────────────
DOC_STATUS_INV = ROOT / "inventory" / "doc-status.yaml"
DOC_STATUS_DIRS = ("spec", "adr")
DOC_STATUS_HEAD = 20          # ★ 射程**写死**：文档头 N 行（口径是判据的一部分，见 DEV-LOG-014 §90.4）
_DOC_FM_RE = re.compile(r"^status:\s*(.+)$")
_DOC_BODY_RE = re.compile(r"^>\s*\*\*状态\*\*:\s*(.+)$")
# ★ 这是**归一表，不是词表**：只为把「同一事实的不同合法写法」比到一处。
#   词表真值**只有一个地方** —— `spec/vulkan-version-control/*_TEMPLATE.md` 的「状态」行（O-106）。
_DOC_NORM = {
    "草稿": "draft", "review 中": "in-review", "review": "in-review",
    "已验证": "verified", "已作废": "superseded",
    "待验收": "pending", "验收中": "in-review",
    "已验收": "accepted", "已验收通过": "accepted", "验收通过": "accepted",
}


def _doc_token(v):
    """状态 token：去粗体 / 括注后归一。

    ★ 与 `_ds()` 同族 —— 对**合法写法差异**宽容（`draft` / `草稿` / `**draft**` 是同一事实），
    只对**真的不等**严格（否则判据会红一片**假阳性**）。
    """
    t = _s(v).strip("*").strip()
    t = re.split(r"[（(—\s]", t)[0].strip("*:：")
    return _DOC_NORM.get(t.lower(), _DOC_NORM.get(t, t.lower()))


def _doc_raw_token(v):
    """状态 token 的**原文**（O-109）—— ★ 与 `_doc_token` 不同：**不做中文↔英文归一**。

    ★ 词表校验必须用**原文**：若拿归一后的 token 去比词表，`草稿` 会等于 `draft`
    `Review 中` 会等于 `in-review` ⇒ 明明是**词表外**的写法也会被判为合规（假绿）。
    ★ 归一只用于**两处比对**（fm ↔ 正文 是同一事实的两种合法写法）。
    """
    t = _s(v).strip("*").strip()
    return re.split(r"[（(—\s]", t)[0].strip("*:：")


# ── O-109 (2026-09-27): 档位 → 词表（**读取位点**分工）────────────────────────
def _parse_template_vocab(path):
    """从模板的「状态」行解析词表：以 `/` 拆分，每段取 `（` 之前的 token。

    ★ 例 `draft（草稿）/ in-review（Review 中）/ …` ⇒ `[draft, in-review, …]`；
    纯中文段（checklist 档 `待验收 / 验收中 / 已验收`）⇒ **中文 token 即词表项**。
    """
    for line in _read_text(path).splitlines():
        m = _DOC_BODY_RE.match(line)
        if not m:
            continue
        toks = []
        for seg in m.group(1).split("/"):
            tok = re.split(r"[（(]", seg.strip())[0].strip().strip("*:：")
            if tok:
                toks.append(tok)
        return toks
    return []


def _vocab_tokens(tokens):
    """词表 token 集（原文 + **归一形**）。

    ★ 词表侧补归一形（如 checklist 档的 `待验收` ⇒ 也认 `pending`），而**实例 token 侧不归一**
    （见 `_doc_raw_token`）—— 于是 fm 写 `accepted` / 正文写 `已验收` **都算合词表**，
    但**词表外的写法**（如 design 档写 `草稿`、写 `active`）仍会被抓出来。
    """
    out = set()
    for t in tokens:
        t = _s(t).strip()
        if t:
            out.add(t)
            out.add(_doc_token(t))
    return out


def load_kind_vocab(root=None, doc=None):
    """**纯函数**（O-109）：档位 → 词表 token 集 `{kind: set(tokens)}`。

    · **有模板的档**（design / checklist / adr）：真值在**模板链** ⇒ 解析
      `kind_source.by_kind[kind].ref` 指向的模板文件的「状态」行（★ **不把这些词抄进 yaml**）。
    · **无模板的档**（ledger / process）：本仓特有、**无模板** ⇒ 直接取 `by_kind[kind].vocab`。
    """
    root = Path(root) if root else ROOT
    if doc is None:
        try:
            import yaml
            doc = yaml.safe_load(_read_text(root / "inventory" / "doc-status.yaml")) or {}
        except Exception:
            return {}
    ks = doc.get("kind_source") if isinstance(doc, dict) else None
    by_kind = ks.get("by_kind") if isinstance(ks, dict) else None
    if not isinstance(by_kind, dict):
        return {}
    out = {}
    for kind, spec in by_kind.items():
        if not isinstance(spec, dict):
            continue
        src = _s(spec.get("from"))
        if src == "here":
            toks = [str(t) for t in (spec.get("vocab") or [])]
        elif src == "template":
            ref = _s(spec.get("ref"))
            toks = _parse_template_vocab(root / ref) if ref else []
        else:
            toks = []
        out[str(kind)] = _vocab_tokens(toks)
    return out


def _doc_kind(fname, kinds_reg):
    """判档（`kind_source.kind_rule`）：

    ① `adr/**` → adr；② 文件名含 `CHECKLIST` → checklist；
    ③ 命中 `kinds:` 登记 → 按登记；④ 其余 → design。
    """
    f_ = _s(fname)
    fl = f_.lower()
    base = fl.rsplit("/", 1)[-1]
    if fl.startswith("adr/") or "/adr/" in fl:
        return "adr"
    if "checklist" in base:
        return "checklist"
    if f_ in (kinds_reg or {}):
        return kinds_reg[f_]
    return "design"


def scan_doc_status(root=ROOT, dirs=DOC_STATUS_DIRS, head=DOC_STATUS_HEAD):
    """扫两处状态声明（★ **纯读，不判**）：返回 `(pairs, n_template, sites)`。

    · `pairs` 只收**两处都有**的**实例**文档 —— `*_TEMPLATE.md` 的正文行是**词表**而非实例值
      ⇒ **不入对**，只报数。
    · `sites` 收**每个位点**（fm / 正文各一条，含模板）—— O-109 的**词表校验按位点**判；
      模板位点由判据侧**跳过**（见 `validate_doc_status`）。

    ★ 射程**写死 `head` 行**：本仓实测，同一测量不写死会把「正文里描述**别的对象**的
    `**状态**:`」（如"某对象状态 = A/B/C"）也算进来 ⇒ 数从 **95 涨到 110**（§90.4）。
    """
    pairs, sites, n_tpl = [], [], 0
    for d in dirs:
        base = root / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.md")):
            rel = p.relative_to(root).as_posix()
            is_tpl = p.name.upper().endswith("_TEMPLATE.MD")
            if is_tpl:
                n_tpl += 1
            fm = body = None
            for i, line in enumerate(_read_text(p).splitlines(), 1):
                if i > head:
                    break
                m = _DOC_FM_RE.match(line)
                if m:
                    if fm is None:
                        fm = m.group(1).strip()
                    sites.append({"file": rel, "slot": "fm",
                                  "value": m.group(1).strip(), "template": is_tpl})
                m2 = _DOC_BODY_RE.match(line)
                if m2:
                    if body is None:
                        body = m2.group(1).strip()
                    sites.append({"file": rel, "slot": "body",
                                  "value": m2.group(1).strip(), "template": is_tpl})
            if fm is not None and body is not None and not is_tpl:
                pairs.append({"file": rel, "fm": fm, "body": body})
    return pairs, n_tpl, sites


def validate_doc_status(pairs, doc, n_template=0, sites=None):
    """**纯函数**（O-108 / O-109）：① 两处状态声明（一个真值 fm + 一个派生位正文）；
    ② **词表符合性（按档）**。

    ★★ ① 为什么它**不是**"被 I-10 禁掉的对账"：**唯一写入点是 front matter**，正文行是**渲染**
    ⇒ 判据检的是「**派生是否过期**」，而**不是**「两处谁对」；★ **修法唯一**（改正文，不改 fm）。
    ⚠ 但**严格读 I-10，本面仍是两个位点** ⇒ 本表是**降格处置**、非完全实现
    （彻底消除 = `O-108` 案①，仍开着）—— 这句如实写在 `semantics.i10_note` 里，**不藏**。

    ★ ② O-109：**每个位点按其「档」**校验 token 是否在**该档词表**内（档 → 词表读取位点见
    `kind_source`）。★ token 取**原文**（`_doc_raw_token`，**不归一**）；★ 模板文件**跳过**
    （其「状态」行是**词表本身**）。`sites` 缺省时由 `pairs` 反推两个位点（兼容旧调用）。
    """
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["顶层不是映射（yaml 根应是 mapping）"], notes

    sem = doc.get("semantics")
    if not isinstance(sem, dict) or not (_s(sem.get("single_write")) and _s(sem.get("derived"))):
        bad.append("缺 `semantics.single_write` / `semantics.derived` ⇒ **本表会退化成一张豁免清单**："
                   "没声明「谁是真值、谁是派生」（而那恰是 I-10 要的那一句）")
    if not _ds(doc.get("updated")):
        bad.append("缺 `updated` ⇒ 没有读数日期（读者无法判断这是哪一天的树）")
    unv = doc.get("unverified")
    if not isinstance(unv, list) or not unv:
        bad.append("`unverified` 为空 ⇒ 本项自己未实测 / 未定的部分没登记")

    fr = doc.get("freeze") or []
    if not isinstance(fr, list):
        return bad + ["`freeze` 不是列表"], notes
    froze = {}
    for i, e in enumerate(fr):
        at = f"freeze[{i}]"
        if not isinstance(e, dict):
            bad.append(f"{at} 不是映射")
            continue
        f_ = _s(e.get("file"))
        if not f_ or not (ROOT / f_).exists():
            bad.append(f"{at} 的 `file`={f_!r} **不在仓里** ⇒ 登记腐化（文件已删 / 改名）")
            continue
        if not _s(e.get("why")):
            bad.append(f"{at} 缺 `why` ⇒ **冻结是一种豁免，必须写理由**"
                       f"（照 `inventory/ops.yaml` 的「冻结存量」）")
        froze[f_] = e

    eq, ne = 0, []
    for p in pairs:
        f_, a, b = _s(p.get("file")), _doc_token(p.get("fm")), _doc_token(p.get("body"))
        if a == b:
            eq += 1
        else:
            ne.append((f_, a, b))
    new_ne = [x for x in ne if x[0] not in froze]
    frz_ne = [x for x in ne if x[0] in froze]
    for f_, a, b in new_ne:
        bad.append(f"★ `{f_}` 两处状态声明**不等**：front matter `{a}` ↔ 正文 `{b}` ⇒ "
                   f"**判为「派生过期」**（唯一写入点是 fm ⇒ **改正文行**；"
                   f"**别**改 fm 去迁就正文）")

    seen = {_s(p.get("file")) for p in pairs}
    eq_files = {_s(p.get("file")) for p in pairs
                if _doc_token(p.get("fm")) == _doc_token(p.get("body"))}
    healed = sorted(f for f in froze if f in eq_files)
    gone = sorted(f for f in froze if f not in seen)
    if healed:
        bad.append(f"冻结清单里 {len(healed)} 项**已自愈**（两处已一致）："
                   f"{', '.join(healed[:5])}{' …' if len(healed) > 5 else ''} ⇒ **删掉它们**"
                   f"（留着会把本表烂成垃圾桶 —— 同 `secrets` 的「豁免未命中」防腐化）")
    if gone:
        bad.append(f"冻结清单里 {len(gone)} 项**已不再是「两处都有」**："
                   f"{', '.join(gone[:5])}{' …' if len(gone) > 5 else ''} ⇒ **删掉它们**"
                   f"（少了一处 ⇒ 该面已只剩一个位点）")

    # ── O-109 ②：词表符合性（**按档**判 token 是否在档内）──────────────────────
    v_note = ""
    ks = doc.get("kind_source")
    if not isinstance(ks, dict):
        bad.append("缺 `kind_source`（档 → 词表的**读取位点**，O-109）⇒ 判据无法按档校验 token"
                   "（`by_kind` / `kind_rule` / `kinds` 都无从取）")
    else:
        vocab = load_kind_vocab(doc=doc)
        reg = {_s(e.get("file")): _s(e.get("kind"))
               for e in (doc.get("kinds") or []) if isinstance(e, dict)}
        if sites is None:                       # 兼容旧调用：由 pairs 反推两个位点
            sites = []
            for p in pairs:
                f_ = _s(p.get("file"))
                sites.append({"file": f_, "slot": "fm", "value": p.get("fm"), "template": False})
                sites.append({"file": f_, "slot": "body", "value": p.get("body"), "template": False})
        n_ok = n_site = n_tpl_site = 0
        vbad = []
        for s in sites:
            if not isinstance(s, dict):
                continue
            f_ = _s(s.get("file"))
            if s.get("template") or f_.upper().endswith("_TEMPLATE.MD"):
                # ★★ 模板位点**不入分母**：其「状态」行是**词表本身**，判它 = 自己判自己。
                #   ⚠ 但**跳过 ≠ 判过且通过**（本仓头号形态：报数型假绿）⇒ 单独报数，不并进分子。
                n_tpl_site += 1
                continue
            n_site += 1
            kind = _doc_kind(f_, reg)
            toks = vocab.get(kind)
            tok = _doc_raw_token(s.get("value"))
            if toks is None:
                vbad.append((f_, _s(s.get("slot")), tok, kind, None))
            elif tok in toks:
                n_ok += 1
            else:
                vbad.append((f_, _s(s.get("slot")), tok, kind, sorted(toks)))
        for f_, slot, tok, kind, toks in vbad[:20]:
            if toks is None:
                bad.append(f"★ `{f_}`（{slot} 位点）token=`{tok}` 属档 `{kind}`，"
                           f"但 `kind_source.by_kind` **没有这一档** ⇒ 无词表可判（**词表缺档**）")
            else:
                bad.append(f"★ `{f_}`（{slot} 位点）token=`{tok}` **不在档 `{kind}` 的词表**"
                           f" {toks} 内 ⇒ 状态位写了**词表外**的值")
        if len(vbad) > 20:
            bad.append(f"…另有 {len(vbad) - 20} 处词表不符（略）")
        v_note = f" · 词表符合 {n_ok}/{n_site}"
        if n_tpl_site:
            v_note += f"（另有模板 {n_tpl_site} 位点**跳过、不入分母**——其「状态」行是词表本身）"

    notes.append(f"两处都有 {len(pairs)} · 一致 {eq} · 不等 {len(ne)}"
                 f"（冻结 {len(frz_ne)} / **新增 {len(new_ne)}**）"
                 f" · 模板 {n_template}（正文行是词表，不入对）{v_note}"
                 f" · 读数 {_ds(doc.get('updated'))}")
    return bad, notes


def check_doc_status(ctx=None, doc=None, pairs=None, sites=None):
    """O-108 / O-109: ① 同一文档两处状态声明（判「**派生是否过期**」）+ ② **词表符合性（按档）**。"""
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 doc-status 断言", []
    if doc is None:
        if not DOC_STATUS_INV.exists():
            return "FAIL", "inventory/doc-status.yaml 缺失（本断言的登记依据）", []
        try:
            doc = yaml.safe_load(_read_text(DOC_STATUS_INV)) or {}
        except Exception as e:
            return "FAIL", f"inventory/doc-status.yaml 解析失败: {type(e).__name__}: {e}", []

    n_tpl = 0
    if pairs is None:
        pairs, n_tpl, sites = scan_doc_status()

    bad, notes = validate_doc_status(pairs, doc, n_template=n_tpl, sites=sites)
    if bad:
        return "FAIL", " · ".join(notes) if notes else "见明细", bad
    return "PASS", " · ".join(notes), []


# ── A4（2026-09-29）: md 表格**列数守恒** ────────────────────────────────────
# 事故形态（真实、已抽象）：某个字段的文本里**出现了一个竖线**（作者以为转义了，其实没有）⇒
#   该行**被拆成了比表头更多的格**，字段错位，而且**长期无人发现**（此前**没有任何检查器读"列数"**）。
# 口径（照 `spec/d6-agent-standard/dogfood-cards/land-a4-cell-safety.md` 的**已勘误**底稿，**单一实现**）：
#   ① **空单元格计入**列数（`| a |  | c |` 是 3 格，不是 2）；
#   ② 分隔行必须**紧邻**表头行的下一行 —— **不跨行去找**（否则会判一张 GFM 里并不存在的表）；
#   ③ 代码围栏（``` 或 ~~~）内**整段跳过**；GFM 缩进码块（≥4 空格）**跳过**；
#   ④ 单元格内容里的 `\|` 是**转义** ⇒ 不算分隔符（这正是「拆格的分隔符」与「内容里的竖线」之别）。
MD_TABLES_INV = ROOT / "inventory" / "md-tables.yaml"


def _md_cols(line):
    """一行 markdown 表格的**格数**（**含空单元格**）。`\\|` 计为内容，不拆格。"""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    parts, cur, esc = [], "", False
    for ch in s:
        if esc:
            cur += ch
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == "|":
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return len(parts)


def _md_is_sep(line):
    """分隔行（`|---|:--:|`）：只由 `-`/`|`/`:`/空白组成且**含** `---`。"""
    s = line.strip()
    return "---" in s and all(c in "|-: \t" for c in s)


def _md_is_fence(line):
    """代码围栏开/关行（``` 或 ~~~ —— 后者是底稿勘误①补入的形态）。"""
    t = line.lstrip()
    return t.startswith("```") or t.startswith("~~~")


def md_table_scan(text):
    """**纯函数**：扫一篇 md 的表格 → `(violations, n_tables)`。

    violations = `[(行号(1 起), kind, 格数, 表头格数)]`，kind ∈ `{"sep", "row"}`。
    ★ 先验红点（A4）：往某数据行塞一个**未转义**竖线 ⇒ 本函数**必须**报出该行（见 `tests/`）。
    """
    lines = text.splitlines()
    out, i, in_code, n_tbl = [], 0, False, 0
    while i < len(lines):
        raw = lines[i]
        if _md_is_fence(raw):
            in_code = not in_code
            i += 1
            continue
        if in_code or raw[:4] == "    ":          # 围栏内 / GFM 缩进码块 ⇒ **不是**表格
            i += 1
            continue
        head = raw.strip()
        if not head.startswith("|") or _md_cols(head) == 0:
            i += 1
            continue
        if i + 1 >= len(lines) or not _md_is_sep(lines[i + 1].strip()):
            i += 1
            continue                              # 口径②：分隔行必须**紧邻**表头
        n_tbl += 1
        hc = _md_cols(head)
        sc = _md_cols(lines[i + 1].strip())
        if sc != hc:
            out.append((i + 2, "sep", sc, hc))
        k = i + 2
        while k < len(lines) and lines[k].strip().startswith("|"):
            s = lines[k].strip()
            if not _md_is_sep(s) and _md_cols(s) != hc:
                out.append((k + 1, "row", _md_cols(s), hc))
            k += 1
        i = k
    return out, n_tbl


def _md_line_hash(raw):
    """违规**原始行**（不含换行）的 sha256 前 16 位 —— 冻结的指纹键（**不用行号**，防漂移）。"""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def check_md_tables(ctx):
    """A4: md 表格**列数守恒** —— 防「某行被拆错格」这类**静默错位**。

    ★ 判什么：同一张表里 **分隔行 / 数据行** 的格数 == **表头**格数；不符 ⇒ 该行**错位**。
    📊 报数：`扫描 N 篇 · 表 T 张 · 违规 V（冻结 F · **新增 D**）` —— 命中冻结的**不判 FAIL**。
    ⚠⚠ **不判什么**：不判表格**内容**对不对，也不判「文档该不该有表」。
      ★ 但 **`表 T 张` 为 0 ⇒ FAIL**（判据**没有对象** = 退化空判，本仓头号形态）——
      因此**「整篇没有表格 ⇒ 空集恒真」这类假绿在本项被显式堵住**（底稿 §假绿 第 1 条）。
    ⚠ 假绿（完整清单见 `dogfood-cards/land-a4-cell-safety.md`）：缩进码块 / `~~~` 围栏内的伪表格
      —— 已按 GFM 跳过（**跳过 ≠ 判过且通过**，故底稿要求它们显式登记）。
    """
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 md 表格列数断言", []
    if not MD_TABLES_INV.exists():
        return "FAIL", "inventory/md-tables.yaml 缺失（本断言的**存量冻结**依据）", []
    try:
        inv = yaml.safe_load(_read_text(MD_TABLES_INV)) or {}
    except Exception as e:
        return "FAIL", f"inventory/md-tables.yaml 解析失败: {type(e).__name__}: {e}", []

    fr = inv.get("frozen")
    if not isinstance(fr, list):
        return "FAIL", "`frozen` 不是列表（本表退化成一张豁免清单？）", []
    inv_bad, frozen = [], {}
    for idx, e in enumerate(fr):
        at = f"frozen[{idx}]"
        if not isinstance(e, dict):
            inv_bad.append(f"{at} 不是映射")
            continue
        f_ = str(e.get("file") or "")
        lh = str(e.get("line_sha256") or "")
        if not f_ or not (ROOT / f_).exists():
            inv_bad.append(f"{at} 的 `file`={f_!r} **不在仓里** ⇒ 登记腐化（已删 / 改名 / 路径写错）")
            continue
        if not lh or not str(e.get("why") or ""):
            inv_bad.append(f"{at} 缺 `line_sha256` 或 `why` ⇒ **冻结是一种豁免，两样都要写**")
            continue
        frozen[(f_, lh)] = str(e.get("why"))

    n_md = n_tbl = 0
    new_v, hit = [], set()
    for p in sorted(ROOT.rglob("*.md")):
        rel = p.relative_to(ROOT)
        if any(s in rel.parts for s in DOCLINK_SKIP_PARTS):
            continue
        n_md += 1
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        vs, nt = md_table_scan("\n".join(lines))
        n_tbl += nt
        rp = rel.as_posix()
        for (ln, kind, dc, hc) in vs:
            lh = _md_line_hash(lines[ln - 1])
            if (rp, lh) in frozen:
                hit.add((rp, lh))
            else:
                new_v.append((rp, ln, kind, dc, hc))

    detail = []
    for (rp, ln, kind, dc, hc) in new_v[:20]:
        detail.append(f"★ {rp}:{ln} **{kind} 行 {dc} 格 ≠ 表头 {hc} 格** ⇒ 该行**错位**"
                      f"（单元格里的裸竖线多半没转义 —— 写成反斜杠 + 竖线）")
    if len(new_v) > 20:
        detail.append(f"…另有 {len(new_v) - 20} 处（略）")
    detail += inv_bad

    missing = [(f_, lh) for (f_, lh) in frozen if (f_, lh) not in hit]
    rot = sorted(f_ for (f_, _) in missing if not (ROOT / f_).exists())
    healed = sorted({f_ for (f_, _) in missing if (ROOT / f_).exists()})
    if rot:
        detail.append(f"冻结条目**指向已不存在的文件** {len(rot)} 条 ⇒ 删掉它们（登记腐化）: "
                      + ", ".join(rot[:6]) + (" …" if len(rot) > 6 else ""))
    if healed:
        detail.append(f"冻结条目**已失配** {len(healed)} 处（那行已改：修好了，或又改坏成别的指纹）"
                      f" ⇒ **请从 inventory/md-tables.yaml 删掉对应条目**（只减不增，防腐化）: "
                      + ", ".join(healed[:6]) + (" …" if len(healed) > 6 else ""))

    note = (f"扫描 {n_md} 篇 · 表 {n_tbl} 张 · 违规 {len(new_v) + len(hit)}"
            f"（冻结 {len(hit)} · **新增 {len(new_v)}**）")
    if rot or healed:
        note += f" · 冻结失配 {len(rot) + len(healed)}"
    if n_tbl == 0:
        return "FAIL", note + " · **表 0 张 ⇒ 判据无对象**（防退化空判）", detail
    fail = bool(new_v) or bool(inv_bad) or bool(rot) or bool(healed)
    return ("FAIL" if fail else "PASS"), note, detail


# ── A5（2026-09-29）: 确定性 —— 噪声口径**单一真值表** + 双跑逐字节比对 ──────────────────
# 事故形态（真实、已抽象）：某判据做"**同源双跑逐字节一致**"，但**没定义哪些差异不算内容差异**
#   ⇒ 时间戳 / 运行 ID / 绝对路径 / CRLF 把**真一致**打成**假红**，或把**真不一致**洗成**假绿**。
# 口径（照 `spec/d6-agent-standard/dogfood-cards/land-a5-determinism.md` 的**已勘误**底稿，单一实现）：
#   ① 噪声口径**统一为单表**（非每条判据各写一份）；② 适用面由表的 `applies_to` 声明；
#   ③ 归一化（CRLF→LF）**只允许在生产端固化**（比对端妥协 = 把噪声洗成假绿）；
#   ④ `determinism: n/a`（天然不可双跑）**必须显式标记 + 给 reason**，缺 reason ⇒ 违规（禁止静默跳过）。
DET_NOISE_INV = ROOT / "inventory" / "determinism-noise.yaml"
# 每类**可机检**噪声的**代表样本** —— 用于证明表里的正则**真能匹配**（防塞一条永远匹配不上的正则）。
# ⚠ 样本是判据的**夹具**，**不是**噪声表的第二定义点（噪声表仍在 yaml 里）。
_DET_SAMPLES = {
    "timestamp": ["2026-09-29T12:00:00", "1700000000"],
    "run-id": ["550e8400-e29b-41d4-a716-446655440000", "01ARZ3NDEKTSV4RRFFQ69G5FAV"],
    "absolute-path": ["/home/u/x", "/tmp/abc123", r"C:\Users\x"],
    "temp-dir": ["tmpabc123", "temp_xyz789"],
    "env-context": ["PWD=/work", "HOSTNAME=node1", "USER=me"],
}


def det_manifest_diff(a, b):
    """**纯函数**：两份 `{路径: sha256}` **逐字节**比对 → 差异清单（**不排序、不归一化换行符**）。

    ★ 先验红点（A5）：把**时间戳写进产物** ⇒ 两份哈希不等 ⇒ 本函数**必须**报出该路径（见 `tests/`）。
    ⚠ CRLF→LF 的归一化**只允许在生产端固化** —— 比对端妥协 = 把噪声洗成假绿（本仓已踩过一次）。
    """
    out = []
    for k in sorted(set(a) | set(b)):
        if a.get(k) != b.get(k):
            out.append({"path": k, "a": a.get(k), "b": b.get(k)})
    return out


def det_scan_noise(text, entries):
    """**纯函数**：按噪声表扫一段文本 → 命中的噪声类 `id` 清单（供先验红 / 自检）。"""
    hits = []
    for e in entries:
        for p in (e.get("match") or []):
            try:
                if re.search(p, text):
                    hits.append(e["id"])
                    break
            except re.error:
                hits.append(str(e.get("id")) + "(正则非法)")
                break
    return hits


def _det_walk_na(node, path, bad):
    """递归找 `determinism: n/a` 声明 ⇒ 返回条数；缺 `reason` 的追加进 `bad`。"""
    n = 0
    if isinstance(node, dict):
        if str(node.get("determinism") or "").strip().lower() in ("n/a", "na"):
            n += 1
            if not str(node.get("reason") or "").strip():
                bad.append(f"{path}: `determinism: n/a` 缺 `reason` ⇒ 判违规（天然不可双跑者必须写理由，禁止静默跳过）")
        for k, v in node.items():
            n += _det_walk_na(v, f"{path}.{k}", bad)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            n += _det_walk_na(v, f"{path}[{i}]", bad)
    return n


def check_determinism(ctx):
    """A5: 确定性 —— 噪声口径**单一真值表**的健康 + **`n/a` 纪律**的机械义务。

    ★ 判什么：① 表结构（7 类噪声各带 `id/why/applies_to` · 行尾策略 · `updated` 读数日期）；
      ② `applies_to` 的**消费者 id 必须真实存在**（**孤儿消费者** = 无消费者的真值表会腐化，本仓纪律）；
      ③ **每类可机检噪声的正则必须真能匹配代表样本**（防表里塞一条永远匹配不上的坏正则而无人察觉）；
      ④ `determinism: n/a` 声明**必须带 `reason`**（`n/a` 不是静默通过的许可）。
    📊 报数：`噪声 N 类（可机检 M · 无字面模式 K）· 消费者 C 个 · 正则样本自证 P/Q · n/a 声明 A 条`。
    ⚠⚠ **不判什么**：本项**不**真的跑某条管线双跑（那要具体管线接入）——
      只钉住**口径单一真值 + 表的可用性**；`match` 为空的类（并发键序 / 文件系统元数据）
      **无字面模式** ⇒ **单列报数**（跳过 ≠ 判过且通过）。
    """
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过确定性噪声表断言", []
    if not DET_NOISE_INV.exists():
        return "FAIL", "inventory/determinism-noise.yaml 缺失（本断言的**噪声口径单一真值**依据）", []
    try:
        tbl = yaml.safe_load(_read_text(DET_NOISE_INV)) or {}
    except Exception as e:
        return "FAIL", f"inventory/determinism-noise.yaml 解析失败: {type(e).__name__}: {e}", []

    detail = []
    if not str(tbl.get("updated") or ""):
        detail.append("表头缺 `updated`（读数日期）⇒ 增长型真值表必须带（否则无法判断读数时效）")
    le = tbl.get("line-ending") or {}
    if str(le.get("normalize_to") or "").upper() != "LF":
        detail.append("`line-ending.normalize_to` 必须是 `LF`（逐字节比对要求二进制一致；归一化在生产端固化）")
    if not str(le.get("why") or ""):
        detail.append("`line-ending` 缺 `why`（归一化/豁免必须写理由）")

    types = tbl.get("noise_types")
    if not isinstance(types, list) or not types:
        return "FAIL", "`noise_types` 缺失或为空（噪声表退化成空 ⇒ 恒真）", detail

    known = {c["id"] for c in CHECKS}
    consumers, machine, no_match, sample_ok, sample_tot = set(), 0, 0, 0, 0
    seen = set()
    for i, e in enumerate(types):
        at = f"noise_types[{i}]"
        if not isinstance(e, dict):
            detail.append(f"{at} 不是映射")
            continue
        tid = str(e.get("id") or "")
        if not tid:
            detail.append(f"{at} 缺 `id`")
        elif tid in seen:
            detail.append(f"{at} 的 `id`={tid!r} **重复**（同一噪声两个定义点）")
        seen.add(tid)
        if not str(e.get("why") or ""):
            detail.append(f"{at}({tid}) 缺 `why`（为什么排除它必须写）")
        ap = e.get("applies_to")
        if not isinstance(ap, list) or not ap:
            detail.append(f"{at}({tid}) 缺 `applies_to` ⇒ 消费者未声明（适用面必须**由表声明**）")
        else:
            for cid in ap:
                consumers.add(cid)
                if cid not in known:
                    detail.append(f"{at}({tid}) 的 `applies_to` 含 {cid!r} —— **不是真实断言 id**"
                                  f"（孤儿消费者 = 无消费者的真值表会腐化）")
        pats = e.get("match") or []
        if not pats:
            no_match += 1
            continue
        machine += 1
        for p in pats:
            try:
                re.compile(p)
            except re.error as ex:
                detail.append(f"{at}({tid}) 的正则 {p!r} **非法**: {ex}")
        samples = _DET_SAMPLES.get(tid)
        if not samples:
            detail.append(f"{at}({tid}) 有 `match` 但**无自证样本** ⇒ 无法证明该正则真能匹配"
                          f"（防塞一条永远匹配不上的正则）")
            continue
        for s in samples:
            sample_tot += 1
            if tid in det_scan_noise(s, [e]):
                sample_ok += 1
            else:
                detail.append(f"{at}({tid}) 正则**匹配不上代表样本** {s!r} ⇒ 该噪声类实际检不出（坏正则）")

    if not consumers:
        detail.append("`applies_to` 全空 ⇒ **无消费者的真值表**（会腐化：没人用就没人维护）")

    # n/a 纪律：扫 inventory/*.yaml 里声明的 `determinism: n/a`（目前应为 0 条 ⇒ **显式报出**，不静默）
    na_items, na_bad = 0, []
    for p in sorted((ROOT / "inventory").glob("*.yaml")):
        try:
            data = yaml.safe_load(_read_text(p)) or {}
        except Exception:
            continue
        na_items += _det_walk_na(data, p.name, na_bad)
    detail += na_bad

    note = (f"噪声 {len(types)} 类（可机检 {machine} · 无字面模式 {no_match}）"
            f" · 消费者 {len(consumers)} 个 · 正则样本自证 {sample_ok}/{sample_tot}"
            f" · `determinism: n/a` 声明 {na_items} 条（缺 reason {len(na_bad)} 条）"
            f" · updated={tbl.get('updated')}")
    if sample_tot == 0:
        return "FAIL", note + " · **样本自证 0 条 ⇒ 判据无对象**（防退化空判）", detail
    fail = bool(detail)
    return ("FAIL" if fail else "PASS"), note, detail


# ── A3（2026-09-29）：派生**只读视图** —— 清单类文档的"第二定义点"正解 ──────────────
#   为什么需要它：本仓头号失败形态是**同一事实两处表达**（第二定义点）。但清单类文档
#   天生要在多处出现（手册 / README / 看板）—— 手抄必漂。正解不是禁抄，而是把抄的那份
#   变成**派生件**：从真值**渲染**出来，并用 `--check` **逐字节**验证"没被手改、也没过期"。
#   ★ 判据 = **退出码 0**（三态互不混淆，由 `ops/derived_view.py` 定义）：
#       0 = 一致 · 1 = 过期/漂移（`source-hash` 不符 或 正文逐字节不一致）· 2 = 渲染链路故障。
#   ⚠ 1 与 2 **绝不可混为一谈**：把"渲染器坏了"算成"视图过期"会让人去重渲染（掩盖故障），
#     把"视图过期"算成"渲染器坏了"会让人去查代码（实则只需 `--emit`）。故两种都 FAIL，但 note 分开报。
DERIVED_VIEW = ROOT / "ops" / "derived_view.py"


def check_derived_view(ctx):
    """A3: 跑 `ops/derived_view.py --check`（重渲染 vs 落档视图**逐字节**比对）—— **退出码 0 才算过**。

    子进程而非 import：视图渲染器是**独立可跑**的工具（人也会手跑 `--emit`），门禁只做**消费者**，
    复用它的三态退出码 ⇒ 口径**单一定义点**（不在这里再实现一遍比对 —— 那正是本仓头号形态）。
    """
    if not DERIVED_VIEW.is_file():
        return "WARN", f"{DERIVED_VIEW.name} 不存在（本断言的登记依据）", []
    try:
        p = subprocess.run([sys.executable, str(DERIVED_VIEW), "--check"], cwd=ROOT,
                           capture_output=True, timeout=120)
    except subprocess.TimeoutExpired:
        return "FAIL", "派生视图校验超时（>120s）⇒ 可能挂死", []
    out = _decode_out(p.stdout or b"") + _decode_out(p.stderr or b"")
    lines = [ln.rstrip() for ln in out.splitlines() if ln.strip()]
    msg = lines[-1] if lines else "（无输出）"
    rc = p.returncode
    if rc == 0:
        return "PASS", msg, lines[-5:]
    kind = "渲染链路故障(rc=2)" if rc == 2 else f"视图过期/漂移(rc={rc})"
    return "FAIL", f"{msg} · **{kind}**", lines[-8:]


# ── A2（2026-09-29）: 执行侧**过程留痕** —— 「判据只能看产物，看不到过程」的正解 ─────────────
#   事故形态（真实、已抽象）：判据**只看得到产物**，看不到**过程**。既有两件与"过程"最近的证据
#   都不顶用 —— ① 输出字节时间序列（每 5 秒一行）只记**吞吐曲线**，不记"做了什么"；
#   ② 工作区改动摘要**实测为空**（0 行）。⇒ 执行体**改过哪些文件 / 跑过哪些命令**，主控侧
#   **查不到**。这正是幻觉抑制最缺的一类证据：**它怎么得出这个结论**，在视野之外。
#   口径（照 `dogfood-cards/imp4-executor-trace-design.md`，**单一实现**）：最小充分集**5 项**，
#   每项尽量由**执行体外 / 主控侧**产生（可核）；唯一做不到"不信任仍可核"的**工具调用链**
#   必须**如实标 `uncore`**（执行体内部产生 ⇒ 可篡改 / 漏报 / 伪造），**不得伪称已核**。
#   ★ 先验红点（A2）：删掉任一个采集点标记 ⇒ 本判据**必须**红（见 `tests/`）。
#   ⚠ 本处**只判**「5 个采集点在不在」与「不可核项有没有如实标」——**逐条字面细节**
#     （两段写入 / `$Script:EV_FILES` 登记 / 主控归档 / `free -m` 而非 `/proc`）由**离线夹具**
#     `ops/station-bin/_fm_golden_test.ps1` 守（那是 ps1 的黄金夹具，见 `ps1-golden`）⇒ **不抄第二份**
#     （本仓头号失败形态 = 同一事实两处表达）。
EXEC_TRACE_SECTIONS = (
    ("[cmd] cmd=",               "命令执行记录（执行体外壳）"),
    ("[env] caught_at=launcher", "环境快照（执行体启动器 fork 前）"),
    ("[fs] diff_pointer=",       "文件系统写入集合（既有 find -newer 派生）"),
    ("[tool] chain=uncore",      "工具调用链（执行体内部 ⇒ 如实标不可核）"),
    ("[artifact] hashes=",       "产物哈希清单（主控侧回收时算）"),
)


def check_executor_trace(ctx):
    """A2: 执行侧过程留痕 —— 机制里五采集点齐备；落到 runDir 的留痕件**须含全部五段**。

    三部分（**判的东西不同，不许混**）：
      · **机制**：`agent-cli.ps1` 里 5 个采集点标记**逐个在位**，且不可核项**如实标 `uncore`**
        （出现 `chain=core` / `chain=verified` ⇒ **伪称执行体内部可核** ⇒ FAIL）。
      · **覆盖**：扫到的 runDir 若**有** `executor-trace.txt` ⇒ 内容**须含全部五段**
        （缺段 = 真缺陷 ⇒ FAIL）；**一个都没有** ⇒ **报数不入分母**（本件尚未经真派发 ⇒
        覆盖率是"没验到"，不是"验出问题" —— 不得把它算成通过，也不得算成失败）。
      · **锚定**（2026-09-30 补：A2 的 runtime 验收要求 = "留痕件齐 **+ 与产物哈希交叉锚定**"，
        上面两部分只判"五段在不在"、**不判锚**）：① `[artifact] hashes=` 必须是 `main-side`
        （执行体自报哈希 ⇒ 伪称可核 ⇒ FAIL）；② 留痕件 `ts=` 必须 == runDir 名（归属不符 ⇒ FAIL）；
        ③ 主控侧须有该 run 的哈希记录（`.agent-run.json` 的 `content_digest` 形如 `sha256:<64hex>`）
        —— **缺 ⇒ 只报数**（"没验到 ≠ 验出问题"）。
        ⚠ **不判什么**：**不判留痕内容真伪**（`[cmd]`/`[env]` 的值对不对）、**不判门的效力**。
    """
    detail = []
    if not AGENT_CLI.is_file():
        return "FAIL", "缺 agent-cli.ps1 ⇒ 留痕机制不可判（**不可判 ≠ 通过**）", []
    txt = _read_text(AGENT_CLI)
    mech_ok = 0
    for lit, why in EXEC_TRACE_SECTIONS:
        if lit in txt:
            mech_ok += 1
        else:
            detail.append(f"缺采集点标记 {lit!r} ⇒ {why} **没被采集**"
                          f"（假绿：看着有留痕，实际缺该维度）")
    for fake in ("chain=core", "chain=verified"):
        if fake in txt:
            detail.append(f"出现 {fake!r} ⇒ **伪称执行体内部可核**"
                          f"（工具调用链在执行体内部，executor 可篡改 / 漏报 / 伪造 ⇒ 只能 `uncore`）")

    # ── 覆盖：落到 runDir 的留痕件（存在则须齐段；一个都没有只报数）──────────────────
    sys.path.insert(0, str(ROOT / "ops"))
    try:
        import cluster
        roots, _note = cluster._agent_proj_roots()
        runs = cluster._chain_runs(roots)
    except Exception as e:
        st = "FAIL" if detail else "WARN"
        return st, (f"机制：采集点 {mech_ok}/{len(EXEC_TRACE_SECTIONS)}"
                    f" · cluster 不可用({type(e).__name__}) ⇒ 覆盖断言跳过"), detail
    n_run, n_ok, n_bad = 0, 0, []
    # 锚定段（2026-09-30）：① 执行体不得自报哈希 ② 留痕件必须属这一次 ③ 主控侧须有哈希记录。
    #   实测（2026-09-30 · 11 个含件 runDir）：ts 11/11 相符 · content_digest 11/11 规范 ·
    #   hashes 11/11 = main-side ⇒ **存量零违规**（先量后定档）⇒ ①② 判 FAIL；③ 只报数。
    n_tsok, n_self, n_tsbad, n_noanch = 0, [], [], []
    for ts, proj, run_dir in runs:
        f = run_dir / "executor-trace.txt"
        if not f.is_file():
            continue
        n_run += 1
        t = f.read_text(encoding="utf-8", errors="replace")
        miss = [lit for lit, _ in EXEC_TRACE_SECTIONS if lit not in t]
        if miss:
            n_bad.append(f"{proj}/{ts} 的 executor-trace.txt 缺段 {', '.join(miss)}")
        else:
            n_ok += 1
        lbl = f"{proj}/{ts}"
        ma = re.search(r"\[artifact\]\s+hashes=(\S+)", t)
        if ma and ma.group(1) != "main-side":
            n_self.append(f"{lbl} 的 executor-trace.txt 写 `[artifact] hashes={ma.group(1)}`"
                          f" ⇒ **执行体自报产物哈希**（执行体不可信 ⇒ 哈希只能由主控侧回收时算；"
                          f"伪称可核，与 `chain=uncore` 同族）")
        mt2 = re.search(r"#\s*executor-trace v1 ts=(\S+)", t)
        if mt2 and mt2.group(1) != ts:
            n_tsbad.append(f"{lbl} 的 executor-trace.txt 记 `ts={mt2.group(1)}` ≠ runDir 名"
                           f" ⇒ **归属不符**（留痕件不属于这一次；与 O-57「归属核对」同族）")
        else:
            n_tsok += 1
        try:
            _aj = json.loads((run_dir / ".agent-run.json").read_text(
                encoding="utf-8-sig", errors="replace"))
        except Exception:
            _aj = {}
        if not re.match(r"^sha256:[0-9a-f]{64}$", str(_aj.get("content_digest") or "")):
            n_noanch.append(lbl)
    detail += n_bad + n_self + n_tsbad
    note = (f"机制：采集点 {mech_ok}/{len(EXEC_TRACE_SECTIONS)}"
            f" · 覆盖：runDir 含该件 {n_run} 个（齐段 {n_ok}"
            + (f" · **缺段 {len(n_bad)}**" if n_bad else "") + "）"
            + f" · 锚定：ts 相符 {n_tsok} · 自报 {len(n_self)} · ts 不符 {len(n_tsbad)}"
              f" · 无锚记录 {len(n_noanch)}")
    if n_run == 0:
        note += " · 0 个 ⇒ 本件尚未经真派发，覆盖率**未验**（报数不入分母）"
    return ("FAIL" if detail else "PASS"), note, detail


CHECKS = [
    {"id": "secrets", "title": "明文扫描", "fn": check_secrets, "quick": True,
     "fix": "删除明文密钥, 或加入 SECRET_ALLOW 并写明原因(不允许静默放行); "
            "文档里引用样串/占位串时**掩码为 sk-xxx-****** (2026-09-16 增: 未掩码的样串会命中本判据); "
            "⚠ 报『豁免未命中 N』= 那条白名单**已不再需要** ⇒ **把它从 SECRET_ALLOW 删掉**（D6-P0-2 防腐化）"},
    {"id": "syntax", "title": "语法检查", "fn": check_syntax, "quick": True,
     "fix": "按明细里的行号修语法; 扩展名与内容不符的应解包或改名"},
    {"id": "scripts", "title": "脚本治理", "fn": check_scripts, "quick": True,
     "fix": "管理操作请走统一入口 (ops/cluster.py <sub> / web 卡片), 不要新增一次性脚本; "
            "确需独立脚本则在 inventory/ops.yaml 登记并在提交信息里说明理由 (ADR-0004)"},
    {"id": "deps", "title": "cluster 模块依赖方向", "fn": check_cluster_deps, "quick": True,
     "fix": "P2-1: ① 新 `ops/cluster_*.py` 模块 ⇒ 必须在 `inventory/ops.yaml` 的 `cluster_layers` 登记层次; "
            "② 模块级 import 成环 ⇒ 拆环，或把其中一条改成**函数内懒加载**（并登记 `cluster_lazy_allow`）; "
            "③ 层序越界（反向/同层）⇒ 调整层次或改依赖方向（只允许依赖**严格下层**）; "
            "④ 反向懒加载未登记 ⇒ 登记原因，或调层; ⚠ 报『未命中登记 N』= 那条登记已可移除（删掉）"},
    {"id": "adr", "title": "ADR 替代方案节", "fn": check_adr, "quick": True,
     "fix": "P2-2: ADR 必须有 `## 考虑的替代方案（Alternatives Considered）` 节"
            "（模板: spec/vulkan-version-control/ADR_TEMPLATE.md），节体内**至少 1 个列表项 或 2 个表格行(表头+数据)**"
            " —— 要写「考虑过/否决了什么」，不是只写标题; **恰 1 个**（改名后别留旧节）; "
            "旧名 `否决/比较对象` / `被否的方案` 一律换规范名; "
            "⚠ 范围只含 adr/ADR-*.md —— DECISIONS.md 是表格载体（列在结构上已保证槽位、值可为 `—`），不在范围"},
    {"id": "model-families", "title": "模型家族表（双向对账）", "fn": check_model_families, "quick": True,
     "fix": "D7-P3-1 前置：`inventory/model-families.yaml` 的成员必须与 `inventory/models.yaml` 的 alias "
            "**双向对上** —— ① 成员不在 `models.yaml` ⇒ **孤儿引用**（删掉或改 alias）; "
            "② `models.yaml` 里的 alias **没被任何族收** ⇒ 按**权重血统**归族"
            "（蒸馏/微调**归基座族**，微调者记 `note`，**不改族**）; ③ 一族缺 `basis` ⇒ 补划分依据。"
            "⚠ 本判据**不判族分得对不对**（那要人读血统），只判「**没有一个 alias 没被归类**」与「引用不悬空」。"
            "⚠⚠ 它也**不提供**「站↔**已加载**模型」—— 那**不是** `models.yaml` 的 `stations`（库中有）"
            "或 `conf`（配过实例）; 见 yaml 的 `linked_state`（**未实测**）"},
    {"id": "ledger-status", "title": "台账状态可机读", "fn": check_ledger_status, "quick": True,
     "fix": "O-93: `spec/d6-agent-standard/OPEN-ISSUES.md` 的**每行**状态格必须**以标记开头**"
            "（`✅`=已闭环 · `◐`=已登记未处置 · `⏳`=待触发或待裁 · `🔵`=部分收口）——**允许加粗包裹**"
            "（如 `**✅ …**`，判据会先剥 `**`/`_`/空白）。"
            "\n\n⚠ **只认格首** ⇒ **引文里的 ✅ 不会被误当状态**（这正是「按整行找 ✅」那种口径会错的地方）。"
             "⚠ 状态格子**不在固定第几格**：本表列数不齐（表头声明 8 列、行有 6/8 格、另有行含裸竖线被拆），"
             "同一列在老行是状态、新行是证据 ⇒ 判据取「**第一个**格首带标记的格」。"
             "\n📊 note 里报出「数据行 N · 状态可机读 M · ✅ 闭环 X · **仍开着 Y**」，明细含**仍开着的 ID 清单** "
             "⇒ 排优先级**不再依赖人读**。"
             "\n⚠⚠ **它不判什么**：「应该闭环多少」**不判** —— 「开着」**不是错误**；也**不判**状态写得对不对"
             "（那仍要人读）。别把本判据读成「台账已被审计」。"
             "\n⚠ 若明细指出某行「状态不可机读」⇒ 给那行补一个格首标记即可（**不要**只改文案）。"},
    {"id": "spec-untested", "title": "规范类文档的未实测登记节", "fn": check_spec_untested, "quick": True,
     "fix": "O-91: **规范类文档**（`spec/d6-agent-standard/U[0-9]-*.md` 与 `D7-PROTOCOL-*.md`）必须带"
            "**非空**的 `## 未实测登记` 节 —— 形状与判据 `adr` 同源（锚精确节名 · **恰 1 个** · "
            "节体 **≥1 列表项 或 ≥2 表格行** · 扫描**只到下一个 H2**，故 `### 子节` 属节体）。"
            "① 缺节 ⇒ FAIL；② 多于 1 个 ⇒ FAIL；③ 只写标题没写内容 ⇒ FAIL；"
            "④ **命中集为 0 ⇒ FAIL**（判据**没有对象** = 退化空判，本仓头号形态）。"
            "\n\n⚠⚠ **它不判什么（别读过头）**：**不判**「正文里有没有无证据断言」—— 那**不可机判**，"
            "**仍然是纪律**。本判据只保证「**那一节在、且非空**」。"
            "\n📊 note 里附一条 **报数（不判）**：E 级内联标注的「带具体取证 / 裸」分布 —— "
            "实测 ADR 侧 **57% 是裸标**，而「裸」**不等于「错」**，且**连计数都口径敏感**"
            "（同一棵树两个正则数出 4 vs 8）⇒ 做成 FAIL 会造假红，假红 → 例外名单 → 判据失效。"
            "\n★★ **O-123（2026-09-30）新增第四件事**：本判据**顺带消费** `inventory/untested-index.yaml` 的分诊"
            "（该索引由此**不再是叶子节点**）—— **报数** state / blocker / needs_decision 分布；"
            "**一条判据**：任一条 `needs_decision: true` ⇒ **WARN**（口径 =「**未裁项不许静默**」）。"
            "⚠ 索引缺失/不可解析/`items` 为 0 ⇒ **WARN（非 FAIL）** —— 索引自身的对账与闭集校验由 `py-tests` 判，"
            "**不在此处重复判**（判据只在一处）。"
            "\n⚠ **逃逸（如实记）**：新规范若取名不带 `U\\d-` 前缀，本判据**看不到它** —— "
            "spec 与 adr 实测**全部无 front-matter**（无 `type:` 可锚）⇒ 靠「命中集在输出里可见」缓解。"},
    {"id": "doclinks", "title": "文档链接可达", "fn": check_doclinks, "quick": True,
     "fix": "资源移动/改名后, 文档里的相对链接要跟着改 (注意别写重前缀: spec/<x>/ 里是 "
            "`../y` 不是 `../spec/y`, 引 docs/ 是 `../../docs/z`); 确有不可修的登记 DOCLINK_ALLOW; "
            "⚠ 报『豁免未命中 N』= 那条例外**已不再需要** ⇒ **把它从 DOCLINK_ALLOW 删掉**（D6-P0-2 防腐化）"},
    {"id": "inventory", "title": "真值登记", "fn": check_inventory, "quick": True,
     "fix": "端口/模型标识有变更时同步 inventory/*.yaml 真值表"},
    {"id": "artifacts", "title": "生成物清单", "fn": check_artifacts, "quick": True,
     "fix": "生成物**禁止手工编辑** —— 改源头 → 重跑 → 跑 --check (D6-P1-1); "
            "清单每条须给 `check`(真实断言 id) 或 `exempt`(豁免理由), 两者都缺 = 静默缺口会 FAIL"},
    {"id": "sensitivity", "title": "内容档位真值表", "fn": check_sensitivity, "quick": True,
     "fix": "O-51: sensitivity.yaml 是「内容→档位」的真值(权威源在自身) —— 断言其自洽: "
            "① path 必须真实存在 ② tier 必须 ∈ 封闭枚举 ③ **同一 path 不得两处不同 tier** "
            "④ default_tier 必须为 local-only (fail-closed)"},
    # O-66 (2026-09-25): 卡面 `input-provenance` 义务的**机判** —— 此前只在文档里（`ops/` 全域零命中）。
    {"id": "input-provenance", "title": "卡面输入来源义务", "fn": check_input_provenance, "quick": True,
     "fix": "O-66: 卡声明 `attach-egress: ok` 且 `sensitivity` ∈ {public, sanitized} 时，它**要带附件出网** ⇒ "
            "按 `CROSS-PROJECT-WORK-STANDARD §4` 必填 `input-provenance`：① 逐项本仓相对路径；"
            "② 每项须在 `inventory/sensitivity.yaml` 有 `tier`；③ 卡档位**不得宽于**该项 tier。"
            "确无本仓输入 ⇒ **显式写 `input-provenance: none`**（不要留空；留空 = 缺字段 ⇒ FAIL）。"
            "⚠ 报『none 可证伪性存疑』= **WARN 不阻断**：声明 none 却在正文提到 tier 严于本卡的已登记路径 —— "
            "『提到』不等于『读到』，机械判不出 ⇒ 请人工核一次：若确实读了，把它列进 `input-provenance` 或降档。"},
    # D7-P1-1 (2026-09-26): U-2 证据强度字典 + 方言映射表 —— 映射表自己的两种病
    #   （**漏项** / **源词表改了而映射表没重抽**）。
    {"id": "dialect", "title": "U-2 方言字典与映射表", "fn": check_dialect, "quick": True,
     "fix": "D7-P1-1: `inventory/dialect.yaml` 是「符号 × 出处 → 含义」的投影（**权威源在别处** ⇒ "
            "已登记进 `inventory/artifacts.yaml`，**禁止手工编辑语义**：改源 → 重抽 → 重跑）。"
            "本项判四件事：① `axis` / `namespaces` 是封闭枚举与白名单，映射行的 `namespace` **必填**"
            "（§11.4 教训①：前缀不靠人自觉写）；② `axis=not-assigned` 必须写 `axis_note`（说明属于什么轴），"
            "`axis_value=undefined` 必须写理由（堵「看着像就填」）；"
            "③ `coverage` 逐族行数与实际**双向**相等（`b1b` 实测漏过一行）；"
            "④ `sources` 的**源切片指纹**不符 ⇒ 红（这就是「源词表变了下游红」）。"
            "⚠ 报「读取失败 ⇒ 不可判」= **要修**，不是通过 —— 判不了不许当通过"},
    # D7-P1-3 (2026-09-26): U-3 依赖边格式 —— 最该被机器盯住的是**最容易缺的那个字段**。
    {"id": "u1-identity", "title": "U-1 产物身份（可复算）", "fn": check_u1_identity, "quick": True,
     "fix": "D7-P1 实现侧（U-1 落地）：`inventory/*.yaml` 里声明了 `u1:` 的，**身份必须可复算**。"
            "① 声明四项 `{namespace, identifier, version, identity}` 必须齐（只写 identity **无法复算**）；"
            "② `identity` 必须 **等于** 按 `(namespace, identifier, version)` 复算的结果 —— "
            f"★ 只判格式是**假绿**（随手编一个合规长度的 hex 就能过）；'身份'可判的含义只有『能从 (ns,id,ver) 复算』；"
            f"③ 声明了身份 ⇒ 文件**前 5 行内必须有** `# {U1_PREFIX}` 头部注释行（D-25：前缀进头部注释、"
            "不进哈希行 —— 进了哈希行整份 `sha256sum -c` 会一行都不被验，一手实测见 U1 spec §1.4）；"
            "④ **一个声明都没有 ⇒ FAIL**（本条会静默退化成空判 = 本仓头号失败形态）。"
            "\n\n算法/截断的**唯一真值**在 `ops/rpc_check.py` 的 `u1_identity()`（门禁与产出方同源）；"
            "取值与理由见 `spec/d6-agent-standard/U1-ARTIFACT-IDENTITY.md`。"
            "⚠ 哈希不可逆 ⇒ 本条只能判『声明可复算』，**不能**判『某个文件内容变了 ⇒ 身份该不该变』（那是 U-4 的事）"},
    {"id": "id-census", "title": "ID 站点计数（口径可复算）", "fn": check_id_census, "quick": True,
     "fix": "O-85: `inventory/id-site-census.yaml` 是**唯一真值**，口径的**唯一实现**在 `ops/id_site_census.py`。"
            "① 数值不符 ⇒ 项目变了（正常）⇒ 跑 `py ops/id_site_census.py --emit` 重出真值，"
            "**并回头复核下游结论**（U4 spec §1 表引用了这些数）；"
            "② **口径漂移（正则 / glob / 排除目录 / 是否含测试）⇒ 比数值漂移严重** —— "
            "口径一变，真值里**所有**数字立刻失去意义 ⇒ 必须重出 + 复核；"
            "③ 项目目录不可达 ⇒ **WARN**（它们在 `F:` / `E:` 等**本机才有**的盘上，换机器就没有）"
            "—— ⚠ 但**绝不静默通过**：报告里显式写 `可达 N/M` 与逐项目 `--`（D-26）。"
            "\n\n★ 这条断言的**存在理由**：U4 §1 表原来那一列「计数」**没有口径** —— "
            "Open_Data 换四种口径实测得 12 / 14 / 117 / 139，而表里写的是 34 ⇒ **数字没有定义**。"
            "⚠ 它只回答『有多少处哈希用法』，**不回答**『哪些是产物 ID』（那是 U-4 的 `affected`，仍未解）。"},
    {"id": "id-storage", "title": "ID 存储面（affected 生产者）", "fn": check_id_storage, "quick": True,
     "fix": "U-4: `inventory/id-storage-census.yaml` 是**唯一真值**，口径的**唯一实现**在 `ops/id_storage_census.py`。"
            "① 数值不符 ⇒ 存储变了（正常）⇒ 跑 `py ops/id_storage_census.py --emit` 重出真值，"
            "**并回头复核 U-4 的 `affected`**；"
            "② ★★ **角色不实 ⇒ FAIL**：声明 `primary_key` 就必须**回库里核过**（duckdb 查 "
            "`duckdb_constraints()` · sqlite 查 `PRAGMA table_info`）—— 声明与实测不一致，说明这张表在**自说自话**；"
            "③ **口径漂移**（形态档 / 取样上限 / role 取值域）⇒ 比数值不符**优先**判红；"
            "④ 存储不可达 ⇒ **WARN 不 FAIL**（库在 `F:`/`E:` 等别的盘）—— 但报 `不可达 N/M`，**绝不静默通过**。"
            "\n\n★ **它是什么**：把 2026-09-26 那次『开库手工数 affected』（duckdb + sqlite）变成**可复算的机制**。"
            "`py ops/id_storage_census.py --invalidate --changed <带 u1: 声明的文件>` 会串起三段："
            "**changed_ids（取声明）→ affected（本普查实测）→ `decide_invalidation()` 的处置**。"
            "⚠ 它只产出**决策**，不执行重算（执行侧仍未实现 —— U4 未实测第 10 条）；"
            "⚠ `affected` 的完整性取决于 `STORES` 清单，而**清单是线索不是事实**（已吃过两次亏）。"},
    {"id": "edges", "title": "U-3 依赖边格式", "fn": check_edges, "quick": True,
     "fix": "D7-P1-3: `inventory/edges.yaml` 的**实例**要满足 `U3-EDGE-FORMAT.md`（形状的单一真值）："
            f"① `src`/`dst` 必须是 **U-1 产物身份**形态 `{U1_PREFIX}:<{U1_TRUNC} 位小写 hex>`"
            "（U-1 与 U-3 咬合：写一条边就得先有一个合规身份）——"
            "★ 判据由 `u1_parse()` 给出，与 U-1 实现**同源**（此前这里另写了一份正则 = 同一事实两个定义点）；"
            "③ `provenance` 必填，形式 `<前缀>:<载荷>`，前缀 ∈ `provenance_prefixes`，"
            "**载荷允许含 `:`**（只按第一个 `:` 切分）；"
            "★ 「缺」= 字段不存在 / 空串 / 仅空白 / `null` / `unknown`·`none`·`n/a`·`null` / 前缀不在封闭集 / 载荷为空"
            " ⇒ **该边无效** ⇒ **FAIL**（⚠ 产出方的处置是 FAIL，**不是「丢掉这条边继续」** —— "
            "依据 D-26「禁止静默 skip」；「丢弃 / 降级」是**消费方**那一侧的 H-3 规则）；"
            "④ `(src,dst,kind)` 不得重复；⑤ **`edges` 为空必须给 `empty_reason`** —— "
            "空 ≠ 没事，门禁会把「0 条」显式报出来"},
    # D7-P1-5 (2026-09-26): U-5 晋升门 schema —— 判的是**schema 自身 + 三处实现的映射**（对象真实存在）。
    {"id": "promotion", "title": "U-5 晋升门 schema", "fn": check_promotion, "quick": True,
     "fix": "D7-P1-5: `inventory/promotion.yaml` 是共享记忆**准入形状**的单一真值。"
            "① `gate.required` / `gate.capacity`（field+max+policy）/ `gate.criteria` / `gate.structure` 四件都要有；"
            "② 判据的 `field`/`ref` 只能引用 `fields` 里的字段，`op`/`policy` 是封闭枚举，`$ref` 类型须与 field 一致；"
            "★ ③ **D-38 要求三种判据并存**（`success_rate` / `recurrence` / `verified`）—— 缺一即『发明第四种』；"
            "★ ④ **映射闭包**：`mapping_closure` 里三处实现的 `uses`/`criteria_used` 必须覆盖 schema 的**全部**"
            "字段与判据 —— **出现孤儿字段/孤儿判据 = 有一处没人用，就是变相发明第四种**；"
            "⑤ `entries` 为空必须给 `empty_reason`；⑥ `unverified` 必须登记本 schema 里**新设**的项"},
    {"id": "facade", "title": "门面符号可达性", "fn": check_facade, "quick": True,
     "fix": "P1-3: `cluster.py` 是统一门面, `cluster_web.py` 以 `import cluster` 复用其符号 —— "
            "缺符号即 FAIL 并点名『哪个符号·被谁引用』; 修法: 在 cluster.py 重导出(或改回引用处)"},
    {"id": "mirror", "title": "事实源↔镜像一致", "fn": check_mirror, "quick": True,
     "fix": "P1-2: ① M-1 手册 §1.3 判官行须与 `JUDGE_TABLE['main']` 的 id/egress/compliance 三项一致; "
            "② M-5/M-6 受理状态机真值(`inventory/inbox.yaml`)须与 inbox/README §3 白名单/状态表一致, "
            "且 `cluster_web.py`/`rpc_check.py` 消费同一真值(不得回归硬编码); "
            "③ #7/#9 真值的 `requires`(必需件)须齐全, 手册 §1.3 状态机段须逐个提到真值状态, "
            "README §5.3『交付态强判据』行须 == 真值 `manifest` 集 —— "
            "**改状态/必需件只改 `inventory/inbox.yaml` 一处**, 文档跟着改; "
            "④ O-50 手册声明的断言计数须 == 真实 `CHECKS`（**加/删断言后同步手册 §2.4 的 "
            "`# N 项断言 (quick Q + 全量 R)`**）; 手册**禁**再写『真实剩余 open = N 项』枚举或写死『门禁 N 绿』; "
            "⚠ M-2 已被 O-50 判为『不再维护第二份枚举』故不并入"},
    {"id": "ports", "title": "端口分配表自洽", "fn": check_ports, "quick": True,
     "fix": "按明细修 inventory/ports.yaml (缺字段/同组重复/跨组重叠/枚举拼错)"},
    {"id": "plugins", "title": "插件同构基线", "fn": check_plugins, "quick": True,
     "fix": "改插件/技能后同步 inventory/plugins.yaml; 无法立即修的真实差异登记 known_drift"},
    {"id": "impact", "title": "影响面反查", "fn": check_impact, "quick": True,
     "fix": "impact.yaml 登记的 consumer 路径不存在 —— 修正路径或删掉该条"},
    {"id": "aliases", "title": "别名解析契约", "fn": check_aliases, "quick": True,
     "fix": "以站上 conf 为准改 cluster.py 的 ROUTE/RPC_MODELS/STATION_ROUTES"},
    {"id": "evidence", "title": "agent 证据链", "fn": check_evidence, "quick": True,
     "fix": "digest/链/锚不符 = 归档证据或链被改动 ⇒ FAIL —— 用 `cluster.py agent verify` 定位到条与件, "
            "再追查改动来源(别急着 `--reanchor`, 那是把信号抹平); 有 run 未入链只是**覆盖缺口** ⇒ WARN, "
            "跑 `cluster.py agent chain` 补录(钩子已自动入链, 出现未入链说明钩子没跑或被 --no-verify 绕过); "
            "「可重放性审计: 新增 N 条」= **增量**可重放性缺口(同属覆盖缺口 ⇒ WARN, 刻意不进 FAIL 集) "
            "⇒ 先看逐条明细, **确认可接受**后跑 `cluster.py agent audit --accept` 推进水印(存量即不再重复报); "
            "若明细里是「已归档但未被任何 subject 覆盖」= 新证据件没进产出方基线 ⇒ 应改 "
            "`ops/station-bin/agent-cli.ps1` 的 `Get-FrameworkSubjects`(清单唯一真值在那里), 而不是接受它; "
            "「judge 校准已过期」= 判据(A/B)或稳定题集改过、校准报告没重跑 ⇒ 跑 "
            "`cluster.py agent audit-judge --save`(需站上在服务跨家族引擎)。这条把"
            "「改判据必须重跑校准」从**空头承诺**变成可判——报告自带 calib 指纹, 比对即可"},
    {"id": "inbox", "title": "受理区状态自洽", "fn": check_inbox, "quick": True,
     "fix": "按明细修: 缺 00_handoff/ = 转运包没冻结; STATE.json 缺失/非法/不在白名单 = 状态没走机读格式; "
            "状态内容不自洽(如 accepted 无受理决定) = 先补 10_admin/受理决定.md 再改状态 "
            "(依据 inbox/README §3 状态机, ADR-0008; 状态只由管理员改, 每次变更追加 40_state/LOG.md); "
            "★ **MANIFEST.sha256 重算不符 = 交付证据束被手改或源被改动**（生成物**禁手改**）⇒ "
            "**别去改清单**，走「改源头 → 重跑 → `cluster.py inbox seal <proj-dir> --go`」；"
            "核对用 `cluster.py inbox seal <proj-dir> --check`（与门禁同一实现）；"
            "报『MANIFEST 未校验 N』= 清单头写的项目根**不在本机**（换 clone/换机），不是篡改"},
    {"id": "ps1-golden", "title": "ps1 离线黄金夹具", "fn": check_ps1_golden, "quick": True,
     "fix": "P3-2: 跑 `powershell -NoProfile -ExecutionPolicy Bypass -File ops/station-bin/_fm_golden_test.ps1` "
            "看明细里的 FAIL 行。⚠ **先判「是回归还是夹具期望值陈旧」**："
            "若代码侧确有语义变更（看 agent-cli.ps1 里的注释/新件/O- 台账）⇒ 改**夹具期望值**并写明理由；"
            "若代码侧无变更 ⇒ **是回归**，改代码。⚠ 出站硬闸的判据本体在夹具里，本断言只负责让它**每次都被跑**"},
    # ── D7-P3-2 (2026-09-26): 编排层的两条判据（防 D7 变瓶颈 / 不新造账本）────────
    {"id": "conclusion-ledger", "title": "账本唯一性（不新造账本）", "fn": check_conclusion_ledger, "quick": True,
     "fix": "D7-P3-2『结论收束记账』：合并稿 §13.3 要求 D7 的结论留痕**复用既有追加式纪律、不新造账本**。"
            "`inventory/conclusion-ledgers.yaml` 是**账本的封闭集**（口径 = 只追加 ∧ 唯一写入者 ∧ 有独立校验）。"
            "① 报『**未登记的账本** <路径>』⇒ 有人在扫描口径内新造了一本 ⇒ **要么登记**，"
            "**要么把 `scan.globs` 口径说清**（口径不先定就量 = 本仓已吃过三次亏）；"
            "② 报『登记了 globs 却一条也没命中』= **登记腐化**（账本被删 / 改名 / glob 写错）；"
            "③ 报『登记的路径不存在』同②（`paths` 那一半）；"
            "④ 报『`not_a_ledger` 为空』= **没写下「什么不算账本」** ⇒ 下一个人会按『看着像』再建一本；"
            "⑤ 报『相撞』= 同一形态既登记为账本、又被声明不是账本（两处口径矛盾）；"
            "⑥ 报『扫描失败 ⇒ 不可判』= **要修**，不是通过。"
            "⚠ **它不判什么**：**不判账本内容**对不对，也**不判**『结论该不该进账本』（后者是纪律）。"
            "⚠ 扫描口径**窄**（只 `inbox/*/40_state/LOG.md`）⇒ **别名账本看不到**，"
            "这点已如实写在 yaml 的 `unverified` 里 —— 别把本项读成『账本已全覆盖』"},
    {"id": "review-catalog", "title": "标准复核目录（免终裁类目）", "fn": check_review_catalog, "quick": True,
     "fix": "D7-P3-2 / D-43：`inventory/review-catalog.yaml` 是**免终裁类目的清单**。"
            "① 准入门槛照抄 ITIL（**同一类被批准两次**）—— 报『`approvals` 未达门槛』或"
            "『`approval_anchors` 条数 ≠ `approvals`』= **只填数字拿不出锚点**（门槛没被真满足）；"
            "② 报『有类目但 `type_axis` 为空』= **类目没有浮出依据**（没有轴就没有『类』）；"
            "③ 报『孤儿字段』= `fields` 里有 `required` 没用的字段（装饰）；"
            "④ `entries` 为空**必须**给 `empty_reason` —— **空 ≠ 没事**，门禁会把「0 条」报出来；"
            "⑤ `ratio_target.judged` 标明这条目标是**判**还是**只报数**。"
            "⚠ **它不判什么**：**不判**类目选得对不对（那是人读血统 / 风险），"
            "也**不判**『该不该引入豁免』（D-48 要求先证它与结构 contain 不冲突）。"
            "⚠ 当前 `entries` **实测 0 条**（理由在 `empty_reason`，两条独立实测）——"
            "**别把本项读成『已有免终裁通道』**"},
    {"id": "memory-gates", "title": "记忆四道门 + 授权边界", "fn": check_memory_gates, "quick": True,
     "fix": "D7-P3-3 / D-47 / D-48：`inventory/memory-gates.yaml` 是**四道门**"
            "（write/retrieval/promotion/reuse）与**授权边界（结构性约束）**的单一真值。"
            "① 报『缺一道门』= D-47 要求四门齐；"
            "② 报『挂名假判』= 某门的 `judgment.ref` 指向一个**不存在**的 CHECKS id"
            "（判据写了但没人跑 —— 本仓最典型的一类假绿）；"
            "③ 报『`gate: none` 且本仓可控 ⇒ 红』= **私有→共享那一跳敞着**"
            "（MAPLE-Guard 点名的关键一跳）；**引擎侧**关不掉的无门通道只**点名 + WARN**（绝不静默）；"
            "④ 报『未登记的记忆面接触点』= 有代码新碰了记忆路径 ⇒ **要么登记**（写清为什么）**要么去掉**；"
            "⑤ 报『记忆出网嫌疑』= 同一行同现【记忆路径】与【跨机搬运令牌】（本模型里最贵的错误）；"
            "⑥ 报『隔离靠文本前缀』= 有人把**命名**升格成了**判据**（D-48：要靠结构 contain）；"
            "⑦ 报『登记的接触点不存在』= 登记腐化。"
            "⚠ 记忆路径的**唯一字面定义点**在 yaml 的 `egress.path_tokens`（角色名 → 路径）；"
            "改路径**只改那里**，不要在代码里再抄一份（本仓头号失败形态）。"
            "⚠ **它不判什么**：不判记忆**内容**，也**验不了门的效力** —— "
            "MAPLE-Guard 的 ASR 下降是**它自己的实验**，本仓没有投毒实验台 ⇒ "
            "**别把本项读成「记忆已安全」**"},
    {"id": "multi-round", "title": "多轮闭环 + 轮数上限", "fn": check_multi_round, "quick": True,
     "fix": "D7-P4-1（退出判据原文：多轮闭环可跑；**轮数上限有判据**）："
            "`inventory/multi-round.yaml` 是本仓**真实存在的重复执行闭环**的单一真值"
            "（★ 受理侧的协商回环**早就有**，路线总表 §11.2(a) 已裁「复用状态语义、不另建」）。"
            "① 报『`cap_state` 不在封闭集』= **漏写上限** —— 上限 / 无上限的理由 / 待谁裁，"
            "**三者必须显式其一**（不许靠「没写就是没有」）；"
            "② 报『`max_rounds` 与代码不符』= 真值表与 `agent-cli.ps1` **实提取**的上限不一致 "
            "⇒ 改真值表**或**改代码；"
            "③ ★★ 报『**未登记的散文上限**』或『散文上限与登记不符』= **注释里的上限落后于代码** —— "
            "本批实测**两处**都写 2 而代码是 3（O-46 改 cap 时注释没跟）；"
            "散文里的上限**逐处登记**，否则它会悄悄骗人；"
            "④ 报『缺 `stop_on_agreement`』= **正向终止条件**没写 —— 上限只管最多几轮，"
            "『什么时候可以停』是另一半（EASE 早停）；"
            "⑤ 报『`on_exceed_kind` 不在封闭集』= **超限时发生什么**必须是一个可枚举的动作"
             "（`escalate` / `terminate` / `fail-record`）—— 且已有上限却留 `undecided` ⇒ 上限只有一半；"
            "⑥ 报『`plus_extra` 锚点找不到』= 那段代码改了/删了（登记腐化）；"
            "⑦ 报『上限未定的闭环 …（待裁，点名）』= **WARN 不阻断**："
            "已如实登记、等裁定 ⇒ 但**点名在案，不许静默**。"
            "⚠ **它不判什么**：不判「多轮**跑通**了没有」—— 只验**上限与终止条件被写明**；"
            "`agent-resume` 的续接链与受理侧回环**本轮均未端到端实跑**（见 yaml 的 `unverified`）"},
    {"id": "interruption-untrusted", "title": "中断态两岸口径 + 不可信证据",
     "fn": check_interruption, "quick": True,
     "fix": "D7-P4-2（Ds 简报 11 / 18）：`inventory/interruption-and-untrusted.yaml` 是单一真值。"
            "① 报『缺 `main_side` / `station_side`』= **只有一端声明了口径** —— "
            "Ds 实测的死锁就出在「一端等待、一端失败」；两岸**都要**写；"
            "② 报『判出死锁风险却**没有 `mitigation`**』= 那个等待**没人管怎么终结** —— "
            "★ 注意：**风险由门禁算，不由你填**（自报 = 同一事实两个定义点）；"
            "③ ★★ 报『**规则算不出这条真事故**』= `history` 里那条已修死锁，按当前两岸动作"
            "**算不出非 none** ⇒ **判据是空转的**，先修 `deadlock_risk()` 的规则；"
            "④ 报『护栏是空头的』= 已修事故写的 `regression_guard` 在夹具/测试里**找不到**；"
            "⑤ ★★ 报『**自报不算声明**』= 某条不可信输入声称已在某文件里声明，"
            "但**那个文件里真找不到**该 marker（第 18 条落空）；"
            "⑥ 报『`declared: false` 却缺 `why_not`』= **「没声明」也要给理由**；"
            "⑦ 报『`trusted_inputs` 为空』= **什么不算不可信**没写，边界靠猜。"
            "⚠ **它不判什么**：只能核那句声明**在不在**，**判不了模型是否真遵守**；"
            "也**不做注入实验**（本仓没有实验台）⇒ **别读成「注入已防住」**。"
            "⚠ `interruptions` 只有 3 条 —— **不是穷举**（ssh 不可达 / 站断电等未登记）"},
    {"id": "rubric-blindspot", "title": "rubric 纪律 + 自环盲区登记",
     "fn": check_rubric_blindspot, "quick": True,
     "fix": "D7-P4-3（Ds 简报 15 / 12 / 21）：`inventory/rubric-and-blindspots.yaml` 是单一真值。"
            "① 报『rubric 里**找不到**必含句』= 某条**裁判纪律被人删了/改了措辞**"
            "（rubric 是纯文本资源，删一句没人知道）⇒ 补回来，或**同步改真值表**；"
            "② ★ 报『找不到 `ReadAllText`』= rubric/tmpl 的**读取退回了裸 `Get-Content`** —— "
            "PS 5.1 默认按 ANSI 读 ⇒ **中文资源会乱码**（本仓那条『UTF-8(BOM) 铁律』"
            "实际是靠**显式编码**兜住的）；"
            "③ 报『缺 `impl-same-source`』= **本仓最实质的盲区没登记**：三站互审走**同一份 "
            "`agent-cli.ps1`** ⇒ 实现层缺陷两侧同时出现，互审**结构上发现不了**；"
            "④ 报『缺 `why_blind`』= 没说清**为什么互审看不见**（那就不叫盲区登记，叫感想）；"
            "⑤ 报『`other_guard` 是 `na` 但缺 `why`』= **「没有替代机制」也要给理由**；"
            "⑥ 报『`derived_edges` 是 `deferred` 但缺 `condition`』= 触发条件没写死 ⇒ "
            "它会**永远挂着或悄悄做掉**。"
            "⚠ **它不判什么**：只核那几句**在不在**，**不判 rubric 全文写得好不好**（纯文本，语义不可机判）；"
            "盲区清单**不是穷举**；`derived_edges` 的触发条件是**跨仓事件**，本仓判不了"},
    # O-105 (2026-09-27): 能力盘点表 —— 动机 = "能力的存在性每次都要靠问一遍"
    #   （实测散落在 4 份调研正文里）⇒ 收成一张**可机核**的表；形态借自姊妹仓 P-050 RESEARCH §3.7。
    {"id": "capabilities", "title": "能力盘点（能力 → 载体 → 判定）",
     "fn": check_capability_inventory, "quick": True,
     "fix": "O-105：`inventory/capability-inventory.yaml` 是**能力层**的单一真值"
            "（与 ports/models/plugins 那类**事实**真值表分工不同：本表只**引用**它们，不复制事实）。"
            "① 报『缺 `metric` / `updated`』= **增长型计数没有口径或读数日期** —— "
            "口径一变，表里所有数字立刻失去意义（§87.6 的『同日漂移』就是这类失败）；"
            "② ★ 报『`carriers` 指的判据**不是已注册 CHECKS id**』= **挂名**"
            "（判据写了但没人跑 —— 本仓最典型的一类假绿）；"
            "③ 报『`carriers` 指的文件 / 真值表不存在』= **载体已腐化** ⇒ 改登记或补文件；"
            "④ 报『partial 缺 `gap`』= **缺哪一块没写清**（否则 partial 是个托词，"
            "读者无法判断它离 present 差多少）；"
            "⑤ ★ 报『absent 缺 `why`，或 `why_kind` 不在封闭集』= "
            "**「不做」也是一种结论，必须写下来**（不适用 / 未做 / 待裁 —— 三者含义不同）；"
            "⑥ 报『`self_id` 不在 items 里』= **「能力盘点」这项能力本身没被盘点**（自指缺口）；"
            "⑦ 报『声明的封闭集与判据实现不一致』= 改了代码没改表（或反之）"
            "⇒ **那时本判据自己就是假绿**。"
            "⚠ **它不判什么**：只保证「**有载体且可达**」，**不保证「载体真的管用」**"
            "（效力未被任何实验测过）；`verdict` 与 `gap` / `why` 均为**人工判断**且未经第二方复核；"
            "★ 「**漏了哪项能力**」**不可判** —— 没有权威清单可比对，只能靠新增时补"},
    # O-108 (2026-09-27): 文档状态声明的**两处位点** —— 动机 = `O-106` 落体时发现：
    #   同一文档在 front matter 与正文各写一份状态，**实例 12 处两处不等**（含 `draft` ↔ `verified`）。
    {"id": "doc-status", "title": "文档状态两处声明（判派生过期）",
     "fn": check_doc_status, "quick": True,
     "fix": "O-108：`inventory/doc-status.yaml` 是**两处状态声明**的单一真值"
            "（`semantics` 声明「谁是真值、谁是派生」；`freeze` 只装**存量**）。"
            "① ★ 报『两处不等』= **判为「派生过期」** ⇒ **先确认真值**：若取证显示 **fm 陈旧**，"
            "**先更新 fm**（那是真值更新）再让正文跟上；**稳态下**修法唯一 = **改正文行**"
            "（别改 fm 去迁就正文 —— 一改，那个面就变回「两处都可写」= 被 I-10 禁的形态）；"
            "② 报『冻结项**已自愈** / 已不再是两处都有』= **从 `freeze` 删掉**"
            "（防腐化 —— 同 `secrets` 的「豁免未命中」、`ops.yaml` 的冻结存量）；"
            "③ 报『缺 `semantics.single_write` / `derived`』= 本表**退化成一张豁免清单**了"
            "（没声明谁是真值，就只剩「不许红」这一个作用）；"
            "④ 报『`file` 不在仓里 / 缺 `why`』= 登记腐化 / **冻结没写理由**。"
            "⚠ **它不判什么**：① 它**验不了**「人是否只改 fm」（只能检出两处**不一致**）——"
            "**这正是 I-10 说的「检不出两处一致地错」**；② ★ **本面仍是两个位点** ⇒ "
            "本项是**降格处置**、**非 I-10 的完全实现**（彻底消除 = O-108 案①：只留 front matter）；"
            "③ **词表符合性**见 ⑤（O-109 起并入本项）；"
            "④ 射程**只到文档头 20 行**（口径写死在 `DOC_STATUS_HEAD`，§90.4 的教训）；"
            "⑤ ★ O-109（**第二段判据：词表符合性，按档**）：`inventory/doc-status.yaml` 的 `kind_source`"
            "登记「档 → 词表读取位点」—— 有模板档（design / checklist / adr）真值**在模板链**、"
            "无模板档（ledger / process）**在 yaml**；`kinds` 只登记无模板档的归属，判档按 `kind_rule`。"
            "报『token **不在档内**』= 该位点写了**词表外**的值 ⇒ 改回档内词（词表见报错列的集合）；"
            "报『**词表缺档**』= `kind_source.by_kind` 少了一档 ⇒ 补档（无模板档要同时补 `kinds` 归属）。"
            "⚠ **它只判 token 在不在档内**，**不判**「这个状态对不对」（状态位的**语义**对不对要人读）；"
            "★ **模板文件跳过**（`*_TEMPLATE.md` 的「状态」行是**词表本身**，不是实例值）"},
    {"id": "md-tables", "title": "md 表格列数守恒（防拆错格）",
     "fn": check_md_tables, "quick": True,
     "fix": "A4（2026-09-29）：同一张 markdown 表里 **分隔行 / 数据行** 的**格数**必须 == **表头**格数。"
            "报『**某行 N 格 ≠ 表头 M 格**』= 该行**被拆错格**（字段错位）—— 最常见的原因是"
            "**单元格文本里的竖线没转义**：写成**反斜杠 + 竖线**（`\\|`）即可；"
            "整行少/多一格（比如漏了个 `|`）⇒ 补齐。"
            "★ 口径（**唯一实现** = `md_table_scan`）：① **空单元格计入**格数；"
            "② 分隔行必须**紧邻**表头（不跨行找表）；③ 代码围栏（``` / ~~~）与 GFM 缩进码块**跳过**；"
            "④ 单元格里的转义竖线**不算分隔**。"
            "📊 note 报 `扫描 N 篇 · 表 T 张 · 违规 V（冻结 F · 新增 D）`；"
            "`表 0 张 ⇒ FAIL`（判据**无对象** = 退化空判，故「整篇没表 ⇒ 空集恒真」这种假绿被堵住）。"
            "⚠ 报『冻结条目**失配** / 指向**已不存在**的文件』= **从 `inventory/md-tables.yaml` 删掉对应条目**"
            "（冻结**只减不增** —— 修好了就清账，留着会烂成垃圾桶；同 `secrets` 的「豁免未命中」防腐化）；"
            "存量冻结的**逐条理由**在该 yaml 里（2026-09-29 上线时实测 28 处 / 13 个文件）。"
            "⚠ **它不判什么**：不判表格**内容**对不对，也不判文档该不该有表 —— 只判**格数守恒**。"},
    {"id": "determinism", "title": "确定性噪声口径（单一真值表）",
     "fn": check_determinism, "quick": True,
     "fix": "A5（2026-09-29）：噪声口径 = **单表** `inventory/determinism-noise.yaml`（所有「双跑 / 逐字节比对」"
            "类判据**引用**它，**不各写一份** —— 各写一份 = 同一事实两处表达，改一处漏一处）。"
            "报『缺 `updated`』= 增长型真值表必须带**读数日期**；报『`line-ending.normalize_to` 必须 LF』="
            "逐字节比对要求二进制一致（归一化只在**生产端**固化，比对端妥协 = 把噪声洗成假绿）；"
            "报『`applies_to` 含 X —— 不是真实断言 id』= **孤儿消费者**（无消费者的真值表会腐化）⇒ 改成真实 gate id；"
            "报『正则匹配不上代表样本』= 表里那条正则**检不出该类噪声**（坏正则）⇒ 修正则；"
            "报『有 match 但无自证样本』= 新增了可机检噪声却没给夹具 ⇒ 在 `_DET_SAMPLES` 补样本；"
            "报『`determinism: n/a` 缺 reason』= 天然不可双跑者必须写理由（**禁止静默跳过**）。"
            "⚠ **它不判什么**：不真的跑某条管线双跑（那要具体管线接入）—— 只钉住**口径单一真值 + 表可用性**。"},
    {"id": "derived-view", "title": "派生只读视图（真值→渲染→逐字节比对）",
     "fn": check_derived_view, "quick": True,
     "fix": "A3（2026-09-29）：清单类文档的**第二定义点**正解 —— 抄的那份改成**派生件**，"
            "从真值**渲染**出来（渲染器 = `ops/derived_view.py`；当前真值源 = `inventory/ports.yaml`；"
            "落档视图 = `docs/派生视图_端口分配.md`）。"
            "报『**过期**（声明 source-hash ≠ 当前）』= 真值改了但视图没重渲染 ⇒ 跑 `py ops/derived_view.py --emit`；"
            "报『**逐字节不一致**』= 视图被**手改**过 ⇒ 别手改，同样 `--emit` 覆盖（手改会被下次渲染冲掉）；"
            "报『**渲染链路故障**(rc=2)』= 读真值/解析 yaml/落档写入失败 ⇒ **先修渲染器**（这与「过期」不是一回事）；"
            "报『落档视图**缺 `source-hash` 行**』= 档头被删 ⇒ `--emit` 重出。"
            "★ **为什么判退出码而不在这里重实现比对**：三态（0 一致 / 1 过期·漂移 / 2 故障）由渲染器**单一定义**，"
            "门禁只做消费者 —— 各写一份 = 同一事实两处表达（本仓头号形态）。"
            "⚠ **它不判什么**：不判视图**内容**对不对（那是 `ports` 判据的事），只判「视图 == 真值的确定函数」。"},
    {"id": "executor-trace", "title": "执行侧过程留痕（五采集点）",
     "fn": check_executor_trace, "quick": True,
     "fix": "A2（2026-09-29）：治「判据只能看产物，看不到过程」—— 站上执行体改过哪些文件 / 跑过哪些命令"
            "此前**查不到**（既有两件：输出字节序列只记吞吐曲线、工作区改动摘要实测为空）。"
            "口径 = `dogfood-cards/imp4-executor-trace-design.md`：最小充分集**5 项**"
            "（cmd / env / fs / tool / artifact）。"
            "报『**缺采集点标记 X**』= `ops/station-bin/agent-cli.ps1` 里那一维**没被采集**"
            "（看着有留痕，实际缺维度）⇒ 补回该采集点（**别只补门禁**）；"
            "报『出现 `chain=core` / `chain=verified`』= **伪称执行体内部可核** —— 工具调用链由执行体**内部**产生"
            "（可篡改 / 漏报 / 伪造），**只能如实标 `uncore`**；"
            "报『runDir 的 executor-trace.txt **缺段**』= 落到仓的留痕件不齐（真缺陷）⇒ 查该次派发的采集链路。"
            "**锚定段**（2026-09-30 补）：报『**自报**』= 留痕件里出现执行体自报的产物哈希"
            "（`[artifact] hashes=` 必须是 `main-side` —— 执行体不可信，哈希只能由主控侧回收时算）⇒ 改采集点；"
            "报『**ts 不符**』= 留痕件不属于这一次（`ts=` ≠ runDir 名）⇒ 查归档 / 回收是否张冠李戴（`O-57` 同族）。"
            "⚠『覆盖 0 个』**不作为 FAIL**（本件尚未经真派发 ⇒ 覆盖率**未验**，报数不入分母）；"
            "⚠『无锚记录 N』同理**只报数**（主控侧没有该次 `content_digest` ⇒「没验到 ≠ 验出问题」）。"
            "⚠ **它不判什么**：逐条字面细节（两段写入 / `$Script:EV_FILES` 登记 / 主控归档 / `free -m` 而非 `/proc`）"
            "由**离线夹具** `_fm_golden_test.ps1` 守（见 `ps1-golden`）—— 本判据**不抄第二份**。"},
    # O-63 (2026-09-25): 取号并发夹具。**刻意 quick:False**（要起 8 个独立进程 + 两次 2.5s 共同释放时刻 ⇒ 约 6s）。
    {"id": "ps1-runstamp", "title": "ts 取号并发夹具", "fn": check_ps1_runstamp, "quick": False,
     "fix": "O-63: 跑 `powershell -NoProfile -ExecutionPolicy Bypass -File ops/station-bin/_runstamp_hammer.ps1 -N 8 -SelfTest`。"
            "两行**都要**在：`RUNSTAMP_HAMMER … PASS`（正向：8 进程 ts 全不同）+ "
            "`RUNSTAMP_HAMMER_SELFTEST … PASS`（负向：**同一把锤子**打旧实现必须检出撞车）。"
            "⚠ 只报负向 = **夹具是装饰**（正向根本没产生唯一 ts）；只报正向 = 负向没跑（少一行 ⇒ 本断言直接 FAIL）。"
            "⚠ 若出现 `dup:` ⇒ **真的撞了**：检查 `Get-UniqueRunStamp` 的原子原语是否被改回 "
            "`New-Item -ItemType Directory`（实测它会漏，uniq=11）—— 必须是 `[IO.File]::Open(..., CreateNew, ...)`"},
    # O-64 (2026-09-25): **测试套件接进门禁** —— 此前 21 套测试无任何机械执行者（"有测试 ≠ 有人在跑"）。
    #   实测依据与本项定位见 check_py_tests 的 docstring 与 PY_TESTS 上方注释（含 quick 取舍的实测值）。
    {"id": "py-tests", "title": "Python 测试套件(统一入口)", "fn": check_py_tests, "quick": False,
     "fix": "跑 `py tests/run_py_tests.py`（或 `-v` 看每题完整输出）⇒ 修明细里的 FAIL。"
            "⚠ **先判「是回归还是断言陈旧」**：若实现侧确有语义变更（看 `ops/station-bin/agent-cli.ps1` 的"
            "注释/O- 台账）⇒ 改**断言**并写明理由（**方向是改写断言，不是回退代码** —— 回退等于把修好的洞挖回来）；"
            "若实现侧无变更 ⇒ **是回归**，改代码。"
            "⚠ 报『总数 == 0』或『未解析到汇总行』= 入口本身坏了（如 discover 找不到测试）⇒ 先修入口 —— "
            "那是**比任何单条测试更严重**的失效（整批验证静默消失）"},
    {"id": "usb4", "title": "USB4 三角环链路", "fn": check_usb4, "quick": False,
     "fix": "地址/路由不符 => 对照 inventory/net.yaml 与归档 §6.3/§6.6; "
            "链路不通 => 先查 BIOS USB4 安全等级与是否冷启动(归档 §6.5)"},
    {"id": "gates", "title": "内存门禁", "fn": check_gates, "quick": False,
     "fix": "load-gate 缺失需补部署到 /usr/local/bin; 余量 ≤0 先卸载或清残留; "
            "loadavg>8 等负载回落再加载; 站上件与仓库副本不一致 => 这些件是站上件(改仓库不生效), "
            "按明细走「备份(cp -a, 核备份 md5 == 原 md5) → install -m 755 → 核新 md5 == 仓库副本」, "
            "或回滚站上版并改仓库侧; 清单见 rpc_check.py 的 STATION_BINS"},
    {"id": "engine", "title": "引擎态与残留", "fn": check_engine, "quick": False,
     "fix": "残留用 infer-unload 或清 llama/rpc 进程; 端口在听但 RSS 异常需查进程归属"},
    {"id": "backend", "title": "引擎后端与 studio 防线", "fn": check_backend, "quick": False,
     "fix": "默认单站引擎=HIP、分布式(/opt)=Vulkan 是本集群的**既定形态**; 后端变了先查是谁改的 "
            "(studio 自更新 / UPGRADE_SOP 升级 / 有人换构建) 再决定是否改期望值, 并把台账 §2.6 "
            "的后端矩阵同步; 回滚基线缺失 => 从同版本站 tar 分发补回 "
            "(UPGRADE_SOP §6: 保留 `<现役>` + `9859` 两个版本目录以支持分钟级回滚); "
            "**pin 未生效** => 落 `/etc/environment` 的 `UNSLOTH_LLAMA_CPP_BACKEND=rocm`"
            "(`.bashrc`/`.profile` 对非交互 ssh 无效, 见决策简报 §8.2); "
            "**缺 `X-Unsloth-Events`** => 升级 studio(简报 §三); "
            "**studio 版本或引擎构建不同版** => `cluster.py studio status` 看矩阵再决定是否同升; "
            "**引擎备份目录为空** => 引擎若被替换只能靠站间 tar(要求三站逐字节同版)或重下"},
    {"id": "models", "title": "模型库完整性", "fn": check_models, "quick": False,
     "fix": "孤儿 `cluster.py models link --go`; 断链 `cluster.py models prune --go`"},
    {"id": "stations", "title": "三站实况对账", "fn": check_stations, "quick": False,
     "fix": "conf/权重/凭据/端口/插件任一项不符 —— 见明细, 一律以站上实况为准改仓库侧"},
]
MARKS = {"PASS": "✓", "WARN": "▲", "FAIL": "✕", "SKIP_FAILED": "⊘"}
# D6-P0-1 (2026-09-23): **"非执行"必须三分, 不许含混** —— 这是本仓"假绿"的头号来源。
#   · **MODE_SKIP**   = `--quick`/`--only` 未选中该断言(**模式性省略**) ⇒ **合法, 不计失败**
#   · **SKIP_FAILED** = `needs` 里有 FAIL/SKIP_FAILED ⇒ **算失败**(不许静默降级)
#   · **WARN**        = **环境降级**(如缺 paramiko ⇒ 断言自报 WARN) ⇒ 不进 FAIL 集, 但必须可见
#     依据: `docs/2026-09-23_D6-D7分阶段执行方案.md` §11.1-A —— 若把环境降级误判成"级联 skip",
#     会让**每个 release 都因环境缺包变红**(假红淹真信号)。
MODE_SKIP = "MODE_SKIP"


def _validate_graph(checks):
    """断言依赖图校验 —— **配置错误必须 FAIL, 不许静默**(D6-P0-1)。

    `needs` = 必须先通过的断言 id 列表。校验两件事：
      · **未知 id**（打错字 / 引用了已删断言）⇒ 报错；
      · **成环** ⇒ 报错（拓扑执行会死锁 / 漏跑）。
    **纯函数** ⇒ 便于单测与注入（正反用例）。
    """
    ids = {c["id"] for c in checks}
    errs = []
    for c in checks:
        for n in c.get("needs", []):
            if n not in ids:
                errs.append(f"{c['id']}: needs 引用了不存在的断言 '{n}'")
    needs_of = {c["id"]: list(c.get("needs", [])) for c in checks}
    color = {}

    def dfs(u, stack):
        color[u] = 1
        for v in needs_of.get(u, []):
            if color.get(v) == 1:
                errs.append("needs 成环: " + " -> ".join(stack + [v]))
                continue
            if color.get(v, 0) == 0:
                dfs(v, stack + [v])
        color[u] = 2

    for c in checks:
        if color.get(c["id"], 0) == 0:
            dfs(c["id"], [c["id"]])
    return errs


def run_checks(selected):
    """**可注入的执行缝**：跑 `selected`，返回 `(results, failures)`。

    D6-P0-1「**非执行三分**」的**唯一落点**（`tests/test_rpc_check_three_classes.py` 三类各一注入）：
      · **MODE_SKIP**   = 调用方**不给**它（`--quick`/`--only` 未选中）⇒ **不进 results ⇒ 不计失败**
        （呈现 = `main()` 里那行"已跳过 (模式=…)"）；
      · **SKIP_FAILED** = `needs` 里有 FAIL/SKIP_FAILED ⇒ **算失败**（不许静默降级成 skip）；
      · **WARN**        = **环境降级**（缺 paramiko/pyyaml 等 ⇒ 断言自报 WARN）⇒ **不进 FAIL 集，但必须可见**。
    ⇒ 三者**互不相同**：**只有 SKIP_FAILED / FAIL 计失败**。

    抽成独立函数是为了能**注入假断言**（不跑真 I/O）做上述三类的注入用例；行为与旧的内联循环逐字等价。
    """
    results, failures, status_of = [], 0, {}
    for c in selected:
        unmet = [n for n in c.get("needs", []) if status_of.get(n) in ("FAIL", "SKIP_FAILED")]
        if unmet:
            status, note, detail = "SKIP_FAILED", f"依赖未满足: {', '.join(unmet)} ⇒ 本项未执行(算失败)", []
        else:
            try:
                status, note, detail = c["fn"]({})
            except Exception as e:
                status, note, detail = "FAIL", f"{type(e).__name__}: {e}", []
        status_of[c["id"]] = status
        results.append((c["id"], c["title"], status, note, detail))
        if status in ("FAIL", "SKIP_FAILED"):
            failures += 1
    return results, failures


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--quick", action="store_true", help="仅本地快检 (pre-commit)")
    ap.add_argument("--only", default="", help="逗号分隔的断言 id")
    ap.add_argument("--list", action="store_true", help="只列断言清单")
    # ★ B 段（2026-10-01）：D7 协议判据的**消费面**（外壳调它 ⇒ 判据只在一处；见 `d7_cli`）。
    ap.add_argument("--d7-envelope", nargs=2, metavar=("KIND", "PATH"),
                    help="D7 信封校验：KIND ∈ TaskContract|RunReport|Verdict；PATH = JSON 文件或 - (stdin)")
    ap.add_argument("--d7-transition", nargs=3, metavar=("FROM", "TO", "ACTOR"),
                    help="D7 六相状态迁移校验（ACTOR ∈ master|worker）")
    ap.add_argument("--d7-block", default="", metavar="RULE",
                    help="D7 8 条拦截之一（RL1/RL2/RL3/I1/I3/I6/PRM/PRW）")
    ap.add_argument("--d7-ctx", default="", metavar="JSON",
                    help="--d7-block 的上下文（JSON 文件或 -）")
    ap.add_argument("--d7-host-sep", nargs=2, default=None, metavar=("EXEC_HOST", "ARBITER_HOST"),
                    help="★ B3 `PRH`：产出机 vs 裁决机的**同机可见性**（0=分离 / 1=同机 / 2=不可判）"
                         "—— 报数用，调用方按 WARN 处理（不阻断）")
    args = ap.parse_args()

    rc = d7_cli(args)                      # 命中 D7 消费面 ⇒ 直接返回（不跑门禁）
    if rc is not None:
        return rc

    if args.list:
        for c in CHECKS:
            print(f"  {c['id']:10s} {c['title']:16s} quick={str(c['quick']):5s} {c.get('fix', '')}")
        return 0

    selected = CHECKS
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        selected = [c for c in CHECKS if c["id"] in want]
    elif args.quick:
        selected = [c for c in CHECKS if c["quick"]]

    mode = "quick" if args.quick else "全量"
    print(f"\nrpc check · 模式={mode} · {ROOT}\n")

    # D6-P0-1: **图校验先行** —— 配置错误(未知 id / 成环)不许静默, 直接阻断
    graph_errs = _validate_graph(CHECKS)
    if graph_errs:
        print("  ── 断言依赖图校验 ──")
        for e in graph_errs:
            print(f"    ✕ {e}")
        print("\n  结论: FAIL (断言依赖图配置错误) → 阻断\n")
        return 1

    results, failures = run_checks(selected)

    for cid, title, status, note, _ in results:
        print(f"  [{status:4s}] {MARKS[status]} {cid:10s} {title:16s} {note}")

    skipped = [c["id"] for c in CHECKS if c not in selected]
    if skipped:
        print(f"\n  已跳过 (模式={mode}): {', '.join(skipped)}")

    for cid, title, status, note, detail in results:
        if status in ("FAIL", "WARN") and detail:
            print(f"\n  ── {cid} 明细 ──")
            for d in detail[:40]:
                print(f"    {d}")
            if len(detail) > 40:
                print(f"    … 另有 {len(detail) - 40} 条")

    # 处置建议: 红灯必须给出"下一步", 不能只报"哪里不对" (P2-2 健康引擎形态)
    bad = [r for r in results if r[2] in ("FAIL", "WARN", "SKIP_FAILED")]
    if bad:
        fixes = {c["id"]: c.get("fix", "") for c in CHECKS}
        print("\n  ── 处置建议 (红灯优先) ──")
        for cid, _t, status, _n, _d in sorted(bad, key=lambda r: r[2] != "FAIL"):
            print(f"    {MARKS[status]} {cid:10s} {fixes.get(cid, '')}")

    n_fail = sum(1 for r in results if r[2] in ("FAIL", "SKIP_FAILED"))
    n_warn = sum(1 for r in results if r[2] == "WARN")
    n_ok = len(results) - n_fail - n_warn
    tail = f"绿灯 {n_ok} · 黄灯 {n_warn} · 红灯 {n_fail}"
    if failures:
        print(f"\n  结论: FAIL ({failures} 项失败) → 阻断; 修复后重跑 · {tail}\n")
        return 1
    print(f"\n  结论: PASS · {tail}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
