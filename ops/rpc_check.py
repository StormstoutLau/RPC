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
import json
import os
import re
import shutil
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
    note = f"扫描 {scanned} 个文本文件 (跳过 {skipped_bin} 个二进制), 命中 {len(hits)} 处"
    if allowed:
        note += f", 白名单 {len(allowed)} 处"
    return ("FAIL" if hits else "PASS"), note, detail


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
            if sh_files:
                bad_sh, det, seen = _bash_lint([p for _, p in sh_files], bash)
                detail += det
                if seen != len(sh_files):
                    bad_sh = len(sh_files)
                    detail.append(f".sh 覆盖不全: 实际检查 {seen} / 应有 {len(sh_files)} 个"
                                  f" (读到数 != 喂入数 ⇒ 结果不可信)")
            if sb_sh:
                bad_sb_sh, det, seen = _bash_lint([p for _, p in sb_sh], bash)
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
    runtime = list(inv.get("station_runtime") or [])
    frozen = list(inv.get("frozen_ops_scripts") or [])
    known = set(entry) | set(runtime) | set(frozen)

    scripts = dict(_iter_governed_scripts())
    unknown = sorted(s for s in scripts if s not in known)
    missing_entry = [e for e in entry if not (ROOT / e).exists()]
    gone = sorted(f for f in frozen if f not in scripts)

    detail = []
    if unknown:
        detail.append(f"新增未登记脚本 {len(unknown)} 个 —— 管理操作请优先给统一入口加子命令 "
                      f"(ops/cluster.py <sub>), 而非再写一个脚本:")
        detail += [f"  {s}" for s in unknown[:20]]
        if len(unknown) > 20:
            detail.append(f"  …另 {len(unknown) - 20} 个")
    if missing_entry:
        detail.append("统一入口件缺失: " + ", ".join(missing_entry))
    if gone:
        detail.append(f"冻结清单里已不存在的 {len(gone)} 项可从 inventory/ops.yaml 删掉 "
                      f"(只减不增, 删减是欢迎的方向): " + ", ".join(gone[:8])
                      + (" …" if len(gone) > 8 else ""))
    bad = bool(unknown) or bool(missing_entry)
    note = (f"扫描 {len(scripts)} 个脚本 · 入口 {len(entry)} · 站上运行时 {len(runtime)} "
            f"· 冻结存量 {len(frozen)} · 未登记 {len(unknown)}")
    # 提示必须进 note: PASS 时明细块不打印, 只放 detail 等于没人看得到 (实测踩到)
    if gone:
        note += f" · 清单含 {len(gone)} 项已不存在(应移除)"
    return ("FAIL" if bad else "PASS"), note, detail


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
                    continue
                n_bad += 1
                bad.append((f"{rel.as_posix()}:{i}", base, reason))

    detail = []
    for loc, base, why in bad:
        detail.append(f"{loc}  ->  {base}" + (f"   【{why}】" if why else ""))
    note = (f"扫描 {n_md} 个 md · 链接 {n_link} 条 (其中非仓库内相对链接/占位词 {n_skip} 条不判) "
            f"· 已登记例外 {n_allow} · 失效 {n_bad}")
    return ("FAIL" if n_bad else "PASS"), note, detail


