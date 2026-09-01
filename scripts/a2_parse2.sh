#!/bin/bash
# A2-2: 切出 tg 稳态段(首个 n_nodes:1553 图起)并算每 token RPC 账单
TG_START=$(grep -an 'n_nodes: 1553' /tmp/a2_inf.log | head -1 | cut -d: -f1)
TG_END=$(wc -l < /tmp/a2_inf.log)
TG_COUNT=$(grep -ac 'n_nodes: 1553' /tmp/a2_inf.log)
echo "tg段: 行 $TG_START..$TG_END, 1553图数=$TG_COUNT"
sed -n "${TG_START},${TG_END}p" /tmp/a2_inf.log > /tmp/a2_tg.log

G=$(grep -ac 'graph_compute' /tmp/a2_tg.log)
S=$(grep -ac 'set_tensor]' /tmp/a2_tg.log)
GT=$(grep -ac 'get_tensor' /tmp/a2_tg.log)
SB=$(grep -a 'set_tensor]' /tmp/a2_tg.log | grep -o 'size: [0-9]*' | cut -d' ' -f2 | paste -sd+ | bc)
GB=$(grep -a 'get_tensor' /tmp/a2_tg.log | grep -o 'size: [0-9]*' | cut -d' ' -f2 | paste -sd+ | bc)
echo "tg段: graph=$G set_tensor=$S(${SB}B) get_tensor=$GT(${GB}B)"
echo "每token(除以129): graph=$(echo "scale=2; $G/129" | bc) set=$(echo "scale=2; $S/129" | bc) get=$(echo "scale=2; $GT/129" | bc)"
echo "每token字节: set=$(echo "scale=0; $SB/129" | bc)B get=$(echo "scale=0; $GB/129" | bc)B 总=$(echo "scale=0; ($SB+$GB)/129" | bc)B"

echo "=== tg段 set_tensor 尺寸 Top6 ==="
grep -a 'set_tensor]' /tmp/a2_tg.log | grep -o 'size: [0-9]*' | sort | uniq -c | sort -rn | head -6
echo "=== tg段 get_tensor 尺寸 Top6 ==="
grep -a 'get_tensor' /tmp/a2_tg.log | grep -o 'size: [0-9]*' | sort | uniq -c | sort -rn | head -6
echo "=== tg段首个完整循环(前14行) ==="
head -14 /tmp/a2_tg.log
