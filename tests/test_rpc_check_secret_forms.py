"""`secrets` 断言的形态覆盖 —— 先验红夹具（2026-10-21）

守的是什么：
    2026-10-21 安全评审发现仓库里有多处**非 `sk-` 形态**的明文凭据（Beszel 账号口令、
    SSH 口令），而 `ops/rpc_check.py` 的 `secrets` 断言完全看不见它们。两个结构原因：
      ① `SECRET_RE` 只认 `sk-[A-Za-z0-9_-]{16,}` 一种形态；
      ② `check_secrets` 有一句 `if "sk-" not in text: continue` —— **整文件短路**，
         任何不含 `sk-` 的文件连正则都不会跑。
    ⇒ 门禁长期全绿，不是因为"干净"，而是因为"看不见"。

本文件钉住三件事：
    1. `SECRET_RE` 必须命中「赋值形态」的凭据（shell `PASS="…"` / JSON `"password":"…"`）；
    2. `SECRET_RE` 必须命中私钥块头与常见云厂商 key 前缀；
    3. ★ `SECRET_RE` **不得**误伤 `SSH_ASKPASS_REQUIRE = "force"` 这类含 `pass` 子串的普通配置
       （扩形态时最容易踩的误报，2026-10-21 摸底实测命中过一次）；
    4. ★ **不得**再有 `sk-` 短路预筛（否则前三条在真实扫描里全部失效）。
    5. ★★ **后缀式变量名**（`ADMIN_PASS` / `DB_PWD`）**必须命中** —— 2026-10-24（O-174）补：
       原口令族用 `\b(?:pass|…)`，而 `_` 与 `P` 之间**没有字边界** ⇒ 这类写法整条漏报
       （实测来源：一条 59 字符真凭据因此长期不被门禁看见）。

★★ 为什么样串要**拼接构造**而不是写字面量：
   本文件测的正是"明文凭据会被抓"，若把样串按字面写进来，**夹具自己就会命中 `secrets` 断言**
   （2026-10-21 实测：提交时 pre-commit 被自己的夹具拦下，红灯里逐条指的是本文件）。
   拼接后源码文本里不存在连续形态，正则仍按运行时拼好的字符串受测 ⇒ 两全。
   ⚠ 也正因如此，**真实凭据一个都不许出现在本文件**（历史清理过的口令不得再落库）。

⚠ 残留盲区（**已知、不假装覆盖**）：
   · 散文里写的"登录: `user` / `pass`"、askpass 脚本里的 `@echo <数字>` —— 无稳定形态；
   · **不带引号**的赋值（`password=abc12345`）—— 加这条分支会误伤 `if decision == "pass":`
     与 `PASS: derived-view` 这类正常文本（2026-10-21 实测），故**刻意不做**。
   以上只能人工清理 + 在安全文档里登记为盲区。

用法（退出码 0 = 全过）：
    py tests\\test_rpc_check_secret_forms.py
"""
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402

fails = []


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + extra if extra else ""))
    if not cond:
        fails.append(name)


SWORD = "pass" + "word"          # 拼出来，避免源码里出现连续标识符
SWD_UP = "PA" + "SS"             # 同上


# ── 1. 必须命中的形态（全部拼接构造，见文件头说明）──────────────────────
MUST_HIT = [
    ("shell 赋值 " + SWD_UP + "=\"…\"", SWD_UP + '="abc12345"'),
    ("JSON \"" + SWORD + "\":\"…\"", '"' + SWORD + '":"s3cretValue"'),
    ("yaml " + SWORD[0:4] + ": '…'", SWORD[0:4] + ": 'sup3rs3cret'"),
    ("私钥块头", "-----BEGIN " + "OPENSSH PRIVATE KEY-----"),
    ("AWS AKID", "AK" + "IAIOSFODNN7EXAMPLE"),
    ("GitHub PAT", "gh" + "p_" + "a" * 36),
    ("unsloth key（原形态，不得回退）", "s" + "k-unsloth-" + "0" * 20),
    # ★★ 2026-10-24（O-174）：**后缀式变量名**（运维脚本里的常见写法）。
    #   实测来源：历史重写时发现 `ADMIN_PASS` 的 59 字符真凭据长期逃过门禁 ——
    #   原正则用 `\b(?:pass|…)` ⇒ `_` 与 `P` 之间**没有字边界** ⇒ 整条被漏。
    ("后缀式 " + "ADMIN_" + SWD_UP + "=\"…\"", "ADMIN_" + SWD_UP + '="abc12345"'),
    ("后缀式 DB_PWD='…'", "DB_" + "PWD" + "='abc12345'"),
]
for name, sample in MUST_HIT:
    hit = bool(R.SECRET_RE.search(sample))
    chk(f"SECRET_RE 命中 {name}", hit, "" if hit else f"漏报: {sample[:24]!r}")

# ── 2. 不得误伤的形态 ────────────────────────────────────────────────
MUST_MISS = [
    ("SSH_ASKPASS_REQUIRE 配置", '$env:SSH_ASK' + SWD_UP + '_REQUIRE = "force"'),
    ("占位符 --token <可选>", "--token <可选>"),
    ("环境变量引用 " + SWORD + "=${BESZEL_PASS}", SWORD + "=${BESZEL_PASS}"),
    ("空口令 " + SWORD + "=", SWORD + '=""'),
    # ★ 下面三条是 2026-10-21 扩形态时**实测撞到的误报**：
    #   代码里 `if decision == "pass":`、测试输出 `PASS: derived-view`、
    #   PowerShell 拼接 `" pass=" + $x + " "` 都会被朴素正则抓成凭据。
    ("代码判定 " + SWORD[0:4] + ":", 'if decision == "' + SWORD[0:4] + '":'),
    ("测试输出 " + SWD_UP + ": ...", SWD_UP + ": derived-view"),
    ("PS 拼接 " + SWORD[0:4] + "=\" + …", '" ' + SWORD[0:4] + '=" + $review.output.' + SWORD[0:4] + ' + "'),
    # ★ 脱敏后的占位符本身不得再被当成凭据（否则"清理即命中"，门禁永远红）：
    #   2026-10-21 第一版清理用了 `<REDACTED-...>`，结果仍被同一正则命中。
    ("脱敏占位 ***", SWD_UP + '="***"'),
]
for name, sample in MUST_MISS:
    hit = bool(R.SECRET_RE.search(sample))
    chk(f"SECRET_RE 不误伤 {name}", not hit, "" if not hit else f"误报: {sample!r}")

# ── 3. check_secrets 不得有 sk- 短路预筛 ─────────────────────────────
# 判据取**代码常量**而不是源码文本：docstring 里会正当地提到 `"sk-" not in text`
# 这段被删掉的坏代码（解释它为什么危险），拿源码做子串匹配会把自己的注释判成违规。
_consts = R.check_secrets.__code__.co_consts
chk("check_secrets 无 `sk-` 短路常量",
    "sk-" not in _consts,
    "" if "sk-" not in _consts else "短路仍在 ⇒ 非 sk- 文件不会进正则")

TOTAL = len(MUST_HIT) + len(MUST_MISS) + 1
print()
if fails:
    print(f"RESULT: FAIL {len(fails)}/{TOTAL} —— " + "; ".join(fails))
    sys.exit(1)
print(f"RESULT: PASS {TOTAL}/{TOTAL} 形态覆盖与误报边界均成立")
sys.exit(0)