# ── 断言 A3: inventory 单点真值 (P1) ──────────────────────────────
# 目的: 阻止"改了这个忘了那个" —— 端口/模型标识变更时, 保证声明源与真值表一致。
#
# **对账模式, 不是文本扫描** (2026-09-14 实测修正, 详见文档 §11):
#   最初的设计是"扫描全仓库出现的端口/模型名, 未登记即 FAIL"。实测该方案不可行:
#     · 端口: 51 个"端口"里 19 个不是端口 (llama.cpp 提交号 9859、参数值 16384/4096/
#       1024、截断匹配 127/808...)。文本里的数字没有唯一语义。
#     · 模型: 以 gguf 结尾的强标识 114 个, 100% 是路径/文件名, 纯噪声。
#   改为只对**结构化声明源**做对账 —— 精确、零噪声、可长期维护:
#     (a) ops/cluster.py 的端口常量 (如 STATION_PORT) 与模型路由常量 (如 ROUTE)
#     (b) docs/三机推理集群使用手册.md 的端点表格行
#   声明源里出现而 inventory 未登记 => FAIL, 并提示"登记真值"或"修正过期引用"。
INVENTORY_DIR = ROOT / "inventory"
DECL_CLUSTER_PY = ROOT / "ops" / "cluster.py"
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
    """从声明源解析 (端口, 模型标识)。返回 ({port: [来源]}, {name: [来源]})。"""
    ports, models = {}, {}
    text = _read_text(DECL_CLUSTER_PY) if DECL_CLUSTER_PY.is_file() else ""
    for m in PORT_CONST_RE.finditer(text):
        for v in re.findall(r":\s*(\d{2,5})", m.group("body")):
            ports.setdefault(int(v), []).append(f"cluster.py:{m.group('name')}")
    for m in MODEL_CONST_RE.finditer(text):
        # STATION_ROUTES 是**派生表** (键 = 站上真实别名 + 站后缀, 值 = (站, 真实别名)),
        # 不逐条登记到 inventory —— 那会与基础别名重复, 且引入双份要同步的真值。
        # 它的正确性由 aliases 断言的 (7) 子项校验 (更强: 含站维度, 要求 (别名,站) 已声明 conf)。
        if m.group("name") == "STATION_ROUTES":
            continue
        for k in re.findall(r"[\"']([^\"']+)[\"']\s*:", m.group("body")):
            models.setdefault(k, []).append(f"cluster.py:{m.group('name')}")
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

