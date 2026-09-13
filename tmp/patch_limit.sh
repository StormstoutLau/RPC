#!/bin/bash
# Make a temp copy of opencode.jsonc with qwen/nemotron/gpt-oss limit.context -> 32768
# (align with think-flavor engine) - for repair-path validation only.
# Then run opencode big-prompt again; expect: compaction NOT ContextOverflowError.
CONF=~/.config/opencode/opencode.jsonc
cp "$CONF" "$CONF.bak-ctx-test" || { echo "backup failed"; exit 1; }
echo "backed up to $CONF.bak-ctx-test"

python3 - <<'PY'
import re, io
p = "/root/.config/opencode/opencode.jsonc" if False else __import__("os").path.expanduser("~/.config/opencode/opencode.jsonc")
s = open(p, encoding="utf-8").read()
# replace limit.context values: "context": 131072 AND "context": 131072 (limit block + body)
s2 = re.sub(r'("context"):\s*131072', r'\1: 32768', s)
# also the shorthand "context": 131072 lines
if s2 == s:
    print("NO replacement happened - check pattern")
else:
    open(p, "w", encoding="utf-8").write(s2)
    print("patched limit.context 131072 -> 32768")
    # show diff lines
    for line in s2.splitlines():
        if "context" in line and "32768" in line:
            print("  >", line.strip())
PY