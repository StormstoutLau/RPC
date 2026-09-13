#!/bin/bash
# 等引擎当前生成结束后，重启 fetch 已完成文件
sleep 30
echo "== 引擎最后 2 行 =="
tail -3 /tmp/nem_b_run.log | grep -iE 'n_gen|release' | tail -2
echo "== 是否已有 jsonl =="
ls -la /tmp/res_nem120b/*.jsonl 2>/dev/null || echo "(B站无 res_nem120b，结果在 Windows 侧)"