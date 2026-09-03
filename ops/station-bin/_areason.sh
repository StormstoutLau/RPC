#!/bin/bash
echo "== unsloth studio run --help 中 reasoning/thinking 相关 =="
~/.local/bin/unsloth studio run --help 2>&1 | grep -iE "reasoning|thinking|effort|--fit|n-reason|reason" | head -15
echo "== 相关 env =="
~/.local/bin/unsloth studio run --help 2>&1 | grep -iE "UNSLOTH.*REASON|REASON.*=" | head