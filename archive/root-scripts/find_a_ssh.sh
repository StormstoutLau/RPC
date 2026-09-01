#!/bin/bash
# find_a_ssh.sh — 对活动 IP 逐个试 ssh hostname (找 A 站)
for ip in 192.168.1.21 192.168.1.29 192.168.1.31 192.168.1.7 192.168.1.3 192.168.1.33; do
  echo -n "$ip: "
  timeout 5 ssh -o ConnectTimeout=3 -o StrictHostKeyChecking=no -o BatchMode=yes scott-lau@$ip 'echo $HOSTNAME' 2>&1 | head -1
done