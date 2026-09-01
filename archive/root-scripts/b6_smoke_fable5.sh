#!/bin/bash
# b6_smoke_fable5.sh — B6 冒烟 gpt-oss-120b-fable-5-distilled (双机 RPC, 看门狗布防)
set -u
exec 2>&1

sed -e 's|MODEL = "deepseek-v4-flash"|MODEL = "gpt-oss-120b-fable-5-distilled"|' \
    -e 's|OUT = "/tmp/b6_smoke_deepseek.jsonl"|OUT = "/tmp/b6_smoke_fable5.jsonl"|' \
    -e 's|b6_smoke_deepseek[.]py|b6_smoke_fable5.py|' \
    -e 's|b6_ds_watchdog|b6_f5_watchdog|g' \
    /tmp/b6ds.sh > /tmp/b6_smoke_fable5_run.sh

bash /tmp/b6_smoke_fable5_run.sh
