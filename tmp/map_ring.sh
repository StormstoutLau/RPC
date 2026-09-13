#!/bin/bash
# Overall ring topology map: A, B thunderbolt neighbor MACs to identify physical links
echo "===== A(sco-lau-NEX 192.168.1.33 .1) ====="
ssh scott-lau@scott-lau-GTR-Pro.local "echo 'B thunderbolt0:'; ip neigh show dev thunderbolt0; echo 'B thunderbolt1:'; ip neigh show dev thunderbolt1; echo 'B threat1 MAC:'; ip -br link show thunderbolt1 | awk '{print \$NF}'" 2>/dev/null
echo "===== B(sco-lau-GTR-Pro 192.168.1.32 .2) ====="
ssh scott-lau@scott-lau-GTR-Pro.local "echo 'B thunderbolt0:'; ip neigh show dev thunderbolt0; echo 'B thunderbolt1:'; ip neigh show dev thunderbolt1" 2>/dev/null