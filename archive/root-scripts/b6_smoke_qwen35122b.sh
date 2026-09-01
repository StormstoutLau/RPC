#!/bin/bash
# b6_smoke_qwen35122b.sh — B6 冒烟 qwen3.5-122b-a10b-claude-distill-v2-i1 (单机 B 站)
set -u
exec 2>&1

sed -e 's|MODEL = "deepseek-v4-flash"|MODEL = "qwen3.5-122b-a10b-claude-distill-v2-i1"|' \
    -e 's|OUT = "/tmp/b6_smoke_deepseek.jsonl"|OUT = "/tmp/b6_smoke_qwen35122b.jsonl"|' \
    -e 's|b6_smoke_deepseek[.]py|b6_smoke_q35.py|' \
    -e 's|b6_ds_watchdog|b6_q35_watchdog|g' \
    /tmp/b6ds.sh > /tmp/b6_smoke_q35_run.sh

bash /tmp/b6_smoke_q35_run.sh
