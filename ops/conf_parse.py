"""llama 实例 conf 解析 —— 与 ops/station-bin/conf-lib.sh 同一格式（P1 #4）。

契约: spec/review-p1-remediation/DESIGN.md §4.2/§4.4
  · 双引号 + 固定四类转义 `\\\\ \\" \\$ \\``；
  · 兼容历史未加引号的值；
  · 单引号原样（不做转义）；
  · 未知转义（如 \\q）原样保留；
  · 忽略注释 / 空行 / 无 `=` 行。

只依赖 stdlib；不导入 paramiko / cluster。`cluster._parse_conf` 在函数内委托本模块。
"""
_ESC = {"\\": "\\", '"': '"', "$": "$", "`": "`"}


def _unescape(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s) and s[i + 1] in _ESC:
            out.append(_ESC[s[i + 1]])
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _value(raw: str) -> str:
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        q = v[0]
        v = v[1:-1]
        return _unescape(v) if q == '"' else v
    return _unescape(v)


def parse_conf(text: str) -> dict:
    d = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        d[k.strip()] = _value(v)
    return d


def get_value(text: str, key: str) -> str:
    return parse_conf(text).get(key, "")
