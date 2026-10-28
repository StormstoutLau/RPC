#!/bin/bash
echo "== B 站 studio server log 尾部 (opencode 报错相关) =="
tail -40 /home/scott-lau/.unsloth/studio/logs/server/server-20260904-020330-pid122013.log
echo
echo "== 含 error/traceback =="
grep -iE "error|traceback|exception|UnsupportedOperation|400|500" /home/scott-lau/.unsloth/studio/logs/server/server-20260904-020330-pid122013.log | tail -15