STATION_CMD = (
    "printf '\\n[cfg]\\n'; sha256sum " + " ".join(WATCHED) + " 2>/dev/null | cut -c1-16; "
    "printf '\\n[conf]\\n'; ls -1 /etc/llama-instances/*.env 2>/dev/null "
    "| xargs -r -n1 basename | sed 's/\\.env$//' | tr '\\n' ' '; echo; "
    "printf '\\n[bind]\\n'; ss -ltn 2>/dev/null | awk 'NR>1{print $4}' | tr '\\n' ' '; echo; "
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
    "echo \"unslothlog=dirperm:${DP} files:${LF} withkeys:${LK} loose:${LL}\""
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

    # (h) LAN 传输面绑定 (ADR-0006) —— master 侧 `ssh -G <名>` 的 hostname 必须 == net.yaml 的 lan 段真值。
    #     为什么放这里: 这是"控制面走哪条路"的唯一可断言点, 造价近 0 (纯本地展开, 不建连),
    #     却能把"DHCP 漂移 ⇒ 走公网 IPv6 + 每次多付 ~16s + 最终连不上"变成一条明确的 FAIL。
    try:
        lan_doc = (_net_doc() or {}).get("lan") or {}
    except Exception as e:
        lan_doc = {}
        warn.append(f"net.yaml 解析失败, LAN 绑定对账跳过 —— {type(e).__name__}: {str(e)[:120]}")
    for ent in (lan_doc.get("stations") or []):
        if not isinstance(ent, dict):
            continue
        alias, want = ent.get("host"), ent.get("ip")
        if not alias or not want:
            continue                    # 仅以 IP 直连的站(如 C) 无别名, 跳过
        got = _ssh_g_hostname(alias)
        if got is None:
            warn.append(f"`ssh -G {alias}` 不可用 —— 无法核对 LAN 绑定 (该名应绑定到 {want})")
        elif got != want:
            detail.append(f"{alias} 的 ssh 绑定 hostname={got}, 而 net.yaml lan 段登记 {want} "
                          f"—— DHCP 可能已漂移, 请同步更新 ~/.ssh/config 与 net.yaml 的 lan 段; "
                          f"不更新则连该站要走公网 IPv6 且每次多付 ~16s")

    if unreachable:
        info.insert(0, f"站点不可达 (未计入判定): {', '.join(unreachable)}")
    note = (f"可达 {len(reach)}/3 站 · 对账 cfg{len(WATCHED)}/ROUTE{len(cluster.ROUTE)}"
            f"/RPC{len(cluster.RPC_MODELS)}/conf{sum(len(v) for v in declared_conf.values())}"
            f"/bind{sum(1 for m in (ports_inv or {}).values() if m.get('expect_bind'))}"
            f"/port{checked_ports}(豁免临时段 {ignored_eph})/plugin{plugin_checked}"
            f"/weight{sum(1 for st in reach for _ in (live[st].get('mpath') or '').splitlines())}")
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
# 残留阈值: 进程 RSS 超过它却没有引擎在服务 → 视为残留(占着内存不干活)。
# 取 2G: 正常单机 llama-server 的 RSS 是几十 G 量级, 而 ggml-rpc-server 空转也有 ~0.3G,
# 故 2G 能把"真占住了"和"进程刚起/空跑"分开 (本会话真的踩到过 62.6G 残留污染判定)。
RESIDUAL_RSS_MB = 2048

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
    "echo '===PROC==='; ps -eo rss,comm 2>/dev/null "
    "| grep -E 'llama-server|ggml-rpc-server|llama-cli' | grep -v grep "
    "| awk '{s+=$1} END {printf \"rss_mb=%d\\n\", s/1024}'; "
    "echo '===LISTEN==='; ss -ltn 2>/dev/null | awk 'NR>1{print $4}' | sed 's/.*://' "
    "| grep -E '^(" + "|".join(ENGINE_PORTS) + ")$' | sort -u | tr '\\n' ','; echo; "
    "echo '===MEM==='; awk '/MemTotal/{printf \"total_mb=%d \", $2/1024} "
    "/MemAvailable/{printf \"avail_mb=%d\", $2/1024}' /proc/meminfo; "
    "printf ' load1=%s' \"$(cut -d' ' -f1 /proc/loadavg)\"; "
    "printf ' loadgate=%s\\n' \"$(command -v load-gate >/dev/null 2>&1 && echo yes || echo no)\""
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
         "ping": {}, "rss_mb": None, "listen": [], "mem": {}, "raw": ""}
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
        if line.startswith("rss_mb="):
            try:
                d["rss_mb"] = int(line.split("=", 1)[1])
            except ValueError:
                pass
    d["listen"] = [x for x in ",".join(sec.get("LISTEN", [])).split(",") if x]
    mem_line = " ".join(sec.get("MEM", []))
    for tok in mem_line.split():
        if "=" in tok:
            k, _, v = tok.partition("=")
            d["mem"][k] = v
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

    note = (f"内存门禁: 可达 {len(reach)}/3 站 · "
            f"最小余量 {min([int(live[s]['mem'].get('avail_mb', 0)) // 1024 - 12 for s in reach] or [0])}G")
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
        if ports:
            running += 1
            info.append(f"{st} 站引擎在服务: 端口 {','.join(ports)} · 进程 RSS {rss // 1024}G")
            if rss < 1024:
                warn.append(f"{st} 站有引擎端口在听但 RSS 仅 {rss}M —— 疑似异常进程/端口被占")
        elif rss >= RESIDUAL_RSS_MB:
            detail.append(f"{st} 站**残留**: 无任何引擎端口在听, 但 llama/rpc 进程仍占 "
                          f"{rss // 1024}G RSS —— 内存被占着没干活, 会污染加载预估 "
                          f"(先 infer-unload / 清残留再加载)")
        else:
            info.append(f"{st} 站引擎未运行 (RSS {rss}M) —— 零自加载方针下属正常")

    note = (f"引擎: 可达 {len(reach)}/3 站 · 在服务 {running} 站 · "
            f"总占用 {sum((live[s]['rss_mb'] or 0) for s in reach) // 1024}G")
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
    "printf 'rollback=%s\\n' \"$(ls -d /opt/llama.cpp-9859 2>/dev/null || echo missing)\""
)
_EXPECT_STUDIO_BACKEND = "libggml-hip.so"      # 默认单站加载 = HIP/ROCm
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

    if not per:
        return "FAIL", "后端: 三站均采集失败", detail
    tip = vals[0] if len(vals) == 1 else " / ".join(f"{s}:{rocm.get(s) or '?'}" for s in sorted(rocm))
    note = f"后端: 可达 {len(per)}/3 站 · 单站=HIP / 分布式=Vulkan · ROCm {tip}"
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


