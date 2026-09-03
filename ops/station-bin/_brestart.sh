#!/bin/bash
echo "== /etc/llama-instances (模型清单) =="
ls -l /etc/llama-instances/ 2>/dev/null
echo "== 各 env 的模型 =="
for f in /etc/llama-instances/*.env; do echo "[$f]"; grep -iE "MODEL|NAME|PORT" "$f" 2>/dev/null | head -3; done
echo "== 单元 Restart 策略 =="
systemctl cat "llama-server@nvidia-nemotron-3-super-120b-a12b" 2>/dev/null | grep -iE "Restart|ExecStart=" | head
echo "== 该单元进程 pid =="
systemctl show "llama-server@nvidia-nemotron-3-super-120b-a12b" -p MainPID --no-pager 2>/dev/null