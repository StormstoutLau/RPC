#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""治理类检查器（review-p2-split 8B-3；从 `rpc_check.py` 整段抽出，行为不变）：secrets / syntax / scripts / artifacts / sensitivity / facade / deps / adr / inventory / shell-strict / station-layout。"""
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
from rpc_common import (
    CHECKS, INVENTORY_DIR, ROOT, SENSITIVITY_INV, SENSITIVITY_SECTIONS, SENSITIVITY_TIERS,
    _read_text, allow_unhit, load_inventory,
)

# ── 断言 A1: 明文扫描 ─────────────────────────────────────────────
# 边界 (?<![A-Za-z0-9]) 用于排除 `task-2026...` 这类含 "sk-" 子串的误报。
# ⚠ 本清单与 `agent-cli.ps1` 的 `Get-ScrubRules`（出网前消毒，2026-09-21 扩到 9 条）**刻意不同**，
#   且**不要**为"对齐"去改：两者**作用域不同** —— 本处扫**仓库跟踪文件**（问"仓库里有没有真钥匙"），
#   那边扫**待出网 prompt**（问"出网字节里有没有敏感形态"）。裁定与理由见
#   docs/security/2026-09-21_scrubber规则扩充裁定与影响面.md §4 行 3。
#
# ★ 2026-10-21 扩形态（安全评审触发）：原正则**只认 `sk-` 前缀**，而仓库里实际躺着
#   Beszel 账号口令与 SSH 口令（非 sk- 形态）⇒ 门禁长期全绿不是因为干净，是因为看不见。
#   现扩到四族：`sk-` / 口令赋值（**仅带引号的字面量**）/ 私钥块头 / 常见云厂商 key 前缀。
#   ⚠ 值分支**刻意只认带引号的字面量**：放开"不带引号"会误伤 `if decision == "pass":`
#     与 `PASS: derived-view` 这类正常文本（2026-10-21 实测）⇒ 该形态登记为盲区，
#     见 tests/test_rpc_check_secret_forms.py 的残留盲区说明。
SECRET_RE = re.compile(
    r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}"
    # ★★ 2026-10-24（O-174）：口令族**允许下划线前缀** —— 原写法 `\b(?:pass|…)` 在
    #   `ADMIN_PASS` / `DB_PWD` 上是**漏报**：`_` 与 `P` 之间没有字边界（两者都是 word char）
    #   ⇒ 整条赋值被跳过（实测：`archive/scripts-history/b5f_hub_deploy.sh` 里一条 59 字符
    #   真凭据因此长期不被门禁看见）。现改为「非字母数字起 + 任意 `xxx_` 前缀 + 关键字」，
    #   并要求关键字**后**不再接字母数字（`(?![A-Za-z0-9])`）。
    #   ⚠ 边界刻意保留：`SSH_ASKPASS_REQUIRE = "force"` 不命中（关键字后接 `_REQUIRE`）、
    #   `bypass="…"` 不命中（`by`/`pass` 之间无下划线），夹具 `test_rpc_check_secret_forms.py` 钉住。
    r"|[\"']?(?<![A-Za-z0-9])(?:[A-Za-z0-9]+_)*(?:pass|passwd|password|pwd)(?![A-Za-z0-9])[\"']?\s*[:=]\s*"
    r"(?:\"(?=[^\"]*[A-Za-z0-9])[^\"\s]{4,}\"|'(?=[^']*[A-Za-z0-9])[^'\s]{4,}')"
    r"|-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
    r"|(?<![A-Za-z0-9])(?:AKIA|ASIA)[0-9A-Z]{16}"
    r"|(?<![A-Za-z0-9])(?:ghp|gho|ghs|ghr)_[A-Za-z0-9]{30,}"
    r"|(?<![A-Za-z0-9])(?:glpat|xox[baprs]|sk_live|AIza)[A-Za-z0-9_\-]{10,}",
    re.IGNORECASE)

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




def _mask(s):
    return s[:8] + "…" if len(s) > 9 else s