# ── 断言清单 (加校验 = 在此加一条 + 写一个函数) ─────────────────────
# fix 字段 = 该项失败/警告时的**处置建议** (健康引擎要求"红灯必须给出下一步", 而不是
# 只报"哪里不对")。main() 在结论区按严重度打印。
CHECKS = [
    {"id": "secrets", "title": "明文扫描", "fn": check_secrets, "quick": True,
     "fix": "删除明文密钥, 或加入 SECRET_ALLOW 并写明原因(不允许静默放行); "
            "文档里引用样串/占位串时**掩码为 sk-xxx-****** (2026-09-16 增: 未掩码的样串会命中本判据)"},
    {"id": "syntax", "title": "语法检查", "fn": check_syntax, "quick": True,
     "fix": "按明细里的行号修语法; 扩展名与内容不符的应解包或改名"},
    {"id": "scripts", "title": "脚本治理", "fn": check_scripts, "quick": True,
     "fix": "管理操作请走统一入口 (ops/cluster.py <sub> / web 卡片), 不要新增一次性脚本; "
            "确需独立脚本则在 inventory/ops.yaml 登记并在提交信息里说明理由 (ADR-0004)"},
    {"id": "doclinks", "title": "文档链接可达", "fn": check_doclinks, "quick": True,
     "fix": "资源移动/改名后, 文档里的相对链接要跟着改 (注意别写重前缀: spec/<x>/ 里是 "
            "`../y` 不是 `../spec/y`, 引 docs/ 是 `../../docs/z`); 确有不可修的登记 DOCLINK_ALLOW"},
    {"id": "inventory", "title": "真值登记", "fn": check_inventory, "quick": True,
     "fix": "端口/模型标识有变更时同步 inventory/*.yaml 真值表"},
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
    {"id": "usb4", "title": "USB4 三角环链路", "fn": check_usb4, "quick": False,
     "fix": "地址/路由不符 => 对照 inventory/net.yaml 与归档 §6.3/§6.6; "
            "链路不通 => 先查 BIOS USB4 安全等级与是否冷启动(归档 §6.5)"},
    {"id": "gates", "title": "内存门禁", "fn": check_gates, "quick": False,
     "fix": "load-gate 缺失需补部署到 /usr/local/bin; 余量 ≤0 先卸载或清残留; "
            "loadavg>8 等负载回落再加载"},
    {"id": "engine", "title": "引擎态与残留", "fn": check_engine, "quick": False,
     "fix": "残留用 infer-unload 或清 llama/rpc 进程; 端口在听但 RSS 异常需查进程归属"},
    {"id": "backend", "title": "引擎后端与回滚基线", "fn": check_backend, "quick": False,
     "fix": "默认单站引擎=HIP、分布式(/opt)=Vulkan 是本集群的**既定形态**; 后端变了先查是谁改的 "
            "(studio 自更新 / UPGRADE_SOP 升级 / 有人换构建) 再决定是否改期望值, 并把台账 §2.6 "
            "的后端矩阵同步; 回滚基线缺失 => 从同版本站 tar 分发补回 "
            "(UPGRADE_SOP §6: 保留 `<现役>` + `9859` 两个版本目录以支持分钟级回滚)"},
    {"id": "models", "title": "模型库完整性", "fn": check_models, "quick": False,
     "fix": "孤儿 `cluster.py models link --go`; 断链 `cluster.py models prune --go`"},
    {"id": "stations", "title": "三站实况对账", "fn": check_stations, "quick": False,
     "fix": "conf/权重/凭据/端口/插件任一项不符 —— 见明细, 一律以站上实况为准改仓库侧"},
]
MARKS = {"PASS": "✓", "WARN": "▲", "FAIL": "✕"}


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--quick", action="store_true", help="仅本地快检 (pre-commit)")
    ap.add_argument("--only", default="", help="逗号分隔的断言 id")
    ap.add_argument("--list", action="store_true", help="只列断言清单")
    args = ap.parse_args()

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

    results, failures = [], 0
    for c in selected:
        try:
            status, note, detail = c["fn"]({})
        except Exception as e:
            status, note, detail = "FAIL", f"{type(e).__name__}: {e}", []
        results.append((c["id"], c["title"], status, note, detail))
        if status == "FAIL":
            failures += 1

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
    bad = [r for r in results if r[2] in ("FAIL", "WARN")]
    if bad:
        fixes = {c["id"]: c.get("fix", "") for c in CHECKS}
        print("\n  ── 处置建议 (红灯优先) ──")
        for cid, _t, status, _n, _d in sorted(bad, key=lambda r: r[2] != "FAIL"):
            print(f"    {MARKS[status]} {cid:10s} {fixes.get(cid, '')}")

    n_fail = sum(1 for r in results if r[2] == "FAIL")
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
