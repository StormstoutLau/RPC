"""conf_parse（P1 #4）—— 与站上 conf-lib.sh 同一格式的 Python 读侧。

覆盖 IMPLEMENTATION §9.1 #4 行：
  · 双引号 + 固定四类转义 `\\\\ \\" \\$ \\``；
  · 历史未加引号值兼容；
  · 单引号原样；
  · 空值 / 未知转义 / 注释 / 空行 / 缺失键。

用法: py tests\\test_conf_parse.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

fails = []


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


try:
    from conf_parse import parse_conf, get_value
except Exception as e:                                   # noqa: BLE001
    print(f"FAIL  import conf_parse: {type(e).__name__}: {e}")
    print("\nRESULT: FAIL (conf_parse 不可导入)")
    sys.exit(1)

TEXT = r'''
# 注释行
CTX=32768
MODEL_PATH="/a b/\$c/\"d\".gguf"
PLAIN=/plain path
SINGLE='x y'
EMPTY=""
BACK="a\\b"
UNKNOWN="x\qy"
SPACED = "v"   
'''

d = parse_conf(TEXT)
chk("双引号 + 空格 + $ + 转义引号",
    get_value(TEXT, "MODEL_PATH") == '/a b/$c/"d".gguf', get_value(TEXT, "MODEL_PATH"))
chk("未加引号历史值", get_value(TEXT, "PLAIN") == "/plain path")
chk("单引号原样", get_value(TEXT, "SINGLE") == "x y")
chk("空值", get_value(TEXT, "EMPTY") == "")
chk("反斜杠转义", get_value(TEXT, "BACK") == "a\\b", repr(get_value(TEXT, "BACK")))
chk("未知转义原样保留", get_value(TEXT, "UNKNOWN") == "x\\qy", repr(get_value(TEXT, "UNKNOWN")))
chk("普通键", d.get("CTX") == "32768")
chk("键两侧空白", d.get("SPACED") == "v")
chk("注释不是键", " 注释行" not in d and "注释行" not in d)
chk("缺失键返回空", get_value(TEXT, "NOPE") == "")
chk("空文本不抛", parse_conf("") == {})

print("\nRESULT: " + ("PASS" if not fails else f"FAIL ({len(fails)} 项)") +
      " · 失败: " + (", ".join(fails) if fails else "无"))
sys.exit(0 if not fails else 1)