def check_secrets(ctx):
    """扫描跟踪文件中的明文密钥形态。

    ★ 2026-10-21：删掉 `if "sk-" not in text: continue` 的**整文件短路**。
      原短路让"不含 sk- 的文件"连正则都不跑 —— 扩形态后它会让新增的四族全部失效
      （实测：Beszel 口令所在文件无一含 `sk-`）。范围本来就是 git 跟踪文件（~1000 个），
      全量跑正则的成本可忽略。
    """
    hits, allowed, scanned, skipped_bin = [], [], 0, 0
    for rel, path in _iter_source_files():
        if _is_binary(path):
            skipped_bin += 1
            continue
        text = _read_text(path)
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

    # ── A. `.sh` 行尾: **CRLF 字节判据** (2026-10-17, 与上面的 `.ps1-bom` 同机理) ──────────
    # 为什么必须**另判一次"字节"**: 本栏的 `bash -n` 跑在 **Git Bash(MSYS)** 上, 而脚本的**靶子是 Linux bash**。
    #   实测(同一份 CRLF 的 .sh, 样本 `archive/scripts-history/gen_manifest.sh`):
    #     · 门禁侧 MSYS `bash -n` ⇒ **rc=0 通过**   (⇒ 本栏报 `.sh:414文件/0失败`, **漏判**)
    #     · 站上 Linux `bash -n` ⇒ **报语法错** `未预期的记号 "}"`
    #   ⇒ 解析式判据对"行尾"这类**字节级**属性**结构性不可见**, 那个绿是**假的**。
    #   与 `.ps1-bom` 的教训**完全同源**: 解析判据抓不到字节级属性 ⇒ 必须另加一个"读字节"的维度。
    # 判据(确定性, 与内容无关): `.sh` 与无扩展名 shebang 脚本**含任何 `0x0D`** ⇒ FAIL。
    #   为什么不能靠 `.gitattributes`: 那里的 `text eol=lf` 只覆盖**已登记前缀**, 覆盖不到全仓与站上产物。
    crlf_targets = sh_files + sb_sh
    bad_crlf = 0
    with tempfile.TemporaryDirectory() as td:
        # 自证(双向): LF 样本必**不**含 CR、CRLF 样本必含 —— 判据本身要能被证伪, 才配写进 FAIL 集
        lf_s, crlf_s = Path(td) / "lf.sh", Path(td) / "crlf.sh"
        lf_s.write_bytes(b"#!/bin/bash\necho hi\n")
        crlf_s.write_bytes(b"#!/bin/bash\r\necho hi\r\n")
        ok_crlf_self = (b"\x0d" not in lf_s.read_bytes()) and (b"\x0d" in crlf_s.read_bytes())
    if not ok_crlf_self:
        bad_crlf = len(crlf_targets)
        detail.append("(sh-crlf) 字节判据自证失败: LF 样本被误判 / CRLF 样本未被识别 ⇒ 本栏不可信, 拒绝给 PASS")
    else:
        for rel, path in crlf_targets:
            try:
                raw = path.read_bytes()
            except OSError as e:
                bad_crlf += 1
                detail.append(f"(sh-crlf) {rel}  读字节失败: {type(e).__name__}")
                continue
            if b"\x0d" in raw:
                bad_crlf += 1
                detail.append(f"(sh-crlf) {rel}  含 CR(0x0D) ⇒ 行尾为 CRLF; 靶子是 **Linux bash**, "
                              f"CRLF 会破坏解析(实测同文件 MSYS `bash -n` 通过而 Linux `bash -n` 报错) "
                              f"⇒ 修: 转 LF (`dos2unix` / 编辑器设 LF / `.gitattributes` 加 `text eol=lf`)")
    counts[".sh-crlf"] = (len(crlf_targets), bad_crlf)

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


