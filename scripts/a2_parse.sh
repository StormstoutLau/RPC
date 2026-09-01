#!/bin/bash
# A2: 解析 /tmp/rpc_debug.log 推理段 (graph_compute 起 ~ get_tensor 止)
# 输出: 命令计数 / 字节总量 / 尺寸直方图 / 图规模分布
set -e
INF=/tmp/a2_inf.log
sed -n '2218,9352p' /tmp/rpc_debug.log > "$INF"

echo "=== 推理段命令计数 ==="
echo "set_tensor:      $(grep -ac 'set_tensor]' $INF)"
echo "set_tensor_hash: $(grep -ac 'set_tensor_hash' $INF)"
echo "get_tensor:      $(grep -ac 'get_tensor' $INF)"
echo "graph_compute:   $(grep -ac 'graph_compute' $INF)"

echo "=== set_tensor 字节总量 ==="
grep -a 'set_tensor]' $INF | grep -o 'size: [0-9]*' | cut -d' ' -f2 | paste -sd+ | bc

echo "=== get_tensor 字节总量 ==="
grep -a 'get_tensor' $INF | grep -o 'size: [0-9]*' | cut -d' ' -f2 | paste -sd+ | bc

echo "=== set_tensor 尺寸 Top10 (次数 尺寸) ==="
grep -a 'set_tensor]' $INF | grep -o 'size: [0-9]*' | sort | uniq -c | sort -rn | head -10

echo "=== get_tensor 尺寸 Top10 (次数 尺寸) ==="
grep -a 'get_tensor' $INF | grep -o 'size: [0-9]*' | sort | uniq -c | sort -rn | head -10

echo "=== graph n_nodes 分布 (次数 规模) ==="
grep -a 'graph_compute' $INF | grep -o 'n_nodes: [0-9]*' | sort | uniq -c | sort -rn | head -10

echo "=== 推理段前 25 行 (相位头) ==="
head -25 "$INF"