# ── review-p2-big（2026-10-28）：站上 shell 严格模式 + station-bin 布局 ──────────
# 两项都是"契约登记在 inventory/ops.yaml、判据在本函数"的形态：门禁与单测读**同一份**真值，
# 避免第二份清单（本仓头号失败形态）。详见 spec/review-p2-big/DESIGN.md §4.1-§4.3。
SHELL_STRICT_KEY = "shell_strict"
STATION_LAYOUT_KEY = "station_bin_layout"
SHELL_STRICT_PROLOGUE = "set -euo pipefail"
SHELL_STRICT_SCAN_LINES = 20
STATION_PROBE_GLOB = re.compile(r"^ops/station-bin/_[^/]+$")


def _load_ops_inv():
    """读 `inventory/ops.yaml`；不可读/缺 pyyaml 返回 None（调用方判 FAIL，不静默放行）。"""
    try:
        import yaml
    except Exception:                                        # noqa: BLE001
        return None
    try:
        return yaml.safe_load(OPS_INV.read_text(encoding="utf-8")) or {}
    except Exception:                                        # noqa: BLE001
        return None


def _shell_prologue(text):
    """前 N 行里**第一条**非注释、非空行（即 prologue 的判据位）。"""
    for ln in (text or "").splitlines()[:SHELL_STRICT_SCAN_LINES]:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        return s
    return ""


def _lib_set_line(text):
    """库里第一条 `set +-...` 行（含函数内）；空 = 合规。"""
    for ln in (text or "").splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if re.match(r"^set\s+[+-]", s):
            return s
    return ""


def validate_shell_strict(doc, read_text):
    """纯函数：`shell_strict` 段自洽 + 13 执行件 prologue + 2 库无 set + 豁免命中。

    `read_text(rel)` 返回文本或 None（文件不存在）。空 problems = PASS。
    """
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["缺 `shell_strict` 段（或不是映射）"], notes

    execs = doc.get("exec")
    libs = doc.get("libs")
    allow = doc.get("allow") or []
    if not isinstance(execs, list) or not execs:
        bad.append("`shell_strict.exec` 为空或不是列表")
        execs = []
    if not isinstance(libs, list):
        bad.append("`shell_strict.libs` 不是列表")
        libs = []
    if not isinstance(allow, list):
        bad.append("`shell_strict.allow` 不是列表")
        allow = []
    execs = [str(x).strip() for x in execs if str(x).strip()]
    libs = [str(x).strip() for x in libs if str(x).strip()]

    dup = sorted({p for p in execs if execs.count(p) > 1})
    if dup:
        bad.append(f"exec 内重复: {dup}")
    overlap = sorted(set(execs) & set(libs))
    if overlap:
        bad.append(f"同一文件同时列入 exec 与 libs（双列）: {overlap}")

    strict_n = 0
    for rel in execs:
        text = read_text(rel)
        if text is None:
            bad.append(f"执行件不存在: {rel}")
            continue
        pro = _shell_prologue(text)
        if pro != SHELL_STRICT_PROLOGUE:
            bad.append(f"prologue 不是 `{SHELL_STRICT_PROLOGUE}`: {rel}（实测 `{pro}`）")
        else:
            strict_n += 1

    for rel in libs:
        text = read_text(rel)
        if text is None:
            bad.append(f"库不存在: {rel}")
            continue
        line = _lib_set_line(text)
        if line:
            bad.append(f"库不得改调用方 shell 选项: {rel}（实测 `{line}`）")

    for i, a in enumerate(allow):
        if not isinstance(a, dict):
            bad.append(f"allow[{i}] 不是映射")
            continue
        f = str(a.get("file") or "").strip()
        why = str(a.get("why") or "").strip()
        if not f:
            bad.append(f"allow[{i}] 缺 `file`")
            continue
        if not why:
            bad.append(f"allow[{i}] 缺 `why`: {f}")
        if f in execs:
            bad.append(f"豁免与 exec 重叠（同一文件既要求严格又豁免）: {f}")
            continue
        text = read_text(f)
        if text is None:
            bad.append(f"豁免文件不存在: {f}")
            continue
        if _shell_prologue(text) == SHELL_STRICT_PROLOGUE:
            bad.append(f"豁免未命中（文件已是严格模式）⇒ 删除该条: {f}")

    notes.append(f"执行件 {len(execs)}（严格 {strict_n}）· 库 {len(libs)} · 豁免 {len(allow)}")
    return bad, notes


def check_shell_strict(ctx):
    """review-p2-big #5：站上 shell 严格模式（真值 = `inventory/ops.yaml` 的 `shell_strict`）。"""
    doc = _load_ops_inv()
    if doc is None:
        return "FAIL", "inventory/ops.yaml 不可读（本断言的登记依据）", []

    def _read(rel):
        p = ROOT / rel
        return _read_text(p) if p.is_file() else None

    bad, notes = validate_shell_strict(doc.get(SHELL_STRICT_KEY), _read)
    return ("FAIL" if bad else "PASS"), " · ".join(notes), bad


def validate_station_layout(doc, root_files, archive_files, frozen_paths):
    """纯函数：根目录 `_*` ⊆ 白名单、归档非空、无同名复制、登记无根级探针残留。"""
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["缺 `station_bin_layout` 段（或不是映射）"], notes

    probes_dir = str(doc.get("probes_dir") or "").strip()
    keep = doc.get("root_keep")
    if not probes_dir:
        bad.append("缺 `probes_dir`")
    if not isinstance(keep, list) or not keep:
        bad.append("`root_keep` 为空或不是列表")
        keep = []
    keep = {str(x).strip() for x in keep if str(x).strip()}

    if probes_dir and not archive_files:
        bad.append(f"归档目录为空或不存在: {probes_dir}")

    stray = sorted(n for n in root_files if n.startswith("_") and n not in keep)
    if stray:
        bad.append(f"根目录有未登记的一次性件 {len(stray)} 个: {stray[:5]}")

    missing = sorted(k for k in keep if k not in root_files)
    if missing:
        bad.append(f"root_keep 指向已不存在的文件（白名单腐化）: {missing}")

    # 只对 `_*` 件判重名：README 等文档在根/归档各有一份是正常的（内容不同）。
    dup = sorted(n for n in (set(root_files) & set(archive_files)) if n.startswith("_"))
    if dup:
        bad.append(f"根目录与归档目录同名（复制而非移动）: {dup[:5]}")

    # 根级探针残留：白名单里的 9 个在跑件**允许**继续登记（它们不是探针，是夹具/运行时件）
    residue = [p for p in frozen_paths
               if STATION_PROBE_GLOB.match(p) and Path(p).name not in keep]
    if residue:
        bad.append(f"登记表残留根级探针 {len(residue)} 条: {residue[:5]}")

    notes.append(f"根目录 `_*` {sum(1 for n in root_files if n.startswith('_'))} · "
                 f"归档 {len(archive_files)} · 白名单 {len(keep)}")
    return bad, notes


def check_station_layout(ctx):
    """review-p2-big #8A：`station-bin` 根目录只放部署件/运行时件/在跑夹具。

    范围 = **git 跟踪文件**（`_iter_source_files`）—— 工作区里未跟踪的运行时残留
    （如 `_dogfood_*.log`）不属于"仓库布局"，不参与判定。
    """
    doc = _load_ops_inv()
    if doc is None:
        return "FAIL", "inventory/ops.yaml 不可读（本断言的登记依据）", []
    sec = doc.get(STATION_LAYOUT_KEY)
    probes_dir = str((sec or {}).get("probes_dir") or "").strip() if isinstance(sec, dict) else ""
    root_files, archive_files = [], []
    for rel, _p in _iter_source_files():
        if rel.startswith("ops/station-bin/") and rel.count("/") == 2:
            root_files.append(Path(rel).name)
        elif probes_dir and rel.startswith(probes_dir + "/"):
            rest = rel[len(probes_dir) + 1:]
            if "/" not in rest:
                archive_files.append(rest)
    frozen = [str(x) for x in (doc.get("frozen_ops_scripts") or [])]
    bad, notes = validate_station_layout(sec, sorted(root_files), sorted(archive_files), frozen)
    return ("FAIL" if bad else "PASS"), " · ".join(notes), bad


